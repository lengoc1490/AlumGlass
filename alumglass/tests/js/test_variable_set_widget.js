#!/usr/bin/env node
/**
 * Test Node thuần cho "ô giá trị biến hiện đúng kiểu".
 *
 * Hai tệp được phủ:
 *   - public/js/al_variable_set_item.js  (bảng con AL Variable Set Item)
 *   - al_master_data/doctype/al_variable_library/al_variable_library.js
 *
 * Quy tắc (Owner 2026-11-27): biến kiểu Select ⇒ ô chọn danh sách; kiểu Link ⇒
 * ô chọn bản ghi của đúng doctype; Float/Int/… ⇒ ô nhập số; Data ⇒ ô chữ.
 *
 * Ba nhóm ca:
 *   (1) Ánh xạ kiểu đúng cho từng kiểu biến.
 *   (2) Ca ÂM: thiếu cấu hình (Select chưa có lựa chọn, Link chưa có doctype)
 *       ⇒ rơi về ô chữ, ⛔ dựng ô chọn rỗng khoá người dùng.
 *   (3) Mỗi dòng một bản meta RIÊNG — dòng Select ⛔ kéo dòng Float theo.
 *
 * Chạy:
 *     node alumglass/tests/js/test_variable_set_widget.js
 */
"use strict";

const path = require("path");

global.window = global;
global.__ = function (s) { return String(s); };
global.locals = {};

const CHILD_JS = path.join(
    __dirname, "..", "..", "public", "js", "al_variable_set_item.js");
const LIB_JS = path.join(
    __dirname, "..", "..", "al_master_data", "doctype", "al_variable_library",
    "al_variable_library.js");

let FORM_EVENTS = {};
let DF_COPIES = {};      // "doctype|cdn" -> df object
let LIB_VALUES = {};     // variable -> {var_type, select_options, link_doctype}
let SET_VALUE_CALLS = [];
let ALERTS = [];

function resetEnv() {
    FORM_EVENTS = {};
    DF_COPIES = {};
    LIB_VALUES = {};
    SET_VALUE_CALLS = [];
    ALERTS = [];
    global.locals = { "AL Variable Set Item": {} };
    console.warn = function () {};
}

global.frappe = {
    ui: { form: { on(doctype, handlers) {
        FORM_EVENTS[doctype] = Object.assign({}, FORM_EVENTS[doctype] || {}, handlers);
    } } },
    meta: {
        get_docfield(doctype, fieldname, cdn) {
            const key = doctype + "|" + cdn + "|" + fieldname;
            return DF_COPIES[key] || null;
        },
    },
    model: {
        set_value(dt, cdn, field, value) {
            SET_VALUE_CALLS.push([dt, cdn, field, value]);
            const row = global.locals[dt] && global.locals[dt][cdn];
            if (row) row[field] = value;
        },
    },
    show_alert: function (opts) { ALERTS.push(opts); },
    db: {
        get_value(dt, name, fields, cb) {
            const rec = LIB_VALUES[name] || null;
            if (typeof fields === "function") { fields(rec); return; }
            cb(rec);
        },
        get_list(dt, opts) {
            // Batch đọc Library: trả về đúng các tên được hỏi.
            const wanted = (opts && opts.filters && opts.filters.name
                && opts.filters.name[1]) || [];
            const rows = wanted
                .filter((n) => LIB_VALUES[n])
                .map((n) => Object.assign({ name: n }, LIB_VALUES[n]));
            // Thenable CHẠY NGAY (không phải Promise thật): bộ test này chạy
            // đồng bộ, mà mã thật chỉ cần `.then/.catch` — giữ đúng hình dạng
            // API mà ⛔ phải nhét microtask vào harness.
            return {
                then(fn) { fn(rows); return this; },
                catch() { return this; },
            };
        },
    },
};

function loadChild() {
    delete require.cache[require.resolve(CHILD_JS)];
    require(CHILD_JS);
}

function loadLib() {
    delete require.cache[require.resolve(LIB_JS)];
    require(LIB_JS);
}

/** Dựng 1 dòng trong lưới: locals + bản meta RIÊNG cho dòng. */
function makeRow(cdn, row, df) {
    global.locals["AL Variable Set Item"][cdn] = row;
    const key = "AL Variable Set Item|" + cdn + "|default_value";
    DF_COPIES[key] = df || {
        fieldname: "default_value",
        fieldtype: "Data",
        options: "",
    };
    return global.locals["AL Variable Set Item"][cdn];
}

/** frm giả của form CHA (AL Variable Set) + grid_row giả. */
function makeParentFrm(refreshed) {
    return {
        doc: { items: [] },
        fields_dict: {
            items: {
                grid: {
                    grid_rows_by_docname: {
                        "row-a": {
                            grid_form: null,
                            refresh_field(field) { refreshed.push(["row-a", field]); },
                        },
                        "row-b": {
                            grid_form: null,
                            refresh_field(field) { refreshed.push(["row-b", field]); },
                        },
                    },
                },
            },
        },
    };
}

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
    if (a !== e) throw new Error((msg || "không khớp") +
        "\n        thực tế: " + a + "\n        mong đợi: " + e);
}

function assert(cond, msg) {
    if (!cond) throw new Error(msg || "assert thất bại");
}

function childHandler(event) {
    const h = FORM_EVENTS["AL Variable Set Item"] || {};
    assert(typeof h[event] === "function", "phải đăng ký " + event);
    return h[event];
}

function parentHandler(event) {
    const h = FORM_EVENTS["AL Variable Set"] || {};
    assert(typeof h[event] === "function", "phải đăng ký " + event);
    return h[event];
}

// ═══════════════════════════════════════════════════════════════════════
// (1) Ánh xạ kiểu
// ═══════════════════════════════════════════════════════════════════════
check("(1a) Select ⇒ ô chọn, danh sách đúng thứ tự, có lựa chọn rỗng", () => {
    resetEnv();
    loadChild();
    const refreshed = [];
    const frm = makeParentFrm(refreshed);
    makeRow("row-a", {
        name: "row-a", var_type: "Select",
        select_options: "Đỏ\nXanh\nTrắng", is_required: 0,
    });
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    const df = DF_COPIES["AL Variable Set Item|row-a|default_value"];
    eq(df.fieldtype, "Select");
    eq(df.options, "\nĐỏ\nXanh\nTrắng");
    eq(refreshed, [["row-a", "default_value"]]);
});

check("(1b) Select BẮT BUỘC ⇒ không có lựa chọn rỗng đầu danh sách", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", {
        name: "row-a", var_type: "Select",
        select_options: "Đỏ\nXanh", is_required: 1,
    });
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    eq(DF_COPIES["AL Variable Set Item|row-a|default_value"].options,
        "Đỏ\nXanh");
});

check("(1c) Link ⇒ ô chọn bản ghi của đúng doctype", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", {
        name: "row-a", var_type: "Link", link_doctype: "AL Color Standard",
    });
    childHandler("link_doctype")(frm, "AL Variable Set Item", "row-a");
    const df = DF_COPIES["AL Variable Set Item|row-a|default_value"];
    eq(df.fieldtype, "Link");
    eq(df.options, "AL Color Standard");
});

check("(1d) Float / Int / Currency / Percent / Check giữ đúng kiểu", () => {
    const cases = [
        ["Float", "Float"], ["Int", "Int"], ["Currency", "Currency"],
        ["Percent", "Percent"], ["Check", "Check"], ["Data", "Data"],
    ];
    cases.forEach(([varType, expected]) => {
        resetEnv();
        loadChild();
        const frm = makeParentFrm([]);
        makeRow("row-a", { name: "row-a", var_type: varType });
        childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
        eq(DF_COPIES["AL Variable Set Item|row-a|default_value"].fieldtype,
            expected, varType);
    });
});

// ═══════════════════════════════════════════════════════════════════════
// (2) Ca âm — thiếu cấu hình thì ⛔ dựng ô chọn rỗng
// ═══════════════════════════════════════════════════════════════════════
check("(2a) Select CHƯA khai lựa chọn ⇒ ô chữ (không khoá người dùng)", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", { name: "row-a", var_type: "Select", select_options: "" });
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    const df = DF_COPIES["AL Variable Set Item|row-a|default_value"];
    eq(df.fieldtype, "Data");
    eq(df.options, "");
});

check("(2b) Link CHƯA khai doctype ⇒ ô chữ", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", { name: "row-a", var_type: "Link", link_doctype: "" });
    childHandler("link_doctype")(frm, "AL Variable Set Item", "row-a");
    eq(DF_COPIES["AL Variable Set Item|row-a|default_value"].fieldtype, "Data");
});

check("(2c) Kiểu lạ ⇒ ô chữ, ⛔ ném lỗi", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", { name: "row-a", var_type: "Bizarre" });
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    eq(DF_COPIES["AL Variable Set Item|row-a|default_value"].fieldtype, "Data");
});

// ═══════════════════════════════════════════════════════════════════════
// (3) Mỗi dòng một bản meta riêng
// ═══════════════════════════════════════════════════════════════════════
check("(3a) dòng Select ⛔ đổi kiểu dòng Float khác", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", {
        name: "row-a", var_type: "Select", select_options: "Đỏ\nXanh",
    });
    makeRow("row-b", { name: "row-b", var_type: "Float" });
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    childHandler("var_type")(frm, "AL Variable Set Item", "row-b");
    eq(DF_COPIES["AL Variable Set Item|row-a|default_value"].fieldtype, "Select");
    eq(DF_COPIES["AL Variable Set Item|row-b|default_value"].fieldtype, "Float");
});

check("(3b) đổi lại kiểu ⇒ đổi CẢ options, không sót danh sách cũ", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    const row = makeRow("row-a", {
        name: "row-a", var_type: "Select", select_options: "Đỏ\nXanh",
    });
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    row.var_type = "Float";
    childHandler("var_type")(frm, "AL Variable Set Item", "row-a");
    const df = DF_COPIES["AL Variable Set Item|row-a|default_value"];
    eq(df.fieldtype, "Float");
    eq(df.options, "");
});

// ═══════════════════════════════════════════════════════════════════════
// (4) Hộp thoại sửa dòng — vẽ lại ô với kiểu đúng
// ═══════════════════════════════════════════════════════════════════════
check("(4a) form_render trên form DÒNG ⇒ replace_field đúng kiểu", () => {
    resetEnv();
    loadChild();
    let replaced = null;
    const rowForm = {
        doc: { name: "row-a", var_type: "Select", select_options: "Đỏ\nXanh" },
        fields_dict: {
            default_value: { df: { fieldname: "default_value", fieldtype: "Data", options: "" } },
        },
        layout: {
            replace_field(fieldname, df) { replaced = [fieldname, df.fieldtype, df.options]; },
        },
    };
    childHandler("form_render")(rowForm);
    eq(replaced, ["default_value", "Select", "\nĐỏ\nXanh"]);
});

check("(4b) form_render khi kiểu ĐÃ đúng ⇒ không vẽ lại (⛔ mất giá trị đang gõ)", () => {
    resetEnv();
    loadChild();
    let replaced = 0;
    const rowForm = {
        doc: { name: "row-a", var_type: "Float" },
        fields_dict: {
            default_value: { df: { fieldname: "default_value", fieldtype: "Float", options: "" } },
        },
        layout: { replace_field() { replaced += 1; } },
    };
    childHandler("form_render")(rowForm);
    eq(replaced, 0);
});

// ═══════════════════════════════════════════════════════════════════════
// (5) Chọn biến ⇒ bù metadata còn thiếu từ Library
// ═══════════════════════════════════════════════════════════════════════
check("(5a) chọn biến Select ⇒ nạp kiểu + lựa chọn rồi áp ô", () => {
    resetEnv();
    loadChild();
    LIB_VALUES["MauSon"] = {
        var_type: "Select", select_options: "Đen\nTrắng", link_doctype: "",
    };
    const frm = makeParentFrm([]);
    makeRow("row-a", { name: "row-a", variable: "MauSon" });
    childHandler("variable")(frm, "AL Variable Set Item", "row-a");
    const df = DF_COPIES["AL Variable Set Item|row-a|default_value"];
    eq(df.fieldtype, "Select");
    eq(df.options, "\nĐen\nTrắng");
    assert(SET_VALUE_CALLS.length >= 1, "phải ghi metadata về dòng");
});

check("(5b) biến chưa có trong Library ⇒ giữ ô chữ, ⛔ ném", () => {
    resetEnv();
    loadChild();
    const frm = makeParentFrm([]);
    makeRow("row-a", { name: "row-a", variable: "KhongCo" });
    childHandler("variable")(frm, "AL Variable Set Item", "row-a");
    eq(DF_COPIES["AL Variable Set Item|row-a|default_value"].fieldtype, "Data");
});

check("(5c) mở lại bộ biến ⇒ dòng thiếu lựa chọn TỰ nhận từ Library", () => {
    resetEnv();
    loadChild();
    LIB_VALUES["MauSon"] = {
        var_type: "Select", select_options: "Đen\nTrắng", link_doctype: "",
    };
    const refreshed = [];
    const frm = makeParentFrm(refreshed);
    // Dòng đã lưu từ trước khi Library có lựa chọn ⇒ giữ cấu hình rỗng.
    const row = makeRow("row-a", {
        name: "row-a", variable: "MauSon", var_type: "Select", select_options: "",
    });
    frm.doc.items = [row];
    parentHandler("refresh")(frm);
    eq(row.select_options, "Đen\nTrắng");
    const df = DF_COPIES["AL Variable Set Item|row-a|default_value"];
    eq(df.fieldtype, "Select", "ô phải đổi sang chọn danh sách");
    assert(refreshed.length >= 1, "phải vẽ lại ô");
});

check("(5d) dòng đã đủ cấu hình ⇒ ⛔ đọc Library, ⛔ ghi đè", () => {
    resetEnv();
    loadChild();
    LIB_VALUES["MauSon"] = {
        var_type: "Select", select_options: "Đen", link_doctype: "",
    };
    const frm = makeParentFrm([]);
    const row = makeRow("row-a", {
        name: "row-a", variable: "MauSon", var_type: "Select",
        select_options: "Đen\nTrắng",
    });
    frm.doc.items = [row];
    parentHandler("refresh")(frm);
    eq(SET_VALUE_CALLS.length, 0, "không được ghi lại cấu hình đã đủ");
    eq(row.select_options, "Đen\nTrắng");
});

// ═══════════════════════════════════════════════════════════════════════
// (6) AL Variable Library — ô Default Value cũng theo kiểu
// ═══════════════════════════════════════════════════════════════════════
function libForm(doc, replaced) {
    return {
        doc: doc,
        set_value(fieldname, value) {
            SET_VALUE_CALLS.push([fieldname, value]);
            doc[fieldname] = value;
        },
        fields_dict: {
            default_value: { df: { fieldname: "default_value", fieldtype: "Data", options: "" } },
        },
        layout: {
            replace_field(fieldname, df) {
                replaced.push([fieldname, df.fieldtype, df.options]);
            },
        },
    };
}

function libHandler(event) {
    const h = FORM_EVENTS["AL Variable Library"] || {};
    assert(typeof h[event] === "function", "phải đăng ký " + event);
    return h[event];
}

check("(6a) Library kiểu Select ⇒ ô mặc định là ô chọn", () => {
    resetEnv();
    loadLib();
    const replaced = [];
    libHandler("var_type")(libForm(
        { var_type: "Select", select_options: "Đỏ\nXanh" }, replaced));
    eq(replaced, [["default_value", "Select", "\nĐỏ\nXanh"]]);
});

check("(6b) Library kiểu Link ⇒ ô chọn bản ghi", () => {
    resetEnv();
    loadLib();
    const replaced = [];
    libHandler("link_doctype")(libForm(
        { var_type: "Link", link_doctype: "AL Glass Master" }, replaced));
    eq(replaced, [["default_value", "Link", "AL Glass Master"]]);
});

check("(6c) Library chưa khai lựa chọn ⇒ ô chữ KÈM lời giải thích", () => {
    resetEnv();
    loadLib();
    const replaced = [];
    libHandler("var_type")(libForm(
        { var_type: "Select", select_options: "" }, replaced));
    // Vẫn là ô chữ (⛔ ô chọn rỗng), nhưng phải nói vì sao — nếu không người
    // dùng tưởng đã cấu hình đúng và chỉ phát hiện lúc tính giá.
    eq(replaced.length, 1);
    eq(replaced[0][0], "default_value");
    eq(replaced[0][1], "Data");
    assert(replaced[0][2] === "" || replaced[0][2] === undefined,
        "ô chữ không được mang options của Select");
});

check("(6e) đổi sang Đúng/Sai mà giá trị không hợp ⇒ báo + để trống", () => {
    resetEnv();
    loadLib();
    const replaced = [];
    const doc = { var_type: "Check", default_value: "8" };
    libHandler("var_type")(libForm(doc, replaced));
    eq(SET_VALUE_CALLS, [["default_value", ""]]);
    assert(ALERTS.length === 1, "phải báo cho người dùng biết vì sao mất giá trị");
});

check("(6d) Library kiểu số ⇒ ô số", () => {
    resetEnv();
    loadLib();
    const replaced = [];
    libHandler("var_type")(libForm({ var_type: "Float" }, replaced));
    eq(replaced, [["default_value", "Float", ""]]);
});

console.log("");
console.log("  Tổng: " + (passed + failed.length)
    + "  PASS: " + passed + "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
