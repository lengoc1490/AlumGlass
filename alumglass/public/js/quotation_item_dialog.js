// AlumGlass — Quotation Item: Dialog nhập tham số BOM
// Mỗi dòng sản phẩm có nút riêng trong grid
// Form fields thay vì JSON thô — user không cần biết cấu trúc JSON

frappe.provide("alumglass.quotation");

alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    constructor(frm, child_doc) {
        this.frm = frm;
        this.child_doc = child_doc;
    }

    show() {
        const vars = this._parse_existing();

        this.dialog = new frappe.ui.Dialog({
            title: __("Tham số BOM — ") + (this.child_doc.item_name || this.child_doc.item_code || ""),
            fields: [
                // ── Section: BOM ──────────────────────────────
                { fieldtype: "Section Break", label: __("Chọn BOM") },
                { fieldname: "al_bom", fieldtype: "Link", label: __("BOM"),
                  options: "AL BOM", default: this.child_doc.al_bom || "",
                  onchange: () => {
                      const bom = this.dialog.get_value("al_bom");
                      if (bom) {
                          frappe.db.get_value("AL BOM", bom, "current_version", (r) => {
                              if (r.current_version) this.dialog.set_value("al_bom_version", r.current_version);
                          });
                      }
                  }
                },
                { fieldname: "col_bom", fieldtype: "Column Break" },
                { fieldname: "al_bom_version", fieldtype: "Link", label: __("BOM Version"),
                  options: "AL BOM Version", default: this.child_doc.al_bom_version || "" },

                // ── Section: Kích thước ────────────────────────
                { fieldtype: "Section Break", label: __("Kích thước (mm)") },
                { fieldname: "W_mm", fieldtype: "Float", label: __("Chiều rộng W"),
                  default: vars.W_mm || 2400, reqd: 1 },
                { fieldname: "col_wh", fieldtype: "Column Break" },
                { fieldname: "H_mm", fieldtype: "Float", label: __("Chiều cao H"),
                  default: vars.H_mm || 2600, reqd: 1 },
                { fieldname: "TransomHeight_mm", fieldtype: "Float",
                  label: __("Chiều cao ô kính cố định (Transom)"), default: vars.TransomHeight_mm || 600 },

                // ── Section: Cấu hình sản phẩm ──────────────────
                { fieldtype: "Section Break", label: __("Cấu hình") },
                { fieldname: "n_panel", fieldtype: "Int", label: __("Số cánh"),
                  default: vars.n_panel || 2, reqd: 1 },
                { fieldname: "col_cfg", fieldtype: "Column Break" },
                { fieldname: "aluminum_color", fieldtype: "Link", label: __("Màu nhôm"),
                  options: "AL Color Standard", default: vars.aluminum_color || "WHITE" },
                { fieldname: "aluminum_origin", fieldtype: "Select", label: __("Xuất xứ nhôm"),
                  options: "IMPORT\nDOMESTIC", default: vars.aluminum_origin || "IMPORT" },

                // ── Section: Thông số kỹ thuật ──────────────────
                { fieldtype: "Section Break", label: __("Thông số kỹ thuật") },
                { fieldname: "aluminum_thickness", fieldtype: "Float", label: __("Độ dày nhôm"),
                  default: vars.aluminum_thickness || 20 },
                { fieldname: "aluminum_surface", fieldtype: "Select", label: __("Bề mặt hoàn thiện"),
                  options: "POWDER_COATED\nANODIZED\nWOOD_GRAIN",
                  default: vars.aluminum_surface || "POWDER_COATED" },
                { fieldname: "col_spec", fieldtype: "Column Break" },
                { fieldname: "glass_master", fieldtype: "Link", label: __("Loại kính"),
                  options: "AL Glass Master", default: vars.glass_master || "" },
                { fieldname: "accessory_set", fieldtype: "Link", label: __("Bộ phụ kiện (khác mặc định)"),
                  options: "AL Accessory Set", default: vars.accessory_set || "",
                  description: __("Để trống nếu dùng bộ phụ kiện mặc định của BOM") },

                // ── Section: Tham số mở rộng ────────────────────
                { fieldtype: "Section Break", label: __("Tham số mở rộng (nâng cao)") },
                { fieldname: "extra_vars_info", fieldtype: "HTML",
                  options: `<p style="color:#666;font-size:0.9em">
                    ${__("Thêm biến tùy chỉnh dạng <code>key=value</code>, mỗi dòng 1 biến.")}
                    ${__("VD: <code>so_lop_kinh=2</code> hoặc <code>he_so_an_toan=1.5</code>")}
                  </p>` },
                { fieldname: "extra_vars_text", fieldtype: "Small Text",
                  label: __("Biến mở rộng"), default: this._extra_vars_to_text(vars.extra_vars || {}),
                  description: __("Mỗi dòng: tên_biến=giá_trị") },
            ],
            size: "large",
            primary_action_label: __("💾 Lưu & Tính giá"),
            primary_action: () => {
                this._save();
                this.dialog.hide();
                if (this.child_doc.al_bom) {
                    new alumglass.BOMDialog(this.child_doc.name).show();
                }
            },
        });
        this.dialog.show();
    }

    _parse_existing() {
        try {
            return JSON.parse(this.child_doc.al_bom_vars || "{}");
        } catch (e) {
            return {};
        }
    }

    _extra_vars_to_text(extra) {
        if (!extra || typeof extra !== "object") return "";
        return Object.entries(extra)
            .map(([k, v]) => `${k}=${v}`)
            .join("\n");
    }

    _text_to_extra_vars(text) {
        if (!text || !text.trim()) return {};
        const result = {};
        text.split("\n").forEach(line => {
            const idx = line.indexOf("=");
            if (idx > 0) {
                const key = line.substring(0, idx).trim();
                let val = line.substring(idx + 1).trim();
                // Auto-detect numbers
                if (/^-?\d+\.?\d*$/.test(val)) val = parseFloat(val);
                else if (val === "true") val = true;
                else if (val === "false") val = false;
                if (key) result[key] = val;
            }
        });
        return result;
    }

    _save() {
        const vals = this.dialog.get_values();
        const vars = {
            W_mm: vals.W_mm,
            H_mm: vals.H_mm,
            n_panel: vals.n_panel,
            TransomHeight_mm: vals.TransomHeight_mm || 0,
            aluminum_color: vals.aluminum_color || "WHITE",
            aluminum_origin: vals.aluminum_origin || "IMPORT",
            aluminum_thickness: vals.aluminum_thickness || 20,
            aluminum_surface: vals.aluminum_surface || "POWDER_COATED",
            glass_master: vals.glass_master || "",
            accessory_set: vals.accessory_set || "",
            extra_vars: this._text_to_extra_vars(vals.extra_vars_text),
        };

        // Lưu vào field JSON
        frappe.model.set_value(
            this.child_doc.doctype, this.child_doc.name,
            "al_bom_vars", JSON.stringify(vars, null, 2)
        );
        if (vals.al_bom) {
            frappe.model.set_value(this.child_doc.doctype, this.child_doc.name, "al_bom", vals.al_bom);
        }
        if (vals.al_bom_version) {
            frappe.model.set_value(this.child_doc.doctype, this.child_doc.name, "al_bom_version", vals.al_bom_version);
        }
    }
};

// ── Nút "📐" trên từng dòng Quotation Item grid ───────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Thêm nút vào từng dòng trong grid "items"
        frm.fields_dict["items"]?.grid?.add_custom_button?.(
            __("📐 Tham số BOM"),
            () => {
                const selected = frm.fields_dict["items"]?.grid?.get_selected_children?.();
                if (selected && selected.length > 0) {
                    new alumglass.quotation.ItemParamDialog(frm, selected[0]).show();
                } else {
                    frappe.msgprint(__("Chọn 1 dòng sản phẩm trước"));
                }
            },
            __("AlumGlass")
        );

        // Cũng thêm nút global
        frm.add_custom_button(__("📐 Tham số BOM"), function () {
            const selected = frm.fields_dict["items"]?.grid?.get_selected_children?.();
            if (selected && selected.length > 0) {
                new alumglass.quotation.ItemParamDialog(frm, selected[0]).show();
            } else {
                frappe.msgprint(__("Chọn 1 dòng sản phẩm trước"));
            }
        }, __("AlumGlass"));
    },
});

// ── Nút "💰 Tính giá" trên từng dòng ──────────────────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.fields_dict["items"]?.grid?.add_custom_button?.(
            __("💰 Tính giá"),
            () => {
                const selected = frm.fields_dict["items"]?.grid?.get_selected_children?.();
                if (selected && selected.length > 0 && selected[0].al_bom) {
                    new alumglass.BOMDialog(selected[0].name).show();
                } else {
                    frappe.msgprint(__("Dòng chưa chọn BOM"));
                }
            },
            __("AlumGlass")
        );
    },
});
