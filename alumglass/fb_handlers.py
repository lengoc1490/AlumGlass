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
    mapping_filters = {}
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
    # MODE 1: EXACT MATCH — composite key lookup, best-partial-match
    # (V6 P10: đồng bộ với BomOrchestrator._match_composite_price — trước
    # đây là AND cứng qua DB filter, đổi hành vi khi chuyển từ fallback
    # sang FB-max lúc FVB seed D3. Dùng chung engine/composite_pricing để
    # 2 nhánh luôn cho cùng kết quả.)
    # ═══════════════════════════════════════════════════════════════
    if pricing_mode == "exact_match":
        from alumglass.engine.composite_pricing import best_partial_match

        dim_fieldnames = {}
        select_fields = ["name", "price_list_rate"]
        for m in mappings:
            dim = dims.get(m["pricing_dimension"])
            cfn = dim.get("custom_fieldname", "") if dim else ""
            if not cfn:
                continue
            dim_fieldnames[m["variable_name"]] = cfn
            if cfn not in select_fields:
                select_fields.append(cfn)

        rows = frappe.get_all(
            "Item Price",
            filters={
                "item_code": item_code,
                "price_list": cfg.get("price_list", "Standard Selling"),
            },
            fields=select_fields,
        )
        price = best_partial_match(rows, dim_fieldnames, resolved_so_far)
        return price if price is not None else 0

    # ═══════════════════════════════════════════════════════════════
    # MODE 2: MULTIPLIER CHAIN — base price × ∏(multipliers)
    # ═══════════════════════════════════════════════════════════════
    if pricing_mode == "multiplier_chain":
        # B1: Get base price (chỉ theo item_code + price_list)
        base_filters = [
            ["item_code", "=", item_code],
            ["price_list", "=", cfg.get("price_list", "Standard Selling")],
        ]
        base_prices = frappe.get_all("Item Price", filters=base_filters,
                                      fields=["price_list_rate"], limit=1)
        base_price = base_prices[0]["price_list_rate"] if base_prices else 0
        if not base_price:
            return 0

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
            linked_mult = 1.0
            link_doctype = dim.get("link_doctype")
            if link_doctype and var_value:
                try:
                    linked_mult = frappe.get_cached_value(
                        link_doctype, var_value, "price_multiplier") or 1.0
                except Exception:
                    linked_mult = 1.0

            # Sử dụng multiplier khác 1.0 (ưu tiên linked, fallback mapping)
            effective_mult = linked_mult if linked_mult != 1.0 else map_mult
            total_multiplier *= effective_mult

        return base_price * total_multiplier

    # Fallback
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
