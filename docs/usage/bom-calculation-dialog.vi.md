---
title: "Cửa sổ Tham số BOM / Preview tính giá — chi tiết màn hình"
contexts:
  - "Form/Quotation"
  - "Form/Quotation Item"
tags: [sales-crm]
doc_type: doctype
---

# Cửa sổ tính giá — chi tiết màn hình

> Trang này tả **từng ô, từng vùng** trên cửa sổ tính giá.
> Cách dùng đầu-cuối, ý nghĩa "giá chưa lưu", lưu và in: xem tệp chuẩn
> `docs/usage/tinh-gia-bao-gia.vi.md`. ⛔ Không chép lại ở đây.
> Lý do kỹ thuật (cho người bảo trì): `docs/design/preview-khong-ghi-db.md`.

## Mở cửa sổ

Mỗi dòng hàng có 2 nút nhỏ ở góc phải ô mã hàng:

- **📐** — mở **Tham số BOM**. Bấm đúp vào dòng cũng mở.
- **🖥️** — bấm thẳng **Preview tính giá** (chưa chọn BOM thì hệ thống nhắc mở 📐 trước).

Khi mở rộng dòng, 2 nút **📐 Tham số BOM** và **🖥️ Preview tính giá** nằm ở đầu vùng
mở rộng. Nút hiện ngay khi mở form có dòng sẵn; không nhân đôi khi lưới vẽ lại.

## Vùng "Chọn BOM"

Chọn **BOM** và **BOM Version**. Bên dưới là **Thông tin sản phẩm** — các ô chỉ đọc,
bố cục 2 cột: **BOM**, **Bom Set**, **Variable Set**, **Hệ profile**, **Hãng nhôm**,
**Phụ kiện**. Mỗi ô hiện `tên (mã)`; thiếu dữ liệu hiện **"—"**. Đổi BOM thì các ô này
và vùng tham số **vẽ lại ngay trong cửa sổ** (không mở cửa sổ mới).

## Vùng tham số

- Form tham số sinh tự động từ bộ biến của BOM, bố cục **3 cột**.
- **Biến đầu vào**: kích thước, số cánh, màu, xuất xứ, độ dày, bề mặt… Biến nào là
  thông số tính giá thì **không bắt buộc** — để trống thì hệ thống bỏ qua thông số đó
  khi chọn giá.
- **Biến hệ thống**: hiện đủ tên và giá trị mặc định, **sửa được**; nút
  **↺ Khôi phục mặc định biến hệ thống** trả về giá trị chuẩn.
- Cạnh mỗi biến có thể có dòng ghi nguồn giá trị, ví dụ *"ĐÃ RESOLVE từ …"* hoặc
  *"Default · Resolve … khi chạy BOM"* — cho biết số đang lấy từ đâu.
- Muốn thêm tham số không có trong bộ biến: dùng bảng **Biến mở rộng** (thêm/xoá dòng).
  Cột **Tên biến** chọn từ danh mục biến; chọn xong cột **Kiểu** tự điền.

Đổi bất kỳ tham số nào → hệ thống tự tính lại sau vài giây. Trong lúc chờ có dòng nhắc
vàng: *"Tham số vừa đổi — đang tự động tính lại giá..."*.

## Vùng "Kính theo vị trí"

Mỗi vị trí kính có một ô chọn kính riêng, **luôn có** — kể cả khi BOM không khai mã
kính mặc định.

- Dưới ô chọn có **dòng trạng thái**: *"Đã chọn: …"*, *"Đang dùng mã cố định trên BOM:
  … · Đổi được nếu khách chọn kính khác."*, *"Đang áp dụng kính mới — tự tính lại giá
  sau giây lát"*, hoặc *"Chưa có mã kính — chọn kính cho vị trí này"*.
- Dòng thứ hai là **giá** của mã kính đang chọn: *"Giá: …"*; giá tạm tính có dấu **≈**
  kèm *"(giá chốt khi tính lại xong)"*; chưa có giá thì ghi rõ lý do.
- Đổi mã kính → giá cạnh ô đổi ngay, cả dòng tự tính lại.
- Xoá trắng ô → hệ thống hiện lại mã đang thực sự dùng (mã cố định của BOM) để bạn
  không bị "ô trống mà vẫn ra giá".

Chi tiết xử lý sự cố kính: `docs/usage/tinh-gia-bao-gia.vi.md` §8.

## Vùng "Màu sắc"

Nhóm theo loại vật tư (Nhôm / Kính / Phụ kiện / Vật tư phụ). Mỗi vị trí có màu cấu
hình riêng thì có một ô chọn màu; vị trí dùng màu cố định thì không hiện ô.

## Bảng kết quả

Cửa sổ 📐 và cửa sổ 🖥️ dùng **cùng một kiểu bảng**:

1. **Tóm tắt**: giá bán (chưa VAT), giá có VAT, số dòng vật tư.
2. **Chi tiết vật tư** (gập được) — 11 cột: **Mã vật tư · Tên vật tư · Rộng (mm) ·
   Cao (mm) · Số lượng · Trọng lượng · Khối lượng · ĐVT · Đơn giá · Thành tiền ·
   Nhóm chi phí**.
   - **Trọng lượng** chỉ hiện với nhôm/thép/inox; loại khác hiện **"—"**.
   - **Khối lượng** và **ĐVT** theo cách tính số lượng của vật tư đó (kg / m / m² /
     cái…).
3. **Tổng theo nhóm chi phí** (gập được): từng nhóm với tên tiếng Việt.
4. **Chi phí chế tạo** (gập được) — 5 cột: **Khoản mục · Công thức · Diễn giải ·
   Giá trị · ĐVT**. Dòng tổng được in đậm, nền vàng. Cột **Diễn giải** ghi từng bước,
   ví dụ *"8% × TONG_VL(1.000.000) = 80.000"*.

Mỗi dòng vật tư có nút **"Vì sao ra số này?"** — mở bảng giải thích đúng kết quả đang
hiện, kể cả khi chưa lưu.

Với dòng có số lượng tính theo quy tắc (bản lề, keo, nẹp…), bảng kết quả hiện sẵn
**một dòng căn cứ nhỏ ngay dưới tên vật tư** (ví dụ *“Chọn số lượng theo quy tắc
‘Số bản lề theo chiều cao’: Chiều cao = 3200 mm → 4 × số cánh 2 = 8.”*), không cần
bấm gì. Bấm **?** để mở bảng giải thích đầy đủ, trong đó có bước **“Quy tắc tính
số lượng”**: chiều cao (hoặc giá trị) đem tra, kết quả mỗi cánh, và hệ số nhân
(ví dụ số cánh).

Cửa sổ **🖥️ Preview tính giá** bổ sung công thức và phần giải thích chi tiết cho từng
dòng chi phí. Với kết quả vừa tính, đầu cửa sổ nhắc *"Kết quả chỉ để xem — chưa ghi vào
báo giá…"*; 2 nút **Áp dụng vào dòng** / **Đóng**. Nút Áp dụng **mờ khi chưa có kết quả**.

## BOM lớn — tính trong nền

- BOM nhỏ/vừa: tính ngay, kết quả hiện tức thì.
- BOM lớn: hệ thống xếp hàng tính trong nền, cửa sổ hiện khung chờ. Kết quả **tự hiện**
  khi xong, **chỉ khi cửa sổ còn mở**; kèm thông báo xanh dương
  *"Tính giá xong — chưa lưu vào báo giá."*
- Đóng cửa sổ trước khi có kết quả: cửa sổ **không tự bật lại**. Mở lại bằng **🖥️**.
- Chờ lâu không thấy: đóng cửa sổ rồi bấm lại nút tính giá.

## Lưu ý

- Giá tính theo **BOM Version đã chốt**: đổi cấu hình BOM sau đó không làm đổi giá báo
  giá đã chốt.
- Không sửa tay các ô giá và bảng kết quả trên dòng — đó là số hệ thống tính.
- Bản ghi tái lập (`ConfigSnapshot`) chỉ tạo khi **gửi duyệt** báo giá; lúc tính giá
  hoặc xem trước thì không tạo.
- Quy tắc "khi nào số được ghi vào báo giá", "in thì hỏi gì": xem tệp chuẩn
  `docs/usage/tinh-gia-bao-gia.vi.md`.
