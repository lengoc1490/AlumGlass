# Quotation Pricing — kiến trúc FB-max (B1/B2/B5 + security + snapshot)

> **Trạng thái:** Implemented (engine R9) — phần FVB seed đang chờ D3 · 2026-08-22
> **Job:** `2026-08-16_alumglass-sprint1-quotation`
> **Thiết kế gốc:** `al_review.md` §5 Phase B + §12 · `docs/design/p1-pricing-dimension-versioning.md` · `docs/design/p2-async-bom-calculation.md`

## Vấn đề

`BomOrchestrator` (7-phase B0–B7) ban đầu tự viết hầu hết resolver thay vì dùng
`formula_builder` (FB) đã cung cấp sẵn — dẫn tới **nhiều nguồn resolve song song**:

| Phase | Trước (tự viết) | Vấn đề |
|---|---|---|
| B1 | `_resolve_system_variables()` query tay AL Variable Library | Trùng `session_variable`/`global_default`/`computed` của FB |
| B2 | `_fetch_composite_prices`/`_match_composite_price` query + match tay Item Price | Trùng `composite_key_lookup` + handler `aluminum_price_composite` |
| B5 | `b5_aggregate_cost_buckets()` loop Python `buckets[bk] += line_total` | Trùng `aggregate_from_items`; `source_type`/`source_config` của AL Cost Bucket **dormant** (validate có, resolve không) |

Ngoài ra, công thức từ DB chạy qua `eval()`/`exec()` trần (R1
`al_quantity_calc_method.py:36`, R2 `al_cost_template.py:42`) — **RCE blocker**
(xem Security model bên dưới).

## Nguyên tắc bao trùm

> Một nguồn dữ liệu, một nơi resolve, cấu hình thay code. Mọi thứ FB/core đã có
> thì gọi, không tự build lại. **Golden test CDMQ-2C (`GIA_VAT ≈ 22.717.289đ`) +
> CDMQ-4C phải pass sau mỗi thay đổi.**

---

## B1 — `get_live_context` + FVB seed (⚠ chờ D3 seed)

`bom_orchestrator.b1_gather_inputs()` (qua `_resolve_fb_context()`) gọi
`formula_builder.api.formula_builder.get_live_context(scope_context_json)`
(`formula_builder.py:274`) với scope context:

```json
{"current_doctype": "Quotation Item", "current_docname": "<qi_name>"}
```

- **Global binding** (`VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT`…) + **system
  variable** (OFFSET_*, NC_* từ AL Profile System / AL Product Type) được FB
  resolve tự động (topological sort theo dependency, fallback `default_value`).
- Kết quả FB merge vào `inputs` — **chỉ scalar** (variable dạng object/dict/list
  bị skip, không nhét vào `inputs`).
- **Fallback backward-compat:** FB trả rỗng / ném exception → `{}` → engine
  resolve từ **AL Variable Library** như cũ. Không mất biến UI.

**FVB seed — CHỜ D3 (DEV1):** để `get_live_context` trả đủ binding, cần seed
`Formula Variable Binding` từ AL Variable Library (1 lần, qua `patches/`). Phần
seed này do DEV1 làm song song (D3) — engine đã sẵn sàng, seed về sau không phá
golden (khi FVB chưa có, fallback Variable Library giữ nguyên giá trị).

---

## B2 — `composite_key_lookup` + `BatchBindingResolver`

`bom_orchestrator.b2_prefetch_master_data()` (qua `_fetch_composite_prices_via_fb`)
dùng `formula_builder.api.batch_binding_resolver.resolve_all_bindings_batch(bindings, ...)`
(`batch_binding_resolver.py:533`) cho binding kiểu **`composite_key_lookup`**
(`data_source_registry.py:2460`):

- **Composite key N-dim** khai báo ngay trong `source_config`:
  `key_fields` (item_code + các `custom_pd_*` từ Pricing Dimension), `value_field`
  (`price_list_rate`), `match_mode` (`exact` / `case_insensitive` /
  `multiplier_chain`), `fallback_keys` (rút dần chiều khi không khớp đủ).
- Handler `aluminum_price_composite` (đã `@register_source`, `batchable=True`,
  fingerprint theo `price_list`) gom toàn bộ item_code cùng fingerprint → **1
  query Item Price** cho cả batch.
- **Fallback:** không có binding (FVB chưa seed / config rỗng) → resolver cũ
  `_match_composite_price` chọn dòng khớp nhiều field nhất (giữ golden).
- **Pricing Dimension versioning (P1):** `_get_dim_fieldnames()` đọc
  `pricing_dimension_snapshot` (đóng băng trên AL BOM Version) **trước**, chỉ
  fallback query live cho version cũ chưa backfill — composite key dùng đúng
  config tại thời điểm publish.

---

## Override config từ al_bom_vars (V6 P4 — A5/A7)

Dialog tham số (ItemParamDialog) cho phép user chỉnh **Bom Set / Accessory Set /
Profile System / Cost Template / kính** (V6 Phase 1). Giá trị khác default được
lưu vào `al_bom_vars` dạng **override keys** prefix `_` + `glass_master` (user var):

| Key | Ý nghĩa | Engine đọc ở đâu |
|---|---|---|
| `_accessory_set` | Bộ phụ kiện thay thế (fallback `accessory_set` cũ) | `b1` → `accessory_set_code` → `b2._load_accessories()` |
| `_profile_system` | Hệ profile thay thế | `b1.1.3` (`_resolve_system_variables`) → OFFSET_FRAME/GLASS/DO_NGANG từ profile đã chọn; re-resolve sau FB scope |
| `_cost_template` | Cost Template thay thế | `b6` → build snapshot trực tiếp từ AL Cost Template doc |
| `glass_master` | Kính override (line kính, global) | `b2` → glass_data thick/type + item_code line kính → RULE-NEP/KEO resolve theo kính đã chọn |
| `glass_master_map` | Kính override **theo từng vị trí** (V6 P7) — map `{rep_code: glass_master}` (rep_code = mã đại diện `default_glass_master`, gom từ `glass_groups`); **ưu tiên hơn `glass_master` global** khi có | `b2` → per-line glass_data cho line kính có rep trong map → RULE-NEP/KEO resolve theo kính từng dòng |
| `_bom_set` / `_bom_name` / `_brand` | Meta BOM (lưu tham chiếu, engine dùng để resolve BOM) | — |

**Nguyên tắc OPT-IN:** không có key nào → engine giữ 100% hành vi cũ
(golden 2C/4C không đổi). Mọi override chỉ áp dụng khi có key trong `al_bom_vars`.

**A7 — Rule lookup nẹp kính / keo (verified):** line nẹp kính dùng
`item_selection_mode=Rule` + `item_rule=RULE-NEP-GLASSTHICK` (THRESHOLD theo
`glass_thick`), line keo dùng `RULE-KEO-GLASSTYPE` (LOOKUP theo `glass_type`).
`rule_input_expr` trỏ `items.<kinh_slug>.glass_thick/glass_type`. Engine b2 build
`glass_data` từ `default_glass_master` của line kính (hoặc kính override) →
`_resolve_rule_input_for_code` → `_resolve_dynamic_item` (AL Dynamic Item Rule) →
line resolve ra item_code + đơn giá. CDMQ-2C: 24mm/LOWE → C3211-20/KEO-TT-01;
override KINH-DON-8 → C3209-20/KEO-TT-02. Config rule + kính đều phải có trên
AL Bom Set / AL Glass Master để lookup chạy đúng.

### V6 P7/P8 — Hợp đồng API dialog + renderer (DEV2, 2026-08-25)

**`get_variable_set_for_bom` trả thêm `glass_groups`** (V6 P7):
mảng nhóm line kính theo mã đại diện, dạng
`[{rep, label, default}]` — `rep` = mã `default_glass_master` của AL Bom Set line
(hay bỏ trùng), `label` = `glass_name` từ AL Glass Master, `default` = rep.
Dialog dựng **N selector "Kính theo vị trí"** (N = số nhóm), mỗi selector mặc định
= `default`. Đổi kính thật → lưu `glass_master_map: {rep: actual}` vào
`al_bom_vars`. Chưa có `glass_groups` → dialog fallback biến global `glass_master`
(backward-compat).

**`get_result_display` trả thêm per line vật tư** (V6 P8):
`weight_per_unit` (kg/m, chỉ vật tư `has_weight` NHÔM/THÉP/INOX), `has_weight`
(bool), `unit`/`output_unit` (từ `calc_pattern`), `trace` (string trace 2 tầng,
đã có sẵn cho cost template). Renderer chung hiển thị 11 cột Chi tiết vật tư +
5 cột Chi phí chế tạo (Khoản mục | Công thức | Diễn giải | Giá trị | ĐVT).
Chưa có field → renderer hiện "—" (không crash).

**`get_result_display` trả thêm cho cost template** (V6 P8):
`cost_template_trace` (dict `{line_code: trace_string}` do engine B6 dựng sẵn từ
`calc_formula` + giá trị thực tế) và `cost_template_units` (dict
`{line_code: unit}`). Frontend dùng trace có sẵn (không rebuild), fallback
`_build_trace` khi chưa có.

**Child table `AL Profile System Variable`** (V6 P1c): biến hệ thống bổ sung theo
profile system. Khi có, `get_variable_set_for_bom` trả thêm các biến này → dialog
hiển thị editable + nút "Khôi phục mặc định biến hệ thống". Hiện tại chỉ có 4
Float `offset_*` hardcode trên AL Profile System — chưa có child table (làm ở
Phase 1c).

### V6 Phase 0b — Chuẩn hoá % lưu phần trăm nguyên (DEV2, 2026-08-25)

**Vấn đề:** trước đây system var phần trăm (PCT/MARGIN/RATE) lưu dạng **decimal**
(0.08/0.12/0.16/0.10/0.03/0.03) → trace hiển thị "0.08 × …" gây nhầm với người
dùng (tưởng 0.08%, thực tế là 8%).

**Giải pháp — lưu PHẦN TRĂM NGUYÊN:**
- Data (seed + patch): system var phần trăm lưu **số nguyên** — `NC_SX_PCT=8`,
  `NC_LD_PCT=12`, `PROFIT_MARGIN=16`, `VAT_RATE=10`, `OH_VC_PCT=3`,
  `OH_QLY_PCT=3`. Phạm vi: `AL Variable Library.default_value`,
  `AL Product Type.nc_pct/nc_ld_rate/profit_margin`,
  `Formula Global Variable.constant_value`.
- Engine: `_normalize_percent_inputs()` chạy cuối `b1_gather_inputs()` — biến
  `key.endswith(_PERCENT_VAR_SUFFIXES) = ("_PCT", "_MARGIN", "_RATE")` và
  `abs(value) > 1` → chia 100 (`8 → 0.08`) trước khi dùng. Giá trị ≤ 1 (đã là
  decimal, kể cả dữ liệu cũ/FB-max) giữ nguyên → **golden-safe**:
  `8/100 = 0.08` (giá trị không đổi so với trước).
- Trace hiển thị: giá trị decimal < 1 trong trace string → frontend
  `format_trace` đổi thành phần trăm (0.08 → "8%") → diễn giải dạng
  **"8% × TONG_VL(1,000,000) = 80,000"**.
- Patch `patches/v28_9/normalize_percent_system_vars.py` — idempotent (chỉ đổi
  value ≤ 1 → phần trăm nguyên đích, giữ nguyên value > 1), `update_modified=False`.

**Fix hạ tầng:** `patches.txt` của alumglass nằm **sai vị trí** (app root thay vì
`alumglass/alumglass/patches.txt`) → `bench migrate` KHÔNG bao giờ chạy patch
alumglass (các patch trước chạy thủ công). Đã `git mv` về đúng vị trí package
root → migrate chạy được toàn bộ 4 patch (idempotent), log vào `tabPatch Log`.

### V6 Phase 1a — AL Quantity Calc Method seed đầy đủ (DEV2, 2026-08-25)

Seed 12 pattern chuẩn theo **v28.md §C.4** (hybrid DB-first + PATTERN_FORMULAS
fallback) + 2 alias legacy:

| # | code | Tên tiếng Việt | input_vars | output_unit | group |
|---|---|---|---|---|---|
| 1 | LENGTH_TO_WEIGHT | Tính kg theo mét dài | width, weight_per_unit | kg | A-Tuyến tính |
| 2 | LENGTH_M | Tính mét dài | width | m | A-Tuyến tính |
| 3 | HEIGHT_M | Tính mét cao | height | m | A-Tuyến tính |
| 4 | LENGTH_TO_PIECES | Cắt thanh thành đoạn | width, piece_length | cái | A-Tuyến tính |
| 5 | AREA_M2 | Tính diện tích m2 | width, height | m2 | B-Diện tích |
| 6 | AREA_TO_WEIGHT | Tính kg từ diện tích | width, height, weight_per_unit | kg | B-Diện tích |
| 7 | PERIMETER_M | Tính chu vi mét | width, height | m | C-Chu vi |
| 8 | VOLUME_M3 | Tính thể tích m3 | width, height, depth | m3 | D-Thể tích |
| 9 | COUNT | Đếm số cái | (không) | cái | E-Đếm |
| 10 | SET | Đếm số bộ | (không) | bộ | E-Đếm |
| 11 | COUNT_PER_LENGTH | Số cái theo khoảng cách | width, spacing | cái | E-Đếm |
| 12 | COUNT_PER_AREA | Số cái theo diện tích | width, height, area_per_piece | cái | E-Đếm |
| — | AREA / LENGTH_ONLY | alias legacy (backward-compat) | như AREA_M2 / LENGTH_M | m2 / m | B / A |

- `_calc_methods()` (seed_demo_data.py) chuyển sang **UPSERT idempotent**: tạo nếu
  chưa có, cập nhật metadata (tên tiếng Việt, `calc_formula` hiển thị, `input_vars`,
  `output_unit`, `group`, `sort_order`) nếu đã có — calc_fn giữ nguyên → golden-safe.
- `input_vars` là JSON field: `get_valid_dict` Frappe v14 chặn list cho mọi field
  non-Table → seed truyền/set dạng **JSON string** (`json.dumps`); khi load Frappe
  parse về list. So sánh list vs list (load) → idempotent.
- `group` dùng matrix **A-Tuyến tính / B-Diện tích / C-Chu vi / D-Thể tích / E-Đếm**
  — cập nhật `_GROUP_BY_KEY` (formula_handlers) khớp cho built-in fallback.
- `get_available_patterns()` đọc đủ 14 pattern từ DB (không fallback name code),
  filter theo category qua `_derive_pattern_filter` (has_weight / has_dimensions /
  requires_glass_master).
- **Test cập nhật:** `test_calc_pattern_hybrid.py` #2 — AREA_M2 giờ có DB record →
  positive cache (không còn negative). Fallback vẫn cover bởi #4 (calc_fn rỗng).
- Pattern có biến phụ (`piece_length`/`depth`/`spacing`/`area_per_piece`) → UI AL Bom
  Item tự hiện field dựa trên `input_vars` (Phase 1d đọc tiếp).

---

## B5 — `aggregate_from_items` + `on_error=default` + structured errors

### B5.1 Gom cost bucket qua FB

`b5_aggregate_cost_buckets()` — LEAF bucket có
`source_type="aggregate_from_items"` (`data_source_registry.py:2726`, sumif-style:
`table` + `key_field`/`value_field` + `filter_key`) resolve qua
`_resolve_cost_buckets_via_fb()`; bucket không có `source_config` → **sum Python
fallback** (bảo toàn golden). Bucket AGGREGATE (`TONG_VL`, `GIA_THANH`…) do B6
`FlexibleFormulaEngine` tính như hiện tại.

### B5.2 `on_error="default"` — 1 dòng lỗi KHÔNG chết cả BOM

B4 (`b4_calculate_bom_items`) và B6 (`b6_calculate_cost_template`) chuyển
`on_error="raise"` → **`on_error="default"`** + `default_value=0`:

- 1 formula lỗi (vd NameError biến thiếu) → value `0` + **error capture** vào
  `bom_engine_errors` / `cost_engine_errors`; các dòng khác vẫn tính bình thường.
- **Div-by-zero LUÔN fatal** bất kể mode (`errors.py:131`) → phải chặn ở nguồn
  data (default_value hợp lệ), không recover.
- `on_error` chỉ nhận giá trị hợp lệ `{"raise", "null", "default"}` — **không có
  "continue"**.

### B5.3 Structured errors → al_bom_result (V5: snapshot chỉ khi submit)

`b7_save_results()` ghi toàn bộ lỗi structured vào `al_bom_result` qua
`result_json.errors` (cấu trúc `{"bom_items": {...}, "cost_template": {...}}`) —
báo giá có lỗi vẫn lưu kết quả các dòng tính được + danh sách lỗi để dev tra cứu.
**Single commit** toàn lần chạy.

**V5 (Owner 2026-08-23):** `b7_save_results()` KHÔNG còn tạo `ConfigSnapshot` —
chỉ ghi `al_gia_vat`/`al_gia_ban`/`al_bom_result` + commit. `ConfigSnapshot`
chỉ được tạo khi **submit Quotation** qua `doc_events` on_submit
(`alumglass.api.quotation_events.on_submit`): mỗi dòng có `al_bom_result` →
1 snapshot (`inputs_json` = `al_bom_vars`, `result_json` = `al_bom_result`,
`bom_version` = `al_bom_version`), link vào `al_config_snapshot`. Chạy trong
transaction submit (atomic) — không commit riêng. Lý do: tránh snapshot rác mỗi
lần bấm tính; snapshot là dấu vết của báo giá ĐÃ chốt khi submit.

---

## Security model — safe_eval đóng cả 2 app

> Phát hiện 2026-08-16: **cả alumglass lẫn formula_builder đều dính RCE qua
> `eval()`** — `eval(expr, {"__builtins__": {}}, {})` KHÔNG chặn object traversal
> (`().__class__.__base__.__subclasses__()` → tìm subprocess/os). Owner chốt: fix
> đưa VÀO formula_builder (nền tảng chung) — 1 fix gộp đóng RCE **cả 2 app**.

- **`formula_builder/security/safe_eval.py`** — `SafeExpression`,
  `ExpressionPolicy`, `compile_expression()` (validate 1 lần lúc build) + `.eval()`
  nhanh hot loop. 3 site FB đã chuyển SafeExpression: filter
  (`data_source_registry.py:556`), condition (`:1062`), transform
  (`batch_binding_resolver.py:224`).
- **FormulaEngine hot loop** (`engine_public.py:452`, `engine_core.py:776/878/953/1005`)
  còn `eval(compiled[name], ...)` NHƯNG bytecode `_compiled` LUÔN do
  `FormulaParser.parse()` + `compile()` sinh — parse chạy `SecurityValidator`
  (AST whitelist: chặn `import/eval/exec/lambda/class/def/comprehension` + dunder
  attr + mọi attr ngoài `get/keys/values/items/to_dict` + tên nguy hiểm
  `__import__/__class__/...`) + `_eval_globals` bỏ `__builtins__` → traversal
  **chặn từ lúc compile**. Hardening khuyến nghị: thêm `getattr/setattr/delattr`
  vào `FORBIDDEN_NAMES`.
- **Alumglass (đóng R1/R2):** `al_quantity_calc_method.py` `_calc_fn_cache` +
  `al_cost_template.py` eval trần đổi sang import `formula_builder.security.safe_eval`.
  DoD: `grep -rn "eval(\|exec(" alumglass/` **VÀ** `formula_builder/` → rỗng (trừ test).
- **Test:** `alumglass/tests/test_safe_eval_a3.py` + FB `tests/test_security.py`
  phủ payload `__import__('os')`, `().__class__.__mro__`, `getattr(obj,'x')` —
  chứng minh payload RCE bị chặn ở **cả 2 app**.

---

## Snapshot & async (tóm tắt — chi tiết design riêng)

### P1 — Pricing Dimension snapshot

`AL BOM Version.pricing_dimension_snapshot` (Long Text, read_only, no_copy) chụp
toàn bộ `AL Pricing Dimension` + `AL Variable Dimension Mapping` lúc publish;
`_guard_published_immutability()` mở rộng guard cả 3 snapshot (BOM Set, Cost
Template, Pricing Dimension). Engine `_get_dim_fieldnames()` đọc snapshot trước,
live fallback (warning) cho version cũ; backfill patch `patches/v28_9/`. Xem
`docs/design/p1-pricing-dimension-versioning.md`.

### P2 — Async BOM (BOM lớn)

`Formula Global Variable.ASYNC_BOM_THRESHOLD` (default 150): `calculate_bom` đếm
dòng từ `bom_set_snapshot` → ≤ ngưỡng chạy sync (giữ nguyên code path, golden
không đổi), > ngưỡng `frappe.enqueue(queue="long", timeout=600)` +
`frappe.set_user(user)` trong worker + `publish_realtime("alumglass_bom_calc_done")`.
3 field trạng thái trên Quotation Item: `al_calc_status`, `al_calc_job_id`,
`al_calc_error`. Xem `docs/design/p2-async-bom-calculation.md`.

---

## File thay đổi

| File | Thay đổi |
|---|---|
| `alumglass/engine/bom_orchestrator.py` | `_resolve_fb_context()` (B1), `_fetch_composite_prices_via_fb()` (B2), `_resolve_cost_buckets_via_fb()` (B5), `on_error="default"`, `b7_save_results()` ghi errors; **V6**: `_normalize_percent_inputs` (0b), `_build_trace`/`_round_num`/`cost_template_trace` + per-line `unit`/`weight_per_unit`/`has_weight`/`trace` (1e) |
| `alumglass/api/__init__.py` | `get_formula_context()` lấy từ `get_live_context` (FB-first + dedup); `calculate_bom` async (P2); **V6**: `glass_groups` trong `get_variable_set_for_bom`, trace/unit/weight per line + `cost_template_trace`/`cost_template_units` trong `get_result_display` (1e) |
| `alumglass/fb_handlers.py` | `@register_source` cho `aluminum_price_composite`, `glass_master_data`, `cost_bucket_aggregate` (batchable + fingerprint) |
| `alumglass/al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py` | bỏ eval trần → import FB `safe_eval` (R1) |
| `alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.py` | bỏ eval trần → import FB `safe_eval` (R2) |
| `alumglass/al_bom_engine/doctype/al_bom_version/…` | `pricing_dimension_snapshot` + guard (P1) |
| `alumglass/setup/custom_fields.py` | +3 field Quotation Item async (P2) |
| `alumglass/patches/…` | seed FVB từ AL Variable Library (**D3, DEV1**) + backfill snapshot (P1) + **normalize_percent_system_vars (0b, DEV2)** |
| `alumglass/patches.txt` | **sai vị trí app root → `git mv` sang `alumglass/alumglass/patches.txt`** (migrate mới chạy được patch alumglass) |
| `standalone_tests/test_phase_b_fbmax.py` | Test standalone FB-max (ngoài package — xem Test) |

## Test

- `standalone_tests/test_phase_b_fbmax.py` — standalone (FakeFrappe stub, không
  cần site): B1 get_live_context + fallback, B2 composite
  fallback/resolve/binding thắng, B4 normalize + dot-to-subscript, B5 on_error
  recovery + aggregate_from_items, B6 get_formula_context FB-first + golden.
  Chạy: `python3 -m pytest standalone_tests/test_phase_b_fbmax.py` (không cần
  bench). **Thư mục nằm NGOÀI package `alumglass/`** để
  `bench run-tests --app alumglass` (os.walk toàn package) không collect — chi
  tiết D1.
- `alumglass/tests/test_safe_eval_a3.py` — RCE bị chặn (payload dunder/import).
- `alumglass/tests/test_composite_pricing.py` — composite key trong luồng thật
  (multi-color, determinism).
- Golden: CDMQ-2C `GIA_VAT ≈ 22.717.289đ` + CDMQ-4C — pass sau mọi phase.
