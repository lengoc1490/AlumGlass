# al_review.md — Đánh giá toàn diện AlumGlass & lộ trình "core-first + Formula Builder tối đa"

> **Bản chất tài liệu:** Review toàn bộ code + ~50 tài liệu `.md` của app `alumglass`
> (đọc trực tiếp tại `/home/nxc/myfrappe/apps/alumglass`), đối chiếu với khả năng của
> **ERPNext 14 / Frappe 14 / HRMS 14** và **formula_builder v31**.
>
> **Mục tiêu:** đề xuất giải pháp **tận dụng tối đa core ERPNext/Frappe/HRMS và sức mạnh
> formula_builder**, giảm tối đa code tự build lại (re-invent the wheel), kèm các điều chỉnh
> cần thiết để chạy được.
>
> **Ngày soạn:** 2026-08-14 · **Tác giả:** Elon (AI Coordinator) — dựa trên code ground-truth + tổng hợp docs.

**Ký hiệu nguồn thông tin (dùng xuyên tài liệu — phân biệt fact code vs kế hoạch docs):**
- ✅ **code** — phát hiện từ đọc code thực tế, đã verify (kèm `file:line`)
- 📄 **docs** — ghi nhận từ tài liệu `.md` (kế hoạch v28.9/v28.10, review...) — *chưa chắc đã triển khai trong code, cần kiểm tra lại trước khi khẳng định*
- ⚠ **cần xác nhận** — đề xuất/chuyển đổi rủi ro, cần BA/Owner chốt nghiệp vụ trước khi làm

---

## ✅ Kiến trúc đã chốt (Owner) — nền tảng của mọi đề xuất trong tài liệu này

> **KHÔNG dùng Item Variant** — làm bùng nổ data (nguyên tắc v28.md #16). AlumGlass quản lý
> **theo từng Project**: mỗi project có spec riêng (nhôm, màu, phụ kiện, kính) và kích thước
> sản phẩm riêng. Item = "mã nhôm đại diện" + thông số ghi ở nghiệp vụ (transaction attribute).
>
> - **Kho:** **Inventory Dimension** (core ERPNext) — nhôm: Màu; kính: Loại × Độ dày × Màu;
>   balance + valuation theo dimension. Cơ chế độc lập với giá.
> - **Giá:** **AL Pricing Dimension** — mô phỏng **Accounting Dimension** (đã triển khai trên
>   Item Price): auto-tạo `custom_pd_{dimension_code}`, composite key tra giá trong dialog
>   Quotation; chỉ cho **báo giá / tham chiếu giá**, KHÔNG cho kho. (Owner đã chốt composite
>   key giữ nguyên — v28.md:6786.)
> - **Tận dụng tối đa:** toàn bộ formula_builder (13 source_type, BatchBindingResolver,
>   SourceTypeRegistry, transform layer) + core ERPNext/Frappe/HRMS.
>
> (Nguồn: v28.md #16 + §B.5A + dòng 6786; TONG_QUAN_KIEN_TRUC.md dòng 538 "Owner làm rõ
> 2026-08-13 — phân tách AL Pricing Dimension (giá) vs Inventory Dimension (kho)";
> ARCHITECTURE-REVIEW **E9 Item Variant cho profile đã bị loại** bởi quyết định này.)

---

## 📄 TÓM TẮT 1 TRANG — DÀNH CHO OWNER

**AlumGlass đang đi đúng hướng (config-driven, engine BOM 7-phase chạy thật, có test "số vàng" GIA_VAT ≈ 22.717.289đ cho CDMQ-2C, snapshot bất biến).** Vấn đề không phải thiếu, mà là **"có nhưng chưa nối"**: core ERPNext/HRMS và formula_builder đều đã cài sẵn (máy dev có erpnext 14.92 + hrms 14.38), nhưng **toàn app không có 1 dòng `from erpnext import ...`** và **13 source_type của Formula Variable Binding chưa từng được gọi**.

**4 việc ưu tiên (cao → thấp):**

| # | Việc | Lợi ích trực tiếp |
|---|---|---|
| 1 | **Nối Formula Variable Binding + đăng ký 3 handler alumglass** chuẩn `@register_source`, cho B1/B2/B5 gọi qua `get_live_context`/`BatchBindingResolver` | Bỏ ~300 dòng resolver tự viết; 13 source_type FB bắt đầu chạy thật |
| 2 | **Instantiate core BOM** từ AL BOM khi version Published → nối Material Request/Production Plan | Mua/SX/Kho đi qua core ERPNext thay vì tự build lại |
| 3 | Dùng **Inventory Dimension** (kho) + **AL Pricing Dimension** (giá — chuẩn Accounting Dimension) + **Cost Center/Accounting Dimension** (P&L) thay custom field | Kho đa chiều + tra giá composite chuẩn + P&L theo bucket/dự án, không tự làm |
| 4 | **HRMS Timesheet/Expense Claim** cho nhân công lắp đặt | Chi phí NC thực tế thay vì ước lượng %/hệ số |

**Rủi ro cần xử lý song song:** `eval()` trên lambda lưu DB; monkey-patch JS `_ContextBuilder.build()`; `on_error="raise"` dễ chết cả BOM; BOM >200 dòng có thể timeout; Pricing Dimension chưa versioning.

**Kết quả mong đợi:** app thành **lớp mỏng nghiệp vụ đúng nghĩa** — cấu hình ở DB, tính toán ở formula_builder, nghiệp vụ chuẩn ở ERPNext. "Config > Code, 0 dòng code cho nghiệp vụ mới" trở thành hiện thực.

> Chi tiết: §4 giải pháp · §6 ưu tiên P0/P1/P2 · §7 lộ trình + Definition of Done.

---

## 0. Tóm tắt điều hành (Executive Summary)

AlumGlass là app **config-driven đúng hướng**: engine BOM 7 phase đã chạy thật, có test "số vàng"
(`GIA_VAT ≈ 22.717.289đ` cho CDMQ-2C), batching query chống N+1, snapshot bất biến. Điểm mạnh cốt lõi:
**cấu hình nghiệp vụ nằm ở DB (AL Variable Library, AL Bom Set, AL Cost Template), không hardcode.**

Tuy nhiên, đối chiếu với mục tiêu "tận dụng tối đa core + formula_builder", có **4 khoảng trống lớn**:

| # | Khoảng trống | Bằng chứng trong code | Tác động |
|---|---|---|---|
| **G1** | **0 dòng `from erpnext import ...`** trong toàn app | `grep -rn "from erpnext" alumglass/` → rỗng | Toàn bộ nghiệp vụ kế toán/kho/SX/HR tự xử lý thay vì dùng core |
| **G2** | **Formula Variable Binding (FVB) chưa được nối vào engine** | `get_live_context`/`resolve_bindings`/`BatchBindingResolver` → 0 lần gọi trong code alumglass | 13 source_type của FB đang chết lặng; B1 tự viết resolver riêng |
| **G3** | **AL Cost Bucket.source_type chưa được resolve** | `BomOrchestrator.b5_aggregate_cost_buckets` (bom_orchestrator.py:588) gom bằng Python loop, không đọc `source_type/source_config` | Trường declarative "aggregate_from_items"/"formula" chỉ được validate, không được tính |
| **G4** | **3 custom fb_handlers chưa `@register_source`** | `alumglass/fb_handlers.py` — 3 hàm plain, không decorator; hooks.py:57-61 chỉ khai báo đường dẫn | Không có metadata/schema/batchable trong `SourceTypeRegistry`; không xuất hiện trong `list_source_types` |

Ngoài ra còn **~15 điểm tái phát minh (reinvent)** liệt kê ở §3 và **3 rủi ro kỹ thuật** (§5):
`eval()` trên lambda lưu DB (`al_quantity_calc_method.py`), monkey-patch JS `_ContextBuilder.build()`,
và `on_error="raise"` thiếu khả năng phục hồi khi BOM lỗi.

**Lộ trình đề xuất gói gọn trong 3 nhóm:** (1) **FB-max** — nối FVB + BatchBindingResolver + registry
vào engine, thay regex bằng FB transformer, dùng MultiTableFormulaBuilder; (2) **ERPNext-core** — core BOM
instantiate từ AL BOM, MRP/Material Request, Inventory Dimension, Cost Center + Accounting Dimension,
Work Order/Job Card, giá theo **AL Pricing Dimension** (không Item Variant — v28.9 #16); (3) **HRMS** —
Timesheet/Expense Claim cho nhân công lắp đặt.
Chi tiết §6, ưu tiên hóa §7, lộ trình §8.

---

## 1. Hiện trạng kiến trúc (ground-truth từ code)

### 1.1 Cấu trúc app

- **12 module nghiệp vụ** (`al_master_data`, `al_bom_engine`, `al_formula_rules`, `al_manufacturing`,
  `al_stock`, `al_selling`, `al_buying`, `al_account`, `al_quality`, `al_construction`, `al_hr`, `al_ai_intelligence`)
- **~53 DocType JSON**, **62 thư mục doctype**, ~171 file Python (~5.200 dòng), ~51 file JS (~4.170 dòng),
  5 test, 7 API whitelisted (`alumglass/api/__init__.py`).
- `required_apps = ["formula_builder"]` (hooks.py:13) — đúng chuẩn.
- **Không có dependency ERPNext/HRMS** trong `required_apps` và **không import erpnext ở đâu cả**.

### 1.2 Luồng tính giá BOM (BomOrchestrator 7-phase) — `alumglass/engine/bom_orchestrator.py`

```
B0  Version pinning       → b0_version_pinning() (71)   dùng AL BOM Version snapshot (immutable)
B1  Gather inputs         → b1_gather_inputs() (93)     al_bom_vars JSON + Formula Global Variable
                            + _resolve_system_variables() (123)  ← TỰ resolver từ AL Variable Library
B2  Pre-fetch master data → b2_prefetch_master_data() (206)
                            + _fetch_composite_prices() (373)  ← TỰ query Item Price theo composite key
                            + _match_composite_price() (403)   ← TỰ chọn dòng khớp nhất
B3  Build formulas        → b3_build_formulas() (479)   TỰ build list {name, formula} + regex thay items.X.Y→X__Y
B4  Tính Bom Items        → b4_calculate_bom_items() (537)  FormulaEngine (FB) — DAG + topo sort ✅
B5  Gom Cost Buckets      → b5_aggregate_cost_buckets() (588)  Python loop buckets[bk] += line_total
B6  Tính Cost Template    → b6_calculate_cost_template() (600)  FlexibleFormulaEngine (FB) ✅
B7  Save                  → b7_save_results() (653)     ConfigSnapshot + ghi Quotation Item (1 commit)
```

**Kết luận:** FB được dùng đúng ở **B4 và B6** (2 engine DAG mạnh nhất). Nhưng **B1, B2, B3, B5** là code
tự viết thay thế đúng những thứ FB đã cung cấp sẵn (xem §4).

### 1.3 Các hệ thống "source_type" đang tồn tại SONG SONG

| Hệ thống | Nơi định nghĩa | Nơi resolve | Trạng thái |
|---|---|---|---|
| **Formula Variable Binding** (13 loại) | `formula_builder/api/data_source_registry.py` (handlers 303–1223) | `get_live_context` (formula_builder.py:273) → `resolve_bindings_with_deps` (1282) / `BatchBindingResolver` (batch_binding_resolver.py:256) | **Chưa được nối** vào luồng BOM alumglass (0 lần gọi) |
| **AL Cost Bucket** (8 loại) | `al_cost_bucket.py` `VALID_SOURCE_TYPES` (12–16) + `validate()` (18–57) | — (không có resolver) | **Validate có, resolve không** — B5 gom bằng loop |
| **AL Variable Library** (is_system + user) | `al_master_data/doctype/al_variable_library` | `_resolve_system_variables()` (bom_orchestrator.py:123) | Tự viết, trùng chức năng `session_variable`/`global_default`/`computed` của FB |
| **AL Variable Set** | `al_master_data/doctype/al_variable_set` | JS dialog (`get_variable_set_for_bom`) | Tự viết — tương đương `applies_to_doctype` scope của FVB |
| **Composite key pricing** | `al_master_data/doctype/al_pricing_dimension` + `al_variable_dimension_mapping` | `_fetch_composite_prices`/`_match_composite_price` (B2) | **Trùng logic** `fb_handlers.aluminum_price_composite` (chính comment bom_orchestrator.py:349 nói vậy) |

---

## 2. Bằng chứng chi tiết cho 4 khoảng trống (G1–G4)

### G1 — Zero ERPNext import

```
$ grep -rn "from erpnext" --include="*.py" alumglass/   →  (rỗng)
$ grep -rn "from hrms"   --include="*.py" alumglass/   →  (rỗng)
```

Toàn bộ app chỉ dùng `frappe` + `formula_builder`. Hệ quả:
- **Kho:** AL Material Plan (al_buying) tự build kế hoạch vật tư → trong khi ERPNext đã có
  `Material Request`, `Production Plan`, `Subcontracting`, MRP.
- **Sản xuất:** AL Production Order Bridge + custom fields trên Work Order → chưa dùng core BOM/Job Card/Routing.
- **Nhân công:** NC_LD (nhân công lắp đặt) tính bằng %/hệ số → trong khi HRMS có `Timesheet`, `Expense Claim`,
  `Payroll` để tính chi phí nhân công thực.
- **Kế toán:** AL Cost Bucket + Journal Entry custom field → trong khi core có `Cost Center`, `Accounting Dimension`,
  `Project Profitability`.

### G2 — Formula Variable Binding không được nối

- `grep -rn "get_live_context\|resolve_bindings\|BatchBindingResolver" alumglass/` → **0 kết quả ngoài comment**
  trong `fb_handlers.py:4` ("Mọi thứ ủy thác cho FB BatchBindingResolver..." — nhưng không có code nào gọi).
- `get_formula_context()` (api/__init__.py:75) chỉ **liệt kê FVB làm autocomplete** (nhóm 7, dòng 185–198),
  không resolve giá trị.
- B1 `_resolve_system_variables()` (bom_orchestrator.py:123) tự query `AL Variable Library` + `AL Profile System` +
  `AL Product Type` bằng get_cached_doc — đúng thứ mà FB `session_variable` / `linked_doctype_field` /
  `global_default` / `computed` đã giải quyết, kèm topological ordering và batch resolution.

### G3 — AL Cost Bucket.source_type không được resolve

- `VALID_SOURCE_TYPES = ["aggregate_from_items","formula","doctype_query","custom_function","constant","pipeline","conditional","fallback_chain"]` (al_cost_bucket.py:12–16) — **vocabulary riêng, khác 13 loại của FVB**.
- `seed_demo_data.py:_cost_buckets()` (55–61) seed `VL_*` với `source_type="aggregate_from_items"`, số còn lại `"formula"` —
  nghĩa là **data demo giả định engine sẽ đọc source_type, nhưng không engine nào đọc**.
- `BomOrchestrator.b5_aggregate_cost_buckets()` (588–595): `for row in bom_result: buckets[bk] += row["line_total"]`
  — chỉ gom theo chuỗi `cost_bucket`, **bỏ qua hoàn toàn** `source_config`, `depends_on`, `parent_bucket`, `bucket_role`.
- `fb_handlers.cost_bucket_aggregate()` (fb_handlers.py:141) có docstring "Dùng cho Cost Bucket có
  source_type = 'aggregate_from_items'" nhưng **không được gọi ở bất kỳ đâu**.
- `tests/test_composite_pricing.py` (AlumGlass_Review_Patches/tests) đã có **bug-demo test** ghi nhận đúng tình trạng
  "handler tồn tại nhưng không được gọi trong luồng tính BOM thật".

### G4 — fb_handlers chưa `@register_source`

- `hooks.py:57-61` khai báo `fb_source_types = ["alumglass.fb_handlers.aluminum_price_composite", ...]`.
- Cơ chế FB yêu cầu: `_discover_from_hooks()` (source_type_registry.py:396) import module và **module phải gọi
  `@register_source()` tại import** để tạo `SourceTypeDefinition` (label, config_schema, app, batchable, fingerprint_fn...).
- README FB §9.7 cho ví dụ chuẩn: handler phải có decorator kèm `config_schema`, `fingerprint_fn`, `batchable`.
- 3 hàm alumglass **không có decorator** → import xong registry không biết chúng là gì:
  không list được trong `list_source_types`, không sinh form config, không batch theo fingerprint, không transform.
  `get_registry_stats` sẽ không đếm chúng.

---

## 3. Danh sách "re-invent the wheel" (đối chiếu core + FB)

> **Nguồn:** §3.1 = ✅ **code-verified** — mọi item đã kiểm chứng FB có sẵn `file:line` trong
> formula_builder. §3.2–3.4 = 📄 **kế hoạch/docs** — khả năng core ERPNext/HRMS có sẵn là ghi nhận
> từ tài liệu + kiến thức core, **chưa chắc đã triển khai, cần DEV xác minh trên bản erpnext 14.92
> hiện có trước khi làm**. Các mục ⚠ cần BA/Owner chốt nghiệp vụ trước khi chuyển.

Bảng dưới liệt kê từng thứ alumglass tự build và thứ core/FB đã có sẵn. Đây là **danh sách động** —
ưu tiên chọn làm theo mức tác động ở §7.

### 3.1 Nên thay bằng formula_builder (đã có sẵn, 0 dòng mới)

| AlumGlass tự làm | File | Thay bằng FB | File FB |
|---|---|---|---|
| Regex `items.X.Y → X__Y` (B3) | bom_orchestrator.py:510 | `DotToSubscriptTransformer` | `formula_builder/formula_utils/parser.py:18` |
| Build formula list thủ công từ Bom Set (B3) | bom_orchestrator.py:479 | `MultiTableFormulaBuilder` (`add_table`, `normalize_global/scoped`, `build`) | `formula_builder/table_formula_builder.py` |
| Resolve system vars thủ công (B1) | bom_orchestrator.py:123 | `get_live_context` + `resolve_bindings_with_deps` / `BatchBindingResolver` | `api/formula_builder.py:273`, `api/data_source_registry.py:1282`, `api/batch_binding_resolver.py:256` |
| Query Item Price composite-key thủ công (B2) | bom_orchestrator.py:373–437 | `aluminum_price_composite` **sau khi** `@register_source` + `BatchBindingResolver` (đã batchable/fingerprint) | `alumglass/fb_handlers.py` (sửa) |
| Gom cost bucket bằng loop (B5) | bom_orchestrator.py:588 | Source type `cost_bucket_aggregate` (register chuẩn) hoặc FVB `computed`/`child_table_aggregate` | `fb_handlers.py` (sửa) |
| `eval()` lambda lưu DB (calc_fn) | `al_quantity_calc_method.py:23` | `custom_function` source type (whitelist hàm) + `FormulaEngine` safe_funcs | `data_source_registry.py:807` |
| `lookup_rule`/THRESHOLD/LOOKUP rule | `al_calculation_rule.py`, `al_dynamic_item_rule.py` | FB `conditional` + `fallback_chain` + custom_function (hoặc giữ nếu quá ngành) | `data_source_registry.py:1008/1124/807` |
| Context vars cho JS autocomplete | `api/__init__.py:get_formula_context` | `get_live_context` (FB) — 1 nguồn chân lý | `api/formula_builder.py:273` |
| `on_error="raise"` dễ chết cả BOM | bom_orchestrator.py:558,641 | `on_error="continue"` + `default_value` + structured errors | `formula_builder/formula_utils/engine_core.py` |

### 3.2 Nên thay bằng ERPNext core (giảm code + có nghiệp vụ chuẩn)

| AlumGlass tự làm | Module | Thay bằng core ERPNext |
|---|---|---|
| `AL BOM` / `AL Bom Set` / `AL Bom Item` (cấu trúc sản phẩm) | al_bom_engine | **Core `BOM` + `BOM Item`** — instantiate từ AL BOM (kế hoạch v28.9) để nối MRP/Work Order; AL BOM giữ làm "mô hình báo giá" |
| `AL Material Plan` + bridge PO | al_buying | `Material Request`, `Production Plan`, `Subcontracting`, `Purchase Order` core |
| Composite pricing qua custom field Item Price | al_selling | **`AL Pricing Dimension`** (chuẩn Accounting Dimension — auto tạo `custom_pd_*` trên Item Price, composite key, v28.9 Owner đã chốt) + core `Price List`/`Pricing Rule` |
| `AL Dynamic Item Rule` (chọn nẹp/keo theo độ dày/loại kính) | al_formula_rules | Core `BOM` alternative items; hoặc giữ như rule ngành |
| `AL Cost Bucket` + JE custom field | al_bom_engine/al_account | **`Cost Center` + `Accounting Dimension`** cho P&L theo bucket (điểm E12 — đã có thiết kế, cần code) |
| Inventory Dimension (kho đa chiều màu/loại/dày) | al_stock | **Core `Inventory Dimension`** (v14.92 hỗ trợ, 3 record config) — kế hoạch v28.9 đã chọn |
| `Batch`/`Serial No` traceability (al_color, al_trace_stage...) | al_stock | Core Batch/Serial + custom fields mỏng |
| `AL Cutting Plan` (nhôm 1D/kinh 2D) | al_manufacturing | Core `Work Order` + `Job Card` + `Operation/Routing` (giữ thuật toán FFD/Guillotine làm addon) |
| `AL Project Warehouse Map` | al_stock | Core `Warehouse` + `Project` + per-project warehouse |

### 3.3 Nên thay bằng HRMS (nhân công thi công)

| AlumGlass tự làm | File | Thay bằng HRMS |
|---|---|---|
| NC_LD (nhân công lắp đặt) = %/hệ số theo installation_height | bom_orchestrator.py:600-648 (B6, qua `RULE-HEIGHT-MULT`) | **`Timesheet` + `Expense Claim`** gắn `Project`/`Task` — chi phí nhân công thực, không ước lượng |
| AL Installation Team/Task (nhóm lắp đặt) | al_construction | Core `Employee` + `Project Task` + HRMS `Attendance` |

### 3.4 Nên thay bằng Frappe core (tầng ứng dụng)

| AlumGlass tự làm | Thay bằng Frappe core |
|---|---|
| ConfigSnapshot (JSON snapshot inputs+results) | Giữ (hợp lý cho audit) — bổ sung core `Version`/Audit Trail |
| Custom role "AL Sales User / AL BOM Manager..." | Core Role + `Workflow` + `has_permission` chi tiết (đã có thiết kế 4 role trong REVIEW_production_readiness) |
| — | **Notification/Email Alert, Print Format, Report Builder, Dashboard KPI, Webhook/API, Translation, Backup** (các điểm E13–E17 chưa làm) |

### 3.5 Bảng đối chiếu DocType AL ↔ core ERPNext/HRMS (quyết định giữ/chuyển)

> 📄 Bảng này dựa trên kiến thức core + kế hoạch v28.9/v28.10. Cột "Quyết định" là **đề xuất cần
> BA/Owner chốt**; DEV phải xác minh từng tính năng trên bản erpnext 14.92 hiện có trước khi làm.

| DocType AL (hiện tại) | Core tương ứng | Quyết định đề xuất | Rủi ro / ghi chú |
|---|---|---|---|
| `AL BOM` + `AL Bom Set` + `AL Bom Item` | Core `BOM` + `BOM Item` | ⚠ **Chuyển dần** — AL BOM giữ cho báo giá; core BOM instantiate từ AL BOM (v28.9) | HIGH: phải giữ test vàng CDMQ-2C/4C không đổi |
| `AL BOM Version` (snapshot + immutable) | — | ✅ **Giữ nguyên** | Đã đúng chuẩn immutable; bổ sung snapshot pricing dimension |
| **Item quản lý theo Project** (mỗi project spec nhôm/màu/kính/kích thước riêng) | Core `Item` + `Project` + **Inventory Dimension** (kho) + **AL Pricing Dimension** (giá) | ✅ **KHÔNG Item Variant** — quản lý per-project (v28.9 #16); Item = mã đại diện, spec ghi ở nghiệp vụ | Chốt cơ chế per-project Variable Set (4.2.7) |
| `AL Cost Bucket` | Core `Cost Center` + `Accounting Dimension` | ⚠ **Chuyển cho P&L**; giữ bucket cho báo giá | MEDIUM; tránh phá `al_bom_result` |
| `AL Material Plan` | Core `Material Request` + `Production Plan` | ✅ **Chuyển** (v28.9 đã chọn) | LOW |
| `AL Production Order Bridge` | Core `Work Order` + `Job Card` + `Routing` | ✅ **Chuyển** (v28.9 đã chọn) | MEDIUM |
| Composite pricing (custom field trên Item Price) | `AL Pricing Dimension` (kiểu Accounting Dimension) + core `Price List` | ✅ **Giữ composite key, chuẩn hóa cơ chế** (v28.9 Owner chốt, v28.md:6786) | LOW-MEDIUM: thêm versioning snapshot (đã có design `P1-pricing-dimension-versioning.md`); test vàng không đổi |
| `AL Dynamic Item Rule` (chọn nẹp/keo) | Core BOM alternative items | ⚠ **Giữ tạm** (quá ngành) | LOW; xem lại sau |
| Inventory Dimension (kho đa chiều Màu/Loại/Dày) | Core `Inventory Dimension` (3 record config) | ✅ **Chuyển** (v28.9 đã chọn) | MEDIUM |
| `Batch`/`Serial No` trace (al_color, al_trace_stage...) | Core Batch/Serial + field mỏng | ✅ **Giữ field tối thiểu**, bỏ phần trùng | LOW |
| `AL Cutting Plan` (nhôm 1D/kinh 2D) | Core `Work Order`/`Job Card` (giữ thuật toán FFD/Guillotine) | ⚠ **Chuyển khung, giữ addon thuật toán** | MEDIUM (phase 2) |
| NC_LD (nhân công lắp đặt %/hệ số) | HRMS `Timesheet` + `Expense Claim` | ⚠ **Chuyển khi có thi công thực**; giữ ước lượng ở báo giá | MEDIUM |
| `AL Installation Team`/`Task` | Core `Employee` + `Project Task` + HRMS `Attendance` | ⚠ **Chuyển dần** | LOW |
| `AL Cost Variance` / `AL Project Profitability Snapshot` | Core `Budget` + `Cost Center` + Report | ⚠ **Thay bằng core khi đủ** | MEDIUM |

---

## 4. Giải pháp đề xuất — "Tận dụng tối đa core + FB"

Nguyên tắc: **một nguồn dữ liệu, một nơi resolve, cấu hình thay code**. Mọi nghiệp vụ có sẵn ở core
thì gọi core; mọi tính toán động thì giao formula_builder.

### 4.1 FB-max: biến Formula Variable Binding thành "biến toàn cục" của engine

**Mục tiêu:** B1/B2/B5 của BomOrchestrator đọc giá trị từ **một nguồn duy nhất** là FB binding, thay vì
3 resolver riêng (Variable Library + tự query Item Price + loop bucket).

1. **Đăng ký 3 handler alumglass chuẩn FB** — thêm decorator `@register_source` vào `fb_handlers.py`
   (mỗi handler kèm `label`, `description`, `config_schema` JSON Schema, `app="alumglass"`,
   `batchable=True`, `fingerprint_fn`):
   ```python
   from formula_builder.api.source_type_registry import register_source

   @register_source("aluminum_price_composite", label="Aluminum Price (Composite Key)",
       description="...", app="alumglass", batchable=True,
       fingerprint_fn=lambda cfg: f"nhom_price:{cfg.get('price_list')}",
       config_schema={"type":"object","properties":{"price_list":{"type":"string"},...}},
       supports_transform=True, supports_cache=True, default_cache_ttl=300)
   def aluminum_price_composite(binding, doc, resolved_so_far):
       ...
   ```
   (Đúng mẫu README FB §9.7.) → registry đếm được, admin UI sinh form, `list_source_types` hiện, batch theo fingerprint.

2. **Nối FVB vào BomOrchestrator B1:** thay `_resolve_system_variables()` bằng
   ```python
   from formula_builder.api.formula_builder import get_live_context
   ctx = get_live_context(doctype="AL BOM", doc=self._bom_doc)  # hoặc build qua VariableResolver
   self.inputs.update(ctx.get("variables", {}))
   ```
   → global binding (`is_global=1`) + per-doctype binding (`applies_to_doctype="AL BOM"`) resolve tự động,
   kèm topological sort, `session_variable`, `default_value` fallback. Bỏ query tay AL Variable Library/Profile/Product Type.

3. **Dùng `BatchBindingResolver` cho price/glass/rule** thay B2 thủ công:
   ```python
   from formula_builder.api.batch_binding_resolver import resolve_all_bindings_batch
   values = resolve_all_bindings_batch(bindings, doc)   # nhóm theo (source_type, fingerprint) → 1 query/nhóm
   ```
   → `aluminum_price_composite` (batchable) tự gom toàn bộ item_code cùng 1 fingerprint thành 1 query Item Price.
   `glass_master_data` batch theo glass_code. `_fetch_composite_prices`/`_match_composite_price` có thể bỏ.

4. **Cost Bucket:** thống nhất 1 vocabulary. Hai lựa chọn (đề xuất chọn A):
   - **A (khuyến nghị):** chuyển AL Cost Bucket sang dùng cơ chế FB — thêm field `bucket_formula` hoặc dùng
     `computed` binding; B5 gọi `cost_bucket_aggregate` (đã register) cho bucket LEAF, và để B6
     FlexibleFormulaEngine tính bucket AGGREGATE từ Cost Template (như hiện tại).
   - **B:** đổi `VALID_SOURCE_TYPES` của AL Cost Bucket thành **trùng 13 loại FVB** và viết 1 resolver
     dùng chung `resolve_bindings_with_deps` cho cả 2 (ít việc hơn nhưng duy trì 2 vocabulary = nợ kỹ thuật).
   - ⚠ **cần BA xác nhận:** đổi vocabulary `source_type` của AL Cost Bucket ảnh hưởng data đã seed
     (`seed_demo_data.py:_cost_buckets` ghi `aggregate_from_items`/`formula`) → phải có patch migrate
     (`alumglass/patches/`) + giữ backward compat; test vàng phải pass sau chuyển.

5. **B3:** thay regex bằng `DotToSubscriptTransformer`; nếu muốn mạnh hơn, dùng `MultiTableFormulaBuilder`
   `from_frappe_doc` để sinh formula + context từ child table 1 lần (FB v28.5, có ví dụ trong
   `docs/multi_table_formula_builder_examples.md`).

6. **B4/B6:** đổi `on_error="raise"` → `on_error="continue"` + `default_value` và trả về danh sách lỗi
   structured (không chết cả BOM khi 1 dòng sai), ghi lỗi vào ConfigSnapshot.

### 4.2 ERPNext-core: instantiate core BOM + nối MRP/SX

Đây là kế hoạch v28.9/v28.10 đã đề ra — cần hiện thực hóa:

1. **Từ AL BOM (mô hình báo giá) → core BOM (sản xuất):** khi AL BOM Version Published, sinh core `BOM`
   với các `BOM Item` tương ứng (item_code, qty theo UOM, scrap). Bridge qua ConfigSnapshot.
2. **v28.10:** khi Site Survey Approved → instantiate core BOM theo **kích thước thực** (không nominal).
3. **Mua hàng:** Material Plan → core `Material Request`; kế hoạch tổng → `Production Plan`.
4. **Kho:** kích hoạt `Inventory Dimension` (3 record config) cho kho đa chiều Màu/Loại/Dày; dùng core
   Batch/Serial cho truy vết (bỏ phần lớn custom field al_* trên Batch/Serial No, giữ tối thiểu).
5. **Kế toán:** mapping Cost Bucket → `Cost Center`; dùng `Accounting Dimension` cho P&L theo dự án/bucket.
6. **Giá — KHÔNG Item Variant (v28.9 #16, tránh bùng nổ data).** Chuẩn hóa **AL Pricing Dimension**
   theo đúng mô hình Accounting Dimension: mỗi dimension auto-tạo custom field `custom_pd_{dimension_code}`
   trên Item Price (composite key tra giá — thiết kế v28.md §B.5A; Owner đã chốt composite key v28.9,
   v28.md:6786). Giữ core `Price List` làm nơi lưu giá. Nghiệp vụ tra giá **không đổi** — chỉ chuẩn hóa
   cơ chế + đóng băng config vào AL BOM Version khi Publish (versioning, đã có design đầy đủ
   `P1-pricing-dimension-versioning.md`: field `pricing_dimension_snapshot` + patch backfill).
   → E9 (Item Variant cho profile) trong ARCHITECTURE-REVIEW **bị loại** bởi quyết định này.
7. **Per-project — KHÔNG Item Variant:** mỗi `Project` giữ 1 `AL Variable Set` riêng (màu nhôm, loại kính,
   phụ kiện, kích thước thực từ Site Survey v28.10) → instantiate core BOM theo kích thước thực.
   Khi nhập kho gán **Inventory Dimension** (Màu/Loại/Dày); khi báo giá dùng **AL Pricing Dimension**
   (composite key). Item vẫn là "mã nhôm đại diện" — không nhân Item theo từng tổ hợp spec (v28.md:996).

### 4.3 HRMS: chi phí nhân công thực

1. NC_LD: chuyển sang `Timesheet`/`Expense Claim` theo `Project`/`Task` khi có đơn thi công
   (giữ ước lượng `nc_ld_rate` ở phase báo giá, thay bằng thực tế khi chốt chi phí).
   - ⚠ **cần BA xác nhận:** chuyển NC_LD từ ước lượng (%/hệ số) sang chi phí thực (Timesheet) sẽ làm
     **báo giá ≠ chi phí thực tế**. Đề xuất chạy **song song 2 chế độ** ở phase 1: giữ `nc_ld_rate`
     cho báo giá, HRMS chỉ dùng cho đối soát chi phí dự án; thống nhất khi đủ dữ liệu.
2. Nhóm lắp đặt → core `Employee` + HRMS `Attendance` + `Project Task`.

### 4.4 Frappe core: tầng ứng dụng còn thiếu

1. `Notification`/`Email Alert` cho: BOM version published, đơn giá composite thiếu, site survey approved.
2. `Print Format` cho báo giá/quyết toán (hiện chỉ có JSON `al_bom_result`).
3. `Report Builder`/`Dashboard` KPI (doanh thu, biên lợi nhuận theo bucket).
4. `Webhook`/API cho tích hợp bên ngoài.
5. Phân quyền: hoàn thiện 4 role nghiệp vụ + workflow per doctype (bảng trong REVIEW_production_readiness).

---

## 5. Rủi ro kỹ thuật cần xử lý

| # | Rủi ro | Vị trí | Khuyến nghị |
|---|---|---|---|
| **R1** | **`eval()` trên chuỗi DB** | `al_quantity_calc_method.py:23` (`eval(fn_str, safe_ns)`) | Hạn chế: chỉ System Manager nhập; ưu tiên chuyển sang `custom_function` whitelist của FB (data_source_registry.py:807) |
| **R2** | Monkey-patch JS `_ContextBuilder.build()` | `public/js/formula_setup.js` | Fragile khi FB đổi API; tạm giữ + mở issue ngược lên FB để có hook chính thức |
| **R3** | `on_error="raise"` BOM chết cả lần tính | bom_orchestrator.py:558,641 | `on_error="continue"` + structured error list + log ConfigSnapshot |
| **R4** | Pricing Dimension **chưa versioning** (P1) | `al_pricing_dimension` | Báo giá cũ có thể sai nếu dimension đổi → snapshot `pricing_dimension_snapshot` vào AL BOM Version khi Publish (đã có design đầy đủ `P1-pricing-dimension-versioning.md` — cần hiện thực + patch backfill) |
| **R5** | BOM >200 dòng có thể **timeout** (P2) | `api.calculate_bom` | Async: đẩy sang background job (frappe.enqueue), trả job_id, client poll |
| **R6** | Custom field **nở rộ** trên Quotation Item (19 field) | `setup/custom_fields.py` | Gộp nhóm nhập liệu vào child table/JSON, chỉ giữ `al_bom`, `al_bom_vars`, `al_bom_result`, `al_gia_*` ở item |
| **R7** | `_resolve_doc_values` nuốt exception | `api/__init__.py:69` | Log thay vì `pass` im lặng |
| **R8** | Slug namespace phẳng, thiếu UOM conversion | `al_slug_library` | Thêm scope/namespace theo ngành (cửa thép, vách...) + UOM conversion (core `UOM Conversion Factor`) |

---

## 6. Ưu tiên hóa (đề xuất triển khai)

> ✅ = code-verified (làm được ngay, không cần hỏi thêm) · ⚠ = cần BA/Owner chốt nghiệp vụ trước ·
> 📄 = theo kế hoạch v28.9/v28.10 (cần xác minh trên erpnext 14.92 hiện có).

### P0 — Làm ngay (tuần 1, mở khóa các khoảng trống G2/G3/G4) — ✅

1. ✅ Đăng ký 3 fb_handlers bằng `@register_source` chuẩn (4.1.1).
2. ✅ Nối `get_live_context`/`resolve_bindings_with_deps` vào B1 (4.1.2) — bỏ `_resolve_system_variables` thủ công.
3. ✅ B5 gọi `cost_bucket_aggregate` cho LEAF bucket (4.1.4-A).
4. ✅ R3: `on_error="continue"` + structured errors.
5. ✅ R1: khoá `eval` theo role System Manager + test.

### P1 — Tuần 2–3 (FB-max + nền core)

6. ✅ `BatchBindingResolver` cho B2 (4.1.3); bỏ `_fetch_composite_prices`/`_match_composite_price`.
7. ✅ B3 dùng `DotToSubscriptTransformer` (bỏ regex).
8. ✅ R4: snapshot pricing dimension vào AL BOM Version.
9. ✅ AL Pricing Dimension chuẩn hóa + versioning snapshot (4.2.6) + per-project Variable Set (4.2.7) — **KHÔNG Item Variant** (v28.9 #16). Chốt detail: dimension set ban đầu + chạy patch backfill (R4 → đã có design `P1-pricing-dimension-versioning.md`).
10. ✅ R5: async BOM calc (frappe.enqueue + poll).

### P2 — Tuần 4+ (core ERPNext + HRMS, gắn v28.9/v28.10) — 📄

11. 📄 Core BOM instantiate từ AL BOM (v28.9) → nối Material Request/Production Plan.
12. 📄 v28.10: instantiate theo Site Survey Approved.
13. 📄 Inventory Dimension + Batch/Serial truy vết.
14. ⚠ Cost Bucket → Cost Center + Accounting Dimension P&L — **chờ BA chốt mapping bucket→cost center**.
15. ⚠ HRMS Timesheet/Expense Claim cho NC_LD thực tế — **chạy song song 2 chế độ** (xem note 4.3.1).
16. ✅ Notification/Print Format/Dashboard/Webhook (tầng ứng dụng Frappe, không rủi ro nghiệp vụ).

---


## 7. Lộ trình đề xuất tổng thể

```
[Hiện tại]  Engine BOM 7-phase chạy được, FVB/registry/ERPNext đều "có nhưng chưa nối"
    │
    ├─ P0 (1 tuần)  →  ✅ đóng G2/G3/G4: FB-max cho B1/B5 + register handlers + error recovery
    ├─ P1 (2–3 tuần) →  BatchBindingResolver, DotToSubscriptTransformer, snapshot dimension,
    │                  async BOM  (✅)  ·  AL Pricing Dimension + per-project (✅)
    └─ P2 (4 tuần+)  →  core BOM instantiate + MRP + Inventory Dimension (📄)
                        + Cost Center/Accounting Dimension (⚠) + HRMS nhân công (⚠, song song 2 chế độ)
                        + tầng ứng dụng Frappe (✅ notif/print/dashboard)
```

> **Điểm chờ quyết định (gating):** trước khi bắt đầu P1 mục 9 (dimension set + versioning) và P2 mục 14–15
> (Cost Center, HRMS) phải có BA/Owner chốt nghiệp vụ. P0 và các mục ✅ còn lại **không phụ thuộc**
> quyết định nào — DEV có thể bắt đầu ngay.

**Tiêu chí hoàn thành (Definition of Done):**
- `grep -rn "from erpnext"` > 0 ở các module al_buying/al_stock/al_manufacturing/al_account/al_construction.
- `list_source_types` hiện đủ 3 source type alumglass với schema + batchable.
- `get_live_context` là nguồn resolve duy nhất của B1 (không còn query tay Variable Library trong engine).
- B5/B6 tính bucket theo đúng `source_type`/`source_config` đã khai báo (không còn Python loop cứng).
- Test vàng CDMQ-2C (`GIA_VAT ≈ 22.717.289đ`) + CDMQ-4C vẫn pass sau mọi thay đổi.

---

## 8. Lưu ý khi migrate (không phá data hiện có)

1. **Giữ backward compat** `AL Variable Library`/`AL Calculation Rule` như fallback (giống cách
   `_resolve_system_variables` giữ CONSTANT rule làm fallback hiện tại, bom_orchestrator.py:174-184).
2. **AL BOM Version immutable** (al_bom_version.py:22) đã đúng — chỉ thêm snapshot pricing dimension,
   không phá snapshot cũ.
3. **Thay đổi vocabulary source_type của AL Cost Bucket** phải có patch migrate data (`alumglass/patches/`),
   không đổi schema đột ngột.
4. **Deploy qua quy trình chuẩn** (merge sub→foundation→master, không force-push, docs đi cùng code).
5. **Per-project:** KHÔNG migrate sang Item Variant — giữ Item đại diện + spec theo transaction; chỉ
   chuẩn hóa AL Pricing Dimension + snapshot vào AL BOM Version (backfill, không phá snapshot cũ).

---

## 9. Kết luận

AlumGlass đã có nền tảng **config-driven rất tốt** (engine chạy thật, test vàng, batching query, snapshot
immutable). Vấn đề không phải là thiếu core/FB, mà là **2 hệ thống "source_type" đang chạy song song chưa
hợp nhất** và **engine tự build lại đúng những gì FB/core đã cung cấp**. Việc nối Formula Variable Binding +
SourceTypeRegistry vào BomOrchestrator (P0) giải quyết ngay G2/G3/G4, sau đó instantiate core BOM + Inventory
Dimension + Cost Center + HRMS (P2) giúp app trở thành **lớp mỏng nghiệp vụ đúng nghĩa**: cấu hình ở DB,
tính toán ở formula_builder, nghiệp vụ chuẩn ở ERPNext — đúng tuyên bố "Config > Code, 0 dòng code cho
nghiệp vụ mới" mà các tài liệu kiến trúc đã hứa.

---

### Phụ lục — Bản đồ file chính (để DEV tra cứu)

| File | Vai trò | Dòng quan trọng |
|---|---|---|
| `alumglass/engine/bom_orchestrator.py` | Engine 7-phase | B1 (93), B2 (206), B3 (479), B4 (537), B5 (588), B6 (600), B7 (653) |
| `alumglass/fb_handlers.py` | 3 custom source type (chưa register) | 10 / 121 / 141 |
| `alumglass/hooks.py` | `fb_source_types` + `required_apps` | 13, 57–61 |
| `alumglass/api/__init__.py` | 7 whitelisted API + `get_formula_context` | 5, 75, 185–198 |
| `al_bom_engine/doctype/al_cost_bucket/al_cost_bucket.py` | Cost Bucket vocab + validate | 12–57 |
| `al_bom_engine/doctype/al_bom_version/al_bom_version.py` | Snapshot + immutability | 22, 45 |
| `al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py` | `eval()` lambda | 23 |
| `al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.py` | Pricing dimension → custom field | — |
| `setup/custom_fields.py` | Custom fields trên core doctypes | toàn bộ |
| `setup/seed_demo_data.py` | Seed A-Z (CDMQ-2C/4C) | 55–61 (_cost_buckets) |
| `public/js/formula_setup.js` | FB JS integration (initGridField/patchField) | 164, 182, 246 |
| **formula_builder** | | |
| `api/data_source_registry.py` | 13 source types + `resolve_bindings_with_deps` | 303–1223, 1282 |
| `api/source_type_registry.py` | v31 registry + `@register_source` | 206, 396, 489 |
| `api/batch_binding_resolver.py` | Batch resolution | 229, 256 |
| `api/formula_builder.py` | `get_live_context` | 273 |
| `table_formula_builder.py` | MultiTableFormulaBuilder | — |
| `flexible_formula_engine.py` | FlexibleFormulaEngine + ERPNextAdapter | — |
| `formula_utils/parser.py` | `DotToSubscriptTransformer` | 18 |
