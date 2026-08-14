# Hướng dẫn sử dụng Report Aggregation - Từ A đến Z

## Tổng quan

Hệ thống cho phép bạn tùy chỉnh cách tính dòng Total trong các report Frappe, thay vì chỉ Sum mặc định.   
Bạn cũng có thể gom nhóm cột, tô màu header, và di chuyển dòng Total.

### Các tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| **Aggregation tùy chỉnh** | Chọn hàm tính cho từng cột: Sum, Average, Min, Max, Count, CountA |
| **Sumif/Countif/Averageif** | Tính có điều kiện (giống Excel) |
| **Header Groups** | Gộp nhiều cột dưới 1 tiêu đề chung |
| **Header Colors** | Tô màu nền + màu chữ cho header |
| **Header Alignment** | Căn trái/giữa/phải cho header — cả merge cell lẫn cột riêng lẻ |
| **Row Icon Formatting** | Format icon/badge theo giá trị từng dòng dữ liệu — chỉ cần config, không viết code |
| **Progress Bar** | Vẽ thanh tiến độ cho cột số, màu tự động theo % — chỉ cần config |
| **Total Row Position** | Chuyển dòng Total lên trên hoặc xuống dưới |

---

## Cách dùng nhanh (3 bước)

### Bước 1: Khai báo trong file JS của report

Mở file `.../report/<tên_report>/<tên_report>.js`.

Ví dụ với report "Approve Channels Statistics":
```js
frappe.query_reports["Approve Channels Statistics"] = {
    filters: [
        // ... filters của bạn
    ],

    // === QUAN TRỌNG: khai báo aggregate_fields ===
    aggregate_fields: {
        // Cú pháp đơn giản: "tên_hàm"
        avg_processing_hours:  "average",    // Trung bình
        min_processing_hours:  "min",        // Nhỏ nhất
        max_processing_hours:  "max",        // Lớn nhất
        pending_count:         "none",       // Bỏ trống (không tính)
        approved_count:        "count",      // Đếm số
        rejected_count:        "countA",     // Đếm cả text và số
        total_docs:            "sum",        // Tổng (mặc định)

        // Cú pháp nâng cao: SUMIF / COUNTIF / AVERAGEIF
        // total_docs: { fn: "sumif", condition_col: "approver", condition: "Nguyễn Văn A" },
        // approved_count: { fn: "countif", condition_col: "status", condition: "Đã đồng ý" },
    },

    // === TÙY CHỌN: Gom nhóm cột ===
    header_groups: [
        { from: "approver", to: "company",              title: "Thông tin chung" },
        { from: "total_docs", to: "pending_count",      title: "Giao dịch" },
        { from: "avg_processing_hours", to: "max_processing_hours", title: "Thời gian xử lý" },
    ],

    // === TÙY CHỌN: Tô màu header ===
    header_styles: [
        { from: "approver", to: "company",              bgColor: "#1a5276", textColor: "#ffffff" },
        { from: "total_docs", to: "pending_count",      bgColor: "#1e8449", textColor: "#ffffff" },
        { from: "avg_processing_hours", to: "max_processing_hours", bgColor: "#b03a2e", textColor: "#ffffff" },
    ],

    // === TÙY CHỌN: Dòng Total lên trên ===
    total_row_position: 'top',

    // === TÙY CHỌN: In đậm header ===
    bold_header: true,
};
```

### Bước 2: Kiểm tra file JSON của report

Mở `.../report/<tên_report>/<tên_report>.json`, đảm bảo có:
```json
{
    "add_total_row": 1,
    "report_type": "Script Report"
}
```

> `add_total_row: 1` là bắt buộc để hiển thị dòng Total.

### Bước 3: Refresh và xem kết quả

- Ctrl+Shift+R (hard refresh)
- Chạy report

---

## Ví dụ cụ thể

### Ví dụ 1: Report thống kê đơn hàng

File Python `sales_order_report.py`:
```python
def get_columns():
    return [
        {"fieldname": "sales_person", "label": "Người bán", "fieldtype": "Data", "width": 150},
        {"fieldname": "branch", "label": "Chi nhánh", "fieldtype": "Data", "width": 120},
        {"fieldname": "total_orders", "label": "Tổng đơn", "fieldtype": "Int", "width": 100},
        {"fieldname": "completed", "label": "Đã giao", "fieldtype": "Int", "width": 100},
        {"fieldname": "pending", "label": "Chưa giao", "fieldtype": "Int", "width": 100},
        {"fieldname": "revenue", "label": "Doanh thu", "fieldtype": "Currency", "width": 150},
        {"fieldname": "avg_order_value", "label": "TB đơn", "fieldtype": "Currency", "width": 120},
    ]
```

File JS `sales_order_report.js`:
```js
frappe.query_reports["Sales Order Report"] = {
    filters: [ /* ... */ ],
    aggregate_fields: {
        total_orders:     "sum",
        completed:        "count",
        pending:          "none",
        revenue:          "sum",
        avg_order_value:  "average",
    },
    header_groups: [
        { from: "sales_person", to: "branch",         title: "Nhân viên" },
        { from: "total_orders", to: "pending",         title: "Đơn hàng" },
        { from: "revenue", to: "avg_order_value",     title: "Doanh thu" },
    ],
    header_styles: [
        { from: "sales_person", to: "branch",         bgColor: "#2c3e50", textColor: "#ffffff" },
        { from: "total_orders", to: "pending",         bgColor: "#27ae60", textColor: "#ffffff" },
        { from: "revenue", to: "avg_order_value",     bgColor: "#8e44ad", textColor: "#ffffff" },
    ],

    // === TOÀN BỘ HEADER (tùy chọn, thay thế header_styles) ===
    // Bỏ comment để dùng màu đồng bộ cho tất cả header:
    // header_style: {
    //     bgColor: "#2c3e50",
    //     textColor: "#ffffff"
    // },

    total_row_position: 'top',
    bold_header: true,
};
```

### Ví dụ 2: Dùng SUMIF

Chỉ tính tổng doanh thu cho nhân viên thuộc chi nhánh "Hà Nội":
```js
aggregate_fields: {
    revenue: { fn: "sumif", condition_col: "branch", condition: "Hà Nội" },

	gia_tri_nhap_kho: { fn: "sumif", condition_col: "voucher_no", condition: "Cộng" },
}
```

> **Lưu ý**: `condition_col` phải trỏ vào cột **text** (Data, Link, Select), không phải cột số.

### Ví dụ 3: Dùng COUNTIF

Đếm số nhân viên có tổng đơn > 10:
```js
aggregate_fields: {
    sales_person: { fn: "countif", condition_col: "total_orders", condition: ">10" },
}
```

### Ví dụ 4: Dùng AVERAGEIF

Trung bình doanh thu cho các đơn đã giao:
```js
aggregate_fields: {
    revenue: { fn: "averageif", condition_col: "completed", condition: ">0" },
}
```

---

## Tương tác UI

### Double-click trên dòng Total
Mở dialog chọn hàm tính cho cột đó (lưu vào localStorage, tồn tại khi refresh).

### Click phải trên header
- **Trên header group (merge cell)**: Mở dialog tô màu
- **Trên cột riêng lẻ**: Cũng mở dialog, nhưng màu được gán theo group chứa cột đó

### Click phải trên dòng Total
Chuyển dòng Total lên trên / xuống dưới.

---

## Các giá trị `aggregate_fields`

| Giá trị | Hàm | Mô tả |
|---------|-----|-------|
| `"sum"` | SUM | Tổng (mặc định) |
| `"average"` / `"avg"` | AVERAGE | Trung bình |
| `"max"` | MAX | Giá trị lớn nhất |
| `"min"` | MIN | Giá trị nhỏ nhất |
| `"count"` | COUNT | Đếm số (chỉ số) |
| `"countA"` | COUNTA | Đếm cả text + số |
| `"none"` | — | Bỏ trống dòng Total |

### Cú pháp SUMIF / COUNTIF / AVERAGEIF

```js
{ fn: "sumif", condition_col: "<cột>", condition: "<điều kiện>" }
{ fn: "countif", condition_col: "<cột>", condition: "<điều kiện>" }
{ fn: "averageif", condition_col: "<cột>", condition: "<điều kiện>" }
```

### Các toán tử cho condition

| Toán tử | Ví dụ | Ý nghĩa |
|---------|-------|---------|
| `=` | `"=Done"` | Bằng (mặc định, có thể bỏ `=`) |
| `!=` hoặc `<>` | `"!=Pending"` | Khác |
| `>` | `">100"` | Lớn hơn |
| `<` | `"<50"` | Nhỏ hơn |
| `>=` | `">=10"` | Lớn hơn hoặc bằng |
| `<=` | `"<=20"` | Nhỏ hơn hoặc bằng |
| `*` | `"*Admin*"` | Chứa chuỗi (wildcard) |
| `?` | `"A?"` | 1 ký tự bất kỳ |

Ví dụ: `condition: ">100"`, `condition: "!=Pending"`, `condition: "*Done*"`
---

### header_groups

Mỗi group có:
- `from`: fieldname của cột đầu tiên trong group
- `to`: fieldname của cột cuối cùng trong group
- `title`: Tiêu đề hiển thị

### header_styles

Mỗi style entry có:
- `from` / `to`: Khớp với `header_groups` để xác định group nào được tô màu
- `bgColor`: Màu nền (hex, ví dụ `"#1a5276"`)
- `textColor`: Màu chữ (hex, ví dụ `"#ffffff"`)


> **QUAN TRỌNG**: `from`/`to` trong `header_styles` phải khớp với `header_groups` tương ứng.

---

## Header Alignment (căn chỉnh header cell)

Căn chỉnh text trong header — áp dụng cho cả **merge cell** (`header_groups`) lẫn **cột riêng lẻ** (base cell). Không ảnh hưởng đến text trong body.

### Cú pháp đơn giản

```js
header_align: 'center',   // 'left' | 'center' | 'right' — áp dụng cho mọi header cell
```

### Cú pháp nâng cao — default + theo cột

```js
header_align: {
    align: 'center',            // default cho mọi header cell
    columns: {
        "ma_hang":  'left',     // riêng cột này: trái
        "so_luong": 'right',    // riêng cột này: phải
    },
},
```

### Kết hợp với header_styles (align riêng cho group)

Thêm `align` vào entry `header_styles` đã có — áp dụng cho toàn bộ group đó:

```js
header_styles: [
    { from: "total_docs", to: "pending_count", bgColor: "#1e8449", textColor: "#ffffff", align: 'center' },
],
```

### Thứ tự ưu tiên (cao → thấp)

1. `header_align.columns[fieldname]` — căn riêng theo từng cột
2. `header_styles[i].align` — căn riêng cho group chứa cột đó
3. `header_align` global (string hoặc `{ align: ... }`)

> Các cột không khai báo: **giữ nguyên hành vi cũ** — merge/filler cell mặc định `center`, base cell mặc định theo datatable (không bị override).

---

## Row Icon Formatting (format icon/badge theo từng dòng)

Format icon/badge theo **giá trị** của từng dòng dữ liệu — giống các report mẫu
`báo_cáo_tồn_đọng_hoạt_động_*`. Khác biệt: **chỉ cần khai báo config trong JS**, core
tự wrap formatter + inject CSS — **không phải viết formatter / `<style>` thủ công**.

### Cú pháp

```js
row_icon_map: {
    // Dạng toàn cục: giá trị khớp → badge (áp dụng mọi cột)
    "Đã hoàn thành":  { cls: "st-green",  icon: "✅" },
    "Đang xử lý":     { cls: "st-orange", icon: "🔄" },

    // Dạng theo cột: fieldname → map giá trị (ưu tiên hơn toàn cục)
    "trang_thai": {
        "Draft":      { cls: "st-purple", icon: "📄" },
        "Cancelled":  { cls: "st-red",    icon: "❌" },
    },
},
```

- `cls`: class CSS của badge (class có sẵn hoặc tự định nghĩa qua `icon_styles`)
- `icon`: emoji/icon hiển thị **trước** giá trị (tùy chọn)
- Key hỗ trợ **wildcard**: `"*Đã hoàn*"` (chứa chuỗi), `"Done?"` (1 ký tự bất kỳ)
- Có thể trộn lẫn dạng toàn cục và dạng theo cột trong cùng một map

### Class badge có sẵn (core inject tự động 1 lần)

| Class | Ý nghĩa |
|-------|---------|
| `st-red` | nền đỏ nhạt, chữ đỏ |
| `st-orange` | nền cam nhạt, chữ cam |
| `st-green` | nền xanh lá nhạt, chữ xanh lá |
| `st-blue` | nền xanh dương nhạt, chữ xanh dương |
| `st-purple` | nền tím nhạt, chữ tím |
| `st-border-red` | viền đỏ, chữ đỏ, nền trong suốt |

### CSS bổ sung (tùy chọn)

```js
icon_styles: {
    ".st-custom": "background:#fff; color:#111; border:1px solid #ccc;",
    ".st-red":    "font-weight:600;",     // ghi đè / bổ sung class có sẵn
},
icon_css: `
    .badge-status.st-custom { border-radius: 3px; }
`,
```

> `icon_styles` = object `{ selector: "css..." }`; `icon_css` = raw CSS string. Cả 2 đều **tùy chọn** — nếu bỏ thì chỉ dùng class có sẵn.

### Ví dụ hoàn chỉnh

```js
frappe.query_reports["Báo cáo tồn đọng hoạt động bán hàng"] = {
    filters: [ /* ... */ ],
    aggregate_fields: { /* ... */ },
    header_groups: [ /* ... */ ],
    header_styles: [ /* ... */ ],
    bold_header: true,
    total_row_position: 'top',

    row_icon_map: {
        "Đã hoàn thành":   { cls: "st-green",  icon: "✅" },
        "Đang xử lý":      { cls: "st-orange", icon: "🔄" },
        "Quá hạn":         { cls: "st-red",    icon: "❌" },
        "Không hoạt động": { cls: "st-purple", icon: "🚫" },
    },
};
```

> Không cần viết `formatter` hay inject `<style>` — core tự làm. Nếu report ĐÃ có `formatter` riêng, core wrap bên ngoài formatter cũ, không ghi đè.

---

## Progress Bar (thanh tiến độ)

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

### Kết hợp với row_icon_map

Cột **trạng thái** hiện badge (qua `row_icon_map`), cột **%** hiện thanh tiến độ (qua
`progress_map`) — 2 cơ chế độc lập, có thể dùng cùng lúc:

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

## Tham chiếu bộ icon & progress

Bộ icon/badge chuẩn theo nghiệp vụ + ví dụ tổng hợp dùng **tất cả** tính năng report_agg
xem tại: [`../usage/report-row-icon-map.md`](../usage/report-row-icon-map.md).

---

## Cấu trúc file

```
apps/<app>/<app>/
├── public/js/report/
│   ├── report_aggregation_core.js      # Engine chính (đã load sẵn)
│   └── report_agg_dropdown.js          # UI Dialog (đã load sẵn)
├── hooks.py                            # Khai báo assets
└── <module>/report/<report_name>/
    ├── <report_name>.py                # Code Python
    ├── <report_name>.js                # Config JS (sửa ở đây)
    └── <report_name>.json              # Config
```

### Các lỗi thường gặp

1. **Không có log `[Agg]` nào** → patch chưa kịp chạy → Ctrl+Shift+R lại
2. **Log "source=NONE"** → `aggregate_fields` không tồn tại trong JS → kiểm tra lại file .js
3. **Log "NOT SET" cho tất cả cột** → `aggregate_fields` không match fieldname → kiểm tra tên cột
4. **SUMIF ra 0** → condition sai hoặc không có row nào match → kiểm tra `condition_col` và `condition`
5. **"none" vẫn hiện số** → `aggregate_function` chưa được set → kiểm tra log

### Xóa localStorage nếu cần

Nếu trước đó bạn double-click để set công thức, giá trị lưu trong localStorage sẽ đè lên config JS. Xóa bằng:
```js
Object.keys(localStorage).filter(k => k.startsWith('eup_report_agg:')).forEach(k => localStorage.removeItem(k));
```