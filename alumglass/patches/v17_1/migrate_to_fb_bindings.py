"""
Migration v17.1 — Migrate AL Variable Binding → Formula Variable Binding
Creates Formula Variable Binding records from existing AL Variable Binding data.
Registers 2 custom handlers: bom_variable, rule_engine_lookup.

P0: AL Variable Binding DocType is deprecated. All bindings are migrated to
Formula Variable Binding with DAG topology support (12 source types available).
"""
import frappe
import json


def execute():
    """Migrate AL Variable Binding to Formula Variable Binding."""
    # Step 1: Check if AL Variable Binding has existing records
    al_bindings = frappe.get_all(
        "AL Variable Binding",
        filters={"is_active": 1},
        fields=["*"],
    )

    if not al_bindings:
        print("[v17.1] No AL Variable Binding records to migrate.")
        return

    # Step 2: Map AL source_type → FB source_type or custom handler
    SOURCE_TYPE_MAP = {
        "Quotation Input": "linked_doctype_field",
        "BOM Variable": "bom_variable",
        "BOM Attribute": "linked_doctype_field",
        "Rule Engine Result": "rule_engine_lookup",
        "Computed": "computed",
        "Context Inject": None,  # Handled separately by VariableResolver
    }

    migrated_count = 0
    for al_b in al_bindings:
        fb_source_type = SOURCE_TYPE_MAP.get(al_b.source_type)

        if fb_source_type is None:
            # Context Inject is handled separately — skip
            continue

        # Check if already migrated
        exists = frappe.db.exists(
            "Formula Variable Binding",
            {"variable_name": al_b.variable_name},
        )
        if exists:
            print(f"[v17.1] Binding '{al_b.variable_name}' already exists in FB, skipping.")
            continue

        # Build source_config for FB
        source_config = _build_source_config(al_b)

        try:
            fb_binding = frappe.get_doc({
                "doctype": "Formula Variable Binding",
                "variable_name": al_b.variable_name,
                "variable_label": al_b.variable_label,
                "source_type": fb_source_type,
                "source_config": json.dumps(source_config, ensure_ascii=False),
                "data_type": _map_data_type(al_b.data_type),
                "resolve_priority": al_b.resolve_priority or 100,
                "is_active": al_b.is_active,
            })
            fb_binding.insert(ignore_permissions=True)
            migrated_count += 1
            print(f"[v17.1] Migrated: {al_b.variable_name} → {fb_source_type}")
        except Exception as e:
            print(f"[v17.1] Error migrating {al_b.variable_name}: {e}")

    frappe.db.commit()

    # Step 3: Register custom handlers
    try:
        from alumglass.fb_handlers import register_handlers
        register_handlers()
        print("[v17.1] Custom FB handlers registered: bom_variable, rule_engine_lookup")
    except Exception as e:
        print(f"[v17.1] Warning: Could not register custom handlers: {e}")

    print(f"[v17.1] Migration complete. Migrated {migrated_count} bindings.")


def _build_source_config(al_binding):
    """Build FB-compatible source_config from AL Variable Binding."""
    source_type = al_binding.source_type
    config = _safe_json(al_binding.source_config)

    if source_type == "Quotation Input":
        return {
            "doctype": "Quotation Item",
            "fieldname": config.get("fieldname", ""),
        }
    elif source_type == "BOM Variable":
        return {
            "var_code": config.get("var_code", ""),
            "default": config.get("default"),
        }
    elif source_type == "BOM Attribute":
        return {
            "doctype": "AL BOM",
            "fieldname": config.get("attribute", ""),
        }
    elif source_type == "Rule Engine Result":
        return {
            "rule_code": config.get("rule_code", ""),
            "rule_type": "LOOKUP",
            "args": config.get("args", {}),
        }
    elif source_type == "Computed":
        return {
            "formula": config.get("formula", ""),
        }
    return config or {}


def _map_data_type(al_data_type):
    """Map AL data types to FB data types."""
    mapping = {
        "Float": "Float",
        "String": "Data",
        "Integer": "Int",
        "Boolean": "Check",
    }
    return mapping.get(al_data_type, "Float")


def _safe_json(val):
    """Safely parse JSON."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
