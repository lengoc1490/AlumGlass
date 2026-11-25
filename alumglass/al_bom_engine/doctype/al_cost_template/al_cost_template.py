import frappe
from frappe.model.document import Document

from formula_builder.formula_utils import BASE_FUNCS, FormulaValidator
from formula_builder.security.safe_eval import compile_expression

from alumglass.al_bom_engine.formula_validate import (
    load_rule_meta, lookup_rule_codes, validate_lookup_rule_codes)

# Hàm custom alumglass dùng trong Cost Template — B6 inject qua
# FormulaEngine (`safe_funcs=`; trước bản vá: EngineConfig.custom_functions
# của FlexibleFormulaEngine). Phải nằm trong whitelist để
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
        # Mã quy tắc literal trong các công thức — đọc metadata 1 query cho cả
        # template (⛔ N+1 theo dòng). `None` = không đọc được ⇒ bỏ qua phép
        # kiểm này, ⛔ cảnh báo "mã không tồn tại" oan.
        lookup_codes = []
        for item in self.items:
            lookup_codes.extend(lookup_rule_codes(item.calc_formula))
        rule_meta = load_rule_meta(lookup_codes)
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
            if rule_meta is not None:
                for code_warning in validate_lookup_rule_codes(
                        formula, "NUMBER", rule_meta=rule_meta):
                    warnings.append(f"Dòng '{item.line_code}': {code_warning}")
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

        `docname` = tên template đang validate để catalog đọc được field
        `variable_profile` CỦA CHÍNH record (doc mới chưa lưu → self.name rỗng
        → truyền None như cũ). `fieldname="calc_formula"` để profile lọc
        `only_fields` đúng field đang kiểm.

        ⚠ `include_all_sources=True`: VALIDATE dùng universe biến ĐẦY ĐỦ
        (đường legacy như trước bản vá) — profile chỉ lọc GỢI Ý, không được
        làm hẹp universe hợp lệ (nếu không bật profile = cảnh báo oan).
        """
        try:
            from alumglass.api import get_formula_context
            ctx = get_formula_context(
                "AL Cost Template", self.name or None,
                fieldname="calc_formula", include_all_sources=True)
            return {
                v["name"] for v in (ctx.get("variables") or []) if v.get("name")
            }
        except Exception as exc:
            frappe.log_error(
                f"AL Cost Template validate: lỗi build known_names — {exc}",
                "AL Cost Template Validate",
            )
            return set()


def _preview_custom_functions():
    """Scope hàm cho preview = bộ hàm nền BASE_FUNCS + 3 hàm custom alumglass.

    F19: trước đây preview CHỈ inject 3 hàm custom (`lookup_rule` /
    `lookup_calc_pattern` / `roundup`), KHÔNG có bộ hàm nền của engine (vd
    `safe_div`) trong khi runtime B4/B6 CÓ — vì FormulaEngine (nay dùng cho
    CẢ B4 lẫn B6) luôn merge `BASE_FUNCS` rồi phủ `safe_funcs` lên (engine_core:
    `base = BASE_FUNCS.copy(); base.update(safe_funcs)`). Công thức dùng
    `safe_div(...)` (có trong seed, dòng DON_GIA_M2) ⇒ báo NameError ở preview
    nhưng tính thật vẫn chạy ⇒ người dùng tưởng công thức sai.

    F14: trước đây cũng lệch cùng kiểu với `lookup_rule`/`lookup_calc_pattern`/
    `roundup` — preview không inject chúng trong khi B6 CÓ.

    ⇒ Dựng scope hàm TỪ CHÍNH `BASE_FUNCS` rồi phủ 3 hàm custom lên (đúng thứ
    tự runtime: custom đè bộ nền — `roundup` của alumglass đè `roundup` của
    engine). Hàm nào runtime có thì preview có ⇒ không bao giờ lệch lại. Import
    trong hàm để tránh vòng import lúc nạp DocType.

    An toàn: mở rộng scope KHÔNG nới lỏng chốt chặn RCE — `compile_expression`
    vẫn chạy `_validate_ast` (chặn import/lambda/dunder/getattr/... và
    `__builtins__` rỗng); các hàm trong BASE_FUNCS đều là hàm an toàn của engine.
    """
    funcs = dict(BASE_FUNCS)
    from alumglass.engine.bom_orchestrator import _lookup_rule, _roundup
    from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import (
        lookup_calc_pattern,
    )
    funcs.update({
        "lookup_rule": _lookup_rule,
        "lookup_calc_pattern": lookup_calc_pattern,
        "roundup": _roundup,
    })
    return funcs


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
    # F14/F19: scope hàm = BASE_FUNCS + 3 hàm custom — ĐÚNG như runtime B6.
    ctx.update(_preview_custom_functions())
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
