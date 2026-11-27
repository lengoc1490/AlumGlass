import frappe
from frappe.model.document import Document

#: Ba lựa chọn của ô "Dùng ở" — nhãn NGƯỜI ĐỌC, ⛔ phải khớp `options` trong JSON.
USAGE_GLOBAL = "Toàn đơn"
USAGE_ROW = "Từng dòng"
USAGE_INPUT = "Người dùng nhập"

ROW_LITERAL_GROUP = "Row Literals"
DEFAULT_INPUT_GROUP = "Thông số nhập"
DEFAULT_GLOBAL_GROUP = "Cấu hình"

#: Nhóm chuẩn của biến người dùng nhập. Giữ tên cũ `BOM Input Variables` như
#: một nhóm hợp lệ để dữ liệu cũ không vỡ Select (patch `unify_variable_group`
#: đổi chúng sang nhóm chuẩn).
LEGACY_INPUT_GROUP = "BOM Input Variables"


def derive_usage(is_system, is_input, group):
    """Suy ô "Dùng ở" từ dữ liệu cũ. Thứ tự: hệ thống → theo dòng → nhập → chung.

    Hàm THUẦN (không DB) để test được và để patch backfill dùng CHUNG một
    logic với form — ⛔ chép lại công thức ở hai nơi.
    """
    if is_system:
        return USAGE_GLOBAL
    if (group or "").strip() == ROW_LITERAL_GROUP:
        return USAGE_ROW
    if is_input:
        return USAGE_INPUT
    return USAGE_GLOBAL


def flags_for_usage(usage, group):
    """`(is_input, group)` cần ghi cho một lựa chọn "Dùng ở".

    ⛔ Trả `is_system`: biến hệ thống do seed/resolver tạo, đổi cờ đó từ form
    là thay đổi hành vi engine — form chỉ CẢNH BÁO khi mâu thuẫn.
    """
    usage = (usage or "").strip()
    group = (group or "").strip()
    # Nhóm hiển thị "Row Literals" chỉ do máy đặt; người dùng chọn nhóm khác
    # thì giữ nguyên nhóm đó.
    if group == ROW_LITERAL_GROUP:
        group = ""
    if usage == USAGE_ROW:
        return 0, ROW_LITERAL_GROUP
    if usage == USAGE_INPUT:
        return 1, group or DEFAULT_INPUT_GROUP
    return 0, group or DEFAULT_GLOBAL_GROUP


class ALVariableLibrary(Document):
    """Thư viện biến tập trung - định nghĩa 1 lần, dùng nhiều nơi."""

    def validate(self):
        if self.is_system and self.source_doctype:
            if not self.source_field:
                frappe.throw(
                    "Biến \"%s\" đã chọn Source Doctype nhưng chưa khai "
                    "Source Field. Điền cột nguồn (hoặc bỏ trống cả hai nếu "
                    "đây là hằng số)."
                    % (self.get("var_label") or self.get("var_name") or "")
                )
        self._sync_usage()
        self._warn_duplicate_global_constant()

    def _warn_duplicate_global_constant(self):
        """Báo khi biến hệ TRÙNG TÊN một hằng số `Formula Global Variable`.

        Engine nạp hằng số FGV vào `inputs` TRƯỚC; lớp Thư viện biến chỉ điền
        chỗ còn thiếu ⇒ sửa `default_value` ở đây KHÔNG đổi giá. Không báo
        thì người cấu hình sửa đúng chỗ nhìn thấy mà tiền không đổi, không
        một dòng lỗi — đúng loại hỏng im lặng phải chặn.
        """
        if not self.get("is_system"):
            return
        if (self.get("source_doctype") or "").strip():
            return  # biến có nguồn — không phải hằng số
        name = (self.get("var_name") or "").strip()
        if not name:
            return
        try:
            if not frappe.db.exists("Formula Global Variable", name):
                return
        except Exception:
            return  # app Formula Builder chưa cài — không phải việc ở đây
        frappe.msgprint(
            "\"%s\" là HẰNG SỐ TOÀN CỤC: giá đang dùng lấy từ "
            "Formula Global Variable cùng tên. Sửa ô Default Value ở đây "
            "KHÔNG đổi giá — sửa ở Formula Global Variable."
            % (self.get("var_label") or name),
            alert=True,
        )

    def _sync_usage(self):
        """Tự suy cờ kỹ thuật từ ô "Dùng ở" (Đ4 — ⛔ bắt người dùng khai 4 ô).

        Dữ liệu cũ chưa có `usage` ⇒ suy từ `is_system`/`is_input`/`group_label`
        (cùng hàm `derive_usage` mà patch backfill dùng). Sau đó giữ
        `is_input`/nhóm khớp lựa chọn — nếu lệch, SỬA theo ô chọn, vì
        ô chọn mới là thứ người dùng vừa bấm.
        """
        usage = (self.get("usage") or "").strip()
        if not usage:
            usage = derive_usage(self.get("is_system"), self.get("is_input"),
                                 self.get("group_label"))
            self.usage = usage

        if usage not in (USAGE_GLOBAL, USAGE_ROW, USAGE_INPUT):
            frappe.throw(
                "Ô \"Dùng ở\" phải là một trong: %s / %s / %s."
                % (USAGE_GLOBAL, USAGE_ROW, USAGE_INPUT))

        if usage in (USAGE_ROW, USAGE_INPUT) and self.get("is_system"):
            # ⛔ tự hạ cờ hệ thống: cờ đó quyết định resolver/engine đọc biến.
            # Chỉ cảnh báo để người cấu hình tạo biến mới thay vì đổi nghĩa.
            frappe.msgprint(
                "Biến \"%s\" đang là biến HỆ THỐNG nhưng chọn \"%s\". "
                "Hệ thống giữ nguyên cờ hệ thống — nếu muốn biến theo dòng/"
                "người dùng nhập, hãy tạo biến mới thay vì đổi biến này."
                % (self.get("var_label") or self.name or self.get("var_name"),
                   usage),
                alert=True,
            )
            return

        chosen = (self.get("group_label") or "").strip()
        is_input, group = flags_for_usage(usage, chosen)
        if chosen == ROW_LITERAL_GROUP and usage != USAGE_ROW:
            # Ô chọn vẫn có "Row Literals" (bắt buộc, để lưu được biến theo
            # dòng) — nhưng chọn nó cho biến KHÔNG theo dòng là hiểu sai.
            frappe.msgprint(
                "Nhóm \"Row Literals\" do máy đặt cho biến \"Từng dòng\". "
                "Biến này đã được chuyển về nhóm \"%s\"." % group,
                alert=True,
            )
        self.is_input = is_input
        if group:
            self.group_label = group
