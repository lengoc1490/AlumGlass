/**
 * AlumGlass — Quotation Item Integration
 * Tích hợp BOM Dialog, Formula Builder fields, Discount UI, Approval UI
 *
 * Depends on: formula_builder.formula.* (loaded via hooks.py app_include_js)
 */
frappe.ui.form.on("Quotation Item", {
    refresh: function (frm, cdt, cdn) {
        alumglass_init_quotation_item(frm, cdt, cdn);
    },
    al_bom: function (frm, cdt, cdn) {
        alumglass_on_bom_change(frm, cdt, cdn);
    },
});

/**
 * Initialize Quotation Item row with AlumGlass integrations
 */
function alumglass_init_quotation_item(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (!row) return;

    // Patch formula fields with Monaco editor (using formula_builder API)
    if (row.al_bom && window.formula_builder && formula_builder.formula) {
        // Patch al_W_mm, al_H_mm as formula-aware fields
        try {
            formula_builder.formula.initGridField(frm, "items", "al_W_mm", {
                language: "formula-builder",
                height: "60px",
            });
            formula_builder.formula.initGridField(frm, "items", "al_H_mm", {
                language: "formula-builder",
                height: "60px",
            });
        } catch (e) {
            console.log("Formula Builder grid field init skipped:", e.message);
        }
    }

    // BOM Version badge
    alumglass_render_version_badge(frm, cdt, cdn);

    // Discount indicator
    alumglass_render_discount_info(frm, cdt, cdn);

    // Approval status badge
    alumglass_render_approval_status(frm, cdt, cdn);
}

/**
 * Handle BOM selection change
 */
function alumglass_on_bom_change(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (!row.al_bom) return;

    // Fetch BOM dialog config from server
    frappe.call({
        method: "alumglass.engine.orchestrator.get_bom_dialog_config",
        args: { bom_doc_name: row.al_bom },
        callback: function (r) {
            if (r.message) {
                alumglass_open_bom_dialog(frm, cdt, cdn, r.message);
            }
        },
    });
}

/**
 * Open the BOM Dialog for glass selection, variables, PK substitution
 */
function alumglass_open_bom_dialog(frm, cdt, cdn, config) {
    const row = frappe.get_doc(cdt, cdn);

    // Build dialog fields dynamically
    const fields = [];

    // Kích thước section
    fields.push({
        label: "Kích thước",
        fieldname: "sb_dimensions",
        fieldtype: "Section Break",
    });
    fields.push({
        label: "Chiều rộng (mm)",
        fieldname: "al_W_mm",
        fieldtype: "Float",
        reqd: 1,
        default: row.al_W_mm || 2500,
    });
    fields.push({
        label: "Chiều cao (mm)",
        fieldname: "al_H_mm",
        fieldtype: "Float",
        reqd: 1,
        default: row.al_H_mm || 3100,
    });
    fields.push({
        label: "Số lượng (bộ)",
        fieldname: "qty",
        fieldtype: "Float",
        reqd: 1,
        default: row.qty || 1,
    });

    // Technical variables from Variable Set
    if (config.variables && config.variables.length > 0) {
        fields.push({
            label: "Thông số kỹ thuật",
            fieldname: "sb_vars",
            fieldtype: "Section Break",
        });
        config.variables.forEach(function (v) {
            const field_opts = {
                label: v.var_label || v.var_code,
                fieldname: "al_var_" + v.var_code,
                fieldtype: v.ui_widget === "Select" ? "Select" : (v.var_type === "FLOAT" ? "Float" : "Data"),
                default: v.override_default || v.default_val || "",
            };
            if (v.ui_widget === "Select" && v.options) {
                field_opts.options = v.options.split(",").map(function (o) { return o.trim(); });
            }
            if (v.depends_on) {
                field_opts.depends_on = "eval:" + v.depends_on;
            }
            fields.push(field_opts);
        });
    }

    // Glass selection section
    if (config.kinh_lines && config.kinh_lines.length > 0) {
        fields.push({
            label: "Loại kính",
            fieldname: "sb_glass",
            fieldtype: "Section Break",
        });

        config.kinh_lines.forEach(function (kinh) {
            // Get available glass masters
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "AL Glass Master",
                    fields: ["name", "glass_name", "total_thick_mm"],
                    limit_page_length: 100,
                },
                async: false,
                callback: function (gr) {
                    const glass_options = (gr.message || []).map(function (g) {
                        return g.name + " - " + g.glass_name + " (" + g.total_thick_mm + "mm)";
                    });
                    fields.push({
                        label: kinh.line_name + " (prefix: " + kinh.prefix + ")",
                        fieldname: "al_glass_" + kinh.prefix,
                        fieldtype: "Select",
                        options: glass_options,
                        default: kinh.default_glass,
                    });
                },
            });
        });
    }

    // Aluminum color
    fields.push({
        label: "Màu nhôm",
        fieldname: "al_mau_nhom",
        fieldtype: "Select",
        options: ["STD", "DAK", "VG"],
        default: row.al_mau_nhom || "STD",
    });

    // PK substitution (from PK Set)
    if (config.pk_lines && config.pk_lines.length > 0) {
        fields.push({
            label: "Phụ kiện",
            fieldname: "sb_pk",
            fieldtype: "Section Break",
        });
        config.pk_lines.forEach(function (pk) {
            if (pk.allow_substitute) {
                fields.push({
                    label: pk.item_name || pk.item_code,
                    fieldname: "al_pk_override_" + pk.item_code,
                    fieldtype: "Link",
                    options: "Item",
                    default: pk.item_code,
                    description: "Có thể thay đổi phụ kiện",
                });
            }
        });
    }

    // Cost template selection
    if (config.cost_templates && config.cost_templates.length > 0) {
        fields.push({
            label: "Bảng giá thành",
            fieldname: "al_cost_template_override",
            fieldtype: "Select",
            options: config.cost_templates.map(function (ct) { return ct.name; }),
            default: config.default_cost_template,
        });
    }

    // Version badge (v17)
    if (config.version_info) {
        fields.push({
            label: "Phiên bản BOM",
            fieldname: "sb_version",
            fieldtype: "Section Break",
        });
        fields.push({
            label: "Version",
            fieldname: "al_version_display",
            fieldtype: "Data",
            default: "v" + config.version_info.version_number + " (published " + config.version_info.published_on + ")",
            read_only: 1,
        });
    }

    // Discount section
    fields.push({
        label: "Chiết khấu",
        fieldname: "sb_discount",
        fieldtype: "Section Break",
    });
    fields.push({
        label: "Chiết khấu (%)",
        fieldname: "al_discount_pct",
        fieldtype: "Float",
        read_only: 1,
        default: row.al_discount_pct || 0,
    });

    // Open dialog
    const d = new frappe.ui.Dialog({
        title: "Tính giá BOM: " + (config.bom_name || config.bom_code),
        fields: fields,
        size: "large",
        primary_action_label: "Tính giá",
        primary_action: function () {
            const values = d.get_values();
            alumglass_calculate_price(frm, cdt, cdn, config, values, d);
        },
    });
    d.show();
}

/**
 * Call the orchestrator to calculate price
 */
function alumglass_calculate_price(frm, cdt, cdn, config, dialog_values, dialog) {
    const row = frappe.get_doc(cdt, cdn);

    // Build glass_selections from dialog values
    const glass_selections = {};
    if (config.kinh_lines) {
        config.kinh_lines.forEach(function (kinh) {
            const val = dialog_values["al_glass_" + kinh.prefix] || "";
            // Extract glass code from "KINH-DON-8 - Kính đơn 8mm (8.0mm)" format
            const glass_code = val.split(" - ")[0] || val;
            if (glass_code) {
                glass_selections[kinh.prefix] = glass_code;
            }
        });
    }

    // Build PK overrides
    const pk_overrides = {};
    if (config.pk_lines) {
        config.pk_lines.forEach(function (pk) {
            const override = dialog_values["al_pk_override_" + pk.item_code];
            if (override && override !== pk.item_code) {
                pk_overrides[pk.item_code] = override;
            }
        });
    }

    // Build BOM variables
    const bom_vars = {};
    if (config.variables) {
        config.variables.forEach(function (v) {
            const val = dialog_values["al_var_" + v.var_code];
            if (val !== undefined && val !== "") {
                bom_vars[v.var_code] = val;
            }
        });
    }

    // Update row with input values
    frappe.model.set_value(cdt, cdn, "al_W_mm", dialog_values.al_W_mm);
    frappe.model.set_value(cdt, cdn, "al_H_mm", dialog_values.al_H_mm);
    frappe.model.set_value(cdt, cdn, "al_mau_nhom", dialog_values.al_mau_nhom);
    frappe.model.set_value(cdt, cdn, "al_glass_selections", JSON.stringify(glass_selections));
    frappe.model.set_value(cdt, cdn, "al_pk_overrides", JSON.stringify(pk_overrides));
    frappe.model.set_value(cdt, cdn, "al_bom_vars", JSON.stringify(bom_vars));
    if (dialog_values.al_cost_template_override) {
        frappe.model.set_value(cdt, cdn, "al_cost_template_override", dialog_values.al_cost_template_override);
    }

    // Call backend to calculate
    frappe.call({
        method: "alumglass.engine.orchestrator.calculate_quotation_item",
        args: {
            quotation_item_name: cdn,
            bom_doc_name: row.al_bom,
        },
        freeze: true,
        freeze_message: "Đang tính giá...",
        callback: function (r) {
            if (r.message) {
                const result = r.message;
                // Update row fields with results
                frappe.model.set_value(cdt, cdn, "al_vl_nhom", result.result.VL_NHOM || 0);
                frappe.model.set_value(cdt, cdn, "al_vl_kinh", result.result.VL_KINH || 0);
                frappe.model.set_value(cdt, cdn, "al_vl_vtp", result.result.VL_VTP || 0);
                frappe.model.set_value(cdt, cdn, "al_vl_pk", result.result.VL_PK || 0);
                frappe.model.set_value(cdt, cdn, "al_tong_vl", result.result.TONG_VL || 0);
                frappe.model.set_value(cdt, cdn, "al_gia_thanh", result.result.GIA_THANH || 0);
                frappe.model.set_value(cdt, cdn, "al_gia_ban", result.result.GIA_BAN || 0);
                frappe.model.set_value(cdt, cdn, "al_gia_vat", result.result.GIA_VAT || 0);
                frappe.model.set_value(cdt, cdn, "al_don_gia_m2", result.result.DON_GIA_M2 || 0);

                // Discount
                if (result.discount_info) {
                    frappe.model.set_value(cdt, cdn, "al_discount_pct", result.discount_info.pct);
                    frappe.model.set_value(cdt, cdn, "al_gia_thuong_mai", result.discount_info.gia_thuong_mai);
                }

                // Version
                if (result.version_info) {
                    frappe.model.set_value(cdt, cdn, "al_bom_version", result.version_info.name);
                }

                // Refresh the row
                frm.refresh_field("items");

                // Show cost summary
                if (result.cost_summary && result.cost_summary.length > 0) {
                    alumglass_show_cost_summary(result);
                }

                dialog.hide();

                frappe.show_alert({
                    message: "Đã tính giá thành công! GIA_BAN = " +
                        frappe.format(result.result.GIA_BAN || 0, { fieldtype: "Currency" }),
                    indicator: "green",
                }, 5);
            }
        },
    });
}

/**
 * Render version badge on the quotation item
 */
function alumglass_render_version_badge(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (!row.al_bom_version) return;

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "AL BOM Version",
            name: row.al_bom_version,
        },
        callback: function (r) {
            if (r.message) {
                const ver = r.message;
                const badge = $(`
                    <span class="badge badge-info" style="margin-left: 5px;">
                        v${ver.version_number}
                    </span>
                `);
                // Append near BOM field in grid
            }
        },
    });
}

/**
 * Render discount info
 */
function alumglass_render_discount_info(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    const disc_pct = parseFloat(row.al_discount_pct || 0);
    if (disc_pct <= 0) return;
    // Discount info hiển thị trong grid
}

/**
 * Render approval status badge
 */
function alumglass_render_approval_status(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (row.al_approval_status === "PENDING") {
        // Show orange badge
    } else if (row.al_approval_status === "APPROVED") {
        // Show green badge
    } else if (row.al_approval_status === "REJECTED") {
        // Show red badge
    }
}

/**
 * Show cost summary after calculation
 */
function alumglass_show_cost_summary(calc_result) {
    if (!calc_result.cost_summary) return;

    let html = '<table class="table table-condensed">';
    html += '<thead><tr><th>Khoản mục</th><th style="text-align:right">Giá trị</th></tr></thead><tbody>';

    calc_result.cost_summary.forEach(function (line) {
        const bold = line.is_subtotal ? 'font-weight: bold;' : '';
        html += '<tr style="' + bold + '">';
        html += '<td>' + line.label + '</td>';
        html += '<td style="text-align:right">' +
            frappe.format(line.value, { fieldtype: "Currency" }) + '</td>';
        html += '</tr>';
    });

    html += '</tbody></table>';

    frappe.msgprint({
        title: "Kết quả tính giá",
        indicator: "green",
        message: html,
    });
}

/**
 * Explain a specific formula value (audit trail)
 */
function alumglass_explain_formula(frm, cdt, cdn, formula_name) {
    const row = frappe.get_doc(cdt, cdn);
    if (!row.al_bom) return;

    frappe.call({
        method: "alumglass.engine.orchestrator.explain",
        args: {
            formula_name: formula_name,
            quotation_item_name: cdn,
            bom_doc_name: row.al_bom,
        },
        callback: function (r) {
            if (r.message) {
                frappe.msgprint({
                    title: "Giải thích: " + formula_name,
                    message: "<pre>" + JSON.stringify(r.message, null, 2) + "</pre>",
                    size: "large",
                });
            }
        },
    });
}
