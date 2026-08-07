// alumglass/public/js/grid_placeholder.js
// Hiển thị placeholder mờ NGAY TRONG Ô GRID khi row CHƯA click (collapsed).
// Tự đọc df.placeholder của từng cột — KHÔNG hardcode fieldname nào.
// Khi row đã click (editable), các control hiển thị placeholder native qua df.placeholder.
//
// Usage:
//   alumglass.grid_placeholder.setup(grid)                    // 1 grid / 1 control table
//   alumglass.grid_placeholder.setup_dialog(dialog)           // toàn bộ Table field trong dialog
//   alumglass.grid_placeholder.setup_form(frm)                // toàn bộ bảng con trong form
//   alumglass.grid_placeholder.enable_global()                // auto cho MỌI grid trong app (gọi 1 lần)
//
// File này tự gọi enable_global() khi load → tất cả grid (dialog, doctype, bảng con)
// đều tự áp dụng mà không cần thêm code ở từng nơi. Muốn tắt global, xóa dòng
// alumglass.grid_placeholder.enable_global(); ở cuối file.

frappe.provide("alumglass.grid_placeholder");

alumglass.grid_placeholder = {
	_css_id: "alumglass-grid-placeholder-css",

	ensure_css() {
		if (document.getElementById(this._css_id)) return;
		const style = document.createElement("style");
		style.id = this._css_id;
		style.textContent = `
.alumglass-grid-ph .grid-static-col .static-area:empty::before {
	content: attr(data-grid-placeholder);
	color: var(--text-muted);
	font-weight: 400;
	pointer-events: none;
}
`;
		document.head.appendChild(style);
	},

	// scope có thể là:
	//   - Grid instance (có is_grid = true)
	//   - Table control (có .grid)
	//   - { frm, parentfield }
	_resolve_grid(scope) {
		if (!scope) return null;
		if (scope.grid && scope.grid.is_grid) return scope.grid; // Table control
		if (scope.is_grid) return scope; // Grid instance
		if (scope.frm && scope.parentfield) {
			const ctrl = scope.frm.fields_dict[scope.parentfield];
			return ctrl && ctrl.grid && ctrl.grid.is_grid ? ctrl.grid : null;
		}
		return null;
	},

	// Gắn data-grid-placeholder cho static-area của mọi cột có df.placeholder.
	// static-area tồn tại lâu dài (chỉ đổi nội dung qua .html()) nên gắn lại là idempotent.
	_apply(grid) {
		if (!grid || !grid.wrapper) return;
		grid.wrapper.addClass("alumglass-grid-ph");
		(grid.grid_rows || []).forEach((row) => {
			(row.columns_list || []).forEach((col) => {
				const df = col.df;
				if (df && df.placeholder && col.static_area) {
					col.static_area.attr("data-grid-placeholder", df.placeholder);
				}
			});
		});
	},

	// render_result_rows là điểm duy nhất render mọi row (refresh + pagination + add row)
	// → wrap lại để tự áp dụng sau mỗi lần render, không cần gọi lại thủ công.
	_wrap(grid) {
		if (!grid || grid.__alumglass_ph_wrapped) return grid;
		grid.__alumglass_ph_wrapped = true;
		const me = this;
		const orig_render = grid.render_result_rows.bind(grid);
		grid.render_result_rows = function (...args) {
			const out = orig_render.apply(grid, args);
			me._apply(grid);
			return out;
		};
		return grid;
	},

	setup(scope) {
		this.ensure_css();
		const grid = this._resolve_grid(scope);
		if (!grid) return null;
		this._wrap(grid);
		this._apply(grid);
		return grid;
	},

	// Set / đổi placeholder cho 1 cột grid theo runtime.
	// Lý do KHÔNG dùng frm.set_df_property('<table>', 'placeholder', ..., null, '<col>'):
	// trong Frappe v14 set_df_property không có docname sẽ nhắm vào df của TABLE field (không phải
	// cột), còn có docname lại mutate object copy theo row-name khác object col.df đang giữ → không
	// hiển thị. Hàm này mutate đúng các object grid đang dùng (grid.docfields cho row mới + từng
	// row.docfields/col.df cho row hiện tại) rồi refresh.
	// scope: Grid | Table control | { frm, parentfield } (như _resolve_grid).
	set_column(scope, fieldname, placeholder) {
		const grid = this._resolve_grid(scope);
		if (!grid || !fieldname) return null;
		this._set_column_on_grid(grid, fieldname, placeholder);
		grid.refresh(); // render lại → _apply gắn data-grid-placeholder
		return grid;
	},

	// mutate placeholder trên mọi object grid đang dùng, KHÔNG refresh (dùng nội bộ)
	_set_column_on_grid(grid, fieldname, placeholder) {
		// grid-level docfields — dùng để dựng row mới thêm sau
		(grid.docfields || []).forEach((df) => {
			if (df.fieldname === fieldname) df.placeholder = placeholder;
		});

		// từng row hiện tại: cập nhật row.docfields + col.df để hiển thị ngay
		(grid.grid_rows || []).forEach((row) => {
			(row.docfields || []).forEach((df) => {
				if (df.fieldname === fieldname) df.placeholder = placeholder;
			});
			const col = row.columns && row.columns[fieldname];
			if (col && col.df) col.df.placeholder = placeholder;
		});
	},

	// Đặt placeholder cho nhiều cột cùng lúc: set_columns(grid, { col_a: 'text', col_b: 'text' })
	// chỉ refresh 1 lần.
	set_columns(scope, map) {
		const grid = this._resolve_grid(scope);
		if (!grid || !map) return null;
		Object.keys(map).forEach((fieldname) => {
			this._set_column_on_grid(grid, fieldname, map[fieldname]);
		});
		grid.refresh();
		return grid;
	},

	// Quét toàn bộ Table field trong dialog
	setup_dialog(dialog) {
		if (!dialog || !dialog.fields_dict) return [];
		const done = [];
		Object.keys(dialog.fields_dict).forEach((fieldname) => {
			const ctrl = dialog.fields_dict[fieldname];
			if (ctrl && ctrl.grid && ctrl.df && ctrl.df.fieldtype === "Table") {
				done.push(this.setup(ctrl));
			}
		});
		return done;
	},

	// Quét toàn bộ bảng con (Table child) trong form doctype
	setup_form(frm) {
		if (!frm || !frm.meta || !frm.meta.fields) return [];
		const done = [];
		frm.meta.fields.forEach((df) => {
			if (df.fieldtype === "Table" && frm.fields_dict[df.fieldname]) {
				const ctrl = frm.fields_dict[df.fieldname];
				if (ctrl && ctrl.grid) done.push(this.setup(ctrl));
			}
		});
		return done;
	},

	// Patch ControlTable.make 1 lần → MỌI grid (dialog/doctype/bảng con/web form)
	// trong app đều tự wrap. Chỉ ảnh hưởng cột nào có df.placeholder.
	enable_global() {
		this.ensure_css();
		if (!frappe.ui.form || !frappe.ui.form.ControlTable) return;
		if (frappe.ui.form.ControlTable.prototype.__alumglass_ph_patched) return;
		frappe.ui.form.ControlTable.prototype.__alumglass_ph_patched = true;
		const me = this;
		const orig_make = frappe.ui.form.ControlTable.prototype.make;
		frappe.ui.form.ControlTable.prototype.make = function (...args) {
			const out = orig_make.apply(this, args);
			if (this.grid) {
				me._wrap(this.grid);
				me._apply(this.grid);
			}
			return out;
		};
	},
};

// Tự bật global khi load → zero-config cho toàn bộ app.
alumglass.grid_placeholder.enable_global();
