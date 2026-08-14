import frappe
from frappe.model.document import Document

class ALPricingDimension(Document):

    def after_insert(self):
        self._sync_custom_field()

    def on_update(self):
        self._sync_custom_field()

    def _ensure_section_and_columns(self):
        """Tạo Pricing Dimension Section + Column Break nếu chưa có"""
        meta = frappe.get_meta("Item Price", cached=False)
        fieldnames = [d.fieldname for d in meta.fields]

        # 1. Section
        if "pricing_dimension_section" not in fieldnames:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Item Price",
                "fieldname": "pricing_dimension_section",
                "label": "Pricing Dimensions",
                "fieldtype": "Section Break",
                "insert_after": "price_list_rate",
            }).insert(ignore_permissions=True)

        # 2. Column Break
        if "pricing_dimension_col_break" not in fieldnames:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Item Price",
                "fieldname": "pricing_dimension_col_break",
                "fieldtype": "Column Break",
                "insert_after": "pricing_dimension_section",
            }).insert(ignore_permissions=True)

        frappe.clear_cache(doctype="Item Price")

    def _sync_custom_field(self):
        """Tạo hoặc update Custom Field chuẩn 2 cột"""

        self._ensure_section_and_columns()

        if not self.custom_fieldname:
            self.custom_fieldname = f"custom_pd_{self.dimension_code.lower()}"
            self.db_update()

        meta = frappe.get_meta("Item Price", cached=False)

        # 🔑 lấy các field pricing dimension đã tồn tại
        pd_fields = [
            df for df in meta.fields
            if df.fieldname.startswith("custom_pd_")
        ]

        # 🔑 quyết định vị trí chèn (giống core)
        if len(pd_fields) % 2 == 0:
            insert_after = "pricing_dimension_section"
        else:
            insert_after = "pricing_dimension_col_break"

        field_def = {
            "fieldname": self.custom_fieldname,
            "label": self.dimension_name,
            "fieldtype": self.dimension_type,
            "insert_after": insert_after,
            "module": "AL Master Data",
        }

        if self.dimension_type == "Link" and self.link_doctype:
            field_def["options"] = self.link_doctype

        elif self.dimension_type == "Select" and self.select_options:
            field_def["options"] = self.select_options

        existing = frappe.db.exists(
            "Custom Field",
            {"dt": "Item Price", "fieldname": self.custom_fieldname}
        )

        if not existing:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Item Price",
                **field_def
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Custom Field", existing, field_def)

        frappe.clear_cache(doctype="Item Price")