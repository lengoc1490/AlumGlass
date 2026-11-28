# -*- coding: utf-8 -*-
"""Câu NGƯỜI ĐỌC cho lỗi công thức của FormulaEngine.

VÌ SAO TÁCH RIÊNG
─────────────────
`FormulaEngine` (lõi Formula Builder) trả lỗi dạng chuỗi Python thô, ví dụ:

    name 'OFFSET_FRAME' is not defined

Chuỗi đó đi thẳng vào `al_bom_result["errors"]` và hiện trên bảng tham số
báo giá. Người dùng thấy một câu vô nghĩa: không biết biến nào, không biết
sửa ở đâu, lại còn phơi mã nội bộ (vi phạm bar trải nghiệm — xem CLAUDE.md
luật 8). Hàm ở đây đổi sang câu nêu NHÃN biến + việc cần làm.

Module THUẦN Python (không import `frappe`) để test được không cần site —
`alumglass/tests/test_formula_error_messages.py`.
"""
import re

#: Python báo thiếu tên trong ngữ cảnh eval: `name 'X' is not defined`.
MISSING_NAME_RE = re.compile(r"name '([A-Za-z_][A-Za-z0-9_]*)' is not defined")


def missing_name(message):
    """Tên biến trong lỗi "name 'X' is not defined"; không khớp ⇒ `None`."""
    match = MISSING_NAME_RE.search(str(message or ""))
    return match.group(1) if match else None


def humanize_formula_error(var_name, label=""):
    """Câu người đọc cho lỗi THIẾU BIẾN trong công thức.

    Args:
        var_name: tên biến kỹ thuật (vd `OFFSET_FRAME`).
        label: nhãn người đọc từ `AL Variable Library.var_label`
            (vd "Khe hở khung-cánh"). Rỗng/trùng tên ⇒ chỉ hiện tên.

    Trả câu: nêu biến + việc cần làm, ⛔ phơi "is not defined".
    """
    var_name = (var_name or "").strip()
    label = (label or "").strip()
    if label and label != var_name:
        shown = "“%s” (%s)" % (label, var_name)
    else:
        shown = "“%s”" % var_name
    return (
        "Chưa có giá trị cho biến %s nên ô này chưa tính được. Khai giá trị "
        "trong bảng tham số, hoặc nhờ quản trị điền ở Thư viện biến / Hệ "
        "nhôm rồi tính lại." % shown
    )


def humanize_unknown_variable(var_name):
    """Câu người đọc khi công thức dùng một TÊN chưa có giá trị nào.

    Khác ca "có biến nhưng thiếu giá trị": ở đây không có chỗ nào để nhập.
    Nói "tên" (⛔ chỉ "biến") vì lỗi này còn gặp khi công thức gõ SAI tên —
    kể cả sai tên một mã tổng chi phí của bộ giá, vốn không nằm trong Thư
    viện biến.
    """
    return (
        "Công thức đang dùng tên “%s” nhưng chưa có giá trị nào mang tên này "
        "(không thấy trong Thư viện biến), nên ô này chưa tính được. Nhờ quản "
        "trị kiểm tra tên trong công thức — có thể gõ sai hoặc thiếu khai biến."
        % ((var_name or "").strip())
    )


def humanize_errors(errors, label_lookup):
    """Đổi cả bảng lỗi `{tên_công_thức: thông_điệp}` sang câu người đọc được.

    Args:
        errors: dict lỗi của FormulaEngine (`last_errors`).
        label_lookup: hàm `var_name -> (có_trong_thư_viện?, nhãn)`.

    Lỗi KHÔNG phải "thiếu biến" giữ NGUYÊN VĂN — nơi phát sinh đã có câu riêng,
    đổi ở đây sẽ che mất thông tin chẩn đoán.
    """
    out = {}
    for key, message in (errors or {}).items():
        text = str(message or "")
        var_name = missing_name(text)
        if not var_name:
            out[key] = message
            continue
        known, label = label_lookup(var_name)
        out[key] = (humanize_formula_error(var_name, label) if known
                    else humanize_unknown_variable(var_name))
    return out


def unchosen_glass_message(label):
    """Câu cho dòng kính CHƯA CHỌN KÍNH (mã đang là mã giữ chỗ, không có giá).

    Khác "thiếu dòng giá": ở đây người dùng không cần sửa bảng giá — chỉ cần
    chọn kính cho vị trí. Câu cũ ("kiểm tra bảng giá hoặc thêm dòng giá…")
    đẩy người dùng đi sửa đúng chỗ không phải nguyên nhân.
    """
    return (
        "Dòng kính “%s” chưa chọn kính cho vị trí này nên đang tạm tính 0. "
        "Mở bảng tham số → phần kính theo vị trí, chọn kính rồi tính lại."
        % ((label or "").strip())
    )
