# Hướng dẫn sử dụng tính năng mới v28_14 — AlumGlass

> **Phạm vi tài liệu**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `566cdc2` (2026-11-12) **+ bản vá validate cross-row chưa commit** (2026-11-13: `al_bom_item.py`, `al_bom_set.py`, `al_accessory_set.py`) |
> | Phạm vi | **Cách dùng** các tính năng v28_14: Variable Profile, Settings, Formula Field, xem trước, `explain_variable`, registry field động, biến chéo dòng |
> | Đối tượng | BOM Manager / admin cấu hình; người lập công thức; DEV bảo trì |
> | ⛔ Ngoài phạm vi | Cách engine tính ra tiền ([hướng dẫn tính giá](../huong-dan-tinh-gia-full-flow.md)) · shape API từng field ([api-reference.md](api-reference.md)) · luật chi tiết của từng rule ([huong-dan-setting-bien.md](huong-dan-setting-bien.md)) |
> | Ngày soạn | 2026-11-13 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa mở form trên site nào**. Toàn bộ mô tả
> UI/DB đọc từ mã của HEAD `566cdc2` + bản vá cross-row trong working tree. Test thuần đã chạy:
> `test_variable_catalog_rules.py` **41/41**, `test_bom_set_cross_row_known_fields.py` **7/7**,
> `test_accessory_cross_row_known_fields.py` **9/9**, `test_seed_bom_profile.py` **14/14**.
> Chưa quan sát trên màn hình thật, chưa đo bằng dữ liệu
> thật. Khi màn hình khác tài liệu, đối chiếu [troubleshooting.md](troubleshooting.md) trước khi kết
> luận tài liệu sai.

> 🔴 **Một câu phải nhớ:** Variable Profile **chỉ lọc danh sách gợi ý**. Nó ⛔ không đổi giá trị
> tính toán, ⛔ không chặn công thức cũ. Bật/tắt/sửa/xoá profile mà số tiền của BOM đổi ⇒ đó là
> **lỗi hồi quy**, báo DEV — ⛔ đừng "sửa" bằng cách nới rule.

---

## 1. Đọc một lượt

1. Có **3 chỗ cấu hình mới**: `AL Variable Profile` (bộ lọc), `AL Variable Settings` (danh sách
   biến dùng chung / biến dòng), `AL Formula Field` (sổ đăng ký field công thức).
2. Gán profile bằng field **Variable Profile** trên 4 doctype: `AL Bom Set`, `AL Cost Template`,
   `AL Accessory Set`, `AL Alert Config`. Để trống = chạy như trước v28_14.
3. Triển khai cần **`bench migrate` + `bench build --app alumglass`** (mục 6). Chưa chạy trên
   site nào — đừng coi tài liệu là bằng chứng đã chạy.

**Đọc nhanh:**

| Bạn cần | Mục |
|---|---|
| Gán profile cho một chứng từ | §4.1 |
| Tạo profile + rule lọc | §4.2 |
| Khai biến dùng chung / biến dòng | §4.3 |
| Đăng ký field công thức mới | §4.4 |
| Xem trước danh sách biến | §4.5 |
| Bật gợi ý `items.<slug>.<field>` | §4.7 |
| Người lập công thức sẽ thấy gì | §4.8 |
| 5 tình huống thực tế | §5 |
| Migrate / build / rollback | §6 |

---

## 2. Ai dùng, cần quyền gì

| Vai | Việc làm | Quyền cần có |
|---|---|---|
| **Người lập công thức** | Mở form, gõ công thức; nhận danh sách biến đã lọc theo profile của bản ghi | Quyền đọc/ghi chứng từ đang làm (như cũ) |
| **BOM Manager / admin** | Tạo/sửa profile, rule, cross-row; khai biến trong Settings; đăng ký field trong `AL Formula Field`; bấm **Xem trước danh sách biến** | `System Manager` (mặc định) — xem cảnh báo dưới |
| **DEV bảo trì** | Gọi API, đọc `meta`/`provenance`, thêm nguồn biến mới | Quyền đọc doctype nghiệp vụ |

> ⚠️ **Phân quyền mặc định, đọc kỹ:** `AL Variable Profile`, `AL Variable Settings`,
> `AL Formula Field` chỉ cấp cho **System Manager** (khai trong JSON DocType). Role
> **`AL BOM Manager` chưa có quyền** ghi 3 DocType này. Muốn giao cho BOM Manager ⇒ phải cấp
> quyền có chủ đích (Role Permission Manager), ⛔ đừng giả định đã có.
>
> - Nút **Xem trước danh sách biến** kiểm quyền **đọc** trên `AL Variable Profile`.
> - `explain_variable` kiểm quyền **đọc** trên chính doctype nghiệp vụ được hỏi.

---

## 3. Có gì mới

| # | Tính năng | Nằm ở đâu | Dùng để làm gì |
|---|---|---|---|
| 1 | `AL Variable Profile` | Desk → tìm `AL Variable Profile` | Một bộ biến cho một ngữ cảnh; chứa rule và cross-row |
| 2 | `AL Variable Profile Rule` (bảng con) | Trong form profile, mục **Luật lọc biến** | Include/Exclude theo nguồn, tiền tố, regex, kiểu, field đang sửa |
| 3 | `AL Variable Cross Row` (bảng con) | Trong form profile, mục **Biến chéo dòng (slug)** | Khai bảng con nào được gợi ý `items.<slug>.<field>` |
| 4 | `AL Variable Settings` (Single) | Desk → tìm `AL Variable Settings` | Hai danh sách biến từng viết cứng trong code: **Common Variables** và **Row Literals**; thêm `default_profile`, `preview_doctype` |
| 5 | `AL Formula Field` | Desk → tìm `AL Formula Field` | Sổ đăng ký "doctype nào có field công thức nào" — thay danh sách cứng trong JS |
| 6 | Field **Variable Profile** | 4 doctype nêu ở mục 1 | Gán profile cho từng bản ghi |
| 7 | Nút **Xem trước danh sách biến** | Form `AL Variable Profile` đã lưu → nhóm nút **Công cụ** | Admin thấy đúng danh sách biến một ngữ cảnh sẽ nhận, kèm nguồn và cảnh báo trùng tên |
| 8 | API `explain_variable` | Gọi API/console (chưa có nút trên form) | Trả lời "vì sao tôi thấy / không thấy biến này" |
| 9 | Registry field động (`get_formula_fields`) | Chạy ngầm khi mở form | Thêm field công thức = thêm 1 record, ⛔ không sửa JS, ⛔ không build lại asset |
| 10 | Autocomplete lọc theo profile | Trong ô công thức (Monaco) | Gõ `VL_`, `TONG_`… chỉ thấy biến đúng ngữ cảnh thay vì toàn bộ 9 nhóm cũ |
| 11 | Gợi ý biến chéo dòng | Trong ô công thức | Chèn `items.<slug>.<field>`; dạng `items[n].<field>` chỉ để tra, ⛔ không dùng trong công thức |

Chi tiết từng cột của rule và 11 nguồn biến: [huong-dan-setting-bien.md](huong-dan-setting-bien.md).
Thay đổi so với bản trước: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md).

---

## 4. Cách dùng từng tính năng

### 4.1 Gán profile cho một chứng từ

- **Mở ở đâu:** form `AL Bom Set` / `AL Cost Template` / `AL Accessory Set` / `AL Alert Config`.
- **Nhập gì:** field **Variable Profile** → chọn một `AL Variable Profile` đang bật.
- **Kết quả mong đợi:** lần mở form kế tiếp, danh sách biến trong ô công thức của bản ghi đó đi
  theo profile. Để trống ⇒ đường cũ (đầy đủ các nhóm), không mất biến nào. Context được cache
  **5 phút** ở client — vừa đổi profile mà chưa thấy khác thì F5.
- **Lỗi thường gặp:** chọn profile `is_active=0` ⇒ hệ thống coi như không có profile, rơi về
  đường cũ. Xem [troubleshooting.md](troubleshooting.md) mục 2.4.

> Đừng quên: `AL Variable Settings.default_profile` **chỉ áp cho doctype đã khai field Link**
> tới `AL Variable Profile` (đúng 4 doctype trên). Doctype khác không bị default profile đụng
> tới — đây là chủ ý, không phải lỗi.

> **Profile mẫu cho Bom Set — `P_BOM_DEFAULT`** (patch `seed_bom_profile` tự tạo và gán cho
> `AL Bom Set` đang trống): 6 rule / 5 tên nhóm — **Thông số hệ** · **Thông số nhập** (2 rule:
> Variable Set `AUTO` và Common var) · **Hằng số** · **Binding** (`AUTO`) · **Dòng khác**
> (`slug_reference items`) — và
> 1 dòng **Cross Row** cho `items` với 12 field (`width`, `height`, `qty`, `unit_qty`,
> `unit_price`, `total_qty`, `line_total`, `weight_per_unit`, `glass_thick`, `glass_type`,
> `calc_pattern`, `scrap_pct`).
>
> Profile này **cố ý không** gợi ý 3 nhóm: **Vật liệu & chi phí** (`cost_bucket`), **Biến dòng
> hiện tại** (`row_literal`) và **Dòng báo giá thành trước** (`cost_template_line`). Lý do người
> dùng thấy: lúc tính công thức dòng BOM, giá trị vật liệu/chuyên mục giá thành **chưa có**, còn
> `unit_price`… chỉ tồn tại ở dạng `items.<slug>.unit_price`. Nếu tự thêm 3 nhóm này, biến **vẫn
> hiện trong gợi ý và lưu được**, nhưng **tính ra 0 và không báo lỗi**. Cần vật liệu/chi phí thì
> dùng ở `AL Cost Template`; cần giá trị dòng thì dùng `items.<slug>.<field>`.
>
> Bộ Bom Set tạo **sau** migrate ⛔ **không tự nhận** profile — phải chọn tay ở field
> **Variable Profile**.

### 4.2 Tạo bộ lọc: profile + rule

- **Mở ở đâu:** Desk → `AL Variable Profile` → **New** (hoặc mở profile mẫu).
- **Nhập gì:**
  1. **Mã profile** (`profile_code`, cũng là tên record), **Tên profile** (`profile_name`),
     **Đang dùng** (`is_active`).
  2. **Chế độ mặc định** (`default_action`): `INCLUDE_ALL` (cho tất cả rồi trừ) hoặc `EXCLUDE_ALL`
     (chỉ cho đúng thứ được khai — khuyến nghị cho profile mới).
     > ⚠️ `INCLUDE_ALL` chỉ đúng nghĩa "tất cả" khi **không có rule Include nào**. Có **ít nhất 1**
     > rule Include ⇒ hệ thống **chỉ chạy các nguồn đó**, phần còn lại mất khỏi gợi ý. Muốn
     > "tất cả trừ vài nhóm" thì đừng thêm rule Include — chỉ dùng rule Exclude.
  3. Bảng **Luật lọc biến** → **Add Row**: **Hành động** (`action`), **Nguồn biến** (`source_kind`),
     **Tham chiếu nguồn** (`source_ref`), **Nhóm hiển thị** (`group_label`), **Thứ tự nhóm**
     (`sort_order`), và các điều kiện lọc thêm nếu cần.
- **Kết quả mong đợi:** biến khớp rule hiện trong autocomplete theo nhóm `group_label`; biến bị
  loại không hiện. Số bị loại được báo trong `meta.excluded_by_rules` (thấy ở nút xem trước).
- **Lỗi thường gặp:**
  - `only_fields` sai định dạng JSON ⇒ **chặn lưu** và báo đúng số dòng rule.
  - Rule `slug_reference` để `source_ref = *` **không chỉ định bảng** — nó rơi về hành vi cũ
    (mọi child table khi `INCLUDE_ALL`, không gợi ý nào khi `EXCLUDE_ALL`). Muốn chỉ định bảng:
    ghi **tên bảng con thật**, ví dụ `items`.
  - `name_prefix` **phân biệt hoa thường**.
  - Xem [troubleshooting.md](troubleshooting.md) mục 2.1, 2.2, 2.4.

### 4.3 Khai biến dùng chung / biến dòng trong `AL Variable Settings`

- **Mở ở đâu:** Desk → `AL Variable Settings` (Single).
- **Nhập gì:**
  - **Common Variables** (`common_variables`) — **chỉ đăng ký tên** cho danh mục gợi ý/validate.
    ⛔ Đây **không phải** nguồn của dialog "Tham số BOM": dialog dựng ô nhập từ
    `AL Variable Set.items` + system var của `AL Variable Library`
    (`get_variable_set_for_bom`). Muốn có ô nhập trong dialog ⇒ thêm biến vào **`AL Variable Set`**
    của BOM (dữ liệu), ⛔ không thêm ở đây.
  - **Row Literals** (`row_literals`) — **đăng ký tên** cho biến engine inject theo từng dòng BOM;
    ⛔ không tự tạo thêm giá trị (xem mục 5.2 và
    [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) §3.2).
  - Mỗi dòng: `var_name` (đúng tên engine dùng), `var_label`, `var_type`, `group_label`,
    `sort_order`, `is_active`, `description`.
  - `default_profile`, `preview_doctype`: chỉ phục vụ resolve profile và ô mặc định của hộp thoại
    xem trước.
- **Kết quả mong đợi:** các tên này trở thành **dữ liệu** — có mặt trong danh mục biến; riêng Row
  Literals còn có mặt trong `get_row_literal_names`, ⛔ không phải sửa Python/JS.
- **Lỗi thường gặp:** giá trị hiện `—` **chưa kết luận được** điều gì — đó là "chưa resolve được
  ở form", xảy ra cả với biến engine **có** inject (`unit_price`, `glass_thick`…) vì form không
  có số để hiển thị. Muốn biết engine có inject thật hay không: chạy tính giá rồi đọc
  `al_bom_result.lines[].trace`, hoặc gọi `explain_variable`. Settings chỉ đăng ký **tên**, ⛔
  không tạo giá trị. Xem [troubleshooting.md](troubleshooting.md) mục 2.3; đối chiếu
  [nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md).

### 4.4 Đăng ký field công thức mới trong `AL Formula Field`

- **Mở ở đâu:** Desk → `AL Formula Field` → **New**.
- **Nhập gì:**

  | Cột | Nhập gì |
  |---|---|
  | Doctype (`target_doctype` trong DB) | Doctype chứa field, ví dụ `AL Bom Set` |
  | Child table | Để trống nếu field ở cấp cha; nhập `items` nếu ở dòng con |
  | Fieldname | **Đúng** fieldname của field công thức |
  | ID field | Field định danh dòng, mặc định `slug` |
  | Editor Options | JSON, ví dụ `{"height":"70px","float_popup":true}` |
  | Thứ tự / Đang dùng | `sort_order`, `is_active` |

- **Kết quả mong đợi:** lần mở form kế tiếp (client cache 60 giây), field đó được gắn editor công
  thức + autocomplete. Không cần sửa JS, không cần build lại asset.
- **Lỗi thường gặp:**
  - `fieldname` gõ sai ⇒ record vẫn lưu hợp lệ nhưng **vô dụng** — hệ thống ⛔ không kiểm field
    có tồn tại. Xem [troubleshooting.md](troubleshooting.md) mục 2.10.
  - Chọn sai `child_table` ⇒ widget không gắn (bỏ qua, không báo lỗi).
  - API lỗi/thiếu bảng ⇒ **không** rơi về danh sách cứng (danh sách cứng đã bị dẹp) — field chỉ
    không có autocomplete nâng cao.

### 4.5 Xem trước danh sách biến

- **Mở ở đâu:** mở một `AL Variable Profile` **đã lưu** → nhóm nút **Công cụ** → **Xem trước danh
  sách biến**.
- **Nhập gì:** `DocType` cần xem (ô mặc định lấy từ `AL Variable Settings.preview_doctype`), tùy
  chọn: bản ghi, bảng con, field đang sửa.
- **Kết quả mong đợi:** bảng theo nhóm: Nhóm · Tên biến · Nhãn · Kiểu · Giá trị · Nguồn; phần đầu
  hiện tổng số và số bị luật loại; nếu có biến trùng tên, khung cảnh báo màu cam ghi rõ **giữ**
  nguồn nào, **bỏ** nguồn nào.
- **Lỗi thường gặp:** bảng trống ⇒ đọc ngay câu gợi ý trong hộp thoại (có/không có số bị loại
  nghĩa là hai nguyên nhân khác nhau). Lỗi quyền: [troubleshooting.md](troubleshooting.md) 2.9.

### 4.6 Giải thích vì sao thấy / không thấy một biến (`explain_variable`)

- **Mở ở đâu:** hiện **chưa có nút trên form**. Gọi qua console/bench hoặc API — cú pháp ở
  [api-reference.md](api-reference.md) mục 6 và mục 10.
- **Nhập gì:** tên biến + ngữ cảnh (`doctype`, tùy chọn `docname`, `child_table`, `row_index`,
  `fieldname`).
- **Kết quả mong đợi:** mọi nguồn có cùng tên biến, mỗi nguồn ghi `selected` (có qua rule không),
  `kept` (có thắng dedupe không), kèm `provenance` và giá trị. Đây là công cụ chẩn đoán **chỉ
  đọc**.
- **Lỗi thường gặp:** chạy **tất cả** adapter nên chậm hơn catalog thường — chỉ dùng khi cần hỏi
  "vì sao". Người gọi cần quyền đọc doctype nghiệp vụ.

### 4.7 Biến chéo dòng (Cross Row)

- **Mở ở đâu:** form profile → mục **Biến chéo dòng (slug)** → **Add Row**.
- **Nhập gì:** **Child table** (`table_field`, ví dụ `items`), **Field định danh dòng** (`id_field`,
  ví dụ `slug`), **Field nhãn dòng** (`label_field`, ví dụ `item_code`), **Danh sách field**
  (`fields`, JSON list), **Sinh thêm dạng items[n]** (`include_index_form`), **Đang dùng**
  (`enabled`).
- **Kết quả mong đợi:** autocomplete gợi ý `items.<slug>.<field>` và (nếu bật) `items[n].<field>`,
  nhãn đọc được thay vì chỉ slug.

> ⛔ **Chỉ dùng dạng slug `items.<slug>.<field>` trong công thức.** Dạng `items[n].<field>` do
> `include_index_form` sinh thêm chỉ để tra theo thứ tự hàng: runtime `inputs["items"]` là dict
> khoá theo slug và `_normalize_items_ref` không đổi được dạng chỉ số ⇒ gõ vào sẽ ra **0**.

**Field nào hợp lệ khi lưu `AL Bom Set`?** Validate cross-row của Bom Set nhận **superset** gồm
3 nguồn:

| Nguồn | Field |
|---|---|
| Field công thức tham gia DAG | `width`, `height`, `qty`, `show_condition` |
| Field engine **luôn** tạo cho mọi dòng | `unit_qty`, `total_qty`, `line_total` |
| Row literal đang bật trong `AL Variable Settings` | `unit_price`, `weight_per_unit`, `glass_thick`, `glass_type`, `scrap_pct`, `calc_pattern`, `max_area_m2`… (đúng danh sách đang bật, đọc từ dữ liệu — thêm/bớt dòng ở Settings là đổi danh sách này) |

> ⚠️ Superset này chỉ **nới `known_names` cho validate** — nó ⛔ không làm field lạ chạy được lúc
> runtime. Field không được engine inject vẫn ra **0**. Vì vậy: chỉ khai vào `cross_row.fields`
> những field engine **thật sự** tạo; đừng khai rồi trông vào validate để phát hiện sai.
> Ví dụ bộ phụ kiện: ⛔ đừng khai `qty_formula` (đó là **chuỗi công thức**, engine không inject).
> Chiều ngược lại cũng đúng: **tắt/xoá** một row literal đang được công thức dùng (ví dụ
> `glass_thick`) sẽ khiến công thức đó **bị chặn lưu** — xem [troubleshooting.md](troubleshooting.md)
> mục 2.8.

- **Lỗi thường gặp:** khai field mà engine **không** tạo `{slug}__<field>` ⇒ công thức chạy ra 0.
  Xem [troubleshooting.md](troubleshooting.md) mục 2.7 và "luật vàng" ở
  [huong-dan-setting-bien.md](huong-dan-setting-bien.md) mục 5.

### 4.8 Người lập công thức thấy gì trong autocomplete

- **Mở ở đâu:** mở chứng từ đã gán profile → bấm vào một field công thức (ví dụ dòng `items` →
  `calc_formula`).
- **Nhập gì:** gõ một tiền tố, ví dụ `VL_`, `TONG_`, `W_`, hoặc mở danh sách gợi ý.
- **Kết quả mong đợi:** chỉ biến thuộc profile của bản ghi, gom theo nhóm; tooltip có nguồn; biến
  chéo dòng hiện ở nhóm riêng.
- **Lỗi thường gặp:** vẫn thấy toàn bộ biến ⇒ bản ghi chưa gán profile, hoặc profile chưa bật,
  hoặc trình duyệt còn asset cũ (chưa `bench build`). Xem
  [troubleshooting.md](troubleshooting.md) mục 2.2 và 2.5.

---

## 5. Năm tình huống sử dụng thực tế

### 5.1 Giấu biến rác ở `AL Cost Template`

**Mục tiêu:** người làm giá thành không phải lọc bằng mắt giữa hàng chục biến không liên quan.

1. Mở `AL Variable Profile` → `P_COST_TEMPLATE_DEFAULT` (profile mẫu do patch tạo).
2. Profile này đã đặt `default_action = EXCLUDE_ALL` và 6 rule Include:
   Vật liệu & chi phí · Dòng tự định nghĩa · Thông số hệ · Hằng số · Binding · Thông số nhập.
3. Mở `AL Cost Template` → field **Variable Profile** phải trỏ profile này. Patch chỉ gán cho
   record **đang trống** lúc migrate; record tạo **sau** đó phải **chọn tay** (⛔ không tự chọn).
4. Bấm **Xem trước danh sách biến** → chọn `AL Cost Template` → đối chiếu danh sách.

**Kết quả mong đợi:** autocomplete của `calc_formula` chỉ còn các nhóm trên; **không** có row
literal và không có biến chéo dòng — vì B6 chỉ có `inputs ⊕ buckets`, gợi ý `{slug}__*` /
`items.*` sẽ dẫn tới công thức ra 0.

**Nếu vẫn còn rác:** thêm rule **Exclude** đúng nguồn + `name_prefix`/`name_regex` của phần rác,
rồi xem trước lại (client cache 5 phút — F5 nếu cần).

### 5.2 Đăng ký một biến dòng đã có đường inject

**Mục tiêu:** cho biến **đã được engine tạo** hiện trong gợi ý/validate mà không sửa code.
`AL Variable Settings.row_literals` chỉ đăng ký **tên**, ⛔ **không làm engine sinh thêm giá trị**.
Với **row literal**, engine chỉ inject: 6 literal cố định (`weight_per_unit`, `unit_price`,
`calc_pattern`, `glass_thick`, `glass_type`, `scrap_pct`) + các tên khai trong
`AL Quantity Calc Method.input_vars` (giá trị lấy từ `AL Bom Item.input_vars` → user input →
row literal → 0) + 3 biến synthetic (`unit_qty`, `total_qty`, `line_total`). Ngoài ra còn các field
công thức `{slug}__*` (mục 4.7) và `inputs["items"]` — đó là đường riêng, không phải row literal.

1. Mở `AL Variable Settings` → bảng **Row Literals** → **Add Row**.
2. Nhập `var_name` **đúng tên engine dùng**, nhãn, kiểu, nhóm, thứ tự, `is_active`.
3. Nếu profile là `EXCLUDE_ALL` — hoặc profile `INCLUDE_ALL` nhưng đã có rule Include (khi đó chỉ
   các nguồn được Include mới chạy): mở profile → thêm rule **Include** `source_kind = row_literal`,
   `source_ref = <tên biến>`, `group_label` phù hợp.
4. Lưu → mở lại form → gõ tên biến trong ô công thức.

**Kết quả mong đợi:** biến có trong danh sách gợi ý và trong `get_row_literal_names`.
**Nếu muốn một giá trị hoàn toàn mới:** khai tên vào `AL Quantity Calc Method.input_vars` của
pattern và cấp giá trị qua `AL Bom Item.input_vars` (dữ liệu); còn engine phải **tự tính** một
đại lượng mới thì phải sửa B2/B3 — ⛔ không có đường cấu hình cho việc đó.
**Dấu hiệu sai:** giá trị `—` **không đủ** để kết luận engine không inject (xem mục 4.3). Muốn
chắc: chạy tính giá và đọc `al_bom_result.lines[].trace`. Biến **không hiện** ⇒ kiểm rule Include
(nếu `EXCLUDE_ALL`) hoặc `is_active`.

### 5.3 Thêm một field công thức mới vào `AL Formula Field`

**Mục tiêu:** một field mới có editor công thức + autocomplete mà không sửa JS.

1. Field phải **đã tồn tại** trên doctype/bảng con (record này ⛔ không tạo field).
2. `AL Formula Field` → **New** → nhập Doctype, Child table, Fieldname, ID field, Editor Options.
3. Lưu → đóng và mở lại form (client cache 60 giây).
4. Kiểm: bấm vào field → phải mở editor công thức; gõ thử một tiền tố → có gợi ý.

**Kết quả mong đợi:** widget gắn đúng field, đúng chiều cao/kiểu popup đã khai trong
`editor_opts`.
**Dấu hiệu sai:** record đã lưu nhưng không có tác dụng ⇒ kiểm `fieldname` và `child_table` trước
tiên (hệ thống không kiểm field có tồn tại). Xem [troubleshooting.md](troubleshooting.md) mục 2.10.

### 5.4 Bật biến chéo dòng cho bộ phụ kiện

**Mục tiêu:** công thức của một dòng phụ kiện tham chiếu được dòng khác trong cùng bảng.

1. Mở `AL Variable Profile` → `P_ACCESSORY_DEFAULT`.
2. Mục **Biến chéo dòng (slug)** đã có một dòng mẫu: `table_field = items`,
   `id_field = slug`, `label_field = item_code`,
   `fields = ["qty","unit_price","calc_pattern","total_qty","line_total"]`,
   `include_index_form = 1`.
3. Mở `AL Accessory Set` → `Variable Profile` phải trỏ profile này.
4. Trong `qty_formula`, gõ `items.` → chọn dòng và field.

**Kết quả mong đợi:** gợi ý dạng `items.<slug>.qty` và `items[n].qty` (dạng chỉ số chỉ để tra —
công thức phải dùng dạng slug), nhãn lấy theo `item_code`.
Danh sách 5 field trên là **đúng** cho bộ phụ kiện — danh sách superset của `AL Bom Set` (mục 4.7)
⛔ không áp cho bộ phụ kiện. Từ bản vá 2026-11-13, validate của `AL Accessory Set` nhận cả
`unit_qty`, `total_qty`, `line_total` (engine sinh, không nằm trong meta) — trước đó Lưu bị chặn oan.
**Dấu hiệu sai:**
- Không có gợi ý ⇒ profile chưa gán, hoặc cross-row `enabled = 0`, hoặc `table_field` không phải
  field bảng con thật.
- Có gợi ý nhưng công thức ra 0 ⇒ field đó không được engine tạo `{slug}__<field>`. Danh sách
  `fields` ở trên đúng là các field engine thật sự tạo cho dòng phụ kiện; ⛔ đừng thêm
  `qty_formula`.

> **Bỏ `slug_reference` rồi mà vẫn thấy `items.`?** Kiểm ba thứ theo thứ tự:
> 1. **Chế độ mặc định** của profile còn `INCLUDE_ALL` — khi đó hệ thống gợi ý `items.*` cho **mọi**
>    bảng con dù không khai `slug_reference`. Đổi sang `EXCLUDE_ALL` mới tắt được.
> 2. **Bản ghi đang mở chưa resolve được profile** (record mới chưa lưu, field Variable Profile
>    trống và `default_profile` trống). Lúc đó autocomplete đi đường cũ và **luôn** thêm
>    `items.<slug>.{field}` từ `AL Slug Library` — không liên quan profile. Lưu bản ghi rồi gán
>    profile, hoặc đặt profile mặc định.
> 3. **Cache 5 phút** của form giữ danh sách cũ — reload trước khi kết luận.
>
> Chi tiết và cách đọc dấu hiệu (`profile: null` = đang ở đường cũ):
> [al-variable-profile.md](al-variable-profile.md) §7.2.1.

### 5.5 Giới hạn biến theo field đang sửa

**Mục tiêu:** field `width` chỉ thấy biến kích thước, field `qty` chỉ thấy biến số lượng.

- **Chỉ hiện ở field** (`only_fields`) là **cổng mức RULE**, không phải allowlist từng biến. Nó
  nhận JSON list fieldname; `[]` / để trống = **không giới hạn** (⛔ không phải "ẩn hết").
- Muốn **mỗi field một danh sách riêng** ⇒ **tách biến giữa các rule** bằng
  **Tham chiếu nguồn** (`source_ref`) / **Tiền tố tên** (`name_prefix`):

  | Rule | Nguồn biến (`source_kind`) | Tham chiếu nguồn (`source_ref`) | Chỉ hiện ở field (`only_fields`) | Nhóm hiển thị (`group_label`) |
  |---|---|---|---|---|
  | 11 | `row_literal` | `width\|height` | `["width","height"]` | `06a · Kích thước` |
  | 12 | `row_literal` | `qty\|calc_pattern` | `["qty","calc_pattern"]` | `06b · Số lượng` |

- ⛔ **Đừng** đặt hai rule đều `source_ref = *` với `only_fields` khác nhau: cả hai cùng khớp mọi
  biến nên kết quả là **hợp** — không tách được.
- Phạm vi từ nguồn (ví dụ binding khai `applies_to_field`) và phạm vi từ rule được **giao** lại.
  Giao rỗng ⇒ biến bị ẩn ở **mọi** field (server đánh dấu `hide_all`), khác hẳn "không giới hạn".

Chi tiết + ví dụ đầy đủ: [huong-dan-setting-bien.md](huong-dan-setting-bien.md) mục 4.

---

## 6. Migrate, build và kiểm tra

### 6.1 Chạy (chỉ trên site dev)

```bash
bench --site <dev> migrate
bench build --app alumglass
bench --site <dev> clear-cache
```

- `migrate` tạo 7 DocType mới, thêm cột `variable_profile` vào 4 doctype, và chạy patch seed
  `alumglass.patches.v28_14.seed_variable_catalog` + `alumglass.patches.v28_14.seed_bom_profile`.
- `build` nạp JS mới — `hooks.py` đã bump `formula_setup.js` / `cost_template.js` lên `v=1.2.0`.
- ⛔ Không chạy thử trên production. Backup site trước khi migrate.
- **Trước khi migrate, chụp danh sách bản ghi đang trống `variable_profile`** của 4 doctype
  (`AL Bom Set`, `AL Cost Template`, `AL Accessory Set`, `AL Alert Config`) — cần cho rollback
  mục 6.3, vì patch gán bằng `update_modified=False` nên sau đó không dựa vào `modified` để tìm lại.

### 6.2 Kiểm sau migrate

| Kiểm | Kỳ vọng |
|---|---|
| `AL Variable Settings` | **8** common variable, **10** row literal |
| `AL Formula Field` | **11** record đang bật |
| `AL Variable Profile` | **3** profile mẫu: `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`, `P_BOM_DEFAULT` |
| Patch Log | Có `seed_variable_catalog` và `seed_bom_profile` |
| `AL Cost Template` cũ | `variable_profile` đã gán nếu trước đó trống |
| `AL Bom Set` cũ | `variable_profile` đã gán `P_BOM_DEFAULT` nếu trước đó trống |
| `AL Accessory Set` | `variable_profile` đã gán `P_ACCESSORY_DEFAULT` bởi `seed_variable_catalog` nếu trước đó trống |
| Mở form, gõ thử | Autocomplete theo profile; form ⛔ không trắng |
| Lưu công thức dùng biến **ngoài** profile | **Phải lưu được** — bị chặn là sai thiết kế |

Chưa thấy dữ liệu seed dù patch đã ghi sổ: chạy lại (patch idempotent, không nhân đôi record):

```bash
bench --site <dev> execute alumglass.patches.v28_14.seed_variable_catalog.execute
bench --site <dev> execute alumglass.patches.v28_14.seed_bom_profile.execute
```

> ⚠️ "Chạy lại vô hại" nghĩa là **không nhân đôi record**. Riêng `seed_bom_profile` **luôn** chạy
> bước gán, nên bản ghi `AL Bom Set` đang trống — kể cả bản ghi anh vừa xoá trắng để rollback —
> sẽ **được gán lại `P_BOM_DEFAULT`**.

Chi tiết triển khai + xử lý patch: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) mục 3.

### 6.3 Rollback mức tài liệu

Tài liệu này chỉ mô tả rollback **cấu hình**; rollback mã/DB schema làm theo quy trình release.

| Muốn hoàn tác | Cách làm | Lưu ý |
|---|---|---|
| Tắt bộ lọc của một profile | `AL Variable Profile.is_active = 0` | Rơi về đường cũ sau khi context hết cache (≤ 5 phút) hoặc F5; ⛔ không xoá dữ liệu |
| Một bản ghi thôi dùng profile | Xoá trắng field **Variable Profile** trên bản ghi | Chỉ đổi gợi ý, ⛔ không đổi số tiền |
| Một field công thức thôi có editor | `AL Formula Field.is_active = 0` | Không xoá record, bật lại dễ |
| Bỏ một biến khỏi danh sách | `is_active = 0` trên dòng Settings tương ứng | Patch không seed lại dòng đã có |
| Hoàn tác việc patch gán profile hàng loạt | Xoá `variable_profile` trên các record **trước khi chạy đã trống** | ⚠️ Phải chụp danh sách này **trước** khi migrate; patch dùng `update_modified=False` nên không dựa vào `modified` để tìm lại |

> ⛔ Profile **không** nằm trong đường tính tiền. Nếu rollback profile mà số tiền đổi, đó là lỗi
> hồi quy — báo DEV, ⛔ đừng tiếp tục nới rule.

---

## 7. Ranh giới — tính năng này ⛔ không làm gì

| ⛔ Không có | Thực tế |
|---|---|
| Override profile **theo từng dòng** | Profile gắn ở **bản ghi mẹ**. Muốn khác theo dòng ⇒ tách bằng rule `only_fields` (mức rule) hoặc tách profile + bản ghi khác |
| `only_fields` là allowlist **từng biến** | Nó là cổng **mức rule**; muốn mỗi field một danh sách phải **tách biến giữa các rule** (mục 5.5) |
| Autocomplete bulk gửi `row_index` | Context nạp **một lần** cho `doctype + docname + child_table`; vì vậy `cost_template_line` có thể gợi ý cả `line_code` đứng **sau** dòng đang sửa. Chỉ preview/validate/gọi API trực tiếp có `row_index` mới lọc đúng "dòng trước" |
| Nút bấm cho `explain_variable` | Chỉ có API/console (mục 4.6) |
| Kiểm tra field tồn tại khi lưu `AL Formula Field` | Gõ sai `fieldname` vẫn lưu được (mục 5.3) |
| Nút "xóa cache" trên form | Sửa profile phải chờ TTL 5 phút của client hoặc F5 |

Danh sách đầy đủ 12 giới hạn đã biết: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) mục 5.

---

## 8. Đọc tiếp

| Tài liệu | Dành cho |
|---|---|
| [README.md](README.md) | Tổng quan Variable Catalog + luồng hoạt động |
| [huong-dan-setting-bien.md](huong-dan-setting-bien.md) | Chi tiết từng cột rule, 11 nguồn biến, 3 ví dụ có số liệu |
| [vi-du-a-z.md](vi-du-a-z.md) | Ví dụ đầu-cuối từ cấu hình tới công thức chạy được |
| [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) | Đường đi của một biến: từ gợi ý tới lúc engine tính |
| [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) | Tra từng DocType: setting ở đâu, lấy từ đâu, điều kiện gì, runtime đọc bảng nào |
| [api-reference.md](api-reference.md) | Bảng API, tham số, shape trả về, quyền |
| [troubleshooting.md](troubleshooting.md) | Triệu chứng → nguyên nhân → cách xử lý |
| [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) | Thay đổi, migration, tương thích ngược, giới hạn |
| [nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) | Toàn bộ nguồn biến, mô hình dữ liệu, autocomplete & runtime A–Z, lỗi đã vá |
| [Formula Builder — tính năng mới](../../../formula_builder/docs/huong-dan-tinh-nang-moi.md) | Phía engine: `$NAME`, lọc binding theo field, dedupe |
| [Hướng dẫn tính giá full flow](../huong-dan-tinh-gia-full-flow.md) | Luồng tính giá B0–B7 (⛔ không chép ở đây) |
