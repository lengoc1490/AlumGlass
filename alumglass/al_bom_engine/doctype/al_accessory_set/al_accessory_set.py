import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import (
    ENGINE_SYNTHETIC_FIELDS)
from alumglass.al_bom_engine.formula_validate import (
    build_known_names, check_formula_fields, load_rule_meta, lookup_rule_codes,
    row_reference_label, validate_lookup_rule_codes)

# V6 P10: field công thức trên AL Accessory Item — trước bản vá này KHÔNG
# có autocomplete lẫn validate (doctype + child đều "pass" trơn).
ACCESSORY_FORMULA_FIELDS = ("qty_formula",)

# Fallback CUỐI khi không đọc được meta/helper (hiếm: site chưa migrate) —
# đúng các field engine nạp cho dòng phụ kiện ở b3_build_formulas. ⛔ Chỉ là
# lưới an toàn: nguồn chính là meta của `AL Accessory Item`.
# 3 synthetic `unit_qty/total_qty/line_total` KHÔNG phải field của meta (engine
# tự tạo) nên phải có mặt ở đây, xem _cross_row_fields().
_FALLBACK_CROSS_ROW_FIELDS = ("qty", "unit_price", "calc_pattern",
                              "qty_formula")


def _with_synthetic(fields):
    """Hợp `fields` với `ENGINE_SYNTHETIC_FIELDS`, giữ thứ tự, bỏ trùng."""
    out = list(fields)
    for name in ENGINE_SYNTHETIC_FIELDS:
        if name not in out:
            out.append(name)
    return tuple(out)


def _cross_row_fields():
    """Field có thể tham chiếu chéo dòng `items.<slug>.<field>` cho phụ kiện.

    Lấy từ META của `AL Accessory Item` (không hardcode danh sách) — nguồn
    chính — rồi HỢP với `ENGINE_SYNTHETIC_FIELDS` (`unit_qty`, `total_qty`,
    `line_total`). Engine B3 (`bom_orchestrator.b3_build_formulas`) LUÔN tạo 3
    khoá `{slug}__{field}` synthetic này cho MỌI dòng — kể cả dòng phụ kiện
    (`_load_accessories` append vào `bom_items`) — nên chúng KHÔNG bao giờ có
    trong meta mà vẫn là biến hợp lệ lúc runtime. Thiếu chúng ở đây = công
    thức `items.<slug>.total_qty` chạy đúng vẫn bị chặn oan "Biến không khai
    báo" (đúng ca seed profile `P_ACCESSORY_DEFAULT` gợi ý `total_qty`/
    `line_total`).

    Danh sách theo meta là PERMISSIVE có chủ đích: field không được engine nạp
    chỉ cho ra 0 lúc chạy, còn validate thì không chặn oan người dùng.
    ⚠ Superset này CHỈ nới `known_names` cho validate — nó ⛔ KHÔNG làm field
    lạ có giá trị lúc runtime (field không được engine inject vẫn ra 0).
    """
    try:
        from alumglass.variable_sources.context import get_scalar_fieldnames
        names = tuple(get_scalar_fieldnames("AL Accessory Item") or ())
        if names:
            return _with_synthetic(names)
    except Exception:
        pass
    return _with_synthetic(_FALLBACK_CROSS_ROW_FIELDS)


class ALAccessorySet(Document):
    """AL Accessory Set — bộ phụ kiện (tay nắm, khóa, bản lề...) nạp vào BOM
    dưới cost_bucket VL_PK mặc định (override được per-item, xem
    bom_orchestrator._load_accessories())."""

    def validate(self):
        self._validate_item_formulas()
        # Cảnh báo (KHÔNG throw) mã quy tắc literal trong `qty_formula` —
        # cùng mức với cảnh báo Rule Input của AL Bom Set.
        self._warn_lookup_rule_codes()

    def _validate_item_formulas(self):
        if not self.items:
            return
        # AL Accessory Set KHÔNG có variable_set riêng — dùng đúng cùng
        # nguồn biến toàn cục (Cost Bucket/System Var/Formula Global Var)
        # như mọi doctype khác qua get_formula_context.
        # v28_14: profile mới (P_ACCESSORY_DEFAULT) có `cross_row` +
        # `slug_reference` cho bảng items ⇒ autocomplete gợi ý
        # `items.<slug>.<field>`. Validate PHẢI chấp nhận cùng cú pháp, nếu
        # không người dùng thấy gợi ý nhưng bị chặn khi lưu. Engine B3 thật
        # sự dựng `{slug}__qty` (từ qty_formula) + `items` dict cho MỌI dòng
        # trong bom_items (kể cả phụ kiện) ⇒ cross-row chạy được.
        slugs = [i.slug for i in self.items if i.slug]
        known_names = build_known_names(
            "AL Accessory Set", self.name,
            cross_row_slugs=slugs, cross_row_fields=_cross_row_fields(),
        )
        all_errors = []
        for item in self.items:
            errs = check_formula_fields(
                item, ACCESSORY_FORMULA_FIELDS, known_names,
                allow_cross_row=True)
            if errs:
                all_errors.append(row_reference_label(item) + ": " + "; ".join(errs))
        if all_errors:
            frappe.throw("Công thức không hợp lệ:\n" + "\n".join(all_errors))

    def _warn_lookup_rule_codes(self):
        """Cảnh báo (KHÔNG throw) mã quy tắc literal trong `qty_formula`.

        Gõ mã bằng trí nhớ mà mã sai / quy tắc tắt / quy tắc trả mã vật tư
        dùng trong công thức số ⇒ lúc tính giá chỉ ra 0 âm thầm. Một
        `frappe.msgprint` cho cả lần lưu (metadata đọc 1 query).
        """
        if not self.items:
            return
        pairs = [(item, item.get("qty_formula") or "") for item in self.items]
        codes = []
        for _item, expr in pairs:
            codes.extend(lookup_rule_codes(expr))
        rule_meta = load_rule_meta(codes)
        if rule_meta is None:
            # Không đọc được bảng quy tắc ⇒ ⛔ cảnh báo "mã không tồn tại" oan.
            return
        warnings = []
        for item, expr in pairs:
            errs = validate_lookup_rule_codes(expr, "NUMBER", rule_meta=rule_meta)
            if errs:
                warnings.append(
                    row_reference_label(item) + ": " + "; ".join(errs))
        if warnings:
            frappe.msgprint(
                "Mã quy tắc trong công thức số lượng cần kiểm tra:\n"
                + "\n".join(warnings),
                title="AL Accessory Set — Cảnh báo mã quy tắc",
                indicator="orange",
            )
