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

// ═════════════════════════════════════════════════════════════════════════
// (4) Căn cứ chọn SỐ LƯỢNG theo quy tắc — `qty_rule_trace` ưu tiên hơn `rule_trace`
// ═════════════════════════════════════════════════════════════════════════
check("(4a) chỉ có rule_trace → vẫn hiện căn cứ (dữ liệu cũ)", () => {
    const html = render_lines([{
        slug: "nep", item_code: "NEP-01", label: "Nẹp",
        qty: 4, total_qty: 4, unit_price: 0, line_total: 0,
        rule_trace: "theo Độ dày kính 10 mm → Chọn nẹp",
    }]);
    assert(html.indexOf("al-bom-rule-trace") !== -1, "thiếu khối căn cứ");
    assert(html.indexOf("theo Độ dày kính 10 mm") !== -1, "thiếu nguyên văn rule_trace");
});

check("(4b) có qty_rule_trace → hiện căn cứ số lượng, ⛔ hiện chồng rule_trace", () => {
    const html = render_lines([{
        slug: "ban_le", item_code: "BAN-LE-01", label: "Bản lề",
        qty: 8, total_qty: 8, unit_price: 0, line_total: 0,
        qty_rule_trace: "Chọn số lượng theo quy tắc “Số bản lề theo chiều cao”: "
            + "Chiều cao = 3200 mm → 4 × số cánh 2 = 8.",
        rule_trace: "CĂN-CỨ-CHỌN-MÃ-CŨ",
    }]);
    assert(html.indexOf("Số bản lề theo chiều cao") !== -1, "thiếu qty_rule_trace");
    assert(html.indexOf("CĂN-CỨ-CHỌN-MÃ-CŨ") === -1,
        "⛔ được hiện chồng rule_trace khi đã có qty_rule_trace");
});

// ═════════════════════════════════════════════════════════════════════════
// (5) UX1 chấm CHẶN vòng 2 — cột Mã vật tư ⛔ slug; nút "?" phải còn khi
//     thiếu mã (đó là lúc người dùng cần nhất).
// ═════════════════════════════════════════════════════════════════════════
// Lấy HTML của ô Mã (td đầu tiên, còn nguyên thẻ con bên trong).
function code_cell_html(html) {
    const body = String(html).split("<tbody>")[1].split("</tbody>")[0];
    return body.split("<td")[1].split("</td>")[0];
}

function render_rule_lines(lines, opts) {
    return render_lines(lines, Object.assign({
        collapsible: false, quotation_item: "QI-1",
    }, opts || {}));
}

check("(5a) dòng Rule THIẾU mã ⇒ 'Chưa tra được mã', ⛔ slug ra cột Mã", () => {
    const html = render_rule_lines([{
        slug: "kinh_tren", item_code: "", label: "Kính trên",
        item_selection_mode: "Rule", rule_missing_reason: "no_source_row",
        width: 0, height: 0, qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]);
    const cell = code_cell_html(html);
    assert(cell.indexOf("Chưa tra được mã") !== -1,
        "cột Mã phải nói 'Chưa tra được mã', nhận: " + cell);
    assert(cell.indexOf("kinh_tren") === -1,
        "cột Mã ⛔ được phơi slug: " + cell);
    // `title` giải thích ngắn theo `rule_missing_reason` (server mới).
    assert(cell.indexOf("chưa được chọn") !== -1,
        "title phải giải thích lý do no_source_row, nhận: " + cell);
});

check("(5b) dòng Rule CÓ mã ⇒ giữ nguyên mã, ⛔ câu 'Chưa tra được mã'", () => {
    const html = render_rule_lines([{
        slug: "nep_tren", item_code: "NEP-20", label: "Nẹp trên",
        item_selection_mode: "Rule",
        width: 0, height: 0, qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]);
    const cell = code_cell_html(html);
    assert(cell.indexOf("NEP-20") !== -1, "phải giữ mã thật: " + cell);
    assert(cell.indexOf("Chưa tra được mã") === -1, "có mã thì ⛔ báo thiếu");
});

check("(5c) dòng KHÔNG phải Rule mà không có mã ⇒ giữ hành vi cũ (slug)", () => {
    const html = render_rule_lines([{
        slug: "canh_doc", item_code: "", label: "Cạnh đứng",
        width: 0, height: 0, qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]);
    const cell = code_cell_html(html);
    assert(cell.indexOf("canh_doc") !== -1, "hành vi cũ phải giữ: " + cell);
    assert(cell.indexOf("Chưa tra được mã") === -1);
});

check("(5d) nút '?' VẪN hiện khi dòng Rule thiếu mã", () => {
    const html = render_rule_lines([{
        slug: "kinh_tren", item_code: "", label: "Kính trên",
        item_selection_mode: "Rule", rule_missing_reason: "row_no_data",
        width: 0, height: 0, qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]);
    assert(html.indexOf("al-bom-explain-btn") !== -1,
        "thiếu mã càng phải có nút giải thích");
    assert(html.indexOf('data-item-code=""') !== -1,
        "data-item-code được phép rỗng khi chưa có mã");
    assert(html.indexOf('data-label="Kính trên"') !== -1,
        "data-label dùng nhãn người đọc");
});

check("(5e) tiêu đề/nhãn dòng KHÔNG lộ slug khi thiếu cả tên lẫn mã", () => {
    const html = render_rule_lines([{
        slug: "dong_bi_an", item_code: "", label: "",
        item_selection_mode: "Rule",
        width: 0, height: 0, qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }]);
    const cell = code_cell_html(html);
    assert(cell.indexOf("dong_bi_an") === -1, "⛔ slug: " + cell);
    assert(html.indexOf('data-label="dòng vật tư"') !== -1,
        "nhãn dự phòng phải là 'dòng vật tư'");
    // Slug vẫn được phép nằm trong `data-slug` (payload kỹ thuật của nút "?"),
    // nhưng ⛔ trong cột Mã / nhãn hiển thị.
    assert(html.indexOf(">dong_bi_an<") === -1, "⛔ slug hiện thành chữ");
});

check("ĐỐI CHỨNG ÂM — (5) bản cũ `item_code || slug` phải bị bắt đỏ", () => {
    // Bản hỏng mô phỏng đúng lỗi UX1 chấm: rơi về slug khi thiếu mã.
    const broken_cell = (ln) => String(ln.item_code || ln.slug);
    const ln = {
        slug: "kinh_tren", item_code: "", label: "Kính trên",
        item_selection_mode: "Rule",
    };
    assert(broken_cell(ln) === "kinh_tren",
        "bản hỏng phải thật sự lộ slug để đối chứng có nghĩa");
    let threw = false;
    try {
        // Chạy đúng bộ kiểm (5a) trên bản hỏng.
        const cell = broken_cell(ln);
        assert(cell.indexOf("Chưa tra được mã") !== -1,
            "bản hỏng không thể nói 'Chưa tra được mã'");
    } catch (e) { threw = true; }
    assert(threw, "ĐỐI CHỨNG ÂM: bộ kiểm KHÔNG bắt được bản lộ slug");
});

// ═════════════════════════════════════════════════════════════════════════
// (6) UX1 chấm CHẶN vòng 3 — MAPPER THẬT `alumglass.raw_to_display`.
//     Đường dòng báo giá MỚI (`new-…`, nhánh fallback) đi qua mapper này.
//     Bản trước đặt `label = l.slug` và BỎ các cờ quy tắc ⇒ renderer không
//     biết dòng là Rule nên phơi slug ở cả cột Mã lẫn cột Tên.
// ═════════════════════════════════════════════════════════════════════════
function raw_rule_line(extra) {
    return Object.assign({
        slug: "kinh_tren",
        item_code: "",
        item_selection_mode: "Rule",
        rule_source_missing: 1,
        rule_missing_reason: "no_source_row",
        line_label: "Kính trên",
        width: 1000, height: 2000, qty: 1, unit_qty: 1, total_qty: 1,
        unit_price: 0, line_total: 0,
    }, extra || {});
}

/** Bộ kiểm dùng CHUNG cho (6a)/(6b) và đối chứng âm: mapper phải giữ cờ + nhãn. */
function testMappedRuleLine(display) {
    const ln = (display.lines || [])[0] || {};
    eq(ln.label, "Kính trên", "label phải là nhãn người đọc (line_label), ⛔ slug");
    eq(ln.item_selection_mode, "Rule", "thiếu pass-through item_selection_mode");
    eq(ln.rule_source_missing, 1, "thiếu pass-through rule_source_missing");
    eq(ln.rule_missing_reason, "no_source_row",
        "thiếu pass-through rule_missing_reason");
    eq(ln.line_label, "Kính trên", "thiếu pass-through line_label");
}

/** Render THẲNG display model (kết quả `raw_to_display`) — ⛔ bọc lại như render_lines. */
function render_display(display) {
    return alumglass.render_bom_result_display(display, { collapsible: false });
}

check("(6a) raw_to_display giữ cờ quy tắc + nhãn thật, ⛔ slug", () => {
    testMappedRuleLine(alumglass.raw_to_display({ lines: [raw_rule_line()] }));
});

check("(6b) render TỪ raw_to_display ⇒ 'Chưa tra được mã', ⛔ 'kinh_tren' ở đâu", () => {
    // ⛔ truyền `quotation_item`: nút "?" sẽ đặt slug vào `data-slug`, che mất
    // phép kiểm "⛔ slug ở bất kỳ đâu".
    const html = render_display(alumglass.raw_to_display({ lines: [raw_rule_line()] }));
    const cell = code_cell_html(html);
    assert(cell.indexOf("Chưa tra được mã") !== -1, "cột Mã phải nói trạng thái: " + cell);
    assert(cell.indexOf("no_source_row") === -1, "⛔ mã lý do ra màn hình: " + cell);
    assert(html.indexOf("kinh_tren") === -1, "⛔ slug ở bất kỳ đâu: " + html);
    assert(html.indexOf("Kính trên") !== -1, "phải hiện nhãn người đọc");
});

check("(6c) payload hình dạng get_result_display — rule_input_missing vẫn là dòng Rule", () => {
    // Quy tắc CHƯA khai gì: server chỉ đặt `rule_input_missing = 1` (không có
    // `rule_source_missing`) ⇒ vẫn phải nhận ra là dòng Rule, ⛔ rơi về slug.
    const html = render_lines([{
        slug: "kinh_tren", item_code: "", label: "",
        item_selection_mode: "Rule", rule_input_missing: 1,
        width: 0, height: 0, qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
    }], { collapsible: false, quotation_item: "QI-1" });
    const cell = code_cell_html(html);
    assert(cell.indexOf("Chưa tra được mã") !== -1,
        "rule_input_missing phải được nhận là dòng Rule: " + cell);
    assert(cell.indexOf("kinh_tren") === -1, "cột Mã ⛔ slug: " + cell);
    assert(html.indexOf(">kinh_tren<") === -1, "nhãn hiển thị ⛔ slug: " + html);
    assert(html.indexOf("dòng vật tư") !== -1,
        "thiếu cả tên lẫn mã ⇒ nhãn 'dòng vật tư'");
});

check("(6d) dòng KHÔNG phải Rule qua mapper — cột Mã vẫn giữ slug (hành vi cũ)", () => {
    const html = render_display(alumglass.raw_to_display({
        lines: [{
            slug: "canh_doc", item_code: "", width: 0, height: 0,
            qty: 1, total_qty: 1, unit_price: 0, line_total: 0,
        }],
    }));
    const cell = code_cell_html(html);
    assert(cell.indexOf("canh_doc") !== -1, "dòng không phải Rule giữ slug ở cột Mã: " + cell);
    assert(cell.indexOf("Chưa tra được mã") === -1, "⛔ báo thiếu cho dòng không Rule");
});

check("ĐỐI CHỨNG ÂM — (6) mapper cũ `label: slug` + bỏ cờ phải bị bắt đỏ", () => {
    // Bản hỏng đúng như trước sửa: label = slug, ⛔ pass cờ quy tắc.
    function brokenMapper(raw) {
        return {
            lines: (raw.lines || []).map((l) => ({
                slug: l.slug, label: l.slug, item_code: l.item_code,
                width: l.width, height: l.height, qty: l.qty, total_qty: l.total_qty,
                unit_price: l.unit_price, line_total: l.line_total,
            })),
        };
    }
    const broken = brokenMapper({ lines: [raw_rule_line()] });
    // Bản hỏng phải THẬT SỰ sai để đối chứng có nghĩa...
    eq(broken.lines[0].label, "kinh_tren", "bản hỏng phải thật sự lấy slug làm nhãn");
    assert(broken.lines[0].item_selection_mode === undefined,
        "bản hỏng phải thật sự bỏ cờ quy tắc");
    // ...và bộ kiểm (6a) phải báo đỏ trên nó.
    let threw = false;
    try {
        testMappedRuleLine(broken);
    } catch (e) { threw = true; }
    assert(threw, "ĐỐI CHỨNG ÂM: bộ kiểm KHÔNG bắt được mapper cũ");
});

console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed +
    "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
