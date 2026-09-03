"""AlumGlass — Auto-seed Formula Variable Binding cho composite pricing.

★ NGUYÊN TẮC: "tận dụng tối đa formula_builder" — nghĩa là đường FB-max
(`bom_orchestrator._fetch_composite_prices_via_fb`, gọi qua
`formula_builder.api.batch_binding_resolver.resolve_all_bindings_batch`)
phải là đường chạy CHÍNH trong vận hành thật, không phải 1 nhánh "chờ D3"
mãi mãi. Trước bản fix này, không có gì tự tạo record `Formula Variable
Binding` cho pricing — `_get_pricing_bindings()` luôn trả `[]` (vì chưa ai
tạo tay), nên `_fetch_composite_prices_via_fb()` luôn trả `None`, và HỆ
THỐNG LUÔN CHẠY NHÁNH FALLBACK PYTHON (`_fetch_composite_prices`) — dù code
FB-max đã viết đầy đủ, đúng, sẵn sàng dùng. "Chờ seed D3" không nên là 1
trạng thái vĩnh viễn cho 1 tính năng lõi (tra giá) — seed NGAY ở đây, idempotent,
tự chạy mỗi migrate, không cần thao tác tay.

★ KHÔNG cần chờ FVB seed thủ công từ AL Variable Library nữa (đó là patch D3
cũ, dùng cho system variable — OFFSET_FRAME/NC_SX_PCT... — mục đích KHÁC,
xem `system_variable_resolver.py`). Binding ở đây RIÊNG cho composite pricing
(nhôm/kính mã đại diện), dùng handler `aluminum_price_composite` đã đăng ký
sẵn trong `fb_handlers.py`.

Sau khi seed xong, `_fetch_composite_prices()` (Python fallback trong
bom_orchestrator.py) về lý thuyết không còn được gọi trong vận hành bình
thường — chỉ là lưới an toàn nếu ai vô hiệu hóa/xóa binding này.
"""
import frappe

# Nguồn sự thật duy nhất cho tên biến + cấu hình binding composite pricing —
# `bom_orchestrator.py::_get_pricing_bindings()` lọc theo đúng source_type
# này (`_PRICING_SOURCE_TYPES`).
#
# ★ FIX C5 (Phase 0 — đồng bộ price_list seed binding): source_config KHÔNG
# hardcode "price_list" ở đây nữa — install_composite_pricing_binding() tự
# điền price_list ĐỘNG tại lúc seed bằng ĐÚNG hàm `_default_price_list()` mà
# engine (`bom_orchestrator._fetch_composite_prices*`, nhánh Python fallback)
# dùng — 2 đường FB-max lẫn fallback LUÔN đọc cùng 1 nguồn (Selling
# Settings.selling_price_list), không thể lệch số khi bảng giá đổi.
COMPOSITE_PRICING_BINDING = {
    "variable_name": "COMPOSITE_MATERIAL_PRICE",
    "variable_label": "Giá vật tư theo composite key (mã đại diện)",
    "source_type": "aluminum_price_composite",
    "source_config": {
        # price_list được điền ĐỘNG trong install_composite_pricing_binding()
        # (đọc Selling Settings qua bom_orchestrator._default_price_list) —
        # xem _resolve_seed_price_list() bên dưới. Không hardcode ở đây.
        "pricing_mode": "exact_match",
    },
    # applies_to_doctype="" (global) — binding này được gọi TRỰC TIẾP qua
    # resolve_all_bindings_batch(bindings, pre_resolved=row_ctx) với context
    # tự build mỗi dòng BOM, không qua resolution theo scope 1 document cụ
    # thể như FVB thường dùng.
    "applies_to_doctype": "",
    "is_global": 1,
    "is_active": 1,
    "resolve_priority": 100,
    "data_type": "Currency",
    "default_value": "0",
}


def _resolve_seed_price_list():
    """FIX C5 — price_list seed binding = ĐÚNG nguồn engine dùng.

    Engine nhánh Python fallback đọc `bom_orchestrator._default_price_list()`
    (Selling Settings.selling_price_list, fallback 'Standard Selling') ở mỗi
    lần tra giá. Binding FB-max phải seed cùng giá trị đó tại thời điểm seed
    (chạy mỗi migrate — idempotent, tự re-sync khi bảng giá trong Selling
    Settings đổi), KHÔNG hardcode 'Standard Selling' — nếu không 2 đường lại
    lệch số như finding C5 (de-xuat-cai-tien-quotation-pricing.md §3C).
    """
    try:
        from alumglass.engine.bom_orchestrator import _default_price_list
        return _default_price_list()
    except Exception:
        # bom_orchestrator chưa import được (formula_builder/engine đang
        # migrate dở) — fallback an toàn giữ hành vi mặc định ERPNext.
        return "Standard Selling"


def install_composite_pricing_binding():
    """Idempotent — tạo/cập nhật đúng 1 Formula Variable Binding cho composite
    pricing nếu chưa có (hoặc cấu hình bị sửa lệch khỏi khai báo ở trên).
    Gọi từ hooks.py::_after_migrate.
    """
    if not frappe.db.exists("DocType", "Formula Variable Binding"):
        # formula_builder chưa cài / chưa migrate xong — bỏ qua êm, sẽ tự
        # chạy lại ở lần migrate kế tiếp.
        return

    import json

    existing = frappe.db.get_value(
        "Formula Variable Binding",
        {"source_type": COMPOSITE_PRICING_BINDING["source_type"],
         "variable_name": COMPOSITE_PRICING_BINDING["variable_name"]},
        "name",
    )
    payload = dict(COMPOSITE_PRICING_BINDING)
    # FIX C5: điền price_list động (Selling Settings) — xem _resolve_seed_price_list().
    payload["source_config"] = dict(payload["source_config"])
    payload["source_config"]["price_list"] = _resolve_seed_price_list()
    payload["source_config"] = json.dumps(payload["source_config"])

    if existing:
        doc = frappe.get_doc("Formula Variable Binding", existing)
        changed = False
        for k, v in payload.items():
            if doc.get(k) != v:
                doc.set(k, v)
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
        return

    doc = frappe.new_doc("Formula Variable Binding")
    doc.update(payload)
    doc.insert(ignore_permissions=True)
