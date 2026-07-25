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
    total_row_position: 'top',
    bold_header: true,
};
```

### Ví dụ 2: Dùng SUMIF

Chỉ tính tổng doanh thu cho nhân viên thuộc chi nhánh "Hà Nội":
```js
aggregate_fields: {
    revenue: { fn: "sumif", condition_col: "branch", condition: "Hà Nội" },
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

## Debug

Mở Console (F12) và lọc log `[Agg]`:

| Log | Ý nghĩa |
|-----|---------|
| `[Agg] QueryReport found, applying patches...` | Patch thành công |
| `[Agg] applySettingsToColumns report=...` | Đang áp dụng config |
| `[Agg] col=total_docs from aggFields: ...` | Cột được set config |
| `[Agg] col=total_docs NOT SET` | Cột KHÔNG có config |
| `[Agg] source=NONE` | Không tìm thấy aggregate_fields |
| `[Agg] sumif field=... cond_col=...` | SUMIF đang chạy |
| `[Agg] sumif result=...` | Kết quả SUMIF |

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


// Copyright (c) 2025, EuP and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Approve Channels Statistics"] = {
	filters: [
		{
			fieldname: "requester",
			label: __("Requester"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "MultiSelectList",
			get_data: function() {
				let company = frappe.query_report.get_filter_value('company');
				let query_filters = {};
				if (company) query_filters["company"] = company;
				return frappe.db.get_list("Department", {
					filters: query_filters, fields: ["name"], limit: 0, as_list: 1
				}).then(data => data.filter(d => d[0]).map(d => ({ value: d[0], description: d[0] })));
			}
		},
		{
			fieldname: "doc_type",
			label: __("Document Type"),
			fieldtype: "MultiSelectList",
			get_data: function () {
				return frappe.db.get_list('Approve Channels', {
					fields: ['origin_doc'], distinct: true, limit: 0
				}).then(rows => rows.filter(r => r.origin_doc).map(r => ({ value: r.origin_doc, description: r.origin_doc })));
			}
		},
		{
			fieldname: "start_date", label: __("Start Date"), fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "end_date", label: __("End Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{ fieldname: "records", label: __("Records"), fieldtype: "Int", default: 20 },
		{
			fieldname: "filter", label: __("Filter"), fieldtype: "Select",
			options: ["Thoi gian xu ly", "So phieu chua xem xet"],
			default: "Thoi gian xu ly",
		}
	],
	"onload": function() {
		const style = document.createElement('style');
		style.innerHTML = `
			.chart-container svg g g.x.axis { padding-bottom: 50px }
			.chart-container svg g g.x.axis g text {
				transform: rotate(328deg) !important;
				translate: -130px 40px !important;
				font-size: 11px !important;
			}
		`;
		document.head.appendChild(style);
	},
	aggregate_fields: {
		total_docs: { fn: "sumif", condition_col: "company", condition: "Elog" },
		rejected_count: "average",
		pending_count:         "none",
		avg_processing_hours:  "average",
		min_processing_hours:  "min",
		max_processing_hours:  "max",
		// Ví dụ SUMIF (cần condition_col trỏ vào cột TEXT, không phải cột số):
		// total_docs: { fn: "sumif", condition_col: "approver", condition: "Nguyễn Văn A" },
	},
	// === Màu nền + chữ cho TOÀN BỘ header cells ===
	// header_style: {
	// 	bgColor: "#2c3e50",
	// 	textColor: "#ffffff"
	// },
	// === Màu nền + chữ RIÊNG cho từng header group ===
	header_styles: [
		{ from: "approver", to: "company",              bgColor: "#1a5276", textColor: "#ffffff" },
		{ from: "total_docs", to: "pending_count",      bgColor: "#1e8449", textColor: "#ffffff" },
		{ from: "avg_processing_hours", to: "max_processing_hours", bgColor: "#b03a2e", textColor: "#ffffff" }
	],
	header_groups: [
		{ from: "approver", to: "company", title: "Thông tin chung" },
		{ from: "total_docs", to: "pending_count", title: "Giao dịch" },
		{ from: "avg_processing_hours", to: "max_processing_hours", title: "Thời gian xử lý" }
	],
	total_row_position: 'top',
	bold_header: true,
};