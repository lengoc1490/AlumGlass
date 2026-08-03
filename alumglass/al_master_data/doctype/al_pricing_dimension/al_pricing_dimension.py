import frappe
from frappe.model.document import Document


class ALPricingDimension(Document):
    """Đặc tính giá động - tự động sinh Custom Field trên Item Price.

    Tương tự Accounting Dimension: thêm đặc tính mới = 1 record,
    hệ thống tự tạo custom field tương ứng trên Item Price.
    """

    def after_insert(self):
        self._sync_custom_field()

    def on_update(self):
        self._sync_custom_field()

    def _sync_custom_field(self):
        """Tạo hoặc cập nhật Custom Field trên Item Price."""
        if not self.custom_fieldname:
            self.custom_fieldname = f"custom_pd_{self.dimension_code}"
            self.db_update()

        field_def = {
            "fieldname": self.custom_fieldname,
            "label": self.dimension_name,
            "fieldtype": self.dimension_type,
            "insert_after": "price_list_rate",
            "module": "AL Master Data",
        }
        if self.dimension_type == "Link" and self.link_doctype:
            field_def["options"] = self.link_doctype
        elif self.dimension_type == "Select" and self.select_options:
            field_def["options"] = self.select_options

        existing = frappe.db.exists(
            "Custom Field", {"dt": "Item Price", "fieldname": self.custom_fieldname}
        )
        if not existing:
            cf = frappe.new_doc("Custom Field")
            cf.dt = "Item Price"
            cf.update(field_def)
            cf.insert(ignore_permissions=True)
        else:
            frappe.db.set_value(
                "Custom Field", existing, field_def
            )
