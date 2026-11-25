import json

import frappe
from frappe.model.document import Document

# ── Field công thức trên AL Bom Item (Small Text, dùng Formula Builder) ──
# Đồng bộ TAY với public/js/formula_setup.js -> "AL Bom Set" refresh
# (formulaFields list) — JS không đọc được Python nên khai báo ở cả 2 nơi.
# FORMULA_FIELDS = field thực sự tham gia DAG cross-row (items.slug.field)
# — dùng làm cross_row_fields khi build known_names (al_bom_set.py).
FORMULA_FIELDS = ("width", "height", "qty", "show_condition")
CONDITION_FORMULA_FIELDS = ("item_condition_formula",)  # chỉ dùng khi mode=Formula
# Synthetic field engine B3 (bom_orchestrator.b3_build_formulas) LUÔN tạo cho
# MỌI dòng — đây là HỢP ĐỒNG ENGINE, ⛔ KHÔNG phải cấu hình người dùng có thể
# tắt (khác row literal: admin bỏ khỏi AL Variable Settings thì engine vẫn
# tạo). Khai ở đây để validate `items.<slug>.<field>` không chặn oan; xem
# al_bom_set._cross_row_known_fields().
ENGINE_SYNTHETIC_FIELDS = ("unit_qty", "total_qty", "line_total")
# rule_input_expr KHÔNG qua FormulaValidator (không phải cú pháp biểu thức
# toán học) — chỉ parse bằng regex, xem ALBomItem.validate() bên dưới.


def _parse_input_vars(raw):
    """Parse input_vars (JSON string hoặc dict/list) → dict.

    AL Bom Item `input_vars` là JSON object {biến phụ: giá trị}.
    AL Quantity Calc Method `input_vars` là JSON list tên biến phụ.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {v: "" for v in raw if isinstance(v, str)}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {v: "" for v in parsed if isinstance(v, str)}
    return {}


def backfill_input_vars(doc, method=None):
    """doc_events hook — validate/backfill `input_vars` khi save AL Bom Item.

    Phase 1d: với mỗi calc_pattern, đọc `input_vars` (danh sách biến phụ) từ
    AL Quantity Calc Method → đảm bảo `input_vars` của line có đủ key (backfill
    key thiếu = "" để engine dùng fallback). Không xoá biến user đã nhập (engine
    chỉ dùng biến thuộc danh sách pattern → biến lạ bị bỏ qua an toàn).
    """
    if not doc.get("calc_pattern"):
        return
    try:
        pattern = frappe.get_cached_doc(
            "AL Quantity Calc Method", doc.get("calc_pattern"))
    except frappe.DoesNotExistError:
        return
    pattern_vars = _parse_input_vars(pattern.get("input_vars") or [])
    if not pattern_vars:
        return

    current = _parse_input_vars(doc.get("input_vars"))
    changed = False
    for v in pattern_vars:
        if v not in current:
            current[v] = ""
            changed = True
    if changed:
        doc.set("input_vars", json.dumps(current))


def assert_item_rules_hop_le(items):
    """Chặn dòng `mode=Rule` trỏ vào quy tắc SAI LOẠI / không tồn tại.

    VÌ SAO là hàm MODULE-LEVEL dùng chung: Frappe v14 **không** gọi
    `validate()` của dòng con khi lưu chứng từ cha (xem chú thích ở
    `ALBomSet.validate` — cùng lý do với `backfill_input_vars`), nên lối đi
    THẬT là `ALBomSet.validate()`. Vẫn giữ lời gọi trong `ALBomItem.validate`
    phòng khi Frappe đổi hành vi; cả hai đi qua ĐÚNG hàm này để câu chữ ⛔ bị
    chép làm hai bản rồi trôi lệch.

    Tra `AL Rule` MỘT LƯỢT cho mọi mã cần kiểm (⛔ N+1 theo từng dòng).

    `items`: danh sách dòng (nhận cả `self` của `ALBomItem`).
    """
    targets = []
    for item in (items or []):
        if (item.get("item_selection_mode") or "") != "Rule":
            continue
        rule_code = item.get("item_rule")
        if rule_code:
            targets.append((item, rule_code))
    if not targets:
        return

    codes = sorted({code for _item, code in targets})
    rule_meta = {
        row.get("name"): row
        for row in (frappe.get_all(
            "AL Rule", filters={"name": ["in", codes]},
            fields=["name", "result_type", "rule_name"]) or [])
    }

    for item, rule_code in targets:
        row_label = item.get("slug") or item.get("idx")
        meta = rule_meta.get(rule_code) or {}
        if not meta:
            frappe.throw(
                f"Dòng '{row_label}': không tìm thấy quy tắc '{rule_code}' — "
                f"chọn lại quy tắc chọn mã vật tư."
            )
        # Nhãn người-đọc-được: tên quy tắc, fallback mã khi chưa đặt tên.
        rule_label = meta.get("rule_name") or rule_code
        if (meta.get("result_type") or "") != "ITEM":
            frappe.throw(
                f"Dòng '{row_label}': quy tắc \"{rule_label}\" là quy tắc "
                f"TÍNH GIÁ TRỊ, không chọn được mã vật tư. Mở dòng này → ô "
                f"Item Rule: chọn quy tắc có Loại kết quả = ITEM; hoặc đổi "
                f"Item Selection Mode sang Fixed/Formula."
            )


class ALBomItem(Document):
    """Dòng vật tư thống nhất - Doctype TRUNG TÂM của hệ thống AlumGlass.

    Mỗi dòng đại diện 1 thành phần trong BOM sản phẩm.
    Validation DATA-DRIVEN dựa trên flags của AL Material Category.
    Hỗ trợ: NHOM, KINH, THEP, INOX, VTP, PK, NHUA, GO...
    """

    def validate(self):
        # Phase 1d: backfill input_vars theo calc_pattern (chạy trước khi
        # category check để luôn đồng bộ kể cả line chưa đủ thông tin).
        backfill_input_vars(self)
        if not self.category:
            return
        cat = frappe.get_cached_doc("AL Material Category", self.category)

        # 1. Item Code bắt buộc khi mode=Fixed
        if cat.requires_item_code and self.item_selection_mode == "Fixed":
            if not self.item_code:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Item Code là bắt buộc "
                    f"cho category '{self.category}'"
                )

        # 2. Price Base Item đại diện để tra giá composite key
        # Bỏ điều kiện `price_type == "Item Price"`: engine KHÔNG đọc price_type
        # khi tra giá — nó luôn lấy giá theo price_base_item, và khi ô này trống
        # thì lặng lẽ lùi về tra theo item_code (bom_orchestrator.py:1057), làm
        # mất phụ phí composite (màu/xuất xứ/độ dày/bề mặt) gắn trên mã đại diện
        # ⇒ tính thiếu tiền mà không có cảnh báo. Điều kiện cũ cho phép lách cổng
        # này bằng cách đổi price_type sang Rule/Fixed — 2 giá trị chưa từng có
        # mã nào xử lý.
        if cat.requires_price_base_item:
            if not self.price_base_item:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Price Base Item là bắt buộc "
                    f"cho category '{self.category}'. Chọn mã Item đại diện dùng "
                    f"chung cho dòng nhôm (nơi gắn bảng giá theo màu, xuất xứ, độ "
                    f"dày, bề mặt) — không phải Item Code của chính dòng này; các "
                    f"dòng nhôm khác trong bộ thường dùng đúng mã đó. Nếu ô này "
                    f"đang ẩn, đặt Price Type = 'Item Price' để hiện ô."
                )

        # 3. Glass Master cho dòng KINH — KHÔNG bắt buộc nữa (V6 P11).
        # `default_glass_master` chỉ là mã MẶC ĐỊNH. Khi để trống, kính thực tế
        # được user chọn theo TỪNG vị trí trong dialog "Kính theo vị trí"
        # (glass_groups → glass_master_map) lúc lập báo giá/sản xuất — engine
        # đọc lại ở B2 (bom_orchestrator) để lấy glass_thick/glass_type.
        # Không thể set cứng 1 mã trong AL Bom Set vì số loại kính thực tế quá
        # lớn; ép buộc mã mặc định sẽ chặn save cấu hình dòng kính "chọn sau".
        # An toàn: user KHÔNG chọn trong dialog → glass_thick=0/glass_type=""
        # hiển thị rõ ở kết quả (bắt lỗi được, không âm thầm sai).

        # 4. CTX Inject Prefix
        if cat.requires_ctx_inject_prefix and not self.ctx_inject_prefix:
            frappe.throw(
                f"Dòng '{self.slug or self.idx}': CTX Inject Prefix là bắt buộc"
            )

        # 5. Qty Formula
        if not self.qty:
            frappe.throw(f"Dòng '{self.slug or self.idx}': Qty Formula là bắt buộc")

        # 6. Rule Mode validation
        if self.item_selection_mode == "Rule":
            if not self.item_rule:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Item Rule là bắt buộc khi mode=Rule"
                )
            # Chặng 2B — `AL Rule` gộp 2 loại rule; ô Item Rule chỉ dùng được
            # rule trả MÃ VẬT TƯ (result_type = ITEM). Rule tính giá trị lọt
            # vào đây thì lúc tính giá dòng hàng mất mã mà ⛔ báo gì — chặn
            # ngay lúc Lưu, nói rõ tên quy tắc + việc cần làm.
            #
            # ⚠ Frappe v14 KHÔNG gọi validate() dòng con khi lưu cha ⇒ trên
            # thực tế cổng này chạy ở `ALBomSet.validate()`. Giữ lời gọi ở đây
            # phòng khi Frappe đổi hành vi; cả hai đi qua CÙNG hàm
            # `assert_item_rules_hop_le` để câu chữ ⛔ trôi lệch.
            assert_item_rules_hop_le([self])
            if not self.rule_input_expr:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Rule Input Expression là bắt buộc "
                    f"khi mode=Rule. VD: items.kinh_tren.glass_thick"
                )
            # V6 P10: rule_input_expr KHÔNG qua FormulaValidator (không phải
            # cú pháp biểu thức toán học — chỉ được bom_orchestrator parse
            # bằng regex, xem _resolve_rule_input_for_item()) — validate
            # đúng format ở đây để bắt lỗi gõ sai NGAY khi save.
            import re
            if not re.match(r'^items\.[\w-]+\.\w+$', self.rule_input_expr.strip()):
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Rule Input Expression phải đúng "
                    f"định dạng 'items.<slug>.<field>' (vd: items.kinh_tren.glass_thick)."
                )

        if self.item_selection_mode == "Formula":
            if not self.item_condition_formula:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Item Condition Formula là bắt buộc "
                    f"khi mode=Formula"
                )

    def before_save(self):
        """Tự động fill category & line_name từ Slug Library."""
        if self.slug:
            try:
                slug_doc = frappe.get_cached_doc("AL Slug Library", self.slug)
                if not self.category:
                    self.category = slug_doc.category
                if not self.line_name:
                    self.line_name = slug_doc.label
            except frappe.DoesNotExistError:
                pass


@frappe.whitelist()
def get_slug_info(slug):
    """Trả về thông tin Slug để client tự fill."""
    if not slug:
        return {}
    doc = frappe.get_cached_doc("AL Slug Library", slug)
    return {"category": doc.category, "line_name": doc.label, "group_tag": doc.group_tag}


@frappe.whitelist()
def get_category_requirements(category_code):
    """Trả về requirement flags cho client-side validation."""
    if not category_code:
        return {}
    cat = frappe.get_cached_doc("AL Material Category", category_code)
    return {
        "requires_item_code": cat.requires_item_code,
        "requires_price_base_item": cat.requires_price_base_item,
        "requires_glass_master": cat.requires_glass_master,
        "requires_ctx_inject_prefix": cat.requires_ctx_inject_prefix,
        "has_weight": cat.has_weight,
        "has_dimensions": cat.has_dimensions,
        "default_calc_pattern": cat.default_calc_pattern,
        "default_cost_bucket": cat.default_cost_bucket,
    }