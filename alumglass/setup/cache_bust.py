# -*- coding: utf-8 -*-
"""Xoá cache phía máy chủ sau `bench migrate` — để mã JS mới có hiệu lực.

VÌ SAO CẦN
──────────
Frappe nhúng nội dung các tệp `doctype_js` (vd `quotation.js`, `sales_order.js`)
vào **form meta** của DocType rồi cache ở Redis dưới hash `doctype_form_meta`
khi site **KHÔNG** bật developer mode:

    frappe/desk/form/meta.py:36-49  →  get_meta()
        if cached and not frappe.conf.developer_mode:
            meta = frappe.cache().hget("doctype_form_meta", doctype)

Hệ quả: kéo mã mới + `bench restart` **không** làm mới JS trong trình duyệt —
meta cũ (mang nội dung `quotation.js` cũ) vẫn nằm nguyên trong Redis. Đây đúng
là triệu chứng Owner gặp 2026-11-23: dòng báo giá đã cập nhật BOM Version nhưng
mở lại dialog vẫn chạy mã CŨ. `bench migrate` chạy hook này ⇒ cache bị xoá ⇒
lượt tải form kế tiếp dựng lại meta từ tệp trên đĩa.

Cũng xoá `assets_json` (cache bản đồ asset dùng chung, `frappe/utils/__init__.py`
`get_assets_json`, key đặt `shared=True`) để lần `bench build` sau đó được nhận.
Lệnh này KHÔNG thay `bench build`: tệp trong `public/` vẫn phải build lại.

IDEMPOTENT: gọi nhiều lần liên tiếp vô hại — `hdel` trên key/hash không tồn tại
là no-op, `delete_value` cũng vậy.
"""

import frappe

# DocType có `doctype_js` trong `alumglass/hooks.py`. Chỉ cần xoá đúng các
# DocType này — xoá cả hash sẽ làm mọi form khác dựng lại meta vô ích.
CACHE_BUST_DOCTYPES = ("Quotation", "Sales Order")


def _delete_value(cache, key, **kwargs):
	"""Xoá 1 khoá value; bản Frappe cũ không có tham số `shared` ⇒ gọi lại
	không kèm tham số đó. Trả 1 (đã xoá) — dùng cho bộ đếm log."""
	try:
		cache.delete_value(key, **kwargs)
	except TypeError:
		cache.delete_value(key)
	return 1


def after_migrate():
	"""Hook `after_migrate` — chạy sau mỗi `bench migrate`.

	Xoá cache form meta của các DocType có JS override + cache `assets_json`.
	Không ném khi cache rỗng (site mới / Redis vừa restart).
	"""
	cache = frappe.cache()
	cleared = 0

	for doctype in CACHE_BUST_DOCTYPES:
		cache.hdel("doctype_form_meta", doctype)
		cleared += 1

	# `assets_json`: Frappe ĐỌC bằng `get_value("assets_json", ..., shared=True)`
	# (`frappe/utils/__init__.py` `get_assets_json`) nhưng chính `bench clear-cache`
	# lại xoá khoá KHÔNG shared (`frappe/cache_manager.py:112`). Xoá CẢ HAI biến
	# thể — rẻ, và nếu bản Frappe nào đổi chỗ ghi thì vẫn sạch.
	cleared += _delete_value(cache, "assets_json", shared=True)
	cleared += _delete_value(cache, "assets_json")

	frappe.logger("alumglass").info(
		"cache_bust: đã xoá %s key cache (doctype_form_meta: %s; assets_json)",
		cleared,
		", ".join(CACHE_BUST_DOCTYPES),
	)

	return cleared
