# Tính năng Aggregation & Header Groups cho Report

> Áp dụng CHO TOÀN BỘ HỆ THỐNG — Query Reports + Report Builder.

## Mục lục

1. [Tổng quan](#1-t%E1%BB%95ng-quan)
2. [Các file liên quan](#2-c%C3%A1c-file-li%C3%AAn-quan)
3. [Cấu hình report (từ A-Z)](#3-c%E1%BA%A5u-h%C3%ACnh-report-t%E1%BB%AB-a-z)
   - [3.1. Bước 1: Tạo JavaScript Report](#31-b%C6%B0%E1%BB%9Bc-1-t%E1%BA%A1o-javascript-report)
   - [3.2. Bước 2: Định nghĩa aggregate_fields](#32-b%C6%B0%E1%BB%9Bc-2-%C4%91%E1%BB%8Bnh-ngh%C4%A9a-aggregatefields)
   - [3.3. Bước 3: Định nghĩa header_groups](#33-b%C6%B0%E1%BB%9Bc-3-%C4%91%E1%BB%8Bnh-ngh%C4%A9a-headergroups)
   - [3.4. Bước 4: Cấu hình total_row_position](#34-b%C6%B0%E1%BB%9Bc-4-c%E1%BA%A5u-h%C3%ACnh-totalrowposition)
   - [3.5. Bước 5: Bật bold_header](#35-b%C6%B0%E1%BB%9Bc-5-b%E1%BA%ADt-boldheader)
   - [3.6. Bước 6: Căn chỉnh header (header_align)](#36-b%C6%B0%E1%BB%9Bc-6-c%C4%83n-ch%E1%BB%89nh-header-headeralign)
   - [3.7. Bước 7: Format icon/badge từng dòng (row_icon_map)](#37-b%C6%B0%E1%BB%9Bc-7-format-iconbadge-t%E1%BB%ABng-d%C3%B2ng-rowiconmap)
   - [3.8. Bước 8: Thanh tiến độ (progress_map)](#38-b%C6%B0%E1%BB%9Bc-8-thanh-ti%E1%BA%BFn-%C4%91%E1%BB%99-progressmap)
4. [Hàm aggregation chi tiết](#4-h%C3%A0m-aggregation-chi-ti%E1%BA%BFt)
5. [Hàm có điều kiện (SUMIF / COUNTIF / AVERAGEIF)](#5-h%C3%A0m-c%C3%B3-%C4%91i%E1%BB%81u-ki%E1%BB%87n-sumif--countif--averageif)
6. [Cách sử dụng trên giao diện](#6-c%C3%A1ch-s%E1%BB%AD-d%E1%BB%A5ng-tr%C3%AAn-giao-di%E1%BB%87n)
   - [6.1. Double-click để đổi hàm aggregation](#61-double-click-%C4%91%E1%BB%83-%C4%91%E1%BB%95i-h%C3%A0m-aggregation)
   - [6.2. Click chuột phải để di chuyển dòng Total](#62-click-chu%E1%BB%99t-ph%E1%BA%A3i-%C4%91%E1%BB%83-di-chuy%E1%BB%83n-d%C3%B2ng-total)
   - [6.3. Export Excel với Header Groups & Bold](#63-export-excel-v%E1%BB%9Bi-header-groups--bold)
7. [Ví dụ hoàn chỉnh: Báo cáo Doanh thu theo khu vực](#7-v%C3%AD-d%E1%BB%A5-ho%C3%A0n-ch%E1%BB%89nh-b%C3%A1o-c%C3%A1o-doanh-thu-theo-khu-v%E1%BB%B1c)
8. [Ví dụ hoàn chỉnh: Báo cáo Nhập-Xuất-Tồn](#8-v%C3%AD-d%E1%BB%A5-ho%C3%A0n-ch%E1%BB%89nh-b%C3%A1o-c%C3%A1o-nh%E1%BA%ADp-xu%E1%BA%A5t-t%E1%BB%93n)
9. [Ví dụ hoàn chỉnh: Báo cáo có badge/icon + căn chỉnh header](#9-v%C3%AD-d%E1%BB%A5-ho%C3%A0n-ch%E1%BB%89nh-b%C3%A1o-c%C3%A1o-c%C3%B3-badgeicon--c%C4%83n-ch%E1%BB%89nh-header)
10. [Cấu hình nâng cao](#10-c%E1%BA%A5u-h%C3%ACnh-n%C3%A2ng-cao)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Tổng quan

Bộ script này mở rộng Frappe Report Total Row — giống Excel:

- **Click vào ô trên dòng Total** (double-click) để chọn hàm aggregation: sum, average, max, min, count, countA, sumif, countif, averageif
- **Click chuột phải** trên dòng Total để di chuyển nó lên trên / xuống dưới
- **Header Groups**: merge nhiều cột thành một nhóm kiểu Excel (multi-level header)
- **Bold Header**: bật/tắt in đậm cho toàn bộ header (cả merge cell)
- **Header Alignment**: căn trái/giữa/phải cho header — cả merge cell lẫn cột riêng lẻ
- **Row Icon Formatting**: format icon/badge theo giá trị từng dòng dữ liệu — chỉ cần config JS, không viết formatter/CSS thủ công
- **Progress Bar**: thanh tiến độ cho cột số, màu tự động theo %, chỉ cần config JS
- **Export Excel** giữ nguyên header groups và định dạng bold

Yêu cầu: Frappe >= v14+ (hỗ trợ DataTable mới).

## 2. Các file liên quan

| File | Vai trò |
|------|---------|
| `eupapp/public/js/report/report_aggregation_core.js` | Core engine: hàm tính, parse config, override DataTable hooks, header groups rendering, export Excel |
| `eupapp/public/js/report/report_agg_dropdown.js` | UI Dialog + Context Menu: double-click để chọn hàm, chuột phải để di chuyển Total row |

Cả 2 file cần được load trong `eupapp/public/js/report/eup_reports.js` (hoặc file entry point tương tự):

```js
frappe.provide('frappe.EUP_REPORT_AGG');

// Load core engine trước
frappe.require('eupapp/public/js/report/report_aggregation_core.js');

// Load UI dialog sau
frappe.require('eupapp/public/js/report/report_agg_dropdown.js');
```

## 3. Cấu hình report (từ A-Z)

### 3.1. Bước 1: Tạo JavaScript Report

Tạo một Query Report (JavaScript) trong Frappe:

```js
// eupapp/eupapp/report/doanh_thu_khu_vuc/doanh_thu_khu_vuc.js

frappe.query_reports["Doanh thu theo khu vuc"] = {
    // --- Cấu hình aggregation core ---
    aggregate_fields: { /* xem bước 2 */ },
    header_groups:    [ /* xem bước 3 */ ],
    total_row_position: 'bottom',  // hoặc 'top'
    bold_header: true,             // true: in đậm header + merge cell

    // --- Cấu hình Frappe chuẩn ---
    filters: [ ... ],
    onload: function(report) { ... }
};
```

### 3.2. Bước 2: Định nghĩa aggregate_fields

**Cú pháp — Hàm đơn** (áp dụng cho tất cả dữ liệu của cột đó):

```js
aggregate_fields: {
    "fieldname1": "sum",           // Tổng
    "fieldname2": "average",       // Trung bình
    "fieldname3": "max",           // Giá trị lớn nhất
    "fieldname4": "min",           // Giá trị nhỏ nhất
    "fieldname5": "count",         // Đếm số (chỉ số, như COUNT trong Excel)
    "fieldname6": "countA",        // Đếm tất cả (kể cả text, như COUNTA trong Excel)
    "fieldname7": "none"           // Không hiện Total (ô trống)
}
```

**Cú pháp — Hàm có điều kiện** (SUMIF / COUNTIF / AVERAGEIF):

```js
aggregate_fields: {
    "fieldname1": {
        fn: "sumif",
        condition_col: "status",        // Cột dùng để kiểm tra điều kiện
        condition: "Done"               // Giá trị điều kiện
    }
}
```

> **Lưu ý quan trọng:** Cột `condition_col` PHẢI nằm trong data mà server trả về (trong mỗi row của report), nếu không sẽ không có dữ liệu để lọc.

### 3.3. Bước 3: Định nghĩa header_groups

Tạo các merge cell ở header — gom nhiều cột dưới một tiêu đề chung:

```js
header_groups: [
    { from: "col_fieldname_1",  to: "col_fieldname_3",  title: "Thong tin co ban" },
    { from: "col_fieldname_4",  to: "col_fieldname_7",  title: "Chi tiet giao dich" },
    { from: "col_fieldname_8",  to: "col_fieldname_10", title: "Tong quan" }
]
```

- `from`: fieldname của cột đầu tiên trong nhóm
- `to`: fieldname của cột cuối cùng trong nhóm
- `title`: tiêu đề hiển thị (tự động translate qua `frappe._()`)

**Các cột không nằm trong bất kỳ group nào** sẽ giữ nguyên label gốc và được kéo dài full height (ô merge overlay với core header cell).

### 3.4. Bước 4: Cấu hình total_row_position

```js
total_row_position: 'bottom'   // Mặc định: Total ở dưới cùng
total_row_position: 'top'      // Total ở ngay dưới header
```

Người dùng có thể thay đổi tạm thời bằng **click chuột phải** vào dòng Total. Lựa chọn này được **lưu vào localStorage** theo user + report.

### 3.5. Bước 5: Bật bold_header

```js
bold_header: true    // Header và merge cell in đậm (font-weight: 600)
bold_header: false   // Header và merge cell không in đậm
```

Hoặc không khai báo (mặc định là `false`). Khi xuất Excel, nếu `bold_header = true` thì toàn bộ dòng header (cả group và column labels) đều được in đậm.

### 3.6. Bước 6: Căn chỉnh header (`header_align`)

Căn chỉnh text trong header — áp dụng cho **cả merge cell** (`header_groups`) lẫn **cột riêng lẻ** (base cell). Không ảnh hưởng đến text trong body.

**Cú pháp đơn giản** — áp dụng cho mọi header cell:

```js
header_align: 'center',   // 'left' | 'center' | 'right'
```

**Cú pháp nâng cao** — default + căn riêng từng cột:

```js
header_align: {
    align: 'center',            // default cho mọi header cell
    columns: {
        "ma_hang":  'left',     // riêng cột ma_hang: trái
        "so_luong": 'right',    // riêng cột so_luong: phải
    },
},
```

**Kết hợp với `header_styles`** — thêm `align` vào entry để căn cho cả group:

```js
header_styles: [
    { from: "total_docs", to: "pending_count", bgColor: "#1e8449", textColor: "#ffffff", align: 'center' },
],
```

**Thứ tự ưu tiên (cao → thấp):** `header_align.columns[fieldname]` > `header_styles[i].align` > `header_align` global.

> Các cột không khai báo giữ nguyên hành vi cũ: merge/filler cell mặc định `center`, base cell mặc định theo datatable.

### 3.7. Bước 7: Format icon/badge từng dòng (`row_icon_map`)

Format icon/badge theo **giá trị** của từng dòng dữ liệu — giống các report mẫu `báo_cáo_tồn_đọng_hoạt_động_*`, nhưng **chỉ cần khai báo config JS**, core tự wrap formatter + inject CSS, không phải viết formatter/`<style>` thủ công.

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

- `cls`: class CSS của badge (dùng class có sẵn hoặc tự định nghĩa qua `icon_styles`)
- `icon`: emoji/icon hiển thị **trước** giá trị (tùy chọn)
- Key hỗ trợ **wildcard**: `"*Đã hoàn*"` (chứa chuỗi), `"Done?"` (1 ký tự bất kỳ)
- Có thể trộn lẫn dạng toàn cục và dạng theo cột trong cùng một map

**Class badge có sẵn** (core inject tự động 1 lần): `st-red`, `st-orange`, `st-green`, `st-blue`, `st-purple`, `st-border-red`.

**CSS bổ sung** (tùy chọn):

```js
icon_styles: {
    ".st-custom": "background:#fff; color:#111; border:1px solid #ccc;",
    ".st-red":    "font-weight:600;",     // ghi đè / bổ sung class có sẵn
},
icon_css: `
    .badge-status.st-custom { border-radius: 3px; }
`,
```

> `icon_styles` = object `{ selector: "css..." }`; `icon_css` = raw CSS string. Nếu bỏ thì chỉ dùng class có sẵn. Nếu report ĐÃ có `formatter` riêng, core wrap bên ngoài formatter cũ — không ghi đè.

### 3.8. Bước 8: Thanh tiến độ (`progress_map`)

Vẽ **thanh tiến độ** cho cột số. Màu **tự động theo %**: `<50%` đỏ, `50–79%` cam, `>=80%` xanh lá (override bằng `color`).

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
        color: "#8e44ad",        // override màu (tùy chọn)
    },
},
```

Kết hợp với `row_icon_map`: cột **trạng thái** hiện badge, cột **%** hiện thanh — 2 cơ chế độc lập. Progress bar không áp dụng cho dòng Total.

---

## 4. Hàm aggregation chi tiết

| Hàm | Mô tả | Giống Excel | Ghi chú |
|-----|-------|-------------|---------|
| `sum` | Tổng các số | `SUM` | Bỏ qua text, boolean |
| `average` | Trung bình cộng | `AVERAGE` | Chỉ tính số |
| `avg` | Bí danh của `average` | — | Giống average |
| `max` | Giá trị lớn nhất | `MAX` | Chỉ tính số |
| `min` | Giá trị nhỏ nhất | `MIN` | Chỉ tính số |
| `count` | Đếm ô chứa số | `COUNT` | Không đếm text, boolean, empty |
| `countA` | Đếm ô không trống | `COUNTA` | Đếm cả số, text, boolean. Chỉ loại null/undefined/empty string |
| `sumif` | Tổng có điều kiện | `SUMIF` | Yêu cầu `condition_col` + `condition` |
| `countif` | Đếm có điều kiện | `COUNTIF` | Yêu cầu `condition_col` + `condition` |
| `averageif` | Trung bình có điều kiện | `AVERAGEIF` | Yêu cầu `condition_col` + `condition` |
| `none` | Không hiển thị Total | — | Ô trống, không tính |

### Cách parse config

Mỗi cột có thể nhận config ở dạng:

```js
// 1. String (hàm đơn)
column.aggregate_function = "sum";

// 2. Object (hàm IF)
column.aggregate_function = {
    fn: "sumif",
    condition_col: "status",
    condition: "Done"
};

// 3. Object alias (hỗ trợ snake_case và camelCase)
column.aggregate_function = {
    fn: "sumif",
    conditionCol: "status",     // thay vì condition_col
    conditionVal: "Done"        // thay vì condition
};
```

---

## 5. Hàm có điều kiện (SUMIF / COUNTIF / AVERAGEIF)

Hỗ trợ các cú pháp điều kiện giống Excel:

### So khớp chính xác

```js
condition: "Done"
// Chỉ khớp ô có giá trị "Done" (không phân biệt hoa-thường)
```

### So khớp ký tự đại diện (wildcard)

```js
condition: "Done*"    // Bắt đầu bằng "Done"
condition: "*Done"    // Kết thúc bằng "Done"
condition: "*Done*"   // Chứa "Done" ở bất kỳ đâu
condition: "???"      // Đúng 3 ký tự bất kỳ
condition: "A*C"      // Bắt đầu bằng "A", kết thúc bằng "C"
```

### So sánh số

```js
condition: ">100"     // Lớn hơn 100
condition: ">=100"    // Lớn hơn hoặc bằng 100
condition: "<50"      // Nhỏ hơn 50
condition: "<=50"     // Nhỏ hơn hoặc bằng 50
```

### So khớp phủ định

```js
condition: "!=Cancelled"   // Khác "Cancelled"
```

### So khớp bằng

```js
condition: "=Pending"   // Bằng "Pending" (tương tự không có dấu =)
```

> **Lưu ý:** Các phép so sánh `!=`, `=`, wildcard hoạt động trên giá trị **text** (không phân biệt hoa-thường). So sánh `>`, `<`, `>=`, `<=` hoạt động trên giá trị **số**.

---

## 6. Cách sử dụng trên giao diện

### 6.1. Double-click để đổi hàm aggregation

1. Chạy bất kỳ Query Report hoặc Report Builder nào
2. **Double-click** vào ô trên dòng Total của cột muốn đổi
3. Dialog hiện ra:
   - **Hàm tính**: chọn hàm (sum, average, max, min, count, countA, sumif, countif, averageif, none)
   - **Cột điều kiện**: (chỉ với sumif/countif/averageif) chọn cột để lọc
   - **Giá trị điều kiện**: (chỉ với sumif/countif/averageif) nhập giá trị cần khớp
4. Nhấn **Áp dụng** — dòng Total được refresh ngay lập tức

Lựa chọn được **tự động lưu vào localStorage** và sẽ khôi phục khi mở lại report.

### 6.2. Click chuột phải để di chuyển dòng Total

1. **Click chuột phải** vào bất kỳ ô nào trên dòng Total
2. Dòng Total sẽ chuyển lên trên (nếu đang ở dưới) hoặc xuống dưới (nếu đang ở trên)
3. Vị trí được lưu vào localStorage

### 6.3. Export Excel với Header Groups & Bold

Khi bấm nút **Export** trên report:
- Nếu report có `header_groups` hoặc `bold_header = true`, script tự động dùng thư viện XLSX (SheetJS) để tạo file Excel với:
  - Merge cell cho các header group
  - In đậm header (nếu `bold_header = true`)
  - Độ rộng cột tự động
- Nếu không có cả 2 cấu hình, dùng cơ chế export mặc định của Frappe

> File Excel được sinh hoàn toàn ở **client-side** (trình duyệt), không cần server hỗ trợ.

---

## 7. Ví dụ hoàn chỉnh: Báo cáo Doanh thu theo khu vực

### Bước 1: Tạo report script

**File:** `eupapp/eupapp/report/doanh_thu_khu_vuc/doanh_thu_khu_vuc.js`

```js
frappe.query_reports["Doanh thu theo khu vuc"] = {
    aggregate_fields: {
        "so_don":      "count",
        "doanh_thu":   "sum",
        "phi_van_chuyen": {
            fn: "sumif",
            condition_col: "loai_don",
            condition: "COD"
        },
        "ty_le":       "average"
    },

    header_groups: [
        { from: "khach_hang", to: "khu_vuc",    title: "Thong tin khach hang" },
        { from: "so_don",     to: "doanh_thu",  title: "Ket qua kinh doanh" },
        { from: "phi_van_chuyen", to: "phi_van_chuyen", title: "COD" },
        { from: "ty_le",      to: "hanh_dong",  title: "Danh gia" }
    ],

    total_row_position: 'top',
    bold_header: true,

    filters: [
        {
            fieldname: "from_date",
            label: __("Tu ngay"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("Den ngay"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "khu_vuc",
            label: __("Khu vuc"),
            fieldtype: "Select",
            options: ["", "Mien Bac", "Mien Trung", "Mien Nam"]
        }
    ],

    columns: [
        { fieldname: "khach_hang", label: __("Khach hang"), fieldtype: "Data", width: 180 },
        { fieldname: "khu_vuc", label: __("Khu vuc"), fieldtype: "Data", width: 120 },
        { fieldname: "so_don", label: __("So don"), fieldtype: "Int", width: 100 },
        { fieldname: "doanh_thu", label: __("Doanh thu"), fieldtype: "Currency", width: 150 },
        { fieldname: "phi_van_chuyen", label: __("Phi van chuyen"), fieldtype: "Currency", width: 140 },
        { fieldname: "ty_le", label: __("Ty le (%)"), fieldtype: "Float", width: 100 },
        { fieldname: "hanh_dong", label: __("Hanh dong"), fieldtype: "Data", width: 100 }
    ],

    onload: function(report) {
        // Nothing extra needed — core engine tự động capture config
    }
};
```

**File:** `eupapp/eupapp/report/doanh_thu_khu_vuc/doanh_thu_khu_vuc.py`

```python
from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    columns = [
        {"fieldname": "khach_hang", "label": _("Khach hang"), "fieldtype": "Data", "width": 180},
        {"fieldname": "khu_vuc", "label": _("Khu vuc"), "fieldtype": "Data", "width": 120},
        {"fieldname": "so_don", "label": _("So don"), "fieldtype": "Int", "width": 100},
        {"fieldname": "doanh_thu", "label": _("Doanh thu"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "phi_van_chuyen", "label": _("Phi van chuyen"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "ty_le", "label": _("Ty le (%)"), "fieldtype": "Float", "width": 100},
        {"fieldname": "hanh_dong", "label": _("Hanh dong"), "fieldtype": "Data", "width": 100},
    ]

    conditions = []
    if filters.get("from_date"):
        conditions.append("so.booking_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("so.booking_date <= %(to_date)s")
    if filters.get("khu_vuc"):
        conditions.append("cu.khu_vuc = %(khu_vuc)s")

    where = " AND ".join(conditions) if conditions else "1=1"

    data = frappe.db.sql("""
        SELECT
            cu.khach_hang AS khach_hang,
            cu.khu_vuc AS khu_vuc,
            COUNT(so.name) AS so_don,
            SUM(so.grand_total) AS doanh_thu,
            SUM(so.shipping_fee) AS phi_van_chuyen,
            AVG(so.profit_margin) AS ty_le
        FROM `tabCustomer` cu
        LEFT JOIN `tabSales Order` so ON so.customer = cu.name
        WHERE {where}
        GROUP BY cu.name
    """.format(where=where), filters, as_dict=1)

    return columns, data
```

### Kết quả trên giao diện

```
┌─────────────────────────────────────────────────────────────────────────────┐
│   Thong tin khach hang     │   Ket qua kinh doanh       │ COD  │ Danh gia  │
├────────────────────────────┼────────────────────────────┼──────┼────────────┤
│ Khach hang   │ Khu vuc     │ So don │ Doanh thu  │ PVC  │ Tyle │ Hanh dong │
├════════════════════════════╪════════════════════════════╪══════╪════════════╡  ← Total ở top
│   Total: 15  │             │   45   │ 125,000,000│ 8,500│ 12.5%│           │
├──────────────┼─────────────┼────────┼────────────┼──────┼──────┼────────────┤
│ Cty A        │ Mien Bac    │   12   │ 35,000,000 │ 2,000│ 15.0%│ [Chi tiet] │
│ Cty B        │ Mien Trung  │   18   │ 50,000,000 │ 4,500│ 11.5%│ [Chi tiet] │
│ Cty C        │ Mien Nam    │   15   │ 40,000,000 │ 2,000│ 13.0%│ [Chi tiet] │
└──────────────┴─────────────┴────────┴────────────┴──────┴──────┴────────────┘
```

**Giải thích:**
- Header group "Thong tin khach hang" merge cột khach_hang và khu_vuc
- "Ket qua kinh doanh" merge so_don, doanh_thu, phi_van_chuyen
- Cột "ty_le" (Ty le) đứng riêng lẻ, overlay với core header cell
- Dòng Total ở trên cùng (`total_row_position: 'top'`)
- Tất cả header và merge cell được in đậm (`bold_header: true`)
- Cột so_don dùng `count` — đếm số lượng đơn hàng
- Cột doanh_thu dùng `sum` — tổng doanh thu
- Cột phi_van_chuyen dùng `sumif` với điều kiện `loai_don = "COD"`
- Cột ty_le dùng `average` — trung bình tỷ lệ lợi nhuận

---

## 8. Ví dụ hoàn chỉnh: Báo cáo Nhập-Xuất-Tồn

### File: `eupapp/eupapp/report/nhap_xuat_ton/nhap_xuat_ton.js`

```js
frappe.query_reports["Nhap Xuat Ton"] = {
    aggregate_fields: {
        "ton_dau":    "sum",
        "nhap_trong_ky": "sum",
        "xuat_trong_ky": "sum",
        "ton_cuoi":   "sum",
        "gia_tri_ton_dau": "sum",
        "gia_tri_nhap":   "sum",
        "gia_tri_xuat":   "sum",
        "gia_tri_ton_cuoi": "sum",
        "so_lo":      "count"
    },

    header_groups: [
        { from: "ma_hang",  to: "don_vi_tinh",    title: "Thong tin hang hoa" },
        { from: "ton_dau",  to: "ton_cuoi",        title: "So luong" },
        { from: "gia_tri_ton_dau", to: "gia_tri_ton_cuoi", title: "Gia tri" }
    ],

    total_row_position: 'bottom',
    bold_header: true,

    filters: [
        {
            fieldname: "warehouse",
            label: __("Kho"),
            fieldtype: "Link",
            options: "Warehouse",
            reqd: 1
        },
        {
            fieldname: "from_date",
            label: __("Tu ngay"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("Den ngay"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        }
    ],

    columns: [
        { fieldname: "ma_hang", label: __("Ma hang"), fieldtype: "Data", width: 150 },
        { fieldname: "ten_hang", label: __("Ten hang"), fieldtype: "Data", width: 200 },
        { fieldname: "don_vi_tinh", label: __("DVT"), fieldtype: "Data", width: 60 },
        { fieldname: "ton_dau", label: __("Ton dau"), fieldtype: "Float", width: 100 },
        { fieldname: "nhap_trong_ky", label: __("Nhap trong ky"), fieldtype: "Float", width: 120 },
        { fieldname: "xuat_trong_ky", label: __("Xuat trong ky"), fieldtype: "Float", width: 120 },
        { fieldname: "ton_cuoi", label: __("Ton cuoi"), fieldtype: "Float", width: 100 },
        { fieldname: "gia_tri_ton_dau", label: __("Gia tri ton dau"), fieldtype: "Currency", width: 140 },
        { fieldname: "gia_tri_nhap", label: __("Gia tri nhap"), fieldtype: "Currency", width: 140 },
        { fieldname: "gia_tri_xuat", label: __("Gia tri xuat"), fieldtype: "Currency", width: 140 },
        { fieldname: "gia_tri_ton_cuoi", label: __("Gia tri ton cuoi"), fieldtype: "Currency", width: 140 },
        { fieldname: "so_lo", label: __("So lo"), fieldtype: "Int", width: 80 }
    ]
};
```

### Kết quả trên giao diện

```
┌──────────────────────┬────────────────────────────┬──────────────────────────────────────┐
│ Thong tin hang hoa   │       So luong             │            Gia tri                    │
├──────────────────────┼────────────────────────────┼──────────────────────────────────────┤
│ Ma hang│ Ten hang│DVT│Ton dau│Nhap│Xuat│Ton cuoi  │ GT ton dau│ GT nhap│ GT xuat│GT cuoi│ So lo│
├══════════════════════╪════════════════════════════╪══════════════════════════════════════╪═══════╡
│ H001   │ Hang A  │Cai│   100 │ 50 │ 30 │    120   │  5,000,000│2,500,00│1,500,00│6,000,00│   2   │
│ H002   │ Hang B  │Cai│   200 │ 80 │ 60 │    220   │  2,000,000│  800,00│  600,00│2,200,00│   3   │
│ H003   │ Hang C  │Cai│   150 │ 40 │ 20 │    170   │ 15,000,000│4,000,00│2,000,00│17,000,0│   1   │
├────────┴─────────┴────┼────────┼─────┼─────┼────────┼───────────┼────────┼────────┼────────┼───────┤
│   Total: 3            │   450  │ 170 │ 110 │   510   │ 22,000,000│7,300,00│4,100,00│25,200,0│  6    │
└───────────────────────┴────────┴─────┴─────┴────────┴───────────┴────────┴────────┴────────┴───────┘
```

## 9. Ví dụ hoàn chỉnh: Báo cáo có badge/icon + căn chỉnh header

### File: `eupapp/eupapp/report/ton_dong_hoat_dong/ton_dong_hoat_dong.js`

```js
frappe.query_reports["Báo cáo tồn đọng hoạt động bán hàng"] = {
    aggregate_fields: {
        "so_phieu":    "count",
        "gia_tri":     "sum",
        "thoi_gian":   "average",
        "so_da_hoan_thanh": "sum",
        "so_ke_hoach":      "sum",
    },

    header_groups: [
        { from: "hoat_dong", to: "so_phieu",    title: "Thong tin hoat dong" },
        { from: "gia_tri",   to: "thoi_gian",   title: "Gia tri & thoi gian" },
    ],
    header_styles: [
        { from: "hoat_dong", to: "so_phieu",    bgColor: "#1a5276", textColor: "#ffffff", align: 'left' },
        { from: "gia_tri",   to: "thoi_gian",   bgColor: "#1e8449", textColor: "#ffffff", align: 'center' },
    ],
    bold_header: true,
    total_row_position: 'top',

    // === TÍNH NĂNG 1: căn chỉnh header (mọi header cell) ===
    header_align: {
        align: 'center',              // default: giữa cho mọi header
        columns: {
            "hoat_dong": 'left',      // riêng cột này: trái
            "gia_tri":   'right',     // riêng cột này: phải
        },
    },

    // === TÍNH NĂNG 2: format icon/badge theo giá trị ===
    row_icon_map: {
        "Đã hoàn thành":   { cls: "st-green",  icon: "✅" },
        "Đang xử lý":      { cls: "st-orange", icon: "🔄" },
        "Quá hạn":         { cls: "st-red",    icon: "❌" },
        "Không hoạt động": { cls: "st-purple", icon: "🚫" },
    },
    icon_styles: {
        ".st-red": "font-weight: 600;",       // ghi đè class có sẵn
    },
    icon_css: `
        .badge-status { box-shadow: 0 1px 2px rgba(0,0,0,.08); }
    `,

    // === TÍNH NĂNG 3: thanh tiến độ (progress bar) ===
    progress_map: {
        "ty_le_hoan_thanh": {
            num: "so_da_hoan_thanh",     // % = so_da_hoan_thanh / so_ke_hoach
            den: "so_ke_hoach",
            icon: "📊",
        },
    },

    filters: [ /* ... */ ],
    columns: [
        { fieldname: "hoat_dong", label: __("Hoat dong"), fieldtype: "Data", width: 180 },
        { fieldname: "trang_thai", label: __("Trang thai"), fieldtype: "Data", width: 140 },
        { fieldname: "so_phieu", label: __("So phieu"), fieldtype: "Int", width: 90 },
        { fieldname: "ty_le_hoan_thanh", label: __("Ty le hoan thanh"), fieldtype: "Percent", width: 140 },
        { fieldname: "gia_tri", label: __("Gia tri"), fieldtype: "Currency", width: 140 },
        { fieldname: "thoi_gian", label: __("Thoi gian (h)"), fieldtype: "Float", width: 110 },
    ]
};
```

### Kết quả trên giao diện

```
┌─────────── Thong tin hoat dong ─────────┬────── Gia tri & thoi gian ──────┐
│   Hoat dong   │ Trang thai│ So phieu │ Ty le hoan thanh │ Gia tri │ Thoi gian │
├═══════════════╪═══════════╪══════════╪══════════════════╪═════════╪═══════════╡  ← Total ở top
│  Total: 3     │           │    45    │   ████████░░ 84%  │125,000,0│    12.5   │
├───────────────┼───────────┼──────────┼───────────────────┼─────────┼───────────┤
│  Nhập kho     │ ✅ Đã hoàn│    12    │   ██████████ 100% │35,000,0│    15.0   │
│  Xuất kho     │ 🔄 Đang xử│    18    │   ████░░░░░░ 40%  │50,000,0│    11.5   │
│  Điều chuyển  │ ❌ Quá hạn│    15    │   ██████████ 100% │40,000,0│    13.0   │
└───────────────┴───────────┴──────────┴───────────────────┴─────────┴───────────┘
```

**Giải thích:**
- `header_groups` + `header_styles` (có `align`) + `header_align.columns` căn/tô màu từng header
- `row_icon_map` biến cột trạng thái thành badge màu + icon: `✅ Đã hoàn`, `🔄 Đang xử`, `❌ Quá hạn`
- `progress_map` biến cột `ty_le_hoan_thanh` thành thanh tiến độ (màu tự theo %: đỏ <50, cam 50-79, xanh >=80)
- `aggregate_fields` + `total_row_position: 'top'` đặt dòng Total lên đầu
- Không cần viết `formatter` hay inject `<style>` thủ công — chỉ khai báo config

> Bộ icon đầy đủ theo nghiệp vụ: [`../usage/report-row-icon-map.md`](../usage/report-row-icon-map.md)

## 10. Cấu hình nâng cao

### 10.1. Kết hợp nhiều cấu hình trong một report

```js
frappe.query_reports["Ban hang chi tiet"] = {
    aggregate_fields: {
        "so_luong":  "sum",
        "don_gia":   "average",
        "thanh_tien": "sum",
        "so_hoa_don": "count",
        "khach_moi": "countA",          // Đếm cả tên khách hàng
        "hoa_hong": {
            fn: "sumif",
            condition_col: "kenh_ban",
            condition: "Online"
        }
    },

    header_groups: [
        { from: "san_pham", to: "don_vi_tinh", title: "San pham" },
        { from: "so_luong", to: "thanh_tien", title: "Giao dich" },
        { from: "khach_hang", to: "khach_moi", title: "Khach hang" }
    ],

    total_row_position: 'top',
    bold_header: true
};
```

### 10.2. Sử dụng trong Report Builder (không cần code JS)

Trong Report Builder của Frappe, bạn có thể set `aggregate_function` trực tiếp trong field definition của DocType:

Không cần cấu hình thêm — khi Report Builder render, các cột có fieldtype là `Currency`, `Int`, `Float`, `Percent` sẽ tự động nhận hàm aggregation mặc định là `sum`. Người dùng có thể double-click vào Total để đổi hàm.

### 10.3. Override từng report bằng localStorage

Khi người dùng double-click để đổi hàm aggregation, lựa chọn đó được lưu vào localStorage với key:

```
eup_report_agg:<user>:<report_name>
```

Điều này override hoàn toàn config từ `frappe.query_reports`. Muốn reset về mặc định, xóa key đó khỏi localStorage (F12 → Application → Local Storage).

### 10.4. Override vị trí Total row

Vị trí Total row được lưu riêng trong localStorage:

```
eup_report_agg_pos:<user>:<report_name>
```

Giá trị: `"top"` hoặc `"bottom"`. Xóa key để quay về config mặc định.

## 11. Troubleshooting

### Vấn đề 1: Double-click không mở dialog

- Kiểm tra xem cả 2 file JS đã được load chưa (F12 → Console → tìm log `[Report Agg] Core loaded` và `Double-click Total cell to configure`)
- Kiểm tra DataTable có footer không (report phải có dữ liệu)
- Thử refresh trang

### Vấn đề 2: Hàm IF không hoạt động

- Kiểm tra `condition_col` có tồn tại trong data trả về từ server không
- Trong console, gõ `frappe.query_report.data[0]` để xem các field có sẵn
- Kiểm tra `condition` có khớp chính xác không (không phân biệt hoa-thường)

### Vấn đề 3: Header groups không hiển thị

- Kiểm tra `header_groups` đã được định nghĩa trong `frappe.query_reports["Tên report"]`
- Đảm bảo `from` và `to` là fieldname có tồn tại trong columns
- Nếu columns thay đổi sau khi render, MutationObserver tự động rebuild — đợi 1-2 giây

### Vấn đề 4: Export Excel không merge header

- Tính năng export tùy chỉnh chỉ kích hoạt khi có `header_groups` hoặc `bold_header = true`
- Nếu không có 2 cấu hình này, export dùng cơ chế mặc định của Frappe
- File Excel được sinh client-side — nếu có lỗi, kiểm tra console

### Vấn đề 5: Bold header không hiệu quả

- Đảm bảo `bold_header: true` được set trong `frappe.query_reports["Tên report"]`
- Khi xuất Excel, bold áp dụng cho tất cả dòng header (group + column labels)
- Trên UI, bold dùng CSS class — đảm bảo không có CSS nào khác override

### Vấn đề 6: Total row crash / không hiển thị

- Core engine tự động patch `bodyRenderer.getTotalRow()` để xử lý cột `none` và `disable_total`
- Nếu gặp lỗi `Cannot read properties of undefined` — core engine cũng patch `datamanager.getColumns()` để lọc bỏ phần tử null
- Thử refresh report

### Vấn đề 7: Badge / progress bar không hiển thị

- Kiểm tra `_eup_formatter_patched` = `true` trong console (xem Debug tips bên dưới)
- Với `row_icon_map`: key phải khớp **giá trị thật** từ server — gõ `frappe.query_report.data[0]` để xem
- Với `progress_map`: `num`/`den` phải là fieldname **có trong data**; nếu `den = 0` hoặc thiếu field → bỏ qua không hiện thanh
- Sau khi đổi config JS nhớ tăng version asset trong `hooks.py` rồi **Ctrl+Shift+R**

### Debug tips

Mở F12 Console và gõ:

```js
// Kiểm tra config aggregation đã capture
frappe.EUP_REPORT_AGG._configs

// Kiểm tra header groups đã capture
frappe.EUP_REPORT_AGG._headerGroups

// Kiểm tra total row position
frappe.EUP_REPORT_AGG._totalRowPosition

// Kiểm tra settings đã lưu trong localStorage
frappe.EUP_REPORT_AGG.loadSettings("Tên report")

// Kiểm tra cấu hình report gốc
frappe.query_reports["Tên report"]

// Kiểm tra formatter đã được wrap cho row_icon_map / progress_map chưa
frappe.query_reports["Tên report"]._eup_formatter_patched   // true = đã wrap

// Kiểm tra CSS badge có được inject chưa
document.getElementById('eup-badge-base-style')             // base style
document.getElementById('eup-badge-custom-<tên report>')    // CSS riêng của report

// Kiểm tra % của progress_map cho 1 dòng
frappe.query_reports["Tên report"].progress_map
// VD với data: % = data["so_da_giao"] / data["so_phai_giao"]
```

---

> **Tài liệu liên quan:** [Bộ icon & progress bar cho Report](../usage/report-row-icon-map.md) | [Report Aggregation Dropdown UI](../usage/report-agg-dropdown.md) | [Report System Overview](../overview.md)
