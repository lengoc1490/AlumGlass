---
title: "Tính giá báo giá nhôm kính (Quotation Pricing)"
contexts:
  - "Form/Quotation Item"
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# Tính giá báo giá nhôm kính

## Mô tả

Khi soạn báo giá trên **Quotation**, mỗi dòng sản phẩm (Quotation Item) gắn với
một **BOM** (`al_bom`) và phiên bản đóng băng (`al_bom_version`). Nút **Tính
giá** / **Preview tính giá** chạy `BomOrchestrator` 7-phase (B0–B7) để tính
thành tiền từng dòng vật tư → gom nhóm cost bucket → chạy Cost Template → ra
**Giá bán có VAT** (`al_gia_vat`).

Phần lõi dùng nền tảng **Formula Builder (FB-max)**: biến hệ thống/bảng giá/chi
phí được resolve từ **một nguồn duy nhất** là Formula Variable Binding (qua
`get_live_context` + `BatchBindingResolver`), thay cho các resolver tự viết trước
đây. Chi tiết kiến trúc: `docs/design/quotation-pricing.md`.

## Cách dùng

1. Mở **Quotation** → mỗi dòng sản phẩm có **2 nút nhỏ ở đầu dòng**: **📐** mở
   **Tham số BOM**, **🖥️** bấm thẳng **Preview tính giá** (hoặc double-click dòng
   để mở Tham số BOM, hoặc mở rộng dòng dùng 2 nút **📐 Tham số BOM** / **🖥️
   Preview tính giá** ở đầu vùng form mở rộng). Nếu bấm 🖥️ khi chưa chọn BOM,
   hệ thống nhắc mở 📐 trước.
2. Mục **Chọn BOM** hiển thị read-only thông tin **BOM / Bom Set / Variable Set**
   (tự cập nhật khi đổi BOM). Điền tham số sản phẩm (chiều rộng/cao, màu, xuất
   xứ, độ dày, bề mặt…) — form sinh động từ Variable Set của BOM, bố cục **3
   cột**; **Biến hệ thống** hiển thị label + giá trị mặc định và **có thể chỉnh
   sửa**.
3. Thêm tham số không có trong Variable Set → bảng **Biến mở rộng**: cột **Tên
   biến** là Link → **AL Variable Library**, cột **Kiểu** tự nạp theo Library khi
   chọn tên biến.
4. Kết quả hiển thị trong dialog: **Cost Breakdown** (TONG_VL, NC_SX, NC_LD,
   TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT, GIA_BAN, DON_GIA_M2, VAT,
   GIA_VAT…), **Cost Buckets**, và bảng chi tiết dòng vật tư. Render dùng
   **renderer dùng chung** (collapsible + label đầy đủ + công thức + trace) —
   xem `docs/usage/bom-calculation-dialog.vi.md`.
5. Kết quả được lưu vào item: `al_gia_vat` (giá có VAT), `al_gia_ban` (chưa VAT),
   `al_bom_result` (JSON đầy đủ buckets/cost_template/lines + danh sách lỗi nếu có).
6. **Sau khi tính xong → `rate` của dòng được set = `al_gia_ban`** (A8, chưa VAT);
   `item_code`/`item_name` của dòng được set từ `representative_item` của BOM khi
   bấm **Lưu** trong dialog Tham số BOM.
7. Nút **form-level** nhóm **AlumGlass**: **Tính giá** (quét + validate từng dòng,
   tính lần lượt, cập nhật rate — cảnh báo rõ dòng nào thiếu gì) và **Preview giá**
   (dialog 90vw, bảng tổng hợp + từng sản phẩm collapsible chi tiết). Xem
   `docs/usage/bom-calculation-dialog.vi.md`.

## Hành vi khi có lỗi tính toán

- Một dòng vật tư/công thức **lỗi** (vd biến thiếu) → dòng đó nhận giá trị `0` +
  lỗi được ghi lại trong `al_bom_result.errors` — **các dòng khác vẫn tính bình
  thường**, không chết cả báo giá.
- **Chia cho 0** luôn báo lỗi dừng — nếu gặp, kiểm tra tham số nhập (kích thước
  = 0, đơn giá thiếu…) trước khi tính lại.
- Nếu dialog báo lỗi chi tiết, tham khảo Error Log / `al_calc_error`.

## BOM lớn — tính trong nền (async)

- BOM ≤ ngưỡng **ASYNC_BOM_THRESHOLD** (mặc định **150**, chỉnh trong Formula
  Global Variable) → tính **đồng bộ**, kết quả hiện ngay.
- BOM lớn hơn ngưỡng → gửi **background job** (queue long): dialog hiện spinner
  "đang tính trong nền", khi xong kết quả **tự động hiện** qua realtime.
- **Đóng/mở lại dialog:** đọc trạng thái đã lưu trên item (`al_calc_status`).
  Đang tính nền → báo chờ; đã xong → hiện lại kết quả; lỗi → hiện thông báo.

## Lưu ý

- Giá tính theo **version đóng băng** (`al_bom_version`): snapshot BOM Set, Cost
  Template và **Pricing Dimension** chụp tại lúc publish — đổi config sau đó
  không làm đổi giá báo giá đã chốt.
- Không sửa trực tiếp `al_gia_vat`/`al_bom_result` — chúng là kết quả tính toán
  (read_only).
- In báo giá: dùng Print Format **"Báo giá AlumGlass"** (đọc số đã chốt, không
  tính lại). Xem `docs/usage/bao-gia-print-format.vi.md`.
