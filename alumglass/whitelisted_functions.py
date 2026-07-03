"""
AlumGlass ERP v17.0 — Whitelisted Functions
Strict whitelist for custom_function source type in Formula Variable Binding.
Only functions registered here can be called via the formula_builder's
custom_function handler when source_config references alumglass scope.

Security: This is the single source of truth for allowed custom functions.
Any function NOT in this registry will be rejected at runtime.
"""
import frappe
from frappe.utils import flt, cint, nowdate, today

# ============================================================
# WHITELIST REGISTRY
# ============================================================
# Format: { "function_name": callable }
# Functions are referenced by name in Formula Variable Binding source_config:
#   {"scope": "alumglass", "function": "get_aluminum_market_price", "args": [...]}

WHITELISTED_FUNCTIONS = {}


def register(name):
    """Decorator to register a whitelisted function."""
    def wrapper(fn):
        WHITELISTED_FUNCTIONS[name] = fn
        return fn
    return wrapper


# ============================================================
# WHITELISTED FUNCTIONS — Master Data Lookups
# ============================================================

@register("get_aluminum_market_price")
def get_aluminum_market_price(brand, color):
    """Look up aluminum market price from AL Calculation Rule LOOKUP table.

    Uses rule_code TRA-GIA-NHOM to find unit price (per kg) for given brand + color.

    Args:
        brand: Brand code (e.g., "XF-NK", "ALUMIL")
        color: Color code (e.g., "STD", "DAK", "VG")

    Returns:
        float: Unit price per kg, or 0 if not found
    """
    lookup_rows = frappe.get_all(
        "AL Rule Lookup Row",
        filters={
            "parenttype": "AL Calculation Rule",
            "parentfield": "lookup_rows",
            "parent": "TRA-GIA-NHOM",
            "key_1": brand,
            "key_2": color,
        },
        fields=["result_value"],
        limit=1,
    )
    if lookup_rows:
        return flt(lookup_rows[0].result_value)
    # Fallback: try default
    default = frappe.db.get_value(
        "AL Calculation Rule", "TRA-GIA-NHOM", "lookup_default"
    )
    return flt(default or 0)


@register("get_glass_thickness")
def get_glass_thickness(glass_code):
    """Get total thickness of a glass master record.

    Args:
        glass_code: AL Glass Master code (e.g., "KINH-DON-8", "KINH-HOP-24")

    Returns:
        float: total_thick_mm, or 0 if not found
    """
    return flt(frappe.db.get_value(
        "AL Glass Master", glass_code, "total_thick_mm"
    ) or 0)


@register("get_item_kg_per_m")
def get_item_kg_per_m(item_code):
    """Get weight per meter (kg/m) of an aluminum profile item.

    Args:
        item_code: Item code

    Returns:
        float: al_kg_per_m value, or 0
    """
    return flt(frappe.db.get_value("Item", item_code, "al_kg_per_m") or 0)


@register("get_item_price")
def get_item_price(item_code, price_list=None):
    """Get item price from Item Price.

    Args:
        item_code: Item code
        price_list: Optional price list name (defaults to Standard Selling)

    Returns:
        float: price_list_rate, or 0
    """
    filters = {"item_code": item_code}
    if price_list:
        filters["price_list"] = price_list
    else:
        filters["selling"] = 1
    price = frappe.db.get_value(
        "Item Price",
        filters,
        "price_list_rate",
        order_by="valid_from desc",
    )
    return flt(price or 0)


@register("get_glass_price")
def get_glass_price(glass_code, price_list=None):
    """Get glass unit price (per m²) from Item Price.

    Args:
        glass_code: AL Glass Master code
        price_list: Optional price list

    Returns:
        float: price per m², or 0
    """
    item_code = frappe.db.get_value(
        "Item", {"al_glass_master": glass_code}, "name"
    )
    if not item_code:
        item_code = glass_code
    return get_item_price(item_code, price_list)


# ============================================================
# WHITELISTED FUNCTIONS — Rule Engine Lookups
# ============================================================

@register("lookup_rule_value")
def lookup_rule_value(rule_code, **keys):
    """Generic LOOKUP rule resolver.

    Looks up a value from AL Calculation Rule LOOKUP table based on key_1..key_3.

    Args:
        rule_code: AL Calculation Rule code
        **keys: key_1, key_2, key_3 values for matching

    Returns:
        Any: result_value from matching row, or lookup_default
    """
    filters = {
        "parenttype": "AL Calculation Rule",
        "parentfield": "lookup_rows",
        "parent": rule_code,
    }
    if "key_1" in keys and keys["key_1"]:
        filters["key_1"] = keys["key_1"]
    if "key_2" in keys and keys["key_2"]:
        filters["key_2"] = keys["key_2"]
    if "key_3" in keys and keys["key_3"]:
        filters["key_3"] = keys["key_3"]

    rows = frappe.get_all(
        "AL Rule Lookup Row",
        filters=filters,
        fields=["result_value"],
        limit=1,
    )
    if rows:
        return rows[0].result_value

    default = frappe.db.get_value(
        "AL Calculation Rule", rule_code, "lookup_default"
    )
    return default


@register("resolve_threshold")
def resolve_threshold(rule_code, input_value):
    """Resolve THRESHOLD rule.

    Args:
        rule_code: AL Calculation Rule code (rule_type = THRESHOLD)
        input_value: Float value to check against threshold ranges

    Returns:
        Any: result_value from matching range, or None
    """
    rows = frappe.get_all(
        "AL Rule Threshold Row",
        filters={
            "parenttype": "AL Calculation Rule",
            "parentfield": "threshold_rows",
            "parent": rule_code,
        },
        fields=["from_value", "to_value", "result_value"],
        order_by="from_value asc",
    )
    input_val = flt(input_value)
    for row in rows:
        from_val = flt(row.from_value)
        to_val = flt(row.to_value)
        if to_val == 0:
            # 0 means no upper limit
            if input_val >= from_val:
                return row.result_value
        elif from_val <= input_val <= to_val:
            return row.result_value
    return None


# ============================================================
# WHITELISTED FUNCTIONS — Business Logic Helpers
# ============================================================

@register("get_customer_group")
def get_customer_group(customer_name):
    """Get customer group for a given customer.

    Args:
        customer_name: Customer name

    Returns:
        str: customer_group value
    """
    return frappe.db.get_value("Customer", customer_name, "customer_group") or ""


@register("get_current_discount")
def get_current_discount(quotation_item_name):
    """Get current discount percentage applied to a quotation item.

    Args:
        quotation_item_name: Quotation Item name

    Returns:
        float: al_discount_pct value, or 0
    """
    return flt(frappe.db.get_value(
        "Quotation Item", quotation_item_name, "al_discount_pct"
    ) or 0)


@register("get_bom_version")
def get_bom_version(bom_code):
    """Get the current published version of a BOM.

    Args:
        bom_code: AL BOM code

    Returns:
        str: AL BOM Version name, or empty string
    """
    return frappe.db.get_value(
        "AL BOM", bom_code, "current_version"
    ) or ""


# ============================================================
# WHITELISTED FUNCTIONS — Date / Period
# ============================================================

@register("get_period_label")
def get_period_label(period_type):
    """Get current period label for KPI.

    Args:
        period_type: "MONTHLY", "QUARTERLY", or "YEARLY"

    Returns:
        str: Period label (e.g., "2026-06", "2026-Q2", "2026")
    """
    from datetime import date
    today_date = date.today()
    if period_type == "MONTHLY":
        return today_date.strftime("%Y-%m")
    elif period_type == "QUARTERLY":
        q = (today_date.month - 1) // 3 + 1
        return f"{today_date.year}-Q{q}"
    elif period_type == "YEARLY":
        return str(today_date.year)
    return ""


# ============================================================
# SECURITY: Resolve function call
# ============================================================

def resolve_custom_function(function_name, *args, **kwargs):
    """Securely resolve a whitelisted function call.

    This is called by the formula_builder's custom_function handler
    when source_type = "custom_function" and scope = "alumglass".

    Args:
        function_name: Name of the function to call
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Any: Function result

    Raises:
        ValueError: If function is not whitelisted
    """
    if function_name not in WHITELISTED_FUNCTIONS:
        frappe.log_error(
            title="AlumGlass Security: Unauthorized custom_function call",
            message=f"Function '{function_name}' is not in the whitelist. "
                    f"Args: {args}, Kwargs: {kwargs}"
        )
        raise ValueError(
            f"Custom function '{function_name}' is not whitelisted. "
            f"Only functions registered in alumglass/whitelisted_functions.py are allowed."
        )

    try:
        return WHITELISTED_FUNCTIONS[function_name](*args, **kwargs)
    except Exception as e:
        frappe.log_error(
            title=f"AlumGlass: Error in whitelisted function '{function_name}'",
            message=f"{e}\nArgs: {args}\nKwargs: {kwargs}"
        )
        raise
