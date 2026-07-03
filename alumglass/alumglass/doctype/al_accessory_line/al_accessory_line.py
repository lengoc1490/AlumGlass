# AL Accessory Line — Child table of AL Accessory Set (formerly AL PK Line)
# Validate sl_formula is a valid formula expression
import frappe
from frappe.model.document import Document


class ALAccessoryLine(Document):
    def validate(self):
        if not (self.sl_formula or "").strip():
            frappe.throw(
                f"Accessory line '{self.item_code}': SL Formula is required"
            )
