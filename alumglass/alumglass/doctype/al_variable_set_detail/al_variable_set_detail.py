# AL Variable Set Detail — Child table of AL Variable Set
# Validate variable is not duplicated within the same Set
import frappe
from frappe.model.document import Document


class ALVariableSetDetail(Document):
    def validate(self):
        if not self.variable:
            return
        # Check for duplicate variables within the same parent Set
        existing = frappe.db.sql(
            """
            SELECT COUNT(*) as cnt FROM `tabAL Variable Set Detail`
            WHERE parent=%s AND variable=%s AND name!=%s
            """,
            (self.parent, self.variable, self.name),
            as_dict=True,
        )
        if existing and existing[0].cnt > 0:
            frappe.throw(
                f"Variable '{self.variable}' already exists in this Variable Set"
            )
