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
// `__` nội suy `{0}`/`{1}` như Frappe thật để câu báo kiểm được ĐÚNG số dòng.
global.__ = function (s, args) {
    let out = String(s);
    if (args && args.length !== undefined) {
        out = out.replace(/\{(\d+)\}/g, (m, i) => (
            args[Number(i)] === undefined ? m : String(args[Number(i)])));
    }
    return out;
};
global.document = {};
// Giữ lại handler đã đăng ký để ca (13c)/(14a) gọi `after_save` đúng như Frappe.
// đúng như Frappe sẽ gọi.
const FORM_EVENTS = {};
global.frappe = {
    provide(ns) {
        const parts = String(ns).split(".");
        let obj = global;
        parts.forEach((p) => {
            if (!obj[p]) obj[p] = {};
            obj = obj[p];
        });
    },
    ui: {
        form: {
            on(doctype, handlers) {
                FORM_EVENTS[doctype] = Object.assign({}, FORM_EVENTS[doctype] || {}, handlers);
            },
        },
    },
    utils: {},
    call() {},
    // Trình duyệt luôn có `frappe.show_alert`; harness cần bản no-op mặc định
    // để đường báo lỗi (VD `_alert_recalc_failed`) không ném TypeError khi
    // không có test nào stub.
    show_alert() {},
    get_doc() { return {}; },
};

// ── Frappe Dialog tối thiểu (ca 13 dựng BOMDialog / _render_dialog) ─────
// Chỉ đủ để code nghiệp vụ chạy: giữ `opts` (kiểm nhãn nút), `set_value`
// (kiểm HTML đã render), `hide()` (kiểm dialog có đóng), `$wrapper.find`.
const DIALOG_INSTANCES = [];
function fakeWrapper() {
    return {
        length: 1,
        _html: "",
        html(v) { if (v === undefined) return this._html; this._html = String(v); return this; },
        append() { return this; }, prepend() { return this; },
        find() { return this; }, text() { return this; },
        css() { return this; }, addClass() { return this; },
        removeClass() { return this; }, attr() { return this; },
        on() { return this; }, empty() { return this; },
    };
}
global.frappe.ui.Dialog = function (opts) {
    this.opts = opts || {};
    this.values = {};
    this.hidden = 0;
    this.shown = 0;
    this.primary_disabled = false;
    this.fields_dict = {};
    (this.opts.fields || []).forEach((f) => {
        this.fields_dict[f.fieldname] = { $wrapper: fakeWrapper() };
    });
    this.$wrapper = fakeWrapper();
    DIALOG_INSTANCES.push(this);
};
global.frappe.ui.Dialog.prototype.show = function () { this.shown += 1; };
// Giống Frappe: `hide()` phát `hide.bs.modal` ⇒ gọi `opts.onhide` (đúng cho cả
// nút X / Esc / click nền vì modal đều đi qua cùng sự kiện).
global.frappe.ui.Dialog.prototype.hide = function () {
    this.hidden += 1;
    if (this.opts && typeof this.opts.onhide === "function") this.opts.onhide();
};
global.frappe.ui.Dialog.prototype.disable_primary_action = function () { this.primary_disabled = true; };
global.frappe.ui.Dialog.prototype.enable_primary_action = function () { this.primary_disabled = false; };
global.frappe.ui.Dialog.prototype.set_value = function (fieldname, value) {
    this.values[fieldname] = value;
};
global.frappe.ui.Dialog.prototype.get_value = function () { return undefined; };
global.frappe.ui.Dialog.prototype.add_custom_action = function () {};
global.frappe.ui.Dialog.prototype.set_primary_action = function () {};
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

// Renderer dùng chung (`render_bom_result_display`) cần 2 hàm định dạng này.
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
    eq(alertMsg, "Tính giá xong — chưa lưu vào báo giá.");
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

// ═════════════════════════════════════════════════════════════════════════
// (5) Nút 💾 Lưu — GHI THẬT xuống DB trước khi đóng dialog
//     `_save()` chỉ cập nhật bộ nhớ trình duyệt; trước đây bấm Lưu là đóng
//     dialog luôn ⇒ reload mất phần vừa sửa, `Quotation Item` giữ giá trị cũ.
// ═════════════════════════════════════════════════════════════════════════
const asyncChecks = [];
function checkAsync(name, fn) { asyncChecks.push({ name: name, fn: fn }); }

function flush() { return new Promise((resolve) => setTimeout(resolve, 0)); }

// Dialog giả tối thiểu cho `_on_primary_action`.
function makeDialog(opts) {
    opts = opts || {};
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    dlg.frm = opts.frm || { doc: {} };
    dlg.child_doc = opts.child_doc || { name: "QTN-ITEM-0001", doctype: "Quotation Item" };
    dlg.hidden = 0;
    dlg.dialog = opts.dialog || { hide() { dlg.hidden += 1; } };
    dlg._var_controls = [];
    dlg._color_controls = [];
    dlg._glass_controls = opts.glass_controls || [];
    dlg._glass_applied_signature = opts.applied_sig || null;
    dlg._preview_inflight = false;
    dlg._preview_waiters = [];
    dlg._preview_seq = 0;
    dlg._save = () => {};
    dlg._cancel_auto_preview = () => {};
    return dlg;
}

// Thay `_sync_row_to_db` bằng spy, trả về bản gốc để restore.
function withSyncSpy(impl) {
    const q = quotation.quotation;
    const orig = q._sync_row_to_db;
    const calls = [];
    q._sync_row_to_db = function () {
        calls.push(Array.prototype.slice.call(arguments));
        return impl ? impl.apply(this, arguments) : Promise.resolve(arguments[2]);
    };
    return { calls: calls, restore() { q._sync_row_to_db = orig; } };
}

// Thay `frappe.get_doc` bằng stub (mặc định trả object rỗng) — trả bản gốc để restore.
function withGetDocSpy(impl) {
    const orig = global.frappe.get_doc;
    global.frappe.get_doc = impl || (() => ({}));
    return { restore() { global.frappe.get_doc = orig; } };
}

// Dòng có ĐẾM số lần ghi từng field — để kiểm "hai đường trùng 1 object thì
// ⛔ không ghi 2 lần".
function makeCountedRow(base) {
    const row = Object.assign({}, base);
    const writes = {};
    ["al_bom", "al_bom_version", "al_bom_vars", "item_code", "item_name"].forEach((f) => {
        let val = row[f];
        delete row[f];
        Object.defineProperty(row, f, {
            enumerable: true,
            configurable: true,
            get() { return val; },
            set(v) { val = v; writes[f] = (writes[f] || 0) + 1; },
        });
    });
    return { row: row, writes: writes };
}

const ROW_FIELDS = ["al_bom", "al_bom_version", "al_bom_vars", "item_code", "item_name"];

checkAsync("(5a) 💾 Lưu thường → CHỈ cập nhật dòng trên form, ⛔ KHÔNG ghi DB, đóng ngay", async () => {
    const tracked = makeCountedRow({ name: "QTN-ITEM-0001", idx: 3, doctype: "Quotation Item" });
    const row = tracked.row;
    const flags = { dirty: 0, refresh: [] };
    const frm = {
        doc: { items: [row] },
        dirty() { flags.dirty += 1; },
        refresh_field(f) { flags.refresh.push(f); },
    };
    // Dialog giữ object KHÁC dòng trong lưới; `frappe.get_doc` trả ĐÚNG dòng lưới
    // ⇒ hai đường cùng trỏ về MỘT object (phải ghi 1 lần, không 2).
    const dlgDoc = { name: "QTN-ITEM-0001", doctype: "Quotation Item" };
    const dlg = makeDialog({ frm: frm, child_doc: dlgDoc });
    dlg._save = function () {
        dlg.child_doc.al_bom = "BOM-0001";
        dlg.child_doc.al_bom_version = "V1";
        dlg.child_doc.al_bom_vars = '{"KINH_1":"GM-02"}';
        dlg.child_doc.item_code = "SP-01";
        dlg.child_doc.item_name = "Cửa sổ 1";
    };
    const sync = withSyncSpy();
    const getDoc = withGetDocSpy(() => row);
    try {
        await dlg._on_primary_action();
        await flush();
    } finally { sync.restore(); getDoc.restore(); }
    eq(sync.calls.length, 0, "⛔ nút Lưu KHÔNG ghi DB — ghi DB là việc của Lưu phiếu");
    eq(flags.dirty, 1, "phải đánh dấu phiếu có thay đổi (nút Lưu phiếu bật)");
    eq(flags.refresh, ["items"], "phải vẽ lại lưới items");
    eq(row.al_bom_vars, '{"KINH_1":"GM-02"}', "dòng trong frm.doc.items nhận al_bom_vars");
    eq(row.al_bom, "BOM-0001", "… nhận al_bom");
    eq(row.al_bom_version, "V1", "… nhận al_bom_version");
    eq(row.item_code, "SP-01", "… nhận item_code");
    ROW_FIELDS.forEach((f) => {
        eq(tracked.writes[f], 1, "hai đường trùng 1 object ⇒ field " + f + " chỉ ghi 1 lần");
    });
    eq(dlg.hidden, 1, "cập nhật dòng xong là đóng NGAY (không chờ mạng)");
    eq(dlgDoc.al_bom_vars, '{"KINH_1":"GM-02"}', "object dialog cũng mang giá trị mới");
});

checkAsync("(5b) dialog giữ object KHÁC dòng lưới (dò theo idx) ⇒ cập nhật CẢ HAI", async () => {
    const formRow = { idx: 2, doctype: "Quotation Item" };  // chưa có `name`
    const dlgDoc = { name: "QTN-ITEM-0001", idx: 2, doctype: "Quotation Item" };
    const frm = { doc: { items: [formRow] }, dirty() {}, refresh_field() {} };
    const dlg = makeDialog({ frm: frm, child_doc: dlgDoc });
    dlg._save = function () {
        dlg.child_doc.al_bom = "BOM-0002";
        dlg.child_doc.al_bom_vars = '{"KINH_1":"GM-09"}';
        dlg.child_doc.item_code = "SP-09";
    };
    const getDoc = withGetDocSpy(() => dlgDoc);
    try {
        await dlg._on_primary_action();
        await flush();
    } finally { getDoc.restore(); }
    eq(formRow.al_bom_vars, '{"KINH_1":"GM-09"}', "dòng lưới phải nhận tham số (thiếu là Lưu phiếu mất)");
    eq(formRow.al_bom, "BOM-0002", "… nhận al_bom");
    eq(formRow.item_code, "SP-09", "… nhận item_code");
    eq(dlgDoc.al_bom_vars, '{"KINH_1":"GM-09"}', "object dialog cũng được giữ đồng bộ");
    eq(dlg.hidden, 1);
});

checkAsync("(5c) cần tính lại kính → preview NGAY (⛔ không sync DB) → mới đóng", async () => {
    const row = { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const flags = { dirty: 0, refresh: [] };
    const frm = {
        doc: { items: [row] },
        dirty() { flags.dirty += 1; },
        refresh_field(f) { flags.refresh.push(f); },
    };
    const dlg = makeDialog({
        frm: frm,
        child_doc: row,
        glass_controls: [{ rep: "KINH_1", display_code: "GM-02" }],
        applied_sig: pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]),
    });
    dlg.dialog = { hide() { dlg.hidden += 1; }, get_value: () => "BOM-0001" };
    dlg._preview_container = () => $();
    const order = [];
    const sync = withSyncSpy(() => {
        order.push("sync");
        return Promise.resolve("QTN-ITEM-0001");
    });
    dlg._exec_calculate_bom = function () {
        order.push("preview");
        // Server tính lại xong (bất đồng bộ) → rate đã theo mã kính đang chọn.
        setTimeout(() => {
            dlg._glass_applied_signature = dlg._glass_current_signature();
            dlg._finish_preview_waiters();
        }, 0);
    };
    let action;
    try {
        action = dlg._on_primary_action();
        eq(dlg.hidden, 0, "preview chưa xong ⇒ CHƯA đóng dialog");
        await flush();
        eq(order, ["preview"], "phase 1: preview nhận params, ⛔ không còn bước ghi DB");
        await action;
        await flush();
    } finally { sync.restore(); }
    eq(sync.calls.length, 0, "⛔ KHÔNG lần nào gọi _sync_row_to_db");
    eq(flags.dirty, 1, "vẫn đánh dấu phiếu có thay đổi");
    eq(dlg.hidden, 1, "tính giá xong mới đóng");
});

checkAsync("(5e) `_run_preview(manual, skipSync=true)` → KHÔNG ghi DB lại lần 2", async () => {
    const dlg = makeDialog();
    dlg.dialog = { get_value: () => "BOM-0001" };
    dlg._preview_container = () => $();
    dlg.exec = 0;
    dlg._exec_calculate_bom = function () { dlg.exec += 1; };
    const spy = withSyncSpy();
    try {
        dlg._run_preview(false, true);
        await flush();
    } finally { spy.restore(); }
    eq(spy.calls.length, 0, "dòng đã ghi DB trước đó ⇒ ⛔ không ghi lại");
    eq(dlg.exec, 1, "vẫn phải gọi engine tính giá");
});

checkAsync("(5f) `_run_preview` thường (Preview tính giá) → ⛔ KHÔNG ghi DB trước khi gọi server", async () => {
    const dlg = makeDialog();
    dlg.dialog = { get_value: () => "BOM-0001" };
    dlg._preview_container = () => $();
    const order = [];
    const spy = withSyncSpy(() => {
        order.push("db");
        return Promise.resolve("QTN-ITEM-0001");
    });
    dlg._exec_calculate_bom = function () { order.push("engine"); };
    try {
        dlg._run_preview(true);
        await flush();
    } finally { spy.restore(); }
    eq(order, ["engine"], "phase 1: engine nhận tham số từ params ⇒ ⛔ không ghi DB trước");
    eq(spy.calls.length, 0, "_sync_row_to_db không được gọi");
});

// ═════════════════════════════════════════════════════════════════════════
// (6) 💾 Lưu phải ghi ĐỦ 5 field xuống dòng Quotation Item — nguồn DIALOG
//     Lỗi Owner báo 2026-11-21: đổi BOM Version trong dialog, bấm 💾 Lưu,
//     dòng Quotation Item vẫn giữ giá trị cũ. Nguyên nhân: `_save` chỉ đọc
//     `dialog.get_value` rồi BỎ QUA khi rỗng, còn `_apply_row_to_form` chép
//     `child_doc` cũ đè lên dòng lưới.
// ═════════════════════════════════════════════════════════════════════════

function withSetValueSpy() {
    const old = global.frappe.model;
    const calls = [];
    global.frappe.model = {
        set_value(cdt, cdn, field, value) { calls.push([cdt, cdn, field, value]); },
    };
    return {
        calls: calls,
        restore() {
            if (old === undefined) delete global.frappe.model;
            else global.frappe.model = old;
        },
    };
}

function withAlertSpy() {
    const old = global.frappe.show_alert;
    const alerts = [];
    global.frappe.show_alert = (o, secs) => {
        alerts.push({ message: o && o.message, indicator: o && o.indicator, secs: secs });
    };
    return {
        alerts: alerts,
        restore() {
            if (old === undefined) delete global.frappe.show_alert;
            else global.frappe.show_alert = old;
        },
    };
}

// Như `withAlertSpy` nhưng ghi thêm "alert" vào `order` — để kiểm THỨ TỰ
// toast so với `dialog.hide()` (deal của UX1: toast phải SAU khi dialog đóng).
function withOrderedAlertSpy(order) {
    const old = global.frappe.show_alert;
    const alerts = [];
    global.frappe.show_alert = (o, secs) => {
        order.push("alert");
        alerts.push({ message: o && o.message, indicator: o && o.indicator, secs: secs });
    };
    return {
        alerts: alerts,
        restore() {
            if (old === undefined) delete global.frappe.show_alert;
            else global.frappe.show_alert = old;
        },
    };
}

// PHASE 1 "Preview không ghi DB" (Owner chốt 2026-11-21): MỌI đường lưu của
// dialog chỉ ghi dòng TRÊN FORM — kể cả đường phải tính lại giá và dòng mới
// (⛔ không còn `_sync_row_to_db`/`frm.save()` ngầm) ⇒ chỉ còn 2 câu.
const MSG_APPLIED_EXISTING =
    "Đã áp dụng tham số vào dòng này — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá để lưu.";
const MSG_APPLIED_NEW =
    "Đã thêm dòng vào phiếu — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá để lưu.";

// Dialog giả ĐỦ cho `_save()` THẬT: `fields_dict.extra_vars` (bảng biến phụ)
// + `get_value` theo bảng giá trị truyền vào.
function makeSaveDialog(opts) {
    opts = opts || {};
    const D = quotation.quotation.ItemParamDialog.prototype;
    const row = opts.row || { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const frm = opts.frm || { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const dlg = Object.create(D);
    dlg.frm = frm;
    dlg.child_doc = opts.child_doc || row;
    dlg.dialog = opts.dialog || { fields_dict: { extra_vars: { df: { data: [] } } } };
    dlg._var_controls = [];
    dlg._color_controls = [];
    dlg._glass_controls = [];
    dlg._bom_meta = opts.bom_meta || null;
    dlg._preview_inflight = false;
    dlg._preview_waiters = [];
    dlg._preview_seq = 0;
    return dlg;
}

check("(6a) 💾 Lưu đổi BOM Version → set_value + dòng trong frm.doc.items mang mã MỚI", () => {
    const row = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-0001", al_bom_version: "V1",
    };
    const values = { al_bom: "BOM-0001", al_bom_version: "V2" };
    const dlg = makeSaveDialog({
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            get_value: (fn) => values[fn],
        },
    });
    const setv = withSetValueSpy();
    const getDoc = withGetDocSpy(() => row);
    try { dlg._save({}); } finally { setv.restore(); getDoc.restore(); }
    const hit = setv.calls.find((c) => c[2] === "al_bom_version");
    assert(!!hit, "phải gọi frappe.model.set_value cho al_bom_version");
    eq(hit, ["Quotation Item", "QTN-ITEM-0001", "al_bom_version", "V2"]);
    eq(row.al_bom_version, "V2", "dòng trên phiếu phải mang mã MỚI");
});

check("(6b) dialog trả RỖNG cho al_bom_version mà dòng đang có giá trị → ⛔ KHÔNG xoá", () => {
    const row = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-0001", al_bom_version: "V1",
    };
    const dlg = makeSaveDialog({
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            get_value: (fn) => (fn === "al_bom" ? "BOM-0001" : ""),
        },
    });
    const setv = withSetValueSpy();
    const getDoc = withGetDocSpy(() => row);
    try { dlg._save({}); } finally { setv.restore(); getDoc.restore(); }
    eq(row.al_bom_version, "V1", "dialog rỗng ≠ người dùng xoá ⇒ giữ giá trị cũ");
    assert(!setv.calls.some((c) => c[2] === "al_bom_version" && c[3] === ""),
        "⛔ không được ghi rỗng đè giá trị đang có");
});

check("(6c) dialog KHÔNG có get_value → đọc fields_dict[fn].get_value()", () => {
    const row = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-0001", al_bom_version: "V1",
    };
    const dlg = makeSaveDialog({
        row: row,
        dialog: {
            fields_dict: {
                extra_vars: { df: { data: [] } },
                al_bom: { get_value: () => "BOM-0001" },
                al_bom_version: { get_value: () => "V7" },
            },
        },
    });
    const setv = withSetValueSpy();
    const getDoc = withGetDocSpy(() => row);
    try { dlg._save({}); } finally { setv.restore(); getDoc.restore(); }
    assert(setv.calls.some((c) => c[2] === "al_bom_version" && c[3] === "V7"),
        "phải ghi mã đọc từ fields_dict");
    eq(row.al_bom_version, "V7", "dòng nhận mã từ fields_dict");
});

check("(6d) get_value NÉM LỖI (field lạ) → vẫn đọc được fields_dict", () => {
    const row = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-0001", al_bom_version: "V1",
    };
    const dlg = makeSaveDialog({
        row: row,
        dialog: {
            fields_dict: {
                extra_vars: { df: { data: [] } },
                al_bom_version: { get_value: () => "V8" },
            },
            get_value() { throw new TypeError("fieldname lạ"); },
        },
    });
    const setv = withSetValueSpy();
    const getDoc = withGetDocSpy(() => row);
    try { dlg._save({}); } finally { setv.restore(); getDoc.restore(); }
    eq(row.al_bom_version, "V8", "lỗi get_value ⛔ không được làm mất giá trị vừa đổi");
});

check("(6e) `_save()` CHỈ ghi, ⛔ KHÔNG tự báo — trả thông tin dòng cho bên gọi", () => {
    const dlg = makeSaveDialog({});
    const setv = withSetValueSpy();
    const alerts = withAlertSpy();
    let info = null;
    try { info = dlg._save({ notify: true }); } finally { setv.restore(); alerts.restore(); }
    eq(alerts.alerts.length, 0,
        "toast phải bắn SAU dialog.hide() ở `_on_primary_action`, ⛔ trong _save()");
    eq(info.row_name, "QTN-ITEM-0001");
    eq(info.is_new, false);
    // PHASE 1: `_run_preview` gửi `vars_json` trong `params` của preview_bom
    // (engine ⛔ đọc `al_bom_vars` từ DB nữa) ⇒ `_save()` phải trả chuỗi này.
    eq(JSON.parse(info.vars_json).extra_vars, {},
        "vars_json = al_bom_vars vừa thu thập trong dialog");
});

check("(6f) `_save()` dòng MỚI (new-…) → trả is_new = true, vẫn ⛔ không báo", () => {
    const row = { name: "new-quotation-item-3", idx: 2, doctype: "Quotation Item" };
    const dlg = makeSaveDialog({ row: row });
    const setv = withSetValueSpy();
    const alerts = withAlertSpy();
    const getDoc = withGetDocSpy(() => row);
    let info = null;
    try { info = dlg._save({ notify: true }); } finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(alerts.alerts.length, 0, "báo là việc của `_on_primary_action`, sau khi đóng dialog");
    eq(info.row_name, "new-quotation-item-3");
    eq(info.is_new, true);
    eq(JSON.parse(info.vars_json).extra_vars, {},
        "dòng mới cũng trả vars_json để preview gửi kèm params");
});

check("(6g) đường KHÔNG phải nút Lưu (auto-preview) → ⛔ KHÔNG báo động", () => {
    const dlg = makeSaveDialog({});
    const setv = withSetValueSpy();
    const alerts = withAlertSpy();
    try { dlg._save(); } finally { setv.restore(); alerts.restore(); }
    eq(alerts.alerts.length, 0, "auto-preview đổi tham số liên tục ⇒ không được spam thông báo");
});

check("(6h) sau khi Lưu, phiếu có __unsaved = 1 (nút Lưu phiếu bật)", () => {
    const row = { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const dlg = makeSaveDialog({ frm: frm, row: row });
    const setv = withSetValueSpy();
    const getDoc = withGetDocSpy(() => row);
    try { dlg._save({}); } finally { setv.restore(); getDoc.restore(); }
    eq(frm.doc.__unsaved, 1, "thiếu cờ này thì nút Lưu phiếu không bật");
});

check("(6i) có BOM + `_bom_meta` → item_code/item_name lấy từ mã sản phẩm của BOM (A8)", () => {
    const row = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-0001", item_code: "", item_name: "",
    };
    const values = { al_bom: "BOM-0001" };
    const dlg = makeSaveDialog({
        row: row,
        bom_meta: { item_code: "SP-01", item_name: "Cửa nhôm 1 cánh" },
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            get_value: (fn) => values[fn],
        },
    });
    const setv = withSetValueSpy();
    const getDoc = withGetDocSpy(() => row);
    try { dlg._save({}); } finally { setv.restore(); getDoc.restore(); }
    assert(setv.calls.some((c) => c[2] === "item_code" && c[3] === "SP-01"), "item_code từ BOM");
    assert(setv.calls.some((c) => c[2] === "item_name" && c[3] === "Cửa nhôm 1 cánh"), "item_name từ BOM");
    eq(row.item_code, "SP-01");
    eq(row.item_name, "Cửa nhôm 1 cánh");
});

checkAsync("(6j) END-TO-END: bấm 💾 Lưu sau khi đổi BOM Version → dòng đổi + báo + đóng", async () => {
    const row = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-0001", al_bom_version: "V1",
    };
    const values = { al_bom: "BOM-0001", al_bom_version: "V3" };
    const flags = { dirty: 0, refresh: [] };
    const frm = {
        doc: { items: [row] },
        dirty() { flags.dirty += 1; },
        refresh_field(f) { flags.refresh.push(f); },
    };
    let hidden = 0;
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            get_value: (fn) => values[fn],
            hide() { hidden += 1; },
        },
    });
    const setv = withSetValueSpy();
    const alerts = withAlertSpy();
    const getDoc = withGetDocSpy(() => row);
    try { await dlg._on_primary_action(); } finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(row.al_bom_version, "V3", "đây là lỗi Owner báo: dòng phải mang mã mới");
    assert(setv.calls.some((c) => c[2] === "al_bom_version" && c[3] === "V3"),
        "phải đi qua API chuẩn frappe.model.set_value");
    eq(alerts.alerts.length, 1, "người dùng phải thấy phản hồi sau khi bấm Lưu");
    eq(alerts.alerts[0].message, MSG_APPLIED_EXISTING);
    eq(alerts.alerts[0].indicator, "blue", "xanh dương = chưa ghi DB (xanh lá = đã xong thật)");
    eq(flags.dirty, 1, "đánh dấu phiếu có thay đổi");
    eq(flags.refresh, ["items"], "vẽ lại lưới items");
    eq(frm.doc.__unsaved, 1);
    eq(hidden, 1, "không cần tính lại giá ⇒ đóng ngay");
});

// ═════════════════════════════════════════════════════════════════════════
// (8) THỨ TỰ toast của nút 💾 Lưu (UX1 gate 2026-11-21, 4 điểm 🟡)
//     Toast cũ bắn TRONG `_save()` ⇒ bị modal che; nhánh chờ preview (tới
//     20s) thì toast 5s hết hạn trước khi người dùng đọc. Nay `_save()` chỉ
//     ghi + trả thông tin; `_on_primary_action` báo SAU `dialog.hide()`.
//     Màu "blue" (⛔ không "green"): dòng mới chỉ nằm trên form, DB CHƯA ghi.
// ═════════════════════════════════════════════════════════════════════════

checkAsync("(8a) 💾 Lưu nhánh đóng NGAY → toast bắn SAU dialog.hide(), màu blue, câu mới", async () => {
    const row = { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const order = [];
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            hide() { order.push("hide"); },
        },
    });
    const setv = withSetValueSpy();
    const alerts = withOrderedAlertSpy(order);
    const getDoc = withGetDocSpy(() => row);
    try {
        await dlg._on_primary_action();
        await flush();
    } finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(order, ["hide", "alert"], "toast phải bắn SAU khi dialog đóng (modal che mất toast)");
    eq(alerts.alerts.length, 1, "đúng 1 thông báo");
    eq(alerts.alerts[0].message, MSG_APPLIED_EXISTING);
    eq(alerts.alerts[0].indicator, "blue");
    eq(alerts.alerts[0].secs, 7);
});

checkAsync("(8b) 💾 Lưu nhánh CHỜ preview → ⛔ không toast trước, chỉ báo sau khi dialog đóng", async () => {
    const row = { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const order = [];
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            hide() { order.push("hide"); },
        },
    });
    // Kính đang chọn KHÁC bản đã tính ⇒ bắt buộc chờ preview.
    dlg._glass_controls = [
        { rep: "KINH_1", code: "GM-02", ctrl: { get_value: () => "GM-02" } },
    ];
    dlg._glass_applied_signature = pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]);
    let finishPreview = null;
    dlg._preview_and_wait = () => new Promise((resolve) => { finishPreview = resolve; });
    const setv = withSetValueSpy();
    const alerts = withOrderedAlertSpy(order);
    const getDoc = withGetDocSpy(() => row);
    try {
        const action = dlg._on_primary_action();
        await flush();
        eq(alerts.alerts.length, 0, "preview CHƯA xong ⇒ ⛔ chưa được báo (toast sẽ hết hạn)");
        eq(order, [], "dialog còn mở ⇒ chưa đóng, chưa báo");
        // Server tính xong: rate đã theo mã kính đang chọn.
        dlg._glass_applied_signature = dlg._glass_current_signature();
        finishPreview();
        await action;
        await flush();
    } finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(order, ["hide", "alert"], "preview xong → đóng dialog RỒI mới báo");
    eq(alerts.alerts.length, 1);
    // Đường này BẮT BUỘC sync dòng xuống DB để engine tính lại giá ⇒ câu
    // "chưa ghi vào hệ thống" là SAI (yêu cầu Owner 2026-11-21).
    eq(alerts.alerts[0].message, MSG_APPLIED_EXISTING);
    eq(alerts.alerts[0].indicator, "blue");
});

checkAsync("(8c) preview THẤT BẠI → CHỈ toast cam lỗi, ⛔ không toast xanh/dương 'đã áp dụng'", async () => {
    const row = { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const order = [];
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            hide() { order.push("hide"); },
        },
    });
    dlg._glass_controls = [
        { rep: "KINH_1", code: "GM-02", ctrl: { get_value: () => "GM-02" } },
    ];
    dlg._glass_applied_signature = pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]);
    let finishPreview = null;
    dlg._preview_and_wait = () => new Promise((resolve) => { finishPreview = resolve; });
    const setv = withSetValueSpy();
    const alerts = withOrderedAlertSpy(order);
    const getDoc = withGetDocSpy(() => row);
    try {
        const action = dlg._on_primary_action();
        await flush();
        // Preview kết thúc nhưng rate vẫn của mã CŨ ⇒ `_needs_glass_recalc()` true.
        finishPreview();
        await action;
        await flush();
    } finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(order, ["hide", "alert"], "đóng dialog rồi mới báo trạng thái lỗi");
    eq(alerts.alerts.length, 1, "CHỈ 1 thông báo — lỗi, ⛔ không thêm 'đã áp dụng'");
    eq(alerts.alerts[0].indicator, "orange");
    eq(alerts.alerts[0].message, pick.RECALC_FAILED_MESSAGE);
    assert(!alerts.alerts.some((a) => a.indicator === "blue" || a.indicator === "green"),
        "⛔ không báo xanh/dương khi giá kính chưa tính lại được");
});

check("(8d) `_save({ notify: false })` (auto-preview) → ⛔ KHÔNG toast nào", () => {
    const dlg = makeSaveDialog({});
    const setv = withSetValueSpy();
    const alerts = withAlertSpy();
    try { dlg._save({ notify: false }); } finally { setv.restore(); alerts.restore(); }
    eq(alerts.alerts.length, 0, "auto-preview đổi tham số liên tục ⇒ phải im lặng");
});

checkAsync("(8e) 💾 Lưu dòng MỚI → câu 'Đã thêm dòng…', màu blue, sau hide", async () => {
    const row = { name: "new-quotation-item-3", idx: 2, doctype: "Quotation Item" };
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const order = [];
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            hide() { order.push("hide"); },
        },
    });
    const setv = withSetValueSpy();
    const alerts = withOrderedAlertSpy(order);
    const getDoc = withGetDocSpy(() => row);
    try {
        await dlg._on_primary_action();
        await flush();
    } finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(order, ["hide", "alert"]);
    eq(alerts.alerts.length, 1);
    eq(alerts.alerts[0].message, MSG_APPLIED_NEW);
    eq(alerts.alerts[0].indicator, "blue");
});

// ═════════════════════════════════════════════════════════════════════════
// (7) Mở LẠI dialog phải đọc từ dòng trong `frm.doc.items` — ⛔ không phải
//     bản sao `locals`. Lỗi Owner báo 2026-11-21: Lưu xong (lưới đã hiện giá
//     trị mới), mở lại dialog vẫn thấy giá trị CŨ.
//     Đường lỗi: nút trong form con của dòng mở dialog bằng
//     `frappe.get_doc("Quotation Item", cdn)` — bản trong `locals`, có thể
//     KHÁC object dòng nằm trong `frm.doc.items` mà lần Lưu trước đã ghi.
// ═════════════════════════════════════════════════════════════════════════

// Dialog dựng thật nhưng chặn phần vẽ UI: chỉ ghi lại danh sách field để
// kiểm `default` (đúng thứ tự mà `show()` chạy trước khi render).
function makeShowDialog(opts) {
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    dlg.frm = opts.frm;
    dlg.child_doc = opts.child_doc;
    dlg._fields = null;
    dlg._render_dialog = function () { dlg._fields = dlg._build_dialog_fields(); };
    return dlg;
}

function fieldDefault(fields, fieldname) {
    const f = (fields || []).find((x) => x.fieldname === fieldname);
    return f ? f.default : undefined;
}

// `frappe.model.set_value` có GHI THẬT vào bản trong `locals` (như trình
// duyệt), đồng thời đếm số lượt gọi — để kiểm "mỗi object ghi 1 lần".
function withSetValueRecorder(target) {
    const old = global.frappe.model;
    const calls = [];
    global.frappe.model = {
        set_value(cdt, cdn, field, value) {
            calls.push([cdt, cdn, field, value]);
            if (target) target[field] = value;
        },
    };
    return {
        calls: calls,
        restore() {
            if (old === undefined) delete global.frappe.model;
            else global.frappe.model = old;
        },
    };
}

const STALE_ROW = {
    name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
    al_bom: "BOM-OLD", al_bom_version: "V-OLD",
    al_bom_vars: '{"KINH_1":"GM-OLD"}',
};

check("(7a) mở lại bằng bản sao `locals` (CŨ) → dùng dòng frm.doc.items (MỚI)", () => {
    const gridRow = {
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        al_bom: "BOM-NEW", al_bom_version: "V-NEW",
        al_bom_vars: '{"KINH_1":"GM-NEW"}',
    };
    const staleCopy = Object.assign({}, STALE_ROW);
    const dlg = makeShowDialog({ frm: { doc: { items: [gridRow] } }, child_doc: staleCopy });
    dlg.show();
    assert(dlg.child_doc === gridRow,
        "child_doc phải trỏ ĐÚNG object dòng trong frm.doc.items");
    eq(fieldDefault(dlg._fields, "al_bom"), "BOM-NEW", "default BOM phải là giá trị MỚI");
    eq(fieldDefault(dlg._fields, "al_bom_version"), "V-NEW", "default BOM Version phải là giá trị MỚI");
    eq(dlg._parse_existing(), { KINH_1: "GM-NEW" }, "biến đọc từ al_bom_vars phải là bản MỚI");
});

check("(7b) mở ngoài ngữ cảnh phiếu (không có frm.doc.items) → giữ child_doc, không ném lỗi", () => {
    const cases = [
        { label: "frm.doc rỗng", frm: { doc: {} } },
        { label: "không có frm", frm: undefined },
        // Có items nhưng KHÔNG chứa dòng của dialog (mở từ ngữ cảnh khác).
        { label: "items không chứa dòng", frm: { doc: { items: [{ name: "QTN-ITEM-9999", idx: 9 }] } } },
    ];
    cases.forEach((c) => {
        const doc = Object.assign({}, STALE_ROW);
        const dlg = makeShowDialog({ frm: c.frm, child_doc: doc });
        dlg.show();  // ⛔ không được ném
        assert(dlg.child_doc === doc, c.label + ": phải giữ nguyên child_doc");
        eq(fieldDefault(dlg._fields, "al_bom_version"), "V-OLD", c.label + ": default giữ giá trị cũ");
    });
});

check("(7c) 3 object KHÁC nhau → cả 3 nhận giá trị, mỗi object ghi đúng 1 lần", () => {
    const tLocals = makeCountedRow({
        name: "QTN-ITEM-0001", doctype: "Quotation Item", al_bom_version: "V-OLD",
    });
    const tForm = makeCountedRow({
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item", al_bom_version: "V-OLD",
    });
    const tDialog = makeCountedRow({
        name: "QTN-ITEM-0001", doctype: "Quotation Item", al_bom_version: "V-OLD",
    });
    const dlg = makeShowDialog({
        frm: { doc: { items: [tForm.row] } },
        child_doc: tDialog.row,
    });
    const setv = withSetValueRecorder(tLocals.row);
    const getDoc = withGetDocSpy(() => tLocals.row);
    let wrote;
    try {
        wrote = dlg._write_row_field("Quotation Item", "QTN-ITEM-0001", "al_bom_version", "V-NEW");
    } finally { setv.restore(); getDoc.restore(); }
    eq(wrote, true, "có thay đổi ⇒ trả true");
    eq(tLocals.row.al_bom_version, "V-NEW", "bản trong locals (nguồn mở lại dialog) phải mới");
    eq(tForm.row.al_bom_version, "V-NEW", "dòng trong frm.doc.items phải mới");
    eq(tDialog.row.al_bom_version, "V-NEW", "object dialog đang giữ phải mới");
    eq(setv.calls, [["Quotation Item", "QTN-ITEM-0001", "al_bom_version", "V-NEW"]],
        "chỉ đi qua API chuẩn 1 lần cho bản trong locals");
    eq(tLocals.writes.al_bom_version, 1, "locals ghi 1 lần");
    eq(tForm.writes.al_bom_version, 1, "dòng lưới ghi 1 lần");
    eq(tDialog.writes.al_bom_version, 1, "object dialog ghi 1 lần");
});

check("(7d) ba đường TRÙNG MỘT object → ⛔ không ghi lặp", () => {
    const t = makeCountedRow({
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item", al_bom_version: "V-OLD",
    });
    const row = t.row;
    const dlg = makeShowDialog({ frm: { doc: { items: [row] } }, child_doc: row });
    const setv = withSetValueRecorder(row);
    const getDoc = withGetDocSpy(() => row);
    let wrote;
    try {
        wrote = dlg._write_row_field("Quotation Item", "QTN-ITEM-0001", "al_bom_version", "V-NEW");
        eq(t.writes.al_bom_version, 1, "một object ⇒ ghi đúng 1 lần (set_value)");
        eq(row.al_bom_version, "V-NEW");
        // Gọi lại với ĐÚNG giá trị đang có → ⛔ không bắn change handler vô ích.
        const again = dlg._write_row_field("Quotation Item", "QTN-ITEM-0001", "al_bom_version", "V-NEW");
        eq(again, false, "giá trị KHÔNG đổi ⇒ trả false");
        eq(t.writes.al_bom_version, 1, "⛔ không ghi lại khi giá trị không đổi");
        eq(setv.calls.length, 1, "⛔ không gọi set_value lần 2");
    } finally { setv.restore(); getDoc.restore(); }
    eq(wrote, true, "lượt đầu có thay đổi ⇒ trả true");
});

// ═════════════════════════════════════════════════════════════════════════
// (9) KẾT QUẢ TÍNH GIÁ PHẢI XUỐNG DÒNG Quotation Item
//     Lỗi Owner báo 2026-11-21 (lớp nặng nhất): máy chủ ghi kết quả thẳng vào
//     DB, nhưng client chỉ cập nhật `child_doc` + bản `locals` ⇒ dòng trong
//     `frm.doc.items` vẫn mang giá trị CŨ/rỗng. Bấm Lưu báo giá → Frappe gửi
//     nguyên doc → GHI ĐÈ kết quả vừa tính. (9b) là ca then chốt của cả bộ.
// ═════════════════════════════════════════════════════════════════════════
const RESULT_FIELDS = ["al_bom_result", "al_gia_ban", "al_gia_vat",
    "al_calc_status", "al_calc_error", "al_calc_job_id", "rate"];

const RESULT_NEW = {
    buckets: { VL_KINH: 1000000 },
    cost_template: { GIA_BAN: 2000000, GIA_VAT: 2200000 },
    lines: [{ slug: "kinh_tren", line_total: 1000000 }],
    errors: {},
};

// Giá trị CŨ/rỗng trên dòng trước khi tính — dùng số KHÁC HẲN kết quả mới để
// ca "chống ghi đè" không thể xanh giả.
const ROW_STALE = {
    al_bom_result: '{"lines":[],"old":true}',
    al_gia_ban: 1111,
    al_gia_vat: 2222,
    al_calc_status: "Failed",
    al_calc_error: "lỗi cũ",
    al_calc_job_id: "JOB-CU",
    rate: 1111,
};

// Như `makeCountedRow` nhưng theo DANH SÁCH field truyền vào (bộ kết quả).
function makeCountedRowWith(fields, base) {
    const row = Object.assign({}, base);
    const writes = {};
    fields.forEach((f) => {
        let val = row[f];
        delete row[f];
        Object.defineProperty(row, f, {
            enumerable: true,
            configurable: true,
            get() { return val; },
            set(v) { val = v; writes[f] = (writes[f] || 0) + 1; },
        });
    });
    return { row: row, writes: writes };
}

// `frappe.call` spy — ghi lại mọi lời gọi; `impl(opts)` tuỳ chọn để trả kết quả.
function withCallSpy(impl) {
    const old = global.frappe.call;
    const calls = [];
    global.frappe.call = function (opts) {
        calls.push(opts);
        if (impl) return impl(opts);
        return undefined;
    };
    return { calls: calls, restore() { global.frappe.call = old; } };
}

// Container giả "có nội dung" — `$()` của harness có length 0 nên code nghiệp
// vụ coi là "dialog đã đóng" và bỏ qua phần ghi dòng.
function fakeContainer() {
    return { length: 1, html() { return this; }, prepend() { return this; }, find() { return { length: 0 }; } };
}

// Dialog giả đủ cho `_exec_calculate_bom` / `_listen_realtime`.
function makePreviewDialog(opts) {
    opts = opts || {};
    const D = quotation.quotation.ItemParamDialog.prototype;
    const dlg = Object.create(D);
    dlg.frm = opts.frm;
    dlg.child_doc = opts.child_doc;
    dlg.dialog = {};
    dlg._dialog_open = false;
    dlg._glass_controls = [];
    dlg._color_controls = [];
    dlg._var_controls = [];
    dlg._preview_seq = 1;
    dlg._preview_waiters = [];
    dlg._preview_inflight = false;
    dlg._last_result = null;
    dlg._render_display_model = () => {};
    dlg._finish_preview_with_glass = () => true;
    return dlg;
}

const FORM_ROW_CTX = () => ({
    name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
});

check("(9a) preview đồng bộ xong → dòng trong frm.doc.items mang ĐỦ kết quả", () => {
    const tLocals = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const tForm = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const tDialog = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const frm = { doc: { items: [tForm.row] } };
    const dlg = makePreviewDialog({ frm: frm, child_doc: tDialog.row });
    const setv = withSetValueRecorder(tLocals.row);
    const getDoc = withGetDocSpy(() => tLocals.row);
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    try {
        dlg._exec_calculate_bom(fakeContainer(), 1, false, null);
    } finally { setv.restore(); getDoc.restore(); call.restore(); }

    eq(tForm.row.al_bom_result, JSON.stringify(RESULT_NEW),
        "dòng lưới phải mang ĐÚNG JSON response (thiếu là Lưu báo giá xoá kết quả)");
    eq(tForm.row.al_gia_ban, 2000000, "al_gia_ban = GIA_BAN (giá trước VAT)");
    eq(tForm.row.al_gia_vat, 2200000, "al_gia_vat = GIA_VAT của kết quả");
    eq(tForm.row.al_calc_status, "Success");
    eq(tForm.row.al_calc_error, "", "xong thành công ⇒ xoá lỗi cũ của dòng");
    eq(tForm.row.al_calc_job_id, "", "đường đồng bộ không còn job nền");
    eq(tForm.row.rate, 2000000, "rate = giá trước VAT (cùng giá trị máy chủ ghi)");
    // Cả 3 object (locals / dòng lưới / object dialog) đều nhận giá trị
    RESULT_FIELDS.forEach((f) => {
        eq(tLocals.row[f], tForm.row[f], "bản locals phải khớp dòng lưới: " + f);
        eq(tDialog.row[f], tForm.row[f], "object dialog phải khớp dòng lưới: " + f);
    });
    eq(dlg._last_result, RESULT_NEW, "giữ kết quả để nút 💾 Lưu ghi lại mà không tính lại");
});

check("(9a2) ưu tiên giá MÁY CHỦ đã tính (gia_vat/gia_ban) hơn GIA_BAN của cost template", () => {
    // `b7_save_results` ghi al_gia_vat = _resolve_final_price() (tôn trọng cờ
    // is_final_price) — có thể KHÁC dòng GIA_VAT của snapshot ⇒ client phải
    // dùng giá trị máy chủ trả, ⛔ không tự suy từ GIA_VAT/GIA_BAN.
    const result = {
        buckets: {},
        cost_template: { GIA_BAN: 2000000, GIA_VAT: 2200000 },
        lines: [],
        errors: {},
        gia_ban: 1900000,
        gia_vat: 2090000,
    };
    const row = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const dlg = makePreviewDialog({ frm: { doc: { items: [row] } }, child_doc: row });
    const setv = withSetValueRecorder(row);
    const getDoc = withGetDocSpy(() => row);
    const call = withCallSpy((o) => o.callback({ message: result }));
    try { dlg._exec_calculate_bom(fakeContainer(), 1, false, null); }
    finally { setv.restore(); getDoc.restore(); call.restore(); }
    eq(row.al_gia_ban, 1900000, "ưu tiên result.gia_ban");
    eq(row.al_gia_vat, 2090000, "ưu tiên result.gia_vat (⛔ không suy GIA_BAN × thuế)");
    eq(row.rate, 1900000, "rate theo giá trước VAT máy chủ đã tính");
});

check("(9b) CHỐNG GHI ĐÈ: Lưu báo giá sau preview gửi lên kết quả MỚI, ⛔ không phải cũ", () => {
    const tForm = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const localsRow = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const dlgRow = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const frm = { doc: { items: [tForm.row] } };
    const dlg = makePreviewDialog({ frm: frm, child_doc: dlgRow });
    const setv = withSetValueRecorder(localsRow);
    const getDoc = withGetDocSpy(() => localsRow);
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    try {
        dlg._exec_calculate_bom(fakeContainer(), 1, false, null);
    } finally { setv.restore(); getDoc.restore(); call.restore(); }

    // Mô phỏng `frm.save()`: Frappe gửi NGUYÊN `frm.doc` (đọc `frm.doc.items`).
    const payload = JSON.parse(JSON.stringify({ doctype: "Quotation", items: frm.doc.items }));
    const sent = payload.items[0];
    eq(sent.al_gia_ban, 2000000,
        "payload gửi lên phải mang giá MỚI — không thì server ghi đè kết quả vừa tính");
    eq(sent.al_gia_vat, 2200000);
    eq(sent.al_bom_result, JSON.stringify(RESULT_NEW),
        "payload mang JSON kết quả mới (⛔ không phải chuỗi cũ/rỗng)");
    eq(sent.rate, 2000000);
    assert(sent.al_gia_ban !== ROW_STALE.al_gia_ban && sent.al_gia_vat !== ROW_STALE.al_gia_vat,
        "giá trị cũ trên dòng đã bị thay bằng kết quả mới");
    eq(sent.al_calc_status, "Success");
});

check("(9c) realtime job nền Success → dòng nhận kết quả như (9a)", () => {
    const tForm = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const localsRow = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const dlgRow = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const dlg = makePreviewDialog({ frm: { doc: { items: [tForm.row] } }, child_doc: dlgRow });

    let handler = null;
    const oldRealtime = global.frappe.realtime;
    global.frappe.realtime = { on(ev, fn) { handler = fn; }, off() {} };
    const setv = withSetValueRecorder(localsRow);
    const getDoc = withGetDocSpy(() => localsRow);
    const alerts = withAlertSpy();
    try {
        dlg._listen_realtime("JOB-9", fakeContainer(), null);
        assert(handler, "phải đăng ký listener realtime");
        handler({ job_id: "JOB-9", status: "Success", result: RESULT_NEW });
    } finally {
        setv.restore(); getDoc.restore(); alerts.restore();
        global.frappe.realtime = oldRealtime;
    }

    eq(tForm.row.al_bom_result, JSON.stringify(RESULT_NEW), "dòng lưới nhận JSON job nền");
    eq(tForm.row.al_gia_ban, 2000000);
    eq(tForm.row.al_gia_vat, 2200000);
    eq(tForm.row.al_calc_status, "Success");
    eq(tForm.row.al_calc_error, "");
    eq(tForm.row.al_calc_job_id, "JOB-9", "giữ job id vừa xong");
    eq(tForm.row.rate, 2000000);
    eq(localsRow.al_gia_vat, 2200000, "bản locals cũng phải mới");
    eq(dlg._last_result, RESULT_NEW);
});

check("(9d) realtime job nền Failed → dòng có al_calc_status='Failed' + al_calc_error", () => {
    const tForm = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const localsRow = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const dlgRow = Object.assign(FORM_ROW_CTX(), ROW_STALE);
    const dlg = makePreviewDialog({ frm: { doc: { items: [tForm.row] } }, child_doc: dlgRow });

    let handler = null;
    const oldRealtime = global.frappe.realtime;
    global.frappe.realtime = { on(ev, fn) { handler = fn; }, off() {} };
    const setv = withSetValueRecorder(localsRow);
    const getDoc = withGetDocSpy(() => localsRow);
    try {
        dlg._listen_realtime("JOB-9", fakeContainer(), null);
        handler({ job_id: "JOB-9", status: "Failed", error: "BOM thiếu dòng kính" });
    } finally {
        setv.restore(); getDoc.restore();
        global.frappe.realtime = oldRealtime;
    }

    eq(tForm.row.al_calc_status, "Failed", "trạng thái hỏng phải nằm TRÊN DÒNG");
    eq(tForm.row.al_calc_error, "BOM thiếu dòng kính");
    eq(tForm.row.al_calc_job_id, "JOB-9");
    // ⛔ Không xoá kết quả cũ khi job hỏng (không ghi giá trị rỗng lên dòng)
    eq(tForm.row.al_bom_result, ROW_STALE.al_bom_result);
    eq(tForm.row.al_gia_ban, ROW_STALE.al_gia_ban);
    eq(tForm.row.al_gia_vat, ROW_STALE.al_gia_vat);
});

checkAsync("(9e) 💾 Lưu khi đã có `_last_result` → ghi lại đủ bộ, mỗi field 1 lần", async () => {
    const tForm = makeCountedRowWith(RESULT_FIELDS,
        Object.assign(FORM_ROW_CTX(), ROW_STALE));
    const row = tForm.row;
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            hide() {},
        },
    });
    dlg._last_result = RESULT_NEW;
    const setv = withSetValueRecorder(row);
    const getDoc = withGetDocSpy(() => row);
    const alerts = withAlertSpy();
    try {
        await dlg._on_primary_action();
        await flush();
        // Gọi lại: idempotent — ⛔ không ghi thêm lần nào.
        dlg._write_result_to_row(dlg._last_result, {});
    } finally { setv.restore(); alerts.restore(); getDoc.restore(); }

    RESULT_FIELDS.forEach((f) => {
        eq(tForm.writes[f], 1, "field " + f + " chỉ được ghi 1 lần");
    });
    eq(row.al_bom_result, JSON.stringify(RESULT_NEW));
    eq(row.al_gia_ban, 2000000);
    eq(row.al_gia_vat, 2200000);
    eq(row.al_calc_status, "Success");
    eq(row.al_calc_error, "");
    eq(row.al_calc_job_id, "");
    eq(row.rate, 2000000);
});

check("(9f) mở lại dialog → API display nhận ĐÚNG al_bom_result của DÒNG", () => {
    const rowResult = JSON.stringify(RESULT_NEW);
    const row = Object.assign(FORM_ROW_CTX(), {
        al_calc_status: "Success", al_bom_result: rowResult,
    });
    const dlg = makePreviewDialog({ frm: { doc: { items: [row] } }, child_doc: row });
    // Dùng `_render_display_model` THẬT (makePreviewDialog stub nó đi) — ca này
    // kiểm chính lời gọi API của nó.
    dlg._render_display_model = quotation.quotation.ItemParamDialog.prototype._render_display_model;
    dlg._preview_container = () => fakeContainer();
    const call = withCallSpy();
    try { dlg._render_preview_panel(); } finally { call.restore(); }

    eq(call.calls.length, 1, "phải gọi API dựng display");
    eq(call.calls[0].method, "alumglass.api.get_result_display");
    eq(call.calls[0].args.quotation_item_name, "QTN-ITEM-0001");
    eq(call.calls[0].args.result_json, rowResult,
        "phải truyền kết quả CỦA DÒNG (⛔ không để server đọc DB bản cũ)");

    // Dòng rỗng ⇒ giữ NGUYÊN đường cũ: ⛔ không gửi key result_json.
    const call2 = withCallSpy();
    try { dlg._render_display_model(fakeContainer(), "QTN-ITEM-0001", false, ""); }
    finally { call2.restore(); }
    eq(call2.calls.length, 1);
    assert(!("result_json" in call2.calls[0].args),
        "dòng rỗng ⇒ gọi kiểu cũ (server đọc DB)");
    eq(call2.calls[0].args, { quotation_item_name: "QTN-ITEM-0001" });
});

checkAsync("(9g) toast nói ĐÚNG trạng thái thật của từng đường", async () => {
    // (i) Đường BẮT BUỘC tính lại (glass đổi) ⇒ tham số + kết quả ĐÃ xuống DB.
    const build = (rowName) => {
        const row = { name: rowName, idx: 1, doctype: "Quotation Item" };
        const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
        const order = [];
        const dlg = makeSaveDialog({
            frm: frm,
            row: row,
            dialog: {
                fields_dict: { extra_vars: { df: { data: [] } } },
                hide() { order.push("hide"); },
            },
        });
        dlg._glass_controls = [
            { rep: "KINH_1", code: "GM-02", ctrl: { get_value: () => "GM-02" } },
        ];
        dlg._glass_applied_signature = pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]);
        return { row: row, order: order, dlg: dlg };
    };

    // (i) đã có dòng → câu "đã tính lại giá cho dòng này"
    const a = build("QTN-ITEM-0001");
    a.dlg._preview_and_wait = () => new Promise((resolve) => {
        setTimeout(() => {
            a.dlg._glass_applied_signature = a.dlg._glass_current_signature();
            resolve();
        }, 0);
    });
    let setv = withSetValueRecorder(a.row);
    let alerts = withOrderedAlertSpy(a.order);
    let getDoc = withGetDocSpy(() => a.row);
    try { await a.dlg._on_primary_action(); await flush(); }
    finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(a.order, ["hide", "alert"], "toast SAU khi đóng dialog");
    eq(alerts.alerts[0].message, MSG_APPLIED_EXISTING);
    eq(alerts.alerts[0].indicator, "blue");
    eq(alerts.alerts[0].secs, 7);

    // (ii) dòng MỚI + đường tính lại → câu "đã thêm dòng và tính giá"
    const b = build("new-quotation-item-3");
    b.dlg._preview_and_wait = () => new Promise((resolve) => {
        setTimeout(() => {
            b.dlg._glass_applied_signature = b.dlg._glass_current_signature();
            resolve();
        }, 0);
    });
    setv = withSetValueRecorder(b.row);
    alerts = withOrderedAlertSpy(b.order);
    getDoc = withGetDocSpy(() => b.row);
    try { await b.dlg._on_primary_action(); await flush(); }
    finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(alerts.alerts[0].message, MSG_APPLIED_NEW);

    // (iii) KHÔNG có gì phải tính lại ⇒ DB chưa ghi ⇒ câu cũ "chưa ghi vào hệ thống"
    const row = { name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item" };
    const order = [];
    const dlg = makeSaveDialog({
        frm: { doc: { items: [row] }, dirty() {}, refresh_field() {} },
        row: row,
        dialog: {
            fields_dict: { extra_vars: { df: { data: [] } } },
            hide() { order.push("hide"); },
        },
    });
    setv = withSetValueRecorder(row);
    alerts = withOrderedAlertSpy(order);
    getDoc = withGetDocSpy(() => row);
    try { await dlg._on_primary_action(); await flush(); }
    finally { setv.restore(); alerts.restore(); getDoc.restore(); }
    eq(order, ["hide", "alert"]);
    eq(alerts.alerts[0].message, MSG_APPLIED_EXISTING);
    eq(alerts.alerts[0].indicator, "blue");
});

// ═════════════════════════════════════════════════════════════════════════
// (10) "Tính giá" HÀNG LOẠT (form-level) phải ghi kết quả xuống dòng
//      Trước đây đường này đoán giá từ cost template (`GIA_VAT || 0`) và
//      KHÔNG ghi al_bom_result/trạng thái xuống dòng ⇒ dòng lệch DB, Lưu báo
//      giá ghi đè. Nay dùng CHUNG `alumglass.quotation._apply_result_to_row`.
// ═════════════════════════════════════════════════════════════════════════

// Dòng Quotation Item đủ điều kiện tính giá (đã có BOM + tham số), mang giá
// trị CŨ để ca "chống ghi đè" không thể xanh giả.
function makeBulkRow(overrides) {
    const row = Object.assign({
        name: "QTN-ITEM-0001", idx: 1, doctype: "Quotation Item",
        is_new: 0, al_bom: "BOM-0001", al_bom_version: "V1", al_bom_vars: "{}",
        item_code: "SP-01", item_name: "Sản phẩm",
    }, ROW_STALE);
    return Object.assign(row, overrides || {});
}

// Chạy `_calc_all_items` với `frappe.call` spy rồi chờ chuỗi promise chạy xong.
async function runBulkCalc(frm, impl, rowToSync) {
    const sync = withSyncSpy(() => Promise.resolve(
        rowToSync ? { name: rowToSync } : { name: frm.doc.items[0].name }));
    const call = withCallSpy(impl);
    try {
        quotation.quotation._calc_all_items(frm);
        await flush();
        await flush();
    } finally {
        sync.restore();
        call.restore();
    }
}

checkAsync("(10a) bulk sync 1 dòng ⇒ dòng trong frm.doc.items mang ĐỦ bộ 7 field", async () => {
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    await runBulkCalc(frm, (o) => o.callback({ message: RESULT_NEW }));

    eq(row.al_bom_result, JSON.stringify(RESULT_NEW), "thiếu JSON là Lưu báo giá xoá kết quả");
    eq(row.al_gia_ban, 2000000, "al_gia_ban = GIA_BAN (giá trước VAT)");
    eq(row.al_gia_vat, 2200000, "al_gia_vat = GIA_VAT của kết quả");
    eq(row.rate, 2000000, "rate = al_gia_ban (chưa VAT)");
    eq(row.al_calc_status, "Success");
    eq(row.al_calc_error, "", "xong thành công ⇒ xoá lỗi cũ");
    eq(row.al_calc_job_id, "", "đường đồng bộ không còn job nền");
});

checkAsync("(10b) server trả gia_vat = 0 (giá thật bằng 0) ⇒ dòng ghi 0, ⛔ không bị falsy", async () => {
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const result = {
        buckets: {}, lines: [], errors: {},
        cost_template: { GIA_BAN: 2000000, GIA_VAT: 2200000 },
        gia_ban: 1500000,
        gia_vat: 0,
    };
    await runBulkCalc(frm, (o) => o.callback({ message: result }));

    eq(row.al_gia_vat, 0, "0 là giá THẬT — ⛔ không bị `|| 0`/falsy biến thành 2200000");
    eq(row.al_gia_ban, 1500000, "al_gia_ban ưu tiên giá máy chủ đã tính");
    eq(row.rate, 1500000);
});

checkAsync("(10c) response bản cũ (không có gia_vat/gia_ban) ⇒ rơi về cost_template", async () => {
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const result = {
        buckets: {}, lines: [], errors: {},
        cost_template: { GIA_BAN: 3000000, GIA_VAT: 3300000 },
    };
    await runBulkCalc(frm, (o) => o.callback({ message: result }));

    eq(row.al_gia_ban, 3000000, "rơi về ct.GIA_BAN");
    eq(row.al_gia_vat, 3300000, "rơi về ct.GIA_VAT");
    eq(row.rate, 3000000);
});

checkAsync("(10d) bulk async (Queued) ⇒ dòng có trạng thái Queued + job id", async () => {
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    await runBulkCalc(frm, (o) => o.callback({
        message: { async: true, job_id: "JOB-10" },
    }));

    eq(row.al_calc_status, "Queued");
    eq(row.al_calc_job_id, "JOB-10");
    // ⛔ Không xoá kết quả cũ khi chỉ xếp hàng.
    eq(row.al_bom_result, ROW_STALE.al_bom_result);
    eq(row.al_gia_ban, ROW_STALE.al_gia_ban);
});

checkAsync("(10e) bulk lỗi ⇒ Failed + câu người-đọc-được, ⛔ không xoá al_bom_result cũ", async () => {
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    await runBulkCalc(frm, (o) => o.error({ message: "Máy chủ tính giá không phản hồi" }));

    eq(row.al_calc_status, "Failed");
    eq(row.al_calc_error, "Máy chủ tính giá không phản hồi", "chỉ lưu câu người-đọc-được");
    eq(row.al_bom_result, ROW_STALE.al_bom_result, "giữ kết quả cũ, ⛔ không xoá");
    eq(row.al_gia_ban, ROW_STALE.al_gia_ban);
    eq(row.al_gia_vat, ROW_STALE.al_gia_vat);
});

checkAsync("(10f) CHỐNG GHI ĐÈ: Lưu báo giá sau bulk gửi lên kết quả MỚI", async () => {
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    await runBulkCalc(frm, (o) => o.callback({ message: RESULT_NEW }));

    // Mô phỏng `frm.save()`: Frappe gửi NGUYÊN doc → phải mang giá MỚI.
    const payload = JSON.parse(JSON.stringify({ doctype: "Quotation", items: frm.doc.items }));
    const sent = payload.items[0];
    eq(sent.al_gia_ban, 2000000, "payload mang giá mới — không thì server ghi đè");
    eq(sent.al_gia_vat, 2200000);
    eq(sent.al_bom_result, JSON.stringify(RESULT_NEW));
    eq(sent.rate, 2000000);
    eq(sent.al_calc_status, "Success");
    assert(sent.al_gia_ban !== ROW_STALE.al_gia_ban && sent.al_gia_vat !== ROW_STALE.al_gia_vat,
        "giá trị cũ trên dòng đã bị thay bằng kết quả mới");
});

checkAsync("(10g) dialog và bulk gọi CÙNG một hàm ghi kết quả (1 nguồn, ⛔ không 2 bản chép)", async () => {
    const seen = [];
    const orig = quotation.quotation._apply_result_to_row;
    quotation.quotation._apply_result_to_row = function (frm, cdt, cdn, result, opts) {
        seen.push({ frm: frm, cdt: cdt, cdn: cdn, result: result, opts: opts });
        return orig.apply(this, arguments);
    };
    try {
        // (i) dialog
        const drow = makeBulkRow({});
        const dlg = makePreviewDialog({ frm: { doc: { items: [drow] } }, child_doc: drow });
        dlg._write_result_to_row(RESULT_NEW, {});
        eq(seen.length, 1, "dialog phải đi qua hàm dùng chung");
        assert(seen[0].opts && seen[0].opts.child_doc === drow, "lượt dialog truyền child_doc");

        // (ii) bulk
        const brow = makeBulkRow({ name: "QTN-ITEM-0002", idx: 2 });
        const bfrm = { doc: { items: [brow] }, dirty() {}, refresh_field() {} };
        await runBulkCalc(bfrm, (o) => o.callback({ message: RESULT_NEW }));
        const bulkCalls = seen.slice(1);
        assert(bulkCalls.length >= 1, "bulk phải đi qua CÙNG hàm (⛔ không bản chép riêng)");
        assert(bulkCalls.some((c) => c.opts && c.opts.row === brow),
            "lượt bulk truyền đúng dòng của frm.doc.items");
    } finally {
        quotation.quotation._apply_result_to_row = orig;
    }
});

check("(10h) bulk async ⇒ nghe realtime, kết quả tự ghi xuống dòng (⛔ không mất)", () => {
    const row = makeBulkRow();
    const frm = { doc: { name: "SAL-QTN-1", items: [row] }, dirty() {}, refresh_field() {} };
    const handlers = {};
    const old_realtime = global.frappe.realtime;
    global.frappe.realtime = {
        on(event, fn) { handlers[event] = fn; },
        off(event) { if (handlers[event]) delete handlers[event]; },
    };
    const call = withCallSpy((o) => o.callback({
        message: { async: true, job_id: "job-9", message: "đang tính" },
    }));
    const getDoc = withGetDocSpy(() => row);
    const setv = withSetValueRecorder(row);
    try {
        quotation.quotation._calc_all_items(frm);
    } finally { setv.restore(); getDoc.restore(); call.restore(); }
    eq(row.al_calc_status, "Queued", "dòng mang trạng thái Queued trong phiên");

    const handler = handlers["alumglass_bom_calc_done"];
    assert(typeof handler === "function",
        "server ⛔ ghi DB cho preview ⇒ client PHẢI nghe realtime, thiếu là mất kết quả");
    handler({ job_id: "job-9", qi_name: row.name, status: "Success", result: RESULT_NEW });
    eq(row.al_calc_status, "Success");
    eq(row.rate, 2000000, "kết quả nền ghi đúng rate xuống dòng");
    eq(row.al_bom_result, JSON.stringify(RESULT_NEW));

    // Job lạ (của lượt khác) ⇒ bỏ qua, ⛔ ghi bừa vào dòng này.
    row.al_calc_status = "Queued";
    handler({ job_id: "job-other", qi_name: row.name, status: "Success", result: RESULT_NEW });
    eq(row.al_calc_status, "Queued");

    if (old_realtime === undefined) delete global.frappe.realtime;
    else global.frappe.realtime = old_realtime;
});

// ═════════════════════════════════════════════════════════════════════════
// (11) Câu toast nói ĐÚNG đã ghi ở đâu (UX1 PASS-with-🟡 2026-11-21)
// ═════════════════════════════════════════════════════════════════════════
checkAsync("(11a) dòng mới + tính lại giá ⇒ ⛔ KHÔNG frm.save, câu 'Đã thêm dòng… chưa lưu'", async () => {
    const row = {
        name: "new-quotation-item-3", idx: 1, doctype: "Quotation Item",
        __islocal: 1, al_bom: "BOM-0001", al_bom_version: "V1", al_bom_vars: "{}",
        item_code: "SP-01", item_name: "Sản phẩm",
    };
    let saveCalls = 0;
    const order = [];
    const frm = {
        doc: { items: [row] },
        dirty() {}, refresh_field() {},
        save() {
            saveCalls += 1;
            return Promise.resolve();
        },
    };
    const dlg = makeSaveDialog({
        frm: frm,
        row: row,
        dialog: {
            fields_dict: {
                extra_vars: { df: { data: [] } },
                preview_html: { $wrapper: fakeContainer() },
            },
            hide() { order.push("hide"); },
        },
    });
    dlg._glass_controls = [
        { rep: "KINH_1", code: "GM-02", ctrl: { get_value: () => "GM-02" } },
    ];
    dlg._glass_applied_signature = pick.glass_signature([{ rep: "KINH_1", code: "GM-01" }]);
    dlg._render_display_model = () => {};
    dlg._find_form_row = () => row;

    const getDoc = withGetDocSpy(() => row);
    const setv = withSetValueRecorder(row);
    const alerts = withOrderedAlertSpy(order);
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    try {
        await dlg._on_primary_action();
        await flush();
    } finally { call.restore(); alerts.restore(); setv.restore(); getDoc.restore(); }

    eq(saveCalls, 0, "phase 1: preview ⛔ ghi DB ⇒ ⛔ KHÔNG frm.save() ngầm cho dòng mới");
    eq(order, ["hide", "alert"], "toast vẫn bắn SAU khi dialog đóng");
    eq(alerts.alerts[0].message, MSG_APPLIED_NEW);
    assert(alerts.alerts[0].message.indexOf("Bấm") >= 0,
        "dòng chỉ nằm trên form ⇒ phải mời bấm Lưu báo giá");
    eq(alerts.alerts[0].indicator, "blue");
    eq(alerts.alerts[0].secs, 7);
});

check("(11b) câu lỗi đã nhắc 'Preview tính giá' ⇒ ⛔ không lặp hướng dẫn 2 lần", () => {
    const dlg = makePreviewDialog({});
    const broken = "Kết quả tính giá lưu trên dòng này bị hỏng nên không hiển thị được — "
        + "không phải do bạn nhập sai. Bấm \"Preview tính giá\" để tính lại.";
    const html = dlg._preview_error_html(broken);
    const hits = html.match(/Preview tính giá/gi) || [];
    eq(hits.length, 1, "chỉ nhắc 'Preview tính giá' ĐÚNG 1 lần (trước đây lặp 2 lần liền nhau)");
    assert(html.indexOf("Nếu vẫn lỗi, báo quản trị.") >= 0, "vẫn giữ vế báo quản trị");

    // Lỗi chung (chưa có lối xử lý) → vẫn hiện câu hướng dẫn đầy đủ.
    const generic = dlg._preview_error_html("Máy chủ không phản hồi");
    assert(generic.indexOf("Preview tính giá") >= 0, "lỗi chung vẫn có hướng dẫn bấm Preview");
});

// ═════════════════════════════════════════════════════════════════════════
// (12) PHASE 1 "PREVIEW KHÔNG GHI DB" (Owner chốt 2026-11-21)
//      Đường preview gửi THAM SỐ trong `params` của `preview_bom`; engine
//      dựng dòng từ params ⇒ ⛔ không còn `_sync_row_to_db`/`frm.save()`.
// ═════════════════════════════════════════════════════════════════════════

checkAsync("(12a) preview ⇒ 0 lần _sync_row_to_db / frm.save, gọi preview_bom kèm params", async () => {
    const row = makeBulkRow();
    let saves = 0;
    const frm = {
        doc: { name: "SAL-QTN-1", items: [row] },
        save() { saves += 1; return Promise.resolve(); },
        dirty() {}, refresh_field() {},
    };
    const dlg = makePreviewDialog({ frm: frm, child_doc: row });
    dlg._save = () => ({ vars_json: '{"extra_vars":{"X":1}}', is_new: false });
    dlg._render_display_model = () => {};
    dlg._preview_container = () => fakeContainer();
    const sync = withSyncSpy(() => Promise.resolve({ name: row.name }));
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    try {
        dlg._run_preview(true);
        await flush();
    } finally { sync.restore(); call.restore(); }

    eq(sync.calls.length, 0, "⛔ KHÔNG được ghi dòng xuống DB trước khi preview");
    eq(saves, 0, "⛔ KHÔNG được frm.save() cả báo giá");
    eq(call.calls.length, 1);
    eq(call.calls[0].method, "alumglass.api.preview_bom",
        "phải gọi API preview (không ghi DB), ⛔ không calculate_bom");
    eq(call.calls[0].args.quotation_item_name, row.name);
    const params = JSON.parse(call.calls[0].args.params);
    eq(params.al_bom, row.al_bom, "params mang BOM đang chọn");
    eq(params.al_bom_vars, '{"extra_vars":{"X":1}}', "params mang vars VỪA THU THẬP trong dialog");
    eq(params.parent, "SAL-QTN-1", "params mang tên báo giá để server kiểm quyền");
    assert(!("currency" in params) && !("price_list" in params),
        "⛔ không gửi tiền tệ/bảng giá từ client — server lấy từ Quotation cha");
});

check("(12b) preview sync xong ⇒ tổng tiền được tính lại ĐÚNG 1 lần sau khi rate đổi", () => {
    const row = Object.assign(makeBulkRow(), { rate: 111 });
    const calls = { calc: 0, refresh: [] };
    const frm = {
        doc: { name: "SAL-QTN-1", items: [row] },
        cscript: { calculate_taxes_and_totals() { calls.calc += 1; } },
        refresh_field(f) { calls.refresh.push(f); },
    };
    const dlg = makePreviewDialog({ frm: frm, child_doc: row });
    dlg._render_display_model = () => {};
    dlg._finish_preview_with_glass = () => true;
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    const setv = withSetValueRecorder(row);
    const getDoc = withGetDocSpy(() => row);
    try {
        dlg._exec_calculate_bom(fakeContainer(), 1, false, null, {
            al_bom: "BOM-0001", al_bom_version: "V1", al_bom_vars: "{}",
        });
    } finally { setv.restore(); getDoc.restore(); call.restore(); }

    eq(row.rate, 2000000, "rate đã theo giá vừa tính");
    eq(calls.calc, 1, "calculate_taxes_and_totals phải chạy ĐÚNG 1 lần cho lượt này");
    assert(calls.refresh.indexOf("items") >= 0, "phải vẽ lại lưới items");
    assert(calls.refresh.indexOf("grand_total") >= 0, "phải vẽ lại tổng tiền");

    // Form chưa có controller (vd đang tải) ⇒ ⛔ không được ném lỗi.
    quotation.quotation._refresh_totals({ doc: {}, refresh_field() {} });
});

checkAsync("(12c) dòng MỚI preview ⇒ ⛔ không gửi tên dòng, ⛔ không frm.save()", async () => {
    const row = {
        name: "new-quotation-item-7", idx: 1, doctype: "Quotation Item",
        __islocal: 1, al_bom: "BOM-0001", al_bom_version: "V1",
        al_bom_vars: "{}", item_code: "SP-01", item_name: "Sản phẩm",
    };
    let saves = 0;
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        save() { saves += 1; return Promise.resolve(); },
        dirty() {}, refresh_field() {},
    };
    const dlg = makePreviewDialog({ frm: frm, child_doc: row });
    dlg._save = () => ({ vars_json: "{}", is_new: true });
    dlg._render_display_model = () => {};
    dlg._preview_container = () => fakeContainer();
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    try {
        dlg._run_preview(true);
        await flush();
    } finally { call.restore(); }

    eq(saves, 0, "⛔ KHÔNG frm.save() — dòng mới chỉ nằm trên form");
    eq(call.calls.length, 1);
    eq(call.calls[0].method, "alumglass.api.preview_bom");
    eq(call.calls[0].args.quotation_item_name, "",
        "dòng chưa có trong DB ⇒ ⛔ gửi tên (server sẽ tra DB và báo lỗi)");
    eq(JSON.parse(call.calls[0].args.params).parent, "new-quotation-1",
        "server kiểm quyền `create` cho báo giá chưa lưu");
});

check("(12d) kết quả preview ⇒ câu 'Giá vừa tính chưa được lưu…' + nhớ theo OBJECT dòng", () => {
    const row = makeBulkRow();
    const frm = { doc: { name: "SAL-QTN-1", items: [row] } };
    // `frappe.model.set_value` thật ghi giá trị vào CHÍNH object dòng (Frappe
    // làm đúng như vậy). Stub no-op còn sót từ ca trước sẽ khiến dòng ⛔ mang
    // kết quả ⇒ dấu "chưa lưu" (so sánh NỘI DUNG) đúng là phải hết hiệu lực.
    const old_model = global.frappe.model;
    global.frappe.model = {
        set_value(cdt, cdn, fieldname, value) {
            const target = (global.frappe.get_doc || (() => null))();
            if (target) target[fieldname] = value;
            return Promise.resolve();
        },
    };
    const getDoc = withGetDocSpy(() => row);
    try {
        quotation.quotation._apply_result_to_row(
            frm, "Quotation Item", row.name, RESULT_NEW, { row: row });
    } finally {
        getDoc.restore();
        if (old_model === undefined) delete global.frappe.model;
        else global.frappe.model = old_model;
    }

    assert(quotation.quotation._is_preview_unsaved(row),
        "dòng vừa nhận kết quả preview phải được đánh dấu CHƯA lưu (client-only)");

    const dlg = makePreviewDialog({ frm: frm, child_doc: row });
    dlg._preview_unsaved = quotation.quotation._is_preview_unsaved(row);
    const html = dlg._unsaved_banner();
    assert(html.indexOf("Giá vừa tính chưa được lưu") >= 0,
        "phải nhắc rõ giá chưa lưu để người dùng không gửi khách bản cũ");
    assert(html.indexOf("Bấm nút Lưu ở thanh trên") >= 0, "phải nêu việc cần làm");
    assert(html.indexOf("đóng trang hoặc tải lại là mất kết quả này") >= 0,
        "phải nêu HẬU QUẢ nếu bỏ qua (UX1 2026-11-21)");
    assert(html.indexOf("al_calc") < 0 && html.indexOf("params_hash") < 0,
        "⛔ không phơi mã kỹ thuật ra người dùng");

    dlg._preview_unsaved = false;
    eq(dlg._unsaved_banner(), "", "chưa preview lượt nào ⇒ không hiện nhắc");
});

// ═════════════════════════════════════════════════════════════════════════
// (13) UX1 gate 2026-11-21 — "Preview không ghi DB" phải NÓI ĐÚNG trạng thái
//      3 điểm 🔴: cửa sổ 🖥️ chỉ để xem; banner "chưa lưu" phải tắt sau khi
//      Lưu; toast kết quả preview phải xanh DƯƠNG + nêu hậu quả.
// ═════════════════════════════════════════════════════════════════════════

// `frappe.model.set_value` THẬT (Frappe ghi thẳng vào object trong `locals`) —
// stub no-op còn sót từ ca trước không phản ánh hành vi thật.
function withRealSetValue(fn) {
    const old_model = global.frappe.model;
    global.frappe.model = {
        set_value(cdt, cdn, fieldname, value) {
            const target = (global.frappe.get_doc || (() => null))();
            if (target) target[fieldname] = value;
            return Promise.resolve();
        },
    };
    try { return fn(); } finally {
        if (old_model === undefined) delete global.frappe.model;
        else global.frappe.model = old_model;
    }
}

// Đánh dấu dòng "đã preview, CHƯA lưu" bằng đúng đường production dùng.
function mark_previewed(frm, row) {
    const getDoc = withGetDocSpy(() => row);
    try {
        withRealSetValue(() => quotation.quotation._apply_result_to_row(
            frm, "Quotation Item", row.name, RESULT_NEW, { row: row }));
    } finally { getDoc.restore(); }
}

function captureAlerts(fn) {
    const alerts = [];
    const old = global.frappe.show_alert;
    global.frappe.show_alert = function (opts, secs) {
        alerts.push({ message: opts && opts.message, indicator: opts && opts.indicator, secs: secs });
    };
    try { fn(); } finally { global.frappe.show_alert = old; }
    return alerts;
}

function captureMsgprints(fn) {
    const msgs = [];
    const old = global.frappe.msgprint;
    global.frappe.msgprint = function (m) { msgs.push(m); };
    try { fn(); } finally { global.frappe.msgprint = old; }
    return msgs;
}

function withRealtime(fn) {
    const handlers = {};
    const old = global.frappe.realtime;
    global.frappe.realtime = {
        on(event, cb) { handlers[event] = cb; },
        off(event) { if (handlers[event]) delete handlers[event]; },
    };
    try { return fn(handlers); } finally {
        if (old === undefined) delete global.frappe.realtime;
        else global.frappe.realtime = old;
    }
}

// Dựng BOMDialog thật (frappe.ui.Dialog đã stub) trên một dòng MỚI (render
// ngay, ⛔ gọi API đọc DB) và trả về [bom, dialog_giả].
function makeBomDialog(row, frm) {
    DIALOG_INSTANCES.length = 0;
    const bom = new quotation.BOMDialog(
        row.name, quotation.quotation._row_preview_params(frm, row), frm);
    bom.show();
    return { bom: bom, dlg: DIALOG_INSTANCES[DIALOG_INSTANCES.length - 1] };
}

check("(13a) BOMDialog chỉ XEM — ⛔ ghi gì xuống dòng, có câu 'chưa ghi vào báo giá'", () => {
    const row = makeBulkRow({ name: "new-quotation-item-1", is_new: 1, idx: 1 });
    delete row.al_bom_result;
    let dirty = 0;
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() { dirty += 1; }, refresh_field() {},
    };
    const call = withCallSpy();  // calculate() gửi preview_bom — KHÔNG callback
    const inst = makeBomDialog(row, frm);
    try {
        inst.bom.render_results(RESULT_NEW);
    } finally { call.restore(); }

    const html = String(inst.dlg.values["result_html"] || "");
    assert(html.indexOf("chưa ghi vào báo giá") >= 0,
        "cửa sổ kết quả PHẢI nói rõ chỉ để xem: " + html.slice(0, 200));
    assert(html.indexOf("Áp dụng vào dòng") >= 0,
        "phải chỉ nút để dùng kết quả");
    // Chưa bấm "Áp dụng vào dòng" ⇒ KHÔNG có gì ghi xuống dòng.
    assert(!row.al_bom_result, "⛔ được ghi al_bom_result khi chưa bấm Áp dụng");
    eq(row.al_calc_status, ROW_STALE.al_calc_status,
        "⛔ được đổi trạng thái trên dòng (giữ nguyên bản cũ)");
    eq(row.rate, ROW_STALE.rate, "⛔ được đổi đơn giá");
    eq(dirty, 0, "⛔ được đánh dấu phiếu có thay đổi");
});

check("(13b) bấm 'Áp dụng vào dòng' ⇒ dòng nhận đủ bộ, dirty(), toast xanh dương, 0 ghi DB", () => {
    const row = makeBulkRow({ name: "new-quotation-item-2", is_new: 1, idx: 1 });
    delete row.al_bom_result;
    let dirty = 0;
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() { dirty += 1; }, refresh_field() {},
    };
    const call = withCallSpy();
    const dbWrites = [];
    const old_db = global.frappe.db;
    global.frappe.db = {
        set_value() { dbWrites.push(Array.prototype.slice.call(arguments)); },
        get_value() { dbWrites.push("get_value"); },
    };
    let inst = null;
    const getDoc = withGetDocSpy(() => row);
    const alerts = captureAlerts(() => {
        inst = makeBomDialog(row, frm);
        inst.bom.render_results(RESULT_NEW);
        withRealSetValue(() => inst.bom._apply_to_form_row());
    });
    getDoc.restore();
    if (old_db === undefined) delete global.frappe.db;
    else global.frappe.db = old_db;
    call.restore();

    eq(row.al_bom_result, JSON.stringify(RESULT_NEW), "dòng phải nhận ĐÚNG kết quả");
    eq(row.al_gia_ban, 2000000, "al_gia_ban = giá trước VAT");
    eq(row.al_gia_vat, 2200000, "al_gia_vat = giá có VAT");
    eq(row.rate, 2000000, "rate theo giá trước VAT");
    eq(row.al_calc_status, "Success");
    eq(dirty, 1, "phải frm.dirty() để nút Lưu của báo giá bật");
    eq(inst.dlg.hidden, 1, "áp dụng xong phải đóng cửa sổ");
    eq(dbWrites.length, 0, "⛔ 0 lần ghi DB — chỉ nút Lưu báo giá mới ghi");

    const toast = alerts.find((a) => String(a.message).indexOf("Đã áp dụng") >= 0);
    assert(toast, "phải báo đã áp dụng: " + JSON.stringify(alerts));
    eq(toast.indicator, "blue", "xanh dương = chưa ghi DB (xanh lá = đã xong thật)");
    eq(toast.secs, 7, "câu dài ⇒ để 7 giây đọc kịp");
    assert(String(toast.message).indexOf("chưa lưu vào báo giá") >= 0, toast.message);
    assert(String(toast.message).indexOf("Bấm nút Lưu trên báo giá") >= 0,
        "phải nêu đúng việc cần làm: " + toast.message);
});

check("(13c) preview → after_save ⇒ banner 'chưa lưu' KHÔNG còn (so sánh NỘI DUNG)", () => {
    const row = makeBulkRow();
    const frm = { doc: { name: "SAL-QTN-1", items: [row] }, dirty() {}, refresh_field() {} };
    mark_previewed(frm, row);
    assert(quotation.quotation._is_preview_unsaved(row), "đã preview ⇒ còn dấu");

    // Đối chứng NỘI DUNG: dòng bị thay `al_bom_result` (vd nạp bản khác) thì
    // dấu cũ hết nghĩa — ⛔ chỉ tin WeakSet giữ object.
    const other = makeBulkRow({ name: "QTN-ITEM-0002", idx: 2 });
    mark_previewed(frm, other);
    assert(quotation.quotation._is_preview_unsaved(other));
    other.al_bom_result = '{"da_bi_thay":true}';
    eq(quotation.quotation._is_preview_unsaved(other), false,
        "nội dung dòng khác bản đã preview ⇒ ⛔ còn báo 'chưa lưu'");

    const handlers = FORM_EVENTS["Quotation"] || {};
    assert(typeof handlers.after_save === "function",
        "phải có handler after_save để xoá dấu sau khi Lưu báo giá");
    handlers.after_save(frm);

    eq(quotation.quotation._is_preview_unsaved(row), false,
        "Lưu báo giá xong ⇒ dấu 'chưa lưu' phải mất");
    const dlg = makePreviewDialog({ frm: frm, child_doc: row });
    dlg._preview_unsaved = quotation.quotation._is_preview_unsaved(row);
    eq(dlg._unsaved_banner(), "", "mở lại dialog sau khi Lưu ⇒ KHÔNG còn banner");
});

check("(13d) 3 toast 'Tính giá xong/Đã tính' ⇒ xanh dương + vế 'chưa lưu'", () => {
    // (i) ItemParamDialog — kết quả job nền về
    const dlg = makePreviewDialog({
        frm: { doc: { items: [] } },
        child_doc: { name: "QTN-ITEM-0001", doctype: "Quotation Item" },
    });
    dlg._write_result_to_row = () => true;
    dlg._render_display_model = () => {};
    dlg._preview_container = () => $();
    dlg._finish_preview_with_glass = () => true;
    const alerts = withRealtime((handlers) => {
        return captureAlerts(() => {
            dlg._listen_realtime("JOB-1", $(), null);
            handlers["alumglass_bom_calc_done"](
                { job_id: "JOB-1", status: "Success", result: RESULT_NEW });
        });
    });
    eq(alerts.length, 1, "phải có đúng 1 toast: " + JSON.stringify(alerts));
    eq(alerts[0].indicator, "blue", "xanh dương, ⛔ xanh lá (chưa ghi DB)");
    assert(alerts[0].message.indexOf("chưa lưu vào báo giá") >= 0, alerts[0].message);

    // (ii) BOMDialog — kết quả job nền về
    const bom = new quotation.BOMDialog("new-quotation-item-5", { al_bom: "BOM-0001" }, null);
    bom.show();
    bom.render_results = () => {};
    const bom_alerts = withRealtime((handlers) => captureAlerts(() => {
        bom._listen_realtime("JOB-2");
        handlers["alumglass_bom_calc_done"](
            { job_id: "JOB-2", status: "Success", result: RESULT_NEW });
    }));
    eq(bom_alerts.length, 1, "BOMDialog phải báo: " + JSON.stringify(bom_alerts));
    eq(bom_alerts[0].indicator, "blue");
    assert(bom_alerts[0].message.indexOf("chưa lưu vào báo giá") >= 0, bom_alerts[0].message);

    // (iii) "Tính giá" hàng loạt — toast tổng kết
    const row = makeBulkRow();
    const frm = { doc: { items: [row] }, dirty() {}, refresh_field() {} };
    const getDoc = withGetDocSpy(() => row);
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    const bulk_alerts = captureAlerts(() => {
        withRealSetValue(() => quotation.quotation._calc_all_items(frm));
    });
    getDoc.restore();
    call.restore();
    const done = bulk_alerts.filter((a) => String(a.message).indexOf("Đã tính") >= 0);
    eq(done.length, 1, "phải có toast tổng kết: " + JSON.stringify(bulk_alerts));
    eq(done[0].indicator, "blue", "đỏ chỉ khi có dòng lỗi");
    assert(done[0].message.indexOf("chưa lưu vào báo giá") >= 0, done[0].message);
    assert(done[0].message.indexOf("Bấm Lưu để ghi lại") >= 0, done[0].message);
});

checkAsync("(13e) bulk với toàn dòng MỚI ⇒ ⛔ báo 'Chưa có dòng sản phẩm nào.'", async () => {
    const row = makeBulkRow({
        name: "new-quotation-item-1", is_new: 1, idx: 1,
        al_bom: "BOM-0001", al_bom_version: "V1", al_bom_vars: "{}",
    });
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() {}, refresh_field() {},
    };
    const getDoc = withGetDocSpy(() => row);
    const call = withCallSpy((o) => o.callback({ message: RESULT_NEW }));
    const msgs = captureMsgprints(() => withRealSetValue(
        () => quotation.quotation._calc_all_items(frm)));
    await flush();
    await flush();
    getDoc.restore();
    call.restore();

    const text = JSON.stringify(msgs);
    assert(text.indexOf("Chưa có dòng sản phẩm nào") < 0,
        "lưới CÓ dòng ⇒ ⛔ được báo 'chưa có dòng nào': " + text);
    eq(call.calls.length, 1, "dòng mới vẫn phải được tính");
    eq(call.calls[0].method, "alumglass.api.preview_bom");
    eq(call.calls[0].args.quotation_item_name, "",
        "dòng chưa lưu ⇒ ⛔ gửi tên dòng");
    eq(JSON.parse(call.calls[0].args.params).parent, "new-quotation-1",
        "server cần `parent` để kiểm quyền");
    eq(row.al_calc_status, "Success");

    // Dòng mới THIẾU BOM ⇒ câu đúng chỗ (⛔ phải 'chưa có dòng nào').
    const row2 = makeBulkRow({ name: "new-quotation-item-2", is_new: 1, idx: 1 });
    delete row2.al_bom;
    const call2 = withCallSpy();
    const msgs2 = captureMsgprints(() => quotation.quotation._calc_all_items({
        doc: { name: "new-quotation-1", items: [row2] }, dirty() {}, refresh_field() {},
    }));
    call2.restore();
    const text2 = JSON.stringify(msgs2);
    assert(text2.indexOf("Chưa có dòng sản phẩm nào") < 0, text2);
    assert(text2.indexOf("Dòng 1") >= 0, "phải nêu ĐÚNG số dòng: " + text2);
    assert(text2.indexOf("chưa chọn BOM") >= 0, text2);
    eq(call2.calls.length, 0, "thiếu BOM ⇒ ⛔ gọi tính giá");

    // "Preview giá toàn bộ" với toàn dòng MỚI ⇒ câu đúng trạng thái, ⛔
    // "Chưa có dòng sản phẩm nào." (lưới CÓ dòng). Frappe ⛔ set property
    // `is_new` trên dòng con ⇒ ca này dùng ĐÚNG cờ thật (`__islocal`).
    const unsaved_row = makeBulkRow({ name: "QTN-ITEM-9999" });
    delete unsaved_row.is_new;
    unsaved_row.__islocal = 1;
    eq(quotation.quotation._row_is_new(unsaved_row), true,
        "`__islocal` là cờ THẬT của dòng chưa lưu");
    eq(quotation.quotation._row_is_new({ name: "QTN-ITEM-0001", is_new: 0 }), false,
        "dòng đã lưu (có tên thật) ⛔ coi là dòng mới");
    const msgs3 = captureMsgprints(() => quotation.quotation._preview_all_items({
        doc: { name: "new-quotation-1", items: [unsaved_row] },
    }));
    const text3 = JSON.stringify(msgs3);
    assert(text3.indexOf("Chưa có dòng sản phẩm nào") < 0, text3);
    assert(text3.indexOf("dòng chưa lưu trên báo giá nên chưa tính") >= 0,
        "phải nói đúng vì sao chưa tính được: " + text3);

    // Lưới RỖNG thật ⇒ câu cũ vẫn đúng.
    const msgs4 = captureMsgprints(() => quotation.quotation._preview_all_items({
        doc: { name: "new-quotation-1", items: [] },
    }));
    assert(JSON.stringify(msgs4).indexOf("Chưa có dòng sản phẩm nào") >= 0,
        "lưới rỗng ⇒ báo chưa có dòng");
});

check("(13f) nút chính của 2 dialog là 'Áp dụng vào dòng' (⛔ 'Lưu')", () => {
    // BOMDialog (🖥️)
    const row = makeBulkRow({ name: "new-quotation-item-1", is_new: 1 });
    const frm = { doc: { name: "new-quotation-1", items: [row] } };
    const call = withCallSpy();
    const inst = makeBomDialog(row, frm);
    call.restore();
    eq(inst.dlg.opts.primary_action_label, "Áp dụng vào dòng");
    eq(inst.dlg.opts.secondary_action_label, "Đóng");

    // ItemParamDialog (📐) — "Lưu" trùng chữ với nút lưu báo giá, nghĩa ngược.
    const D = quotation.quotation.ItemParamDialog.prototype;
    const ipd = Object.create(D);
    ipd.child_doc = { item_name: "Sản phẩm" };
    ipd._build_dialog_fields = () => [];
    ipd._populate_extra_vars = () => {};
    ipd._setup_extra_vars_autofill = () => {};
    ipd._load_variable_set = () => Promise.resolve({});
    ipd._render_vars_container = () => {};
    ipd._render_bom_info = () => {};
    ipd._schedule_auto_preview = () => {};
    ipd._cleanup_realtime = () => {};
    const old_excel = quotation.excel_io;
    quotation.excel_io = { attach() {} };
    DIALOG_INSTANCES.length = 0;
    try { ipd._render_dialog(); } finally {
        if (old_excel === undefined) delete quotation.excel_io;
        else quotation.excel_io = old_excel;
    }
    eq(DIALOG_INSTANCES[DIALOG_INSTANCES.length - 1].opts.primary_action_label,
        "Áp dụng vào dòng");
});

check("(13i) `_attach_row_actions` với form THIẾU `fields_dict` ⇒ ⛔ ném (lỗi rò timer)", () => {
    // Lỗi thật đã thấy: `after_save` đặt `setTimeout(..., 600)`, form giả/đã
    // đóng không có `fields_dict` ⇒ TypeError **trong timer** ⇒ test xanh mà
    // tiến trình chết (exit 1) và không ai thấy trong log PASS.
    quotation.quotation._attach_row_actions({ doc: { items: [] } });
    quotation.quotation._attach_row_actions({});
    quotation.quotation._attach_row_actions(null);
    quotation.quotation._attach_row_actions(undefined);
});

// ═════════════════════════════════════════════════════════════════════════
// (14) Phase 2 — "Lưu rồi in": in khi còn preview CHƯA lưu ⇒ bắt Lưu trước
//      (Owner chốt 2026-11-21). Chỉ 2 lối: "Lưu rồi in" hoặc "Huỷ".
// ═════════════════════════════════════════════════════════════════════════

// Form giả: `save` mô phỏng Frappe — biết kết quả qua `callback` / `on_error`
// (promise của Frappe NUỐT lỗi nên ⛔ dựa vào nó để biết lưu xong).
function makePrintFrm(opts) {
    opts = opts || {};
    return {
        doc: { name: "SAL-QTN-1", items: opts.items || [] },
        printed: [],
        save_calls: 0,
        save_cb: null,
        save_on_error: null,
        print_doc() { this.printed.push(Array.prototype.slice.call(arguments)); },
        save(action, cb, btn, on_error) {
            this.save_calls += 1;
            this.save_cb = cb || null;
            this.save_on_error = on_error || null;
            return undefined;
        },
    };
}

function open_print_dialog(frm) {
    DIALOG_INSTANCES.length = 0;
    frm.print_doc();
    return DIALOG_INSTANCES[DIALOG_INSTANCES.length - 1] || null;
}

check("(14a) in khi có preview chưa lưu ⇒ hộp thoại 2 nút, ⛔ in, ⛔ cảnh báo-rồi-in", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    const msgs = captureMsgprints(() => {
        DIALOG_INSTANCES.length = 0;
        frm.print_doc();
    });
    eq(frm.printed.length, 0, "⛔ in khi chưa Lưu");
    eq(msgs.length, 0, "phase 2 thay cảnh báo-rồi-in bằng hộp thoại");
    eq(DIALOG_INSTANCES.length, 1, "phải mở ĐÚNG 1 hộp thoại");

    const opts = DIALOG_INSTANCES[0].opts;
    // Báo giá ĐÃ lưu ⇒ tiêu đề nói "có giá vừa tính chưa lưu" (⛔ khẳng định
    // bản in là bản cũ: printview nhận chính document từ trình duyệt khi có).
    eq(opts.title, "Báo giá có giá vừa tính chưa lưu");
    eq(opts.primary_action_label, "Lưu rồi in");
    eq(opts.secondary_action_label, "Huỷ");
    assert(!("tertiary_action" in opts), "⛔ được có lối 'vẫn in bản cũ'");
    const html = String(DIALOG_INSTANCES[0].fields_dict["al_print_msg"].$wrapper.html());
    assert(html.indexOf("Bạn vừa tính lại giá nhưng chưa lưu báo giá") >= 0, html);
    assert(html.indexOf("bản in chắc chắn khớp số trên màn hình") >= 0, html);
});

check("(14b) 'Lưu rồi in' ⇒ lưu 1 lần, lưu XONG mới in 1 lần, đúng tham số in ban đầu", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    DIALOG_INSTANCES.length = 0;
    frm.print_doc("ALUMGLASS-QUOTATION");
    const dlg = DIALOG_INSTANCES[0];
    dlg.opts.primary_action();

    eq(frm.save_calls, 1, "phải gọi frm.save đúng 1 lần");
    eq(frm.printed.length, 0, "⛔ in trước khi lưu xong");
    // Frappe lưu xong: bắn after_save (xoá dấu) rồi gọi callback.
    quotation.quotation._clear_preview_marks(frm);
    frm.save_cb({ docs: [] });

    eq(frm.printed.length, 1, "lưu xong ⇒ in ĐÚNG 1 lần");
    eq(frm.printed[0], ["ALUMGLASS-QUOTATION"],
        "phát lại ĐÚNG lệnh in người dùng vừa bấm (cùng tham số)");
});

check("(14c) bấm 'Huỷ' ⇒ ⛔ lưu, ⛔ in", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    const dlg = open_print_dialog(frm);
    dlg.opts.secondary_action();
    eq(frm.save_calls, 0, "Huỷ ⇒ ⛔ lưu");
    eq(frm.printed.length, 0, "Huỷ ⇒ ⛔ in");
});

check("(14d) in khi KHÔNG còn preview chưa lưu ⇒ in ngay, ⛔ hộp thoại", () => {
    const frm = makePrintFrm({ items: [makeBulkRow()] });
    quotation.quotation._attach_print_guard(frm);
    DIALOG_INSTANCES.length = 0;
    frm.print_doc("PF-1");
    eq(frm.printed.length, 1, "in ngay");
    eq(DIALOG_INSTANCES.length, 0, "⛔ hộp thoại");
    eq(frm.save_calls, 0, "⛔ lưu");

    // Đã Lưu báo giá (after_save xoá dấu) ⇒ in bình thường.
    const row = makeBulkRow({ name: "QTN-ITEM-0002", idx: 2 });
    const frm2 = makePrintFrm({ items: [row] });
    mark_previewed(frm2, row);
    quotation.quotation._attach_print_guard(frm2);
    quotation.quotation._clear_preview_marks(frm2);
    DIALOG_INSTANCES.length = 0;
    frm2.print_doc();
    eq(frm2.printed.length, 1, "Lưu xong ⇒ in ngay");
    eq(DIALOG_INSTANCES.length, 0);
});

check("(14e) lưu thất bại ⇒ ⛔ in + câu người-đọc-được (⛔ traceback)", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    // (i) lỗi validate/mạng: Frappe gọi on_error
    let dlg = open_print_dialog(frm);
    dlg.opts.primary_action();
    const msgs = captureMsgprints(() => frm.save_on_error());
    eq(frm.printed.length, 0, "lưu lỗi ⇒ ⛔ in");
    eq(msgs.length, 1, "phải báo cho người dùng");
    eq(msgs[0].indicator, "red");
    assert(String(msgs[0].message).indexOf("Chưa lưu được báo giá nên chưa in") >= 0,
        msgs[0].message);
    assert(!/Traceback|Exception|TypeError/.test(String(msgs[0].message)),
        "⛔ phơi traceback");

    // (ii) server trả `exc` qua callback
    const row2 = makeBulkRow({ name: "QTN-ITEM-0002", idx: 2 });
    const frm2 = makePrintFrm({ items: [row2] });
    mark_previewed(frm2, row2);
    quotation.quotation._attach_print_guard(frm2);
    dlg = open_print_dialog(frm2);
    dlg.opts.primary_action();
    const msgs2 = captureMsgprints(() => frm2.save_cb({ exc: "boom", _server_messages: "[]" }));
    eq(frm2.printed.length, 0, "server báo lỗi ⇒ ⛔ in");
    eq(msgs2.length, 1);
});

check("(14f) gọi in 2 lần trong lúc đang lưu ⇒ ⛔ in 2 lần (chống đệ quy/đua)", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    DIALOG_INSTANCES.length = 0;
    frm.print_doc();
    frm.print_doc();  // bấm in lần 2 khi hộp thoại đang mở
    eq(DIALOG_INSTANCES.length, 1, "⛔ mở 2 hộp thoại");

    const dlg = DIALOG_INSTANCES[0];
    dlg.opts.primary_action();
    frm.print_doc();  // bấm in lần 3 khi đang LƯU
    eq(frm.save_calls, 1, "⛔ lưu 2 lần");
    eq(frm.printed.length, 0, "⛔ in khi đang lưu");

    frm.save_cb({});
    eq(frm.printed.length, 1, "in ĐÚNG 1 lần cho lượt in ban đầu");

    // Lượt in do hộp thoại phát lại ⛔ mở lại hộp thoại (bypass), và sau khi
    // Lưu (dấu đã xoá ở after_save) thì in bình thường.
    quotation.quotation._clear_preview_marks(frm);
    frm.print_doc();
    eq(frm.printed.length, 2, "sau khi Lưu ⇒ in bình thường");
});

// ═════════════════════════════════════════════════════════════════════════
// (15) UX1 chặn tiếp (2026-11-21) — hộp thoại in kẹt cờ, toast phơi docname,
//      lưu lỗi vẫn in, tiêu đề sai với báo giá chưa lưu, cửa sổ 🖥️ tự bật lại
// ═════════════════════════════════════════════════════════════════════════

check("(15a) đóng hộp thoại in bằng X/Esc/click nền ⇒ lần in sau MỞ LẠI hộp (⛔ im lặng)", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    DIALOG_INSTANCES.length = 0;
    frm.print_doc();
    eq(DIALOG_INSTANCES.length, 1, "mở hộp lần 1");
    eq(frm.__al_print_dialog_open, true);

    DIALOG_INSTANCES[0].hide();   // X / Esc / click nền — Frappe phát `onhide`
    eq(frm.__al_print_dialog_open, false,
        "đóng kiểu nào cũng phải nhả cờ (thiếu là mọi lần in sau chết im lặng)");

    frm.print_doc();
    eq(DIALOG_INSTANCES.length, 2, "lần in sau phải MỞ LẠI hộp thoại");
    eq(frm.printed.length, 0, "vẫn ⛔ in khi chưa Lưu");
});

check("(15b) toast kết quả nền của cửa sổ 🖥️ ⛔ chứa docname dòng (hash)", () => {
    const DOCNAME = "7f3a91c0d2ab4e55";
    const bom = new quotation.BOMDialog(DOCNAME, { al_bom: "BOM-0001" }, null);
    bom.show();
    bom.render_results = () => {};
    const alerts = withRealtime((handlers) => captureAlerts(() => {
        bom._listen_realtime("JOB-15");
        handlers["alumglass_bom_calc_done"](
            { job_id: "JOB-15", status: "Success", result: RESULT_NEW });
    }));
    eq(alerts.length, 1, JSON.stringify(alerts));
    assert(String(alerts[0].message).indexOf(DOCNAME) < 0,
        "⛔ phơi docname (hash) ra người dùng: " + alerts[0].message);
    eq(alerts[0].message, "Tính giá xong — chưa lưu vào báo giá.");
    eq(alerts[0].indicator, "blue");
});

check("(15c) `frm.save` gọi on_error ⇒ ⛔ in + câu có lối thoát tải lại trang", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    const dlg = open_print_dialog(frm);
    dlg.opts.primary_action();
    const msgs = captureMsgprints(() => frm.save_on_error());
    eq(frm.printed.length, 0, "⛔ in");
    eq(msgs.length, 1);
    eq(msgs[0].indicator, "red");
    assert(String(msgs[0].message).indexOf("Chưa lưu được báo giá nên chưa in") >= 0,
        msgs[0].message);
    assert(String(msgs[0].message).indexOf("tải lại trang") >= 0,
        "phải có lối thoát cho người chỉ cần bản in: " + msgs[0].message);
});

checkAsync("(15d) promise lưu resolve nhưng phiếu VẪN BẨN ⇒ ⛔ in", async () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    mark_previewed(frm, row);
    // Frappe: `frm.save()` resolve KỂ CẢ khi `validate_form_action` ném (chỉ
    // `.catch(console.error)`), ⛔ gọi callback ⇒ chỉ còn backstop promise.
    frm.is_dirty = () => true;
    frm.save = function () { this.save_calls += 1; return Promise.resolve(); };
    quotation.quotation._attach_print_guard(frm);

    const dlg = open_print_dialog(frm);
    // Giữ spy qua CẢ microtask (finish() chạy trong `.then` sau khi hàm trả về).
    const msgs = [];
    const old_msgprint = global.frappe.msgprint;
    global.frappe.msgprint = (m) => msgs.push(m);
    try {
        dlg.opts.primary_action();
        await flush();
        await flush();
    } finally {
        global.frappe.msgprint = old_msgprint;
    }
    eq(frm.printed.length, 0, "phiếu còn bẩn ⇒ lưu CHƯA xong ⇒ ⛔ in");
    eq(msgs.length, 1, "phải báo lỗi cho người dùng");
});

check("(15e) cửa sổ 🖥️ chưa có kết quả ⇒ nút 'Áp dụng' DISABLED, bấm ⛔ đóng im lặng", () => {
    const row = makeBulkRow({ name: "new-quotation-item-1", is_new: 1, idx: 1 });
    delete row.al_bom_result;
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() {}, refresh_field() {},
    };
    const call = withCallSpy();   // calculate() ⛔ callback ⇒ chưa có kết quả
    const inst = makeBomDialog(row, frm);
    call.restore();

    eq(inst.dlg.primary_disabled, true,
        "chưa có kết quả ⇒ phải disable_primary_action()");
    const hidden_before = inst.dlg.hidden;
    inst.bom._apply_to_form_row();
    eq(inst.dlg.hidden, hidden_before,
        "⛔ đóng cửa sổ im lặng khi chưa có gì để áp dụng");
    eq(row.al_calc_status, ROW_STALE.al_calc_status, "⛔ ghi gì xuống dòng");

    // Kết quả về ⇒ bật lại nút.
    inst.bom.render_results(RESULT_NEW);
    eq(inst.dlg.primary_disabled, false, "có kết quả ⇒ bật lại nút Áp dụng");
});

check("(15f) kết quả nền về MUỘN sau khi đóng cửa sổ 🖥️ ⇒ ⛔ tự bật lại", () => {
    const row = makeBulkRow({ name: "new-quotation-item-2", is_new: 1, idx: 1 });
    const frm = { doc: { name: "new-quotation-1", items: [row] } };
    const call = withCallSpy();
    const inst = makeBomDialog(row, frm);
    call.restore();

    const shown_before = inst.dlg.shown;
    inst.dlg.hide();   // người dùng đóng bằng X/Esc
    eq(inst.bom._dialog_open, false, "đóng ⇒ cờ phải về false");

    inst.bom.render_results(RESULT_NEW);  // kết quả về muộn (dòng mới render ngay)
    eq(inst.dlg.shown, shown_before, "⛔ tự mở lại cửa sổ người dùng đã đóng");
});

check("(15g) báo giá CHƯA từng lưu ⇒ tiêu đề 'Báo giá chưa được lưu'", () => {
    const row = makeBulkRow({ name: "new-quotation-item-1", is_new: 1 });
    const frm = makePrintFrm({ items: [row] });
    frm.doc.name = "new-quotation-1";
    frm.is_new = () => true;
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    const dlg = open_print_dialog(frm);
    eq(dlg.opts.title, "Báo giá chưa được lưu",
        "chưa lưu lần nào ⇒ ⛔ nói 'Bản in đang là giá đã lưu'");
    const html = String(dlg.fields_dict["al_print_msg"].$wrapper.html());
    assert(html.indexOf("bản in chắc chắn khớp số trên màn hình") >= 0, html);
});

check("(15h) báo giá CHƯA lưu + lưu lỗi ⇒ câu lỗi báo mất TOÀN BỘ nội dung vừa nhập", () => {
    // Với phiếu CHƯA từng lưu, tải lại trang mất cả báo giá vừa nhập — ⛔ phải
    // "chỉ mất kết quả vừa tính" như câu của phiếu đã lưu ("in bản đã lưu").
    const row = makeBulkRow({ name: "new-quotation-item-1", is_new: 1 });
    const frm = makePrintFrm({ items: [row] });
    frm.doc.name = "new-quotation-1";
    frm.is_new = () => true;
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    const dlg = open_print_dialog(frm);
    dlg.opts.primary_action();
    const msgs = captureMsgprints(() => frm.save_on_error());
    eq(frm.printed.length, 0, "lưu lỗi ⇒ ⛔ in");
    eq(msgs.length, 1, "phải báo cho người dùng");
    eq(msgs[0].indicator, "red");
    const msg = String(msgs[0].message);
    assert(msg.indexOf("in bản đã lưu") < 0,
        "phiếu mới ⛔ có 'bản đã lưu' nào để in: " + msg);
    assert(msg.indexOf("mất toàn bộ nội dung vừa nhập") >= 0, msg);
    assert(msg.indexOf("báo giá chưa được lưu lần nào") >= 0, msg);
    // Lỗi server trả qua callback cũng phải rẽ nhánh như on_error.
    const dlg2 = open_print_dialog(frm);
    const msgs2 = captureMsgprints(() => {
        dlg2.opts.primary_action();
        frm.save_cb({ exc: "boom", _server_messages: "[]" });
    });
    eq(msgs2.length, 1);
    assert(String(msgs2[0].message).indexOf("mất toàn bộ nội dung vừa nhập") >= 0,
        msgs2[0].message);
});

check("(15i) báo giá ĐÃ lưu + lưu lỗi ⇒ GIỮ câu cũ (in bản đã lưu, mất kết quả vừa tính)", () => {
    const row = makeBulkRow();
    const frm = makePrintFrm({ items: [row] });
    frm.is_new = () => false;
    mark_previewed(frm, row);
    quotation.quotation._attach_print_guard(frm);

    const dlg = open_print_dialog(frm);
    dlg.opts.primary_action();
    const msgs = captureMsgprints(() => frm.save_on_error());
    eq(frm.printed.length, 0, "lưu lỗi ⇒ ⛔ in");
    eq(msgs.length, 1);
    eq(msgs[0].indicator, "red");
    eq(String(msgs[0].message),
        "Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi bấm Lưu lại. " +
        "Nếu chỉ cần in bản đã lưu thì tải lại trang (kết quả vừa tính sẽ mất).",
        "đã lưu ⇒ phải giữ NGUYÊN câu cũ");

    // Form KHÔNG có `is_new` (form giả/khác phiên bản) ⇒ guard coi như ĐÃ lưu:
    // câu nhẹ hơn, ⛔ hù bằng cảnh báo mất toàn bộ dữ liệu sai.
    const row2 = makeBulkRow({ name: "QTN-ITEM-0002", idx: 2 });
    const frm2 = makePrintFrm({ items: [row2] });
    mark_previewed(frm2, row2);
    quotation.quotation._attach_print_guard(frm2);
    const dlg2 = open_print_dialog(frm2);
    dlg2.opts.primary_action();
    const msgs2 = captureMsgprints(() => frm2.save_on_error());
    eq(msgs2.length, 1);
    const msg2 = String(msgs2[0].message);
    assert(msg2.indexOf("in bản đã lưu") >= 0, msg2);
    assert(msg2.indexOf("tải lại trang") >= 0, msg2);
    assert(msg2.indexOf("mất toàn bộ nội dung vừa nhập") < 0,
        "thiếu `is_new` ⇒ guard phải coi là đã lưu: " + msg2);
});

check("(13h) bulk async dòng MỚI (server trả qi_name rỗng) ⇒ kết quả vẫn về ĐÚNG dòng", () => {
    const row = makeBulkRow({
        name: "new-quotation-item-9", is_new: 1, idx: 1,
        al_bom: "BOM-0001", al_bom_version: "V1", al_bom_vars: "{}",
    });
    delete row.al_bom_result;
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() {}, refresh_field() {},
    };
    const handlers = {};
    const old_realtime = global.frappe.realtime;
    global.frappe.realtime = {
        on(event, fn) { handlers[event] = fn; },
        off(event) { if (handlers[event]) delete handlers[event]; },
    };
    const call = withCallSpy((o) => o.callback({
        message: { async: true, job_id: "job-9", message: "đang tính" },
    }));
    const getDoc = withGetDocSpy(() => row);
    try {
        withRealSetValue(() => quotation.quotation._calc_all_items(frm));
    } finally { getDoc.restore(); call.restore(); }
    eq(row.al_calc_status, "Queued");

    const handler = handlers["alumglass_bom_calc_done"];
    assert(typeof handler === "function", "phải nghe realtime cho dòng mới");
    const getDoc2 = withGetDocSpy(() => row);
    try {
        withRealSetValue(() => handler(
            { job_id: "job-9", qi_name: "", status: "Success", result: RESULT_NEW }));
    } finally { getDoc2.restore(); }
    if (old_realtime === undefined) delete global.frappe.realtime;
    else global.frappe.realtime = old_realtime;

    eq(row.al_calc_status, "Success",
        "dòng MỚI có qi_name rỗng ⇒ phải dùng object dòng đã gửi job");
    eq(row.al_bom_result, JSON.stringify(RESULT_NEW));
    eq(row.rate, 2000000);
});

// ═════════════════════════════════════════════════════════════════════════
// (16) Nhãn tiếng Anh còn sót trên bề mặt người dùng (UX1 phát hiện)
//   Cửa sổ 🖥️ và bảng kết quả phải nói tiếng Việt như phần còn lại của UI.
// ═════════════════════════════════════════════════════════════════════════
check("(16a) cửa sổ 🖥️ có tiêu đề tiếng Việt 'Kết quả tính giá'", () => {
    const row = makeBulkRow({ name: "new-quotation-item-16a", is_new: 1, idx: 1 });
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() {}, refresh_field() {},
    };
    const call = withCallSpy();
    let inst = null;
    try {
        inst = makeBomDialog(row, frm);
    } finally { call.restore(); }
    eq(inst.dlg.opts.title, "Kết quả tính giá",
        "tiêu đề cửa sổ 🖥️ phải là tiếng Việt");
});

check("(16b) renderer kết quả dùng tiêu đề bảng tiếng Việt 'Kết quả tính giá'", () => {
    const row = makeBulkRow({ name: "new-quotation-item-16b", is_new: 1, idx: 1 });
    delete row.al_bom_result;
    const frm = {
        doc: { name: "new-quotation-1", items: [row] },
        dirty() {}, refresh_field() {},
    };
    const call = withCallSpy();
    const inst = makeBomDialog(row, frm);
    try {
        inst.bom.render_results(RESULT_NEW);
    } finally { call.restore(); }

    const html = String(inst.dlg.values["result_html"] || "");
    assert(html.indexOf("Kết quả tính giá") >= 0,
        "bảng kết quả phải có tiêu đề tiếng Việt: " + html.slice(0, 200));
    assert(html.indexOf("BOM Calculation Result") < 0,
        "⛔ được còn tiêu đề tiếng Anh trong bảng kết quả");

    // Nhánh dòng ĐÃ LƯU: render đi qua `frappe.call(get_result_display)` rồi
    // mới dán tiêu đề — phải kiểm RIÊNG, nếu không sửa sót một nhánh vẫn xanh.
    const saved = new quotation.BOMDialog("QTN-ITEM-0016", null, null);
    saved.dialog = new frappe.ui.Dialog({
        fields: [{ fieldname: "result_html", fieldtype: "HTML" }],
    });
    const call2 = withCallSpy((o) => o.callback({
        message: {
            summary: { calculated: true }, lines: [], buckets: [], cost_template: [],
        },
    }));
    try {
        saved.render_results(RESULT_NEW);
    } finally { call2.restore(); }
    const html2 = String(saved.dialog.values["result_html"] || "");
    assert(html2.indexOf("Kết quả tính giá") >= 0,
        "dòng ĐÃ LƯU cũng phải dùng tiêu đề tiếng Việt: " + html2.slice(0, 200));
    assert(html2.indexOf("BOM Calculation Result") < 0,
        "⛔ được còn tiêu đề tiếng Anh ở nhánh dòng đã lưu");
});

check("(16c) quotation.js KHÔNG còn chuỗi 'BOM Calculation Result'", () => {
    const fs = require("fs");
    const src = fs.readFileSync(path.join(
        __dirname, "..", "..", "alumglass", "doctype", "overrides", "quotation.js"),
        "utf8");
    const idx = src.indexOf("BOM Calculation Result");
    assert(idx < 0, "còn chuỗi tiếng Anh tại vị trí " + idx);
});

// ═════════════════════════════════════════════════════════════════════════
// (17) Mở lại dialog "Tham số BOM" phải lấy dòng THẬT (Owner 2026-11-23)
//   Lỗi gặp trên site: dòng đã cập nhật BOM Version nhưng mở lại dialog vẫn
//   thấy version CŨ vì `show()` dò dòng từ `this.frm.doc.items` — khi `frm.doc`
//   là chính DÒNG (form con truyền `frappe.get_doc("Quotation Item", cdn)`)
//   thì `items` không tồn tại ⇒ giữ `child_doc` cũ.
//   `_resolve_row_object()` dò 3 lớp; các ca dưới kiểm từng lớp + ca âm.
// ═════════════════════════════════════════════════════════════════════════
function makeParamDialog(frm, child_doc) {
    const dlg = new quotation.quotation.ItemParamDialog(frm, child_doc);
    // Chỉ kiểm phần CHỌN DÒNG — không dựng dialog thật.
    dlg._render_dialog = function () { dlg.rendered = (dlg.rendered || 0) + 1; };
    return dlg;
}
function withCurFrm(value, fn) {
    const had = Object.prototype.hasOwnProperty.call(global, "cur_frm");
    const old = global.cur_frm;
    if (value === undefined) delete global.cur_frm;
    else global.cur_frm = value;
    try { return fn(); } finally {
        if (had) global.cur_frm = old; else delete global.cur_frm;
    }
}

check("(17a) frm là form báo giá bình thường ⇒ lấy dòng từ frm.doc.items", () => {
    const rowMoi = { doctype: "Quotation Item", name: "QTN-ITEM-17A", idx: 1,
        al_bom_version: "VER-MOI" };
    const banSaoCu = { doctype: "Quotation Item", name: "QTN-ITEM-17A", idx: 1,
        al_bom_version: "VER-CU" };
    const frm = { doc: { doctype: "Quotation", name: "QTN-17A", items: [rowMoi] } };
    const dlg = makeParamDialog(frm, banSaoCu);
    dlg.show();
    assert(dlg.child_doc === rowMoi,
        "phải dùng ĐÚNG object dòng trong frm.doc.items");
    eq(dlg.child_doc.al_bom_version, "VER-MOI", "phải đọc version MỚI");
    eq(dlg.rendered, 1);
});

check("(17b) frm.doc là DÒNG + cur_frm có dòng cùng tên version MỚI ⇒ dùng version MỚI", () => {
    // Đây là ca then chốt: form con truyền chính dòng, `frm.doc.items` KHÔNG có.
    const rowTrenPhieu = { doctype: "Quotation Item", name: "QTN-ITEM-17B", idx: 1,
        al_bom_version: "VER-MOI" };
    const frmCon = { doc: { doctype: "Quotation Item", name: "QTN-ITEM-17B",
        idx: 1, al_bom_version: "VER-CU" } };
    const curFrm = { doc: { doctype: "Quotation", name: "QTN-17B",
        items: [rowTrenPhieu] } };
    const dlg = makeParamDialog(frmCon, frmCon.doc);
    withCurFrm(curFrm, () => dlg.show());
    assert(dlg.child_doc === rowTrenPhieu,
        "phải lấy dòng từ cur_frm.doc.items (lớp 2)");
    eq(dlg.child_doc.al_bom_version, "VER-MOI",
        "dialog phải hiện BOM Version MỚI, ⛔ không phải bản trong locals");
});

check("(17c) chỉ có frm.doc là dòng, KHÔNG có cur_frm ⇒ dùng chính nó", () => {
    const frmCon = { doc: { doctype: "Quotation Item", name: "QTN-ITEM-17C",
        idx: 1, al_bom_version: "VER-MOI" } };
    const dlg = makeParamDialog(frmCon, { doctype: "Quotation Item",
        name: "QTN-ITEM-17C", idx: 1, al_bom_version: "VER-CU" });
    withCurFrm(undefined, () => dlg.show());
    assert(dlg.child_doc === frmCon.doc, "phải dùng chính frm.doc (lớp 3)");
    eq(dlg.child_doc.al_bom_version, "VER-MOI");
});

check("(17d) mở NGOÀI ngữ cảnh báo giá ⇒ giữ child_doc, không ném", () => {
    const childDoc = { doctype: "Quotation Item", name: "QTN-ITEM-17D",
        al_bom_version: "VER-GOC" };
    const frm = { doc: { doctype: "Sales Order", name: "SO-17D" } };
    const dlg = makeParamDialog(frm, childDoc);
    withCurFrm(undefined, () => dlg.show());   // ⛔ không được ném
    assert(dlg.child_doc === childDoc, "phải giữ nguyên object ban đầu");
    eq(dlg.child_doc.al_bom_version, "VER-GOC");
    // `this.frm.doc` là dòng nhưng TÊN KHÁC `child_doc.name` → ⛔ nhận nhầm
    const frmKhac = { doc: { doctype: "Quotation Item", name: "QTN-ITEM-KHAC" } };
    const child2 = { doctype: "Quotation Item", name: "QTN-ITEM-17D",
        al_bom_version: "VER-GOC" };
    const dlg2 = makeParamDialog(frmKhac, child2);
    withCurFrm(undefined, () => dlg2.show());
    assert(dlg2.child_doc === child2, "tên khác ⇒ ⛔ được nhận dòng khác");
});

check("(17e) dấu phiên bản alumglass.__build__ tồn tại (kiểm nhanh trên site)", () => {
    assert(typeof quotation.__build__ === "string", "__build__ phải là chuỗi");
    assert(quotation.__build__.trim().length > 0, "__build__ ⛔ được rỗng");
});

check("(17f) dòng mới đã lưu: tên đổi new-… → tên thật, mở lại dò ĐÚNG tên", () => {
    // Sau khi Lưu, `frm.doc.items` mang tên thật; object dialog còn `new-…`.
    const rowThat = { doctype: "Quotation Item", name: "QTN-ITEM-17F", idx: 1,
        al_bom_version: "VER-MOI" };
    const childCu = { doctype: "Quotation Item",
        name: "new-quotation-item-17f", idx: 1, al_bom_version: "VER-CU" };
    const frm = { doc: { doctype: "Quotation", name: "QTN-17F", items: [rowThat] } };
    const dlg = makeParamDialog(frm, childCu);
    dlg.show();
    eq(childCu.name, "QTN-ITEM-17F",
        "child_doc.name phải được đồng bộ sang tên thật để lần sau dò theo tên");
    assert(dlg.child_doc === rowThat);
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

(async () => {
    for (const c of asyncChecks) {
        try {
            await c.fn();
            passed += 1;
            console.log("  PASS  " + c.name);
        } catch (err) {
            failed.push(c.name);
            console.log("  FAIL  " + c.name);
            console.log("        " + (err && err.message ? err.message : err));
        }
    }
    printSummary();
})();
