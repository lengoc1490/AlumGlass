---
title: "Tính giá BOM trên báo giá (dialog Preview / Tính giá)"
contexts:
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# Tính giá BOM trên báo giá

## Mô tả

Khi soạn báo giá AlumGlass trên **Quotation**, mỗi dòng sản phẩm (Quotation
Item) gắn với một **BOM** (`al_bom`) và phiên bản đóng băng (`al_bom_version`).
Nút **Tính giá** / **Preview tính giá** chạy `BomOrchestrator` 7-phase (B0–B7)
để tính thành tiền từng dòng vật tư → gom nhóm cost bucket → chạy Cost
Template → ra **Giá bán có VAT** (`al_gia_vat`).

## Cách dùng

Nút tính giá nằm ở **từng dòng con Quotation Item** (không còn nút toolbar ở
đầu form):

- Mỗi dòng có nút nhỏ **📐** ở đầu dòng (hoặc **double-click** vào dòng) để mở
  dialog **Tham số BOM**.
- Khi mở rộng dòng (grid form), có 2 nút **📐 Tham số BOM** và **🖥️ Preview
  tính giá** ngay trong dòng.

Trong dialog **Tham số BOM**:

1. Chọn **BOM** (`al_bom`) → hệ thống tự sinh form tham số từ **Variable Set**
   của BOM (bố cục **2 cột thoáng**). Biến hệ thống (`is_system`) hiển thị
   read-only ở cuối.
2. Đổi BOM → vùng tham số **re-render ngay trong dialog** (không tạo dialog mới,
   không giật, không mất vị trí/kích thước).
3. Cần thêm tham số không có trong Variable Set → thêm dòng trong bảng **Biến
   mở rộng** (Table field chuẩn Frappe, thêm/xóa dòng được).
4. Bấm **💾 Lưu** để lưu tham số vào dòng, hoặc **🖥️ Preview tính giá** để xem
   kết quả ngay.
5. Kết quả hiển thị trong dialog: **Cost Breakdown** (các khoản mục Cost
   Template: TONG_VL, NC_SX, NC_LD, TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT,
   GIA_BAN, DON_GIA_M2, VAT, GIA_VAT…), **Cost Buckets**, và bảng chi tiết dòng
   vật tư (slug, item, W/H, qty, đơn giá, thành tiền).
6. Kết quả được lưu vào item: `al_gia_vat` (giá có VAT), `al_gia_ban` (chưa
   VAT), `al_bom_result` (JSON đầy đủ buckets/cost_template/lines).

## BOM lớn — tính trong nền (async)

- BOM có số dòng ≤ ngưỡng **ASYNC_BOM_THRESHOLD** (mặc định **150**, chỉnh
  trong Formula Global Variable) → tính **đồng bộ**, kết quả hiện ngay.
- BOM lớn hơn ngưỡng → hệ thống gửi vào **background job** (queue long):
  dialog hiện spinner "đang tính trong nền", khi xong kết quả **tự động hiện**
  qua realtime (không cần bấm lại).
- **Đóng/mở lại dialog:** hệ thống đọc trạng thái đã lưu trên item
  (`al_calc_status`). Nếu đang tính nền → hiện thông báo chờ, không gọi lại.
  Nếu đã xong → hiện lại kết quả đã lưu ngay lập tức. Nếu lỗi → hiện thông báo
  lỗi (chi tiết trong `al_calc_error` / Error Log).

## Lưu ý

- Giá tính theo **version đóng băng** (`al_bom_version`): snapshot BOM Set,
  Cost Template và **Pricing Dimension** chụp tại lúc publish — đổi config sau
  đó không làm đổi giá báo giá đã chốt.
- Không sửa trực tiếp các trường `al_gia_vat`/`al_bom_result` — chúng là kết
  quả tính toán (read_only).
