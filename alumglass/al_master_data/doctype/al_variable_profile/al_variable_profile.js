// AL Variable Profile — Client Script
// Module: AL Master Data
//
// Nút "Xem trước danh sách biến": cho admin thấy ĐÚNG danh sách biến mà form
// nghiệp vụ sẽ nhận khi gán profile này — theo nhóm, kèm nguồn (provenance)
// và cảnh báo trùng tên.
//
// Dữ liệu 100% từ server (`alumglass.api.variable_catalog.preview_variable_catalog`),
// ⛔ KHÔNG có danh sách biến cứng ở client — thêm nguồn biến mới (adapter,
// rule, AL Variable Settings) là preview tự có.

frappe.provide("alumglass.VariableProfilePreview");

alumglass.VariableProfilePreview = {
    // ── Escape HTML ──────────────────────────────────────────────────────
    // Tên/nhãn/giá trị biến là dữ liệu người dùng nhập (có thể chứa <, &…) —
    // phải escape trước khi ghép vào chuỗi HTML của dialog.
    _esc: function (value) {
        let s = (value === null || value === undefined) ? "" : String(value);
        if (frappe.utils && frappe.utils.escape_html) {
            return frappe.utils.escape_html(s);
        }
        return s.replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    },

    // ── Hiển thị giá trị: rỗng → "—", object → JSON, chuỗi dài → rút gọn ──
    _val: function (value) {
        if (value === null || value === undefined) return "—";
        let s;
        if (typeof value === "object") {
            try { s = JSON.stringify(value); } catch (e) { s = String(value); }
        } else {
            s = String(value);
        }
        if (s === "") return "—";
        if (s.length > 80) s = s.slice(0, 77) + "…";
        return this._esc(s);
    },

    // ── Mở dialog chọn ngữ cảnh rồi gọi API ──────────────────────────────
    open: function (frm) {
        let profileCode = frm.doc.profile_code || frm.doc.name;
        if (!profileCode) {
            frappe.msgprint(__("Lưu profile trước khi xem trước danh sách biến."));
            return;
        }

        // Doctype mặc định cho ô chọn nằm ở Single `AL Variable Settings.preview_doctype`
        // (KHÔNG phải field của profile). frappe.prompt cần giá trị ĐỒNG BỘ nên
        // phải đọc Single xong mới dựng prompt; lỗi/không có ⇒ dùng "".
        let done = false;
        let fallback = function () {
            if (done) return;
            done = true;
            alumglass.VariableProfilePreview._prompt(frm, profileCode, "");
        };

        try {
            frappe.db.get_single_value("AL Variable Settings", "preview_doctype")
                .then(function (value) {
                    if (done) return;
                    done = true;
                    alumglass.VariableProfilePreview._prompt(frm, profileCode, value || "");
                })
                .catch(fallback);
        } catch (e) {
            // Site chưa migrate (Single/field chưa tồn tại) — không chặn preview.
            fallback();
        }
    },

    // ── Dựng dialog nhập ngữ cảnh preview ────────────────────────────────
    _prompt: function (frm, profileCode, defaultDoctype) {
        frappe.prompt([
            {
                fieldname: "doctype",
                fieldtype: "Link",
                options: "DocType",
                label: __("DocType cần xem trước"),
                reqd: 1,
                default: defaultDoctype || "",
                description: __("Doctype nghiệp vụ nhận profile này, ví dụ AL Bom Set, AL Cost Template."),
            },
            {
                fieldname: "docname",
                fieldtype: "Data",
                label: __("Bản ghi (không bắt buộc)"),
                description: __("Để trống nếu chỉ muốn xem danh mục biến; nhập tên bản ghi để resolve giá trị thật."),
            },
            {
                fieldname: "child_table",
                fieldtype: "Data",
                label: __("Bảng con (không bắt buộc)"),
                description: __("Ví dụ items — dùng để áp luật theo dòng và only_fields."),
            },
            {
                fieldname: "fieldname",
                fieldtype: "Data",
                label: __("Field đang sửa (không bắt buộc)"),
                description: __("Dùng để áp luật only_fields, ví dụ calc_formula."),
            },
        ], function (values) {
            alumglass.VariableProfilePreview._call(profileCode, values);
        }, __("Xem trước danh sách biến"), __("Xem trước"));
    },

    // ── Gọi API preview ──────────────────────────────────────────────────
    _call: function (profileCode, values) {
        frappe.call({
            method: "alumglass.api.variable_catalog.preview_variable_catalog",
            args: {
                profile: profileCode,
                doctype: values.doctype,
                docname: values.docname || "",
                child_table: values.child_table || "",
                fieldname: values.fieldname || "",
            },
            freeze: true,
            freeze_message: __("Đang dựng danh sách biến…"),
            callback: function (r) {
                alumglass.VariableProfilePreview.render(r && r.message, values, profileCode);
            },
            error: function () {
                frappe.msgprint({
                    title: __("Không xem trước được"),
                    indicator: "red",
                    message: __("Không gọi được API xem trước danh sách biến. "
                        + "Kiểm tra app đã migrate và API variable_catalog đã được cài đặt."),
                });
            },
        });
    },

    // ── Render kết quả ───────────────────────────────────────────────────
    render: function (res, values, profileCode) {
        if (!res) {
            frappe.msgprint({
                title: __("Không xem trước được"),
                indicator: "red",
                message: __("API không trả dữ liệu. Thử lại sau khi migrate."),
            });
            return;
        }
        if (res.success === false) {
            frappe.msgprint({
                title: __("Không xem trước được"),
                indicator: "red",
                message: this._esc(res.error || __("Profile hoặc doctype không hợp lệ.")),
            });
            return;
        }

        let meta = res.meta || {};
        let rows = this._buildRows(res);
        let duplicates = Array.isArray(meta.duplicates) ? meta.duplicates : [];

        let header = this._renderHeader(res, values, profileCode, meta, rows.length);
        let body = rows.length
            ? this._renderTable(rows)
            : this._renderEmpty(meta);
        let warn = duplicates.length ? this._renderDuplicates(duplicates) : "";

        frappe.msgprint({
            title: __("Xem trước danh sách biến"),
            indicator: duplicates.length ? "orange" : "blue",
            wide: true,
            message: header + warn + body,
        });
    },

    // ── Dựng danh sách dòng từ groups (fallback: variables phẳng) ────────
    _buildRows: function (res) {
        let rows = [];
        let pushRow = function (groupLabel, v) {
            rows.push({
                group: groupLabel || v.group || "—",
                name: v.name || "",
                label: v.label || "",
                type: v.type || "",
                value: v.value,
                provenance: v.provenance || v.value_source || v.source_kind || "—",
            });
        };

        if (Array.isArray(res.groups) && res.groups.length) {
            res.groups.forEach(function (g) {
                (g.variables || []).forEach(function (v) {
                    pushRow(g.label || g.key || "", v);
                });
            });
        }
        if (!rows.length && Array.isArray(res.variables)) {
            res.variables.forEach(function (v) { pushRow("", v); });
        }
        return rows;
    },

    _renderHeader: function (res, values, profileCode, meta, count) {
        let profile = res.profile || {};
        let code = profile.code || profileCode;
        let name = profile.name || "";
        let parts = [
            __("Profile") + ": <b>" + this._esc(code) + "</b>" +
                (name ? " — " + this._esc(name) : ""),
            __("DocType") + ": <b>" + this._esc(values.doctype) + "</b>",
        ];
        if (values.child_table) {
            parts.push(__("Bảng con") + ": <b>" + this._esc(values.child_table) + "</b>");
        }
        if (values.fieldname) {
            parts.push(__("Field") + ": <b>" + this._esc(values.fieldname) + "</b>");
        }

        let stats = __("Tổng") + ": <b>" + count + "</b>";
        if (meta.excluded_by_rules !== undefined) {
            stats += " · " + __("Bị luật loại") + ": <b>" + cint(meta.excluded_by_rules) + "</b>";
        }

        return '<div class="small" style="margin-bottom:8px;">'
            + parts.join(" · ")
            + '<div class="text-muted" style="margin-top:2px;">' + stats + "</div>"
            + "</div>";
    },

    _renderTable: function (rows) {
        let html = [
            '<div style="max-height:420px;overflow:auto;">',
            '<table class="table table-bordered table-condensed small" style="margin-bottom:0;">',
            "<thead><tr>",
            '<th style="width:16%;">' + __("Nhóm") + "</th>",
            '<th style="width:18%;">' + __("Tên biến") + "</th>",
            '<th style="width:20%;">' + __("Nhãn") + "</th>",
            '<th style="width:8%;">' + __("Kiểu") + "</th>",
            '<th style="width:16%;">' + __("Giá trị") + "</th>",
            '<th style="width:22%;">' + __("Nguồn") + "</th>",
            "</tr></thead><tbody>",
        ];
        rows.forEach(function (r) {
            html.push(
                "<tr>",
                "<td>" + this._esc(r.group) + "</td>",
                "<td><code>" + this._esc(r.name) + "</code></td>",
                "<td>" + this._esc(r.label || "—") + "</td>",
                "<td>" + this._esc(r.type || "—") + "</td>",
                "<td>" + this._val(r.value) + "</td>",
                "<td>" + this._esc(r.provenance) + "</td>",
                "</tr>"
            );
        }, this);
        html.push("</tbody></table></div>");
        return html.join("");
    },

    _renderEmpty: function (meta) {
        let msg = __("Profile này chưa trả về biến nào cho ngữ cảnh đã chọn.");
        if (cint(meta.excluded_by_rules)) {
            msg += " " + __("Có {0} biến bị luật loại — kiểm tra lại action Include/Exclude.", [cint(meta.excluded_by_rules)]);
        } else {
            msg += " " + __("Kiểm tra lại DocType/bảng con đã chọn và các luật Include của profile.");
        }
        return '<div class="text-muted small" style="padding:12px 0;">' + msg + "</div>";
    },

    // ── Cảnh báo trùng tên ───────────────────────────────────────────────
    _renderDuplicates: function (duplicates) {
        let items = duplicates.map(function (d) {
            let name = this._esc(d.name || d.variable || "?");
            let kept = d.kept ? this._esc(d.kept) : "—";
            let dropped = d.dropped
                ? (Array.isArray(d.dropped) ? d.dropped.map(x => this._esc(x)).join(", ") : this._esc(d.dropped))
                : "—";
            return "<li><code>" + name + "</code> — "
                + __("giữ") + ": " + kept + "; "
                + __("bỏ") + ": " + dropped + "</li>";
        }, this);

        return '<div style="border:1px solid #f59e0b;background:#fffbeb;border-radius:6px;'
            + 'padding:8px 12px;margin-bottom:10px;" class="small">'
            + "<b>" + __("Cảnh báo: có biến trùng tên ở nhiều nguồn") + "</b>"
            + '<div class="text-muted" style="margin:2px 0 6px;">'
            + __("Catalog chỉ giữ một nguồn cho mỗi tên biến; các nguồn còn lại bị bỏ (không ảnh hưởng giá trị tính toán).")
            + "</div>"
            + "<ul style=\"margin:0;padding-left:18px;\">" + items.join("") + "</ul>"
            + "</div>";
    },
};

// ── Đăng ký nút trên form ────────────────────────────────────────────────
frappe.ui.form.on("AL Variable Profile", {
    refresh: function (frm) {
        // Chưa lưu thì chưa có profile_code để preview
        if (frm.is_new()) return;

        frm.add_custom_button(__("Xem trước danh sách biến"), function () {
            alumglass.VariableProfilePreview.open(frm);
        }, __("Công cụ"));
    },
});
