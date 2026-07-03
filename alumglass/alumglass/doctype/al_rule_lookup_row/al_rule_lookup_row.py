# AL Rule Lookup Row — Child table of AL Calculation Rule (LOOKUP type)
# Validate no duplicate (key_1, key_2, key_3) combinations within same parent
import frappe
from frappe.model.document import Document


class ALRuleLookupRow(Document):
    def validate(self):
        # Check for duplicate keys within the same parent rule
        if not self.parent:
            return
        existing = frappe.db.sql(
            """
            SELECT COUNT(*) as cnt FROM `tabAL Rule Lookup Row`
            WHERE parent=%s AND key_1=%s AND IFNULL(key_2,'')=IFNULL(%s,'')
            AND IFNULL(key_3,'')=IFNULL(%s,'') AND name!=%s
            """,
            (
                self.parent, self.key_1 or "", self.key_2 or "",
                self.key_3 or "", self.name,
            ),
            as_dict=True,
        )
        if existing and existing[0].cnt > 0:
            frappe.throw(
                f"Duplicate lookup key combination: "
                f"({self.key_1}, {self.key_2}, {self.key_3})"
            )
