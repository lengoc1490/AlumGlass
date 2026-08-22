# TỔNG QUAN KIẾN TRÚC — ALUMGLASS ERP

> **Phiên bản:** v28.8 | **Ngày:** 2026-08-04 | **60 DocType | 10 Module | Formula Builder v31**
> **Trạng thái:** Production-ready với đầy đủ validation, test, role-based permissions

---

## MỤC LỤC

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc phân lớp](#2-kiến-trúc-phân-lớp)
3. [Luồng tính toán BOM (BomOrchestrator 7-Phase)](#3-luồng-tính-toán-bom-bomorchestrator-7-phase)
4. [Luồng nghiệp vụ đầu-cuối](#4-luồng-nghiệp-vụ-đầu-cuối)
5. [Hệ thống biến (Variable System)](#5-hệ-thống-biến-variable-system)
6. [Cơ chế Composite Key Pricing](#6-cơ-chế-composite-key-pricing)
7. [Hệ thống Role & Permission](#7-hệ-thống-role--permission)
8. [Danh sách Module & Doctype](#8-danh-sách-module--doctype)
9. [Nguyên tắc thiết kế](#9-nguyên-tắc-thiết-kế)
10. [Performance & Cache Strategy](#10-performance--cache-strategy)
11. [Cách mở rộng hệ thống](#11-cách-mở-rộng-hệ-thống)

---

## 1. TỔNG QUAN HỆ THỐNG

AlumGlass ERP là hệ thống ERP chuyên ngành nhôm kính xây dựng, xây dựng trên nền tảng **Frappe/ERPNext 14.92.14** + **Formula Builder v31**. Hệ thống được thiết kế theo nguyên tắc **DATA-DRIVEN** — mọi logic nghiệp vụ đến từ database, code chỉ là framework trung gian.

### Sơ đồ tổng thể

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         A L U M G L A S S   E R P                       │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                  FORMULA BUILDER v31 (ENGINE)                    │   │
│  │  FormulaEngine (DAG + Topo Sort)  │  FlexibleFormulaEngine       │   │
│  │  BatchBindingResolver             │  SnapshotManager             │   │
│  │  SourceTypeRegistry               │  DotToSubscriptTransformer   │   │
│  └────────────────────────────┬─────────────────────────────────────┘   │
│                               │ fb_source_types hook                    │
│  ┌────────────────────────────┴─────────────────────────────────────┐   │
│  │             fb_handlers.py (THIN LAYER ~180 lines)               │   │
│  │  aluminum_price_composite    │  glass_master_data                │   │
│  │  cost_bucket_aggregate       │  (exact_match + multiplier_chain) │   │
│  └────────────────────────────┴─────────────────────────────────────┘   │
│                               │                                         │
│  ┌────────────────────────────┴─────────────────────────────────────┐   │
│  │           BomOrchestrator (7-PHASE CALCULATION ENGINE)           │   │
│  │  B0: Version Pinning         B1: Gather Inputs                   │   │
│  │  B2: Pre-fetch Master Data   B3: Build Formulas                  │   │
│  │  B4: Calculate Bom Items     B5: Aggregate Cost Buckets          │   │
│  │  B6: Calculate Cost Template B7: Save Results (Single Commit)    │   │
│  └────────────────────────────┴─────────────────────────────────────┘   │
│                               │                                         │
│  ┌────────────────────────────┴─────────────────────────────────────┐   │
│  │                   DOCTYPE CONFIG LAYER (DB)                      │   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐│   │
│  │  │AL Master Data│  │AL BOM Engine │  │AL Formula Rules          ││   │
│  │  │(12 doctypes) │  │(12 doctypes) │  │(8 doctypes)              ││   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘│   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐│   │
│  │  │AL Buying(1)  │  │AL Stock(1)   │  │AL Manufacturing(5)       ││   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘│   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐│   │
│  │  │AL Construction│ │AL Account    │  │AL Quality + AL AI        ││   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘│   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              ERPNext CORE (Tái sử dụng)                          │   │
│  │  Quotation │ Sales Order │ Item │ Item Price │ BOM │ Work Order  │   │
│  │  Production Plan │ Material Request │ RFQ │ Supplier Quotation   │   │
│  │  Purchase Order │ Subcontracting Order │ Inventory Dimension     │   │
│  │  Batch │ Serial No │ GL Entry │ Journal Entry │ Payment Entry    │   │
│  │  Project │ Task │ Timesheet │ Quality Inspection │ Warranty Claim│   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Các con số chính

| Metric | Giá trị |
|---|---|
| **Số Module** | 11 module AlumGlass (10 có doctype + 1 AL Selling dùng ERPNext core) |
| **Số DocType** | 53 triển khai (v28.9: bỏ 5 DocType trùng core, +1 AL Glass Thickness cho Inventory Dimension) |
| **Số Role nghiệp vụ** | 4 (AL Sales User, AL BOM Manager, AL Site Engineer, AL Project Accountant) |
| **Số phase tính toán** | 7 (B0 → B7) |
| **DB queries / lần tính** | ~10-12 (giảm 50% từ v28.6) |
| **API endpoints** | 5 |
| **JS client scripts** | 6 |
| **Dòng code fb_handlers** | ~180 lines (thin layer) |
| **Dòng code BomOrchestrator** | ~690 lines (engine) |

---

## 2. KIẾN TRÚC PHÂN LỚP

```
TẦNG 5: BUSINESS MODULES (ERPNext Core + Custom Fields)
        Quotation, Sales Order, Purchase, Stock, Manufacturing, Construction...
        
TẦNG 4: ORCHESTRATION (alumglass/engine/)
        BomOrchestrator — 7-phase engine tính BOM
        API layer (alumglass/api/)
        
TẦNG 3: FB HANDLERS (alumglass/fb_handlers.py)
        Thin layer đăng ký custom data sources với Formula Builder
        aluminum_price_composite, glass_master_data, cost_bucket_aggregate
        
TẦNG 2: FORMULA BUILDER ENGINE (formula_builder app - BẤT BIẾN)
        FormulaEngine (DAG + topo sort), FlexibleFormulaEngine
        BatchBindingResolver, SnapshotManager, SourceTypeRegistry
        
TẦNG 1: DOCTYPE CONFIG (Database)
        AL Variable Library, AL Bom Set, AL Bom Item, AL Cost Bucket,
        AL Cost Template, AL Pricing Dimension, AL Calculation Rule...
```

### Nguyên tắc phân lớp

- **Tầng 1-2 là bất biến**: Không chứa logic nghiệp vụ nhôm kính
- **Tầng 3 là thin layer**: Chỉ map dữ liệu, không tự tính toán
- **Tầng 4 là orchestration**: Điều phối flow, không hardcode nghiệp vụ
- **Tầng 5 là business**: Tận dụng ERPNext core, chỉ thêm custom fields

---

## 3. LUỒNG TÍNH TOÁN BOM (BomOrchestrator 7-Phase)

Đây là trái tim của hệ thống. Khi user bấm "Tính giá" trên Quotation Item:

```
QUOTATION ITEM
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ B0: VERSION PINNING                                             │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  Quotation Item (al_bom, al_bom_version)                 │
│ Output: AL BOM Version doc (cached)                             │
│                                                                 │
│ 1. Đọc al_bom_version từ Quotation Item                         │
│ 2. Nếu không có version → đọc current_version từ AL BOM         │
│ 3. get_cached_doc("AL BOM Version") → Redis cache 3600s         │
│ 4. Nếu không có version → frappe.throw()                        │
│                                                                 │
│ Query count: 1 (cached after first call)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B1: GATHER INPUTS                                               │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  AL BOM Version, Quotation Item                          │
│ Output: self.inputs dict (~50-80 keys)                          │
│                                                                 │
│ Step 1: Đọc user inputs từ al_bom_vars JSON                     │
│   → W_mm=2400, H_mm=2600, n_panel=2, aluminum_color=WHITE...    │
│                                                                 │
│ Step 2: Global Variables từ Formula Builder                     │
│   → frappe.get_all("Formula Global Variable")                   │
│   → VAT_RATE=0.1, OH_VC_PCT=0.03...                             │
│                                                                 │
│ Step 3: Resolve System Variables (DATA-DRIVEN)                  │
│   → Đọc AL Variable Library (filter: is_system=1)               │
│   → Batch query theo source_doctype:                            │
│     • AL Profile System → OFFSET_FRAME=48, OFFSET_GLASS=90...   │
│     • AL Product Type → NC_SX_PCT=0.08, PROFIT_MARGIN=0.16...   │
│   → Fallback: default_value từ Library                          │
│   → Fallback cuối: AL Calculation Rule CONSTANT                 │
│                                                                 │
│ Step 4: Merge — user inputs ghi đè system vars                  │
│                                                                 │
│ Query count: 2-3                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B2: PRE-FETCH MASTER DATA (BATCH QUERY)                         │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  bom_set_snapshot (JSON từ BOM Version)                  │
│ Output: self.row_literals dict (per BOM line)                   │
│                                                                 │
│ Step 1: Parse snapshot → self.bom_items list                    │
│                                                                 │
│ Step 2: Gom tất cả codes để query 1 lần:                        │
│   → item_codes, price_base_items, glass_master_codes, rule_codes│
│                                                                 │
│ Batch Query #1: Item weights                                    │
│   SELECT name, weight_per_unit FROM tabItem                     │
│   WHERE name IN (all item_codes)                                │
│                                                                 │
│ Batch Query #2: Item Prices ★ COMPOSITE-KEY AWARE (v28.8) ★    │
│   → _fetch_composite_prices() thay vì query đơn giản            │
│   → Đọc AL Variable Dimension Mapping + AL Pricing Dimension    │
│   → v28.9: giữ composite key (màu/xuất xứ... trên mã nhôm đại   │
│     diện) — giá bán/tham chiếu dialog Quotation; độc lập kho     │
│   → _match_composite_price(): chọn dòng khớp nhất               │
│   → Fallback: dòng "trần" không set composite field             │
│                                                                 │
│ Batch Query #3: Glass Masters (gom 1 query, tránh N+1)          │
│  SELECT name, total_thick_mm, glass_type FROM tabAL Glass Master│
│   WHERE name IN (all glass_master_codes)                        │
│                                                                 │
│ Batch Query #4: Material Categories (scrap_pct)                 │
│   SELECT name, default_scrap_pct FROM tabAL Material Category   │
│   WHERE name IN (all category codes)                            │
│                                                                 │
│ Batch Query #5: Dynamic Item Rules                              │
│   → Resolve item_code từ rule (THRESHOLD/LOOKUP)                │
│   → VD: glass_thick=24 → RULE-NEP-GLASSTHICK → NEP-KINH-24      │
│                                                                 │
│ Batch Query #6: Resolved Item weights + prices                  │
│   → Cho items được resolve từ Dynamic Item Rule                 │
│                                                                 │
│ Build row_literals cho từng dòng BOM:                           │
│   {slug: {weight_per_unit, unit_price, calc_pattern,            │
│           glass_thick, glass_type, item_code, scrap_pct}}       │
│                                                                 │
│ Query count: 5-6 (gom từ N+1 thành batch)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B3: BUILD FORMULAS                                              │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  self.bom_items, self.row_literals, self.inputs          │
│ Output: self.bom_formulas list                                  │
│                                                                 │
│ Step 1: Đọc formula_fieldnames từ Bom Set config (data-driven)  │
│   → Fallback: DEFAULT_FORMULA_FIELDS nếu không có config        │
│                                                                 │
│ Step 2: Inject literals vào context (prefix = slug__)           │
│   → khung_ngang_tren__weight_per_unit = 1.2                     │
│   → khung_ngang_tren__unit_price = 113000                       │
│   → khung_ngang_tren__scrap_pct = 3                             │
│   → kinh_tren__glass_thick = 24                                 │
│                                                                 │
│ Step 3: Build formula list từ Bom Item fields:                  │
│   → width: "W_mm - 2*OFFSET_FRAME"                              │
│     → normalized: "W_mm - 2*OFFSET_FRAME"                       │
│   → qty: "2 * n_panel"                                          │
│   → Cross-row: "items.kinh_tren.width" → "kinh_tren__width"     │
│                                                                 │
│ Step 4: Synthetic formulas (luôn được tạo):                     │
│   → unit_qty  = lookup_calc_pattern(calc_pattern, w, h, tlr)    │
│   → total_qty = unit_qty * qty                                  │
│   → line_total = total_qty * unit_price                         │
│                                                                 │
│ Query count: 0 (pure in-memory)                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B4: CALCULATE BOM ITEMS (FORMULA ENGINE)                        │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  self.bom_formulas, self.inputs                          │
│ Output: self.bom_result list                                    │
│                                                                 │
│ FormulaEngine (FB):                                             │
│   → DAG builder: phát hiện phụ thuộc giữa các formula           │
│   → Topological sort: sắp xếp thứ tự tính                       │
│   → Safe evaluation: restricted namespace                       │
│                                                                 │
│ Safe functions đăng ký:                                         │
│   → lookup_calc_pattern(code, w, h, tlr): pattern từ DB         │
│   → lookup_rule(code, input): AL Calculation Rule resolve       │
│   → roundup(x, y): ceil(x)                                      │
│                                                                 │
│ Ví dụ execution order:                                          │
│   1. khung_ngang_tren__width = 2400 - 2*48 = 2304               │
│   2. khung_ngang_tren__unit_qty = (2304/1000) * 1.2 = 2.765 kg  │
│   3. khung_ngang_tren__total_qty = 2.765 * 2 = 5.53 kg          │
│   4. khung_ngang_tren__line_total = 5.53 * 113000 = 624,890 VND │
│   ... (cho tất cả các dòng)                                     │
│                                                                 │
│ on_error="raise": nếu 1 công thức lỗi → dừng toàn bộ            │
│ deterministic=True: đảm bảo kết quả lặp lại                     │
│                                                                 │
│ Build bom_result: [{"slug","item_code","width","height","qty",  │
│ "unit_qty","total_qty","unit_price","line_total","cost_bucket"}]│
│                                                                 │
│ Query count: 0 (FB engine chạy in-memory)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B5: AGGREGATE COST BUCKETS                                      │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  self.bom_result                                         │
│ Output: self.buckets dict                                       │
│                                                                 │
│ Gom line_total theo cost_bucket:                                │
│   → VL_NHOM = Σ line_total WHERE cost_bucket = "VL_NHOM"        │
│   → VL_KINH = Σ line_total WHERE cost_bucket = "VL_KINH"        │
│   → VL_VTP  = Σ line_total WHERE cost_bucket = "VL_VTP"         │
│   → VL_PK   = Σ line_total WHERE cost_bucket = "VL_PK"          │
│                                                                 │
│ Bucket name từ AL Bom Item → không hardcode                     │
│                                                                 │
│ Query count: 0 (Python loop)                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B6: CALCULATE COST TEMPLATE (FLEXIBLE FORMULA ENGINE)           │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  cost_template_snapshot, self.buckets, self.inputs       │
│ Output: self.cost_result dict, self.gia_vat                     │
│                                                                 │
│ Step 1: Parse cost_template_snapshot → global_formulas          │
│   → TONG_VL = VL_NHOM + VL_KINH + VL_VTP + VL_PK                │
│   → NC_SX = NC_SX_PCT * TONG_VL                                 │
│   → ... 14 dòng công thức                                       │
│                                                                 │
│ Step 2: Extract referenced bucket codes (regex)                 │
│   → Chỉ set default 0 cho codes được dùng (không load toàn bộ)  │
│                                                                 │
│ Step 3: Build extra_context = inputs + buckets                  │
│                                                                 │
│ Step 4: FlexibleFormulaEngine.calculate()                       │
│   → Sequential evaluation (không DAG)                           │
│                                                                 │
│ Output: {TONG_VL, NC_SX, NC_LD, TONG_NC, OH_VC, OH_QLY,         │
│          TONG_OH, GIA_THANH, PROFIT, GIA_BAN, DON_GIA_M2,       │
│          VAT, GIA_VAT}                                          │
│                                                                 │
│ Query count: 0 (FB engine in-memory)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B7: SAVE RESULTS (SINGLE COMMIT)                                │
│ ─────────────────────────────────────────────────────────────── │
│ Input:  Tất cả kết quả từ B4, B5, B6                            │
│ Output: Quotation Item updated + ConfigSnapshot created         │
│                                                                 │
│ Step 1: Build full_result JSON                                  │
│   → {buckets, cost_template, lines, gia_vat}                    │
│                                                                 │
│ Step 2: Create ConfigSnapshot (audit trail)                     │
│   → bom_version, quotation_item_name, calculation_timestamp     │
│   → inputs_json, result_json (TOÀN BỘ context + kết quả)        │
│                                                                 │
│ Step 3: Update Quotation Item (1 set_value call)                │
│   → al_gia_vat, al_gia_ban, al_bom_result, al_config_snapshot   │
│                                                                 │
│ Step 4: SINGLE commit (frappe.db.commit())                      │
│                                                                 │
│ Query count: 2 (1 insert + 1 update) + 1 commit                 │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ RESPONSE                                                        │
│ ─────────────────────────────────────────────────────────────── │
│ {                                                               │
│   "buckets": {VL_NHOM: 8500000, VL_KINH: 3200000, ...},         │
│   "cost_template": {GIA_VAT: 22717289, GIA_BAN: 20652081, ...}, │
│   "lines": [{slug, item_code, width, height, qty, ...}, ...]    │
│ }                                                               │
│                                                                 │
│ JS Client hiển thị TOÀN BỘ cost_template keys động              │
└─────────────────────────────────────────────────────────────────┘
```

### Tổng kết queries mỗi phase

| Phase | Queries | Ghi chú |
|---|---|---|
| B0 | 1 (cached) | get_cached_doc AL BOM Version |
| B1 | 2-3 | Formula Global Variables + Variable Library + resolve system vars |
| B2 | 5-6 | Batch: Items, Prices (composite-aware), Glass Masters, Categories, Rules |
| B3 | 0 | In-memory |
| B4 | 0 | FormulaEngine in-memory |
| B5 | 0 | Python loop |
| B6 | 0 | FlexibleFormulaEngine in-memory |
| B7 | 2 + 1 commit | Insert ConfigSnapshot + Update Quotation Item |
| **Tổng** | **~10-12** | **Giảm 50% từ v28.6 (~24 queries)** |

---

## 4. LUỒNG NGHIỆP VỤ ĐẦU-CUỐI

### 4.1 Setup sản phẩm mới (1 lần — BOM Manager)

```
BƯỚC 1: Tạo Variable Set
  AL Variable Library → chọn biến → AL Variable Set VS-CDMQ-2C
  Biến user: W_mm, H_mm, n_panel, TransomHeight_mm, aluminum_color...
  System vars (is_system=1): OFFSET_FRAME, NC_SX_PCT, VAT_RATE...
  
BƯỚC 2: Tạo Accessory Set (nếu cần)
  AL Accessory Set ACC-CDMQ-2C
  → tay_nam, khoa, ban_le (qty_formula=lookup_rule('RULE-BANLE-QTY', H_mm)*n_panel)

BƯỚC 3: Tạo Bom Set
  AL Bom Set BS-CDMQ-2C → 14-17 dòng AL Bom Item
  Mỗi dòng: slug, category, item_code, width, height, qty, calc_pattern...
  Link: variable_set=VS-CDMQ-2C
  formula_fieldnames: ["width","height","qty","show_condition",...]

BƯỚC 4: Tạo Cost Template (dùng chung)
  AL Cost Template CT-01-STANDARD → 14 dòng công thức
  GIA_VAT = GIA_BAN + VAT = (GIA_THANH + PROFIT) + VAT_RATE*GIA_BAN

BƯỚC 5: Tạo BOM
  AL BOM BOM-CDMQ-2C
  → bom_set=BS-CDMQ-2C, default_cost_template=CT-01-STANDARD

BƯỚC 6: Publish BOM Version
  → Tự động snapshot: copy mọi Small Text field từ AL Bom Item meta
  → Immutable: sau khi Published, không được sửa snapshot (guard trong validate())

TỔNG: 0 dòng code Python/JS
```

### 4.2 Báo giá (hàng ngày — Sales User)

```
BƯỚC 1: Tạo Quotation
  → Chọn Customer, AL Profile System
  → Custom fields: al_project_ref, al_profile_system

BƯỚC 2: Thêm Quotation Item
  → Chọn Item sản phẩm (CDMQ-2C - item phi tồn kho đại diện)
  → Chọn AL BOM (BOM-CDMQ-2C)
  → Tự động load Variable Set

BƯỚC 3: Nhập tham số
  → Bấm nút 📐 Tham số BOM
  → Dialog hiển thị fields động từ Variable Set
  → Nhập: W=2400, H=2600, n_panel=2, màu=WHITE...
  → System vars hiển thị read-only (OFFSET_FRAME=48...)

BƯỚC 4: Tính giá
  → Bấm nút 💰 Tính giá
  → API: alumglass.api.calculate_bom(qi_name)
  → BomOrchestrator.run() → 7 phase
  → GIA_VAT ≈ 22,717,289 VND

BƯỚC 5: Xem kết quả
  → Dialog hiển thị TOÀN BỘ cost_template keys
  → Bảng chi tiết BOM lines
  → ConfigSnapshot lưu để audit

BƯỚC 6: Submit Quotation → Sales Order
```

### 4.3 Sản xuất & Mua hàng — core-first (v28.9)

> **Luồng sản xuất/mua đi qua core ERPNext 100%**, AL BOM chỉ là "cỗ máy tính nhu cầu". Chi tiết tại `v28.md §E.2`, `§E.2A`, `§E.2B`.

> **⚠️ v28.10 — instantiate theo kích thước KHẢO SÁT THỰC TẾ:** trigger đổi từ *"SO submit (nominal)"* sang *"Site Survey Approved (kích thước thực)"*. 1 AL BOM formula → nhiều core BOM theo từng kích thước khảo sát thực; các vị trí trùng kích thước thực gom chung 1 core BOM (fingerprint). Vì sao: nhiều bộ cửa cùng báo giá 1 kích thước nhưng thực tế lệch nhau → instantiate theo nominal sẽ sai vật tư sản xuất.

```
① BÁO GIÁ (dự toán) — kích thước DANH NGHĨA
   AL BOM tính nominal → ConfigSnapshot quote_config → giá chào
       ▼  trúng thầu
② KHẢO SÁT — AL Site Survey (kích thước THỰC từng vị trí)
   actual_width_mm / actual_height_mm → deviation → action_required
       ▼  Approved
③ SẢN XUẤT — instantiate theo kích thước THỰC
   [hook] instantiate_production_bom (item có al_bom)
     → ConfigSnapshot production → core BOM instantiated
     (reuse fingerprint theo kích thước thực; SỐ BOM ≤ số cụm kích thước thực, không per-bộ)
     → set sales_order_item.bom
       ▼
CORE PRODUCTION PLAN  (get_items_from = Sales Order)
   │
   ├──→ CORE WORK ORDER (per cụm cấu hình; cùng kích thước thực → gom qty)
   │      → AL Cutting Plan (nhôm 1D / kính 2D) sinh từ WO
   │      → Stock Entry (manufacture) → thành phẩm
   │
   └──→ CORE MATERIAL REQUEST (gom vật tư theo kích thước THỰC, trừ projected_qty)
          → RFQ → Supplier Quotation → "Supplier Quotation Comparison"
          → Purchase Order → Purchase Receipt
          → (kính gia công ngoài: Subcontracting Order)

Sản phẩm CHỈ có AL BOM formula (không có core BOM):
   → hook tạo core Material Request trực tiếp từ ConfigSnapshot (không qua PP)
   → MR chỉ phát sinh SAU khi khảo sát Approved (theo kích thước thực)

Cần đặt vật tư nền sớm (lead time NCC) → tách raw stock:
   phôi nhôm + kính tấm đặt theo nominal + buffer trước; cắt theo kích thước thực sau.
   MR bổ sung phần chênh lệch do sai lệch khảo sát (§E.2A "lead time").
```

---

## 5. HỆ THỐNG BIẾN (Variable System)

### 5.1 Single Source of Truth

```
AL VARIABLE LIBRARY (định nghĩa 1 lần)
  │
  ├── System Variables (is_system=1)
  │   ├── source_doctype: "AL Profile System"
  │   ├── source_field: "offset_frame"
  │   └── Engine tự resolve từ DB → không hardcode
  │
  ├── User Variables (is_system=0)
  │   ├── W_mm, H_mm, n_panel...
  │   └── Hiển thị trong dialog cho user nhập
  │
  └── Default Values
      └── Fallback khi không resolve được
```

### 5.2 Variable Resolution Flow

```
Variable Set → Variable Set Item → AL Variable Library
                                       │
                        ┌──────────────┼──────────────┐
                        ▼              ▼              ▼
                   User Input     System Var     Global Var (FB)
                   (dialog)       (resolve từ    (Formula Global
                                  DB source)     Variable)
                        │              │              │
                        └──────────────┼──────────────┘
                                       ▼
                               self.inputs dict
                                       │
                        ┌──────────────┼──────────────┐
                        ▼              ▼              ▼
                   B3: Formulas   B4: Engine    B6: Cost Template
```

---

## 6. CƠ CHẾ COMPOSITE KEY PRICING

> **✅ Owner làm rõ (2026-08-13) — phân tách:** AL Pricing Dimension (composite key trên Item Price) là cơ chế **giá bán / tham chiếu giá**, dùng trong **dialog Quotation**. Giá nhôm tính theo **mã nhôm đại diện** + các thông số (màu sắc, xuất xứ...) — **không** theo từng mã nhôm cụ thể. **Inventory Dimension (kho)** là cơ chế độc lập (balance/valuation theo màu/loại/dày trên Stock Entry/SLE) — không liên quan. Chi tiết: `05_inventory-dimension-design.md §4.4`.

### 6.1 Vấn đề

Trong ngành nhôm kính, giá nhôm tham chiếu tính theo **mã nhôm đại diện** thay đổi theo:
- **Màu sắc** (WHITE: 113,000đ vs DARK: 145,000đ vs GO: 170,000đ)
- **Xuất xứ** (IMPORT vs DOMESTIC)
- **Độ dày** (1.2mm vs 1.4mm vs 2.0mm)
- **Bề mặt** (POWDER_COATED vs ANODIZED vs WOOD_GRAIN)

### 6.2 Cơ chế

```
BƯỚC 1: Định nghĩa Pricing Dimension
  AL Pricing Dimension:
    dimension_code = "MAU_SAC"
    dimension_type = "Link" → AL Color Standard
    custom_fieldname = "custom_pd_mau_sac" (auto-sinh, lowercase)

BƯỚC 2: Map Variable → Dimension
  AL Variable Dimension Mapping:
    variable_name = "aluminum_color"
    pricing_dimension = "MAU_SAC"

BƯỚC 3: Tạo Item Price trên MÃ NHÔM ĐẠI DIỆN với composite fields
  Item Price (mã nhôm đại diện — KHÔNG phải từng mã profile cụ thể):
    item_code = "NHOM-DAI-DIEN"
    price_list = "Standard Selling"
    custom_pd_mau_sac = "WHITE"    ← composite key
    price_list_rate = 113000

  Item Price:
    item_code = "NHOM-DAI-DIEN"    ← CÙNG mã đại diện
    price_list = "Standard Selling"
    custom_pd_mau_sac = "DARK"     ← KHÁC màu
    price_list_rate = 145000       ← KHÁC giá

BƯỚC 4: Engine tự động match khi tính giá trong dialog Quotation
  BomOrchestrator._fetch_composite_prices():
    1. Đọc AL Variable Dimension Mapping → variable→dimension→custom_fieldname
    2. Query tất cả Item Price cho mã đại diện (bao gồm composite fields)
    3. _match_composite_price():
       - Duyệt từng dòng, tính score = số field khớp với self.inputs (màu, xuất xứ...)
       - Chọn dòng có score cao nhất
       - Fallback: dòng "trần" không set composite field nào (giá mặc định)
```

> **Lưu ý:** cơ chế này phục vụ **giá bán/tham chiếu** tại dialog Quotation — không dùng cho valuation kho. Kho định giá theo giá mua thực tế (PO/Item Price buying) trên dimension bucket.

### 6.3 Hai chế độ pricing

| Mode | Mô tả | Dùng khi |
|---|---|---|
| **exact_match** | Composite key lookup chính xác | Có bảng giá đầy đủ cho từng tổ hợp |
| **multiplier_chain** | Giá gốc × ∏(hệ số) | Ít tổ hợp, dùng hệ số nhân |

Ví dụ `multiplier_chain` (trên mã nhôm đại diện):
```
Giá gốc NHOM-DAI-DIEN = 110,000đ
× COLOR=DARK (×1.08 từ AL Color Standard)
× ORIGIN=IMPORT (×1.15 từ Variable Dimension Mapping)
= 110,000 × 1.08 × 1.15 = 136,620đ
```

---

## 7. HỆ THỐNG ROLE & PERMISSION

### 7.1 4 Role nghiệp vụ

| Role | Mô tả | Quyền chính |
|---|---|---|
| **AL Sales User** | Nhân viên bán hàng | CRUD Quotation, Quotation Item; Read AL Master Data, AL Bom Engine |
| **AL BOM Manager** | Quản lý cấu hình sản phẩm | Full AL Master Data, AL Bom Engine, AL Formula Rules; Read các module khác |
| **AL Site Engineer** | Kỹ sư công trường | Full AL Construction; Read/Write AL Stock; Read AL Bom Engine, AL Manufacturing |
| **AL Project Accountant** | Kế toán dự án | Full AL Account; Read/Write AL Buying; Read AL Construction |

### 7.2 Permission Matrix (theo module)

| Module | AL Sales User | AL BOM Manager | AL Site Engineer | AL Project Accountant |
|---|---|---|---|---|
| **ERPNext: Quotation, Sales Order** | CRUD | Read | — | — |
| **AL Master Data** | Read | CRUD | — | — |
| **AL Bom Engine** | Read | CRUD | Read | — |
| **AL Formula Rules** | — | CRUD | — | — |
| **AL Buying** | — | CRUD | — | Read/Write/Create |
| **AL Stock** | — | Read/Write/Create | Read/Write/Create | — |
| **AL Manufacturing** | — | CRUD | Read | — |
| **AL Construction** | — | Read | CRUD | Read |
| **AL Account** | — | Read | — | CRUD |
| **AL Quality** | — | CRUD | Read/Write/Create | — |
| **AL AI Intelligence** | Read | Read | Read | Read |

### 7.3 Cài đặt

```bash
# Tự động cài đặt qua after_install hook:
bench install-app alumglass
# → install_all_custom_fields()
# → install_roles_and_permissions()
#   → 4 roles + DocPerm cho 10 module AL + core ERPNext doctypes
```

---

## 8. DANH SÁCH MODULE & DOCTYPE

### 8.1 Module AL Master Data (`al_master_data`) — 13 doctypes

| Doctype | Vai trò |
|---|---|
| **AL Variable Library** | Thư viện biến tập trung — single source of truth |
| **AL Variable Set** | Tập biến cho 1 sản phẩm |
| **AL Variable Set Item** | Dòng biến (child, auto-fill từ Library) |
| **AL Variable Dimension Mapping** | Map variable → pricing dimension |
| **AL Slug Library** | Định danh vật tư (cross-row reference) |
| **AL Material Category** | Loại vật tư động (flags điều khiển validate) |
| **AL Profile System** | Hệ profile + bộ offset hình học |
| **AL Color Standard** | Danh mục màu (+price_multiplier) — composite key giá bán (AL Pricing Dimension) + reference Inventory Dimension Màu (kho) |
| **AL Glass Type** | Phân loại kính (reference Inventory Dimension) |
| **AL Glass Thickness** 🆕 | Độ dày kính (5/8/10/12mm) — reference Inventory Dimension (v28.9) |
| **AL Glass Master** | Thông số kỹ thuật kính |
| **AL Product Type** | Loại sản phẩm + NC/PROFIT config |
| **AL Pricing Dimension** | Đặc tính giá **bán** động — auto-sinh Custom Field trên Item Price (mã nhôm đại diện + màu/xuất xứ...), tham chiếu trong dialog Quotation. Độc lập Inventory Dimension |

### 8.2 Module AL Bom Engine (`al_bom_engine`) — 12 doctypes

| Doctype | Vai trò |
|---|---|
| **AL Bom Item** | Dòng vật tư — DocType TRUNG TÂM |
| **AL Bom Set** | Tập hợp Bom Items + link Variable Set (+formula_fieldnames) |
| **AL BOM** | BOM — link Bom Set + Cost Template |
| **AL BOM Version** | Snapshot bất biến (immutable sau Published) |
| **AL BOM Change Log** | Nhật ký thay đổi |
| **AL Cost Bucket** | Tài khoản chi phí (8 source types) |
| **AL Cost Template** | Master công thức giá thành |
| **AL Cost Template Item** | Dòng công thức (child) |
| **ConfigSnapshot** | Snapshot kết quả tính (audit trail) |
| **AL Design Revision** | Thay đổi thiết kế |
| **AL Accessory Set** | Bộ phụ kiện |
| **AL Accessory Item** | Dòng phụ kiện (child) |

### 8.3 Module AL Formula Rules (`al_formula_rules`) — 8 doctypes

| Doctype | Vai trò |
|---|---|
| **AL Calculation Rule** | CONSTANT / THRESHOLD / LOOKUP |
| **AL Rule Threshold Row** | Dòng ngưỡng (child) |
| **AL Rule Lookup Row** | Dòng tra cứu (child) |
| **AL Dynamic Item Rule** | Rule chọn Item động |
| **AL Dynamic Item Rule Threshold Row** | Dòng ngưỡng (child) |
| **AL Dynamic Item Rule Lookup Row** | Dòng tra cứu (child) |
| **AL Dynamic Item Rule Version** | Snapshot bất biến của rule |
| **AL Quantity Calc Method** | Pattern tính quantity (calc_fn lambda từ DB) |

### 8.4 Các module Operational

| Module | Package | Doctypes |
|---|---|---|
| **AL Selling** | `al_selling` | ★ 0 doctype riêng — dùng ERPNext core (Quotation, Quotation Item, Sales Order) + Custom Fields + Client Scripts + API |
| **AL Buying** | `al_buying` | Cost Variance (1) — v28.9: bỏ Supplier Price List + Material Plan, dùng core (Item Price buying, RFQ, Supplier Quotation, Purchase Order, Material Request) |
| **AL Stock** | `al_stock` | Project Warehouse Map (1) + **Inventory Dimension** (core, 3 records: màu/loại/dày) |
| **AL Manufacturing** | `al_manufacturing` | Cutting Standard (1), Cutting Plan Alu (2), Cutting Plan Glass (2) — v28.9: bỏ Production Order Bridge, thay bằng core BOM instantiated |
| **AL Construction** | `al_construction` | Installation Team (1), Site Survey (2), Installation Order (2), Installation Progress (1), Installation Cost (1), Change Order (1), Handover Acceptance (2), Punchlist (1) |
| **AL Account** | `al_account` | Project Profitability Snapshot (1), Project Financial Config (1) |
| **AL Quality** | `al_quality` | Warranty Policy (1) |
| **AL AI Intelligence** | `al_ai_intelligence` | Suggestion Log (1), Interaction Log (1), Alert Config (1) |

### 8.5 Custom Fields trên ERPNext Core

| Core Doctype | Custom Fields |
|---|---|
| **Quotation** | al_project_ref, al_profile_system, al_loss_reason |
| **Quotation Item** | al_bom, al_bom_version, al_bom_vars (JSON), al_config_snapshot, al_gia_ban, al_gia_vat, al_bom_result (JSON) |
| **Sales Order** | al_project_id, al_installation_team, al_expected_start_date, al_expected_end_date |
| **Item** | al_material_category, al_weight_per_m, al_glass_master, al_is_color_variable |
| **Item Price** | al_is_composite_price + custom_pd_* (auto-generated từ Pricing Dimension) — **giá bán/tham chiếu** (mã nhôm đại diện + màu/xuất xứ...), tra trong dialog Quotation. Độc lập Inventory Dimension |
| **Inventory Dimension** 🆕 | config 3 records: Màu (AL Color Standard), Loại kính (AL Glass Type), Độ dày kính (AL Glass Thickness) — core tự tạo fields trên Stock Entry/SLE |
| **Batch** | al_source_project, al_trace_stage, al_bin_location (bỏ al_color → Inventory Dimension) |
| **Serial No** | al_piece_length_mm, al_is_offcut, al_parent_cut_id |
| **Work Order** | al_config_snapshot, al_bom_version, al_cutting_plan_aluminum, al_cutting_plan_glass, al_project |
| **Purchase Order** | al_project, al_config_snapshot, al_bom_version (bỏ al_color → Inventory Dimension) |
| **Stock Entry** | al_project, al_installation_order |
| **Delivery Note** | al_project, al_installation_order |
| **Quality Inspection** | al_work_order, al_inspection_stage, al_bom_slug, al_surface_check, al_dimension_check, al_color_match, al_glass_defect_check |
| **Warranty Claim** | al_installation_order, al_defect_category, al_warranty_policy, al_covered_by_warranty |
| **Journal Entry** | al_project, al_cost_bucket, al_change_order |
| **Payment Entry** | al_payment_stage, al_handover |

---

## 9. NGUYÊN TẮC THIẾT KẾ

### 9.1 Nguyên tắc cốt lõi

| # | Nguyên tắc | Mô tả |
|---|---|---|
| 1 | **Zero Hardcode** | Mọi giá trị từ DB. Code chỉ là framework. Thêm config mới = 0 dòng code. |
| 2 | **FB cho toán** | Mọi tính toán ủy thác cho Formula Builder. AlumGlass không tự eval(). |
| 3 | **ERPNext Core First** | Tận dụng tối đa core doctypes. Chỉ tạo mới khi thực sự cần. **v28.9:** toàn bộ luồng mua/sản xuất đi qua core (Item Price buying, RFQ, Supplier Quotation, Purchase Order, Material Request, Production Plan, Work Order, Subcontracting Order). AL BOM (công thức động) **giữ nguyên** cho báo giá — bridge sang core qua **core BOM instantiated** (từ ConfigSnapshot). |
| 4 | **Single Source of Truth** | Variable Library → Variable Set → Bom Set → Dialog |
| 5 | **Config > Code** | Cost Bucket mới = JSON config. Pricing Dimension mới = 2 DB records. |
| 6 | **Batch Query** | BomOrchestrator B2 gom tất cả query, tránh N+1. |
| 7 | **Immutable Snapshot** | BOM Version + ConfigSnapshot bất biến, tái lập được. |
| 8 | **Data-Driven Validation** | Material Category flags điều khiển validate, không if/elif. |
| 9 | **Kho đa chiều = Inventory Dimension** (v28.9) | Màu/loại/dày = dimension trên Stock Entry/SLE (core), Batch chỉ trace lô. Valuation theo giá mua thực tế, mỗi bucket 1 rate. |
| 10 | **Composite Key Pricing (giá bán)** | AL Pricing Dimension + Dim Mapping → composite fields trên Item Price (mã nhôm đại diện), tham chiếu trong dialog Quotation. **Độc lập** với Inventory Dimension (kho). |
| 10 | **Single Commit** | B7 ghi tất cả trong 1 transaction. |
| 11 | **Redis Cache** | get_cached_doc() cho config doctypes, tự invalidate khi save. |
| 12 | **Least Privilege** | 4 role nghiệp vụ — Sales không cần System Manager. |
| 13 | **Self-Check** | install_roles.py tự verify module names, báo WARNING nếu mismatch. |
| 14 | **Snapshot Động** | BOM Version tự copy mọi Small Text field từ Bom Item meta. |
| 15 | **calc_fn từ DB** | Quantity Calc Method lưu lambda trong DB, engine eval động. |

### 9.2 Quy tắc đặt tên

- **Doctype**: Tiền tố `AL` + PascalCase: `AL Bom Item`, `AL Pricing Dimension`
- **Module Frappe**: snake_case: `al_bom_engine`, `al_master_data`  
- **Field trong DocType**: snake_case: `bom_set_snapshot`, `custom_fieldname`
- **Custom Field trên Core**: Tiền tố `al_`: `al_bom`, `al_gia_vat`
- **Variable name**: snake_case: `aluminum_color`, `installation_height_m`
- **Slug**: snake_case tiếng Việt (domain-specific): `khung_ngang_tren`
- **Cost Bucket code**: UPPER_SNAKE: `VL_NHOM`, `GIA_VAT`

---

## 10. PERFORMANCE & CACHE STRATEGY

### 10.1 Cache layers

| Layer | Cơ chế | TTL | Đối tượng |
|---|---|---|---|
| **Redis (Frappe)** | `frappe.get_cached_doc()` | 3600s | AL BOM, AL BOM Version, Bom Set, Profile System, Product Type, Calculation Rule |
| **In-memory** | `self._qi_doc`, `self._bom_doc`, `self._dim_fieldname_cache` | Request scope | Dùng xuyên suốt engine, tránh load lại |
| **FB Engine** | `FormulaEngine` internal | Request scope | DAG + topo sort cache |

### 10.2 Query optimization (v28.7-v28.8)

| Optimization | Trước | Sau | Tiết kiệm |
|---|---|---|---|
| Single commit (B7) | 5 set_value + 3 commit | 1 set_value + 1 commit | 6 queries |
| get_cached_doc | get_doc() mỗi lần | Redis cache | 5-8 queries |
| Batch Glass Master | N+1 query | 1 get_all(IN) | K-1 queries |
| Cost Bucket load | Load toàn bộ bảng | Parse formula → chỉ load referenced | 1 query |
| Composite Price query | 1 query/Item Price row | 1 batch query + in-memory match | N-1 queries |
| Duplicate load removal | Load lại cùng doc | Cache trong __init__ | 2 queries |

### 10.3 Tổng kết queries

| Scenario | v28.6 | v28.8 | Giảm |
|---|---|---|---|
| Typical (version given) | ~24 | ~10-12 | **50%** |
| Cold cache (first call) | ~24 | ~15-17 | **30%** |
| Warm cache (subsequent) | ~24 | ~8-10 | **60%** |

---

## 11. CÁCH MỞ RỘNG HỆ THỐNG

### 11.1 Thêm sản phẩm mới (cửa sổ 1 cánh)

```
1. AL Variable Set VS-CS1C → chọn biến
2. AL Accessory Set ACC-CS1C → phụ kiện
3. AL Bom Set BS-CS1C → 10-15 Bom Items
4. AL BOM BOM-CS1C → link Bom Set + Cost Template
5. Publish BOM Version

→ 0 dòng code
```

### 11.2 Thêm đặc tính giá mới (độ bóng)

```
1. AL Pricing Dimension: dimension_code="DO_BONG", dimension_type="Select"
   → Tự động sinh custom_pd_do_bong trên Item Price
2. AL Variable Dimension Mapping: variable_name="aluminum_gloss" → "DO_BONG"
3. Thêm "aluminum_gloss" vào Variable Set

→ 0 dòng code
```

### 11.3 Thêm ngành mới (thép)

```
1. AL Material Category: category_code="STEEL", has_weight=1
2. AL Slug Library: thanh_ngang_thep, thanh_dung_thep...
3. AL Variable Library: thêm biến (steel_grade...)
4. AL Bom Set mới + AL BOM mới

→ 0 dòng code
```

### 11.4 Thêm pattern tính mới

```
AL Quantity Calc Method:
  calc_pattern_code = "SURFACE_AREA"
  calc_fn = "lambda w, h, tlr, **kw: 2 * (w/1000) * (h/1000)"

→ 0 dòng code Python
```

### 11.5 Bảng tổng hợp: Muốn thêm gì → Cần làm gì → Có cần code?

| Muốn thêm... | Cần làm | Sửa code? |
|---|---|---|
| Hệ profile mới | 1 record AL Profile System | ❌ |
| Loại vật tư mới | 1 record AL Material Category | ❌ |
| Cost bucket mới | 1 record AL Cost Bucket + 1 dòng Cost Template | ❌ |
| Pattern tính mới | 1 record AL Quantity Calc Method (calc_fn lambda) | ❌ |
| Biến mới (user) | 1 record AL Variable Library → thêm vào Variable Set | ❌ |
| Biến mới (system) | 1 record AL Variable Library + source_doctype/source_field | ❌ |
| Rule chọn Item mới | 1 record AL Dynamic Item Rule | ❌ |
| Đặc tính giá mới | 1 AL Pricing Dimension + 1 Variable Dimension Mapping | ❌ |
| Field formula mới | Thêm vào formula_fieldnames JSON trong Bom Set | ❌ |
| Data source type mới | 1 hàm trong fb_handlers.py + 1 dòng fb_source_types | ✅ ~10 lines |
| Sản phẩm mới | Bom Set + Variable Set + Accessory Set | ❌ |
| Ngành mới | Material Category + Slug Library + Bom Set | ❌ |
| Role mới | 1 record Role + cập nhật MODULE_PERMISSIONS | ❌ |

---

## PHỤ LỤC

### A. Cấu trúc thư mục

```
alumglass/
├── hooks.py                    # App hooks, fixtures, fb_source_types
├── engine/
│   └── bom_orchestrator.py     # 7-phase calculation engine
├── fb_handlers.py              # Thin layer FB data sources
├── api/
│   └── __init__.py             # 5 whitelisted API endpoints
├── setup/
│   ├── custom_fields.py        # Custom field installer
│   ├── install_roles.py        # Role & permission installer
│   └── seed_demo_data.py       # Demo data seeder
├── tests/
│   ├── test_bom_orchestrator.py    # Integration tests
│   └── test_composite_pricing.py   # Composite key tests
├── fixtures/
│   └── roles.json              # Role fixture definitions
├── al_master_data/             # Module: Master Data (12 doctypes)
├── al_bom_engine/              # Module: BOM Engine (12 doctypes)
├── al_formula_rules/           # Module: Formula Rules (8 doctypes)
├── al_buying/                  # Module: Buying (5 doctypes)
├── al_stock/                   # Module: Stock (1 doctype)
├── al_manufacturing/           # Module: Manufacturing (6 doctypes)
├── al_construction/            # Module: Construction (11 doctypes)
├── al_account/                 # Module: Account (2 doctypes)
├── al_quality/                 # Module: Quality (1 doctype)
├── al_ai_intelligence/         # Module: AI (3 doctypes)
└── public/js/                  # Client scripts
```

### B. API Reference

| Endpoint | Method | Mô tả |
|---|---|---|
| `alumglass.api.calculate_bom(qi_name)` | Whitelist | Tính BOM cho Quotation Item |
| `alumglass.api.preview_cost_template(code, inputs)` | Whitelist | Preview Cost Template |
| `alumglass.api.get_variable_set_for_bom(bom_code)` | Whitelist | Lấy biến từ Variable Set |
| `alumglass.api.get_slug_info(slug)` | Whitelist | Tra cứu Slug Library |
| `alumglass.api.resolve_item_rule(rule, input)` | Whitelist | Resolve Dynamic Item Rule |
| `alumglass.api.get_bom_structure(bom_code)` | Whitelist | Cấu trúc BOM |

### C. JS Client Scripts

| Script | Chức năng |
|---|---|
| `formula_setup.js` | Autocomplete formula |
| `bom_dialog.js` | Hiển thị kết quả BOM (dynamic keys) |
| `cost_template.js` | Preview Cost Template |
| `quotation_item_dialog.js` | Dialog nhập tham số BOM |
| `doctype/overrides/quotation.js` | Nút Tính giá trên Quotation |
| `doctype/overrides/sales_order.js` | FB integration cho Sales Order |

---

*Tài liệu cập nhật: 2026-08-04 | Phiên bản: v28.8*
