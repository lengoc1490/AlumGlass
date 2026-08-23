// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Quotation override: Row buttons + ItemParamDialog + BOMDialog
// ═══════════════════════════════════════════════════════════════════════════
// Tổ chức theo eupapp: toàn bộ logic per-doctype nằm trong 1 file override
// load qua doctype_js của "Quotation" — KHÔNG load toàn trang qua app_include_js.
//
// ── ItemParamDialog ────────────────────────────────────────────────────────
//   Dialog tham số BOM cho TỪNG dòng con Quotation Item.
//   - Biến đầu vào render động từ Variable Set (alumglass.api.get_variable_set_for_bom)
//   - Layout 2 cột thoáng, không hardcode field nào
//   - Biến mở rộng = Table field chuẩn Frappe (add/delete row)
//   - Preview tính giá async (realtime "alumglass_bom_calc_done", spinner)
//   - Đổi BOM → chỉ re-render vùng biến trong dialog CŨ (không recreate dialog)
//
// ── BOMDialog ──────────────────────────────────────────────────────────────
//   Dialog kết quả tính giá BOM (tách từ public/js/bom_dialog.js, gộp vào đây)
// ═══════════════════════════════════════════════════════════════════════════

frappe.provide("alumglass");
frappe.provide("alumglass.quotation");

// ═══════════════════════════════════════════════════════════════════════════
// ItemParamDialog — dialog tham số BOM cho 1 dòng Quotation Item
// ═══════════════════════════════════════════════════════════════════════════
alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    constructor(frm, child_doc) {
        this.frm = frm;
        this.child_doc = child_doc;
        this.dialog = null;
        this._var_controls = [];    // [{ var_name, ctrl }] — controls biến động
        this._current_vars = [];    // Variable Set đang hiển thị
        this._realtime_handler = null;
    }

    show() {
        this._render_dialog();
    }

    // ── Đọc Variable Set từ BOM → Bom Set → Variable Set ──────────
    async _load_variable_set() {
        const bom = this.child_doc.al_bom;
        if (!bom) { this._bom_meta = null; return []; }

        return new Promise(resolve => {
            frappe.call({
                method: "alumglass.api.get_variable_set_for_bom",
                args: { bom_code: bom },
                callback: r => {
                    this._bom_meta = r.message || null;
                    if (r.message?.variables) {
                        resolve(r.message.variables);
                    } else {
                        resolve([]);
                    }
                },
                error: () => { this._bom_meta = null; resolve([]); },
            });
        });
    }

    // ── Fields cố định của dialog (BOM + vùng biến + extra_vars + preview) ──
    // Vùng biến động là 1 HTML container → re-render khi đổi BOM mà KHÔNG
    // phải tạo lại dialog (fix lỗi render liên tục).
    _build_dialog_fields() {
        return [
            { fieldtype: "Section Break", label: __("Chọn BOM") },
            {
                fieldname: "al_bom", fieldtype: "Link", label: __("BOM"),
                options: "AL BOM", default: this.child_doc.al_bom || "",
                onchange: () => this._on_bom_change(),
            },
            { fieldname: "col_bom_1", fieldtype: "Column Break" },
            {
                fieldname: "al_bom_version", fieldtype: "Link", label: __("BOM Version"),
                options: "AL BOM Version",
                default: this.child_doc.al_bom_version || "",
                get_query: () => {
                    const bom = this.dialog?.get_value("al_bom");
                    if (bom) return { filters: { bom: bom } };
                    return {};
                },
            },

            // Thông tin sản phẩm — các field read_only (ô đọc được), cập nhật khi đổi BOM
            // qua set_value + refresh (không tạo lại dialog, không dùng HTML blob cũ).
            { fieldtype: "Section Break", label: __("Thông tin sản phẩm") },
            { fieldname: "al_info_bom", fieldtype: "Data", label: __("BOM"), read_only: 1 },
            { fieldname: "al_info_variable_set", fieldtype: "Data", label: __("Variable Set"), read_only: 1 },
            { fieldname: "al_info_brand", fieldtype: "Data", label: __("Hãng nhôm"), read_only: 1 },
            { fieldname: "col_info_1", fieldtype: "Column Break" },
            { fieldname: "al_info_bom_set", fieldtype: "Data", label: __("Bom Set"), read_only: 1 },
            { fieldname: "al_info_profile_system", fieldtype: "Data", label: __("Hệ profile"), read_only: 1 },
            { fieldname: "al_info_accessory_set", fieldtype: "Data", label: __("Phụ kiện (Accessory Set)"), read_only: 1 },

            { fieldtype: "Section Break", label: __("Tham số sản phẩm") },
            { fieldname: "vars_container", fieldtype: "HTML", label: "" },

            { fieldtype: "Section Break", label: __("Biến mở rộng (tùy chọn)") },
            {
                fieldname: "extra_vars", fieldtype: "Table",
                label: __("Biến mở rộng (tùy chọn)"),
                fields: [
                    {
                        fieldname: "var_name", fieldtype: "Link", in_list_view: 1, label: __("Tên biến"),
                        options: "AL Variable Library",
                        get_query: () => ({ filters: { is_system: 0 } }),
                    },
                    {
                        fieldname: "var_type", fieldtype: "Select", in_list_view: 1, label: __("Kiểu"),
                        options: ["Data", "Float", "Int", "Select", "Link", "Check", "Currency"],
                    },
                    { fieldname: "var_value", fieldtype: "Data", in_list_view: 1, label: __("Giá trị") },
                ],
            },

            { fieldtype: "Section Break", label: __("Kết quả Preview") },
            { fieldname: "preview_html", fieldtype: "HTML", label: "" },
        ];
    }

    // ── Render dialog ───────────────────────────────────────────────
    _render_dialog() {
        this.dialog = new frappe.ui.Dialog({
            title: __("Tham số BOM — ") + (this.child_doc.item_name || this.child_doc.item_code || __("Dòng mới")),
            fields: this._build_dialog_fields(),
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
        this.dialog.$wrapper.find(".modal-dialog").css("max-width", "80vw");

        // Cleanup realtime listener khi dialog đóng (tránh leak)
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => this._cleanup_realtime());

        // Nạp extra vars từ al_bom_vars hiện có (Table field chuẩn Frappe)
        this._populate_extra_vars();
        this._setup_extra_vars_autofill();

        // Load Variable Set → render vùng biến động (KHÔNG recreate dialog)
        this._load_variable_set().then(vars => {
            this._current_vars = vars;
            this._render_vars_container(vars);
            this._render_bom_info();
        });

        setTimeout(() => this._render_preview_panel(), 300);
    }

    // ── Cập nhật thông tin sản phẩm (read-only fields) khi đổi BOM ──
    // Thay HTML blob cũ bằng các field Data read_only riêng biệt trong Section
    // "Thông tin sản phẩm" — set_value + refresh, KHÔNG tạo lại dialog.
    _render_bom_info() {
        if (!this.dialog) return;
        const m = this._bom_meta || null;
        const set = (fieldname, value) => {
            const ctrl = this.dialog.fields_dict[fieldname];
            if (ctrl && ctrl.set_value) ctrl.set_value(value);
        };
        if (!m || !m.bom_code) {
            set("al_info_bom", "—");
            set("al_info_bom_set", "—");
            set("al_info_variable_set", "—");
            set("al_info_profile_system", "—");
            set("al_info_brand", "—");
            set("al_info_accessory_set", "—");
            return;
        }
        set("al_info_bom", m.bom_name ? `${m.bom_name} (${m.bom_code})` : m.bom_code);
        set("al_info_bom_set", m.bom_set_name ? `${m.bom_set_name} (${m.bom_set_code})` : "—");
        set("al_info_variable_set", m.variable_set_name ? `${m.variable_set_name} (${m.variable_set_code})` : "—");
        set("al_info_profile_system", m.profile_system_name ? `${m.profile_system_name} (${m.profile_system_code})` : "—");
        set("al_info_brand", m.brand || "—");
        // Phụ kiện hiển thị tên bộ phụ kiện (không kèm code) — theo spec Owner.
        set("al_info_accessory_set", m.accessory_set_name || "—");
    }

    // ── Auto-fill var_type (và options) khi chọn var_name từ Library ──
    _setup_extra_vars_autofill() {
        if (!this.dialog) return;
        const table_field = this.dialog.fields_dict["extra_vars"];
        if (!table_field || !table_field.grid) return;
        const grid = table_field.grid;

        const self = this;
        // Event delegation — bắt cả row mới thêm sau khi refresh
        $(grid.wrapper)
            .off("change.autofill awesomplete-selectcomplete.autofill", "[data-fieldname='var_name']")
            .on("change.autofill awesomplete-selectcomplete.autofill", "[data-fieldname='var_name']", function () {
                const $row = $(this).closest(".grid-row");
                const idx = parseInt($row.attr("data-idx") || "0", 10);
                if (!idx) return;
                const row_doc = (table_field.df.data || [])[idx - 1];
                if (!row_doc || !row_doc.var_name) return;

                frappe.db.get_value("AL Variable Library", row_doc.var_name,
                    ["var_type", "select_options", "link_doctype"], (r) => {
                        if (!r) return;
                        const grid_row = (grid.grid_rows || []).find(gr => gr.idx === idx);
                        const type_ctrl = grid_row && grid_row.fields_dict && grid_row.fields_dict.var_type;
                        if (type_ctrl && type_ctrl.set_value) {
                            type_ctrl.set_value(r.var_type || "Data");
                        } else {
                            row_doc.var_type = r.var_type || "Data";
                            if (grid.refresh_row) grid.refresh_row(idx);
                        }
                        // Lưu options phụ vào row (Select/Link dùng lại khi save/preview)
                        row_doc.select_options = r.select_options || "";
                        row_doc.link_doctype = r.link_doctype || "";
                    });
            });
    }

    // ── Map Variable Set item → Frappe form field ─────────────────
    _var_to_field(v, current_val) {
        const base = {
            fieldname: "al_var_" + v.var_name,
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

    // ── Render vùng biến động vào HTML container (3 cột thoáng) ──
    _render_vars_container(vars) {
        const $container = this._vars_container();
        if (!$container.length) return;

        // Hủy controls cũ (khi đổi BOM → re-render)
        this._var_controls = [];
        $container.empty();

        const existing = this._parse_existing();
        const user_vars = (vars || []).filter(v => !v.is_system);
        const sys_vars = (vars || []).filter(v => v.is_system);

        // Chưa có Variable Set / chưa chọn BOM → hướng dẫn (dùng bảng Biến mở rộng)
        if (!(vars && vars.length)) {
            const hasBom = !!this.child_doc.al_bom;
            $container.html(`<div style="padding:16px;text-align:center;color:#64748b;background:#f8fafc;border:1px dashed #d1d5db;border-radius:6px;">
                <p style="margin:0 0 4px;font-size:14px;">${hasBom ? __("BOM này chưa có Variable Set.") : __("Chọn BOM ở trên để bắt đầu")}</p>
                <p style="margin:0;font-size:12px;">${hasBom ? __("Dùng bảng 'Biến mở rộng' bên dưới để thêm tham số.") : __("Hệ thống sẽ tự động sinh form tham số từ Variable Set của BOM.")}</p>
            </div>`);
            return;
        }

        // ── Biến đầu vào (user) — 3 cột ──
        if (user_vars.length) {
            $container.append(`<div style="font-weight:600;color:#1e293b;font-size:12.5px;margin:4px 0 8px;">${__("Biến đầu vào")}</div>`);
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $container.append($grid);
            user_vars.forEach(v => {
                const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;
                const df = this._var_to_field(v, val);
                if (df) this._make_var_control($grid, v, df);
            });
        }

        // ── Biến hệ thống (hiển thị sau, cho phép chỉnh sửa) ──
        if (sys_vars.length) {
            $container.append(`<div style="font-weight:600;color:#1e293b;font-size:12.5px;margin:10px 0 8px;">${__("Biến hệ thống (tự động)")}</div>`);
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $container.append($grid);
            sys_vars.forEach(v => {
                const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;
                const df = this._var_to_field(v, val);
                if (df) this._make_var_control($grid, v, df);
            });
        }
    }

    // ── Tạo 1 control biến động bằng make_control (pattern eupapp) ──
    _make_var_control($grid, v, df) {
        const $cell = $('<div style="min-width:0;"></div>');
        $grid.append($cell);

        const ctrl = frappe.ui.form.make_control({
            df: df,
            parent: $cell[0],
            only_input: false,
        });
        ctrl.make_input();
        ctrl.refresh();

        // Set giá trị hiện tại sau khi render
        const val = df.default;
        if (val !== undefined && val !== null && val !== "") {
            ctrl.set_value(val);
        }

        this._var_controls.push({ var_name: v.var_name, ctrl });
    }

    // ── Nạp extra_vars từ al_bom_vars hiện có vào Table field ──────
    _populate_extra_vars() {
        if (!this.dialog) return;
        const table_field = this.dialog.fields_dict["extra_vars"];
        if (!table_field) return;

        const existing = this._parse_existing();
        const extra = existing.extra_vars && typeof existing.extra_vars === "object"
            ? existing.extra_vars : {};

        const rows = Object.entries(extra).map(([key, val]) => ({
            var_name: key,
            var_type: this._guess_var_type(val),
            var_value: typeof val === "boolean" ? (val ? "1" : "0")
                : (val === undefined || val === null ? "" : String(val)),
        }));

        table_field.df.data = rows;
        if (table_field.grid) table_field.grid.refresh();
    }

    // ── Đoán kiểu biến mở rộng khi đọc lại từ al_bom_vars ─────────
    _guess_var_type(val) {
        if (typeof val === "boolean") return "Check";
        if (typeof val === "number") {
            return Number.isInteger(val) ? "Int" : "Float";
        }
        return "Data";
    }

    // ── Đổi BOM: re-render vùng biến trong dialog CŨ (không recreate) ──
    _on_bom_change() {
        const bom = this.dialog?.get_value("al_bom");
        if (!bom) return;
        // Tự động set version mới nhất
        frappe.db.get_value("AL BOM", bom, "current_version", r => {
            if (r?.current_version) this.dialog?.set_value("al_bom_version", r.current_version);
        });
        this.child_doc.al_bom = bom;
        // Chỉ re-render vùng biến + thông tin BOM — dialog giữ nguyên vị trí/kích thước,
        // không giật, không tạo dialog mới, không reset preview.
        this._load_variable_set().then(vars => {
            this._current_vars = vars;
            this._render_vars_container(vars);
            this._render_bom_info();
        });
    }

    // ── HTML container chứa vùng biến động ─────────────────────────
    _vars_container() {
        if (!this.dialog) return $();
        const field = this.dialog.fields_dict["vars_container"];
        return field ? field.$wrapper : $();
    }

    // ── Preview Panel ──────────────────────────────────────────────
    _render_preview_panel() {
        const $container = this._preview_container();
        if (!$container.length) return;

        // Mở lại panel → đọc trạng thái đã lưu trên item, không gọi lại API
        const status = this.child_doc.al_calc_status;

        if (status === "Success" && this.child_doc.al_bom_result) {
            let data = null;
            try { data = JSON.parse(this.child_doc.al_bom_result); } catch (e) { /* ignore */ }
            if (data) {
                $container.html(this._build_preview_html(data));
                return;
            }
        }

        if (status === "Queued" || status === "Running") {
            const job_id = this.child_doc.al_calc_job_id;
            $container.html(this._preview_progress_html(
                __("BOM đang tính trong nền — kết quả sẽ hiện tự động khi xong...")
            ));
            if (job_id) this._listen_realtime(job_id, $container);
            return;
        }

        if (status === "Failed") {
            $container.html(this._preview_error_html(this.child_doc.al_calc_error || ""));
            return;
        }

        $container.html(`<div style="padding:12px;text-align:center;color:#94a3b8;background:#f8fafc;border:1px dashed #d1d5db;border-radius:6px;">
            <span style="font-size:13px;">🖥️ ${__("Nhấn nút 'Preview tính giá' để xem kết quả")}</span>
        </div>`);
    }

    // ── Realtime cho async BOM (lọc theo job_id) ───────────────────
    _listen_realtime(job_id, $container) {
        this._cleanup_realtime();
        const self = this;
        this._realtime_handler = function (data) {
            if (!data || data.job_id !== job_id) return;
            self._cleanup_realtime();
            if (!$container || !$container.length) $container = self._preview_container();

            if (data.status === "Success") {
                const result_json = data.result ? JSON.stringify(data.result) : null;
                if (self.child_doc.name) {
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_calc_status", "Success");
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_bom_result", result_json);
                }
                self.child_doc.al_calc_status = "Success";
                self.child_doc.al_bom_result = result_json;
                $container.html(self._build_preview_html(data.result || {}));
                frappe.show_alert({ message: __("Tính giá xong"), indicator: "green" });
            } else {
                if (self.child_doc.name) {
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_calc_status", "Failed");
                }
                self.child_doc.al_calc_status = "Failed";
                self.child_doc.al_calc_error = data.error || "";
                $container.html(self._preview_error_html(data.error || ""));
            }
        };
        frappe.realtime.on("alumglass_bom_calc_done", this._realtime_handler);
    }

    _cleanup_realtime() {
        if (this._realtime_handler) {
            frappe.realtime.off("alumglass_bom_calc_done", this._realtime_handler);
            this._realtime_handler = null;
        }
    }

    _preview_container() {
        if (!this.dialog) return $();
        const field = this.dialog.fields_dict["preview_html"];
        return field ? field.$wrapper : $();
    }

    _preview_progress_html(message) {
        return `<div style="padding:20px;text-align:center;color:#64748b;">
            <i class="fa fa-spinner fa-spin" style="font-size:18px;color:#f59e0b;"></i>
            <p style="margin-top:10px;font-size:13px;">${message || __("Đang tính BOM trong nền...")}</p>
        </div>`;
    }

    _preview_error_html(error) {
        const safe_error = error ? this._esc_html(String(error)) : "";
        return `<div style="padding:12px;color:#ef4444;text-align:center;">
            ❌ ${__("Tính giá thất bại")}
            ${safe_error ? `<pre style="margin-top:8px;font-size:11px;max-height:200px;overflow:auto;text-align:left;">${safe_error}</pre>` : ""}
        </div>`;
    }

    _run_preview() {
        // Hiển thị trạng thái loading
        const $container = this._preview_container();
        if ($container.length) {
            $container.html(this._preview_progress_html(__("Đang tính toán...")));
            $container[0].scrollIntoView({ behavior: "smooth", block: "center" });
        }

        const self = this;
        // Lưu trước để đảm bảo BOM vars được persist
        this._save();

        // Nếu chưa có BOM, báo lỗi
        const bom = this.dialog?.get_value("al_bom") || this.child_doc.al_bom;
        if (!bom) {
            if ($container.length) {
                $container.html(this._preview_error_html(__("Vui lòng chọn BOM trước khi Preview")));
            }
            return;
        }

        // Gọi API calculate_bom
        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: { quotation_item_name: this.child_doc.name },
            callback: (r) => {
                if (!$container.length) return;
                if (r.message) {
                    if (r.message.async) {
                        // BOM lớn — job đã enqueue, chờ realtime event
                        $container.html(this._preview_progress_html(
                            r.message.message || __("Đang tính BOM lớn trong nền — có thể mất vài phút...")
                        ));
                        if (self.child_doc.name) {
                            frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                self.child_doc.name, "al_calc_status", "Queued");
                            if (r.message.job_id) {
                                frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                    self.child_doc.name, "al_calc_job_id", r.message.job_id);
                            }
                        }
                        self.child_doc.al_calc_status = "Queued";
                        self.child_doc.al_calc_job_id = r.message.job_id;
                        self._listen_realtime(r.message.job_id, $container);
                    } else {
                        // BOM nhỏ/vừa — kết quả trả về ngay
                        self.child_doc.al_calc_status = "Success";
                        if (self.child_doc.name) {
                            frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                self.child_doc.name, "al_calc_status", "Success");
                            frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                self.child_doc.name, "al_bom_result", JSON.stringify(r.message));
                        }
                        self.child_doc.al_bom_result = JSON.stringify(r.message);
                        $container.html(self._build_preview_html(r.message));
                    }
                } else {
                    $container.html(this._preview_error_html(__("Không có kết quả. Kiểm tra lại tham số đầu vào.")));
                }
            },
            error: (err) => {
                if ($container.length) {
                    $container.html(this._preview_error_html(String(err || "")));
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

        // ── Cost Buckets ──────────────────────────────────────────
        if (data.buckets && Object.keys(data.buckets).length > 0) {
            html += `<h5 style="margin-top:8px;color:#1e293b;">🗂️ ${__("Cost Buckets")}</h5>`;
            html += `<table class="table table-condensed table-bordered" style="margin:0 0 12px 0;font-size:11px;">
                <thead style="background:#f1f5f9;"><tr>
                    <th>${__("Bucket")}</th>
                    <th class="text-right">${__("Thành tiền")}</th>
                </tr></thead><tbody>`;

            for (let [key, val] of Object.entries(data.buckets)) {
                html += `<tr>
                    <td>${key}</td>
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

    // ── Escape helper ─────────────────────────────────────────────
    _esc_html(str) {
        return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    _save() {
        const vars = {};

        // ── Thu thập biến từ controls động (Variable Set) ─────────
        this._var_controls.forEach(({ var_name, ctrl }) => {
            let val = ctrl.get_value();
            if (val !== undefined && val !== null && val !== "") {
                vars[var_name] = val;
            }
        });

        // ── Thu thập extra vars từ Table field chuẩn Frappe ────────
        vars.extra_vars = {};
        const extra_rows = this.dialog ? (this.dialog.fields_dict["extra_vars"]?.df.data || []) : [];
        (extra_rows || []).forEach(row => {
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

        // ── Lưu vào Quotation Item ─────────────────────────────────
        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        if (cdn) {
            const bom = this.dialog?.get_value("al_bom");
            const version = this.dialog?.get_value("al_bom_version");
            frappe.model.set_value(cdt, cdn, "al_bom_vars", JSON.stringify(vars, null, 2));
            if (bom) frappe.model.set_value(cdt, cdn, "al_bom", bom);
            if (version) frappe.model.set_value(cdt, cdn, "al_bom_version", version);
            // Cập nhật local child_doc để dialog dùng lại nếu cần
            this.child_doc.al_bom_vars = JSON.stringify(vars, null, 2);
            if (bom) this.child_doc.al_bom = bom;
            if (version) this.child_doc.al_bom_version = version;
        }
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// BOMDialog — dialog kết quả tính giá BOM (tách từ public/js/bom_dialog.js)
// ═══════════════════════════════════════════════════════════════════════════
alumglass.BOMDialog = class BOMDialog {
    constructor(quotation_item_name) {
        this.quotation_item_name = quotation_item_name;
        this.dialog = null;
        this._realtime_handler = null;
    }

    show() {
        this.dialog = new frappe.ui.Dialog({
            title: __("BOM Calculation Result"),
            fields: [
                {
                    fieldname: "result_html",
                    fieldtype: "HTML",
                }
            ],
            size: "large",
            primary_action_label: __("Close"),
            primary_action: () => this.dialog.hide(),
        });

        // Cleanup listener khi dialog đóng (tránh leak realtime handler)
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => this._cleanup_realtime());

        this._load_existing_state();
    }

    // ── Mở lại: đọc trạng thái đã lưu trên Quotation Item ───────────
    _load_existing_state() {
        const self = this;
        frappe.db.get_value("Quotation Item", this.quotation_item_name, [
            "al_calc_status", "al_calc_job_id", "al_bom_result", "al_calc_error",
        ], (r) => {
            if (r) {
                if (r.al_calc_status === "Success" && r.al_bom_result) {
                    // Kết quả đã lưu — render luôn, KHÔNG gọi lại API
                    let data = null;
                    try { data = JSON.parse(r.al_bom_result); } catch (e) { /* ignore */ }
                    if (data) { this.render_results(data); return; }
                }
                if (r.al_calc_status === "Queued" || r.al_calc_status === "Running") {
                    // Đang tính trong nền — không gọi lại, chỉ chờ realtime
                    this._show_async_progress(
                        r.al_calc_job_id,
                        __("BOM đang tính trong nền — kết quả sẽ hiện tự động khi xong...")
                    );
                    this._listen_realtime(r.al_calc_job_id);
                    return;
                }
                if (r.al_calc_status === "Failed") {
                    this._render_error(r.al_calc_error || "");
                    return;
                }
            }
            // Chưa có trạng thái (chưa tính) → gọi API như bình thường
            this.calculate();
        });
    }

    calculate() {
        const self = this;
        this._show_loading(__("Đang tính giá..."));

        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: {
                quotation_item_name: this.quotation_item_name,
            },
            callback: (r) => {
                if (!r.message) {
                    self._render_error(__("Không có kết quả trả về."));
                    return;
                }
                if (r.message.async) {
                    // BOM lớn — job đã enqueue, chờ realtime event
                    self._show_async_progress(r.message.job_id, r.message.message);
                    self._listen_realtime(r.message.job_id);
                } else {
                    // BOM nhỏ/vừa — kết quả trả về ngay
                    self.render_results(r.message);
                }
            },
            error: (err) => {
                self._render_error(String(err || ""));
            },
        });
    }

    // ── Realtime: lắng nghe kết quả job async (lọc theo job_id) ─────
    _listen_realtime(job_id) {
        this._cleanup_realtime();
        const self = this;
        this._realtime_handler = function (data) {
            if (!data || data.job_id !== job_id) return;  // không phải job của dialog này
            self._cleanup_realtime();  // nhận kết quả → huỷ listener

            if (data.status === "Success") {
                frappe.show_alert({
                    message: __("Tính giá xong cho {0}", [self.quotation_item_name]),
                    indicator: "green",
                });
                self.render_results(data.result);
            } else {
                self._render_error(data.error || "");
            }
        };
        frappe.realtime.on("alumglass_bom_calc_done", this._realtime_handler);
    }

    _cleanup_realtime() {
        if (this._realtime_handler) {
            frappe.realtime.off("alumglass_bom_calc_done", this._realtime_handler);
            this._realtime_handler = null;
        }
    }

    // ── Loading / Async / Error states ──────────────────────────────
    _show_loading(message) {
        this._set_html(`<div class="text-center" style="padding:30px;">
            <i class="fa fa-spinner fa-spin" style="font-size:20px;color:#f59e0b;"></i>
            <p style="margin-top:10px;color:#64748b;">${message || __("Đang tính giá...")}</p>
        </div>`);
    }

    _show_async_progress(job_id, message) {
        this._set_html(`<div class="alert alert-info" style="margin-bottom:0;"
            data-job="${frappe.utils.escape_html(job_id || "")}">
            <i class="fa fa-spinner fa-spin"></i>
            ${message || __("Đang tính BOM lớn trong nền — có thể mất vài phút...")}
        </div>`);
    }

    _render_error(error) {
        const safe_error = error ? frappe.utils.escape_html(String(error)) : "";
        this._set_html(`<div class="alert alert-danger" style="margin-bottom:0;">
            <strong>${__("Tính giá thất bại")}</strong><br>
            ${__("Xem chi tiết trong Error Log hoặc trường AL Calc Error trên Quotation Item.")}
            ${safe_error ? `<pre style="margin-top:8px;font-size:11px;max-height:200px;overflow:auto;">${safe_error}</pre>` : ""}
        </div>`);
    }

    _set_html(html) {
        if (this.dialog) {
            this.dialog.set_value("result_html", html);
            this.dialog.show();
        }
    }

    // ── Render kết quả (sync hoặc async Success) ────────────────────
    render_results(data) {
        data = data || {};
        let html = `<div class="bom-result">`;
        html += `<h3>${__("BOM Calculation Results")}</h3>`;

        // ── Cost Template Summary (DYNAMIC từ response) ────────────
        if (data.cost_template && Object.keys(data.cost_template).length > 0) {
            html += `<h4>${__("Cost Breakdown")}</h4>`;
            html += `<table class="table table-bordered table-striped">
                <thead><tr>
                    <th>${__("Line Item")}</th>
                    <th class="text-right">${__("Amount")}</th>
                </tr></thead><tbody>`;

            const keys = Object.keys(data.cost_template);
            const subtotal_keys = keys.filter(k =>
                k.startsWith("TONG_") || k.startsWith("GIA_") || k.startsWith("PROFIT") || k.startsWith("VAT"));
            const detail_keys = keys.filter(k => !subtotal_keys.includes(k));

            for (let key of [...detail_keys, ...subtotal_keys]) {
                const val = data.cost_template[key];
                const is_subtotal = key.startsWith("TONG_") || key.startsWith("GIA_") || key === "PROFIT";
                const row_class = is_subtotal ? "font-weight-bold" : "";
                const prefix = is_subtotal ? "━━ " : "";
                html += `<tr class="${row_class}">
                    <td>${prefix}${__(key)}</td>
                    <td class="text-right">${format_currency(val || 0)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p class="text-muted">${__("Không có Cost Template trong kết quả.")}</p>`;
        }

        // ── Bucket Summary ──────────────────────────────────────────
        if (data.buckets && Object.keys(data.buckets).length > 0) {
            html += `<h4>${__("Cost Buckets")}</h4>`;
            html += `<table class="table table-bordered table-striped">
                <thead><tr>
                    <th>${__("Bucket")}</th>
                    <th class="text-right">${__("Amount")}</th>
                </tr></thead><tbody>`;

            for (let [key, val] of Object.entries(data.buckets)) {
                html += `<tr>
                    <td>${key}</td>
                    <td class="text-right">${format_currency(val)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        }

        // ── Detail Lines ────────────────────────────────────────────
        if (data.lines && data.lines.length) {
            html += `<h4>${__("Detail Lines")}</h4>`;
            html += `<table class="table table-striped table-bordered">
                <thead>
                    <tr>
                        <th>${__("Slug")}</th>
                        <th>${__("Item")}</th>
                        <th>${__("W")}</th>
                        <th>${__("H")}</th>
                        <th>${__("Qty")}</th>
                        <th>${__("Unit Qty")}</th>
                        <th class="text-right">${__("Line Total")}</th>
                    </tr>
                </thead>
                <tbody>`;

            for (let line of data.lines) {
                html += `<tr>
                    <td>${line.slug}</td>
                    <td>${line.item_code || ""}</td>
                    <td>${line.width || ""}</td>
                    <td>${line.height || ""}</td>
                    <td>${line.qty || ""}</td>
                    <td>${line.unit_qty || ""}</td>
                    <td class="text-right">${format_currency(line.line_total || 0)}</td>
                </tr>`;
            }

            html += `</tbody></table>`;
        }

        html += `</div>`;
        this._set_html(html);
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// Form handlers — nút theo TỪNG DÒNG con Quotation Item (không nút toolbar)
// ═══════════════════════════════════════════════════════════════════════════
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        // Row-level buttons + double-click (mỗi dòng mở dialog cho chính dòng đó)
        _attach_row_actions(frm);
        // Grid render rows SAU refresh → retry có kiểm soát để nút xuất hiện ngay
        // khi mở form có dòng sẵn (V5 — Owner: "phải add dòng/reload mới thấy nút").
        _schedule_row_actions_retry(frm);

        alumglass.grid_placeholder.set_column({ frm, parentfield: 'items' },
            'item_code', __('Chọn Asset Category'));
    },

    after_save(frm) {
        setTimeout(() => _attach_row_actions(frm), 600);
    },
});

frappe.ui.form.on("Quotation Item", {
    // Dòng mới thêm → gắn nút hành động
    items_add(frm) {
        setTimeout(() => _attach_row_actions(frm), 200);
    },

    // Form con mở rộng của dòng → thêm nút "Tham số BOM" + "Preview tính giá"
    form_render(innerFrm, cdt, cdn) {
        // Chỉ xử lý trong context của form Quotation
        if (!innerFrm || innerFrm.doctype !== "Quotation") return;
        const row = frappe.get_doc("Quotation Item", cdn);
        if (!row) return;

        setTimeout(() => {
            const gridBody = $(`.grid-row[data-name="${cdn}"] .grid-form-body`);
            if (gridBody.length && !gridBody.find(".al-form-btn").length) {
                const $formBtns = $(`<div class="al-form-btn" style="padding:6px 0;border-top:1px solid #e5e7eb;margin-top:8px;">
                    <button class="btn btn-sm btn-primary al-btn-params">
                        📐 ${__("Tham số BOM")}
                    </button>
                    <button class="btn btn-sm btn-default al-btn-preview">
                        🖥️ ${__("Preview tính giá")}
                    </button>
                </div>`);
                $formBtns.find(".al-btn-params").on("click", function () {
                    new alumglass.quotation.ItemParamDialog(innerFrm, row).show();
                });
                $formBtns.find(".al-btn-preview").on("click", function () {
                    if (!row.al_bom) {
                        frappe.msgprint(__("Chưa chọn BOM. Vui lòng mở Tham số BOM trước."));
                        return;
                    }
                    // Lưu trước rồi preview
                    frappe.model.set_value(cdt, cdn, "al_bom_vars",
                        JSON.stringify(_collect_form_vars(innerFrm, cdn) || {}));
                    new alumglass.BOMDialog(cdn).show();
                });
                gridBody.prepend($formBtns);
            }
        }, 400);
    },
});

// ── Retry attach row actions (grid render xong mới có .grid-row) ─────
// V5: mở form có dòng sẵn → refresh chạy trước khi grid render rows → nút chưa gắn.
// Retry ~0.5s tối đa 10 lần (~5s) rồi dừng; `_attach_row_actions` idempotent
// (guard `data("_al_btn")` + `.al-row-actions`) nên gọi lặp an toàn, không nhân đôi nút.
let _alRowActionsTimer = null;
function _schedule_row_actions_retry(frm, maxAttempts = 10) {
    if (_alRowActionsTimer) {
        clearInterval(_alRowActionsTimer);
        _alRowActionsTimer = null;
    }
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid) return;

    let attempts = 0;
    const deadline = Date.now() + maxAttempts * 500;
    _alRowActionsTimer = setInterval(() => {
        attempts += 1;
        _attach_row_actions(frm);

        // Dừng sớm khi mọi row đã gắn nút (guard idempotent đã chống nhân đôi)
        const $grid = grid.wrapper ? $(grid.wrapper) : $(grid.$wrapper);
        const rows = $grid.find(".grid-row");
        const attached = rows.filter((i, el) => $(el).find(".al-row-actions").length).length;
        const allAttached = rows.length && attached === rows.length;

        if (allAttached || attempts >= maxAttempts || Date.now() >= deadline) {
            clearInterval(_alRowActionsTimer);
            _alRowActionsTimer = null;
        }
    }, 500);
}

// ── Gắn button + double-click cho từng dòng trong bảng Items ────────
function _attach_row_actions(frm) {
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid) return;

    // Dùng grid.wrapper để bắt cả row render sau
    const $grid = grid.wrapper ? $(grid.wrapper) : $(grid.$wrapper);
    if (!$grid.length) return;

    $grid.find(".grid-row").each(function () {
        const $row = $(this);
        if ($row.data("_al_btn")) return;
        $row.data("_al_btn", true);

        // Nhóm 2 nút 📐 (tham số BOM) + 🖥️ (Preview tính giá) ở GÓC PHẢI cell item_code —
        // hiển thị THƯỜNG TRỰC ngoài form, user bấm ngay không cần mở rộng dòng.
        // Cell item_code thành flex → text trái, nút bên phải (giống row action buttons).
        const $itemCell = $row.find('.grid-static-col[data-fieldname="item_code"]');
        const $targetCell = $itemCell.length ? $itemCell : $row.find(".grid-static-col:first");
        if ($targetCell.length && !$targetCell.find(".al-row-actions").length) {
            const $actions = $(`<span class="al-row-actions" style="display:inline-flex;align-items:center;gap:2px;white-space:nowrap;flex-shrink:0;">
                <button class="al-row-params btn btn-xs btn-default"
                    title="${__("Mở tham số BOM")}"
                    style="padding:0 4px;font-size:11px;line-height:18px;">📐</button>
                <button class="al-row-preview btn btn-xs btn-default"
                    title="${__("Preview tính giá")}"
                    style="padding:0 4px;font-size:11px;line-height:18px;">🖥️</button>
            </span>`);
            $actions.find(".al-row-params").on("click", function (e) {
                e.stopPropagation();
                e.preventDefault();
                const rowDoc = _get_row_doc(frm, $row);
                if (rowDoc) new alumglass.quotation.ItemParamDialog(frm, rowDoc).show();
            });
            $actions.find(".al-row-preview").on("click", function (e) {
                e.stopPropagation();
                e.preventDefault();
                const rowDoc = _get_row_doc(frm, $row);
                if (!rowDoc) return;
                if (!rowDoc.al_bom) {
                    frappe.msgprint(__("Chưa chọn BOM. Vui lòng mở 📐 Tham số BOM trước."));
                    return;
                }
                new alumglass.BOMDialog(rowDoc.name).show();
            });
            // Text (static_area) co dãn đẩy nút về góc phải; khi row mở rộng (editable)
            // field_area cũng chiếm phần còn lại — nút luôn nằm góc phải cell item_code.
            $targetCell.css("display", "flex").css("align-items", "center").css("gap", "4px");
            $targetCell.find(".static-area, .field-area").css("flex", "1 1 0").css("min-width", "0");
            $targetCell.append($actions);
        }

        // Double-click để mở dialog
        $row.off("dblclick.alumglass").on("dblclick.alumglass", function () {
            const rowDoc = _get_row_doc(frm, $row);
            if (rowDoc) new alumglass.quotation.ItemParamDialog(frm, rowDoc).show();
        });
    });
}

// ── Lấy doc của row từ grid row element ────────────────────────────
function _get_row_doc(frm, $row) {
    const cdn = $row.attr("data-name");
    if (!cdn) return null;
    const rows = frm.doc?.items || [];
    return rows.find(r => r.name === cdn) || null;
}

// ── Thu thập giá trị form từ grid form con ──────────────────────────
function _collect_form_vars(frm, cdn) {
    const row = frappe.get_doc("Quotation Item", cdn);
    if (!row) return {};
    // Merge với al_bom_vars hiện có
    let vars = {};
    try { vars = JSON.parse(row.al_bom_vars || "{}"); } catch (e) {}
    // Giữ nguyên vars, chỉ đảm bảo BOM version đúng
    if (row.al_bom && !vars._bom) vars._bom = row.al_bom;
    return vars;
}
