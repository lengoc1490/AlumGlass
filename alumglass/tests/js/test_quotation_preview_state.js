#!/usr/bin/env node
/**
 * Test Node thuần cho phần CLIENT của phase 1.5 "Preview không ghi DB"
 * (alumglass/alumglass/doctype/overrides/quotation.js).
 *
 * BỐI CẢNH (Owner chốt 2026-11-21)
 * ────────────────────────────────
 * Preview ⛔ không ghi `al_bom_vars`/`al_bom` xuống DB nữa ⇒ 3 API CHỈ ĐỌC
 * phải nhận trạng thái DIALOG từ client, nếu không chúng đọc bản CŨ/rỗng:
 *   1. `get_variable_set_for_bom` ← `params` (biến/kính/BOM/Version trên form)
 *   2. `get_glass_master_price`   ← `params` (tra giá theo biến đang sửa)
 *   3. `explain_bom_line`         ← `result_json` (kết quả đang hiển thị)
 *
 * File này phủ ĐÚNG phần client (hàm thuần + renderer):
 *   (1) `build_variable_set_args` gửi `params`; ⛔ không truyền ⇒ args như cũ
 *   (2) `make_price_requester` gửi `params` và lấy trạng thái MỚI mỗi lượt
 *   (3) `explain_bom_line_args` — dòng cũ/mới, kèm `result_json` + `parent`
 *   (4) renderer gắn nút "Vì sao ra số này?" cho DÒNG MỚI khi có kết quả
 *       trong tay, và đăng ký payload để nút giải thích đúng kết quả đó
 *
 * KHÔNG cần site, KHÔNG cần npm — chạy:
 *     node alumglass/tests/js/test_quotation_preview_state.js
 *
 * `quotation.js` là doctype_js của Frappe (nạp trong trình duyệt) nên trước
 * khi require() ta stub môi trường Frappe tối thiểu, y như 2 file test JS khác.
 */
"use strict";

const path = require("path");

// ── Stub môi trường Frappe tối thiểu ────────────────────────────────────
global.__ = (s) => s;
global.document = {};
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
    show_alert() {},
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

const alumglass = require(path.join(
    __dirname, "..", "..", "alumglass", "doctype", "overrides", "quotation.js"));
const pick = alumglass.glass_pick;

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

// ── Đồng hồ giả cho debounce (giống test_quotation_glass_pick.js) ───────
function makeFakeTimers() {
    let now = 0;
    let nextId = 0;
    let timers = [];
    return {
        setTimeout(fn, ms) {
            const t = { id: ++nextId, at: now + (Number(ms) || 0), fn: fn };
            timers.push(t);
            return t.id;
        },
        clearTimeout(id) {
            timers = timers.filter((t) => t.id !== id);
        },
        advance(ms) {
            now += ms;
            for (;;) {
                const due = timers.filter((t) => t.at <= now)
                    .sort((a, b) => a.at - b.at)[0];
                if (!due) break;
                timers = timers.filter((t) => t.id !== due.id);
                due.fn();
            }
        },
        pending() { return timers.length; },
    };
}

// ═════════════════════════════════════════════════════════════════════════
// (1) `build_variable_set_args` — gửi trạng thái dialog
// ═════════════════════════════════════════════════════════════════════════

check("(1a) có params → args.params là chuỗi JSON của chúng", () => {
    const params = {
        al_bom: "BOM-1", al_bom_version: "ALBOMV-1",
        al_bom_vars: '{"glass_master_map":{"GM-01":"GM-02"}}',
        item_code: "SP-01", item_name: "Sản phẩm",
        parent: "QTN-1", parenttype: "Quotation",
    };
    const args = pick.build_variable_set_args("BOM-1", "QI-0001", params);
    eq(args, {
        bom_code: "BOM-1",
        quotation_item_name: "QI-0001",
        params: JSON.stringify(params),
    });
    eq(JSON.parse(args.params), params, "params phải round-trip nguyên vẹn");
});

check("(1b) dòng MỚI vẫn gửi params (server cần parent để kiểm quyền)", () => {
    const args = pick.build_variable_set_args(
        "BOM-1", "new-quotation-item-3", { al_bom: "BOM-1", parent: "QTN-1" });
    assert(!("quotation_item_name" in args), "⛔ gửi tên dòng chưa lưu");
    eq(JSON.parse(args.params).parent, "QTN-1");
});

check("(1c) ⛔ không params → args y như TRƯỚC phase 1.5 (không key params)", () => {
    eq(pick.build_variable_set_args("BOM-1", "QI-0001"),
        { bom_code: "BOM-1", quotation_item_name: "QI-0001" });
    eq(pick.build_variable_set_args("BOM-1", ""), { bom_code: "BOM-1" });
});

// ═════════════════════════════════════════════════════════════════════════
// (2) `make_price_requester` — gửi params, lấy trạng thái MỚI mỗi lượt
// ═════════════════════════════════════════════════════════════════════════

check("(2a) mỗi lượt hỏi giá gửi kèm params đang có", () => {
    const timers = makeFakeTimers();
    const calls = [];
    let glassColor = "Trang";
    const requester = pick.make_price_requester({
        timers: timers,
        quotation_item_name: "QI-0001",
        params: () => ({ al_bom: "BOM-1", al_bom_vars: JSON.stringify({ glass_color: glassColor }) }),
        call: (method, args, cb) => { calls.push({ method, args }); cb(null); },
    });

    requester.request("GM-02", () => {});
    timers.advance(pick.DEBOUNCE_MS);
    eq(calls[0].method, pick.PRICE_METHOD);
    eq(calls[0].args.quotation_item_name, "QI-0001");
    eq(calls[0].args.glass_code, "GM-02");
    assert(calls[0].args.params, "⛔ thiếu params");
    eq(JSON.parse(calls[0].args.params).al_bom_vars,
        JSON.stringify({ glass_color: "Trang" }));

    // Người dùng đổi màu SAU khi requester được tạo → lượt sau phải mang
    // giá trị MỚI (params là hàm, không chụp lại lúc tạo requester).
    glassColor = "Den";
    requester.request("GM-02", () => {});
    timers.advance(pick.DEBOUNCE_MS);
    eq(JSON.parse(calls[1].args.params).al_bom_vars,
        JSON.stringify({ glass_color: "Den" }));
});

check("(2b) ⛔ không có params → args KHÔNG có key params (hành vi cũ)", () => {
    const timers = makeFakeTimers();
    const calls = [];
    const requester = pick.make_price_requester({
        timers: timers,
        quotation_item_name: "QI-0001",
        call: (method, args, cb) => { calls.push(args); cb(null); },
    });
    requester.request("GM-02", () => {});
    timers.advance(pick.DEBOUNCE_MS);
    eq(calls[0], { quotation_item_name: "QI-0001", glass_code: "GM-02" });
});

check("(2c) params dạng object cũng được serialize", () => {
    const timers = makeFakeTimers();
    const calls = [];
    const requester = pick.make_price_requester({
        timers: timers,
        quotation_item_name: "QI-0001",
        params: { al_bom: "BOM-1" },
        call: (method, args, cb) => { calls.push(args); cb(null); },
    });
    requester.request("GM-01", () => {});
    timers.advance(pick.DEBOUNCE_MS);
    eq(JSON.parse(calls[0].params), { al_bom: "BOM-1" });
});

// ═════════════════════════════════════════════════════════════════════════
// (3) `explain_bom_line_args` — dòng cũ / dòng mới / thiếu định danh
// ═════════════════════════════════════════════════════════════════════════

const RESULT_JSON = JSON.stringify({ lines: [{ slug: "kinh_tren", line_total: 222000 }] });

check("(3a) dòng ĐÃ LƯU có result_json → gửi cả result_json", () => {
    eq(alumglass.explain_bom_line_args({
        quotation_item: "QI-0001", slug: "kinh_tren", result_json: RESULT_JSON,
    }), {
        quotation_item_name: "QI-0001", slug: "kinh_tren",
        result_json: RESULT_JSON,
    });
});

check("(3b) dòng ĐÃ LƯU không result_json → giữ hành vi cũ (đọc DB)", () => {
    eq(alumglass.explain_bom_line_args({
        quotation_item: "QI-0001", slug: "kinh_tren", result_json: "",
    }), { quotation_item_name: "QI-0001", slug: "kinh_tren" });
});

check("(3c) dòng MỚI + result_json + parent → giải thích được từ kết quả trong tay", () => {
    eq(alumglass.explain_bom_line_args({
        quotation_item: "", slug: "kinh_tren",
        result_json: RESULT_JSON, parent: "QTN-1",
    }), {
        quotation_item_name: "", slug: "kinh_tren",
        result_json: RESULT_JSON, parent: "QTN-1",
    });
    // Tên `new-…` cũng coi là dòng mới.
    const args = alumglass.explain_bom_line_args({
        quotation_item: "new-quotation-item-3", slug: "kinh_tren",
        result_json: RESULT_JSON, parent: "QTN-1",
    });
    eq(args.parent, "QTN-1");
});

check("(3d) dòng MỚI thiếu result_json HOẶC parent → ⛔ không gọi server", () => {
    eq(alumglass.explain_bom_line_args({
        quotation_item: "", slug: "kinh_tren", parent: "QTN-1",
    }), null);
    eq(alumglass.explain_bom_line_args({
        quotation_item: "", slug: "kinh_tren", result_json: RESULT_JSON,
    }), null);
});

check("(3e) thiếu slug → ⛔ không gọi server (kể cả có tên dòng)", () => {
    eq(alumglass.explain_bom_line_args({
        quotation_item: "QI-0001", slug: "", result_json: RESULT_JSON,
    }), null);
});

// ═════════════════════════════════════════════════════════════════════════
// (4) Renderer — nút "Vì sao ra số này?" cho DÒNG MỚI + payload đính kèm
// ═════════════════════════════════════════════════════════════════════════

function render_lines(opts) {
    return alumglass.render_bom_result_display({
        summary: { calculated: true, gia_ban: 1000, gia_vat: 1100, line_count: 1 },
        lines: [{
            slug: "kinh_tren", item_code: "KINH-01", label: "Kính trên",
            width: 2000, height: 1000, qty: 2, total_qty: 4,
            unit_price: 50000, line_total: 200000, unit: "m2",
            cost_bucket: "VL_KINH", bucket_name: "Vật liệu kính",
        }],
        buckets: [], cost_template: [],
    }, opts || { collapsible: false });
}

function explain_btn(html) {
    const s = String(html);
    if (s.indexOf("al-bom-explain-btn") < 0) return null;
    const start = s.indexOf("al-bom-explain-btn");
    const end = s.indexOf("</button>", start);
    return s.slice(start, end);
}

check("(4a) dòng MỚI (⛔ không tên) + kết quả trong tay → CÓ nút giải thích", () => {
    const html = render_lines({
        quotation_item: "",
        explain_result_json: RESULT_JSON,
        explain_parent: "QTN-1",
    });
    const btn = explain_btn(html);
    assert(btn, "dòng mới phải có nút 'Vì sao ra số này?' khi có kết quả");
    assert(/data-explain-key="ex-\d+"/.test(btn), "nút thiếu data-explain-key: " + btn);
});

check("(4b) dòng MỚI ⛔ không kết quả → KHÔNG có nút (không có gì để giải thích)", () => {
    const html = render_lines({ quotation_item: "" });
    eq(explain_btn(html), null);
});

check("(4c) payload đăng ký đúng result_json + parent để nút gửi server", () => {
    const html = render_lines({
        quotation_item: "",
        explain_result_json: RESULT_JSON,
        explain_parent: "QTN-1",
    });
    const btn = explain_btn(html);
    const key = (btn.match(/data-explain-key="([^"]*)"/) || [])[1];
    assert(key, "không đọc được key từ nút");
    const payload = alumglass._explain_payloads[key];
    assert(payload, "không tìm thấy payload của key " + key);
    eq(payload.result_json, RESULT_JSON);
    eq(payload.parent, "QTN-1");

    // Args client sẽ gửi (dùng lại đúng payload như handler click).
    const args = alumglass.explain_bom_line_args({
        quotation_item: "",
        slug: "kinh_tren",
        result_json: payload.result_json,
        parent: payload.parent,
    });
    eq(args.result_json, RESULT_JSON);
    eq(args.parent, "QTN-1");
});

check("(4d) dòng ĐÃ LƯU → nút vẫn có (kèm result_json mới nhất)", () => {
    const html = render_lines({
        quotation_item: "QI-0001",
        explain_result_json: RESULT_JSON,
        explain_parent: "QTN-1",
    });
    const btn = explain_btn(html);
    assert(btn, "dòng đã lưu phải có nút");
    assert(/data-quotation-item="QI-0001"/.test(btn), btn);
    assert(/data-explain-key="ex-\d+"/.test(btn), btn);
});

check("(4e) dòng ĐÃ LƯU ⛔ không result_json → nút dùng đường cũ (không key)", () => {
    const html = render_lines({ quotation_item: "QI-0001" });
    const btn = explain_btn(html);
    assert(btn, "dòng đã lưu vẫn phải có nút");
    assert(!/data-explain-key="ex-/.test(btn), "không có payload thì ⛔ gắn key");
});

check("(4f) đăng ký payload nhận cả object (⛔ để lọt '[object Object]')", () => {
    const key = alumglass.register_explain_payload({ lines: [] }, "QTN-1");
    assert(key, "object cũng phải đăng ký được");
    eq(alumglass._explain_payloads[key].result_json, JSON.stringify({ lines: [] }));
});

// ── Runner ──────────────────────────────────────────────────────────────
console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed + "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
