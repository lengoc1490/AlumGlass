# AL Material Cost Variance Report — Compare quoted vs actual purchase prices
import frappe
from frappe.utils import flt, today, add_to_date


def execute(filters=None):
    """Generate Material Cost Variance report."""
    filters = filters or {}
    from_date = filters.get("from_date") or add_to_date(today(), months=-6)
    to_date = filters.get("to_date") or today()
    variance_status = filters.get("variance_status")

    conditions = ["cv.creation BETWEEN %s AND %s"]
    params = [from_date, to_date]

    if variance_status:
        conditions.append("cv.variance_status = %s")
        params.append(variance_status)

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            cv.name,
            cv.creation AS date,
            cv.item_code,
            cv.quoted_unit_price,
            cv.actual_unit_price,
            cv.variance_amount,
            cv.variance_pct,
            cv.variance_status,
            cv.impact_on_margin,
            cv.purchase_invoice,
            cv.quotation_item,
            cv.reviewed_by,
            cv.review_note
        FROM `tabAL Cost Variance` cv
        WHERE {where_clause}
        ORDER BY ABS(cv.variance_pct) DESC, cv.creation DESC
        """,
        tuple(params),
        as_dict=True,
    )

    # Summary
    total_variance = sum(flt(d.impact_on_margin or 0) for d in data)
    alert_count = sum(1 for d in data if d.variance_status == "ALERT")
    caution_count = sum(1 for d in data if d.variance_status == "CAUTION")
    favorable_count = sum(1 for d in data if d.variance_status == "FAVORABLE")

    columns = [
        {"fieldname": "name", "label": "Variance ID", "fieldtype": "Link", "options": "AL Cost Variance", "width": 150},
        {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "item_code", "label": "Item", "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "quoted_unit_price", "label": "Quoted Price", "fieldtype": "Currency", "width": 120},
        {"fieldname": "actual_unit_price", "label": "Actual Price", "fieldtype": "Currency", "width": 120},
        {"fieldname": "variance_amount", "label": "Variance", "fieldtype": "Currency", "width": 100},
        {"fieldname": "variance_pct", "label": "Variance %", "fieldtype": "Percent", "width": 90},
        {"fieldname": "variance_status", "label": "Status", "fieldtype": "Data", "width": 90},
        {"fieldname": "impact_on_margin", "label": "Margin Impact", "fieldtype": "Currency", "width": 120},
        {"fieldname": "purchase_invoice", "label": "Purchase Invoice", "fieldtype": "Link", "options": "Purchase Invoice", "width": 150},
        {"fieldname": "quotation_item", "label": "Quotation Item", "fieldtype": "Link", "options": "Quotation Item", "width": 150},
        {"fieldname": "reviewed_by", "label": "Reviewed By", "fieldtype": "Data", "width": 120},
        {"fieldname": "review_note", "label": "Review Note", "fieldtype": "Data", "width": 200},
    ]

    return columns, data, None, None, {
        "total_variance": total_variance,
        "alert_count": alert_count,
        "caution_count": caution_count,
        "favorable_count": favorable_count,
        "period": f"{from_date} to {to_date}",
    }
