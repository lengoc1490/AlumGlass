// Trang "Cấu hình sản phẩm" (B8/Đ1) — CHỈ ĐỌC.
//
// Một sản phẩm (AL BOM) tham chiếu tới 6 nơi cấu hình rời nhau. Trang gom
// chúng thành các khối trên một màn; mỗi khối có nút "Mở" nhảy đúng form.
//
// Nguyên tắc hiển thị:
//   · Khối lỗi ⇒ viền cam + CÂU LỖI tiếng Việt + nút "Tải lại".
//     ⛔ Không im lặng bỏ khối — im lặng = nói dối là sản phẩm không có.
//   · Mọi chuỗi động đi qua `.text()` (⛔ innerHTML) để không phơi HTML.
//   · Mã kỹ thuật chỉ hiện KÈM tên; thiếu tên mới hiện mã.

frappe.provide("frappe.al_product_config");

frappe.al_product_config.PRODUCT_DOCTYPE = "AL BOM";
frappe.al_product_config.METHOD =
	"alumglass.api.product_config.get_product_config";

// ── Hàm thuần (không chạm DOM) — có test node riêng ────────────────────
function _al_first_value(value) {
	if (Array.isArray(value)) {
		return value.length ? String(value[0]) : "";
	}
	if (value === null || value === undefined) {
		return "";
	}
	return String(value);
}

frappe.al_product_config.read_params = function (route_options) {
	const opts = route_options || {};
	let doctype = _al_first_value(opts.doctype).trim();
	const docname = (
		_al_first_value(opts.docname) || _al_first_value(opts.name)
	).trim();
	if (!doctype) {
		doctype = frappe.al_product_config.PRODUCT_DOCTYPE;
	}
	return { doctype: doctype, docname: docname };
};

frappe.al_product_config.card_state = function (block) {
	const data = block || {};
	const ok = !!data.ok;
	// Ba trạng thái KHÁC NHAU, ⛔ gộp "chưa gắn" vào "không đọc được":
	// chưa gắn thì có việc phải làm (mở sản phẩm gắn vào), đọc lỗi thì thử lại.
	let state = data.state || (ok ? "ok" : "error");
	// Chỉ "đọc được"/"cảnh báo" mới đòi ok; "chưa gắn" thì ok=False là đúng.
	if ((state === "ok" || state === "warning") && !ok) {
		state = "error";
	}
	if (state === "empty" && ok) state = "ok";
	// Phòng thủ: payload cũ/thiếu state mà đọc được ⇒ coi là ok.
	if (!data.state && ok) state = "ok";
	const status = {
		ok: __("Đọc được"),
		warning: __("Đang ngừng dùng"),
		empty: __("Chưa gắn"),
		error: __("Không đọc được"),
	}[state] || __("Không đọc được");
	return {
		state: state,
		tone: state === "ok" ? "ok" : state,
		status: status,
		// Chỉ trạng thái LỖI mới có câu lỗi. "Đang ngừng dùng" và "Chưa gắn"
		// có câu riêng của chúng (detail / missing), ⛔ dán "Không đọc được".
		error:
			state === "error"
				? data.error || __("Không đọc được khối này.")
				: "",
		// "Chưa gắn" vẫn cần LÝ DO (vd hồ sơ biến: thiếu thì gợi ý hiện toàn bộ biến).
		note: state === "empty" ? data.error || "" : "",
		can_open: ok && !!data.link,
		fix_link: state === "empty" ? data.fix_link || "" : "",
		label: data.label || data.code || data.name || __("Chưa có"),
	};
};

// ── Vẽ trang ──────────────────────────────────────────────────────────
// Câu lỗi cho người dùng: ưu tiên câu server gửi (đã là tiếng Việt), chỉ
// dùng câu "mất mạng" khi thật sự không có phản hồi.
function _al_error_text(r) {
	try {
		const payload = r && r.responseJSON;
		const raw = payload && payload._server_messages;
		if (raw) {
			const first = JSON.parse(JSON.parse(raw)[0]);
			const msg = first && first.message;
			if (msg) {
				return $("<div>").html(msg).text();
			}
		}
	} catch (e) {
		// ⛔ để lỗi đọc câu server làm hỏng màn hình lỗi.
	}
	return __("Không kết nối được máy chủ — kiểm tra mạng rồi thử lại.");
}

function _al_render_prompt(state) {
	const body = state.page.body;
	body.empty();
	const box = $('<div class="al-cfg-empty">').appendTo(body);
	$('<div class="al-cfg-empty-title">')
		.text(__("Chọn một sản phẩm để xem cấu hình"))
		.appendTo(box);
	$('<div class="al-cfg-empty-text">')
		.text(
			__(
				"Chọn sản phẩm (BOM) ở ô phía trên. Trang sẽ gom bộ BOM, " +
					"bộ phụ kiện, bộ biến, mẫu tính giá, hồ sơ biến và các " +
					"quy tắc đang dùng về một chỗ."
			)
		)
		.appendTo(box);
}

function _al_render_message(state, message) {
	const body = state.page.body;
	body.empty();
	$('<div class="al-cfg-loading">').text(message).appendTo(body);
}

function _al_render_failure(state, message) {
	const body = state.page.body;
	body.empty();
	const card = $('<div class="al-cfg-card is-error al-cfg-card-wide">')
		.appendTo(body);
	$('<div class="al-cfg-card-title">')
		.text(__("Không tải được trang"))
		.appendTo(card);
	$('<div class="al-cfg-card-error">').text(message).appendTo(card);
	const actions = $('<div class="al-cfg-card-actions">').appendTo(card);
	$('<button class="btn btn-xs btn-default">')
		.text(__("Tải lại"))
		.on("click", function () {
			_al_reload(state);
		})
		.appendTo(actions);
}

function _al_render_children(body, children) {
	if (!children || !children.length) {
		return;
	}
	const list = $('<ul class="al-cfg-card-list">').appendTo(body);
	children.forEach(function (child) {
		const item = $("<li>").appendTo(list);
		const label = child.label || child.code || child.name || "";
		if (child.link) {
			$('<a href="#">')
				.text(label)
				.on("click", function (event) {
					event.preventDefault();
					frappe.set_route(child.link);
				})
				.appendTo(item);
		} else {
			$('<span class="al-cfg-card-child-muted">')
				.text(label || __("Không đọc được"))
				.appendTo(item);
		}
		if (!child.link && child.error) {
			$('<span class="al-cfg-card-child-error">')
				.text(child.error)
				.appendTo(item);
		}
	});
}

function _al_make_card(state, block) {
	const data = block || {};
	const st = frappe.al_product_config.card_state(data);
	const card = $('<div class="al-cfg-card">').addClass(
		st.tone === "ok"
			? "is-ok"
			: st.tone === "empty"
			? "is-empty"
			: st.tone === "warning"
			? "is-warn"
			: "is-error"
	);

	const head = $('<div class="al-cfg-card-head">').appendTo(card);
	$('<div class="al-cfg-card-title">')
		.text(data.title || "")
		.appendTo(head);
	$('<span class="al-cfg-card-status">')
		.addClass(
			st.tone === "ok"
				? "is-ok"
				: st.tone === "empty"
				? "is-empty"
				: st.tone === "warning"
				? "is-warn"
				: "is-error"
		)
		.text(st.status)
		.appendTo(head);

	const body = $('<div class="al-cfg-card-body">').appendTo(card);
	if (st.tone === "ok" || st.tone === "warning") {
		$('<div class="al-cfg-card-label">').text(st.label).appendTo(body);
		if (data.code && data.code !== st.label) {
			$('<div class="al-cfg-card-code">').text(data.code).appendTo(body);
		}
		if (data.detail) {
			$('<div class="al-cfg-card-detail">').text(data.detail).appendTo(body);
		}
	} else {
		if (st.error) {
			$('<div class="al-cfg-card-error">').text(st.error).appendTo(body);
		}
		if (st.note) {
			$('<div class="al-cfg-card-detail">').text(st.note).appendTo(body);
		}
	}
	// Khối nhiều bản ghi (quy tắc) vẫn hiện các mục đọc được bên cạnh câu lỗi.
	_al_render_children(body, data.children || []);

	const actions = $('<div class="al-cfg-card-actions">').appendTo(card);
	if (st.can_open) {
		$('<button class="btn btn-xs btn-default">')
			.text(__("Mở"))
			.on("click", function () {
				frappe.set_route(data.link);
			})
			.appendTo(actions);
	}
	if (st.fix_link) {
		// "Chưa gắn" ⇒ việc phải làm là mở sản phẩm để gắn, ⛔ "Tải lại".
		$('<button class="btn btn-xs btn-primary">')
			.text(__("Mở sản phẩm để gắn"))
			.on("click", function () {
				frappe.set_route(st.fix_link);
			})
			.appendTo(actions);
	}
	if (st.state === "error") {
		$('<button class="btn btn-xs btn-default">')
			.text(__("Tải lại"))
			.on("click", function () {
				_al_reload(state);
			})
			.appendTo(actions);
	}
	if (!actions.children().length) {
		actions.remove();
	}

	return card;
}

function _al_render_blocks(state, payload) {
	const data = payload || {};
	const body = state.page.body;
	body.empty();

	const blocks = data.blocks || [];
	const product = blocks[0] || {};

	const head = $('<div class="al-cfg-head">').appendTo(body);
	$('<div class="al-cfg-head-title">')
		.text(product.label || data.docname || "")
		.appendTo(head);
	if (product.code && product.code !== product.label) {
		$('<div class="al-cfg-head-code">').text(product.code).appendTo(head);
	}
	$('<div class="al-cfg-head-read-at">')
		.text(
			data.read_at_display
				? __("Đọc lúc {0}", [data.read_at_display])
				: __("Vừa đọc xong")
		)
		.appendTo(head);
	$('<button class="btn btn-xs btn-default al-cfg-head-reload">')
		.text(__("Tải lại"))
		.on("click", function () {
			_al_reload(state);
		})
		.appendTo(head);

	const grid = $('<div class="al-cfg-grid">').appendTo(body);
	blocks.forEach(function (block) {
		grid.append(_al_make_card(state, block));
	});
}

// ── Nạp dữ liệu ───────────────────────────────────────────────────────
function _al_reload(state) {
	const docname =
		state.docname ||
		(state.bom_field && state.bom_field.get_value()) ||
		"";
	_al_load(state, {
		doctype: frappe.al_product_config.PRODUCT_DOCTYPE,
		docname: docname,
	});
}

function _al_load(state, params) {
	if (!params.docname) {
		state.docname = "";
		state.loading = false;
		if (state.bom_field && state.bom_field.get_value()) {
			state.bom_field.set_value("");
		}
		_al_render_prompt(state);
		return;
	}

	state.docname = params.docname;
	state.loading = true;
	_al_render_message(state, __("Đang đọc cấu hình sản phẩm…"));

	frappe.call({
		method: frappe.al_product_config.METHOD,
		args: { doctype: params.doctype, docname: params.docname },
		callback: function (r) {
			// Người dùng đã chọn sản phẩm khác ⇒ bỏ phản hồi cũ.
			if (state.docname !== params.docname) {
				return;
			}
			state.loading = false;
			if (!r || !r.message) {
				_al_render_failure(
					state,
					__("Không tải được cấu hình sản phẩm — vui lòng thử lại.")
				);
				return;
			}
			if (state.bom_field.get_value() !== params.docname) {
				state.bom_field.set_value(params.docname);
			}
			_al_render_blocks(state, r.message);
		},
		error: function (r) {
			if (state.docname !== params.docname) {
				return;
			}
			state.loading = false;
			_al_render_failure(state, _al_error_text(r));
		},
	});
}

frappe.pages["al-product-config"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cấu hình sản phẩm"),
		single_column: true,
	});

	const state = { page: page, docname: "", loading: false };
	wrapper.al_product_config = state;

	state.bom_field = page.add_field({
		fieldname: "bom",
		label: __("Sản phẩm"),
		fieldtype: "Link",
		options: frappe.al_product_config.PRODUCT_DOCTYPE,
		placeholder: __("Chọn sản phẩm cần xem cấu hình"),
		change: function () {
			const name = state.bom_field.get_value();
			if (!name || name === state.docname) {
				return;
			}
			// `frappe.set_route(route, options)` ⛔ nhận options như tham số
			// thứ hai — Frappe coi đó là một đoạn route ⇒ URL hỏng. Gán
			// `frappe.route_options` TRƯỚC khi đổi route.
			frappe.route_options = {
				doctype: frappe.al_product_config.PRODUCT_DOCTYPE,
				docname: name,
			};
			frappe.set_route("al-product-config");
		},
	});

	_al_load(
		state,
		frappe.al_product_config.read_params(frappe.route_options)
	);
};

frappe.pages["al-product-config"].on_page_show = function (wrapper) {
	const state = wrapper.al_product_config;
	if (!state || state.loading) {
		return;
	}
	if (!frappe.al_product_config.read_params(frappe.route_options).docname) {
		return;
	}
	// Quay lại trang (vd sửa bộ BOM rồi Back) ⇒ nạp LẠI, ⛔ hiện số cũ.
	_al_load(
		state,
		frappe.al_product_config.read_params(frappe.route_options)
	);
};
