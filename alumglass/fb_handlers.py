"""FB Handlers — Thin layer đăng ký custom data sources với Formula Builder.

AlumGlass không tự code batch query, cache, transform.
Mọi thứ ủy thác cho FB BatchBindingResolver + SourceTypeRegistry.

Mỗi handler = 1 data source type. Đăng ký qua hooks.py fb_source_types.
"""


def aluminum_price_composite(binding, doc, resolved_so_far):
    """Tra giá nhôm theo composite key (DATA-DRIVEN từ AL Variable Dimension Mapping).

    Composite key được khám phá động:
    1. Đọc AL Variable Dimension Mapping để biết variable → pricing dimension
    2. Đọc AL Pricing Dimension để biết custom field name
    3. Build filter động dựa trên các biến đã resolve

    Thêm pricing dimension mới = 1 AL Pricing Dimension + 1 Mapping record.
    """
    import json
    import frappe

    cfg = json.loads(binding.get("source_config", "{}")) if isinstance(
        binding.get("source_config"), str) else (binding.get("source_config") or {})

    item_code = resolved_so_far.get("price_base_item") or binding.get("item_code", "")
    category = resolved_so_far.get("category") or cfg.get("material_category", "")

    filters = [
        ["item_code", "=", item_code],
        ["price_list", "=", cfg.get("price_list", "Standard Selling")],
    ]

    # ── Khám phá composite key động từ AL Variable Dimension Mapping ──
    mapping_filters = {}
    if category:
        mapping_filters["material_category"] = category

    mappings = frappe.get_all("AL Variable Dimension Mapping",
                               filters=mapping_filters,
                               fields=["variable_name", "pricing_dimension"])

    if mappings:
        # Batch query pricing dimensions để lấy custom_fieldname
        dim_codes = list({m["pricing_dimension"] for m in mappings})
        dims = {}
        for d in frappe.get_all("AL Pricing Dimension",
                                 filters={"name": ("in", dim_codes)},
                                 fields=["name", "custom_fieldname"]):
            dims[d["name"]] = d.get("custom_fieldname", "")

        for m in mappings:
            cfn = dims.get(m["pricing_dimension"])
            if not cfn:
                continue
            value = resolved_so_far.get(m["variable_name"])
            if value is None or value == "":
                continue
            filters.append([cfn, "=", value])

    prices = frappe.get_all("Item Price", filters=filters,
                             fields=["price_list_rate"], limit=1)
    return prices[0]["price_list_rate"] if prices else 0


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


def cost_bucket_aggregate(binding, doc, resolved_so_far):
    """Gom line_total theo cost_bucket từ Bom Items.

    Dùng cho Cost Bucket có source_type = 'aggregate_from_items'.
    """
    import json
    import frappe
    from collections import defaultdict

    cfg = json.loads(binding.get("source_config", "{}")) if isinstance(
        binding.get("source_config"), str) else (binding.get("source_config") or {})

    filter_by = cfg.get("filter_by", {})
    sum_field = cfg.get("sum_field", "line_total")

    # Lấy Bom Items từ snapshot
    bom_version = resolved_so_far.get("bom_version")
    if not bom_version:
        return 0

    # Dùng get_cached_value
    snap = frappe.get_cached_value("AL BOM Version", bom_version, "bom_set_snapshot")
    if not snap:
        return 0

    items = json.loads(snap).get("items", []) if isinstance(snap, str) else snap.get("items", [])

    total = 0.0
    for item in items:
        if filter_by:
            # Hỗ trợ multi-field filter
            matches = True
            for f_key, f_val in filter_by.items():
                if item.get(f_key) != f_val:
                    matches = False
                    break
            if not matches:
                continue
        total += item.get(sum_field, 0) or 0

    return total
