import frappe, re
from frappe.model.document import Document

from formula_builder.security.safe_eval import compile_expression


def _is_number(v):
    """Kiểm tra chuỗi có phải số thực — để coerce input giữ hành vi cũ.

    Input từ client có thể là chuỗi số (vd "1000.5"). Coerce về float để
    tránh "A + B" nối chuỗi thay vì cộng số.
    """
    if not isinstance(v, str):
        return False
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


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
    # Coerce chuỗi số → float để giữ hành vi cũ (tránh "A+B" nối chuỗi khi input là str)
    ctx = {
        k: (float(v) if _is_number(v) else v)
        for k, v in dict(inputs).items()
    }
    results = {}
    for item in template.items:
        try:
            # Bỏ string-substitution — cho ctx trực tiếp làm scope.
            # compile_expression chặn import/lambda/dunder/getattr/... → chặn RCE.
            expr = compile_expression(item.calc_formula or "0")
            val = expr.eval(ctx)
            ctx[item.line_code] = val
            results[item.line_code] = {"formula": item.calc_formula, "result": val, "is_subtotal": item.is_subtotal}
        except Exception as e:
            results[item.line_code] = {"formula": item.calc_formula, "error": str(e)}
    return results
