# NGUỒN BIẾN THAM CHIẾU — ALUMGLASS ↔ FORMULA BUILDER

> Bản **viết lại 2026-11-13**, thay hoàn toàn bản cũ 1 728 dòng. Bản cũ có phần đề xuất chưa
> làm, số dòng đã trôi và nhiều chỗ mô tả code không còn tồn tại. Bản này chỉ tả **code đang
> có**, dẫn chứng bằng `file:function` (⛔ không dùng `:dòng` — số dòng đổi sau mỗi lần sửa).

---

## 1. Phạm vi, mốc code, mức kiểm chứng

| | |
|---|---|
| App `alumglass` | nhánh `main`, HEAD `566cdc2` (2026-11-12) **+ thay đổi chưa commit**: `al_bom_item.py`, `al_bom_set.py` (validate cross-row dùng superset), `README.md`; kèm test và tài liệu mới trong `docs/variable-catalog/` |
| App `formula_builder` | nhánh `develop`, HEAD `51cb497`; thay đổi v28_14 **đã commit** |
| Phạm vi | *"Biến này ở đâu ra, hàm nào đọc, khi nào có giá trị, khi nào chỉ là gợi ý"* — cho cả 2 mặt phẳng: gợi ý trong autocomplete và tính tiền thật |
| Đối tượng | DEV bảo trì engine/catalog; admin cấu hình cần hiểu vì sao một biến có/không có giá trị; người review |
| Ngày soạn | 2026-11-13 |
| Mức kiểm chứng | Đọc trực tiếp mã 2 repo. **Đã chạy lại 4 bộ test thuần** (không cần site): `test_variable_catalog_rules.py` **41 ca PASS**, `test_dollar_normalize.py` **15 PASS**, `test_live_context_dedupe.py` **11 PASS**, `test_bom_set_cross_row_known_fields.py` **7 PASS**. ⛔ **Chưa chạy `bench migrate`, chưa chạy test Frappe/unittest trên site, chưa mở form, chưa đọc DB thật.** |
| Quy ước dẫn chứng | `đường/dẫn.py:function`; JS ghi `file.js:object.method`. Khi tên hàm đổi, tìm theo tên trong tệp — ⛔ đừng tin số dòng ở tài liệu khác. |

> 🔴 **Đọc câu này trước mọi câu khác:** tài liệu mô tả hành vi **đọc từ mã**. Mọi câu "người
> dùng thấy…", "bấm nút…" là suy ra từ mã, **chưa quan sát trên màn hình**. Khi màn hình khác
> tài liệu, ghi lại hiện tượng thật rồi đối chiếu `docs/variable-catalog/troubleshooting.md`
> trước khi kết luận bên nào sai.

Ba tầng thuật ngữ dùng xuyên suốt:

| Tầng | Nghĩa trong tài liệu này |
|---|---|
| **Engine / runtime** | `BomOrchestrator` chạy B0→B7 để ra tiền (`alumglass/engine/bom_orchestrator.py`) |
| **Catalog** | Lớp gợi ý/lọc biến theo `AL Variable Profile` (`alumglass/variable_sources/`, `alumglass/api/variable_catalog.py`) |
| **Formula Builder (FB)** | Platform resolve biến dùng chung: binding, data source, engine công thức (`formula_builder/`) |

---

## 2. TL;DR

### 2.1 Ba tầng, hai mặt phẳng

```
┌──────────────────────────────────────────────────────────────────────────┐
│ TẦNG CẤU HÌNH — nơi khai biến                                           │
│  AL Variable Library · AL Variable Set · AL Profile System              │
│  AL Cost Bucket · AL Cost Template · AL Accessory Set · AL Slug Library │
│  AL Variable Settings (common var / row literal) · AL Variable Profile  │
│  AL Formula Field · Formula Global Variable · Formula Variable Binding  │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
        ┌───────────────────────┴────────────────────────┐
        ▼                                                ▼
┌──────────────────────────────┐          ┌──────────────────────────────────┐
│ MẶT PHẲNG A — GỢI Ý          │          │ MẶT PHẲNG B — TÍNH TIỀN          │
│ autocomplete / validate      │          │ BomOrchestrator B0→B7            │
│ get_formula_context          │          │ đọc thẳng DB + al_bom_vars       │
│ catalog + profile (nếu có)   │          │ ⛔ KHÔNG đọc profile             │
│ → danh sách người dùng thấy  │          │ → ra số tiền                     │
└──────────────────────────────┘          └──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ TẦNG NỀN — Formula Builder                                               │
│  Formula Variable Binding (21 source_type) · FormulaEngine (DAG+topo)    │
│  BatchBindingResolver · safe_eval · normalize ($NAME → NAME)             │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Hai mặt phẳng — điều quan trọng nhất

| | **A. Gợi ý / validate** | **B. Tính tiền** |
|---|---|---|
| Điểm vào | `alumglass.api.get_formula_context` | `alumglass.api.calculate_bom` → `BomOrchestrator.run` |
| Có đọc `AL Variable Profile`? | **Có**, khi bản ghi đã gán profile (`include_all_sources=False`) | ⛔ **Không**, ở bất kỳ bước nào |
| Có đọc `AL Formula Field`? | Có — để biết field nào gắn autocomplete | ⛔ Không |
| Có đọc `AL Variable Settings`? | Có — nguồn `row_literal` / `common_var` | Chỉ đọc **gián tiếp** qua `get_row_literal_names` khi **lưu** `AL Bom Set` (cảnh báo `rule_input_expr`), ⛔ không đọc lúc tính |
| Hệ quả khi sửa profile | Đổi danh sách biến người dùng thấy | **Không đổi một đồng nào** |

> 🔴 **Bất biến kiểm được:** bật/tắt/sửa/xoá `AL Variable Profile` mà số tiền của một BOM đã
> tính thay đổi ⇒ **lỗi hồi quy**, không phải "profile có tác dụng". Sửa profile không phải
> cách sửa giá.

### 2.3 v28_14 đổi gì

| Nhóm | Trước | Sau |
|---|---|---|
| Lọc biến khi gõ | 9 nhóm chồng lấn, không lọc theo ngữ cảnh | `AL Variable Profile` + rule Include/Exclude + `only_fields` |
| Nguồn biến | Row literal / common var / registry field nằm cứng trong Python + JS | `AL Variable Settings` + `AL Formula Field` (dữ liệu) |
| Truy vết nguồn | Không có | `source_kind`, `provenance`, `meta.duplicates`, API `explain_variable` |
| Validate | Dùng chính danh sách gợi ý ⇒ bật profile là chặn oan | `include_all_sources=True` — universe đầy đủ, profile ⛔ không thu hẹp |
| Cross-row khi lưu Bom Set | Chỉ `width/height/qty/show_condition` được coi là hợp lệ | **Superset**: + `unit_qty/total_qty/line_total` + row literal đang bật |
| `$NAME` | Engine không hiểu `$` ⇒ syntax error | `normalize.strip_dollar_prefix`: `$NAME → NAME`, giữ `$snap.*` và chuỗi literal |
| Phạm vi field của binding | Widget không gửi `fieldname` ⇒ `applies_to_field` vô hiệu | Widget gửi `fieldname`; mỗi biến mang `only_fields`/`hide_all` để client lọc |
| Global Variable tắt | Vẫn vào `inputs` | `get_all_global_variables` lọc `is_active=1` |

### 2.4 "Muốn thêm biến mới thì thêm ở đâu?"

| Nhu cầu | Thêm ở | Ai đọc |
|---|---|---|
| Hằng số dùng chung | `Formula Global Variable` (`CONSTANT`) | B1 + catalog `formula_global` |
| Biến hệ đọc từ bản ghi liên kết | `AL Variable Library` (`is_system=1`, `source_doctype`/`source_field`, có thể `source_link_field`) | B1 + catalog `variable_library_system` |
| Biến người dùng nhập khi báo giá | `AL Variable Library` (`is_system=0`) + gán vào `AL Variable Set` | dialog Quotation → `al_bom_vars` (B1) |
| Đọc từ bản ghi bất kỳ (kể cả doctype ngoài) | `Formula Variable Binding` + `source_type` phù hợp | B1 (`get_live_context`), B2 (giá), B5 (bucket), catalog `fvb_scope` |
| Biến engine inject theo dòng | Engine B2/B3 — danh sách cố định; khai **tên** trong `AL Variable Settings.row_literals` chỉ để gợi ý/cảnh báo | catalog `row_literal` |
| Biến người dùng nhập (gợi ý) | `AL Variable Settings.common_variables` | catalog `common_var` |
| Biến chéo dòng `items.slug.field` | `AL Slug Library` (dữ liệu dòng) + `AL Variable Cross Row` (gợi ý) | B3 + references |
| Field công thức mới (có autocomplete) | 1 record `AL Formula Field` | `formula_setup.js` |
| Field vô hướng của chứng từ | Không cần khai — adapter `doctype_field` tự dò | catalog `doctype_field` |

---

## 3. Bảng tổng hợp nguồn biến

Ký hiệu: **R** = có mặt lúc tính tiền; **C** = có mặt trong catalog/autocomplete.

| # | Nguồn | Nơi khai | Runtime đọc ở đâu | C | `source_kind` | Ghi chú |
|---|---|---|---|---|---|---|
| 1 | System Variable | `AL Variable Library` (`is_system=1`) | `b1_gather_inputs` → `_resolve_system_variables` → `system_variable_resolver.resolve_system_variable_values` | ✅ | `variable_library_system` | Resolve theo `source_doctype`/`source_field`; `source_link_field` khai tường minh field Link |
| 2 | Profile System override | `AL Profile System.system_variables` (child) | `_resolve_system_variables` (ghi đè sau FB), `resolve_system_variable_values` | ✅ (gián tiếp: chỉ là **giá trị** của var) | — | ⛔ Không có adapter riêng; ưu tiên cao hơn field của profile |
| 3 | User Variable | `AL Variable Library` (`is_system=0`) | `_resolve_user_variable_defaults` (chỉ điền khi thiếu) | ✅ | `variable_library_user` | Giá trị thật đến từ `al_bom_vars` (B1 1.5) |
| 4 | Variable Set | `AL Variable Set` + `AL Variable Set Item` | Runtime **không đọc set**; chỉ đọc giá trị user đã lưu trong `al_bom_vars` | ✅ | `variable_set` | Là hợp đồng UI của dialog; `AL Accessory Set.variable_set` nay được adapter dùng |
| 5 | Row Literal (engine) | Engine B2 dựng `row_literals[slug]` | `b2_prefetch_master_data` → B3 inject `{slug}__{key}` | ✅ | `row_literal` (đọc `AL Variable Settings`) | Danh sách engine inject là **cố định trong mã** — xem §6.4 |
| 6 | Common Var | `AL Variable Settings.common_variables` | ⛔ Engine không đọc Settings; giá trị đến từ `al_bom_vars` | ✅ | `common_var` | Tên gợi ý; không có engine nào tự tính |
| 7 | Field công thức Bom Item | `AL Bom Set.items.<field>` (`formula_fieldnames` hoặc mặc định) | `b3_build_formulas` sinh `{slug}__{field}` | ✅ | — (chỉ references) | Field công thức chạy trong DAG B4 |
| 8 | Calc-pattern input vars | `AL Quantity Calc Method.input_vars` (list) + `AL Bom Item.input_vars` (object) | `b3_build_formulas` (thứ tự: line → inputs → literal → 0) | ⛔ | — | Không có adapter; gõ tay mới thấy |
| 9 | Accessory row | `AL Accessory Set.items` | `_load_accessories` → append vào `bom_items` | ✅ | `variable_set`, `row_literal`, references | `qty_formula` được biên dịch thành `{slug}__qty` (xem §6.4) |
| 10 | Cost Bucket | `AL Cost Bucket.bucket_code` | `b5_aggregate_cost_buckets` (+ `_resolve_cost_buckets_via_fb`) | ✅ | `cost_bucket` | Giá trị chỉ có sau B4; gợi ý hiện `—` |
| 11 | Cost Template line | `AL Cost Template.items.line_code` | `b6_calculate_cost_template` | ✅ | `cost_template_line` | Chỉ thấy dòng **trước** khi API có `row_index` |
| 12 | Formula Global Variable | `Formula Global Variable` | `b1_gather_inputs` 1.2 qua `global_variable_cache.get_all_global_variables` | ✅ | `formula_global` | Chỉ `is_active=1`; `$NAME` được normalize về `NAME` |
| 13 | Formula Variable Binding | `Formula Variable Binding` | B1 `_resolve_fb_context`; B2 `_get_pricing_bindings`; B5 | ✅ | `fvb_scope` | 21 `source_type`; scope cha + dòng con |
| 14 | Cross-row | `AL Slug Library` + field `slug` của dòng | `b3_build_formulas` + `_normalize_items_ref` | ✅ | references (`slug_reference` / `cross_row`) | `items.slug.field → slug__field` |
| 15 | AL Calculation Rule CONSTANT | `AL Calculation Rule` | Fallback cuối trong `_resolve_system_variables` | ⛔ | — | Di sản; chỉ khi var vẫn thiếu/0 |
| 16 | Formula Set / Snapshot | `Formula Set`, cache `formula_snapshot:*` | ⛔ Không đi qua `VariableResolver` ở B3/B6 | ⛔ | — | `$snap.*`, `FS-CODE.var` chỉ chạy khi đã có biến cùng tên trong `inputs` |
| 17 | Pricing Dimension | `AL Variable Dimension Mapping` | `_get_dim_fieldnames`, `_get_pricing_bindings`, `fb_handlers.aluminum_price_composite` | ✅ (cờ `is_pricing_dimension`) | — | Quyết định biến nào là chiều tra giá |
| 18 | Material Category | `AL Material Category.default_scrap_pct` / `has_weight` | `b2_prefetch_master_data` → `{slug}__scrap_pct` | ✅ | `row_literal` (tên) | `has_weight` chỉ để hiển thị cột trọng lượng |

> Bảng này cố ý **gộp**: một "nguồn" có thể vừa là biến (R) vừa là tên gợi ý (C) vừa là dữ
> liệu cấu hình. Cột C trả lời *"có thấy trong autocomplete không"*, ⛔ không trả lời *"có giá
> trị không"* — hai chuyện khác nhau.

---

## 4. Mô hình dữ liệu v28_14

7 DocType mới, module **`AL Master Data`** (trừ ghi chú riêng). Tất cả đều là dữ liệu cấu
hình — ⛔ không phải chứng từ nghiệp vụ.

### 4.1 `AL Variable Profile` — master

`autoname = field:profile_code`. Quyền mặc định: **System Manager** (đọc/ghi/tạo/xoá).

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `profile_code` | Data | ✅ | Mã profile, đồng thời là `name` |
| `profile_name` | Data | ✅ | Tên hiển thị |
| `is_active` | Check (default 1) | — | Tắt ⇒ catalog **bỏ qua**, rơi về legacy |
| `default_action` | Select `INCLUDE_ALL`/`EXCLUDE_ALL` (default `INCLUDE_ALL`) | ✅ | Cho tất cả rồi trừ, hay chỉ cho đúng thứ được khai |
| `description` | Small Text | — | Ghi chú |
| `rules` | Table → `AL Variable Profile Rule` | — | Luật lọc |
| `cross_row` | Table → `AL Variable Cross Row` | — | Cấu hình biến chéo dòng |

`validate` (`al_variable_profile.py:ALVariableProfile.validate`) chỉ chặn `only_fields` không
phải JSON list, báo đúng số dòng rule.

### 4.2 `AL Variable Profile Rule` — child (13 cột dữ liệu)

| Field | Kiểu | Ghi chú |
|---|---|---|
| `action` | Select `Include`/`Exclude` (default Include) | Exclude **luôn thắng** Include |
| `source_kind` | Select 11 giá trị | Xem §5.3 |
| `source_ref` | Data | `*`/rỗng/`AUTO` = **không lọc thêm** (tập vẫn do adapter ngữ cảnh sinh ra; riêng `variable_set` là set gắn với bản ghi); ngược lại là danh sách ngăn `\|` |
| `group_label` | Data | Nhóm hiện trong autocomplete |
| `sort_order` | Int (default 100) | Nhóm nhỏ trước; rule khai trước thắng khi hoà |
| `is_active` | Check (default 1) | Tắt rule mà không xoá |
| `name_prefix` | Data | Danh sách tiền tố ngăn `\|`, **phân biệt hoa thường** |
| `name_regex` | Data | `re.search`; regex hỏng ⇒ coi như không khớp |
| `category_tag` | Data | So với `category` **hoặc** `group` của biến, không phân biệt hoa thường |
| `var_type` | Select 8 kiểu | So khớp **chính xác** với `type` của candidate |
| `source_type` | Data | Chỉ có tác dụng với `fvb_scope` |
| `only_fields` | Small Text (JSON list) | Cổng **theo field ở mức rule** — xem §5.5 |
| `require_value` | Check (default 0) | Chỉ hiện biến có giá trị thật |

### 4.3 `AL Variable Cross Row` — child của Profile

| Field | Kiểu | Default | Ý nghĩa |
|---|---|---|---|
| `table_field` | Data | — | Field bảng con, vd `items` (bắt buộc) |
| `id_field` | Data | `slug` | Field định danh dòng |
| `label_field` | Data | — | Field nhãn; trống ⇒ tự dò `line_name` → `item_code` |
| `fields` | Small Text (JSON list) | — | Field được gợi ý chéo; trống = mọi field vô hướng |
| `include_index_form` | Check | 1 | Sinh thêm dạng `items[0].field` |
| `enabled` | Check | 1 | Tắt dòng mà không xoá |

### 4.4 `AL Variable Settings` — Single

| Field | Kiểu | Ý nghĩa |
|---|---|---|
| `default_profile` | Link `AL Variable Profile` | ⚠ **Chỉ áp cho doctype đã khai field Link tới Profile**; doctype không có field ⇒ bỏ qua (xem §5.2) |
| `preview_doctype` | Link `DocType` | Giá trị mặc định cho ô "DocType cần xem trước" |
| `common_variables` | Table → `AL Common Variable` | Nguồn `common_var` |
| `row_literals` | Table → `AL Row Literal` | Nguồn `row_literal` + danh sách field cho cảnh báo `rule_input_expr` |

`AL Common Variable` và `AL Row Literal` có **cùng bộ field**: `var_name` (bắt buộc),
`var_label`, `var_type` (8 kiểu), `group_label`, `sort_order` (100), `is_active` (1),
`description`. Không có `category`.

⛔ Settings **không còn** `cache_ttl` / `enable_legacy_fallback` (bản cũ có nhắc — đã bỏ khỏi
mã; đừng đi tìm).

### 4.5 `AL Formula Field` — master, `autoname = hash`

| Field | Kiểu | Ghi chú |
|---|---|---|
| `target_doctype` | Link `DocType` | ⚠ **Không phải `doctype`** — Frappe cấm fieldname `doctype` (từ khoá dành riêng). API vẫn trả key `"doctype"` |
| `child_table` | Data | Rỗng = field trên chính doctype |
| `fieldname` | Data | Bắt buộc |
| `id_field` | Data (default `slug`) | Truyền xuống widget làm `id_field` |
| `editor_opts` | JSON (default `{}`) | `height`, `float_popup`…; hỏng ⇒ `{}` |
| `sort_order` | Int (default 0) | Thứ tự nạp |
| `is_active` | Check (default 1) | |

Quyền mặc định: **System Manager**.

### 4.6 Field `variable_profile` trên 4 doctype

| DocType | Field đi kèm đáng chú ý | Áp cho |
|---|---|---|
| `AL Bom Set` | `product_type`, `profile_system`, `variable_set`, `default_accessory_set`, `formula_fieldnames`, `apply_scrap_pct` | Field cha + mọi dòng `items` |
| `AL Cost Template` | `product_type` | Dòng `items.calc_formula` |
| `AL Accessory Set` | `product_type`, `variable_set` | `qty_formula` + gợi ý chéo dòng |
| `AL Alert Config` | — | `trigger_condition` |

Cả 4 đều là **Link → `AL Variable Profile`**, không bắt buộc. Bảng con **không** có field
riêng: catalog nhận `doctype` + `docname` + `child_table` + `row_index` rồi kế thừa profile
của cha.

---

## 5. Autocomplete A–Z

### 5.1 Chuỗi gọi (một lượt)

```
form-refresh  (Frappe phát document event)
  │
  └─ alumglass.FormulaFields.init(frm)                 formula_setup.js
       ├─ get_formula_fields(doctype)                  → AL Formula Field (is_active=1)
       ├─ FormulaContext.fetch(doctype, docname, "")   → get_formula_context
       ├─ FormulaContext.fetch(doctype, docname, tbl)  → 1 lần / child table
       └─ apply(frm, row) → initGridField / patchField  (widget FB)
                                │
                                ▼
                    widget mở editor → _buildCtx() gửi fieldname
                                │
                                ▼
              _ContextBuilder.build (đã bị AlumGlass patch)
                    ├─ biến từ cache  (lọc only_fields / hide_all)
                    ├─ references từ cache
                    └─ field/sibling do lõi FB tự dựng
```

Bước cuối — **widget chèn token** theo `insert` của từng mục (`formula_builder.js`):

| Loại mục | `insert` |
|---|---|
| Field cha / field dòng hiện tại | `fieldname` trần |
| Dòng khác (sibling) | `items[0].field` hoặc `items.slug.field` |
| Reference từ catalog | đúng `insert` server trả (`items.slug.field` / `items[n].field`) |
| Biến **global** | **`$` + tên** (`$VAT_RATE`) — engine bỏ `$` khi normalize (§7.5) |
| Biến local / catalog khác | tên trần |

Điểm vào phía server — `get_formula_context` (`alumglass/api/__init__.py`):

| Bước | Hàm | Việc |
|---|---|---|
| 0 | `_assert_formula_context_doctype` | Allowlist doctype + quyền đọc (chạy **trước** mọi thứ) |
| 1 | `_get_catalog_context` | Thử đường catalog; trả `None` nếu chưa cài module / lỗi / **bản ghi chưa gán profile** |
| 2a | `variable_catalog.get_variable_catalog` | Đường catalog: resolve profile → adapter → rule → dedupe → groups/references |
| 2b | `_get_live_context_vars` + 9 khối legacy | Đường cũ: FB live context + Cost Bucket + Library + Global + Row Literal + Common Var + FVB + Variable Set + Slug |

`include_all_sources=True` ⇒ **bỏ qua bước 1 hoàn toàn**, luôn đi 2b (dùng cho validate —
xem §9).

### 5.2 Resolve profile — thứ tự và điều kiện

`variable_catalog._resolve_profile_doc`:

```
1. tham số `profile` truyền tường minh (preview/admin)
2. field Link ĐẦU TIÊN trên doctype trỏ tới `AL Variable Profile`, đọc giá trị trên docname
3. AL Variable Settings.default_profile
4. không có → None ⇒ get_formula_context dùng legacy
```

Hai chốt dễ bỏ qua:

- **Bước 2 chỉ chạy khi doctype thật sự có field Link** tới Profile (`_find_profile_field`
  quét meta). Doctype không có field ⇒ `_resolve_profile_doc` trả `None` **ngay**, không xét
  `default_profile`. Nếu không, một default toàn cục sẽ tự bật cho mọi doctype.
- Profile `is_active=0` hoặc không tồn tại ⇒ `_load_profile` trả `None` ⇒ **rơi về legacy**,
  ⛔ không báo lỗi ra UI.

`get_variable_catalog` khi **không** có profile trả `{profile: null, variables: [], ...,
meta.legacy_fallback: true}` — đây là tín hiệu "hãy đi đường cũ", ⛔ không phải "không có biến".

### 5.3 Adapter — 10 nguồn, 1 `source_kind` đặc biệt

`alumglass/variable_sources/adapters.py`, đăng ký bằng `@register_adapter(kind, label, order)`.
`order` nhỏ = ưu tiên cao khi dedupe hoà.

| Order | `source_kind` | Sinh từ | Giá trị lấy từ |
|---|---|---|---|
| 10 | `fvb_scope` | Formula Variable Binding, scope **doctype cha + doctype dòng con** | `resolve_bindings_with_deps` trên doc cha; binding của dòng con resolve trên **dòng hiện tại** |
| 20 | `cost_bucket` | `AL Cost Bucket` (`is_active=1`) | `ctx.resolved` (thường `—` — bucket chỉ có sau B4) |
| 30 | `variable_library_system` | `AL Variable Library` (`is_system=1`) | `ctx.resolved`, thiếu thì `default_value` |
| 40 | `variable_library_user` | `AL Variable Library` (`is_system=0`) | không resolve — chỉ tên/nhãn |
| 45 | `variable_set` | Set khai trong rule (`source_ref`) + set tự dò của bản ghi | `ctx.resolved` |
| 50 | `cost_template_line` | `AL Cost Template.items.line_code` | không có (tính ở B6) |
| 55 | `formula_global` | `Formula Global Variable` (`is_active=1`) | `constant_value` khi `value_source=CONSTANT` |
| 60 | `row_literal` | `AL Variable Settings.row_literals` | field cùng tên trên **dòng hiện tại**, fallback trên chứng từ |
| 70 | `common_var` | `AL Variable Settings.common_variables` | `ctx.resolved` |
| 80 | `doctype_field` | Field vô hướng của doctype cha **hoặc** dòng đang sửa | giá trị field |

`slug_reference` là `source_kind` **thứ 11 nhưng ⛔ không có adapter** — nó điều khiển phần
`references` (`adapters.build_references`). Vì vậy: 11 `source_kind`, 10 adapter.

Cách thêm nguồn mới (đúng thiết kế, không sửa core): viết 1 hàm + `@register_adapter`, thêm 1
option vào `source_kind` của `AL Variable Profile Rule`, khai rule trong profile.
`rules.py` và `variable_catalog.py` **không phải sửa**.

### 5.3.1 `source_ref` — mỗi nguồn một nghĩa

| `source_kind` | `source_ref` nhận | Ghi chú |
|---|---|---|
| `fvb_scope` | **tên biến** (vd `OFFSET_FRAME`), hoặc `*` / `AUTO` = mọi binding | ⛔ Không lọc theo doctype bằng `source_ref` — dùng `source_type`, `name_prefix`, `name_regex`. Scope cha + dòng con do adapter tự lấy |
| `cost_template_line` | **`line_code`**, hoặc `AUTO` / `*` = mọi dòng | Chỉ lọc "dòng trước" khi API **có `row_index`** |
| `variable_set` | **`set_code`**, hoặc `AUTO` / `*` = bộ của chính bản ghi | `AUTO` còn kéo thêm set khai tường minh trong chính rule |
| `cost_bucket` / `variable_library_system` / `variable_library_user` / `formula_global` / `row_literal` / `common_var` / `doctype_field` | mã/tên cụ thể (danh sách ngăn `\|`), hoặc `*` | So khớp **không phân biệt hoa thường** với `source_ref` của candidate |
| `slug_reference` | **tên bảng con thật** (`items`) | `*` / `AUTO` bị **bỏ qua** ở nhánh rule ⇒ ⛔ đừng dùng; nhiều bảng thì ngăn `\|` |

⚠ `AUTO` phải viết **HOA**. `auto` thường bị hiểu là **tham chiếu thật** (tên bảng/biến) ⇒
rule không khớp gì, biến biến mất **im lặng** (không có `excluded_by_rules` bất thường để thấy).

⚠ Giới hạn `cost_template_line`: autocomplete **bulk không gửi `row_index`**, nên có thể thấy
cả `line_code` của dòng **sau**. Chỉ preview / validate / gọi API trực tiếp (có `row_index`)
mới cắt đúng "dòng trước". Tham chiếu dòng sau ⇒ công thức ra 0/vòng.

### 5.4 Áp rule — thứ tự cố định

`rules.select_candidates`:

```
1. Rule Exclude khớp                          → loại (Exclude thắng Include)
2. require_value: rule đòi giá trị + biến rỗng + CHƯA khớp Include nào khác → loại hẳn
   (nếu còn rule Include khác khớp, biến rỗng vẫn hiện)
3. EXCLUDE_ALL và không khớp Include nào      → loại
4. Include khớp                               → gắn group_label + sort_order của rule tốt nhất
5. Phạm vi field = GIAO (phạm vi nguồn) × (hợp only_fields của các rule khớp)
   - giao rỗng                                → hide_all = true (ẩn MỌI field)
```

Điều kiện khớp của một rule (`rules._matches`): nguồn (rỗng = mọi nguồn) · `source_ref` · tiền
tố · regex · category/group · `var_type` · `source_type` · `only_fields` · `require_value`.
Thiếu `fieldname` ở caller ⇒ điều kiện `only_fields` **được bỏ qua** (an toàn ngược, ⛔ không
phải "rule bị bỏ qua").

`active_source_kinds` quyết định adapter nào **được chạy**:

| `default_action` | Có rule Include? | Nguồn được chạy |
|---|---|---|
| `INCLUDE_ALL` | Không | **Tất cả** adapter (profile rỗng ⛔ không làm mất biến) |
| `INCLUDE_ALL` | Có | Chỉ các nguồn được Include |
| `EXCLUDE_ALL` | Có | Chỉ các nguồn được Include |
| `EXCLUDE_ALL` | Không | Không chạy adapter nào ⇒ danh sách rỗng |

### 5.5 `only_fields` — cổng theo field ở mức rule

Đây là chỗ hiểu sai nhiều nhất. Ba mệnh đề, đọc đủ cả ba:

1. `only_fields` **không phải** allowlist từng biến. Nó là danh sách field mà **rule** được áp.
   Biến do rule đó chọn sẽ chỉ hiện ở các field trong danh sách.
2. **Muốn mỗi field một danh sách riêng** ⇒ **tách biến giữa các rule** bằng `source_ref` /
   `name_prefix` / `name_regex`. Ví dụ 2 rule `row_literal`: một rule `width|height` với
   `["width","height"]`, một rule `qty|calc_pattern` với `["qty","calc_pattern"]`.
3. **Nhiều rule cùng chọn một biến** ⇒ `only_fields` lấy **hợp**; nếu **một** rule không khai
   giới hạn ⇒ biến **không giới hạn**. Vì vậy đặt 2 rule `source_ref=*` với hai danh sách khác
   nhau sẽ **không tách được** biến — kết quả là hợp.
4. **Bất đối xứng với `INCLUDE_ALL`:** khi rule khai cả `source_ref` cụ thể lẫn `only_fields`, server
   chỉ bỏ qua điều kiện field nếu `fieldname` vắng; nếu `fieldname` có mà rule không khớp field,
   candidate **không bị loại** dưới `INCLUDE_ALL` ⇒ `only_fields` không phải cổng cứng. Muốn chặn
   thật, dùng `EXCLUDE_ALL`. Chi tiết + ví dụ: [docs/variable-catalog/al-variable-profile.md](docs/variable-catalog/al-variable-profile.md) §5.5.

Hai giá trị khác nghĩa hoàn toàn:

| | `only_fields = []` | `hide_all = true` |
|---|---|---|
| Nghĩa | **Không giới hạn** field | Ẩn ở **mọi** field |
| Ai gắn | Nguồn hoặc rule | Server, khi giao phạm vi nguồn × rule **rỗng** |
| Có phải field cấu hình? | Có (`AL Variable Profile Rule.only_fields`) | ⛔ Không — chỉ có trong response |

Nguồn cũng mang phạm vi field: `fvb_scope` lấy `applies_to_field` của binding. Khi widget gửi
`fieldname`, binding được so **nguyên chuỗi** (`width` khớp; `width|height` ⛔ không khớp field nào);
chỉ đường bulk không có `fieldname` mới tách `|`/`,` thành danh sách. `doctype_field` / `row_literal`
/ `common_var` không giới hạn.

### 5.6 Client lọc theo field đang sửa

`formula_setup.js` patch `formula_builder.formula._ContextBuilder.build`:

- `_buildCtx()` (widget) truyền `fieldname: opts.current_field`.
- Patch đọc `params.fieldname` → `_fieldExcluded(variable, fieldname)`:
  `hide_all` ⇒ loại; `only_fields` rỗng ⇒ giữ; `only_fields` không chứa field ⇒ loại;
  **không có fieldname** ⇒ không lọc.
- Biến được đẩy vào `params.liveCtx.variables` với tooltip ghép `group · value_source`.
- References đẩy nguyên vào `params.liveCtx.references`.

Vì sao phải lọc ở client: context chỉ fetch **một lần cho cả form** (`doctype::docname::child_table`),
⛔ không fetch theo từng lần gõ.

### 5.7 Cache phía client — và giới hạn của nó

| Cache | Khoá | TTL | Ghi chú |
|---|---|---|---|
| `alumglass.FormulaContext` | `doctype::docname::child_table` | 5 phút | `getSync` fallback dần: có childTable → không childTable → chỉ doctype |
| `alumglass.FormulaFields` | `doctype` | 60 giây | Registry `AL Formula Field` |
| `alumglass.CostTemplate._contextCache` | `docname` | không TTL | Context cho Cost Template |
| `alumglass.CostTemplate._validationCache` | `docname` | không TTL | Universe **đầy đủ** để validate |

⚠ Có hàm `invalidate(doctype)` nhưng **không có chỗ nào gọi** trong app (đã grep toàn bộ
`alumglass/`). Sửa `AL Formula Field` / profile ⇒ phải chờ TTL hoặc F5. Đây là giới hạn đã
biết, ⛔ không phải tính năng.

### 5.8 References (gợi ý biến chéo dòng)

`adapters.build_references` — thứ tự quyết định:

```
1. Profile có `cross_row` (enabled, table_field không rỗng)  → dùng đúng cấu hình đó
2. Không có cross_row, CÓ rule Include `slug_reference`      → chỉ các bảng được trỏ tới
3. Không có cả hai + default_action = INCLUDE_ALL            → mọi child table (hành vi cũ)
4. EXCLUDE_ALL và không khai gì                              → không gợi ý
```

Rule `slug_reference` **Exclude** luôn loại bảng tương ứng ở mọi nhánh. Mỗi dòng sinh 2 dạng:
`items.<slug>.<field>` (slug đọc theo `id_field`, tự dò `custom_slug` → `line_ref` → `*_slug` →
`slug`) và `items[<index>].<field>` nếu `include_index_form`.

> 🔴 **Không có profile ⇒ vẫn có `items.*`.** Nếu `get_formula_context` rơi vào đường legacy
> (`profile: null` — record mới chưa lưu, field trống + `default_profile` trống, profile tắt),
> phần cuối đường legacy **luôn** thêm references từ `AL Slug Library` dạng
> `items.<slug>.{field}`, ⛔ không liên quan rule `slug_reference`. Vì vậy bỏ rule này **không**
> tắt được gợi ý nếu profile chưa resolve; và `INCLUDE_ALL` + không có `cross_row` cũng sinh
> references cho mọi bảng con. Xem [docs/variable-catalog/al-variable-profile.md](docs/variable-catalog/al-variable-profile.md) §7.2.1.

---

## 6. Runtime A–Z (B0 → B7)

### 6.1 Sơ đồ

```
calculate_bom(quotation_item_name)                         api/__init__.py:calculate_bom
  ├─ _require_quotation_item_permission  (read trên Quotation cha)
  ├─ assert_quotation_item_editable      (chốt sớm; chốt thật ở B7)
  ├─ ≤ ngưỡng  → chạy đồng bộ
  └─ > ngưỡng  → frappe.enqueue(queue="long") + trả {async, job_id}
        │
        └─ BomOrchestrator(qi).run()                        engine/bom_orchestrator.py:run
             B0 b0_version_pinning          Quotation Item.al_bom(_version) → AL BOM Version
             B1 b1_gather_inputs            dựng self.inputs (xem §6.2)
             B2 b2_prefetch_master_data     snapshot items + phụ kiện + master data + row literal
             B3 b3_build_formulas           danh sách formula + inputs["items"]
             B4 b4_calculate_bom_items      FormulaEngine.calculate
             B5 b5_aggregate_cost_buckets   gom line_total theo bucket
             B6 b6_calculate_cost_template  FormulaEngine trên cost template
             B7 b7_save_results             ghi Quotation Item + tổng tiền Quotation
             → _build_response
```

**Catalog ⛔ không xuất hiện ở bất kỳ bước nào trong 8 bước trên.** Cụ thể:

| Bước | Có đọc profile? | Có đọc Settings/Formula Field? | Vì sao |
|---|---|---|---|
| B0 | Không | Không | Chỉ chọn version |
| B1 | Không | Không | Đọc `al_bom_vars`, Global Variable, FVB, Library |
| B2 | Không | Không | Đọc snapshot + master data + Item Price |
| B3 | Không | Không | Đọc `formula_fieldnames` / `input_vars` của chính BOM |
| B4 | Không | Không | Chạy engine trên `inputs` |
| B5 | Không | Không | Đọc `AL Cost Bucket.source_type` / `source_config` |
| B6 | Không | Không | Đọc snapshot cost template |
| B7 | Không | Không | Ghi kết quả |

### 6.2 B1 — bảng ưu tiên (ai ghi trước / sau)

`b1_gather_inputs` ghi theo **đúng thứ tự dưới**; lớp ghi sau thắng, trừ lớp ghi rõ "chỉ điền
khi thiếu".

| Thứ tự | Lớp | Ghi đè? | Hàm / nguồn |
|---|---|---|---|
| 1 | `al_bom_vars.extra_vars` | lớp đầu | `b1_gather_inputs` (đọc JSON) |
| 2 | Formula Global Variable (`is_active=1`) | **ghi đè** | `global_variable_cache.get_all_global_variables` |
| 3 | FB `get_live_context` (binding + doc field + global) | **ghi đè** | `_resolve_fb_context` (scope `AL Bom Set`, fallback `Quotation Item`) |
| 4 | Library system var | chỉ khi thiếu | `_resolve_system_variables(fill_missing_only=True)` |
| 5 | `AL Profile System.system_variables` (child) | **ghi đè** | `_profile_child_vars` (capture trực tiếp từ child row) |
| 6 | `al_bom_vars` **top-level** + `extra_vars` (áp lại) | **ghi đè** | `b1_gather_inputs` bước 1.5 |
| 7 | `_profile_system` override → resolve **toàn bộ** system var | **ghi đè** system var | `_resolve_system_variables()` rồi áp lại snapshot user |
| 8 | Library user var `default_value` | chỉ khi thiếu | `_resolve_user_variable_defaults` |
| 9 | Chuẩn hoá % (`abs(v) > 1` → `v/100`) | biến đổi tại chỗ | `_normalize_percent_inputs` |

Suy ra thứ tự thắng cuối (cao → thấp):

```
user input (top-level + extra_vars, áp lại ở bước 6)   ← mạnh nhất
  > system var resolve lại theo _profile_system override
    > Profile System.system_variables
      > FB get_live_context
        > Formula Global Variable
Lớp chỉ-điền-khi-thiếu: Library system var · Library user default
```

*(`extra_vars` được ghi sớm ở bước 1 nhưng bị các lớp 2–5 đè; nó chỉ thật sự thắng khi được
áp lại cùng top-level ở bước 6 — đó là nội dung bản vá #10.)*

Ba điểm thực chiến (đọc từ mã, ✅ đã sửa ở v28_14 nếu ghi "đã sửa"):

1. **`extra_vars` và top-level nay cùng lớp user.** Trước đây `extra_vars` bị Global Variable
   đè; nay được áp lại ở bước 6 nên cùng hạng với top-level.
2. **Đổi `_profile_system` ở dialog sẽ resolve lại toàn bộ system var** (bước 7). Giá trị user
   đã sửa tay được snapshot **trước** rồi áp lại **sau** ⇒ user vẫn thắng. Đây là bản vá #9.
3. **B1 gọi FB trước Library** để biến đã seed FVB không phải resolve 2 lần; `fill_missing_only`
   chỉ query những biến **chưa** có trong `self.inputs`.

Chuẩn hoá % (`_normalize_percent_inputs`): biến khai `var_type=Percent` **hoặc** tên kết thúc
`_PCT`/`_MARGIN`/`_RATE`; `abs(v) > 1` ⇒ chia 100; `v == 1` là ca mơ hồ → **cảnh báo**, không
đổi luồng.

### 6.3 B2 — prefetch

`b2_prefetch_master_data`:

1. Đọc `AL BOM Version.bom_set_snapshot` → `self.bom_items` (không có snapshot ⇒ throw).
2. `_load_accessories(bom_set)`: chọn bộ theo `al_bom_vars._accessory_set` / `accessory_set` →
   `AL Bom Set.default_accessory_set`; mỗi `AL Accessory Item` thành **một dòng** `bom_items`
   (`slug`, `item_code`, `qty` = `qty_formula` nếu có, `unit_price`, `calc_pattern` mặc định
   `COUNT`, `cost_bucket` mặc định `VL_PK`, metadata màu/vị trí/ghi chú).
3. 6 lượt batch: weight · Item Price (composite qua FB, fallback resolver cũ) · Glass Master
   (`total_thick_mm`, `glass_type`, `max_area_m2`) · Material Category (`default_scrap_pct`,
   `has_weight`) · Dynamic Item Rule (resolve theo **từng dòng**, cache theo
   `(rule_code, rule_input)`) · weight/price của item vừa resolve.
4. Dựng `self.row_literals[slug]` — xem §6.4.
5. Lưu `formula_fieldnames` từ `AL Bom Set` (JSON list) nếu có.

Cảnh báo phát sinh (thiếu giá, nhiều dòng giá, source_type chưa hỗ trợ…) đi vào túi
`bom_engine_errors` và **merge** (không ghi đè) ở B4.

### 6.4 B3 — dựng công thức

`b3_build_formulas`:

1. `formula_fields = self._formula_fieldnames or DEFAULT_FORMULA_FIELDS` với mặc định
   `width, height, qty, show_condition, item_condition_formula, rule_input_expr`.
2. Batch `AL Quantity Calc Method.input_vars` theo `calc_pattern`.
3. Với **từng** `bom_item`:
   - inject literal vào `inputs`: `{slug}__weight_per_unit`, `__unit_price`, `__calc_pattern`,
     `__glass_thick`, `__glass_type`, `__scrap_pct`;
   - pre-set 0 cho `width/height/qty/...` nếu chưa có (tránh NameError);
   - biến phụ của pattern (trừ `width/height/weight_per_unit` là tham số vị trí): lấy theo
     **line `input_vars` → `self.inputs` → row literal → 0**, inject `{slug}__{var}`, truyền
     qua dict literal thứ 5 của `lookup_calc_pattern`;
   - mỗi field có công thức ⇒ formula `{slug}__{field}`, đã normalize cross-row;
   - luôn thêm 3 formula tổng hợp: `{slug}__unit_qty` (= `lookup_calc_pattern(...)`),
     `{slug}__total_qty` (= `unit_qty × qty`, nhân thêm `(1 + scrap_pct/100)` **chỉ khi**
     `AL Bom Set.apply_scrap_pct`), `{slug}__line_total` (= `total_qty × unit_price`).
4. Mirror mọi `{slug}__{field}` thành `inputs["items"] = {slug: {field: value}}`.

**Row literal engine thật sự inject** (B2 dựng dict, B3 inject vào `inputs`) — danh sách **cố
định trong mã**:

| Key trong `row_literals[slug]` | Nguồn |
|---|---|
| `weight_per_unit` | `Item.weight_per_unit` |
| `unit_price` | `Item Price` (composite/FB) hoặc `AL Accessory Item.unit_price` |
| `calc_pattern` | `AL Bom Item.calc_pattern` |
| `glass_thick`, `glass_type` | `AL Glass Master` của mã kính đã resolve |
| `item_code` | mã thực tế sau rule/kính |
| `scrap_pct` | `AL Material Category.default_scrap_pct` |
| `has_weight`, `color`, `supplier_location`, `install_position`, `cut_angle`, `note` | metadata / màu đã resolve — **chỉ để hiển thị**, B3 ⛔ không inject `{slug}__*` cho các key này |

> ⚠ **Hệ quả cần nhớ:** thêm một tên vào `AL Variable Settings.row_literals` làm nó **hiện
> trong gợi ý**, ⛔ **không** làm engine inject `{slug}__tên_đó`. Công thức dùng biến đó sẽ ra
> **0 âm thầm** (`on_error="default"`). Settings là danh sách *gợi ý + phạm vi cảnh báo*, ⛔
> không phải cơ chế tiêm biến.

> ⚠ **Accessory `qty_formula`:** vì `qty_formula` được đặt vào `qty` của dòng phụ kiện và `qty`
> nằm trong `formula_fields`, nó được biên dịch thành `{slug}__qty`. Hệ quả: nếu một
> `AL Bom Set.formula_fieldnames` **không chứa `qty`**, công thức số lượng phụ kiện sẽ không
> được dựng. Đây là ghép nối đọc từ mã — kiểm khi cấu hình `formula_fieldnames` riêng.

### 6.5 B4 — FormulaEngine

`b4_calculate_bom_items`:

- Engine dựng qua `BOM_ENGINE_CACHE`, khoá theo **nội dung** `bom_formulas` + bộ hàm
  (`bom_safe_funcs_v1`) ⇒ sửa công thức là tự dựng engine mới; cùng công thức thì tái dùng.
- `engine.calculate(dict(self.inputs))`; lỗi từng dòng ghi vào `engine.last_errors` và **merge**
  vào `bom_engine_errors` (⛔ không chết cả BOM trừ chia 0).
- `self.inputs.update(result)`.
- `_validate_glass_max_area`: nếu `AL Glass Master.max_area_m2 > 0` và diện tích `unit_qty`
  vượt ⇒ **cảnh báo**, ⛔ không throw.
- Dựng `bom_result` mỗi dòng: `slug`, `item_code`, `width/height/qty/unit_qty/total_qty`,
  `unit_price`, `line_total`, `cost_bucket`, `unit` (ĐVT theo `calc_pattern`), `weight_per_unit`,
  `has_weight`, `trace`, `color`, vị trí/ghi chú.

Bộ hàm an toàn dùng chung B4+B6: `_engine_safe_funcs` (BASE_FUNCS + `lookup_rule`,
`lookup_calc_pattern`, `roundup`). Danh sách này là **nguồn duy nhất** cho client qua
`get_allowed_formula_functions`.

### 6.6 B5 — gom bucket

`b5_aggregate_cost_buckets`:

```
fb_buckets = _resolve_cost_buckets_via_fb()
  - chỉ bucket có source_type = "aggregate_from_items" VÀ source_config không rỗng
  - tạo binding tạm, pre_resolved = inputs + rows=[{cost_bucket, line_total}]
  - resolve_all_bindings_batch → {bucket: value}
  - source_type khác (khác rỗng) ⇒ cảnh báo "chưa hỗ trợ", quay về cộng Python
với mỗi dòng bom_result:
  bucket có trong fb_buckets ⇒ lấy giá trị FB (1 lần)
  ngược lại                 ⇒ cộng line_total
```

### 6.7 B6 — cost template

`b6_calculate_cost_template`:

1. Snapshot: nếu có `_cost_template` override → dựng từ doc `AL Cost Template`; ngược lại đọc
   `AL BOM Version.cost_template_snapshot` (không có ⇒ return).
2. Mỗi `line_code` có `calc_formula` → 1 formula; quét token `[A-Z][A-Z0-9_]{1,30}` để tìm
   bucket được tham chiếu và set default `0` cho chúng.
3. Context = `self.inputs` ⊕ `self.buckets`; engine cache `COST_ENGINE_CACHE`; chạy
   `engine.calculate({**extra_context, **self.inputs})`.
   ⚠ Vì `self.inputs` được trải **sau**, nếu một `bucket_code` trùng tên một biến trong
   `inputs` thì **giá trị trong `inputs` thắng** — công thức đọc phải bucket đó sẽ ra số khác
   bucket vừa gom. Đây là hành vi có từ trước, ⛔ không phải mới ở v28_14.
4. `gia_vat = _resolve_final_price()` — dòng `is_final_price=1`, fallback `GIA_VAT`.
   `gia_ban = _resolve_pre_vat_price()` — dòng `is_pre_vat_price=1`, fallback `GIA_BAN`.
5. Lưu `cost_template_trace[line_code]` = diễn giải công thức; lỗi vào `cost_engine_errors`.

⛔ **B6 không có `items.*`**: context chỉ là inputs ⊕ buckets. Đây là lý do profile mẫu của
Cost Template **không** gợi ý slug/row literal.

### 6.8 B7 — lưu

`b7_save_results`:

- Dựng JSON `{buckets, cost_template, cost_template_trace, lines, gia_vat, gia_ban, errors{...}}`.
- `assert_quotation_item_editable` **sát lệnh ghi** (chặn báo giá đã submit/huỷ).
- Một `frappe.db.set_value` gộp: `al_gia_vat`, `al_gia_ban`, `al_bom_result`, **`rate`** (server
  ghi để không phụ thuộc trình duyệt).
- `_recalculate_quotation_totals` — tính lại tổng Quotation, ghi bằng `set_value(...,
  update_modified=False)`, ⛔ **không** `parent.save()`.
- Một `commit`.

---

## 7. Formula Builder

### 7.1 Scope binding — một luật duy nhất

`formula_builder/api/binding_scope.py:binding_matches_scope`:

| `applies_to_doctype` | `applies_to_field` | Áp dụng khi |
|---|---|---|
| `""` | `""` | Global — mọi nơi |
| `"AL Bom Set"` | `""` | Mọi field của `AL Bom Set` |
| `"AL Bom Set"` | `"width"` | Chỉ `width` **nếu caller truyền field**; caller không truyền field ⇒ vẫn áp |
| `""` | `"width"` | ⛔ Không áp cho doctype cụ thể nào (chỉ khi caller không có doctype) |

`get_scope_bindings(doctype, field)` prefilter DB (`is_active=1`, `applies_to_doctype in ["",
doctype]`) rồi lọc field trong Python. `get_scope_bindings_multi(doctypes, field)` dùng cho
pattern **không có một doc duy nhất** (pricing theo row-context).

### 7.2 `get_live_context` — các bước

`formula_builder/api/formula_builder.py:get_live_context(scope_context_json)`:

1. `_scope(scope_json)` → `current_doctype`, `current_docname`, `fieldname` (nhận cả
   `current_field`), `child_table_field`, `row_index`…
2. `_assert_read_perm(doctype, docname)`.
3. `get_scope_bindings(doctype, field=target_field, order_by="resolve_priority asc")`.
4. `resolve_bindings_with_deps(bindings, doc)` — topo sort + resolve.
5. Mỗi binding → 1 entry `{name, label, value, type, source, source_type, is_global,
   applies_to_field}`.
6. Thêm field vô hướng của doc hiện tại (`source="field"`, `source_type="doctype_field"`) nếu
   chưa trùng tên.
7. `_build_cross_tables` — map child table → rows (dùng cho cú pháp `items.slug.field` ở widget).
8. Thêm `Formula Global Variable` có `value_source=CONSTANT` và `is_active=1`
   (`source_type="global_variable"`).
9. `_dedupe_live_variables` — gộp trùng tên; xem §7.3.
10. Trả `{success, variables, crossTables, objects, json_str}`. Lỗi ⇒ `success: False` +
    danh sách rỗng (⛔ không ném ra UI).

`objects` chỉ dành cho binding `data_type = Object` (vd `whole_doctype`); AlumGlass B1 **bỏ
qua** giá trị dict/list.

### 7.3 Dedupe trong live context

`_dedupe_live_variables`:

- Ưu tiên entry có **giá trị thật** (`value is not None`); hoà ⇒ giữ entry đầu (ổn định thứ tự).
- Entry bị bỏ **vẫn được resolve** (⛔ không xoá binding) — chỉ không lặp trong danh sách; nguồn
  bị bỏ ghi vào `duplicate_sources`.
- Phạm vi field của các entry trùng được **hợp** lại (`_merge_field_scope`: một phía rỗng ⇒
  không giới hạn).
- Mọi entry (kể cả không trùng) được chuẩn hoá qua `_with_field_scope` → `only_fields` (list) +
  `applies_to_field` (chuỗi `a|b`) để **client** lọc.

### 7.4 Resolve phụ thuộc và batch

- `data_source_registry.resolve_bindings_with_deps(bindings, doc)`: dựng graph từ
  `source_type="computed".dependencies`, topo sort, gọi handler từng binding; lỗi ⇒
  `default_value`.
- `data_source_registry` là nơi đăng ký **19 source_type built-in**; 2 source_type còn lại do
  AlumGlass đăng ký qua `hooks.py:fb_source_types` → `alumglass/fb_handlers.py`
  (`aluminum_price_composite`, `glass_master_data`). Tổng **21** trong hệ đang chạy.
- `batch_binding_resolver.resolve_all_bindings_batch(bindings, doc, pre_resolved)` gom binding
  `batchable` theo fingerprint để tránh N+1; AlumGlass B5 dùng nó cho bucket.

**21 `source_type`:**

| # | `source_type` | Nhóm | AlumGlass dùng |
|---|---|---|---|
| 1 | `constant` | built-in | `DEFAULT_ACCESSORY_CATEGORY` |
| 2 | `linked_doctype_field` | built-in | System var seed FVB (`link_field` → `target_field`) |
| 3 | `whole_doctype` | built-in | chưa |
| 4 | `child_table_aggregate` | built-in | chưa (bucket B5 dùng #19) |
| 5 | `global_default` | built-in | chưa |
| 6 | `session_variable` | built-in | chưa |
| 7 | `doctype_query` | built-in | chưa |
| 8 | `custom_function` | built-in | chưa |
| 9 | `dynamic_link` | built-in | chưa |
| 10 | `computed` | built-in | chưa |
| 11 | `pipeline` | built-in | chưa |
| 12 | `conditional` | built-in | chưa |
| 13 | `fallback_chain` | built-in | chưa |
| 14 | `matrix_lookup` | built-in | chưa |
| 15 | `reuse_formula_result` | built-in | chưa |
| 16 | `composite_key_lookup` | built-in | dự phòng cho pricing |
| 17 | `range_lookup` | built-in | chưa |
| 18 | `child_table_lookup` | built-in | chưa |
| 19 | `aggregate_from_items` | built-in | Cost Bucket B5 (`rows_source`, `key_field`, `value_field`) |
| 20 | `aluminum_price_composite` | alumglass | `COMPOSITE_MATERIAL_PRICE` (B2) |
| 21 | `glass_master_data` | alumglass | dự phòng cho rule input kính |

### 7.5 Chuẩn hoá công thức

`formula_utils/normalize.py:normalize_formula` (thứ tự quan trọng):

1. Gỡ HTML entity (`&gt;` → `>`…) **trước** mọi phép khác.
2. `strip_dollar_prefix`: `$NAME → NAME`. ⛔ Không đụng `$snap.*` và **nội dung trong nháy**
   (`'$NAME'` là dữ liệu). Quét từng ký tự để nhận biết vùng literal + nháy escape.
   *Vì sao cần:* widget chèn biến **global** dưới dạng `$NAME`; trước bản vá engine coi đó là
   syntax error dù cùng nghĩa với `NAME`.
3. `%` → `(x/100)`; `<>` → `!=`; `=` đơn → `==`; chuẩn hoá tên hàm; `and/or/not` khi gọi hàm.

### 7.6 An toàn (safe_eval)

`security/safe_eval.py` + `formula_utils/security.py`:

- Validate **một lần** lúc parse/compile (SecurityValidator + whitelist hàm + giới hạn
  subscript/iterable), rồi `eval(code, {"__builtins__": {}}, locals)` trong hot loop.
- Cấm import/exec/eval/lambda/class/def/gán/dunder/getattr-setattr-delattr.
- `engine_core` khi **restore từ cache bytecode** parse lại toàn bộ từ source (⛔ không tin
  bytecode đã serialize).

### 7.7 AlumGlass gọi FB ở đâu

| Chỗ | Hàm AlumGlass | Gọi FB | Scope |
|---|---|---|---|
| B1 — inputs | `_resolve_fb_context` | `get_live_context` | `AL Bom Set` (fallback `Quotation Item`); **không** gửi `fieldname` ⇒ mọi binding khớp doctype đều được resolve |
| B2 — giá composite | `_get_pricing_bindings` → `_fetch_composite_prices_via_fb` | `get_scope_bindings_multi` + batch resolver | `("Quotation Item", "AL Bom Item")` |
| B5 — bucket | `_resolve_cost_buckets_via_fb` | `resolve_all_bindings_batch` | binding tạm từ `AL Cost Bucket` |
| B4/B6 — tính | `_engine_safe_funcs` + `FormulaEngine` | engine | Không qua `VariableResolver` |
| Autocomplete | `_get_live_context_vars` | `get_live_context` | Có gửi `fieldname` |
| Named constant | `fb_config.get_named_constant` | binding `constant` | — |

---

## 8. Cross-row `items.<slug>.<field>`

### 8.1 Cú pháp và đường đi

| Tầng | Việc | Hàm |
|---|---|---|
| Gợi ý | Sinh `items.<slug>.<field>` / `items[n].<field>` | `adapters.build_references`; lõi widget `_ContextBuilder.build` |
| Lưu công thức | Chuẩn hoá trước khi validate | `formula_validate.normalize_cross_row` |
| Validate Bom Set | Mở rộng `known_names` | `build_known_names(cross_row_slugs, cross_row_fields)` |
| Runtime | `items.X.Y → X__Y` | `bom_orchestrator._normalize_items_ref` (dùng `normalize_global` của FB) |
| Namespace | `{slug}__{field}` + `inputs["items"]` lồng | `b3_build_formulas` |

Cả validate và runtime dùng **cùng một** hàm `normalize_global`; fallback regex chỉ khi thiếu
module FB.

### 8.2 Engine inject gì cho mỗi dòng

| Nguồn | Field có `{slug}__{field}` thật |
|---|---|
| Field công thức của dòng | `width`, `height`, `qty`, `show_condition`, `item_condition_formula`, `rule_input_expr` (theo `formula_fieldnames`) |
| Row literal B3 inject | `weight_per_unit`, `unit_price`, `calc_pattern`, `glass_thick`, `glass_type`, `scrap_pct` |
| Tổng hợp luôn tạo | `unit_qty`, `total_qty`, `line_total` |
| Field công thức tham gia DAG | chính các field ở dòng 1 (nên `items.kinh_tren.width` trỏ tới **kết quả** `kinh_tren__width`) |

**Accessory:** engine inject `qty`, `unit_qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total`;
⛔ **không** có `qty_formula` (đó là chuỗi công thức, không phải giá trị). Profile mẫu khai
`qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total` (có thể thêm `unit_qty`).

**Cost Template:** ⛔ không dùng cross-row — B6 không có context `items.*`.

### 8.3 Validate Bom Set nay dùng superset

`al_bom_set._cross_row_known_fields()` (thay đổi **chưa commit**, 2026-11-13):

```
FORMULA_FIELDS           = width, height, qty, show_condition
ENGINE_SYNTHETIC_FIELDS  = unit_qty, total_qty, line_total      (hằng ở al_bom_item.py)
row literal đang bật     = AL Variable Settings.row_literals    (qua _rule_input_known_fields)
```

⇒ `items.<slug>.unit_price`, `.glass_thick`, `.total_qty`, `.line_total`… **được validate chấp
nhận** vì engine thật sự inject. Trước bản vá, các field này **chạy đúng lúc runtime nhưng bị
chặn oan khi lưu** ("Biến không khai báo").

**Accessory Set — cùng lỗi, cùng bản vá (2026-11-13):** `al_accessory_set._cross_row_fields()`
lấy meta `AL Accessory Item` rồi hợp `ENGINE_SYNTHETIC_FIELDS`. Ba field tổng hợp
`unit_qty/total_qty/line_total` do B3 sinh nên không nằm trong meta; trước vá, gợi ý cross-row
`total_qty`/`line_total` của `P_ACCESSORY_DEFAULT` chèn được nhưng Lưu bị chặn oan. Test:
`alumglass/tests/test_accessory_cross_row_known_fields.py` (9 ca, có đối chứng âm).

⚠ Superset này **chỉ nới `known_names`**. Nó ⛔ không làm field lạ chạy được: field ngoài tập
engine inject vẫn ra **0**. Luật "chỉ khai field engine thật sự inject" **không đổi**.

Lưu ý: `AL Accessory Set` validate dùng **toàn bộ field vô hướng** của `AL Accessory Item`
(`get_scalar_fieldnames`) — permissive có chủ đích để không chặn oan; ⛔ đừng suy ra rằng mọi
field trong meta đều có giá trị lúc chạy.

### 8.4 Giới hạn

- Chỉ gợi ý được dòng **đã có** trong grid (`frm.doc`).
- Chỉ field của child table, ⛔ không đi sâu vào doctype liên kết của dòng.
- Dạng `items[n].field` **không** được engine hỗ trợ cho `rule_input_expr` (engine parse bằng
  regex `items.<slug>.<field>`), dù reference có sinh ra dạng index.
- `rule_input_expr` là vùng "gõ được nhưng không qua FormulaValidator": field/slug sai ⇒ cảnh
  báo cam khi lưu Bom Set (`_warn_rule_input_expr`, dùng `get_row_literal_names`), ⛔ **không
  chặn**, và lúc chạy vẫn là **0**.

---

## 9. Validate và gợi ý — hai universe khác nhau

| | Gợi ý (autocomplete) | Validate |
|---|---|---|
| Đường | `get_formula_context(..., include_all_sources=False)` | `get_formula_context(..., include_all_sources=True)` |
| Có bị profile lọc? | **Có** (nếu bản ghi gán profile) | ⛔ **Không** — luôn legacy đầy đủ |
| Hệ quả | Người dùng thấy ít biến hơn | Công thức cũ dùng biến ngoài profile **vẫn lưu được** |

Điểm gọi validate:

| Nơi | Cách lấy universe | Mức xử lý |
|---|---|---|
| `AL Bom Set.validate` → `_validate_child_formulas` | `build_known_names("AL Bom Set", name, slugs, superset)` | **throw** khi sai |
| `AL Accessory Set.validate` → `_validate_item_formulas` | `build_known_names("AL Accessory Set", name, slugs, meta fields **∪** `ENGINE_SYNTHETIC_FIELDS`)` | **throw** |
| `AL Cost Template.validate` | `_build_known_names()` → `get_formula_context(..., fieldname="calc_formula", include_all_sources=True)` | **msgprint** cảnh báo, ⛔ không chặn |
| Client `al_cost_template.js:validate` | `cost_template.js:fetchValidationContext` (`include_all_sources: 1`) + `validate_formula` | chặn save (`frappe.validated = false`) |
| Client `cost_template.js` khi sửa dòng | `fetchContext` (đã lọc profile) | chỉ phản hồi sớm |

`AL Cost Template` validate còn kiểm: công thức rỗng ⇒ throw; ngoặc không cân bằng ⇒ throw;
`FormulaValidator` bắt biến/hàm lạ ⇒ **cảnh báo**. `line_code` của dòng trước được cộng vào
`known_names` khi validate dòng sau.

⚠ **Tin cậy:** validate dùng chính `get_formula_context` ⇒ *mọi biến hiện trong autocomplete
đều được coi là hợp lệ*, kể cả biến không bao giờ có giá trị lúc tính. Đây là giới hạn thiết
kế, ⛔ không phải bug cần "sửa" bằng cách nới rule.

---

## 10. Thay đổi so với trước v28_14

### 10.1 Mười một lỗi đã vá (tóm tắt — chi tiết ở `docs/variable-catalog/CHANGELOG-v28_14.md` mục 2.6)

| # | Vấn đề | Sửa ở |
|---|---|---|
| 1 | `applies_to_field` vô hiệu vì widget không gửi `fieldname` | `_get_live_context_vars`, `formula_setup.js`, patch `_buildCtx` |
| 2 | Dedup "first wins" che giá trị thật | `rules.dedupe_candidates`, `_dedupe_live_variables`, legacy dedup trong `get_formula_context` |
| 3 | Cost Template thấy toàn bộ user var | Profile `P_COST_TEMPLATE_DEFAULT` (`EXCLUDE_ALL`) |
| 4 | `cost_template.js` lọc sai theo `v.source` | Bỏ lọc, inject toàn bộ `ctx.variables` |
| 5 | `FORMULA_DOCTYPE_REGISTRY` cứng trong JS | `AL Formula Field` + `get_formula_fields` |
| 6 | Row literal / common var cứng trong Python | `AL Variable Settings`; tuple cũ chỉ là fallback |
| 7 | Map offset cứng 4 tên | `AL Variable Library.source_field` / `source_link_field` |
| 8 | `AL Accessory Set.variable_set` là field chết | Adapter `variable_set` đọc Link trực tiếp |
| 9 | 1.5c ghi đè biến user vừa sửa | Snapshot + áp lại sau 1.5c |
| 10 | `extra_vars` bị Global Variable đè | `extra_vars` + top-level cùng lớp user |
| 11 | Global Variable tắt vẫn vào `inputs` | `is_active=1` trong `get_all_global_variables` |

Phụ chú: `panel_count_formula` / `qty_per_panel_formula` trên `AL Bom Item` **cố ý** không
đăng ký `AL Formula Field` — không engine nào đọc.

### 10.2 Data-driven mới

| Việc | Nguồn dữ liệu | Đọc bằng |
|---|---|---|
| Field nào có autocomplete | `AL Formula Field` | `get_formula_fields` (cache theo request) |
| Nhóm/nguồn biến gợi ý | `AL Variable Profile` + rule | `get_variable_catalog` |
| Danh sách row literal / common var | `AL Variable Settings` | adapter + `get_row_literal_names` |
| Biến hệ resolve từ đâu | `AL Variable Library.source_doctype/source_field/source_link_field` | `system_variable_resolver` |
| Field nào hợp lệ cho `rule_input_expr` | `AL Variable Settings.row_literals` | `_rule_input_known_fields` |
| Cờ "là chiều tra giá" | `AL Variable Dimension Mapping` | `_enrich_pricing_dimension` |

`system_variable_resolver` nay là **nguồn duy nhất** cho cả runtime (B1) và autocomplete
(`ctx.resolved`, `_resolve_doc_values`) — trước đây 2 bản đọc riêng, lệch cả tên biến
(`OFFSET_CROSSBAR` vs `OFFSET_DO_NGANG`).

---

## 11. API và quyền

### 11.1 Bảy endpoint

| # | Hàm | Việc | Quyền |
|---|---|---|---|
| 1 | `variable_catalog.get_variable_catalog` | Danh mục cho 1 field/ngữ cảnh | Guard doctype + read |
| 2 | `variable_catalog.get_variable_profile` | Profile đang áp cho bản ghi (hoặc `null`) | Guard doctype + read |
| 3 | `variable_catalog.preview_variable_catalog` | Admin xem trước 1 profile | Guard doctype + **read `AL Variable Profile`** |
| 4 | `variable_catalog.explain_variable` | Vì sao thấy/không thấy 1 biến; nguồn nào thắng | Guard doctype + read |
| 5 | `variable_catalog.get_row_literal_names` | Tên row literal đang bật | Đăng nhập (whitelist) |
| 6 | `formula_registry.get_formula_fields` | Registry field công thức | Đăng nhập (whitelist) |
| 7 | `api.get_formula_context` | Context autocomplete/validate (2 đường) | Guard doctype + read |

Guard dùng chung `api._assert_formula_context_doctype`: cho qua khi **đồng thời**
(1) module bắt đầu bằng `AL `, **hoặc** module `Formula Builder`, **hoặc** đúng tên
`Quotation`/`Quotation Item`; và (2) user có quyền **read** trên chính doctype. `doctype`
rỗng hoặc không tồn tại ⇒ chặn.

`preview_variable_catalog` thiếu quyền ⇒ `PermissionError` với câu *"Bạn không có quyền xem
trước danh mục biến."* `explain_variable` thiếu `variable_name` ⇒ *"Thiếu tên biến cần giải
thích."*

### 11.2 Shape và ghi chú

- `get_variable_catalog` trả `{success, profile, variables, groups, references, meta}`.
  `meta`: `total`, `excluded_by_rules`, `duplicates`, `profile_code`, `fieldname`,
  `child_table`, `row_index`, `source_kinds`. Không có profile ⇒ `profile: null`,
  `variables: []`, `meta.legacy_fallback: true`.
- `explain_variable` chạy **tất cả** adapter (kể cả nguồn bị loại) — đắt hơn catalog, chỉ dùng
  chẩn đoán. Mỗi nguồn có `selected` (qua rule?) và `kept` (thắng dedupe?); đúng **một**
  `kept=true`.
- `get_formula_context` trả `variables` đã chuẩn hoá qua `_normalize_catalog_variable` (luôn có
  `label`, `value` (`—` khi rỗng), `type`, `source`, `source_type`, `group`, `value_source`,
  `description`, `is_pricing_dimension`, `only_fields` list, `hide_all` bool).
- `include_values=False` ⇒ server đặt `value="—"` cho **mọi** biến nhưng **giữ** `has_value`.

### 11.3 Quyền của 3 DocType cấu hình

`AL Variable Profile`, `AL Variable Settings`, `AL Formula Field` mặc định chỉ **System
Manager**. Role `AL BOM Manager` **chưa** có quyền ghi — muốn giao phải sửa `permissions` trong
JSON, ⛔ đừng giả định đã có.

---

## 12. Bản đồ file / hàm

### 12.1 AlumGlass

| File | Hàm / object | Vai trò |
|---|---|---|
| `alumglass/api/__init__.py` | `calculate_bom` | Entry tính giá; quyền + async |
| | `get_formula_context` | 2 đường catalog/legacy; `include_all_sources` |
| | `_get_catalog_context` | Thử catalog, `None` ⇒ legacy |
| | `_get_live_context_vars` | Gọi FB `get_live_context`, **có** `fieldname` |
| | `_resolve_doc_values` | Resolve system var cho preview |
| | `_normalize_catalog_variable`, `_binding_scope_fields` | Chuẩn hoá shape cho JS |
| | `_resolve_variable_set_name`, `_inject_variable_set_vars` | Dò & chèn Variable Set |
| | `get_variable_set_for_bom` | Dialog "Tham số BOM" |
| | `_assert_formula_context_doctype` | Allowlist + quyền |
| | `get_allowed_formula_functions` | 3 hàm custom cho client |
| `alumglass/api/variable_catalog.py` | `get_variable_catalog`, `preview_variable_catalog`, `explain_variable`, `get_variable_profile`, `get_row_literal_names` | API catalog |
| | `_build_catalog`, `_resolve_profile_doc`, `_run_adapters` | Nhân chung |
| `alumglass/api/formula_registry.py` | `get_formula_fields` | Registry field công thức |
| `alumglass/variable_sources/registry.py` | `register_adapter`, `get_adapters` | Đăng ký adapter |
| `alumglass/variable_sources/rules.py` | `select_candidates`, `dedupe_candidates`, `build_groups`, `active_source_kinds` | Luật lọc (thuần Python) |
| `alumglass/variable_sources/context.py` | `CatalogContext`, `get_scalar_fieldnames`, `detect_slug_field` | Nạp doc/meta/dòng/Settings |
| `alumglass/variable_sources/adapters.py` | 10 adapter + `build_references` | Sinh candidate + cross-row |
| `alumglass/engine/bom_orchestrator.py` | `run` | B0→B7 |
| | `b1_gather_inputs` | Hợp đồng ưu tiên inputs |
| | `_resolve_system_variables`, `_resolve_fb_context`, `_resolve_user_variable_defaults`, `_normalize_percent_inputs` | Các lớp B1 |
| | `_load_accessories`, `b2_prefetch_master_data` | Dòng BOM + master data + row literal |
| | `b3_build_formulas`, `_normalize_items_ref`, `_parse_line_input_vars` | Dựng formula + cross-row |
| | `b4_calculate_bom_items`, `_validate_glass_max_area` | Tính + cảnh báo khổ kính |
| | `b5_aggregate_cost_buckets`, `_resolve_cost_buckets_via_fb` | Gom bucket |
| | `b6_calculate_cost_template`, `_resolve_final_price`, `_resolve_pre_vat_price` | Giá thành |
| | `b7_save_results`, `_recalculate_quotation_totals` | Ghi kết quả |
| `alumglass/al_bom_engine/formula_validate.py` | `build_known_names`, `normalize_cross_row`, `check_formula`, `validate_rule_input_expr` | Validate dùng chung |
| `alumglass/al_bom_engine/system_variable_resolver.py` | `fetch_system_vars`, `resolve_source_record_names`, `resolve_system_variable_values` | Nguồn duy nhất system var |
| `alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.py` | `FORMULA_FIELDS`, `ENGINE_SYNTHETIC_FIELDS`, `backfill_input_vars` | Hợp đồng field dòng |
| `alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.py` | `_cross_row_known_fields`, `_validate_child_formulas`, `_warn_rule_input_expr` | Validate + cảnh báo |
| `alumglass/al_bom_engine/doctype/al_accessory_set/al_accessory_set.py` | `_validate_item_formulas`, `_cross_row_fields` | Validate phụ kiện |
| `alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.py` | `validate`, `_build_known_names` | Validate cost template |
| `alumglass/fb_handlers.py` | `aluminum_price_composite`, `glass_master_data` | 2 source_type của app |
| `alumglass/public/js/formula_setup.js` | `FormulaContext`, `FormulaFields`, `_patchContextBuilder` | Cache + registry + inject biến |
| `alumglass/public/js/cost_template.js` | `validate_formula`, `fetchContext`, `fetchValidationContext`, `injectContext` | Validate + context |
| `alumglass/al_master_data/doctype/al_variable_profile/al_variable_profile.js` | nút **Xem trước danh sách biến** | Preview |

### 12.2 Formula Builder

| File | Hàm | Vai trò |
|---|---|---|
| `formula_builder/api/formula_builder.py` | `get_live_context` | Resolve binding + field + crossTables + global |
| | `_split_field_scope`, `_merge_field_scope`, `_with_field_scope`, `_dedupe_live_variables` | Chuẩn hoá phạm vi field + dedupe |
| | `validate_formula`, `get_suggestions` | API widget |
| `formula_builder/api/binding_scope.py` | `binding_matches_scope`, `get_scope_bindings`, `get_scope_bindings_multi` | Luật scope duy nhất |
| `formula_builder/api/data_source_registry.py` | `resolve_bindings_with_deps`, 19 handler | Resolve + topo |
| `formula_builder/api/source_type_registry.py` | `register_source`, `list_all` | Registry source_type |
| `formula_builder/api/batch_binding_resolver.py` | `resolve_all_bindings_batch` | Batch chống N+1 |
| `formula_builder/api/global_variable_cache.py` | `get_all_global_variables` | Cache Redis 60s, chỉ `is_active=1` |
| `formula_builder/formula_utils/engine_public.py` | `FormulaEngine` | API engine (explain, snapshot, topo…) |
| `formula_builder/formula_utils/engine_core.py` | `calculate`, `_eval_globals` | Hot loop eval |
| `formula_builder/formula_utils/normalize.py` | `normalize_formula`, `strip_dollar_prefix` | `$NAME → NAME`, `%`, `<>`, `==` |
| `formula_builder/security/safe_eval.py` | `compile_expression`, `validate_expression` | Validate 1 lần + eval an toàn |
| `formula_builder/public/js/formula_builder.js` | `_ContextBuilder.build`, `AluglassFormulaEditor._scope`, `_buildCtx` | Widget + gửi `fieldname` |

---

## 13. Migration và vận hành

### 13.1 Patch

Hai patch khai ở **`[post_model_sync]`** trong `alumglass/patches.txt` (chạy sau khi DocType đã
sync), nối tiếp: `seed_variable_catalog`, rồi `seed_bom_profile` (thêm 2026-11-13 — profile
`P_BOM_DEFAULT` cho `AL Bom Set`).

| Bước | Nội dung | Idempotent nhờ |
|---|---|---|
| Settings — common var | Seed **8** biến (`W_mm`, `H_mm`, `n_panel`, `TransomHeight_mm`, `SideLiteWidth`, `SideLiteHeight`, `installation_height_m`, `TONG_M2`) | Chỉ seed khi bảng **rỗng** |
| Settings — row literal | Seed **10** biến (9 cũ + `max_area_m2`) | Bổ sung theo **tên** còn thiếu, ⛔ không đè nhãn/thứ tự admin sửa |
| Formula Field | Seed **11** record (6 field `AL Bom Set.items`, 1 `qty_formula`, 1 `calc_formula`, 3 field cha: `AL Alert Config.trigger_condition`, `AL Quantity Calc Method.calc_fn`, `Formula Global Variable.formula_expr`) | Bỏ qua nếu `(target_doctype, child_table, fieldname)` đã có |
| Profile | Seed `P_COST_TEMPLATE_DEFAULT` (6 rule) + `P_ACCESSORY_DEFAULT` (8 rule + 1 cross_row); patch riêng `seed_bom_profile` seed `P_BOM_DEFAULT` (6 rule + 1 cross_row) | Bỏ qua nếu mã đã tồn tại; chỉ gán bản ghi đang trống |
| Gán profile | Gán cho record **đang trống** `variable_profile` của `AL Cost Template` / `AL Accessory Set`; `update_modified=False` | Chỉ gán khi cột tồn tại và giá trị rỗng |

Patch ⛔ **không** set `AL Variable Settings.default_profile`. Patch `throw` nếu chưa có DocType
`AL Variable Profile` (dấu hiệu khai sai khối patches) và `commit` ở cuối.

### 13.2 Trình tự triển khai (chưa chạy ở đâu)

```bash
# 0) backup site theo quy trình chuẩn
# 1) xác nhận site có CẢ alumglass và formula_builder
bench --site <dev> migrate          # tạo 7 DocType + cột variable_profile/source_link_field + chạy patch
bench build --app alumglass         # hooks.py đã bump formula_setup.js / cost_template.js lên v=1.2.0
bench --site <dev> clear-cache
```

Kiểm sau migrate (⛔ chưa thực hiện, đây là **kỳ vọng**):

| Kiểm | Kỳ vọng |
|---|---|
| `AL Variable Settings` | 8 common var, 10 row literal |
| `AL Formula Field` | 11 record `is_active=1` |
| `AL Variable Profile` | 3 profile mẫu |
| Patch Log | Có `seed_variable_catalog` và `seed_bom_profile` |
| `AL Cost Template` cũ | `variable_profile` đã gán nếu trước đó trống |
| Lưu công thức dùng biến ngoài profile | **Phải lưu được** |

### 13.3 Chạy lại patch

Patch idempotent:

```bash
bench --site <dev> execute alumglass.patches.v28_14.seed_variable_catalog.execute
```

Báo "chưa có doctype 'AL Variable Profile'" ⇒ kiểm `patches.txt`: patch phải ở
`[post_model_sync]`.

### 13.4 Cache — 5 tầng, đừng nhầm

| Cache | Ở đâu | TTL / invalidate |
|---|---|---|
| `Formula Global Variable` | Redis (`formula_builder:global_variables`) | 60s; invalidate từ `on_update`/`on_trash` |
| Context autocomplete | Client (`FormulaContext`) | 5 phút; **không có chỗ gọi `invalidate`** |
| Registry field | Client (`FormulaFields`) | 60s; `invalidate(doctype)` có hàm nhưng chưa gọi |
| Context Cost Template | Client (`_contextCache`) | không TTL; đổi bản ghi là đổi khoá |
| Universe validate | Client (`_validationCache`) | không TTL |
| `AL Formula Field` (server) | `frappe.local` | theo **request** |
| Document (`get_cached_doc`) | Frappe | theo request/redis của Frappe — ⛔ **không** cache kết quả catalog |

⚠ `frappe.db.set_value` **không chạy** document event ⇒ ghi Global Variable bằng đường đó
⛔ không xoá cache; TTL 60s là lưới an toàn.

### 13.5 Rollback

⛔ **Chưa có kịch bản revert đã kiểm chứng.** Cách rẻ nhất và ít rủi ro nhất là **tắt**:
`is_active=0` cho profile đang dùng (về legacy), hoặc để trống `variable_profile` trên bản ghi.
Xoá 7 DocType chỉ nên làm khi đã backup và chắc chắn không còn record nào tham chiếu.

### 13.6 Quy ước vận hành

- Profile chỉ đổi **danh sách gợi ý**; ⛔ không đổi giá trị, ⛔ không chặn công thức cũ.
- Thêm nguồn biến: 1 adapter + 1 option `source_kind` + rule. Không sửa core catalog.
- Thêm field công thức: 1 record `AL Formula Field`. Không sửa JS.
- Thêm common var / row literal: 1 dòng trong Settings. Không sửa Python — nhưng nhớ §6.4:
  thêm tên ⛔ không làm engine inject giá trị.
- Muốn giảm nhiễu autocomplete: `EXCLUDE_ALL` + rule Include tường minh.

---

## 14. Giới hạn đã biết và rủi ro

### 14.1 Mười hai giới hạn ghi trong CHANGELOG (tóm tắt, ⛔ không chép nguyên)

| # | Giới hạn | Ảnh hưởng |
|---|---|---|
| 1 | **Chưa migrate / chưa test trên site** | Chưa có bằng chứng UI + DB; chỉ test thuần + đọc mã |
| 2 | Patch gán profile hàng loạt cho record đang trống | Đổi danh sách gợi ý của dữ liệu cũ (⛔ không đổi tiền) |
| 3 | **Không có cache server** cho kết quả catalog | Mỗi lượt gọi chạy lại adapter; nhiều query |
| 4 | 3 DocType cấu hình chỉ `System Manager` | BOM Manager không tự cấu hình được |
| 5 | `invalidate()` ở client chưa có chỗ gọi | Sửa profile phải chờ 5 phút / F5 |
| 6 | `explain_variable` chạy **tất cả** adapter | Chậm; chỉ dùng chẩn đoán |
| 7 | Autocomplete bulk không gửi `fieldname`/`row_index` | Server không lọc theo field; client lọc bằng `only_fields` |
| 8 | Cross-row chỉ đúng nếu field engine thật sự inject | Gợi ý sai ⇒ tính ra 0; phụ kiện ⛔ `qty_formula` |
| 9 | `doctype_field` bỏ field text dài | Không gợi ý `width/height/qty` trên `AL Bom Item` (chúng là chuỗi công thức) |
| 10 | `AL Formula Field` chưa kiểm `fieldname` có tồn tại | Gõ sai ⇒ record hợp lệ nhưng vô dụng |
| 11 | Thay đổi `formula_builder` ở repo khác | Triển khai phải chốt **cả hai** repo |
| 12 | `cost_template_line` chỉ lọc "dòng trước" khi có `row_index` | Bulk autocomplete có thể thấy dòng **sau** ⇒ tham chiếu dòng sau ra 0/vòng |

### 14.2 Rủi ro đọc thêm từ mã (chưa có trong CHANGELOG)

| Mức | Rủi ro | Vì sao |
|---|---|---|
| 🟠 | **Row literal trong Settings ≠ biến engine inject** | Thêm tên vào Settings chỉ đổi gợi ý; `{slug}__<tên>` không tồn tại ⇒ công thức ra 0 âm thầm (§6.4) |
| 🟠 | **`doctype_field` trả tên field trần cho dòng con** | Với dòng con, namespace lúc tính là `{slug}__{field}`; tên trần không có trong `inputs`. Profile mẫu ⛔ không bật nguồn này, nhưng profile tự tạo có thể bật |
| 🟠 | **`AL Bom Set.formula_fieldnames` không chứa `qty`** | `qty_formula` của phụ kiện không được biên dịch (§6.4) |
| 🟡 | Comment `al_accessory_set.py:_validate_item_formulas` nói "KHÔNG có variable_set riêng" | Sai với hiện trạng: doctype **có** field `variable_set` và adapter `variable_set` đọc nó. Chỉ là lệch chú thích, ⛔ không đổi hành vi |
| 🟡 | B1 resolve FVB **không gửi `fieldname`** | Mọi binding khớp doctype đều được resolve — đúng thiết kế (một lần cho cả chứng từ) nhưng khác autocomplete; đừng suy ra `applies_to_field` lọc cả runtime |
| 🟡 | Cùng tên ở nhiều nguồn | Autocomplete và runtime có thể lấy từ nguồn khác nhau; `explain_variable` chỉ giải thích phía catalog, ⛔ **không** giải thích runtime |
| 🟡 | `$snap.*` / `FS-CODE.var` | ⛔ Không đi qua `VariableResolver` ở B3/B6 ⇒ không resolve trừ khi đã có biến cùng tên trong `inputs` |

### 14.3 Điều ⛔ không được dùng profile để làm

| ⛔ Không dùng để | Vì sao | Muốn chặn thật thì |
|---|---|---|
| Đổi giá trị tính toán | Runtime không đọc profile | Sửa engine/công thức |
| Chặn công thức cũ dùng biến ngoài profile | Validate dùng universe đầy đủ | Viết kiểm riêng |
| Thay đổi dữ liệu đã lưu | Profile không ghi vào chứng từ | — |
| Chặn người dùng gõ biến ngoài danh sách | Autocomplete chỉ gợi ý | Kiểm riêng nếu thật cần |

---

## 15. Đọc tiếp

| Tài liệu | Dành cho |
|---|---|
| [docs/variable-catalog/README.md](docs/variable-catalog/README.md) | Tổng quan tính năng, luồng, khái niệm |
| [docs/variable-catalog/huong-dan-su-dung-tinh-nang.md](docs/variable-catalog/huong-dan-su-dung-tinh-nang.md) | Cách dùng theo tình huống thực tế |
| [docs/variable-catalog/huong-dan-setting-bien.md](docs/variable-catalog/huong-dan-setting-bien.md) | Thao tác từng bước: profile, rule, cross-row, xem trước |
| [docs/variable-catalog/al-variable-profile.md](docs/variable-catalog/al-variable-profile.md) | Tra cứu đầy đủ `AL Variable Profile`: mọi field, 11 `source_kind`, thuật toán rule, cross-row, 4 ví dụ |
| [docs/variable-catalog/vi-du-setting-day-du.md](docs/variable-catalog/vi-du-setting-day-du.md) | Ví dụ setting đầy đủ 13 cột, cách hệ thống hiển thị từng nguồn, tắt / chỉ hiện một số biến |
| [docs/variable-catalog/nguon-bien-theo-doctype.md](docs/variable-catalog/nguon-bien-theo-doctype.md) | Tra theo từng DocType: setting ở đâu, lấy từ đâu, điều kiện gì, runtime đọc bảng nào |
| [docs/variable-catalog/api-reference.md](docs/variable-catalog/api-reference.md) | Tham số, shape trả về, quyền, ví dụ gọi |
| [docs/variable-catalog/troubleshooting.md](docs/variable-catalog/troubleshooting.md) | Triệu chứng → nguyên nhân → xử lý |
| [docs/variable-catalog/CHANGELOG-v28_14.md](docs/variable-catalog/CHANGELOG-v28_14.md) | Thay đổi theo nhóm, migration, tương thích ngược, 12 giới hạn |
| [docs/huong-dan-tinh-gia-full-flow.md](docs/huong-dan-tinh-gia-full-flow.md) | Luồng tính giá đầy đủ (quy ước tài liệu của repo) |
| [docs/design/fvb-guide-alumglass-pricing.md](docs/design/fvb-guide-alumglass-pricing.md) | Binding phục vụ tra giá composite |
| [docs/design/fvb-seed.md](docs/design/fvb-seed.md) | Seed binding từ Variable Library |
| [docs/usage/tinh-gia-bao-gia.vi.md](docs/usage/tinh-gia-bao-gia.vi.md) | Hướng dẫn dùng tính giá báo giá (tệp chuẩn): tính một dòng, giá chưa lưu, lưu, in, sự cố |
| [docs/usage/bom-calculation-dialog.vi.md](docs/usage/bom-calculation-dialog.vi.md) | Chi tiết màn hình cửa sổ 📐 Tham số BOM / 🖥️ Preview tính giá |
| [docs/usage/validate-cong-thuc-va-workflow.vi.md](docs/usage/validate-cong-thuc-va-workflow.vi.md) | Validate công thức và workflow cho người dùng |
| [docs/BAN-FULL-A-Z.md](docs/BAN-FULL-A-Z.md) | Bản A–Z triển khai alumglass ↔ formula_builder |
| [../formula_builder/docs/fb_source_type_contract.md](../formula_builder/docs/fb_source_type_contract.md) | Hợp đồng `source_type` của FB |
| [../formula_builder/docs/aggregate_from_items.md](../formula_builder/docs/aggregate_from_items.md) | `aggregate_from_items` (bucket B5) |
| [../formula_builder/docs/security_safe_eval.md](../formula_builder/docs/security_safe_eval.md) | Mô hình an toàn của engine |
| [../formula_builder/docs/Snapshot_Lifecycle_Full_Example.md](../formula_builder/docs/Snapshot_Lifecycle_Full_Example.md) | Vòng đời snapshot (`$snap.*`) |

---

*Tài liệu viết trong repo `alumglass`; lần soạn này **không commit, không push**. Khi code đổi,
sửa theo **tên hàm** (mục 12) — ⛔ đừng sửa theo số dòng, và ⛔ đừng thêm mô tả cho thứ chưa
có trong mã.*
