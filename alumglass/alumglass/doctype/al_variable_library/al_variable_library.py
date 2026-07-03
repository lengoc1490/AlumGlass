# AL Variable Library — Global variable definitions with UI widget config
# Validate var_code is unique
import frappe
from frappe.model.document import Document


class ALVariableLibrary(Document):
    def validate(self):
        # var_code uniqueness is handled by autoname, but we also validate
        # that it follows naming conventions (no spaces, valid identifier)
        if self.var_code and " " in self.var_code:
            frappe.throw("Variable Code cannot contain spaces")
        if self.var_code and not self.var_code.replace("_", "").isalnum():
            frappe.throw("Variable Code can only contain letters, numbers, and underscores")
