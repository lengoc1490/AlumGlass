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
    eq(api.parseFormulaSnippet("lookup_rule('A')").preset, "",
        "thiếu dữ liệu đem tra ⇒ chưa nhận dạng");

    eq(api.parseLookupSnippet("lookup_rule('A', f(H_mm)) * 2"),
        { code: "A", input: "f(H_mm)", multiplier: "2" }, "ngoặc lồng nhau");
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
        "filterNumberRules",
        "buildInputOptions", "buildRuleInputOptions", "validateRuleInput",
        "resolveItemValue", "findEquivalentOption", "fetchNumberRules",
        "fetchRuleForCode", "fetchOptionSample", "callPreviewRule",
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
console.log("");
console.log("Kết quả: " + passed + " PASS · " + failed.length + " FAIL");
if (failed.length) {
    console.log("Ca đỏ: " + failed.join(" · "));
    process.exit(1);
}
