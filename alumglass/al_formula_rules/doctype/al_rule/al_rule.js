// AL Rule — Client Script
// Module: AL Formula Rules
//
// ═══════════════════════════════════════════════════════════════════════════
// HAI THỨ Ở ĐÂY (thiết kế docs/design/tra-cuu-quy-tac-de-hieu.md §3.1)
//   1. Hiện `rule_description` ngay dưới tiêu đề — quản trị đọc là biết quy
//      tắc dùng để làm gì, không phải suy từ mã + các con số.
//   2. Nút "Thử tra" — nhập 1 giá trị, thấy dòng khớp (tô đậm), kết quả và cả
//      bảng. Không phải lập báo giá mới biết mình cấu hình đúng/sai.
//
// CHỊU ĐƯỢC SITE CHƯA MIGRATE: 4 field mô tả (`rule_description`,
// `input_label`, `input_unit`, `output_label`) có thể CHƯA có trong DB. Thiếu
// field ⇒ chỉ ẩn phần mô tả/nhãn, KHÔNG lỗi, KHÔNG chặn nút Thử tra.
//
// ⛔ KHÔNG tự thêm logic ẩn/hiện cột kết quả (Frappe đã ẩn/hiện section theo
// `depends_on` khai trong JSON).
// ═══════════════════════════════════════════════════════════════════════════

frappe.ui.form.on("AL Rule", {
    refresh: function (frm) {
        _al_rule_show_description(frm);
        _al_rule_add_preview_button(frm);
    },

    // Quản trị sửa mô tả ⇒ cập nhật ngay, không phải tải lại form.
    rule_description: function (frm) {
        _al_rule_show_description(frm);
    },
});

/** Mô tả nghiệp vụ dưới tiêu đề — cách ít xâm lấn nhất (không thêm field JSON). */
function _al_rule_show_description(frm) {
    if (!frm.dashboard || typeof frm.dashboard.set_headline !== "function") return;
    var description = String((frm.doc && frm.doc.rule_description) || "").trim();
    // ⚠ `layout.show_message` APPEND html vào vùng thông báo (không thay thế)
    // ⇒ phải XOÁ trước mỗi lần vẽ, nếu không mô tả cũ sẽ chồng/nằm lại khi
    // quản trị xoá trắng ô Mô tả.
    if (typeof frm.dashboard.clear_headline === "function") {
        frm.dashboard.clear_headline();
    } else {
        frm.dashboard.set_headline("");
    }
    if (!description) return;
    frm.dashboard.set_headline(
        '<div style="font-size:12px;line-height:1.45;">'
        + frappe.utils.escape_html(description) + "</div>"
    );
}

function _al_rule_add_preview_button(frm) {
    frm.add_custom_button(__("Thử tra"), function () {
        // Quy tắc mới chưa lưu ⇒ chưa có gì trong DB để tra.
        if (frm.is_new && frm.is_new()) {
            frappe.msgprint(__("Lưu quy tắc trước rồi bấm Thử tra."));
            return;
        }
        var helper = window.AlumGlassRuleHelper;
        if (!helper || typeof helper.openRulePreview !== "function") {
            frappe.msgprint(__("Chưa nạp được phần hỗ trợ tra cứu. Tải lại trang rồi thử lại."));
            return;
        }
        helper.openRulePreview({
            rule_code: frm.doc.rule_code || frm.doc.name,
            rule_name: frm.doc.rule_name || "",
            // Site chưa migrate ⇒ undefined, hộp thoại tự dùng nhãn chung.
            input_label: frm.doc.input_label || "",
            input_unit: frm.doc.input_unit || "",
            // API đọc bản ĐÃ LƯU trong DB ⇒ nói rõ khi form đang có sửa đổi
            // chưa lưu, kẻo quản trị tưởng đang thử bản vừa sửa.
            draft_dirty: typeof frm.is_dirty === "function" ? !!frm.is_dirty() : false,
        });
    });
}
