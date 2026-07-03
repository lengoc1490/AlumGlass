"""
AlumGlass ERP v17.0 — Public API Endpoints
All endpoints are whitelisted for client-side (JS) calls.
"""
import frappe
import json
from frappe.utils import flt


@frappe.whitelist()
def get_bom_dialog_config(bom_doc_name):
    """Get config for BOM Dialog UI: variables, glass lines, accessory lines, cost templates."""
    from alumglass.engine.orchestrator import BomOrchestrator
    orch = BomOrchestrator()
    return orch.get_bom_dialog_config(bom_doc_name)


@frappe.whitelist()
def calculate_quotation_item(quotation_item_name, bom_doc_name):
    """Calculate price for a Quotation Item using the BOM engine.
    Called when Sales clicks "Calculate" in BOM Dialog.
    """
    from alumglass.engine.orchestrator import BomOrchestrator
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    orch = BomOrchestrator()
    return orch.run(qi, bom_doc_name)


@frappe.whitelist()
def get_explain_tree(formula_name, quotation_item_name, bom_doc_name):
    """Get explanation tree for a formula — used for EnrichedExplain UI."""
    from alumglass.engine.orchestrator import BomOrchestrator
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    orch = BomOrchestrator()
    return orch.explain(formula_name, qi, bom_doc_name)


@frappe.whitelist()
def get_bom_version_info(bom_doc_name):
    """Get version history for a BOM."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    mgr = BOMVersionManager()
    return mgr.get_version_info(bom_doc_name)


@frappe.whitelist()
def compare_versions(version_1_name, version_2_name):
    """Compare two BOM Versions and return diff."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    mgr = BOMVersionManager()
    return mgr.compare_versions(version_1_name, version_2_name)


@frappe.whitelist()
def get_applicable_discounts(quotation_item_name):
    """Get applicable discount rules for a quotation item."""
    from alumglass.modules.discount.discount_stack import DiscountStack
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    return DiscountStack.get_applicable_discounts(qi)


@frappe.whitelist()
def apply_manual_discount(quotation_item_name, discount_rule_name):
    """Apply a manual discount rule to a quotation item."""
    from alumglass.modules.discount.discount_stack import DiscountStack
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    return DiscountStack.apply_manual_discount(qi, discount_rule_name)


@frappe.whitelist()
def get_material_plan(plan_name):
    """Get material plan with calculated quantities."""
    from alumglass.modules.mrp.mrp_aggregator import MRPAggregator
    plan = frappe.get_doc("AL Material Plan", plan_name)
    aggregator = MRPAggregator()
    return aggregator.get_plan_with_stock_info(plan)


@frappe.whitelist()
def generate_plan_lines(plan_name):
    """Generate material plan lines from quotation/SO pool."""
    from alumglass.modules.mrp.mrp_aggregator import MRPAggregator
    plan = frappe.get_doc("AL Material Plan", plan_name)
    aggregator = MRPAggregator()
    return aggregator.generate_plan_lines(plan)


@frappe.whitelist()
def check_alerts_for_quotation(quotation_name):
    """Check and trigger alerts for a quotation."""
    from alumglass.modules.notification.notification_engine import NotificationEngine
    engine = NotificationEngine()
    return engine.check_alerts_for_quotation(quotation_name)


@frappe.whitelist()
def get_sales_kpi_dashboard(kpi_period="MONTHLY"):
    """Get sales KPI dashboard data."""
    period_label = _get_current_period_label(kpi_period)
    kpis = frappe.get_all(
        "AL Sales KPI",
        filters={"kpi_period": kpi_period, "period_label": period_label},
        fields=["*"],
    )
    return {
        "period": period_label,
        "kpis": kpis,
    }


@frappe.whitelist()
def publish_bom_version(bom_name, change_summary=""):
    """Publish a new BOM version (snapshot current configuration)."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    bom = frappe.get_doc("AL BOM", bom_name)
    mgr = BOMVersionManager()
    return mgr.publish(bom, change_summary).as_dict()


@frappe.whitelist()
def rollback_bom_version(version_name):
    """Rollback BOM to a previous version."""
    from alumglass.modules.version.bom_version_manager import BOMVersionManager
    mgr = BOMVersionManager()
    return mgr.rollback(version_name).as_dict()


def _get_current_period_label(period_type):
    """Get current period label for KPI dashboard."""
    from datetime import date
    today_date = date.today()
    if period_type == "MONTHLY":
        return today_date.strftime("%Y-%m")
    elif period_type == "QUARTERLY":
        q = (today_date.month - 1) // 3 + 1
        return f"{today_date.year}-Q{q}"
    elif period_type == "YEARLY":
        return str(today_date.year)
    return ""
