"""
AlumGlass Scheduled Tasks — Daily, Weekly & Hourly jobs
All tasks have try/except + frappe.log_error + retry mechanism (max 3 retries).
"""
import frappe
from frappe.utils import today, add_days, now
import time


MAX_RETRIES = 3
RETRY_DELAY_SEC = 60  # 1 minute between retries


def _run_with_retry(task_name, fn, *args, **kwargs):
    """Execute a task with retry logic.

    Args:
        task_name: Name of the task for logging
        fn: Callable to execute
        *args, **kwargs: Arguments passed to fn

    Returns:
        True if successful, False if all retries failed
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            fn(*args, **kwargs)
            return True
        except Exception as e:
            last_error = e
            frappe.log_error(
                title=f"Scheduled Task Failed: {task_name} (Attempt {attempt}/{MAX_RETRIES})",
                message=f"{e}",
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)

    frappe.log_error(
        title=f"Scheduled Task FAILED after {MAX_RETRIES} retries: {task_name}",
        message=str(last_error),
    )
    return False


# ============================================================
# HOURLY TASKS
# ============================================================

def process_notification_queue():
    """Hourly: Process queued notifications (rate-limited: 5/min)."""
    _run_with_retry("process_notification_queue", _do_process_notification_queue)


def _do_process_notification_queue():
    from alumglass.modules.notification.notification_engine import NotificationEngine
    engine = NotificationEngine()
    engine.process_queue()


# ============================================================
# DAILY TASKS
# ============================================================

def update_sales_kpi():
    """Daily ~1:00 AM — Update KPI for all Sales users."""
    _run_with_retry("update_sales_kpi", _do_update_sales_kpi)


def _do_update_sales_kpi():
    from alumglass.modules.analytics.kpi_calculator import KPICalculator
    calc = KPICalculator()
    calc.update_all_kpi("MONTHLY")
    calc.update_all_kpi("QUARTERLY")
    frappe.db.commit()


def check_price_change_alerts():
    """Daily ~9:00 AM — Compare Item Price vs ConfigSnapshot."""
    _run_with_retry("check_price_change_alerts", _do_check_price_change_alerts)


def _do_check_price_change_alerts():
    alerts = frappe.get_all(
        "AL Alert Config",
        filters={"is_active": 1, "alert_type": "PRICE_CHANGE"},
        fields=["*"],
    )
    if not alerts:
        return

    from alumglass.modules.notification.notification_engine import NotificationEngine
    engine = NotificationEngine()
    for alert in alerts:
        engine.check_price_change(alert)


def check_low_stock_alerts():
    """Daily ~8:00 AM — Check aluminum/glass stock levels."""
    _run_with_retry("check_low_stock_alerts", _do_check_low_stock_alerts)


def _do_check_low_stock_alerts():
    alerts = frappe.get_all(
        "AL Alert Config",
        filters={"is_active": 1, "alert_type": "LOW_STOCK"},
        fields=["*"],
    )
    if not alerts:
        return

    from alumglass.modules.notification.notification_engine import NotificationEngine
    engine = NotificationEngine()
    for alert in alerts:
        engine.check_low_stock(alert)


def generate_daily_digest():
    """Daily ~7:00 PM — Gather CAUTION/ALERT variance → email digest."""
    _run_with_retry("generate_daily_digest", _do_generate_daily_digest)


def _do_generate_daily_digest():
    variance_records = frappe.get_all(
        "AL Cost Variance",
        filters={
            "variance_status": ("in", ["CAUTION", "ALERT"]),
            "creation": [">", today()],
        },
        fields=["name", "item_code", "variance_pct", "variance_status", "impact_on_margin"],
    )
    if not variance_records:
        return

    # Get admin recipients
    admin_users = frappe.get_all(
        "Has Role",
        filters={"role": ("in", ["alumglass Admin"]), "parenttype": "User"},
        fields=["parent"],
    )
    recipients = [u.parent for u in admin_users if u.parent]

    if not recipients:
        return

    lines = []
    for r in variance_records:
        status_badge = "🔴 ALERT" if r.variance_status == "ALERT" else "🟡 CAUTION"
        lines.append(
            f"<li>{status_badge} — {r.item_code}: "
            f"variance {r.variance_pct:.1f}%, "
            f"impact {r.impact_on_margin:,.0f}</li>"
        )

    try:
        frappe.sendmail(
            recipients=recipients,
            subject=f"AlumGlass Daily Cost Variance Digest — {today()}",
            message=f"""
            <h3>Cost Variance Digest — {today()}</h3>
            <p>The following variances require review:</p>
            <ul>{''.join(lines)}</ul>
            <p>Please review in <b>AL Cost Variance</b>.</p>
            <hr>
            <small>AlumGlass ERP v17 — Automated Digest</small>
            """,
        )
    except Exception as e:
        frappe.log_error(
            title="Daily digest email failed",
            message=str(e),
        )


# ============================================================
# WEEKLY TASKS
# ============================================================

def deprecate_old_bom_versions():
    """Weekly Monday — Mark BOM Versions older than 365 days as Deprecated."""
    _run_with_retry("deprecate_old_bom_versions", _do_deprecate_old_bom_versions)


def _do_deprecate_old_bom_versions():
    cutoff = add_days(today(), -365)
    old_versions = frappe.get_all(
        "AL BOM Version",
        filters={
            "status": "Published",
            "published_on": ["<", cutoff],
        },
        fields=["name", "bom"],
    )

    for v in old_versions:
        # Do not deprecate if it's the only Published version for this BOM
        published_count = frappe.db.count(
            "AL BOM Version",
            {"bom": v.bom, "status": "Published"},
        )
        if published_count <= 1:
            continue  # Keep at least one published version
        frappe.db.set_value("AL BOM Version", v.name, "status", "Deprecated")

    frappe.db.commit()
