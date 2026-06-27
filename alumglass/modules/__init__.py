"""
AlumGlass Modules v17 — P0 Updated: Đăng ký custom FB handlers + hooks
Mỗi module tự register qua event bus, Orchestrator không import module nào.
"""
from alumglass.engine.module_registry import register_hook

# P0: Đăng ký custom source_type handlers vào formula_builder
from alumglass.fb_handlers import register_handlers
register_handlers()

# Import để trigger registration
from alumglass.modules.discount.discount_stack import DiscountStack
from alumglass.modules.version.bom_version_manager import BOMVersionManager
from alumglass.modules.cost_variance.variance_analyzer import CostVarianceAnalyzer
from alumglass.modules.notification.notification_engine import NotificationEngine


# Register tất cả hooks
def register_all_hooks():
    """Gọi khi app load — đăng ký hooks vào event bus."""
    # Hook A: Discount sau calculate
    register_hook("after_calculate", DiscountStack.apply)

    # Hook B: Link BOM Version
    register_hook("after_calculate", BOMVersionManager.link_version)

    # Hook C: Register Cost Variance reference
    register_hook("after_calculate", CostVarianceAnalyzer.register)

    # Hook D: Check alerts
    register_hook("after_calculate", NotificationEngine.check_alerts)


# Auto-register khi import
register_all_hooks()
