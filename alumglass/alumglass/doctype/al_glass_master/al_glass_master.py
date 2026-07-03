# AL Glass Master — Technical specs for glass products
# Validate total_thick_mm > 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALGlassMaster(Document):
    def validate(self):
        if flt(self.total_thick_mm) <= 0:
            frappe.throw("Total Thickness (mm) must be greater than 0")
