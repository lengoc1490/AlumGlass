# AL Glass Layer Line — Child table of AL Glass Master (Phase 3)
# Validate thickness_mm > 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALGlassLayerLine(Document):
    def validate(self):
        if flt(self.thickness_mm) <= 0:
            frappe.throw("Layer Thickness (mm) must be greater than 0")
