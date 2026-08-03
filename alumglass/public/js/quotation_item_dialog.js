// AlumGlass — Quotation Item Dialog (dynamic từ AL Variable Set)
// Đọc danh sách biến từ Variable Set → tự sinh form fields
// Không hardcode field nào — mọi biến đều từ DB config
// v28.7.1: Thay thế textarea "Biến bổ sung" bằng dynamic table

frappe.provide("alumglass.quotation");

alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    constructor(frm, child_doc) {
        this.frm = frm;
        this.child_doc = child_doc;
        this.extra_vars = [];       // dynamic extra variables table data
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
            fields.push({ fieldtype: "Section Break", label: __("Biến BOM (JSON)") });
            fields.push({
                fieldname: "al_bom_vars_raw", fieldtype: "Code", label: __("Variables (JSON)"),
                options: "JSON",
                default: JSON.stringify(existing, null, 2),
                description: __("Không tìm thấy Variable Set. Nhập JSON thủ công."),
            });
            return fields;
        }

        // ── Section: Biến từ Variable Set (hiển thị dạng form fields) ──
        const user_vars = vars.filter(v => !v.is_system);

        fields.push({ fieldtype: "Section Break", label: __("Tham số sản phẩm") });
        let col = 0;
        const types_need_column = ["Float", "Int", "Data"];
        user_vars.forEach((v, i) => {
            const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;

            if (col > 0 && types_need_column.includes(v.var_type)) {
                fields.push({ fieldtype: "Column Break", fieldname: `col_var_${i}` });
            }

            const field = this._var_to_field(v, val);
            if (field) fields.push(field);

            col = (col + 1) % 2;
        });

        // ── Section: Biến mở rộng (Dynamic Table — KHÔNG dùng textarea) ──
        fields.push({ fieldtype: "Section Break", label: __("Biến mở rộng (tùy chọn)") });
        fields.push({
            fieldname: "extra_vars_html",
            fieldtype: "HTML",
            label: "",
        });

        // Load extra vars từ existing
        const extra = existing.extra_vars || {};
        this.extra_vars = Object.entries(extra).map(([key, val]) => ({
            var_name: key,
            var_value: val,
        }));

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
                return { ...base, fieldtype: "Float", precision: "1" };
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

    // ── Render dialog + dynamic table ─────────────────────────────
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

        // Render dynamic table cho extra vars SAU KHI dialog hiển thị
        setTimeout(() => this._render_extra_vars_table(), 200);
    }

    // ── Dynamic Table: Biến mở rộng (thay thế textarea) ──────────
    _render_extra_vars_table() {
        const $wrapper = $(this.dialog.$wrapper).find('[data-fieldname="extra_vars_html"]');
        if (!$wrapper.length) return;

        const self = this;
        const $container = $wrapper.find(".frappe-control[data-fieldname='extra_vars_html'] .control-input") || $wrapper;

        function build_html() {
            let html = `<div class="al-extra-vars-table" style="border:1px solid #d1d5db;border-radius:6px;overflow:hidden;">
                <table class="table table-condensed" style="margin:0;background:#fff;">
                    <thead style="background:#f9fafb;">
                        <tr>
                            <th style="width:35%">${__("Tên biến")}</th>
                            <th style="width:10%">${__("Kiểu")}</th>
                            <th style="width:40%">${__("Giá trị")}</th>
                            <th style="width:15%;text-align:center">${__("Xóa")}</th>
                        </tr>
                    </thead>
                    <tbody>`;

            self.extra_vars.forEach((row, idx) => {
                const val_str = row.var_value !== undefined ? String(row.var_value) : "";
                html += `<tr>
                    <td><input type="text" class="form-control input-sm al-ev-name"
                        value="${row.var_name || ""}" placeholder="vd: he_so_an_toan"
                        data-idx="${idx}"></td>
                    <td>
                        <select class="form-control input-sm al-ev-type" data-idx="${idx}">
                            <option value="Data" ${!row.var_type || row.var_type === 'Data' ? 'selected' : ''}>Text</option>
                            <option value="Float" ${row.var_type === 'Float' ? 'selected' : ''}>Số</option>
                            <option value="Int" ${row.var_type === 'Int' ? 'selected' : ''}>Nguyên</option>
                            <option value="Check" ${row.var_type === 'Check' ? 'selected' : ''}>Check</option>
                        </select>
                    </td>
                    <td><input type="text" class="form-control input-sm al-ev-value"
                        value="${val_str}" placeholder="Giá trị"
                        data-idx="${idx}"></td>
                    <td style="text-align:center">
                        <button class="btn btn-xs btn-danger al-ev-del" data-idx="${idx}">
                            <i class="fa fa-trash"></i>
                        </button>
                    </td>
                </tr>`;
            });

            html += `</tbody></table>
                <div style="padding:8px;background:#f9fafb;border-top:1px solid #e5e7eb;">
                    <button class="btn btn-xs btn-primary al-ev-add">
                        <i class="fa fa-plus"></i> ${__("Thêm biến")}
                    </button>
                    <span class="text-muted small" style="margin-left:8px;">
                        ${__("Biến mở rộng dùng cho tham số không có trong Variable Set")}
                    </span>
                </div>
            </div>`;

            return html;
        }

        function bind_events() {
            $container.find(".al-ev-add").off("click").on("click", function () {
                self.extra_vars.push({ var_name: "", var_type: "Data", var_value: "" });
                refresh();
            });

            $container.find(".al-ev-del").off("click").on("click", function () {
                const idx = parseInt($(this).data("idx"));
                self.extra_vars.splice(idx, 1);
                refresh();
            });

            $container.find(".al-ev-name, .al-ev-type, .al-ev-value").off("change keyup").on("change keyup", function () {
                const idx = parseInt($(this).data("idx"));
                if (idx >= 0 && idx < self.extra_vars.length) {
                    if ($(this).hasClass("al-ev-name")) self.extra_vars[idx].var_name = $(this).val();
                    if ($(this).hasClass("al-ev-type")) self.extra_vars[idx].var_type = $(this).val();
                    if ($(this).hasClass("al-ev-value")) self.extra_vars[idx].var_value = $(this).val();
                }
            });
        }

        function refresh() {
            $container.html(build_html());
            bind_events();
        }

        refresh();
    }

    // ── Parse existing al_bom_vars JSON ────────────────────────────
    _parse_existing() {
        try { return JSON.parse(this.child_doc.al_bom_vars || "{}"); } catch (e) { return {}; }
    }

    _save() {
        const vals = this.dialog.get_values();
        const vars = {};

        // Thu thập tất cả biến từ form fields (động)
        Object.keys(vals).forEach(key => {
            if (!key.startsWith("col_") && key !== "al_bom" && key !== "al_bom_version"
                && key !== "extra_vars_html" && key !== "al_bom_vars_raw") {
                vars[key] = vals[key];
            }
        });

        // Thu thập extra vars từ dynamic table (thay vì parse text)
        vars.extra_vars = {};
        this.extra_vars.forEach(row => {
            if (row.var_name && row.var_name.trim()) {
                let val = row.var_value;
                // Auto-convert type
                if (row.var_type === "Float" || row.var_type === "Int") {
                    val = parseFloat(val);
                    if (isNaN(val)) val = 0;
                } else if (row.var_type === "Check") {
                    val = val === "true" || val === "1" || val === true;
                }
                vars.extra_vars[row.var_name.trim()] = val;
            }
        });

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
