# CẤU TRÚC MODULE & DOCTYPE — ALUMGLASS ERP

> **Tài liệu gốc tham chiếu:** `v28.md`, `KE_HOACH_TRIEN_KHAI_CHI_TIET.md`
> **Phiên bản:** v1.0 — 2026-07-30
> **Nguyên tắc:** Module core ERPNext khi thêm tính năng sẽ có tiền tố `AL` tương ứng (VD: AL Selling, AL Buying, AL Stock...). DocType mới 100% đặt trong module AlumGlass tương ứng.

---

## MỤC LỤC

1. [Sơ đồ tổng thể các Module](#1-sơ-đồ-tổng-thể-các-module)
2. [Module 1: AL Master Data](#2-module-1-al-master-data)
3. [Module 2: AL BOM Engine](#3-module-2-al-bom-engine)
4. [Module 3: AL Formula & Rules](#4-module-3-al-formula--rules)
5. [Module 4: AL Selling](#5-module-4-al-selling)
6. [Module 5: AL Buying](#6-module-5-al-buying)
7. [Module 6: AL Stock](#6-module-6-al-stock)
8. [Module 7: AL Manufacturing](#7-module-7-al-manufacturing)
9. [Module 8: AL Construction](#8-module-8-al-construction)
10. [Module 9: AL Account](#9-module-9-al-account)
11. [Module 10: AL Quality](#10-module-10-al-quality)
12. [Module 11: AL AI & Intelligence](#11-module-11-al-ai--intelligence)
13. [Module 12: Formula Builder (FB) — Tích hợp](#12-module-12-formula-builder-fb--tích-hợp)
14. [Bảng tổng hợp DocType theo Module](#14-bảng-tổng-hợp-doctype-theo-module)

---

## 1. SƠ ĐỒ TỔNG THỂ CÁC MODULE

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ALUMGLASS ERP SYSTEM                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ AL Master    │  │ AL BOM       │  │ AL Formula & Rules       │   │
│  │ Data         │  │ Engine       │  │ (Rule Engine)            │   │
│  │ (Nền tảng)   │  │ (Tính giá)   │  │                          │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘   │
│         │                 │                       │                 │
│         ▼                 ▼                       ▼                 │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              ERPNext Core (Tái sử dụng + Custom Fields)       │  │
│  │                                                               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │  │AL Selling│ │AL Buying │ │ AL Stock │ │ AL Manufacturing │  │  │
│  │  │(Sales)   │ │(Purchase)│ │(Inventory│ │ (Production)     │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │  │
│  │                                                               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │  │AL Quality│ │  AL HR   │ │AL Account│ │ AL Construction  │  │  │
│  │  │(QC)      │ │(HR)      │ │(Accounts)│ │ (Site/Install)   │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │  │
│  │                                                               │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │              AL AI & Intelligence                        │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │          Formula Builder v31 (Engine Nền Tảng - Bất Biến)     │  │
│  │  FlexibleFormulaEngine | BatchBindingResolver | Snapshot      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.1 Danh sách Module

| # | Module | Tên Frappe | Loại | Mô tả |
|---|---|---|---|---|
| 1 | **AL Master Data** | `al_master_data` | New | Danh mục nền tảng: Slug, Profile System, Glass, Color, Product Type, Material Category, Pricing Dimension |
| 2 | **AL BOM Engine** | `al_bom_engine` | New | Cấu trúc BOM: Bom Item, Bom Set, BOM, BOM Version, Cost Bucket, Cost Template, ConfigSnapshot |
| 3 | **AL Formula & Rules** | `al_formula_rules` | New | Rule engine: Calculation Rule, Dynamic Item Rule, Quantity Calc Method |
| 4 | **AL Selling** | `al_selling` | Custom | Bán hàng: Quotation, Sales Order — Custom Fields + Client Script + API |
| 5 | **AL Buying** | `al_buying` | Custom | Mua hàng: Supplier Price List, Material Plan — Custom Fields |
| 6 | **AL Stock** | `al_stock` | Custom | Kho: Batch (màu), Serial No (offcut), Warehouse Map — Custom Fields |
| 7 | **AL Manufacturing** | `al_manufacturing` | Custom | Sản xuất: Cutting Plan, Production Order Bridge |
| 8 | **AL Construction** | `al_construction` | New | Thi công: Site Survey, Installation Order, Installation Progress, Installation Cost |
| 9 | **AL Account** | `al_account` | Custom | Kế toán dự án: Custom Fields trên Accounts core (Payment Schedule, Journal Entry, GL Entry, Accounting Dimension) + Change Order, P&L Snapshot, Handover Acceptance, Project Financial Config |
| 10 | **AL Quality** | `al_quality` | Custom | Chất lượng: Quality Inspection — Custom Fields, Warranty Claim, Warranty Policy |
| 11 | **AL AI & Intelligence** | `al_ai` | New | AI: Suggestion Log, Interaction Log, Alert Config |
| 12 | **Formula Builder** | `formula_builder` | External | Engine nền tảng: Formula Global Variable, Formula Set, Formula Snapshot, Settings |

---

## 2. MODULE 1: AL MASTER DATA

**Tên Frappe:** `al_master_data`
**Vai trò:** Quản lý toàn bộ danh mục nền tảng của hệ thống nhôm kính. Đây là module nền tảng, tất cả module khác phụ thuộc vào.

### 2.1 AL Slug Library
**Mô tả:** Hệ thống slug tập trung — định danh duy nhất cho mỗi vai trò vật tư trong BOM. Dùng cho cross-row reference `items.<slug>.<field>`.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `slug` | Data | Y | Y | Mã slug: `khung_ngang_tren`, `kinh_tren`, `nep_kinh_tren` |
| `label` | Data | Y | | Tên hiển thị: "Khung ngang trên" |
| `category` | Link → AL Material Category | Y | | Loại vật tư (NHOM, KINH, VTP, PK, THEP, INOX...) |
| `group_tag` | Data | | | Nhóm: KHUNG, CANH, NEP, KINH, GIOANG, VIT, PK |
| `description` | Small Text | | | Mô tả chi tiết, hướng dẫn sử dụng |

**Dữ liệu mẫu (17 slug):**

| slug | label | category | group_tag |
|---|---|---|---|
| khung_ngang_tren | Khung ngang trên | NHOM | KHUNG |
| khung_ngang_duoi | Khung ngang dưới | NHOM | KHUNG |
| khung_dung | Khung đứng | NHOM | KHUNG |
| do_ngang | Đố ngang | NHOM | KHUNG |
| canh_ngang | Cánh ngang | NHOM | CANH |
| canh_dung | Cánh đứng | NHOM | CANH |
| kinh_tren | Kính cố định trên | KINH | GLASS |
| kinh_duoi | Kính cánh dưới | KINH | GLASS |
| nep_kinh_tren | Nẹp kính trên | NHOM | NEP |
| nep_kinh_duoi | Nẹp kính dưới | NHOM | NEP |
| keo_tren | Keo dán kính trên | VTP | KEO |
| keo_duoi | Keo dán kính dưới | VTP | KEO |
| gioang | Gioăng | VTP | GIOANG |
| vit | Vít | VTP | VIT |
| tay_nam | Tay nắm | PK | PK |
| khoa | Khóa | PK | PK |
| ban_le | Bản lề | PK | PK |

---

### 2.2 AL Material Category
**Mô tả:** Danh mục loại vật tư động — thay thế Select field cứng `line_type`. Người dùng tự tạo loại vật tư mới không cần code.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `category_code` | Data | Y | Y | Mã loại: NHOM, THEP, INOX, KINH, VTP, PK, NHUA, GO, ALU_COMPOSITE... |
| `category_name` | Data | Y | | Tên hiển thị: "Aluminum", "Steel", "Glass"... |
| `default_calc_pattern` | Link → AL Quantity Calc Method | Y | | Pattern mặc định: LENGTH_TO_WEIGHT, AREA... |
| `default_cost_bucket` | Link → AL Cost Bucket | | | Bucket mặc định cho vật tư loại này |
| `requires_item_code` | Check | | | Bắt buộc chọn Item? (default=1) |
| `requires_price_base_item` | Check | | | Bắt buộc có price_base_item? |
| `requires_glass_master` | Check | | | Bắt buộc có AL Glass Master? |
| `requires_ctx_inject_prefix` | Check | | | Bắt buộc có ctx_inject_prefix? |
| `has_weight` | Check | | | Có trọng lượng riêng (kg/m)? |
| `has_dimensions` | Check | | | Có width/height? (default=1) |
| `allowed_calc_patterns` | Table MultiSelect → AL Quantity Calc Method | | | Các pattern được phép |
| `is_active` | Check | | | (default=1) |

**Dữ liệu mẫu:**

| category_code | category_name | default_calc_pattern | default_cost_bucket | requires_price_base_item | requires_glass_master | has_weight | has_dimensions |
|---|---|---|---|---|---|---|---|
| NHOM | Nhôm | LENGTH_TO_WEIGHT | VL_NHOM | 1 | 0 | 1 | 1 |
| THEP | Thép | LENGTH_TO_WEIGHT | VL_THEP | 1 | 0 | 1 | 1 |
| INOX | Inox | LENGTH_TO_WEIGHT | VL_INOX | 1 | 0 | 1 | 1 |
| KINH | Kính | AREA | VL_KINH | 0 | 1 | 0 | 1 |
| VTP | Vật tư phụ | LENGTH_ONLY | VL_VTP | 0 | 0 | 0 | 1 |
| PK | Phụ kiện | COUNT | VL_PK | 0 | 0 | 0 | 0 |
| NHUA | Nhựa | LENGTH_TO_WEIGHT | VL_NHUA | 1 | 0 | 1 | 1 |
| ALU_COMPOSITE | Alu Composite | AREA | VL_ALU | 0 | 0 | 0 | 1 |
| GO | Gỗ | AREA | VL_GO | 0 | 0 | 0 | 1 |

---

### 2.3 AL Profile System
**Mô tả:** Hệ profile (Xingfa 55, Xingfa 60, Alumil M9560...) — mỗi hệ có bộ offset hình học riêng. Thêm hệ mới = 1 record, 0 dòng code.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `system_code` | Data | Y | Y | `XINGFA_55`, `XINGFA_60`, `ALUMIL_M9560` |
| `system_name` | Data | Y | | "Xingfa hệ 55", "Alumil M9560" |
| `brand` | Link → Brand | Y | | Thương hiệu: XINGFA, ALUMIL |
| `offset_frame` | Float | Y | | Khe hở khung-cánh (mm) — OFFSET_FRAME |
| `offset_glass` | Float | Y | | Khe hở cánh-kính (mm) — OFFSET_GLASS |
| `offset_fixed` | Float | Y | | Khe hở khung-kính cố định (mm) — OFFSET_FIXED |
| `offset_crossbar` | Float | Y | | Khe hở đố ngang (mm) — OFFSET_DO_NGANG |
| `is_active` | Check | | | (default=1) |

**Dữ liệu mẫu:**

| system_code | brand | offset_frame | offset_glass | offset_fixed | offset_crossbar |
|---|---|---|---|---|---|
| XINGFA_55 | XINGFA | 48 | 90 | 50 | 48 |
| XINGFA_60 | XINGFA | 52 | 94 | 54 | 52 |
| ALUMIL_M9560 | ALUMIL | 44 | 86 | 46 | 44 |

---

### 2.4 AL Color Standard
**Mô tả:** Danh mục màu chuẩn — dùng cho composite key tra giá Item Price và quản lý Batch-màu.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `color_code` | Data | Y | Y | Mã màu: RAL9016, VANGO-OC-CHO-01 |
| `color_name` | Data | | | Tên hiển thị: "Trắng RAL 9016" |
| `applies_to` | Link → Item Group | | | Áp dụng cho nhóm: NHOM_PROFILE, ACCESSORY |
| `is_standard_stock` | Check | | | Màu tồn kho đệm? (default=0) |
| `default_safety_stock_qty` | Float | | | Tồn kho an toàn (chỉ khi is_standard_stock=1) |
| `surcharge_rule` | Link → AL Calculation Rule | | | Rule LOOKUP phụ thu giá theo màu |

---

### 2.5 AL Glass Type
**Mô tả:** Phân loại kính — DON, CUONG_LUC, HOP, LOWE, LAM.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `type_code` | Data | Y | Y | DON, CUONG_LUC, HOP, LOWE, LAM |
| `type_name` | Data | | | "Kính dán", "Kính cường lực"... |

---

### 2.6 AL Glass Master
**Mô tả:** Thông số kỹ thuật kính — nguồn `glass_thick`, `glass_type` cho Bom Item dòng KINH.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `glass_code` | Data | Y | Y | KINH-LOWE-24, KINH-CL-8 |
| `glass_name` | Data | | | Tên hiển thị |
| `total_thick_mm` | Decimal(5,2) | Y | | Độ dày tổng (mm) — Decimal tránh lỗi rounding |
| `glass_type` | Link → AL Glass Type | Y | | DON, CUONG_LUC, HOP, LOWE, LAM |
| `u_value` | Float | | | Thông số nhiệt (nâng cao) |
| `shgc` | Float | | | Hệ số hấp thụ nhiệt (nâng cao) |
| `vlt` | Float | | | Độ truyền sáng (nâng cao) |

---

### 2.7 AL Product Type
**Mô tả:** Loại sản phẩm (cửa đi, cửa sổ, vách kính...) — nguồn NC_SX_PCT, NC_LD_PCT, PROFIT_MARGIN được resolve scoped qua doctype_query.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `type_code` | Data | Y | Y | DOOR, WINDOW, CURTAIN_WALL |
| `type_name` | Data | | | "Cửa đi", "Cửa sổ", "Vách kính" |
| `nc_pct` | Float | | | % Nhân công sản xuất (default=0.12) |
| `nc_ld_rate` | Float | | | % Nhân công lắp đặt (default=0.12) |
| `profit_margin` | Float | | | % Lợi nhuận kỳ vọng (default=0.16) |
| `default_warranty_policy` | Link → AL Warranty Policy | | | Chính sách bảo hành mặc định |

---

### 2.8 AL Pricing Dimension
**Mô tả:** Đặc tính giá động (tương tự Accounting Dimension) — tự động sinh custom field trên Item Price. Thêm đặc tính mới = 1 record.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `dimension_code` | Data | Y | Y | MAU_SAC, XUAT_XU, DO_DAY, BE_MAT, DO_BONG... |
| `dimension_name` | Data | Y | | "Màu sắc", "Xuất xứ", "Độ dày"... |
| `dimension_type` | Select | Y | | Link / Select / Data / Float / Int |
| `link_doctype` | Link → DocType | | | Nếu dimension_type=Link |
| `select_options` | Small Text | | | Nếu dimension_type=Select: "IMPORT\nDOMESTIC\n..." |
| `custom_fieldname` | Data (read-only) | | | Tự sinh: `custom_pd_{dimension_code}` |
| `applies_to_category` | Table MultiSelect → AL Material Category | | | Áp dụng cho loại vật tư nào |
| `is_required_for_price` | Check | | | Bắt buộc khi tạo Item Price? |
| `is_active` | Check | | | (default=1) |
| `sort_order` | Int | | | Thứ tự hiển thị trên form |

**Dữ liệu mẫu:**

| dimension_code | dimension_name | dimension_type | link_doctype / select_options |
|---|---|---|---|
| MAU_SAC | Màu sắc | Link | AL Color Standard |
| XUAT_XU | Xuất xứ | Select | IMPORT\nDOMESTIC |
| DO_DAY | Độ dày sơn | Int | — |
| BE_MAT | Bề mặt | Select | POWDER_COATED\nANODIZED\nWOOD_GRAIN |
| DO_BONG | Độ bóng | Select | BONG\nMO\nXUOC |

---

### 2.9 AL Variable Dimension Mapping
**Mô tả:** Cầu nối Variable Set ↔ Pricing Dimension.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `variable_name` | Data | Y | Tên biến trong Variable Set: `aluminum_color`, `aluminum_origin` |
| `pricing_dimension` | Link → AL Pricing Dimension | Y | Map tới dimension |
| `material_category` | Link → AL Material Category | | Áp dụng cho category nào (trống = tất cả) |

---

### 2.10 AL Accessory Set
**Mô tả:** Bộ phụ kiện (optional, có thể dùng AL Bom Item với category=PK thay thế).

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `set_code` | Data | Y | Y | Mã bộ PK: PK-CDMQ-2C |
| `set_name` | Data | Y | | Tên bộ phụ kiện |
| `product_type` | Link → AL Product Type | | | Loại sản phẩm |
| `al_pk_lines` | Table → AL Accessory Line | | | Danh sách phụ kiện |

**AL Accessory Line (Child Table):**

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `slug` | Data | Y | Định danh dòng |
| `item_code` | Link → Item | Y | Item phụ kiện |
| `qty` | Float | Y | Số lượng |
| `unit_price` | Currency | | Đơn giá |

---

### 2.11 AL Cutting Standard
**Mô tả:** Quy cách cắt chuẩn cho nhôm và kính.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `applies_to` | Select | Y | NHOM_PROFILE / KINH |
| `profile_code` | Data | | Mã profile (cho NHOM) |
| `item_group` | Link → Item Group | | Nhóm item (cho KINH) |
| `stock_bar_length_mm` | Float | | Chiều dài phôi chuẩn — 6000mm (cho NHOM) |
| `saw_kerf_mm` | Float | | Hao do lưỡi cưa (cho NHOM) |
| `jumbo_sheet_size` | Data | | VD: 3210x2250 (cho KINH) |
| `edge_trim_mm` | Float | | Trừ hao mép (cho KINH) |
| `min_offcut_reusable_mm` | Float | | Ngưỡng phế liệu tái dùng |
| `survey_tolerance_mm` | Float | | Ngưỡng sai lệch tối đa Site Survey |

---

### 2.12 AL Installation Team
**Mô tả:** Đội thi công.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `team_name` | Data | Y | Tên đội |
| `team_leader` | Link → Employee | | Đội trưởng |
| `members` | Table → Employee | | Danh sách thành viên |
| `capacity_m2_per_day` | Float | | Năng suất (m2/ngày) |
| `is_active` | Check | | (default=1) |

---

### 2.13 AL Warranty Policy
**Mô tả:** Chính sách bảo hành theo loại sản phẩm.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `policy_code` | Data | Y | Y | Mã chính sách |
| `product_type` | Link → AL Product Type | | | Loại sản phẩm |
| `warranty_months` | Int | | | Thời gian bảo hành (tháng) |
| `coverage_scope` | Small Text | | | Phạm vi bảo hành |

---

### 2.14 AL Supplier Price List
**Mô tả:** Bảng giá nhà cung cấp.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `supplier` | Link → Supplier | Y | Nhà cung cấp |
| `brand` | Link → Brand | | Thương hiệu |
| `effective_date` | Date | Y | Ngày hiệu lực |
| `expiry_date` | Date | | Ngày hết hạn |
| `currency` | Link → Currency | Y | Nguyên tệ |
| `exchange_rate_snapshot` | Float | | Tỷ giá tham khảo |
| `status` | Select | | Draft / Active / Expired |
| `al_price_lines` | Table → AL Supplier Price List Line | | Dòng bảng giá |

**AL Supplier Price List Line (Child Table):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_code` | Link → Item | Item |
| `unit_price` | Currency | Đơn giá nguyên tệ |
| `fx_change_pct` | Float (read-only) | Biến động tỷ giá |
| `base_price_change_pct` | Float (read-only) | Biến động giá gốc NCC |

---

## 3. MODULE 2: AL BOM ENGINE

**Tên Frappe:** `al_bom_engine`
**Vai trò:** Trung tâm tính giá — cấu trúc BOM, Cost Bucket, Cost Template, Snapshot.

### 3.1 AL Bom Item
**Mô tả:** Dòng vật tư thống nhất cho MỌI loại (Nhôm, Kính, Thép, Nhựa, Phụ kiện...). Đây là DocType trung tâm của toàn hệ thống.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `parent` | Data (system) | Y | Link tới AL Bom Set |
| `parentfield` | Data (system) | Y | `al_bom_items` |
| `parenttype` | Data (system) | Y | AL Bom Set |
| `idx` | Int (system) | Y | Thứ tự dòng |
| `slug` | Link → AL Slug Library | Y | Định danh duy nhất, lấy từ Slug Library |
| `category` | Link → AL Material Category (read-only) | Y | Tự động từ AL Slug Library |
| `line_name` | Data | | Tên hiển thị (tự động từ AL Slug Library.label) |
| `is_active` | Check | | (default=1) |
| `show_condition` | Small Text | | Điều kiện hiển thị dòng (FB formula syntax) |
| `cost_bucket` | Link → AL Cost Bucket | | LEAF bucket chứa chi phí dòng này |
| `item_selection_mode` | Select | Y | Fixed / Rule / Formula |
| `item_code` | Link → Item | | Item ERPNext cụ thể (bắt buộc nếu mode=Fixed) |
| `item_rule` | Link → AL Dynamic Item Rule | | Rule chọn item động (nếu mode=Rule) |
| `item_fallback` | Link → Item | | Fallback nếu Rule không tra được |
| `item_condition_formula` | Small Text | | Công thức chọn Item (nếu mode=Formula) |
| `allow_sales_override` | Check | | Cho phép Sales thay đổi Item? |
| `override_item_group` | Link → Item Group | | Giới hạn override trong nhóm này |
| `width` | Small Text | | Công thức tính width (FB syntax): `W_mm - 2*$OFFSET_FIXED` |
| `height` | Small Text | | Công thức tính height (FB syntax): `TransomHeight_mm - $OFFSET_FIXED` |
| `qty` | Small Text | Y | Công thức tính số lượng (FB syntax): `2*n_panel` |
| `calc_pattern` | Link → AL Quantity Calc Method | | LENGTH_TO_WEIGHT / AREA / LENGTH_ONLY / COUNT |
| `price_type` | Select | | Item Price / Rule / Fixed |
| `price_base_item` | Link → Item | | Item đại diện để tra giá composite key |
| `price_rule` | Link → AL Calculation Rule | | Rule tính giá (nếu price_type=Rule) |
| `price_list` | Link → Price List | | Bảng giá (nếu price_type=Item Price) |
| `fixed_price` | Currency | | Giá cố định (nếu price_type=Fixed) |
| `rule_input_expr` | Small Text | | Biểu thức input cho Dynamic Item Rule |
| `formula_set` | Link → Formula Set (FB) | | Formula Set áp dụng (mặc định BOM_LINE) |

### 3.1A AL Bom Item — Chi tiết field theo Material Category

**Category có `has_weight=1` + `requires_price_base_item=1` (NHOM, THEP, INOX, NHUA...):**

Ngoài các field chung, các category này có thêm:

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_code` | Link → Item | Profile cụ thể: XF55-KB-20 |
| `calc_pattern` | Link → AL Quantity Calc Method | Mặc định LENGTH_TO_WEIGHT |
| `price_base_item` | Link → Item | Item đại diện: NHOM-XINGFA (tra giá composite key) |
| `price_type` | Select | Item Price / Rule / Fixed |
| `price_rule` | Link → AL Calculation Rule | Nếu price_type=Rule |
| `fixed_price` | Currency | Nếu price_type=Fixed |

**Category có `requires_glass_master=1` (KINH):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_code` | Link → Item | KINH-LOWE-24 |
| `calc_pattern` | Link → AL Quantity Calc Method | Mặc định AREA |
| `default_glass_master` | Link → AL Glass Master | Nguồn total_thick_mm và glass_type |
| `ctx_inject_prefix` | Data | Prefix để inject `glass_thick_{prefix}`, `glass_type_{prefix}` |
| `panel_count_formula` | Small Text | Số tấm khi vách nhiều ô (FB formula) |
| `panel_glass_override_allowed` | Check | Cho phép Sales chọn kính riêng? |
| `qty_per_panel_formula` | Small Text | Mặc định "1" |
| `price_type` | Select | Item Price / Fixed |
| `price_list` | Link → Price List | Bảng giá kính |
| `fixed_price` | Currency | |
| `cut_fee_pct` | Float | Phí cắt kính (%) — default=0 |

**Category có `has_dimensions=1` nhưng `has_weight=0` (VTP):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_code` | Link → Item | KEO-TT-01, GIO-EPDM-55... |
| `calc_pattern` | Link → AL Quantity Calc Method | LENGTH_ONLY hoặc COUNT |
| `price_type` | Select | Item Price / Fixed |
| `price_list` | Link → Price List | |
| `fixed_price` | Currency | |

**Category có `has_dimensions=0` (PK thuần đếm):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_code` | Link → Item | KL-MZS20, KL-KHOA-01... |
| `calc_pattern` | Link → AL Quantity Calc Method | COUNT |
| `price_type` | Select | Item Price / Fixed |
| `price_list` | Link → Price List | |
| `fixed_price` | Currency | |
| `allow_substitute` | Check | Cho phép thay thế phụ kiện? |
| `substitute_item_group` | Link → Item Group | Giới hạn substitute trong nhóm này |

**Chung cho Rule (mọi category):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_rule` | Link → AL Dynamic Item Rule | Rule áp dụng |
| `rule_input_expr` | Small Text | Biểu thức lấy input: `items.kinh_tren.glass_thick` |
| `item_fallback` | Link → Item | Item fallback nếu Rule không tra được |

**Chung cho Sales Override (mọi category):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `allow_sales_override` | Check | Cho phép Sales thay đổi Item trên Quotation? |
| `override_item_group` | Link → Item Group | Giới hạn override trong nhóm này |

---

### 3.2 AL Bom Set
**Mô tả:** Tập hợp AL Bom Item — định nghĩa cấu trúc sản phẩm.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `set_code` | Data | Y | Y | Mã Bom Set: BS-CDMQ-2C |
| `set_name` | Data | Y | | Tên: "Cửa đi 2 cánh mở quay + ô kính cố định" |
| `product_type` | Link → AL Product Type | | | Loại sản phẩm (để resolve NC_SX_PCT, PROFIT_MARGIN) |
| `brand` | Link → Brand | | | Thương hiệu: XINGFA, ALUMIL |
| `profile_system` | Link → AL Profile System | | | Hệ profile (XINGFA_55, ALUMIL_M9560...) — quyết định bộ offset |
| `version` | Data | | | 1.0 |
| `al_bom_items` | Table → AL Bom Item | Y | | Danh sách Bom Item |

---

### 3.3 AL BOM
**Mô tả:** BOM — liên kết Bom Set + Cost Template.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `bom_code` | Data | Y | Y | Mã BOM: BOM-CDMQ-2C |
| `bom_name` | Data | | | Tên BOM |
| `product_type` | Link → AL Product Type | | | Loại sản phẩm |
| `brand` | Link → Brand | | | Thương hiệu |
| `representative_item` | Link → Item | Y | | Item phi tồn kho đại diện |
| `bom_set` | Link → AL Bom Set | Y | | Bom Set chứa Bom Items |
| `pk_set` | Link → AL Accessory Set | | | Bộ phụ kiện (optional) |
| `default_cost_template` | Link → AL Cost Template | Y | | Cost Template mặc định |
| `is_active` | Check | | | (default=1) |
| `current_version` | Link → AL BOM Version | | | Version đang Published |
| `requires_approval_for_new_version` | Check | | | Cần duyệt khi tạo version mới? |
| `default_installation_team` | Link → AL Installation Team | | | Đội thi công mặc định |

---

### 3.4 AL BOM Version
**Mô tả:** Snapshot bất biến của BOM — quản lý qua Workflow core.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `bom` | Link → AL BOM | Y | BOM cha |
| `version_name` | Data | Y | Tên version: "v1.0", "v2.0" |
| `valid_from` | Datetime | Y | Ngày hiệu lực |
| `valid_to` | Datetime | | Ngày hết hiệu lực |
| `workflow_state` | Data | | Draft / Pending Approval / Approved / Published / Retired |
| `bom_set_snapshot` | JSON | | Snapshot của AL Bom Set tại thời điểm tạo version |
| `cost_template_snapshot` | JSON | | Snapshot của AL Cost Template |
| `change_log` | Table → AL BOM Change Log | | Nhật ký thay đổi |

---

### 3.5 AL BOM Change Log
**Mô tả:** Nhật ký thay đổi BOM Version (Child Table).

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `changed_by` | Link → User | Người thay đổi |
| `changed_on` | Datetime | Thời điểm |
| `change_type` | Select | Added / Modified / Removed |
| `field_name` | Data | Tên field thay đổi |
| `old_value` | Small Text | Giá trị cũ |
| `new_value` | Small Text | Giá trị mới |
| `reason` | Small Text | Lý do thay đổi |

---

### 3.6 AL Cost Bucket
**Mô tả:** Tài khoản chi phí LEAF/AGGREGATE — mỗi bucket định nghĩa nguồn dữ liệu và cách aggregate.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `bucket_code` | Data | Y | Y | VL_NHOM, VL_KINH, TONG_VL, NC_SX, GIA_VAT... |
| `bucket_name` | Data | Y | | Tên hiển thị |
| `bucket_role` | Select | Y | | LEAF / AGGREGATE |
| `parent_bucket` | Link → AL Cost Bucket | | | Bucket cha (cho AGGREGATE) |
| `source_type` | Select | Y | | aggregate_from_items / formula / doctype_query / custom_function / constant / pipeline / conditional / fallback_chain |
| `source_config` | JSON | | | Cấu hình data source (filters, fieldname, transform, steps, branches, chain...) |
| `depends_on` | JSON | | | Các biến phụ thuộc: `["aluminum_color", "aluminum_origin"]` |
| `batch_group` | Data | | | Nhóm batch query (cùng group → gom 1 query) |
| `report_group` | Data | | | A. Vật liệu, B. Nhân công, C. Overhead, D. Tổng hợp |
| `default_expense_account` | Link → Account | | | Cầu nối với GL Entry |
| `sort_order` | Int | | | Thứ tự hiển thị |

**Dữ liệu mẫu (14 bucket):**

| bucket_code | bucket_role | parent_bucket | source_type | report_group |
|---|---|---|---|---|
| VL_NHOM | LEAF | TONG_VL | aggregate_from_items | A. Vật liệu |
| VL_KINH | LEAF | TONG_VL | aggregate_from_items | A. Vật liệu |
| VL_VTP | LEAF | TONG_VL | aggregate_from_items | A. Vật liệu |
| VL_PK | LEAF | TONG_VL | aggregate_from_items | A. Vật liệu |
| TONG_VL | AGGREGATE | — | formula | A. Vật liệu |
| NC_SX | LEAF | TONG_NC | doctype_query | B. Nhân công |
| NC_LD | LEAF | TONG_NC | doctype_query | B. Nhân công |
| TONG_NC | AGGREGATE | — | formula | B. Nhân công |
| OH_VC | LEAF | TONG_OH | formula | C. Overhead |
| OH_QLY | LEAF | TONG_OH | formula | C. Overhead |
| TONG_OH | AGGREGATE | — | formula | C. Overhead |
| GIA_THANH | AGGREGATE | — | formula | D. Tổng hợp |
| GIA_BAN | AGGREGATE | — | formula | D. Tổng hợp |
| GIA_VAT | AGGREGATE | — | formula | D. Tổng hợp |

---

### 3.7 AL Cost Template
**Mô tả:** Master — công thức tính giá thành từ Cost Bucket.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `template_code` | Data | Y | Y | CT-01-STANDARD |
| `template_name` | Data | Y | | Tên template |
| `product_type` | Link → AL Product Type | | | Loại sản phẩm áp dụng |
| `al_lines` | Table → AL Cost Template Line | Y | | Danh sách dòng công thức |

---

### 3.8 AL Cost Template Line
**Mô tả:** Dòng công thức trong Cost Template (Child Table).

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `sort_order` | Int | | Thứ tự |
| `line_code` | Data | Y | Mã dòng: TONG_VL, NC_SX, GIA_BAN, GIA_VAT... |
| `line_label` | Data | | Tên hiển thị |
| `calc_formula` | Small Text | Y | Công thức FB (bare name): `VL_NHOM + VL_KINH + VL_VTP + VL_PK` |
| `cost_bucket` | Link → AL Cost Bucket | | Bucket tương ứng |
| `is_subtotal` | Check | | Là dòng tổng phụ? |
| `show_on_quotation` | Check | | Hiển thị trên báo giá? |

**Cost Template CT-01-STANDARD (14 dòng):**

| line_code | calc_formula | is_subtotal | cost_bucket |
|---|---|---|---|
| TONG_VL | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` | 1 | TONG_VL |
| TONG_M2 | `(W_mm/1000)*(H_mm/1000)` | 0 | — |
| NC_SX | `NC_SX_PCT * TONG_VL` | 0 | NC_SX |
| NC_LD | `NC_LD_PCT * TONG_VL` | 0 | NC_LD |
| TONG_NC | `NC_SX + NC_LD` | 1 | TONG_NC |
| OH_VC | `OH_VC_PCT * TONG_VL` | 0 | OH_VC |
| OH_QLY | `OH_QLY_PCT * (TONG_VL + TONG_NC)` | 0 | OH_QLY |
| TONG_OH | `OH_VC + OH_QLY` | 1 | TONG_OH |
| GIA_THANH | `TONG_VL + TONG_NC + TONG_OH` | 1 | GIA_THANH |
| PROFIT | `PROFIT_MARGIN * GIA_THANH` | 0 | — |
| GIA_BAN | `GIA_THANH + PROFIT` | 1 | GIA_BAN |
| DON_GIA_M2 | `GIA_BAN / TONG_M2` | 0 | — |
| VAT | `VAT_RATE * GIA_BAN` | 0 | — |
| GIA_VAT | `GIA_BAN + VAT` | 1 | GIA_VAT |

---

### 3.9 ConfigSnapshot
**Mô tả:** Wrapper mỏng quanh Formula Snapshot của FB — lưu metadata nghiệp vụ AlumGlass.

| Fieldname | Fieldtype | Unique | Mô tả |
|---|---|---|---|
| `snapshot_id` | Data | Y | UUID |
| `fb_snapshot_id` | Data | | Tham chiếu `tabFormula Snapshot` |
| `bom_version_id` | Link → AL BOM Version | | Version BOM tại thời điểm tính |
| `rule_version_ids` | JSON | | `{rule_code: version_name}` |
| `inputs_json` | JSON | | Inputs đã dùng để tính |
| `result_json` | JSON | | Kết quả FB engine trả về |
| `calculation_timestamp` | Datetime | | Thời điểm tính |
| `quotation_item_name` | Data | | Tham chiếu Quotation Item |

---

### 3.10 AL Design Revision
**Mô tả:** Thay đổi thiết kế/spec — có thể trigger BOM Version mới.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `revision_code` | Data | Y | Mã revision |
| `bom` | Link → AL BOM | Y | BOM bị ảnh hưởng |
| `requested_by` | Link → User | Y | Người yêu cầu |
| `revision_type` | Select | Y | DIMENSION / MATERIAL / PROFILE_SYSTEM / GLASS_SPEC / ACCESSORY |
| `description` | Text | Y | Mô tả thay đổi |
| `old_spec_json` | JSON | | Spec cũ |
| `new_spec_json` | JSON | | Spec mới |
| `impact_analysis` | Text | | Phân tích ảnh hưởng |
| `requires_new_bom_version` | Check | | Cần tạo BOM Version mới? |
| `new_bom_version` | Link → AL BOM Version | | Version mới (nếu có) |
| `workflow_state` | Data | | Draft / Under Review / Approved / Implemented |

---

## 4. MODULE 3: AL FORMULA & RULES

**Tên Frappe:** `al_formula_rules`
**Vai trò:** Rule engine — Calculation Rule, Dynamic Item Rule, Quantity Calc Method.

### 4.1 AL Calculation Rule
**Mô tả:** Rule CONSTANT / LOOKUP / THRESHOLD — dùng cho offset fallback, phụ thu giá màu, v.v.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `rule_code` | Data | Y | Y | OFFSET_FRAME_DEFAULT, SURCHARGE_COLOR |
| `rule_name` | Data | | | Tên hiển thị |
| `rule_type` | Select | Y | | CONSTANT / THRESHOLD / LOOKUP |
| `constant_value` | Float | | | Giá trị hằng số (nếu CONSTANT) |
| `threshold_rows` | Table → AL Rule Threshold Row | | | Dòng ngưỡng (nếu THRESHOLD) |
| `lookup_rows` | Table → AL Rule Lookup Row | | | Dòng tra cứu (nếu LOOKUP) |

**AL Rule Threshold Row (Child Table):**

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `from_value` | Decimal(10,2) | Y | Giá trị từ |
| `to_value` | Decimal(10,2) | Y | Giá trị đến |
| `result_value` | Float | Y | Kết quả |

**AL Rule Lookup Row (Child Table):**

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `key_field` | Data | Y | Giá trị khóa |
| `result_value` | Data | Y | Kết quả |

---

### 4.2 AL Dynamic Item Rule
**Mô tả:** Rule chọn Item động theo THRESHOLD hoặc LOOKUP. VD: chọn nẹp kính theo độ dày kính, chọn keo theo loại kính.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `rule_code` | Data | Y | Y | RULE-NEP-GLASSTHICK, RULE-KEO-GLASSTYPE |
| `rule_name` | Data | | | Tên hiển thị |
| `rule_type` | Select | Y | | THRESHOLD / LOOKUP |
| `current_version` | Link → AL Dynamic Item Rule Version | | | Version hiện hành |
| `threshold_rows` | Table → AL Dynamic Item Rule Threshold Row | | | Dòng ngưỡng (nếu THRESHOLD) |
| `lookup_rows` | Table → AL Dynamic Item Rule Lookup Row | | | Dòng tra cứu (nếu LOOKUP) |

**AL Dynamic Item Rule Threshold Row (Child Table):**

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `from_value` | Decimal(10,2) | Y | Giá trị từ |
| `to_value` | Decimal(10,2) | Y | Giá trị đến |
| `result_item` | Link → Item | Y | Item được chọn |

**AL Dynamic Item Rule Lookup Row (Child Table):**

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `key_field` | Data | Y | Giá trị khóa |
| `result_item` | Link → Item | Y | Item được chọn |

---

### 4.3 AL Dynamic Item Rule Version
**Mô tả:** Snapshot bất biến của Dynamic Item Rule — qua Workflow.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `rule` | Link → AL Dynamic Item Rule | Y | Rule cha |
| `version_name` | Data | Y | Tên version |
| `valid_from` | Datetime | Y | Ngày hiệu lực |
| `rule_snapshot_json` | JSON | Y | Snapshot bất biến của rule |
| `workflow_state` | Data | | Draft / Approved / Published / Retired |

---

### 4.4 AL Quantity Calc Method
**Mô tả:** Pattern tính số lượng đơn vị (unit_qty) — DATA-DRIVEN từ DB. Thêm pattern mới = 1 record.

| Fieldname | Fieldtype | Reqd | Unique | Mô tả |
|---|---|---|---|---|
| `calc_pattern_code` | Data | Y | Y | LENGTH_TO_WEIGHT, AREA, LENGTH_ONLY, COUNT, VOLUME... |
| `calc_pattern_name` | Data | Y | | Tên hiển thị |
| `calc_formula` | Small Text | | | Công thức hiển thị (KHÔNG dùng để eval) |
| `calc_fn` | Small Text | Y | | Python lambda: `lambda w, h, tlr, **kw: (w/1000) * tlr` |
| `input_vars` | JSON | | | Các biến đầu vào: `["width", "height", "weight_per_unit"]` |
| `output_unit` | Data | | | Đơn vị: kg, m2, m, cai, m3... |
| `sort_order` | Int | | | Thứ tự |

**Dữ liệu mẫu:**

| calc_pattern_code | calc_fn | input_vars | output_unit |
|---|---|---|---|
| LENGTH_TO_WEIGHT | `lambda w, h, tlr, **kw: (w/1000) * tlr` | ["width", "weight_per_unit"] | kg |
| AREA | `lambda w, h, tlr, **kw: (w/1000) * (h/1000)` | ["width", "height"] | m2 |
| LENGTH_ONLY | `lambda w, h, tlr, **kw: w/1000` | ["width"] | m |
| COUNT | `lambda w, h, tlr, **kw: 1` | [] | cai |
| VOLUME | `lambda w, h, tlr, **kw: (w/1000)*(h/1000)*(kw.get("thickness",0)/1000)` | ["width", "height", "thickness"] | m3 |

---

## 5. MODULE 4: AL SELLING

**Tên Frappe:** `al_selling`
**Vai trò:** Bán hàng — Custom Fields trên Quotation, Sales Order; Client Script nút "Tính giá"; API `calculate_bom`.

### 5.1 Quotation (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_product_type` | Link → AL Product Type | Loại sản phẩm |
| `al_bom` | Link → AL BOM | BOM áp dụng |
| `al_bom_version` | Link → AL BOM Version | Version BOM |
| `al_profile_system` | Link → AL Profile System | Hệ profile |
| `al_color` | Link → AL Color Standard | Màu sắc |
| `al_aluminum_origin` | Select | IMPORT / DOMESTIC |
| `al_aluminum_thickness` | Float | Độ dày nhôm (mm) |
| `al_aluminum_surface` | Select | POWDER_COATED / ANODIZED / WOOD_GRAIN |
| `al_loss_reason` | Select | Lý do mất đơn: GIA_CAO / CHAM_TIEN_DO / DOI_THU / KHAC |

### 5.2 Quotation Item (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_bom` | Link → AL BOM | BOM áp dụng |
| `al_bom_version` | Link → AL BOM Version | Version BOM đã dùng |
| `al_W_mm` | Float | Chiều rộng (mm) |
| `al_H_mm` | Float | Chiều cao (mm) |
| `al_transom_height_mm` | Float | Chiều cao ô kính cố định (mm) |
| `al_n_panel` | Int | Số cánh |
| `al_aluminum_color` | Data | Màu nhôm |
| `al_aluminum_origin` | Select | IMPORT / DOMESTIC |
| `al_aluminum_thickness` | Float | Độ dày nhôm |
| `al_aluminum_surface` | Select | POWDER_COATED / ANODIZED / WOOD_GRAIN |
| `al_glass_master` | Link → AL Glass Master | Loại kính |
| `al_bom_vars` | JSON | Biến bổ sung cho BOM |
| `al_config_snapshot` | Link → ConfigSnapshot | Snapshot sau khi tính |
| `al_gia_ban` | Currency | Giá bán chưa VAT |
| `al_gia_vat` | Currency | Giá bán có VAT |
| `al_tong_vl` | Currency | Tổng vật liệu |
| `al_vl_nhom` | Currency | Chi tiết VL nhôm |
| `al_vl_kinh` | Currency | Chi tiết VL kính |
| `al_vl_vtp` | Currency | Chi tiết VL phụ trợ |
| `al_vl_pk` | Currency | Chi tiết phụ kiện |

### 5.3 Sales Order (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_project_id` | Data | Mã dự án |
| `al_site_address` | Link → Address | Địa chỉ công trình |
| `al_installation_team` | Link → AL Installation Team | Đội thi công |
| `al_expected_start_date` | Date | Ngày dự kiến bắt đầu |
| `al_expected_end_date` | Date | Ngày dự kiến hoàn thành |

### 5.4 Client Script: Nút "Tính giá"
- Vị trí: Form Quotation Item
- Gọi API: `alumglass.api.calculate_bom(quotation_item_name)`
- Hiển thị kết quả: GIA_VAT + 17 dòng chi tiết BOM

### 5.5 API: `calculate_bom`
```python
@frappe.whitelist()
def calculate_bom(quotation_item_name):
    """Tính BOM cho 1 dòng báo giá — trả về GIA_VAT + chi tiết."""
    orch = BomOrchestrator(quotation_item_name)
    return orch.run()
```

### 5.6 Pricing Rule (ERPNext Core)
**Sử dụng nguyên bản — không cần custom field.** Dùng cho chiết khấu theo điều kiện.

---

## 6. MODULE 5: AL BUYING

**Tên Frappe:** `al_buying`
**Vai trò:** Mua hàng — Material Plan, Cost Variance, Supplier Price List.

### 6.1 AL Material Plan
**Mô tả:** Kế hoạch vật tư tổng hợp từ nhiều BOM.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `plan_code` | Data | Y | Mã kế hoạch |
| `plan_date` | Date | Y | Ngày lập |
| `project` | Link → Project | | Dự án |
| `sales_orders` | Table MultiSelect → Sales Order | | Các SO được gộp |
| `al_lines` | Table → AL Material Plan Line | Y | Dòng vật tư |

### 6.2 AL Material Plan Line
**Mô tả:** Dòng vật tư trong kế hoạch (Child Table).

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_code` | Link → Item | Item |
| `required_qty` | Float | Số lượng yêu cầu |
| `required_date` | Date | Ngày cần |
| `source_bom` | Data | Từ BOM nào |
| `source_slug` | Data | Từ slug nào |
| `stock_qty` | Float | Tồn kho hiện tại |
| `ordered_qty` | Float | Đã đặt hàng |
| `shortfall_qty` | Float | Thiếu hụt |
| `purchase_order` | Link → Purchase Order | PO đã tạo |
| `supplier` | Link → Supplier | NCC |

### 6.3 AL Cost Variance
**Mô tả:** So sánh giá Quotation vs GL thực tế.

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `project` | Link → Project | Dự án |
| `cost_bucket` | Link → AL Cost Bucket | Bucket chi phí |
| `estimated_amount` | Currency | Dự toán |
| `actual_amount` | Currency | Thực tế (từ GL Entry) |
| `variance_amount` | Currency | Chênh lệch |
| `variance_pct` | Float | % Chênh lệch |
| `period_from` | Date | Từ ngày |
| `period_to` | Date | Đến ngày |

### 6.4 Purchase Order / Purchase Invoice (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_project` | Link → Project | Dự án liên quan |
| `al_material_plan` | Link → AL Material Plan | Kế hoạch vật tư |

---

## 7. MODULE 6: AL STOCK

**Tên Frappe:** `al_stock`
**Vai trò:** Kho — Batch (màu), Serial No (offcut), Warehouse Map.

### 7.1 Batch (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_color` | Link → AL Color Standard | Màu sắc của lô |
| `al_source_project` | Link → Project | Dự án nguồn |
| `al_trace_stage` | Select | RAW / CUT / FABRICATED / INSTALLED |
| `al_bin_location` | Data | Vị trí kệ |

### 7.2 Serial No (ERPNext Core) — Custom Fields
**Dùng cho offcut (phế liệu nhôm tái dùng).**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_piece_length_mm` | Float | Chiều dài thanh (mm) |
| `al_is_offcut` | Check | Là offcut? |
| `al_parent_cut_id` | Data | ID lần cắt cha |

### 7.3 AL Project Warehouse Map
**Mô tả:** Ánh xạ kho tạm theo dự án.

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `project` | Link → Project | Dự án |
| `warehouse` | Link → Warehouse | Kho |
| `is_temporary` | Check | Kho tạm? |
| `activation_date` | Date | Ngày kích hoạt |
| `deactivation_date` | Date | Ngày hủy |

### 7.4 Stock Entry / Delivery Note (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_project` | Link → Project | Dự án |
| `al_installation_order` | Link → AL Installation Order | Lệnh thi công |

---

## 8. MODULE 7: AL MANUFACTURING

**Tên Frappe:** `al_manufacturing`
**Vai trò:** Sản xuất — Cutting Plan, Production Order Bridge.

### 8.1 AL Cutting Plan (Aluminum)
**Mô tả:** Kế hoạch cắt nhôm 1D — tối ưu từ phôi 6000mm.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `plan_code` | Data | Y | Mã kế hoạch cắt |
| `bom_version` | Link → AL BOM Version | Y | Version BOM |
| `project` | Link → Project | | Dự án |
| `sales_order` | Link → Sales Order | | Đơn hàng |
| `stock_bar_length_mm` | Float | Y | Chiều dài phôi (mặc định 6000) |
| `saw_kerf_mm` | Float | Y | Hao lưỡi cưa (mm) |
| `min_offcut_reusable_mm` | Float | | Ngưỡng tái dùng |
| `total_bars_required` | Int | | Tổng số phôi cần |
| `total_waste_mm` | Float | | Tổng hao hụt (mm) |
| `waste_pct` | Float | | % Hao hụt |
| `al_lines` | Table → AL Cutting Plan Line | Y | Danh sách thanh cắt |

**AL Cutting Plan Line (Child Table):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `bar_number` | Int | Số thứ tự phôi |
| `slug` | Data | Slug từ BOM |
| `item_code` | Link → Item | Profile nhôm |
| `cut_length_mm` | Float | Chiều dài cắt (mm) |
| `angle_start` | Float | Góc cắt đầu (độ) |
| `angle_end` | Float | Góc cắt cuối (độ) |
| `position_from_mm` | Float | Vị trí bắt đầu trên phôi |
| `position_to_mm` | Float | Vị trí kết thúc |
| `offcut_length_mm` | Float | Chiều dài offcut |
| `offcut_reusable` | Check | Tái dùng được? |
| `offcut_serial_no` | Link → Serial No | Serial No offcut |

### 8.2 AL Cutting Plan (Glass)
**Mô tả:** Kế hoạch cắt kính 2D — tối ưu từ tấm jumbo.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `plan_code` | Data | Y | Mã kế hoạch |
| `bom_version` | Link → AL BOM Version | Y | Version BOM |
| `project` | Link → Project | | Dự án |
| `jumbo_sheet_size` | Data | Y | Kích thước tấm jumbo: "3210x2250" |
| `edge_trim_mm` | Float | Y | Trừ hao mép |
| `total_sheets_required` | Int | | Tổng số tấm cần |
| `total_waste_m2` | Float | | Hao hụt (m2) |
| `waste_pct` | Float | | % Hao hụt |
| `al_lines` | Table → AL Glass Cutting Line | Y | Danh sách tấm cắt |

**AL Glass Cutting Line (Child Table):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `sheet_number` | Int | Số thứ tự tấm |
| `slug` | Data | Slug từ BOM |
| `item_code` | Link → Item | Loại kính |
| `cut_width_mm` | Float | Chiều rộng cắt |
| `cut_height_mm` | Float | Chiều cao cắt |
| `pos_x_mm` | Float | Vị trí X trên tấm jumbo |
| `pos_y_mm` | Float | Vị trí Y |
| `offcut_width_mm` | Float | Chiều rộng offcut |
| `offcut_height_mm` | Float | Chiều cao offcut |
| `offcut_reusable` | Check | Tái dùng được? |

### 8.3 AL Production Order Bridge
**Mô tả:** Cầu nối ERPNext Work Order — map BOM AlumGlass sang sản xuất.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `al_bom_version` | Link → AL BOM Version | Y | Version BOM |
| `al_cutting_plan_aluminum` | Link → AL Cutting Plan (Aluminum) | | Kế hoạch cắt nhôm |
| `al_cutting_plan_glass` | Link → AL Cutting Plan (Glass) | | Kế hoạch cắt kính |
| `work_order` | Link → Work Order | | Work Order ERPNext |
| `status` | Select | | Draft / In Progress / Completed |
| `start_date` | Datetime | | Ngày bắt đầu |
| `end_date` | Datetime | | Ngày kết thúc |

### 8.4 Work Order (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_production_order_bridge` | Link → AL Production Order Bridge | Cầu nối |
| `al_project` | Link → Project | Dự án |

---

## 9. MODULE 8: AL CONSTRUCTION

**Tên Frappe:** `al_construction`
**Vai trò:** Thi công — Site Survey, Installation Order, Progress, Cost.

### 9.1 AL Site Survey
**Mô tả:** Đối chiếu kích thước công trình thực tế vs thiết kế.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `survey_code` | Data | Y | Mã khảo sát |
| `project` | Link → Project | Y | Dự án |
| `sales_order` | Link → Sales Order | | Đơn hàng |
| `survey_date` | Date | Y | Ngày khảo sát |
| `surveyor` | Link → Employee | | Người khảo sát |
| `status` | Select | | Draft / Completed / Approved |
| `al_lines` | Table → AL Site Survey Line | Y | Danh sách vị trí đo |

**AL Site Survey Line (Child Table):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `location_code` | Data | Mã vị trí: "TANG1-PHONG1-CUA1" |
| `design_width_mm` | Float | Chiều rộng thiết kế |
| `design_height_mm` | Float | Chiều cao thiết kế |
| `actual_width_mm` | Float | Chiều rộng thực tế |
| `actual_height_mm` | Float | Chiều cao thực tế |
| `width_deviation_mm` | Float | Sai lệch chiều rộng |
| `height_deviation_mm` | Float | Sai lệch chiều cao |
| `within_tolerance` | Check | Trong dung sai? |
| `action_required` | Select | NONE / RESIZE / REDESIGN / CHANGE_ORDER |
| `note` | Small Text | Ghi chú |

### 9.2 AL Installation Order
**Mô tả:** Lệnh thi công.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `order_code` | Data | Y | Mã lệnh |
| `project` | Link → Project | Y | Dự án |
| `sales_order` | Link → Sales Order | Y | Đơn hàng |
| `installation_team` | Link → AL Installation Team | Y | Đội thi công |
| `planned_start_date` | Date | Y | Ngày dự kiến bắt đầu |
| `planned_end_date` | Date | Y | Ngày dự kiến kết thúc |
| `actual_start_date` | Date | | Ngày bắt đầu thực tế |
| `actual_end_date` | Date | | Ngày kết thúc thực tế |
| `status` | Select | | Draft / Scheduled / In Progress / Completed / On Hold |
| `al_tasks` | Table → AL Installation Task | Y | Danh sách công việc |

**AL Installation Task (Child Table):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `task_name` | Data | Tên công việc |
| `location_code` | Data | Vị trí |
| `bom_slug` | Data | Slug BOM tương ứng |
| `planned_hours` | Float | Giờ dự kiến |
| `actual_hours` | Float | Giờ thực tế |
| `status` | Select | Pending / In Progress / Completed |
| `assigned_to` | Link → Employee | Người thực hiện |

### 9.3 AL Installation Progress
**Mô tả:** Nhật ký tiến độ thi công (append-only).

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `installation_order` | Link → AL Installation Order | Y | Lệnh thi công |
| `report_date` | Date | Y | Ngày báo cáo |
| `reported_by` | Link → Employee | Y | Người báo cáo |
| `progress_pct` | Float | | % Hoàn thành |
| `description` | Text | | Mô tả công việc đã làm |
| `issues` | Text | | Vấn đề gặp phải |
| `next_steps` | Text | | Kế hoạch tiếp theo |
| `attachments` | Attach Image | | Ảnh hiện trường |

### 9.4 AL Installation Cost Actual
**Mô tả:** Chi phí thi công thực tế.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `installation_order` | Link → AL Installation Order | Y | Lệnh thi công |
| `cost_date` | Date | Y | Ngày phát sinh |
| `cost_type` | Select | Y | LABOR / MATERIAL / EQUIPMENT / TRANSPORT / OTHER |
| `description` | Data | Y | Mô tả |
| `amount` | Currency | Y | Số tiền |
| `paid_by` | Select | | COMPANY / CUSTOMER / SUPPLIER |
| `reference_doc` | Dynamic Link | | Chứng từ tham chiếu |
| `receipt` | Attach Image | | Chứng từ/ảnh |

---

## 10. MODULE 9: AL ACCOUNT

**Tên Frappe:** `al_account`
**Vai trò:** Kế toán dự án — tận dụng tối đa ERPNext Accounts core (Chart of Accounts, Journal Entry, GL Entry, Payment Entry, Accounting Dimension). Chỉ thêm custom fields vào core DocTypes và tạo mới DocType đặc thù nhôm kính (Change Order, P&L Snapshot, Handover Acceptance, Project Financial Config).

> **Nguyên tắc:** AL Account là lớp mỏng trên module Accounts của ERPNext. Mọi nghiệp vụ kế toán (hạch toán, công nợ, thuế, báo cáo tài chính) đều dùng core. AlumGlass chỉ thêm: custom fields trên Payment Schedule, Accounting Dimension "AL Product Type", và các DocType quản lý tài chính dự án đặc thù.

### 10.1 AL Change Order
**Mô tả:** Phát sinh có duyệt — mọi thay đổi phạm vi sau chốt hợp đồng phải qua đây.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `change_code` | Data | Y | Mã phát sinh |
| `project` | Link → Project | Y | Dự án |
| `sales_order` | Link → Sales Order | Y | Đơn hàng gốc |
| `requested_by` | Link → User | Y | Người yêu cầu |
| `request_date` | Date | Y | Ngày yêu cầu |
| `change_type` | Select | Y | SCOPE_CHANGE / DESIGN_CHANGE / MATERIAL_CHANGE / PRICE_ADJUSTMENT |
| `description` | Text | Y | Mô tả thay đổi |
| `impact_scope` | Text | | Ảnh hưởng đến BOM/vật tư |
| `impact_cost` | Currency | | Ảnh hưởng đến chi phí |
| `impact_schedule_days` | Int | | Ảnh hưởng đến tiến độ (ngày) |
| `customer_approval` | Check | | Khách hàng đã duyệt? |
| `internal_approval` | Check | | Nội bộ đã duyệt? |
| `workflow_state` | Data | | Draft / Pending / Approved / Rejected / Implemented |
| `revised_quotation` | Link → Quotation | | Báo giá điều chỉnh |
| `revised_sales_order` | Link → Sales Order | | SO điều chỉnh |

### 10.2 AL Project Profitability Snapshot
**Mô tả:** P&L bất biến theo dự án — snapshot định kỳ.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `project` | Link → Project | Y | Dự án |
| `snapshot_date` | Date | Y | Ngày chụp |
| `total_revenue` | Currency | | Tổng doanh thu |
| `total_estimated_cost` | Currency | | Tổng chi phí dự toán |
| `total_actual_cost` | Currency | | Tổng chi phí thực tế (từ GL) |
| `gross_profit` | Currency | | Lợi nhuận gộp |
| `gross_margin_pct` | Float | | % Biên lợi nhuận |
| `cost_breakdown_json` | JSON | | Chi tiết theo Cost Bucket |
| `notes` | Text | | Ghi chú |

### 10.3 AL Handover Acceptance
**Mô tả:** Biên bản nghiệm thu bàn giao.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `handover_code` | Data | Y | Mã biên bản |
| `project` | Link → Project | Y | Dự án |
| `installation_order` | Link → AL Installation Order | Y | Lệnh thi công |
| `handover_date` | Date | Y | Ngày nghiệm thu |
| `customer_representative` | Data | Y | Đại diện khách hàng |
| `company_representative` | Link → Employee | Y | Đại diện công ty |
| `acceptance_status` | Select | | ACCEPTED / ACCEPTED_WITH_PUNCHLIST / REJECTED |
| `punchlist_items` | Table → AL Punchlist Item | | Danh sách lỗi cần sửa |
| `customer_signature` | Attach Image | | Chữ ký khách hàng |
| `warranty_start_date` | Date | | Ngày bắt đầu bảo hành |

**AL Punchlist Item (Child Table):**

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `item_description` | Data | Mô tả lỗi |
| `location` | Data | Vị trí |
| `severity` | Select | MINOR / MAJOR / CRITICAL |
| `corrective_action` | Text | Biện pháp khắc phục |
| `due_date` | Date | Hạn hoàn thành |
| `status` | Select | OPEN / IN_PROGRESS / RESOLVED / VERIFIED |
| `resolved_by` | Link → Employee | Người sửa |
| `verified_by` | Link → Employee | Người kiểm tra lại |

### 10.4 Payment Schedule (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_trigger_type` | Select | MILESTONE / DATE / PERCENT_COMPLETE |
| `al_trigger_value` | Data | Giá trị trigger |
| `al_is_released` | Check | Đã giải ngân? |

### 10.5 Journal Entry (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_project` | Link → Project | Dự án liên quan |
| `al_cost_bucket` | Link → AL Cost Bucket | Cost Bucket (để so sánh dự toán vs thực tế) |
| `al_change_order` | Link → AL Change Order | Phát sinh liên quan |

### 10.6 Payment Entry (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_payment_stage` | Select | DEPOSIT / PROGRESS / FINAL / RETENTION |
| `al_handover` | Link → AL Handover Acceptance | Biên bản nghiệm thu liên quan |

### 10.7 AL Project Financial Config
**Mô tả:** Cấu hình overhead, margin, payment terms theo dự án.

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `project` | Link → Project | Dự án |
| `overhead_pct` | Float | % Overhead dự án |
| `contingency_pct` | Float | % Dự phòng |
| `payment_terms_template` | Link → Payment Terms Template | Điều khoản thanh toán |
| `retention_pct` | Float | % Bảo lưu |
| `retention_release_days` | Int | Ngày giải phóng bảo lưu |

### 10.8 Accounting Dimension (ERPNext Core) — Khai báo mới
- Dimension: `AL Product Type` — để lọc P&L theo loại sản phẩm (DOOR, WINDOW, CURTAIN_WALL)

---

## 11. MODULE 10: AL QUALITY

**Tên Frappe:** `al_quality`
**Vai trò:** Chất lượng — Quality Inspection (custom fields), Warranty Claim.

### 11.1 Quality Inspection (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_production_order_bridge` | Link → AL Production Order Bridge | Cầu nối sản xuất |
| `al_inspection_stage` | Select | INCOMING / IN_PROCESS / FINAL / SITE |
| `al_bom_slug` | Data | Slug BOM tương ứng |
| `al_surface_check` | Select | PASS / FAIL / N/A |
| `al_dimension_check` | Select | PASS / FAIL / N/A |
| `al_color_match` | Select | PASS / FAIL / N/A |
| `al_glass_defect_check` | Select | PASS / FAIL / N/A |

### 11.2 Warranty Claim (ERPNext Core) — Custom Fields

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `al_installation_order` | Link → AL Installation Order | Lệnh thi công gốc |
| `al_defect_category` | Select | GLASS_BREAK / SEAL_FAIL / HARDWARE / LEAK / COLOR_FADE / STRUCTURAL |
| `al_warranty_policy` | Link → AL Warranty Policy | Chính sách bảo hành |
| `al_inspection_date` | Date | Ngày kiểm tra |
| `al_inspection_finding` | Text | Kết quả kiểm tra |
| `al_root_cause` | Text | Nguyên nhân gốc rễ |
| `al_corrective_action` | Text | Biện pháp khắc phục |
| `al_covered_by_warranty` | Check | Có bảo hành? |
| `al_estimated_repair_cost` | Currency | Chi phí sửa chữa ước tính |

---

## 12. MODULE 11: AL AI & INTELLIGENCE

**Tên Frappe:** `al_ai`
**Vai trò:** AI — Suggestion Log, Interaction Log, Alert Config.

### 12.1 AL AI Suggestion Log
**Mô tả:** Đề xuất AI cần Approval — AI luôn là đề xuất, không tự ghi vào snapshot.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `suggestion_code` | Data | Y | Mã đề xuất |
| `created_by_ai` | Check | Y | Do AI tạo? |
| `ai_model` | Data | | Tên model AI |
| `suggestion_type` | Select | Y | PRICE_OPTIMIZATION / MATERIAL_ALTERNATIVE / DESIGN_IMPROVEMENT / RISK_ALERT / SCHEDULE_OPTIMIZATION |
| `target_doctype` | Link → DocType | | DocType đích |
| `target_docname` | Data | | Document đích |
| `suggestion_content` | JSON | Y | Nội dung đề xuất |
| `confidence_score` | Float | | Điểm tự tin (0-1) |
| `rationale` | Text | | Lý do AI đưa ra |
| `status` | Select | | PENDING / APPROVED / REJECTED / IMPLEMENTED |
| `approved_by` | Link → User | | Người duyệt |
| `approved_on` | Datetime | | Ngày duyệt |
| `implementation_result` | Text | | Kết quả triển khai |

### 12.2 AL AI Interaction Log
**Mô tả:** Tương tác tra cứu — không cần approval.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `interaction_code` | Data | Y | Mã tương tác |
| `user` | Link → User | Y | Người dùng |
| `interaction_date` | Datetime | Y | Thời điểm |
| `query_type` | Select | | PRICE_INQUIRY / MATERIAL_SEARCH / BOM_COMPARE / SPEC_CHECK / COST_ESTIMATE |
| `query_text` | Text | Y | Câu hỏi |
| `ai_response` | Text | | Trả lời của AI |
| `ai_model` | Data | | Model |
| `response_time_ms` | Int | | Thời gian phản hồi |
| `user_feedback` | Select | | HELPFUL / PARTIALLY / NOT_HELPFUL |
| `feedback_note` | Text | | Ghi chú feedback |

### 12.3 AL Alert Config
**Mô tả:** Cấu hình cảnh báo — trigger và notification.

| Fieldname | Fieldtype | Reqd | Mô tả |
|---|---|---|---|
| `alert_code` | Data | Y | Mã cảnh báo |
| `alert_name` | Data | Y | Tên cảnh báo |
| `alert_type` | Select | Y | BOM_VERSION_EXPIRED / COST_VARIANCE / SCHEDULE_DELAY / QC_FAILED / MATERIAL_SHORTAGE / WARRANTY_EXPIRING |
| `trigger_condition` | Small Text | | Điều kiện kích hoạt (FB formula) |
| `recipients` | Table MultiSelect → User | | Người nhận |
| `notification_channel` | Select | | EMAIL / SYSTEM / SMS / ALL |
| `is_active` | Check | | (default=1) |
| `cooldown_minutes` | Int | | Thời gian giãn cách (phút) |

---

## 13. MODULE 12: FORMULA BUILDER (FB) — TÍCH HỢP

**Tên Frappe:** `formula_builder` (app external)
**Vai trò:** Engine nền tảng — AlumGlass dùng nguyên bản, không sửa code FB.

### 13.1 Formula Global Variable (FB — AlumGlass chỉ dùng 3 biến)

Sau review v28.3, phạm vi Global Variable bị thu hẹp — chỉ dùng cho hằng số bất biến tuyệt đối.

| var_name | value_source | constant_value | Ghi chú |
|---|---|---|---|
| VAT_RATE | CONSTANT | 0.10 | ✅ Thuế GTGT — luật áp dụng đồng loạt |
| OH_VC_PCT | CONSTANT | 0.03 | Chi phí vận chuyển (cân nhắc chuyển scoped) |
| OH_QLY_PCT | CONSTANT | 0.03 | Chi phí quản lý |

> **Đã chuyển khỏi Global Variable:** NC_SX_PCT → AL Product Type, NC_LD_PCT → AL Product Type, PROFIT_MARGIN → AL Product Type, OFFSET_FRAME → AL Profile System, OFFSET_GLASS → AL Profile System, OFFSET_FIXED → AL Profile System, OFFSET_DO_NGANG → AL Profile System.

### 13.2 Formula Set (FB)
- **BOM_LINE:** 3 công thức `unit_qty`, `total_qty`, `line_total` cho mỗi dòng Bom Item.

### 13.3 Formula Variable Binding (FB)
- Map variable giữa AlumGlass context và FB variable system.

### 13.4 Formula Snapshot (FB)
- DocType generic của FB — lưu toàn bộ 5-layer EnterpriseSnapshot vào DB.
- Tất cả data field là JSON (= MariaDB LONGTEXT).
- `snapshot_id`, `engine_meta`, `dag_structure`, `formulas`, `business_input`, `outputs`, `execution_trace`, `audit_trail`

### 13.5 Formula Builder Settings (FB)
- Cấu hình security, rate limit, whitelist function, Formula Column Name.

---

## 14. BẢNG TỔNG HỢP DOCTYPE THEO MODULE

### 14.1 DocType Mới (AlumGlass App)

| # | DocType | Module | Loại | Số trường | Ghi chú |
|---|---|---|---|---|---|
| 1 | AL Slug Library | AL Master Data | Master | 5 | Slug tập trung |
| 2 | AL Material Category | AL Master Data | Master | 12 | Danh mục vật tư động |
| 3 | AL Profile System | AL Master Data | Master | 8 | Hệ profile + offset |
| 4 | AL Color Standard | AL Master Data | Master | 6 | Danh mục màu |
| 5 | AL Glass Type | AL Master Data | Master | 2 | Phân loại kính |
| 6 | AL Glass Master | AL Master Data | Master | 7 | Thông số kỹ thuật kính |
| 7 | AL Product Type | AL Master Data | Master | 6 | Loại sản phẩm + NC/PROFIT |
| 8 | AL Pricing Dimension | AL Master Data | Master | 10 | Đặc tính giá động |
| 9 | AL Variable Dimension Mapping | AL Master Data | Master | 3 | Cầu nối Variable ↔ Dimension |
| 10 | AL Accessory Set | AL Master Data | Master | 4 | Bộ phụ kiện |
| 11 | AL Accessory Line | AL Master Data | Child | 4 | Dòng phụ kiện |
| 12 | AL Cutting Standard | AL Master Data | Master | 10 | Quy cách cắt chuẩn |
| 13 | AL Installation Team | AL Master Data | Master | 5 | Đội thi công |
| 14 | AL Warranty Policy | AL Master Data | Master | 4 | Chính sách bảo hành |
| 15 | AL Supplier Price List | AL Master Data | Master | 8 | Bảng giá NCC |
| 16 | AL Supplier Price List Line | AL Master Data | Child | 4 | Dòng bảng giá NCC |
| 17 | AL Bom Item | AL BOM Engine | Child | 30 | Dòng vật tư — trung tâm |
| 18 | AL Bom Set | AL BOM Engine | Master | 7 | Tập hợp Bom Item |
| 19 | AL BOM | AL BOM Engine | Master | 12 | BOM + Cost Template |
| 20 | AL BOM Version | AL BOM Engine | Master | 8 | Snapshot BOM |
| 21 | AL BOM Change Log | AL BOM Engine | Child | 7 | Nhật ký thay đổi |
| 22 | AL Cost Bucket | AL BOM Engine | Master | 11 | Tài khoản chi phí |
| 23 | AL Cost Template | AL BOM Engine | Master | 4 | Master công thức giá |
| 24 | AL Cost Template Line | AL BOM Engine | Child | 7 | Dòng công thức |
| 25 | ConfigSnapshot | AL BOM Engine | Master | 9 | Wrapper snapshot |
| 26 | AL Calculation Rule | AL Formula & Rules | Master | 6 | Rule CONSTANT/LOOKUP/THRESHOLD |
| 27 | AL Rule Threshold Row | AL Formula & Rules | Child | 3 | Dòng ngưỡng |
| 28 | AL Rule Lookup Row | AL Formula & Rules | Child | 2 | Dòng tra cứu |
| 29 | AL Dynamic Item Rule | AL Formula & Rules | Master | 6 | Rule chọn Item động |
| 30 | AL Dynamic Item Rule Threshold Row | AL Formula & Rules | Child | 3 | Dòng ngưỡng Item |
| 31 | AL Dynamic Item Rule Lookup Row | AL Formula & Rules | Child | 2 | Dòng tra cứu Item |
| 32 | AL Dynamic Item Rule Version | AL Formula & Rules | Master | 5 | Snapshot Rule |
| 33 | AL Quantity Calc Method | AL Formula & Rules | Master | 7 | Pattern tính quantity |
| 34 | AL Material Plan | AL Buying | Master | 6 | Kế hoạch vật tư |
| 35 | AL Material Plan Line | AL Buying | Child | 10 | Dòng vật tư |
| 36 | AL Cost Variance | AL Buying | Master | 8 | So sánh dự toán vs thực tế |
| 37 | AL Project Warehouse Map | AL Stock | Master | 5 | Ánh xạ kho dự án |
| 38 | AL Cutting Plan (Aluminum) | AL Manufacturing | Master | 10 | Kế hoạch cắt nhôm 1D |
| 39 | AL Cutting Plan Line | AL Manufacturing | Child | 11 | Dòng cắt nhôm |
| 40 | AL Cutting Plan (Glass) | AL Manufacturing | Master | 9 | Kế hoạch cắt kính 2D |
| 41 | AL Glass Cutting Line | AL Manufacturing | Child | 10 | Dòng cắt kính |
| 42 | AL Production Order Bridge | AL Manufacturing | Master | 7 | Cầu nối Work Order |
| 43 | AL Site Survey | AL Construction | Master | 8 | Khảo sát công trình |
| 44 | AL Site Survey Line | AL Construction | Child | 10 | Dòng vị trí đo |
| 45 | AL Installation Order | AL Construction | Master | 12 | Lệnh thi công |
| 46 | AL Installation Task | AL Construction | Child | 7 | Công việc thi công |
| 47 | AL Installation Progress | AL Construction | Master | 8 | Nhật ký tiến độ |
| 48 | AL Installation Cost Actual | AL Construction | Master | 9 | Chi phí thi công thực tế |
| 49 | AL Change Order | AL Account | Master | 17 | Phát sinh có duyệt |
| 50 | AL Project Profitability Snapshot | AL Account | Master | 9 | P&L dự án |
| 51 | AL Handover Acceptance | AL Account | Master | 10 | Biên bản nghiệm thu |
| 52 | AL Punchlist Item | AL Account | Child | 8 | Lỗi cần sửa |
| 53 | AL Design Revision | AL BOM Engine | Master | 12 | Thay đổi thiết kế (trigger BOM Version mới) |
| 54 | AL Project Financial Config | AL Account | Master | 7 | Cấu hình tài chính dự án |
| 55 | AL AI Suggestion Log | AL AI | Master | 14 | Đề xuất AI |
| 56 | AL AI Interaction Log | AL AI | Master | 10 | Tương tác AI |
| 57 | AL Alert Config | AL AI | Master | 8 | Cấu hình cảnh báo |

### 14.2 Core ERPNext — Custom Fields Bổ Sung

| Core DocType | Module gốc | AL Module tương ứng | Custom Fields thêm | Mục đích |
|---|---|---|---|---|
| Item | Stock | AL Master Data | 5 fields | `al_material_category`, `al_glass_master`, `al_weight_per_m`, `al_is_color_variable`, `al_material_category_code` |
| Item Price | Stock | AL Selling | N fields (động) | `custom_pd_{dimension_code}` — tự sinh từ AL Pricing Dimension |
| Batch | Stock | AL Stock | 4 fields | `al_color`, `al_source_project`, `al_trace_stage`, `al_bin_location` |
| Serial No | Stock | AL Stock | 3 fields | `al_piece_length_mm`, `al_is_offcut`, `al_parent_cut_id` |
| Quotation | Selling | AL Selling | 9 fields | `al_product_type`, `al_bom`, `al_bom_version`, `al_profile_system`, `al_color`, `al_aluminum_origin`, `al_aluminum_thickness`, `al_aluminum_surface`, `al_loss_reason` |
| Quotation Item | Selling | AL Selling | 19 fields | `al_bom`, `al_bom_version`, `al_W_mm`, `al_H_mm`, `al_transom_height_mm`, `al_n_panel`, `al_aluminum_color`, `al_aluminum_origin`, `al_aluminum_thickness`, `al_aluminum_surface`, `al_glass_master`, `al_bom_vars`, `al_config_snapshot`, `al_gia_ban`, `al_gia_vat`, `al_tong_vl`, `al_vl_nhom`, `al_vl_kinh`, `al_vl_vtp`, `al_vl_pk` |
| Sales Order | Selling | AL Selling | 5 fields | `al_project_id`, `al_site_address`, `al_installation_team`, `al_expected_start_date`, `al_expected_end_date` |
| Purchase Order | Buying | AL Buying | 2 fields | `al_project`, `al_material_plan` |
| Purchase Invoice | Buying | AL Buying | 2 fields | `al_project`, `al_material_plan` |
| Stock Entry | Stock | AL Stock | 2 fields | `al_project`, `al_installation_order` |
| Delivery Note | Stock | AL Stock | 2 fields | `al_project`, `al_installation_order` |
| Work Order | Manufacturing | AL Manufacturing | 2 fields | `al_production_order_bridge`, `al_project` |
| Quality Inspection | Quality | AL Quality | 7 fields | `al_production_order_bridge`, `al_inspection_stage`, `al_bom_slug`, `al_surface_check`, `al_dimension_check`, `al_color_match`, `al_glass_defect_check` |
| Warranty Claim | Support | AL Quality | 8 fields | `al_installation_order`, `al_defect_category`, `al_warranty_policy`, `al_inspection_date`, `al_inspection_finding`, `al_root_cause`, `al_corrective_action`, `al_covered_by_warranty` |
| Payment Schedule | Accounts | AL Account | 3 fields | `al_trigger_type`, `al_trigger_value`, `al_is_released` |
| Journal Entry | Accounts | AL Account | 3 fields | `al_project`, `al_cost_bucket`, `al_change_order` |
| Payment Entry | Accounts | AL Account | 2 fields | `al_payment_stage`, `al_handover` |

### 14.3 Item Group & Brand (Core ERPNext — Data)

**Item Group (6 nhóm):**
| Item Group | Mô tả |
|---|---|
| NHOM_PROFILE | Nhôm profile (cha) |
| NHOM_XINGFA | Nhôm Xingfa |
| NHOM_ALUMIL | Nhôm Alumil |
| KINH | Kính |
| VTP | Vật tư phụ |
| ACCESSORY | Phụ kiện |

**Brand (3 thương hiệu):**
| Brand | Mô tả |
|---|---|
| XINGFA | Xingfa |
| ALUMIL | Alumil |
| KINLONG | Kinlong |

---

### 14.4 Ma trận phụ thuộc giữa các DocType

| DocType | Phụ thuộc (phải có trước) |
|---|---|
| AL Material Category | AL Quantity Calc Method, AL Cost Bucket |
| AL Pricing Dimension | AL Material Category |
| AL Variable Dimension Mapping | AL Pricing Dimension, AL Material Category |
| AL Slug Library | AL Material Category |
| AL Glass Master | AL Glass Type |
| AL Color Standard | Item Group |
| AL Profile System | Brand |
| AL Product Type | AL Warranty Policy |
| AL Bom Item | AL Slug Library, AL Quantity Calc Method, AL Cost Bucket, AL Dynamic Item Rule, Item |
| AL Bom Set | AL Bom Item, AL Profile System, AL Product Type |
| AL Cost Template | AL Cost Bucket |
| AL Cost Template Line | AL Cost Template, AL Cost Bucket |
| AL BOM | AL Bom Set, AL Accessory Set, AL Cost Template, AL Product Type, Brand |
| AL BOM Version | AL BOM |
| AL BOM Change Log | AL BOM Version |
| ConfigSnapshot | AL BOM Version, Formula Snapshot (FB) |
| AL Calculation Rule | — (độc lập) |
| AL Rule Threshold Row | AL Calculation Rule |
| AL Rule Lookup Row | AL Calculation Rule |
| AL Dynamic Item Rule | Item (result_item) |
| AL Dynamic Item Rule Threshold Row | AL Dynamic Item Rule |
| AL Dynamic Item Rule Lookup Row | AL Dynamic Item Rule |
| AL Dynamic Item Rule Version | AL Dynamic Item Rule |
| AL Quantity Calc Method | — (độc lập) |
| Item | Item Group, Brand, AL Material Category, AL Glass Master (nếu KINH) |
| Item Price | Item, AL Color Standard (qua Pricing Dimension) |
| AL Supplier Price List | Supplier, Brand |
| AL Material Plan | Project, Sales Order |
| AL Cost Variance | Project, AL Cost Bucket |
| AL Cutting Plan (Aluminum) | AL BOM Version, Project, Sales Order |
| AL Cutting Plan (Glass) | AL BOM Version, Project, Sales Order |
| AL Production Order Bridge | AL BOM Version, AL Cutting Plan |
| AL Site Survey | Project, Sales Order |
| AL Installation Order | Project, Sales Order, AL Installation Team |
| AL Installation Progress | AL Installation Order |
| AL Installation Cost Actual | AL Installation Order |
| AL Change Order | Project, Sales Order |
| AL Project Profitability Snapshot | Project |
| AL Handover Acceptance | Project, AL Installation Order |
| AL Design Revision | AL BOM | AL BOM Engine |
| AL Project Financial Config | Project |
| AL AI Suggestion Log | — (độc lập) |
| AL AI Interaction Log | — (độc lập) |
| AL Alert Config | — (độc lập) |

---

## PHỤ LỤC: SƠ ĐỒ PHỤ THUỘC DOCTYPE

```
ITEM GROUP ─────────────────────────────────────────────────────────────┐
BRAND ──────────────────────────────────────────────────────────────┐   │
                                                                    │   │
┌─────────────────────────────────────────────────────────────────┐ │   │
│ MODULE: AL MASTER DATA                                          │ │   │
│                                                                 │ │   │
│ AL Material Category ─────────────────────────────────┐         │ │   │
│ AL Glass Type ──→ AL Glass Master                     │         │ │   │
│ AL Color Standard ──────────────────────────────┐     │         │ │   │
│ AL Profile System ──┐                           │     │         │ │   │
│ AL Product Type ────┤                           │     │         │ │   │
│ AL Pricing Dimension┤                           │     │         │ │   │
│ AL Slug Library ────┤ (category)                │     │         │ │   │
│                     │                           │     │         │ │   │
│                     ▼                           ▼     ▼         │ │   │
│              ┌─────────────────────────────────────────────┐    │ │   │
│              │          MODULE: AL BOM ENGINE              │    │ │   │
│              │                                             │    │ │   │
│              │  AL Cost Bucket ──→ AL Cost Template        │    │ │   │
│              │       │                    │                │    │ │   │
│              │       │                    ▼                │    │ │   │
│              │       │           AL Cost Template Line     │    │ │   │
│              │       │                                     │    │ │   │
│              │       ▼                                     │    │ │   │
│              │  AL Bom Item ──→ AL Bom Set ──→ AL BOM      │    │ │   │
│              │                                    │        │    │ │   │
│              │                                    ▼        │    │ │   │
│              │                           AL BOM Version    │    │ │   │
│              │                                    │        │    │ │   │
│              │                                    ▼        │    │ │   │
│              │                            ConfigSnapshot   │    │ │   │
│              └─────────────────────────────────────────────┘    │ │   │
└─────────────────────────────────────────────────────────────────┘ │   │
                                                                    │   │
┌─────────────────────────────────────────────────────────────────┐ │   │
│ MODULE: AL FORMULA & RULES                                      │ │   │
│                                                                 │ │   │
│ AL Calculation Rule ──────────────────────────────┐             │ │   │
│ AL Dynamic Item Rule ──→ AL Dynamic Item Rule Version           │ │   │
│ AL Quantity Calc Method                                         │ │   │
└─────────────────────────────────────────────────────────────────┘ │   │
                                                                    │   │
┌─────────────────────────────────────────────────────────────────┐ │   │
│ MODULE: AL SELLING (Custom ERPNext Core)                        │ │   │
│                                                                 │ │   │
│ Quotation + Quotation Item (custom fields)                      │ │   │
│     │                                                           │ │   │
│     ▼                                                           │ │   │
│ Sales Order (custom fields)                                     │ │   │
│     │                                                           │ │   │
│     ├──→ AL Construction: Installation Order                    │ │   │
│     ├──→ AL Manufacturing: Cutting Plan, Work Order             │ │   │
│     └──→ AL Buying: Material Plan                               │ │   │
└─────────────────────────────────────────────────────────────────┘ │   │
(các module còn lại phụ thuộc Sales Order)                                                          
```

### 14.5 Slug Color Map (Bổ sung)

**Mô tả:** Mapping giữa slug và màu — dùng cho sản phẩm nhôm 2 màu (dual-color).

| Fieldname | Fieldtype | Mô tả |
|---|---|---|
| `slug_color_map` | JSON | `{"canh_ngang": "WHITE", "canh_dung": "DARK", ...}` |

Field này có thể đặt trên AL Bom Set hoặc AL BOM, cho phép các dòng profile khác nhau có màu khác nhau (VD: mặt ngoài màu DARK, mặt trong màu WHITE).

### 14.6 Hooks Frappe (hooks.py) — Tổng hợp

| Loại hook | DocType / Sự kiện | Hàm xử lý |
|---|---|---|
| `doc_events` | Quotation — before_serve | `pin_bom_version` |
| `doc_events` | Quotation Item — validate | `validate_bom_inputs` |
| `doc_events` | Sales Order Item — on_submit | `trigger_material_plan` |
| `doc_events` | Stock Entry — on_submit | `update_batch_trace_stage` |
| `doc_events` | AL Cutting Plan — validate | `material_check_hook` |
| `doc_events` | AL Installation Progress — after_insert | `update_installation_order_progress` |
| `doc_events` | Item Price — validate | `validate_unique_price_combo` |
| `doc_events` | AL BOM Version — on_change | `take_bom_snapshot_on_publish` |
| `doc_events` | AL Dynamic Item Rule Version — on_change | `take_rule_snapshot_on_publish` |
| `doc_events` | AL Pricing Dimension — after_insert | `auto_create_custom_field` |
| `doc_events` | AL Bom Item — validate | `validate_bom_item` (data-driven) |
| `doc_events` | AL Cost Bucket — validate | `validate_source_config` |
| `fb_source_types` | (global) | `alumglass.fb_handlers.aluminum_price_composite`, `glass_master_data`, `cost_bucket_aggregate` |
| `app_include_js` | (global) | `alumglass/js/cost_template.js`, `alumglass/js/bom_dialog.js` |
| `whitelisted_methods` | (global) | `calculate_bom`, `get_cost_template_context`, `validate_formula` |

---

*Tài liệu này mô tả đầy đủ 57 DocType mới + 15 Core DocType được custom, phân bổ trong 12 module. Mọi số liệu, công thức, tên field tham chiếu từ `v28.md` và `KE_HOACH_TRIEN_KHAI_CHI_TIET.md`.*
