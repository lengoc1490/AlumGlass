# -*- coding: utf-8 -*-
"""Registry field công thức (DATA-DRIVEN) — thay danh sách hardcode
`FORMULA_DOCTYPE_REGISTRY` trong `public/js/formula_setup.js`.

Trước bản vá, danh sách "doctype nào có field công thức nào" nằm CỨNG trong
JS ⇒ thêm 1 field công thức mới phải sửa JS + deploy asset.

Nay nguồn DUY NHẤT là doctype `AL Formula Field` (module AL Master Data).
JS chỉ fetch API này ở `refresh` của form ⇒ thêm field = thêm 1 record, không
sửa code, không build lại asset.

Hợp đồng trả về (DEV3 tiêu thụ trong `alumglass.FormulaFields`):
    [
      {
        "doctype": "AL Bom Set",
        "child_table": "items",          # "" = field trên chính doctype
        "fieldname": "width",
        "id_field": "slug",              # slug field của child table
        "editor_opts": {"height": "70px", "float_popup": true},
        "sort_order": 10,
      },
      ...
    ]

`editor_opts` đã parse JSON; giá trị hỏng ⇒ {} (không làm chết autocomplete).

⚠ Cột doctype đích trong DB tên `target_doctype` (`doctype` là từ khoá dành
riêng của Frappe) — API vẫn trả key `"doctype"` theo hợp đồng ở trên.
"""

import json

import frappe

# Cache theo REQUEST, không theo worker: `frappe.local` được dựng lại mỗi
# request ⇒ admin thêm/sửa record `AL Formula Field` thấy ngay ở lần mở form
# kế tiếp (cache module-level sẽ sống tới khi restart worker — đúng lỗi cũ).
_CACHE_ATTR = "_al_formula_fields_cache"


def _request_cache():
    """Dict cache gắn vào `frappe.local` (mỗi request/lượt một bản).

    Ngoài ngữ cảnh Frappe (script/test thuần) không có `frappe.local` ⇒ trả
    dict rỗng MỚI mỗi lần gọi (không cache) thay vì ném lỗi.
    """
    try:
        cache = getattr(frappe.local, _CACHE_ATTR, None)
        if cache is None:
            cache = {}
            setattr(frappe.local, _CACHE_ATTR, cache)
        return cache
    except Exception:
        return {}


_CACHE_FIELDS = ("child_table", "fieldname", "id_field",
                 "editor_opts", "sort_order")

# Frappe ⛔ KHÔNG cho DocType dùng fieldname `doctype` (từ khoá dành riêng của
# BaseDocument) ⇒ cột thật của `AL Formula Field` là `target_doctype`. Vẫn đọc
# theo meta để chịu được cả 2 cách đặt tên (spec ghi `doctype`) mà không sửa
# code khi schema đổi.
_DOCTYPE_FIELD_CANDIDATES = ("target_doctype", "doctype")


def _doctype_fieldname():
    """Tên cột chứa doctype đích của record `AL Formula Field`."""
    try:
        meta_fields = {
            f.fieldname
            for f in (frappe.get_meta("AL Formula Field").get("fields") or [])
        }
    except Exception:
        meta_fields = set()
    for candidate in _DOCTYPE_FIELD_CANDIDATES:
        if candidate in meta_fields:
            return candidate
    # Không đọc được meta (hiếm) → dùng tên theo spec; query sẽ tự báo lỗi
    # và được ghi log ở dưới thay vì đoán bừa.
    return "doctype"


def _parse_editor_opts(raw):
    """`editor_opts` lưu dạng JSON string trong DocType — parse lỗi ⇒ {}.

    ⛔ Không throw: cấu hình hỏng chỉ làm mất tuỳ chọn hiển thị (height,
    float_popup), KHÔNG được làm mất autocomplete của field.
    """
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@frappe.whitelist()
def get_formula_fields(doctype=None):
    """Trả danh sách field công thức đang bật của `doctype` (rỗng = tất cả).

    Args:
        doctype: lọc theo doctype đang mở (vd "AL Bom Set"). Bỏ trống ⇒ trả
            toàn bộ registry (dùng cho trang quản trị/kiểm tra).

    Lỗi/thiếu doctype `AL Formula Field` (site chưa migrate) ⇒ trả [] và ghi
    log — phía JS đã có hợp đồng "API lỗi thì không làm gì" (không fallback
    danh sách cứng, vì danh sách cứng chính là thứ đang được dẹp bỏ).
    """
    cache = _request_cache()
    cache_key = doctype or "*"
    if cache_key in cache:
        return cache[cache_key]

    if not frappe.db.exists("DocType", "AL Formula Field"):
        # Site chưa migrate bản có doctype này — trả rỗng thay vì ném lỗi
        # (form vẫn mở được, chỉ chưa có autocomplete nâng cao).
        cache[cache_key] = []
        return []

    filters = {"is_active": 1}
    doctype_field = _doctype_fieldname()
    if doctype:
        filters[doctype_field] = doctype

    try:
        rows = frappe.get_all(
            "AL Formula Field",
            filters=filters,
            fields=[doctype_field] + list(_CACHE_FIELDS),
            order_by="sort_order asc, %s asc, fieldname asc" % doctype_field,
        ) or []
    except Exception:
        # Bảng thiếu cột (migrate dở) / lỗi DB — ghi log đủ context, trả rỗng.
        frappe.log_error(
            frappe.get_traceback(),
            title="AlumGlass get_formula_fields failed: %s" % (doctype or "*"),
        )
        cache[cache_key] = []
        return []

    result = []
    for row in rows:
        result.append({
            "doctype": row.get(doctype_field) or "",
            "child_table": row.get("child_table") or "",
            "fieldname": row.get("fieldname") or "",
            "id_field": row.get("id_field") or "slug",
            "editor_opts": _parse_editor_opts(row.get("editor_opts")),
            "sort_order": row.get("sort_order") or 0,
        })

    cache[cache_key] = result
    return result
