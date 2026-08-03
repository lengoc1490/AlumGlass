// AlumGlass Cost Template - Client-side formula validation
frappe.provide("alumglass");

alumglass.CostTemplate = {
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

    // Preview cost template calculation
    preview: function (frm) {
        frappe.call({
            method: "alumglass.api.preview_cost_template",
            args: {
                template_code: frm.doc.template_code,
                inputs: {
                    W_mm: 2400,
                    H_mm: 2600,
                    VL_NHOM: 1000000,
                    VL_KINH: 2000000,
                    VL_VTP: 500000,
                    VL_PK: 1000000,
                }
            },
            callback: function (r) {
                if (r.message) {
                    frappe.msgprint({
                        title: __("Cost Template Preview"),
                        message: JSON.stringify(r.message, null, 2),
                        indicator: "green",
                    });
                }
            }
        });
    },
};

// Add preview button to AL Cost Template form
frappe.ui.form.on("AL Cost Template", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Preview Calculation"), function () {
                alumglass.CostTemplate.preview(frm);
            }, __("Actions"));
        }
    },
});
