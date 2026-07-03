# AL BOM Version — Immutable snapshot of BOM configuration at publish time
# - When status='Published': IMMUTABLE — no edits allowed to snapshot fields
# - Auto-calculate snapshot_hash (SHA-256) before insert
import frappe
import json
import hashlib
from frappe.model.document import Document
from frappe.utils import now


class ALBOMVersion(Document):
    def before_insert(self):
        """Auto-calculate snapshot_hash before insert."""
        if not self.snapshot_hash:
            self.snapshot_hash = self._compute_hash()

    def on_update(self):
        """Handle status changes.

        When status becomes 'Published':
          - Set published_on and published_by
          - Make document immutable
          - Update parent BOM's current_version
        """
        old_doc = self.get_doc_before_save()
        old_status = old_doc.status if old_doc else None

        if self.status == "Published" and old_status != "Published":
            self.published_on = now()
            self.published_by = frappe.session.user

            # Update BOM's current_version
            frappe.db.set_value(
                "AL BOM", self.bom, "current_version", self.name
            )
            frappe.db.set_value(
                "AL BOM", self.bom, "last_published_on", now()
            )
            # Increment total_versions
            total = frappe.db.count(
                "AL BOM Version",
                {"bom": self.bom, "status": "Published"},
            )
            frappe.db.set_value(
                "AL BOM", self.bom, "total_versions", total
            )

    def validate(self):
        """Prevent editing snapshot fields when Published."""
        if self.status == "Published":
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.status == "Published":
                # Check if snapshot fields have changed
                immutable_fields = [
                    "profile_set_snapshot", "variable_set_snapshot",
                    "accessory_set_snapshot", "cost_template_snapshot",
                    "snapshot_hash",
                ]
                for field in immutable_fields:
                    old_val = getattr(old_doc, field, None)
                    new_val = getattr(self, field, None)
                    if old_val != new_val:
                        frappe.throw(
                            f"Cannot modify '{field}' on a Published BOM Version. "
                            f"Published versions are immutable."
                        )

        # Recalculate hash if snapshot data changed
        if not self.snapshot_hash or self.has_snapshot_changed():
            self.snapshot_hash = self._compute_hash()

    def has_snapshot_changed(self):
        """Check if any snapshot field has changed."""
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return True
        snapshot_fields = [
            "profile_set_snapshot", "variable_set_snapshot",
            "accessory_set_snapshot", "cost_template_snapshot",
        ]
        for field in snapshot_fields:
            if getattr(old_doc, field, None) != getattr(self, field, None):
                return True
        return False

    def _compute_hash(self):
        """Compute SHA-256 hash of all snapshots."""
        payload = json.dumps({
            "profile_set": self.profile_set_snapshot or "",
            "variable_set": self.variable_set_snapshot or "",
            "accessory_set": self.accessory_set_snapshot or "",
            "cost_template": self.cost_template_snapshot or "",
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()
