"""
P0 — Custom source_type handlers for formula_builder's data_source_registry.

Đăng ký 2 handler AL-specific vào DATA_SOURCE_HANDLERS của formula_builder:
  - bom_variable       : thay thế AL source_type "BOM Variable"
  - rule_engine_lookup : thay thế AL source_type "Rule Engine Result"

Được gọi từ alumglass.modules.__init__ tại app startup.
"""
import frappe
import json
from frappe.utils import flt


def _handle_bom_variable(binding, doc, resolved_so_far):
    """Resolve BOM variable từ al_bom_vars JSON của quotation_item.

    source_config format:
        {"var_code": "n_canh", "default": 1}
    """
    config = _safe_json(binding.get("source_config"))
    var_code = config.get("var_code", "")
    default = config.get("default")

    bom_vars = doc.get("al_bom_vars", {})
    if isinstance(bom_vars, str):
        try:
            bom_vars = json.loads(bom_vars)
        except (json.JSONDecodeError, TypeError):
            bom_vars = {}

    val = bom_vars.get(var_code, default)
    return _cast(val, binding.get("data_type", "Float"))


def _handle_rule_engine_lookup(binding, doc, resolved_so_far):
    """Resolve LOOKUP rule từ AL Calculation Rule.

    source_config format:
        {
            "rule_code": "TRA-GIA-NHOM",
            "arg_mapping": {
                "key_1": "brand",
                "key_2": "mau_nhom"
            }
        }
    """
    config = _safe_json(binding.get("source_config"))
    rule_code = config.get("rule_code", "")

    if not rule_code:
        return None

    rule = frappe.db.get_value(
        "AL Calculation Rule",
        {"rule_code": rule_code, "rule_type": "LOOKUP", "is_active": 1},
        ["name", "lookup_default"],
        as_dict=True,
    )
    if not rule:
        return None

    arg_mapping = config.get("arg_mapping", {})
    key_values = {}
    for key_name, var_name in arg_mapping.items():
        key_values[key_name] = resolved_so_far.get(var_name, "")

    lookup_rows = frappe.get_all(
        "AL Rule Lookup Row",
        filters={"parent": rule.name},
        fields=["key_1", "key_2", "key_3", "result_value"],
    )

    for row in lookup_rows:
        match = True
        for i in range(1, 4):
            lookup_key = row.get(f"key_{i}")
            input_key = key_values.get(f"key_{i}")
            if lookup_key and input_key and str(input_key) != str(lookup_key):
                match = False
                break
        if match:
            return _cast(row.result_value, binding.get("data_type", "Float"))

    return _cast(rule.lookup_default, binding.get("data_type", "Float"))


def register_handlers():
    """Đăng ký custom handlers vào formula_builder's data_source_registry.
    Gọi 1 lần khi app startup.
    """
    try:
        from formula_builder.api.data_source_registry import DATA_SOURCE_HANDLERS

        if "bom_variable" not in DATA_SOURCE_HANDLERS:
            DATA_SOURCE_HANDLERS["bom_variable"] = _handle_bom_variable

        if "rule_engine_lookup" not in DATA_SOURCE_HANDLERS:
            DATA_SOURCE_HANDLERS["rule_engine_lookup"] = _handle_rule_engine_lookup

        frappe.logger().info(
            "AlumGlass: Registered custom FB handlers: bom_variable, rule_engine_lookup"
        )
    except ImportError:
        frappe.logger().warning(
            "AlumGlass: formula_builder not available — custom handlers skipped"
        )
    except Exception as e:
        frappe.log_error(
            title="AlumGlass FB handler registration failed",
            message=str(e),
        )


def _safe_json(val):
    """Parse JSON safely."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _cast(val, dtype):
    """Cast value theo data_type của FB."""
    if val is None:
        return None
    dtype = (dtype or "").lower()
    if dtype in ("float", "currency", "percent"):
        return flt(val)
    elif dtype in ("int",):
        return int(flt(val))
    elif dtype in ("check",):
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes")
        return bool(val)
    return val
