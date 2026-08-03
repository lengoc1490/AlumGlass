// AlumGlass — Formula Builder Autocomplete Integration
// Pattern giống hệt alumglass/alumglass/alumglass/doctype/overrides/sales_order.js
// Sử dụng formula_builder.formula.patchField (form) + initGridField (grid)

// ─────────────────────────────────────────────────────────────────────────────
// 1. AL BOM SET (parent) — 2 child tables: items + accessory_items
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Bom Set", {
    refresh(frm) {
        // Grid 1: Bom Items (Nhôm, Kính, VTP) — các cột formula
        const item_grid_fields = ["width", "height", "qty", "show_condition",
                                  "item_condition_formula", "rule_input_expr"];
        item_grid_fields.forEach(fieldname => {
            formula_builder.formula.initGridField(frm, "items", fieldname, {
                language    : "formula-builder",
                height      : "70px",
                show_toolbar: false,
            });
        });

        // Grid 2: Accessory Items (Phụ kiện) — không có cột formula, chỉ chọn item + qty
        // (không cần initGridField vì accessory item dùng Link + Float, không có formula)
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. AL COST TEMPLATE (parent) — chứa child table AL Cost Template Item
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        // Grid field calc_formula — popup nổi to hơn vì công thức dài
        formula_builder.formula.initGridField(frm, "items", "calc_formula", {
            language    : "formula-builder",
            height      : "80px",
            show_toolbar: false,
            float_popup : true,
            float_width : "600px",
            float_height: "150px",
        });

        // Nút Preview
        if (!frm.is_new()) {
            frm.add_custom_button(__("Preview Calculation"), function () {
                alumglass.CostTemplate?.preview(frm);
            }, __("Actions"));
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. AL ALERT CONFIG — field trigger_condition trên form chính
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Alert Config", {
    refresh(frm) {
        if (frm.fields_dict["trigger_condition"]) {
            formula_builder.formula.patchField(frm, "trigger_condition", {
                language    : "formula-builder",
                height      : "100px",
                show_toolbar: false,
            });
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. AL QUANTITY CALC METHOD — field calc_fn
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("AL Quantity Calc Method", {
    refresh(frm) {
        if (frm.fields_dict["calc_fn"]) {
            formula_builder.formula.patchField(frm, "calc_fn", {
                language    : "formula-builder",
                height      : "80px",
                show_toolbar: false,
            });
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. FORMULA GLOBAL VARIABLE — field formula_expr
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("Formula Global Variable", {
    refresh(frm) {
        if (frm.fields_dict["formula_expr"]) {
            formula_builder.formula.patchField(frm, "formula_expr", {
                language    : "formula-builder",
                height      : "80px",
                show_toolbar: false,
            });
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. AL PROFIL SYSTEM — hiển thị offset visualization (nếu có custom_html field)
// ─────────────────────────────────────────────────────────────────────────────
// (placeholder cho các doctype khác nếu cần thêm field formula)

// ─────────────────────────────────────────────────────────────────────────────
// 7. QUOTATION — nút Formula Builder cho custom_formula (nếu có)
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        // Nút mở dialog tham số BOM
        if (!frm.is_new()) {
            frm.add_custom_button(__("📐 Tham số BOM"), function () {
                const selected = frm.fields_dict["items"]?.grid?.get_selected_children();
                if (selected && selected.length > 0) {
                    new alumglass.quotation.ItemParamDialog(frm, selected[0]).show();
                } else {
                    frappe.msgprint(__("Vui lòng chọn 1 dòng sản phẩm trong bảng"));
                }
            }, __("AlumGlass"));
        }
    },
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. QUOTATION ITEM — nút Tính giá BOM
// ─────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on("Quotation Item", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.al_bom) {
            frm.add_custom_button(__("💰 Tính giá BOM"), function () {
                new alumglass.BOMDialog(frm.doc.name).show();
            }, __("AlumGlass"));
        }
    },
});
