# AL Variable Profile — tra cứu đầy đủ mọi lựa chọn
>
> 🔴 **Cập nhật 2026-11-27 (B2/R3):** `AL Variable Settings` **đã ngừng dùng**. Ba loại biến nay nằm
> trong **`AL Variable Library`**: biến người dùng nhập = bật **“Người dùng nhập”** (`is_input`);
> biến theo dòng = **Category = “Row Literals”**; còn lại = biến cấu hình. `default_profile` →
> **`AL Variable Profile.is_default`**; `preview_doctype` → **`AL Variable Profile.preview_doctype`**.
> Mọi câu bên dưới nhắc “mở `AL Variable Settings`” là **lịch sử** — trạng thái hiện tại xem
> [thiết kế gộp cấu hình](../design/gop-noi-cau-hinh-bien-va-tinh-toan.md).


> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App / nhánh | `alumglass` — nhánh `main`, HEAD `566cdc2` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | `AL Variable Profile`, `AL Variable Profile Rule`, `AL Variable Cross Row`: ngữ nghĩa từng field, 11 nguồn biến, thuật toán áp rule, biến chéo dòng, cách resolve và cách kiểm |
> | Ngoài phạm vi | Thao tác UI từng bước → [huong-dan-setting-bien.md](huong-dan-setting-bien.md); chẩn đoán sự cố → [troubleshooting.md](troubleshooting.md); engine tính ra tiền → [../huong-dan-tinh-gia-full-flow.md](../huong-dan-tinh-gia-full-flow.md) |
> | Đối tượng | BOM Manager / admin cấu hình (mặc định là `System Manager`) và DEV bảo trì |
> | Mức kiểm chứng | Đọc từ **mã trong working tree**. Chưa chạy `bench migrate`, chưa mở form. Mọi "bạn sẽ thấy" là suy ra từ mã, chưa phải ảnh chụp màn hình |
> | Ngày soạn | 2026-11-13 |

Bài này là bản tra cứu. Nó trả lời câu hỏi "field này nhận gì, chọn cái nào thì ra kết quả gì".
Nó không dạy từng cú bấm; các bước bấm nằm ở bài hướng dẫn UI đã dẫn trên.

**Mục lục**

0. Một câu phải nhớ
1. Khi nào dùng, khi nào không
2. Quan hệ với sáu DocType còn lại
3. Ba DocType của profile, đầy đủ từng field
4. Mười một nguồn biến (`source_kind`)
5. Thuật toán áp rule, giải thích cho người cấu hình
6. `default_action` và bốn tổ hợp
7. Biến chéo dòng (`cross_row`)
8. Profile được chọn thế nào, áp cho những đâu
9. Kiểm tra: xem trước, giải thích, API
10. Bốn ví dụ cấu hình hoàn chỉnh
11. Mười một kiểu cấu hình sai thường gặp
12. Quy trình kiểm trước khi đóng job
13. Giới hạn đã biết
14. Đọc tiếp

---

## 0. Một câu phải nhớ

**Profile chỉ lọc danh sách gợi ý. Nó không đổi giá trị tính toán, không đổi số tiền.**

Ba hệ quả kéo theo, phải nhớ cùng:

1. Công thức dùng biến **ngoài** profile vẫn lưu được và vẫn chạy đúng. Validate dùng
   "vũ trụ biến đầy đủ", không dùng danh sách đã lọc.
2. Sửa hoặc xoá profile **không làm đổi** một BOM đã tính. Nếu bạn thấy số tiền đổi sau khi
   sửa profile, nguyên nhân nằm ở chỗ khác.
3. Profile không phải phân quyền. Nó không ngăn người ta gõ biến bị loại; nó chỉ không gợi ý.

---

## 1. Khi nào dùng, khi nào không

### 1.1 Dùng khi

| Việc bạn muốn | Profile làm được? | Cách làm |
|---|---|---|
| Bớt biến rối khi gõ công thức ở một loại chứng từ | Có | Tạo profile riêng cho loại đó, chọn `EXCLUDE_ALL` rồi Include đúng nguồn cần |
| Gom biến thành nhóm có thứ tự đọc được | Có | Đặt **Nhóm hiển thị** (`group_label`) và **Thứ tự nhóm** (`sort_order`) trên rule |
| Mỗi field công thức thấy một danh sách khác nhau | Có, có điều kiện | Tách biến giữa nhiều rule bằng `source_ref`, mỗi rule khai **Chỉ hiện ở field** (`only_fields`) — xem mục 5.4 và ví dụ 4 |
| Chỉ gợi ý biến đang có giá trị thật | Có | Bật **Bắt buộc có giá trị** (`require_value`) trên rule Include |
| Gợi ý biến chéo dòng `items.<slug>.<field>` | Có | Khai bảng **Cross Row** — xem mục 7 |
| Ẩn một nguồn cụ thể mà không xoá dữ liệu | Có | Rule `Exclude` đúng `source_kind` và `source_ref` |
| Gán bộ biến mặc định cho bản ghi mới | Có, một phần | Patch chỉ gán cho bản ghi **đang trống** lúc migrate; bản ghi tạo sau phải chọn tay |

### 1.2 Không nên dùng khi

| Ý định | Vì sao sai | Làm gì thay thế |
|---|---|---|
| "Ẩn biến hỏng để người dùng khỏi thấy" | Profile không sửa giá trị. Biến vẫn tính ra 0 hoặc rỗng, chỉ là không ai thấy để sửa | Sửa nguồn biến, hoặc sửa engine |
| "Chặn người dùng gõ biến ngoài profile" | Validate cố ý dùng vũ trụ đầy đủ; profile không có quyền chặn | Chấp nhận, hoặc siết validate ở tầng khác (có chủ đích, có test) |
| "Phân quyền ai thấy biến nào" | Không có cơ chế này. Profile áp theo chứng từ, không theo người | Dùng quyền DocType/role |
| "Giảm tải máy chủ" | `explain_variable` còn chạy **tất cả** adapter, chậm hơn cả không dùng profile | Giữ profile gọn, tránh gọi explain theo từng lần gõ |
| "Đổi cách tính giá" | Profile không nằm trong runtime | Sửa cấu hình engine / công thức |

### 1.3 Ranh giới ba tầng, đừng lẫn

| Tầng | Câu hỏi nó trả lời | DocType / mã |
|---|---|---|
| Field nào có autocomplete công thức? | Ô này có gợi ý hay không | `AL Formula Field` (sổ đăng ký field) |
| Gợi ý những biến nào? | Gõ vào thì thấy danh sách gì | `AL Variable Profile` (bài này) |
| Biến có giá trị bao nhiêu lúc chạy? | Con số thật khi tính giá | Engine B0–B7 + cấu hình nguồn biến |

Ba tầng độc lập. Thêm một dòng `AL Formula Field` không làm profile có thêm biến.
Thêm rule vào profile không làm field lạ có autocomplete.

---

## 2. Quan hệ với sáu DocType còn lại

| DocType | Vai trò | Profile có đọc trực tiếp? | Ghi chú |
|---|---|---|---|
| `AL Variable Profile` | Bộ lọc + nhóm biến theo ngữ cảnh | Chính nó | Có bảng con Rule và Cross Row |
| `AL Variable Settings` (Single) | **ĐÃ NGỪNG DÙNG từ 2026-11-27** — dữ liệu đã chuyển sang `AL Variable Library` (3 loại) và `AL Variable Profile` (`is_default`, `preview_doctype`) | Không (chỉ đọc khi site chưa migrate) | Chỉ còn để lùi một chu kỳ; form hiện banner chỉ chỗ mới |
| `AL Formula Field` | Sổ đăng ký "field nào dùng công thức" | Không | Độc lập hoàn toàn. Hai cơ chế không nhìn thấy nhau |
| `AL Variable Library` | Kho biến hệ thống và biến người dùng | Có, qua adapter `variable_library_system` / `variable_library_user` | `is_system=1` là biến hệ thống; `=0` là biến người dùng |
| `AL Variable Set` | Bộ biến gắn với sản phẩm / bộ BOM / bộ phụ kiện | Có, qua adapter `variable_set` | Rule có thể khai mã set cụ thể; mã đó được adapter nạp **thêm** ngoài set tự dò |
| `Formula Global Variable` | Hằng số dùng chung toàn hệ | Có, qua adapter `formula_global` | Chỉ bản ghi `is_active=1` |
| `Formula Variable Binding` | Binding của Formula Builder theo doctype / field | Có, qua adapter `fvb_scope` | Nguồn duy nhất có phạm vi field riêng (`applies_to_field`) |

**Điều dễ lẫn nhất:** dòng `AL Variable Library` bật **Người dùng nhập** (`is_input`) **không** tự nuôi
dialog "Tham số BOM". Dialog đó đọc `AL Variable Set` và biến hệ thống của Library. Cờ `is_input`
chỉ đăng ký **tên biến** cho gợi ý và cho validate; giá trị đến từ chỗ khác. Cùng lý do với `row_literals`:
đăng ký tên, không tạo giá trị. Chi tiết đường đi của từng biến:
[nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md).

---

## 3. Ba DocType của profile, đầy đủ từng field

### 3.1 `AL Variable Profile`

Tên record chính là **Mã profile** (`profile_code`): DocType đặt `autoname = field:profile_code`,
cho phép đổi tên, và trường này là duy nhất.

| fieldname | Nhãn trên form | Kiểu | Bắt buộc | Mặc định | Lựa chọn / ý nghĩa |
|---|---|---|---|---|---|
| `profile_code` | Mã profile | Data | Có | — | Cũng là tên record. Nên viết HOA, có tiền tố nhóm: `P_BOM_DEFAULT`, `P_COST_TEMPLATE_DEFAULT` |
| `profile_name` | Tên profile | Data | Có | — | Tên người đọc. Hiện trong kết quả API ở khoá `profile.name` |
| `is_active` | Đang dùng | Check | Không | 1 | Tắt ⇒ `_load_profile` trả `None` ⇒ **coi như chưa từng có profile**: resolve rơi xuống bước kế tiếp (default, rồi legacy — xem mục 8). Đây là cách "tắt khẩn cấp" không cần gỡ field trên bản ghi |
| `default_action` | Chế độ mặc định | Select | Có | `INCLUDE_ALL` | `INCLUDE_ALL` hoặc `EXCLUDE_ALL` — xem mục 6. Hai giá trị này hành xử khác nhau nhiều hơn tên gọi gợi ý |
| `description` | Mô tả | Small Text | Không | — | Không tham gia tính toán. Nên ghi rõ **vì sao thiếu nguồn nào đó**, để người sau không "bổ sung cho đủ" |
| `rules` | Rules | Table → `AL Variable Profile Rule` | Không | — | Bảng luật lọc. Rỗng nghĩa phụ thuộc `default_action` |
| `cross_row` | Cross Row | Table → `AL Variable Cross Row` | Không | — | Khai báo biến chéo dòng. Rỗng + `INCLUDE_ALL` ⇒ dùng lại hành vi cũ (mọi bảng con) |

Phần form: **Thông tin chung** (mã, tên, đang dùng, chế độ mặc định), **Cấu hình bộ lọc** (mô tả),
**Luật lọc biến** (rules), **Biến chéo dòng (slug)** (cross_row).

### 3.2 `AL Variable Profile Rule` — đúng 13 cột dữ liệu

Đây là bảng con. Mọi dòng đều có 13 cột dữ liệu dưới đây; không có cột ẩn nào khác tham gia luật.

| # | fieldname | Nhãn | Kiểu | Bắt buộc | Mặc định | Lựa chọn / ý nghĩa |
|---|---|---|---|---|---|---|
| 1 | `action` | Hành động | Select | Có | `Include` | `Include` / `Exclude`. **Exclude luôn thắng**: một dòng Exclude khớp là biến bị loại, bất kể bao nhiêu Include khớp |
| 2 | `source_kind` | Nguồn biến | Select | Có | — | Một trong 11 giá trị ở mục 4. Chọn sai nguồn ⇒ rule không khớp gì, biến mất **im lặng** |
| 3 | `source_ref` | Tham chiếu nguồn | Data | Không | — | Nghĩa **khác nhau theo từng nguồn** — xem mục 4. Rỗng hoặc `*` thường là "không lọc thêm" (riêng `variable_set`: set gắn với bản ghi) |
| 4 | `group_label` | Nhóm hiển thị | Data | Không | — | Đè nhóm hiển thị của biến. Rỗng = giữ nhóm gốc do nguồn đặt. Nên đánh số đầu nhóm: `01 · Vật liệu` |
| 5 | `sort_order` | Thứ tự nhóm | Int | Không | 100 | Số nhỏ đứng trước. Khi hai rule cùng khớp và hoà số, **rule khai trước thắng** |
| 6 | `is_active` | Đang dùng | Check | Không | 1 | Tắt ⇒ rule không tham gia khớp, và nếu là Include còn không được tính vào tập nguồn cần chạy |
| 7 | `name_prefix` | Tiền tố tên | Data | Không | — | Danh sách tiền tố ngăn bằng dấu sổ dọc, ví dụ `W_\|H_\|TONG_`. **Phân biệt hoa thường** |
| 8 | `name_regex` | Regex tên biến | Data | Không | — | Biểu thức chính quy Python, dùng `re.search` trên tên biến. Regex hỏng ⇒ coi như **không khớp**, không ném lỗi ra UI |
| 9 | `category_tag` | Category | Data | Không | — | Danh sách ngăn bằng dấu sổ dọc. So **khớp chính xác, không phân biệt hoa thường** với `category` **hoặc** `group` của biến |
| 10 | `var_type` | Kiểu biến | Select | Không | — | Rỗng = mọi kiểu. Các lựa chọn: `Float`, `Int`, `Data`, `Select`, `Link`, `Check`, `Currency`, `Percent`. So **khớp chính xác** |
| 11 | `source_type` | Source Type (FVB) | Data | Không | — | Chỉ có nghĩa với candidate do nguồn `fvb_scope` sinh ra; so khớp chính xác với `source_type` của Formula Variable Binding |
| 12 | `only_fields` | Chỉ hiện ở field | Small Text | Không | — | **JSON list** tên field, ví dụ `["qty","width"]`. `[]` hoặc để trống = **không giới hạn**. Chuỗi không phải JSON bị controller của `AL Variable Profile` chặn lưu; dữ liệu cũ lọt vào thì adapter coi như không giới hạn |
| 13 | `require_value` | Bắt buộc có giá trị | Check | Không | 0 | Bật ⇒ chỉ khớp khi candidate có giá trị thật (`has_value`). Đây là cổng **toàn cục** cho biến — xem mục 5.3 |

### 3.3 `AL Variable Cross Row`

| fieldname | Nhãn | Kiểu | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `table_field` | Child table | Data | — | **Tên field bảng con** trên doctype mẹ (bắt buộc), ví dụ `items`. Không phải tên doctype con (`AL Bom Item`) và cũng không phải tên bảng con của doctype khác |
| `id_field` | Field định danh dòng | Data | `slug` | Field dùng làm khoá dòng trong công thức. Để trống ⇒ tự dò theo thứ tự `custom_slug` → `line_ref` → field kết thúc bằng `_slug` → `slug` |
| `label_field` | Field nhãn dòng | Data | — | Field lấy nhãn đọc được cho gợi ý. Nếu field khai không tồn tại, tự rơi về `line_name` → `item_code` → dùng slug |
| `fields` | Danh sách field | Small Text | — | **JSON list** field được gợi ý, ví dụ `["width","height"]`. Rỗng = mọi field vô hướng của doctype con. Xem cảnh báo ở mục 7.3 |
| `include_index_form` | Sinh thêm dạng items[n] | Check | 1 | Sinh thêm dạng `items[0].width` **chỉ để tra**. Dạng này không dùng được trong công thức — xem mục 7.4 |
| `enabled` | Đang dùng | Check | 1 | Tắt ⇒ dòng cross-row không tham gia, không xoá dữ liệu |

### 3.4 Quyền

| DocType | Role có quyền theo JSON |
|---|---|
| `AL Variable Profile` | `System Manager`: đọc, ghi, tạo, xoá |
| `AL Variable Settings` | `System Manager`: đọc, ghi, tạo, xoá |
| `AL Formula Field` | `System Manager`: đọc, ghi, tạo, xoá |
| `AL Variable Profile Rule` | Không khai quyền riêng (bảng con, quyền theo cha) |
| `AL Variable Cross Row` | Không khai quyền riêng (bảng con, quyền theo cha) |

**Role `AL BOM Manager` chưa có quyền trên ba DocType cấu hình.** Đừng giả định BOM Manager mở
được form. Muốn giao ⇒ phải sửa `permissions` trong JSON của DocType (và cân nhắc hệ quả: người
sửa profile có thể làm cả đội không thấy biến cần dùng, trong khi validate vẫn cho lưu).

---

## 4. Mười một nguồn biến (`source_kind`)

Mỗi `source_kind` tương ứng một **adapter**: một hàm sinh danh sách biến của nguồn đó.
Có 11 giá trị nhưng chỉ **10 adapter**, vì `slug_reference` không sinh biến — nó điều khiển
phần gợi ý biến chéo dòng.

### 4.1 Bảng tra đầy đủ

| `source_kind` | Đọc từ đâu | `source_ref` nhận gì | Ví dụ | Lưu ý |
|---|---|---|---|---|
| `variable_library_system` | `AL Variable Library` có `is_system=1` | `*` / rỗng = mọi bản ghi; ngược lại danh sách `var_name` ngăn bằng dấu sổ dọc | `OFFSET_FRAME\|NC_PCT`; hoặc `*` | Adapter cố resolve giá trị thật từ chứng từ đang mở; không resolve được thì lấy `default_value` |
| `variable_library_user` | `AL Variable Library` có `is_system=0` | `*` / rỗng = mọi bản ghi; ngược lại danh sách `var_name` | `W_mm\|H_mm` | Candidate **luôn không có giá trị** (`has_value=false`). Bật `require_value` cho rule này sẽ loại sạch |
| `variable_set` | `AL Variable Set` áp cho bản ghi hiện tại | `AUTO` = tự dò set của bản ghi; `*` / rỗng = không lọc thêm; còn lại danh sách `set_code` | `AUTO`; `VS_CUA_DI` | `AUTO` phải viết **HOA**. `*` **không** quét cả bảng `AL Variable Set`: adapter chỉ lấy set áp cho bản ghi, cộng các mã khai tường minh |
| `cost_bucket` | `AL Cost Bucket` đang bật (`is_active=1`) | `*` / rỗng = mọi bucket; ngược lại danh sách `bucket_code` | `VL_NHOM\|VL_PK` | Giá trị chỉ có **sau** bước engine gom bucket. Gợi ý ở nơi tính trước bước đó sẽ dẫn tới công thức ra 0 |
| `cost_template_line` | Các dòng `line_code` của `AL Cost Template` đang xét | `AUTO` = `line_code` của template đang xét; ngược lại danh sách `line_code` | `AUTO`; `TONG_VL` | Chỉ lọc được dòng **đứng trước** dòng đang sửa khi API có `row_index`. Candidate luôn `has_value=false` |
| `formula_global` | `Formula Global Variable` có `is_active=1` | `*` / rỗng = mọi hằng số đang bật; ngược lại danh sách `var_name` | `VAT_RATE` | Chỉ hằng số kiểu `CONSTANT` mới có giá trị gợi ý; kiểu khác `has_value=false` |
| `fvb_scope` | `Formula Variable Binding` áp cho doctype cha và doctype dòng con | `*` / rỗng / `AUTO` = mọi binding; ngược lại danh sách **tên biến** (`variable_name`) | `AUTO`; `OFFSET_FRAME` | **Không phải doctype.** Muốn lọc theo doctype hay loại nguồn thì dùng `source_type`, `name_prefix`, `name_regex` |
| `row_literal` | `AL Variable Library` — dòng đang bật có **Category = Row Literals** | `*` / rỗng = mọi tên trong bảng; ngược lại danh sách `var_name` | `unit_price\|glass_thick` | Đăng ký **tên**, không tạo giá trị. Chỉ đúng ở bước engine có inject literal theo dòng |
| `common_var` | `AL Variable Library` — dòng đang bật có **Người dùng nhập** (`is_input`) | `*` / rỗng = mọi tên trong bảng; ngược lại danh sách `var_name` | `W_mm\|n_panel` | Giá trị lấy từ ngữ cảnh đã resolve; có thể rỗng ⇒ `—` |
| `doctype_field` | Field vô hướng của doctype cha, hoặc của doctype con khi đang sửa một dòng | `*` / rỗng = mọi field vô hướng; ngược lại danh sách `fieldname` ngăn bằng dấu sổ dọc | `customer\|company` | Nguồn **có** lọc theo `source_ref`: adapter đặt `source_ref` của candidate bằng chính `fieldname`, nên `source_ref` so đúng tên field (mã chuẩn hoá chữ thường cả hai phía). Chỉ liệt kê field vô hướng; bỏ Small Text/Text/JSON/Table |
| `slug_reference` | Không có adapter. Điều khiển danh sách `references` | **Tên bảng con thật**, ví dụ `items`. `*` không chỉ định bảng nào | `items` | Không sinh biến đơn. Exclude ở đây loại bảng khỏi mọi nhánh sinh references |

### 4.2 Bốn nguồn cần đọc kỹ

**`variable_set` với `AUTO`** — adapter tự dò tên set theo ba nhánh:

1. Nếu doctype **có** field Link đầu tiên trỏ thẳng `AL Variable Set` (ví dụ `AL Accessory Set.variable_set`)
   thì lấy giá trị field đó. Có field nhưng giá trị rỗng thì dừng ở đây, **không** rơi sang nhánh 2.
2. Nếu doctype **không có** field ở nhánh 1: tìm field Link trỏ `AL Bom Set` → lấy `AL Bom Set.variable_set`.
3. Nhánh độc lập, luôn chạy thêm: nếu doctype có field `product_type` (Link `AL Product Type`) và
   field có giá trị → lấy `AL Variable Set` đang bật khớp `product_type`, chọn bản `modified` gần nhất.
   Quy tắc này **cố định**, không đổi theo dữ liệu.

Vì nhánh 3 chạy thêm, một bản ghi có thể nhận **hai** bộ biến: bộ gắn trực tiếp và bộ theo product type.

`source_ref = *` hoặc rỗng ở nguồn này **không** có nghĩa "mọi `AL Variable Set` trong hệ".
Adapter không quét cả bảng; nó chỉ lấy set áp cho bản ghi (tự dò) cộng các `set_code` khai tường minh.
Muốn gợi ý một bộ không gắn với bản ghi, phải ghi mã bộ vào `source_ref`.

**`cost_template_line` và `row_index`** — chỉ khi `doctype = AL Cost Template`, `child_table = items`
và API có `row_index` thì adapter mới cắt danh sách dòng về phía trước dòng đang sửa. Lý do: bước
tính bảng giá thành chạy **tuần tự theo bảng**, dòng sau chưa có giá trị nên tham chiếu dòng sau
luôn ra 0. Autocomplete dạng bulk **không gửi** `row_index`, nên có thể thấy cả dòng sau — xem mục 13.

**`fvb_scope`** — adapter lấy binding của **cả** doctype cha và doctype con (khi đang sửa dòng).
Binding của dòng con được resolve trên chính dòng đó; binding còn lại resolve trên chứng từ cha.
Mỗi binding có thể mang sẵn phạm vi field qua `applies_to_field`; phạm vi này là **phạm vi của
nguồn** và sẽ bị giao với phạm vi của rule (mục 5.4).

**`doctype_field`** — adapter tự dò, không nhận danh sách field từ nơi khác. Hệ quả thực tế cần
biết: trên `AL Bom Item`, `width`, `height`, `qty` là **Small Text chứa công thức**, nên nguồn này
**không** liệt kê chúng. Muốn gợi ý chúng thì dùng đường cross-row (mục 7), không dùng `doctype_field`.

### 4.3 So khớp phân biệt hay không phân biệt hoa thường

| Điều kiện | Cách so | Ghi nhớ |
|---|---|---|
| `source_kind` | Khớp chính xác chuỗi | Danh sách cố định trong Select |
| `source_ref` | Không phân biệt hoa thường khi so với candidate | Riêng `AUTO` được nhận diện **trước** bước so khớp, nên phải viết đúng `AUTO`; `auto` bị hiểu là mã cụ thể và gần như không khớp gì |
| `name_prefix` | Phân biệt hoa thường, so đầu chuỗi | `TONG_` không khớp `tong_m2` |
| `name_regex` | `re.search`, phân biệt hoa thường | Regex hỏng ⇒ không khớp, không báo lỗi |
| `category_tag` | Không phân biệt hoa thường, so **bằng** với `category` hoặc `group` | Không phải so chứa |
| `var_type` | Khớp chính xác chuỗi | `float` không khớp `Float` |
| `source_type` | Khớp chính xác chuỗi | Chỉ nguồn `fvb_scope` mới có dữ liệu để so |

---

## 5. Thuật toán áp rule, giải thích cho người cấu hình

Toàn bộ nằm ở `alumglass/variable_sources/rules.py`. Thứ tự dưới đây là thứ tự **thật** trong mã,
không phải thứ tự trình bày cho đẹp.

### 5.1 Bước 0 — chọn adapter nào được chạy

**Trả lời nhanh "nguồn nào mặc định luôn có":**

- Ô **Nguồn biến** (`source_kind`) luôn có đủ **11 lựa chọn** — danh sách khai trong JSON của
  DocType, không phụ thuộc dữ liệu. Nhưng **không nguồn nào tự động được bật**: chỉ rule Include
  mới bật nguồn đó.
- Trường hợp duy nhất "mặc định có tất cả" là `default_action = INCLUDE_ALL` **và không có rule
  Include nào**: khi đó cả 10 adapter chạy (hành vi cũ). Có **một** rule Include ⇒ chỉ nguồn của
  rule đó chạy.
- `slug_reference` **không phải nguồn biến** — nó chỉ điều khiển gợi ý chèn `items.*`; xem §7.2.1
  vì gợi ý này vẫn có thể xuất hiện khi profile không resolve được.

Trước khi lọc từng biến, hệ thống chọn tập nguồn cần chạy để khỏi truy vấn thừa. Ví dụ điền đủ
13 cột cho từng chế độ: [vi-du-setting-day-du.md](vi-du-setting-day-du.md). Các nhánh:

- Có **ít nhất một rule Include đang bật** với `source_kind` khác `slug_reference`
  ⇒ **chỉ chạy các nguồn đó**. Các nguồn không được Include **không được chạy**, nên biến của
  chúng không tồn tại trong kết quả — kể cả khi `default_action = INCLUDE_ALL`.
- Không có rule Include nào:
  - `INCLUDE_ALL` ⇒ chạy **tất cả** adapter (hành vi cũ).
  - `EXCLUDE_ALL` ⇒ **không chạy adapter nào**. Kết quả biến rỗng; references vẫn có nếu `cross_row` khai.

Hệ quả quan trọng: một rule Include **chỉ** có `slug_reference` không kéo theo adapter nào.
Nếu đó là rule Include duy nhất và `default_action = INCLUDE_ALL`, hệ thống coi như "không có
rule Include" và chạy tất cả adapter.

### 5.2 Bước 1 — xét từng biến, theo đúng thứ tự này

Cho mỗi candidate (một dòng biến do adapter sinh ra):

1. **Rule Exclude khớp ⇒ loại ngay.** Exclude thắng mọi Include. Không có ngoại lệ.
2. **Cổng `require_value`.** Quét các rule Include đang bật. Nếu một rule có `require_value=1`
   và khớp candidate khi **bỏ qua** điều kiện giá trị, thì candidate bị loại khi nó **không có giá
   trị thật** — **với điều kiện chưa khớp rule Include nào khác**. Nếu còn một rule Include khác
   khớp (không đòi giá trị) thì biến rỗng vẫn hiện. Đừng hiểu `require_value` là cổng tuyệt đối
   toàn cục.
3. **`EXCLUDE_ALL` và không khớp Include nào ⇒ loại.**
4. **Không bị loại ⇒ giữ**, và nếu có rule Include khớp thì gắn nhóm + thứ tự từ rule đó.

Một rule "khớp" khi **tất cả** điều kiện nó khai đều đúng:

| Điều kiện | Bỏ trống nghĩa là |
|---|---|
| `source_kind` | Khớp mọi nguồn (chỉ xảy ra với dữ liệu cũ/hỏng; field bắt buộc nên UI không cho lưu trống) |
| `source_ref` | Không lọc thêm — tập candidate vẫn do adapter của ngữ cảnh sinh ra (riêng `variable_set`: set gắn với bản ghi, ⛔ không phải cả bảng) |
| `name_prefix` | Không lọc theo tiền tố |
| `name_regex` | Không lọc theo regex |
| `category_tag` | Không lọc theo category/nhóm |
| `var_type` | Không lọc theo kiểu |
| `source_type` | Không lọc theo loại nguồn FVB |
| `only_fields` | Không giới hạn field — **nhưng** nếu request có `fieldname` thì rule chỉ khớp khi `fieldname` nằm trong danh sách |
| `require_value` | Không đòi giá trị |
| `is_active` | Rule bị bỏ qua hoàn toàn |

### 5.3 `require_value` — cổng loại biến rỗng, không phải bộ lọc hiển thị

Đây là chỗ hay hiểu sai nhất. `require_value` không phải "ẩn nhãn khi rỗng". Nó là điều kiện
**loại khỏi danh sách** — nhưng chỉ khi biến **chưa khớp một rule Include nào khác**; nếu có rule
Include khác khớp mà không đòi giá trị, biến rỗng **vẫn hiện**.

Ví dụ: rule Include `common_var` với `source_ref = *`, `require_value = 1`.
`common_variables` có `W_mm = 1200` và `H_mm` chưa resolve.
Kết quả: `W_mm` hiện; `H_mm` **không hiện ở đâu cả**, không phải hiện với giá trị `—`.

Cẩn thận với các nguồn mà candidate luôn rỗng:

| Nguồn | `has_value` của candidate |
|---|---|
| `variable_library_user` | Luôn `false` |
| `cost_template_line` | Luôn `false` |
| `formula_global` | Chỉ `true` khi hằng số kiểu `CONSTANT` |
| `cost_bucket`, `fvb_scope`, `common_var`, `variable_library_system` | Tuỳ giá trị resolve được |
| `row_literal`, `doctype_field` | Tuỳ dòng/chứng từ hiện tại; xem giới hạn ở mục 13 |

### 5.4 Phạm vi field: `only_fields` giao với phạm vi nguồn

Mỗi biến có thể mang phạm vi field từ **hai phía**:

- **Phạm vi nguồn**: adapter gắn. Hiện chỉ nguồn `fvb_scope` có, lấy từ `applies_to_field`
  của binding. Khi widget gửi `fieldname`, binding được so **nguyên chuỗi** (`width` khớp,
  `width|height` ⛔ không khớp field nào); chỉ đường bulk **không** có `fieldname` mới tách
  `|`/`,` thành danh sách. Adapter khác để rỗng.
- **Phạm vi rule**: hợp `only_fields` của **mọi rule Include cùng khớp**.

Luật kết hợp:

| Tình huống | Kết quả |
|---|---|
| Một phía rỗng | Lấy phía còn lại, `hide_all = false` |
| Cả hai có danh sách, giao khác rỗng | Danh sách giao, `hide_all = false` |
| Cả hai có danh sách, giao **rỗng** | `only_fields = []` **và** `hide_all = true` — biến ẩn ở **mọi** field |

`hide_all` là cờ nội bộ do server gắn, **không có field cấu hình**. `only_fields = []` nghĩa là
"không giới hạn"; `hide_all = true` nghĩa là "ẩn hết". Hai thứ này khác nhau hoàn toàn, và việc
giao rỗng sinh ra cái thứ hai chứ không phải cái thứ nhất.

Ví dụ số: binding có `applies_to_field = "qty"`, rule có `only_fields = ["width"]`.
Mỗi phía đều cho phép một field, nhưng giao rỗng ⇒ biến bị ẩn ở **cả** `qty` lẫn `width`.
Đây là lý do khi chẩn đoán "biến không hiện ở đâu", phải đọc `hide_all` trong kết quả API.

Hợp `only_fields` của nhiều rule có một luật riêng: **một rule không khai `only_fields` thì thắng**,
kết quả là không giới hạn. Lý do: một rule đã cho phép mọi field thì rule khác không được thu hẹp oan.

### 5.5 `only_fields` trên `INCLUDE_ALL` — một bất đối xứng cần biết

Trên `INCLUDE_ALL`, rule **không khớp vẫn không loại biến**. Vì vậy:

- Đường **autocomplete bulk** (không gửi `fieldname`): rule khớp (vì không có fieldname để chặn),
  server gắn `only_fields` lên từng biến, **client** lọc theo field đang sửa. Kết quả đúng như mong đợi.
- Đường **gọi API có `fieldname`**: rule có `only_fields` không chứa field đó **không khớp**;
  nhưng vì `INCLUDE_ALL` giữ candidate không khớp, biến vẫn xuất hiện, mang `only_fields` của
  **nguồn** — thường là rỗng (trừ binding có `applies_to_field`) ⇒ không bị lọc ở field đó.

Muốn `only_fields` là cổng chắc chắn ở **cả hai** đường thì dùng `EXCLUDE_ALL`.
Đây là lý do các profile mẫu đều dùng `EXCLUDE_ALL`.

### 5.6 Dedupe khi nhiều nguồn cùng tên biến

Sau khi lọc, các candidate trùng `name` được gộp còn một. Thứ tự ưu tiên:

1. **Có giá trị thật** (`has_value = true`) thắng không có giá trị.
2. `sort_order` nhỏ hơn thắng.
3. Adapter đăng ký trước thắng (số `adapter_order` nhỏ hơn).
4. Xuất hiện trước trong danh sách thắng.

Không có bước nào bị bỏ im lặng: mọi tên bị gộp đều ghi vào `meta.duplicates`, dạng
`{name, kept, dropped[]}`, với `kept`/`dropped` là `source_kind:source_ref`.

Ví dụ số (minh hoạ):

| Nguồn | `has_value` | `sort_order` | `adapter_order` | Kết quả |
|---|---|---|---|---|
| `fvb_scope:unit_price` | false | 100 | 10 | Bị bỏ |
| `row_literal:unit_price` | true (250000) | 100 | 60 | **Thắng** |

Dù binding đăng ký trước, nguồn có giá trị vẫn thắng. Nếu **cả hai** đều có giá trị thì
`sort_order` mới có tiếng nói, rồi tới thứ tự adapter.

Khi gộp, phạm vi field của tên biến là **hợp** phạm vi các nguồn: một nguồn không giới hạn thì
biến không giới hạn; tất cả cùng `hide_all` thì `hide_all`; còn lại là hợp danh sách field.
Nhờ vậy binding global không bị binding hẹp che mất.

### 5.7 Gom nhóm và sắp thứ tự

- Nhóm = `group` của biến. `group` do `group_label` của rule đặt nếu rule khớp và nhãn không rỗng;
  ngược lại giữ nhóm gốc của nguồn. Biến không có nhóm vào nhóm `Khác`.
- Khi **nhiều rule Include cùng khớp**, nhóm và `sort_order` lấy từ rule có `sort_order` **nhỏ nhất**;
  hoà số thì rule **khai trước** thắng. Phạm vi field thì không lấy theo rule đó mà lấy **hợp** (mục 5.4).
- Thứ tự nhóm = `(sort_order nhỏ nhất trong nhóm, nhãn nhóm)`.
- Trong nhóm, biến sắp theo `(sort_order, tên)`.
- `sort_order` của biến đã bị **thay bằng** `sort_order` của rule thắng. Vì vậy mọi biến của cùng
  một rule có cùng số, và trong nhóm chúng xếp theo **tên**. Muốn một biến đứng đầu nhóm, tách nó
  ra rule riêng với `sort_order` nhỏ hơn.

### 5.8 Ví dụ số đầy đủ cho cả thuật toán

Profile `P_DEMO`, `default_action = EXCLUDE_ALL` (số liệu minh hoạ):

| # | action | source_kind | source_ref | group_label | sort_order | require_value |
|---|---|---|---|---|---|---|
| R1 | Include | `cost_bucket` | `*` | 01 · Vật liệu | 10 | 0 |
| R2 | Include | `variable_library_system` | `*` | 02 · Thông số hệ | 20 | 0 |
| R3 | Exclude | `variable_library_system` | `NC_PCT` | — | 30 | 0 |
| R4 | Include | `common_var` | `*` | 03 · Thông số nhập | 40 | 1 |

Candidate giả định: `VL_NHOM` (bucket, chưa có giá trị), `OFFSET_FRAME` (hệ thống, 25),
`NC_PCT` (hệ thống, 8), `W_mm` (dùng chung, 1200), `H_mm` (dùng chung, chưa resolve).

Kết quả từng bước:

| Biến | Bước 1 Exclude | Bước 2 `require_value` | Bước 3 EXCLUDE_ALL | Kết quả |
|---|---|---|---|---|
| `VL_NHOM` | Không khớp | Không rule nào đòi giá trị | Khớp R1 | Hiện, nhóm 01, thứ tự 10 |
| `OFFSET_FRAME` | Không khớp | — | Khớp R2 | Hiện, nhóm 02, thứ tự 20 |
| `NC_PCT` | **Khớp R3 ⇒ loại** | — | — | Không hiện |
| `W_mm` | Không khớp | R4 đòi giá trị, có 1200 | Khớp R4 | Hiện, nhóm 03, thứ tự 40 |
| `H_mm` | Không khớp | R4 đòi giá trị, **rỗng ⇒ loại** | — | Không hiện |

`meta.excluded_by_rules` trong kết quả API đếm số candidate bị loại — dùng con số này để biết
rule có đang cắn quá tay không.

---

## 6. `default_action` và bốn tổ hợp

`default_action` chỉ có hai giá trị, nhưng hành vi phụ thuộc **có bao nhiêu rule Include**.
Bảng dưới là bốn tổ hợp thực tế.

| # | `default_action` | Rule Include đang bật | Adapter được chạy | Kết quả |
|---|---|---|---|---|
| 1 | `INCLUDE_ALL` | 0 | Tất cả 10 adapter | Hiện **mọi** biến của mọi nguồn. Rule Exclude (nếu có) vẫn loại bớt. Đây là hành vi cũ |
| 2 | `INCLUDE_ALL` | ≥ 1 | **Chỉ** các `source_kind` được Include | Biến của nguồn không Include **biến mất hoàn toàn**. Trong nguồn được Include, biến không khớp điều kiện phụ vẫn hiện (vì `INCLUDE_ALL` giữ lại) |
| 3 | `EXCLUDE_ALL` | 0 | Không chạy adapter nào | Danh sách biến **rỗng**. `references` vẫn sinh nếu `cross_row` có khai. Đây là cấu hình "allowlist rỗng" — thường là lỗi cấu hình, không phải chủ ý |
| 4 | `EXCLUDE_ALL` | ≥ 1 | Chỉ các `source_kind` được Include | Chỉ biến **khớp ít nhất một rule Include** mới hiện. Đây là chế độ dùng cho mọi profile mẫu |

Ba điểm dễ hiểu sai:

1. **`INCLUDE_ALL` + một rule Include không phải "tất cả trừ vài nhóm".** Nó là "chỉ nhóm được
   Include". Muốn "tất cả trừ vài nhóm" thì để `INCLUDE_ALL`, **không** thêm rule Include, chỉ
   thêm rule Exclude.
2. **`EXCLUDE_ALL` + không rule Include = không có biến nào.** Nếu preview trắng trơn và
   `meta.excluded_by_rules = 0`, kiểm tra tổ hợp này trước.
3. **Rule Exclude rỗng `source_kind`** (dữ liệu hỏng) sẽ loại mọi nguồn khớp các điều kiện còn
   lại. Rất nguy hiểm, chỉ dùng khi hiểu rõ; UI bắt buộc chọn nguồn nên bình thường không xảy ra.

---

## 7. Biến chéo dòng (`cross_row`)

### 7.1 Cross-row giải quyết việc gì

Trong công thức của một dòng, người dùng cần tham chiếu dòng khác: `items.kinh_tren.width`.
Profile khai bảng con nào được gợi ý, field nào được gợi ý, và nhãn hiển thị lấy ở đâu.
Phần này sinh ra **references** — một danh sách riêng, không phải biến đơn.

### 7.2 Thứ tự quyết định sinh references

1. **Có `cross_row` đang bật và có `table_field`** ⇒ chỉ sinh cho các dòng đó.
   Nếu có rule Include `slug_reference`, danh sách cross-row còn bị lọc theo đúng các bảng được Include.
2. **Không có `cross_row` nhưng có rule Include `slug_reference`** ⇒ sinh cho các bảng rule trỏ tới,
   với **mọi field vô hướng** của doctype con và slug tự dò.
3. **Không có cả hai, `default_action = INCLUDE_ALL`, và doctype có bảng con** ⇒ hành vi cũ:
   mọi bảng con, mọi field vô hướng, slug tự dò; nhãn cũng tự dò `line_name` → `item_code`.
4. **Còn lại** ⇒ không gợi ý gì. `EXCLUDE_ALL` là allowlist: không khai nghĩa là không có.

Rule `slug_reference` **Exclude** loại bảng tương ứng ở **mọi** nhánh trên.

### 7.2.1 Vì sao bỏ `slug_reference` mà vẫn thấy `items.*`

**Không có nguồn nào "mặc định luôn có" trong danh sách biến.** Với `EXCLUDE_ALL`, chỉ adapter
của rule Include được chạy; không khai thì không có biến. Nhưng **references** (`items.<slug>.<field>`)
đi theo một đường riêng, và có bốn nguyên nhân vẫn sinh ra chúng dù bạn đã bỏ rule
`slug_reference`:

| # | Nguyên nhân | Dấu hiệu phân biệt | Cách xử lý |
|---|---|---|---|
| 1 | `default_action = INCLUDE_ALL` (giá trị **mặc định của DocType**) và **không có** `cross_row` hợp lệ | Profile trả về đúng `meta.profile_code`, nhưng `references` vẫn đầy đủ cho **mọi** bảng con | Đổi sang `EXCLUDE_ALL`, hoặc khai `cross_row` có `table_field` để chỉ còn đúng bảng được khai |
| 2 | **Profile không resolve được cho bản ghi đang mở** — record **chưa lưu**, `variable_profile` để trống mà không hồ sơ nào bật `is_default`, profile `is_active=0`, hoặc cột chưa migrate | `get_formula_context` trả `profile: null` (không có `meta.profile_code`); danh sách biến là bộ legacy đầy đủ | Gán profile cho bản ghi **sau khi lưu**, hoặc đặt `default_profile`. Record mới **luôn** đi đường legacy cho tới lần lưu đầu |
| 3 | Hồ sơ `is_default` đang là profile khác (ví dụ `P_BOM_DEFAULT`) | `meta.profile_code` ra mã **khác** mã bạn vừa sửa | Sửa đúng profile đang được resolve, hoặc bỏ default và gán theo bản ghi |
| 4 | Cache client 5 phút (`doctype::docname::childTable`) giữ context cũ trước khi bạn sửa/gán profile | Sửa xong vẫn thấy y như cũ; mở bản ghi khác hoặc reload thì hết | Reload form / xoá cache `alumglass.FormulaContext` |

> 🔴 **Dễ nhầm nhất là #2.** Trong đường legacy, `get_formula_context` **luôn** thêm references từ
> `AL Slug Library` dạng `items.<slug>.{field}` — danh sách slug toàn cục, ⛔ không liên quan profile.
> Vì vậy "chưa khai `slug_reference`" mà vẫn gợi ý `items.` **không chứng minh** profile đang được áp.
> Kiểm tra bằng `meta.profile_code`: có mã ⇒ catalog đang chạy; `profile: null` ⇒ đang ở legacy.

Cần phân biệt hai thứ:

- **Biến** (`variables`): chỉ do adapter sinh. `slug_reference` **không bao giờ** sinh biến.
- **Gợi ý chèn** (`references`): do `cross_row` / rule `slug_reference` / nhánh legacy quyết định.
  Vì vậy một profile có thể **không có biến `items.*`** nhưng vẫn **gợi ý chèn** `items.*` — và
  ngược lại, chèn được không có nghĩa công thức sẽ ra giá trị ở bước đang chạy (§7.3).

Ví dụ đầy đủ cho từng trường hợp, gồm cách tắt hẳn và cách chỉ ẩn ở vài field:
[vi-du-setting-day-du.md](vi-du-setting-day-du.md) §7.

### 7.3 Bảng field: chỉ khai field engine thật sự tạo

Đây là luật vàng. Gợi ý một field mà engine không nạp dẫn tới một trong hai kiểu hỏng:

| Kiểu hỏng | Khi nào | Người dùng thấy gì |
|---|---|---|
| Lưu bị chặn | Validate không biết `{slug}__<field>` | Gợi ý vẫn hiện, chèn vào công thức, bấm Lưu thì báo "Biến không khai báo" |
| Lưu được nhưng ra 0 | Validate biết tên (do đăng ký ở nguồn khác) nhưng bước engine đang chạy không inject | Công thức lưu trơn, chạy ra 0, không có cảnh báo. Đây là kiểu nguy hiểm hơn |

Vì sao danh sách field phải bám engine: bước dựng công thức của BOM (`b3_build_formulas`) tạo cho
mỗi dòng một namespace **phẳng** dạng `{slug}__{field}` — từ field công thức của dòng, từ row
literal engine inject, và từ các field tổng hợp `unit_qty`, `total_qty`, `line_total`. Ngoài ra
engine có thể inject thêm `{slug}__<biến phụ>` theo `input_vars` của `AL Quantity Calc Method` cho
dòng có `calc_pattern`; tập này phụ thuộc dữ liệu nên **không khai tay** trong cross-row.

Bảng nên và không nên khai:

| Bảng con | Nên khai | Không nên khai | Vì sao |
|---|---|---|---|
| `AL Bom Set.items` | `width`, `height`, `qty`, `unit_qty`, `unit_price`, `total_qty`, `line_total`, `weight_per_unit`, `glass_thick`, `glass_type`, `calc_pattern`, `scrap_pct` | `item_condition_formula`, `rule_input_expr`, `show_condition` — có tồn tại nhưng là biến điều kiện/chuỗi, không phải đại lượng để tính; gợi ý chúng trong công thức số dễ gây nhầm | Danh sách bên trái đúng bằng tập **đại lượng** engine tạo cho mỗi dòng |
| `AL Accessory Set.items` | `qty`, `unit_qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total` — engine tạo cả sáu | `qty_formula` — đây là **chuỗi công thức**, engine không tạo `{slug}__qty_formula` | Xem ghi chú ngay dưới bảng về các field tổng hợp |
| `AL Cost Template.items` | Không dùng cross-row | Mọi field | Bước tính bảng giá thành không có ngữ cảnh `items.*` |

`fields` để **trống** không phải "không gợi ý gì". Nó nghĩa là **mọi field vô hướng** của doctype
con — gồm cả field engine không nạp. Chuỗi JSON hỏng cũng rơi về trường hợp này, vì bảng Cross Row
**không có controller kiểm JSON** (khác `only_fields` của rule). Luôn khai danh sách tường minh.

**Ghi chú riêng cho `AL Accessory Set` (đã vá trong bản working tree, test thuần 9/9 PASS):**
validate của doctype này dựng superset `{slug}__{field}` từ **meta** của `AL Accessory Item`, **hợp**
với `ENGINE_SYNTHETIC_FIELDS` (`unit_qty`, `total_qty`, `line_total`). Ba field tổng hợp không nằm
trong meta nhưng engine B3 luôn tạo cho mọi dòng, nên trước bản vá `items.<slug>.total_qty` chạy
đúng vẫn bị chặn oan khi Lưu. Nay superset đã gồm chúng; đối chứng âm trong test xác nhận field
**không tồn tại** vẫn bị chặn. Lưu ý: superset chỉ nới **validate**, ⛔ không làm field lạ có giá trị
lúc chạy — field engine không nạp vẫn ra 0.

### 7.4 Dạng `items[n]` chỉ để tra

`include_index_form = 1` sinh thêm `items[0].width`, `items[1].width`… (chỉ số **bắt đầu từ 0**,
nhãn hiển thị ghi "hàng 1" cho chỉ số 0).

Dạng này **không dùng được trong công thức**. Lý do đọc từ mã:

- Runtime dựng `inputs["items"]` là **dict khoá theo slug**, không phải list.
- Hàm chuẩn hoá `_normalize_items_ref` chỉ đổi dạng `items.<slug>.<field>` thành `{slug}__{field}`.
  Dạng `items[0].width` không khớp mẫu, nên không được đổi; công thức sẽ đọc chỉ số trên một dict
  và ra 0, hoặc bị validate chặn.

Muốn tra nhanh theo thứ tự hàng thì dùng; muốn viết công thức thì luôn dùng slug.

### 7.5 Cross-row không tạo biến

Một rule Include `slug_reference` **không** làm biến `items.kinh_tren.width` xuất hiện trong
`variables`. Nó chỉ điều khiển `references`. Vì vậy:

- Autocomplete có thể gợi ý `items...` trong khi `meta.total` vẫn nhỏ.
- `explain_variable("items.kinh_tren.width", ...)` không phải công cụ đúng để giải thích
  references; nó làm việc trên biến đơn.

---

## 8. Profile được chọn thế nào, áp cho những đâu

### 8.1 Thứ tự resolve

| Bước | Nguồn | Điều kiện |
|---|---|---|
| 1 | Tham số `profile` truyền tường minh | Dùng ở preview và khi gọi `get_variable_catalog` có truyền `profile`. `explain_variable` **không** nhận tham số này |
| 2 | Field Link **đầu tiên** trên doctype trỏ `AL Variable Profile`, lấy giá trị trên bản ghi | Cần `docname` và bản ghi có giá trị |
| 3 | `AL Variable Profile.is_default` (chưa migrate ⇒ `AL Variable Settings.default_profile`) | **Chỉ** khi doctype đã có field Link nói trên. Doctype không có field ⇒ dừng, không áp default |
| 4 | Không có ⇒ coi như chưa gán profile | Rơi về đường legacy (bộ biến cũ; chú thích trong mã gọi là "8 nhóm cũ", danh sách mục nguồn đánh số 0–8) |

Bước 3 có điều kiện rất chặt vì một lý do cụ thể: nếu không, đặt `default_profile` sẽ tự bật cho
**mọi** doctype trong hệ, kể cả doctype không liên quan, làm autocomplete đổi hành vi ngoài ý muốn.

Cảnh báo thực dụng: `AL Variable Settings.default_profile` áp cho **cả bốn** doctype có field Link
nếu bản ghi của chúng chưa chọn profile riêng. Đừng đặt một profile chuyên biệt (ví dụ profile BOM)
làm default toàn hệ.

### 8.2 Profile `is_active = 0`

`_load_profile` trả `None`, nên profile bị coi như **không tồn tại** ở mọi bước. Bản ghi có Link
trỏ profile đã tắt sẽ rơi tiếp xuống bước 3 (default) hoặc bước 4 (legacy). Đây là cách tắt nhanh
khi cấu hình sai mà không phải gỡ field trên từng bản ghi.

### 8.3 Phạm vi áp dụng

Field Link trỏ `AL Variable Profile` có trên **đúng bốn** doctype:

| DocType | Fieldname | Có bảng con? |
|---|---|---|
| `AL Bom Set` | `variable_profile` | Có (`items`) |
| `AL Accessory Set` | `variable_profile` | Có (`items`) |
| `AL Cost Template` | `variable_profile` | Có (`items`) |
| `AL Alert Config` | `variable_profile` | Không |

`AL Bom Set` còn có field `profile_system` trỏ `AL Profile System` — **khác hoàn toàn**, không liên
quan đến profile biến. Đừng chọn nhầm.

**Bảng con kế thừa profile của bản ghi mẹ.** Không có profile riêng cho từng dòng. Khi đang sửa một
dòng, `child_table` và `row_index` chỉ giúp adapter lấy đúng ngữ cảnh (binding của dòng, dòng đang
sửa, field đang sửa), không đổi profile.

### 8.4 Profile không đi vào runtime

Đường validate cố ý bỏ qua profile: `build_known_names` gọi context với `include_all_sources=True`,
nên vũ trụ biến hợp lệ là **đường legacy đầy đủ**. Đường tính giá của engine cũng không đọc profile.
Vì vậy:

- Công thức cũ dùng biến ngoài profile: vẫn lưu, vẫn chạy.
- Bật profile mới: chỉ đổi danh sách gợi ý.
- Xoá profile: không làm hỏng công thức đã có.

### 8.5 Cache phía client

| Cache | TTL | Khoá | Ai xoá |
|---|---|---|---|
| Context biến (`FormulaContext`) | 5 phút | `doctype::docname::child_table` | **Không nơi nào gọi** `invalidate` trong mã hiện tại |
| Sổ `AL Formula Field` | 60 giây | `doctype` | Cũng không có lời gọi invalidate |

Hệ quả: sửa profile xong, form đang mở vẫn thấy danh sách cũ tới 5 phút. Cách xử lý: tải lại trang
(F5) hoặc chờ hết TTL. Đây là hành vi đã biết, không phải lỗi dữ liệu.

---

## 9. Kiểm tra: xem trước, giải thích, API

### 9.1 Nút "Xem trước danh sách biến"

| Mục | Thực tế trong mã |
|---|---|
| Vị trí | Form `AL Variable Profile`, nhóm nút **Công cụ** |
| Điều kiện hiện | Profile đã lưu (`frm.is_new()` trả false). Chưa lưu thì không có mã để xem |
| Ô nhập trong dialog | `doctype` (bắt buộc, mặc định lấy từ `AL Variable Profile.preview_doctype`; trống ⇒ Single cũ), `docname`, `child_table`, `fieldname` |
| Ô **không** có | `row_index` — xem mục 13 |
| API gọi | `preview_variable_catalog(profile, doctype, docname, child_table, row_index, fieldname)` |
| Quyền | Ngoài guard doctype, cần **read** trên `AL Variable Profile` |
| Hiển thị | Bảng theo nhóm: Nhóm, Tên biến, Nhãn, Kiểu, Giá trị, Nguồn. Kèm cảnh báo cam nếu có trùng tên, và số "Bị luật loại" |

Nút này dùng **profile đang mở**, không dùng profile gán trên bản ghi. Nhờ vậy thử được profile
trước khi gán.

### 9.2 `explain_variable` — vì sao tôi thấy hoặc không thấy biến này

Trả **mọi nguồn** cùng tên, kể cả nguồn bị rule loại, kèm hai cờ:

| Cờ | Nghĩa |
|---|---|
| `selected` | Nguồn này có vượt qua rule không |
| `kept` | Nguồn này có thắng dedupe không (chỉ một nguồn `kept = true`; có thể `null`) |

Hàm chạy **tất cả** adapter, nên chậm hơn catalog. Dùng để chẩn đoán, không gọi theo từng lần gõ.
Hàm **không nhận tham số `profile`**: nó luôn dùng profile resolve từ bản ghi. Muốn giải thích một
profile chưa gán, dùng preview.

### 9.3 Bốn API liên quan

| API | Dùng để | Quyền |
|---|---|---|
| `get_variable_catalog` | Danh mục đầy đủ: `variables`, `groups`, `references`, `meta` | Guard doctype + read doctype nghiệp vụ |
| `get_variable_profile` | Profile đang áp cho `(doctype, docname)`, hoặc `null` | Như trên |
| `preview_variable_catalog` | Xem trước một profile cụ thể | Thêm read trên `AL Variable Profile` |
| `explain_variable` | Giải thích một tên biến | Read trên doctype nghiệp vụ |

Shape chi tiết và ví dụ gọi: [api-reference.md](api-reference.md). Bài này chỉ nêu ngữ nghĩa.

### 9.4 Đọc `meta` trước khi đọc `variables`

| Khoá | Nghĩa | Dùng khi |
|---|---|---|
| `excluded_by_rules` | Số candidate bị loại | Danh sách quá ngắn: rule có cắn quá tay không |
| `duplicates` | Tên bị gộp, nguồn giữ và nguồn bỏ | Một biến có giá trị lạ: có thể nguồn khác đang thắng |
| `profile_code` | Profile đã resolve | Kiểm tra có đúng profile mình nghĩ không |
| `source_kinds` | Các nguồn **thực sự được chạy** | Danh sách trắng: xem adapter nào còn chạy |
| `legacy_fallback` | `true` = không có profile | Ở `get_variable_catalog`, khoá này chỉ có trong kết quả **rỗng** (chưa gán profile); khi có profile thì đọc `profile_code`. Ở `explain_variable` thì khoá luôn có |

---

## 10. Bốn ví dụ cấu hình hoàn chỉnh

Số liệu trong mục này là **ví dụ minh hoạ**, không phải dữ liệu khách hàng.
Hai ví dụ đầu dùng đúng profile do patch seed tạo; ví dụ 3 và 4 là profile tự tạo.

### 10.1 Ví dụ 1 — `P_COST_TEMPLATE_DEFAULT`

**Mục đích:** bảng giá thành chỉ thấy vật liệu/chi phí, dòng tự định nghĩa, thông số hệ, hằng số,
binding và biến người dùng nhập. Không thấy row literal trần và không thấy biến chéo dòng.

`default_action = EXCLUDE_ALL`, không có `cross_row`.

| # | action | source_kind | source_ref | group_label | sort_order |
|---|---|---|---|---|---|
| 1 | Include | `cost_bucket` | `*` | 01 · Vật liệu & chi phí | 10 |
| 2 | Include | `cost_template_line` | `AUTO` | 02 · Dòng tự định nghĩa | 20 |
| 3 | Include | `variable_library_system` | `*` | 03 · Thông số hệ | 30 |
| 4 | Include | `formula_global` | `*` | 04 · Hằng số | 40 |
| 5 | Include | `fvb_scope` | `AUTO` | 05 · Binding | 50 |
| 6 | Include | `common_var` | `*` | 06 · Thông số nhập | 60 |

**Kết quả khi gõ ở `AL Cost Template Item.calc_formula`** (số liệu minh hoạ):

| Nhóm | Biến thấy được | Nguồn |
|---|---|---|
| 01 · Vật liệu & chi phí | `VL_NHOM`, `VL_PK`, `CP_NHANCONG` | Cost Bucket |
| 02 · Dòng tự định nghĩa | `TONG_VL`, `TONG_PK` | `line_code` của chính template |
| 03 · Thông số hệ | `OFFSET_FRAME`, `NC_PCT` | Variable Library hệ thống |
| 04 · Hằng số | `VAT_RATE` | Formula Global Variable |
| 05 · Binding | các biến binding áp cho `AL Cost Template` và dòng của nó | Formula Variable Binding |
| 06 · Thông số nhập | `W_mm`, `H_mm`, `n_panel` | Settings.common_variables |

**Không thấy:**

| Biến | Vì sao |
|---|---|
| `unit_price`, `glass_thick`, `line_total` (dạng trần) | Không có rule `row_literal`. Bước tính bảng giá thành không có namespace literal theo dòng |
| `items.<slug>.<field>` | Không có `cross_row`, không có rule `slug_reference`, và `EXCLUDE_ALL` ⇒ mục 7.2 nhánh 4 |
| `variable_set` | Không Include. Bảng giá thành có `product_type`, nên nếu Include thì adapter sẽ gợi ý bộ biến theo product type — profile này cố ý không làm vậy |

**Vì sao dùng `AUTO` cho dòng tự định nghĩa:** người dựng template tự đặt `line_code`. Khai tay
một danh sách mã sẽ lệch ngay khi thêm dòng mới.

**Điều cần nhớ khi xem trước:** dialog preview không có `row_index`, nên rule 2 trả **tất cả**
`line_code` của template, kể cả dòng sau dòng đang sửa. Khi sửa thật trên form, API có `row_index`
và chỉ gợi ý dòng trước. Đừng kết luận "preview sai" khi thấy khác form.

### 10.2 Ví dụ 2 — `P_BOM_DEFAULT`

**Mục đích:** bộ biến cho dòng BOM, bám đúng bước engine dựng công thức cho `AL Bom Item`.
Patch `seed_bom_profile` (2026-11-13) tạo profile này và gán cho các `AL Bom Set` đang trống.

`default_action = EXCLUDE_ALL`.

| # | action | source_kind | source_ref | group_label | sort_order |
|---|---|---|---|---|---|
| 1 | Include | `variable_library_system` | `*` | 01 · Thông số hệ | 10 |
| 2 | Include | `variable_set` | `AUTO` | 02 · Thông số nhập | 20 |
| 3 | Include | `common_var` | `*` | 03 · Thông số nhập | 30 |
| 4 | Include | `formula_global` | `*` | 04 · Hằng số | 40 |
| 5 | Include | `fvb_scope` | `AUTO` | 05 · Binding | 50 |
| 6 | Include | `slug_reference` | `items` | 06 · Dòng khác | 60 |

Cross Row: `table_field = items`, `id_field = slug`, `label_field = line_name`,
`include_index_form = 1`, `enabled = 1`.

`fields`: `["width","height","qty","unit_qty","unit_price","total_qty","line_total","weight_per_unit","glass_thick","glass_type","calc_pattern","scrap_pct"]`.

**Kết quả khi gõ ở `AL Bom Item.width`** (số liệu minh hoạ):

| Loại gợi ý | Ví dụ | Ghi chú |
|---|---|---|
| Biến hệ thống | `OFFSET_FRAME`, `NC_PCT` | Resolve được giá trị từ chứng từ |
| Biến của Variable Set | `SO_CANH`, `LOAI_RAY` (ví dụ) | Set tự dò theo bộ BOM hoặc product type |
| Biến dùng chung | `TONG_M2`, `installation_height_m` | Từ Settings |
| Hằng số | `VAT_RATE` | Chỉ hằng số đang bật |
| Binding | biến binding áp cho `AL Bom Set` và `AL Bom Item` | Có thể mang phạm vi field riêng |
| Dòng khác | `items.kinh_tren.width`, `items.kinh_tren.qty`, `items.kinh_tren.line_total`… | Một mục cho mỗi field khai trong cross-row |

Khi gõ ở `AL Bom Item.qty`, danh sách **gần như** giống hệt: cùng nguồn, cùng nhóm, cùng biến chéo.
Khác biệt duy nhất có thể có là các biến binding khai `applies_to_field` — adapter lọc binding theo
field đang sửa, nên `width` và `qty` có thể thấy hai tập binding khác nhau. `only_fields` không
dùng trong profile này: mọi biến áp cho mọi field công thức của dòng.

**Ba nguồn cố ý không có, và lý do:**

| Nguồn thiếu | Nếu thêm vào thì sao | Vì sao không thêm |
|---|---|---|
| `cost_bucket` | Biến hiện, lưu được, tính ra **0** ở bước dựng công thức BOM | Bucket chỉ có giá trị **sau** bước gom bucket. Công thức dòng BOM chạy trước bước đó |
| `row_literal` | Biến trần `unit_price` hiện, lưu được, tính ra **0** | Namespace của bước đó chỉ có `{slug}__<field>`, không có literal trần. Muốn tham chiếu đúng thì dùng cross-row `items.<slug>.unit_price` |
| `cost_template_line` | Không có gì để hiện | `AL Bom Set` không Link tới `AL Cost Template`; dòng giá thành chỉ tồn tại ở bước sau |

Đây là ví dụ rõ nhất cho luật "chỉ khai field/nguồn engine thật sự tạo". Patch ghi rõ trong
docstring để người sau không "bổ sung cho đủ".

**Không thấy thêm:** `variable_library_user` (profile chỉ Include bản `system`), `doctype_field`
(không có rule), nên field cấp cha như mã khách hàng không được gợi ý. Nếu cần biến người dùng của
Library thì phải thêm rule `variable_library_user` — cân nhắc trước, vì có thể trùng tên với biến
đã có từ Variable Set và bị dedupe.

### 10.3 Ví dụ 3 — profile tự tạo "chỉ thông số nhập"

**Tình huống:** một bộ BOM mà người lập công thức chỉ được dùng biến người dùng nhập và biến dùng
chung. Muốn danh sách ngắn, tránh chọn nhầm thông số hệ thống.

`profile_code = P_BOM_CHI_NHAP`, `default_action = EXCLUDE_ALL`.

| # | action | source_kind | source_ref | group_label | sort_order | require_value |
|---|---|---|---|---|---|---|
| 1 | Include | `variable_set` | `AUTO` | 01 · Biến của bộ | 10 | 0 |
| 2 | Include | `common_var` | `*` | 02 · Biến dùng chung | 20 | 0 |

**Thấy:** biến của Variable Set gắn với bộ (hoặc theo product type), và toàn bộ
dòng Library bật **Người dùng nhập** (`is_input`).

**Không thấy:** biến hệ thống, hằng số, cost bucket, binding, row literal, references.

**Hệ quả cần nói với người dùng trước khi gán:**

- Công thức đang dùng `OFFSET_FRAME` vẫn lưu và vẫn chạy, nhưng người sửa sẽ **không được gợi ý**
  biến đó nữa. Họ phải nhớ tên hoặc mở tài liệu.
- `TONG_M2` là common var nên vẫn thấy. Nếu nhóm này chuyển `TONG_M2` sang Library hệ thống thì
  nó biến mất khỏi gợi ý mà không có cảnh báo.

**Khi nào nên bật `require_value`:** nếu muốn danh sách chỉ còn biến đã có số. Nhưng nhớ:
`variable_library_user` và `cost_template_line` luôn rỗng, nên bật `require_value` cho chúng là
xoá sạch gợi ý. Với `variable_set` và `common_var`, bật được nhưng người dùng sẽ mất khả năng
phát hiện "biến này tồn tại nhưng chưa nhập".

### 10.4 Ví dụ 4 — tách danh sách theo field bằng hai rule khác `source_ref`

**Tình huống:** cùng là row literal, nhưng khi sửa công thức kích thước chỉ nên thấy biến kích
thước; khi sửa công thức số lượng chỉ nên thấy biến số lượng.

Profile `P_BOM_TACH_FIELD`, `default_action = EXCLUDE_ALL`.
Bảng dưới ghi đủ **13 cột dữ liệu**; cột nào để `—` nghĩa là bỏ trống (hoặc giữ mặc định).

| # | action | source_kind | source_ref | group_label | sort_order | is_active | name_prefix | name_regex | category_tag | var_type | source_type | only_fields | require_value |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Include | `row_literal` | `unit_price\|glass_thick` | 08a · Kích thước | 10 | 1 | — | — | — | — | — | `["width","height"]` | 0 |
| 2 | Include | `row_literal` | `qty\|calc_pattern` | 08b · Số lượng | 20 | 1 | — | — | — | — | — | `["qty","line_total"]` | 0 |

**Kết quả:**

| Ngữ cảnh | Rule khớp | Biến thấy |
|---|---|---|
| Gõ ở `width` | Rule 1 (vì `only_fields` có `width`); rule 2 không khớp | `unit_price`, `glass_thick` |
| Gõ ở `qty` | Rule 2 | `qty`, `calc_pattern` |
| Gõ ở `height` | Rule 1 | `unit_price`, `glass_thick` |
| Autocomplete bulk (không fieldname) | Cả hai khớp | Cả bốn biến, mỗi biến mang `only_fields` riêng để **client** lọc |

**Ba điều phải hiểu đúng:**

1. `only_fields` là **cổng mức rule**, không phải thuộc tính của từng biến. Mọi biến mà rule 1
   chọn đều mang cùng phạm vi `["width","height"]`. Muốn hai biến trong cùng nhóm có phạm vi khác
   nhau thì phải tách thành hai rule với `source_ref` khác nhau.
2. Nếu hai rule **cùng** chọn một biến (ví dụ `source_ref` chồng nhau), phạm vi là **hợp**.
   Một rule không khai `only_fields` thì biến thành không giới hạn, và khi đó không tách được nữa.
3. Đừng đặt hai rule đều `source_ref = *` với `only_fields` khác nhau. Cả hai cùng khớp mọi biến,
   kết quả là hợp, tức là không tách.

---

## 11. Mười một kiểu cấu hình sai thường gặp

| # | Cấu hình | Chuyện gì xảy ra | Cách đúng |
|---|---|---|---|
| 1 | `only_fields` ghi `qty,width` (không phải JSON) | Controller của `AL Variable Profile` chặn lưu với câu "phải là JSON list". Dữ liệu cũ lọt vào thì được hiểu là **không giới hạn** | `["qty","width"]` |
| 2 | `source_kind = fvb_scope`, `source_ref = AL Bom Item` | Không khớp gì, vì `source_ref` của nguồn này là **tên biến**, không phải doctype | Để `AUTO`/`*`, rồi lọc bằng `source_type`, `name_prefix`, `name_regex` |
| 3 | `source_ref = auto` (chữ thường) | `AUTO` chỉ được nhận diện khi viết HOA; `auto` bị hiểu là mã cụ thể, gần như không khớp | Viết `AUTO` |
| 4 | `slug_reference` với `source_ref = *` | Không chỉ định bảng nào; rule không lọc được gì, rơi về hành vi mặc định | Ghi tên bảng con thật: `items` |
| 5 | Hai rule `source_ref = *`, `only_fields` khác nhau | Cả hai cùng khớp mọi biến ⇒ phạm vi là **hợp** ⇒ không tách được | Tách bằng `source_ref` (ví dụ 4) |
| 6 | Thêm `cost_bucket` vào profile của `AL Bom Set` | Biến hiện, lưu được, tính ra **0** không báo lỗi | Bỏ ra. Bucket chỉ có sau bước gom bucket |
| 7 | Thêm `row_literal` vào profile của `AL Bom Set` | Biến trần `unit_price` hiện, lưu được, tính ra **0** | Dùng cross-row `items.<slug>.unit_price` |
| 8 | Khai `qty_formula` vào cross-row của `AL Accessory Set` | Gợi ý chèn được nhưng Lưu báo "Biến không khai báo" | Chỉ khai `qty`, `unit_qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total` |
| 9 | Khai `items[0].width` vào công thức | Dạng chỉ số chỉ để tra; runtime là dict theo slug nên ra 0 hoặc bị validate chặn | Dùng `items.<slug>.width` |
| 10 | `INCLUDE_ALL` + một rule Include | Không phải "tất cả trừ nhóm đó"; các nguồn không Include **mất hẳn** | Muốn trừ bớt: giữ `INCLUDE_ALL`, chỉ thêm rule Exclude |
| 11 | Kỳ vọng sửa/xoá profile làm đổi số tiền BOM | Không đổi. Profile không nằm trong runtime | Sửa cấu hình engine/công thức; dùng profile đúng phạm vi của nó |

Hai bẫy bổ sung, ít gặp nhưng tốn thời gian:

- **Bật `require_value` cho `variable_library_user` hoặc `cost_template_line`**: hai nguồn này luôn
  `has_value = false`, nên gợi ý bị xoá sạch dù rule "đúng".
- **Để `cross_row.fields` trống hoặc JSON hỏng**: rơi về **mọi field vô hướng** của doctype con,
  gồm field engine không nạp. Bảng Cross Row không có controller kiểm JSON.

---

## 12. Quy trình kiểm trước khi đóng job

Làm đúng thứ tự, mỗi bước có mục đích riêng. Bỏ bước nào cũng để lại một vùng mù.

| Bước | Việc làm | Câu hỏi phải trả lời được |
|---|---|---|
| 1 | **Xem trước danh sách biến** trên profile, chọn đúng doctype + `child_table` + `fieldname` | Nhóm có đúng thứ tự tôi muốn? Có biến lạ nào lọt vào? `total` và "Bị luật loại" có hợp lý? |
| 2 | Đọc cảnh báo **trùng tên** trong dialog | Tên nào bị gộp, nguồn nào thắng? Nguồn thắng có phải nguồn tôi muốn? |
| 3 | Gọi `explain_variable` cho 2–3 biến quan trọng | Biến có `selected = true` không? `kept` có đúng nguồn không? |
| 4 | Mở bản ghi nghiệp vụ thật, gõ thử ở một field công thức | Danh sách có giống preview không? Biến chéo dòng có hiện đúng slug? |
| 5 | Lưu thử một công thức dùng biến **ngoài** profile | Hệ thống **phải cho lưu**. Bị chặn là sai thiết kế, không phải profile chặt |
| 6 | Chạy tính giá trên **site dev** và so số với trước khi đổi profile | Số phải **không đổi**. Đổi là có thay đổi khác ngoài profile |

Lưu ý riêng cho bước 1:

- Dialog **không có `row_index`** ⇒ rule `cost_template_line` trả cả dòng sau; rule
  `row_literal` không biết dòng đang sửa nên giá trị có thể khác form thật.
- Chọn `docname` rỗng thì không resolve được giá trị; `require_value` sẽ loại gần hết. Muốn thấy
  đúng như người dùng, nhập tên bản ghi thật.
- Preview cần quyền read trên `AL Variable Profile`. `bench execute` chạy bằng Administrator nên
  **không** phản ánh quyền của BOM Manager.

Câu lệnh kiểm nhanh (chi tiết tham số ở [api-reference.md](api-reference.md) mục 10):

```bash
bench --site <dev> execute alumglass.api.variable_catalog.get_variable_profile \
  --kwargs '{"doctype": "AL Bom Set", "docname": "<tên record>"}'

bench --site <dev> execute alumglass.api.variable_catalog.preview_variable_catalog \
  --kwargs '{"profile": "P_BOM_DEFAULT", "doctype": "AL Bom Set", "child_table": "items", "fieldname": "width"}'
```

---

## 13. Giới hạn đã biết

Ghi lại để người sau không mất thời gian chẩn đoán những thứ là **hành vi đã biết**, không phải lỗi.

| # | Giới hạn | Hệ quả thực tế | Cách sống chung |
|---|---|---|---|
| 1 | Context biến cache 5 phút; sổ `AL Formula Field` cache 60 giây; **không nơi nào gọi invalidate** | Sửa profile xong form vẫn thấy danh sách cũ | F5 hoặc chờ TTL |
| 2 | Bulk autocomplete **không gửi `fieldname`** | Server gắn `only_fields`/`hide_all`, client lọc theo field đang sửa | Đường này vẫn lọc đúng; đừng thêm điều kiện field ở server cho bulk nữa |
| 3 | Gọi API có `fieldname` trên profile `INCLUDE_ALL`: rule không khớp **không loại** biến | Danh sách có thể rộng hơn bulk ở cùng field | Dùng `EXCLUDE_ALL` nếu cần `only_fields` là cổng chắc chắn |
| 4 | Preview không có ô `row_index` | `cost_template_line` trả cả dòng sau; `row_literal` không biết dòng hiện tại | Đọc kết quả là "danh mục tối đa", không phải "đúng bằng form" |
| 5 | Bulk autocomplete cũng không gửi `row_index` | Có thể thấy `line_code` của dòng sau | Chỉ dùng dòng trước khi viết công thức; tham chiếu dòng sau sẽ ra 0 lúc chạy |
| 6 | `items[n].<field>` chỉ để tra | Gõ vào công thức ra 0 hoặc bị chặn | Luôn dùng `items.<slug>.<field>` |
| 7 | Không có profile riêng cho từng dòng | Mọi dòng của một bản ghi dùng chung một profile | Tách bằng `only_fields` hoặc tách bản ghi mẹ |
| 8 | Profile không chặn lưu công thức ngoài profile | Người dùng vẫn gõ được biến bị loại nếu nhớ tên | Chấp nhận; đây là thiết kế để không phá công thức cũ |
| 9 | Ba DocType cấu hình chỉ cấp `System Manager` | BOM Manager không mở/sửa được profile | Sửa `permissions` nếu muốn giao; cân nhắc hậu quả |
| 10 | `cross_row.fields` trống hoặc JSON hỏng ⇒ mọi field vô hướng | Gợi ý field engine không nạp | Luôn khai danh sách tường minh; không có controller kiểm |
| 11 | `require_value` dựa vào `has_value` của adapter. `doctype_field` và `row_literal` truyền `has_value = value is not None`, nên field rỗng chuỗi vẫn tính là "có giá trị" | `require_value` có thể không lọc sạch như mong đợi với hai nguồn này | Đừng dựa vào `require_value` để lọc hai nguồn đó |
| 12 | `explain_variable` không nhận tham số `profile` | Không giải thích được profile chưa gán | Dùng preview cho profile chưa gán |
| 13 | Hồ sơ `is_default` áp cho **cả bốn** doctype có field Link | Một default chuyên biệt có thể lan sang doctype khác | Để trống default, gán theo bản ghi |
| 14 | Rule Include có `source_kind` rỗng (dữ liệu hỏng) | Không đóng góp nguồn nào vào tập adapter, và với `EXCLUDE_ALL` có thể làm kết quả rỗng | Sửa dữ liệu; UI bắt buộc chọn nguồn nên bình thường không xảy ra |
| 15 | Superset validate **khác nhau theo doctype**: `AL Accessory Set` = field vô hướng của meta ∪ 3 field tổng hợp; `AL Bom Set` = `FORMULA_FIELDS` ∪ 3 field tổng hợp ∪ **tên row literal đang bật**. Đây là permissive có chủ đích | Field nằm trong superset nhưng engine không tạo `{slug}__<field>` vẫn **qua validate** rồi ra 0 lúc chạy (ví dụ `items.x.max_area_m2` trên Bom Set, `items.x.supplier_location` trên Accessory). Ngược lại, `qty_formula` là Small Text nên **không** thuộc superset ⇒ bị **chặn lưu** | Chỉ khai **đại lượng** engine thật sự nạp; đừng suy "validate qua = có giá trị", cũng đừng suy "có trong form = qua validate" |

---

## 14. Đọc tiếp

| Tài liệu | Dành cho |
|---|---|
| [huong-dan-setting-bien.md](huong-dan-setting-bien.md) | Thao tác từng bước trên UI: tạo profile, thêm rule, khai cross-row, gán, xem trước |
| [vi-du-setting-day-du.md](vi-du-setting-day-du.md) | Ví dụ điền đủ 13 cột, 11 nguồn hiển thị thế nào, 3 profile hoàn chỉnh, cách tắt / chỉ hiện một số biến |
| [huong-dan-su-dung-tinh-nang.md](huong-dan-su-dung-tinh-nang.md) | Bức tranh tính năng v28_14 cho người dùng: 11 tính năng, tình huống thực tế, migrate/rollback |
| [vi-du-a-z.md](vi-du-a-z.md) | Một ví dụ xuyên suốt từ dữ liệu nền tới runtime, có số liệu |
| [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) | Đường đi của một biến từ autocomplete tới giá trị engine, kèm chỗ đứt gãy |
| [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) | Tra theo DocType: setting ở đâu, runtime B0–B7 đọc bảng nào |
| [api-reference.md](api-reference.md) | Tham số, shape trả về, quyền, ví dụ gọi API |
| [troubleshooting.md](troubleshooting.md) | Triệu chứng → nguyên nhân → cách xử lý |
| [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) | Thay đổi theo nhóm, migration, tương thích ngược |
| [../huong-dan-tinh-gia-full-flow.md](../huong-dan-tinh-gia-full-flow.md) | Luồng tính giá đầy đủ B0–B7 (quy ước tài liệu của repo) |
