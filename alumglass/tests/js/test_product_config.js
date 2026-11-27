// Test THUẦN cho phần logic của trang "Cấu hình sản phẩm" (B8/Đ1).
//
// Trang vẽ DOM bằng jQuery nên phần vẽ KHÔNG test ở đây (xem báo cáo). Thứ
// được test là 2 hàm thuần mà lỗi của chúng làm hỏng cả trang:
//   · read_params — đọc query param ?doctype=&docname= (mặc định AL BOM).
//   · card_state — quyết định khối ok/lỗi, có mở được form hay không.
//
// Chạy:
//   cd ~/myfrappe/apps/alumglass
//   node alumglass/tests/js/test_product_config.js
"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

// ── Stub tối thiểu ────────────────────────────────────────────────────
global.frappe = {
	pages: {},
	provide: function (namespace) {
		const parts = String(namespace).split(".");
		if (parts[0] === "frappe") {
			parts.shift();
		}
		let obj = global.frappe;
		parts.forEach(function (part) {
			if (!obj[part]) {
				obj[part] = {};
			}
			obj = obj[part];
		});
	},
};
global.__ = function (message) {
	return message;
};

// Frappe tạo `frappe.pages[<tên trang>]` (container DOM) TRƯỚC khi eval
// script của Page — xem `frappe.views.Page` constructor. Stub làm đúng vậy.
global.frappe.pages["al-product-config"] = {};

const PAGE_JS = path.join(
	__dirname,
	"../../al_master_data/page/al_product_config/al_product_config.js"
);
vm.runInThisContext(fs.readFileSync(PAGE_JS, "utf8"), { filename: PAGE_JS });

const cfg = global.frappe.al_product_config;

let passed = 0;
function test(name, fn) {
	fn();
	passed += 1;
	console.log("ok - " + name);
}

// ── read_params ───────────────────────────────────────────────────────
test("mặc định doctype = AL BOM, docname rỗng", function () {
	const got = cfg.read_params();
	assert.deepStrictEqual(got, { doctype: "AL BOM", docname: "" });
});

test("đọc đúng ?doctype=&docname=", function () {
	const got = cfg.read_params({ doctype: "AL BOM", docname: "BOM-1" });
	assert.deepStrictEqual(got, { doctype: "AL BOM", docname: "BOM-1" });
});

test("thiếu doctype thì mặc định AL BOM", function () {
	const got = cfg.read_params({ docname: "BOM-2" });
	assert.strictEqual(got.doctype, "AL BOM");
	assert.strictEqual(got.docname, "BOM-2");
});

test("nhận cả khoá name (query param cũ)", function () {
	const got = cfg.read_params({ name: "BOM-3" });
	assert.strictEqual(got.docname, "BOM-3");
});

test("giá trị lặp trên URL lấy phần tử đầu", function () {
	const got = cfg.read_params({ docname: ["BOM-1", "BOM-2"] });
	assert.strictEqual(got.docname, "BOM-1");
});

test("cắt khoảng trắng", function () {
	const got = cfg.read_params({ docname: "  BOM-9  " });
	assert.strictEqual(got.docname, "BOM-9");
});

// ── card_state ────────────────────────────────────────────────────────
test("khối đang ngừng dùng: tone vàng, KHÔNG có câu lỗi giả", function () {
	const st = cfg.card_state({
		ok: true,
		state: "warning",
		label: "Cửa đi 2 cánh",
		detail: "Sản phẩm đã ngừng dùng — báo giá mới nên cân nhắc.",
	});
	assert.strictEqual(st.tone, "warning");
	assert.strictEqual(st.status, "Đang ngừng dùng");
	assert.strictEqual(st.error, "");
});

test("khối chưa gắn: xám + đường mở sản phẩm, KHÔNG phải lỗi", function () {
	const st = cfg.card_state({
		ok: false,
		state: "empty",
		error: "Sản phẩm chưa gắn bộ BOM.",
		fix_link: "/app/al-bom/AL-BOM-1",
	});
	assert.strictEqual(st.tone, "empty");
	assert.strictEqual(st.status, "Chưa gắn");
	assert.strictEqual(st.fix_link, "/app/al-bom/AL-BOM-1");
	// Vẫn phải giữ LÝ DO (vd hồ sơ biến: thiếu thì ô công thức hiện toàn bộ biến).
	assert.strictEqual(st.note, "Sản phẩm chưa gắn bộ BOM.");
});

test("payload cũ thiếu state mà đọc được ⇒ vẫn coi là ok", function () {
	const st = cfg.card_state({ ok: true, link: "/x", label: "X" });
	assert.strictEqual(st.state, "ok");
	assert.strictEqual(st.error, "");
});

test("khối ok: tone ok, mở được, nhãn là tên", function () {
	const st = cfg.card_state({
		ok: true,
		link: "/app/al-bom-set/SET-1",
		label: "Bộ BOM cửa đi",
	});
	assert.strictEqual(st.tone, "ok");
	assert.strictEqual(st.can_open, true);
	assert.strictEqual(st.label, "Bộ BOM cửa đi");
	assert.strictEqual(st.error, "");
});

test("khối lỗi: tone error, giữ câu lỗi, không mở", function () {
	const st = cfg.card_state({
		ok: false,
		link: "/app/al-bom-set/SET-1",
		error: "Không đọc được bộ BOM — bộ có thể đã bị xoá.",
	});
	assert.strictEqual(st.tone, "error");
	assert.strictEqual(st.can_open, false);
	assert.strictEqual(st.error, "Không đọc được bộ BOM — bộ có thể đã bị xoá.");
});

test("khối lỗi không có câu lỗi vẫn có câu mặc định", function () {
	const st = cfg.card_state({ ok: false });
	assert.ok(st.error.length > 0);
	assert.strictEqual(st.tone, "error");
});

test("khối ok nhưng không có link thì không mở", function () {
	const st = cfg.card_state({ ok: true, label: "Chưa có quy tắc nào được dùng" });
	assert.strictEqual(st.can_open, false);
});

test("thiếu tên thì nhãn rơi về mã", function () {
	const st = cfg.card_state({ ok: true, code: "SET-1" });
	assert.strictEqual(st.label, "SET-1");
});

test("không có dữ liệu khối vẫn không ném", function () {
	const st = cfg.card_state(null);
	assert.strictEqual(st.tone, "error");
	assert.ok(st.label.length > 0);
});

// ── Hợp đồng với backend ──────────────────────────────────────────────
test("tên method khớp API đã viết", function () {
	assert.strictEqual(
		cfg.METHOD,
		"alumglass.api.product_config.get_product_config"
	);
});

test("trang đăng ký đủ on_page_load và on_page_show", function () {
	const page = global.frappe.pages["al-product-config"];
	assert.ok(page, "phải có frappe.pages['al-product-config']");
	assert.strictEqual(typeof page.on_page_load, "function");
	assert.strictEqual(typeof page.on_page_show, "function");
});

console.log("\n" + passed + " test pass");
