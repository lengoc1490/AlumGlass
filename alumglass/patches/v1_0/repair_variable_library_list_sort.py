# -*- coding: utf-8 -*-
"""v1_0 — Dọn kiểu sắp xếp CŨ còn trỏ tới ô `category` đã bỏ.

VÌ SAO CẦN PATCH NÀY
────────────────────
Danh sách `AL Variable Library` từng có cột **Category** để bấm sắp xếp. Sau
khi gộp về một ô `group_label`, cột đó không còn trong DocType — nhưng **lựa
chọn sắp xếp của từng người** thì Frappe lưu riêng ở bảng `__UserSettings`
(`List.sort_by`), và `bench migrate` **không** dọn giá trị đó (đồng bộ DocType
chỉ ghi lại phần meta).

Frappe v16 kiểm quyền trên đúng ô dùng để sắp xếp; thấy `category` không còn
⇒ ném

    PermissionError: You do not have permission to access field: ...

— tức **mở danh sách là lỗi**, chứ không phải người dùng thiếu quyền. Sau
khi sửa dữ liệu, người dùng mở lại bình thường (không phải cấp thêm quyền).

PATCH LÀM GÌ
───────────
1. Mỗi dòng `__UserSettings` của `AL Variable Library`: `List.sort_by` trỏ
   tới ô không còn ⇒ đổi về `group_label`, giữ nguyên chiều sắp xếp.
2. Bỏ các **điều kiện lọc** còn trỏ tới ô không còn (v16 cũng kiểm ô lọc).
3. Phòng xa: `DocType.sort_field` nếu trỏ vào ô không có thật ⇒ `group_label`.
4. Quét cache `_user_settings` (Redis) — bản cũ có thể **chưa** kịp đồng bộ
   xuống `__UserSettings`; key nào còn sắp xếp trỏ ô đã bỏ thì xoá. Sau đó xoá
   luôn cache của những người vừa sửa dưới DB, tránh Redis giữ bản cũ.

IDEMPOTENT: chạy lại không đổi gì, không ghi thêm.
"""

import json

import frappe

LIBRARY = "AL Variable Library"
FALLBACK_FIELD = "group_label"

#: Ô hệ thống luôn sắp xếp được dù không nằm trong `meta.fields`.
STD_FIELDS = frozenset(
	("name", "creation", "modified", "modified_by", "owner", "docstatus", "idx")
)

#: Khoá cache user settings (xem `frappe/model/utils/user_settings.py`).
USER_SETTINGS_CACHE = "_user_settings"


def execute():
	print("v1_0 — dọn kiểu sắp xếp cũ của %s" % LIBRARY)
	if not _exists():
		print("  · chưa có loại dữ liệu này — bỏ qua")
		return

	valid = _valid_fields()
	sort_field_fixed = _fix_doctype_sort_field(valid)
	cache_dropped = _drop_stale_cache(valid)
	changed, users = _fix_user_settings(valid)
	_clear_cache(users)

	print(
		"  · Sắp xếp của người dùng đã sửa: %d · cache cũ đã xoá: %d · "
		"sort_field của DocType: %s"
		% (
			changed,
			cache_dropped,
			"đã sửa" if sort_field_fixed else "không cần",
		)
	)
	if changed:
		print("    ⚠ Những người này mở lại danh sách là hết lỗi: %s" % ", ".join(users))
		frappe.db.commit()
	print("v1_0 — xong")


# ══════════════════════════════════════════════════════════════════════
# Ô hợp lệ
# ══════════════════════════════════════════════════════════════════════
def _exists():
	try:
		return bool(frappe.db.exists("DocType", LIBRARY))
	except Exception:
		return False


def _valid_fields():
	"""Tên các ô ĐANG có trong DocType (sau khi migrate đồng bộ)."""
	names = set(STD_FIELDS)
	try:
		meta = frappe.get_meta(LIBRARY)
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="repair_variable_library_list_sort: không đọc được meta",
		)
		return names

	for df in getattr(meta, "fields", None) or []:
		name = (getattr(df, "fieldname", "") or "").strip()
		if name:
			names.add(name)
	for attr in ("title_field", "image_field"):
		value = (getattr(meta, attr, "") or "").strip()
		if value:
			names.add(value)
	return names


def _fallback(valid):
	return FALLBACK_FIELD if FALLBACK_FIELD in valid else "modified"


def _order_field(value):
	"""`sort_field` có thể kèm chiều (`"a asc, b desc"`) — lấy tên ô."""
	if not isinstance(value, str):
		return ""
	return value.strip().split(" ")[0]


# ══════════════════════════════════════════════════════════════════════
# 3) DocType.sort_field
# ══════════════════════════════════════════════════════════════════════
def _fix_doctype_sort_field(valid):
	try:
		current = frappe.db.get_value("DocType", LIBRARY, "sort_field") or ""
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="repair_variable_library_list_sort: không đọc được sort_field",
		)
		return 0

	bad = [
		_order_field(part)
		for part in current.split(",")
		if _order_field(part) and _order_field(part) not in valid
	]
	if not bad:
		return 0

	try:
		frappe.db.set_value(
			"DocType", LIBRARY, "sort_field", _fallback(valid), update_modified=False
		)
		frappe.clear_cache(doctype=LIBRARY)
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="repair_variable_library_list_sort: không sửa được sort_field",
		)
		return 0
	return 1


# ══════════════════════════════════════════════════════════════════════
# 1+2) __UserSettings
# ══════════════════════════════════════════════════════════════════════
def _fix_user_settings(valid):
	"""Trả (số người đã sửa, danh sách người). Lỗi ⇒ ghi log, ⛔ chặn migrate."""
	try:
		rows = frappe.db.sql(
			"""select `user`, `data` from `__UserSettings` where `doctype` = %s""",
			(LIBRARY,),
			as_dict=True,
		) or []
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="repair_variable_library_list_sort: không đọc được __UserSettings",
		)
		print(
			"  · KHÔNG đọc được lựa chọn sắp xếp của người dùng (xem Error Log). "
			"Sau khi sửa, chạy lại: bench --site <site> execute "
			"alumglass.patches.v1_0.repair_variable_library_list_sort.execute"
		)
		return 0, []

	changed = []
	for row in rows:
		user = row.get("user")
		data = _loads(row.get("data"))
		if not user or not isinstance(data, dict):
			continue
		view = data.get("List")
		if not isinstance(view, dict):
			continue
		if not _repair_view(view, valid):
			continue
		try:
			frappe.db.sql(
				"""update `__UserSettings` set `data` = %s
				   where `user` = %s and `doctype` = %s""",
				(json.dumps(data, ensure_ascii=False), user, LIBRARY),
			)
		except Exception:
			frappe.log_error(
				message=frappe.get_traceback(),
				title="repair_variable_library_list_sort: không ghi được cho %s" % user,
			)
			continue
		changed.append(user)

	return len(changed), changed


def _repair_view(view, valid):
	"""Sửa tại chỗ 1 khối `List`; trả True nếu có thay đổi."""
	touched = False

	raw_sort = view.get("sort_by")
	sort_by = raw_sort.strip() if isinstance(raw_sort, str) else ""
	if raw_sort and sort_by not in valid:
		view["sort_by"] = _fallback(valid)
		touched = True

	filters = view.get("filters")
	if isinstance(filters, list):
		kept = [f for f in filters if _filter_field(f) in valid]
		if len(kept) != len(filters):
			view["filters"] = kept
			touched = True

	return touched


def _filter_field(entry):
	"""Tên ô của một điều kiện lọc — chịu được cả dạng cũ và mới."""
	if isinstance(entry, (list, tuple)):
		if len(entry) >= 2 and isinstance(entry[1], str):
			return entry[1].strip()
		return ""
	if isinstance(entry, dict):
		name = entry.get("fieldname")
		return name.strip() if isinstance(name, str) else ""
	return ""


def _loads(raw):
	try:
		return json.loads(raw or "{}")
	except (TypeError, ValueError):
		return {}


# ══════════════════════════════════════════════════════════════════════
# 4) Cache
# ══════════════════════════════════════════════════════════════════════
def _drop_stale_cache(valid):
	"""Xoá key cache còn giữ kiểu sắp xếp cũ.

	`__UserSettings` không phải nguồn duy nhất: `frappe.model.utils.user_settings`
	giữ bản trong Redis (`_user_settings`) và chỉ đồng bộ xuống DB định kỳ. Bản
	chỉ-có-trong-cache vẫn làm lỗi khi mở danh sách, nên phải soi cả cache.
	Xoá key là đủ: lần mở sau nó đọc lại từ DB (đã được sửa ở bước trên).
	"""
	cache = _cache()
	if cache is None or not hasattr(cache, "hgetall"):
		return 0

	try:
		entries = cache.hgetall(USER_SETTINGS_CACHE) or {}
	except Exception:
		return 0

	dropped = 0
	for key, raw in entries.items():
		key = key.decode() if isinstance(key, bytes) else key
		if not isinstance(key, str) or "::" not in key:
			continue
		doctype, _user = key.split("::", 1)
		if doctype != LIBRARY:
			continue
		if isinstance(raw, bytes):
			raw = raw.decode()
		data = _loads(raw)
		view = data.get("List") if isinstance(data, dict) else None
		if not isinstance(view, dict):
			continue
		sort_by = view.get("sort_by")
		if not sort_by or (isinstance(sort_by, str) and sort_by.strip() in valid):
			continue
		try:
			cache.hdel(USER_SETTINGS_CACHE, key)
			dropped += 1
		except Exception:
			frappe.log_error(
				message=frappe.get_traceback(),
				title="repair_variable_library_list_sort: không xoá được cache %s" % key,
			)
	return dropped


def _clear_cache(users):
	if not users:
		return
	cache = _cache()
	if cache is None:
		return
	for user in users:
		try:
			cache.hdel(USER_SETTINGS_CACHE, "%s::%s" % (LIBRARY, user))
		except Exception:
			# Cache chỉ là bản sao; hết hạn là tự lành. ⛔ chặn migrate vì nó.
			frappe.log_error(
				message=frappe.get_traceback(),
				title="repair_variable_library_list_sort: không xoá được cache",
			)


def _cache():
	"""v14 gọi `frappe.cache()`, v15+ dùng `frappe.cache` — chịu được cả hai."""
	try:
		cache = frappe.cache
		return cache() if callable(cache) else cache
	except Exception:
		return None
