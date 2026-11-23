// AL Rule - Client Script
// Module: AL Formula Rules
//
// Hai doctype rule cũ (đã xoá 2026-11-23) chỉ có khung refresh/validate
// RỖNG — giữ đúng mức đó, ⛔ tự thêm logic ẩn/hiện cột kết quả (Frappe đã
// ẩn/hiện section theo `depends_on` khai trong JSON).

frappe.ui.form.on("AL Rule", {
    refresh: function(frm) {
        // Form refresh logic
    },

    validate: function(frm) {
        // Form validation logic
    },
});
