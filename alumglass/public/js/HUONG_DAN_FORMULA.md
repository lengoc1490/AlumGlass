# ALUMGLASS ERP — DANH MỤC TOÀN BỘ DOCTYPE & KIẾN TRÚC HỆ THỐNG

> **Phiên bản:** v28.8 | **Cập nhật:** 2026-08-06
> **Tổng số doctype:** 57 (bao gồm child tables)
> **Module:** 11 module nghiệp vụ + 1 engine + API + FB handlers

---

## MỤC LỤC

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Sơ đồ luồng dữ liệu end-to-end](#2-sơ-đồ-luồng-dữ-liệu-end-to-end)
3. [Module: AL Master Data (12 doctypes)](#3-module-al-master-data)
4. [Module: AL Bom Engine (12 doctypes)](#4-module-al-bom-engine)
5. [Module: AL Formula Rules (8 doctypes)](#5-module-al-formula-rules)
6. [Module: AL Buying (5 doctypes)](#6-module-al-buying)
7. [Module: AL Manufacturing (6 doctypes)](#7-module-al-manufacturing)
8. [Module: AL Construction (10 doctypes)](#8-module-al-construction)
9. [Module: AL Account (2 doctypes)](#9-module-al-account)
10. [Module: AL Quality (1 doctype)](#10-module-al-quality)
11. [Module: AL Stock (1 doctype)](#11-module-al-stock)
12. [Module: AL AI Intelligence (3 doctypes)](#12-module-al-ai-intelligence)
13. [Core ERPNext Custom Fields](#13-core-erpnext-custom-fields)
14. [Engine: BomOrchestrator (7-phase)](#14-engine-bomorchestrator)
15. [API & FB Handlers](#15-api--fb-handlers)
16. [Phụ lục: Ma trận quan hệ Doctype](#16-phụ-lục-ma-trận-quan-hệ-doctype)

---

## 1. TỔNG QUAN KIẾN TRÚC

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ALUMGLASS ERP                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ AL MASTER    │  │ AL BOM       │  │ AL FORMULA   │               │
│  │ DATA (12)    │  │ ENGINE (12)  │  │ RULES (8)    │               │
│  │              │  │              │  │              │               │
│  │ • Variable   │  │ • AL BOM     │  │ • Calc Rule  │               │
│  │   Library    │──│ • Bom Set    │──│ • Dyn Item   │               │
│  │ • Variable   │  │ • Bom Item   │  │   Rule       │               │
│  │   Set        │  │ • Bom Ver    │  │ • Qty Calc   │               │
│  │ • Material   │  │ • Cost Templ │  │   Method     │               │
│  │   Category   │  │ • Cost Bucket│  │ • Rule Ver   │               │
│  │ • Profile    │  │ • Accessory  │  │              │               │
│  │   System     │  │   Set/Item   │  │              │               │
│  │ • Glass      │  │ • Design Rev │  │              │               │
│  │   Master     │  │ • ConfigSnap │  │              │               │
│  │ • Pricing    │  │ • Change Log │  │              │               │
│  │   Dimension  │  │              │  │              │               │
│  │ • Slug Lib   │  │              │  │              │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                 │                       │
│         └─────────┬───────┴─────────┬───────┘                       │
│                   │                 │                               │
│                   ▼                 ▼                               │
│  ┌──────────────────────────────────────────────┐                   │
│  │            ENGINE LAYER                      │                   │
│  │  BomOrchestrator (7-phase)                   │                   │
│  │  B0→B1→B2→B3→B4→B5→B6→B7                     │                   │
│  │  + FormulaEngine (FB) + FlexibleFormulaEngine│                   │
│  │  + api/__init__.py + fb_handlers.py          │                   │
│  └──────────────────┬───────────────────────────┘                   │
│                     │                                               │
│                     ▼                                               │
│  ┌───────────────────────────────────────────────┐                  │
│  │            EXECUTION LAYER                    │                  │
│  │  ┌───────────┐ ┌───────────┐ ┌──────────────┐ │                  │
│  │  │ AL BUYING │ │AL MFG (6) │ │AL CONSTRUCT  │ │                  │
│  │  │ (5)       │ │• Cut Plan │ │ (10)         │ │                  │
│  │  │• Mat Plan │ │• Cut Std  │ │• Install Ord │ │                  │
│  │  │• Sup Price│ │• Prod Brdg│ │• Site Survey │ │                  │
│  │  │• Cost Var │ │           │ │• Handover    │ │                  │
│  │  └───────────┘ └───────────┘ │• Change Ord  │ │                  │
│  │                              └──────────────┘ │                  │
│  │  ┌──────────┐ ┌───────────┐ ┌─────────────┐   │                  │
│  │  │AL ACCOUNT│ │AL QUALITY │ │AL STOCK (1) │   │                  │
│  │  │ (2)      │ │ (1)       │ │• Proj WH Map│   │                  │
│  │  │• Fin Cfg │ │• Warranty │ │             │   │                  │
│  │  │• Profit  │ │  Policy   │ │             │   │                  │
│  │  └──────────┘ └───────────┘ └─────────────┘   │                  │
│  │  ┌──────────┐                                 │                  │
│  │  │AL AI (3) │ ← cross-cutting                 │                  │
│  │  │• Alert   │                                 │                  │
│  │  │• Suggest │                                 │                  │
│  │  └──────────┘                                 │                  │
│  └───────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Vai trò từng module

| Module | Vai trò | Số doctype |
|--------|---------|:---------:|
| **AL Master Data** | Dữ liệu chủ: biến, profile, kính, màu, giá, slug, category | 12 |
| **AL Bom Engine** | Cấu trúc BOM: định nghĩa sản phẩm, công thức, cost, phiên bản | 12 |
| **AL Formula Rules** | Rule engine: quy tắc chọn item, công thức tính số lượng | 8 |
| **AL Buying** | Mua hàng: kế hoạch vật tư, bảng giá NCC, chênh lệch chi phí | 5 |
| **AL Manufacturing** | Sản xuất: kế hoạch cắt nhôm/kính, tiêu chuẩn cắt | 6 |
| **AL Construction** | Thi công: khảo sát, lắp đặt, nghiệm thu, phát sinh | 10 |
| **AL Account** | Tài chính dự án: cấu hình tài chính, snapshot lợi nhuận | 2 |
| **AL Quality** | Chất lượng: chính sách bảo hành | 1 |
| **AL Stock** | Kho: map kho theo dự án | 1 |
| **AL AI Intelligence** | AI/Alert: cảnh báo, gợi ý, log tương tác | 3 |
| **Core ERPNext CF** | Custom fields trên Quotation, Item, Work Order... | ~13 doctypes |

---

## 2. SƠ ĐỒ LUỒNG DỮ LIỆU END-TO-END

```
┌────────────────────────────────────────────────────────────────────────┐
│ FLOW BÁO GIÁ → SẢN XUẤT → THI CÔNG → NGHIỆM THU                        │
│                                                                        │
│  1. CẤU HÌNH (AL Master Data)                                          │
│     AL Profile System ─┐                                               │
│     AL Material Cat ───┼──► AL Variable Library ──► AL Variable Set    │
│     AL Glass Master ───┘        ▲                                      │
│     AL Pricing Dimension ───────┤                                      │
│     AL Variable Dim Mapping ────┘                                      │
│                                                                        │
│  2. ĐỊNH NGHĨA SẢN PHẨM (AL Bom Engine)                                │
│     AL Slug Library ──► AL Bom Set ──► AL Bom Item (child table)       │
│     AL Cost Bucket ──► AL Cost Template ──► AL Cost Template Item      │
│                              │                                         │
│                              ▼                                         │
│                         AL BOM ──► AL BOM Version (snapshot)           │
│                                        │                               │
│  3. BÁO GIÁ (Quotation + Core ERPNext)                                 │
│     Quotation ──► Quotation Item                                       │
│                      │ .al_bom → AL BOM                                │
│                      │ .al_bom_version → AL BOM Version                │
│                      │ .al_bom_vars → JSON input từ dialog             │
│                      │                                                 │
│                      ▼                                                 │
│  4. TÍNH GIÁ (Engine)                                                  │
│     BomOrchestrator.run(quotation_item_name)                           │
│       B0: Pin version                                                  │
│       B1: Gather inputs (W_mm, H_mm, color, origin...)                 │
│       B2: Prefetch master (glass, item price composite-key)            │
│       B3: Build formulas (compile Bom Items → formula list)            │
│       B4: Calculate via FormulaEngine                                  │
│       B5: Aggregate cost buckets                                       │
│       B6: Calculate cost template via FlexibleFormulaEngine            │
│       B7: Save → ConfigSnapshot + Quotation Item fields                │
│                      │                                                 │
│                      ▼                                                 │
│     Sales Order ──► AL Installation Order                              │
│                                                                        │
│  5. MUA HÀNG & SẢN XUẤT                                                │
│     AL Material Plan ──► Purchase Order                                │
│     AL Cutting Plan Al/Glass ──► AL Production Order Bridge ──► WO     │
│                                                                        │
│  6. THI CÔNG                                                           │
│     AL Site Survey ──► AL Installation Order ──► AL Install Task       │
│     AL Installation Progress                                           │
│     AL Change Order (phát sinh)                                        │
│                                                                        │
│  7. NGHIỆM THU & BẢO HÀNH                                              │
│     AL Handover Acceptance ──► AL Punchlist Item                       │
│     AL Warranty Policy ──► Warranty Claim                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MODULE: AL MASTER DATA

Module dữ liệu chủ — tất cả các bảng tham chiếu cốt lõi. Mọi thứ đều data-driven.

### 3.1 AL Profile System — Hệ profile nhôm

**File:** `al_master_data/doctype/al_profile_system/`
**Autoname:** `field:system_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `system_code` | Data (reqd, unique) | Mã hệ profile (vd: XINGFA_55) |
| `system_name` | Data (reqd) | Tên hiển thị |
| `brand` | Link→Brand (reqd) | Thương hiệu (XINGFA, ALUMIL...) |
| `is_active` | Check (default 1) | Đang hoạt động? |
| `offset_frame` | Float (reqd) | Khe hở khung-cánh (mm) — dùng trong công thức width/height |
| `offset_glass` | Float (reqd) | Khe hở cánh-kính (mm) |
| `offset_fixed` | Float (reqd) | Khe hở khung-kính cố định (mm) |
| `offset_crossbar` | Float (reqd) | Khe hở đố ngang (mm) |

**Cách dùng:** Khi chọn profile system cho Bom Set, các offset được resolve thành system variables (`OFFSET_FRAME`, `OFFSET_GLASS`, `OFFSET_FIXED`, `OFFSET_DO_NGANG`) dùng trong công thức Bom Item.

---

### 3.2 AL Material Category — Phân loại vật tư

**File:** `al_master_data/doctype/al_material_category/`
**Autoname:** `field:category_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `category_code` | Data (reqd, unique) | Mã loại (NHOM, KINH, VTP, PK...) |
| `category_name` | Data (reqd) | Tên hiển thị |
| `default_calc_pattern` | Link→AL Quantity Calc Method (reqd) | Pattern tính số lượng mặc định |
| `default_cost_bucket` | Link→AL Cost Bucket | Cost bucket mặc định |
| **Flags quy định behavior:** | | |
| `requires_item_code` | Check (default 1) | Bắt buộc item_code khi mode=Fixed |
| `requires_price_base_item` | Check (default 0) | Bắt buộc price_base_item cho tra giá composite key |
| `requires_glass_master` | Check (default 0) | Bắt buộc glass master (cho KINH) |
| `requires_ctx_inject_prefix` | Check (default 0) | Bắt buộc ctx inject prefix |
| `has_weight` | Check (default 0) | Có trọng lượng riêng (kg/m)? |
| `has_dimensions` | Check (default 1) | Có kích thước WxH? |
| `default_scrap_pct` | Float (default 0) | % Hao hụt mặc định |

**Cách dùng:** Mỗi dòng Bom Item được gán 1 category. Category quy định validation rules (Item Code bắt buộc? Cần glass master?) và default calc pattern. Flags được đọc bởi `al_bom_item.py:validate()` để kiểm tra data-driven.

---

### 3.3 AL Variable Library — Thư viện biến tập trung

**File:** `al_master_data/doctype/al_variable_library/`
**Autoname:** `field:var_name`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `var_name` | Data (reqd, unique) | Tên biến dùng trong công thức (W_mm, n_panel...) |
| `var_label` | Data | Nhãn hiển thị |
| `var_type` | Select (reqd) | Float / Int / Data / Select / Link / Check / Currency |
| `category` | Data | Nhóm: Kích thước, Cấu hình, Màu sắc... |
| `is_system` | Check (default 0) | System variable? (ẩn trong dialog, resolve tự động) |
| `link_doctype` | Link→DocType | Cho field kiểu Link |
| `select_options` | Small Text | Cho field kiểu Select |
| `source_doctype` | Link→DocType | Doctype nguồn resolve system var |
| `source_field` | Data | Field nguồn trong doctype |
| `default_value` | Data | Giá trị mặc định toàn cục |
| `description` | Small Text | Mô tả |

**Cách dùng:** Định nghĩa 1 lần, dùng nhiều nơi. System variables (`is_system=1`) được resolve tự động từ `source_doctype.source_field` khi chạy BOM. User variables (`is_system=0`) hiển thị trong dialog Tham số BOM.

**Ví dụ system variable:**
- `OFFSET_FRAME` → nguồn: `AL Profile System.offset_frame`
- `NC_SX_PCT` → nguồn: `AL Product Type.nc_pct`

**Ví dụ user variable:**
- `W_mm` (Float) — Chiều rộng, user nhập
- `aluminum_color` (Link→AL Color Standard) — Màu nhôm, user chọn

---

### 3.4 AL Variable Set — Bộ biến cho sản phẩm

**File:** `al_master_data/doctype/al_variable_set/`
**Autoname:** `field:set_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `set_code` | Data (reqd, unique) | Mã bộ biến (VS-CDMQ) |
| `set_name` | Data (reqd) | Tên hiển thị |
| `product_type` | Link→AL Product Type | Loại sản phẩm |
| `is_active` | Check (default 1) | Đang hoạt động? |
| `items` | Table→AL Variable Set Item (reqd) | Danh sách biến |

---

### 3.5 AL Variable Set Item — Dòng biến trong Variable Set

**File:** `al_master_data/doctype/al_variable_set_item/`
**istable:** Yes

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `variable` | Link→AL Variable Library (reqd) | Chọn biến từ thư viện |
| `var_label` | Data (read_only) | Tự động từ Variable Library |
| `var_type` | Data (read_only) | Tự động từ Variable Library |
| `link_doctype` | Data (read_only) | Tự động |
| `select_options` | Small Text (read_only) | Tự động |
| `default_value` | Data | Ghi đè default nếu cần |
| `sort_order` | Int | Thứ tự hiển thị |
| `is_required` | Check (default 0) | Bắt buộc nhập? |

**Cách dùng:** `before_save()` tự động fill label/type/options từ Variable Library. Khi người dùng mở dialog Tham số BOM, JS gọi `get_variable_set_for_bom()` → trả về danh sách biến → tự sinh form fields.

---

### 3.6 AL Product Type — Loại sản phẩm

**File:** `al_master_data/doctype/al_product_type/`
**Autoname:** `field:type_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `type_code` | Data (reqd, unique) | DOOR, WINDOW, PARTITION... |
| `type_name` | Data | Tên hiển thị |
| `nc_pct` | Float | % Nhân công sản xuất |
| `nc_ld_rate` | Float | % Nhân công lắp đặt |
| `profit_margin` | Float | % Lợi nhuận mục tiêu |
| `default_warranty_policy` | Link→AL Warranty Policy | Chính sách bảo hành mặc định |

**Cách dùng:** `nc_pct`, `nc_ld_rate`, `profit_margin` được resolve thành system variables khi chạy BOM.

---

### 3.7 AL Slug Library — Thư viện định danh dòng BOM

**File:** `al_master_data/doctype/al_slug_library/`
**Autoname:** `field:slug`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `slug` | Data (reqd, unique) | Mã định danh (khung_ngang_tren, kinh_canh...) |
| `label` | Data (reqd) | Tên hiển thị |
| `category` | Link→AL Material Category (reqd) | Loại vật tư |
| `group_tag` | Data | Nhóm (KHUNG, CANH, GLASS, NEP, KEO...) |
| `description` | Small Text | Mô tả |

**Vai trò then chốt:**
1. **Định danh duy nhất** mỗi dòng Bom Item — dùng cho cross-row reference (`items.kinh_tren.width`)
2. **Auto-fill category** khi chọn slug trong Bom Item
3. **Phân nhóm** trong autocomplete formula builder

---

### 3.8 AL Glass Master — Thông số kính

**File:** `al_master_data/doctype/al_glass_master/`
**Autoname:** `field:glass_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `glass_code` | Data (reqd, unique) | Mã kính (KINH-LOWE-24) |
| `glass_name` | Data | Tên hiển thị |
| `total_thick_mm` | Float (reqd) | Tổng độ dày (mm) |
| `glass_type` | Link→AL Glass Type (reqd) | Loại kính (DON, CUONG_LUC, HOP, LOWE...) |
| `u_value` | Float | Hệ số truyền nhiệt U-Value |
| `shgc` | Float | Hệ số hấp thụ nhiệt SHGC |
| `vlt` | Float | Độ truyền sáng VLT |

**Cách dùng:** Dòng KINH trong Bom Item trỏ đến Glass Master. Engine đọc `total_thick_mm` và `glass_type` để resolve Dynamic Item Rule (chọn nẹp theo độ dày, chọn keo theo loại kính).

---

### 3.9 AL Glass Type — Loại kính

**File:** `al_master_data/doctype/al_glass_type/`
**Autoname:** `field:type_code`

| Field | Kiểu |
|-------|------|
| `type_code` | Data (reqd, unique) |
| `type_name` | Data |

---

### 3.10 AL Color Standard — Tiêu chuẩn màu

**File:** `al_master_data/doctype/al_color_standard/`
**Autoname:** `field:color_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `color_code` | Data (reqd, unique) | WHITE, DARK, GRAY, GO... |
| `color_name` | Data | Tên hiển thị |
| `applies_to` | Link→Item Group | Áp dụng cho nhóm item |
| `is_standard_stock` | Check | Màu tồn kho tiêu chuẩn? |
| `price_multiplier` | Float (default 1.0) | Hệ số nhân giá (1.08 = tăng 8%) |
| `default_safety_stock_qty` | Float | Tồn kho an toàn mặc định |
| `surcharge_rule` | Link→AL Calculation Rule | Rule phụ thu |

**Cách dùng:** Dùng trong composite pricing: `aluminum_color = WHITE` → `custom_pd_mau_sac = WHITE` → match Item Price có màu Trắng. `price_multiplier` dùng trong mode `multiplier_chain`.

---

### 3.11 AL Pricing Dimension — Chiều giá động

**File:** `al_master_data/doctype/al_pricing_dimension/`
**Autoname:** `field:dimension_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `dimension_code` | Data (reqd, unique) | MAU_SAC, XUAT_XU, DO_DAY, BE_MAT |
| `dimension_name` | Data (reqd) | Tên hiển thị |
| `dimension_type` | Select (reqd) | Link / Select / Data / Float / Int |
| `link_doctype` | Link→DocType | Cho type=Link |
| `select_options` | Small Text | Cho type=Select |
| `custom_fieldname` | Data (read_only) | Tự sinh: `custom_pd_{code}` |
| `is_required_for_price` | Check | Bắt buộc khi tạo Item Price? |
| `is_active` | Check (default 1) | |
| `sort_order` | Int | |

**Cơ chế:** `after_insert()` và `on_update()` tự động sync Custom Field lên Item Price (tên `custom_pd_{dimension_code.lower()}`). Đây là cơ chế giống Accounting Dimension của ERPNext: thêm chiều giá mới = 1 record, không cần code.

---

### 3.12 AL Variable Dimension Mapping — Map biến → chiều giá

**File:** `al_master_data/doctype/al_variable_dimension_mapping/`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `variable_name` | Data (reqd) | Tên biến đầu vào (aluminum_color) |
| `pricing_dimension` | Link→AL Pricing Dimension (reqd) | Chiều giá (MAU_SAC) |
| `material_category` | Link→AL Material Category | Lọc theo loại vật tư |
| `price_multiplier` | Float (default 1.0) | Hệ số nhân giá |

**Cách dùng:** Engine đọc mapping → build map `variable_name → custom_fieldname`. Khi tra giá: `aluminum_color=WHITE` → tìm dimension `MAU_SAC` → field `custom_pd_mau_sac` → match trên Item Price.

---

## 4. MODULE: AL BOM ENGINE

Module trung tâm — định nghĩa cấu trúc BOM, quản lý phiên bản, snapshot.

### 4.1 AL BOM — Header BOM

**File:** `al_bom_engine/doctype/al_bom/`
**Autoname:** `field:bom_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `bom_code` | Data (reqd, unique) | Mã BOM (BOM-CDMQ-2C) |
| `bom_name` | Data | Tên hiển thị |
| `product_type` | Link→AL Product Type | Loại sản phẩm |
| `brand` | Link→Brand | Thương hiệu |
| `representative_item` | Link→Item (reqd) | **Item đại diện** cho nhôm chính (NHOM-XINGFA). Dùng để reference, KHÔNG phải mã bán ra. Giá thực tế tra qua `price_base_item` trên từng dòng Bom Item |
| `is_active` | Check (default 1) | |
| `bom_set` | Link→AL Bom Set (reqd) | Bộ định nghĩa cấu trúc |
| `pk_set` | Link→AL Accessory Set | Bộ phụ kiện (optional) |
| `default_cost_template` | Link→AL Cost Template (reqd) | Template tính giá thành |
| `current_version` | Link→AL BOM Version (read_only) | Version hiện tại (tự động set khi Published) |
| `requires_approval_for_new_version` | Check (default 0) | Yêu cầu duyệt khi tạo version mới? |
| `default_installation_team` | Link→AL Installation Team | Đội thi công mặc định |

**Python:** `validate()` kiểm tra bom_set và cost_template tồn tại. API `get_bom_structure(bom_code)` trả về BOM + Bom Set + Items.

---

### 4.2 AL Bom Set — Bộ định nghĩa cấu trúc sản phẩm

**File:** `al_bom_engine/doctype/al_bom_set/`
**Autoname:** `field:set_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `set_code` | Data (reqd, unique) | Mã bộ (BS-CDMQ-2C) |
| `set_name` | Data (reqd) | Tên hiển thị |
| `product_type` | Link→AL Product Type | |
| `brand` | Link→Brand | |
| `profile_system` | Link→AL Profile System | Hệ profile (quyết định offset) |
| `variable_set` | Link→AL Variable Set | Tập biến đầu vào |
| `default_accessory_set` | Link→AL Accessory Set | Bộ phụ kiện mặc định |
| `version` | Data | Phiên bản |
| `is_active` | Check (default 1) | |
| `formula_fieldnames` | Small Text | JSON array các field công thức: `["width","height","qty","show_condition","item_condition_formula","rule_input_expr"]` |
| `items` | Table→AL Bom Item (reqd) | Danh sách dòng vật tư |

---

### 4.3 AL Bom Item — Dòng vật tư (TRUNG TÂM)

**File:** `al_bom_engine/doctype/al_bom_item/`
**istable:** Yes (child của AL Bom Set)

| Section | Field | Kiểu | Mô tả |
|---------|-------|------|-------|
| **Basic** | `slug` | Link→AL Slug Library (reqd) | Định danh dòng (khung_ngang_tren...) |
| | `category` | Link→AL Material Category (read_only) | Auto-fill từ slug |
| | `line_name` | Data | Tên hiển thị (auto-fill) |
| | `is_active` | Check (default 1) | |
| | `show_condition` | Small Text | Công thức FB — ẩn/hiện dòng |
| | `cost_bucket` | Link→AL Cost Bucket | Nhóm chi phí |
| **Item Selection** | `item_selection_mode` | Select (reqd) | **Fixed** / **Rule** / **Formula** |
| | `item_code` | Link→Item | Item cố định (mode=Fixed) |
| | `item_rule` | Link→AL Dynamic Item Rule | Rule chọn item (mode=Rule) |
| | `item_fallback` | Link→Item | Item dự phòng |
| | `item_condition_formula` | Small Text | Công thức điều kiện (mode=Formula) |
| **Override** | `allow_sales_override` | Check | Cho phép sales override item? |
| | `override_item_group` | Link→Item Group | Nhóm item được override |
| | `allow_substitute` | Check | Cho phép thay thế? |
| | `substitute_item_group` | Link→Item Group | Nhóm item thay thế |
| **Dimensions** | `width` | Small Text | Công thức FB chiều rộng |
| | `height` | Small Text | Công thức FB chiều cao |
| | `qty` | Small Text (reqd) | Công thức FB số lượng |
| | `calc_pattern` | Link→AL Quantity Calc Method | Pattern tính unit_qty |
| **Pricing** | `price_type` | Select | Item Price / Rule / Fixed |
| | `price_base_item` | Link→Item | **Item đại diện tra giá composite key.** VD: NHOM-XINGFA |
| | `price_rule` | Link→AL Calculation Rule | Rule tính giá |
| | `price_list` | Link→Price List | Bảng giá |
| | `fixed_price` | Currency | Giá cố định |
| | `cut_fee_pct` | Float | % Phí cắt |
| **Glass** | `default_glass_master` | Link→AL Glass Master | Kính mặc định |
| | `ctx_inject_prefix` | Data | Prefix inject context |
| | `panel_count_formula` | Small Text | Công thức số panel |
| | `qty_per_panel_formula` | Small Text | Công thức SL/panel |
| | `panel_glass_override_allowed` | Check | Cho override kính panel? |
| **Rule Config** | `rule_input_expr` | Small Text | Biểu thức input cho Rule (vd: `items.kinh_tren.glass_thick`) |
| | `formula_set` | Link→Formula Set | Bộ công thức FB |

**3 chế độ Item Selection:**

| Mode | Field dùng | Mô tả | Ví dụ |
|------|-----------|-------|-------|
| **Fixed** | `item_code` | Dùng item cố định | `khung_ngang_tren → XF55-KB-20` |
| **Rule** | `item_rule` + `rule_input_expr` | Rule chọn item dựa trên input | `nep_kinh → RULE-NEP-GLASSTHICK`, input=`items.kinh_tren.glass_thick` |
| **Formula** | `item_condition_formula` | Công thức FB quyết định item | `IF(glass_thick>16,'C3211-20','C3209-20')` |

**Python validation (data-driven):**
- `requires_item_code` → bắt buộc item_code khi mode=Fixed
- `requires_price_base_item` → bắt buộc price_base_item khi price_type=Item Price
- `requires_glass_master` → bắt buộc glass master cho KINH
- `qty` luôn bắt buộc
- Rule mode → bắt buộc item_rule + rule_input_expr
- Formula mode → bắt buộc item_condition_formula

---

### 4.4 AL BOM Version — Snapshot bất biến

**File:** `al_bom_engine/doctype/al_bom_version/`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `bom` | Link→AL BOM (reqd) | BOM cha |
| `version_name` | Data (reqd) | Tên version (v1.0, v2.0...) |
| `valid_from` | Datetime (reqd) | Hiệu lực từ |
| `valid_to` | Datetime | Hiệu lực đến |
| `workflow_state` | Select | Draft / Pending Approval / Approved / Published / Retired |
| `bom_set_snapshot` | JSON | Snapshot Bom Set (tự động khi before_insert) |
| `cost_template_snapshot` | JSON | Snapshot Cost Template |
| `items` | Table→AL BOM Change Log | Lịch sử thay đổi |

**Cơ chế snapshot:**
1. `before_insert()` → `_take_snapshots()` chụp toàn bộ Bom Set items (bao gồm tất cả Small Text fields) + Cost Template items thành JSON
2. `_get_bom_item_formula_fields()` đọc meta của AL Bom Item, lấy tất cả field có fieldtype=Small Text → tự động chụp mọi công thức
3. `validate()` → `_guard_published_immutability()` chặn sửa snapshot sau Published
4. `on_update()` → khi Published, tự động set `AL BOM.current_version`

**Tại sao cần?** Mỗi báo giá gắn với 1 version → luôn truy ngược được "lúc báo giá dùng công thức gì, giá bao nhiêu". Immutable = không ai sửa được sau khi gửi khách.

---

### 4.5 AL BOM Change Log — Nhật ký thay đổi

**File:** `al_bom_engine/doctype/al_bom_change_log/`
**istable:** Yes (child của AL BOM Version)

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `change_type` | Select | Added / Modified / Removed |
| `field_name` | Data | Tên field thay đổi |
| `old_value` | Text | Giá trị cũ |
| `new_value` | Text | Giá trị mới |
| `changed_by` | Link→User | Người thay đổi |
| `changed_on` | Datetime | Thời điểm |
| `reason` | Text | Lý do |

---

### 4.6 AL Design Revision — Yêu cầu thay đổi thiết kế

**File:** `al_bom_engine/doctype/al_design_revision/`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `revision_code` | Data (reqd) | Mã yêu cầu |
| `bom` | Link→AL BOM (reqd) | BOM liên quan |
| `requested_by` | Link→User (reqd) | Người yêu cầu |
| `revision_type` | Select (reqd) | DIMENSION / MATERIAL / PROFILE_SYSTEM / GLASS_SPEC / ACCESSORY |
| `workflow_state` | Select | Draft / Under Review / Approved / Implemented |
| `description` | Text (reqd) | Mô tả thay đổi |
| `old_spec_json` | JSON | Spec cũ |
| `new_spec_json` | JSON | Spec mới |
| `impact_analysis` | Text | Phân tích ảnh hưởng |
| `requires_new_bom_version` | Check (default 0) | Cần tạo version mới? |
| `new_bom_version` | Link→AL BOM Version | Version mới (tự động tạo) |

**Cơ chế:** Khi Approved + `requires_new_bom_version=1`, `on_update()` tự động tạo AL BOM Version mới (Draft, version_name=`v{N}.0`).

---

### 4.7 AL Cost Bucket — Nhóm chi phí

**File:** `al_bom_engine/doctype/al_cost_bucket/`
**Autoname:** `field:bucket_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `bucket_code` | Data (reqd, unique) | VL_NHOM, VL_KINH, TONG_VL, GIA_VAT... |
| `bucket_name` | Data | Tên hiển thị |
| `bucket_role` | Select | LEAF (chi phí gốc) / AGGREGATE (tổng hợp) |
| `parent_bucket` | Link→AL Cost Bucket | Bucket cha |
| `source_type` | Select | aggregate_from_items / formula / doctype_query / custom_function / constant / pipeline / conditional / fallback_chain |
| `source_config` | JSON | Cấu hình nguồn dữ liệu |
| `depends_on` | JSON | Danh sách bucket phụ thuộc |
| `report_group` | Data | Nhóm báo cáo |
| `sort_order` | Int | Thứ tự |

**Cách dùng:** Mỗi dòng Bom Item gán 1 cost_bucket. Engine B5 gom `line_total` theo bucket. Cost Template dùng bucket codes làm biến trong công thức.

---

### 4.8 AL Cost Template — Template tính giá thành

**File:** `al_bom_engine/doctype/al_cost_template/`
**Autoname:** `field:template_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `template_code` | Data (reqd, unique) | CT-01-STANDARD |
| `template_name` | Data (reqd) | Tên hiển thị |
| `product_type` | Link→AL Product Type | |
| `is_active` | Check (default 1) | |
| `items` | Table→AL Cost Template Item (reqd) | 14 dòng chuẩn |

---

### 4.9 AL Cost Template Item — Dòng công thức giá thành

**File:** `al_bom_engine/doctype/al_cost_template_item/`
**istable:** Yes

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `line_code` | Data (reqd) | Mã dòng (TONG_VL, NC_SX, GIA_VAT...) |
| `line_label` | Data | Nhãn hiển thị |
| `calc_formula` | Small Text (reqd) | **Công thức FB tính giá.** VD: `VL_NHOM + VL_KINH + VL_VTP + VL_PK` |
| `cost_bucket` | Link→AL Cost Bucket | Bucket liên quan |
| `is_subtotal` | Check | Là dòng tổng phụ? |
| `show_on_quotation` | Check | Hiển thị trên báo giá? |
| `sort_order` | Int | Thứ tự |

**Chuỗi 14 dòng chuẩn:**
```
VL_NHOM, VL_KINH, VL_VTP, VL_PK → TONG_VL → NC_SX, NC_LD → TONG_NC
→ OH_VC, OH_QLY → TONG_OH → GIA_THANH → PROFIT → GIA_BAN → VAT → GIA_VAT
```

---

### 4.10 AL Accessory Set — Bộ phụ kiện

**File:** `al_bom_engine/doctype/al_accessory_set/`
**Autoname:** `field:set_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `set_code` | Data (reqd, unique) | ACC-CDMQ-2C |
| `set_name` | Data (reqd) | Tên hiển thị |
| `product_type` | Link→AL Product Type | |
| `variable_set` | Link→AL Variable Set | Tập biến dùng chung |
| `is_active` | Check (default 1) | |
| `items` | Table→AL Accessory Item | Danh sách phụ kiện |

---

### 4.11 AL Accessory Item — Dòng phụ kiện

**File:** `al_bom_engine/doctype/al_accessory_item/`
**istable:** Yes

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `slug` | Data (reqd) | Định danh (tay_nam, khoa, ban_le...) |
| `item_code` | Link→Item (reqd) | Mã item phụ kiện |
| `qty` | Float | Số lượng cố định |
| `qty_formula` | Small Text | **Công thức FB tính số lượng.** VD: `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel` |
| `unit_price` | Currency | Đơn giá |

---

### 4.12 ConfigSnapshot — Audit trail tính toán

**File:** `al_bom_engine/doctype/configsnapshot/`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `bom_version` | Link→AL BOM Version | Version BOM đã dùng |
| `quotation_item_name` | Data | Dòng báo giá |
| `inputs_json` | JSON | Input đầu vào (W_mm, color...) |
| `result_json` | JSON | Kết quả tính toán (buckets, cost_template, lines) |
| `calculation_timestamp` | Datetime | Thời điểm tính |

**Cách dùng:** Mỗi lần tính BOM, BomOrchestrator B7 tạo 1 ConfigSnapshot → full audit trail.

---

## 5. MODULE: AL FORMULA RULES

Module quy tắc tính toán — rule engine chọn item, tính số lượng.

### 5.1 AL Calculation Rule — Quy tắc tính toán

**File:** `al_formula_rules/doctype/al_calculation_rule/`
**Autoname:** `field:rule_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `rule_code` | Data (reqd, unique) | OFFSET-FRAME, RULE-BANLE-QTY... |
| `rule_name` | Data | Tên hiển thị |
| `rule_type` | Select (reqd) | **CONSTANT** / **THRESHOLD** / **LOOKUP** |
| `constant_value` | Float | Giá trị hằng số (mode=CONSTANT) |
| `is_active` | Check (default 1) | |
| `threshold_rows` | Table→AL Rule Threshold Row | Ngưỡng (mode=THRESHOLD) |
| `lookup_rows` | Table→AL Rule Lookup Row | Tra cứu (mode=LOOKUP) |

**3 chế độ:**

| Mode | Mô tả | Ví dụ |
|------|-------|-------|
| CONSTANT | Trả về hằng số | `OFFSET-FRAME → 48` |
| THRESHOLD | Input trong khoảng [from,to] → result | `RULE-BANLE-QTY`: 0-2100→2, 2101-2700→3, 2701+→4 |
| LOOKUP | Match key → result | (ít dùng trong demo) |

**Python:** `resolve(input_value)` trả về kết quả dựa trên rule_type.

---

### 5.2 AL Dynamic Item Rule — Quy tắc chọn Item động

**File:** `al_formula_rules/doctype/al_dynamic_item_rule/`
**Autoname:** `field:rule_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `rule_code` | Data (reqd, unique) | RULE-NEP-GLASSTHICK, RULE-KEO-GLASSTYPE |
| `rule_name` | Data | Tên hiển thị |
| `rule_type` | Select (reqd) | **THRESHOLD** / **LOOKUP** |
| `is_active` | Check (default 1) | |
| `threshold_rows` | Table→AL Dynamic Item Rule Threshold Row | Ngưỡng |
| `lookup_rows` | Table→AL Dynamic Item Rule Lookup Row | Tra cứu |

**Ví dụ THRESHOLD:** `RULE-NEP-GLASSTHICK`
- Input là `glass_thick` (độ dày kính)
- 0-10.38mm → `C3209-20` (nẹp nhỏ)
- 10.39-16mm → `C3210-20` (nẹp vừa)
- 16.01+mm → `C3211-20` (nẹp lớn)

**Ví dụ LOOKUP:** `RULE-KEO-GLASSTYPE`
- Input là `glass_type` (loại kính)
- LOWE → `KEO-TT-01` (keo trung tính)
- DON → `KEO-TT-02` (keo thường)

---

### 5.3 AL Dynamic Item Rule Threshold/Lookup Rows — Child tables

**Threshold Row:** `from_value`, `to_value`, `result_item`
**Lookup Row:** `key_field`, `result_item`

---

### 5.4 AL Dynamic Item Rule Version — Snapshot version của rule

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `rule` | Link→AL Dynamic Item Rule (reqd) | Rule cha |
| `version_name` | Data (reqd) | v1.0 |
| `valid_from` | Datetime (reqd) | Hiệu lực từ |
| `workflow_state` | Select | Draft / Approved / Published / Retired |
| `rule_snapshot_json` | JSON (reqd) | Snapshot toàn bộ rule |

---

### 5.5 AL Quantity Calc Method — Phương pháp tính số lượng

**File:** `al_formula_rules/doctype/al_quantity_calc_method/`
**Autoname:** `field:calc_pattern_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `calc_pattern_code` | Data (reqd, unique) | LENGTH_TO_WEIGHT, AREA, COUNT... |
| `calc_pattern_name` | Data | Tên hiển thị |
| `calc_fn` | Code | **Python lambda.** VD: `lambda w,h,tlr,**kw: (w/1000)*tlr` |
| `output_unit` | Data | Đơn vị đầu ra (kg, m2, m, cai) |

**4 pattern chuẩn:**

| Pattern | Lambda | Output | Dùng cho |
|---------|--------|--------|----------|
| LENGTH_TO_WEIGHT | `(w/1000)*tlr` | kg | NHOM (tính trọng lượng từ chiều dài) |
| AREA | `(w/1000)*(h/1000)` | m2 | KINH (tính diện tích) |
| LENGTH_ONLY | `w/1000` | m | VTP (tính mét dài) |
| COUNT | `1` | cai | PK (đếm số lượng) |

---

### 5.6 AL Rule Threshold/Lookup Rows — Child tables cho AL Calculation Rule

**Threshold Row:** `from_value` (Float), `to_value` (Float), `result_value` (Float)
**Lookup Row:** `key_field` (Data), `result_value` (Float)

---

## 6. MODULE: AL BUYING

### 6.1 AL Material Plan — Kế hoạch vật tư

**File:** `al_buying/doctype/al_material_plan/`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `plan_code` | Data (reqd) | MP-00001 (tự sinh) |
| `plan_date` | Date (reqd) | Ngày lập |
| `project` | Link→Project | Dự án |
| `sales_orders` | Table MultiSelect→Sales Order | Đơn hàng nguồn |
| `items` | Table→AL Material Plan Item (reqd) | Danh sách vật tư |

**Python:**
- `before_save()`: Tự sinh `plan_code = MP-.#####`
- `validate()`: `_calculate_shortfalls()` — tính stock_qty, shortfall_qty
- API `aggregate_requirements(sales_orders)`: Tổng hợp nhu cầu từ BOM Versions của nhiều Sales Order

---

### 6.2 AL Material Plan Item — Dòng vật tư cần mua

**istable:** Yes

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `item_code` | Link→Item | Mã vật tư |
| `required_qty` | Float | SL yêu cầu |
| `required_date` | Date | Ngày cần |
| `source_bom` | Data | BOM nguồn |
| `source_slug` | Data | Slug nguồn |
| `stock_qty` | Float | Tồn kho (tự động tính) |
| `ordered_qty` | Float | Đã đặt |
| `shortfall_qty` | Float | Thiếu (tự động tính) |
| `purchase_order` | Link→Purchase Order | Đơn hàng mua |
| `supplier` | Link→Supplier | Nhà cung cấp |

---

### 6.3 AL Supplier Price List — Bảng giá nhà cung cấp

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `supplier` | Link→Supplier (reqd) | NCC |
| `brand` | Link→Brand | Thương hiệu |
| `effective_date` | Date (reqd) | Ngày hiệu lực |
| `expiry_date` | Date | Ngày hết hạn |
| `currency_type` | Link→Currency (reqd) | Loại tiền |
| `exchange_rate_snapshot` | Float | Tỷ giá tại thời điểm |
| `status` | Select | Draft / Active / Expired |
| `items` | Table→AL Supplier Price List Item | |

---

### 6.4 AL Supplier Price List Item — Dòng giá NCC

**istable:** Yes

| Field | Kiểu |
|-------|------|
| `item_code` | Link→Item |
| `unit_price` | Currency |
| `fx_change_pct` | Float (read_only) |
| `base_price_change_pct` | Float (read_only) |

---

### 6.5 AL Cost Variance — Chênh lệch chi phí

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `project` | Link→Project | |
| `cost_bucket` | Link→AL Cost Bucket | |
| `period_from/to` | Date | Kỳ |
| `estimated_amount` | Currency | Dự toán |
| `actual_amount` | Currency | Thực tế (từ GL) |
| `variance_amount` | Currency | Chênh lệch |
| `variance_pct` | Float | % Chênh lệch |

---

## 7. MODULE: AL MANUFACTURING

### 7.1 AL Cutting Standard — Tiêu chuẩn cắt

**File:** `al_manufacturing/doctype/al_cutting_standard/`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `applies_to` | Select (reqd) | NHOM_PROFILE / KINH |
| `profile_code` | Data | Mã profile (cho NHOM) |
| `item_group` | Link→Item Group | Nhóm item (cho KINH) |
| `stock_bar_length_mm` | Float | Chiều dài thanh chuẩn (mm) |
| `saw_kerf_mm` | Float | Độ dày lưỡi cưa (mm) |
| `jumbo_sheet_size` | Data | Kích thước tấm kính chuẩn |
| `edge_trim_mm` | Float | Biên cắt kính (mm) |
| `min_offcut_reusable_mm` | Float | Đoạn dư tối thiểu tái sử dụng |
| `survey_tolerance_mm` | Float | Dung sai khảo sát (mm) — dùng trong AL Site Survey |

---

### 7.2 AL Cutting Plan Aluminum — Kế hoạch cắt nhôm

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `plan_code` | Data (reqd) | Mã kế hoạch |
| `bom_version` | Link→AL BOM Version (reqd) | Version BOM |
| `project` | Link→Project | |
| `sales_order` | Link→Sales Order | |
| `status` | Select | Draft / In Progress / Completed |
| `stock_bar_length_mm` | Float (reqd) | Chiều dài thanh |
| `saw_kerf_mm` | Float (reqd) | Độ dày cưa |
| `min_offcut_reusable_mm` | Float | Offcut tối thiểu |
| `total_bars_required` | Int | Tổng số thanh |
| `total_waste_mm` | Float | Tổng hao (mm) |
| `waste_pct` | Float | % Hao |
| `items` | Table→AL Cutting Plan Item (reqd) | Chi tiết cắt |

---

### 7.3 AL Cutting Plan Item — Dòng cắt nhôm

**istable:** Yes

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `bar_number` | Int | Số thanh |
| `slug` | Data | Slug BOM |
| `item_code` | Link→Item | |
| `cut_length_mm` | Float | Chiều dài cắt |
| `angle_start/end` | Float | Góc cắt |
| `position_from/to_mm` | Float | Vị trí trên thanh |
| `offcut_length_mm` | Float | Đoạn dư |
| `offcut_reusable` | Check | Tái sử dụng? |
| `offcut_serial_no` | Link→Serial No | Serial offcut |

---

### 7.4 AL Cutting Plan Glass — Kế hoạch cắt kính

Tương tự nhôm nhưng có `jumbo_sheet_size`, `edge_trim_mm`, `total_sheets_required`, `total_waste_m2`. Items là `AL Glass Cutting Item` với `sheet_number`, `cut_width_mm/height_mm`, `pos_x/y_mm`, `offcut_width/height_mm`.

---

### 7.5 AL Production Order Bridge — Cầu nối BOM → Work Order

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `al_bom_version` | Link→AL BOM Version (reqd) | Version BOM |
| `work_order` | Link→Work Order | Lệnh sản xuất ERPNext |
| `status` | Select | Draft / In Progress / Completed |
| `start/end_date` | Datetime | |
| `al_cutting_plan_aluminum` | Link→AL Cutting Plan Aluminum | KH cắt nhôm |
| `al_cutting_plan_glass` | Link→AL Cutting Plan Glass | KH cắt kính |

---

## 8. MODULE: AL CONSTRUCTION

### 8.1 AL Installation Team — Đội thi công

| Field | Kiểu |
|-------|------|
| `team_name` | Data (reqd) |
| `team_leader` | Link→Employee |
| `capacity_m2_per_day` | Float |
| `is_active` | Check (default 1) |
| `members` | Table→Employee |

---

### 8.2 AL Installation Order — Lệnh thi công

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `order_code` | Data (reqd) | Mã lệnh |
| `project` | Link→Project (reqd) | |
| `sales_order` | Link→Sales Order (reqd) | |
| `installation_team` | Link→AL Installation Team (reqd) | Đội thi công |
| `status` | Select | Draft / Scheduled / In Progress / Completed / On Hold |
| `planned_start/end_date` | Date (reqd) | Kế hoạch |
| `actual_start/end_date` | Date | Thực tế |
| `items` | Table→AL Installation Task (reqd) | Công việc |

**Python:** `before_save()` tự động sync status dựa trên progress của tasks.

---

### 8.3 AL Installation Task — Công việc thi công

**istable:** Yes

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `task_name` | Data | Tên việc |
| `location_code` | Data | Vị trí |
| `bom_slug` | Data | Slug BOM tương ứng |
| `planned_hours` | Float | Giờ kế hoạch |
| `actual_hours` | Float | Giờ thực tế |
| `status` | Select | Pending / In Progress / Completed |
| `assigned_to` | Link→Employee | Người phụ trách |

---

### 8.4 AL Installation Progress — Nhật ký tiến độ

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `installation_order` | Link→AL Installation Order (reqd) | |
| `report_date` | Date (reqd) | |
| `reported_by` | Link→Employee (reqd) | |
| `progress_pct` | Float | % Hoàn thành |
| `description/issues/next_steps` | Text | |
| `attachments` | Attach Image | |

**Python:** `after_insert()` tự động cập nhật status của Installation Order dựa trên progress_pct.

---

### 8.5 AL Site Survey — Khảo sát công trình

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `survey_code` | Data (reqd) | |
| `project` | Link→Project (reqd) | |
| `sales_order` | Link→Sales Order | |
| `survey_date` | Date (reqd) | |
| `surveyor` | Link→Employee | |
| `status` | Select | Draft / Completed / Approved |
| `items` | Table→AL Site Survey Item (reqd) | |

**Python:** `_calculate_deviations()` tự động tính sai lệch (actual - design) và kiểm tra within_tolerance dựa trên `AL Cutting Standard.survey_tolerance_mm`.

---

### 8.6 AL Site Survey Item — Dòng khảo sát

**istable:** Yes

| Field | Kiểu |
|-------|------|
| `location_code` | Data |
| `design_width/height_mm` | Float |
| `actual_width/height_mm` | Float |
| `width/height_deviation_mm` | Float (tự tính) |
| `within_tolerance` | Check (tự tính) |
| `action_required` | Select: NONE / RESIZE / REDESIGN / CHANGE_ORDER |
| `note` | Small Text |

---

### 8.7 AL Change Order — Phát sinh

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `change_code` | Data (reqd) | |
| `project` | Link→Project (reqd) | |
| `sales_order` | Link→Sales Order (reqd) | |
| `requested_by` | Link→User (reqd) | |
| `request_date` | Date (reqd) | |
| `change_type` | Select | SCOPE_CHANGE / DESIGN_CHANGE / MATERIAL_CHANGE / PRICE_ADJUSTMENT |
| `workflow_state` | Select | Draft / Pending / Approved / Rejected / Implemented |
| `description` | Text (reqd) | |
| `impact_scope` | Text | Phạm vi ảnh hưởng |
| `impact_cost` | Currency | Chi phí ảnh hưởng |
| `impact_schedule_days` | Int | Ngày ảnh hưởng |
| `customer_approval` | Check | Khách duyệt? |
| `internal_approval` | Check | Nội bộ duyệt? |
| `revised_quotation` | Link→Quotation | Báo giá điều chỉnh |
| `revised_sales_order` | Link→Sales Order | Đơn hàng điều chỉnh |

---

### 8.8 AL Handover Acceptance — Nghiệm thu bàn giao

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `handover_code` | Data (reqd) | |
| `project` | Link→Project (reqd) | |
| `installation_order` | Link→AL Installation Order (reqd) | |
| `handover_date` | Date (reqd) | |
| `customer_representative` | Data (reqd) | Đại diện KH |
| `company_representative` | Link→Employee (reqd) | Đại diện công ty |
| `acceptance_status` | Select | ACCEPTED / ACCEPTED_WITH_PUNCHLIST / REJECTED |
| `customer_signature` | Attach Image | Chữ ký KH |
| `warranty_start_date` | Date | Ngày bắt đầu bảo hành |
| `items` | Table→AL Punchlist Item | Danh sách tồn tại |

**Python:** Khi ACCEPTED → tự động set `warranty_start_date` và cập nhật `AL Installation Order.status = Completed`.

---

### 8.9 AL Punchlist Item — Tồn tại cần sửa

**istable:** Yes

| Field | Kiểu |
|-------|------|
| `item_description` | Data |
| `location` | Data |
| `severity` | Select: MINOR / MAJOR / CRITICAL |
| `corrective_action` | Text |
| `due_date` | Date |
| `status` | Select: OPEN / IN_PROGRESS / RESOLVED / VERIFIED |
| `resolved_by` | Link→Employee |
| `verified_by` | Link→Employee |

---

### 8.10 AL Installation Cost Actual — Chi phí thi công thực tế

| Field | Kiểu |
|-------|------|
| `installation_order` | Link→AL Installation Order (reqd) |
| `cost_date` | Date (reqd) |
| `cost_type` | Select: LABOR / MATERIAL / EQUIPMENT / TRANSPORT / OTHER |
| `amount` | Currency (reqd) |
| `paid_by` | Select: COMPANY / CUSTOMER / SUPPLIER |
| `description` | Data (reqd) |
| `reference_doctype` | Link→DocType |
| `reference_docname` | Dynamic Link |
| `receipt` | Attach Image |

---

## 9. MODULE: AL ACCOUNT

### 9.1 AL Project Financial Config — Cấu hình tài chính dự án

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `project` | Link→Project | |
| `overhead_pct` | Float | % Overhead |
| `contingency_pct` | Float | % Dự phòng |
| `payment_terms_template` | Link→Payment Terms Template | |
| `retention_pct` | Float | % Giữ lại |
| `retention_release_days` | Int | Ngày giải phóng retention |

---

### 9.2 AL Project Profitability Snapshot — Snapshot lợi nhuận dự án

| Field | Kiểu |
|-------|------|
| `project` | Link→Project (reqd) |
| `snapshot_date` | Date (reqd) |
| `total_revenue` | Currency |
| `total_estimated_cost` | Currency |
| `total_actual_cost` | Currency |
| `gross_profit` | Currency |
| `gross_margin_pct` | Float |
| `cost_breakdown_json` | JSON |
| `notes` | Text |

---

## 10. MODULE: AL QUALITY

### 10.1 AL Warranty Policy — Chính sách bảo hành

**File:** `al_quality/doctype/al_warranty_policy/`
**Autoname:** `field:policy_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `policy_code` | Data (reqd, unique) | Mã chính sách |
| `product_type` | Link→AL Product Type | Loại sản phẩm |
| `warranty_months` | Int | Số tháng bảo hành |
| `is_active` | Check (default 1) | |
| `coverage_scope` | Small Text | Phạm vi bảo hành |

---

## 11. MODULE: AL STOCK

### 11.1 AL Project Warehouse Map — Map kho theo dự án

| Field | Kiểu |
|-------|------|
| `project` | Link→Project |
| `warehouse` | Link→Warehouse |
| `is_temporary` | Check |
| `activation_date` | Date |
| `deactivation_date` | Date |

---

## 12. MODULE: AL AI INTELLIGENCE

### 12.1 AL Alert Config — Cấu hình cảnh báo

**File:** `al_ai_intelligence/doctype/al_alert_config/`
**Autoname:** `field:alert_code`

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `alert_code` | Data (reqd, unique) | |
| `alert_name` | Data (reqd) | |
| `alert_type` | Select (reqd) | BOM_VERSION_EXPIRED / COST_VARIANCE / SCHEDULE_DELAY / QC_FAILED / MATERIAL_SHORTAGE / WARRANTY_EXPIRING |
| `is_active` | Check (default 1) | |
| `cooldown_minutes` | Int | Thời gian giữa các lần alert |
| `trigger_condition` | Small Text | **Công thức FB** — điều kiện kích hoạt |
| `recipients` | Table MultiSelect→User | Người nhận |
| `notification_channel` | Select | EMAIL / SYSTEM / SMS / ALL |

**Tích hợp Formula Builder:** `formula_setup.js` gọi `patchField(frm, "trigger_condition", ...)` để render Monaco editor.

---

### 12.2 AL AI Interaction Log — Nhật ký tương tác AI

| Field | Kiểu |
|-------|------|
| `interaction_code` | Data (reqd) |
| `user` | Link→User (reqd) |
| `interaction_date` | Datetime (reqd) |
| `query_type` | Select: PRICE_INQUIRY / MATERIAL_SEARCH / BOM_COMPARE / SPEC_CHECK / COST_ESTIMATE |
| `ai_model` | Data |
| `response_time_ms` | Int |
| `query_text` | Text (reqd) |
| `ai_response` | Text |
| `user_feedback` | Select: HELPFUL / PARTIALLY / NOT_HELPFUL |
| `feedback_note` | Text |

---

### 12.3 AL AI Suggestion Log — Gợi ý từ AI

| Field | Kiểu |
|-------|------|
| `suggestion_code` | Data (reqd) |
| `created_by_ai` | Check (reqd) |
| `ai_model` | Data |
| `suggestion_type` | Select: PRICE_OPTIMIZATION / MATERIAL_ALTERNATIVE / DESIGN_IMPROVEMENT / RISK_ALERT / SCHEDULE_OPTIMIZATION |
| `status` | Select: PENDING / APPROVED / REJECTED / IMPLEMENTED |
| `confidence_score` | Float (0-1) |
| `target_doctype/docname` | Link / Data |
| `suggestion_content` | JSON (reqd) |
| `rationale` | Text |
| `approved_by/on` | Link→User / Datetime |
| `implementation_result` | Text |

---

## 13. CORE ERPNEXT CUSTOM FIELDS

`setup/custom_fields.py` thêm custom fields vào các doctype chuẩn của ERPNext:

| ERPNext Doctype | Custom Fields thêm vào |
|-----------------|----------------------|
| **Quotation** | `al_project_ref`, `al_profile_system`, `al_loss_reason` |
| **Quotation Item** | `al_bom`, `al_bom_version`, `al_bom_vars` (JSON), `al_config_snapshot`, `al_gia_ban`, `al_gia_vat`, `al_bom_result` |
| **Sales Order** | `al_project_id`, `al_installation_team`, `al_expected_start/end_date` |
| **Item** | `al_material_category`, `al_weight_per_m`, `al_glass_master`, `al_is_color_variable` |
| **Item Price** | `al_is_composite_price` (read_only) |
| **Batch** | `al_color`, `al_source_project`, `al_trace_stage`, `al_bin_location` |
| **Serial No** | `al_piece_length_mm`, `al_is_offcut`, `al_parent_cut_id` |
| **Work Order** | `al_production_order_bridge`, `al_project` |
| **Purchase Order** | `al_project`, `al_material_plan` |
| **Stock Entry** | `al_project`, `al_installation_order` |
| **Delivery Note** | `al_project`, `al_installation_order` |
| **Quality Inspection** | `al_production_order_bridge`, `al_inspection_stage`, `al_bom_slug`, `al_surface_check`, `al_dimension_check`, `al_color_match`, `al_glass_defect_check` |
| **Warranty Claim** | `al_installation_order`, `al_defect_category`, `al_warranty_policy`, `al_covered_by_warranty` |
| **Journal Entry** | `al_project`, `al_cost_bucket`, `al_change_order` |
| **Payment Entry** | `al_payment_stage`, `al_handover` |

---

## 14. ENGINE: BOMORCHESTRATOR

File: `engine/bom_orchestrator.py` (692 dòng)

### 7-Phase Pipeline

```
B0: Pin Version
    └── Đọc al_bom + al_bom_version từ Quotation Item
        Nếu không có version → dùng AL BOM.current_version

B1: Gather Inputs
    └── Merge: al_bom_vars (JSON từ dialog) + extra_vars
        + Formula Global Variables (float)
        + System variables resolve từ source_doctype.source_field
        + Fallback: AL Calculation Rule CONSTANT

B2: Prefetch Master Data (5 batch queries)
    ├── #1: Item weights
    ├── #2: Item Prices ★ COMPOSITE-KEY AWARE
    ├── #3: Glass Masters (glass_thick, glass_type)
    ├── #4: Material Categories (scrap_pct)
    └── #5: Dynamic Item Rules → resolve item_code

B3: Build Formulas
    └── Đọc formula_fieldnames từ Bom Set config
        Normalize items.xxx.field → xxx__field
        Tạo synthetic formulas: unit_qty, total_qty, line_total

B4: Calculate Bom Items
    └── FormulaEngine (formula_builder) với safe_funcs:
        lookup_calc_pattern, lookup_rule, roundup

B5: Aggregate Cost Buckets
    └── Gom line_total theo cost_bucket

B6: Calculate Cost Template
    └── FlexibleFormulaEngine (formula_builder)
        Parse bucket codes referenced → set default 0

B7: Save Results
    └── Tạo ConfigSnapshot (audit trail)
        Ghi al_gia_vat, al_gia_ban, al_bom_result vào Quotation Item
        ★ 1 COMMIT duy nhất
```

### Composite Price Matching

```python
def _match_composite_price(item_code, rows, dim_fieldnames):
    # dim_fieldnames = {"aluminum_color": "custom_pd_mau_sac", ...}
    # Với mỗi dòng Item Price:
    #   - Bỏ qua field không set
    #   - Field có set → phải khớp với self.inputs
    # Chọn dòng có NHIỀU field khớp nhất (best score)
    # Fallback: dòng "trần" không set field composite nào
```

---

## 15. API & FB HANDLERS

### API (`api/__init__.py`)

| Endpoint | Args | Returns |
|----------|------|---------|
| `calculate_bom` | `quotation_item_name` | `{buckets, cost_template, lines}` |
| `preview_cost_template` | `template_code, inputs_json` | `{line_code: {formula, result}}` |
| `get_slug_info` | `slug` | `{category, line_name, group_tag}` |
| `resolve_item_rule` | `rule_code, input_value` | `{item_code}` |
| `get_bom_structure` | `bom_code` | `{bom, bom_set, items}` |
| `get_formula_context` | `doctype, docname` | `{variables[...], references[...]}` |
| `get_variable_set_for_bom` | `bom_code` | `{variables[...]}` |

### FB Handlers (`fb_handlers.py`)

| Handler | Vai trò |
|---------|---------|
| `aluminum_price_composite` | Tra giá nhôm composite key (exact_match / multiplier_chain) |
| `glass_master_data` | Tra thông số kính (glass_thick, glass_type) |
| `cost_bucket_aggregate` | Gom line_total theo cost_bucket từ snapshot |

---

## 16. PHỤ LỤC: MA TRẬN QUAN HỆ DOCTYPE

### Dependency Graph

```
AL Variable Library ◄── AL Variable Set ──► AL Variable Set Item
        │                      │
        │              AL Bom Set ◄── AL Slug Library
        │                 │  │
        │                 │  └──► AL Bom Item (child)
        │                 │          │
        │                 │          ├──► AL Material Category
        │                 │          ├──► AL Quantity Calc Method
        │                 │          ├──► AL Dynamic Item Rule
        │                 │          ├──► AL Glass Master ──► AL Glass Type
        │                 │          └──► AL Cost Bucket
        │                 │
        │          AL BOM ─┴──► AL BOM Version ──► AL BOM Change Log
        │           │  │                         ──► ConfigSnapshot
        │           │  └──► AL Cost Template ──► AL Cost Template Item
        │           │
        │      Quotation Item (.al_bom, .al_bom_version, .al_bom_vars)
        │
AL Profile System ──► System Variables (OFFSET_FRAME...)
AL Product Type ────► System Variables (NC_SX_PCT, PROFIT_MARGIN...)
AL Pricing Dimension ◄── AL Variable Dimension Mapping
        │                       │
        └──► Item Price (custom_pd_* fields)

                            ┌──► AL Installation Order ──► AL Installation Task
Quotation → Sales Order ───┤
                            ├──► AL Site Survey ──► AL Site Survey Item
                            ├──► AL Change Order
                            └──► AL Handover Acceptance ──► AL Punchlist Item

AL Material Plan ──► Purchase Order
AL Cutting Plan Al/Glass ──► AL Production Order Bridge ──► Work Order
AL Supplier Price List ──► AL Supplier Price List Item
AL Cost Variance
AL Project Financial Config
AL Project Profitability Snapshot
AL Project Warehouse Map
AL Warranty Policy ──► Warranty Claim
AL Alert Config
```

### Bảng tổng số doctype theo module

| Module | Doctypes | Child Tables |
|--------|:--------:|:------------:|
| AL Master Data | 10 | 1 (Variable Set Item) |
| AL Bom Engine | 7 | 5 (Bom Item, Acc Item, Cost Templ Item, Change Log, ConfigSnapshot) |
| AL Formula Rules | 4 | 4 (Threshold/Lookup × 2 rules) |
| AL Buying | 3 | 2 (Mat Plan Item, Sup Price Item) |
| AL Manufacturing | 4 | 2 (Cut Plan Item, Glass Cut Item) |
| AL Construction | 8 | 2 (Install Task, Punchlist, Survey Item) |
| AL Account | 2 | 0 |
| AL Quality | 1 | 0 |
| AL Stock | 1 | 0 |
| AL AI Intelligence | 3 | 0 |
| **TOTAL** | **43** | **16** |

---

*Cập nhật: 2026-08-06 | AlumGlass v28.8 | 57 doctypes | 11 modules | Data-driven, zero hardcode*
