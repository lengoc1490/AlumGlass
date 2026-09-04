# BÁO CÁO TỔNG HỢP — Các phần đã bổ sung & điều chỉnh

> **Trạng thái:** Merged (code-only) · 2026-09-03 — CHƯA migrate site, CHƯA chạy golden
> **Lưu trữ:** alumglass/docs/design — báo cáo tổng hợp thay đổi 2 repo (alumglass + formula_builder)
> **Job:** `2026-09-03_alumglass-patch3-merge-fb-platform-ph0-1`
> **Chi tiết platform formula_builder:** `formula_builder/docs/design/fvb-single-resolution-layer.md` (§10–12) · `de-xuat-cai-tien-quotation-pricing.md` · `aggregate_from_items.md`


**alumglass + formula_builder · 2026-09-03**

> Phạm vi báo cáo: toàn bộ thay đổi code + docs được triển khai trong job
> `2026-09-03_alumglass-patch3-merge-fb-platform-ph0-1`, gồm 2 đợt:
> **Đợt 1 — Phase 0 + Phase 1** (DEV1 merge `alumglass-patch-3-full`; DEV2 platform A1–A5)
> **Đợt 2 — Phase 2/3/4 + A5 hookup** (DEV1 app-side; DEV2 platform contract + docs)
>
> Chế độ triển khai theo duyệt Owner: **CHỈ CODE, KHÔNG verify site** (không `bench
> migrate`, không chạy golden CDMQ-2C/4C trên site) — mọi mục **Chờ verify site** liệt kê
> ở §5 là bắt buộc trước khi tin cậy vào production.

---

## 1. Repo alumglass — các phần bổ sung / điều chỉnh

Nhánh `main`, base `084896c` → local HEAD `b922756` → remote `fe12821e` (tree khớp).
Tổng **14 commit mới** (8 Phase 0 + 6 Phase 2–4). Không thay đổi schema DocType cần migrate
ngoài các field JSON đã liệt kê; `bench migrate` trên site dev sẽ sync field + chạy patch.

### 1.1 Phase 0 — áp gói `alumglass-patch-3-full` vào app thật (8 commit `e812238→eb337d7`)

| # | Phần | File thay đổi | Nội dung bổ sung/điều chỉnh |
|---|---|---|---|
| A | Kính/vật tư mã đại diện **theo vị trí** | `engine/bom_orchestrator.py` (1439→1575 dòng), `engine/composite_pricing.py` (MỚI), `fb_handlers.py`, `.../al_accessory_item/al_accessory_item.json` | `_resolve_glass_override()` ưu tiên per-position `glass_master_map` → đổi kính từng vị trí trong dialog giờ có tác dụng thật; batch-fetch `glass_master_map.values()`; lọc dimension theo `material_category` (`_dim_fieldnames_for_category`); **gộp 2 nhánh tra giá** (Python fallback + FB-max) về chung `composite_pricing.best_partial_match` (60 dòng) — xoá khác biệt thuật toán; xoá file chết `public/js/bom_set_context.js` (C8) |
| B | Validate công thức dùng chung | `al_bom_engine/formula_validate.py` (MỚI, 111 dòng); wiring `al_bom_set.py`, `al_bom_item.py`, `al_accessory_set.py`, `al_alert_config.py` | Validate save-time 4 doctype, normalize cross-row bằng `normalize_global` của FB |
| C1–C9 | Zero-hardcode | `bom_orchestrator.py`, `api/__init__.py`, `quotation.js`, `public/js/cost_template.js`, `formula_setup.js`, `al_cost_template.js` | `_default_price_list()` đọc Selling Settings (bỏ hardcode `"Standard Selling"`); `calc_pattern`/`cost_bucket` phụ kiện đọc field thật (bỏ hardcode `COUNT`/`VL_PK`); `_resolve_variable_set_name` (C4); `is_pricing_dimension` từ bảng Dimension Mapping (C5); `get_allowed_formula_functions` nguồn duy nhất (C6); gộp handler Preview (C7); `FORMULA_DOCTYPE_REGISTRY` 1 vòng đăng ký (C9) |
| D11 | Workflow thật | `setup/install_workflows.py` (MỚI), `hooks.py` | Workflow role-gated cho 4 doctype (AL BOM Version, AL Change Order, AL Dynamic Item Rule Version, AL Design Revision) thay `workflow_state` Select tự chế |
| D12 | Generalize resolver | `al_bom_engine/system_variable_resolver.py` (MỚI, 113 dòng), `api/__init__.py`, `bom_orchestrator` | Sửa bug `OFFSET_CROSSBAR` → `OFFSET_DO_NGANG`; auto-discover Link field làm shared source (bỏ hardcode 2 doctype + 4 offset field) |
| E + **FIX C5** | Seed FB binding pricing | `setup/install_fb_bindings.py` (MỚI), `hooks.py` | Auto-seed FVB `COMPOSITE_MATERIAL_PRICE` (source_type `aluminum_price_composite`, `is_active=1`) — **bật FB-max pricing thật**; lưới an toàn: set `is_active=0` quay về Python fallback. **FIX C5 (làm tay ngoài gói vá):** bỏ hardcode `price_list: "Standard Selling"` trong `source_config` → `_resolve_seed_price_list()` resolve đúng `bom_orchestrator._default_price_list()` (đọc Selling Settings) tại lúc seed |
| v28_10 | Backfill snapshot | `patches/v28_10/rebackfill_snapshot_category_final_price.py` (MỚI), `patches.txt` | Rebackfill `material_category` + `is_final_price` cho BOM Version Published cũ (lan tới báo giá cũ) |
| Schema | Field mới | `al_cost_template_item.json`, `al_accessory_item.json` | `material_category`, `is_final_price` (Check, default 0) — liên quan snapshot + category filter |

### 1.2 Phase 2 — Seed FVB đầy đủ (6 commit `6be5cd4→b922756`)

| # | Nội dung |
|---|---|
| **D6 — Seed FVB FULL** | Patch mới `patches/v28_11/seed_fvb_full_from_variable_library.py` (+ `patches.txt` [post_model_sync]). Seed Formula Variable Binding cho **MỌI** system var (AL Variable Library `is_system=1`) có `source_doctype`+`source_field` — không chỉ 2 doctype như `v28_9`. Nguồn link_field tự dò qua `system_variable_resolver.resolve_source_link_fields(doctype)` (hàm mới, tách từ `resolve_source_record_names`). **Chỉ seed khi chắc chắn semantics = resolution cũ 1.3** (cùng scope AL Bom Set mà FB context resolve); var không map được (thiếu Link field) → **KHÔNG seed**, engine giữ fallback → an toàn khi chưa chạy golden. Idempotent check `(variable_name, applies_to_doctype, is_global)`. KHÔNG xoá `source_doctype`/`source_field` trên Variable Library |

### 1.3 Phase 3 — Retire path cũ + migrate bucket + D7

| # | Nội dung |
|---|---|
| **3a — Flip B1 FB-first** | `bom_orchestrator.b1_gather_inputs`: đảo thứ tự — **FVB/`_resolve_fb_context()` (1.4) resolve TRƯỚC**; `_resolve_system_variables()` (1.3, path cũ) sau với `fill_missing_only=True` → chỉ resolve biến CHƯA có trong inputs (biến FB đã phủ giữ giá trị FB). Override `profile_system` (1.5c) vẫn gọi full-call (ghi đè toàn bộ theo profile override). `_profile_child_vars` capture **trực tiếp từ child row** (parse số giống module dùng chung) — tránh lưu nhầm giá trị FB field value trong thứ tự mới. `get_formula_context()` (`api/__init__.py`) cập nhật mô tả nguồn: system var đã seed → "Resolve qua FVB", fallback an toàn cho var chưa seed |
| **3b — C2 migrate bucket** | Patch `v28_11/migrate_cost_bucket_aggregate_to_aggregate_from_items.py`: rewrite FVB record `source_type=cost_bucket_aggregate` → `aggregate_from_items` với `{rows_source:"snapshot", snapshot_doctype:"AL BOM Version", snapshot_name:"{{resolved.bom_version}}", snapshot_field:"bom_set_snapshot", rows_path:"items", aggregate:"sum", value_field:<sum_field cũ>, filters:[[k,"=",v]...]}` — **đúng contract DEV2** (value_field bắt buộc schema; snapshot_field tường minh; snapshot_name template resolved var). Sau migrate: **GỠ handler** khỏi `fb_handlers.py` (còn 2: `aluminum_price_composite`, `glass_master_data`), **GỠ entry** `hooks.py::fb_source_types`, **sửa test** `test_safe_eval_a3.py` (assert 2 handler + no-legacy-bucket). **AC A-5 đạt**: grep `cost_bucket_aggregate` rỗng ở 3 file code |
| **D7 — Giá trước VAT theo cờ** | Field `is_pre_vat_price` (Check, default 0) trên AL Cost Template Item (JSON) + snapshot builder (version + engine b6 override) ghi cờ. Engine thêm `_resolve_final_price()` (hoàn thiện C3: dòng `is_final_price=1` → line_code trong cost_result; fallback `"GIA_VAT"` = hành vi cũ) + `_resolve_pre_vat_price()` (dòng `is_pre_vat_price=1`; fallback `"GIA_BAN"`). Gắn vào `gia_vat`, `al_gia_ban`, `full_result.gia_ban`, `get_result_display`. Patch `v28_11/rebackfill_cost_template_pre_vat_price.py` backfill snapshot cũ. **Golden-safe**: snapshot pre-flag → default-fallback giữ giá trị cũ |

### 1.4 A5 — Pricing scope qua binding_scope (mảnh nối với DEV2)

| # | Nội dung |
|---|---|
| **A5** | `_get_pricing_bindings` (`bom_orchestrator.py:~869`): bỏ filter tay `applies_to_doctype in ["", "Quotation Item", "AL Bom Item"]` → dùng **`formula_builder.api.binding_scope.get_scope_bindings_multi(["Quotation Item","AL Bom Item"], source_types=PRICING_SOURCE_TYPES)`** (helper platform DEV2 bổ sung) làm nguồn lọc scope DUY NHẤT — tôn trọng `applies_to_field` khi set (khớp đúng row doctype+field), KHÔNG đổi kết quả khi không binding set `applies_to_field`. Có fallback filter tay khi formula_builder version cũ chưa có `binding_scope` |

### 1.5 Phase 4 — Docs alumglass

Cập nhật trong cùng repo code: `docs/design/quotation-pricing.md` (Phase 2–4: D6/flip/C2/D7/A5 + bảng file), `docs/design/fvb-seed.md` (mục D6 seed full), `docs/design/p3-quotation-pricing-patch-3-full.md` (append Phase 2–4 + sửa bullet "GIỮ" → đã gỡ), `docs/quotation-pricing-flow.md` (§6 B1 FB-first, §7 bỏ hàng cost_bucket_aggregate), `docs/usage/bom-calculation-dialog.vi.md` + `.en.md` (2 trạng thái nguồn hiển thị — frontmatter contexts/tags đủ).

---

## 2. Repo formula_builder — các phần bổ sung / điều chỉnh

Nhánh `develop`, base `d201fd4` → local HEAD `edaebc4` → remote `5e46e053` (tree khớp).
Tổng **10 commit mới** (7 Phase 1 + 3 Phase 2–4). Mọi thay đổi **additive** — không đổi
output source type hiện hữu, không đụng golden alumglass.

### 2.1 Phase 1 — Platform A1–A5 (7 commit `39725e7→18f04ca`)

| # | Nội dung |
|---|---|
| **A1 — Dropdown `source_type` động** | FVB doctype: `source_type` Select(13 static) → **Autocomplete**, options nạp động từ whitelisted `list_source_types()` (17 built-in + custom qua hooks `fb_source_types`). Autocomplete map varchar → **không cần migrate dữ liệu**; binding cũ (13) vẫn đọc; giá trị legacy không còn trong registry hiển thị nhãn "(không có trong registry)". Files: `formula_variable_binding.json` + `.js` |
| **A2 — Form động `source_config`** | Thêm HTML field `source_config_editor_html`; JS render form theo `config_schema` từ `get_source_type_schema(source_type)` (checkbox/enum/number/text/JSON textarea), ghi về field JSON native `source_config` (source of truth, submit-safe). Tôn trọng `required_unless` (vd `aggregate_from_items.value_field` bỏ trống hợp lệ khi `aggregate=count`). Nút tiện ích: Validate Config / Test (no doc) / Test With Doc / Preview Batch Groups. An toàn khi doctype chưa sync (JS guard `if (!rendered) return`) |
| **A3 — `test_data_source_with_doc`** | Tách executor dùng chung `_execute_source_test`; `test_data_source` cũ (doc=None) backward-compatible. Whitelisted API mới `test_data_source_with_doc(source_type, source_config, doctype, docname, resolved_context_json, data_type)` — load doc thật (từ chối `new-*` chưa lưu), pre-resolved context; shape giống test cũ + `doc_context`. File: `api/source_type_registry.py` |
| **A4 — `preview_batch_groups`** | `BatchBindingResolver.preview_groups(bindings)`: mô phỏng pipeline `_split_batchable`→`_group_by_fingerprint` **KHÔNG execute**; phân loại strategy đúng thứ tự `_execute_one_group` (resolve_batch / resolve_batch_query / execute_individual — expose N+1). Whitelisted `preview_batch_groups(doctype, applies_to_field, include_inactive)`; output `{scope, summary, groups, individual_bindings}`. Files: `api/batch_binding_resolver.py` |
| **A5 — Scope semantics tập trung** | Module mới **`api/binding_scope.py`**: `binding_matches_scope`, `filter_bindings_for_scope`, `get_scope_bindings` — luật filter scope DUY NHẤT (global/doctype/doctype+field), bảo toàn 100% semantics cũ của `get_live_context`. Refactor `get_live_context` → gọi `get_scope_bindings` (hành vi giữ nguyên). Fix gap: `_get_pricing_bindings` (alumglass) trước đây bỏ qua `applies_to_field` |

### 2.2 Phase 2–4 — Contract + docs platform (3 commit `700cf88→edaebc4`)

| # | Nội dung |
|---|---|
| **A5 mở rộng — scope đa doctype cho pricing** | Helper hiện có chỉ cover **1 doctype** → thêm additive 3 hàm: `binding_matches_any_doctype`, `filter_bindings_for_scope_multi`, `get_scope_bindings_multi(doctypes, field="", source_types=None, ...)` (DB prefilter `applies_to_doctype in ["", *doctypes]` + optional `source_type`; python filter). Semantics: field binding rỗng → áp mọi field (KHÔNG đổi kết quả khi không set); set → chỉ khớp đúng doctype+field. +8 unit test (`TestBindingScopeMultiDoctype`). File: `api/binding_scope.py` + test |
| **Contract migration C2** | Xác nhận config `aggregate_from_items` (rows_source=snapshot, snapshot_field, rows_path, filters AND, value_field) **hợp lệ trên handler `data_source_registry.py`** — CHỈ config, KHÔNG cần platform change. 3 lưu ý cho DEV1: (1) `value_field` bắt buộc schema (alias `sum_field` không qua validate), (2) `snapshot_name` phải tường minh `{{resolved.bom_version}}`, (3) `snapshot_field="bom_set_snapshot"` set tường minh (default platform `"snapshot"`). Migration guide chính thức thêm vào `docs/aggregate_from_items.md` |
| **Docs Phase 4 (AC A-6)** | ADR `fvb-single-resolution-layer.md`: status → "✅ Approved + **đã triển khai (platform)**" + thêm **§12** "Phase 2–4 — alumglass adopt + status" (12.1 D6 seed full + FB-first; 12.2 cost_bucket retired → aggregate_from_items; 12.3 line-flag is_pre_vat_price/is_final_price; 12.4 A5 hookup đa doctype; 12.5 docs; 12.6 status platform). §10.5 bổ sung bộ hàm đa doctype; §11.1 trỏ helper. `docs/design/co_che_tinh_gia_quotation.md`: ghi chú đầu file cơ chế mới đã merge (giữ as-is lịch sử). `docs/design/de-xuat-cai-tien-quotation-pricing.md`: status DRAFT → đã triển khai 2026-09-03 + bảng đóng mục. `docs/fb_source_type_contract.md` §9.1: pattern pricing scope khuyến nghị cho app. `docs/review1.md` KHÔNG tồn tại trong repo → không có việc đánh dấu |

---

## 3. Tổng hợp commit (14 alumglass + 10 formula_builder)

### alumglass — `main` → remote `fe12821e`
| Phase | Commit |
|---|---|
| Phase 0 (8) | `e812238` engine Phần A · `d8a422b` validate Phần B · `fec33ab` C4–C6 + D12 · `4f3a849` UI C5/C7/C8/C9 · `3f0f011` snapshot schema · `b2f40ec` D11+E (+FIX C5) · `907be37` v28_10 · `eb337d7` docs |
| Phase 2–4 (6) | `6be5cd4` v28_11 seed+migrate+rebackfill · `f10ac1d` B1 flip · `ff98f39` C2 remove · `f92d703` D7 · `f4b30f4` A5 binding_scope · `b922756` docs |

### formula_builder — `develop` → remote `5e46e053`
| Phase | Commit |
|---|---|
| Phase 1 (7) | `39725e7` A1/A2 · `3c70b3d` A3 · `2dca46d` A5 binding_scope · `c1043ed` A4 · `62d61a5` refactor live_context · `b5992da` test · `18f04ca` docs |
| Phase 2–4 (3) | `700cf88` A5 đa doctype + test · `e7ea1af` contract docs · `edaebc4` docs Phase 4 |

---

## 4. Trạng thái kiểm chứng (đã chạy)

| Kiểm chứng | Kết quả |
|---|---|
| `py_compile` mọi file Python touched (bench env + system) | PASS |
| Import-check chéo `formula_builder.api.binding_scope` từ bom_orchestrator (no-site) | PASS |
| `test_safe_eval_a3.py` (alumglass) — mini-runner no-site | **10/10 PASS** (2 handler + no legacy bucket) |
| `test_platform_phase1.py` (formula_builder) | **32/32 PASS** (23 + 8 multi-doctype) |
| AC A-5: grep `cost_bucket_aggregate` rỗng (fb_handlers.py / hooks.py / tests) | PASS |
| Migrate config khớp contract DEV2 (value_field / snapshot_name / snapshot_field) | PASS |
| D7 helpers sanity 4 case (no-flag, flagged, missing line_code, old snapshot) | PASS |
| Push remote tree == local (alumglass `fe12821e`, formula_builder `5e46e053`) | PASS |

---

## 5. ⚠️ Chưa verify — bắt buộc khi mở site dev (Owner QA)

Job triển khai theo chế độ **CHỈ CODE** (Owner duyệt) → các mục sau **CHƯA chạy** và là bước
bắt buộc trước khi tin cậy vào production:

1. **`bench migrate`** → sync field mới (`is_pre_vat_price`, `source_type` Autocomplete,
   `source_config_editor_html`, `material_category`, `is_final_price`) + chạy **6 patch**:
   v28_10 (rebackfill category/final) + v28_11 × 3 (seed D6, migrate C2, rebackfill D7).
   Rà log "D6 FALLBACK" để xác nhận var nào không seed được (thiếu Link field) đúng kỳ vọng.
2. **Golden CDMQ-2C = 22,717,289 / CDMQ-4C = 47,430,808** (gate số 1 mọi phase) — engine đổi
   thứ tự resolve B1 (FB-first) + D7 đọc cờ snapshot; thiết kế **golden-safe** (fallback giữ
   giá trị cũ) nhưng phải tính lại trên site có data thật. Lệch → binding `is_active=0` quay
   Python fallback (không cần revert code).
3. **FB-max pricing end-to-end** (`_fetch_composite_prices_via_fb` không trả None) + giá
   composite có thể đổi nhẹ theo thiết kế kính-per-position — đối chiếu 1–2 mẫu thật.
4. **`aggregate_from_items`** resolve trên FVB migrated (sau C2) — test no-site/platform.
5. Workflow thật 4 doctype hiển thị transition theo role; dialog text nguồn mới hiển thị.

---

*Báo cáo biên soạn bởi Elon (điều phối) từ report DEV1 + DEV2 đã review + verify code độc lập.
Chi tiết từng việc: `DEV1_report.md`, `DEV2_report.md`, `DEV1_report_phase234.md`,
`DEV2_report_phase234.md` (cùng thư mục job).*
