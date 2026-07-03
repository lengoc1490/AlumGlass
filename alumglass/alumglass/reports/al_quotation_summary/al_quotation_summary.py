# AL Quotation Summary Report — Quotation performance by BOM, Sales, Customer
import frappe
from frappe.utils import flt, getdate, today, add_to_date


def execute(filters=None):
    """Generate Quotation Summary report."""
    filters = filters or {}
    from_date = filters.get("from_date") or add_to_date(today(), months=-3)
    to_date = filters.get("to_date") or today()
    sales_user = filters.get("sales_user")
    bom = filters.get("bom")

    conditions = ["q.docstatus IN (0, 1)", "q.transaction_date BETWEEN %s AND %s"]
    params = [from_date, to_date]

    if sales_user:
        conditions.append("q.owner = %s")
        params.append(sales_user)
    if bom:
        conditions.append("qi.al_bom = %s")
        params.append(bom)

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            q.name AS quotation,
            q.transaction_date AS date,
            q.customer_name AS customer,
            q.owner AS sales_user,
            qi.item_code,
            qi.item_name,
            qi.al_bom AS bom,
            qi.al_selling_price AS selling_price,
            qi.al_total_cost AS total_cost,
            qi.al_discount_pct AS discount_pct,
            qi.al_commercial_price AS commercial_price,
            qi.al_unit_price_per_m2 AS unit_price_m2,
            qi.al_bom_version AS bom_version,
            qi.al_approval_status AS approval_status
        FROM `tabQuotation` q
        INNER JOIN `tabQuotation Item` qi ON qi.parent = q.name
        WHERE {where_clause} AND qi.al_bom IS NOT NULL
        ORDER BY q.transaction_date DESC, q.name
        """,
        tuple(params),
        as_dict=True,
    )

    # Summary
    total_quotations = len(set(d.quotation for d in data))
    total_value = sum(flt(d.commercial_price or d.selling_price or 0) for d in data)
    total_cost = sum(flt(d.total_cost or 0) for d in data)
    avg_margin = ((total_value - total_cost) / total_value * 100) if total_value > 0 else 0

    columns = [
        {"fieldname": "quotation", "label": "Quotation", "fieldtype": "Link", "options": "Quotation", "width": 150},
        {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "customer", "label": "Customer", "fieldtype": "Data", "width": 200},
        {"fieldname": "sales_user", "label": "Sales User", "fieldtype": "Data", "width": 120},
        {"fieldname": "item_code", "label": "Item", "fieldtype": "Data", "width": 120},
        {"fieldname": "bom", "label": "BOM", "fieldtype": "Link", "options": "AL BOM", "width": 150},
        {"fieldname": "selling_price", "label": "Selling Price", "fieldtype": "Currency", "width": 120},
        {"fieldname": "total_cost", "label": "Total Cost", "fieldtype": "Currency", "width": 120},
        {"fieldname": "discount_pct", "label": "Discount %", "fieldtype": "Percent", "width": 80},
        {"fieldname": "commercial_price", "label": "Commercial Price", "fieldtype": "Currency", "width": 130},
        {"fieldname": "unit_price_m2", "label": "Unit Price/m²", "fieldtype": "Currency", "width": 120},
        {"fieldname": "bom_version", "label": "BOM Version", "fieldtype": "Link", "options": "AL BOM Version", "width": 150},
        {"fieldname": "approval_status", "label": "Approval", "fieldtype": "Data", "width": 100},
    ]

    return columns, data, None, None, {
        "total_quotations": total_quotations,
        "total_value": total_value,
        "total_cost": total_cost,
        "avg_margin_pct": round(avg_margin, 1),
        "period": f"{from_date} to {to_date}",
    }
