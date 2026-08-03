"""FB Handlers — Thin layer đăng ký custom data sources với Formula Builder.

AlumGlass không tự code batch query, cache, transform.
Mọi thứ ủy thác cho FB BatchBindingResolver + SourceTypeRegistry.

Mỗi handler = 1 data source type. Đăng ký qua hooks.py fb_source_types.
"""


def aluminum_price_composite(binding, doc, resolved_so_far):
    """Tra giá nhôm theo composite key (màu + xuất xứ + độ dày + bề mặt).

    Đây là nơi DUY NHẤT định nghĩa logic tra giá composite.
    Mọi thứ khác (batch, cache, transform) do FB lo.
    """
    import json
    import frappe

    cfg = json.loads(binding.get("source_config", "{}")) if isinstance(
        binding.get("source_config"), str) else (binding.get("source_config") or {})

    item_code = resolved_so_far.get("price_base_item") or binding.get("item_code", "")
    color = resolved_so_far.get("aluminum_color", "WHITE")
    origin = resolved_so_far.get("aluminum_origin", "IMPORT")
    thickness = resolved_so_far.get("aluminum_thickness", 20)
    surface = resolved_so_far.get("aluminum_surface", "POWDER_COATED")

    # Query Item Price với composite key
    filters = [
        ["item_code", "=", item_code],
        ["price_list", "=", cfg.get("price_list", "Standard Selling")],
    ]
    # Custom fields cho composite key
    if frappe.db.exists("Custom Field", {"dt": "Item Price", "fieldname": "custom_color"}):
        filters.append(["custom_color", "=", color])
    if frappe.db.exists("Custom Field", {"dt": "Item Price", "fieldname": "custom_origin"}):
        filters.append(["custom_origin", "=", origin])
    if frappe.db.exists("Custom Field", {"dt": "Item Price", "fieldname": "custom_thickness"}):
        filters.append(["custom_thickness", "=", thickness])
    if frappe.db.exists("Custom Field", {"dt": "Item Price", "fieldname": "custom_surface_finish"}):
        filters.append(["custom_surface_finish", "=", surface])

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

    gm = frappe.db.get_value("AL Glass Master", glass_code,
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

    snap = frappe.db.get_value("AL BOM Version", bom_version, "bom_set_snapshot")
    if not snap:
        return 0

    items = json.loads(snap).get("items", []) if isinstance(snap, str) else snap.get("items", [])

    total = 0.0
    for item in items:
        # Filter theo category nếu có
        if filter_by:
            cat = item.get("category", "")
            if filter_by.get("category") and cat != filter_by["category"]:
                continue
        total += item.get(sum_field, 0) or 0

    return total
