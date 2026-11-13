# Hướng dẫn setting biến trên UI (Variable Profile)

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `90892c1` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | Thao tác cấu hình trên form: `AL Variable Profile`, rule, cross-row, gán profile, xem trước |
> | Đối tượng | BOM Manager / admin (quyền `System Manager` theo JSON mặc định) |
> | ⛔ Ngoài phạm vi | Cách engine tính tiền; shape API chi tiết (xem [api-reference.md](api-reference.md)) |
> | Ngày soạn | 2026-11-12 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa mở form trên site**. Nội dung đọc từ
> JSON DocType, controller Python và JS của working tree v28_14. Nếu màn hình khác mô tả, đối
> chiếu [troubleshooting.md](troubleshooting.md) trước khi kết luận tài liệu sai.

> 🔴 **Đọc trước một dòng:** profile **chỉ lọc danh sách gợi ý**. Nó ⛔ không đổi giá trị tính
> toán, ⛔ không chặn công thức cũ. Validate khi lưu dùng universe đầy đủ
> (`include_all_sources=True`). Xem mục 10.

---

## 0. Trước khi bắt đầu

```bash
bench --site <dev> migrate           # tạo 7 DocType mới + cột variable_profile + chạy patch seed
bench build --app alumglass          # nạp JS mới (hooks.py đã bump v=1.2.0)
```

Kiểm tra nhanh sau migrate:

1. Mở `AL Variable Profile` → phải thấy 3 record: `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`, `P_BOM_DEFAULT`.
2. Mở `AL Variable Settings` → `common_variables` có 8 dòng, `row_literals` có 10 dòng.
3. Mở `AL Formula Field` → có 11 dòng đang bật.
4. Mở `AL Bom Set` → field **Variable Profile** xuất hiện và **đã trỏ `P_BOM_DEFAULT`** nếu trước migrate để trống. Bộ Bom Set tạo **sau** migrate thì field để trống là bình thường — phải chọn tay.

Chưa thấy các mục trên ⇒ migrate chưa chạy hoặc patch chưa vào sổ. Xem
[troubleshooting.md](troubleshooting.md) mục "Migrate chưa chạy".

> ⚠️ **Quyền:** 3 DocType cấu hình (`AL Variable Profile`, `AL Variable Settings`,
> `AL Formula Field`) mặc định chỉ `System Manager` đọc/ghi. Tài khoản BOM Manager
> thường ngày sẽ **không mở được** các form này cho tới khi được cấp quyền.

---

## 1. Tạo một profile

**Đường đi:** Desk → tìm `AL Variable Profile` → **New**.

| Field | Bắt buộc | Ý nghĩa | Cách chọn |
|---|---|---|---|
| `profile_code` | Có | Mã profile, cũng là tên record (`autoname = field:profile_code`) | Đặt theo quy ước `P_<NGỮ_CẢNH>`, ví dụ `P_BOM_CUA_DI` |
| `profile_name` | Có | Tên hiển thị | Tiếng Việt, đọc được |
| `is_active` | — | Tắt = profile bị bỏ qua, hệ thống rơi về legacy | Mặc định bật |
| `default_action` | Có | `INCLUDE_ALL` = cho tất cả rồi trừ; `EXCLUDE_ALL` = chỉ cho đúng thứ được khai | Dùng `EXCLUDE_ALL` khi muốn danh sách gọn |
| `description` | — | Ghi chú nội bộ | Nên ghi ngữ cảnh sử dụng |

### `default_action` chọn cái nào?

| Chọn | Kết quả | Khi nào dùng |
|---|---|---|
| `INCLUDE_ALL` | Mọi biến của các nguồn được chạy đều hiện, trừ biến khớp rule Exclude | Muốn "ít thay đổi so với cũ", chỉ giấu vài nhóm rác |
| `EXCLUDE_ALL` | **Chỉ** biến khớp ít nhất một rule Include mới hiện | Muốn danh sách đúng ngữ cảnh (khuyến nghị cho profile mới) |

> ⚠️ Với `INCLUDE_ALL` **có** rule Include: hệ thống chỉ chạy adapter của các nguồn được
> Include (tránh query thừa). Không có rule Include nào ⇒ chạy **tất cả** adapter.
> Đây là lý do một profile `INCLUDE_ALL` rỗng không làm mất biến nào.

Lưu profile. Nếu `only_fields` của rule sai định dạng JSON, hệ thống **chặn lưu** và báo
đúng số dòng rule.

---

## 2. Thêm rule Include / Exclude

**Đường đi:** trong form profile → bảng **Luật lọc biến** (`rules`) → **Add Row**.

Thứ tự áp dụng cố định, ⛔ không phụ thuộc thứ tự bạn nhập:

```
1. Rule Exclude khớp  → loại (Exclude LUÔN thắng Include)
2. EXCLUDE_ALL        → chỉ giữ biến khớp một rule Include
3. Rule Include khớp  → gắn nhóm + thứ tự nhóm của rule
4. Dedup trùng tên    → giữ một nguồn, ghi phần bị bỏ vào meta.duplicates
```

### Giải thích từng cột

| Cột | Bắt buộc | Nhận gì | Chi tiết dễ sai |
|---|---|---|---|
| `action` | Có | `Include` / `Exclude` | Exclude thắng mọi Include |
| `source_kind` | Có | 1 trong 11 nguồn (mục 3) | Chọn sai nguồn ⇒ rule không khớp gì, biến biến mất im lặng |
| `source_ref` | — | `*`, rỗng hoặc `AUTO` = **không lọc thêm** (tập biến vẫn do ngữ cảnh sinh ra; riêng `variable_set` là set gắn với bản ghi). Ngược lại: danh sách ngăn `\|` | Với `slug_reference` phải là **tên bảng con thật** (`items`), ⛔ không dùng `*` |
| `name_prefix` | — | Danh sách tiền tố ngăn `\|`, ví dụ `W_\|H_\|TONG_` | **Phân biệt hoa thường** |
| `name_regex` | — | Regex Python, dùng `re.search` | Regex hỏng ⇒ coi như không khớp, ⛔ không báo lỗi ra UI |
| `category_tag` | — | Danh sách ngăn `\|`, so với `category` **hoặc** `group` của biến | Không phân biệt hoa thường |
| `var_type` | — | `Float`, `Int`, `Data`, `Select`, `Link`, `Check`, `Currency`, `Percent` | So khớp **chính xác** |
| `source_type` | — | `source_type` của Formula Variable Binding, ví dụ `custom_function` | Chỉ có tác dụng với nguồn `fvb_scope` |
| `group_label` | — | Tên nhóm hiện trong autocomplete, ví dụ `01 · Chi phí` | Đặt số đầu nhóm để sắp thứ tự dễ đọc |
| `sort_order` | — | Số nguyên, mặc định 100 | Nhóm nhỏ đứng trước; rule khớp đầu tiên thắng khi hoà |
| `only_fields` | — | **JSON list** tên field, ví dụ `["qty","width"]` | `[]` hoặc để trống = **không giới hạn**, ⛔ không phải "ẩn hết". Autocomplete: server gắn, **client lọc** theo field đang sửa. API có `fieldname`: **server lọc** ngay |
| `require_value` | — | Chỉ hiện khi biến resolve được giá trị thật | Bật cho profile "chỉ thấy cái dùng được" |
| `is_active` | — | Tắt rule mà không xoá | |

### Nhiều rule Include cùng khớp một biến

- **Nhóm + thứ tự**: lấy từ rule có `sort_order` nhỏ nhất (hoà thì rule khai trước).
- **only_fields**: hợp của mọi rule khớp. Nếu **một** rule không giới hạn ⇒ biến không
  giới hạn. Đây là chủ ý: một rule "cho mọi field" không được bị rule khác thu hẹp oan.

### Nội bộ `hide_all` — ⛔ không phải field cấu hình

Mỗi biến có thể mang phạm vi field từ **hai phía**: nguồn (ví dụ binding khai
`applies_to_field`) và rule. Hệ thống lấy **giao** hai phạm vi. Nếu giao **rỗng**, biến bị
đánh dấu `hide_all=true` — ẩn ở **mọi** field, khác hẳn `only_fields=[]` (không giới hạn).

`hide_all` do server gắn, **không có field** trong `AL Variable Profile Rule`. Khi chẩn
đoán "biến không hiện ở đâu cả", đọc `hide_all` trong kết quả API.

---

## 3. Mười một `source_kind`

| `source_kind` | Lấy biến từ đâu | `source_ref` nhận gì | Ví dụ |
|---|---|---|---|
| `cost_bucket` | `AL Cost Bucket` đang bật (`is_active=1`) | `bucket_code` hoặc `*` | `VL_NHOM`, `TONG_VL` |
| `variable_library_system` | `AL Variable Library` có `is_system=1` | `var_name` hoặc `*` | `OFFSET_FRAME`, `NC_PCT` |
| `variable_library_user` | `AL Variable Library` có `is_system=0` | `var_name` hoặc `*` | `W_mm`, `H_mm`, `TONG_M2` |
| `variable_set` | `AL Variable Set` gắn với chứng từ | `set_code`, `AUTO` hoặc `*` | `AUTO` = bộ của chính bản ghi |
| `cost_template_line` | Các `line_code` của `AL Cost Template` **đứng trước** dòng đang sửa (chỉ khi API có `row_index`) | `AUTO` = mọi dòng; hoặc **`line_code`** | `TONG_VL`, dòng tự định nghĩa |
| `formula_global` | `Formula Global Variable` đang bật | `var_name` hoặc `*` | `VAT_RATE`, hằng số dùng chung |
| `fvb_scope` | `Formula Variable Binding` theo scope doctype cha + doctype dòng con | `AUTO` / `*` = mọi binding; hoặc **tên biến** (vd `OFFSET_FRAME`) | `AUTO` = mọi binding áp cho ngữ cảnh |
| `row_literal` | `AL Variable Settings.row_literals` — biến engine inject **theo dòng** | `var_name` hoặc `*` | `unit_price`, `glass_thick` |
| `common_var` | `AL Variable Settings.common_variables` — biến người dùng nhập | `var_name` hoặc `*` | `W_mm`, `n_panel` |
| `doctype_field` | Field vô hướng của doctype cha hoặc dòng đang sửa | `fieldname` hoặc `*` | `customer`, `description` |
| `slug_reference` | Sinh **references** `items.<slug>.<field>`, ⛔ không sinh biến đơn | **Tên bảng con**, ví dụ `items` | Chỉ dùng để bật/tắt gợi ý chéo dòng |

> `slug_reference` là trường hợp đặc biệt: **không có adapter**. Nó điều khiển phần
> `references` trong kết quả API. Vì vậy 11 `source_kind` nhưng chỉ **10 adapter**.

> ⚠️ `fvb_scope` **không lọc theo doctype bằng `source_ref`**: `source_ref` của mỗi biến FVB
> là **tên biến**. Muốn giới hạn theo doctype hoặc loại nguồn, dùng `source_type`
> (ví dụ `custom_function`) hoặc `name_prefix` / `name_regex`. Scope doctype cha + dòng con
> do adapter tự lấy.

### `source_ref` với `variable_set` / `fvb_scope` / `cost_template_line`

- `AUTO` nghĩa là "tự dò theo bản ghi hiện tại":
  - `variable_set`: (1) field Link trực tiếp tới `AL Variable Set`; nếu không có,
    (2) field Link tới `AL Bom Set` → lấy `AL Bom Set.variable_set`; nếu không có,
    (3) field `product_type` → lấy bộ đang bật khớp `product_type` (bản `modified` gần nhất).
  - `fvb_scope`: `AUTO` / `*` = mọi binding áp cho ngữ cảnh; giá trị khác được hiểu là
    **tên biến**. Adapter tự lấy cả binding scope doctype cha và doctype dòng con.
  - `cost_template_line`: `AUTO` = mọi `line_code` đứng trước dòng đang sửa (khi có
    `row_index`); hoặc một `line_code` cụ thể.

---

## 4. `only_fields` và `require_value`

### `only_fields`

- Nhận **JSON list**: `["qty","width","height"]`.
- `[]`, chuỗi rỗng, hoặc để trống = **không giới hạn field**.
- **Hai đường lọc — đừng lẫn:**
  - **Autocomplete (bulk context):** `formula_setup.js` nạp context **một lần** cho
    `doctype + docname + child_table` và **không gửi `fieldname`** lên server. Server vẫn
    gắn `only_fields` (và `hide_all`) vào **từng biến**; client tự lọc theo field đang sửa
    bằng `_fieldExcluded()` trước khi đưa vào gợi ý. Vì vậy `only_fields` **vẫn có tác dụng**
    khi dùng autocomplete.
  - **Gọi API có `fieldname`** (validate, preview, gọi trực tiếp): server lọc rule ngay
    theo field — rule có `only_fields` không chứa field đó **không khớp**, nên các biến
    của rule bị loại khỏi kết quả.
- Nếu **không xác định được field** ở cả hai phía (API không truyền `fieldname` và client
  không có field đang sửa) thì không lọc — đây là đường an toàn ngược, ⛔ không phải
  "rule bị bỏ qua".

### Muốn mỗi field thấy một danh sách riêng

Tách biến giữa các rule bằng `source_ref` (hoặc `name_prefix` / `name_regex`).
Ví dụ 2 rule `row_literal`:

| # | source_kind | source_ref | only_fields | group_label |
|---|---|---|---|---|
| 11 | `row_literal` | `width\|height` | `["width","height"]` | `06a · Kích thước` |
| 12 | `row_literal` | `qty\|calc_pattern` | `["qty","calc_pattern"]` | `06b · Số lượng` |

- Mỗi biến chỉ do **một** rule chọn ⇒ bulk autocomplete vẫn đúng: `width`/`height` mang
  `only_fields` của rule 11, `qty`/`calc_pattern` mang của rule 12; `unit_price` không rule
  nào chọn ⇒ không hiện (`EXCLUDE_ALL`).
- Gọi API có `fieldname`: `width` → chỉ `width`/`height`; `qty` → chỉ `qty`/`calc_pattern`.
- Nếu **nhiều rule cùng chọn một biến** (`source_ref` chồng nhau) ⇒ `only_fields` lấy **hợp**;
  một rule không giới hạn ⇒ biến không giới hạn ⇒ khi đó không tách được biến đó theo field.
- ⛔ Đừng đặt 2 rule đều `source_ref = *` với `only_fields` khác nhau — cả hai cùng khớp mọi
  biến nên kết quả là **hợp**, không tách.

### `require_value`

- Bật: biến chỉ hiện khi có giá trị thật (`has_value`).
- Tắt: biến vẫn hiện với giá trị `—` để người dùng biết tên biến tồn tại.
- Lưu ý: `require_value` là cổng **toàn cục** cho biến đó — nếu rule khớp điều kiện nguồn
  nhưng biến rỗng, biến bị loại hẳn, ⛔ không rơi về "hiện với nhóm mặc định".

---

## 5. Cấu hình biến chéo dòng (`cross_row`)

**Đường đi:** trong form profile → bảng **Biến chéo dòng (slug)** → **Add Row**.

| Cột | Ý nghĩa | Ghi chú |
|---|---|---|
| `table_field` | Tên field bảng con, ví dụ `items` | Bắt buộc |
| `id_field` | Field định danh dòng, mặc định `slug` | Có thể là `custom_slug`, `line_ref`… |
| `label_field` | Field nhãn để đọc gợi ý, ví dụ `line_name` | Không có thì tự dò `line_name` → `item_code` |
| `fields` | JSON list field được gợi ý chéo | Để trống = mọi field vô hướng (dễ gợi ý field engine không nạp) |
| `include_index_form` | Sinh thêm dạng `items[0].field` | Mặc định bật |
| `enabled` | Tắt dòng mà không xoá | |

### Luật vàng: chỉ gợi ý field engine **thật sự inject**

Gợi ý một field mà engine không nạp ⇒ công thức chạy ra **0 âm thầm**. Vì vậy:

| Bảng con | Field nên khai | ⛔ Không khai |
|---|---|---|
| `AL Accessory Set.items` | `qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total` | `qty_formula` — đây là **chuỗi công thức**, engine không tạo `{slug}__qty_formula` |
| `AL Bom Set.items` | `width`, `height`, `qty`, `glass_thick`, `glass_type`, `unit_price`, `line_total`… (theo `cross_row.fields`) | Field không phải row literal / field công thức engine nạp |
| `AL Cost Template.items` | Không dùng cross-row | B6 không có context `items.*` |

Cú pháp người dùng gõ: `items.<slug>.<field>`.
Ví dụ: `items.kinh_tren.width`.

> ⚠️ **Dạng `items[0].width` chỉ là gợi ý, ⛔ không dùng trong công thức.**
> `include_index_form` sinh thêm dạng này để tra nhanh theo thứ tự hàng, nhưng runtime
> `inputs["items"]` là **dict khoá theo slug** và `_normalize_items_ref` chỉ đổi được dạng
> `items.<slug>.<field>` → `{slug}__{field}`. Gõ dạng chỉ số sẽ ra **0** (hoặc bị validate chặn).
> Luôn dùng dạng slug.

### Thứ tự sinh references khi không có `cross_row`

1. Có `cross_row` → dùng đúng cấu hình.
2. Không có, nhưng có rule Include `slug_reference` → chỉ sinh cho các bảng rule trỏ tới.
3. Không có cả hai + `default_action=INCLUDE_ALL` → sinh cho **mọi** bảng con (hành vi cũ).
4. `EXCLUDE_ALL` và không khai gì → **không** gợi ý chéo dòng.

> ⚠️ Bảng trên chỉ áp khi profile **resolve được** cho bản ghi. Nếu field `Variable Profile` còn
> trống (record mới chưa lưu, `default_profile` trống, profile tắt), autocomplete chạy đường cũ và
> **luôn** gợi ý `items.<slug>.{field}` từ `AL Slug Library` — bỏ rule `slug_reference` không tắt
> được. Kiểm bằng `profile: null` trong kết quả `get_formula_context`. Chi tiết:
> [al-variable-profile.md](al-variable-profile.md) §7.2.1.

---

## 6. Ba ví dụ có số liệu cụ thể

### Ví dụ A — `AL Cost Template` (profile mẫu `P_COST_TEMPLATE_DEFAULT`)

Profile do patch tạo, `default_action = EXCLUDE_ALL`, 6 rule Include:

| # | action | source_kind | source_ref | group_label | sort |
|---|---|---|---|---|---|
| 1 | Include | `cost_bucket` | `*` | `01 · Vật liệu & chi phí` | 10 |
| 2 | Include | `cost_template_line` | `AUTO` | `02 · Dòng tự định nghĩa` | 20 |
| 3 | Include | `variable_library_system` | `*` | `03 · Thông số hệ` | 30 |
| 4 | Include | `formula_global` | `*` | `04 · Hằng số` | 40 |
| 5 | Include | `fvb_scope` | `AUTO` | `05 · Binding` | 50 |
| 6 | Include | `common_var` | `*` | `06 · Thông số nhập` | 60 |

**Người dùng thấy:** bucket, dòng template đứng trước, system var, hằng số, binding,
common var.
**Người dùng ⛔ không thấy:** row literal (`width`, `unit_price`…), biến chéo dòng,
`doctype_field`, `variable_set`.

**Vì sao:** B6 chỉ có context `inputs ⊕ buckets`; gợi ý `width` hay `items.*` sẽ dẫn tới
công thức chạy ra 0/None. Common var **vẫn** gợi ý vì chúng nằm trong `inputs`
(`al_bom_vars`).

> Lưu ý dòng `cost_template_line`: khi sửa dòng thứ `n`, chỉ thấy `line_code` của các dòng
> **trước** nó. Đây là chủ ý — B6 tính tuần tự, tham chiếu dòng sau là tham chiếu vòng.
>
> ⚠️ **Giới hạn đã biết:** điều trên chỉ đúng khi API có `row_index` (preview/validate/gọi
> trực tiếp). Autocomplete bulk hiện **không gửi `row_index`**, nên có thể thấy cả dòng
> **sau** — ⛔ đừng tham chiếu dòng sau; công thức sẽ ra 0/vòng.

### Ví dụ B — `AL Accessory Set` (profile mẫu `P_ACCESSORY_DEFAULT`)

`default_action = EXCLUDE_ALL`, 8 rule Include:

| # | action | source_kind | source_ref | group_label | sort |
|---|---|---|---|---|---|
| 1 | Include | `cost_bucket` | `*` | `01 · Vật liệu & chi phí` | 10 |
| 2 | Include | `variable_library_system` | `*` | `02 · Thông số hệ` | 20 |
| 3 | Include | `variable_set` | `AUTO` | `03 · Thông số nhập` | 30 |
| 4 | Include | `formula_global` | `*` | `04 · Hằng số` | 40 |
| 5 | Include | `fvb_scope` | `AUTO` | `05 · Binding` | 50 |
| 6 | Include | `common_var` | `*` | `06 · Thông số nhập` | 60 |
| 7 | Include | `row_literal` | `*` | `07 · Dòng hiện tại` | 70 |
| 8 | Include | `slug_reference` | `items` | `08 · Dòng khác` | 80 |

`cross_row`:

| table_field | id_field | label_field | fields | include_index_form |
|---|---|---|---|---|
| `items` | `slug` | `item_code` | `["qty","unit_price","calc_pattern","total_qty","line_total"]` | 1 |

**Người dùng thấy:** biến user của **chính bộ phụ kiện** (`variable_set=AUTO`), row literal
của dòng hiện tại, và gợi ý `items.<slug>.qty`, `items.<slug>.unit_price`…
**⛔ Không thấy:** `items.<slug>.qty_formula` — field này là chuỗi công thức, không phải
giá trị engine inject.

> `label_field = item_code` vì `AL Accessory Item` **không có** `line_name`. Nếu chép cấu
> hình từ `AL Bom Set` sẽ ra nhãn chỉ có slug.

### Ví dụ C — `AL Bom Set` với cross-row `items.kinh_tren.width`

`AL Bom Set` có profile mẫu `P_BOM_DEFAULT` (patch `seed_bom_profile`; 6 rule + cross-row 12 field).
Ví dụ dưới đây tạo profile riêng `P_BOM_CUA_DI` để minh hoạ cơ chế cross-row:

- `default_action = EXCLUDE_ALL`
- Rule Include tối thiểu: `variable_library_system *`,
  `variable_set AUTO`, `formula_global *`, `fvb_scope AUTO`, `common_var *`,
  `slug_reference items`
- `cross_row`: `table_field=items`, `id_field=slug`, `label_field=line_name`,
  `fields=["width","height","qty","glass_thick","glass_type","unit_price","line_total"]`

> 🔴 **Riêng profile `AL Bom Set`: ⛔ đừng thêm `cost_bucket` và `row_literal`.** Công thức dòng
> BOM tính trước khi có bucket, và literal trần (`unit_price`…) không tồn tại trong namespace lúc
> tính — biến vẫn hiện trong gợi ý, lưu được, nhưng **ra 0 và không báo lỗi**. Dùng
> `items.<slug>.<field>` cho giá trị dòng. (Profile bộ phụ kiện `P_ACCESSORY_DEFAULT` hiện vẫn
> khai 2 nguồn này — khác Bom Set; nếu định bỏ thì kiểm lại riêng.)

Khi mở Bom Set `BS-CUA-DI-01`, dòng `items[0]` có `slug=kinh_tren`, sửa `qty`:

1. Client gọi `get_variable_catalog` với `child_table=items`, `row_index=0`, `fieldname=qty`.
2. Adapter `fvb_scope` lấy cả binding của `AL Bom Set` và `AL Bom Item`.
3. Nếu profile có rule `row_literal`: adapter đọc giá trị từ **dòng hiện tại**.
4. `build_references` sinh:
   - `items.kinh_tren.width` → nhãn `Chiều rộng — kính trên`
   - `items[0].width` → nhãn `Chiều rộng — hàng 1`
5. Người dùng gõ `items.` → thấy đúng các slug hiện có × field trong `cross_row.fields`.
6. Lưu: validate dùng `include_all_sources=True` → `kinh_tren__width` vẫn hợp lệ.
7. Runtime B3: engine đổi `items.kinh_tren.width` → `kinh_tren__width` và lấy giá trị thật.

> ⚠️ Nếu Bom Set **chưa gán profile**, hệ thống rơi về đường legacy: vẫn có gợi ý chéo
> dòng theo hành vi cũ (mọi bảng con), nhưng ⛔ không có bộ lọc theo `cross_row.fields`.

---

## 7. Gán profile cho bản ghi mẹ

| DocType | Field | Ghi chú |
|---|---|---|
| `AL Bom Set` | `variable_profile` | Áp cho field cha + mọi dòng `items` |
| `AL Cost Template` | `variable_profile` | Áp cho các dòng `items` (`calc_formula`) |
| `AL Accessory Set` | `variable_profile` | Áp cho `qty_formula` và gợi ý chéo dòng |
| `AL Alert Config` | `variable_profile` | Áp cho `trigger_condition` |

Không cần field trên bảng con: catalog nhận `doctype` + `docname` + `child_table` +
`row_index` rồi tự kế thừa profile của cha.

### `AL Variable Settings.default_profile`

- Chỉ áp cho doctype **đã khai field Link** tới `AL Variable Profile`.
- Doctype không có field đó ⇒ ⛔ **không** nhận default. Nếu không, một default toàn cục sẽ
  tự bật cho mọi doctype và làm autocomplete đổi hành vi ngoài ý muốn.
- Patch v28_14 **cố ý không set** `default_profile`; mọi doctype khác giữ legacy.

Thứ tự chọn profile (server, `_resolve_profile_doc`):

```
1. profile truyền tường minh (tham số `profile`)
2. field `variable_profile` trên bản ghi
3. AL Variable Settings.default_profile (chỉ khi doctype có field Link)
4. không có → legacy
```

---

## 8. Xem trước và đọc cảnh báo

### Xem trước danh sách biến

1. Mở profile **đã lưu** (nút chỉ hiện khi record không phải new).
2. Bấm **Công cụ → Xem trước danh sách biến**.
3. Nhập:
   - **DocType cần xem trước** (mặc định lấy từ `AL Variable Settings.preview_doctype`)
   - **Bản ghi** (không bắt buộc — nhập để resolve giá trị thật)
   - **Bảng con** (ví dụ `items`)
   - **Field đang sửa** (ví dụ `calc_formula`) — để áp `only_fields`
4. Bấm **Xem trước**.

Kết quả hiển thị theo nhóm, cột: Nhóm · Tên biến · Nhãn · Kiểu · Giá trị · Nguồn.
Đầu dialog có `Tổng` và `Bị luật loại`.

### Đọc cảnh báo trùng tên

Khi một tên biến đến từ nhiều nguồn, dialog hiện khung cam:

- **giữ**: nguồn thắng sau dedupe
- **bỏ**: (các) nguồn bị loại

Cảnh báo này **không** phải lỗi. Catalog chỉ giữ một nguồn cho mỗi tên. Nếu nguồn thắng
không phải nguồn bạn muốn, sửa bằng rule `group_label` / `sort_order`, hoặc dùng
`explain_variable` để xem vì sao.

Thứ tự dedupe: **có giá trị** → `sort_order` nhỏ hơn → adapter đăng ký trước → thứ tự
xuất hiện.

### Không có biến nào

Dialog báo "Profile này chưa trả về biến nào". Đọc tiếp thông báo:
- có `Bị luật loại: N` ⇒ rule Exclude hoặc `EXCLUDE_ALL` đang loại quá tay;
- không có ⇒ kiểm DocType/bảng con đã chọn và các rule Include.

---

## 9. Checklist sau khi setting (8 mục)

- [ ] **1. Profile đúng ngữ cảnh**: `default_action` hợp lý; `is_active=1`.
- [ ] **2. Rule không âm thầm vô hiệu**: mỗi `source_kind` đều tồn tại; `slug_reference`
      dùng tên bảng thật, ⛔ không dùng `*`.
- [ ] **3. `only_fields` là JSON list hợp lệ**; nhớ `[]` = không giới hạn.
- [ ] **4. Cross-row chỉ khai field engine inject**; với phụ kiện ⛔ không khai
      `qty_formula`.
- [ ] **5. Xem trước** trên 1 bản ghi **thật**, đúng cả `child_table` + `fieldname`.
- [ ] **6. Gán profile** trên bản ghi mẹ; thử gõ 3 từ khoá khác nhau trong autocomplete.
- [ ] **7. Lưu thử công thức dùng biến ngoài profile** → phải lưu được (không bị chặn oan).
- [ ] **8. Mở bản ghi thứ hai** trong cùng phiên → danh sách biến phải đổi theo bản ghi
      (nếu không, dính cache client — xem [troubleshooting.md](troubleshooting.md)).

---

## 10. Điều ⛔ KHÔNG được dùng profile để làm

| ⛔ Không dùng để | Vì sao | Muốn chặn thật thì |
|---|---|---|
| Đổi giá trị tính toán | Catalog là lớp gợi ý; runtime không đọc profile | Sửa engine / công thức — không có đường tắt qua profile |
| Chặn công thức cũ dùng biến ngoài profile | Validate dùng `include_all_sources=True`, universe đầy đủ | Viết kiểm riêng, ⛔ đừng dựa vào profile |
| Thay đổi dữ liệu đã lưu | Profile không ghi vào chứng từ | — |
| Chặn người dùng gõ biến ngoài danh sách | Autocomplete chỉ gợi ý; người dùng vẫn gõ tay được | Kiểm riêng nếu thật cần |

> ✅ Đã đo trong mã: `formula_validate.build_known_names()` gọi
> `get_formula_context(..., include_all_sources=True)` (`alumglass/al_bom_engine/formula_validate.py:73-76`);
> `cost_template.js` tách `fetchValidationContext()` dùng `include_all_sources: 1`
> (`alumglass/public/js/cost_template.js:224-243`). Đây là hai chỗ giữ cho validate
> không bị profile thu hẹp.

---

## 11. Đọc tiếp

- Toàn bộ nguồn biến và kiến trúc: [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) §3 nguồn, §5 gợi ý, §6 runtime
- Tra cứu **mọi field và mọi lựa chọn** của `AL Variable Profile`: [al-variable-profile.md](al-variable-profile.md)
- Ví dụ điền đủ 13 cột, cách tắt / chỉ hiện một số biến: [vi-du-setting-day-du.md](vi-du-setting-day-du.md)
- API và shape trả về: [api-reference.md](api-reference.md)
- Triệu chứng khi setting không ăn: [troubleshooting.md](troubleshooting.md)
- Thay đổi của bản vá: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md)
