// AL BOM - Client Script
// Module: AL Bom Engine

frappe.ui.form.on("AL BOM", {
    refresh: function(frm) {
        // "Mã sản phẩm" (representative_item) — Item thuộc Item Group SAN_PHAM
        // + các group con (PA B, Owner chốt). Query method server-side trong
        // alumglass.api.product_item_query (DocField v14 không có cột get_query
        // trong doctype JSON nên dùng JS set_query + query method).
        frm.set_query("representative_item", function() {
            return { query: "alumglass.api.product_item_query" };
        });
    },
});
