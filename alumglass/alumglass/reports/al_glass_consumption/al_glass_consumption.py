# AL Glass Consumption Report — Glass usage by type, thickness, project
import frappe
from frappe.utils import flt, today, add_to_date


def execute(filters=None):
    """Generate Glass Consumption report from ConfigSnapshots."""
    filters = filters or {}
    from_date = filters.get("from_date") or add_to_date(today(), months=-6)
    to_date = filters.get("to_date") or today()

    data = frappe.db.sql(
        """
        SELECT
            cs.creation AS date,
            cs.quotation,
            cs.quotation_item_name,
            cs.glass_master_hashes,
            cs.enterprise_snapshot_json
        FROM `tabConfigSnapshot` cs
        WHERE cs.creation BETWEEN %s AND %s
        ORDER BY cs.creation DESC
        """,
        (from_date, to_date),
        as_dict=True,
    )

    # Parse glass data from snapshots
    import json
    result = []
    for d in data:
        try:
            snap = json.loads(d.enterprise_snapshot_json)
            results = snap.get("results", {})
            inputs = snap.get("inputs", {})

            # Find glass-related results
            for key, value in results.items():
                if "_glass_thick_mm" in key and flt(value) > 0:
                    prefix = key.replace("_glass_thick_mm", "")
                    m2_key = f"{prefix}_m2" if f"{prefix}_m2" in results else f"{prefix}_total_m2"
                    area = flt(results.get(m2_key, 0))
                    if area > 0:
                        result.append({
                            "date": d.date,
                            "quotation": d.quotation,
                            "prefix": prefix,
                            "thickness_mm": flt(value),
                            "area_m2": area,
                        })
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # Aggregate
    total_area = sum(flt(r["area_m2"]) for r in result)

    columns = [
        {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "quotation", "label": "Quotation", "fieldtype": "Link", "options": "Quotation", "width": 150},
        {"fieldname": "prefix", "label": "Glass Prefix", "fieldtype": "Data", "width": 120},
        {"fieldname": "thickness_mm", "label": "Thickness (mm)", "fieldtype": "Float", "width": 110},
        {"fieldname": "area_m2", "label": "Area (m²)", "fieldtype": "Float", "width": 100},
    ]

    return columns, result, None, None, {
        "total_area_m2": round(total_area, 2),
        "total_panels": len(result),
        "period": f"{from_date} to {to_date}",
    }
