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
	var condColOptions = [{ label: __('(chon cot dieu kien)'), value: '' }];
	for (var i=0; i<allColumns.length; i++) {
		if (allColumns[i].fieldname) {
			var label = allColumns[i].label || allColumns[i].fieldname;
			if (allColumns[i].fieldname === column.fieldname) label += ' (chinh cot nay)';
			condColOptions.push({ label: label, value: allColumns[i].fieldname });
		}
	}

	var fields = [
		{
			label: __('Ham tinh cho dong Total'),
			fieldname: 'fn',
			fieldtype: 'Select',
			options: [
				{ label: __('∑ Sum (mac dinh)'),     value: 'sum' },
				{ label: __('x̄ Average'),             value: 'average' },
				{ label: __('↑ Max'),                  value: 'max' },
				{ label: __('↓ Min'),                  value: 'min' },
				{ label: __('# Count (chi so)'),       value: 'count' },
				{ label: __('# CountA (ca text+so)'), value: 'countA' },
				{ label: __('∑ SUMIF'),               value: 'sumif' },
				{ label: __('# COUNTIF'),              value: 'countif' },
				{ label: __('x̄ AVERAGEIF'),           value: 'averageif' },
				{ label: __('— None (tat)'),          value: 'none' }
			],
			default: currentFn
		},
		{
			label: __('Cot dieu kien'),
			fieldname: 'condition_col',
			fieldtype: 'Select',
			options: condColOptions,
			default: aggConfig.condition_col || '',
			depends_on: "eval:doc.fn=='sumif'||doc.fn=='countif'||doc.fn=='averageif'"
		},
		{
			label: __('Gia tri dieu kien'),
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
		primary_action_label: __('Ap dung'),
		primary_action: function(data) {
			var config;
			if (data.fn === 'sumif' || data.fn === 'countif' || data.fn === 'averageif') {
				config = { fn: data.fn, condition_col: data.condition_col || null, condition: data.condition || null };
				if (!config.condition_col || !config.condition) {
					frappe.show_alert({ message: __('Can chon cot va gia tri dieu kien cho ham IF'), indicator: 'orange' }, 4);
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
	dialog.show();
};


$(document).on('frappe:init', function() {
	console.log('[Report Agg] Double-click Total cell to configure aggregation like Excel.');
});
