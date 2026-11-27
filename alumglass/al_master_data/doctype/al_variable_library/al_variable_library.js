// AL Variable Library — ô "Default Value" hiện ĐÚNG KIỂU của biến.
//
// Vì sao: giá trị mặc định là thứ người dùng sẽ thấy/chọn về sau. Khai biến
// kiểu Select mà ô mặc định là chữ tự do ⇒ gõ vào một giá trị không có trong
// danh sách, hoặc sai chính tả, và lỗi chỉ lộ lúc tính BOM. Cùng quy tắc với
// bảng con AL Variable Set Item (xem public/js/al_variable_set_item.js):
//   Select → chọn trong danh sách đã khai · Link → chọn bản ghi của doctype
//   Float/Int/Currency/Percent → nhập số · Check → đánh dấu · còn lại → chữ.

(function () {
    var VALUE_FIELD = "default_value";
    var PASSTHROUGH = {
        Float: "Float",
        Int: "Int",
        Currency: "Currency",
        Percent: "Percent",
        Check: "Check",
        Data: "Data",
    };

    function _want(doc) {
        var type = String((doc && doc.var_type) || "").trim() || "Data";
        if (type === "Select") {
            var opts = String(doc.select_options || "").trim();
            // Biến mới chưa khai lựa chọn ⇒ giữ ô chữ, nhưng PHẢI nói vì sao.
            if (!opts) {
                return {
                    type: "Data",
                    options: "",
                    hint: __("Kiểu là Chọn danh sách nhưng chưa khai 'Select Options' — ô này tạm là ô chữ tự do. Khai lựa chọn (mỗi dòng một giá trị) để hiện danh sách chọn."),
                };
            }
            return { type: "Select", options: "\n" + opts, hint: "" };
        }
        if (type === "Link") {
            var link = String(doc.link_doctype || "").trim();
            if (!link) {
                return {
                    type: "Data",
                    options: "",
                    hint: __("Kiểu là Liên kết nhưng chưa khai 'Link Doctype' — ô này tạm là ô chữ tự do. Khai doctype đích để hiện ô chọn bản ghi."),
                };
            }
            return { type: "Link", options: link, hint: "" };
        }
        return { type: PASSTHROUGH[type] || "Data", options: "", hint: "" };
    }

    function _apply(frm) {
        var field = frm.fields_dict && frm.fields_dict[VALUE_FIELD];
        if (!field || !field.df) return;
        var want = _want(frm.doc);
        var cur = field.df;
        if (cur.fieldtype === want.type
            && String(cur.options || "") === want.options
            && String(cur.description || "") === (want.hint || "")) return;

        var df = Object.assign({}, cur, {
            fieldtype: want.type,
            options: want.options,
            description: want.hint || "",
        });
        try {
            if (frm.layout && frm.layout.replace_field) {
                frm.layout.replace_field(VALUE_FIELD, df);
                return;
            }
            frm.set_df_property(VALUE_FIELD, "fieldtype", want.type);
            frm.set_df_property(VALUE_FIELD, "options", want.options);
            // Đường dự phòng cũng phải giữ lời giải thích.
            frm.set_df_property(VALUE_FIELD, "description", want.hint || "");
            frm.refresh_field(VALUE_FIELD);
        } catch (e) {
            console.warn("[alumglass] không vẽ lại được ô giá trị mặc định", e);
            frappe.show_alert({
                message: __("Ô giá trị chưa đổi được kiểu — tải lại trang rồi thử lại."),
                indicator: "orange",
            }, 7);
        }
    }

    /**
     * Đổi kiểu mà giá trị mặc định không còn hợp ⇒ NÓI ra, ⛔ để nó âm thầm
     * thành 0/trống rồi mới lộ lúc tính giá.
     */
    function _guard_value(frm) {
        var type = String((frm.doc && frm.doc.var_type) || "").trim();
        var value = String((frm.doc && frm.doc.default_value) || "").trim();
        if (!value) return;

        var bad = "";
        if (type === "Check" && ["0", "1"].indexOf(value) === -1) {
            bad = __("Giá trị “{0}” không hợp kiểu Đúng/Sai.", [value]);
        } else if (
            ["Float", "Int", "Currency", "Percent"].indexOf(type) !== -1
            && isNaN(parseFloat(value))
        ) {
            bad = __("Giá trị “{0}” không phải số.", [value]);
        } else if (type === "Select") {
            var opts = String((frm.doc && frm.doc.select_options) || "")
                .split("\n")
                .map(function (item) { return item.trim(); })
                .filter(function (item) { return item; });
            if (opts.length && opts.indexOf(value) === -1) {
                // Giữ giá trị (có thể là dữ liệu cũ) nhưng phải báo.
                frappe.show_alert({
                    message: __("Giá trị “{0}” không có trong danh sách lựa chọn — kiểm tra lại."),
                    indicator: "orange",
                }, 7);
            }
            return;
        }
        if (!bad) return;
        frm.set_value(VALUE_FIELD, "");
        frappe.show_alert({
            message: bad + " " + __("Đã để trống — nhập lại theo kiểu mới."),
            indicator: "orange",
        }, 7);
    }

    frappe.ui.form.on("AL Variable Library", {
        refresh: function (frm) { _apply(frm); },
        var_type: function (frm) {
            _apply(frm);
            _guard_value(frm);
        },
        select_options: function (frm) { _apply(frm); },
        link_doctype: function (frm) { _apply(frm); },
    });
})();
