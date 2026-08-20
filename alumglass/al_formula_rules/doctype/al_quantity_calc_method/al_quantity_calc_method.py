"""AL Quantity Calc Method — DocType + thin re-export (HYBRID).

🆕 v28.8: Logic `lookup_calc_pattern` HYBRID (DB-first + PATTERN_FORMULAS fallback)
chuyển sang `alumglass.formula_handlers`. Module này re-export để giữ NGUYÊN module
path — `bom_orchestrator.py` (B4 dòng 814 / B6 dòng 989) import từ đây, không đổi.

Backward-compat:
- `_compile_calc_fn`, `_calc_fn_cache` vẫn expose (test_safe_eval_a3 thao tác trực tiếp).
  `_calc_fn_cache` là ALIAS trỏ cùng dict `_DB_PATTERN_CACHE` → gán/clear qua tên cũ
  tác động đúng cache thật của lookup.
- `_CALC_ALLOWED_FUNCTIONS`, `PATTERN_FORMULAS` re-export cho ai cần.
"""
import frappe
from frappe.model.document import Document

from formula_builder.security.safe_eval import compile_expression  # noqa: F401  (backward-compat)

from alumglass.formula_handlers import (
    PATTERN_FORMULAS,                      # noqa: F401
    _DB_PATTERN_CACHE,
    _NEGATIVE_CACHE,
    _CALC_ALLOWED_FUNCTIONS,               # noqa: F401  (backward-compat)
    _compile_calc_fn,                      # noqa: F401  (test_safe_eval_a3 dùng qcm._compile_calc_fn)
    _validate_calc_fn,
    clear_calc_fn_cache,
    get_available_patterns,
    lookup_calc_pattern,
)

# Backward-compat: test_safe_eval_a3 gán/clear qua qcm._calc_fn_cache.
# Alias cùng dict → lookup_calc_pattern đọc đúng cache positive thật (_DB_PATTERN_CACHE).
_calc_fn_cache = _DB_PATTERN_CACHE


class ALQuantityCalcMethod(Document):
    """Pattern tính số lượng đơn vị - DATA-DRIVEN từ DB + fallback code (HYBRID)."""

    def validate(self):
        # Phase 2 (v28.8): calc_fn KHÔNG bắt buộc — empty = fallback PATTERN_FORMULAS.
        if self.calc_fn and self.calc_fn.strip():
            _validate_calc_fn(self.calc_fn)
        # Phase 3 (v28.8): chặn đổi calc_fn khi không đủ role.
        # Field-level permission không có trong Frappe core → validate hook là chuẩn.
        if not self.is_new():
            old = frappe.db.get_value(self.doctype, self.name, "calc_fn")
            if old != self.get("calc_fn") and not (
                "AL Technical Admin" in frappe.get_roles()
                or "System Manager" in frappe.get_roles()
            ):
                frappe.throw(
                    "Chỉ AL Technical Admin hoặc System Manager được thay đổi calc_fn."
                )
