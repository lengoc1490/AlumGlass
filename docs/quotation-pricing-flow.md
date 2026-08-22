# Luồng Tính Giá Báo Giá Đầy Đủ — AlumGlass × Formula Builder

> **Phạm vi:** Toàn bộ luồng tính giá 1 dòng Quotation Item — từ **master data**
> → các bước tính toán (B0–B7) → mapping từng hàm / từng file cụ thể của
> **formula_builder** và **alumglass** → kết quả cuối cùng `GIA_VAT`.
> **Ví dụ đi kèm:** CDMQ-2C (cửa đi 2 cánh) và CDMQ-4C + Vách kính (4 cánh + 2 transom + sidelite).
>
> **Số liệu tham chiếu:** chạy thật trên site dev `alumglass-dev`, golden
> CDMQ-2C = **22,717,289** (delta 10) · CDMQ-4C = **47,430,808** (delta 0).
> Verify lại bằng `bench --site alumglass-dev execute alumglass.run_test.main`.

---

## MỤC LỤC

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Master data — toàn bộ dữ liệu cấu hình nuôi engine](#2-master-data--toàn-bộ-dữ-liệu-cấu-hình-nuôi-engine)
3. [Điểm vào API](#3-điểm-vào-api)
4. [B0–B7 — Từng bước tính toán chi tiết + mapping hàm/file](#4-b0b7--từng-bước-tính-toán-chi-tiết--mapping-hàmfile)
5. [Bảng mapping — Formula Builder functions theo từng bước](#5-bảng-mapping--formula-builder-functions-theo-từng-bước)
6. [FB-max paths — kích hoạt khi nào, fallback khi nào](#6-fb-max-paths--kích-hoạt-khi-nào-fallback-khi-nào)
7. [Custom handlers đăng ký với FB](#7-custom-handlers-đăng-ký-với-fb)
8. [Lớp bảo mật safe_eval](#8-lớp-bảo-mật-safe_eval)
9. [Worked example 1 — CDMQ-2C](#9-worked-example-1--cdmq-2c)
10. [Worked example 2 — CDMQ-4C + Vách kính](#10-worked-example-2--cdmq-4c--vách-kính)
11. [Hướng dẫn mở rộng](#11-hướng-dẫn-mở-rộng)
12. [Ghi chú & item mở](#12-ghi-chú--item-mở)
13. [Đối chiếu với v28.md — điểm khớp / lệch](#13-đối-chiếu-với-v28md--điểm-khớp--lệch)

---

## 1. Kiến trúc tổng quan

```
Quotation Item (al_bom, al_bom_vars, al_bom_version)
        │  nút "Tính giá" → API
        ▼
alumglass.api.calculate_bom(qi_name)                 [alumglass/api/__init__.py]
        ▼
BomOrchestrator(qi_name).run()                       [alumglass/engine/bom_orchestrator.py]
  B0  Version pinning        → AL BOM Version snapshot (config đóng băng)
  B1  Gather inputs          → FB get_live_context + AL Variable Library + user vars
  B2  Prefetch master data   → batch query Item/ItemPrice/GlassMaster/MaterialCat
  B3  Build formulas         → normalize_global (FB) → FormulaEngine DAG
  B4  Calculate Bom Items    → formula_builder FormulaEngine
  B5  Aggregate cost buckets → FB aggregate_from_items (hoặc sum Python fallback)
  B6  Cost Template          → formula_builder FlexibleFormulaEngine
  B7  Save results           → ConfigSnapshot + ghi Quotation Item
        ▼
{al_gia_vat, al_gia_ban, al_bom_result, al_config_snapshot}
```

> **In báo giá (C5):** Print Format **"Báo giá AlumGlass"** đọc trực tiếp
> `al_bom_result` (JSON) + `al_gia_ban`/`al_gia_vat` từ Quotation Item — **không
> tính lại** lúc in. Template không dùng CSS zoom (tương thích wkhtmltopdf).
> Chi tiết: `docs/design/c5-print-format.md` + `docs/usage/bao-gia-print-format.vi.md`.

**Nguyên tắc thiết kế** (từ `bom_orchestrator.py` docstring): *AlumGlass chỉ config,
không hardcode nghiệp vụ.* Mọi logic nghiệp vụ nằm trong DB (Bom Item, Cost Bucket,
Cost Template, Profile System, Product Type…), mọi tính toán ủy thác cho Formula
Builder. Engine chỉ làm: đọc config → resolve biến → build formulas → gọi FB → lưu kết quả.

---

## 2. Master data — toàn bộ dữ liệu cấu hình nuôi engine

### 2.1 Chuỗi cấu hình BOM (data-driven)

```
AL BOM (bom_code, bom_set, default_cost_template, current_version)
  └─ AL BOM Version (bom_set_snapshot, cost_template_snapshot,
     pricing_dimension_snapshot, Published)   ← P1: + snapshot Pricing Dimension
       └─ AL Bom Set (product_type, profile_system, variable_set,
          default_accessory_set, formula_fieldnames)
            ├─ AL Bom Item  ×N   (slug, item_code, width/height/qty formula,
            │                     calc_pattern, cost_bucket, price_type,
            │                     price_base_item, item_selection_mode,
            │                     item_rule, rule_input_expr, default_glass_master)
            ├─ AL Variable Set (items → AL Variable Library)
            ├─ AL Accessory Set (items: slug, item_code, qty, qty_formula)
            └─ AL Slug Library (slug → category/group_tag, cho cross-row ref)
```

### 2.2 Bảng master data chi tiết — ai nuôi bước nào

| DocType | File seed | Vai trò | Tiêu thụ ở bước |
|---|---|---|---|
| `AL BOM` / `AL BOM Version` | `seed_demo_data.py::_bom/_bom_version` | Điểm định tuyến, snapshot đóng băng cấu hình | B0, B2, B6 |
| `AL Bom Set` / `AL Bom Item` | `_bom_items_and_set` | Công thức width/height/qty từng dòng, cost_bucket | B2, B3, B4 |
| `AL Variable Set` / `AL Variable Library` | `_variable_set` / `_variable_library` | Biến user (W_mm, H_mm, n_panel…) + system vars (OFFSET, NC_*, PROFIT) | B1 |
| `AL Accessory Set` | `_accessory_set` / `_accessory_set_4c` | Phụ kiện VL_PK (tay nắm, khóa, bản lề + qty_formula) | B2 (`_load_accessories`) |
| `AL Slug Library` | `_slug_library` | Định danh cross-row `items.{slug}.{field}` | B2, B3 |
| `AL Profile System` | `_profile_systems` | OFFSET_FRAME/GLASS/FIXED/CROSSBAR | B1 (system vars) |
| `AL Product Type` | `_product_type` | NC_SX_PCT, NC_LD_PCT, PROFIT_MARGIN | B1 (system vars) |
| `AL Material Category` | `_material_categories` | `default_scrap_pct`, `default_calc_pattern`, `default_cost_bucket` | B2 (scrap inject) |
| `AL Quantity Calc Method` | `_calc_methods` | `calc_fn` lambda: 4 legacy (LENGTH_TO_WEIGHT/AREA/LENGTH_ONLY/COUNT) + 9 v28.8 (LENGTH_M/HEIGHT_M/LENGTH_TO_PIECES/AREA_TO_WEIGHT/PERIMETER_M/VOLUME_M3/SET/COUNT_PER_LENGTH/COUNT_PER_AREA) + `group` | B4 (qua `lookup_calc_pattern` HYBRID) |
| `AL Calculation Rule` | `_calc_rules` | CONSTANT/THRESHOLD/LOOKUP: OFFSET-*, RULE-BANLE-QTY, RULE-HEIGHT-MULT | B4/B6 (qua `lookup_rule`) |
| `AL Dynamic Item Rule` | `_dynamic_item_rules` | Chọn item theo glass_thick/glass_type (nẹp/keo) | B2 (`resolve_item`) |
| `AL Glass Master` | `_glass_masters` | `total_thick_mm`, `glass_type` → rule_input | B2 |
| `AL Cost Bucket` | `_cost_buckets` | Vocabulary 14 bucket: VL_NHOM…GIA_VAT + `source_type`/`source_config` | B5 |
| `AL Cost Template` | `_cost_template` | 14 dòng công thức: TONG_VL → GIA_VAT | B6 |
| `AL Pricing Dimension` / `AL Variable Dimension Mapping` | `_pricing_dimensions` / `_variable_dimension_mapping` | Composite key: màu/xuất xứ/độ dày/bề mặt → custom fieldname trên Item Price. **P1:** snapshot đóng băng vào `AL BOM Version.pricing_dimension_snapshot` lúc publish — engine đọc snapshot trước, không query live | B2 (tra giá) |
| `AL Color Standard` | `_color_standards` | Màu + `price_multiplier` (DARK ×1.08) | B2 (multiplier_chain — FB handler) |
| `Formula Global Variable` | `_global_vars` + `_seed_async_threshold` | VAT_RATE, OH_VC_PCT, OH_QLY_PCT, **ASYNC_BOM_THRESHOLD** (P2 — default 150 dòng, chỉnh được) | B1 (+ quyết định sync/async ở `calculate_bom`) |
| `Formula Variable Binding` | *(D3 — chưa seed)* | Định nghĩa biến FB (pricing, glass_master…) | B1/B2 (FB-max) |
| `Item` / `Item Price` | `_items` / `_item_prices` | Trọng lượng riêng (tlr) + bảng giá composite key | B2 |

### 2.3 Item Price — composite key (nền tảng giá)

- Mỗi `item_code` có **1+ dòng** Item Price trong price_list `Standard Selling`.
- Dòng "trần" (không gắn dimension nào) = giá mặc định. Dòng màu/xuất xứ/độ dày/bề
  mặt gắn `custom_pd_*` field (map từ `AL Pricing Dimension.custom_fieldname`).
- Ánh xạ biến nhập → dimension → field trên Item Price:
  `aluminum_color → MAU_SAC → custom_pd_color`, `aluminum_origin → XUAT_XU`,
  `aluminum_thickness → DO_DAY`, `aluminum_surface → BE_MAT`
  (xem `_variable_dimension_mapping` + `_pricing_dimensions`).

### 2.4 AL Cost Template — validate công thức (client + server)

Có **2 lớp validate** bổ trợ — cùng nguồn universe biến động
`alumglass.api.get_formula_context("AL Cost Template")`:

1. **Client-side (chặn NGAY trên UI):** `alumglass/public/js/cost_template.js`
   `validate_formula(formula, opts)` — nâng cấp từ 2026-08-21 (job
   `fix/al-cost-template-validate`):
   - Giữ nguyên check cũ: công thức trống, dấu ngoặc không cân bằng, ký tự không hợp lệ.
   - **Mới:** parse identifier (bỏ qua string literal `'…'`/`"…"` — không tách nhầm
     `'RULE-HEIGHT-MULT'` thành RULE/HEIGHT/MULT) → biến nào không nằm trong
     `known_names` (từ `get_formula_context`), không phải `line_code` dòng trước, không phải
     hàm whitelist → trả về `{ valid: false, message: "Biến không khai báo: X" }`
     (hàm lạ → `"Hàm không hỗ trợ: X"`).
   - **Fallback an toàn:** `known_names` là async (fetch context). Nếu context chưa load xong
     → **bỏ qua check biến** (không chặn sai) — giống `_build_known_names` server fallback set rỗng.
   - Nguồn `known_names`: `get_formula_context("AL Cost Template")` — KHÔNG dùng
     `get_cost_template_context` (deprecated).
   - Kích hoạt: `al_cost_template.js` gọi `validate_formula` trong
     `frappe.ui.form.on("AL Cost Template Item", { calc_formula })` (feedback ngay khi sửa dòng,
     toast đỏ 5s) + trong `validate(frm)` của form (chặn save — `frappe.validated = false` +
     msgprint). Hàm whitelist client mirror server `_VALIDATOR_ALLOWED_FUNCS`
     (`BASE_FUNCS` + `lookup_rule`, `lookup_calc_pattern`, `roundup`).
   - Keyword operator Python (`and`, `or`, `not`, `in`, `is`, `if`, `else`, `elif`,
     `True`, `False`, `None`) được phép dùng làm biến — mirror server
     `FormulaValidator._python_keywords`, tránh chặn nhầm công thức dạng
     `W_mm > 100 and H_mm < 200`.
   - **(Optional) FB API:** `validateViaFB()` gọi
     `formula_builder.api.formula_builder.validate_formula(formula, scope_context_json)` với
     scope chứa `local_vars` = known_names (FB `parse_scope` chỉ đọc `local_vars`, không đọc key
     `variables`), lọc bỏ cảnh báo hàm custom alumglass, chỉ hiện error dạng toast.

2. **Server-side (cảnh báo khi save):** `ALCostTemplate.validate()` chạy mỗi lần save form
   (Document.validate, chỉ chặn save khi công thức trống hoặc dấu ngoặc không cân bằng — giữ
   hành vi cũ).
   - **Nguồn biến động** (không hardcode): `alumglass.api.get_formula_context("AL Cost Template")`
     — cùng universe với autocomplete form: Cost Bucket codes, AL Variable Library (system + user),
     Formula Global Variable, Common Vars (W_mm, H_mm, TransomHeight_mm, n_panel,
     installation_height_m…), Formula Variable Binding, Row Literals.
   - **Cơ chế:** ủy thác `FormulaValidator` (AST — `formula_builder/formula_utils/security.py`)
     với whitelist hàm = `BASE_FUNCS` + `lookup_rule`, `lookup_calc_pattern`, `roundup` (các custom
     function B6 inject). String literal không bị tách nhầm thành Name; biến lowercase chưa khai báo
     (typo) và hàm không whitelist đều được bắt.
   - **Message:** gộp **1 lần** `frappe.msgprint` (warning, indicator orange) — không chặn save,
     vì engine chạy `on_error="default"` nên biến thiếu sẽ tính 0 chứ không crash.
   - Đảm bảo golden không đổi: validate chỉ cảnh báo, không ảnh hưởng engine B1-B7.

---

## 3. Điểm vào API

`alumglass/api/__init__.py`:

```python
@frappe.whitelist()
def calculate_bom(quotation_item_name):
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    line_count = _estimate_bom_line_count(qi)     # đếm từ bom_set_snapshot (P2)
    threshold  = _get_async_threshold()           # Formula Global Variable ASYNC_BOM_THRESHOLD (default 150)
    if line_count <= threshold:
        result = BomOrchestrator(quotation_item_name).run()   # ĐỒNG BỘ — hành vi cũ giữ 100%
        return _normalize_bom_response(result)                # {buckets, cost_template, lines}
    return _enqueue_bom_calculation(qi)                       # BOM lớn → async (P2)
```

**BOM ≤ ngưỡng (sync):** `BomOrchestrator.run()` chạy tuần tự
`b0→b1→b2→b3→b4→b5→b6→b7`, trả về `{buckets, cost_template, lines}`. Client
(dialog báo giá) tự chọn key hiển thị. Response chuẩn hoá luôn đủ 3 key (C4).

**BOM > ngưỡng (async, P2):** `_enqueue_bom_calculation()` set
`al_calc_status=Queued` + `al_calc_job_id`, rồi
`frappe.enqueue(method="alumglass.api._run_bom_calculation_job", queue="long",
timeout=600, ..., user=frappe.session.user)` → trả về
`{async: True, job_id, status: "Queued", message}`. Worker set
`Running`→`Success` (hoặc `Failed`) + `commit` → push qua realtime
`alumglass_bom_calc_done` (lọc theo `job_id`). Client spinner + auto-update.
Bắt buộc `frappe.set_user(user)` trong worker (tránh chạy quyền Administrator).

> **Golden không đổi:** CDMQ-2C (16 dòng) và CDMQ-4C (22 dòng) đều < 150 →
> chạy sync, cùng code path cũ. Chi tiết: `docs/design/p2-async-bom-calculation.md`.

---

## 4. B0–B7 — Từng bước tính toán chi tiết + mapping hàm/file

### B0. Version pinning — `bom_orchestrator.py::b0_version_pinning`

- Đọc `Quotation Item.al_bom` + `al_bom_version`. Nếu không pin version → lấy
  `AL BOM.current_version` (Published). `frappe.throw` nếu chưa có version.
- Kết quả: `self.bom_version` (AL BOM Version có `bom_set_snapshot` +
  `cost_template_snapshot` — **cấu hình đóng băng**, engine không đọc trực tiếp
  bảng master để tránh drift khi đổi config).

### B1. Gather inputs — `b1_gather_inputs` (+ `_resolve_system_variables`, `_resolve_fb_context`, `_resolve_user_variable_defaults`)

Thứ tự merge (ưu tiên thấp → cao), tất cả vào `self.inputs`:

| # | Nguồn | Hàm | File (FB) |
|---|---|---|---|
| 1.1 | `al_bom_vars.extra_vars` JSON | `json.loads` | — |
| 1.2 | `Formula Global Variable` (VAT_RATE, OH_VC_PCT, OH_QLY_PCT) | `frappe.get_all("Formula Global Variable")` | — |
| 1.3 | **System variables** resolve từ `AL Variable Library` (is_system=1) với `source_doctype.source_field` → batch đọc `AL Profile System` + `AL Product Type` (OFFSET_*, NC_*, PROFIT_MARGIN); fallback `default_value`; fallback cuối AL Calculation Rule CONSTANT | `_resolve_system_variables` | — |
| 1.4 | **FB-max:** `get_live_context({"current_doctype":"Quotation Item","current_docname":qi})` — resolve global binding + system var + doc fields (topo-sort + default_value). Chỉ merge **scalar** (dict/list = Object bỏ qua) | `_resolve_fb_context` → `formula_builder.api.formula_builder.get_live_context` | `formula_builder/api/formula_builder.py` |
| 1.5 | User `bom_vars` (W_mm, H_mm, n_panel, …) ghi đè | merge dict | — |
| 1.6 | **User variables mặc định** (is_system=0) chưa có giá trị → `AL Variable Library.default_value` (vd `installation_height_m` → 3) | `_resolve_user_variable_defaults` | — |

> ⚠ Nếu biến không có giá trị → NameError ở B4/B6 → `NC_LD=0`. Bước 1.6 là fix
> quan trọng giúp golden 2C chạy đúng (RULE-HEIGHT-MULT(3)=1.0).

### B2. Prefetch master data — `b2_prefetch_master_data`

1. Load `bom_set_snapshot` → `self.bom_items`.
2. **`_load_accessories(bom_set)`** — nạp phụ kiện từ `AL Accessory Set`
   (`bom_vars.accessory_set` ưu tiên → `Bom Set.default_accessory_set`). Mỗi phụ
   kiện thành 1 row `cost_bucket="VL_PK"`, `calc_pattern="COUNT"`, qty có thể là
   **qty_formula** (vd `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel`), có thể
   ghi đè `unit_price` trực tiếp.
3. Gom toàn bộ code → **6 batch query** (thay N+1):
   - Q1 Item weights (`weight_per_unit` → tlr)
   - Q2 Item Prices (composite-key aware) — xem B2-FB-max bên dưới
   - Q3 AL Glass Master (`total_thick_mm`, `glass_type`) → `glass_data`
   - Q4 AL Material Category (`default_scrap_pct`) → inject `scrap_pct`
   - Q5 AL Dynamic Item Rule resolve (rule_input từ `glass_data` — bắt buộc Q3 trước Q5)
   - Q6 Resolved item weights + prices
4. Build `row_literals[slug]` = `{weight_per_unit, unit_price, calc_pattern,
   glass_thick, glass_type, item_code, scrap_pct}`.

**B2-FB-max — Tra giá composite key:**

```
all_price_items = item_codes + price_base_items
prices = self._fetch_composite_prices_via_fb(all_price_items)   # ★ FB
if prices is None:
    prices = self._fetch_composite_prices(all_price_items)       # fallback cũ
```

- `_fetch_composite_prices_via_fb` → `_get_pricing_bindings()` filter
  `Formula Variable Binding` có `source_type ∈ {composite_key_lookup,
  aluminum_price_composite}` + `applies_to_doctype ∈ {"", Quotation Item, AL Bom Item}`
  → gọi **`resolve_all_bindings_batch(bindings, doc=qi, pre_resolved=row_ctx)`**
  (`formula_builder/api/batch_binding_resolver.py`). Với mỗi item_code build
  `row_ctx = inputs + {item_code, price_base_item, row}`.
- Không có binding active → trả `None` → **fallback `_fetch_composite_prices`**
  (match Item Price theo composite key qua `_get_dim_fieldnames()` +
  `_match_composite_price` — chọn dòng khớp nhiều field nhất, fallback dòng "trần").

> **Trạng thái hiện tại:** FVB pricing (`composite_key_lookup`/
> `aluminum_price_composite`) **chưa seed** → `_get_pricing_bindings()` trả `[]` →
> luồng FB pricing chưa active, luôn chạy fallback cũ (giá 113,000/1,150,000 flat).
> D3 (`seed_fvb_from_variable_library`) mới seed **global constant + system
> variable** FVB (bật B1.4 FB-max cho variables) — KHÔNG seed pricing bindings.
> Pricing bindings là việc Phase D riêng (xem §6 gating + `docs/design/fvb-seed.md`).

### B3. Build formulas — `b3_build_formulas`

- Với mỗi Bom Item: inject literal `{slug}__{field}` vào `inputs`
  (weight_per_unit, unit_price, calc_pattern, glass_thick, glass_type, scrap_pct).
- Build formulas từ **`formula_fieldnames`** config của Bom Set
  (fallback `DEFAULT_FORMULA_FIELDS` = width, height, qty, show_condition,
  item_condition_formula, rule_input_expr). Mỗi field có công thức → formula node
  `{slug}__{field}`.
- **`_normalize_items_ref`** — cross-row `items.X.Y` → `X__Y` qua
  `formula_builder.table_formula_builder.normalize_global` (regex `\w+\.(\w[\w-]*)\.(\w+)`
  → `\1__\2`). *Không* dùng DotToSubscriptTransformer (X__Y trỏ vào **formula result**
  DAG node, không phải nested dict đã resolve — nếu transform thành `items['X']['Y']`
  engine đọc literal = 0 → lệch golden).
- **3 synthetic formulas** luôn được tạo cho mỗi slug:
  ```
  {slug}__unit_qty   = lookup_calc_pattern({slug}__calc_pattern,
                                            {slug}__width, {slug}__height,
                                            {slug}__weight_per_unit)
  {slug}__total_qty  = {slug}__unit_qty * {slug}__qty
  {slug}__line_total = {slug}__total_qty * {slug}__unit_price
  ```
- Inject `self.inputs["items"]` = nested dict (cho tooling/normalizer tham chiếu).

### B4. Calculate Bom Items — `b4_calculate_bom_items`

```python
from formula_builder.formula_utils.engine_public import FormulaEngine
engine = FormulaEngine(
    formulas=self.bom_formulas,
    safe_funcs={
        "lookup_calc_pattern": lookup_calc_pattern,   # alumglass AL Quantity Calc Method
        "lookup_rule":         _lookup_rule,          # alumglass AL Calculation Rule
        "roundup":             _roundup,
    },
    on_error="default", default_value=0, deterministic=True,
)
result = engine.calculate(dict(self.inputs))
self.bom_engine_errors = engine.last_errors.copy()   # structured errors, không chết cả BOM
```

- `FormulaEngine` tự **topo-sort DAG**: width/height/qty → unit_qty → total_qty →
  line_total; cross-row dependency qua `X__Y` nodes (items.kinh_tren.width → kinh_tren__width).
- **`lookup_calc_pattern`** (v28.8 HYBRID — `alumglass/formula_handlers.py`, re-export qua
  `al_quantity_calc_method.py` giữ nguyên module path): **DB-first** đọc `calc_fn` lambda từ
  DB (cache positive), parse AST → lấy body → `safe_eval.compile_expression` → eval với
  scope `{w, h, tlr, kw, abs, min, max, round}`; nếu không có DB record hoặc `calc_fn`
  rỗng → **fallback** `PATTERN_FORMULAS` (12 built-in + 2 alias legacy AREA≡AREA_M2,
  LENGTH_ONLY≡LENGTH_M) → `ValueError` nếu không có cả 2. Negative cache tránh query lại
  DB cho code không có record. Không hardcode if/elif.
  - `LENGTH_TO_WEIGHT`: `(w/1000)*tlr`
  - `AREA` ≡ `AREA_M2`: `(w/1000)*(h/1000)`
  - `LENGTH_ONLY` ≡ `LENGTH_M`: `w/1000`
  - `COUNT`: `1`
- **`_lookup_rule`** (`bom_orchestrator.py` module-level): `AL Calculation Rule.resolve(input)`:
  CONSTANT → giá trị cố định; THRESHOLD → tier; LOOKUP → key match.
- Build `bom_result[]` = per-slug `{slug, item_code, width, height, qty, unit_qty,
  total_qty, unit_price, line_total, cost_bucket}`.

### B5. Aggregate cost buckets — `b5_aggregate_cost_buckets`

```
fb_buckets = self._resolve_cost_buckets_via_fb()   # ★ FB
buckets = defaultdict(float)
for row in bom_result:
    if row.cost_bucket in fb_buckets: buckets[bk] = fb_buckets[bk]   # set 1 lần
    else:                            buckets[bk] += row.line_total    # fallback sum Python
```

- **FB path** `_resolve_cost_buckets_via_fb`: đọc `AL Cost Bucket.source_type` +
  `source_config`; LEAF bucket có `source_type="aggregate_from_items"` + `source_config`
  hợp lệ → build binding → `resolve_all_bindings_batch(..., pre_resolved={inputs, rows:
  [{cost_bucket, line_total}...]})` → FB `aggregate_from_items` (sum theo key_field
  giống sumif, `rows_source="resolved"`).
- **Gating:** chưa có `source_config` → trả `{}` → sum Python. Seed hiện tại set
  `source_type="aggregate_from_items"` nhưng **source_config trống** → fallback sum —
  đây là đường golden hiện tại (bảo toàn số).

### B6. Cost Template — `b6_calculate_cost_template` (FlexibleFormulaEngine)

```python
from formula_builder.flexible_formula_engine import FlexibleFormulaEngine, EngineConfig
config = EngineConfig(
    global_formulas=global_formulas,          # từ cost_template_snapshot (14 dòng)
    extra_context={**self.inputs, **self.buckets},
    on_error="default", default_value=0, deterministic=True,
    custom_functions={                        # ⚠ BẮT BUỘC — thiếu → UNKNOWN_FUNCTION
        "lookup_calc_pattern": lookup_calc_pattern,
        "lookup_rule": _lookup_rule,
        "roundup": _roundup,
    },
)
result = FlexibleFormulaEngine(config).calculate(dict(self.inputs))
self.gia_vat = result.values["GIA_VAT"]
```

- `global_formulas` = `{line_code: calc_formula}` từ snapshot Cost Template
  (TONG_VL, NC_SX, NC_LD, TONG_NC, OH_VC, OH_QLY, TONG_OH, GIA_THANH, PROFIT,
  GIA_BAN, DON_GIA_M2, VAT, GIA_VAT…).
- Regex trích **bucket codes được reference** → set default 0 (không load cả bảng).
- `extra_context` gồm `inputs` + `buckets` (giá trị từ B5) — B6 đọc `TONG_VL` qua
  bucket, không qua B4 lines.
- **NC_LD dùng `lookup_rule('RULE-HEIGHT-MULT', installation_height_m)`** — hệ số
  nhân công theo độ cao lắp đặt (custom function B6).
- Kết quả: `self.cost_result` (14 dòng), `self.gia_vat`, `self.cost_engine_errors`.

### B7. Save results — `b7_save_results` (SINGLE commit)

- Build `full_result = {buckets, cost_template, lines, gia_vat, errors:{bom_items,
  cost_template}}` → `result_json`.
- Tạo **`ConfigSnapshot`** (inputs_json + result_json + bom_version + quotation_item)
  → lưu `al_config_snapshot` (audit trail).
- `frappe.db.set_value("Quotation Item", qi, {al_gia_vat, al_gia_ban, al_bom_result,
  al_config_snapshot})` → **1 commit duy nhất** (`frappe.db.commit()`).

---

## 5. Bảng mapping — Formula Builder functions theo từng bước

| Bước | Hàm FB | File FB | Ý nghĩa |
|---|---|---|---|
| B1 | `get_live_context(scope_json)` | `formula_builder/api/formula_builder.py` | Resolve FVB global + system var + doc field (topo + default) |
| B2 | `resolve_all_bindings_batch(bindings, doc, pre_resolved)` | `formula_builder/api/batch_binding_resolver.py` | Batch resolve pricing bindings (group theo fingerprint, 1 query/group) |
| B2 | `BatchBindingResolver` (transform layer) | `formula_builder/api/batch_binding_resolver.py` | `source_config.transform` (multiply/divide/add/formula/round/cast) — evaluate qua `safe_eval` |
| B3 | `normalize_global(expr)` | `formula_builder/table_formula_builder.py` | `items.{slug}.{field}` → `{slug}__{field}` (canonical flat) |
| B4 | `FormulaEngine(formulas, safe_funcs, on_error, default_value, deterministic)` | `formula_builder/formula_utils/engine_public.py` | DAG + topo-sort + tính toàn bộ Bom Items |
| B4/B6 | `safe_eval.compile_expression(...)` | `formula_builder/security/safe_eval.py` | Compile an toàn (thay eval trần) — dùng bởi calc_fn, transform, cost template |
| B5 | `aggregate_from_items` handler | `formula_builder/api/data_source_registry.py` | Sum theo key_field/key_value (giống sumif) từ rows đã resolve |
| B5 | `resolve_all_bindings_batch` | `formula_builder/api/batch_binding_resolver.py` | Aggregate binding batch |
| B6 | `FlexibleFormulaEngine(EngineConfig)` | `formula_builder/flexible_formula_engine.py` | Cost template header formulas + custom_functions |
| B6 | `EngineConfig(global_formulas, extra_context, custom_functions, ...)` | `formula_builder/flexible_formula_engine.py` | Config lớp bọc FormulaEngine |

### Hàm alumglass gọi bởi FB (safe_funcs / custom_functions)

| Tên | File alumglass | Chức năng |
|---|---|---|
| `lookup_calc_pattern(code, w, h, tlr, **kw)` | `al_formula_rules/.../al_quantity_calc_method.py` | Dispatch pattern tính SL đơn vị từ DB |
| `_lookup_rule(rule_code, input_value)` | `engine/bom_orchestrator.py` | Tra AL Calculation Rule (CONSTANT/THRESHOLD/LOOKUP) |
| `_roundup(x, y)` | `engine/bom_orchestrator.py` | `math.ceil` |

---

## 6. FB-max paths — kích hoạt khi nào, fallback khi nào

**Nguyên tắc gating:** *FB-max chỉ active khi dữ liệu FB tồn tại.* Không có FVB
binding/config → resolver cũ chạy → **bảo toàn golden** (D3 chỉ thêm engine
guard nhỏ trong `_resolve_fb_context`: scope AL Bom Set + bỏ qua chuỗi rỗng +
coerce số — KHÔNG đụng core calculation; chi tiết `docs/design/fvb-seed.md`).

| Điểm | FB-max active khi | Fallback (hiện tại) |
|---|---|---|
| B1 `_resolve_fb_context` | FVB seed (D3) → `get_live_context` trả đủ binding; scope ưu tiên **AL Bom Set** để system-var FVB resolve từ Profile System/Product Type | `get_live_context` vẫn trả global vars + doc fields → trả ít binding; resolver cũ ở 1.3 chạy song song |
| B2 pricing | ≥1 binding `composite_key_lookup`/`aluminum_price_composite` active | `_fetch_composite_prices` (match Item Price theo composite key) |
| B5 aggregate | AL Cost Bucket có `source_type="aggregate_from_items"` **và** `source_config` hợp lệ | sum Python trên `bom_result.line_total` |
| B6 | Luôn chạy FlexibleFormulaEngine (bắt buộc `custom_functions`) | — (không fallback; thiếu custom_functions = crash UNKNOWN_FUNCTION) |

> ⚠ **Quan trọng:** B6 `custom_functions` là **bắt buộc từ mọi phiên bản** — seed
> Cost Template dùng `lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` (NC_LD)
> nên EngineConfig thiếu nó → `[ENGINE.UNKNOWN_FUNCTION]`. Baseline HEAD cũ thiếu fix
> này → import chưa từng chạy ra golden.

---

## 7. Custom handlers đăng ký với FB

`alumglass/fb_handlers.py` — đăng ký qua `@register_source`
(`formula_builder/api/source_type_registry.py`, auto-discover qua `hooks.py fb_source_types`):

| Source type | batchable | fingerprint | Cache TTL | Chức năng |
|---|---|---|---|---|
| `aluminum_price_composite` | ✅ | `price_list\|material_category` | 300s | Tra giá nhôm theo composite key từ `AL Variable Dimension Mapping`. 2 mode: `exact_match` (lookup Item Price chính xác) / `multiplier_chain` (base price × ∏(multipliers), đọc `AL Color Standard.price_multiplier`) |
| `glass_master_data` | ✅ | `glass_code` | 3600s | Tra `glass_thick`/`glass_type` từ `AL Glass Master` |
| `cost_bucket_aggregate` | ❌ | — | — | **DEPRECATED** — thay bằng source_type `aggregate_from_items` của FB. Giữ backward-compat |

```python
# fb_handlers.py — khai báo chuẩn
@register_source("aluminum_price_composite", label="Aluminum Price (Composite Key)",
    config_schema={...}, app="alumglass", version="1.0",
    batchable=True,
    fingerprint_fn=lambda cfg: "aluminum_price_composite:" + cfg.get("price_list","") + "|" + cfg.get("material_category",""),
    supports_cache=True, default_cache_ttl=300)
def aluminum_price_composite(binding, doc, resolved_so_far):
    # read mapping: AL Variable Dimension Mapping (filter material_category)
    # read dims: AL Pricing Dimension (custom_fieldname, link_doctype)
    # exact_match: get_all("Item Price", filters=[item_code, price_list] + [cfn, "=", value]...)
    # multiplier_chain: base price × ∏(linked_mult | map_mult)
    ...
```

---

## 8. Lớp bảo mật safe_eval

- **Bối cảnh:** cũ dùng `eval(expr, {"__builtins__": {}}, {})` — **sandbox myth**:
  `().__class__.__base__.__subclasses__()` vẫn escape được (attribute traversal).
- **Fix** (`formula_builder/security/safe_eval.py`):
  - `compile_expression(expr, allowed_functions, policy)` → validate AST 1 lần → compile → `SafeExpression.eval(scope)` nhanh trong hot loop.
  - `ExpressionPolicy`: chặn import/lambda/gán/dunder attr/`getattr,setattr,delattr`
    (`FORBIDDEN_NAMES`), method call, subscript depth, iter size. 4 policy:
    `DEFAULT_POLICY`, `FILTER_POLICY`, `CONDITION_POLICY`, `TRANSFORM_POLICY`.
  - `SecurityValidator.FORBIDDEN_NAMES` bổ sung `getattr/setattr/delattr` (tầng compile).
- **Điểm áp dụng trong alumglass:**
  - `al_cost_template.py::preview_cost_template` — `compile_expression(item.calc_formula or "0").eval(ctx)` + `_is_number` coerce.
  - `al_quantity_calc_method.py::_compile_calc_fn` — parse `ast.Lambda` → `ast.unparse(body)` → `compile_expression(body, allowed_functions=("abs","min","max","round"))`.
  - `batch_binding_resolver.py::_apply_transform` — transform formula qua `compile_expression(..., policy=TRANSFORM_POLICY)`.

---

## 9. Worked example 1 — CDMQ-2C

**Input** (`run_test.py::test_cdmq_2c`): `W_mm=2400, H_mm=2600, n_panel=2,
TransomHeight_mm=600, aluminum_color=WHITE, aluminum_origin=IMPORT,
aluminum_thickness=20, aluminum_surface=POWDER_COATED`. BOM `BOM-CDMQ-2C`.

**System vars (B1):** `OFFSET_FRAME=48, OFFSET_GLASS=90, OFFSET_FIXED=50,
OFFSET_DO_NGANG=48` (XINGFA_55) · `NC_SX_PCT=0.08, NC_LD_PCT=0.12, PROFIT_MARGIN=0.16`
(Product Type DOOR) · `VAT_RATE=0.10, OH_VC_PCT=0.03, OH_QLY_PCT=0.03` (Global Var).
`installation_height_m` không truyền → default **3** → RULE-HEIGHT-MULT(3) = **1.0**.

### 9.1 Per-line (B2–B4) — `GIA_VAT = 22,717,299` (golden ref 22,717,289, delta 10 ✓)

| Slug | item_code | width (mm) | uqty | qty | total_qty | price | line_total | bucket |
|---|---|---|---|---|---|---|---|---|
| khung_ngang_tren | XF55-KB-20 | 2400 | 3.017 | 1 | 3.017 | 113,000 | 340,898 | VL_NHOM |
| khung_ngang_duoi | XF55-KB-20 | 2400 | 3.017 | 1 | 3.017 | 113,000 | 340,898 | VL_NHOM |
| khung_dung | XF55-KB-20 | 2600 | 3.268 | 2 | 6.536 | 113,000 | 738,613 | VL_NHOM |
| do_ngang | XF55-KB-20 | 2400−2×48=2304 | 2.896 | 1 | 2.896 | 113,000 | 327,262 | VL_NHOM |
| canh_ngang | XF55-CANH-20 | 2400/2−48=1152 | 1.555 | 4 | 6.221 | 113,000 | 702,950 | VL_NHOM |
| canh_dung | XF55-CANH-20 | (2600−600)−48=1952 | 2.635 | 4 | 10.541 | 113,000 | 1,191,110 | VL_NHOM |
| kinh_tren | KINH-LOWE-24 | 2400−2×50=2300 | 1.265 | 1 | 1.265 | 1,150,000 | 1,454,750 | VL_KINH |
| kinh_duoi | KINH-LOWE-24 | 2400/2−90=1110 | 2.120 | 2 | 4.240 | 1,150,000 | 4,876,230 | VL_KINH |
| nep_kinh_tren | C3211-20 (Rule) | 2×(2300+550)=5700 | 1.778 | 2 | 3.557 | 113,000 | 401,918 | VL_NHOM |
| nep_kinh_duoi | C3211-20 (Rule) | 2×(1110+1910)=6040 | 1.884 | 4 | 7.538 | 113,000 | 851,785 | VL_NHOM |
| keo_tren | KEO-TT-01 (Rule) | 5700 | 5.700 | 1 | 5.700 | 45,000 | 256,500 | VL_VTP |
| keo_duoi | KEO-TT-01 (Rule) | 6040 | 6.040 | 2 | 12.080 | 45,000 | 543,600 | VL_VTP |
| gioang | GIO-EPDM-55 | 2400+2400+2×2600=10000 | 10.000 | 1 | 10.000 | 1,250 | 12,500 | VL_VTP |
| vit | VIT-TK-35X16 | — | 1.000 | 28 | 28.000 | 850 | 23,800 | VL_VTP |
| tay_nam | KL-MZS20 | — | 1.000 | 1 | 1.000 | 210,000 | 210,000 | VL_PK |
| khoa | KL-KHOA-01 | — | 1.000 | 1 | 1.000 | 350,000 | 350,000 | VL_PK |
| ban_le | KL-T-MJ06 | — | 1.000 | **8** | 8.000 | 180,000 | 1,440,000 | VL_PK |

> `nep`/`keo` resolve item qua **Dynamic Item Rule**: glass_thick=24 → RULE-NEP-GLASSTHICK
> → tier 16.01-999 → `C3211-20`; glass_type=LOWE → RULE-KEO-GLASSTYPE → `KEO-TT-01`.
> `ban_le`: `lookup_rule('RULE-BANLE-QTY', 2600) × 2` = tier 2101-2700 → 4 × 2 = **8**
> (golden khớp 8 bản lề — seed tier `2101-2700=4`, không còn 3).

### 9.2 Buckets (B5) — sum theo cost_bucket

| Bucket | Σ line_total |
|---|---|
| VL_NHOM | **4,895,437** |
| VL_KINH | **6,330,980** |
| VL_VTP | **836,400** |
| VL_PK | **2,000,000** (210,000+350,000+1,440,000) |
| **TONG_VL** | **14,062,817** |

### 9.3 Cost Template (B6) — CT-01-STANDARD

| Line | Công thức | Kết quả |
|---|---|---|
| TONG_M2 | `(W_mm/1000)*(H_mm/1000)` | 2.4×2.6 = **6.240 m²** |
| NC_SX | `0.08 × TONG_VL` | 1,125,025 |
| NC_LD | `0.12 × TONG_VL × lookup_rule('RULE-HEIGHT-MULT', 3)` | 1,687,538 (×1.0) |
| TONG_NC | `NC_SX + NC_LD` | **2,812,563** |
| OH_VC | `0.03 × TONG_VL` | 421,884 |
| OH_QLY | `0.03 × (TONG_VL + TONG_NC)` | 506,261 |
| TONG_OH | `OH_VC + OH_QLY` | **928,146** |
| GIA_THANH | `TONG_VL + TONG_NC + TONG_OH` | **17,803,526** |
| PROFIT | `0.16 × GIA_THANH` | 2,848,564 |
| GIA_BAN | `GIA_THANH + PROFIT` | **20,652,090** |
| DON_GIA_M2 | `GIA_BAN / TONG_M2` | **3,309,630 VND/m²** |
| VAT | `0.10 × GIA_BAN` | 2,065,209 |
| **GIA_VAT** | `GIA_BAN + VAT` | **22,717,299** ✅ |

---

## 10. Worked example 2 — CDMQ-4C + Vách kính

**Input** (`test_cdmq_4c`): `W_mm=3600, H_mm=3200, n_panel=4, TransomHeightTop=600,
TransomHeightBottom=400, SideLiteWidth=800, SideLiteHeight=2800, aluminum_color=DARK,
aluminum_origin=IMPORT, aluminum_thickness=20, aluminum_surface=POWDER_COATED,
installation_height_m=15`. BOM `BOM-CDMQ-4C`.

Sản phẩm demo **toàn bộ tính năng**: 22 Bom Items (khung 4 + đố 2 + cánh 4×2 hướng +
kính 4 + nẹp 2 + keo 2 + gioăng + vít) + phụ kiện 4C.

> **Lưu ý màu DARK:** `AL Color Standard.price_multiplier=1.08` chỉ được áp khi FB
> `aluminum_price_composite` ở mode `multiplier_chain` được kích hoạt qua FVB binding
> (Phase C/D). **Hiện tại** FVB chưa seed → fallback trả giá base 113,000/1,150,000 —
> golden 47,430,808 được chốt trên số liệu này. Khi seed FVB → giá tự ×1.08 mà không
> đổi code (verify lại golden).

### 10.1 Per-line (B2–B4) — `GIA_VAT = 47,430,808` (delta 0 ✅)

| Slug | item_code | width (mm) | uqty | qty | total_qty | price | line_total | bucket |
|---|---|---|---|---|---|---|---|---|
| khung_ngang_tren | XF55-KB-20 | 3600 | 4.525 | 1 | 4.525 | 113,000 | 511,348 | VL_NHOM |
| khung_ngang_duoi | XF55-KB-20 | 3600 | 4.525 | 1 | 4.525 | 113,000 | 511,348 | VL_NHOM |
| khung_dung_trai | XF55-KB-20 | 3200 | 4.022 | 2 | 8.045 | 113,000 | 909,062 | VL_NHOM |
| khung_dung_phai | XF55-KB-20 | 3200 | 4.022 | 2 | 8.045 | 113,000 | 909,062 | VL_NHOM |
| do_ngang_tren | XF55-KB-20 | 3600−96=3504 | 4.405 | 1 | 4.405 | 113,000 | 497,712 | VL_NHOM |
| do_ngang_duoi | XF55-KB-20 | 3504 | 4.405 | 1 | 4.405 | 113,000 | 497,712 | VL_NHOM |
| canh_dung_c1…c4 | XF55-CANH-20 | (3200−600−400)−48=2152 | 2.905 | 2 | 5.810 | 113,000 | 656,575 ×4 | VL_NHOM |
| canh_ngang_c1…c4 | XF55-CANH-20 | 3600/4−48=852 | 1.150 | 2 | 2.300 | 113,000 | 259,945 ×4 | VL_NHOM |
| kinh_fixed_top | KINH-LOWE-24 | 3600−100=3500 | 1.925 | 1 | 1.925 | 1,150,000 | 2,213,750 | VL_KINH |
| kinh_fixed_bottom | KINH-LOWE-24 | 3500 | 1.225 | 1 | 1.225 | 1,150,000 | 1,408,750 | VL_KINH |
| kinh_canh | KINH-LOWE-24 | 3600/4−90=810 | 1.709 | 4 | 6.836 | 1,150,000 | 7,861,860 | VL_KINH |
| kinh_sidelite | KINH-LOWE-24 | 800−100=700 | 1.890 | 1 | 1.890 | 1,150,000 | 2,173,500 | VL_KINH |
| nep_kinh_canh | C3211-20 | 2×(810+2110)=5840 | 1.822 | 8 | 14.577 | 113,000 | 1,647,160 | VL_NHOM |
| nep_kinh_sidelite | C3211-20 | 2×(700+2700)=6800 | 2.122 | 2 | 4.243 | 113,000 | 479,482 | VL_NHOM |
| keo_canh | KEO-TT-01 | 5840 | 5.840 | 4 | 23.360 | 45,000 | 1,051,200 | VL_VTP |
| keo_sidelite | KEO-TT-01 | 6800 | 6.800 | 1 | 6.800 | 45,000 | 306,000 | VL_VTP |
| gioang | GIO-EPDM-55 | 3600+3600+2×3200=13600 | 13.600 | 1 | 13.600 | 1,250 | 17,000 | VL_VTP |
| vit | VIT-TK-35X16 | — | 1.000 | 80 | 80.000 | 850 | 68,000 | VL_VTP |
| tay_nam | KL-MZS20 | — | 1.000 | 4 | 4.000 | 210,000 | 840,000 | VL_PK |
| khoa | KL-KHOA-01 | — | 1.000 | 1 | 1.000 | 350,000 | 350,000 | VL_PK |
| ban_le | KL-T-MJ06 | — | 1.000 | **16** | 16.000 | 180,000 | 2,880,000 | VL_PK |

> `ban_le`: `lookup_rule('RULE-BANLE-QTY', 3200) × 4` = tier 2701-99999 → 4 × 4 = **16**.
> `kinh_sidelite` = vách kính bên (SideLiteWidth−2×OFFSET_FIXED = 800−100 = 700).

### 10.2 Buckets (B5)

| Bucket | Σ line_total |
|---|---|
| VL_NHOM | **9,628,967** |
| VL_KINH | **13,657,860** |
| VL_VTP | **1,442,200** |
| VL_PK | **4,070,000** (840,000+350,000+2,880,000) |
| **TONG_VL** | **28,799,027** |

### 10.3 Cost Template (B6) — installation_height_m=15 → RULE-HEIGHT-MULT = **1.2**

| Line | Công thức | Kết quả |
|---|---|---|
| TONG_M2 | `(3600/1000)*(3200/1000)` | 3.6×3.2 = **11.520 m²** |
| NC_SX | `0.08 × 28,799,027` | 2,303,922 |
| NC_LD | `0.12 × 28,799,027 × lookup_rule('RULE-HEIGHT-MULT', 15)` | **4,147,060** (×1.2 ★) |
| TONG_NC | `NC_SX + NC_LD` | **6,450,982** |
| OH_VC | `0.03 × TONG_VL` | 863,971 |
| OH_QLY | `0.03 × (TONG_VL + TONG_NC)` | 1,057,500 |
| TONG_OH | `OH_VC + OH_QLY` | **1,921,471** |
| GIA_THANH | `TONG_VL + TONG_NC + TONG_OH` | **37,171,480** |
| PROFIT | `0.16 × GIA_THANH` | 5,947,437 |
| GIA_BAN | `GIA_THANH + PROFIT` | **43,118,917** |
| DON_GIA_M2 | `GIA_BAN / TONG_M2` | **3,742,962 VND/m²** |
| VAT | `0.10 × GIA_BAN` | 4,311,892 |
| **GIA_VAT** | `GIA_BAN + VAT` | **47,430,808** ✅ |

### 10.4 Điểm nổi bật của 4C

- **Dynamic Item Rule:** 2 nẹp (THRESHOLD theo glass_thick=24 → C3211-20) + 2 keo
  (LOOKUP theo glass_type=LOWE → KEO-TT-01).
- **lookup_rule 2 chỗ:** NC_LD (RULE-HEIGHT-MULT 15m → 1.2) + ban_le
  (RULE-BANLE-QTY 3200 → 4/cánh).
- **System vars từ DB:** OFFSET(48,90,50,48), NC(8%,12%), PROFIT(16%).
- **Cross-row refs:** gioăng = `khung_ngang_tren__width + khung_ngang_duoi__width +
  2×khung_dung_trai__width`; nẹp/keo tham chiếu `kinh_canh__width/height`.

---

## 11. Hướng dẫn mở rộng

| Muốn | Làm gì | Không sửa code |
|---|---|---|
| Thêm pattern tính SL | Thêm record `AL Quantity Calc Method` (calc_fn lambda) | ✅ |
| Thêm rule nghiệp vụ | Thêm `AL Calculation Rule` (CONSTANT/THRESHOLD/LOOKUP) | ✅ |
| Thêm pricing dimension | Thêm `AL Pricing Dimension` + `AL Variable Dimension Mapping` + Item Price field | ✅ |
| Thêm màu + hệ số giá | Thêm `AL Color Standard` (price_multiplier) → kích hoạt `multiplier_chain` qua FVB | ✅ (cần seed FVB) |
| Thêm dòng BOM | Thêm Bom Item vào Bom Set (formula width/height/qty) | ✅ |
| Thêm cost bucket / dòng cost template | Sửa `AL Cost Bucket` / `AL Cost Template` | ✅ |
| Bật FB pricing (FB-max) | Seed FVB: binding `aluminum_price_composite` / `composite_key_lookup` + source_config | ✅ (Phase D3) |
| Bật FB aggregate | Set `AL Cost Bucket.source_config` = `{"rows_source":"resolved","key_field":"cost_bucket","value_field":"line_total","key_value":"VL_NHOM",...}` | ✅ |
| Thêm source type mới | Thêm handler `@register_source` trong `fb_handlers.py` + khai báo `hooks.py fb_source_types` | — |

---

## 12. Ghi chú & item mở

1. **Scrap_pct** được inject vào context (B2) nhưng **chưa được dùng** bởi
   synthetic formula mặc định (`line_total = total_qty × unit_price`). Khi cần
   % hao hụt → thêm công thức vào Bom Item hoặc bật qua config, không hardcode.
2. **Color multiplier DARK ×1.08** cần FVB `multiplier_chain` để active (xem §10).
3. **Item Price composite key — product gap:** ERPNext `ItemPrice.check_duplicates`
   chặn item price thứ 2 cùng item/price_list (không biết `custom_pd_*`). Test fixture
   né bằng `ignore_validate` — **đang chờ Owner quyết** (patch validate qua doc_event
   hoặc chấp nhận import/raw).
4. **`test_phase_b_fbmax.py`** là test độc lập (frappe stub, chạy python3 thuần) —
   đã **tách sang `standalone_tests/`** (ngoài package alumglass/) → `bench
   run-tests --app alumglass` không collect. Chạy:
   `python3 -m pytest standalone_tests/test_phase_b_fbmax.py`.
5. Verify lại sau bất kỳ đổi seed: `bench --site alumglass-dev execute alumglass.run_test.main`.

---

## 13. Đối chiếu với v28.md — điểm khớp / lệch

> Tài liệu này mô tả **code đang chạy thật** trên `alumglass-dev` (bom_orchestrator.py
> 1058 dòng), không phải bản thiết kế lý tưởng. Đối chiếu với spec `v28.md` (v28.8):

### 13.1 Khớp với v28.md ✅

| Yêu cầu v28.md | Hiện trạng code | Chứng cứ |
|---|---|---|
| 7 phase B0–B7 (D.1) | ✅ Đúng | `bom_orchestrator.py` b0→b7 |
| Formula inject `{slug}__{field}` + synthetic unit_qty/total_qty/line_total (C.2.3) | ✅ Đúng | `b3_build_formulas` |
| Cross-row `items.X.Y` → `X__Y` (C.2.3) | ✅ Đúng | `normalize_global` + regex fallback |
| Cost Template qua FlexibleFormulaEngine + global_formulas (C.3.1) | ✅ Đúng | `b6_calculate_cost_template` |
| Composite key pricing trong engine B2 (nguyên tắc #28) | ✅ Đúng | `_fetch_composite_prices` (fallback active) |
| System variables từ DB — AL Variable Library + source_doctype/source_field (nguyên tắc #26) | ✅ Đúng | `_resolve_system_variables` |
| formula_fieldnames từ AL Bom Set (nguyên tắc #27) | ✅ Đúng | `b3_build_formulas` |
| DataSourceRegistry custom handlers (C.4) | ✅ Đúng | `fb_handlers.py` |
| safe_eval chống RCE (C.5 + H.5) | ✅ Đúng | `compile_expression` + `ast.Lambda` — nhánh DB calc_fn v28.8 **GIỮ `compile_expression`** (KHÔNG dùng `eval(fn, {"__builtins__": {}})` — sandbox myth bị `().__class__.__base__.__subclasses__()` escape; xem v28 §C.5/H.5). Thêm `_validate_calc_fn` AST whitelist defense-in-depth khi lưu |
| ConfigSnapshot audit (C.6, F.7) | ✅ Đúng | `b7_save_results` |

### 13.2 Lệch code vs spec — cần anh biết ⚠️

| # | Vấn đề | v28.md nói | Code thật làm | Đánh giá |
|---|---|---|---|---|
| 1 | **Golden 2C lệch +10 VND** | GIA_VAT = 22,717,289 (F.5.2) | GIA_VAT = **22,717,299** | ⚠️ Float precision (xem 13.3) |
| 2 | **NC_LD thêm height multiplier** | `NC_LD = NC_LD_PCT * TONG_VL` (C.3.2) | `NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` | ✅ Nâng cấp v28.7 — spec chưa cập nhật |
| 3 | **ban_le dùng rule thay roundup** | `roundup(H_mm/700,0)*n_panel` (F.4.1) | `lookup_rule('RULE-BANLE-QTY', H_mm)*n_panel` (tier 0-2100:2, 2101-2700:4, 2701+:4) | ✅ Data-driven tốt hơn hardcode |
| 4 | ~~lookup_calc_pattern KHÔNG có fallback~~ → **implemented hướng A (v28.8)** | Nguyên tắc #25: HYBRID DB-first + 12 `PATTERN_FORMULAS` code fallback | **HYBRID**: DB-first (giữ `compile_expression` safe_eval) + `PATTERN_FORMULAS` fallback (12 + 2 alias AREA≡AREA_M2, LENGTH_ONLY≡LENGTH_M) + pre-seed 13 record + negative cache. Phân quyền: role **AL Technical Admin** độc quyền sửa `calc_fn`, AL BOM Manager hạ xuống read | ✅ Implemented — `formula_handlers.py` + test `test_calc_pattern_hybrid.py` (6 case) |
| 5 | **Normalize khác cơ chế** | `DotToSubscriptTransformer` → `items['X']['Y']` → normalize (C.2.1) | `normalize_global` (regex) thẳng `X__Y`, **cố ý không** dùng DotToSubscriptTransformer (nested dict = literal 0 → lệch golden) | ✅ Quyết định đúng, có lý do kỹ thuật |
| 6 | **B6 on_error** | `on_error="raise"` (C.3.1) | `on_error="default", default_value=0` (bom không chết vì 1 lỗi) | ✅ Resilient hơn |
| 7 | **Item Price seed flat** | F.2.5: 15 dòng Item Price **theo composite key** (màu/xuất xứ/độ dày) | Seed chỉ 1 dòng flat/item (113,000/1,150,000...), **không có dòng theo màu** | ⚠️ Phase C/D — F.6.1 "DARK→118,000" chưa có trong data |

### 13.3 Giải trình golden +10 VND (vấn đề #1)

Không phải lỗi logic — là **độ chính xác số thực**, tích lũy qua các phép nhân:

| Dòng | v28.md (làm tròn từng bước) | Code thật (float liên tục) |
|---|---|---|
| do_ngang | `2.8961 × 113,000 = 327,259` | `2.896128 × 113,000 = 327,262` (**+3**) |
| VL_NHOM | 4,895,431 | 4,895,437 (+6 từ các phần lẻ) |
| TONG_VL | 14,062,811 | 14,062,817 (+6) |
| GIA_THANH | 17,803,518 | 17,803,526 (+8) |
| GIA_BAN | 20,652,081 | 20,652,090 (+9) |
| **GIA_VAT** | **22,717,289** | **22,717,299 (+10)** |

`run_test.py` chấp nhận delta < 1000 → PASS. Tài liệu này **ghi số code thật** (chuẩn hơn);
v28.md ghi số làm tròn tay. Nếu anh muốn khớp tuyệt đối với spec → cần round ở từng dòng
(`line_total = round(total_qty*unit_price)`), nhưng sẽ làm golden hiện tại đổi giá trị.

### 13.4 Độ chính xác bucket vs per-line (đọc bảng §9/§10)

Per-line hiển thị **làm tròn tới VND**; bucket B5 = **tổng full-precision line_total**
→ tổng các dòng hiển thị có thể lệch bucket **vài VND** (vd VL_NHOM 2C: 4,895,434
[hiển thị] vs 4,895,437 [bucket]). Số chính thức = bucket / cost template (đã verify
bằng dump thật), không phải tổng các dòng làm tròn.
