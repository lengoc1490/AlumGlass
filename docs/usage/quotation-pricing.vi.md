---
title: "Tính giá báo giá nhôm kính (Quotation Pricing)"
contexts:
  - "Form/Quotation Item"
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# Tính giá báo giá nhôm kính

> **Hướng dẫn dùng đầu-cuối (tệp chuẩn):** `docs/usage/tinh-gia-bao-gia.vi.md`.
> Trang này chỉ tóm tắt đường vào và cách xử lý khi có lỗi. ⛔ Không chép lại
> hướng dẫn ở tệp chuẩn.
>
> Kiến trúc và lý do kỹ thuật: `docs/design/quotation-pricing.md` ·
> `docs/design/preview-khong-ghi-db.md`.

## Mô tả

Mỗi dòng hàng của **báo giá** gắn với một **BOM** và một **BOM Version đã chốt**. Khi
tính giá, hệ thống bóc BOM thành từng dòng vật tư, tính khối lượng và thành tiền, gom
theo nhóm chi phí, rồi chạy bảng chi phí chế tạo để ra **giá bán** và **giá có VAT**.

**Tính giá không ghi vào báo giá.** Số chỉ nằm trên màn hình cho tới khi bạn bấm
`Lưu` trên báo giá. Chi tiết: tệp chuẩn ở trên.

## Đường vào

- **Từng dòng:** **📐 Tham số BOM** (hoặc bấm đúp vào dòng, hoặc mở rộng dòng) —
  nhập tham số, xem kết quả, bấm **Áp dụng vào dòng**.
- **Tính nhanh một dòng:** **🖥️ Preview tính giá** ở dòng — mở cửa sổ kết quả chỉ để
  xem, có nút **Áp dụng vào dòng** / **Đóng**.
- **Cả báo giá:** menu **AlumGlass → Tính giá** (tính hàng loạt, kể cả dòng mới) và
  **AlumGlass → Preview giá** (xem lại toàn báo giá).

Kết quả gồm: giá bán, giá có VAT, chi tiết từng dòng vật tư, tổng theo nhóm chi phí và
bảng chi phí chế tạo có diễn giải từng bước. Mỗi dòng vật tư có nút
**"Vì sao ra số này?"**.

## Khi có lỗi tính toán

- Một dòng vật tư hoặc một công thức lỗi (ví dụ thiếu biến) → dòng đó nhận giá trị `0`
  và lỗi được ghi lại; **các dòng khác vẫn tính bình thường**, không hỏng cả báo giá.
- **Chia cho 0** luôn báo lỗi dừng. Kiểm tra tham số vừa nhập (kích thước bằng 0, đơn
  giá thiếu…) rồi tính lại.
- Cửa sổ kết quả hiện câu lỗi đọc được và nút **Thử lại**; chi tiết kỹ thuật chỉ nằm
  trong mục gập *"Chi tiết kỹ thuật (gửi cho quản trị khi cần)"*.
- Lỗi còn được ghi ở **Error Log** để quản trị tra khi cần.

## BOM lớn — tính trong nền

- BOM nhỏ/vừa: tính đồng bộ, kết quả hiện ngay.
- BOM lớn: xếp hàng tính trong nền; kết quả tự hiện khi xong, **chỉ khi cửa sổ còn
  mở**. Câu nhắc trên cửa sổ: *"Kết quả chỉ nhận được khi cửa sổ này còn mở — nếu
  không thấy, bấm 'Preview tính giá' để tính lại."*
- Đóng cửa sổ giữa chừng → mất kết quả đang chờ; mở lại và bấm tính lại.

## Lưu ý

- Giá tính theo **BOM Version đã chốt**: đổi cấu hình BOM sau đó không làm đổi giá báo
  giá đã chốt.
- Không sửa tay các ô giá và bảng kết quả trên dòng — đó là số hệ thống tính.
- In báo giá: xem `docs/usage/bao-gia-print-format.vi.md`; quy tắc hỏi lưu trước khi in
  nằm ở tệp chuẩn `docs/usage/tinh-gia-bao-gia.vi.md` §7.
