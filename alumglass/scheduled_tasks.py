"""
AlumGlass Scheduled Tasks — Daily & Weekly jobs
"""
import frappe


def update_sales_kpi():
    """Daily 1:00 AM — Cập nhật KPI tất cả Sales users."""
    from alumglass.modules.analytics.kpi_calculator import update_all_kpi
    update_all_kpi("MONTHLY")
    frappe.db.commit()


def check_price_change_alerts():
    """Daily 9:00 AM — So sánh Item Price vs ConfigSnapshot."""
    alerts = frappe.get_all(
        "AL Alert Config",
        filters={"is_active": 1, "alert_type": "PRICE_CHANGE"},
        fields=["*"],
    )
    if not alerts:
        return

    from alumglass.modules.notification.notification_engine import NotificationEngine
    for alert in alerts:
        # Check all active BOMs
        boms = frappe.get_all("AL BOM", filters={"is_active": 1}, fields=["name", "profile_set"])
        for bom in boms:
            bom_doc = frappe.get_doc("AL BOM", bom.name)
            NotificationEngine._check_price_change(alert, bom_doc)
    frappe.db.commit()


def check_low_stock_alerts():
    """Daily 8:00 AM — Kiểm tra tồn kho nhôm/kính."""
    alerts = frappe.get_all(
        "AL Alert Config",
        filters={"is_active": 1, "alert_type": "LOW_STOCK"},
        fields=["*"],
    )
    if not alerts:
        return

    from alumglass.modules.notification.notification_engine import NotificationEngine
    for alert in alerts:
        NotificationEngine._check_low_stock(alert)
    frappe.db.commit()


def generate_daily_digest():
    """Daily 7:00 PM — Gom CAUTION variance → email digest."""
    from frappe.utils import today
    caution_records = frappe.get_all(
        "AL Cost Variance",
        filters={
            "variance_status": "CAUTION",
            "creation": [">", today()],
        },
        fields=["name", "item_code", "variance_pct", "impact_on_margin"],
    )
    if not caution_records:
        return

    # Send digest email to Admin
    admin_users = frappe.get_all(
        "Has Role",
        filters={"role": "AluGlass Admin", "parenttype": "User"},
        fields=["parent"],
    )
    recipients = [u.parent for u in admin_users]

    if recipients:
        lines = []
        for r in caution_records:
            lines.append(
                f"<li>{r.item_code}: variance {r.variance_pct:.1f}%, "
                f"impact {r.impact_on_margin:,.0f}đ</li>"
            )
        frappe.sendmail(
            recipients=recipients,
            subject=f"AluGlass Daily Digest — Cost Variance ({today()})",
            message=f"""
            <h3>Cost Variance CAUTION — {today()}</h3>
            <ul>{''.join(lines)}</ul>
            <p>Vui lòng review trong AL Cost Variance.</p>
            """,
        )


def deprecate_old_bom_versions():
    """Weekly Monday — Đánh dấu BOM Version > 365 ngày."""
    from frappe.utils import add_days, today
    cutoff = add_days(today(), -365)
    old_versions = frappe.get_all(
        "AL BOM Version",
        filters={
            "status": "Published",
            "published_on": ["<", cutoff],
        },
        fields=["name"],
    )
    for v in old_versions:
        frappe.db.set_value("AL BOM Version", v.name, "status", "Deprecated")
    frappe.db.commit()
