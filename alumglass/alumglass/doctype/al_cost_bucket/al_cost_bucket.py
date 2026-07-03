# AL Cost Bucket — Cost accounting buckets for BOM pricing
# Validate bucket_code uniqueness
import frappe
from frappe.model.document import Document


class ALCostBucket(Document):
    def validate(self):
        # bucket_code uniqueness is handled by autoname
        # Prevent circular parent bucket reference
        if self.parent_bucket and self.parent_bucket == self.bucket_code:
            frappe.throw("A Cost Bucket cannot be its own parent")
