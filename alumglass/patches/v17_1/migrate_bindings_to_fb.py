"""
P0 Migration: Migrate AL Variable Binding -> Formula Variable Binding
+ Create Formula Global Variable from AL Calculation Rule CONSTANT
Idempotent - safe to run multiple times.
Handles v17 P0: AL Variable Binding replaced by Formula Variable Binding.
"""
import frappe
import json


def execute():
    """Run P0 migration. Safe to re-run."""
    count_bindings = _migrate_bindings()
    count_globals = _migrate_constant_rules()
    frappe.db.commit()
    print(f"\nP0 Migration: {count_bindings} bindings, {count_globals} global vars")


def _migrate_bindings():
    """Create Formula Variable Binding records from legacy AL Variable Binding.
    If AL Variable Binding table doesn't exist (v17 P0), skip gracefully.
    """
    # Check if legacy table exists
    if not frappe.db.exists("DocType", "AL Variable Binding"):
        print("  AL Variable Binding DocType not found (already migrated to FB). Skipping.")
        return 0

    try:
        al_bindings = frappe.get_all(
            "AL Variable Binding",
            filters={"is_active": 1},
            fields=["*"],
        )
    except Exception as e:
        print(f"  Could not read AL Variable Binding: {e}. Skipping.")
        return 0

    count = 0
    source_type_map = {
        "Quotation Input": "linked_doctype_field",
        "BOM Variable": "bom_variable",
        "BOM Attribute": "linked_doctype_field",
        "Rule Engine Result": "rule_engine_lookup",
        "Computed": "computed",
        "Context Inject": None,
        "Constant": "constant",
    }

    for ab in al_bindings:
        fb_source_type = source_type_map.get(ab.source_type)
        if fb_source_type is None:
            continue

        al_config = _safe_json(ab.source_config)
        fb_config = _map_source_config(ab.source_type, al_config)

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
            print(f"  FAILED: {ab.variable_name} - {e}")

    return count


def _migrate_constant_rules():
    """Create Formula Global Variable from AL Calculation Rule CONSTANT."""
    if not frappe.db.exists("DocType", "AL Calculation Rule"):
        print("  AL Calculation Rule DocType not found. Skipping.")
        return 0

    try:
        rules = frappe.get_all(
            "AL Calculation Rule",
            filters={"rule_type": "CONSTANT", "is_active": 1},
            fields=["rule_code", "rule_name", "constant_value"],
        )
    except Exception:
        # Table might not have 'rule_type' field yet, or CONSTANT type removed
        print("  Could not read CONSTANT rules (may already be migrated). Skipping.")
        return 0

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
            print(f"  FAILED: {r.rule_code} - {e}")

    return count


def _map_source_config(al_source_type, al_config):
    if al_source_type == "Quotation Input":
        fieldname = al_config.get("fieldname", "")
        return {"link_field": fieldname, "target_field": fieldname}
    elif al_source_type == "BOM Variable":
        return {"var_code": al_config.get("var_code", ""), "default": al_config.get("default")}
    elif al_source_type == "BOM Attribute":
        return {"link_field": al_config.get("attribute", ""), "target_field": al_config.get("attribute", "")}
    elif al_source_type == "Rule Engine Result":
        return {"rule_code": al_config.get("rule_code", ""), "arg_mapping": al_config.get("args", {})}
    elif al_source_type == "Computed":
        return {"formula": al_config.get("formula", ""), "dependencies": al_config.get("dependencies", [])}
    elif al_source_type == "Constant":
        return {"value": al_config.get("value", "")}
    return al_config


def _map_data_type(al_data_type):
    type_map = {"Float": "Float", "String": "Data", "Integer": "Int", "Boolean": "Check"}
    return type_map.get(al_data_type, "Data")


def _safe_json(val):
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
