# AL Discount Rule Line — Child table of AL Discount Rule (volume tiers)
# Validate min_qty < max_qty if max_qty > 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALDiscountRuleLine(Document):
    def validate(self):
        if flt(self.max_qty) > 0 and flt(self.min_qty) >= flt(self.max_qty):
            frappe.throw(
                f"Min Qty ({self.min_qty}) must be less than Max Qty ({self.max_qty})"
            )
