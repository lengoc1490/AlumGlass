import frappe
from frappe.model.document import Document

from formula_builder.formula_utils import BASE_FUNCS, FormulaValidator
from formula_builder.security.safe_eval import compile_expression

# Hàm custom alumglass dùng trong Cost Template — B6 inject qua
# FlexibleFormulaEngine.custom_functions. Phải nằm trong whitelist để
# FormulaValidator không bắt nhầm là "hàm không được hỗ trợ".
_ALUMGLASS_CUSTOM_FUNCS = frozenset({"lookup_rule", "lookup_calc_pattern", "roundup"})
_VALIDATOR_ALLOWED_FUNCS = frozenset(set(BASE_FUNCS.keys()) | _ALUMGLASS_CUSTOM_FUNCS)


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
        # Universe biến động = nguồn runtime thật (Cost Bucket, System/User Vars,
        # Formula Global Vars, Common Vars, FVB...) — build 1 lần trước loop.
        known_names = self._build_known_names()
        validator = FormulaValidator(allowed_functions=_VALIDATOR_ALLOWED_FUNCS)
        defined_vars = set()
        warnings = []
        for item in self.items:
            formula = (item.calc_formula or "").strip()
            if not formula:
                frappe.throw(f"Dòng '{item.line_code}': Công thức không được trống")
            if formula.count("(") != formula.count(")"):
                frappe.throw(f"Dòng '{item.line_code}': Dấu ngoặc không cân bằng")
            # AST-based validator: bắt biến chưa khai báo (kể cả lowercase), hàm
            # không whitelist, string literal không bị tách nhầm thành Name.
            result = validator.validate(formula, known_names=known_names | defined_vars)
            if result.errors:
                warnings.append(
                    f"Dòng '{item.line_code}': {'; '.join(result.errors)}"
                )
            defined_vars.add(item.line_code)
        if warnings:
            frappe.msgprint(
                "\n".join(warnings),
                title="AL Cost Template — Cảnh báo công thức",
                indicator="orange",
            )

    def _build_known_names(self):
        """Xây universe biến động cho validator — đúng nguồn runtime.

        Tái sử dụng get_formula_context (cùng nguồn với autocomplete form) để lấy
        toàn bộ biến engine inject: Cost Bucket, System/User Vars, Formula Global
        Vars, Row Literals, Common Vars, FVB bindings — dedup đã xử lý bên trong.
        Không hardcode biến nào. Nếu nguồn lỗi → log + trả set rỗng (validate vẫn
        chạy được phần cú pháp/hàm, không chặn save chỉ vì infra).
        """
        try:
            from alumglass.api import get_formula_context
            ctx = get_formula_context("AL Cost Template", None)
            return {
                v["name"] for v in (ctx.get("variables") or []) if v.get("name")
            }
        except Exception as exc:
            frappe.log_error(
                f"AL Cost Template validate: lỗi build known_names — {exc}",
                "AL Cost Template Validate",
            )
            return set()


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
