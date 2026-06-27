"""
Cost Variance Analyzer — So sánh giá Quotation vs Purchase thực tế (Hook C)
"""
import frappe
import json
from frappe.utils import flt


class CostVarianceAnalyzer:
    """Phân tích biến động giá giữa báo giá và mua thực tế."""

    @staticmethod
    def register(result, quotation_item, bom_doc, snapshot, **kwargs):
        """Hook C — Đăng ký reference để so sánh sau khi có Purchase Invoice."""
        # Hook C chỉ đăng ký — variance được tạo khi Purchase Invoice submit
        # Không cần action ngay lúc này vì chưa có purchase data
        pass


def on_purchase_invoice_submit(doc, method):
    """Hook: khi Purchase Invoice submit → tạo AL Cost Variance."""
    for item in doc.items:
        try:
            related_items = find_related_quotation_items(item.item_code, doc.posting_date)
            for qi in related_items:
                create_cost_variance(qi, item, doc)
        except Exception as e:
            frappe.log_error(
                title=f"Cost Variance creation failed for {item.item_code}",
                message=str(e),
            )


def find_related_quotation_items(item_code, posting_date):
    """Tìm Quotation Items dùng item này trong 90 ngày trước posting_date."""
    since = frappe.utils.add_days(posting_date, -90)

    # Simple approach: find QT Items with config_snapshot that reference this item
    qi_with_snapshots = frappe.db.sql("""
        SELECT qi.name, qi.al_config_snapshot, qi.qty, qi.parent
        FROM `tabQuotation Item` qi
        JOIN `tabQuotation` q ON qi.parent = q.name
        WHERE qi.al_config_snapshot IS NOT NULL
          AND qi.al_config_snapshot != ''
          AND q.docstatus = 1
          AND q.transaction_date >= %s
        ORDER BY q.transaction_date DESC
    """, (since,), as_dict=True)

    related = []
    for qi in qi_with_snapshots:
        try:
            snap = frappe.get_doc("ConfigSnapshot", qi.al_config_snapshot)
            data = json.loads(snap.enterprise_snapshot_json)
            formulas = data.get("formulas", {})

            # Check if this item_code appears in any formula
            # Heuristic: item codes appear in _dg (unit price) formulas
            for var_name, formula_str in formulas.items():
                if var_name.endswith("_dg") and item_code.lower().replace("-", "_") in var_name.lower():
                    related.append(qi)
                    break
        except Exception:
            continue

    return related


def create_cost_variance(qi, pi_item, pi_doc):
    """Tạo AL Cost Variance record với dedup check."""
    # Dedup
    existing = frappe.db.exists("AL Cost Variance", {
        "quotation_item": qi.name,
        "purchase_invoice": pi_doc.name,
        "item_code": pi_item.item_code,
    })
    if existing:
        return

    # Lấy giá đã báo từ ConfigSnapshot
    quoted_price = 0
    try:
        snap = frappe.get_doc("ConfigSnapshot", qi.al_config_snapshot)
        data = json.loads(snap.enterprise_snapshot_json)
        results = data.get("results", {})

        # Tìm key _dg tương ứng với item_code
        item_key = pi_item.item_code.lower().replace("-", "_")
        for var_name, value in results.items():
            if var_name.endswith("_dg") and item_key in var_name.lower():
                quoted_price = flt(value)
                break
    except Exception:
        pass

    actual_price = flt(pi_item.rate or 0)

    if quoted_price == 0:
        quoted_price = actual_price  # fallback

    if quoted_price == 0:
        return  # Không đủ dữ liệu

    variance_pct = ((actual_price - quoted_price) / quoted_price * 100) if quoted_price else 0

    if variance_pct < -5:
        status = "FAVORABLE"
    elif abs(variance_pct) < 5:
        status = "NORMAL"
    elif abs(variance_pct) < 15:
        status = "CAUTION"
    else:
        status = "ALERT"

    cv = frappe.new_doc("AL Cost Variance")
    cv.quotation_item = qi.name
    cv.config_snapshot = qi.al_config_snapshot
    cv.purchase_invoice = pi_doc.name
    cv.item_code = pi_item.item_code
    cv.quoted_unit_price = quoted_price
    cv.actual_unit_price = actual_price
    cv.variance_amount = actual_price - quoted_price
    cv.variance_pct = variance_pct
    cv.variance_status = status
    cv.impact_on_margin = (actual_price - quoted_price) * flt(qi.qty or 1)
    cv.insert(ignore_permissions=True)

    frappe.db.commit()


@frappe.whitelist()
def get_cost_variances(filters=None):
    """API: Lấy danh sách Cost Variance."""
    filters = filters or {}
    return frappe.get_all(
        "AL Cost Variance",
        filters=filters,
        fields=["*"],
        order_by="creation desc",
    )
