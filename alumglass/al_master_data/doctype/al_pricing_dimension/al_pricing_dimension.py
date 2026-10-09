import re

import frappe
from frappe.model.document import Document

# MySQL giới hạn tên cột 64 ký tự; Frappe (CustomField.set_fieldname) cũng chỉ
# nhận fieldname chữ thường / số / gạch dưới, bắt đầu bằng chữ.
_FIELDNAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_FIELDNAME_MAX_LEN = 64


class ALPricingDimension(Document):

    def validate(self):
        # F15: `custom_fieldname` là TÊN CỘT thật trên tabItem Price (sinh tự
        # động từ dimension_code khi để trống). Chặn ngay ở validate để lỗi hiện
        # ra lúc save, thay vì để MySQL/Frappe nổ ở tầng ALTER TABLE với thông
        # báo khó hiểu.
        self._validate_custom_fieldname()

    def after_insert(self):
        self._sync_custom_field()

    def on_update(self):
        self._sync_custom_field()

    def _effective_custom_fieldname(self):
        """Tên cột sẽ dùng: field người dùng khai, hoặc sinh từ dimension_code."""
        if self.custom_fieldname:
            return self.custom_fieldname
        if not self.dimension_code:
            return ""
        return f"custom_pd_{self.dimension_code.lower()}"

    def _validate_custom_fieldname(self):
        name = self._effective_custom_fieldname()
        if not name:
            frappe.throw(
                "Cần Dimension Code (hoặc khai Custom Fieldname) để sinh tên "
                "field trên Item Price."
            )
        if not _FIELDNAME_RE.match(name):
            frappe.throw(
                f"Tên field '{name}' không hợp lệ — chỉ nhận chữ thường, số và "
                f"gạch dưới, bắt đầu bằng chữ cái. Sửa Dimension Code "
                f"'{self.dimension_code}' hoặc khai Custom Fieldname thủ công."
            )
        if len(name) > _FIELDNAME_MAX_LEN:
            frappe.throw(
                f"Tên field '{name}' dài {len(name)} ký tự — MySQL chỉ cho tối đa "
                f"{_FIELDNAME_MAX_LEN} ký tự cho tên cột. Rút ngắn Dimension Code "
                f"hoặc khai Custom Fieldname ngắn hơn."
            )

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
            self.custom_fieldname = self._effective_custom_fieldname()
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
            # F15: PHẢI đi qua doc API. `frappe.db.set_value` ghi thẳng bảng
            # Custom Field nên KHÔNG chạy `CustomField.on_update` ⇒ không
            # `frappe.db.updatedb("Item Price")` ⇒ đổi dimension_type (Data →
            # Select/Link…) chỉ đổi METADATA, kiểu cột trong DB giữ nguyên bản
            # cũ — lệch âm thầm cho tới lần migrate sau. `save()` chạy đủ
            # validate + clear_cache + updatedb (⇒ ALTER TABLE đúng kiểu).
            cf = frappe.get_doc("Custom Field", existing)
            cf.update(field_def)
            # Đổi sang loại field không dùng `options` → xoá options cũ, tránh
            # để lại danh sách Select/Link mồ côi trong metadata.
            if not field_def.get("options"):
                cf.options = None
            cf.flags.ignore_permissions = True
            cf.save()

        frappe.clear_cache(doctype="Item Price")