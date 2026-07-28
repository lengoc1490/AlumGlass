# MultiTableFormulaBuilder — Ví Dụ Toàn Diện

> **File:** `/alumglass/docs/multi_table_formula_builder_examples.md`
> **Phiên bản:** v28.5 — 2026-07-28
> **Tài liệu gốc:** `formula_builder/table_formula_builder.py`

---

## Mục lục

1. [Giới thiệu](#1-giới-thiệu)
2. [Ví dụ 1: Cơ bản — 1 bảng, 1 formula/row](#2-ví-dụ-1-cơ-bản--1-bảng-1-formularow)
3. [Ví dụ 2: 1 bảng, nhiều formula/row + literal injection](#3-ví-dụ-2-1-bảng-nhiều-formularow--literal-injection)
4. [Ví dụ 3: Nhiều bảng, cross-table reference](#4-ví-dụ-3-nhiều-bảng-cross-table-reference)
5. [Ví dụ 4: Synthetic formulas](#5-ví-dụ-4-synthetic-formulas)
6. [Ví dụ 5: Custom formula_builder override](#6-ví-dụ-5-custom-formula_builder-override)
7. [Ví dụ 6: Hybrid — builder + tự code](#7-ví-dụ-6-hybrid--builder--tự-code)
8. [Ví dụ 7: Cost Template AlumGlass](#8-ví-dụ-7-cost-template-alumglass)
9. [Ví dụ 8: Invoice + Tax (ngành kế toán)](#9-ví-dụ-8-invoice--tax-ngành-kế-toán)
10. [Ví dụ 9: Payroll (ngành nhân sự)](#10-ví-dụ-9-payroll-ngành-nhân-sự)
11. [Ví dụ 10: End-to-End — Full BOM AlumGlass 3 bảng](#11-ví-dụ-10-end-to-end--full-bom-alumglass-3-bảng)
12. [Bảng tổng hợp pattern](#12-bảng-tổng-hợp-pattern)

---

## 1. Giới thiệu

`MultiTableFormulaBuilder` là utility generic của Formula Builder, giúp tự động tạo
`List[{"name":..., "formula":...}]` + context từ dữ liệu có cấu trúc dạng bảng.

**Không gắn với BOM hay ngành cụ thể.** Dùng cho mọi bài toán: nhôm kính, may mặc,
hóa đơn, bảng lương, dự toán, kế hoạch sản xuất...

```python
from formula_builder.integration import MultiTableFormulaBuilder
```

---

## 2. Ví dụ 1: Cơ bản — 1 bảng, 1 formula/row

### Scenario
Bảng `items` có các dòng hàng. Mỗi dòng có 1 công thức `amount`. Context có sẵn `TAX_RATE`.

### Code

```python
from formula_builder.integration import MultiTableFormulaBuilder

# Dữ liệu
rows = [
    {"line_ref": "L1", "amount": "qty * unit_price"},
    {"line_ref": "L2", "amount": "qty * unit_price * (1 + TAX_RATE)"},
    {"line_ref": "L3", "amount": "100 + 50"},
]

builder = MultiTableFormulaBuilder(normalize_mode="global")
builder.add_table(
    table_name="items",
    rows=rows,
    formula_fields=["amount"],
    id_field="line_ref",
    literal_fields=["qty", "unit_price"],
)

formulas, context = builder.build(
    base_context={"TAX_RATE": 0.1, "qty": 10, "unit_price": 200}
)
```

### Kết quả `formulas`

```python
[
    {"name": "L1__amount", "formula": "qty * unit_price"},
    {"name": "L2__amount", "formula": "qty * unit_price * (1 + TAX_RATE)"},
    {"name": "L3__amount", "formula": "100 + 50"},
]
```

### Kết quả `context`

```python
{
    "TAX_RATE": 0.1,
    "qty": 10,
    "unit_price": 200,
    # NOTE: L1__qty, L1__unit_price NOT injected because "qty" and "unit_price"
    # are formula_fields' values, not literal_fields. They're formula variables.
    # Only literal_fields values get injected into context with prefix.
}
```

### Chạy Engine

```python
from formula_builder.formula_utils import FormulaEngine

engine = FormulaEngine(formulas=formulas)
result = engine.calculate(context)
# result = {"L1__amount": 2000, "L2__amount": 2200, "L3__amount": 150}
```

---

## 3. Ví dụ 2: 1 bảng, nhiều formula/row + literal injection

### Scenario
Bảng `materials` — mỗi dòng có 3 công thức: `width`, `height`, `qty`.
Cần inject `unit_price` và `weight_per_unit` làm literal để synthetic formulas dùng.

### Code

```python
rows = [
    {
        "slug": "panel_A",
        "width": "W_mm - 2*OFFSET",
        "height": "H_mm - OFFSET",
        "qty": "n_panel",
        "unit_price": 1150000,
        "weight_per_unit": 1.257,
    },
    {
        "slug": "panel_B",
        "width": "W_mm/2 - OFFSET",
        "height": "H_mm - 100",
        "qty": "2",
        "unit_price": 850000,
        "weight_per_unit": 1.350,
    },
]

builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table(
    table_name="materials",
    rows=rows,
    formula_fields=["width", "height", "qty"],
    literal_fields=["unit_price", "weight_per_unit"],
    id_field="slug",
)

formulas, context = builder.build(
    base_context={"W_mm": 2400, "H_mm": 2600, "OFFSET": 50, "n_panel": 2}
)
```

### Kết quả `formulas`

```python
[
    {"name": "materials__panel_A__width",  "formula": "W_mm - 2*OFFSET"},
    {"name": "materials__panel_A__height", "formula": "H_mm - OFFSET"},
    {"name": "materials__panel_A__qty",    "formula": "n_panel"},
    {"name": "materials__panel_B__width",  "formula": "W_mm/2 - OFFSET"},
    {"name": "materials__panel_B__height", "formula": "H_mm - 100"},
    {"name": "materials__panel_B__qty",    "formula": "2"},
]
```

### Kết quả `context`

```python
{
    "W_mm": 2400, "H_mm": 2600, "OFFSET": 50, "n_panel": 2,
    "materials__panel_A__unit_price": 1150000,
    "materials__panel_A__weight_per_unit": 1.257,
    "materials__panel_B__unit_price": 850000,
    "materials__panel_B__weight_per_unit": 1.350,
}
```

---

## 4. Ví dụ 3: Nhiều bảng, cross-table reference

### Scenario
Bảng `profiles` (nhôm) và `glasses` (kính). Dòng `nep_kinh` trong profiles
tham chiếu đến kích thước của `panel_top` trong glasses.

### Code

```python
profile_rows = [
    {"slug": "frame",    "width": "W_mm", "qty": "2"},
    {"slug": "nep_kinh", "width": "2*(glasses.panel_top.width + glasses.panel_top.height)", "qty": "2"},
]

glass_rows = [
    {"slug": "panel_top", "width": "W_mm - 100", "height": "TransomH - 50", "qty": "1"},
]

builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table(
    table_name="profiles",
    rows=profile_rows,
    formula_fields=["width", "qty"],
    id_field="slug",
)
builder.add_table(
    table_name="glasses",
    rows=glass_rows,
    formula_fields=["width", "height", "qty"],
    id_field="slug",
)

formulas, context = builder.build(
    base_context={"W_mm": 2400, "TransomH": 600}
)
```

### Kết quả `formulas`

```python
[
    # profiles
    {"name": "profiles__frame__width",    "formula": "W_mm"},
    {"name": "profiles__frame__qty",      "formula": "2"},
    {"name": "profiles__nep_kinh__width", "formula": "2*(glasses__panel_top__width + glasses__panel_top__height)"},
    {"name": "profiles__nep_kinh__qty",   "formula": "2"},
    # glasses
    {"name": "glasses__panel_top__width",  "formula": "W_mm - 100"},
    {"name": "glasses__panel_top__height", "formula": "TransomH - 50"},
    {"name": "glasses__panel_top__qty",    "formula": "1"},
]
```

### Engine DAG tự động

```
profiles__nep_kinh__width PHỤ THUỘC:
  ├── glasses__panel_top__width
  └── glasses__panel_top__height

→ Engine tự động tính glasses trước, profiles__nep_kinh sau.

Kết quả:
  glasses__panel_top__width  = 2400 - 100 = 2300
  glasses__panel_top__height = 600 - 50   = 550
  profiles__nep_kinh__width  = 2*(2300 + 550) = 5700
```

---

## 5. Ví dụ 4: Synthetic formulas

### Scenario
Bảng `profiles` cần sinh thêm 3 formulas tự động: `unit_qty`, `total_qty`, `line_total`.
Dùng callback có sẵn `synthetic_for_pattern`.

### Code

```python
from formula_builder.integration import (
    MultiTableFormulaBuilder,
    synthetic_for_pattern,
)

rows = [
    {
        "slug": "frame",
        "width": "W_mm",
        "qty": "2",
        "unit_price": 113000,
        "calc_pattern": "LENGTH_TO_WEIGHT",
        "weight_per_unit": 1.257,
    },
]

builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table(
    table_name="profiles",
    rows=rows,
    formula_fields=["width", "qty"],
    literal_fields=["unit_price", "calc_pattern", "weight_per_unit"],
    id_field="slug",
    synthetic_formulas=synthetic_for_pattern,
)

formulas, context = builder.build(base_context={"W_mm": 2400})
```

### Kết quả `formulas`

```python
[
    # Từ formula_fields
    {"name": "profiles__frame__width",  "formula": "W_mm"},
    {"name": "profiles__frame__qty",    "formula": "2"},
    # Từ synthetic_formulas callback
    {"name": "profiles__frame__unit_qty",
     "formula": "lookup_calc_pattern(profiles__frame__calc_pattern, profiles__frame__width, profiles__frame__height, profiles__frame__weight_per_unit, 1, 1, 1, 1)"},
    {"name": "profiles__frame__total_qty",
     "formula": "profiles__frame__unit_qty * (profiles__frame__qty or 1)"},
    {"name": "profiles__frame__line_total",
     "formula": "profiles__frame__total_qty * (profiles__frame__unit_price or 0)"},
]
```

### Custom synthetic callback

```python
def my_glass_synthetic(builder, table_name, slug, row, context, var_prefix, **kwargs):
    """Tự tính diện tích + thành tiền cho kính."""
    return [
        {
            "name": f"{var_prefix}__area_m2",
            "formula": f"({var_prefix}__width/1000) * ({var_prefix}__height/1000)",
        },
        {
            "name": f"{var_prefix}__line_total",
            "formula": (
                f"{var_prefix}__area_m2 * "
                f"({var_prefix}__qty or 1) * "
                f"({var_prefix}__unit_price or 0)"
            ),
        },
    ]

builder.add_table(
    table_name="glasses",
    rows=glass_rows,
    formula_fields=["width", "height", "qty"],
    literal_fields=["unit_price"],
    id_field="slug",
    synthetic_formulas=my_glass_synthetic,
)
```

### Kết quả `formulas` (với custom callback)

```python
[
    {"name": "glasses__panel_top__width",     "formula": "W_mm - 100"},
    {"name": "glasses__panel_top__height",    "formula": "TransomH - 50"},
    {"name": "glasses__panel_top__qty",       "formula": "1"},
    # Từ custom callback:
    {"name": "glasses__panel_top__area_m2",
     "formula": "(glasses__panel_top__width/1000) * (glasses__panel_top__height/1000)"},
    {"name": "glasses__panel_top__line_total",
     "formula": "glasses__panel_top__area_m2 * (glasses__panel_top__qty or 1) * (glasses__panel_top__unit_price or 0)"},
]
```

---

## 6. Ví dụ 5: Custom formula_builder override

### Scenario
Bảng `taxes` có logic quá phức tạp, không theo pattern chuẩn → override toàn bộ.

### Code

```python
def build_taxes_manually(builder, table_name, rows, context):
    """Logic tính thuế phức tạp: tra DB, tính theo region."""
    formulas = []
    for row in rows:
        # Logic đặc biệt không thể khai báo declarative
        region = row.get("region", "DEFAULT")
        rate = 0.1 if region == "DOMESTIC" else 0.05
        formulas.append({
            "name": f"TAX_{row['code']}",
            "formula": f"{rate} * SUBTOTAL",
        })
    return formulas

tax_rows = [
    {"code": "VAT", "region": "DOMESTIC"},
    {"code": "GST", "region": "EXPORT"},
]

builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table(
    table_name="taxes",
    rows=tax_rows,
    formula_builder=build_taxes_manually,  # ← Override toàn bộ
    # Không cần formula_fields, literal_fields, synthetic_formulas
)

formulas, context = builder.build(base_context={"SUBTOTAL": 1000000})
```

### Kết quả `formulas`

```python
[
    {"name": "TAX_VAT", "formula": "0.1 * SUBTOTAL"},
    {"name": "TAX_GST", "formula": "0.05 * SUBTOTAL"},
]
```

---

## 7. Ví dụ 6: Hybrid — builder + tự code

### Scenario
80% bảng dùng builder, 20% phức tạp → merge thủ công.

### Code

```python
builder = MultiTableFormulaBuilder(normalize_mode="scoped")

# 80% chuẩn: dùng builder
builder.add_table(
    table_name="profiles",
    rows=profile_rows,
    formula_fields=["width", "qty"],
    literal_fields=["unit_price"],
    id_field="slug",
)
builder.add_table(
    table_name="glasses",
    rows=glass_rows,
    formula_fields=["width", "height", "qty"],
    literal_fields=["unit_price"],
    id_field="slug",
)

# Build phần chuẩn
formulas, context = builder.build(base_context=inputs)

# 20% đặc biệt: tự code thêm formulas
custom_formulas = [
    {"name": "SPECIAL_DISCOUNT", "formula": "IF(TONG_VL > 10000000, 0.05, 0.02) * TONG_VL"},
    {"name": "FINAL_TOTAL", "formula": "TONG_VL - SPECIAL_DISCOUNT + TONG_NC + TONG_OH"},
]

# Merge
formulas.extend(custom_formulas)

from formula_builder.formula_utils import FormulaEngine
engine = FormulaEngine(formulas=formulas)
result = engine.calculate(context)
```

### Kết quả `formulas` (phần merge)

```python
[
    # ... formulas từ builder (profiles + glasses) ...
    {"name": "SPECIAL_DISCOUNT", "formula": "IF(TONG_VL > 10000000, 0.05, 0.02) * TONG_VL"},
    {"name": "FINAL_TOTAL", "formula": "TONG_VL - SPECIAL_DISCOUNT + TONG_NC + TONG_OH"},
]
```

---

## 8. Ví dụ 7: Cost Template AlumGlass

### Scenario
14 dòng Cost Template, mỗi dòng 1 công thức. Biến đến từ context đã được resolve sẵn.

### Code

```python
cost_template_lines = [
    {"line_code": "TONG_VL",     "calc_formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK"},
    {"line_code": "TONG_M2",     "calc_formula": "(W_mm/1000)*(H_mm/1000)"},
    {"line_code": "NC_SX",       "calc_formula": "NC_SX_PCT * TONG_VL"},
    {"line_code": "NC_LD",       "calc_formula": "NC_LD_PCT * TONG_VL"},
    {"line_code": "TONG_NC",     "calc_formula": "NC_SX + NC_LD"},
    {"line_code": "OH_VC",       "calc_formula": "OH_VC_PCT * TONG_VL"},
    {"line_code": "OH_QLY",      "calc_formula": "OH_QLY_PCT * (TONG_VL + TONG_NC)"},
    {"line_code": "TONG_OH",     "calc_formula": "OH_VC + OH_QLY"},
    {"line_code": "GIA_THANH",   "calc_formula": "TONG_VL + TONG_NC + TONG_OH"},
    {"line_code": "PROFIT",      "calc_formula": "PROFIT_MARGIN * GIA_THANH"},
    {"line_code": "GIA_BAN",     "calc_formula": "GIA_THANH + PROFIT"},
    {"line_code": "DON_GIA_M2",  "calc_formula": "GIA_BAN / TONG_M2"},
    {"line_code": "VAT",         "calc_formula": "VAT_RATE * GIA_BAN"},
    {"line_code": "GIA_VAT",     "calc_formula": "GIA_BAN + VAT"},
]

# normalize_mode="global" để giữ tên biến ngắn (TONG_VL thay vì cost_template__TONG_VL)
builder = MultiTableFormulaBuilder(normalize_mode="global")
builder.add_table(
    table_name="cost_template",
    rows=cost_template_lines,
    formula_fields=["calc_formula"],
    id_field="line_code",
    # Không literal_fields — tất cả biến đã có trong base_context
    # Không synthetic_formulas — Cost Template thuần túy
)

cost_context = {
    "VL_NHOM": 4895431, "VL_KINH": 6330980, "VL_VTP": 836400, "VL_PK": 2000000,
    "NC_SX_PCT": 0.08, "NC_LD_PCT": 0.12,
    "OH_VC_PCT": 0.03, "OH_QLY_PCT": 0.03,
    "PROFIT_MARGIN": 0.16, "VAT_RATE": 0.10,
    "W_mm": 2400, "H_mm": 2600,
}

formulas, context = builder.build(base_context=cost_context)
```

### Kết quả `formulas`

```python
[
    {"name": "TONG_VL__calc_formula",     "formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK"},
    {"name": "TONG_M2__calc_formula",     "formula": "(W_mm/1000)*(H_mm/1000)"},
    {"name": "NC_SX__calc_formula",       "formula": "NC_SX_PCT * TONG_VL"},
    {"name": "NC_LD__calc_formula",       "formula": "NC_LD_PCT * TONG_VL"},
    {"name": "TONG_NC__calc_formula",     "formula": "NC_SX + NC_LD"},
    {"name": "OH_VC__calc_formula",       "formula": "OH_VC_PCT * TONG_VL"},
    {"name": "OH_QLY__calc_formula",      "formula": "OH_QLY_PCT * (TONG_VL + TONG_NC)"},
    {"name": "TONG_OH__calc_formula",     "formula": "OH_VC + OH_QLY"},
    {"name": "GIA_THANH__calc_formula",   "formula": "TONG_VL + TONG_NC + TONG_OH"},
    {"name": "PROFIT__calc_formula",      "formula": "PROFIT_MARGIN * GIA_THANH"},
    {"name": "GIA_BAN__calc_formula",     "formula": "GIA_THANH + PROFIT"},
    {"name": "DON_GIA_M2__calc_formula",  "formula": "GIA_BAN / TONG_M2"},
    {"name": "VAT__calc_formula",         "formula": "VAT_RATE * GIA_BAN"},
    {"name": "GIA_VAT__calc_formula",     "formula": "GIA_BAN + VAT"},
]
```

> **Lưu ý:** Tên formula là `{line_code}__calc_formula` vì `id_field="line_code"` và `formula_fields=["calc_formula"]`.
> Nếu muốn tên ngắn hơn (VD: `TONG_VL` thay vì `TONG_VL__calc_formula`), có thể dùng `formula_builder` override
> hoặc tự build formulas như code gốc trong v28.md C.3.1.

---

## 9. Ví dụ 8: Invoice + Tax (ngành kế toán)

### Scenario
Hóa đơn có 2 bảng con: `invoice_items` và `tax_lines`. Cần tính dòng hàng → subtotal → thuế → total.

### Code

```python
invoice_items = [
    {"slug": "ITEM01", "line_total": "qty * unit_price", "qty": 10, "unit_price": 50000},
    {"slug": "ITEM02", "line_total": "qty * unit_price * (1 - discount)", "qty": 5, "unit_price": 120000, "discount": 0.1},
    {"slug": "ITEM03", "line_total": "qty * unit_price", "qty": 2, "unit_price": 250000},
]

tax_lines = [
    {"code": "VAT",  "tax_amount": "TAX_RATE_VAT * SUBTOTAL",  "TAX_RATE_VAT": 0.10},
    {"code": "PIT",  "tax_amount": "TAX_RATE_PIT * SUBTOTAL",  "TAX_RATE_PIT": 0.05},
]

builder = MultiTableFormulaBuilder(normalize_mode="scoped")

builder.add_table(
    table_name="invoice_items",
    rows=invoice_items,
    formula_fields=["line_total"],
    literal_fields=["qty", "unit_price", "discount"],
    id_field="slug",
)

builder.add_table(
    table_name="tax_lines",
    rows=tax_lines,
    formula_fields=["tax_amount"],
    literal_fields=["TAX_RATE_VAT", "TAX_RATE_PIT"],
    id_field="code",
)

formulas, context = builder.build(base_context={"SUBTOTAL": 1000000})

# Merge synthetic: SUBTOTAL = SUM các line
def build_subtotal(builder, table_name, rows, context):
    refs = []
    for row in rows:
        refs.append(f"{builder.get_var_ref(table_name, row['slug'], 'line_total')}")
    return [{"name": "SUBTOTAL_CALC", "formula": " + ".join(refs)}]

# Hoặc tự thêm thủ công:
formulas.append({"name": "GRAND_TOTAL",
                  "formula": "SUBTOTAL + invoice_items__VAT__tax_amount + invoice_items__PIT__tax_amount"})
```

### Kết quả `formulas`

```python
[
    {"name": "invoice_items__ITEM01__line_total", "formula": "qty * unit_price"},
    {"name": "invoice_items__ITEM02__line_total", "formula": "qty * unit_price * (1 - discount)"},
    {"name": "invoice_items__ITEM03__line_total", "formula": "qty * unit_price"},
    {"name": "tax_lines__VAT__tax_amount", "formula": "TAX_RATE_VAT * SUBTOTAL"},
    {"name": "tax_lines__PIT__tax_amount", "formula": "TAX_RATE_PIT * SUBTOTAL"},
    {"name": "GRAND_TOTAL", "formula": "SUBTOTAL + invoice_items__VAT__tax_amount + invoice_items__PIT__tax_amount"},
]
```

---

## 10. Ví dụ 9: Payroll (ngành nhân sự)

### Scenario
Bảng lương có `salary_lines` (lương cơ bản, phụ cấp, thưởng) và `deduction_lines` (bảo hiểm, thuế).

### Code

```python
salary_rows = [
    {"code": "BASIC",    "amount": "BASE_SALARY", "BASE_SALARY": 15000000},
    {"code": "ALLOWANCE","amount": "BASE_SALARY * ALLOWANCE_RATE", "ALLOWANCE_RATE": 0.15},
    {"code": "BONUS",    "amount": "BASE_SALARY * BONUS_RATE", "BONUS_RATE": 0.20},
]

deduction_rows = [
    {"code": "SI",  "amount": "GROSS * SI_RATE", "SI_RATE": 0.08},
    {"code": "HI",  "amount": "GROSS * HI_RATE", "HI_RATE": 0.015},
    {"code": "UI",  "amount": "GROSS * UI_RATE", "UI_RATE": 0.01},
    {"code": "PIT", "amount": "(GROSS - DEDUCTION_BEFORE_TAX) * PIT_RATE", "PIT_RATE": 0.10},
]

builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table(
    table_name="salary_lines",
    rows=salary_rows,
    formula_fields=["amount"],
    literal_fields=["BASE_SALARY", "ALLOWANCE_RATE", "BONUS_RATE"],
    id_field="code",
)
builder.add_table(
    table_name="deduction_lines",
    rows=deduction_rows,
    formula_fields=["amount"],
    literal_fields=["SI_RATE", "HI_RATE", "UI_RATE", "PIT_RATE"],
    id_field="code",
)

# Tự thêm các synthetic global formulas
formulas, context = builder.build(base_context={})

# GROSS = sum of salary lines
salary_refs = [f"salary_lines__{r['code']}__amount" for r in salary_rows]
formulas.append({"name": "GROSS", "formula": " + ".join(salary_refs)})

# DEDUCTION_BEFORE_TAX = SI + HI + UI
deduction_refs = [f"deduction_lines__{r['code']}__amount" for r in deduction_rows[:3]]
formulas.append({"name": "DEDUCTION_BEFORE_TAX", "formula": " + ".join(deduction_refs)})

# NET = GROSS - all deductions
all_deductions = [f"deduction_lines__{r['code']}__amount" for r in deduction_rows]
formulas.append({"name": "NET_SALARY", "formula": f"GROSS - ({' + '.join(all_deductions)})"})
```

### Kết quả `formulas` (phần tự thêm)

```python
[
    # ... salary_lines + deduction_lines từ builder ...
    {"name": "GROSS",
     "formula": "salary_lines__BASIC__amount + salary_lines__ALLOWANCE__amount + salary_lines__BONUS__amount"},
    {"name": "DEDUCTION_BEFORE_TAX",
     "formula": "deduction_lines__SI__amount + deduction_lines__HI__amount + deduction_lines__UI__amount"},
    {"name": "NET_SALARY",
     "formula": "GROSS - (deduction_lines__SI__amount + deduction_lines__HI__amount + deduction_lines__UI__amount + deduction_lines__PIT__amount)"},
]
```

---

## 11. Ví dụ 10: End-to-End — Full BOM AlumGlass 3 bảng

### Scenario
Tính giá cửa nhôm CDMQ-2C-TRANSOM: profiles (nhôm) + glasses (kính) + accessories (phụ kiện).

### Input

```python
base_inputs = {
    "W_mm": 2400, "H_mm": 2600,
    "TransomHeight_mm": 600, "n_panel": 2,
    "OFFSET_FRAME": 48, "OFFSET_GLASS": 90,
    "OFFSET_FIXED": 50, "OFFSET_DO_NGANG": 48,
    "aluminum_color": "WHITE", "aluminum_origin": "IMPORT",
}
```

### Code đầy đủ

```python
from formula_builder.integration import (
    MultiTableFormulaBuilder,
    synthetic_for_pattern,
    build_engine_from_builder,
)

builder = MultiTableFormulaBuilder(normalize_mode="scoped")

# ─── Bảng 1: Profiles (nhôm) ───
builder.add_table(
    table_name="profiles",
    rows=[
        {"slug": "khung_ngang_tren","width": "W_mm", "qty": "1",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 1.257},
        {"slug": "khung_ngang_duoi","width": "W_mm", "qty": "1",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 1.257},
        {"slug": "khung_dung",      "width": "H_mm", "qty": "2",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 1.257},
        {"slug": "do_ngang",        "width": "W_mm - 2*OFFSET_DO_NGANG", "qty": "1",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 1.257},
        {"slug": "canh_ngang",      "width": "W_mm/n_panel - OFFSET_FRAME", "qty": "2*n_panel",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 1.350},
        {"slug": "canh_dung",       "width": "(H_mm-TransomHeight_mm) - OFFSET_FRAME", "qty": "2*n_panel",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 1.350},
        {"slug": "nep_kinh_tren",   "width": "2*(glasses__panel_top__width + glasses__panel_top__height)", "qty": "2",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 0.312},
        {"slug": "nep_kinh_duoi",   "width": "2*(glasses__panel_bottom__width + glasses__panel_bottom__height)", "qty": "2*n_panel",
         "unit_price": 113000, "calc_pattern": "LENGTH_TO_WEIGHT", "weight_per_unit": 0.312},
    ],
    formula_fields=["width", "qty"],
    literal_fields=["unit_price", "calc_pattern", "weight_per_unit"],
    id_field="slug",
    synthetic_formulas=synthetic_for_pattern,
)

# ─── Bảng 2: Glasses (kính) ───
builder.add_table(
    table_name="glasses",
    rows=[
        {"slug": "panel_top",    "width": "W_mm - 2*OFFSET_FIXED",
         "height": "TransomHeight_mm - OFFSET_FIXED", "qty": "1",
         "unit_price": 1150000},
        {"slug": "panel_bottom", "width": "W_mm/n_panel - OFFSET_GLASS",
         "height": "(H_mm-TransomHeight_mm) - OFFSET_GLASS", "qty": "n_panel",
         "unit_price": 1150000},
    ],
    formula_fields=["width", "height", "qty"],
    literal_fields=["unit_price"],
    id_field="slug",
)

# ─── Bảng 3: Accessories (phụ kiện) ───
builder.add_table(
    table_name="accessories",
    rows=[
        {"slug": "keo_tren",  "qty": "1", "unit_price": 45000},
        {"slug": "keo_duoi",  "qty": "n_panel", "unit_price": 45000},
        {"slug": "gioang",    "qty": "1", "unit_price": 1250},
        {"slug": "vit",       "qty": "10*n_panel + 8", "unit_price": 850},
        {"slug": "tay_nam",   "qty": "1", "unit_price": 210000},
        {"slug": "khoa",      "qty": "1", "unit_price": 350000},
        {"slug": "ban_le",    "qty": "roundup(H_mm/700,0)*n_panel", "unit_price": 180000},
    ],
    formula_fields=["qty"],
    literal_fields=["unit_price"],
    id_field="slug",
)

# ─── Build → Engine ───
formulas, context = builder.build(base_context=base_inputs)

print(f"Total formulas: {len(formulas)}")   # ~50 formulas
print(builder.report())
```

### Kết quả `builder.report()`

```
MultiTableFormulaBuilder (mode=scoped)
  Tables: 3
  ├─ profiles: 8 rows
  │  formula_fields: ['width', 'qty']
  │  literal_fields: ['unit_price', 'calc_pattern', 'weight_per_unit']
  │  synthetic: synthetic_for_pattern
  ├─ glasses: 2 rows
  │  formula_fields: ['width', 'height', 'qty']
  │  literal_fields: ['unit_price']
  ├─ accessories: 7 rows
  │  formula_fields: ['qty']
  │  literal_fields: ['unit_price']
```

### Kết quả `formulas` (trích)

```python
[
    # ── profiles (8 dòng × 2 fields + 3 synthetic) = 40 formulas ──
    {"name": "profiles__khung_ngang_tren__width", "formula": "W_mm"},
    {"name": "profiles__khung_ngang_tren__qty",   "formula": "1"},
    {"name": "profiles__khung_ngang_tren__unit_qty",
     "formula": "lookup_calc_pattern(profiles__khung_ngang_tren__calc_pattern, ...)"},
    {"name": "profiles__khung_ngang_tren__total_qty",
     "formula": "profiles__khung_ngang_tren__unit_qty * (profiles__khung_ngang_tren__qty or 1)"},
    {"name": "profiles__khung_ngang_tren__line_total",
     "formula": "profiles__khung_ngang_tren__total_qty * (profiles__khung_ngang_tren__unit_price or 0)"},

    {"name": "profiles__canh_ngang__width",  "formula": "W_mm/n_panel - OFFSET_FRAME"},
    {"name": "profiles__canh_ngang__qty",    "formula": "2*n_panel"},
    # ... (unit_qty, total_qty, line_total cho canh_ngang)

    {"name": "profiles__nep_kinh_tren__width",
     "formula": "2*(glasses__panel_top__width + glasses__panel_top__height)"},
    # ☝ Cross-table reference: profiles → glasses

    # ── glasses (2 dòng × 3 fields) = 6 formulas ──
    {"name": "glasses__panel_top__width",  "formula": "W_mm - 2*OFFSET_FIXED"},
    {"name": "glasses__panel_top__height", "formula": "TransomHeight_mm - OFFSET_FIXED"},
    {"name": "glasses__panel_top__qty",    "formula": "1"},
    {"name": "glasses__panel_bottom__width",  "formula": "W_mm/n_panel - OFFSET_GLASS"},
    {"name": "glasses__panel_bottom__height", "formula": "(H_mm-TransomHeight_mm) - OFFSET_GLASS"},
    {"name": "glasses__panel_bottom__qty",    "formula": "n_panel"},

    # ── accessories (7 dòng × 1 field) = 7 formulas ──
    {"name": "accessories__keo_tren__qty",  "formula": "1"},
    {"name": "accessories__keo_duoi__qty",  "formula": "n_panel"},
    {"name": "accessories__vit__qty",       "formula": "10*n_panel + 8"},
    {"name": "accessories__ban_le__qty",    "formula": "roundup(H_mm/700,0)*n_panel"},
    # ...
]
```

### Kết quả Engine

```python
from formula_builder.formula_utils import FormulaEngine

engine = FormulaEngine(formulas=formulas)
result = engine.calculate(context)

# Profiles
assert result["profiles__khung_ngang_tren__width"] == 2400
assert result["profiles__canh_ngang__width"] == 2400/2 - 48  # 1152
assert result["profiles__canh_dung__width"] == (2600-600) - 48  # 1952

# Cross-table: nep_kinh phụ thuộc glasses
assert result["glasses__panel_top__width"] == 2400 - 100  # 2300
assert result["glasses__panel_top__height"] == 600 - 50  # 550
assert result["profiles__nep_kinh_tren__width"] == 2*(2300 + 550)  # 5700

# Accessories
assert result["accessories__vit__qty"] == 10*2 + 8  # 28
assert result["accessories__ban_le__qty"] == 4 * 2  # 8
```

---

## 12. Bảng tổng hợp pattern

| Pattern | Dùng khi | add_table config |
|---|---|---|
| **1 bảng, 1 formula/row** | Cost Template, hóa đơn đơn giản | `formula_fields=["formula"], literal_fields=[]` |
| **1 bảng, N formula/row** | Bom Item, panel kính | `formula_fields=["width","height","qty"], literal_fields=[...]` |
| **N bảng, cross-table ref** | BOM đa bảng, lương + khấu trừ | Gọi `add_table()` N lần, normalize_mode="scoped" |
| **Synthetic formulas** | Cần unit_qty, line_total | `synthetic_formulas=synthetic_for_pattern` |
| **Custom synthetic** | Công thức tự định nghĩa | Viết callback, truyền vào `synthetic_formulas` |
| **Override toàn bộ** | Logic quá phức tạp | `formula_builder=my_func` |
| **Hybrid** | 80% chuẩn + 20% đặc biệt | `builder.build()` + `formulas.extend(manual)` |
| **Global mode** | Slug unique toàn cục | `normalize_mode="global"` |
| **Scoped mode** | Slug có thể trùng bảng | `normalize_mode="scoped"` (mặc định) |
| **Custom normalize** | Quy tắc đặt tên riêng | `normalize_fn=my_func` |
| **Build thẳng Engine** | Convenience | `build_engine_from_builder(builder, ctx)` |

---

🤖 *Generated with [Claude Code](https://claude.com/claude-code)*
*Tham chiếu: `formula_builder/table_formula_builder.py`, `formula_builder/README.md` Section 13, `alumglass/v28.md`*