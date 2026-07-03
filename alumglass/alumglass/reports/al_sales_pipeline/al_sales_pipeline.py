# AL Sales Pipeline Report — Quotation → SO → SI conversion tracking
import frappe
from frappe.utils import flt, today, add_to_date, getdate


def execute(filters=None):
    """Generate Sales Pipeline report with conversion rates."""
    filters = filters or {}
    from_date = filters.get("from_date") or add_to_date(today(), months=-6)
    to_date = filters.get("to_date") or today()
    sales_user = filters.get("sales_user")

    # Get all quotations in period
    qt_conditions = ["q.transaction_date BETWEEN %s AND %s", "qi.al_bom IS NOT NULL"]
    qt_params = [from_date, to_date]

    if sales_user:
        qt_conditions.append("q.owner = %s")
        qt_params.append(sales_user)

    qt_where = " AND ".join(qt_conditions)

    quotations = frappe.db.sql(
        f"""
        SELECT
            q.name, q.owner AS sales_user, q.transaction_date,
            q.customer_name, q.status,
            qi.al_bom AS bom, qi.al_selling_price AS selling_price,
            qi.al_total_cost AS total_cost,
            qi.al_commercial_price AS commercial_price
        FROM `tabQuotation` q
        INNER JOIN `tabQuotation Item` qi ON qi.parent = q.name
        WHERE {qt_where}
        ORDER BY q.transaction_date
        """,
        tuple(qt_params),
        as_dict=True,
    )

    # Get SO data
    qt_names = list(set(q.name for q in quotations))
    so_data = {}
    if qt_names:
        so_items = frappe.db.sql(
            """
            SELECT
                soi.al_source_quotation_item AS qt_name,
                so.name AS so_name,
                so.transaction_date,
                so.status
            FROM `tabSales Order Item` soi
            INNER JOIN `tabSales Order` so ON so.name = soi.parent
            WHERE soi.al_source_quotation_item IN %s
            """,
            (qt_names,),
            as_dict=True,
        )
        for s in so_items:
            so_data[s.qt_name] = s

    # Build pipeline data
    data = []
    for q in quotations:
        so = so_data.get(q.name, {})
        data.append({
            "quotation": q.name,
            "date": q.transaction_date,
            "customer": q.customer_name,
            "sales_user": q.sales_user,
            "bom": q.bom,
            "selling_price": flt(q.selling_price or q.commercial_price or 0),
            "total_cost": flt(q.total_cost or 0),
            "qt_status": q.status,
            "so": so.get("so_name"),
            "so_status": so.get("status"),
            "converted": 1 if so else 0,
        })

    # Summary
    total_qt = len(data)
    converted = sum(1 for d in data if d["converted"])
    conversion_rate = (converted / total_qt * 100) if total_qt > 0 else 0
    total_value = sum(d["selling_price"] for d in data)
    total_margin = sum(d["selling_price"] - d["total_cost"] for d in data)

    columns = [
        {"fieldname": "quotation", "label": "Quotation", "fieldtype": "Link", "options": "Quotation", "width": 150},
        {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "customer", "label": "Customer", "fieldtype": "Data", "width": 200},
        {"fieldname": "sales_user", "label": "Sales User", "fieldtype": "Data", "width": 120},
        {"fieldname": "bom", "label": "BOM", "fieldtype": "Link", "options": "AL BOM", "width": 180},
        {"fieldname": "selling_price", "label": "Selling Price", "fieldtype": "Currency", "width": 120},
        {"fieldname": "total_cost", "label": "Total Cost", "fieldtype": "Currency", "width": 120},
        {"fieldname": "qt_status", "label": "QT Status", "fieldtype": "Data", "width": 90},
        {"fieldname": "so", "label": "Sales Order", "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"fieldname": "so_status", "label": "SO Status", "fieldtype": "Data", "width": 90},
        {"fieldname": "converted", "label": "Converted", "fieldtype": "Check", "width": 80},
    ]

    return columns, data, None, None, {
        "total_quotations": total_qt,
        "converted": converted,
        "conversion_rate_pct": round(conversion_rate, 1),
        "total_value": total_value,
        "total_margin": total_margin,
        "period": f"{from_date} to {to_date}",
    }
