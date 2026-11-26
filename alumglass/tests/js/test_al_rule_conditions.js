#!/usr/bin/env node
/**
 * Test Node thuần cho phần điều kiện tra của
 * alumglass/al_formula_rules/doctype/al_rule/al_rule.js
 *
 * KHÔNG cần site, KHÔNG cần npm/cài package — chạy:
 *     node alumglass/tests/js/test_al_rule_conditions.js
 *
 * Bối cảnh (Owner, 2026-11-25): "Khi chọn nẹp theo độ dày kính thì phải
 * chuyển danh sách các điều kiện tra ra kính lên gần chỗ rule". Bảng điều kiện
 * nằm ngay dưới ô "Tra theo", nhãn cột đổi theo dữ liệu đang tra. Tệp này phủ
 * phần THUẦN (không DOM, không frappe):
 *   1. findGaps             — khe hở giữa các dải ngưỡng
 *   2. findOverlaps         — dải chồng lấn (chạm biên KHÔNG tính)
 *   3. summarizeThresholds  — số điều kiện + phạm vi đang phủ
 *   4. conditionRecap       — "0–10 mm → Nẹp 10"
 *   5. columnLabels         — nhãn cột theo dữ liệu + cột kết quả bị ẩn
 *   6. findDuplicateKeys    — giá trị cần tra bị lặp
 *
 * Mỗi nhóm có ĐỐI CHỨNG ÂM: dựng một bản CỐ TÌNH HỎNG, chạy đúng bộ kiểm của
 * nhóm đó, và đòi bộ kiểm PHẢI báo đỏ — "xanh" ở trên mới là xanh thật.
 */
"use strict";

const path = require("path");

// `__()` của Desk — map 1:1 để chuỗi test khớp chuỗi hiển thị.
global.__ = function (text) { return String(text); };
// Desk có `window`; nạp trước để kiểm đúng đường xuất `window.AlumGlassRuleConditions`.
global.window = {};

const MODULE_PATH = path.join(
    __dirname, "..", "..", "al_formula_rules", "doctype", "al_rule", "al_rule.js");
const exported = require(MODULE_PATH);
const conditions = global.window.AlumGlassRuleConditions;

// Bản helper dùng chung (nạp toàn trang trên Desk) — để kiểm `al_rule.js` uỷ
// quyền cho nó ra Y HỆT bản dự phòng.
const helperApi = require(path.join(
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

const DASH = "–";
const GE = "≥"; // ≥

// ═══════════════════════════════════════════════════════════════════════════
// 0. Xuất hàm thuần
// ═══════════════════════════════════════════════════════════════════════════
check("xuất qua window.AlumGlassRuleConditions + module.exports", () => {
    assert(conditions && typeof conditions === "object", "thiếu window.AlumGlassRuleConditions");
    assert(conditions === exported, "module.exports khác window.AlumGlassRuleConditions");
    ["findGaps", "findOverlaps", "summarizeThresholds", "conditionRecap",
        "columnLabels", "findDuplicateKeys"].forEach((name) => {
        assert(typeof conditions[name] === "function", "thiếu hàm " + name);
    });
});

// ═══════════════════════════════════════════════════════════════════════════
// 1. findGaps — khe hở
// ═══════════════════════════════════════════════════════════════════════════
function testFindGaps(api) {
    // Bảng rỗng: câu "chưa có điều kiện" lo riêng, findGaps không báo khe.
    eq(api.findGaps([]), [], "bảng rỗng ⇒ không khe");
    eq(api.findGaps(undefined), [], "undefined ⇒ không khe");

    // Chạm biên là LIỀN nhau (quy ước [from, to)).
    eq(api.findGaps([
        { from_value: 0, to_value: 10 },
        { from_value: 10, to_value: 20 },
    ]), [], "0–10 + 10–20 ⇒ KHÔNG trống");

    eq(api.findGaps([
        { from_value: 0, to_value: 10 },
        { from_value: 20, to_value: 30 },
    ]), [{ from: 10, to: 20 }], "0–10 + 20–30 ⇒ trống 10–20");

    // Dải đầu không bắt đầu từ 0 ⇒ trống phía dưới.
    eq(api.findGaps([{ from_value: 5, to_value: 10 }]),
        [{ from: 0, to: 5 }], "bắt đầu từ 5 ⇒ trống 0–5");

    // "Đến" bỏ trống = trở lên ⇒ không trống phía trên.
    eq(api.findGaps([
        { from_value: 0, to_value: 10 },
        { from_value: 10, to_value: null },
    ]), [], "dải trên bỏ trống 'Đến' ⇒ không trống phía trên");
    eq(api.findGaps([{ from_value: 0, to_value: "" }]), [],
        "'Đến' chuỗi rỗng ⇒ trở lên, không trống");

    // Một dải 0–∞.
    eq(api.findGaps([{ from_value: 0, to_value: null }]), [],
        "một dải 0–∞ ⇒ không trống");

    // Thứ tự dòng đảo + giá trị dạng chuỗi (dữ liệu form) vẫn đúng.
    eq(api.findGaps([
        { from_value: "20", to_value: "30" },
        { from_value: "0", to_value: "10" },
    ]), [{ from: 10, to: 20 }], "phải sắp theo 'Từ' và nhận chuỗi");

    // Dòng thiếu "Từ" không xếp được vào trục ⇒ bỏ qua, ⛔ bịa khe.
    eq(api.findGaps([
        { from_value: null, to_value: 10 },
        { from_value: 0, to_value: 10 },
    ]), [], "dòng thiếu 'Từ' ⇒ bỏ qua");

    // Nhiều khe: 0–10, 15–20, 30–∞.
    eq(api.findGaps([
        { from_value: 0, to_value: 10 },
        { from_value: 15, to_value: 20 },
        { from_value: 30, to_value: null },
    ]), [{ from: 10, to: 15 }, { from: 20, to: 30 }], "hai khe liên tiếp");

    // Dải chồng lấn phủ rộng hơn ⇒ mốc phủ phải là mép XA nhất.
    eq(api.findGaps([
        { from_value: 0, to_value: 30 },
        { from_value: 10, to_value: 20 },
        { from_value: 40, to_value: 50 },
    ]), [{ from: 30, to: 40 }], "dải lồng nhau không được bịa khe 20–30");
}

check("findGaps — rỗng / liền / khe / đầu > 0 / trở lên / sắp xếp", () => {
    testFindGaps(conditions);
});

check("ĐỐI CHỨNG ÂM — findGaps", () => {
    // Bản hỏng: coi chạm biên là khe (dùng >=) và bỏ khe phía dưới.
    const broken = {
        findGaps(rows) {
            const list = (rows || []).map((row) => ({
                from: Number(row.from_value),
                to: (row.to_value === "" || row.to_value === null) ? Infinity : Number(row.to_value),
            })).sort((a, b) => a.from - b.from);
            const gaps = [];
            for (let i = 0; i < list.length - 1; i++) {
                if (list[i].to >= list[i + 1].from) {
                    gaps.push({ from: list[i].to, to: list[i + 1].from });
                }
            }
            return gaps;
        },
    };
    mustFail(() => testFindGaps(broken), "coi chạm biên là khe");
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. findOverlaps — dải chồng lấn
// ═══════════════════════════════════════════════════════════════════════════
function testFindOverlaps(api) {
    eq(api.findOverlaps([]), [], "bảng rỗng ⇒ không chồng");

    const overlap = api.findOverlaps([
        { from_value: 10, to_value: 20 },
        { from_value: 15, to_value: 25 },
    ]);
    eq(overlap.length, 1, "10–20 + 15–25 ⇒ phải báo chồng");
    eq(overlap[0].first, { from: 10, to: 20 }, "cặp thứ nhất");
    eq(overlap[0].second, { from: 15, to: 25 }, "cặp thứ hai");

    eq(api.findOverlaps([
        { from_value: 10, to_value: 20 },
        { from_value: 20, to_value: 30 },
    ]), [], "chạm biên 20 ⇒ KHÔNG chồng");

    eq(api.findOverlaps([{ from_value: 10, to_value: 20 }]), [],
        "một dòng ⇒ không chồng");

    eq(api.findOverlaps([
        { from_value: 0, to_value: 10 },
        { from_value: 10, to_value: 20 },
        { from_value: 20, to_value: 30 },
    ]), [], "ba dải liền nhau ⇒ không chồng");

    // Thứ tự dòng đảo vẫn phải phát hiện.
    eq(api.findOverlaps([
        { from_value: 15, to_value: 25 },
        { from_value: 10, to_value: 20 },
    ]).length, 1, "dòng đảo thứ tự vẫn phải báo chồng");

    // Dải mở tới trên cùng chồng lên mọi dải phía sau.
    eq(api.findOverlaps([
        { from_value: 0, to_value: null },
        { from_value: 10, to_value: 20 },
    ]).length, 1, "dải 'trở lên' chồng lên dải khác");

    // Một dải rộng lồng hai dải nhỏ ⇒ mỗi dải nhỏ một cặp.
    eq(api.findOverlaps([
        { from_value: 0, to_value: 100 },
        { from_value: 10, to_value: 20 },
        { from_value: 30, to_value: 40 },
    ]).length, 2, "dải rộng lồng hai dải nhỏ ⇒ hai cặp");
}

check("findOverlaps — chồng thật / chạm biên / một dòng / dải mở", () => {
    testFindOverlaps(conditions);
});

check("ĐỐI CHỨNG ÂM — findOverlaps", () => {
    // Bản hỏng: coi chạm biên là chồng lấn (dùng >=).
    const broken = {
        findOverlaps(rows) {
            const list = (rows || []).map((row) => ({
                from: Number(row.from_value),
                to: (row.to_value === "" || row.to_value === null) ? Infinity : Number(row.to_value),
            })).sort((a, b) => a.from - b.from);
            const overlaps = [];
            for (let i = 0; i < list.length - 1; i++) {
                if (list[i].to >= list[i + 1].from) {
                    overlaps.push({ first: list[i], second: list[i + 1] });
                }
            }
            return overlaps;
        },
    };
    mustFail(() => testFindOverlaps(broken), "coi chạm biên là chồng lấn");
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. summarizeThresholds — thống kê nhanh
// ═══════════════════════════════════════════════════════════════════════════
function testSummarize(api) {
    eq(api.summarizeThresholds([], "mm"), {
        count: 0, from: null, to: null, openEnded: false, rangeText: "",
    }, "bảng rỗng");

    eq(api.summarizeThresholds([
        { from_value: 0, to_value: 10 },
        { from_value: 10, to_value: 30 },
    ], "mm"), {
        count: 2, from: 0, to: 30, openEnded: false,
        rangeText: "0" + DASH + "30 mm",
    }, "phủ 0–30, hai điều kiện, không trở lên");

    eq(api.summarizeThresholds([
        { from_value: 20, to_value: null },
    ], "mm"), {
        count: 1, from: 20, to: null, openEnded: true,
        rangeText: "20 mm trở lên",
    }, "'Đến' bỏ trống ⇒ trở lên");

    eq(api.summarizeThresholds([
        { from_value: 0, to_value: 10 },
        { from_value: 30, to_value: null },
    ], ""), {
        count: 2, from: 0, to: 10, openEnded: true,
        rangeText: "0 trở lên",
    }, "không đơn vị + có dải trở lên");

    eq(api.summarizeThresholds([
        { from_value: "10,5", to_value: "20" },
    ], "mm").rangeText, "10,5" + DASH + "20 mm", "nhận số thập phân dấu phẩy");
}

check("summarizeThresholds — phủ 0–30 / số điều kiện / trở lên / đơn vị", () => {
    testSummarize(conditions);
});

check("ĐỐI CHỨNG ÂM — summarizeThresholds", () => {
    // Bản hỏng: không biết "trở lên", cộng cả dòng thiếu "Từ", không ghép đơn vị.
    const broken = {
        summarizeThresholds(rows, unit) {
            const list = rows || [];
            let from = null;
            let to = null;
            list.forEach((row) => {
                const value = Number(row.from_value);
                if (from === null || value < from) from = value;
                if (to === null || Number(row.to_value) > to) to = Number(row.to_value);
            });
            return {
                count: list.length,
                from: from,
                to: to,
                openEnded: false,
                rangeText: from + DASH + to + " " + (unit || ""),
            };
        },
    };
    mustFail(() => testSummarize(broken), "bỏ qua dải 'trở lên'");
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. conditionRecap — đọc từng dòng thành câu
// ═══════════════════════════════════════════════════════════════════════════
function testRecap(api) {
    eq(api.conditionRecap([], { unit: "mm" }), [], "bảng rỗng ⇒ không câu");
    eq(api.conditionRecap(undefined, {}), [], "undefined ⇒ không câu");

    eq(api.conditionRecap([
        { from_value: 0, to_value: 10, result_item: "NEP-10" },
        { from_value: 20, to_value: null, result_item: "NEP-30" },
    ], { unit: "mm", resultType: "ITEM" }), [
        "0" + DASH + "10 mm → NEP-10",
        GE + " 20 mm → NEP-30",
    ], "ITEM: đơn vị + dải 'trở lên' dùng ≥");

    eq(api.conditionRecap([
        { from_value: 0, to_value: 10, result_value: 2 },
    ], { unit: "mm", resultType: "NUMBER" }),
    ["0" + DASH + "10 mm → 2"], "NUMBER: đọc cột số");

    eq(api.conditionRecap([
        { from_value: 0, to_value: 10, result_item: "C1", result_item_name: "Nẹp nhôm 10" },
    ], { resultType: "ITEM" }),
    ["0" + DASH + "10 → Nẹp nhôm 10"],
    "ITEM có tên vật tư ⇒ hiện tên, ⛔ hiện mã thô");

    eq(api.conditionRecap([
        { from_value: 0, to_value: 10, result_item: "" },
    ], { resultType: "ITEM", resultLabel: "Mã nẹp" }),
    ["0" + DASH + "10 → chưa có mã nẹp"], "thiếu kết quả ⇒ câu nhắc điền");

    eq(api.conditionRecap([
        { from_value: 10.5, to_value: 20, result_value: 0.5 },
    ], { unit: "mm", resultType: "NUMBER" }),
    ["10,5" + DASH + "20 mm → 0,5"], "số thập phân hiện dấu phẩy");

    // Dòng tra bảng: khoá đứng trước mũi tên.
    eq(api.conditionRecap([
        { key_field: "LOWE", result_item: "K-LOWE" },
        { key_field: "  ", result_item: "K-BO" },
    ], { resultType: "ITEM" }), ["LOWE → K-LOWE"], "khoá rỗng ⇒ bỏ dòng");

    // Dòng ngưỡng thiếu "Từ" ⇒ không đọc được ⇒ bỏ, ⛔ bịa câu.
    eq(api.conditionRecap([
        { from_value: null, to_value: 10, result_value: 1 },
    ], { resultType: "NUMBER" }), [], "thiếu 'Từ' ⇒ bỏ dòng");
}

check("conditionRecap — mm / trở lên dùng ≥ / ITEM / tên vật tư / tra bảng", () => {
    testRecap(conditions);
});

check("ĐỐI CHỨNG ÂM — conditionRecap", () => {
    // Bản hỏng: quên đơn vị, không có dạng "≥", dùng nhầm cột kết quả cho ITEM.
    const broken = {
        conditionRecap(rows, opts) {
            return (rows || []).map((row) => {
                const from = Number(row.from_value);
                const to = (row.to_value === "" || row.to_value === null)
                    ? null : Number(row.to_value);
                const when = from + DASH + (to === null ? "∞" : to);
                return when + " → " + (row.result_value || row.result_item || "");
            });
        },
    };
    mustFail(() => testRecap(broken), "mất đơn vị + sai cột kết quả");
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. columnLabels — nhãn cột theo dữ liệu đang tra
// ═══════════════════════════════════════════════════════════════════════════
function testColumnLabels(api) {
    const withLabel = api.columnLabels("Độ dày kính", "Mã nẹp", "ITEM", "THRESHOLD");
    eq(withLabel.labels.from_value, "Từ (Độ dày kính)", "cột 'Từ' mang nhãn dữ liệu");
    eq(withLabel.labels.to_value,
        "Đến (Độ dày kính) " + DASH + " bỏ trống = trở lên",
        "cột 'Đến' mang nhãn dữ liệu");
    eq(withLabel.labels.result_value, "Kết quả: Mã nẹp", "cột kết quả theo 'Kết quả trả về'");
    eq(withLabel.labels.result_item, "Kết quả: Mã nẹp", "cột mã vật tư cùng nhãn kết quả");
    eq(withLabel.hidden, { result_value: true, result_item: false },
        "ITEM ⇒ ẩn cột số");

    const noLabel = api.columnLabels("", "", "NUMBER", "THRESHOLD");
    eq(noLabel.labels.from_value, "Từ", "thiếu nhãn ⇒ 'Từ'");
    eq(noLabel.labels.to_value, "Đến " + DASH + " bỏ trống = trở lên",
        "thiếu nhãn ⇒ 'Đến'");
    eq(noLabel.labels.result_value, "Kết quả: số", "thiếu 'Kết quả trả về' ⇒ 'Kết quả: số'");
    eq(noLabel.hidden, { result_value: false, result_item: true },
        "NUMBER ⇒ ẩn cột mã vật tư");

    const lookup = api.columnLabels("Độ dày kính", "Mã keo", "ITEM", "LOOKUP");
    eq(lookup.labels.key_field, "Giá trị (Độ dày kính)", "LOOKUP: cột khoá mang nhãn dữ liệu");
    assert(lookup.labels.from_value === undefined, "LOOKUP ⛔ có cột 'Từ'");
    eq(lookup.hidden, { result_value: true, result_item: false }, "LOOKUP ITEM ⇒ ẩn cột số");

    const lookupNoLabel = api.columnLabels("", "", "NUMBER", "LOOKUP");
    eq(lookupNoLabel.labels.key_field, "Giá trị", "LOOKUP thiếu nhãn ⇒ 'Giá trị'");

    // UX1 vòng 4 — dữ liệu CŨ đã lưu `input_label = total_thick_mm`: nhãn
    // TRÙNG tên biến ⇒ "dữ liệu quy tắc đọc", ⛔ nhét mã biến vào tiêu đề cột.
    const sameAsVar = api.columnLabels(
        "total_thick_mm", "", "NUMBER", "THRESHOLD", "total_thick_mm");
    eq(sameAsVar.labels.from_value, "Từ (dữ liệu quy tắc đọc)",
        "nhãn trùng tên biến ⛔ lọt vào tiêu đề cột");
    eq(sameAsVar.labels.to_value,
        "Đến (dữ liệu quy tắc đọc) " + DASH + " bỏ trống = trở lên",
        "cột 'Đến' cũng phải làm sạch");
    eq(api.columnLabels("  Total_Thick_MM ", "", "NUMBER", "THRESHOLD", "total_thick_mm")
        .labels.from_value, "Từ (dữ liệu quy tắc đọc)",
        "trùng khác hoa/thường + khoảng trắng vẫn phải làm sạch");
    // Nhãn thật + biến khác ⇒ giữ nguyên.
    eq(api.columnLabels("Độ dày kính", "", "NUMBER", "THRESHOLD", "total_thick_mm")
        .labels.from_value, "Từ (Độ dày kính)", "nhãn thật giữ nguyên");

    // Dữ liệu chưa khai gì ⇒ mặc định NUMBER, không vỡ.
    const empty = api.columnLabels(undefined, undefined, undefined, undefined);
    eq(empty.labels.from_value, "Từ", "chưa chọn loại ⇒ cột ngưỡng");
    eq(empty.hidden.result_item, true, "chưa có result_type ⇒ coi như NUMBER");
}

check("columnLabels — nhãn động / fallback / ITEM ẩn số / NUMBER ẩn mã", () => {
    testColumnLabels(conditions);
});

check("ĐỐI CHỨNG ÂM — columnLabels", () => {
    // Bản hỏng: nhãn cứng, không ẩn cột kết quả thừa, LOOKUP vẫn có cột "Từ".
    const broken = {
        columnLabels() {
            return {
                labels: {
                    from_value: "Từ",
                    to_value: "Đến",
                    key_field: "Giá trị cần tra",
                    result_value: "Kết quả",
                    result_item: "Kết quả",
                },
                hidden: { result_value: false, result_item: false },
            };
        },
    };
    mustFail(() => testColumnLabels(broken), "nhãn cứng + không ẩn cột");
});

check("ĐỐI CHỨNG ÂM — columnLabels (nhãn trùng tên biến vẫn lọt)", () => {
    // Bản hỏng đúng như trước sửa: dùng thẳng `input_label`, chỉ xử lý ca rỗng.
    const broken = {
        columnLabels(inputLabel, outputLabel, resultType, kind) {
            const input = String(inputLabel === null || inputLabel === undefined
                ? "" : inputLabel).trim();
            return {
                labels: {
                    from_value: input ? "Từ (" + input + ")" : "Từ",
                    key_field: input ? "Giá trị (" + input + ")" : "Giá trị",
                },
                hidden: {},
            };
        },
    };
    let threw = false;
    try {
        const out = broken.columnLabels(
            "total_thick_mm", "", "NUMBER", "THRESHOLD", "total_thick_mm");
        assert(out.labels.from_value === "Từ (dữ liệu quy tắc đọc)",
            "bản hỏng lọt mã biến: " + out.labels.from_value);
    } catch (e) { threw = true; }
    assert(threw, "ĐỐI CHỨNG ÂM: bộ kiểm KHÔNG bắt được nhãn trùng tên biến");
});

// ═══════════════════════════════════════════════════════════════════════════
// 6. findDuplicateKeys — giá trị cần tra bị lặp
// ═══════════════════════════════════════════════════════════════════════════
function testDuplicateKeys(api) {
    eq(api.findDuplicateKeys([]), [], "bảng rỗng");
    eq(api.findDuplicateKeys([
        { key_field: "LOWE" },
        { key_field: "8" },
    ]), [], "không lặp");
    eq(api.findDuplicateKeys([
        { key_field: "LOWE" },
        { key_field: "LOWE" },
        { key_field: "8" },
    ]), ["LOWE"], "lặp một giá trị ⇒ báo một lần");
    eq(api.findDuplicateKeys([
        { key_field: " 8 " },
        { key_field: "8" },
        { key_field: "8" },
    ]), ["8"], "bỏ khoảng trắng khi so");
    eq(api.findDuplicateKeys([
        { key_field: "" },
        { key_field: null },
        { key_field: "" },
    ]), [], "giá trị rỗng ⛔ tính là lặp");
}

check("findDuplicateKeys — lặp / không lặp / rỗng", () => {
    testDuplicateKeys(conditions);
});

check("ĐỐI CHỨNG ÂM — findDuplicateKeys", () => {
    // Bản hỏng: tính cả giá trị rỗng là lặp + không trim.
    const broken = {
        findDuplicateKeys(rows) {
            const seen = {};
            const duplicates = [];
            (rows || []).forEach((row) => {
                const key = String(row.key_field === null || row.key_field === undefined
                    ? "" : row.key_field);
                if (seen[key]) {
                    if (duplicates.indexOf(key) === -1) duplicates.push(key);
                    return;
                }
                seen[key] = true;
            });
            return duplicates;
        },
    };
    mustFail(() => testDuplicateKeys(broken), "tính giá trị rỗng là lặp");
});

// ═══════════════════════════════════════════════════════════════════════════
// 7. ruleInputDisplayLabel — câu người đọc ⛔ mã biến (UX1 chấm vòng 3)
// ═══════════════════════════════════════════════════════════════════════════
function testInputDisplayLabel(api) {
    // Nhãn thật ⇒ giữ nguyên.
    eq(api.ruleInputDisplayLabel("Độ dày kính", "total_thick_mm"), "Độ dày kính",
        "nhãn thật phải giữ nguyên");
    // Nhãn RỖNG mà có biến ⇒ nói "dữ liệu quy tắc đọc", ⛔ tên biến.
    eq(api.ruleInputDisplayLabel("", "total_thick_mm"), "dữ liệu quy tắc đọc",
        "nhãn rỗng ⛔ lấy tên biến");
    eq(api.ruleInputDisplayLabel(null, "width"), "dữ liệu quy tắc đọc",
        "nhãn null cũng vậy");
    // Nhãn TRÙNG tên biến (khác hoa/thường + khoảng trắng) ⇒ như trên.
    eq(api.ruleInputDisplayLabel("total_thick_mm", "total_thick_mm"),
        "dữ liệu quy tắc đọc", "nhãn trùng tên biến");
    eq(api.ruleInputDisplayLabel("  Total_Thick_MM ", "total_thick_mm"),
        "dữ liệu quy tắc đọc", "khác hoa/thường + khoảng trắng vẫn là trùng");
    // Nhãn khác tên biến nhưng cùng chữ căn bản ⇒ vẫn là nhãn thật (⛔ đoán bừa).
    eq(api.ruleInputDisplayLabel("total_thick", "total_thick_mm"), "total_thick",
        "khác tên biến thì giữ nguyên");

    // Câu của form: chưa khai gì ⇒ "" (caller nói "chưa khai"), có biến ⇒ nhãn.
    eq(api.ruleInputSentenceLabel("", ""), "", "chưa khai gì ⇒ chuỗi rỗng");
    eq(api.ruleInputSentenceLabel("", "total_thick_mm"), "dữ liệu quy tắc đọc",
        "có biến, chưa có nhãn ⇒ 'dữ liệu quy tắc đọc'");
    eq(api.ruleInputSentenceLabel("Độ dày kính", "total_thick_mm"), "Độ dày kính",
        "nhãn thật ⇒ giữ");
}

check("ruleInputDisplayLabel — rỗng / trùng tên biến / nhãn thật", () => {
    testInputDisplayLabel(conditions);
});

check("ĐỐI CHỨNG ÂM — ruleInputDisplayLabel (rơi về tên biến)", () => {
    // Bản hỏng đúng như trước sửa: `input_label || input_variable`.
    const broken = {
        ruleInputDisplayLabel(label, variable) {
            return String(label || "").trim() || String(variable || "").trim();
        },
        ruleInputSentenceLabel(label, variable) {
            return String(label || "").trim() || String(variable || "").trim();
        },
    };
    mustFail(() => testInputDisplayLabel(broken), "rơi về mã biến");
});

check("ruleInputDisplayLabel — uỷ quyền helper, 2 bản ra Y HỆT trên 4 ca", () => {
    assert(typeof helperApi.readableInputLabel === "function",
        "rule_helper.js thiếu hàm chung readableInputLabel");
    const cases = [
        ["", "total_thick_mm"],
        ["total_thick_mm", "total_thick_mm"],
        ["  Total_Thick_MM ", "total_thick_mm"],
        ["Độ dày kính", "total_thick_mm"],
    ];
    // Bản dự phòng (helper CHƯA nạp — trang/test thuần).
    delete global.window.AlumGlassRuleHelper;
    const fallback = cases.map((pair) => conditions.ruleInputDisplayLabel(pair[0], pair[1]));
    // Bản uỷ quyền (helper đã nạp như trên Desk).
    global.window.AlumGlassRuleHelper = helperApi;
    const delegated = cases.map((pair) => conditions.ruleInputDisplayLabel(pair[0], pair[1]));
    delete global.window.AlumGlassRuleHelper;

    eq(fallback, ["dữ liệu quy tắc đọc", "dữ liệu quy tắc đọc",
        "dữ liệu quy tắc đọc", "Độ dày kính"], "4 ca chuẩn của bản dự phòng");
    eq(delegated, fallback, "uỷ quyền helper phải ra Y HỆT bản dự phòng");
});

// ═══════════════════════════════════════════════════════════════════════════
// 8. lastRangeOpen — dải CUỐI đang mở ⇒ khoá nút thêm dòng
// ═══════════════════════════════════════════════════════════════════════════
function testLastRangeOpen(api) {
    eq(api.lastRangeOpen([]), false, "bảng rỗng ⇒ không khoá");
    eq(api.lastRangeOpen(undefined), false, "undefined ⇒ không khoá");
    eq(api.lastRangeOpen([
        { from_value: 0, to_value: 10 },
        { from_value: 10, to_value: 20 },
    ]), false, "mọi dải đóng ⇒ thêm được");
    eq(api.lastRangeOpen([
        { from_value: 0, to_value: 10 },
        { from_value: 10, to_value: "" },
    ]), true, "'Đến' trống (chuỗi) ở dải cuối ⇒ đang mở");
    eq(api.lastRangeOpen([
        { from_value: 0, to_value: null },
    ]), true, "'Đến' null ⇒ đang mở");
    // Sắp theo mốc bắt đầu, ⛔ theo thứ tự khai trong bảng.
    eq(api.lastRangeOpen([
        { from_value: 20, to_value: "" },
        { from_value: 0, to_value: 10 },
    ]), true, "dải mở có 'Từ' lớn nhất vẫn là dải cuối dù khai trước");
    eq(api.lastRangeOpen([
        { from_value: 20, to_value: 30 },
        { from_value: 0, to_value: "" },
    ]), false, "dải mở KHÔNG phải dải cuối ⇒ dữ liệu đã sai sẵn, ⛔ khoá oan");
}

check("lastRangeOpen — rỗng / đóng / mở / thứ tự khai", () => {
    testLastRangeOpen(conditions);
});

check("ĐỐI CHỨNG ÂM — lastRangeOpen (chỉ nhìn dòng CUỐI trong bảng)", () => {
    // Bản hỏng: lấy dòng cuối theo THỨ TỰ KHAI thay vì sắp theo `Từ`; bỏ qua
    // chuỗi rỗng. Ca "dải mở khai trước" sẽ lọt.
    const broken = {
        lastRangeOpen(rows) {
            const list = Array.isArray(rows) ? rows : [];
            if (!list.length) return false;
            const last = list[list.length - 1];
            return last && (last.to_value === null || last.to_value === "");
        },
    };
    mustFail(() => testLastRangeOpen(broken), "chỉ nhìn dòng cuối theo thứ tự khai");
});

console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed +
    "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
