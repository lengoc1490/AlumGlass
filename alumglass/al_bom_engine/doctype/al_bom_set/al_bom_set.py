import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import (
    backfill_input_vars, FORMULA_FIELDS, CONDITION_FORMULA_FIELDS,
    ENGINE_SYNTHETIC_FIELDS)
from alumglass.al_bom_engine.formula_validate import (
    build_known_names, check_formula_fields, validate_rule_input_expr)


def _rule_input_known_fields():
    """Field mà engine nạp cho mỗi dòng (row literal) — đọc từ DỮ LIỆU.

    Nguồn: `AL Variable Settings.row_literals` qua helper `get_row_literal_names`
    của module catalog (cùng nguồn với adapter `row_literal`) — ⛔ KHÔNG
    hardcode danh sách tên trong file này.

    Helper chưa có (DEV1 chưa merge / site chưa migrate) ⇒ trả `()`; caller
    coi như "không kiểm field" (chỉ kiểm slug), ⛔ KHÔNG fallback danh sách
    cứng — thà cảnh báo thiếu còn hơn cảnh báo sai.
    """
    try:
        from alumglass.api.variable_catalog import get_row_literal_names
        return tuple(get_row_literal_names() or ())
    except Exception:
        return ()


def _cross_row_known_fields():
    """Superset field có thể là target của `items.<slug>.<field>` khi validate.

    ⚠ Đây là `cross_row_fields` truyền cho `build_known_names` — tức tập
    `{slug}__{field}` được coi là biến HỢP LỆ. Nó PHẢI phủ đúng những gì
    engine B3 thật sự inject cho mỗi dòng (`bom_orchestrator.b3_build_formulas`),
    nếu không công thức chạy tốt lúc runtime vẫn bị `validate` chặn oan
    ("Biến không khai báo"). Gồm 3 nguồn:

      1. `FORMULA_FIELDS` — field công thức tham gia DAG cross-row.
      2. Row literal đang bật trong `AL Variable Settings.row_literals`
         (`weight_per_unit`, `unit_price`, `glass_thick`, `glass_type`,
         `scrap_pct`, `calc_pattern`...) — đọc từ DỮ LIỆU qua
         `_rule_input_known_fields`, ⛔ KHÔNG hardcode tên ở đây. Rỗng
         (site chưa migrate / thiếu helper) ⇒ bỏ qua nguồn này.
      3. `ENGINE_SYNTHETIC_FIELDS` — `unit_qty`/`total_qty`/`line_total` do
         engine tạo cho MỌI dòng; là hợp đồng engine (xem al_bom_item.py),
         ⛔ không phải cấu hình người dùng nên không đọc từ Settings.

    ⚠ Superset này CHỈ nới `known_names` cho validate — nó KHÔNG làm field lạ
    chạy được lúc runtime: field không được engine inject vẫn ra 0, nên
    ⛔ vẫn không nên khai vào `cross_row.fields` (tài liệu đã cảnh báo).
    """
    fields = set(FORMULA_FIELDS) | set(ENGINE_SYNTHETIC_FIELDS)
    fields |= set(_rule_input_known_fields())
    return tuple(sorted(fields))


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
        # Cảnh báo (không chặn) tham chiếu chéo dòng trong rule_input_expr —
        # vùng "gõ được nhưng chưa từng được kiểm" (xem docstring hàm).
        self._warn_rule_input_expr()

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
        # cross_row_fields = MỌI field có thể là target của items.slug.field —
        # SUPERSET của FORMULA_FIELDS: FORMULA_FIELDS (DAG cross-row, đồng bộ
        # với bom_orchestrator._normalize_items_ref) + row literal đang bật
        # (AL Variable Settings) + synthetic unit_qty/total_qty/line_total.
        # Xem _cross_row_known_fields(): đây chỉ là universe biến HỢP LỆ cho
        # validate, không phải danh sách field bị validate chính (vẫn là
        # FORMULA_FIELDS ở check_formula_fields bên dưới).
        known_names = build_known_names(
            "AL Bom Set", self.name,
            cross_row_slugs=slugs, cross_row_fields=_cross_row_known_fields(),
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

    def _warn_rule_input_expr(self):
        """Cảnh báo (KHÔNG throw) `items.<slug>.<field>` trong rule_input_expr.

        `rule_input_expr` KHÔNG đi qua FormulaValidator (không phải biểu thức
        toán học) — engine chỉ parse bằng regex rồi tra row_literals/
        glass_data của dòng đích. Trước đây gõ sai slug/field vẫn save được và
        engine trả 0 ÂM THẦM. Nay hiện cảnh báo cam để người cấu hình sửa,
        nhưng vẫn KHÔNG chặn — nhiều Bom Set đang chạy có thể đang ở trạng
        thái này, chặn cứng sẽ khoá dữ liệu cũ (spec: warn, not throw).
        Danh sách field hợp lệ lấy từ `AL Variable Settings.row_literals`
        (xem `_rule_input_known_fields`) — KHÔNG hardcode ở đây.
        """
        if not self.items:
            return
        slugs = {i.slug for i in self.items if i.slug}
        # Danh sách field đọc từ AL Variable Settings (xem _rule_input_known_fields).
        # Rỗng ⇒ None = chỉ kiểm slug, không cảnh báo field (tránh cảnh báo oan).
        known_fields = _rule_input_known_fields() or None
        warnings = []
        for item in self.items:
            # Engine CHỈ đọc rule_input_expr khi dòng chọn mã theo Rule
            # (item_selection_mode == "Rule") — các dòng khác cảnh báo là nhiễu.
            if item.item_selection_mode != "Rule":
                continue
            errs = validate_rule_input_expr(
                getattr(item, "rule_input_expr", ""), slugs, known_fields)
            if errs:
                warnings.append(
                    f"Dòng '{item.slug or item.idx}': " + "; ".join(errs))
        if warnings:
            frappe.msgprint(
                "Tham chiếu trong Rule Input có thể cho kết quả 0:\n"
                + "\n".join(warnings),
                title="AL Bom Set — Cảnh báo Rule Input",
                indicator="orange",
            )


@frappe.whitelist()
def clone_bom_set(source_code, new_code, new_name):
    """Sao chép Bom Set cùng tất cả items."""
    source = frappe.get_doc("AL Bom Set", source_code)
    new_doc = frappe.copy_doc(source)
    new_doc.set_code = new_code
    new_doc.set_name = new_name
    new_doc.insert()
    return new_doc.name
