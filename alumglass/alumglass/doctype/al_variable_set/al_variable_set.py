# AL Variable Set — Groups variables for a specific BOM type
# Validate at least 1 detail row exists
import frappe
from frappe.model.document import Document


class ALVariableSet(Document):
    def validate(self):
        if not self.al_var_details or len(self.al_var_details) == 0:
            frappe.throw("Variable Set must have at least one Variable Detail row")
