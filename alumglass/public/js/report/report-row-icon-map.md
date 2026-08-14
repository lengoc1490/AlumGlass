---
title: "Bộ icon & progress bar cho Report (row_icon_map / progress_map)"
feature: EUPAPP-report-agg
tags: [report]
doc_type: other
---

# Bộ icon & progress bar cho Report — row_icon_map / progress_map

Tài liệu tham chiếu bộ icon/badge chuẩn + cách vẽ thanh **progress bar** cho báo cáo
dùng engine **report_agg** (`row_icon_map`, `progress_map`, `icon_styles`, `icon_css`).

- Cách cấu hình đầy đủ: [`../dev/report-aggregation-feature.md`](../dev/report-aggregation-feature.md)
- Cách hoạt động core: [`../dev/report_aggregation_core.md`](../dev/report_aggregation_core.md)

## Nguyên tắc màu sắc (nhớ nhanh)

| Màu | Class | Ý nghĩa |
|---|---|---|
| 🔴 Đỏ | `st-red` | **Lỗi / quá hạn / hủy / từ chối / nguy hiểm** |
| 🟠 Cam | `st-orange` | **Cảnh báo / chờ đợi / một phần / sắp cạn** |
| 🟢 Xanh lá | `st-green` | **Hoàn thành / OK / đã duyệt / đã giao / đã thanh toán** |
| 🔵 Xanh dương | `st-blue` | **Đang xử lý / trung tính / thông tin** |
| 🟣 Tím | `st-purple` | **Đóng / dừng / đặc biệt / bảo trì** |
| 🔘 Viền đỏ | `st-border-red` | **Highlight đặc biệt** (ưu tiên cao, sai lệch, cần chú ý) |

> Các class `st-*` có sẵn từ core — không cần khai báo gì. Muốn thêm màu mới → dùng `icon_styles`.

---

## 1. Trạng thái chung (áp dụng mọi workflow)

```js
row_icon_map: {
    // --- Trạng thái gốc ---
    "Draft":            { cls: "st-blue",   icon: "📝" },   // Nháp
    "Submitted":        { cls: "st-blue",   icon: "📤" },   // Đã gửi / trình duyệt
    "Pending":          { cls: "st-orange", icon: "⏳" },   // Chờ xử lý
    "In Progress":      { cls: "st-blue",   icon: "🔄" },   // Đang xử lý
    "On Hold":          { cls: "st-orange", icon: "⏸️" },  // Tạm hoãn
    "Approved":         { cls: "st-green",  icon: "✅" },   // Đã duyệt
    "Rejected":         { cls: "st-red",    icon: "❌" },   // Từ chối
    "Cancelled":        { cls: "st-red",    icon: "🚫" },   // Đã hủy
    "Completed":        { cls: "st-green",  icon: "✅" },   // Hoàn thành
    "Closed":           { cls: "st-purple", icon: "🔒" },   // Đã đóng
    "Overdue":          { cls: "st-red",    icon: "🚨" },   // Quá hạn
    "Expired":          { cls: "st-red",    icon: "⌛" },   // Hết hạn
},
```

## 2. Bán hàng & Mua hàng (Order / Delivery)

```js
row_icon_map: {
    "To Confirm":       { cls: "st-orange", icon: "🤝" },  // Chờ xác nhận
    "Confirmed":        { cls: "st-green",  icon: "🤝" },  // Đã xác nhận
    "To Deliver":       { cls: "st-blue",   icon: "🚚" },  // Chờ giao
    "Partially Delivered": { cls: "st-orange", icon: "📦" },// Giao một phần
    "Delivered":        { cls: "st-green",  icon: "🚚" },  // Đã giao
    "To Receive":       { cls: "st-blue",   icon: "📥" },  // Chờ nhận
    "Partially Received": { cls: "st-orange", icon: "📦" },// Nhận một phần
    "Received":         { cls: "st-green",  icon: "📥" },  // Đã nhận
    "Not Delivered":    { cls: "st-blue",   icon: "📭" },  // Chưa giao
    "Returned":         { cls: "st-orange", icon: "↩️" },  // Trả hàng
},
```

## 3. Kho (Inventory)

```js
row_icon_map: {
    "In Stock":         { cls: "st-green",  icon: "✅" },  // Còn hàng
    "Low Stock":        { cls: "st-orange", icon: "⚠️" }, // Sắp hết
    "Out of Stock":     { cls: "st-red",    icon: "🚫" },  // Hết hàng
    "Reserved":         { cls: "st-blue",   icon: "📌" },  // Đặt trước
    "Transferred":      { cls: "st-blue",   icon: "🔀" },  // Đã chuyển
    "Obsolete":         { cls: "st-purple", icon: "🗄️" }, // Hàng lỗi thời
},
```

## 4. Tài chính & thanh toán (Finance)

```js
row_icon_map: {
    // --- Hóa đơn ---
    "Not Billed":       { cls: "st-blue",   icon: "📄" },  // Chưa xuất HĐ
    "Partially Billed": { cls: "st-orange", icon: "🧾" },  // HĐ một phần
    "Billed":           { cls: "st-green",  icon: "🧾" },  // Đã xuất HĐ
    // --- Thanh toán ---
    "Unpaid":           { cls: "st-blue",   icon: "⏳" },  // Chưa TT
    "Partially Paid":   { cls: "st-orange", icon: "💰" },  // TT một phần
    "Paid":             { cls: "st-green",  icon: "💳" },  // Đã TT
    "Overdue Payment":  { cls: "st-red",    icon: "🚨" },  // Quá hạn TT
    "Written Off":      { cls: "st-purple", icon: "✂️" },  // Xóa nợ
},
```

## 5. Sản xuất (Manufacturing)

```js
row_icon_map: {
    "Planned":          { cls: "st-blue",   icon: "📅" },  // Kế hoạch
    "In Production":    { cls: "st-blue",   icon: "🏭" },  // Đang SX
    "Completed":        { cls: "st-green",  icon: "✅" },  // Hoàn thành
    "Quality OK":       { cls: "st-green",  icon: "✔️" }, // Đạt QC
    "Quality Failed":   { cls: "st-red",    icon: "❌" },  // Không đạt
    "Stocked":          { cls: "st-green",  icon: "📦" },  // Nhập kho
    "Scrapped":         { cls: "st-red",    icon: "🗑️" }, // Phế phẩm
},
```

## 6. Duyệt & con người (Approval / HR)

```js
row_icon_map: {
    "Pending Approval": { cls: "st-orange", icon: "⏳" },  // Chờ duyệt
    "Approved":         { cls: "st-green",  icon: "✅" },  // Đã duyệt
    "Rejected":         { cls: "st-red",    icon: "❌" },  // Từ chối
    "Active":           { cls: "st-green",  icon: "🟢" },  // Đang hoạt động
    "Inactive":         { cls: "st-purple", icon: "⚫" },  // Không hoạt động
    "On Leave":         { cls: "st-blue",   icon: "🌴" },  // Nghỉ phép
},
```

## 7. Tiến trình (process) mẫu — map trọn vòng đời

| Nghiệp vụ | Chuỗi trạng thái |
|---|---|
| **Đơn bán hàng** | `📝 Draft` → `📤 Submitted` → `🚚 To Deliver` → `✅ Delivered` → `📄 To Bill` → `🧾 Billed` → `🔒 Closed` |
| **Mua hàng** | `📝 Draft` → `📤 Submitted` → `📥 To Receive` → `✅ Received` → `📄 To Bill` → `🧾 Billed` → `🔒 Closed` |
| **Sản xuất** | `📅 Planned` → `🏭 In Production` → `✅ Completed` → `✔️/❌ Quality` → `📦 Stocked` |
| **Duyệt** | `📤 Submitted` → `⏳ Pending` → `✅ Approved / ❌ Rejected` |
| **Thanh toán** | `⏳ Unpaid` → `💰 Partially Paid` → `💳 Paid` / `🚨 Overdue` |

---

## 8. Progress Bar — `progress_map`

Vẽ **thanh tiến độ** cho cột số. Màu **tự động theo %**: `<50%` đỏ, `50–79%` cam, `>=80%` xanh lá
(có thể override bằng `color`).

### Cú pháp

```js
progress_map: {
    // 1) Cột tự chứa % (0-100)
    "ty_le_hoan_thanh": true,

    // 2) Lấy % từ cột khác (0-100)
    "ty_le_hoan_thanh": "field_pct",

    // 3) Tính % từ 2 cột: num / den
    "ty_le_giao": { num: "so_da_giao", den: "so_phai_giao" },

    // 4) Tỷ lệ 0-1 (nhân 100)
    "ty_le_hoan_thanh": { frac: "completion_ratio" },

    // 5) Đầy đủ tùy chọn
    "ty_le_hoan_thanh": {
        num: "so_da_giao",
        den: "so_phai_giao",
        icon: "🚀",              // icon trước thanh (tùy chọn)
        show_percent: true,      // hiện % bên cạnh (mặc định true; đặt false để ẩn)
        color: "#8e44ad",        // override màu (tùy chọn — mặc định tự theo %)
    },
},
```

### Kết hợp icon badge (cột trạng thái) + progress bar (cột %)

Thường gặp nhất: **cột trạng thái** hiện badge, **cột khác** hiện thanh tiến độ — 2 cơ chế độc lập
không xung đột:

```js
row_icon_map: {
    "trang_thai": {
        "Draft":      { cls: "st-blue",   icon: "📝" },
        "Delivered":  { cls: "st-green",  icon: "🚚" },
        "Overdue":    { cls: "st-red",    icon: "🚨" },
    },
},
progress_map: {
    "ty_le_hoan_thanh": { num: "so_da_giao", den: "so_phai_giao", icon: "🚚" },
},
```

> **Lưu ý:** progress bar không áp dụng cho dòng Total (dữ liệu đã tổng hợp).

---

## 9. Ví dụ chi tiết — dùng TẤT CẢ tính năng report_agg

Báo cáo "Tình hình giao hàng & thanh toán theo đơn hàng" — kết hợp: `aggregate_fields`,
`header_groups`, `header_styles`, `header_align`, `bold_header`, `total_row_position`,
`row_icon_map`, `progress_map`, `icon_styles`.

```js
frappe.query_reports["Tình hình giao hàng & thanh toán"] = {
    filters: [
        { fieldname: "from_date", label: __("Từ ngày"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
        { fieldname: "to_date",   label: __("Đến ngày"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
        { fieldname: "khach_hang", label: __("Khách hàng"), fieldtype: "Link", options: "Customer" },
    ],

    // ============ AGGREGATION — dòng Total ============
    aggregate_fields: {
        "gia_tri_don":    "sum",                              // Tổng
        "gia_tri_da_giao": "sum",                             // Tổng
        "gia_tri_da_tt":  "sum",                              // Tổng
        "so_don":         "countA",                           // Đếm cả text
        "ty_le_hoan_thanh": { fn: "averageif", condition_col: "trang_thai", condition: "!Cancelled" },
        // "no_qua_han": { fn: "sumif", condition_col: "trang_thai", condition: "Overdue" },
    },

    // ============ HEADER GROUPS — gom cột ============
    header_groups: [
        { from: "khach_hang",  to: "so_don",             title: "Thông tin đơn hàng" },
        { from: "gia_tri_don", to: "gia_tri_da_giao",    title: "Giá trị & giao hàng" },
        { from: "gia_tri_da_tt", to: "no_qua_han",       title: "Thanh toán" },
    ],

    // ============ HEADER STYLES — tô màu + căn riêng group ============
    header_styles: [
        { from: "khach_hang",  to: "so_don",          bgColor: "#1a5276", textColor: "#ffffff", align: "left" },
        { from: "gia_tri_don", to: "gia_tri_da_giao", bgColor: "#1e8449", textColor: "#ffffff", align: "center" },
        { from: "gia_tri_da_tt", to: "no_qua_han",    bgColor: "#b03a2e", textColor: "#ffffff", align: "center" },
    ],

    // ============ HEADER ALIGN — mọi header cell ============
    header_align: {
        align: "center",                       // default cho mọi header cell
        columns: {
            "khach_hang": "left",              // riêng cột này: trái
            "ma_don":     "left",              // riêng cột này: trái
        },
    },

    // ============ BOLD + TOTAL ROW ============
    bold_header: true,
    total_row_position: "top",                 // 'top' | 'bottom'

    // ============ ROW ICON — badge theo trạng thái ============
    row_icon_map: {
        // Dạng toàn cục — áp mọi cột có giá trị khớp
        "Đã hoàn thành":   { cls: "st-green",  icon: "✅" },
        "Đang xử lý":      { cls: "st-blue",   icon: "🔄" },
        "Quá hạn":         { cls: "st-red",    icon: "🚨" },

        // Dạng theo cột — ưu tiên hơn toàn cục
        "trang_thai": {
            "Draft":          { cls: "st-blue",   icon: "📝" },
            "To Deliver":     { cls: "st-orange", icon: "🚚" },
            "Partially Delivered": { cls: "st-orange", icon: "📦" },
            "Delivered":      { cls: "st-green",  icon: "🚚" },
            "Cancelled":      { cls: "st-red",    icon: "🚫" },
        },
        "tt_thanh_toan": {
            "Unpaid":         { cls: "st-blue",   icon: "⏳" },
            "Partially Paid": { cls: "st-orange", icon: "💰" },
            "Paid":           { cls: "st-green",  icon: "💳" },
            "Overdue Payment":{ cls: "st-red",    icon: "🚨" },
        },
        // Wildcard — bắt mọi biến thể "...Delivered..."
        "*Delivered*": { cls: "st-green", icon: "🚚" },
    },

    // ============ PROGRESS BAR — thanh tiến độ ============
    progress_map: {
        // % hoàn thành = giá trị đã giao / tổng giá trị đơn
        "ty_le_hoan_thanh": {
            num: "gia_tri_da_giao",
            den: "gia_tri_don",
            icon: "🚚",
            show_percent: true,      // mặc định true
        },
        // Cột tự chứa % có sẵn
        "phan_tram_khac": true,
    },

    // ============ CSS BỔ SUNG (tùy chọn) ============
    icon_styles: {
        ".st-gray":   "background:#f0f0f0; color:#666;",   // thêm màu mới
        ".st-red":    "font-weight: 600;",                 // ghi đè class có sẵn
    },
    icon_css: `
        .badge-status { box-shadow: 0 1px 2px rgba(0,0,0,.08); }
        .eup-progress-track { box-shadow: inset 0 1px 2px rgba(0,0,0,.06); }
    `,
};
```

### Kết quả trên giao diện

```
┌────────── Thông tin đơn hàng (trái) ─────────┬── Giá trị & giao hàng ──┬── Thanh toán ──┐
│ Khách hàng   │ Mã đơn │ Số đơn │ Trạng thái   │ GT đơn    │ GT đã giao  │ % hoàn thành  │ Đã TT │
├══════════════╪════════╪════════╪══════════════╪═══════════╪═════════════╪═══════════════╪═══════╡
│  Total: 3    │        │   3    │              │ 125,000,000│ 95,000,000 │ ██████░░░ 76% │   ... │
├──────────────┼────────┼────────┼──────────────┼───────────┼─────────────┼───────────────┼───────┤
│ Cty A        │ SO-001 │   1    │ ✅ Delivered │ 35,000,000│  35,000,000 │ ██████████ 100%│ 💳 Paid│
│ Cty B        │ SO-002 │   1    │ 🚚 To Deliver│ 50,000,000│  20,000,000 │ ████░░░░░░ 40% │ ⏳ Unpaid│
│ Cty C        │ SO-003 │   1    │ 🚨 Overdue   │ 40,000,000│  40,000,000 │ ██████████ 100%│ 🚨 Overdue│
└──────────────┴────────┴────────┴──────────────┴───────────┴─────────────┴───────────────┴───────┘
```

**Giải thích:**
- `header_groups` + `header_styles` + `header_align` căn/tô màu từng nhóm header
- `row_icon_map` biến cột `trang_thai`/`tt_thanh_toan` thành badge màu + icon (có cả wildcard)
- `progress_map` biến cột `ty_le_hoan_thanh` thành thanh tiến độ, màu tự theo % (đỏ <50, cam 50-79, xanh >=80)
- `aggregate_fields` tính dòng Total; `total_row_position: "top"` đưa Total lên đầu
- `bold_header` + `icon_css` hoàn thiện hiển thị

---

## Lưu ý quan trọng khi dùng

1. **Key phải khớp giá trị THẬT của report** — ERPNext thường trả giá trị **tiếng Anh**
   (`"Draft"`, `"Delivered"`). Mở console `frappe.query_report.data[0]` để xem giá trị chính xác.
2. **Wildcard cho giá trị nhiều dạng** — `"*Delivered*"` bắt mọi biến thể `"...Delivered..."`.
3. **2 cột trạng thái khác nhau** → dùng dạng theo cột trong cùng 1 map (xem ví dụ §9).
4. **Muốn màu mới** (vd `st-gray`) → khai báo qua `icon_styles` (xem ví dụ §9).
5. **Đổi config JS xong phải tăng version asset** trong `eupapp/hooks.py`
   (`report_aggregation_core.js?v=...` + `report_agg_dropdown.js?v=...`) rồi **Ctrl+Shift+R**.
