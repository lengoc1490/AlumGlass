import frappe
from frappe.model.document import Document
from frappe.utils import today


class ALInstallationOrder(Document):
    """Lệnh thi công - quản lý toàn bộ quá trình lắp đặt."""

    def validate(self):
        if self.planned_start_date and self.planned_end_date:
            if self.planned_end_date < self.planned_start_date:
                frappe.throw("Ngày kết thúc không thể trước ngày bắt đầu")

    def before_save(self):
        """Tự động sync status dựa trên task progress."""
        if not self.items:
            return
        completed = sum(1 for t in self.items if t.status == "Completed")
        total = len(self.items)
        if completed == total and self.status != "On Hold":
            self.status = "Completed"
            self.actual_end_date = today()
        elif completed > 0 and self.status in ("Draft", "Scheduled"):
            self.status = "In Progress"
            if not self.actual_start_date:
                self.actual_start_date = today()
