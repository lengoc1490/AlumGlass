"""
P0 Migration: Chuyển AL Variable Binding → Formula Variable Binding
+ Tạo Formula Global Variable từ AL Calculation Rule CONSTANT
Chạy an toàn — không xóa data cũ, tạo mới song song.
"""
import frappe
import json


def execute():
    """Chạy migration P0."""
    count_bindings = _migrate_bindings()
    count_globals = _migrate_constant_rules()
    frappe.db.commit()
    print(f"\nP0 Migration complete:")
    print(f"  - Formula Variable Bindings created: {count_bindings}")
    print(f"  - Formula Global Variables created: {count_globals}")


def _migrate_bindings():
    """Tạo Formula Variable Binding records từ AL Variable Binding."""
    al_bindings = frappe.get_all(
        "AL Variable Binding",
        filters={"is_active": 1},
        fields=["*"],
    )
    count = 0

    for ab in al_bindings:
        # Map AL source_type → FB source_type
        source_type_map = {
            "Quotation Input": "linked_doctype_field",
            "BOM Variable": "bom_variable",
            "BOM Attribute": "linked_doctype_field",
            "Rule Engine Result": "rule_engine_lookup",
            "Computed": "computed",
            "Context Inject": None,  # skip — handled separately
            "Constant": "constant",
        }

        fb_source_type = source_type_map.get(ab.source_type)
        if fb_source_type is None:
            continue

        # Build FB source_config
        al_config = _safe_json(ab.source_config)
        fb_config = _map_source_config(ab.source_type, al_config)

        # Check duplicate
        existing = frappe.db.exists(
            "Formula Variable Binding",
            {"variable_name": ab.variable_name, "source_type": fb_source_type},
        )
        if existing:
            continue

        try:
            fb = frappe.new_doc("Formula Variable Binding")
            fb.variable_name = ab.variable_name
            fb.variable_label = ab.variable_label or ab.variable_name
            fb.source_type = fb_source_type
            fb.resolve_priority = ab.resolve_priority or 50
            fb.source_config = json.dumps(fb_config, ensure_ascii=False)
            fb.data_type = _map_data_type(ab.data_type)
            fb.is_active = 1
            fb.is_global = 1
            fb.insert(ignore_permissions=True)
            count += 1
        except Exception as e:
            print(f"  FAILED: {ab.variable_name} — {e}")

    return count


def _map_source_config(al_source_type, al_config):
    """Map AL source_config → FB source_config format."""
    if al_source_type == "Quotation Input":
        fieldname = al_config.get("fieldname", "")
        return {
            "link_field": fieldname,
            "target_field": fieldname,
        }
    elif al_source_type == "BOM Variable":
        return {
            "var_code": al_config.get("var_code", ""),
            "default": al_config.get("default"),
        }
    elif al_source_type == "BOM Attribute":
        return {
            "link_field": al_config.get("attribute", ""),
            "target_field": al_config.get("attribute", ""),
        }
    elif al_source_type == "Rule Engine Result":
        return {
            "rule_code": al_config.get("rule_code", ""),
            "arg_mapping": al_config.get("args", {}),
        }
    elif al_source_type == "Computed":
        return {
            "formula": al_config.get("formula", ""),
            "dependencies": al_config.get("dependencies", []),
        }
    elif al_source_type == "Constant":
        return {"value": al_config.get("value", "")}
    return al_config


def _map_data_type(al_data_type):
    """Map AL data_type → FB data_type."""
    type_map = {
        "Float": "Float",
        "String": "Data",
        "Integer": "Int",
        "Boolean": "Check",
    }
    return type_map.get(al_data_type, "Data")


def _migrate_constant_rules():
    """Tạo Formula Global Variable từ AL Calculation Rule CONSTANT."""
    rules = frappe.get_all(
        "AL Calculation Rule",
        filters={"rule_type": "CONSTANT", "is_active": 1},
        fields=["rule_code", "rule_name", "constant_value"],
    )
    count = 0

    for r in rules:
        existing = frappe.db.exists(
            "Formula Global Variable", {"var_name": r.rule_code}
        )
        if existing:
            continue

        try:
            gv = frappe.new_doc("Formula Global Variable")
            gv.var_name = r.rule_code
            gv.label = r.rule_name or r.rule_code
            gv.var_type = "Float"
            gv.value_source = "CONSTANT"
            gv.constant_value = r.constant_value
            gv.is_active = 1
            gv.insert(ignore_permissions=True)
            count += 1
        except Exception as e:
            print(f"  FAILED: {r.rule_code} — {e}")

    return count


def _safe_json(val):
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
