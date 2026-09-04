# HƯỚNG DẪN — Formula Variable Binding (FVB) a–z + ứng dụng alumglass cho tính giá

> **Trạng thái:** DRAFT — chờ Elon/Owner review (2026-09-04). CHƯA commit, CHƯA push.
> **Lưu trữ:** alumglass/docs/design — tài liệu tham chiếu "FVB là gì, hoạt động thế nào, alumglass dùng ra sao".
> **Job:** `2026-09-03_alumglass-patch3-merge-fb-platform-ph0-1`
> **Phạm vi trace:** code HIỆN TẠI của cả 2 repo — alumglass (post v28_11: B1 flip FB-first, `_get_pricing_bindings` qua `binding_scope`, `_resolve_final_price`/`_resolve_pre_vat_price` D7, seed v28_9/v28_11, `install_fb_bindings` FIX C5) + formula_builder (binding_scope, batch_binding_resolver, get_live_context, source_type_registry).
> **Doc liên quan:** `formula_builder/docs/design/fvb-single-resolution-layer.md` (§1–12 — ADR nền, đọc cùng) · `alumglass/docs/design/quotation-pricing.md` · `alumglass/docs/quotation-pricing-flow.md` · `report-bo-sung-dieu-chinh.md`

> Nội dung guide bám sát code thật (không lặp lại ADR cũ nếu code đã khác). Mọi tên hàm/doc bên
> dưới tra được trong `alumglass/engine/bom_orchestrator.py` và `formula_builder/formula_builder/api/*`.
> Ví dụ tính giá ở **§8 là SỐ LIỆU MINH HOẠ tự chọn** (đánh dấu `[MH]`), **KHÔNG phải số golden**
> — số golden CDMQ-2C/4C chỉ xuất hiện ở §8.1/§9 như *mốc regression thật*, không gán cho ví dụ.

---

## Mục lục

1. FVB là gì & vì sao có nó
2. Doctype Formula Variable Binding a–z
3. 17 source_type built-in + 2 custom alumglass
4. Scope semantics (global / doctype / doctype+field · AL Bom Set scope)
5. Batch resolution & hiệu năng
6. Test binding (Validate Config / Test Source / Test With Doc / Preview Batch)
7. Ứng dụng alumglass trong tính giá (3 tầng · FVB tham gia B1/B2/B5/B6 · seeds thật)
8. **Ví dụ tính giá đầy đủ từng bước (minh hoạ)**
9. Lưu ý vận hành

---

## 1. FVB là gì & vì sao có nó

### 1.1 Vấn đề trước FVB

Trước Phase 0–4, alumglass resolve "biến / giá / bucket" bằng code Python rải rác trong engine:

| Nhu cầu | Code cũ (trước FVB) |
| --- | --- |
| Biến hệ thống (OFFSET_FRAME, NC_SX_PCT…) | `bom_orchestrator._resolve_system_variables()` đọc AL Variable Library → source_doctype/source_field → resolve tay |
| Global constants (VAT_RATE…) | đọc Formula Global Variable cứng trong B1 |
| Giá composite (nhôm/kính theo mã đại diện) | `_fetch_composite_prices()` tự query Item Price + tự lọc dimension |
| Gom bucket chi phí | vòng lặp sum `line_total` theo `cost_bucket` trong Python |

Mỗi nguồn dữ liệu thêm mới → phải viết/duy trì 1 nhánh resolver riêng trong app. Khó mở rộng,
dễ lệch giữa các nhánh (đã từng lệch: FB-max thiếu `category` — FIX, `price_list` hardcode — finding C5).

### 1.2 Phân vai: "resolve thế nào" vs "biến nghĩa là gì"

- **FB platform (formula_builder)** trả lời **"resolve thế nào"**:
  - Doctype `Formula Variable Binding` = 1 record cấu hình nguồn dữ liệu (source_type + source_config + scope + default).
  - `source_type_registry.py` / `data_source_registry.py` = danh bạ các "loại nguồn" (17 built-in + app đăng ký thêm qua `@register_source`).
  - `formula_builder.api.formula_builder.get_live_context(scope_json)` = resolve theo scope 1 doc.
  - `formula_builder.api.batch_binding_resolver.resolve_all_bindings_batch(bindings, doc, pre_resolved)` = resolve hàng loạt binding (batch theo fingerprint).
  - `formula_builder.api.binding_scope` = filter binding theo scope (global/doctype/field).
- **App nghiệp vụ (alumglass)** trả lời **"biến nghĩa là gì"**:
  - Khai báo biến: `AL Variable Library` (var_name, source_doctype/source_field, default…).
  - Đăng ký nguồn dữ liệu riêng: `alumglass/fb_handlers.py` (`aluminum_price_composite`, `glass_master_data`).
  - Seed binding cho master data hiện tại: patch `v28_9` (D3), `v28_11` (D6, C2) + `setup/install_fb_bindings.py` (auto-seed pricing binding mỗi migrate).
  - Engine dùng binding: `bom_orchestrator.py` B1.4 / B2 / B5 / B6.

> Nguyên tắc lõi: **single resolution layer** — muốn resolve thứ gì, đừng viết code mới, hãy tạo/bật 1
> `Formula Variable Binding` trỏ đúng source_type. App chỉ giữ *ý nghĩa* biến (tên, nguồn field, default),
> platform lo *cách lấy giá trị* (topological sort, batch, cache, fallback default_value).

### 1.3 B1 flip FB-first (Phase 3a) — vì sao

Thứ tự B1 hiện tại (code `bom_orchestrator.b1_gather_inputs`, comment "Phase 3a FLIP"):

```
1.1 al_bom_vars.extra_vars
1.2 Formula Global Variable (đọc thẳng doctype — giá trị tức thời)
1.4 _resolve_fb_context()      ← FB resolve TRƯỚC (FVB theo scope AL Bom Set)
1.3 _resolve_system_variables(fill_missing_only=True)   ← legacy CHỈ fill biến chưa có
1.4b _profile_child_vars (child-table override direct-capture)
1.5 user bom_vars (ghi đè)
1.5b capture override config (_accessory_set/_profile_system/_cost_template/glass_master_map)
1.5c override profile → _resolve_system_variables() (fill_missing_only=False, ghi đè)
1.6 user-var defaults (AL Variable Library.default_value)
1.7 _normalize_percent_inputs() (suffix _PCT/_MARGIN/_RATE, value >1 → /100)
```

Trước flip thứ tự là 1.3 → 1.4 (legacy chạy trước rồi FB ghi đè cùng giá trị = resolve 2 lần).
Sau flip: biến đã có FVB seed **không** chạy legacy nữa (`fill_missing_only=True` — guard
`if var not in self.inputs`), biến **chưa** seed vẫn về resolver 1.3 như cũ → **golden-safe**.

### 1.4 Vì sao alumglass cần FVB

1. **Một nguồn sự thật** cho "lấy giá trị thế nào" — thêm nguồn mới không cần sửa engine.
2. **Tận dụng tối đa platform**: batch/cache/topological sort/default_value có sẵn, app không tự fork.
3. **Preview/Test trước khi bật** (Admin UI A3/A4) — bớt rủi ro đổi hành vi tính giá.
4. **Tắt nhanh** bằng `is_active=0` thay vì xóa code (xem §9).

---

## 2. Doctype Formula Variable Binding a–z

DocType: `formula_builder/formula_builder/doctype/formula_variable_binding/formula_variable_binding.json`.

| Field | Bắt buộc / Mặc định | Ý nghĩa & cách dùng | Ghi chú trace code |
| --- | --- | --- | --- |
| `variable_name` | reqd | Tên biến sẽ xuất hiện trong context khi resolve (vd `VAT_RATE`, `OFFSET_FRAME`, `COMPOSITE_MATERIAL_PRICE`). | Được merge vào `inputs` (B1) hoặc `pre_resolved` (B2/B5). |
| `variable_label` | — | Nhãn hiển thị (Admin, trace). | |
| `source_type` | reqd (Autocomplete) | Mã nguồn dữ liệu — danh sách từ `list_source_types()` (registry, gồm 17 built-in + 2 custom alumglass). | Quyết định handler chạy khi resolve. |
| `source_config` | JSON | Config của source_type (validate theo `config_schema` của type; form sinh động từ schema — `get_source_type_schema`). | `aluminum_price_composite`: `{price_list, material_category, pricing_mode: exact_match|multiplier_chain}`. |
| `resolve_priority` | Int = 100 | Thứ tự ưu tiên khi nhiều binding cùng variable/scope (asc). | `_get_pricing_bindings` order `resolve_priority asc`; B1 lấy giá trị "đầu tiên khác default" theo thứ tự này. |
| `batch_group` | Data | Nhóm batch tùy ý (hiếm dùng; mặc định gom theo fingerprint của handler). | Đọc trong `batch_binding_resolver`. |
| `applies_to_doctype` | Link → DocType (trống = global) | Giới hạn scope: binding chỉ resolve khi doc hiện tại thuộc doctype này (hoặc con). | B1 system-var: `AL Bom Set`. Pricing binding: trống (global, gọi trực tiếp với row context). |
| `applies_to_field` | Data | Giới hạn thêm tới 1 field của doctype. | `binding_scope` dùng để filter chính xác theo field (A5). |
| `data_type` | Select: Float/Int/Currency/Percent/Check/Data/Object | Kiểu trả về. | Map từ `AL Variable Library` qua `_DTYPE_MAP` khi seed system var (Float/Int/Currency/Check → giữ; Data/Select/Link → Data). |
| `default_value` | Data | Giá trị mặc định khi resolve lỗi/thiếu — lưới an toàn. | Engine B1 **bỏ qua chuỗi rỗng** khi merge (`_resolve_fb_context` golden-safe guard). |
| `is_global` | Check = 0 | 1 = binding áp dụng mọi scope (không cần doc context). | System var `is_global=0` + `applies_to_doctype=AL Bom Set`; constant global `is_global=1`. |
| `is_active` | Check = 1 | 0 = tắt binding mà không xóa (DB prefilter `is_active=1`). | `binding_scope.get_scope_bindings*` lọc `is_active=1`; `_get_pricing_bindings` fallback cũ cũng filter `is_active=1`. |

Bộ field mà layer platform dùng khi trả binding: `BINDING_FIELDS` trong `binding_scope.py`
(`name, variable_name, variable_label, source_type, source_config, resolve_priority,
applies_to_doctype, applies_to_field, is_global, data_type, default_value`).

**Khi nào có record FVB:** (a) seed tự động từ patch `v28_9`/`v28_11` + `install_fb_bindings.py`
sau `bench migrate` (idempotent); (b) tạo tay trên Admin; (c) migrate C2 (viết lại config cũ).
KHÔNG cần sửa code app khi thêm 1 nguồn dữ liệu mới cùng loại.

---

## 3. 17 source_type built-in + 2 custom alumglass

Danh sách built-in theo `data_source_registry.py`, gom nhóm A–F như ADR
`formula_builder/docs/design/fvb-single-resolution-layer.md` §3 (cập nhật theo registry hiện tại;
`cost_bucket_aggregate` đã deprecated & migrate sang `aggregate_from_items` — không còn count).

| Nhóm | source_type | Chức năng | batchable | Dùng trong alumglass |
| --- | --- | --- | --- | --- |
| A — Literal & System (không cần doc) | `constant` | Hằng số (VAT, hệ số) — cast theo `data_type` | ✓ | **Có** — FVB constant global cho VAT_RATE/OH_VC_PCT/OH_QLY_PCT (D3 Group 1) |
| A | `global_default` | Đọc 1 giá trị từ Global Defaults | ✓ | — |
| A | `session_variable` | user/roles/company/today/now/lang | thấp | — |
| B — Đọc doc liên kết (cần doc context) | `linked_doctype_field` | Đọc **1 field** từ doc liên kết (workhorse) | ✓ | **Có** — system vars OFFSET_*/NC_SX_PCT… scope AL Bom Set (D3 Group 2 / D6) |
| B | `whole_doctype` | Trả **toàn bộ** doc liên kết thành Object | ✓ | — (Object không vào inputs B1) |
| B | `child_table_aggregate` | sum/avg/min/max/count/list child table + filter | ✓ | — |
| B | `dynamic_link` | Target doctype động (Dynamic Link) | ✗ | — |
| C — Query & phái sinh | `doctype_query` | Query doctype bất kỳ + filters template `{doc.x}`/`{resolved.x}` + aggregate | ✓ | — |
| C | `computed` | Biến phái sinh = formula dùng resolved vars (DAG) | ✓ | — |
| D — Composite không cần code | `pipeline` | Chain nhiều bước (output N → input N+1) | ✓ (outer) | — |
| D | `conditional` | Rẽ nhánh theo runtime condition | ✗ (inner tuần tự) | — |
| D | `fallback_chain` | primary → fallback → default | ✗ | — |
| E — Ma trận / tra cứu | `matrix_lookup` | Ma trận 2D (row_key, col_key, fallback) | ✓ | — |
| E | `composite_key_lookup` | Ma trận N-chiều: key_fields động + fallback_keys + match_mode | ✓ | **Có** — 1 trong `_PRICING_SOURCE_TYPES` (B2 pricing binding ứng viên) |
| E | `aggregate_from_items` | SUMIF-style trên rows (snapshot/child_table/doctype_query/resolved) | ✓ | **Có** — B5 leaf bucket FB path + migration C2 (thay `cost_bucket_aggregate`) |
| E | `reuse_formula_result` | Dùng lại kết quả formula/BOM/config khác | ✓ | — |
| F — Escape hatch | `custom_function` | Gọi hàm Python module whitelist | ✗ | — |

**Custom alumglass** (`alumglass/fb_handlers.py`, đăng ký qua `@register_source` — hooks `fb_source_types`):

| source_type | label | config_schema | batch/fingerprint/cache | Cách dùng |
| --- | --- | --- | --- | --- |
| `aluminum_price_composite` | Aluminum Price (Composite Key) | `{price_list, material_category, pricing_mode: exact_match\|multiplier_chain}` | batchable · fingerprint `"aluminum_price_composite:{price_list}|{category}"` · cache ttl 300 | Tra giá nhôm/vật tư theo composite key (màu/xuất xứ/độ dày/bề mặt) qua `AL Variable Dimension Mapping` → Item Price. `exact_match` dùng chung `composite_pricing.best_partial_match` với nhánh fallback. |
| `glass_master_data` | Glass Master Data | `{glass_code}` | batchable · fingerprint `"glass_master_data:{glass_code}"` · cache ttl 3600 | Tra `total_thick_mm`/`glass_type` từ AL Glass Master (cho Dynamic Item Rule input). Đăng ký sẵn; engine B2 hiện đọc AL Glass Master bằng batch DB query trực tiếp. |

> Count built-in: 3+4+2+3+4+1 = 17. Không tính custom 2. `cost_bucket_aggregate` đã xóa khỏi
> `fb_handlers.py` sau C2 — grep `cost_bucket_aggregate` hiện rỗng ở handlers/hooks/tests.

---

## 4. Scope semantics

### 4.1 Bộ ba `is_global` + `applies_to_doctype` + `applies_to_field`

`formula_builder/api/binding_scope.py` định nghĩa luật khớp (`binding_matches_scope`, dùng chung bởi
preview/get_live_context và `_get_pricing_bindings` — A5 chống fork luật lọc):

| Cấu hình | Scope thực tế | Khớp khi |
| --- | --- | --- |
| `applies_to_doctype=""` + `is_global=1` | **Global** — mọi doc | luôn đúng (2 vế scope rỗng) |
| `applies_to_doctype="X"`, `applies_to_field=""` | **Doctype X** | doc hiện tại thuộc X |
| `applies_to_doctype="X"`, `applies_to_field="f"` | **Doctype X + field f** | doc thuộc X **và** scope có field khớp `f` |
| multi-doctype | OR giữa các doctype | `binding_matches_any_doctype` (`filter_bindings_for_scope_multi`) |

### 4.2 `get_live_context(scope_json)` — resolve theo 1 doc

Chữ ký (`formula_builder/api/formula_builder.py::get_live_context`):
`scope_context_json` mang `{"current_doctype", "current_docname"}` (+ tuỳ chọn `fieldname`/`current_field`
để lọc theo field). Luồng: `get_scope_bindings(doctype, field)` → load doc (trừ `new-`) →
`resolve_bindings_with_deps` (topological sort + fallback default_value) → build `variables`
(Object → objects dict + placeholder), gộp scalar field của doc (`source="field"`), `crossTables`,
legacy Formula Global Variables → trả `{success, variables, crossTables, objects, json_str}`.

### 4.3 AL Bom Set scope trong engine alumglass

`bom_orchestrator._resolve_fb_context()` chọn scope:

```
scope_doctype = "Quotation Item"; scope_docname = quotation_item_name
nếu resolve được AL Bom Set (qua AL BOM Version → AL BOM → bom_set):
    scope_doctype = "AL Bom Set"; scope_docname = bom_set.name
```

**Vì sao "AL Bom Set"?** Chuỗi `Quotation Item → AL BOM → AL BOM Version → AL BOM → AL Bom Set`;
AL Bom Set là doc duy nhất có **link trực tiếp** tới AL Profile System (`profile_system`) và
AL Product Type (`product_type`) — chính là 2 nguồn của system variable FVB (D3). Quotation Item
không có link này nên scope cũ không resolve được.

Merge chỉ nhận **scalar** (bỏ dict/list, chuỗi rỗng) — Object từ `whole_doctype` không vào `inputs`;
giá trị từ BINDING (`source != "field"`) được coerce float khi là số, doc field giữ type gốc.
Binding lỗi → default `""` bị bỏ → resolver 1.3 (Variable Library) giữ giá trị thật (golden-safe).

> Lưu ý override profile (`_profile_system`): FVB không biết override (scope vẫn Bom Set mặc định),
> nên B1 bước 1.5c resolve LẠI toàn bộ system vars theo profile override
> (`_resolve_system_variables()` full, không fill-missing) — override thắng FB. OPT-IN: không có
> override → không chạy nhánh này.

---

## 5. Batch resolution & hiệu năng

### 5.1 `resolve_all_bindings_batch(bindings, doc, pre_resolved)`

`formula_builder/api/batch_binding_resolver.py`. Luồng chính:

1. **Split** danh sách binding theo khả năng batch (`batchable` của source type).
2. **Group by fingerprint**: binding cùng handler + cùng `fingerprint_fn(cfg)` → 1 nhóm.
3. Mỗi nhóm batch: gọi handler dạng batch một lần (`resolve_batch` / `resolve_batch_query`) với
   `pre_resolved` (context đã có sẵn). Nhóm **không batch**: resolve từng binding 1-1
   (`execute_individual`) → **N+1**.
4. `_apply_transform` qua `safe_eval` khi config có transform.

`pre_resolved` là context chìa khóa: engine B2 build `row_ctx` mỗi dòng BOM
(`inputs + item_code + price_base_item + category + row:{...}`) rồi gọi batch resolve — nhờ đó
1 binding `aluminum_price_composite` (global) resolve được giá cho **từng item_code** khác nhau.

### 5.2 Fingerprint & cache

- `fingerprint_fn` (handler đăng ký) → chuỗi định danh nhóm, vd
  `aluminum_price_composite:{price_list}|{category}`. Binding cùng fingerprint = cùng 1 query/1 lần.
- `supports_cache` + `default_cache_ttl`: kết quả handler được cache (alumglass: pricing ttl 300s,
  glass ttl 3600s).

### 5.3 Preview Batch Groups (Admin A4)

Nút **Preview Batch Groups** → endpoint `preview_batch_groups` gọi `preview_groups` của batch
resolver: liệt kê binding sẽ resolve thành bao nhiêu nhóm, nhóm nào batch/individual trước khi
bật thật. Dùng bắt buộc khi chuẩn bị binding per-line (xem §6/§9).

### 5.4 Hệ quả hiệu năng (quy tắc vàng)

- Dùng source **batchable** (constant, linked_doctype_field, doctype_query, aggregate_from_items,
  composite_key_lookup, aluminum_price_composite…) khi resolve theo **nhiều dòng / nhiều doc**.
- **Tránh** `custom_function` / `pipeline` / `conditional` / `fallback_chain` cho binding **per-line
  trên BOM lớn** — inner chạy tuần tự / N+1, không batch hóa được.

---

## 6. Test binding (Admin UI)

Form `Formula Variable Binding` (JS `formula_variable_binding.js`, module FB_ADMIN):

| Nút | Endpoint / nguồn | Làm gì | Dùng khi |
| --- | --- | --- | --- |
| **Validate Config** | `validate_source_config` theo `config_schema` (registry) | Kiểm tra `source_config` khớp schema của source_type trước khi lưu | Sau khi sửa JSON config |
| **Test Source** (không doc) | `test_data_source` | Build binding tối thiểu + gọi handler với config hiện tại | Kiểm tra nguồn có chạy được không khi chưa có doc |
| **Test With Doc** | `test_data_source_with_doc` | Load doc thật (scope đã chọn) + resolve context đầy đủ rồi test | Kiểm tra trên doc thật (vd AL Bom Set có link profile thật) |
| **Preview Batch Groups** | `preview_batch_groups` | Xem binding sẽ resolve thành nhóm batch nào | Trước khi bật binding per-line |

Nguồn danh sách type / schema: `source_type_registry.list_source_types()`,
`get_source_type_schema(source_type)` — form `source_config_editor_html` sinh động
(checkbox/enum/number/JSON textarea). Autocomplete `source_type` lấy từ `list_source_types()`.

> Quy trình đề xuất trước khi bật binding thật (nhất là binding pricing per-line):
> Validate Config → Test Source → Test With Doc → Preview Batch Groups → bật `is_active=1` → chạy
> golden gate (CDMQ-2C=22,717,289 / CDMQ-4C=47,430,808, dung sai <1,000).

---

## 7. Ứng dụng alumglass trong tính giá

### 7.1 Kiến trúc 3 tầng

```
┌─ Tầng 3 — CẤU HÌNH (FVB records, master data) ─────────────────────────────┐
│  Formula Variable Binding: constant globals · system vars · pricing · bucket │
│  AL Variable Library / AL Profile System / AL Product Type / AL Bom Set      │
│  AL Cost Template / AL Cost Bucket / AL Pricing Dimension + Mapping          │
└───────────────┬──────────────────────────────────────────────────────────────┘
┌─ Tầng 2 — PLATFORM formula_builder (resolve "thế nào") ─────────────────────┐
│  get_live_context · binding_scope · batch_binding_resolver ·                 │
│  source_type_registry / data_source_registry · FlexibleFormulaEngine         │
└───────────────┬──────────────────────────────────────────────────────────────┘
┌─ Tầng 1 — ENGINE alumglass (BomOrchestrator B0→B7) ─────────────────────────┐
│  b1_gather_inputs(1.4 _resolve_fb_context) · b2(_fetch_composite_prices_via_ │
│  fb) · b3/b4 FormulaEngine · b5(_resolve_cost_buckets_via_fb) · b6 cost temp. │
│  b7 _resolve_final_price/_resolve_pre_vat_price → al_gia_vat/al_gia_ban       │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Điểm FVB tham gia vào 7 phase

| Phase | Điểm tham gia FVB / FB | Hàm engine | Ghi chú |
| --- | --- | --- | --- |
| **B1.4** | `get_live_context` scope AL Bom Set → global constant + system variable | `_resolve_fb_context()` | FB-first sau flip Phase 3a; 1.3 fill-missing |
| **B2** | Pricing binding `COMPOSITE_MATERIAL_PRICE` → `resolve_all_bindings_batch` row-context | `_fetch_composite_prices_via_fb()` → `_get_pricing_bindings()` | Handler `aluminum_price_composite` exact_match |
| **B5** | Leaf Cost Bucket `source_type="aggregate_from_items"` + `source_config` hợp lệ | `_resolve_cost_buckets_via_fb()` | Chưa có source_config → sum Python (default hiện tại) |
| **B6** | `FlexibleFormulaEngine` (FB) + `custom_functions` | `b6_calculate_cost_template()` | lookup_calc_pattern/lookup_rule/roundup |
| **B7** | Không FVB — resolve cờ is_final_price/is_pre_vat_price | `_resolve_final_price()`/`_resolve_pre_vat_price()` | Cờ nằm trên AL Cost Template Item snapshot |

### 7.3 Seeds thật (trace từ patch + hooks)

| Nguồn | Patch / Setup | Seed gì | Cấu hình binding |
| --- | --- | --- | --- |
| Global constants | `patches/v28_9/seed_fvb_from_variable_library.py` (D3, Group 1) | Mọi Formula Global Variable (is_active, value_source=CONSTANT, kiểu số) → vd `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` | `source_type="constant"`, `source_config={"value": cval}`, `applies_to_doctype=""`, `is_global=1`, `default_value=constant_value` |
| System vars 2 doctype nguồn | D3 Group 2 (v28_9) | AL Profile System → `OFFSET_FRAME/OFFSET_GLASS/OFFSET_FIXED/OFFSET_DO_NGANG` (link `profile_system`); AL Product Type → `NC_SX_PCT/NC_LD_PCT/PROFIT_MARGIN` (link `product_type`) | `source_type="linked_doctype_field"`, `source_config={link_field, target_doctype, target_field}`, `applies_to_doctype="AL Bom Set"`, `is_global=0`, `resolve_priority=100`, dtype từ `_DTYPE_MAP` |
| System vars FULL | `patches/v28_11/seed_fvb_full_from_variable_library.py` (D6) | Tổng quát hóa D3: mọi system var có `source_doctype+source_field` mà AL Bom Set có link field (dò bằng `system_variable_resolver.resolve_source_link_fields`) → seed FVB; **không** có link → KHÔNG seed, log "D6 FALLBACK", engine 1.3 lo | `linked_doctype_field`, scope AL Bom Set, không chain_link_lookup; idempotent `_binding_exists`/`_other_binding_exists` |
| Bucket handler cũ | `patches/v28_11/migrate_cost_bucket_aggregate_to_aggregate_from_items.py` (C2) | FVB `cost_bucket_aggregate` → viết lại `aggregate_from_items` | `source_config = {rows_source:"snapshot", snapshot_doctype:"AL BOM Version", snapshot_name:"{{resolved.bom_version}}", snapshot_field:"bom_set_snapshot", rows_path:"items", aggregate:"sum", value_field:<sum_field cũ>, filters:[[k,"=",v]…]}` |
| **Pricing binding** | `setup/install_fb_bindings.py` (auto-seed trong `hooks._after_migrate`/`_after_install`) | `COMPOSITE_MATERIAL_PRICE` | `source_type="aluminum_price_composite"`, `source_config={pricing_mode:"exact_match", price_list:<ĐỘNG>}`, `applies_to_doctype=""`, `is_global=1`, `data_type="Currency"`, `default_value="0"` |

**FIX C5 (price_list động):** binding pricing KHÔNG hardcode `price_list` — lúc seed
`install_composite_pricing_binding()` điền bằng `_resolve_seed_price_list()` →
`bom_orchestrator._default_price_list()` (Selling Settings `selling_price_list`, fallback
"Standard Selling") — cùng nguồn nhánh Python fallback → 2 đường không thể lệch số khi bảng giá đổi.
Idempotent: get-or-update theo `{source_type, variable_name}`.

> **Trạng thái hiện tại (sau Phase 0 E + FIX C5):** `_fetch_composite_prices_via_fb` đã có binding
> → đường FB-max là đường chạy chính; `_fetch_composite_prices()` (Python) chỉ là lưới an toàn nếu
> binding bị inactive/xóa. Ghi chú "FVB pricing chưa seed → fallback" trong `quotation-pricing-flow.md`
> §2.2/§6 là **cũ**, không còn đúng từ khi có `install_fb_bindings.py`.

---

## 8. Ví dụ tính giá đầy đủ từng bước (minh hoạ)

> ⚠️ **SỐ LIỆU MINH HOẠ `[MH]`** — tự chọn, nhất quán toán học nội bộ giữa các bước,
> **KHÔNG phải số golden**, không đại diện cho giá thật của bất kỳ sản phẩm nào.
> Golden thật CDMQ-2C = 22,717,289 VND / CDMQ-4C = 47,430,808 VND (dung sai <1,000) chỉ dùng làm
> **mốc regression** (§9), KHÔNG gán cho ví dụ này. Ví dụ giản lược hình học (không mô phỏng
> mitre/khấu trừ profile thật) nhưng giữ đúng ĐƯỜNG engine (B0→B7) và ĐÚNG điểm FVB tham gia.

### Bước 0 — Sản phẩm, kích thước & master data `[MH]`

Sản phẩm: **Cửa đi nhôm mở quay 1 cánh `CD1C-MH`**. Người dùng nhập trong dialog Quotation:

| Biến user | Giá trị `[MH]` |
| --- | --- |
| `W_mm` | 1000 |
| `H_mm` | 2000 |
| `n_panel` | 1 |
| `aluminum_color` | WHITE |
| `aluminum_origin` | IMPORT |
| `aluminum_thickness` | 20 |
| `aluminum_surface` | POWDER_COATED |
| `installation_height_m` | 3 (không nhập → lấy default 3 ở B1.6) |

Master data liên quan (khai trong AL BOM → AL Bom Set → snapshot của AL BOM Version):

| Master data `[MH]` | Trường quan trọng |
| --- | --- |
| AL Bom Set `BOM-SET-MH-1C` | `product_type=DOOR-MH`, `profile_system=MINH-55`, `variable_set=VS-MH-1C`, `default_accessory_set=ACC-MH-1C` |
| AL Product Type `DOOR-MH` | `nc_sx_pct=8`, `nc_ld_pct=12`, `profit_margin=10` |
| AL Profile System `MINH-55` | `offset_frame=50`, `offset_glass=50`, `offset_fixed=50`, `offset_do_ngang=50` (child `system_variables` đồng bộ 4 giá trị) |
| Formula Global Variable | `VAT_RATE=10`, `OH_VC_PCT=3`, `OH_QLY_PCT=3` (value_source=CONSTANT, is_active) |
| AL Variable Library user var | `installation_height_m` default `"3"` |
| AL Cost Bucket | `VL_NHOM`, `VL_KINH`, `VL_VTP`, `VL_PK` (leaf) |
| AL Accessory Set `ACC-MH-1C` | tay_nam 150,000 · khoa 250,000 · ban_le 80,000 (per cái) |

Bom Set items (snapshot `bom_set_snapshot`) — 12 dòng:

| slug | item_code | category | calc_pattern | width expr (mm) | height expr (mm) | qty/formula | unit_price nguồn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| khung_ngang_tren | NHOM-XF-MH-20 | NHOM | LENGTH_TO_WEIGHT | `W_mm` = 1000 | — | 1 | Item Price |
| khung_ngang_duoi | NHOM-XF-MH-20 | NHOM | LENGTH_TO_WEIGHT | `W_mm` = 1000 | — | 1 | Item Price |
| khung_dung | NHOM-XF-MH-20 | NHOM | LENGTH_TO_WEIGHT | `H_mm` = 2000 | — | 2 | Item Price |
| canh_ngang_tren | NHOM-XF-CANH-20 | NHOM | LENGTH_TO_WEIGHT | `W_mm - 2*OFFSET_FRAME` = 900 | — | 1 | Item Price |
| canh_ngang_duoi | NHOM-XF-CANH-20 | NHOM | LENGTH_TO_WEIGHT | `W_mm - 2*OFFSET_FRAME` = 900 | — | 1 | Item Price |
| canh_dung | NHOM-XF-CANH-20 | NHOM | LENGTH_TO_WEIGHT | `H_mm - 2*OFFSET_FRAME` = 1900 | — | 2 | Item Price |
| kinh | KINH-MH-24 | KINH | AREA_M2 | `W_mm - 2*OFFSET_FRAME - 2*OFFSET_GLASS` = 800 | `H_mm - 2*OFFSET_FRAME - 2*OFFSET_GLASS` = 1800 | 1 | Item Price |
| gioang | GIOANG-MH-10 | VTP | LENGTH_M | `2*(kinh.width + kinh.height)` = 5200 | — | 1 | Item Price |
| vit | VIT-MH-4x25 | VTP | COUNT | — | — | 20 | Item Price |
| tay_nam | PK-TAY-NAM | PK | COUNT | — | — | 1 | Accessory Set (unit_price) |
| khoa | PK-KHOA-1 | PK | COUNT | — | — | 1 | Accessory Set |
| ban_le | PK-BAN-LE | PK | COUNT | — | — | `lookup_rule('RULE-BANLE-QTY', H_mm)` = 3 | Accessory Set |

> Ghi chú: item gioang/vit/tay_nam/khoa/ban_le thuộc nhóm dòng COUNT/LENGTH_M — pattern không dùng
> `weight_per_unit`; phụ kiện giá lấy thẳng từ AL Accessory Item (`unit_price` override trong B2),
> không qua composite pricing. Nhôm/kính giá qua FB pricing binding (§8.5).

### Bước 1 — Dialog quotation → `al_bom_vars` JSON

Dialog "Tham số BOM" lưu thẳng các biến user thành JSON (đúng dạng engine đọc ở B1 — test
`test_bom_orchestrator.py` dùng dạng phẳng này):

```json
{
  "W_mm": 1000,
  "H_mm": 2000,
  "n_panel": 1,
  "aluminum_color": "WHITE",
  "aluminum_origin": "IMPORT",
  "aluminum_thickness": 20,
  "aluminum_surface": "POWDER_COATED",
  "installation_height_m": 3,
  "extra_vars": {}
}
```

Các override key `_accessory_set` / `_profile_system` / `_cost_template` / `glass_master_map`
CHỈ xuất hiện khi người dùng đổi khác default của BOM (OPT-IN — quotation.js "Chỉ lưu khi user đổi
khác default BOM"). Ví dụ này không đổi gì → dùng default của AL Bom Set.

### Bước 2 — B0: version pinning

`bom_orchestrator.b0_version_pinning()`: Quotation Item `al_bom=BOM-MH-1C` → AL BOM Version active
v1 → snapshot dùng để tính:
- `bom_set_snapshot` (12 dòng BOM + accessories),
- `cost_template_snapshot` (AL Cost Template `CT-MH-01`, xem Bước 9),
- `pricing_dimension_snapshot` (map dimension → custom fieldname trên Item Price).

### Bước 3 — B1: gather inputs (FB-first)

`b1_gather_inputs()` thực hiện theo thứ tự §1.3. Kết quả từng biến (giá trị sau normalize % B1.7):

| variable | Giá trị thô | Giá trị cuối B1 | Nguồn / FVB tham gia | Scope binding |
| --- | --- | --- | --- | --- |
| `W_mm`, `H_mm`, `n_panel` | 1000 / 2000 / 1 | 1000 / 2000 / 1 | 1.5 al_bom_vars (user) | — |
| `aluminum_*` | WHITE/IMPORT/20/POWDER | như user | 1.5 al_bom_vars | — |
| `installation_height_m` | 3 | 3.0 | 1.6 default AL Variable Library (user chưa truyền? — ở đây truyền thẳng) | — |
| `VAT_RATE` | 10 | **0.10** | 1.2 Formula Global Variable **+ 1.4 FVB `constant` global** (D3 Group 1) | global |
| `OH_VC_PCT` | 3 | **0.03** | 1.2 + 1.4 FVB `constant` global | global |
| `OH_QLY_PCT` | 3 | **0.03** | 1.2 + 1.4 FVB `constant` global | global |
| `OFFSET_FRAME` | 50 | 50 | 1.4 FVB `linked_doctype_field` (AL Profile System MINH-55 qua `bom_set.profile_system`) + 1.4b child-table override 50 | AL Bom Set |
| `OFFSET_GLASS` | 50 | 50 | như trên | AL Bom Set |
| `OFFSET_FIXED` | 50 | 50 | như trên | AL Bom Set |
| `OFFSET_DO_NGANG` | 50 | 50 | như trên | AL Bom Set |
| `NC_SX_PCT` | 8 | **0.08** | 1.4 FVB `linked_doctype_field` (AL Product Type DOOR-MH qua `bom_set.product_type`) | AL Bom Set |
| `NC_LD_PCT` | 12 | **0.12** | như trên | AL Bom Set |
| `PROFIT_MARGIN` | 10 | **0.10** | như trên | AL Bom Set |

> Điểm mấu chốt: `OFFSET_*`/`NC_*`/`PROFIT_MARGIN` KHÔNG chạy legacy 1.3 nữa — FVB đã seed
> (D3/D6) nên `get_live_context` (scope AL Bom Set, doc `BOM-SET-MH-1C`) resolve và merge trước;
> legacy 1.3 `fill_missing_only=True` chỉ fill biến chưa có (không biến nào thiếu trong ví dụ này).
> Child-table override (1.4b) ghi lại cùng giá trị 50 — không đổi kết quả.
> Normalize % (1.7): mọi biến suffix `_PCT/_MARGIN/_RATE` có giá trị >1 → chia 100 (idempotent).

### Bước 4 — B2: prefetch master data + resolve giá composite qua FB

`b2_prefetch_master_data()` — 6 batch query (weights, prices, glass masters, material categories,
dynamic rules, resolved items). Nhánh giá: `_fetch_composite_prices_via_fb(all_price_items)`:

- `_get_pricing_bindings()` → `binding_scope.get_scope_bindings_multi(
  doctypes=("Quotation Item","AL Bom Item"),
  source_types=("composite_key_lookup","aluminum_price_composite"),
  order_by="resolve_priority asc")` → trả 1 binding active: **COMPOSITE_MATERIAL_PRICE** (global).
- Với mỗi item_code, build `row_ctx` = `inputs + {item_code, price_base_item, category, row:{...}}`
  rồi gọi `resolve_all_bindings_batch(bindings, doc=self._qi_doc, pre_resolved=row_ctx)`.
- Handler `aluminum_price_composite` (mode `exact_match`) tra Item Price theo composite key
  (WHITE/IMPORT/20/POWDER_COATED) + `material_category`; lấy giá trị số đầu tiên ≠ default `0`.
- Không có binding → `None` → fallback `_fetch_composite_prices()` (hiện không xảy ra vì
  `install_fb_bindings` đã seed; giữ là lưới an toàn).

Kết quả giá đơn vị `[MH]` (price_list = Selling Settings):

| slug | item_code | unit_price (VND) | Nguồn |
| --- | --- | --- | --- |
| khung_* | NHOM-XF-MH-20 | 100,000/kg | FB pricing binding (composite khớp đủ 4 chiều) |
| canh_* | NHOM-XF-CANH-20 | 100,000/kg | FB pricing binding |
| kinh | KINH-MH-24 | 1,000,000/m² | FB pricing binding |
| gioang | GIOANG-MH-10 | 5,000/m | Item Price (không composite → "trần") |
| vit | VIT-MH-4x25 | 500/cái | Item Price |
| tay_nam / khoa / ban_le | PK-* | 150,000 / 250,000 / 80,000 | AL Accessory Item.unit_price (override trong row_literals) |

### Bước 5 — B3: build formulas

`b3_build_formulas()` — với mỗi dòng BOM, bơm literal `{slug}__{field}`
(`weight_per_unit`, `unit_price`, `calc_pattern`, `glass_thick`, `glass_type`, `scrap_pct`…),
thêm formula từ `formula_fields` (width/height/qty… — normalize `items.X.Y` → `X__Y` qua
`normalize_global`, KHÔNG DotToSubscript), và **3 formula tổng hợp**:

```
{slug}__unit_qty  = lookup_calc_pattern({slug}__calc_pattern, {slug}__width,
                                        {slug}__height, {slug}__weight_per_unit[, {extra}])
{slug}__total_qty = {slug}__unit_qty * {slug}__qty
{slug}__line_total= {slug}__total_qty * {slug}__unit_price
```

`extra` = input_vars của pattern (dict-positional tham số 5) — ví dụ này không dùng pattern phụ.
Các pattern chuẩn trong `formula_handlers.py`:
`LENGTH_TO_WEIGHT = (w/1000)*tlr` · `LENGTH_M = w/1000` · `AREA_M2 = (w/1000)*(h/1000)` · `COUNT = 1`.

Ví dụ formula thật của vài dòng (sau normalize):

| name | formula |
| --- | --- |
| `khung_dung__width` | `H_mm` |
| `khung_dung__unit_qty` | `lookup_calc_pattern(khung_dung__calc_pattern, khung_dung__width, khung_dung__height, khung_dung__weight_per_unit)` |
| `kinh__width` | `W_mm - 2*OFFSET_FRAME - 2*OFFSET_GLASS` |
| `kinh__height` | `H_mm - 2*OFFSET_FRAME - 2*OFFSET_GLASS` |
| `kinh__unit_qty` | `lookup_calc_pattern(kinh__calc_pattern, kinh__width, kinh__height, kinh__weight_per_unit)` |
| `gioang__width` | `2*(kinh__width + kinh__height)` |
| `ban_le__qty` | `lookup_rule('RULE-BANLE-QTY', H_mm)` |

### Bước 6 — B4: tính bom items (FormulaEngine)

`b4_calculate_bom_items()` — FormulaEngine tính DAG các formula trên; kết quả per dòng
(`unit_qty`, `total_qty`, `unit_price`, `line_total` + trace):

| slug | unit_qty | qty | total_qty | unit_price | **line_total** | cost_bucket |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| khung_ngang_tren | 1.000 kg | 1 | 1.00 | 100,000 | **100,000** | VL_NHOM |
| khung_ngang_duoi | 1.000 kg | 1 | 1.00 | 100,000 | **100,000** | VL_NHOM |
| khung_dung | 2.000 kg | 2 | 4.00 | 100,000 | **400,000** | VL_NHOM |
| canh_ngang_tren | 0.900 kg | 1 | 0.90 | 100,000 | **90,000** | VL_NHOM |
| canh_ngang_duoi | 0.900 kg | 1 | 0.90 | 100,000 | **90,000** | VL_NHOM |
| canh_dung | 1.900 kg | 2 | 3.80 | 100,000 | **380,000** | VL_NHOM |
| kinh | 1.440 m² | 1 | 1.44 | 1,000,000 | **1,440,000** | VL_KINH |
| gioang | 5.200 m | 1 | 5.20 | 5,000 | **26,000** | VL_VTP |
| vit | 1 cái | 20 | 20 | 500 | **10,000** | VL_VTP |
| tay_nam | 1 cái | 1 | 1 | 150,000 | **150,000** | VL_PK |
| khoa | 1 cái | 1 | 1 | 250,000 | **250,000** | VL_PK |
| ban_le | 1 cái | 3 | 3 | 80,000 | **240,000** | VL_PK |

Kiểm tra: khung_dung `2.00kg × 2 = 4.00kg × 100,000 = 400,000` ✓ · kinh `0.8×1.8 = 1.44 m² × 1,000,000 = 1,440,000` ✓
· ban_le `lookup_rule('RULE-BANLE-QTY', 2000) = 3` ✓.

### Bước 7 — B5: aggregate cost buckets

`b5_aggregate_cost_buckets()` — cộng `line_total` theo `cost_bucket`:

| bucket | Giá trị |
| --- | ---: |
| VL_NHOM | 1,160,000 |
| VL_KINH | 1,440,000 |
| VL_VTP | 36,000 |
| VL_PK | 640,000 |
| **TONG_VL (tổng)** | **3,276,000** |

> Path FB cho bucket (nếu bật): `_resolve_cost_buckets_via_fb()` đọc AL Cost Bucket
> (`bucket_code/bucket_role/source_type/source_config`); bucket nào có `source_type="aggregate_from_items"`
> **và** `source_config` hợp lệ → resolve qua `resolve_all_bindings_batch` với
> `pre_resolved["rows"] = [{cost_bucket, line_total}…]` (rows_source="resolved"), gom theo key_field;
> bucket nào chưa config → vẫn sum Python. **Cấu hình hiện tại chưa set source_config**
> (seed gốc) → path sum Python là default (golden-safe). Không tự suy default config khi bật
> (tránh đổi semantics golden — xem §9 gating).
>
> Cấu hình FVB `aggregate_from_items` sau migration C2 (nếu dùng) có dạng:
> `{rows_source:"snapshot", snapshot_doctype:"AL BOM Version", snapshot_name:"{{resolved.bom_version}}",
> snapshot_field:"bom_set_snapshot", rows_path:"items", aggregate:"sum", value_field:"line_total",
> filters:[[key,"=",val]…]}`.

### Bước 8 — B6: cost template (FlexibleFormulaEngine)

`b6_calculate_cost_template()` — snapshot `CT-MH-01` (từ `cost_template_snapshot` của AL BOM
Version; override `_cost_template` nếu có). Build `global_formulas` từ item snapshot, parse token
để set default 0 cho bucket được tham chiếu (loại token prefix `TONG_/GIA_/PROFIT/VAT/DON_GIA` —
đây là dòng kết quả DAG), `extra_context = inputs + buckets`, chạy `FlexibleFormulaEngine`
với `custom_functions = {lookup_calc_pattern, lookup_rule, roundup}`, `on_error="default"`,
`default_value=0`.

Snapshot items `CT-MH-01` `[MH]` (giữ cờ D7):

| line_code | calc_formula | is_final_price | is_pre_vat_price |
| --- | --- | --- | --- |
| TONG_M2 | `(W_mm/1000)*(H_mm/1000)` | 0 | 0 |
| TONG_VL | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` | 0 | 0 |
| NC_SX | `NC_SX_PCT * TONG_VL` | 0 | 0 |
| NC_LD | `NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` | 0 | 0 |
| TONG_NC | `NC_SX + NC_LD` | 0 | 0 |
| OH_VC | `OH_VC_PCT * TONG_VL` | 0 | 0 |
| OH_QLY | `OH_QLY_PCT * (TONG_VL + TONG_NC)` | 0 | 0 |
| TONG_OH | `OH_VC + OH_QLY` | 0 | 0 |
| GIA_THANH | `TONG_VL + TONG_NC + TONG_OH` | 0 | 0 |
| PROFIT | `PROFIT_MARGIN * GIA_THANH` | 0 | 0 |
| GIA_BAN | `GIA_THANH + PROFIT` | 0 | **1** |
| DON_GIA_M2 | `GIA_BAN / TONG_M2` | 0 | 0 |
| VAT | `VAT_RATE * GIA_BAN` | 0 | 0 |
| GIA_VAT | `GIA_BAN + VAT` | **1** | 0 |

`lookup_rule('RULE-HEIGHT-MULT', 3)` = **1.0** (nhỏ hơn ngưỡng cao) — nên NC_LD không nhân thêm.

`cost_result` (sau DAG) + trace diễn giải:

| line_code | Giá trị (VND) | Trace ngắn |
| --- | ---: | --- |
| TONG_M2 | 2.00 m² | (1.0 × 2.0) |
| TONG_VL | 3,276,000 | 1,160,000+1,440,000+36,000+640,000 |
| NC_SX | **262,080** | 8% × TONG_VL(3,276,000) = 262,080 |
| NC_LD | **393,120** | 12% × TONG_VL(3,276,000) × 1.0 = 393,120 |
| TONG_NC | **655,200** | 262,080 + 393,120 |
| OH_VC | **98,280** | 3% × TONG_VL(3,276,000) = 98,280 |
| OH_QLY | **117,936** | 3% × (3,276,000 + 655,200) = 117,936 |
| TONG_OH | **216,216** | 98,280 + 117,936 |
| GIA_THANH | **4,147,416** | 3,276,000 + 655,200 + 216,216 |
| PROFIT | **414,741.60** | 10% × GIA_THANH(4,147,416) = 414,741.60 |
| GIA_BAN | **4,562,157.60** | GIA_THANH + PROFIT |
| DON_GIA_M2 | **2,281,078.80** | GIA_BAN ÷ 2.00 m² |
| VAT | **456,215.76** | 10% × GIA_BAN(4,562,157.60) |
| GIA_VAT | **5,018,373.36** | GIA_BAN + VAT |

> Ghi chú: % đã normalize (B1.7) nên công thức dùng `0.08 × TONG_VL`; renderer JS hiển thị lại
> dạng "8% × TONG_VL(3,276,000) = 262,080" từ `cost_template_trace` (build lúc tính với ctx đầy đủ).

### Bước 9 — B7: save + resolve giá theo cờ (D7)

`b7_save_results()` — resolve giá KHÔNG hardcode line_code:

- `_resolve_final_price()`: dòng `is_final_price=1` → `GIA_VAT` → `cost_result["GIA_VAT"]` = **5,018,373.36**
  (không có dòng flag → fallback `cost_result["GIA_VAT"]` — golden-safe).
- `_resolve_pre_vat_price()`: dòng `is_pre_vat_price=1` → `GIA_BAN` → `cost_result["GIA_BAN"]` = **4,562,157.60**
  (fallback `GIA_BAN`).
- Ghi 1 lần `set_value("Quotation Item", …, {al_gia_vat, al_gia_ban, al_bom_result})` + **1 commit**
  duy nhất. `al_bom_result` JSON gồm `buckets`, `cost_template`, `cost_template_trace`, `lines`,
  `gia_vat`, `gia_ban`, `errors` (structured — 1 dòng lỗi không chết cả BOM).
- ConfigSnapshot CHỈ tạo khi **submit** Quotation (`doc_events on_submit` → `quotation_events`),
  KHÔNG tạo lúc tính.

| Field Quotation Item | Giá trị engine lưu | Hiển thị làm tròn |
| --- | ---: | ---: |
| `al_gia_ban` | 4,562,157.60 | 4,562,158 |
| `al_gia_vat` | 5,018,373.36 | 5,018,373 |

### Bước 10 — Tổng kết & sơ đồ FVB tham gia

Chuỗi số từ dialog tới giá bán:

```
W_mm=1000, H_mm=2000, WHITE/IMPORT/20/POWDER  ──►  B0 pin v1 snapshot
   │
B1  FB resolve (FVB): OFFSET_*=50 · NC_SX_PCT=8→.08 · NC_LD_PCT=12→.12 ·
    PROFIT_MARGIN=10→.10 · VAT_RATE/OH_VC_PCT/OH_QLY_PCT=10/3/3→.10/.03/.03
   │
B2  COMPOSITE_MATERIAL_PRICE (FB binding) ──► NHOM 100,000/kg · KINH 1,000,000/m²
   │
B3/B4  unit_qty → total_qty → line_total (per dòng) ──► TONG VL_NHOM 1,160,000 · VL_KINH 1,440,000
   │                                                       VL_VTP 36,000 · VL_PK 640,000
B5  bucket sum ──► {VL_NHOM…} (FB aggregate path khi bật source_config)
   │
B6  FlexibleFormulaEngine (cost template CT-MH-01 + lookup_rule) ──► GIA_THANH 4,147,416
   │                                                                    PROFIT 414,741.60
B7  _resolve_final_price → al_gia_vat 5,018,373.36 · _resolve_pre_vat_price → al_gia_ban 4,562,157.60
```

| Bước | FVB / FB tham gia | Kết quả số `[MH]` |
| --- | --- | ---: |
| B0 | — | version v1 snapshot |
| B1 | FVB constant + linked_doctype_field (scope AL Bom Set) | %, offsets, decimals |
| B2 | `COMPOSITE_MATERIAL_PRICE` (aluminum_price_composite, global, resolve_all_bindings_batch row-context) | giá 100,000 / 1,000,000 |
| B3/B4 | FormulaEngine (FB, không phải FVB) | line_total 100,000…1,440,000 |
| B5 | `aggregate_from_items` (bật khi source_config) / sum Python | VL_* tổng 3,276,000 |
| B6 | FlexibleFormulaEngine + lookup_rule/roundup | GIA_THANH 4,147,416 · GIA_VAT 5,018,373.36 |
| B7 | — (cờ is_final_price/is_pre_vat_price) | al_gia_ban/al_gia_vat |

---

## 9. Lưu ý vận hành

1. **`is_active=0` là lưới an toàn** — muốn tắt 1 binding tạm thời (nghi lệch số, đang debug),
   tắt `is_active` thay vì xóa record. Mọi layer lọc `is_active=1` (binding_scope, fallback cũ).
   Pricing binding tắt → `_fetch_composite_prices_via_fb` không có binding → trả `None` →
   engine quay về `_fetch_composite_prices()` (hành vi cũ, vẫn chạy đúng).

2. **Golden gate trước khi bật binding mới / đổi config**: chạy CDMQ-2C (kỳ vọng **22,717,289** VND)
   và CDMQ-4C (**47,430,808** VND), dung sai <1,000 VND (test `test_bom_orchestrator.py`). Đây là
   mốc regression THẬT — ví dụ §8 là số minh hoạ, không thay thế golden.

3. **`bench migrate` bắt buộc** để chạy patch `v28_9`/`v28_10`/`v28_11` (seed FVB D3/D6, migrate C2,
   field sync) + `install_fb_bindings` auto-seed trong `hooks._after_migrate`. Site cài app trước
   khi có các patch này: `bench migrate` mới tạo đủ field + seed (idempotent).

4. **Preview Batch Groups trước khi bật binding per-line**: xem binding sẽ tạo bao nhiêu nhóm
   batch / nhóm nào chạy individual. Với BOM nhiều dòng, binding không batchable → N+1
   (xem §5.4).

5. **KHÔNG dùng `custom_function`/`pipeline` cho binding per-line BOM lớn** — inner chạy tuần tự,
   không batch, dễ timeout/quá tải khi tính async nhiều quotation song song.

6. **B5 bucket FB path chỉ bật khi `source_config` hợp lệ trên AL Cost Bucket** — KHÔNG tự suy
   default config (tránh đổi semantics golden). Hiện seed gốc chưa set config → sum Python là
   default. ⚠ **GATING (trong code, chưa quyết — cần Elon/Owner duyệt):** giữ vocabulary
   AL Cost Bucket + handler resolve là khuyến nghị; đổi hẳn sang FVB (bỏ vocabulary bucket) là
   quyết định thiết kế cần Owner xác nhận.

7. **Override & scope**: override `_profile_system` làm B1.5c resolve lại toàn bộ system vars
   (thắng FVB của profile default). `_cost_template` override dùng snapshot build trực tiếp từ
   AL Cost Template (không snapshot version). Mọi override OPT-IN — thiếu key = hành vi cũ.

8. **Price_list binding đồng bộ động**: không hardcode — `install_fb_bindings` tự sync
   `price_list` theo Selling Settings mỗi migrate (FIX C5). Nếu đổi bảng giá chính, chạy lại
   migrate hoặc gọi `install_composite_pricing_binding()` để binding không lệch nhánh fallback.

9. **FVB chỉ là cấu hình, không phải code** — thêm nguồn dữ liệu cùng loại = thêm record binding +
   seed idempotent, không sửa engine. Sửa semantics (nghĩa biến) thì sửa master data
   (Variable Library / Profile / Product Type), KHÔNG sửa binding.

10. **Bắt buộc cập nhật knowledge sau thay đổi** schema/quyết định thiết kế liên quan FVB →
    cập nhật `alumglass/docs/design/*` + `formula_builder/docs/design/fvb-single-resolution-layer.md`
    (ADR nền) cùng commit code (quy tắc chung của workspace).
