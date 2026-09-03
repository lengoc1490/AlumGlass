# P3 — Merge gói vá `alumglass-patch-3-full` (V6 P10) vào app thật — Phase 0

> **Trạng thái:** Merged (code-only) · 2026-09-03 — CHƯA migrate site, CHƯA chạy golden
> **Job:** `2026-09-03_alumglass-patch3-merge-fb-platform-ph0-1`
> **Cơ sở:** commit `084896c` (real app) — gói vá chỉ được import làm reference, tài liệu này ghi nhận lần merge thật từng file
> **Tham chiếu:** proposal `formula_builder/docs/design/de-xuat-cai-tien-quotation-pricing.md` (§3B Phase 0) · `formula_builder/docs/design/co_che_tinh_gia_quotation.md` · `alumglass/docs/design/quotation-pricing.md` · `alumglass/docs/design/p1-pricing-dimension-versioning.md` · `README_TONG_HOP.md` (trong gói vá)
> **Ràng buộc:** KHÔNG đụng production; golden `CDMQ-2C = 22,717,289` / `CDMQ-4C = 47,430,808` chưa chạy (để sau khi có site)

## Vì sao file này tồn tại

Gói vá `alumglass-patch-3-full` (V6 P10 — bản tổng hợp Phần A–E) đã nằm trong repo
như package tham chiếu từ commit `084896c`, nhưng CHƯA từng được merge vào logic thật
của app `alumglass/`. Tài liệu này ghi lại toàn bộ quyết định merge từng file (merge/
giữ nguyên/không có real) + cơ chế mới sau patch, để (1) phase sau không phải "đọc lại
diff từ đầu", (2) đối chiếu được khi chạy golden.

Nguyên tắc merge: **KHÔNG `cp -r` mù** — mỗi file đều `diff` bản real vs bản vá trước
khi quyết định. Gói vá được rà trên cùng lineage nên hầu hết là **pure superset** (real
+ bổ sung), copy đè an toàn.

## Quyết định merge theo file

| File (trong app `alumglass/`) | Quyết định | Ghi chú |
|---|---|---|
| `engine/bom_orchestrator.py` | MERGE (copy đè) | 1439 → **1575 dòng**. Diff thuần superset: `_default_price_list()`, `glass_master_map`, `_resolve_glass_override`, `_category_by_code`, `_get_dim_mappings_raw`/`_dim_fieldnames_for_category`, `row_ctx["category"]` ở FB-max, `_fetch_composite_prices` wrapper `best_partial_match`, `is_final_price`, `_resolve_system_variables` → module chung |
| `engine/composite_pricing.py` | THÊM MỚI (60 dòng) | `best_partial_match` dùng chung 2 nhánh |
| `al_bom_engine/formula_validate.py` | THÊM MỚI (111 dòng) | Validate dùng chung, `normalize_global` đúng chuẩn FB |
| `al_bom_engine/system_variable_resolver.py` | THÊM MỚI (113 dòng) | `resolve_source_record_names` + `resolve_system_variable_values` — 1 nguồn cho autocomplete lẫn tính BOM |
| `al_bom_engine/doctype/al_bom_set/al_bom_set.py` | MERGE | thêm `_validate_child_formulas()` |
| `al_bom_engine/doctype/al_bom_item/al_bom_item.py` | MERGE | `FORMULA_FIELDS`, regex check `rule_input_expr` |
| `al_bom_engine/doctype/al_accessory_set/al_accessory_set.py` | MERGE | `pass` → validate `qty_formula` |
| `al_bom_engine/doctype/al_ai_intelligence/.../al_alert_config.py` | MERGE | `pass` → validate `trigger_condition` |
| `al_bom_engine/doctype/al_accessory_item/al_accessory_item.py` | GIỮ NGUYÊN | real = vá (diff rỗng) |
| `al_bom_engine/doctype/al_accessory_item/al_accessory_item.json` | MERGE | thêm field `calc_pattern`, `cost_bucket` (chỉ thêm, không đổi field cũ) |
| `al_bom_engine/doctype/al_cost_template_item/al_cost_template_item.json` | MERGE | thêm field `is_final_price` (chỉ thêm) |
| `al_bom_engine/doctype/al_cost_template/al_cost_template.py` | GIỮ NGUYÊN | real = vá (diff rỗng) |
| `al_bom_engine/doctype/al_cost_template/al_cost_template.js` | MERGE | refresh gọi `injectContext(frm)` (C7 gộp Preview) |
| `al_bom_engine/doctype/al_bom_version/al_bom_version.py` | MERGE | snapshot thêm `material_category` + `is_final_price` |
| `alumglass/doctype/overrides/quotation.js` | MERGE | chỉ đổi 1 block (C5): bỏ hardcode `OPTIONAL_DIMENSIONS` → đọc `is_pricing_dimension` server trả. Real đã có sẵn render glass_groups + lưu `glass_master_map` — KHÔNG overwrite lùi |
| `api/__init__.py` | MERGE | `_resolve_doc_values` → module chung (fix bug `OFFSET_CROSSBAR`), `_resolve_variable_set_name`, `get_allowed_formula_functions`, cờ `is_pricing_dimension` 2 nơi |
| `fb_handlers.py` | MERGE | exact_match → `best_partial_match` (bỏ AND cứng) |
| `hooks.py` | MERGE | chỉ đổi `_after_install`/`_after_migrate` (thêm install_workflows + install_composite_pricing_binding); giữ nguyên mọi cấu hình real khác |
| `setup/install_workflows.py` | THÊM MỚI (192 dòng) | 4 workflow thật (D11) |
| `setup/install_fb_bindings.py` | THÊM MỚI + **FIX C5** | seed binding composite pricing; price_list ĐỘNG từ Selling Settings (xem dưới) |
| `patches/v28_10/rebackfill_snapshot_category_final_price.py` | THÊM MỚI | re-backfill snapshot Published cũ (thêm `material_category` + `is_final_price`) |
| `patches/v28_9/backfill_pricing_dimension_snapshot.py` | MERGE | query thêm `material_category` |
| `patches.txt` | MERGE | thêm dòng v28_10 vào `[post_model_sync]` |
| `public/js/cost_template.js` | MERGE | C6 fetch customFns động; C7 xóa block refresh trùng ở cuối file |
| `public/js/formula_setup.js` | MERGE | C9 gộp 6 doctype về `FORMULA_DOCTYPE_REGISTRY` + 1 vòng đăng ký; B thêm autocomplete AL Accessory Set `qty_formula` |
| `public/js/bom_set_context.js` | XÓA (C8) | file chết — không có trong app_include_js, không ai reference |

## Cơ chế mới (tóm tắt kỹ thuật — chi tiết trong `README_TONG_HOP.md` của gói)

### A — Kính/vật tư mã đại diện theo vị trí (B2)
- `self.glass_master_map` đọc từ `al_bom_vars["glass_master_map"]` (dialog đã lưu từ
  trước, engine CHƯA từng đọc) — `_resolve_glass_override(rep_code)` ưu tiên per-position
  → global → giữ nguyên.
- Batch query weight/price/Glass Master gộp cả `glass_master_map.values()`.
- `glass_data[slug]` + `row_literals` resolve qua `_resolve_glass_override` → nẹp/kính
  tra đúng độ dày theo TỪNG vị trí đã đổi.
- Pricing Dimension lọc theo `material_category` của ĐÚNG dòng BOM:
  `_get_dim_mappings_raw()` + `_dim_fieldnames_for_category(category)` (giữ
  `_get_dim_fieldnames()` cũ). Nhánh FB-max và fallback giờ cùng dùng `_category_by_code()`.
- Gộp 2 nhánh tra giá về 1 thuật toán `composite_pricing.best_partial_match`.

### B — Validate công thức dùng chung
`al_bom_engine/formula_validate.py`: `build_known_names`, `check_formula`,
`check_formula_fields` — cross-row `items.slug.field` normalize bằng ĐÚNG
`formula_builder.table_formula_builder.normalize_global`. Wiring chặn cứng lúc save cho
AL Bom Set (`_validate_child_formulas`), AL Accessory Set, AL Alert Config.

### C — Zero hardcode (C1–C9)
- C1: `_default_price_list()` đọc `Selling Settings.selling_price_list` (fallback "Standard Selling") — thay 2 chỗ hardcode trong `bom_orchestrator`.
- C2: `_load_accessories` đọc `acc.get("calc_pattern")`/`acc.get("cost_bucket")` (bỏ trống = COUNT/VL_PK cũ).
- C3: `is_final_price` trên AL Cost Template Item + `_resolve_final_price`.
- C4: `_resolve_variable_set_name()` tự dò field Link.
- C5: quotation.js bỏ `OPTIONAL_DIMENSIONS` hardcode → server trả `is_pricing_dimension`.
- C6: `alumglass.api.get_allowed_formula_functions()` — JS fetch động.
- C7: gộp Preview về 1 nút (al_cost_template.js); xóa block refresh trùng trong cost_template.js.
- C8: xóa `public/js/bom_set_context.js`.
- C9: `FORMULA_DOCTYPE_REGISTRY` 1 vòng đăng ký autocomplete.

### D11/D12 — Workflow thật + resolver chung
- `setup/install_workflows.py`: 4 Workflow Frappe thật (AL BOM Version, AL Change Order,
  AL Dynamic Item Rule Version, AL Design Revision) — role-gating transition thay
  `workflow_state` Select tự chế. Idempotent, xóa & tạo lại record Workflow (chỉ cấu hình).
  Business logic trong `.py` (`_guard_published_immutability`, `_create_new_bom_version`,
  validate approvals của AL Change Order) GIỮ NGUYÊN 100%.
- `al_bom_engine/system_variable_resolver.py`: 1 nguồn cho `_resolve_doc_values`
  (autocomplete) + `_resolve_system_variables` (engine) — sửa bug autocomplete
  `OFFSET_CROSSBAR` → biến thật `OFFSET_DO_NGANG`.

### E — Seed FB binding pricing (FB-max chạy thật)
- `setup/install_fb_bindings.py` tự seed đúng 1 binding `COMPOSITE_MATERIAL_PRICE`
  (`source_type=aluminum_price_composite`, `applies_to_doctype=""` global, `is_active=1`)
  mỗi lần migrate (idempotent) — trước đây `_fetch_composite_prices_via_fb()` luôn trả
  None vì chưa ai tạo binding.
- **FIX C5 (bổ sung khi merge):** bundle gốc seed `source_config={"price_list":
  "Standard Selling"}` CỨNG — lệch nguồn với engine `_default_price_list()` (Selling
  Settings). `install_fb_bindings.py` giờ gọi `bom_orchestrator._default_price_list()`
  tại lúc seed để điền price_list ĐỘNG (mỗi migrate tự re-sync khi bảng giá đổi), 2
  đường FB-max/fallback không thể lệch số. Xem §3C C5 proposal.

### v28_10 — Re-backfill snapshot
`rebackfill_snapshot_category_final_price.py` ghi đè lại `pricing_dimension_snapshot` +
`cost_template_snapshot` (config hiện tại) cho mọi AL BOM Version `Published` — để báo
giá cũ cũng lọc được `material_category`/`is_final_price`.

## KHÔNG đổi / còn lại sau patch (chủ đích)
- `cost_bucket_aggregate` handler + `hooks.py::fb_source_types` — GIỮ (deprecated,
  migration sang `aggregate_from_items` thuộc Phase 3 roadmap, không làm trong Phase 0).
- `al_cost_template.py` vẫn giữ bản validate + `_ALUMGLASS_CUSTOM_FUNCS` riêng
  (không nằm trong phạm vi bundle; nguồn hàm JS đã gộp về `get_allowed_formula_functions`).
- `public/js/bom_set_context.js` đã xóa (C8).
- 2 field JSON mới (`calc_pattern`, `cost_bucket`, `is_final_price`) chỉ có hiệu lực sau
  `bench migrate` tạo cột — code đã tương thích ngược (bỏ trống = hành vi cũ).

## Gate & bước còn thiếu (chưa verify được vì không có site)
1. `bench migrate` → chạy `v28_10` + `install_workflows` + `install_fb_bindings`.
2. Chạy checklist test README_TONG_HOP Phần A–E (test tay + run-tests module
   `test_bom_orchestrator`/`test_composite_pricing`/`test_pricing_dimension_snapshot`).
3. **Golden CDMQ-2C/4C KHÔNG đổi** — kể cả khi xác nhận FB-max chạy thật.
4. Sau migrate: kiểm tra field `workflow_state` không bị đụng, Workflow 4 doctype hoạt động.
