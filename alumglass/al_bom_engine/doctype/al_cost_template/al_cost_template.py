import frappe, re
from frappe.model.document import Document


class ALCostTemplate(Document):
    """Master công thức tính giá thành từ Cost Buckets. 14 dòng chuẩn từ TONG_VL -> GIA_VAT."""

    def validate(self):
        if not self.items:
            return
        defined_vars = set()
        for item in self.items:
            formula = (item.calc_formula or "").strip()
            if not formula:
                frappe.throw(f"Dòng '{item.line_code}': Công thức không được trống")
            if formula.count("(") != formula.count(")"):
                frappe.throw(f"Dòng '{item.line_code}': Dấu ngoặc không cân bằng")
            # Kiểm tra tham chiếu biến chưa định nghĩa
            refs = set(re.findall(r'\b([A-Z_][A-Z0-9_]*)\b', formula))
            unknown = refs - defined_vars - {"W_mm", "H_mm", "TransomHeight_mm", "n_panel"}
            if unknown:
                frappe.msgprint(
                    f"Dòng '{item.line_code}' tham chiếu biến chưa định nghĩa: "
                    f"{', '.join(sorted(unknown))}"
                )
            defined_vars.add(item.line_code)


@frappe.whitelist()
def preview_cost_template(template_code, inputs_json):
    """Xem trước kết quả Cost Template với inputs giả định."""
    import json as _json
    inputs = _json.loads(inputs_json) if isinstance(inputs_json, str) else inputs_json
    template = frappe.get_doc("AL Cost Template", template_code)
    ctx = dict(inputs)
    results = {}
    for item in template.items:
        expr = item.calc_formula or ""
        for var_name in sorted(ctx.keys(), key=len, reverse=True):
            expr = expr.replace(var_name, str(ctx[var_name]))
        try:
            val = eval(expr, {"__builtins__": {}}, {})
            ctx[item.line_code] = val
            results[item.line_code] = {"formula": item.calc_formula, "result": val, "is_subtotal": item.is_subtotal}
        except Exception as e:
            results[item.line_code] = {"formula": item.calc_formula, "error": str(e)}
    return results
