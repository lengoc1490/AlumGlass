"""
AlumGlass ERP v17.0 — App Hooks
Dependencies: formula_builder (formula_utils v29.1+)
"""
app_name = "alumglass"
app_title = "AlumGlass ERP"
app_publisher = "Le Ngoc"
app_description = "ERP for aluminum & glass manufacturing — Quotation, BOM, Costing, MRP"
app_email = "lengoc1490@gmail.com"
app_license = "mit"

# ---- JS / CSS Includes ----
app_include_js = [
    "/assets/alumglass/js/report/report_aggregation_core.js?v=1.0.0",
    "/assets/alumglass/js/report/report_agg_dropdown.js?v=1.0.0",
]
# app_include_css = [
#     "/assets/alumglass/css/custom_theme.css?v=1.0.1",
# ]

# web_include_css = [
#     "/assets/alumglass/css/custom_theme.css?v=1.0.1",
# ]

# ---- DocType JS overrides ----
doctype_js = {
    "Sales Order": "alumglass/doctype/overrides/sales_order.js",
}

# ---- Custom Fields ----
# These are installed via fixtures/migration patches
# fixtures = [
#     # Core Master Data (from v16)
#     {"doctype": "AL Variable Group", "filters": []},
#     {"doctype": "AL Glass Type", "filters": []},
#     {"doctype": "AL Glass Master", "filters": []},
#     {"doctype": "AL Variable Library", "filters": []},
#     {"doctype": "AL Calculation Rule", "filters": []},
#     {"doctype": "AL Cost Bucket", "filters": []},
#     {"doctype": "AL Cost Template", "filters": []},
#     # v17 Module Data
#     {"doctype": "AL Alert Config", "filters": []},
#     {"doctype": "AL Discount Rule", "filters": []},
#     # Custom Fields for ERPNext core doctypes
#     {"doctype": "Custom Field", "filters": [
#         ["dt", "in", ["Item", "Quotation Item", "Sales Order Item", "Sales Invoice Item"]]
#     ]},
# ]

# ---- Document Events ----
# doc_events = {
#     "Quotation": {
#         "before_submit": "alumglass.modules.approval.approval_engine.check_pending_approvals",
#     },
#     "Sales Order": {
#         "before_insert": "alumglass.engine.orchestrator.copy_al_fields_to_so",
#     },
#     "Sales Invoice": {
#         "before_insert": "alumglass.engine.orchestrator.copy_al_fields_to_si",
#     },
#     "Purchase Invoice": {
#         "on_submit": "alumglass.modules.cost_variance.variance_analyzer.on_purchase_invoice_submit",
#     },
#     "AL BOM Version": {
#         "after_insert": "alumglass.modules.version.bom_version_manager.on_version_created",
#         "on_update": "alumglass.modules.version.bom_version_manager.on_version_status_changed",
#     },
#     "AL BOM": {
#         "validate": "alumglass.modules.version.bom_version_manager.on_bom_validate",
#     },
#     "AL Discount Rule": {
#         "validate": "alumglass.modules.discount.discount_stack.validate_discount_rule",
#     },
#     "AL Material Plan": {
#         "on_update": "alumglass.modules.mrp.mrp_aggregator.on_plan_status_change",
#     },
#     "AL Sales KPI": {
#         "before_insert": "alumglass.modules.analytics.kpi_calculator.before_insert_kpi",
#     },
# }

# ---- Scheduler Events ----
# scheduler_events = {
#     "daily": [
#         "alumglass.scheduled_tasks.update_sales_kpi",
#         "alumglass.scheduled_tasks.check_price_change_alerts",
#         "alumglass.scheduled_tasks.check_low_stock_alerts",
#         "alumglass.scheduled_tasks.generate_daily_digest",
#     ],
#     "weekly": [
#         "alumglass.scheduled_tasks.deprecate_old_bom_versions",
#     ],
#     "hourly": [
#         "alumglass.scheduled_tasks.process_notification_queue",
#     ],
# }


# include js, css files in header of web template
# web_include_css = "/assets/formula_builder/css/formula_builder.css"
# web_include_js = "/assets/formula_builder/js/formula_builder.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "formula_builder/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "formula_builder/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "formula_builder.utils.jinja_methods",
# 	"filters": "formula_builder.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "formula_builder.install.before_install"
# after_install = "formula_builder.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "formula_builder.uninstall.before_uninstall"
# after_uninstall = "formula_builder.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "formula_builder.utils.before_app_install"
# after_app_install = "formula_builder.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "formula_builder.utils.before_app_uninstall"
# after_app_uninstall = "formula_builder.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "formula_builder.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"formula_builder.tasks.all"
# 	],
# 	"daily": [
# 		"formula_builder.tasks.daily"
# 	],
# 	"hourly": [
# 		"formula_builder.tasks.hourly"
# 	],
# 	"weekly": [
# 		"formula_builder.tasks.weekly"
# 	],
# 	"monthly": [
# 		"formula_builder.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "formula_builder.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "formula_builder.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "formula_builder.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# after_request = ["formula_builder.utils.after_request"]

# Job Events
# ----------
# before_job = ["formula_builder.utils.before_job"]
# after_job = ["formula_builder.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"formula_builder.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }