# Ví dụ A→Z — setting biến gợi ý cho “Cửa đi nhôm kính 2 cánh”
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
> | App | `alumglass` — nhánh `main`, HEAD `566cdc2` (2026-11-12) **+ thay đổi v28_14 chưa commit**, gồm vá superset validate cross-row (2026-11-13) |
> | Phạm vi | Một ví dụ **xuyên suốt** từ tạo dữ liệu nền → profile → rule → cross-row → Settings → Formula Field → gán → xem trước → gõ thử → lưu → runtime |
> | Đối tượng | BOM Manager / admin cấu hình (quyền `System Manager` theo JSON mặc định) |
> | ⛔ Ngoài phạm vi | Lý thuyết cấu hình (xem [huong-dan-setting-bien.md](huong-dan-setting-bien.md)); shape API chi tiết (xem [api-reference.md](api-reference.md)) |
> | Ngày soạn | 2026-11-13 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa `bench build`, chưa mở form trên site.**
> Toàn bộ nội dung đọc từ 7 JSON DocType, controller Python, `public/js` và
> `engine/bom_orchestrator.py` của working tree. Chưa có bước nào được bấm tay.

> 🔴 **Số liệu trong tài liệu là VÍ DỤ MINH HOẠ**, ⛔ không phải golden case và ⛔ không lấy từ
> dữ liệu thật của khách. Giá, khối lượng, giá trị bucket đều được chọn cho dễ theo dõi phép tính.
> Đừng dùng chúng để đối chiếu kết quả tính giá thật.

> 🔴 **Đọc trước một dòng:** `AL Variable Profile` **chỉ lọc danh sách gợi ý**. Nó ⛔ không đổi
> giá trị tính toán, ⛔ không chặn công thức cũ. Bỏ profile đi thì BOM vẫn ra đúng số tiền cũ.
> Ranh giới này được nhắc lại ở mục 12.

**Đọc nhanh — chỉ cần một việc thì vào thẳng:**

| Bạn cần | Mục |
|---|---|
| Dựng dữ liệu nền đúng thứ tự (slug, Library, Set, Bucket, Template) | §1 |
| Tạo profile + rule lọc biến | §2 · §3 |
| Cho phép gợi ý `items.<slug>.<field>` | §4 |
| Đăng ký tên biến dòng / field công thức | §5 · §6 |
| Gán profile cho bản ghi | §7 |
| Xem trước danh sách biến | §8 |
| Gõ thử trong autocomplete | §9 |
| Chia danh sách theo field đang sửa | §10 |
| Hiểu vì sao lưu/chặn lưu | §11 |
| Biết vì sao ra 0 lúc tính tiền | §12 (đủ 8 nguyên nhân: [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) §14) |

---

## 0. Trước khi bắt đầu

### 0.1 Điều kiện

```bash
bench --site <dev> migrate          # tạo 7 DocType mới + cột variable_profile + chạy patch seed
bench build --app alumglass         # nạp JS mới (hooks.py đã bump v=1.2.0)
```

- Tài khoản cần **System Manager**: `AL Variable Profile`, `AL Variable Settings`,
  `AL Formula Field` mặc định chỉ cấp role này.
- Site phải cài **`formula_builder`** — thiếu app này, nguồn `fvb_scope` trả rỗng
  (các nguồn khác vẫn chạy).

### 0.2 Kiểm sau migrate — 4 con số

| Mở | Kỳ vọng | Nếu thiếu |
|---|---|---|
| `AL Variable Profile` | **3** profile mẫu: `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`, `P_BOM_DEFAULT` | migrate chưa chạy / patch chưa vào Patch Log |
| `AL Variable Settings` → Common Variables | **8** dòng | như trên |
| `AL Variable Settings` → Row Literals | **10** dòng (có `max_area_m2`) | như trên |
| `AL Formula Field` | **11** dòng `is_active=1` | như trên |

Kiểm thêm: form `AL Bom Set` phải có field **Variable Profile**. Thiếu ⇒ đối chiếu
[troubleshooting.md](troubleshooting.md) mục 2.6.

> **Đã có sẵn `P_BOM_DEFAULT`** cho `AL Bom Set` (patch `seed_bom_profile` tự gán cho bản ghi đang
> trống). Ví dụ dưới đây vẫn tạo profile riêng `P_BOM_CUA_DI` để đi qua **từng bước cấu hình**;
> nếu chỉ cần dùng ngay, mở `P_BOM_DEFAULT` và đối chiếu các mục 2–4, ⛔ **đừng** thêm
> `cost_bucket`/`row_literal` vào profile Bom Set (xem cảnh báo đầu mục 3).

---

## 1. Tạo dữ liệu nền

Tạo **theo đúng thứ tự dưới đây** — Set cần Library trước, template cần Bucket trước.

### 1.1 Slug (`AL Slug Library`) — 4 dòng

| slug | label | category (tuỳ chọn) |
|---|---|---|
| `khung_ngang_tren` | Khung ngang trên | `NHOM` |
| `khung_doc_trai` | Khung dọc trái | `NHOM` |
| `kinh_tren` | Kính trên | `KINH` |
| `ban_le` | Bản lề | `PHUKIEN` |

> `category` là Link tới `AL Material Category` — dùng giá trị nào thì phải có record đó trước,
> nếu không sẽ không lưu được. Bỏ trống cột này cũng chạy bình thường.

> Record name chính là `slug` (`autoname = field:slug`). Slug phải **duy nhất trong một Bom Set** —
> engine và validate đều dựa vào nó.

### 1.2 Biến thư viện (`AL Variable Library`) — 5 dòng

| var_name | var_label | var_type | is_system | category | default_value | Nguồn resolve (chỉ system) |
|---|---|---|---|---|---|---|
| `OFFSET_FRAME` | Khe hở khung (mm) | Float | 1 | `system` | 10 | `source_doctype`/`source_field` nếu muốn resolve tự động |
| `NC_PCT` | % nhân công | Float | 1 | `system` | 5 | như trên |
| `W_mm` | Chiều rộng (mm) | Float | 0 | `input` | — | người dùng nhập |
| `H_mm` | Chiều cao (mm) | Float | 0 | `input` | — | người dùng nhập |
| `TONG_M2` | Tổng diện tích (m²) | Float | 0 | `input` | — | người dùng nhập |

> `category` là chỗ **duy nhất** trong ví dụ này dùng tới `category_tag` của rule (mục 3).
> `category_tag` so **khớp chính xác, không phân biệt hoa thường** với `category` **hoặc**
> `group` của biến — ⛔ không phải so chứa chuỗi.

### 1.3 Bộ biến (`AL Variable Set`) — `VS_CUA_DI_01`

| Field | Giá trị |
|---|---|
| `set_code` | `VS_CUA_DI_01` |
| `set_name` | Bộ biến — cửa đi 2 cánh |
| `is_active` | 1 |
| `items` (3 dòng) | `W_mm` (sort 10), `H_mm` (20), `TONG_M2` (30) — mỗi dòng `variable` là **Link tới `AL Variable Library`**, nên phải tạo mục 1.2 trước |

### 1.4 Cost Bucket (`AL Cost Bucket`) — 4 dòng

| bucket_code | bucket_name | bucket_role | report_group | sort_order |
|---|---|---|---|---|
| `VL_NHOM` | Vật liệu nhôm | LEAF | `Vật liệu` | 10 |
| `VL_KINH` | Vật liệu kính | LEAF | `Vật liệu` | 20 |
| `VL_PK` | Phụ kiện | LEAF | `Vật liệu` | 30 |
| `TONG_VL` | Tổng vật liệu | AGGREGATE | `Vật liệu` | 40 |

> `report_group` chỉ dùng làm **nhóm gợi ý** khi chưa có `group_label` của rule. Trong ví dụ này
> rule đè nhóm, nên giá trị ở đây không quyết định thứ tự hiển thị.

### 1.5 Hằng số (`Formula Global Variable`) — `VAT_RATE`

| Field | Giá trị |
|---|---|
| `var_name` | `VAT_RATE` |
| `label` | Thuế GTGT |
| `var_type` | Float |
| `value_source` | `CONSTANT` |
| `constant_value` | `0.08` |
| `is_active` | 1 |

### 1.6 Dòng giá thành (`AL Cost Template`) — `CT_CUA_DI_01`

| sort_order | line_code | line_label | calc_formula | is_final_price |
|---|---|---|---|---|
| 10 | `TONG_VL` | Tổng vật liệu (chưa gồm phụ kiện) | `VL_NHOM + VL_KINH` | 0 |
| 20 | `TONG_VL_PK` | Tổng vật liệu + phụ kiện | `TONG_VL + VL_PK` | 0 |
| 30 | `GIA_VAT` | Giá sau VAT | `TONG_VL_PK * (1 + VAT_RATE)` | 1 |

> Template này **không bắt buộc** để chạy Bom Set. Nó tồn tại trong ví dụ để thấy nhóm
> `cost_template_line` (rule 10) và phép gõ ở `calc_formula` (mục 9), `only_fields` (mục 10).

---

## 2. Tạo `AL Variable Profile` `P_BOM_CUA_DI`

Desk → `AL Variable Profile` → **New**.

| Field | Giá trị ví dụ | Ghi chú |
|---|---|---|
| `profile_code` | `P_BOM_CUA_DI` | cũng là record name (`autoname = field:profile_code`) |
| `profile_name` | BOM cửa đi 2 cánh | tiếng Việt, đọc được |
| `is_active` | 1 | tắt = rơi về đường legacy |
| `default_action` | `EXCLUDE_ALL` | **chỉ** biến khớp một rule Include mới hiện |
| `description` | Bộ biến cho BOM cửa đi nhôm kính 2 cánh (ví dụ minh hoạ) | |

> Chọn `EXCLUDE_ALL` vì đây là profile mới, muốn danh sách đúng ngữ cảnh. `INCLUDE_ALL` chỉ hợp
> khi muốn “gần giống cũ, giấu vài nhóm rác”. Lưu ý: `INCLUDE_ALL` **rỗng rule** ⇒ hệ thống chạy
> **tất cả** adapter — danh sách sẽ quay về hành vi cũ.

---

## 3. Rules — bảng đầy đủ 13 cột

> 🔴 **Ví dụ này KHÔNG phải profile nên dùng cho site thật.** `P_BOM_CUA_DI` cố ý khai thêm
> **Vật liệu & chi phí** (`cost_bucket`, rule 1–2) và **Biến dòng hiện tại** (`row_literal`,
> rule 8) để minh hoạ cơ chế lọc. Hai nhóm này **không có giá trị lúc công thức dòng BOM chạy**:
> biến vẫn hiện trong gợi ý, lưu được, nhưng **tính ra 0 và không báo lỗi**. Profile mẫu đúng để
> dùng là `P_BOM_DEFAULT` (mục 0.2) — 6 nhóm, không có 3 nhóm này.
>
> Nếu tự tạo profile cho `AL Bom Set`: ⛔ **đừng thêm** `cost_bucket`, `row_literal` trần,
> `cost_template_line`. Cần vật liệu/chi phí ⇒ dùng ở `AL Cost Template`; cần giá trị dòng ⇒
> `items.<slug>.<field>`.

Form profile → bảng **Luật lọc biến** (`rules`) → thêm 12 dòng dưới đây.
Cột `#` chỉ để dẫn chiếu, ⛔ không phải field.

| # | action | source_kind | source_ref | name_prefix | name_regex | category_tag | var_type | source_type | group_label | sort_order | only_fields | require_value | is_active |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Include | `cost_bucket` | `*` | `VL_` | — | — | — | — | `01 · Vật liệu` | 10 | — | 0 | 1 |
| 2 | Include | `cost_bucket` | `*` | `TONG_` | — | — | — | — | `01b · Tổng vật liệu` | 15 | — | 0 | 1 |
| 3 | Include | `variable_library_system` | `*` | — | — | `system` | — | — | `02 · Thông số hệ` | 20 | — | 0 | 1 |
| 4 | Include | `variable_set` | `AUTO` | — | — | — | — | — | `03 · Thông số nhập` | 30 | — | 0 | 1 |
| 5 | Include | `formula_global` | `VAT_RATE` | — | — | — | Float | — | `04 · Hằng số` | 40 | — | 1 | 1 |
| 6 | Include | `fvb_scope` | `AUTO` | — | — | — | — | — | `05 · Binding` | 50 | — | 0 | 1 |
| 7 | Include | `common_var` | `W_mm\|H_mm\|n_panel\|TONG_M2\|installation_height_m` | — | — | — | — | — | `06 · Thông số nhập` | 60 | — | 0 | 1 |
| 8 | Include | `row_literal` | `width\|height\|qty\|unit_price\|calc_pattern\|line_total` | — | — | — | — | — | `07 · Dòng hiện tại` | 70 | — | 0 | 1 |
| 9 | Include | `slug_reference` | `items` | — | — | — | — | — | `08 · Dòng khác` | 80 | — | 0 | 1 |
| 10 | Include | `cost_template_line` | `AUTO` | — | — | — | — | — | `09 · Dòng giá thành trước` | 90 | `["calc_formula"]` | 0 | 1 |
| 11 | Include | `variable_library_user` | `*` | — | — | — | — | — | `03b · Thư viện user` | 95 | — | 0 | **0** |
| 12 | Exclude | `variable_library_system` | `NC_PCT` | — | — | — | — | — | — | 0 | — | 0 | **0** |

### 3.1 Vì sao từng dòng

| # | Giải thích |
|---|---|
| 1 | Lấy **mọi** cost bucket đang bật có tên bắt đầu `VL_` ⇒ `VL_NHOM`, `VL_KINH`, `VL_PK`. `name_prefix` **phân biệt hoa thường**. |
| 2 | Cùng nguồn nhưng tiền tố `TONG_` ⇒ `TONG_VL`. Tách nhóm để nó đứng riêng, không lẫn với 3 bucket vật liệu. |
| 3 | Lấy biến thư viện hệ thống có `category = system` ⇒ `OFFSET_FRAME`, `NC_PCT`. `source_ref = *` nghĩa là mọi bản ghi của nguồn, rồi `category_tag` lọc tiếp. |
| 4 | `AUTO` = bộ biến của **chính bản ghi** (`AL Bom Set.variable_set`). Chữ `AUTO` phải **viết HOA**. |
| 5 | Chỉ hằng số `VAT_RATE`; `var_type = Float` là điều kiện khớp **chính xác**. `require_value = 1` ⇒ nếu hằng số rỗng thì biến bị loại hẳn (với `VAT_RATE` có `constant_value` nên vẫn hiện). |
| 6 | `AUTO` = mọi Formula Variable Binding áp cho ngữ cảnh (doctype cha + doctype dòng con). Site chưa có binding ⇒ nhóm này rỗng, ⛔ không phải lỗi. |
| 7 | Danh sách common var hiện cho profile này. ⛔ **Đừng dùng `var_name in [...]`** — đó là cú pháp tài liệu cũ, field này chỉ nhận danh sách ngăn `\|`. |
| 8 | Các row literal engine nạp theo dòng. Xem cảnh báo ở mục 5 về `width`/`height`/`qty`. |
| 9 | `slug_reference` **không sinh biến** — nó bật/tắt phần `references` (gợi ý `items.<slug>.<field>`). `source_ref` phải là **tên bảng con thật** (`items`), ⛔ không dùng `*`. |
| 10 | Dòng `line_code` đứng **trước** dòng đang sửa. `only_fields` giới hạn: chỉ hiện khi sửa `calc_formula`. Ở ngữ cảnh `AL Bom Set` nguồn này trả rỗng vì Bom Set không có Link tới Cost Template. |
| 11 | **Đang tắt.** Bật lên sẽ kéo **toàn bộ** biến user của Library vào, gây trùng tên với rule 4 và rule 7. Để đây làm ví dụ “đừng bật”. |
| 12 | **Đang tắt.** Bật lên thì `NC_PCT` biến mất: **Exclude luôn thắng Include** (rule 3 vẫn khớp, nhưng bị loại trước). |

### 3.2 Bốn chỗ dễ sai

1. **`source_kind` sai ⇒ rule không khớp gì, biến biến mất im lặng.** Không có cảnh báo đỏ.
2. **`source_ref` của `fvb_scope` là TÊN BIẾN**, ⛔ không phải tên doctype. Muốn lọc theo loại
   nguồn thì dùng `source_type` (ví dụ `custom_function`).
3. **`only_fields` phải là JSON list**: `["qty","width"]`. Chuỗi rỗng hoặc `[]` = **không giới
   hạn**, ⛔ không phải “ẩn hết”. Gõ sai JSON ⇒ **chặn lưu** và báo đúng số dòng rule.
4. **Không có field `bucket_role` trong rule**, cũng không có cú pháp `var_name in [...]`.
   Chỉ dùng đúng 13 cột ở bảng trên.

### 3.3 Thứ tự áp dụng (cố định, ⛔ không theo thứ tự bạn nhập)

```
1. Rule Exclude khớp              → loại
2. EXCLUDE_ALL và không khớp Include → loại
3. Include khớp                   → gắn group_label + sort_order
4. only_fields (server lọc khi có fieldname; autocomplete để client lọc)
5. require_value                  → loại nếu biến rỗng
6. Dedup trùng tên                → giữ một nguồn, phần bỏ ghi vào meta.duplicates
```

---

## 4. Biến chéo dòng (`cross_row`)

Form profile → bảng **Biến chéo dòng (slug)** → 1 dòng.

| table_field | id_field | label_field | fields | include_index_form | enabled |
|---|---|---|---|---|---|
| `items` | `slug` | `line_name` | `["width","height","qty","unit_qty","unit_price","total_qty","line_total","glass_thick","glass_type"]` | 1 | 1 |

### 4.1 Field nào engine **thật sự** inject

| Field trong `cross_row.fields` | Engine tạo ở đâu | Runtime có giá trị | Validate `AL Bom Set` nhận |
|---|---|---|---|
| `width`, `height`, `qty` | B3 dựng `{slug}__<field>` từ field công thức của `AL Bom Item` | ✅ | ✅ `FORMULA_FIELDS` |
| `unit_qty` | B3 synthetic `{slug}__unit_qty` (kết quả `lookup_calc_pattern`) | ✅ | ✅ `ENGINE_SYNTHETIC_FIELDS` |
| `total_qty` | B3 synthetic `{slug}__total_qty` | ✅ | ✅ `ENGINE_SYNTHETIC_FIELDS` |
| `line_total` | B3 synthetic `{slug}__line_total` | ✅ | ✅ `ENGINE_SYNTHETIC_FIELDS` |
| `unit_price` | B2/B3 row literal (Item Price của `item_code`/`price_base_item`; phụ kiện có thể ghi đè giá) | ✅ | ✅ row literal đang bật |
| `glass_thick`, `glass_type` | B2 lấy từ `AL Glass Master` → row literal | ✅ | ✅ row literal đang bật |

> ⚠ `unit_qty` **không phải lúc nào cũng là m²**: đơn vị do `calc_pattern` quyết định (kính = m²,
> nhôm = m). Đừng nhân `unit_qty` với đơn giá m² mà chưa kiểm `calc_pattern` của dòng.

> ✅ **Vì sao bảng trên có cột “Validate nhận”:** từ bản vá 2026-11-13, `AL Bom Set` kiểm
> `items.<slug>.<field>` bằng **superset**: `FORMULA_FIELDS` (`width/height/qty/show_condition`)
> + `ENGINE_SYNTHETIC_FIELDS` (`unit_qty/total_qty/line_total`) + **row literal đang bật** trong
> `AL Variable Settings` (`unit_price`, `glass_thick`, `glass_type`, `scrap_pct`, `calc_pattern`,
> `weight_per_unit`…). Nhờ vậy `items.kinh_tren.unit_price` lưu được, không còn bị chặn oan.
> Superset chỉ nới **validate** — field engine không nạp vẫn ra **0** lúc chạy, nên ⛔ vẫn không
> khai bừa vào `cross_row.fields`.

> ⛔ **Không khai** `qty_formula` (chỉ có ở `AL Accessory Set`, và là **chuỗi công thức**, engine
> không tạo `{slug}__qty_formula`), `show_condition` (là điều kiện, không phải số),
> `item_code` (chuỗi, không dùng trong số học).

### 4.2 Ba luật của cross-row

- `id_field` mặc định `slug`. Đổi sang `custom_slug`/`line_ref` chỉ khi bảng con thật sự dùng field đó.
- `label_field = line_name`: nhãn gợi ý đọc được (`Chiều rộng — kính trên`). Thiếu `line_name`,
  hệ thống tự dò `item_code`; không có nữa thì nhãn chỉ còn slug.
- `fields` để trống = **mọi field vô hướng** — dễ gợi ý field engine không nạp. Luôn khai tường minh.

---

## 5. `AL Variable Settings` — common var, row literal, preview

### 5.1 Common Variables (8 dòng seed)

Patch đã seed 8 dòng: `W_mm`, `H_mm`, `n_panel`, `TransomHeight_mm`, `SideLiteWidth`,
`SideLiteHeight`, `installation_height_m`, `TONG_M2` — nhóm `BOM Input Variables`.
Ví dụ này dùng 5 trong số đó; 3 dòng còn lại cứ để nguyên.

### 5.2 Row Literals — 10 dòng seed + 3 dòng thêm cho ví dụ

| var_name | var_label | var_type | group_label | sort | Có sẵn sau patch? |
|---|---|---|---|---|---|
| `unit_price` | Đơn giá | Float | Row Literals | 20 | ✅ |
| `calc_pattern` | Pattern | Data | Row Literals | 90 | ✅ |
| `line_total` | Thành tiền | Float | Row Literals | 50 | ✅ |
| `width` | Chiều rộng | Float | Row Literals | 110 | ⛔ **không** — thêm tay cho ví dụ |
| `height` | Chiều cao | Float | Row Literals | 120 | ⛔ **không** |
| `qty` | Số lượng | Float | Row Literals | 130 | ⛔ **không** |

> 🔴 **Cảnh báo thật về 3 dòng thêm tay.** Với `AL Bom Item`, `width/height/qty` là **field chứa
> chuỗi công thức** (`Small Text`), không phải số. Nếu khai chúng làm row literal:
> - catalog sẽ gợi ý tên **trần** `width` — dễ bị dùng nhầm (runtime tên trần ⛔ không tồn tại,
>   engine chỉ có `{slug}__width` ⇒ công thức ra **0**);
> - cột **Giá trị** ở preview lấy từ field cùng tên trên dòng/chứng từ nên thường là `—` hoặc
>   chính chuỗi công thức.
>
> Cách đúng cho 3 field này là **`items.<slug>.width`** (mục 4), ⛔ không phải row literal.
> **Chọn một trong hai, đừng lửng lơ:**
> - Muốn ví dụ hiện đủ 6 tên như rule 8 ⇒ thêm 3 dòng, chấp nhận bẫy trên và đọc kỹ cột Giá trị.
> - Làm cho site thật ⇒ **bỏ 3 dòng khỏi Settings và bỏ 3 tên khỏi `source_ref` của rule 8**
>   (chỉ giữ `unit_price|calc_pattern|line_total`).

### 5.3 Hai field còn lại

| Field | Giá trị ví dụ | Tác dụng |
|---|---|---|
| `preview_doctype` | `AL Bom Set` | DocType mặc định khi bấm **Xem trước danh sách biến** |
| `default_profile` | **để trống** | Patch v28_14 cố ý không set. Chỉ áp cho doctype **đã khai field Link** tới `AL Variable Profile`; doctype khác ⛔ không nhận |

> ⚠ `AL Variable Settings` là **Single**. Sửa bằng form; ⛔ đừng `insert` một document đầy đủ lên
> Single đang có dữ liệu — sẽ ghi đè cấu hình admin đã sửa.

---

## 6. `AL Formula Field` — đăng ký field công thức

Bảng dưới là 8 dòng cho ví dụ (patch seed đã tạo sẵn đúng các dòng này):

| target_doctype | child_table | fieldname | id_field | editor_opts | sort_order | is_active |
|---|---|---|---|---|---|---|
| `AL Bom Set` | `items` | `width` | `slug` | `{"height":"70px"}` | 10 | 1 |
| `AL Bom Set` | `items` | `height` | `slug` | `{"height":"70px"}` | 20 | 1 |
| `AL Bom Set` | `items` | `qty` | `slug` | `{"height":"70px"}` | 30 | 1 |
| `AL Bom Set` | `items` | `show_condition` | `slug` | `{"height":"70px"}` | 40 | 1 |
| `AL Bom Set` | `items` | `item_condition_formula` | `slug` | `{"height":"70px"}` | 50 | 1 |
| `AL Bom Set` | `items` | `rule_input_expr` | `slug` | `{"height":"70px"}` | 60 | 1 |
| `AL Accessory Set` | `items` | `qty_formula` | `slug` | `{"height":"70px"}` | 10 | 1 |
| `AL Cost Template` | `items` | `calc_formula` | *(trống)* | `{"height":"80px","float_popup":true}` | 10 | 1 |

Patch còn 3 dòng cấp cha (đủ 11): `AL Alert Config.trigger_condition`,
`AL Quantity Calc Method.calc_fn`, `Formula Global Variable.formula_expr` — `child_table` để **trống**.

### 6.1 Ba điều bắt buộc đúng

1. `child_table` là **tên field bảng** (`items`), ⛔ không phải tên doctype con (`AL Bom Item`).
   Field cấp cha ⇒ để trống.
2. `target_doctype` là fieldname thật trong DB (nhãn form: **Doctype**). ⛔ Không đặt tên field là
   `doctype` — Frappe coi là từ khoá dành riêng, migrate sẽ từ chối.
3. Bộ `(target_doctype, child_table, fieldname)` phải **duy nhất**; controller chặn lưu nếu trùng.

> Tối thiểu để ví dụ chạy được chỉ cần **2** dòng: `AL Bom Set/items/width` và
> `AL Cost Template/items/calc_formula`. Các dòng còn lại làm ví dụ đầy đủ.

---

## 7. Gán profile cho bản ghi mẹ

Mở `AL Bom Set` `BS-CUA-DI-01`:

| Field | Giá trị |
|---|---|
| `set_code` | `BS-CUA-DI-01` |
| `set_name` | Cửa đi nhôm kính 2 cánh |
| `variable_set` | `VS_CUA_DI_01` |
| `variable_profile` | `P_BOM_CUA_DI` |
| `items` | 4 dòng theo slug ở mục 1.1 |

> `variable_set` **phải có** thì rule 4 (`variable_set` + `AUTO`) mới thấy biến user. `AUTO` dò
> theo thứ tự: field Link trực tiếp tới `AL Variable Set` → field Link tới `AL Bom Set` →
> `product_type`. Với `AL Bom Set`, field `variable_set` rơi đúng bước 1.

### Con tự kế thừa — ⛔ không khai gì trên `AL Bom Item`

Catalog nhận `doctype` + `docname` + `child_table` + `row_index` rồi **tự đọc profile của cha**.
Bảng con ⛔ không có field `variable_profile`; thêm vào cũng ⛔ không được đọc.

Thứ tự chọn profile trên server:

```
1. tham số `profile` truyền tường minh (preview/API)
2. field `variable_profile` trên bản ghi
3. AL Variable Settings.default_profile (chỉ doctype có field Link)
4. không có → đường legacy
```

> Nếu `BS-CUA-DI-01` chưa gán profile, hệ thống vẫn gợi ý chéo dòng theo **hành vi cũ** (mọi bảng
> con, mọi field vô hướng) — nhưng ⛔ không có bộ lọc `cross_row.fields`. Đây là lý do phải gán.

---

## 8. Bấm **Xem trước danh sách biến**

1. Mở profile **đã lưu** (nút chỉ hiện khi record không phải new).
2. **Công cụ → Xem trước danh sách biến**.
3. Nhập:

| Ô | Giá trị ví dụ |
|---|---|
| DocType cần xem trước | `AL Bom Set` (mặc định lấy từ `AL Variable Settings.preview_doctype`) |
| Bản ghi | `BS-CUA-DI-01` |
| Bảng con | `items` |
| Field đang sửa | `width` |

4. Bấm **Xem trước**. Dialog hiện: `Profile: P_BOM_CUA_DI — BOM cửa đi 2 cánh · DocType: AL Bom Set ·
   Bảng con: items · Field: width` và `Tổng: 18 · Bị luật loại: 6` (số minh hoạ).

### 8.1 Bảng kết quả mẫu (đọc theo 6 cột của dialog)

| Nhóm | Tên biến | Nhãn | Kiểu | Giá trị | Nguồn |
|---|---|---|---|---|---|
| 01 · Vật liệu | `VL_NHOM` | VL_NHOM — Vật liệu nhôm | Float | — | AL Cost Bucket |
| 01 · Vật liệu | `VL_KINH` | VL_KINH — Vật liệu kính | Float | — | AL Cost Bucket |
| 01 · Vật liệu | `VL_PK` | VL_PK — Phụ kiện | Float | — | AL Cost Bucket |
| 01b · Tổng vật liệu | `TONG_VL` | TONG_VL — Tổng vật liệu | Float | — | AL Cost Bucket |
| 02 · Thông số hệ | `OFFSET_FRAME` | OFFSET_FRAME — Khe hở khung (mm) | Float | 10 | AL Variable Library |
| 02 · Thông số hệ | `NC_PCT` | NC_PCT — % nhân công | Float | 5 | AL Variable Library |
| 03 · Thông số nhập | `W_mm` | W_mm — Chiều rộng (mm) | Float | — | AL Variable Set VS_CUA_DI_01 |
| 03 · Thông số nhập | `H_mm` | H_mm — Chiều cao (mm) | Float | — | AL Variable Set VS_CUA_DI_01 |
| 03 · Thông số nhập | `TONG_M2` | TONG_M2 — Tổng diện tích (m²) | Float | — | AL Variable Set VS_CUA_DI_01 |
| 04 · Hằng số | `VAT_RATE` | VAT_RATE — Thuế GTGT | Float | 0.08 | Formula Global Variable |
| 06 · Thông số nhập | `n_panel` | n_panel — Số cánh | Int | — | AL Variable Settings · Common Variables |
| 06 · Thông số nhập | `installation_height_m` | installation_height_m — Cao lắp đặt (m) | Float | — | AL Variable Settings · Common Variables |
| 07 · Dòng hiện tại | `unit_price` | unit_price — Đơn giá | Float | — | AL Bom Set (chứng từ hiện tại) |
| 07 · Dòng hiện tại | `calc_pattern` | calc_pattern — Pattern | Data | — | AL Bom Set (chứng từ hiện tại) |
| 07 · Dòng hiện tại | `line_total` | line_total — Thành tiền | Float | — | AL Bom Set (chứng từ hiện tại) |
| 07 · Dòng hiện tại | `width` | width — Chiều rộng | Float | — | AL Bom Set (chứng từ hiện tại) |
| 07 · Dòng hiện tại | `height` | height — Chiều cao | Float | — | AL Bom Set (chứng từ hiện tại) |
| 07 · Dòng hiện tại | `qty` | qty — Số lượng | Float | — | AL Bom Set (chứng từ hiện tại) |

Nhóm **05 · Binding** không có dòng nào (site chưa có `Formula Variable Binding` cho 2 doctype này).

> ⚠ **Vì sao nhiều `—`:** `—` = **chưa resolve được giá trị tại form**, ⛔ không phải lỗi.
> Bucket chỉ có giá trị sau B4–B5; dòng giá thành chỉ có sau B6; biến người dùng nhập chưa có
> nguồn resolve ở tầng catalog. Đọc cột **Nguồn** để biết giá trị đến từ đâu.

> ⚠ **Dialog xem trước không có ô `row_index`.** Hệ quả đã biết:
> - row literal đọc field cùng tên trên **chứng từ** (không phải dòng) ⇒ thường `—`;
> - `cost_template_line` **không lọc dòng trước** ⇒ có thể thấy cả dòng **sau**.
> Autocomplete dạng bulk cũng rơi vào cùng giới hạn này. ⛔ Đừng tham chiếu dòng sau chỉ vì
> “thấy nó trong danh sách”.

### 8.2 Cảnh báo trùng tên (khung cam)

Dialog hiện khung cam khi một tên biến đến từ nhiều nguồn:

```
W_mm    — giữ: variable_set:VS_CUA_DI_01 ; bỏ: common_var:W_mm
H_mm    — giữ: variable_set:VS_CUA_DI_01 ; bỏ: common_var:H_mm
TONG_M2 — giữ: variable_set:VS_CUA_DI_01 ; bỏ: common_var:TONG_M2
```

Cách đọc: catalog **chỉ giữ một nguồn cho mỗi tên**; các nguồn còn lại bị loại và được ghi vào
`meta.duplicates`. Đây ⛔ **không phải lỗi**, và ⛔ không ảnh hưởng giá trị tính toán.
`W_mm` trùng vì nó vừa nằm trong `AL Variable Settings.common_variables` (rule 7) vừa nằm trong
`VS_CUA_DI_01` (rule 4). Muốn hết trùng: bỏ 3 tên khỏi một trong hai nơi.

Nguồn thắng theo thứ tự: **có giá trị** → `sort_order` nhỏ hơn → adapter đăng ký trước → xuất hiện trước.

### 8.3 Xem trước lần hai — trên `AL Cost Template`

Đổi ô DocType thành `AL Cost Template`, Bản ghi `CT_CUA_DI_01`, Bảng con `items`,
Field `calc_formula`. Lần này thấy thêm nhóm `09 · Dòng giá thành trước` và cảnh báo:

```
TONG_VL — giữ: cost_bucket:TONG_VL ; bỏ: cost_template_line:TONG_VL
```

`TONG_VL` vừa là bucket (AGGREGATE) vừa là `line_code` của template — trùng tên là bình thường.
Nếu nguồn thắng không phải nguồn bạn muốn, chỉnh `sort_order` của rule hoặc dùng
`explain_variable` (xem [api-reference.md](api-reference.md) mục 6).

---

## 9. Gõ thử ở 4 field khác nhau

Bảng “gõ gì → thấy gì → vì sao”. Tên biến lấy từ profile ở mục 3.

| # | Field đang sửa | Gõ | Thấy (ví dụ) | Vì sao |
|---|---|---|---|---|
| 1 | `AL Bom Item.width` (dòng `kinh_tren`) | `W_` | `W_mm` | biến user của Variable Set (rule 4); `name_prefix` không chặn vì gõ tay tự lọc theo tiền tố |
| 2 | `AL Bom Item.qty` (dòng `kinh_tren`) | `items.` | `items.kinh_tren.width`, `items.kinh_tren.height`, `items.kinh_tren.unit_price`, `items.kinh_tren.total_qty`… và dạng `items[0].width`… | `cross_row` mục 4 + rule 9 (`slug_reference items`); `include_index_form=1` sinh thêm dạng chỉ số — **chỉ để tra, ⛔ đừng chèn dạng chỉ số** (xem 9.1) |
| 3 | `AL Bom Item.show_condition` | `VL_` | `VL_NHOM`, `VL_KINH`, `VL_PK` | rule 1 (`cost_bucket` + `name_prefix VL_`). Danh sách **không phán** biến có hợp lý với field — đó là việc của người viết công thức |
| 4 | `AL Cost Template.calc_formula` (xem qua **Xem trước**, mục 8.3) | `TONG_` | `TONG_VL` (bucket), `TONG_VL`, `TONG_VL_PK` (dòng template) | rule 2 + rule 10. Rule 10 có `only_fields=["calc_formula"]` nên các `line_code` **chỉ** hiện ở field này |

### 9.1 Điều bảng này KHÔNG hứa

- Autocomplete **chỉ gợi ý**, ⛔ không chặn gõ tay. Người dùng vẫn gõ được biến ngoài danh sách.
- ⛔ **`items[n].<field>` không chạy được.** Đây là dạng gợi ý do `include_index_form` sinh thêm;
  runtime `inputs["items"]` là **dict khoá theo slug**, còn `_normalize_items_ref` chỉ đổi dạng
  `items.<slug>.<field>`. Luôn dùng `items.<slug>.<field>`.
- Biến hiện trong danh sách ⛔ **không** bảo đảm có giá trị lúc tính. `—` là chuyện bình thường.
- Với field `calc_formula`, profile **chưa được gán** cho `CT_CUA_DI_01` trong ví dụ này. Muốn
  autocomplete trên form thật dùng profile, gán `variable_profile` cho template — nhưng đọc cảnh
  báo ở mục 10.3 trước.

---

## 10. `only_fields` — mỗi field một danh sách riêng

### 10.1 Điều kiện để **tách được** biến

Tách bằng cách chia biến giữa các rule, ⛔ **không** bằng cách đặt `only_fields` khác nhau trên
cùng một tập biến:

1. Mỗi biến phải do **đúng một** rule Include chọn — các `source_ref` **không chồng nhau**.
2. Rule đó phải khai `only_fields`; nếu để trống thì biến **không giới hạn**.
3. Không được có rule nào khác (không giới hạn) cùng khớp biến đó — vì `only_fields` của nhiều
   rule khớp nhau được lấy **hợp**.

### 10.2 Ví dụ tách thay cho rule 8

| # | action | source_kind | source_ref | only_fields | group_label | sort_order |
|---|---|---|---|---|---|---|
| 8a | Include | `row_literal` | `width\|height` | `["width","height"]` | `07a · Kích thước` | 70 |
| 8b | Include | `row_literal` | `qty\|unit_price\|calc_pattern\|line_total` | `["qty","unit_price","calc_pattern","line_total"]` | `07b · Số lượng & giá` | 71 |

Kết quả:

- Sửa `width`/`height` ⇒ chỉ thấy `width`, `height`.
- Sửa `qty` ⇒ chỉ thấy `qty`, `unit_price`, `calc_pattern`, `line_total`.
- Biến không rule nào chọn ⇒ **không hiện** (`EXCLUDE_ALL`).

> Autocomplete: server gắn `only_fields` lên từng biến, **client lọc** theo field đang sửa
> (`_fieldExcluded`). API có `fieldname` (validate, preview): **server lọc rule** ngay.

### 10.3 Hai cảnh báo

- ⛔ **Đừng đặt 2 rule đều `source_ref = *`** với `only_fields` khác nhau. Cả hai cùng khớp mọi
  biến ⇒ kết quả là **hợp** ⇒ không tách được gì.
- Nếu dùng lại `P_BOM_CUA_DI` cho `AL Cost Template`, rule 8 (không `only_fields`) sẽ gợi ý
  `width`, `unit_price` trong `calc_formula` — B6 ⛔ không có các biến này. Tắt rule 8 khi dùng
  cho Cost Template, hoặc tạo profile riêng.

> `hide_all` (server gắn khi giao phạm vi nguồn × rule **rỗng**) ⛔ **không phải** field cấu hình.
> Nếu “biến không hiện ở đâu cả”, đọc `hide_all` trong kết quả API — đừng đi tìm field này trên form.

---

## 11. Lưu công thức — client validate khác server validate

### 11.1 Bảng đối chiếu

| Tầng | Chạy ở đâu | Kiểm gì | Không đạt thì |
|---|---|---|---|
| **Client — khi đang gõ** | `cost_template.js` → `validateRowSoon` (debounce 400 ms) | ngoặc cân bằng, ký tự hợp lệ, biến/hàm lạ so với **universe đầy đủ** (`include_all_sources=1`), `line_code` của các dòng trước | `show_alert` **đỏ** / cảnh báo **cam**; ⛔ **không chặn lưu** — chỉ phản hồi ngay |
| **Client — lúc bấm Lưu** | `al_cost_template.js` (JS của doctype) → `validate(frm)`, gọi `validate_formula` trong `public/js/cost_template.js` | chạy lại `validate_formula` cho **mọi dòng**; gom lỗi | `frappe.validated = false` + `msgprint` ⇒ **chặn lưu** |
| **Server — `AL Bom Set`** | `ALBomSet.validate` → `_validate_child_formulas` | `width`, `height`, `qty`, `show_condition` (+ `item_condition_formula` khi mode = Formula) | `frappe.throw` ⇒ **chặn lưu** |
| **Server — `AL Accessory Set`** | `ALAccessorySet.validate` | `qty_formula` | `frappe.throw` ⇒ **chặn lưu** |
| **Server — `AL Cost Template`** | `ALCostTemplate.validate` | thiếu công thức / ngoặc lệch ⇒ chặn; biến-hàm lạ ⇒ **chỉ `msgprint` cam** | vẫn **lưu được** ở tầng server (client đã chặn trước đó — trừ khi gọi API bỏ qua client) |

> 🔴 Vì sao validate dùng universe **đầy đủ**: `build_known_names()` luôn gọi
> `get_formula_context(..., include_all_sources=True)`. Profile chỉ lọc **gợi ý**; nếu thu hẹp cả
> universe thì bật profile = chặn oan công thức đang chạy.

### 11.2 Ba ca cụ thể

**Ca A — biến ngoài profile vẫn lưu được (đúng thiết kế).**

Đặt vào `AL Bom Item.width` của dòng `khung_doc_trai`:

```
items.kinh_tren.glass_thick + scrap_pct
```

- `glass_thick` và `scrap_pct` **không** có trong danh sách rule 8 của profile ⇒ autocomplete không gợi ý.
- Server `AL Bom Set` kiểm bằng universe đầy đủ (row literal đang bật + superset cross-row) ⇒ **lưu được**.
- Runtime: `kinh_tren__glass_thick` và `{slug}__scrap_pct` đều được engine nạp ⇒ có giá trị thật.

**Ca B — gõ sai thật thì bị chặn.**

```
items.khung_giua.width
```

- `khung_giua` không có trong `BS-CUA-DI-01` ⇒ `khung_giua__width` không nằm trong `known_names`.
- `AL Bom Set` **throw**: “Công thức không hợp lệ … Biến không khai báo”.
- Nếu bỏ qua được (ví dụ dữ liệu cũ), engine vẫn trả **0 âm thầm** — xem
  [troubleshooting.md](troubleshooting.md) mục 2.7.

**Ca C — cùng một lỗi, hai doctype xử khác nhau.**

Đặt vào `AL Cost Template.calc_formula` dòng `TONG_VL_PK`:

```
TONG_VL + VL_KINHH
```

- Đang gõ: client hiện cảnh báo **đỏ** “Biến không khai báo: VL_KINHH” (chưa chặn).
- Bấm **Lưu**: `validate(frm)` của client gom lỗi và đặt `frappe.validated = false` ⇒ **chặn lưu**.
- Server `AL Cost Template` (nếu tới được, ví dụ gọi API bỏ qua client) chỉ `msgprint` **cam** cho
  biến lạ ⇒ **vẫn lưu**; thiếu công thức/ngoặc lệch thì server mới `throw`.
- Runtime: tên lạ ⇒ engine `on_error=default`, `default_value=0` ⇒ `VL_KINHH` = 0 ⇒ **giá thiếu
  âm thầm**, không có exception.

> Vì tầng server ⛔ không chặn biến lạ, ⛔ đừng coi “gọi API lưu được” là “công thức đúng”. Luôn
> xem cảnh báo cam và chạy thử trước khi dùng.

### 11.3 `rule_input_expr` — chỉ cảnh báo, ⛔ không chặn

Field này **không** đi qua `FormulaValidator` (không phải biểu thức toán học); engine chỉ parse
regex `items.<slug>.<field>` rồi tra `row_literals`/`glass_data` của dòng đích. Vì vậy:
slug sai hoặc field không được nạp ⇒ **0 âm thầm**. `AL Bom Set` có cảnh báo cam khi lưu, nhưng
⛔ không throw (để không khoá dữ liệu cũ). Cảnh báo chỉ hiện với dòng có
`item_selection_mode = Rule`.

---

## 12. Runtime — catalog ⛔ không tham gia

### 12.1 Công thức trong đề bài: một công thức **trộn hai tầng**

```
items.kinh_tren.width * items.kinh_tren.height / 1000000 * VL_KINH
```

Nó trộn biến **theo dòng** (`items.*`, chỉ có ở B3–B4) với **cost bucket** (`VL_KINH`, chỉ có sau
B5). Bảng dưới là chỗ từng biến thật sự có mặt:

| Bước | Việc engine làm | `items.kinh_tren.width` | `VL_KINH` |
|---|---|---|---|
| B1 | Gom inputs: user nhập (`al_bom_vars`), hằng số (`VAT_RATE`), binding, biến thư viện | ❌ chưa có | ❌ chưa có |
| B2 | Prefetch master data + dựng **row literal** từng slug (`unit_price`, `glass_thick`, `calc_pattern`…) | ❌ chưa có | ❌ chưa có |
| B3 | Dựng formula từng dòng: `{slug}__width/height/qty` + synthetic `unit_qty`, `total_qty`, `line_total`; đổi `items.kinh_tren.width` → `kinh_tren__width` **trước khi** đưa vào engine | ✅ có (dạng `kinh_tren__width`) | ❌ chưa có |
| B4 | FormulaEngine chạy DAG + topo sort ⇒ ra số | ✅ `590` | ❌ **không có** ⇒ engine dùng default `0` |
| B5 | Gom `line_total` theo `cost_bucket` | (đã xong) | ✅ `1.813.542` |
| B6 | Cost template: `extra_context = inputs + buckets` | ❌ **không có** `items.*` (không normalize cross-row ở B6) | ✅ có |

**Kết luận (đọc từ mã, chưa chạy):** công thức này ⛔ **không chạy được ở đâu cả**.

- Đặt ở field dòng BOM (B4): `VL_KINH` chưa tồn tại ⇒ nhân với **0** ⇒ kết quả **0**.
- Đặt ở dòng cost template (B6): B6 **không** đổi `items.<slug>.<field>` thành `{slug}__<field>`
  (chỉ B3/B4 làm việc đó) ⇒ engine không resolve được vế `items.*` ⇒ **0**.

Ngoài ra phép nhân còn **sai thứ nguyên**: diện tích (m²) × tiền của cả bucket (đồng) không phải
một đại lượng có nghĩa. Đây là ví dụ tốt cho việc “catalog không cứu được công thức sai tầng”.

### 12.2 Cách viết đúng — tách 2 tầng

**Tầng B4** — tính diện tích một dòng kính, đặt vào `qty` của dòng cần nó (hoặc `rule_input_expr`):

```
items.kinh_tren.width * items.kinh_tren.height / 1000000
```

Giá trị minh hoạ: `590 × 2180 / 1000000 = 1,2862` m² (một tấm); dòng `kinh_tren` có
`qty = n_panel = 2` ⇒ `total_qty = 2,5724` m².

**Tầng B6** — dùng bucket đã là tiền, đặt vào `calc_formula`:

```
VL_KINH
```

Giá trị minh hoạ: `2,5724 × 705.000 = 1.813.542`.

### 12.3 Chuỗi giá trị minh hoạ đầy đủ

| Bước | Kết quả |
|---|---|
| B1 inputs | `W_mm=1200`, `H_mm=2200`, `n_panel=2`, `TONG_M2=5.28`, `installation_height_m=3`, `OFFSET_FRAME=10`, `VAT_RATE=0.08` |
| B2 row literal `kinh_tren` | `unit_price=705.000`, `calc_pattern=KINH_DIEN_TICH`, `glass_thick=8`, `glass_type=Temper` |
| B3 formula | `kinh_tren__width = (W_mm - 2*OFFSET_FRAME)/n_panel`, `kinh_tren__height = H_mm - 2*OFFSET_FRAME`, `kinh_tren__qty = n_panel`; synthetic `unit_qty`, `total_qty`, `line_total` |
| B4 | `width=590`, `height=2180`, `qty=2`, `unit_qty=1,2862`, `total_qty=2,5724`, `unit_price=705.000`, `line_total=1.813.542` |
| B5 buckets | `VL_NHOM=323.000`, `VL_KINH=1.813.542`, `VL_PK=240.000`, `TONG_VL` (AGGREGATE) không do B5 tính |
| B6 cost template | `TONG_VL = VL_NHOM + VL_KINH = 2.136.542`; `TONG_VL_PK = TONG_VL + VL_PK = 2.376.542`; `GIA_VAT = TONG_VL_PK * 1.08 = 2.566.665,36` |

> `TONG_M2 = 5.28` là **input** (diện tích phẳng của cả ô cửa: `1,2 × 2,2 × 2`), ⛔ không bằng
> diện tích kính thật `2,5724` m² — chênh vì đã trừ khe khung. Đừng dùng lẫn hai con số.

### 12.4 Catalog **không** tham gia

- `engine/bom_orchestrator.py` ⛔ không import `variable_catalog`, ⛔ không đọc `variable_profile`.
- Sửa/xoá profile, đổi rule, bỏ `cross_row` ⇒ **không đổi một đồng nào** trong kết quả tính.
- Công thức dùng biến ngoài profile vẫn chạy; công thức gõ sai vẫn ra 0 như cũ.
- Muốn đổi **giá trị**, phải sửa dữ liệu engine thật đọc: `AL Bom Item`, `AL Variable Settings`,
  `AL Cost Bucket`, `AL Cost Template`, Item Price…

Đây là ranh giới xuyên suốt của tính năng; xem thêm [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md).

---

## 13. Checklist sau khi setting (10 mục)

- [ ] **1. Migrate + build** đã chạy; Patch Log có `seed_variable_catalog` **và** `seed_bom_profile`.
- [ ] **2. Đủ 4 con số** ở mục 0.2 (3 profile · 8 common · 10 row literal · 11 formula field).
- [ ] **3. Dữ liệu nền đúng thứ tự**: Library trước Set, Bucket trước Template.
- [ ] **4. Profile** `EXCLUDE_ALL`, `is_active=1`; đã lưu không lỗi `only_fields`.
- [ ] **5. Rule**: mỗi `source_kind` có thật; `slug_reference.source_ref = items` (⛔ không `*`);
      `AUTO` viết HOA; ⛔ không dùng `bucket_role`/`var_name in [...]`.
- [ ] **6. `only_fields` là JSON list hợp lệ**; nhớ `[]` = không giới hạn.
- [ ] **7. `cross_row.fields`** chỉ gồm field engine thật sự inject; ⛔ không `qty_formula`.
- [ ] **8. Gán `variable_profile` trên bản ghi mẹ** (và `variable_set` nếu dùng rule `AUTO`).
- [ ] **9. Xem trước trên bản ghi thật**: đúng `child_table` + `fieldname`; đọc cả khung cảnh báo
      trùng tên.
- [ ] **10. Thử lưu** một công thức dùng biến **ngoài** profile ⇒ phải lưu được; thử một công thức
      sai ⇒ nhận cảnh báo/chặn đúng như mục 11.

### 13.1 Sáu lỗi thường gặp

| # | Hiện tượng | Đọc |
|---|---|---|
| 1 | Gõ vào field công thức mà danh sách trống | [troubleshooting.md](troubleshooting.md) 2.1 |
| 2 | Danh sách vẫn y như trước khi cài, quá nhiều biến | 2.2 (thường là chưa gán profile) |
| 3 | Sửa rule nhưng mở lại form vẫn danh sách cũ | 2.5 (cache client 5 phút) |
| 4 | `items.<slug>.<field>` lưu được nhưng tính ra 0 | 2.7 (field engine không nạp / slug sai) |
| 5 | Báo “Biến không khai báo” oan | 2.8 (validate phải dùng universe đầy đủ) |
| 6 | Nút Xem trước không có / báo thiếu quyền | 2.9 (cần read trên `AL Variable Profile`) |

> Còn 6 mục sự cố khác (cross-row, trùng tên, Formula Field không tác dụng, cache bản ghi thứ hai…)
> trong [troubleshooting.md](troubleshooting.md) mục 2.10–2.12.

---

## 14. Phụ lục — JSON mẫu đúng fieldname thật

> Dùng để **đối chiếu cấu hình**, ⛔ không phải lệnh nạp. `AL Variable Settings` là Single —
> sửa qua form, ⛔ đừng `insert` đè.

### 14.1 Profile

```json
{
  "doctype": "AL Variable Profile",
  "profile_code": "P_BOM_CUA_DI",
  "profile_name": "BOM cửa đi 2 cánh",
  "is_active": 1,
  "default_action": "EXCLUDE_ALL",
  "description": "Bộ biến cho BOM cửa đi nhôm kính 2 cánh (ví dụ minh hoạ)",
  "rules": [
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "cost_bucket", "source_ref": "*", "name_prefix": "VL_", "group_label": "01 · Vật liệu", "sort_order": 10, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "cost_bucket", "source_ref": "*", "name_prefix": "TONG_", "group_label": "01b · Tổng vật liệu", "sort_order": 15, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "variable_library_system", "source_ref": "*", "category_tag": "system", "group_label": "02 · Thông số hệ", "sort_order": 20, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "variable_set", "source_ref": "AUTO", "group_label": "03 · Thông số nhập", "sort_order": 30, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "formula_global", "source_ref": "VAT_RATE", "var_type": "Float", "group_label": "04 · Hằng số", "sort_order": 40, "require_value": 1, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "fvb_scope", "source_ref": "AUTO", "group_label": "05 · Binding", "sort_order": 50, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "common_var", "source_ref": "W_mm|H_mm|n_panel|TONG_M2|installation_height_m", "group_label": "06 · Thông số nhập", "sort_order": 60, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "row_literal", "source_ref": "width|height|qty|unit_price|calc_pattern|line_total", "group_label": "07 · Dòng hiện tại", "sort_order": 70, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "slug_reference", "source_ref": "items", "group_label": "08 · Dòng khác", "sort_order": 80, "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "cost_template_line", "source_ref": "AUTO", "group_label": "09 · Dòng giá thành trước", "sort_order": 90, "only_fields": "[\"calc_formula\"]", "require_value": 0, "is_active": 1},
    {"doctype": "AL Variable Profile Rule", "action": "Include", "source_kind": "variable_library_user", "source_ref": "*", "group_label": "03b · Thư viện user", "sort_order": 95, "require_value": 0, "is_active": 0},
    {"doctype": "AL Variable Profile Rule", "action": "Exclude", "source_kind": "variable_library_system", "source_ref": "NC_PCT", "sort_order": 0, "require_value": 0, "is_active": 0}
  ],
  "cross_row": [
    {"doctype": "AL Variable Cross Row", "table_field": "items", "id_field": "slug", "label_field": "line_name", "fields": "[\"width\",\"height\",\"qty\",\"unit_qty\",\"unit_price\",\"total_qty\",\"line_total\",\"glass_thick\",\"glass_type\"]", "include_index_form": 1, "enabled": 1}
  ]
}
```

### 14.2 Một dòng rule (tách riêng để đọc)

```json
{
  "doctype": "AL Variable Profile Rule",
  "action": "Include",
  "source_kind": "row_literal",
  "source_ref": "width|height",
  "name_prefix": null,
  "name_regex": null,
  "category_tag": null,
  "var_type": null,
  "source_type": null,
  "group_label": "07a · Kích thước",
  "sort_order": 70,
  "only_fields": "[\"width\",\"height\"]",
  "require_value": 0,
  "is_active": 1
}
```

### 14.3 Một dòng cross-row

```json
{
  "doctype": "AL Variable Cross Row",
  "table_field": "items",
  "id_field": "slug",
  "label_field": "line_name",
  "fields": "[\"width\",\"height\",\"qty\",\"unit_qty\",\"unit_price\",\"total_qty\",\"line_total\",\"glass_thick\",\"glass_type\"]",
  "include_index_form": 1,
  "enabled": 1
}
```

### 14.4 `AL Variable Settings` (Single — chỉ để đối chiếu)

```json
{
  "doctype": "AL Variable Settings",
  "default_profile": null,
  "preview_doctype": "AL Bom Set",
  "common_variables": [
    {"doctype": "AL Common Variable", "var_name": "W_mm", "var_label": "Chiều rộng (mm)", "var_type": "Float", "group_label": "BOM Input Variables", "sort_order": 10, "is_active": 1},
    {"doctype": "AL Common Variable", "var_name": "H_mm", "var_label": "Chiều cao (mm)", "var_type": "Float", "group_label": "BOM Input Variables", "sort_order": 20, "is_active": 1},
    {"doctype": "AL Common Variable", "var_name": "n_panel", "var_label": "Số cánh", "var_type": "Int", "group_label": "BOM Input Variables", "sort_order": 30, "is_active": 1},
    {"doctype": "AL Common Variable", "var_name": "TONG_M2", "var_label": "Tổng diện tích (m²)", "var_type": "Float", "group_label": "BOM Input Variables", "sort_order": 80, "is_active": 1},
    {"doctype": "AL Common Variable", "var_name": "installation_height_m", "var_label": "Cao lắp đặt (m)", "var_type": "Float", "group_label": "BOM Input Variables", "sort_order": 70, "is_active": 1}
  ],
  "row_literals": [
    {"doctype": "AL Row Literal", "var_name": "unit_price", "var_label": "Đơn giá", "var_type": "Float", "group_label": "Row Literals", "sort_order": 20, "is_active": 1},
    {"doctype": "AL Row Literal", "var_name": "calc_pattern", "var_label": "Pattern", "var_type": "Data", "group_label": "Row Literals", "sort_order": 90, "is_active": 1},
    {"doctype": "AL Row Literal", "var_name": "line_total", "var_label": "Thành tiền", "var_type": "Float", "group_label": "Row Literals", "sort_order": 50, "is_active": 1},
    {"doctype": "AL Row Literal", "var_name": "width", "var_label": "Chiều rộng", "var_type": "Float", "group_label": "Row Literals", "sort_order": 110, "is_active": 1},
    {"doctype": "AL Row Literal", "var_name": "height", "var_label": "Chiều cao", "var_type": "Float", "group_label": "Row Literals", "sort_order": 120, "is_active": 1},
    {"doctype": "AL Row Literal", "var_name": "qty", "var_label": "Số lượng", "var_type": "Float", "group_label": "Row Literals", "sort_order": 130, "is_active": 1}
  ]
}
```

> 3 dòng `width`/`height`/`qty` ở đây là phần **thêm cho ví dụ** và đã được cảnh báo ở mục 5.2.
> Seed thật chỉ có 10 dòng, ⛔ không gồm 3 dòng này.

### 14.5 `AL Formula Field`

```json
{
  "doctype": "AL Formula Field",
  "target_doctype": "AL Bom Set",
  "child_table": "items",
  "fieldname": "width",
  "id_field": "slug",
  "editor_opts": "{\"height\": \"70px\"}",
  "sort_order": 10,
  "is_active": 1
}
```

Ba dòng cấp cha trong seed (để trống `child_table`, `id_field`):

```json
[
  {"doctype": "AL Formula Field", "target_doctype": "AL Alert Config", "child_table": "", "fieldname": "trigger_condition", "id_field": "", "editor_opts": "{\"height\": \"100px\"}", "sort_order": 10, "is_active": 1},
  {"doctype": "AL Formula Field", "target_doctype": "AL Quantity Calc Method", "child_table": "", "fieldname": "calc_fn", "id_field": "", "editor_opts": "{\"height\": \"80px\"}", "sort_order": 10, "is_active": 1},
  {"doctype": "AL Formula Field", "target_doctype": "Formula Global Variable", "child_table": "", "fieldname": "formula_expr", "id_field": "", "editor_opts": "{\"height\": \"80px\"}", "sort_order": 10, "is_active": 1}
]
```

---

## 15. Đọc tiếp

| Tài liệu | Dùng khi |
|---|---|
| [huong-dan-setting-bien.md](huong-dan-setting-bien.md) | Cần lý thuyết từng field, 11 `source_kind`, thứ tự áp luật |
| [troubleshooting.md](troubleshooting.md) | Ví dụ chạy không như mô tả — tra triệu chứng trước khi kết luận tài liệu sai |
| [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) | Đường đi từ gợi ý đến giá trị lúc tính |
| [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) | Tra từng DocType: setting ở đâu, lấy từ đâu, điều kiện gì, runtime B0–B7 |
| [api-reference.md](api-reference.md) | Gọi API, đọc shape trả về, `explain_variable` |
| [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) | Toàn bộ nguồn biến và kiến trúc (§3 nguồn, §5 gợi ý, §6 runtime) |
