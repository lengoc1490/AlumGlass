// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Lọc gợi ý biến chéo dòng theo cross_row.fields của profile
// ═══════════════════════════════════════════════════════════════════════════
//
// VÌ SAO CẦN FILE NÀY
// -------------------
// `_ContextBuilder.build` (formula_builder/public/js/formula_builder.js) tự
// sinh `siblingItems` = MỌI field của MỌI bảng con từ meta — không biết gì về
// profile. Server AlumGlass đã lọc đúng (variable_sources/adapters.py
// `build_references` → `_append_references(fields=parse_json_list(row.get(
// "fields")))`), nhưng client vẫn trộn `siblingItems` (toàn bộ meta) vào
// `allItems` ⇒ autocomplete hiện cả field KHÔNG khai trong `cross_row.fields`
// (vd line_name, price_type, fixed_price...). Tài liệu
// docs/variable-catalog/huong-dan-setting-bien.md §5 ghi hành vi ĐÚNG là
// "chỉ slug hiện có × field trong cross_row.fields" ⇒ đây là bug client.
//
// CÁCH DÙNG
// ---------
// formula_setup.js (`_patchContextBuilder`) gọi:
//     out = window.AlumGlassFormulaRefs.filterSiblingItems(out)
//
// HỢP ĐỒNG ĐẦU VÀO (ctx = kết quả `_ContextBuilder.build` + metadata)
//   - ctx.profile        : profile catalog server trả (falsy = đường legacy)
//   - ctx.refs           : references server trả (đã map: name/label/insert)
//   - ctx.siblingItems   : gợi ý chéo dòng client tự sinh (sẽ bị lọc)
//   - ctx.currentRowFields / parentFields / localVars / globalVars
//
// KHÔNG phụ thuộc frappe/jQuery ⇒ chạy được bằng Node (xem
// tests/js/test_al_formula_refs.js) và không cần build lại asset để test.
// ═══════════════════════════════════════════════════════════════════════════

(function (root) {
    "use strict";

    // Bảng + field: tên field Frappe chỉ gồm chữ/số/underscore/gạch.
    // Index form : "items[0].glass_thick"
    // Slug form  : "items.kinh_canh.glass_thick"
    var RE_INDEX = /^([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])*)\[(\d+)\]\.(.+)$/;
    var RE_SLUG = /^([A-Za-z_][A-Za-z0-9_]*)\.([^.\[]+)\.(.+)$/;

    /**
     * Tách 1 chuỗi insert thành {table, field, form}.
     * Trả null nếu không phải dạng tham chiếu bảng con.
     */
    function splitInsert(insert) {
        if (typeof insert !== "string" || !insert) return null;
        var m = insert.match(RE_INDEX);
        if (m) return { table: m[1], field: m[3], form: "index" };
        m = insert.match(RE_SLUG);
        if (m) return { table: m[1], field: m[3], form: "slug" };
        return null;
    }

    /** Khoá so khớp cặp (bảng, field) — bỏ qua dạng index/slug. */
    function pairKey(table, field) {
        return table + "\u0000" + field;
    }

    /**
     * Dựng allowlist từ references server trả.
     * Mỗi ref có thể là object {name, insert} hoặc chuỗi thuần.
     *
     * Trả { inserts: Set-like object, pairs: Set-like object }
     * (dùng object thay vì Set để chạy được cả môi trường cũ).
     */
    function buildAllowlist(refs) {
        var inserts = {};
        var pairs = {};
        (Array.isArray(refs) ? refs : []).forEach(function (r) {
            var raw = (r && (r.insert || r.name)) || (typeof r === "string" ? r : "");
            if (!raw) return;
            inserts[raw] = true;
            var parsed = splitInsert(raw);
            if (parsed) pairs[pairKey(parsed.table, parsed.field)] = true;
        });
        return { inserts: inserts, pairs: pairs };
    }

    /** Lấy (bảng, field) của 1 sibling item, ưu tiên `insert`. */
    function _itemPair(item) {
        if (!item) return null;
        var parsed = splitInsert(item.insert) || splitInsert(item.name);
        if (parsed) return parsed;
        // Fallback: item do core dựng luôn có tableName + name "tbl[...].field"
        if (item.tableName && typeof item.name === "string") {
            var idx = item.name.lastIndexOf(".");
            if (idx > 0) {
                return { table: item.tableName, field: item.name.slice(idx + 1) };
            }
            if (item.fieldname) return { table: item.tableName, field: item.fieldname };
        }
        return null;
    }

    function _allowed(item, allow) {
        var insert = item && (item.insert || item.name);
        if (insert && allow.inserts[insert]) return true;
        var pair = _itemPair(item);
        return !!(pair && allow.pairs[pairKey(pair.table, pair.field)]);
    }

    function _arr(v) {
        return Array.isArray(v) ? v : [];
    }

    /**
     * Lọc `ctx.siblingItems` theo allowlist references.
     *
     * - KHÔNG có `ctx.profile`  → trả nguyên ctx (đường legacy, 100% cũ).
     * - CÓ profile              → chỉ giữ sibling item có field nằm trong
     *   references (allowlist). Bảng con không khai cross_row.fields ⇒ không
     *   còn gợi ý chéo (đúng nghĩa allowlist).
     * - `currentRowFields` / `parentFields` GIỮ NGUYÊN — chỉ lọc chéo dòng.
     *
     * So khớp theo CẶP (bảng, field) nên ref dạng `items.<slug>.<field>` và
     * dạng `items[idx].<field>` của CÙNG field đều được giữ (kể cả khi
     * `include_index_form` bị tắt ở server) — tránh mất gợi ý dòng kính
     * (`glass_thick`/`glass_type` do engine inject, không có trong meta).
     * Allowlist = ĐÚNG những gì server trả: profile khai `cross_row.fields`
     * rỗng (server trả mọi field vô hướng) ⇒ filter không hẹp quá mức.
     *
     * @param {Object} ctx
     * @returns {Object} chính ctx (đã cập nhật siblingItems + allItems)
     */
    function filterSiblingItems(ctx) {
        if (!ctx || typeof ctx !== "object") return ctx;
        // Đường legacy: record chưa gán Variable Profile ⇒ không đổi gì.
        if (!ctx.profile) return ctx;

        var refs = _arr(ctx.refs).length ? _arr(ctx.refs) : _arr(ctx.references);
        var allow = buildAllowlist(refs);
        var siblingItems = _arr(ctx.siblingItems).filter(function (item) {
            return _allowed(item, allow);
        });

        ctx.siblingItems = siblingItems;
        // Dựng lại đúng thứ tự allItems mà _ContextBuilder.build dùng.
        ctx.allItems = []
            .concat(
                _arr(ctx.currentRowFields),
                _arr(ctx.localVars),
                _arr(ctx.parentFields),
                siblingItems,
                _arr(ctx.globalVars),
                refs
            );
        return ctx;
    }

    var api = {
        filterSiblingItems: filterSiblingItems,
        buildAllowlist: buildAllowlist,
        splitInsert: splitInsert,
        pairKey: pairKey,
    };

    // Trình duyệt (app_include_js)
    if (root) root.AlumGlassFormulaRefs = api;

    // Node (test standalone, không cần build asset)
    if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
