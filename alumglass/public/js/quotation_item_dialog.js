// AlumGlass — Quotation Item Dialog (dynamic từ AL Variable Set)
// Đọc danh sách biến từ Variable Set → tự sinh form fields
// Không hardcode field nào — mọi biến đều từ DB config
// v28.8: Thêm nút Preview tính toán, layout 3 cột

frappe.provide("alumglass.quotation");

alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    constructor(frm, child_doc) {
        this.frm = frm;
        this.child_doc = child_doc;
        this.extra_vars = [];       // dynamic extra variables table data
        this.preview_open = false;  // flag cho panel preview
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
                error: () => resolve([]),
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
        fields.push({ fieldname: "col_bom_1", fieldtype: "Column Break" });
        fields.push({
            fieldname: "al_bom_version", fieldtype: "Link", label: __("BOM Version"),
            options: "AL BOM Version",
            default: this.child_doc.al_bom_version || "",
            get_query: () => {
                const bom = this.dialog?.get_value("al_bom");
                if (bom) return { filters: { bom: bom } };
                return {};
            },
        });

        if (vars.length === 0) {
            // Không có Variable Set → hiển thị fallback: JSON textarea hoặc hướng dẫn
            const hasBom = !!this.child_doc.al_bom;
            fields.push({ fieldtype: "Section Break", label: __("Tham số sản phẩm") });
            if (hasBom) {
                fields.push({
                    fieldname: "al_bom_vars_raw", fieldtype: "Code", label: __("Variables (JSON)"),
                    options: "JSON",
                    default: JSON.stringify(existing, null, 2),
                    description: __("BOM này chưa có Variable Set. Nhập JSON thủ công hoặc chọn BOM khác."),
                });
            } else {
                fields.push({
                    fieldname: "_info", fieldtype: "HTML",
                    options: `<div style="padding:20px;text-align:center;color:#64748b;">
                        <p style="font-size:16px;">📐 ${__("Chọn BOM ở trên để bắt đầu")}</p>
                        <p style="font-size:12px;">${__("Hệ thống sẽ tự động sinh form tham số từ Variable Set của BOM.")}</p>
                    </div>`,
                });
            }
            return fields;
        }

        // ── Section: Biến từ Variable Set (layout tối đa 3 cột) ──
        const user_vars = vars.filter(v => !v.is_system);
        const sys_vars = vars.filter(v => v.is_system);

        fields.push({ fieldtype: "Section Break", label: __("Tham số sản phẩm") });
        let col = 0;
        const MAX_COLS = 3;
        user_vars.forEach((v, i) => {
            const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;

            if (col > 0) {
                fields.push({ fieldtype: "Column Break", fieldname: `col_var_${i}` });
            }

            const field = this._var_to_field(v, val);
            if (field) fields.push(field);

            col = (col + 1) % MAX_COLS;
        });

        // ── System variables (read-only, hiển thị sau) ─────────────
        if (sys_vars.length > 0) {
            fields.push({ fieldtype: "Section Break", label: __("Biến hệ thống (tự động)") });
            col = 0;
            sys_vars.forEach((v, i) => {
                const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;
                if (col > 0) {
                    fields.push({ fieldtype: "Column Break", fieldname: `col_sys_${i}` });
                }
                const field = this._var_to_field(v, val);
                if (field) {
                    field.read_only = 1;
                    fields.push(field);
                }
                col = (col + 1) % MAX_COLS;
            });
        }

        // ── Section: Biến mở rộng ──────────────────────────────────
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

        // ── Preview panel ──────────────────────────────────────────
        fields.push({ fieldtype: "Section Break", label: __("Kết quả Preview") });
        fields.push({
            fieldname: "preview_html",
            fieldtype: "HTML",
            label: "",
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
        // Tự động set version mới nhất
        frappe.db.get_value("AL BOM", bom, "current_version", r => {
            if (r?.current_version) this.dialog?.set_value("al_bom_version", r.current_version);
        });
        // Reload dialog với Variable Set của BOM mới
        this.child_doc.al_bom = bom;
        this._load_variable_set().then(vars => {
            const fields = this._build_dynamic_fields(vars);
            // Refresh dialog fields
            this.dialog.hide();
            this._render_dialog(fields);
        });
    }

    // ── Render dialog + dynamic table + preview ────────────────────
    _render_dialog(fields) {
        const self = this;
        this.dialog = new frappe.ui.Dialog({
            title: __("Tham số BOM — ") + (this.child_doc.item_name || this.child_doc.item_code || __("Dòng mới")),
            fields: fields,
            size: "large",
            primary_action_label: __("💾 Lưu"),
            primary_action: () => {
                this._save();
                this.dialog.hide();
            },
            secondary_action_label: __("🖥️ Preview tính giá"),
            secondary_action: () => {
                this._save();  // Lưu trước khi preview
                this._run_preview();
            },
        });
        this.dialog.show();

        // Render dynamic table SAU KHI dialog hiển thị
        setTimeout(() => {
            this._render_extra_vars_table();
            this._render_preview_panel();
        }, 300);
    }

    // ── Dynamic Table: Biến mở rộng ───────────────────────────────
    _render_extra_vars_table() {
        const $wrapper = $(this.dialog.$wrapper).find('[data-fieldname="extra_vars_html"]');
        if (!$wrapper.length) return;

        const self = this;
        const $container = $wrapper.find(".frappe-control[data-fieldname='extra_vars_html'] .control-input");
        if (!$container.length) return;

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
                        value="${self._esc_attr(row.var_name || "")}" placeholder="vd: he_so_an_toan"
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
                        value="${self._esc_attr(val_str)}" placeholder="Giá trị"
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

    // ── Preview Panel ──────────────────────────────────────────────
    _render_preview_panel() {
        const $wrapper = $(this.dialog.$wrapper).find('[data-fieldname="preview_html"]');
        if (!$wrapper.length) return;
        const $container = $wrapper.find(".frappe-control[data-fieldname='preview_html'] .control-input");
        if (!$container.length) return;

        $container.html(`<div style="padding:12px;text-align:center;color:#94a3b8;background:#f8fafc;border:1px dashed #d1d5db;border-radius:6px;">
            <span style="font-size:13px;">🖥️ ${__("Nhấn nút 'Preview tính giá' để xem kết quả")}</span>
        </div>`);
    }

    _run_preview() {
        // Hiển thị trạng thái loading
        const $container = $(this.dialog.$wrapper)
            .find(".frappe-control[data-fieldname='preview_html'] .control-input");
        if ($container.length) {
            $container.html(`<div style="padding:20px;text-align:center;">
                <span style="font-size:14px;color:#f59e0b;">⏳ ${__("Đang tính toán...")}</span>
            </div>`);
            // Scroll đến preview
            $container[0].scrollIntoView({ behavior: "smooth", block: "center" });
        }

        const self = this;
        // Lưu trước để đảm bảo BOM vars được persist
        this._save();

        // Nếu chưa có BOM, báo lỗi
        const bom = this.dialog?.get_value("al_bom") || this.child_doc.al_bom;
        if (!bom) {
            if ($container.length) {
                $container.html(`<div style="padding:12px;color:#ef4444;text-align:center;">
                    ❌ ${__("Vui lòng chọn BOM trước khi Preview")}
                </div>`);
            }
            return;
        }

        // Gọi API calculate_bom
        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: { quotation_item_name: this.child_doc.name },
            callback: (r) => {
                if ($container.length) {
                    if (r.message) {
                        $container.html(self._build_preview_html(r.message));
                    } else {
                        $container.html(`<div style="padding:12px;color:#ef4444;text-align:center;">
                            ❌ ${__("Không có kết quả. Kiểm tra lại tham số đầu vào.")}
                        </div>`);
                    }
                }
            },
            error: (err) => {
                if ($container.length) {
                    $container.html(`<div style="padding:12px;color:#ef4444;text-align:center;">
                        ❌ ${__("Lỗi tính toán: ")} ${self._esc_html(String(err || ""))}
                    </div>`);
                }
            },
        });
    }

    _build_preview_html(data) {
        let html = `<div class="bom-preview" style="font-size:12px;">`;

        // ── Cost Breakdown ────────────────────────────────────────
        if (data.cost_template && Object.keys(data.cost_template).length > 0) {
            html += `<h5 style="margin-top:0;color:#1e293b;">📊 ${__("Cost Breakdown")}</h5>`;
            html += `<table class="table table-condensed table-bordered" style="margin:0 0 12px 0;font-size:11px;">
                <thead style="background:#f1f5f9;"><tr>
                    <th>${__("Khoản mục")}</th>
                    <th class="text-right">${__("Thành tiền")}</th>
                </tr></thead><tbody>`;

            const keys = Object.keys(data.cost_template);
            const subtotal_keys = keys.filter(k =>
                k.startsWith("TONG_") || k.startsWith("GIA_") || k.startsWith("PROFIT") || k.startsWith("VAT"));
            const detail_keys = keys.filter(k => !subtotal_keys.includes(k));

            for (let key of [...detail_keys, ...subtotal_keys]) {
                const val = data.cost_template[key];
                const isBold = key.startsWith("TONG_") || key.startsWith("GIA_") || key === "PROFIT";
                html += `<tr class="${isBold ? 'font-weight-bold' : ''}" style="${isBold ? 'background:#fef3c7;' : ''}">
                    <td>${isBold ? '━━ ' : ''}${key}</td>
                    <td class="text-right">${format_currency(val || 0)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        }

        // ── Detail Lines ──────────────────────────────────────────
        if (data.lines && data.lines.length) {
            html += `<h5 style="color:#1e293b;">📋 ${__("Chi tiết dòng vật tư")} <span style="font-weight:normal;color:#94a3b8;font-size:11px;">(${data.lines.length} dòng)</span></h5>`;
            html += `<table class="table table-condensed table-striped table-bordered" style="margin:0;font-size:11px;">
                <thead style="background:#f1f5f9;"><tr>
                    <th>${__("Slug")}</th>
                    <th>${__("Item")}</th>
                    <th class="text-right">${__("W")}</th>
                    <th class="text-right">${__("H")}</th>
                    <th class="text-right">${__("Qty")}</th>
                    <th class="text-right">${__("Đơn giá")}</th>
                    <th class="text-right">${__("Thành tiền")}</th>
                </tr></thead><tbody>`;

            for (let line of data.lines) {
                html += `<tr>
                    <td><strong>${line.slug || ""}</strong></td>
                    <td>${line.item_code || ""}</td>
                    <td class="text-right">${line.width || ""}</td>
                    <td class="text-right">${line.height || ""}</td>
                    <td class="text-right">${line.qty || ""}</td>
                    <td class="text-right">${format_currency(line.unit_price || 0)}</td>
                    <td class="text-right"><strong>${format_currency(line.line_total || 0)}</strong></td>
                </tr>`;
            }

            html += `</tbody></table>`;
        }

        html += `</div>`;
        return html;
    }

    // ── Parse existing al_bom_vars JSON ────────────────────────────
    _parse_existing() {
        try { return JSON.parse(this.child_doc.al_bom_vars || "{}"); } catch (e) { return {}; }
    }

    // ── Escape helpers ────────────────────────────────────────────
    _esc_attr(str) {
        return String(str || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    _esc_html(str) {
        return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    _save() {
        const vals = this.dialog ? this.dialog.get_values() : {};
        const vars = {};

        // Thu thập tất cả biến từ form fields (động)
        Object.keys(vals).forEach(key => {
            if (!key.startsWith("col_") && key !== "al_bom" && key !== "al_bom_version"
                && key !== "extra_vars_html" && key !== "al_bom_vars_raw"
                && key !== "preview_html" && key !== "_info") {
                vars[key] = vals[key];
            }
        });

        // Thu thập extra vars từ dynamic table
        vars.extra_vars = {};
        this.extra_vars.forEach(row => {
            if (row.var_name && row.var_name.trim()) {
                let val = row.var_value;
                if (row.var_type === "Float" || row.var_type === "Int") {
                    val = parseFloat(val);
                    if (isNaN(val)) val = 0;
                } else if (row.var_type === "Check") {
                    val = val === "true" || val === "1" || val === true;
                }
                vars.extra_vars[row.var_name.trim()] = val;
            }
        });

        // Lưu vào Quotation Item
        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        if (cdn) {
            frappe.model.set_value(cdt, cdn, "al_bom_vars", JSON.stringify(vars, null, 2));
            if (vals.al_bom) frappe.model.set_value(cdt, cdn, "al_bom", vals.al_bom);
            if (vals.al_bom_version) frappe.model.set_value(cdt, cdn, "al_bom_version", vals.al_bom_version);
            // Cập nhật local child_doc để dialog dùng lại nếu cần
            this.child_doc.al_bom_vars = JSON.stringify(vars, null, 2);
            if (vals.al_bom) this.child_doc.al_bom = vals.al_bom;
            if (vals.al_bom_version) this.child_doc.al_bom_version = vals.al_bom_version;
        }
    }
};

// NOTE: Form event handlers for Quotation (toolbar buttons, row actions, double-click)
// are now centralized in doctype/overrides/quotation.js.
// This file only defines the alumglass.quotation.ItemParamDialog class.
