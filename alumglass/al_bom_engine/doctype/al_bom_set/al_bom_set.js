// AL Bom Set - Client Script
// Module: AL Bom Engine

frappe.ui.form.on("AL Bom Set", {
    refresh: function(frm) {
        // "Mã sản phẩm" (item_code) — Item thuộc Item Group SAN_PHAM + các
        // group con (PA B, Owner chốt). Query method server-side trong
        // alumglass.api.product_item_query (DocField v14 không có cột get_query
        // trong doctype JSON nên dùng JS set_query + query method).
        frm.set_query("item_code", function() {
            return { query: "alumglass.api.product_item_query" };
        });

        // "Default Color" (dòng Items — AL Bom Item) — chỉ cho chọn AL Color
        // Standard đã tích "Mau dai dien" (is_representative). Để trống field
        // này = dòng luôn dùng 1 màu cố định, không tham gia nhóm "Màu sắc
        // theo vị trí" trong dialog báo giá.
        frm.set_query("default_color", "items", function() {
            return { filters: { is_representative: 1 } };
        });

        // "Item Rule" (dòng Items — AL Bom Item): ô này chỉ dùng được quy tắc
        // CHỌN MÃ vật tư (`result_type = ITEM`). Lọc ngay trong ô chọn để
        // nhân viên ⛔ chọn nhầm quy tắc tính giá trị rồi mất mã dòng hàng.
        frm.set_query("item_rule", "items", function() {
            return { filters: { result_type: "ITEM" } };
        });

        // R5 (2026-11-27): ô "Price Rule" của dòng BOM đã bị GỠ — nó là ô
        // chết (engine không đọc), nên bỏ luôn set_query để không còn mã
        // trỏ tới field không tồn tại.

        // B9/Đ2 — "Tạo sản phẩm từ bộ này": nhân bản bộ đang mở thành BỘ MỚI
        // độc lập (bộ BOM + bộ phụ kiện + bộ biến + bộ giá nếu bộ mẫu có trỏ),
        // rồi mở ngay bộ mới để người dùng chỉ sửa vài ô. Chỉ hiện với bộ ĐÃ
        // LƯU — bộ chưa lưu chưa có dữ liệu để nhân bản.
        if (!frm.is_new() && frm.doc.set_code) {
            frm.add_custom_button(__("Tạo sản phẩm từ bộ này"), function() {
                _al_bom_set_clone_open(frm);
            });
        }
    },
});

// Nhãn người-đọc của từng bộ — ⛔ hiện tên DocType kỹ thuật trong hộp thoại.
var _AL_BOM_SET_CLONE_LABELS = {
    "AL Bom Set": __("Bộ BOM"),
    "AL Accessory Set": __("Bộ phụ kiện"),
    "AL Cost Template": __("Bộ giá"),
    "AL Variable Set": __("Bộ biến")
};

// Danh sách việc sẽ làm → HTML để người dùng xác nhận trước khi ghi.
var _al_bom_set_clone_plan_html = function(plan, new_name) {
    var rows = plan.created || [];
    var items = rows.map(function(row) {
        var label = _AL_BOM_SET_CLONE_LABELS[row.doctype] || row.doctype;
        return "<li>" + label + ": <b>" + frappe.utils.escape_html(row.code) +
            "</b> — " + row.rows + " " + __("dòng") + "</li>";
    });
    var html = "<p>" +
        __("Sẽ tạo {0} bộ mới, độc lập với bộ mẫu (sửa bộ mới không đổi bộ mẫu):",
           [rows.length]) +
        "</p>";
    if (new_name) {
        // Cho người dùng soát lại tên vừa gõ — hộp nhập đã đóng.
        html += "<p>" + __("Tên: <b>{0}</b>",
            [frappe.utils.escape_html(new_name)]) + "</p>";
    }
    html += "<ul>" + items.join("") + "</ul>";
    var warnings = plan.warnings || [];
    if (warnings.length) {
        html += "<div class=\"text-muted small\"><b>" + __("Cần biết") +
            ":</b><ul>" +
            warnings.map(function(w) {
                return "<li>" + frappe.utils.escape_html(w) + "</li>";
            }).join("") +
            "</ul></div>";
    }
    return html;
};

// Lỗi ở bước xem trước/tạo ⇒ giữ nguyên mã + tên người dùng vừa gõ và cho
// thử lại ngay (hộp nhập đã đóng thì ⛔ bắt họ gõ lại từ đầu).
var _al_bom_set_clone_retry = function(frm, values, title, message) {
    frappe.msgprint({
        title: title,
        indicator: "red",
        message: frappe.utils.escape_html(
            message || __("Không có phản hồi từ máy chủ.")),
        primary_action: {
            label: __("Thử lại"),
            action: function() {
                _al_bom_set_clone_open(frm, values);
            }
        }
    });
};

// Gọi API tạo thật sau khi người dùng xác nhận kế hoạch.
var _al_bom_set_clone_create = function(frm, values) {
    frappe.call({
        method: "alumglass.api.product_clone.create_product_clone",
        args: {
            source_set_code: frm.doc.name,
            // Mã trống ⇒ server tự đặt mã chưa trùng; plan đã hiện mã sẽ dùng.
            new_code: values.new_code || "",
            new_name: values.new_name
        },
        freeze: true,
        freeze_message: __("Đang tạo bộ mới..."),
        callback: function(r) {
            var res = r.message || {};
            if (!res.ok) {
                _al_bom_set_clone_retry(
                    frm, values, __("Không tạo được"),
                    res.error || __("Máy chủ không cho biết lý do — thử lại; nếu vẫn vậy, báo quản trị."));
                return;
            }
            var top = (res.created || [])[0] || {};
            var warnings = res.warnings || [];
            var message = __("Đã tạo bộ mới <b>{0}</b>.",
                            [frappe.utils.escape_html(top.code || "")]);
            if (warnings.length) {
                message += "<br><br><b>" + __("Cần biết") + ":</b><ul>" +
                    warnings.map(function(w) {
                        return "<li>" + frappe.utils.escape_html(w) + "</li>";
                    }).join("") + "</ul>";
            }
            // ⛔ nhảy trang ngay: danh sách "Cần biết" sẽ bị điều hướng che
            // mất. Để người dùng đọc xong rồi tự bấm mở.
            frappe.msgprint({
                title: __("Tạo sản phẩm từ mẫu"),
                indicator: "green",
                message: message,
                primary_action: top.name ? {
                    label: __("Mở bộ mới"),
                    action: function() {
                        frappe.set_route("Form", "AL Bom Set", top.name);
                    }
                } : null
            });
        },
        error: function() {
            _al_bom_set_clone_retry(
                frm, values, __("Không kết nối được máy chủ"),
                __("Kiểm tra mạng rồi thử lại — mã và tên bạn đã nhập vẫn giữ nguyên."));
        }
    });
};

// Hỏi mã + tên mới → xem kế hoạch (dry-run) → xác nhận → tạo.
// `prefill` dùng khi thử lại sau lỗi — giữ nguyên giá trị người dùng đã gõ.
var _al_bom_set_clone_open = function(frm, prefill) {
    prefill = prefill || {};
    var source_code = frm.doc.name;
    var source_name = frm.doc.set_name || source_code;
    frappe.prompt([
        {
            fieldname: "new_code",
            fieldtype: "Data",
            label: __("Mã bộ mới"),
            default: prefill.new_code || "",
            description: __(
                "Để trống ⇒ hệ thống tự đặt mã chưa trùng (…-MOI2, -MOI3…). Nhập tay nếu muốn mã riêng. Bộ phụ kiện / bộ biến / bộ giá đi kèm được đặt mã theo mã này.")
        },
        {
            fieldname: "new_name",
            fieldtype: "Data",
            label: __("Tên bộ mới"),
            reqd: 1,
            default: prefill.new_name || (source_name + " (bản mới)")
        }
    ], function(values) {
        values.new_code = (values.new_code || "").trim();
        values.new_name = (values.new_name || "").trim();
        frappe.call({
            method: "alumglass.api.product_clone.preview_product_clone",
            args: {
                source_set_code: source_code,
                new_code: values.new_code,
                new_name: values.new_name
            },
            freeze: true,
            freeze_message: __("Đang soạn kế hoạch nhân bản..."),
            callback: function(r) {
                var plan = r.message || {};
                if (!plan.ok) {
                    _al_bom_set_clone_retry(
                        frm, values, __("Chưa xem được kế hoạch"),
                        plan.error || __("Máy chủ không cho biết lý do — thử lại; nếu vẫn vậy, báo quản trị."));
                    return;
                }
                // Người dùng để trống mã ⇒ chốt đúng mã máy đã gợi ý, để cái
                // họ thấy trong kế hoạch chính là cái được tạo.
                if (!values.new_code && plan.suggested_new_code) {
                    values.new_code = plan.suggested_new_code;
                }
                frappe.confirm(_al_bom_set_clone_plan_html(plan, values.new_name), function() {
                    _al_bom_set_clone_create(frm, values);
                }, function() {
                    frappe.show_alert({
                        message: __("Đã huỷ — chưa tạo gì."),
                        indicator: "orange"
                    });
                });
            },
            error: function() {
                _al_bom_set_clone_retry(
                    frm, values, __("Không kết nối được máy chủ"),
                    __("Kiểm tra mạng rồi thử lại — mã và tên bạn đã nhập vẫn giữ nguyên."));
            }
        });
    }, __("Tạo sản phẩm từ bộ này"), __("Xem kế hoạch"));
};
