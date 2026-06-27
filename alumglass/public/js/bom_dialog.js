/**
 * AlumGlass — BOM Dialog JS
 * Tích hợp Approve/Reject UI + Discount selector
 */
frappe.ui.form.on("AL BOM", {
    refresh: function (frm) {
        alumglass_bom_refresh(frm);
    },
    publish_version: function (frm) {
        alumglass_publish_bom_version(frm);
    },
});

function alumglass_bom_refresh(frm) {
    // Add Publish Version button
    if (frm.doc.name && !frm.is_new()) {
        frm.add_custom_button("Publish Version", function () {
            alumglass_publish_bom_version(frm);
        }, "Actions");

        frm.add_custom_button("Compare Versions", function () {
            alumglass_compare_versions(frm);
        }, "Actions");
    }

    // Init Formula Builder on formula fields (AL Profile Line child table)
    if (window.formula_builder && formula_builder.formula) {
        try {
            formula_builder.formula.initGridField(frm, "al_lines", "qty_formula", {
                language: "formula-builder",
                height: "60px",
            });
            formula_builder.formula.initGridField(frm, "al_lines", "show_condition", {
                language: "formula-builder",
                height: "50px",
            });
            formula_builder.formula.initGridField(frm, "al_lines", "width_formula", {
                language: "formula-builder",
                height: "60px",
            });
            formula_builder.formula.initGridField(frm, "al_lines", "height_formula", {
                language: "formula-builder",
                height: "60px",
            });
            formula_builder.formula.initGridField(frm, "al_lines", "panel_count_formula", {
                language: "formula-builder",
                height: "60px",
            });
            formula_builder.formula.initGridField(frm, "al_lines", "qty_per_panel_formula", {
                language: "formula-builder",
                height: "60px",
            });
        } catch (e) {
            console.log("Formula Builder init on AL BOM skipped:", e.message);
        }
    }

    // Version history table
    if (frm.doc.current_version) {
        alumglass_render_version_history(frm);
    }
}

/**
 * Publish BOM Version
 */
function alumglass_publish_bom_version(frm) {
    const d = new frappe.ui.Dialog({
        title: "Publish BOM Version",
        fields: [
            {
                label: "Tóm tắt thay đổi",
                fieldname: "change_summary",
                fieldtype: "Small Text",
                reqd: 0,
            },
            {
                label: "Yêu cầu duyệt?",
                fieldname: "requires_approval",
                fieldtype: "Check",
                default: frm.doc.requires_approval_for_new_version || 0,
            },
        ],
        primary_action_label: "Publish",
        primary_action: function () {
            const values = d.get_values();
            frappe.call({
                method: "alumglass.modules.version.bom_version_manager.publish",
                args: {
                    bom_name: frm.doc.name,
                    change_summary: values.change_summary,
                },
                freeze: true,
                callback: function (r) {
                    d.hide();
                    frm.reload_doc();
                    frappe.show_alert({
                        message: "BOM Version đã được publish!",
                        indicator: "green",
                    });
                },
            });
        },
    });
    d.show();
}

/**
 * Compare two BOM versions
 */
function alumglass_compare_versions(frm) {
    // Get list of versions
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "AL BOM Version",
            filters: { bom: frm.doc.name },
            fields: ["name", "version_number", "published_on", "status"],
            order_by: "version_number desc",
            limit_page_length: 50,
        },
        callback: function (r) {
            if (!r.message || r.message.length < 2) {
                frappe.msgprint("Cần ít nhất 2 version để so sánh.");
                return;
            }
            const versions = r.message.map(function (v) {
                return "v" + v.version_number + " (" + v.status + ")";
            });
            const version_names = r.message.map(function (v) { return v.name; });

            const d = new frappe.ui.Dialog({
                title: "So sánh BOM Versions",
                fields: [
                    {
                        label: "Version A (cũ hơn)",
                        fieldname: "ver_a",
                        fieldtype: "Select",
                        options: versions,
                        default: versions[versions.length - 1], // oldest
                    },
                    {
                        label: "Version B (mới hơn)",
                        fieldname: "ver_b",
                        fieldtype: "Select",
                        options: versions,
                        default: versions[0], // newest
                    },
                ],
                primary_action_label: "So sánh",
                primary_action: function () {
                    const vals = d.get_values();
                    const idx_a = versions.indexOf(vals.ver_a);
                    const idx_b = versions.indexOf(vals.ver_b);
                    d.hide();

                    frappe.call({
                        method: "alumglass.modules.version.bom_version_manager.compare_versions",
                        args: {
                            version_a: version_names[idx_a],
                            version_b: version_names[idx_b],
                        },
                        freeze: true,
                        callback: function (cr) {
                            if (cr.message) {
                                alumglass_show_diff_result(cr.message);
                            }
                        },
                    });
                },
            });
            d.show();
        },
    });
}

function alumglass_show_diff_result(diff) {
    let html = '<h4>Kết quả so sánh</h4>';
    html += '<p><strong>Tóm tắt:</strong> ' + (diff.summary || "Không có thay đổi") + '</p>';

    if (diff.added_lines && diff.added_lines.length > 0) {
        html += '<h5 style="color:green">+ Thêm:</h5><ul>';
        diff.added_lines.forEach(function (l) {
            html += '<li>' + l.slug + ' - ' + l.line_name + ' (' + l.line_type + ')</li>';
        });
        html += '</ul>';
    }

    if (diff.removed_lines && diff.removed_lines.length > 0) {
        html += '<h5 style="color:red">- Xóa:</h5><ul>';
        diff.removed_lines.forEach(function (l) {
            html += '<li>' + l.slug + ' - ' + l.line_name + ' (' + l.line_type + ')</li>';
        });
        html += '</ul>';
    }

    if (diff.modified_lines && diff.modified_lines.length > 0) {
        html += '<h5 style="color:orange">~ Sửa:</h5><ul>';
        diff.modified_lines.forEach(function (l) {
            html += '<li><strong>' + l.slug + '</strong> - ' + l.line_name + '<ul>';
            (l.changes || []).forEach(function (c) {
                html += '<li>' + c.field + ': <span style="color:red">' +
                    (c.old || '""') + '</span> → <span style="color:green">' +
                    (c.new || '""') + '</span></li>';
            });
            html += '</ul></li>';
        });
        html += '</ul>';
    }

    frappe.msgprint({
        title: "BOM Version Diff",
        message: html,
        size: "large",
    });
}

/**
 * Render version history below the BOM form
 */
function alumglass_render_version_history(frm) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "AL BOM Version",
            filters: { bom: frm.doc.name },
            fields: ["name", "version_number", "published_on", "status", "change_summary"],
            order_by: "version_number desc",
            limit_page_length: 20,
        },
        callback: function (r) {
            if (!r.message) return;
            let html = '<table class="table table-condensed">';
            html += '<thead><tr><th>Version</th><th>Status</th><th>Published</th><th>Summary</th></tr></thead><tbody>';
            r.message.forEach(function (v) {
                const badge = v.status === "Published" ? "success" :
                    v.status === "Deprecated" ? "warning" : "default";
                html += '<tr>';
                html += '<td><strong>v' + v.version_number + '</strong></td>';
                html += '<td><span class="badge badge-' + badge + '">' + v.status + '</span></td>';
                html += '<td>' + (v.published_on || "-") + '</td>';
                html += '<td>' + (v.change_summary || "-") + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table>';

            // Add to form as a custom section
            if (frm.fields_dict["version_history_html"]) {
                $(frm.fields_dict["version_history_html"].wrapper).html(html);
            }
        },
    });
}

// Permission: only Admin can approve/reject
frappe.ui.form.on("AL BOM", {
    onload: function (frm) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Has Role",
                filters: { parent: frappe.session.user, role: "AluGlass Admin" },
            },
            callback: function (r) {
                if (!r.message || r.message.length === 0) {
                    // Non-admin: hide sensitive buttons
                    frm.set_df_property("requires_approval_for_new_version", "read_only", 1);
                }
            },
        });
    },
});
