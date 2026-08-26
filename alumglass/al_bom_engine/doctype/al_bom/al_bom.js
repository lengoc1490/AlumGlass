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

    // V6 Phase 4: nút "Tạo BOM Version mới" — tạo AL BOM Version Draft từ BOM hiện tại.
    create_new_version_btn: function(frm) {
        if (!frm.doc.bom_code) {
            frappe.msgprint(__("Chưa có BOM Code — hãy lưu BOM trước."));
            return;
        }
        frappe.call({
            method: "alumglass.al_bom_engine.doctype.al_bom.al_bom.create_bom_version",
            args: { bom_code: frm.doc.name },
            freeze: true,
            freeze_message: __("Đang tạo BOM Version mới..."),
            callback: function(r) {
                if (r.message && r.message.name) {
                    frappe.msgprint(__("Đã tạo BOM Version mới: {0} (Draft)",
                        [r.message.name]));
                    frm.reload_doc();
                }
            },
        });
    },
});
