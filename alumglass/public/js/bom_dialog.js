// AlumGlass BOM Dialog - Client-side BOM calculation UI
// Hiển thị động toàn bộ cost_template keys từ response
frappe.provide("alumglass");

alumglass.BOMDialog = class BOMDialog {
    constructor(quotation_item_name) {
        this.quotation_item_name = quotation_item_name;
        this.dialog = null;
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

        this.calculate();
    }

    calculate() {
        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: {
                quotation_item_name: this.quotation_item_name,
            },
            callback: (r) => {
                if (r.message) {
                    this.render_results(r.message);
                }
            },
        });
    }

    render_results(data) {
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

            // Sort keys: subtotals/GIA_* cuối cùng
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
        this.dialog.set_value("result_html", html);
        this.dialog.show();
    }
};

// Add "Calculate BOM" button to Quotation Item form
frappe.ui.form.on("Quotation Item", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Calculate BOM"), function () {
                new alumglass.BOMDialog(frm.doc.name).show();
            }, __("AlumGlass"));
        }
    },
});
