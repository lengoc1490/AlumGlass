import frappe
from frappe.model.document import Document
from frappe.utils import today


class ALSupplierPriceList(Document):
    """Bảng giá nhà cung cấp."""

    def validate(self):
        if self.expiry_date and self.effective_date:
            if self.expiry_date < self.effective_date:
                frappe.throw("Ngày hết hạn không thể trước ngày hiệu lực")

    def before_save(self):
        if self.expiry_date and str(self.expiry_date) < str(today()):
            self.status = "Expired"
        elif not self.status or self.status == "Expired":
            self.status = "Active"
