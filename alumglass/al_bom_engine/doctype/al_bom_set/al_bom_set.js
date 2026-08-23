// AL Bom Set - Client Script
// Module: AL Bom Engine

frappe.ui.form.on("AL Bom Set", {
    refresh: function(frm) {
        // "Mã sản phẩm" (item_code) — chỉ chọn Item thuộc Item Group SAN_PHAM
        // (sản phẩm hoàn chỉnh). Filter qua set_query (JS) — DocField v14 không có
        // cột get_query trong doctype JSON.
        frm.set_query("item_code", function() {
            return { filters: { item_group: "SAN_PHAM" } };
        });
    },
});
