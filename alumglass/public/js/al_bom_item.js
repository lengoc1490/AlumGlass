// AL Bom Item — Client Script (dòng con của AL Bom Set)
// Module: AL Bom Engine
//
// ⚠ NẠP QUA `app_include_js`, KHÔNG qua `doctype_js`: đây là doctype CON,
// Frappe v14 chỉ eval `__js` của doctype đang mở form — dòng con dùng chung
// script_manager của form CHA nên `doctype_js` cho doctype con không chạy.
// Tệp này chỉ ĐĂNG KÝ handler `frappe.ui.form.on("AL Bom Item", …)`.
//
// ═══════════════════════════════════════════════════════════════════════════
// MỤC ĐÍCH (thiết kế docs/design/tra-cuu-quy-tac-de-hieu.md §3.4)
//
//   1. `qty_helper_html` (ngay dưới ô Qty Formula): nút "🧩 Chọn công thức" —
//      mở hộp thoại chọn cách tính số lượng KHÔNG CẦN BIẾT CODE. Hộp thoại
//      3 bước + 4 lựa chọn dựng sẵn nằm trong public/js/rule_helper.js.
//
//   2. `rule_help_html` (mục Rule Configuration, chỉ hiện khi mode = Rule):
//      tự kể "tra CÁI GÌ của dòng NÀO → quy tắc NÀO → ra CÁI GÌ" + 3 nút
//      Xem quy tắc / Thử tra / Chọn dữ liệu tra. Thiếu cấu hình ⇒ câu hướng
//      dẫn đúng ô cần sửa (không phải ô trống).
//
// RÀNG BUỘC ĐÃ XỬ LÝ
//   - Dòng CHƯA LƯU (cdn `new-…`) vẫn render bình thường (không đọc DB).
//   - Chưa có `item_rule` ⇒ ⛔ KHÔNG gọi API quy tắc.
//   - Site chưa migrate (thiếu 4 field mô tả của AL Rule) ⇒ vẫn chạy, chỉ
//     dùng nhãn suy từ `rule_input_expr`.
//   - Không có dòng kính ⇒ câu nói rõ cần chọn kính trước.
// ═══════════════════════════════════════════════════════════════════════════

frappe.ui.form.on("AL Bom Item", {
    form_render: function (frm, cdt, cdn) {
        _al_bom_item_render(frm, cdt, cdn, 0);
    },
    refresh: function (frm, cdt, cdn) {
        _al_bom_item_render(frm, cdt, cdn, 0);
    },
    item_selection_mode: function (frm, cdt, cdn) {
        _al_bom_item_render(frm, cdt, cdn, 0);
    },
    item_rule: function (frm, cdt, cdn) {
        _al_bom_item_render(frm, cdt, cdn, 0);
    },
    rule_input_expr: function (frm, cdt, cdn) {
        _al_bom_item_render(frm, cdt, cdn, 0);
    },
});

// Nhãn dự phòng khi AL Rule chưa có field mô tả (site chưa migrate) — SUY TỪ
// chính `rule_input_expr`, không hardcode theo từng quy tắc cụ thể.
// Giữ chuỗi RAW rồi dịch lúc dùng: tệp nạp toàn trang, `__()` chưa chắc có
// ngay lúc eval.
var AL_BOM_ITEM_FIELD_LABELS = {
    total_thick_mm: "Độ dày kính",
    glass_thick: "Độ dày kính",
    glass_type: "Loại kính",
    width: "Rộng",
    height: "Cao",
    // Dữ liệu cũ / quy tắc đặc biệt — engine đọc được từ `glass_data`.
    max_area_m2: "Diện tích tối đa",
    glass_name: "Tên kính",
    glass_type_name: "Tên loại kính",
};
var AL_BOM_ITEM_FIELD_UNITS = {
    total_thick_mm: "mm",
    glass_thick: "mm",
    width: "mm",
    height: "mm",
    max_area_m2: "m²",
};

function _al_bom_item_field_label(field) {
    return __(AL_BOM_ITEM_FIELD_LABELS[field] || "giá trị đã chọn");
}

// Token chống vẽ đè: metadata quy tắc về muộn cho dòng đã đổi cấu hình.
// Dùng WeakMap theo OBJECT dòng — ⛔ gắn thuộc tính lạ lên doc (doc bị gửi
// lên server khi Lưu).
var _al_bom_item_tokens = typeof WeakMap === "function" ? new WeakMap() : null;

function _al_bom_item_next_token(row) {
    if (!_al_bom_item_tokens) return 1;
    var next = (_al_bom_item_tokens.get(row) || 0) + 1;
    _al_bom_item_tokens.set(row, next);
    return next;
}

function _al_bom_item_token(row) {
    return _al_bom_item_tokens ? (_al_bom_item_tokens.get(row) || 0) : 1;
}

/**
 * Vẽ lại 2 vùng hỗ trợ của 1 dòng. `attempt` = số lần đã thử (grid form có
 * thể chưa dựng xong ngay sau form_render ⇒ thử lại có giới hạn).
 */
function _al_bom_item_render(frm, cdt, cdn, attempt) {
    if (!frm || !cdt || !cdn || !window.AlumGlassRuleHelper) return;
    var row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;
    var table = row.parentfield || "items";
    var helper = window.AlumGlassRuleHelper;

    var $qtyHelper = helper.rowFieldWrapper(frm, table, cdn, "qty_helper_html");
    var $ruleHelp = helper.rowFieldWrapper(frm, table, cdn, "rule_help_html");

    if (!$qtyHelper.length && !$ruleHelp.length) {
        // Ô HTML chưa có trong form (dòng thu gọn / site chưa migrate) —
        // thử lại vài nhịp rồi bỏ, KHÔNG ném lỗi.
        if (attempt < 3) {
            setTimeout(function () {
                _al_bom_item_render(frm, cdt, cdn, attempt + 1);
            }, 150);
        }
        return;
    }

    if ($qtyHelper.length) _al_bom_item_render_qty_button(frm, table, cdn, $qtyHelper);
    if ($ruleHelp.length) _al_bom_item_render_rule_help(frm, table, cdn, row, $ruleHelp);
}

function _al_bom_item_render_qty_button(frm, table, cdn, $wrap) {
    var html = '<div style="margin:4px 0 2px;">'
        + '<button type="button" class="btn btn-xs btn-default" data-role="open-insert">'
        + "🧩 " + __("Chọn công thức") + "</button></div>";
    $wrap.html(html);
    $wrap.off(".alrule");
    $wrap.on("click.alrule", "[data-role='open-insert']", function () {
        var row = locals["AL Bom Item"] && locals["AL Bom Item"][cdn];
        window.AlumGlassRuleHelper.openInsert({
            frm: frm,
            child_table: table,
            cdn: cdn,
            fieldname: "qty",
            // Dòng kính trong BOM CÓ Rộng/Cao — hộp thoại mời 2 cột này cho
            // mỗi dòng (ô `qty` đi qua Formula Engine nên hợp lệ).
            item_fields: ["width", "height"],
            line_label: row && row.line_name ? row.line_name : "",
        });
    });
}

/** Câu hướng dẫn khi thiếu cấu hình — nói ĐÚNG ô cần sửa. */
function _al_bom_item_hint(text) {
    return '<div style="font-size:12px;color:#b45309;line-height:1.5;">'
        + text + "</div>";
}

function _al_bom_item_buttons(buttons) {
    var html = '<div style="margin-top:4px;">';
    buttons.forEach(function (button) {
        html += '<button type="button" class="btn btn-xs btn-default" '
            + 'data-role="' + button.role + '" style="margin-right:4px;"'
            + (button.disabled ? " disabled" : "") + ">"
            + button.label + "</button>";
    });
    return html + "</div>";
}

function _al_bom_item_render_rule_help(frm, table, cdn, row, $wrap) {
    var helper = window.AlumGlassRuleHelper;

    // `depends_on` đã ẩn vùng này khi mode khác Rule; ở đây chỉ việc dọn nội
    // dung cũ để lần bật lại không thấy câu của trạng thái trước.
    if (row.item_selection_mode !== "Rule") {
        $wrap.empty();
        return;
    }

    var ruleCode = String(row.item_rule || "").trim();
    var expr = String(row.rule_input_expr || "").trim();
    var ref = helper.parseItemExpr(expr);
    var items = (frm.doc && frm.doc[table]) || [];
    var refRow = ref ? helper.findRowBySlug(items, ref.slug) : null;

    var viewButton = { role: "view-rule", label: __("Xem quy tắc"), disabled: !ruleCode };
    var tryButton = { role: "try-rule", label: __("Thử tra"), disabled: !ruleCode };
    var pickButton = { role: "pick-input", label: __("Chọn dữ liệu tra") };

    // Khung câu hướng dẫn + 2 nút (bấm được): dùng cho mọi trạng thái thiếu/
    // sai cấu hình để câu chữ không trôi lệch giữa các nhánh.
    function paintHint(text) {
        $wrap.html(_al_bom_item_hint(text) + _al_bom_item_buttons([viewButton, pickButton]))
            .off(".alrule")
            .on("click.alrule", "[data-role='view-rule']", function () {
                _al_bom_item_open_rule(ruleCode);
            })
            .on("click.alrule", "[data-role='pick-input']", function () {
                _al_bom_item_pick_input(frm, table, cdn);
            });
    }

    // ── Thiếu cấu hình ────────────────────────────────────────────────
    if (!ruleCode) {
        $wrap.html(_al_bom_item_hint(
            __("Chưa chọn quy tắc cho dòng này. Chọn quy tắc ở ô <b>Item Rule</b> phía trên.")
        ) + _al_bom_item_buttons([pickButton]))
            .off(".alrule")
            .on("click.alrule", "[data-role='pick-input']", function () {
                _al_bom_item_pick_input(frm, table, cdn);
            });
        return;
    }
    if (!expr) {
        paintHint(__("Chưa chọn dữ liệu đem tra. Bấm <b>Chọn dữ liệu tra</b> để chọn (ví dụ độ dày kính của dòng Kính trên)."));
        return;
    }
    if (!refRow) {
        // ⛔ KHÔNG in slug kỹ thuật (`kinh_tren`) ra câu người dùng.
        paintHint(__("Dòng dữ liệu đã chọn không còn trong bộ này — bấm <b>Chọn dữ liệu tra</b> để chọn lại."));
        return;
    }
    if (!helper.isRuleInputReadable(expr, items)) {
        // Chọn "Rộng"/"Cao" (hoặc dòng không phải kính) ⇒ engine đọc ra 0 ÂM
        // THẦM, dòng không có mã. Báo ngay thay vì để lỗi im lặng.
        paintHint(__("Dữ liệu tra đang chọn không đọc được — quy tắc chỉ đọc được độ dày kính hoặc loại kính của DÒNG KÍNH. Bấm <b>Chọn dữ liệu tra</b> để chọn lại."));
        return;
    }

    // ── Đủ cấu hình: đọc metadata quy tắc rồi vẽ câu hoàn chỉnh ───────
    // Render ngay bản dùng TÊN DÒNG + nhãn suy từ field (không chờ API);
    // metadata về sau thì vẽ lại để có `rule_name`/`output_label`.
    var lineName = refRow.line_name || refRow.slug;
    var labelFromField = _al_bom_item_field_label(ref.field);
    var unitFromField = AL_BOM_ITEM_FIELD_UNITS[ref.field] || "";
    var inputLabel = labelFromField + (unitFromField ? " (" + unitFromField + ")" : "");
    var outputLabel = __("mã vật tư");
    // Chưa có metadata ⇒ ⛔ phơi mã `RULE-…` ra câu người dùng; hiện nhãn
    // chung, mã nằm trong `title` để vẫn tra được khi cần.
    var ruleName = "";
    var ruleFetchFailed = false;

    function ruleLabelHtml() {
        var text = ruleName
            ? helper.escapeHtml(ruleName)
            : helper.escapeHtml(__("quy tắc đã chọn"));
        return '<span title="' + helper.escapeHtml(ruleCode) + '">' + text + "</span>";
    }

    function paint() {
        var sentence = __("Dòng này <b>lấy mã tự động</b>: tra <b>{0}</b> của dòng <b>“{1}”</b> → quy tắc <b>“{2}”</b> → ra <b>{3}</b>.", [
            helper.escapeHtml(inputLabel),
            helper.escapeHtml(lineName),
            ruleLabelHtml(),
            helper.escapeHtml(outputLabel),
        ]);
        var html = '<div style="font-size:12px;color:#0f172a;line-height:1.5;">'
            + sentence + "</div>";
        if (ruleFetchFailed) {
            html += '<div style="font-size:11px;color:#b45309;margin-top:2px;">'
                + __("Chưa đọc được tên quy tắc — mở «Xem quy tắc».") + "</div>";
        }
        html += _al_bom_item_buttons([viewButton, tryButton, pickButton]);
        $wrap.html(html)
            .off(".alrule")
            .on("click.alrule", "[data-role='view-rule']", function () {
                _al_bom_item_open_rule(ruleCode);
            })
            .on("click.alrule", "[data-role='try-rule']", function () {
                _al_bom_item_try(table, ruleCode, expr, items, inputLabel, ruleName);
            })
            .on("click.alrule", "[data-role='pick-input']", function () {
                _al_bom_item_pick_input(frm, table, cdn);
            });
    }

    var token = _al_bom_item_next_token(row);
    paint();

    helper.fetchRuleForCode(ruleCode).then(function (meta) {
        // Dòng đã đổi cấu hình / đã đóng trong lúc chờ ⇒ ⛔ vẽ đè.
        if (_al_bom_item_token(row) !== token) return;
        if (row.item_rule !== ruleCode) return;
        if (!meta) {
            // Đọc metadata lỗi ⇒ nói việc cần làm, vẫn giữ nhãn chung ở câu
            // trên (⛔ không hiện mã quy tắc trần).
            ruleFetchFailed = true;
            paint();
            return;
        }
        ruleName = String(meta.rule_name || "").trim() || ruleName;
        if (meta.input_label) {
            inputLabel = helper.ruleInputLabel(meta);
        }
        if (meta.output_label) outputLabel = meta.output_label;
        else if (String(meta.result_type || "").toUpperCase() === "NUMBER") {
            outputLabel = __("số");
        }
        paint();
    });
}

function _al_bom_item_open_rule(ruleCode) {
    if (!ruleCode) return;
    // Mở tab mới — KHÔNG rời form BOM đang sửa dở (mất thay đổi chưa lưu).
    var url = "/app/al-rule/" + encodeURIComponent(ruleCode);
    try {
        if (frappe.utils && typeof frappe.utils.get_form_link === "function") {
            url = frappe.utils.get_form_link("AL Rule", ruleCode, true);
        }
    } catch (e) { /* dùng url mặc định */ }
    window.open(url, "_blank");
}

function _al_bom_item_pick_input(frm, table, cdn) {
    window.AlumGlassRuleHelper.openInputPicker({
        frm: frm,
        child_table: table,
        cdn: cdn,
        fieldname: "rule_input_expr",
        on_applied: function () {
            var row = locals["AL Bom Item"] && locals["AL Bom Item"][cdn];
            _al_bom_item_render(frm, (row && row.doctype) || "AL Bom Item", cdn, 0);
        },
    });
}

/**
 * "Thử tra": lấy giá trị hiện tại của dòng được tham chiếu (nếu có) rồi mở
 * hộp thoại; chưa có số liệu ⇒ hộp thoại cho nhập tay.
 */
function _al_bom_item_try(table, ruleCode, expr, items, inputLabel, ruleName) {
    var helper = window.AlumGlassRuleHelper;
    var option = { value: expr, sample_value: null, label: inputLabel };
    helper.fetchOptionSample(option, items).then(function (sample) {
        // `inputLabel` ở đây đã kèm đơn vị ⇒ không truyền thêm `input_unit`.
        helper.openRulePreview({
            rule_code: ruleCode,
            input_value: sample,
            input_label: inputLabel,
            rule_name: ruleName,
        });
    });
}
