// AL BOM - Client Script
// Module: AL Bom Engine

frappe.ui.form.on("AL BOM", {
    refresh: function(frm) {
        // "Mã sản phẩm" (representative_item) — chỉ chọn Item thuộc Item Group SAN_PHAM
        // (sản phẩm hoàn chỉnh). Filter qua set_query (JS) — DocField v14 không có
        // cột get_query trong doctype JSON.
        frm.set_query("representative_item", function() {
            return { filters: { item_group: "SAN_PHAM" } };
        });
    },
});
