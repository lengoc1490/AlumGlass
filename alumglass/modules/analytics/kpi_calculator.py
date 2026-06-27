"""
Sales KPI Calculator — Scheduled job cập nhật KPI
"""
import frappe
from frappe.utils import flt, now, get_first_day, get_last_day, today


def update_all_kpi(period_type="MONTHLY"):
    """Scheduled job: cập nhật KPI cho tất cả sales users."""
    period_label = _get_period_label(period_type)
    date_from, date_to = _get_period_dates(period_type)

    users = frappe.get_all("User", filters={"enabled": 1}, fields=["name"])

    for user in users:
        try:
            _update_user_kpi(user.name, period_type, period_label, date_from, date_to)
        except Exception as e:
            frappe.log_error(
                title=f"KPI update failed for {user.name}",
                message=str(e),
            )

    frappe.db.commit()


def _update_user_kpi(user, period_type, period_label, date_from, date_to):
    """Tính KPI cho 1 user."""
    # Tìm hoặc tạo KPI record
    kpi_name = frappe.db.exists("AL Sales KPI", {
        "sales_user": user,
        "kpi_period": period_type,
        "period_label": period_label,
    })

    if not kpi_name:
        kpi = frappe.new_doc("AL Sales KPI")
        kpi.sales_user = user
        kpi.kpi_period = period_type
        kpi.period_label = period_label
        kpi.insert(ignore_permissions=True)
        kpi_name = kpi.name

    kpi = frappe.get_doc("AL Sales KPI", kpi_name)

    # Quotation trong kỳ (submitted, owned by user)
    quotations = frappe.get_all(
        "Quotation",
        filters={
            "owner": user,
            "docstatus": 1,
            "transaction_date": ["between", [date_from, date_to]],
        },
        fields=["name", "grand_total"],
    )
    kpi.actual_quotations = len(quotations)

    if not quotations:
        kpi.last_calculated_on = now()
        kpi.save(ignore_permissions=True)
        return

    q_names = [q.name for q in quotations]

    # Sales Orders linked from user's quotations
    so_items = frappe.get_all(
        "Sales Order Item",
        filters={"prevdoc_docname": ["in", q_names]},
        fields=["parent", "prevdoc_docname", "amount"],
    )

    # Conversion rate
    unique_converted = set(i.prevdoc_docname for i in so_items)
    kpi.conversion_rate_actual = (
        len(unique_converted) / len(quotations) * 100
    )

    # Doanh số thực tế từ SO
    so_parents = list(set(i.parent for i in so_items))
    if so_parents:
        so_totals = frappe.get_all(
            "Sales Order",
            filters={"name": ["in", so_parents], "docstatus": 1},
            fields=["grand_total"],
        )
        kpi.actual_amount = sum(flt(s.grand_total) for s in so_totals)
    else:
        kpi.actual_amount = 0

    # Margin thực tế
    qi_list = frappe.get_all(
        "Quotation Item",
        filters={"parent": ["in", q_names]},
        fields=["al_gia_ban", "al_gia_thanh", "al_discount_pct"],
    )

    gia_ban_sum = sum(flt(i.al_gia_ban or 0) for i in qi_list)
    gia_thanh_sum = sum(flt(i.al_gia_thanh or 0) for i in qi_list)

    kpi.avg_margin_actual_pct = (
        (gia_ban_sum - gia_thanh_sum) / gia_ban_sum * 100
        if gia_ban_sum else 0
    )

    # Discount trung bình
    discounts = [flt(i.al_discount_pct) for i in qi_list if flt(i.al_discount_pct) > 0]
    kpi.avg_discount_pct = (
        sum(discounts) / len(discounts) if discounts else 0
    )

    kpi.last_calculated_on = now()
    kpi.save(ignore_permissions=True)


def _get_period_label(period_type):
    """Tạo period label. VD: '2025-06' cho MONTHLY."""
    t = today()
    if period_type == "MONTHLY":
        return t[:7]  # "2025-06"
    elif period_type == "QUARTERLY":
        month = int(t[5:7])
        quarter = (month - 1) // 3 + 1
        return f"{t[:4]}-Q{quarter}"
    elif period_type == "YEARLY":
        return t[:4]
    return today()


def _get_period_dates(period_type):
    """Lấy date_from, date_to cho period."""
    t = today()
    if period_type == "MONTHLY":
        return get_first_day(t), get_last_day(t)
    elif period_type == "QUARTERLY":
        month = int(t[5:7])
        quarter = (month - 1) // 3 + 1
        q_start_month = (quarter - 1) * 3 + 1
        q_end_month = q_start_month + 2
        return (
            f"{t[:4]}-{q_start_month:02d}-01",
            get_last_day(f"{t[:4]}-{q_end_month:02d}-01"),
        )
    elif period_type == "YEARLY":
        return f"{t[:4]}-01-01", f"{t[:4]}-12-31"
    return get_first_day(t), get_last_day(t)


@frappe.whitelist()
def get_sales_kpi(user=None, period_type="MONTHLY"):
    """API: Lấy KPI của user."""
    if not user:
        user = frappe.session.user

    period_label = _get_period_label(period_type)
    kpi = frappe.db.get_value(
        "AL Sales KPI",
        {
            "sales_user": user,
            "kpi_period": period_type,
            "period_label": period_label,
        },
        ["*"],
        as_dict=True,
    )
    return kpi or {}
