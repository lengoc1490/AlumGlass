# -*- coding: utf-8 -*-
"""v1_0 — GỘP `category` vào `group_label` (một nhóm DUY NHẤT cho mỗi biến).

VÌ SAO
------
`AL Variable Library` từng có HAI ô cùng nghĩa: `category` (Category) và
`group_label` (Nhóm hiển thị). Trên thực tế hai ô luôn bằng nhau — cả đường
gộp Settings lẫn form đều ghi cùng một giá trị. Hai ô cùng nghĩa là hai nguồn
sự thật: sửa một ô, ô kia cũ hơn, và danh sách gợi ý hiện sai nhóm.

Từ 2026-11-27 **chỉ còn `group_label`** (Select: Kích thước · Cấu hình ·
Màu sắc · Xuất xứ · Kỹ thuật · Thi công · Thông số nhập · System ·
Row Literals). Bảng vẫn giữ cột `category` cũ ở DB cho an toàn — mã ⛔ đọc nó
nữa.

PATCH LÀM GÌ
-----------
1. Dòng có `group_label` rỗng ⇒ lấy `category` (nếu cột còn).
2. Nhóm cũ `BOM Input Variables` ⇒ đổi sang `Thông số nhập` (hai tên cho cùng
   một loại biến).
3. Dòng có `is_input = 1` mà nhóm đang rỗng ⇒ `Thông số nhập`.
4. Biến theo dòng (`category` hoặc `usage` = Row Literals) ⇒ `Row Literals`.

Idempotent: chạy lại không đổi gì. `update_modified=False` — chỉ đồng bộ
metadata kỹ thuật, ⛔ phải làm bản ghi "vừa bị sửa".
"""
import frappe

LIBRARY = "AL Variable Library"

ROW_LITERAL_GROUP = "Row Literals"
USAGE_ROW = "Từng dòng"
INPUT_GROUP = "Thông số nhập"
LEGACY_INPUT_GROUP = "BOM Input Variables"

#: Phải khớp `options` của ô "Nhóm hiển thị" trong
#: `al_variable_library.json` — Select từ chối giá trị ngoài danh sách.
GROUP_OPTIONS = (
	"Kích thước", "Cấu hình", "Màu sắc", "Xuất xứ", "Kỹ thuật",
	"Thi công", "Thông số nhập", "System", "Row Literals",
)


def execute():
	print("v1_0 — gộp category vào group_label (%s)" % LIBRARY)
	if not frappe.db.has_column(LIBRARY, "group_label"):
		print("  · chưa có cột group_label — bỏ qua")
		return

	has_category = frappe.db.has_column(LIBRARY, "category")
	fields = ["name", "group_label", "is_input", "usage"]
	if has_category:
		fields.append("category")

	try:
		rows = frappe.get_all(LIBRARY, fields=fields, order_by="name asc") or []
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="unify_variable_group: không đọc được %s" % LIBRARY,
		)
		print(
			"  · KHÔNG đọc được bảng (xem Error Log). Sửa xong chạy lại: "
			"bench --site <site> execute "
			"alumglass.patches.v1_0.unify_variable_group.execute"
		)
		return

	from_category = 0
	renamed = 0
	filled_input = 0
	row_literals = 0
	unknown = []

	for row in rows:
		group = (row.get("group_label") or "").strip()
		legacy = (row.get("category") or "").strip() if has_category else ""
		usage = (row.get("usage") or "").strip()

		if group == LEGACY_INPUT_GROUP:
			group = INPUT_GROUP
			renamed += 1
		if not group and (legacy == ROW_LITERAL_GROUP or usage == USAGE_ROW):
			group = ROW_LITERAL_GROUP
			row_literals += 1
		elif not group and legacy:
			group = INPUT_GROUP if legacy == LEGACY_INPUT_GROUP else legacy
			from_category += 1
		elif not group and row.get("is_input"):
			group = INPUT_GROUP
			filled_input += 1
		if not group:
			continue
		if group not in GROUP_OPTIONS:
			# Nhóm tự do (cột cũ là Data) — Select sẽ CHẶN khi người dùng mở
			# dòng đó bấm Lưu. Quy về nhóm mặc định theo loại biến.
			mapped = INPUT_GROUP if row.get("is_input") else "Cấu hình"
			print("    ⚠ Nhóm lạ %r của %s ⇒ %s" % (group, row["name"], mapped))
			group = mapped
			unknown.append(row["name"])
		if group == (row.get("group_label") or "").strip():
			continue

		frappe.db.set_value(
			LIBRARY, row["name"], "group_label", group, update_modified=False
		)

	print(
		"  · Lấy từ category: %d · Đổi tên nhóm cũ: %d · Điền nhóm nhập: %d · "
		"Row Literals: %d · Quy đổi nhóm lạ: %d"
		% (from_category, renamed, filled_input, row_literals, len(unknown))
	)
	if unknown:
		print("    ⚠ Đã quy đổi nhóm lạ cho: %s" % ", ".join(unknown))
	frappe.db.commit()
	print("v1_0 — xong")
