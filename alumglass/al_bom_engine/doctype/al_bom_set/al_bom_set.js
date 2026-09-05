// AL Bom Set - Client Script
// Module: AL Bom Engine

frappe.ui.form.on("AL Bom Set", {
    refresh: function(frm) {
        // "Mã sản phẩm" (item_code) — Item thuộc Item Group SAN_PHAM + các
        // group con (PA B, Owner chốt). Query method server-side trong
        // alumglass.api.product_item_query (DocField v14 không có cột get_query
        // trong doctype JSON nên dùng JS set_query + query method).
        frm.set_query("item_code", function() {
            return { query: "alumglass.api.product_item_query" };
        });

        // "Default Color" (dòng Items — AL Bom Item) — chỉ cho chọn AL Color
        // Standard đã tích "Mau dai dien" (is_representative). Để trống field
        // này = dòng luôn dùng 1 màu cố định, không tham gia nhóm "Màu sắc
        // theo vị trí" trong dialog báo giá.
        frm.set_query("default_color", "items", function() {
            return { filters: { is_representative: 1 } };
        });
    },
});