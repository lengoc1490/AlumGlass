// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Đèn báo mã cũ (build beacon)
// ═══════════════════════════════════════════════════════════════════════════
// Nạp ở MỌI trang Desk qua `app_include_js`. Mục đích: khi trình duyệt còn
// giữ `quotation.js` CŨ (Frappe nhúng doctype_js vào form meta rồi cache ở
// Redis; kéo mã mới + restart KHÔNG đủ — phải migrate), người dùng mở dialog
// và thấy hành vi cũ mà không ai biết vì sao. Tệp này so dấu build của bản
// vừa nạp (`alumglass.__build__`, khai trong quotation.js) với bản mong đợi
// dưới đây; lệch ⇒ cảnh báo MỘT lần mỗi phiên.
//
// QUY ƯỚC KHI SỬA quotation.js:
//   nâng `__build__` trong quotation.js VÀ hằng `alumglass_build_expected`
//   dưới đây cùng một lần, rồi bump `?v=` trong hooks.py để trình duyệt nạp
//   lại chính tệp beacon này.
window.alumglass_build_expected = "2026-11-23";

(function () {
    // Chỉ chạy trên trình duyệt Desk (tệp có thể bị nạp nhầm ở môi trường
    // không có `window`, vd test Node).
    if (typeof window === "undefined" || typeof frappe === "undefined") return;
    // Đăng ký handler ĐÚNG MỘT lần: tệp có thể bị nạp lại (giữa các trang,
    // hot reload) — đăng ký lặp sẽ chồng handler và cảnh báo nhiều lần.
    if (window.__al_beacon_bound) return;
    window.__al_beacon_bound = true;

    const SESSION_KEY = "al_build_warned";

    // Đã cảnh báo trong phiên này chưa? `sessionStorage` có thể bị chặn
    // (chế độ riêng tư, chính sách trình duyệt) ⇒ coi như chưa, vẫn cảnh báo.
    const already_warned = () => {
        try { return sessionStorage.getItem(SESSION_KEY) === "1"; } catch (e) { return false; }
    };
    const mark_warned = () => {
        try { sessionStorage.setItem(SESSION_KEY, "1"); } catch (e) { /* ⛔ chặn cảnh báo */ }
    };

    const check_build = () => {
        // Chỉ kiểm khi Frappe đã nạp xong boot (đủ ngữ cảnh, tránh báo nhầm
        // lúc trang còn đang dựng).
        if (!frappe.boot) return;
        const expected = window.alumglass_build_expected;
        const actual = (window.alumglass && window.alumglass.__build__) || undefined;
        if (actual === expected) return;
        if (already_warned()) return;
        mark_warned();
        // Chi tiết cho người vận hành — ⛔ hiện cho người dùng cuối.
        console.warn("[alumglass] giao diện báo giá là bản CŨ",
            { expected: expected, actual: actual });
        if (typeof frappe.show_alert === "function") {
            frappe.show_alert({
                // Câu người-dùng-đọc: ⛔ KHÔNG phơi thuật ngữ vận hành
                // (migrate/cache/DB/version) — chúng nằm ở `console.warn` bên
                // trên, chỉ dành cho người vận hành.
                message: __("Giao diện báo giá chưa phải bản mới nhất. Báo quản trị cập nhật, rồi tải lại trang."),
                indicator: "orange",
            }, 10);
        }
    };

    // ⛔ KHÔNG kiểm lúc nạp: `app_include_js` chạy TRƯỚC `quotation.js` nên
    // `alumglass.__build__` luôn `undefined` ⇒ báo SAI ở mọi trang (kể cả
    // Danh sách Item), và `sessionStorage` đánh dấu "đã cảnh báo" ⇒ khi thật
    // sự mở báo giá bằng mã cũ thì KHÔNG còn cảnh báo. Chỉ kiểm trong
    // `refresh` của form Quotation — lúc đó `quotation.js` chắc chắn đã nạp.
    //
    // Thiếu API form (môi trường không phải Desk form) ⇒ ⛔ đăng ký.
    if (typeof frappe.ui?.form?.on !== "function") return;
    frappe.ui.form.on("Quotation", {
        refresh() { check_build(); },
    });
})();
