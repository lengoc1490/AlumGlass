# Từ gõ gợi ý đến runtime ra giá trị

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `566cdc2` + thay đổi v28_14 **và bản vá validate cross-row chưa commit** (working tree: `al_bom_item.py`, `al_bom_set.py` sửa; `alumglass/tests/test_bom_set_cross_row_known_fields.py` mới) |
> | Formula Builder | nhánh `develop`, HEAD `51cb497` |
> | Phạm vi | Vòng đời một biến công thức: từ lúc **gợi ý trong autocomplete** đến lúc **engine ra số tiền**; chỉ ra chỗ hai mặt phẳng khớp và chỗ lệch |
> | Đối tượng | DEV bảo trì, người cấu hình công thức đang gỡ lỗi "gợi ý có mà ra 0" |
> | Ngày soạn | 2026-11-13 |
>
> **Mức kiểm chứng:** đọc mã tĩnh toàn bộ đường đi (JS + Python + JSON DocType). **Chưa chạy
> `bench migrate`, chưa mở form, chưa chạy test trên site** — bench hiện không có site cài
> `alumglass`. Các test thuần hiện có được ghi nhận ở [README.md](README.md) mục "Mốc code".
> Mọi mô tả giao diện dưới đây suy ra từ mã, **chưa quan sát trên màn hình thật**.

> **Một câu chốt:** catalog quyết định bạn **THẤY** gì khi gõ; engine quyết định bạn **ĐƯỢC**
> bao nhiêu tiền khi tính. Hai bên chỉ gặp nhau ở đúng ba chỗ (mục 1.3). Sửa profile, đổi
> `only_fields`, bật/tắt một rule — **không đổi một đồng nào** trong báo giá.

---

## 0. Đọc nhanh

| Câu hỏi | Đọc mục |
|---|---|
| Vì sao gợi ý hiện một biến mà công thức ra 0? | [14](#14-vì-sao-gợi-ý-thấy-mà-runtime-ra-0none--8-nguyên-nhân) |
| Biến này từ đâu ra? Nguồn nào đang thắng? | [12](#12-bước-10--bảng-provenance-giá-trị), [5](#5-bước-3--adapter-sinh-candidate), API `explain_variable` |
| Profile gán ở đâu, thứ tự resolve thế nào? | [4](#4-bước-2--resolve-profile) |
| Công thức lưu ở field nào? | [8](#8-bước-6--lưu-công-thức) |
| Engine tính theo thứ tự nào, lớp nào đè lớp nào? | [10](#10-bước-8--runtime-b0b7) |
| Sửa cấu hình xong bao lâu mới thấy? | [15](#15-cache-và-invalidation) |
| Đang gỡ lỗi, làm theo thứ tự nào? | [Phụ lục D](#d-checklist-debug-10-bước) |

Ba tầng nhìn, đừng lẫn:

1. **Danh mục (design-time)** — `AL Variable Profile` + adapter + rule. Chỉ tên/nhãn/giá trị
   hiển thị.
2. **Văn bản công thức (lưu trữ)** — chuỗi người dùng gõ, lưu nguyên văn vào field Small Text.
3. **Runtime** — `BomOrchestrator` dựng `inputs`, chạy DAG công thức, ra bucket rồi ra giá.

---

## 1. Bức tranh hai mặt phẳng

### 1.1 Mặt phẳng A — gợi ý (design-time)

```
form-refresh
  → formula_setup.js  (alumglass.FormulaFields, alumglass.FormulaContext)
  → RPC alumglass.api.get_formula_context
  → api/__init__.py :: _get_catalog_context
  → api/variable_catalog.py :: get_variable_catalog
  → variable_sources/context.py  (đọc doc, settings, resolved)
  → variable_sources/adapters.py (10 adapter)
  → variable_sources/rules.py    (Exclude/Include, dedupe, group)
  → trả { profile, variables, groups, references, meta }
  → monkey-patch Formula Builder _ContextBuilder.build  → Monaco autocomplete
```

Đầu ra chỉ có: `name`, `label`, `type`, `value` (để hiển thị), `group`, `provenance`,
`only_fields`, `hide_all`, `references`. Không có đường nào từ đây ghi vào `inputs` của engine.

### 1.2 Mặt phẳng B — tính giá (runtime)

```
alumglass.api.calculate_bom(quotation_item)
  → engine/bom_orchestrator.py :: BomOrchestrator.run()
      B0 version pinning
      B1 gather inputs
      B2 prefetch master data
      B3 build formulas
      B4 calculate bom items
      B5 aggregate cost buckets
      B6 calculate cost template
      B7 save results
```

Đầu vào của B1 **không đọc** `AL Variable Profile`, **không gọi** `get_formula_context`.
Đã kiểm tĩnh: `grep -n "variable_catalog\|get_formula_context\|variable_profile"
alumglass/engine/*.py` → không có kết quả.

### 1.3 Ba cầu nối thật giữa hai mặt phẳng

| Cầu nối | Dùng ở đâu | Hệ quả |
|---|---|---|
| `system_variable_resolver.py` | Cả `api/__init__.py::_resolve_doc_values` (gợi ý) và `BomOrchestrator._resolve_system_variables` (runtime) | Giá trị system var hiện trong tooltip là cùng nguồn với giá trị engine dùng — trước đây hai nơi tự viết nên lệch tên biến |
| `formula_builder.api.formula_builder.get_live_context` | Cả `_get_live_context_vars` (gợi ý) và `_resolve_fb_context` (B1) | Binding resolve cùng handler; scope khác nhau (khi tính giá scope là `AL Bom Set`, khi gợi ý là doctype đang mở) |
| Chuỗi công thức lưu trong field | Autocomplete chèn vào; engine đọc lại đúng field đó ở B3/B6 | Không có bản sao thứ hai; nhưng engine chuẩn hoá chuỗi trước khi chạy (mục 8) |

Ngoài ba cầu nối trên, mọi thứ khác là **hai hệ độc lập**. Vì vậy một biến có thể:

- **có trong gợi ý, không có trong runtime** → ra 0/None (mục 14);
- **không có trong gợi ý, vẫn chạy đúng ở runtime** → validate cũng không chặn, vì validate dùng
  universe đầy đủ (`include_all_sources=True`, mục 9).

### 1.4 Ranh giới phải nhớ khi sửa cấu hình

| Việc bạn làm | Đổi danh sách gợi ý | Đổi số tiền |
|---|---|---|
| Sửa rule Include/Exclude của profile | Có | Không |
| Sửa `only_fields`, `require_value` | Có | Không |
| Gán/đổi `variable_profile` trên bản ghi | Có | Không |
| Sửa `AL Variable Library.default_value` | Có (giá trị hiển thị) | **Có** (B1 fallback) |
| Sửa `Formula Variable Binding` | Có | **Có** (B1 nguồn chính) |
| Sửa công thức trong field | Gián tiếp (đổi chuỗi) | **Có** |

---

## 2. Bước 0 — dữ liệu nền

Đây là các bảng phải có trước khi cả hai mặt phẳng chạy được. Cột "ai đọc" chỉ nơi đọc thật.

| # | Dữ liệu | DocType / bảng | Ai đọc | Dùng để |
|---|---|---|---|---|
| 1 | Thư viện biến | `AL Variable Library` | adapter `variable_library_system/user`, `system_variable_resolver`, B1 | Tên, nhãn, kiểu, `is_system`, `source_doctype`/`source_field`, `default_value` |
| 2 | Bộ biến theo sản phẩm | `AL Variable Set` + `AL Variable Set Item` | adapter `variable_set`, `_inject_variable_set_vars`, `_resolve_variable_set_name` | Nhóm biến user theo sản phẩm; giá trị vẫn do người dùng nhập |
| 3 | Bucket giá thành | `AL Cost Bucket` | adapter `cost_bucket`, B5, B6 | `bucket_code` là tên biến; `report_group` là nhóm; `source_type`/`source_config` quyết cách gom |
| 4 | Slug dòng | `AL Slug Library` + `AL Bom Item.slug` | adapter references, B2 `row_literals`, B3 | Định danh dòng cho cross-row `items.<slug>.<field>` |
| 5 | Mẫu giá thành | `AL Cost Template` + `AL Cost Template Item` | adapter `cost_template_line`, B6 | `line_code` là biến dẫn xuất; `calc_formula` là công thức |
| 6 | Row Literal / Common Var | `AL Variable Settings.row_literals` / `.common_variables` | adapter `row_literal`/`common_var`, B2/B3, `get_row_literal_names` | Row literal engine inject theo dòng; common var người dùng nhập |
| 7 | Binding biến | `Formula Variable Binding` (app `formula_builder`) | adapter `fvb_scope`, `get_live_context`, B1 | Lớp resolve có handler theo `source_type` |
| 8 | Hằng số toàn cục | `Formula Global Variable` | adapter `formula_global`, B1 bước 1.2, `global_variable_cache` | Hằng số như `VAT_RATE`, `NC_SX_PCT` |
| 9 | Hồ sơ danh mục | `AL Variable Profile` + `AL Variable Profile Rule` + `AL Variable Cross Row` | `variable_catalog.py`, `rules.py` | Chỉ lọc gợi ý (mục 4–6) |
| 10 | Cấu hình chung | `AL Variable Settings` (Single) | `_settings_variable_entries`, `_resolve_profile_doc` | `default_profile`, hai bảng biến (mục 5.1) |
| 11 | Registry field công thức | `AL Formula Field` | `formula_setup.js`, `formula_registry.get_formula_fields` | Field nào trên form nào được gắn Monaco + autocomplete |

Bảng phụ nhưng ảnh hưởng số tiền: `AL Material Category` (`default_scrap_pct`, `has_weight`,
`default_calc_pattern`), `AL Quantity Calc Method` (`input_vars`, `output_unit`),
`AL Profile System` (child `system_variables` override), `AL Variable Dimension Mapping`
(cờ `is_pricing_dimension` + giá composite), `Item Price`, `AL Glass Master`.

---

## 3. Bước 1 — mở form

**Ai gọi:** Frappe phát sự kiện `form-refresh` trên `$(document)` trong lúc render form.

**Hàm/tệp:** `alumglass/public/js/formula_setup.js`

1. Handler `$(document).on("form-refresh", ...)` bỏ qua form dòng con (`frm.meta.istable`).
2. `alumglass.FormulaFields.init(frm)`:
   - `fetch(frm.doctype)` → RPC `alumglass.api.get_formula_fields`, cache **60 giây** theo
     doctype (`_ttl = 60000`), có `_pending` chống gọi trùng.
   - Không có dòng nào → dừng (không gọi context).
   - Có dòng → `FormulaContext.fetch(doctype, docname, "")` cho field cha, và **một lần cho mỗi
     `child_table` phân biệt** có field công thức. Không gọi theo từng `fieldname`.
3. `FormulaContext.fetch`:
   - Cache key `doctype::docname::childTable`, TTL **5 phút** (`_ttl = 300000`).
   - Gọi RPC `alumglass.api.get_formula_context` với `{doctype, docname, child_table}`.
   - Lỗi mạng → trả `{variables: [], references: []}` và `console.warn`; **không** fallback
     danh sách cứng.
4. `getSync(doctype, docname, childTable)` — đọc cache đồng bộ, thử lần lượt:
   `doctype::docname::child` → `doctype::docname::` → `doctype::docname` → `doctype`.
   Nhờ vậy widget vẫn có biến khi prefetch theo child table chưa xong.
5. `apply(frm, row)`: kiểm `is_active`, kiểm field tồn tại, rồi
   `formula_builder.formula.patchField` (field cha) hoặc `initGridField` (cột bảng con).

**Vào/ra:** vào là `frm`; ra là editor Monaco được gắn vào field + cache context nạp sẵn.

Ghi chú: `AL Formula Field.editor_opts` (JSON) được `_buildOpts` merge đè lên mặc định
(`language: "formula-builder"`, ẩn toolbar/preview). `id_field` mặc định `slug`; field cha
không tự đặt `height`.

---

## 4. Bước 2 — resolve profile

**Ai gọi:** server, trong `api/__init__.py::_get_catalog_context` → `api/variable_catalog.py::_resolve_profile_doc`.

**Thứ tự (dừng ở cái đầu tiên tìm được):**

| Bước | Nguồn | Điều kiện |
|---|---|---|
| 1 | Tham số `profile` truyền thẳng | Chỉ có ở `preview_variable_catalog` / `explain_variable` (admin xem trước) |
| 2 | Field Link trên chính doctype trỏ `AL Variable Profile` | `_find_profile_field` lấy field Link **đầu tiên**; doctype **không có** field này thì dừng ngay, trả `None` |
| 3 | Giá trị field đó của bản ghi (`docname`) | Chỉ khi có `docname`; đọc bằng `frappe.db.get_value` |
| 4 | `AL Variable Settings.default_profile` | Chỉ tới được bước này khi doctype **đã có** field Link |

`_load_profile` kiểm thêm: record tồn tại **và** `is_active = 1`. Profile tắt coi như không có.

**Hệ quả của "không gán profile":** `_get_catalog_context` trả `None` → `get_formula_context`
rơi xuống **đường legacy 9 nhóm** (mục 5.3). Đây là hành vi tương thích ngược có chủ đích: bản
ghi cũ không bị đổi danh sách biến khi bật tính năng.

Profile hiện được khai field Link trên **đúng 4 doctype**: `AL Bom Set`, `AL Accessory Set`,
`AL Cost Template`, `AL Alert Config` (`variable_profile` trong JSON). Doctype khác muốn dùng phải
thêm field Link — không sửa code.

---

## 5. Bước 3 — adapter sinh candidate

**Ai gọi:** `variable_catalog._build_catalog` → `_run_adapters(ctx, kinds)`.

**Vào:** `CatalogContext` (doctype, docname, child_table, row_index, fieldname, profile).
**Ra:** list candidate cùng shape (`make_candidate`), chưa lọc rule.

`_run_adapters` chỉ chạy adapter có `source_kind` nằm trong tập `active_source_kinds`
(mục 6.1). Lỗi một adapter → `frappe.log_error` + bỏ adapter đó, các adapter khác vẫn chạy.

### 5.1 Mười adapter

| Order | `source_kind` | Đọc bảng nào | Giá trị hiển thị lấy từ đâu | `has_value` khi nào |
|---|---|---|---|---|
| 10 | `fvb_scope` | `Formula Variable Binding` qua `binding_scope.get_scope_bindings_multi([doctype, child_doctype], field=fieldname)` | Resolve bằng `resolve_bindings_with_deps`: binding của dòng con resolve trên **dòng hiện tại** (cần `row_index`), còn lại resolve trên **chứng từ cha**; thứ tự giá trị: dòng → cha → `default_value` | `value is not None` |
| 20 | `cost_bucket` | `AL Cost Bucket` (`is_active=1`) | `ctx.resolved[bucket_code]` — tức chỉ có số nếu trùng tên một system var resolve được; bình thường là `None` → hiển thị `—` | `value is not None` |
| 30 | `variable_library_system` | `AL Variable Library` (`is_system=1`) | `ctx.resolved[var_name]`; không có thì `default_value` | `value is not None` |
| 40 | `variable_library_user` | `AL Variable Library` (`is_system=0`) | Luôn `None` → `—` (người dùng nhập ở dialog) | `False` |
| 45 | `variable_set` | `AL Variable Set` (+ `AL Variable Set Item`, đọc thêm Library để lấy nhãn/kiểu) | `ctx.resolved[var_name]` | `value is not None` |
| 50 | `cost_template_line` | `AL Cost Template.items` | Luôn `None` (chỉ tính được ở B6) | `False` |
| 55 | `formula_global` | `Formula Global Variable` (`is_active=1`) | `constant_value`, **chỉ khi** `value_source == "CONSTANT"`; loại khác → `None` | `value is not None` |
| 60 | `row_literal` | `AL Variable Settings.row_literals` | Có dòng hiện tại (`row_index`) → đọc field cùng tên trên dòng; không → đọc field cùng tên trên chứng từ; không nữa → `None` | `value is not None` |
| 70 | `common_var` | `AL Variable Settings.common_variables` | `ctx.resolved[var_name]` | `value is not None` |
| 80 | `doctype_field` | Meta của doctype chứa field đang sửa + doc/dòng | Giá trị field vô hướng (Data, Int, Float, Currency, Percent, Check, Select, Link, Date, Datetime, Time) | `value is not None` |

`doctype_field` **cố ý loại** `Small Text`/`Text`/`Table`/`JSON` (`get_scalar_fieldnames`).
Trên `AL Bom Item`, `width`/`height`/`qty` là Small Text chứa **công thức** — gợi ý chúng như
biến số là sai nghĩa.

### 5.2 Vài chi tiết dễ đọc nhầm

- `cost_bucket` và `variable_library_user` gần như luôn hiện `—`. Đó **không phải lỗi**: giá trị
  chỉ có lúc engine chạy hoặc do người dùng nhập. `has_value=false` là thông tin đúng.
- `fvb_scope` là nguồn duy nhất resolve được giá trị **thật** của binding ngay trong autocomplete.
  Nó cần `row_index` để đọc binding scope dòng con; đường autocomplete hiện **không gửi**
  `row_index` (mục 7.4). Hệ quả đúng theo mã: `get_current_row()` trả `None` → binding của dòng
  con **không resolve được giá trị trên dòng**, chỉ còn giá trị resolve từ chứng từ cha hoặc
  `default_value`.
- `cost_template_line` cắt danh sách theo `row_index` (`rows[:row_index]`) để tránh tham chiếu
  vòng. Không có `row_index` → **không cắt**, gợi ý cả dòng phía sau (mục 7.4 và 14.7).
- `variable_set` lấy tên set theo 3 nhánh: field Link trỏ thẳng `AL Variable Set` → đi qua
  `AL Bom Set.variable_set` → suy theo `product_type` (bản `modified desc` thắng, chốt thêm
  `name asc` cho ổn định). Set khai tường minh trong rule Include cũng được thêm vào.

### 5.3 Đường legacy — 9 nhóm khi bản ghi chưa gán profile

`_get_catalog_context` trả `None` khi không resolve được profile (hoặc khi gọi với
`include_all_sources=True`). Khi đó `get_formula_context` dựng danh sách từ DB theo đúng thứ tự
dưới đây rồi dedupe:

| # | Nhóm | Nguồn |
|---|---|---|
| 0 | `Bindings · FB (global)` / `Bindings · {doctype}` | `get_live_context` (chỉ dòng có giá trị scalar) |
| 1 | `Cost Bucket` (hoặc `report_group` của bucket) | `AL Cost Bucket` |
| 2 | `System Variables` | `AL Variable Library is_system=1` + `_resolve_doc_values` |
| 3 | `User Variables` | `AL Variable Library is_system=0` |
| 4 | `Formula Global Variables` | `Formula Global Variable` |
| 5 | `Row Literals` (hoặc `group_label`) | `AL Variable Settings.row_literals` |
| 6 | `BOM Input Variables` | `AL Variable Settings.common_variables` |
| 7 | `Formula Bindings` / `Bindings · {doctype}` | `Formula Variable Binding` |
| 8 | `Variable Set · {code}` | `AL Variable Set` của bản ghi hiện tại |

References (`items.<slug>.<field>`) sinh riêng từ `AL Slug Library`, không nằm trong 9 nhóm biến.

Khác biệt so với đường catalog:

- **Không** áp rule, **không** có `groups` trong response (client phẳng theo `group`);
- vẫn có dedupe, nhưng luật hợp phạm vi field chỉ áp cho entry đến từ FVB (`hide_all` có thể
  xuất hiện ở nhóm 0);
- bảng rỗng/chưa migrate → hai bảng Row Literal/Common Var rơi về tuple cứng
  (`_LEGACY_ROW_LITERALS`, `_LEGACY_COMMON_VARS`); bảng có dòng nhưng tắt hết → trả rỗng, tôn
  trọng cấu hình admin.

---

## 6. Bước 4 — rule + dedupe + nhóm + references

**Ai gọi:** `_build_catalog` → `rules.active_source_kinds` → `select_candidates` →
`dedupe_candidates` → `build_groups`; `adapters.build_references` chạy riêng.

### 6.1 Chọn nguồn cần chạy (`active_source_kinds`)

| Cấu hình | Nguồn được chạy |
|---|---|
| Có ít nhất 1 rule Include (bỏ `slug_reference`) | Chỉ các `source_kind` đó |
| Không có Include, `default_action = INCLUDE_ALL` | **Tất cả** adapter đã đăng ký (trừ `slug_reference`) — profile rỗng không làm mất biến |
| Không có Include, `default_action = EXCLUDE_ALL` | Không chạy nguồn nào (allowlist: không khai = không có) |

### 6.2 Áp rule (`select_candidates`), đúng thứ tự

1. Rule **Exclude** khớp → loại. **Exclude luôn thắng Include.**
2. `require_value`: rule Include khớp điều kiện nguồn nhưng khai `require_value=1` mà biến rỗng
   → loại hẳn (không rơi về "hiện với nhóm mặc định") — **chỉ khi biến chưa khớp rule Include
   nào khác**; có rule khác khớp thì biến rỗng vẫn hiện.
3. `default_action = EXCLUDE_ALL` và không có Include nào khớp → loại.
4. Rule Include khớp → lấy `group_label` + `sort_order` của rule **sort_order nhỏ nhất**
   (hoà thì rule khai trước thắng).
5. Phạm vi field = **giao** của phạm vi nguồn (adapter gắn) và **hợp** `only_fields` của mọi
   rule Include khớp. Giao rỗng → `only_fields=[]`, `hide_all=True` (ẩn ở mọi field).

Điều kiện khớp của một rule (`_matches`), theo thứ tự:

| # | Điều kiện | Ghi chú |
|---|---|---|
| 1 | `source_kind` | Rỗng = mọi nguồn |
| 2 | `source_ref` | `*`/rỗng/`AUTO` = **không lọc thêm** (tập vẫn do adapter ngữ cảnh sinh ra; riêng `variable_set` là set gắn với bản ghi); còn lại so với `source_ref` của candidate (so khớp, không phân biệt hoa thường) |
| 3 | `name_prefix` | Nhiều tiền tố phân tách bằng dấu sổ dọc; **phân biệt hoa thường** |
| 4 | `name_regex` | Regex hỏng → coi như **không khớp** (không ném lỗi ra UI) |
| 5 | `category_tag` | So với `category` **hoặc** `group`, không phân biệt hoa thường |
| 6 | `var_type`, `source_type` | So khớp chính xác |
| 7 | `only_fields` (mức rule) | **Chỉ áp khi có `fieldname`**; không có fieldname → bỏ qua điều kiện |
| 8 | `require_value` | Chỉ khớp khi `candidate_has_value` |

Điểm 7 là chỗ hay hiểu sai: autocomplete nạp **một lần cho cả form** và không gửi
`fieldname`. Vì vậy server không dùng `only_fields` để chặn candidate; nó **mang phạm vi field
trên candidate** (`only_fields`, `hide_all`) để **client** lọc theo field đang sửa (mục 7.1).
Kết quả cuối cùng như nhau, nhưng nếu bạn gọi API tay mà không truyền `fieldname`, danh sách
trả về sẽ **không bị lọc theo field**.

`only_fields` **chỉ nhận JSON list** (Small Text chứa ví dụ `["qty","width"]`). Chuỗi không phải
JSON bị controller của `AL Variable Profile` **chặn lưu**; nếu dữ liệu cũ lọt vào thì adapter coi
như `None` = **không giới hạn** (không phải `,`/`|`).

### 6.3 Dedupe (`dedupe_candidates`)

Cùng `name` → xếp hạng theo thứ tự:

1. `has_value = true` thắng `false`;
2. `sort_order` nhỏ hơn;
3. `adapter_order` nhỏ hơn (adapter đăng ký trước);
4. thứ tự xuất hiện.

Sau khi chọn người thắng, phạm vi field được **hợp** từ mọi entry cùng tên:
một entry không giới hạn → không giới hạn; tất cả `hide_all` → `hide_all`; còn lại hợp danh sách.
Mọi ca bỏ đều ghi vào `meta.duplicates` — không bỏ im lặng.

### 6.4 Nhóm (`build_groups`)

Gom theo `group` (label), `sort_order` của nhóm = nhỏ nhất trong nhóm, sắp theo
`(sort_order, label)`. Trong nhóm sắp theo `(sort_order, name)`. `variables` phẳng cũng được sắp
cùng khoá để client cũ đọc được.

### 6.5 References — biến chéo dòng

Sinh trong `build_references`, thứ tự quyết định:

1. Profile có `cross_row` (bảng `AL Variable Cross Row`, `enabled`, có `table_field`) → chỉ sinh
   cho các bảng đó. `include_index_form` bật thì sinh cả dạng `items[0].field`.
2. Không có `cross_row` nhưng có rule Include `slug_reference` → chỉ các bảng rule trỏ tới.
3. Không có cả hai và `default_action = INCLUDE_ALL` → mọi bảng con của doctype cha, mọi field
   vô hướng, tự dò slug (`detect_slug_field`: `custom_slug` → `line_ref` → `*_slug` → `slug`).
4. Còn lại (EXCLUDE_ALL) → không gợi ý.

Rule `slug_reference` Exclude luôn loại bảng tương ứng ở mọi nhánh.

> 🔴 **Chỉ đúng khi profile resolve được.** Nếu `get_formula_context` trả `profile: null` (record
> mới chưa lưu, field trống + `default_profile` trống, profile tắt), hệ thống đi đường legacy và
> **luôn** thêm `items.<slug>.{field}` từ `AL Slug Library` — danh sách slug toàn cục, ⛔ không liên
> quan rule `slug_reference`. Đây là lý do thường gặp nhất khiến "bỏ `slug_reference` mà vẫn thấy
> `items.*`". Xem [al-variable-profile.md](al-variable-profile.md) §7.2.1.

Mỗi field sinh **hai** dạng:

- `items.<slug>.<field>` — dạng engine hiểu ở B3;
- `items[<idx>].<field>` — dạng theo chỉ số, **chỉ để tra theo thứ tự hàng**. ⛔ Không dùng trong
  công thức: `inputs["items"]` là dict khoá theo slug và `_normalize_items_ref` chỉ đổi dạng
  `items.<slug>.<field>`; gõ dạng chỉ số sẽ ra **0** (hoặc bị validate chặn).

Nhãn lấy từ meta (`get_field_label`) + nhãn dòng (`line_name` → `item_code` → slug).

---

## 7. Bước 5 — client nhận và chèn gợi ý

### 7.1 Đường vào Monaco

`formula_setup.js` monkey-patch `formula_builder.formula._ContextBuilder.build` **một lần**
(bọc `_orig`, đánh dấu `__alumglassPatched`; nếu FB chưa load thì poll 100 ms × 50 lần).

Mỗi lần build:

1. Lấy `doctype`, `docname`, `childTable` (`params.childTableField` hoặc `params.child_table`),
   `currentField` (`params.fieldname`).
2. `FormulaContext.getSync(...)` lấy context đã cache.
3. Với từng biến, gọi `_fieldExcluded(v, currentField)`:
   - `v.hide_all` → ẩn;
   - `v.only_fields` là chuỗi JSON → parse (parse lỗi ⇒ **không lọc**);
   - `only_fields` rỗng hoặc không có `fieldname` → **không lọc**;
   - ngược lại: chỉ hiện khi `only_fields` chứa `fieldname`.
4. Đẩy vào `params.liveCtx.variables` với `name/label/value/type/source/source_type/doctype`;
   `doctype` ở đây là **chuỗi tooltip** (`group · value_source`), không phải tên bảng.
5. Nối `ctx.references` vào `params.liveCtx.references`.

### 7.2 Widget dựng context

`AluglassFormulaEditor._buildCtx()` → `_ContextBuilder.build({frm, childTableField, cdn,
liveCtx, fieldname})`. `_scope()` gửi 7 khoá: `current_doctype`, `current_docname`,
`child_table_field`, `row_index`, `line_ref`, `formula_set_code`, `fieldname`.

`current_field` được truyền từ `patchField`/`patchChildField`/`initGridField` — nhờ vậy biến
`only_fields` mới lọc đúng cột đang sửa.

### 7.3 Chèn token

- Biến có `source === "global"` → hiện và chèn dạng `$NAME`; biến `local` → chèn `NAME`.
- Reference chéo dòng → chèn đúng `items.slug.field` hoặc `items[idx].field`.
- Field của dòng hiện tại / doctype cha / bảng anh em → chèn `fieldname` hoặc `table.slug.field`.
- `AL Cost Template`: `cost_template.injectContext(frm)` ghi **toàn bộ** biến context vào
  `window._afbFieldConfig.global_vars` (tạo object **mới**, không sửa tại chỗ — `_cfg()` cache
  theo identity). Vì đường này gán `source: "global"`, mọi biến Cost Template được chèn kèm `$`.

`$` chỉ là cú pháp của autocomplete. `normalize_formula` (`formula_utils/normalize.py` →
`strip_dollar_prefix`) bỏ `$` trước khi engine parse, **giữ nguyên** `$snap.*` và nội dung trong
nháy. Viết tay `VAT_RATE` hay `$VAT_RATE` đều ra cùng kết quả.

### 7.4 Bulk autocomplete không gửi `row_index`

`FormulaContext.fetch` chỉ gửi `doctype`, `docname`, `child_table`. Không có `fieldname`,
không có `row_index`. Hệ quả (đúng như mã, không phải suy đoán):

- lọc theo field là việc của **client** (mục 7.1) — server trả phạm vi trên từng biến;
- adapter `cost_template_line` **không cắt** dòng phía sau (mục 5.2);
- binding scope dòng con chỉ resolve được khi `CatalogContext` có `row_index` — đường này không có.

Hai API `preview_variable_catalog` và `explain_variable` **có** nhận `row_index`; dùng chúng khi
cần kiểm tra đúng ngữ cảnh một dòng.

---

## 8. Bước 6 — lưu công thức

**Ai gọi:** người dùng bấm Lưu trên form; Frappe ghi nguyên văn chuỗi vào field Small Text/JSON.
**Vào/ra:** vào là chuỗi trong editor; ra là giá trị trong DB, không qua xử lý nào của AlumGlass.

Người dùng gõ gì, lưu nguyên văn nấy. **Không chuẩn hoá lúc lưu.**

| Nơi lưu | Field | Kiểu | Ai đọc lúc chạy |
|---|---|---|---|
| Dòng vật tư BOM | `AL Bom Item.width`, `.height`, `.qty`, `.show_condition`, `.item_condition_formula` | Small Text | B3 theo `formula_fieldnames` của Bom Set; mặc định `width/height/qty/show_condition/item_condition_formula/rule_input_expr` |
| Dòng phụ kiện | `AL Accessory Item.qty_formula` | Small Text | B2 đưa vào `bom_items`, B3 dựng `{slug}__qty` |
| Dòng giá thành | `AL Cost Template Item.calc_formula` | Small Text | B6 dựng `global_formulas` theo `line_code` |
| Biến phụ của pattern | `AL Bom Item.input_vars` (JSON object), `AL Quantity Calc Method.input_vars` (JSON list tên) | JSON | B3 inject `{slug}__{var}` và truyền vào `lookup_calc_pattern` |
| Biến người dùng nhập | `Quotation Item.al_bom_vars` (JSON) | JSON | B1 bước 1.1/1.5 |
| Tham chiếu chéo dòng (chọn mã theo rule) | `AL Bom Item.rule_input_expr` | Small Text | B2 `_resolve_rule_input_for_item` — **không** qua FormulaEngine |

`rule_input_expr` **không phải** biểu thức toán học: engine chỉ `re.match` mẫu
`items.<slug>.<field>` ở **đầu chuỗi** rồi tra `row_literals`/`glass_data` của dòng đích.
Không khớp → fallback `glass_thick`/`glass_type` của **chính dòng đó**.

Chuẩn hoá xảy ra ở ba chỗ, sau khi đã lưu:

| Chỗ | Làm gì |
|---|---|
| B3 `_normalize_items_ref` | `items.slug.field` → `slug__field` (namespace phẳng), dùng `formula_builder.table_formula_builder.normalize_global`, lỗi thì fallback regex |
| FormulaEngine `normalize_formula` | Gỡ HTML entity, bỏ `$`, `%` → `/100`, `<>` → `!=`, `=` → `==`, chuẩn hoá tên hàm |
| Validate `normalize_cross_row` | Cùng phép đổi của B3, để validator thấy đúng tên phẳng |

Lưu ý: **B6 không chạy `_normalize_items_ref`.** Công thức Cost Template nhận thẳng chuỗi đã
lưu. Muốn dùng giá trị một dòng vật tư ở B6, dùng tên phẳng `{slug}__{field}` (đã có trong
`inputs` sau B4), **không** viết `items.slug.field`.

---

## 9. Bước 7 — validate

Có **ba** lớp kiểm, không lớp nào thay lớp nào.

### 9.1 Client — chỉ có ở `AL Cost Template`

**Ai gọi:** `onchange calc_formula` của dòng (debounce 400 ms) và event `validate` của form.

**Hàm/tệp:** `public/js/cost_template.js`, `doctype/al_cost_template/al_cost_template.js`.

1. `fetchValidationContext(frm)` → RPC `get_formula_context(..., include_all_sources=1)`,
   cache theo `docname`, **không TTL**.
2. `validate_formula(formula, {known_names, line_codes})`:
   - rỗng → lỗi; ngoặc không cân bằng → lỗi; ký tự lạ → lỗi;
   - tách identifier (bỏ chuỗi trong nháy, bỏ phần mũ `1e5`); hàm phải nằm trong
     `_ALLOWED_FUNCTIONS`; biến phải nằm trong `known_names` ∪ `line_code` các dòng **trước**;
   - `known_names = null` (context chưa load) → **bỏ qua** kiểm biến (fail-open).
3. Tuỳ chọn: gọi `formula_builder.api.formula_builder.validate_formula` với `local_vars`;
   lỗi hạ tầng → coi như hợp lệ (`fail-open`).
4. Form `validate` gom lỗi mọi dòng, `frappe.validated = false` → chặn lưu.

### 9.2 Server — `AL Bom Set`

**Ai gọi:** `ALBomSet.validate` → `_validate_child_formulas`.

1. `slugs` = slug các dòng.
2. `build_known_names("AL Bom Set", name, cross_row_slugs=slugs,
   cross_row_fields=_cross_row_known_fields())`.
3. `check_formula_fields(item, FORMULA_FIELDS, ...)` cho `width/height/qty/show_condition`;
   thêm `item_condition_formula` khi `item_selection_mode == "Formula"`.
4. Có lỗi → `frappe.throw` (chặn cứng).

`_cross_row_known_fields()` (bản vá **chưa commit**) trả **superset**:

| Nguồn | Field |
|---|---|
| `FORMULA_FIELDS` | `width`, `height`, `qty`, `show_condition` |
| `ENGINE_SYNTHETIC_FIELDS` (hợp đồng engine, luôn tồn tại) | `unit_qty`, `total_qty`, `line_total` |
| Row literal đang bật (`AL Variable Settings.row_literals`) | `unit_price`, `weight_per_unit`, `glass_thick`, `glass_type`, `scrap_pct`, `calc_pattern`, … (đọc từ dữ liệu, không hardcode) |

Đây chỉ là **universe hợp lệ** cho `items.<slug>.<field>`. Danh sách field **bị kiểm** vẫn là
`FORMULA_FIELDS` (+ condition). Superset **không** làm field lạ chạy được lúc runtime: field
engine không inject vẫn ra 0.

### 9.3 Server — `AL Cost Template`

`ALCostTemplate.validate` → `_build_known_names` (`include_all_sources=True`,
`fieldname="calc_formula"`) → `FormulaValidator` AST. Thiếu công thức hoặc ngoặc lệch →
`frappe.throw`; biến/hàm lạ → **`frappe.msgprint` cảnh báo cam**, không chặn.

### 9.4 `rule_input_expr` — chỉ cảnh báo

`ALBomSet._warn_rule_input_expr` gọi `validate_rule_input_expr(expr, slugs, known_fields)`.
`known_fields` lấy từ `get_row_literal_names()`; rỗng → chỉ kiểm slug. Có vấn đề →
`frappe.msgprint` cam, **không throw** (nhiều Bom Set đang chạy ở trạng thái này).

### 9.5 Gợi ý và hợp lệ là hai tập khác nhau

| Tập | Nguồn | Dùng cho |
|---|---|---|
| Gợi ý | Catalog + profile (đã lọc) | Autocomplete |
| Hợp lệ | Legacy đầy đủ (`include_all_sources=True`) + `{slug}__{field}` cross-row | Validate |

Vì vậy: biến **không** có trong gợi ý vẫn lưu được nếu engine resolve được nó; biến **có**
trong gợi ý vẫn có thể ra 0 lúc chạy. Bật profile không bao giờ làm công thức cũ bị chặn.

---

## 10. Bước 8 — runtime B0–B7

**Ai gọi:** `alumglass.api.calculate_bom(quotation_item_name)` → `BomOrchestrator(qi).run()`.

### B0 — Version pinning

`b0_version_pinning`: đọc `Quotation Item`, lấy `al_bom_version` nếu có; không thì
`AL BOM.current_version`; không nữa thì version mới nhất (`creation DESC`) và **không tạo**
version mới. Không có version nào → `frappe.throw` kèm hướng dẫn tạo version.

### B1 — Gom inputs (thứ tự GHI, ghi sau thắng)

`b1_gather_inputs`, làm đúng thứ tự dưới đây:

| Bước | Lớp | Nguồn | Ghi đè lên |
|---|---|---|---|
| 1.1 | `extra_vars` | `al_bom_vars.extra_vars` | (nền) |
| 1.2 | Global Variable | `Formula Global Variable` đang bật, qua cache Redis 60 s | 1.1 |
| 1.4 | FB binding | `get_live_context` scope `AL Bom Set` (không có Bom Set → `Quotation Item`); chỉ merge scalar, bỏ `None`/dict/list/chuỗi rỗng | 1.2 |
| 1.3 | System Variable (fill-missing) | `AL Variable Library is_system=1` + `source_doctype.source_field`, override child `AL Profile System.system_variables`, rồi `default_value`, rồi `AL Rule` CONSTANT | **chỉ biến chưa có** |
| 1.4b | Profile System child | `AL Profile System.system_variables` (bật, có giá trị) | 1.4 |
| 1.5 | User input | `al_bom_vars.extra_vars` + mọi key top-level (trừ `extra_vars`, `accessory_set`, `glass_master`) | **mạnh nhất** |
| 1.5c | Resolve lại system var | Chỉ khi có `_profile_system`: chạy `_resolve_system_variables()` đầy đủ rồi **áp lại snapshot user** | 1.4/1.4b (user vẫn thắng) |
| 1.6 | User var default | `AL Variable Library is_system=0` `default_value`, chỉ biến chưa có | — |
| 1.7 | Chuẩn hoá % | `var_type == "Percent"` hoặc hậu tố tên phần trăm: `abs(value) > 1` → chia 100; `= 1` → giữ nguyên 1 (100%) + **cảnh báo** | — |

`_profile_child_vars` được capture **trực tiếp** từ child row (không đọc lại `inputs`) vì ở thời
điểm đó `inputs` có thể đang giữ giá trị FB.

Cảnh báo và lỗi B1 đi vào `self.bom_engine_errors`.

### B2 — Prefetch master data

`b2_prefetch_master_data`:

1. Đọc `bom_version.bom_set_snapshot` (không có → `throw`).
2. `_load_accessories(bom_set)` — nạp `AL Accessory Set` (override `al_bom_vars.accessory_set`
   hoặc `default_accessory_set`) thành dòng BOM với `qty_formula`, bucket mặc định `VL_PK`.
   Phải chạy **trước** vòng gom mã để giá/khối lượng phụ kiện vào batch.
3. Gom mã: `item_code`, `price_base_item`, `default_glass_master`, mã kính override
   (`glass_master_map`, `glass_master`), rule code (chế độ `Rule`).
4. Batch query: `Item.weight_per_unit`; `Item Price` (thử composite qua FB, không có thì resolver
   cũ); `AL Glass Master` (`total_thick_mm`, `glass_type`, `max_area_m2`); `AL Material Category`
   (`default_scrap_pct`, `has_weight`); `AL Variable Dimension Mapping`.
5. Resolve rule (`_resolve_rule_input_for_item`) → `item_code` thật cho dòng chọn theo Rule.
6. Build `self.row_literals[slug]` = `{weight_per_unit, unit_price, calc_pattern, glass_thick,
   glass_type, item_code, scrap_pct, has_weight, color, supplier_location, install_position,
   cut_angle, note}`.
7. Lưu `formula_fieldnames` từ `AL Bom Set` (JSON) — dùng ở B3.

### B3 — Dựng danh sách công thức

`b3_build_formulas`:

- Với mỗi dòng: inject row literal vào `inputs` dưới dạng `{slug}__{key}` (6 khoá chính);
  đặt mặc định 0 cho `width/height/qty/calc_pattern/weight_per_unit/unit_price/scrap_pct`.
- Pattern có `input_vars`: resolve theo thứ tự `line.input_vars` → input toàn cục →
  `row_literals` → 0, inject `{slug}__{var}` và truyền vào `lookup_calc_pattern` bằng dict
  positional (vì `normalize_formula` đổi `=` thành `==`, keyword args không dùng được).
- Mỗi field công thức không rỗng → thêm formula `{slug}__{field}` với chuỗi đã chuẩn hoá
  cross-row (`_normalize_items_ref`).
- Luôn thêm 3 formula tổng hợp:

| Tên | Công thức |
|---|---|
| `{slug}__unit_qty` | `lookup_calc_pattern({slug}__calc_pattern, {slug}__width, {slug}__height, {slug}__weight_per_unit[, {...}])` |
| `{slug}__total_qty` | `{slug}__unit_qty * {slug}__qty`; bật `apply_scrap_pct` thì nhân thêm `(1 + {slug}__scrap_pct/100)` |
| `{slug}__line_total` | `{slug}__total_qty * {slug}__unit_price` |

- Cuối cùng dựng `inputs["items"]` = dict lồng `{slug: {field: value}}` (phục vụ dạng
  `items.X.Y` nếu còn chỗ đọc trực tiếp).

### B4 — Tính dòng vật tư

`b4_calculate_bom_items`:

- Engine cache theo **nội dung công thức** (`BOM_ENGINE_CACHE`, `make_key`), không theo sản phẩm.
- `FormulaEngine(formulas, safe_funcs=_engine_safe_funcs(), on_error="default",
  default_value=0, deterministic=True)`.
- `engine.calculate(dict(self.inputs))` → merge kết quả ngược vào `inputs`; `engine.last_errors`
  **merge** vào `bom_engine_errors`.
- `_validate_glass_max_area`: diện tích `{slug}__unit_qty` vượt `max_area_m2` → **cảnh báo**,
  không throw.
- Build `bom_result` từng dòng: `width/height/qty/unit_qty/total_qty/unit_price/line_total`,
  `cost_bucket`, `unit`, `weight_per_unit`, `color`, `trace` (thay biến bằng giá trị).

`safe_funcs` = bộ hàm nền của FB + `lookup_rule`, `lookup_calc_pattern`, `roundup`. Hàm ngoài
whitelist → lỗi engine → formula đó nhận `default_value` = 0.

Biên dịch biểu thức đi qua `formula_builder/security/safe_eval.py::compile_expression`: dựng AST
rồi `_validate_ast` chặn `import`, `lambda`, thuộc tính `__dunder__`, `getattr`, và chạy với
`__builtins__` rỗng. Đây là chốt chặn RCE của cả B4 lẫn B6 — mở rộng `safe_funcs` không nới
lỏng chốt này.

### B5 — Gom bucket

`b5_aggregate_cost_buckets`:

1. `_resolve_cost_buckets_via_fb`: bucket có `source_type == "aggregate_from_items"` **và**
   `source_config` hợp lệ → resolve qua `resolve_all_bindings_batch` (đọc `bom_result`).
2. Bucket còn lại → cộng `line_total` theo `cost_bucket` của từng dòng.
3. Bucket khai `source_type` khác mà engine chưa hỗ trợ → **cảnh báo** rồi vẫn cộng Python.

Bucket không có dòng nào mang mã đó → **không có khoá** trong `self.buckets`.

### B6 — Tính cost template

`b6_calculate_cost_template`:

1. Snapshot: `al_bom_vars._cost_template` (dựng trực tiếp từ doc) → `bom_version.cost_template_snapshot`.
   Không có → dừng bước này.
2. `global_formulas` = mọi dòng có `calc_formula`, tên formula là `line_code`.
3. `extra_context = dict(inputs); extra_context.update(buckets)`.
4. Quét mã bucket được tham chiếu trong công thức; mã **chưa có** trong context → gán **0.0**.
5. Engine: `FormulaEngine(formulas=global_formulas, safe_funcs=..., on_error="default",
   default_value=0)`; context tính = `{**extra_context, **self.inputs}`.
6. `cost_result` = toàn bộ kết quả; `gia_vat` lấy theo dòng `is_final_price=1`, không có cờ thì
   fallback `GIA_VAT`.
7. Trace từng dòng lưu vào `cost_template_trace[line_code]`.

### B7 — Ghi kết quả

`b7_save_results`: một JSON duy nhất `{buckets, cost_template, cost_template_trace, lines,
gia_vat, gia_ban, errors}` → `frappe.db.set_value("Quotation Item", name, {al_gia_vat, al_gia_ban,
al_bom_result, rate})` → tính lại tổng Quotation cha bằng `set_value(update_modified=False)`
(**không** `save()` cha, tránh `TimestampMismatchError`) → **một** `commit`.

---

## 11. Bước 9 — Formula Builder resolve

Đây là lớp dùng chung cho cả gợi ý (Bước 3, adapter `fvb_scope`) và runtime (B1 bước 1.4).

### 11.1 `get_live_context(scope_context_json)`

**Vào:** JSON scope `{current_doctype, current_docname, fieldname | current_field}`.
**Ra:** `{success, variables, crossTables, objects, json_str}`.

Thứ tự:

1. `_scope` parse JSON; `_assert_read_perm` kiểm quyền đọc doctype/docname.
2. `fieldname` lấy từ `fieldname` hoặc `current_field`.
3. `get_scope_bindings(doctype, field, order_by="resolve_priority asc")` — luật scope:
   - cả hai field rỗng → **global**, áp mọi nơi;
   - `applies_to_doctype == doctype`, field rỗng → áp mọi field của doctype;
   - `applies_to_doctype == doctype`, field khớp → áp đúng field;
   - caller không truyền field → binding có field vẫn lọt (vì "không có field để so").
4. `doc = frappe.get_cached_doc(doctype, docname)` nếu docname không phải `new-…`.
5. `resolve_bindings_with_deps(bindings, doc)` — topo theo `source_config.dependencies`;
   có vòng → log rồi fallback thứ tự `resolve_priority`; handler thiếu/lỗi → `default_value`.
6. Dựng `variables`: `Object` → chuỗi `[Object: N fields]`; còn lại giữ giá trị thật.
   `is_global` quyết `source` = `global`/`local`.
7. Thêm field vô hướng của chính document với `source="field"`, `source_type="doctype_field"`.
8. Thêm `crossTables` từ meta bảng con (kèm `_rows` cho `line_ref`).
9. Thêm `Formula Global Variable` (`value_source=CONSTANT`) nếu chưa có tên.
10. `_dedupe_live_variables`: cùng tên → entry **có giá trị** thắng; hoà → giữ entry đầu;
    phạm vi field của các entry trùng được **hợp** và gắn lại dưới `only_fields` +
    `applies_to_field`; nguồn bị bỏ ghi vào `duplicate_sources`.

### 11.2 Batch resolver

`BatchBindingResolver.resolve_all_batch(bindings, doc)`:

1. Tách batchable (handler có `@batchable`) và không.
2. Gom nhóm theo `(source_type, fingerprint)` — fingerprint do handler khai, ví dụ
   `linked_doctype_field` gom theo `target_doctype` (không theo từng field) để N biến cùng
   doctype chỉ còn 1 truy vấn.
3. Mỗi nhóm gọi `resolve_batch` nếu handler có, không thì gọi lẻ.
4. Gộp kết quả; không batchable thì rơi về `resolve_bindings_with_deps`.

Cache: `frappe.local` theo request (`_request_cache`); `cache_ttl > 0` mới dùng Redis.

### 11.3 Hai mươi mốt `source_type`

| Nhóm | Tên |
|---|---|
| Lõi (13) | `constant`, `linked_doctype_field`, `whole_doctype`, `child_table_aggregate`, `global_default`, `session_variable`, `doctype_query`, `custom_function`, `dynamic_link`, `computed`, `pipeline`, `conditional`, `fallback_chain` |
| Bảng/tra cứu (6) | `matrix_lookup`, `composite_key_lookup`, `range_lookup`, `child_table_lookup`, `reuse_formula_result`, `aggregate_from_items` |
| AlumGlass (2) | `aluminum_price_composite`, `glass_master_data` |

Đăng ký ở `formula_builder/api/data_source_registry.py` (13 lõi + 6 bảng) và
`alumglass/fb_handlers.py` (2 hàm AlumGlass). Thêm source type mới phải đăng ký qua
`source_type_registry.register_source` để có cả metadata/config schema — xem
`formula_builder/docs/fb_source_type_contract.md`.

### 11.4 Chuẩn hoá công thức khi engine parse

`normalize_formula` (dùng bởi parser và `FormulaValidator`):

- gỡ HTML entity (`&gt;` → `>` …) **trước** mọi phép khác;
- bỏ `$` của biến (`strip_dollar_prefix`), giữ `$snap.*` và chuỗi trong nháy;
- `%` → `(\1/100)`; `<>` → `!=`; mọi `=` đơn → `==`;
- chuẩn hoá tên hàm theo canonical (không phân biệt hoa thường), `and/or/not` → `and_/or_/not_`
  khi gọi hàm.

### 11.5 Snapshot

`FormulaEngine` có `snapshot()`, `snapshot_with_trace()`, `snapshot_revise()`. Đây là cơ chế
đóng băng kết quả/dấu vết của một lần tính, **không** phải nguồn biến. Tài liệu riêng:
`formula_builder/docs/Snapshot_Lifecycle_Full_Example.md`.

---

## 12. Bước 10 — Bảng provenance giá trị

"Runtime lấy từ đâu" — trả lời cho từng nguồn. Cột cuối là chỗ hay hỏi nhất.

| Nguồn | Runtime lấy từ đâu | Khi nào có | Khi nào 0/None | Có trong gợi ý? |
|---|---|---|---|---|
| **Cost Bucket** | B5 `self.buckets` → B6 `extra_context` | Có ít nhất 1 dòng mang `cost_bucket` đó, hoặc bucket cấu hình `aggregate_from_items` | B4 **chưa có** (bucket chỉ sinh sau B4); B6 mã được tham chiếu nhưng thiếu → gán 0.0 | Có (luôn hiện `—`) |
| **System Variable** | B1: FB → Library (`source_doctype.field`) → child profile → `default_value` → `AL Rule` CONSTANT | Có source record, hoặc có default, hoặc có rule CONSTANT | Không nguồn nào → **không có khoá** → NameError → formula nhận 0 | Có; tooltip nói nguồn |
| **User Variable** | B1: `al_bom_vars` (top-level + `extra_vars`) → Library `default_value` | Người dùng nhập, hoặc có default | Không nhập, không default → NameError → 0 | Có (`—`) |
| **Global Variable** | B1 bước 1.2 (mọi record đang bật) | Record `is_active=1` | Bị lớp sau ghi đè nếu trùng tên; record tắt → không có | Có (kèm giá trị) |
| **Formula Variable Binding** | B1 `_resolve_fb_context` scope `AL Bom Set` | Handler resolve được giá trị khác `None` | Handler lỗi/`None` → `default_value`; nếu vẫn `None` → **không merge** vào inputs | Có (adapter `fvb_scope`) |
| **Row Literal** | B2 dựng `row_literals[slug]` → B3 inject `{slug}__{field}` | Luôn có khoá cho 6 field chính (mặc định 0) | `unit_price` 0 khi không có Item Price/composite key; `weight_per_unit` 0 khi Item không khai; `glass_thick` 0 khi chưa chọn kính | Có; giá trị đọc từ dòng hiện tại nếu có `row_index` |
| **Common Var** | B1 `inputs[name]` (không có tiền tố slug) | Người dùng nhập hoặc Library default | Như user var → NameError → 0 | Có (`—`) |
| **Slug cross-row** | B3 `items.slug.field` → `slug__field` | Slug tồn tại **và** field đó được engine tạo cho dòng đích | Slug sai/không có dòng → không có khoá → 0 | Có (references) |
| **Cost Template line** | B6 DAG theo `line_code` | Dòng có `calc_formula` | Công thức tham chiếu vòng → lỗi engine → 0; dòng không có công thức → không có khoá | Có (`—`) |
| **Doctype field** | **Không tự động vào runtime** | Chỉ khi đồng thời là row literal, binding, hoặc `{slug}__{field}` | Luôn 0 nếu chỉ là field thường | Có (adapter `doctype_field`) |

Câu chốt của bảng: **"có trong gợi ý" không suy ra "có trong runtime"**. Suy ra được chiều
ngược lại: nếu engine resolve được một tên, validate cũng chấp nhận tên đó (universe validate
là bản đầy đủ), kể cả khi profile không gợi ý.

---

## 13. Ví dụ trace số

Toàn bộ số dưới đây là **minh hoạ** để nhìn đường đi, không phải dữ liệu production. Đơn vị:
mm, m², VND.

### 13.1 Công thức trong `AL Bom Item.qty` — đúng dạng nhưng sai chỗ đặt

Giả sử dòng kính có slug `kinh_tren`, và công thức lưu là:

```
items.kinh_tren.width * items.kinh_tren.height / 1000000 * VL_KINH
```

Dữ liệu: `kinh_tren.width = 1200`, `kinh_tren.height = 2100`.

| Bước | Phép tính | Kết quả |
|---|---|---|
| B3 chuẩn hoá | `items.kinh_tren.width` → `kinh_tren__width` | `kinh_tren__width * kinh_tren__height / 1000000 * VL_KINH` |
| B3 inject literal | `kinh_tren__width = 1200`, `kinh_tren__height = 2100` | — |
| B4 thay số | `1200 * 2100 / 1000000 * VL_KINH` | `2.52 * VL_KINH` |
| B4 tìm `VL_KINH` | `VL_KINH` là **mã Cost Bucket**, chỉ sinh ở **B5** | **không có trong inputs** |
| B4 kết quả | NameError → `on_error="default"`, `default_value=0` | **0** |

Đây là ca 14.2: gợi ý có `VL_KINH`, validate có `VL_KINH` (nó nằm trong universe legacy), nhưng
engine chạy B4 **trước** khi bucket tồn tại. Cả biểu thức về 0, không chỉ riêng một thừa số.

**Bản đúng** — dùng đơn giá của dòng, không dùng tổng bucket:

```
items.kinh_tren.width * items.kinh_tren.height / 1000000 * kinh_tren__unit_price
```

`kinh_tren__unit_price = 420000` → `2.52 * 420000 = 1,058,400` VND.

Nếu cố tình viết bản sai và `VL_KINH` **đã có** giá trị từ một lần chạy trước
(ví dụ 1,058,400), công thức ra `2.52 * 1,058,400 = 2,667,168` — **ra số nhưng sai nghĩa**
(nhân diện tích với tổng tiền). Con số không báo lỗi là loại lỗi khó thấy nhất.

### 13.2 Công thức Cost Template dùng `TONG_VL` và `TONG_M2`

Dòng chuẩn (seed demo):

```
TONG_VL    = VL_NHOM + VL_KINH + VL_VTP + VL_PK
TONG_M2    = (W_mm/1000) * (H_mm/1000)
NC_SX      = NC_SX_PCT * TONG_VL
GIA_THANH  = TONG_VL + TONG_NC + TONG_OH
GIA_BAN    = GIA_THANH + PROFIT
DON_GIA_M2 = safe_div(GIA_BAN, TONG_M2, 0)
```

Giả định đầu vào:

| Biến | Giá trị | Đến từ |
|---|---|---|
| `VL_NHOM` | 3,850,000 | B5, cộng `line_total` các dòng bucket `VL_NHOM` |
| `VL_KINH` | 1,058,400 | B5, dòng kính ở 13.1 (bản đúng) |
| `VL_VTP` | 240,000 | B5 |
| `VL_PK` | 1,640,000 | B5 (phụ kiện `_load_accessories`) |
| `W_mm`, `H_mm` | 2400, 2600 | user nhập ở `al_bom_vars` |
| `NC_SX_PCT` | 8 (nhập phần trăm nguyên) | user nhập → B1.7 chia 100 → 0.08 |
| `NC_LD_PCT` | 12 → 0.12 | user nhập |
| `OH_VC_PCT`, `OH_QLY_PCT` | 3 → 0.03 mỗi biến | user nhập |
| `PROFIT_MARGIN` | 16 → 0.16 | user nhập |
| `VAT_RATE` | 10 → 0.10 | user nhập hoặc Global Variable |
| `RULE-HEIGHT-MULT` | 1.0 | giả định, để ví dụ không phụ thuộc rule |

Trace:

| Dòng | Phép tính | Kết quả |
|---|---|---|
| `TONG_VL` | 3,850,000 + 1,058,400 + 240,000 + 1,640,000 | **6,788,400** |
| `TONG_NC` | `NC_SX = 0.08 × 6,788,400 = 543,072`; `NC_LD = 0.12 × 6,788,400 × 1.0 = 814,608` | **1,357,680** |
| `TONG_OH` | `OH_VC = 203,652`; `OH_QLY = 0.03 × (6,788,400 + 1,357,680) = 244,382.4` | **448,034.4** |
| `GIA_THANH` | 6,788,400 + 1,357,680 + 448,034.4 | **8,594,114.4** |
| `PROFIT` | 0.16 × 8,594,114.4 | **1,375,058.3** |
| `GIA_BAN` | 8,594,114.4 + 1,375,058.3 | **9,969,172.7** |
| `TONG_M2` | (2400/1000) × (2600/1000) | **6.24** |
| `DON_GIA_M2` | `safe_div(9,969,172.7, 6.24, 0)` | **1,597,623.8** |
| `VAT` | 0.10 × 9,969,172.7 | **996,917.3** |
| `GIA_VAT` | 9,969,172.7 + 996,917.3 | **10,966,090.0** |

Đường đi của `VL_KINH` trong ví dụ này là **một chiều**: B4 tính `line_total` dòng kính →
B5 cộng vào `VL_KINH` → B6 đọc `VL_KINH`. Không có đường ngược lại. Đó là lý do 13.1 sai.

---

## 14. Vì sao gợi ý thấy mà runtime ra 0/None — 8 nguyên nhân

Mỗi mục: dấu hiệu → nguyên nhân trong mã → cách kiểm.

### 14.1 Biến chỉ là "field của chứng từ"

- **Dấu hiệu:** gợi ý có `item_code`, `customer`, `company`… nhưng công thức ra 0.
- **Nguyên nhân:** adapter `doctype_field` chỉ **liệt kê** field vô hướng. Engine chỉ đưa vào
  `inputs` thứ nó chủ động nạp: `{slug}__{field}` (row literal), binding, biến người dùng.
- **Kiểm:** tên biến có trong `al_bom_result.lines[].trace` không? Nếu không, engine chưa từng
  có khoá đó. Dùng `explain_variable` xem `source_kind` — nếu là `doctype_field` thì đúng ca này.

### 14.2 Dùng Cost Bucket ở B4

- **Dấu hiệu:** công thức trong `AL Bom Item` tham chiếu `VL_*`, `TONG_*` → cả dòng 0.
- **Nguyên nhân:** bucket sinh ở B5, B4 chạy trước. Không có khoá → NameError → `default_value=0`
  cho **toàn biểu thức**.
- **Kiểm:** `al_bom_result.errors.bom_items` có khoá dạng `{slug}__{field}`; sửa bằng cách
  chuyển phép tính sang Cost Template (B6) hoặc dùng `{slug}__unit_price`.

### 14.3 Cross-row sai slug hoặc sai field

- **Dấu hiệu:** `items.kinh_tren.width` ra 0; các dòng khác vẫn đúng.
- **Nguyên nhân:** chuẩn hoá thành `kinh_tren__width`; nếu không có dòng slug đó, hoặc field đó
  không được engine tạo cho dòng đích, khoá không tồn tại → 0. Với `rule_input_expr`, engine
  còn chỉ `re.match` **ở đầu chuỗi** — thêm chữ phía trước là fallback âm thầm.
- **Kiểm:** `build_known_names` + `validate_rule_input_expr` cảnh báo slug/field; xem
  `AL Slug Library` và slug thật trên dòng; kiểm `al_bom_result.lines` có dòng đích.

### 14.4 Row literal thiếu dữ liệu nền

- **Dấu hiệu:** `line_total` đúng số lượng nhưng tiền 0; `weight_per_unit` 0.
- **Nguyên nhân:** `unit_price` lấy từ `Item Price` theo `price_base_item` (ưu tiên) hoặc
  `item_code`; không có dòng giá khớp composite key → 0. `weight_per_unit` = 0 khi Item không
  khai. `glass_thick` = 0 khi chưa chọn glass master (B2 chỉ ghi 0, không throw).
- **Kiểm:** `al_bom_result.lines[]` xem `unit_price`, `weight_per_unit`; đối chiếu `Item Price`
  theo đúng bộ dimension; `errors.bom_items` có cảnh báo tra giá.

### 14.5 User/Common var không nhập và không có default

- **Dấu hiệu:** `NC_LD = 0` dù `NC_LD_PCT` đúng.
- **Nguyên nhân:** B1.6 chỉ điền `default_value` khi có; không có → không khoá → NameError → 0
  (hoặc cả công thức 0 nếu biến nằm trong cùng biểu thức).
- **Kiểm:** đọc `Quotation Item.al_bom_vars`; xem `AL Variable Library.default_value` của biến;
  `errors.cost_template` chỉ ra line_code lỗi.

### 14.6 Phần trăm: 8, 0.08 và 1

- **Dấu hiệu:** chi phí nhân công nhỏ hơn 100 lần, hoặc lớn hơn 100 lần.
- **Nguyên nhân:** B1.7 chia 100 khi `abs(value) > 1`. Nhập `8` → 0.08 (đúng). Nhập `0.08` →
  giữ nguyên (đúng). Nhập `1` → **giữ nguyên 1 = 100%**, kèm cảnh báo `phan_tram_mo_ho_bang_1`.
- **Kiểm:** xem cảnh báo trong `al_bom_result.errors.cost_template`; đối chiếu cách nhập ở
  dialog Tham số BOM.

### 14.7 Cost Template: dòng sau, tham chiếu vòng, bucket rỗng

- **Dấu hiệu:** một `line_code` ra 0 trong khi các dòng trước đúng.
- **Nguyên nhân:** (a) công thức tham chiếu dòng **sau** trong điều kiện bị cắt theo `row_index`
  (adapter gợi ý), nhưng runtime vẫn tính được nếu DAG không vòng; (b) tham chiếu vòng thật →
  topo lỗi → engine trả 0; (c) mã bucket được tham chiếu nhưng **không dòng nào** mang bucket đó
  → B6 gán 0.0; (d) bucket khai `source_type` engine chưa hỗ trợ → cảnh báo + cộng Python.
- **Kiểm:** `al_bom_result.cost_template` xem từng `line_code`; `al_bom_result.buckets` xem
  bucket có khoá không; `errors.cost_template`.

### 14.8 Cache client còn dữ liệu cũ

- **Dấu hiệu:** vừa sửa binding/profile/field mà gợi ý vẫn như cũ; mở bản ghi khác vẫn thấy biến
  của bản ghi trước.
- **Nguyên nhân:** `FormulaContext` 5 phút theo `doctype::docname::child`; `FormulaFields` 60 s;
  `CostTemplate._contextCache` theo docname **không TTL**. Không nơi nào gọi `invalidate`.
- **Kiểm:** tải lại trang (xoá cache JS); so với `explain_variable` gọi tay (server không cache
  catalog). Mục 15 có bảng đầy đủ.

---

## 15. Cache và invalidation

### 15.1 Bảng cache

| Cache | Ở đâu | Khoá | TTL | Ai xoá |
|---|---|---|---|---|
| `alumglass.FormulaContext._cache` | trình duyệt | `doctype::docname::childTable` | **5 phút** | `invalidate(doctype)` — **không nơi nào gọi** |
| `alumglass.FormulaFields._cache` | trình duyệt | `doctype` | **60 giây** | `invalidate(doctype)` — không nơi nào gọi |
| `alumglass.CostTemplate._contextCache` | trình duyệt | `docname` | **không có TTL** | `CostTemplate.invalidate(docname)` — không nơi nào gọi |
| `CostTemplate._validationCache` | trình duyệt | `docname` | **không có TTL** | như trên |
| `Formula Global Variable` | Redis (`formula_builder`) | một khoá chung | **60 giây** | `on_update`/`on_trash` của DocType; `frappe.db.set_value` **không** kích hoạt |
| `frappe.get_cached_doc` | server (Frappe document cache) | `(doctype, name)` | theo Frappe | Frappe xoá khi document lưu qua ORM; ghi thẳng `db.set_value` không xoá |
| Catalog (`get_variable_catalog`) | **không cache** | — | — | Mỗi lần gọi đều query DB |
| `BatchBindingResolver._request_cache` | `frappe.local` | theo request | hết request | tự hết |
| Engine DAG (`BOM_ENGINE_CACHE`, `COST_ENGINE_CACHE`) | tiến trình | theo nội dung công thức | theo cache engine | đổi công thức → khoá đổi |

### 15.2 Hệ quả vận hành

- Sửa `AL Variable Profile` / rule / `AL Variable Settings` → người dùng đang mở form **có thể
  phải chờ tới 5 phút** hoặc tải lại trang. Server đã trả dữ liệu mới ngay.
- Sửa `AL Formula Field` (thêm field công thức) → tối đa 60 giây mới thấy editor ở form mới.
- Sửa giá trị hằng số `Formula Global Variable` bằng API/patch → tối đa 60 giây (Redis). Sửa qua
  form thì có hiệu lực ngay sau commit.
- Sửa `AL Cost Template` rồi mở lại cùng bản ghi trong **cùng phiên** → context cũ vẫn còn (không
  TTL). Tải lại trang là hết.
- `invalidate` đã được viết nhưng **chưa nối vào nơi nào**. Nếu cần "sửa là thấy ngay", đó là
  việc phải làm thêm — tài liệu này không hứa là đã có.

---

## 16. Phụ lục

### A. File và hàm

| Việc | Tệp | Hàm |
|---|---|---|
| Bắt `form-refresh`, cache context, patch `_ContextBuilder` | `alumglass/public/js/formula_setup.js` | `FormulaFields.init/fetch/apply`, `FormulaContext.fetch/getSync/invalidate`, `_patchContextBuilder`, `_fieldExcluded` |
| Validate client + inject `_afbFieldConfig` | `alumglass/public/js/cost_template.js` | `validate_formula`, `_find_unknown_identifiers`, `fetchContext`, `fetchValidationContext`, `validateRow`, `injectContext`, `invalidate` |
| API context (2 đường) | `alumglass/api/__init__.py` | `get_formula_context`, `_get_catalog_context`, `_get_live_context_vars`, `_resolve_doc_values`, `_normalize_catalog_variable`, `_binding_scope_fields`, `_assert_formula_context_doctype` |
| Nhân catalog | `alumglass/api/variable_catalog.py` | `get_variable_catalog`, `_build_catalog`, `_resolve_profile_doc`, `_load_profile`, `explain_variable`, `preview_variable_catalog`, `get_row_literal_names` |
| Bối cảnh đọc DB | `alumglass/variable_sources/context.py` | `CatalogContext.get_doc/get_current_row/resolve_doc_values`, `get_scalar_fieldnames`, `detect_slug_field` |
| 10 adapter + references | `alumglass/variable_sources/adapters.py` | `fvb_scope`, `cost_bucket`, `variable_library_system/user`, `variable_set`, `cost_template_line`, `formula_global`, `row_literal`, `common_var`, `doctype_field`, `build_references` |
| Luật lọc + dedupe | `alumglass/variable_sources/rules.py` | `select_candidates`, `active_source_kinds`, `dedupe_candidates`, `_combine_field_scopes`, `build_groups` |
| Sổ adapter | `alumglass/variable_sources/registry.py` | `register_adapter`, `get_adapters` |
| Engine tính giá | `alumglass/engine/bom_orchestrator.py` | `run`, `b0..b7`, `_resolve_system_variables`, `_resolve_fb_context`, `_load_accessories`, `_normalize_items_ref`, `_validate_glass_max_area` |
| Validate dùng chung | `alumglass/al_bom_engine/formula_validate.py` | `build_known_names`, `check_formula`, `check_formula_fields`, `validate_rule_input_expr`, `normalize_cross_row` |
| Resolve system var | `alumglass/al_bom_engine/system_variable_resolver.py` | `fetch_system_vars`, `resolve_source_record_names`, `resolve_system_variable_values` |
| Cross-row superset khi validate | `alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.py` | `_cross_row_known_fields`, `_validate_child_formulas`, `_warn_rule_input_expr` |
| Field engine luôn tạo | `alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.py` | `FORMULA_FIELDS`, `CONDITION_FORMULA_FIELDS`, `ENGINE_SYNTHETIC_FIELDS`, `backfill_input_vars` |
| Validate Cost Template | `alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.py` và `.js` | `ALCostTemplate.validate`, `_build_known_names`, `preview_cost_template` |
| Live context FB | `formula_builder/api/formula_builder.py` | `get_live_context`, `_dedupe_live_variables`, `_split_field_scope`, `_merge_field_scope` |
| Scope binding | `formula_builder/api/binding_scope.py` | `binding_matches_scope`, `get_scope_bindings`, `get_scope_bindings_multi` |
| Resolve binding | `formula_builder/api/data_source_registry.py` | `resolve_bindings_with_deps`, `_get_dependency_graph`, handlers |
| Batch resolve | `formula_builder/api/batch_binding_resolver.py` | `BatchBindingResolver.resolve_all_batch` |
| Cache hằng số | `formula_builder/api/global_variable_cache.py` | `get_all_global_variables`, `invalidate_global_variable_cache` |
| Chuẩn hoá công thức | `formula_builder/formula_utils/normalize.py` | `strip_dollar_prefix`, `normalize_formula` |
| Engine công thức | `formula_builder/formula_utils/engine_public.py`, `engine_core.py` | `FormulaEngine.calculate`, `last_errors` |
| An toàn eval | `formula_builder/security/safe_eval.py` | `compile_expression`, `_validate_ast` |

### B. API (whitelist)

| API | Tham số chính | Trả về |
|---|---|---|
| `alumglass.api.get_formula_context` | `doctype`, `docname`, `fieldname`, `child_table`, `row_index`, `include_all_sources` | `{doctype, docname, variables, references, groups?, profile, meta, total_*}` |
| `alumglass.api.get_formula_fields` | `doctype` | list dòng `AL Formula Field` đang bật |
| `alumglass.api.get_allowed_formula_functions` | — | `{custom_functions: [...]}` |
| `alumglass.api.variable_catalog.get_variable_catalog` | `doctype`, `docname`, `child_table`, `row_index`, `fieldname`, `include_values`, `profile` | `{success, profile, variables, groups, references, meta}` |
| `alumglass.api.variable_catalog.explain_variable` | `variable_name`, `doctype`, `docname`, `child_table`, `row_index`, `fieldname` | `{sources: [...], kept, meta}` |
| `alumglass.api.variable_catalog.preview_variable_catalog` | `profile`, `doctype`, … | như API chính |
| `alumglass.api.calculate_bom` | `quotation_item_name` | kết quả BOM (có thể chạy nền) |
| `alumglass.api.preview_cost_template` | `template_code`, `inputs_json` | kết quả tính thử |
| `formula_builder.api.formula_builder.get_live_context` | `scope_context_json` | `{variables, crossTables, objects, json_str}` |

### C. Bảng DB liên quan

`AL Variable Library`, `AL Variable Set`, `AL Variable Set Item`, `AL Cost Bucket`,
`AL Cost Template`, `AL Cost Template Item`, `AL Slug Library`, `AL Variable Settings` (Single),
`AL Common Variable`, `AL Row Literal`, `AL Variable Profile`, `AL Variable Profile Rule`,
`AL Variable Cross Row`, `AL Formula Field`, `AL Variable Dimension Mapping`,
`AL Profile System`, `AL Material Category`, `AL Quantity Calc Method`, `AL Glass Master`,
`AL Rule` (rule tính giá trị + rule chọn mã), `Formula Variable Binding`, `Formula Global Variable`,
`Quotation Item` (các cột `al_bom_vars`, `al_bom_result`, `al_gia_ban`, `al_gia_vat`).

### D. Checklist debug 10 bước

Làm theo thứ tự, dừng ở bước đầu tiên có bất thường.

1. **Biến có trong gợi ý không?** Mở đúng form, gõ 2 ký tự đầu. Không thấy → sang bước 2; thấy
   → sang bước 5.
2. **Profile nào đang áp?** Gọi `get_variable_profile(doctype, docname)`. `null` → đường legacy
   9 nhóm; có mã → kiểm rule.
3. **Biến bị rule loại hay adapter không sinh?** Gọi `explain_variable(...)`: xem `sources`,
   `selected`, `kept`.
4. **Phạm vi field có chặn không?** Xem `only_fields`, `hide_all` của biến; đối chiếu field đang
   sửa. Nhớ: bulk autocomplete không gửi `fieldname` — lọc là ở client.
5. **Validate nói gì?** Lưu thử. Cost Template: cảnh báo cam/đỏ trên form. Bom Set: lỗi chặn lưu.
6. **Chuỗi đã lưu đúng chưa?** Đọc thẳng field (`width/qty/calc_formula`), so với thứ vừa gõ.
   Chưa lưu được thì không có gì để engine đọc.
7. **Chạy tính giá rồi mở `al_bom_result.errors`.** `bom_items` là lỗi B4; `cost_template` là lỗi
   B6. Lỗi ở đây thường là NameError/zero-division của đúng biến đang nghi.
8. **Xem `al_bom_result.lines[]`.** `unit_price`, `weight_per_unit`, `glass_thick`, `trace` cho
   biết dữ liệu nền có vào hay không.
9. **Xem `al_bom_result.buckets`.** Bucket nghi vấn có khoá không; nếu không, không dòng nào mang
   `cost_bucket` đó (hoặc bucket bị tắt/không tồn tại).
10. **Xem `al_bom_result.cost_template`.** `line_code` nghi vấn có giá trị chưa; nếu 0, kiểm công
    thức cùng các mã nó tham chiếu (đặc biệt bucket và dòng phía sau).

Nếu cả 10 bước bình thường mà giao diện vẫn khác: ca cache (mục 15) — tải lại trang trước khi kết
luận.

### E. Phép canh lệch tài liệu với mã

Tài liệu này mô tả mã tại một mốc. Khi mã đổi, chạy các lệnh sau để biết chỗ nào đã trôi — đừng
dựa vào việc có người nhớ cập nhật.

```bash
cd ~/myfrappe/apps/alumglass

# 1) Các hàm mà tài liệu gọi tên phải còn tồn tại
grep -n "def _resolve_profile_doc\|def _build_catalog\|def get_variable_catalog" \
     alumglass/api/variable_catalog.py
grep -n "def get_formula_context\|def _get_catalog_context\|def _get_live_context_vars" \
     alumglass/api/__init__.py
grep -n "def b1_gather_inputs\|def b3_build_formulas\|def b6_calculate_cost_template" \
     alumglass/engine/bom_orchestrator.py
grep -n "def build_known_names\|def validate_rule_input_expr" \
     alumglass/al_bom_engine/formula_validate.py
grep -n "def _cross_row_known_fields" \
     alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.py

# 2) Số adapter và số source_type phải khớp bảng trong tài liệu
grep -c "@register_adapter" alumglass/variable_sources/adapters.py          # kỳ vọng 10
grep -c "@register_source" ../formula_builder/formula_builder/api/data_source_registry.py
grep -c "@register_source" alumglass/fb_handlers.py                         # kỳ vọng 2

# 3) Hằng số cache phải khớp mục 15
grep -n "_ttl" alumglass/public/js/formula_setup.js
grep -n "CACHE_TTL_SECONDS" ../formula_builder/formula_builder/api/global_variable_cache.py

# 4) Field lưu công thức phải khớp bước 6
python3 -c "import json;d=json.load(open('alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.json'));print([f['fieldname'] for f in d['fields'] if f.get('fieldtype')=='Small Text'])"
```

Nếu kết quả khác kỳ vọng: sửa tài liệu **trước** khi dùng nó để chẩn đoán.

### F. Đọc tiếp

- Cách setting profile trên UI: [huong-dan-setting-bien.md](huong-dan-setting-bien.md)
- Ví dụ setting đầy đủ 13 cột + cách tắt/chỉ hiện biến: [vi-du-setting-day-du.md](vi-du-setting-day-du.md)
- Tra theo từng DocType (setting ở đâu, lấy từ đâu, điều kiện gì): [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md)
- Ví dụ cấu hình A–Z có số liệu: [vi-du-a-z.md](vi-du-a-z.md)
- Bản đồ nguồn biến đầy đủ (tra cứu, không phải luồng): [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md)
- Tính năng mới của Formula Builder: [../../../formula_builder/docs/huong-dan-tinh-nang-moi.md](../../../formula_builder/docs/huong-dan-tinh-nang-moi.md)
- Luồng tính giá đầy đủ B0–B7 ở góc nghiệp vụ: [../huong-dan-tinh-gia-full-flow.md](../huong-dan-tinh-gia-full-flow.md)
- Shape API và mã lỗi: [api-reference.md](api-reference.md)
- Triệu chứng thường gặp: [troubleshooting.md](troubleshooting.md)
