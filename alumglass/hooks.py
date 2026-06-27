"""
AlumGlass ERP v17.0 — App Hooks
Phụ thuộc: formula_builder (formula_utils v29.1+)
"""
app_name = "alumglass"
app_title = "AlumGlass ERP"
app_publisher = "Lê Ngọc"
app_description = "ERP for aluminum & glass manufacturing — Quotation, BOM, Costing, MRP"
app_email = "lengoc1490@gmail.com"
app_license = "mit"

# ---- JS / CSS Includes ----
app_include_js = [
    "/assets/formula_builder/js/formula_builder.js",
    "/assets/formula_builder/js/formula_builder_field.js",
    "/assets/formula_builder/js/formula_builder_dialog.js",
    "/assets/alumglass/js/quotation_item.js",
    "/assets/alumglass/js/bom_dialog.js",
]
app_include_css = [
    "/assets/formula_builder/css/formula_builder.css",
    "/assets/formula_builder/css/formula_builder_field.css",
]

# ---- Doctype JS overrides ----
doctype_js = {
    "Sales Order": "alumglass/doctype/overrides/sales_order.js",
}

# ---- Document Events ----
doc_events = {
    "Quotation": {
        "before_submit": "alumglass.modules.approval.approval_engine.check_pending_approvals",
    },
    "Sales Order": {
        "before_insert": "alumglass.engine.orchestrator.copy_al_fields_to_so",
    },
    "Sales Invoice": {
        "before_insert": "alumglass.engine.orchestrator.copy_al_fields_to_si",
    },
    "Purchase Invoice": {
        "on_submit": "alumglass.modules.cost_variance.variance_analyzer.on_purchase_invoice_submit",
    },
    "AL BOM Version": {
        "after_insert": "alumglass.modules.version.bom_version_manager.on_version_created",
        "on_update": "alumglass.modules.version.bom_version_manager.on_version_status_changed",
    },
}

# ---- Scheduler Events ----
scheduler_events = {
    "daily": [
        "alumglass.scheduled_tasks.update_sales_kpi",
        "alumglass.scheduled_tasks.check_price_change_alerts",
        "alumglass.scheduled_tasks.check_low_stock_alerts",
        "alumglass.scheduled_tasks.generate_daily_digest",
    ],
    "weekly": [
        "alumglass.scheduled_tasks.deprecate_old_bom_versions",
    ],
}

# ---- Fixtures ----
fixtures = [
    {"doctype": "AL Variable Group", "filters": []},
    {"doctype": "AL Glass Type", "filters": []},
    {"doctype": "AL Glass Master", "filters": []},
    {"doctype": "AL Variable Library", "filters": []},
    {"doctype": "AL Variable Binding", "filters": []},
    {"doctype": "AL Calculation Rule", "filters": []},
    {"doctype": "AL Cost Bucket", "filters": []},
    {"doctype": "AL Cost Template", "filters": []},
    {"doctype": "AL Alert Config", "filters": []},
    {"doctype": "AL Discount Rule", "filters": []},
]

# ---- Module hooks registered at import time ----
from alumglass.modules import register_all_hooks  # noqa: E402, F401
