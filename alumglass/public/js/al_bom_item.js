// AL Bom Item — Client Script (dòng con của AL Bom Set)
// Module: AL Bom Engine
//
// ⚠ NẠP QUA `app_include_js`, KHÔNG qua `doctype_js`: đây là doctype CON,
// Frappe v14 chỉ eval `__js` của doctype đang mở form — dòng con dùng chung
// script_manager của form CHA nên `doctype_js` cho doctype con không chạy.
// Tệp này chỉ ĐĂNG KÝ handler `frappe.ui.form.on("AL Bom Item", …)`.
//
// ═══════════════════════════════════════════════════════════════════════════
// MỤC ĐÍCH (thiết kế docs/design/tra-cuu-quy-tac-de-hieu.md §3.4 + §7)
//
//   1. `qty_helper_html` (ngay dưới ô Qty Formula): nút "🧩 Chọn công thức" —
//      mở hộp thoại chọn cách tính số lượng KHÔNG CẦN BIẾT CODE. Hộp thoại
//      3 bước + 4 lựa chọn dựng sẵn nằm trong public/js/rule_helper.js.
//
//   2. `rule_help_html` (mục Rule Configuration, chỉ hiện khi mode = Rule):
//      tự kể "tra CÁI GÌ của dòng NÀO → quy tắc NÀO → ra CÁI GÌ" + nút
//      Xem quy tắc / Thử tra / chọn nguồn dữ liệu.
//
//   3. KHỐI "ĐIỀU KIỆN TRA" ngay dưới câu quy tắc (Owner 2026-11-25: "phải
//      chuyển danh sách các điều kiện công thức tra ra kính lên gần chỗ rule"):
//      đọc doc `AL Rule` của `item_rule` (cache trong phiên, qua
//      `AlumGlassRuleHelper.fetchRuleForCode`), hiện tối đa 3 điều kiện +
//      "… và N nữa" + "Xem tất cả" mở form quy tắc ở tab mới. Câu mỗi dòng
//      dựng từ CHÍNH metadata quy tắc (`input_label`/`input_unit`/
//      `output_label`) — ⛔ hardcode "Độ dày kính". Lỗi/không quyền ⇒ khối
//      trống, ⛔ làm vỡ form. Quy tắc đang TẮT ⇒ cảnh báo trước khi hiện.
//
//      CHẶNG 3 (2026-11-25): quy tắc TỰ KHAI nó tra theo dữ liệu nào —
//      `AL Rule.input_variable` + `input_scope`:
//        · ROW    ⇒ dòng BOM chỉ chọn DÒNG NGUỒN (`rule_input_row`); câu
//                   "Quy tắc khai tra theo <label> · lấy từ dòng <tên dòng>
//                   · hiện tại <số> → <kết quả>".
//        · GLOBAL ⇒ ⛔ hỏi nguồn; câu "Quy tắc tự lấy <label> (<biến>)".
//        · chưa khai ⇒ đường cũ (`rule_input_expr`, danh sách dòng kính).
//      Ô `rule_input_expr` ẩn khỏi người dùng thường, chỉ còn dưới mục
//      "Nâng cao" cho quản trị.
//
// RÀNG BUỘC ĐÃ XỬ LÝ
//   - Dòng CHƯA LƯU (cdn `new-…`) vẫn render bình thường (không đọc DB).
//   - Chưa có `item_rule` ⇒ ⛔ KHÔNG gọi API quy tắc.
//   - Site chưa migrate (thiếu field mô tả / `input_variable`) ⇒ vẫn chạy,
//     quy tắc đọc ra "chưa khai" ⇒ giữ nguyên giao diện cũ.
//   - Không có dòng chứa dữ liệu ⇒ câu nói rõ cần chọn dữ liệu ở dòng nguồn.
//   - ⛔ phơi `rule_code` / `items.…` ra câu người dùng (mã quy tắc chỉ nằm
//     trong `title` của tên quy tắc; biểu thức cũ nằm trong mục "Nâng cao").
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
    rule_input_row: function (frm, cdt, cdn) {
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

/**
 * Nhãn dòng người-đọc — có helper mới thì dùng (fallback "Dòng chưa đặt tên
 * (Dòng N)"); trình duyệt còn cache `rule_helper.js` CŨ (thiếu hàm) thì để
 * trống, ⛔ rơi về slug.
 */
function _al_bom_item_line_name(helper, row, items) {
    if (!row) return "";
    if (helper && typeof helper.rowDisplayName === "function") {
        var index = (typeof helper.rowIndexBySlug === "function")
            ? helper.rowIndexBySlug(items, row.slug) : -1;
        return helper.rowDisplayName(row, index);
    }
    return row.line_name || "";
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

    // Biến "Tra theo" do engine TỰ TÍNH cần danh mục biến (cờ `computed`);
    // chưa có thì nạp nền rồi vẽ lại đúng 1 lượt.
    _al_bom_item_ensure_input_vars(function () {
        _al_bom_item_render(frm, table, cdn, 0);
    });

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
        var items = (frm.doc && frm.doc[table]) || [];
        window.AlumGlassRuleHelper.openInsert({
            frm: frm,
            child_table: table,
            cdn: cdn,
            fieldname: "qty",
            // Dòng kính trong BOM CÓ Rộng/Cao — hộp thoại mời 2 cột này cho
            // mỗi dòng (ô `qty` đi qua Formula Engine nên hợp lệ). Quy tắc tự
            // khai "tra theo" thì danh sách do QUY TẮC quyết định.
            item_fields: ["width", "height"],
            line_label: _al_bom_item_line_name(
                window.AlumGlassRuleHelper, row, items),
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
        // `primary`: hành động BẮT BUỘC để dòng ra được mã (vd chọn dòng lấy
        // dữ liệu) — tô hổ phách để không lẫn với nút phụ.
        var cls = button.primary ? "btn btn-xs btn-warning" : "btn btn-xs btn-default";
        html += '<button type="button" class="' + cls + '" '
            + 'data-role="' + button.role + '" style="margin-right:4px;"'
            + (button.disabled ? " disabled" : "") + ">"
            + button.label + "</button>";
    });
    return html + "</div>";
}

function _al_bom_item_grid_row(frm, table, cdn) {
    var field = frm && frm.fields_dict && frm.fields_dict[table];
    var grid = field && field.grid;
    if (!grid) return null;
    if (typeof grid.get_row === "function") return grid.get_row(cdn);
    return (grid.grid_rows_by_docname || {})[cdn] || null;
}

/**
 * Ẩn/hiện 1 field trong dòng đang mở rộng. Ba lớp dự phòng vì Frappe đổi API
 * giữa các phiên bản — mục tiêu là ô kỹ thuật KHÔNG hiện ra với người dùng
 * thường (yêu cầu thiết kế §7.3).
 *
 * ⚠ `df` của field dòng con là object meta DÙNG CHUNG giữa các dòng ⇒ mỗi lượt
 * vẽ PHẢI đặt lại trạng thái cho đúng dòng của nó (không dựa vào trạng thái
 * còn sót từ dòng khác). Hàm này chạy ở mọi `form_render` / `refresh` của dòng.
 */
function _al_bom_item_toggle_field(frm, table, cdn, fieldname, show) {
    var row = _al_bom_item_grid_row(frm, table, cdn);
    if (row && typeof row.toggle_display === "function") {
        try { row.toggle_display(fieldname, !!show); } catch (e) { /* rơi xuống */ }
    }
    var control = row && row.grid_form && row.grid_form.fields_dict
        && row.grid_form.fields_dict[fieldname];
    if (control && typeof control.toggle === "function") {
        try { control.toggle(!!show); } catch (e) { /* rơi xuống */ }
    }
    try {
        $('.grid-row[data-name="' + cdn + '"]')
            .find('[data-fieldname="' + fieldname + '"]')
            .toggle(!!show);
    } catch (e) { /* bỏ qua */ }
}

/**
 * Khối "Nâng cao" — biểu thức cũ chỉ còn cho người kỹ thuật/đường lùi.
 * `warn` = biểu thức KHÔNG CÒN HIỆU LỰC (quy tắc đã khai "Tra theo") ⇒ tô
 * hổ phách + khoá nút sửa, ⛔ để người dùng sửa một ô vô tác dụng.
 */
function _al_bom_item_advanced_html(helper, expr, showFieldButton, note, warn) {
    var html = '<details style="margin-top:4px;">'
        + '<summary style="font-size:11px;color:#64748b;cursor:pointer;">'
        + helper.escapeHtml(__("Nâng cao")) + "</summary>"
        + '<div style="font-size:11px;color:' + (warn ? "#b45309" : "#64748b")
        + ';line-height:1.5;margin-top:2px;">'
        + helper.escapeHtml(note || __("Dòng này lấy dữ liệu theo quy tắc đã khai — không cần nhập biểu thức."));
    if (expr) {
        // Màn hình cấu hình ⇒ được hiện chuỗi kỹ thuật, ⛔ trộn vào câu chính.
        html += "<br>" + helper.escapeHtml(
            warn ? __("Biểu thức cũ (chỉ để đối chiếu)") : __("Biểu thức cũ đang có")) + ": "
            + '<span style="font-family:monospace;color:#0f172a;">'
            + helper.escapeHtml(expr) + "</span>";
    }
    html += "</div>";
    if (showFieldButton) {
        html += '<div style="margin-top:4px;"><button type="button" '
            + 'class="btn btn-xs btn-default" data-role="show-expr">'
            + helper.escapeHtml(__("Hiện ô biểu thức")) + "</button></div>";
    }
    return html + "</details>";
}

/**
 * Danh mục biến "Tra theo" (cờ `computed`) chưa có ⇒ nạp MỘT lần rồi vẽ
 * lại, để biến engine tự tính liệt kê được mọi dòng BOM (#4). Lỗi ⇒ thôi,
 * giữ hành vi cũ (⛔ chặn người dùng).
 */
var _al_bom_item_input_vars_requested = false;
function _al_bom_item_ensure_input_vars(callback) {
    var helper = window.AlumGlassRuleHelper;
    if (!helper || typeof helper.fetchInputVariables !== "function") return;
    if (typeof helper.cachedInputVariables === "function"
            && helper.cachedInputVariables().length) return;
    if (_al_bom_item_input_vars_requested) return;
    _al_bom_item_input_vars_requested = true;
    helper.fetchInputVariables().then(function () {
        if (typeof callback === "function") callback();
    }).catch(function () { /* giữ hành vi cũ */ });
}

/**
 * Câu khi quy tắc ROW CHƯA chọn dòng nguồn — nói thẳng hậu quả (dòng chưa có
 * mã vật tư) + việc cần làm. THUẦN (test bằng Node).
 */
function _al_bom_item_pick_row_hint(label, hasOptions) {
    if (hasOptions) {
        return __("Quy tắc khai tra theo <b>{0}</b> — chưa chọn <b>dòng lấy dữ liệu</b> nên dòng này <b>chưa có mã vật tư</b>. Bấm <b>Chọn dòng lấy dữ liệu</b> bên dưới.", [label]);
    }
    return __("Quy tắc khai tra theo <b>{0}</b> nhưng bộ này chưa có dòng nào chứa dữ liệu đó nên dòng này <b>chưa có mã vật tư</b> — nhập số liệu cho dòng nguồn (ví dụ dòng kính) trước, rồi bấm <b>Chọn dòng lấy dữ liệu</b>.", [label]);
}

/**
 * Câu khi dòng nguồn ĐÃ chọn nhưng KHÔNG đọc được dữ liệu — nêu rõ thiếu cái
 * gì, làm gì, và hậu quả. `lineName` rỗng = dòng đã bị xoá khỏi bộ. THUẦN.
 */
function _al_bom_item_source_missing_hint(lineName, label) {
    if (lineName) {
        return __("Dòng <b>“{0}”</b> chưa có <b>{1}</b> — nhập số liệu cho dòng đó, hoặc bấm <b>Chọn dòng lấy dữ liệu</b> để chọn dòng khác. Dòng này sẽ không ra mã vật tư.", [lineName, label]);
    }
    return __("Dòng lấy dữ liệu đã chọn không còn trong bộ này — bấm <b>Chọn dòng lấy dữ liệu</b> để chọn lại.");
}

/**
 * Khối "Điều kiện tra" NGAY DƯỚI câu quy tắc (Owner 2026-11-25): người dựng
 * báo giá thấy quy tắc tra theo cái gì, mấy điều kiện, phạm vi nào — ⛔ phải
 * mở tài liệu quy tắc.
 *
 * Vẽ NGAY bằng mã vật tư (⛔ chờ API), rồi tra TÊN của mã và vẽ lại. Lỗi /
 * không có quyền ⇒ khối trống, ⛔ làm vỡ form. Lượt về muộn (dòng đã đổi
 * quy tắc) ⇒ bỏ qua.
 */
function _al_bom_item_paint_conditions(meta, $slot, isStale) {
    if (!$slot || !$slot.length) return;
    var helper = window.AlumGlassRuleHelper;
    if (!helper || typeof helper.ruleConditionPreviewHtml !== "function") return;
    if (!meta) {
        $slot.empty();
        return;
    }

    function paint(names) {
        var html = "";
        // Quy tắc đang TẮT ⇒ điều kiện CHƯA áp dụng: nói trước rồi mới hiện
        // danh sách (⛔ trình bày như đang dùng được).
        if (helper.isRuleActive(meta) === false) {
            html += '<div style="font-size:11px;color:#b45309;margin-top:2px;">⚠ '
                + helper.escapeHtml(__("Quy tắc đang tắt nên các điều kiện dưới đây chưa áp dụng."))
                + "</div>";
        }
        html += helper.ruleConditionPreviewHtml(meta, {
            max: 3,
            item_names: names || {},
            // "compact" ⇒ "Tra theo: <nhãn> · N điều kiện:" — câu quy tắc ngay
            // TRÊN khối đã nói "Quy tắc tra theo <nhãn>", dạng "full" lặp lại
            // đúng câu đó ngay dưới (UX1 vòng 3).
            heading: "compact",
        });
        $slot.html(html);
    }

    var codes = (typeof helper.ruleConditionItemCodes === "function")
        ? helper.ruleConditionItemCodes(meta) : [];
    var known = (typeof helper.cachedItemNames === "function")
        ? helper.cachedItemNames(codes) : {};
    paint(known);

    var missing = codes.filter(function (code) {
        return known[code] === undefined;
    });
    if (!missing.length || typeof helper.fetchItemNames !== "function") return;
    helper.fetchItemNames(codes).then(function (names) {
        if (isStale()) return;
        paint(names);
    }).catch(function () { /* giữ mã vật tư */ });
}

function _al_bom_item_render_rule_help(frm, table, cdn, row, $wrap) {
    var helper = window.AlumGlassRuleHelper;

    // `depends_on` đã ẩn vùng này khi mode khác Rule; ở đây chỉ việc dọn nội
    // dung cũ để lần bật lại không thấy câu của trạng thái trước.
    if (row.item_selection_mode !== "Rule") {
        $wrap.empty().off(".alrule");
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_row", false);
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_expr", false);
        return;
    }

    var ruleCode = String(row.item_rule || "").trim();
    var items = (frm.doc && frm.doc[table]) || [];

    var viewButton = { role: "view-rule", label: __("Xem quy tắc"), disabled: !ruleCode };
    var tryButton = { role: "try-rule", label: __("Thử tra"), disabled: !ruleCode };

    function setContent(html, handlers) {
        $wrap.html(html).off(".alrule");
        Object.keys(handlers || {}).forEach(function (role) {
            $wrap.on("click.alrule", "[data-role='" + role + "']", handlers[role]);
        });
    }

    // ── Thiếu cấu hình ────────────────────────────────────────────────
    if (!ruleCode) {
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_row", false);
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_expr", false);
        setContent(_al_bom_item_hint(
            __("Chưa chọn quy tắc cho dòng này. Chọn quy tắc ở ô <b>Quy tắc chọn mã</b> phía trên.")
        ));
        return;
    }

    var token = _al_bom_item_next_token(row);
    setContent('<div style="font-size:12px;color:#94a3b8;">'
        + helper.escapeHtml(__("Đang đọc thông tin quy tắc…")) + "</div>");

    function isStale() {
        return _al_bom_item_token(row) !== token || row.item_rule !== ruleCode;
    }

    function openRule() {
        _al_bom_item_open_rule(ruleCode);
    }

    // ── Giao diện theo quy tắc TỰ KHAI (chặng 3) ─────────────────────
    function paintGlobal(meta) {
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_expr", false);
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_row", false);

        var variable = helper.ruleInputVariable(meta);
        var label = helper.ruleInputLabel(meta);
        var expr = String(row.rule_input_expr || "").trim();
        var html = '<div style="font-size:12px;color:#0f172a;line-height:1.5;">'
            + helper.ruleGlobalSentenceHtml(meta) + "</div>"
            // Điều kiện tra ngay dưới câu quy tắc (chặng 4).
            + '<div data-role="conditions"></div>'
            + '<div style="font-size:11px;color:#64748b;margin-top:2px;">'
            + helper.escapeHtml(__("Quy tắc tự lấy giá trị khi tính — dòng này không cần chọn nguồn."))
            + "</div>"
            + '<div data-role="global-value" style="margin-top:4px;"></div>'
            + _al_bom_item_buttons([viewButton, tryButton])
            + _al_bom_item_advanced_html(helper, expr, false,
                expr
                    ? __("Không còn hiệu lực (quy tắc đã khai Tra theo) — quy tắc tự lấy dữ liệu khi tính.")
                    : "",
                !!expr);

        setContent(html, {
            "view-rule": openRule,
            "try-rule": function () {
                helper.fetchVariableSample(frm, table, variable).then(function (sample) {
                    helper.openRulePreview({
                        rule_code: ruleCode,
                        input_value: sample,
                        input_label: label,
                        rule_name: String(meta.rule_name || ""),
                        // Lượt tính chưa có giá trị ⇒ hộp thoại báo hổ phách
                        // thay vì để người dùng tưởng đã có số (#6/#8).
                        global_value_missing: sample === null || sample === undefined || sample === "",
                        variable_label: label,
                    });
                });
            },
        });
        _al_bom_item_paint_conditions(
            meta, $wrap.find("[data-role='conditions']"), isStale);

        // Lượt tính CHƯA có giá trị biến ⇒ nói ngay trên dòng, ⛔ im lặng
        // (dòng sẽ không ra mã mà người dùng không hiểu vì sao).
        helper.fetchVariableSample(frm, table, variable).then(function (sample) {
            if (isStale()) return;
            if (sample === null || sample === undefined || sample === "") {
                var missingHtml = (typeof helper.variableMissingNoticeHtml === "function")
                    ? helper.variableMissingNoticeHtml(label)
                    : _al_bom_item_hint(__("Chưa có {0} cho lượt tính này — kiểm tra tham số báo giá rồi tính lại.", [helper.escapeHtml(label)]));
                $wrap.find("[data-role='global-value']").html(missingHtml);
            }
        });
    }

    function paintRow(meta) {
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_expr", false);
        // `rule_input_row` là SLUG kỹ thuật, khai `hidden: 1` trong JSON — câu
        // trên dòng ("lấy từ dòng Kính trên") mới là bề mặt người dùng. Đặt
        // lại false mỗi lượt phòng khi meta bị dòng khác bật lên.
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_row", false);

        var variable = helper.ruleInputVariable(meta);
        var label = helper.ruleInputLabel(meta);
        var expr = String(row.rule_input_expr || "").trim();
        var inputVariables = (typeof helper.cachedInputVariables === "function")
            ? helper.cachedInputVariables() : [];
        // Biến do ENGINE TỰ TÍNH ⇒ mọi dòng BOM đều dùng được (#4); thiếu cờ
        // (server cũ / helper cũ) ⇒ `false` = giữ hành vi cũ.
        var computed = (typeof helper.ruleInputVariableComputed === "function")
            && helper.ruleInputVariableComputed(inputVariables, variable) === true;
        var options = helper.buildRuleRowOptions(meta, items, { variables: inputVariables });
        var rowSlug = String(row.rule_input_row || "").trim();
        var refRow = rowSlug ? helper.findRowBySlug(items, rowSlug) : null;
        // Chọn dòng là HÀNH ĐỘNG BẮT BUỘC để dòng ra mã ⇒ nút nổi bật.
        var pickButton = { role: "pick-input", label: __("Chọn dòng lấy dữ liệu"), primary: true };

        var pickHandler = function () {
            _al_bom_item_pick_row(frm, table, cdn, meta);
        };
        var escape = helper.escapeHtml;

        if (!rowSlug) {
            // Nói thẳng HẬU QUẢ (dòng chưa có mã vật tư) + việc cần làm.
            var hint = _al_bom_item_pick_row_hint(escape(label), options.length > 0);
            setContent(_al_bom_item_hint(hint)
                + '<div data-role="conditions"></div>'
                + _al_bom_item_buttons([viewButton, pickButton]), {
                "view-rule": openRule,
                "pick-input": pickHandler,
            });
            _al_bom_item_paint_conditions(
                meta, $wrap.find("[data-role='conditions']"), isStale);
            return;
        }
        if (!refRow || (!computed && !helper.rowSupportsVariable(refRow, variable))) {
            // Dòng nguồn đã chọn nhưng KHÔNG đọc được dữ liệu ⇒ nói RÕ thiếu
            // cái gì + làm gì (⛔ "không khớp" chung chung, ⛔ slug).
            var refName = refRow
                ? _al_bom_item_line_name(helper, refRow, items)
                : "";
            setContent(_al_bom_item_hint(
                _al_bom_item_source_missing_hint(escape(refName), escape(label))
            ) + '<div data-role="conditions"></div>'
                + _al_bom_item_buttons([viewButton, pickButton]), {
                "view-rule": openRule,
                "pick-input": pickHandler,
            });
            _al_bom_item_paint_conditions(
                meta, $wrap.find("[data-role='conditions']"), isStale);
            return;
        }

        var lineName = _al_bom_item_line_name(helper, refRow, items);
        var html = '<div style="font-size:12px;color:#0f172a;line-height:1.5;">'
            + helper.ruleRowSentenceHtml(meta, lineName)
            + '<span data-role="current"></span></div>'
            // Điều kiện tra ngay dưới câu quy tắc (chặng 4).
            + '<div data-role="conditions"></div>'
            + _al_bom_item_buttons([viewButton, tryButton, pickButton])
            + _al_bom_item_advanced_html(helper, expr, false,
                expr
                    ? __("Không còn hiệu lực (quy tắc đã khai Tra theo) — dòng lấy dữ liệu từ dòng nguồn phía trên.")
                    : "",
                !!expr);

        setContent(html, {
            "view-rule": openRule,
            "try-rule": function () {
                helper.fetchOptionSample({
                    value: helper.ruleRowOptionExpr(rowSlug, variable),
                    label: label,
                    sample_value: null,
                }, items).then(function (sample) {
                    helper.openRulePreview({
                        rule_code: ruleCode,
                        input_value: sample,
                        input_label: label,
                        rule_name: String(meta.rule_name || ""),
                    });
                });
            },
            "pick-input": pickHandler,
            "show-expr": function () {
                _al_bom_item_toggle_field(frm, table, cdn, "rule_input_expr", true);
            },
        });
        _al_bom_item_paint_conditions(
            meta, $wrap.find("[data-role='conditions']"), isStale);

        // Giá trị hiện tại + kết quả tra — chỉ khi đọc được giá trị.
        helper.fetchOptionSample({
            value: helper.ruleRowOptionExpr(rowSlug, variable),
            label: label,
            sample_value: null,
        }, items).then(function (sample) {
            if (isStale() || sample === null || sample === undefined || sample === "") return;
            return helper.callPreviewRule(ruleCode, sample).then(function (resp) {
                if (isStale()) return;
                var result = "";
                if (resp && !helper.isPreviewError(resp) && resp.success !== false) {
                    result = helper.resultText(resp);
                }
                $wrap.find("[data-role='current']").html(
                    helper.ruleCurrentValueHtml(sample, result));
            });
        });
    }

    // ── Đường CŨ: quy tắc chưa khai "tra theo" (hoặc site chưa migrate) ──
    function paintLegacy(meta) {
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_row", false);
        _al_bom_item_toggle_field(frm, table, cdn, "rule_input_expr", true);

        var expr = String(row.rule_input_expr || "").trim();
        var ref = helper.parseItemExpr(expr);
        var refRow = ref ? helper.findRowBySlug(items, ref.slug) : null;
        var pickButton = { role: "pick-input", label: __("Chọn dữ liệu tra") };

        var pickHandler = function () {
            _al_bom_item_pick_input(frm, table, cdn);
        };

        // Metadata quy tắc đọc lỗi ⇒ nói việc cần làm, vẫn giữ nhãn chung ở
        // câu dưới (⛔ không hiện mã quy tắc trần).
        var ruleFetchFailed = !meta;
        var ruleName = meta ? String(meta.rule_name || "").trim() : "";

        function paintHint(text) {
            setContent(_al_bom_item_hint(text)
                + _al_bom_item_buttons([viewButton, pickButton]), {
                "view-rule": openRule,
                "pick-input": pickHandler,
            });
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
            // Chọn "Rộng"/"Cao" (hoặc dòng không phải kính) ⇒ engine đọc ra 0
            // ÂM THẦM, dòng không có mã. Báo ngay thay vì để lỗi im lặng.
            paintHint(__("Dữ liệu tra đang chọn không đọc được — quy tắc chỉ đọc được độ dày kính hoặc loại kính của DÒNG KÍNH. Bấm <b>Chọn dữ liệu tra</b> để chọn lại."));
            return;
        }

        var lineName = _al_bom_item_line_name(helper, refRow, items);
        var labelFromField = _al_bom_item_field_label(ref.field);
        var unitFromField = AL_BOM_ITEM_FIELD_UNITS[ref.field] || "";
        var inputLabel = labelFromField + (unitFromField ? " (" + unitFromField + ")" : "");
        var outputLabel = __("mã vật tư");
        if (meta && meta.input_label) inputLabel = helper.ruleInputLabel(meta);
        if (meta && meta.output_label) outputLabel = meta.output_label;
        else if (meta && String(meta.result_type || "").toUpperCase() === "NUMBER") {
            outputLabel = __("số");
        }

        var sentence = __("Dòng này <b>lấy mã tự động</b>: tra <b>{0}</b> của dòng <b>“{1}”</b> → quy tắc <b>“{2}”</b> → ra <b>{3}</b>.", [
            helper.escapeHtml(inputLabel),
            helper.escapeHtml(lineName),
            ruleName
                ? helper.escapeHtml(ruleName)
                : '<span title="' + helper.escapeHtml(ruleCode) + '">'
                    + helper.escapeHtml(__("quy tắc đã chọn")) + "</span>",
            helper.escapeHtml(outputLabel),
        ]);
        var html = '<div style="font-size:12px;color:#0f172a;line-height:1.5;">'
            + sentence + "</div>"
            // Điều kiện tra ngay dưới câu quy tắc (chặng 4).
            + '<div data-role="conditions"></div>';
        if (ruleFetchFailed) {
            html += '<div style="font-size:11px;color:#b45309;margin-top:2px;">'
                + helper.escapeHtml(__("Chưa đọc được tên quy tắc — mở «Xem quy tắc».")) + "</div>";
        }
        html += _al_bom_item_buttons([viewButton, tryButton, pickButton])
            + _al_bom_item_advanced_html(helper, "", false,
                __("Quy tắc này chưa khai «Tra theo» nên dòng dùng biểu thức nguồn dữ liệu ở ô phía trên — đường nâng cao dành cho người kỹ thuật."));

        setContent(html, {
            "view-rule": openRule,
            "try-rule": function () {
                _al_bom_item_try(frm, table, { expr: expr, label: inputLabel, rule_code: ruleCode, rule_name: ruleName, items: items });
            },
            "pick-input": pickHandler,
        });
        _al_bom_item_paint_conditions(
            meta, $wrap.find("[data-role='conditions']"), isStale);
    }

    helper.fetchRuleForCode(ruleCode).then(function (meta) {
        // Dòng đã đổi cấu hình / đã đóng trong lúc chờ ⇒ ⛔ vẽ đè.
        if (isStale()) return;
        var scope = helper.ruleInputScope(meta);
        var variable = helper.ruleInputVariable(meta);
        if (meta && variable && scope === "GLOBAL") paintGlobal(meta);
        else if (meta && variable && scope === "ROW") paintRow(meta);
        else paintLegacy(meta);
    });
}

function _al_bom_item_open_rule(ruleCode) {
    if (!ruleCode) return;
    // Route THUẦN cho `window.open`. ⛔ `frappe.utils.get_form_link(..., true)`
    // trả CHUỖI `<a href="…">…</a>` (tham số 3 là `html`), đưa vào
    // `window.open` sẽ ra URL méo `/desk/…/%3Ca%20href=…`.
    var url = "";
    var helper = window.AlumGlassRuleHelper;
    if (helper && typeof helper.ruleFormRoute === "function") {
        url = helper.ruleFormRoute(ruleCode);
    }
    if (!url) url = "/app/al-rule/" + encodeURIComponent(ruleCode);
    // Mở tab mới — KHÔNG rời form BOM đang sửa dở (mất thay đổi chưa lưu).
    window.open(url, "_blank");
}

/** Đường CŨ: chọn `rule_input_expr` (quy tắc chưa khai "tra theo"). */
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

/** Quy tắc khai biến theo dòng ⇒ chọn DÒNG nguồn (`rule_input_row`). */
function _al_bom_item_pick_row(frm, table, cdn, rule) {
    var row = locals["AL Bom Item"] && locals["AL Bom Item"][cdn];
    window.AlumGlassRuleHelper.openRuleRowPicker({
        frm: frm,
        child_table: table,
        cdn: cdn,
        fieldname: "rule_input_row",
        rule: rule,
        rule_code: row ? row.item_rule : "",
        on_applied: function () {
            _al_bom_item_render(frm, (row && row.doctype) || "AL Bom Item", cdn, 0);
        },
    });
}

/**
 * "Thử tra": lấy giá trị hiện tại của dòng được tham chiếu (nếu có) rồi mở
 * hộp thoại; chưa có số liệu ⇒ hộp thoại cho nhập tay.
 */
function _al_bom_item_try(frm, table, ctx) {
    ctx = ctx || {};
    var helper = window.AlumGlassRuleHelper;
    var option = { value: ctx.expr, sample_value: null, label: ctx.label };
    helper.fetchOptionSample(option, ctx.items || []).then(function (sample) {
        // `input_label` ở đây đã kèm đơn vị ⇒ không truyền thêm `input_unit`.
        helper.openRulePreview({
            rule_code: ctx.rule_code,
            input_value: sample,
            input_label: ctx.label,
            rule_name: ctx.rule_name,
        });
    });
}
