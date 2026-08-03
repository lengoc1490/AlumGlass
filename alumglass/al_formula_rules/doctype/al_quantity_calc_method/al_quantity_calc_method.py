import frappe
from frappe.model.document import Document


class ALQuantityCalcMethod(Document):
    """Pattern tính số lượng đơn vị - DATA-DRIVEN từ DB."""

    def validate(self):
        if not self.calc_fn or not self.calc_fn.strip():
            frappe.throw("calc_fn (Python lambda) là bắt buộc")


# ============================================================
# DISPATCH TABLE - Python thuần, KHÔNG gọi ngược Formula Engine
# ============================================================

def lookup_calc_pattern(calc_pattern_code, width=None, height=None,
                         weight_per_unit=None, **extra_vars):
    """Dispatch table Python thuần cho quantity calculation.

    QUAN TRỌNG: Hàm này KHÔNG được gọi ngược Formula Engine.
    Nó là pure Python arithmetic, không DAG, không DB query.

    Args:
        calc_pattern_code: LENGTH_TO_WEIGHT | AREA | LENGTH_ONLY | COUNT | VOLUME
        width: mm
        height: mm
        weight_per_unit: kg/m (cho LENGTH_TO_WEIGHT)
        **extra_vars: tham số mở rộng (vd: thickness cho VOLUME)
    """
    w = (width or 0) / 1000.0   # mm → m
    h = (height or 0) / 1000.0  # mm → m
    tlr = weight_per_unit or 0

    if calc_pattern_code == "LENGTH_TO_WEIGHT":
        return w * tlr
    if calc_pattern_code == "AREA":
        return w * h
    if calc_pattern_code == "LENGTH_ONLY":
        return w
    if calc_pattern_code == "COUNT":
        return 1.0
    if calc_pattern_code == "VOLUME":
        t = extra_vars.get("thickness", 0) / 1000.0
        return w * h * t

    frappe.throw(f"Calc pattern '{calc_pattern_code}' không được hỗ trợ")
