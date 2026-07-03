"""
AlumGlass Modules v17 — Module Hook Registry
Each module self-registers via event bus. Orchestrator does NOT import modules directly.

Pattern: Module hooks run AFTER core calculation completes.
Hooks that fail do NOT block the calculation thread (they log errors).
Timeout: 5 seconds per hook to prevent blocking.
"""
import frappe
from alumglass.engine.module_registry import register_hook

# P0: Register custom source_type handlers into formula_builder
try:
    from alumglass.fb_handlers import register_handlers
    register_handlers()
except Exception as e:
    frappe.log_error(f"Failed to register FB custom handlers: {e}")

# Lazy imports — only trigger registration, let hooks.py call register_all_hooks()


def register_all_hooks():
    """Called at app load — registers all module hooks into the event bus.
    Each module's hook is wrapped in try/except so a single module failure
    does not prevent other modules from loading.
    """
    # Hook A: Discount Stack — apply after calculation
    try:
        from alumglass.modules.discount.discount_stack import DiscountStack
        register_hook("after_calculate", DiscountStack.apply)
    except Exception as e:
        frappe.log_error(f"Failed to register DiscountStack hook: {e}")

    # Hook B: BOM Version Manager — link version to quotation item
    try:
        from alumglass.modules.version.bom_version_manager import BOMVersionManager
        register_hook("after_calculate", BOMVersionManager.link_version)
    except Exception as e:
        frappe.log_error(f"Failed to register BOMVersionManager hook: {e}")

    # Hook C: Cost Variance Analyzer — register quotation reference
    try:
        from alumglass.modules.cost_variance.variance_analyzer import CostVarianceAnalyzer
        register_hook("after_calculate", CostVarianceAnalyzer.register_quotation_reference)
    except Exception as e:
        frappe.log_error(f"Failed to register CostVarianceAnalyzer hook: {e}")

    # Hook D: Notification Engine — check alerts
    try:
        from alumglass.modules.notification.notification_engine import NotificationEngine
        register_hook("after_calculate", NotificationEngine.check_alerts)
    except Exception as e:
        frappe.log_error(f"Failed to register NotificationEngine hook: {e}")
