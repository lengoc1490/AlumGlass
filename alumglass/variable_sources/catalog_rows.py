"""MỘT nguồn đọc danh mục biến sau khi gộp (B2/R3).

Trước 2026-11-27 danh mục biến nằm ở HAI nhà: `AL Variable Library` và
`AL Variable Settings` (2 bảng con). B2 gộp cả hai vào Library (R3) và
2026-11-27 **xoá hẳn** bảng Settings. Tệp này là **chỗ duy nhất** biết cách
đọc, để adapter / API / validate không mỗi nơi một kiểu.

BA LOẠI — RỜI NHAU, ⛔ chồng lấn (nếu chồng, cùng một biến hiện 2 lần và
`dedupe_candidates` báo "trùng tên" trên UI):

  · `KIND_COMMON` (`common_variables`) — `is_input=1` (người dùng nhập: W_mm, H_mm…).
  · `KIND_ROW`    (`row_literals`)     — `group_label == "Row Literals"` (engine inject theo dòng).
  · `KIND_USER`   (`user_variables`)   — `is_system=0`, `is_input=0`, KHÔNG thuộc
                         Row Literals (biến cấu hình còn lại: glass_master, màu…).

Tên `KIND_*` giữ nguyên chuỗi cũ vì là khoá API/JSON, ⛔ phải đổi theo bảng.

VÌ SAO TÁCH `user_variables` KHỎI ROW LITERAL:
`variable_library_user` được mở cho hồ sơ BOM (B3b). Nếu nó trả cả row literal,
người dùng sẽ thấy `unit_price` trong ô công thức B4 — nơi engine **không có**
namespace literal trần (chỉ `items.<slug>.<field>`) ⇒ công thức chạy ra 0 âm
thầm. Row literal chỉ được mở qua nguồn `row_literal`, và hồ sơ BOM cố ý
không bật nguồn đó (xem `patches/v28_14/seed_bom_profile.py`).

MỘT NGUỒN DUY NHẤT: `AL Variable Library`. Bảng Settings đã bị xoá
(patch `v1_0.drop_variable_settings_tables`) nên ⛔ còn đường đọc cũ — đọc
vào bảng không tồn tại chỉ tạo lỗi SQL lúc chạy.
"""
import frappe

DOCTYPE = "AL Variable Library"
ROW_LITERAL_GROUP = "Row Literals"
COMMON_DEFAULT_GROUP = "Thông số nhập"

KIND_COMMON = "common_variables"
KIND_ROW = "row_literals"
KIND_USER = "user_variables"

_FIELDS = (
    "var_name", "var_label", "var_type", "group_label",
    "sort_order", "is_active", "description", "source_doctype",
    "source_field", "default_value", "is_input",
)


def _as_flag(value, default=True):
    """Ép cờ về bool — `bool("0")` là True nên phải xét chuỗi."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no")
    return bool(value)


def _normalize(row, kind):
    """Chuẩn hoá 1 dòng Library về bộ khoá dùng chung cho cả 3 loại.

    `group_label` là **nhóm DUY NHẤT** — không còn `category` riêng (2026-11-27).
    """
    group = (row.get("group_label") or "").strip()
    if kind == KIND_ROW:
        group = ROW_LITERAL_GROUP
    elif not group and kind == KIND_COMMON:
        group = COMMON_DEFAULT_GROUP
    # KIND_USER: để RỖNG — adapter tự dùng nhóm "User Variables" như cũ.
    return {
        "var_name": (row.get("var_name") or "").strip(),
        "var_label": row.get("var_label") or "",
        "var_type": row.get("var_type") or "Float",
        "group_label": group,
        "sort_order": row.get("sort_order") or 0,
        "is_active": row.get("is_active"),
        "description": row.get("description") or "",
        "source_doctype": row.get("source_doctype") or "",
        "source_field": row.get("source_field") or "",
        "default_value": row.get("default_value"),
        "is_input": 1 if kind == KIND_COMMON else 0,
        "is_system": 0,
    }


def _rows_from_library(kind):
    try:
        rows = frappe.get_all(
            DOCTYPE,
            filters={"is_system": 0},
            fields=list(_FIELDS),
            order_by="sort_order asc, var_name asc",
        ) or []
    except Exception:
        return []
    out = []
    for row in rows:
        is_input = _as_flag(row.get("is_input"), False)
        is_row = (row.get("group_label") or "").strip() == ROW_LITERAL_GROUP
        # Nhóm Row Literals THẮNG cờ is_input: một dòng không thể vừa là
        # biến người dùng nhập vừa là literal engine inject — nếu cả hai cờ
        # cùng bật, xếp vào ROW (đúng nghĩa runtime) để ⛔ hiện 2 nhóm.
        if kind == KIND_COMMON and (not is_input or is_row):
            continue
        if kind == KIND_ROW and not is_row:
            continue
        if kind == KIND_USER and (is_input or is_row):
            continue
        out.append(_normalize(row, kind))
    return out


def rows_for(kind):
    """Toàn bộ dòng của 1 loại, ĐÃ chuẩn hoá (kể cả dòng đang tắt).

    Caller tự lọc `is_active` — để phân biệt "admin tắt hết" với "chưa khai".
    """
    if kind not in (KIND_COMMON, KIND_ROW, KIND_USER):
        raise ValueError("catalog_rows: loại biến không hợp lệ: %r" % (kind,))

    return _rows_from_library(kind)


def active_rows(kind):
    """Dòng đang bật, sắp theo `sort_order` rồi tên."""
    rows = [r for r in rows_for(kind) if _as_flag(r.get("is_active"), True)]
    rows.sort(key=lambda r: (r.get("sort_order") or 0, r.get("var_name") or ""))
    return rows


def active_names(kind):
    """Tên biến đang bật — dùng cho validate/`rule_input`."""
    return [r["var_name"] for r in active_rows(kind) if r.get("var_name")]
