// AL Cost Template - Client Script
// Module: AL Bom Engine
//
// ★ Công thức calc_formula dùng Cost Bucket codes làm biến.
// Context variables được load tự động từ API get_formula_context("AL Cost Template")
// → Cost Buckets, System Vars, Formula Global Vars, Common Vars
// → KHÔNG hardcode biến nào — mọi thứ từ DB.

frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        // Context được formula_setup.js pre-fetch + inject tự động
        // Không cần gọi gì thêm ở đây

        // Thêm nút Preview (nếu muốn)
        if (!frm.is_new()) {
            frm.add_custom_button(__("Preview"), function () {
                alumglass.CostTemplate?.preview(frm);
            }, __("Actions"));
        }
    },

    validate(frm) {
        // Validate từng dòng calc_formula
        if (frm.doc.items) {
            frm.doc.items.forEach(function(row) {
                if (row.calc_formula && !alumglass.CostTemplate?.validate_formula(row.calc_formula).valid) {
                    frappe.msgprint(__("Công thức không hợp lệ ở dòng: ") + row.line_code);
                }
            });
        }
    },
});
