"""v1_0 — R3/B2: gộp `common_variables` + `row_literals` vào `AL Variable Library`.

VÌ SAO
------
Trước 2026-11-27 danh mục biến nằm ở 3 nhà: Library (hệ thống + người dùng),
`AL Variable Settings.common_variables`, `AL Variable Settings.row_literals`.
Người dùng phải biết "biến này khai ở bảng nào" mới thêm được — và thêm sai
bảng thì biến im lặng không có giá trị. B2 gộp 2 bảng con vào Library.

DỮ LIỆU ĐI ĐÂU
--------------
  · `common_variables` → Library với `is_input = 1`, `group_label` = nhóm của dòng Settings.
  · `row_literals`     → Library với `group_label = "Row Literals"`,
    giữ `source_doctype`/`source_field` (đã có từ patch v28_15).
  · `default_profile`  → `AL Variable Profile.is_default`.
  · `preview_doctype`  → `AL Variable Profile.preview_doctype` (hồ sơ mặc định).

NGUYÊN TẮC GHI — ⛔ KHÔNG ĐÈ CẤU HÌNH ADMIN
-------------------------------------------
Tên biến là khoá (`autoname = field:var_name`). Đã có dòng cùng tên ⇒ chỉ
ĐIỀN CHỖ TRỐNG (group_label, sort_order, source_*, is_active) và bật cờ
`is_input` cho common; ⛔ không đổi `is_system`, nhãn, kiểu, default_value.
Đã có mà là biến HỆ THỐNG (`is_system=1`) ⇒ **xung đột thật** (một tên không
thể vừa hệ thống vừa row-literal/common): in rõ tên + ghi log, KHÔNG ghi đè.

ĐÃ MIGRATE thì Library là nguồn DUY NHẤT (xem `variable_sources/catalog_rows.py`):
bảng Settings rỗng hay bị tắt hết cũng không làm biến cũ sống lại. Bảng vật lý
GIỮ LẠI một chu kỳ để lùi (R3), chỉ bỏ khỏi màn hình.

Idempotent: chạy lại lần 2 không tạo thêm dòng, không đổi gì.
"""
import frappe

SETTINGS_DOCTYPE = "AL Variable Settings"
LIBRARY_DOCTYPE = "AL Variable Library"
PROFILE_DOCTYPE = "AL Variable Profile"
ROW_LITERAL_GROUP = "Row Literals"
COMMON_DEFAULT_GROUP = "Thông số nhập"

_LIB_FIELDS = (
    "name", "var_name", "var_label", "var_type", "group_label",
    "sort_order", "is_active", "description", "source_doctype",
    "source_field", "default_value", "is_system", "is_input",
)


def _as_flag(value, default=True):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no")
    return bool(value)


def _clean(value):
    return (value or "").strip() if isinstance(value, str) else (value or "")


def _load_settings():
    try:
        return frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        return None


def _existing_rows():
    try:
        rows = frappe.get_all(
            LIBRARY_DOCTYPE, fields=list(_LIB_FIELDS),
            order_by="var_name asc") or []
    except Exception:
        # Thiếu cột mới ⇒ patch chạy sai thứ tự (phải ở [post_model_sync]).
        frappe.throw(
            "v1_0.merge_variable_settings_into_library: chưa đọc được cột mới "
            "của %s. Patch phải chạy ở [post_model_sync] sau khi sync doctype "
            "— kiểm tra alumglass/patches.txt." % LIBRARY_DOCTYPE)
    return {row.get("var_name"): row for row in rows if row.get("var_name")}


def _create_row(row, kind, created):
    is_common = kind == "common"
    group = _clean(row.get("group_label")) or (
        COMMON_DEFAULT_GROUP if is_common else ROW_LITERAL_GROUP)
    doc = frappe.get_doc({
        "doctype": LIBRARY_DOCTYPE,
        "var_name": _clean(row.get("var_name")),
        "var_label": row.get("var_label") or "",
        "var_type": row.get("var_type") or "Float",
        "group_label": group,
        "sort_order": row.get("sort_order") or 0,
        "is_active": 1 if _as_flag(row.get("is_active"), True) else 0,
        "description": row.get("description") or "",
        "source_doctype": row.get("source_doctype") or None,
        "source_field": row.get("source_field") or None,
        "default_value": row.get("default_value"),
        "is_system": 0,
        "is_input": 1 if is_common else 0,
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    created.append(doc.name if hasattr(doc, "name") else doc.var_name)


def _fill_missing(existing, row, kind, updates):
    """Điền chỗ trống trên dòng Library đã có. Trả list field đã đổi."""
    is_common = kind == "common"
    values = {}

    if is_common and not _as_flag(existing.get("is_input"), False):
        values["is_input"] = 1
    if not _clean(existing.get("group_label")):
        group = _clean(row.get("group_label")) or (
            COMMON_DEFAULT_GROUP if is_common else ROW_LITERAL_GROUP)
        values["group_label"] = group
    if not existing.get("sort_order") and row.get("sort_order"):
        values["sort_order"] = row.get("sort_order")
    if existing.get("is_active") is None:
        values["is_active"] = 1 if _as_flag(row.get("is_active"), True) else 0
    if not _clean(existing.get("description")) and row.get("description"):
        values["description"] = row.get("description")
    if kind == "row":
        for field in ("source_doctype", "source_field"):
            if not _clean(existing.get(field)) and row.get(field):
                values[field] = row.get(field)

    if values:
        updates.append((existing.get("name") or existing.get("var_name"),
                        values))
    return values


def _merge_table(rows, kind, existing, report):
    for row in rows or []:
        name = _clean(row.get("var_name"))
        if not name:
            continue
        current = existing.get(name)
        if current is None:
            _create_row(row, kind, report["created"])
            # Ghi ngay vào sổ trong bộ nhớ — nếu bảng Settings có 2 dòng cùng
            # tên, dòng sau phải điền chỗ trống thay vì tạo bản ghi thứ hai
            # (var_name unique ⇒ lần insert sau sẽ nổ).
            existing[name] = {
                "name": name, "var_name": name, "is_system": 0,
                "is_input": 1 if kind == "common" else 0,
            }
            continue

        if _as_flag(current.get("is_system"), False):
            report["conflicts"].append(name)
            continue
        _fill_missing(current, row, kind, report["updates"])


def _migrate_default_profile(settings, report):
    default = _clean(settings.get("default_profile"))
    preview = _clean(settings.get("preview_doctype"))
    if not default:
        return
    if not frappe.db.exists(PROFILE_DOCTYPE, default):
        report["profile_missing"] = default
        return

    updates = {}
    if frappe.db.has_column(PROFILE_DOCTYPE, "is_default"):
        updates["is_default"] = 1
    if preview and frappe.db.has_column(PROFILE_DOCTYPE, "preview_doctype"):
        updates["preview_doctype"] = preview
    if updates:
        frappe.db.set_value(PROFILE_DOCTYPE, default, updates,
                            update_modified=False)
        report["profile_moved"] = default


def execute():
    print("v1_0 — gộp AL Variable Settings vào AL Variable Library")
    settings = _load_settings()
    if settings is None:
        print("  · %s: không có (site mới chưa seed) — bỏ qua"
              % SETTINGS_DOCTYPE)
        return

    existing = _existing_rows()
    report = {"created": [], "updates": [], "conflicts": [],
              "profile_moved": None, "profile_missing": None}

    _merge_table(settings.get("common_variables"), "common", existing, report)
    # Nạp lại sau bảng common: row literal có thể trùng tên với dòng vừa tạo.
    existing = _existing_rows()
    _merge_table(settings.get("row_literals"), "row", existing, report)

    for name, values in report["updates"]:
        frappe.db.set_value(LIBRARY_DOCTYPE, name, values,
                            update_modified=False)

    _migrate_default_profile(settings, report)

    print("  · Tạo mới: %d · Điền chỗ trống: %d · Xung đột: %d"
          % (len(report["created"]), len(report["updates"]),
             len(report["conflicts"])))
    if report["created"]:
        print("    + %s" % ", ".join(report["created"]))
    if report["conflicts"]:
        # ⛔ im lặng: một tên vừa là biến hệ thống vừa là row-literal/common
        # là mâu thuẫn mô hình — người vận hành phải quyết định tên khác.
        msg = ("Xung đột tên với biến HỆ THỐNG (giữ nguyên dòng hệ thống): %s"
               % ", ".join(report["conflicts"]))
        print("    ⚠ " + msg)
        frappe.log_error(msg, "AlumGlass B2 merge settings")
    if report["profile_moved"]:
        print("    · Hồ sơ mặc định → %s" % report["profile_moved"])
    if report["profile_missing"]:
        print("    ⚠ default_profile trỏ hồ sơ không tồn tại: %s"
              % report["profile_missing"])

    frappe.db.commit()
    print("v1_0 — xong")
