"""
Approval Engine — Quy trình duyệt discount + BOM version
"""
import frappe
from frappe import _


def check_pending_approvals(doc, method):
    """Hook before_submit Quotation: chặn nếu có dòng chờ duyệt."""
    pending = [
        i for i in doc.items
        if i.get("al_approval_status") == "PENDING"
    ]
    if pending:
        frappe.throw(_(
            "Có {0} dòng chờ duyệt discount. "
            "Vui lòng chờ Admin duyệt trước khi Submit."
        ).format(len(pending)))


@frappe.whitelist()
def approve_discount(quotation_item_name, approved_by=None, note=""):
    """Admin duyệt discount cho 1 dòng Quotation Item."""
    if not approved_by:
        approved_by = frappe.session.user

    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    if qi.al_approval_status != "PENDING":
        frappe.throw(_("Dòng này không ở trạng thái chờ duyệt."))

    qi.db_set("al_approval_status", "APPROVED")
    qi.db_set("al_approved_by", approved_by)
    qi.db_set("al_approval_note", note)

    # Gửi notification cho Sales
    quotation_owner = frappe.db.get_value("Quotation", qi.parent, "owner")
    if quotation_owner:
        frappe.publish_realtime(
            "aluglass_approval",
            {
                "message": f"Discount cho {qi.item_name} đã được duyệt",
                "status": "APPROVED",
                "quotation": qi.parent,
            },
            user=quotation_owner,
        )

    return {"status": "APPROVED"}


@frappe.whitelist()
def reject_discount(quotation_item_name, approved_by=None, note=""):
    """Admin từ chối discount."""
    if not approved_by:
        approved_by = frappe.session.user

    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    if qi.al_approval_status != "PENDING":
        frappe.throw(_("Dòng này không ở trạng thái chờ duyệt."))

    qi.db_set("al_approval_status", "REJECTED")
    qi.db_set("al_approved_by", approved_by)
    qi.db_set("al_approval_note", note or "Từ chối bởi Admin")

    # Reset discount
    qi.db_set("al_discount_pct", 0)
    qi.db_set("al_gia_thuong_mai", qi.al_gia_ban)
    qi.db_set("al_discount_rule", None)

    # Notify Sales
    quotation_owner = frappe.db.get_value("Quotation", qi.parent, "owner")
    if quotation_owner:
        frappe.publish_realtime(
            "aluglass_approval",
            {
                "message": f"Discount cho {qi.item_name} bị từ chối: {note}",
                "status": "REJECTED",
                "quotation": qi.parent,
            },
            user=quotation_owner,
        )

    return {"status": "REJECTED"}


@frappe.whitelist()
def get_pending_approvals(user=None):
    """Lấy danh sách Quotation Item đang chờ duyệt."""
    if not user:
        user = frappe.session.user

    # Lấy tất cả QT Items PENDING (trừ của chính user để tránh self-approve)
    items = frappe.get_all(
        "Quotation Item",
        filters={"al_approval_status": "PENDING"},
        fields=[
            "name", "parent", "item_name", "al_bom",
            "al_discount_pct", "al_gia_ban", "al_gia_thuong_mai",
            "al_discount_rule", "creation",
        ],
        order_by="creation asc",
    )

    # Lọc bỏ các QT của chính user (không được tự duyệt)
    result = []
    for item in items:
        qt_owner = frappe.db.get_value("Quotation", item.parent, "owner")
        if qt_owner != user:
            item["quotation_owner"] = qt_owner
            result.append(item)

    return result
