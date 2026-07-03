# AL Alert Config — Alert configuration for notifications
# Validate threshold_value > 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALAlertConfig(Document):
    def validate(self):
        if flt(self.threshold_value) <= 0:
            frappe.throw("Threshold Value must be greater than 0")
