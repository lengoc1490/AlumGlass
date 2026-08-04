// AlumGlass — Formula Builder Autocomplete Integration
// Sử dụng formula_builder.formula.patchField (form) + initGridField (grid)
//
// ═══════════════════════════════════════════════════════════════════════════
// ★ CƠ CHẾ INJECT CONTEXT VARIABLES CHO AUTOCOMPLETE
// ═══════════════════════════════════════════════════════════════════════════
//
// Vấn đề: formula_builder_field.js:_buildContext() delegate sang
// _ContextBuilder.build() với liveCtx=null → _afbFieldConfig.global_vars
// KHÔNG được đọc. Tất cả global vars từ config bị bỏ qua.
//
// Giải pháp: Monkey-patch _ContextBuilder.build() để inject biến vào
// liveCtx.variables trước khi gốc chạy. Biến được thêm với source="local"
// để KHÔNG bị thêm prefix "$".
//
// ═══════════════════════════════════════════════════════════════════════════

// ── 1. Định nghĩa bộ biến toàn cục ────────────────────────────────────
const ALUMGLASS_FORMULA_VARS = [
    // ── Cost Bucket codes (dùng trong calc_formula của Cost Template) ──
    { name: "VL_NHOM",       label: "VL_NHOM — VL Nhôm",              value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "VL_KINH",       label: "VL_KINH — VL Kính",              value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "VL_VTP",        label: "VL_VTP — VL Vật tư phụ",         value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "VL_PK",         label: "VL_PK — VL Phụ kiện",            value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "TONG_VL",       label: "TONG_VL — Tổng vật liệu",        value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "NC_SX",         label: "NC_SX — Nhân công sản xuất",     value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "NC_LD",         label: "NC_LD — Nhân công lắp đặt",      value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "TONG_NC",       label: "TONG_NC — Tổng nhân công",       value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "OH_VC",         label: "OH_VC — Overhead vận chuyển",    value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "OH_QLY",        label: "OH_QLY — Overhead quản lý",      value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "TONG_OH",       label: "TONG_OH — Tổng overhead",        value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "GIA_THANH",     label: "GIA_THANH — Giá thành",          value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "PROFIT",        label: "PROFIT — Lợi nhuận",             value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "GIA_BAN",       label: "GIA_BAN — Giá bán chưa VAT",    value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "DON_GIA_M2",    label: "DON_GIA_M2 — Đơn giá /m²",      value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "VAT",           label: "VAT — Thuế VAT",                 value: 0, type: "Float", desc: "Cost Bucket" },
    { name: "GIA_VAT",       label: "GIA_VAT — Giá sau VAT",          value: 0, type: "Float", desc: "Cost Bucket" },
    // ── System Variables (từ AL Variable Library) ───────────────────
    { name: "OFFSET_FRAME",     label: "OFFSET_FRAME — Offset khung (mm)",        value: 48,  type: "Float", desc: "System Variable" },
    { name: "OFFSET_GLASS",     label: "OFFSET_GLASS — Offset kính (mm)",         value: 90,  type: "Float", desc: "System Variable" },
    { name: "OFFSET_FIXED",     label: "OFFSET_FIXED — Offset kính cố định (mm)", value: 50,  type: "Float", desc: "System Variable" },
    { name: "OFFSET_CROSSBAR",  label: "OFFSET_CROSSBAR — Offset đố ngang (mm)",  value: 48,  type: "Float", desc: "System Variable" },
    { name: "NC_SX_PCT",        label: "NC_SX_PCT — % Nhân công sản xuất",       value: 0.08, type: "Float", desc: "System Variable" },
    { name: "NC_LD_PCT",        label: "NC_LD_PCT — % Nhân công lắp đặt",        value: 0.12, type: "Float", desc: "System Variable" },
    { name: "OH_VC_PCT",        label: "OH_VC_PCT — % Overhead vận chuyển",      value: 0.03, type: "Float", desc: "System Variable" },
    { name: "OH_QLY_PCT",       label: "OH_QLY_PCT — % Overhead quản lý",        value: 0.03, type: "Float", desc: "System Variable" },
    { name: "VAT_RATE",         label: "VAT_RATE — Thuế suất VAT (0.1=10%)",     value: 0.10, type: "Float", desc: "System Variable" },
    { name: "PROFIT_MARGIN",    label: "PROFIT_MARGIN — % Lợi nhuận",            value: 0.16, type: "Float", desc: "System Variable" },
    // ── Common BOM Variables ────────────────────────────────────────
    { name: "W_mm",              label: "W_mm — Chiều rộng (mm)",         value: 0, type: "Float", desc: "BOM Input" },
    { name: "H_mm",              label: "H_mm — Chiều cao (mm)",          value: 0, type: "Float", desc: "BOM Input" },
    { name: "n_panel",           label: "n_panel — Số cánh",              value: 0, type: "Int",   desc: "BOM Input" },
    { name: "TransomHeight_mm",  label: "TransomHeight_mm — Cao ô kính",  value: 0, type: "Float", desc: "BOM Input" },
    { name: "TONG_M2",           label: "TONG_M2 — Tổng diện tích (m²)",  value: 0, type: "Float", desc: "BOM Calculated" },
    // ── Row Literals (engine inject per-row) ─────────────────────────
    { name: "weight_per_unit",   label: "weight_per_unit — TL riêng (kg/m)", value: 0, type: "Float", desc: "Row Literal" },
    { name: "unit_price",        label: "unit_price — Đơn giá",             value: 0, type: "Float", desc: "Row Literal" },
    { name: "unit_qty",          label: "unit_qty — Số lượng đơn vị",      value: 0, type: "Float", desc: "Row Literal" },
    { name: "total_qty",         label: "total_qty — Tổng số lượng",       value: 0, type: "Float", desc: "Row Literal" },
    { name: "line_total",        label: "line_total — Thành tiền dòng",    value: 0, type: "Float", desc: "Row Literal" },
    { name: "scrap_pct",         label: "scrap_pct — % Hao hụt",           value: 0, type: "Float", desc: "Row Literal" },
    { name: "glass_thick",       label: "glass_thick — Độ dày kính (mm)",  value: 0, type: "Float", desc: "Row Literal" },
    { name: "glass_type",        label: "glass_type — Loại kính",          value: "", type: "Data", desc: "Row Literal" },
    { name: "calc_pattern",      label: "calc_pattern — Pattern tính",     value: "", type: "Data", desc: "Row Literal" },
];

// ── 2. Monkey-patch _ContextBuilder.build ────────────────────────────
// Inject ALUMGLASS_FORMULA_VARS vào liveCtx.variables với source="local"
// (source="local" → KHÔNG bị thêm prefix "$" → gõ VL_ là khớp)
// Chạy sau khi formula_builder.js đã load (dùng polling check).
// ─────────────────────────────────────────────────────────────────────
(function _patchContextBuilder() {
    function _doPatch() {
        var CB = formula_builder.formula && formula_builder.formula._ContextBuilder;
        if (!CB || !CB.build || CB.__alumglassPatched) return;
        var _orig = CB.build;
        CB.build = function(params) {
            params = params || {};
            params.liveCtx = params.liveCtx || {};
            params.liveCtx.variables = params.liveCtx.variables || [];
            // Inject AlumGlass vars với source="local" để tránh prefix "$"
            for (var i = 0; i < ALUMGLASS_FORMULA_VARS.length; i++) {
                var v = ALUMGLASS_FORMULA_VARS[i];
                params.liveCtx.variables.push({
                    name: v.name,
                    label: v.label,
                    value: v.value,
                    type: v.type,
                    source: "local",        // ← KEY: "local" → NO "$" PREFIX
                    source_type: "alumglass",
                    doctype: v.desc || "AlumGlass",
                });
            }
            return _orig.call(this, params);
        };
        CB.__alumglassPatched = true;
        console.log("[AlumGlass] ContextBuilder patched — injected " +
            ALUMGLASS_FORMULA_VARS.length + " formula variables");
    }
    // Thử ngay, nếu chưa sẵn sàng thì poll mỗi 100ms
    if (formula_builder.formula && formula_builder.formula._ContextBuilder) {
        _doPatch();
    } else {
        var _tries = 0, _maxTries = 50;
        var _poll = setInterval(function() {
            _tries++;
            if (formula_builder.formula && formula_builder.formula._ContextBuilder) {
                clearInterval(_poll);
                _doPatch();
            } else if (_tries >= _maxTries) {
                clearInterval(_poll);
                console.warn("[AlumGlass] ContextBuilder not found after " +
                    (_maxTries * 100) + "ms — autocomplete may be limited");
            }
        }, 100);
    }
})();

// ═══════════════════════════════════════════════════════════════════════════
// FORMULA FIELD SETUP CHO TỪNG DOCTYPE
// ═══════════════════════════════════════════════════════════════════════════

// ── 1. AL BOM SET — grid Bom Items + Accessory Items ────────────────────
frappe.ui.form.on("AL Bom Set", {
    refresh(frm) {
        // Grid 1: Bom Items — các cột công thức
        var item_grid_fields = ["width", "height", "qty", "show_condition",
                                "item_condition_formula", "rule_input_expr"];
        item_grid_fields.forEach(function(fieldname) {
            formula_builder.formula.initGridField(frm, "items", fieldname, {
                language    : "formula-builder",
                height      : "70px",
                show_toolbar: false,
                show_preview: false,
                id_field    : "slug",
            });
        });
    },
});

// ── 2. AL COST TEMPLATE — grid calc_formula ───────────────────────────
frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        formula_builder.formula.initGridField(frm, "items", "calc_formula", {
            language    : "formula-builder",
            height      : "80px",
            show_toolbar: false,
            show_preview: false,
            float_popup : true,
            float_width : "600px",
            float_height: "150px",
        });
    },
});

// ── 3. AL ALERT CONFIG — field trigger_condition ──────────────────────
frappe.ui.form.on("AL Alert Config", {
    refresh(frm) {
        if (frm.fields_dict["trigger_condition"]) {
            formula_builder.formula.patchField(frm, "trigger_condition", {
                language    : "formula-builder",
                height      : "100px",
                show_toolbar: false,
                show_preview: false,
            });
        }
    },
});

// ── 4. AL QUANTITY CALC METHOD — field calc_fn ────────────────────────
frappe.ui.form.on("AL Quantity Calc Method", {
    refresh(frm) {
        if (frm.fields_dict["calc_fn"]) {
            formula_builder.formula.patchField(frm, "calc_fn", {
                language    : "formula-builder",
                height      : "80px",
                show_toolbar: false,
                show_preview: false,
            });
        }
    },
});

// ── 5. FORMULA GLOBAL VARIABLE — field formula_expr ────────────────────
frappe.ui.form.on("Formula Global Variable", {
    refresh(frm) {
        if (frm.fields_dict["formula_expr"]) {
            formula_builder.formula.patchField(frm, "formula_expr", {
                language    : "formula-builder",
                height      : "80px",
                show_toolbar: false,
                show_preview: false,
            });
        }
    },
});

// ── 6. QUOTATION — Nút Tham số BOM ─────────────────────────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("📐 Tham số BOM"), function () {
                var selected = frm.fields_dict["items"]?.grid?.get_selected_children();
                if (selected && selected.length > 0) {
                    new alumglass.quotation.ItemParamDialog(frm, selected[0]).show();
                } else {
                    frappe.msgprint(__("Vui lòng chọn 1 dòng sản phẩm trong bảng"));
                }
            }, __("AlumGlass"));
        }
    },
});

// ── 7. QUOTATION ITEM — Nút Tính giá BOM ───────────────────────────────
frappe.ui.form.on("Quotation Item", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.al_bom) {
            frm.add_custom_button(__("💰 Tính giá BOM"), function () {
                new alumglass.BOMDialog(frm.doc.name).show();
            }, __("AlumGlass"));
        }
    },
});
