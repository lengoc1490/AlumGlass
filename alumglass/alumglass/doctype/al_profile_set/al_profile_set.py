# AL Profile Set — Unified table of material lines (Aluminum/Glass/Consumable/Accessory)
# Validate at least 1 line with line_type='Glass' exists
import frappe
from frappe.model.document import Document


class ALProfileSet(Document):
    def validate(self):
        if not self.al_lines or len(self.al_lines) == 0:
            frappe.throw("Profile Set must have at least one Profile Line")

        # At least one Glass line required (for glass_thick injection)
        has_glass = any(
            line.line_type == "KINH" for line in self.al_lines
        )
        if not has_glass:
            frappe.throw(
                "Profile Set must have at least one Glass (KINH) line"
            )
