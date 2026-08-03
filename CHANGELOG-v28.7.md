# AlumGlass v28.7 — CHANGELOG

> Ngày: 2026-08-03 | Từ v28.6 → v28.7 | 12 files | +580 / -314 lines

---

## Tổng quan

v28.7 là bản nâng cấp tập trung vào **xóa toàn bộ hardcode** khỏi core engine và **tối ưu performance** (giảm ~50% DB queries). Kiến trúc chuyển từ "config-driven với vài điểm hardcode" sang **DATA-DRIVEN hoàn toàn** — mọi thứ đều từ DB, 0 dòng code cho mọi config mới.

---

## A. XÓA HARDCODE — 6 điểm (đã triển khai)

### A1. System Variables: `SCOPED_VAR_SOURCES` → AL Variable Library

**Vấn đề:** `bom_orchestrator.py` có dict `SCOPED_VAR_SOURCES` hardcode 7 mappings:
```python
SCOPED_VAR_SOURCES = {
    "OFFSET_FRAME": ("AL Profile System", "offset_frame"),
    "OFFSET_GLASS": ("AL Profile System", "offset_glass"),
    ...
}
```
Thêm system variable mới → phải sửa dict này.

**Giải pháp:**
- Thêm 2 field vào `AL Variable Library`: `source_doctype` (Link→DocType) và `source_field` (Data)
- Engine đọc tất cả system variables từ Library (`is_system=1`), batch query theo `source_doctype`, resolve giá trị
- Fallback: `default_value` từ Library → `AL Calculation Rule` CONSTANT

**Files:**
- `al_master_data/doctype/al_variable_library/al_variable_library.json` — thêm `source_doctype`, `source_field`
- `al_master_data/doctype/al_variable_library/al_variable_library.py` — validate source_doctype cần source_field
- `engine/bom_orchestrator.py` — `_resolve_system_variables()` thay thế `SCOPED_VAR_SOURCES`
- `setup/seed_demo_data.py` — thêm source_doctype/source_field cho 10 system vars

**Kết quả:** Thêm 1 system variable mới = 1 record `AL Variable Library` với `is_system=1` + `source_doctype` + `source_field`.

---

### A2. API System Vars: Hardcode list → DB Query

**Vấn đề:** `api/__init__.py:get_variable_set_for_bom()` hardcode 10 system variables:
```python
system_vars = [
    {"var_name": "OFFSET_FRAME", ...},
    {"var_name": "OFFSET_GLASS", ...},
    ...  # 10 dòng
]
```

**Giải pháp:**
- Query `AL Variable Library` với filter `is_system=1`
- Merge system vars vào response — JS dialog tự filter `is_system` để ẩn khỏi form
- Dùng `get_cached_doc()` cho BOM, Bom Set, Variable Set

**Files:**
- `api/__init__.py` — rewrite `get_variable_set_for_bom`

**Kết quả:** System variable mới tự động xuất hiện trong API response, JS dialog tự dynamic.

---

### A3. Composite Key Pricing: Hardcode → Variable Dimension Mapping

**Vấn đề:** `fb_handlers.py:aluminum_price_composite()` hardcode 4 composite key fields + defaults:
```python
color = resolved_so_far.get("aluminum_color", "WHITE")
origin = resolved_so_far.get("aluminum_origin", "IMPORT")
thickness = resolved_so_far.get("aluminum_thickness", 20)
surface = resolved_so_far.get("aluminum_surface", "POWDER_COATED")
...
filters.append(["custom_color", "=", color])       # hardcode field name
filters.append(["custom_origin", "=", origin])     # hardcode field name
```

**Giải pháp:**
- Implement `AL Variable Dimension Mapping` controller (trước là `pass` stub)
- Handler đọc mappings: `variable_name` → `pricing_dimension` → `custom_fieldname`
- Build filter động dựa trên các biến đã resolve

**Files:**
- `fb_handlers.py` — rewrite `aluminum_price_composite` với dynamic discovery
- `al_master_data/doctype/al_variable_dimension_mapping/al_variable_dimension_mapping.py` — implement
- `setup/seed_demo_data.py` — thêm `_variable_dimension_mapping()` seed 4 mappings

**Kết quả:** Thêm pricing dimension mới = 1 `AL Pricing Dimension` + 1 `AL Variable Dimension Mapping`.

---

### A4. Response Format: 4 keys → Toàn bộ cost_template

**Vấn đề:** `_build_response()` chỉ trả về 4 keys:
```python
return {
    "gia_vat": self.gia_vat,
    "gia_ban": self.cost_result.get("GIA_BAN", 0),
    "tong_vl": self.cost_result.get("TONG_VL", 0),
    "tong_nc": self.cost_result.get("TONG_NC", 0),
}
```
Thêm cost bucket mới → JS không nhận được.

**Giải pháp:** Trả về toàn bộ `cost_result` dict. Client tự chọn key cần hiển thị.

**Files:**
- `engine/bom_orchestrator.py` — `_build_response()` trả về `{"buckets", "cost_template", "lines"}`
- `public/js/bom_dialog.js` — hiển thị động toàn bộ cost_template keys

**Kết quả:** Mọi cost bucket mới tự động xuất hiện trong dialog.

---

### A5. Formula Fields: Hardcode list → Bom Set config + Dynamic meta

**Vấn đề:** `BOM_ITEM_FORMULA_FIELDS` hardcode 6 field names:
```python
BOM_ITEM_FORMULA_FIELDS = ["width", "height", "qty", "show_condition",
                            "item_condition_formula", "rule_input_expr"]
```
Thêm field formula mới → phải sửa list này.

**Giải pháp:**
- Thêm `formula_fieldnames` (Small Text, JSON) vào `AL Bom Set` — config ở Bom Set level
- Fallback: engine đọc mọi Small Text field từ `AL Bom Item` doctype meta
- `AL BOM Version._take_snapshots()` tự động copy mọi Small Text field (dynamic meta read)

**Files:**
- `al_bom_engine/doctype/al_bom_set/al_bom_set.json` — thêm `formula_fieldnames`
- `engine/bom_orchestrator.py` — `b3_build_formulas()` đọc formula_fields từ config
- `al_bom_engine/doctype/al_bom_version/al_bom_version.py` — dynamic snapshot
- `setup/seed_demo_data.py` — Bom Set có formula_fieldnames JSON

**Kết quả:** Thêm field formula mới vào Bom Item → thêm vào `formula_fieldnames` JSON trong Bom Set. Hoặc thêm Small Text field vào doctype → snapshot tự động copy.

---

### A6. Quantity Calc Dispatch: if/elif → calc_fn từ DB

**Vấn đề:** `lookup_calc_pattern()` dùng if/elif dispatch cho 4 pattern:
```python
if calc_pattern_code == "LENGTH_TO_WEIGHT": return w * tlr
if calc_pattern_code == "AREA": return w * h
if calc_pattern_code == "LENGTH_ONLY": return w
if calc_pattern_code == "COUNT": return 1.0
```
Thêm pattern mới → phải thêm elif.

**Giải pháp:**
- Đọc `calc_fn` lambda từ `AL Quantity Calc Method` record
- Eval với restricted namespace (`{"__builtins__": {}, "abs": abs, "max": max, ...}`)
- Cache result trong module-level dict

**Files:**
- `al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py` — rewrite

**Kết quả:** Thêm pattern tính mới = 1 record `AL Quantity Calc Method` với `calc_fn` lambda.

---

## B. PERFORMANCE — giảm ~50% DB queries

### B1. Single Commit (B7)
- **Trước:** 5 `set_value` + 1 raw SQL INSERT + 3 `commit()` = 9 roundtrips
- **Sau:** 1 `set_value({field1, val1, ...})` gộp multi-field + `get_doc().insert()` + 1 `commit()`
- **Tiết kiệm:** ~6 queries

### B2. get_cached_doc() cho config doctypes
- Config doctypes (BOM, BOM Version, Bom Set, Profile System, Product Type, Calculation Rule) dùng Redis cache 3600s
- Frappe tự invalidate cache khi document save
- **Tiết kiệm:** 5-8 queries sau lần gọi đầu

### B3. Batch Glass Master query
- Gom tất cả `default_glass_master` codes → 1 `get_all(..., {"name": ("in", codes)})`
- **Tiết kiệm:** K-1 queries (K = số dòng KINH)

### B4. Cost Bucket load tối ưu
- Parse Cost Template formulas bằng regex → extract bucket codes được reference
- Chỉ set default 0.0 cho những code đó (không load toàn bộ bảng)
- **Tiết kiệm:** 1 query + scalability

### B5. Loại bỏ duplicate loads
- Cache `self._qi_doc` và `self._bom_doc` xuyên suốt engine
- B1 đọc `al_bom_vars` từ QI doc thay vì `get_value` riêng
- **Tiết kiệm:** 2 queries

### Tổng kết performance

| Scenario | v28.6 | v28.7 | Giảm |
|---|---|---|---|
| Typical (version given, full config) | ~24 queries | ~10-12 queries | **50%** |
| Cold cache (first call) | ~24 queries | ~15-17 queries | **30%** |
| Warm cache (subsequent calls) | ~24 queries | ~8-10 queries | **60%** |

---

## C. JS CLIENT

### C1. BOM Dialog hiển thị động
- `bom_dialog.js`: Hiển thị toàn bộ `cost_template` keys trong bảng, phân loại detail/subtotal
- Format VND tự động
- Không còn phụ thuộc vào key names cố định

### C2. Cost Template Preview bỏ mock data
- `cost_template.js`: Thay mock data hardcode bằng prompt dialog cho user nhập test JSON

---

## D. SCHEMA CHANGES

### Doctype JSON thay đổi

| Doctype | Field mới | Type | Mục đích |
|---|---|---|---|
| `AL Variable Library` | `source_doctype` | Link→DocType | Doctype nguồn resolve system var |
| `AL Variable Library` | `source_field` | Data | Field trong source doctype |
| `AL Bom Set` | `formula_fieldnames` | Small Text | JSON array field names cần evaluate |

### Python controller thay đổi

| Doctype | Thay đổi |
|---|---|
| `AL Variable Library` | Validate: source_doctype → cần source_field |
| `AL BOM Version` | `_take_snapshots()`: dynamic copy tất cả Small Text fields từ Bom Item meta |
| `AL Variable Dimension Mapping` | Implement từ stub (`pass`) |

---

## E. KIỂM CHỨNG

```bash
# 1. Apply schema
cd /home/lengoc/frappe-bench && bench migrate

# 2. Re-seed
bench console
>>> from alumglass.setup.seed_demo_data import seed_all
>>> seed_all()

# 3. Test
bench console
>>> from alumglass.run_test import main
>>> main()
# Expected: GIA_VAT ≈ 22,717,289 VND
```

## F. BACKWARD COMPATIBILITY

- ✅ `run_test.py` giữ nguyên expected value — output không đổi
- ✅ `bom_dialog.js` vẫn hiển thị summary + detail lines như cũ, thêm cost_template đầy đủ
- ✅ API endpoints giữ nguyên signature — response có thêm keys mới (additive)
- ✅ Seed data tương thích — thêm fields mới, giữ nguyên data cũ
- ✅ Không cần migrate data — BOM Versions cũ có thể re-publish để có snapshot mới

## G. KIẾN TRÚC TƯƠNG LAI

Các hướng mở rộng tiếp theo (đã có trong thiết kế, chưa triển khai):

| Item | Mô tả | Độ khó |
|---|---|---|
| **ERPNext BOM Bridge** | Tự động sync sang ERPNext BOM để MRP/Production Order hoạt động | Medium |
| **Item Variant cho Profile** | Mỗi profile system = 1 Item Template, giảm ~80% master Items | High |
| **GL Entry Actual Costing** | Đọc GL Entry để so sánh estimate vs actual | Medium |
| **Print Format** | Jinja template cho báo giá, hợp đồng | Low |
| **Scheduler Tasks** | Uncomment 7 scheduled tasks (KPI, alerts, notifications) | Low |
| **Permission System** | Role-based permissions cho AL doctypes | Low |
