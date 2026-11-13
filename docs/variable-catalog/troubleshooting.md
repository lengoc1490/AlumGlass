# Xử lý sự cố — Variable Catalog (v28_14)

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `90892c1` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | Triệu chứng khi cấu hình/gõ công thức với `AL Variable Profile` |
> | Đối tượng | Admin cấu hình, người trực hỗ trợ, DEV |
> | Ngày soạn | 2026-11-12 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy migrate, chưa tái hiện trên site**. Bảng dưới đây suy ra
> từ mã của working tree. Khi gặp ca mới, ghi lại triệu chứng **thật** rồi bổ sung — ⛔ đừng
> suy đoán thêm triệu chứng chưa ai gặp.

---

## 1. Cách đọc bảng

Mỗi mục theo thứ tự: **hiện tượng → nguyên nhân → cách xử lý**.
Ký hiệu:

- `[API]` — kiểm bằng `bench execute` hoặc console.
- `[UI]` — kiểm trên màn hình.
- `[LOG]` — xem **Error Log** trong Desk (tìm theo tiêu đề ghi trong bảng).

### Bộ lệnh chẩn đoán nhanh

```bash
# Profile đang áp cho bản ghi (null = chưa gán)
bench --site <dev> execute alumglass.api.variable_catalog.get_variable_profile \
  --kwargs '{"doctype": "AL Bom Set", "docname": "<tên>"}'

# Danh mục thật + thống kê lọc
bench --site <dev> execute alumglass.api.variable_catalog.get_variable_catalog \
  --kwargs '{"doctype": "AL Bom Set", "docname": "<tên>", "child_table": "items", "row_index": 0, "fieldname": "qty"}'

# Vì sao một biến hiện / không hiện
bench --site <dev> execute alumglass.api.variable_catalog.explain_variable \
  --kwargs '{"variable_name": "TONG_M2", "doctype": "AL Bom Set", "docname": "<tên>"}'

# Registry field công thức
bench --site <dev> execute alumglass.api.formula_registry.get_formula_fields \
  --kwargs '{"doctype": "AL Bom Set"}'

# Danh sách row literal engine thật sự inject
bench --site <dev> execute alumglass.api.variable_catalog.get_row_literal_names
```

> `bench execute` chạy thường với user Administrator ⇒ **không** dùng để kết luận về quyền
> của người dùng thật.

---

## 2. Bảng sự cố

### 2.1 Không thấy biến nào

| | |
|---|---|
| **Hiện tượng** | Gõ vào field công thức, autocomplete trống hoặc chỉ có vài biến lạ |
| **Nguyên nhân thường gặp** | (a) profile `EXCLUDE_ALL` nhưng thiếu rule Include; (b) `source_kind` chọn sai nên không khớp nguồn nào; (c) `source_ref` ghi mã không tồn tại; (d) `only_fields` ghi sai tên field; (e) `require_value=1` nhưng biến rỗng; (f) rule Exclude quá rộng; (g) adapter lỗi (thiếu app `formula_builder`); (h) `hide_all=true` do giao phạm vi rỗng |
| **Cách xử lý** | `[API]` `get_variable_catalog` xem `meta.excluded_by_rules` và `meta.source_kinds`. Nếu `source_kinds` thiếu nguồn bạn định dùng ⇒ rule Include không được nhận. Nếu `excluded_by_rules` lớn ⇒ soi rule Exclude và `EXCLUDE_ALL`. `[API]` `explain_variable` cho biết nguồn nào bị loại ở bước nào. `[LOG]` tìm "Variable catalog adapter lỗi: &lt;source_kind&gt;". |

**Kiểm từng bước:**

1. `[API]` `get_variable_profile` → `null`? Nếu null, bản ghi **chưa** gán profile; đây không
   phải "không thấy biến" mà là đường legacy (xem 2.2).
2. `[API]` `get_variable_catalog` → `profile` có mã đúng không.
3. Đọc `meta.source_kinds` — chỉ các nguồn này được chạy.
4. Đọc `meta.duplicates` — nếu biến bị nguồn khác "nuốt", nó vẫn còn 1 bản; ⛔ không mất.
5. Với từng biến còn lại, đọc `only_fields` / `hide_all`.

> ⚠️ `only_fields` **không hề vô tác dụng** khi dùng autocomplete. Autocomplete nạp context
> **một lần** và không gửi `fieldname` lên server, nhưng server vẫn trả `only_fields`/
> `hide_all` trên **từng biến**, và **client lọc theo field đang sửa**. Khi API được gọi
> **có** `fieldname` (validate, preview), **server lọc rule** ngay. Chỉ khi không xác định
> được field ở cả hai phía thì mới không lọc.

---

### 2.2 Thấy quá nhiều biến

| | |
|---|---|
| **Hiện tượng** | Danh sách giống hệt trước khi cài v28_14; hàng chục biến không liên quan |
| **Nguyên nhân** | (a) bản ghi **chưa** gán `variable_profile`; (b) profile bị `is_active=0`; (c) profile không tồn tại (đã xoá) ⇒ rơi về legacy; (d) `default_action=INCLUDE_ALL` và **không có** rule Include nào ⇒ chạy **tất cả** adapter; (e) rule có `source_kind` để trống ⇒ khớp mọi nguồn |
| **Cách xử lý** | `[API]` `get_variable_profile`. Null ⇒ gán profile. Có profile nhưng vẫn nhiều ⇒ kiểm `default_action` và danh sách rule; dùng `EXCLUDE_ALL` + rule Include tường minh. `[UI]` mở profile xem băng "Đang dùng". |

> Đây là hành vi **cố ý** của tương thích ngược: record chưa gán profile phải giữ nguyên
> danh sách cũ. Không phải lỗi.

---

### 2.3 Biến hiện giá trị "—"

| | |
|---|---|
| **Hiện tượng** | Biến có trong danh sách nhưng cột giá trị là `—` |
| **Nguyên nhân** | `—` = **chưa resolve được giá trị tại form**, không phải lỗi. Thường gặp: cost bucket (chỉ có giá trị sau B4–B5), cost template line (tính tuần tự B6), user var chưa nhập, binding chưa resolve, docname trống khi tạo mới |
| **Cách xử lý** | Đọc `value_source` / `provenance` của biến để biết giá trị đến từ đâu và khi nào có. Nếu muốn **ẩn** biến rỗng ⇒ bật `require_value=1` trên rule Include. Nếu muốn biết lúc tính giá có giá trị không ⇒ mở dialog Tham số BOM hoặc chạy tính giá, ⛔ đừng suy từ autocomplete. |

> 🔴 Ghi nhớ: **biến hiện trong autocomplete ≠ biến chắc chắn có giá trị lúc tính.**
> Xem `../../nguon_bien_tham_chieu.md` §1.2.

---

### 2.4 Profile không áp

| | |
|---|---|
| **Hiện tượng** | Đã gán profile nhưng danh sách không đổi |
| **Nguyên nhân** | (a) `variable_profile` gán trên **bảng con** thay vì bản ghi mẹ; (b) profile `is_active=0`; (c) client đang dùng **cache 5 phút** của bản ghi (xem 2.5); (d) đang mở form **tạo mới** nên `docname` trống và field Link chưa lưu; (e) JS cũ chưa build lại (hooks đã bump `v=1.2.0`); (f) doctype không nằm trong 4 doctype có field `variable_profile` |
| **Cách xử lý** | `[API]` `get_variable_profile` phải trả mã profile. Nếu đúng mà UI vẫn cũ ⇒ `bench build --app alumglass` rồi tải lại trang. Nếu vẫn cũ ⇒ `bench --site <dev> clear-cache` rồi F5. |

> 4 doctype có field: `AL Bom Set`, `AL Cost Template`, `AL Accessory Set`,
> `AL Alert Config`. Các doctype khác **không** có field nên không gán được.
>
> ⚠️ Form **tạo mới** chưa có profile ⇒ chạy đường legacy: danh sách biến đầy đủ **và** gợi ý
> `items.<slug>.{field}` từ `AL Slug Library`. Đây là hành vi đúng, không phải lỗi; lưu bản ghi
> (hoặc đặt `AL Variable Settings.default_profile`) rồi mở lại mới thấy profile áp dụng.

---

### 2.5 Sửa profile nhưng không thấy thay đổi (cache 5 phút)

| | |
|---|---|
| **Hiện tượng** | Vừa sửa rule/nhóm, mở lại form vẫn danh sách cũ |
| **Nguyên nhân** | `formula_setup.js` cache context theo khoá `doctype::docname::child_table`, **TTL 5 phút** (`_ttl: 300000`, dòng 28). Mở lại form trong Single Page App **không** xoá cache. Mã có hàm `invalidate(doctype)` xoá theo prefix `doctype::`, nhưng **hiện chưa có chỗ nào gọi** (đọc mã 2026-11-12) |
| **Cách xử lý** | (1) **F5 / đóng tab** — xoá cache trong RAM của trang. (2) Chờ tối đa 5 phút rồi refresh. (3) Nếu vẫn cũ, `bench --site <dev> clear-cache`. (4) Kiểm server: `[API]` `get_variable_catalog` trả đúng chưa — nếu server đúng thì chắc chắn là cache client. |

> Cache registry `AL Formula Field` ngắn hơn: **60 giây** (`_ttl: 60000`, dòng 241).
> Thêm field mới có thể phải chờ 60 giây hoặc F5.

> Ghi chú cho DEV: hai hàm `invalidate()` (dòng 102 và 362) đang là **code chết** — nếu muốn
> "sửa thấy ngay", phải gọi chúng ở chỗ phù hợp (sau khi lưu profile / `AL Formula Field`).
> Hiện tài liệu **không** hứa hành vi đó.

---

### 2.6 Migrate chưa chạy

| | |
|---|---|
| **Hiện tượng** | Không thấy menu `AL Variable Profile`; form `AL Bom Set` không có field **Variable Profile**; `get_formula_fields` trả `[]`; Settings không có dữ liệu; xem trước báo lỗi API |
| **Nguyên nhân** | 7 DocType mới + cột `variable_profile` + patch seed chỉ có sau migrate. Code có fallback (thiếu bảng ⇒ legacy / rỗng), nên triệu chứng là **im lặng**, không phải lỗi đỏ |
| **Cách xử lý** | `bench --site <dev> migrate` → `bench build --app alumglass`. Kiểm **Patch Log**: phải có `alumglass.patches.v28_14.seed_variable_catalog` và `alumglass.patches.v28_14.seed_bom_profile`. Nếu patch đã ghi sổ nhưng không có dữ liệu, chạy lại (idempotent) lần lượt `…seed_variable_catalog.execute` và `…seed_bom_profile.execute`. Nếu patch báo lỗi "chưa có doctype 'AL Variable Profile'", kiểm `alumglass/patches.txt` — patch phải nằm ở khối `[post_model_sync]`. |

> **Profile có mà `AL Bom Set` vẫn trống `variable_profile`** ⇒ chạy lại
> `bench --site <dev> execute alumglass.patches.v28_14.seed_bom_profile.execute`. Bước gán chạy
> lại được kể cả khi profile đã tồn tại; nó chỉ gán bản ghi **đang trống**, ⛔ không đè lựa chọn
> admin đã đặt.

**Kiểm nhanh sau migrate:**

| Mục | Kỳ vọng |
|---|---|
| `AL Variable Settings.common_variables` | 8 dòng |
| `AL Variable Settings.row_literals` | 10 dòng (có `max_area_m2`) |
| `AL Formula Field` | 11 dòng `is_active=1` |
| `AL Variable Profile` | 3 profile mẫu (`P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`, `P_BOM_DEFAULT`) |
| `AL Cost Template.variable_profile` | record cũ đã được gán nếu trước đó trống |
| `AL Bom Set.variable_profile` | record cũ đã được gán `P_BOM_DEFAULT` nếu trước đó trống |

---

### 2.7 Cross-row ra 0

| | |
|---|---|
| **Hiện tượng** | Công thức `items.<slug>.<field>` lưu được, validate PASS, nhưng tính ra 0/None |
| **Nguyên nhân** | (a) field **không được engine inject** — điển hình là `qty_formula` trên `AL Accessory Set` (đây là **chuỗi công thức**, không phải giá trị); (b) slug không tồn tại trong bảng; (c) dùng `items[n].field` trong `rule_input_expr` — engine chỉ parse dạng slug ở đó; (d) field thuộc bảng con khác; (e) dòng đích chưa có giá trị tại thời điểm tính |
| **Cách xử lý** | Đối chiếu danh sách field engine thật sự tạo `{slug}__{field}`. Với `AL Accessory Set`: `qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total` — ⛔ **không** `qty_formula`. Với `rule_input_expr`, xem cảnh báo cam khi lưu `AL Bom Set` (tính năng mới: cảnh báo slug/field sai, **không chặn**). `[API]` `get_variable_catalog` → `references` chỉ chứa field đã khai trong `cross_row.fields`. |

> ⚠️ **Validate PASS ≠ runtime có giá trị.** Từ bản vá 2026-11-13, `AL Bom Set` nhận **superset**:
> `FORMULA_FIELDS` (`width/height/qty/show_condition`) + `ENGINE_SYNTHETIC_FIELDS`
> (`unit_qty/total_qty/line_total`) + row literal **đang bật** trong `AL Variable Settings`
> (`unit_price`, `glass_thick`, `scrap_pct`, `calc_pattern`…). Đây chỉ là universe cho `known_names`
> — field không được engine inject vẫn ra **0**. Đừng lấy việc lưu được làm bằng chứng field có giá trị.

> Cảnh báo `rule_input_expr` **không** hiện với dòng có `item_selection_mode` khác `Rule` —
> engine chỉ đọc `rule_input_expr` ở chế độ đó.

### 2.7.1 Bỏ `slug_reference` mà vẫn thấy `items.*`

| | |
|---|---|
| **Hiện tượng** | Profile không khai rule `slug_reference`, có khi cũng không có `cross_row`, nhưng autocomplete vẫn gợi ý `items.<slug>.<field>` |
| **Nguyên nhân** | (a) `default_action = INCLUDE_ALL` — `build_references` nhánh 3 sinh cho **mọi** bảng con mà không cần rule; (b) **profile không resolve được** cho bản ghi đang mở (record mới chưa lưu, `variable_profile` trống + `default_profile` trống, profile `is_active=0`) ⇒ đường legacy **luôn** thêm `items.<slug>.{field}` từ `AL Slug Library` toàn cục; (c) `default_profile` trỏ profile khác; (d) cache 5 phút |
| **Cách xử lý** | Gọi `get_formula_context` và đọc `profile`: `null` ⇒ đang ở legacy (nguyên nhân b); có `meta.profile_code` ⇒ kiểm `default_action` và `AL Variable Settings.default_profile`. Reload form trước khi kết luận vì cache `doctype::docname::childTable` giữ 5 phút. Chi tiết: [al-variable-profile.md](al-variable-profile.md) §7.2.1 |

> `slug_reference` **không bao giờ** sinh biến — nó chỉ sinh references. Vì vậy "không thấy biến
> `items.*`" và "vẫn thấy gợi ý `items.*`" có thể cùng đúng trên một profile.

---

### 2.8 Báo "Biến không khai báo" oan

| | |
|---|---|
| **Hiện tượng** | Công thức đang chạy đúng (hoặc biến có trong gợi ý) nhưng khi lưu bị báo biến không khai báo |
| **Nguyên nhân** | (a) universe validate bị thu hẹp theo profile — **không được xảy ra** sau v28_14, nhưng client cũ / code tự gọi `get_formula_context` không truyền `include_all_sources` có thể gây lại; (b) `build_known_names` ném lỗi ⇒ universe rỗng (chỉ còn biến cross-row); (c) biến thật sự không có trong đường legacy (gõ sai tên); (d) field cross-row **không thuộc superset** validate (không phải field công thức, không phải `unit_qty`/`total_qty`/`line_total`, và row literal đó đang **tắt** trong `AL Variable Settings`); (e) biến `$NAME` chưa được normalize |
| **Cách xử lý** | `[API]` gọi `get_formula_context(..., include_all_sources=True)` (qua `bench execute` thêm `"include_all_sources": 1`) và kiểm tên biến có trong `variables`. Nếu có ⇒ lỗi ở client/validate, không phải dữ liệu. `[LOG]` tìm "AlumGlass Formula Validate". Kiểm field công thức đang validate có phải `qty_formula` / `calc_formula` không — hai chỗ này đã có đường validate riêng. |

> ✅ Hợp đồng đúng: validate **luôn** dùng universe đầy đủ. Profile chỉ lọc gợi ý.
> Nếu bạn thấy validate bị profile chặn, đó là **lỗi hồi quy** — ghi lại đường gọi
> (method + tham số) rồi báo DEV, ⛔ đừng nới rule profile để lách.

---

### 2.9 Preview lỗi quyền

| | |
|---|---|
| **Hiện tượng** | Bấm **Xem trước danh sách biến** báo "Bạn không có quyền xem trước danh mục biến." hoặc nút không có |
| **Nguyên nhân** | `preview_variable_catalog` yêu cầu quyền **read trên `AL Variable Profile`**. Phân quyền mặc định của 3 DocType cấu hình chỉ cấp `System Manager` |
| **Cách xử lý** | Cấp role có read trên `AL Variable Profile` (Role Permission Manager), hoặc dùng tài khoản System Manager để cấu hình. Nút chỉ hiện khi record **đã lưu** (`frm.is_new()` ⇒ ẩn). |

> Preview còn đi qua guard doctype: chọn `DocType` ngoài miền `AL `/`Formula Builder`/
> `Quotation` sẽ bị chặn với câu "Không lấy được danh sách biến công thức…".

---

### 2.10 `AL Formula Field` không có tác dụng

| | |
|---|---|
| **Hiện tượng** | Thêm record nhưng field không thành editor công thức / không có autocomplete |
| **Nguyên nhân** | (a) `is_active=0`; (b) `target_doctype` sai; (c) `child_table` ghi **tên doctype con** (`AL Bom Item`) thay vì **tên field bảng** (`items`); (d) `fieldname` không đúng field thật; (e) trùng bộ `(target_doctype, child_table, fieldname)` — controller chặn lưu; (f) chưa `bench build` nên trình duyệt còn JS cũ; (g) cache 60 giây; (h) form đang mở là form **dòng con** (`meta.istable`) nên bị bỏ qua; (i) field bị `depends_on` ẩn lúc patch |
| **Cách xử lý** | `[API]` `get_formula_fields` với doctype tương ứng phải trả record. Không trả ⇒ kiểm (a)–(e) và migrate. Có trả mà UI không đổi ⇒ (f)(g), rồi F5. Với `AL Bom Set`, đổi **Item Selection Mode** sẽ kích hoạt patch lại `item_condition_formula` / `rule_input_expr`. |

**Giá trị đúng của `child_table`:**

| Field công thức nằm ở | `child_table` |
|---|---|
| Dòng `items` của `AL Bom Set` / `AL Accessory Set` / `AL Cost Template` | `items` |
| Field cấp cha (`trigger_condition`, `calc_fn`, `formula_expr`) | để **trống** |

> `target_doctype` là fieldname thật trong DB (nhãn trên form: **Doctype**). ⛔ Không đặt tên
> field là `doctype` —
> Frappe coi đó là từ khoá dành riêng và DocType bị từ chối khi migrate.

---

### 2.11 Biến bị "nuốt" do trùng tên

| | |
|---|---|
| **Hiện tượng** | Biết chắc có 2 nguồn cung cấp cùng tên biến nhưng chỉ thấy 1, giá trị/nhóm khác mong đợi |
| **Nguyên nhân** | Dedup giữ 1 nguồn theo thứ tự: **có giá trị** → `sort_order` nhỏ hơn → adapter đăng ký trước → xuất hiện trước |
| **Cách xử lý** | `[API]` `explain_variable` xem `sources[].selected/kept` và `meta.duplicates`. Muốn đổi nguồn thắng ⇒ chỉnh `sort_order` của rule hoặc xoá/tắt nguồn không mong muốn. Đây là **lọc gợi ý**, ⛔ không đổi giá trị lúc tính. |

---

### 2.12 Bản ghi thứ hai hiện biến của bản ghi thứ nhất

| | |
|---|---|
| **Hiện tượng** | Mở Cost Template A rồi mở B trong cùng phiên, danh sách biến vẫn của A |
| **Nguyên nhân** | Cache client khoá theo `doctype::docname::child_table`. Nếu docname trống (form tạo mới) hoặc JS cũ, khoá có thể trùng |
| **Cách xử lý** | Kiểm JS đã là bản `v=1.2.0` (`bench build`). Với `AL Cost Template`, `cost_template.js` đã tách cache **theo docname**; bản cũ dùng 1 ô chung nên dính lỗi này. F5 để xoá cache. |

---

## 3. Ba chỗ ghi log cần biết

| Tiêu đề Error Log | Phát ra từ | Nghĩa |
|---|---|---|
| `Variable catalog adapter lỗi: <source_kind>` | `variable_catalog._run_adapters` | Một nguồn hỏng; các nguồn khác vẫn chạy |
| `AlumGlass get_variable_catalog failed: <doctype>` | `api/__init__.py::_get_catalog_context` | Catalog lỗi ⇒ đã rơi về legacy |
| `AlumGlass get_formula_fields failed: <doctype>` | `formula_registry.get_formula_fields` | Registry lỗi ⇒ trả `[]` |
| `AlumGlass Formula Validate` | `formula_validate.build_known_names` | Universe validate rỗng ⇒ có thể báo lỗi biến oan |

---

## 4. Đọc tiếp

- Cách setting đúng: [huong-dan-setting-bien.md](huong-dan-setting-bien.md)
- Ví dụ setting đầy đủ + cách tắt/chỉ hiện biến: [vi-du-setting-day-du.md](vi-du-setting-day-du.md)
- Shape API và lỗi trả về: [api-reference.md](api-reference.md)
- Trạng thái triển khai và giới hạn: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md)
- Toàn bộ nguồn biến: [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md)
