import frappe
from frappe.model.document import Document

from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import (
    backfill_input_vars, assert_item_rules_hop_le, FORMULA_FIELDS,
    CONDITION_FORMULA_FIELDS, ENGINE_SYNTHETIC_FIELDS)
from alumglass.al_bom_engine.formula_validate import (
    build_known_names, check_formula_fields, load_rule_meta, lookup_rule_codes,
    row_reference_label, validate_lookup_rule_codes, validate_rule_input_expr)
from alumglass.al_formula_rules import rule_engine
from alumglass.al_formula_rules import rule_input


def _rule_input_known_fields():
    """Field mà engine nạp cho mỗi dòng (row literal) — đọc từ DỮ LIỆU.

    Nguồn: row literal đang bật trong `AL Variable Library`
    (`group_label = "Row Literals"`, trước 2026-11-27 ở `AL Variable Settings`)
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
      2. Row literal đang bật trong `AL Variable Library` (group_label Row Literals)
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
        # Cổng "ô Item Rule phải là quy tắc CHỌN MÃ (result_type = ITEM)".
        # ⚠ Frappe v14 KHÔNG gọi `validate()` của dòng con khi lưu chứng từ
        # cha (`frappe/model/document.py` — `_save_children`/`update_children`
        # ghi thẳng DB, ⛔ qua validate), nên cổng trong `ALBomItem.validate`
        # KHÔNG chạy trên đường thật: nhập qua API/import, hoặc đổi
        # `Result Type` của một rule ĐANG được dùng, đều ghi được rule sai
        # loại ⇒ lúc tính giá dòng hàng mất mã âm thầm. Vì vậy kiểm ở ĐÂY —
        # chỗ duy nhất người dùng thật sự bấm Lưu.
        assert_item_rules_hop_le(self.items)
        self._validate_child_formulas()
        # Cảnh báo (không chặn) tham chiếu chéo dòng trong rule_input_expr —
        # vùng "gõ được nhưng chưa từng được kiểm" (xem docstring hàm).
        self._warn_rule_input_expr()
        # Cảnh báo (không chặn) mã quy tắc literal trong CÔNG THỨC qty —
        # `lookup_rule('MÃ', …)` gõ sai/rule tắt/rule sai loại trước đây chỉ
        # cho ra 0 âm thầm lúc tính giá.
        self._warn_lookup_rule_codes()
        # Chặng 3: quy tắc tra theo dữ liệu TỪNG DÒNG mà dòng chưa chọn
        # "Lấy từ dòng" (và cũng không có biểu thức cũ) ⇒ dòng mất mã.
        self._warn_rule_input_row()
        # Đ4: biến THEO DÒNG dùng trần trong công thức — validator cho qua
        # nhưng runtime B4 không có tên trần ⇒ 0 âm thầm. Cảnh báo, ⛔ chặn.
        self._warn_bare_row_variables()

    def _validate_slug_uniqueness(self):
        """Đảm bảo không slug trùng trong cả items và accessory_items."""
        seen = []
        for item in (self.items or []):
            if item.slug:
                if item.slug in seen:
                    frappe.throw(
                        f"Mã '{item.slug}' bị trùng trong bộ — mỗi dòng "
                        f"cần một mã riêng.")
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
        # (AL Variable Library, group_label Row Literals) + synthetic
        # unit_qty/total_qty/line_total.
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
                all_errors.append(row_reference_label(item) + ": " + "; ".join(errs))
        if all_errors:
            frappe.throw("Công thức không hợp lệ:\n" + "\n".join(all_errors))

    def _warn_bare_row_variables(self):
        """Cảnh báo biến THEO DÒNG dùng TRẦN trong công thức (Đ4).

        Vì sao cần: `_cross_row_known_fields` cố ý nới `known_names` cho
        validate (để `items.<slug>.<field>` chạy được), nên viết trần
        `unit_price` **qua được** validate. Nhưng B4 chỉ có `inputs` toàn cục
        và `items` lồng; tên trần **không tồn tại** ⇒ công thức ra 0 mà không
        báo. Hàm này chỉ CẢNH BÁO (dữ liệu cũ có thể đang vậy), ⛔ throw.
        """
        try:
            from alumglass.variable_sources import catalog_rows
            rows = catalog_rows.active_rows(catalog_rows.KIND_ROW)
        except Exception:
            return
        labels = {
            row.get("var_name"): (row.get("var_label") or row.get("var_name"))
            for row in rows or [] if row.get("var_name")
        }
        if not labels:
            return

        warnings = []
        fields = tuple(FORMULA_FIELDS) + tuple(CONDITION_FORMULA_FIELDS)
        for item in self.items or []:
            for fieldname in fields:
                formula = item.get(fieldname) or ""
                for name in rule_input.find_bare_row_variables(formula, labels):
                    warnings.append(
                        "Dòng '%s', ô '%s': biến theo dòng '%s' đang dùng "
                        "trần. Dữ liệu theo dòng chỉ đọc được ở dạng "
                        "items.<dòng>.<cột> — dùng trần sẽ ra 0."
                        % (item.slug or item.idx, fieldname, labels[name]))
        if warnings:
            frappe.msgprint(
                "Công thức dùng biến theo dòng không đúng dạng:\n"
                + "\n".join(warnings),
                title="Cảnh báo công thức", indicator="orange")

    def _warn_rule_input_expr(self):
        """Cảnh báo (KHÔNG throw) `items.<slug>.<field>` trong rule_input_expr.

        `rule_input_expr` KHÔNG đi qua FormulaValidator (không phải biểu thức
        toán học) — engine chỉ parse bằng regex rồi tra row_literals/
        glass_data của dòng đích. Trước đây gõ sai slug/field vẫn save được và
        engine trả 0 ÂM THẦM. Nay hiện cảnh báo cam để người cấu hình sửa,
        nhưng vẫn KHÔNG chặn — nhiều Bom Set đang chạy có thể đang ở trạng
        thái này, chặn cứng sẽ khoá dữ liệu cũ (spec: warn, not throw).
        Danh sách field hợp lệ lấy từ row literal trong `AL Variable Library`
        (xem `_rule_input_known_fields`) — KHÔNG hardcode ở đây.
        """
        if not self.items:
            return
        slugs = {i.slug for i in self.items if i.slug}
        # Danh sách field đọc từ AL Variable Library (xem _rule_input_known_fields).
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

    def _warn_lookup_rule_codes(self):
        """Cảnh báo (KHÔNG throw) mã quy tắc literal trong công thức `qty`.

        Cùng mức với `_warn_rule_input_expr`: gõ mã bằng trí nhớ
        (`lookup_rule('MÃ', …)`) mà mã sai / quy tắc đang tắt / quy tắc trả
        mã vật tư dùng trong công thức số ⇒ lúc tính giá chỉ ra 0 ÂM THẦM.
        Một `frappe.msgprint` cho cả lần lưu (đọc metadata 1 query).
        """
        if not self.items:
            return
        pairs = [(item, item.get("qty") or "") for item in self.items]
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
                title="AL Bom Set — Cảnh báo mã quy tắc",
                indicator="orange",
            )

    def _warn_rule_input_row(self):
        """Cảnh báo (KHÔNG throw) dòng chọn mã thiếu nguồn dữ liệu tra.

        Chặng 3 (§7.1 + §7.6): quy tắc khai biến theo DÒNG
        (`input_scope = ROW`) thì mỗi dòng BOM phải chỉ **dòng lấy dữ liệu**
        (`rule_input_row`). Ô đó ẨN trên form — câu cảnh báo phải chỉ nút
        NHÌN THẤY được (**Chọn dòng lấy dữ liệu**), ⛔ nhắc tên field kỹ thuật.
        Thiếu nguồn (và cũng không còn biểu thức cũ) ⇒ engine không có đầu
        vào, dòng hàng mất mã ÂM THẦM.

        Cùng mức với `_warn_rule_input_expr`: chỉ `frappe.msgprint`, ⛔ chặn
        lưu — nhiều Bom Set đang chạy có thể đang ở trạng thái này.
        """
        if not self.items:
            return
        rule_items = [
            item for item in self.items
            if item.get("item_selection_mode") == "Rule"
            and item.get("item_rule")
        ]
        if not rule_items:
            return
        rule_meta = load_rule_meta([item.get("item_rule") for item in rule_items])
        if rule_meta is None:
            # Không đọc được bảng quy tắc ⇒ ⛔ cảnh báo oan.
            return
        warnings = []
        for item in rule_items:
            rule = rule_meta.get(item.get("item_rule")) or {}
            var = (rule.get("input_variable") or "").strip()
            if not var:
                # Quy tắc CHƯA khai "Tra theo" ⇒ biểu thức cũ vẫn là đường
                # chạy thật, ⛔ cảnh báo "bị bỏ qua".
                continue
            scope = (rule.get("input_scope") or "").strip().upper()
            row_slug = str(item.get("rule_input_row") or "").strip()
            expr = str(item.get("rule_input_expr") or "").strip()
            # Nhãn người-đọc của dữ liệu đem tra. ⛔ Lấy tên biến kỹ thuật
            # (`var`) làm nhãn — câu cảnh báo sẽ phơi `total_thick_mm` ra
            # người dùng. Rỗng / trùng đúng tên biến ⇒ câu chung.
            label = rule_engine.rule_input_label(rule)
            rule_name = (rule.get("rule_name") or "").strip()
            rule_label = ('"%s"' % rule_name) if rule_name else "quy tắc đã chọn"
            if scope == "ROW":
                if not row_slug and not expr:
                    warnings.append(
                        "%s: quy tắc %s tra theo %s của từng dòng nhưng chưa "
                        "chọn dòng lấy dữ liệu — dòng này sẽ không có mã vật "
                        "tư, thành tiền chưa đúng. Bấm <b>Chọn dòng lấy dữ "
                        "liệu</b> rồi chọn dòng chứa dữ liệu (vd Kính trên)."
                        % (row_reference_label(item), rule_label, label))
                elif row_slug and expr:
                    # Đã chọn dòng ⇒ engine đọc dòng đó; biểu thức nâng cao
                    # KHÔNG còn được dùng — nói rõ để ⛔ ai sửa nhầm chỗ.
                    warnings.append(
                        "%s: quy tắc %s đã khai tra theo %s nên biểu thức "
                        "nâng cao của dòng này đang bị bỏ qua — xoá biểu thức "
                        "trong mục Nâng cao (hoặc bỏ chọn dòng lấy dữ liệu "
                        "nếu muốn dùng biểu thức)."
                        % (row_reference_label(item), rule_label, label))
            elif expr:
                # GLOBAL: engine đọc thông số của lượt tính, ⛔ đọc biểu thức
                # nâng cao của dòng ⇒ biểu thức đang bị bỏ qua.
                warnings.append(
                    "%s: quy tắc %s tự lấy %s của lượt tính nên biểu thức "
                    "nâng cao của dòng này đang bị bỏ qua — xoá biểu thức "
                    "trong mục Nâng cao cho khỏi nhầm."
                    % (row_reference_label(item), rule_label, label))
        if warnings:
            frappe.msgprint(
                "Dòng chọn mã thiếu nguồn dữ liệu tra:\n"
                + "\n".join(warnings),
                title="AL Bom Set — Cảnh báo dữ liệu tra",
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
