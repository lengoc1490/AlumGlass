# AL Dashboard Config — Dashboard widget configuration per role
# Validate widgets is valid JSON
import frappe
import json
from frappe.model.document import Document


class ALDashboardConfig(Document):
    def validate(self):
        if self.widgets:
            try:
                data = json.loads(self.widgets) if isinstance(self.widgets, str) else self.widgets
                if not isinstance(data, list):
                    frappe.throw("Widgets must be a JSON array")
            except (json.JSONDecodeError, TypeError) as e:
                frappe.throw(f"Widgets JSON is invalid: {str(e)}")
