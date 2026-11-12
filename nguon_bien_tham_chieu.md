# NGUỒN BIẾN THAM CHIẾU — ALUMGLASS + FORMULA BUILDER

> **Ngày đo:** 2026-11-12 · **Phạm vi:** app `alumglass` (nhánh `main`) + app `formula_builder`
> **Mục đích:** trả lời chính xác *"biến này ở đâu ra, hàm nào đọc, file nào, khi nào có giá trị, khi nào chỉ là gợi ý"*.
> **Cách đọc:** mọi dẫn chứng ghi `file:dòng`. Số dòng đo tại thời điểm viết; nếu code đã đổi, tìm theo **tên hàm** (ổn định hơn số dòng).

---

## MỤC LỤC

1. [TL;DR — 3 tầng và 2 đường đọc](#1-tldr--3-tầng-và-2-đường-đọc)
2. [Bảng tổng hợp 21 nguồn biến](#2-bảng-tổng-hợp-các-nguồn-biến)
3. [Chi tiết từng nguồn](#3-chi-tiết-từng-nguồn)
4. [Luồng runtime khi tính giá (B0→B7)](#4-luồng-runtime-khi-tính-giá-b0b7)
5. [Luồng gợi ý biến khi gõ công thức](#5-luồng-gợi-ý-biến-khi-gõ-công-thức)
6. [Bảng ưu tiên & các điểm lệch preview/runtime](#6-bảng-ưu-tiên--các-điểm-lệch-previewruntime)
7. [Nhận xét — điểm mạnh, rủi ro, nợ kỹ thuật](#7-nhận-xét--điểm-mạnh-rủi-ro-nợ-kỹ-thuật)
8. [Hướng phát triển: Variable Catalog + Variable Profile](#8-hướng-phát-triển-variable-catalog--variable-profile)
9. [Ví dụ setting chi tiết + diễn giải cách hoạt động](#9-ví-dụ-setting-chi-tiết--diễn-giải-cách-hoạt-động)
10. [Lộ trình triển khai & checklist kiểm chứng](#10-lộ-trình-triển-khai--checklist-kiểm-chứng)
11. [Phụ lục A — Bản đồ file/hàm](#phụ-lục-a--bản-đồ-filehàm)
12. [Phụ lục B — 21 source_type của Formula Builder](#phụ-lục-b--21-source_type-của-formula-builder)
13. [Phụ lục C — Cấu trúc `al_bom_vars`](#phụ-lục-c--cấu-trúc-al_bom_vars)

---

## 1. TL;DR — 3 tầng và 2 đường đọc

### 1.1 Ba tầng

```
┌────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 1 — DỮ LIỆU CẤU HÌNH (ai khai báo biến, khai ở đâu)                    │
│                                                                            │
│  AL Variable Library ──► AL Variable Set ──► AL Bom Set.variable_set       │
│  AL Profile System (+ system_variables)                                    │
│  AL Product Type · AL Material Category · AL Quantity Calc Method          │
│  AL Cost Bucket · AL Cost Template (line_code) · AL Accessory Set          │
│  AL Pricing Dimension · AL Variable Dimension Mapping                      │
│  AL Slug Library · AL Calculation Rule (CONSTANT)                          │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │  được "nhìn thấy" qua
┌────────────────────────────────────▼───────────────────────────────────────┐
│ TẦNG 2 — NỀN TẢNG FORMULA BUILDER (nguồn biến tổng quát, resolve giá trị)  │
│                                                                            │
│  Formula Global Variable (CONSTANT / FORMULA / DB_QUERY)                   │
│  Formula Variable Binding (21 source_type) + scope doctype/field           │
│  Formula Set (FS-CODE.var) · Snapshot ($snap.field)                        │
│  FormulaEngine (DAG, topo sort, safe_eval)                                 │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │  được gọi bởi
┌────────────────────────────────────▼───────────────────────────────────────┐
│ TẦNG 3 — RUNTIME ALUMGLASS (ai gọi, theo thứ tự nào)                       │
│                                                                            │
│  BomOrchestrator B1..B6  ← tính giá thật                                   │
│  get_formula_context()   ← autocomplete / validate trong form              │
│  get_variable_set_for_bom() ← dialog "Tham số BOM" của Quotation Item      │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Hai đường đọc — và chúng KHÔNG hoàn toàn giống nhau

| | **Đường A — Tính giá** | **Đường B — Gợi ý / validate** |
|---|---|---|
| Điểm vào | `BomOrchestrator.run()` (`engine/bom_orchestrator.py:297`) | `alumglass.api.get_formula_context()` (`api/__init__.py:436`) |
| Gọi từ | nút **Tính giá** / preview trong dialog Quotation | `formula_setup.js`, `cost_template.js`, validate khi save |
| Nguồn chính | `al_bom_vars` + FB `get_live_context` + AL Variable Library + Profile System | FB `get_live_context` + 8 nhóm fallback AL |
| Giá trị | **giá trị thật** đem đi tính | **giá trị live / default / "—"** để gợi ý |
| Hệ quả | quyết định ra tiền | chỉ ảnh hưởng người dùng thấy biến nào, và validate có chặn hay không |

> 🔴 Điều quan trọng nhất cần nhớ: **biến hiện trong autocomplete ≠ biến chắc chắn có giá trị lúc tính**.
> Nhiều biến chỉ là "gợi ý" (Row Literals, Common Vars, Slug) và giá trị thật do engine inject ở B2/B3.

### 1.3 "Muốn thêm biến mới thì thêm ở đâu?"

| Nhu cầu | Thêm ở | Ai dùng |
|---|---|---|
| Hằng số dùng chung nhiều công thức | `Formula Global Variable` (CONSTANT) | runtime + autocomplete + `$TEN` |
| Biến theo hệ profile (offset, NC…) | `AL Variable Library` (is_system=1) + `source_doctype/source_field` | runtime B1 + autocomplete |
| Biến người dùng nhập khi báo giá | `AL Variable Library` (is_system=0) → gán vào `AL Variable Set` | dialog Quotation |
| Giá trị đọc từ 1 bản ghi liên kết (bất kỳ doctype) | `Formula Variable Binding` + `linked_doctype_field` | FB `get_live_context` → runtime |
| Tổng/đếm trên dòng (SUMIF) | `AL Cost Bucket.source_config` + `aggregate_from_items` | B5 |
| Biến mới xuất hiện theo từng dòng BOM | `AL Quantity Calc Method.input_vars` + `AL Bom Item.input_vars` | B2/B3 |
| Biến chéo dòng `items.slug.field` | `AL Slug Library` + `AL Bom Item.slug` | B3 (normalize) + autocomplete |
| Tra giá theo nhiều chiều | `AL Pricing Dimension` + `AL Variable Dimension Mapping` | B2 + `aluminum_price_composite` |
| Biến chỉ để hiển thị/ghi chú | `AL Bom Item` fields (supplier_location, note…) | B2 row literal |

---

## 2. Bảng tổng hợp các nguồn biến

Ký hiệu: **R** = có mặt lúc tính giá; **S** = có mặt trong gợi ý/validate.

| # | Nguồn | Nơi khai báo | Tên biến là gì | Hàm đọc chính | File:dòng | R | S |
|---|---|---|---|---|---|---|---|
| 1 | System Variable | `AL Variable Library` (`is_system=1`) | `var_name` | `resolve_system_variable_values()` | `al_bom_engine/system_variable_resolver.py:74` | ✅ | ✅ |
| 2 | User Variable (Library) | `AL Variable Library` (`is_system=0`) | `var_name` | `_resolve_user_variable_defaults()` | `engine/bom_orchestrator.py:546` | ✅ (default) | ✅ |
| 3 | Variable Set | `AL Variable Set` + `AL Variable Set Item` | `item.variable` | `get_variable_set_for_bom()` | `api/__init__.py:736` | ❌ (chỉ dialog) | ✅ |
| 4 | Profile System — field | `AL Profile System.offset_*` | theo `AL Variable Library.source_field` | `resolve_system_variable_values()` | `system_variable_resolver.py:91-104` | ✅ | ✅ |
| 5 | Profile System — child override | `AL Profile System.system_variables` | `row.variable` | `resolve_system_variable_values()` | `system_variable_resolver.py:106-128` | ✅ | ✅ |
| 6 | Product Type | `AL Product Type.nc_pct`, `nc_ld_rate`, `profit_margin` | theo `source_doctype/source_field` | `resolve_source_record_names()` | `system_variable_resolver.py:47` | ✅ | ✅ |
| 7 | Material Category | `AL Material Category.default_scrap_pct`, `has_weight` | `{slug}__scrap_pct`, `{slug}__has_weight` | `b2_prefetch_master_data()` | `engine/bom_orchestrator.py:946-958, 1095-1115` | ✅ | ✅ (row literal) |
| 8 | Calc Pattern vars | `AL Quantity Calc Method.input_vars` + `AL Bom Item.input_vars` | `{slug}__{tên_biến}` | `b3_build_formulas()` | `engine/bom_orchestrator.py:2000-2068` | ✅ | ✅ (một phần) |
| 9 | Bom Item formula fields | `AL Bom Item.width/height/qty/...` | `{slug}__{field}` | `b3_build_formulas()` | `engine/bom_orchestrator.py:2071-2115` | ✅ | ✅ |
| 10 | Accessory Item | `AL Accessory Set.items` | `{slug}__qty/unit_price/...` | `_load_accessories()` | `engine/bom_orchestrator.py:799` | ✅ | ❌ |
| 11 | Cost Bucket | `AL Cost Bucket.bucket_code` | `bucket_code` | `b5_aggregate_cost_buckets()` + `_resolve_cost_buckets_via_fb()` | `engine/bom_orchestrator.py:2315, 2341` | ✅ | ✅ |
| 12 | Cost Template line | `AL Cost Template Item.line_code` | `line_code` (định nghĩa tuần tự) | `b6_calculate_cost_template()` | `engine/bom_orchestrator.py:2432` | ✅ | ✅ |
| 13 | Formula Global Variable | `Formula Global Variable` | `var_name` (+ `$var_name`) | `VariableResolver._get_global()` / `get_all_global_variables()` | `formula_builder/api/variable_resolver.py:220`; `formula_builder/api/global_variable_cache.py` | ✅ | ✅ |
| 14 | Formula Variable Binding | `Formula Variable Binding` | `variable_name` | `get_live_context()` → `get_scope_bindings()` + `resolve_bindings_with_deps()` | `formula_builder/api/formula_builder.py:275`; `api/binding_scope.py:139`; `api/data_source_registry.py:1369` | ✅ | ✅ |
| 15 | Row Literal | engine tự inject | `weight_per_unit`, `unit_price`, `glass_thick`… | `b2_prefetch_master_data()` | `engine/bom_orchestrator.py:1072-1133` | ✅ | ✅ (danh sách tay) |
| 16 | Common BOM Var | không có record — danh sách tay | `W_mm`, `H_mm`, `n_panel`, `TONG_M2`… | `get_formula_context()` nhóm 6 | `api/__init__.py:575-588` | ⚠️ chỉ khi user nhập / có trong `al_bom_vars` | ✅ |
| 17 | Slug / cross-row | `AL Slug Library` | `items.{slug}.{field}` | `_normalize_items_ref()` + `normalize_global()` | `engine/bom_orchestrator.py:2145`; `formula_builder/table_formula_builder.py:81` | ✅ | ✅ |
| 18 | Formula Set output | `Formula Set` | `FS-CODE.var` | `VariableResolver._get_formula_set_output()` | `formula_builder/api/variable_resolver.py:333` | ✅ | ✅ |
| 19 | Snapshot | cache `formula_snapshot:{doctype}:{docname}` | `$snap.field` | `VariableResolver._get_snapshot()` | `formula_builder/api/variable_resolver.py:327` | ✅ | ✅ |
| 20 | AL Calculation Rule CONSTANT | `AL Calculation Rule` | `var_name.replace("_","-")` | `_resolve_system_variables()` fallback cuối | `engine/bom_orchestrator.py:691-701` | ✅ (fallback) | ❌ |
| 21 | Pricing Dimension Mapping | `AL Variable Dimension Mapping` | `variable_name` | `_get_dim_fieldnames()` / handler `aluminum_price_composite` | `engine/bom_orchestrator.py:1146`; `fb_handlers.py:53` | ✅ | ✅ (cờ `is_pricing_dimension`) |

---

## 3. Chi tiết từng nguồn

### 3.1 `AL Variable Library` — nguồn gốc của system/user variable

**Schema** (`al_master_data/doctype/al_variable_library/al_variable_library.json`):

| Field | Ý nghĩa |
|---|---|
| `var_name` (autoname) | tên biến dùng trong công thức |
| `var_label` | nhãn hiển thị |
| `var_type` | `Float · Int · Data · Select · Link · Check · Currency · Percent` |
| `category` | nhóm để gợi ý |
| `is_system` | 1 = hệ thống tự resolve; 0 = người dùng nhập |
| `link_doctype` / `select_options` | cấu hình cho kiểu Link/Select |
| `source_doctype` / `source_field` | **chỉ system var**: đọc field nào của doctype nào |
| `default_value` | fallback |
| `description` | mô tả |

**Ba cách nguồn này được đọc:**

1. **Runtime — system var** (`engine/bom_orchestrator.py:576` `_resolve_system_variables`):
   - dò field Link trên `AL Bom Set` trỏ tới `source_doctype` → lấy tên bản ghi;
   - đọc `source_field` của bản ghi đó (`system_variable_resolver.py:91-104`);
   - **override** bằng child table `AL Profile System.system_variables` (`:106-128`);
   - nếu vẫn thiếu: `default_value` (`bom_orchestrator.py:684-689`);
   - nếu vẫn thiếu: `AL Calculation Rule` có `rule_type=CONSTANT` (`:691-701`).
2. **Runtime — user var** (`bom_orchestrator.py:546`): chỉ điền `default_value` khi user chưa nhập.
3. **Gợi ý** (`api/__init__.py:515-548`): nhóm "System Variables" và "User Variables".

**Lưu ý thực chiến:**
- `var_type=Percent` → B1 chuẩn hoá `8 → 0.08` nếu `abs(value) > 1`; tên có hậu tố `_PCT`, `_MARGIN`, `_RATE` cũng bị chuẩn hoá (`bom_orchestrator.py:209, 514-544`). Giá trị đúng bằng `1` là ca mơ hồ — có cảnh báo.
- Library **không** tự động là "nguồn duy nhất": cùng tên có thể bị `Formula Global Variable` hoặc FVB ghi đè (xem §6).

---

### 3.2 `AL Variable Set` + `AL Variable Set Item` — bộ biến của một sản phẩm

**Schema:**

| `AL Variable Set` | `AL Variable Set Item` (child) |
|---|---|
| `set_code` (autoname), `set_name` | `variable` → Link `AL Variable Library` |
| `product_type` → `AL Product Type` | `var_label`, `var_type` (fetch từ Library) |
| `is_active` | `link_doctype`, `select_options` |
| `items` (Table) | `default_value` (**override**), `sort_order`, `is_required` |

**Đường nối runtime/UI:**

```
Quotation Item.al_bom
      └► AL BOM.bom_set
            └► AL Bom Set.variable_set
                  └► AL Variable Set.items ──► AL Variable Library
```

- **Dialog Quotation** gọi `get_variable_set_for_bom(bom_code)` (`api/__init__.py:736`) → trả `variables` + `glass_groups` + `color_groups`. JS `_load_variable_set()` (`alumglass/doctype/overrides/quotation.js:579`) render control theo `var_type` (`_var_to_field`, `:859`), lưu vào `Quotation Item.al_bom_vars` (`_save`, `:1538`).
- **Autocomplete trong form** dùng `_inject_variable_set_vars()` (`api/__init__.py:705`), tự dò field Link `AL Variable Set` trên doctype hiện tại, hoặc đi 1 hop qua `AL Bom Set` (`_resolve_variable_set_name`, `:674`).
- **Runtime không đọc Variable Set.** Engine chỉ đọc `al_bom_vars` (giá trị user đã nhập). Variable Set là **hợp đồng UI**, không phải nguồn giá trị.
- `AL Accessory Set.variable_set` **có field nhưng không được dùng ở đâu** (chỉ `AL Bom Set.variable_set` được đọc). Đây là field chết cần dọn hoặc nối.

**Hệ quả cần biết:** doctype không có field Link → Variable Set (ví dụ `AL Cost Template`) **không** nhận được bộ biến riêng; nó thấy **toàn bộ** user var trong Library (nhóm 3 của `get_formula_context`). Đây là nguồn gây nhiễu lớn nhất khi gõ công thức ở Cost Template.

---

### 3.3 `AL Profile System` + `AL Profile System Variable` — override theo hệ profile

**Schema:** `offset_frame`, `offset_glass`, `offset_fixed`, `offset_crossbar` (Float) + child `system_variables`:

| Child field | Ý nghĩa |
|---|---|
| `variable` → `AL Variable Library` | tên biến |
| `value` (Data) | giá trị override |
| `is_active` | bật/tắt |

**Hàm dùng chung — `al_bom_engine/system_variable_resolver.py`:**

| Hàm | Việc |
|---|---|
| `resolve_source_link_fields(doctype)` `:28` | quét meta, trả `{options_doctype: fieldname}` — field Link **đầu tiên** trỏ tới doctype |
| `resolve_source_record_names(doctype, docname, system_vars)` `:47` | từ tên bản ghi (vd `AL Bom Set`) → tên bản ghi nguồn (vd `AL Profile System`) |
| `resolve_system_variable_values(source_records, system_vars)` `:74` | đọc `source_field`, rồi **override** bằng child `system_variables` |

**Hai nơi gọi — nay đã thống nhất:**
- runtime: `bom_orchestrator._resolve_system_variables()` (`:576`);
- gợi ý: `api._resolve_doc_values()` (`api/__init__.py:380`).

**Còn hardcode (đã xác nhận):**
- `api/__init__.py:867-875` map cứng `offset_frame→OFFSET_FRAME`, `offset_crossbar→OFFSET_DO_NGANG`… khi overlay giá trị profile vào `default_value` của dialog.
- `resolve_source_link_fields` chọn **field Link đầu tiên**; nếu 1 doctype có 2 field cùng trỏ `AL Profile System` thì có thể chọn sai — chưa có cấu hình ưu tiên.

---

### 3.4 `AL Product Type`

Field: `nc_pct`, `nc_ld_rate`, `profit_margin`. **Không phải tên biến** — tên biến do `AL Variable Library` quyết định qua cặp `source_doctype="AL Product Type"` + `source_field="nc_pct"`.

Ví dụ record Library:

```
var_name = NC_SX_PCT
source_doctype = AL Product Type
source_field = nc_pct
```

Engine dò field Link `product_type` trên `AL Bom Set` (`AL Bom Set.product_type`) → đọc `nc_pct` của bản ghi `AL Product Type` tương ứng.

⚠ Đây là chỗ dễ nhầm: đổi `source_field` không đổi tên biến; đổi `var_name` là đổi tên dùng trong công thức.

---

### 3.5 `AL Material Category` — row literal `scrap_pct`, `has_weight`

- `default_scrap_pct` → `row_literals[slug]["scrap_pct"]` (`bom_orchestrator.py:1103`).
- B3 chỉ nhân hao hụt vào `total_qty` khi `AL Bom Set.apply_scrap_pct = 1` (`:1997-2107`):
  `total_qty = unit_qty × qty × (1 + scrap_pct/100)`.
- `has_weight` chỉ phục vụ hiển thị cột trọng lượng (`:1104-1106`), không tham gia công thức.
- Giá trị được inject vào context dưới `{slug}__scrap_pct` (B3 `:2026-2030`).

---

### 3.6 `AL Quantity Calc Method.input_vars` + `AL Bom Item.input_vars`

**Luồng:**
1. `AL Quantity Calc Method.input_vars` là **danh sách tên biến phụ** (JSON list), ví dụ `["depth", "panel_count"]`.
2. Khi lưu `AL Bom Item`, hook `backfill_input_vars` (`al_bom_engine/doctype/al_bom_item/al_bom_item.py:41`) đảm bảo `AL Bom Item.input_vars` (JSON object) có đủ key.
3. B3 (`bom_orchestrator.py:2000-2068`):
   - đọc `pattern_input_vars` 1 lần cho tất cả pattern;
   - với mỗi dòng, thứ tự ưu tiên giá trị: **`line.input_vars` → `self.inputs` (user/global) → `row_literals` → 0**;
   - inject thành `{slug}__{var}` và truyền vào `lookup_calc_pattern(..., { 'depth': slug__depth })`.
4. `_POSITIONAL = {width, height, weight_per_unit}` không inject qua dict — đã là tham số vị trí.

**Điểm cần lưu ý:** đây là nguồn **duy nhất** cho biến phụ của pattern; nếu biến không có trong `input_vars` của pattern, nó không được truyền — dù có trong Library.

---

### 3.7 `AL Bom Item` — field công thức và biến `{slug}__{field}`

- `FORMULA_FIELDS = ("width", "height", "qty", "show_condition")` + `CONDITION_FORMULA_FIELDS = ("item_condition_formula",)` (`al_bom_item.py:10-13`).
- B3 dùng `DEFAULT_FORMULA_FIELDS = [width, height, qty, show_condition, item_condition_formula, rule_input_expr]` nếu `AL Bom Set.formula_fieldnames` rỗng (`bom_orchestrator.py:239`).
- Mỗi field có công thức → sinh formula tên `{slug}__{field}` (`:2071-2084`).
- Sinh thêm 3 formula hệ thống cho mỗi dòng (`:2085-2115`):
  - `{slug}__unit_qty = lookup_calc_pattern(...)`
  - `{slug}__total_qty = unit_qty × qty [× (1+scrap%)]`
  - `{slug}__line_total = total_qty × unit_price`
- Cuối B3, mirror toàn bộ `{slug}__{field}` thành dict lồng `inputs["items"]` (`:2117-2126`) để công thức `items.X.Y` chạy được.

⚠ `rule_input_expr` được B3 coi là formula field, nhưng `AL Bom Set._validate_child_formulas()` **không** validate nó bằng FormulaValidator (chỉ validate `FORMULA_FIELDS` + `CONDITION_FORMULA_FIELDS`); engine lại parse nó bằng regex `items.slug.field` (`:1917-1933`). Đây là vùng "gõ được nhưng không được kiểm".

---

### 3.8 `AL Accessory Set` + `AL Accessory Item` — phụ kiện thành dòng BOM

`_load_accessories()` (`bom_orchestrator.py:799`) biến mỗi accessory item thành 1 dòng `bom_items`:

| Nguồn | Thành biến/dòng |
|---|---|
| `slug` | khoá dòng |
| `item_code` | mã item |
| `qty_formula` | công thức số lượng (chạy qua FormulaEngine ở B4) |
| `qty` | số lượng cố định nếu không có `qty_formula` |
| `unit_price` | giá ghi đè trực tiếp (không cần Item Price) |
| `calc_pattern` | mặc định `COUNT` |
| `cost_bucket` | mặc định `VL_PK` |
| `default_color` | tham gia nhóm màu |
| `supplier_location`, `install_position`, `note` | metadata hiển thị |

Bộ phụ kiện được chọn: `al_bom_vars.accessory_set` (override) → `AL Bom Set.default_accessory_set`.
Danh mục màu phụ kiện lấy từ **named constant** `DEFAULT_ACCESSORY_CATEGORY` (`fb_config.get_named_constant`, `al_bom_engine/fb_config.py:10`) — bản thân giá trị này là 1 `Formula Variable Binding` source_type `constant`.

---

### 3.9 `AL Cost Bucket` — mã bucket là biến, `source_config` là cách gom

**Schema:** `bucket_code`, `bucket_role` (`LEAF`/`AGGREGATE`), `source_type`, `source_config` (JSON), `depends_on`, `report_group`, `sort_order`.

**Runtime:**
- `b5_aggregate_cost_buckets()` (`:2315`) mặc định cộng `line_total` theo `cost_bucket` bằng Python.
- Nếu bucket có `source_type = "aggregate_from_items"` **và** `source_config` không rỗng → `_resolve_cost_buckets_via_fb()` (`:2341`) tạo binding tạm và gọi `resolve_all_bindings_batch`, với `pre_resolved["rows"] = [{cost_bucket, line_total}]`.
- Bucket khai `source_type` khác → cảnh báo `bucket_source_type_chua_ho_tro` và quay về cộng Python (`:2379-2390`).
- `bucket_code` xuất hiện trong autocomplete ở nhóm `Cost Bucket` (`api/__init__.py:493-502`).

**Ví dụ `source_config` cho 1 bucket LEAF:**

```json
{
  "rows_source": "resolved",
  "rows_var": "rows",
  "key_field": "cost_bucket",
  "key_value": "VL_NHOM",
  "value_field": "line_total",
  "aggregate": "sum",
  "default_value": 0
}
```

---

### 3.10 `AL Cost Template` + `AL Cost Template Item` — nơi định nghĩa biến dẫn xuất

**Schema:** `line_code`, `line_label`, `calc_formula`, `cost_bucket`, `is_subtotal`, `is_final_price`, `is_pre_vat_price`, `show_on_quotation`.

**Runtime B6** (`bom_orchestrator.py:2432`):
1. Lấy snapshot cost template (hoặc doc nếu có `_cost_template` override).
2. Mỗi `line_code` có `calc_formula` → 1 formula trong `global_formulas`.
3. Quét token `[A-Z][A-Z0-9_]` trong công thức để tìm bucket được tham chiếu; set default `0` cho bucket chưa có giá trị (`:2477-2491`).
4. Context = `self.inputs` ⊕ `self.buckets` (`extra_context`), rồi `engine.calculate({**extra_context, **self.inputs})`.
5. `is_final_price` → `gia_vat`; `is_pre_vat_price` → giá trước VAT (`_resolve_final_price`, `:2565`).

**Autocomplete/validate:** `get_formula_context("AL Cost Template", None)` → `_build_known_names()` (`al_cost_template.py:63`). Vì `docname=None`:
- không có Variable Set;
- vẫn có **tất cả** user var trong Library;
- vẫn có Cost Bucket, System Var, Global Var, Row Literal, Common Var, FVB, Slug.

**Preview** (`preview_cost_template`, `al_cost_template.py:122`) dùng `compile_expression(...).eval(ctx)` với `BASE_FUNCS` + 3 hàm custom — cố ý khớp runtime B6.

---

### 3.11 `Formula Global Variable` (formula_builder)

**Schema:** `var_name` (autoname), `label`, `var_type`, `unit`, `category`, `value_source` (`CONSTANT`/`FORMULA`/`DB_QUERY`), `constant_value`, `formula_expr`, `db_query_doctype`, `db_query_field`, `db_query_filters`, `is_active`.

**Ba đường đọc:**
1. **Runtime B1** — `get_all_global_variables()` (cache Redis 60s) → `self.inputs[var_name]` (`bom_orchestrator.py:389-396`).
2. **Runtime công thức** — `VariableResolver._get_global()` (`variable_resolver.py:220`) khi gặp tên thuần hoặc `$name`.
3. **Gợi ý** — `get_formula_context` nhóm 4 + `get_live_context` bước 7 (chỉ `CONSTANT`).

**Thứ tự ưu tiên nội bộ của `_get_global`:**
- `CONSTANT` → cast theo `var_type`;
- `FORMULA` → chạy `FormulaEngine` với các CONSTANT khác làm input;
- `DB_QUERY` → chỉ chạy nếu doctype nằm trong `Formula Builder Settings.db_query_allowed_doctypes` (`variable_resolver.py:75-82, 254-273`); nếu không → ghi Error Log và trả `None`.

**Điểm cần biết:** B1 nạp **mọi** Global Variable vào `inputs`, kể cả `FORMULA`/`DB_QUERY` và **cả record `is_active=0`** — vì `get_all_global_variables()` (`formula_builder/api/global_variable_cache.py:29-45`) chỉ query `var_name, constant_value`, **không lọc `is_active`**. Với biến không phải CONSTANT, `constant_value` thường rỗng → B1 ghi `inputs[var_name] = ""`. Vì vậy một Global Variable trùng tên với system var có thể **che** giá trị system var (chuỗi rỗng vẫn là "đã có trong inputs"), và biến đã tắt vẫn có mặt. Đường `$NAME` thì khác: `_get_global` lọc `is_active=1` và **có** đánh giá FORMULA/DB_QUERY.

---

### 3.12 `Formula Variable Binding` — lớp resolve chung của Formula Builder

Đây là nguồn **quan trọng nhất** của tầng nền tảng. Một binding gồm:

| Field | Ý nghĩa |
|---|---|
| `variable_name`, `variable_label` | tên/nhãn |
| `source_type` | 1 trong 21 loại (Phụ lục B) |
| `source_config` (JSON) | cấu hình theo từng loại |
| `resolve_priority` | thứ tự resolve (thấp trước) |
| `applies_to_doctype` / `applies_to_field` | phạm vi áp dụng |
| `is_global` | cờ hiển thị "toàn cục" |
| `data_type`, `default_value` | kiểu và fallback |
| `is_active` | bật/tắt |

**Luật scope — một nơi duy nhất:** `formula_builder/api/binding_scope.py`

| Binding `applies_to_doctype` / `applies_to_field` | Áp dụng khi nào |
|---|---|
| `""` / `""` | mọi nơi (global) |
| `"AL Bom Set"` / `""` | mọi field của AL Bom Set |
| `"AL Bom Set"` / `"width"` | chỉ field `width` (nếu caller truyền field) |
| `""` / `"width"` | **không** áp cho doctype cụ thể nào (chỉ khi caller không có doctype) |

**Đường resolve của `get_live_context`** (`formula_builder/api/formula_builder.py:275`):

```
scope JSON {current_doctype, current_docname, fieldname?}
   │
   ├─1 get_scope_bindings(doctype, field)        ← binding_scope.py:139
   │      DB prefilter: is_active=1, applies_to_doctype in ["", doctype]
   │      Python filter: global / doctype / doctype+field
   │
   ├─2 resolve_bindings_with_deps(bindings, doc) ← data_source_registry.py:1369
   │      - dựng graph phụ thuộc từ source_type="computed".dependencies
   │      - topological sort (Kahn), lỗi chu trình → fallback sort theo priority
   │      - gọi handler từng binding, lỗi → default_value
   │
   ├─3 variables = binding đã resolve (kèm is_global, source_type)
   │
   ├─4 + field scalar của doc hiện tại (source="field")
   │
   ├─5 + crossTables = meta các child table + _rows (line_ref, idx, label)
   │
   └─6 + Formula Global Variable CONSTANT (source_type="global_variable")
```

**AlumGlass dùng binding ở 3 chỗ:**

| Chỗ | Binding | Cách gọi |
|---|---|---|
| Runtime B1 | system var đã seed (`linked_doctype_field`) + global | `_resolve_fb_context()` (`bom_orchestrator.py:703`) → `get_live_context(scope="AL Bom Set")` |
| Runtime B2 | `COMPOSITE_MATERIAL_PRICE` (`aluminum_price_composite`) | `_get_pricing_bindings()` (`:1292`) → `get_scope_bindings_multi(("Quotation Item","AL Bom Item"))` |
| Named constant | `DEFAULT_ACCESSORY_CATEGORY` (`constant`) | `fb_config.get_named_constant()` (`fb_config.py:10`) |

**Seed tự động:**
- `install_composite_pricing_binding()` — `setup/install_fb_bindings.py:79`; chạy mỗi migrate (`hooks.py:195-236`). `price_list` lấy động từ `Selling Settings.selling_price_list` qua `_default_price_list()`.
- `install_named_constant_bindings()` — `:139`.
- Patch `v28_11/seed_fvb_full_from_variable_library.py` — seed mọi System Variable có `source_doctype/source_field` thành binding `linked_doctype_field`, scope `AL Bom Set`. Chỉ seed khi `AL Bom Set` có field Link trỏ đúng `source_doctype`.

**Vì sao B1 gọi FB trước rồi mới tới Library?**
`bom_orchestrator.py:398-415`: FB-first để biến đã seed không phải resolve 2 lần; legacy `_resolve_system_variables(fill_missing_only=True)` chỉ điền biến FB chưa phủ.

---

### 3.13 Row Literal — engine tự sinh, không có record cấu hình

Với **mỗi** dòng BOM, B2 dựng `row_literals[slug]` (`bom_orchestrator.py:1072-1133`) gồm:

| Key | Nguồn |
|---|---|
| `weight_per_unit` | `Item.weight_per_unit` |
| `unit_price` | `Item Price` (composite key) hoặc `AL Accessory Item.unit_price` |
| `calc_pattern` | `AL Bom Item.calc_pattern` |
| `glass_thick`, `glass_type` | `AL Glass Master` (theo mã kính đã resolve) |
| `item_code` | mã thực tế sau rule/kính |
| `scrap_pct` | `AL Material Category.default_scrap_pct` |
| `has_weight` | `AL Material Category.has_weight` |
| `color` | màu đã resolve theo vị trí |
| `supplier_location`, `install_position`, `cut_angle`, `note` | metadata từ dòng |

B3 inject các key này vào context dưới `{slug}__{key}` (`:2026-2030`) trước khi build công thức.

**Autocomplete** chỉ liệt kê 9 tên tay ở nhóm "Row Literals" (`api/__init__.py:561-573`) — không bao gồm các key metadata như `supplier_location`, `note`. Đây là danh sách **hardcode**, thêm literal mới phải sửa cả 2 nơi.

---

### 3.14 Common BOM Variable + `al_bom_vars` — biến người dùng nhập

**Danh sách "common" đang hardcode trong `api/__init__.py:575-588`:**

`W_mm`, `H_mm`, `n_panel`, `TransomHeight_mm`, `SideLiteWidth`, `SideLiteHeight`, `installation_height_m`, `TONG_M2`.

⚠ **Không có engine nào tự tính các biến này.** Chúng chỉ là tên gợi ý; giá trị phải đến từ:
- `AL Variable Set` (user var) → dialog → `al_bom_vars`; hoặc
- `extra_vars`; hoặc
- FVB (`constant`/`computed`).

Nếu user gõ `W_mm` mà không khai ở đâu → lúc tính sẽ thiếu biến (engine `on_error="default"` có thể trả 0/None tùy cấu hình).

**Cấu trúc `al_bom_vars`:** xem Phụ lục C. Các key engine đọc:
- top-level: user var (ghi đè mạnh nhất);
- `extra_vars`: bảng "Biến mở rộng";
- `glass_master`, `glass_master_map`: kính global / theo vị trí;
- `aluminum_color`, `color_master_map`: màu global / theo vị trí;
- `_accessory_set`, `_profile_system`, `_cost_template` (và alias `accessory_set`).

---

### 3.15 Slug / cross-row `items.slug.field`

Đây là cơ chế user gọi là "gõ biến chéo slug". Ba mảnh:

1. **UI gợi ý** — `formula_builder.js` quét các child table của **doctype cha**, sinh 2 dạng (`formula_builder.js:414-446`):
   - `items[0].width`
   - `items.kinh_tren.width` (slug lấy từ `id_field`; AlumGlass cấu hình `id_field: "slug"` trong `formula_setup.js:164,188-219`)
2. **Validate** — `formula_validate.py:29` `normalize_cross_row()` đổi `items.slug.field → slug__field`; `build_known_names()` thêm `{slug}__{field}` cho mọi slug × `FORMULA_FIELDS`.
3. **Runtime** — `bom_orchestrator._normalize_items_ref()` (`:2145`) dùng **cùng** `normalize_global()` của FB; sau đó B3 mirror `{slug}__{field}` thành dict lồng `inputs["items"]`.

Ngoài ra `VariableResolver.ChildTableRows` (`variable_resolver.py:14`) cho phép truy cập theo slug trong các API FB: `items.canh_trai.qty`, `items['canh_trai']`, `items[0]`.

**Giới hạn hiện tại:**
- Chỉ gợi ý được các dòng **đã có** trong grid (đọc từ `frm.doc`).
- Chỉ gợi ý field của child table, không gợi ý field của doctype liên kết của dòng.
- `id_field` phải khai trong JS (`_afbSlugFieldMap`); nếu quên → fallback `line_ref` (AlumGlass không dùng `line_ref`).

---

### 3.16 Formula Set, Snapshot, `$` prefix

- **Formula Set**: `FS-CODE.var` → `VariableResolver._resolve_formula_set_output()` (`variable_resolver.py:333`). Đọc `Formula Set Line`, chạy `FormulaEngine` với `build_full_context(ctx)`. Dùng khi 1 dòng BOM chọn `AL Bom Item.formula_set`.
- **Snapshot**: `$snap.field` → `_get_snapshot()` (`:327`), đọc cache `formula_snapshot:{doctype}:{docname}`. Giá trị do luồng publish snapshot ghi vào cache (không phải doctype).
- **Global prefix**: `$NAME` → `_get_global()`.

⚠ `$` và `FS-` chỉ hoạt động trong ngữ cảnh có `ScopeContext` (VariableResolver). B3/B6 dùng `FormulaEngine` trực tiếp, **không** đi qua `VariableResolver` — nên `$TEN`/`FS-CODE.var` **không** resolve trong công thức BOM/Cost Template trừ khi đã có biến cùng tên trong `inputs`.

---

### 3.17 `AL Calculation Rule` CONSTANT — fallback cuối

Khi system var không resolve được từ Library/profile/default:
`var_name.replace("_", "-")` → tìm `AL Calculation Rule` cùng tên; nếu `rule_type = CONSTANT` → lấy `constant_value` (`bom_orchestrator.py:691-701`).

Đây là di sản backward-compat; **không** xuất hiện trong autocomplete.

---

### 3.18 Pricing Dimension + Variable Dimension Mapping

Không phải "biến công thức" theo nghĩa thông thường, nhưng là nguồn quyết định **biến nào là chiều tra giá**:

- `AL Pricing Dimension`: `dimension_code`, `dimension_type`, `link_doctype`, `custom_fieldname` (tên cột trên `Item Price`), `represents_color`, `is_required_for_price`.
- `AL Variable Dimension Mapping`: `variable_name` → `pricing_dimension`, `material_category`, `price_multiplier`, `is_active`.

**Được dùng bởi:**
- `bom_orchestrator._get_dim_fieldnames()` (`:1146`) — map biến → cột Item Price;
- `_get_pricing_bindings()` (`:1292`) — lọc binding pricing;
- `fb_handlers.aluminum_price_composite` (`fb_handlers.py:53`) — 2 mode `exact_match` / `multiplier_chain`;
- `api/__init__.py:619-623` và `:890-894` — gắn cờ `is_pricing_dimension` cho từng biến để dialog không bắt buộc nhập.

Thêm 1 chiều giá mới = thêm 1 `AL Pricing Dimension` + 1 dòng Mapping + (nếu cần) field trên `Item Price`. Không sửa code.

---

## 4. Luồng runtime khi tính giá (B0→B7)

### 4.1 Sơ đồ

```
calculate_bom(quotation_item)                       api/__init__.py:6
  └─ BomOrchestrator(qi).run()                      engine/bom_orchestrator.py:297
       │
       B0 version pinning                           :311
       │   Quotation Item.al_bom → AL BOM.current_version → AL BOM Version
       │
       B1 gather inputs                             :368
       │   1.1 al_bom_vars.extra_vars
       │   1.2 Formula Global Variable (CONSTANT/…)
       │   1.4 get_live_context(scope AL Bom Set)  ← FVB
       │   1.3 legacy AL Variable Library (fill-missing)
       │   1.4b AL Profile System.system_variables (override)
       │   1.5 al_bom_vars top-level (user)
       │   1.5c nếu có _profile_system override → resolve lại toàn bộ system var
       │   1.6 default_value user var
       │   1.7 chuẩn hoá %
       │
       B2 prefetch master data                      :857
       │   snapshot AL Bom Set → bom_items
       │   + _load_accessories()
       │   + Item weights / Item Price (composite) / Glass Master
       │   + Material Category / Dynamic Item Rule
       │   + row_literals[slug]
       │
       B3 build formulas                            :1967
       │   {slug}__width/height/qty/...
       │   {slug}__unit_qty/total_qty/line_total
       │   inputs["items"] = {slug: {field: value}}
       │
       B4 FormulaEngine calculate                   :2181
       │
       B5 cost buckets                              :2315
       │   FB aggregate_from_items nếu có source_config
       │   else cộng line_total theo cost_bucket
       │
       B6 cost template                             :2432
       │   FormulaEngine với inputs ⊕ buckets
       │   → cost_result, gia_vat, gia_ban
       │
       B7 save results                              :2588
```

### 4.2 Bảng ưu tiên của B1 (đọc theo thứ tự GHI)

Cột "Ghi đè?" cho biết lớp đó có quyền thay giá trị đã có hay chỉ điền khi thiếu. **Lớp ghi sau thắng** (trừ lớp "chỉ khi thiếu").

| Thứ tự ghi | Lớp | Ghi đè? | Code |
|---|---|---|---|
| 1 | `al_bom_vars.extra_vars` | — (lớp đầu) | `:379-380` |
| 2 | `Formula Global Variable` (mọi record, kể cả inactive) | **ghi đè** | `:389-396` |
| 3 | FB `get_live_context` (binding + doc fields + global) | **ghi đè** | `:398-407` |
| 4 | `AL Variable Library` system var (theo `source_doctype/field`) | chỉ khi thiếu | `:409-415` |
| 5 | `AL Profile System.system_variables` (child override) | **ghi đè** | `:417-422` |
| 6 | `al_bom_vars` top-level (user nhập) | **ghi đè** | `:424-427` |
| 7 | `_profile_system` override → `_resolve_system_variables()` full | **ghi đè system var** | `:470-471` |
| 8 | `AL Variable Library.default_value` (user var) | chỉ khi thiếu | `:546-574` |
| 9 | Chuẩn hoá % (`>1` → chia 100) | biến đổi tại chỗ | `:514-544` |

**Suy ra thứ tự thắng cuối cùng (cao → thấp), bỏ qua lớp "chỉ khi thiếu":**

```
profile_system override  (7)
  > al_bom_vars top-level (6)
    > Profile System.system_variables (5)
      > FB get_live_context (3)
        > Formula Global Variable (2)
          > extra_vars (1)

Lớp chỉ-điền-khi-thiếu (không thắng lớp nào ở trên):
  Library system var (4) · Library user default (8)
```

⚠ **Hai điểm bất ngờ đã xác nhận bằng code:**
1. `extra_vars` được ghi ở 1.1 **trước** Global Variable (1.2) → một Global Variable trùng tên sẽ **đè** giá trị `extra_vars`; trong khi top-level `al_bom_vars` (1.5) lại đè Global. Cùng là "user nhập" nhưng 2 bảng có ưu tiên khác nhau.
2. Nếu user đổi `_profile_system` trong dialog **và** có sửa tay biến hệ thống, bước 1.5c chạy `_resolve_system_variables()` full → **ghi đè lại** các biến hệ thống vừa sửa. Chưa có cảnh báo cho người dùng.

### 4.3 Điều kiện "biến có giá trị"

| Loại biến | Có giá trị khi |
|---|---|
| system var | có `source_doctype/source_field` + tìm được bản ghi nguồn + field khác NULL |
| user var | user nhập trong dialog / `extra_vars` / có `default_value` |
| row literal | dòng BOM có `slug` + master data tương ứng |
| bucket | B5 đã chạy (sau khi có `bom_result`) |
| cost template line | B6, và `line_code` đứng trước trong bảng |
| FVB | scope khớp + handler chạy được + `source_config` hợp lệ |
| `$NAME` / `FS-CODE.var` / `$snap.field` | chỉ khi đi qua `VariableResolver` (không phải B3/B6 trực tiếp) |

---

## 5. Luồng gợi ý biến khi gõ công thức

### 5.1 Ai gọi ai

```
formula_setup.js  (formula_builder.formula.initGridField / patchField)
   │
   ├─ refresh form → alumglass.FormulaContext.fetch(doctype, docname)
   │      └─ frappe.call alumglass.api.get_formula_context
   │
   └─ monkey-patch formula_builder.formula._ContextBuilder.build
          (formula_setup.js:87-150)
          → chèn ctx.variables + ctx.references vào liveCtx
                 │
                 ▼
          widget dựng autocomplete:
            - liveCtx.variables  → global vars
            - _ContextBuilder     → local fields + sibling child rows
            - _afbFieldConfig.global_vars (cost_template.js:173-190)
            - extra_completions (patchField)
```

### 5.2 `get_formula_context` — hai đường (catalog / legacy)

`api/__init__.py` — từ v28_14 có **HAI đường**:

1. **Đường catalog** (record đã gán `variable_profile`): gọi
   `alumglass.api.variable_catalog.get_variable_catalog` → adapter + rule +
   dedupe + references. Trả thêm `profile` + `meta` (nguồn gốc, bị loại, trùng tên).
2. **Đường legacy** (record chưa gán profile, hoặc gọi với
   `include_all_sources=True`): 9 nhóm dưới đây, giữ nguyên hành vi cũ.

Bảng legacy (chỉ dùng khi chưa có profile):

| Nhóm | Nội dung | `source_type` |
|---|---|---|
| 0 | FB `get_live_context` (binding + field doc + global) | `binding` / `doctype_field` / `global_variable` |
| 1 | Cost Bucket | `cost_bucket` |
| 2 | System Variable (Library is_system=1) | `variable_library` |
| 3 | User Variable (Library is_system=0) | `variable_library` |
| 4 | Formula Global Variable | `formula_global_var` |
| 5 | Row Literal — `AL Variable Settings.row_literals` (fallback tuple khi chưa migrate) | `row_literal` |
| 6 | Common BOM Var — `AL Variable Settings.common_variables` (fallback tuple) | `common_var` |
| 7 | Formula Variable Binding (doctype/global, có `only_fields` theo field) | `binding` |
| 8 | Variable Set của document (nếu resolve được) | `variable_set` |
| — | Slug Library → `references` | — |

**Dedup legacy:** giữ entry **đầu tiên** theo tên để bảo toàn vị trí nhóm,
nhưng (a) nếu giá trị entry đầu rỗng thì lấy giá trị entry sau, (b) hợp phạm vi
`only_fields`/`hide_all` của mọi nguồn trùng tên, (c) ghi mọi nguồn bị bỏ vào
`meta.duplicates`. **Dedup catalog:** ưu tiên `has_value` → `sort_order` →
`adapter_order`; hợp phạm vi field; báo `meta.duplicates`.

### 5.3 `get_live_context` — `applies_to_field` (đã sửa 2026-11-12)

✅ Widget (`formula_builder.js:_scope()` + `_buildCtx()`) nay gửi `fieldname`;
`get_live_context` lọc binding theo `applies_to_field`. Ngoài ra mỗi biến trả
kèm `applies_to_field`/`only_fields` để client lọc được **kể cả khi context chỉ
fetch 1 lần cho cả form** (cache theo `doctype::docname::child_table`).

Trước bản vá: `_scope()` không gửi `fieldname` ⇒ mọi binding có
`applies_to_field` đều lọt qua. Xem §6.2 mục 1 và §10A.

### 5.4 Gợi ý trong dialog toàn màn hình (double-click)

- Widget gọi thẳng `get_live_context` (`formula_builder.js:1828-1852`), **không** đi qua `get_formula_context`.
- API đó chỉ trả: binding + field của doc + crossTables + global constant.
- **Nhưng** sau khi có `_liveCtx`, widget dựng sidebar qua `_populateSidebarFromCtx()` → `_buildCtx()` → `_ContextBuilder.build` **đã bị AlumGlass patch** (`formula_setup.js`). Patch chèn thêm `alumglass.FormulaContext.getSync(doctype, docname, childTable)` — tức bộ biến catalog/legacy — vào `liveCtx.variables`/`references`.
- Hệ quả thực tế: dialog **có** biến AlumGlass nếu form đã `refresh` (cache 5 phút đã nạp). Nếu mở dialog trước khi cache có (hiếm) thì dialog chỉ còn bộ của FB; cache được nạp theo `doctype::docname::child_table` từ `AL Formula Field` (không còn danh sách doctype cứng).

> Tài liệu cũ `alumglass/public/js/HUONG_DAN_FORMULA_CONTEXT.md` mô tả đúng hành vi **widget gốc** ("FVB chỉ ảnh hưởng dialog"), nhưng không còn đúng sau khi AlumGlass patch `_ContextBuilder`. Tài liệu đó cũng còn vài chỗ lỗi thời (`get_cost_template_context` đã deprecated, `v.source === "bucket"/"system"` không còn được `get_formula_context` gán).

### 5.5 Validate công thức

| Nơi | Cách lấy biến hợp lệ | Ghi chú |
|---|---|---|
| `AL Cost Template.validate()` | `_build_known_names()` → `get_formula_context("AL Cost Template", None)` | chỉ cảnh báo (`msgprint`), không chặn save |
| `AL Bom Set.validate()` | `build_known_names("AL Bom Set", name, slugs, FORMULA_FIELDS)` | **throw** khi sai |
| `AL Accessory Set.validate()` | `build_known_names("AL Accessory Set", name)` | **throw** |
| client `cost_template.js` | `get_formula_context` cache | chỉ cảnh báo |

🔴 Vì validate dùng `get_formula_context`, **mọi biến hiện trong autocomplete đều được coi là hợp lệ** — kể cả biến không bao giờ có giá trị lúc tính. Đây là lỗ hổng tin cậy: sửa `get_formula_context` là sửa luôn "luật hợp lệ".

---

## 6. Bảng ưu tiên & các điểm lệch preview/runtime

### 6.1 Cùng một biến, nhiều nguồn — chuyện gì xảy ra?

| Tình huống | Runtime | Autocomplete | Rủi ro |
|---|---|---|---|
| System var đã seed FVB | FB `get_live_context` thắng | FB entry (nhóm 0) thắng | OK nếu binding đúng |
| System var chưa seed | Library + profile override | Library entry (nhóm 2) | OK |
| Cùng tên có Global Variable + Library | **Global thắng** (bước 2 ghi trước; Library system/user chỉ điền khi thiếu) | **Library thắng** — dedup giữ entry nhóm 2/3 (đứng trước Global nhóm 4) | 🔴 Gợi ý hiện giá trị Library, lúc tính dùng Global |
| Cùng tên có FVB `constant` + Library | FB thắng | FB thắng | nếu admin quên xoá binding cũ → biến "chết" vẫn hiện |
| Cost Bucket trùng tên biến Library | B5 ghi `buckets`, không ghi `inputs`; B6 ưu tiên `inputs` (`{**extra_context, **inputs}`) | Bucket entry (nhóm 1) bị dedup nếu trùng | Công thức B6 đọc **inputs**, không đọc bucket → có thể ra 0 |
| User var không nhập | `default_value` hoặc thiếu | hiện `"—"` / default | công thức có thể lỗi âm thầm (on_error default) |

### 6.2 Danh sách lệch đã xác nhận

> **Trạng thái 2026-11-12:** 11 điểm dưới đây đã được vá trong mã (nhánh
> `main` của `alumglass`, `develop` của `formula_builder`), chưa commit/push.
> Cột "Trạng thái" ghi nơi đã sửa; chi tiết đầy đủ ở §10A.

| # | Vấn đề | Trạng thái |
|---|---|---|
| 1 | **`applies_to_field` không có tác dụng** — widget không gửi `fieldname` (§5.3). | ✅ Đã sửa: widget gửi `fieldname`; binding mang `only_fields`; client lọc cả khi context chỉ fetch 1 lần. |
| 2 | **Dedup che giá trị** — entry FB `None` thắng entry Library có giá trị (§5.2). | ✅ Đã sửa: dedup lấy giá trị từ entry sau nếu entry đầu rỗng + ghi `meta.duplicates`; catalog ưu tiên `has_value`. |
| 3 | **Cost Template thấy toàn bộ user var** — không có Variable Set nên nhóm 3 trả hết Library. | ✅ Đã sửa: profile `P_COST_TEMPLATE_DEFAULT` (EXCLUDE_ALL) gán cho record hiện có; vẫn thêm rule nếu cần user var. Validate vẫn dùng universe đầy đủ. |
| 4 | **`injectContext` trong `cost_template.js` lọc sai** — lọc `v.source` theo bucket/system/global, nhưng `get_formula_context` gán `source="local"` cho bucket/system. | ✅ Đã sửa: inject toàn bộ `ctx.variables`, không lọc theo `source`. |
| 5 | **`FORMULA_DOCTYPE_REGISTRY` hardcode** — danh sách doctype/field nằm trong JS (`formula_setup.js:188-219`). | ✅ Đã bỏ: nguồn duy nhất là `AL Formula Field` + API `get_formula_fields`. |
| 6 | **Row Literal & Common Var hardcode** — thêm literal/common var mới phải sửa Python (2 danh sách). | ✅ Đã sửa: `AL Variable Settings.row_literals` / `common_variables` là nguồn chính; tuple cũ chỉ còn là fallback khi site chưa migrate. |
| 7 | **Offset mapping hardcode** — `api/__init__.py:867-875`. | ✅ Đã sửa: đọc `AL Variable Library.source_field` / `source_link_field`; map 4 tên cũ chỉ là fallback migrate. |
| 8 | **`AL Accessory Set.variable_set` chết** — không nơi nào đọc. | ✅ Đã sửa: adapter `variable_set` đọc Link trực tiếp; profile mặc định của Accessory Set dùng nó. |
| 9 | **1.5c ghi đè biến hệ thống user vừa sửa** — khi đổi profile (§4.2). | ✅ Đã sửa: snapshot user input trước 1.5c và áp lại sau. |
| 10 | **`extra_vars` bị Global Variable đè** — khác với top-level (§4.2). | ✅ Đã sửa: `extra_vars` + top-level cùng thuộc lớp user, áp lại ở 1.5 sau Global/FB. |
| 11 | **Global Variable tắt vẫn vào `inputs`** — `get_all_global_variables()` không lọc `is_active`. | ✅ Đã sửa: lọc `is_active=1`; biến tắt không còn vào `inputs`. |

*Ghi chú:* mục 5 — `panel_count_formula` / `qty_per_panel_formula` có field trên
`AL Bom Item` nhưng **không engine nào đọc**; registry bỏ qua 2 field này là
đúng, không phải thiếu.

---

## 7. Nhận xét — điểm mạnh, rủi ro, nợ kỹ thuật

### 7.1 Điểm mạnh

- **Data-driven thật** ở phần lớn nguồn: thêm Cost Bucket, System Variable, Pricing Dimension, Slug… không phải sửa code.
- **Một resolver dùng chung** cho system variable (`system_variable_resolver.py`) — đã sửa được lỗi 2 bản đọc lệch nhau.
- **FB là lớp resolve mạnh**: 21 source_type, batch resolver chống N+1, topological sort, safe_eval chống RCE, scope doctype/field.
- **Cross-row slug** hoạt động xuyên suốt 3 tầng (UI → validate → engine) và dùng **cùng** hàm normalize.
- **Có đường lùi rõ ràng**: mọi nhánh FB đều fallback về Python cũ, có cảnh báo thay vì im lặng (phần lớn).

### 7.2 Rủi ro chính (theo mức)

| Mức | Vấn đề | Vì sao nguy hiểm |
|---|---|---|
| 🔴 Cao | Autocomplete/validate dùng chung `get_formula_context` với 9 nhóm chồng lấn | Người dùng thấy 1 biến "hợp lệ" nhưng runtime lấy giá trị từ nguồn khác hoặc không có giá trị → ra tiền sai mà không báo |
| 🔴 Cao | Không có bộ lọc theo ngữ cảnh/field thực sự | Gõ `DO_` ở Cost Template thấy hàng chục biến không liên quan; dễ chọn nhầm |
| 🟠 TB | Dedup "first wins" không phân biệt nguồn | Binding rỗng che giá trị thật |
| 🟠 TB | Hardcode còn rải rác | Thêm biến phải sửa 2-4 nơi, dễ quên |
| 🟠 TB | Thứ tự ưu tiên B1 phức tạp, không có tài liệu chuẩn | 2 bảng "user nhập" ưu tiên khác nhau; đổi profile ghi đè biến sửa tay |
| 🟡 Thấp | `$`/`FS-` không chạy trong B3/B6 | Người dùng học 1 cú pháp nhưng nó chỉ chạy ở ngữ cảnh khác |
| 🟡 Thấp | Field chết `AL Accessory Set.variable_set` | Gây hiểu nhầm cấu hình có tác dụng |

### 7.3 Kết luận ngắn

Hệ thống **đủ mạnh về khả năng resolve**, nhưng **thiếu một lớp "danh mục biến" (catalog) có bộ lọc và nguồn gốc rõ ràng**. Người dùng đang phải tự lọc bằng mắt giữa 9 nguồn chồng lấn. Việc cần làm không phải thêm nguồn mới, mà là **gom nguồn + khai báo phạm vi + lọc theo ngữ cảnh**, đồng thời giữ nguyên cơ chế slug chéo.

---

## 8. Hướng phát triển: Variable Catalog + Variable Profile

### 8.1 Mục tiêu

1. **1 field ở doctype mẹ** quyết định bộ biến cho cả cây (form mẹ + child table).
2. **Mọi nguồn** (Library, Variable Set, Cost Bucket, FVB, Global, Slug…) đi qua **một catalog API**.
3. **Bộ lọc khai báo được** (include/exclude, prefix, category, source, field, có giá trị hay không).
4. **Giữ nguyên cross-row slug** `items.<slug>.<field>` và dạng index `items[n].<field>`.
5. **Preview = runtime**: preview dùng cùng nguồn resolve với runtime; profile **chỉ lọc danh sách gợi ý**, ⛔ không đổi giá trị tính toán.

### 8.2 Kiến trúc đề xuất

```
Doctype mẹ (AL Bom Set / AL Cost Template / AL Accessory Set …)
   └─ field: variable_profile → AL Variable Profile
                                   ├─ rules (AL Variable Profile Rule)
                                   └─ cross_row (AL Variable Cross Row)

API: alumglass.api.variable_catalog.get_variable_catalog(...)
   ├─ Source Adapters (mỗi nguồn 1 adapter, trả candidate có metadata)
   ├─ Profile Filter (include/exclude + field + value)
   ├─ Dedup + Precedence (theo catalog rule, không theo thứ tự code)
   └─ Output: groups + variables + references + provenance + thống kê bị lọc
```

### 8.3 Mô hình dữ liệu

#### `AL Variable Profile` (master)

| Field | Type | Ý nghĩa |
|---|---|---|
| `profile_code` | Data (autoname) | mã, vd `P_BOM_CUA_NHOM` |
| `profile_name` | Data | tên hiển thị |
| `is_active` | Check | |
| `default_action` | Select `INCLUDE_ALL` / `EXCLUDE_ALL` | chế độ mặc định (allowlist vs denylist) |
| `rules` | Table → `AL Variable Profile Rule` | các luật |
| `cross_row` | Table → `AL Variable Cross Row` | cấu hình slug chéo |
| `description` | Small Text | |

#### `AL Variable Profile Rule` (child)

| Field | Type | Ý nghĩa |
|---|---|---|
| `action` | Select `Include` / `Exclude` | |
| `source_kind` | Select (xem dưới) | nguồn biến |
| `source_ref` | Data | tham chiếu: `VAR_SET_CODE`, `DT:AL Profile System`, `BUCKET:*`, `FVB:*`… |
| `name_prefix` | Data | lọc theo tiền tố tên (vd `OFFSET_`) |
| `name_regex` | Data | lọc regex (nâng cao) |
| `category_tag` | Data | lọc `AL Variable Library.category` / group |
| `var_type` | Select | Float/Int/Data/… |
| `source_type` | Data | lọc `Formula Variable Binding.source_type` |
| `group_label` | Data | nhóm hiển thị trong autocomplete |
| `sort_order` | Int | thứ tự nhóm |
| `only_fields` | Small Text (JSON list) | chỉ hiện ở các field này (vd `["qty","width","height"]`) |
| `require_value` | Check | chỉ hiện khi resolve được giá trị khác rỗng |
| `is_active` | Check | |

**`source_kind` đề xuất (14):**

`variable_library_system`, `variable_library_user`, `variable_set`, `profile_system`, `product_type`, `material_category`, `cost_bucket`, `cost_template_line`, `formula_global`, `fvb_scope`, `row_literal`, `common_var`, `slug_reference`, `doctype_field`.

#### `AL Variable Cross Row` (child của Profile)

| Field | Type | Ý nghĩa |
|---|---|---|
| `table_field` | Data | vd `items` |
| `id_field` | Data | vd `slug` (mặc định `slug`) |
| `label_field` | Data | vd `line_name` |
| `fields` | Small Text (JSON list) | field được gợi ý; rỗng = mọi field công thức |
| `include_index_form` | Check | sinh thêm `items[0].field` |
| `enabled` | Check | |

#### Field trên doctype mẹ

Thêm **một** field Link vào các doctype mẹ (qua `custom_fields.py` hoặc JSON):

```
variable_profile  →  AL Variable Profile
```

Áp dụng cho: `AL Bom Set`, `AL Cost Template`, `AL Accessory Set`, `AL Alert Config`, `AL Quantity Calc Method`, `Formula Global Variable`.
Child table **không cần field riêng** — catalog nhận `parent_doctype/parent_docname/child_table/row_index` và tự kế thừa profile của cha.

### 8.4 API đề xuất

```python
# alumglass/api/variable_catalog.py

@frappe.whitelist()
def get_variable_catalog(doctype, docname=None, child_table=None,
                         row_index=None, fieldname=None,
                         include_values=True):
    """
    Trả:
    {
      "profile": {"code": "...", "name": "..."},
      "groups": [
         {"key": "bucket", "label": "Chi phí",
          "variables": [
             {"name": "VL_NHOM", "label": "...", "type": "Float",
              "value": 0, "value_display": "0",
              "source_kind": "cost_bucket", "source_ref": "VL_NHOM",
              "group": "Chi phí", "provenance": "AL Cost Bucket",
              "is_required": False, "is_pricing_dimension": False}
          ]}
      ],
      "references": [ {"name": "items.kinh_tren.width", ...} ],
      "meta": {"total": 42, "excluded_by_rules": 118, "profile_code": "..."}
    }
    """
```

**Quy tắc resolve (cố định, có tài liệu):**

```
candidates = union(adapters được rule Include chạm tới)
candidates = candidates - (rule Exclude khớp)
nếu default_action = EXCLUDE_ALL:
    candidates = chỉ những gì có rule Include khớp
nếu only_fields và fieldname không nằm trong danh sách: loại
nếu require_value và value rỗng: loại
dedup theo (name) — giữ candidate có priority cao nhất;
    nếu trùng priority → giữ theo thứ tự adapter ưu tiên khai báo trong profile
sort: rule.sort_order → group_label → name
```

**API phụ:**
- `get_variable_profile(doctype, docname)` — profile đang áp dụng.
- `preview_variable_catalog(profile_code, doctype, child_table, fieldname)` — cho admin xem trước.
- `explain_variable(name, doctype, docname, ...)` — trả provenance + giá trị từng lớp (dùng cho tooltip "vì sao tôi thấy biến này").

### 8.5 Tích hợp UI

1. `formula_setup.js` gọi `alumglass.api.variable_catalog.get_variable_catalog` thay `get_formula_context`.
2. Patch `_ContextBuilder.build` như hiện tại, nhưng đẩy thêm metadata:
   - `source_kind`, `provenance`, `group` → tooltip;
   - `references` từ `cross_row` → gợi ý slug chéo.
3. Autocomplete hiển thị **theo nhóm** và có badge nguồn; gõ tên sẽ ưu tiên nhóm khớp.
4. Dialog double-click gọi cùng API (truyền `child_table`/`row_index`) → không còn cảnh "dialog thiếu biến".
5. Field-level: truyền `fieldname` từ widget. Nếu chưa sửa được widget, `initGridField` có thể truyền `extra_completions` đã lọc sẵn theo field.

### 8.6 Giữ nguyên cross-row slug

- `AL Variable Cross Row` sinh references:
  - `items.<slug>.<field>` (slug-based, dùng `id_field`);
  - `items[<idx>].<field>` (index-based, nếu bật).
- Validate vẫn dùng `normalize_cross_row` + `build_known_names(cross_row_slugs, cross_row_fields)`.
- Runtime vẫn dùng `normalize_global` + `inputs["items"]`.
- Catalog **không thay** cơ chế này — chỉ **lọc** danh sách field/slug được gợi ý.

### 8.7 Tương thích ngược

| Trạng thái | Hành vi |
|---|---|
| Doctype chưa gán `variable_profile` | Dùng profile mặc định `P_LEGACY_<doctype>` seed sẵn, mô phỏng đúng 9 nhóm hiện tại |
| Profile `default_action=INCLUDE_ALL`, không rule | Không lọc gì — y hệt hiện tại |
| FVB cũ | Vẫn là candidate `fvb_scope`; nếu profile không include FVB → ẩn khỏi gợi ý nhưng runtime vẫn resolve (catalog chỉ ảnh hưởng UI/validate) |
| Code cũ gọi `get_formula_context` | Giữ nguyên hàm, bên trong chuyển sang catalog; nếu lỗi → fallback 9 nhóm cũ |

### 8.8 Vì sao KHÔNG đưa catalog vào runtime resolve

- Catalog là **danh mục để gợi ý**, không phải nguồn giá trị.
- Runtime cần ổn định kể cả khi profile bị sửa/xoá. Nếu runtime phụ thuộc profile, một thay đổi UI có thể làm đổi giá bán — rủi ro không chấp nhận.
- Tuy nhiên **precedence table** nên được tách thành module dùng chung (`engine/variable_resolution.py`) để catalog hiển thị đúng "nguồn nào thắng".

---

## 9. Ví dụ setting chi tiết + diễn giải cách hoạt động

### 9.1 Ví dụ A — `AL Bom Set` cho "Cửa đi nhôm kính"

#### Bước 1 — Tạo Profile

**`AL Variable Profile`**

```
profile_code   = P_BOM_CUA_DI
profile_name   = BOM cửa đi nhôm kính
default_action = EXCLUDE_ALL          ← chỉ hiện đúng biến được khai
is_active      = 1
```

**`rules` (AL Variable Profile Rule):**

| # | action | source_kind | source_ref | điều kiện thêm | group_label | sort | only_fields |
|---|---|---|---|---|---|---|---|
| 1 | Include | `cost_bucket` | `*` | — | `01 · Chi phí` | 10 | — |
| 2 | Include | `variable_library_system` | `*` | `category_tag = OFFSET\|NC` | `02 · Thông số hệ` | 20 | — |
| 3 | Include | `variable_library_user` | `*` | `name_prefix = W_\|H_\|n_\|TONG_\|installation_` | `03 · Thông số nhập` | 30 | — |
| 4 | Include | `variable_set` | `AUTO` | — | `03 · Thông số nhập` | 31 | — |
| 5 | Include | `formula_global` | `*` | — | `04 · Hằng số` | 40 | — |
| 6 | Include | `fvb_scope` | `AUTO` | — | `05 · Binding` | 50 | — |
| 7 | Include | `row_literal` | `*` | — | `06 · Dòng hiện tại` | 60 | `["width","height","qty","calc_pattern"]` |
| 8 | Include | `slug_reference` | `items` | — | `07 · Dòng khác` | 70 | — |
| 9 | Exclude | `variable_library_user` | `*` | `name_prefix = OLD_\|TEST_` | — | 5 | — |
| 10 | Exclude | `fvb_scope` | `*` | `source_type = custom_function` | — | 5 | — |

> ⚠️ Rule **không có** điều kiện `bucket_role`, `var_name`, `category in [...]` hay
> `is_active=1`. `is_active` là điều kiện **tự có** của adapter (bucket/global/library đều
> tự lọc), ⛔ không nhập vào rule. Muốn lọc bucket theo role: dùng `source_ref` liệt kê mã
> cụ thể (`VL_NHOM|VL_KINH`) hoặc `category_tag` nếu `report_group` tương ứng.
> `fvb_scope.source_ref` là **tên biến**, ⛔ không phải doctype — muốn lọc theo doctype/loại
> nguồn dùng `source_type` hoặc `name_prefix`/`name_regex`.

**`cross_row`:**

```
table_field   = items
id_field      = slug
label_field   = line_name
fields        = ["width","height","qty","glass_thick","glass_type","unit_price","line_total"]
include_index_form = 1
enabled       = 1
```

#### Bước 2 — Gán vào doctype mẹ

Trên `AL Bom Set`, field `variable_profile = P_BOM_CUA_DI`.

> Chỉ 1 field. Mọi dòng `items` của Bom Set này **tự động** dùng cùng profile — vì catalog nhận `parent_doctype` + `parent_docname`, không cần khai lại trên child.

#### Bước 3 — Người dùng thấy gì khi gõ

Mở `AL Bom Set` → click vào `items[0].qty` → widget gọi:

```
GET /api/method/alumglass.api.variable_catalog.get_variable_catalog
    doctype = AL Bom Set
    docname = BS-CUA-DI-01
    child_table = items
    row_index = 0
    fieldname = qty
```

Catalog chạy:

1. **Adapters** sinh candidate (số lượng dưới đây là minh hoạ):
   - 8 cost bucket → nhóm `01 · Chi phí`
   - 6 system var lọc `OFFSET_*`, `NC_*`
   - 12 user var khớp prefix
   - 5 biến của Variable Set gắn với Bom Set
   - 3 global constant
   - 20 binding scope `AL Bom Set`
   - 9 row literal (rule chỉ khớp khi field đang sửa nằm trong 4 tên khai)
   - Slug refs: 12 slug × 7 field = 84 references
2. **Exclude** loại `OLD_*`, `TEST_*`, `custom_function`.
3. **`only_fields`**: field đang sửa là `qty` và `qty` nằm trong danh sách của rule ⇒ rule
   `row_literal` khớp, **mọi** row literal của nguồn đi tiếp (kể cả `unit_price`).
   `only_fields` là cổng theo **field đang sửa ở mức rule**; muốn mỗi field một danh sách
   riêng thì **tách biến giữa các rule** (xem §9.3). Sửa field ngoài 4 tên đó ⇒ rule không
   khớp, row literal không hiện (vì `EXCLUDE_ALL`).
4. **Dedup**: `TONG_M2` có ở cả common var (rule sort 60) và FVB (sort 50). Ưu tiên **có giá trị** trước, rồi `sort_order` nhỏ hơn ⇒ FVB thắng nếu cả hai cùng có giá trị; nếu FVB rỗng mà common var có giá trị thì lấy giá trị common var (giữ metadata FVB).
5. **Sort** theo `sort_order` → nhóm `01..07`.

Kết quả: gõ `T` → chỉ còn `TONG_M2`, `TONG_VL` (bucket), `TransomHeight_mm`; không còn 40 biến rác từ Library.

Gõ `items.` → chỉ hiện 12 slug × 7 field, nhãn `Chiều rộng — khung ngang trên`, v.v.

#### Bước 4 — Diễn giải cách hoạt động (end-to-end)

| Lớp | Việc xảy ra |
|---|---|
| **UI** | `formula_setup.js` fetch catalog 1 lần/record, cache 5 phút; patch `_ContextBuilder.build` chèn `variables` + `references`. |
| **Gợi ý slug** | Catalog trả `references` dạng `items.kinh_tren.width`; widget hiển thị; chèn vào công thức đúng chuỗi đó. |
| **Validate** | `AL Bom Set.validate()` gọi `build_known_names` → `get_formula_context(..., include_all_sources=True)` → universe **đầy đủ** (legacy), không dùng catalog đã lọc profile → `kinh_tren__width` có trong `known_names` → hợp lệ. |
| **Lưu** | Không đổi gì: `AL Bom Item.width` lưu nguyên văn `items.kinh_tren.width`. |
| **Runtime B3** | `_normalize_items_ref` đổi thành `kinh_tren__width`; B3 mirror `inputs["items"]["kinh_tren"]["width"]`. |
| **Runtime B1** | Các biến scalar (bucket, system, user, global, FVB) resolve theo precedence hiện có — catalog **không** can thiệp. |
| **Kết quả** | Cùng một danh sách biến ở UI và validate; runtime vẫn ổn định. |

### 9.2 Ví dụ B — `AL Cost Template` cho "Giá thành cửa đi"

#### Profile

```
profile_code   = P_COST_CUA_DI
profile_name   = Giá thành cửa đi
default_action = EXCLUDE_ALL
```

| # | action | source_kind | source_ref | điều kiện | group_label | sort |
|---|---|---|---|---|---|---|
| 1 | Include | `cost_bucket` | `*` | — | `01 · Vật liệu & chi phí` | 10 |
| 2 | Include | `cost_template_line` | `AUTO` | — | `02 · Dòng tự định nghĩa` | 20 |
| 3 | Include | `variable_library_system` | `*` | `name_prefix = NC_\|VAT_\|PROFIT_` | `03 · Tỷ lệ` | 30 |
| 4 | Include | `variable_library_user` | `TONG_M2\|installation_height_m` | — | `04 · Thông số nhập` | 40 |
| 5 | Include | `formula_global` | `*` | — | `05 · Hằng số` | 50 |
| 6 | Include | `common_var` | `*` | — | `06 · Thông số nhập` | 60 |
| 7 | Exclude | `row_literal` | `*` | — | — | 5 |
| 8 | Exclude | `slug_reference` | `*` | — | — | 5 |

>`cost_template_line` = adapter đặc biệt: sinh biến từ các `line_code` **đứng trước** dòng đang sửa (vì B6 tính tuần tự). Đây chính là cách "biến dẫn xuất" nên được gợi ý mà không cần khai tay.
>
> ⚠️ **Giới hạn:** điều kiện "chỉ dòng trước" chỉ chạy khi API **có `row_index`**
> (`adapters.cost_template_line`: `rows[:ctx.row_index]`). Autocomplete bulk
> (`formula_setup.js`) **không gửi `row_index`** ⇒ context có thể chứa cả `line_code` của
> dòng **sau**. ⛔ Đừng tham chiếu dòng sau — công thức sẽ ra 0/vòng.

#### Vì sao loại row literal / slug

- B6 chạy **sau** B2/B4 nhưng context của B6 là `inputs` + `buckets`, **không có** row literal dạng `{slug}__*` và **không có** `items.*`.
- Nếu vẫn hiện, người dùng có thể gõ `width` trong `calc_formula` → engine trả 0/None âm thầm.
- Common var (`W_mm`, `H_mm`, `TONG_M2`…) **vẫn dùng được**: chúng đi từ `al_bom_vars` vào `inputs`, nên profile seed thực tế có Include `common_var`.
- Đây là ví dụ điển hình cho "lọc để tránh nhầm lẫn".

#### Diễn giải

1. Mở `AL Cost Template` → fetch catalog với `child_table="items"`, `fieldname="calc_formula"`.
2. Gõ `VL_` → chỉ thấy bucket `VL_NHOM`, `VL_KINH`, `VL_PK`, `VL_VTP`.
3. Gõ `TONG_` → `TONG_VL`, `TONG_VL_PK`, `TONG_M2` (common var), và các `line_code` tự định nghĩa đứng trước.
4. Validate khi save: dùng **universe đầy đủ** (`include_all_sources=True`), ⛔ không dùng catalog đã lọc profile → công thức cũ dùng biến ngoài profile không bị báo oan; biến thật sự không tồn tại vẫn bị validator cảnh báo/chặn theo luật hiện hành.
5. Runtime B6: `extra_context = inputs ⊕ buckets`; các `line_code` trước đã có trong `values` → công thức chạy đúng thứ tự.

### 9.3 Ví dụ C — `only_fields` lọc theo FIELD ĐANG SỬA

`only_fields` **không phải** danh sách biến được phép. Nó là **cổng theo field đang sửa ở
mức rule**: nếu có `fieldname` và field đó **không** nằm trong danh sách, rule không khớp
**toàn bộ** candidate của rule đó.

Cùng `P_BOM_CUA_DI`, muốn **mỗi field thấy một danh sách riêng**: tách biến giữa các rule
bằng `source_ref` (hoặc `name_prefix` / `name_regex`).

| # | action | source_kind | source_ref | only_fields | group_label | sort |
|---|---|---|---|---|---|---|
| 11 | Include | `row_literal` | `width\|height` | `["width","height"]` | `06a · Kích thước` | 60 |
| 12 | Include | `row_literal` | `qty\|calc_pattern` | `["qty","calc_pattern"]` | `06b · Số lượng` | 61 |

**Điều kiện:** mỗi biến chỉ do **một** rule chọn. Khi đó:

- **Bulk (không gửi `fieldname`):** `width`/`height` mang `only_fields` của rule 11;
  `qty`/`calc_pattern` mang của rule 12; `unit_price` không rule nào chọn ⇒ không hiện
  (`EXCLUDE_ALL`). Client lọc theo field đang sửa ⇒ đúng danh sách từng field.
- **Có `fieldname`:** `width` → chỉ `width`/`height`; `qty` → chỉ `qty`/`calc_pattern`;
  `unit_price` → rỗng.
- Nếu **nhiều rule cùng chọn một biến** (`source_ref` chồng nhau) ⇒ `only_fields` lấy **hợp**;
  một rule không giới hạn ⇒ biến không giới hạn. Khi đó **không** tách được biến đó theo field.

Hai đường lọc:

- **Autocomplete bulk**: client không gửi `fieldname` lên server; server vẫn gắn
  `only_fields`/`hide_all` vào từng biến, **client lọc theo field đang sửa**.
- **API có `fieldname`** (preview/validate): server lọc rule ngay.

> ⚠️ Đừng đặt 2 rule đều `source_ref = *` với `only_fields` khác nhau: cả hai cùng khớp mọi
> biến ⇒ lấy **hợp**, ⛔ không tách theo field. Phải tách biến giữa các rule.

### 9.4 Ví dụ D — Cross-slug vẫn giữ nguyên

Công thức hợp lệ trong `AL Bom Item.qty`:

```
items.kinh_tren.width * items.kinh_tren.height / 1000000
```

- Catalog trả reference `items.kinh_tren.width` (slug `kinh_tren` lấy từ `AL Slug Library` + dòng có `slug=kinh_tren`).
- Validate: `normalize_cross_row` → `kinh_tren__width`, `kinh_tren__height`; `build_known_names` thêm đúng 2 tên này.
- Runtime B3: `normalize_global` → `kinh_tren__width * kinh_tren__height / 1000000`; `inputs["items"]["kinh_tren"]` có `width/height` từ B3.
- Dạng index `items[0].width` vẫn được hỗ trợ; catalog bật `include_index_form` để gợi ý cả 2 dạng.

### 9.5 Ví dụ E — Một field ở mẹ, con nhận tự động (giải thích cơ chế)

```
AL Bom Set (docname BS-001, variable_profile=P_BOM_CUA_DI)
   ├─ items[0] slug=khung_ngang_tren  ← khi sửa width, catalog nhận:
   │      parent_doctype=AL Bom Set, parent_docname=BS-001,
   │      child_table=items, row_index=0, fieldname=width
   │      → đọc variable_profile của BS-001
   │      → áp rule, trả biến
   └─ items[1] slug=kinh_tren         ← cùng profile, row_index=1
```

Không cần field `variable_profile` trên `AL Bom Item`. Hiện **chưa** hỗ trợ override profile theo từng dòng — `_resolve_profile_doc` chỉ đọc profile từ doctype cha + `docname`. Muốn có phải thêm field trên child **và** sửa `_resolve_profile_doc` (ngoài phạm vi v28_14).

### 9.6 Mẫu record JSON đầy đủ (để triển khai)

**1) `AL Variable Profile` — `P_BOM_CUA_DI`**

```json
{
  "doctype": "AL Variable Profile",
  "profile_code": "P_BOM_CUA_DI",
  "profile_name": "BOM cửa đi nhôm kính",
  "is_active": 1,
  "default_action": "EXCLUDE_ALL",
  "description": "Bộ biến chuẩn cho BOM cửa đi — lọc theo nguồn, nhóm và field.",
  "rules": [
    {"action": "Include", "source_kind": "cost_bucket", "source_ref": "*",
     "group_label": "01 · Chi phí", "sort_order": 10, "is_active": 1},
    {"action": "Include", "source_kind": "variable_library_system", "source_ref": "*",
     "category_tag": "OFFSET", "group_label": "02 · Thông số hệ", "sort_order": 20, "is_active": 1},
    {"action": "Include", "source_kind": "variable_library_system", "source_ref": "*",
     "category_tag": "NC", "group_label": "02 · Thông số hệ", "sort_order": 20, "is_active": 1},
    {"action": "Include", "source_kind": "variable_library_user", "source_ref": "*",
     "name_prefix": "W_|H_|n_|TONG_|installation_",
     "group_label": "03 · Thông số nhập", "sort_order": 30, "is_active": 1},
    {"action": "Include", "source_kind": "variable_set", "source_ref": "AUTO",
     "group_label": "03 · Thông số nhập", "sort_order": 31, "is_active": 1},
    {"action": "Include", "source_kind": "formula_global", "source_ref": "*",
     "group_label": "04 · Hằng số", "sort_order": 40, "is_active": 1},
    {"action": "Include", "source_kind": "fvb_scope", "source_ref": "AUTO",
     "group_label": "05 · Binding", "sort_order": 50, "is_active": 1},
    {"action": "Include", "source_kind": "row_literal", "source_ref": "*",
     "group_label": "06 · Dòng hiện tại", "sort_order": 60,
     "only_fields": "[\"width\",\"height\",\"qty\",\"calc_pattern\"]", "is_active": 1},
    {"action": "Include", "source_kind": "slug_reference", "source_ref": "items",
     "group_label": "07 · Dòng khác", "sort_order": 70, "is_active": 1},
    {"action": "Exclude", "source_kind": "variable_library_user", "source_ref": "*",
     "name_prefix": "OLD_|TEST_", "sort_order": 5, "is_active": 1},
    {"action": "Exclude", "source_kind": "fvb_scope", "source_ref": "*",
     "source_type": "custom_function", "sort_order": 5, "is_active": 1}
  ],
  "cross_row": [
    {"table_field": "items", "id_field": "slug", "label_field": "line_name",
     "fields": "[\"width\",\"height\",\"qty\",\"glass_thick\",\"glass_type\",\"unit_price\",\"line_total\"]",
     "include_index_form": 1, "enabled": 1}
  ]
}
```

**2) Gắn vào doctype mẹ**

```json
// AL Bom Set (custom field hoặc sửa JSON)
{
  "fieldname": "variable_profile",
  "fieldtype": "Link",
  "label": "Variable Profile",
  "options": "AL Variable Profile",
  "reqd": 0
}
```

**3) Response mẫu của `get_variable_catalog`**

```json
{
  "profile": {"code": "P_BOM_CUA_DI", "name": "BOM cửa đi nhôm kính"},
  "groups": [
    {"key": "01 · Chi phí", "label": "01 · Chi phí", "variables": [
      {"name": "TONG_VL", "label": "Tổng vật liệu", "type": "Float", "value": 0,
       "source_kind": "cost_bucket", "source_ref": "TONG_VL",
       "provenance": "AL Cost Bucket", "group": "01 · Chi phí"},
      {"name": "VL_NHOM", "label": "VL Nhôm", "type": "Float", "value": 0,
       "source_kind": "cost_bucket", "source_ref": "VL_NHOM",
       "provenance": "AL Cost Bucket", "group": "01 · Chi phí"}
    ]},
    {"key": "06 · Dòng hiện tại", "label": "06 · Dòng hiện tại", "variables": [
      {"name": "width", "label": "Chiều rộng", "type": "Float", "value": 1200,
       "source_kind": "row_literal", "source_ref": "width",
       "provenance": "AL Bom Item (dòng hiện tại)", "group": "06 · Dòng hiện tại"}
    ]}
  ],
  "references": [
    {"name": "items.kinh_tren.width", "label": "Chiều rộng — kính trên",
     "insert": "items.kinh_tren.width", "table": "items", "slug": "kinh_tren"},
    {"name": "items[0].width", "label": "Chiều rộng — hàng 1",
     "insert": "items[0].width", "table": "items", "idx": 0}
  ],
  "meta": {"total": 38, "excluded_by_rules": 112, "profile_code": "P_BOM_CUA_DI"}
}
```

> Các con số `total`/`excluded_by_rules` là **ví dụ minh hoạ**; giá trị thật phụ thuộc dữ liệu từng site.

### 9.7 Hướng dẫn setting biến từng bước trên UI

> **Trạng thái:** bản vá v28_14 **chưa commit, chưa chạy migrate trên site**. Mục này mô tả
> thao tác đọc từ DocType JSON + controller + JS của working tree. Bản đầy đủ hơn (kèm
> triệu chứng và cách xử lý): `docs/variable-catalog/huong-dan-setting-bien.md`.
>
> ⚠️ §8.3 đề xuất **14** `source_kind`; bản triển khai thực tế có **11**:
> `variable_library_system`, `variable_library_user`, `variable_set`, `cost_bucket`,
> `cost_template_line`, `formula_global`, `fvb_scope`, `row_literal`, `common_var`,
> `doctype_field`, `slug_reference`. Ba nguồn đề xuất `profile_system`, `product_type`,
> `material_category` **chưa có adapter riêng** — đọc §2 để biết chúng đang đi qua đường nào.

#### Bước 0 — Điều kiện

```bash
bench --site <dev> migrate        # tạo 7 DocType + cột variable_profile + chạy patch seed
bench build --app alumglass       # nạp JS v=1.2.0
```

Sau migrate phải có: 2 profile mẫu (`P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`),
8 `common_variables`, 10 `row_literals`, 11 `AL Formula Field`.
Phân quyền mặc định của 3 DocType cấu hình: **System Manager**.

#### Bước 1 — Tạo `AL Variable Profile`

| Field | Giá trị | Ghi chú |
|---|---|---|
| `profile_code` | `P_<NGỮ_CẢNH>` | Cũng là `name` (`autoname = field:profile_code`) |
| `profile_name` | Tên đọc được | |
| `is_active` | `1` | `0` ⇒ rơi về legacy |
| `default_action` | `EXCLUDE_ALL` (khuyến nghị) | `INCLUDE_ALL` = cho tất cả rồi trừ |
| `description` | Ngữ cảnh dùng | |

Ghi nhớ: `INCLUDE_ALL` **có** rule Include ⇒ chỉ chạy adapter của nguồn được Include;
**không** có rule Include ⇒ chạy **mọi** adapter (tương thích ngược).

#### Bước 2 — Khai `rules`

Mỗi dòng là 1 luật. Thứ tự áp dụng **cố định**, không theo thứ tự nhập:

```
Exclude khớp → loại
EXCLUDE_ALL + không khớp Include → loại
Include khớp → gắn group_label + sort_order
only_fields (nếu có fieldname) → lọc
require_value → lọc
dedupe theo name → giữ 1, phần bỏ ghi vào meta.duplicates
```

| Cột | Nhận gì | Dễ sai |
|---|---|---|
| `action` | `Include` / `Exclude` | Exclude thắng mọi Include |
| `source_kind` | 1 trong 11 nguồn (bảng dưới) | Chọn sai ⇒ rule không khớp gì |
| `source_ref` | `*` / rỗng / `AUTO` = mọi bản ghi; ngược lại danh sách ngăn `\|` | `slug_reference` phải là **tên bảng** (`items`), ⛔ không `*` |
| `name_prefix` | Tiền tố, ngăn `\|` | Phân biệt hoa thường |
| `name_regex` | Regex Python (`re.search`) | Regex hỏng ⇒ không khớp, không báo lỗi |
| `category_tag` | So `category` hoặc `group` của biến | Không phân biệt hoa thường |
| `var_type` | `Float/Int/Data/Select/Link/Check/Currency/Percent` | So khớp chính xác |
| `source_type` | Chỉ cho `fvb_scope`, ví dụ `custom_function` | |
| `group_label` | Nhóm hiện trong autocomplete | Nên đánh số `01 ·` |
| `sort_order` | Thứ tự nhóm, mặc định 100 | Rule khớp đầu tiên thắng khi hoà |
| `only_fields` | JSON list field | `[]` = **không giới hạn** |
| `require_value` | Chỉ hiện khi có giá trị thật | |
| `is_active` | Tắt không xoá | |

Nhiều rule Include cùng khớp một biến: nhóm/thứ tự lấy rule `sort_order` nhỏ nhất;
`only_fields` lấy **hợp**, và một rule không giới hạn ⇒ biến không giới hạn.

#### Bước 3 — Bảng 11 `source_kind` (bản triển khai)

| `source_kind` | Adapter (order) | Nguồn engine đọc | `source_ref` |
|---|---|---|---|
| `fvb_scope` | 10 | `Formula Variable Binding` — scope doctype cha **và** dòng con | `AUTO` / `*` = mọi binding; hoặc **tên biến** |
| `cost_bucket` | 20 | `AL Cost Bucket` (`is_active=1`) | `bucket_code` / `*` |
| `variable_library_system` | 30 | `AL Variable Library` (`is_system=1`) | `var_name` / `*` |
| `variable_library_user` | 40 | `AL Variable Library` (`is_system=0`) | `var_name` / `*` |
| `variable_set` | 45 | `AL Variable Set` gắn với chứng từ | `set_code` / `AUTO` / `*` |
| `cost_template_line` | 50 | `AL Cost Template.items.line_code` **đứng trước** dòng đang sửa | `AUTO` = mọi dòng trước; hoặc **`line_code`** |
| `formula_global` | 55 | `Formula Global Variable` (`is_active=1`) | `var_name` / `*` |
| `row_literal` | 60 | `AL Variable Settings.row_literals` | `var_name` / `*` |
| `common_var` | 70 | `AL Variable Settings.common_variables` | `var_name` / `*` |
| `doctype_field` | 80 | Field vô hướng của doctype cha / dòng đang sửa | `fieldname` / `*` |
| `slug_reference` | — | **Không phải adapter** — điều khiển `references` (`items.<slug>.<field>`) | Tên bảng con (`items`) |

Thứ tự `order` cũng là ưu tiên dedup khi mọi tiêu chí khác hoà.

> ⚠️ `fvb_scope` ⛔ **không lọc theo doctype bằng `source_ref`** — `source_ref` của mỗi
> candidate FVB là **tên biến**, không phải doctype. Muốn giới hạn theo doctype/loại nguồn:
> dùng `source_type` (vd `custom_function`) hoặc `name_prefix` / `name_regex`. Scope doctype
> cha + dòng con do adapter tự lấy.

#### Bước 4 — `only_fields` và `require_value`

- `only_fields` = **JSON list**: `["qty","width","height"]`.
  - `[]` / rỗng = **không giới hạn** — ⛔ không phải "ẩn hết".
  - **Autocomplete bulk**: client không gửi `fieldname` lên server; server vẫn gắn
    `only_fields`/`hide_all` vào từng biến, **client lọc theo field đang sửa**.
  - **API có `fieldname`** (validate/preview/gọi trực tiếp): **server lọc rule** theo field.
  - Không xác định được field ở cả hai phía ⇒ không lọc (an toàn ngược).
- `require_value=1` ⇒ biến rỗng bị loại hẳn, không rơi về nhóm mặc định.
- **`hide_all`** (chỉ có trong response): server gắn khi giao phạm vi **nguồn × rule**
  rỗng ⇒ ẩn ở mọi field. ⛔ Không phải field cấu hình.

#### Bước 5 — `cross_row` (biến chéo dòng)

| Cột | Nhận gì |
|---|---|
| `table_field` | Tên field bảng con, ví dụ `items` |
| `id_field` | Mặc định `slug` |
| `label_field` | `line_name` (Bom Item) / `item_code` (Accessory Item) |
| `fields` | JSON list field được gợi ý |
| `include_index_form` | Sinh thêm `items[n].<field>` |
| `enabled` | |

**Luật:** chỉ khai field engine **thật sự inject**.

- `AL Accessory Set.items`: `qty`, `unit_price`, `calc_pattern`, `total_qty`, `line_total`.
  ⛔ **Không** `qty_formula` — đây là **chuỗi công thức**, engine không tạo
  `{slug}__qty_formula`.
- `AL Bom Set.items`: `width`, `height`, `qty`, `glass_thick`, `glass_type`,
  `unit_price`, `line_total`… theo `cross_row.fields`.
- `AL Cost Template.items`: **không** dùng cross-row — B6 không có context `items.*`.

Thứ tự sinh `references`:

1. Có `cross_row` ⇒ dùng cấu hình.
2. Không có, nhưng có rule Include `slug_reference` ⇒ chỉ các bảng được trỏ.
3. Không có cả hai + `INCLUDE_ALL` ⇒ mọi bảng con (hành vi cũ).
4. `EXCLUDE_ALL` + không khai ⇒ không gợi ý chéo dòng.

#### Bước 6 — Gán profile ở doctype mẹ

| DocType | Field | Phạm vi |
|---|---|---|
| `AL Bom Set` | `variable_profile` | Field cha + mọi dòng `items` |
| `AL Cost Template` | `variable_profile` | Dòng `items` (`calc_formula`) |
| `AL Accessory Set` | `variable_profile` | `qty_formula` + cross-row |
| `AL Alert Config` | `variable_profile` | `trigger_condition` |

Không cần field trên bảng con — catalog nhận `child_table` + `row_index` và kế thừa cha.
`AL Variable Settings.default_profile` **chỉ** áp cho doctype đã khai field Link; patch
v28_14 **không** set default này.

> §8.3 đề xuất thêm field cho 6 doctype; bản triển khai thêm **4**: `AL Bom Set`,
> `AL Cost Template`, `AL Accessory Set`, `AL Alert Config`. `AL Quantity Calc Method` và
> `Formula Global Variable` **chưa** có field `variable_profile` — muốn dùng phải thêm field
> trước (catalog tự dò field Link đầu tiên trỏ `AL Variable Profile`).

Thứ tự resolve profile: tham số `profile` → field trên bản ghi → `default_profile` → legacy.

#### Bước 7 — Xem trước

1. Lưu profile (nút chỉ hiện khi record không phải new).
2. **Công cụ → Xem trước danh sách biến**.
3. Nhập DocType (mặc định từ `AL Variable Settings.preview_doctype`), bản ghi, bảng con,
   field đang sửa.
4. Đọc kết quả: nhóm · tên · nhãn · kiểu · giá trị · nguồn; đầu dialog có `Tổng` và
   `Bị luật loại`.
5. Khung cam "biến trùng tên" liệt kê nguồn **giữ** và nguồn **bỏ** — không phải lỗi.
6. Quyền: cần **read trên `AL Variable Profile`**; thiếu ⇒ "Bạn không có quyền xem trước
   danh mục biến."

#### Bước 8 — Checklist sau khi setting

- [ ] Profile `is_active=1`, `default_action` đúng ý.
- [ ] Mỗi rule có `source_kind` tồn tại; `slug_reference` dùng tên bảng thật.
- [ ] `only_fields` là JSON list hợp lệ; nhớ `[]` = không giới hạn.
- [ ] `cross_row.fields` chỉ gồm field engine inject; phụ kiện ⛔ không có `qty_formula`.
- [ ] Preview trên **bản ghi thật**, đúng `child_table` + `fieldname`.
- [ ] Gán profile ở bản ghi mẹ; gõ thử ≥ 3 từ khoá.
- [ ] Lưu thử công thức dùng biến **ngoài** profile → **phải lưu được**.
- [ ] Mở bản ghi thứ hai trong cùng phiên → danh sách đổi theo bản ghi (nếu không: cache
      client 5 phút → F5).

#### Bước 9 — Điều ⛔ không được làm bằng profile

| ⛔ Không dùng để | Vì sao |
|---|---|
| Đổi giá trị tính toán | Runtime không đọc profile |
| Chặn công thức cũ | Validate dùng `include_all_sources=True` (universe đầy đủ) |
| Chặn người dùng gõ tay | Autocomplete chỉ gợi ý |

✅[V] `build_known_names()` gọi `get_formula_context(..., include_all_sources=True)`
(`alumglass/al_bom_engine/formula_validate.py:73-76`); `cost_template.js` có
`fetchValidationContext()` gửi `include_all_sources: 1`
(`alumglass/public/js/cost_template.js:224-243`).

---

## 10. Lộ trình triển khai & checklist kiểm chứng

### 10.1 Phase

| Phase | Việc | Kết quả |
|---|---|---|
| **P0 — Đo & chốt** | Viết test parity: catalog (khi chưa lọc) phải trả **đúng** tập biến `get_formula_context` hiện tại cho 4 doctype | Không đổi hành vi |
| **P1 — Doctype + API** | Tạo `AL Variable Profile`, `AL Variable Profile Rule`, `AL Variable Cross Row`; viết adapters; API `get_variable_catalog` | API chạy song song, chưa dùng |
| **P2 — Tích hợp UI** | `formula_setup.js` + `cost_template.js` chuyển sang catalog; thêm `fieldname` vào scope widget | Người dùng thấy bộ lọc |
| **P3 — Seed profile** | Seed `P_LEGACY_*` cho doctype chưa cấu hình; seed `P_BOM_CUA_DI`, `P_COST_CUA_DI` mẫu | Bắt đầu lọc thật |
| **P4 — Dọn nợ** | Bỏ hardcode Common/Row/Offset; nối hoặc xoá `AL Accessory Set.variable_set`; thống nhất `extra_vars` precedence | Ít nơi sửa khi thêm biến |
| **P5 — Runtime provenance** | Tách `engine/variable_resolution.py`; API `explain_variable` | Preview = runtime, có giải thích |

### 10.2 Checklist kiểm chứng

- [ ] Thêm 1 Cost Bucket mới → hiện trong catalog của cả 3 doctype đã gán profile (nếu rule include bucket).
- [ ] Thêm 1 `AL Variable Library` mới → chỉ hiện khi profile include và qua bộ lọc prefix/category.
- [ ] Gõ `items.` ở `AL Bom Item` → thấy đúng slug × field theo `cross_row.fields`; không thấy slug của bảng khác.
- [ ] Công thức `items.kinh_tren.width` lưu được, validate PASS, tính ra đúng số.
- [ ] Gõ cùng 1 từ khoá ở `AL Bom Set` và `AL Cost Template` → danh sách khác nhau đúng theo profile.
- [ ] Biến bị Exclude không hiện, nhưng runtime vẫn resolve nếu công thức cũ đang dùng (không làm chết dữ liệu cũ).
- [ ] Record chưa gán profile → danh sách **giống hệt** trước khi triển khai (parity test).
- [ ] Đổi `variable_profile` trên form mẹ → autocomplete đổi sau khi hết cache client (5 phút) hoặc F5 (hiện chưa có chỗ gọi `invalidate()`).
- [ ] `only_fields`: autocomplete bulk (không gửi `fieldname`) **vẫn lọc ở client**; gọi API có `fieldname` thì **server lọc rule**.
- [ ] Profile bị xoá / inactive → fallback **đường legacy** (không có profile), không lỗi trắng form. ⛔ Không có profile `P_LEGACY_*` nào được seed.

---

## 10A. Trạng thái triển khai bản vá v28_14 (2026-11-12)

> Phạm vi: **chưa commit, chưa push**; chỉ sửa working tree của
> `alumglass` (nhánh `main`) và `formula_builder` (nhánh `develop`).
> Chưa chạy `bench migrate` / test trên site vì bench hiện tại **không có
> site nào cài `alumglass`** — xem mục "Kiểm chứng đã chạy" bên dưới.

### 10A.1 Đã làm

**A. Mô hình dữ liệu mới (7 DocType, module `AL Master Data`)**

| DocType | Vai trò |
|---|---|
| `AL Variable Profile` | 1 profile = 1 bộ biến cho 1 ngữ cảnh; `default_action` INCLUDE_ALL/EXCLUDE_ALL |
| `AL Variable Profile Rule` | Luật Include/Exclude theo nguồn, tiền tố, regex, category, kiểu, `only_fields`, `require_value` |
| `AL Variable Cross Row` | Khai bảng con + slug field + field được tham chiếu chéo (`items.<slug>.<field>`) |
| `AL Variable Settings` (Single) | `default_profile`, `preview_doctype`, danh sách `common_variables` + `row_literals` (nguồn dữ liệu thay hardcode) |
| `AL Common Variable` / `AL Row Literal` | Bảng con của Settings |
| `AL Formula Field` | Sổ đăng ký field công thức (thay `FORMULA_DOCTYPE_REGISTRY` trong JS) |

**B. Catalog engine (`alumglass/variable_sources/`)**

- `registry.py` — đăng ký adapter; thêm nguồn mới = thêm 1 adapter + 1 option
  `source_kind` trong DocType Rule (không sửa engine).
- `rules.py` — **thuần Python, không import frappe**: Include/Exclude, prefix,
  regex, category, kiểu, `only_fields` (giao nguồn × rule, `hide_all` khi giao
  rỗng), `require_value`, dedupe (ưu tiên có giá trị; hợp phạm vi field), gom nhóm.
- `context.py` — nạp doc/meta/dòng con/Settings đúng 1 lần; chịu được doc mới,
  cột chưa migrate, thiếu app.
- `adapters.py` — 10 adapter: `fvb_scope`, `cost_bucket`, `variable_library_system`,
  `variable_library_user`, `variable_set`, `cost_template_line`, `formula_global`,
  `row_literal`, `common_var`, `doctype_field` + `build_references` (cross-row).
  `fvb_scope` lấy **cả** scope doctype cha và doctype dòng con, resolve dòng con
  với row hiện tại.

**C. API (`alumglass/api/variable_catalog.py`)**

- `get_variable_catalog` — danh mục cho 1 field/ngữ cảnh; trả `variables`,
  `groups`, `references`, `meta` (tổng, bị loại, trùng tên, profile, field).
- `preview_variable_catalog` — admin xem trước profile (có kiểm quyền).
- `explain_variable` — vì sao thấy/không thấy 1 biến, nguồn nào thắng.
- `get_variable_profile` — profile đang áp cho record.
- `get_row_literal_names` — tên row literal đang bật (cho cảnh báo `rule_input_expr`).

**D. Tích hợp**

- `get_formula_context(doctype, docname, fieldname, child_table, row_index,
  include_all_sources=False)`:
  - Record **có** profile → đường catalog; record **chưa** gán → đường legacy
    8 nhóm (tương thích ngược).
  - `include_all_sources=True` → **bỏ qua catalog**, dùng legacy: dành cho
    **validate**. Profile chỉ lọc gợi ý, không được làm hẹp universe hợp lệ.
- `AL Bom Set` / `AL Cost Template` / `AL Accessory Set` / `AL Alert Config` có
  field Link `variable_profile`; profile quyết định bộ biến của cả form mẹ +
  child table (catalog nhận `child_table`/`row_index`).
- `formula_setup.js`: registry động từ `AL Formula Field`; cache context theo
  `doctype::docname::child_table`; gửi `fieldname`/`child_table`; lọc
  `only_fields`/`hide_all` ở client.
- `cost_template.js`: bỏ lọc `source` cũ; inject toàn bộ biến; cache theo record.
- `formula_builder`: `$NAME` được normalize về `NAME` ở cửa vào engine (giữ
  `$snap.*` + chuỗi literal); `get_live_context` trả `applies_to_field` và gộp
  phạm vi field khi trùng tên; `get_all_global_variables` lọc `is_active=1`.
- `al_bom_engine/formula_validate.py`: validate dùng `include_all_sources=True`;
  cảnh báo (không chặn) `items.<slug>.<field>` trong `rule_input_expr`, danh sách
  field lấy từ `AL Variable Settings`.
- `engine/bom_orchestrator.py`: hợp đồng ưu tiên B1 ghi rõ; `extra_vars` +
  top-level cùng lớp user; snapshot/áp lại user input sau 1.5c.
- `system_variable_resolver.py`: `source_link_field` khai tường minh (kiểm
  fieldtype Link + đúng `options`), fallback auto-discover; query chịu được cột
  chưa migrate.

**E. Seed & migration**

- `patches/v28_14/seed_variable_catalog.py` (khai ở `[post_model_sync]`):
  - Seed `AL Variable Settings` (8 common var + 10 row literal, có `max_area_m2`).
  - Seed 11 `AL Formula Field` (6 field Bom Item, 1 Accessory, 1 Cost Template,
    3 field cha).
  - Seed 2 profile mẫu: `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`.
  - Gán profile cho record **đang trống** `variable_profile` của 2 doctype đích;
    **không** set `default_profile` (mọi doctype khác giữ nguyên legacy).
  - Idempotent: chạy lại không nhân đôi, không đè cấu hình admin đã sửa.

**F. Test thuần (không cần site)**

| Bộ | Số ca | Kết quả |
|---|---|---|
| `alumglass/tests/test_variable_catalog_rules.py` | 41 | PASS |
| `formula_builder/tests/test_dollar_normalize.py` | 15 | PASS |
| `formula_builder/tests/test_live_context_dedupe.py` | 11 | PASS |

Kiểm tra tĩnh đã chạy: `py_compile` toàn bộ file Python đã sửa/mới,
`json.load` toàn bộ JSON của `alumglass`, `node --check` 3 file JS,
`ruff --select E9,F` (theo báo cáo DEV).

### 10A.2 Chưa kiểm chứng / cần làm khi triển khai

1. **Chưa chạy `bench migrate`** — 7 DocType mới + cột `variable_profile` +
   `source_link_field` chỉ có sau migrate. Trước migrate, code đã có fallback
   (query thiếu cột → dùng danh sách cột cũ; catalog thiếu bảng → legacy),
   nhưng **chưa đo trên site thật**.
2. **Chưa chạy test Frappe/unittest trên site** — chỉ test thuần. Cần chạy trên
   site dev có `alumglass` + `formula_builder`:
   `bench --site <dev> migrate` → mở form `AL Bom Set`, `AL Cost Template`,
   `AL Accessory Set`, `AL Variable Profile` → gõ thử autocomplete, lưu thử.
3. **Asset JS** — `hooks.py` đã bump `formula_setup.js`/`cost_template.js` lên
   `v=1.2.0`; cần `bench build --app alumglass` (hoặc restart asset pipeline)
   để trình duyệt nhận bản mới.
4. **Profile mặc định gán hàng loạt** — patch gán `P_COST_TEMPLATE_DEFAULT` /
   `P_ACCESSORY_DEFAULT` cho **mọi record đang trống**. Đây là thay đổi
   *gợi ý*, không đổi số tiền; nhưng nên xem trước bằng nút "Xem trước danh
   sách biến" trên 1 record thật trước khi chạy production.
5. **Chưa commit/push** — toàn bộ thay đổi nằm ở working tree; xem
   `git status` trước khi bàn giao.

### 10A.3 Quy ước vận hành profile

- **Profile chỉ đổi danh sách gợi ý**, không đổi giá trị tính toán. Xoá/sửa
  profile không làm sai BOM đang chạy.
- **Validate dùng universe đầy đủ** (legacy): công thức cũ dùng biến ngoài
  profile vẫn lưu được; nếu muốn chặn hẳn phải thêm kiểm riêng, không dựa vào
  profile.
- Muốn thêm nguồn biến mới: viết 1 adapter trong `variable_sources/adapters.py`,
  thêm option `source_kind` vào `AL Variable Profile Rule`, thêm rule trong
  profile. Không sửa `rules.py`/`variable_catalog.py`.
- Muốn thêm field công thức mới: thêm 1 record `AL Formula Field`, không sửa JS.
- Muốn thêm common var/row literal: thêm dòng trong `AL Variable Settings`,
  không sửa Python.

---

## Phụ lục A — Bản đồ file/hàm

### A.1 Alumglass

| File | Hàm/khối | Vai trò |
|---|---|---|
| `alumglass/api/__init__.py` | `calculate_bom` `:6` | entry tính giá |
| | `get_formula_context` | autocomplete/validate — catalog (có profile) hoặc legacy 8 nhóm; `include_all_sources=True` cho validate |
| | `_get_live_context_vars` | gọi FB `get_live_context`, gửi `fieldname` |
| | `_resolve_doc_values` | resolve system var cho preview |
| | `_resolve_variable_set_name` | dò Variable Set (Link trực tiếp → AL Bom Set → product_type) |
| | `_inject_variable_set_vars` | chèn biến Variable Set |
| | `get_variable_set_for_bom` | dialog tham số BOM |
| | `_assert_formula_context_doctype` | allowlist doctype |
| | `get_allowed_formula_functions` | 3 hàm custom |
| `alumglass/api/variable_catalog.py` | `get_variable_catalog`, `preview_variable_catalog`, `explain_variable`, `get_variable_profile`, `get_row_literal_names` | API Variable Catalog |
| `alumglass/api/formula_registry.py` | `get_formula_fields` | registry field công thức từ `AL Formula Field` |
| `alumglass/variable_sources/registry.py` | `register_adapter`, `get_adapters` | đăng ký nguồn biến |
| `alumglass/variable_sources/rules.py` | `select_candidates`, `dedupe_candidates`, `build_groups` | luật lọc/dedupe thuần Python |
| `alumglass/variable_sources/context.py` | `CatalogContext` | nạp doc/meta/dòng con/Settings |
| `alumglass/variable_sources/adapters.py` | 10 adapter + `build_references` | sinh candidate + cross-row |
| `alumglass/al_master_data/doctype/al_variable_*` | 7 DocType | Profile/Rule/Cross Row/Settings/Common/Row Literal/Formula Field |
| `engine/bom_orchestrator.py` | `run` `:297` | B0→B7 |
| | `b1_gather_inputs` `:368` | precedence inputs |
| | `_resolve_system_variables` `:576` | Library + profile |
| | `_resolve_fb_context` `:703` | FB get_live_context |
| | `_resolve_user_variable_defaults` `:546` | default user var |
| | `_normalize_percent_inputs` `:514` | % → decimal |
| | `_load_accessories` `:799` | phụ kiện → dòng BOM |
| | `b2_prefetch_master_data` `:857` | master data + row literals |
| | `_get_pricing_bindings` `:1292` | scope giá |
| | `_fetch_composite_prices_via_fb` `:1561` | giá qua FB |
| | `b3_build_formulas` `:1967` | formula list |
| | `_normalize_items_ref` `:2145` | cross-row slug |
| | `b4_calculate_bom_items` `:2181` | FormulaEngine |
| | `b5_aggregate_cost_buckets` `:2315` | gom bucket |
| | `_resolve_cost_buckets_via_fb` `:2341` | aggregate_from_items |
| | `b6_calculate_cost_template` `:2432` | giá thành |
| `al_bom_engine/system_variable_resolver.py` | 3 hàm | nguồn duy nhất system var |
| `al_bom_engine/formula_validate.py` | `normalize_cross_row` `:29`, `build_known_names` `:44`, `check_formula` `:77` | validate dùng chung |
| `al_bom_engine/fb_config.py` | `get_named_constant` `:10` | đọc binding constant |
| `fb_handlers.py` | `aluminum_price_composite` `:53`, `glass_master_data` `:271` | 2 source type custom |
| `setup/install_fb_bindings.py` | `install_composite_pricing_binding` `:79`, `install_named_constant_bindings` `:139` | seed binding |
| `patches/v28_11/seed_fvb_full_from_variable_library.py` | `execute` `:121` | seed system var → FVB |
| `public/js/formula_setup.js` | `_patchContextBuilder`, `alumglass.FormulaFields` | inject context + registry động từ `AL Formula Field` |
| `public/js/cost_template.js` | `fetchContext` `:149`, `injectContext` `:171` | context cho Cost Template |
| `alumglass/doctype/overrides/quotation.js` | `_load_variable_set` `:579`, `_var_to_field` `:859`, `_render_vars_container` `:894`, `_save` `:1538` | dialog tham số BOM |

### A.2 Formula Builder

| File | Hàm | Vai trò |
|---|---|---|
| `api/formula_builder.py` | `get_live_context` `:275` | resolve binding + doc fields + crossTables + global |
| | `get_suggestions` `:45` | suggestions API (widget gốc) |
| `api/binding_scope.py` | `binding_matches_scope` `:51`, `get_scope_bindings` `:139`, `get_scope_bindings_multi` `:186` | luật scope |
| `api/data_source_registry.py` | `_register_all_to_central_registry` `:1482` | 13 built-in đầu |
| | `resolve_bindings_with_deps` `:1369` | topo sort + resolve |
| | `aggregate_from_items` `:3019` | SUMIF cho cost bucket |
| `api/source_type_registry.py` | `register_source` `:494`, `list_source_types` `:617` | registry + admin API |
| `api/variable_resolver.py` | `VariableResolver` `:148` | `$`, `FS-`, child row, snapshot |
| | `SuggestionsBuilder` `:623` | 7 nhóm gợi ý |
| `api/batch_binding_resolver.py` | `resolve_all_bindings_batch` `:634` | batch chống N+1 |
| `api/global_variable_cache.py` | `get_all_global_variables` | cache Redis |
| `table_formula_builder.py` | `normalize_global` `:81` | `items.slug.field → slug__field` |
| `public/js/formula_builder.js` | `_ContextBuilder` `:~340`, `_scope` `:753`, `_loadLiveContext` `:1828` | UI autocomplete |

---

## Phụ lục B — 21 source_type của Formula Builder

| # | source_type | Label | Config chính | AlumGlass dùng |
|---|---|---|---|---|
| 1 | `constant` | Constant Value | `value` | `DEFAULT_ACCESSORY_CATEGORY` |
| 2 | `linked_doctype_field` | Linked DocType Field | `link_field`, `target_doctype`, `target_field`, `fallback` | system var seed |
| 3 | `whole_doctype` | Whole DocType | `link_field`, `target_doctype`, `fields`, `include_child_tables` | chưa |
| 4 | `child_table_aggregate` | Child Table Aggregate | `child_table_field`, `field`, `aggregate`, `filter_expr` | có thể thay bucket Python |
| 5 | `global_default` | Global Default | `key`, `company_specific`, `company_field` | chưa |
| 6 | `session_variable` | Session Variable | `key` | chưa |
| 7 | `doctype_query` | DocType Query | `doctype`, `fieldname`, `aggregate`, `batch_key`, `formula`, `round`, `multiply` | chưa |
| 8 | `custom_function` | Custom Function | `module`, `function`, `args` | chưa |
| 9 | `dynamic_link` | Dynamic Link | `doctype_field`, `name_field`, `target_field` | chưa |
| 10 | `computed` | Computed Formula | `formula`, `dependencies`, `items` | chưa |
| 11 | `pipeline` | Pipeline | `steps[]` (source_type/source_config/output_as/merge_strategy) | chưa |
| 12 | `conditional` | Conditional | `branches[]` (condition/source_type/source_config) | chưa |
| 13 | `fallback_chain` | Fallback Chain | `chain[]` (source_type/source_config/on_failure/transform) | chưa |
| 14 | `matrix_lookup` | Matrix Lookup (2D) | `doctype`, `row_key_field`, `col_key_field`, `value_field`, `row_key`, `col_key`, `match_mode`, `filters` | chưa |
| 15 | `reuse_formula_result` | Reuse Formula Result | `formula_document`, `scope_field`, `scope_value`, `document_name`, `line_field`, `line_match`, `result_field`, `aggregation`, `filters` | chưa |
| 16 | `composite_key_lookup` | Composite Key Lookup | `doctype`, `value_field`, `key_fields`, `key_values`, `fallback_keys`, `match_mode`, `multipliers`, `filters` | dự phòng pricing (`_PRICING_SOURCE_TYPES`) |
| 17 | `range_lookup` | Range / Threshold | `doctype`, `value_field`, `input_value`, `range_from_field`, `range_to_field`, `filters` | chưa |
| 18 | `child_table_lookup` | Child Table Row Lookup | `child_table_field`, `key_field`, `key_value`, `value_field`, `filter_active_field` | chưa |
| 19 | `aggregate_from_items` | Aggregate From Items | `rows_source`, `rows_var`, `key_field`, `key_value`, `value_field`, `aggregate`, `filters`, `default_value` | Cost Bucket (B5) |
| 20 | `aluminum_price_composite` | Aluminum Price (Composite) | `price_list`, `material_category`, `pricing_mode` | `COMPOSITE_MATERIAL_PRICE` |
| 21 | `glass_master_data` | Glass Master Data | `glass_code` | rule input kính (dự phòng) |

> 19 source_type do FB đăng ký + 2 do AlumGlass đăng ký qua `hooks.py:fb_source_types`. Test chốt số lượng: `formula_builder/tests/test_registry_consistency.py:33-52`.

---

## Phụ lục C — Cấu trúc `al_bom_vars`

Lưu trên `Quotation Item.al_bom_vars` (JSON string), do dialog `_save()` ghi (`quotation.js:1538`).

```json
{
  "W_mm": 1200,
  "H_mm": 2200,
  "n_panel": 2,
  "TONG_M2": 5.28,
  "installation_height_m": 3,
  "NC_SX_PCT": 8,

  "extra_vars": {
    "do_day": 2.0,
    "he_profile": "XINGFA"
  },

  "glass_master": "KINH-CUONG-LOWE-8.38",
  "glass_master_map": {
    "KINH_1": "KINH-CUONG-LOWE-8.38",
    "KINH_2": "KINH-DAN-6.38"
  },

  "aluminum_color": "MAU-RAL-7016",
  "color_master_map": {
    "NHOM_1": "MAU-RAL-7016",
    "NHOM_2": "MAU-RAL-9006",
    "PK": "MAU-DEN"
  },

  "_accessory_set": "PK-CUA-DI-01",
  "_profile_system": "PS-XINGFA-55",
  "_cost_template": "CT-CUA-DI-2026"
}
```

| Key | Ai đọc | Ý nghĩa |
|---|---|---|
| top-level (không `_`) | `b1_gather_inputs` bước 1.5 | user input, **ưu tiên cao nhất** (áp sau Global/FB/Library) |
| `extra_vars` | `b1_gather_inputs` bước 1.5 | bảng "Biến mở rộng" — **cùng lớp ưu tiên với top-level**, không còn bị Global Variable đè |
| `glass_master` | `:444` | kính global cũ |
| `glass_master_map` | `:450-452` | kính theo vị trí |
| `aluminum_color` | `:455` | màu global cũ |
| `color_master_map` | `:456-458` | màu theo vị trí |
| `_accessory_set` / `accessory_set` | `:442-443` | override bộ phụ kiện |
| `_profile_system` | `:459` | override hệ profile |
| `_cost_template` | `:460` | override cost template |

⚠ Các key override (`_*`) là **opt-in**: không có key → giữ nguyên hành vi mặc định của BOM.

---

*Tài liệu này viết trực tiếp trong repo `alumglass`, không commit/push. Khi code thay đổi, cập nhật theo tên hàm ở Phụ lục A.*
