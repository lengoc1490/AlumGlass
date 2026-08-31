import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.formula_validate import build_known_names, check_formula_fields

# V6 P10: field công thức trên AL Accessory Item — trước bản vá này KHÔNG
# có autocomplete lẫn validate (doctype + child đều "pass" trơn).
ACCESSORY_FORMULA_FIELDS = ("qty_formula",)


class ALAccessorySet(Document):
    """AL Accessory Set — bộ phụ kiện (tay nắm, khóa, bản lề...) nạp vào BOM
    dưới cost_bucket VL_PK mặc định (override được per-item, xem
    bom_orchestrator._load_accessories())."""

    def validate(self):
        self._validate_item_formulas()

    def _validate_item_formulas(self):
        if not self.items:
            return
        # AL Accessory Set KHÔNG có variable_set riêng — dùng đúng cùng
        # nguồn biến toàn cục (Cost Bucket/System Var/Formula Global Var)
        # như mọi doctype khác qua get_formula_context. Không cross-row
        # (phụ kiện không tham chiếu items.slug.field).
        known_names = build_known_names("AL Accessory Set", self.name)
        all_errors = []
        for item in self.items:
            errs = check_formula_fields(item, ACCESSORY_FORMULA_FIELDS, known_names)
            if errs:
                all_errors.append(f"Dòng '{item.slug or item.idx}': " + "; ".join(errs))
        if all_errors:
            frappe.throw("Công thức không hợp lệ:\n" + "\n".join(all_errors))
