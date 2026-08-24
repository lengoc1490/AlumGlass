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
| `glass_master` | Kính override (line kính) | `b2` → glass_data thick/type + item_code line kính → RULE-NEP/KEO resolve theo kính đã chọn |
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
| `alumglass/engine/bom_orchestrator.py` | `_resolve_fb_context()` (B1), `_fetch_composite_prices_via_fb()` (B2), `_resolve_cost_buckets_via_fb()` (B5), `on_error="default"`, `b7_save_results()` ghi errors |
| `alumglass/api/__init__.py` | `get_formula_context()` lấy từ `get_live_context` (FB-first + dedup); `calculate_bom` async (P2) |
| `alumglass/fb_handlers.py` | `@register_source` cho `aluminum_price_composite`, `glass_master_data`, `cost_bucket_aggregate` (batchable + fingerprint) |
| `alumglass/al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py` | bỏ eval trần → import FB `safe_eval` (R1) |
| `alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.py` | bỏ eval trần → import FB `safe_eval` (R2) |
| `alumglass/al_bom_engine/doctype/al_bom_version/…` | `pricing_dimension_snapshot` + guard (P1) |
| `alumglass/setup/custom_fields.py` | +3 field Quotation Item async (P2) |
| `alumglass/patches/…` | seed FVB từ AL Variable Library (**D3, DEV1**) + backfill snapshot (P1) |
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
