import frappe, json
from frappe.model.document import Document


class ALCostBucket(Document):
    """Tài khoản chi phí với data source config.

    Mỗi bucket định nghĩa NGUỒN DỮ LIỆU và CÁCH TÍNH.
    Thêm bucket mới = 1 record, 0 dòng code.
    """

    VALID_SOURCE_TYPES = [
        "aggregate_from_items", "formula", "doctype_query",
        "custom_function", "constant", "pipeline",
        "conditional", "fallback_chain"
    ]

    def validate(self):
        self._validate_source_config()

    def _validate_source_config(self):
        if self.source_type not in self.VALID_SOURCE_TYPES:
            frappe.throw(f"source_type '{self.source_type}' không hợp lệ")

        if self.source_config:
            try:
                cfg = json.loads(self.source_config) if isinstance(
                    self.source_config, str
                ) else self.source_config
            except (json.JSONDecodeError, TypeError):
                frappe.throw("source_config phải là JSON hợp lệ")

            if self.source_type == "doctype_query":
                if not cfg.get("doctype"):
                    frappe.throw("doctype_query cần 'doctype' trong source_config")
                if not cfg.get("fieldname"):
                    frappe.throw("doctype_query cần 'fieldname' trong source_config")

            if self.source_type == "aggregate_from_items":
                if not cfg.get("sum_field"):
                    frappe.throw("aggregate_from_items cần 'sum_field'")

            if self.source_type == "pipeline" and not cfg.get("steps"):
                frappe.throw("pipeline cần 'steps'")

            if self.source_type == "fallback_chain" and not cfg.get("chain"):
                frappe.throw("fallback_chain cần 'chain'")

        if self.depends_on:
            try:
                deps = json.loads(self.depends_on) if isinstance(
                    self.depends_on, str
                ) else self.depends_on
                if not isinstance(deps, list):
                    frappe.throw("depends_on phải là JSON array")
            except (json.JSONDecodeError, TypeError):
                frappe.throw("depends_on phải là JSON array hợp lệ")
