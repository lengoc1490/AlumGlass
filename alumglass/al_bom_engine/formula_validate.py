# -*- coding: utf-8 -*-
"""Validate công thức DÙNG CHUNG cho mọi doctype có field Formula Builder
(Small Text). Trước bản vá này, AL Cost Template validate CÔNG THỨC RIÊNG
(viết tay trong al_cost_template.py) — module này tách ra để tái dùng cho
AL Bom Set/AL Bom Item, AL Accessory Set/Item, AL Alert Config, v.v. mà
KHÔNG copy lại logic.

⚠ Cross-row `items.slug.field`: FormulaValidator (formula_builder/formula_utils/
security.py) CHẶN mọi truy cập `.attr` không nằm trong whitelist
{'get','keys','values','items','to_dict'} — `.slug`/`.field` KHÔNG được phép.
Engine thật (bom_orchestrator._normalize_items_ref, FormulaEngineCore) luôn
normalize `items.slug.field` → `slug__field` (namespace FLAT) TRƯỚC khi
validate/compile. Module này bắt buộc làm y hệt — dùng chung
formula_builder.table_formula_builder.normalize_global, không tự viết lại.
"""
import re

import frappe
from formula_builder.formula_utils import BASE_FUNCS, FormulaValidator

from alumglass.al_formula_rules import rule_engine

# Regex CHỈ nhận dạng trực tiếp `items.<slug>.<field>` — đúng thứ engine parse
# bằng regex (bom_orchestrator._resolve_rule_input_for_item). Dạng index
# `items[0].field` KHÔNG được engine hỗ trợ cho rule_input_expr nên không
# kiểm ở đây (tránh cảnh báo sai).
_RULE_INPUT_REF_RE = re.compile(r"items\.([A-Za-z_][\w-]*)\.([A-Za-z_]\w*)")

# Lời gọi `lookup_rule('<MÃ>', …)` với mã dạng LITERAL. Lookahead `[,)]` bắt
# buộc sau chuỗi mã phải là dấu phẩy hoặc đóng ngoặc — nhờ vậy
# `lookup_rule('A' + 'B', x)` (nối chuỗi, KHÔNG phải mã literal) bị bỏ qua
# thay vì cảnh báo oan mã "A". Tham số không phải literal (biến, biểu thức)
# cũng không khớp ⇒ không kiểm.
_LOOKUP_RULE_LITERAL_RE = re.compile(
    r"""\blookup_rule\s*\(\s*(?P<quote>['"])(?P<code>[^'"\n]+)(?P=quote)\s*[,)]""")

# Hàm custom alumglass inject qua `safe_funcs=` của FormulaEngine (dùng cho
# CẢ B4 lẫn B6; trước bản vá B6 đi qua EngineConfig.custom_functions của
# FlexibleFormulaEngine) — PHẢI đồng bộ tay với:
#   - bom_orchestrator.py (SAFE FUNCS dùng chung B4+B6, đầu file)
#   - public/js/cost_template.js -> customFns (fetch động qua
#     alumglass.api.get_allowed_formula_functions, xem api/__init__.py)
ALUMGLASS_CUSTOM_FUNCS = frozenset({"lookup_rule", "lookup_calc_pattern", "roundup"})
VALIDATOR_ALLOWED_FUNCS = frozenset(set(BASE_FUNCS.keys()) | ALUMGLASS_CUSTOM_FUNCS)


def normalize_cross_row(expr):
    """items.slug.field -> slug__field — DÙNG ĐÚNG hàm engine thật dùng
    (formula_builder.table_formula_builder.normalize_global), fallback regex
    y hệt bom_orchestrator._normalize_items_ref nếu import lỗi.
    """
    if not expr or "items." not in expr:
        return expr
    try:
        from formula_builder.table_formula_builder import normalize_global
        return normalize_global(expr)
    except Exception:
        return re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)


def build_known_names(doctype, docname, cross_row_slugs=None, cross_row_fields=None,
                      fieldname=None):
    """Universe biến hợp lệ cho 1 doctype/record.

    - Nguồn chính: get_formula_context(doctype, docname, fieldname=...) — Cost
      Bucket, System/User Var, Formula Global Var, Row Literals, FVB binding...
      (KHÔNG hardcode biến nào, xem alumglass/api/__init__.py).
    - cross_row_slugs / cross_row_fields (optional): nếu doctype có
      cross-row reference kiểu `items.slug.field` (vd AL Bom Set, AL Accessory
      Set), truyền vào để bổ sung {slug}__{field} — CHÍNH XÁC namespace FLAT
      mà FormulaEngineCore dùng lúc chạy thật. Không truyền = doctype không
      có cross-row (vd AL Cost Template, AL Alert Config).
    - fieldname (optional): field công thức đang validate — truyền xuống
      get_formula_context để catalog lọc `only_fields` của profile theo đúng
      field; bỏ trống = không lọc (an toàn ngược khi widget chưa gửi field).
    - ⚠ Validate LUÔN dùng `include_all_sources=True`: universe biến hợp lệ là
      đường legacy ĐẦY ĐỦ (như trước bản vá), KHÔNG phải danh sách đã lọc theo
      `AL Variable Profile`. Profile chỉ được lọc GỢI Ý (autocomplete); nếu
      thu hẹp cả universe validate thì bật profile là chặn oan các công thức
      đang chạy (user var, row literal, biến slug... vẫn resolve lúc runtime).
    """
    try:
        from alumglass.api import get_formula_context
        ctx = get_formula_context(
            doctype, docname, fieldname=fieldname,
            include_all_sources=True)
        names = {v["name"] for v in (ctx.get("variables") or []) if v.get("name")}
    except Exception as exc:
        frappe.log_error(
            f"{doctype} validate: lỗi build known_names — {exc}",
            "AlumGlass Formula Validate",
        )
        names = set()

    if cross_row_slugs and cross_row_fields:
        for slug in cross_row_slugs:
            if not slug:
                continue
            for field in cross_row_fields:
                names.add(f"{slug}__{field}")

    return names


def validate_rule_input_expr(expr, known_slugs, known_fields=None):
    """Cảnh báo tham chiếu chéo dòng trong `rule_input_expr` — KHÔNG throw.

    `rule_input_expr` KHÔNG phải biểu thức toán học, nó không đi qua
    FormulaValidator. Engine chỉ parse nó bằng regex `items.<slug>.<field>`
    (bom_orchestrator._resolve_rule_input_for_item) rồi tra giá trị trong
    row_literals/glass_data của dòng đích. Hệ quả:
      - slug không có trong Bom Set → engine trả 0 ÂM THẦM;
      - field không được engine nạp (không phải row literal) → cũng 0 âm thầm.
    Đây là vùng "gõ được nhưng chưa từng được kiểm" ⇒ hàm này trả list[str]
    cảnh báo để caller `frappe.msgprint`. ⛔ KHÔNG frappe.throw: chặn cứng có
    thể làm hỏng các Bom Set đang chạy production.

    Args:
        expr: nội dung rule_input_expr (chuỗi thô, vd
            "items.kinh_tren.glass_thick").
        known_slugs: slug hợp lệ của Bom Set hiện tại.
        known_fields: tên field mà engine có nạp cho 1 dòng (row_literals /
            glass_data). None = không kiểm field, chỉ kiểm slug.

    Returns:
        list[str] cảnh báo (rỗng = không phát hiện vấn đề).
    """
    expr = (expr or "").strip()
    if not expr:
        return []

    refs = _RULE_INPUT_REF_RE.findall(expr)
    if not refs:
        # Không có tham chiếu `items.x.y` → engine fallback glass_thick/
        # glass_type của CHÍNH dòng đó (hành vi hợp lệ) ⇒ không cảnh báo.
        return []

    slugs = set(known_slugs or [])
    fields = set(known_fields) if known_fields is not None else None

    warnings = []
    for slug, field in refs:
        if slug not in slugs:
            warnings.append(
                f"items.{slug}.{field}: không có dòng nào mang slug '{slug}' "
                f"trong Bom Set này — engine sẽ dùng giá trị 0."
            )
            continue
        if fields is not None and field not in fields:
            warnings.append(
                f"items.{slug}.{field}: field '{field}' không được engine nạp "
                f"cho dòng '{slug}' — engine sẽ dùng giá trị 0."
            )
    return warnings


def lookup_rule_codes(expr):
    """Danh sách mã quy tắc LITERAL trong `expr` (giữ thứ tự, bỏ trùng).

    Chỉ nhận `lookup_rule('MÃ', …)` / `lookup_rule("MÃ", …)`. Tham số không
    phải literal (biến/chuỗi nối) ⇒ bỏ qua — ⛔ đoán mã từ biểu thức.
    """
    codes = []
    for match in _LOOKUP_RULE_LITERAL_RE.finditer(expr or ""):
        code = match.group("code").strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def load_rule_meta(codes):
    """Đọc metadata `AL Rule` theo LÔ (1 query) — `{mã: row}`.

    Trả `None` khi KHÔNG đọc được DB (lỗi hạ tầng): caller phải coi là
    "chưa kiểm được" và ⛔ cảnh báo "mã không tồn tại" oan. Trả `{}` khi
    không có mã nào cần đọc.
    """
    codes = [code for code in dict.fromkeys(codes or []) if code]
    if not codes:
        return {}
    try:
        rows = frappe.get_all(
            "AL Rule",
            filters={"name": ["in", codes]},
            fields=["name", "rule_name", "result_type", "is_active"],
        )
    except Exception as exc:  # noqa: BLE001 — lỗi hạ tầng ⛔ chặn lưu
        frappe.log_error(
            f"load_rule_meta: không đọc được AL Rule — {exc}",
            "AlumGlass Formula Validate",
        )
        return None
    return {(row.get("name") or ""): row for row in (rows or [])}


def _rule_warning_label(rule, code):
    """Nhãn người đọc cho câu cảnh báo: tên quy tắc + mã (quản trị cần mã)."""
    name = (rule.get("rule_name") or "").strip()
    return ('"%s" (%s)' % (name, code)) if name else ("mã %s" % code)


def row_reference_label(row):
    """`Dòng {idx} — {tên dòng}` cho câu cảnh báo lúc Lưu.

    `frappe.msgprint` hiện trong hộp thoại rồi đóng — người dùng cần tìm lại
    ĐÚNG dòng trong bảng, nên câu phải có số thứ tự + tên/ mã/ slug đọc được.
    ⛔ dùng mỗi slug trần (khó tìm sau khi đóng hộp).
    """
    if row is None:
        return "Dòng ?"
    getter = getattr(row, "get", None)
    if not callable(getter):
        return "Dòng ?"
    idx = getter("idx")
    name = (getter("line_name") or getter("item_code") or getter("slug")
            or "")
    name = str(name).strip()
    if idx and name:
        return "Dòng %s — %s" % (idx, name)
    if name:
        return "Dòng %s" % name
    return "Dòng %s" % idx if idx else "Dòng ?"


def validate_lookup_rule_codes(expr, expect_result_type="NUMBER",
                               rule_meta=None):
    """Cảnh báo mã quy tắc sai trong công thức — KHÔNG throw.

    Quét các lời gọi `lookup_rule('<MÃ>', …)` có mã LITERAL trong `expr` và
    báo khi:
      - mã không tồn tại trong `AL Rule`;
      - quy tắc đang TẮT (`is_active = 0`);
      - quy tắc trả sai loại so với `expect_result_type` (vd dùng quy tắc
        ITEM trong công thức số ⇒ công thức không ra số).

    Mục đích: vùng "gõ mã bằng trí nhớ" trước đây không ai kiểm — gõ sai mã
    thì lúc tính giá chỉ ra 0 âm thầm. Chỉ CẢNH BÁO (caller `frappe.msgprint`)
    cùng mức với `validate_rule_input_expr`, ⛔ chặn lưu: nhiều BOM đang chạy
    có thể đang ở trạng thái này.

    Câu cảnh báo dùng HTML (`<b>`) vì `frappe.msgprint` render HTML — markdown
    `*…*` sẽ hiện nguyên dấu sao.

    Args:
        expr: chuỗi công thức (có thể rỗng).
        expect_result_type: "NUMBER" (công thức số) / "ITEM" / None để bỏ
            qua phép kiểm loại.
        rule_meta: kết quả `load_rule_meta()` đã đọc sẵn cho CẢ đợt validate
            — truyền vào để tránh N+1 khi kiểm nhiều dòng. None = hàm tự đọc.

    Returns:
        list[str] cảnh báo (rỗng = không phát hiện vấn đề).
    """
    codes = lookup_rule_codes(expr)
    if not codes:
        return []
    meta = load_rule_meta(codes) if rule_meta is None else rule_meta
    if meta is None:
        # Không đọc được bảng quy tắc ⇒ không kết luận gì (⛔ cảnh báo oan).
        return []

    # Tên nút/hộp THẬT trên form công thức (đổi 2026-11-25 theo UX1):
    # nút "🧩 Chọn công thức" → nhánh "Tra quy tắc theo giá trị".
    how_to_fix = "<b>Chọn công thức</b> → <b>Tra quy tắc theo giá trị</b>"

    warnings = []
    for code in codes:
        rule = meta.get(code)
        if not rule:
            warnings.append(
                "lookup_rule('%s', …): không tìm thấy quy tắc này — bấm %s "
                "để chọn lại quy tắc đúng." % (code, how_to_fix))
            continue
        if not rule_engine.rule_is_active(rule):
            warnings.append(
                "lookup_rule('%s', …): quy tắc %s đang tắt nên công thức sẽ "
                "nhận giá trị rỗng — bật lại quy tắc hoặc bấm %s để chọn "
                "quy tắc khác."
                % (code, _rule_warning_label(rule, code), how_to_fix))
            continue
        actual = (rule.get("result_type") or "").strip()
        if expect_result_type and actual and actual != expect_result_type:
            wanted = "số" if expect_result_type == "NUMBER" else (
                "mã vật tư" if expect_result_type == "ITEM" else
                expect_result_type)
            got = "mã vật tư" if actual == "ITEM" else (
                "số" if actual == "NUMBER" else actual)
            warnings.append(
                "lookup_rule('%s', …): quy tắc %s trả về %s trong khi công "
                "thức cần %s — bấm %s để chọn quy tắc khác."
                % (code, _rule_warning_label(rule, code), got, wanted,
                   how_to_fix))
    return warnings


def check_formula(formula, known_names, label="", allow_cross_row=False,
                   extra_known_names=None):
    """Validate 1 công thức. Trả về list[str] lỗi (rỗng = hợp lệ).

    KHÔNG tự throw — caller quyết định frappe.throw()/msgprint() theo bảng
    "chặn cứng hay chỉ cảnh báo" (xem HUONG_DAN_INJECT_VALIDATE.md mục 3.4).
    """
    formula = (formula or "").strip()
    if not formula:
        return []  # rỗng: field-required tự lo riêng (không phải việc của validator công thức)

    expr = normalize_cross_row(formula) if allow_cross_row else formula

    names = set(known_names)
    if extra_known_names:
        names |= set(extra_known_names)

    validator = FormulaValidator(allowed_functions=VALIDATOR_ALLOWED_FUNCS)
    result = validator.validate(expr, known_names=names)
    if result.errors:
        prefix = f"{label}: " if label else ""
        return [f"{prefix}{e}" for e in result.errors]
    return []


def check_formula_fields(row_or_doc, fields, known_names, allow_cross_row=False,
                          extra_known_names=None):
    """Validate nhiều field công thức trên CÙNG 1 row/doc. Trả list[str] lỗi."""
    errors = []
    for fn in fields:
        formula = row_or_doc.get(fn)
        errs = check_formula(formula, known_names, label=fn,
                              allow_cross_row=allow_cross_row,
                              extra_known_names=extra_known_names)
        errors.extend(errs)
    return errors
