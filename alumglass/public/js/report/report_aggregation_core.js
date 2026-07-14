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
// 7b. PATCH render_datatable
// ============================================================
var _orig_render = frappe.views.QueryReport.prototype.render_datatable;
if (_orig_render) {
	frappe.views.QueryReport.prototype.render_datatable = function() {
		// Apply aggregate_fields vao columns TRUOC KHI render
		if (this.columns && this.report_name) {
			frappe.EUP_REPORT_AGG.applySettingsToColumns(this.columns, this.report_name, this.report_settings);
		}
		var result = _orig_render.apply(this, arguments);
		if (this.datatable) {
			this.datatable._eup_report_instance = this;
			// Dam bao columnTotal hook luon dung ham override
			if (this.datatable.options && this.datatable.options.hooks) {
				this.datatable.options.hooks.columnTotal = _eup_column_total;
			}
			// Patch getTotalRow de set content = "" cho cot none
			_eup_patch_body_renderer(this.datatable);
			setTimeout(function(dt) { frappe.EUP_REPORT_AGG._bindTotalRowClick(dt); }, 100, this.datatable);
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
			// Dam bao columnTotal hook luon dung ham override
			if (this.datatable.options && this.datatable.options.hooks) {
				this.datatable.options.hooks.columnTotal = _eup_column_total;
			}
			// Patch getTotalRow de set content = "" cho cot none
			_eup_patch_body_renderer(this.datatable);
			setTimeout(function(dt) { frappe.EUP_REPORT_AGG._bindTotalRowClick(dt); }, 100, this.datatable);
		}
		return result;
	};
}

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
