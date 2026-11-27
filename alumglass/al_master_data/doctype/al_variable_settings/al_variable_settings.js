// AL Variable Settings — ĐÃ NGỪNG DÙNG từ 2026-11-27 (B2/R3).
//
// Hai bảng con của màn này đã được gộp vào `AL Variable Library`:
//   · common_variables → biến có "Người dùng nhập" (is_input) bật;
//   · row_literals     → biến có Category = "Row Literals".
// `default_profile` / `preview_doctype` chuyển sang `AL Variable Profile`
// (`is_default` / `preview_doctype`).
//
// Tệp này KHÔNG xoá dữ liệu, không chặn Lưu: bảng vật lý còn một chu kỳ để
// lùi. Nó chỉ nói cho người mở đúng chỗ mới — thay vì để họ sửa vào đây rồi
// thắc mắc vì sao danh sách biến không đổi.
frappe.ui.form.on("AL Variable Settings", {
    refresh: function (frm) {
        frm.dashboard.clear_headline();
        frm.dashboard.set_headline(
            __("Màn hình này đã ngừng dùng. Khai biến trong <b>AL Variable Library</b> — "
              + "bật “Người dùng nhập” cho biến người dùng nhập, đặt Category = "
              + "“Row Literals” cho biến theo dòng. Hồ sơ mặc định đặt ở "
              + "<b>AL Variable Profile</b>.")
        );
    },
});
