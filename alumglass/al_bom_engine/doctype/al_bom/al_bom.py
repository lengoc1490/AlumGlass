import frappe
from frappe.model.document import Document


class ALBOM(Document):
    """BOM - liên kết Bom Set + Cost Template + Accessory Set."""

    def validate(self):
        if self.bom_set and not frappe.db.exists("AL Bom Set", self.bom_set):
            frappe.throw(f"BOM Set '{self.bom_set}' không tồn tại")
        if self.default_cost_template and not frappe.db.exists(
            "AL Cost Template", self.default_cost_template
        ):
            frappe.throw(f"Cost Template '{self.default_cost_template}' không tồn tại")


@frappe.whitelist()
def get_bom_structure(bom_code):
    """Trả về toàn bộ cấu trúc BOM."""
    bom = frappe.get_doc("AL BOM", bom_code)
    bom_set = frappe.get_doc("AL Bom Set", bom.bom_set)
    return {
        "bom": bom.as_dict(),
        "bom_set": bom_set.as_dict(),
        "items": [item.as_dict() for item in bom_set.items],
    }
