"""v1_0 — cấp quyền cấu hình sản phẩm cho ĐÚNG nhân vật (B10).

VÌ SAO CẦN
---------
`AL Variable Profile` (bộ lọc biến hiện trong ô công thức) và
`AL Formula Field` (field nào là công thức) chỉ khai `System Manager` trong
JSON của doctype. Nhưng vòng lặp module trong `setup/install_roles.py` cấp
`AL BOM Manager` TOÀN QUYỀN trên mọi doctype thuộc module "AL Master Data".
Hệ quả là quyền **ngược nhân vật**:

  · quản trị BOM sửa được regex / registry công thức — thứ họ không nên sửa;
  · `AL Technical Admin` (vai kỹ thuật) KHÔNG mở được để sửa.

`install_roles` chỉ chạy lúc after_install ⇒ sửa hằng số ở đó KHÔNG có tác
dụng với site đã cài. Patch này chạy sau và phủ cả site cũ lẫn site mới.

THIẾT KẾ ĐÃ DUYỆT (§4.4 + B10 của
`docs/design/gop-noi-cau-hinh-bien-va-tinh-toan.md`)
--------------------------------------------------------------------
  · `AL Technical Admin`: read/write/create (sửa regex + registry).
    KHÔNG cấp delete/import: xoá một hồ sơ đang dùng phải là thao tác có
    chủ đích, không phải một cú bấm.
  · `AL BOM Manager`: chỉ ĐỌC (+ export). Họ vẫn cần đọc để biết vì sao
    biến hiện/không hiện trong ô công thức, nhưng không sửa regex.

VÌ SAO DÙNG `_set_full_docperm` CHỨ KHÔNG PHẢI `_upsert_docperm`
--------------------------------------------------------------
Bản ghi `(parent, role, permlevel=0)` của BOM Manager đã tồn tại với
`write=1` do vòng lặp module. `_upsert_docperm` chỉ cập nhật các khoá có
trong dict ⇒ `write` cũ vẫn còn 1, patch "hạ quyền" sẽ **không hạ được**.
`_set_full_docperm` đặt mọi cờ về 0 rồi mới bật cờ được cấp.

Idempotent: `_set_full_docperm` upsert theo `(parent, role, permlevel)` nên
chạy lại không tạo bản ghi trùng.

AN TOÀN KHI THIẾU VAI
---------------------
Mỗi doctype cần ĐỦ cả `AL BOM Manager` và `AL Technical Admin` mới chạy.
Thiếu một vai ⇒ bỏ qua cả doctype: hạ quyền BOM Manager khi chưa có người
thay thế sẽ khoá đường sửa (chỉ còn System Manager).

BẢNG QUYỀN NẰM Ở ĐÂU
--------------------
`setup/install_roles.py::CONFIG_PERMISSIONS` — MỘT bản duy nhất. Patch này
import lại (cho site đã cài), còn `after_install` dùng nó (cho site cài
mới). ⛔ Khai lại bảng ở đây: Frappe đánh dấu mọi patch là "đã chạy" lúc
cài mới (`set_all_patches_as_completed`) nên patch KHÔNG chạy trên site mới
— thiếu bản trong `install_roles` là site mới bị quyền ngược nhân vật.
"""

import frappe


def _grant():
	"""Cấp quyền theo `CONFIG_PERMISSIONS`. Trả số cặp (doctype, role) đã cấp."""
	# Dùng CHUNG bảng + hàm với `setup/install_roles.py` — một bản sự thật,
	# một bản logic upsert (parent, role, permlevel). ⛔ chép lại ở đây.
	from alumglass.setup.install_roles import (
		CONFIG_PERMISSIONS,
		_set_full_docperm,
	)

	granted = 0
	for doctype, role_perms in CONFIG_PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			print("  · %s: chưa có, bỏ qua" % doctype)
			continue

		# Thiếu MỘT vai là bỏ qua CẢ doctype: hạ quyền BOM Manager khi chưa có
		# người thay thế sẽ khoá đường sửa (chỉ còn System Manager).
		missing = [role for role in role_perms if not frappe.db.exists("Role", role)]
		if missing:
			print("  · %s: thiếu vai %s — bỏ qua để không khoá quyền" % (doctype, ", ".join(missing)))
			continue

		for role, perms in role_perms.items():
			_set_full_docperm(doctype, role, perms)
			granted += 1
			print("  · %s · %s: đã cấp %s" % (doctype, role, perms))

	return granted


def execute():
	print("v1_0 — cấp quyền cấu hình sản phẩm (B10)")
	granted = _grant()
	print("  · Tổng: %d cặp (doctype, role)" % granted)

	# Patch convention của repo: ghi sổ rồi commit ngay.
	frappe.db.commit()
	print("v1_0 — xong")
