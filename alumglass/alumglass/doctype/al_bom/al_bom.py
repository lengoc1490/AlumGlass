# AL BOM — Central BOM linking Variable Set, Profile Set, Accessory Set, Cost Template
# Validate: variable_set, profile_set, default_cost_template are not empty
# Validate: when current_version changes, the version must have status='Published'
import frappe
from frappe.model.document import Document


class ALBOM(Document):
    def validate(self):
        if not self.variable_set:
            frappe.throw("Variable Set is required")

        if not self.profile_set:
            frappe.throw("Profile Set is required")

        if not self.default_cost_template:
            frappe.throw("Default Cost Template is required")

    def on_update(self):
        """Track version changes."""
        old_doc = self.get_doc_before_save()
        if old_doc:
            old_version = old_doc.current_version
            new_version = self.current_version
            if old_version != new_version and new_version:
                # Validate the new version is Published
                status = frappe.db.get_value(
                    "AL BOM Version", new_version, "status"
                )
                if status != "Published":
                    frappe.throw(
                        f"Cannot set current_version to '{new_version}'. "
                        f"The version must have status='Published' (current: {status})."
                    )
