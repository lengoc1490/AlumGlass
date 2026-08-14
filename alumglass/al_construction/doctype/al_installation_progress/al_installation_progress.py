import frappe
from frappe.model.document import Document


class ALInstallationProgress(Document):
    """Nhật ký tiến độ thi công - append-only."""

    def after_insert(self):
        if not self.installation_order:
            return
        order = frappe.get_doc("AL Installation Order", self.installation_order)
        if self.progress_pct is not None:
            if self.progress_pct >= 100:
                order.status = "Completed"
                order.actual_end_date = frappe.utils.today()
            elif self.progress_pct > 0:
                order.status = "In Progress"
                if not order.actual_start_date:
                    order.actual_start_date = frappe.utils.today()
            order.save(ignore_permissions=True)
