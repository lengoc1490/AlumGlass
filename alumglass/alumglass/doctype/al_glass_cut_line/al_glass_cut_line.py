# AL Glass Cut Line — Child table of AL Glass Cut Order (Phase 3)
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALGlassCutLine(Document):
    def before_save(self):
        """Auto-calculate area_m2."""
        if self.width_mm and self.height_mm:
            self.area_m2 = round(
                (flt(self.width_mm) * flt(self.height_mm) / 1_000_000)
                * flt(self.quantity),
                3,
            )
