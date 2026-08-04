// AlumGlass Cost Template - Client-side formula validation + preview + context injection
frappe.provide("alumglass");

alumglass.CostTemplate = {
    // Cache cho context variables (tránh gọi API nhiều lần)
    _contextCache: null,

    // Validate formula syntax before save
    validate_formula: function (formula) {
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

        return { valid: true };
    },

    // ★ Fetch Cost Bucket codes + system vars để inject vào autocomplete
    fetchContext: async function () {
        if (alumglass.CostTemplate._contextCache) {
            return alumglass.CostTemplate._contextCache;
        }
        try {
            const r = await frappe.call({
                method: "alumglass.api.get_cost_template_context",
            });
            if (r.message) {
                alumglass.CostTemplate._contextCache = r.message;
                return r.message;
            }
        } catch (e) {
            console.warn("[CostTemplate] Failed to load context:", e);
        }
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

// ── AL COST TEMPLATE Form Events ──────────────────────────────────────
frappe.ui.form.on("AL Cost Template", {
    refresh: function (frm) {
        // ★ Inject Cost Bucket + System Variable context vào autocomplete
        alumglass.CostTemplate.injectContext(frm);

        // Nút Preview
        if (!frm.is_new()) {
            frm.add_custom_button(__("Preview Calculation"), function () {
                alumglass.CostTemplate.preview(frm);
            }, __("Actions"));
        }
    },
});
