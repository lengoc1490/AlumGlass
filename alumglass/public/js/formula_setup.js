// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Formula Builder Integration (DATA-DRIVEN, ZERO HARDCODE)
// ═══════════════════════════════════════════════════════════════════════════
//
// ★ KIẾN TRÚC:
//   1. API get_formula_fields(doctype) → field nào dùng formula builder
//      (bảng AL Formula Field; thay hoàn toàn danh sách cứng cũ)
//   2. API get_formula_context(doctype, docname) → biến động từ DB
//   3. FormulaFields.init(frm) → initGridField/patchField theo dữ liệu API
//   4. FormulaContext cache → lưu per-doctype, tránh gọi API nhiều lần
//   5. Monkey-patch _ContextBuilder.build() → inject biến từ cache
//
// ★ THÊM DOCTYPE/FIELD CÔNG THỨC MỚI (NGƯỜI DÙNG NGHIỆP VỤ):
//   - Thêm 1 record `AL Formula Field` (doctype / child_table / fieldname /
//     id_field / editor_opts) → tự động có autocomplete, KHÔNG sửa JS.
//   - Thêm nguồn biến mới: xem docs/nguon_bien_tham_chieu.md §1.3.
//
// ★ ZERO CODE cho mọi config mới. Mọi thứ từ DB.
// ═══════════════════════════════════════════════════════════════════════════

frappe.provide("alumglass");
frappe.provide("alumglass.FormulaContext");

// ── 1. Formula Context Cache ───────────────────────────────────────────
// Lưu biến theo doctype, TTL 5 phút, tự động invalidate khi form reload
alumglass.FormulaContext = {
    _cache: {},       // { cacheKey: { data: {...}, ts } }
    _ttl: 300000,     // 5 phút
    // Promise đang chạy THEO cacheKey — tránh 2 request trùng, nhưng KHÔNG để
    // bản ghi A lấy nhầm dữ liệu của bản ghi B khi mở liên tiếp 2 form.
    _pending: {},

    /** Gọi API lấy context cho 1 doctype (có cache).
     *  @param doctype     - Tên doctype
     *  @param docname     - (optional) Tên record hiện tại để resolve Variable Set
     *  @param childTable  - (optional) Field child table đang sửa (vd "items").
     *                       Cache và request TÁCH theo child table vì biến của
     *                       dòng con (row context, only_fields) khác field cha.
     */
    async fetch(doctype, docname, childTable) {
        var cacheKey = doctype + "::" + (docname || "") + "::" + (childTable || "");
        var cached = this._cache[cacheKey];
        if (cached && (Date.now() - cached.ts) < this._ttl) {
            return cached.data;
        }
        // Tránh duplicate calls cho CÙNG cacheKey
        if (this._pending[cacheKey]) {
            return this._pending[cacheKey];
        }
        this._pending[cacheKey] = frappe.call({
            method: "alumglass.api.get_formula_context",
            args: {
                doctype: doctype,
                docname: docname || "",
                child_table: childTable || "",
            },
        }).then(function(r) {
            var data = r.message || { variables: [], references: [] };
            alumglass.FormulaContext._cache[cacheKey] = { data: data, ts: Date.now() };
            delete alumglass.FormulaContext._pending[cacheKey];
            console.log("[AlumGlass] Context loaded for " + doctype +
                (docname ? " (" + docname + ")" : "") +
                (childTable ? " [" + childTable + "]" : "") + ": " +
                data.total_variables + " variables, " +
                (data.references || []).length + " refs");
            return data;
        }).catch(function(e) {
            delete alumglass.FormulaContext._pending[cacheKey];
            console.warn("[AlumGlass] Context load failed for " + doctype + ":", e);
            return { variables: [], references: [] };
        });
        return this._pending[cacheKey];
    },

    /** Lấy context từ cache (sync — dùng trong monkey-patch).
     *  Thử lần lượt: có childTable → không childTable → chỉ doctype::docname
     *  → chỉ doctype. Nhờ vậy widget vẫn có biến ngay cả khi prefetch theo
     *  child table chưa xong (fallback dần về phạm vi rộng hơn).
     */
    getSync(doctype, docname, childTable) {
        var dn = docname || "";
        var ct = childTable || "";
        var keys = [];
        if (ct) keys.push(doctype + "::" + dn + "::" + ct);
        keys.push(doctype + "::" + dn + "::");
        if (dn) keys.push(doctype + "::" + dn);
        keys.push(doctype);
        for (var i = 0; i < keys.length; i++) {
            var cached = this._cache[keys[i]];
            if (cached) return cached.data;
        }
        return { variables: [], references: [] };
    },

    /** Xóa cache cho 1 doctype (mọi docname + child table của doctype đó). */
    /** Xóa cache của 1 doctype — MỌI key dạng `doctype::docname::childTable`.
     *
     * Prefix `doctype + "::"` (có `::`) nên KHÔNG khớp nhầm doctype khác có
     * cùng tiền tố tên, vd "AL Bom Set" vs "AL Bom Set Item". Chỉ xoá đúng
     * `doctype` trần (key cũ) + các key bắt đầu bằng `doctype::`.
     */
    invalidate(doctype) {
        var self = this;
        Object.keys(this._cache).forEach(function (k) {
            if (k === doctype || k.indexOf(doctype + "::") === 0) delete self._cache[k];
        });
        Object.keys(this._pending).forEach(function (k) {
            if (k === doctype || k.indexOf(doctype + "::") === 0) delete self._pending[k];
        });
    },
};

// ── 2. Monkey-patch _ContextBuilder.build ──────────────────────────────
// Inject biến từ FormulaContext cache vào liveCtx (data-driven, 0 hardcode)
// ────────────────────────────────────────────────────────────────────────
(function _patchContextBuilder() {
    // Biến có `only_fields` (array tên field) chỉ được gợi ý ở đúng các field
    // đó — luật khai trong AL Variable Profile Rule. Rỗng/không có ⇒ hiện mọi
    // field (an toàn ngược khi profile chưa khai). Không có fieldname (vd gọi
    // từ ngữ cảnh không xác định) ⇒ không lọc.
    function _fieldExcluded(variable, fieldname) {
        // Server đánh dấu `hide_all=true` khi phạm vi field của binding × rule
        // profile giao nhau RỖNG (không dùng sentinel chuỗi) ⇒ ẩn ở MỌI field.
        if (variable && variable.hide_all) return true;
        var only = variable && variable.only_fields;
        if (typeof only === "string") {
            // Server có thể trả JSON string (rule lưu Small Text) — chịu được cả 2.
            try { only = JSON.parse(only); } catch (e) { return false; }
        }
        if (!Array.isArray(only) || !only.length) return false;
        if (!fieldname) return false;
        return only.indexOf(fieldname) === -1;
    }

    function _doPatch() {
        var CB = formula_builder.formula && formula_builder.formula._ContextBuilder;
        if (!CB || !CB.build || CB.__alumglassPatched) return;

        var _orig = CB.build;
        CB.build = function(params) {
            params = params || {};
            params.liveCtx = params.liveCtx || {};
            params.liveCtx.variables = params.liveCtx.variables || [];
            params.liveCtx.references = params.liveCtx.references || [];

            // ★ Đọc doctype + docname + child table → lấy context từ cache
            // (có thể có Variable Set / biến theo dòng con)
            var dt = (params.frm && params.frm.doctype) || "";
            var dn = (params.frm && params.frm.docname) || "";
            var childTable = params.childTableField || params.child_table || "";
            // Field đang sửa — widget truyền qua `_buildCtx()`; dùng để áp
            // `only_fields` (biến chỉ gợi ý ở một số field).
            var currentField = params.fieldname || "";
            if (dt) {
                var ctx = alumglass.FormulaContext.getSync(dt, dn, childTable);
                if (ctx && ctx.variables) {
                    for (var i = 0; i < ctx.variables.length; i++) {
                        var v = ctx.variables[i];
                        if (_fieldExcluded(v, currentField)) continue;
                        // doctype field hiển thị trong tooltip — gộp group + value_source
                        var tooltipInfo = (v.group || v.source_type || "AlumGlass");
                        if (v.value_source) {
                            tooltipInfo += " · " + v.value_source;
                        }
                        params.liveCtx.variables.push({
                            name: v.name,
                            label: v.label || v.name,
                            value: v.value,
                            type: v.type || "Float",
                            field_type: v.type || "Float",
                            source: v.source || "local",
                            source_type: v.source_type || "alumglass",
                            doctype: tooltipInfo,
                        });
                    }
                }
                if (ctx && ctx.references) {
                    for (var j = 0; j < ctx.references.length; j++) {
                        params.liveCtx.references.push(ctx.references[j]);
                    }
                }
            }

            return _orig.call(this, params);
        };
        CB.__alumglassPatched = true;
        console.log("[AlumGlass] ContextBuilder patched — data-driven, zero hardcode");
    }

    // Poll cho đến khi formula_builder.js load xong
    if (formula_builder.formula && formula_builder.formula._ContextBuilder) {
        _doPatch();
    } else {
        var _tries = 0, _maxTries = 50;
        var _poll = setInterval(function() {
            _tries++;
            if (formula_builder.formula && formula_builder.formula._ContextBuilder) {
                clearInterval(_poll); _doPatch();
            } else if (_tries >= _maxTries) {
                clearInterval(_poll);
                console.warn("[AlumGlass] ContextBuilder timeout — autocomplete limited");
            }
        }, 100);
    }
})();

// ── 3. Default Formula UI Config ───────────────────────────────────────
// Dùng chung cho tất cả doctype. Override per-doctype bằng editor_opts
// của record AL Formula Field (Object.assign trong FormulaFields._buildOpts).
// ────────────────────────────────────────────────────────────────────────
var ALUMGLASS_FORMULA_DEFAULTS = {
    language    : "formula-builder",
    show_toolbar: false,     // Toolbar (chỉ có Copy btn)
    show_preview: false,     // Preview bar (▶ kết quả + nút Chạy + Editor)
};

// ── 4. Helper: tạo opts cho formula field ─────────────────────────────
// Dùng: initGridField(frm, "items", "width", ALUMGLASS_OPTS({height:"70px", id_field:"slug"}))
function ALUMGLASS_OPTS(overrides) {
    return Object.assign({}, ALUMGLASS_FORMULA_DEFAULTS, overrides || {});
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. REGISTRY ĐỘNG — AL Formula Field (V6 P12)
// ═══════════════════════════════════════════════════════════════════════════
// Trước bản vá này, file có mảng cứng FORMULA_DOCTYPE_REGISTRY liệt kê 6
// doctype + danh sách field công thức ⇒ thêm field công thức mới phải sửa JS
// và build lại asset. (2 field `panel_count_formula` / `qty_per_panel_formula`
// trên AL Bom Item cố ý KHÔNG đăng ký: không engine nào đọc chúng — xem
// docs/nguon_bien_tham_chieu.md §6.2.)
//
// Nay danh sách nằm ở bảng `AL Formula Field` và được đọc qua API
// `alumglass.api.get_formula_fields(doctype)`. Thêm field = thêm 1 record,
// KHÔNG sửa file này.
// ═══════════════════════════════════════════════════════════════════════════
alumglass.FormulaFields = {
    _cache: {},     // { doctype: { rows: [...], ts } }
    _pending: {},   // { doctype: Promise } — tránh gọi trùng khi refresh liên tiếp
    // 60s đủ ngắn để admin thêm AL Formula Field là thấy ngay ở lần mở form kế
    // tiếp, đủ dài để không gọi API mỗi lần refresh form.
    _ttl: 60000,

    /** Gọi API lấy danh sách field công thức của 1 doctype (có cache).
     *  Lỗi API → trả [] và console.warn — ⛔ KHÔNG fallback danh sách cứng
     *  (fallback cứng chính là thứ đang gây lệch registry).
     */
    async fetch(doctype) {
        if (!doctype) return [];
        var self = this;
        var cached = this._cache[doctype];
        if (cached && (Date.now() - cached.ts) < this._ttl) {
            return cached.rows;
        }
        if (this._pending[doctype]) {
            return this._pending[doctype];
        }

        this._pending[doctype] = frappe.call({
            method: "alumglass.api.get_formula_fields",
            args: { doctype: doctype },
        }).then(function(r) {
            var rows = self._extractRows(r && r.message);
            self._cache[doctype] = { rows: rows, ts: Date.now() };
            delete self._pending[doctype];
            return rows;
        }).catch(function(e) {
            delete self._pending[doctype];
            console.warn("[AlumGlass] get_formula_fields failed for " + doctype + ":", e);
            return [];
        });
        return this._pending[doctype];
    },

    /** API có thể trả thẳng array hoặc {rows: [...]} — chấp nhận cả hai. */
    _extractRows(message) {
        if (Array.isArray(message)) return message;
        if (message && Array.isArray(message.rows)) return message.rows;
        return [];
    },

    /** editor_opts là JSON string trong DB; API có thể trả string hoặc object. */
    _parseEditorOpts(raw) {
        if (!raw) return {};
        if (typeof raw === "object") return raw;
        try {
            var parsed = JSON.parse(raw);
            return (parsed && typeof parsed === "object") ? parsed : {};
        } catch (e) {
            console.warn("[AlumGlass] editor_opts JSON không hợp lệ:", raw);
            return {};
        }
    },

    /** Dựng opts cho patchField/initGridField từ 1 dòng AL Formula Field. */
    _buildOpts(row) {
        var editorOpts = this._parseEditorOpts(row.editor_opts);
        var base = { id_field: row.id_field || "slug" };
        // Chiều cao mặc định chỉ áp cho child table — field cha để
        // patchField tự chọn theo fieldtype nếu record không khai height.
        if (row.child_table) base.height = "70px";
        if (editorOpts.height) base.height = editorOpts.height;
        return ALUMGLASS_OPTS(Object.assign(base, editorOpts));
    },

    /** Áp 1 dòng cấu hình lên form đang mở. */
    apply(frm, row) {
        var fieldname = row.fieldname || row.field_name;
        if (!fieldname) return;
        // API đã lọc is_active, nhưng phòng khi cache/phiên bản cũ trả về cả
        // dòng đã tắt — bỏ qua để không bật autocomplete ngoài ý muốn.
        if (row.is_active !== undefined && !cint(row.is_active)) return;
        if (!window.formula_builder || !window.formula_builder.formula) return;

        var opts = this._buildOpts(row);
        if (row.child_table) {
            // Doctype cha không có bảng con này → bỏ qua (không phải lỗi).
            if (!frm.fields_dict || !frm.fields_dict[row.child_table]) return;
            formula_builder.formula.initGridField(
                frm, row.child_table, fieldname, opts
            );
        } else if (frm.fields_dict && frm.fields_dict[fieldname]) {
            formula_builder.formula.patchField(frm, fieldname, opts);
        }
    },

    /** Nạp toàn bộ field công thức cho form hiện tại. */
    async init(frm) {
        if (!frm || !frm.doctype) return;
        if (frm.meta && frm.meta.istable) return;   // form dòng con — không patch

        var self = this;
        var rows = await this.fetch(frm.doctype);
        if (!rows.length) return;

        // Chỉ doctype CÓ field công thức mới cần context biến — tránh gọi
        // get_formula_context cho mọi form trong desk (API đó có allowlist và
        // sẽ throw với doctype ngoài miền).
        // Prefetch 1 lần cho field cha + 1 lần cho MỖI child table phân biệt có
        // field công thức. KHÔNG gọi theo từng fieldname: server trả kèm
        // `only_fields` để client tự lọc theo field đang sửa (tiết kiệm request).
        var docname = frm.docname || (frm.doc && frm.doc.name) || "";
        alumglass.FormulaContext.fetch(frm.doctype, docname, "");
        var tables = [];
        rows.forEach(function (row) {
            var tbl = row.child_table || "";
            if (tbl && tables.indexOf(tbl) === -1) tables.push(tbl);
        });
        tables.forEach(function (tbl) {
            alumglass.FormulaContext.fetch(frm.doctype, docname, tbl);
        });

        rows.forEach(function(row) {
            try {
                self.apply(frm, row);
            } catch (e) {
                console.warn("[AlumGlass] Không khởi tạo được formula field:", row, e);
            }
        });
    },

    /** Xoá cache của 1 doctype (dùng sau khi sửa AL Formula Field). */
    invalidate(doctype) {
        delete this._cache[doctype];
        delete this._pending[doctype];
    },
};

// ── 6. Đăng ký refresh cho MỌI form (không danh sách cứng) ──────────────
// Frappe phát sự kiện document "form-refresh" (kèm frm) ngay trong
// render_form — lúc này `frm.fields_dict` đã có đủ control để patch.
// Doctype chưa khai AL Formula Field → API trả [] → init không làm gì.
// (Không dùng frappe.ui.form.on("refresh") vì phải biết trước doctype, tức
// lại quay về danh sách cứng.)
$(document).on("form-refresh", function (e, frm) {
    if (!frm || !frm.doctype) return;
    if (frm.meta && frm.meta.istable) return;

    // Init tự fetch AL Formula Field; nếu doctype có field công thức thì
    // nạp thêm context biến cho monkey-patch _ContextBuilder (ở trên).
    alumglass.FormulaFields.init(frm);
});

// ── 7. AL BOM ITEM — depends_on field re-patch ─────────────────────────
// Fix: Khi Item Selection Mode thay đổi, các field có depends_on
// (item_condition_formula, rule_input_expr) cần được patch lại để
// formula_builder Monaco editor override hoàn toàn textarea gốc,
// tránh tình trạng cả 2 cùng hiển thị (textarea gốc nằm trên, Monaco nằm dưới).
// KHÔNG liên quan registry AL Formula Field — đây là xử lý sự kiện
// item_selection_mode (không phải refresh), việc khác hẳn "bật autocomplete".
frappe.ui.form.on("AL Bom Item", {
    item_selection_mode: function(frm, cdt, cdn) {
        _repatchDependsOnFormulaFields(frm, cdt, cdn);
    },
});

/**
 * Force re-patch các formula field có depends_on trong expanded row.
 * Khi Frappe's depends_on ẩn/hiện field, textarea gốc có thể bị show lại
 * song song với Monaco wrapper đã được tạo từ trước. Hàm này dispose editor
 * cũ và tạo mới, đảm bảo Monaco luôn là element duy nhất hiển thị.
 */
function _repatchDependsOnFormulaFields(frm, cdt, cdn) {
    if (frm.doctype !== "AL Bom Set") return;

    var grid = frm.fields_dict["items"] && frm.fields_dict["items"].grid;
    if (!grid) return;

    var frappeRow = grid.get_row(cdn);
    if (!frappeRow) return;
    var rowEl = (frappeRow.wrapper && frappeRow.wrapper[0])
             || (frappeRow.$wrapper && frappeRow.$wrapper[0]);
    if (!rowEl || !rowEl.classList.contains("grid-row-open")) return;

    // Đợi Frappe depends_on xử lý xong rồi mới re-patch
    setTimeout(function () {
        _forceRepatchChildField(frm, cdt, cdn, rowEl, "item_condition_formula");
        _forceRepatchChildField(frm, cdt, cdn, rowEl, "rule_input_expr");
    }, 150);
}

function _forceRepatchChildField(frm, cdt, cdn, rowEl, fieldname) {
    var expandedWrapper =
        rowEl.querySelector('.form-layout [data-fieldname="' + fieldname + '"] .control-input')
        || rowEl.querySelector('[data-fieldname="' + fieldname + '"] .control-input');
    if (!expandedWrapper) return;

    formula_builder.formula.patchChildField(frm, "items", cdn, fieldname, {
        language: "formula-builder",
        height: "70px",
        show_toolbar: false,
        show_preview: true,
        forceNew: true,
        expanded: true,
        wrapper: expandedWrapper,
    });
}

// NOTE: Quotation & Quotation Item buttons + dialog are handled in:
//   - doctype/overrides/quotation.js  (row buttons + double-click + ItemParamDialog + BOMDialog)
// DO NOT add form.on("Quotation") or form.on("Quotation Item") here — it causes duplicate buttons.
