// AL Cost Template - Client Script
// Module: AL Bom Engine
//
// ★ Công thức calc_formula dùng Cost Bucket codes làm biến.
// Context variables được load tự động từ API get_formula_context("AL Cost Template")
// → Cost Buckets, System Vars, Formula Global Vars, Common Vars
// → KHÔNG hardcode biến nào — mọi thứ từ DB.
//
// ★ Validate 2 lớp:
//   1. Client (validate_formula trong cost_template.js) — chặn biến/hàm lạ NGAY
//      trên UI (onchange calc_formula) + chặn save (validate event).
//   2. Server (ALCostTemplate.validate — FormulaValidator AST) — cảnh báo khi save.

frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        // Pre-load context (dùng cache) + nạp global_vars vào
        // window._afbFieldConfig cho autocomplete Monaco editor — trước đây
        // fetchContext() trần bỏ sót bước nạp _afbFieldConfig. Giờ đây là
        // NƠI DUY NHẤT xử lý refresh + Preview cho AL Cost Template (đã gộp
        // với khối trùng ở public/js/cost_template.js — xem README).
        if (alumglass.CostTemplate) {
            alumglass.CostTemplate.injectContext(frm);
        }

        // Thêm nút Preview (nếu muốn)
        if (!frm.is_new()) {
            frm.add_custom_button(__("Preview"), function () {
                alumglass.CostTemplate?.preview(frm);
            }, __("Actions"));
        }
    },

    // Chặn save NGAY khi có biến/hàm lạ (không chờ server)
    async validate(frm) {
        if (!alumglass.CostTemplate) return;

        // Đảm bảo context đã load (cache → nhanh). Nếu load lỗi → knownNames null
        // → validate_formula bỏ qua check biến (fallback an toàn).
        await alumglass.CostTemplate.fetchContext();
        let knownNames = alumglass.CostTemplate.getKnownNames();

        let errors = [];
        let definedVars = new Set();
        let rows = frm.doc.items || [];
        for (let i = 0; i < rows.length; i++) {
            let row = rows[i];
            if (!row.calc_formula) continue;
            let result = alumglass.CostTemplate.validate_formula(row.calc_formula, {
                known_names: knownNames,
                line_codes: Array.from(definedVars),
            });
            if (!result.valid) {
                errors.push(__("Dòng '") + (row.line_code || (i + 1)) + __("': ") + result.message);
            }
            if (row.line_code) definedVars.add(row.line_code);
        }

        if (errors.length) {
            frappe.validated = false;
            frappe.msgprint(errors.join("\n"), __("AL Cost Template — Công thức không hợp lệ"));
        }
    },
});

// ── Child table: feedback NGAY trên UI khi sửa calc_formula ─────────────
frappe.ui.form.on("AL Cost Template Item", {
    calc_formula: function (frm, cdt, cdn) {
        if (!alumglass.CostTemplate) return;
        alumglass.CostTemplate.validateRowSoon(frm, cdt, cdn);
    },
});
