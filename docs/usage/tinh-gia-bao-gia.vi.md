---
title: "Tính giá báo giá — hướng dẫn dùng"
contexts:
  - "Form/Quotation"
  - "Form/Quotation Item"
tags: [sales-crm]
doc_type: doctype
---

# Tính giá báo giá

> Dành cho người lập báo giá (kế toán / kỹ thuật). Đây là hướng dẫn chính cho luồng
> tính giá; các trang khác chỉ dẫn về đây.
>
> Chi tiết từng ô trên màn hình: `docs/usage/bom-calculation-dialog.vi.md`.
> Lý do kỹ thuật (dành cho người bảo trì): `docs/design/preview-khong-ghi-db.md`.

## Điều quan trọng nhất — đọc 30 giây

1. **Tính giá chỉ là xem trước.** Số vừa tính chỉ nằm **trên màn hình**.
2. **Muốn giữ số: bấm `Lưu` trên báo giá.** Chưa bấm `Lưu` thì báo giá vẫn là bản cũ.
3. **Tải lại trang hoặc đóng tab là mất kết quả vừa tính** — kể cả tham số vừa sửa.
   Với báo giá **chưa lưu lần nào**, tải lại trang mất **toàn bộ nội dung vừa nhập**.
4. **In khi còn số chưa lưu:** in **từ màn hình báo giá** thì hệ thống hỏi bạn `Lưu rồi in`
   hoặc `Huỷ` — để bản in chắc chắn khớp số đang hiện. In từ danh sách / in hàng loạt
   **không hỏi** — xem §7.

## Tra nhanh

- Đang bị **chặn Lưu** → §6 (hệ thống tự tính lại) và §8 (câu lỗi cụ thể).
- Cần **in hoặc gửi** báo giá → §7.
- Tính xong **không thấy số** → §8.
- Đang ở **báo giá đã gửi khách / đã huỷ** → §8.

## 1. Tính giá một dòng

1. Mở **báo giá** cần tính.
2. Tại dòng hàng, bấm nút **📐** ở góc phải ô mã hàng (hoặc **bấm đúp** vào dòng).
   Cũng có thể mở rộng dòng rồi bấm **📐 Tham số BOM**.
3. Chọn **BOM** và **BOM Version**. Điền tham số sản phẩm (kích thước, màu, xuất xứ,
   độ dày, bề mặt…).
4. Ngừng sửa khoảng vài giây — hệ thống **tự tính lại**. Trong lúc chờ, bảng kết quả
   hiện dòng nhắc vàng: *"Tham số vừa đổi — đang tự động tính lại giá..."*.
5. Xem kết quả ngay trong cửa sổ. Muốn xem cửa sổ lớn: bấm **🖥️ Preview tính giá**.
6. Bấm **Áp dụng vào dòng** để đưa tham số **và kết quả** xuống dòng hàng (vẫn chưa
   lưu báo giá). Cửa sổ đóng, hiện thông báo xanh dương:
   *"Đã áp dụng tham số vào dòng này — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá
   để lưu."*
   Dòng mới: *"Đã thêm dòng vào phiếu — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá
   để lưu."*
7. Bấm **Lưu** trên báo giá để ghi lại.

**Bấm 🖥️ ở dòng** (không mở 📐) cũng tính giá được ngay. Chưa chọn BOM thì hệ thống
nhắc bạn mở 📐 trước.

**Dòng mới tính được ngay** — không cần lưu báo giá trước.

## 2. "Giá vừa tính chưa lưu" nghĩa là gì

| Bạn đang ở trạng thái | Thấy gì trên màn hình | Bấm `Lưu` thì sao | Tải lại trang thì sao |
|---|---|---|---|
| Vừa tính, **chưa lưu** | Bảng kết quả có dòng nhắc: *"Giá vừa tính chưa được lưu vào báo giá. Bấm nút Lưu ở thanh trên để ghi lại — đóng trang hoặc tải lại là mất kết quả này."* | Số được ghi vào báo giá; dòng nhắc tự tắt | **Mất** kết quả và tham số vừa sửa. Báo giá chưa lưu lần nào: mất **toàn bộ nội dung vừa nhập** |
| **Đã lưu** | Không còn dòng nhắc | Không đổi gì thêm | Vẫn còn số đã lưu |
| **Đang tính trong nền** (BOM lớn) | Khung chờ + câu *"Kết quả chỉ nhận được khi cửa sổ này còn mở…"* | Lưu được ngay — nếu kết quả chưa khớp tham số, hệ thống tự tính lại lúc Lưu (chậm hơn) | Mất; mở lại và bấm **Preview tính giá** để tính lại |

Cách phân biệt nhanh trong luồng tính giá: **thông báo xanh dương = số mới chỉ ở
trên màn hình**; đã ghi vào báo giá thì không còn lời nhắc nào.

**Bấm `Lưu` khi một dòng còn đang tính nền:** nếu kết quả mới chưa về, lúc Lưu hệ thống
tự kiểm tra — tham số đã đổi (hoặc dòng chưa có kết quả) thì tự tính lại trước khi ghi,
nên bạn **không bị lưu giá cũ**; chỉ chậm hơn. Tốt nhất vẫn chờ kết quả về rồi mới `Lưu`.

## 3. Xem kết quả chi tiết và "Vì sao ra số này?"

Kết quả gồm 4 phần:

- **Tóm tắt**: giá bán (chưa VAT), giá có VAT, số dòng vật tư.
- **Chi tiết vật tư**: từng món với kích thước, số lượng, khối lượng, đơn vị, đơn giá,
  thành tiền và nhóm chi phí.
- **Tổng theo nhóm chi phí**: vật liệu nhôm, vật liệu kính, vật tư phụ…
- **Chi phí chế tạo**: từng khoản mục, công thức, **diễn giải** và giá trị.

**"Vì sao ra số này?"** — bấm nút hỏi nhỏ cạnh tên vật tư trong bảng chi tiết. Hệ thống
mở bảng giải thích từng bước: mã vật tư → số lượng → đơn giá → thành tiền.
Giải thích **luôn theo kết quả đang hiện trên màn hình**, kể cả khi bạn chưa lưu.
Nếu chưa lấy được căn cứ: bấm **Thử lại**; nếu không có quyền xem: hệ thống báo rõ và
bạn liên hệ quản trị.

Trong cửa sổ **🖥️ Preview tính giá** có đúng 2 nút:

- **Áp dụng vào dòng** — đưa kết quả đang hiện xuống dòng hàng. Nút **mờ khi chưa có
  kết quả**, **bật khi đã có kết quả**.
- **Đóng** — đóng cửa sổ, không đổi gì.

Với kết quả vừa tính, đầu cửa sổ nhắc: *"Kết quả chỉ để xem — chưa ghi vào báo giá. Bấm
"Áp dụng vào dòng" nếu muốn dùng kết quả này."*

## 4. Đổi mã kính — giá hiện ngay cạnh ô chọn

Mỗi vị trí kính có một ô chọn kính riêng. Ngay **dưới ô chọn** có 2 dòng:

- **Trạng thái** — ví dụ *"Đã chọn: Kính Low-E 24 (KINH-LOWE-24)"*, *"Chưa có mã kính —
  chọn kính cho vị trí này"*, hoặc *"Đang áp dụng kính mới — tự tính lại giá sau giây lát"*.
- **Giá** — *"Giá: 1.234.567 đ"*. Giá tạm tính hiện dấu **≈** kèm câu
  *"(giá chốt khi tính lại xong)"*.

Đổi mã kính: giá cạnh ô tự cập nhật, sau đó hệ thống tự tính lại toàn dòng (không phải
bấm gì thêm).

- Lần **tự tính** mà lỗi: bảng kết quả hiện đỏ **"Tính giá thất bại"** kèm câu lỗi và lối
  thử lại.
- Bấm **Áp dụng vào dòng** mà lần tính lại ngay trước đó chưa xong: hiện câu cam
  *"Chưa tính lại được giá kính — dòng đang giữ giá cũ…"* — xem cách xử lý ở §8.

Nếu ô giá ghi **"Chưa có giá — kiểm tra bảng giá đang áp dụng"**, mã kính đó chưa có
giá trong bảng giá — báo người phụ trách bảng giá, đừng chọn mã khác cho xong.
Dòng mới chưa lưu lần nào: ô giá ghi *"Giá hiện sau khi lưu dòng và hệ thống tính
lại."* — bấm **Áp dụng vào dòng** rồi **Lưu**, mở lại sẽ thấy giá.

## 5. Tính giá hàng loạt

1. Mở báo giá cần tính.
2. Menu **AlumGlass → Tính giá**.
3. Hệ thống kiểm từng dòng **trước khi tính**. Nếu có dòng thiếu thông tin, hộp cảnh
   báo liệt kê rõ: *"Dòng 3 (…): chưa chọn BOM"*, *"chưa nhập tham số (mở Tham số BOM và
   bấm Áp dụng vào dòng)"* — và **chưa tính dòng nào cả**. Bổ sung đủ rồi bấm
   **AlumGlass → Tính giá** lại.
4. Tính xong, thông báo: *"Đã tính X/Y dòng — chưa lưu vào báo giá. Bấm Lưu để ghi
   lại."* (xanh dương). Có dòng lỗi: thông báo **đỏ** kèm số dòng lỗi.
5. Bấm **Lưu** trên báo giá.

Dòng mới cũng được tính. BOM lớn tính trong nền — cứ để trang báo giá mở (đừng tải lại
trang, đừng đóng tab), kết quả tự về dòng.

Nút **AlumGlass → Preview giá** chỉ để xem lại toàn báo giá; nó **không dựng được chi
tiết cho dòng chưa lưu** — hệ thống sẽ ghi *"{n} dòng chưa lưu trên báo giá nên chưa
tính — mở 📐 Tham số BOM để tính."*

## 6. Lưu báo giá — cái gì được ghi, khi nào

**Chỉ khi bạn bấm `Lưu` trên báo giá**, hệ thống mới ghi lại:

- tham số và mã kính bạn đã chọn cho từng dòng;
- mã hàng / tên hàng lấy từ BOM;
- giá bán, giá có VAT và bảng tính chi tiết của dòng.

Gửi khách là bước sau khi đã lưu — hãy `Lưu` trước khi gửi.

Trước khi lưu, hệ thống so **tham số đang lưu** với **tham số lúc tính**:

- Khớp → lưu ngay.
- **Lệch** (bạn sửa tham số sau khi tính, **hoặc dòng chưa từng tính**) → hệ thống
  **tự tính lại dòng đó** rồi mới lưu. Bạn không phải tính tay.
- Tính lại không được → **chặn lưu**, báo:
  *"Dòng 3 (Khung nhôm 55): không tính lại được giá theo tham số mới. Mở "Tham số BOM"
  của dòng này, bấm "Preview tính giá" rồi lưu lại."*
  Làm đúng theo câu đó rồi bấm `Lưu` lại.

Mẹo: tính xong thì bấm **Áp dụng vào dòng** + **Lưu** ngay, đừng để lâu rồi sửa tiếp.

## 7. In và gửi báo giá

**In từ màn hình báo giá** khi còn số chưa lưu: hệ thống mở hộp thoại chặn mềm.

| Thành phần | Nội dung |
|---|---|
| Tiêu đề — báo giá đã lưu | *"Báo giá có giá vừa tính chưa lưu"* |
| Tiêu đề — báo giá chưa từng lưu | *"Báo giá chưa được lưu"* |
| Nội dung | *"Bạn vừa tính lại giá nhưng chưa lưu báo giá. Lưu báo giá rồi in để bản in chắc chắn khớp số trên màn hình."* |
| Nút chính | **Lưu rồi in** — lưu xong mới in đúng bản in bạn vừa chọn |
| Nút phụ | **Huỷ** — không lưu, không in |

Đóng hộp thoại bằng **X / Esc / bấm ra ngoài** cũng coi như **Huỷ**; lần in sau vẫn
hỏi lại (không bị kẹt).

**Lưu thất bại** → không in, kèm câu hướng dẫn:

- Báo giá **đã lưu**: *"Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi bấm Lưu
  lại. Nếu chỉ cần in bản đã lưu thì tải lại trang (kết quả vừa tính sẽ mất)."*
- Báo giá **chưa từng lưu**: *"Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi
  bấm Lưu lại — báo giá chưa được lưu lần nào, tải lại trang sẽ mất toàn bộ nội dung
  vừa nhập."*

Báo giá **không còn** số chưa lưu → in ngay, không hỏi.

**Giới hạn cần biết (đừng trông đợi hơn):**

- Hộp thoại **Lưu rồi in** chỉ có khi in **từ màn hình báo giá**.
- In **từ danh sách**, **in hàng loạt**, hoặc **mở link in trực tiếp** — **chưa có**
  lớp hỏi này.
- **Gửi email** báo giá — **chưa có** lớp kiểm.
- Vì vậy: muốn bản in/gửi đi chắc chắn khớp số trên màn hình, hãy bấm **Lưu** trước.

## 8. Sự cố thường gặp → cách xử lý

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Tải lại trang, kết quả vừa tính biến mất | Tính giá chỉ nằm trên màn hình; chưa bấm `Lưu` | Mở lại 📐 Tham số BOM, điền lại tham số, bấm **Áp dụng vào dòng** rồi **Lưu**. Báo giá chưa lưu lần nào: tải lại trang mất toàn bộ nội dung vừa nhập. |
| Đã đổi **BOM Version** trong 📐, **tải lại trang** (hoặc rời trang) rồi mở lại vẫn thấy version cũ | Chưa bấm **Lưu** trên báo giá — thay đổi mới chỉ nằm trên màn hình, tải lại trang là mất | Chọn lại version trong 📐 (chọn xong là hệ thống ghi xuống dòng ngay — **đóng rồi mở lại cửa sổ** thì vẫn thấy version mới), rồi bấm **Lưu** trên báo giá. Sau khi Lưu, giá là giá của version mới nên **có thể khác số bạn vừa thấy** — hệ thống tự kiểm và tính lại khi Lưu. |
| Đã **Lưu** báo giá mà mở lại dialog vẫn thấy **BOM Version** cũ | Giao diện báo giá còn là bản cũ (chưa nhận bản sửa mới) | Nếu có **thông báo cam** *"Giao diện báo giá chưa phải bản mới nhất"*: báo quản trị cập nhật giao diện rồi tải lại trang. Thông báo này chỉ hiện **một lần mỗi phiên làm việc** — không thấy thì mở tab mới rồi mở lại báo giá để kiểm. |
| Mở lại 📐 thấy ô ⏳ *"Tham số vừa đổi — đang tính lại giá"* thay cho bảng giá (ô xám; lúc đang chờ có thể kèm dòng nhắc vàng) | Bạn vừa đổi tham số (BOM Version, BOM, kính, biến, cấu hình…); số còn nằm trên dòng là giá của tham số **cũ** | Chờ vài giây — hệ thống tự tính lại rồi bảng giá tự hiện. Không thấy đổi sau khoảng 10 giây: bấm **🖥️ Preview tính giá**. Đây không phải lỗi, nên không có nút báo hỏng. |
| Nút **Áp dụng vào dòng** trong cửa sổ 🖥️ bị mờ | Chưa có kết quả (đang tính, hoặc lỗi) | Chờ tính xong; nếu cửa sổ đã đóng trước khi có kết quả thì bấm lại **🖥️ Preview tính giá**. Vẫn lỗi: xem dòng cảnh báo đỏ, sửa tham số rồi tính lại. |
| Bấm `Lưu` thì bị chặn, báo *"Dòng 3 (…): không tính lại được giá theo tham số mới…"* | Tham số đã đổi so với lúc tính, mà hệ thống không tính lại được | Mở 📐 **Tham số BOM** của đúng dòng đó, bấm **🖥️ Preview tính giá**, xem có lỗi gì (thiếu giá, kích thước bằng 0…), sửa rồi bấm **Áp dụng vào dòng**, sau đó `Lưu` lại. |
| Bấm **Áp dụng vào dòng** mà hiện *"Chưa tính lại được giá kính — dòng đang giữ giá cũ. Mở lại bảng tham số rồi bấm "Preview tính giá" để tính lại."* | Vừa đổi kính; hệ thống chưa tính lại xong (lỗi hoặc quá lâu) | Mở lại 📐 **Tham số BOM**, bấm 🖥️ **Preview tính giá**; thấy kết quả mới rồi bấm **Áp dụng vào dòng** lần nữa. |
| In bị chặn, hiện *"Chưa lưu được báo giá nên chưa in…"* | Báo giá đang có lỗi nên không lưu được | Sửa lỗi vừa hiện rồi bấm `Lưu` lại. Chỉ cần bản in cũ: làm đúng câu hướng dẫn trên hộp thoại. |
| Dòng mới: cạnh ô kính ghi *"Giá hiện sau khi lưu dòng và hệ thống tính lại."* | Dòng chưa có trong báo giá nên chưa tra được giá kính | Vẫn tính giá bình thường. Bấm **Áp dụng vào dòng** rồi `Lưu`; mở lại 📐 sẽ thấy giá kính. |
| Ô giá kính ghi *"Chưa có giá — kiểm tra bảng giá đang áp dụng"* | Mã kính chưa có giá trong bảng giá | Báo người phụ trách bảng giá bổ sung rồi tính lại. **Đừng** đổi mã kính chỉ để hết cảnh báo — báo giá sẽ sai sản phẩm. |
| Thông báo *"Đã tính X/Y dòng…"* nhưng có dòng trên lưới chưa đổi số | Dòng đó đang **tính nền** (kết quả chưa về) hoặc **tính lỗi** (giữ kết quả cũ) | Chờ kết quả nền tự về (giữ trang mở). Nếu lỗi: xem cảnh báo đỏ của dòng, sửa tham số rồi tính lại dòng đó bằng 📐. Sau đó bấm `Lưu`. |
| Tính xong mà không thấy kết quả trong cửa sổ | BOM lớn tính trong nền; kết quả chỉ về khi cửa sổ còn mở | Mở lại **🖥️ Preview tính giá** để xem/tính lại. |
| Không thấy nút 📐/🖥️ và menu **AlumGlass → Tính giá** | Báo giá **đã gửi khách** hoặc **đã huỷ** — số liệu đã chốt nên không cho tính lại | Bấm **Amend** (Sửa) để tạo bản sửa, hoặc tạo báo giá mới, rồi tính trên bản nháp. |
| Hộp đỏ *"Tính giá có lỗi — cần xử lý trước khi chốt báo giá"* | Có dòng vật tư/công thức lỗi (thiếu biến, thiếu giá…), giá dòng đó có thể bằng 0 | Đọc từng dòng trong hộp/bảng kết quả, sửa tham số hoặc bổ sung giá rồi tính lại. Báo giá **vẫn Lưu được**, nhưng số có thể sai — xử lý trước khi gửi khách. |
| Menu **Tính giá** báo *"Chưa thể tính giá — thiếu thông tin"* dù chỉ một dòng thiếu | Lượt tính hàng loạt **dừng cả lượt** khi bất kỳ dòng nào thiếu BOM / BOM Version / tham số. Dòng **cố ý không gắn BOM** sẽ luôn chặn lượt hàng loạt | Bổ sung đủ cho mọi dòng; nếu có dòng không cần tính, dùng **📐** để tính riêng từng dòng thay vì nút hàng loạt. |

## 9. Câu hỏi nhanh

**Tính giá có tự lưu báo giá không?**
Không. Số chỉ nằm trên màn hình cho tới khi bạn bấm `Lưu`.

**Tôi sửa tham số rồi đóng cửa sổ, có sao không?**
Nếu hệ thống đã tự tính lại xong (dòng nhắc vàng đã biến mất, bảng kết quả đã cập nhật) thì
tham số và kết quả đã nằm trên dòng — đóng cửa sổ không mất, nhưng vẫn phải bấm `Lưu` trên
báo giá. Nếu bạn đóng ngay lúc hệ thống chưa kịp tự tính thì tham số vừa sửa bị bỏ —
riêng **BOM Version**: chọn xong là hệ thống ghi xuống dòng ngay, đóng cửa sổ không mất.
Bấm **Áp dụng vào dòng** lúc số đang cũ thì hệ thống tính lại trước rồi mới đóng; nếu không
tính lại được, nó báo rõ và giữ nguyên dấu "số đang cũ" thay vì đóng im lặng.

**Nút nào dùng để đưa kết quả xuống dòng?**
Nút chính trong cửa sổ là **Áp dụng vào dòng** — nó đưa tham số và kết quả xuống dòng;
nút `Lưu` nằm trên thanh của báo giá và là bước ghi lại báo giá.

**Tôi đổi kính, giá có tự đổi không?**
Có. Giá cạnh ô kính đổi ngay, cả dòng tự tính lại sau vài giây.

**Tôi có phải tính lại trước khi bấm `Lưu` không?**
Không. Dòng đã sửa tham số — hoặc chưa từng tính — được hệ thống tự tính lại trước khi lưu.

**In luôn được không?**
Được. In **từ màn hình báo giá** mà còn số chưa lưu thì hệ thống hỏi `Lưu rồi in` / `Huỷ`.
In từ danh sách hoặc in hàng loạt thì không hỏi — hãy `Lưu` trước.

**In từ danh sách có hỏi lưu trước khi in không?**
Chưa. Lớp hỏi chỉ có khi in từ màn hình báo giá — hãy `Lưu` trước.

**Gửi email báo giá có kiểm tra số chưa lưu không?**
Chưa. Hãy `Lưu` trước khi gửi.

## Xem thêm

- Từng ô trên màn hình, bảng kết quả, biến mở rộng: `docs/usage/bom-calculation-dialog.vi.md`
- In báo giá: `docs/usage/bao-gia-print-format.vi.md`
- Vì sao tính giá không ghi vào báo giá (dành cho người bảo trì):
  `docs/design/preview-khong-ghi-db.md`
