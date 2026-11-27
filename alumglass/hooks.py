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

# ---- Required Dependencies ----
required_apps = ["formula_builder"]

# ---- JS / CSS Includes ----
app_include_js = [
    # 2026-11-26 (Owner): MỌI hộp thoại mở từ form dòng con phải GIỮ form dòng
    # mở khi đóng. Frappe v16 (`dialog.js`, handler `hide.bs.modal`) tự gọi
    # `get_open_grid_form().hide_form()` khi `keep_grid_form_open` false ⇒ tệp
    # này bọc `frappe.ui.Dialog` một lần cho toàn app, khỏi thêm cờ ở từng
    # doctype. PHẢI ĐỨNG ĐẦU danh sách: nạp sau JS tạo hộp thoại là hộp đã
    # dựng bằng class gốc, cờ không có tác dụng.
    "/assets/alumglass/js/dialog_keep_grid_form.js?v=1.0.0",
    "/assets/alumglass/js/report/report_aggregation_core.js?v=1.0.2",
    "/assets/alumglass/js/report/report_agg_dropdown.js?v=1.0.1",
    # 2026-11-20: lọc gợi ý chéo dòng theo cross_row.fields của profile.
    # PHẢI nạp TRƯỚC formula_setup.js (patch _ContextBuilder gọi
    # window.AlumGlassFormulaRefs) — sai thứ tự thì patch chỉ warn và bỏ qua.
    "/assets/alumglass/js/al_formula_refs.js?v=1.0.0",
    # 2026-11-25: hộp thoại "Chọn công thức" / "Thử tra quy tắc" dùng chung cho
    # AL Bom Item, AL Accessory Item, AL Rule (xem docs/design/tra-cuu-quy-tac).
    # v1.1.0 (2026-11-25b): quy tắc tự khai "tra theo" — GLOBAL bỏ bước chọn
    # dữ liệu, ROW chỉ hỏi dòng nguồn (bump để trình duyệt nạp asset mới).
    # v1.1.1 (2026-11-25c): UX1 chấm chặn vòng 2 — câu mô tả bỏ mã biến, nhãn
    # dòng thay slug, biến engine tự tính liệt kê mọi dòng, cảnh báo thiếu
    # giá trị / quy tắc đã tắt-xoá.
    # v1.1.2 (2026-11-25d): UX1 chấm chặn vòng 3 — câu chồng lấn nói đúng ai
    # thắng, "Đến" của dải mở = "trở lên" trong hộp Thử tra, nhãn enum AL Rule
    # (dùng chung với danh sách).
    "/assets/alumglass/js/rule_helper.js?v=1.1.2",
    # ⚠ 2 tệp dưới là script của DOCTYPE CON (dòng trong lưới). Frappe v14
    # CHỈ eval `__js` của doctype đang mở form (script_manager.setup) — dòng
    # con dùng chung script_manager của form CHA nên `doctype_js` cho doctype
    # con KHÔNG BAO GIỜ chạy. Vì vậy nạp toàn trang: chúng chỉ ĐĂNG KÝ handler
    # `frappe.ui.form.on("AL Bom Item"/"AL Accessory Item")` (cùng cách
    # formula_setup.js đang làm cho AL Bom Item).
    # v1.1.0 (2026-11-25b): mục Rule Configuration theo quy tắc tự khai
    # "tra theo" (ROW chọn dòng nguồn / GLOBAL không hỏi nguồn).
    # v1.1.1 (2026-11-25c): câu bỏ mã biến, "Chưa tra được mã", cảnh báo
    # thiếu giá trị / quy tắc đã tắt-xoá, khối nâng cao bị khoá.
    # v1.1.2 (2026-11-25d): khối điều kiện trên dòng BOM dùng tiêu đề GỌN
    # (⛔ lặp câu quy tắc phía trên), câu nhắc đổi sang ô "Quy tắc chọn mã".
    "/assets/alumglass/js/al_bom_item.js?v=1.1.2",
    "/assets/alumglass/js/al_accessory_item.js?v=1.0.1",
    # 2026-11-27 (Owner): ô giá trị trong bảng con `AL Variable Set Item` phải
    # hiện ĐÚNG KIỂU của biến (Select / Link / Float / Int / Data) — cùng lý do
    # trên (doctype con không tự eval JS). Tệp chỉ đổi kiểu ô trên bản meta
    # RIÊNG của từng dòng ⇒ không ảnh hưởng lưới nơi khác.
    "/assets/alumglass/js/al_variable_set_item.js?v=1.0.0",
    # v28_14: formula_setup.js đổi sang registry `AL Formula Field`
    # (get_formula_fields) + cost_template.js bỏ lọc `source` cũ — bump version
    # để trình duyệt nạp asset mới thay bản cache.
    # v1.3.0: filterSiblingItems (allowlist cross_row.fields).
    "/assets/alumglass/js/formula_setup.js?v=1.3.0",
    "/assets/alumglass/js/cost_template.js?v=1.2.0",
    "/assets/alumglass/js/grid_placeholder.js?v=1.0.1",
    "/assets/alumglass/js/excel_io.js?v=1.0.1",
    # Đèn báo mã cũ: so dấu build của quotation.js với bản mong đợi — trình
    # duyệt còn cache doctype_js cũ thì báo người dùng (xem tệp + docs/ops).
    # v0.0.7 (2026-11-25c): dấu build mong đợi đổi theo quotation.js.
    # v0.0.8 (2026-11-25d): quotation.js đổi mapper raw_to_display (nhãn thay
    # slug + giữ cờ quy tắc) ⇒ nâng dấu build cùng lúc.
    "/assets/alumglass/js/build_beacon.js?v=0.0.8",
]
app_include_css = [
    "/assets/alumglass/css/formula_fix.css?v=1.0.0",
]

# web_include_css = [
#     "/assets/alumglass/css/custom_theme.css?v=1.0.1",
# ]

# ---- DocType JS overrides ----
doctype_js = {
    "Quotation": "alumglass/doctype/overrides/quotation.js",
    "Sales Order": "alumglass/doctype/overrides/sales_order.js",
    # 2026-11-25 — "Thử tra" + mô tả nghiệp vụ trên form AL Rule (thiết kế
    # docs/design/tra-cuu-quy-tac-de-hieu.md).
    # ⚠ Script của AL Bom Item / AL Accessory Item KHÔNG khai ở đây: đó là
    # doctype CON, `__js` không được eval trong lưới — chúng nạp qua
    # app_include_js (xem khối JS/CSS bên trên).
    "AL Rule": "al_formula_rules/doctype/al_rule/al_rule.js",
}

# ---- Custom Fields ----
fixtures = [
    {"doctype": "Custom Field", "filters": [
        ["dt", "in", ["Quotation", "Quotation Item", "Sales Order", "Item", "Item Price",
                       "Batch", "Serial No", "Work Order", "Purchase Order", "Stock Entry",
                       "Delivery Note", "Quality Inspection", "Warranty Claim",
                       "Journal Entry", "Payment Entry"]]
    ]},
    {"doctype": "Role", "filters": [
        ["name", "in", ["AL Sales User", "AL BOM Manager",
                        "AL Site Engineer", "AL Project Accountant",
                        "AL Technical Admin"]]
    ]},
]

# ---- Document Events ----
doc_events = {
    "Quotation": {
        # V5 (Owner): ConfigSnapshot chỉ tạo khi SUBMIT Quotation — không mỗi lần tính
        "on_submit": "alumglass.api.quotation_events.on_submit",
        # Phase 2 "Preview không ghi DB" (Owner chốt 2026-11-21, design
        # docs/design/preview-khong-ghi-db.md §9.1 câu 3): Lưu báo giá mà kết
        # quả BOM của dòng LỆCH tham số (hoặc chưa từng preview) ⇒ TỰ TÍNH LẠI
        # dòng lệch rồi mới ghi, ⛔ không chặn người dùng. Dòng khớp
        # `calc_meta.params_hash` ⇒ 0 lượt engine. Handler tự bỏ qua khi
        # docstatus != 0 (submit/cancel có luồng riêng, ⛔ tính lại giá).
        "validate": "alumglass.api.preview_guard.validate_preview_freshness",
    },
    # V6 Phase 1d: backfill `input_vars` (biến phụ theo calc_pattern) khi save
    # AL Bom Item — line luôn có đủ key biến phụ để engine B3 truyền vào
    # lookup_calc_pattern(pattern, w, h, tlr, **extra).
    "AL Bom Item": {
        "validate": "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item.backfill_input_vars",
    },
    # F3: nối vòng đời cache calc_fn vào AL Quantity Calc Method — trước đây
    # formula_handlers.clear_calc_fn_cache() không nơi nào gọi nên sửa/xoá
    # calc_fn xong hệ thống vẫn dùng bản cache cũ. Hàm nối nằm ở alumglass.api
    # (controller của doctype này do DEV khác sở hữu — ⛔ không sửa controller).
    "AL Quantity Calc Method": {
        "on_update": "alumglass.api.on_calc_method_change",
        "on_trash": "alumglass.api.on_calc_method_trash",
    },
}

# ---- FB Source Types (đăng ký custom data sources với Formula Builder) ----
# C2 (v28_11): đã bỏ handler gom cost bucket deprecated — việc đó giờ dùng
# source_type platform 'aggregate_from_items' (FVB config migrate qua patch
# v28_11). Chỉ còn 2 source type alumglass tự đăng ký.
fb_source_types = [
    "alumglass.fb_handlers.aluminum_price_composite",
    "alumglass.fb_handlers.glass_master_data",
]

# ---- Whitelisted Methods ----
# ⚠ F16 — ĐÂY KHÔNG PHẢI HOOK FRAPPE. `whitelisted_methods` không tồn tại trong
# lõi Frappe (grep toàn `frappe/` = 0 lần); hook thật để GHI ĐÈ một method đã
# whitelist là `override_whitelisted_methods` (frappe/hooks.py:374). Khai ở đây
# TRƯỚC ĐÂY không có tác dụng gì — các hàm dưới đây vốn đã tự có
# `@frappe.whitelist()` trong api/__init__.py. Giữ lại danh sách chỉ để tra cứu,
# KHÔNG phải cấu hình: thêm/bớt endpoint phải sửa decorator trong api/__init__.py.
# whitelisted_methods = {
#     "alumglass.api.calculate_bom": "alumglass.api.calculate_bom",
#     "alumglass.api.preview_cost_template": "alumglass.api.preview_cost_template",
#     "alumglass.api.get_slug_info": "alumglass.api.get_slug_info",
#     "alumglass.api.resolve_item_rule": "alumglass.api.resolve_item_rule",
#     "alumglass.api.get_bom_structure": "alumglass.api.get_bom_structure",
#     "alumglass.api.get_cost_template_context": "alumglass.api.get_cost_template_context",
#     "alumglass.api.get_formula_context": "alumglass.api.get_formula_context",
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

# Cài đặt Roles & Permissions sau khi install custom fields
def _after_install():
    """Install hook: Custom Fields → Roles & Permissions → Print Format → Workflow → FB Bindings."""
    from alumglass.setup.custom_fields import install_all_custom_fields
    from alumglass.setup.custom_fields import remove_stale_custom_fields
    from alumglass.setup.install_roles import install_roles_and_permissions
    from alumglass.setup.print_format import create_bao_gia_print_format
    from alumglass.setup.install_workflows import install_workflows
    from alumglass.setup.install_fb_bindings import install_composite_pricing_binding
    from alumglass.setup.install_fb_bindings import install_named_constant_bindings   # ← THÊM (PHẦN E)
    install_all_custom_fields()
    remove_stale_custom_fields()
    install_roles_and_permissions()
    create_bao_gia_print_format()
    # install_workflows()
    install_composite_pricing_binding()
    install_named_constant_bindings()   # ← THÊM (PHẦN E)

after_install = "alumglass.hooks._after_install"


def _after_migrate():
    """Chạy sau mỗi bench migrate — đảm bảo custom fields AL + print format +
    workflow luôn tồn tại và khớp đúng cấu hình khai báo (idempotent).

    Lý do: site cài trước khi thêm các field này thì `bench migrate` cũng không tạo
    chúng (chỉ `after_install` chạy lúc cài app). Thiếu field → các truy vấn
    `frappe.db.get_value("Quotation Item", ..., ["al_calc_status", ...])` throw
    `DataError: Field not permitted in query`. Cả 4 hàm đều idempotent.

    V6 P6 (E): `remove_stale_custom_fields()` dọn field cũ bỏ khỏi definition
    (al_project_ref + al_profile_system trên Quotation) — chỉ xóa field meta.

    V6 P11: `install_workflows()` — Workflow thật thay cho workflow_state Select
    tự chế. Chạy lại mỗi migrate để đảm bảo transitions/roles luôn khớp đúng
    WORKFLOWS khai báo trong install_workflows.py (source of truth duy nhất) —
    an toàn xóa & tạo lại vì Workflow doctype chỉ lưu CẤU HÌNH, không lưu dữ
    liệu nghiệp vụ của các document đang có workflow_state hiện tại.

    V6 P12: `install_composite_pricing_binding()` — auto-seed Formula Variable
    Binding cho composite pricing (nguyên tắc "tận dụng tối đa formula_builder"):
    trước đây nhánh FB-max (`_fetch_composite_prices_via_fb`) không bao giờ
    chạy vì không có binding nào — hệ thống luôn rơi về Python fallback dù
    code FB-max đã sẵn sàng. Seed NGAY ở đây (idempotent), không chờ thao
    tác tay D3 nữa.
    """
    from alumglass.setup.custom_fields import install_all_custom_fields
    from alumglass.setup.custom_fields import remove_stale_custom_fields
    from alumglass.setup.print_format import create_bao_gia_print_format
    from alumglass.setup.install_workflows import install_workflows
    from alumglass.setup.install_fb_bindings import install_composite_pricing_binding
    from alumglass.setup.install_fb_bindings import install_named_constant_bindings   # ← THÊM (PHẦN E)
    install_all_custom_fields()
    remove_stale_custom_fields()
    create_bao_gia_print_format()
    # ★ ĐÃ BẬT (đợt nâng cấp toàn diện) — TRƯỚC KHI deploy lên site thật, xác
    # nhận role "AL BOM Manager"/"AL Technical Admin"/"AL Site Engineer" đã
    # gán đúng người, nếu không sẽ không ai bấm được nút chuyển trạng thái.
    # install_workflows()
    install_composite_pricing_binding()
    install_named_constant_bindings()   # ← THÊM (PHẦN E)

# Chạy sau mỗi `bench migrate` — Frappe gọi lần lượt TẤT CẢ handler trong list.
#   · `_after_migrate` (đã có từ trước): custom fields + print format + FB bindings.
#   · `cache_bust.after_migrate` (2026-11-23): xoá cache form meta (`doctype_form_meta`
#     của Quotation / Sales Order) + `assets_json`. Frappe nhúng nội dung
#     `doctype_js` vào form meta rồi cache ở Redis khi site TẮT developer mode
#     (`frappe/desk/form/meta.py:36-49`) ⇒ kéo mã mới + `bench restart` KHÔNG đủ,
#     phải xoá cache này. Xem docs/ops/cap-nhat-ma-va-cache.md.
after_migrate = [
    "alumglass.hooks._after_migrate",
    "alumglass.setup.cache_bust.after_migrate",
]

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