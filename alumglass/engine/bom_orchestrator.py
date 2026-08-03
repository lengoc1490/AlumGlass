"""BomOrchestrator — Engine tính BOM config-driven, dùng Formula Builder.

NGUYÊN TẮC: AlumGlass chỉ config, không hardcode nghiệp vụ.
- Mọi logic đến từ DB: Bom Item, Cost Bucket, Cost Template, Profile System, Product Type.
- Tính toán ủy thác cho Formula Builder: FormulaEngine (Bom Items) + FlexibleFormulaEngine (Cost Template).
- Engine này chỉ làm: đọc config → resolve biến → build formulas → gọi FB → lưu kết quả.

Flow 7 phase:
  B0: Version pinning
  B1: Gather inputs (al_bom_vars + scoped vars từ DB)
  B2: Pre-fetch master data (batch query)
  B3: Build formula list cho FormulaEngine (FB)
  B4: Calculate Bom Items qua FormulaEngine (DAG + topo sort)
  B5: Aggregate cost buckets (Python loop)
  B6: Calculate Cost Template qua FlexibleFormulaEngine (FB)
  B7: Save results
"""
import frappe
import json
import re
import math
from collections import defaultdict


# ── CONFIG: Variable name mapping (field → formula variable) ──────────
# Đây là mapping DUY NHẤT được định nghĩa ở code level.
# Giá trị thực tế đến từ DB records (AL Profile System, AL Product Type).
# Mỗi dòng: (variable_name, source_doctype, source_field)
SCOPED_VAR_SOURCES = {
    # Từ AL Profile System (theo profile_system của Bom Set)
    "OFFSET_FRAME":     ("AL Profile System", "offset_frame"),
    "OFFSET_GLASS":     ("AL Profile System", "offset_glass"),
    "OFFSET_FIXED":     ("AL Profile System", "offset_fixed"),
    "OFFSET_DO_NGANG":  ("AL Profile System", "offset_crossbar"),
    # Từ AL Product Type (theo product_type của Bom Set)
    "NC_SX_PCT":        ("AL Product Type", "nc_pct"),
    "NC_LD_PCT":        ("AL Product Type", "nc_ld_rate"),
    "PROFIT_MARGIN":    ("AL Product Type", "profit_margin"),
}

# ── CONFIG: Các field trong Bom Item chứa công thức (Small Text) ─────
BOM_ITEM_FORMULA_FIELDS = ["width", "height", "qty", "show_condition",
                            "item_condition_formula", "rule_input_expr"]

# ── CONFIG: Các field kết quả ghi vào Quotation Item ─────────────────
OUTPUT_FIELDS = [
    "al_gia_vat", "al_gia_ban", "al_bom_result",
]


class BomOrchestrator:
    """Engine tính BOM 7-phase, hoàn toàn config-driven."""

    def __init__(self, quotation_item_name):
        self.quotation_item_name = quotation_item_name
        self.inputs = {}
        self.bom_items = []
        self.row_literals = {}
        self.bom_result = []
        self.buckets = defaultdict(float)
        self.cost_result = {}
        self.gia_vat = 0

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════
    def run(self):
        self.b0_version_pinning()
        self.b1_gather_inputs()
        self.b2_prefetch_master_data()
        self.b3_build_formulas()
        self.b4_calculate_bom_items()
        self.b5_aggregate_cost_buckets()
        self.b6_calculate_cost_template()
        self.b7_save_results()
        return self._build_response()

    # ══════════════════════════════════════════════════════════════════
    # B0: Version Pinning
    # ══════════════════════════════════════════════════════════════════
    def b0_version_pinning(self):
        qi = frappe.get_doc("Quotation Item", self.quotation_item_name)
        self.bom_code = qi.get("al_bom")
        self.bom_version_name = qi.get("al_bom_version")

        if self.bom_version_name:
            self.bom_version = frappe.get_doc("AL BOM Version", self.bom_version_name)
        elif self.bom_code:
            bom = frappe.get_doc("AL BOM", self.bom_code)
            if bom.current_version:
                self.bom_version = frappe.get_doc("AL BOM Version", bom.current_version)
                self.bom_version_name = bom.current_version
            else:
                frappe.throw(f"BOM '{self.bom_code}' chưa có version nào được Published")

    # ══════════════════════════════════════════════════════════════════
    # B1: Gather Inputs — đọc từ al_bom_vars JSON + resolve scoped vars
    # ══════════════════════════════════════════════════════════════════
    def b1_gather_inputs(self):
        # ── 1.1 Đọc user inputs từ al_bom_vars JSON ──────────────────
        bom_vars_str = frappe.db.get_value("Quotation Item",
                                            self.quotation_item_name, "al_bom_vars")
        bom_vars = {}
        if bom_vars_str:
            try:
                bom_vars = json.loads(bom_vars_str) if isinstance(bom_vars_str, str) else bom_vars_str
            except json.JSONDecodeError:
                pass

        self.inputs.update(bom_vars.get("extra_vars", {}) if isinstance(
            bom_vars.get("extra_vars"), dict) else {})

        # ── 1.2 Global Variables từ Formula Builder ──────────────────
        for gv in frappe.get_all("Formula Global Variable",
                                  fields=["var_name", "constant_value"]):
            try:
                self.inputs[gv["var_name"]] = float(gv["constant_value"])
            except (ValueError, TypeError):
                self.inputs[gv["var_name"]] = gv["constant_value"]

        # ── 1.3 Resolve scoped variables từ DB config ────────────────
        if self.bom_version and self.bom_version.bom:
            bom = frappe.get_doc("AL BOM", self.bom_version.bom)
            if bom.bom_set:
                bom_set = frappe.get_doc("AL Bom Set", bom.bom_set)

                # Lấy giá trị từ AL Profile System
                if bom_set.profile_system:
                    ps = frappe.get_doc("AL Profile System", bom_set.profile_system)
                    for var_name, (doctype, field) in SCOPED_VAR_SOURCES.items():
                        if doctype == "AL Profile System":
                            self.inputs[var_name] = ps.get(field) or 0

                # Lấy giá trị từ AL Product Type
                if bom_set.product_type:
                    pt = frappe.get_doc("AL Product Type", bom_set.product_type)
                    for var_name, (doctype, field) in SCOPED_VAR_SOURCES.items():
                        if doctype == "AL Product Type":
                            self.inputs[var_name] = pt.get(field) or 0

        # ── 1.4 Fallback từ Calculation Rule CONSTANT ────────────────
        for var_name in SCOPED_VAR_SOURCES:
            if var_name not in self.inputs or self.inputs[var_name] == 0:
                fallback_code = var_name.replace("_", "-")
                if frappe.db.exists("AL Calculation Rule", fallback_code):
                    rule = frappe.get_doc("AL Calculation Rule", fallback_code)
                    if rule.rule_type == "CONSTANT":
                        self.inputs[var_name] = rule.constant_value or 0

        # ── 1.5 Merge user input values (bom_vars ghi đè) ────────────
        for key in list(bom_vars.keys()):
            if key not in ("extra_vars", "accessory_set", "glass_master"):
                self.inputs[key] = bom_vars[key]

    # ══════════════════════════════════════════════════════════════════
    # B2: Pre-fetch Master Data — batch query từ DB
    # ══════════════════════════════════════════════════════════════════
    def b2_prefetch_master_data(self):
        if not self.bom_version or not self.bom_version.bom_set_snapshot:
            frappe.throw("BOM Version không có snapshot")

        snap = json.loads(self.bom_version.bom_set_snapshot) if isinstance(
            self.bom_version.bom_set_snapshot, str
        ) else self.bom_version.bom_set_snapshot
        self.bom_items = snap.get("items", [])

        # ── Batch query Item master data ─────────────────────────────
        item_codes = []
        price_base_items = []
        for item in self.bom_items:
            ic = item.get("item_code")
            if ic: item_codes.append(ic)
            pbi = item.get("price_base_item")
            if pbi: price_base_items.append(pbi)

        # Trọng lượng từ Item
        weights = {}
        if item_codes:
            for it in frappe.get_all("Item", filters={"name": ("in", item_codes)},
                                      fields=["name", "weight_per_unit"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)

        # Giá từ Item Price
        prices = {}
        all_price_items = list(set(item_codes + price_base_items))
        if all_price_items:
            for ip in frappe.get_all("Item Price",
                                      filters={"item_code": ("in", all_price_items),
                                               "price_list": "Standard Selling"},
                                      fields=["item_code", "price_list_rate"]):
                prices[ip["item_code"]] = ip["price_list_rate"]

        # ── Build row_literals cho từng dòng Bom Item ─────────────────
        for item in self.bom_items:
            slug = item.get("slug", "")
            ic = item.get("item_code", "")
            pbi = item.get("price_base_item", "")

            lit = {
                "weight_per_unit": weights.get(ic, 0) if ic else 0,
                "unit_price": prices.get(pbi, 0) if pbi else (prices.get(ic, 0) if ic else 0),
                "calc_pattern": item.get("calc_pattern", ""),
                "glass_thick": 0,
                "glass_type": "",
                "item_code": ic,  # resolved item code (có thể bị ghi đè bởi rule)
            }

            # Glass Master lookup
            if item.get("category") == "KINH" and item.get("default_glass_master"):
                gm = frappe.db.get_value("AL Glass Master", item["default_glass_master"],
                                          ["total_thick_mm", "glass_type"], as_dict=True)
                if gm:
                    lit["glass_thick"] = gm.get("total_thick_mm", 0)
                    lit["glass_type"] = gm.get("glass_type", "")

            # Dynamic Item Rule resolution
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_input = self._resolve_rule_input(item, lit)
                resolved = self._resolve_dynamic_item(item["item_rule"], rule_input)
                if resolved:
                    lit["item_code"] = resolved
                    lit["unit_price"] = prices.get(resolved, 0)
                    lit["weight_per_unit"] = weights.get(resolved, 0)

            self.row_literals[slug] = lit

    def _resolve_rule_input(self, item, lit):
        """Phân giải rule_input_expr: 'items.kinh_tren.glass_thick' → giá trị."""
        expr = item.get("rule_input_expr", "")
        ref_match = re.match(r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
        if ref_match:
            ref_slug, ref_field = ref_match.group(1), ref_match.group(2)
            ref_lit = self.row_literals.get(ref_slug, {})
            return ref_lit.get(ref_field, 0)
        # Fallback: dùng literals của chính item này
        return lit.get("glass_thick") if lit.get("glass_thick") else lit.get("glass_type", "")

    def _resolve_dynamic_item(self, rule_code, input_value):
        """Gọi AL Dynamic Item Rule để resolve item_code từ input."""
        from alumglass.al_formula_rules.doctype.al_dynamic_item_rule.al_dynamic_item_rule import resolve_item
        result = resolve_item(rule_code, input_value)
        return result.get("item_code") if result else None

    # ══════════════════════════════════════════════════════════════════
    # B3: Build Formulas — tạo formula list cho FormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b3_build_formulas(self):
        """Build list of {name, formula} dicts cho FormulaEngine.

        Mỗi Bom Item field trong BOM_ITEM_FORMULA_FIELDS → 1 formula.
        Cross-row reference: items.kinh_tren.width → kinh_tren__width.
        Literal injection: weight_per_unit, unit_price... vào context.
        Synthetic formulas: unit_qty, total_qty, line_total.
        """
        self.bom_formulas = []

        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            # Inject literals vào context (để cross-row và synthetic formulas dùng)
            for key in ("weight_per_unit", "unit_price", "calc_pattern",
                         "glass_thick", "glass_type"):
                if key in lit:
                    self.inputs[f"{slug}__{key}"] = lit[key]

            # Pre-set defaults cho các field có thể không có formula (tránh NameError trong engine)
            for field in ("width", "height", "qty", "calc_pattern", "weight_per_unit", "unit_price"):
                if f"{slug}__{field}" not in self.inputs:
                    self.inputs[f"{slug}__{field}"] = "" if field == "calc_pattern" else 0

            # Build formulas từ Bom Item fields
            for field in BOM_ITEM_FORMULA_FIELDS:
                expr = item.get(field)
                if expr and str(expr).strip():
                    normalized = re.sub(
                        r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', str(expr))
                    self.bom_formulas.append({
                        "name": f"{slug}__{field}",
                        "formula": normalized,
                    })

            # Synthetic formulas (dev-defined, based on calc_pattern)
            self.bom_formulas.append({
                "name": f"{slug}__unit_qty",
                "formula": (f"lookup_calc_pattern("
                            f"{slug}__calc_pattern, "
                            f"{slug}__width, "
                            f"{slug}__height, "
                            f"{slug}__weight_per_unit)"),
            })
            self.bom_formulas.append({
                "name": f"{slug}__total_qty",
                "formula": f"{slug}__unit_qty * {slug}__qty",
            })
            self.bom_formulas.append({
                "name": f"{slug}__line_total",
                "formula": f"{slug}__total_qty * {slug}__unit_price",
            })

    # ══════════════════════════════════════════════════════════════════
    # B4: Calculate Bom Items — dùng FormulaEngine (FB) thay vì eval()
    # ══════════════════════════════════════════════════════════════════
    def b4_calculate_bom_items(self):
        """Tính Bom Items qua FormulaEngine.
        Engine tự build DAG, topological sort, evaluate.
        AlumGlass chỉ chuẩn bị formulas + context, không tự eval.
        """
        from formula_builder.formula_utils.engine_public import FormulaEngine
        from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import lookup_calc_pattern

        # Build engine với safe_funcs (context passed to calculate, not __init__)
        engine = FormulaEngine(
            formulas=self.bom_formulas,
            safe_funcs={
                "lookup_calc_pattern": lookup_calc_pattern,
                "roundup": lambda x, y: math.ceil(x),
            },
            on_error="raise",
            deterministic=True,
        )

        # Calculate — engine tự DAG + topo sort + evaluate
        result = engine.calculate(dict(self.inputs))

        # Merge kết quả vào inputs cho B6 dùng
        self.inputs.update(result)

        # Build bom_result từ result
        self.bom_result = []
        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            w = result.get(f"{slug}__width", 0)
            h = result.get(f"{slug}__height", 0)
            q = result.get(f"{slug}__qty", 0)
            unit_qty = result.get(f"{slug}__unit_qty", 0)
            total_qty = result.get(f"{slug}__total_qty", 0)
            line_total = result.get(f"{slug}__line_total", 0)

            self.bom_result.append({
                "slug": slug,
                "item_code": lit.get("item_code", item.get("item_code", "")),
                "width": w, "height": h, "qty": q,
                "unit_qty": unit_qty, "total_qty": total_qty,
                "unit_price": lit.get("unit_price", 0),
                "line_total": line_total,
                "cost_bucket": item.get("cost_bucket", ""),
            })

    # ══════════════════════════════════════════════════════════════════
    # B5: Aggregate Cost Buckets — gom line_total theo cost_bucket
    # ══════════════════════════════════════════════════════════════════
    def b5_aggregate_cost_buckets(self):
        """Gom line_total theo cost_bucket (đọc từ Bom Item, không hardcode bucket code)."""
        buckets = defaultdict(float)
        for row in self.bom_result:
            bk = row.get("cost_bucket", "")
            if bk:
                buckets[bk] += row.get("line_total", 0)
        self.buckets = dict(buckets)

    # ══════════════════════════════════════════════════════════════════
    # B6: Calculate Cost Template — dùng FlexibleFormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b6_calculate_cost_template(self):
        """Tính Cost Template qua FlexibleFormulaEngine.

        Engine tự DAG + topo sort. AlumGlass chỉ cung cấp:
        - global_formulas: từ Cost Template DB
        - extra_context: bucket values + global vars
        """
        if not self.bom_version or not self.bom_version.cost_template_snapshot:
            return

        from formula_builder.flexible_formula_engine import (
            FlexibleFormulaEngine, EngineConfig)

        snap = json.loads(self.bom_version.cost_template_snapshot) if isinstance(
            self.bom_version.cost_template_snapshot, str
        ) else self.bom_version.cost_template_snapshot

        # Build global_formulas từ Cost Template
        global_formulas = []
        for item in snap.get("items", []):
            if item.get("calc_formula", "").strip():
                global_formulas.append({
                    "name": item["line_code"],
                    "formula": item["calc_formula"],
                })

        # Build extra_context: bucket values + global vars
        extra_context = dict(self.inputs)
        extra_context.update(self.buckets)

        # Pre-set ALL bucket codes referenced in Cost Template to 0 (tránh NameError)
        all_bucket_codes = frappe.get_all("AL Cost Bucket", pluck="name")
        for code in all_bucket_codes:
            if code not in extra_context:
                extra_context[code] = 0.0

        # Tính qua FlexibleFormulaEngine
        config = EngineConfig(
            global_formulas=global_formulas,
            extra_context=extra_context,
            on_error="raise",
            deterministic=True,
        )
        engine = FlexibleFormulaEngine(config)
        result = engine.calculate(dict(self.inputs))

        # Collect results (CalculationResult → dict via .values)
        values = result.values if hasattr(result, 'values') else dict(result)
        self.cost_result = dict(values)
        self.gia_vat = self.cost_result.get("GIA_VAT", 0)

    # ══════════════════════════════════════════════════════════════════
    # ── B7: Save Results — ghi Quotation Item + ConfigSnapshot ──────
    def b7_save_results(self):
        # Ghi tóm tắt (cho hiển thị nhanh)
        frappe.db.set_value("Quotation Item", self.quotation_item_name,
                            "al_gia_vat", self.gia_vat)
        frappe.db.set_value("Quotation Item", self.quotation_item_name,
                            "al_gia_ban", self.cost_result.get("GIA_BAN", 0))

        # Ghi TOÀN BỘ kết quả vào JSON (linh hoạt, mọi bucket đều lưu được)
        full_result = {
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            "lines": self.bom_result,
            "gia_vat": self.gia_vat,
        }
        frappe.db.set_value("Quotation Item", self.quotation_item_name,
                            "al_bom_result", json.dumps(full_result, indent=2, default=str))
        frappe.db.commit()

        # Tạo ConfigSnapshot
        snap_name = frappe.generate_hash(length=15)
        frappe.db.sql("""INSERT INTO `tabConfigSnapshot`
            (name, bom_version, quotation_item_name, calculation_timestamp,
             inputs_json, result_json, creation, modified, owner, modified_by, docstatus)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), 'Administrator', 'Administrator', 0)""",
            (snap_name, self.bom_version_name, self.quotation_item_name,
             frappe.utils.now(),
             json.dumps(self.inputs, indent=2, default=str),
             json.dumps(full_result, indent=2, default=str)))
        frappe.db.commit()

        frappe.db.set_value("Quotation Item", self.quotation_item_name,
                            "al_config_snapshot", snap_name)
        frappe.db.commit()

    # ── Response builder ─────────────────────────────────────────────
    def _build_response(self):
        return {
            "gia_vat": self.gia_vat,
            "gia_ban": self.cost_result.get("GIA_BAN", 0),
            "tong_vl": self.cost_result.get("TONG_VL", 0),
            "tong_nc": self.cost_result.get("TONG_NC", 0),
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            "lines": self.bom_result,
        }
