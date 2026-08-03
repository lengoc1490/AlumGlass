import frappe
from frappe.model.document import Document


class ALChangeOrder(Document):
    """Phát sinh có duyệt - mọi thay đổi phạm vi sau chốt hợp đồng phải qua đây."""

    def validate(self):
        if self.workflow_state == "Approved":
            if not self.customer_approval:
                frappe.throw("Cần khách hàng phê duyệt")
            if not self.internal_approval:
                frappe.throw("Cần phê duyệt nội bộ")


@frappe.whitelist()
def get_pending_changes(project):
    return frappe.get_all("AL Change Order",
        filters={"project": project, "workflow_state": ("in", ["Draft","Pending","Approved"])},
        fields=["change_code","change_type","impact_cost","impact_schedule_days","workflow_state"],
        order_by="request_date DESC")
