#!/usr/bin/env node
/**
 * Test Node thuần cho phần HIỂN THỊ số đo trong bảng "Chi tiết vật tư" của
 * alumglass/alumglass/doctype/overrides/quotation.js (hàm
 * `render_bom_result_display` + helper `alumglass.fmt_dimension`).
 *
 * KHÔNG cần site, KHÔNG cần npm/cài package — chạy:
 *     node alumglass/tests/js/test_quotation_display.js
 *
 * Yêu cầu Owner (2026-11-21): "cột rộng, cao nếu giá trị = 0 thì hiển thị -
 * tương tự như cột trọng lượng".
 *
 * Phủ:
 *   (1) fmt_dimension — mọi dạng "chưa có số đo" phải ra "—", số thật ra số đã
 *       format, NaN/chuỗi rác KHÔNG được in "NaN"
 *   (2) render_bom_result_display — 2 ô Rộng/Cao dùng helper đó; cột Số lượng /
 *       Đơn giá / Thành tiền / Trọng lượng KHÔNG bị đổi hành vi
 *
 * File quotation.js là doctype_js của Frappe (nạp trong trình duyệt) nên trước
 * khi require() ta stub môi trường Frappe tối thiểu, y như
 * test_quotation_glass_pick.js.
 */
"use strict";

const path = require("path");

// ── Stub môi trường Frappe tối thiểu ────────────────────────────────────
global.__ = (s) => s;
global.document = {};

// format_number: ngăn nghìn bằng dấu phẩy (locale en) — đủ để khẳng định
// "giá trị số thật đã được format" mà không phụ thuộc site.
global.format_number = function (value) {
    const n = Number(value);
    if (!isFinite(n)) return String(value);
    const rounded = Math.round(n * 100) / 100;
    const parts = String(rounded).split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join(".");
};
global.format_currency = function (value) {
    return global.format_number(value) + " đ";
};

global.frappe = {
    provide(ns) {
        const parts = String(ns).split(".");
        let obj = global;
        parts.forEach((p) => {
            if (!obj[p]) obj[p] = {};
            obj = obj[p];
        });
    },
    ui: { form: { on() {} } },
    utils: {},
    call() {},
    get_doc() { return {}; },
};
global.$ = function () {
    const jq = {
        length: 0,
        on() { return jq; }, off() { return jq; },
        find() { return jq; }, first() { return jq; },
        append() { return jq; }, prepend() { return jq; },
        attr() { return jq; }, css() { return jq; },
        text() { return jq; }, html() { return jq; },
        val() { return ""; }, empty() { return jq; },
    };
    return jq;
};

const alumglass = require(path.join(
    __dirname, "..", "..", "alumglass", "doctype", "overrides", "quotation.js"));

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
    if (a !== e) throw new Error((msg || "không khớp") + "\n        thực tế: " + a + "\n        mong đợi: " + e);
}

function assert(cond, msg) {
    if (!cond) throw new Error(msg || "assert thất bại");
}

// Lấy nội dung từng <td> của dòng vật tư ĐẦU TIÊN trong HTML renderer.
// Thứ tự cột: 0 Mã, 1 Tên, 2 Rộng, 3 Cao, 4 Số lượng, 5 Trọng lượng,
//             6 Khối lượng, 7 ĐVT, 8 Đơn giá, 9 Thành tiền, 10 Nhóm CP.
function row_cells(html) {
    const s = String(html);
    const body = s.split("<tbody>")[1].split("</tbody>")[0];
    return body.split("<td").slice(1).map(function (chunk) {
        const inner = chunk.split("</td>")[0];
        return inner.slice(inner.indexOf(">") + 1).trim();
    });
}

function render_lines(lines, opts) {
    return alumglass.render_bom_result_display(
        { summary: { calculated: false }, lines: lines, buckets: [], cost_template: [] },
        opts || { collapsible: false });
}

const fmt = alumglass.fmt_dimension;

// ═════════════════════════════════════════════════════════════════════════
// (1) fmt_dimension — "chưa có số đo" ⇒ "—"
// ═════════════════════════════════════════════════════════════════════════
check("(1a) số 0 (mọi dạng) → '—', ⛔ không in '0'", () => {
    eq(fmt(0), "—", "0 (number)");
    eq(fmt(0.0), "—", "0.0 (number)");
    eq(fmt("0"), "—", "chuỗi '0'");
    eq(fmt("0.0"), "—", "chuỗi '0.0'");
    eq(fmt("  0  "), "—", "chuỗi '  0  '");
    eq(fmt(-0), "—", "-0");
});

check("(1b) rỗng / null / undefined / khoảng trắng → '—'", () => {
    eq(fmt(null), "—");
    eq(fmt(undefined), "—");
    eq(fmt(""), "—");
    eq(fmt("  "), "—");
    eq(fmt("\t\n"), "—");
});

check("(1c) số đo thật → format_number (ngăn nghìn)", () => {
    eq(fmt(1200), "1,200");
    eq(fmt("1200"), "1,200", "chuỗi số cũng phải hiện số");
    eq(fmt(1200.5), "1,200.5");
    eq(fmt(" 900 "), "900", "bỏ khoảng trắng thừa");
    eq(fmt(1), "1");
});

check("(1d) giá trị không phải số → '—', ⛔ tuyệt đối không in 'NaN'", () => {
    eq(fmt("abc"), "—");
    eq(fmt(NaN), "—");
    eq(fmt("NaN"), "—");
    // Bất biến: đầu ra không bao giờ chứa 'NaN' / 'undefined' / 'null'
    ["abc", NaN, "NaN", undefined, null, Infinity, "  ", ""].forEach((v) => {
        const out = fmt(v);
        assert(out === "—", "giá trị rác " + JSON.stringify(String(v)) + " phải là '—', nhận " + JSON.stringify(out));
        assert(!/NaN|undefined|null/.test(out), "đầu ra chứa rác kỹ thuật: " + out);
    });
});

check("(1e) chỉ 0 mới bị coi là 'chưa có' — số khác 0 vẫn hiện đúng", () => {
    eq(fmt(-1), "-1");
    eq(fmt(0.01), "0.01");
});

// ═════════════════════════════════════════════════════════════════════════
// (2) render_bom_result_display — 2 ô Rộng/Cao
// ═════════════════════════════════════════════════════════════════════════
check("(2a) Rộng = 0, Cao = 0 → 2 ô hiện '—' (không in '0')", () => {
    const cells = row_cells(render_lines([{
        slug: "nep", item_code: "NEP-01", label: "Nẹp", width: 0, height: 0,
        qty: 4, total_qty: 12, unit: "m", unit_price: 1000, line_total: 12000,
    }]));
    eq(cells[2], "—", "ô Rộng (mm)");
    eq(cells[3], "—", "ô Cao (mm)");
});

check("(2b) có số đo thật → ô Rộng/Cao hiện số đã format", () => {
    const cells = row_cells(render_lines([{
        slug: "kinh", item_code: "KINH-01", label: "Kính", width: 1200, height: 900,
        qty: 1, total_qty: 1, unit: "m2", unit_price: 300000, line_total: 300000,
    }]));
    eq(cells[2], "1,200");
    eq(cells[3], "900");
});

check("(2c) chuỗi '0'/null/rỗng ở dữ liệu cũ → '—' (không lọt xuống format_number)", () => {
    const cells = row_cells(render_lines([{
        slug: "a", item_code: "A", label: "A", width: "0", height: null,
        qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]));
    eq(cells[2], "—", "Rộng '0'");
    eq(cells[3], "—", "Cao null");
    const cells2 = row_cells(render_lines([{
        slug: "b", item_code: "B", label: "B", width: "", height: "   ",
        qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]));
    eq(cells2[2], "—");
    eq(cells2[3], "—");
});

check("(2d) ô rác ('abc'/NaN) → '—', ⛔ không in 'NaN' ra màn hình", () => {
    const cells = row_cells(render_lines([{
        slug: "c", item_code: "C", label: "C", width: "abc", height: NaN,
        qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]));
    eq(cells[2], "—");
    eq(cells[3], "—");
});

// ═════════════════════════════════════════════════════════════════════════
// (3) KHÔNG hồi quy các cột khác
// ═════════════════════════════════════════════════════════════════════════
check("(3a) Số lượng = 0 vẫn in '0' (chỉ Rộng/Cao đổi hành vi)", () => {
    const cells = row_cells(render_lines([{
        slug: "d", item_code: "D", label: "D", width: 0, height: 0,
        qty: 0, total_qty: 0, unit: "cai", unit_price: 0, line_total: 0,
    }]));
    eq(cells[4], "0", "cột Số lượng");
    eq(cells[6], "0", "cột Khối lượng");
});

check("(3b) Đơn giá / Thành tiền vẫn hiện '0 đ'", () => {
    const cells = row_cells(render_lines([{
        slug: "e", item_code: "E", label: "E", width: 0, height: 0,
        qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]));
    assert(cells[8].indexOf("0 đ") !== -1, "Đơn giá phải là '0 đ', nhận: " + cells[8]);
    assert(cells[9].indexOf("0 đ") !== -1, "Thành tiền phải là '0 đ', nhận: " + cells[9]);
});

check("(3c) Trọng lượng giữ nguyên logic cũ: 0 → '—', có giá trị → số + kg/m", () => {
    const zero = row_cells(render_lines([{
        slug: "f", item_code: "F", label: "F", width: 0, height: 0,
        qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
        has_weight: true, weight_per_unit: 0,
    }]));
    eq(zero[5], "—", "Trọng lượng 0");
    const heavy = row_cells(render_lines([{
        slug: "g", item_code: "G", label: "G", width: 0, height: 0,
        qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
        has_weight: true, weight_per_unit: 2.5,
    }]));
    assert(heavy[5].indexOf("2.5") === 0, "Trọng lượng phải bắt đầu bằng số, nhận: " + heavy[5]);
    assert(heavy[5].indexOf("kg/m") !== -1, "Trọng lượng phải kèm kg/m");
});

console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed +
    "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
