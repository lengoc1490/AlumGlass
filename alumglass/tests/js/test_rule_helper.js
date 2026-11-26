#!/usr/bin/env node
/**
 * Test Node thuần cho alumglass/public/js/rule_helper.js
 *
 * KHÔNG cần site, KHÔNG cần npm/cài package — chạy:
 *     node alumglass/tests/js/test_rule_helper.js
 *
 * Bối cảnh: thiết kế `docs/design/tra-cuu-quy-tac-de-hieu.md` (chốt
 * 2026-11-25) đổi bước tra nẹp/keo/bản lề từ "gõ tay mã quy tắc" thành
 * "chọn bằng tên". Tệp này phủ phần THUẦN của helper:
 *   1. buildSnippet        — dựng `lookup_rule('MÃ', input) [* multiplier]`
 *   2. buildPresetSnippet  — 4 lựa chọn không-code (số cố định / số cánh / 2×)
 *   3. filterNumberRules   — chỉ quy tắc trả SỐ, đang bật
 *   4. buildInputOptions   — danh sách "dữ liệu đem tra" có nhãn người đọc
 *   5. resolveItemValue    — đọc giá trị dòng được tham chiếu (alias độ dày)
 *   6. Câu chữ kết quả thử + nhãn quy tắc
 *   7. ĐIỀU KIỆN TRA của quy tắc (chặng 4 — Owner 2026-11-25 "phải chuyển
 *      danh sách các điều kiện công thức tra ra kính lên gần chỗ rule"):
 *      ruleConditionLines · ruleConditionSummary · ruleConditionPreviewHtml ·
 *      ruleConditionItemCodes + đối chiếu bản dự phòng khe hở/chồng lấn với
 *      `window.AlumGlassRuleConditions` (al_rule.js).
 *
 * Mỗi nhóm có ĐỐI CHỨNG ÂM: dựng một bản CỐ TÌNH HỎNG, chạy đúng bộ kiểm
 * của nhóm đó, và đòi bộ kiểm PHẢI báo đỏ. Nhờ vậy "xanh" ở trên là xanh
 * thật, không phải test không bắt được lỗi.
 */
"use strict";

const path = require("path");

// `__()` của Desk — map 1:1 để chuỗi test khớp chuỗi hiển thị.
global.__ = function (text) { return String(text); };

const helper = require(path.join(
    __dirname, "..", "..", "public", "js", "rule_helper.js"));

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

function assert(condition, msg) {
    if (!condition) throw new Error(msg || "assert thất bại");
}

/** Bản CỐ TÌNH HỎNG phải làm bộ kiểm ném lỗi — nếu không, test đang vô dụng. */
function mustFail(fn, label) {
    try {
        fn();
    } catch (err) {
        return;
    }
    throw new Error("ĐỐI CHỨNG ÂM: bộ kiểm KHÔNG bắt được bản hỏng (" + label + ")");
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. buildSnippet
// ═══════════════════════════════════════════════════════════════════════════
function testBuildSnippet(api) {
    eq(api.buildSnippet({ code: "RULE-A", input: "H_mm" }),
        "lookup_rule('RULE-A', H_mm)", "dạng cơ bản");

    eq(api.buildSnippet({ code: " RULE-A ", input: " H_mm " }),
        "lookup_rule('RULE-A', H_mm)", "phải trim code + input");

    eq(api.buildSnippet({ code: "RULE-A", input: "H_mm", multiplier: " n_panel " }),
        "lookup_rule('RULE-A', H_mm) * n_panel", "nhân với biến");

    eq(api.buildSnippet({ code: "RULE-A", input: "H_mm", multiplier: "  " }),
        "lookup_rule('RULE-A', H_mm)", "multiplier rỗng ⇒ không nhân");

    eq(api.buildSnippet({ code: "O'BRIEN", input: "H_mm" }),
        "lookup_rule('O\\'BRIEN', H_mm)", "phải escape dấu nháy đơn");

    eq(api.buildSnippet({ code: "A\\B", input: "H_mm" }),
        "lookup_rule('A\\\\B', H_mm)", "phải escape dấu gạch chéo ngược");

    eq(api.buildSnippet({ code: "", input: "H_mm" }), null, "thiếu mã ⇒ null");
    eq(api.buildSnippet({ code: "RULE-A" }), null, "thiếu input ⇒ null");
    eq(api.buildSnippet({ code: "  ", input: "   " }), null, "toàn khoảng trắng ⇒ null");
    eq(api.buildSnippet({}), null, "không tham số ⇒ null");
    eq(api.buildSnippet(), null, "undefined ⇒ null");
}

check("buildSnippet — đủ / thiếu / thoát nháy / khoảng trắng / nhân", () => {
    testBuildSnippet(helper);
});

check("ĐỐI CHỨNG ÂM — buildSnippet", () => {
    // Bản hỏng: không trim, không escape nháy, không trim multiplier.
    const broken = {
        buildSnippet(o) {
            o = o || {};
            const code = String(o.code == null ? "" : o.code);
            const input = String(o.input == null ? "" : o.input);
            if (!code || !input) return null;
            const core = "lookup_rule('" + code + "', " + input + ")";
            return o.multiplier ? core + " * " + o.multiplier : core;
        },
    };
    mustFail(() => testBuildSnippet(broken), "không trim/escape");
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. buildPresetSnippet — 4 lựa chọn không-code
// ═══════════════════════════════════════════════════════════════════════════
function testPreset(api) {
    eq(api.buildPresetSnippet({ preset: "panels" }), "n_panel");
    eq(api.buildPresetSnippet({ preset: "panels2" }), "2 * n_panel");
    eq(api.buildPresetSnippet({ preset: "fixed", value: "4" }), "4");
    eq(api.buildPresetSnippet({ preset: "fixed", value: " 2,5 " }), "2.5",
        "dấu phẩy thập phân của người Việt");
    eq(api.buildPresetSnippet({ preset: "fixed", value: "0" }), "0");
    eq(api.buildPresetSnippet({ preset: "fixed", value: "4.0" }), "4");
    eq(api.buildPresetSnippet({ preset: "fixed", value: "" }), null);
    eq(api.buildPresetSnippet({ preset: "fixed" }), null);
    eq(api.buildPresetSnippet({ preset: "fixed", value: "bốn" }), null, "chữ ⇒ null");
    eq(api.buildPresetSnippet({ preset: "fixed", value: "4 cái" }), null);
    eq(api.buildPresetSnippet({ preset: "rule" }), null, "nhánh rule dùng buildSnippet");
    eq(api.buildPresetSnippet({}), null);

    const defs = api.presetDefinitions();
    eq(defs.map((d) => d.kind), ["fixed", "panels", "panels2", "rule"],
        "4 lựa chọn đúng thứ tự");
    defs.forEach((d) => {
        assert(d.label && d.desc && d.example, "thiếu chữ giải thích: " + d.kind);
    });
    const ruleDef = defs.filter((d) => d.kind === "rule")[0];
    assert(ruleDef.desc.indexOf("hoặc mã") === -1,
        "preset 'Tra quy tắc' chỉ trả SỐ ⇒ ⛔ hứa 'hoặc mã'");
    assert(ruleDef.desc.indexOf("số lượng") !== -1, "phải nói rõ ra số lượng");
}

check("buildPresetSnippet — đủ 4 preset / thiếu field / số hợp lệ", () => {
    testPreset(helper);
});

check("ĐỐI CHỨNG ÂM — buildPresetSnippet", () => {
    // Bản hỏng: trả nguyên chuỗi người dùng gõ (không kiểm số).
    const broken = {
        buildPresetSnippet(o) {
            o = o || {};
            if (o.preset === "panels") return "n_panel";
            if (o.preset === "panels2") return "2 * n_panel";
            if (o.preset === "fixed") return String(o.value || "").trim() || null;
            return null;
        },
        presetDefinitions: helper.presetDefinitions,
    };
    mustFail(() => testPreset(broken), "nhận cả chữ vào ô số lượng");
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. filterNumberRules
// ═══════════════════════════════════════════════════════════════════════════
function testFilter(api) {
    const rows = [
        { rule_code: "A", result_type: "NUMBER", is_active: 1 },
        { rule_code: "B", result_type: "ITEM", is_active: 1 },
        { rule_code: "C", result_type: "NUMBER", is_active: 0 },
        { rule_code: "D", result_type: "NUMBER" },          // thiếu cờ ⇒ coi như bật
        { rule_code: "E", result_type: "NUMBER", is_active: "0" },
        { rule_code: "F", result_type: "number", is_active: 1 },
        { rule_code: "G", result_type: "NUMBER", is_active: false },
    ];
    eq(api.filterNumberRules(rows).map((r) => r.rule_code), ["A", "D", "F"],
        "chỉ NUMBER và đang bật");
    eq(rows.length, 7, "⛔ được sửa mảng đầu vào");
    eq(api.filterNumberRules(null), []);
    eq(api.filterNumberRules(undefined), []);
    assert(api.isRuleActive({}) === true, "thiếu is_active ⇒ bật");
    assert(api.isRuleActive({ is_active: 1 }) === true);
    assert(api.isRuleActive({ is_active: "0" }) === false);
    assert(api.isRuleActive({ is_active: "false" }) === false);
}

check("filterNumberRules — NUMBER + đang bật, không sửa mảng gốc", () => {
    testFilter(helper);
});

check("ĐỐI CHỨNG ÂM — filterNumberRules", () => {
    // Bản hỏng: chỉ lọc result_type, bỏ qua is_active.
    const broken = {
        filterNumberRules(rows) {
            return (Array.isArray(rows) ? rows : []).filter(
                (r) => r && String(r.result_type).toUpperCase() === "NUMBER");
        },
        isRuleActive: helper.isRuleActive,
    };
    mustFail(() => testFilter(broken), "quên lọc quy tắc đang tắt");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. buildInputOptions — dòng vật tư × field, biến chứng từ
// ═══════════════════════════════════════════════════════════════════════════
function makeItems() {
    return [
        {
            slug: "kinh_tren", line_name: "Kính trên",
            default_glass_master: "KINH-LOWE-24",
            total_thick_mm: 10, glass_type: "LOWE",
            width: 1200, height: 2000,
        },
        {
            slug: "nep_tren", line_name: "Nẹp trên",
            width: "W_mm / n_panel", height: 0,
        },
        {
            // Không khai kính mặc định, tên KHÔNG dấu — vẫn phải nhận là dòng kính.
            slug: "kinh_canh", line_name: "Kinh canh",
            glass_thick: 8,
        },
        {
            slug: "canh_doc", line_name: "Cạnh đứng", category: "Nhôm",
            width: 100,
        },
    ];
}

function makeVariables() {
    return [
        { name: "H_mm", label: "Chiều cao", value: 3200 },
        { name: "n_panel", label: "Số cánh", value: 2 },
        { name: "H_mm", label: "Chiều cao (trùng)", value: 999 },
        { name: "aluminum_color", label: "Màu nhôm", value: "WHITE" },
        { name: "", label: "Không tên", value: 1 },
    ];
}

function byValue(options, value) {
    return options.filter((o) => o.value === value)[0] || null;
}

function testOptions(api) {
    const options = api.buildInputOptions({
        items: makeItems(), variables: makeVariables(),
    });

    // ── Dòng kính: có độ dày + loại kính ──
    const thick = byValue(options, "items.kinh_tren.total_thick_mm");
    assert(thick, "thiếu option độ dày kính của dòng kính");
    eq(thick.label, "Kính trên — Độ dày kính (mm)");
    eq(thick.group, "Dòng trong BOM");
    eq(thick.sample_value, 10);

    const type = byValue(options, "items.kinh_tren.glass_type");
    assert(type, "thiếu option loại kính");
    eq(type.label, "Kính trên — Loại kính");
    eq(type.sample_value, "LOWE");

    const width = byValue(options, "items.kinh_tren.width");
    eq(width.label, "Kính trên — Rộng (mm)");
    eq(width.sample_value, 1200);
    assert(byValue(options, "items.kinh_tren.height"), "thiếu option Cao");

    // ── Dòng KHÔNG phải kính: ⛔ không có độ dày/loại kính ──
    eq(byValue(options, "items.nep_tren.total_thick_mm"), null,
        "dòng nẹp ⛔ được có option độ dày kính");
    eq(byValue(options, "items.nep_tren.glass_type"), null,
        "dòng nẹp ⛔ được có option loại kính");
    const nepWidth = byValue(options, "items.nep_tren.width");
    assert(nepWidth, "dòng nẹp vẫn phải có Rộng");
    eq(nepWidth.sample_value, null, "công thức chữ ⇒ không làm mẫu thử");
    eq(nepWidth.label, "Nẹp trên — Rộng (mm)");

    // ── Nhận dòng kính theo tên không dấu + alias glass_thick ──
    const unaccented = byValue(options, "items.kinh_canh.total_thick_mm");
    assert(unaccented, "tên 'Kinh canh' (không dấu) phải nhận là dòng kính");
    eq(unaccented.sample_value, 8, "đọc alias glass_thick");

    // ── Biến chứng từ: nhãn + tên biến, không trùng ──
    const height = byValue(options, "H_mm");
    assert(height, "thiếu biến H_mm");
    eq(height.label, "Chiều cao (H_mm)");
    eq(height.group, "Biến của chứng từ");
    eq(height.sample_value, 3200);
    eq(options.filter((o) => o.value === "H_mm").length, 1, "biến trùng tên chỉ 1 option");
    eq(byValue(options, "n_panel").label, "Số cánh (n_panel)");
    eq(byValue(options, ""), null, "biến không tên bị bỏ");

    // ── Hợp đồng option + không trùng giá trị ──
    options.forEach((o) => {
        assert(Object.prototype.hasOwnProperty.call(o, "value"), "option thiếu value");
        assert(Object.prototype.hasOwnProperty.call(o, "label"), "option thiếu label");
        assert(Object.prototype.hasOwnProperty.call(o, "group"), "option thiếu group");
        assert(Object.prototype.hasOwnProperty.call(o, "sample_value"), "option thiếu sample_value");
    });
    const values = options.map((o) => o.value);
    eq(values.length, new Set(values).size, "danh sách option bị trùng value");

    // ── buildVariableOptions: chỉ biến (dùng cho ô "Nhân với") ──
    const varsOnly = api.buildVariableOptions({ items: makeItems(), variables: makeVariables() });
    assert(varsOnly.length > 0, "thiếu option biến");
    assert(varsOnly.every((o) => o.value.indexOf("items.") !== 0),
        "ô Nhân với ⛔ được chứa dòng vật tư");

    // ── item_fields: bảng phụ kiện KHÔNG có cột Rộng/Cao ──
    const accessoryRows = [
        { slug: "ban_le", item_code: "BAN-LE-01" },
        { slug: "keo", item_code: "KEO-01", width: 10, height: 20 },
    ];
    const accOptions = api.buildInputOptions({
        items: accessoryRows, variables: makeVariables(), item_fields: [],
    });
    assert(accOptions.every((o) => o.value.indexOf("items.") !== 0),
        "bảng phụ kiện (item_fields rỗng) ⛔ được mời bất kỳ cột dòng nào");
    assert(byValue(accOptions, "H_mm"), "vẫn phải có biến chứng từ H_mm");
    assert(byValue(accOptions, "n_panel"), "vẫn phải có biến chứng từ n_panel");

    const bomOptions = api.buildInputOptions({
        items: makeItems(), variables: [], item_fields: ["width", "height"],
    });
    assert(byValue(bomOptions, "items.kinh_tren.width"), "item_fields phải mời Rộng");
    assert(byValue(bomOptions, "items.kinh_tren.height"), "item_fields phải mời Cao");
    // Mặc định (thiếu item_fields) giữ hành vi cũ để không phá nơi gọi khác.
    const defaultOptions = api.buildInputOptions({ items: makeItems(), variables: [] });
    assert(byValue(defaultOptions, "items.kinh_tren.width"), "mặc định vẫn mời Rộng");

    // qty tự tham chiếu ⇒ TUYỆT ĐỐI không mời kể cả khi caller xin.
    const withQty = api.buildInputOptions({
        items: makeItems(), variables: [], item_fields: ["width", "qty"],
    });
    assert(withQty.every((o) => !/\.qty$/.test(o.value)), "⛔ được mời qty");
}

check("buildInputOptions — dòng kính vs không kính, biến, nhãn, không trùng", () => {
    testOptions(helper);
});

check("ĐỐI CHỨNG ÂM — buildInputOptions", () => {
    // Bản hỏng: sinh độ dày/loại kính cho MỌI dòng (bỏ điều kiện dòng kính).
    const broken = Object.assign({}, helper, {
        buildInputOptions(input) {
            input = input || {};
            const items = Array.isArray(input.items) ? input.items : [];
            const out = [];
            const seen = {};
            const push = (value, label, group, sample) => {
                if (!value || seen[value]) return;
                seen[value] = true;
                out.push({ value, label, group, sample_value: sample == null ? null : sample });
            };
            items.forEach((row) => {
                if (!row || !row.slug) return;
                const line = row.line_name || row.slug;
                push("items." + row.slug + ".total_thick_mm",
                    line + " — Độ dày kính (mm)", "Dòng trong BOM",
                    row.total_thick_mm == null ? null : row.total_thick_mm);
                push("items." + row.slug + ".glass_type",
                    line + " — Loại kính", "Dòng trong BOM", row.glass_type || null);
            });
            return out;
        },
    });
    mustFail(() => testOptions(broken), "sinh độ dày cho cả dòng nẹp");
});

// ĐỐI CHỨNG ÂM riêng cho `item_fields` — đúng lỗi UX1 chấm chặn:
// bảng phụ kiện bị mời Rộng/Cao ⇒ chèn `items.ban_le.height` ⇒ Lưu báo
// "Biến 'ban_le__height' chưa được khai báo".
function testAccessoryFields(api) {
    const options = api.buildInputOptions({
        items: [{ slug: "ban_le", item_code: "BAN-LE-01" }],
        variables: makeVariables(),
        item_fields: [],
    });
    assert(options.every((o) => String(o.value).indexOf("items.") !== 0),
        "bảng phụ kiện ⛔ được mời bất kỳ cột dòng nào (width/height)");
}

check("buildInputOptions — item_fields rỗng ⇒ bảng phụ kiện chỉ còn biến", () => {
    testAccessoryFields(helper);
});

check("ĐỐI CHỨNG ÂM — item_fields (để width/height lọt vào bảng phụ kiện)", () => {
    // Bản hỏng: bỏ qua item_fields, luôn mời Rộng/Cao.
    const broken = {
        buildInputOptions(input) {
            input = input || {};
            return helper.buildInputOptions(Object.assign({}, input, {
                item_fields: ["width", "height"],
            }));
        },
    };
    mustFail(() => testAccessoryFields(broken), "bỏ qua item_fields");
    // Khôi phục: bản thật phải xanh lại.
    testAccessoryFields(helper);
});

// ═══════════════════════════════════════════════════════════════════════════
// 4b. buildRuleInputOptions — nguồn dữ liệu cho `rule_input_expr`
// ═══════════════════════════════════════════════════════════════════════════
function testRuleInputOptions(api) {
    const items = makeItems();
    const options = api.buildRuleInputOptions(items);
    const values = options.map((o) => o.value);

    // CHỈ dòng kính × {độ dày kính, loại kính} — đúng thứ tự khai.
    eq(values, [
        "items.kinh_tren.total_thick_mm",
        "items.kinh_tren.glass_type",
        "items.kinh_canh.total_thick_mm",
        "items.kinh_canh.glass_type",
    ], "danh sách nguồn dữ liệu");

    // ĐÂY là lỗi nghiệp vụ phải chặn: engine KHÔNG đọc width/height/qty cho
    // rule_input_expr ⇒ chọn "Rộng" ra 0 âm thầm, dòng không có mã.
    assert(values.every((v) => !/\.(width|height|qty)$/.test(v)),
        "⛔ được mời Rộng/Cao/Số lượng cho rule_input_expr");

    // Dòng nẹp / nhôm / không phải kính ⇒ không sinh option nào.
    assert(values.every((v) => v.indexOf("items.nep_tren.") !== 0),
        "dòng nẹp ⛔ được sinh nguồn dữ liệu");
    assert(values.every((v) => v.indexOf("items.canh_doc.") !== 0),
        "dòng nhôm ⛔ được sinh nguồn dữ liệu");

    // Nhãn + mẫu (dòng Kính trên có total_thick_mm = 10; dòng Kinh canh dùng alias).
    eq(options[0].label, "Kính trên — Độ dày kính (mm)");
    eq(options[0].group, "Dòng trong BOM");
    eq(options[0].sample_value, 10);
    eq(options[1].label, "Kính trên — Loại kính");
    eq(options[1].sample_value, "LOWE");
    eq(options[2].sample_value, 8, "đọc alias glass_thick");
    eq(options[3].sample_value, null);

    eq(values.length, new Set(values).size, "danh sách nguồn dữ liệu bị trùng");
    eq(api.buildRuleInputOptions([]), []);
    eq(api.buildRuleInputOptions(null), []);
    eq(api.buildRuleInputOptions(undefined), []);
    eq(api.buildRuleInputOptions(items.filter((r) => !api.isGlassRow(r))), [],
        "bộ chỉ có dòng không phải kính ⇒ danh sách rỗng");

    options.forEach((o) => {
        assert("value" in o && "label" in o && "group" in o && "sample_value" in o,
            "option thiếu khoá: " + JSON.stringify(o));
    });
}

check("buildRuleInputOptions — chỉ dòng kính × độ dày/loại kính", () => {
    testRuleInputOptions(helper);
});

check("ĐỐI CHỨNG ÂM — buildRuleInputOptions (để Rộng/Cao lọt)", () => {
    // Bản hỏng = hành vi CŨ: dùng chung buildInputOptions ⇒ mời cả Rộng/Cao.
    const broken = {
        buildRuleInputOptions(items) {
            return helper.buildInputOptions({ items: items, variables: [] })
                .filter((o) => String(o.value).indexOf("items.") === 0);
        },
        isGlassRow: helper.isGlassRow,
    };
    mustFail(() => testRuleInputOptions(broken), "mời Rộng/Cao cho rule_input_expr");
});

check("validateRuleInput — chặn cột ngoài allowlist / dòng không phải kính", () => {
    const items = makeItems();
    assert(helper.validateRuleInput("items.kinh_tren.total_thick_mm", items).ok);
    assert(helper.validateRuleInput("items.kinh_tren.glass_thick", items).ok, "alias cũ vẫn nhận");
    assert(helper.validateRuleInput("items.kinh_tren.glass_type", items).ok);

    const width = helper.validateRuleInput("items.kinh_tren.width", items);
    assert(!width.ok, "Rộng phải bị chặn");
    assert(width.message && width.message.length > 0, "chặn phải kèm câu giải thích");

    assert(!helper.validateRuleInput("items.nep_tren.total_thick_mm", items).ok,
        "dòng nẹp không đọc được");
    const gone = helper.validateRuleInput("items.khong_co.width", items);
    assert(!gone.ok && gone.message.indexOf("khong_co") < 0,
        "câu lỗi ⛔ được nêu slug kỹ thuật");
    assert(!helper.validateRuleInput("H_mm", items).ok);
    assert(!helper.validateRuleInput("items[0].glass_thick", items).ok);
    assert(!helper.validateRuleInput("", items).ok);

    assert(helper.isRuleInputReadable("items.kinh_tren.total_thick_mm", items));
    assert(helper.isRuleInputReadable("items.kinh_tren.max_area_m2", items),
        "max_area_m2 engine vẫn đọc (dữ liệu cũ)");
    assert(!helper.isRuleInputReadable("items.kinh_tren.width", items));
    assert(!helper.isRuleInputReadable("items.canh_doc.total_thick_mm", items),
        "dòng nhôm không đọc được");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4c. findEquivalentOption — alias `glass_thick` ↔ `total_thick_mm`
// ═══════════════════════════════════════════════════════════════════════════
function testAliasOption(api) {
    const options = helper.buildRuleInputOptions(makeItems());
    const exact = api.findEquivalentOption(options, "items.kinh_tren.total_thick_mm");
    assert(exact, "tên chuẩn phải khớp");
    eq(exact.value, "items.kinh_tren.total_thick_mm");

    const alias = api.findEquivalentOption(options, "items.kinh_tren.glass_thick");
    assert(alias, "quy tắc cũ dùng glass_thick phải khớp option tên chuẩn");
    eq(alias.value, "items.kinh_tren.total_thick_mm",
        "alias phải trỏ về option đang có trong danh sách");

    eq(api.findEquivalentOption(options, "items.kinh_tren.width"), null,
        "Rộng ⛔ được coi là khớp");
    eq(api.findEquivalentOption(options, "H_mm"), null, "biến không phải alias");
    eq(api.findEquivalentOption(options, ""), null);
    eq(api.findEquivalentOption(null, "items.kinh_tren.glass_thick"), null);
}

check("findEquivalentOption — glass_thick là alias của total_thick_mm", () => {
    testAliasOption(helper);
});

check("ĐỐI CHỨNG ÂM — findEquivalentOption (so khớp đúng tên)", () => {
    // Bản hỏng: chỉ so khớp đúng chuỗi ⇒ công thức cũ rơi xuống ô "Nhập tay".
    const broken = {
        findEquivalentOption(options, value) {
            return (options || []).filter((o) => o.value === value)[0] || null;
        },
    };
    mustFail(() => testAliasOption(broken), "không nhận alias glass_thick");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4d. parseFormulaSnippet — đọc công thức ĐANG CÓ thành trạng thái hộp thoại
// ═══════════════════════════════════════════════════════════════════════════
function testFormulaParsing(api) {
    eq(api.parseFormulaSnippet("").preset, "", "ô trống");
    eq(api.parseFormulaSnippet(null).preset, "", "null");

    eq(api.parseFormulaSnippet("n_panel").preset, "panels");
    eq(api.parseFormulaSnippet("2 * n_panel").preset, "panels2");
    eq(api.parseFormulaSnippet("2*n_panel").preset, "panels2", "không khoảng trắng");
    eq(api.parseFormulaSnippet("  2  *  n_panel  ").preset, "panels2");

    const fixed = api.parseFormulaSnippet("4");
    eq([fixed.preset, fixed.fixed], ["fixed", "4"]);
    const fixedComma = api.parseFormulaSnippet("2,5");
    eq([fixedComma.preset, fixedComma.fixed], ["fixed", "2,5"],
        "giữ nguyên chuỗi người dùng gõ");

    const rule = api.parseFormulaSnippet("lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel");
    eq([rule.preset, rule.rule, rule.input, rule.multiplier],
        ["rule", "RULE-BANLE-QTY", "H_mm", "n_panel"]);

    const noMul = api.parseFormulaSnippet("lookup_rule('RULE-NEP', items.kinh_tren.total_thick_mm)");
    eq([noMul.rule, noMul.input, noMul.multiplier],
        ["RULE-NEP", "items.kinh_tren.total_thick_mm", ""]);

    // Round-trip: phân tích rồi dựng lại phải ra đúng chuỗi cũ.
    eq(api.buildSnippet({ code: rule.rule, input: rule.input, multiplier: rule.multiplier }),
        "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel");

    // Mã có dấu nháy đơn đã thoát.
    eq(api.parseFormulaSnippet("lookup_rule('O\\'BRIEN', H_mm)").rule, "O'BRIEN");

    // Biểu thức chưa thuộc dạng dựng sẵn ⇒ preset rỗng nhưng giữ raw để hiện
    // "Ô đang có: …".
    const free = api.parseFormulaSnippet("H_mm * 2");
    eq([free.preset, free.raw], ["", "H_mm * 2"]);
    eq(api.parseFormulaSnippet("lookup_rule('A', H_mm) + 1").preset, "",
        "chỉ nhận đúng dạng lookup_rule [* multiplier]");

    // Chặng 3: lời gọi MỘT tham số hợp lệ (quy tắc tự lấy dữ liệu tra).
    const single = api.parseFormulaSnippet("lookup_rule('A')");
    eq([single.preset, single.rule, single.input, single.single_arg],
        ["rule", "A", "", true], "lookup_rule('A') nhận dạng 1 tham số");
    const singleMul = api.parseFormulaSnippet("lookup_rule('A') * n_panel");
    eq([singleMul.rule, singleMul.input, singleMul.multiplier, singleMul.single_arg],
        ["A", "", "n_panel", true]);
    eq(api.parseFormulaSnippet("lookup_rule('A', H_mm)").single_arg, false,
        "2 tham số ⇒ ⛔ cờ 1 tham số");
    eq(api.parseFormulaSnippet("lookup_rule('A') + 1").preset, "",
        "1 tham số mà còn phép tính khác ⇒ chưa nhận dạng");

    eq(api.parseLookupSnippet("lookup_rule('A', f(H_mm)) * 2"),
        { code: "A", input: "f(H_mm)", multiplier: "2" }, "ngoặc lồng nhau");
    eq(api.parseLookupSnippet("lookup_rule('A')"),
        { code: "A", input: "", multiplier: "" });
    eq(api.parseLookupSnippet("lookup_rule( 'A' )  *  2"),
        { code: "A", input: "", multiplier: "2" }, "khoảng trắng quanh tham số");
    eq(api.parseLookupSnippet("H_mm"), null);
}

check("parseFormulaSnippet — 4 preset + nhánh quy tắc + biểu thức tự do", () => {
    testFormulaParsing(helper);
});

check("ĐỐI CHỨNG ÂM — parseFormulaSnippet", () => {
    // Bản hỏng: luôn trả preset rỗng (không phản chiếu gì) ⇒ mở hộp thoại
    // rồi bấm Chèn là ghi đè im lặng.
    const broken = {
        parseFormulaSnippet(value) {
            return { preset: "", fixed: "", rule: "", input: "", multiplier: "", raw: String(value || "") };
        },
        parseLookupSnippet() { return null; },
        buildSnippet: helper.buildSnippet,
    };
    mustFail(() => testFormulaParsing(broken), "không nhận dạng công thức đang có");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4d-ter. Chặng 3 — quy tắc tự khai "tra theo cái gì"
//   GLOBAL ⇒ bỏ bước "Dữ liệu đem tra", chèn `lookup_rule('MÃ')`
//   ROW    ⇒ chỉ mời DÒNG có biến, chèn `lookup_rule('MÃ', items.<dòng>.<cột>)`
//   chưa khai ⇒ giữ nguyên đường cũ
// ═══════════════════════════════════════════════════════════════════════════
const GLOBAL_RULE = {
    rule_code: "RULE-BANLE-QTY", rule_name: "Số bản lề theo chiều cao",
    result_type: "NUMBER", input_variable: "H_mm", input_scope: "GLOBAL",
    input_label: "Chiều cao", input_unit: "mm",
};
const ROW_RULE = {
    rule_code: "RULE-NEP-GLASSTHICK", rule_name: "Chọn nẹp theo độ dày kính",
    result_type: "ITEM", input_variable: "total_thick_mm", input_scope: "ROW",
    input_label: "Độ dày kính", input_unit: "mm",
};
const LEGACY_RULE = {
    rule_code: "RULE-OLD", rule_name: "Quy tắc cũ",
    result_type: "ITEM", input_label: "Độ dày kính",
};

function testRuleInputModel(api) {
    // normalizeRule mang thêm 2 field + chuẩn hoá phạm vi.
    const row = api.normalizeRule({
        name: "R1", input_variable: " H_mm ", input_scope: "global",
    });
    eq([row.rule_code, row.input_variable, row.input_scope],
        ["R1", "H_mm", "GLOBAL"], "normalizeRule mang input_variable/input_scope");
    eq(api.normalizeRule({ name: "R2" }).input_scope, "",
        "thiếu field (site chưa migrate) ⇒ rỗng = legacy");
    eq(api.normalizeRule({ name: "R3", input_scope: "bậy" }).input_scope, "",
        "phạm vi lạ ⇒ rỗng, ⛔ đoán");
    eq(api.normalizeRule({ name: "R4", input_scope: "row" }).input_scope, "ROW");

    assert(api.hasDeclaredRuleInput(GLOBAL_RULE));
    assert(api.hasDeclaredRuleInput(ROW_RULE));
    assert(!api.hasDeclaredRuleInput(LEGACY_RULE), "chưa khai ⇒ legacy");
    assert(!api.hasDeclaredRuleInput({ input_variable: "H_mm" }),
        "có biến mà thiếu phạm vi ⇒ chưa khai");
    eq(api.ruleInputScope(GLOBAL_RULE), "GLOBAL");
    eq(api.ruleInputScope(ROW_RULE), "ROW");
    eq(api.ruleInputScope(LEGACY_RULE), "");
    eq(api.ruleInputVariable(GLOBAL_RULE), "H_mm");
    eq(api.ruleInputVariable(null), "");
    // UX1 chấm CHẶN vòng 2 (2026-11-25c): câu người dùng đọc ⛔ chứa MÃ BIẾN.
    // Có biến mà thiếu nhãn ⇒ "dữ liệu quy tắc đọc" (KHÔNG lấy `H_mm` làm
    // nhãn như bản trước — đó chính là lỗi bị chặn).
    eq(api.ruleInputLabel({ input_variable: "H_mm", input_unit: "mm" }),
        "dữ liệu quy tắc đọc (mm)");
    eq(api.ruleInputLabel({ input_unit: "mm" }), "giá trị đem tra (mm)",
        "chưa có biến lẫn nhãn ⇒ nhãn chung");

    // ── GLOBAL: ⛔ bước "Dữ liệu đem tra" ──
    const gplan = api.ruleInsertPlan(GLOBAL_RULE);
    eq([gplan.declared, gplan.scope, gplan.variable, gplan.needs_input, gplan.single_arg],
        [true, "GLOBAL", "H_mm", false, true],
        "GLOBAL ⛔ hỏi dữ liệu + chèn dạng 1 tham số");
    eq(gplan.label, "Chiều cao (mm)");

    // ── ROW: vẫn hỏi, nhưng chỉ hỏi DÒNG ──
    const rplan = api.ruleInsertPlan(ROW_RULE);
    eq([rplan.declared, rplan.scope, rplan.needs_input, rplan.single_arg],
        [true, "ROW", true, false], "ROW hỏi dòng lấy dữ liệu");

    // ── Chưa khai: giữ nguyên hành vi cũ ──
    const lplan = api.ruleInsertPlan(LEGACY_RULE);
    eq([lplan.declared, lplan.scope, lplan.needs_input, lplan.single_arg],
        [false, "", true, false], "legacy giữ bước chọn dữ liệu");
    eq(api.ruleInsertPlan(null).needs_input, true, "không có metadata ⇒ legacy");

    // Câu chữ người dùng đọc — UX1 vòng 2: ⛔ mã biến trong câu.
    eq(api.ruleGlobalSentenceHtml(GLOBAL_RULE),
        "Quy tắc tự lấy <b>Chiều cao (mm)</b>");
    eq(api.ruleRowSentenceHtml(ROW_RULE, "Kính trên"),
        "Quy tắc khai tra theo <b>Độ dày kính (mm)</b> · lấy từ dòng <b>Kính trên</b>");
    eq(api.ruleRowSentenceHtml(ROW_RULE, ""),
        "Quy tắc khai tra theo <b>Độ dày kính (mm)</b>", "chưa chọn dòng ⇒ bỏ vế sau");
    eq(api.ruleCurrentValueHtml(24, "C3211-20"),
        " · hiện tại <b>24</b> → <b>C3211-20</b>");
    eq(api.ruleCurrentValueHtml(24, ""), " · hiện tại <b>24</b>",
        "chưa tra được ⇒ vẫn hiện giá trị hiện tại");
    // Escape: nhãn quy tắc là dữ liệu quản trị nhập ⇒ ⛔ chèn thẻ HTML.
    eq(api.ruleRowSentenceHtml(
        Object.assign({}, ROW_RULE, { input_label: "<x>" }), "A<b>"),
        "Quy tắc khai tra theo <b>&lt;x&gt; (mm)</b> · lấy từ dòng <b>A&lt;b&gt;</b>");
}

check("Chặng 3 — quy tắc khai 'tra theo': GLOBAL ⛔ bước dữ liệu / ROW hỏi dòng / legacy giữ nguyên", () => {
    testRuleInputModel(helper);
});

check("ĐỐI CHỨNG ÂM — ruleInsertPlan (GLOBAL vẫn hỏi dữ liệu)", () => {
    // Bản hỏng: mọi quy tắc đều phải chọn dữ liệu ⇒ GLOBAL hiện bước thừa và
    // chèn `lookup_rule('MÃ', …)` dù engine không cần.
    const broken = Object.assign({}, helper, {
        ruleInsertPlan(rule) {
            const variable = helper.ruleInputVariable(rule);
            const scope = helper.ruleInputScope(rule);
            return {
                declared: !!(variable && scope), scope, variable,
                label: helper.ruleInputLabel(rule),
                needs_input: true, single_arg: false,
            };
        },
    });
    mustFail(() => testRuleInputModel(broken), "GLOBAL vẫn hỏi dữ liệu");
});

function testRuleSnippet(api) {
    // GLOBAL: 1 tham số + vẫn cho "Nhân với"
    eq(api.buildSnippet({ code: "RULE-BANLE-QTY", single_arg: true }),
        "lookup_rule('RULE-BANLE-QTY')");
    eq(api.buildSnippet({
        code: "RULE-BANLE-QTY", input: "", single_arg: true,
    }), "lookup_rule('RULE-BANLE-QTY')");
    eq(api.buildSnippet({
        code: "RULE-BANLE-QTY", single_arg: true, multiplier: " n_panel ",
    }), "lookup_rule('RULE-BANLE-QTY') * n_panel", "ví dụ thiết kế §7.5");
    eq(api.buildSnippet({ code: "RULE-BANLE-QTY" }), null,
        "thiếu input mà ⛔ single_arg ⇒ vẫn null (hành vi cũ)");
    eq(api.buildSnippet({ code: "O'BRIEN", single_arg: true }),
        "lookup_rule('O\\'BRIEN')", "vẫn escape nháy");

    // ROW: chèn biểu thức theo dòng
    eq(api.buildSnippet({
        code: "RULE-NEP-GLASSTHICK", input: "items.kinh_tren.total_thick_mm",
    }), "lookup_rule('RULE-NEP-GLASSTHICK', items.kinh_tren.total_thick_mm)");

    // Round-trip 1 tham số.
    const parsed = api.parseFormulaSnippet("lookup_rule('RULE-BANLE-QTY') * n_panel");
    eq(api.buildSnippet({
        code: parsed.rule, input: parsed.input,
        multiplier: parsed.multiplier, single_arg: parsed.single_arg,
    }), "lookup_rule('RULE-BANLE-QTY') * n_panel");
    // Round-trip 2 tham số vẫn đúng.
    const parsed2 = api.parseFormulaSnippet(
        "lookup_rule('RULE-NEP', items.kinh_tren.glass_thick)");
    eq(api.buildSnippet({
        code: parsed2.rule, input: parsed2.input, multiplier: parsed2.multiplier,
    }), "lookup_rule('RULE-NEP', items.kinh_tren.glass_thick)");
}

check("Chặng 3 — snippet GLOBAL 1 tham số / ROW có items.<dòng>.<cột> / round-trip", () => {
    testRuleSnippet(helper);
});

check("ĐỐI CHỨNG ÂM — buildSnippet single_arg (quên cờ ⇒ GLOBAL không chèn được)", () => {
    // Bản hỏng: bản cũ đòi input ⇒ quy tắc GLOBAL không dựng được snippet.
    const broken = {
        buildSnippet(o) {
            o = o || {};
            const code = String(o.code || "").trim();
            const input = String(o.input || "").trim();
            if (!code || !input) return null;
            const core = "lookup_rule('" + code + "', " + input + ")";
            return o.multiplier ? core + " * " + String(o.multiplier).trim() : core;
        },
        parseFormulaSnippet: helper.parseFormulaSnippet,
    };
    mustFail(() => testRuleSnippet(broken), "đòi input với quy tắc GLOBAL");
});

function testRuleRowOptions(api) {
    const items = makeItems();

    // Biến kính ⇒ chỉ dòng kính, nhãn "dòng — nhãn biến (đơn vị)".
    const options = api.buildRuleRowOptions(ROW_RULE, items);
    eq(options.map((o) => o.slug), ["kinh_tren", "kinh_canh"],
        "chỉ dòng kính (⛔ mời dòng nẹp/nhôm)");
    eq(options[0].label, "Kính trên — Độ dày kính (mm)");
    eq(options[0].value, "items.kinh_tren.total_thick_mm");
    eq(options[0].line_name, "Kính trên");
    eq(options[0].sample_value, 10);
    eq(options[1].sample_value, 8, "đọc alias glass_thick của dòng kính");
    eq(options[0].group, "Dòng trong BOM");

    // Biến KHÁC (không phải dữ liệu kính): chỉ dòng THẬT SỰ có giá trị.
    const widthRule = {
        rule_code: "R-W", input_variable: "width", input_scope: "ROW",
        input_label: "Rộng", input_unit: "mm", result_type: "NUMBER",
    };
    const widths = api.buildRuleRowOptions(widthRule, items);
    eq(widths.map((o) => o.slug), ["kinh_tren", "nep_tren", "canh_doc"],
        "bỏ dòng không có số Rộng (kinh_canh)");
    eq(widths[0].label, "Kính trên — Rộng (mm)");
    eq(widths[1].sample_value, "W_mm / n_panel", "ô đang giữ công thức ⇒ giữ nguyên chữ");

    // Biến loại kính: dòng kính thiếu loại vẫn mời (engine đọc từ kính mặc định).
    const typeRule = Object.assign({}, ROW_RULE, {
        input_variable: "glass_type", input_label: "Loại kính", input_unit: "",
    });
    eq(api.buildRuleRowOptions(typeRule, items).map((o) => o.slug),
        ["kinh_tren", "kinh_canh"]);

    // Chưa khai biến ⇒ không có "dòng lấy dữ liệu".
    eq(api.buildRuleRowOptions(LEGACY_RULE, items), []);
    eq(api.buildRuleRowOptions(null, items), []);
    eq(api.buildRuleRowOptions(ROW_RULE, []), []);
    eq(api.buildRuleRowOptions(ROW_RULE, null), []);

    // Biểu thức dòng
    eq(api.ruleRowOptionExpr("kinh_tren", "total_thick_mm"),
        "items.kinh_tren.total_thick_mm");
    eq(api.ruleRowOptionExpr("", "x"), "");
    eq(api.ruleRowOptionExpr("a b", "x"), "", "slug không dựng được biểu thức");
    eq(api.ruleRowOptionExpr("kinh", ""), "");

    // rowVariableValue / rowSupportsVariable
    eq(api.rowVariableValue(items[0], "glass_thick"), 10, "alias độ dày");
    eq(api.rowVariableValue(items[3], "total_thick_mm"), null);
    assert(api.rowSupportsVariable(items[0], "total_thick_mm"));
    assert(!api.rowSupportsVariable(items[1], "total_thick_mm"),
        "dòng nẹp ⛔ cung cấp được độ dày kính");
    assert(api.rowSupportsVariable(items[1], "width"));

    // findRuleRowOption
    eq(api.findRuleRowOption(options, "kinh_canh").slug, "kinh_canh");
    eq(api.findRuleRowOption(options, "nep_tren"), null);
    eq(api.findRuleRowOption(null, "kinh_tren"), null);

    // buildRuleInsertOptions phân nhánh theo quy tắc
    const vars = makeVariables();
    const rowInsert = api.buildRuleInsertOptions({
        rule: ROW_RULE, items: items, variables: vars, item_fields: ["width", "height"],
    });
    eq(rowInsert.map((o) => o.value),
        ["items.kinh_tren.total_thick_mm", "items.kinh_canh.total_thick_mm"],
        "ROW: chỉ dòng có biến, ⛔ biến chứng từ / cột khác");
    eq(api.buildRuleInsertOptions({
        rule: GLOBAL_RULE, items: items, variables: vars,
    }), [], "GLOBAL: ⛔ mời dữ liệu");

    const legacyInsert = api.buildRuleInsertOptions({
        rule: LEGACY_RULE, items: items, variables: vars, item_fields: ["width", "height"],
    });
    assert(byValue(legacyInsert, "H_mm"), "legacy vẫn mời biến chứng từ");
    assert(byValue(legacyInsert, "items.kinh_tren.width"), "legacy vẫn mời Rộng");
}

check("Chặng 3 — buildRuleRowOptions chỉ mời dòng có biến của quy tắc", () => {
    testRuleRowOptions(helper);
});

check("ĐỐI CHỨNG ÂM — buildRuleRowOptions (mời mọi dòng × mọi cột)", () => {
    // Bản hỏng = hành vi cũ: đường "dữ liệu đem tra" mời mọi dòng × Rộng/Cao
    // và cả biến chứng từ ⇒ chọn dòng nẹp cho quy tắc độ dày = 0 âm thầm.
    const broken = {
        buildRuleRowOptions(rule, items) {
            return helper.buildInputOptions({ items: items, variables: [] })
                .filter((o) => String(o.value).indexOf("items.") === 0)
                .map((o) => {
                    const ref = helper.parseItemExpr(o.value);
                    return {
                        slug: ref ? ref.slug : "", line_name: "", value: o.value,
                        label: o.label, group: o.group, sample_value: o.sample_value,
                    };
                });
        },
        ruleRowOptionExpr: helper.ruleRowOptionExpr,
        rowVariableValue: helper.rowVariableValue,
        rowSupportsVariable: helper.rowSupportsVariable,
        findRuleRowOption: helper.findRuleRowOption,
        buildRuleInsertOptions: helper.buildRuleInsertOptions,
    };
    mustFail(() => testRuleRowOptions(broken), "mời Rộng/Cao và dòng không phù hợp");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4d-quater. Danh mục biến "Tra theo" — chỉ mời biến ENGINE ĐỌC ĐƯỢC
//   API `alumglass.api.get_rule_input_variables()` trả
//   [{name, label, category, scope, resolvable}]; `resolvable = false` nghĩa là
//   biến không có giá trị ở bước chọn mã ⇒ chọn vào là quy tắc không ra kết quả.
// ═══════════════════════════════════════════════════════════════════════════
function makeInputVariables() {
    return [
        { name: "total_thick_mm", label: "Độ dày kính", category: "Row Literals", scope: "ROW", resolvable: 1 },
        { name: "glass_type", label: "Loại kính", category: "Row Literals", scope: "ROW", resolvable: true },
        { name: "total_thick_mm", label: "trùng tên", scope: "ROW", resolvable: 1 },
        { name: "width", label: "Rộng", scope: "ROW", resolvable: 0 },
        { name: "height", label: "Cao", scope: "ROW", resolvable: "0" },
        { name: "H_mm", label: "Chiều cao", scope: "GLOBAL" },        // thiếu cờ ⇒ giữ
        { name: "n_panel", label: "Số cánh", scope: "GLOBAL", resolvable: false },
        { name: "", label: "Không tên", resolvable: 1 },
        { name: "  glass_type  ", resolvable: "1" },
        null,
    ];
}

function testResolvableInputs(api) {
    const vars = makeInputVariables();

    eq(api.ruleInputResolvableNames(vars),
        ["total_thick_mm", "glass_type", "H_mm"],
        "chỉ biến dùng được + bỏ trùng + trim tên");
    eq(api.ruleInputResolvableNames(null), []);
    eq(api.ruleInputResolvableNames(undefined), []);
    eq(api.ruleInputResolvableNames([]), []);

    assert(api.isRuleInputResolvable(vars, "total_thick_mm"));
    assert(api.isRuleInputResolvable(vars, "glass_type"));
    assert(api.isRuleInputResolvable(vars, "H_mm"), "thiếu cờ resolvable ⇒ coi như dùng được");
    assert(!api.isRuleInputResolvable(vars, "width"), "resolvable=0 phải bị loại");
    assert(!api.isRuleInputResolvable(vars, "height"), "resolvable='0' phải bị loại");
    assert(!api.isRuleInputResolvable(vars, "n_panel"), "resolvable=false phải bị loại");

    // Chưa đủ dữ liệu để kết luận ⇒ ⛔ cảnh báo oan.
    assert(api.isRuleInputResolvable(vars, ""), "chưa chọn biến ⇒ không cảnh báo");
    assert(api.isRuleInputResolvable(null, "width"), "chưa có danh sách ⇒ không cảnh báo");
    assert(api.isRuleInputResolvable([], "width"), "danh sách rỗng ⇒ không cảnh báo");
    assert(api.isRuleInputResolvable([null, {}], "width"), "danh sách toàn rác ⇒ không cảnh báo");
}

check("Biến 'Tra theo' — chỉ mời biến resolvable, thiếu cờ/danh sách rỗng ⇒ không kết luận", () => {
    testResolvableInputs(helper);
});

check("ĐỐI CHỨNG ÂM — ruleInputResolvableNames (bỏ qua cờ resolvable)", () => {
    // Bản hỏng: mời MỌI biến trong danh mục ⇒ chọn `width` là quy tắc không
    // bao giờ ra kết quả mà giao diện vẫn báo "hợp lệ".
    const broken = {
        ruleInputResolvableNames(variables) {
            const out = [];
            (Array.isArray(variables) ? variables : []).forEach((entry) => {
                if (entry && entry.name && out.indexOf(entry.name) === -1) out.push(entry.name);
            });
            return out;
        },
        isRuleInputResolvable(variables, name) {
            const want = String(name || "").trim();
            if (!want || !Array.isArray(variables)) return true;
            const names = this.ruleInputResolvableNames(variables);
            return !names.length || names.indexOf(want) !== -1;
        },
    };
    mustFail(() => testResolvableInputs(broken), "mời cả biến không dùng được");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4d-bis. ruleFormRoute — URL thuần cho "Xem quy tắc" (⛔ chuỗi <a>)
// ═══════════════════════════════════════════════════════════════════════════
function testRuleFormRoute(api) {
    eq(api.ruleFormRoute("RULE-NEP-GLASSTHICK"),
        "/app/al-rule/RULE-NEP-GLASSTHICK");
    eq(api.ruleFormRoute("  RULE-X  "), "/app/al-rule/RULE-X", "phải trim");

    const weird = api.ruleFormRoute("RULE A/B&<x>");
    assert(weird.indexOf("/app/al-rule/") === 0, "phải là route tuyệt đối: " + weird);
    assert(weird.indexOf("<") === -1 && weird.indexOf(">") === -1,
        "URL ⛔ được chứa thẻ HTML: " + weird);
    assert(weird.indexOf("<a") === -1, "URL ⛔ được là chuỗi <a href>: " + weird);
    assert(weird.indexOf("%20") !== -1, "khoảng trắng phải encode: " + weird);
    assert(weird.indexOf("%2F") !== -1, "dấu / trong mã phải encode: " + weird);

    eq(api.ruleFormRoute(""), "");
    eq(api.ruleFormRoute(null), "");
    eq(api.ruleFormRoute("   "), "");
}

check("ruleFormRoute — route thuần, mã lạ vẫn encode, ⛔ thẻ <a>", () => {
    testRuleFormRoute(helper);
});

check("ĐỐI CHỨNG ÂM — ruleFormRoute (trả lại chuỗi HTML của get_form_link)", () => {
    // Bản hỏng đúng lỗi Owner gặp: `get_form_link(..., html=true)`.
    const broken = {
        ruleFormRoute(code) {
            const route = "/app/al-rule/" + encodeURIComponent(String(code || "").trim());
            return `<a href="${route}">${code}</a>`;
        },
    };
    mustFail(() => testRuleFormRoute(broken), "trả chuỗi <a> thay vì route");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4e. extractServerMessage — lỗi thử tra phải nêu đúng câu server
// ═══════════════════════════════════════════════════════════════════════════
function testServerMessage(api) {
    const payload = {
        _server_messages: JSON.stringify([
            JSON.stringify({ message: "Bạn không có quyền xem quy tắc này.", indicator: "red" }),
        ]),
    };
    eq(api.extractServerMessage(payload), "Bạn không có quyền xem quy tắc này.");

    eq(api.extractServerMessage({
        responseJSON: {
            _server_messages: JSON.stringify([JSON.stringify({ message: "Không tìm thấy quy tắc." })]),
        },
    }), "Không tìm thấy quy tắc.", "lỗi jQuery nằm trong responseJSON");

    eq(api.extractServerMessage({ _server_messages: "[]" }), "", "mảng rỗng ⇒ không có câu");
    eq(api.extractServerMessage({}), "");
    eq(api.extractServerMessage(null), "");
    // `e.message` là câu kỹ thuật (Internal Server Error) ⇒ ⛔ dùng.
    eq(api.extractServerMessage({ message: "Internal Server Error" }), "");
    // Chuỗi không phải JSON vẫn giữ nguyên văn — ⛔ nuốt mất lý do.
    eq(api.extractServerMessage({ _server_messages: "Lỗi thô từ server" }), "Lỗi thô từ server");

    assert(api.isPreviewError({ __preview_error: "" }), "cờ lỗi rỗng vẫn là lỗi");
    assert(api.isPreviewError({ __preview_error: "câu" }));
    assert(!api.isPreviewError({ result: { value: 1 } }), "payload thành công ⛔ là lỗi");
    assert(!api.isPreviewError(null));
}

check("extractServerMessage — đọc `_server_messages`, ⛔ lấy câu kỹ thuật", () => {
    testServerMessage(helper);
});

check("ĐỐI CHỨNG ÂM — extractServerMessage", () => {
    // Bản hỏng: luôn rỗng ⇒ hộp thoại lại đổ cho quyền / câu trung tính.
    const broken = {
        extractServerMessage() { return ""; },
        isPreviewError: helper.isPreviewError,
    };
    mustFail(() => testServerMessage(broken), "nuốt câu lỗi của server");
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. resolveItemValue + parseItemExpr
// ═══════════════════════════════════════════════════════════════════════════
check("resolveItemValue — alias độ dày, dòng không tồn tại, expr sai dạng", () => {
    const items = makeItems();

    eq(helper.parseItemExpr("items.kinh_tren.glass_thick"),
        { slug: "kinh_tren", field: "glass_thick" });
    eq(helper.parseItemExpr("items[0].glass_thick"), null, "engine ⛔ nhận dạng index");
    eq(helper.parseItemExpr("H_mm"), null);
    eq(helper.parseItemExpr(""), null);

    const alias = helper.resolveItemValue(items, "items.kinh_tren.glass_thick");
    assert(alias, "alias glass_thick phải resolve được");
    eq(alias.value, 10);
    eq(alias.field, "total_thick_mm");

    eq(helper.resolveItemValue(items, "items.kinh_tren.total_thick_mm").value, 10);
    eq(helper.resolveItemValue(items, "items.kinh_canh.glass_thick").value, 8);
    eq(helper.resolveItemValue(items, "items.canh_doc.width").value, 100);

    eq(helper.resolveItemValue(items, "items.khong_co.width"), null);
    // 0 vẫn là giá trị THẬT (engine đọc đúng số đó) ⇒ ⛔ coi như "chưa có";
    // chỉ undefined / null / "" mới là chưa khai.
    eq(helper.resolveItemValue(items, "items.nep_tren.height").value, 0);
    // Field đang giữ CÔNG THỨC (chữ) vẫn trả nguyên giá trị thô — nơi dùng
    // phải tự kiểm số (fetchOptionSample chỉ nhận mẫu số cho độ dày/loại kính).
    eq(helper.resolveItemValue(items, "items.nep_tren.width").value, "W_mm / n_panel");
    eq(helper.resolveItemValue(items, "H_mm"), null);
    eq(helper.resolveItemValue(null, "items.kinh_tren.width"), null);
});

// ═══════════════════════════════════════════════════════════════════════════
// 6. Câu chữ kết quả thử + nhãn quy tắc
// ═══════════════════════════════════════════════════════════════════════════
check("Câu chữ kết quả thử — nhãn chủ ngữ + nhãn kết quả + nhãn biến nhân", () => {
    const heightOption = { value: "H_mm", label: "Chiều cao (H_mm)", sample_value: 3200 };
    eq(helper.samplePreviewText(heightOption,
        { result: { value: 4 }, output_label: "bản lề/cánh" }, null),
        "Chiều cao (H_mm) = 3200 → 4 bản lề/cánh");
    eq(helper.samplePreviewText(heightOption,
        { result: { value: 4 }, output_label: "bản lề/cánh" },
        { value: "n_panel", label: "Số cánh", sample_value: 2 }),
        "Chiều cao (H_mm) = 3200 → 4 bản lề/cánh × Số cánh 2 = 8", "ví dụ thiết kế");

    // Không có `output_label` ⇒ vẫn ghép phần nhân, ⛔ mất số cuối.
    eq(helper.samplePreviewText(heightOption, { result: { value: 4 } },
        { value: "n_panel", label: "Số cánh", sample_value: 2 }),
        "Chiều cao (H_mm) = 3200 → 4 × Số cánh 2 = 8");
    // Không có nhãn biến ⇒ dùng tên biến làm nhãn.
    eq(helper.samplePreviewText(heightOption, { result: { value: 4 } },
        { value: "n_panel", sample_value: 2 }),
        "Chiều cao (H_mm) = 3200 → 4 × n_panel 2 = 8");

    const thickOption = {
        value: "items.kinh_tren.total_thick_mm",
        label: "Kính trên — Độ dày kính (mm)",
        sample_value: 10,
    };
    // Kết quả là MÃ vật tư ⇒ ⛔ ghép `output_label` (đã có tên vật tư).
    eq(helper.samplePreviewText(thickOption,
        { result: { item_code: "C3209-20", item_name: "Nẹp 20" }, output_label: "Mã nẹp" }, null),
        "Kính trên — Độ dày kính (mm) = 10 → C3209-20 (Nẹp 20)");

    // Không có nhãn (nhập tay) ⇒ dùng chính giá trị làm chủ ngữ.
    eq(helper.samplePreviewText({ value: "3200", sample_value: 3200 },
        { result: { value: 4 } }, null), "3200 = 3200 → 4");

    eq(helper.samplePreviewText(null, { result: { value: 1 } }, null), "");

    eq(helper.resultText({ result: { value: 0 } }), "0");
    eq(helper.resultText({ result: { item_code: "C1" } }), "C1");
    eq(helper.resultText({ result: null }), "");
    eq(helper.resultText(null), "");

    eq(helper.matchText({ matched: { kind: "range", from: 0, to: 10.38 } }),
        "Khớp dải 0 – 10.38");
    eq(helper.matchText({ matched: { kind: "key", key: "LOWE" } }), "Khớp khóa LOWE");
    eq(helper.matchText({ matched: { kind: "constant" } }), "Quy tắc hằng số");
    eq(helper.matchText({ matched: null }), "");

    eq(helper.ruleSummary({
        input_label: "Độ dày kính", input_unit: "mm",
        output_label: "Mã nẹp", result_type: "ITEM",
    }), "tra theo Độ dày kính (mm) → Mã nẹp");
    eq(helper.ruleSummary({ result_type: "NUMBER" }),
        "tra theo giá trị đem tra → số", "site chưa migrate: nhãn dự phòng");
    eq(helper.ruleInputLabel({ input_label: "Độ dày kính (mm)", input_unit: "mm" }),
        "Độ dày kính (mm)", "⛔ nhân đôi đơn vị");
    eq(helper.ruleOutputLabel({ result_type: "ITEM" }), "mã vật tư");
});

// ═══════════════════════════════════════════════════════════════════════════
// 7. Bề mặt API (đảm bảo file nạp được và đủ hàm cho 3 màn hình dùng)
// ═══════════════════════════════════════════════════════════════════════════
check("Xuất API — đủ hàm cho AL Bom Item / AL Accessory Item / AL Rule", () => {
    [
        "buildSnippet", "buildPresetSnippet", "parseFormulaSnippet",
        "ruleFormRoute", "filterNumberRules",
        "buildInputOptions", "buildRuleInputOptions", "validateRuleInput",
        // Chặng 3 — quy tắc tự khai "tra theo"
        "ruleInputVariable", "ruleInputScope", "hasDeclaredRuleInput",
        "ruleInputResolvableNames", "isRuleInputResolvable",
        "ruleInsertPlan", "ruleGlobalSentenceHtml", "ruleRowSentenceHtml",
        "ruleCurrentValueHtml", "rowVariableValue", "rowSupportsVariable",
        "ruleRowOptionExpr", "buildRuleRowOptions", "findRuleRowOption",
        "buildRuleInsertOptions", "openRuleRowPicker",
        "resolveItemValue", "findEquivalentOption", "fetchNumberRules",
        "fetchRuleForCode", "fetchOptionSample", "fetchVariableSample",
        "callPreviewRule",
        "extractServerMessage",
        "insertFormula", "rowFieldWrapper",
        "openInsert", "openRulePreview", "openInputPicker",
    ].forEach((name) => {
        assert(typeof helper[name] === "function", "thiếu hàm " + name);
    });
    assert(global.AlumGlassRuleHelper === helper,
        "phải gắn window.AlumGlassRuleHelper cho doctype_js dùng");
});

// ═══════════════════════════════════════════════════════════════════════════
// 8. UX1 chấm CHẶN vòng 2 (2026-11-25c) — câu người dùng đọc
//    (a) ⛔ mã biến/mã quy tắc trong câu
//    (b) nhãn dòng ⛔ slug
//    (c) biến engine TỰ TÍNH ⇒ liệt kê mọi dòng
//    (d) trạng thái thiếu giá trị / quy tắc tắt-xoá phải có câu + việc cần làm
// ═══════════════════════════════════════════════════════════════════════════

// ── 8a. describeFormula — câu thường trực cho ô công thức phụ kiện ────────
function testDescribeFormula(api) {
    eq(api.describeFormula("").text, "Chưa đặt công thức số lượng.");
    eq(api.describeFormula(null).text, "Chưa đặt công thức số lượng.");

    eq(api.describeFormula("n_panel").text, "Số lượng = số cánh của bộ");
    eq(api.describeFormula("2 * n_panel").text, "Số lượng = 2 × số cánh");
    eq(api.describeFormula("4").text, "Số lượng cố định: 4");
    eq(api.describeFormula("2,5").text, "Số lượng cố định: 2,5",
        "giữ nguyên số người dùng gõ");

    const lookup = api.describeFormula(
        "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel");
    eq(lookup.text, "Số lượng = kết quả tra quy tắc theo chiều cao × số cánh");
    eq([lookup.rule_code, lookup.linkable], ["RULE-BANLE-QTY", true],
        "mã quy tắc CHỈ dùng cho nút Xem quy tắc");

    const itemVar = api.describeFormula(
        "lookup_rule('RULE-NEP', items.kinh_tren.total_thick_mm)");
    eq(itemVar.text, "Số lượng = kết quả tra quy tắc theo độ dày kính");
    eq(itemVar.rule_code, "RULE-NEP");

    const single = api.describeFormula("lookup_rule('RULE-X')");
    eq(single.text, "Số lượng = kết quả tra quy tắc");
    eq([single.rule_code, single.linkable], ["RULE-X", true]);

    // Công thức lạ ⇒ câu trung tính, ⛔ đoán số, ⛔ mã.
    ["H_mm * 2", "lookup_rule('A', H_mm) + 1", "W_mm / n_panel"].forEach((raw) => {
        const info = api.describeFormula(raw);
        eq(info.text, "Công thức tự nhập", "công thức lạ: " + raw);
        eq(info.linkable, false, "⛔ nút Xem quy tắc khi chưa đọc được mã");
    });

    // Bất biến: câu người dùng đọc ⛔ chứa mã kỹ thuật.
    const samples = [
        "n_panel", "2 * n_panel", "4",
        "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel",
        "lookup_rule('RULE-NEP', items.kinh_tren.total_thick_mm)",
        "lookup_rule('RULE-X')", "H_mm * 2",
    ];
    samples.forEach((raw) => {
        const text = api.describeFormula(raw).text;
        ["H_mm", "n_panel", "RULE-", "items.", "lookup_rule"].forEach((token) => {
            assert(text.indexOf(token) === -1,
                "câu '" + text + "' ⛔ được chứa mã '" + token + "'");
        });
    });
}

check("describeFormula — câu thường trực: 2 dạng đơn giản + quy tắc + câu trung tính", () => {
    testDescribeFormula(helper);
});

check("ĐỐI CHỨNG ÂM — describeFormula (trả nguyên chuỗi công thức)", () => {
    const broken = Object.assign({}, helper, {
        describeFormula(value) {
            const raw = String(value == null ? "" : value).trim();
            return { text: "Công thức: " + raw, rule_code: "", linkable: false };
        },
    });
    mustFail(() => testDescribeFormula(broken), "lộ mã biến/mã quy tắc trong câu");
});

// ── 8b. Nhãn dòng — ⛔ slug ở mọi danh sách ───────────────────────────────
function testRowDisplayName(api) {
    eq(api.rowDisplayName({ line_name: "Kính trên", slug: "kinh_tren" }, 0), "Kính trên");
    eq(api.rowDisplayName({ slug: "kinh_tren" }, 2), "Dòng chưa đặt tên (Dòng 3)");
    eq(api.rowDisplayName({}, 0), "Dòng chưa đặt tên (Dòng 1)");
    eq(api.rowDisplayName({ slug: "x" }), "Dòng chưa đặt tên",
        "không có vị trí ⇒ vẫn ⛔ slug");
    eq(api.rowIndexBySlug(makeItems(), "nep_tren"), 1);
    eq(api.rowIndexBySlug(makeItems(), "khong_co"), -1);

    // Danh sách chọn "dữ liệu đem tra" của đường cũ.
    const options = api.buildInputOptions({
        items: [{ slug: "nep_bi_an", width: 10 }], variables: [], item_fields: ["width"],
    });
    eq(options[0].label, "Dòng chưa đặt tên (Dòng 1) — Rộng (mm)");
    assert(options[0].label.indexOf("nep_bi_an") === -1, "⛔ slug trong nhãn");

    // Danh sách chọn dòng nguồn của quy tắc ROW.
    const widthRule = {
        rule_code: "R-W", input_variable: "width", input_scope: "ROW",
        input_label: "Rộng", input_unit: "mm", result_type: "NUMBER",
    };
    const rows = api.buildRuleRowOptions(widthRule, [
        { line_name: "Nẹp trên", slug: "nep_tren", width: 100 },
        { slug: "khong_ten", width: 50 },
    ]);
    eq(rows.map((o) => o.line_name), ["Nẹp trên", "Dòng chưa đặt tên (Dòng 2)"]);
    assert(rows.every((o) => o.label.indexOf("khong_ten") === -1),
        "⛔ slug trong nhãn dòng nguồn");
}

check("Nhãn dòng — line_name, chưa đặt tên ⇒ 'Dòng chưa đặt tên (Dòng N)', ⛔ slug", () => {
    testRowDisplayName(helper);
});

check("ĐỐI CHỨNG ÂM — rowDisplayName (rơi về slug)", () => {
    const broken = Object.assign({}, helper, {
        rowDisplayName(row) {
            return String((row && (row.line_name || row.slug)) || "");
        },
    });
    mustFail(() => testRowDisplayName(broken), "lộ slug khi dòng chưa đặt tên");
});

// ── 8c. Biến `computed` — engine tự tính ⇒ mọi dòng BOM ───────────────────
const COMPUTED_VAR = "total_area_m2";
const COMPUTED_RULE = {
    rule_code: "R-AREA", input_variable: COMPUTED_VAR, input_scope: "ROW",
    input_label: "Diện tích", input_unit: "m²", result_type: "NUMBER",
};
const COMPUTED_VARIABLES = [
    { name: COMPUTED_VAR, label: "Diện tích", scope: "ROW", computed: 1 },
    { name: "width", label: "Rộng", scope: "ROW", computed: false },
];

function testComputedRowOptions(api) {
    const items = makeItems();
    const allSlugs = items.map((r) => r.slug);

    // Server CŨ (không có cờ) ⇒ giữ hành vi cũ: không dòng nào có giá trị
    // `total_area_m2` ⇒ danh sách rỗng.
    eq(api.buildRuleRowOptions(COMPUTED_RULE, items), [],
        "thiếu cờ computed ⇒ hành vi cũ");
    eq(api.buildRuleRowOptions(
        COMPUTED_RULE, items, { variables: COMPUTED_VARIABLES.filter((v) => v.name !== COMPUTED_VAR) }
    ), [], "biến không có trong danh mục ⇒ hành vi cũ");

    // Có cờ computed ⇒ MỌI dòng, ⛔ lọc theo field kính.
    const options = api.buildRuleRowOptions(COMPUTED_RULE, items, {
        variables: COMPUTED_VARIABLES,
    });
    eq(options.map((o) => o.slug), allSlugs, "computed ⇒ liệt kê mọi dòng BOM");
    assert(options.every((o) => o.computed === true), "option phải mang cờ computed");
    assert(options.every((o) => o.sample_value === null),
        "engine tự tính ⇒ chưa có mẫu thử, ⛔ đoán");
    eq(options[0].label, "Kính trên — Diện tích (m²)");

    // Metadata quy tắc mang cờ cũng đủ.
    const viaMeta = api.buildRuleRowOptions(
        Object.assign({}, COMPUTED_RULE, { input_computed: 1 }), items);
    eq(viaMeta.map((o) => o.slug), allSlugs, "cờ trên metadata quy tắc");

    // Ghi chú giải thích vì sao mời mọi dòng.
    const note = api.ruleRowComputedNote(COMPUTED_RULE, { variables: COMPUTED_VARIABLES });
    assert(note.indexOf("Hệ thống tự tính") !== -1, "thiếu câu giải thích");
    assert(note.indexOf("Diện tích") !== -1, "phải kèm nhãn biến");
    eq(api.ruleRowComputedNote(COMPUTED_RULE, { variables: [] }), "",
        "chưa biết cờ ⇒ ⛔ bịa ghi chú");
    eq(api.ruleRowComputedNote(ROW_RULE, { variables: COMPUTED_VARIABLES }), "",
        "quy tắc biến thường ⇒ không ghi chú");

    // Đường hộp chèn công thức truyền danh mục biến xuống.
    const insert = api.buildRuleInsertOptions({
        rule: COMPUTED_RULE, items: items,
        variables: makeVariables(), input_variables: COMPUTED_VARIABLES,
        item_fields: ["width", "height"],
    });
    eq(insert.map((o) => o.slug), allSlugs, "hộp chèn công thức cũng phải mời mọi dòng");

    eq(api.ruleInputVariableComputed(COMPUTED_VARIABLES, COMPUTED_VAR), true);
    eq(api.ruleInputVariableComputed(COMPUTED_VARIABLES, "width"), false);
    eq(api.ruleInputVariableComputed(COMPUTED_VARIABLES, "khong_co"), null,
        "biến không có trong danh mục ⇒ chưa biết");
    eq(api.ruleInputVariableComputed(null, COMPUTED_VAR), null, "chưa có danh mục ⇒ chưa biết");
}

check("Biến computed — liệt kê MỌI dòng BOM; thiếu cờ ⇒ giữ hành vi cũ", () => {
    testComputedRowOptions(helper);
});

check("ĐỐI CHỨNG ÂM — buildRuleRowOptions (bỏ qua cờ computed)", () => {
    // Bản hỏng = hàm cũ: luôn lọc theo field kính / giá trị dòng.
    const broken = Object.assign({}, helper, {
        buildRuleRowOptions(rule, items) {
            const variable = helper.ruleInputVariable(rule);
            if (!variable) return [];
            const label = helper.ruleInputLabel(rule);
            const out = [];
            (Array.isArray(items) ? items : []).forEach((row, idx) => {
                if (!row || !row.slug) return;
                if (!helper.rowSupportsVariable(row, variable)) return;
                out.push({
                    slug: row.slug, line_name: helper.rowDisplayName(row, idx),
                    value: helper.ruleRowOptionExpr(row.slug, variable),
                    label: helper.rowDisplayName(row, idx) + " — " + label,
                    group: "Dòng trong BOM", sample_value: helper.rowVariableValue(row, variable),
                });
            });
            return out;
        },
        ruleRowComputedNote() { return ""; },
        ruleInputVariableComputed() { return null; },
        buildRuleInsertOptions: helper.buildRuleInsertOptions,
        rowDisplayName: helper.rowDisplayName,
        rowIndexBySlug: helper.rowIndexBySlug,
    });
    mustFail(() => testComputedRowOptions(broken), "bỏ qua cờ computed");
});

// ── 8d. Câu cảnh báo thiếu giá trị / quy tắc đã tắt-xoá ───────────────────
function testNotices(api) {
    const missing = api.variableMissingNoticeText("Chiều cao (mm)");
    assert(missing.indexOf("Chưa có Chiều cao (mm) cho lượt tính này") !== -1,
        "câu phải nêu ĐÚNG nhãn biến thiếu: " + missing);
    assert(missing.indexOf("tham số báo giá") !== -1, "phải kèm việc cần làm");
    const html = api.variableMissingNoticeHtml("Chiều cao (mm)");
    assert(html.indexOf('data-role="variable-missing"') !== -1, "thiếu khối cảnh báo");
    assert(html.indexOf("#b45309") !== -1, "phải là màu hổ phách");

    assert(api.ruleStateNoticeText("inactive").indexOf("đã bị tắt") !== -1);
    assert(api.ruleStateNoticeText("missing").indexOf("không còn tồn tại") !== -1);
    assert(api.ruleStateNoticeText("unknown").indexOf("Chưa kiểm tra được") !== -1);
    assert(api.ruleStateNoticeText("active", { not_listed: true })
        .indexOf("không trả về số lượng") !== -1, "đang bật nhưng không trong danh sách");
    eq(api.ruleStateNoticeText("active"), "", "quy tắc bình thường ⇒ không cảnh báo");
    eq(api.ruleStateNoticeText(""), "", "chưa kiểm tra xong ⇒ không bịa");
    // Mọi câu ⛔ mã kỹ thuật.
    ["inactive", "missing", "unknown"].forEach((state) => {
        const text = api.ruleStateNoticeText(state);
        ["AL Rule", "is_active", "result_type"].forEach((token) => {
            assert(text.indexOf(token) === -1, "câu ⛔ chứa mã kỹ thuật: " + text);
        });
    });

    assert(typeof api.fetchRuleState("X").then === "function",
        "fetchRuleState phải trả Promise (Desk mới gọi được)");
}

check("Cảnh báo — thiếu giá trị biến / quy tắc tắt-xoá: câu + việc cần làm", () => {
    testNotices(helper);
});

check("ĐỐI CHỨNG ÂM — ruleStateNoticeText (đoán 'không tồn tại' khi chưa kiểm tra được)", () => {
    const broken = {
        variableMissingNoticeText: helper.variableMissingNoticeText,
        variableMissingNoticeHtml: helper.variableMissingNoticeHtml,
        ruleStateNoticeText(state) {
            // Bản hỏng: mọi trạng thái lạ đều đổ cho "đã bị xoá".
            return String(state || "").toLowerCase() === "inactive"
                ? "Quy tắc đang chọn đã bị tắt."
                : "Quy tắc đang chọn không còn tồn tại.";
        },
        fetchRuleState: helper.fetchRuleState,
    };
    mustFail(() => testNotices(broken), "đoán bừa khi chưa kiểm tra được");
});

// ═══════════════════════════════════════════════════════════════════════════
// 7. ĐIỀU KIỆN TRA — xem ngay tại chỗ chọn quy tắc (chặng 4)
//    Owner 2026-11-25: chọn nẹp theo độ dày kính ⇒ thấy các điều kiện tra
//    ngay dưới câu quy tắc, ⛔ phải mở form `AL Rule`.
// ═══════════════════════════════════════════════════════════════════════════
const THRESHOLD_DOC = {
    name: "RULE-NEP-DAY",
    rule_code: "RULE-NEP-DAY",
    rule_type: "THRESHOLD",
    result_type: "ITEM",
    input_label: "Độ dày kính",
    input_unit: "mm",
    output_label: "Nẹp",
    threshold_rows: [
        { from_value: 0, to_value: 10, result_item: "N10", result_item_name: "Nẹp nhôm 10" },
        { from_value: 10, to_value: 20, result_item: "N20" },
        { from_value: 20, to_value: 30, result_item: "N30", result_item_name: "Nẹp nhôm 30" },
        { from_value: 30, to_value: 40, result_item: "N40" },
        { from_value: 40, to_value: null, result_item: "N50", result_item_name: "Nẹp nhôm 50" },
    ],
};

const GAP_DOC = {
    name: "RULE-GAP",
    rule_type: "THRESHOLD",
    result_type: "NUMBER",
    input_label: "Độ dày kính",
    input_unit: "mm",
    output_label: "số nẹp",
    threshold_rows: [
        { from_value: 0, to_value: 10, result_value: 5 },
        { from_value: 20, to_value: 30, result_value: 7 },
    ],
};

const OVERLAP_DOC = {
    name: "RULE-OVERLAP",
    rule_type: "THRESHOLD",
    result_type: "NUMBER",
    input_label: "Độ dày kính",
    input_unit: "mm",
    threshold_rows: [
        { from_value: 0, to_value: 20, result_value: 1 },
        { from_value: 10, to_value: 30, result_value: 2 },
    ],
};

const LOOKUP_DOC = {
    name: "RULE-KEO",
    rule_type: "LOOKUP",
    result_type: "ITEM",
    input_label: "Loại kính",
    output_label: "Keo",
    lookup_rows: [
        { key_field: "Kính cường lực", result_item: "KEO-A", result_item_name: "Keo A" },
        { key_field: "", result_item: "KEO-B" },
        { key_field: "Kính dán", result_item: "KEO-C" },
    ],
};

function testConditionLines(api) {
    // THRESHOLD: 3 dòng đầu đúng dạng câu, `to_value` trống ⇒ "≥".
    const lines = api.ruleConditionLines(THRESHOLD_DOC);
    eq(lines.length, 5, "phải đọc đủ 5 điều kiện");
    eq(lines[0], "0–10 mm → Nẹp nhôm 10 (N10)", "dải có tên vật tư");
    eq(lines[1], "10–20 mm → N20", "thiếu tên ⇒ dùng mã");
    eq(lines[2], "20–30 mm → Nẹp nhôm 30 (N30)", "dải giữa");
    eq(lines[4], "≥ 40 mm → Nẹp nhôm 50 (N50)", "to_value trống ⇒ '≥'");

    // Tên vật tư từ `opts.item_names` khi dòng chưa có sẵn tên.
    eq(api.ruleConditionLines(THRESHOLD_DOC, { item_names: { N20: "Nẹp nhôm 20" } })[1],
        "10–20 mm → Nẹp nhôm 20 (N20)", "tên vật tư tra được phải hiện kèm mã");

    // Đơn vị rỗng ⇒ ⛔ khoảng trắng thừa.
    const noUnit = api.ruleConditionLines({
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        threshold_rows: [{ from_value: 0, to_value: 10, result_value: 5 }],
    });
    eq(noUnit, ["0–10 → 5"], "không có đơn vị ⇒ không thừa khoảng trắng");

    // Kết quả NUMBER phải định dạng số người đọc (10.5 → "10,5").
    eq(api.ruleConditionLines({
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        input_unit: "mm",
        threshold_rows: [{ from_value: 10.5, to_value: 20, result_value: 10.5 }],
    }), ["10,5–20 mm → 10,5"], "số thập phân dùng dấu phẩy");

    // Dòng thiếu "Từ" là dòng đang khai dở ⇒ bỏ (⛔ bịa điều kiện).
    eq(api.ruleConditionLines({
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        threshold_rows: [{ to_value: 10, result_value: 1 }, { from_value: 0, to_value: 5, result_value: 2 }],
    }), ["0–5 → 2"], "dòng khai dở bị bỏ");

    // LOOKUP: "Giá trị cần tra → kết quả"; dòng thiếu khoá bị bỏ.
    eq(api.ruleConditionLines(LOOKUP_DOC),
        ["Kính cường lực → Keo A (KEO-A)", "Kính dán → KEO-C"],
        "tra bảng dùng đúng khoá + kết quả");

    // Thiếu bảng ⇒ đúng câu "Chưa đọc được…" (⛔ đoán số).
    const unreadable = api.ruleConditionLines({
        rule_type: "THRESHOLD", result_type: "NUMBER",
    });
    eq(unreadable.length, 1, "thiếu bảng ⇒ 1 câu, ⛔ danh sách rỗng câm lặng");
    assert(unreadable[0].indexOf("Chưa đọc được điều kiện") !== -1, unreadable[0]);
    assert(unreadable[0].indexOf("mở quy tắc để xem") !== -1, unreadable[0]);
    // Loại quy tắc lạ cũng vậy.
    assert(api.ruleConditionLines({ rule_type: "???" })[0]
        .indexOf("Chưa đọc được điều kiện") !== -1, "loại lạ phải nói chưa đọc được");

    // Bảng có nhưng chưa dòng nào đọc được ⇒ [] (caller nói "chưa có điều kiện").
    eq(api.ruleConditionLines({ rule_type: "LOOKUP", lookup_rows: [] }), [],
        "bảng rỗng ⇒ không điều kiện nào");

    // Dòng khai dở (chưa có kết quả) ⇒ gọi tên kết quả theo `output_label`,
    // thiếu nhãn ⇒ câu trung tính, ⛔ đoán số.
    eq(api.ruleConditionLines({
        rule_type: "LOOKUP", result_type: "NUMBER", output_label: "Số keo",
        lookup_rows: [{ key_field: "Kính dán", result_value: "" }],
    }), ["Kính dán → chưa có số keo"], "kết quả trống ⇒ nhãn từ quy tắc");
    eq(api.ruleConditionLines({
        rule_type: "THRESHOLD", result_type: "NUMBER",
        threshold_rows: [{ from_value: 0, to_value: 5, result_value: "" }],
    }), ["0–5 → chưa có kết quả"], "thiếu output_label ⇒ câu trung tính");

    // ⛔ mã quy tắc / tên field kỹ thuật trong câu điều kiện.
    const all = lines.concat(api.ruleConditionLines(LOOKUP_DOC));
    all.forEach((line) => {
        ["RULE-", "threshold_rows", "lookup_rows", "result_value",
            "input_label", "from_value"].forEach((token) => {
            assert(line.indexOf(token) === -1, "câu lộ mã kỹ thuật: " + line);
        });
    });
}

check("Điều kiện tra — câu mỗi dòng (THRESHOLD/LOOKUP, '≥', đơn vị, ITEM)", () => {
    testConditionLines(helper);
});

check("ĐỐI CHỨNG ÂM — ruleConditionLines (in giá trị thô, hardcode mm)", () => {
    const broken = {
        ruleConditionLines(rule) {
            // Bản hỏng: ghép giá trị thô + hardcode đơn vị, ⛔ câu người đọc.
            const rows = rule.threshold_rows || rule.lookup_rows || [];
            return rows.map((row) => {
                if (row.key_field !== undefined) {
                    return row.key_field + " => " + row.result_item;
                }
                return row.from_value + "-" + row.to_value + " mm => " + row.result_item;
            });
        },
    };
    mustFail(() => testConditionLines(broken), "câu thô, thiếu câu 'Chưa đọc được…'");
});

function testConditionSummary(api) {
    const summary = api.ruleConditionSummary(THRESHOLD_DOC);
    eq(summary.count, 5, "đếm đủ điều kiện");
    eq(summary.spanText, "0 mm trở lên", "dải mở tới trên cùng");
    eq(summary.gapText, "", "không khe hở ⇒ ⛔ cảnh báo");
    eq(summary.overlapText, "", "không chồng lấn ⇒ ⛔ cảnh báo");

    const gap = api.ruleConditionSummary(GAP_DOC);
    eq(gap.count, 2);
    eq(gap.spanText, "0–30 mm");
    assert(gap.gapText.indexOf("Còn trống 10–20 mm") !== -1, "phải chỉ đúng khe hở: " + gap.gapText);
    eq(gap.overlapText, "");

    const overlap = api.ruleConditionSummary(OVERLAP_DOC);
    assert(overlap.overlapText.indexOf("Dải chồng lấn") !== -1, overlap.overlapText);
    assert(overlap.overlapText.indexOf("0–20 mm") !== -1, overlap.overlapText);
    assert(overlap.overlapText.indexOf("10–30 mm") !== -1, overlap.overlapText);
    // UX1 chấm vòng 3: engine xếp dải theo mốc `Từ` TĂNG DẦN, lấy dòng khớp
    // ĐẦU TIÊN ⇒ dải có mốc bắt đầu THẤP HƠN thắng. Câu cũ "dải khai trước
    // được chọn" nói SAI ai thắng (thứ tự khai trong bảng không quyết định).
    assert(overlap.overlapText.indexOf("mốc bắt đầu thấp hơn được chọn") !== -1,
        "phải nói ĐÚNG ai thắng: " + overlap.overlapText);
    assert(overlap.overlapText.indexOf("khai trước") === -1,
        "⛔ nói 'dải khai trước được chọn' (sai): " + overlap.overlapText);
    eq(overlap.gapText, "");

    // LOOKUP: chỉ đếm, ⛔ bịa "phạm vi số".
    const lookup = api.ruleConditionSummary(LOOKUP_DOC);
    eq(lookup.count, 2);
    eq(lookup.spanText, "");
    eq(lookup.gapText, "");
    eq(lookup.overlapText, "");

    // Quy tắc thiếu bảng ⇒ mọi trường rỗng, ⛔ đoán số.
    eq(api.ruleConditionSummary({ rule_type: "THRESHOLD" }),
        { count: 0, spanText: "", gapText: "", overlapText: "" });

    // Chạm biên KHÔNG phải chồng lấn (0–10 và 10–20 liền nhau).
    const touching = api.ruleConditionSummary({
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        input_unit: "mm",
        threshold_rows: [
            { from_value: 0, to_value: 10, result_value: 1 },
            { from_value: 10, to_value: 20, result_value: 2 },
        ],
    });
    eq(touching.gapText, "", "chạm biên không phải khe hở");
    eq(touching.overlapText, "", "chạm biên không phải chồng lấn");
}

check("Điều kiện tra — thống kê (số điều kiện, phạm vi, khe hở, chồng lấn)", () => {
    testConditionSummary(helper);
});

check("ĐỐI CHỨNG ÂM — ruleConditionSummary (bỏ khe hở/chồng lấn)", () => {
    const broken = {
        ruleConditionSummary(rule) {
            const rows = rule.threshold_rows || [];
            return { count: rows.length, spanText: "", gapText: "", overlapText: "" };
        },
    };
    mustFail(() => testConditionSummary(broken), "không báo khe hở/chồng lấn");
});

check("ĐỐI CHỨNG ÂM — câu chồng lấn 'dải khai trước được chọn' phải bị bắt đỏ", () => {
    // Bản hỏng: giữ đúng câu cũ (nói sai ai thắng).
    const broken = Object.assign({}, helper, {
        ruleConditionSummary(rule) {
            const summary = helper.ruleConditionSummary(rule);
            if (summary.overlapText) {
                summary.overlapText = summary.overlapText.replace(
                    "dải có mốc bắt đầu thấp hơn được chọn",
                    "dải khai trước được chọn");
            }
            return summary;
        },
    });
    mustFail(() => testConditionSummary(broken), "câu nói sai ai thắng");
});

function testConditionPreview(api) {
    const html = api.ruleConditionPreviewHtml(THRESHOLD_DOC, { max: 3 });
    // Câu mở đầu dùng NHÃN QUY TẮC tự khai (⛔ hardcode "Độ dày kính").
    assert(html.indexOf("Quy tắc tra theo <b>Độ dày kính</b>:") !== -1,
        "thiếu câu mở đầu: " + html);
    // Chỉ 3 điều kiện đầu + "… và N nữa".
    eq((html.match(/<li>/g) || []).length, 3, "chỉ hiện tối đa 3 điều kiện");
    assert(html.indexOf("0–10 mm → Nẹp nhôm 10 (N10)") !== -1, "thiếu điều kiện đầu");
    assert(html.indexOf("… và 2 nữa") !== -1, "thiếu phần còn lại: " + html);
    assert(html.indexOf("5 điều kiện") !== -1, "thiếu số điều kiện");
    assert(html.indexOf("0 mm trở lên") !== -1, "thiếu phạm vi đang phủ");
    assert(html.indexOf('href="/app/al-rule/RULE-NEP-DAY"') !== -1,
        "thiếu link Xem tất cả");
    assert(html.indexOf("Xem tất cả") !== -1, "link phải có nhãn người đọc");

    // `max` tuỳ biến; ít điều kiện hơn max ⇒ ⛔ "… và 0 nữa".
    const one = api.ruleConditionPreviewHtml({
        name: "RULE-1", rule_type: "LOOKUP", result_type: "NUMBER",
        input_label: "Loại kính",
        lookup_rows: [{ key_field: "Kính dán", result_value: 2 }],
    });
    eq((one.match(/<li>/g) || []).length, 1);
    assert(one.indexOf("… và") === -1, "không thừa dòng: " + one);

    // Nhãn quy tắc chưa khai ⇒ "dữ liệu quy tắc đọc", ⛔ mã biến.
    const unlabeled = api.ruleConditionPreviewHtml({
        name: "RULE-U", input_variable: "H_mm", rule_type: "LOOKUP",
        result_type: "NUMBER", lookup_rows: [{ key_field: "A", result_value: 1 }],
    });
    assert(unlabeled.indexOf("dữ liệu quy tắc đọc") !== -1, unlabeled);
    assert(unlabeled.indexOf("H_mm") === -1, "lộ mã biến: " + unlabeled);

    // Tiêu đề "compact" cho hộp chọn quy tắc: "Tra theo: … · N điều kiện:".
    const compact = api.ruleConditionPreviewHtml(GAP_DOC, { heading: "compact" });
    assert(compact.indexOf("Tra theo: <b>Độ dày kính</b> · 2 điều kiện:") !== -1,
        "thiếu tiêu đề gọn: " + compact);
    assert(compact.indexOf("Còn trống 10–20 mm") !== -1, "mất cảnh báo khe hở");

    // Escape toàn bộ: nhãn + khoá + mã quy tắc.
    const evil = api.ruleConditionPreviewHtml({
        name: "RULE/../<x>&y",
        rule_type: "LOOKUP",
        result_type: "NUMBER",
        input_label: "<script>alert(1)</script>",
        lookup_rows: [{ key_field: "<b>khoá</b>", result_value: 1 }],
    });
    assert(evil.indexOf("<script>") === -1, "chưa escape nhãn: " + evil);
    assert(evil.indexOf("&lt;script&gt;") !== -1, "nhãn phải escape");
    assert(evil.indexOf("<b>khoá</b>") === -1, "chưa escape khoá: " + evil);
    assert(evil.indexOf("&lt;b&gt;khoá&lt;/b&gt;") !== -1, "khoá phải escape");
    // Mã quy tắc CHỈ nằm trong URL, và URL phải encode.
    assert(evil.indexOf("RULE/../") === -1, "mã quy tắc lộ ra ngoài URL: " + evil);
    assert(evil.indexOf('href="/app/al-rule/RULE%2F..%2F%3Cx%3E%26y"') !== -1,
        "URL chưa encode: " + evil);

    // Không có mã ⇒ ⛔ link (⛔ href rỗng).
    const noCode = api.ruleConditionPreviewHtml({
        rule_type: "LOOKUP", result_type: "NUMBER",
        lookup_rows: [{ key_field: "A", result_value: 1 }],
    });
    assert(noCode.indexOf("Xem tất cả") === -1, "không có mã ⇒ ⛔ link: " + noCode);

    // Thiếu bảng ⇒ câu "Chưa đọc được…" + link; ⛔ đoán điều kiện.
    const unreadable = api.ruleConditionPreviewHtml({
        name: "RULE-X", rule_type: "THRESHOLD", input_label: "Độ dày kính",
    });
    assert(unreadable.indexOf("Chưa đọc được điều kiện") !== -1, unreadable);
    assert(unreadable.indexOf("/app/al-rule/RULE-X") !== -1, "vẫn phải có link mở quy tắc");
    assert(unreadable.indexOf("<li>") === -1, "⛔ bịa dòng điều kiện");

    // Không có doc ⇒ chuỗi rỗng (caller ẩn khối, ⛔ làm vỡ form).
    eq(api.ruleConditionPreviewHtml(null), "", "không có quy tắc ⇒ không vẽ gì");

    // Mã vật tư của kết quả (để tra tên) — chỉ quy tắc ITEM.
    eq(api.ruleConditionItemCodes(THRESHOLD_DOC), ["N10", "N20", "N30", "N40", "N50"]);
    eq(api.ruleConditionItemCodes(GAP_DOC), [], "kết quả số ⇒ không có mã vật tư");
    eq(api.ruleConditionItemCodes({
        rule_type: "LOOKUP", result_type: "ITEM",
        lookup_rows: [{ key_field: "A", result_item: "X" }, { key_field: "B", result_item: "X" }],
    }), ["X"], "mã vật tư trùng chỉ lấy một lần");
}

check("Điều kiện tra — khối HTML (3 dòng đầu, còn lại, link encode, escape)", () => {
    testConditionPreview(helper);
});

check("ĐỐI CHỨNG ÂM — ruleConditionPreviewHtml (in thô, không cắt, không link)", () => {
    const broken = {
        ruleConditionLines: helper.ruleConditionLines,
        ruleConditionItemCodes: helper.ruleConditionItemCodes,
        ruleConditionPreviewHtml(rule, opts) {
            // Bản hỏng: nối thẳng câu điều kiện, ⛔ escape, ⛔ giới hạn, ⛔ link.
            return helper.ruleConditionLines(rule, opts).join("<br>");
        },
    };
    mustFail(() => testConditionPreview(broken), "HTML thô, không cắt, không link");
});

check("Điều kiện tra — bản dự phòng khớp AlumGlassRuleConditions (khe hở/chồng lấn/phạm vi)", () => {
    const docs = [THRESHOLD_DOC, GAP_DOC, OVERLAP_DOC, {
        name: "RULE-OPEN",
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        input_unit: "mm",
        threshold_rows: [
            { from_value: 0, to_value: 10, result_value: 1 },
            { from_value: 12, to_value: 18, result_value: 2 },
            { from_value: 15, to_value: null, result_value: 3 },
        ],
    }];
    // Form BOM KHÔNG nạp `al_rule.js` ⇒ bản dự phòng phải chạy được một mình.
    delete global.AlumGlassRuleConditions;
    const withoutShared = docs.map((doc) => helper.ruleConditionSummary(doc));

    // Có module dùng chung ⇒ dùng nó, và kết quả phải Y HỆT bản dự phòng.
    global.AlumGlassRuleConditions = require(path.join(
        __dirname, "..", "..", "al_formula_rules", "doctype", "al_rule", "al_rule.js"));
    const withShared = docs.map((doc) => helper.ruleConditionSummary(doc));
    eq(withShared, withoutShared, "hai bản thuật toán phải ra cùng kết quả");
    assert(withShared[3].gapText.indexOf("10–12 mm") !== -1,
        "khe hở phải đúng: " + withShared[3].gapText);
    assert(withShared[3].overlapText !== "", "phải bắt được chồng lấn");
});

// ═══════════════════════════════════════════════════════════════════════════
// 9. UX1 chấm vòng 3 — ô cột "Đến" + nhãn enum tiếng Việt
// ═══════════════════════════════════════════════════════════════════════════

// 9a. Cột "Đến" của bảng điều kiện trong hộp "Thử tra": dải MỞ ⇒ "trở lên"
//     (khớp nhãn cột form "bỏ trống = trở lên"), ⛔ "—".
function testRangeToCell(api) {
    eq(api.rangeToCellText(20, null), "trở lên",
        "Đến trống + có Từ ⇒ 'trở lên'");
    eq(api.rangeToCellText(20, ""), "trở lên", "chuỗi rỗng cũng là dải mở");
    eq(api.rangeToCellText(20, undefined), "trở lên", "undefined cũng vậy");
    eq(api.rangeToCellText(0, 10), "10", "dải đóng ⇒ hiện số 'Đến'");
    eq(api.rangeToCellText(1000, 2000), "2000", "dải đóng, số lớn");
    eq(api.rangeToCellText(null, 10), "10", "chỉ có Đến ⇒ hiện số");
    eq(api.rangeToCellText(null, null), "—", "không có Từ lẫn Đến ⇒ '—'");
    eq(api.rangeToCellText(undefined, undefined), "—", "undefined ⇒ '—'");
}

check("rangeToCellText — dải mở 'trở lên' / dải đóng / rỗng", () => {
    testRangeToCell(helper);
});

check("ĐỐI CHỨNG ÂM — rangeToCellText (dải mở in '—')", () => {
    // Bản hỏng đúng như trước sửa: chỉ format `to`, rỗng ⇒ "—".
    const broken = {
        rangeToCellText(from, to) {
            if (to === null || to === undefined || to === "") return "—";
            return String(to);
        },
    };
    mustFail(() => testRangeToCell(broken), "dải mở hiện '—'");
});

// 9b. Nhãn enum tiếng Việt — form (options {label,value}) + danh sách (formatter)
//     dùng CHUNG một bản. Giá trị LƯU ⛔ đổi.
function testEnumLabels(api) {
    eq(api.ruleTypeOptions(), [
        { value: "CONSTANT", label: "Hằng số" },
        { value: "THRESHOLD", label: "Tra theo dải" },
        { value: "LOOKUP", label: "Tra theo bảng" },
    ], "options kiểu quy tắc — đúng thứ tự + GIÁ TRỊ LƯU giữ nguyên");
    eq(api.ruleResultTypeOptions(), [
        { value: "NUMBER", label: "Số" },
        { value: "ITEM", label: "Mã vật tư" },
    ], "options loại kết quả");
    eq(api.ruleTypeLabel("THRESHOLD"), "Tra theo dải");
    eq(api.ruleTypeLabel("lookup"), "Tra theo bảng", "⛔ phân biệt hoa/thường");
    eq(api.ruleResultTypeLabel("ITEM"), "Mã vật tư");
    eq(api.ruleResultTypeLabel("NUMBER"), "Số");
    eq(api.ruleTypeLabel(""), "", "rỗng ⇒ rỗng");
    eq(api.ruleTypeLabel("SOMETHING_NEW"), "SOMETHING_NEW",
        "enum lạ ⇒ giữ nguyên, ⛔ ô trống câm lặng");
    // ⛔ đổi giá trị lưu (server/patches đang dựa vào chuỗi tiếng Anh).
    const values = api.ruleTypeOptions().map((option) => option.value);
    eq(values, ["CONSTANT", "THRESHOLD", "LOOKUP"], "giá trị lưu ⛔ đổi");
}

check("Nhãn enum tiếng Việt — options + label, giá trị lưu giữ nguyên", () => {
    testEnumLabels(helper);
});

check("ĐỐI CHỨNG ÂM — nhãn enum (hiện nguyên CONSTANT/THRESHOLD/LOOKUP)", () => {
    // Bản hỏng: trả nguyên giá trị tiếng Anh làm nhãn.
    const broken = {
        ruleTypeOptions() {
            return ["CONSTANT", "THRESHOLD", "LOOKUP"].map((value) => ({ value, label: value }));
        },
        ruleResultTypeOptions() {
            return ["NUMBER", "ITEM"].map((value) => ({ value, label: value }));
        },
        ruleTypeLabel(value) { return String(value || ""); },
        ruleResultTypeLabel(value) { return String(value || ""); },
    };
    mustFail(() => testEnumLabels(broken), "nhãn vẫn là enum tiếng Anh");
});

// ═══════════════════════════════════════════════════════════════════════════
// 10. UX1 vòng 4 — nhãn TRÙNG TÊN BIẾN (dữ liệu cũ `input_label = total_thick_mm`)
// ═══════════════════════════════════════════════════════════════════════════
function testReadableInputLabel(api) {
    // Hàm chung: rỗng / trùng biến / trùng khác hoa-thường / nhãn thật.
    eq(api.readableInputLabel("", "total_thick_mm"), "dữ liệu quy tắc đọc",
        "nhãn rỗng");
    eq(api.readableInputLabel("total_thick_mm", "total_thick_mm"),
        "dữ liệu quy tắc đọc", "nhãn trùng tên biến");
    eq(api.readableInputLabel("  Total_Thick_MM ", "total_thick_mm"),
        "dữ liệu quy tắc đọc", "trùng khác hoa/thường + khoảng trắng");
    eq(api.readableInputLabel("Độ dày kính", "total_thick_mm"), "Độ dày kính",
        "nhãn thật");
    eq(api.readableInputLabel("", ""), "dữ liệu quy tắc đọc",
        "rỗng cả hai ⇒ mặc định 'dữ liệu quy tắc đọc'");
    eq(api.readableInputLabel("", "", "giá trị đem tra"), "giá trị đem tra",
        "fallback do caller truyền");
    eq(api.readableInputLabel("total_thick", "total_thick_mm"), "total_thick",
        "khác tên biến ⇒ giữ nguyên, ⛔ đoán bừa");

    // (b) Nhãn quy tắc — đo thật của UX1: "total_thick_mm (mm)".
    eq(api.ruleInputLabel({
        input_label: "total_thick_mm",
        input_variable: "total_thick_mm",
        input_unit: "mm",
    }), "dữ liệu quy tắc đọc (mm)", "ruleInputLabel phải làm sạch rồi mới ghép đơn vị");
    eq(api.ruleInputLabel({
        input_label: "Độ dày kính", input_variable: "total_thick_mm", input_unit: "mm",
    }), "Độ dày kính (mm)", "nhãn thật + đơn vị");
    eq(api.ruleInputLabel({
        input_label: "", input_variable: "", input_unit: "mm",
    }), "giá trị đem tra (mm)", "chưa khai biến lẫn nhãn ⇒ câu chung");

    // (c) Câu mở đầu khối điều kiện — đo thật: "Tra theo: total_thick_mm · 2 điều kiện:".
    const html = api.ruleConditionPreviewHtml({
        name: "RULE-OLD",
        rule_type: "THRESHOLD",
        result_type: "NUMBER",
        input_unit: "mm",
        input_label: "total_thick_mm",
        input_variable: "total_thick_mm",
        threshold_rows: [
            { from_value: 0, to_value: 10, result_value: 1 },
            { from_value: 10, to_value: 20, result_value: 2 },
        ],
    }, { max: 3, heading: "compact" });
    assert(html.indexOf("Tra theo: <b>dữ liệu quy tắc đọc</b> · 2 điều kiện:") !== -1,
        "câu mở đầu phải làm sạch nhãn: " + html);
    assert(html.indexOf("total_thick_mm") === -1,
        "⛔ mã biến trong khối điều kiện: " + html);

    // Khối dựng từ metadata CHƯA đọc đủ doc (thiếu field) cũng không được lọt.
    const summary = api.ruleSummary({
        input_label: "width", input_variable: "width", output_label: "",
    });
    assert(summary.indexOf("width") === -1, "ruleSummary ⛔ mã biến: " + summary);
}

check("readableInputLabel / ruleInputLabel / câu điều kiện — trùng tên biến", () => {
    testReadableInputLabel(helper);
});

check("ĐỐI CHỨNG ÂM — nhãn trùng tên biến (chỉ xử lý ca rỗng)", () => {
    // Bản hỏng đúng như trước sửa: chỉ xử lý nhãn RỖNG, nhãn trùng biến lọt.
    const broken = {
        readableInputLabel(label, variable, fallback) {
            const text = String(label === null || label === undefined ? "" : label).trim();
            if (!text) {
                return (fallback === null || fallback === undefined)
                    ? "dữ liệu quy tắc đọc" : String(fallback);
            }
            return text;
        },
        ruleInputLabel(rule) {
            if (!rule) return "giá trị đem tra";
            const variable = String(rule.input_variable || "").trim();
            let label = this.readableInputLabel(rule.input_label, variable,
                variable ? "dữ liệu quy tắc đọc" : "giá trị đem tra");
            const unit = String(rule.input_unit || "").trim();
            if (unit && label.indexOf("(") === -1) label += " (" + unit + ")";
            return label;
        },
        ruleConditionPreviewHtml(ruleDoc, opts) {
            const label = String(ruleDoc.input_label || "").trim() || "dữ liệu quy tắc đọc";
            return "Tra theo: <b>" + label + "</b> · 2 điều kiện:";
        },
        ruleSummary(rule) {
            return "tra theo " + (rule.input_label || rule.input_variable) + " → số";
        },
    };
    mustFail(() => testReadableInputLabel(broken), "nhãn trùng tên biến vẫn lọt");
});

// ═══════════════════════════════════════════════════════════════════════════
console.log("");
console.log("Kết quả: " + passed + " PASS · " + failed.length + " FAIL");
if (failed.length) {
    console.log("Ca đỏ: " + failed.join(" · "));
    process.exit(1);
}
