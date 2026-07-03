# AL Rule Threshold Row — Child table of AL Calculation Rule (THRESHOLD type)
# Validate from_value < to_value (if to_value > 0)
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALRuleThresholdRow(Document):
    def validate(self):
        if flt(self.to_value) > 0 and flt(self.from_value) >= flt(self.to_value):
            frappe.throw(
                f"From Value ({self.from_value}) must be less than To Value ({self.to_value})"
            )
