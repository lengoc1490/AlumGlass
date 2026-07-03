# ConfigSnapshot — Immutable audit trail of BOM calculation
# Validate enterprise_snapshot_json is valid JSON
import frappe
import json
from frappe.model.document import Document


class ConfigSnapshot(Document):
    def validate(self):
        if self.enterprise_snapshot_json:
            try:
                json.loads(self.enterprise_snapshot_json)
            except (json.JSONDecodeError, TypeError) as e:
                frappe.throw(
                    f"Enterprise Snapshot JSON is invalid: {str(e)}"
                )

    def on_trash(self):
        """Prevent deletion of snapshots referenced by Quotation Items."""
        # Check if any Quotation Item references this snapshot
        refs = frappe.db.count(
            "Quotation Item",
            {"al_config_snapshot": self.name},
        )
        if refs > 0:
            frappe.throw(
                f"Cannot delete ConfigSnapshot '{self.name}'. "
                f"It is referenced by {refs} Quotation Item(s)."
            )
