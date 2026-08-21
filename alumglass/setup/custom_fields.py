"""Cài đặt Custom Fields cho ERPNext Core doctypes.

Các field được tự động tạo khi chạy `after_install` hook.
"""

CUSTOM_FIELDS = {
    # ── Quotation (chỉ giữ thông tin dự án/context, KO có tham số sản phẩm) ──
    "Quotation": [
        {"fieldname": "al_project_ref", "label": "AL Project Ref", "fieldtype": "Data",
         "insert_after": "quotation_to", "description": "Mã dự án / công trình"},
        {"fieldname": "al_profile_system", "label": "AL Profile System", "fieldtype": "Link",
         "options": "AL Profile System", "insert_after": "al_project_ref",
         "description": "Hệ profile mặc định cho toàn bộ báo giá"},
        {"fieldname": "al_loss_reason", "label": "Loss Reason", "fieldtype": "Select",
         "options": "GIA_CAO\nCHAM_TIEN_DO\nDOI_THU\nKHAC", "insert_after": "al_profile_system",
         "description": "Lý do mất đơn (nếu có)"},
    ],
    # ── Quotation Item (BOM ref + JSON input + JSON output linh hoạt) ──
    "Quotation Item": [
        {"fieldname": "al_bom", "label": "AL BOM", "fieldtype": "Link",
         "options": "AL BOM", "insert_after": "item_code"},
        {"fieldname": "al_bom_version", "label": "AL BOM Version", "fieldtype": "Link",
         "options": "AL BOM Version", "insert_after": "al_bom"},
        {"fieldname": "al_bom_vars", "label": "BOM Input (JSON)", "fieldtype": "JSON",
         "insert_after": "al_bom_version",
         "description": "Tham số đầu vào. Sinh tự động từ AL Variable Set, KHÔNG nhập tay."},
        {"fieldname": "al_config_snapshot", "label": "Snapshot", "fieldtype": "Link",
         "options": "ConfigSnapshot", "insert_after": "al_bom_vars", "read_only": 1},
        {"fieldname": "al_gia_ban", "label": "Giá bán (chưa VAT)", "fieldtype": "Currency",
         "insert_after": "al_config_snapshot", "read_only": 1},
        {"fieldname": "al_gia_vat", "label": "Giá bán (có VAT)", "fieldtype": "Currency",
         "insert_after": "al_gia_ban", "read_only": 1},
        {"fieldname": "al_bom_result", "label": "Kết quả BOM (JSON)", "fieldtype": "JSON",
         "insert_after": "al_gia_vat", "read_only": 1,
         "description": "Toàn bộ kết quả: buckets, cost_template, lines. Linh hoạt với mọi số lượng cost bucket."},
        # P2 — Async BOM Calculation: trạng thái/job/error cho BOM > ngưỡng
        {"fieldname": "al_calc_status", "label": "AL Calc Status", "fieldtype": "Select",
         "options": "\nQueued\nRunning\nSuccess\nFailed", "insert_after": "al_bom_result",
         "read_only": 1, "no_copy": 1, "print_hide": 1,
         "description": "Trạng thái tính BOM (P2 async): rỗng = chưa tính, Queued/Running = đang chạy nền, Success/Failed = xong."},
        {"fieldname": "al_calc_job_id", "label": "AL Calc Job ID", "fieldtype": "Data",
         "insert_after": "al_calc_status", "read_only": 1, "no_copy": 1, "hidden": 1,
         "description": "Job ID của background job (queue long) — client lọc realtime event theo job này."},
        {"fieldname": "al_calc_error", "label": "AL Calc Error", "fieldtype": "Small Text",
         "insert_after": "al_calc_job_id", "read_only": 1, "no_copy": 1, "print_hide": 1,
         "description": "Traceback ngắn khi job tính BOM thất bại."},
    ],
    # ── Sales Order ────────────────────────────────────
    "Sales Order": [
        {"fieldname": "al_project_id", "label": "Project ID", "fieldtype": "Data", "insert_after": "project"},
        {"fieldname": "al_installation_team", "label": "Installation Team", "fieldtype": "Link",
         "options": "AL Installation Team", "insert_after": "al_project_id"},
        {"fieldname": "al_expected_start_date", "label": "Expected Start", "fieldtype": "Date",
         "insert_after": "al_installation_team"},
        {"fieldname": "al_expected_end_date", "label": "Expected End", "fieldtype": "Date",
         "insert_after": "al_expected_start_date"},
    ],
    # ── Item ───────────────────────────────────────────
    "Item": [
        {"fieldname": "al_material_category", "label": "Material Category", "fieldtype": "Link",
         "options": "AL Material Category", "insert_after": "item_group"},
        {"fieldname": "al_weight_per_m", "label": "Weight per Meter (kg/m)", "fieldtype": "Float",
         "insert_after": "al_material_category"},
        {"fieldname": "al_glass_master", "label": "Glass Master", "fieldtype": "Link",
         "options": "AL Glass Master", "insert_after": "al_weight_per_m"},
        {"fieldname": "al_is_color_variable", "label": "Is Color Variable?", "fieldtype": "Check",
         "insert_after": "al_glass_master"},
    ],
    # ── Item Price ─────────────────────────────────────
    "Item Price": [
        {"fieldname": "al_is_composite_price", "label": "Is Composite Price?", "fieldtype": "Check",
         "insert_after": "price_list_rate", "read_only": 1},
    ],
    # ── Batch ──────────────────────────────────────────
    "Batch": [
        {"fieldname": "al_color", "label": "AL Color", "fieldtype": "Link",
         "options": "AL Color Standard", "insert_after": "batch_id"},
        {"fieldname": "al_source_project", "label": "Source Project", "fieldtype": "Link",
         "options": "Project", "insert_after": "al_color"},
        {"fieldname": "al_trace_stage", "label": "Trace Stage", "fieldtype": "Select",
         "options": "RAW\nCUT\nFABRICATED\nINSTALLED", "insert_after": "al_source_project"},
        {"fieldname": "al_bin_location", "label": "Bin Location", "fieldtype": "Data",
         "insert_after": "al_trace_stage"},
    ],
    # ── Serial No ──────────────────────────────────────
    "Serial No": [
        {"fieldname": "al_piece_length_mm", "label": "Piece Length (mm)", "fieldtype": "Float",
         "insert_after": "serial_no"},
        {"fieldname": "al_is_offcut", "label": "Is Offcut?", "fieldtype": "Check",
         "insert_after": "al_piece_length_mm"},
        {"fieldname": "al_parent_cut_id", "label": "Parent Cut ID", "fieldtype": "Data",
         "insert_after": "al_is_offcut"},
    ],
    # ── Work Order ─────────────────────────────────────
    "Work Order": [
        {"fieldname": "al_production_order_bridge", "label": "Production Order Bridge", "fieldtype": "Link",
         "options": "AL Production Order Bridge", "insert_after": "bom_no"},
        {"fieldname": "al_project", "label": "Project", "fieldtype": "Link",
         "options": "Project", "insert_after": "al_production_order_bridge"},
    ],
    # ── Purchase Order ─────────────────────────────────
    "Purchase Order": [
        {"fieldname": "al_project", "label": "Project", "fieldtype": "Link",
         "options": "Project", "insert_after": "project"},
        {"fieldname": "al_material_plan", "label": "Material Plan", "fieldtype": "Link",
         "options": "AL Material Plan", "insert_after": "al_project"},
    ],
    # ── Stock Entry ────────────────────────────────────
    "Stock Entry": [
        {"fieldname": "al_project", "label": "Project", "fieldtype": "Link",
         "options": "Project", "insert_after": "project"},
        {"fieldname": "al_installation_order", "label": "Installation Order", "fieldtype": "Link",
         "options": "AL Installation Order", "insert_after": "al_project"},
    ],
    # ── Delivery Note ──────────────────────────────────
    "Delivery Note": [
        {"fieldname": "al_project", "label": "Project", "fieldtype": "Link",
         "options": "Project", "insert_after": "project"},
        {"fieldname": "al_installation_order", "label": "Installation Order", "fieldtype": "Link",
         "options": "AL Installation Order", "insert_after": "al_project"},
    ],
    # ── Quality Inspection ─────────────────────────────
    "Quality Inspection": [
        {"fieldname": "al_production_order_bridge", "label": "Production Order Bridge", "fieldtype": "Link",
         "options": "AL Production Order Bridge", "insert_after": "reference_name"},
        {"fieldname": "al_inspection_stage", "label": "Inspection Stage", "fieldtype": "Select",
         "options": "INCOMING\nIN_PROCESS\nFINAL\nSITE", "insert_after": "al_production_order_bridge"},
        {"fieldname": "al_bom_slug", "label": "BOM Slug", "fieldtype": "Data",
         "insert_after": "al_inspection_stage"},
        {"fieldname": "al_surface_check", "label": "Surface Check", "fieldtype": "Select",
         "options": "PASS\nFAIL\nN/A", "insert_after": "al_bom_slug"},
        {"fieldname": "al_dimension_check", "label": "Dimension Check", "fieldtype": "Select",
         "options": "PASS\nFAIL\nN/A", "insert_after": "al_surface_check"},
        {"fieldname": "al_color_match", "label": "Color Match", "fieldtype": "Select",
         "options": "PASS\nFAIL\nN/A", "insert_after": "al_dimension_check"},
        {"fieldname": "al_glass_defect_check", "label": "Glass Defect Check", "fieldtype": "Select",
         "options": "PASS\nFAIL\nN/A", "insert_after": "al_color_match"},
    ],
    # ── Warranty Claim ─────────────────────────────────
    "Warranty Claim": [
        {"fieldname": "al_installation_order", "label": "Installation Order", "fieldtype": "Link",
         "options": "AL Installation Order", "insert_after": "complaint"},
        {"fieldname": "al_defect_category", "label": "Defect Category", "fieldtype": "Select",
         "options": "GLASS_BREAK\nSEAL_FAIL\nHARDWARE\nLEAK\nCOLOR_FADE\nSTRUCTURAL",
         "insert_after": "al_installation_order"},
        {"fieldname": "al_warranty_policy", "label": "Warranty Policy", "fieldtype": "Link",
         "options": "AL Warranty Policy", "insert_after": "al_defect_category"},
        {"fieldname": "al_covered_by_warranty", "label": "Covered by Warranty?", "fieldtype": "Check",
         "insert_after": "al_warranty_policy"},
    ],
    # ── Journal Entry ──────────────────────────────────
    "Journal Entry": [
        {"fieldname": "al_project", "label": "Project", "fieldtype": "Link",
         "options": "Project", "insert_after": "project"},
        {"fieldname": "al_cost_bucket", "label": "Cost Bucket", "fieldtype": "Link",
         "options": "AL Cost Bucket", "insert_after": "al_project"},
        {"fieldname": "al_change_order", "label": "Change Order", "fieldtype": "Link",
         "options": "AL Change Order", "insert_after": "al_cost_bucket"},
    ],
    # ── Payment Entry ──────────────────────────────────
    "Payment Entry": [
        {"fieldname": "al_payment_stage", "label": "Payment Stage", "fieldtype": "Select",
         "options": "DEPOSIT\nPROGRESS\nFINAL\nRETENTION", "insert_after": "payment_type"},
        {"fieldname": "al_handover", "label": "Handover", "fieldtype": "Link",
         "options": "AL Handover Acceptance", "insert_after": "al_payment_stage"},
    ],
}


def install_all_custom_fields():
    """Cài đặt tất cả custom fields vào ERPNext core doctypes."""
    import frappe

    for dt, fields in CUSTOM_FIELDS.items():
        for field_def in fields:
            fieldname = field_def["fieldname"]
            if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
                continue
            cf = frappe.new_doc("Custom Field")
            cf.dt = dt
            cf.update(field_def)
            cf.insert(ignore_permissions=True)
            print(f"  Created: {dt}.{fieldname}")
