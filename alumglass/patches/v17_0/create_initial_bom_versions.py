"""Migration v16 → v17: Tạo AL BOM Version v1 cho tất cả BOM hiện có"""
import frappe


def execute():
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    mgr = BOMVersionManager()
    count = 0
    for bom in frappe.get_all("AL BOM", fields=["name"]):
        bom_doc = frappe.get_doc("AL BOM", bom.name)
        try:
            ver = mgr.publish(bom_doc, change_summary="Initial version — migrated from v16")
            ver.db_set("status", "Published")
            ver.db_set("published_on", frappe.utils.now())
            bom_doc.db_set("current_version", ver.name)
            bom_doc.db_set("total_versions", 1)
            count += 1
            print(f"  BOM {bom.name}: created version {ver.name}")
        except Exception as e:
            print(f"  BOM {bom.name}: FAILED — {e}")
    frappe.db.commit()
    print(f"\nMigration v16→v17: Created {count} initial BOM Versions")
