// AlumGlass Cost Template - Client-side formula validation + preview
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
        // Prompt user for test inputs thay vì hardcode mock data
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
