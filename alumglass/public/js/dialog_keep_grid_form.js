// alumglass/public/js/dialog_keep_grid_form.js
// ═══════════════════════════════════════════════════════════════════════════
// GIỮ FORM DÒNG CON MỞ KHI ĐÓNG HỘP THOẠI — Frappe v16
// ═══════════════════════════════════════════════════════════════════════════
//
// VẤN ĐỀ (Owner 2026-11-26)
// -------------------------
// Mở một dòng bảng con (AL Bom Item, AL Accessory Item…) ⇒ hiện form dòng.
// Trong form dòng mở hộp tra cứu (Chọn công thức / Thử tra quy tắc / Vì sao
// ra số này? …). Đóng hộp tra cứu ⇒ **form dòng cũng bị đóng luôn**.
//
// NGUYÊN NHÂN — ĐÃ ĐỌC MÃ NGUỒN, ⛔ KHÔNG ĐOÁN
// --------------------------------------------
// Frappe **v16** `frappe/public/js/frappe/ui/dialog.js` (nhánh `version-16`),
// handler `hide.bs.modal`:
//
//     if (!me.keep_grid_form_open) {
//         frappe.ui.form.get_open_grid_form?.()?.hide_form();
//     }
//
// `keep_grid_form_open` mặc định `false` ⇒ hễ đóng hộp là đóng form dòng đang
// mở, dù hộp đó chẳng liên quan gì tới việc đóng dòng.
//
// CÁCH XỬ LÝ — MỘT CHỖ CHO TOÀN APP
// ---------------------------------
// Bọc `frappe.ui.Dialog` MỘT LẦN: mọi hộp thoại tạo sau thời điểm này tự có
// `keep_grid_form_open: true`, ⛔ phải thêm cờ vào từng `new frappe.ui.Dialog`
// ở từng doctype (dễ sót, sót là im lặng).
//
//   · Nơi nào CỐ Ý muốn đóng form dòng khi đóng hộp ⇒ truyền
//     `keep_grid_form_open: false` — tệp này ⛔ ghi đè lựa chọn tường minh.
//   · Frappe **v14** không có cờ này: `$.extend(this, {...}, opts)` nhận thêm
//     khoá lạ rồi bỏ qua ⇒ thêm cờ VÔ HẠI, chạy được cả 2 phiên bản.
//   · Tắt toàn bộ: `delete frappe.ui.Dialog.__alKeepGridForm` rồi nạp lại
//     trang (hoặc đặt lại `frappe.ui.Dialog` bản gốc) — chỉ dùng khi gỡ lỗi.
//
// Nạp qua `app_include_js` trong `hooks.py`, đặt ĐẦU danh sách để chắc chắn
// chạy TRƯỚC mọi JS tạo hộp thoại (kể cả script của app khác).
//
// Test: node alumglass/tests/js/test_dialog_keep_grid_form.js
// ═══════════════════════════════════════════════════════════════════════════

(function () {
    "use strict";

    // Trang ngoài Desk (portal/in print) không có `frappe.ui` ⇒ bỏ qua, ⛔ lỗi.
    if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.Dialog) return;

    var Original = frappe.ui.Dialog;

    // IDEMPOTENT: asset có thể nạp 2 lần (đổi trang trong SPA, cache tải lại).
    // Bọc chồng nhiều lớp vẫn cho ra cờ đúng nhưng làm `instanceof`/gỡ lỗi
    // rối, nên đánh dấu trên chính class và thoát nếu đã bọc rồi.
    if (Original.__alKeepGridForm) return;

    class AlumGlassDialog extends Original {
        constructor(opts) {
            // Sao chép opts rồi mới thêm mặc định — ⛔ sửa object của nơi gọi
            // (cùng một opts có thể được dùng lại cho hộp khác).
            var next = Object.assign({}, opts || {});
            // Chỉ điền khi nơi gọi KHÔNG nói gì. `false` là lựa chọn tường
            // minh "đóng hộp thì đóng luôn form dòng" ⇒ giữ nguyên.
            if (next.keep_grid_form_open === undefined) {
                next.keep_grid_form_open = true;
            }
            super(next);
        }
    }

    AlumGlassDialog.__alKeepGridForm = true;
    frappe.ui.Dialog = AlumGlassDialog;
})();
