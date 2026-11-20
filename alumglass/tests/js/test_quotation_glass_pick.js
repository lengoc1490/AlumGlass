#!/usr/bin/env node
/**
 * Test Node thuần cho logic "Kính theo vị trí" trong
 * alumglass/alumglass/doctype/overrides/quotation.js (namespace `alumglass.glass_pick`).
 *
 * KHÔNG cần site, KHÔNG cần npm/cài package — chạy:
 *     node alumglass/tests/js/test_quotation_glass_pick.js
 *
 * Phủ 3 yêu cầu Pha 3 (Owner 2026-11-20):
 *   (1) giá trị khởi tạo ô kính cho 4 nguồn effective_source
 *   (2) câu trạng thái + câu giá (có giá / không có giá / giá tạm tính)
 *   (3) đổi mã kính → gọi API ĐÚNG 1 lần sau debounce 300ms
 *
 * File quotation.js là doctype_js của Frappe (không có module.exports cho
 * trình duyệt) nên trước khi require() ta stub môi trường Frappe tối thiểu.
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

const quotation = require(path.join(
    __dirname, "..", "..", "alumglass", "doctype", "overrides", "quotation.js"));
const pick = quotation.glass_pick;

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

// ── Đồng hồ giả cho debounce ────────────────────────────────────────────
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
            // Chạy cả timer được đặt TRONG callback của timer khác.
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
// (0) Tham số gửi get_variable_set_for_bom
// ═════════════════════════════════════════════════════════════════════════
check("(0a) dòng ĐÃ LƯU → args có quotation_item_name", () => {
    eq(pick.build_variable_set_args("BOM-0001", "QTN-ITEM-0001"),
        { bom_code: "BOM-0001", quotation_item_name: "QTN-ITEM-0001" });
});

check("(0b) dòng CHƯA lưu (new-...) → args KHÔNG có key quotation_item_name", () => {
    const args = pick.build_variable_set_args("BOM-0001", "new-quotation-item-3");
    eq(args, { bom_code: "BOM-0001" });
    assert(!("quotation_item_name" in args), "⛔ không được gửi dòng chưa lưu lên server");
    // Không có tên dòng (undefined/rỗng) → cũng không gửi
    assert(!("quotation_item_name" in pick.build_variable_set_args("BOM-0001", "")), "rỗng vẫn gửi");
    assert(!("quotation_item_name" in pick.build_variable_set_args("BOM-0001")), "undefined vẫn gửi");
});

// ═════════════════════════════════════════════════════════════════════════
// (1) Mã khởi tạo cho 4 effective_source
// ═════════════════════════════════════════════════════════════════════════
check("(1a) saved → hiện đúng mã đã chọn, nguồn saved", () => {
    const out = pick.initial({
        rep: "KINH_1", saved: "KINH-CUONG-LUC-8LY",
        effective_code: "KINH-CUONG-LUC-8LY", effective_source: "saved",
    });
    eq(out, { code: "KINH-CUONG-LUC-8LY", source: "saved", set_value: true, is_glass_master: true });
});

check("(1b) bom_default → hiện mã cố định của BOM (ô KHÔNG trống)", () => {
    const out = pick.initial({
        rep: "KINH_1", saved: "", default: "KINH-01",
        effective_code: "KINH-01", effective_source: "bom_default",
        effective_is_glass_master: true,
    });
    eq(out, { code: "KINH-01", source: "bom_default", set_value: true, is_glass_master: true });
});

check("(1c) item_code → hiện mã vật tư dòng kính đang dùng", () => {
    const out = pick.initial({
        rep: "__slug__kinh_canh", saved: "", default: "",
        effective_code: "KINH-TAM-5LY", effective_source: "item_code",
        effective_is_glass_master: true,
    });
    eq(out, { code: "KINH-TAM-5LY", source: "item_code", set_value: true, is_glass_master: true });
});

check("(1d) none → ô trống + nguồn none (chưa có mã nào)", () => {
    const out = pick.initial({
        rep: "__slug__kinh_canh", saved: "", default: "",
        effective_code: "", effective_source: "none",
    });
    eq(out, { code: "", source: "none", set_value: false, is_glass_master: true });
});

check("(1e) mã CLIENT thắng effective_code; server chưa biết mã đó → pending", () => {
    // glass_master_map của báo giá đang mở (savedFallback) khác với effective_code
    const out = pick.initial({ saved: "", effective_code: "KINH-01" }, "KINH-KHACH-CHON");
    eq(out, { code: "KINH-KHACH-CHON", source: "pending", set_value: true, is_glass_master: true });
});

check("(1f) server cũ (chưa có saved/effective_*) → vẫn như trước: default của BOM", () => {
    const out = pick.initial({ rep: "KINH_1", default: "KINH-01" }, "");
    eq(out, { code: "KINH-01", source: "bom_default", set_value: true, is_glass_master: true });
    const empty = pick.initial({ rep: "__slug__kinh_canh", default: "" }, "");
    eq(empty, { code: "", source: "none", set_value: false, is_glass_master: true });
});

check("(1g) giá trị rỗng/khoảng trắng không được coi là mã", () => {
    const out = pick.initial({ saved: "   ", effective_code: "  ", default: "" }, "");
    eq(out, { code: "", source: "none", set_value: false, is_glass_master: true });
});

// ── Mã giữ chỗ KHÔNG có trong danh mục kính (effective_is_glass_master) ──
check("(1h) effective_is_glass_master=false → KHÔNG nhét mã vào Link, vẫn giữ mã để hiện", () => {
    const out = pick.initial({
        rep: "__slug__kinh_canh", saved: "", default: "",
        effective_code: "KINH-01", effective_source: "item_code",
        effective_is_glass_master: false,
    });
    eq(out, { code: "KINH-01", source: "item_code", set_value: false, is_glass_master: false });
});

check("(1i) effective_is_glass_master=true → set vào Link như thường", () => {
    const out = pick.initial({ effective_code: "KINH-01", effective_source: "item_code",
        effective_is_glass_master: true });
    eq(out.set_value, true);
    eq(out.is_glass_master, true);
});

check("(1j) THIẾU cờ (server bản cũ) → giữ hành vi cũ, KHÔNG tự suy là mã giữ chỗ", () => {
    const out = pick.initial({ effective_code: "KINH-01", effective_source: "item_code" });
    eq(out.set_value, true);
    eq(out.is_glass_master, true);
});

check("(1k) đã có kính CHỌN (saved) → luôn set vào Link", () => {
    const out = pick.initial({ saved: "KINH-THAT", effective_code: "KINH-THAT",
        effective_source: "saved", effective_is_glass_master: false });
    eq(out.set_value, true);
    eq(out.is_glass_master, true);
});

check("(1l) group_price chỉ lấy 4 khoá giá của nhóm kính", () => {
    eq(pick.group_price({ has_price: true, price: 1, price_list: "BG", price_approx: true, rep: "X" }),
        { has_price: true, price: 1, price_list: "BG", price_approx: true });
    eq(pick.group_price(), { has_price: undefined, price: undefined,
        price_list: undefined, price_approx: undefined });
});

check("(1m) mã CLIENT khác mã server đã tính → source 'pending' (KHÔNG phải saved)", () => {
    // Dòng vừa đổi kính + Lưu nhưng preview chưa chạy: client biết mã MỚI,
    // server vẫn trả `saved`/`effective_code` của mã CŨ.
    const out = pick.initial({
        saved: "KINH-CU", effective_code: "KINH-CU", effective_source: "saved",
    }, "KINH-MOI");
    eq(out, { code: "KINH-MOI", source: "pending", set_value: true, is_glass_master: true });
});

check("(1n) client và server CÙNG mã → vẫn là 'saved'", () => {
    const out = pick.initial({
        saved: "KINH-CU", effective_code: "KINH-CU", effective_source: "saved",
    }, "KINH-CU");
    eq(out.source, "saved");
});

check("(1o) server CHƯA LƯU gì mà client có mã → 'pending' (DB chưa biết mã này)", () => {
    const out = pick.initial({ saved: "", effective_code: "KINH-01" }, "KINH-MOI");
    eq(out, { code: "KINH-MOI", source: "pending", set_value: true, is_glass_master: true });
});

check("(1o2) client trùng MÃ ENGINE đang dùng (dù map chưa có) → 'saved', không pending", () => {
    // TD biến global `glass_master` cũ: engine vẫn tính theo mã đó.
    const out = pick.initial({ saved: "", effective_code: "KINH-CU" }, "KINH-CU");
    eq(out, { code: "KINH-CU", source: "saved", set_value: true, is_glass_master: true });
});

check("(1p) server bản cũ (không có saved/effective_code) → không tự gắn pending", () => {
    const out = pick.initial({ default: "KINH-01" }, "KINH-KHACH-CHON");
    eq(out.source, "saved");
});

// ═════════════════════════════════════════════════════════════════════════
// Giá vẽ ngay khi mở dialog: KHÔNG dùng giá của mã khác
// ═════════════════════════════════════════════════════════════════════════
check("(1q) mã hiển thị ĐÚNG mã server đã tính → dùng giá của nhóm", () => {
    const g = { effective_code: "KINH-01", default: "KINH-01",
        has_price: true, price: 300000, price_list: "BG 2026", price_approx: false };
    eq(pick.price_for_initial("KINH-01", g), {
        has_price: true, price: 300000, price_list: "BG 2026", price_approx: false,
    });
});

check("(1r) mã hiển thị KHÁC mã server đã tính → null (phải gọi API, ⛔ không vẽ giá mã cũ)", () => {
    const g = { effective_code: "KINH-CU", default: "KINH-CU",
        has_price: true, price: 300000, price_list: "BG 2026" };
    eq(pick.price_for_initial("KINH-MOI", g), null);
    // Không có mã hiển thị → không vẽ gì
    eq(pick.price_for_initial("", g), {});
});

// ═════════════════════════════════════════════════════════════════════════
// Xoá trắng ô kính → quay về mã engine vẫn đang dùng
// ═════════════════════════════════════════════════════════════════════════
check("(1s) xoá trắng + nhóm có mã mặc định → về mã mặc định (bom_default)", () => {
    eq(pick.fallback_after_clear({ default: "KINH-01", effective_source: "item_code" }, ""),
        { code: "KINH-01", source: "bom_default", is_glass_master: true });
});

check("(1t) xoá trắng + có mã giữ chỗ → hiện lại mã giữ chỗ (không phải kính thật)", () => {
    eq(pick.fallback_after_clear({ default: "KINH-01", effective_source: "item_code" }, "KINH-01"),
        { code: "KINH-01", source: "item_code", is_glass_master: false });
});

check("(1u) xoá trắng + không có gì → 'none'", () => {
    eq(pick.fallback_after_clear({}, ""),
        { code: "", source: "none", is_glass_master: true });
});

// ═════════════════════════════════════════════════════════════════════════
// (2a) Câu trạng thái
// ═════════════════════════════════════════════════════════════════════════
check("(2a) câu trạng thái cho từng nguồn (không còn dòng hint riêng)", () => {
    eq(pick.status("saved"), {
        text: "Đã chọn cho báo giá này", tone: "ok",
    });
    eq(pick.status("bom_default"), {
        text: "Đang dùng mã cố định trên BOM · Đổi được nếu khách chọn kính khác.",
        // Trạng thái BÌNH THƯỜNG → trung tính, không hổ phách
        tone: "muted",
    });
    // item_code dùng CHUNG câu với bom_default — người dùng không cần biết
    // mã đó đến từ "default của BOM" hay "item_code của dòng".
    eq(pick.status("item_code"), pick.status("bom_default"));
    eq(pick.status("none"), {
        text: "Chưa có mã kính — chọn kính cho vị trí này", tone: "muted",
    });
    // Đổi kính: hệ thống TỰ tính lại — ⛔ không bảo người dùng bấm "Tính giá"
    eq(pick.status("override"), {
        text: "Đang áp dụng kính mới — tự tính lại giá sau giây lát",
        tone: "warn",
    });
    eq(pick.status("pending"), pick.status("override"));
    // Tính giá xong → trạng thái chốt
    eq(pick.status("applied"), { text: "Đã áp dụng", tone: "ok" });
    // Nguồn lạ → câu an toàn, KHÔNG hiện mã nội bộ
    eq(pick.status("xyz_lạ"), pick.status("none"));
});

check("(2a1) hiện TÊN kính, không chỉ mã", () => {
    eq(pick.status("saved", { code: "GM-01", name: "Kính trắng 8 mm" }), {
        text: "Đã chọn: Kính trắng 8 mm (GM-01)", tone: "ok",
    });
    eq(pick.status("bom_default", { code: "GM-01", name: "Kính trắng 8 mm" }), {
        text: "Đang dùng mã cố định trên BOM: Kính trắng 8 mm (GM-01)"
            + " · Đổi được nếu khách chọn kính khác.",
        tone: "muted",
    });
    // Thiếu tên → chỉ mã; thiếu mã → chỉ tên (không ra "()" rỗng)
    eq(pick.status("saved", { code: "GM-01" }).text, "Đã chọn: GM-01");
    eq(pick.status("saved", { name: "Kính trắng 8 mm" }).text, "Đã chọn: Kính trắng 8 mm");
    eq(pick.code_label("GM-01", "Kính trắng"), "Kính trắng (GM-01)");
    eq(pick.code_label("", ""), "");
});

check("(2a2) mã giữ chỗ không có trong danh mục → nêu ĐÚNG mã + lối xử lý", () => {
    const out = pick.status("item_code", { code: "KINH-01", is_glass_master: false });
    eq(out, {
        text: "Mã đại diện trên BOM: KINH-01 (không phải kính trong danh mục)"
            + " · Chọn kính thật cho vị trí này.",
        tone: "warn",
    });
});

check("(2a3) is_glass_master=true hoặc thiếu mã → câu trạng thái bình thường", () => {
    eq(pick.status("item_code", { code: "KINH-01", is_glass_master: true }).tone, "muted");
    eq(pick.status("item_code", { code: "", is_glass_master: false }), pick.status("item_code"));
    eq(pick.status("saved", { code: "K-1" }).tone, "ok");
});

// ═════════════════════════════════════════════════════════════════════════
// (2b) Câu giá
// ═════════════════════════════════════════════════════════════════════════
check("(2b) có giá → 'Giá: 300.000 đ'", () => {
    eq(pick.price_text({ has_price: true, price: 300000, price_list: "Bảng giá bán lẻ 2026" }),
        "Giá: 300.000 đ");
});

check("(2c) không có giá → nêu TÊN bảng giá đang tra", () => {
    eq(pick.price_text({ has_price: false, price: 0, price_list: "Bảng giá bán lẻ 2026" }),
        "Chưa có giá trong bảng giá Bảng giá bán lẻ 2026");
});

check("(2d) không có giá + không rõ bảng giá → câu vẫn chỉ ra việc cần làm", () => {
    eq(pick.price_text({ has_price: false }),
        "Chưa có giá — kiểm tra bảng giá đang áp dụng");
});

check("(2e) giá tạm tính (chưa áp màu/độ dày) → có ≈ và ghi chú", () => {
    eq(pick.price_text({ has_price: true, price: 1234567, approx: true }),
        "Giá: ≈ 1.234.567 đ (giá chốt khi tính lại xong)");
    // Tên trường từ glass_groups của server là price_approx
    eq(pick.price_text({ has_price: true, price: 500, price_approx: true }),
        "Giá: ≈ 500 đ (giá chốt khi tính lại xong)");
});

check("(2f) trạng thái tải / lỗi / dòng chưa lưu", () => {
    eq(pick.price_text({ state: "loading" }), "Đang lấy giá...");
    // Lỗi mạng: câu chung, ⛔ không phơi exception
    eq(pick.price_text({ state: "error" }), "Chưa lấy được giá, thử lại");
    eq(pick.price_text({ state: "unsaved" }), "Giá hiện sau khi lưu dòng và hệ thống tính lại.");
    // Server nói rõ lý do (mã không tồn tại) → hiện đúng câu đó
    eq(pick.price_text({ state: "invalid", message: "Mã kính không tồn tại" }),
        "Mã kính không tồn tại");
    eq(pick.price_text({ state: "invalid" }), "Mã kính này không dùng được, chọn mã khác");
});

check("(2g) server CHƯA trả thông tin giá → không bịa 'Chưa có giá'", () => {
    eq(pick.price_text({}), "");
    eq(pick.price_text(), "");
});

check("(2h) giá 0 là giá THẬT khi has_price=true (không suy từ price>0)", () => {
    eq(pick.price_text({ has_price: true, price: 0 }), "Giá: 0 đ");
    eq(pick.price_text({ has_price: false, price: 0, price_list: "BG 2026" }),
        "Chưa có giá trong bảng giá BG 2026");
});

check("(2i) format_price ngăn nghìn bằng dấu chấm", () => {
    eq(pick.format_price(300000), "300.000 đ");
    eq(pick.format_price(0), "0 đ");
    eq(pick.format_price("1234567.4"), "1.234.567 đ");
    eq(pick.format_price(null), "0 đ");
    eq(pick.format_price(undefined), "0 đ");
});

// ═════════════════════════════════════════════════════════════════════════
// (3a) Chuẩn hoá phản hồi API
// ═════════════════════════════════════════════════════════════════════════
check("(3a) bóc `r.message` của frappe.call", () => {
    const out = pick.normalize_price_response({
        message: { success: true, code: "K1", name: "Kính cường lực", price: 300000,
            price_list: "BG 2026", has_price: true, approx: false },
    }, "K1-DU-PHONG");
    eq(out, {
        ok: true, state: "ok", code: "K1", name: "Kính cường lực",
        price: 300000, price_list: "BG 2026", has_price: true, approx: false, note: "",
    });
});

check("(3b) success:false + câu người đọc được → hiện câu đó", () => {
    const out = pick.normalize_price_response(
        { success: false, message: "Mã kính không tồn tại trong danh mục" }, "K-XX");
    eq(out.state, "invalid");
    eq(out.message, "Mã kính không tồn tại trong danh mục");
    eq(pick.price_text(out), "Mã kính không tồn tại trong danh mục");
});

check("(3c) success:false + rác kỹ thuật → câu chung, không phơi lỗi", () => {
    const out = pick.normalize_price_response(
        { success: false, message: "Traceback (most recent call last):\n  File \"x.py\", line 3" }, "K-XX");
    eq(out.state, "error");
    assert(!out.message, "không được mang message kỹ thuật");
    eq(pick.price_text(out), "Chưa lấy được giá, thử lại");
});

check("(3d) phản hồi rỗng/không phải object → lỗi chung, không throw", () => {
    eq(pick.normalize_price_response(null, "K1").state, "error");
    eq(pick.normalize_price_response("boom", "K1").state, "error");
    // Object lỗi của frappe.call (không phải payload giá) → KHÔNG được đoán
    // thành "không có giá"
    eq(pick.normalize_price_response({ exc_type: "ValidationError", message: "x" }, "K1").state, "error");
    eq(pick.normalize_price_response({ _server_messages: "[]" }, "K1").state, "error");
});

check("(3e) có giá nhưng chưa áp màu/độ dày → approx giữ nguyên", () => {
    const out = pick.normalize_price_response(
        { success: true, code: "K1", price: 200000, has_price: true, approx: true }, "K1");
    eq(out.approx, true);
    eq(pick.price_text(out), "Giá: ≈ 200.000 đ (giá chốt khi tính lại xong)");
});

// ═════════════════════════════════════════════════════════════════════════
// (3b) Debounce 300ms — đổi mã liên tiếp chỉ gọi API 1 lần
// ═════════════════════════════════════════════════════════════════════════
function makeRequester(opts) {
    opts = opts || {};
    const timers = makeFakeTimers();
    const calls = [];
    const requester = pick.make_price_requester({
        quotation_item_name: "QTN-ITEM-0001",
        timers: timers,
        call(method, args, cb, err_cb) {
            calls.push({ method, args, cb, err_cb });
        },
    });
    return { requester, timers, calls };
}

check("(3f) đổi mã 3 lần liên tiếp → chỉ 1 lần gọi, dùng mã CUỐI, sau 300ms", () => {
    const h = makeRequester();
    const got = [];
    h.requester.request("K1", (r) => got.push(r));
    h.requester.request("K2", (r) => got.push(r));
    h.requester.request("K3", (r) => got.push(r));
    eq(h.calls.length, 0, "chưa hết debounce thì chưa được gọi");
    h.timers.advance(299);
    eq(h.calls.length, 0, "299ms chưa đủ debounce");
    h.timers.advance(1);
    eq(h.calls.length, 1, "phải gọi ĐÚNG 1 lần");
    eq(h.calls[0].method, "alumglass.api.get_glass_master_price");
    eq(h.calls[0].args, { quotation_item_name: "QTN-ITEM-0001", glass_code: "K3" });
    // Chưa có phản hồi → chưa cập nhật UI
    eq(got.length, 0);
    // Server trả giá
    h.calls[0].cb({ message: { success: true, code: "K3", price: 450000, has_price: true } });
    eq(got.length, 1);
    eq(pick.price_text(got[0]), "Giá: 450.000 đ");
});

check("(3g) kết quả về MUỘN của lần gõ trước bị bỏ (chống race)", () => {
    const h = makeRequester();
    const got = [];
    h.requester.request("K1", (r) => got.push("K1:" + r.code));
    h.timers.advance(300);
    h.requester.request("K2", (r) => got.push("K2:" + r.code));
    h.timers.advance(300);
    eq(h.calls.length, 2);
    // K2 trả trước, K1 trả sau (mạng chậm)
    h.calls[1].cb({ message: { success: true, code: "K2", price: 100, has_price: true } });
    h.calls[0].cb({ message: { success: true, code: "K1", price: 200, has_price: true } });
    eq(got, ["K2:K2"], "chỉ kết quả MỚI NHẤT được áp");
});

check("(3h) cancel() huỷ lần gọi đang chờ", () => {
    const h = makeRequester();
    h.requester.request("K1", () => {});
    h.requester.cancel();
    h.timers.advance(1000);
    eq(h.calls.length, 0, "đã huỷ thì không gọi");
    eq(h.timers.pending(), 0);
});

check("(3i) delay mặc định đúng 300ms", () => {
    eq(pick.DEBOUNCE_MS, 300);
    const h = makeRequester();
    h.requester.request("K1", () => {});
    h.timers.advance(299);
    eq(h.calls.length, 0);
    h.timers.advance(1);
    eq(h.calls.length, 1);
});

check("(3j) lỗi mạng → 'Chưa lấy được giá, thử lại' (không phơi exception)", () => {
    const h = makeRequester();
    const got = [];
    h.requester.request("K1", (r) => got.push(r));
    h.timers.advance(300);
    h.calls[0].err_cb({ status: 500, message: "Internal Server Error" });
    eq(got.length, 1);
    eq(pick.price_text(got[0]), "Chưa lấy được giá, thử lại");
});

check("(3k) lỗi mạng về SAU kết quả mới hơn → bị bỏ", () => {
    const h = makeRequester();
    const got = [];
    h.requester.request("K1", (r) => got.push(r.code));
    h.timers.advance(300);
    h.requester.request("K2", (r) => got.push(r.code));
    h.timers.advance(300);
    h.calls[0].err_cb();
    eq(got, [], "lỗi của lần gõ cũ không được đè kết quả mới");
    h.calls[1].cb({ message: { success: true, code: "K2", price: 100, has_price: true } });
    eq(got, ["K2"]);
});

// ═════════════════════════════════════════════════════════════════════════
// (4) CHỮ KÝ lựa chọn kính — nguồn sự thật của "giá đã theo kính nào"
//     Phủ 2 đường lỗi CHẶN: xoá trắng ô kính và đổi kính khi preview đang chạy.
// ═════════════════════════════════════════════════════════════════════════
const sig = (list) => pick.glass_signature(list);

check("(4a) cùng lựa chọn, khác thứ tự phần tử → CÙNG chữ ký", () => {
    eq(sig([{ rep: "KINH_1", code: "GM-01" }, { rep: "KINH_2", code: "GM-02" }]),
        sig([{ rep: "KINH_2", code: "GM-02" }, { rep: "KINH_1", code: "GM-01" }]));
});

check("(4b) đổi mã kính → chữ ký KHÁC", () => {
    const before = sig([{ rep: "KINH_1", code: "GM-01" }]);
    const after = sig([{ rep: "KINH_1", code: "GM-02" }]);
    assert(before !== after, "đổi mã phải đổi chữ ký");
});

check("(4c) xoá trắng ô kính → chữ ký KHÁC (mã rỗng vẫn được ghi)", () => {
    const before = sig([{ rep: "KINH_1", code: "GM-01" }]);
    const after = sig([{ rep: "KINH_1", code: "" }]);
    assert(before !== after, "xoá trắng phải đổi chữ ký");
    eq(after, '[["KINH_1",""]]', "mã rỗng vẫn ghi thành cặp");
});

check("(4d) 'chưa chọn kính' KHÁC 'không có vị trí kính nào'", () => {
    assert(sig([{ rep: "KINH_1", code: "" }]) !== sig([]));
    eq(sig([]), "[]");
    eq(sig(null), "[]");
    eq(sig(undefined), "[]");
});

check("(4e) mã có khoảng trắng thừa → bỏ, không tạo chữ ký giả", () => {
    eq(sig([{ rep: "KINH_1", code: "  GM-01  " }]),
        sig([{ rep: "KINH_1", code: "GM-01" }]));
});

check("(4f) dialog truyền thẳng entry ({rep, display_code}) → đọc display_code", () => {
    eq(sig([{ rep: "KINH_1", display_code: "GM-01" }]),
        sig([{ rep: "KINH_1", code: "GM-01" }]));
    // Entry chưa có mã nào → coi như "chưa chọn"
    eq(sig([{ rep: "KINH_1" }]), sig([{ rep: "KINH_1", code: "" }]));
});

check("(4g) mở lại dialog với CÙNG dữ liệu → chữ ký GIỐNG (không bắt tính lại)", () => {
    const engineDaTinh = [{ rep: "KINH_1", code: "GM-01" }, { rep: "KINH_2", code: "" }];
    const moLai = [{ rep: "KINH_2", display_code: "" }, { rep: "KINH_1", display_code: "GM-01" }];
    eq(pick.needs_recalc(sig(moLai), sig(engineDaTinh)), false);
});

check("(4h) ĐƯỜNG LỖI 1 — xoá trắng → về mã mặc định của BOM ⇒ vẫn phải tính lại", () => {
    // Lần tính giá gần nhất chạy với mã người dùng chọn (GM-02)
    const daApDung = sig([{ rep: "__slug__kinh_canh", code: "GM-02" }]);
    // Xoá trắng → ô hiện lại mã engine vẫn dùng (mã cố định trên BOM)
    const sauKhiXoa = sig([{ rep: "__slug__kinh_canh", code: "KINH-01" }]);
    eq(pick.needs_recalc(sauKhiXoa, daApDung), true);
    // ... kể cả khi không còn mã nào (nguồn "none")
    eq(pick.needs_recalc(sig([{ rep: "__slug__kinh_canh", code: "" }]), daApDung), true);
});

check("(4i) ĐƯỜNG LỖI 2 — đổi kính trong lúc preview đang chạy ⇒ vẫn phải tính lại", () => {
    const chup = sig([{ rep: "KINH_1", code: "GM-01" }]);      // chụp lúc lượt bắt đầu
    const hienTai = sig([{ rep: "KINH_1", code: "GM-02" }]);   // đổi giữa lúc chạy
    eq(pick.needs_recalc(hienTai, chup), true);
});

check("(4j) should_mark_applied FALSE khi kính đổi trong lúc lượt đó chạy", () => {
    const chup = sig([{ rep: "KINH_1", code: "GM-01" }]);
    const hienTai = sig([{ rep: "KINH_1", code: "GM-02" }]);
    eq(pick.should_mark_applied(hienTai, chup), false);
    // Xoá trắng giữa lúc chạy cũng vậy
    eq(pick.should_mark_applied(sig([{ rep: "KINH_1", code: "" }]), chup), false);
});

check("(4k) should_mark_applied TRUE khi kính không đổi (khác thứ tự key)", () => {
    const chup = sig([{ rep: "KINH_2", code: "GM-02" }, { rep: "KINH_1", code: "GM-01" }]);
    const hienTai = sig([{ rep: "KINH_1", code: "GM-01" }, { rep: "KINH_2", code: "GM-02" }]);
    eq(pick.should_mark_applied(hienTai, chup), true);
});

check("(4l) chưa có lượt tính giá nào (chưa chụp) → KHÔNG gắn 'Đã áp dụng'", () => {
    const hienTai = sig([{ rep: "KINH_1", code: "GM-01" }]);
    eq(pick.should_mark_applied(hienTai, undefined), false);
    eq(pick.should_mark_applied(hienTai, null), false);
});

check("(4m) needs_recalc: cùng rỗng → không tính lại; một bên rỗng → có", () => {
    eq(pick.needs_recalc("[]", "[]"), false);
    eq(pick.needs_recalc("", ""), false);
    eq(pick.needs_recalc(undefined, null), false);
    eq(pick.needs_recalc(null, "[]"), true);
});

check("(4n) mô phỏng nút 💾 Lưu: xoá trắng → tính lại xong MỚI cho đóng", () => {
    let daApDung = sig([{ rep: "KINH_1", code: "GM-01" }]);
    const hienTai = sig([{ rep: "KINH_1", code: "" }]);   // người dùng vừa xoá trắng
    eq(pick.needs_recalc(hienTai, daApDung), true);        // ⛔ chưa được đóng
    // Server tính lại xong → chỉ chốt được khi chữ ký hiện tại đúng là chữ ký đã chụp
    eq(pick.should_mark_applied(hienTai, hienTai), true);
    daApDung = hienTai;
    eq(pick.needs_recalc(hienTai, daApDung), false);       // giờ đóng được
});

check("(4o) _needs_glass_recalc của dialog dùng CHỮ KÝ (không còn xét `source`)", () => {
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    dlg._glass_controls = [
        { rep: "KINH_1", display_code: "GM-02", source: "override" },
        { rep: "__slug__kinh_canh", display_code: "", source: "none" },
    ];
    dlg._glass_applied_signature = pick.glass_signature(dlg._glass_controls);
    eq(dlg._needs_glass_recalc(), false, "chữ ký khớp ⇒ Lưu đóng được");
    // Đổi mã 1 vị trí
    dlg._glass_controls[0].display_code = "GM-03";
    eq(dlg._needs_glass_recalc(), true, "đổi mã ⇒ phải tính lại");
    // ĐƯỜNG LỖI 1: xoá trắng → nguồn thành bom_default, chữ ký đổi theo
    dlg._glass_controls[0].display_code = "KINH-01";
    dlg._glass_controls[0].source = "bom_default";
    eq(dlg._needs_glass_recalc(), true, "nguồn bom_default vẫn phải tính lại");
});

check("(4p) _mark_glass_applied KHÔNG gắn 'Đã áp dụng' khi kính đổi giữa lượt", () => {
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    const entry = { rep: "KINH_1", display_code: "GM-02", source: "override" };
    dlg._glass_controls = [entry];
    dlg._render_glass_state = () => {};
    const chup = pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]);
    eq(dlg._mark_glass_applied(chup), false, "kết quả của mã CŨ ⇒ không gắn nhãn");
    eq(entry.source, "override", "phải giữ 'Đang áp dụng…'");
    // Lượt mới chụp đúng mã đang hiện → mới được gắn
    eq(dlg._mark_glass_applied(pick.glass_signature([{ rep: "KINH_1", code: "GM-02" }])), true);
    eq(entry.source, "applied");
    eq(dlg._needs_glass_recalc(), false, "chữ ký đã chốt ⇒ Lưu thấy khớp");
});

check("(4q) lượt cũ về muộn khi kính đã đổi → KHÔNG đánh thức Lưu, tính lại NGAY", () => {
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    dlg._glass_controls = [{ rep: "KINH_1", display_code: "GM-02", source: "override" }];
    dlg._render_glass_state = () => {};
    dlg.dialog = {};
    dlg._dialog_open = true;
    let ran = 0, finished = 0;
    dlg._run_preview = () => { ran += 1; };
    dlg._finish_preview_waiters = () => { finished += 1; };
    dlg._cancel_auto_preview = () => {};
    const chup = pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]);
    eq(dlg._finish_preview_with_glass(chup), false);
    eq(ran, 1, "phải chạy lượt mới ngay (không chờ debounce 700ms)");
    eq(finished, 0, "chưa được đánh thức nút 💾 Lưu");
});

check("(4r) mở lại dialog với job nền Queued rồi ĐỔI kính → kết quả cũ KHÔNG gắn nhãn", () => {
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    const entry = { rep: "KINH_1", display_code: "GM-01", source: "saved" };
    dlg._glass_controls = [entry];
    dlg._render_glass_state = () => {};
    dlg._cleanup_realtime = () => {};
    dlg._preview_container = () => $();
    dlg._apply_rate = () => {};
    dlg._render_display_model = () => {};
    dlg.child_doc = { name: "QTN-ITEM-0001", doctype: "Quotation Item" };
    dlg.dialog = {};
    dlg._dialog_open = true;
    let ran = 0, finished = 0, alertMsg = null;
    dlg._run_preview = () => { ran += 1; };
    dlg._finish_preview_waiters = () => { finished += 1; };
    dlg._cancel_auto_preview = () => {};
    // Stub tối thiểu cho nhánh realtime
    let handler = null;
    const old_realtime = global.frappe.realtime;
    global.frappe.realtime = { on(ev, fn) { handler = fn; }, off() {} };
    global.frappe.model = global.frappe.model || { set_value() {} };
    const old_alert = global.frappe.show_alert;
    global.frappe.show_alert = (o) => { alertMsg = o && o.message; };
    try {
        // Lúc gắn lại listener: kính đang hiện là GM-01 ⇒ đó là chữ ký của job
        dlg._listen_realtime("JOB-1", $(), dlg._glass_current_signature());
        // Người dùng đổi sang GM-02 TRƯỚC KHI job cũ trả kết quả
        dlg._glass_controls[0].display_code = "GM-02";
        handler({ job_id: "JOB-1", status: "Success", result: {} });
    } finally {
        global.frappe.realtime = old_realtime;
        global.frappe.show_alert = old_alert;
    }
    eq(entry.source, "saved", "⛔ không được gắn 'Đã áp dụng' cho mã người dùng vừa chọn");
    eq(ran, 1, "phải tính lại ngay cho mã mới");
    eq(finished, 0, "chưa được đánh thức nút 💾 Lưu");
    eq(alertMsg, null, "không báo 'Tính giá xong' khi kết quả là của mã cũ");
});

check("(4s) mở lại dialog với job nền Queued, KHÔNG đổi gì → vẫn gắn 'Đã áp dụng'", () => {
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    const entry = { rep: "KINH_1", display_code: "GM-01", source: "saved" };
    dlg._glass_controls = [entry];
    dlg._render_glass_state = () => {};
    dlg._cleanup_realtime = () => {};
    dlg._preview_container = () => $();
    dlg._apply_rate = () => {};
    dlg._render_display_model = () => {};
    dlg.child_doc = { name: "QTN-ITEM-0001", doctype: "Quotation Item" };
    dlg.dialog = {};
    dlg._dialog_open = true;
    let ran = 0, finished = 0, alertMsg = null;
    dlg._run_preview = () => { ran += 1; };
    dlg._finish_preview_waiters = () => { finished += 1; };
    dlg._cancel_auto_preview = () => {};
    let handler = null;
    const old_realtime = global.frappe.realtime;
    global.frappe.realtime = { on(ev, fn) { handler = fn; }, off() {} };
    global.frappe.model = global.frappe.model || { set_value() {} };
    const old_alert = global.frappe.show_alert;
    global.frappe.show_alert = (o) => { alertMsg = o && o.message; };
    try {
        dlg._listen_realtime("JOB-1", $(), dlg._glass_current_signature());
        handler({ job_id: "JOB-1", status: "Success", result: {} });
    } finally {
        global.frappe.realtime = old_realtime;
        global.frappe.show_alert = old_alert;
    }
    eq(entry.source, "saved", "dòng chưa ai chạm thì giữ nhãn 'Đã chọn…'");
    eq(dlg._glass_applied_signature, dlg._glass_current_signature(),
        "chữ ký đã chốt ⇒ state coi như đã áp dụng");
    eq(dlg._needs_glass_recalc(), false, "nút 💾 Lưu thấy khớp, không bắt tính lại");
    eq(finished, 1, "đánh thức nút 💾 Lưu");
    eq(ran, 0, "không chạy thêm lượt nào");
    eq(alertMsg, "Tính giá xong");
});

check("(4t) câu cảnh báo nêu ĐÚNG việc phải làm (mở lại rồi bấm Preview)", () => {
    eq(pick.RECALC_FAILED_MESSAGE,
        "Chưa tính lại được giá kính — dòng đang giữ giá cũ."
        + " Mở lại bảng tham số rồi bấm \"Preview tính giá\" để tính lại.");
    // Dialog dùng ĐÚNG câu đó (một nguồn duy nhất, không chép lại chữ)
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    let msg = null;
    const old_alert = global.frappe.show_alert;
    global.frappe.show_alert = (o) => { msg = o && o.message; };
    try { dlg._alert_recalc_failed(); } finally { global.frappe.show_alert = old_alert; }
    eq(msg, pick.RECALC_FAILED_MESSAGE);
});

check("(2a4) 'Đã áp dụng' nêu TÊN kính như các trạng thái khác", () => {
    eq(pick.status("applied", { code: "GM-01", name: "Kính trắng 8 mm" }), {
        text: "Đã áp dụng: Kính trắng 8 mm (GM-01)", tone: "ok",
    });
    eq(pick.status("applied", { code: "GM-01" }).text, "Đã áp dụng: GM-01");
});

console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed +
    "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
