/**
 * report_aggregation_core.js
 *
 * Mở rộng Frappe Report Total Row — giống Excel:
 * - Click vào ô trên dòng Total để chọn hàm aggregation
 * - Hàm đơn: sum, average, max, min, count, countA
 * - Hàm có điều kiện: sumif, countif, averageif
 * - Đếm cả text (countA) chứ không chỉ số như count cũ
 *
 * Áp dụng CHO TOÀN BỘ HỆ THỐNG (Query Reports + Report Builder).
 *
 * Cấu hình trong aggregate_fields của mỗi report:
 *   "fieldname": "sum"                      // hàm đơn
 *   "fieldname": { fn: "sumif", condition_col: "status", condition: "Done" }  // hàm IF
 *   "fieldname": "countA"                   // đếm text
 *
 * Bổ sung: header_groups, total_row_position, bold_header (config trong query_reports)
 */

// ============================================================
// UTILITY: Chuyển giá trị về số an toàn
// ============================================================
function _eup_to_num(v) {
	if (v === null || v === undefined || v === '' || v === true || v === false) return NaN;
	if (typeof v === 'number') return v;
	var s = String(v).replace(/[^0-9.\-]/g, '');
	return s ? parseFloat(s) : NaN;
}
function _eup_to_str(v) {
	if (v === null || v === undefined) return '';
	return String(v);
}

// ============================================================
// UTILITY: Lấy data gốc từ report instance
// ============================================================
function _eup_get_raw_data() {
	try { if (frappe.query_report && frappe.query_report.data) return frappe.query_report.data; } catch(e) {}
	return null;
}

// ============================================================
// UTILITY: Kiểm tra điều kiện giống Excel
// ============================================================
function _eup_match_condition(cellValue, condition) {
	if (condition === undefined || condition === null) return true;
	var s = _eup_to_str(cellValue);
	var c = _eup_to_str(condition);
	if (c.indexOf('*') >= 0 || c.indexOf('?') >= 0) {
		var reStr = c.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
		return new RegExp('^' + reStr + '$', 'i').test(s);
	}
	if (c.length > 1 && (c[0] === '>' || c[0] === '<')) {
		var num = _eup_to_num(cellValue);
		var cmp = _eup_to_num(c.substring(c[1] === '=' ? 2 : 1));
		if (!isNaN(num) && !isNaN(cmp)) {
			if (c[0] === '>') return c[1] === '=' ? num >= cmp : num > cmp;
			if (c[0] === '<') return c[1] === '=' ? num <= cmp : num < cmp;
		}
		return false;
	}
	if (c.indexOf('!=') === 0) return s !== c.substring(2);
	if (c.indexOf('=') === 0) return s === c.substring(1);
	return s.toLowerCase() === c.toLowerCase();
}

// ============================================================
// UTILITY: Lọc rows theo condition
// ============================================================
function _eup_filter_rows(rawData, colFieldname, conditionCol, conditionVal) {
	if (!rawData || !rawData.length) return [];
	// Khong co dieu kien -> lay tat ca gia tri cua colFieldname
	if (!conditionCol || conditionVal === undefined || conditionVal === null) {
		return rawData.map(function(r) { return r[colFieldname]; });
	}
	// Kiem tra colFieldname co ton tai trong raw row khong
	// (co the la fieldname ao chi co trong column definition)
	var hasTargetField = rawData[0] && (colFieldname in rawData[0]);
	return rawData
		.filter(function(r) { return _eup_match_condition(r[conditionCol], conditionVal); })
		.map(function(r) {
			if (hasTargetField) return r[colFieldname];
			// Neu target field khong co trong data -> dung chinh condition_col
			// Vi du: COUNTIF(company, "EuP") => dem tren cot company
			return r[conditionCol];
		});
}

// ============================================================
// UTILITY: Parse config aggregate_fields
// ============================================================
function _eup_parse_agg_config(colConfig) {
	if (typeof colConfig === 'string') return { fn: colConfig, condition_col: null, condition: null };
	if (typeof colConfig === 'object' && colConfig !== null) {
		return {
			fn: colConfig.fn || colConfig.type || 'sum',
			condition_col: colConfig.condition_col || colConfig.conditionCol || null,
			condition: colConfig.condition || colConfig.conditionVal || null
		};
	}
	return { fn: 'sum', condition_col: null, condition: null };
}

// ============================================================
// 1. ĐỊNH NGHĨA CÁC HÀM AGGREGATION
// ============================================================
frappe.EUP_REPORT_AGG = {
	functions: {
		sum: function(values) {
			var nums = [];
			for (var i=0; i<values.length; i++) {
				var n = _eup_to_num(values[i]);
				if (!isNaN(n)) nums.push(n);
			}
			return nums.length ? nums.reduce(function(a,b){return a+b;},0) : null;
		},
		average: function(values) {
			var nums = [];
			for (var i=0; i<values.length; i++) {
				var n = _eup_to_num(values[i]);
				if (!isNaN(n)) nums.push(n);
			}
			return nums.length ? nums.reduce(function(a,b){return a+b;},0)/nums.length : null;
		},
		avg: function(values) { return frappe.EUP_REPORT_AGG.functions.average(values); },
		max: function(values) {
			if (!values || !values.length) return null;
			return Math.max.apply(null, values);
		},
		min: function(values) {
			if (!values || !values.length) return null;
			return Math.min.apply(null, values);
		},
		count: function(values) {
			// COUNT: dem so o CHUA SO — giong Excel COUNT
			// Khong dem text, khong dem boolean, khong dem empty string
			var count = 0;
			for (var i = 0; i < values.length; i++) {
				var v = values[i];
				if (v === null || v === undefined || v === '') continue;
				// Number thuan
				if (typeof v === 'number' && isFinite(v)) { count++; continue; }
				// String co the chuyen thanh so — Excel COUNT van dem
				if (typeof v === 'string') {
					var n = _eup_to_num(v);
					if (!isNaN(n) && isFinite(n)) { count++; continue; }
				}
				// Boolean (true/false): Excel COUNT khong dem
				// Text khong phai so: Excel COUNT khong dem
			}
			return count;
		},

		countA: function(values) {
			// COUNTA: dem tat ca o KHONG TRONG — giong Excel COUNTA
			// Dem so, text, boolean — chi loai null/undefined/empty string
			var count = 0;
			for (var i = 0; i < values.length; i++) {
				var v = values[i];
				if (v === null || v === undefined) continue;
				if (typeof v === 'string' && v.trim() === '') continue;
				count++;
			}
			return count;
		},
		none: function(values) { return null; },
		sumif: function(values, rawData, colFieldname, aggConfig) {
			var filtered = _eup_filter_rows(rawData, colFieldname, aggConfig.condition_col, aggConfig.condition);
			return frappe.EUP_REPORT_AGG.functions.sum(filtered);
		},
		countif: function(values, rawData, colFieldname, aggConfig) {
			if (aggConfig.condition_col && aggConfig.condition !== null) {
				var raw = rawData || _eup_get_raw_data();
				if (raw) {
					var count=0;
					for (var i=0; i<raw.length; i++) {
						if (_eup_match_condition(raw[i][aggConfig.condition_col], aggConfig.condition)) count++;
					}
					return count;
				}
			}
			// Fallback: dem tu values (dang visible rows)
			var count = 0;
			for (var i=0; i<values.length; i++) {
				if (values[i] !== null && values[i] !== undefined && values[i] !== '') count++;
			}
			return count;
		},
		averageif: function(values, rawData, colFieldname, aggConfig) {
			var filtered = _eup_filter_rows(rawData, colFieldname, aggConfig.condition_col, aggConfig.condition);
			return frappe.EUP_REPORT_AGG.functions.average(filtered);
		}
	},
	labels: {
		sum:       { label: '∑ Sum',              icon: '∑' },
		average:   { label: 'x̄ Average',          icon: 'x̄' },
		avg:       { label: 'x̄ Average',          icon: 'x̄' },
		max:       { label: '↑ Max',              icon: '↑' },
		min:       { label: '↓ Min',              icon: '↓' },
		count:     { label: '# Count (số)',       icon: '#' },
		countA:    { label: '# CountA (text+số)', icon: '#' },
		sumif:     { label: '∑ SUMIF',            icon: '∑↓' },
		countif:   { label: '# COUNTIF',          icon: '#↓' },
		averageif: { label: 'x̄ AVERAGEIF',       icon: 'x̄↓' },
		none:      { label: '— None',             icon: '—' }
	},
	defaultFn: 'sum',
	getLabel: function(fnName) {
		fnName = fnName || this.defaultFn;
		var info = this.labels[fnName];
		return info ? info.label : (this.labels[this.defaultFn].label);
	}
};

// Cache aggregate_fields doc lap (tranh bi frappe core ghi de)
frappe.EUP_REPORT_AGG._configs = {};

// Ham capture aggregate_fields — goi sau khi frappe.query_reports[name] duoc set
frappe.EUP_REPORT_AGG._captureAggFields = function(reportName, obj) {
	if (obj && obj.aggregate_fields && reportName) {
		frappe.EUP_REPORT_AGG._configs[reportName] = obj.aggregate_fields;
	}
};

// Pat qua frappe:init de capture aggregate_fields tu frappe.query_reports
$(document).on('frappe:init', function() {
	// Capture tat ca configs hien co
	for (var k in frappe.query_reports) {
		if (frappe.query_reports.hasOwnProperty(k) && frappe.query_reports[k].aggregate_fields) {
			frappe.EUP_REPORT_AGG._configs[k] = frappe.query_reports[k].aggregate_fields;
		}
	}
});

// ============================================================
// 2. LƯU / ĐỌC SETTINGS (localStorage)
// ============================================================
frappe.EUP_REPORT_AGG.STORAGE_PREFIX = 'eup_report_agg';
frappe.EUP_REPORT_AGG.getStorageKey = function(reportName) {
	return this.STORAGE_PREFIX + ':' + (frappe.session.user || 'Guest') + ':' + (reportName || '');
};
frappe.EUP_REPORT_AGG.loadSettings = function(reportName) {
	try {
		var key = this.getStorageKey(reportName);
		var val = localStorage.getItem(key);
		console.log('[Agg] Loaded from localStorage key=' + key + ' found=' + (val ? 'yes' : 'no'));
		return JSON.parse(val) || {};
	} catch(e) { return {}; }
};
frappe.EUP_REPORT_AGG.saveSettings = function(reportName, settings) {
	try {
		var key = this.getStorageKey(reportName);
		localStorage.setItem(key, JSON.stringify(settings));
		console.log('[Agg] Saved to localStorage key=' + key);
	} catch(e) { console.warn('[Agg] Save failed', e); }
};
frappe.EUP_REPORT_AGG.saveColumnSetting = function(reportName, fieldname, config) {
	if (!reportName || !fieldname) return;
	var settings = this.loadSettings(reportName);
	settings[fieldname] = config;
	this.saveSettings(reportName, settings);
	console.log('[Agg] Saved setting', reportName, fieldname, '=', JSON.stringify(config));
};

// ============================================================
// 3. ÁP DỤNG SETTINGS VÀO COLUMNS
// ============================================================
// Luu tru aggregate_fields doc lap, tranh bi frappe core ghi de
frappe.EUP_REPORT_AGG._configs = frappe.EUP_REPORT_AGG._configs || {};

frappe.EUP_REPORT_AGG.applySettingsToColumns = function(columns, reportName, reportSettings) {
	if (!columns || !reportName) return columns;
	var settings = this.loadSettings(reportName);

	// HARD FIX: Lay aggregate_fields truc tiep tu frappe.query_report.report_settings
	// Khong qua cache hay query_reports (de tranh bi core ghi de)
	var aggFields = null;
	if (reportSettings && reportSettings.aggregate_fields) {
		aggFields = reportSettings.aggregate_fields;
	} else if (frappe.query_report && frappe.query_report.report_settings && frappe.query_report.report_settings.aggregate_fields) {
		aggFields = frappe.query_report.report_settings.aggregate_fields;
	} else {
		var reportConfig = frappe.query_reports ? frappe.query_reports[reportName] : null;
		if (reportConfig && reportConfig.aggregate_fields) aggFields = reportConfig.aggregate_fields;
	}
	// Neu co _configs cache thi uu tien hon (setting tu dialog)
	if (this._configs[reportName]) aggFields = this._configs[reportName];
	// Luu lai vao cache
	if (aggFields) this._configs[reportName] = aggFields;
	columns.forEach(function(col) {
		var config = null;
		if (settings[col.fieldname]) config = settings[col.fieldname];
		else if (aggFields && aggFields[col.fieldname] !== undefined) config = aggFields[col.fieldname];
		if (config) {
			col.aggregate_function = config;
			// "none" => disable_total de DataTable khong hien o Total
			var parsed = _eup_parse_agg_config(config);
			if (parsed.fn === 'none') {
				col.disable_total = true;
			}
		}
	});
	return columns;
};

// ============================================================
// 4a. OVERRIDE: columnTotal HOOK — tính giá trị cho dòng Total
// ============================================================
// Ham tinh toan aggregate cho dong Total
// Dinh nghia truoc, gan vao frappe.utils sau (trong frappe:init)
function _eup_column_total(values, cell) {
	if (!cell || !cell.column) return null;

	var column = cell.column;
	var rawConfig = column.aggregate_function;

	// Neu KHONG co aggregate_function (mac dinh) => khong tinh, de DataTube tu xu ly
	if (!rawConfig) return null;

	var aggConfig = _eup_parse_agg_config(rawConfig);
	var aggFn = aggConfig.fn;

	// "none" hoac disable_total => return null
	if (cell.column.disable_total || aggFn === 'none') {
		return null;
	}

	if (!values || values.length === 0) return null;

	var fn = frappe.EUP_REPORT_AGG.functions[aggFn];
	if (!fn) return null;

	if (aggFn === 'sumif' || aggFn === 'countif' || aggFn === 'averageif') {
		var rawData = _eup_get_raw_data();
		if (rawData) return fn(values, rawData, column.fieldname || column.id, aggConfig);
		// Fallback: lay visible rows tu DataTable
		try {
			var qr = frappe.query_report;
			if (qr && qr.datatable) {
				var dt = qr.datatable;
				var cols = dt.datamanager.getColumns();
				var rows = dt.bodyRenderer.visibleRows;
				if (rows && rows.length) {
					var rawConverted = rows.map(function(row) {
						var obj = {};
						for (var c=0; c<cols.length; c++) {
							obj[cols[c].id] = row[c] ? row[c].content : null;
						}
						return obj;
					});
					return fn(values, rawConverted, column.fieldname || column.id, aggConfig);
				}
			}
		} catch(e) {}
		return fn(values);
	}
	return fn(values);
}

// Gan NGAY khi file load (frappe.utils co san tu frappe core JS)
// va cung gan lai trong frappe:init de dam bao
if (typeof frappe !== 'undefined' && frappe.utils) {
	frappe.utils.report_column_total = _eup_column_total;
}
$(document).on('frappe:init', function() {
	frappe.utils.report_column_total = _eup_column_total;
});

// ============================================================
// 5. OVERRIDE: prepare_report_data
// ============================================================
var _orig_prepare = frappe.views.QueryReport.prototype.prepare_report_data;
if (_orig_prepare) {
	frappe.views.QueryReport.prototype.prepare_report_data = function(data) {
		if (data && data.columns) {
			frappe.EUP_REPORT_AGG.applySettingsToColumns(data.columns, this.report_name);
			// Debug log
			var named = {};
			for (var ci=0; ci<data.columns.length; ci++) {
				var c = data.columns[ci];
				if (c.aggregate_function) {
					named[c.fieldname] = c.aggregate_function;
				}
			}
			if (Object.keys(named).length) console.log('[Agg] applied:', JSON.stringify(named));
		}
		return _orig_prepare.apply(this, arguments);
	};
}

// ============================================================
// 6. OVERRIDE: ReportView.get_columns_totals (Report Builder)
// ============================================================
var _orig_get_totals = frappe.views.ReportView.prototype.get_columns_totals;
if (_orig_get_totals) {
	frappe.views.ReportView.prototype.get_columns_totals = function(data) {
		if (!this.add_totals_row) return [];
		var row_totals = {};
		this.columns.forEach(function(col) {
			if (!(col.id in data[0]) || !frappe.model.is_numeric_field(col.docfield)) {
				row_totals[col.id] = 0; return;
			}
			var rc = col.aggregate_function || frappe.EUP_REPORT_AGG.defaultFn;
			var ac = _eup_parse_agg_config(rc);
			var fn = frappe.EUP_REPORT_AGG.functions[ac.fn];
			if (!fn) { row_totals[col.id] = 0; return; }
			if (ac.fn === 'none') { row_totals[col.id] = ''; return; }

			if (ac.fn === 'sumif' || ac.fn === 'countif' || ac.fn === 'averageif') {
				var vals = data.map(function(r) { return r[col.id]; });
				var res = fn(vals, data, col.id, ac);
				row_totals[col.id] = (res !== null && res !== undefined) ? res : '';
			} else {
				var vals = [];
				for (var j=0; j<data.length; j++) vals.push(data[j][col.id]);
				var res = fn(vals);
				row_totals[col.id] = (res !== null && res !== undefined) ? res : '';
			}
		});
		return row_totals;
	};
}

// ============================================================
// 7b. PATCH RENDER DATATABLE — set content = "" cho cot "none"
// ============================================================
// DataTable khong cho phep columnTotal hook tra ve "" de hien thi empty
// (format Int bien "" thanh "0", hoac return null bi fallback SUM)
// Giai phap: pat truc tiep vao datatable.bodyRenderer.getTotalRow
// de set content = "" cho nhung cot disable_total / none
function _eup_patch_body_renderer(datatable) {
	if (!datatable || !datatable.bodyRenderer || datatable._eup_br_patched) return;
	var br = datatable.bodyRenderer;
	var origGetTotalRow = br.getTotalRow;
	if (!origGetTotalRow) return;

	br.getTotalRow = function() {
		var result = origGetTotalRow.apply(this, arguments);
		if (result && result.length) {
			for (var i=0; i<result.length; i++) {
				var cell = result[i];
				if (!cell || !cell.column) continue;
				var col = cell.column;
				// Chi xu ly "none" khi col.aggregate_function duoc set CU THE
				// Neu khong co aggregate_function (undefined), bo qua de DataTable tu xu ly
				if (col.disable_total) {
					cell.content = "";
					cell.format = function() { return ""; };
				} else if (col.aggregate_function) {
					var rawConfig = col.aggregate_function;
					var aggConfig = _eup_parse_agg_config(rawConfig);
					if (aggConfig.fn === 'none') {
						cell.content = "";
						cell.format = function() { return ""; };
					}
				}
			}
		}
		return result;
	};
	datatable._eup_br_patched = true;
	console.log('[Report Agg] BodyRenderer.getTotalRow patched for instance');
}


// ============================================================
// 7b-2. PATCH THU: loc phan tu null/undefined khoi getColumns()
// ============================================================
// Phong ngua crash "Cannot read properties of undefined (reading
// 'minWidth')" trong Style.setupMinWidth cua core (xay ra khi sort lam
// core render lai va gap phan tu "lo hong" trong mang cot). Sau khi da
// sua nguyen nhan chinh (khong con dung class dt-cell/dt-cell--header/
// dt-row trung voi core nua), patch nay la lop bao ve bo sung — neu vi
// ly do nao khac mang cot van co lo hong thi report se tu loc bo thay vi
// crash lam "treo/lag" toan bo giao dien.
function _eup_patch_datamanager_getColumns(datatable) {
	if (!datatable || !datatable.datamanager || datatable._eup_dm_patched) return;
	var dm = datatable.datamanager;
	var orig = dm.getColumns;
	if (typeof orig !== 'function') return;
	dm.getColumns = function() {
		var cols = orig.apply(this, arguments);
		if (Array.isArray(cols)) {
			var hasHole = false;
			for (var k = 0; k < cols.length; k++) {
				if (cols[k] === null || cols[k] === undefined) { hasHole = true; break; }
			}
			if (hasHole) return cols.filter(function(c) { return c !== null && c !== undefined; });
		}
		return cols;
	};
	datatable._eup_dm_patched = true;
}

// ============================================================
// 7c. CLICK VAO DONG TOTAL — MO DIALOG CHON AGG FUNCTION
// ============================================================
// Dung event delegation: lang nghe dblclick tren .dt-footer
// DataTable render footer bang innerHTML nen can delegate.
frappe.EUP_REPORT_AGG._bindTotalRowClick = function(datatable) {
	if (!datatable || datatable._eup_total_click_bound) return;
	datatable._eup_total_click_bound = true;

	var wrapper = datatable.wrapper;
	if (!wrapper) return;

	// Dung event delegation: lang nghe dblclick tren wrapper, loc .dt-footer
	wrapper.addEventListener('dblclick', function(e) {
		// Tranh mo nhieu dialog cung luc
		if (frappe.EUP_REPORT_AGG._dialogOpen) return;
		if (frappe.EUP_REPORT_AGG._clickTimer) return;

		var target = e.target;
		// Tim cell duoc click (di len den .dt-cell)
		var cellEl = target.closest ? target.closest('.dt-cell') : null;
		if (!cellEl) return;

		// Kiem tra co nam trong footer khong
		var footer = cellEl.closest ? cellEl.closest('.dt-footer') : null;
		if (!footer) return;

		e.stopPropagation();
		e.stopImmediatePropagation();

		// Lay colIndex tu data attribute
		var colIdx = parseInt(cellEl.getAttribute('data-col-index'));
		if (isNaN(colIdx) || colIdx < 0) return;

		var cols = datatable.datamanager ? datatable.datamanager.getColumns() : null;
		if (!cols || !cols[colIdx]) return;
		var column = cols[colIdx];

		// Lay reportName
		var reportName = '';
		if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
		else if (frappe.query_report) reportName = frappe.query_report.report_name;

		// Set timer de tranh double-click lien tiep (300ms)
		frappe.EUP_REPORT_AGG._clickTimer = setTimeout(function() {
			frappe.EUP_REPORT_AGG._clickTimer = null;
		}, 300);

		if (frappe.EUP_REPORT_AGG.showAggDialog) {
			frappe.EUP_REPORT_AGG.showAggDialog(column, datatable, reportName);
		}
	});

	console.log('[Report Agg] Total row click bound');
};

// ============================================================
// 8. REFRESH TOTAL ROW
// ============================================================
frappe.EUP_REPORT_AGG.refreshTotalRow = function(datatable) {
	if (!datatable) return;
	if (datatable.bodyRenderer) datatable.bodyRenderer.renderFooter();
	// Re-bind click event sau khi refresh
	setTimeout(function() { frappe.EUP_REPORT_AGG._bindTotalRowClick(datatable); }, 100, datatable);
};

// ============================================================
// 9. SHOW INDICATOR
// ============================================================
frappe.EUP_REPORT_AGG.showAggChangedToast = function(columnLabel, fnName) {
	var info = this.labels[fnName];
	var label = info ? info.label : fnName;
	frappe.show_alert({ message: __('Column {0}: {1}', [__(columnLabel || ''), label]), indicator: 'green' }, 3);
};

console.log('[Report Agg] Core loaded. Double-click Total cell to change aggregation.');

// ============================================================
// 7a. TOTAL ROW POSITION — di chuyen dong Total len tren cung
// ============================================================
// Bien cache total_row_position cho moi report
frappe.EUP_REPORT_AGG._totalRowPosition = frappe.EUP_REPORT_AGG._totalRowPosition || {};

frappe.EUP_REPORT_AGG.applyTotalRowPosition = function(datatable) {
	if (!datatable || !datatable.wrapper) return;

	var wrapper = datatable.wrapper;
	var reportName = '';
	if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
	else if (frappe.query_report) reportName = frappe.query_report.report_name;
	if (!reportName) return;

	// Doc tu config report + fallback tu frappe.query_reports
	var position = frappe.EUP_REPORT_AGG._totalRowPosition[reportName];
	if (!position) {
		var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
		if (repConf && repConf.total_row_position) {
			frappe.EUP_REPORT_AGG._totalRowPosition[reportName] = repConf.total_row_position;
			position = repConf.total_row_position;
		}
	}
	position = position || 'bottom';
	// Kiem tra localStorage override
	var lsPos = frappe.EUP_REPORT_AGG._loadPositionSettings(reportName);
	if (lsPos) position = lsPos;

	// Luu lai de dung sau
	frappe.EUP_REPORT_AGG._totalRowPosition[reportName] = position;

	// Tim .datatable ben trong wrapper de set flex
	var dtWrapper = wrapper.querySelector('.datatable');
	if (!dtWrapper) return;

	var footer = wrapper.querySelector('.dt-footer');
	if (!footer) return;

	if (position === 'top') {
		// Total o giua header va body (sau header, truoc data rows)
		var hdr = wrapper.querySelector('.dt-header');
		var scb = wrapper.querySelector('.dt-scrollable');
		footer.style.order = '1';
		if (hdr) hdr.style.order = '0';
		if (scb) scb.style.order = '2';
		dtWrapper.style.display = 'flex';
		dtWrapper.style.flexDirection = 'column';
		footer.style.borderTop = '';
		footer.style.borderBottom = '2px solid var(--dt-border-color, #d1d8dd)';
	} else {
		footer.style.order = '';
		var hdr = wrapper.querySelector('.dt-header');
		var scb = wrapper.querySelector('.dt-scrollable');
		if (hdr) hdr.style.order = '';
		if (scb) scb.style.order = '';
		footer.style.borderTop = '';
		footer.style.borderBottom = '';
		dtWrapper.style.display = '';
		dtWrapper.style.flexDirection = '';
	}
};

// ============================================================
// 7b. HEADER GROUPS — merge cell kieu Excel (multi-level header)
// ============================================================
frappe.EUP_REPORT_AGG._headerGroups = frappe.EUP_REPORT_AGG._headerGroups || {};

// Hàm toggle bold header trên UI (sử dụng dynamic style tag trên wrapper)
// Dùng CSS !important để override cả inline style của header group cells
frappe.EUP_REPORT_AGG._toggleBoldHeaderUI = function(reportName, enable) {
    var safeName = reportName.replace(/[^a-zA-Z0-9_-]/g, '_');
    var styleId = 'eup-bold-header-style-' + safeName;
    var existing = document.getElementById(styleId);
    if (existing) existing.remove();

    // Luôn inject style quản lý bold để tránh inline style bị mất sync
    var style = document.createElement('style');
    style.id = styleId;
    if (enable) {
        // Bold: header cells và group cells đều đậm
        style.textContent = `
            .eup-bold-header-${safeName} .dt-cell--header .dt-cell__content,
            .eup-bold-header-${safeName} .eup-header-group-cell {
                font-weight: 600 !important;
            }
        `;
        document.head.appendChild(style);
        var headers = document.querySelectorAll('.dt-header');
        headers.forEach(function(h) {
            h.classList.add('eup-bold-header-' + safeName);
            h.classList.remove('eup-no-bold-header-' + safeName);
        });
    } else {
        // Không bold: header cells và group cells bình thường
        style.textContent = `
            .eup-no-bold-header-${safeName} .dt-cell--header .dt-cell__content,
            .eup-no-bold-header-${safeName} .eup-header-group-cell {
                font-weight: normal !important;
            }
        `;
        document.head.appendChild(style);
        var headers = document.querySelectorAll('.dt-header');
        headers.forEach(function(h) {
            h.classList.add('eup-no-bold-header-' + safeName);
            h.classList.remove('eup-bold-header-' + safeName);
        });
    }

    // Apply luôn vào các cell đã render (trong trường hợp DOM đã có)
    var cells = document.querySelectorAll('.eup-header-group-cell');
    cells.forEach(function(cell) {
        cell.style.fontWeight = '';
    });
};

frappe.EUP_REPORT_AGG.applyHeaderGroups = function(datatable) {
    if (!datatable || !datatable.wrapper) return;

    // Hủy timeout cũ
    if (datatable._eup_header_groups_timeout) {
        clearTimeout(datatable._eup_header_groups_timeout);
        datatable._eup_header_groups_timeout = null;
    }

    // Nếu đang có build chạy, bỏ qua
    if (datatable._eup_building_header) {
        return;
    }

    var reportName = '';
    if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
    else if (frappe.query_report) reportName = frappe.query_report.report_name;
    if (!reportName) return;

    var groups = frappe.EUP_REPORT_AGG._headerGroups[reportName];
    if (!groups || !groups.length) {
        var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
        if (repConf && repConf.header_groups) {
            frappe.EUP_REPORT_AGG._headerGroups[reportName] = repConf.header_groups;
            groups = repConf.header_groups;
        }
    }

    // Đọc config bold_header
    var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
    var boldHeader = repConf && repConf.bold_header ? true : false;

    // Áp dụng toggle bold header cho UI
    frappe.EUP_REPORT_AGG._toggleBoldHeaderUI(reportName, boldHeader);

    // Xóa tất cả các hàng header group cũ và listener
    frappe.EUP_REPORT_AGG._teardownHeaderGroupRow(datatable);

    if (!groups || !groups.length) return;

    // Đánh dấu đang build
    datatable._eup_building_header = true;

    // Dùng setTimeout debounce, nhưng kiểm tra cờ trước khi build
    datatable._eup_header_groups_timeout = setTimeout(function() {
        datatable._eup_header_groups_timeout = null;
        // Kiểm tra cờ: nếu vẫn đang build (có thể do nhiều lần gọi) thì bỏ qua
        if (datatable._eup_building_header) {
            frappe.EUP_REPORT_AGG._buildHeaderGroupRow(datatable, groups);
        }
    }, 200);
};

// Go bo hang tieu de nhom + ngat toan bo observer/listener dang theo doi.
frappe.EUP_REPORT_AGG._teardownHeaderGroupRow = function(datatable) {
    if (!datatable) return;

    // Xóa TẤT CẢ các hàng .eup-header-group-row trong .dt-header
    var wrapper = datatable.wrapper;
    if (wrapper) {
        var headerEl = wrapper.querySelector('.dt-header');
        if (headerEl) {
            var rows = headerEl.querySelectorAll('.eup-header-group-row');
            rows.forEach(function(row) {
                if (row.parentNode) row.parentNode.removeChild(row);
            });
        }
    }

    // Hủy state cũ (observer/listener)
    var state = datatable._eup_header_group_state;
    if (state) {
        if (state.watcher) { try { state.watcher.disconnect(); } catch(e) {} }
        if (state.resizeObserver) { try { state.resizeObserver.disconnect(); } catch(e) {} }
        if (state.onWindowResize) { try { window.removeEventListener('resize', state.onWindowResize); } catch(e) {} }
        if (state.onMouseDown) { try { document.removeEventListener('mousedown', state.onMouseDown, true); } catch(e) {} }
        if (state.onMouseUp) { try { document.removeEventListener('mouseup', state.onMouseUp, true); } catch(e) {} }
        if (state.onDragStart) { try { document.removeEventListener('dragstart', state.onDragStart, true); } catch(e) {} }
        if (state.onDragEnd) {
            try { document.removeEventListener('dragend', state.onDragEnd, true); } catch(e) {}
            try { document.removeEventListener('drop', state.onDragEnd, true); } catch(e) {}
        }
        if (state.row && state.row.parentNode) {
            try { state.row.parentNode.removeChild(state.row); } catch(e) {}
        }
    }
    datatable._eup_header_group_state = null;
};

// ============================================================
// HÀM DỰNG HEADER GROUP — CÓ HỖ TRỢ BOLD HEADER
// ============================================================
frappe.EUP_REPORT_AGG._buildHeaderGroupRow = function(datatable, groups) {
    if (!datatable || !datatable.wrapper) return;

    // Nếu cờ build đã bị reset (bởi một lần teardown khác) thì không build
    if (!datatable._eup_building_header) {
        return;
    }

    var headerEl = datatable.wrapper.querySelector('.dt-header');
    if (!headerEl) {
        datatable._eup_building_header = false;
        return;
    }

    // Xóa sạch các hàng group cũ (phòng trường hợp có sót)
    var oldRows = headerEl.querySelectorAll('.eup-header-group-row');
    oldRows.forEach(function(row) { if (row.parentNode) row.parentNode.removeChild(row); });

    // Hủy state cũ
    frappe.EUP_REPORT_AGG._teardownHeaderGroupRow(datatable);

    var columns = datatable.datamanager ? datatable.datamanager.getColumns() : null;
    if (!columns || !columns.length) {
        datatable._eup_building_header = false;
        return;
    }

    var state = {
        row: null, watcher: null, resizeObserver: null, onWindowResize: null,
        onMouseDown: null, onMouseUp: null, onDragStart: null, onDragEnd: null,
        isDragging: false
    };
    datatable._eup_header_group_state = state;

    function makeAbsCell(left, width, height, text, borderStyle, isOverlayMerge, bgColor) {
        var cell = document.createElement('div');
        cell.className = 'eup-header-group-cell';
        cell.style.position = 'absolute';
        cell.style.top = '0';
        cell.style.left = left + 'px';
        cell.style.width = width + 'px';
        cell.style.height = height + 'px';
        cell.style.boxSizing = 'border-box';
        cell.style.display = 'flex';
        cell.style.alignItems = 'center';
        cell.style.justifyContent = 'center';
        cell.style.textAlign = 'center';
        cell.style.fontWeight = ''; // bold duoc quan ly qua CSS class trong _toggleBoldHeaderUI
        cell.style.padding = '0 8px';
        cell.style.margin = '0';
        cell.style.overflow = 'hidden';
        cell.style.textOverflow = 'ellipsis';
        cell.style.whiteSpace = 'nowrap';
        cell.style.borderRadius = '0';
        cell.style.boxShadow = 'none';
        cell.style.borderTop = borderStyle.top;
        cell.style.borderRight = borderStyle.right;
        cell.style.borderBottom = borderStyle.bottom;
        cell.style.borderLeft = borderStyle.left;

        if (isOverlayMerge) {
            cell.style.pointerEvents = 'none';
            cell.style.zIndex = '20';
            cell.style.background = bgColor || '#fff';
        } else {
            cell.style.background = 'transparent';
        }
        cell.innerHTML = text || '';
        return cell;
    }

    function buildRowContent(headerRow) {
        var headerCells = headerRow.children;
        var totalCols = headerCells.length;
        if (!totalCols) return;

        state.row.innerHTML = '';

        var headerRowRect = headerRow.getBoundingClientRect();
        var rowHeight = headerRowRect.height || 32;
        state.row.style.height = rowHeight + 'px';
        state.row.style.width = headerRowRect.width + 'px';

        var sampleCell = headerCells[0];
        if (sampleCell) {
            var cs = getComputedStyle(sampleCell);
            if (cs.fontFamily) state.row.style.fontFamily = cs.fontFamily;
            if (cs.fontSize) state.row.style.fontSize = cs.fontSize;
            if (cs.color) state.row.style.color = cs.color;
        }

        var cellStyles = [];
        for (var i = 0; i < totalCols; i++) {
            var cs = getComputedStyle(headerCells[i]);
            cellStyles.push({
                top: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
                right: cs.borderRightWidth + ' ' + cs.borderRightStyle + ' ' + cs.borderRightColor,
                bottom: cs.borderBottomWidth + ' ' + cs.borderBottomStyle + ' ' + cs.borderBottomColor,
                left: cs.borderLeftWidth + ' ' + cs.borderLeftStyle + ' ' + cs.borderLeftColor,
                bg: cs.backgroundColor
            });
        }

        var domFieldToIndex = {};
        for (var di = 0; di < totalCols; di++) {
            var ciAttr = headerCells[di].getAttribute('data-col-index');
            var ci = ciAttr !== null ? parseInt(ciAttr, 10) : NaN;
            var colObj = !isNaN(ci) && columns[ci] ? columns[ci] : null;
            if (colObj && colObj.id) domFieldToIndex[colObj.id] = di;
        }

        var colGroupMap = [];
        for (var i = 0; i < totalCols; i++) colGroupMap[i] = -1;
        for (var g = 0; g < groups.length; g++) {
            var grp = groups[g];
            var fi = grp.from ? domFieldToIndex[grp.from] : 0;
            var ti = grp.to ? domFieldToIndex[grp.to] : (totalCols - 1);
            if (fi === undefined) fi = 0;
            if (ti === undefined) ti = totalCols - 1;
            if (fi < 0) fi = 0;
            if (ti >= totalCols) ti = totalCols - 1;
            for (var c = fi; c <= ti; c++) colGroupMap[c] = g;
        }

        var i = 0;
        while (i < totalCols) {
            var gIdx = colGroupMap[i];
            if (gIdx >= 0) {
                var grp = groups[gIdx];
                var j = i;
                while (j < totalCols && colGroupMap[j] === gIdx) j++;
                var firstRect = headerCells[i].getBoundingClientRect();
                var lastRect = headerCells[j - 1].getBoundingClientRect();
                var left = firstRect.left - headerRowRect.left;
                var width = lastRect.right - firstRect.left;
                var borderStyle = {
                    top: cellStyles[i].top,
                    right: cellStyles[j - 1].right,
                    bottom: cellStyles[i].bottom,
                    left: cellStyles[i].left
                };
                state.row.appendChild(makeAbsCell(
                    left, width, rowHeight, frappe._(grp.title || ''),
                    borderStyle, false, null
                ));
                i = j;
            } else {
                var rect = headerCells[i].getBoundingClientRect();
                var left = rect.left - headerRowRect.left;
                var width = rect.width;
                var contentEl = headerCells[i].querySelector('.dt-cell__content');
                var label = contentEl ? contentEl.textContent.trim() : '';
                var fullHeight = rowHeight + headerRowRect.height;
                var bgColor = cellStyles[i].bg;
                if (!bgColor || bgColor === 'rgba(0, 0, 0, 0)') bgColor = '#fff';
                var borderStyle = {
                    top: cellStyles[i].top,
                    right: cellStyles[i].right,
                    bottom: cellStyles[i].bottom,
                    left: cellStyles[i].left
                };
                state.row.appendChild(makeAbsCell(
                    left, width, fullHeight, frappe._(label),
                    borderStyle, true, bgColor
                ));
                i++;
            }
        }
    }

    function ensureRowAttached(headerRow) {
        var headerContainer = headerRow.parentNode;
        if (!headerContainer) return false;
        if (!state.row) {
            state.row = document.createElement('div');
            state.row.className = 'eup-header-group-row';
            state.row.style.position = 'relative';
            state.row.style.boxSizing = 'border-box';
            state.row.style.overflow = 'visible';
            state.row.style.zIndex = '15';
        }
        if (state.row.parentNode !== headerContainer || state.row.nextSibling !== headerRow) {
            headerContainer.insertBefore(state.row, headerRow);
        }
        return true;
    }

    var syncScheduled = false;
    function scheduleSync() {
        if (state.isDragging) return;
        if (syncScheduled) return;
        syncScheduled = true;
        requestAnimationFrame(function () {
            syncScheduled = false;
            sync();
        });
    }

    function sync() {
        var headerRow = headerEl.querySelector('.dt-row-header');
        if (!headerRow) return;

        if (state.watcher) state.watcher.disconnect();
        if (state.resizeObserver) state.resizeObserver.disconnect();
        try {
            if (ensureRowAttached(headerRow)) buildRowContent(headerRow);
            if (state.resizeObserver) {
                state.resizeObserver.observe(headerRow);
                for (var k = 0; k < headerRow.children.length; k++) {
                    state.resizeObserver.observe(headerRow.children[k]);
                }
            }
        } finally {
            if (state.watcher) {
                state.watcher.observe(headerEl, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['style', 'class']
                });
            }
        }
        // Sau khi sync xong, reset cờ build
        datatable._eup_building_header = false;
    }

    state.watcher = new MutationObserver(scheduleSync);
    state.watcher.observe(headerEl, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['style', 'class']
    });

    if (typeof ResizeObserver !== 'undefined') {
        state.resizeObserver = new ResizeObserver(scheduleSync);
    }

    state.onWindowResize = function () { scheduleSync(); };
    window.addEventListener('resize', state.onWindowResize);

    state.onMouseDown = function (e) {
        if (headerEl.contains(e.target)) state.isDragging = true;
    };
    state.onMouseUp = function () {
        if (state.isDragging) {
            state.isDragging = false;
            scheduleSync();
        }
    };
    state.onDragStart = function (e) {
        if (headerEl.contains(e.target)) state.isDragging = true;
    };
    state.onDragEnd = function () {
        if (state.isDragging) {
            state.isDragging = false;
            scheduleSync();
        }
    };
    document.addEventListener('mousedown', state.onMouseDown, true);
    document.addEventListener('mouseup', state.onMouseUp, true);
    document.addEventListener('dragstart', state.onDragStart, true);
    document.addEventListener('dragend', state.onDragEnd, true);
    document.addEventListener('drop', state.onDragEnd, true);

    sync();
};
// ============================================================
// 7c. LUU / DOC total_row_position (localStorage)
// ============================================================
frappe.EUP_REPORT_AGG.POSITION_STORAGE_PREFIX = 'eup_report_agg_pos';
frappe.EUP_REPORT_AGG._loadPositionSettings = function(reportName) {
	try {
		var key = this.POSITION_STORAGE_PREFIX + ':' + (frappe.session.user || 'Guest') + ':' + (reportName || '');
		return localStorage.getItem(key) || null;
	} catch(e) { return null; }
};
frappe.EUP_REPORT_AGG._savePositionSettings = function(reportName, position) {
	try {
		var key = this.POSITION_STORAGE_PREFIX + ':' + (frappe.session.user || 'Guest') + ':' + (reportName || '');
		if (position && position !== 'bottom') localStorage.setItem(key, position);
		else localStorage.removeItem(key);
	} catch(e) {}
};

// ============================================================
// 7d. BIND TOTAL ROW + RENDER HOOKS
// ============================================================
// Pat vao render_datatable de apply total position + header groups
var _orig_render = frappe.views.QueryReport.prototype.render_datatable;
if (_orig_render) {
	frappe.views.QueryReport.prototype.render_datatable = function() {
		if (this.columns && this.report_name) {
			frappe.EUP_REPORT_AGG.applySettingsToColumns(this.columns, this.report_name, this.report_settings);
		}
		var result = _orig_render.apply(this, arguments);
		if (this.datatable) {
			this.datatable._eup_report_instance = this;
			if (this.datatable.options && this.datatable.options.hooks) {
				this.datatable.options.hooks.columnTotal = _eup_column_total;
			}
			_eup_patch_body_renderer(this.datatable);
			_eup_patch_datamanager_getColumns(this.datatable);
			setTimeout(function(dt) { frappe.EUP_REPORT_AGG._bindTotalRowClick(dt); }, 100, this.datatable);
			setTimeout(function(dt) { if (frappe.EUP_REPORT_AGG._bindTotalRowContextMenu) frappe.EUP_REPORT_AGG._bindTotalRowContextMenu(dt); }, 150, this.datatable);
			// Apply total row position + header groups
			setTimeout(function(dt) {
				frappe.EUP_REPORT_AGG.applyTotalRowPosition(dt);
				frappe.EUP_REPORT_AGG.applyHeaderGroups(dt);
			}, 300, this.datatable);
		}
		return result;
	};
}

// Report Builder
var _orig_rv_setup = frappe.views.ReportView.prototype.setup_datatable;
if (_orig_rv_setup) {
	frappe.views.ReportView.prototype.setup_datatable = function(values) {
		var result = _orig_rv_setup.apply(this, arguments);
		if (this.datatable) {
			this.datatable._eup_report_instance = this;
			if (this.datatable.options && this.datatable.options.hooks) {
				this.datatable.options.hooks.columnTotal = _eup_column_total;
			}
			_eup_patch_body_renderer(this.datatable);
			_eup_patch_datamanager_getColumns(this.datatable);
			setTimeout(function(dt) { frappe.EUP_REPORT_AGG._bindTotalRowClick(dt); }, 100, this.datatable);
			setTimeout(function(dt) { if (frappe.EUP_REPORT_AGG._bindTotalRowContextMenu) frappe.EUP_REPORT_AGG._bindTotalRowContextMenu(dt); }, 150, this.datatable);
			// Apply total row position + header groups
			setTimeout(function(dt) {
				frappe.EUP_REPORT_AGG.applyTotalRowPosition(dt);
				frappe.EUP_REPORT_AGG.applyHeaderGroups(dt);
			}, 300, this.datatable);
		}
		return result;
	};
}

// Capture config tu frappe.query_reports - chay trong frappe:init
$(document).on('frappe:init', function() {
	frappe.EUP_REPORT_AGG._totalRowPosition = frappe.EUP_REPORT_AGG._totalRowPosition || {};
	frappe.EUP_REPORT_AGG._headerGroups = frappe.EUP_REPORT_AGG._headerGroups || {};
	for (var k in frappe.query_reports) {
		if (frappe.query_reports.hasOwnProperty(k)) {
			var obj = frappe.query_reports[k];
			if (obj.total_row_position) frappe.EUP_REPORT_AGG._totalRowPosition[k] = obj.total_row_position;
			if (obj.header_groups) frappe.EUP_REPORT_AGG._headerGroups[k] = obj.header_groups;
		}
	}
});


// ============================================================
// 10. EXPORT EXCEL VỚI HEADER GROUPS & BOLD (client-side)
// ============================================================
(function() {
    // Tải thư viện XLSX nếu chưa có
    function loadXLSX(callback) {
        if (typeof XLSX !== 'undefined') {
            callback();
            return;
        }
        var script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
        script.onload = callback;
        script.onerror = function() {
            frappe.msgprint(__('Không thể tải thư viện XLSX. Vui lòng kiểm tra kết nối mạng.'));
        };
        document.head.appendChild(script);
    }

    // Tạo workbook với header groups và bold
    function buildExcelWorkbookWithGroups(reportName, data, columns, headerGroups, boldHeader) {
        var wb = XLSX.utils.book_new();

        // Dòng header chính (label của các cột)
        var headerRow = columns.map(function(col) {
            return col.label || col.fieldname || '';
        });
        var rows = [headerRow];

        // Dòng dữ liệu
        data.forEach(function(row) {
            var rowData = columns.map(function(col) {
                var val = row[col.fieldname];
                return (val !== undefined && val !== null) ? val : '';
            });
            rows.push(rowData);
        });

        var merge = [];
        // Nếu có header_groups, chèn thêm hàng nhóm phía trên
        if (headerGroups && headerGroups.length) {
            var groupRow = new Array(columns.length).fill('');
            var colIndexMap = {};
            columns.forEach(function(col, idx) {
                colIndexMap[col.fieldname] = idx;
            });

            headerGroups.forEach(function(grp) {
                var fromIdx = colIndexMap[grp.from];
                var toIdx = colIndexMap[grp.to];
                if (fromIdx === undefined || toIdx === undefined) return;
                if (fromIdx > toIdx) { var tmp = fromIdx; fromIdx = toIdx; toIdx = tmp; }
                groupRow[fromIdx] = grp.title || '';
                merge.push({ s: { r: 0, c: fromIdx }, e: { r: 0, c: toIdx } });
            });

            // Chèn hàng nhóm vào đầu
            rows.unshift(groupRow);
        }

        var ws = XLSX.utils.aoa_to_sheet(rows);
        if (merge.length) ws['!merges'] = merge;

        // Tự động độ rộng cột
        var colWidths = columns.map(function(col, idx) {
            var maxLen = (col.label || col.fieldname || '').length;
            data.forEach(function(row) {
                var val = row[col.fieldname];
                if (val !== undefined && val !== null) {
                    var len = String(val).length;
                    if (len > maxLen) maxLen = len;
                }
            });
            return { wch: Math.min(Math.max(maxLen + 2, 10), 50) };
        });
        ws['!cols'] = colWidths;

        // Áp dụng bold cho tất cả header (cả group và cột) nếu boldHeader = true
        if (boldHeader) {
            var numHeaderRows = (headerGroups && headerGroups.length) ? 2 : 1;
            var range = XLSX.utils.decode_range(ws['!ref']);
            for (var R = range.s.r; R < range.s.r + numHeaderRows; R++) {
                for (var C = range.s.c; C <= range.e.c; C++) {
                    var addr = XLSX.utils.encode_cell({ r: R, c: C });
                    if (!ws[addr]) continue;
                    if (!ws[addr].s) ws[addr].s = {};
                    ws[addr].s.font = { bold: true };
                }
            }
        }

        XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
        return wb;
    }

    // Hàm export chính
    function exportExcelWithHeaderGroups(reportName, data, columns, headerGroups, boldHeader) {
        if (!data || !data.length) {
            frappe.msgprint(__('Không có dữ liệu để xuất.'));
            return;
        }

        loadXLSX(function() {
            try {
                var wb = buildExcelWorkbookWithGroups(reportName, data, columns, headerGroups, boldHeader);
                var wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
                var blob = new Blob([wbout], { type: 'application/octet-stream' });
                var link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = (reportName || 'report') + '.xlsx';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(link.href);
            } catch (e) {
                frappe.msgprint(__('Lỗi xuất Excel: ') + e.message);
            }
        });
    }

    // ----- GHI ĐÈ PHƯƠNG THỨC export_report của QueryReport -----
    var origExportReport = frappe.views.QueryReport.prototype.export_report;
    if (origExportReport) {
        frappe.views.QueryReport.prototype.export_report = function() {
            var reportName = this.report_name;
            var data = this.data || [];
            var columns = this.columns || [];
            var headerGroups = frappe.EUP_REPORT_AGG._headerGroups[reportName] || [];
            var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
            var boldHeader = repConf && repConf.bold_header ? true : false;

            if ((headerGroups && headerGroups.length) || boldHeader) {
                exportExcelWithHeaderGroups(reportName, data, columns, headerGroups, boldHeader);
                return;
            }
            origExportReport.apply(this, arguments);
        };
    }

    // ----- GHI ĐÈ CHO Report Builder (nếu có) -----
    var origRVExport = frappe.views.ReportView.prototype.export_report;
    if (origRVExport) {
        frappe.views.ReportView.prototype.export_report = function() {
            var reportName = this.report_name;
            var data = [];
            if (this.datamanager) {
                var rows = this.datamanager.getRows();
                data = rows.map(function(row) {
                    var obj = {};
                    row.forEach(function(cell, idx) {
                        var col = this.columns[idx];
                        if (col) obj[col.fieldname] = cell.content;
                    }, this);
                    return obj;
                }, this);
            }
            var columns = this.columns || [];
            var headerGroups = frappe.EUP_REPORT_AGG._headerGroups[reportName] || [];
            var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
            var boldHeader = repConf && repConf.bold_header ? true : false;

            if ((headerGroups && headerGroups.length) || boldHeader) {
                exportExcelWithHeaderGroups(reportName, data, columns, headerGroups, boldHeader);
                return;
            }
            origRVExport.apply(this, arguments);
        };
    }
})();