// AlumGlass — Quotation Item Dialog (dynamic từ AL Variable Set)
// Đọc danh sách biến từ Variable Set → tự sinh form fields
// Không hardcode field nào — mọi biến đều từ DB config

frappe.provide("alumglass.quotation");

alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    constructor(frm, child_doc) {
        this.frm = frm;
        this.child_doc = child_doc;
    }

    show() {
        this._load_variable_set().then(vars => {
            const fields = this._build_dynamic_fields(vars);
            this._render_dialog(fields);
        });
    }

    // ── Đọc Variable Set từ BOM → Bom Set → Variable Set ──────────
    async _load_variable_set() {
        const bom = this.child_doc.al_bom;
        if (!bom) return [];

        return new Promise(resolve => {
            frappe.call({
                method: "alumglass.api.get_variable_set_for_bom",
                args: { bom_code: bom },
                callback: r => {
                    if (r.message?.variables) {
                        resolve(r.message.variables);
                    } else {
                        resolve([]);
                    }
                },
            });
        });
    }

    // ── Sinh fields động từ Variable Set items ────────────────────
    _build_dynamic_fields(vars) {
        const existing = this._parse_existing();
        const fields = [];

        // Section: Chọn BOM
        fields.push({ fieldtype: "Section Break", label: __("Chọn BOM") });
        fields.push({
            fieldname: "al_bom", fieldtype: "Link", label: __("BOM"),
            options: "AL BOM", default: this.child_doc.al_bom || "",
            onchange: () => this._on_bom_change(),
        });
        fields.push({ fieldname: "col_bom", fieldtype: "Column Break" });
        fields.push({
            fieldname: "al_bom_version", fieldtype: "Link", label: __("BOM Version"),
            options: "AL BOM Version", default: this.child_doc.al_bom_version || "",
        });

        if (vars.length === 0) {
            // Fallback: nếu không có Variable Set, hiển thị field JSON thô
            fields.push({ fieldtype: "Section Break", label: __("Biến BOM (JSON)") });
            fields.push({
                fieldname: "al_bom_vars_raw", fieldtype: "Code", label: __("Variables (JSON)"),
                options: "JSON",
                default: JSON.stringify(existing, null, 2),
                description: __("Không tìm thấy Variable Set. Nhập JSON thủ công."),
            });
            return fields;
        }

        // Section: Biến từ Variable Set
        fields.push({ fieldtype: "Section Break", label: __("Tham số đầu vào (từ Variable Set)") });
        let col = 0;
        const types_need_column = ["Float", "Int", "Data"];
        vars.filter(v => !v.is_system).forEach((v, i) => {
            const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;

            if (col > 0 && types_need_column.includes(v.var_type)) {
                fields.push({ fieldtype: "Column Break", fieldname: `col_var_${i}` });
            }

            const field = this._var_to_field(v, val);
            if (field) fields.push(field);

            col = (col + 1) % 2;
        });

        // Section: Tham số mở rộng (biến custom không có trong Variable Set)
        fields.push({ fieldtype: "Section Break", label: __("Tham số mở rộng") });
        fields.push({
            fieldname: "extra_vars_text", fieldtype: "Small Text",
            label: __("Biến bổ sung (mỗi dòng: tên_biến=giá_trị)"),
            default: this._extra_to_text(existing.extra_vars || {}),
            description: __("Dùng cho biến không có trong Variable Set. VD: he_so_an_toan=1.5"),
        });

        return fields;
    }

    // ── Map Variable Set item → Frappe form field ─────────────────
    _var_to_field(v, current_val) {
        const base = {
            fieldname: v.var_name,
            label: __(v.var_label || v.var_name),
            default: current_val !== undefined ? current_val : v.default_value,
            reqd: v.is_required || 0,
        };

        switch (v.var_type) {
            case "Float":
                return { ...base, fieldtype: "Float" };
            case "Int":
                return { ...base, fieldtype: "Int" };
            case "Data":
                return { ...base, fieldtype: "Data" };
            case "Select":
                return { ...base, fieldtype: "Select", options: v.select_options || "" };
            case "Link":
                return { ...base, fieldtype: "Link", options: v.link_doctype || "" };
            case "Check":
                return { ...base, fieldtype: "Check" };
            case "Currency":
                return { ...base, fieldtype: "Currency" };
            default:
                return { ...base, fieldtype: "Data" };
        }
    }

    _on_bom_change() {
        const bom = this.dialog?.get_value("al_bom");
        if (!bom) return;
        frappe.db.get_value("AL BOM", bom, "current_version", r => {
            if (r?.current_version) this.dialog?.set_value("al_bom_version", r.current_version);
        });
    }

    _render_dialog(fields) {
        this.dialog = new frappe.ui.Dialog({
            title: __("Tham số BOM — ") + (this.child_doc.item_name || this.child_doc.item_code || ""),
            fields: fields,
            size: "large",
            primary_action_label: __("💾 Lưu & Tính giá"),
            primary_action: () => {
                this._save();
                this.dialog.hide();
                if (this.child_doc.al_bom) new alumglass.BOMDialog(this.child_doc.name).show();
            },
        });
        this.dialog.show();
    }

    // ── Parse / Save ──────────────────────────────────────────────
    _parse_existing() {
        try { return JSON.parse(this.child_doc.al_bom_vars || "{}"); } catch (e) { return {}; }
    }
    _extra_to_text(extra) {
        if (!extra || typeof extra !== "object") return "";
        return Object.entries(extra).map(([k, v]) => `${k}=${v}`).join("\n");
    }
    _text_to_extra(text) {
        if (!text || !text.trim()) return {};
        const r = {};
        text.split("\n").forEach(line => {
            const idx = line.indexOf("=");
            if (idx > 0) {
                const key = line.substring(0, idx).trim();
                let val = line.substring(idx + 1).trim();
                if (/^-?\d+\.?\d*$/.test(val)) val = parseFloat(val);
                else if (val === "true") val = true; else if (val === "false") val = false;
                if (key) r[key] = val;
            }
        });
        return r;
    }
    _save() {
        const vals = this.dialog.get_values();
        const vars = {};

        // Thu thập tất cả biến từ dialog (động)
        Object.keys(vals).forEach(key => {
            if (!key.startsWith("col_") && key !== "al_bom" && key !== "al_bom_version"
                && key !== "extra_vars_text" && key !== "al_bom_vars_raw") {
                vars[key] = vals[key];
            }
        });

        // Thêm extra vars
        vars.extra_vars = this._text_to_extra(vals.extra_vars_text || "");

        // Lưu
        frappe.model.set_value(this.child_doc.doctype, this.child_doc.name,
            "al_bom_vars", JSON.stringify(vars, null, 2));
        if (vals.al_bom) frappe.model.set_value(this.child_doc.doctype, this.child_doc.name,
            "al_bom", vals.al_bom);
        if (vals.al_bom_version) frappe.model.set_value(this.child_doc.doctype, this.child_doc.name,
            "al_bom_version", vals.al_bom_version);
    }
};

// ── Grid buttons ──────────────────────────────────────────────────
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Nút trên toolbar — hoạt động trên dòng được chọn
        frm.add_custom_button(__("📐 Tham số BOM"), () => {
            const sel = frm.fields_dict["items"]?.grid?.get_selected_children?.();
            if (sel?.length) new alumglass.quotation.ItemParamDialog(frm, sel[0]).show();
            else frappe.msgprint(__("Chọn 1 dòng sản phẩm trước"));
        }, __("AlumGlass"));

        frm.add_custom_button(__("💰 Tính giá"), () => {
            const sel = frm.fields_dict["items"]?.grid?.get_selected_children?.();
            if (sel?.length && sel[0].al_bom) new alumglass.BOMDialog(sel[0].name).show();
            else frappe.msgprint(__("Dòng chưa chọn BOM"));
        }, __("AlumGlass"));

        // Double-click vào dòng → mở dialog tham số
        const grid = frm.fields_dict["items"]?.grid;
        if (grid?.grid_rows) {
            grid.grid_rows.forEach(row => {
                if (row._al_dblclick) return;
                row._al_dblclick = true;
                $(row.wrapper).on("dblclick", () => {
                    new alumglass.quotation.ItemParamDialog(frm, row.doc).show();
                });
            });
        }
    },

    // Sau khi thêm dòng mới → gắn double-click
    after_save(frm) {
        setTimeout(() => {
            const grid = frm.fields_dict["items"]?.grid;
            if (grid?.grid_rows) {
                grid.grid_rows.forEach(row => {
                    if (row._al_dblclick) return;
                    row._al_dblclick = true;
                    $(row.wrapper).on("dblclick", () => {
                        new alumglass.quotation.ItemParamDialog(frm, row.doc).show();
                    });
                });
            }
        }, 500);
    },
});
