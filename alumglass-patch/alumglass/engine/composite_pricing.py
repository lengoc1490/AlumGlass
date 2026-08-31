# -*- coding: utf-8 -*-
"""Thuật toán match Item Price theo composite key (Pricing Dimension) —
DÙNG CHUNG giữa 2 nhánh resolve giá:
  - BomOrchestrator._fetch_composite_prices() (nhánh fallback, luôn chạy)
  - fb_handlers.aluminum_price_composite() (nhánh FB-max, chạy khi FVB seed D3)

Trước đây 2 nhánh có 2 thuật toán KHÁC NHAU (fallback = best-partial-match,
FB-max/exact_match = AND cứng qua query filter) → hành vi tra giá composite
ĐỔI KHÁC khi chuyển từ nhánh này sang nhánh kia (xem ghi nhận audit 2026-08).
Gộp về đây để 2 nhánh LUÔN cho cùng kết quả, sửa 1 chỗ áp dụng cả 2 nơi.
"""


def best_partial_match(rows, dim_fieldnames, inputs):
    """Chọn dòng Item Price khớp NHIỀU field composite nhất với `inputs`.

    rows: list[dict] — mỗi dict là 1 dòng Item Price, phải có "price_list_rate"
        + các custom_fieldname trong dim_fieldnames.values().
    dim_fieldnames: {variable_name: custom_fieldname} — dimension áp dụng cho
        item_code đang tra (đã lọc theo material_category của dòng đó).
    inputs: {variable_name: value} — composite key hiện tại.

    Quy tắc:
    - Dòng không set 1 field composite nào đó → bỏ qua field đó (không loại).
    - Dòng có set field nhưng khác input hiện tại → loại (mismatch).
    - Trong các dòng còn lại, chọn dòng có điểm khớp cao nhất.
    - Không dòng nào khớp → fallback dòng "trần" (không set field composite nào).
    - Không có gì phù hợp → None (caller tự quyết định throw/trả 0).
    """
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]["price_list_rate"]

    best_row, best_score = None, -1
    for row in rows:
        score, mismatch = 0, False
        for var_name, fieldname in dim_fieldnames.items():
            row_val = row.get(fieldname)
            if not row_val:
                continue  # dòng không set field này -> bỏ qua, không loại
            if str(row_val) == str(inputs.get(var_name, "")):
                score += 1
            else:
                mismatch = True
                break
        if mismatch:
            continue
        if score > best_score:
            best_score, best_row = score, row

    if best_row:
        return best_row["price_list_rate"]

    # Fallback: dòng không set field composite nào (giá mặc định)
    for row in rows:
        if all(not row.get(fn) for fn in dim_fieldnames.values()):
            return row["price_list_rate"]

    return None
