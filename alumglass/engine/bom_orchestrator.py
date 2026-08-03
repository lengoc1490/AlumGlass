"""BomOrchestrator — Engine tính BOM config-driven, dùng Formula Builder.

NGUYÊN TẮC: AlumGlass chỉ config, không hardcode nghiệp vụ.
- Mọi logic đến từ DB: Bom Item, Cost Bucket, Cost Template, Profile System, Product Type.
- Tính toán ủy thác cho Formula Builder: FormulaEngine (Bom Items) + FlexibleFormulaEngine (Cost Template).
- Engine này chỉ làm: đọc config → resolve biến → build formulas → gọi FB → lưu kết quả.

Flow 7 phase:
  B0: Version pinning
  B1: Gather inputs (al_bom_vars + scoped vars từ DB — data-driven)
  B2: Pre-fetch master data (batch query)
  B3: Build formula list cho FormulaEngine (FB)
  B4: Calculate Bom Items qua FormulaEngine (DAG + topo sort)
  B5: Aggregate cost buckets (Python loop)
  B6: Calculate Cost Template qua FlexibleFormulaEngine (FB)
  B7: Save results (single commit)
"""
import frappe
import json
import re
import math
from collections import defaultdict


# ── CONFIG: Các field kết quả ghi vào Quotation Item ─────────────────
OUTPUT_FIELDS = [
    "al_gia_vat", "al_gia_ban", "al_bom_result",
]

# ── DEFAULT: Các field trong Bom Item chứa công thức ─────────────────
# Dùng khi Bom Set không có formula_fieldnames config
DEFAULT_FORMULA_FIELDS = ["width", "height", "qty", "show_condition",
                           "item_condition_formula", "rule_input_expr"]


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
        # Cached references (tránh load lại)
        self._qi_doc = None
        self._bom_doc = None
        self._formula_fieldnames = None

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
        self._qi_doc = frappe.get_doc("Quotation Item", self.quotation_item_name)
        self.bom_code = self._qi_doc.get("al_bom")
        self.bom_version_name = self._qi_doc.get("al_bom_version")

        if self.bom_version_name:
            # get_cached_doc: snapshot docs are read-only, safe to cache
            self.bom_version = frappe.get_cached_doc(
                "AL BOM Version", self.bom_version_name)
        elif self.bom_code:
            self._bom_doc = frappe.get_cached_doc("AL BOM", self.bom_code)
            if self._bom_doc.current_version:
                self.bom_version = frappe.get_cached_doc(
                    "AL BOM Version", self._bom_doc.current_version)
                self.bom_version_name = self._bom_doc.current_version
            else:
                frappe.throw(
                    f"BOM '{self.bom_code}' chưa có version nào được Published")

    # ══════════════════════════════════════════════════════════════════
    # B1: Gather Inputs — đọc từ al_bom_vars JSON + resolve system vars
    # ══════════════════════════════════════════════════════════════════
    def b1_gather_inputs(self):
        # ── 1.1 Đọc user inputs từ al_bom_vars JSON (đã có trong _qi_doc) ──
        bom_vars_str = self._qi_doc.get("al_bom_vars")
        bom_vars = {}
        if bom_vars_str:
            try:
                bom_vars = json.loads(bom_vars_str) if isinstance(
                    bom_vars_str, str) else bom_vars_str
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

        # ── 1.3 Resolve system variables từ AL Variable Library ──────
        self._resolve_system_variables()

        # ── 1.4 Merge user input values (bom_vars ghi đè) ────────────
        for key in list(bom_vars.keys()):
            if key not in ("extra_vars", "accessory_set", "glass_master"):
                self.inputs[key] = bom_vars[key]

    def _resolve_system_variables(self):
        """DATA-DRIVEN: Đọc system variables từ AL Variable Library.

        Với mỗi system variable có source_doctype + source_field,
        tự động resolve giá trị. Thêm 1 system var mới = 1 record Library.
        """
        system_vars = frappe.get_all("AL Variable Library",
                                      filters={"is_system": 1},
                                      fields=["var_name", "source_doctype",
                                              "source_field", "default_value"])

        # Gom các var theo source_doctype để batch query
        by_doctype = defaultdict(list)
        for sv in system_vars:
            if sv.get("source_doctype") and sv.get("source_field"):
                by_doctype[sv["source_doctype"]].append(sv)

        # Cần biết tên record cụ thể để query
        bom_set = self._get_bom_set()
        if not bom_set:
            return

        # Map: doctype → record name
        source_records = {
            "AL Profile System": bom_set.get("profile_system"),
            "AL Product Type": bom_set.get("product_type"),
        }

        # Resolve từng source doctype
        for doctype, vars_list in by_doctype.items():
            record_name = source_records.get(doctype)
            if not record_name:
                continue
            try:
                doc = frappe.get_cached_doc(doctype, record_name)
                for sv in vars_list:
                    val = doc.get(sv["source_field"])
                    if val is not None:
                        self.inputs[sv["var_name"]] = val
            except frappe.DoesNotExistError:
                pass

        # Fallback: system vars không có source_doctype hoặc không resolve được
        # → dùng default_value từ Variable Library
        for sv in system_vars:
            if sv["var_name"] not in self.inputs and sv.get("default_value"):
                try:
                    self.inputs[sv["var_name"]] = float(sv["default_value"])
                except (ValueError, TypeError):
                    self.inputs[sv["var_name"]] = sv["default_value"]

        # Fallback cuối: AL Calculation Rule CONSTANT (cho backward compat)
        for sv in system_vars:
            if sv["var_name"] not in self.inputs or self.inputs[sv["var_name"]] in (0, ""):
                fallback_code = sv["var_name"].replace("_", "-")
                try:
                    rule = frappe.get_cached_doc(
                        "AL Calculation Rule", fallback_code)
                    if rule.rule_type == "CONSTANT":
                        self.inputs[sv["var_name"]] = rule.constant_value or 0
                except frappe.DoesNotExistError:
                    pass

    def _get_bom_set(self):
        """Lấy Bom Set doc (cached)."""
        if not self.bom_version or not self.bom_version.bom:
            return None
        if not self._bom_doc:
            try:
                self._bom_doc = frappe.get_cached_doc(
                    "AL BOM", self.bom_version.bom)
            except frappe.DoesNotExistError:
                return None
        if self._bom_doc.bom_set:
            try:
                return frappe.get_cached_doc("AL Bom Set", self._bom_doc.bom_set)
            except frappe.DoesNotExistError:
                pass
        return None

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

        # ── Gom tất cả codes để batch query ──────────────────────────
        item_codes = []
        price_base_items = []
        glass_master_codes = []
        rule_codes = []

        for item in self.bom_items:
            ic = item.get("item_code")
            if ic:
                item_codes.append(ic)
            pbi = item.get("price_base_item")
            if pbi:
                price_base_items.append(pbi)
            gm = item.get("default_glass_master")
            if gm:
                glass_master_codes.append(gm)
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_codes.append(item["item_rule"])

        # ── Batch query #1: Item weights ─────────────────────────────
        weights = {}
        if item_codes:
            for it in frappe.get_all("Item",
                                      filters={"name": ("in", item_codes)},
                                      fields=["name", "weight_per_unit"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)

        # ── Batch query #2: Item Prices ──────────────────────────────
        prices = {}
        all_price_items = list(set(item_codes + price_base_items))
        if all_price_items:
            for ip in frappe.get_all("Item Price",
                                      filters={"item_code": ("in", all_price_items),
                                               "price_list": "Standard Selling"},
                                      fields=["item_code", "price_list_rate"]):
                prices[ip["item_code"]] = ip["price_list_rate"]

        # ── Batch query #3: Glass Masters (B3 fix: 1 query thay vì N+1) ──
        glass_masters = {}
        if glass_master_codes:
            for gm in frappe.get_all("AL Glass Master",
                                      filters={"name": ("in", list(set(glass_master_codes)))},
                                      fields=["name", "total_thick_mm", "glass_type"]):
                glass_masters[gm["name"]] = {
                    "glass_thick": gm.get("total_thick_mm", 0),
                    "glass_type": gm.get("glass_type", ""),
                }

        # ── Batch query #4: Material Categories (scrap_pct) ─────────
        material_categories = {}
        cat_codes = list({item.get("category", "") for item in self.bom_items if item.get("category")})
        if cat_codes:
            for mc in frappe.get_all("AL Material Category",
                                      filters={"name": ("in", cat_codes)},
                                      fields=["name", "default_scrap_pct"]):
                material_categories[mc["name"]] = mc.get("default_scrap_pct", 0) or 0

        # ── Batch query #5: Dynamic Item Rules (cached) ─────────────
        resolved_items = {}
        resolved_item_names = {}
        for rule_code in set(rule_codes):
            rule_input = self._resolve_rule_input_for_code(rule_code)
            if rule_input is not None and rule_input != "":
                resolved = self._resolve_dynamic_item(rule_code, rule_input)
                if resolved:
                    resolved_items[rule_code] = resolved
                    resolved_item_names[resolved] = True

        # ── Batch query #5: Resolved Item weights + prices ───────────
        if resolved_item_names:
            for it in frappe.get_all("Item",
                                      filters={"name": ("in", list(resolved_item_names))},
                                      fields=["name", "weight_per_unit"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)
            for ip in frappe.get_all("Item Price",
                                      filters={"item_code": ("in", list(resolved_item_names)),
                                               "price_list": "Standard Selling"},
                                      fields=["item_code", "price_list_rate"]):
                prices[ip["item_code"]] = ip["price_list_rate"]

        # ── Build row_literals ───────────────────────────────────────
        for item in self.bom_items:
            slug = item.get("slug", "")
            ic = item.get("item_code", "")
            pbi = item.get("price_base_item", "")

            lit = {
                "weight_per_unit": weights.get(ic, 0) if ic else 0,
                "unit_price": (prices.get(pbi, 0) if pbi
                               else (prices.get(ic, 0) if ic else 0)),
                "calc_pattern": item.get("calc_pattern", ""),
                "glass_thick": 0,
                "glass_type": "",
                "item_code": ic,
                "scrap_pct": material_categories.get(
                    item.get("category", ""), 0),
            }

            # Glass Master lookup (từ batch query)
            gm_code = item.get("default_glass_master", "")
            if gm_code and gm_code in glass_masters:
                lit["glass_thick"] = glass_masters[gm_code]["glass_thick"]
                lit["glass_type"] = glass_masters[gm_code]["glass_type"]

            # Dynamic Item Rule resolution
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_code = item["item_rule"]
                resolved = resolved_items.get(rule_code)
                if resolved:
                    lit["item_code"] = resolved
                    lit["unit_price"] = prices.get(resolved, 0)
                    lit["weight_per_unit"] = weights.get(resolved, 0)

            self.row_literals[slug] = lit

        # ── Lưu formula_fieldnames từ Bom Set config ─────────────────
        bom_set = self._get_bom_set()
        if bom_set and bom_set.get("formula_fieldnames"):
            try:
                self._formula_fieldnames = json.loads(
                    bom_set.formula_fieldnames) if isinstance(
                    bom_set.formula_fieldnames, str
                ) else bom_set.formula_fieldnames
            except json.JSONDecodeError:
                self._formula_fieldnames = None

    def _resolve_rule_input_for_code(self, rule_code):
        """Tìm rule_input phù hợp cho rule_code từ Bom Items."""
        for item in self.bom_items:
            if item.get("item_rule") == rule_code:
                expr = item.get("rule_input_expr", "")
                ref_match = re.match(
                    r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
                if ref_match:
                    ref_slug, ref_field = ref_match.group(
                        1), ref_match.group(2)
                    ref_lit = self.row_literals.get(ref_slug, {})
                    return ref_lit.get(ref_field, 0)
        return None

    def _resolve_rule_input(self, item, lit):
        """Phân giải rule_input_expr: 'items.kinh_tren.glass_thick' → giá trị."""
        expr = item.get("rule_input_expr", "")
        ref_match = re.match(
            r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
        if ref_match:
            ref_slug, ref_field = ref_match.group(1), ref_match.group(2)
            ref_lit = self.row_literals.get(ref_slug, {})
            return ref_lit.get(ref_field, 0)
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

        Dùng formula_fieldnames từ Bom Set config (data-driven),
        fallback DEFAULT_FORMULA_FIELDS nếu không có config.
        """
        self.bom_formulas = []
        formula_fields = self._formula_fieldnames or DEFAULT_FORMULA_FIELDS

        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            # Inject literals vào context (bao gồm scrap_pct từ Material Category)
            for key in ("weight_per_unit", "unit_price", "calc_pattern",
                         "glass_thick", "glass_type", "scrap_pct"):
                if key in lit:
                    self.inputs[f"{slug}__{key}"] = lit[key]

            # Pre-set defaults cho các field (tránh NameError trong engine)
            for field in ("width", "height", "qty", "calc_pattern",
                          "weight_per_unit", "unit_price", "scrap_pct"):
                if f"{slug}__{field}" not in self.inputs:
                    self.inputs[f"{slug}__{field}"] = (
                        "" if field == "calc_pattern" else 0)

            # Build formulas từ Bom Item fields (DATA-DRIVEN)
            for field in formula_fields:
                expr = item.get(field)
                if expr and str(expr).strip():
                    normalized = re.sub(
                        r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', str(expr))
                    self.bom_formulas.append({
                        "name": f"{slug}__{field}",
                        "formula": normalized,
                    })

            # Synthetic formulas (luôn được tạo)
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
    # B4: Calculate Bom Items — dùng FormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b4_calculate_bom_items(self):
        from formula_builder.formula_utils.engine_public import FormulaEngine
        from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import lookup_calc_pattern

        # ── lookup_rule: tra cứu AL Calculation Rule từ formula ─────
        # Cho phép formula như: lookup_rule("RULE-BANLE-QTY", H_mm) * n_panel
        def _lookup_rule(rule_code, input_value=None):
            """Tra cứu AL Calculation Rule. Hỗ trợ CONSTANT, THRESHOLD, LOOKUP."""
            try:
                rule = frappe.get_cached_doc("AL Calculation Rule", rule_code)
                result = rule.resolve(input_value)
                return result if result is not None else 0
            except frappe.DoesNotExistError:
                return 0

        engine = FormulaEngine(
            formulas=self.bom_formulas,
            safe_funcs={
                "lookup_calc_pattern": lookup_calc_pattern,
                "lookup_rule": _lookup_rule,
                "roundup": lambda x, y: math.ceil(x),
            },
            on_error="raise",
            deterministic=True,
        )

        result = engine.calculate(dict(self.inputs))
        self.inputs.update(result)

        # Build bom_result
        self.bom_result = []
        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            self.bom_result.append({
                "slug": slug,
                "item_code": lit.get("item_code", item.get("item_code", "")),
                "width": result.get(f"{slug}__width", 0),
                "height": result.get(f"{slug}__height", 0),
                "qty": result.get(f"{slug}__qty", 0),
                "unit_qty": result.get(f"{slug}__unit_qty", 0),
                "total_qty": result.get(f"{slug}__total_qty", 0),
                "unit_price": lit.get("unit_price", 0),
                "line_total": result.get(f"{slug}__line_total", 0),
                "cost_bucket": item.get("cost_bucket", ""),
            })

    # ══════════════════════════════════════════════════════════════════
    # B5: Aggregate Cost Buckets — gom line_total theo cost_bucket
    # ══════════════════════════════════════════════════════════════════
    def b5_aggregate_cost_buckets(self):
        """Gom line_total theo cost_bucket (đọc từ Bom Item, không hardcode)."""
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
        if not self.bom_version or not self.bom_version.cost_template_snapshot:
            return

        from formula_builder.flexible_formula_engine import (
            FlexibleFormulaEngine, EngineConfig)

        snap = json.loads(self.bom_version.cost_template_snapshot) if isinstance(
            self.bom_version.cost_template_snapshot, str
        ) else self.bom_version.cost_template_snapshot

        # Build global_formulas từ Cost Template
        global_formulas = []
        referenced_codes = set()
        for item in snap.get("items", []):
            if item.get("calc_formula", "").strip():
                global_formulas.append({
                    "name": item["line_code"],
                    "formula": item["calc_formula"],
                })
                # B4 fix: Parse formula để tìm bucket codes được reference
                tokens = re.findall(
                    r'\b([A-Z][A-Z0-9_]{1,30})\b', item["calc_formula"])
                referenced_codes.update(t for t in tokens if not t.startswith(
                    ("TONG_", "GIA_", "PROFIT", "VAT", "DON_GIA")))

        # Build extra_context: bucket values + global vars
        extra_context = dict(self.inputs)
        extra_context.update(self.buckets)

        # B4 fix: Chỉ set default 0 cho bucket codes được reference
        # (không load toàn bộ bảng AL Cost Bucket)
        for code in referenced_codes:
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

        values = result.values if hasattr(result, 'values') else dict(result)
        self.cost_result = dict(values)
        self.gia_vat = self.cost_result.get("GIA_VAT", 0)

    # ══════════════════════════════════════════════════════════════════
    # B7: Save Results — SINGLE commit (B1 fix)
    # ══════════════════════════════════════════════════════════════════
    def b7_save_results(self):
        # Ghi TOÀN BỘ kết quả vào JSON (linh hoạt, mọi bucket đều lưu được)
        full_result = {
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            "lines": self.bom_result,
            "gia_vat": self.gia_vat,
        }
        result_json = json.dumps(full_result, indent=2, default=str)

        # Tạo ConfigSnapshot qua Frappe ORM (không raw SQL)
        snap_doc = frappe.new_doc("ConfigSnapshot")
        snap_doc.bom_version = self.bom_version_name
        snap_doc.quotation_item_name = self.quotation_item_name
        snap_doc.calculation_timestamp = frappe.utils.now()
        snap_doc.inputs_json = json.dumps(self.inputs, indent=2, default=str)
        snap_doc.result_json = result_json
        snap_doc.insert(ignore_permissions=True)
        snap_name = snap_doc.name

        # Ghi tất cả vào Quotation Item (1 lần set_value gộp multi-field)
        frappe.db.set_value("Quotation Item", self.quotation_item_name, {
            "al_gia_vat": self.gia_vat,
            "al_gia_ban": self.cost_result.get("GIA_BAN", 0),
            "al_bom_result": result_json,
            "al_config_snapshot": snap_name,
        })

        # B1 fix: 1 commit duy nhất
        frappe.db.commit()

    # ── Response builder — trả về TOÀN BỘ cost_result ────────────────
    def _build_response(self):
        """Trả về toàn bộ kết quả. Client tự chọn key cần hiển thị."""
        return {
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            "lines": self.bom_result,
        }
