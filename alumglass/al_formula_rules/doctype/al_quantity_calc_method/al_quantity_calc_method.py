import ast

import frappe
from frappe.model.document import Document

from formula_builder.security.safe_eval import compile_expression


class ALQuantityCalcMethod(Document):
    """Pattern tính số lượng đơn vị - DATA-DRIVEN từ DB."""

    def validate(self):
        if not self.calc_fn or not self.calc_fn.strip():
            frappe.throw("calc_fn (Python lambda) là bắt buộc")


# ============================================================
# DATA-DRIVEN DISPATCH — đọc calc_fn từ DB record
# ============================================================

_calc_fn_cache = {}

# Hàm được phép gọi trong body calc_fn (backward-compat với namespace cũ).
_CALC_ALLOWED_FUNCTIONS = ("abs", "min", "max", "round")


def _compile_calc_fn(fn_str):
    """Compile calc_fn (chuỗi lambda từ DB) → SafeExpression của FB safe_eval.

    Giữ backward-compat: calc_fn trong DB vẫn là chuỗi lambda
    ("lambda w,h,tlr,**kw: ..."). Parse AST → lấy body expression → compile
    an toàn (FB chặn Lambda node → không truyền thẳng chuỗi lambda vào
    compile_expression).

    Raises:
        ValueError: nếu calc_fn không phải lambda hoặc body chứa cấu trúc
        không cho phép (import / lambda lồng / dunder attr / getattr / ...).
    """
    fn_str = (fn_str or "").strip()
    if not fn_str:
        raise ValueError("calc_fn rỗng")
    try:
        tree = ast.parse(fn_str, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"calc_fn không phải biểu thức hợp lệ: {e.msg}") from e
    if not isinstance(tree.body, ast.Lambda):
        raise ValueError(
            f"calc_fn phải là lambda, nhận: {type(tree.body).__name__}"
        )
    body_source = ast.unparse(tree.body.body)
    return compile_expression(body_source, allowed_functions=_CALC_ALLOWED_FUNCTIONS)


def _get_calc_fn(calc_pattern_code):
    """Lấy SafeExpression từ DB record AL Quantity Calc Method, có cache."""
    if calc_pattern_code not in _calc_fn_cache:
        fn_str = frappe.db.get_value(
            "AL Quantity Calc Method", calc_pattern_code, "calc_fn")
        if not fn_str:
            frappe.throw(
                f"AL Quantity Calc Method '{calc_pattern_code}' không tồn tại "
                f"hoặc không có calc_fn"
            )
        try:
            _calc_fn_cache[calc_pattern_code] = _compile_calc_fn(fn_str)
        except (ValueError, SyntaxError) as e:
            frappe.throw(
                f"AL Quantity Calc Method '{calc_pattern_code}' calc_fn không "
                f"hợp lệ: {e}"
            )
    return _calc_fn_cache[calc_pattern_code]


def lookup_calc_pattern(calc_pattern_code, width=None, height=None,
                         weight_per_unit=None, **extra_vars):
    """DATA-DRIVEN: Dispatch quantity calculation từ DB.

    Đọc calc_fn lambda từ AL Quantity Calc Method record.
    Không còn if/elif hardcode — thêm pattern mới = 1 DB record.

    Args:
        calc_pattern_code: pattern code (vd: LENGTH_TO_WEIGHT, AREA)
        width: mm
        height: mm
        weight_per_unit: kg/m (cho LENGTH_TO_WEIGHT)
        **extra_vars: tham số mở rộng (vd: thickness cho VOLUME)
    """
    expr = _get_calc_fn(calc_pattern_code)
    # Chỉ expose đúng biến + hàm seed data cần (w/h/tlr + abs/min/max/round).
    scope = {
        "w": width,
        "h": height,
        "tlr": weight_per_unit,
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
    }
    scope.update(extra_vars)  # tương đương **kw của lambda cũ
    return expr.eval(scope)


def clear_calc_fn_cache():
    """Xóa cache — gọi khi AL Quantity Calc Method được cập nhật."""
    _calc_fn_cache.clear()
