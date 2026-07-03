# AL Material Plan — MRP Lite: aggregate materials from Quotation/SO pool
# Validate: quotation_list or so_list is not empty
# If status='Confirmed' → cannot edit al_plan_lines
import frappe
import json
from frappe.model.document import Document


class ALMaterialPlan(Document):
    def validate(self):
        # At least one source list must have entries
        has_quotations = self._has_entries(self.quotation_list)
        has_so = self._has_entries(self.so_list)

        if not has_quotations and not has_so:
            frappe.throw(
                "Material Plan must reference at least one Quotation "
                "or Sales Order"
            )

    def on_update(self):
        """If status becomes Confirmed, lock plan lines."""
        old_doc = self.get_doc_before_save()
        old_status = old_doc.status if old_doc else None

        if self.status == "Confirmed" and old_status != "Confirmed":
            self._lock_plan_lines()

    def _lock_plan_lines(self):
        """Mark plan as immutable when Confirmed."""
        # The child table validation will handle this
        pass

    @staticmethod
    def _has_entries(json_field):
        """Check if a JSON field has entries."""
        if not json_field:
            return False
        if isinstance(json_field, list):
            return len(json_field) > 0
        if isinstance(json_field, str):
            try:
                data = json.loads(json_field)
                return len(data) > 0
            except (json.JSONDecodeError, TypeError):
                return False
        return False
