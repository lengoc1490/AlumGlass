"""
Migration v17.1 — Create version v1 for all existing BOMs that don't have one.
Takes snapshot of current BOM configuration and creates AL BOM Version (Published).
"""
import frappe
import json
import hashlib
from frappe.utils import now


def execute():
    """Create initial BOM Version v1 for all existing BOM records."""
    boms = frappe.get_all(
        "AL BOM",
        filters={"current_version": ("is", "not set")},
        or_filters={"current_version": ""},
        fields=["name", "bom_code"],
    )

    created_count = 0
    for bom in boms:
        try:
            ver = _create_initial_version(bom.name)
            if ver:
                created_count += 1
                print(f"[v17.1] Created initial version v1 for BOM '{bom.bom_code}'")
        except Exception as e:
            print(f"[v17.1] Error creating initial version for BOM '{bom.bom_code}': {e}")

    # Also handle BOMs where current_version is NULL
    null_version_boms = frappe.db.sql(
        """
        SELECT name, bom_code FROM `tabAL BOM`
        WHERE current_version IS NULL OR current_version = ''
        """,
        as_dict=True,
    )
    for bom in null_version_boms:
        try:
            exists = frappe.db.exists(
                "AL BOM Version", {"bom": bom.name, "status": "Published"}
            )
            if not exists:
                ver = _create_initial_version(bom.name)
                if ver:
                    created_count += 1
        except Exception as e:
            print(f"[v17.1] Error: {e}")

    frappe.db.commit()
    print(f"[v17.1] Migration complete. Created {created_count} initial BOM Versions.")


def _create_initial_version(bom_name):
    """Create version v1 snapshot for a BOM."""
    bom = frappe.get_doc("AL BOM", bom_name)

    # Get snapshots of linked documents
    ps_snap = frappe.get_doc("AL Profile Set", bom.profile_set).as_dict()
    vs_snap = frappe.get_doc("AL Variable Set", bom.variable_set).as_dict()
    ct_snap = frappe.get_doc(
        "AL Cost Template", bom.default_cost_template
    ).as_dict()

    acc_snap = {}
    if bom.accessory_set:
        acc_snap = frappe.get_doc(
            "AL Accessory Set", bom.accessory_set
        ).as_dict()

    # Compute SHA-256 hash
    payload_str = json.dumps({
        "profile_set": ps_snap,
        "variable_set": vs_snap,
        "accessory_set": acc_snap,
        "cost_template": ct_snap,
    }, sort_keys=True, default=str, ensure_ascii=False)
    snap_hash = hashlib.sha256(payload_str.encode()).hexdigest()

    # Create version
    ver = frappe.get_doc({
        "doctype": "AL BOM Version",
        "bom": bom.name,
        "version_number": 1,
        "status": "Published",
        "published_on": now(),
        "published_by": "Administrator",
        "profile_set_snapshot": json.dumps(ps_snap, default=str, ensure_ascii=False),
        "variable_set_snapshot": json.dumps(vs_snap, default=str, ensure_ascii=False),
        "accessory_set_snapshot": json.dumps(acc_snap, default=str, ensure_ascii=False),
        "cost_template_snapshot": json.dumps(ct_snap, default=str, ensure_ascii=False),
        "snapshot_hash": snap_hash,
        "change_summary": "Initial version created by migration v17.1",
    })
    ver.insert(ignore_permissions=True)

    # Update BOM
    frappe.db.set_value("AL BOM", bom.name, "current_version", ver.name)
    frappe.db.set_value("AL BOM", bom.name, "total_versions", 1)
    frappe.db.set_value("AL BOM", bom.name, "last_published_on", now())

    return ver
