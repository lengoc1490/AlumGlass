// AlumGlass Cost Template - Client-side formula validation + preview + context injection
frappe.provide("alumglass");

alumglass.CostTemplate = {
    // Cache cho context variables (tránh gọi API nhiều lần)
    _contextCache: null,

    // ── Function whitelist (mirror server _VALIDATOR_ALLOWED_FUNCS) ─────────
    // Server: formula_builder/formula_utils/funcs/registry.py BASE_FUNCS
    //         + alumglass custom {lookup_rule, lookup_calc_pattern} (roundup đã có trong BASE_FUNCS)
    // + True/False/None xử lý riêng trong _find_unknown_identifiers().
    // Nếu server thêm hàm → bổ sung vào đây để client không chặn nhầm.
    _ALLOWED_FUNCTIONS: new Set([
        "and_", "or_", "not_", "IF", "IIF", "IFS", "SWITCH",
        "abs", "round", "roundup", "rounddown", "floor", "ceil", "power", "sqrt",
        "ln", "log10", "pi", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
        "degrees", "radians", "exp", "log", "min", "max", "sum", "len", "length", "zip",
        "int", "float", "str", "bool", "vlookup", "xlookup",
        "sumif", "sumifs", "countif", "countifs", "averageif",
        "count", "countnum", "counta", "average", "unique", "count_unique", "flatten",
        "sum_by_type", "unique_key_sum_by_type", "unique_sum", "index", "match",
        "filter_array", "choose", "rf", "last", "latest", "earliest", "first", "nth",
        "concat", "concatenate", "text_join", "textjoin",
        "left", "right", "mid", "upper", "lower", "trim", "replace", "substitute",
        "find", "len_text", "number_to_words", "coalesce", "safe_div", "safe_str",
        "now", "today", "year", "month", "day", "date_diff", "sorted_array", "sort",
        "map_key", "group_sum", "group_by_sum", "group_count", "group_by_count",
        "group_avg", "percent_of", "clamp", "is_blank", "not_blank", "isnumber",
        "to_number", "between", "date_add", "date_format", "quarter", "workdays",
        "sum_dict", "time_buckets", "in_time_bucket", "get_bucket_label", "get_period",
        "period_offset", "same_period_last_year", "year_buckets", "TB_FORMAT",
        "topo_sort_data", "topo_sort_flat", "scc_topo_sort_data", "scc_topo_sort_flat",
        "solve_linear_on_graph", "SccLinearSolver", "allocate", "AllocTuple",
        "AllocationEngine",
        // ── Custom alumglass inject qua FlexibleFormulaEngine.custom_functions ──
        "lookup_rule", "lookup_calc_pattern",
    ]),

    // Validate formula syntax before save
    validate_formula: function (formula, opts) {
        if (!formula || !formula.trim()) {
            return { valid: false, message: __("Formula cannot be empty") };
        }

        // Check for balanced parentheses
        let open = (formula.match(/\(/g) || []).length;
        let close = (formula.match(/\)/g) || []).length;
        if (open !== close) {
            return { valid: false, message: __("Unbalanced parentheses") };
        }

        // Check for invalid characters
        let valid_chars = /^[a-zA-Z0-9_\s\+\-\*\/\(\)\.\,\%\^\<\>\=\&\|\!\~\@\#\$\[\]\{\}\'\:\;\?\s]+$/;
        if (!valid_chars.test(formula)) {
            return { valid: false, message: __("Formula contains invalid characters") };
        }

        // ── NEW: chặn biến/hàm lạ (typo) ngay trên UI ────────────────────
        // opts.known_names: array các tên biến hợp lệ HOẶC null.
        // null = context chưa load xong → BỎ QUA check biến (fallback an toàn,
        // không chặn sai) — tinh thần server _build_known_names fallback set rỗng.
        opts = opts || {};
        if (opts.known_names) {
            let problem = this._find_unknown_identifiers(
                formula, opts.known_names, opts.line_codes || []
            );
            if (problem) {
                return { valid: false, message: problem };
            }
        }

        return { valid: true };
    },

    // ── Parse identifier (biến/hàm) trong formula ─────────────────────────
    // Bỏ qua string literal ('...' / "...") — không tách nhầm 'RULE-HEIGHT-MULT'
    // thành RULE/HEIGHT/MULT. Trả về [{ name, is_function }].
    _parse_identifiers: function (formula) {
        let stripped = String(formula).replace(/'[^']*'|"[^"]*"/g, " ");
        let tokens = [];
        let re = /[A-Za-z_][A-Za-z0-9_]*/g;
        let m;
        while ((m = re.exec(stripped)) !== null) {
            // Bỏ qua phần exponent của số khoa học (vd 1e5, 2.5e-3) — không
            // tách nhầm "e5"/"e-3" thành biến chưa khai báo.
            let before = stripped.charAt(m.index - 1);
            if ((before === "." || /[0-9]/.test(before)) && /^[eE][+-]?[0-9]*$/.test(m[0])) {
                continue;
            }
            let after = stripped.slice(re.lastIndex).replace(/^\s+/, "");
            tokens.push({ name: m[0], is_function: after.charAt(0) === "(" });
        }
        return tokens;
    },

    // ── Tìm biến/hàm chưa khai báo ────────────────────────────────────────
    // known_names: universe biến động (get_formula_context) — KHÔNG null ở đây.
    // line_codes:  line_code các dòng TRƯỚC (dòng hiện tại được dùng lại).
    // Trả về message lỗi hoặc null (hợp lệ).
    _find_unknown_identifiers: function (formula, known_names, line_codes) {
        let knownSet = new Set(known_names || []);
        (line_codes || []).forEach(function (rc) { if (rc) knownSet.add(rc); });

        let funcs = new Set(this._ALLOWED_FUNCTIONS);
        // True/False/None + Python keyword operators — mirror server
        // FormulaValidator._python_keywords (không tách nhầm 'and'/'or' thành biến)
        ["True", "False", "None", "and", "or", "not", "in", "is", "if", "else", "elif"]
            .forEach(function (kw) { funcs.add(kw); });

        let unknownVars = [];
        let unknownFns = [];
        let tokens = this._parse_identifiers(formula);
        tokens.forEach(function (t) {
            if (t.is_function) {
                // Hàm lạ (vd lookup_ruleX) → chặn
                if (!funcs.has(t.name)) unknownFns.push(t.name);
            } else {
                // Biến phải nằm trong known_names ∪ line_codes trước,
                // hoặc trùng tên hàm/True/False/None (được phép)
                if (!knownSet.has(t.name) && !funcs.has(t.name)) {
                    unknownVars.push(t.name);
                }
            }
        });

        let uniq = function (arr) { return Array.from(new Set(arr)); };
        if (unknownFns.length) {
            return __("Hàm không hỗ trợ: ") + uniq(unknownFns).join(", ");
        }
        if (unknownVars.length) {
            return __("Biến không khai báo: ") + uniq(unknownVars).join(", ");
        }
        return null;
    },

    // ── Lấy known_names từ context cache ──────────────────────────────────
    // Trả về array tên biến hợp lệ, HOẶC null nếu context chưa load xong/lỗi
    // (caller phải bỏ qua check biến — fallback an toàn).
    getKnownNames: function () {
        let ctx = alumglass.CostTemplate._contextCache;
        if (!ctx || !ctx.variables) return null;
        return ctx.variables.map(function (v) { return v.name; }).filter(Boolean);
    },

    // ★ Fetch Cost Bucket codes + system vars để inject vào autocomplete
    // Nguồn: get_formula_context("AL Cost Template") — KHÔNG dùng
    // get_cost_template_context (deprecated).
    fetchContext: async function () {
        if (alumglass.CostTemplate._contextCache) {
            return alumglass.CostTemplate._contextCache;
        }
        try {
            const r = await frappe.call({
                method: "alumglass.api.get_formula_context",
                args: { doctype: "AL Cost Template" },
            });
            if (r && r.message) {
                alumglass.CostTemplate._contextCache = r.message;
                return r.message;
            }
        } catch (e) {
            console.warn("[CostTemplate] Failed to load context:", e);
        }
        // KHÔNG cache fallback rỗng → getKnownNames() trả null → bỏ qua check biến
        return { variables: [], references: [] };
    },

    // ★ Inject context vào Formula Builder autocomplete
    // Gọi từ form refresh của AL Cost Template
    injectContext: async function (frm) {
        const ctx = await alumglass.CostTemplate.fetchContext();
        if (!ctx || !ctx.variables) return;

        // Inject global vars vào _afbFieldConfig để patchField/initGridField dùng
        window._afbFieldConfig = window._afbFieldConfig || {};
        window._afbFieldConfig.global_vars = ctx.variables
            .filter(v => v.source === "bucket" || v.source === "system" || v.source === "global")
            .map(v => ({
                name: v.name,
                label: v.label || v.name,
                value: v.value,
                field_type: v.type || "Float",
                source: "global",
                doctype: v.source_type || "Cost Template",
            }));
    },

    // ── Debounce + validate 1 dòng child table ────────────────────────────
    // Gọi từ onchange calc_formula — cho feedback NGAY trên UI (không chờ save).
    _debounceTimers: {},

    validateRowSoon: function (frm, cdt, cdn) {
        let key = cdn;
        if (alumglass.CostTemplate._debounceTimers[key]) {
            clearTimeout(alumglass.CostTemplate._debounceTimers[key]);
        }
        alumglass.CostTemplate._debounceTimers[key] = setTimeout(() => {
            delete alumglass.CostTemplate._debounceTimers[key];
            alumglass.CostTemplate.validateRow(frm, cdt, cdn);
        }, 400);
    },

    validateRow: async function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (!row || !row.calc_formula) return;

        await alumglass.CostTemplate.fetchContext();
        let knownNames = alumglass.CostTemplate.getKnownNames();
        let lineCodes = alumglass.CostTemplate._lineCodesBefore(frm, cdn);

        let result = alumglass.CostTemplate.validate_formula(row.calc_formula, {
            known_names: knownNames,
            line_codes: lineCodes,
        });
        if (!result.valid) {
            frappe.utils.show_alert({
                message: __("Dòng '") + (row.line_code || cdn) + __("': ") + result.message,
                indicator: "red",
            }, 5);
            return;
        }

        // ★ (Optional) FB validate_formula với known_names đúng (qua local_vars)
        if (knownNames) {
            let fb = await alumglass.CostTemplate.validateViaFB(row.calc_formula, knownNames, lineCodes);
            if (!fb.valid) {
                frappe.utils.show_alert({
                    message: __("Dòng '") + (row.line_code || cdn) + __("': ") + fb.message,
                    indicator: "orange",
                }, 5);
            }
        }
    },

    // line_code các dòng TRƯỚC dòng cdn (theo thứ tự trong child table)
    _lineCodesBefore: function (frm, cdn) {
        let rows = frm.doc.items || [];
        let idx = rows.findIndex(function (r) { return r.name === cdn; });
        let codes = [];
        if (idx > 0) {
            for (let i = 0; i < idx; i++) {
                if (rows[i].line_code) codes.push(rows[i].line_code);
            }
        }
        return codes;
    },

    // ── (Optional) FB validate_formula với scope chứa known_names ─────────
    // FB nhận biến qua local_vars (parse_scope chỉ đọc local_vars, KHÔNG đọc
    // key "variables"). Lọc bỏ cảnh báo hàm custom alumglass mà FB không biết
    // (lookup_rule/lookup_calc_pattern) để không báo nhầm.
    validateViaFB: async function (formula, knownNames, lineCodes) {
        try {
            let localVars = {};
            (knownNames || []).forEach(function (n) { localVars[n] = 0; });
            (lineCodes || []).forEach(function (rc) { if (rc) localVars[rc] = 0; });
            let scope = {
                current_doctype: "AL Cost Template",
                current_docname: "",
                local_vars: localVars,
            };
            const res = await frappe.call({
                method: "formula_builder.api.formula_builder.validate_formula",
                args: { formula: formula, scope_context_json: JSON.stringify(scope) },
            });
            let msg = res.message || {};
            // V6 P10: KHÔNG hardcode danh sách hàm custom nữa — fetch động từ
            // server (nguồn DUY NHẤT: alumglass.al_bom_engine.formula_validate
            // .ALUMGLASS_CUSTOM_FUNCS), tránh lệch pha khi thêm hàm mới.
            let customFns = new Set(await alumglass.CostTemplate._getCustomFns());
            let errors = (msg.errors || []).filter(function (e) {
                return !alumglass.CostTemplate._mentionsCustomFn(e, customFns);
            });
            let warnings = (msg.warnings || []).filter(function (w) {
                return !alumglass.CostTemplate._mentionsCustomFn(w, customFns);
            });
            if (errors.length) {
                return { valid: false, message: errors.join("; ") };
            }
            if (warnings.length) {
                return { valid: true, warning: warnings.join("; ") };
            }
            return { valid: true };
        } catch (e) {
            console.warn("[CostTemplate] FB validate failed:", e);
            return { valid: true }; // fail-open — không chặn vì infra
        }
    },

    // Cache danh sách hàm custom AlumGlass — fetch 1 lần/phiên (không đổi
    // giữa các lần validate liên tiếp trong cùng session làm việc).
    _customFnsCache: null,
    _getCustomFns: async function () {
        if (alumglass.CostTemplate._customFnsCache) {
            return alumglass.CostTemplate._customFnsCache;
        }
        try {
            const res = await frappe.call({
                method: "alumglass.api.get_allowed_formula_functions",
            });
            alumglass.CostTemplate._customFnsCache =
                (res.message && res.message.custom_functions) || [];
        } catch (e) {
            console.warn("[CostTemplate] get_allowed_formula_functions failed, fallback:", e);
            alumglass.CostTemplate._customFnsCache = ["lookup_rule", "lookup_calc_pattern", "roundup"];
        }
        return alumglass.CostTemplate._customFnsCache;
    },

    _mentionsCustomFn: function (text, customFns) {
        let s = String(text || "");
        return Array.from(customFns).some(function (fn) {
            return s.indexOf("'" + fn + "'") !== -1 || s.indexOf(" " + fn + " ") !== -1;
        });
    },

    // Preview cost template calculation
    preview: function (frm) {
        frappe.prompt([
            {
                fieldname: "test_inputs",
                fieldtype: "Small Text",
                label: __("Test Inputs (JSON)"),
                default: JSON.stringify({
                    VL_NHOM: 0, VL_KINH: 0, VL_VTP: 0, VL_PK: 0,
                    W_mm: 2400, H_mm: 2600,
                    NC_SX_PCT: 0.08, NC_LD_PCT: 0.12,
                    OH_VC_PCT: 0.03, OH_QLY_PCT: 0.03,
                    PROFIT_MARGIN: 0.16, VAT_RATE: 0.10,
                }, null, 2),
                description: __("Nhập giá trị test cho các biến. VD: bucket values, dimensions, rates...")
            }
        ], (values) => {
            let inputs;
            try {
                inputs = JSON.parse(values.test_inputs);
            } catch (e) {
                frappe.msgprint(__("JSON không hợp lệ"));
                return;
            }

            frappe.call({
                method: "alumglass.api.preview_cost_template",
                args: {
                    template_code: frm.doc.template_code,
                    inputs_json: JSON.stringify(inputs),
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __("Cost Template Preview"),
                            message: "<pre>" + JSON.stringify(r.message, null, 2) + "</pre>",
                            indicator: "green",
                        });
                    }
                }
            });
        }, __("Preview Cost Template"), __("Tính"));
    },

};