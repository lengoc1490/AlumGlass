// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Formula Builder Integration (DATA-DRIVEN, ZERO HARDCODE)
// ═══════════════════════════════════════════════════════════════════════════
//
// ★ KIẾN TRÚC:
//   1. API get_formula_context(doctype) → trả về biến động từ DB
//   2. FormulaContext cache → lưu per-doctype, tránh gọi API nhiều lần
//   3. Monkey-patch _ContextBuilder.build() → inject biến từ cache
//   4. ALUMGLASS_FORMULA_DEFAULTS → config giao diện mặc định
//
// ★ THÊM NGUỒN BIẾN MỚI (NGƯỜI DÙNG NGHIỆP VỤ):
//   - Cost Bucket: thêm record AL Cost Bucket → tự động có
//   - System Variable: thêm record AL Variable Library (is_system=1) → tự động có
//   - User Variable: thêm record AL Variable Library (is_system=0) → tự động có
//   - Global Constant: thêm record Formula Global Variable → tự động có
//   - Binding: thêm record Formula Variable Binding → tự động có
//   - Slug: thêm record AL Slug Library → tự động có cross-row ref
//
// ★ ZERO CODE cho mọi config mới. Mọi thứ từ DB.
// ═══════════════════════════════════════════════════════════════════════════

frappe.provide("alumglass");
frappe.provide("alumglass.FormulaContext");

// ── 1. Formula Context Cache ───────────────────────────────────────────
// Lưu biến theo doctype, TTL 5 phút, tự động invalidate khi form reload
alumglass.FormulaContext = {
    _cache: {},       // { doctype: { variables: [...], ts: Date.now() } }
    _ttl: 300000,     // 5 phút
    _pending: null,   // Promise đang chạy (tránh duplicate calls)

    /** Gọi API lấy context cho 1 doctype (có cache).
     *  @param doctype - Tên doctype
     *  @param docname - (optional) Tên record hiện tại để resolve Variable Set
     */
    async fetch(doctype, docname) {
        var cacheKey = docname ? (doctype + "::" + docname) : doctype;
        var cached = this._cache[cacheKey];
        if (cached && (Date.now() - cached.ts) < this._ttl) {
            return cached.data;
        }
        // Tránh duplicate calls
        if (this._pending) {
            return this._pending;
        }
        this._pending = frappe.call({
            method: "alumglass.api.get_formula_context",
            args: { doctype: doctype, docname: docname || "" },
        }).then(function(r) {
            var data = r.message || { variables: [], references: [] };
            alumglass.FormulaContext._cache[cacheKey] = { data: data, ts: Date.now() };
            alumglass.FormulaContext._pending = null;
            console.log("[AlumGlass] Context loaded for " + doctype +
                (docname ? " (" + docname + ")" : "") + ": " +
                data.total_variables + " variables, " +
                (data.references || []).length + " refs");
            return data;
        }).catch(function(e) {
            alumglass.FormulaContext._pending = null;
            console.warn("[AlumGlass] Context load failed for " + doctype + ":", e);
            return { variables: [], references: [] };
        });
        return this._pending;
    },

    /** Lấy context từ cache (sync — dùng trong monkey-patch).
     *  Ưu tiên cache có docname, fallback cache không docname.
     */
    getSync(doctype, docname) {
        if (docname) {
            var cached = this._cache[doctype + "::" + docname];
            if (cached) return cached.data;
        }
        var genericCached = this._cache[doctype];
        return genericCached ? genericCached.data : { variables: [], references: [] };
    },

    /** Xóa cache cho 1 doctype */
    invalidate(doctype) {
        delete this._cache[doctype];
    },
};

// ── 2. Monkey-patch _ContextBuilder.build ──────────────────────────────
// Inject biến từ FormulaContext cache vào liveCtx (data-driven, 0 hardcode)
// ────────────────────────────────────────────────────────────────────────
(function _patchContextBuilder() {
    function _doPatch() {
        var CB = formula_builder.formula && formula_builder.formula._ContextBuilder;
        if (!CB || !CB.build || CB.__alumglassPatched) return;

        var _orig = CB.build;
        CB.build = function(params) {
            params = params || {};
            params.liveCtx = params.liveCtx || {};
            params.liveCtx.variables = params.liveCtx.variables || [];
            params.liveCtx.references = params.liveCtx.references || [];

            // ★ Đọc doctype + docname → lấy context từ cache (có thể có Variable Set)
            var dt = (params.frm && params.frm.doctype) || "";
            var dn = (params.frm && params.frm.docname) || "";
            if (dt) {
                var ctx = alumglass.FormulaContext.getSync(dt, dn);
                if (ctx && ctx.variables) {
                    for (var i = 0; i < ctx.variables.length; i++) {
                        var v = ctx.variables[i];
                        params.liveCtx.variables.push({
                            name: v.name,
                            label: v.label || v.name,
                            value: v.value,
                            type: v.type || "Float",
                            field_type: v.type || "Float",
                            source: v.source || "local",
                            source_type: v.source_type || "alumglass",
                            doctype: v.group || v.source_type || "AlumGlass",
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
// Dùng chung cho tất cả doctype. Override per-doctype bằng Object.assign.
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
// DOCTYPE SETUP
// ═══════════════════════════════════════════════════════════════════════════

// ── AL BOM SET ──────────────────────────────────────────────────────────
frappe.ui.form.on("AL Bom Set", {
    refresh(frm) {
        // ★ Pre-fetch context + resolve Variable Set từ docname
        alumglass.FormulaContext.fetch("AL Bom Set", frm.doc.name);

        var formulaFields = ["width", "height", "qty", "show_condition",
                             "item_condition_formula", "rule_input_expr"];
        formulaFields.forEach(function(fn) {
            formula_builder.formula.initGridField(frm, "items", fn,
                ALUMGLASS_OPTS({ height: "70px", id_field: "slug" }));
        });
    },
});

// ── AL COST TEMPLATE ────────────────────────────────────────────────────
frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("AL Cost Template", frm.doc.name);

        formula_builder.formula.initGridField(frm, "items", "calc_formula",
            ALUMGLASS_OPTS({
                height: "80px", float_popup: true,
                float_width: "600px", float_height: "150px",
            }));
    },
});

// ── AL ALERT CONFIG ─────────────────────────────────────────────────────
frappe.ui.form.on("AL Alert Config", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("AL Alert Config", frm.doc.name);
        if (frm.fields_dict["trigger_condition"]) {
            formula_builder.formula.patchField(frm, "trigger_condition",
                ALUMGLASS_OPTS({ height: "100px" }));
        }
    },
});

// ── AL QUANTITY CALC METHOD ─────────────────────────────────────────────
frappe.ui.form.on("AL Quantity Calc Method", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("AL Quantity Calc Method", frm.doc.name);
        if (frm.fields_dict["calc_fn"]) {
            formula_builder.formula.patchField(frm, "calc_fn",
                ALUMGLASS_OPTS({ height: "80px" }));
        }
    },
});

// ── FORMULA GLOBAL VARIABLE ─────────────────────────────────────────────
frappe.ui.form.on("Formula Global Variable", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("Formula Global Variable", frm.doc.name);
        if (frm.fields_dict["formula_expr"]) {
            formula_builder.formula.patchField(frm, "formula_expr",
                ALUMGLASS_OPTS({ height: "80px" }));
        }
    },
});

// ── QUOTATION ───────────────────────────────────────────────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("📐 Tham số BOM"), function () {
                var sel = frm.fields_dict["items"]?.grid?.get_selected_children();
                if (sel && sel.length) new alumglass.quotation.ItemParamDialog(frm, sel[0]).show();
                else frappe.msgprint(__("Chọn 1 dòng sản phẩm trước"));
            }, __("AlumGlass"));
        }
    },
});

// ── QUOTATION ITEM ──────────────────────────────────────────────────────
frappe.ui.form.on("Quotation Item", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.al_bom) {
            frm.add_custom_button(__("💰 Tính giá BOM"), function () {
                new alumglass.BOMDialog(frm.doc.name).show();
            }, __("AlumGlass"));
        }
    },
});
