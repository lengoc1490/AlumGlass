#!/usr/bin/env node
/**
 * Test Node thuần: TỆP CHUNG giữ FORM DÒNG CON mở khi đóng hộp thoại.
 *
 * KHÔNG cần site, KHÔNG cần npm — chạy:
 *     node alumglass/tests/js/test_dialog_keep_grid_form.js
 *
 * ── VẤN ĐỀ (Owner 2026-11-26)
 * Frappe **v16** `frappe/public/js/frappe/ui/dialog.js` (nhánh `version-16`),
 * handler `hide.bs.modal`:
 *
 *     if (!me.keep_grid_form_open) {
 *         frappe.ui.form.get_open_grid_form?.()?.hide_form();
 *     }
 *
 * ⇒ Mở form dòng con (AL Bom Item / AL Accessory Item…), mở hộp tra cứu, đóng
 * hộp ⇒ form dòng bị đóng theo. v14 không có cờ này (`$.extend` bỏ qua khoá
 * lạ) nên thêm cờ là vô hại trên cả 2 phiên bản.
 *
 * ── CÁCH XỬ LÝ (Owner đổi hướng: MỘT chỗ cho toàn app, ⛔ từng doctype)
 * `alumglass/public/js/dialog_keep_grid_form.js` bọc `frappe.ui.Dialog` một
 * lần, nạp qua `app_include_js` (hooks.py, ĐẦU danh sách). Test này kiểm:
 *
 *   (a) nạp tệp chung ⇒ hộp KHÔNG truyền cờ vẫn giữ form dòng khi đóng
 *   (b) `keep_grid_form_open: false` ⇒ tôn trọng lựa chọn tường minh (vẫn đóng)
 *   (c) nạp tệp 2 lần ⇒ ⛔ bọc 2 lớp (class giữ nguyên, cờ vẫn đúng)
 *   (d) `frappe.ui.Dialog` kiểu v14 (không dùng cờ) ⇒ nạp không lỗi,
 *       `instanceof`/`show` vẫn chạy
 *   (e) ĐỐI CHỨNG ÂM — KHÔNG nạp tệp chung ⇒ đóng hộp ĐÓNG form dòng
 *       (chứng minh phép kiểm bắt được hành vi thật)
 *   (f) TĨNH — hooks.py đăng ký tệp chung, ĐỨNG ĐẦU `app_include_js`, tệp
 *       tồn tại, và ⛔ còn cờ rải rác trong script từng doctype.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP_DIR = path.join(__dirname, "..", "..");
const SHARED_JS = path.join(APP_DIR, "public", "js", "dialog_keep_grid_form.js");
const HOOKS_PY = path.join(APP_DIR, "hooks.py");
const RULE_HELPER_JS = path.join(APP_DIR, "public", "js", "rule_helper.js");
const QUOTATION_JS = path.join(
    APP_DIR, "alumglass", "doctype", "overrides", "quotation.js");
const SHARED_URL = "/assets/alumglass/js/dialog_keep_grid_form.js";

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
// Stub môi trường: `frappe.ui.Dialog` + form dòng con đang mở
// ═══════════════════════════════════════════════════════════════════════════

/** Form dòng con đang mở — đếm số lần bị đóng (`get_open_grid_form()`). */
const gridFormSpy = {
    hideCalls: 0,
    hide_form() { this.hideCalls += 1; },
};

/**
 * Bắt chước ĐÚNG handler `hide.bs.modal` của Frappe v16
 * (`frappe/public/js/frappe/ui/dialog.js`).
 */
function applyV16HideBehaviour(opts) {
    if (!(opts && opts.keep_grid_form_open)) {
        const gridForm = typeof frappe.ui.form.get_open_grid_form === "function"
            ? frappe.ui.form.get_open_grid_form()
            : null;
        if (gridForm && typeof gridForm.hide_form === "function") gridForm.hide_form();
    }
}

/**
 * `frappe.ui.Dialog` giả. Dùng FUNCTION CONSTRUCTOR (kiểu ES5) chứ không phải
 * `class` — đúng dạng Frappe cũ, và kiểm luôn việc `class extends` của tệp
 * chung bọc được constructor không phải class.
 *
 * `version`:
 *   · "v16" — `hide()` gọi `get_open_grid_form().hide_form()` khi thiếu cờ.
 *   · "v14" — `hide()` không đụng gì (`$.extend` bỏ qua cờ lạ).
 */
function makeDialogClass(version) {
    function Dialog(opts) {
        // v14/v16 đều `$.extend(this, {...mặc định}, opts)` ⇒ chép opts lên this.
        this.opts = Object.assign({}, opts || {});
        Object.assign(this, this.opts);
        this.showCalls = 0;
        this.hideCalls = 0;
    }
    Dialog.prototype.show = function () {
        this.showCalls += 1;
        return this;
    };
    Dialog.prototype.hide = function () {
        this.hideCalls += 1;
        if (version === "v16") applyV16HideBehaviour(this.opts);
        return this;
    };
    Dialog.prototype.set_title = function () { return this; };
    return Dialog;
}

/** Dựng `global.frappe` mới (mỗi kịch bản độc lập) + reset bộ đếm. */
function setupFrappe(version) {
    gridFormSpy.hideCalls = 0;
    global.frappe = {
        ui: {
            Dialog: makeDialogClass(version),
            form: {
                get_open_grid_form() { return gridFormSpy; },
            },
        },
    };
    return global.frappe.ui.Dialog;
}

/** Nạp `dialog_keep_grid_form.js` y như trình duyệt nạp asset. */
function loadShared() {
    const code = fs.readFileSync(SHARED_JS, "utf8");
    vm.runInThisContext(code, { filename: SHARED_JS });
}

/** Phép kiểm dùng chung cho (a) — tách ra để ĐỐI CHỨNG ÂM gọi lại được. */
function assertDialogKeepsGridForm(label) {
    const dlg = new frappe.ui.Dialog({ title: label });
    dlg.show();
    dlg.hide();
    assert(gridFormSpy.hideCalls === 0,
        label + ": đóng hộp đã gọi `get_open_grid_form().hide_form()` ⇒ "
        + "FORM DÒNG CON BỊ ĐÓNG (tệp chung chưa nạp / bọc hỏng)");
    assert(dlg.opts.keep_grid_form_open === true,
        label + ": opts tới Dialog gốc phải có `keep_grid_form_open: true`, "
        + "thực tế " + JSON.stringify(dlg.opts));
}

// ═══════════════════════════════════════════════════════════════════════════
// (a) Nạp tệp chung ⇒ hộp mặc định giữ form dòng
// ═══════════════════════════════════════════════════════════════════════════
check("(a) nạp tệp chung ⇒ `new frappe.ui.Dialog({})` + hide GIỮ form dòng", function () {
    setupFrappe("v16");
    loadShared();
    assertDialogKeepsGridForm("Chọn công thức");
    assert(gridFormSpy.hideCalls === 0, "form dòng bị đóng");
});

check("(a2) nạp tệp chung ⇒ hộp CÓ truyền opts khác vẫn giữ nguyên opts đó", function () {
    setupFrappe("v16");
    loadShared();
    const dlg = new frappe.ui.Dialog({ title: "Thử tra quy tắc", size: "large" });
    assert(dlg.opts.title === "Thử tra quy tắc", "title bị mất");
    assert(dlg.opts.size === "large", "size bị mất");
    assert(dlg.opts.keep_grid_form_open === true, "thiếu cờ mặc định");
});

// ═══════════════════════════════════════════════════════════════════════════
// (b) Lựa chọn tường minh `false` phải được tôn trọng
// ═══════════════════════════════════════════════════════════════════════════
check("(b) `keep_grid_form_open: false` ⇒ hide ĐÓNG form dòng (tôn trọng tường minh)", function () {
    setupFrappe("v16");
    loadShared();
    const dlg = new frappe.ui.Dialog({ title: "hộp muốn đóng dòng", keep_grid_form_open: false });
    dlg.hide();
    assert(gridFormSpy.hideCalls === 1,
        "lựa chọn `false` bị ghi đè — hide_form gọi " + gridFormSpy.hideCalls + " lần (mong đợi 1)");
});

// ═══════════════════════════════════════════════════════════════════════════
// (c) Idempotent — nạp 2 lần không bọc 2 lớp
// ═══════════════════════════════════════════════════════════════════════════
check("(c) nạp tệp 2 lần ⇒ ⛔ bọc 2 lớp, hành vi vẫn đúng", function () {
    setupFrappe("v16");
    loadShared();
    const wrapped = frappe.ui.Dialog;
    loadShared();
    assert(frappe.ui.Dialog === wrapped,
        "nạp lần 2 đã bọc lại `frappe.ui.Dialog` (class đổi) ⇒ sẽ chồng lớp");
    assert(frappe.ui.Dialog.__alKeepGridForm === true,
        "thiếu dấu idempotent `__alKeepGridForm`");
    // Hành vi sau lần nạp thứ 2 vẫn đúng.
    assertDialogKeepsGridForm("sau khi nạp 2 lần");
    // Và cờ chỉ được điền 1 lần, đúng giá trị.
    const dlg = new frappe.ui.Dialog({});
    assert(dlg.opts.keep_grid_form_open === true, "cờ sai sau khi nạp 2 lần");
});

check("(c2) ĐỐI CHỨNG ÂM — bọc chồng THẬT thì phép kiểm (c) phải bắt được", function () {
    setupFrappe("v16");
    loadShared();
    const wrapped = frappe.ui.Dialog;
    // Mô phỏng bản hỏng: bỏ dấu idempotent rồi nạp lại ⇒ bọc chồng.
    wrapped.__alKeepGridForm = false;
    loadShared();
    assert(frappe.ui.Dialog !== wrapped, "bản hỏng không bọc lại được ⇒ đối chứng vô nghĩa");
});

// ═══════════════════════════════════════════════════════════════════════════
// (d) Frappe v14 — Dialog không dùng cờ, nạp tệp chung không được làm vỡ
// ═══════════════════════════════════════════════════════════════════════════
check("(d) Dialog kiểu v14 ⇒ nạp không lỗi, instanceof/show vẫn chạy", function () {
    const Original = setupFrappe("v14");
    loadShared(); // ⛔ được ném lỗi
    const dlg = new frappe.ui.Dialog({ title: "hộp v14" });
    assert(dlg instanceof frappe.ui.Dialog, "mất instanceof class đã bọc");
    assert(dlg instanceof Original, "mất instanceof Dialog gốc (class extends hỏng)");
    assert(typeof dlg.show === "function" && typeof dlg.hide === "function",
        "mất phương thức show/hide của Dialog gốc");
    dlg.show();
    assert(dlg.showCalls === 1, "show() không chạy");
    dlg.hide();
    // v14 không có handler đóng form dòng ⇒ dù cờ có hay không, không đóng.
    assert(gridFormSpy.hideCalls === 0, "v14 không được đóng form dòng");
    assert(dlg.keep_grid_form_open === true,
        "v14 vẫn nhận cờ như một thuộc tính lạ vô hại (không được ném lỗi)");
});

// ═══════════════════════════════════════════════════════════════════════════
// (e) ĐỐI CHỨNG ÂM — không nạp tệp chung thì form dòng BỊ ĐÓNG
// ═══════════════════════════════════════════════════════════════════════════
check("(e) ĐỐI CHỨNG ÂM — KHÔNG nạp tệp chung ⇒ hide ĐÓNG form dòng", function () {
    setupFrappe("v16");
    // ⛔ KHÔNG gọi loadShared()
    const dlg = new frappe.ui.Dialog({ title: "hộp chưa được bọc" });
    dlg.hide();
    assert(gridFormSpy.hideCalls === 1,
        "không nạp tệp chung mà form dòng KHÔNG bị đóng ⇒ stub sai, phép kiểm (a) "
        + "sẽ xanh giả. hide_form gọi " + gridFormSpy.hideCalls + " lần (mong đợi 1)");
});

check("(e2) ĐỐI CHỨNG ÂM — chạy đúng phép kiểm (a) khi CHƯA nạp tệp ⇒ phải báo đỏ", function () {
    setupFrappe("v16");
    mustFail(function () {
        assertDialogKeepsGridForm("chưa nạp tệp chung");
    }, "assertDialogKeepsGridForm không phát hiện hộp chưa được bọc");
});

// ═══════════════════════════════════════════════════════════════════════════
// (f) QUÉT TĨNH — đăng ký trong hooks.py + tệp tồn tại + ⛔ cờ rải rác
// ═══════════════════════════════════════════════════════════════════════════

/** Danh sách đường dẫn JS khai trong `app_include_js` (đúng thứ tự nạp). */
function appIncludeJsPaths(hooksSource) {
    const start = hooksSource.indexOf("app_include_js");
    assert(start >= 0, "hooks.py không có `app_include_js`");
    const open = hooksSource.indexOf("[", start);
    assert(open >= 0, "`app_include_js` không mở bằng `[`");
    const close = hooksSource.indexOf("\n]", open);
    const block = close < 0 ? hooksSource.slice(open) : hooksSource.slice(open, close);
    // Bỏ comment Python (dòng `# ...`) trước khi bóc chuỗi: comment trong danh
    // sách có nhắc `"AL Bom Item"/"AL Accessory Item"` ⇒ bóc thô sẽ bắt nhầm
    // một "đường dẫn" rác và làm thứ tự sai.
    const code = block.split("\n").map(function (line) {
        return line.replace(/#.*$/, "");
    }).join("\n");
    const paths = [];
    const re = /"(\/assets\/[^"]+\.js[^"]*)"/g;
    let match;
    while ((match = re.exec(code)) !== null) paths.push(match[1]);
    return paths;
}

check("(f1) hooks.py đăng ký tệp chung trong `app_include_js` (có ?v=)", function () {
    const hooks = fs.readFileSync(HOOKS_PY, "utf8");
    const paths = appIncludeJsPaths(hooks);
    assert(paths.some(function (p) { return p.indexOf(SHARED_URL) === 0; }),
        "không thấy `" + SHARED_URL + "` trong app_include_js; có: "
        + JSON.stringify(paths));
    const entry = paths.filter(function (p) { return p.indexOf(SHARED_URL) === 0; })[0];
    assert(/^\/assets\/alumglass\/js\/dialog_keep_grid_form\.js\?v=\d+\.\d+\.\d+$/.test(entry),
        "đường dẫn phải kèm `?v=x.y.z` để phá cache, thực tế: " + entry);
});

check("(f2) tệp chung ĐỨNG ĐẦU `app_include_js` (nạp trước mọi JS tạo hộp thoại)", function () {
    const paths = appIncludeJsPaths(fs.readFileSync(HOOKS_PY, "utf8"));
    assert(paths.length > 0, "app_include_js rỗng");
    assert(paths[0].indexOf(SHARED_URL) === 0,
        "phần tử đầu phải là tệp chung, thực tế: " + paths[0]);
});

check("(f3) tệp chung TỒN TẠI và có đủ guard + idempotent + cờ", function () {
    assert(fs.existsSync(SHARED_JS), "không thấy tệp " + SHARED_JS);
    const src = fs.readFileSync(SHARED_JS, "utf8");
    assert(/typeof frappe === "undefined"/.test(src), "thiếu guard `typeof frappe`");
    assert(/frappe\.ui\.Dialog\s*=\s*AlumGlassDialog/.test(src),
        "không gán lại `frappe.ui.Dialog`");
    assert(/__alKeepGridForm/.test(src), "thiếu dấu idempotent `__alKeepGridForm`");
    assert(/keep_grid_form_open/.test(src), "tệp chung không nhắc `keep_grid_form_open`");
    assert(/get_open_grid_form/.test(src),
        "thiếu dẫn chứng nguyên nhân (`get_open_grid_form`)");
});

check("(f4) ⛔ cờ KHÔNG còn rải rác trong script từng doctype", function () {
    const leaks = [];
    [RULE_HELPER_JS, QUOTATION_JS].forEach(function (file) {
        const src = fs.readFileSync(file, "utf8");
        src.split("\n").forEach(function (line, idx) {
            if (/keep_grid_form_open/.test(line)) {
                leaks.push(path.relative(APP_DIR, file) + ":" + (idx + 1) + " — " + line.trim());
            }
        });
    });
    assert(leaks.length === 0,
        "còn cờ lẻ (Owner đổi hướng: làm 1 tệp chung, ⛔ từng doctype):\n  "
        + leaks.join("\n  "));
});

// ═══════════════════════════════════════════════════════════════════════════
// Tổng kết
// ═══════════════════════════════════════════════════════════════════════════
console.log("");
console.log("── Tổng kết ──────────────────────────────────────────────");
console.log("  xanh: " + passed + " · đỏ: " + failed.length);
if (failed.length) {
    failed.forEach(function (name) { console.log("  ✗ " + name); });
    process.exit(1);
}
console.log("  OK — tệp chung giữ form dòng con mở trên Frappe v16, vô hại trên v14.");
