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


if (!frappe.EUP_REPORT_AGG) {
	frappe.EUP_REPORT_AGG = {};
}

frappe.EUP_REPORT_AGG._aggCache = {};

// ============================================================
// UTILITY: Lay kieu du lieu cua cot tu column definitions
// Tra ve: 'number', 'date', 'text' (mac dinh)
// ============================================================
function _eup_get_column_type(fieldname) {
	// Uu tien lay tu frappe.query_report.columns (Query Report)
	try {
		var cols = frappe.query_report && frappe.query_report.columns;
		if (cols && cols.length) {
			for (var i=0; i<cols.length; i++) {
				if (cols[i].fieldname === fieldname) {
					var ft = cols[i].fieldtype || '';
					if (ft === 'Date' || ft === 'Datetime' || ft === 'Time') return 'date';
					if (ft === 'Int' || ft === 'Float' || ft === 'Currency' || ft === 'Percent'
						|| ft === 'Duration' || ft === 'Rating' || ft.indexOf('Int') >= 0
						|| ft.indexOf('Float') >= 0 || ft.indexOf('Number') >= 0)
						return 'number';
					return 'text';
				}
			}
		}
	} catch(e) {}
	// Fallback 1: doc tu frappe.model.docinfo neu co
	try {
		if (frappe.model && frappe.model.docinfo && frappe.meta && frappe.meta.docfield) {
			var df = frappe.meta.docfield && frappe.meta.docfield(frappe.query_report && frappe.query_report.report_name, fieldname);
			if (df && df.fieldtype) {
				var ft = df.fieldtype;
				if (ft === 'Date' || ft === 'Datetime' || ft === 'Time') return 'date';
				if (ft === 'Int' || ft === 'Float' || ft === 'Currency' || ft === 'Percent'
					|| ft === 'Duration' || ft === 'Rating')
					return 'number';
				// Da co fieldtype ro rang va khong phai so/ngay => chac chan la text
				return 'text';
			}
		}
	} catch(e) {}

	try {
		var raw = _eup_get_raw_data();
		if (raw && raw.length) {
			var sampleSize = Math.min(raw.length, 30);
			var numCount = 0, dateCount = 0, validCount = 0;
			for (var si = 0; si < sampleSize; si++) {
				var row = raw[si];
				if (!row || !(fieldname in row)) continue;
				var v = row[fieldname];
				if (v === null || v === undefined || v === '') continue;
				validCount++;
				if (typeof v === 'number' && isFinite(v)) { numCount++; continue; }
				if (v instanceof Date) { dateCount++; continue; }
				var vs = String(v).trim();
				// Chuoi thuan so (co the co dau phay ngan cach, dau am, dau cham thap phan)
				if (/^-?[\d.,]+$/.test(vs) && !isNaN(_eup_to_num(vs))) { numCount++; continue; }
				// Chuoi dang ngay YYYY-MM-DD hoac DD/MM/YYYY
				if (/^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$/.test(vs) || /^\d{2}\/\d{2}\/\d{4}$/.test(vs)) {
					if (_eup_to_date(vs) !== null) { dateCount++; continue; }
				}
			}
			// Chi ket luan khi TOAN BO gia tri mau (khac rong) dong nhat 1 kieu,
			// tranh nhan dien sai cho cot text co lan chua vai gia tri giong so
			if (validCount > 0 && numCount === validCount) return 'number';
			if (validCount > 0 && dateCount === validCount) return 'date';
		}
	} catch(e) {}
	return 'text';
}

// ============================================================
// UTILITY: Lấy data gốc từ report instance
// ============================================================
function _eup_get_raw_data() {
	try {
		var qr = frappe.query_report;
		if (!qr || !qr.data) return null;
		var hasTotalRowAppended = !!(qr.raw_data && qr.raw_data.add_total_row);
		if (hasTotalRowAppended && qr.data.length) return qr.data.slice(0, -1);
		return qr.data;
	} catch(e) {}
	return null;
}

function _eup_get_filtered_data() {
	try {
		var qr = frappe.query_report;
		if (!qr || !qr.datatable) return null;
		var dt = qr.datatable;
		var cols = dt.datamanager.getColumns();
		var rows = dt.bodyRenderer.visibleRows;
		if (!rows || !rows.length) return null;
		// Kiem tra neu visibleRows co cung so luong voi total data -> khong co filter
		// thi tra ve _eup_get_raw_data() de tranh mat precision cua field number
		var rawData = _eup_get_raw_data();
		if (rawData && rawData.length === rows.length) return rawData;
		return rows.map(function(row) {
			var obj = {};
			for (var c=0; c<cols.length; c++) {
				obj[cols[c].id] = row[c] ? row[c].content : null;
			}
			return obj;
		});
	} catch(e) {}
	// Fallback: tra ve raw data
	return _eup_get_raw_data();
}

function _eup_compare_values(cellValue, cmpRaw) {
	// Uu tien so sanh SO
	var cellNum = _eup_to_num(cellValue);
	var cmpNum = _eup_to_num(cmpRaw);
	if (!isNaN(cellNum) && !isNaN(cmpNum)) {
		if (cellNum < cmpNum) return -1;
		if (cellNum > cmpNum) return 1;
		return 0;
	}
	// Khong phai so ca hai ben -> thu so sanh NGAY
	var cellDate = _eup_to_date(cellValue);
	var cmpDate = _eup_to_date(cmpRaw);
	if (cellDate !== null && cmpDate !== null) {
		var ct = cellDate.getTime(), pt = cmpDate.getTime();
		if (ct < pt) return -1;
		if (ct > pt) return 1;
		return 0;
	}
	return null; // khong so sanh duoc theo so/ngay -> de goi so sanh theo chuoi
}

function _eup_match_condition(cellValue, condition) {
	if (condition === undefined || condition === null || condition === '') return true;
	var c = _eup_to_str(condition).trim();

	// Trich xuat toan tu 2 ky tu (<>, !=, >=, <=) TRUOC toan tu 1 ky tu (>, <, =),
	// khong co toan tu -> mac dinh la so sanh bang (=).
	var op = null, cmpRaw = null;
	if (c.indexOf('<>') === 0) { op = '<>'; cmpRaw = c.substring(2); }
	else if (c.indexOf('!=') === 0) { op = '!='; cmpRaw = c.substring(2); }
	else if (c.indexOf('>=') === 0) { op = '>='; cmpRaw = c.substring(2); }
	else if (c.indexOf('<=') === 0) { op = '<='; cmpRaw = c.substring(2); }
	else if (c.indexOf('>') === 0) { op = '>'; cmpRaw = c.substring(1); }
	else if (c.indexOf('<') === 0) { op = '<'; cmpRaw = c.substring(1); }
	else if (c.indexOf('=') === 0) { op = '='; cmpRaw = c.substring(1); }
	else { op = '='; cmpRaw = c; }
	cmpRaw = cmpRaw.trim();

	// --- Wildcard (*, ?) — chi ap dung y nghia cho =, != , <> giong Excel ---
	if (cmpRaw.indexOf('*') >= 0 || cmpRaw.indexOf('?') >= 0) {
		var sW = _eup_to_str(cellValue);
		var reStrW = cmpRaw.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
		var isMatch = new RegExp('^' + reStrW + '$', 'i').test(sW);
		if (op === '<>' || op === '!=') return !isMatch;
		return isMatch;
	}

	var isBlank = (cellValue === null || cellValue === undefined || cellValue === '');

	// --- Toan tu = ---
	if (op === '=') {
		if (isBlank) return cmpRaw === '';
		var cmpEq = _eup_compare_values(cellValue, cmpRaw);
		if (cmpEq !== null) return cmpEq === 0;
		return _eup_to_str(cellValue).trim().toLowerCase() === cmpRaw.toLowerCase();
	}

	// --- Toan tu != / <> (dung CHUNG logic voi '=', chi dao nguoc ket qua) ---
	if (op === '!=' || op === '<>') {
		if (isBlank) return cmpRaw !== '';
		var cmpNe = _eup_compare_values(cellValue, cmpRaw);
		if (cmpNe !== null) return cmpNe !== 0;
		return _eup_to_str(cellValue).trim().toLowerCase() !== cmpRaw.toLowerCase();
	}

	if (isBlank) return false;

	var cmp = _eup_compare_values(cellValue, cmpRaw);
	if (cmp === null) {
		// Khong ep duoc ve so/ngay o CA HAI phia -> so sanh chuoi (fallback cuoi cung)
		var sT = _eup_to_str(cellValue).trim().toLowerCase();
		var cmpT = cmpRaw.toLowerCase();
		if (op === '>') return sT > cmpT;
		if (op === '>=') return sT >= cmpT;
		if (op === '<') return sT < cmpT;
		if (op === '<=') return sT <= cmpT;
		return false;
	}
	if (op === '>') return cmp === 1;
	if (op === '>=') return cmp === 1 || cmp === 0;
	if (op === '<') return cmp === -1;
	if (op === '<=') return cmp === -1 || cmp === 0;
	return false;
}

// ============================================================
// UTILITY: Chuyen doi gia tri sang Date object
// Tra ve: Date object, hoac null neu khong the parse
// ============================================================
function _eup_to_date(v) {
	if (v === null || v === undefined || v === '') return null;
	// Neu la Date object
	if (v instanceof Date && !isNaN(v.getTime())) return v;
	// Neu la moment object (Frappe)
	if (v._d && v._d instanceof Date && !isNaN(v._d.getTime())) return v._d;
	// Neu la string: ho tro "YYYY-MM-DD", "YYYY-MM-DD HH:mm:ss", "DD/MM/YYYY"
	var s = String(v).trim();
	// Format "YYYY-MM-DD" hoac "YYYY-MM-DD HH:mm:ss"
	var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
	if (m) {
		var d = new Date(parseInt(m[1]), parseInt(m[2])-1, parseInt(m[3]));
		return isNaN(d.getTime()) ? null : d;
	}
	// Format "DD/MM/YYYY" — uu tien khi ngay > 12
	m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
	if (m) {
		var day = parseInt(m[1]), month = parseInt(m[2]), year = parseInt(m[3]);
		// Neu day > 12 chac chan la DD/MM/YYYY
		if (day > 12) {
			var d = new Date(year, month-1, day);
			return isNaN(d.getTime()) ? null : d;
		}
		// Neu month > 12 chac chan la MM/DD/YYYY
		if (month > 12) {
			var d = new Date(year, day-1, month);
			return isNaN(d.getTime()) ? null : d;
		}
		// Ambiguous: uu tien MM/DD/YYYY (format My)
		var d1 = new Date(year, month-1, day);   // DD/MM
		var d2 = new Date(year, day-1, month);    // MM/DD
		if (!isNaN(d1.getTime()) && !isNaN(d2.getTime())) return d2; // uu tien MM/DD
		if (!isNaN(d1.getTime())) return d1;
		if (!isNaN(d2.getTime())) return d2;
		return null;
	}
	return null;
}

// ============================================================
// UTILITY: Lọc rows theo condition
// ============================================================
function _eup_filter_rows(rawData, colFieldname, conditionCol, conditionVal) {
	if (!rawData || !rawData.length) return [];
	// Khong co dieu kien -> lay tat ca gia tri cua colFieldname
	if (!conditionCol || conditionVal === undefined || conditionVal === null || conditionVal === '') {
		return rawData.map(function(r) { return r ? r[colFieldname] : undefined; });
	}

	var result = [];
	for (var _ri = 0; _ri < rawData.length; _ri++) {
		var r = rawData[_ri];
		if (!r) continue;
		if (!_eup_match_condition(r[conditionCol], conditionVal)) continue;
		result.push(r[colFieldname]);
	}
	return result;
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

function _eup_resolveFillerHeaderStyle(reportName, fieldId, columns) {
	if (!fieldId) return null;
	var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
	if (!repConf) return null;

	var colIndexMap = {};
	for (var i = 0; i < columns.length; i++) {
		if (columns[i] && columns[i].id) colIndexMap[columns[i].id] = i;
	}
	var fIdx = colIndexMap[fieldId];

	var result = { bgColor: null, textColor: null };

	// 1) Global header_style ap dung cho MOI header cell
	if (repConf.header_style) {
		if (repConf.header_style.bgColor) result.bgColor = repConf.header_style.bgColor;
		if (repConf.header_style.textColor) result.textColor = repConf.header_style.textColor;
	}

	// 2) header_styles rieng cho field/khoang field nay — uu tien hon global
	if (repConf.header_styles && repConf.header_styles.length && fIdx !== undefined) {
		for (var k = 0; k < repConf.header_styles.length; k++) {
			var hs = repConf.header_styles[k];
			if (!hs || !hs.from) continue;
			var fromIdx = colIndexMap[hs.from];
			var toIdx = colIndexMap[hs.to || hs.from];
			if (fromIdx === undefined) continue;
			if (toIdx === undefined) toIdx = fromIdx;
			if (fromIdx > toIdx) { var tmp = fromIdx; fromIdx = toIdx; toIdx = tmp; }
			if (fIdx >= fromIdx && fIdx <= toIdx) {
				if (hs.bgColor) result.bgColor = hs.bgColor;
				if (hs.textColor) result.textColor = hs.textColor;
				break;
			}
		}
	}

	if (!result.bgColor && !result.textColor) return null;
	return result;
}

function _eup_resolve_group_index(styleEntry, idx, headerGroups) {
	if (!headerGroups || !headerGroups.length) return -1;
	if (styleEntry && styleEntry.from) {
		for (var g = 0; g < headerGroups.length; g++) {
			var grp = headerGroups[g];
			if (!grp) continue;
			// Match chinh xac: from va to deu khop
			if (grp.from === styleEntry.from && (!styleEntry.to || grp.to === styleEntry.to)) {
				return g;
			}

			if (styleEntry.from && styleEntry.from === styleEntry.to && grp.from && grp.to) {

			}
		}
		try {
			var allFieldnames = [];
			if (frappe.query_report && frappe.query_report.columns) {
				allFieldnames = frappe.query_report.columns.map(function(c) { return c.fieldname; });
			}
			if (allFieldnames.length > 0) {
				var fIdx = allFieldnames.indexOf(styleEntry.from);
				if (fIdx >= 0) {
					for (var g2 = 0; g2 < headerGroups.length; g2++) {
						var grp2 = headerGroups[g2];
						if (!grp2 || !grp2.from || !grp2.to) continue;
						var grpFromIdx = allFieldnames.indexOf(grp2.from);
						var grpToIdx = allFieldnames.indexOf(grp2.to);
						if (grpFromIdx >= 0 && grpToIdx >= 0 && fIdx >= grpFromIdx && fIdx <= grpToIdx) {
							return g2;
						}
					}
				}
			}
		} catch(e) {}
		return -1;
	}
	// Khong co from/to rieng -> fallback: khop theo vi tri (dung 1-1 voi header_groups)
	return (idx < headerGroups.length) ? idx : -1;
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
			// FIXED: loc bo NaN/null/undefined truoc khi tinh Math.max
			if (!values || !values.length) return null;
			var nums = [];
			for (var i=0; i<values.length; i++) {
				var n = _eup_to_num(values[i]);
				if (!isNaN(n)) nums.push(n);
			}
			return nums.length ? Math.max.apply(null, nums) : null;
		},
		min: function(values) {
			// FIXED: loc bo NaN/null/undefined truoc khi tinh Math.min
			if (!values || !values.length) return null;
			var nums = [];
			for (var i=0; i<values.length; i++) {
				var n = _eup_to_num(values[i]);
				if (!isNaN(n)) nums.push(n);
			}
			return nums.length ? Math.min.apply(null, nums) : null;
		},
		count: function(values) {
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
			}
			return count;
		},

		countA: function(values) {
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
		sumif: function(rawData, colFieldname, aggConfig) {
			var filtered = _eup_filter_rows(rawData, colFieldname, aggConfig.condition_col, aggConfig.condition);
			return frappe.EUP_REPORT_AGG.functions.sum(filtered);
		},
		countif: function(rawData, colFieldname, aggConfig) {
			var filtered = _eup_filter_rows(rawData, colFieldname, aggConfig.condition_col, aggConfig.condition);
			return filtered.length;
		},
		averageif: function(rawData, colFieldname, aggConfig) {
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
		countif:   { label: '# COUNTIF',            icon: '#↓' },
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

frappe.EUP_REPORT_AGG._aggCache = {};
frappe.EUP_REPORT_AGG._aggCacheActive = false;

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
		return JSON.parse(val) || {};
	} catch(e) { return {}; }
};
frappe.EUP_REPORT_AGG.saveSettings = function(reportName, settings) {
	try {
		var key = this.getStorageKey(reportName);
		localStorage.setItem(key, JSON.stringify(settings));
	} catch(e) { console.warn('[Agg] Save failed', e); }
};

// ============================================================
frappe.EUP_REPORT_AGG._getScriptDefaultAggFields = function(reportName) {
	var reportConfig = frappe.query_reports ? frappe.query_reports[reportName] : null;
	return (reportConfig && reportConfig.aggregate_fields) || null;
};

// ============================================================
frappe.EUP_REPORT_AGG.saveColumnSetting = function(reportName, fieldname, config) {
	if (!reportName || !fieldname) return;
	var settings = this.loadSettings(reportName);
	if (config === null || config === undefined) {
		// Xoa key -> reset ve mac dinh
		delete settings[fieldname];
	} else {
		var defaults = this._getScriptDefaultAggFields(reportName) || {};
		var defaultForField = defaults.hasOwnProperty(fieldname) ? defaults[fieldname] : null;
		settings[fieldname] = {
			value: config,
			_defaultSnapshot: JSON.stringify(defaultForField)
		};
	}
	this.saveSettings(reportName, settings);
};

// ============================================================
frappe.EUP_REPORT_AGG.resetReportSettings = function(reportName) {
	try {
		localStorage.removeItem(this.getStorageKey(reportName));
		frappe.show_alert({ message: __('Đã xoá cache aggregation cho report: ') + reportName, indicator: 'green' }, 3);
	} catch(e) { console.warn('[Agg] Reset failed', e); }
};

// ============================================================
// 3. ÁP DỤNG SETTINGS VÀO COLUMNS
// ============================================================
// Luu tru aggregate_fields doc lap, tranh bi frappe core ghi de
frappe.EUP_REPORT_AGG._configs = frappe.EUP_REPORT_AGG._configs || {};

frappe.EUP_REPORT_AGG.applySettingsToColumns = function(columns, reportName, reportSettings) {
	if (!columns || !reportName) return columns;
	var settings = this.loadSettings(reportName);

	var aggFields = null;
	if (reportSettings && reportSettings.aggregate_fields) {
		aggFields = reportSettings.aggregate_fields;
	} else if (frappe.query_report && frappe.query_report.report_settings && frappe.query_report.report_settings.aggregate_fields) {
		aggFields = frappe.query_report.report_settings.aggregate_fields;
	} else {
		var reportConfig = frappe.query_reports ? frappe.query_reports[reportName] : null;
		if (reportConfig && reportConfig.aggregate_fields) {
			aggFields = reportConfig.aggregate_fields;
		} else {

		}
	}
	if (this._configs[reportName]) {
		aggFields = this._configs[reportName];
	}
	if (aggFields) this._configs[reportName] = aggFields;

	// Config "goc" moi nhat dang khai bao trong script — dung de:
	// 1) fallback khi khong co gi trong localStorage
	// 2) doi chieu versioning, phat hien setting cu (stale) trong localStorage
	var scriptDefaults = this._getScriptDefaultAggFields(reportName) || aggFields || {};

	columns.forEach(function(col) {
		var config = null;
		var stored = settings[col.fieldname];
		var scriptDefaultForField = scriptDefaults ? scriptDefaults[col.fieldname] : undefined;

		if (stored && typeof stored === 'object' && stored.hasOwnProperty('value')) {
			// Setting co versioning (dang moi) — chi dung khi config mac dinh
			// trong script CHUA thay doi so voi luc user luu setting nay.
			var currentSnapshot = JSON.stringify(scriptDefaultForField !== undefined ? scriptDefaultForField : null);
			if (stored._defaultSnapshot === currentSnapshot) {
				config = stored.value; // user thuc su tuy chinh & script khong doi -> giu nguyen
			} else {
				config = (scriptDefaultForField !== undefined) ? scriptDefaultForField
					: (aggFields ? aggFields[col.fieldname] : undefined);
			}
		} else if (stored !== undefined && stored !== null) {
			// Format cu (truoc khi co versioning) — van con trong localStorage
			// tu ban cai truoc. Uu tien tuong thich nguoc, hien thi dung nhu cu.
			config = stored;
		} else if (aggFields && aggFields[col.fieldname] !== undefined) {
			config = aggFields[col.fieldname];
		}

		if (config !== null && config !== undefined) {
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
function _eup_column_total(values, columnOrCell) {
	if (!columnOrCell) return null;
	var column = columnOrCell.column ? columnOrCell.column : columnOrCell;
	if (!column) return null;

	var rawConfig = column.aggregate_function;
	if (!rawConfig) return null;

	var aggConfig = _eup_parse_agg_config(rawConfig);
	var aggFn = aggConfig.fn;

	if (column.disable_total || aggFn === 'none') return null;

	var fn = frappe.EUP_REPORT_AGG.functions[aggFn];
	if (!fn) return null;

	var fieldname = column.fieldname || column.id;

	var cacheKey = (fieldname || '') + '::' + aggFn +
		'::' + (aggConfig.condition_col || '') + '::' + (aggConfig.condition || '');

	// ✅ CHẶN GỌI LẦN 2 (KỂ CẢ = 0)
	if (Object.prototype.hasOwnProperty.call(frappe.EUP_REPORT_AGG._aggCache, cacheKey)) {
		return frappe.EUP_REPORT_AGG._aggCache[cacheKey];
	}

	var result = null;

	if (aggFn === 'sumif' || aggFn === 'countif' || aggFn === 'averageif') {
		var data = _eup_get_filtered_data();
		if (!data) data = _eup_get_raw_data();

		if (data && data.length) {
			result = fn(data, fieldname, aggConfig);
		}

		// ✅ LUÔN TRẢ VỀ 0 NẾU KHÔNG CÓ KẾT QUẢ
		if (result === null || result === undefined) {
			result = 0;
		}

	} else {
		if (!values || !values.length) return null;
		result = fn(values);
	}

	// ✅ CACHE LUÔN (KỂ CẢ 0)
	frappe.EUP_REPORT_AGG._aggCache[cacheKey] = result;

	return result;
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
// 4b. DEFERRED PATCHING ENGINE
//     QueryReport class chi ton tai sau khi report.bundle.js load
//     (lazy-loaded). Cac monkey-patch o duoi can doi cho den khi
//     class do co san, neu khong se bi skip am tham.
// ============================================================
frappe.EUP_REPORT_AGG._QR_patched = false;

frappe.EUP_REPORT_AGG._patchQueryReport = function() {
	// Tranh pat nhieu lan
	if (frappe.EUP_REPORT_AGG._QR_patched) return true;
	if (!frappe.views || !frappe.views.QueryReport) {
		return false;
	}

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
					var res = fn(data, col.id, ac);
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
	// 7d. BIND TOTAL ROW + RENDER HOOKS
	// ============================================================
	// Pat vao render_datatable de apply total position + header groups
	var _orig_render = frappe.views.QueryReport.prototype.render_datatable;
	if (_orig_render) {
		frappe.views.QueryReport.prototype.render_datatable = function() {
			if (this.columns && this.report_name) {
				frappe.EUP_REPORT_AGG.applySettingsToColumns(this.columns, this.report_name, this.report_settings);
			};

			var hadDatatableBefore = !!this.datatable;
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

				if (this.datatable && !this.datatable._eup_refresh_patched) {
					var dt0 = this.datatable;
					var origDtRefresh = dt0.refresh;
					if (typeof origDtRefresh === 'function') {
						dt0.refresh = function() {
							var r = origDtRefresh.apply(this, arguments);
							var dtSelf = this;
							setTimeout(function() {
								frappe.EUP_REPORT_AGG._teardownHeaderGroupRow(dtSelf);
								frappe.EUP_REPORT_AGG.applyTotalRowPosition(dtSelf);
								frappe.EUP_REPORT_AGG.applyHeaderGroups(dtSelf);
							}, 300);
							return r;
						};
						dt0._eup_refresh_patched = true;
					}
				}

				if (!hadDatatableBefore) {
					setTimeout(function(dt) {
						frappe.EUP_REPORT_AGG.applyTotalRowPosition(dt);
						frappe.EUP_REPORT_AGG.applyHeaderGroups(dt);
					}, 300, this.datatable);
				}
			}
			return result;
		};
	}

	// Report Builder
	var _orig_rv_setup = frappe.views.ReportView.prototype.setup_datatable;
	if (_orig_rv_setup) {
		frappe.views.ReportView.prototype.setup_datatable = function(values) {
			var hadDatatableBefore = !!this.datatable;
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

				if (this.datatable && !this.datatable._eup_refresh_patched) {
					var dt1 = this.datatable;
					var origDtRefresh2 = dt1.refresh;
					if (typeof origDtRefresh2 === 'function') {
						dt1.refresh = function() {
							var r = origDtRefresh2.apply(this, arguments);
							var dtSelf = this;
							setTimeout(function() {
								frappe.EUP_REPORT_AGG._teardownHeaderGroupRow(dtSelf);
								frappe.EUP_REPORT_AGG.applyTotalRowPosition(dtSelf);
								frappe.EUP_REPORT_AGG.applyHeaderGroups(dtSelf);
							}, 300);
							return r;
						};
						dt1._eup_refresh_patched = true;
					}
				}

				if (!hadDatatableBefore) {
					setTimeout(function(dt) {
						frappe.EUP_REPORT_AGG.applyTotalRowPosition(dt);
						frappe.EUP_REPORT_AGG.applyHeaderGroups(dt);
					}, 300, this.datatable);
				}
			}
			return result;
		};
	}

	frappe.EUP_REPORT_AGG._QR_patched = true;
	return true;
};

// Retry patching: setInterval lien tuc de dam bao bat kip khi QueryReport load
// (lazy bundle). Khi da patch thanh cong, clear interval.
if (!frappe.EUP_REPORT_AGG._patchQueryReport()) {
	frappe.EUP_REPORT_AGG._patchInterval = setInterval(function() {
		if (frappe.EUP_REPORT_AGG._patchQueryReport()) {
			clearInterval(frappe.EUP_REPORT_AGG._patchInterval);
		}
	}, 10);
}
// Cung retry trong frappe:init (de phong)
$(document).on('frappe:init', function() {
	if (!frappe.EUP_REPORT_AGG._QR_patched) {
		frappe.EUP_REPORT_AGG._patchQueryReport();
	}
});

// ============================================================
// 7b. PATCH RENDER DATATABLE — set content = "" cho cot "none"
// ============================================================
function _eup_patch_body_renderer(datatable) {
	if (!datatable || !datatable.bodyRenderer || datatable._eup_br_patched) return;
	var br = datatable.bodyRenderer;
	var origGetTotalRow = br.getTotalRow;
	if (!origGetTotalRow) return;

	br.getTotalRow = function() {

		frappe.EUP_REPORT_AGG._aggCache = {};
		frappe.EUP_REPORT_AGG._aggCacheActive = true;
		var result;
		try {
			result = origGetTotalRow.apply(this, arguments);
		} finally {
			frappe.EUP_REPORT_AGG._aggCacheActive = false;
		}
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
}


// ============================================================
// 7b-2. PATCH THU: loc phan tu null/undefined khoi getColumns()
// ============================================================

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
// 7b. HEADER STYLES — màu nền & màu chữ cho header
// ============================================================
frappe.EUP_REPORT_AGG._headerStyles = frappe.EUP_REPORT_AGG._headerStyles || {};

/**
 * Cấu hình header_style:
 *   header_style: { bgColor: '#...', textColor: '#...' }     — cho TOÀN BỘ header
 *   header_styles: [                                          — cho RIÊNG từng header group
 *       { from: 'col_a', to: 'col_c', bgColor: '#...', textColor: '#...' },
 *       { from: 'col_d', to: 'col_f', bgColor: '#...', textColor: '#...' }
 *   ]
 *
 * Lưu ý: header_styles dùng chung field `from`/`to` với header_groups.
 * Nếu header_styles[i] không có from/to, nó sẽ ghép với header_groups[i] cùng index.
 */

// Inject dynamic style tag cho header colors
frappe.EUP_REPORT_AGG._injectHeaderColorStyle = function(reportName, styleConfig, groupStyles, headerGroups) {
    var safeName = reportName.replace(/[^a-zA-Z0-9_-]/g, '_');
    var styleId = 'eup-header-color-style-' + safeName;
    var existing = document.getElementById(styleId);
    if (existing) existing.remove();

    var rules = [];

    // --- Style TOÀN BỘ header cells ---
    if (styleConfig) {
        if (styleConfig.bgColor) {
            rules.push(
                '.eup-header-colored-' + safeName + ' .dt-cell--header .dt-cell__content { background-color: ' + styleConfig.bgColor + ' !important; }',
                '.eup-header-colored-' + safeName + ' .eup-header-group-cell { background-color: ' + styleConfig.bgColor + ' !important; }'
            );
        }
        if (styleConfig.textColor) {
            rules.push(
                '.eup-header-colored-' + safeName + ' .dt-cell--header .dt-cell__content { color: ' + styleConfig.textColor + ' !important; }',
                '.eup-header-colored-' + safeName + ' .eup-header-group-cell { color: ' + styleConfig.textColor + ' !important; }'
            );
        }
    }

    if (groupStyles && groupStyles.length && headerGroups && headerGroups.length) {
        groupStyles.forEach(function(gs, idx) {
            if (!gs.bgColor && !gs.textColor) return;
            var gIdx = _eup_resolve_group_index(gs, idx, headerGroups);
            if (gIdx < 0) return;
            var bgRule = gs.bgColor ? ('background-color: ' + gs.bgColor + ' !important;') : '';
            var fgRule = gs.textColor ? ('color: ' + gs.textColor + ' !important;') : '';
            // Selector theo thuoc tinh: khong phu thuoc buoc JS add class nao ca
            var attrSel = '.eup-header-colored-' + safeName + ' .eup-header-group-cell[data-eup-group-idx="' + gIdx + '"]';
            rules.push(attrSel + ' { ' + bgRule + ' ' + fgRule + ' }');
            var cls = 'eup-hdr-custom-' + safeName + '-' + idx;
            rules.push('.' + cls + ' { ' + bgRule + ' ' + fgRule + ' }');
        });
    }

    if (rules.length) {
        var style = document.createElement('style');
        style.id = styleId;
        style.textContent = rules.join('\n');
        document.head.appendChild(style);
    }
};

// Áp dụng class màu riêng cho từng header group cell (goi sau khi group cells da tao)
// FIXED: tach rieng de co the goi sau _buildHeaderGroupRow thay vi chi goi truoc
frappe.EUP_REPORT_AGG._applyGroupColorStyles = function(datatable, reportName) {
	if (!datatable || !datatable.wrapper || !reportName) return;
	var safeName = reportName.replace(/[^a-zA-Z0-9_-]/g, '_');
	var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
	if (!repConf || !repConf.header_styles || !repConf.header_styles.length) return;
	
	// FIXED: Áp dụng màu cho cả group title cells và individual header cells (bang inline style)
	var headerGroups = repConf.header_groups || null;
	var columns = datatable.datamanager ? datatable.datamanager.getColumns() : null;
	
	// 1. Tô màu group title cells (merge cells) — FIXED: tra theo data-eup-group-idx
	// Chi ap dung khi report co header_groups VA hang merge-title da duoc dung.

	var state = datatable._eup_header_group_state;
	if (state && state.row && headerGroups && headerGroups.length) {
		repConf.header_styles.forEach(function(gs, idx) {
			if (!gs.bgColor && !gs.textColor) return;
			var gIdx = _eup_resolve_group_index(gs, idx, headerGroups);
			if (gIdx < 0) return;
			var targetCell = state.row.querySelector('.eup-header-group-cell[data-eup-group-idx="' + gIdx + '"]');
			if (targetCell) {
				var cls2 = 'eup-hdr-custom-' + safeName + '-' + idx;
				targetCell.classList.add(cls2);
			}
		});
	}

	// 2. Tô màu CÁC HEADER CELL RIÊNG LẺ (tung cot) — set inline style truc tiep
	if (columns && columns.length) {
		var colIndexMap = {};
		for (var ci = 0; ci < columns.length; ci++) {
			if (columns[ci] && columns[ci].id) {
				colIndexMap[columns[ci].id] = ci;
			}
		}

		var headerRowEl = datatable.wrapper.querySelector('.dt-header .dt-row-header');

		// Reset màu cũ trước khi áp lại — tránh màu dính khi đổi config
		if (headerRowEl) {
			headerRowEl.querySelectorAll('[data-col-index] .dt-cell__content').forEach(function(el) {
				el.style.removeProperty('background-color');
				el.style.removeProperty('color');
			});
		}

		if (headerRowEl) {
			repConf.header_styles.forEach(function(gs, idx) {
				if (!gs || (!gs.bgColor && !gs.textColor)) return;

				var fromField = gs.from;
				var toField = gs.to || gs.from;

				// Style entry khong khai bao from rieng -> ghep theo vi tri voi
				// header_groups[idx] (backward-compat voi cau hinh cu).
				if (!fromField && headerGroups && headerGroups[idx]) {
					fromField = headerGroups[idx].from;
					toField = headerGroups[idx].to || fromField;
				}
				if (!fromField) return;

				var fromIdx = colIndexMap[fromField];
				var toIdx = colIndexMap[toField];
				if (fromIdx === undefined) return;
				if (toIdx === undefined) toIdx = fromIdx;
				if (fromIdx > toIdx) { var tmp = fromIdx; fromIdx = toIdx; toIdx = tmp; }

				for (var ci2 = fromIdx; ci2 <= toIdx; ci2++) {
					var cellEl = headerRowEl.querySelector('[data-col-index="' + ci2 + '"]');
					if (!cellEl) continue;
					var contentEl = cellEl.classList.contains('dt-cell__content')
						? cellEl : cellEl.querySelector('.dt-cell__content');
					if (!contentEl) continue;
					if (gs.bgColor) contentEl.style.setProperty('background-color', gs.bgColor, 'important');
					if (gs.textColor) contentEl.style.setProperty('color', gs.textColor, 'important');
				}
			});
		}
	}
};

// Áp dụng class màu cho wrapper
frappe.EUP_REPORT_AGG._applyHeaderColorClass = function(datatable, reportName) {
    if (!datatable || !datatable.wrapper) return;
    var safeName = reportName.replace(/[^a-zA-Z0-9_-]/g, '_');
    var wrapper = datatable.wrapper;
    var cls = 'eup-header-colored-' + safeName;

    // Xóa class cũ (nếu có)
    var allWrappers = document.querySelectorAll('[class*="eup-header-colored-' + safeName + '"]');
    allWrappers.forEach(function(el) {
        el.classList.remove(cls);
    });

    // Kiểm tra xem có style nào cần apply không
    var hasGlobalStyle = false;
    var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
    if (repConf) {
        if (repConf.header_style) hasGlobalStyle = true;
        if (repConf.header_styles && repConf.header_styles.length) hasGlobalStyle = true;
    }

    if (hasGlobalStyle) {
        wrapper.classList.add(cls);
        // Apply cho cả header group cells
        setTimeout(function() {
            var headerCells = wrapper.querySelectorAll('.eup-header-group-cell');
            headerCells.forEach(function(cell) {
                cell.style.backgroundColor = '';
                cell.style.color = '';
            });
        }, 50);
    }
};

// ============================================================
// 7c. HEADER GROUPS — merge cell kieu Excel (multi-level header)
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

    // === LUÔN LUÔN RESET TRƯỚC KHI BUILD (kể cả đang build) ===
    this._teardownHeaderGroupRow(datatable);

    var reportName = '';
    if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
    else if (frappe.query_report) reportName = frappe.query_report.report_name;
    if (!reportName) return;

    var groups = frappe.EUP_REPORT_AGG._headerGroups[reportName];
    var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
    if ((!groups || !groups.length) && repConf) {
        if (repConf.header_groups) {
            frappe.EUP_REPORT_AGG._headerGroups[reportName] = repConf.header_groups;
            groups = repConf.header_groups;
        }
    }

    // ---- HEADER STYLES: inject CSS cho mau nen & mau chu ----
    var headerStyle = repConf ? repConf.header_style : null;
    var headerStyles = repConf ? repConf.header_styles : null;
    var mergedGroupStyles = headerStyles;

    // FIXED: truyen them `groups` (header_groups da resolve) de _injectHeaderColorStyle
    // co the to mau merge-cell (group title) THANG bang CSS attribute-selector
    // [data-eup-group-idx], khong con phu thuoc buoc JS add class rieng chay sau.
    frappe.EUP_REPORT_AGG._injectHeaderColorStyle(reportName, headerStyle, mergedGroupStyles, groups);

    // Doc config bold_header
    var boldHeader = repConf && repConf.bold_header ? true : false;
    frappe.EUP_REPORT_AGG._toggleBoldHeaderUI(reportName, boldHeader);

    // Apply class mau cho wrapper
    frappe.EUP_REPORT_AGG._applyHeaderColorClass(datatable, reportName);

    if (headerStyles && headerStyles.length) {
        frappe.EUP_REPORT_AGG._applyGroupColorStyles(datatable, reportName);
    }

    if (!groups || !groups.length) return;

    // Danh dau dang build
    datatable._eup_building_header = true;

    // Debounce build để tránh gọi quá nhiều
    if (datatable._eup_header_groups_timeout) {
        clearTimeout(datatable._eup_header_groups_timeout);
    }
    datatable._eup_header_groups_timeout = setTimeout(function() {
        datatable._eup_header_groups_timeout = null;
        if (datatable._eup_building_header) {
            frappe.EUP_REPORT_AGG._buildHeaderGroupRow(datatable, reportName, groups);
        }
    }, 200);
};

frappe.EUP_REPORT_AGG._teardownHeaderGroupRow = function(datatable) {
    if (!datatable) return;
    try {
        var wrapper = datatable.wrapper;
        if (wrapper) {
            var reportName = '';
            if (datatable._eup_report_instance) reportName = datatable._eup_report_instance.report_name;
            else if (frappe.query_report) reportName = frappe.query_report.report_name;
            if (reportName) {
                var safeName = reportName.replace(/[^a-zA-Z0-9_-]/g, '_');
                var prefix = 'eup-hdr-individual-color-' + safeName;
                var allStyles = document.querySelectorAll('style[id^="' + prefix + '"]');
                allStyles.forEach(function(st) { st.remove(); });
            }
        }
    } catch(e) {}

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

    // === QUAN TRỌNG: Reset cờ build ===
    datatable._eup_building_header = false;
    // Hủy timeout nếu còn
    if (datatable._eup_header_groups_timeout) {
        clearTimeout(datatable._eup_header_groups_timeout);
        datatable._eup_header_groups_timeout = null;
    }
};

// ============================================================
// HÀM DỰNG HEADER GROUP — CÓ HỖ TRỢ BOLD HEADER
// ============================================================
frappe.EUP_REPORT_AGG._buildHeaderGroupRow = function(datatable, reportName, groups) {
    if (!datatable || !datatable.wrapper) return;

    // Nếu cờ build đã bị reset (bởi một lần teardown khác) thì không build
    if (!datatable._eup_building_header) {
        return;
    }

    var myBuildId = (datatable._eup_header_build_id = (datatable._eup_header_build_id || 0) + 1);

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

    function makeAbsCell(left, width, height, text, borderStyle, isOverlayMerge, bgColor, groupIdx) {
        var cell = document.createElement('div');
        cell.className = 'eup-header-group-cell';

        if (typeof groupIdx === 'number' && groupIdx >= 0) {
            cell.setAttribute('data-eup-group-idx', String(groupIdx));
        } else {
            cell.setAttribute('data-eup-filler', '1');
        }
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
                    borderStyle, false, null, gIdx
                ));
                i = j;
            } else {
                var rect = headerCells[i].getBoundingClientRect();
                var left = rect.left - headerRowRect.left;
                var width = rect.width;
                var contentEl = headerCells[i].querySelector('.dt-cell__content');
                var label = contentEl ? contentEl.textContent.trim() : '';
                var fullHeight = rowHeight + headerRowRect.height;
                var ciAttrX = headerCells[i].getAttribute('data-col-index');
                var ciX = ciAttrX !== null ? parseInt(ciAttrX, 10) : NaN;
                var fieldIdX = (!isNaN(ciX) && columns[ciX]) ? columns[ciX].id : '';
                var customStyle = _eup_resolveFillerHeaderStyle(reportName, fieldIdX, columns);

                var bgColor = (customStyle && customStyle.bgColor) ? customStyle.bgColor : cellStyles[i].bg;
                if (!bgColor || bgColor === 'rgba(0, 0, 0, 0)') bgColor = '#fff';
                var fgColor = customStyle ? customStyle.textColor : null;

                var borderStyle = {
                    top: cellStyles[i].top,
                    right: cellStyles[i].right,
                    bottom: cellStyles[i].bottom,
                    left: cellStyles[i].left
                };
                var fillerCell = makeAbsCell(
                    left, width, fullHeight, frappe._(label),
                    borderStyle, true, bgColor
                    /* khong truyen groupIdx: day la cell filler, khong thuoc nhom nao */
                );
                if (fgColor) fillerCell.style.color = fgColor;
                if (fieldIdX) fillerCell.setAttribute('data-eup-field', fieldIdX);
                state.row.appendChild(fillerCell);
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
        // FIXED: neu da co 1 lan build MOI hon bat dau (build-id doi khac), day la
        // closure "mo coi" cua lan build CU -> khong schedule gi nua, tranh no chay
        // sync() sau khi da bi teardown.
        if (datatable._eup_header_build_id !== myBuildId) return;
        if (state.isDragging) return;
        if (syncScheduled) return;
        syncScheduled = true;
        requestAnimationFrame(function () {
            syncScheduled = false;
            sync();
        });
    }

    function sync() {
        if (datatable._eup_header_build_id !== myBuildId) return;

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

        frappe.EUP_REPORT_AGG._applyGroupColorStyles(datatable, reportName);
        // Chi reset co dung chung neu MINH van la lan build hien hanh (da kiem tra o dau ham)
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

// (Phan 7d va Report Builder da duoc chuyen vao _patchQueryReport() o tren)

// Capture config tu frappe.query_reports - chay trong frappe:init
$(document).on('frappe:init', function() {
	frappe.EUP_REPORT_AGG._totalRowPosition = frappe.EUP_REPORT_AGG._totalRowPosition || {};
	frappe.EUP_REPORT_AGG._headerGroups = frappe.EUP_REPORT_AGG._headerGroups || {};
	frappe.EUP_REPORT_AGG._headerStyles = frappe.EUP_REPORT_AGG._headerStyles || {};
	for (var k in frappe.query_reports) {
		if (frappe.query_reports.hasOwnProperty(k)) {
			var obj = frappe.query_reports[k];
			if (obj.total_row_position) frappe.EUP_REPORT_AGG._totalRowPosition[k] = obj.total_row_position;
			if (obj.header_groups) frappe.EUP_REPORT_AGG._headerGroups[k] = obj.header_groups;
			if (obj.header_style) frappe.EUP_REPORT_AGG._headerStyles[k] = obj.header_style;
			if (obj.header_styles) frappe.EUP_REPORT_AGG._headerStyles[k] = obj.header_styles;
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
        function buildExcelWorkbookWithGroups(reportName, data, columns, headerGroups, boldHeader, headerStyle, headerStyles) {
        var wb = XLSX.utils.book_new();

        // Doc headerStyle va headerStyles tu report config
        var repConf = frappe.query_reports ? frappe.query_reports[reportName] : null;
        if (!headerStyle && repConf) headerStyle = repConf.header_style || null;
        if (!headerStyles && repConf) headerStyles = repConf.header_styles || null;

        // Dong header chinh (label cua cac cot)
        var headerRow = columns.map(function(col) {
            return col.label || col.fieldname || '';
        });
        var rows = [headerRow];

        // Dong du lieu
        data.forEach(function(row) {
            var rowData = columns.map(function(col) {
                var val = row[col.fieldname];
                return (val !== undefined && val !== null) ? val : '';
            });
            rows.push(rowData);
        });

        var merge = [];
        var headerStyleRules = []; // luu thong tin fill/font cho tung cell

        // colIndexMap can duoc dung o ca 2 truong hop co/khong co header_groups
        var colIndexMap = {};
        columns.forEach(function(col, idx) {
            colIndexMap[col.fieldname] = idx;
        });

        // Neu co header_groups, chen them hang nhom phia tren
        if (headerGroups && headerGroups.length) {
            var groupRow = new Array(columns.length).fill('');

            headerGroups.forEach(function(grp, grpIdx) {
                var fromIdx = colIndexMap[grp.from];
                var toIdx = colIndexMap[grp.to];
                if (fromIdx === undefined || toIdx === undefined) return;
                if (fromIdx > toIdx) { var tmp = fromIdx; fromIdx = toIdx; toIdx = tmp; }
                groupRow[fromIdx] = grp.title || '';
                merge.push({ s: { r: 0, c: fromIdx }, e: { r: 0, c: toIdx } });

                var matchedStyle = null;
                if (headerStyles && headerStyles.length) {
                    for (var hsi = 0; hsi < headerStyles.length; hsi++) {
                        var hs = headerStyles[hsi];
                        if (hs && hs.from && hs.from === grp.from && (!hs.to || hs.to === grp.to)) {
                            matchedStyle = hs;
                            break;
                        }
                    }
                    if (!matchedStyle && headerStyles[grpIdx] && !headerStyles[grpIdx].from) {
                        matchedStyle = headerStyles[grpIdx];
                    }
                }
                if (matchedStyle) {
                    headerStyleRules.push({
                        row: 0, col: fromIdx,
                        bgColor: matchedStyle.bgColor || null,
                        textColor: matchedStyle.textColor || null
                    });
                }
            });

            // Chen hang nhom vao dau
            rows.unshift(groupRow);
        }

        if (headerStyles && headerStyles.length) {
            var columnHeaderRowIdx = (headerGroups && headerGroups.length) ? 1 : 0;
            headerStyles.forEach(function(hs, idx) {
                if (!hs || (!hs.bgColor && !hs.textColor)) return;

                var fromField = hs.from;
                var toField = hs.to || hs.from;

                if (!fromField && headerGroups && headerGroups[idx]) {
                    fromField = headerGroups[idx].from;
                    toField = headerGroups[idx].to || fromField;
                }
                if (!fromField) return;

                var fromIdx2 = colIndexMap[fromField];
                var toIdx2 = colIndexMap[toField];
                if (fromIdx2 === undefined) return;
                if (toIdx2 === undefined) toIdx2 = fromIdx2;
                if (fromIdx2 > toIdx2) { var tmp2 = fromIdx2; fromIdx2 = toIdx2; toIdx2 = tmp2; }

                for (var c2 = fromIdx2; c2 <= toIdx2; c2++) {
                    headerStyleRules.push({
                        row: columnHeaderRowIdx, col: c2,
                        bgColor: hs.bgColor || null,
                        textColor: hs.textColor || null
                    });
                }
            });
        }

        // Neu co header_style toan bo, apply cho tat ca header rows
        if (headerStyle) {
            var numHeaderRows = (headerGroups && headerGroups.length) ? 2 : 1;
            for (var R = 0; R < numHeaderRows; R++) {
                for (var C = 0; C < columns.length; C++) {
                    headerStyleRules.push({
                        row: R, col: C,
                        bgColor: headerStyle.bgColor || null,
                        textColor: headerStyle.textColor || null
                    });
                }
            }
        }

        var ws = XLSX.utils.aoa_to_sheet(rows);
        if (merge.length) ws['!merges'] = merge;

        // Tu dong do rong cot
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

        // Ap dung bold cho tat ca header (ca group va cot) neu boldHeader = true
        if (boldHeader) {
            var numHeaderRows = (headerGroups && headerGroups.length) ? 2 : 1;
            var range = XLSX.utils.decode_range(ws['!ref']);
            for (var R = range.s.r; R < range.s.r + numHeaderRows; R++) {
                for (var C = range.s.c; C <= range.e.c; C++) {
                    var addr = XLSX.utils.encode_cell({ r: R, c: C });
                    if (!ws[addr]) ws[addr] = { t: 's', v: '' };
                    if (!ws[addr].s) ws[addr].s = {};
                    if (!ws[addr].s.font) ws[addr].s.font = {};
                    ws[addr].s.font.bold = true;
                }
            }
        }

        // Ap dung mau nen & mau chu cho header cells
        if (headerStyleRules.length) {
            var range = XLSX.utils.decode_range(ws['!ref']);
            for (var ri = 0; ri < headerStyleRules.length; ri++) {
                var rule = headerStyleRules[ri];
                if (rule.row > range.e.r || rule.col > range.e.c) continue;
                var addr = XLSX.utils.encode_cell({ r: rule.row, c: rule.col });
                if (!ws[addr]) ws[addr] = { t: 's', v: '' };
                if (!ws[addr].s) ws[addr].s = {};
                var s = ws[addr].s;
                if (rule.bgColor) {
                    var rgb = rule.bgColor.replace('#', '');
                    if (!s.fill) s.fill = {};
                    s.fill.fgColor = { rgb: rgb };
                    s.fill.patternType = 'solid';
                }
                if (rule.textColor) {
                    var rgb2 = rule.textColor.replace('#', '');
                    if (!s.font) s.font = {};
                    s.font.color = { rgb: rgb2 };
                }
            }
        }

        XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
        return wb;
    }

    // Hàm export chính
    function exportExcelWithHeaderGroups(reportName, data, columns, headerGroups, boldHeader, headerStyle, headerStyles) {
        if (!data || !data.length) {
            frappe.msgprint(__('Không có dữ liệu để xuất.'));
            return;
        }

        loadXLSX(function() {
            try {
                var wb = buildExcelWorkbookWithGroups(reportName, data, columns, headerGroups, boldHeader, headerStyle, headerStyles);
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

            var headerStyle = repConf ? repConf.header_style : null;
            var headerStyles = repConf ? repConf.header_styles : null;

            if ((headerGroups && headerGroups.length) || boldHeader || headerStyle || (headerStyles && headerStyles.length)) {
                exportExcelWithHeaderGroups(reportName, data, columns, headerGroups, boldHeader, headerStyle, headerStyles);
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

            var headerStyle = repConf ? repConf.header_style : null;
            var headerStyles = repConf ? repConf.header_styles : null;

            if ((headerGroups && headerGroups.length) || boldHeader || headerStyle || (headerStyles && headerStyles.length)) {
                exportExcelWithHeaderGroups(reportName, data, columns, headerGroups, boldHeader, headerStyle, headerStyles);
                return;
            }
            origRVExport.apply(this, arguments);
        };
    }
})();