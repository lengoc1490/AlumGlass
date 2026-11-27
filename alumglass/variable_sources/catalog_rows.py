"""MỘT nguồn đọc danh mục biến sau khi gộp (B2/R3).

Trước 2026-11-27 danh mục biến nằm ở HAI nhà:
  · `AL Variable Library` — biến hệ thống (`is_system=1`) và biến người dùng;
  · `AL Variable Settings` — 2 bảng con `common_variables` + `row_literals`.
B2 gộp cả hai bảng con vào Library (R3). Tệp này là **chỗ duy nhất** biết
cách đọc, để adapter / API / validate không mỗi nơi một kiểu.

BA LOẠI — RỜI NHAU, ⛔ chồng lấn (nếu chồng, cùng một biến hiện 2 lần và
`dedupe_candidates` báo "trùng tên" trên UI):

  · `common_variables` — `is_input=1` (người dùng nhập: W_mm, H_mm…).
  · `row_literals`     — `category == "Row Literals"` (engine inject theo dòng).
  · `user_variables`   — `is_system=0`, `is_input=0`, KHÔNG thuộc Row Literals
                         (biến cấu hình còn lại: glass_master, màu…).

VÌ SAO TÁCH `user_variables` KHỎI ROW LITERAL:
`variable_library_user` được mở cho hồ sơ BOM (B3b). Nếu nó trả cả row literal,
người dùng sẽ thấy `unit_price` trong ô công thức B4 — nơi engine **không có**
namespace literal trần (chỉ `items.<slug>.<field>`) ⇒ công thức chạy ra 0 âm
thầm. Row literal chỉ được mở qua nguồn `row_literal`, và hồ sơ BOM cố ý
không bật nguồn đó (xem `patches/v28_14/seed_bom_profile.py`).

TƯƠNG THÍCH NGƯỢC (site chưa `bench migrate`):
Cột `is_input` do B2 thêm. Chưa có cột ⇒ đọc `AL Variable Settings` như cũ;
`user_variables` đọc Library `is_system=0` trừ Row Literals. Sau migrate,
Library là nguồn DUY NHẤT — bảng Settings rỗng hay bị tắt hết cũng KHÔNG
làm biến cũ sống lại (⛔ fallback ngầm sau migrate).
"""
import frappe

DOCTYPE = "AL Variable Library"
SETTINGS_DOCTYPE = "AL Variable Settings"
ROW_LITERAL_CATEGORY = "Row Literals"
COMMON_DEFAULT_GROUP = "BOM Input Variables"

KIND_COMMON = "common_variables"
KIND_ROW = "row_literals"
KIND_USER = "user_variables"

_FIELDS = (
    "var_name", "var_label", "var_type", "category", "group_label",
    "sort_order", "is_active", "description", "source_doctype",
    "source_field", "default_value", "is_input",
)


#: Patch đã CHÉP dữ liệu Settings → Library. Có cột `is_input` chưa đủ: model
#: sync thêm cột xong mà patch nổ giữa đường thì Library RỖNG, trong khi cột
#: đã có — đọc Library sẽ làm MẤT toàn bộ biến. Chốt bằng Patch Log.
MIGRATION_PATCH = ("alumglass.patches.v1_0."
                   "merge_variable_settings_into_library")


def is_library_migrated():
    """B2 đã chạy XONG chưa (có cột `is_input` VÀ patch gộp đã ghi sổ)."""
    try:
        if not frappe.db.has_column(DOCTYPE, "is_input"):
            return False
    except Exception:
        return False
    try:
        return bool(frappe.db.exists("Patch Log", {"patch": MIGRATION_PATCH}))
    except Exception:
        # Không đọc được Patch Log ⇒ giữ đường CŨ (Settings). Chọn hướng an
        # toàn: biến cũ vẫn hiện; biến mới thêm trong Library có thể chưa
        # hiện cho tới khi đọc được Patch Log — ⛔ mất biến hàng loạt.
        return False


def _as_flag(value, default=True):
    """Ép cờ về bool — `bool("0")` là True nên phải xét chuỗi."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no")
    return bool(value)


def _normalize(row, kind):
    """Chuẩn hoá 1 dòng (Library hoặc Settings) về cùng bộ khoá."""
    category = (row.get("category") or "").strip()
    if kind == KIND_ROW:
        category = ROW_LITERAL_CATEGORY
    group = (row.get("group_label") or "").strip()
    if not group:
        if kind == KIND_ROW:
            group = ROW_LITERAL_CATEGORY
        elif kind == KIND_COMMON:
            # Biến người dùng nhập: nhóm hiển thị lấy group_label của dòng
            # Settings cũ, không có thì theo category (Kích thước, Thi công…).
            group = category or COMMON_DEFAULT_GROUP
        # KIND_USER: để RỖNG — adapter tự dùng nhóm "User Variables" như cũ.
    return {
        "var_name": (row.get("var_name") or "").strip(),
        "var_label": row.get("var_label") or "",
        "var_type": row.get("var_type") or "Float",
        "category": category,
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
        category = (row.get("category") or "").strip()
        is_input = _as_flag(row.get("is_input"), False)
        is_row = category == ROW_LITERAL_CATEGORY
        # Category Row Literals THẮNG cờ is_input: một dòng không thể vừa là
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


def _rows_from_library_legacy(kind):
    """Trước migrate: chưa có cột `is_input`.

    `common_variables`/`row_literals` vẫn ở Settings; `user_variables` đọc
    Library `is_system=0` (trừ Row Literals — phòng site đã tự tạo tay).
    """
    if kind != KIND_USER:
        return None
    fields = [f for f in _FIELDS if f != "is_input"]
    try:
        rows = frappe.get_all(
            DOCTYPE, filters={"is_system": 0}, fields=fields,
            order_by="var_name asc") or []
    except Exception:
        return []
    out = []
    for row in rows:
        if (row.get("category") or "").strip() == ROW_LITERAL_CATEGORY:
            continue
        out.append(_normalize(row, kind))
    return out


def _rows_from_settings(kind):
    table = KIND_ROW if kind == KIND_ROW else KIND_COMMON
    try:
        settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
        rows = list(settings.get(table) or []) if settings else []
    except Exception:
        return []
    return [_normalize(row, kind) for row in rows]


def rows_for(kind):
    """Toàn bộ dòng của 1 loại, ĐÃ chuẩn hoá (kể cả dòng đang tắt).

    Caller tự lọc `is_active` — để phân biệt "admin tắt hết" với "chưa khai".
    """
    if kind not in (KIND_COMMON, KIND_ROW, KIND_USER):
        raise ValueError("catalog_rows: loại biến không hợp lệ: %r" % (kind,))

    if is_library_migrated():
        return _rows_from_library(kind)

    legacy = _rows_from_library_legacy(kind)
    if legacy is not None:
        return legacy
    return _rows_from_settings(kind)


def active_rows(kind):
    """Dòng đang bật, sắp theo `sort_order` rồi tên."""
    rows = [r for r in rows_for(kind) if _as_flag(r.get("is_active"), True)]
    rows.sort(key=lambda r: (r.get("sort_order") or 0, r.get("var_name") or ""))
    return rows


def active_names(kind):
    """Tên biến đang bật — dùng cho validate/`rule_input`."""
    return [r["var_name"] for r in active_rows(kind) if r.get("var_name")]
