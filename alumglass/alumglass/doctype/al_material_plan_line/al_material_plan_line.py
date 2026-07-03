# AL Material Plan Line — Child table of AL Material Plan
# Validate total_qty_net >= 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALMaterialPlanLine(Document):
    def validate(self):
        if flt(self.total_qty_net) < 0:
            frappe.throw(
                f"Total Qty (Net) for '{self.item_code}' cannot be negative"
            )
