// AL Quantity Calc Method - Client Script
// Module: AL Formula Rules

frappe.ui.form.on("AL Quantity Calc Method", {
    refresh: function(frm) {
        // B7/Đ5: nhắc nhẹ khi cách tính còn phải chạy bằng Python Lambda — người
        // dùng cuối không đọc được ô đó, nên màn hình cấu hình sẽ trống nghĩa.
        if ((frm.doc.calc_fn || "").trim() && !(frm.doc.calc_expr || "").trim()
            && frm.dashboard && frm.dashboard.set_headline) {
            frm.dashboard.set_headline(
                __("Cách tính này còn dùng 'Python Lambda'. Hãy chuyển sang ô <b>Công thức tính</b> để hiển thị được cho người dùng."),
                "orange"
            );
        }
    },

    calc_expr: function(frm) {
        // Ô câu chữ hiển thị đang trống ⇒ chép công thức sang cho khỏi trống trơn.
        if (!(frm.doc.calc_formula || "").trim()) {
            frm.set_value("calc_formula", frm.doc.calc_expr || "");
        }
    },
});
