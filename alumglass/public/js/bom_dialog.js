// AlumGlass BOM Dialog - Client-side BOM calculation UI
// Hiển thị động toàn bộ cost_template keys từ response
// v28.9 (C3/C4): async BOM (> ASYNC_BOM_THRESHOLD) qua frappe.enqueue +
//   realtime "alumglass_bom_calc_done". Đóng/mở lại đọc al_calc_status +
//   al_bom_result sẵn có — không gọi lại API nếu đang tính trong nền / đã xong.
frappe.provide("alumglass");

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

// NOTE: "Calculate BOM" button on Quotation/Quotation Item is now handled
// by doctype/overrides/quotation.js (toolbar + form buttons + row actions).
// BOMDialog is also launched from ItemParamDialog's Preview button.
// This file only defines the alumglass.BOMDialog class.
