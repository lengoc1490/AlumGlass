"""
API endpoints for Cost Variance Analysis
"""
import frappe
from frappe import _


@frappe.whitelist()
def get_cost_variances(filters=None):
    """Lấy danh sách Cost Variance records."""
    import json
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}
    return frappe.get_all(
        "AL Cost Variance",
        filters=filters,
        fields=["*"],
        order_by="creation desc",
        limit_page_length=100,
    )


@frappe.whitelist()
def review_variance(variance_name, note=""):
    """Đánh dấu Cost Variance đã review."""
    variance = frappe.get_doc("AL Cost Variance", variance_name)
    variance.reviewed_by = frappe.session.user
    variance.review_note = note
    variance.save(ignore_permissions=True)
    return {"status": "reviewed"}


@frappe.whitelist()
def get_variance_summary(date_from=None, date_to=None):
    """Tổng hợp variance theo kỳ."""
    from frappe.utils import today, get_first_day, get_last_day

    if not date_from:
        date_from = get_first_day(today())
    if not date_to:
        date_to = get_last_day(today())

    records = frappe.get_all(
        "AL Cost Variance",
        filters={"creation": ["between", [date_from, date_to]]},
        fields=["variance_status", "variance_pct", "impact_on_margin", "item_code"],
    )

    summary = {
        "total": len(records),
        "normal": 0,
        "caution": 0,
        "alert": 0,
        "favorable": 0,
        "total_impact": 0,
        "avg_variance_pct": 0,
    }

    for r in records:
        status = r.variance_status
        if status == "NORMAL":
            summary["normal"] += 1
        elif status == "CAUTION":
            summary["caution"] += 1
        elif status == "ALERT":
            summary["alert"] += 1
        elif status == "FAVORABLE":
            summary["favorable"] += 1
        summary["total_impact"] += r.impact_on_margin or 0

    if records:
        summary["avg_variance_pct"] = sum(
            abs(r.variance_pct or 0) for r in records
        ) / len(records)

    return summary
