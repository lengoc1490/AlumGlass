import frappe
from frappe.model.document import Document

#: Ba lựa chọn của ô "Dùng ở" — nhãn NGƯỜI ĐỌC, ⛔ phải khớp `options` trong JSON.
USAGE_GLOBAL = "Toàn đơn"
USAGE_ROW = "Từng dòng"
USAGE_INPUT = "Người dùng nhập"

ROW_LITERAL_CATEGORY = "Row Literals"
DEFAULT_INPUT_CATEGORY = "Thông số nhập"
DEFAULT_GLOBAL_CATEGORY = "Cấu hình"


def derive_usage(is_system, is_input, category):
    """Suy ô "Dùng ở" từ dữ liệu cũ. Thứ tự: hệ thống → theo dòng → nhập → chung.

    Hàm THUẦN (không DB) để test được và để patch backfill dùng CHUNG một
    logic với form — ⛔ chép lại công thức ở hai nơi.
    """
    if is_system:
        return USAGE_GLOBAL
    if (category or "").strip() == ROW_LITERAL_CATEGORY:
        return USAGE_ROW
    if is_input:
        return USAGE_INPUT
    return USAGE_GLOBAL


def flags_for_usage(usage, category, group_label):
    """`(is_input, category)` cần ghi cho một lựa chọn "Dùng ở".

    ⛔ Trả `is_system`: biến hệ thống do seed/resolver tạo, đổi cờ đó từ form
    là thay đổi hành vi engine — form chỉ CẢNH BÁO khi mâu thuẫn.
    """
    usage = (usage or "").strip()
    category = (category or "").strip()
    group_label = (group_label or "").strip()
    if usage == USAGE_ROW:
        return 0, ROW_LITERAL_CATEGORY
    if usage == USAGE_INPUT:
        # Rời khỏi nhóm Row Literals — giữ nhóm hiển thị cũ nếu có.
        new_category = (group_label or category
                        if category != ROW_LITERAL_CATEGORY
                        else (group_label or DEFAULT_INPUT_CATEGORY))
        return 1, new_category
    # Toàn đơn
    new_category = (category if category != ROW_LITERAL_CATEGORY
                    else (group_label or DEFAULT_GLOBAL_CATEGORY))
    return 0, new_category


class ALVariableLibrary(Document):
    """Thư viện biến tập trung - định nghĩa 1 lần, dùng nhiều nơi."""

    def validate(self):
        if self.is_system and self.source_doctype:
            if not self.source_field:
                frappe.throw(
                    f"System variable '{self.var_name}': "
                    f"cần 'Source Field' khi đã chọn 'Source Doctype'"
                )
        self._sync_usage()

    def _sync_usage(self):
        """Tự suy cờ kỹ thuật từ ô "Dùng ở" (Đ4 — ⛔ bắt người dùng khai 4 ô).

        Dữ liệu cũ chưa có `usage` ⇒ suy từ `is_system`/`is_input`/`category`
        (cùng hàm `derive_usage` mà patch backfill dùng). Sau đó giữ
        `is_input`/`category` khớp lựa chọn — nếu lệch, SỬA theo ô chọn, vì
        ô chọn mới là thứ người dùng vừa bấm.
        """
        usage = (self.get("usage") or "").strip()
        if not usage:
            usage = derive_usage(self.get("is_system"), self.get("is_input"),
                                 self.get("category"))
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

        is_input, category = flags_for_usage(
            usage, self.get("category"), self.get("group_label"))
        self.is_input = is_input
        if category:
            self.category = category
