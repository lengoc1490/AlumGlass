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
def get_variable_set_for_bom(bom_code):
    """Lấy danh sách biến từ Variable Set của BOM.

    Flow: BOM → Bom Set → Variable Set → Variable Set Items
    Trả về list biến để JS dialog tự sinh form fields.
    """
    if not bom_code:
        return {"variables": []}

    bom = frappe.get_doc("AL BOM", bom_code)
    if not bom.bom_set:
        return {"variables": []}

    bom_set = frappe.get_doc("AL Bom Set", bom.bom_set)
    if not bom_set.get("variable_set"):
        return {"variables": []}

    vs = frappe.get_doc("AL Variable Set", bom_set.variable_set)
    variables = []
    for item in vs.items:
        # Lấy thông tin từ Variable Library (qua Link)
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

    # System variables (không hiển thị trong dialog, tự resolve từ DB)
    system_vars = [
        {"var_name": "OFFSET_FRAME", "var_label": "Offset Frame", "var_type": "Float", "is_system": True},
        {"var_name": "OFFSET_GLASS", "var_label": "Offset Glass", "var_type": "Float", "is_system": True},
        {"var_name": "OFFSET_FIXED", "var_label": "Offset Fixed", "var_type": "Float", "is_system": True},
        {"var_name": "OFFSET_DO_NGANG", "var_label": "Offset Crossbar", "var_type": "Float", "is_system": True},
        {"var_name": "NC_SX_PCT", "var_label": "NC SX %", "var_type": "Float", "is_system": True},
        {"var_name": "NC_LD_PCT", "var_label": "NC LD %", "var_type": "Float", "is_system": True},
        {"var_name": "PROFIT_MARGIN", "var_label": "Profit Margin", "var_type": "Float", "is_system": True},
        {"var_name": "VAT_RATE", "var_label": "VAT Rate", "var_type": "Float", "is_system": True},
        {"var_name": "OH_VC_PCT", "var_label": "OH VC %", "var_type": "Float", "is_system": True},
        {"var_name": "OH_QLY_PCT", "var_label": "OH QL %", "var_type": "Float", "is_system": True},
    ]
    variables.extend(system_vars)

    return {
        "variable_set_code": vs.set_code,
        "variable_set_name": vs.set_name,
        "variables": sorted(variables, key=lambda v: (v.get("is_system", False), v.get("sort_order", 0))),
    }
