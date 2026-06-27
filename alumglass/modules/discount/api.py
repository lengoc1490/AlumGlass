"""
API endpoints for AL Discount Rule module
"""
import frappe
from frappe import _


@frappe.whitelist()
def get_applicable_discounts(quotation_item_name):
    """Lấy danh sách discount rules applicable cho 1 Quotation Item."""
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    quotation = frappe.get_doc("Quotation", qi.parent)
    customer = quotation.party_name

    if not customer:
        return []

    customer_group = frappe.db.get_value("Customer", customer, "customer_group")
    qty = qi.qty or 1
    amount = qi.al_gia_ban or 0

    rules = frappe.get_all(
        "AL Discount Rule",
        filters={"is_active": 1},
        fields=["*"],
        order_by="priority asc",
    )

    applicable = []
    from alumglass.modules.discount.discount_stack import DiscountStack

    for r in rules:
        if DiscountStack._rule_matches(r, customer, customer_group, {"name": qi.al_bom}, qty, amount):
            applicable.append({
                "name": r["name"],
                "rule_name": r["rule_name"],
                "rule_type": r["rule_type"],
                "discount_pct": r["discount_pct"],
                "stackable": r["stackable"],
                "priority": r["priority"],
            })

    return applicable


@frappe.whitelist()
def apply_manual_discount(quotation_item_name, discount_pct, reason=""):
    """Sales nhập discount MANUAL."""
    qi = frappe.get_doc("Quotation Item", quotation_item_name)

    # Kiểm tra max discount
    max_disc = frappe.db.get_single_value("AL Alert Config", "max_total_discount_pct") or 15
    if float(discount_pct) > float(max_disc):
        frappe.throw(_("Chiết khấu tối đa cho phép là {0}%").format(max_disc))

    gia_ban = qi.al_gia_ban or 0
    gia_thuong_mai = gia_ban * (1 - float(discount_pct) / 100)

    qi.db_set("al_discount_pct", float(discount_pct))
    qi.db_set("al_gia_thuong_mai", gia_thuong_mai)
    qi.db_set("al_discount_rule", "MANUAL")

    # Check approval threshold
    approval_threshold = frappe.db.get_single_value("AL Alert Config", "approval_threshold_pct") or 8
    if float(discount_pct) > float(approval_threshold):
        qi.db_set("al_approval_status", "PENDING")
        return {"status": "PENDING_APPROVAL", "discount_pct": discount_pct, "gia_thuong_mai": gia_thuong_mai}

    return {"status": "APPLIED", "discount_pct": discount_pct, "gia_thuong_mai": gia_thuong_mai}
