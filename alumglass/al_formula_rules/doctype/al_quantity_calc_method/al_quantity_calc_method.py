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
from formula_builder.security.safe_eval import compile_expression
from frappe.model.document import Document

from alumglass.formula_handlers import (
    _CALC_ALLOWED_FUNCTIONS,
    _DB_PATTERN_CACHE,
    _NEGATIVE_CACHE,
    PATTERN_FORMULAS,
    _compile_calc_expr,
    _compile_calc_fn,
    _validate_calc_fn,
    clear_calc_fn_cache,
    get_available_patterns,
    lookup_calc_pattern,
)


def _validate_calc_expr_text(expr_text):
    """Validate `calc_expr` trước khi lưu — cùng bộ lọc safe_eval của Formula Builder.

    Khác `_validate_calc_fn`: đây là BIỂU THỨC (`(w/1000)*tlr`), ⛔ phải lambda.
    """
    try:
        _compile_calc_expr(expr_text)
    except ValueError as exc:
        frappe.throw(f"Công thức tính không hợp lệ: {exc}")

# Backward-compat: test_safe_eval_a3 gán/clear qua qcm._calc_fn_cache.
# Alias cùng dict → lookup_calc_pattern đọc đúng cache positive thật (_DB_PATTERN_CACHE).
_calc_fn_cache = _DB_PATTERN_CACHE


class ALQuantityCalcMethod(Document):
    """Pattern tính số lượng đơn vị - DATA-DRIVEN từ DB + fallback code (HYBRID)."""

    def validate(self):
        # B7/Đ5: `calc_expr` (cú pháp Formula Builder) là NGUỒN CHÍNH.
        has_expr = bool(self.calc_expr and self.calc_expr.strip())
        has_fn = bool(self.calc_fn and self.calc_fn.strip())
        if has_expr:
            _validate_calc_expr_text(self.calc_expr)
        # Phase 2 (v28.8): calc_fn KHÔNG bắt buộc — empty = fallback PATTERN_FORMULAS.
        if has_fn:
            _validate_calc_fn(self.calc_fn)
        if has_expr and has_fn:
            frappe.msgprint(
                "Cách tính này đang khai CẢ 'Công thức tính' lẫn 'Python Lambda'. "
                "Hệ thống chỉ dùng 'Công thức tính' — hãy xoá ô còn lại để "
                "người sau không sửa nhầm ô không có tác dụng.",
                indicator="orange",
                alert=True,
            )
        # Ô câu chữ hiển thị: bỏ trống, HOẶC công thức vừa đổi mà câu chữ không đổi
        # ⇒ chép lại từ công thức. Nhờ vậy câu chữ không lệch khỏi phép tính, mà
        # admin vẫn đặt được câu tiếng Việt dễ đọc (seed đang để câu tiếng Việt).
        old_expr = old_display = None
        if not self.is_new():
            old_expr = frappe.db.get_value(
                self.doctype, self.name, "calc_expr")
            old_display = frappe.db.get_value(
                self.doctype, self.name, "calc_formula")
        display = (self.calc_formula or "").strip()
        if has_expr and (not display or (display == (old_display or "").strip()
                         and (self.calc_expr or "").strip() != (old_expr or "").strip())):
            self.calc_formula = self.calc_expr.strip()

        # Phase 3 (v28.8): chặn đổi công thức khi không đủ role.
        # Field-level permission không có trong Frappe core → validate hook là chuẩn.
        # B7: áp cho CẢ calc_expr (đổi calc_expr cũng đổi số tiền y hệt calc_fn).
        if not self.is_new():
            old_fn = frappe.db.get_value(self.doctype, self.name, "calc_fn")
            if (old_expr != self.get("calc_expr")
                    or old_fn != self.get("calc_fn")) and not (
                "AL Technical Admin" in frappe.get_roles()
                or "System Manager" in frappe.get_roles()
            ):
                frappe.throw(
                    "Chỉ AL Technical Admin hoặc System Manager được thay đổi công thức tính."
                )

    def on_update(self):
        """F3: xoá cache `calc_fn` sau khi save.

        `lookup_calc_pattern` cache cả kết quả DƯƠNG (_DB_PATTERN_CACHE) lẫn ÂM
        (_NEGATIVE_CACHE) — sửa `calc_fn` mà không xoá thì bản CŨ còn sống tới
        khi restart tiến trình. `clear_calc_fn_cache()` đã có sẵn trong module
        này (re-export từ `alumglass.formula_handlers`) nhưng trước đây KHÔNG
        nơi nào gọi.

        Frappe tự gọi `on_update` của controller qua `Document.run_method`
        (`getattr(self, "on_update")` — xem frappe/model/document.py, không cần
        khai `doc_events` trong hooks.py cho method CÙNG TÊN).
        """
        clear_calc_fn_cache()

    def on_trash(self):
        """F3: xoá cache `calc_fn` khi xoá record — không thì bullet cũ vẫn
        sống trong cache tới khi restart (lookup sẽ dùng công thức của record
        đã bị xoá)."""
        clear_calc_fn_cache()
