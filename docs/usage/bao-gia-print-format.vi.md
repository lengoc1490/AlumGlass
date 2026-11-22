---
title: "In báo giá AlumGlass (Print Format)"
contexts:
  - "print-format/Báo giá AlumGlass"
tags: [sales-crm]
doc_type: print_format
---

# In báo giá AlumGlass

> Quy tắc "khi nào số được ghi vào báo giá", "in khi còn số chưa lưu thì hỏi gì":
> xem tệp chuẩn `docs/usage/tinh-gia-bao-gia.vi.md`.

## Mô tả

Print Format **"Báo giá AlumGlass"** dùng để in/export báo giá từ **Quotation**
ra PDF. Bản in **không tính lại giá** — nó in **số đang có trên dòng** của báo giá.

## Cách dùng

1. Mở **Quotation** đã có dòng hàng đã tính giá.
2. **Lưu** báo giá (nếu vừa tính lại giá mà chưa lưu).
3. Bấm **Menu → Print → Báo giá AlumGlass** (hoặc từ nút Print trên form).
4. Kiểm tra: từng dòng sản phẩm hiện BOM + version + **Giá chưa VAT** +
   **Giá có VAT**; phần cuối hiện chi tiết bảng chi phí (từ vật liệu tới giá có
   VAT) + tổng theo nhóm chi phí + **Tổng cộng toàn báo giá**.

Khi in từ **form báo giá** mà còn số vừa tính chưa lưu, hệ thống mở hộp thoại
**Lưu rồi in** / **Huỷ** — để bản in chắc chắn khớp số trên màn hình.

## Dữ liệu nguồn

Template đọc thẳng số trên dòng hàng của báo giá (không tính lại):

| Hiển thị trên bản in | Lấy từ |
|---|---|
| BOM + version đã chốt | dòng hàng của báo giá |
| Giá chưa VAT / giá có VAT | dòng hàng của báo giá |
| Bảng chi phí chi tiết (nhóm chi phí, khoản mục) | kết quả tính đã lưu trên dòng hàng |

## Lưu ý

- Dòng hàng **chưa tính giá** sẽ hiển thị trống — hãy tính giá cho dòng đó trước
  khi in.
- BOM lớn tính trong nền: đợi kết quả về dòng rồi mới in; đang tính thì giá chưa có.
- **Giới hạn:** hộp thoại hỏi lưu chỉ có khi in **từ form báo giá**. In từ danh
  sách, in hàng loạt, hoặc mở link in trực tiếp **chưa có** lớp hỏi này — hãy
  `Lưu` trước.
- Template không dùng CSS zoom — tương thích **wkhtmltopdf** lẫn browser
  preview. Nếu gặp lệch font/size trên wkhtmltopdf → xem trước qua browser
  preview (memory `eup-dntt-bulk-print-wkhtmltopdf`).
