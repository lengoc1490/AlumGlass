# AL Calculation Rule — Calculation rules for BOM engine
# Only THRESHOLD and LOOKUP retained (CONSTANT/FORMULA/SEQUENCE → Formula Global Variable/Formula Set)
# Validate: THRESHOLD → must have threshold_rows, LOOKUP → must have lookup_rows
import frappe
from frappe.model.document import Document


class ALCalculationRule(Document):
    def validate(self):
        if self.rule_type == "THRESHOLD":
            if not self.threshold_rows or len(self.threshold_rows) == 0:
                frappe.throw(
                    "THRESHOLD rule must have at least one Threshold Row"
                )
            if not self.threshold_input_var:
                frappe.throw(
                    "THRESHOLD rule must specify threshold_input_var"
                )

        if self.rule_type == "LOOKUP":
            if not self.lookup_rows or len(self.lookup_rows) == 0:
                frappe.throw(
                    "LOOKUP rule must have at least one Lookup Row"
                )
