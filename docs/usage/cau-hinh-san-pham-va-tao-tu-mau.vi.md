# Cấu hình sản phẩm và tạo sản phẩm từ mẫu

> **Dành cho:** người cấu hình BOM (BOM Manager) và quản trị kỹ thuật.
> **Ngày:** 2026-11-27 · **Phạm vi:** app `alumglass`.
> **Trạng thái kiểm chứng:** viết từ mã trong working tree; **chưa mở trên site** (máy soạn
> không có site cài `alumglass`). Nếu màn hình khác mô tả, đối chiếu
> [../ops/cap-nhat-ma-va-cache.md](../ops/cap-nhat-ma-va-cache.md) trước khi kết luận tài liệu sai.

---

## 1. Xem nhanh một sản phẩm đang dùng cấu hình gì

Mở **AL BOM** của sản phẩm → nút **"Cấu hình sản phẩm"** (mở trang `al-product-config`).

Trang gom 7 khối, **chỉ đọc**:

| Khối | Cho biết |
|---|---|
| Sản phẩm | mã, tên, trạng thái version hiện tại |
| Bộ BOM | bộ dòng BOM sản phẩm đang dùng |
| Bộ phụ kiện | bộ phụ kiện đi kèm |
| Bộ biến | bộ biến người dùng nhập |
| Mẫu tính giá | mẫu tính giá đang gắn |
| Hồ sơ biến | hồ sơ quyết định biến nào hiện trong gợi ý |
| Quy tắc đang dùng | các `AL Rule` mà cấu hình này dùng |

Mỗi khối có **ba trạng thái khác nhau**:

| Trạng thái | Nghĩa | Nút |
|---|---|---|
| **Đọc được** (xanh) | có dữ liệu | **Mở** form tương ứng |
| **Chưa gắn** (xám) | sản phẩm chưa nối tới bộ đó — việc bình thường, chưa phải lỗi | **Mở sản phẩm để gắn** |
| **Không đọc được** (cam) | đọc lỗi, hoặc bản ghi đã bị xoá | **Tải lại** |

Khối lỗi không làm hỏng các khối khác. Bấm **Tải lại** ở góc phải tiêu đề để đọc lại toàn bộ
(sau khi sửa ở form khác rồi quay về, trang cũng tự đọc lại).

> Trang **không sửa được gì**. Sửa vẫn làm ở form gốc (đúng một nơi chứa dữ liệu).

---

## 2. Tạo sản phẩm mới từ một bộ mẫu

1. Mở **AL Bom Set** của bộ mẫu (ví dụ bộ cửa đi 2 cánh).
2. Bấm **"Tạo sản phẩm từ bộ này"**.
3. Nhập **tên mới**; **mã mới có thể để trống** — máy tự đặt mã chưa trùng (`…-MOI2`, `…-MOI3`…)
   và hiện mã đó trong kế hoạch. Muốn mã riêng thì nhập tay; mã trùng ⇒ hệ thống báo và
   **không tự thêm số**.
4. Xem **kế hoạch**: sẽ tạo bộ nào, bao nhiêu dòng, cảnh báo (nếu có) → bấm xác nhận.
5. Hệ thống tạo **bộ độc lập** (Bộ BOM + Bộ phụ kiện + Bộ biến + Bộ giá nếu bộ mẫu có trỏ) và
   mở ngay bộ BOM mới để sửa vài ô.

Điều cần biết:

- Bộ mới **không dính** bộ mẫu: sửa bộ mới không đổi bộ mẫu và ngược lại.
- Mỗi bộ đều ghi **"được tạo từ … lúc …"** để sau này biết bộ nào là gốc.
- Nếu bộ mẫu có dùng **bộ giá**, bộ giá mới được tạo nhưng liên kết bộ giá nằm trên **AL BOM** —
  mở AL BOM của sản phẩm mới và trỏ sang bộ giá mới (kế hoạch có nhắc việc này).
- Bấm xem trước rồi đóng hộp thoại thì **không có gì được tạo**.

---

## 3. Khi biến đổi kiểu: ô giá trị đổi theo

Trong **AL Variable Set** (bảng "Variables") và ô **Default Value** của **AL Variable Library**,
ô giá trị hiện theo kiểu đã khai:

| Kiểu | Ô hiện ra |
|---|---|
| Select | danh sách chọn đúng lựa chọn đã khai |
| Link | chọn bản ghi của đúng doctype đã khai |
| Float / Int / Currency / Percent | ô nhập số |
| Check | ô đánh dấu |
| Data | ô nhập chữ |

Nếu biến Select **chưa khai lựa chọn** (hoặc Link chưa khai doctype), ô vẫn là ô chữ và hệ thống
**không chặn** — khai xong rồi Lưu là ô đổi ngay. Đây là cố ý: dựng ô chọn rỗng sẽ khoá người
dùng mà không nói vì sao.

---

## 4. Câu cảnh báo mới khi tính giá

Nếu lần tính báo *"Biến hệ '…' chưa có nguồn giá trị"*: mở `AL Variable Library` → kiểm
**Source Doctype / Source Field** của biến, hoặc khai `Formula Variable Binding`, hoặc đặt giá trị
trong `AL Profile System.system_variables`.

Hệ thống **không còn tự lấy số từ `AL Rule`** khi biến thiếu nguồn. Nếu một báo giá đổi số sau khi
cập nhật, chỗ đổi chính là chỗ trước đây đang dùng con số tự lấy — đối chiếu 2 mốc giá chuẩn trước
khi gửi khách.
