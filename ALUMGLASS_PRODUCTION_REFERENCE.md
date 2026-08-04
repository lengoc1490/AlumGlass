# ALUMGLASS ERP v28.8 — PRODUCTION REFERENCE

> Ngày: 2026-08-04 | Phiên bản: v28.8 | 60 Doctypes | Formula Builder v31
> **v28.7: Tối ưu hardcode → DB-driven + Performance (giảm 50% queries)**
> **v28.7.1: Nghiệp vụ chuyên sâu: price multiplier chain, lookup_rule, scrap config, height multiplier**
> **v28.8: Production hardening — composite pricing fix, immutability guard, roles, tests, audit trail**

---

## MỤC LỤC

1. [Kiến trúc tổng thể](#1-kiến-trúc-tổng-thể)
2. [Danh sách Module & Doctype](#2-danh-sách-module--doctype)
3. [Luồng dữ liệu chính](#3-luồng-dữ-liệu-chính)
4. [Cách cấu hình sản phẩm mới](#4-cách-cấu-hình-sản-phẩm-mới)
5. [Cách mở rộng hệ thống](#5-cách-mở-rộng-hệ-thống)
6. [API Reference](#6-api-reference)
7. [JS Client Scripts](#7-js-client-scripts)
8. [Nguyên tắc kiến trúc](#8-nguyên-tắc-kiến-trúc)
9. [v28.7 Change Log](#9-v287-change-log)

---

## 1. KIẾN TRÚC TỔNG THỂ

```
┌──────────────────────────────────────────────────────────────┐
│                    FORMULA BUILDER v31 (BẤT BIẾN)            │
│  FormulaEngine (DAG)  │  FlexibleFormulaEngine               │
│  BatchBindingResolver │  SnapshotManager                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ fb_source_types hook
┌──────────────────────────┴───────────────────────────────────┐
│           alumglass/fb_handlers.py (THIN LAYER ~80 dòng)     │
│  aluminum_price_composite (DATA-DRIVEN từ Dim Mapping)       │
│  glass_master_data       │  cost_bucket_aggregate            │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│         alumglass/engine/bom_orchestrator.py                 │
│  B0: Version pinning (get_cached_doc)                        │
│  B1: Gather inputs (AL Variable Library → resolve system)    │
│  B2: Batch query (Glass Master batched, Rules cached)        │
│  B3: Build formulas (fields động từ Bom Set config)          │
│  B4: FormulaEngine (safe_funcs: calc_pattern, lookup_rule..) │
│  B5: Aggregate cost buckets                                  │
│  B6: FlexibleFormulaEngine (Cost Template → GIA_VAT)         │
│  B7: Save results (SINGLE commit)                            │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│              DOCTYPE CONFIG (DB — 0 DÒNG CODE)               │
│  AL Variable Library (+source_doctype/source_field)          │
│  AL Variable Set → AL Variable Set Item (auto-fill từ Lib)   │
│  AL Bom Set (+formula_fieldnames) → AL Bom Item              │
│  AL BOM → AL BOM Version (snapshot động đủ fields)           │
│  AL Cost Bucket → AL Cost Template                           │
│  AL Profile System  │  AL Product Type                       │
│  AL Pricing Dimension  │  AL Variable Dimension Mapping      │
│  AL Slug Library  │  AL Material Category                    │
│  AL Quantity Calc Method (calc_fn lambda từ DB)              │
│  AL Calculation Rule  │  AL Dynamic Item Rule                │
└──────────────────────────────────────────────────────────────┘
```

### v28.7: Kiến trúc DATA-DRIVEN hoàn chỉnh

- **AL Variable Library** là SINGLE SOURCE OF TRUTH cho mọi biến — cả user-facing và system
- **AL Variable Dimension Mapping** + **AL Pricing Dimension** khám phá composite key động
- **AL Quantity Calc Method** dùng `calc_fn` lambda từ DB (không còn if/elif dispatch)
- **AL Bom Set.formula_fieldnames** cho phép config field nào là formula (không hardcode list)
- **AL BOM Version snapshot** tự động thu thập mọi Small Text field từ Bom Item meta
- **BomOrchestrator** dùng `get_cached_doc()` cho config doctypes, batch query, single commit

---

## 2. DANH SÁCH MODULE & DOCTYPE

### AL Master Data (11 doctypes)

| Doctype | Vai trò | v28.7 |
|---|---|---|
| **AL Variable Library** | Thư viện biến tập trung — định nghĩa 1 lần, dùng nhiều nơi | +`source_doctype`, +`source_field` |
| **AL Variable Set** | Tập biến cho 1 sản phẩm (Link → Variable Library) | |
| **AL Variable Set Item** | Dòng biến trong Variable Set (child, auto-fill từ Library) | |
| **AL Slug Library** | Định danh vật tư — dùng cho cross-row reference | |
| **AL Material Category** | Loại vật tư động — flags điều khiển validate | |
| **AL Profile System** | Hệ profile + bộ offset hình học | |
| **AL Color Standard** | Danh mục màu — composite key tra giá | |
| **AL Glass Type** | Phân loại kính | |
| **AL Glass Master** | Thông số kỹ thuật kính | |
| **AL Product Type** | Loại sản phẩm + NC/PROFIT | |
| **AL Pricing Dimension** | Đặc tính giá động — auto-sinh Custom Field | |
| **AL Variable Dimension Mapping** | Map variable → pricing dimension → composite key | **ĐÃ IMPLEMENT** (trước là stub) |

### AL BOM Engine (12 doctypes)

| Doctype | Vai trò | v28.7 |
|---|---|---|
| **AL Bom Item** | Dòng vật tư — DocType TRUNG TÂM (child của AL Bom Set) | |
| **AL Bom Set** | Tập hợp Bom Items + link Variable Set + Accessory Set | +`formula_fieldnames` |
| **AL BOM** | BOM — link Bom Set + Cost Template | |
| **AL BOM Version** | Snapshot bất biến của BOM | **Snapshot động**: tự copy mọi Small Text field |
| **AL BOM Change Log** | Nhật ký thay đổi (child) | |
| **AL Cost Bucket** | Tài khoản chi phí — 8 source types | |
| **AL Cost Template** | Master công thức giá thành | |
| **AL Cost Template Item** | Dòng công thức (child) | |
| **ConfigSnapshot** | Wrapper snapshot kết quả tính | |
| **AL Design Revision** | Thay đổi thiết kế — trigger BOM Version | |
| **AL Accessory Set** | Bộ phụ kiện (tách riêng khỏi Bom Set) | |
| **AL Accessory Item** | Dòng phụ kiện (child, có qty_formula) | |

### AL Formula Rules (8 doctypes)

| Doctype | Vai trò | v28.7 |
|---|---|---|
| **AL Calculation Rule** | CONSTANT / THRESHOLD / LOOKUP | |
| **AL Dynamic Item Rule** | Rule chọn Item động | |
| **AL Quantity Calc Method** | Pattern tính quantity | **DATA-DRIVEN**: eval calc_fn từ DB |

### Operational Modules

| Module | Doctypes |
|---|---|
| **AL Buying** | Supplier Price List, Material Plan, Cost Variance |
| **AL Stock** | Project Warehouse Map |
| **AL Manufacturing** | Cutting Standard, Cutting Plan (Alu+Glass), Production Order Bridge |
| **AL Construction** | Installation Team, Site Survey, Installation Order/Progress/Cost, Change Order, Handover, Punchlist |
| **AL Account** | Project Profitability Snapshot, Project Financial Config |
| **AL Quality** | Warranty Policy |
| **AL AI** | Suggestion Log, Interaction Log, Alert Config |

---

## 3. LUỒNG DỮ LIỆU CHÍNH

### 3.1 Tạo sản phẩm mới (1 lần)

```
1. AL Variable Library: định nghĩa biến (W_mm, H_mm, n_panel...)
   → System vars (OFFSET, NC_PCT...) có source_doctype + source_field
2. AL Slug Library: định nghĩa slug (khung_ngang_tren, kinh_tren...)
3. AL Material Category: định nghĩa loại vật tư (NHOM, KINH, VTP...)
4. AL Quantity Calc Method: định nghĩa pattern (LENGTH_TO_WEIGHT, AREA...)
   → calc_fn là Python lambda, eval động từ DB
5. AL Cost Bucket: định nghĩa bucket (VL_NHOM, TONG_VL, GIA_VAT...)
6. AL Cost Template: định nghĩa công thức giá (14 dòng)
7. AL Variable Set VS-XXX: chọn biến từ Library cho sản phẩm
   → Variable Set Item tự động auto-fill từ Library (before_save)
8. AL Accessory Set ACC-XXX: chọn phụ kiện cho sản phẩm
9. AL Bom Set BS-XXX: nhập 14-17 dòng Bom Items + link VS + ACC
   → formula_fieldnames: config các field nào là formula
10. AL BOM BOM-XXX: link Bom Set + Cost Template
11. AL BOM Version: Publish → auto-snapshot (tự động copy mọi Small Text field)
```

### 3.2 Báo giá (hàng ngày) — v28.7 flow

```
1. Tạo Quotation → chọn khách hàng
2. Thêm Quotation Item → chọn Item sản phẩm (CDMQ-2C)
3. Chọn AL BOM → auto-load Variable Set
4. Bấm 📐 Tham số BOM → dialog hiển thị fields động từ Variable Set + System vars
5. Nhập W=2400, H=2600, n_panel=2, color=WHITE...
6. Bấm 💾 Lưu & Tính giá
7. BomOrchestrator chạy 7 phase:
   B0: get_cached_doc AL BOM Version (Redis cache 3600s)
   B1: Resolve system vars từ AL Variable Library (source_doctype.source_field)
   B2: Batch query ALL Items, Prices, Glass Masters, Rules (1 query/type)
   B3: Build formulas — field list từ Bom Set.formula_fieldnames
   B4: FormulaEngine tính Bom Items (DAG + topo sort)
   B5: Aggregate cost buckets
   B6: FlexibleFormulaEngine tính Cost Template → GIA_VAT
   B7: Save results (1 set_value + 1 commit)
8. Kết quả hiển thị TOÀN BỘ cost_template keys động trong dialog
```

### 3.3 System Variables — Cơ chế resolve mới (v28.7)

```
AL Variable Library (is_system=1, source_doctype, source_field)
        │
        ├─ OFFSET_FRAME  → AL Profile System.offset_frame
        ├─ OFFSET_GLASS  → AL Profile System.offset_glass
        ├─ NC_SX_PCT     → AL Product Type.nc_pct
        ├─ PROFIT_MARGIN → AL Product Type.profit_margin
        ├─ VAT_RATE      → Formula Global Variable (default_value fallback)
        └─ OH_VC_PCT     → Formula Global Variable (default_value fallback)

Engine đọc từ AL Variable Library → batch query theo source_doctype → resolve giá trị
Fallback: default_value từ Library → Calculation Rule CONSTANT
```

---

## 4. CÁCH CẤU HÌNH SẢN PHẨM MỚI

### Ví dụ: Thêm "Cửa sổ 1 cánh mở quay"

```
Bước 1: Tạo Variable Set VS-CS1C
  → Chọn biến từ AL Variable Library: W_mm, H_mm, n_panel=1, aluminum_color...

Bước 2: Tạo Accessory Set ACC-CS1C (nếu cần)
  → tay_nam, khoa, ban_le (qty_formula=roundup(H_mm/700,0)*1)

Bước 3: Tạo Bom Set BS-CS1C
  → Nhập Bom Items (khung, cánh, kính, nẹp...)
  → Link variable_set=VS-CS1C, default_accessory_set=ACC-CS1C
  → formula_fieldnames=["width","height","qty","show_condition","item_condition_formula","rule_input_expr"]

Bước 4: Tạo BOM BOM-CS1C
  → Link bom_set=BS-CS1C, cost_template=CT-01-STANDARD

Bước 5: Publish BOM Version
  → Tự động snapshot (mọi Small Text field được copy)

TỔNG: 0 dòng code Python/JS
```

### Thêm ngành mới (THÉP)

```
1. AL Material Category: THÉP, has_weight=1, requires_price_base_item=1
2. AL Slug Library: thanh_ngang_thep, thanh_dung_thep...
3. AL Variable Library: thêm biến nếu cần (steel_grade...)
   → System vars: source_doctype="AL Product Type", source_field="..."
4. AL Bom Set mới + AL BOM mới
→ 0 dòng code
```

---

## 5. CÁCH MỞ RỘNG HỆ THỐNG

| Muốn thêm... | Cần làm | Sửa code? |
|---|---|---|
| Hệ profile mới | 1 record AL Profile System | ❌ |
| Loại vật tư mới | 1 record AL Material Category | ❌ |
| Cost bucket mới | 1 record AL Cost Bucket + 1 dòng Cost Template | ❌ |
| Pattern tính mới | 1 record AL Quantity Calc Method (calc_fn lambda) | ❌ |
| Biến mới (user) | 1 record AL Variable Library → thêm vào Variable Set | ❌ |
| Biến mới (system) | 1 record AL Variable Library + source_doctype/source_field | ❌ |
| Rule chọn Item mới | 1 record AL Dynamic Item Rule | ❌ |
| Đặc tính giá mới | 1 record AL Pricing Dimension + 1 Mapping | ❌ |
| Field formula mới | 1 dòng JSON trong Bom Set.formula_fieldnames | ❌ |
| Data source type mới | 1 hàm fb_handlers.py + 1 dòng fb_source_types | ✅ ~10 dòng |
| Sản phẩm mới | Bom Set + Variable Set + Accessory Set | ❌ |
| Ngành mới | Material Category + Slug Library + Bom Set | ❌ |

---

## 6. API REFERENCE

| Endpoint | Mục đích | v28.7 |
|---|---|---|
| `alumglass.api.calculate_bom(qi_name)` | Tính BOM cho Quotation Item | Response: toàn bộ cost_template keys |
| `alumglass.api.preview_cost_template(code, inputs)` | Preview Cost Template | |
| `alumglass.api.get_variable_set_for_bom(bom_code)` | Lấy biến từ Variable Set + System vars từ Library | **DATA-DRIVEN**: system vars từ DB |
| `alumglass.api.get_slug_info(slug)` | Lấy thông tin Slug Library | |
| `alumglass.api.resolve_item_rule(rule, input)` | Tra cứu Dynamic Item Rule | |
| `alumglass.api.get_bom_structure(bom_code)` | Lấy toàn bộ cấu trúc BOM | |

### API Response Format (v28.7)

```json
{
  "buckets": {
    "VL_NHOM": 8500000,
    "VL_KINH": 3200000,
    "VL_VTP": 450000,
    ...
  },
  "cost_template": {
    "TONG_VL": 12150000,
    "NC_SX": 972000,
    "NC_LD": 1458000,
    "TONG_NC": 2430000,
    "OH_VC": 364500,
    "OH_QLY": 437850,
    "TONG_OH": 802350,
    "GIA_THANH": 15382350,
    "PROFIT": 2461176,
    "GIA_BAN": 17843526,
    "DON_GIA_M2": 2854964,
    "VAT": 1784352,
    "GIA_VAT": 19627878
  },
  "lines": [
    {"slug":"khung_ngang_tren","item_code":"XF55-KB-20","width":2400,...},
    ...
  ]
}
```

Client tự chọn key cần hiển thị — không còn phụ thuộc vào engine return format.

---

## 7. JS CLIENT SCRIPTS

| Script | Chức năng | v28.7 |
|---|---|---|
| `formula_setup.js` | Autocomplete formula cho AL Bom Set, AL Cost Template, AL Alert Config... | |
| `bom_dialog.js` | Dialog hiển thị kết quả tính BOM | **DYNAMIC**: hiển thị toàn bộ cost_template keys |
| `cost_template.js` | Preview Cost Template | **PROMPT**: user nhập test values thay vì mock data |
| `quotation_item_dialog.js` | Dialog nhập tham số BOM (động từ Variable Set + System vars) | |
| `doctype/overrides/quotation.js` | Nút 📐 Tham số + 💰 Tính giá trên Quotation form | |
| `doctype/overrides/sales_order.js` | Formula Builder integration cho Sales Order | |

---

## 8. NGUYÊN TẮC KIẾN TRÚC

1. **Zero hardcode**: Mọi giá trị từ DB. Code chỉ là framework.
2. **FB cho toán**: FormulaEngine (B4) + FlexibleFormulaEngine (B6) — không eval()
3. **ERPNext core**: Item, Quotation, Work Order, Batch, GL Entry — custom fields mỏng
4. **1 nguồn sự thật**: Variable Library → Variable Set → Bom Item → Dialog
5. **Config > Code**: Cost Bucket mới = JSON config, không code Python
6. **Batch query**: BomOrchestrator B2 gom query, không N+1
7. **Immutable snapshot**: BOM Version snapshot bất biến, tái lập được
8. **Cross-row**: items.kinh_tren.width → DAG tự sắp xếp thứ tự
9. **Pricing Dimension + Dim Mapping**: Composite key giá động, auto-sinh Custom Field
10. **Accessory Set riêng**: Phụ kiện tách khỏi Bom Items, qty_formula dùng biến chung
11. **System vars trong Library**: `is_system=1` + `source_doctype`/`source_field` → 0 hardcode
12. **calc_fn từ DB**: AL Quantity Calc Method lưu lambda, engine eval động
13. **Snapshot động**: AL BOM Version tự copy mọi Small Text field từ Bom Item meta
14. **Single commit**: B7 ghi tất cả kết quả trong 1 transaction
15. **get_cached_doc**: Config doctypes dùng Redis cache, tự invalidate khi save

---

## 9. v28.7 CHANGE LOG

### Ngày: 2026-08-03 | Từ v28.6 → v28.7

### A. Xóa Hardcode — Chuyển vào DB (6 điểm)

#### A1. System Variables: SCOPED_VAR_SOURCES → AL Variable Library
- **File**: `al_variable_library.json` (+`source_doctype`, +`source_field`), `bom_orchestrator.py`
- **Trước**: `SCOPED_VAR_SOURCES` dict hardcode 7 mappings (OFFSET_FRAME→AL Profile System.offset_frame...)
- **Sau**: AL Variable Library có `source_doctype` + `source_field`. Engine batch query Library → resolve động.
- **Kết quả**: Thêm 1 system variable mới = 1 record Library, 0 dòng code.

#### A2. API System Vars: Hardcode list → DB Query
- **File**: `api/__init__.py` (`get_variable_set_for_bom`)
- **Trước**: 10 system variables hardcode trong Python list
- **Sau**: Query `AL Variable Library` filter `is_system=1` → merge vào response
- **Kết quả**: System variable mới tự động xuất hiện trong API response.

#### A3. Composite Key Pricing: Hardcode fields → Dim Mapping
- **File**: `fb_handlers.py`, `al_variable_dimension_mapping.py` (implemented từ stub)
- **Trước**: `aluminum_price_composite` hardcode 4 custom field names + defaults
- **Sau**: Đọc `AL Variable Dimension Mapping` → `AL Pricing Dimension.custom_fieldname` → build filter động
- **Kết quả**: Thêm pricing dimension mới = 1 Pricing Dimension + 1 Mapping, 0 dòng code.

#### A4. Response Format: 4 keys → Toàn bộ cost_template
- **File**: `bom_orchestrator.py` (`_build_response`)
- **Trước**: Chỉ trả về `gia_vat`, `gia_ban`, `tong_vl`, `tong_nc`
- **Sau**: Trả về toàn bộ `cost_result` dict (TONG_OH, GIA_THANH, PROFIT, DON_GIA_M2, VAT...)
- **Kết quả**: Client hiển thị được mọi cost bucket mới mà không cần sửa engine.

#### A5. Formula Fields: Hardcode list → Bom Set config + Dynamic meta
- **File**: `al_bom_set.json` (+`formula_fieldnames`), `bom_orchestrator.py`, `al_bom_version.py`
- **Trước**: `BOM_ITEM_FORMULA_FIELDS = ["width","height","qty",...]` hardcode trong Python
- **Sau**: 
  - Bom Set có `formula_fieldnames` (JSON array) → config field nào là formula
  - Fallback: đọc mọi Small Text field từ `AL Bom Item` doctype meta
  - BOM Version snapshot tự động copy mọi Small Text field
- **Kết quả**: Thêm field formula mới vào Bom Item → thêm vào `formula_fieldnames` trong Bom Set, 0 dòng code.

#### A6. Quantity Calc Dispatch: if/elif → calc_fn từ DB
- **File**: `al_quantity_calc_method.py`
- **Trước**: `lookup_calc_pattern` dùng if/elif dispatch cho 4 pattern (LENGTH_TO_WEIGHT, AREA, LENGTH_ONLY, COUNT)
- **Sau**: Đọc `calc_fn` lambda từ `AL Quantity Calc Method` record, eval với restricted namespace
- **Kết quả**: Thêm pattern tính mới = 1 record với calc_fn lambda, 0 dòng code.

### B. Performance (giảm ~50% queries: 24 → ~10-12)

#### B1. Single Commit (B7)
- **Trước**: 5 `set_value` + 1 raw SQL INSERT + 3 `commit()` = 9 roundtrips
- **Sau**: 1 `set_value({field1, field2, ...})` + `frappe.get_doc().insert()` + 1 `commit()`
- **Tiết kiệm**: ~6 queries

#### B2. get_cached_doc cho config doctypes
- **Trước**: `frappe.get_doc()` gọi DB mỗi lần cho BOM, BOM Version, Bom Set, Profile System, Product Type, Calculation Rule
- **Sau**: `frappe.get_cached_doc()` — Frappe Redis cache 3600s, tự invalidate khi save
- **Tiết kiệm**: 5-8 queries (sau lần gọi đầu)

#### B3. Batch Glass Master query
- **Trước**: `frappe.db.get_value("AL Glass Master", ...)` trong vòng lặp mỗi KINH item (N+1)
- **Sau**: 1 `get_all("AL Glass Master", {"name": ("in", codes)})` gom tất cả codes
- **Tiết kiệm**: K-1 queries (K = số dòng KINH)

#### B4. Cost Bucket load tối ưu
- **Trước**: `get_all("AL Cost Bucket", pluck="name")` load TOÀN BỘ bảng chỉ để set default 0.0
- **Sau**: Parse Cost Template formulas → extract bucket codes được reference → chỉ set những code đó
- **Tiết kiệm**: 1 query + tránh load toàn bộ buckets

#### B5. Loại bỏ duplicate loads
- **Trước**: B0 load QI, B1 lại `get_value` al_bom_vars; B0 path B load AL BOM, B1 lại load lần nữa
- **Sau**: Dùng `self._qi_doc` và `self._bom_doc` cache xuyên suốt engine
- **Tiết kiệm**: 2 queries

### C. JS Client

#### C1. BOM Dialog hiển thị động
- **File**: `bom_dialog.js`
- **Trước**: Chỉ hiển thị 4 keys tĩnh (gia_vat, gia_ban, tong_vl, tong_nc)
- **Sau**: Hiển thị TOÀN BỘ `cost_template` keys, phân loại detail/subtotal, format VND

#### C2. Cost Template Preview bỏ mock data
- **File**: `cost_template.js`
- **Trước**: Mock data hardcode `W_mm: 2400, H_mm: 2600...`
- **Sau**: Prompt dialog cho user nhập test values JSON

### D. Schema Changes

| Doctype | Thay đổi |
|---|---|
| `AL Variable Library` | +`source_doctype` (Link→DocType), +`source_field` (Data) |
| `AL Bom Set` | +`formula_fieldnames` (Small Text, JSON) |
| `AL Variable Dimension Mapping` | Python controller implemented (trước là `pass`) |
| `AL BOM Version` | `_take_snapshots()`: dynamic copy mọi Small Text field từ Bom Item meta |

### E. Tổng kết metrics

| Metric | v28.6 | v28.7 | Cải thiện |
|---|---|---|---|
| Điểm hardcode trong engine | ~12 | 0 | ✅ 100% |
| DB queries / calculate_bom | ~24 | ~10-12 | ✅ -50% |
| Dòng code core | ~2,200 | ~2,200 | ≈ (chất lượng tăng) |
| System vars thêm mới | Sửa code | 1 DB record | ✅ |
| Pattern tính thêm mới | Sửa code | 1 DB record | ✅ |
| Field formula thêm mới | Sửa code | Config JSON | ✅ |
| Composite key thêm mới | Sửa code | 2 DB records | ✅ |
| Response keys | 4 cố định | Toàn bộ động | ✅ |

### F. v28.7.1 — Nghiệp vụ chuyên sâu (2026-08-03)

#### F1. Price Multiplier Chain
- `aluminum_price_composite` hỗ trợ mode `multiplier_chain`: giá gốc × ∏(hệ số)
- `AL Color Standard` + `price_multiplier`: WHITE=1.0, DARK=1.08, GRAY=1.05, GO=1.20
- `AL Variable Dimension Mapping` + `price_multiplier`: mỗi dimension có hệ số riêng
- Cấu hình qua `source_config.pricing_mode` trong Cost Bucket binding

#### F2. lookup_rule Safe Function
- FormulaEngine hỗ trợ `lookup_rule("RULE-CODE", value)` trong mọi formula
- Gọi `AL Calculation Rule.resolve()` — hỗ trợ CONSTANT, THRESHOLD, LOOKUP
- `RULE-BANLE-QTY`: định mức bản lề theo chiều cao (THRESHOLD)
- `RULE-HEIGHT-MULT`: hệ số nhân công theo độ cao (THRESHOLD)
- Dùng trong Bom Item formula, Accessory qty_formula, Cost Template

#### F3. Installation Height Multiplier
- `installation_height_m` thêm vào Variable Library (user variable)
- Cost Template NC_LD: `NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)`
- Hệ số: <10m=1.0, 10-30m=1.2, 30-60m=1.5, >60m=2.0

#### F4. Material Scrap/Waste
- `AL Material Category` + `default_scrap_pct` (% hao hụt)
- Engine tự động inject `{slug}__scrap_pct` vào context
- Bom Item formula tham chiếu: `qty = base_qty * (1 + scrap_pct/100)`
- Seed: NHOM=3%, KINH=5%, VTP=2%, PK=0%

| Schema | Field | Type | Doctype |
|---|---|---|---|
| +`price_multiplier` | Float (default 1.0) | AL Color Standard, AL Variable Dimension Mapping |
| +`default_scrap_pct` | Float (default 0) | AL Material Category |
| +`lookup_rule` | safe_func trong FormulaEngine | bom_orchestrator.py |
| +2 Calculation Rules | THRESHOLD | RULE-BANLE-QTY, RULE-HEIGHT-MULT |
| +1 Variable | Float | installation_height_m |

---

## 10. v28.8 CHANGE LOG — Production Hardening

### Ngày: 2026-08-04 | Từ v28.7.1 → v28.8

### G. Composite Key Pricing Fix (CRITICAL)

**Vấn đề:** `BomOrchestrator.b2_prefetch_master_data()` query Item Price chỉ theo `(item_code, price_list)`, bỏ qua composite fields (`custom_pd_mau_sac`, `custom_pd_xuat_xu`...). Hậu quả:
1. Mọi màu của cùng item_code ra cùng 1 giá
2. Dict `prices[item_code]` bị ghi đè → non-deterministic

**Giải pháp:**
- Thêm 3 methods vào `BomOrchestrator`:
  - `_get_dim_fieldnames()`: Map variable_name → custom_fieldname (data-driven từ AL Variable Dimension Mapping + AL Pricing Dimension)
  - `_fetch_composite_prices()`: Batch query Item Price với composite fields, group theo item_code
  - `_match_composite_price()`: Chọn dòng khớp nhiều composite fields nhất, fallback dòng "trần"
- `len(rows) == 1` → trả thẳng, giữ nguyên hành vi cho item không có composite key

**File:** `engine/bom_orchestrator.py` (+`_dim_fieldname_cache`, +~90 lines, thay thế Batch Query #2)

### H. Required Apps Declaration (MEDIUM)

**Vấn đề:** `hooks.py` không khai báo `required_apps = ["formula_builder"]` → cài trên site thiếu formula_builder pass install nhưng crash runtime.

**Giải pháp:** Thêm `required_apps = ["formula_builder"]` vào `hooks.py`. Frappe tự chặn install nếu thiếu dependency.

**File:** `hooks.py` (+1 line)

### I. AL BOM Version Immutability Guard (MEDIUM)

**Vấn đề:** Không có guard chặn sửa `bom_set_snapshot`/`cost_template_snapshot` sau khi `workflow_state = "Published"` → phá vỡ cam kết "immutable version".

**Giải pháp:**
- Thêm `validate()` method gọi `_guard_published_immutability()`
- So sánh snapshot cũ vs mới — nếu đã Published mà thay đổi → `frappe.throw()`
- Chỉ cho phép đổi `workflow_state` (vd Published → Retired)

**File:** `al_bom_version.py` (+`validate()`, +`_guard_published_immutability()`)

### J. Role-Based Access Control (CRITICAL for Production)

**Vấn đề:** 60 DocType chỉ có role `System Manager` → nhân viên bán hàng cần System Manager để tạo Quotation.

**Giải pháp:**
- Tạo 4 role nghiệp vụ: AL Sales User, AL BOM Manager, AL Site Engineer, AL Project Accountant
- `install_roles.py`: Cài đặt DocPerm cho tất cả AL doctypes + core ERPNext doctypes
- Module permission matrix: mỗi module → role → quyền cụ thể
- Self-check: báo WARNING nếu config module name không khớp doctype thực tế
- Role fixtures trong `hooks.py` để bench migrate tự động sync

**Files:**
- `setup/install_roles.py` (new, ~200 lines)
- `fixtures/roles.json` (new)
- `hooks.py` (+Role fixtures, +`_after_install()`)

### K. Audit Trail (track_changes)

**Vấn đề:** `track_changes` không được set trên các doctype quan trọng.

**Giải pháp:** Bật `track_changes: 1` cho:
- `AL BOM Version`
- `AL Calculation Rule`
- `AL Dynamic Item Rule Version`

**Files:** 3 doctype JSON files

### L. Pricing Dimension Fieldname Casing Fix

**Vấn đề:** `custom_fieldname = f"custom_pd_{self.dimension_code}"` không lowercase → `MAU_SAC` tạo `custom_pd_MAU_SAC` (chữ hoa).

**Giải pháp:** `self.dimension_code.lower()` khi build fieldname.

**File:** `al_pricing_dimension.py` (sửa 1 dòng)

### M. Test Suite Migration

**Vấn đề:** `run_test.py` nằm ngoài CI framework → `bench run-tests` không chạy được.

**Giải pháp:**
- Tạo thư mục `alumglass/tests/`
- `test_bom_orchestrator.py`: 3 integration tests (CDMQ-2C golden value, CDMQ-4C runs, CDMQ-4C dynamic rules)
- `test_composite_pricing.py`: 2 tests (different color = different price, deterministic lookup)

**Files:**
- `tests/__init__.py` (new)
- `tests/test_bom_orchestrator.py` (new, ~180 lines)
- `tests/test_composite_pricing.py` (new, ~180 lines)

### N. Documentation Update

- `TONG_QUAN_KIEN_TRUC.md`: Tài liệu tổng quan kiến trúc mới (comprehensive)
- `HUONG_DAN_TRIEN_KHAI.md`: Hướng dẫn triển khai từng bước
- `ALUMGLASS_PRODUCTION_REFERENCE.md`: Cập nhật v28.8
- `README.md`: Cập nhật trạng thái hiện tại
- `CAU_TRUC_MODULE_VA_DOCTYPE.md`: Sửa tên module cho khớp thực tế

### Tổng kết v28.8

| Metric | v28.7.1 | v28.8 | Thay đổi |
|---|---|---|---|
| Composite pricing hoạt động | ❌ (handler có nhưng không gọi) | ✅ (engine gọi đúng) | Bug fix |
| Role-based access | ❌ (chỉ System Manager) | ✅ (4 roles nghiệp vụ) | Production-ready |
| Immutability guard | ❌ (có thể sửa snapshot) | ✅ (validate chặn) | Security |
| Audit trail | ⚠️ (track_changes=0) | ✅ (3 doctypes quan trọng) | Compliance |
| Test suite | ⚠️ (run_test.py thủ công) | ✅ (FrappeTestCase, CI-ready) | Quality |
| Dependency check | ❌ (crash runtime) | ✅ (required_apps) | DX |
| Fieldname casing | ⚠️ (chữ hoa) | ✅ (lowercase) | Consistency |
| Tài liệu | 5 docs | 7 docs (thêm TONG_QUAN + HUONG_DAN) | Documentation |
| Dòng code thay đổi | — | +~800 / -~20 | — |
| Files thay đổi | — | 12 files (6 sửa, 6 mới) | — |

### Kiểm chứng

```bash
# 1. Apply schema
cd /home/lengoc/frappe-bench && bench migrate

# 2. Run all tests
bench --site <site> run-tests --app alumglass

# 3. Verify composite pricing
bench --site <site> run-tests --app alumglass \
    --module alumglass.tests.test_composite_pricing

# 4. Verify golden case
bench console
>>> from alumglass.run_test import main
>>> main()
# Expected: GIA_VAT ≈ 22,717,289 VND
```
