# AL Discount Rule — Structured discount rules applied AFTER BOM pricing
# Validate: valid_from < valid_to
# Validate: if requires_approval=1 then approval_threshold_pct > 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class ALDiscountRule(Document):
    def validate(self):
        if self.valid_from and self.valid_to:
            if getdate(self.valid_from) >= getdate(self.valid_to):
                frappe.throw(
                    "Valid From date must be before Valid To date"
                )

        if self.requires_approval and flt(self.approval_threshold_pct) <= 0:
            frappe.throw(
                "When 'Requires Approval' is checked, "
                "Approval Threshold (%) must be greater than 0"
            )
