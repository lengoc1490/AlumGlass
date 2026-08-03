import frappe
from frappe.model.document import Document


class ALDynamicItemRule(Document):
    """Rule chọn Item động theo THRESHOLD hoặc LOOKUP.

    VD: chọn nẹp kính theo độ dày kính, chọn keo theo loại kính.
    """

    def validate(self):
        if self.rule_type == "THRESHOLD":
            if not self.threshold_rows:
                frappe.throw("THRESHOLD rule cần ít nhất 1 dòng")
            self._validate_threshold_rows()
        if self.rule_type == "LOOKUP":
            if not self.lookup_rows:
                frappe.throw("LOOKUP rule cần ít nhất 1 dòng")

    def _validate_threshold_rows(self):
        rows = sorted(self.threshold_rows, key=lambda r: r.from_value)
        for i, row in enumerate(rows):
            if not row.result_item:
                frappe.throw(f"Threshold row {i+1}: cần Result Item")
            if row.from_value > row.to_value:
                frappe.throw(f"Threshold row {i+1}: from > to")
        for i in range(len(rows) - 1):
            if rows[i].to_value >= rows[i + 1].from_value:
                frappe.throw(
                    f"Threshold chồng lấp: [{rows[i].from_value}-{rows[i].to_value}]"
                )

    def resolve(self, input_value):
        """Tra cứu Item code từ input value."""
        if input_value is None or input_value == "":
            return None
        if self.rule_type == "THRESHOLD":
            try:
                val = float(input_value)
            except (ValueError, TypeError):
                return None
            for row in self.threshold_rows:
                if row.from_value <= val <= row.to_value:
                    return row.result_item
        if self.rule_type == "LOOKUP":
            for row in self.lookup_rows:
                if str(row.key_field) == str(input_value):
                    return row.result_item
        return None


@frappe.whitelist()
def resolve_item(rule_code, input_value):
    """API: Tra cứu Item từ rule. Trả về {item_code, item_name}."""
    doc = frappe.get_cached_doc("AL Dynamic Item Rule", rule_code)
    result = doc.resolve(input_value)
    if result:
        return {
            "item_code": result,
            "item_name": frappe.db.get_value("Item", result, "item_name"),
        }
    return None
