import frappe
from frappe.model.document import Document

class ALVariableLibrary(Document):
    """Thư viện biến tập trung - định nghĩa 1 lần, dùng nhiều nơi."""

    def validate(self):
        if self.is_system and self.source_doctype:
            if not self.source_field:
                frappe.throw(
                    f"System variable '{self.var_name}': "
                    f"cần 'Source Field' khi đã chọn 'Source Doctype'"
                )
