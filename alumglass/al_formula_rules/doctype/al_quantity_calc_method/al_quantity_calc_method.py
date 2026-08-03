import frappe
from frappe.model.document import Document


class ALQuantityCalcMethod(Document):
    """Pattern tính số lượng đơn vị - DATA-DRIVEN từ DB."""

    def validate(self):
        if not self.calc_fn or not self.calc_fn.strip():
            frappe.throw("calc_fn (Python lambda) là bắt buộc")


# ============================================================
# DATA-DRIVEN DISPATCH — đọc calc_fn từ DB record
# ============================================================

_calc_fn_cache = {}

def _get_calc_fn(calc_pattern_code):
    """Lấy lambda từ DB record AL Quantity Calc Method, có cache."""
    if calc_pattern_code not in _calc_fn_cache:
        fn_str = frappe.db.get_value(
            "AL Quantity Calc Method", calc_pattern_code, "calc_fn")
        if not fn_str:
            frappe.throw(
                f"AL Quantity Calc Method '{calc_pattern_code}' không tồn tại "
                f"hoặc không có calc_fn"
            )
        # Restricted namespace: chỉ cho phép pure math
        import math
        safe_ns = {
            "__builtins__": {},
            "abs": abs, "min": min, "max": max, "round": round,
            "math": math,
        }
        _calc_fn_cache[calc_pattern_code] = eval(fn_str, safe_ns)
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
    fn = _get_calc_fn(calc_pattern_code)
    return fn(w=width, h=height, tlr=weight_per_unit, **extra_vars)


def clear_calc_fn_cache():
    """Xóa cache — gọi khi AL Quantity Calc Method được cập nhật."""
    _calc_fn_cache.clear()
