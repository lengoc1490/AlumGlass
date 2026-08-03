"""BomOrchestrator — Engine tính BOM config-driven.

NGUYÊN TẮC: AlumGlass chỉ config, không hardcode nghiệp vụ.
Mọi logic đến từ DB: Bom Item, Cost Bucket, Cost Template, Profile System, Product Type.
Engine này chỉ làm nhiệm vụ: đọc config → resolve biến → tính toán → lưu kết quả.

Flow 7 phase:
  B0: Version pinning — chốt BOM Version
  B1: Gather inputs — đọc al_bom_vars + resolve scoped vars từ DB
  B2: Pre-fetch master data — batch query Item weights, prices, glass specs, rules
  B3: Build formulas — đọc formula fields từ Bom Item schema
  B4: Calculate Bom Items — dispatch calc_pattern + compute line_total
  B5: Aggregate cost buckets — gom theo cost_bucket assignment
  B6: Calculate Cost Template — đọc formulas từ Cost Template DB
  B7: Save results — ghi Quotation Item + ConfigSnapshot
"""
import frappe
import json
import re
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
    "al_gia_vat", "al_gia_ban", "al_tong_vl", "al_tong_nc",
    "al_vl_nhom", "al_vl_kinh", "al_vl_vtp", "al_vl_pk",
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
    # B3: Build Formulas — đọc formula fields từ Bom Item schema
    # ══════════════════════════════════════════════════════════════════
    def b3_build_formulas(self):
        """Resolve công thức: thay biến = giá trị, eval kết quả.

        Mỗi field trong BOM_ITEM_FORMULA_FIELDS được đọc từ Bom Item.
        Công thức dùng cú pháp: W_mm, OFFSET_FRAME, items.kinh_tren.width...
        """
        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            # Inject literal values vào context (để cross-row reference dùng được)
            for key in ("weight_per_unit", "unit_price", "calc_pattern",
                         "glass_thick", "glass_type"):
                if key in lit:
                    self.inputs[f"{slug}__{key}"] = lit[key]

            # Resolve từng formula field
            for field in BOM_ITEM_FORMULA_FIELDS:
                expr = item.get(field)
                if expr and str(expr).strip():
                    normalized = self._normalize_cross_ref(str(expr))
                    val = self._eval_expr(normalized, self.inputs)
                    self.inputs[f"{slug}__{field}"] = val
                elif field in ("width", "height", "qty"):
                    self.inputs[f"{slug}__{field}"] = 0

    def _normalize_cross_ref(self, expr):
        """Chuyển items.slug.field → slug__field."""
        return re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)

    def _eval_expr(self, expr, ctx):
        """Evaluate biểu thức số học đơn giản với context."""
        try:
            result = expr
            for var_name in sorted(ctx.keys(), key=len, reverse=True):
                result = result.replace(var_name, str(ctx[var_name]))
            return float(eval(result, {"__builtins__": {}, "roundup": lambda x, y: __import__("math").ceil(x)}, {}))
        except Exception:
            frappe.log_error(f"Eval failed: {expr}", "BomOrchestrator._eval_expr")
            return 0

    # ══════════════════════════════════════════════════════════════════
    # B4: Calculate Bom Items — dispatch calc_pattern
    # ══════════════════════════════════════════════════════════════════
    def b4_calculate_bom_items(self):
        from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import lookup_calc_pattern

        self.bom_result = []
        for item in self.bom_items:
            slug = item.get("slug", "")
            w = self.inputs.get(f"{slug}__width", 0)
            h = self.inputs.get(f"{slug}__height", 0)
            q = self.inputs.get(f"{slug}__qty", 0)
            lit = self.row_literals.get(slug, {})
            pattern = lit.get("calc_pattern", item.get("calc_pattern", ""))
            wpu = lit.get("weight_per_unit", 0)
            up = lit.get("unit_price", 0)

            unit_qty = lookup_calc_pattern(pattern, w, h, wpu)
            total_qty = unit_qty * q
            line_total = total_qty * up

            self.bom_result.append({
                "slug": slug,
                "item_code": lit.get("item_code", item.get("item_code", "")),
                "width": w, "height": h, "qty": q,
                "unit_qty": unit_qty, "total_qty": total_qty,
                "unit_price": up, "line_total": line_total,
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
    # B6: Calculate Cost Template — đọc formulas từ DB
    # ══════════════════════════════════════════════════════════════════
    def b6_calculate_cost_template(self):
        if not self.bom_version or not self.bom_version.cost_template_snapshot:
            return

        snap = json.loads(self.bom_version.cost_template_snapshot) if isinstance(
            self.bom_version.cost_template_snapshot, str
        ) else self.bom_version.cost_template_snapshot

        ctx = dict(self.inputs)
        ctx.update(self.buckets)

        for item in snap.get("items", []):
            formula = item.get("calc_formula", "")
            expr = formula
            for var_name in sorted(ctx.keys(), key=len, reverse=True):
                expr = expr.replace(var_name, str(ctx[var_name]))
            try:
                val = eval(expr, {"__builtins__": {}}, {})
                ctx[item["line_code"]] = val
                self.cost_result[item["line_code"]] = val
            except Exception:
                self.cost_result[item["line_code"]] = 0

        self.gia_vat = self.cost_result.get("GIA_VAT", 0)

    # ══════════════════════════════════════════════════════════════════
    # B7: Save Results — ghi Quotation Item + ConfigSnapshot
    # ══════════════════════════════════════════════════════════════════
    def b7_save_results(self):
        # Ghi kết quả tổng hợp (đọc field names từ OUTPUT_FIELDS config)
        output_values = {
            "al_gia_vat": self.gia_vat,
            "al_gia_ban": self.cost_result.get("GIA_BAN", 0),
            "al_tong_vl": self.cost_result.get("TONG_VL", 0),
            "al_tong_nc": self.cost_result.get("TONG_NC", 0),
        }
        # Map bucket codes → output fields theo convention
        bucket_field_map = {
            "VL_NHOM": "al_vl_nhom",
            "VL_KINH": "al_vl_kinh",
            "VL_VTP": "al_vl_vtp",
            "VL_PK": "al_vl_pk",
        }
        for bucket_code, fieldname in bucket_field_map.items():
            if bucket_code in self.buckets:
                output_values[fieldname] = self.buckets[bucket_code]

        for field, value in output_values.items():
            frappe.db.set_value("Quotation Item", self.quotation_item_name,
                                field, value)
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
             json.dumps({"bom_items": self.bom_result, "buckets": self.buckets,
                         "cost_template": self.cost_result, "gia_vat": self.gia_vat},
                        indent=2, default=str)))
        frappe.db.commit()

        frappe.db.set_value("Quotation Item", self.quotation_item_name,
                            "al_config_snapshot", snap_name)
        frappe.db.commit()

    # ══════════════════════════════════════════════════════════════════
    # Response builder
    # ══════════════════════════════════════════════════════════════════
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
