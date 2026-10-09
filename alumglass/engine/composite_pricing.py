# -*- coding: utf-8 -*-
"""Thuật toán match Item Price theo composite key (Pricing Dimension) —
DÙNG CHUNG giữa 2 nhánh resolve giá:
  - BomOrchestrator._fetch_composite_prices() (nhánh fallback, luôn chạy)
  - fb_handlers.aluminum_price_composite() (nhánh FB-max, chạy khi FVB seed D3)

Trước đây 2 nhánh có 2 thuật toán KHÁC NHAU (fallback = best-partial-match,
FB-max/exact_match = AND cứng qua query filter) → hành vi tra giá composite
ĐỔI KHÁC khi chuyển từ nhánh này sang nhánh kia (xem ghi nhận audit 2026-08).
Gộp về đây để 2 nhánh LUÔN cho cùng kết quả, sửa 1 chỗ áp dụng cả 2 nơi.

Từ bản vá F5-3/F5-4/F5-7 (audit 2026-10), module này giữ thêm 2 nhóm hàm DÙNG
CHUNG cho cả 2 nhánh (cùng lý do: sửa 1 chỗ áp dụng cả 2 nơi):
  - lọc dòng Item Price dùng được: còn hiệu lực (valid_from/valid_upto) +
    đúng tiền tệ + chọn dòng giá GỐC cho multiplier_chain;
  - túi cảnh báo engine (không tìm được giá / thiếu dòng giá gốc / mã rule
    sai) — fb_handlers chạy trong cùng tiến trình với BomOrchestrator nhưng
    KHÔNG có tham chiếu tới instance, nên cần 1 chỗ chung để lỗi không biến mất.

Module KHÔNG import frappe ở cấp module (chỉ import trong hàm) để giữ nguyên
khả năng import thuần Python của test standalone.
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


# ══════════════════════════════════════════════════════════════════════
# F2/D9 — Túi cảnh báo engine dùng chung
# ══════════════════════════════════════════════════════════════════════
# Treo trên frappe.local (phạm vi 1 request) để không rò cảnh báo sang lần
# tính tiếp theo trong cùng worker bench. BomOrchestrator hút túi này về
# `bom_engine_errors`/`cost_engine_errors` (xem _drain_engine_warnings) rồi
# ghi vào `al_bom_result["errors"]` — lỗi không còn biến mất im lặng.
_WARNING_SINK_ATTR = "_alumglass_engine_warnings"


def _frappe_local():
    """frappe.local nếu có — test stub không có thì trả None (mọi hàm dưới
    vẫn chạy an toàn, chỉ là cảnh báo không được giữ lại)."""
    try:
        import frappe
        return getattr(frappe, "local", None)
    except Exception:
        return None


def add_engine_warning(key, message):
    """Ghi 1 cảnh báo engine (key → message), KHÔNG throw, KHÔNG đổi luồng tính."""
    store = _frappe_local()
    if store is None:
        return
    try:
        bag = getattr(store, _WARNING_SINK_ATTR, None)
        if bag is None:
            bag = {}
            setattr(store, _WARNING_SINK_ATTR, bag)
        bag[key] = message
    except Exception:
        # Túi cảnh báo không được phép làm chết luồng tính giá
        pass


def drain_engine_warnings():
    """Lấy HẾT cảnh báo ra khỏi túi và xoá túi (dict rỗng nếu không có gì)."""
    store = _frappe_local()
    if store is None:
        return {}
    try:
        bag = getattr(store, _WARNING_SINK_ATTR, None) or {}
        setattr(store, _WARNING_SINK_ATTR, {})
        return dict(bag)
    except Exception:
        return {}


def _local_cache(attr):
    """dict cache treo trên frappe.local (None nếu không có frappe.local).

    fb_handlers được FB resolver gọi theo TỪNG dòng nên các lookup tiền tệ phải
    cache theo request, tránh N+1 query (xem fb_config.frappe.local._al_named_
    constant_cache — cùng cách làm trong app này).
    """
    store = _frappe_local()
    if store is None:
        return None
    try:
        cache = getattr(store, attr, None)
        if cache is None:
            cache = {}
            setattr(store, attr, cache)
        return cache
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════
# F5-3 — Lọc dòng Item Price dùng được (tiền tệ + thời hạn hiệu lực)
# ══════════════════════════════════════════════════════════════════════
def today_iso():
    """Ngày hôm nay dạng 'YYYY-MM-DD'. Ưu tiên nowdate() (timezone site),
    fallback stdlib khi frappe.utils không có nowdate (test stub)."""
    try:
        from frappe.utils import nowdate
        return nowdate()
    except Exception:
        import datetime
        return datetime.date.today().strftime("%Y-%m-%d")


def _as_iso_date(value):
    """Chuẩn hoá giá trị Date (str / datetime.date / None) → 'YYYY-MM-DD'."""
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def row_is_current(row, today):
    """Dòng Item Price còn hiệu lực tại ngày `today` (valid_from/valid_upto).

    ERPNext cho phép để TRỐNG cả 2 field (dòng giá vô thời hạn) — dòng trống
    PHẢI được chấp nhận, nếu không mọi bảng giá không khai thời hạn sẽ mất
    giá (về 0). Dòng có khai thời hạn mà đã hết hạn / chưa tới hạn → loại.
    So sánh chuỗi ISO 'YYYY-MM-DD' nên không phụ thuộc kiểu trả về của DB.
    """
    valid_from = _as_iso_date(row.get("valid_from"))
    if valid_from and valid_from > today:
        return False
    valid_upto = _as_iso_date(row.get("valid_upto"))
    if valid_upto and valid_upto < today:
        return False
    return True


def filter_price_rows(rows, currency=None, today=None):
    """Giữ lại các dòng Item Price DÙNG ĐƯỢC: còn hiệu lực + đúng tiền tệ.

    currency: tiền tệ cần lọc (xem currency_filter_value) — None = không lọc
    tiền tệ (giữ hành vi cũ). Dòng chưa khai `currency` (data nhập tay/legacy)
    vẫn được giữ: NULL-tolerant, tránh mất giá vì field trống.

    Trả về [] khi không còn dòng nào → caller phải BÁO THIẾU GIÁ (F5-7), không
    được âm thầm dùng dòng đã hết hạn.
    """
    today = today or today_iso()
    out = []
    for row in rows or []:
        if not row_is_current(row, today):
            continue
        if currency:
            row_currency = row.get("currency")
            if row_currency and row_currency != currency:
                continue
        out.append(row)
    return out


def currency_filter_value(price_list, doc_currency):
    """Tiền tệ dùng để lọc Item Price — None nghĩa là KHÔNG lọc (hành vi cũ).

    CHỈ lọc khi tiền tệ của Price List KHỚP tiền tệ của báo giá (hoặc Price
    List chưa khai currency). Lệch nhau = site cấu hình bảng giá khác tiền tệ
    báo giá: lọc theo báo giá sẽ ra 0 dòng → giá 0 im lặng (đúng lỗi F5-7 đang
    sửa), nên giữ nguyên hành vi cũ + ghi Error Log để người vận hành xử lý.
    """
    if not price_list or not doc_currency:
        return None
    try:
        import frappe
    except Exception:
        return None
    # Cache theo request: fb_handlers được FB resolver gọi theo từng dòng hàng,
    # không cache thì mỗi dòng tốn thêm 1 query Price List. Cache cả kết quả
    # lệch tiền tệ để Error Log chỉ ghi 1 lần cho mỗi cặp bảng giá/tiền tệ.
    cache = _local_cache("_alumglass_currency_filter_cache")
    cache_key = (price_list, doc_currency)
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    result = None
    try:
        pl_currency = frappe.db.get_value("Price List", price_list, "currency")
    except Exception:
        pl_currency = None
    if pl_currency and pl_currency == doc_currency:
        result = pl_currency   # khớp → lọc dòng giá theo đúng tiền tệ này
    elif pl_currency:
        try:
            frappe.log_error(
                title="AlumGlass: bảng giá KHÁC tiền tệ báo giá",
                message=(
                    "Price List '%s' dùng tiền tệ %s nhưng báo giá dùng %s — KHÔNG "
                    "lọc Item Price theo tiền tệ (giữ hành vi cũ) để tránh giá 0 "
                    "im lặng. Kiểm tra lại bảng giá / Selling Settings."
                    % (price_list, pl_currency, doc_currency)
                ),
            )
        except Exception:
            pass
    # pl_currency rỗng (Price List chưa khai currency) → result = None, không lọc
    if cache is not None:
        cache[cache_key] = result
    return result


# ══════════════════════════════════════════════════════════════════════
# F5-4 — Chọn dòng giá GỐC cho multiplier_chain
# ══════════════════════════════════════════════════════════════════════
def pick_base_price(rows, dim_fieldnames):
    """Chọn giá GỐC của 1 item trong bảng giá — trả (price, is_base_row).

    Giá gốc = dòng KHÔNG set field composite nào (dòng "trần"). Trước bản vá,
    caller lấy dòng Item Price ĐẦU TIÊN (`setdefault`) → có thể vô tình lấy
    dòng giá composite (đã gồm phụ phí màu/độ dày) làm giá gốc rồi nhân
    multiplier thêm lần nữa.

    Không có dòng "trần" → trả dòng đầu tiên + is_base_row=False (giữ hành vi
    cũ, tránh giá 0) để caller ghi cảnh báo.
    """
    if not rows:
        return None, False
    for row in rows:
        if all(not row.get(fn) for fn in (dim_fieldnames or {}).values()):
            return row.get("price_list_rate"), True
    return rows[0].get("price_list_rate"), False
