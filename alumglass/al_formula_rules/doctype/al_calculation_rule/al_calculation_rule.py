import frappe
from frappe.model.document import Document


class ALCalculationRule(Document):
    """Rule CONSTANT / THRESHOLD / LOOKUP — dùng cho offset, phụ thu giá màu."""

    def validate(self):
        if self.rule_type == "CONSTANT" and self.constant_value is None:
            frappe.throw("CONSTANT rule cần constant_value")
        if self.rule_type == "THRESHOLD":
            if not self.threshold_rows:
                frappe.throw("THRESHOLD rule cần ít nhất 1 dòng")
            self._validate_no_overlap()
        if self.rule_type == "LOOKUP" and not self.lookup_rows:
            frappe.throw("LOOKUP rule cần ít nhất 1 dòng")

    def _validate_no_overlap(self):
        rows = sorted(self.threshold_rows, key=lambda r: r.from_value)
        for i in range(len(rows) - 1):
            if rows[i].to_value > rows[i + 1].from_value:
                frappe.throw(
                    f"Threshold chồng lấp: [{rows[i].from_value}-{rows[i].to_value}] "
                    f"và [{rows[i+1].from_value}-{rows[i+1].to_value}]"
                )

    def resolve(self, input_value):
        """Tra cứu giá trị từ rule. Dùng bởi BomOrchestrator."""
        if self.rule_type == "CONSTANT":
            return self.constant_value
        if self.rule_type == "THRESHOLD":
            for row in self.threshold_rows:
                if row.from_value <= float(input_value) <= row.to_value:
                    return row.result_value
            return None
        if self.rule_type == "LOOKUP":
            for row in self.lookup_rows:
                if str(row.key_field) == str(input_value):
                    return row.result_value
            return None
