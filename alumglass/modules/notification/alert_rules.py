"""
Alert Rules — Separate alert check functions for scheduled jobs
"""
import frappe


def check_price_change_alerts_job():
    """Daily 9:00 AM job: So sánh Item Price vs ConfigSnapshot."""
    alerts = frappe.get_all(
        "AL Alert Config",
        filters={"is_active": 1, "alert_type": "PRICE_CHANGE"},
        fields=["*"],
    )
    if not alerts:
        return

    from alumglass.modules.notification.notification_engine import NotificationEngine
    boms = frappe.get_all("AL BOM", filters={"is_active": 1}, fields=["name", "profile_set"])
    for bom in boms:
        bom_doc = frappe.get_doc("AL BOM", bom.name)
        for alert in alerts:
            try:
                NotificationEngine._check_price_change(alert, bom_doc)
            except Exception as e:
                frappe.log_error(f"Price change alert failed for {bom.name}: {e}")


def check_low_stock_alerts_job():
    """Daily 8:00 AM job: Kiểm tra tồn kho."""
    alerts = frappe.get_all(
        "AL Alert Config",
        filters={"is_active": 1, "alert_type": "LOW_STOCK"},
        fields=["*"],
    )
    if not alerts:
        return

    from alumglass.modules.notification.notification_engine import NotificationEngine
    for alert in alerts:
        try:
            NotificationEngine._check_low_stock(alert)
        except Exception as e:
            frappe.log_error(f"Low stock alert failed: {e}")


def generate_daily_digest_job():
    """Daily 7:00 PM job: Gom CAUTION variance → email digest."""
    from frappe.utils import today
    records = frappe.get_all(
        "AL Cost Variance",
        filters={
            "variance_status": "CAUTION",
            "creation": [">", today()],
        },
        fields=["name", "item_code", "variance_pct", "impact_on_margin"],
    )
    if not records:
        return

    admin_users = frappe.get_all(
        "Has Role",
        filters={"role": "AluGlass Admin", "parenttype": "User"},
        fields=["parent"],
    )
    recipients = [u.parent for u in admin_users]
    if not recipients:
        return

    lines = "".join(
        f"<li>{r.item_code}: {r.variance_pct:.1f}%, impact {r.impact_on_margin:,.0f}đ</li>"
        for r in records
    )
    frappe.sendmail(
        recipients=recipients,
        subject=f"AluGlass Daily Digest — Cost Variance ({today()})",
        message=f"<h3>Cost Variance CAUTION</h3><ul>{lines}</ul>",
    )


def deprecate_old_bom_versions_job():
    """Weekly Monday job: Đánh dấu BOM Version > 365 ngày."""
    from frappe.utils import add_days, today
    cutoff = add_days(today(), -365)
    old_versions = frappe.get_all(
        "AL BOM Version",
        filters={"status": "Published", "published_on": ["<", cutoff]},
        fields=["name"],
    )
    for v in old_versions:
        try:
            frappe.db.set_value("AL BOM Version", v.name, "status", "Deprecated")
        except Exception as e:
            frappe.log_error(f"Deprecate version {v.name} failed: {e}")
