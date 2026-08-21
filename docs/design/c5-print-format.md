# C5 — Print Format báo giá tối thiểu ("Báo giá AlumGlass")

> **Trạng thái:** Implemented (C5, Nhóm I quotation production-ready) · 2026-08-21
> **Job:** `2026-08-16_alumglass-sprint1-quotation`

## Vấn đề

Báo giá cần in ra PDF/giấy từ Quotation. Không được **tính lại giá** tại thời
điểm in — báo giá phải in **đúng số đã chốt** lúc bấm "Tính giá" (lưu trong
`al_bom_result` + `al_gia_ban`/`al_gia_vat` trên từng Quotation Item).

## Giải pháp

### 1. Print Format Jinja — đọc kết quả ĐÃ TÍNH, không recalculate

`templates/print_formats/bao_gia.html` + Print Format **"Báo giá AlumGlass"**
(`doc_type="Quotation"`, `custom_format=1`, `print_format_type="Jinja"`).

Dữ liệu nguồn (từ item, không tính lại):

| Field | Nội dung |
|---|---|
| `item.al_bom` / `item.al_bom_version` | BOM + version đã chốt |
| `item.al_gia_ban` / `item.al_gia_vat` | Giá chốt (chưa/có VAT) |
| `item.al_bom_result` (JSON) | `buckets` + `cost_template` + `lines` — dùng `frappe.parse_json` |

Template hiển thị: header báo giá (khách hàng, ngày), bảng dòng item (BOM,
version, giá chưa/có VAT), chi tiết `cost_template` (14 dòng: TONG_VL → GIA_VAT),
buckets, tổng cộng toàn báo giá (Σ al_gia_vat). Dùng `frappe.utils.fmt_money`
format số.

### 2. Tương thích wkhtmltopdf

**Không dùng CSS `zoom`/`@media screen`** — wkhtmltopdf không chạy CSS zoom.
Template dùng layout đơn giản (table + inline style basic) chạy tốt trên cả
wkhtmltopdf lẫn browser preview (xem memory
`eup-dntt-bulk-print-wkhtmltopdf`). Nếu khách hàng gặp lệch font/size trên
wkhtmltopdf → dùng browser preview qua `/bulk_print_preview` (tiền lệnh đã có).

### 3. Tạo Print Format — patch (lần đầu có cơ chế patches)

Repo chưa có fixture Print Format → tạo qua patch (cùng đợt tạo `patches.txt`
cho P1 backfill):

- `alumglass/setup/print_format.py::create_bao_gia_print_format()` — idempotent
  (bỏ qua nếu đã tồn tại), đọc template file → tạo Print Format.
- Patch `alumglass/patches/v28_9/create_bao_gia_print_format.py` gọi helper.
- `hooks.py::_after_install` cũng gọi helper (máy cài mới không cần migrate).

## File thay đổi

| File | Thay đổi |
|---|---|
| `alumglass/templates/print_formats/bao_gia.html` | Template Jinja mới |
| `alumglass/setup/print_format.py` | Helper tạo Print Format (idempotent) |
| `alumglass/patches/v28_9/create_bao_gia_print_format.py` | Patch chạy 1 lần |
| `patches.txt` | Đăng ký patch |
| `alumglass/hooks.py` | `_after_install` gọi helper |

## Test / verify

- Manual: mở Quotation có item đã tính giá → Print → chọn "Báo giá AlumGlass"
  → kiểm tra số khớp `al_gia_vat`, không có dòng recalc.
- Không chạy `bench migrate` trên site dev (constraint job) — Print Format chỉ
  cần patch/after_install để khởi tạo.
