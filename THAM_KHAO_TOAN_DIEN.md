# ALUMGLASS ERP — THAM KHẢO TOÀN DIỆN A-Z

> **v28.8 | 2026-08-05 | 60 DocType | 10 Module | 5 API | 6 JS Client | 5 Tests | 17 Docs**
> **Đây là tài liệu GỐC DUY NHẤT — mọi thông tin về dự án đều có ở đây.**

---

## MỤC LỤC

1. [Thống kê dự án](#1-thống-kê-dự-án)
2. [Kiến trúc tổng thể](#2-kiến-trúc-tổng-thể)
3. [Engine tính toán — BomOrchestrator 7-Phase Flow](#3-engine-tính-toán--bomorchestrator-7-phase-flow)
4. [Luồng nghiệp vụ đầu-cuối](#4-luồng-nghiệp-vụ-đầu-cuối)
5. [Hệ thống biến — Data-Driven Context](#5-hệ-thống-biến--data-driven-context)
6. [Formula Builder — Tích hợp & Autocomplete](#6-formula-builder--tích-hợp--autocomplete)
7. [Composite Key Pricing](#7-composite-key-pricing)
8. [Role & Permission](#8-role--permission)
9. [Danh sách file — Đường dẫn cụ thể](#9-danh-sách-file--đường-dẫn-cụ-thể)
10. [Tài liệu tham khảo](#10-tài-liệu-tham-khảo)

---

## 1. THỐNG KÊ DỰ ÁN

### 1.1 Tổng quan

| Metric | Giá trị |
|---|---|
| **Phiên bản** | v28.9 (core-first procurement/production) |
| **Số Module** | 10 module AlumGlass + 1 module ảo (AL Selling dùng ERPNext core) |
| **Số DocType** | 53 JSON doctypes (v28.9: bỏ 5 DocType mua/sản xuất trùng core, + AL Glass Thickness cho Inventory Dimension) |
| **Số Role** | 4 (AL Sales User, AL BOM Manager, AL Site Engineer, AL Project Accountant) |
| **Số API** | 7 whitelisted endpoints |
| **Số JS Client** | 5 files (~980 dòng) |
| **Số Test** | 5 tests (2 integration + 2 composite + 1 manual) |
| **Số File Python** | 171 files (~5,200 dòng) |
| **Số File JS** | 51 files (~4,170 dòng) |
| **Số File MD** | 17 tài liệu |
| **Core Engine** | `bom_orchestrator.py` (691 dòng) + `fb_handlers.py` (181 dòng) |
| **DB queries/lần tính** | ~10-12 (giảm 50% từ v28.6) |
| **Nguyên tắc thiết kế** | 30 nguyên tắc (xem [v28.md](v28.md) A.1) |

### 1.2 Module breakdown

| # | Module | Package | Doctype JSON | Vai trò |
|---|--------|---------|:---:|-------|
| 1 | **AL Master Data** | `al_master_data` | 13 | Danh mục nền tảng: Variable Library, Slug, Profile, Color, Glass, Glass Thickness (v28.9), Product Type, Pricing Dimension |
| 2 | **AL Bom Engine** | `al_bom_engine` | 12 | Cấu trúc BOM: Bom Item, Bom Set, BOM, Version, Cost Bucket, Cost Template, Snapshot |
| 3 | **AL Formula Rules** | `al_formula_rules` | 8 | Rule engine: Calculation Rule, Dynamic Item Rule, Quantity Calc Method |
| 4 | **AL Selling** | `al_selling` | 0 | Bán hàng: Custom Fields + Client Scripts + API trên ERPNext core |
| 5 | **AL Buying** | `al_buying` | 1 | Mua hàng (core-first): Cost Variance — bỏ Supplier Price List + Material Plan, dùng core Item Price buying / RFQ / SQ / PO / Material Request |
| 6 | **AL Stock** | `al_stock` | 1 | Kho: Project Warehouse Map + core **Inventory Dimension** (3 records: màu/loại kính/dày kính) — tách tồn kho nhôm/kính |
| 7 | **AL Manufacturing** | `al_manufacturing` | 5 | Sản xuất: Cutting Plan, Cutting Standard — bỏ Production Order Bridge, dùng core BOM instantiated + Production Plan / Work Order / Subcontracting |
| 8 | **AL Construction** | `al_construction` | 10 | Thi công: Site Survey, Installation Order, Handover |
| 9 | **AL Account** | `al_account` | 2 | Kế toán: P&L Snapshot, Financial Config |
| 10 | **AL Quality** | `al_quality` | 1 | Chất lượng: Warranty Policy |
| 11 | **AL AI Intelligence** | `al_ai_intelligence` | 3 | AI: Suggestion Log, Alert Config |

### 1.3 Tính năng chính

| # | Tính năng | File chính | Dòng |
|---|----------|-----------|:---:|
| 1 | **BomOrchestrator 7-Phase** | `engine/bom_orchestrator.py` | 691 |
| 2 | **FB Handlers (thin layer)** | `fb_handlers.py` | 181 |
| 3 | **Composite Key Pricing** | `engine/bom_orchestrator.py:_fetch_composite_prices` | ~100 |
| 4 | **Data-Driven System Variables** | `engine/bom_orchestrator.py:_resolve_system_variables` | ~60 |
| 5 | **Formula Context Injection** | `api/__init__.py:get_formula_context` | ~180 |
| 6 | **Formula Autocomplete** | `public/js/formula_setup.js` | 249 |
| 7 | **Role Installer** | `setup/install_roles.py` | 236 |
| 8 | **Immutability Guard** | `al_bom_version.py:_guard_published_immutability` | 20 |
| 9 | **Pricing Dimension Auto-Sync** | `al_pricing_dimension.py:_sync_custom_field` | 25 |
| 10 | **Seed Demo Data** | `setup/seed_demo_data.py` | 371 |

---

## 2. KIẾN TRÚC TỔNG THỂ

### 2.1 Sơ đồ 5 tầng

```
TẦNG 5 — BUSINESS (ERPNext Core + Custom Fields)
  Quotation, Sales Order, Item, Item Price, BOM, Work Order,
  Batch, Serial No, GL Entry, Journal Entry, Project, Task...
  → Custom fields `al_*` được tạo tự động qua after_install

TẦNG 4 — ORCHESTRATION (alumglass/engine/ + api/)
  BomOrchestrator — 7-phase engine
  API layer — 7 whitelisted endpoints

TẦNG 3 — FB HANDLERS (alumglass/fb_handlers.py)
  aluminum_price_composite, glass_master_data, cost_bucket_aggregate
  → Đăng ký qua hooks.py fb_source_types

TẦNG 2 — FORMULA BUILDER (formula_builder app — BẤT BIẾN)
  FormulaEngine (DAG), FlexibleFormulaEngine, BatchBindingResolver,
  SnapshotManager, SourceTypeRegistry, CompletionRegistry

TẦNG 1 — DOCTYPE CONFIG (Database)
  AL Variable Library, AL Bom Set, AL Cost Bucket, AL Cost Template,
  AL Pricing Dimension, AL Calculation Rule, AL Slug Library...
```

### 2.2 File quan trọng nhất — đường dẫn

```
alumglass/
├── hooks.py                          # App config: fixtures, fb_source_types, API whitelist, after_install
├── engine/
│   └── bom_orchestrator.py           # ★ TRÁI TIM: 7-phase BOM calculation engine
├── fb_handlers.py                    # Thin layer: custom data sources cho Formula Builder
├── api/
│   └── __init__.py                   # 7 API endpoints + get_formula_context()
├── setup/
│   ├── custom_fields.py              # Custom field installer (ERPNext core doctypes)
│   ├── install_roles.py              # Role + DocPerm installer (4 roles × 60 doctypes)
│   └── seed_demo_data.py             # Demo data: CDMQ-2C + CDMQ-4C
├── tests/
│   ├── test_bom_orchestrator.py      # Integration tests (FrappeTestCase)
│   └── test_composite_pricing.py     # Composite key pricing tests
├── fixtures/
│   └── roles.json                    # Role fixture definitions
├── public/js/
│   ├── formula_setup.js              # ★ Formula Builder integration + context injection
│   ├── cost_template.js              # Cost Template: validate + preview + context
│   ├── bom_dialog.js                 # BOM calculation result dialog
│   ├── quotation_item_dialog.js      # BOM parameter input dialog
│   └── HUONG_DAN_FORMULA.md          # ★ A-Z Formula Builder guide
├── al_master_data/                   # Module: Master Data (12 doctypes)
├── al_bom_engine/                    # Module: BOM Engine (12 doctypes)
├── al_formula_rules/                 # Module: Formula Rules (8 doctypes)
├── al_selling/                       # Module: Selling (custom fields only)
├── al_buying/                        # Module: Buying (5 doctypes)
├── al_stock/                         # Module: Stock (1 doctype)
├── al_manufacturing/                 # Module: Manufacturing (6 doctypes)
├── al_construction/                  # Module: Construction (10 doctypes)
├── al_account/                       # Module: Account (2 doctypes)
├── al_quality/                       # Module: Quality (1 doctype)
└── al_ai_intelligence/               # Module: AI (3 doctypes)
```

---

## 3. ENGINE TÍNH TOÁN — BOMORCHESTRATOR 7-PHASE FLOW

**File:** [engine/bom_orchestrator.py](alumglass/engine/bom_orchestrator.py) (691 dòng)

### 3.1 Flow tổng quan

```
QUOTATION ITEM (user bấm "Tính giá")
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ B0: VERSION PINNING                          [1 query, cached]  │
│ ─────────────────────────────────────────────────────────────── │
│ • Đọc al_bom_version từ Quotation Item                          │
│ • get_cached_doc("AL BOM Version") → Redis cache 3600s         │
│ • Output: self.bom_version (snapshot JSON)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B1: GATHER INPUTS                               [2-3 queries]   │
│ ─────────────────────────────────────────────────────────────── │
│ 1. Đọc user inputs từ al_bom_vars JSON (W_mm, H_mm, color...)   │
│ 2. Formula Global Variables (VAT_RATE, OH_VC_PCT...)            │
│ 3. ★ Resolve System Variables từ AL Variable Library:           │
│    • AL Profile System → OFFSET_FRAME, OFFSET_GLASS...          │
│    • AL Product Type → NC_SX_PCT, PROFIT_MARGIN...              │
│    • Fallback: default_value → Calculation Rule CONSTANT        │
│ 4. Merge: user inputs ghi đè system vars                        │
│ Output: self.inputs dict (~50-80 keys)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B2: PRE-FETCH MASTER DATA                      [5-6 queries]    │
│ ─────────────────────────────────────────────────────────────── │
│ Parse bom_set_snapshot → self.bom_items list                    │
│                                                                 │
│ Batch #1: Item weights (get_all IN)                             │
│ Batch #2: ★ Item Prices (COMPOSITE-KEY AWARE):                 │
│   → _fetch_composite_prices()                                   │
│   → Đọc AL Variable Dimension Mapping + Pricing Dimension       │
│   → _match_composite_price(): best match + fallback             │
│ Batch #3: Glass Masters (get_all IN, tránh N+1)                 │
│ Batch #4: Material Categories (scrap_pct)                       │
│ Batch #5: Dynamic Item Rules (resolve item_code từ input)       │
│ Batch #6: Resolved Item weights + prices                        │
│                                                                 │
│ Build row_literals per BOM line:                                │
│   {weight_per_unit, unit_price, calc_pattern,                   │
│    glass_thick, glass_type, scrap_pct, item_code}               │
│ Output: self.row_literals dict                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B3: BUILD FORMULAS                                [0 queries]   │
│ ─────────────────────────────────────────────────────────────── │
│ • Đọc formula_fieldnames từ Bom Set config (data-driven)        │
│ • Inject literals: {slug}__weight_per_unit, {slug}__unit_price  │
│ • Normalize cross-row: items.kinh_tren.width → kinh_tren__width │
│ • Build formula list: [{name, formula}, ...]                    │
│ • Synthetic: unit_qty, total_qty, line_total                    │
│ Output: self.bom_formulas list                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B4: CALCULATE BOM ITEMS (FORMULA ENGINE)          [0 queries]   │
│ ─────────────────────────────────────────────────────────────── │
│ FormulaEngine (FB):                                             │
│   → DAG builder: phát hiện phụ thuộc                            │
│   → Topological sort: sắp xếp thứ tự tính                       │
│   → Safe evaluation: restricted namespace                       │
│                                                                 │
│ Safe functions:                                                 │
│   • lookup_calc_pattern(code, w, h, tlr) → pattern từ DB        │
│   • lookup_rule(code, input) → AL Calculation Rule resolve      │
│   • roundup(x, y) → ceil(x)                                     │
│                                                                 │
│ Output: self.bom_result [{slug, item_code, width, height,       │
│          qty, unit_qty, total_qty, unit_price, line_total}]     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B5: AGGREGATE COST BUCKETS                        [0 queries]   │
│ ─────────────────────────────────────────────────────────────── │
│ Σ line_total theo cost_bucket (từ Bom Item, không hardcode):    │
│   VL_NHOM = Σ line_total WHERE cost_bucket = "VL_NHOM"          │
│   VL_KINH = Σ line_total WHERE cost_bucket = "VL_KINH"          │
│   ...                                                           │
│ Output: self.buckets dict                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B6: CALCULATE COST TEMPLATE (FLEXIBLE FORMULA ENGINE)           │
│ ─────────────────────────────────────────────────────────────── │
│ Parse cost_template_snapshot → 14 dòng công thức:               │
│   TONG_VL = VL_NHOM + VL_KINH + VL_VTP + VL_PK                  │
│   NC_SX = NC_SX_PCT * TONG_VL                                   │
│   ...                                                           │
│   GIA_VAT = GIA_BAN + VAT                                       │
│                                                                 │
│ FlexibleFormulaEngine: sequential evaluation                    │
│ extra_context = inputs + buckets                                │
│                                                                 │
│ Output: self.cost_result {TONG_VL, NC_SX, ..., GIA_VAT}         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ B7: SAVE RESULTS (SINGLE COMMIT)                [2 queries + 1] │
│ ─────────────────────────────────────────────────────────────── │
│ 1. Build full_result JSON {buckets, cost_template, lines}       │
│ 2. Create ConfigSnapshot (audit trail):                         │
│    • bom_version, quotation_item_name, inputs_json, result_json │
│ 3. Update Quotation Item (1 set_value):                         │
│    • al_gia_vat, al_gia_ban, al_bom_result, al_config_snapshot  │
│ 4. SINGLE commit (frappe.db.commit())                           │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ RESPONSE                                                        │
│ {                                                               │
│   "buckets": {VL_NHOM: 8500000, ...},                           │
│   "cost_template": {GIA_VAT: 22717289, ...},                    │
│   "lines": [{slug, item_code, line_total, ...}, ...]            │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Tổng queries mỗi phase

| Phase | Queries | Cache? | Ghi chú |
|-------|:---:|:---:|-------|
| B0 | 1 | Redis 3600s | `get_cached_doc` AL BOM Version |
| B1 | 2-3 | Không | Formula Global Var + Variable Library + resolve |
| B2 | 5-6 | Không | Batch: Items, Prices★, Glass, Categories, Rules |
| B3 | 0 | — | In-memory formula normalization |
| B4 | 0 | — | FormulaEngine DAG (in-memory) |
| B5 | 0 | — | Python loop |
| B6 | 0 | — | FlexibleFormulaEngine (in-memory) |
| B7 | 2+1 | — | Insert ConfigSnapshot + Update QI + commit |
| **Tổng** | **~10-12** | | **-50% từ v28.6** |

---

## 4. LUỒNG NGHIỆP VỤ ĐẦU-CUỐI

### 4.1 Flow tạo sản phẩm mới (BOM Manager)

```
1. AL Variable Library    → Định nghĩa biến (W_mm, H_mm, n_panel...)
2. AL Slug Library        → Định nghĩa slug (khung_ngang_tren, kinh_tren...)
3. AL Material Category   → Định nghĩa loại vật tư
4. AL Quantity Calc Method→ Định nghĩa pattern (LENGTH_TO_WEIGHT, AREA...)
5. AL Cost Bucket         → Định nghĩa bucket (VL_NHOM, TONG_VL, GIA_VAT...)
6. AL Cost Template       → Công thức giá thành (14 dòng)
7. AL Variable Set        → Nhóm biến cho sản phẩm (link tới Variable Library)
8. AL Accessory Set       → Bộ phụ kiện (optional)
9. AL Bom Set             → Bom Items (14-17 dòng) + link Variable Set
10. AL BOM                → Link Bom Set + Cost Template
11. AL BOM Version        → Publish → auto-snapshot (immutable)

TỔNG: 0 dòng code Python/JS
```

### 4.2 Flow báo giá (Sales User)

```
1. Tạo Quotation → chọn Customer, Profile System
2. Thêm Quotation Item → chọn Item + AL BOM
3. Bấm 📐 Tham số BOM → dialog động từ Variable Set
4. Nhập: W=2400, H=2600, n_panel=2, color=WHITE...
5. Bấm 💰 Tính giá → BomOrchestrator.run()
6. Kết quả: GIA_VAT ≈ 22,717,289 VND
7. ConfigSnapshot lưu để audit
```

### 4.3 Flow sản xuất (từ Sales Order) — core-first v28.9

> **v28.9:** thay Material Plan + Production Order Bridge bằng **core ERPNext** (Production Plan + Material Request + Work Order). AL BOM giữ cho báo giá, bridge qua core BOM instantiated. Chi tiết: `v28.md §E.2`, `§E.2A`, `§E.2B`.
>
> **⚠️ v28.10 — instantiate theo kích thước KHẢO SÁT THỰC:** trigger đổi từ SO submit (nominal dự toán) sang **AL Site Survey Approved** (kích thước thực từng vị trí). 1 AL BOM formula → nhiều core BOM theo từng kích thước khảo sát thực; vị trí trùng kích thước thực gom chung 1 core BOM (fingerprint). MR chỉ phát sinh **sau khảo sát** theo kích thước thực.

```
0. Báo giá: AL BOM tính nominal → ConfigSnapshot quote_config (chỉ báo giá)
1. Khảo sát: AL Site Survey đo actual_width/height_mm từng vị trí → Approved
2. [hook] instantiate core BOM theo kích thước THỰC (từ ConfigSnapshot production, reuse fingerprint)
3. Production Plan (get_items_from = Sales Order) → sinh Work Order (gom qty theo cụm kích thước thực) + Material Request (theo kích thước thực)
4. Material Request → RFQ → Supplier Quotation → Purchase Order
5. Work Order → AL Cutting Plan (Alu + Glass) → cắt tối ưu
6. Quality Inspection → kiểm tra
7. Delivery Note → xuất kho (theo dimension: màu / loại kính / độ dày)
8. Installation Order → thi công
9. Handover Acceptance → nghiệm thu

Cần đặt vật tư nền sớm → raw stock: phôi nhôm + kính tấm theo nominal + buffer trước;
cắt theo kích thước thực sau; MR bổ sung chênh lệch do sai lệch khảo sát (§E.2A lead time).
```

> **v28.9 — kho đa chiều:** nhôm/kính tách tồn + xuất theo **Inventory Dimension** (màu/loại/dày) qua dimension fields trên Stock Entry / Delivery Note / Stock Ledger Entry. Batch (core) chỉ giữ trace lô nhôm. Chi tiết: `05_inventory-dimension-design.md`.

---

## 5. HỆ THỐNG BIẾN — DATA-DRIVEN CONTEXT

### 5.1 Kiến trúc

**File:** [api/__init__.py:get_formula_context()](alumglass/api/__init__.py#L51)

```
8 NGUỒN BIẾN — TỰ ĐỘNG KHÁM PHÁ TỪ DB:

1. AL Cost Bucket          → Cost bucket codes (VL_NHOM, TONG_VL...)
2. AL Variable Library     → System variables (is_system=1)
3. AL Variable Library     → User variables (is_system=0)
4. Formula Global Variable → Global constants
5. Row Literals            → Engine injects per-row
6. Common BOM Vars         → W_mm, H_mm, n_panel...
7. Formula Variable Binding→ Per-doctype bindings
8. ★ AL Variable Set       → Resolved từ docname (nếu có Variable Set)
```

### 5.2 JS Context Flow

**File:** [public/js/formula_setup.js](alumglass/public/js/formula_setup.js) (249 dòng)

```
Form refresh
    │
    ▼
alumglass.FormulaContext.fetch(doctype, docname)
    │
    ▼
API: get_formula_context(doctype, docname)
    │  → Đọc 8 nguồn từ DB
    │  → Resolve Variable Set từ docname (nếu AL Bom Set/AL BOM)
    ▼
Cache (TTL 5 phút)
    │
    ▼
Monkey-patch _ContextBuilder.build()
    │  → Inject biến vào liveCtx.variables
    ▼
Monaco Editor
    ├── Autocomplete: gợi ý khi gõ
    └── Hover: tooltip khi rê chuột
```

### 5.3 Thêm biến mới

| Muốn thêm | Làm gì | Sửa code? |
|-----------|--------|:---:|
| Cost bucket mới | Thêm record `AL Cost Bucket` | ❌ |
| System variable | Thêm record `AL Variable Library` (is_system=1) | ❌ |
| User variable | Thêm record `AL Variable Library` (is_system=0) | ❌ |
| Global constant | Thêm record `Formula Global Variable` | ❌ |
| Slug cross-row | Thêm record `AL Slug Library` | ❌ |
| Biến cho dialog | Thêm record `Formula Variable Binding` | ❌ |
| Biến từ Variable Set | Gán Variable Set cho Bom Set/BOM qua UI | ❌ |

---

## 6. FORMULA BUILDER — TÍCH HỢP & AUTOCOMPLETE

### 6.1 Cấu hình UI

**File:** [public/js/formula_setup.js](alumglass/public/js/formula_setup.js)

```javascript
// Default toàn cục
var ALUMGLASS_FORMULA_DEFAULTS = {
    language    : "formula-builder",
    show_toolbar: false,     // Toolbar (Copy btn)
    show_preview: false,     // Preview bar (▶ + nút Chạy + Editor)
};

// Helper
function ALUMGLASS_OPTS(overrides) {
    return Object.assign({}, ALUMGLASS_FORMULA_DEFAULTS, overrides || {});
}

// Dùng cho child table
formula_builder.formula.initGridField(frm, "items", "width",
    ALUMGLASS_OPTS({ height: "70px", id_field: "slug" }));

// Dùng cho parent form
formula_builder.formula.patchField(frm, "calc_fn",
    ALUMGLASS_OPTS({ height: "80px" }));
```

### 6.2 Các doctype đã tích hợp Formula Builder

| Doctype | Field(s) | Kiểu | Cross-row? |
|---------|----------|------|:---:|
| **AL Bom Set** | width, height, qty, show_condition, item_condition_formula, rule_input_expr | `initGridField` | ✅ `id_field: "slug"` |
| **AL Cost Template** | calc_formula | `initGridField` + float_popup | — |
| **AL Alert Config** | trigger_condition | `patchField` | — |
| **AL Quantity Calc Method** | calc_fn | `patchField` | — |
| **Formula Global Variable** | formula_expr | `patchField` | — |

### 6.3 Cách thêm doctype mới vào Formula Builder

```javascript
// 1. Tạo file JS mới hoặc thêm vào formula_setup.js
frappe.ui.form.on("My New Doctype", {
    refresh(frm) {
        // Load context từ DB
        alumglass.FormulaContext.fetch("My New Doctype", frm.doc.name);

        // Grid child table
        formula_builder.formula.initGridField(frm, "items", "my_formula",
            ALUMGLASS_OPTS({ height: "70px" }));

        // Parent form
        if (frm.fields_dict["overhead_formula"]) {
            formula_builder.formula.patchField(frm, "overhead_formula",
                ALUMGLASS_OPTS({ height: "100px" }));
        }
    },
});

// 2. hooks.py: thêm JS file vào app_include_js
// 3. bench build
```

---

## 7. COMPOSITE KEY PRICING

### 7.1 Cơ chế

**Files:**
- [engine/bom_orchestrator.py:_fetch_composite_prices()](alumglass/engine/bom_orchestrator.py)
- [fb_handlers.py:aluminum_price_composite()](alumglass/fb_handlers.py)
- [al_pricing_dimension.py:_sync_custom_field()](alumglass/al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.py)

> **✅ Owner làm rõ (2026-08-13):** AL Pricing Dimension tạo composite fields trên **Item Price** dùng làm **tham chiếu giá bán trong dialog Quotation**. Giá nhôm tính theo **mã nhôm đại diện** (không theo từng mã profile cụ thể) + các thông số (màu sắc, xuất xứ...). **Độc lập** với Inventory Dimension (kho) — xem `05_inventory-dimension-design.md §4.4`.

```
BƯỚC 1: Định nghĩa Pricing Dimension
  AL Pricing Dimension: MAU_SAC → custom_pd_mau_sac (auto-sinh trên Item Price)

BƯỚC 2: Map Variable → Dimension
  AL Variable Dimension Mapping: aluminum_color → MAU_SAC

BƯỚC 3: Tạo Item Price trên MÃ NHÔM ĐẠI DIỆN với composite fields
  Item Price { item_code: "NHOM-DAI-DIEN", custom_pd_mau_sac: "WHITE", rate: 113000 }
  Item Price { item_code: "NHOM-DAI-DIEN", custom_pd_mau_sac: "DARK",  rate: 145000 }

BƯỚC 4: Engine tự động match khi tính giá (dialog Quotation)
  _fetch_composite_prices():
    → Đọc Variable Dimension Mapping → variable→dimension→custom_fieldname
    → Query tất cả Item Price cho mã đại diện (gồm composite fields)
    → _match_composite_price(): chọn dòng khớp nhất, fallback dòng "trần"
```

### 7.2 Hai chế độ

| Mode | Cách hoạt động | Dùng khi |
|------|---------------|---------|
| **exact_match** | Composite key lookup chính xác | Có bảng giá đầy đủ cho từng tổ hợp |
| **multiplier_chain** | Giá gốc × ∏(hệ số từ dimensions) | Ít tổ hợp, dùng hệ số nhân |

> Cả 2 mode đều hoạt động trên **mã nhôm đại diện** (màu/xuất xứ... làm composite). Không liên quan valuation kho.

---

## 8. ROLE & PERMISSION

### 8.1 4 Role nghiệp vụ

**File:** [setup/install_roles.py](alumglass/setup/install_roles.py) (236 dòng)

| Role | Quyền chính |
|------|-----------|
| **AL Sales User** | CRUD Quotation, Sales Order; Read Master Data, BOM Engine |
| **AL BOM Manager** | Full AL Master Data, AL Bom Engine, AL Formula Rules |
| **AL Site Engineer** | Full AL Construction; Read/Write AL Stock |
| **AL Project Accountant** | Full AL Account; Read/Write AL Buying |

### 8.2 Cài đặt

```python
# hooks.py
after_install = "alumglass.hooks._after_install"
# → install_all_custom_fields()
# → install_roles_and_permissions()
# → 4 roles + DocPerm cho 10 module + ERPNext core doctypes
```

### 8.3 Permission matrix

| Module | AL Sales | AL BOM Mgr | AL Site Eng | AL Accountant |
|--------|:---:|:---:|:---:|:---:|
| Quotation, Sales Order | CRUD | Read | — | — |
| AL Master Data | Read | CRUD | — | — |
| AL Bom Engine | Read | CRUD | Read | — |
| AL Formula Rules | — | CRUD | — | — |
| AL Buying | — | CRUD | — | Read/Write |
| AL Construction | — | Read | CRUD | Read |
| AL Account | — | Read | — | CRUD |

---

## 9. DANH SÁCH FILE — ĐƯỜNG DẪN CỤ THỂ

### 9.1 Core Engine (3 files)

| File | Dòng | Vai trò |
|------|:---:|-------|
| [engine/bom_orchestrator.py](alumglass/engine/bom_orchestrator.py) | 691 | ★ BomOrchestrator 7-phase: B0→B7 |
| [fb_handlers.py](alumglass/fb_handlers.py) | 181 | FB thin layer: aluminum_price_composite, glass_master_data, cost_bucket_aggregate |
| [api/__init__.py](alumglass/api/__init__.py) | 346 | 7 API endpoints + get_formula_context() + _inject_variable_set_vars() |

### 9.2 Config & Setup (4 files)

| File | Dòng | Vai trò |
|------|:---:|-------|
| [hooks.py](alumglass/hooks.py) | 309 | App config: fixtures, fb_source_types, whitelist, after_install |
| [setup/custom_fields.py](alumglass/setup/custom_fields.py) | 172 | Custom field installer cho 15 ERPNext core doctypes |
| [setup/install_roles.py](alumglass/setup/install_roles.py) | 236 | Role + DocPerm installer |
| [setup/seed_demo_data.py](alumglass/setup/seed_demo_data.py) | 371 | Demo data: CDMQ-2C + CDMQ-4C |

### 9.3 JS Client (5 files)

| File | Dòng | Vai trò |
|------|:---:|-------|
| [public/js/formula_setup.js](alumglass/public/js/formula_setup.js) | 249 | ★ Formula Builder integration + context cache + monkey-patch |
| [public/js/cost_template.js](alumglass/public/js/cost_template.js) | 127 | Cost Template: validate + preview + injectContext |
| [public/js/bom_dialog.js](alumglass/public/js/bom_dialog.js) | 139 | Dialog kết quả tính BOM |
| [public/js/quotation_item_dialog.js](alumglass/public/js/quotation_item_dialog.js) | 342 | Dialog tham số BOM (dynamic fields từ Variable Set) |
| [public/js/bom_set_context.js](alumglass/public/js/bom_set_context.js) | 123 | Context bổ sung cho AL Bom Set |

### 9.4 Tests (4 files)

| File | Dòng | Vai trò |
|------|:---:|-------|
| [tests/test_bom_orchestrator.py](alumglass/tests/test_bom_orchestrator.py) | 171 | Integration: CDMQ-2C golden + CDMQ-4C features |
| [tests/test_composite_pricing.py](alumglass/tests/test_composite_pricing.py) | 182 | Composite key: different color + deterministic |
| [run_test.py](alumglass/run_test.py) | 152 | Manual test: CDMQ-2C + CDMQ-4C full output |

### 9.5 Doctype quan trọng (Python controllers)

| File | Vai trò |
|------|-------|
| [al_bom_version.py](alumglass/al_bom_engine/doctype/al_bom_version/al_bom_version.py) | Snapshot + immutability guard |
| [al_pricing_dimension.py](alumglass/al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.py) | Auto-sync custom field trên Item Price |
| [al_quantity_calc_method.py](alumglass/al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py) | calc_fn lambda từ DB |
| [al_calculation_rule.py](alumglass/al_formula_rules/doctype/al_calculation_rule/al_calculation_rule.py) | resolve() cho THRESHOLD/LOOKUP/CONSTANT |
| [al_dynamic_item_rule.py](alumglass/al_formula_rules/doctype/al_dynamic_item_rule/al_dynamic_item_rule.py) | resolve_item() từ input |
| [al_variable_dimension_mapping.py](alumglass/al_master_data/doctype/al_variable_dimension_mapping/al_variable_dimension_mapping.py) | Map variable→dimension |

### 9.6 Fixtures

| File | Vai trò |
|------|-------|
| [fixtures/roles.json](alumglass/fixtures/roles.json) | 4 Role definitions (name + role_name) |

---

## 10. TÀI LIỆU THAM KHẢO

| # | File | Dung lượng | Vai trò |
|---|------|:---:|-------|
| 1 | **[THAM_KHAO_TOAN_DIEN.md](THAM_KHAO_TOAN_DIEN.md)** | — | ★ TÀI LIỆU NÀY — Master reference |
| 2 | **[TONG_QUAN_KIEN_TRUC.md](TONG_QUAN_KIEN_TRUC.md)** | 51KB | Tổng quan kiến trúc + 7-phase flow chi tiết |
| 3 | **[HUONG_DAN_TRIEN_KHAI.md](HUONG_DAN_TRIEN_KHAI.md)** | 17KB | Cài đặt → cấu hình → go-live checklist |
| 4 | **[v28.md](v28.md)** | 317KB | Thiết kế gốc — đặc tả kỹ thuật đầy đủ, 30 nguyên tắc |
| 5 | **[ALUMGLASS_PRODUCTION_REFERENCE.md](ALUMGLASS_PRODUCTION_REFERENCE.md)** | 30KB | Production reference + changelog |
| 6 | **[CAU_TRUC_MODULE_VA_DOCTYPE.md](CAU_TRUC_MODULE_VA_DOCTYPE.md)** | 90KB | Chi tiết từng doctype: fields, mô tả, dữ liệu mẫu |
| 7 | **[CHANGELOG-v28.7.md](CHANGELOG-v28.7.md)** | 18KB | Changelog kỹ thuật v28.7→v28.8 |
| 8 | **[ARCHITECTURE-REVIEW-v28.2.md](ARCHITECTURE-REVIEW-v28.2.md)** | 23KB | Đánh giá kiến trúc + khuyến nghị |
| 9 | **[README.md](README.md)** | 5KB | Quick overview |
| 10 | **[NAMING-CONVENTION.md](NAMING-CONVENTION.md)** | 9KB | Quy ước đặt tên tiếng Anh |
| 11 | **[v28.2-UPGRADE-ANALYSIS.md](v28.2-UPGRADE-ANALYSIS.md)** | 33KB | Phân tích nâng cấp + hardcode elimination |
| 12 | **[KE_HOACH_TRIEN_KHAI_CHI_TIET.md](KE_HOACH_TRIEN_KHAI_CHI_TIET.md)** | 133KB | Kế hoạch triển khai chi tiết |
| 13 | **[AlumGlass_Vi_Du_Full_Chi_Tiet.md](AlumGlass_Vi_Du_Full_Chi_Tiet.md)** | 72KB | Ví dụ A-Z đầy đủ |
| 14 | **[frappe-permission-system.md](frappe-permission-system.md)** | 113KB | Hệ thống permission Frappe |
| 15 | **[HUONG_DAN_FORMULA.md](alumglass/public/js/HUONG_DAN_FORMULA.md)** | — | ★ A-Z Formula Builder: cấu hình, autocomplete, nguồn biến |
| 16 | **[AlumGlass_Review_Patches/](AlumGlass_Review_Patches/)** | — | Review + patches (PATCH_composite_pricing, PATCH_deploy, REVIEW_production) |

---

*AlumGlass ERP v28.8 — 2026-08-05*
