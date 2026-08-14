frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        frm.add_custom_button("📐 Formula Builder", () => {
            formula_builder.formula.openDialog({
                current_doctype: frm.doctype,
                current_docname: frm.docname,
                value: frm.doc.custom_formula || "",
                field_label: "Formula",
                onSave(val) {
                    frm.set_value("custom_formula", val);
                    frm.save_or_update();
                    frappe.show_alert({ message: "✓ Đã lưu công thức", indicator: "green" });
                },
            });
        }, "Tools");

        ["custom_formula", "custom_formula_html", "custom_discount_rule", "custom_condition"].forEach(fieldname => {
            if (frm.fields_dict[fieldname]) {
                formula_builder.formula.patchField(frm, fieldname, {
                    height      : "100px",
                    language    : "formula-builder",
                    show_toolbar: false,
                });
            }
        });

        // // ── Tích hợp inline grid cho cột custom_formula ──────────────────
        formula_builder.formula.initGridField(frm, "items", "custom_formula", {
            language    : "formula-builder",
            height      : "80px",
            show_toolbar: false,
            id_field    : "custom_slug",
            // float_popup: false  ← mặc định
        });

        // Bật float popup:
        formula_builder.formula.initGridField(frm, "items", "custom_item_formula", {
            language    : "formula-builder",
            height      : "80px",    // chiều cao inline (khi float_popup: false)
            show_toolbar: false,
            float_popup : true,      // ← bật popup nổi
            float_width : "520px",   // tùy chỉnh chiều rộng
            float_height: "150px",   // tùy chỉnh chiều cao
            word_wrap   : true, 
            id_field    : "custom_slug",
        });

    },

    after_save(frm) {
        ["custom_formula", "custom_discount_rule"].forEach(fieldname => {
            const key = `${frm.doctype}::${frm.docname}::${fieldname}`;
            const api = window._afbPatchedEditors?.[key];
            if (api?.getValue && api.getValue() !== frm.doc[fieldname]) {
                api.setValue(frm.doc[fieldname]);
            }
        });
    },
});
