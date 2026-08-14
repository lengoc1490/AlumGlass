// AlumGlass — BOM Set Context Injector
// Inject AL Variable Library + System Variables + Cost Bucket codes
// vào Formula Builder autocomplete cho AL Bom Set grid
frappe.provide("alumglass");

alumglass.BomSetContext = {
    _cache: null,

    /**
     * Fetch context variables từ API.
     * Trả về {variables: [...], references: [...]}
     */
    fetchContext: async function () {
        if (alumglass.BomSetContext._cache) return alumglass.BomSetContext._cache;
        try {
            const r = await frappe.call({
                method: "alumglass.api.get_cost_template_context",
            });
            if (r.message) {
                alumglass.BomSetContext._cache = r.message;
                return r.message;
            }
        } catch (e) {
            console.warn("[BomSetContext] Failed to load:", e);
        }
        return { variables: [], references: [] };
    },

    /**
     * Inject context vào window._afbFieldConfig.
     * Gọi từ form refresh của AL Bom Set.
     *
     * @param {object} frm - Frappe form object
     * @param {object} opts - Tuỳ chọn thêm
     * @param {string} opts.bom_code - Mã BOM (để load Variable Set riêng)
     */
    inject: async function (frm, opts = {}) {
        const ctx = await alumglass.BomSetContext.fetchContext();
        if (!ctx || !ctx.variables) return;

        // Biến bổ sung từ Variable Set của BOM hiện tại
        let bomVars = [];
        if (opts.bom_code || (frm.doc && frm.doc.bom_code)) {
            try {
                const r = await frappe.call({
                    method: "alumglass.api.get_variable_set_for_bom",
                    args: { bom_code: opts.bom_code || frm.doc.bom_code },
                });
                if (r.message?.variables) {
                    bomVars = r.message.variables.map(v => ({
                        name: v.var_name,
                        label: v.var_label || v.var_name,
                        value: v.default_value,
                        source: v.is_system ? "system" : "user",
                        doctype: "AL Variable Library",
                        field_type: v.var_type || "Float",
                    }));
                }
            } catch (e) {
                console.warn("[BomSetContext] Failed to load BOM vars:", e);
            }
        }

        // Merge tất cả nguồn biến
        window._afbFieldConfig = window._afbFieldConfig || {};
        window._afbFieldConfig.global_vars = [
            // System variables từ Variable Library (OFFSET_FRAME, VAT_RATE...)
            ...ctx.variables
                .filter(v => v.source === "system")
                .map(v => ({
                    name: v.name,
                    label: v.label || v.name,
                    value: v.value,
                    source: "global",
                    doctype: v.source_type || "Variable Library",
                    field_type: v.type || "Float",
                })),
            // Global variables từ Formula Builder (OH_VC_PCT, PROFIT_MARGIN...)
            ...ctx.variables
                .filter(v => v.source === "global")
                .map(v => ({
                    name: v.name,
                    label: v.label || v.name,
                    value: v.value,
                    source: "global",
                    doctype: v.source_type || "Formula Builder",
                    field_type: v.type || "Float",
                })),
            // Variable Set của BOM hiện tại
            ...bomVars,
            // Common variables
            ...ctx.variables
                .filter(v => v.source === "bom")
                .map(v => ({
                    name: v.name,
                    label: v.label || v.name,
                    value: v.value,
                    source: "global",
                    doctype: "Common",
                    field_type: v.type || "Float",
                })),
            // Cost Bucket codes (cho cross-reference, thường dùng trong Cost Template)
            ...ctx.variables
                .filter(v => v.source === "bucket")
                .map(v => ({
                    name: v.name,
                    label: v.label || v.name,
                    value: v.value,
                    source: "global",
                    doctype: "Cost Bucket",
                    field_type: v.type || "Float",
                })),
        ];

        console.log("[BomSetContext] Injected",
            window._afbFieldConfig.global_vars.length, "variables");
    },

    /** Xoá cache — gọi khi cần refresh context */
    invalidateCache: function () {
        alumglass.BomSetContext._cache = null;
    },
};
