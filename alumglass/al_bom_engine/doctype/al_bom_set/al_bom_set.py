import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import backfill_input_vars


class ALBomSet(Document):
    """Tập hợp Bom Items - định nghĩa cấu trúc sản phẩm.

    Mỗi Bom Set chứa danh sách AL Bom Item, đại diện cho
    toàn bộ vật tư cấu thành 1 sản phẩm (cửa, vách...).
    """

    def validate(self):
        self._validate_slug_uniqueness()
        # V6 Phase 1d: doc_events validate trên child KHÔNG chạy khi parent save
        # (Frappe flush children trực tiếp qua DB) → backfill input_vars ở đây.
        for item in (self.items or []):
            backfill_input_vars(item)

    def _validate_slug_uniqueness(self):
        """Đảm bảo không slug trùng trong cả items và accessory_items."""
        seen = []
        for item in (self.items or []):
            if item.slug:
                if item.slug in seen:
                    frappe.throw(f"Slug '{item.slug}' bị trùng trong Bom Set")
                seen.append(item.slug)
        # Accessory items validated in AL Accessory Set, not here


@frappe.whitelist()
def clone_bom_set(source_code, new_code, new_name):
    """Sao chép Bom Set cùng tất cả items."""
    source = frappe.get_doc("AL Bom Set", source_code)
    new_doc = frappe.copy_doc(source)
    new_doc.set_code = new_code
    new_doc.set_name = new_name
    new_doc.insert()
    return new_doc.name
