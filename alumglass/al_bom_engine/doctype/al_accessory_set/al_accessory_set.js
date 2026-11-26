// AL Accessory Set - Client Script
// Module: AL Bom Engine

frappe.ui.form.on("AL Accessory Set", {
    refresh: function(frm) {
        // "Mã sản phẩm" (item_code) — Item thuộc Item Group SAN_PHAM + các
        // group con (PA B, Owner chốt). Query method server-side trong
        // alumglass.api.product_item_query (DocField v14 không có cột get_query
        // trong doctype JSON nên dùng JS set_query + query method).
        frm.set_query("item_code", function() {
            return { query: "alumglass.api.product_item_query" };
        });

        // "Default Color" (dòng Items — AL Accessory Item) — chỉ cho chọn
        // AL Color Standard đã tích "Mau dai dien" (is_representative).
        frm.set_query("default_color", "items", function() {
            return { filters: { is_representative: 1 } };
        });
    },

    cost_bucket: function(frm) {
        $.each(frm.doc.items || [], function(i, item) {
            item.cost_bucket = frm.doc.cost_bucket;
        });
        frm.refresh_field("items");
    }
});