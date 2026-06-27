"""
API endpoints for Material Planning (MRP Lite)
"""
import frappe
from frappe import _


@frappe.whitelist()
def create_material_plan(plan_name, source_type, quotation_list, so_list=None,
                         aggregation_method="BY_ITEM", include_safety_stock_pct=5):
    """Tạo Material Plan từ danh sách Quotation/SO."""
    import json

    plan = frappe.new_doc("AL Material Plan")
    plan.plan_name = plan_name
    plan.plan_date = frappe.utils.today()
    plan.status = "Draft"
    plan.source_type = source_type
    plan.quotation_list = quotation_list if isinstance(quotation_list, str) else json.dumps(quotation_list)
    plan.so_list = so_list if isinstance(so_list, str) else json.dumps(so_list or [])
    plan.aggregation_method = aggregation_method
    plan.include_safety_stock_pct = include_safety_stock_pct
    plan.insert(ignore_permissions=True)

    # Tổng hợp vật tư
    from alumglass.modules.mrp.mrp_aggregator import MRPAggregator
    agg = MRPAggregator()
    plan = agg.populate_plan_lines(plan)
    plan.save(ignore_permissions=True)

    return {
        "plan_name": plan.name,
        "total_lines": len(plan.al_plan_lines),
        "grand_total": plan.grand_total_value,
    }


@frappe.whitelist()
def get_plan_summary(plan_name):
    """Lấy tổng hợp vật tư cho 1 plan."""
    plan = frappe.get_doc("AL Material Plan", plan_name)

    lines = []
    for line in plan.al_plan_lines:
        lines.append({
            "item_code": line.item_code,
            "item_name": line.item_name,
            "item_type": line.item_type,
            "total_qty_net": line.total_qty_net,
            "current_stock_qty": line.current_stock_qty,
            "qty_to_purchase": line.qty_to_purchase,
            "estimated_total": line.estimated_total,
        })

    return {
        "plan_name": plan.plan_name,
        "status": plan.status,
        "source_type": plan.source_type,
        "lines": lines,
        "total_nhom": plan.total_nhom_value,
        "total_kinh": plan.total_kinh_value,
        "total_vtp": plan.total_vtp_value,
        "total_pk": plan.total_pk_value,
        "grand_total": plan.grand_total_value,
    }


@frappe.whitelist()
def generate_po_from_plan(plan_name):
    """Tạo Purchase Orders từ Material Plan."""
    if not frappe.has_permission("AL Material Plan", "write", plan_name):
        frappe.throw(_("Bạn không có quyền tạo PO từ plan này."))

    plan = frappe.get_doc("AL Material Plan", plan_name)
    from alumglass.modules.mrp.mrp_aggregator import MRPAggregator
    agg = MRPAggregator()
    po_names = agg.generate_purchase_orders(plan)

    return {
        "purchase_orders": po_names,
        "count": len(po_names),
    }
