// AL Accessory Item — Client Script (dòng con của AL Accessory Set)
// Module: AL Bom Engine
//
// ⚠ NẠP QUA `app_include_js`, KHÔNG qua `doctype_js` — xem giải thích ở
// public/js/al_bom_item.js (doctype con không được eval `__js` trong lưới).
//
// `qty_formula` là CHỖ CÔNG THỨC BẢN LỀ (thiết kế §3.3): người dựng báo giá
// phải gõ `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel`. Tệp này gắn nút
// "🧩 Chọn công thức" ngay dưới ô đó; toàn bộ hộp thoại nằm trong
// public/js/rule_helper.js (dùng chung với AL Bom Item.qty).
//
// Site chưa migrate (thiếu field HTML) ⇒ wrapper rỗng, bỏ qua, không lỗi.

frappe.ui.form.on("AL Accessory Item", {
    form_render: function (frm, cdt, cdn) {
        _al_accessory_item_render(frm, cdt, cdn, 0);
    },
    refresh: function (frm, cdt, cdn) {
        _al_accessory_item_render(frm, cdt, cdn, 0);
    },
});

function _al_accessory_item_render(frm, cdt, cdn, attempt) {
    if (!frm || !cdt || !cdn || !window.AlumGlassRuleHelper) return;
    var row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;
    var table = row.parentfield || "items";
    var $wrap = window.AlumGlassRuleHelper.rowFieldWrapper(
        frm, table, cdn, "qty_formula_helper_html");
    if (!$wrap.length) {
        // Dòng thu gọn / site chưa migrate — thử lại vài nhịp rồi bỏ.
        if (attempt < 3) {
            setTimeout(function () {
                _al_accessory_item_render(frm, cdt, cdn, attempt + 1);
            }, 150);
        }
        return;
    }

    $wrap.html(
        '<div style="margin:4px 0 2px;">'
        + '<button type="button" class="btn btn-xs btn-default" data-role="open-insert">'
        + "🧩 " + __("Chọn công thức") + "</button></div>"
    );
    $wrap.off(".alrule");
    $wrap.on("click.alrule", "[data-role='open-insert']", function () {
        var row = locals["AL Accessory Item"] && locals["AL Accessory Item"][cdn];
        window.AlumGlassRuleHelper.openInsert({
            frm: frm,
            child_table: table,
            cdn: cdn,
            fieldname: "qty_formula",
            // AL Accessory Item KHÔNG có cột Rộng/Cao ⇒ ⛔ mời `items.<dòng>.width/height`
            // (chèn vào là Lưu báo "Biến …height chưa được khai báo"). Chỉ còn
            // biến chứng từ: H_mm, n_panel, …
            item_fields: [],
            line_label: row && row.line_name ? row.line_name : "",
        });
    });
}
