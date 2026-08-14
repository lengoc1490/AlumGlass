# HƯỚNG DẪN TRIỂN KHAI — ALUMGLASS ERP v28.8

> **Mục tiêu:** Hướng dẫn từng bước từ cài đặt → cấu hình → vận hành → go-live
> **Đối tượng:** Người triển khai ERP, BOM Manager, System Administrator
> **Ngày:** 2026-08-04

---

## MỤC LỤC

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt](#2-cài-đặt)
3. [Cấu hình ban đầu](#3-cấu-hình-ban-đầu)
4. [Seed dữ liệu demo](#4-seed-dữ-liệu-demo)
5. [Tạo sản phẩm đầu tiên](#5-tạo-sản-phẩm-đầu-tiên)
6. [Phân quyền người dùng](#6-phân-quyền-người-dùng)
7. [Quy trình báo giá](#7-quy-trình-báo-giá)
8. [Kiểm thử & Xác nhận](#8-kiểm-thử--xác-nhận)
9. [Go-live Checklist](#9-go-live-checklist)
10. [Bảo trì & Vận hành](#10-bảo-trì--vận-hành)
11. [Xử lý sự cố](#11-xử-lý-sự-cố)

---

## 1. YÊU CẦU HỆ THỐNG

### 1.1 Phần mềm

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| **Frappe Framework** | v16.x | Bắt buộc |
| **ERPNext** | v16.x | Bắt buộc |
| **Python** | 3.12 - 3.14 | Khuyến nghị 3.12/3.13 cho production |
| **MariaDB** | 10.6+ | |
| **Redis** | 6+ | Cho cache |
| **Node.js** | 18+ | Cho JS build |
| **Formula Builder** | v31+ | App dependency — tự cài nếu dùng bench |

### 1.2 Apps yêu cầu

```bash
# Kiểm tra apps đã cài
bench list-apps

# Phải có:
# - frappe (v16)
# - erpnext (v16)
# - formula_builder (v31+)
# - alumglass (v28.8)
```

---

## 2. CÀI ĐẶT

### 2.1 Cài đặt mới hoàn toàn

```bash
# Bước 1: Tạo bench mới (nếu chưa có)
bench init --frappe-branch version-16 frappe-bench
cd frappe-bench

# Bước 2: Tạo site
bench new-site your-site.com --db-name alumglass_prod
bench use your-site.com

# Bước 3: Cài ERPNext
bench get-app erpnext --branch version-16
bench install-app erpnext

# Bước 4: Cài Formula Builder
bench get-app formula_builder --branch version-31
bench install-app formula_builder

# Bước 5: Cài AlumGlass
bench get-app alumglass --branch version-16
bench install-app alumglass
# → Tự động: install_all_custom_fields() + install_roles_and_permissions()
```

### 2.2 Cài vào site có sẵn

```bash
cd /path/to/frappe-bench

# Cài Formula Builder (nếu chưa có)
bench get-app formula_builder --branch version-31
bench --site your-site.com install-app formula_builder

# Cài AlumGlass
bench get-app alumglass --branch version-16
bench --site your-site.com install-app alumglass
```

### 2.3 Kiểm tra cài đặt

```bash
# Kiểm tra custom fields đã được tạo
bench --site your-site.com console
>>> import frappe
>>> frappe.db.exists("Custom Field", {"dt": "Quotation Item", "fieldname": "al_bom"})
# → Trả về tên record nếu thành công

# Kiểm tra roles
>>> frappe.db.exists("Role", "AL Sales User")
# → Trả về "AL Sales User" nếu thành công
```

---

## 3. CẤU HÌNH BAN ĐẦU

### 3.1 Cấu hình Company & Defaults

```bash
# ERPNext Setup Wizard (nếu chưa chạy)
bench --site your-site.com console
>>> import frappe
>>> from erpnext.setup.setup_wizard.setup_wizard import setup_complete
>>> # Hoặc vào Desk → Setup Wizard
```

### 3.2 Tạo Item Groups

```
Desk → Item → Item Group:
├── ALUMINUM_PROFILES    (Nhôm profile)
├── GLASS                (Kính)
├── ACCESSORIES          (Phụ kiện)
├── SUPPLIES             (Vật tư phụ: keo, gioăng, vít)
├── SELLING_ITEMS        (Item phi tồn kho đại diện: CDMQ-2C, CDMQ-4C...)
└── RAW_MATERIALS        (Nguyên liệu: phôi nhôm 6m, tấm kính jumbo...)
```

### 3.3 Tạo Items

**Item phi tồn kho (đại diện sản phẩm):**
- CDMQ-2C: Item Group=SELLING_ITEMS, Is Stock Item=❌
- CDMQ-4C: Item Group=SELLING_ITEMS, Is Stock Item=❌

**Item profile nhôm (tồn kho):**
- NHOM-XINGFA: Item Group=ALUMINUM_PROFILES, Is Stock Item=✅
- XF55-KB-20, XF55-CANH-25... (nếu dùng Item riêng từng profile)

**Item kính:**
- KINH-LOWE-24: Item Group=GLASS, Is Stock Item=✅

**Item phụ kiện:**
- KL-MZS20, KL-KHOA-01: Item Group=ACCESSORIES, Is Stock Item=✅

### 3.4 Tạo Price List

```
Desk → Accounting → Price List:
  Standard Selling (mặc định)
  Standard Buying  (mặc định)
```

---

## 4. SEED DỮ LIỆU DEMO

Seed data tạo đầy đủ cấu hình mẫu cho 2 sản phẩm (CDMQ-2C, CDMQ-4C):

```bash
bench --site your-site.com console
>>> from alumglass.setup.seed_demo_data import seed_all
>>> seed_all()
```

Dữ liệu được tạo (có thể kiểm tra từng bảng):

| Loại | Dữ liệu |
|---|---|
| **AL Profile System** | XINGFA_55 |
| **AL Product Type** | DOOR |
| **AL Material Category** | NHOM, KINH, VTP, PK |
| **AL Color Standard** | WHITE (×1.0), DARK (×1.08), GRAY, GO |
| **AL Glass Master** | KINH-LOWE-24 (total_thick_mm=24) |
| **AL Slug Library** | 17 slugs (khung_ngang_tren, kinh_tren...) |
| **AL Variable Library** | 25+ variables (cả system + user) |
| **AL Variable Set** | VS-CDMQ-2C, VS-CDMQ-4C |
| **AL Pricing Dimension** | MAU_SAC, XUAT_XU, DO_DAY, BE_MAT |
| **AL Variable Dimension Mapping** | 4 mappings |
| **AL Cost Bucket** | 14 buckets |
| **AL Cost Template** | CT-01-STANDARD (14 dòng) |
| **AL Calculation Rule** | RULE-BANLE-QTY, RULE-HEIGHT-MULT |
| **AL Quantity Calc Method** | LENGTH_TO_WEIGHT, AREA, LENGTH_ONLY, COUNT |
| **AL Bom Set** | BS-CDMQ-2C, BS-CDMQ-4C |
| **AL BOM** | BOM-CDMQ-2C, BOM-CDMQ-4C |
| **Item** | CDMQ-2C, CDMQ-4C, NHOM-XINGFA, các profile... |
| **Item Price** | NHOM-XINGFA (Standard Selling) |

---

## 5. TẠO SẢN PHẨM ĐẦU TIÊN

### 5.1 Quy trình tạo sản phẩm mới

Ví dụ: Tạo "Cửa sổ 1 cánh mở quay" (CSMQ-1C)

```
BƯỚC 1: AL Variable Set → VS-CSMQ-1C
  - Chọn biến từ Library: W_mm, H_mm, n_panel=1, aluminum_color...
  - System vars tự động thêm

BƯỚC 2: AL Slug Library (nếu cần slug mới)
  - canh_ngang_cs, canh_dung_cs, kinh_cs...

BƯỚC 3: AL Accessory Set → ACC-CSMQ-1C
  - tay_nam, khoa, ban_le (qty_formula: lookup_rule('RULE-BANLE-QTY', H_mm)*n_panel)

BƯỚC 4: AL Bom Set → BS-CSMQ-1C
  - Nhập 10-14 Bom Items (khung, cánh, kính, nẹp, keo, gioăng, vít...)
  - Mỗi dòng: slug, category, item_code, width, height, qty, calc_pattern, cost_bucket
  - Link: variable_set=VS-CSMQ-1C
  - formula_fieldnames: ["width","height","qty","show_condition","rule_input_expr"]

BƯỚC 5: AL BOM → BOM-CSMQ-1C
  - bom_set=BS-CSMQ-1C, default_cost_template=CT-01-STANDARD
  - representative_item=CSMQ-1C

BƯỚC 6: AL BOM Version → Publish
  - Tự động snapshot BOM Set + Cost Template
  - Sau Publish: immutable (không sửa được snapshot)
```

### 5.2 Công thức mẫu cho Bom Items

```
# Khung ngang trên (slug=khung_ngang_tren, category=NHOM)
width:  W_mm
height: 0
qty:    2
calc_pattern: LENGTH_TO_WEIGHT
price_base_item: NHOM-XINGFA

# Kính trên (slug=kinh_tren, category=KINH)
width:  W_mm - 2*OFFSET_FIXED
height: TransomHeight_mm - OFFSET_FIXED
qty:    1
calc_pattern: AREA
default_glass_master: KINH-LOWE-24

# Nẹp kính (slug=nep_kinh_tren, category=NHOM)
width:  W_mm - 2*OFFSET_FIXED
height: 0
qty:    2
calc_pattern: LENGTH_ONLY
item_selection_mode: Rule
item_rule: RULE-NEP-GLASSTHICK
rule_input_expr: items.kinh_tren.glass_thick

# Keo (slug=keo_tren, category=VTP)
width:  W_mm - 2*OFFSET_FIXED
height: 0
qty:    1
calc_pattern: LENGTH_ONLY
item_selection_mode: Rule
item_rule: RULE-KEO-GLASSTYPE
rule_input_expr: items.kinh_tren.glass_type
```

---

## 6. PHÂN QUYỀN NGƯỜI DÙNG

### 6.1 4 Role mặc định

Sau khi `install-app alumglass`, 4 role đã được tạo và gán quyền:

| Role | Dùng cho |
|---|---|
| **AL Sales User** | Nhân viên kinh doanh / báo giá |
| **AL BOM Manager** | Kỹ thuật / thiết kế sản phẩm |
| **AL Site Engineer** | Giám sát / thi công công trường |
| **AL Project Accountant** | Kế toán dự án |

### 6.2 Gán Role cho User

```
Desk → User → chọn User → tab Roles:
  - Thêm AL Sales User (cho nhân viên bán hàng)
  - Thêm AL BOM Manager (cho kỹ thuật)
  - ...
  
User có thể có nhiều role. Không cần System Manager cho nghiệp vụ hàng ngày.
```

### 6.3 Kiểm tra phân quyền

```bash
bench --site your-site.com console
>>> import frappe
>>> # Kiểm tra quyền của AL Sales User trên Quotation
>>> roles = frappe.get_roles("AL Sales User")  # nếu đã có user với role này
>>> frappe.get_all("Custom DocPerm", filters={"parent": "Quotation", "role": "AL Sales User"})
```

### 6.4 Thêm role mới (nếu cần)

Sửa `alumglass/setup/install_roles.py`:
```python
ROLES = [
    ...
    {"role_name": "AL Warehouse Staff", "desk_access": 1},  # thêm
]

MODULE_PERMISSIONS = {
    ...
    "AL Stock": {
        "AL Warehouse Staff": {"read": 1, "write": 1, "create": 1, "export": 1},
        ...
    },
}
```

Chạy lại:
```bash
bench --site your-site.com console
>>> from alumglass.setup.install_roles import install_roles_and_permissions
>>> install_roles_and_permissions()
```

---

## 7. QUY TRÌNH BÁO GIÁ

### 7.1 Flow hàng ngày (Sales User)

```
1. Desk → CRM → Quotation → New
2. Chọn Customer, AL Profile System (XINGFA_55)
3. Thêm Quotation Item:
   - Item: CDMQ-2C (item đại diện)
   - AL BOM: BOM-CDMQ-2C
4. Bấm nút 📐 Tham số BOM → Dialog:
   - W_mm: 2400
   - H_mm: 2600
   - n_panel: 2
   - TransomHeight_mm: 600
   - aluminum_color: WHITE
   - aluminum_origin: IMPORT
   - aluminum_thickness: 20
   - aluminum_surface: POWDER_COATED
5. Bấm 💾 Lưu & Tính giá
6. Kết quả: GIA_VAT ≈ 22,717,289 VND
7. Xem chi tiết: cost_template, buckets, BOM lines
8. Save → Submit Quotation
```

### 7.2 Các nút trên form Quotation

| Nút | Vị trí | Chức năng |
|---|---|---|
| 📐 **Tham số BOM** | Quotation Item row | Mở dialog nhập tham số (W, H, màu...) |
| 💰 **Tính giá** | Quotation Item row | Chạy BomOrchestrator → hiển thị kết quả |
| 📋 **Xem BOM** | Quotation Item row | Xem cấu trúc BOM chi tiết |

---

## 8. KIỂM THỬ & XÁC NHẬN

### 8.1 Chạy test suite

```bash
# Tất cả tests
bench --site your-site.com run-tests --app alumglass

# Test cụ thể
bench --site your-site.com run-tests --app alumglass --module alumglass.tests.test_bom_orchestrator
bench --site your-site.com run-tests --app alumglass --module alumglass.tests.test_composite_pricing
```

### 8.2 Xác nhận golden case

```bash
bench --site your-site.com console
>>> from alumglass.run_test import main
>>> main()
# Expected output:
#   TEST 1: CDMQ-2C
#   GIA_VAT ≈ 22,717,289 VND (±1,000 VND)
#   ✅ PASS
#
#   TEST 2: CDMQ-4C
#   Hiển thị đầy đủ buckets, cost_template, lines
```

### 8.3 Kiểm tra composite pricing

```bash
bench --site your-site.com console
>>> from alumglass.tests.test_composite_pricing import TestCompositePricing
>>> # Xác nhận: WHITE=113,000đ ≠ DARK=999,000đ
>>> # Xác nhận: 5 lần chạy cùng màu → cùng giá (deterministic)
```

### 8.4 Kiểm tra immutability guard

```bash
bench --site your-site.com console
>>> import frappe
>>> bv = frappe.get_doc("AL BOM Version", {"bom": "BOM-CDMQ-2C", "workflow_state": "Published"})
>>> bv.bom_set_snapshot = "{}"
>>> bv.save()
# Expected: frappe.throw() → "không được sửa bom_set_snapshot/cost_template_snapshot"
```

---

## 9. GO-LIVE CHECKLIST

### 9.1 Trước go-live

- [ ] Cài đặt thành công trên môi trường production
- [ ] `bench migrate` chạy không lỗi
- [ ] Custom fields đã được tạo trên tất cả core doctypes
- [ ] 4 roles đã được tạo và gán quyền
- [ ] User đã được gán role phù hợp (không dùng System Manager)
- [ ] Seed data demo đã chạy (hoặc data thật đã nhập)
- [ ] Test suite PASS: `bench --site <site> run-tests --app alumglass`
- [ ] Golden case PASS: `run_test.main()` → GIA_VAT ≈ 22,717,289
- [ ] Composite pricing đúng: khác màu → khác giá
- [ ] Immutability guard hoạt động: không sửa được Published version
- [ ] BOM Version có thể Publish → tạo Quotation → Tính giá
- [ ] Kết quả hiển thị đúng trên dialog

### 9.2 Cấu hình production

- [ ] `requirements.txt`: kiểm tra phiên bản các thư viện
- [ ] Redis configured & running
- [ ] Database backup schedule configured
- [ ] `pyproject.toml`: Python version phù hợp môi trường hosting (3.12+)
- [ ] `hooks.py`: scheduler_events uncomment nếu cần scheduled tasks
- [ ] CI/CD pipeline configured (`.github/workflows/ci.yml`)
- [ ] Email configuration (cho notifications nếu cần)

### 9.3 Dữ liệu nghiệp vụ

- [ ] AL Profile System: tất cả hệ profile đang dùng (XINGFA_55, XINGFA_60...)
- [ ] AL Material Category: tất cả loại vật tư
- [ ] AL Color Standard: tất cả màu + price_multiplier
- [ ] AL Glass Master: tất cả loại kính
- [ ] AL Pricing Dimension: tất cả đặc tính giá
- [ ] AL Variable Dimension Mapping: map đầy đủ variable → dimension
- [ ] AL Slug Library: tất cả slug cần thiết
- [ ] AL Variable Library: tất cả biến (cả system + user)
- [ ] AL Cost Bucket: tất cả buckets
- [ ] AL Cost Template: công thức giá thành
- [ ] AL Quantity Calc Method: tất cả pattern
- [ ] AL Calculation Rule: tất cả rules
- [ ] AL Dynamic Item Rule: rules chọn item động
- [ ] Items ERPNext: tất cả profile, kính, phụ kiện, vật tư phụ
- [ ] Item Prices: bảng giá với composite key đầy đủ
- [ ] AL Bom Set → AL BOM → AL BOM Version Published

### 9.4 Sau go-live (theo dõi)

- [ ] Monitor query performance: mỗi lần tính BOM ~10-12 queries
- [ ] Kiểm tra ConfigSnapshot đang được tạo sau mỗi lần tính
- [ ] Kiểm tra `track_changes` log trên các doctype quan trọng
- [ ] Backup database hàng ngày
- [ ] Theo dõi Redis cache hit rate

---

## 10. BẢO TRÌ & VẬN HÀNH

### 10.1 Cập nhật app

```bash
cd /path/to/frappe-bench
bench switch-to-branch version-16 --app alumglass
git pull  # nếu dùng git repo local
bench migrate
bench restart
```

### 10.2 Thêm sản phẩm mới (không cần code)

Xem [Section 5](#5-tạo-sản-phẩm-đầu-tiên) — quy trình 6 bước, 0 dòng code.

### 10.3 Thêm cấu hình mới (không cần code)

| Muốn thêm | Cần làm |
|---|---|
| Hệ profile mới | 1 record `AL Profile System` |
| Màu mới | 1 record `AL Color Standard` (+ price_multiplier) |
| Loại kính mới | 1 record `AL Glass Master` |
| Pattern tính mới | 1 record `AL Quantity Calc Method` (calc_fn lambda) |
| Rule mới | 1 record `AL Calculation Rule` hoặc `AL Dynamic Item Rule` |
| Đặc tính giá mới | 1 `AL Pricing Dimension` + 1 `AL Variable Dimension Mapping` |
| Cost bucket mới | 1 `AL Cost Bucket` + sửa Cost Template |

### 10.4 Backup & Restore

```bash
# Backup database
bench --site your-site.com backup

# Restore
bench --site your-site.com restore /path/to/backup.sql.gz
```

---

## 11. XỬ LÝ SỰ CỐ

### 11.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `ModuleNotFoundError: formula_builder` | Thiếu app formula_builder | `bench get-app formula_builder && bench install-app formula_builder` |
| `BOM 'XXX' chưa có version nào được Published` | Chưa Publish BOM Version | Vào AL BOM → tạo AL BOM Version → Publish |
| `Không tìm được Item Price khớp cho 'XXX'` | Thiếu dòng Item Price hoặc composite field không khớp | Thêm Item Price với composite fields đầy đủ hoặc thêm dòng giá mặc định (không set dimension) |
| `AL BOM Version đã ở trạng thái Published` | Đang sửa version đã Published | Tạo Design Revision → phiên bản mới |
| `Không có quyền truy cập` | User chưa được gán role | Vào User → thêm role AL Sales User/AL BOM Manager... |

### 11.2 Debug BomOrchestrator

```bash
bench --site your-site.com console
>>> from alumglass.engine.bom_orchestrator import BomOrchestrator
>>> orch = BomOrchestrator("quotation_item_name")
>>> orch.b0_version_pinning()
>>> print(orch.bom_version_name, orch.bom_code)
>>> orch.b1_gather_inputs()
>>> print(orch.inputs)  # Kiểm tra inputs đã resolve đúng chưa
>>> orch.b2_prefetch_master_data()
>>> print(orch.row_literals)  # Kiểm tra giá/composite key
```

### 11.3 Kiểm tra dữ liệu

```bash
bench --site your-site.com console

# Kiểm tra composite key pricing
>>> from alumglass.engine.bom_orchestrator import BomOrchestrator
>>> # Tạo instance và gọi _get_dim_fieldnames()
>>> orch = BomOrchestrator.__new__(BomOrchestrator)
>>> orch.inputs = {"aluminum_color": "WHITE"}
>>> orch._dim_fieldname_cache = None
>>> print(orch._get_dim_fieldnames())
# → {"aluminum_color": "custom_pd_mau_sac", "aluminum_origin": "custom_pd_xuat_xu", ...}

# Kiểm tra số lượng doctype trong mỗi module
>>> import frappe
>>> for mod in ["AL Master Data", "AL Bom Engine", "AL Formula Rules"]:
...     doctypes = frappe.get_all("DocType", filters={"module": mod}, fields=["name"])
...     print(f"{mod}: {len(doctypes)} doctypes")
```

---

*Tài liệu cập nhật: 2026-08-04 | Phiên bản: v28.8*
