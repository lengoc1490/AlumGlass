// ═══════════════════════════════════════════════════════════════════════════
// AL Variable Set Item — ô giá trị hiển thị ĐÚNG KIỂU của biến trong Library
//
// Owner 2026-11-27: "bảng con đã lấy biến từ AL Variable Library thì phải lấy
// phụ thuộc vào giá trị đã setting". Nghĩa là:
//   Select        → ô chọn danh sách (đúng các lựa chọn đã khai)
//   Link          → ô chọn bản ghi của đúng doctype đã khai
//   Float / Int / Currency / Percent → ô nhập số
//   Check         → ô đánh dấu
//   Data (và mọi kiểu lạ) → ô nhập chữ tự do
//
// ⚠ Tệp này nạp TOÀN TRANG (`app_include_js`), không phải `doctype_js` của
// doctype con. Vì sao: Frappe chỉ eval `__js` của doctype đang mở form; dòng
// con dùng chung script_manager của form CHA ⇒ JS đặt cạnh JSON doctype con
// KHÔNG BAO GIỜ chạy (xem hooks.py, mục 2 tệp al_bom_item/al_accessory_item).
//
// ⚠ `df` của dòng là bản COPY RIÊNG cho từng dòng (frappe.meta.make_docfield_copy_for)
// ⇒ đổi kiểu ở đây KHÔNG ảnh hưởng dòng khác, KHÔNG ảnh hưởng lưới của doctype
// con ở nơi khác. Đổi xong phải vẽ lại ô, nếu không ô giữ control cũ.
// ═══════════════════════════════════════════════════════════════════════════

(function () {
    var CHILD = "AL Variable Set Item";
    var VALUE_FIELD = "default_value";

    // Kiểu giữ NGUYÊN tên fieldtype Frappe; kiểu lạ ⇒ Data.
    var PASSTHROUGH = {
        Float: "Float",
        Int: "Int",
        Currency: "Currency",
        Percent: "Percent",
        Check: "Check",
        Data: "Data",
    };

    /**
     * Kiểu + options mong muốn cho ô giá trị của 1 dòng.
     * Thiếu cấu hình (Select chưa có lựa chọn / Link chưa có doctype) ⇒ rơi về
     * Data, ⛔ dựng ô chọn rỗng khiến người dùng không nhập được gì.
     */
    function _want_for(row) {
        row = row || {};
        var type = (String(row.var_type == null ? "" : row.var_type)).trim() || "Data";

        if (type === "Select") {
            var opts = String(row.select_options == null ? "" : row.select_options).trim();
            if (!opts) {
                // Rơi về ô chữ ⇒ PHẢI nói vì sao, nếu không người dùng tưởng
                // đã cấu hình đúng và chỉ phát hiện lúc tính giá.
                return {
                    type: "Data",
                    options: "",
                    hint: __("Biến kiểu Chọn danh sách nhưng chưa khai 'Select Options' — ô này tạm là ô chữ tự do. Khai lựa chọn (mỗi dòng một giá trị) để hiện danh sách chọn."),
                };
            }
            // Không bắt buộc ⇒ cho phép bỏ trống (lựa chọn rỗng đầu danh sách).
            if (!row.is_required) opts = "\n" + opts;
            return { type: "Select", options: opts, hint: "" };
        }
        if (type === "Link") {
            var link = String(row.link_doctype == null ? "" : row.link_doctype).trim();
            if (!link) {
                return {
                    type: "Data",
                    options: "",
                    hint: __("Biến kiểu Liên kết nhưng chưa khai 'Link Doctype' — ô này tạm là ô chữ tự do. Khai doctype đích để hiện ô chọn bản ghi."),
                };
            }
            return { type: "Link", options: link, hint: "" };
        }
        return { type: PASSTHROUGH[type] || "Data", options: "", hint: "" };
    }

    function _same(df, want) {
        if (!df) return false;
        var options = df.options == null ? "" : String(df.options);
        var hint = df.description == null ? "" : String(df.description);
        return df.fieldtype === want.type && options === want.options
            && hint === (want.hint || "");
    }

    /** Vẽ lại ô giá trị trên MỘT form (form dòng trong hộp thoại). */
    function _apply_on_form(form) {
        if (!form || !form.doc || !form.fields_dict) return;
        var field = form.fields_dict[VALUE_FIELD];
        if (!field || !field.df) return;

        var want = _want_for(form.doc);
        if (_same(field.df, want)) return;

        var df = Object.assign({}, field.df, {
            fieldtype: want.type,
            options: want.options,
            description: want.hint || "",
        });
        try {
            if (form.layout && form.layout.replace_field) {
                form.layout.replace_field(VALUE_FIELD, df);
                return;
            }
            // Frappe cũ không có replace_field — đặt thuộc tính rồi vẽ lại.
            form.set_df_property(VALUE_FIELD, "fieldtype", want.type);
            form.set_df_property(VALUE_FIELD, "options", want.options);
            // Đường dự phòng cũng phải giữ lời giải thích — thiếu nó thì
            // người dùng thấy ô chữ mà không biết vì sao.
            form.set_df_property(VALUE_FIELD, "description", want.hint || "");
            form.refresh_field(VALUE_FIELD);
        } catch (e) {
            // Lỗi vẽ ô KHÔNG được làm hỏng form cấu hình — nhưng phải BÁO
            // người dùng, đừng im lặng để họ sửa một ô sai kiểu.
            console.warn("[alumglass] không vẽ lại được ô giá trị biến", e);
            frappe.show_alert({
                message: __("Ô giá trị chưa đổi được kiểu — tải lại trang rồi thử lại."),
                indicator: "orange",
            }, 7);
        }
    }

    function _grid_row(frm, cdn) {
        var table = frm && frm.fields_dict && frm.fields_dict.items;
        var grid = table && table.grid;
        return (grid && grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn]) || null;
    }

    /** Áp kiểu cho 1 dòng: bản meta RIÊNG của dòng + ô đang mở (nếu có). */
    function _apply_row(frm, cdn) {
        var row = locals[CHILD] && locals[CHILD][cdn];
        if (!row) return;

        var df = frappe.meta.get_docfield(CHILD, VALUE_FIELD, cdn);
        if (df) {
            var want = _want_for(row);
            if (!_same(df, want)) {
                df.fieldtype = want.type;
                df.options = want.options;
                df.description = want.hint || "";
            }
        }

        var grid_row = _grid_row(frm, cdn);
        if (!grid_row) return;
        if (grid_row.grid_form) _apply_on_form(grid_row.grid_form);
        if (grid_row.refresh_field) grid_row.refresh_field(VALUE_FIELD);
    }

    /**
     * Bù metadata còn thiếu từ Library (dòng tạo trước khi có fetch_from).
     * Dùng khi người dùng CHỌN biến — 1 lượt gọi, không quét cả bảng.
     */
    function _load_library_meta(frm, cdn, done) {
        var row = locals[CHILD] && locals[CHILD][cdn];
        if (!row || !row.variable) { done(); return; }
        frappe.db.get_value(
            "AL Variable Library",
            row.variable,
            ["var_type", "select_options", "link_doctype"],
            function (r) {
                if (r) {
                    ["var_type", "select_options", "link_doctype"].forEach(function (f) {
                        var v = r[f] == null ? "" : r[f];
                        if ((row[f] || "") !== v) {
                            frappe.model.set_value(CHILD, cdn, f, v);
                        }
                    });
                }
                done();
            }
        );
    }

    /**
     * Bù lại kiểu cho dòng còn THIẾU cấu hình, đọc từ Library.
     *
     * Tình huống thật: quản trị khai biến kiểu Chọn danh sách nhưng quên
     * "Select Options" (hoặc Link thiếu "Link Doctype") ⇒ dòng đã lưu giữ cấu
     * hình rỗng. Sửa Library xong, mở lại bộ biến thì dòng cũ phải tự nhận,
     * ⛔ bắt chọn lại biến từng dòng.
     *
     * Một lượt đọc cho cả bảng (`get_list`), ⛔ N query theo dòng.
     *
     * Ghi THẲNG vào dòng (⛔ `frappe.model.set_value`): đây là đồng bộ hiển
     * thị, không phải người dùng sửa — dùng set_value sẽ đánh dấu form "có
     * thay đổi" và bắt người ta lưu/ bỏ khi chỉ mở ra xem.
     */
    function _refresh_stale_meta(frm, done) {
        var rows = (frm && frm.doc && frm.doc.items) || [];
        var names = [];
        rows.forEach(function (row) {
            var type = String(row.var_type == null ? "" : row.var_type).trim();
            var stale = !type
                || (type === "Select" && !String(row.select_options || "").trim())
                || (type === "Link" && !String(row.link_doctype || "").trim());
            if (row.variable && stale && names.indexOf(row.variable) === -1) {
                names.push(row.variable);
            }
        });
        if (!names.length) { done(); return; }

        frappe.db.get_list("AL Variable Library", {
            filters: { name: ["in", names] },
            fields: ["name", "var_type", "select_options", "link_doctype"],
            limit: 0,
        }).then(function (res) {
            var by_name = {};
            (res || []).forEach(function (r) { by_name[r.name] = r; });
            rows.forEach(function (row) {
                var lib = by_name[row.variable];
                if (!lib) return;
                ["var_type", "select_options", "link_doctype"].forEach(function (f) {
                    var value = lib[f] == null ? "" : lib[f];
                    if (String(row[f] == null ? "" : row[f]) !== String(value)) {
                        row[f] = value;
                    }
                });
            });
            done();
        }).catch(function () { done(); });
    }

    frappe.ui.form.on(CHILD, {
        // Hộp thoại sửa dòng vừa dựng ⇒ ô giá trị phải đúng kiểu NGAY.
        form_render: function (frm) {
            _apply_on_form(frm);
        },

        variable: function (frm, cdt, cdn) {
            _load_library_meta(frm, cdn, function () {
                _apply_row(frm, cdn);
            });
        },
        var_type: function (frm, cdt, cdn) { _apply_row(frm, cdn); },
        select_options: function (frm, cdt, cdn) { _apply_row(frm, cdn); },
        link_doctype: function (frm, cdt, cdn) { _apply_row(frm, cdn); },
        is_required: function (frm, cdt, cdn) { _apply_row(frm, cdn); },
    });

    frappe.ui.form.on("AL Variable Set", {
        refresh: function (frm) {
            _refresh_stale_meta(frm, function () {
                (frm.doc.items || []).forEach(function (row) {
                    _apply_row(frm, row.name);
                });
            });
        },
        items_add: function (frm, cdt, cdn) {
            // Grid_row mới dựng sau lượt add ⇒ đợi 1 nhịp rồi áp kiểu.
            setTimeout(function () { _apply_row(frm, cdn); }, 0);
        },
    });
})();
