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
    // Công thức đổi (gõ tay / chèn từ hộp thoại) ⇒ câu giải thích thường trực
    // phải cập nhật ngay, ⛔ để câu cũ nói sai công thức mới.
    qty_formula: function (frm, cdt, cdn) {
        _al_accessory_item_render(frm, cdt, cdn, 0);
    },
});

/**
 * Câu giải thích THƯỜNG TRỰC dưới nút "Chọn công thức": sau khi hộp thoại
 * đóng, đây là chỗ DUY NHẤT nói ô `qty_formula` đang tính gì (UX1 #3).
 * Dùng `describeFormula` của rule_helper — nhãn người đọc, ⛔ mã biến/mã quy
 * tắc trong câu. Công thức lạ ⇒ "Công thức tự nhập", ⛔ đoán số.
 */
function _al_accessory_item_formula_html(helper, value) {
    var info = typeof helper.describeFormula === "function"
        ? helper.describeFormula(value)
        : { text: __("Công thức tự nhập"), linkable: false, rule_code: "" };
    var html = '<div class="al-formula-desc" style="font-size:11px;color:#475569;'
        + 'margin-top:3px;line-height:1.45;">'
        + helper.escapeHtml(info.text) + "</div>";
    if (info.linkable) {
        // Mã quy tắc CHỈ nằm trong route của nút — ⛔ hiện trong câu.
        html += '<button type="button" class="btn btn-xs btn-default" '
            + 'data-role="open-rule" data-rule-code="'
            + helper.escapeHtml(info.rule_code) + '" style="margin-top:3px;">'
            + helper.escapeHtml(__("Xem quy tắc")) + "</button>";
    }
    return html;
}

function _al_accessory_item_line_name(helper, row, items) {
    if (!row) return "";
    if (typeof helper.rowDisplayName === "function") {
        var index = (typeof helper.rowIndexBySlug === "function")
            ? helper.rowIndexBySlug(items, row.slug) : -1;
        return helper.rowDisplayName(row, index);
    }
    // Trình duyệt còn cache helper CŨ ⇒ để trống, ⛔ slug.
    return row.line_name || "";
}

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

    var helper = window.AlumGlassRuleHelper;
    $wrap.html(
        '<div style="margin:4px 0 2px;">'
        + '<button type="button" class="btn btn-xs btn-default" data-role="open-insert">'
        + "🧩 " + __("Chọn công thức") + "</button>"
        + _al_accessory_item_formula_html(helper, row.qty_formula)
        + "</div>"
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
            line_label: _al_accessory_item_line_name(
                window.AlumGlassRuleHelper, row,
                (frm.doc && frm.doc[table]) || []),
        });
    });
    $wrap.on("click.alrule", "[data-role='open-rule']", function () {
        var code = String($(this).attr("data-rule-code") || "");
        var url = helper.ruleFormRoute ? helper.ruleFormRoute(code) : "";
        if (url) window.open(url, "_blank");
    });
}
