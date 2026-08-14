# AlumGlass Formula Builder — Công thức tính giá ngành Nhôm Kính

> **Pattern:** `formulas → FormulaEngine(context) → result` (giống hệt các ví dụ `formula_builder`)

## Cách dùng cơ bản

```python
from formula_builder.formula_utils import FormulaEngine
from alumglass.formula_builder.templates import (
    FORMULAS_KHUNG_DUNG, FORMULAS_COST_TEMPLATE,
    build_glass_formulas, build_bucket_formulas,
    ALUMINUM_PRICE_TABLE, GLASS_PRICE_TABLE,
)

# 1. Định nghĩa formulas (ghép từ các bộ có sẵn)
formulas = []
formulas.extend(FORMULAS_KHUNG_DUNG)
formulas.extend(build_glass_formulas("kinh_canh", "W_mm - 86", "H_mm - 86"))
formulas.extend(build_bucket_formulas({"VL_NHOM": ["khung_dung_tt"], "VL_KINH": ["kinh_canh_tt"]}))
formulas.extend(FORMULAS_COST_TEMPLATE)

# 2. Tạo engine
engine = FormulaEngine(formulas=formulas, on_error="raise", default_value=0)

# 3. Tạo context (inputs dict)
ctx = {
    "W_mm": 1200, "H_mm": 2200, "W_m": 1.2, "H_m": 2.2,
    "qty": 1, "n_canh": 2,
    "don_gia_nhom": 113000,
    "khung_dung_kg_per_m": 1.257,
    "glass_thick_kinh_canh": 10.0,
    "TONG_M2": 2.64,
    "nc_sx_pct": 0.12, "nc_ld_rate": 180000,
    "oh_hh_pct": 0.02, "oh_vc_pct": 0.03,
    "oh_bh_pct": 0.01, "profit_pct": 0.15, "vat_pct": 0.10,
}

# 4. Tính toán
result = engine.calculate(ctx)
print(result["GIA_BAN"])     # → giá bán
print(result["DON_GIA_M2"])  # → đơn giá / m²

# 5. Giải thích
expl = engine.explain("GIA_BAN", ctx)
print(expl.to_text())  # → chuỗi tính toán đầy đủ
```

## Các bộ công thức có sẵn

| Bộ công thức | Mô tả |
|---|---|
| `FORMULAS_KHUNG_DUNG`, `_NGANG`, `_CANH_DUNG`, `_CANH_NGANG`, `_NEP` | Công thức tính số lượng + thành tiền profile nhôm |
| `build_glass_formulas(prefix, W, H, ...)` | Công thức tính kính (hỗ trợ multi-panel) |
| `build_bucket_formulas({bucket: [vars]})` | Gom biến thành tiền vào cost buckets |
| `FORMULAS_COST_TEMPLATE` | Từ buckets → GIA_THANH → GIA_BAN → GIA_VAT |
| `FORMULAS_PROJECT` | Tổng hợp giá thành toàn dự án |
| `FORMULAS_COST_VARIANCE` | Phân tích biến động ước tính vs thực tế |
| `FORMULAS_CUTTING_NHOM` / `_KINH` | Tối ưu cắt nhôm (1D) & kính (2D) |

## Tiện ích (pure functions)

```python
from alumglass.formula_utils import (
    quick_quote,          # Báo giá nhanh không cần Engine/DB
    lookup_aluminum_price, # Tra đơn giá nhôm (brand, màu)
    lookup_glass_price,    # Tra đơn giá kính (glass_code)
    glass_area_m2,         # Diện tích kính từ mm
    aluminum_cut_efficiency, # Hiệu suất cắt nhôm
    analyze_margin,        # Phân tích biên lợi nhuận
    fmt_vnd,               # Format tiền VND
)
```

## Ví dụ

```bash
cd /home/lengoc/frappe-bench/apps
PYTHONPATH=.:alumglass:formula_builder python3 alumglass/alumglass/formula_builder/examples/01_bao_gia.py
PYTHONPATH=.:alumglass:formula_builder python3 alumglass/alumglass/formula_builder/examples/02_giathanh.py
PYTHONPATH=.:alumglass:formula_builder python3 alumglass/alumglass/formula_builder/examples/03_du_toan.py
```

## Cấu trúc files

```
alumglass/alumglass/
├── formula_builder/
│   ├── templates.py       ← TẤT CẢ công thức mẫu (chỉ là list dicts)
│   ├── __init__.py
│   ├── README.md
│   └── examples/
│       ├── 01_bao_gia.py      ← Báo giá + so sánh phương án
│       ├── 02_giathanh.py     ← Giá thành dự án + Cost Variance + mass test
│       └── 03_du_toan.py      ← Dự toán công trình + Cutting Plan + Explain
│
└── formula_utils/
    ├── calculations.py    ← Pure functions (lookup, quick_quote, format...)
    ├── validators.py      ← Validate kích thước, kính, profile
    └── __init__.py
```
