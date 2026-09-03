import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import (
    backfill_input_vars, FORMULA_FIELDS, CONDITION_FORMULA_FIELDS)
from alumglass.al_bom_engine.formula_validate import build_known_names, check_formula_fields


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
        self._validate_child_formulas()

    def _validate_slug_uniqueness(self):
        """Đảm bảo không slug trùng trong cả items và accessory_items."""
        seen = []
        for item in (self.items or []):
            if item.slug:
                if item.slug in seen:
                    frappe.throw(f"Slug '{item.slug}' bị trùng trong Bom Set")
                seen.append(item.slug)
        # Accessory items validated in AL Accessory Set, not here

    # ── V6 P10: validate công thức width/height/qty/show_condition/
    #    item_condition_formula của toàn bộ dòng — chặn NGAY khi save Bom Set
    #    thay vì để lộ lỗi lúc chạy BOM thật cho khách hàng. Doctype này
    #    CHƯA có lớp chặn client nào validate cú pháp/biến (chỉ có
    #    autocomplete gõ dễ hơn) → server PHẢI throw cứng (xem
    #    HUONG_DAN_INJECT_VALIDATE.md mục 3.4).
    def _validate_child_formulas(self):
        if not self.items:
            return
        slugs = [i.slug for i in self.items if i.slug]
        # cross_row_fields = MỌI field có thể là target của items.slug.field
        # (chính là FORMULA_FIELDS — đồng bộ với DAG thật của engine, xem
        # bom_orchestrator._normalize_items_ref).
        known_names = build_known_names(
            "AL Bom Set", self.name,
            cross_row_slugs=slugs, cross_row_fields=FORMULA_FIELDS,
        )
        all_errors = []
        for item in self.items:
            errs = check_formula_fields(
                item, FORMULA_FIELDS, known_names, allow_cross_row=True)
            if item.item_selection_mode == "Formula":
                errs += check_formula_fields(
                    item, CONDITION_FORMULA_FIELDS, known_names, allow_cross_row=True)
            if errs:
                all_errors.append(f"Dòng '{item.slug or item.idx}': " + "; ".join(errs))
        if all_errors:
            frappe.throw("Công thức không hợp lệ:\n" + "\n".join(all_errors))


@frappe.whitelist()
def clone_bom_set(source_code, new_code, new_name):
    """Sao chép Bom Set cùng tất cả items."""
    source = frappe.get_doc("AL Bom Set", source_code)
    new_doc = frappe.copy_doc(source)
    new_doc.set_code = new_code
    new_doc.set_name = new_name
    new_doc.insert()
    return new_doc.name
