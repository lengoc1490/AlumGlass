#!/usr/bin/env node
/**
 * Test Node thuần cho 2 tệp script DÒNG CON (nạp qua `app_include_js`):
 *   · alumglass/public/js/al_bom_item.js
 *   · alumglass/public/js/al_accessory_item.js
 *
 * KHÔNG cần site, KHÔNG cần npm — chạy:
 *     node alumglass/tests/js/test_rule_row_ui.js
 *
 * Bối cảnh: UX1 chấm CHẶN vòng 2 (2026-11-25c). Các ca dưới phủ:
 *   (1) Câu quy tắc ROW chưa chọn dòng nguồn: nói HẬU QUẢ "chưa có mã vật tư"
 *       + việc cần làm; dòng nguồn chọn rồi mà thiếu số liệu: nêu thiếu gì.
 *   (2) Khối "Nâng cao": biểu thức cũ bị KHOÁ + nhãn "Không còn hiệu lực"
 *       khi quy tắc đã khai Tra theo (⛔ để người dùng sửa ô vô tác dụng).
 *   (3) AL Accessory Item: câu giải thích THƯỜNG TRỰC dưới nút chọn công
 *       thức (2 dạng: đơn giản/có mã quy tắc vs phức tạp), ⛔ mã thô.
 *   (4) KHỐI "ĐIỀU KIỆN TRA" ngay dưới câu quy tắc trên dòng BOM (chặng 4,
 *       Owner 2026-11-25): đọc quy tắc đang chọn ⇒ hiện tối đa 3 điều kiện +
 *       "… và N nữa" + link mở quy tắc; quy tắc TẮT ⇒ cảnh báo trước; không
 *       đọc được quy tắc ⇒ khối trống (⛔ làm vỡ form).
 *
 * Hai tệp kia là script trình duyệt (không export) ⇒ nạp bằng `vm` để hàm
 * cấp cao nhất trở thành biến của sandbox, giống môi trường toàn trang.
 */
"use strict";

const path = require("path");
const vm = require("vm");

// ── `__()` của Desk: hỗ trợ tham số {0} như Frappe ─────────────────────
function translate(text, args) {
    let out = String(text);
    (Array.isArray(args) ? args : []).forEach((value, index) => {
        out = out.split("{" + index + "}").join(String(value));
    });
    return out;
}
global.__ = translate;

const helper = require(path.join(
    __dirname, "..", "..", "public", "js", "rule_helper.js"));

// jQuery tối thiểu — các hàm cấp cao nhất được test KHÔNG chạm DOM; chỉ cần
// đủ để nạp tệp và gắn handler.
function makeJq() {
    const jq = {
        length: 0,
        on() { return jq; }, off() { return jq; },
        find() { return jq; }, first() { return jq; },
        append() { return jq; }, prepend() { return jq; },
        attr() { return ""; }, css() { return jq; }, prop() { return jq; },
        text() { return jq; }, html() { return jq; },
        val() { return ""; }, empty() { return jq; }, toggle() { return jq; },
    };
    return jq;
}

const REGISTERED = {};

const sandbox = {
    __: translate,
    $: makeJq,
    window: null,
    locals: {},
    setTimeout: setTimeout,
    console: console,
    WeakMap: WeakMap,
    frappe: {
        ui: {
            form: {
                on(doctype, handlers) {
                    REGISTERED[doctype] = Object.assign(
                        {}, REGISTERED[doctype] || {}, handlers);
                },
            },
        },
        model: { set_value() {} },
        show_alert() {},
        msgprint() {},
    },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

function loadScript(name) {
    const file = path.join(__dirname, "..", "..", "public", "js", name);
    vm.runInNewContext(require("fs").readFileSync(file, "utf8"), sandbox, {
        filename: file,
    });
}

loadScript("al_bom_item.js");
loadScript("al_accessory_item.js");

// Desk nạp `rule_helper.js` qua `app_include_js` ⇒ script dòng con đọc được
// `window.AlumGlassRuleHelper`. Gán đúng module thật để test khối điều kiện
// chạy trên hàm THẬT (⛔ dựng bản giả rồi tự khen).
sandbox.AlumGlassRuleHelper = helper;

let passed = 0;
const failed = [];

function check(name, fn) {
    try {
        fn();
        passed += 1;
        console.log("  PASS  " + name);
    } catch (err) {
        failed.push(name);
        console.log("  FAIL  " + name);
        console.log("        " + (err && err.message ? err.message : err));
    }
}

function eq(actual, expected, msg) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a !== e) {
        throw new Error((msg || "không khớp")
            + "\n        thực tế: " + a + "\n        mong đợi: " + e);
    }
}

function assert(cond, msg) {
    if (!cond) throw new Error(msg || "assert thất bại");
}

function mustFail(fn, label) {
    try {
        fn();
    } catch (err) {
        return;
    }
    throw new Error("ĐỐI CHỨNG ÂM: bộ kiểm KHÔNG bắt được bản hỏng (" + label + ")");
}

// ═══════════════════════════════════════════════════════════════════════════
// (0) Tệp nạp được + handler lưới đã đăng ký
// ═══════════════════════════════════════════════════════════════════════════
check("(0a) AL Bom Item / AL Accessory Item đăng ký handler lưới", () => {
    assert(REGISTERED["AL Bom Item"], "thiếu handler AL Bom Item");
    assert(REGISTERED["AL Accessory Item"], "thiếu handler AL Accessory Item");
    // Đổi công thức ⇒ câu giải thích thường trực phải vẽ lại (⛔ câu cũ).
    assert(typeof REGISTERED["AL Accessory Item"].qty_formula === "function",
        "thiếu handler qty_formula để cập nhật câu giải thích");
    ["item_rule", "rule_input_row", "rule_input_expr"].forEach((field) => {
        assert(typeof REGISTERED["AL Bom Item"][field] === "function",
            "thiếu handler " + field);
    });
});

// ═══════════════════════════════════════════════════════════════════════════
// (1) Câu quy tắc ROW — hậu quả + việc cần làm, ⛔ mã biến/slug
// ═══════════════════════════════════════════════════════════════════════════
function testPickRowHint(api) {
    const withOptions = api._al_bom_item_pick_row_hint("Độ dày kính (mm)", true);
    assert(withOptions.indexOf("chưa có mã vật tư") !== -1,
        "phải nói HẬU QUẢ 'chưa có mã vật tư': " + withOptions);
    assert(withOptions.indexOf("Chọn dòng lấy dữ liệu") !== -1,
        "phải chỉ việc cần làm: " + withOptions);
    assert(withOptions.indexOf("Độ dày kính (mm)") !== -1, "phải kèm nhãn biến");

    const noOptions = api._al_bom_item_pick_row_hint("Độ dày kính (mm)", false);
    assert(noOptions.indexOf("chưa có dòng nào") !== -1,
        "bộ chưa có dòng phù hợp ⇒ nói đúng trạng thái: " + noOptions);
    assert(noOptions.indexOf("nhập số liệu") !== -1,
        "phải chỉ việc cần làm: " + noOptions);
}

check("(1a) câu chưa chọn dòng nguồn — hậu quả + hành động", () => {
    testPickRowHint(sandbox);
});

check("ĐỐI CHỨNG ÂM — (1a) câu im lặng 'Chưa chọn dữ liệu.'", () => {
    // Bản hỏng: câu chung chung, ⛔ nói hậu quả ⇒ người dùng không biết
    // dòng sẽ không ra mã.
    const broken = {
        _al_bom_item_pick_row_hint() { return __("Chưa chọn dữ liệu."); },
    };
    mustFail(() => testPickRowHint(broken), "câu không nêu hậu quả");
});

function testSourceMissingHint(api) {
    const text = api._al_bom_item_source_missing_hint(
        "Kính trên", "Độ dày kính (mm)");
    assert(text.indexOf("Kính trên") !== -1, "phải nêu TÊN dòng nguồn");
    assert(text.indexOf("Độ dày kính (mm)") !== -1, "phải nêu thiếu CÁI GÌ");
    assert(text.indexOf("Chọn dòng lấy dữ liệu") !== -1, "phải chỉ việc cần làm");
    assert(text.indexOf("không ra mã vật tư") !== -1, "phải nói hậu quả");
    assert(text.indexOf("<b>“Kính trên”</b>") !== -1, "tên dòng phải được làm nổi");

    const gone = api._al_bom_item_source_missing_hint("", "Độ dày kính (mm)");
    assert(gone.indexOf("không còn trong bộ này") !== -1,
        "dòng nguồn đã bị xoá ⇒ nói đúng trạng thái: " + gone);
    assert(gone.indexOf("Chọn dòng lấy dữ liệu") !== -1, "vẫn phải có hành động");
}

check("(1b) dòng nguồn thiếu số liệu — thiếu gì + làm gì", () => {
    testSourceMissingHint(sandbox);
});

check("ĐỐI CHỨNG ÂM — (1b) câu 'không khớp' chung chung", () => {
    const broken = {
        _al_bom_item_source_missing_hint() { return __("Dữ liệu không khớp."); },
    };
    mustFail(() => testSourceMissingHint(broken), "câu không nêu thiếu gì");
});

// ── Câu quy tắc ⛔ mã biến (dùng helper thật của rule_helper) ────────────
check("(1c) câu quy tắc (GLOBAL/ROW) ⛔ chứa mã biến `(H_mm)`", () => {
    const global = helper.ruleGlobalSentenceHtml({
        input_variable: "H_mm", input_scope: "GLOBAL",
        input_label: "Chiều cao", input_unit: "mm",
    });
    assert(global.indexOf("H_mm") === -1, "GLOBAL lộ mã biến: " + global);
    assert(global.indexOf("Chiều cao (mm)") !== -1, "phải hiện nhãn: " + global);

    const row = helper.ruleRowSentenceHtml({
        input_variable: "total_thick_mm", input_scope: "ROW",
        input_label: "Độ dày kính", input_unit: "mm",
    }, "Kính trên");
    assert(row.indexOf("total_thick_mm") === -1, "ROW lộ mã biến: " + row);

    // Quy tắc chưa có nhãn ⇒ "dữ liệu quy tắc đọc", ⛔ mã biến.
    const unlabeled = helper.ruleGlobalSentenceHtml({
        input_variable: "H_mm", input_scope: "GLOBAL",
    });
    assert(unlabeled.indexOf("H_mm") === -1, "thiếu nhãn ⇒ lộ mã: " + unlabeled);
    assert(unlabeled.indexOf("dữ liệu quy tắc đọc") !== -1, unlabeled);
});

check("ĐỐI CHỨNG ÂM — (1c) câu ghép '(<var>)'", () => {
    const broken = {
        ruleGlobalSentenceHtml(rule) {
            return __("Quy tắc tự lấy") + " <b>" + helper.ruleInputLabel(rule)
                + "</b> (" + String(rule.input_variable || "") + ")";
        },
    };
    mustFail(() => {
        const global = broken.ruleGlobalSentenceHtml({
            input_variable: "H_mm", input_label: "Chiều cao", input_unit: "mm",
        });
        assert(global.indexOf("H_mm") === -1, "vẫn lộ mã biến");
    }, "ghép mã biến vào câu");
});

// ═══════════════════════════════════════════════════════════════════════════
// (2) Khối "Nâng cao" — biểu thức cũ KHÔNG CÒN HIỆU LỰC
// ═══════════════════════════════════════════════════════════════════════════
function testAdvancedExpired(api) {
    const html = api._al_bom_item_advanced_html(
        helper, "items.kinh_tren.width", false,
        "Không còn hiệu lực (quy tắc đã khai Tra theo) — dòng lấy dữ liệu từ dòng nguồn phía trên.",
        true);
    assert(html.indexOf("Không còn hiệu lực (quy tắc đã khai Tra theo)") !== -1,
        "thiếu nhãn 'Không còn hiệu lực': " + html);
    assert(html.indexOf("Biểu thức cũ (chỉ để đối chiếu)") !== -1,
        "biểu thức cũ phải là read-only đối chiếu");
    assert(html.indexOf("items.kinh_tren.width") !== -1,
        "vẫn giữ chuỗi cũ để đối chiếu");
    assert(html.indexOf("Hiện ô biểu thức") === -1,
        "⛔ hiện nút sửa ô vô tác dụng");
    assert(html.indexOf("#b45309") !== -1, "phải tô hổ phách");

    // Đường LEGACY (quy tắc chưa khai Tra theo) vẫn cho sửa như cũ.
    const legacy = api._al_bom_item_advanced_html(helper, "", false);
    assert(legacy.indexOf("Không còn hiệu lực") === -1, "legacy ⛔ bị đánh dấu hết hiệu lực");
}

check("(2a) biểu thức cũ bị khoá + nhãn 'Không còn hiệu lực'", () => {
    testAdvancedExpired(sandbox);
});

check("ĐỐI CHỨNG ÂM — (2a) vẫn hiện nút 'Hiện ô biểu thức'", () => {
    const broken = {
        _al_bom_item_advanced_html(h, expr, showFieldButton, note, warn) {
            return sandbox._al_bom_item_advanced_html(h, expr, true, note, warn);
        },
    };
    mustFail(() => testAdvancedExpired(broken), "để người dùng sửa ô vô tác dụng");
});

// ═══════════════════════════════════════════════════════════════════════════
// (3) AL Accessory Item — câu giải thích THƯỜNG TRỰC dưới nút
// ═══════════════════════════════════════════════════════════════════════════
function desc_text(html) {
    // Chỉ lấy phần câu trong div mô tả (bỏ nút + attribute chứa mã).
    const start = String(html).indexOf('class="al-formula-desc"');
    if (start === -1) return "";
    const open = String(html).indexOf(">", start) + 1;
    const end = String(html).indexOf("</div>", open);
    return String(html).slice(open, end);
}

function testAccessoryDesc(api) {
    const simple = api._al_accessory_item_formula_html(
        helper, "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel");
    eq(desc_text(simple), "Số lượng = kết quả tra quy tắc theo chiều cao × số cánh");
    assert(desc_text(simple).indexOf("RULE-") === -1, "câu ⛔ chứa mã quy tắc");
    assert(simple.indexOf('data-role="open-rule"') !== -1, "phải có nút Xem quy tắc");
    assert(simple.indexOf('data-rule-code="RULE-BANLE-QTY"') !== -1,
        "nút mang mã để mở form quy tắc");

    const panels = api._al_accessory_item_formula_html(helper, "2 * n_panel");
    eq(desc_text(panels), "Số lượng = 2 × số cánh");
    assert(panels.indexOf('data-role="open-rule"') === -1,
        "công thức không có mã quy tắc ⇒ ⛔ nút Xem quy tắc");

    const fixed = api._al_accessory_item_formula_html(helper, "4");
    eq(desc_text(fixed), "Số lượng cố định: 4");

    const complex = api._al_accessory_item_formula_html(helper, "H_mm * 2");
    eq(desc_text(complex), "Công thức tự nhập",
        "công thức lạ ⇒ câu trung tính, ⛔ đoán số");
    assert(complex.indexOf('data-role="open-rule"') === -1, "⛔ nút khi chưa đọc được mã");
    assert(desc_text(complex).indexOf("H_mm") === -1, "⛔ mã biến trong câu");

    const empty = api._al_accessory_item_formula_html(helper, "");
    eq(desc_text(empty), "Chưa đặt công thức số lượng.");
}

check("(3a) Accessory — câu thường trực: quy tắc / preset / cố định / phức tạp", () => {
    testAccessoryDesc(sandbox);
});

check("ĐỐI CHỨNG ÂM — (3a) in nguyên công thức (lộ mã biến/mã quy tắc)", () => {
    const broken = {
        _al_accessory_item_formula_html(h, value) {
            return '<div class="al-formula-desc">'
                + h.escapeHtml(String(value || "")) + "</div>";
        },
    };
    mustFail(() => testAccessoryDesc(broken), "lộ mã thô trong câu");
});

// ═══════════════════════════════════════════════════════════════════════════
// (4) KHỐI "ĐIỀU KIỆN TRA" ngay dưới câu quy tắc (chặng 4)
// ═══════════════════════════════════════════════════════════════════════════
const CONDITION_RULE = {
    name: "RULE-NEP-DAY",
    rule_code: "RULE-NEP-DAY",
    rule_type: "THRESHOLD",
    result_type: "ITEM",
    input_label: "Độ dày kính",
    input_unit: "mm",
    is_active: 1,
    threshold_rows: [
        { from_value: 0, to_value: 10, result_item: "N10", result_item_name: "Nẹp nhôm 10" },
        { from_value: 10, to_value: 20, result_item: "N20" },
        { from_value: 20, to_value: 30, result_item: "N30" },
        { from_value: 30, to_value: 40, result_item: "N40" },
    ],
};

/** Ô HTML giả — đủ để hàm vẽ ghi nội dung và báo "đã xoá". */
function fakeSlot() {
    const slot = { length: 1, htmlText: "", cleared: false };
    slot.empty = () => { slot.cleared = true; slot.htmlText = ""; return slot; };
    slot.html = (html) => { slot.htmlText = String(html); return slot; };
    return slot;
}

function testRowConditions(api) {
    const slot = fakeSlot();
    api._al_bom_item_paint_conditions(CONDITION_RULE, slot, () => false);

    assert(slot.htmlText.indexOf("Tra theo: <b>Độ dày kính</b> · 4 điều kiện:") !== -1,
        "thiếu câu mở đầu từ metadata quy tắc: " + slot.htmlText);
    assert(slot.htmlText.indexOf("0–10 mm → Nẹp nhôm 10 (N10)") !== -1,
        "thiếu điều kiện đầu: " + slot.htmlText);
    eq((slot.htmlText.match(/<li>/g) || []).length, 3,
        "chỉ hiện tối đa 3 điều kiện");
    assert(slot.htmlText.indexOf("… và 1 nữa") !== -1,
        "thiếu phần còn lại: " + slot.htmlText);
    assert(slot.htmlText.indexOf('href="/app/al-rule/RULE-NEP-DAY"') !== -1,
        "thiếu link mở quy tắc: " + slot.htmlText);
    assert(slot.htmlText.indexOf("Quy tắc đang tắt") === -1,
        "quy tắc đang bật ⇒ ⛔ cảnh báo tắt");
    // ⛔ mã quy tắc ngoài URL, ⛔ tên field kỹ thuật.
    assert(slot.htmlText.indexOf("threshold_rows") === -1, "lộ tên field");
    assert(slot.htmlText.indexOf("RULE-NEP-DAY") === slot.htmlText.lastIndexOf("RULE-NEP-DAY"),
        "mã quy tắc chỉ được nằm trong URL");

    // Quy tắc TẮT: cảnh báo TRƯỚC, ⛔ trình bày như đang dùng được.
    const off = fakeSlot();
    api._al_bom_item_paint_conditions(
        Object.assign({}, CONDITION_RULE, { is_active: 0 }), off, () => false);
    assert(off.htmlText.indexOf("Quy tắc đang tắt nên các điều kiện dưới đây chưa áp dụng.") !== -1,
        "quy tắc tắt phải cảnh báo: " + off.htmlText);
    assert(off.htmlText.indexOf("Quy tắc đang tắt") < off.htmlText.indexOf("0–10 mm"),
        "cảnh báo phải đứng TRƯỚC danh sách điều kiện");

    // Không đọc được quy tắc (lỗi / không quyền) ⇒ khối trống, ⛔ vỡ form.
    const empty = fakeSlot();
    api._al_bom_item_paint_conditions(null, empty, () => false);
    assert(empty.cleared && empty.htmlText === "", "không đọc được quy tắc ⇒ xoá khối");

    // Quy tắc NUMBER (bản lề) ⇒ hiện ĐÚNG nhãn/đơn vị của nó (⛔ hardcode
    // "Độ dày kính").
    const hinge = fakeSlot();
    api._al_bom_item_paint_conditions({
        name: "RULE-BANLE",
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        input_label: "Chiều cao",
        input_unit: "cm",
        is_active: 1,
        threshold_rows: [{ from_value: 0, to_value: 100, result_value: 2 }],
    }, hinge, () => false);
    assert(hinge.htmlText.indexOf("Tra theo: <b>Chiều cao</b> · 1 điều kiện:") !== -1,
        "nhãn phải lấy từ quy tắc: " + hinge.htmlText);
    assert(hinge.htmlText.indexOf("0–100 cm → 2") !== -1,
        "đơn vị + kết quả số của quy tắc: " + hinge.htmlText);
    assert(hinge.htmlText.indexOf("Độ dày kính") === -1,
        "⛔ hardcode 'Độ dày kính'");
}

check("(4a) khối điều kiện dưới câu quy tắc — 3 dòng đầu, link, tắt, trống", () => {
    testRowConditions(sandbox);
});

check("ĐỐI CHỨNG ÂM — (4a) in giá trị thô, không giới hạn, không link", () => {
    const broken = {
        _al_bom_item_paint_conditions(meta, $slot) {
            const rows = (meta && meta.threshold_rows) || [];
            $slot.html("Điều kiện: " + rows.map((row) => row.from_value + "-"
                + row.to_value + " -> " + row.result_item).join(", "));
        },
    };
    mustFail(() => testRowConditions(broken), "khối thô, ⛔ cắt 3, ⛔ link, ⛔ cảnh báo tắt");
});

check("(4b) khối điều kiện nằm NGAY DƯỚI câu quy tắc ở cả 3 nhánh vẽ", () => {
    const source = require("fs").readFileSync(
        path.join(__dirname, "..", "..", "public", "js", "al_bom_item.js"), "utf8");
    const names = ["function paintGlobal", "function paintRow", "function paintLegacy"];
    names.forEach((name, index) => {
        const start = source.indexOf(name);
        assert(start !== -1, "thiếu nhánh vẽ " + name);
        // Biên cuối = nhánh vẽ KẾ TIẾP (⛔ cắt ở "function paintHint" lồng bên trong).
        const ends = names.slice(index + 1)
            .map((other) => source.indexOf(other))
            .filter((position) => position > start);
        const end = ends.length ? Math.min.apply(null, ends) : source.length;
        const body = source.slice(start, end);
        assert(body.indexOf('data-role="conditions"') !== -1,
            name + " thiếu ô điều kiện");
        assert(body.indexOf("_al_bom_item_paint_conditions(") !== -1,
            name + " chưa vẽ khối điều kiện");
    });
});

// ═══════════════════════════════════════════════════════════════════════════
// (5) KHỐI ĐIỀU KIỆN trên dòng BOM — tiêu đề GỌN (UX1 chấm vòng 3)
//     Câu quy tắc ngay trên đã nói "Quy tắc tra theo <nhãn>"; khối dưới phải
//     dùng dạng "compact", ⛔ lặp lại y nguyên câu đó.
// ═══════════════════════════════════════════════════════════════════════════
function testCompactHeading(api) {
    const slot = fakeSlot();
    api._al_bom_item_paint_conditions(CONDITION_RULE, slot, () => false);
    const html = slot.htmlText;
    assert(html.indexOf('class="al-rule-conditions-head">Tra theo: <b>') !== -1,
        "thiếu tiêu đề gọn 'Tra theo: <nhãn>': " + html);
    assert(html.indexOf("Quy tắc tra theo") === -1,
        "tiêu đề lặp lại đúng câu quy tắc phía trên: " + html);
    // Gọn nhưng ⛔ mất thông tin: vẫn số điều kiện, danh sách, link.
    assert(html.indexOf("· 4 điều kiện:") !== -1, "thiếu số điều kiện trong tiêu đề");
    eq((html.match(/<li>/g) || []).length, 3, "vẫn hiện tối đa 3 điều kiện");
    assert(html.indexOf('href="/app/al-rule/RULE-NEP-DAY"') !== -1,
        "vẫn phải có link mở quy tắc");
}

check("(5a) khối điều kiện dùng tiêu đề gọn, ⛔ lặp câu quy tắc", () => {
    testCompactHeading(sandbox);
});

check("ĐỐI CHỨNG ÂM — (5a) heading 'full' lặp câu quy tắc phải bị bắt đỏ", () => {
    const broken = {
        _al_bom_item_paint_conditions(meta, $slot) {
            // Bản hỏng: dựng lại đúng dạng "full" cũ (lặp câu quy tắc).
            $slot.html(sandbox.AlumGlassRuleHelper
                .ruleConditionPreviewHtml(meta, { max: 3 }));
        },
    };
    mustFail(() => testCompactHeading(broken), "heading 'full' lặp câu quy tắc");
});

// ═══════════════════════════════════════════════════════════════════════════
console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed
    + "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
