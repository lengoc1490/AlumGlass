# AlumGlass v28.7.1 — HƯỚNG DẪN & VÍ DỤ TOÀN DIỆN A-Z

> **Sản phẩm mẫu:** Cửa đi 4 cánh mở quay + 2 ô kính cố định + vách kính bên hông
> **Mã:** CDMQ-4C-2TRANSOM-SIDELITE | **Hệ profile:** Xingfa 55
> **Mục tiêu:** Demo TOÀN BỘ 14 tính năng v28.7.1 trên 1 sản phẩm phức tạp thực tế

---

## MỤC LỤC

1. [Tổng quan sản phẩm mẫu](#1-tổng-quan-sản-phẩm-mẫu)
2. [Kiến trúc dữ liệu vận hành](#2-kiến-trúc-dữ-liệu-vận-hành)
3. [Step-by-Step: Tạo cấu hình sản phẩm](#3-step-by-step-tạo-cấu-hình-sản-phẩm)
4. [Step-by-Step: Báo giá & Tính toán](#4-step-by-step-báo-giá--tính-toán)
5. [Engine Flow Chi Tiết](#5-engine-flow-chi-tiết)
6. [Kết quả tính toán cụ thể](#6-kết-quả-tính-toán-cụ-thể)
7. [Snapshot & Audit Trail](#7-snapshot--audit-trail)
8. [Mở rộng hệ thống](#8-mở-rộng-hệ-thống)

---

## 1. TỔNG QUAN SẢN PHẨM MẪU

### Cửa đi 4 cánh mở quay + 2 ô kính cố định (transom) + vách kính bên

```
┌──────────────────────────────────────────────┐
│  ╔══════════════════════════════════════╗    │
│  ║         Ô KÍNH CỐ ĐỊNH TRÊN          ║    │  TransomHeightTop = 600mm
│  ║         (kinh_fixed_top)             ║    │
│  ╠══════════╦══════════╦══════════╦═════╣    │
│  ║          ║          ║          ║     ║    │
│  ║ CÁNH 1   ║ CÁNH 2   ║ CÁNH 3   ║CÁNH4║    │  H_main = 2200mm
│  ║ (mở)     ║ (mở)     ║ (mở)     ║(mở) ║    │  (H_total - TransomTop - TransomBot)
│  ║          ║          ║          ║     ║    │
│  ╠══════════╩══════════╩══════════╩═════╣    │
│  ║         Ô KÍNH CỐ ĐỊNH DƯỚI          ║    │  TransomHeightBottom = 400mm
│  ║         (kinh_fixed_bottom)          ║    │
│  ╚══════════════════════════════════════╝    │
│                                              │
│  W_total = 3600mm                            │
└──────────────────────────────────────────────┘
                   +
┌─────────────────┐
│  VÁCH KÍNH BÊN  │  SideLiteWidth = 800mm
│  (kinh_sidelite)│  SideLiteHeight = 2800mm
└─────────────────┘

THÔNG SỐ ĐẦU VÀO:
  W_total = 3600mm          (tổng chiều rộng)
  H_total = 3200mm          (tổng chiều cao)
  TransomHeightTop = 600mm  (ô kính cố định trên)
  TransomHeightBottom = 400mm (ô kính cố định dưới)
  n_panel = 4               (4 cánh mở quay)
  SideLiteWidth = 800mm     (vách kính bên)
  SideLiteHeight = 2800mm   (chiều cao vách)

  aluminum_color = DARK     (màu đen → price_multiplier = 1.08)
  aluminum_origin = IMPORT  (xuất xứ nhập khẩu)
  aluminum_thickness = 20   (độ dày sơn 20 micron)
  aluminum_surface = POWDER_COATED
  installation_height_m = 15 (tầng 5 → height_multiplier = 1.2)

  Profile System: XINGFA_55 (offset_frame=48, offset_glass=90, offset_fixed=50, offset_crossbar=48)
  Product Type: DOOR (nc_pct=0.08, nc_ld_rate=0.12, profit_margin=0.16)
```

### Các tính năng AlumGlass được sử dụng trong ví dụ này

| # | Tính năng | Áp dụng ở đâu |
|---|---|---|
| 1 | **Variable Library → Variable Set** | W_total, H_total, n_panel, màu sắc, xuất xứ... |
| 2 | **System Variables (source_doctype/source_field)** | OFFSET_FRAME, NC_SX_PCT, PROFIT_MARGIN... resolve từ AL Profile System & AL Product Type |
| 3 | **Dynamic BOM Items với formula fields** | width, height, qty của từng thanh nhôm/kính/nẹp |
| 4 | **Cross-row reference (items.X.Y)** | nẹp/keo tham chiếu width/height của kính |
| 5 | **lookup_calc_pattern (DATA-DRIVEN)** | LENGTH_TO_WEIGHT, AREA, LENGTH_ONLY, COUNT |
| 6 | **Dynamic Item Rule (THRESHOLD/LOOKUP)** | Nẹp theo độ dày kính, keo theo loại kính |
| 7 | **lookup_rule (Calculation Rule)** | Số bản lề theo H, hệ số NC theo độ cao |
| 8 | **Price Multiplier Chain** | DARK color ×1.08 qua AL Color Standard.price_multiplier |
| 9 | **Composite Key Pricing** | Tra giá nhôm theo màu + xuất xứ + độ dày + bề mặt |
| 10 | **Scrap/Waste Injection** | NHOM 3%, KINH 5% từ Material Category |
| 11 | **Cost Template (FlexibleFormulaEngine)** | TONG_VL → NC → OH → GIA_THANH → GIA_BAN → GIA_VAT |
| 12 | **BOM Version Snapshot (dynamic fields)** | Snapshot tự động copy mọi Small Text field |
| 13 | **ConfigSnapshot** | Lưu immutable record inputs + results |
| 14 | **Accessory Set với qty_formula** | Bản lề, khóa, tay nắm dùng lookup_rule |

---

## 2. KIẾN TRÚC DỮ LIỆU VẬN HÀNH

### Layer 1: AL Variable Library — Định nghĩa biến 1 lần

```
┌──────────────────────────────────────────────────────────────────┐
│                    AL VARIABLE LIBRARY                           │
│  ┌───────────────┬──────────┬────────┬──────────────┬──────────┐ │
│  │ var_name      │ var_type │ is_sys │source_doctype│src_field │ │
│  ├───────────────┼──────────┼────────┼──────────────┼──────────┤ │
│  │ W_total       │ Float    │ 0      │              │          │ │
│  │ H_total       │ Float    │ 0      │              │          │ │
│  │ n_panel       │ Int      │ 0      │              │          │ │
│  │ aluminum_color│ Link     │ 0      │              │          │ │
│  │ OFFSET_FRAME  │ Float    │ 1   ★  │AL Profile Sys│offset_fr │ │
│  │ NC_SX_PCT     │ Float    │ 1   ★  │AL Product Typ│nc_pct    │ │
│  │ PROFIT_MARGIN │ Float    │ 1   ★  │AL Product Typ│profit_mar│ │
│  │ VAT_RATE      │ Float    │ 1   ★  │              │          │ │
│  └───────────────┴──────────┴─────────┴─────────────┴───────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

### Layer 2: AL Variable Set — Chọn biến cho sản phẩm cụ thể

```
VS-CDMQ-4C: Cửa đi 4 cánh + 2 transom + sidelite
├── W_total = 3600          (override default từ Library)
├── H_total = 3200          (override default từ Library)
├── n_panel = 4             (override default từ Library)
├── TransomHeightTop = 600
├── TransomHeightBottom = 400
├── SideLiteWidth = 800
├── SideLiteHeight = 2800
├── aluminum_color = DARK   (★ trigger price_multiplier=1.08)
├── aluminum_origin = IMPORT
├── aluminum_thickness = 20
├── aluminum_surface = POWDER_COATED
├── installation_height_m = 15 (★ trigger height_multiplier=1.2)
└── glass_master = KINH-LOWE-24
```

### Layer 3: AL Bom Set → AL Bom Items (công thức động)

```
BS-CDMQ-4C: Cửa đi 4 cánh + 2 transom + sidelite
├── profile_system = XINGFA_55
├── variable_set = VS-CDMQ-4C
├── formula_fieldnames = ["width","height","qty","show_condition",
│                          "item_condition_formula","rule_input_expr"]
└── Items (26 dòng Bom):
    ├── KHUNG BAO (4 dòng)
    │   ├── khung_ngang_tren:  W=W_total, Q=1, calc=LENGTH_TO_WEIGHT
    │   ├── khung_ngang_duoi:  W=W_total, Q=1, calc=LENGTH_TO_WEIGHT
    │   ├── khung_dung_trai:   H=H_total, Q=2, calc=LENGTH_TO_WEIGHT
    │   └── khung_dung_phai:   H=H_total, Q=2, calc=LENGTH_TO_WEIGHT
    ├── ĐỐ NGANG (2 dòng)
    │   ├── do_ngang_tren:     W=W_total-2*OFFSET_DO_NGANG, Q=1
    │   └── do_ngang_duoi:     W=W_total-2*OFFSET_DO_NGANG, Q=1
    ├── CÁNH (8 dòng — 4 cánh × 2 thanh)
    │   ├── canh_dung (×4):    H=(H_total-TransomTop-TransomBot)-OFFSET_FRAME, Q=n_panel
    │   └── canh_ngang (×4):   W=W_total/n_panel-OFFSET_FRAME, Q=n_panel
    ├── KÍNH (4 dòng)
    │   ├── kinh_fixed_top:    W=W_total-2*OFFSET_FIXED, H=TransomTop-OFFSET_FIXED
    │   ├── kinh_canh (×4):    W=W_total/n_panel-OFFSET_GLASS, H=canh_dung.height
    │   ├── kinh_fixed_bottom: W=W_total-2*OFFSET_FIXED, H=TransomBot-OFFSET_FIXED
    │   └── kinh_sidelite:     W=SideLiteW-2*OFFSET_FIXED, H=SideLiteH-2*OFFSET_FIXED
    ├── NẸP KÍNH (4 dòng — ★ Rule-based)
    │   ├── nep_kinh_top:      W=2*(items.kinh_fixed_top.w+items.kinh_fixed_top.h)
    │   ├── nep_kinh_canh:     W=2*(items.kinh_canh.w+items.kinh_canh.h)
    │   ├── nep_kinh_bottom:   W=2*(items.kinh_fixed_bottom.w+items.kinh_fixed_bottom.h)
    │   └── nep_kinh_sidelite: W=2*(items.kinh_sidelite.w+items.kinh_sidelite.h)
    ├── KEO (4 dòng — ★ Rule-based)
    │   └── (tương tự nẹp, item_rule=RULE-KEO-GLASSTYPE)
    ├── GIOĂNG (1 dòng)
    └── VÍT (1 dòng): Q=15*n_panel+20
```

### Layer 4: AL BOM → AL BOM Version (snapshot bất biến)

```
BOM-CDMQ-4C:
├── bom_set = BS-CDMQ-4C
├── representative_item = NHOM-XINGFA
├── default_cost_template = CT-01-STANDARD
└── current_version → AL BOM Version v1.0
    ├── bom_set_snapshot = JSON (toàn bộ 26 items + config)
    ├── cost_template_snapshot = JSON (14 dòng công thức giá)
    └── workflow_state = Published
```

---

## 3. STEP-BY-STEP: TẠO CẤU HÌNH SẢN PHẨM

### Bước 1: Định nghĩa Variable Library

```python
# Các biến user-facing (hiển thị trong dialog)
AL Variable Library:
  W_total              | Float  | "Chiều rộng tổng (mm)"       | default=3600
  H_total              | Float  | "Chiều cao tổng (mm)"        | default=3200
  TransomHeightTop     | Float  | "Cao ô kính trên (mm)"       | default=600
  TransomHeightBottom  | Float  | "Cao ô kính dưới (mm)"       | default=400
  n_panel              | Int    | "Số cánh"                    | default=4
  SideLiteWidth        | Float  | "Rộng vách kính (mm)"        | default=800
  SideLiteHeight       | Float  | "Cao vách kính (mm)"         | default=2800
  aluminum_color       | Link→AL Color Standard | "Màu nhôm"   | default=WHITE
  aluminum_origin      | Select | "Xuất xứ"                    | default=IMPORT
  aluminum_thickness   | Float  | "Độ dày sơn (micron)"        | default=20
  aluminum_surface     | Select | "Bề mặt"                     | default=POWDER_COATED
  installation_height_m| Float  | "Chiều cao lắp đặt (m)"      | default=3
  glass_master         | Link→AL Glass Master | "Loại kính"    |

# System variables (resolve tự động, không hiện dialog)
  OFFSET_FRAME     | Float | is_system=1 | source_doctype=AL Profile System | source_field=offset_frame
  OFFSET_GLASS     | Float | is_system=1 | source_doctype=AL Profile System | source_field=offset_glass
  OFFSET_FIXED     | Float | is_system=1 | source_doctype=AL Profile System | source_field=offset_fixed
  OFFSET_DO_NGANG  | Float | is_system=1 | source_doctype=AL Profile System | source_field=offset_crossbar
  NC_SX_PCT        | Float | is_system=1 | source_doctype=AL Product Type   | source_field=nc_pct
  NC_LD_PCT        | Float | is_system=1 | source_doctype=AL Product Type   | source_field=nc_ld_rate
  PROFIT_MARGIN    | Float | is_system=1 | source_doctype=AL Product Type   | source_field=profit_margin
  VAT_RATE         | Float | is_system=1 | (từ Formula Global Variable)
  OH_VC_PCT        | Float | is_system=1 | (từ Formula Global Variable)
  OH_QLY_PCT       | Float | is_system=1 | (từ Formula Global Variable)
```

### Bước 2: Định nghĩa Material Category (với scrap %)

```python
AL Material Category:
  NHOM | default_calc_pattern=LENGTH_TO_WEIGHT | default_scrap_pct=3 ★
  KINH | default_calc_pattern=AREA             | default_scrap_pct=5 ★
  VTP  | default_calc_pattern=LENGTH_ONLY      | default_scrap_pct=2 ★
  PK   | default_calc_pattern=COUNT            | default_scrap_pct=0 ★
```

### Bước 3: Định nghĩa Slug Library (26 slugs)

```python
AL Slug Library:
  # Khung bao
  khung_ngang_tren     | NHOM | KHUNG
  khung_ngang_duoi     | NHOM | KHUNG
  khung_dung_trai      | NHOM | KHUNG
  khung_dung_phai      | NHOM | KHUNG
  # Đố ngang
  do_ngang_tren        | NHOM | KHUNG
  do_ngang_duoi        | NHOM | KHUNG
  # Cánh (4 cánh)
  canh_dung_c1..c4     | NHOM | CANH
  canh_ngang_c1..c4    | NHOM | CANH
  # Kính
  kinh_fixed_top       | KINH | GLASS
  kinh_fixed_bottom    | KINH | GLASS
  kinh_canh            | KINH | GLASS
  kinh_sidelite        | KINH | GLASS
  # Nẹp
  nep_kinh_top         | NHOM | NEP
  nep_kinh_bottom      | NHOM | NEP
  nep_kinh_canh        | NHOM | NEP
  nep_kinh_sidelite    | NHOM | NEP
  # Keo
  keo_top              | VTP  | KEO
  keo_bottom           | VTP  | KEO
  keo_canh             | VTP  | KEO
  keo_sidelite         | VTP  | KEO
  # Khác
  gioang               | VTP  | GIOANG
  vit                   | VTP  | VIT
```

### Bước 4: Định nghĩa Bom Items (với công thức động)

```python
# Mỗi dòng Bom Item có các field formula:
# width, height, qty, show_condition, item_condition_formula, rule_input_expr

# ── Ví dụ dòng canh_dung_c1 ──
slug: canh_dung_c1
category: NHOM                                    # → scrap_pct = 3%
item_code: XF55-CANH-20
item_selection_mode: Fixed
width: ""                                          # (cánh đứng không có width)
height: "(H_total - TransomHeightTop - TransomHeightBottom) - OFFSET_FRAME"
qty: "n_panel"                                     # = 4 cánh
calc_pattern: LENGTH_TO_WEIGHT                     # ★ DATA-DRIVEN: eval calc_fn từ DB
cost_bucket: VL_NHOM
price_type: Item Price
price_base_item: NHOM-XINGFA                       # Item đại diện tra giá composite

# ── Ví dụ dòng kinh_canh ──
slug: kinh_canh
category: KINH                                    # → scrap_pct = 5%
item_code: KINH-LOWE-24
item_selection_mode: Fixed
width: "W_total/n_panel - OFFSET_GLASS"
height: "(H_total - TransomHeightTop - TransomHeightBottom) - OFFSET_GLASS"
qty: "n_panel"
calc_pattern: AREA                                 # ★ (w/1000)*(h/1000)
cost_bucket: VL_KINH
price_type: Fixed                                  # Kính dùng fixed price
default_glass_master: KINH-LOWE-24

# ── Ví dụ dòng nep_kinh_canh (★ Rule-based) ──
slug: nep_kinh_canh
category: NHOM
item_selection_mode: Rule ★                        # ★ Dynamic Item Rule
item_rule: RULE-NEP-GLASSTHICK                    # THRESHOLD: chọn nẹp theo glass_thick
rule_input_expr: "items.kinh_canh.glass_thick" ★  # ★ Cross-row reference
width: "2*(items.kinh_canh.width + items.kinh_canh.height)" ★
qty: "2 * n_panel"
calc_pattern: LENGTH_TO_WEIGHT
cost_bucket: VL_NHOM
price_type: Item Price
price_base_item: NHOM-XINGFA
```

### Bước 5: Định nghĩa Accessory Set (dùng lookup_rule)

```python
AL Accessory Set ACC-CDMQ-4C:
  tay_nam  | KL-MZS20    | qty=n_panel | qty_formula=""
  khoa     | KL-KHOA-01  | qty=1       | qty_formula=""
  ban_le   | KL-T-MJ06   | qty=0       | qty_formula="lookup_rule('RULE-BANLE-QTY', H_total) * n_panel" ★
  # RULE-BANLE-QTY: <2100→2, 2101-2700→4, >2700→4
  # H_total=3200 > 2700 → 4 bản lề/cánh × 4 cánh = 16 bản lề
```

### Bước 6: Định nghĩa Cost Template (dùng lookup_rule)

```python
AL Cost Template CT-01-STANDARD:
  TONG_VL   = VL_NHOM + VL_KINH + VL_VTP + VL_PK
  TONG_M2   = (W_total/1000)*(H_total/1000)
  NC_SX     = NC_SX_PCT * TONG_VL
  NC_LD     = NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m) ★
  TONG_NC   = NC_SX + NC_LD
  OH_VC     = OH_VC_PCT * TONG_VL
  OH_QLY    = OH_QLY_PCT * (TONG_VL + TONG_NC)
  TONG_OH   = OH_VC + OH_QLY
  GIA_THANH = TONG_VL + TONG_NC + TONG_OH
  PROFIT    = PROFIT_MARGIN * GIA_THANH
  GIA_BAN   = GIA_THANH + PROFIT
  DON_GIA_M2= GIA_BAN / TONG_M2
  VAT       = VAT_RATE * GIA_BAN
  GIA_VAT   = GIA_BAN + VAT
```

---

## 4. STEP-BY-STEP: BÁO GIÁ & TÍNH TOÁN

### Flow người dùng

```
1. Mở Quotation → chọn Khách hàng: "Công ty ABC"
2. Thêm dòng sản phẩm:
   - Item: CDMQ-4C (Item đại diện)
   - Qty: 2 bộ
   - AL BOM: BOM-CDMQ-4C
3. Bấm 📐 Tham số BOM → Dialog hiển thị:
   ┌────────────────────────────────────────────┐
   │ Tham số BOM — Cửa đi 4 cánh + vách kính    │
   │                                            │
   │ W_total:            [3600] mm              │
   │ H_total:            [3200] mm              │
   │ TransomHeightTop:   [600]  mm              │
   │ TransomHeightBottom:[400]  mm              │
   │ n_panel:            [4]                    │
   │ SideLiteWidth:      [800]  mm              │
   │ SideLiteHeight:     [2800] mm              │
   │ aluminum_color:     [DARK ▼]               │
   │ aluminum_origin:    [IMPORT ▼]             │
   │ aluminum_thickness: [20]                   │
   │ aluminum_surface:   [POWDER_COATED ▼]      │
   │ installation_height_m:[15]                 │
   │ glass_master:       [KINH-LOWE-24 ▼]       │
   │                                            │
   │ (System vars ẩn: OFFSET_FRAME=48,          │
   │  NC_SX_PCT=0.08, VAT_RATE=0.10...)         │
   │                                            │
   │       [💾 Lưu & Tính giá]                  │
   └────────────────────────────────────────────┘

4. Bấm 💾 Lưu & Tính giá → BomOrchestrator.run()
```

---

## 5. ENGINE FLOW CHI TIẾT

### B0: Version Pinning

```
Input: quotation_item_name = "QI-XXXX-001"
→ frappe.get_doc("Quotation Item", ...)           # KHÔNG cache (sẽ write sau)
→ al_bom = "BOM-CDMQ-4C"
→ frappe.get_cached_doc("AL BOM", ...)            # Redis cache 3600s
→ current_version = "BOM-CDMQ-4C-v1.0"
→ frappe.get_cached_doc("AL BOM Version", ...)
→ bom_version.bom_set_snapshot = JSON {...}        # parse 1 lần, dùng xuyên suốt
→ bom_version.cost_template_snapshot = JSON {...}
```

### B1: Gather Inputs — ★ DATA-DRIVEN System Variable Resolution

```python
# 1. User inputs từ al_bom_vars JSON → self.inputs:
{
  "W_total": 3600, "H_total": 3200,
  "n_panel": 4, "TransomHeightTop": 600, "TransomHeightBottom": 400,
  "SideLiteWidth": 800, "SideLiteHeight": 2800,
  "aluminum_color": "DARK", "aluminum_origin": "IMPORT",
  "aluminum_thickness": 20, "aluminum_surface": "POWDER_COATED",
  "installation_height_m": 15
}

# 2. Formula Global Variables:
VAT_RATE=0.10, OH_VC_PCT=0.03, OH_QLY_PCT=0.03

# 3. ★ Đọc AL Variable Library (is_system=1) → batch resolve:
system_vars = frappe.get_all("AL Variable Library",
    filters={"is_system": 1},
    fields=["var_name", "source_doctype", "source_field", "default_value"])

# Gom theo source_doctype:
# AL Profile System (XINGFA_55):
#   OFFSET_FRAME    = ps.offset_frame    = 48
#   OFFSET_GLASS    = ps.offset_glass    = 90
#   OFFSET_FIXED    = ps.offset_fixed    = 50
#   OFFSET_DO_NGANG = ps.offset_crossbar = 48
#
# AL Product Type (DOOR):
#   NC_SX_PCT       = pt.nc_pct          = 0.08
#   NC_LD_PCT       = pt.nc_ld_rate      = 0.12
#   PROFIT_MARGIN   = pt.profit_margin   = 0.16

# → self.inputs = {W_total:3600, ..., OFFSET_FRAME:48, NC_SX_PCT:0.08, ...}
```

### B2: Pre-fetch Master Data — ★ BATCH QUERIES

```python
# Gom tất cả codes:
item_codes = ["XF55-KB-20", "XF55-CANH-20", "KINH-LOWE-24", ...]

# ★ BATCH #1: Item weights (1 query cho tất cả)
weights = frappe.get_all("Item", {"name": ("in", item_codes)},
                         ["name", "weight_per_unit"])
# → {"XF55-KB-20": 1.257, "XF55-CANH-20": 1.350, ...}

# ★ BATCH #2: Item Prices (1 query cho tất cả)
prices = frappe.get_all("Item Price",
    {"item_code": ("in", all_price_items), "price_list": "Standard Selling"},
    ["item_code", "price_list_rate"])
# → {"XF55-KB-20": 113000, "NHOM-XINGFA": 113000, ...}

# ★ BATCH #3: Glass Masters (1 query, không N+1)
glass_masters = frappe.get_all("AL Glass Master",
    {"name": ("in", ["KINH-LOWE-24"])},
    ["name", "total_thick_mm", "glass_type"])
# → {"KINH-LOWE-24": {"glass_thick": 24, "glass_type": "LOWE"}}

# ★ BATCH #4: Material Categories (scrap_pct)
material_categories = frappe.get_all("AL Material Category",
    {"name": ("in", ["NHOM","KINH","VTP","PK"])},
    ["name", "default_scrap_pct"])
# → {"NHOM": 3, "KINH": 5, "VTP": 2, "PK": 0}

# ★ BATCH #5: Dynamic Item Rules (resolve nẹp, keo)
# Rule RULE-NEP-GLASSTHICK: input=24 → THRESHOLD 16.01-999 → "C3211-20"
# Rule RULE-KEO-GLASSTYPE:   input="LOWE" → LOOKUP → "KEO-TT-01"
# → resolved_items = {"RULE-NEP-GLASSTHICK": "C3211-20", "RULE-KEO-GLASSTYPE": "KEO-TT-01"}

# ★ Build row_literals cho TỪNG dòng (với scrap_pct):
# "khung_ngang_tren": {weight_per_unit:1.257, unit_price:113000,
#   calc_pattern:"LENGTH_TO_WEIGHT", scrap_pct:3, item_code:"XF55-KB-20"}
# "nep_kinh_canh":    {weight_per_unit:0.312, unit_price:113000,
#   calc_pattern:"LENGTH_TO_WEIGHT", scrap_pct:3,
#   item_code:"C3211-20"}  # ★ resolved từ RULE-NEP-GLASSTHICK
```

### B3: Build Formulas — ★ DATA-DRIVEN FIELDS

```python
# Đọc formula_fieldnames từ Bom Set config:
# → ["width","height","qty","show_condition","item_condition_formula","rule_input_expr"]

# Với mỗi item, build formulas:
# 1. Normalize cross-row reference: items.kinh_canh.width → kinh_canh__width
# 2. Tạo {slug}__{field} formula
# 3. Synthetic formulas: unit_qty, total_qty, line_total

# Ví dụ formulas cho khung_ngang_tren:
formulas = [
  {"name":"khung_ngang_tren__width",     "formula":"W_total"},       # = 3600
  {"name":"khung_ngang_tren__qty",       "formula":"1"},
  {"name":"khung_ngang_tren__unit_qty",  "formula":"lookup_calc_pattern(LENGTH_TO_WEIGHT, 3600, 0, 1.257)"},
  {"name":"khung_ngang_tren__total_qty", "formula":"khung_ngang_tren__unit_qty * 1"},
  {"name":"khung_ngang_tren__line_total","formula":"khung_ngang_tren__total_qty * 113000"},
]

# Ví dụ formulas cho canh_dung_c1:
formulas = [
  {"name":"canh_dung_c1__height","formula":"(H_total-TransomHeightTop-TransomHeightBottom)-OFFSET_FRAME"},
  # = (3200 - 600 - 400) - 48 = 2152
  {"name":"canh_dung_c1__qty",   "formula":"n_panel"},               # = 4
  ...
]

# ★ Context injection — scrap_pct từ Material Category:
self.inputs["khung_ngang_tren__scrap_pct"] = 3   # NHOM
self.inputs["kinh_canh__scrap_pct"]         = 5   # KINH
self.inputs["gioang__scrap_pct"]            = 2   # VTP
```

### B4: Calculate Bom Items — ★ FORMULA ENGINE + lookup_rule

```python
# FormulaEngine với DAG + topological sort
def _lookup_rule(rule_code, input_value=None):
    """★ DATA-DRIVEN: Tra cứu AL Calculation Rule"""
    rule = frappe.get_cached_doc("AL Calculation Rule", rule_code)
    return rule.resolve(input_value) or 0

engine = FormulaEngine(
    formulas=bom_formulas,        # ~100+ formulas cho 26 items
    safe_funcs={
        "lookup_calc_pattern": lookup_calc_pattern,  # ★ eval calc_fn từ DB
        "lookup_rule": _lookup_rule,                 # ★ Calculation Rule resolve
        "roundup": lambda x,y: math.ceil(x),
    },
    deterministic=True,
)

result = engine.calculate(self.inputs)

# ★ DAG tự động sắp xếp thứ tự tính:
# Bước 1: width, height (từ input vars)
# Bước 2: unit_qty (phụ thuộc width, height, calc_pattern)
# Bước 3: total_qty (phụ thuộc unit_qty, qty)
# Bước 4: line_total (phụ thuộc total_qty, unit_price)

# ★ Cross-row resolving:
# nep_kinh_canh__width = 2*(kinh_canh__width + kinh_canh__height)
# Engine đảm bảo kinh_canh__width được tính TRƯỚC nep_kinh_canh__width

# ★ lookup_calc_pattern gọi calc_fn lambda từ AL Quantity Calc Method:
# LENGTH_TO_WEIGHT: lambda w,h,tlr,**kw: (w/1000)*tlr
#   → khung_ngang_tren: (3600/1000)*1.257 = 4.525 kg
# AREA: lambda w,h,tlr,**kw: (w/1000)*(h/1000)
#   → kinh_canh: ((3600/4-90)/1000)*((3200-600-400-90)/1000)=0.810*2.110=1.709m²
```

### B5: Aggregate Cost Buckets

```python
# ★ DATA-DRIVEN: Gom line_total theo cost_bucket từ Bom Item
buckets = defaultdict(float)
for row in bom_result:
    buckets[row["cost_bucket"]] += row["line_total"]

# Kết quả:
# VL_NHOM: sum(tất cả dòng NHOM)
# VL_KINH: sum(tất cả dòng KINH)
# VL_VTP:  sum(tất cả dòng VTP)
# VL_PK:   sum(tất cả dòng PK) từ Accessory Set
```

### B6: Calculate Cost Template — ★ FLEXIBLE FORMULA ENGINE

```python
# FlexibleFormulaEngine với global_formulas từ Cost Template snapshot

# ★ lookup_rule được dùng trong formula:
# NC_LD = NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', 15)
#                                                     ↓
#                               RULE-HEIGHT-MULT: 15m → THRESHOLD → 1.2 ★

extra_context = {
    "VL_NHOM": 9628967, "VL_KINH": 13657860, "VL_VTP": 1442200, "VL_PK": 4070000,
    "W_total": 3600, "H_total": 3200,
    "NC_SX_PCT": 0.08, "NC_LD_PCT": 0.12, "PROFIT_MARGIN": 0.16,
    "OH_VC_PCT": 0.03, "OH_QLY_PCT": 0.03, "VAT_RATE": 0.10,
    "installation_height_m": 15,
}

# Engine tính theo DAG (từ Cost Template definition):
TONG_VL   = 9628967 + 13657860 + 1442200 + 4070000 = 28,799,027
TONG_M2   = (3600/1000)*(3200/1000)                = 11.520
NC_SX     = 0.08 * 28799027                        = 2,303,922
NC_LD     = 0.12 * 28799027 * 1.2 ★                = 4,147,060
TONG_NC   = 2303922 + 4147060                      = 6,450,982
OH_VC     = 0.03 * 28799027                        =   863,971
OH_QLY    = 0.03 * (28799027 + 6450982)            = 1,057,500
TONG_OH   = 863971 + 1057500                       = 1,921,471
GIA_THANH = 28799027 + 6450982 + 1921471           = 37,171,480
PROFIT    = 0.16 * 37171480                        = 5,947,437
GIA_BAN   = 37171480 + 5947437                     = 43,118,917
DON_GIA_M2= 43118917 / 11.520                      = 3,742,962
VAT       = 0.10 * 43118917                        = 4,311,892
GIA_VAT   = 43118917 + 4311892                     = 47,430,808 ★
```

### B7: Save Results — ★ SINGLE COMMIT

```python
# 1 set_value gộp 4 fields (Frappe tự gộp thành 1 UPDATE):
frappe.db.set_value("Quotation Item", qi_name, {
    "al_gia_vat": 47430808,
    "al_gia_ban": 43118917,
    "al_bom_result": json.dumps(full_result),
    "al_config_snapshot": snap_name,
})

# ConfigSnapshot qua ORM (không raw SQL):
frappe.get_doc({
    "doctype": "ConfigSnapshot",
    "bom_version": "BOM-CDMQ-4C-v1.0",
    "quotation_item_name": qi_name,
    "calculation_timestamp": "2026-08-03 14:30:00",
    "inputs_json": json.dumps(self.inputs),       # toàn bộ biến đầu vào
    "result_json": json.dumps(full_result),        # toàn bộ kết quả
}).insert()

# ★ 1 COMMIT duy nhất (thay vì 3 như v28.6)
frappe.db.commit()
```

---

## 6. KẾT QUẢ TÍNH TOÁN CỤ THỂ

Với input: W_total=3600, H_total=3200, n_panel=4, OFFSET_FRAME=48, OFFSET_GLASS=90, OFFSET_FIXED=50, OFFSET_DO_NGANG=48, TransomTop=600, TransomBot=400, SideLiteW=800, SideLiteH=2800

### 6.1 Chi tiết từng dòng Bom Item

```
┌─────────────────────┬────────────┬────────┬────────┬──────┬──────────┬──────────────┐
│ Slug                │ Item       │ Width  │ Height │ Qty  │ Unit Qty │ Line Total   │
├─────────────────────┼────────────┼────────┼────────┼──────┼──────────┼──────────────┤
│ khung_ngang_tren    │XF55-KB-20  │ 3600   │ -      │ 1    │ 4.525 kg │   511,348 VND│
│ khung_ngang_duoi    │XF55-KB-20  │ 3600   │ -      │ 1    │ 4.525 kg │   511,348 VND│
│ khung_dung_trai     │XF55-KB-20  │ 3200   │ -      │ 2    │ 4.022 kg │   909,062 VND│
│ khung_dung_phai     │XF55-KB-20  │ 3200   │ -      │ 2    │ 4.022 kg │   909,062 VND│
│ do_ngang_tren       │XF55-KB-20  │ 3504   │ -      │ 1    │ 4.405 kg │   497,712 VND│
│ do_ngang_duoi       │XF55-KB-20  │ 3504   │ -      │ 1    │ 4.405 kg │   497,712 VND│
│ canh_dung_c1..c4    │XF55-CANH-20│ 2152   │ -      │ 8    │ 2.905 kg │ 2,626,300 VND│
│ canh_ngang_c1..c4   │XF55-CANH-20│ 852    │ -      │ 8    │ 1.150 kg │ 1,039,780 VND│
│ kinh_fixed_top      │KINH-LOWE-24│ 3500   │ 550    │ 1    │ 1.925 m² │ 2,213,750 VND│
│ kinh_canh (×4)      │KINH-LOWE-24│ 810    │ 2110   │ 4    │ 1.709 m² │ 7,861,860 VND│
│ kinh_fixed_bottom   │KINH-LOWE-24│ 3500   │ 350    │ 1    │ 1.225 m² │ 1,408,750 VND│
│ kinh_sidelite       │KINH-LOWE-24│ 700    │ 2700   │ 1    │ 1.890 m² │ 2,173,500 VND│
│ nep_kinh_canh       │C3211-20    │ 5840   │ -      │ 8    │ 1.822 kg │ 1,647,160 VND│
│ nep_kinh_sidelite   │C3211-20    │ 6800   │ -      │ 2    │ 2.122 kg │   479,482 VND│
│ keo_canh            │KEO-TT-01   │ 5840   │ -      │ 4    │ 5.840 m  │ 1,051,200 VND│
│ keo_sidelite        │KEO-TT-01   │ 6800   │ -      │ 1    │ 6.800 m  │   306,000 VND│
│ gioang              │GIO-EPDM-55 │ 13600  │ -      │ 1    │13.600 m  │    17,000 VND│
│ vit                 │VIT-TK-35X16│ -      │ -      │ 80   │80 cái    │    68,000 VND│
│ tay_nam             │KL-MZS20    │ -      │ -      │ 4    │4 cái     │   840,000 VND│
│ khoa                │KL-KHOA-01  │ -      │ -      │ 1    │1 cái     │   350,000 VND│
│ ban_le              │KL-T-MJ06   │ -      │ -      │ 16   │16 cái    │ 2,880,000 VND│
└─────────────────────┴────────────┴────────┴────────┴──────┴──────────┴──────────────┘
★ = Item resolved từ Dynamic Item Rule (THRESHOLD/LOOKUP)
```

### 6.2 Cost Buckets

```
VL_NHOM = 9,628,967 VND  (khung + đố + cánh + nẹp)
VL_KINH = 13,657,860 VND (4 tấm kính)
VL_VTP  = 1,442,200 VND  (keo + gioăng + vít)
VL_PK   = 4,070,000 VND  (tay nắm 4×210K + khóa 350K + bản lề 16×180K)
```

### 6.3 Cost Template Chain (FULL)

```
TONG_VL    = 28,799,027 VND
TONG_M2    = 11.520 m²
NC_SX      = 0.08 × 28,799,027           = 2,303,922 VND
NC_LD      = 0.12 × 28,799,027 × 1.2★    = 4,147,060 VND
TONG_NC    = 2,303,922 + 4,147,060       = 6,450,982 VND
OH_VC      = 0.03 × 28,799,027           =   863,971 VND
OH_QLY     = 0.03 × (28,799,027+6,450,982)= 1,057,500 VND
TONG_OH    = 863,971 + 1,057,500         = 1,921,471 VND
GIA_THANH  = 28,799,027+6,450,982+1,921,471 = 37,171,480 VND
PROFIT     = 0.16 × 37,171,480           = 5,947,437 VND
GIA_BAN    = 37,171,480 + 5,947,437      = 43,118,917 VND
DON_GIA_M2 = 43,118,917 / 11.520         = 3,742,962 VND/m²
VAT        = 0.10 × 43,118,917           = 4,311,892 VND
GIA_VAT    = 43,118,917 + 4,311,892      = 47,430,808 VND ★
```

### 6.4 Hiệu ứng của Price Multiplier Chain

```
Nếu KHÔNG dùng multiplier_chain (exact_match mode):
  - Giá nhôm gốc (WHITE): 113,000 VND/kg
  - Với DARK: cần 1 Item Price record riêng cho MỌI tổ hợp
    (DARK+IMPORT+20μm+POWDER_COATED) → bùng nổ data

Với multiplier_chain (★ v28.7.1):
  - 1 base price record: NHOM-XINGFA = 113,000 VND/kg
  - DARK multiplier (từ AL Color Standard.price_multiplier): ×1.08
  - → Giá hiệu quả: 113,000 × 1.08 = 122,040 VND/kg
  - Nếu thêm ANODIZED surface ×1.15: 113,000 × 1.08 × 1.15 = 140,346 VND/kg
```

### 6.5 Hiệu ứng của Height Multiplier

```
installation_height_m = 3  (tầng trệt): NC_LD = 0.12 × 28,799,027 × 1.0 = 3,455,883 VND
installation_height_m = 15 (tầng 5):    NC_LD = 0.12 × 28,799,027 × 1.2 = 4,147,060 VND
installation_height_m = 45 (tầng 15):   NC_LD = 0.12 × 28,799,027 × 1.5 = 5,183,825 VND
→ Chênh lệch GIA_VAT giữa tầng trệt và tầng 15: ~2,270,000 VND
```

### 6.6 Hiệu ứng của Scrap/Waste

```
# Nếu áp dụng scrap vào qty formula:
# Không scrap: qty = 1 → line_total = 511,348 VND
# Với scrap NHOM 3%: qty = 1*(1+3/100) = 1.03 → line_total = 526,688 VND
# → Chênh lệch: +15,340 VND/dòng
```

---

## 7. SNAPSHOT & AUDIT TRAIL

### 7.1 BOM Version Snapshot (bom_set_snapshot)

```json
{
  "set_code": "BS-CDMQ-4C",
  "set_name": "Cửa đi 4 cánh + 2 transom + sidelite",
  "product_type": "DOOR",
  "profile_system": "XINGFA_55",
  "items": [
    {
      "slug": "canh_dung_c1",
      "category": "NHOM",
      "item_code": "XF55-CANH-20",
      "item_selection_mode": "Fixed",
      "width": "",
      "height": "(H_total-TransomHeightTop-TransomHeightBottom)-OFFSET_FRAME",
      "qty": "n_panel",
      "calc_pattern": "LENGTH_TO_WEIGHT",
      "cost_bucket": "VL_NHOM",
      "price_type": "Item Price",
      "price_base_item": "NHOM-XINGFA",
      "rule_input_expr": "",
      "show_condition": "",
      "item_condition_formula": "",
      "default_glass_master": null
    },
    {
      "slug": "nep_kinh_canh",
      "category": "NHOM",
      "item_selection_mode": "Rule",
      "item_rule": "RULE-NEP-GLASSTHICK",
      "rule_input_expr": "items.kinh_canh.glass_thick",
      "width": "2*(items.kinh_canh.width + items.kinh_canh.height)",
      "qty": "2*n_panel",
      ...
    }
  ]
}
```

**★ KEY POINT:** `_take_snapshots()` tự động đọc `frappe.get_meta("AL Bom Item")` → lấy mọi field có `fieldtype == "Small Text"` → copy vào snapshot. KHÔNG hardcode field list. Thêm Small Text field mới vào doctype → snapshot TỰ ĐỘNG include.

### 7.2 Cost Template Snapshot (cost_template_snapshot)

```json
{
  "template_code": "CT-01-STANDARD",
  "items": [
    {"line_code":"TONG_VL","calc_formula":"VL_NHOM+VL_KINH+VL_VTP+VL_PK"},
    {"line_code":"NC_LD","calc_formula":"NC_LD_PCT*TONG_VL*lookup_rule('RULE-HEIGHT-MULT',installation_height_m)"},
    {"line_code":"GIA_VAT","calc_formula":"GIA_BAN+VAT"}
  ]
}
```

### 7.3 ConfigSnapshot (★ immutable calculation record)

```json
{
  "name": "SNAP-abc123def456",
  "bom_version": "BOM-CDMQ-4C-v1.0",
  "quotation_item_name": "QI-XXXX-001",
  "calculation_timestamp": "2026-08-03T14:30:00",
  "inputs_json": {
    "W_total": 3600, "H_total": 3200, "n_panel": 4,
    "OFFSET_FRAME": 48, "OFFSET_GLASS": 90, "OFFSET_FIXED": 50,
    "NC_SX_PCT": 0.08, "PROFIT_MARGIN": 0.16, "VAT_RATE": 0.10,
    "installation_height_m": 15,
    "khung_ngang_tren__weight_per_unit": 1.257,
    "khung_ngang_tren__scrap_pct": 3,
    "khung_ngang_tren__unit_price": 113000
  },
  "result_json": {
    "buckets": {"VL_NHOM": 9628967, "VL_KINH": 13657860, "VL_VTP": 1442200, "VL_PK": 4070000},
    "cost_template": {"TONG_VL": 28799027, "NC_SX": 2303922, "NC_LD": 4147060, "GIA_VAT": 47430808},
    "lines": [
      {"slug":"khung_ngang_tren","item_code":"XF55-KB-20","width":3600,"line_total":511348},
      {"slug":"nep_kinh_canh","item_code":"C3211-20","width":5840,"line_total":1647160}
    ]
  }
}
```

**★ KEY POINT:** Mọi input + result được lưu immutable. Có thể tái lập tính toán bất kỳ lúc nào từ inputs_json. Audit trail đầy đủ.

---

## 8. MỞ RỘNG HỆ THỐNG

### 8.1 Thêm sản phẩm mới: Cửa sổ lùa 2 cánh

```
0 DÒNG CODE — tất cả qua UI:

1. AL Slug Library: thêm slug (canh_lua_tren, ray_truot...)
2. AL Variable Set VS-CSL-2C: chọn biến
3. AL Bom Set BS-CSL-2C: nhập Bom Items với công thức
4. AL BOM BOM-CSL-2C: link Bom Set + Cost Template
5. Publish BOM Version → Xong.
```

### 8.2 Thêm ngành mới: Cửa thép chống cháy

```
0 DÒNG CODE:

1. AL Material Category: THEP, has_weight=1, requires_price_base_item=1, default_scrap_pct=5
2. AL Slug Library: thêm slug (thep_hop_50x100, thep_tam_2ly...)
3. AL Quantity Calc Method: thêm VOLUME → lambda w,h,tlr,thickness,**kw: (w/1000)*(h/1000)*(thickness/1000)
4. AL Variable Library → Variable Set → Bom Set → BOM như trên
→ Xong.
```

### 8.3 Thêm đặc tính giá mới

```
0 DÒNG CODE:

1. AL Pricing Dimension: TECH_STANDARD, type=Select → auto-sinh custom_pd_TECH_STANDARD
2. AL Variable Library: thêm tech_standard
3. AL Variable Dimension Mapping: tech_standard → TECH_STANDARD → NHOM
→ Khi chọn tech_standard=EN, multiplier_chain tự động áp dụng
```

---

## TỔNG KẾT

Ví dụ trên minh họa **TOÀN BỘ 14 tính năng** của AlumGlass v28.7.1:

| # | Tính năng | Demo |
|---|---|---|
| 1 | Variable Library → Set | 13 user + 10 system vars |
| 2 | System Variables (source_doctype/source_field) | OFFSET, NC, PROFIT resolve tự động |
| 3 | Dynamic BOM formula fields | 26 Bom Items × 6 formula fields |
| 4 | Cross-row reference (items.X.Y) | nẹp/keo tham chiếu kính |
| 5 | lookup_calc_pattern (DATA-DRIVEN) | 4 patterns eval từ DB lambda |
| 6 | Dynamic Item Rule (THRESHOLD/LOOKUP) | Nẹp/keo theo glass_thick/type |
| 7 | lookup_rule (Calculation Rule) | Bản lề theo H, NC theo độ cao |
| 8 | Price Multiplier Chain | DARK ×1.08 |
| 9 | Composite Key Pricing | Tra giá nhôm 4 chiều |
| 10 | Scrap/Waste Injection | NHOM 3%, KINH 5% |
| 11 | Cost Template (FlexibleFormulaEngine) | 14 dòng → GIA_VAT |
| 12 | BOM Version Snapshot (dynamic) | Auto-copy mọi Small Text field |
| 13 | ConfigSnapshot | Immutable inputs + results |
| 14 | Accessory Set với qty_formula | lookup_rule('RULE-BANLE-QTY', H) |

**Số dòng code cần viết để tạo sản phẩm này: 0**

Tất cả đều qua UI, DB config. Engine tự động resolve variable, batch query, DAG evaluate.
