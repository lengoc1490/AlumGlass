# al_review.md v2 — Đánh giá AlumGlass & Kế hoạch triển khai: **TÍNH GIÁ QUOTATION**

> **Bản chất tài liệu:** Review toàn bộ code + tài liệu `.md` của app `alumglass` và `formula_builder`
> (đọc trực tiếp tại `/home/nxc/myfrappe/apps/alumglass` và `/home/nxc/myfrappe/apps/formula_builder`),
> đối chiếu khả năng **ERPNext 14.92.14 / Frappe 14.101.1 / HRMS 14.38.1** và **formula_builder** (engine v30/v31).
>
> **Phạm vi đợt này (theo yêu cầu Owner 2026-08-16):** **CHỈ triển khai sơ bộ tính giá quotation** —
> tận dụng tối đa core ERPNext/Frappe + formula_builder theo triết lý "Config > Code, 0 dòng code".
> **CHƯA triển khai bất kỳ module nào khác** (SX, kho, kế toán, HR, thi công...). Toàn bộ module khác được
> liệt kê ở §8 như "tương lai" — không nằm trong kế hoạch này.

> **Ngày soạn:** 2026-08-16 · **Tác giả:** Elon (AI Coordinator) — dựa trên code ground-truth (đã xác minh
> từng `file:line`) + tổng hợp toàn bộ docs v28.x.

**Ký hiệu nguồn thông tin (phân biệt fact code vs kế hoạch docs):**
- ✅ **code** — phát hiện từ đọc code thực tế, đã verify (kèm `file:line`).
- 📄 **docs** — ghi nhận từ tài liệu `.md` (kế hoạch v28.9/v28.10, review...) — *chưa chắc đã triển khai trong code, cần kiểm tra lại trước khi khẳng định*.
- ⚠ **cần chốt** — đề xuất/chuyển đổi rủi ro, cần BA/Owner chốt nghiệp vụ trước khi làm.

---

## 0. Tóm tắt điều hành — dành cho Owner

**AlumGlass đã có nền config-driven đúng hướng cho tính giá quotation:** engine BOM 7-phase chạy thật,
có test "số vàng" `GIA_VAT ≈ 22.717.289đ` (CDMQ-2C), batching query chống N+1, snapshot bất biến,
composite key pricing đã fix (v28.8 §G). **Không cần xây lại gì** — việc của đợt này là:

1. **🔴 Bảo mật (BLOCKER — làm trước tiên):** có **2** chỗ `eval()` trên chuỗi lưu DB đều dính RCE
   (`al_quantity_calc_method.py:36`, `al_cost_template.py:42`) — phải đóng trước khi production.
2. **Cài app lên dev site:** `alumglass` **chưa cài trên site nào** của máy dev `nxc20` (cả `formula_builder`
   cũng chưa) → test chưa từng chạy được. Phase A bắt đầu bằng install + chạy baseline test.
3. **Nối FB tối đa (đúng triết lý):** đăng ký chuẩn `@register_source` cho 3 handler + nối
   `get_live_context`/`BatchBindingResolver` vào engine — **bỏ ~300 dòng resolver tự viết** ở B1/B2/B5.
   Giữ test vàng không đổi sau mọi thay đổi.
4. **Đúng-sai báo giá:** test composite pricing **trong luồng thật** (multi-color), versioning Pricing
   Dimension (P1), `on_error` phục hồi không chết cả BOM, async cho BOM lớn (P2).

**Kết quả mong đợi:** tính giá quotation là **lớp mỏng nghiệp vụ đúng nghĩa** — cấu hình ở DB,
tính toán ở formula_builder, nghiệp vụ chuẩn ở ERPNext (Quotation/Item/Item Price qua custom fields + hooks,
**0 dòng `from erpnext import` — và điều đó là đúng/tốt cho phạm vi này**).

**Mở rộng (Owner 2026-08-16):** đợt quotation pricing là **Sprint 1** của roadmap **toàn phân hệ** —
alumglass là dự án chuyên ngành nhôm kính với **đầy đủ phân hệ như một ERP** (Bán hàng, Kho, Mua, Sản xuất
& Cắt, Thi công, Kế toán, AI). Toàn bộ roadmap các module + kế hoạch triển khai từng phân hệ + track phát
triển **formula_builder thành nền tảng chung** nằm ở **§11 + §12**.

> Chi tiết: §3 G1-G4 · §4 Bảo mật · §5 Kế hoạch chi tiết (Sprint 1) · §6 DoD · §8 Ngoài phạm vi
> · §11 Roadmap toàn phân hệ · §12 Phát triển formula_builder.

---

## 1. Phạm vi đợt triển khai này (theo yêu cầu Owner)

> **Owner chốt (2026-08-16):** "tận dụng tối đa core erpnext frappe + formula_builder, **chỉ triển khai
> sơ bộ cho tính giá quotation, chưa triển khai cho bất kỳ module nào khác**".

### 1.1 Có trong phạm vi (thuộc luồng tính giá quotation)

| Nhóm | DocType / Code | Lý do |
|---|---|---|
| AL Master Data | AL Variable Library, AL Variable Set/Item, AL Variable Dimension Mapping, AL Pricing Dimension, AL Slug Library, AL Material Category, AL Profile System, AL Color Standard, AL Glass Type/Thickness/Master, AL Product Type | Cấu hình giá, tham số, composite key |
| AL BOM Engine | AL Bom Item, AL Bom Set, AL BOM, AL BOM Version, AL BOM Change Log, AL Cost Bucket, AL Cost Template/Item, ConfigSnapshot | Mô hình + tính giá |
| AL Formula & Rules | AL Calculation Rule (+ Threshold/Lookup Row), AL Dynamic Item Rule (+Threshold/Lookup/Version), AL Quantity Calc Method | Công thức tính lượng |
| AL Selling | **Core** Quotation + Quotation Item (custom fields `al_bom`, `al_bom_version`, `al_bom_vars`, `al_config_snapshot`, `al_gia_ban`, `al_gia_vat`, `al_bom_result`) + `doctype/overrides/*.js` + client JS (`bom_dialog.js`, `quotation_item_dialog.js`) | Màn hình nghiệp vụ báo giá |
| Engine & API | `engine/bom_orchestrator.py`, `api/__init__.py`, `fb_handlers.py`, `hooks.py`, `setup/custom_fields.py`, `setup/seed_demo_data.py`, `patches/` | Phần lõi chạy thật |
| Phụ thuộc ngoài | Core `Item`, `Item Price` (custom `custom_pd_*`), Formula Global Variable (VAT_RATE, OH_VC_PCT, OH_QLY_PCT) | Dữ liệu gốc |

### 1.2 KHÔNG có trong phạm vi đợt này (xem §8 — danh sách tương lai)

- **AL Manufacturing** (Cutting Plan/Standard — thuật toán cắt **chưa implement**), **AL Construction** toàn bộ
  (Site Survey, Installation...), **AL Stock** (Inventory Dimension kho), **AL Buying** (Material Plan),
  **AL Account** (P&L, Cost Center, Accounting Dimension), **AL AI**, **AL Quality** (chỉ 1 doctype Warranty Policy).
- **HRMS** Timesheet/Expense Claim cho NC_LD (được tham chiếu ở §8, KHÔNG làm đợt này).
- Core BOM instantiate → MRP/Production (là kế hoạch v28.9/v28.10, KHÔNG làm đợt này).
- Tầng ứng dụng Frappe (Notification, Webhook, Dashboard, Translation...) — chỉ làm tối thiểu nếu trực tiếp
  phục vụ báo giá (vd Print Format báo giá — ⚠ cần Owner chốt, xem Phase C).

---

## 2. Hiện trạng kiến trúc — ground-truth đã xác minh (2026-08-16)

### 2.1 Môi trường + cài đặt

| Hạng mục | Giá trị thực | Ghi chú |
|---|---|---|
| Frappe | **14.101.1** (branch version-14) | ✅ code-verified |
| ERPNext | **14.92.14** (branch version-14) | ✅ code-verified. ⚠ **docs `TONG_QUAN_KIEN_TRUC.md` ghi "Frappe/ERPNext v16" — SAI so với bản cài hiện tại**, cần sửa doc (Phase D) |
| HRMS | **14.38.1** (branch version-14) | ✅ code-verified |
| formula_builder | folder develop (engine v30/v31, `FINAL_AUDIT_v30.md`) | ✅ `source_type_registry.py` có `@register_source` (line 489). ⚠ **chưa nằm trong `sites/apps.txt`** → chưa cài site nào |
| alumglass | app code có sẵn | ⚠ **chưa cài trên site nào** → test chưa chạy được; là việc đầu tiên của Phase A |
| Dev machine | `nxc20` | theo CLAUDE.md, mọi dev/migrate/test trên dev, không production |

### 2.2 Cấu trúc app

- **12 module** — nhưng `al_hr` chỉ là **shell rỗng (chỉ có `__init__.py`, 0 doctype)**; `al_selling` dùng
  core Quotation (0 doctype tự tạo). Số doctype JSON thực tế: **~60 file** (bao gồm child table);
  docs v28.9 ghi "53 triển khai". ✅ code-verified.
- `required_apps = ["formula_builder"]` (hooks.py:13) — đúng chuẩn. ⚠ `required_apps` **không cần**
  erpnext/hrms cho phạm vi quotation (app dùng core qua custom fields + hooks, không import).
- **API:** `hooks.py` khai báo `whitelisted_methods` = **7 endpoints** (`calculate_bom`, `preview_cost_template`,
  `get_slug_info`, `resolve_item_rule`, `get_bom_structure`, `get_cost_template_context`, `get_formula_context`);
  trong code `api/__init__.py` có **8** `@frappe.whitelist()` (dòng 4,16,23,30,37,44,74,264). ✅ code-verified.
- `hooks.py:57-61` khai báo `fb_source_types` = 3 handler (chưa register chuẩn — xem G4).

### 2.3 Luồng tính giá BOM — `engine/bom_orchestrator.py` (7-phase, "trái tim")

```
B0  Version pinning        → b0_version_pinning() (71)      dùng AL BOM Version snapshot (immutable)
B1  Gather inputs          → b1_gather_inputs() (93)        al_bom_vars JSON + Formula Global Variable
                              + _resolve_system_variables() (123)  ← TỰ resolver từ AL Variable Library
B2  Pre-fetch master data  → b2_prefetch_master_data() (206)
                              + _fetch_composite_prices() (373)  ← TỰ query Item Price theo composite key (✅ đã fix v28.8 §G)
                              + _match_composite_price() (403)   ← TỰ chọn dòng khớp nhất
B3  Build formulas         → b3_build_formulas() (479)      TỰ build list {name, formula} + regex items.X.Y → X__Y (510)
B4  Tính Bom Items         → b4_calculate_bom_items() (537) FormulaEngine (FB) — DAG + topo sort ✅
B5  Gom Cost Buckets       → b5_aggregate_cost_buckets() (588)  Python loop buckets[bk] += line_total (bỏ qua source_type)
B6  Tính Cost Template     → b6_calculate_cost_template() (600) FlexibleFormulaEngine (FB) ✅
B7  Save                   → b7_save_results() (653)       ConfigSnapshot + ghi Quotation Item (1 commit)
```

**Kết luận:** FB được dùng đúng ở **B4 và B6** (2 engine DAG mạnh nhất). B1/B2/B3/B5 là code tự viết
thay thế đúng thứ FB đã cung cấp sẵn (chi tiết §3 G2/G3 + §5 Phase B).

### 2.4 Các hệ thống "source_type" đang tồn tại SONG SONG

| Hệ thống | Nơi định nghĩa | Nơi resolve | Trạng thái |
|---|---|---|---|
| **Formula Variable Binding** (13 loại) | `formula_builder/api/data_source_registry.py` | `get_live_context` (`api/formula_builder.py:274`, nhận `scope_context_json`) → `resolve_bindings_with_deps` (`data_source_registry.py:1282`) / `BatchBindingResolver` (`batch_binding_resolver.py:229`) | **Chưa được nối** vào luồng BOM (0 lần gọi) |
| **AL Cost Bucket** (8 loại) | `al_cost_bucket.py` `VALID_SOURCE_TYPES` + `validate()` | — (không có resolver) | **Validate có, resolve không** — B5 gom bằng loop |
| **AL Variable Library** (is_system + user) | `al_master_data/doctype/al_variable_library` | `_resolve_system_variables()` (bom_orchestrator.py:123) | Tự viết, trùng `session_variable`/`global_default`/`computed` của FB |
| **AL Variable Set** | `al_master_data/doctype/al_variable_set` | JS dialog (`get_variable_set_for_bom`) | Tự viết — tương đương `applies_to_doctype` scope của FVB |
| **Composite key pricing** | `al_pricing_dimension` + `al_variable_dimension_mapping` | `_fetch_composite_prices`/`_match_composite_price` (B2) | Trùng logic `fb_handlers.aluminum_price_composite` |

### 2.5 Các quyết định Owner đã chốt — CẦN GIỮ trong tài liệu này

1. **Composite Key Pricing (giá bán) tách biệt Inventory Dimension (kho)** — Owner làm rõ 2026-08-13
   (`TONG_QUAN_KIEN_TRUC.md:538`): AL Pricing Dimension = tra giá trong dialog Quotation; kho = cơ chế độc lập.
2. **KHÔNG dùng Item Variant** (v28.9 #16) — Item = "mã nhôm đại diện", spec theo transaction (per-project).
3. **Composite key pricing giữ nguyên** (v28.md:6786).
4. **Config > Code, 0 dòng code cho nghiệp vụ mới** — cấu hình nghiệp vụ ở DB, code chỉ là framework trung gian.

---

## 3. Bốn khoảng trống G1-G4 (xác minh code) — định hướng theo phạm vi

| # | Khoảng trống | Bằng chứng | **Định hướng trong đợt quotation pricing** |
|---|---|---|---|
| **G1** | **0 dòng `from erpnext import ...`** trong toàn app | `grep -rn "from erpnext" alumglass/` → rỗng | ✅ **KHÔNG cần xử lý — và nên GIỮ 0 import.** Quotation pricing dùng core đúng cách qua custom fields + hooks (`doctype_js` overrides Quotation/Item). G1 chỉ thành "gap" khi mở rộng sang SX/kho/kế toán (đã cần gọi erpnext API) — để §8. ⚠ DoD của bản cũ ("`grep from erpnext` > 0") là **sai mục tiêu** cho phạm vi này. |
| **G2** | **FVB chưa được nối vào engine** | `get_live_context`/`resolve_bindings`/`BatchBindingResolver` → 0 lần gọi; `get_formula_context()` (api/__init__.py:75) chỉ liệt kê cho autocomplete | 🎯 **XỬ LÝ trong đợt này** (Phase B) — theo triết lý "tận dụng tối đa formula_builder". B1 thay resolver tự viết bằng `get_live_context(scope_context_json)`; B2 dùng `resolve_all_bindings_batch`. |
| **G3** | **AL Cost Bucket.source_type chưa được resolve** | `VALID_SOURCE_TYPES` (al_cost_bucket.py:12-16) chỉ validate; `b5_aggregate_cost_buckets` (588) gom bằng loop; `fb_handlers.cost_bucket_aggregate` không được gọi | 🎯 **XỬ LÝ trong đợt này** (Phase B) — B5 resolve LEAF bucket qua handler đã register; bucket AGGREGATE do B6 FlexibleFormulaEngine tính (như hiện tại). |
| **G4** | **3 fb_handlers chưa `@register_source`** | `fb_handlers.py` — 3 hàm plain, không decorator; hooks.py:57-61 chỉ khai báo đường dẫn | 🎯 **XỬ LÝ trong đợt này** (Phase A/B) — đăng ký chuẩn: `@register_source(source_type, label, description, config_schema, app="alumglass", batchable=True, fingerprint_fn, supports_transform, supports_cache, default_cache_ttl)` (đúng signature `source_type_registry.py:489`). |

---

## 4. Bảo mật — RCE qua eval() (BLOCKER) — ⚠⚠ formula_builder CŨNG DÍNH (đã chứng minh)

> ⚠ **Nghiêm trọng — cập nhật 2026-08-16:** không chỉ alumglass dính RCE; **formula_builder CHÍNH NÓ
> cũng dùng `eval()` với cùng pattern lỏng**. Đã kiểm chứng thực nghiệm trên máy (Python 3.10):
> - `eval(expr, {"__builtins__": {}}, {})` → `().__class__.__base__.__subclasses__()` **chạy được** (trả 144 class → tìm subprocess/os để RCE).
> - `eval(expr, {}, {})` → **nghiêm trọng hơn**: Python auto-inject `__builtins__` khi thiếu key → `__import__('os').getcwd()` chạy trực tiếp.
> - Comment FB `data_source_registry.py:145` "Bảo mật thực sự: `eval(__builtins__={})`" là **quan niệm SAI (sandbox myth)**.
>
> **Owner chốt (2026-08-16):** fix RCE **đưa VÀO formula_builder** (nền tảng chung) — không giữ bản local
> alumglass. Một fix gộp đóng RCE **cả alumglass lẫn FB**, và FB thành nền tảng an toàn thực sự.
> Chi tiết: §5 A3 + §12 F1.

| # | Vị trí | Code | Rủi ro |
|---|---|---|---|
| **R1** | `al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py:36` | `_calc_fn_cache[...] = eval(fn_str, safe_ns)` | `safe_ns` không chặn object traversal → RCE nếu tạo/sửa `AL Quantity Calc Method` |
| **R2** | `al_bom_engine/doctype/al_cost_template/al_cost_template.py:42` | `val = eval(expr, {"__builtins__": {}}, {})` | Empty builtins KHÔNG chặn RCE (đã chứng minh) — dùng trong B6 |
| **R-FB1** | **`formula_builder/formula_utils/engine_public.py:452`** (FormulaEngine) | `eval(compiled[name], eval_globals, ctx)` — `_eval_globals = {"__builtins__": {runtime_env}}` (engine_core.py:637) | Chặn `__import__` nhưng **traversal vẫn chạy** → RCE qua công thức của MỌI app dùng FB |
| **R-FB2** | **`formula_builder/api/data_source_registry.py:584, 1075`** | `eval(filter_expr/condition, {"__builtins__": {}}, safe_globals)` | Traversal bypass → RCE (child_table_aggregate filter, conditional) |

**Yêu cầu bắt buộc trước khi production:** không còn `eval()`/`exec()` chạy chuỗi DB ở **cả alumglass lẫn
formula_builder** (trừ test). Giải pháp an toàn: §5 Phase A-A3 (đưa vào FB) + §12 F1.

---

## 5. Kế hoạch triển khai chi tiết — TÍNH GIÁ QUOTATION

> **Nguyên tắc bao trùm:** một nguồn dữ liệu, một nơi resolve, cấu hình thay code. Mọi thứ FB/core đã có
> thì gọi, không tự build lại. **Mọi phase: test vàng CDMQ-2C (`GIA_VAT ≈ 22.717.289đ`) + CDMQ-4C phải
> pass sau mỗi thay đổi.**

---

### PHASE A — Baseline + Bảo mật (blocker, ~tuần 1)

**Mục tiêu:** có môi trường chạy được, xác nhận baseline, đóng lỗ hổng RCE.

| # | Việc | Chi tiết / file | DoD |
|---|---|---|---|
| **A1** | **Cài app lên dev site** | Trên `nxc20`: tạo site dev riêng (đề xuất `alumglass-dev`) HOẶC dùng site dev có sẵn — ⚠ chốt với Owner/DEVOP. Cài `formula_builder` trước (chưa cài site nào), rồi `alumglass` (bench install-app). Chạy `bench migrate`. | `bench list-apps <site>` có formula_builder + alumglass; migrate sạch |
| **A2** | **Chạy baseline test vàng** | `bench --site <site> execute alumglass.run_test.main` (file `alumglass/alumglass/run_test.py` — nhớ đường dẫn đúng, KHÔNG ở app root). Verify `GIA_VAT = 22,717,289` ± 1000 cho CDMQ-2C. | Baseline pass; chụp output làm chuẩn đối chiếu |
| **A3** | **Đóng RCE — ĐƯA VÀO formula_builder (Owner chốt 2026-08-16)** | **(1) Xây safe-evaluator trong FB:** `formula_builder/formula_builder/security/safe_eval.py` — public API (`safe_eval_expr`, `safe_eval_lambda`), whitelist node + whitelist hàm, **chặn dunder attribute/subscript + attribute trên literal** (chặn traversal), nhưng vẫn cho `row.field` hợp lệ trong child_table_aggregate filter. **(2) Sửa 3 eval của FB** dùng safe evaluator: `engine_public.py:452`, `data_source_registry.py:584`, `:1075` (giữ `row.attr` hợp lệ; chặn dunder + literal-traversal). **(3) alumglass dùng FB:** thay `al_quantity_calc_method.py:36` + `al_cost_template.py:42` bằng import `formula_builder.security.safe_eval` — **KHÔNG giữ bản local alumglass**. Backward compat (KHÔNG đổi data). Test FB độc lập + test alumglass. | `grep -rn "eval(\|exec(" alumglass/` **và** `formula_builder/` (trừ test) → rỗng; unit test chứng minh payload RCE bị chặn ở **cả 2 app**; golden test vẫn pass |
| **A4** | **Đóng G4: `@register_source` cho 3 handler** | Sửa `fb_handlers.py` — 3 hàm: `aluminum_price_composite`, `glass_master_data`, `cost_bucket_aggregate` mỗi hàm thêm decorator đúng signature (`source_type_registry.py:489`): `label`, `description`, `config_schema` (JSON Schema), `app="alumglass"`, `batchable=True`, `fingerprint_fn` (vd nhóm theo price_list / glass_code / bucket). | `list_source_types` (API FB) hiện đủ 3 source type + schema + batchable; `get_registry_stats` đếm được |
| **A5** | **Test composite pricing cấp handler** | `tests/test_composite_pricing.py` (đã có: WHITE=113000 vs DARK=999000, determinism) chạy pass trên site đã cài. | Test pass trong `bench --site <site> run-tests --app alumglass` |

> **⚠⚠ RÀNG BUỘC A3 (Owner 2026-08-16):** khi sửa security FB **KHÔNG làm mất tính linh hoạt và performance**:
> - **Flexibility:** 80+ hàm `BASE_FUNCS` (safe_div, lookup_rule, round, math.*...) chạy như cũ; `row.attr` trong
>   child_table_aggregate filter còn (vd `row.qty > 10`); conditional/fallback/IfExp/lambda calc_fn/so sánh/số học
>   không đổi; **backward compat** — công thức DB cũ parse y hệt.
> - **Performance:** safe evaluator nằm trên **hot path** (FormulaEngine từng node `engine_public.py:452`, filter
>   per-row). **AST-interpreter node-by-node CHẬM (10-100×)** → cấm. **Đúng: validate 1 lần lúc build/compile
>   (dùng `SecurityValidator` FB đã có: `formula_utils/security.py`) → `compile` + `eval` với globals whitelist
>   trong hot loop**, giữ `_compiled` cache. Chặn traversal bằng validator off-hot-path.
> - **Baseline:** `PERFORMANCE_REPORT_v31.md` (~2.0–2.5M node/s; 1000-product × 100-formula < 50ms) +
>   `example/benchmark_v31_comprehensive.py`. Chạy benchmark trước/sau → **không tụt quá ~10-15%**.
> - Test FB full (`tests/` incl. `test_security.py`) phải pass sau khi sửa.

> **⚠ Chờ chốt:** A1 (site nào) — đã chốt `alumglass-dev` (2026-08-16); A3 — đã chốt **đưa fix vào FB**. A2/A4/A5 không phụ thuộc quyết định.

---

### PHASE B — FB-max: nối formula_builder vào engine (theo triết lý, ~tuần 2-3)

**Mục tiêu:** B1/B2/B5 đọc giá trị từ **một nguồn resolve duy nhất là FB** (FVB + BatchBindingResolver +
handler đã register), bỏ resolver tự viết. **Giữ golden test không đổi.**

| # | Việc | Chi tiết / file | DoD |
|---|---|---|---|
| **B1** | **Nối `get_live_context` vào B1** | Thay `_resolve_system_variables()` (bom_orchestrator.py:123) bằng `get_live_context(scope_context_json)` — scope context dạng `{"current_doctype": "Quotation Item", "current_docname": <qi_name>}` (đúng chữ ký `formula_builder.py:274`). Global binding (VAT_RATE, OH_VC_PCT, OH_QLY_PCT) + system variable resolve tự động (topological sort, fallback `default_value`). **Đồng bộ dữ liệu:** seed FVB bindings từ AL Variable Library (1 lần, `patches/`), giữ Variable Library làm fallback backward-compat (như code hiện giữ CONSTANT rule). | Engine B1 không còn query tay Variable Library/Profile/Product Type; golden test pass |
| **B2** | **Nối `BatchBindingResolver` vào B2** | Thay `_fetch_composite_prices`/`_match_composite_price` (bom_orchestrator.py:373-437) bằng `resolve_all_bindings_batch(bindings, ...)` (`batch_binding_resolver.py:508`). Handler `aluminum_price_composite` (đã register, batchable, fingerprint theo price_list) tự gom toàn bộ item_code cùng fingerprint → 1 query Item Price. `glass_master_data` batch theo glass_code. | B2 không còn SQL tay cho Item Price/Glass; composite pricing vẫn khớp dòng đúng (multi-color test pass) |
| **B3** | **B5 resolve `source_type` của Cost Bucket** | `b5_aggregate_cost_buckets` (588) — LEAF bucket (`aggregate_from_items`) gọi handler `cost_bucket_aggregate` đã register; AGGREGATE bucket do B6 FlexibleFormulaEngine tính (như hiện tại). Thống nhất vocabulary hoặc giữ 2 vocabulary có map — ⚠ chốt (đề xuất: giữ `VALID_SOURCE_TYPES` hiện có + handler resolve, không đổi data seed). | B5 không còn loop cứng; tính đúng theo `source_config`; golden test pass |
| **B4** | **B3 thay regex bằng transformer** | `b3_build_formulas` (479): regex `items.X.Y → X__Y` (510) thay bằng `DotToSubscriptTransformer` (`formula_utils/parser.py:18`). Nếu cần sinh formula từ Bom Set tự động: `MultiTableFormulaBuilder` (`table_formula_builder.py:115` — ✅ tồn tại trong FB hiện có) — ⚠ xác minh mức độ thay thế khả thi, KHÔNG bắt buộc. | B3 không dùng regex thủ công; golden test pass |
| **B5** | **B4/B6: `on_error` phục hồi** | ⚠ **SỬA SO VỚI BẢN CŨ:** `on_error` hợp lệ chỉ là `{"raise", "null", "default"}` (`engine_core.py:248`, `flexible_formula_engine.py:222`) — **KHÔNG có "continue"**. Đề xuất: B4/B6 chuyển `on_error="raise"` (bom_orchestrator.py:559,640) → **`"default"`** kèm `default_value` + trả danh sách lỗi structured, ghi vào ConfigSnapshot — 1 dòng sai KHÔNG chết cả BOM. Lưu ý: chia cho 0 LUÔN fatal bất kể mode (`errors.py:131`) → phải chặn ở nguồn data (default_value hợp lệ). | BOM có 1 dòng lỗi vẫn trả kết quả các dòng khác + danh sách lỗi; golden test pass |
| **B6** | **`get_formula_context` dùng chung FB** | `api/__init__.py:75` — autocomplete context lấy từ 1 nguồn `get_live_context` thay vì liệt kê tay. | JS dialog autocomplete khớp binding thật |

> **⚠ Chốt:** B1 (đồng bộ Variable Library → FVB: seed 1 chiều hay map động), B3 (vocabulary cost bucket).

---

### PHASE C — Đúng-sai báo giá + sẵn sàng production (~tuần 3-4)

**Mục tiêu:** báo giá tái lập được, không timeout, hiển thị đúng, composite pricing được kiểm chứng
trong luồng thật.

| # | Việc | Chi tiết / file | DoD |
|---|---|---|---|
| **C1** | **Test composite pricing TRONG luồng thật** | Thêm test orchestrator-level: CDMQ-2C golden (WHITE) + cùng BOM đổi DARK → giá đổi theo composite key đúng (không còn bug "đổi màu không đổi giá"); test determinism (chạy 2 lần bằng nhau). Phủ 2 chế độ: `exact_match` + `multiplier_chain`. | Test pass; phát hiện regression nếu `_match_composite_price` lệch |
| **C2** | **P1 — Versioning Pricing Dimension** | Theo design đã có `P1-pricing-dimension-versioning.md`: +1 field `pricing_dimension_snapshot` (Long Text, read_only, no_copy) trên `al_bom_version.json`; `_snapshot_pricing_dimensions()` chụp toàn bộ AL Pricing Dimension + AL Variable Dimension Mapping khi Publish; mở rộng `_guard_published_immutability`; engine `_get_dim_fieldnames` đọc snapshot trước, fallback live (cảnh báo); patch backfill `patches/v28_9/backfill_pricing_dimension_snapshot.py`. | BOM Version Published không thể thay đổi pricing config; báo giá cũ tái lập được; golden test pass |
| **C3** | **P2 — Async BOM cho BOM lớn** | Theo design `P2-async-bom-calculation.md`: Global Variable `ASYNC_BOM_THRESHOLD` (default 150); `api/calculate_bom` đếm dòng từ `bom_set_snapshot` → ≤ threshold sync, > threshold `frappe.enqueue(queue="long", timeout=600)`; **bắt buộc `frappe.set_user(user)` trong worker**; +3 custom field Quotation Item (`al_calc_status`, `al_calc_job_id`, `al_calc_error`); client JS nghe `frappe.publish_realtime("alumglass_bom_calc_done")`, filter theo job_id. ⚠ Vận hành: cần worker `bench worker --queue long`. | BOM > threshold chạy background, realtime cập nhật status; small BOM vẫn sync |
| **C4** | **Hoàn thiện response + dialog** | `api/__init__.py` response format (buckets + cost_template keys + lines — client tự chọn key, động). `public/js/bom_dialog.js` + `quotation_item_dialog.js`: hiển thị đủ keys, trạng thái loading/error, xử lý khi đóng dialog mở lại (đọc `al_calc_status`). | Sales User tính giá 1 Quotation hoàn chỉnh không lỗi; UI phản hồi đúng |
| **C5** | **Print Format báo giá (⚠ chốt Owner)** | Hiện chỉ có JSON `al_bom_result` trong Quotation Item. Nếu báo giá cần xuất: tạo Print Format báo giá tối thiểu (đọc `al_bom_result` + item fields). **Nếu Owner muốn giữ strict scope, C5 bỏ qua** (tầng ứng dụng Frappe, không thuộc module nghiệp vụ). | (nếu làm) Print Format ra được báo giá từ data có sẵn, không tính lại |

> **⚠ Chốt:** C2 (có chấp nhận patch backfill dùng config hiện tại không), C5 (làm print format hay không).

---

### PHASE D — Đóng gói, test chuẩn & docs (~tuần 4)

**Mục tiêu:** nghiệm thu được, CI-ready, docs đi cùng code (bắt buộc theo CLAUDE.md).

| # | Việc | Chi tiết | DoD |
|---|---|---|---|
| **D1** | **Test suite FrappeTestCase chuẩn** | Chuyển/bao quanh `run_test.py` thủ công (SQL trực tiếp) thành `tests/` dùng `FrappeTestCase` + fixtures (`seed_demo_data`). Tối thiểu: `test_bom_orchestrator` (golden 22,717,289 + CDMQ-4C), `test_composite_pricing` (multi-color), `test_fb_handlers_registered`, `test_safe_eval` (RCE bị chặn), `test_async_threshold` (mock enqueue), `test_on_error_recovery`, `test_snapshot_immutability`. | `bench --site <site> run-tests --app alumglass` pass toàn bộ, không cần thao tác tay |
| **D2** | **Docs đi cùng code** | ⚠ Bắt buộc (CLAUDE.md): `docs/design/quotation-pricing.md` (kiến trúc FB-max nối B1/B2/B5 + security model); `docs/usage/quotation-pricing.md` — **kèm `contexts:`** (`Form/Quotation Item`) và **`tags:`** (Bán hàng & CRM); sửa `TONG_QUAN_KIEN_TRUC.md` (v16 → 14.92.14), cập nhật `PRODUCTION_REFERENCE` (danh sách API, flow). | Knowledge đồng bộ code; đủ `knowledge_updated` khi ship |
| **D3** | **Migrate/data plan** | App chưa production → không phá data. Seed demo (CDMQ-2C/4C) cho test. `patches/` cho: FVB seed (B1), backfill snapshot (C2). | Patch chạy idempotent; golden test pass sau migrate |
| **D4** | **Đánh dấu milestone + nghiệm thu** | Báo Owner qua `working/outbox/` (closure) — kèm kết quả test, docs cập nhật, quyết định đã chốt. | Owner xác nhận |

---

## 6. Definition of Done — tổng (đợt quotation pricing)

- [ ] App `alumglass` + `formula_builder` cài trên site dev, `bench migrate` sạch.
- [ ] `grep -rn "eval(\|exec(" alumglass/` **VÀ** `formula_builder/` → **rỗng** (trừ test); unit test chứng minh payload RCE bị chặn ở cả 2 app.
- [ ] `list_source_types` hiện đủ **3 source type** alumglass với schema + `batchable=True`.
- [ ] Engine B1/B2/B5 resolve qua FB (FVB/`get_live_context`/`BatchBindingResolver`/handler đã register) —
      **không còn resolver tự viết** cho Variable Library / Item Price composite / Cost Bucket.
- [ ] `on_error` dùng `{"raise","null","default"}` hợp lệ; BOM lỗi 1 dòng KHÔNG chết cả lần tính;
      lỗi structured ghi ConfigSnapshot.
- [ ] **Test vàng CDMQ-2C (`GIA_VAT ≈ 22.717.289đ`) + CDMQ-4C pass** sau MỌI phase (không đổi giá trị).
- [ ] Composite pricing test **trong luồng thật** (multi-color, exact_match + multiplier_chain) pass.
- [ ] P1 versioning: `pricing_dimension_snapshot` + guard immutability + backfill patch.
- [ ] P2 async: BOM > threshold chạy background + realtime; small BOM vẫn sync.
- [ ] `bench --site <site> run-tests --app alumglass` pass toàn bộ (không phụ thuộc run_test tay).
- [ ] Docs đi cùng code (design + usage kèm `contexts`/`tags`), `knowledge_updated` đủ.

---

## 7. Rủi ro kỹ thuật (cập nhật 2026-08-16)

| # | Rủi ro | Vị trí | Khuyến nghị | Trạng thái đợt này |
|---|---|---|---|---|
| **R1** | `eval()` RCE (calc_fn) | `al_quantity_calc_method.py:36` | Safe evaluator **trong FB** (`formula_builder/security/safe_eval.py`) — alumglass import FB | 🎯 Phase A-A3 |
| **R2** | `eval()` RCE (cost template expr) | `al_cost_template.py:42` | Như R1 | 🎯 Phase A-A3 |
| **R-FB** | ⚠⚠ **formula_builder chính nó cũng RCE** (3 eval lỏng) | `engine_public.py:452`, `data_source_registry.py:584/1075` | Đưa safe-evaluator vào FB + sửa 3 eval FB (F1 §12) — đã chứng minh thực nghiệm | 🎯 Phase A-A3 |
| **R3** | `on_error="raise"` chết cả BOM | bom_orchestrator.py:559,640 | `on_error="default"` + `default_value` + structured errors (⚠ "continue" không tồn tại) | 🎯 Phase B-B5 |
| **R4** | Pricing Dimension chưa versioning | `al_pricing_dimension` | Snapshot `pricing_dimension_snapshot` vào AL BOM Version khi Publish (design đã có) | 🎯 Phase C-C2 |
| **R5** | BOM >200 dòng timeout | `api.calculate_bom` | Async: `frappe.enqueue` + realtime (design đã có) | 🎯 Phase C-C3 |
| **R6** | App + formula_builder **chưa cài site nào** | — | Phase A-A1; xác minh `bench list-apps` | 🎯 Phase A |
| **R7** | Monkey-patch JS `_ContextBuilder.build()` | `public/js/formula_setup.js` | Tạm giữ + mở issue ngược FB có hook chính thức | ⚠ giữ nguyên, theo dõi |
| **R8** | Custom field nở rộ trên Quotation Item (19 field) | `setup/custom_fields.py` | Gộp nhập liệu vào JSON (`al_bom_vars`), chỉ giữ field nghiệp vụ | ⚠ tối ưu dần, không chặn |
| **R9** | `_resolve_doc_values` nuốt exception | `api/__init__.py:69` | Log thay `pass` im lặng | 🎯 Phase C-C4 |
| **R10** | FB Snapshot +871-1014% chậm | formula_builder | KHÔNG dùng Formula Snapshot cho mỗi lần tính BOM — AL BOM Version snapshot + ConfigSnapshot là đủ | ✅ đã đúng, giữ |

---

## 8. Ngoài phạm vi Sprint 1 — tương lai (đã có roadmap đầy đủ ở §11)

> **Ghi chú cập nhật (2026-08-16):** Owner yêu cầu bổ sung kế hoạch **đầy đủ tất cả phân hệ** như v28.
> Phần dưới chỉ là tóm tắt nhanh từng module "để sau" — **kế hoạch triển khai chi tiết từng phân hệ
> nằm ở §11**, track phát triển formula_builder nền tảng chung ở §12.

| Hạng mục | Lý do để sau |
|---|---|
| **Core BOM instantiate** (AL BOM → core BOM, v28.9) + MRP/Material Request/Production Plan (v28.10: instantiate theo kích thước thực từ Site Survey Approved) | Thuộc luồng SX/Mua — vượt phạm vi quotation. ⚠ đây là lúc cần `from erpnext import` (đảo G1) |
| **Inventory Dimension (kho đa chiều Màu/Loại/Dày)** | Owner chốt tách khỏi giá (2026-08-13); thuộc luồng kho, không phải báo giá |
| **Cost Center + Accounting Dimension** cho P&L theo bucket | Thuộc kế toán; cần BA chốt mapping bucket→cost center |
| **HRMS Timesheet/Expense Claim** cho NC_LD thực tế | Báo giá ≠ chi phí thực; chạy song song 2 chế độ khi có thi công |
| **AL Construction** toàn bộ (Site Survey, Installation...) | Module nghiệp vụ riêng |
| **AL Manufacturing** (Cutting Plan nhôm 1D/kinh 2D — **thuật toán chưa implement**), Cutting Standard | Thuật toán cắt là dự án riêng |
| **AL Account** (P&L Snapshot, Project Financial Config), **AL Buying** (Material Plan, Cost Variance) | Kế toán/Mua |
| **AL AI** (Suggestion/Interaction Log), **AL Quality** (Warranty Policy) | Phụ trợ |
| **AL Accessory Set** | deprecated candidate (A7) |
| Tầng ứng dụng Frappe: Notification/Email, Dashboard KPI, Webhook, Translation | Trừ Print Format báo giá (C5, ⚠ chốt) — đều ngoài phạm vi |
| Migrate `calc_fn`/`expr` sang FB `custom_function` whitelist (thay AST evaluator) | Cải tiến FB-max sâu hơn; khi Owner muốn "0 eval kể cả trong trường hợp phức tạp" |

---

## 9. Lộ trình (timeline ước lượng)

```
Tuần 1      Tuần 2            Tuần 3               Tuần 4
──────────  ───────────────   ───────────────────   ────────────────────
A1 install  │  B1 get_live    │  C1 composite thật  │  D1 test FrappeTestCase
A2 baseline │  B2 BatchResolv │  C2 P1 versioning   │  D2 docs (contexts/tags)
A3 eval RCE │  B3 bucket      │  C3 P2 async        │  D3 patches/migrate
A4 register │  B4 transformer │  C4 dialog/response │  D4 milestone + outbox
A5 handler  │  B5 on_error    │  C5 print (⚠ chốt)  │
test        │  B6 ctx FB      │                     │
```

**Điểm chờ quyết định (gating):**
- A1: site dev nào (tạo mới `alumglass-dev` hay dùng site có sẵn).
- A3: chọn AST safe-eval (nhanh, backward-compat) hay FB `custom_function` (thuần FB-max hơn, đổi data).
- B1: đồng bộ Variable Library → FVB — seed 1 chiều (khuyến nghị) hay map động.
- B3: giữ vocabulary Cost Bucket hiện có + handler resolve (khuyến nghị) hay đổi sang 13 loại FVB.
- C2: chấp nhận backfill dùng config hiện tại cho BOM Version cũ không.
- C5: có làm Print Format báo giá tối thiểu không.

**Những việc KHÔNG phụ thuộc quyết định (DEV có thể bắt đầu ngay):** A2 (baseline test), A4 (register
handler), A5, B4 (transformer), B5 (on_error), C1 (test composite thật), C4 (dialog/response).

---

## 10. Kết luận

AlumGlass đã có nền **config-driven rất tốt cho tính giá quotation** (engine 7-phase chạy thật, test vàng,
batching query, snapshot immutable, composite key đã fix v28.8). Đợt triển khai này **không xây lại gì** —
chỉ: (1) đóng 2 lỗ hổng RCE, (2) cài app + chạy baseline test, (3) nối formula_builder tối đa theo đúng
triết lý "Config > Code" (đăng ký handler + FVB + BatchBindingResolver, bỏ resolver tự viết), (4) làm cho
báo giá **đúng-sai và tái lập được** (composite thật, versioning, async, on_error phục hồi), (5) đóng gói
test chuẩn + docs đi cùng code.

Kết quả: tính giá quotation là **lớp mỏng nghiệp vụ** — cấu hình ở DB, tính toán ở formula_builder,
nghiệp vụ chuẩn ở ERPNext (Quotation/Item/Item Price), **0 dòng `from erpnext import` (đúng — không cần)**.

**Về tổng thể:** theo yêu cầu Owner 2026-08-16, đợt này là **Sprint 1 (tính giá quotation)** trong roadmap
**toàn phân hệ** của một ERP chuyên ngành nhôm kính — chi tiết từng module, từng sprint, mức tận dụng
core/FB và lượng code tự viết còn lại nằm ở **§11**; việc phát triển **formula_builder thành nền tảng chung**
(dùng lại cho nhiều ngành) nằm ở **§12**. Các module còn lại (SX & Cắt, Kho, Mua, Thi công, Kế toán, AI)
**được lên kế hoạch đầy đủ nhưng triển khai theo thứ tự phụ thuộc**, KHÔNG làm trong Sprint 1.

---

## 11. Roadmap toàn phân hệ — kế hoạch triển khai TẤT CẢ module (bổ sung 2026-08-16)

> **Yêu cầu Owner (2026-08-16):** alumglass là dự án chuyên ngành nhôm kính, có **đầy đủ phân hệ như một
> ERP**. Bổ sung kế hoạch triển khai **toàn bộ phân hệ** (như v28) vào tài liệu này. Nguyên tắc xuyên suốt:
> **tận dụng tối đa core ERPNext/Frappe + formula_builder, và phát triển formula_builder thành nền tảng chung**
> (track riêng ở §12).
>
> **Cấu trúc:** §11.2 roadmap tổng thể (sprint) → §11.3–11.8 từng sprint với plan chi tiết theo 5 cột
> (Phân hệ / Doctype · Core reuse · FB reuse · Code tự viết còn lại · DoD). §11.9 ma trận tổng hợp.
> Sprint 1 = §5 (đang triển khai, giao DEV ngay phần không phụ thuộc quyết định).

### 11.1 Nguyên tắc chung cho toàn phân hệ

1. **Core-first:** phân hệ nào ERPNext/Frappe đã có luồng chuẩn → **dùng nguyên bản**, custom chỉ qua
   custom fields + hooks + `doctype_js` (overrides), **KHÔNG tạo doctype mới trùng core** (đã bỏ 5 DocType
   trùng core ở v28.9). `from erpnext import` chỉ xuất hiện khi thực sự cần gọi API core (bridge/trigger).
2. **FB-max:** mọi *tính toán động* (giá, lượng vật tư, chi phí, cắt) → giao formula_builder
   (FVB/`get_live_context`/`BatchBindingResolver`/handler đăng ký chuẩn). Cấu hình ở DB, 0 dòng code.
3. **Tách bạch 2 cơ chế (Owner chốt 2026-08-13):** **AL Pricing Dimension** = giá bán/tham chiếu giá
   (tra trong dialog Quotation, composite key); **Inventory Dimension** = kho (balance/valuation theo
   Màu/Loại/Dày). Không lẫn: kho valuation theo giá mua thực tế, KHÔNG dùng color_multiplier từ giá bán.
4. **KHÔNG Item Variant (v28.9 #16):** Item = "mã nhôm đại diện"; spec (màu, kính, kích thước) là
   transaction attribute theo Project / per-project Variable Set.
5. **Tính pháp lý của dữ liệu:** mọi bước sinh dữ liệu có **ConfigSnapshot** (SHA-256 fingerprint) →
   tái lập được; BOM Version Published bất biến.
6. **Tuần tự theo phụ thuộc:** mỗi sprint xây trên kết quả sprint trước (giá → mua/kho → sản xuất →
   thi công → kế toán). Song song hoá được giữa các DEV ở các module *không đụng file* nhau.

### 11.2 Roadmap tổng thể

| Sprint | Phân hệ | Mục tiêu | Phụ thuộc | Module/Doctype |
|---|---|---|---|---|
| **S1** (đang làm) | Tính giá quotation | §5 Phases A-D (security, FB-max, đúng-sai, test) | — | al_master_data, al_bom_engine, al_formula_rules, al_selling |
| **S2** | Bán hàng hoàn chỉnh + nền sản xuất | SO → core; core BOM instantiate (v28.9/10); per-project | S1 | al_selling, al_bom_engine bridge, al_stock (warehouse map) |
| **S3** | Kho & Mua | Inventory Dimension (nhôm Màu / kính Loại×Dày×Màu); nhập kho; Material Request → PO | S1 (giá), S2 (BOM) | al_stock, al_buying |
| **S4** | Sản xuất & Cắt | Core BOM → WO → **Cutting Plan** (1D nhôm FFD / 2D kính Guillotine); Quality | S2 (core BOM), S3 (kho) | al_manufacturing, al_quality |
| **S5** | Thi công & Nhân công | Site Survey → Installation Order → Progress → Handover; HRMS nhân công | S2, S4 | al_construction (+ HRMS) |
| **S6** | Kế toán & P&L | Cost Center + Accounting Dimension; Project Profitability; Cost Variance | S3, S5 | al_account |
| **S7** | AI & tầng ứng dụng | AI suggestion/interaction; Print/Dashboard/Notification/Webhook | S1–S6 | al_ai_intelligence, app layer |
| **FB** | formula_builder nền tảng chung | §12 — phát triển FB thành nền tảng (safe-eval, composite lookup, async, versioned config, optimizer) | xuyên suốt | formula_builder |

---

### 11.3 Sprint 2 — Bán hàng hoàn chỉnh + Nền sản xuất (core BOM bridge)

> **Nền tảng:** S1 đã có tính giá quotation + composite pricing + snapshot. Sprint này "nối" AL BOM (formula)
> sang core ERPNext để mở luồng SX/Mua.

**Phân hệ AL Selling (custom trên core) — hoàn chỉnh:**

| Cột | Nội dung |
|---|---|
| Doctype | Core `Quotation`, `Sales Order`, `Sales Invoice`, `Price List`, `Pricing Rule`, `Discount`. Custom fields `al_*` đã có trên Quotation/Item/Item Price. |
| Core reuse | Toàn bộ luồng bán: Quotation → SO → SI → AR. `Pricing Rule` (chiết khấu — E5 giữ nguyên bản). `doctype_js` override Quotation/SO (đã có). |
| FB reuse | Giá bán động qua `aluminum_price_composite` (đã register S1) + `get_live_context` cho tham số báo giá. Dynamic Item Rule (nẹp/keo) — giữ làm rule ngành (đã chốt). |
| Code tự viết còn lại | Bổ sung: SO → Quotation copy hoàn chỉnh (`al_bom`, `al_bom_vars`, `al_config_snapshot` carry sang SO Item); hook ghi `al_quote_config` vào SO Item; validation chặn sửa sau chốt. |
| DoD | SO tạo từ Quotation giữ nguyên cấu hình BOM; báo giá → SO không mất tham số; Pricing Rule core chạy đúng; golden test không đổi. |

**Phân hệ Production BOM Bridge — core BOM instantiate (kế hoạch v28.9/v28.10 đã chốt):**

| Cột | Nội dung |
|---|---|
| Cơ chế | AL BOM là **công thức động** (giữ). Khi **AL Site Survey Approved** → hook `instantiate_production_bom` (mẫu: `04_production-bridge-plan.md`) tính lại AL BOM theo kích thước **KHẢO SÁT THỰC** → **ConfigSnapshot production** (fingerprint) → tạo **core BOM is_default=0** (reuse theo fingerprint, cùng kích thước gom 1 BOM) → set `Sales Order Item.bom`. |
| Core reuse | Core `BOM`, `Production Plan` (`get_items_from = Sales Order`), `Material Request`, `Work Order`. |
| FB reuse | ConfigSnapshot production chính là output B7 (`b7_save_results`) — tính lại AL BOM theo W/H thực = gọi lại engine (S1). |
| Code tự viết | Hook on_submit Survey (Approved) + cache fingerprint reuse + guard `action_required ∈ (RESIZE, REDESIGN)` chờ Design Revision. |
| ⚠ Chốt | Per-project Variable Set (màu/kính/phụ kiện từ Survey) — cơ chế gán; ngưỡng nào cần Design Revision mới (RESIZE/REDESIGN threshold). |
| DoD | Survey Approved sinh đúng core BOM theo kích thước thực; Production Plan explode đúng; fingerprint reuse không nhân BOM trùng. |

---

### 11.4 Sprint 3 — Kho & Mua (Inventory Dimension + Buying)

> **Nền tảng:** S2 có core BOM → cần kho để nhập phôi + MR/PO. Thiết kế kho đa chiều đã chốt
> (`05_inventory-dimension-design.md`).

**Phân hệ AL Stock (custom trên core) — Inventory Dimension:**

| Cột | Nội dung |
|---|---|
| Doctype | Core `Inventory Dimension` (**Master**, v14.5+ ổn định — đã verify source), `Stock Entry`, `Stock Ledger Entry`, `Batch`, `Serial No`, `Warehouse`, `Project`. Custom fields `al_*` trên Batch/Serial (offcut: `al_piece_length_mm`, `al_is_offcut`, `al_parent_cut_id`). |
| Core reuse | Inventory Dimension record: **Nhôm → Màu** (`AL Color Standard`); **Kính → Loại × Độ dày × Màu** (`AL Glass Type`, `AL Glass Thickness` 🆕, `AL Color Standard`). Core auto-sinh field trên Stock Entry Detail/SLE + balance/valuation/negative-stock theo dimension. Core `Stock Balance`/`Stock Ledger` report đã hỗ trợ dimension columns → **không cần custom report**. `Batch` cho lô nhập; `Serial No` cho offcut (per-unit, độc lập dimension). |
| FB reuse | — (kho không phải formula-driven; chỉ dùng FB ở mức tính nhu cầu vật tư: `cost_bucket_aggregate`/B5 output). |
| Code tự viết | Seed 3 dimension config (reference doctype); project warehouse map (`AL Project Warehouse Map`); validate dimension bắt buộc trên Stock Entry theo item type. ⚠ `Item Price` KHÔNG có dimension (verified) → giá mua theo dimension xử lý ở Buying (mục dưới). |
| DoD | Nhập kho nhôm theo Màu, kính theo Loại×Dày×Màu → balance + valuation riêng từng dimension; SLE âm theo dimension bị chặn; Stock Balance report hiện đúng theo dimension. |

**Phân hệ AL Buying (custom trên core):**

| Cột | Nội dung |
|---|---|
| Doctype | Core `Material Request`, `Supplier`, `Supplier Quotation`, `Supplier Quotation Comparison` (Item-wise), `Purchase Order`, `Purchase Receipt`, `Purchase Invoice`, `Supplier Scorecard`. Custom: **AL Cost Variance** (giữ tối thiểu — đọc accounting, nối core Budget/Budget Variance). |
| Core reuse | `Material Request` (mua) + `Production Plan` (SX) sinh từ core BOM (S2). `Supplier Quotation` + **Comparison** → `PO`. **Đã bỏ** AL Supplier Price List / AL Material Plan (trùng core, v28.9). |
| FB reuse | Tính nhu cầu vật tư tổng hợp = output B5/B6 (S1); so sánh giá NCC (hiệu giá % theo composite key) có thể dùng handler giá (FB). |
| Code tự viết | Nối MR → RFQ → SQC → PO khi có S2; cấu hình `AL Cost Variance` (thu hồi chi phí thực vs dự toán — ⚠ chờ BA chốt mapping bucket→cost center, xem S6); giá mua theo dimension (Item Price không có dimension — đề xuất: supplier-specific Item Price theo item + dimension fields custom hoặc dùng `custom_pd_*`). |
| DoD | MR/PO đi qua core; supplier price comparison theo composite key đúng; Cost Variance khớp số liệu accounting. |

---

### 11.5 Sprint 4 — Sản xuất & Cắt (Manufacturing + Quality)

> **Nền tảng:** S2 core BOM + S3 kho. **Lưu ý quan trọng:** thuật toán cắt hiện **chưa implement**
> (docs nói FFD/Guillotine nhưng code chưa có) — là khối lượng thật của sprint này, tận dụng FB optimizer (§12.3-F6).

**Phân hệ AL Manufacturing (custom trên core):**

| Cột | Nội dung |
|---|---|
| Doctype | Core `Work Order`, `Job Card`, `Operation`, `Routing`, `Production Plan`, `Stock Entry` (manufacture). Custom: **AL Cutting Standard**, **AL Cutting Plan (Aluminum)** + Item, **AL Cutting Plan (Glass)** + Item. |
| Core reuse | WO/Job Card/Routing core chạy production; `Stock Entry manufacture` thành phẩm. **Đã bỏ** AL Production Order Bridge (v28.9 — thay bằng core BOM bridge S2). |
| FB reuse | **Cắt nhôm 1D (FFD)** + **Cắt kính 2D (Guillotine)** → implement như **FB optimizer source type** (F6 §12.3): input = danh sách (length/width, qty) từ WO, output = pattern cắt + phế liệu. Tính tối ưu gom phôi (stock dimension) có thể dùng FVB. |
| Code tự viết | Thuật toán cắt 1D/2D (register FB); sinh Cutting Plan từ WO; ghi nhận offcut → Serial No (`al_is_offcut`) → tái dùng; cập nhật cutting progress. |
| ⚠ Chốt | Quy tắc cắt nghiệp vụ (dung sai, cạnh, vị trí ưu tiên) — cần BA chốt trước khi viết optimizer. |
| DoD | Cutting Plan sinh từ WO đúng kích thước thực (Survey), tối ưu ≥ mức chi phí hiện tại, offcut tracked; WO complete → thành phẩm nhập kho dimension đúng. |

**Phân hệ AL Quality (custom trên core):**

| Cột | Nội dung |
|---|---|
| Doctype | Core `Quality Inspection`, `Quality Inspection Template/Parameter`, `Warranty Claim`. Custom: **AL Warranty Policy** (1 doctype). |
| Core reuse | QI gắn WO/Stock Entry; Warranty Claim core. |
| FB reuse | — |
| Code tự viết | AL Warranty Policy (thời hạn theo sản phẩm); khi QI fail → chặn/flag WO. |
| DoD | QI theo template trên production; warranty policy hiển thị trên báo giá/BI. |

---

### 11.6 Sprint 5 — Thi công & Nhân công (Construction + HRMS)

> **Nền tảng:** S2 core BOM (Survey trigger đã có), S4 cắt. Phân hệ lớn nhất của ngành — khối lượng
> thiết kế ở v28 đã đầy đủ (10 doctype).

**Phân hệ AL Construction (new — 10 doctype):**

| Cột | Nội dung |
|---|---|
| Doctype | `AL Installation Team`, `AL Site Survey` + Item, `AL Installation Order`, `AL Installation Task`, `AL Installation Progress`, `AL Installation Cost Actual`, `AL Change Order`, `AL Handover Acceptance`, `AL Punchlist Item`. |
| Core reuse | `Project` + `Project Task` (nghiệp vụ thi công), `Employee` (nhân công), core `Timesheet` (HRMS) cho thời gian, `Asset` (nếu thiết bị). Site Survey Approved = trigger core BOM instantiate (S2) — **Owner đã duyệt giữ nguyên v28.10**. |
| FB reuse | Tính chi phí thi công (NC_LD, vật tư phụ) theo Progress → `AL Installation Cost Actual` (FVB `computed`/handler); ước lượng vs thực tế (Estimate vs Actual — Owner chốt). |
| Code tự viết | Workflow Site Survey (Draft→Approved→Instantiate); Installation Order/Task/Progress CRUD + realtime update; Change Order → ghi nhận → ảnh hưởng báo giá (đối chiếu ConfigSnapshot); Handover + Punchlist. |
| ⚠ Chốt | Quy trình thi công thực tế (team, ca, nghiệm thu) — BA phối hợp Site Engineer; ngưỡng Change Order tự trigger. |
| DoD | Survey → Instantiate BOM → Installation Order → Progress → Handover đầy đủ; chi phí thực đối chiếu dự toán. |

**Phân hệ Nhân công (HRMS — KHÔNG tự build):**

| Cột | Nội dung |
|---|---|
| Doctype | Core HRMS: `Employee`, `Attendance`, `Timesheet`, `Expense Claim`, `Payroll`, `Leave`. (`al_hr` hiện là **shell rỗng** — bỏ dần, dùng HRMS nguyên bản.) |
| Core reuse | NC_LD báo giá giữ ước lượng (%/hệ số — S1 B6). Chi phí **thực tế**: `Timesheet` + `Expense Claim` gắn `Project`/`Task`. **Chạy song song 2 chế độ** (đã đề xuất §3.3) — báo giá ≠ chi phí thực. |
| FB reuse | — |
| DoD | Timesheet/Expense Claim theo Project gom vào Cost Actual; báo giá không phụ thuộc (giữ ước lượng). |

---

### 11.7 Sprint 6 — Kế toán & P&L (Account)

> **Nền tảng:** cần kho (S3) + thi công (S5) để có chi phí thực. P&L theo bucket/dự án.

**Phân hệ AL Account (custom trên core):**

| Cột | Nội dung |
|---|---|
| Doctype | Core `Cost Center`, `Accounting Dimension`, `Journal Entry`, `Budget`, `Project`, `Accounts Receivable/Payable`, `Project Profitability`. Custom: **AL Project Profitability Snapshot**, **AL Project Financial Config**. |
| Core reuse | **Cost Center + Accounting Dimension** cho P&L theo dự án/bucket (điểm E12 — đã có thiết kế, cần code). Core `Budget` + `Budget Variance Report`. `Project Profitability` core đã tổng hợp chi phí/doanh thu theo project. |
| FB reuse | Rollup P&L theo bucket (B5/B6 output) → handler FB cho report; dự toán vs thực tế (`computed`). |
| Code tự viết | Mapping **Cost Bucket → Cost Center** (⚠ chờ BA chốt bảng mapping — gating S6); `AL Project Profitability Snapshot` (đọc core GL theo Accounting Dimension, chụp định kỳ); `AL Project Financial Config` (tỷ lệ phân bổ). |
| DoD | P&L theo dự án/bucket ra đúng từ GL (Accounting Dimension); budget vs variance báo đúng; snapshot tái lập. |

---

### 11.8 Sprint 7 — AI & tầng ứng dụng

| Cột | AL AI (new — 3 doctype) | Tầng ứng dụng Frappe |
|---|---|---|
| Doctype | `AL AI Suggestion Log`, `AL AI Interaction Log`, `AL Alert Config` | Core `Notification`/`Email Alert`, `Print Format`, `Dashboard`/`Number Card`, `Webhook`, `Report Builder`, `Translation` |
| Core reuse | Frappe `/api/method` + LLM (integration) | Nguyên bản core |
| FB reuse | Suggestion sinh từ phân tích BOM/cost (handler FB) | — |
| Code tự viết | Ghi log interaction/suggestion; alert config (ngưỡng giá, biên lợi nhuận thấp); nối LLM API | **Print Format báo giá** (đọc `al_bom_result` + item fields — S1 C5 ⚠ chốt); Notification khi BOM published / đơn giá composite thiếu / Survey approved; Dashboard KPI (doanh thu, margin theo bucket); Webhook public. |
| DoD | Suggestion/Alert hoạt động từ dữ liệu thật; báo giá ra PDF đẹp; dashboard KPI realtime | — |

### 11.9 Ma trận tổng hợp — module → chiến lược triển khai

| Module | Loại | Core reuse (chính) | FB reuse | Code tự viết ước lượng | Sprint |
|---|---|---|---|---|---|
| al_master_data | New | Item, Item Price (`custom_pd_*`), UOM | FVB, composite handler | Thấp (seed + validate) | S1 |
| al_bom_engine | New | (ConfigSnapshot) | FormulaEngine, FlexibleFormulaEngine, snapshot | Trung bình (engine đã có — nối FB) | S1 |
| al_formula_rules | New | — | custom_function, conditional, fallback_chain | Thấp (rule ngành) | S1 |
| al_selling | Custom | Quotation/SO/SI, Price List, Pricing Rule | composite pricing | Thấp (dialog + carry config) | S1–S2 |
| al_buying | Custom | MR, RFQ, SQC, PO, PR, PI, Supplier Scorecard | nhu cầu từ B5/B6 | Thấp–Trung bình | S3 |
| al_stock | Custom | Inventory Dimension, SLE, Batch, Serial, Stock Balance report | — | Trung bình (dimension config + offcut) | S3 |
| al_manufacturing | Custom | WO, Job Card, Routing, Production Plan, Stock Entry | **FB optimizer (cutting)** | **Cao (thuật toán cắt)** | S4 |
| al_construction | New | Project, Task, Employee | computed (cost), Estimate vs Actual | **Cao (10 doctype + workflow)** | S5 |
| al_account | Custom | Cost Center, Accounting Dimension, Budget, Project Profitability | rollup P&L | Trung bình (mapping + snapshot) | S6 |
| al_quality | Custom | QI, Warranty Claim | — | Thấp | S4 |
| al_hr | (shell rỗng) | HRMS nguyên bản | — | 0 (bỏ dần) | S5 |
| al_ai_intelligence | New | Frappe API + LLM | suggestion handler | Trung bình | S7 |

---

## 12. Phát triển formula_builder — NỀN TẢNG CHUNG (track riêng)

> **Nguyên tắc (Owner 2026-08-16):** "tận dụng tối đa erpnext frappe + formula_builder **và phát triển thêm
> formula_builder để làm nền tảng chung**". Nghĩa là FB **không chỉ phục vụ alumglass** — mỗi khả năng mới
> phát triển cho alumglass phải **generic** để tái dùng cho ngành khác (thép, gỗ, cửa nhựa...).
>
> **MỞ RỘNG TẦM NHÌN (bổ sung 2026-08-16):** FB là **nền tảng tính toán formula động cho MỌI app**
> (Frappe/ERPNext hoặc bất kỳ app nào cần giá/khối lượng/cắt/chi phí theo công thức). Track FB gồm **3 lớp**:
> **① Triển khai thêm source_type** (bảng §12.3 — các nguồn dữ liệu mới, generic) · **② Bổ sung capability nền
> tảng** (F1–F20, §12.2) · **③ Governance & chuẩn tích hợp** để app khác dùng FB (đăng ký handler, version,
> compatibility — §12.4). Mọi app dùng formula dynamic đều kéo FB làm dependency, khai báo handler riêng
> qua `hooks.py fb_source_types` — logic ngành ở app, engine + source_type chung ở FB.
>
> Track chạy **xuyên suốt các sprint**, giao DEV chuyên trách FB (DEV2/DEV3 song song với DEV1 module alumglass)
> — không đụng file alumglass, test FB độc lập.

### 12.1 Hiện trạng FB (đã verify code)

**13 source_type đang có (code-verified, `data_source_registry.py`):**

| # | source_type | Dòng | Vai trò |
|---|---|---|---|
| 1 | `constant` | 303 | Hằng số |
| 2 | `linked_doctype_field` | 309 | Đọc field của doctype liên kết |
| 3 | `whole_doctype` | 408 | Toàn bộ bản ghi doctype |
| 4 | `child_table_aggregate` | 550 | Aggregate child table (sum/avg/...) + filter `row.attr` |
| 5 | `global_default` | 614 | Global default value |
| 6 | `session_variable` | 629 | Biến session/người dùng |
| 7 | `doctype_query` | 645 | Query doctype theo điều kiện |
| 8 | `custom_function` | 807 | Gọi hàm Python whitelist |
| 9 | `dynamic_link` | 842 | Nạp doc từ link field động |
| 10 | `computed` | 863 | Công thức tính giữa các biến |
| 11 | `pipeline` | 906 | Nhiều bước nối tiếp |
| 12 | `conditional` | 1008 | Rẽ nhánh điều kiện |
| 13 | `fallback_chain` | 1124 | Chuỗi fallback |

Ngoài ra: `@register_source` (`source_type_registry.py:489`), `get_live_context(scope_context_json)`
(`api/formula_builder.py:274`), `BatchBindingResolver` (`batch_binding_resolver.py:229`), `MultiTableFormulaBuilder`
(`table_formula_builder.py:115`), `FlexibleFormulaEngine` v2 (`flexible_formula_engine.py`), Snapshot (immutable,
hash SHA-256 **+871–1014% chậm** — chỉ dùng ở milestone), Global Variable, `DotToSubscriptTransformer`
(`parser.py:18`). Hiệu năng 2.0–2.5M formula-node/s.

- ⚠ `formula_builder` **chưa cài site nào** (apps.txt không có) — Sprint 1 Phase A sẽ cài trên dev site.
- ⚠⚠ **Bảo mật FB đang LỎNG:** FB dùng `eval()` ở `engine_public.py:452` + `data_source_registry.py:584/1075`
  với pattern `{"__builtins__": {}}` — **đã chứng minh RCE qua object traversal** (xem §4 R-FB). Đây là lý do F1
  (safe-eval trong FB) là **Blocker Sprint 1**, không phải "tương lai".
- ✅ **Có sẵn để kế thừa:** `SecurityValidator`/`FormulaValidator` (`formula_utils/security.py` — AST sandbox,
  max_depth/max_iter_size) + `tests/test_security.py`; benchmark baseline `PERFORMANCE_REPORT_v31.md`
  (~2.0–2.5M node/s) + `example/benchmark_v31_comprehensive.py`. F1 phải tận dụng (không xây mới trùng),
  giữ flexibility 80+ hàm BASE_FUNCS/`row.attr`/conditional + **perf ≥90% baseline** (ràng buộc §5 A3).
- **Contract đăng ký source_type:** built-in 13 register trực tiếp trong `data_source_registry.py` qua `@register_source`;
  app ngoài khai `fb_source_types` trong hooks.py → registry auto-discover (import module → `@register_source` trigger).
  Source_type mới phải có `config_schema` (validate JSON) + `fingerprint_fn` (batch cache) + `batchable` nếu batch.

### 12.2 Các khả năng cần phát triển cho FB (ưu tiên theo sprint)

| # | Khả năng FB | Dùng cho | Sprint | Mức |
|---|---|---|---|---|
| **F1** | **Safe formula evaluation** — AST interpreter trong FB (`formula_builder/security/safe_eval.py`), whitelist node + chặn dunder/literal-traversal; sửa 3 eval FB (`engine_public.py:452`, `data_source_registry.py:584/1075`); alumglass import FB (bỏ bản local). Generic cho mọi ngành | S1 (security) | **Blocker — ĐANG LÀM (Owner chốt 2026-08-16)** |
| **F2** | **Composite-key lookup source** — tổng quát hoá `aluminum_price_composite`: source type nhận `key_fields` (dimension) + `match_mode` (exact/multiplier/fallback) bất kỳ, không hardcode ngành | S1–S2 | Cao |
| **F3** | **Versioned/snapshot config** — tổng quát hoá AL BOM Version (immutable snapshot + fingerprint) thành capability FB cho *bất kỳ* config nào (pricing dimension, rule, template) | S1–S2 | Trung bình |
| **F4** | **Async engine execution** — enqueue formula evaluation lên worker + `publish_realtime` completion; thay thế P2 async BOM bằng FB native | S2 | Trung bình |
| **F5** | **`MultiTableFormulaBuilder.from_frappe_doc`** — sinh formula + context từ child table (Bom Set) 1 lần, bỏ build formula thủ công | S1 | Trung bình |
| **F6** | **Optimizer/solver source type** — pluggable algorithm (1D FFD / 2D Guillotine / allocation) như source type; đầu vào/ra có schema | S4 (cutting) | **Cao** |
| **F7** | **UOM-aware arithmetic** — formula biết đơn vị (m, m², kg, cây), auto conversion (nối core `UOM Conversion Factor`) | S2–S3 | Trung bình |
| **F8** | **Audit trail / eval log** — log từng formula node tính + version config dùng; hỗ trợ P&L, truy vết | S3 | Trung bình |
| **F9** | **Report aggregation source** — rollup cost theo bucket/dimension cho report (kế thừa B5) | S3–S6 | Trung bình |
| **F10** | **Snapshot performance** — xử lý chậm +871–1014% (caching, incremental hash) | khi dùng milestone | Thấp |
| **F11** | **Formula debugger/playground UI** — gõ thử công thức, xem dependency graph, test kết quả tức thì (form builder UI chung) | mọi app | Trung bình |
| **F12** | **Formula versioning + registry dùng chung** — lưu/so sánh/reuse công thức qua các app (F3 đẩy mạnh thành thư viện chung) | mọi app | Trung bình |
| **F13** | **Import/Export công thức** (Excel/JSON) giữa môi trường dev/prod, giữa app | mọi app | Trung bình |
| **F14** | **Dependency graph visualization** — UI vẽ DAG biến, chỉ ra biến thiếu/loop | mọi app | Thấp |
| **F15** | **RBAC cho config công thức** — role riêng "Formula Admin", ai được tạo/sửa công thức/binding (ngăn nhập liệu bậy) | mọi app | Trung bình |
| **F16** | **Formula test harness** — chạy unit test cho công thức (golden case, regression) qua UI/CLI | mọi app | Trung bình |
| **F17** | **Public API/CLI invoke** — gọi tính formula từ ngoài (API whitelist, script) ổn định | mọi app | Trung bình |
| **F18** | **Multi-company/tenant scope** — binding áp dụng theo company/warehouse/project, không global | mọi app | Trung bình |
| **F19** | **Currency + UOM conversion nâng cao** — auto chuyển tiền tệ (core Currency Exchange), đơn vị (F7) tích hợp ngay trong công thức | mọi app | Trung bình |
| **F20** | **Version contract + migration** — FB versioning rõ, tool upgrade app dùng FB (compatibility matrix) | nền tảng | Cao |

### 12.3 Source_type mới cần triển khai vào FB (mở rộng vượt 13 hiện có)

> **Owner 2026-08-16:** "triển khai thêm source_type vào FB". Các source_type mới phải **generic** (không hardcode
> ngành), có `config_schema` + `fingerprint_fn` + `batchable` (đúng chuẩn registry). Khi cần nguồn dữ liệu đặc thù
> một app → app tự viết handler (vd alumglass `aluminum_price_composite`) — KHÔNG nhét vào FB trừ khi tái dùng nhiều app.

| # | source_type mới (đề xuất) | Mục đích | Dùng cho (use case chung) | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|
| **S1** | `formula_chain` / `reuse_formula_result` | Gọi **kết quả** của formula/BOM/cấu hình khác (tính chuyền đa tầng, chi phí lũy kế) | alumglass B5/B6 (cost từ các dòng), thép/gỗ (chi phí nhiều tầng) | F3 versioning | Cao |
| **S2** | `matrix_lookup` | Tra bảng **2 chiều** (giá theo (size × qty), (độ dày × màu)) | pricing matrix mọi ngành | — | Cao |
| **S3** | `imported_reference_table` | Đọc bảng tham chiếu từ **file Excel/CSV upload** (bảng giá import, hệ số vận chuyển) | mọi app nhập bảng giá/định mức ngoài | — | Trung bình |
| **S4** | `http_external_source` | Fetch dữ liệu từ **API ngoài** (tỷ giá, giá thị trường, thời tiết) | mọi app | cache + timeout | Trung bình |
| **S5** | `currency_conversion` | Chuyển đổi tiền tệ trong công thức (nối core `Currency Exchange`) | mọi app bán/nhập ngoại tệ | F19 | Trung bình |
| **S6** | `optimizer_solver` | Gọi **thuật toán** (1D FFD / 2D Guillotine / allocation) như source type, schema đầu vào/ra chuẩn | alumglass cắt S4, thép (cắt thanh), gỗ (cắt tấm) | — | **Cao** |
| **S7** | `iteration` / `sequence` | Vòng lặp hữu hạn trong formula (sinh N dòng theo điều kiện) | lập giá dây chuyền, nhiều tầng | — | Trung bình |
| **S8** | `request_context` | Đọc từ request: user, role, branch, vùng (mở rộng `session_variable`) | giá theo khu vực/chi nhánh/đối tượng | — | Trung bình |
| **S9** | `scheduler_time_series` | Dữ liệu theo thời gian (lịch sử giá, dự báo, tỷ giá biến động) | pricing động theo thời gian | — | Thấp |
| **S10** | `approval_workflow_trigger` | Kết quả formula trigger **workflow/alert** (vd giá > ngưỡng → duyệt) | mọi app cần cảnh báo từ công thức | core Workflow | Thấp |
| **S11** | `llm_suggestion` | LLM sinh/đánh giá giá trị (AI hỗ trợ) | alumglass AI S7, pricing AI | F7 AI | Thấp |

> **Nguyên tắc khi thêm source_type:** mỗi cái phải có design doc `formula_builder/docs/`, ví dụ dùng đa ngành,
> test riêng FB, và giữ đúng contract `@register_source` + batchable + fingerprint (không phá `BatchBindingResolver`).

### 12.4 FB làm nền tảng cho MỌI app tính toán formula động — governance & tích hợp

**Mô hình:** FB = engine + source_type chung + capability nền tảng (F1–F20). App = khai báo `required_apps=["formula_builder"]`
+ handler riêng qua `hooks.py fb_source_types` (`@register_source`) + config ở DB. Logic ngành KHÔNG vào FB.

| Khía cạnh | Quy ước |
|---|---|
| **Đăng ký nguồn dữ liệu** | App viết `fb_handlers.py` + `@register_source` + khai `fb_source_types` trong hooks → registry FB tự discover (`source_type_registry.py:396`). |
| **Gọi engine** | App dùng `get_live_context(scope_context_json)` + `resolve_bindings_with_deps` / `BatchBindingResolver`; `FormulaEngine`/`FlexibleFormulaEngine` cho DAG/sequence. |
| **Tách trách nhiệm** | `custom_function`/`computed`/`pipeline` = engine. `fb_handlers` = nguồn dữ liệu ngành. Config DB = nghiệp vụ. |
| **Versioning & compatibility** | FB giữ contract ổn định (`@register_source` signature, `get_live_context`, on_error set). Thêm source_type/capability mới **không phá** cái cũ (backward-compatible). Có `F20` version matrix + tool upgrade. |
| **Bảo mật chuẩn** | Mọi eval qua safe evaluator FB (F1 — đang làm). RBAC config formula (F15). Không import builtin nguy hiểm. |
| **Hiệu năng chuẩn** | Benchmark mỗi release ≥90% baseline 2M node/s (PERFORMANCE_REPORT). BatchBindingResolver giữ -90% query. |
| **Test chuẩn** | Mỗi release FB: full test suite (`tests/`) + benchmark. Mỗi app dùng FB có test riêng (golden case) — không phụ thuộc nhau. |
| **Docs chuẩn** | Design doc + ví dụ + API reference trong `formula_builder/docs/`; app docs ở `docs/design|usage` riêng. |
| **Roadmap ưu tiên FB** | Sprint 1: F1 (security, blocker) + F2 (composite generic). S1–S2: F3/F5/F7/F19. S4: F6/S6 (cắt). Xuyên suốt: S1–S3 (source type mới) + F11–F20. |

### 12.5 Ghi chú triển khai track FB

- **Kiến trúc FB vẫn là BẤT BIẾN với business logic** — phát triển thêm capability chung, không nhét logic
  ngành vào FB. Logic ngành (quy tắc cắt, giá nhôm) ở handler/`fb_handlers` alumglass.
- Mỗi F1–F20 + S1–S11 kèm: design doc `formula_builder/docs/`, ví dụ dùng, test riêng của FB (không phụ thuộc alumglass).

### 12.6 Hợp nhất AL Cost Bucket ↔ Formula Variable Binding (Owner duyệt 2026-08-16)

> Phương án chi tiết: `working/jobs/2026-08-16_alumglass-sprint1-quotation/06_phuong-an-hop-nhat-fb.md`.

**Vấn đề (verified code):** FB và AL Cost Bucket đều có `source_type` + `source_config` nhưng là **2 vocabulary song song** (FB registry 13 vs AL vocab 8) và **engine alumglass B3–B6 không resolve qua binding nào** — B5 gom chi phí = sum Python thuần (`bom_orchestrator.py:588`), `source_type`/`source_config`/`depends_on` của Cost Bucket **dormant**.

**Mục tiêu:** AL Cost Bucket = **thin wrapper** trên Formula Variable Binding (map 1:1 sang registry FB, bỏ vocab 8); B5 aggregation qua FB; FB nâng matrix N-chiều + hàm agg làm nền tảng chung.

**Nâng FB (FB-1 REVISED, DEV2 — đang làm):**
- `composite_key_lookup` (F2) — matrix N-chiều: `key_fields` động + `fallback_keys` (rút dần chiều) + `match_mode` exact/case_insensitive/**multiplier_chain** (Owner chốt multiplier_chain VÀO FB); `matrix_lookup` 2 trục = special case.
- **`aggregate_from_items` source_type mới** — thay py thuần dict sum của AL Cost Bucket (`fb_handlers.py:141`): sum theo `key_field`/`key_value` giống `sumif` (FB đã có sumif/group_sum/filter_array làm hàm), đọc snapshot/child_table/doctype, batchable+fingerprint, tăng performance.
- **BỎ** RowCollection + agg_collection (SUM/AVG/COUNT/FILTER UPPERCASE) — **dư thừa**, FB đã có hàm agg trên list dict (`sumif`, `group_sum`, `filter_array`, `first/last`...). Engine = truyền `formulas` + `context` (caller tự xây).

**Alumglass tận dụng (sau FB-1):**
- **AL-1:** Cost Bucket map 1:1 registry FB (aggregate_from_items → child_table_rows + `SUM(line_total)`), B5 = formula `SUM(FILTER(rows, row.cost_bucket==bk).line_total)` hoặc `aggregate`; migration `source_config` cũ; golden re-test.
- **AL-2:** `aluminum_price_composite` → `composite_key_lookup`; B3/B4 resolve qua `get_live_context` + `BatchBindingResolver`.
- **Gate mọi pha:** golden case **22,717,289** pass + FB benchmark ≥90% baseline.

**Ràng buộc:** backward-compat (13 source_type cũ + matrix_lookup + reuse_formula_result giữ nguyên); security/performance chuẩn; KHÔNG refactor B3–B6 giữa Sprint 1.
- **Không phá contract hiện có:** FB đang được alumglass (S1) dùng ở B4/B6 — mọi thay đổi phải giữ
  backward compatible + test FB pass trước khi alumglass nâng cấp.
- **Track FB giao DEV chuyên trách riêng** (ví dụ DEV2) — tránh conflict file với DEV1 (alumglass engine);
  nếu cùng DEV thì tách commit/répo, test FB độc lập.
- Chi phí: F1–F5 (S1–S2) ước lượng ~2–3 tuần DEV FB; F6/S6 cắt tách riêng theo thuật toán; S1–S3 (source type mới) theo khả năng tái dùng.

---

## Phụ lục — Bản đồ file chính (để DEV tra cứu)

| File | Vai trò | Dòng quan trọng |
|---|---|---|
| `alumglass/engine/bom_orchestrator.py` | Engine 7-phase | B1 (93), B2 (206), B3 (479), B4 (537), B5 (588), B6 (600), B7 (653); resolver tự viết (123, 373, 403); regex (510); on_error (559, 640) |
| `alumglass/fb_handlers.py` | 3 custom source type (chưa register) | 10 / 121 / 141 |
| `alumglass/hooks.py` | `fb_source_types`, `required_apps`, `whitelisted_methods` (7), `doc_events` | 13, 57–61 |
| `alumglass/api/__init__.py` | 8 `@frappe.whitelist()`, `get_formula_context` | 4–264; 75 |
| `alumglass/alumglass/run_test.py` | Test thủ công (SQL) — baseline | main() / expected=22717289 |
| `al_bom_engine/doctype/al_cost_bucket/al_cost_bucket.py` | Cost Bucket vocab + validate | 12–16, 18–57 |
| `al_bom_engine/doctype/al_cost_template/al_cost_template.py` | **eval() RCE #2** (→ import FB safe_eval) | **42** |
| `alumglass/security/safe_eval.py` | ⚠ **BỎ BẢN LOCAL** — chuyển vào formula_builder (Owner chốt) | — |
| `al_bom_engine/doctype/al_bom_version/al_bom_version.py` | Snapshot + immutability | 22, 45 |
| `al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py` | **eval() RCE #1** | **36** |
| `al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.py` | Pricing dimension → custom field | — |
| `setup/custom_fields.py` | Custom fields trên core doctypes | toàn bộ |
| `setup/seed_demo_data.py` | Seed A-Z (CDMQ-2C/4C) | 55–61 (_cost_buckets) |
| `public/js/formula_setup.js`, `bom_dialog.js`, `quotation_item_dialog.js` | FB JS + dialog tính giá | — |
| **formula_builder** | | |
| `api/source_type_registry.py` | Registry + `@register_source` | 489 (signature), 396 (discover) |
| `api/data_source_registry.py` | 13 source types + `resolve_bindings_with_deps` | 303–1223, 1282 |
| `api/batch_binding_resolver.py` | `BatchBindingResolver` + `resolve_all_bindings_batch` | 229, 256, 508 |
| `api/formula_builder.py` | `get_live_context(scope_context_json)` | 274 |
| `table_formula_builder.py` | `MultiTableFormulaBuilder` | 115 |
| `formula_utils/parser.py` | `DotToSubscriptTransformer` | 18 |
| `formula_utils/engine_core.py` | `on_error` valid set + FormulaEngine + `_eval_globals` | 200, 241–248, 637 |
| `formula_utils/engine_public.py` | **eval() RCE #3 (FormulaEngine)** | **452** |
| `api/data_source_registry.py` | **eval() RCE #4/#5 (filter/condition)** | **584, 1075** |
| `security/safe_eval.py` 🆕 | Safe evaluator FB (F1 — đang làm) | — |
| `formula_utils/errors.py` | div-by-zero ALWAYS fatal | 131 |
| `flexible_formula_engine.py` | FlexibleFormulaEngine v2 | 173–226 (on_error), 279 (errors dict) |
