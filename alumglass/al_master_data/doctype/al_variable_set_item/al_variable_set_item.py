import frappe
from frappe.model.document import Document

class ALVariableSetItem(Document):
    """Dòng biến trong Variable Set - Link đến AL Variable Library."""
    
    def before_save(self):
        """Auto-fill var_label, var_type, options từ Variable Library."""
        if self.variable:
            lib = frappe.get_cached_doc("AL Variable Library", self.variable)
            self.var_label = lib.var_label or self.variable
            self.var_type = lib.var_type
            self.link_doctype = lib.link_doctype or ""
            self.select_options = lib.select_options or ""
