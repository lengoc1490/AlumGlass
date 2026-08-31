import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.formula_validate import build_known_names, check_formula


class ALAlertConfig(Document):
    """AL Alert Config — trigger_condition quyết định khi nào bắn cảnh báo."""

    def validate(self):
        known_names = build_known_names("AL Alert Config", self.name)
        errs = check_formula(self.get("trigger_condition"), known_names,
                              label="Trigger Condition")
        if errs:
            frappe.throw("\n".join(errs))
