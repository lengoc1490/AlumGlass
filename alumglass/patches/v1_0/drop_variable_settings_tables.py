# -*- coding: utf-8 -*-
"""XOÁ HẲN `AL Variable Settings` + 2 bảng con — bước cuối của B2/R3.

Sau khi `merge_variable_settings_into_library` đã chép dữ liệu sang
`AL Variable Library`, bảng Settings chỉ còn là **bản sao chết**. Giữ nó
nhiều kỳ nghĩa là mỗi lần đọc mã phải nhớ "đừng dùng bảng này", và trên site
còn hiện một màn cấu hình trùng lặp (người dùng sửa vào đó, sửa xong không ai
đọc ⇒ hỏng im lặng). Patch này xoá hẳn.

GỒM BA VIỆC
──────────
1. Chạy LẠI `merge_variable_settings_into_library` (idempotent) — để phiên
   migrate nào bị đứt giữa đường cũng không mất dữ liệu.
2. CỔNG CHẶN: **mọi** `var_name` còn trong 2 bảng con phải tồn tại ở
   `AL Variable Library`; nếu `default_profile` có giá trị thì phải có một
   `AL Variable Profile` đang bật `is_default=1`. Thiếu/lệch ⇒ `frappe.throw`
   liệt kê mã, ⛔ xoá gì.
3. Xuất dữ liệu còn lại ra tệp JSON trong `private/backups/` rồi xoá:
   DocType record (con trước, cha sau), dòng `tabSingles`, và DROP 3 bảng.

VÌ SAO PHẢI DROP BẢNG Ở ĐÂY
───────────────────────────
`frappe.delete_doc("DocType", ...)` **không** xoá bảng vật lý (xem
`frappe/tests/test_rename_doc.py`: "delete_doc doesnt drop tables"). Nếu chỉ
xoá DocType record, `tabAL Common Variable` / `tabAL Row Literal` vẫn nằm đó
vĩnh viễn — đúng thứ cần dọn. Nên patch chạy `DROP TABLE IF EXISTS` sau khi
đã kiểm tra + sao lưu.

BẢO VỆ
──────
· ⛔ xoá khi còn mã chưa có bản trong Library (cổng chặn trên).
· Tệp sao lưu `al_variable_settings_<thời điểm>.json` nằm trong
  `sites/<site>/private/backups/` — khôi phục bằng tay nếu cần đối chiếu.
· IDEMPOTENT: bảng không còn ⇒ bỏ qua, patch chạy lại không lỗi.
· Vẫn nên backup site trước lượt migrate:
  `bench --site <site> backup --with-files`
"""

import json
import os

import frappe

SETTINGS_DOCTYPE = "AL Variable Settings"
CHILD_DOCTYPES = ("AL Common Variable", "AL Row Literal")
LIBRARY_DOCTYPE = "AL Variable Library"
PROFILE_DOCTYPE = "AL Variable Profile"

#: Thứ tự xoá: con trước, cha sau.
DELETE_ORDER = ("AL Common Variable", "AL Row Literal", SETTINGS_DOCTYPE)

#: Cột đọc để sao lưu / đối chiếu — chỉ những cột chắc chắn có ở mọi site.
_BACKUP_COLUMNS = {
	"AL Common Variable": (
		"name", "parent", "parentfield", "parenttype", "idx",
		"var_name", "var_label", "var_type", "group_label", "sort_order",
		"is_active", "description",
	),
	"AL Row Literal": (
		"name", "parent", "parentfield", "parenttype", "idx",
		"var_name", "var_label", "var_type", "group_label", "sort_order",
		"is_active", "description", "source_doctype", "source_field",
	),
}


def execute():
	"""Điểm vào của patch (đăng ký ở `alumglass/patches.txt`)."""
	if not _table_exists(SETTINGS_DOCTYPE) and not _any_child_table():
		# Đã dọn xong (lượt migrate trước) — không còn gì để đọc. Vẫn dọn
		# nốt DocType record / dòng Singles nếu lượt trước đứt giữa đường.
		_delete_doctype_records()
		_drop_singles_rows()
		return

	_backup_rows()
	_run_merge_again()
	_assert_library_has_everything()
	_delete_doctype_records()
	_drop_tables()


# ══════════════════════════════════════════════════════════════════════
# Đọc / kiểm tra
# ══════════════════════════════════════════════════════════════════════
def _table_exists(doctype):
	"""Bảng vật lý đã có chưa — `cached=False` để không đọc cache cũ."""
	try:
		return bool(frappe.db.table_exists(doctype, cached=False))
	except frappe.DoesNotExistError:
		return False


def _any_child_table():
	return any(_table_exists(doctype) for doctype in CHILD_DOCTYPES)


def _existing_columns(doctype, wanted):
	"""Cột thật sự có trong bảng — bảng cũ có thể thiếu cột mới thêm."""
	if not _table_exists(doctype):
		return []
	out = []
	for column in wanted:
		try:
			if frappe.db.has_column(doctype, column):
				out.append(column)
		except Exception:
			continue
	return out


def _rows(doctype):
	"""Đọc thẳng bảng bằng SQL thô (⛔ phụ thuộc DocType record)."""
	if not _table_exists(doctype):
		return []
	columns = _existing_columns(doctype, _BACKUP_COLUMNS.get(doctype, ("name",)))
	if not columns:
		return []
	column_sql = ", ".join("`%s`" % column for column in columns)
	return frappe.db.sql(
		"select %s from `tab%s` order by `name` asc" % (column_sql, doctype),
		as_dict=True,
	)


def _settings_singles():
	"""2 ô của Single: `default_profile`, `preview_doctype` (bảng Singles)."""
	try:
		rows = frappe.db.sql(
			"""select `field`, `value` from `tabSingles`
			   where `doctype` = %s and `field` in ('default_profile', 'preview_doctype')""",
			(SETTINGS_DOCTYPE,),
			as_dict=True,
		) or []
	except Exception:
		return {}
	return {row.get("field"): row.get("value") for row in rows if row.get("value")}


# ══════════════════════════════════════════════════════════════════════
# 1) Sao lưu
# ══════════════════════════════════════════════════════════════════════
def _backup_rows():
	"""Ghi toàn bộ dữ liệu còn lại ra `private/backups/` trước khi xoá.

	Không làm được (quyền/đĩa) ⇒ `frappe.log_error` rồi ĐI TIẾP: mất tệp sao
	lưu tay không đáng để chặn migrate, vì dữ liệu đã có bản trong Library
	(cổng chặn ngay sau đây kiểm đúng điều đó).
	"""
	payload = {
		"doctype": SETTINGS_DOCTYPE,
		"singles": _settings_singles(),
	}
	for doctype in CHILD_DOCTYPES:
		payload[doctype] = _rows(doctype)

	if not any(payload.get(doctype) for doctype in CHILD_DOCTYPES) and not payload["singles"]:
		return None

	try:
		backup_dir = frappe.get_site_path("private", "backups")
		os.makedirs(backup_dir, exist_ok=True)
		name = "al_variable_settings_%s.json" % frappe.utils.now_datetime().strftime(
			"%Y%m%d_%H%M%S"
		)
		path = os.path.join(backup_dir, name)
		with open(path, "w", encoding="utf-8") as handle:
			json.dump(payload, handle, ensure_ascii=False, indent=1, default=str)
		return path
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="drop_variable_settings_tables: không ghi được tệp sao lưu (migrate VẪN chạy tiếp; dữ liệu vẫn còn trong %s)" % LIBRARY_DOCTYPE,
		)
		return None


# ══════════════════════════════════════════════════════════════════════
# 2) Cổng chặn
# ══════════════════════════════════════════════════════════════════════
def _run_merge_again():
	"""Chạy lại patch gộp — idempotent, cứu phiên migrate đứt giữa đường."""
	try:
		from alumglass.patches.v1_0.merge_variable_settings_into_library import (
			execute as merge_execute,
		)

		merge_execute()
	except Exception:
		# Không chặn: cổng chặn ngay dưới đây mới là nơi quyết định.
		frappe.log_error(
			message=frappe.get_traceback(),
			title="drop_variable_settings_tables: chạy lại patch gộp thất bại",
		)


def _library_names():
	"""Toàn bộ `var_name` đang có ở Library (kể cả dòng đang tắt)."""
	if not _table_exists(LIBRARY_DOCTYPE):
		return set()
	rows = frappe.db.sql(
		"select `var_name` from `tab%s`" % LIBRARY_DOCTYPE, as_dict=True
	) or []
	return {(row.get("var_name") or "").strip() for row in rows if row.get("var_name")}


def _default_profile_ok():
	"""`default_profile` có giá trị ⇒ phải có hồ sơ đang bật `is_default=1`."""
	default_profile = (_settings_singles().get("default_profile") or "").strip()
	if not default_profile:
		return True
	if not frappe.db.has_column(PROFILE_DOCTYPE, "is_default"):
		return False
	rows = frappe.db.sql(
		"""select `name` from `tab%s`
		   where `is_default` = 1 and ifnull(`is_active`, 0) = 1""" % PROFILE_DOCTYPE,
		as_dict=True,
	) or []
	return bool(rows)


def _assert_library_has_everything():
	"""Mọi biến còn ở bảng Settings phải có ở Library — thiếu ⇒ throw."""
	library = _library_names()
	missing = []
	for doctype in CHILD_DOCTYPES:
		for row in _rows(doctype):
			var_name = (row.get("var_name") or "").strip()
			if var_name and var_name not in library:
				missing.append("%s (từ %s)" % (var_name, doctype))

	problems = []
	if missing:
		problems.append(
			"%d biến CHƯA có trong `%s`: %s."
			% (len(missing), LIBRARY_DOCTYPE, ", ".join(sorted(set(missing))))
		)
	if not _default_profile_ok():
		problems.append(
			"Hồ sơ mặc định chưa chuyển xong: chưa có hồ sơ nào **VỪA** tích "
			"\"Hồ sơ mặc định\" **VỪA** tích \"Đang dùng\" ở `%s`. Mở %s, "
			"tích cả hai ô trên đúng một hồ sơ." % (PROFILE_DOCTYPE, PROFILE_DOCTYPE)
		)
	if not problems:
		return

	frappe.throw(
		"Không xoá được bảng `%s`: dữ liệu chưa gộp đủ. %s Việc cần làm: "
		"(a) biến thiếu ⇒ mở **AL Variable Library** thêm đúng tên biến đó; "
		"(b) hồ sơ mặc định ⇒ tích hai ô như trên; "
		"(c) xong thì chạy lại: `bench --site <site> execute "
		"alumglass.patches.v1_0.merge_variable_settings_into_library.execute` "
		"rồi `bench --site <site> migrate`. ⛔ xoá bảng khi còn biến chưa có nhà."
		% (SETTINGS_DOCTYPE, " ".join(problems))
	)


# ══════════════════════════════════════════════════════════════════════
# 3) Xoá DocType record + dòng Singles
# ══════════════════════════════════════════════════════════════════════
def _referencing_fields(doctype):
	"""Các ô (DocField/Custom Field) còn trỏ tới `doctype` — để báo THẲNG tên.

	Trả list `"<doctype.field>"`; tra không được ⇒ list rỗng (⛔ bịa).
	"""
	refs = []
	for table, label in (("DocField", "DocField"), ("Custom Field", "Custom Field")):
		try:
			rows = frappe.db.sql(
				"""select `parent`, `fieldname` from `tab%s`
				   where `fieldtype` = 'Link' and `options` = %%s
				     and `parent` != %%s""" % table,
				(doctype, doctype),
				as_dict=True,
			) or []
		except Exception:
			continue
		for row in rows:
			name = "%s.%s" % (row.get("parent"), row.get("fieldname"))
			if name not in refs:
				refs.append(name)
	return refs


def _delete_doctype_records():
	for doctype in DELETE_ORDER:
		if not frappe.db.exists("DocType", doctype):
			continue
		try:
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
		except Exception as exc:  # noqa: BLE001 — ghi rõ rồi ném, ⛔ nuốt
			refs = _referencing_fields(doctype)
			if refs:
				action = (
					"Các ô sau vẫn trỏ tới nó: %s. Gỡ các ô đó rồi chạy lại patch."
					% ", ".join(refs)
				)
			else:
				action = (
					"Chưa thấy ô nào trỏ tới nó — xem chi tiết kỹ thuật ở dưới, "
					"xử lý nguyên nhân rồi chạy lại patch."
				)
			message = (
				"Không xoá được loại dữ liệu `%s`. %s Chi tiết kỹ thuật: %s"
				% (doctype, action, exc)
			)
			frappe.log_error(message=message, title="Xoá bảng Settings thất bại")
			frappe.throw(message)


def _drop_singles_rows():
	"""Xoá 2 ô của Single khỏi `tabSingles` (nếu còn)."""
	try:
		frappe.db.sql("delete from `tabSingles` where `doctype` = %s", (SETTINGS_DOCTYPE,))
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="drop_variable_settings_tables: không xoá được tabSingles",
		)


# ══════════════════════════════════════════════════════════════════════
# 4) DROP bảng
# ══════════════════════════════════════════════════════════════════════
def _drop_tables():
	if not _table_exists(SETTINGS_DOCTYPE) and not _any_child_table():
		return

	_drop_singles_rows()

	for doctype in CHILD_DOCTYPES + (SETTINGS_DOCTYPE,):
		if not _table_exists(doctype):
			continue
		try:
			frappe.db.sql_ddl("DROP TABLE IF EXISTS `tab%s`" % doctype)
		except Exception as exc:  # noqa: BLE001 — ghi rõ rồi ném, ⛔ nuốt
			message = (
				"Không xoá được bảng `tab%s`: %s. Dữ liệu đã nằm đủ ở `%s`. "
				"Nếu bước sao lưu đã chạy, tệp ở "
				"`private/backups/al_variable_settings_*.json`; nếu chưa, chạy "
				"`bench --site <site> backup --with-files` TRƯỚC khi xoá tay. "
				"Xong thì chạy tay `DROP TABLE IF EXISTS \\`tab%s\\`` rồi migrate lại."
				% (doctype, exc, LIBRARY_DOCTYPE, doctype)
			)
			frappe.log_error(message=message, title="DROP bảng Settings thất bại")
			frappe.throw(message)
