// alumglass/public/js/excel_io.js
// === Excel IO — thư viện dùng chung cho dialog ===
// Thiết kế: docs/design/excel-io-shared-library.md
//
// Vì sao có file này: luồng "tải file mẫu -> chọn file -> kiểm tra -> đổ vào bảng" từng bị chép tay
// ở từng dialog rồi trôi khác nhau (bản Purchase Invoice khoá nút khi đang chạy, bản ĐNTT Domestic
// Shipment thì không; bản này phân biệt lỗi mạng với lỗi file, bản kia quy hết cho file người dùng).
// Gom về một chỗ thì dialog mới chỉ còn khai `section` + `table` + `doctype`, không phải viết lại
// FormData/CSRF/khoá nút/hiển thị lỗi — và cũng không phải liệt kê lại các cột, vì cột được TỰ SUY
// RA từ đúng field Table đã khai trên dialog.
//
// Dùng tối thiểu (không cần khai `columns` — thư viện tự đọc field Table của dialog):
//
//   alumglass.excel_io.attach(dialog, {
//       section: "upload_section",   // fieldname ô HTML trong dialog để vẽ thanh công cụ
//       table:   "items",            // fieldname bảng Table để đổ dữ liệu vào
//       doctype: "Purchase Receipt", // để kiểm quyền ở server
//   });
//
// Cột tự suy ra = các field hiển thị trong bảng (in_list_view), lấy label/fieldtype/options/độ
// rộng đúng như đã khai trên field Table của dialog. Vào file: MẶC ĐỊNH KHÔNG cột nào bắt buộc —
// dòng có 4 cột nhưng chỉ 3 cột có dữ liệu vẫn nạp bình thường (đọc đủ 3, cột thiếu để trống);
// muốn ép buộc cột nào đó phải có dữ liệu thì khai `columns` tường minh kèm `required: 1`.
//
// Chỉ cần khai `columns` khi thật sự cần khác mặc định — ví dụ chỉ muốn 1 trong nhiều cột của
// bảng, muốn đổi nhãn cột trong file, thêm cột chỉ-để-nhập (không có trên bảng), hay bắt buộc
// một cột cụ thể:
//
//   alumglass.excel_io.attach(dialog, {
//       section: "upload_section",
//       table:   "items",
//       doctype: "Purchase Receipt",
//       columns: [                   // override — không khai thì tự lấy từ field Table
//           { fieldname: "purchase_receipt", label: __("Purchase Receipt"),
//             fieldtype: "Link", options: "Purchase Receipt", width: 24, required: 1 },
//       ],
//       key: "purchase_receipt",     // cột khoá — dò trùng, báo "trùng với dòng N"
//       validator: "alumglass.alumglass.doctype.overrides.purchase_invoice.validate_receipt_rows",
//       extra_args: (dialog) => ({ company: dialog.fields_dict.company?.value || "" }),
//       map_row: (row) => ({ purchase_receipt: row.purchase_receipt }),
//       mode: "replace",             // "replace" (mặc định) | "append"
//       export: { enabled: true, filename: "purchase_receipt" },
//       labels: { template: "...", choose: "...", export: "...", guide: "..." },
//       on_loaded: (data, dialog) => {},
//   });
//
// Xuất lẻ từng mảnh cho nơi cần ghép riêng: build_toolbar_html, fill_grid, collect_grid_rows,
// render_result, download_template, export_rows, derive_columns_from_table.

frappe.provide("alumglass.excel_io");

(function (ns) {
	"use strict";

	var METHODS = {
		template: "alumglass.excel_io.download_template",
		upload: "alumglass.excel_io.upload",
		export: "alumglass.excel_io.export_xlsx",
	};

	// Phải khớp MAX_UPLOAD_BYTES bên eup_core/excel_io.py — chặn ở client để người dùng biết ngay
	// file quá lớn, không phải chờ tải lên xong mới nhận lỗi.
	var MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
	var XLSX_NAME = /\.xlsx$/i;

	// Kiểu field KHÔNG đưa vào file Excel khi tự suy cột — không phải dữ liệu để người dùng gõ tay
	var SKIP_FIELDTYPES = {
		"Section Break": 1, "Column Break": 1, "Tab Break": 1, "HTML": 1, "Button": 1,
		"Heading": 1, "Table": 1, "Table MultiSelect": 1, "Image": 1, "Attach": 1,
		"Attach Image": 1, "Signature": 1, "Geolocation": 1, "Fold": 1,
	};

	// Nhãn mặc định — KHÔNG gọi __() ở đây vì file này chạy lúc load trang, có thể chưa có __()
	var DEFAULT_LABELS = {
		template: "Tải file mẫu",
		choose: "Chọn file",
		export: "Xuất Excel",
		no_file: "Chưa chọn file",
	};

	function _t(config, key, fallback) {
		var labels = (config && config.labels) || {};
		return __(labels[key] || DEFAULT_LABELS[key] || fallback || "");
	}

	// Mọi nội dung lấy từ file hoặc từ server đều phải escape trước khi nhét vào DOM
	function _esc(text) {
		if (text === null || text === undefined) return "";
		return frappe.utils.escape_html(String(text));
	}

	function _mode(config) {
		return (config && config.mode) === "append" ? "append" : "replace";
	}

	function _pick(row, columns) {
		var out = {};
		(columns || []).forEach(function (col) {
			if (col && col.fieldname) out[col.fieldname] = row ? row[col.fieldname] : "";
		});
		return out;
	}

	// ---- Tự suy cột từ field Table đã khai trên dialog ----
	// Lấy đúng danh sách field mà dialog đã khai cho bảng con (ctrl.df.fields) — không hỏi thêm
	// doctype ở server, vì field Table trên dialog có thể có bộ field riêng khác doctype gốc.
	// Chỉ lấy field hiển thị trong bảng (in_list_view) và bỏ qua field không phải dữ liệu nhập tay.
	// MẶC ĐỊNH mọi cột không bắt buộc (required: 0): mục tiêu là "có dữ liệu cột nào thì nạp cột
	// đó", không phải bắt người dùng điền đủ mọi cột trong file mới nạp được dòng.
	function _derive_columns(dialog, table) {
		var ctrl = dialog && dialog.fields_dict ? dialog.fields_dict[table] : null;
		if (!ctrl) return [];

		var fields = (ctrl.df && ctrl.df.fields) || (ctrl.grid && ctrl.grid.df && ctrl.grid.df.fields) || [];

		return fields
			.filter(function (f) {
				return f && f.fieldname && !SKIP_FIELDTYPES[f.fieldtype] && f.in_list_view && !f.hidden;
			})
			.map(function (f) {
				return {
					fieldname: f.fieldname,
					label: f.label || f.fieldname,
					fieldtype: f.fieldtype || "Data",
					options: f.options || "",
					required: 0, // mặc định KHÔNG bắt buộc — khai `columns` tường minh nếu cần ép buộc
					width: f.columns ? f.columns * 6 : 16,
				};
			});
	}

	// Lấy câu lỗi người-đọc-được từ response của frappe.throw(); không có thì dùng câu dự phòng
	function _server_error_message(response, fallback) {
		if (response && response._server_messages) {
			try {
				var messages = JSON.parse(response._server_messages);
				if (messages && messages.length) {
					var first = JSON.parse(messages[0]);
					if (first && first.message) return first.message;
				}
			} catch (e) {
				// Không đọc được thông báo của server — dùng câu mặc định bên dưới
			}
		}
		return fallback || __("Máy chủ chưa trả về kết quả. Vui lòng thử lại.");
	}

	function _set_busy($area, busy) {
		$area.data("excel-io-busy", !!busy);
		// Khoá cả nút lẫn ô chọn file: bấm đúp mà không khoá thì file được nạp 2 lần
		$area.find(".excel-io-template, .excel-io-choose, .excel-io-export, .excel-io-file")
			.prop("disabled", !!busy);
		$area.find(".excel-io-result").css("opacity", busy ? 0.5 : 1);
	}

	function _result_area($area) {
		var $result = $area.find(".excel-io-result");
		if (!$result.length) {
			$area.append('<div class="excel-io-result" style="max-height: 160px; overflow-y: auto;"></div>');
			$result = $area.find(".excel-io-result");
		}
		return $result;
	}

	function _show_error($area, message) {
		_result_area($area).html(
			'<div style="margin-top: 10px; padding: 10px; background: #fff3f3; border: 1px solid #f5c6cb; border-radius: 4px; color: #b71c1c;">' +
			_esc(message) +
			'</div>'
		);
	}

	function _filename_from_response(response, fallback) {
		try {
			var header = response.headers.get("content-disposition") || "";
			var match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header);
			if (match && match[1]) return decodeURIComponent(match[1].replace(/"/g, ""));
		} catch (e) {
			// Không đọc được header (đổi tên file) — dùng tên dự phòng
		}
		return fallback;
	}

	// Tải nội dung nhị phân về máy; server trả JSON (lỗi) thì hiển thị câu đọc được thay vì tải file rác
	function _save_binary_response(response, fallback_name) {
		var content_type = (response.headers.get("content-type") || "").toLowerCase();

		if (!response.ok || content_type.indexOf("application/json") !== -1) {
			return response.text().then(function (text) {
				var parsed = null;
				try { parsed = JSON.parse(text); } catch (e) { /* không phải JSON thì dùng câu dự phòng */ }
				frappe.msgprint({
					title: __("Không tải được file"),
					message: _esc(_server_error_message(parsed, __("Máy chủ chưa trả về file. Vui lòng thử lại."))),
					indicator: "red",
				});
			});
		}

		var name = _filename_from_response(response, fallback_name);
		return response.blob().then(function (blob) {
			var url = URL.createObjectURL(blob);
			var link = document.createElement("a");
			link.href = url;
			link.download = name;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			// Thu hồi URL sau khi trình duyệt đã kịp bắt đầu tải
			setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
		});
	}

	function _post(method, form_data) {
		return fetch("/api/method/" + method, {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			body: form_data,
		});
	}

	function _guide_text(config) {
		if (config.labels && config.labels.guide) return config.labels.guide;

		var labels = (config.columns || [])
			.map(function (col) { return col.label || col.fieldname; })
			.filter(Boolean);
		var lines = [
			__("Tải file mẫu Excel ({0} cột: {1}), điền dữ liệu rồi tải lên.", [labels.length, labels.join(", ")]),
			__("Chỉ nhận file .xlsx. Hệ thống tự kiểm tra và nạp các dòng hợp lệ vào bảng; dòng nào có dữ liệu cột nào thì nạp cột đó, không cần điền đủ mọi cột. Dòng sai được báo lại kèm số dòng trong file để sửa."),
		];
		if (_mode(config) === "replace") {
			// Nói rõ ngay trên dialog: người dùng phải biết thao tác này xoá nội dung bảng đang có
			lines.push(__("Nạp file sẽ thay thế toàn bộ nội dung bảng."));
		}
		return lines.join(" ");
	}

	ns = Object.assign(ns, {
		MAX_UPLOAD_BYTES: MAX_UPLOAD_BYTES,

		// ---- Suy cột từ field Table của dialog (dùng lại được ở nơi khác nếu cần) ----
		derive_columns_from_table: _derive_columns,

		// ---- Dựng thanh công cụ (tách riêng cho nơi cần ghép vào HTML của mình) ----
		build_toolbar_html: function (config) {
			var export_button = (config.export && config.export.enabled)
				? '<button class="btn btn-xs btn-default excel-io-export" type="button">' +
					'<i class="fa fa-file-excel-o"></i> ' + _esc(_t(config, "export")) + '</button>'
				: "";

			return '' +
				'<div class="excel-io-area" style="padding: 10px 0;">' +
					'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 8px;">' +
						'<button class="btn btn-xs btn-default excel-io-template" type="button">' +
							'<i class="fa fa-download"></i> ' + _esc(_t(config, "template")) + '</button>' +
						'<button class="btn btn-xs btn-primary excel-io-choose" type="button">' +
							'<i class="fa fa-upload"></i> ' + _esc(_t(config, "choose")) + '</button>' +
						export_button +
						'<span class="excel-io-filename" style="color: #666;">' + _esc(_t(config, "no_file")) + '</span>' +
					'</div>' +
					'<div style="background: #f9f9f9; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #555;">' +
						'<strong>' + __('Hướng dẫn') + ':</strong> ' + _esc(_guide_text(config)) +
					'</div>' +
					'<input type="file" class="excel-io-file" accept=".xlsx" style="display:none;">' +
					'<div class="excel-io-result" style="max-height: 160px; overflow-y: auto;"></div>' +
				'</div>';
		},

		// ---- Gắn vào dialog: dựng thanh công cụ + nối sự kiện ----
		attach: function (dialog, config) {
			if (!dialog || !dialog.fields_dict) {
				console.error("[excel_io] attach() cần một dialog có fields_dict");
				return null;
			}
			if (!config || !config.section || !dialog.fields_dict[config.section]) {
				console.error("[excel_io] dialog chưa khai ô HTML '" + ((config && config.section) || "?") + "'");
				return null;
			}
			if (!config.table || !dialog.fields_dict[config.table]) {
				console.error("[excel_io] dialog chưa khai bảng Table '" + ((config && config.table) || "?") + "'");
				return null;
			}

			config = Object.assign({}, config);

			// Không khai `columns` -> tự suy từ field Table của dialog. Đây là điểm đơn giản hoá
			// chính: dialog thường không cần khai gì thêm ngoài section/table/doctype.
			if (!config.columns || !config.columns.length) {
				config.columns = _derive_columns(dialog, config.table);
				if (!config.columns.length) {
					console.error(
						"[excel_io] không tự suy được cột nào từ bảng '" + config.table + "' " +
						"(không có field nào bật in_list_view). Vui lòng khai 'columns' tường minh."
					);
					return null;
				}
			}

			var $area = $(dialog.fields_dict[config.section].$wrapper);
			$area.html(ns.build_toolbar_html(config));

			$area.find(".excel-io-template").on("click", function (event) {
				event.preventDefault();
				if (!$area.data("excel-io-busy")) ns.download_template(config, dialog, $area);
			});

			$area.find(".excel-io-choose").on("click", function (event) {
				event.preventDefault();
				if ($area.data("excel-io-busy")) return;
				// Xoá giá trị cũ trước khi mở hộp chọn: chọn lại ĐÚNG file vừa sửa nội dung
				// vẫn phải kích hoạt nạp, không thì người dùng sửa file xong bấm chọn mà không có gì xảy ra
				$area.find(".excel-io-file").val("").trigger("click");
			});

			$area.find(".excel-io-export").on("click", function (event) {
				event.preventDefault();
				if (!$area.data("excel-io-busy")) ns.export_rows(config, dialog, $area);
			});

			$area.find(".excel-io-file").on("change", function () {
				var file = this.files && this.files[0];
				$(this).val("");
				if (!file || $area.data("excel-io-busy")) return;
				ns.upload_file(config, dialog, $area, file);
			});

			return {
				dialog: dialog,
				config: config,
				$area: $area,
				download_template: function () { ns.download_template(config, dialog, $area); },
				export_rows: function () { ns.export_rows(config, dialog, $area); },
				reset: function () {
					$area.find(".excel-io-filename").text(_t(config, "no_file"));
					_result_area($area).empty();
				},
			};
		},

		// ---- Nạp file ----
		upload_file: function (config, dialog, $area, file) {
			if (!XLSX_NAME.test(file.name || "")) {
				_show_error($area, __("Chỉ nhận file Excel (.xlsx). File bạn chọn là '{0}'.", [file.name || ""]));
				return;
			}
			if (file.size && file.size > MAX_UPLOAD_BYTES) {
				_show_error($area, __(
					"File có dung lượng {0} MB, vượt quá giới hạn {1} MB mỗi lần tải lên. Vui lòng chia nhỏ file rồi tải lên lại.",
					[(file.size / 1024 / 1024).toFixed(1), Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)]
				));
				return;
			}

			var form_data = new FormData();
			form_data.append("file", file);
			form_data.append("doctype", config.doctype || "");
			form_data.append("columns", JSON.stringify(config.columns || []));
			if (config.key) form_data.append("key", config.key);
			if (config.validator) form_data.append("validator", config.validator);
			if (typeof config.extra_args === "function") {
				var extra = {};
				try {
					extra = config.extra_args(dialog) || {};
				} catch (e) {
					console.error("[excel_io] extra_args lỗi:", e);
				}
				form_data.append("extra_args", JSON.stringify(extra));
			}

			$area.find(".excel-io-filename").text(file.name);
			_result_area($area).html('<div style="margin-top: 10px; color: #666;">' + __('Đang đọc file...') + '</div>');
			_set_busy($area, true);

			_post(METHODS.upload, form_data)
				.then(function (response) {
					return response.json().catch(function () {
						// Server không trả JSON (sập, gateway, hết phiên) — KHÔNG quy lỗi cho file người dùng
						throw { __excel_io_network: true };
					});
				})
				.then(function (r) {
					if (!r || r.exc_type || !r.message) {
						_show_error($area, _server_error_message(r));
						return;
					}

					var data = r.message;
					var results = data.results || [];
					var mode = _mode(config);
					if (results.length) {
						ns.fill_grid(dialog, config.table, results, config, mode);
					}

					ns.render_result(_result_area($area), data, config);

					if (results.length) {
						var errors = (data.errors || []).length;
						frappe.show_alert({
							message: errors
								? __("Đã nạp {0} dòng, {1} dòng cần sửa", [results.length, errors])
								: __("Đã nạp {0} dòng vào bảng", [results.length]),
							indicator: errors ? "orange" : "green",
						}, 5);
					}

					if (typeof config.on_loaded === "function") {
						config.on_loaded(data, dialog);
					}
				})
				.catch(function (err) {
					if (err && err.__excel_io_network) {
						_show_error($area, __("Chưa nhận được kết quả từ máy chủ. Vui lòng thử lại, hoặc chia file nhỏ hơn nếu file quá lớn."));
						return;
					}
					// Lỗi ở bước hiển thị kết quả (không phải lỗi máy chủ, không phải lỗi file) —
					// nói đúng chỗ hỏng, không quy cho file người dùng
					console.error("[excel_io] lỗi hiển thị kết quả nạp file:", err);
					frappe.msgprint({
						title: __("Chưa hiển thị được kết quả"),
						message: __("Dữ liệu đã được máy chủ xử lý nhưng chưa hiển thị được lên bảng. Vui lòng tải lại trang rồi thử lại."),
						indicator: "red",
					});
				})
				.finally(function () {
					_set_busy($area, false);
				});
		},

		// ---- Đổ dữ liệu vào bảng của dialog ----
		fill_grid: function (dialog, table, rows, config, mode) {
			var ctrl = dialog && dialog.fields_dict ? dialog.fields_dict[table] : null;
			if (!ctrl || !ctrl.grid) {
				console.error("[excel_io] dialog chưa khai bảng Table '" + table + "'");
				return 0;
			}

			// Không khai map_row thì lấy đúng các cột đã khai (không đổ nguyên dict của server vào
			// bảng — dict có thể chứa trường không có trên bảng, Frappe bỏ qua nhưng rối khi debug).
			// Không khai cả `columns` thì trả nguyên dòng, cho nơi gọi lẻ tự quyết.
			var map_row = (config && config.map_row) || function (row) {
				var columns = (config && config.columns) || [];
				return columns.length ? _pick(row, columns) : row;
			};
			var mapped = (rows || []).map(function (row) { return map_row(row); });
			var data = (mode === "append") ? (ctrl.df.data || []).concat(mapped) : mapped;

			ctrl.df.data = data;
			ctrl.grid.df.data = data;
			ctrl.grid.refresh();
			return mapped.length;
		},

		// ---- Lấy dữ liệu đang có trên bảng để xuất ----
		collect_grid_rows: function (dialog, table) {
			var ctrl = dialog && dialog.fields_dict ? dialog.fields_dict[table] : null;
			var rows = (ctrl && ctrl.df && ctrl.df.data) || [];
			return rows.map(function (row) { return Object.assign({}, row); });
		},

		// ---- Hiển thị kết quả nạp: số dòng đã nạp + lỗi/cảnh báo kèm số dòng ----
		render_result: function ($area, data, config) {
			if (!$area || !$area.length) return;

			var results = (data && data.results) || [];
			var errors = (data && data.errors) || [];
			var warnings = (data && data.warnings) || [];
			var html = '<div style="margin-top: 10px;">';

			if (results.length) {
				html += '<div style="color: #2e7d32;">✓ ' +
					_esc(__("Đã nạp {0} dòng vào bảng.", [results.length])) + '</div>';
			} else if (errors.length) {
				html += '<div style="color: #b71c1c;">✗ ' + _esc(__("Không có dòng nào được nạp vào bảng.")) + '</div>';
			} else {
				html += '<div style="color: #b71c1c;">✗ ' +
					_esc(__("File không có dòng dữ liệu nào ở các cột đã khai báo (từ dòng 2 trở xuống).")) + '</div>';
			}

			if (!results.length && (errors.length || _mode(config) === "replace")) {
				html += '<div style="color: #555;">' + _esc(__("Bảng giữ nguyên nội dung đang có.")) + '</div>';
			}

			if (errors.length) {
				html += '<div style="margin-top: 8px; padding: 10px; background: #fff3f3; border: 1px solid #f5c6cb; border-radius: 4px;">';
				html += '<div style="color: #b71c1c;">' +
					_esc(__("{0} dòng chưa nạp được — sửa các dòng sau trong file rồi tải lên lại:", [errors.length])) + '</div>';
				html += '<ul style="margin: 5px 0 0 10px;">';
				errors.forEach(function (message) {
					html += '<li style="color: #d32f2f;">⚠ ' + _esc(message) + '</li>';
				});
				html += '</ul></div>';
			}

			if (warnings.length) {
				html += '<div style="margin-top: 8px; padding: 10px; background: #fff8e1; border: 1px solid #ffe082; border-radius: 4px;">';
				html += '<div style="color: #e65100;">' +
					_esc(__("{0} dòng cần lưu ý:", [warnings.length])) + '</div>';
				html += '<ul style="margin: 5px 0 0 10px;">';
				warnings.forEach(function (message) {
					html += '<li style="color: #e65100;">⚡ ' + _esc(message) + '</li>';
				});
				html += '</ul></div>';
			}

			html += '</div>';
			$area.html(html);
		},

		// ---- Tải file mẫu ----
		download_template: function (config, dialog, $area) {
			var form_data = new FormData();
			form_data.append("doctype", config.doctype || "");
			form_data.append("columns", JSON.stringify(config.columns || []));
			if (config.export && config.export.filename) form_data.append("filename", config.export.filename);
			if (config.title) form_data.append("title", config.title);

			_set_busy($area, true);
			_post(METHODS.template, form_data)
				.then(function (response) {
					return _save_binary_response(response, (config.doctype || "template") + "_upload_template.xlsx");
				})
				.catch(function (err) {
					console.error("[excel_io] lỗi tải file mẫu:", err);
					frappe.msgprint({
						title: __("Không tải được file"),
						message: __("Chưa nhận được kết quả từ máy chủ. Vui lòng thử lại."),
						indicator: "red",
					});
				})
				.finally(function () {
					_set_busy($area, false);
				});
		},

		// ---- Xuất dữ liệu đang có trên bảng của dialog ----
		export_rows: function (config, dialog, $area) {
			var rows = ns.collect_grid_rows(dialog, config.table);
			if (!rows.length) {
				frappe.msgprint(__("Chưa có dòng nào để xuất."));
				return;
			}

			var filename = (config.export && config.export.filename) || config.doctype || "export";
			var form_data = new FormData();
			form_data.append("doctype", config.doctype || "");
			form_data.append("columns", JSON.stringify(config.columns || []));
			form_data.append("rows", JSON.stringify(rows));
			form_data.append("filename", filename);

			_set_busy($area, true);
			_post(METHODS.export, form_data)
				.then(function (response) {
					return _save_binary_response(response, filename + ".xlsx");
				})
				.catch(function (err) {
					console.error("[excel_io] lỗi xuất Excel:", err);
					frappe.msgprint({
						title: __("Không xuất được file"),
						message: __("Chưa nhận được kết quả từ máy chủ. Vui lòng thử lại."),
						indicator: "red",
					});
				})
				.finally(function () {
					_set_busy($area, false);
				});
		},
	});
})(alumglass.excel_io);