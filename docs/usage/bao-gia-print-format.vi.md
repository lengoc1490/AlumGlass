---
title: "In báo giá AlumGlass (Print Format)"
contexts:
  - "print-format/Báo giá AlumGlass"
tags: [sales-crm]
doc_type: print_format
---

# In báo giá AlumGlass

## Mô tả

Print Format **"Báo giá AlumGlass"** dùng để in/export báo giá từ **Quotation**
ra PDF. Báo giá in **đúng số đã chốt** tại lúc bấm "Tính giá" — **không tính
lại giá** khi in.

## Cách dùng

1. Mở **Quotation** đã có dòng item đã tính giá (có `al_gia_vat`).
2. Bấm **Menu → Print → Báo giá AlumGlass** (hoặc từ nút Print trên form).
3. Kiểm tra: từng dòng sản phẩm hiện BOM + version + **Giá chưa VAT** +
   **Giá có VAT**; phần cuối hiện chi tiết **Cost Template** (TONG_VL → GIA_VAT)
   + **Cost Buckets** + **Tổng cộng toàn báo giá** (Σ `al_gia_vat`).

## Dữ liệu nguồn

Template đọc thẳng từ Quotation Item (không recalculate):

| Trường | Ý nghĩa |
|---|---|
| `item.al_bom` / `item.al_bom_version` | BOM + version đã chốt |
| `item.al_gia_ban` / `item.al_gia_vat` | Giá chưa / có VAT |
| `item.al_bom_result` (JSON) | buckets + cost_template + lines (parse qua `frappe.parse_json`) |

## Lưu ý

- Dòng item **chưa tính giá** (thiếu `al_gia_vat`) sẽ hiển thị trống — hãy bấm
  "Tính giá" cho từng dòng trước khi in.
- BOM lớn (async): đợi kết quả tính nền xong (`al_calc_status = Success`) rồi
  mới in — nếu đang tính (`Queued`/`Running`), giá chưa có.
- Template không dùng CSS zoom — tương thích **wkhtmltopdf** lẫn browser
  preview. Nếu gặp lệch font/size trên wkhtmltopdf → xem trước qua browser
  preview (memory `eup-dntt-bulk-print-wkhtmltopdf`).
