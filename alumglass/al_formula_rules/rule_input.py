# -*- coding: utf-8 -*-
"""Chặng 3 — quy tắc tự khai "tra theo dữ liệu gì".

Thiết kế: `docs/design/tra-cuu-quy-tac-de-hieu.md` §7.

`AL Rule.input_variable` (Link → `AL Variable Library`) nói quy tắc tra theo
biến nào; `AL Rule.input_scope` (Select ROW/GLOBAL) nói biến đó là dữ liệu
theo TỪNG DÒNG hay biến TOÀN CỤC của lượt tính. Phạm vi **suy từ dữ liệu**
(`AL Variable Library.category`), ⛔ hardcode tên field:

    category == "Row Literals"  ⇒ ROW
    còn lại                     ⇒ GLOBAL

Module này KHÔNG quyết định giá trị cuối cùng — nó chỉ:
  - đọc cấu hình đầu vào của 1 quy tắc (`rule_input_config`);
  - tra metadata biến (nhãn/phạm vi) trong `AL Variable Library`;
  - đọc 1 field từ dict dữ liệu dòng, có alias độ dày kính
    (`glass_thick` ↔ `total_thick_mm`);
  - parse lời gọi `lookup_rule(...)` trong chuỗi công thức (đếm tham số, lấy
    mã literal, lấy token đơn) — dùng CHUNG cho engine, validate và patch để
    ba nơi không tự viết regex riêng rồi trôi lệch nhau.

⛔ Đổi số tiền: mọi hàm ở đây chỉ đọc/parse chuỗi và metadata.
"""

import re

import frappe

ROW_SCOPE = "ROW"
GLOBAL_SCOPE = "GLOBAL"

#: Nhóm biến trong `AL Variable Library` = dữ liệu theo TỪNG DÒNG BOM.
ROW_LITERAL_CATEGORY = "Row Literals"

VARIABLE_DOCTYPE = "AL Variable Library"

#: Alias độ dày kính: `glass_data`/`row_literals` mang CẢ hai tên cùng giá
#: trị; rule khai tên nào cũng phải đọc ra số (xem §7.2).
FIELD_ALIASES = {
    "glass_thick": "total_thick_mm",
    "total_thick_mm": "glass_thick",
}

#: Biến THEO DÒNG mà engine THẬT SỰ đọc được ở bước CHỌN MÃ — ĐÚNG hợp 2
#: nguồn `b2_prefetch_master_data` nạp cho mỗi dòng:
#:   - `glass_data[slug]`: total_thick_mm, glass_thick, glass_type,
#:     max_area_m2, glass_name, glass_type_name;
#:   - `row_literals[slug]`: weight_per_unit, unit_price, calc_pattern,
#:     total_thick_mm, glass_thick, glass_type, glass_type_name, glass_name,
#:     max_area_m2, item_code, scrap_pct, has_weight, color,
#:     supplier_location, install_position, cut_angle, note.
#:
#: ⚠ `width` / `height` / `qty` / `unit_qty` / `total_qty` / `line_total`
#: KHÔNG có trong 2 nguồn đó (chúng là kết quả công thức, chỉ biết SAU bước
#: chọn mã) ⇒ quy tắc ROW chọn chúng sẽ ra 0 ÂM THẦM. Giữ danh sách này khớp
#: ĐÚNG nguồn engine đọc — ⛔ suy diễn thêm (mở rộng danh sách mà engine
#: không nạp chỉ làm cảnh báo im lặng đi, không làm giá trị xuất hiện).
ROW_RESOLVABLE_VARIABLES = frozenset({
    # glass_data
    "total_thick_mm", "glass_thick", "glass_type", "max_area_m2",
    "glass_name", "glass_type_name",
    # row_literals
    "weight_per_unit", "unit_price", "calc_pattern", "item_code",
    "scrap_pct", "has_weight", "color", "supplier_location",
    "install_position", "cut_angle", "note",
})


def is_row_variable_resolvable(var_name):
    """Biến theo dòng này có được engine nạp ở bước chọn mã không."""
    return (var_name or "").strip() in ROW_RESOLVABLE_VARIABLES


#: Nhãn người-đọc DỰ PHÒNG khi quy tắc không có nhãn cho dữ liệu đem tra.
#: ⛔ KHÔNG bao giờ lấy tên biến kỹ thuật (`input_variable`) làm nhãn — câu
#: cảnh báo/lỗi sẽ phơi `total_thick_mm` ra người dùng.
INPUT_LABEL_FALLBACK = "dữ liệu quy tắc đọc"


def readable_input_label(label, var_name=""):
    """Nhãn người-đọc của DỮ LIỆU QUY TẮC ĐEM TRA — một bản dùng CHUNG.

    `label` rỗng, HOẶC trùng đúng tên biến (bỏ khoảng trắng hai đầu, ⛔ phân
    biệt hoa/thường — dữ liệu cũ từng điền tay tên biến vào ô nhãn) ⇒
    `INPUT_LABEL_FALLBACK`; ngược lại giữ nguyên `label`.

    Đặt ở tầng THẤP này (module ⛔ import `rule_engine`/engine) để controller,
    `rule_engine` và `bom_orchestrator` dùng chung một bản — chép hằng ở
    nhiều nơi là bắt đầu trôi lệch (bài học gộp rule 2026-11-23).
    """
    text = str(label or "").strip()
    var = str(var_name or "").strip()
    if not text or (var and text.casefold() == var.casefold()):
        return INPUT_LABEL_FALLBACK
    return text

#: `lookup_rule(` — `\b` đầu để `mylookup_rule(` / `lookup_rule2(` không khớp.
_LOOKUP_START_RE = re.compile(r"\blookup_rule\s*\(")

#: Token BIẾN đơn (không phải số, không phải biểu thức).
_SIMPLE_VARIABLE_RE = re.compile(r"^[A-Za-z_]\w*$")


# ── Metadata biến trong `AL Variable Library` ───────────────────────
def variable_meta(var_name):
    """`{name, category, var_label}` của biến; `{}` khi không có/không đọc được.

    Lỗi đọc (site chưa migrate, thiếu quyền...) ⇒ `{}` — nơi gọi coi như
    "chưa khai biến" và giữ hành vi cũ, ⛔ chết cả lượt tính giá.
    """
    name = (var_name or "").strip()
    if not name:
        return {}
    try:
        rows = frappe.get_all(
            VARIABLE_DOCTYPE,
            filters={"name": name},
            fields=["name", "category", "var_label"],
            limit=1,
        )
    except Exception:  # noqa: BLE001 — metadata hiển thị ⛔ chặn nghiệp vụ
        return {}
    if not rows:
        return {}
    return dict(rows[0])


def scope_of_variable(var_name):
    """Phạm vi của biến: `ROW` khi category = "Row Literals", còn lại GLOBAL."""
    category = (variable_meta(var_name).get("category") or "").strip()
    return ROW_SCOPE if category == ROW_LITERAL_CATEGORY else GLOBAL_SCOPE


def _rule_get(rule, key):
    """Đọc 1 field từ Document/`_dict`/dict mà ⛔ giả định kiểu cụ thể."""
    if rule is None:
        return ""
    getter = getattr(rule, "get", None)
    if callable(getter):
        try:
            value = getter(key)
        except Exception:  # noqa: BLE001 — object lạ chỉ để đọc
            value = None
    else:
        value = getattr(rule, key, None)
    return "" if value is None else str(value).strip()


def rule_input_config(rule):
    """Cấu hình đầu vào của quy tắc — `{}` khi chưa khai `input_variable`.

    Trả `{input_variable, input_scope, input_label}`:
      - `input_scope` lấy đúng giá trị đã lưu; chỉ suy lại từ
        `AL Variable Library` khi trống (dữ liệu cũ/ghi tay qua DB);
      - `input_label` để trống ⇒ `var_label` của biến; nếu vẫn không có nhãn
        đọc được (hoặc nhãn đang là chính tên biến) ⇒ câu chung
        `INPUT_LABEL_FALLBACK` — ⛔ trả tên biến kỹ thuật (xem
        `readable_input_label`).
    """
    var = _rule_get(rule, "input_variable")
    if not var:
        return {}
    scope = _rule_get(rule, "input_scope").upper()
    if scope not in (ROW_SCOPE, GLOBAL_SCOPE):
        scope = scope_of_variable(var)
    label = _rule_get(rule, "input_label")
    if not label:
        label = (variable_meta(var).get("var_label") or "").strip()
    return {
        "input_variable": var,
        "input_scope": scope,
        "input_label": readable_input_label(label, var),
    }


def read_row_value(mapping, field):
    """Đọc `field` từ dict dữ liệu 1 dòng → `(value, found)`.

    `found` phân biệt "không có đầu vào" với "giá trị 0 hợp lệ" — độ dày kính
    0 là số THẬT, còn thiếu field nghĩa là dòng đó không mang dữ liệu.
    Alias độ dày kính: khai `glass_thick` mà dict chỉ có `total_thick_mm`
    (hoặc ngược lại) vẫn đọc ra đúng số.
    """
    if not isinstance(mapping, dict) or not field:
        return None, False
    if field in mapping:
        return mapping.get(field), True
    alias = FIELD_ALIASES.get(field)
    if alias and alias in mapping:
        return mapping.get(alias), True
    return None, False


# ── Parse lời gọi `lookup_rule(...)` trong chuỗi công thức ──────────
def _skip_string(text, index):
    """Vị trí ngay SAU chuỗi bắt đầu tại `index`; -1 khi chuỗi không đóng."""
    quote = text[index]
    index += 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        index += 1
    return -1


def _find_close_paren(text, start):
    """Vị trí `)` đóng lời gọi (đếm độ sâu, bỏ qua chuỗi); None nếu thiếu."""
    depth = 1
    index = start
    while index < len(text):
        char = text[index]
        if char in "'\"":
            index = _skip_string(text, index)
            if index < 0:
                return None
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _split_args(text):
    """Tách tham số theo dấu phẩy MỨC 0 (bỏ qua chuỗi + ngoặc lồng)."""
    args = []
    buffer = []
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in "'\"":
            end = _skip_string(text, index)
            if end < 0:
                buffer.append(text[index:])
                index = len(text)
                continue
            buffer.append(text[index:end])
            index = end
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(buffer).strip())
            buffer = []
            index += 1
            continue
        buffer.append(char)
        index += 1
    tail = "".join(buffer).strip()
    if tail or args:
        args.append(tail)
    return args


def _literal_code(token):
    """Mã quy tắc LITERAL (`'MÃ'` / `"MÃ"`); None khi là biểu thức/nối chuỗi."""
    token = (token or "").strip()
    if len(token) >= 2 and token[0] in "'\"" and token[-1] == token[0]:
        inner = token[1:-1]
        if token[0] not in inner:
            return inner
    return None


def parse_lookup_rule_calls(expr):
    """Mọi lời gọi `lookup_rule(...)` trong `expr`.

    Trả list `[{code: str|None, args: [str, ...]}, ...]` theo thứ tự xuất
    hiện. `code is None` nghĩa là tham số đầu KHÔNG phải mã literal (biến,
    nối chuỗi, biểu thức) — nơi gọi tự bỏ qua. Lời gọi lồng nhau được tách
    đúng nhờ đếm độ sâu ngoặc, nên `roundup(lookup_rule('A', x), 0)` vẫn
    thấy đúng 1 lời gọi.
    """
    text = expr or ""
    calls = []
    position = 0
    while position < len(text):
        match = _LOOKUP_START_RE.search(text, position)
        if not match:
            break
        start = match.end()
        close = _find_close_paren(text, start)
        if close is None:
            break
        args = _split_args(text[start:close])
        calls.append({
            "code": _literal_code(args[0]) if args else None,
            "args": args,
        })
        position = close + 1
    return calls


def lookup_rule_arities(expr):
    """`{mã: {số_tham_số, ...}}` cho các lời gọi có mã LITERAL."""
    arities = {}
    for call in parse_lookup_rule_calls(expr):
        code = call.get("code")
        if not code:
            continue
        arities.setdefault(code, set()).add(len(call.get("args") or []))
    return arities


def one_arg_rule_codes(expr):
    """Tập mã quy tắc được gọi với ĐÚNG MỘT tham số trong `expr`."""
    return {code for code, counts in lookup_rule_arities(expr).items()
            if 1 in counts}


def simple_variable_arg(args):
    """Tham số thứ 2 khi nó là TOKEN BIẾN đơn; None khi số/biểu thức/thiếu.

    Dùng cho patch suy `input_variable`: chỉ nhận `lookup_rule('MÃ', H_mm)`.
    """
    if not args or len(args) != 2:
        return None
    token = (args[1] or "").strip()
    return token if _SIMPLE_VARIABLE_RE.match(token) else None
