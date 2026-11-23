#!/usr/bin/env node
/**
 * Test Node thuần cho "đèn báo mã cũ" — alumglass/public/js/build_beacon.js.
 *
 * KHÔNG cần site, KHÔNG cần package — chạy:
 *     node alumglass/tests/js/test_build_beacon.js
 *
 * Mục đích của beacon: trình duyệt còn cache `quotation.js` CŨ (Frappe nhúng
 * doctype_js vào form meta + cache Redis ⇒ kéo mã mới/restart KHÔNG đủ) thì
 * người dùng phải được báo, thay vì ngồi đoán vì sao hành vi vẫn cũ.
 * Các ca dưới kiểm: báo đúng 1 lần/phiên, không báo khi khớp, không đăng ký
 * handler 2 lần, và các ca âm (thiếu `frappe.boot`, storage bị chặn).
 */
"use strict";

const path = require("path");

// ── Stub môi trường trình duyệt ─────────────────────────────────────────
global.window = global;
global.__ = function (s) { return String(s); };

const BEACON = path.join(__dirname, "..", "..", "public", "js", "build_beacon.js");

// `sessionStorage` giả — bật/tắt chặn để kiểm nhánh riêng tư.
let STORAGE = {};
let STORAGE_BLOCKED = false;
global.sessionStorage = {
    getItem(k) {
        if (STORAGE_BLOCKED) throw new Error("blocked");
        return Object.prototype.hasOwnProperty.call(STORAGE, k) ? STORAGE[k] : null;
    },
    setItem(k, v) {
        if (STORAGE_BLOCKED) throw new Error("blocked");
        STORAGE[k] = String(v);
    },
};

// Gom cảnh báo Console (beacon cố ý warn để chẩn đoán) — giữ log test sạch
// và kiểm được beacon CÓ kèm 2 giá trị expected/actual.
const WARNS = [];
console.warn = function () { WARNS.push(Array.prototype.slice.call(arguments)); };

let ALERTS = [];
let FORM_EVENTS = {};
let FORM_ON_CALLS = 0;

global.frappe = {
    boot: {},
    show_alert(opts, secs) { ALERTS.push({ opts: opts, secs: secs }); },
    ui: {
        form: {
            on(doctype, handlers) {
                FORM_ON_CALLS += 1;
                FORM_EVENTS[doctype] = Object.assign({}, FORM_EVENTS[doctype] || {}, handlers);
            },
        },
    },
};

// Nhãn của beacon — test đọc lại để biết phải đặt dấu build nào cho khớp.
const EXPECTED_BUILD = "2026-11-23b";

function resetEnv(opts) {
    opts = opts || {};
    STORAGE = {};
    STORAGE_BLOCKED = !!opts.storageBlocked;
    ALERTS = [];
    WARNS.length = 0;
    FORM_EVENTS = {};
    FORM_ON_CALLS = 0;
    global.frappe.boot = opts.boot === undefined ? {} : opts.boot;
    delete global.alumglass;
    delete global.__al_beacon_bound;
    delete global.alumglass_build_expected;
}

// Nạp LẠI tệp beacon như trình duyệt nạp trang mới (xoá cache require).
function loadBeacon() {
    delete require.cache[require.resolve(BEACON)];
    require(BEACON);
}

function refreshQuotation() {
    const handlers = FORM_EVENTS["Quotation"] || {};
    assert(typeof handlers.refresh === "function", "phải đăng ký refresh cho Quotation");
    handlers.refresh({ doc: { doctype: "Quotation" } });
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

// ── (0) Tệp khai đúng hằng mong đợi ─────────────────────────────────────
check("(0a) beacon khai alumglass_build_expected khớp bản mong đợi", () => {
    resetEnv();
    loadBeacon();
    eq(global.alumglass_build_expected, EXPECTED_BUILD,
        "hằng mong đợi trong tệp phải đúng (đổi thì phải đổi cùng quotation.js)");
});

// ── (20a) Bản cũ ⇒ cảnh báo orange ĐÚNG 1 lần ──────────────────────────
check("(20a) __build__ KHÁC expected ⇒ show_alert orange đúng 1 lần khi mở form", () => {
    resetEnv();
    global.alumglass = { __build__: "2026-11-01" };
    loadBeacon();          // ⛔ còn kiểm lúc nạp nữa (xem 20a2)
    eq(ALERTS.length, 0, "nạp tệp ⛔ được cảnh báo (quotation.js chưa chắc đã nạp)");
    refreshQuotation();    // mở form báo giá ⇒ lúc này đủ ngữ cảnh
    eq(ALERTS.length, 1, "mở form báo giá với mã CŨ ⇒ phải cảnh báo");
    eq(ALERTS[0].opts.indicator, "orange", "màu cam (cảnh báo, ⛔ đỏ chặn việc)");
    assert(String(ALERTS[0].opts.message).indexOf("chưa phải bản mới nhất") >= 0,
        "câu báo phải nói rõ giao diện chưa phải bản mới nhất");
    eq(ALERTS[0].secs, 10, "hiện đủ lâu để người dùng đọc");
    const warn = WARNS.find((a) => String(a[0]).indexOf("bản CŨ") >= 0);
    assert(warn, "phải warn Console để người vận hành chẩn đoán");
    eq(warn[1], { expected: EXPECTED_BUILD, actual: "2026-11-01" },
        "warn kèm đủ 2 dấu build, ⛔ hiện mã cho người dùng cuối");
    // Mở form báo giá lần nữa ⇒ session guard giữ đúng 1 lần.
    refreshQuotation();
    refreshQuotation();
    eq(ALERTS.length, 1, "cảnh báo ⛔ được lặp lại trong cùng phiên");
});

check("(20a2) nạp lúc chưa có __build__ ⇒ ⛔ cảnh báo; mở form với mã CŨ ⇒ cảnh báo 1 lần", () => {
    resetEnv();
    // LÚC NẠP: `app_include_js` chạy TRƯỚC `quotation.js` ⇒ `__build__` luôn
    // undefined. Đây chính là ca báo SAI khắp Desk trước đây ⇒ phải im lặng.
    loadBeacon();
    eq(ALERTS.length, 0, "nạp beacon khi chưa có __build__ ⛔ được cảnh báo");

    // Sau đó quotation.js (bản CŨ) mới nạp xong rồi người dùng mở báo giá.
    global.alumglass = { __build__: "2026-11-01" };
    refreshQuotation();
    eq(ALERTS.length, 1, "mở form với mã CŨ ⇒ cảnh báo ĐÚNG 1 lần (⛔ bị phiên trước ăn mất)");

    // Phiên MỚI với mã ĐÚNG ⇒ mở form ⛔ cảnh báo.
    resetEnv();
    global.alumglass = { __build__: EXPECTED_BUILD };
    loadBeacon();
    refreshQuotation();
    eq(ALERTS.length, 0, "mã đúng ⇒ ⛔ làm phiền người dùng");
});

check("(20a3) storage bị chặn (chế độ riêng tư) ⇒ vẫn cảnh báo khi mở form, ⛔ ném", () => {
    resetEnv({ storageBlocked: true });
    global.alumglass = { __build__: "2026-11-01" };
    loadBeacon();          // ⛔ không được ném
    refreshQuotation();
    eq(ALERTS.length, 1, "không ghi được sessionStorage vẫn phải báo");
});

// ── (20b) Bản khớp ⇒ KHÔNG cảnh báo ────────────────────────────────────
check("(20b) __build__ KHỚP expected ⇒ ⛔ cảnh báo", () => {
    resetEnv();
    global.alumglass = { __build__: EXPECTED_BUILD };
    loadBeacon();
    refreshQuotation();
    eq(ALERTS.length, 0, "bản mới ⇒ không được làm phiền người dùng");
});

// ── (20c) Không đăng ký handler 2 lần ──────────────────────────────────
check("(20c) nạp beacon 2 lần ⇒ handler chỉ đăng ký 1 lần; thiếu API form ⇒ ⛔ đăng ký", () => {
    resetEnv();
    global.alumglass = { __build__: EXPECTED_BUILD };
    loadBeacon();
    loadBeacon();          // như trình duyệt nạp lại tệp (hot reload / điều hướng)
    eq(FORM_ON_CALLS, 1, "guard __al_beacon_bound phải chặn đăng ký lặp");
    eq(Object.keys(FORM_EVENTS["Quotation"] || {}), ["refresh"]);

    // Thiếu `frappe.ui.form.on` (môi trường không phải Desk form) ⇒ ⛔ ném,
    // ⛔ đăng ký handler (guard trước khi gọi `.on`).
    resetEnv();
    const old_ui = global.frappe.ui;
    global.frappe.ui = {};
    try {
        loadBeacon();      // ⛔ được ném
    } finally {
        global.frappe.ui = old_ui;
    }
    eq(FORM_ON_CALLS, 0, "thiếu frappe.ui.form.on ⇒ ⛔ đăng ký");
});

check("(20d) ĐỐI CHỨNG ÂM: frappe.boot CHƯA sẵn ⇒ ⛔ cảnh báo (tránh báo nhầm)", () => {
    resetEnv({ boot: null });
    global.alumglass = { __build__: "2026-11-01" };
    loadBeacon();
    refreshQuotation();
    eq(ALERTS.length, 0, "chưa có boot thì chưa đủ ngữ cảnh để kết luận");
});

// ── (20e) Câu người dùng thấy ⛔ phơi thuật ngữ vận hành ──────────────
// UX1 chặn đúng bar "không phơi mã kỹ thuật": `migrate`/`cache`/`DB`/
// `version` chỉ được nằm ở log Console, ⛔ được nằm trong toast.
check("(20e) câu cảnh báo KHÔNG chứa migrate/DB/cache/version", () => {
    resetEnv();
    global.alumglass = { __build__: "2026-11-01" };
    loadBeacon();
    refreshQuotation();    // kiểm lúc mở form (⛔ lúc nạp tệp)
    eq(ALERTS.length, 1);
    const msg = String(ALERTS[0].opts.message);
    ["migrate", "cache", "version"].forEach((word) => {
        assert(!new RegExp("\\b" + word + "\\b", "i").test(msg),
            "câu người dùng thấy ⛔ được chứa thuật ngữ '" + word + "'");
    });
    assert(!/\bDB\b/.test(msg), "câu người dùng thấy ⛔ được chứa 'DB'");
    // Vẫn phải kèm HÀNH ĐỘNG cho người dùng (báo ai + làm gì).
    assert(msg.indexOf("quản trị") >= 0 && msg.indexOf("tải lại trang") >= 0,
        "phải kèm hành động: báo quản trị, rồi tải lại trang");
    // Chi tiết vận hành vẫn phải có ở Console (người vận hành cần để xử lý).
    assert(WARNS.length > 0, "Console vẫn phải có log chẩn đoán cho người vận hành");
});

function printSummary() {
    console.log("\n" + "=".repeat(60));
    console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed +
        "  FAIL: " + failed.length);
    if (failed.length) {
        console.log("  FAILED: " + JSON.stringify(failed));
        process.exit(1);
    }
    console.log("  ALL TESTS PASSED");
}

printSummary();
