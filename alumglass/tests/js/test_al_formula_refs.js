#!/usr/bin/env node
/**
 * Test Node thuần cho alumglass/public/js/al_formula_refs.js
 *
 * KHÔNG cần site, KHÔNG cần npm/cài package — chạy:
 *     node alumglass/tests/js/test_al_formula_refs.js
 *
 * Bối cảnh (bug 2026-11-20): `_ContextBuilder.build` của formula_builder sinh
 * `siblingItems` = MỌI field của MỌI bảng con từ meta, nên autocomplete vẫn
 * hiện field KHÔNG khai trong `cross_row.fields` của profile dù server đã lọc
 * đúng trong `references`. `filterSiblingItems` lọc lại theo allowlist.
 */
"use strict";

const path = require("path");
const refs = require(path.join(
    __dirname, "..", "..", "public", "js", "al_formula_refs.js"));

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

/** Dựng ctx giống output `_ContextBuilder.build` (rút gọn). */
function makeCtx(over) {
    const siblingItems = [
        // Bảng "items" — slug kinh_canh
        { name: "items[0].glass_thick", insert: "items[0].glass_thick", tableName: "items", source: "sibling_table" },
        { name: "items.kinh_canh.glass_thick", insert: "items.kinh_canh.glass_thick", tableName: "items", slug: "kinh_canh", source: "sibling_table" },
        { name: "items[0].glass_type", insert: "items[0].glass_type", tableName: "items", source: "sibling_table" },
        { name: "items.kinh_canh.glass_type", insert: "items.kinh_canh.glass_type", tableName: "items", slug: "kinh_canh", source: "sibling_table" },
        // Field KHÔNG khai trong cross_row.fields — phải bị loại
        { name: "items[0].line_name", insert: "items[0].line_name", tableName: "items", source: "sibling_table" },
        { name: "items.kinh_canh.price_type", insert: "items.kinh_canh.price_type", tableName: "items", slug: "kinh_canh", source: "sibling_table" },
        { name: "items.kinh_canh.fixed_price", insert: "items.kinh_canh.fixed_price", tableName: "items", slug: "kinh_canh", source: "sibling_table" },
        // Bảng khác hoàn toàn không có refs — phải bị loại
        { name: "accessories[0].item_code", insert: "accessories[0].item_code", tableName: "accessories", source: "sibling_table" },
    ];
    const currentRowFields = [{ name: "width", insert: "width", source: "current_row" }];
    const parentFields = [{ name: "customer", insert: "customer", source: "parent" }];
    const localVars = [{ name: "W_mm", insert: "W_mm", source: "local" }];
    const globalVars = [{ name: "$VAT_RATE", insert: "$VAT_RATE", source: "global" }];
    const refsList = [
        { name: "items[0].glass_thick", insert: "items[0].glass_thick", source: "ref" },
        { name: "items.kinh_canh.glass_thick", insert: "items.kinh_canh.glass_thick", source: "ref" },
        { name: "items[0].glass_type", insert: "items[0].glass_type", source: "ref" },
        { name: "items.kinh_canh.glass_type", insert: "items.kinh_canh.glass_type", source: "ref" },
    ];
    const ctx = {
        profile: { code: "P_BOM_DEFAULT" },
        refs: refsList,
        siblingItems: siblingItems,
        currentRowFields: currentRowFields,
        parentFields: parentFields,
        localVars: localVars,
        globalVars: globalVars,
        allItems: [].concat(
            currentRowFields, localVars, parentFields, siblingItems, globalVars, refsList),
    };
    return Object.assign(ctx, over || {});
}

// ── (a) Không profile → KHÔNG đổi gì (đường legacy) ───────────────────
check("(a) không profile → giữ nguyên ctx (legacy)", () => {
    const ctx = makeCtx({ profile: null });
    const before = JSON.stringify(ctx);
    const out = refs.filterSiblingItems(ctx);
    assert(out === ctx, "phải trả đúng object ctx");
    eq(JSON.parse(JSON.stringify(out)), JSON.parse(before), "ctx bị thay đổi");
    assert(out.siblingItems.length === 8, "siblingItems phải còn đủ 8, được " + out.siblingItems.length);
});

// ── (b) Có profile + refs glass_thick/glass_type ─────────────────────
check("(b) có profile + refs → lọc đúng cặp (slug × field)", () => {
    const out = refs.filterSiblingItems(makeCtx());
    const inserts = out.siblingItems.map((i) => i.insert).sort();
    eq(inserts, [
        "items.kinh_canh.glass_thick",
        "items.kinh_canh.glass_type",
        "items[0].glass_thick",
        "items[0].glass_type",
    ].sort(), "siblingItems sai");
    assert(out.allItems.indexOf(out.siblingItems[0]) !== -1, "allItems thiếu sibling");
    // allItems dựng lại đúng thứ tự + đúng thành phần
    eq(out.allItems.map((i) => i.insert), [
        "width", "W_mm", "customer",
        "items[0].glass_thick", "items.kinh_canh.glass_thick",
        "items[0].glass_type", "items.kinh_canh.glass_type",
        "$VAT_RATE",
        "items[0].glass_thick", "items.kinh_canh.glass_thick",
        "items[0].glass_type", "items.kinh_canh.glass_type",
    ], "allItems sai");
    // Field ngoài cross_row.fields không còn
    ["line_name", "price_type", "fixed_price", "accessories"].forEach((bad) => {
        assert(!out.siblingItems.some((i) => i.insert.indexOf(bad) !== -1),
            "còn sót " + bad);
    });
    // currentRowFields / parentFields giữ nguyên
    assert(out.currentRowFields.length === 1, "currentRowFields bị đổi");
    assert(out.parentFields.length === 1, "parentFields bị đổi");
});

// ── (c) Có profile nhưng refs rỗng → không gợi ý chéo ────────────────
check("(c) profile + refs rỗng → siblingItems rỗng, giữ field dòng/cha", () => {
    const out = refs.filterSiblingItems(makeCtx({ refs: [] }));
    eq(out.siblingItems, [], "siblingItems phải rỗng");
    eq(out.currentRowFields.map((i) => i.insert), ["width"],
        "currentRowFields phải giữ nguyên (field dòng đang sửa)");
    eq(out.parentFields.map((i) => i.insert), ["customer"],
        "parentFields phải giữ nguyên (field doctype cha)");
    eq(out.allItems.map((i) => i.insert),
        ["width", "W_mm", "customer", "$VAT_RATE"], "allItems sai");
});

// ── (d) refs chỉ dạng index → vẫn giữ cả 2 dạng của cùng field ────────
check("(d) refs dạng items[idx].x → giữ cả index và slug", () => {
    const out = refs.filterSiblingItems(makeCtx({
        refs: [
            { name: "items[0].glass_thick", insert: "items[0].glass_thick", source: "ref" },
        ],
    }));
    const inserts = out.siblingItems.map((i) => i.insert).sort();
    eq(inserts, [
        "items.kinh_canh.glass_thick",
        "items[0].glass_thick",
    ].sort(), "phải giữ cả 2 dạng của glass_thick");
    assert(!out.siblingItems.some((i) => i.insert.indexOf("glass_type") !== -1),
        "glass_type không khai thì không được giữ");
});

// ── (e) Cùng bảng nhưng field khác → loại (chống lọc theo bảng) ──────
check("(e) ref 1 field không kéo theo field khác cùng bảng", () => {
    const out = refs.filterSiblingItems(makeCtx({
        refs: [{ name: "items.kinh_canh.glass_thick", insert: "items.kinh_canh.glass_thick", source: "ref" }],
    }));
    eq(out.siblingItems.map((i) => i.insert).sort(),
        ["items.kinh_canh.glass_thick", "items[0].glass_thick"].sort(),
        "chỉ được giữ glass_thick");
});

// ── (f) splitInsert tách đúng 2 dạng ─────────────────────────────────
check("(f) splitInsert parse đúng index/slug", () => {
    eq(refs.splitInsert("items[2].glass_thick"),
        { table: "items", field: "glass_thick", form: "index" });
    eq(refs.splitInsert("items.kinh_canh.glass_thick"),
        { table: "items", field: "glass_thick", form: "slug" });
    eq(refs.splitInsert("VL_NHOM"), null);
});

// ═════════════════════════════════════════════════════════════════════
// BỔ SUNG (Owner 2026-11-20): KHÔNG được làm mất gợi ý "dòng kính đại diện"
// — glass_thick/glass_type KHÔNG phải field thật trên AL Bom Item mà do
// engine inject per-row từ AL Glass Master; chúng nằm trong cross_row.fields
// nên PHẢI còn trong gợi ý.
// ═════════════════════════════════════════════════════════════════════

/** Ctx cho 2 dòng kính: kinh_canh (cạnh) + kinh_fixed_bottom (đáy). */
function makeGlassCtx(over) {
    const siblingItems = [
        { name: "items[0].glass_thick", insert: "items[0].glass_thick", tableName: "items" },
        { name: "items.kinh_canh.glass_thick", insert: "items.kinh_canh.glass_thick", tableName: "items", slug: "kinh_canh" },
        { name: "items[0].glass_type", insert: "items[0].glass_type", tableName: "items" },
        { name: "items.kinh_canh.glass_type", insert: "items.kinh_canh.glass_type", tableName: "items", slug: "kinh_canh" },
        { name: "items[1].glass_thick", insert: "items[1].glass_thick", tableName: "items" },
        { name: "items.kinh_fixed_bottom.glass_thick", insert: "items.kinh_fixed_bottom.glass_thick", tableName: "items", slug: "kinh_fixed_bottom" },
        // Không khai cross_row.fields → phải bị loại
        { name: "items[0].line_name", insert: "items[0].line_name", tableName: "items" },
        { name: "items.kinh_canh.line_name", insert: "items.kinh_canh.line_name", tableName: "items", slug: "kinh_canh" },
        { name: "items[0].price_type", insert: "items[0].price_type", tableName: "items" },
        { name: "items.kinh_canh.price_type", insert: "items.kinh_canh.price_type", tableName: "items", slug: "kinh_canh" },
        { name: "items[1].fixed_price", insert: "items[1].fixed_price", tableName: "items" },
    ];
    const currentRowFields = [{ name: "width", insert: "width", source: "current_row" }];
    const parentFields = [{ name: "customer", insert: "customer", source: "parent" }];
    const refsList = [
        { name: "items[0].glass_thick", insert: "items[0].glass_thick" },
        { name: "items.kinh_canh.glass_thick", insert: "items.kinh_canh.glass_thick" },
        { name: "items.kinh_canh.glass_type", insert: "items.kinh_canh.glass_type" },
        { name: "items[1].glass_thick", insert: "items[1].glass_thick" },
        { name: "items.kinh_fixed_bottom.glass_thick", insert: "items.kinh_fixed_bottom.glass_thick" },
    ];
    return Object.assign({
        profile: { code: "P_BOM_DEFAULT" },
        refs: refsList,
        siblingItems: siblingItems,
        currentRowFields: currentRowFields,
        parentFields: parentFields,
        localVars: [],
        globalVars: [],
        allItems: [].concat(currentRowFields, parentFields, siblingItems, refsList),
    }, over || {});
}

check("(g) giữ đủ gợi ý dòng kính (glass_thick/glass_type) theo refs", () => {
    const out = refs.filterSiblingItems(makeGlassCtx());
    // So khớp theo CẶP (bảng, field) ⇒ ref dạng slug cũng giữ dạng index
    // cùng field (items[0].glass_type) — đúng chủ đích "giữ cả 2 dạng".
    eq(out.siblingItems.map((i) => i.insert).sort(), [
        "items.kinh_canh.glass_thick",
        "items.kinh_canh.glass_type",
        "items.kinh_fixed_bottom.glass_thick",
        "items[0].glass_thick",
        "items[0].glass_type",
        "items[1].glass_thick",
    ].sort(), "gợi ý dòng kính bị mất/hẹp sai");
    const kept = out.siblingItems.map((i) => i.insert).join("|");
    ["line_name", "price_type", "fixed_price"].forEach((bad) => {
        assert(kept.indexOf(bad) === -1, "còn sót field không khai: " + bad);
    });
});

check("(h) cross_row.fields RỖNG (mọi field vô hướng) → không hẹp quá mức", () => {
    // Server trả danh sách RỘNG khi fields rỗng ⇒ allowlist = đúng refs đó.
    // Filter chỉ được lọc theo refs, KHÔNG được tự áp thêm danh sách cứng.
    const wide = ["width", "height", "qty", "unit_price", "line_total",
        "line_name", "price_type", "fixed_price", "note", "calc_pattern"];
    const siblingItems = [];
    const refsList = [];
    wide.forEach((f) => {
        siblingItems.push(
            { name: "items[0]." + f, insert: "items[0]." + f, tableName: "items" },
            { name: "items.kinh_canh." + f, insert: "items.kinh_canh." + f, tableName: "items", slug: "kinh_canh" });
        refsList.push(
            { name: "items[0]." + f, insert: "items[0]." + f },
            { name: "items.kinh_canh." + f, insert: "items.kinh_canh." + f });
    });
    // 1 bảng KHÔNG có trong refs — vẫn phải bị loại
    siblingItems.push({ name: "accessories[0].item_code", insert: "accessories[0].item_code", tableName: "accessories" });

    const out = refs.filterSiblingItems({
        profile: { code: "P_BOM_PROFILE_RONG" },
        refs: refsList,
        siblingItems: siblingItems,
        currentRowFields: [{ name: "width", insert: "width" }],
        parentFields: [{ name: "customer", insert: "customer" }],
        localVars: [],
        globalVars: [],
    });
    eq(out.siblingItems.length, wide.length * 2,
        "không được cắt bớt field server đã trả (rộng = " + (wide.length * 2) + ")");
    assert(!out.siblingItems.some((i) => i.insert.indexOf("accessories") !== -1),
        "bảng không có refs phải bị loại");
    assert(out.siblingItems.some((i) => i.insert === "items.kinh_canh.line_name"),
        "line_name nằm trong refs (fields rỗng) thì phải giữ");
});

console.log("\n" + "=".repeat(60));
console.log("  TOTAL: " + (passed + failed.length) + "  PASS: " + passed +
    "  FAIL: " + failed.length);
if (failed.length) {
    console.log("  FAILED: " + JSON.stringify(failed));
    process.exit(1);
}
console.log("  ALL TESTS PASSED");
