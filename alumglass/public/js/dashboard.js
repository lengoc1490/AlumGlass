// AlumGlass ERP v17.0 — Dashboard Widgets
// Renders dashboard widgets based on AL Dashboard Config per role.

frappe.provide('alumglass.dashboard');

alumglass.dashboard = {
    /**
     * Initialize dashboard for the current user's role.
     * Called from dashboard page or desk.
     */
    init(container) {
        const me = this;
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'AL Dashboard Config',
                fields: ['role', 'widgets', 'default_date_range', 'refresh_interval_sec'],
                filters: { role: frappe.user_roles },
                limit: 1,
            },
            callback(r) {
                if (r.message && r.message.length > 0) {
                    me.render(container, r.message[0]);
                } else {
                    me.render_default(container);
                }
            },
        });
    },

    /**
     * Render dashboard widgets from config.
     */
    render(container, config) {
        const widgets = JSON.parse(config.widgets || '[]');
        const date_range = config.default_date_range || 'THIS_MONTH';

        let html = '<div class="alumglass-dashboard">';
        html += `<h3>AlumGlass Dashboard</h3>`;

        // Date range selector
        html += `<div class="dashboard-filters" style="margin-bottom:15px;">
            <select class="form-control date-range-select" style="width:200px;display:inline;">
                <option value="THIS_MONTH" ${date_range === 'THIS_MONTH' ? 'selected' : ''}>This Month</option>
                <option value="THIS_QUARTER" ${date_range === 'THIS_QUARTER' ? 'selected' : ''}>This Quarter</option>
                <option value="THIS_YEAR" ${date_range === 'THIS_YEAR' ? 'selected' : ''}>This Year</option>
            </select>
        </div>`;

        // Widget grid
        html += '<div class="row">';
        widgets.forEach((w, i) => {
            html += `<div class="col-md-${w.width || 6}">
                <div class="dashboard-widget" id="widget-${i}" style="border:1px solid #d1d8dd;border-radius:4px;padding:15px;margin-bottom:15px;background:#fff;">
                    <h4>${w.title || 'Widget'}</h4>
                    <div class="widget-content" id="widget-content-${i}">
                        <div class="text-center text-muted">Loading...</div>
                    </div>
                </div>
            </div>`;
        });
        html += '</div></div>';

        container.innerHTML = html;

        // Load each widget
        widgets.forEach((w, i) => {
            this.load_widget(w, i);
        });

        // Auto-refresh
        if (config.refresh_interval_sec > 0) {
            setInterval(() => {
                widgets.forEach((w, i) => this.load_widget(w, i));
            }, config.refresh_interval_sec * 1000);
        }
    },

    /**
     * Load a single widget's data.
     */
    load_widget(widget, index) {
        const me = this;
        const content_el = document.getElementById(`widget-content-${index}`);

        // KPI widget
        if (widget.type === 'kpi') {
            this._render_kpi_widget(content_el, widget);
        }
        // Chart widget
        else if (widget.type === 'chart') {
            this._render_chart_widget(content_el, widget);
        }
        // Report widget
        else if (widget.type === 'report') {
            this._render_report_widget(content_el, widget);
        }
        // Summary widget
        else if (widget.type === 'summary') {
            this._render_summary_widget(content_el, widget);
        }
        // Alert widget
        else if (widget.type === 'alerts') {
            this._render_alerts_widget(content_el, widget);
        }
    },

    _render_kpi_widget(el, widget) {
        frappe.call({
            method: 'alumglass.api.get_sales_kpi_dashboard',
            args: { kpi_period: widget.kpi_period || 'MONTHLY' },
            callback(r) {
                if (!r.message) return;
                const data = r.message;
                let html = '';
                data.kpis.forEach(kpi => {
                    const achieved = kpi.target_amount > 0
                        ? ((kpi.actual_amount / kpi.target_amount) * 100).toFixed(0)
                        : 0;
                    html += `<div style="margin-bottom:10px;">
                        <strong>${kpi.sales_user}</strong><br>
                        Sales: ${frappe.format(kpi.actual_amount, {fieldtype:'Currency'})}
                        / ${frappe.format(kpi.target_amount, {fieldtype:'Currency'})}
                        <div class="progress" style="height:8px;margin-top:4px;">
                            <div class="progress-bar" style="width:${Math.min(achieved, 100)}%"></div>
                        </div>
                        <small>${achieved}% of target</small>
                    </div>`;
                });
                el.innerHTML = html || '<div class="text-muted">No KPI data for this period</div>';
            },
        });
    },

    _render_chart_widget(el, widget) {
        try {
            new frappe.Chart(el, {
                title: widget.title,
                data: widget.data || {},
                type: widget.chart_type || 'bar',
                height: 250,
                colors: ['#7cd6fd', '#5e64ff', '#743ee2', '#ff5858'],
            });
        } catch (e) {
            el.innerHTML = '<div class="text-muted">Chart data not available</div>';
        }
    },

    _render_report_widget(el, widget) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: widget.report_doctype || 'Quotation',
                fields: widget.fields || ['name'],
                filters: widget.filters || {},
                order_by: 'creation desc',
                limit_page_length: widget.limit || 5,
            },
            callback(r) {
                if (!r.message || r.message.length === 0) {
                    el.innerHTML = '<div class="text-muted">No data</div>';
                    return;
                }
                let html = '<table class="table table-condensed" style="margin:0;">';
                r.message.forEach(row => {
                    html += '<tr>';
                    widget.fields.forEach(f => {
                        html += `<td>${row[f] || ''}</td>`;
                    });
                    html += '</tr>';
                });
                html += '</table>';
                el.innerHTML = html;
            },
        });
    },

    _render_summary_widget(el, widget) {
        // Render summary from AL Sales Pipeline data
        frappe.call({
            method: 'frappe.call',
            args: {
                module: 'alumglass.alumglass.reports.al_sales_pipeline.al_sales_pipeline',
                method: 'execute',
                args: { filters: {} },
            },
            callback(r) {
                if (!r.message) return;
                const [columns, data, chart, report_summary] = r.message;
                const s = report_summary || {};
                el.innerHTML = `
                    <div style="display:flex;justify-content:space-around;text-align:center;">
                        <div><h2>${s.total_quotations || 0}</h2><small>Quotations</small></div>
                        <div><h2>${s.conversion_rate_pct || 0}%</h2><small>Conversion</small></div>
                        <div><h2>${frappe.format(s.total_value || 0, {fieldtype:'Currency'})}</h2><small>Value</small></div>
                        <div><h2>${frappe.format(s.total_margin || 0, {fieldtype:'Currency'})}</h2><small>Margin</small></div>
                    </div>
                `;
            },
        });
    },

    _render_alerts_widget(el, widget) {
        frappe.call({
            method: 'alumglass.api.check_alerts_for_quotation',
            args: { quotation_name: '' },
            callback(r) {
                if (!r.message) {
                    el.innerHTML = '<div class="text-success">No active alerts</div>';
                    return;
                }
                let html = '<ul style="padding-left:20px;">';
                r.message.forEach(alert => {
                    html += `<li style="color:${alert.severity === 'high' ? 'red' : 'orange'}">
                        ${alert.message}
                    </li>`;
                });
                html += '</ul>';
                el.innerHTML = html;
            },
        });
    },

    /**
     * Render default dashboard when no config is found.
     */
    render_default(container) {
        container.innerHTML = `
            <div class="alumglass-dashboard">
                <h3>AlumGlass Dashboard</h3>
                <div class="row">
                    <div class="col-md-6">
                        <div class="alert alert-info">
                            <strong>Welcome to AlumGlass ERP v17!</strong><br>
                            Configure your dashboard in <b>AL Dashboard Config</b>.
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="alert alert-warning">
                            <strong>Quick Links:</strong><br>
                            <a href="/app/al-bom">AL BOM</a> |
                            <a href="/app/quotation">Quotations</a> |
                            <a href="/app/al-sales-kpi">Sales KPI</a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },
};
