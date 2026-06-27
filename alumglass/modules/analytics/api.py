"""
API endpoints for Sales Analytics & Dashboard
"""
import frappe


@frappe.whitelist()
def get_sales_kpi(user=None, period_type="MONTHLY"):
    """Lấy KPI của user trong kỳ."""
    from alumglass.modules.analytics.kpi_calculator import get_sales_kpi as _get_kpi
    return _get_kpi(user, period_type)


@frappe.whitelist()
def get_dashboard_data():
    """Lấy dữ liệu cho Dashboard widget theo role của user hiện tại."""
    roles = frappe.get_roles()
    data = {"widgets": []}

    if "AluGlass Admin" in roles or "AluGlass Director" in roles:
        data["widgets"].append(_admin_dashboard())

    if "AluGlass Sales" in roles:
        data["widgets"].append(_sales_dashboard())

    if "AluGlass Kỹ Thuật" in roles:
        data["widgets"].append(_kythuat_dashboard())

    return data


def _admin_dashboard():
    """Dashboard data cho Admin."""
    from frappe.utils import today, get_first_day, get_last_day

    date_from = get_first_day(today())
    date_to = get_last_day(today())

    # Doanh số tháng này
    so_total = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE docstatus = 1
          AND transaction_date BETWEEN %s AND %s
    """, (date_from, date_to))[0][0]

    # Quotation → SO rate (30 ngày)
    qt_count = frappe.db.count("Quotation", {
        "docstatus": 1,
        "transaction_date": ["between", [date_from, date_to]],
    })
    so_count = frappe.db.count("Sales Order", {
        "docstatus": 1,
        "transaction_date": ["between", [date_from, date_to]],
    })
    conversion_rate = (so_count / qt_count * 100) if qt_count else 0

    # Pending approvals
    pending = frappe.db.count("Quotation Item", {"al_approval_status": "PENDING"})

    return {
        "type": "admin",
        "metrics": {
            "monthly_revenue": so_total,
            "conversion_rate": round(conversion_rate, 1),
            "pending_approvals": pending,
        },
    }


def _sales_dashboard():
    """Dashboard data cho Sales."""
    from frappe.utils import today, get_first_day, get_last_day

    date_from = get_first_day(today())
    date_to = get_last_day(today())

    # Quotation của user
    my_qt = frappe.db.count("Quotation", {
        "owner": frappe.session.user,
        "docstatus": 1,
        "transaction_date": ["between", [date_from, date_to]],
    })

    # KPI
    from alumglass.modules.analytics.kpi_calculator import get_sales_kpi
    kpi = get_sales_kpi(frappe.session.user, "MONTHLY")

    return {
        "type": "sales",
        "metrics": {
            "my_quotations": my_qt,
            "kpi": kpi,
        },
    }


def _kythuat_dashboard():
    """Dashboard data cho Kỹ Thuật."""
    active_boms = frappe.db.count("AL BOM", {"is_active": 1, "current_version": ["!=", ""]})

    # Recent versions
    recent_versions = frappe.get_all(
        "AL BOM Version",
        filters={"status": "Published"},
        fields=["name", "bom", "version_number", "published_on"],
        order_by="published_on desc",
        limit=5,
    )

    return {
        "type": "kythuat",
        "metrics": {
            "active_boms": active_boms,
            "recent_versions": recent_versions,
        },
    }
