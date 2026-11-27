# Ví dụ setting đầy đủ — `AL Variable Profile`
>
> 🔴 **Cập nhật 2026-11-27 (B2/R3):** `AL Variable Settings` **đã bị XOÁ** (bảng + 2 bảng con).
> Ba loại biến nay nằm
> trong **`AL Variable Library`**: biến người dùng nhập = bật **“Người dùng nhập”** (`is_input`);
> biến theo dòng = **Category = “Row Literals”**; còn lại = biến cấu hình. `default_profile` →
> **`AL Variable Profile.is_default`**; `preview_doctype` → **`AL Variable Profile.preview_doctype`**.
> 🔴 **Cập nhật 2026-11-27 (lần 2):** `AL Variable Library` chỉ còn **MỘT** nhóm — ô
> **Nhóm hiển thị** (Select); ô `category` cũ đã gộp vào đó. Mọi câu bên dưới nhắc `category`
> là **lịch sử**.
>
> Mọi câu bên dưới nhắc “mở `AL Variable Settings`” là **lịch sử đã xoá hẳn** — trạng thái hiện tại xem
> [thiết kế gộp cấu hình](../design/gop-noi-cau-hinh-bien-va-tinh-toan.md).


> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App / nhánh | `alumglass` — nhánh `main`, HEAD `566cdc2` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | Ví dụ cấu hình **đầy đủ mọi cột** của rule, ba profile hoàn chỉnh, cách tắt / chỉ hiện một số biến, và cách hệ thống hiển thị từng nguồn khi gõ |
> | Không dạy lại | Ngữ nghĩa từng field: [al-variable-profile.md](al-variable-profile.md) §3–§7. Thao tác bấm: [huong-dan-setting-bien.md](huong-dan-setting-bien.md) |
> | Mức kiểm chứng | Đọc từ **mã trong working tree**. Chưa chạy `bench migrate`, chưa mở form. Tên biến/bucket trong ví dụ là dữ liệu minh hoạ |
> | Ngày soạn | 2026-11-13 |

**Một câu phải nhớ:** profile chỉ quyết định **danh sách gợi ý khi gõ**. Nó ⛔ không vô hiệu hoá
biến, ⛔ không đổi giá trị tính, ⛔ không chặn lưu công thức dùng biến ngoài profile.

**Mục lục**

1. Hệ thống hiển thị gì khi gõ
2. Mười một nguồn: lấy từ đâu, hiện ra sao
3. Toàn bộ lựa chọn của một rule
4. Ví dụ 1 — `AL Cost Template`: chỉ hiện thứ dùng được
5. Ví dụ 2 — `AL Accessory Set`: đủ 8 nguồn + cross-row
6. Ví dụ 3 — `AL Bom Set`: cross-row thay cho row literal trần
7. Tắt hiển thị và chỉ hiện một số biến
8. Mười hiểu nhầm hay gặp
9. Cách kiểm sau khi setting
10. Đọc tiếp

---

## 1. Hệ thống hiển thị gì khi gõ

Mỗi biến trong autocomplete có 4 phần:

| Phần | Lấy từ đâu | Ví dụ |
|---|---|---|
| **Tên chèn vào công thức** | `name` của biến | `VL_NVL`, `W_mm`, `items.kinh_tren.width` |
| **Nhãn đọc được** | `label` — thường `mã — tên` | `VL_NVL — Nhôm vật liệu` |
| **Dòng chi tiết** | `type · group · value_source` | `Float · 01 · Vật liệu & chi phí · Tính tự động khi chạy B4-B5` |
| **Giá trị hiện tại** | `value`; rỗng hiện `—` | `125000` hoặc `—` |

Cùng một biến hiện ở **hai nhóm giao diện**:

- **Autocomplete khi gõ**: danh sách phẳng, mỗi dòng là một biến; nhóm/nguồn nằm ở dòng chi tiết.
- **Panel ngữ cảnh**: gom theo chuỗi `group · value_source` (nhóm lấy từ `group_label` của rule;
  không khai thì lấy nhóm gốc của nguồn). Vì vậy tiêu đề nhóm có thể dài, và **cùng một nhóm có thể
  tách làm hai** nếu nguồn giá trị khác nhau (ví dụ biến đã resolve và biến còn dùng default).

`items.<slug>.<field>` **không phải biến** — nó là *gợi ý chèn* (`references`), hiện ở nhóm tham
chiếu. Vì vậy có thể “không có biến `items.*`” mà vẫn “chèn được `items.*`”.

Danh sách được dựng theo 5 bước:

```
1. Profile resolve được?  ── không ──► đường legacy: bộ biến đầy đủ + AL Slug Library (xem §7.4)
2. Chọn nguồn được chạy theo default_action + rule Include
3. Nguồn sinh danh sách biến (name, label, value, group, source_ref…)
4. Áp rule: Exclude thắng → require_value → EXCLUDE_ALL → nhóm/thứ tự, only_fields
5. Gộp biến trùng tên → sắp theo sort_order/nhóm → trả biến + gợi ý chèn
```

---

## 2. Mười một nguồn: lấy từ đâu, hiện ra sao

| `source_kind` | Tên hiển thị của nguồn | Dữ liệu lấy từ | `name` / `source_ref` | Nhóm mặc định | `value_source` (phần sau nhóm ở dòng chi tiết) | Có giá trị? |
|---|---|---|---|---|---|---|
| `fvb_scope` | Formula Variable Binding | `Formula Variable Binding` đang bật, scope doctype cha + dòng con | `variable_name` / **`variable_name`** | `Bindings · FB (global)` hoặc `Bindings · <doctype>` | `Formula Variable Binding · <source_type> · <scope>` | Có, khi resolve ra khác `None` (kể cả `default_value`) |
| `cost_bucket` | Cost Bucket | `AL Cost Bucket` có `is_active=1` | `bucket_code` / **`bucket_code`** | `report_group` hoặc `Cost Bucket` | `Tính tự động khi chạy BomOrchestrator B4-B5` | **Thường `—`** — bucket chỉ có giá trị sau B5; nguồn resolve của autocomplete không chứa bucket |
| `variable_library_system` | System Variable | `AL Variable Library` có `is_system=1` | `var_name` / **`var_name`** | `System Variables` | `ĐÃ RESOLVE từ <doctype> '<docname>'` / `Engine resolve từ <src_doctype>.<src_field> khi chạy BOM` / `Default · AL Variable Library (is_system=1)` | Có, khi resolve được hoặc có `default_value` |
| `variable_library_user` | User Variable | `AL Variable Library` có `is_system=0` | `var_name` / **`var_name`** | `User Variables` | `Người dùng nhập khi mở dialog Tham số BOM` | **Không** — luôn `—` khi gợi ý |
| `variable_set` | AL Variable Set | `AL Variable Set.items` của set gắn với bản ghi (hoặc mã khai trong rule) | `item.variable` / **`set_code`** ⚠️ | `Variable Set · <set_code>` | `Từ Variable Set '<set_label>' — user nhập khi mở dialog` | Thường `—`; chỉ có khi biến trùng tên System Variable đã resolve hoặc có override ở `AL Profile System` |
| `cost_template_line` | Cost Template Line | `AL Cost Template.items` của template áp cho ngữ cảnh; có `row_index` thì bỏ dòng hiện tại và các dòng sau | `line_code` / **`line_code`** | `Cost Template Lines` | `Tính tuần tự khi BomOrchestrator chạy B6` | **Không** — luôn `—` khi gợi ý |
| `formula_global` | Formula Global Variable | `Formula Global Variable` đang bật | `var_name` / **`var_name`** | `Formula Global Variables` | `Hằng số toàn cục · CONSTANT/FORMULA` | Chỉ hằng số `CONSTANT` |
| `row_literal` | Row Literal | `AL Variable Settings.row_literals` đang bật | `var_name` / **`var_name`** | `row.group_label` hoặc `Row Literals` | `Engine inject per-row khi chạy BomOrchestrator B2` | Tuỳ dòng/chứng từ hiện tại |
| `common_var` | Common Variable | `AL Variable Settings.common_variables` | `var_name` / **`var_name`** | `row.group_label` hoặc `BOM Input Variables` | `Người dùng nhập khi mở dialog Tham số BOM` | **Thường `—`** — chỉ có khi trùng tên System Variable đã resolve hoặc có override ở `AL Profile System` |
| `doctype_field` | Doctype Field | Field vô hướng của **doctype chứa field đang sửa**: sửa field cấp cha ⇒ doctype cha; sửa field trên dòng con ⇒ doctype dòng con, giá trị đọc từ dòng đó | `fieldname` / **`fieldname`** | `Trường · <doctype>` | `Field của <doctype>` | Có, khi dòng/chứng từ đã có dữ liệu |
| `slug_reference` | — **không sinh biến** | `cross_row` của profile, meta bảng con, hoặc `AL Slug Library` ở đường legacy | **không sinh biến** | — | — | — |

> ⚠️ **`variable_set` là ngoại lệ về `source_ref`:** giá trị là **mã set** (`SET_CUA_DI`), không
> phải tên biến. Muốn lọc theo tên biến trong set, dùng `name_prefix` hoặc `name_regex`.

> ⚠️ **Ba nguồn thường không có giá trị lúc gợi ý:** `variable_library_user`, `cost_template_line`
> (luôn `—`), và `common_var` (thường `—` vì adapter đọc giá trị System Variable đã resolve, không
> đọc giá trị người dùng nhập ở dialog). Bật `require_value=1` trên rule của ba nguồn này sẽ
> **xoá sạch** chúng khỏi danh sách trong cấu hình mặc định.

---

## 3. Toàn bộ lựa chọn của một rule

Bảng con `AL Variable Profile Rule` có 13 cột. Cột nào bỏ trống thì hệ quả ghi ở cột cuối.

| # | Cột | Nhãn trên form | Nhận gì | Bỏ trống nghĩa là | Ảnh hưởng khi gõ | Bẫy |
|---|---|---|---|---|---|---|
| 1 | `action` | Hành động | `Include` / `Exclude` | UI bắt buộc | `Exclude` thắng mọi `Include` | Exclude chỉ loại biến **khớp đủ** điều kiện của nó |
| 2 | `source_kind` | Nguồn biến | 11 giá trị ở §2 | UI bắt buộc | Chọn nguồn để lọc | Rỗng (dữ liệu hỏng) khớp **mọi** nguồn |
| 3 | `source_ref` | Tham chiếu nguồn | Theo từng nguồn (§2); nhiều mã ngăn `\|` | Không lọc thêm | Giữ đúng bản ghi nguồn | `AUTO` phải viết HOA; `*` ⛔ không phải "tất cả set" với `variable_set` |
| 4 | `name_prefix` | Tiền tố tên | Nhiều tiền tố ngăn `\|` | Không lọc tiền tố | Chỉ giữ tên bắt đầu bằng tiền tố | **Phân biệt hoa thường** |
| 5 | `name_regex` | Regex tên biến | Regex Python, dùng `re.search` | Không lọc regex | Chỉ giữ tên khớp | Regex hỏng ⇒ **không khớp gì**, không báo lỗi UI |
| 6 | `category_tag` | Category | Nhiều nhãn ngăn `\|` | Không lọc category | So với `category` **hoặc** `group`, không phân biệt hoa thường | Dùng được với mọi nguồn theo `group`; muốn lọc theo `category` riêng thì nguồn phải có `category` |
| 7 | `var_type` | Kiểu biến | `Float/Int/Data/Select/Link/Check/Currency/Percent` | Không lọc kiểu | Chỉ giữ đúng kiểu | So khớp **chính xác**, phân biệt hoa thường |
| 8 | `source_type` | Source Type (FVB) | Giá trị `Formula Variable Binding.source_type` | Không lọc | Dùng chủ yếu với `fvb_scope` | Nguồn khác có `source_type` khác nên dễ ra rỗng |
| 9 | `only_fields` | Chỉ hiện ở field | JSON list fieldname, ví dụ `["width","height"]` | `[]` = **không giới hạn** | Biến chỉ hiện khi sửa field trong danh sách | ⛔ Không phải "ẩn hết"; ở form client vẫn lọc đúng, nhưng API/preview có `fieldname` + `INCLUDE_ALL` thì không phải cổng cứng |
| 10 | `require_value` | Bắt buộc có giá trị | Check | `0` = không đòi giá trị | Ẩn biến rỗng | Chỉ loại khi **chưa khớp Include nào khác**; ba nguồn thường rỗng sẽ mất sạch |
| 11 | `group_label` | Nhóm hiển thị | Tên nhóm hiển thị | Giữ nhóm gốc của nguồn | Đổi tiêu đề nhóm trong panel | Nhiều rule cùng biến: lấy rule `sort_order` nhỏ nhất |
| 12 | `sort_order` | Thứ tự nhóm | Số, mặc định `100` | 100 | Nhóm nhỏ trước; trong nhóm xếp theo tên | Bị **thay** bằng số của rule thắng, không phải số của biến |
| 13 | `is_active` | Đang dùng | Check, mặc định `1` | — | Tắt = rule bị bỏ qua hoàn toàn | Không xoá dữ liệu, bật lại là áp lại |

Ba cột của profile cần nhớ:

| Cột | Nhận gì | Ảnh hưởng |
|---|---|---|
| `default_action` | `INCLUDE_ALL` (mặc định DocType) / `EXCLUDE_ALL` | Quyết định "hiện tất cả rồi trừ" hay "chỉ hiện thứ khai" |
| `is_active` | Check | Tắt ⇒ profile bị bỏ qua, autocomplete về đường legacy |
| `profile_code` | Mã duy nhất | Dùng để gán vào bản ghi |

Bảng con `AL Variable Cross Row` có 6 cột: `table_field` (bảng con), `id_field` (field định danh
dòng, thường `slug`), `label_field` (nhãn đọc được), `fields` (JSON list field được chèn),
`include_index_form` (sinh thêm dạng `items[n]`), `enabled`. `fields` để trống = **mọi field vô
hướng**, gồm cả field engine không nạp — luôn khai tường minh.

---

## 4. Ví dụ 1 — `AL Cost Template`: chỉ hiện thứ dùng được

### 4.1 Dữ liệu giả định

| Nguồn | Dữ liệu |
|---|---|
| Cost Bucket | `VL_NVL`, `VL_NC`, `VL_PK`, `DO_DAY`, `DO_DAI` |
| Library hệ thống | `OFFSET_FRAME`, `NC_PCT` |
| Library người dùng | `KHOANG_HO`, `MAU_GO` |
| Common Variable | `W_mm`, `H_mm`, `n_panel` |
| Formula Global | `VAT_PCT` (CONSTANT, category `hang-so`), `PI` (category `hang-so`) |
| Binding | `DON_GIA_NHOM`, `DIEN_TICH_KINH` — `source_type = binding` |
| Cost Template Line | `LINE_NVL`, `LINE_NC`, `LINE_LOI_NHUAN` |
| Field dòng `AL Cost Template Item` | `line_code`, `cost_bucket`, `is_final_price` (ví dụ 3 tên; danh sách thật xem ghi chú dưới) |

> ℹ️ **`doctype_field` tự dò meta, không có cột chọn field.** Với `AL Cost Template Item`, nguồn này
> sinh **8** field vô hướng: `sort_order`, `line_code`, `line_label`, `cost_bucket`, `is_subtotal`,
> `is_final_price`, `is_pre_vat_price`, `show_on_quotation` (`calc_formula` là Small Text nên bị loại).
> Ví dụ dưới đây chỉ nêu 3 tên đại diện.

> ℹ️ **Đây là profile minh hoạ `P_CT_DEMO`, ⛔ không phải `P_COST_TEMPLATE_DEFAULT` đang được gán
> sẵn.** Profile mặc định chỉ có 6 rule (cost_bucket, cost_template_line, system var, global,
> binding, common var) — xem [huong-dan-su-dung-tinh-nang.md](huong-dan-su-dung-tinh-nang.md) §5.
> Mục đích của ví dụ này là chỉ ra **mọi cột hoạt động thế nào**, không phải dữ liệu seed.

### 4.2 Profile

`P_CT_DEMO` — `default_action = EXCLUDE_ALL`, `is_active = 1`, gán cho `AL Cost Template`.

| # | action | source_kind | source_ref | name_prefix | name_regex | category_tag | var_type | source_type | only_fields | require_value | group_label | sort_order | is_active |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Include | `cost_bucket` | `*` | | | | | | | 0 | `01 · Vật liệu & chi phí` | 10 | 1 |
| R2 | Include | `cost_template_line` | `AUTO` | | | | | | | 0 | `02 · Dòng giá thành` | 20 | 1 |
| R3 | Include | `variable_library_system` | `*` | | | | | | | 0 | `03 · Thông số hệ` | 30 | 1 |
| R4 | **Exclude** | `variable_library_system` | `NC_PCT` | | | | | | | 0 | | 100 | 1 |
| R5 | Include | `variable_library_user` | `*` | `KHOANG_\|MAU_` | | | | | | 0 | `04 · Thông số nhập` | 40 | 1 |
| R6 | Include | `formula_global` | `*` | | | `hang-so` | | | | 0 | `05 · Hằng số` | 50 | 1 |
| R7 | Include | `fvb_scope` | `AUTO` | | | | | `binding` | | 0 | `06 · Binding` | 60 | 1 |
| R8 | Include | `common_var` | `*` | | | | | | | 0 | `07 · Nhập tay` | 70 | 1 |
| R9 | Include | `doctype_field` | `*` | | | | | | `["calc_formula"]` | 0 | `08 · Field dòng giá thành` | 80 | 1 |
| R10 | Include | `row_literal` | `*` | | | | | | | 0 | — | 90 | **0** |

### 4.3 Người dùng thấy gì

Khi sửa `calc_formula` ở một dòng:

| Nhóm | Biến hiện ra | Vì sao |
|---|---|---|
| `01 · Vật liệu & chi phí` | `VL_NVL`, `VL_NC`, `VL_PK`, `DO_DAY`, `DO_DAI` — thường `—` vì autocomplete không chạy engine (lúc tính B6, bucket đã có giá trị) | R1 |
| `02 · Dòng giá thành` | `LINE_NVL`, `LINE_NC`, `LINE_LOI_NHUAN` — giá trị `—` | R2; B6 tính tuần tự |
| `03 · Thông số hệ` | `OFFSET_FRAME` | R3; `NC_PCT` bị R4 loại |
| `04 · Thông số nhập` | `KHOANG_HO`, `MAU_GO` — giá trị `—` | R5 |
| `05 · Hằng số` | `VAT_PCT` có giá trị; `PI` không phải `CONSTANT` nên `—` | R6 |
| `06 · Binding` | `DON_GIA_NHOM`, `DIEN_TICH_KINH` + giá trị resolve | R7, `source_type = binding` |
| `07 · Nhập tay` | `W_mm`, `H_mm`, `n_panel` — **giá trị `—`** (common var không đọc giá trị người dùng nhập) | R8 |
| `08 · Field dòng giá thành` | 8 field vô hướng của `AL Cost Template Item` (3 tên đại diện: `line_code`, `cost_bucket`, `is_final_price`) | R9, chỉ ở field `calc_formula` |

**Không thấy:** `row_literal` (`unit_price`, `glass_thick`…) — R10 tắt; và mọi nguồn không khai
(`variable_set`, `slug_reference`). `NC_PCT` không thấy dù R3 Include cả nguồn, vì Exclude thắng.

### 4.4 Thay đổi một ô, thấy khác ngay

| Sửa gì | Kết quả |
|---|---|
| Xoá R4 | `NC_PCT` hiện lại trong nhóm `03 · Thông số hệ` |
| R8 `require_value = 1` | Nhóm `07 · Nhập tay` **rỗng** — common var thường không có giá trị lúc gợi ý |
| R9 `only_fields = []` | Cả **8** field vô hướng của `AL Cost Template Item` hiện ở **mọi** field |
| R5 `name_prefix` để trống | Mọi user var hiện, không chỉ `KHOANG_`, `MAU_` |
| R1 `name_regex = ^VL_` | Chỉ `VL_NVL`, `VL_NC`, `VL_PK`; `DO_*` biến mất |
| R2 `source_ref = LINE_NVL` | Chỉ gợi ý đúng dòng `LINE_NVL` |
| R5 `sort_order = 5` | Nhóm `04 · Thông số nhập` lên đầu; `group_label` chỉ đổi tên, ⛔ không đổi thứ tự |

---

## 5. Ví dụ 2 — `AL Accessory Set`: đủ 8 nguồn + cross-row

Đây là profile mẫu `P_ACCESSORY_DEFAULT` do patch tạo, viết đầy đủ cột.

| # | action | source_kind | source_ref | name_prefix | name_regex | category_tag | var_type | source_type | only_fields | require_value | group_label | sort_order | is_active |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Include | `cost_bucket` | `*` | | | | | | | 0 | `01 · Vật liệu & chi phí` | 10 | 1 |
| R2 | Include | `variable_library_system` | `*` | | | | | | | 0 | `02 · Thông số hệ` | 20 | 1 |
| R3 | Include | `variable_set` | `AUTO` | | | | | | | 0 | `03 · Thông số nhập` | 30 | 1 |
| R4 | Include | `formula_global` | `*` | | | | | | | 0 | `04 · Hằng số` | 40 | 1 |
| R5 | Include | `fvb_scope` | `AUTO` | | | | | | | 0 | `05 · Binding` | 50 | 1 |
| R6 | Include | `common_var` | `*` | | | | | | | 0 | `06 · Thông số nhập` | 60 | 1 |
| R7 | Include | `row_literal` | `*` | | | | | | | 0 | `07 · Dòng hiện tại` | 70 | 1 |
| R8 | Include | `slug_reference` | `items` | | | | | | | 0 | `08 · Dòng khác` | 80 | 1 |

Cross-row của profile:

| `table_field` | `id_field` | `label_field` | `fields` | `include_index_form` | `enabled` |
|---|---|---|---|---|---|
| `items` | `slug` | `item_code` | `["qty","unit_price","calc_pattern","total_qty","line_total"]` | 1 | 1 |

**Kết quả khi sửa `qty_formula`:**

- 8 nhóm biến theo R1–R8; `variable_set` lấy đúng set gắn với bộ phụ kiện (`source_ref = AUTO`).
- Gợi ý chèn: `items.<slug>.qty`, `.unit_price`, `.calc_pattern`, `.total_qty`, `.line_total`
  và dạng `items[n].<field>` (chỉ để tra, ⛔ không dùng trong công thức). Engine còn tạo
  `{slug}__unit_qty`; muốn dùng thì thêm `unit_qty` vào `fields`.
- `qty_formula` **không** được khai trong `fields` vì đây là chuỗi công thức; engine không tạo
  `{slug}__qty_formula`.

**Thay đổi một ô:**

| Sửa gì | Kết quả |
|---|---|
| R7 `is_active = 0` | Mất nhóm `07 · Dòng hiện tại` (các `unit_price`, `glass_thick` trần) |
| R8 `source_ref = *` | Rule không trỏ bảng nào ⇒ **không lọc** danh sách cross-row; references vẫn sinh theo cross-row. Chỉ khi bỏ luôn cross-row thì `EXCLUDE_ALL` mới không sinh `items.*` |
| `fields` bỏ `total_qty` | Không còn gợi ý `items.x.total_qty`; công thức cũ vẫn chạy |
| `fields` để trống | Gợi ý **mọi field vô hướng** của `AL Accessory Item`, gồm cả field engine không nạp |
| `include_index_form = 0` | Chỉ còn dạng `items.<slug>.<field>` |
| `enabled = 0` | Không sinh references từ cross-row; nếu có R8 thì R8 vẫn sinh |

---

## 6. Ví dụ 3 — `AL Bom Set`: cross-row thay cho row literal trần

Profile `P_BOM_DEFAULT` (patch `seed_bom_profile`) — `default_action = EXCLUDE_ALL`.

| # | action | source_kind | source_ref | name_prefix | name_regex | category_tag | var_type | source_type | only_fields | require_value | group_label | sort_order | is_active |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Include | `variable_library_system` | `*` | | | | | | | 0 | `01 · Thông số hệ` | 10 | 1 |
| R2 | Include | `variable_set` | `AUTO` | | | | | | | 0 | `02 · Thông số nhập` | 20 | 1 |
| R3 | Include | `common_var` | `*` | | | | | | | 0 | `03 · Thông số nhập` | 30 | 1 |
| R4 | Include | `formula_global` | `*` | | | | | | | 0 | `04 · Hằng số` | 40 | 1 |
| R5 | Include | `fvb_scope` | `AUTO` | | | | | | | 0 | `05 · Binding` | 50 | 1 |
| R6 | Include | `slug_reference` | `items` | | | | | | | 0 | `06 · Dòng khác` | 60 | 1 |

Cross-row: `table_field = items`, `id_field = slug`, `label_field = line_name`,
`fields = ["width","height","qty","unit_qty","unit_price","total_qty","line_total",
"weight_per_unit","glass_thick","glass_type","calc_pattern","scrap_pct"]`, `include_index_form = 1`.

**Cố ý không có `row_literal` và `cost_bucket`:**

- `cost_bucket` chỉ có giá trị **sau B5**, còn công thức dòng chạy ở **B4** ⇒ gợi ý sẽ dẫn tới 0.
- `row_literal` trần (`unit_price`, `glass_thick`…) không có trong ngữ cảnh B4; muốn dùng thì
  tham chiếu qua dòng: `items.<slug>.unit_price`.

**Kết quả:** 6 nhóm biến + references `items.<slug>.<field>` cho 12 field khai trong cross-row.

| Sửa gì | Kết quả |
|---|---|
| Thêm R7 Include `row_literal` | Biến trần hiện và lưu được, nhưng tính ra **0** — ⛔ đừng thêm |
| Thêm `cost_bucket` vào profile | Như trên: hiện, lưu được, ra **0** |
| R6 bỏ (không có rule slug) nhưng vẫn có cross-row | References vẫn sinh theo cross-row — không cần rule slug |
| Bỏ luôn cross-row | Với `EXCLUDE_ALL`: **không** gợi ý `items.*` (nếu profile resolve được) |
| `fields` thêm `show_condition` | Gợi ý được, nhưng đây là field điều kiện, không phải đại lượng — dễ nhầm |

---

## 7. Tắt hiển thị và chỉ hiện một số biến

### 7.1 Năm cách “tắt”, khác nhau hoàn toàn

| Muốn | Cách làm | Phạm vi ảnh hưởng |
|---|---|---|
| **Tắt hẳn một biến ở mọi nơi** | Rule **Exclude** khớp đúng nguồn + tên | Biến không còn trong gợi ý ở mọi field, mọi bản ghi dùng profile. Công thức cũ vẫn chạy |
| **Tắt hẳn một nguồn** | `EXCLUDE_ALL` và **không** Include nguồn đó | Không có biến nào của nguồn xuất hiện |
| **Chỉ hiện một số biến** (allowlist) | `EXCLUDE_ALL` + rule Include thật hẹp (`source_ref`, `name_prefix`, `name_regex`) | Mọi thứ không khớp Include đều biến mất |
| **Vẫn có biến, chỉ ẩn ở vài field** | Rule Include `only_fields = ["width","height"]` | Trên form, client lọc đúng theo field đang sửa ở mọi chế độ. Ở API/preview có truyền `fieldname`, `INCLUDE_ALL` không phải cổng cứng — muốn chắc ở mọi đường dùng `EXCLUDE_ALL` |
| **Ẩn biến rỗng** | `require_value = 1` | Ẩn khi chưa có giá trị — và chỉ khi biến **chưa khớp Include nào khác** |

> 🔴 **“Tắt hiển thị” ⛔ không phải “vô hiệu hoá biến”.** Không có cột nào trong profile chặn người
> dùng gõ tay biến đó, chặn lưu, hay đổi giá trị tính. Muốn chặn thật phải sửa validate/engine.

### 7.2 Tắt hẳn một biến — ví dụ đúng cho từng nguồn

| Nguồn | Rule Exclude đúng | Ghi chú |
|---|---|---|
| `cost_bucket` | `source_kind=cost_bucket`, `source_ref=VL_PK` | `source_ref` là mã bucket |
| `variable_library_system/user` | `source_kind=...`, `source_ref=NC_PCT` | `source_ref` là tên biến |
| `variable_set` | `source_kind=variable_set`, **`name_prefix=NC_PCT`** | ⛔ `source_ref` là **mã set**, không phải tên biến |
| `fvb_scope` | `source_kind=fvb_scope`, `source_ref=DON_GIA_NHOM` | `source_ref` là `variable_name` |
| `cost_template_line` | `source_kind=cost_template_line`, `source_ref=LINE_LOI_NHUAN` | `source_ref` là `line_code` |
| `formula_global` | `source_kind=formula_global`, `source_ref=PI` | |
| `row_literal` | `source_kind=row_literal`, `source_ref=glass_thick` | `source_ref` là tên row literal |
| `common_var` | `source_kind=common_var`, `source_ref=W_mm` | `source_ref` là tên biến nhập tay |
| `doctype_field` | `source_kind=doctype_field`, `source_ref=line_code` | Là field của doctype chứa field đang sửa |

Nếu **cùng một tên** đến từ nhiều nguồn (ví dụ `unit_price` vừa là row literal vừa là binding),
một rule Exclude chỉ loại biến khớp điều kiện của nó. Muốn loại mọi nguồn cùng tên ⇒ tạo
**mỗi nguồn một rule Exclude**, hoặc dùng `name_regex = ^unit_price$` với từng nguồn.

### 7.3 Chỉ hiện một số biến, không tắt hẳn

**Cách A — allowlist toàn bộ (khuyến nghị):** `EXCLUDE_ALL` + vài rule Include hẹp.

| # | action | source_kind | source_ref | name_prefix | name_regex | only_fields | group_label | sort_order |
|---|---|---|---|---|---|---|---|---|
| 1 | Include | `variable_library_system` | | `OFFSET_\|NC_` | | | `01 · Thông số hệ` | 10 |
| 2 | Include | `cost_bucket` | `VL_NVL` | | | | `02 · Vật liệu` | 20 |
| 3 | Include | `formula_global` | | | `^VAT_` | | `03 · Thuế` | 30 |

Kết quả: chỉ `OFFSET_FRAME`, `NC_PCT`, `VL_NVL`, `VAT_PCT`. Tất cả biến khác — dù cùng nguồn —
không hiện, vì `EXCLUDE_ALL` và không khớp Include nào.

**Cách B — vẫn giữ nguồn, chỉ giới hạn field:** `EXCLUDE_ALL`, rule Include `only_fields`.

| # | action | source_kind | source_ref | only_fields | group_label |
|---|---|---|---|---|---|
| 1 | Include | `variable_library_system` | | `["width","height"]` | `01 · Kích thước` |
| 2 | Include | `common_var` | | `["qty","calc_formula"]` | `02 · Số lượng` |

Kết quả: khi sửa `width`/`height` thấy nhóm 1; khi sửa `qty`/`calc_formula` thấy nhóm 2; field
khác **không thấy** cả hai. Đây là “chỉ hiện một số biến theo field”, không phải tắt biến.

**Cách C — ẩn khỏi gợi ý nhưng công thức cũ vẫn hợp lệ:** chỉ cần **không Include** biến đó.
Validate dùng universe đầy đủ, nên công thức đã có vẫn lưu và chạy; người dùng gõ tay vẫn được.

### 7.4 Khi profile không được áp

Nếu bản ghi chưa resolve được profile (record mới chưa lưu, `variable_profile` trống +
`default_profile` trống, profile `is_active=0`), autocomplete chạy **đường legacy**:

- Bộ biến legacy **đầy đủ** — không bị rule nào lọc.
- References **luôn** có `items.<slug>.{field}` từ `AL Slug Library`, ⛔ không liên quan
  `slug_reference`.

Đây là lý do phổ biến nhất của “đã bỏ `slug_reference` mà vẫn thấy `items.*`”.
Chi tiết và cách đọc dấu hiệu: [al-variable-profile.md](al-variable-profile.md) §7.2.1.

### 7.5 Bảng chọn nhanh

| Tôi muốn… | Làm thế này |
|---|---|
| Giấu `NC_PCT` | Exclude `variable_library_system` + `source_ref=NC_PCT` |
| Giấu cả nguồn binding | `EXCLUDE_ALL`, không Include `fvb_scope`; hoặc Exclude `fvb_scope` + `source_ref=*` |
| Chỉ hiện biến có giá trị | `require_value=1` trên rule Include (nhớ **ba nguồn** thường rỗng: user var, cost template line, common var) |
| Chỉ hiện biến ở field `width` | `only_fields=["width"]` + `EXCLUDE_ALL` |
| Chỉ hiện 5 biến | `EXCLUDE_ALL` + Include với `name_regex`/`name_prefix` hẹp |
| Đổi tên nhóm | `group_label` trên rule |
| Đưa nhóm lên đầu | `sort_order` nhỏ hơn |
| Chỉ gợi ý chéo vài field | `cross_row.fields` tường minh |
| Không gợi ý chéo dòng nào | `EXCLUDE_ALL` + không có cross-row, không rule `slug_reference`, và bảo đảm profile resolve được |
| Giữ biến nhưng không cho chèn | Không có cơ chế — profile chỉ lọc; biến vẫn gõ tay được |

---

## 8. Mười hiểu nhầm hay gặp

| # | Hiểu nhầm | Thực tế |
|---|---|---|
| 1 | Profile tắt biến là biến không dùng được nữa | Chỉ tắt **gợi ý**; công thức cũ vẫn chạy, gõ tay vẫn lưu |
| 2 | `EXCLUDE_ALL` + 1 rule Include = “tất cả trừ nhóm đó” | Là “**chỉ** nguồn được Include”; nguồn khác mất hẳn |
| 3 | `INCLUDE_ALL` + 1 rule Include = vẫn hiện tất cả | Cũng là “chỉ nguồn được Include” |
| 4 | `only_fields=[]` là ẩn hết | Là **không giới hạn**. Chỉ ẩn hết khi phạm vi của nguồn và của rule **giao rỗng** — ví dụ binding chỉ áp cho `qty` nhưng rule chỉ cho `width` |
| 5 | `only_fields` chặn được ở mọi chế độ | Trên form, client luôn lọc theo field đang sửa. Ở API/preview có truyền `fieldname` và `default_action=INCLUDE_ALL`, biến không khớp field **vẫn được giữ**; muốn cổng cứng ở mọi đường dùng `EXCLUDE_ALL` |
| 6 | `require_value` là cổng tuyệt đối | Chỉ loại khi biến **chưa khớp Include nào khác** |
| 7 | `source_ref` luôn là tên biến | Với `variable_set` là **mã set**; với `slug_reference` là **tên bảng con** |
| 8 | `slug_reference` sinh biến | Không. Nó chỉ sinh **references** `items.*` |
| 9 | Bỏ `slug_reference` là hết `items.*` | Còn `cross_row`, `INCLUDE_ALL`, hoặc đường legacy khi profile chưa resolve |
| 10 | Sửa profile xong là thấy ngay | Client cache context 5 phút; reload trước khi kết luận |

---

## 9. Cách kiểm sau khi setting

1. **Preview**: mở profile → **Xem trước danh sách biến** → chọn doctype/bản ghi/bảng con/field.
   So số nhóm và từng tên với bảng kỳ vọng ở §4–§6.
2. **`meta.profile_code`**: gọi `get_formula_context`; có mã ⇒ catalog đang chạy;
   `profile: null` ⇒ đang legacy (mọi rule bị bỏ qua).
3. **`meta.duplicates`**: xem biến trùng tên bị gộp từ nguồn nào — tránh tưởng “mất biến”.
4. **`meta.excluded_by_rules`**: số biến bị loại; tăng bất thường sau khi thêm rule ⇒ kiểm
   `name_regex` hỏng hoặc `source_ref` sai hệ.
5. **References**: `references.length`; với `EXCLUDE_ALL` + không cross-row + không rule slug
   phải bằng **0**.
6. **Thử công thức ngoài profile**: phải **lưu được** — nếu bị chặn là sai thiết kế.

API và shape đầy đủ: [api-reference.md](api-reference.md). Chẩn đoán theo triệu chứng:
[troubleshooting.md](troubleshooting.md) §2.4 · §2.7.1.

---

## 10. Đọc tiếp

| Tài liệu | Nội dung |
|---|---|
| [al-variable-profile.md](al-variable-profile.md) | Ngữ nghĩa từng field, thuật toán rule, cross-row, giới hạn |
| [huong-dan-setting-bien.md](huong-dan-setting-bien.md) | Thao tác từng bước trên UI |
| [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) | Từng DocType: nguồn nào, điều kiện nào, runtime nào |
| [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) | Một biến đi từ gợi ý tới engine |
| [troubleshooting.md](troubleshooting.md) | Triệu chứng → nguyên nhân → xử lý |
| [api-reference.md](api-reference.md) | API, tham số, shape |
