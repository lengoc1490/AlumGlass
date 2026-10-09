"""FB Handlers — Thin layer đăng ký custom data sources với Formula Builder.

AlumGlass không tự code batch query, cache, transform.
Mọi thứ ủy thác cho FB BatchBindingResolver + SourceTypeRegistry.

Mỗi handler = 1 data source type. Đăng ký qua @register_source + hooks.py fb_source_types.

C2 (v28_11): đã GỠ handler gom cost bucket viết tay (deprecated) — việc gom
line_total theo cost_bucket giờ dùng source_type CHUẨN `aggregate_from_items`
của platform (FVB config đã migrate qua patch v28_11). Chỉ còn 2 handler đăng
ký ở đây.
"""

from formula_builder.api.source_type_registry import register_source


def _doc_currency(doc):
    """Tiền tệ của báo giá đang tính — "" khi không xác định được (KHÔNG lọc).

    Nguồn theo thứ tự: doc.currency → Quotation (doc.parent) → Global Defaults.
    Cache theo request vì FB resolver gọi handler theo TỪNG dòng hàng, không
    cache thì mỗi dòng tốn thêm query (xem composite_pricing._local_cache).
    """
    import frappe
    from alumglass.engine.composite_pricing import _local_cache

    co_doc = doc is not None and hasattr(doc, "get")
    parent = (doc.get("parent") if co_doc else None) or "current"
    cache = _local_cache("_alumglass_doc_currency_cache")
    if cache is not None and parent in cache:
        return cache[parent]

    currency = doc.get("currency") if co_doc else None
    try:
        if not currency and parent != "current":
            currency = frappe.db.get_value("Quotation", parent, "currency")
        if not currency:
            currency = frappe.db.get_single_value(
                "Global Defaults", "default_currency")
    except Exception as exc:
        # D9: mất nguồn tiền tệ chỉ làm mất bộ lọc tiền tệ (KHÔNG chết BOM)
        # nhưng phải để lại dấu vết thay vì nuốt im lặng.
        frappe.logger("alumglass").error(
            "AlumGlass: không resolve được tiền tệ báo giá "
            "(aluminum_price_composite) — %s" % exc)
        currency = None
    currency = currency or ""
    if cache is not None:
        cache[parent] = currency
    return currency


@register_source(
    "aluminum_price_composite",
    label="Aluminum Price (Composite Key)",
    description=(
        "Tra giá nhôm theo composite key từ AL Variable Dimension Mapping. "
        "Hỗ trợ 2 mode (source_config.pricing_mode): "
        "'exact_match' — lookup chính xác trên Item Price theo composite key; "
        "'multiplier_chain' — base price × ∏(multipliers theo dimensions). "
        "Thêm pricing dimension mới = 1 AL Pricing Dimension + 1 Mapping record."
    ),
    config_schema={
        "type": "object",
        "properties": {
            "price_list": {"type": "string", "description": "Price list (vd 'Standard Selling')"},
            "material_category": {"type": "string", "description": "Lọc AL Variable Dimension Mapping theo material_category"},
            "pricing_mode": {
                "type": "string",
                "enum": ["exact_match", "multiplier_chain"],
                "description": "exact_match: lookup chính xác; multiplier_chain: base price × chain",
            },
        },
    },
    app="alumglass",
    version="1.0",
    batchable=True,
    fingerprint_fn=lambda cfg: "aluminum_price_composite:" + cfg.get("price_list", "") + "|" + cfg.get("material_category", ""),
    supports_cache=True,
    default_cache_ttl=300,
)
def aluminum_price_composite(binding, doc, resolved_so_far):
    """Tra giá nhôm theo composite key (DATA-DRIVEN từ AL Variable Dimension Mapping).

    Hỗ trợ 2 chế độ (source_config.pricing_mode):
    - "exact_match" (default): Composite key lookup chính xác trên Item Price
    - "multiplier_chain": Base price × ∏(multipliers từ dimensions)

    Thêm pricing dimension mới = 1 AL Pricing Dimension + 1 Mapping record.
    """
    import json
    import frappe

    cfg = json.loads(binding.get("source_config", "{}")) if isinstance(
        binding.get("source_config"), str) else (binding.get("source_config") or {})

    item_code = resolved_so_far.get("price_base_item") or binding.get("item_code", "")
    category = resolved_so_far.get("category") or cfg.get("material_category", "")
    pricing_mode = cfg.get("pricing_mode", "exact_match")

    # ── Load mappings + dimensions (dùng chung cho cả 2 mode) ──────
    mapping_filters = {"is_active": 1}
    if category:
        mapping_filters["material_category"] = category

    mappings = frappe.get_all("AL Variable Dimension Mapping",
                               filters=mapping_filters,
                               fields=["variable_name", "pricing_dimension",
                                       "price_multiplier"])

    dims = {}
    if mappings:
        dim_codes = list({m["pricing_dimension"] for m in mappings})
        for d in frappe.get_all("AL Pricing Dimension",
                                 filters={"name": ("in", dim_codes)},
                                 fields=["name", "custom_fieldname", "link_doctype"]):
            dims[d["name"]] = d

    # ═══════════════════════════════════════════════════════════════
    # Field query + fieldname dimension DÙNG CHUNG cho cả 2 mode:
    # exact_match cần để match composite key; multiplier_chain cần để nhận
    # diện dòng giá GỐC không gắn dimension (F5-4). Thêm currency/valid_from/
    # valid_upto để lọc dòng còn dùng được (F5-3).
    # ═══════════════════════════════════════════════════════════════
    from alumglass.engine.composite_pricing import (
        add_engine_warning, best_partial_match, currency_filter_value,
        filter_price_rows, pick_base_price,
    )

    price_list = cfg.get("price_list", "Standard Selling")
    dim_fieldnames = {}
    select_fields = ["name", "price_list_rate", "currency", "valid_from", "valid_upto"]
    for m in mappings:
        dim = dims.get(m["pricing_dimension"])
        cfn = dim.get("custom_fieldname", "") if dim else ""
        if not cfn:
            continue
        dim_fieldnames[m["variable_name"]] = cfn
        if cfn not in select_fields:
            select_fields.append(cfn)

    # F5-3: bỏ dòng Item Price hết hiệu lực / khác tiền tệ. NULL-tolerant —
    # dòng không khai valid_from/valid_upto/currency vẫn được giữ. None = không
    # lọc (Price List chưa khai currency, hoặc khác tiền tệ báo giá → có
    # Error Log, xem composite_pricing.currency_filter_value).
    price_currency = currency_filter_value(price_list, _doc_currency(doc))

    # ═══════════════════════════════════════════════════════════════
    # MODE 1: EXACT MATCH — composite key lookup, best-partial-match
    # (V6 P10: đồng bộ với BomOrchestrator._match_composite_price — trước
    # đây là AND cứng qua DB filter, đổi hành vi khi chuyển từ fallback
    # sang FB-max lúc FVB seed D3. Dùng chung engine/composite_pricing để
    # 2 nhánh luôn cho cùng kết quả.)
    # ═══════════════════════════════════════════════════════════════
    if pricing_mode == "exact_match":
        rows = frappe.get_all(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list},
            fields=select_fields,
        )
        rows = filter_price_rows(rows, currency=price_currency)
        price = best_partial_match(rows, dim_fieldnames, resolved_so_far)
        if price is None:
            # F5-7: không match / hết hạn KHÔNG được trả 0 im lặng — ghi cảnh
            # báo vào túi lỗi engine (hiện ở kết quả BOM) rồi vẫn trả 0 để
            # không làm chết luồng tính.
            add_engine_warning(
                "thieu_gia_item:%s" % item_code,
                "Không có dòng Item Price còn hiệu lực khớp composite key cho "
                "item '%s' (bảng giá '%s') — tạm tính 0. Kiểm tra giá / khai "
                "báo pricing dimension cho item này."
                % (item_code, price_list),
            )
            return 0
        return price

    # ═══════════════════════════════════════════════════════════════
    # MODE 2: MULTIPLIER CHAIN — base price × ∏(multipliers)
    # ═══════════════════════════════════════════════════════════════
    if pricing_mode == "multiplier_chain":
        # B1: giá GỐC = dòng KHÔNG gắn pricing dimension ("dòng trần"). Bản cũ
        # lấy dòng ĐẦU TIÊN (limit=1) nên có thể lấy nhầm dòng giá composite
        # rồi nhân multiplier thêm lần nữa (F5-4) → nay xét hết dòng.
        rows = frappe.get_all(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list},
            fields=select_fields,
        )
        rows = filter_price_rows(rows, currency=price_currency)
        base_price, is_base_row = pick_base_price(rows, dim_fieldnames)
        if not base_price:
            # F5-7: thiếu giá gốc phải BÁO, không trả 0 im lặng.
            add_engine_warning(
                "thieu_gia_goc:%s" % item_code,
                "Không có dòng Item Price còn hiệu lực cho item '%s' (bảng giá "
                "'%s') — không có giá gốc để nhân multiplier, tạm tính 0."
                % (item_code, price_list),
            )
            return 0
        if not is_base_row:
            add_engine_warning(
                "gia_goc_thieu_dong_tran:%s" % item_code,
                "Item '%s' không có dòng giá GỐC (dòng không gắn pricing "
                "dimension) trong bảng giá '%s' — tạm lấy dòng '%s' làm giá gốc "
                "rồi nhân multiplier, có thể tính trùng phụ phí."
                % (item_code, price_list, rows[0].get("name", "?")),
            )

        # B2: Apply multipliers chain
        total_multiplier = 1.0
        for m in mappings:
            var_value = resolved_so_far.get(m["variable_name"])
            if var_value is None or var_value == "":
                continue

            dim = dims.get(m["pricing_dimension"])
            if not dim:
                continue

            # Ưu tiên 1: multiplier từ Variable Dimension Mapping
            map_mult = m.get("price_multiplier", 1.0) or 1.0

            # Ưu tiên 2: nếu dimension link đến doctype có price_multiplier
            # (vd: AL Color Standard → price_multiplier cho từng màu cụ thể)
            linked_mult = None
            link_doctype = dim.get("link_doctype")
            if link_doctype and var_value:
                try:
                    linked_raw = frappe.get_cached_value(
                        link_doctype, var_value, "price_multiplier")
                    linked_mult = float(linked_raw) if linked_raw else None
                except Exception as exc:
                    # D9: nuốt im lặng ở đây từng che lỗi tra master data.
                    frappe.logger("alumglass").error(
                        "AlumGlass: không tra được price_multiplier của %s '%s' "
                        "(item '%s') — dùng multiplier từ mapping — %s"
                        % (link_doctype, var_value, item_code, exc))
                    linked_mult = None

            # F5-4: None = dimension CHƯA khai multiplier → lấy theo mapping.
            # Còn 1.0 THẬT (khai tay) phải được tôn trọng — bản cũ dùng
            # `linked_mult != 1.0` nên biến 1.0 thành map_mult.
            effective_mult = linked_mult if linked_mult is not None else map_mult
            total_multiplier *= effective_mult

        return base_price * total_multiplier

    # Fallback: pricing_mode lạ — trước đây trả 0 im lặng (F5-7 cùng loại).
    add_engine_warning(
        "pricing_mode_la:%s" % pricing_mode,
        "Item '%s' cấu hình pricing_mode '%s' không hỗ trợ (chỉ có "
        "'exact_match' / 'multiplier_chain') — tạm tính 0."
        % (item_code, pricing_mode),
    )
    return 0


@register_source(
    "glass_master_data",
    label="Glass Master Data",
    description=(
        "Tra cứu thông số kỹ thuật kính (glass_thick, glass_type) từ AL Glass Master. "
        "Dùng cho Bom Item dòng KINH để resolve Dynamic Item Rule input."
    ),
    config_schema={
        "type": "object",
        "properties": {
            "glass_code": {"type": "string", "description": "Mã AL Glass Master (fallback khi resolved_so_far/binding không có)"},
        },
    },
    app="alumglass",
    version="1.0",
    batchable=True,
    fingerprint_fn=lambda cfg: "glass_master_data:" + cfg.get("glass_code", ""),
    supports_cache=True,
    default_cache_ttl=3600,
)
def glass_master_data(binding, doc, resolved_so_far):
    """Tra cứu thông số kỹ thuật kính (glass_thick, glass_type).

    Dùng cho Bom Item dòng KINH để resolve Dynamic Item Rule input.
    """
    import frappe

    glass_code = resolved_so_far.get("default_glass_master") or binding.get("item_code", "")
    if not glass_code:
        return {"glass_thick": 0, "glass_type": ""}

    # Dùng get_cached_value cho read-only master data
    gm = frappe.get_cached_value("AL Glass Master", glass_code,
                                  ["total_thick_mm", "glass_type"], as_dict=True)
    if gm:
        return {"glass_thick": gm.get("total_thick_mm", 0),
                "glass_type": gm.get("glass_type", "")}
    return {"glass_thick": 0, "glass_type": ""}
