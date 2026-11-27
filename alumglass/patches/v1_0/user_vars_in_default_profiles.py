"""v1_0 — Biến người dùng của `AL Variable Library` hiện trong gợi ý công thức.

VÌ SAO CẦN
---------
Ba profile mặc định (`P_BOM_DEFAULT`, `P_COST_TEMPLATE_DEFAULT`,
`P_ACCESSORY_DEFAULT`) đặt `default_action = EXCLUDE_ALL` và chỉ Include 6
nguồn — **không có `variable_library_user`**. Hệ quả đã đo được trên site:

    Người dùng tạo biến mới trong `AL Variable Library`
    → mở ô công thức gõ tên biến
    → KHÔNG thấy biến, KHÔNG câu nào giải thích.

Đây là lỗi im lặng: biến có thật, engine đọc được (biến toàn cục lấy từ
`inputs` của lượt tính), chỉ danh sách gợi ý bị lọc mất.

PATCH LÀM 3 VIỆC — cả 3 đều idempotent, ⛔ không ghi đè cấu hình admin
--------------------------------------------------------------------
1. Thêm rule `Include · variable_library_user` vào 3 profile mặc định.
   CHỈ khi profile **chưa có rule nào chạm nguồn này** (Include hay Exclude).
   Admin đã chủ động ẩn biến người dùng ⇒ tôn trọng, bỏ qua.

2. Cấp Custom DocPerm cho `AL BOM Manager` trên `Formula Global Variable`.
   R4 chọn bảng hằng số của `formula_builder` làm nhà DUY NHẤT cho hằng số,
   nhưng doctype đó chỉ cấp quyền cho System Manager ⇒ người quản trị BOM
   không mở được dù thiết kế bảo họ quản lý hằng số.

3. KHÔNG đổi mã cho nhánh "không gán profile ⇒ hiện tất cả": nhánh này đã
   đúng sẵn — `api.get_formula_context` rơi về đường legacy 8 nhóm khi
   catalog trả `profile = None` (xem `_get_catalog_context`,
   `legacy_fallback`). Ghi ở đây để người sau không "sửa" nó thành rỗng.

VÌ SAO PATCH MỚI, KHÔNG SỬA `seed_bom_profile` / `seed_variable_catalog`
----------------------------------------------------------------------
Hai patch đó đã ghi Patch Log trên site đang chạy ⇒ sửa hằng `RULES` ở đó
KHÔNG có tác dụng với site đã chạy (đúng cảnh báo trong chính tệp seed).
Patch này chạy sau, phủ cả site cũ lẫn site cài mới.

VÌ SAO AN TOÀN KHI MỞ NGUỒN NÀY
------------------------------
`variable_library_user` chỉ đọc `AL Variable Library` với `is_system = 0` —
tức biến người dùng nhập (kích thước, cấu hình, màu…), KHÔNG phải Row
Literals (những dòng đó nằm ở `AL Variable Settings.row_literals`, patch này
không chạm). Nếu admin tự tạo biến Library với nhóm "Row Literals" mà
engine không nạp ở bước chọn mã, `AL Rule._sync_input_variable` đã cảnh báo
sẵn khi lưu quy tắc — không thành số 0 âm thầm.
"""
import frappe

PROFILE_DOCTYPE = "AL Variable Profile"
SOURCE_KIND = "variable_library_user"

#: profile_code → (group_label, sort_order).
#: Chèn NGAY SAU nhóm "Thông số nhập" sẵn có của từng profile để biến người
#: dùng nằm cạnh các biến nhập khác, không rơi xuống cuối danh sách.
PROFILE_RULES = {
    "P_BOM_DEFAULT": ("03 · Thông số nhập", 35),
    "P_COST_TEMPLATE_DEFAULT": ("06 · Thông số nhập", 65),
    "P_ACCESSORY_DEFAULT": ("06 · Thông số nhập", 65),
}

CONSTANT_DOCTYPE = "Formula Global Variable"
CONSTANT_ROLE = "AL BOM Manager"


def _touches_source(rules, source_kind):
    """Profile đã có rule (Include hoặc Exclude) chạm nguồn này chưa."""
    for rule in rules or []:
        if (rule.get("source_kind") or "").strip() == source_kind:
            return True
    return False


def _include_user_library():
    """Thêm rule Include cho 3 profile mặc định. Trả số profile đã sửa."""
    if not frappe.db.exists("DocType", PROFILE_DOCTYPE):
        # Patch khai ở [post_model_sync] ⇒ thiếu doctype là cấu hình
        # patches.txt sai. Báo lớn, ⛔ bỏ qua im lặng.
        frappe.throw(
            "v1_0.user_vars_in_default_profiles: chưa có doctype '%s'. "
            "Patch phải chạy ở [post_model_sync] sau khi sync doctype — "
            "kiểm tra alumglass/patches.txt." % PROFILE_DOCTYPE)

    changed = 0
    for profile_code, (group_label, sort_order) in PROFILE_RULES.items():
        if not frappe.db.exists(PROFILE_DOCTYPE, profile_code):
            print("  · Profile %s: chưa có, bỏ qua" % profile_code)
            continue

        doc = frappe.get_doc(PROFILE_DOCTYPE, profile_code)
        if _touches_source(doc.get("rules"), SOURCE_KIND):
            print("  · Profile %s: đã khai '%s', bỏ qua (giữ cấu hình admin)"
                  % (profile_code, SOURCE_KIND))
            continue

        doc.append("rules", {
            "doctype": "AL Variable Profile Rule",
            "action": "Include",
            "source_kind": SOURCE_KIND,
            # "*" = mọi bản ghi của nguồn (không giới hạn theo tên).
            "source_ref": "*",
            "group_label": group_label,
            "sort_order": sort_order,
            "is_active": 1,
        })
        doc.flags.ignore_permissions = True
        doc.save()
        changed += 1
        print("  · Profile %s: +Include · %s" % (profile_code, SOURCE_KIND))

    return changed


def _grant_constant_permission():
    """Cấp quyền quản trị bảng hằng số cho vai BOM Manager. Trả True nếu cấp."""
    if not frappe.db.exists("DocType", CONSTANT_DOCTYPE):
        # `formula_builder` chưa cài ⇒ không có bảng hằng số để cấp quyền.
        # Đây là trạng thái hợp lệ (app phụ thuộc), ⛔ throw.
        print("  · %s: chưa có (formula_builder chưa cài), bỏ qua"
              % CONSTANT_DOCTYPE)
        return False
    if not frappe.db.exists("Role", CONSTANT_ROLE):
        print("  · Role %s: chưa có, bỏ qua" % CONSTANT_ROLE)
        return False

    # Dùng CHUNG hàm với `setup/install_roles.py` — một bản logic upsert
    # (parent, role, permlevel), ⛔ chép lại ở đây.
    from alumglass.setup.install_roles import (
        CONSTANT_PERMISSIONS,
        _upsert_docperm,
    )

    perms = CONSTANT_PERMISSIONS.get(CONSTANT_DOCTYPE, {}).get(CONSTANT_ROLE)
    if not perms:
        print("  · %s · %s: chưa khai trong CONSTANT_PERMISSIONS, bỏ qua"
              % (CONSTANT_DOCTYPE, CONSTANT_ROLE))
        return False

    _upsert_docperm(CONSTANT_DOCTYPE, CONSTANT_ROLE, perms)
    print("  · %s · %s: đã cấp quyền" % (CONSTANT_DOCTYPE, CONSTANT_ROLE))
    return True


def execute():
    print("v1_0 — mở biến người dùng cho gợi ý công thức")
    changed = _include_user_library()
    granted = _grant_constant_permission()
    print("  · Tổng: %d profile sửa, quyền hằng số=%s"
          % (changed, "đã cấp" if granted else "bỏ qua"))

    # Patch convention của repo: ghi sổ rồi commit ngay.
    frappe.db.commit()
    print("v1_0 — xong")
