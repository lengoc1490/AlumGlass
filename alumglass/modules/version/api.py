"""
API endpoints for BOM Version Control
"""
import frappe
from frappe import _


@frappe.whitelist()
def get_bom_version_info(bom_name):
    """Lấy thông tin version hiện tại + lịch sử."""
    current_ver = frappe.db.get_value("AL BOM", bom_name, "current_version")
    versions = frappe.get_all(
        "AL BOM Version",
        filters={"bom": bom_name},
        fields=["name", "version_number", "status", "published_on", "change_summary", "snapshot_hash"],
        order_by="version_number desc",
        limit_page_length=20,
    )

    current_info = None
    if current_ver:
        ver = frappe.get_doc("AL BOM Version", current_ver)
        current_info = {
            "name": ver.name,
            "version_number": ver.version_number,
            "status": ver.status,
            "published_on": str(ver.published_on) if ver.published_on else None,
            "change_summary": ver.change_summary,
            "snapshot_hash": ver.snapshot_hash,
        }

    return {
        "current_version": current_info,
        "version_history": versions,
        "total_versions": len(versions),
    }


@frappe.whitelist()
def compare_versions(version_a, version_b):
    """So sánh 2 BOM versions → DiffResult."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    mgr = BOMVersionManager()
    return mgr.compare_versions(version_a, version_b)


@frappe.whitelist()
def rollback_version(bom_name, target_version_name):
    """Rollback BOM về version cũ."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    # Permission check
    if not frappe.has_permission("AL BOM", "write", bom_name):
        frappe.throw(_("Bạn không có quyền rollback BOM này."))

    mgr = BOMVersionManager()
    ver = mgr.rollback(target_version_name, frappe.session.user)
    return {
        "new_version": ver.name,
        "new_version_number": ver.version_number,
        "rollback_of": target_version_name,
    }


@frappe.whitelist()
def publish_version(bom_name, change_summary=""):
    """Publish BOM version mới."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    bom_doc = frappe.get_doc("AL BOM", bom_name)

    if not frappe.has_permission("AL BOM", "write", bom_name):
        frappe.throw(_("Bạn không có quyền publish BOM này."))

    # Kiểm tra xem Kỹ Thuật có quyền tự publish không
    if bom_doc.requires_approval_for_new_version:
        if "AluGlass Admin" not in frappe.get_roles():
            frappe.throw(_("BOM này yêu cầu Admin duyệt trước khi publish."))

    mgr = BOMVersionManager()
    ver = mgr.publish(bom_doc, change_summary)
    return {
        "version_name": ver.name,
        "version_number": ver.version_number,
        "status": ver.status,
    }
