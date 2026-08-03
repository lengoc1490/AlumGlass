import frappe
from frappe.model.document import Document


class ALVariableDimensionMapping(Document):
    """Maps input variable → pricing dimension + material category.

    Dùng bởi aluminum_price_composite handler để khám phá
    composite key động khi tra giá Item Price.
    """
    pass
