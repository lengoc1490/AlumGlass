# -*- coding: utf-8 -*-
"""Bộ máy DÙNG CHUNG cho rule có dải ngưỡng.

`AL Rule` gộp cả hai loại kết quả (NUMBER trả `result_value`, ITEM trả
`result_item`) về một DocType. Trước đây hai doctype rule song song mỗi bên
tự chép: sort theo `from_value`, kiểm chồng lấp, cảnh báo khe hở, resolve
biên nửa mở + lưới tương thích dữ liệu cũ. Chép đôi ⇒ hai bên trôi khỏi nhau
(từng có chuyện một bên CẤM chạm biên còn bên kia CHO PHÉP). Hai DocType cũ
đã bị xoá (2026-11-23), phần dùng chung ở đây là nơi duy nhất.

Quy ước chung (F9):
  - Dải biên NỬA MỞ ``[from, to)``. Hai dải chạm biên là HỢP LỆ và luôn xác
    định: dải TRÊN thắng (``[0,10)`` + ``[10,20)`` với input 10 ⇒ dải sau).
  - ``to`` ĐỂ TRỐNG = dải MỞ phía trên ``[from, +∞)`` (nhãn form "Đến (bỏ
    trống = trở lên)"). Chỉ dải CUỐI được mở; dải mở ở giữa bị validate chặn.
  - Dòng xếp theo ``from_value`` — ⛔ KHÔNG theo thứ tự lưu.
  - Lưới tương thích DỮ LIỆU CŨ: nếu nửa mở không khớp dòng nào, thử lại
    đúng tại biên trên ĐÓNG. Rule cũ khai ``[0,10]`` + ``[10.1,20]`` cần
    input 10 vẫn khớp (nếu không, NV_LD về 0 ⇒ sai giá âm thầm). Đây là
    chịu-lỗi cho dữ liệu cũ, ⛔ phải quy ước thứ hai.

Module này CHỈ đọc dữ liệu dòng (không tự lưu/xoá gì). `frappe.throw` dùng để
chặn lúc Lưu DocType; `frappe.msgprint` để cảnh báo khe hở (⛔ throw — dữ liệu
cũ đang chạy được).
"""

import frappe

from alumglass.al_formula_rules.rule_input import (
    INPUT_LABEL_FALLBACK,  # noqa: F401 — re-export cho nơi dùng cũ
    readable_input_label,
)

#: Nhãn người-đọc của cột kết quả trên từng loại rule.
RESULT_LABELS = {
    "result_value": "Giá trị kết quả",
    "result_item": "Mã vật tư",
}

# ══════════════════════════════════════════════════════════════════
# Nhãn người-đọc cho các ENUM của `AL Rule`
# ══════════════════════════════════════════════════════════════════
# Giá trị LƯU trong DB vẫn là enum (CONSTANT/THRESHOLD/LOOKUP,
# NUMBER/ITEM) — các bảng dưới đây CHỈ dùng để dựng câu cho người dùng.
# ⛔ Phơi enum ra thông báo/lỗi: người dùng thấy "quy tắc THRESHOLD cần
# ít nhất 1 dòng" là mã kỹ thuật lọt ra ngoài.
# Đặt ở ĐÂY (không chép sang `al_rule.py`) để controller và engine dùng
# CHUNG một bản — hai bản sẽ trôi khỏi nhau (bài học gộp rule 2026-11-23).

#: Loại quy tắc → nhãn nghiệp vụ.
RULE_TYPE_LABELS = {
    "CONSTANT": "Hằng số",
    "THRESHOLD": "Tra theo dải",
    "LOOKUP": "Tra theo bảng",
}

#: Loại kết quả → nhãn nghiệp vụ.
RESULT_TYPE_LABELS = {
    "NUMBER": "Số",
    "ITEM": "Mã vật tư",
}

#: Nhãn thay thế khi quy tắc KHÔNG có nhãn người-đọc cho dữ liệu đem tra.
#: MỘT BẢN duy nhất ở `rule_input` (import ở đầu tệp) — ⛔ định nghĩa lại
#: ở đây để hai bản không trôi khỏi nhau.


def rule_type_label(value):
    """Nhãn người-đọc của `rule_type`; giá trị lạ ⇒ "chưa xác định"."""
    return RULE_TYPE_LABELS.get(value, "chưa xác định")


def result_type_label(value):
    """Nhãn người-đọc của `result_type`; giá trị lạ ⇒ "chưa xác định"."""
    return RESULT_TYPE_LABELS.get(value, "chưa xác định")


def rule_input_label(rule):
    """Nhãn người-đọc cho DỮ LIỆU QUY TẮC ĐEM TRA.

    Uỷ quyền cho `rule_input.readable_input_label` (một bản dùng chung):
      - `input_label` có giá trị đọc được ⇒ dùng nguyên văn;
      - rỗng, HOẶC trùng đúng `input_variable` (dữ liệu cũ điền tay / nhãn
        chưa đặt nên hệ thống từng lấy tên biến) ⇒ câu chung
        "dữ liệu quy tắc đọc" — ⛔ phơi tên biến ra người dùng.
    """
    return readable_input_label(
        _get(rule, "input_label"), _get(rule, "input_variable"))


# ── Truy cập dòng: chịu được cả Document thật, frappe._dict và dict thường ──
def _get(row, field, default=None):
    """Đọc 1 field của dòng — dùng được cho Document, `_dict` và `dict`."""
    if isinstance(row, dict):
        return row.get(field, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        try:
            return getter(field, default)
        except TypeError:  # object có .get() nhưng không nhận default
            value = getter(field)
            return default if value is None else value
    return getattr(row, field, default)


def _is_missing(value):
    """Rỗng thật sự. Lưu ý 0 / 0.0 là GIÁ TRỊ HỢP LỆ cho `result_value`."""
    return value is None or value == ""


def _num(value, default=0.0):
    """Ép số an toàn — dữ liệu form có thể là chuỗi."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value):
    """Hiển thị số gọn cho câu lỗi (10.0 → '10')."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return repr(number)


#: Bản CÔNG KHAI của `_get`/`_num` cho controller/API (`ALRule.preview`).
#: Cùng một cách đọc dòng — ⛔ chép lại accessor ở nơi khác rồi trôi khỏi nhau.
def row_field(row, field, default=None):
    """Đọc 1 field của dòng: nhận Document, `frappe._dict` và dict thường."""
    return _get(row, field, default)


def as_number(value, default=0.0):
    """Ép số an toàn cho field của dòng (None/chuỗi rỗng ⇒ `default`)."""
    return _num(value, default)


def sorted_threshold_rows(rows):
    """Dòng threshold xếp theo `from_value` TĂNG DẦN — ⛔ theo thứ tự lưu."""
    return sorted(rows or [], key=lambda row: _num(_get(row, "from_value")))


def rule_is_active(rule):
    """Rule còn bật không.

    Field `is_active` thiếu/rỗng ⇒ coi như ĐANG BẬT (dữ liệu cũ, stub test);
    chỉ giá trị khai báo tường minh bằng 0/"0"/False mới là TẮT.
    """
    value = _get(rule, "is_active")
    if value is None or value == "":
        return True
    try:
        return int(value) != 0
    except (TypeError, ValueError):
        return bool(value)


def warn_threshold_gaps(rows, title):
    """Cảnh báo KHE HỞ giữa 2 dải liền nhau (F9).

    Quy ước `[from, to)` khiến 2 dải liền nhau phải khai `to` = `from` dải
    sau (vd [0,24] + [24,30]). Kiểu khai cũ có khe 0.1 (vd [0,24] + [24.1,30])
    để lại vùng 24 → 24.1 KHÔNG dải nào phủ ⇒ giá trị rơi vào đó (vd 24.05)
    không khớp dòng nào và trả None âm thầm. Cảnh báo (KHÔNG throw — dữ liệu
    cũ đang chạy được) để người khai rule thấy ngay lúc save.

    Dải để TRỐNG "Đến" là dải MỞ phía trên (+∞) ⇒ nó không có khe phía trên,
    ⛔ được đọc `to` rỗng thành 0 rồi báo khe oan.
    """
    rows = sorted_threshold_rows(rows)
    gaps = []
    for i in range(len(rows) - 1):
        to_value = _get(rows[i], "to_value")
        if _is_missing(to_value):
            continue
        next_from = _get(rows[i + 1], "from_value")
        if _num(to_value) < _num(next_from):
            gaps.append("[%s – %s]" % (_fmt(to_value), _fmt(next_from)))
    if gaps:
        frappe.msgprint(
            "Các dải tra theo đang có KHE HỞ — giá trị nằm trong khe sẽ không "
            "khớp dòng nào (trả rỗng): " + ", ".join(gaps) + ". Nên khai liền: "
            "dải sau bắt đầu đúng bằng giá trị \"Đến\" của dải trước.",
            title=title,
            indicator="orange",
        )


def validate_threshold_rows(rows, result_field, doctype_label=None):
    """Kiểm dải threshold lúc Lưu DocType. Throw nếu dữ liệu không dùng được.

    Kiểm:
      1. Mỗi dòng có cột kết quả (`result_field`) và `from_value` (Từ) bắt buộc.
      2. `to_value` (Đến) ĐƯỢC ĐỂ TRỐNG = dải mở phía trên (+∞). Chỉ dải
         CUỐI (theo `from`) được mở; mở ở giữa ⇒ throw (dải mở nuốt mọi dải
         nằm trên nó nên cấu hình đó không bao giờ dùng được).
      3. `from_value <= to_value` — chỉ kiểm dải ĐÓNG.
      4. Không chồng lấp: biên NỬA MỞ `[from, to)`, chạm biên HỢP LỆ.
      5. Cảnh báo (KHÔNG throw) khe hở giữa các dải liền nhau.
    """
    result_label = RESULT_LABELS.get(result_field, result_field)
    rows = sorted_threshold_rows(rows)

    open_indexes = []
    for i, row in enumerate(rows):
        if _is_missing(_get(row, result_field)):
            frappe.throw(
                "Dòng ngưỡng %d: còn thiếu '%s' — điền giá trị kết quả "
                "cho dòng này rồi lưu lại." % (i + 1, result_label))
        from_value = _get(row, "from_value")
        to_value = _get(row, "to_value")
        if _is_missing(from_value):
            frappe.throw(
                "Dòng ngưỡng %d: còn thiếu 'Từ' — điền giá trị bắt "
                "đầu của dải rồi lưu lại." % (i + 1))
        if _is_missing(to_value):
            open_indexes.append(i)
            continue
        if _num(from_value) > _num(to_value):
            frappe.throw(
                "Dòng ngưỡng %d: 'Từ' (%s) lớn hơn 'Đến' (%s) — "
                "dải ngược không dùng được. Sửa lại cho 'Từ' nhỏ hơn hoặc "
                "bằng 'Đến'."
                % (i + 1, _fmt(from_value), _fmt(to_value)))

    # Dải mở phía trên CHỈ hợp lệ khi nằm CUỐI (theo `from`). Mở ở giữa thì
    # mọi giá trị từ `from` trở lên đều rơi vào nó, các dải phía trên vô nghĩa.
    for index in open_indexes:
        if index != len(rows) - 1:
            frappe.throw(
                "Dòng ngưỡng %d: 'Đến' để trống nghĩa là dải mở phía "
                "trên (+∞) — chỉ dải CUỐI được để trống. Điền 'Đến' cho dòng "
                "này hoặc chuyển nó xuống cuối bảng." % (index + 1))

    for i in range(len(rows) - 1):
        # Quy ước biên NỬA MỞ [from, to): chạm biên (to == next.from) là HỢP
        # LỆ và luôn xác định — dải TRÊN thắng, xem resolve_threshold().
        # Dải trước MỞ (+∞) thì không có "chồng lấp" tính được; validate đã
        # chặn trường hợp đó ở trên — bỏ qua để ⛔ đọc `to` rỗng thành 0.
        to_value = _get(rows[i], "to_value")
        if _is_missing(to_value):
            continue
        if _num(to_value) > _num(_get(rows[i + 1], "from_value")):
            frappe.throw(
                "Các dải tra theo bị chồng lấp: [%s-%s] và [%s-%s] — sửa lại "
                "sao cho 'Đến' của dải trước không vượt quá 'Từ' của dải "
                "sau." % (
                    _fmt(_get(rows[i], "from_value")),
                    _fmt(_get(rows[i], "to_value")),
                    _fmt(_get(rows[i + 1], "from_value")),
                    _fmt(_get(rows[i + 1], "to_value")),
                )
            )

    warn_threshold_gaps(
        rows,
        "%s — Cảnh báo khe hở" % doctype_label
        if doctype_label else "Cảnh báo khe hở",
    )


def match_threshold_row(rows, value):
    """Trả DÒNG threshold khớp `value` (None nếu không khớp dòng nào).

    Tách ra từ `resolve_threshold` để màn "Thử tra" (`ALRule.preview`) tô
    đúng dòng đã khớp mà ⛔ phải viết lại logic resolve lần thứ hai — hai
    bản logic song song sẽ trôi khỏi nhau (bài học gộp rule 2026-11-23).
    Ngữ nghĩa: nửa mở `[from, to)`; dòng để TRỐNG `to` là dải MỞ phía trên
    (+∞) nên khớp mọi giá trị `>= from`. Sau đó (chỉ khi chưa khớp) mới chạy
    lưới tương thích dữ liệu cũ tại biên trên ĐÓNG — lưới này CHỈ xét dòng
    CÓ `to`, ⛔ được đọc `to` rỗng thành 0 (giá trị 0 sẽ khớp dải mở oan).
    """
    try:
        val = float(value)
    except (ValueError, TypeError):
        return None
    rows = sorted_threshold_rows(rows)
    for row in rows:
        from_value = _num(_get(row, "from_value"))
        to_value = _get(row, "to_value")
        if _is_missing(to_value):
            if from_value <= val:  # dải mở: [from, +∞)
                return row
            continue
        if from_value <= val < _num(to_value):
            return row
    for row in rows:
        to_value = _get(row, "to_value")
        if _is_missing(to_value):
            continue
        if val == _num(to_value):
            return row
    return None


def match_lookup_row(rows, value):
    """Trả DÒNG tra bảng khớp `value` theo `key_field` (None nếu không khớp).

    So khớp dạng chuỗi như `ALRule.resolve()` (dữ liệu form có thể là số
    hoặc chuỗi). Giữ NGUYÊN thứ tự dòng đã lưu: dòng đầu tiên khớp thắng.
    """
    for row in rows or []:
        if str(_get(row, "key_field")) == str(value):
            return row
    return None


def resolve_threshold(rows, value, result_field):
    """Tra 1 dòng threshold theo quy ước biên NỬA MỞ `[from, to)`.

    Duyệt theo `from_value` TĂNG DẦN (trước đây theo thứ tự lưu ⇒ đổi thứ tự
    dòng là đổi kết quả khi 2 dải chạm biên).

    Lưới tương thích dữ liệu CŨ: rule hiện khai theo lối ĐÓNG hai đầu có khe
    0.1 (vd seed RULE-HEIGHT-MULT [(0,10),(10.1,30)…]) — giá trị đúng bằng
    biên trên một dải (10, 2100, 2700…) sẽ trượt hết nếu chỉ dùng nửa mở, làm
    NV_LD về 0 ⇒ SAI GIÁ âm thầm. Nên nếu nửa mở không khớp dòng nào, thử lại
    đúng tại biên trên ĐÓNG. Đây là chịu-lỗi cho dữ liệu cũ, KHÔNG phải quy
    ước thứ hai: chỗ 2 dải chạm biên vẫn xử theo nửa mở (dải trên thắng).
    """
    row = match_threshold_row(rows, value)
    if row is None:
        return None
    return _get(row, result_field)
