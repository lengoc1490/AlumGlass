# Hướng dẫn sử dụng Report Aggregation & Header Styling

## Tổng quan

Hệ thống mở rộng Frappe Report với các tính năng:
- **Aggregation tùy chỉnh**: Thay vì chỉ Sum mặc định, có thể dùng Average, Min, Max, Count, CountA, SUMIF, COUNTIF, AVERAGEIF
- **Header Groups**: Gom nhóm cột theo logic (multi-level header)
- **Header Colors**: Tô màu nền & màu chữ cho header (toàn bộ hoặc từng nhóm)
- **Total Row Position**: Di chuyển dòng Total lên trên hoặc xuống dưới

## Cách hoạt động

### File cốt lõi (đã load sẵn trong toàn bộ hệ thống)
- `/assets/eupapp/js/report/report_aggregation_core.js` — Engine chính
- `/assets/eupapp/js/report/report_agg_dropdown.js` — UI Dialog & Context Menu

### File report (customize cho từng report)
Mỗi report chỉ cần định nghĩa thêm các thuộc tính trong object `frappe.query_reports["Tên Report"]`.

---

## Ví dụ A-Z: Report "Approve Channels Statistics"

### File Python: `approve_channels_statistics.py`

> File này định nghĩa cột, lấy dữ liệu từ database, vẽ chart.  
> Các columns cần có `fieldname` trùng khớp với cấu hình trong JS.

```python
import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    conditions = get_conditions(filters)
    data = get_data(conditions, filters)
    chart = get_chart_data(data, filters)
    return columns, data, None, chart

def get_columns():
    return [
        {"fieldname": "approver", "label": _("Tên người duyệt"), "fieldtype": "Data", "width": 200},
        {"fieldname": "designation", "label": _("Chức danh"), "fieldtype": "Data", "width": 300},
        {"fieldname": "company", "label": _("Company"), "fieldtype": "Link", "options": "Company", "width": 100},
        {"fieldname": "total_docs", "label": _("Tổng số phiếu"), "fieldtype": "Int", "width": 100},
        {"fieldname": "approved_count", "label": _("Số lần duyệt"), "fieldtype": "Int", "width": 100},
        {"fieldname": "rejected_count", "label": _("Số lần từ chối"), "fieldtype": "Int", "width": 100},
        {"fieldname": "pending_count", "label": _("Số phiếu chưa xem"), "fieldtype": "Int", "width": 120},
        {"fieldname": "avg_processing_hours", "label": _("TG xử lý TB (Giờ)"), "fieldtype": "Float", "width": 230},
        {"fieldname": "min_processing_hours", "label": _("TG xử lý nhanh nhất (Giờ)"), "fieldtype": "Float", "width": 230},
        {"fieldname": "max_processing_hours", "label": _("TG xử lý chậm nhất (Giờ)"), "fieldtype": "Float", "width": 230},
    ]

def get_conditions(filters):
    # ... (xem code gốc)
    return conditions

def get_data(conditions, filters):
    # ... (xem code gốc)
    return data

def get_chart_data(data, filters):
    # ... (xem code gốc)
    return chart
```

> **QUAN TRỌNG**: File JSON của report (`approve_channels_statistics.json`) cần có:
> ```json
> {
>   "add_total_row": 1,
>   "report_type": "Script Report",
>   ...
> }
> ```
> `add_total_row: 1` để hiển thị dòng Total.

### File JavaScript: `approve_channels_statistics.js`

> File này định nghĩa filters, aggregate_fields, header_groups, header_styles.

```js
frappe.query_reports["Approve Channels Statistics"] = {
    // === FILTERS (bắt buộc) ===
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
        { fieldname: "start_date", label: __("Start Date"), fieldtype: "Date", default: frappe.datetime.month_start() },
        // ... thêm filter khác
    ],

    // === AGGREGATE FIELDS (tùy chọn) ===
    // Định nghĩa cách tính dòng Total cho từng cột
    aggregate_fields: {
        // Cú pháp đơn giản:
        pending_count:         "none",          // Không tính (bỏ trống)
        avg_processing_hours:  "average",       // Trung bình
        min_processing_hours:  "min",           // Giá trị nhỏ nhất
        max_processing_hours:  "max",           // Giá trị lớn nhất
        total_docs:            "sum",           // Tổng (mặc định)
        approved_count:        "count",         // Đếm số lượng
        rejected_count:        "countA",        // Đếm cả text + số

        // Cú pháp nâng cao (SUMIF/COUNTIF/AVERAGEIF):
        // total_docs: { fn: "sumif", condition_col: "status", condition: "Approved" },
        // approved_count: { fn: "countif", condition_col: "status", condition: "=Approved" },
        // Giá trị condition hỗ trợ: *, ?, >100, <50, !=value, >=10, <=20
    },

    // === HEADER GROUPS (tùy chọn) ===
    // Gom nhóm các cột liên quan dưới 1 tiêu đề chung
    header_groups: [
        { from: "approver", to: "company",              title: "Thông tin chung" },
        { from: "total_docs", to: "pending_count",      title: "Giao dịch" },
        { from: "avg_processing_hours", to: "max_processing_hours", title: "Thời gian xử lý" },
    ],

    // === HEADER STYLES (tùy chọn) ===
    // Tô màu RIÊNG cho từng header group
    header_styles: [
        { from: "approver", to: "company",              bgColor: "#1a5276", textColor: "#ffffff" },
        { from: "total_docs", to: "pending_count",      bgColor: "#1e8449", textColor: "#ffffff" },
        { from: "avg_processing_hours", to: "max_processing_hours", bgColor: "#b03a2e", textColor: "#ffffff" },
    ],

    // === TOÀN BỘ HEADER (tùy chọn, thay thế header_styles) ===
    // Bỏ comment để dùng màu đồng bộ cho tất cả header:
    // header_style: {
    //     bgColor: "#2c3e50",
    //     textColor: "#ffffff"
    // },

    // === TOTAL ROW POSITION (tùy chọn) ===
    total_row_position: 'top',   // 'top' hoặc 'bottom' (mặc định)

    // === BOLD HEADER (tùy chọn) ===
    bold_header: true,
};
```

---

## Chi tiết cấu hình

### 1. `aggregate_fields`

| Giá trị | Ý nghĩa |
|---------|---------|
| `"sum"` | Tổng (mặc định nếu không cấu hình) |
| `"average"` | Trung bình |
| `"avg"` | Tương tự average |
| `"max"` | Giá trị lớn nhất |
| `"min"` | Giá trị nhỏ nhất |
| `"count"` | Đếm số (chỉ số) |
| `"countA"` | Đếm cả text + số |
| `"none"` | Không hiện gì (bỏ trống) |
| `{ fn: "sumif", condition_col: "field", condition: "value" }` | Tính tổng có điều kiện |
| `{ fn: "countif", condition_col: "field", condition: "value" }` | Đếm có điều kiện |
| `{ fn: "averageif", condition_col: "field", condition: "value" }` | Trung bình có điều kiện |

**Condition operators**: `=`, `!=`, `<>`, `>`, `<`, `>=`, `<=`, `*` (wildcard), `?` (single char).

Ví dụ: `condition: ">100"`, `condition: "!=Pending"`, `condition: "*Done*"`

### 2. `header_groups`

Mỗi group có:
- `from`: fieldname của cột đầu tiên trong group
- `to`: fieldname của cột cuối cùng trong group
- `title`: Tiêu đề hiển thị

### 3. `header_styles`

Mỗi style entry có:
- `from` / `to`: Khớp với `header_groups` để xác định group nào được tô màu
- `bgColor`: Màu nền (hex, ví dụ `"#1a5276"`)
- `textColor`: Màu chữ (hex, ví dụ `"#ffffff"`)

> **QUAN TRỌNG**: `from`/`to` trong `header_styles` phải khớp với `header_groups` tương ứng.

---

## Tương tác UI

### Double-click trên dòng Total
Mở dialog chọn hàm aggregation cho cột đó.

### Click chuột phải trên header
- Nếu click vào header group cell (merge cell): mở dialog màu header
- Có thể set màu TOÀN BỘ (global) hoặc RIÊNG cho từng group

### Click chuột phải trên dòng Total
Chuyển dòng Total lên trên / xuống dưới.

---

## Cách debug

Mở Console của browser (F12) và tìm log bắt đầu bằng `[Agg]`:

- `[Agg] QueryReport not ready yet, will retry...` — Đang chờ report.bundle.js load
- `[Agg] QueryReport found, applying patches...` — Đã tìm thấy QueryReport
- `[Agg] prepare_report_data called` — Data đã về từ server
- `[Agg] apply OK: {"total_docs":"sumif",...}` — aggregate_fields đã được áp dụng
- `[Agg] WARN: No agg func applied for...` — KHÔNG tìm thấy aggregate_fields → kiểm tra lại config

## Lưu ý

1. Khi sửa JS, cần bump version trong `hooks.py` (thêm `?v=1.0.x`) và clear browser cache
2. `total_row_position` trong localStorage sẽ override config trong JS
3. Màu sắc (header_styles) lưu tạm trong session, cần refresh trang để reset
4. Nếu `aggregate_fields` không hoạt động, hãy kiểm tra Console > [Agg] log để biết nguyên nhân

## Cấu trúc thư mục

```
apps/eupapp/eupapp/
├── public/js/report/
│   ├── report_aggregation_core.js      # Engine chính
│   └── report_agg_dropdown.js          # UI Dialog + Context Menu
├── hooks.py                            # Khai báo assets
└── docs/dev/
    └── report-aggregation-guide.md     # Tài liệu này
```
