# AL Cost Template — Cost calculation template with optional Formula Set reference
# P1: Supports formula_set field linking to formula_builder's Formula Set
# Validate: if formula_set is set, al_lines can be empty
import frappe
from frappe.model.document import Document


class ALCostTemplate(Document):
    def validate(self):
        if self.formula_set:
            # Formula Set manages calculation — al_lines optional for display
            return

        # If no Formula Set, must have at least one cost line
        if not self.al_lines or len(self.al_lines) == 0:
            frappe.throw(
                "Cost Template must have at least one Cost Line "
                "or reference a Formula Set"
            )
