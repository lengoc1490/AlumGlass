# AL Product Type — Product categories (SwingDoor, Window, SlidingDoor, TiltAndTurnDoor, Partition)
# Validate nc_pct >= 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALProductType(Document):
    def validate(self):
        if flt(self.nc_pct) < 0:
            frappe.throw("NC Production (%) cannot be negative")
