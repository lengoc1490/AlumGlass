// AlumGlass — Formula Builder Autocomplete Integration
// Sử dụng formula_builder.formula.patchField (form) + initGridField (grid)
//
// ★ CONTEXT VARIABLES — set SYNCHRONOUSLY trước khi form events chạy
// Đây là bộ biến cốt lõi cho autocomplete của TẤT CẢ doctype.
// Bổ sung thêm qua async API call trong từng form refresh nếu cần.
// ─────────────────────────────────────────────────────────────────────
(function _initGlobalContext() {
    window._afbFieldConfig = window._afbFieldConfig || {};
    window._afbFieldConfig.global_vars = [
        // ── Cost Bucket codes ──────────────────────────────────
        { name: "VL_NHOM",       label: "VL Nhôm",          value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "VL_KINH",       label: "VL Kính",          value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "VL_VTP",        label: "VL VTP",           value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "VL_PK",         label: "VL Phụ kiện",      value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "TONG_VL",       label: "Tổng vật liệu",    value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "NC_SX",         label: "NC Sản xuất",      value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "NC_LD",         label: "NC Lắp đặt",       value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "TONG_NC",       label: "Tổng nhân công",   value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "OH_VC",         label: "OH Vận chuyển",    value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "OH_QLY",        label: "OH Quản lý",       value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "TONG_OH",       label: "Tổng overhead",    value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "GIA_THANH",     label: "Giá thành",        value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "PROFIT",        label: "Lợi nhuận",        value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "GIA_BAN",       label: "Giá bán",          value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "DON_GIA_M2",    label: "Đơn giá /m²",      value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "VAT",           label: "Thuế VAT",         value: 0, source: "global", doctype: "Cost Bucket" },
        { name: "GIA_VAT",       label: "Giá sau VAT",      value: 0, source: "global", doctype: "Cost Bucket" },
        // ── System Variables (từ Variable Library) ──────────
        { name: "OFFSET_FRAME",      label: "Offset khung",     value: 48,  source: "global", doctype: "System" },
        { name: "OFFSET_GLASS",      label: "Offset kính",      value: 90,  source: "global", doctype: "System" },
        { name: "OFFSET_FIXED",      label: "Offset cố định",   value: 50,  source: "global", doctype: "System" },
        { name: "OFFSET_CROSSBAR",   label: "Offset đố ngang",  value: 48,  source: "global", doctype: "System" },
        { name: "NC_SX_PCT",         label: "% NC Sản xuất",    value: 0.08, source: "global", doctype: "System" },
        { name: "NC_LD_PCT",         label: "% NC Lắp đặt",     value: 0.12, source: "global", doctype: "System" },
        { name: "OH_VC_PCT",         label: "% OH Vận chuyển",  value: 0.03, source: "global", doctype: "System" },
        { name: "OH_QLY_PCT",        label: "% OH Quản lý",     value: 0.03, source: "global", doctype: "System" },
        { name: "VAT_RATE",          label: "Thuế suất VAT",    value: 0.10, source: "global", doctype: "System" },
        { name: "PROFIT_MARGIN",     label: "% Lợi nhuận",      value: 0.16, source: "global", doctype: "System" },
        // ── Common Variables (BOM) ───────────────────────────
        { name: "W_mm",              label: "Width (mm)",       value: 0, source: "global", doctype: "Common" },
        { name: "H_mm",              label: "Height (mm)",      value: 0, source: "global", doctype: "Common" },
        { name: "n_panel",           label: "Số cánh",          value: 0, source: "global", doctype: "Common" },
        { name: "TransomHeight_mm",  label: "Cao ô kính (mm)",  value: 0, source: "global", doctype: "Common" },
        { name: "TONG_M2",           label: "Tổng m²",          value: 0, source: "global", doctype: "Common" },
        // ── Row Literals (injected per-row bởi engine) ──────
        { name: "weight_per_unit",   label: "TL riêng (kg/m)",  value: 0, source: "global", doctype: "Row" },
        { name: "unit_price",        label: "Đơn giá",          value: 0, source: "global", doctype: "Row" },
        { name: "calc_pattern",      label: "Pattern tính",     value: "", source: "global", doctype: "Row" },
        { name: "scrap_pct",         label: "% Hao hụt",        value: 0, source: "global", doctype: "Row" },
        { name: "glass_thick",       label: "Độ dày kính (mm)", value: 0, source: "global", doctype: "Row" },
        { name: "glass_type",        label: "Loại kính",        value: "", source: "global", doctype: "Row" },
    ];
    console.log("[AlumGlass] Global context injected:",
        window._afbFieldConfig.global_vars.length, "variables");
})();
//
// ═══════════════════════════════════════════════════════════════════════════
// ★ HƯỚNG DẪN CẤU HÌNH FORMULA BUILDER CHO TỪNG DOCTYPE
// ═══════════════════════════════════════════════════════════════════════════
//
// Có 3 cấp độ inject context variables cho autocomplete:
//
// CẤP 1: window._afbFieldConfig.global_vars (toàn cục — ảnh hưởng TẤT CẢ field)
//   → Set 1 lần trong file JS load sớm nhất (vd: cost_template.js, hoặc
//     custom boot script). Tất cả patchField/patchChildField/initGridField
//     inline editor đều đọc được.
//   → KHÔNG ảnh hưởng đến dialog toàn màn hình (dblclick)!
//
// CẤP 2: opts.extra_completions trong patchField (per-field)
//   → Chỉ dùng được cho patchField (form mẹ), KHÔNG cho initGridField.
//
// CẤP 3: Formula Variable Binding records (database — per-doctype)
//   → Ảnh hưởng đến dialog toàn màn hình (dblclick) qua API get_live_context.
//   → DocType: Formula Variable Binding (của formula_builder)
//   → Set applies_to_doctype = "AL Cost Template", applies_to_field = "calc_formula"
//
// ═══════════════════════════════════════════════════════════════════════════
// ★ LƯU Ý VỀ show_preview VÀ show_toolbar
// ═══════════════════════════════════════════════════════════════════════════
//
// show_toolbar: false → Ẩn toolbar inline (chỉ có nút Copy) — ĐÃ HOẠT ĐỘNG
// show_preview: false → Ẩn preview bar (nút "Chạy" + "⬡ Editor") — HOẠT ĐỘNG TRÊN:
//   ✅ patchField (form mẹ)
//   ✅ initGridField inline cell (single click) — forced false
//   ❌ initGridField EXPANDED ROW — BUG trong formula_builder (line 1642 hardcode true)
//   ❌ initGridField DBLCLICK DIALOG — mở openDialog() với show_toolbar mặc định true
//
// Workaround cho expanded row: CSS ẩn nút (xem file CSS kèm theo)
// Workaround cho dialog: Tạo Formula Variable Binding records để context hiện đúng

// ─────────────────────────────────────────────────────────────────────────────
// 1. AL BOM SET (parent) — 2 child tables: items + accessory_items
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Bom Set", {
    refresh(frm) {
        // Context đã được inject SYNCHRONOUSLY ở đầu file — không cần async call
        // Bổ sung Variable Set riêng của BOM nếu cần: alumglass.BomSetContext?.inject(frm);

        // Grid 1: Bom Items (Nhôm, Kính, VTP) — các cột formula
        // Lưu ý: show_toolbar ẩn toolbar (Copy btn), show_preview ẩn nút "Chạy" + "⬡ Editor"
        const item_grid_fields = ["width", "height", "qty", "show_condition",
                                  "item_condition_formula", "rule_input_expr"];
        item_grid_fields.forEach(fieldname => {
            formula_builder.formula.initGridField(frm, "items", fieldname, {
                language    : "formula-builder",
                height      : "70px",
                show_toolbar: false,
                show_preview: false,   // ← Ẩn nút "Chạy" + "⬡ Editor" trong cell
            });
        });

        // Grid 2: Accessory Items (Phụ kiện) — không có cột formula, chỉ chọn item + qty
        // (không cần initGridField vì accessory item dùng Link + Float, không có formula)
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. AL COST TEMPLATE (parent) — chứa child table AL Cost Template Item
// Context autocomplete: Cost Bucket codes (VL_NHOM, TONG_VL...), system vars
// (NC_SX_PCT, VAT_RATE...), global vars được inject qua cost_template.js
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        // Context đã được inject SYNCHRONOUSLY ở đầu file — KHÔNG cần async call
        // Nếu cần bổ sung variable đặc thù: alumglass.CostTemplate?.injectContext(frm);

        // Grid field calc_formula — popup nổi to hơn vì công thức dài
        formula_builder.formula.initGridField(frm, "items", "calc_formula", {
            language    : "formula-builder",
            height      : "80px",
            show_toolbar: false,
            show_preview: false,   // ← Ẩn nút "Chạy" + "⬡ Editor"
            float_popup : true,
            float_width : "600px",
            float_height: "150px",
        });
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. AL ALERT CONFIG — field trigger_condition trên form chính
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Alert Config", {
    refresh(frm) {
        if (frm.fields_dict["trigger_condition"]) {
            formula_builder.formula.patchField(frm, "trigger_condition", {
                language    : "formula-builder",
                height      : "100px",
                show_toolbar: false,
                show_preview: false,   // ← Ẩn nút "Chạy" + "⬡ Editor"
            });
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. AL QUANTITY CALC METHOD — field calc_fn
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Quantity Calc Method", {
    refresh(frm) {
        if (frm.fields_dict["calc_fn"]) {
            formula_builder.formula.patchField(frm, "calc_fn", {
                language    : "formula-builder",
                height      : "80px",
                show_toolbar: false,
                show_preview: false,   // ← Ẩn nút "Chạy" + "⬡ Editor"
            });
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. FORMULA GLOBAL VARIABLE — field formula_expr
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("Formula Global Variable", {
    refresh(frm) {
        if (frm.fields_dict["formula_expr"]) {
            formula_builder.formula.patchField(frm, "formula_expr", {
                language    : "formula-builder",
                height      : "80px",
                show_toolbar: false,
                show_preview: false,   // ← Ẩn nút "Chạy" + "⬡ Editor"
            });
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. AL PROFIL SYSTEM — hiển thị offset visualization (nếu có custom_html field)
// ─────────────────────────────────────────────────────────────────────────────
// (placeholder cho các doctype khác nếu cần thêm field formula)

// ─────────────────────────────────────────────────────────────────────────────
// 7. QUOTATION — nút Formula Builder cho custom_formula (nếu có)
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        // Nút mở dialog tham số BOM
        if (!frm.is_new()) {
            frm.add_custom_button(__("📐 Tham số BOM"), function () {
                const selected = frm.fields_dict["items"]?.grid?.get_selected_children();
                if (selected && selected.length > 0) {
                    new alumglass.quotation.ItemParamDialog(frm, selected[0]).show();
                } else {
                    frappe.msgprint(__("Vui lòng chọn 1 dòng sản phẩm trong bảng"));
                }
            }, __("AlumGlass"));
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. QUOTATION ITEM — nút Tính giá BOM
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("Quotation Item", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.al_bom) {
            frm.add_custom_button(__("💰 Tính giá BOM"), function () {
                new alumglass.BOMDialog(frm.doc.name).show();
            }, __("AlumGlass"));
        }
    },
});
