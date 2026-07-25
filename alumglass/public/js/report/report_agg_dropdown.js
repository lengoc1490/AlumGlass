/**
 * report_agg_dropdown.js
 *
 * UI Dialog — Double-click vào ô trên dòng Total để chọn hàm aggregation.
 * Giống Excel: click AutoSum ở footer.
 *
 * Hỗ trợ: sum, average, max, min, count, countA, sumif, countif, averageif
 */

// ============================================================
// 1. SHOW DIALOG — từ dòng Total
// ============================================================
frappe.EUP_REPORT_AGG.showAggDialog = function(column, datatable, reportName) {
	if (!column) return;

	var rawConfig = column.aggregate_function || frappe.EUP_REPORT_AGG.defaultFn;
	var aggConfig = _eup_parse_agg_config(rawConfig);
	var currentFn = aggConfig.fn;
	var columnLabel = column.label || column.name || column.fieldname || '';
	var report = reportName || '';

	if (!report && datatable && datatable._eup_report_instance)
		report = datatable._eup_report_instance.report_name;

	// Lấy danh sách columns để chọn condition_col cho hàm IF
	var allColumns = [];
	try { if (frappe.query_report && frappe.query_report.columns) allColumns = frappe.query_report.columns; } catch(e) {}
	var condColOptions = [{ label: __('(Chọn cột điều kiện)'), value: '' }];
	for (var i=0; i<allColumns.length; i++) {
		if (allColumns[i].fieldname) {
			var label = allColumns[i].label || allColumns[i].fieldname;
			if (allColumns[i].fieldname === column.fieldname) label += ' (chính cột này)';
			condColOptions.push({ label: label, value: allColumns[i].fieldname });
		}
	}

	var fields = [
		{
			label: __('Hàm tính toán cho dòng Total'),
			fieldname: 'fn',
			fieldtype: 'Select',
			options: [
				{ label: __('← Mặc định (theo report)'), value: '__default__' },
				{ label: __('∑ Sum'),                   value: 'sum' },
				{ label: __('x̄ Average'),               value: 'average' },
				{ label: __('↑ Max'),                    value: 'max' },
				{ label: __('↓ Min'),                    value: 'min' },
				{ label: __('# Count (Số)'),            value: 'count' },
				{ label: __('# CountA (Text+Số)'),      value: 'countA' },
				{ label: __('∑ SUMIF'),                 value: 'sumif' },
				{ label: __('# COUNTIF'),                value: 'countif' },
				{ label: __('x̄ AVERAGEIF'),             value: 'averageif' },
				{ label: __('— None (Tắt)'),            value: 'none' }
			],
			default: currentFn
		},
		{
			label: __('Cột điều kiện'),
			fieldname: 'condition_col',
			fieldtype: 'Select',
			options: condColOptions,
			default: aggConfig.condition_col || '',
			depends_on: "eval:doc.fn=='sumif'||doc.fn=='countif'||doc.fn=='averageif'"
		},
		{
			label: __('Giá trị điều kiện'),
			fieldname: 'condition',
			fieldtype: 'Data',
			default: aggConfig.condition || '',
			depends_on: "eval:doc.fn=='sumif'||doc.fn=='countif'||doc.fn=='averageif'",
			description: __('Ho tro: *, ?, >100, <50, !=value')
		}
	];

	var dialog = new frappe.ui.Dialog({
		title: __('Aggregation: {0}', [__(columnLabel)]),
		fields: fields,
		primary_action_label: __('Áp dụng'),
		primary_action: function(data) {
			var config;
			// Reset 1 cot ve mac dinh
			if (data.fn === '__default__') {
				frappe.EUP_REPORT_AGG.saveColumnSetting(report, column.fieldname, null);
				delete column.aggregate_function;
				delete column.disable_total;
				dialog.hide();
				if (datatable) frappe.EUP_REPORT_AGG.refreshTotalRow(datatable);
				frappe.show_alert({ message: __('Đã reset cột {0} về mặc định', [__(columnLabel)]), indicator: 'blue' }, 3);
				return;
			}
			if (data.fn === 'sumif' || data.fn === 'countif' || data.fn === 'averageif') {
				config = { fn: data.fn, condition_col: data.condition_col || null, condition: data.condition || null };
				if (!config.condition_col || !config.condition) {
					frappe.show_alert({ message: __('Cần chọn cột và giá trị điều kiện cho hàm IF'), indicator: 'orange' }, 4);
					return;
				}
			} else {
				config = data.fn;
			}

			column.aggregate_function = config;
			column.disable_total = (data.fn === 'none');

			frappe.EUP_REPORT_AGG.saveColumnSetting(report, column.fieldname, config);
			dialog.hide();

			if (datatable) frappe.EUP_REPORT_AGG.refreshTotalRow(datatable);

			var label = frappe.EUP_REPORT_AGG.getLabel(data.fn);
			frappe.show_alert({ message: __('{0} = {1}', [__(columnLabel), label]), indicator: 'green' }, 3);
		}
	});

	// Danh dau dialog dang mo de tranh mo nhieu
	frappe.EUP_REPORT_AGG._dialogOpen = true;
	dialog.onshow = function() { frappe.EUP_REPORT_AGG._dialogOpen = true; };
	dialog.onhide = function() { frappe.EUP_REPORT_AGG._dialogOpen = false; };
	// Nut "Reset tat ca" dang to, mau xanh dam, de nhin thay
	dialog.set_secondary_action(function() {
	});
	// Custom style cho nut secondary (to + mau xanh)
	var resetBtn = dialog.get_secondary_btn();
	resetBtn.css({
		'background': '#2490ef',
		'color': '#fff',
		'font-weight': '600',
		'padding': '8px 16px',
		'border-radius': '6px',
		'border': 'none',
		'font-size': '13px',
		'line-height': '1.5'
	});
	resetBtn.text(__('Reset tất cả về mặc định'));
	resetBtn.off('click').on('click', function() {
		var settings = frappe.EUP_REPORT_AGG.loadSettings(report);
		Object.keys(settings).forEach(function(k) {
			delete settings[k];
		});
		frappe.EUP_REPORT_AGG.saveSettings(report, settings);
		if (datatable && frappe.query_report && frappe.query_report.columns) {
			frappe.query_report.columns.forEach(function(col) {
				delete col.aggregate_function;
				delete col.disable_total;
			});
		}
		dialog.hide();
		if (datatable) frappe.EUP_REPORT_AGG.refreshTotalRow(datatable);
		frappe.show_alert({ message: __('Đã reset tất cả cột về mặc định của report'), indicator: 'blue' }, 4);
	});
	dialog.show();
};

// ============================================================
// 2. CONTEXT MENU — click chuột phải trên dòng Total
// ============================================================
frappe.EUP_REPORT_AGG._bindTotalRowContextMenu = function(datatable) {
	if (!datatable || datatable._eup_ctxmenu_bound) return;
	datatable._eup_ctxmenu_bound = true;

	var wrapper = datatable.wrapper;
	if (!wrapper) return;

	wrapper.addEventListener('contextmenu', function(e) {
		var target = e.target;
		var cellEl = target.closest ? target.closest('.dt-cell') : null;
		if (!cellEl) return;

		var footer = cellEl.closest ? cellEl.closest('.dt-footer') : null;
		if (!footer) return;

		e.preventDefault();
		e.stopPropagation();

		var reportName = '';
		if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
		else if (frappe.query_report) reportName = frappe.query_report.report_name;
		if (!reportName) return;

		var currentPos = frappe.EUP_REPORT_AGG._totalRowPosition[reportName] || 'bottom';
		var newPos = (currentPos === 'top') ? 'bottom' : 'top';

		frappe.EUP_REPORT_AGG._totalRowPosition[reportName] = newPos;
		frappe.EUP_REPORT_AGG._savePositionSettings(reportName, newPos);
		frappe.EUP_REPORT_AGG.applyTotalRowPosition(datatable);

		frappe.show_alert({
			message: (newPos === 'top')
				? __('Đã chuyển dòng Total lên trên')
				: __('Đã chuyển dòng Total xuống dưới'),
			indicator: 'green'
		}, 3);
	});
};


// ============================================================
// 3. HEADER COLOR SETTINGS — mau nen & mau chu cho header
// ============================================================
// Su dung context menu: click phai tren header cell de mo setting

frappe.EUP_REPORT_AGG._bindHeaderColorContextMenu = function(datatable) {
    if (!datatable || datatable._eup_hdr_color_bound) return;
    datatable._eup_hdr_color_bound = true;

    var wrapper = datatable.wrapper;
    if (!wrapper) return;

    wrapper.addEventListener('contextmenu', function(e) {
        var target = e.target;
        var cellEl = target.closest ? target.closest('.dt-cell--header, .eup-header-group-cell, .dt-cell') : null;
        if (!cellEl) return;

        // Kiem tra co nam trong header khong
        var header = cellEl.closest ? cellEl.closest('.dt-header') : null;
        if (!header) return;

        e.preventDefault();
        e.stopPropagation();

        var reportName = '';
        if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
        else if (frappe.query_report) reportName = frappe.query_report.report_name;
        if (!reportName) return;

        // Lay column info
        var colIdx = parseInt(cellEl.getAttribute('data-col-index'));
        var fieldname = '';
        if (!isNaN(colIdx) && colIdx >= 0) {
            var cols = datatable.datamanager ? datatable.datamanager.getColumns() : null;
            if (cols && cols[colIdx] && cols[colIdx].id) fieldname = cols[colIdx].id;
        }

        // Kiem tra xem co phai header group cell khong (merge cell)
        var isGroupCell = cellEl.classList.contains('eup-header-group-cell');

        frappe.EUP_REPORT_AGG._showHeaderColorDialog(datatable, reportName, fieldname, isGroupCell);
    });
};

// Hien thi dialog setting mau cho header
frappe.EUP_REPORT_AGG._showHeaderColorDialog = function(datatable, reportName, fieldname, isGroupCell) {
    if (frappe.EUP_REPORT_AGG._colorDialogOpen) return;
    frappe.EUP_REPORT_AGG._colorDialogOpen = true;

    var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
    if (!repConf) {
        // Neu khong co config, tao tam
        frappe.EUP_REPORT_AGG._colorDialogOpen = false;
        frappe.show_alert({ message: __('Không tìm thấy config cho report: ' + reportName), indicator: 'red' }, 3);
        return;
    }

    var currentGlobalStyle = repConf.header_style || {};
    var currentStyles = repConf.header_styles || [];

    var currentFieldStyle = {};
    (function resolveCurrentFieldStyle() {
        var headerGroups = repConf.header_groups || [];
        var targetFrom = fieldname, targetTo = fieldname;
        var allFieldnames = (frappe.query_report && frappe.query_report.columns)
            ? frappe.query_report.columns.map(function(c) { return c.fieldname; }) : [];
        for (var gi = 0; gi < headerGroups.length; gi++) {
            var hg = headerGroups[gi];
            if (!hg || !hg.from || !hg.to) continue;
            var fromIdx = allFieldnames.indexOf(hg.from);
            var toIdx = allFieldnames.indexOf(hg.to);
            var fIdx = allFieldnames.indexOf(fieldname);
            if (fromIdx >= 0 && toIdx >= 0 && fIdx >= fromIdx && fIdx <= toIdx) {
                targetFrom = hg.from; targetTo = hg.to;
                break;
            }
        }
        for (var i = 0; i < currentStyles.length; i++) {
            if (currentStyles[i].from === targetFrom &&
                (!currentStyles[i].to || currentStyles[i].to === targetTo)) {
                currentFieldStyle = currentStyles[i];
                break;
            }
        }
    })();

    var fields = [];

    // --- Global header settings ---
    fields.push({
        label: __('--- Thiết lập toàn bộ HEADER ---'),
        fieldname: 'section_global',
        fieldtype: 'Section Break',
        collapsible: 1
    });
    fields.push({
        label: __('Màu nền (toàn bộ header)'),
        fieldname: 'global_bg',
        fieldtype: 'Color',
        default: currentGlobalStyle.bgColor || '',
        description: __('Để trống để sử dụng màu mặc định')
    });
    fields.push({
        label: __('Màu chữ (toàn bộ header)'),
        fieldname: 'global_fg',
        fieldtype: 'Color',
        default: currentGlobalStyle.textColor || '',
        description: __('Để trống để sử dụng màu mặc định')
    });

    // --- Per-field header settings ---
    fields.push({
        label: __('--- Thiết lập riêng cho field: ' + (fieldname || '(tất cả)') + ' ---'),
        fieldname: 'section_field',
        fieldtype: 'Section Break',
        collapsible: 1
    });
    fields.push({
        label: __('Field name'),
        fieldname: 'fieldname',
        fieldtype: 'Data',
        default: fieldname || '',
        read_only: 1,
        hidden: 1
    });
    fields.push({
        label: __('Màu nền (riêng)'),
        fieldname: 'field_bg',
        fieldtype: 'Color',
        default: currentFieldStyle.bgColor || '',
        description: __('Chỉ áp dụng cho field này (nếu có header_groups, map với group tương ứng)')
    });
    fields.push({
        label: __('Màu chữ (riêng)'),
        fieldname: 'field_fg',
        fieldtype: 'Color',
        default: currentFieldStyle.textColor || '',
        description: __('Chỉ áp dụng cho field này')
    });

    var dialog = new frappe.ui.Dialog({
        title: __('Header Color Settings: ' + reportName),
        fields: fields,
        primary_action_label: __('Lưu'),
        primary_action: function(data) {
            var changed = false;

            var newGlobalBg = data.global_bg || '';
            var newGlobalFg = data.global_fg || '';
            if (newGlobalBg || newGlobalFg) {
                if (!repConf.header_style) repConf.header_style = {};
                if (newGlobalBg) repConf.header_style.bgColor = newGlobalBg;
                else delete repConf.header_style.bgColor;
                if (newGlobalFg) repConf.header_style.textColor = newGlobalFg;
                else delete repConf.header_style.textColor;
                // Clean up empty object
                if (!repConf.header_style.bgColor && !repConf.header_style.textColor) {
                    delete repConf.header_style;
                }
                changed = true;
            } else if (repConf.header_style) {
                delete repConf.header_style;
                changed = true;
            }

            // Per-field settings
            var fname = data.fieldname || fieldname;
            var newFieldBg = data.field_bg || '';
            var newFieldFg = data.field_fg || '';

            if (fname && (newFieldBg || newFieldFg)) {
                var styleFrom = fname;
                var styleTo = fname;
                var headerGroups = repConf.header_groups || [];
                for (var gi = 0; gi < headerGroups.length; gi++) {
                    var hg = headerGroups[gi];
                    if (hg && hg.from && hg.to) {
                        var allFieldnames = [];
                        if (frappe.query_report && frappe.query_report.columns) {
                            allFieldnames = frappe.query_report.columns.map(function(c) { return c.fieldname; });
                        } else {
                            try {
                                if (datatable && datatable.datamanager) {
                                    var cols = datatable.datamanager.getColumns();
                                    allFieldnames = cols.map(function(c) { return c && c.id; }).filter(Boolean);
                                }
                            } catch(e) {}
                        }
                        var fromIdx = allFieldnames.indexOf(hg.from);
                        var toIdx = allFieldnames.indexOf(hg.to);
                        var fIdx = allFieldnames.indexOf(fname);
                        if (fromIdx >= 0 && toIdx >= 0 && fIdx >= 0 && fIdx >= fromIdx && fIdx <= toIdx) {
                            styleFrom = hg.from;
                            styleTo = hg.to;
                            break;
                        }
                    }
                }

                if (!repConf.header_styles) repConf.header_styles = [];
                var found = false;
                for (var si = 0; si < repConf.header_styles.length; si++) {
                    if (repConf.header_styles[si].from === styleFrom &&
                        (!repConf.header_styles[si].to || repConf.header_styles[si].to === styleTo)) {
                        found = true;
                        if (newFieldBg) repConf.header_styles[si].bgColor = newFieldBg;
                        else delete repConf.header_styles[si].bgColor;
                        if (newFieldFg) repConf.header_styles[si].textColor = newFieldFg;
                        else delete repConf.header_styles[si].textColor;
                        // Clean up empty entry
                        if (!repConf.header_styles[si].bgColor && !repConf.header_styles[si].textColor && !repConf.header_styles[si].title) {
                            repConf.header_styles.splice(si, 1);
                        }
                        break;
                    }
                }
                if (!found) {
                    repConf.header_styles.push({
                        from: styleFrom,
                        to: styleTo,
                        bgColor: newFieldBg || undefined,
                        textColor: newFieldFg || undefined
                    });
                }
                changed = true;
            }

            if (changed) {
                // Refresh header groups de ap dung mau moi
                frappe.EUP_REPORT_AGG._headerGroups[reportName] = repConf.header_groups;
                if (repConf.header_styles) {
                    frappe.EUP_REPORT_AGG._headerStyles[reportName] = repConf.header_styles;
                }
                if (repConf.header_style) {
                    frappe.EUP_REPORT_AGG._headerStyles[reportName] = repConf.header_style;
                }

                // Re-apply header groups de CSS duoc inject lai
                frappe.EUP_REPORT_AGG.applyHeaderGroups(datatable);

                frappe.show_alert({
                    message: __('Đã cập nhật màu sắc cho header'),
                    indicator: 'green'
                }, 3);
            }

            dialog.hide();
            frappe.EUP_REPORT_AGG._colorDialogOpen = false;
        }
    });

    dialog.onshow = function() { frappe.EUP_REPORT_AGG._colorDialogOpen = true; };
    dialog.onhide = function() { frappe.EUP_REPORT_AGG._colorDialogOpen = false; };
    dialog.show();
};

frappe.EUP_REPORT_AGG._patchColorContext = function() {
    if (frappe.EUP_REPORT_AGG._colorCtxPatched) return true;
    if (!frappe.views || !frappe.views.QueryReport) return false;

    // Pat vao render_datatable de bind context menu cho header colors
    var _orig_render_hdr = frappe.views.QueryReport.prototype.render_datatable;
    if (_orig_render_hdr) {
        var _eup_orig_render2 = _orig_render_hdr;
        frappe.views.QueryReport.prototype.render_datatable = function() {
            var result = _eup_orig_render2.apply(this, arguments);
            if (this.datatable) {
                setTimeout(function(dt) {
                    frappe.EUP_REPORT_AGG._bindHeaderColorContextMenu(dt);
                }, 200, this.datatable);
            }
            return result;
        };
    }

    var _orig_rv_setup_hdr = frappe.views.ReportView.prototype.setup_datatable;
    if (_orig_rv_setup_hdr) {
        var _eup_orig_rv2 = _orig_rv_setup_hdr;
        frappe.views.ReportView.prototype.setup_datatable = function(values) {
            var result = _eup_orig_rv2.apply(this, arguments);
            if (this.datatable) {
                setTimeout(function(dt) {
                    frappe.EUP_REPORT_AGG._bindHeaderColorContextMenu(dt);
                }, 200, this.datatable);
            }
            return result;
        };
    }

    frappe.EUP_REPORT_AGG._colorCtxPatched = true;
    return true;
};

// Retry cho den khi QueryReport san sang
if (!frappe.EUP_REPORT_AGG._patchColorContext()) {
    frappe.EUP_REPORT_AGG._colorInterval = setInterval(function() {
        if (frappe.EUP_REPORT_AGG._patchColorContext()) {
            clearInterval(frappe.EUP_REPORT_AGG._colorInterval);
        }
    }, 10);
}
$(document).on('frappe:init', function() {
    if (!frappe.EUP_REPORT_AGG._colorCtxPatched) {
        frappe.EUP_REPORT_AGG._patchColorContext();
    }
});