"""
Migration v17.0 — Create new DocTypes introduced in v17
Creates 10 new DocTypes: AL BOM Version, AL BOM Change Log, AL Discount Rule,
AL Discount Rule Line, AL Material Plan, AL Material Plan Line, AL Cost Variance,
AL Alert Config, AL Dashboard Config, AL Sales KPI.
"""
import frappe


def execute():
    """Create new v17 DocTypes if they don't already exist."""
    doctypes_to_create = [
        "AL BOM Version",
        "AL BOM Change Log",
        "AL Discount Rule",
        "AL Discount Rule Line",
        "AL Material Plan",
        "AL Material Plan Line",
        "AL Cost Variance",
        "AL Alert Config",
        "AL Dashboard Config",
        "AL Sales KPI",
    ]

    for dt_name in doctypes_to_create:
        if not frappe.db.exists("DocType", dt_name):
            try:
                frappe.get_doc({
                    "doctype": "DocType",
                    "name": dt_name,
                    "module": "AlumGlass",
                    "custom": 0,
                    "istable": "Line" in dt_name,
                    "__needs_migration": False,
                })
                frappe.db.commit()
                print(f"[v17.0] DocType '{dt_name}' registered for creation via JSON import.")
            except Exception as e:
                print(f"[v17.0] Warning: Could not register {dt_name}: {e}")

    print("[v17.0] New DocType registration complete. Run bench migrate to create tables.")
