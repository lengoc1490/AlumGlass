"""B7/Đ5 — điền `calc_expr` cho 14 cách tính đã seed.

Vì sao cần: `calc_expr` (cú pháp Formula Builder) là **nguồn chính** từ đợt này.
Record cũ chỉ có `calc_fn` (chuỗi lambda) — người dùng không đọc được trên màn
hình cấu hình. Patch chép **đúng** biểu thức tương đương của từng lambda seed,
nên **số tiền không đổi** (xem `test_calc_expr_b7.py` đối chứng từng cặp).

Nguồn biểu thức: `alumglass.formula_handlers.CALC_EXPR` — MỘT BẢN, dùng chung
với seed. ⛔ Không chép bảng sang đây (bản chép sẽ trôi khỏi lambda).

Nguyên tắc:
  - CHỈ điền khi `calc_expr` đang rỗng — ⛔ đè công thức admin đã sửa tay.
  - Nếu `calc_fn` đang có mà **khác** biểu thức seed ⇒ coi là công thức admin tự
    sửa: ⛔ KHÔNG điền (điền vào là đổi số tiền sau lưng), chỉ liệt kê để người
    phụ trách chuyển tay.
  - `calc_fn` **giữ nguyên** (đường lùi): engine ưu tiên `calc_expr`, `calc_fn` chỉ
    còn là phương án dự phòng cho pattern chưa chuyển được.
  - Record không tồn tại → bỏ qua, chỉ đếm (site chưa seed thì patch vô hại).
"""

import ast

import frappe

from alumglass.formula_handlers import CALC_EXPR

DOCTYPE = "AL Quantity Calc Method"


def _lambda_body(fn_str):
    """Trả về body đã chuẩn hoá của chuỗi lambda, None nếu không phải lambda."""
    try:
        tree = ast.parse((fn_str or "").strip(), mode="eval")
    except SyntaxError:
        return None
    if not isinstance(tree.body, ast.Lambda):
        return None
    return ast.unparse(tree.body.body)


def _expr_body(expr):
    try:
        return ast.unparse(ast.parse((expr or "").strip(), mode="eval").body)
    except SyntaxError:
        return None


def execute():
    if not frappe.db.has_column(DOCTYPE, "calc_expr"):
        print(f"[backfill_calc_expr] {DOCTYPE} chưa có cột calc_expr — bỏ qua")
        return

    filled, kept, custom, missing = [], [], [], []
    for code, expr in CALC_EXPR.items():
        if not frappe.db.exists(DOCTYPE, code):
            missing.append(code)
            continue
        current = frappe.db.get_value(DOCTYPE, code, "calc_expr")
        if current and current.strip():
            kept.append(code)
            continue
        fn_str = frappe.db.get_value(DOCTYPE, code, "calc_fn")
        if fn_str and fn_str.strip() and _lambda_body(fn_str) != _expr_body(expr):
            # Công thức riêng của site — ⛔ không đụng, vì đổi là đổi số tiền.
            custom.append(code)
            continue
        frappe.db.set_value(DOCTYPE, code, "calc_expr", expr, update_modified=False)
        filled.append(code)

    msg = (
        f"[backfill_calc_expr] Điền mới: {len(filled)} · Giữ nguyên: {len(kept)} "
        f"· Công thức riêng (bỏ qua): {len(custom)} · Không có record: {len(missing)}"
    )
    print(msg)
    if filled:
        print("  Điền: " + ", ".join(filled))
    if custom:
        print("  Công thức riêng — chuyển tay sang ô 'Công thức tính': "
              + ", ".join(custom))
    if missing:
        print("  Chưa có record: " + ", ".join(missing))
    if filled or kept or custom or missing:
        try:
            frappe.log_error(msg, "backfill_calc_expr")
        except Exception:
            pass
