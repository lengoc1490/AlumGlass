import frappe
from frappe.model.document import Document
from frappe.utils import today


class ALHandoverAcceptance(Document):
    """Biên bản nghiệm thu bàn giao - xác nhận hoàn thành & bắt đầu bảo hành."""

    def validate(self):
        if self.acceptance_status in ("ACCEPTED", "ACCEPTED_WITH_PUNCHLIST"):
            if not self.warranty_start_date:
                self.warranty_start_date = self.handover_date or today()

    def on_update(self):
        old = self.get_doc_before_save()
        if old and self.acceptance_status != old.acceptance_status:
            if self.acceptance_status in ("ACCEPTED", "ACCEPTED_WITH_PUNCHLIST"):
                if self.installation_order:
                    frappe.db.set_value(
                        "AL Installation Order", self.installation_order,
                        "status", "Completed"
                    )
