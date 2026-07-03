"""
Migration v17.0 — Add v17 custom fields to ERPNext core doctypes
Adds: al_bom_version, al_discount_rule, al_discount_pct, al_commercial_price,
al_accessory_overrides, al_cost_variance_ref, al_approval_status, al_approved_by,
al_approval_note to Quotation Item, Sales Order Item, Sales Invoice Item.
"""
import frappe
import json
import os


def execute():
    """Add v17 custom fields to ERPNext core doctypes."""
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Custom fields for each doctype
    field_sets = {
        "Quotation Item": "quotation_item_v17.json",
        "Sales Order Item": "sales_order_item_v17.json",
        "Sales Invoice Item": "sales_invoice_item_v17.json",
    }

    for dt, filename in field_sets.items():
        filepath = os.path.join(app_dir, "custom_fields", filename)
        if not os.path.exists(filepath):
            print(f"[v17.0] Custom field file not found: {filepath}")
            continue

        with open(filepath, "r") as f:
            fields = json.load(f)

        for field_def in fields:
            fieldname = field_def.get("fieldname")
            if not fieldname:
                continue

            # Check if field already exists
            exists = frappe.db.exists(
                "Custom Field",
                {"dt": dt, "fieldname": fieldname},
            )
            if exists:
                print(f"[v17.0] Custom field {dt}.{fieldname} already exists, skipping.")
                continue

            try:
                cf = frappe.get_doc({
                    "doctype": "Custom Field",
                    **field_def,
                })
                cf.insert(ignore_permissions=True)
                print(f"[v17.0] Created custom field: {dt}.{fieldname}")
            except Exception as e:
                print(f"[v17.0] Error creating {dt}.{fieldname}: {e}")

        frappe.db.commit()

    print("[v17.0] v17 custom fields migration complete.")
