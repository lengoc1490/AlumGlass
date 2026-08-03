# ALUMGLASS ERP v28.6 — PRODUCTION REFERENCE

> Ngày: 2026-08-03 | Phiên bản: v28.6 | 60 Doctypes | Formula Builder v31

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

---

## 1. KIẾN TRÚC TỔNG THỂ

```
┌──────────────────────────────────────────────────────────────┐
│                    FORMULA BUILDER v31 (BẤT BIẾN)             │
│  FormulaEngine (DAG)  │  FlexibleFormulaEngine               │
│  BatchBindingResolver │  SnapshotManager                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ fb_source_types hook
┌──────────────────────────┴───────────────────────────────────┐
│              alumglass/fb_handlers.py (THIN LAYER ~100 dòng) │
│  aluminum_price_composite  │  glass_master_data              │
│  cost_bucket_aggregate     │                                 │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│         alumglass/engine/bom_orchestrator.py                  │
│  B0: Version pinning    B4: FormulaEngine (FB)               │
│  B1: Gather inputs      B5: Aggregate cost buckets           │
│  B2: Batch query        B6: FlexibleFormulaEngine (FB)       │
│  B3: Build formulas     B7: Save results                     │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│              DOCTYPE CONFIG (DB — KHÔNG CODE)                 │
│  AL Variable Library → AL Variable Set → AL Bom Set → AL BOM │
│  AL Cost Bucket → AL Cost Template                           │
│  AL Profile System  │  AL Product Type  │  AL Pricing Dim    │
│  AL Slug Library  │  AL Material Category                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. DANH SÁCH MODULE & DOCTYPE

### AL Master Data (11 doctypes)

| Doctype | Vai trò |
|---|---|
| **AL Variable Library** | Thư viện biến tập trung — định nghĩa 1 lần, dùng nhiều nơi |
| **AL Variable Set** | Tập biến cho 1 sản phẩm (Link → Variable Library) |
| **AL Variable Set Item** | Dòng biến trong Variable Set (child table) |
| **AL Slug Library** | Định danh vật tư — dùng cho cross-row reference |
| **AL Material Category** | Loại vật tư động — flags điều khiển validate |
| **AL Profile System** | Hệ profile + bộ offset hình học |
| **AL Color Standard** | Danh mục màu — composite key tra giá |
| **AL Glass Type** | Phân loại kính |
| **AL Glass Master** | Thông số kỹ thuật kính |
| **AL Product Type** | Loại sản phẩm + NC/PROFIT |
| **AL Pricing Dimension** | Đặc tính giá động — auto-sinh Custom Field |

### AL BOM Engine (12 doctypes)

| Doctype | Vai trò |
|---|---|
| **AL Bom Item** | Dòng vật tư — DocType TRUNG TÂM (child của AL Bom Set) |
| **AL Bom Set** | Tập hợp Bom Items + link Variable Set + Accessory Set |
| **AL BOM** | BOM — link Bom Set + Cost Template |
| **AL BOM Version** | Snapshot bất biến của BOM |
| **AL BOM Change Log** | Nhật ký thay đổi (child) |
| **AL Cost Bucket** | Tài khoản chi phí — source_type + source_config JSON |
| **AL Cost Template** | Master công thức giá thành |
| **AL Cost Template Item** | Dòng công thức (child) |
| **ConfigSnapshot** | Wrapper snapshot kết quả tính |
| **AL Design Revision** | Thay đổi thiết kế — trigger BOM Version |
| **AL Accessory Set** | Bộ phụ kiện (tách riêng khỏi Bom Set) |
| **AL Accessory Item** | Dòng phụ kiện (child, có qty_formula) |

### AL Formula Rules (8 doctypes)

| Doctype | Vai trò |
|---|---|
| **AL Calculation Rule** | CONSTANT / THRESHOLD / LOOKUP |
| **AL Dynamic Item Rule** | Rule chọn Item động |
| **AL Quantity Calc Method** | Pattern tính quantity (DATA-DRIVEN) |

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
2. AL Slug Library: định nghĩa slug (khung_ngang_tren, kinh_tren...)
3. AL Material Category: định nghĩa loại vật tư (NHOM, KINH, VTP...)
4. AL Quantity Calc Method: định nghĩa pattern (LENGTH_TO_WEIGHT, AREA...)
5. AL Cost Bucket: định nghĩa bucket (VL_NHOM, TONG_VL, GIA_VAT...)
6. AL Cost Template: định nghĩa công thức giá (14 dòng)
7. AL Variable Set VS-XXX: chọn biến từ Library cho sản phẩm
8. AL Accessory Set ACC-XXX: chọn phụ kiện cho sản phẩm
9. AL Bom Set BS-XXX: nhập 14-17 dòng Bom Items + link VS + ACC
10. AL BOM BOM-XXX: link Bom Set + Cost Template
11. AL BOM Version: Publish → auto-snapshot
```

### 3.2 Báo giá (hàng ngày)

```
1. Tạo Quotation → chọn khách hàng
2. Thêm Quotation Item → chọn Item sản phẩm (CDMQ-2C)
3. Chọn AL BOM → auto-load Variable Set
4. Bấm 📐 Tham số BOM → dialog hiển thị fields từ Variable Set
5. Nhập W=2400, H=2600, n_panel=2, color=WHITE...
6. Bấm 💾 Lưu & Tính giá
7. BomOrchestrator chạy 7 phase → GIA_VAT
8. Kết quả lưu vào al_bom_result JSON + al_gia_vat Currency
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

Bước 4: Tạo BOM BOM-CS1C
  → Link bom_set=BS-CS1C, cost_template=CT-01-STANDARD

Bước 5: Publish BOM Version
  → Tự động snapshot

TỔNG: 0 dòng code Python/JS
```

### Thêm ngành mới (THÉP)

```
1. AL Material Category: THÉP, has_weight=1, requires_price_base_item=1
2. AL Slug Library: thanh_ngang_thep, thanh_dung_thep...
3. AL Variable Library: thêm biến nếu cần (steel_grade...)
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
| Pattern tính mới | 1 record AL Quantity Calc Method | ❌ |
| Biến mới | 1 record AL Variable Library → thêm vào Variable Set | ❌ |
| Rule chọn Item mới | 1 record AL Dynamic Item Rule | ❌ |
| Đặc tính giá mới | 1 record AL Pricing Dimension | ❌ |
| Data source type mới | 1 hàm fb_handlers.py + 1 dòng fb_source_types | ✅ ~10 dòng |
| Sản phẩm mới | Bom Set + Variable Set + Accessory Set | ❌ |
| Ngành mới | Material Category + Slug Library + Bom Set | ❌ |

---

## 6. API REFERENCE

| Endpoint | Mục đích |
|---|---|
| `alumglass.api.calculate_bom(qi_name)` | Tính BOM cho Quotation Item |
| `alumglass.api.preview_cost_template(code, inputs)` | Preview Cost Template |
| `alumglass.api.get_variable_set_for_bom(bom_code)` | Lấy biến từ Variable Set (cho dialog) |
| `alumglass.api.get_slug_info(slug)` | Lấy thông tin Slug Library |
| `alumglass.api.resolve_item_rule(rule, input)` | Tra cứu Dynamic Item Rule |
| `alumglass.api.get_bom_structure(bom_code)` | Lấy toàn bộ cấu trúc BOM |

---

## 7. JS CLIENT SCRIPTS

| Script | Chức năng |
|---|---|
| `formula_setup.js` | Autocomplete formula cho AL Bom Set, AL Cost Template, AL Alert Config... |
| `bom_dialog.js` | Dialog hiển thị kết quả tính BOM |
| `cost_template.js` | Preview Cost Template |
| `quotation_item_dialog.js` | Dialog nhập tham số BOM (động từ Variable Set) |
| `doctype/overrides/quotation.js` | Nút 📐 Tham số + 💰 Tính giá trên Quotation form |
| `doctype/overrides/sales_order.js` | Formula Builder integration cho Sales Order |

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
9. **Pricing Dimension**: Composite key giá động, auto-sinh Custom Field
10. **Accessory Set riêng**: Phụ kiện tách khỏi Bom Items, qty_formula dùng biến chung
