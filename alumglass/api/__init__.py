import frappe


@frappe.whitelist()
def calculate_bom(quotation_item_name):
    """Tính BOM cho 1 dòng báo giá - trả về GIA_VAT + chi tiết.

    Đây là API chính được gọi từ nút "Tính giá" trên Quotation Item.
    """
    from alumglass.engine.bom_orchestrator import BomOrchestrator

    orch = BomOrchestrator(quotation_item_name)
    return orch.run()


@frappe.whitelist()
def preview_cost_template(template_code, inputs_json):
    """Xem trước kết quả Cost Template với inputs giả định."""
    from alumglass.al_bom_engine.doctype.al_cost_template.al_cost_template import preview_cost_template as _preview
    return _preview(template_code, inputs_json)


@frappe.whitelist()
def get_slug_info(slug):
    """Lấy thông tin Slug Library."""
    from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import get_slug_info as _get
    return _get(slug)


@frappe.whitelist()
def resolve_item_rule(rule_code, input_value):
    """Tra cứu Item từ Dynamic Item Rule."""
    from alumglass.al_formula_rules.doctype.al_dynamic_item_rule.al_dynamic_item_rule import resolve_item
    return resolve_item(rule_code, input_value)


@frappe.whitelist()
def get_bom_structure(bom_code):
    """Lấy toàn bộ cấu trúc BOM."""
    from alumglass.al_bom_engine.doctype.al_bom.al_bom import get_bom_structure as _get
    return _get(bom_code)


@frappe.whitelist()
def get_cost_template_context(template_code=None):
    """Lấy context variables cho AL Cost Template formula autocomplete.

    Trả về danh sách các biến có thể dùng trong công thức calc_formula:
    - Cost Bucket codes (VL_NHOM, VL_KINH, TONG_VL, GIA_VAT...)
    - System variables từ AL Variable Library (NC_SX_PCT, VAT_RATE...)
    - Global variables từ Formula Builder (PROFIT_MARGIN, OH_VC_PCT...)
    - Biến từ Bom Items (W_mm, H_mm, n_panel...)
    """
    variables = []

    # ── 1. Cost Bucket codes ──────────────────────────────────────────
    buckets = frappe.get_all("AL Cost Bucket",
                             fields=["bucket_code", "bucket_name", "bucket_role"],
                             order_by="sort_order")
    for b in buckets:
        variables.append({
            "name": b["bucket_code"],
            "label": b.get("bucket_name") or b["bucket_code"],
            "value": None,
            "type": "Float",
            "source": "bucket",
            "source_type": "cost_bucket",
            "description": f"Cost Bucket ({b.get('bucket_role', '')})",
        })

    # ── 2. System variables từ AL Variable Library ───────────────────
    sys_vars = frappe.get_all("AL Variable Library",
                              filters={"is_system": 1},
                              fields=["var_name", "var_label", "default_value"])
    for sv in sys_vars:
        variables.append({
            "name": sv["var_name"],
            "label": sv.get("var_label") or sv["var_name"],
            "value": sv.get("default_value"),
            "type": "Float",
            "source": "system",
            "source_type": "variable_library",
            "description": "System Variable",
        })

    # ── 3. Global variables từ Formula Builder ───────────────────────
    for gv in frappe.get_all("Formula Global Variable",
                             fields=["var_name", "constant_value"]):
        variables.append({
            "name": gv["var_name"],
            "label": gv["var_name"],
            "value": gv.get("constant_value"),
            "type": "Float",
            "source": "global",
            "source_type": "formula_global_var",
            "description": "Formula Global Variable",
        })

    # ── 4. Biến thường dùng từ Bom Items ─────────────────────────────
    common_vars = [
        {"name": "W_mm", "label": "Width (mm)", "description": "Chiều rộng cửa"},
        {"name": "H_mm", "label": "Height (mm)", "description": "Chiều cao cửa"},
        {"name": "n_panel", "label": "Số cánh", "description": "Số lượng cánh"},
        {"name": "TONG_M2", "label": "Tổng m²", "description": "Tổng diện tích"},
    ]
    for cv in common_vars:
        variables.append({
            "name": cv["name"],
            "label": cv["label"],
            "value": None,
            "type": "Float",
            "source": "bom",
            "source_type": "common_var",
            "description": cv.get("description", ""),
        })

    return {
        "variables": variables,
        "references": [
            {"name": f"items.{{slug}}.{{field}}", "label": "Cross-row ref", "doctype": "AL Bom Item"},
        ],
    }


@frappe.whitelist()
def get_variable_set_for_bom(bom_code):
    """Lấy danh sách biến từ Variable Set của BOM.

    Flow: BOM → Bom Set → Variable Set → Variable Set Items + System vars từ Library.
    Trả về list biến để JS dialog tự sinh form fields.
    """
    if not bom_code:
        return {"variables": []}

    bom = frappe.get_cached_doc("AL BOM", bom_code)
    if not bom.bom_set:
        return {"variables": []}

    bom_set = frappe.get_cached_doc("AL Bom Set", bom.bom_set)
    set_code = bom_set.set_code
    set_name = bom_set.set_name

    variables = []

    # ── 1. User variables từ Variable Set ─────────────────────────
    if bom_set.get("variable_set"):
        vs = frappe.get_cached_doc("AL Variable Set", bom_set.variable_set)
        set_code = vs.set_code
        set_name = vs.set_name
        for item in vs.items:
            var_name = item.variable if hasattr(item, 'variable') else item.var_name
            var_label = item.var_label or var_name
            var_type = item.var_type or "Data"
            link_doctype = item.link_doctype or ""
            select_options = item.select_options or ""

            variables.append({
                "var_name": var_name,
                "var_label": var_label,
                "var_type": var_type,
                "link_doctype": link_doctype,
                "select_options": select_options,
                "default_value": item.default_value or "",
                "is_required": item.is_required or 0,
                "sort_order": item.sort_order or 0,
            })

    # ── 2. System variables từ AL Variable Library (DATA-DRIVEN) ──
    for sv in frappe.get_all("AL Variable Library",
                              filters={"is_system": 1},
                              fields=["var_name", "var_label", "var_type",
                                      "default_value", "description"]):
        variables.append({
            "var_name": sv["var_name"],
            "var_label": sv.get("var_label") or sv["var_name"],
            "var_type": sv.get("var_type") or "Float",
            "link_doctype": "",
            "select_options": "",
            "default_value": sv.get("default_value") or "",
            "is_required": 0,
            "sort_order": 999,
            "is_system": True,
        })

    return {
        "variable_set_code": set_code,
        "variable_set_name": set_name,
        "variables": sorted(variables, key=lambda v: (
            v.get("is_system", False), v.get("sort_order", 0))),
    }
