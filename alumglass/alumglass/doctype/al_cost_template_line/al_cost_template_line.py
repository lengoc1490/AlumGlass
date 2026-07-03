# AL Cost Template Line — Child table of AL Cost Template
# Validate calc_formula not empty if parent has no formula_set
import frappe
from frappe.model.document import Document


class ALCostTemplateLine(Document):
    def validate(self):
        # Check if parent has formula_set
        if self.parent:
            has_formula_set = frappe.db.get_value(
                "AL Cost Template", self.parent, "formula_set"
            )
            if not has_formula_set and not (self.calc_formula or "").strip():
                frappe.throw(
                    f"Line '{self.line_code or self.line_label}': "
                    "calc_formula is required when Cost Template has no Formula Set"
                )
