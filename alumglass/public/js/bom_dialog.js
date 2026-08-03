// AlumGlass BOM Dialog - Client-side BOM calculation UI
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

        // Summary
        html += `<table class="table table-bordered">
            <tr><th>${__("GIA_VAT")}</th><td class="text-right"><strong>${format_currency(data.gia_vat)}</strong></td></tr>
            <tr><th>${__("GIA_BAN")}</th><td class="text-right">${format_currency(data.gia_ban)}</td></tr>
            <tr><th>${__("TONG_VL")}</th><td class="text-right">${format_currency(data.tong_vl)}</td></tr>
            <tr><th>${__("TONG_NC")}</th><td class="text-right">${format_currency(data.tong_nc)}</td></tr>
        </table>`;

        // Detail lines
        if (data.lines && data.lines.length) {
            html += `<h4>${__("Detail Lines")}</h4>`;
            html += `<table class="table table-striped table-bordered">
                <thead>
                    <tr>
                        <th>${__("Slug")}</th>
                        <th>${__("Item")}</th>
                        <th>${__("Width")}</th>
                        <th>${__("Height")}</th>
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
