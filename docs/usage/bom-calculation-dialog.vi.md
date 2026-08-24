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

- Mỗi dòng có **2 nút nhỏ ở góc phải trường item_code**: **📐** mở dialog
  **Tham số BOM** và **🖥️** bấm thẳng **Preview tính giá** (không cần mở rộng
  dòng; nếu chưa chọn BOM sẽ nhắc mở 📐 trước). **Double-click** vào dòng cũng
  mở dialog Tham số BOM.
- Nút **hiển thị ngay khi mở form** có dòng sẵn (không cần thêm dòng/reload):
  form tự retry gắn nút sau khi grid render xong các dòng (khoảng ≤ 5 giây;
  gắn xong là dừng, idempotent — không nhân đôi nút khi re-render).
- Khi mở rộng dòng (grid form), 2 nút **📐 Tham số BOM** và **🖥️ Preview
  tính giá** nằm ở **đầu** vùng form mở rộng.

Trong dialog **Tham số BOM**:

1. Mục **Chọn BOM**: chọn **BOM** (`al_bom`) + **BOM Version**. Bên dưới là
   section **Thông tin sản phẩm** gồm các **ô read-only** (Data field chuẩn,
   bố cục 2 cột): **BOM**, **Bom Set**, **Variable Set**, **Hệ profile**, **Hãng
   nhôm**, **Phụ kiện (Accessory Set)** — mỗi ô hiển thị `tên (code)` (riêng
   **Phụ kiện** hiển thị tên bộ phụ kiện), thiếu dữ liệu hiển thị **"—"**. Các
   ô này tự cập nhật khi đổi BOM (không tạo lại dialog).
2. Hệ thống tự sinh form tham số từ **Variable Set** của BOM với bố cục
   **3 cột thoáng** (gồm **Biến đầu vào** và **Biến hệ thống**). Biến hệ thống
   (`is_system`) hiển thị **đầy đủ label + giá trị mặc định** và **cho phép
   chỉnh sửa**.
3. Đổi BOM → vùng tham số + thông tin BOM **re-render ngay trong dialog**
   (không tạo dialog mới, không giật, không mất vị trí/kích thước).
4. Cần thêm tham số không có trong Variable Set → thêm dòng trong bảng **Biến
   mở rộng** (Table field chuẩn Frappe, thêm/xóa dòng được). Cột **Tên biến** là
   **Link → AL Variable Library** (chỉ hiện biến `is_system = 0`); khi chọn xong,
   cột **Kiểu** tự nạp theo Library. Kiểu cho phép: Data / Float / Int / Select /
   Link / Check / Currency.
6. Bấm **💾 Lưu** để lưu tham số vào dòng, hoặc **🖥️ Preview tính giá** để xem
   kết quả ngay.
7. Kết quả hiển thị trong dialog — **renderer dùng chung**
   (`alumglass.render_bom_result_display`, cùng renderer với dialog 🖥️):
   - **Summary bar**: Giá bán (`GIA_BAN`), VAT (`GIA_VAT`), số dòng vật tư.
   - **Chi tiết vật tư** (collapsible): mỗi dòng hiển thị **label đầy đủ** (từ
     AL Slug Library), mã vật tư, **kích thước W×H (mm)**, **số lượng**,
     **đơn giá**, **thành tiền**, **nhóm chi phí** (tên bucket từ AL Cost
     Bucket).
   - **Tổng theo nhóm chi phí** (collapsible): từng cost bucket với tên tiếng
     Việt (Vật liệu nhôm, Vật liệu kính, Vật tư phụ…).
   - **Chi phí chế tạo** (collapsible): từng khoản mục Cost Template
     (TONG_VL, NC_SX, NC_LD, TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT,
     GIA_BAN, DON_GIA_M2, VAT, GIA_VAT…) hiển thị **label** (từ Cost Template
     Item trong snapshot version) + **công thức** + **giá trị**. Các dòng
     tổng (`TONG_`/`GIA_`/`VAT`) in đậm nền vàng.
8. Dialog **🖥️ Preview tính giá** (BOMDialog) render **cùng bảng chi tiết**
   (tái sử dụng renderer dùng chung — không duplicate code), bổ sung:
   - **Công thức + giá trị** mỗi dòng chi phí chế tạo.
   - **Trace dạng HTML** mỗi dòng (formula → thay biến bằng giá trị → kết
     quả) trong accordion "Xem trace" — server `get_result_display` build
     trace (thay biến đầu vào + bucket + dòng cost template).
9. Kết quả được lưu vào item: `al_gia_vat` (giá có VAT), `al_gia_ban` (chưa
   VAT), `al_bom_result` (JSON đầy đủ buckets/cost_template/lines).
10. **Biến `glass_master` (Loại kính)** là biến đầu vào của BOM có kính (Link →
    AL Glass Master): chọn kính khác trong dialog sẽ **lưu vào `al_bom_vars`**
    (`glass_master`) và **engine ÁP DỤNG** (V6 Phase 4 — 2026-08-24): line kính
    chuyển sang kính đã chọn (item_code + giá), **nẹp kính** + **keo** resolve lại
    theo kính đó (RULE-NEP-GLASSTHICK theo độ dày, RULE-KEO-GLASSTYPE theo loại).
    Không có `glass_master` trong al_bom_vars → dùng `default_glass_master` của
    từng dòng AL Bom Item như cũ.
11. **Giá theo thông số**: giá vật tư được nạp theo **composite key** — Item
    Price có cột `custom_pd_mau_sac`/`custom_pd_xuat_xu`/`custom_pd_do_day`/
    `custom_pd_be_mat` (màu, xuất xứ, độ dày, bề mặt) qua
    `AL Variable Dimension Mapping` → engine chọn dòng Item Price khớp **nhiều
    nhất** với thông số đang chọn (`_match_composite_price`). Dữ liệu hiện tại
    mỗi item mới có 1 dòng giá (chưa tách theo từng thông số).

## Nút form-level: Tính giá / Preview giá toàn bộ (Phase 3)

Ngoài nút trên từng dòng, trên toolbar form Quotation có nhóm **AlumGlass**
gồm 2 nút:

- **Tính giá** (C1): quét toàn bộ dòng sản phẩm, **validate** từng dòng — dòng
  nào thiếu BOM / BOM Version / tham số (`al_bom_vars`) sẽ **liệt kê rõ dòng nào
  thiếu gì** trong hộp cảnh báo (không tính dòng đó). Các dòng đủ thông tin sẽ
  tính lần lượt (sync/async theo ngưỡng như bình thường), cập nhật
  `rate = al_gia_ban` (A8), `al_gia_ban`, `al_gia_vat`, `al_bom_result`. Hiển thị
  tổng kết **"đã tính X/Y dòng"** (+ số dòng chờ nền / lỗi nếu có).
- **Preview giá** (C2): mở dialog lớn (max-width **90vw**) gồm:
  - **Bảng tổng hợp**: # , Mã sp, Tên sp, Số lượng, Đơn giá, Thành tiền.
  - **Từng sản phẩm** dạng **collapsible** chi tiết tính toán — **tái sử dụng
    renderer dùng chung** Phase 2 (Chi tiết vật tư / Tổng nhóm chi phí / Chi phí
    chế tạo). Dòng chưa tính → hiển thị **"Chưa tính giá"**.

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
- **ConfigSnapshot chỉ tạo khi SUBMIT Quotation** (doc_events `on_submit`):
  mỗi dòng Quotation Item đã tính BOM (`al_bom_result` có giá trị) sẽ tạo 1
  `ConfigSnapshot` (chụp `inputs_json` từ `al_bom_vars`, `result_json` từ
  `al_bom_result`, `bom_version` từ `al_bom_version`) và link vào
  `al_config_snapshot`. Việc bấm **Tính giá / Preview** chỉ ghi
  `al_gia_vat`/`al_gia_ban`/`al_bom_result` vào dòng — **không tạo snapshot**
  mỗi lần tính.
