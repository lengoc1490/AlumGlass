# KẾ HOẠCH TRIỂN KHAI CHI TIẾT — ALUMGLASS ERP (THEO CHUẨN v28.2)

> **Tài liệu gốc tham chiếu:** `alumglass/v28.md` — AlumGlass ERP Tài liệu Hợp nhất Chuẩn Triển khai
> **Phiên bản kế hoạch:** v28.3 — 🆕 cập nhật sau review: thêm AL Profile System, chuyển offset+NC+PROFIT từ Global Variable sang doctype_query scoped, thêm profile_system vào AL Bom Set
> **Sản phẩm mẫu:** Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)
> **Ngày:** 2026-07-27

---

## MỤC LỤC

1. [Tổng quan & Nguyên tắc](#1-tổng-quan--nguyên-tắc)
2. [Sơ đồ 18 giai đoạn](#2-sơ-đồ-18-giai-đoạn)
3. [Ma trận phụ thuộc DocType](#3-ma-trận-phụ-thuộc-doctype)
4. [Chi tiết từng giai đoạn (G0 → G17)](#4-chi-tiết-từng-giai-đoạn)
5. [Kế hoạch kiểm thử](#5-kế-hoạch-kiểm-thử)
6. [Cổng nghiệm thu cuối](#6-cổng-nghiệm-thu-cuối)
7. [Kế hoạch rủi ro](#7-kế-hoạch-rủi-ro)
8. [Checklist tổng hợp](#8-checklist-tổng-hợp)

---

## 1. TỔNG QUAN & NGUYÊN TẮC

### 1.1 Phạm vi

Triển khai hệ thống tính BOM/giá bán cho sản phẩm nhôm kính trên nền:
- **Frappe/ERPNext** (core)
- **Formula Builder v31** (engine + data source platform)
- **AlumGlass** (app xây mới — lớp mỏng nghiệp vụ)

Kết quả cuối: `calculate_bom()` chạy ra **GIA_VAT = 22,717,289 VND** với input chuẩn CDMQ-2C-TRANSOM (W_mm=2400, H_mm=2600).

### 1.2 Nguyên tắc triển khai (từ v28 Section A.1)

| # | Nguyên tắc | Hệ quả cho kế hoạch |
|---|---|---|
| 1 | Zero Python trong DB | Công thức lưu trong Formula Builder, không code Python trong DB |
| 2 | Dùng FB cho việc FB làm được | AlumGlass là lớp mỏng — không tự code DAG, resolver, snapshot |
| 3 | Dùng ERPNext core trước | Pricing Rule, Workflow, Quality Inspection dùng core |
| 19 | Dispatch table Python thuần | `lookup_calc_pattern` không gọi ngược engine |
| **NEW** | **FB v31 DataSourceResolver** | Batch query + cache + transform do FB đảm nhiệm |
| **NEW** | **Khai báo > Code** | Cost Bucket mới = 1 dòng config JSON, không code Python |

### 1.3 Giả định

- 1 backend dev Frappe chính, 1 người nghiệp vụ nhôm kính, 1 QA cuối giai đoạn
- Formula Builder v31 đã cài sẵn (bao gồm BatchBindingResolver, SourceTypeRegistry, Composite Types)
- Số liệu mẫu trong v28.md được dùng cho dev/test; số liệu thật thay thế khi UAT

---

## 2. SƠ ĐỒ 18 GIAI ĐOẠN

| Giai đoạn | Tên | Thời gian | Tuần | Tham chiếu v28 |
|---|---|---|---|---|
| **G0** | Chuẩn bị môi trường & app | 0.5 ngày | Tuần 1 | A.2, A.3 |
| **G1** | Core ERPNext: Item Group, Brand | 0.5 ngày | Tuần 1 | B.5 |
| **G2** | DocType nền tảng: Color, Rule, Global Variable | 1 ngày | Tuần 1 | B.4, B.11 |
| **G3** | DocType cấp 2: Glass, Dynamic Rule, Slug, Calc Method | 1.5 ngày | Tuần 1 | B.1, B.3, B.6, B.10 |
| **G4** | Item + Item Price + Custom Fields + Validate | 1.5 ngày | Tuần 1-2 | B.5, Phụ lục C |
| **G5** | Cost Bucket & Cost Template (có source_type/source_config) | 1.5 ngày | Tuần 2 | B.7, C.4 |
| **G6** | Formula Set `BOM_LINE` (FB) | 0.5 ngày | Tuần 2 | B.4.2 |
| **G7** | Bom Item, Bom Set, BOM, BOM Version | 2 ngày | Tuần 2 | B.2, B.3, B.12 |
| **G8** | 🆕 Formula Snapshot (FB) + ConfigSnapshot (wrapper) | 1 ngày | Tuần 2 | B.8, C.6 |
| **G9** | Code: `fb_handlers.py` — đăng ký custom handlers vào FB | 1 ngày | Tuần 3 | C.4.9 |
| **G10** | Code: `data_source_resolver.py` — DataSourceResolver (lớp mỏng) | 1 ngày | Tuần 3 | C.4.5 |
| **G11** | Code: `lookup_calc_pattern` + `cost_handlers.py` | 1 ngày | Tuần 3 | C.4.1 |
| **G12** | Code: `BomOrchestrator` 7 phase + API `calculate_bom` | 3 ngày | Tuần 3 | D.1, D.2 |
| **G13** | Client Script UI + BOM Dialog | 0.5 ngày | Tuần 4 | D.3 |
| **G14** | Script seed demo data | 1 ngày | Tuần 4 | Phần F, H |
| **G15** | Kiểm thử số liệu & sensitivity | 2 ngày | Tuần 4 | Phần F, H.8 |
| **G16** | Kiểm thử hiệu năng (batch query, N+1, cache) | 1 ngày | Tuần 4 | C.4.5 |
| **G17** | UAT nghiệp vụ + đào tạo + go-live | 2 ngày | Tuần 5 | Toàn bộ |

**Tổng: ~20 ngày (~4 tuần) cho 1 dev full-time.**

> Có thể rút ngắn còn ~3 tuần nếu G1-G8 (nhập master data) làm song song với G9-G12 (code engine).

---

## 3. MA TRẬN PHỤ THUỘC DOCTYPE (🆕 v28.3)

| DocType cần tạo | Phụ thuộc (phải có trước) |
|---|---|
| AL Color Standard | Item Group |
| AL Calculation Rule | — (độc lập) |
| **🆕 AL Profile System** | Brand |
| AL Glass Master | AL Glass Type |
| AL Dynamic Item Rule | Item (result_item) |
| AL Slug Library | — (độc lập) |
| AL Quantity Calc Method | — (độc lập) |
| AL Product Type | — (độc lập. 🆕 Thêm field `profit_margin`) |
| **AL Cost Bucket** | — (độc lập. Có thêm source_type, source_config, depends_on, batch_group) |
| AL Cost Template | AL Cost Bucket |
| Formula Set `BOM_LINE` | — (FB đã cài) |
| Item | Item Group, Brand, AL Glass Master (nếu KINH) |
| Item Price | Item, AL Color Standard (qua custom field) |
| AL Bom Item | AL Slug Library, AL Quantity Calc Method, AL Cost Bucket, Item, AL Dynamic Item Rule |
| AL Bom Set | AL Bom Item, AL Profile System (🆕), AL Product Type |
| AL BOM | AL Bom Set, AL Cost Template |
| AL BOM Version | AL BOM |
| ConfigSnapshot | AL BOM Version |

---

## 4. CHI TIẾT TỪNG GIAI ĐOẠN

### G0 — Chuẩn bị môi trường *(0.5 ngày)*

```bash
bench get-app formula_builder
bench --site your-site install-app formula_builder
bench new-app alumglass
bench --site your-site install-app alumglass
```

**Xác nhận:**
- [ ] Formula Builder v31 đã cài (kiểm tra: có `batch_binding_resolver.py`, `source_type_registry.py`)
- [ ] `bench --site your-site list-apps` hiện đủ `frappe`, `erpnext`, `formula_builder`, `alumglass`
- [ ] Xác nhận cơ chế `custom_functions`/`safe_funcs` của FB (dùng `FormulaEngine(safe_funcs={...})`)

**DoD:** Site chạy được, 2 app đã cài. Ghi lại chính xác API signature của FB để dùng cho G9-G12.

---

### G1 — Core ERPNext: Item Group, Brand *(0.5 ngày)*

Tạo qua Desk UI hoặc fixture JSON:
- 6 Item Group: `NHOM_PROFILE` (cha), `NHOM_XINGFA`, `NHOM_ALUMIL`, `KINH`, `VTP`, `ACCESSORY`
- 3 Brand: `XINGFA`, `ALUMIL`, `KINLONG`

**DoD:** Vào Desk → Item Group thấy cây phân cấp đúng.

---

### G2 — DocType nền tảng *(1 ngày)* — 🆕 v28.3

1. **AL Color Standard** (B.9): `color_code`, `color_name`, `applies_to` (Link→Item Group), `is_standard_stock` — nhập 4 màu
2. **AL Profile System** (🆕 B.3.6): `system_code`, `system_name`, `brand`, `offset_frame`, `offset_glass`, `offset_fixed`, `offset_crossbar`, `is_active` — nhập 2 hệ (XINGFA_55, ALUMIL_M9560)
3. **AL Calculation Rule** (B.11): `rule_code`, `rule_name`, `rule_type` (CONSTANT/THRESHOLD/LOOKUP), `constant_value` — nhập 4 offset **làm default fallback** (giữ lại cho backward compatible, KHÔNG dùng làm nguồn chính)
4. **AL Product Type** (B.3.5): `type_code`, `type_name`, `nc_pct`, `nc_ld_rate`, `profit_margin` (🆕), `default_warranty_policy` — nhập DOOR với nc_pct=0.08, nc_ld_rate=0.12, profit_margin=0.16
5. **Formula Global Variable** (B.4.1 — DocType của FB): 🆕 CHỈ nhập 3 biến (VAT_RATE, OH_VC_PCT, OH_QLY_PCT). NC_SX_PCT, NC_LD_PCT, PROFIT_MARGIN đã chuyển sang AL Product Type. OFFSET đã chuyển sang AL Profile System.

**DoD:** 
- [ ] `frappe.get_all("AL Profile System")` trả về 2 dòng đúng offset
- [ ] `frappe.db.get_value("AL Product Type", "DOOR", "nc_pct")` → 0.08
- [ ] `frappe.get_all("Formula Global Variable", filters={"var_name": "NC_SX_PCT"})` → rỗng (đã xóa)

---

### G3 — DocType cấp 2 *(1.5 ngày)*

1. **AL Glass Type** (B.3.4): DON, CUONG_LUC, HOP, LOWE, LAM
2. **AL Glass Master** (B.3.3): 2 dòng kính — chú ý `total_thick_mm` là Decimal(5,2)
3. **AL Dynamic Item Rule** (B.6): 2 rule — `RULE-NEP-GLASSTHICK` (THRESHOLD, 3 khoảng), `RULE-KEO-GLASSTYPE` (LOOKUP, 2 khóa)
4. **AL Slug Library** (B.1): 17 slug — copy chính xác từng ký tự
5. **AL Quantity Calc Method** (B.10): 4 pattern — `calc_formula` chỉ để hiển thị

**DoD:** Test `RULE-NEP-GLASSTHICK` với input 24 → `C3211-20`; test `RULE-KEO-GLASSTYPE` với `LOWE` → `KEO-TT-01`.

---

### G4 — Item + Item Price + Custom Fields *(1.5 ngày)*

1. Custom Field trên Item: `al_material_category`, `al_weight_per_m`, `al_glass_master`, `al_is_color_variable`
2. Custom Field trên Item Price: `custom_color`, `custom_origin`, `custom_thickness`, `custom_surface_finish`
3. Tạo 3 Item "đại diện" + 14 Item "profile cụ thể" (Phần F.2.4)
4. Nhập 15 dòng Item Price mẫu (Phần F.2.5)
5. Server Script `validate_unique_price_combo` (Phụ lục G)
6. **Test ngay:** thử tạo Item Price trùng composite key → phải bị `frappe.throw()` chặn

**DoD:** 17 Item, 15 Item Price, validate hoạt động.

---

### G5 — Cost Bucket & Cost Template *(1.5 ngày)* — 🆕 v28.3

**NEW v28.3:** AL Cost Bucket có thêm 4 fields cho Data Source Definition + NC_SX/NC_LD không còn là formula đơn giản.

1. Tạo DocType `AL Cost Bucket` với fields:
   - `source_type` (Select): aggregate_from_items / formula / doctype_query / custom_function / constant / pipeline / conditional / fallback_chain
   - `source_config` (JSON): cấu hình nguồn dữ liệu
   - `depends_on` (JSON): biến phụ thuộc
   - `batch_group` (Data): nhóm batch query

2. Nhập 14 bucket (B.7.1) — 🆕 NC_SX, NC_LD đổi source_type:
   ```json
   // VL_NHOM: gom từ Bom Items
   {"bucket_code": "VL_NHOM", "source_type": "aggregate_from_items", "source_config": {"filter_by": {"category": "NHOM"}, "sum_field": "line_total"}}
   
   // 🆕 NC_SX: resolve từ AL Product Type (không còn formula với $NC_SX_PCT)
   {"bucket_code": "NC_SX", "source_type": "doctype_query", "source_config": {"doctype": "AL Product Type", "fieldname": "nc_pct", "aggregate": "first", "filters": [["name", "=", "{inputs.product_type}"]]}, "depends_on": ["product_type"]}
   
   // 🆕 NC_LD: resolve từ AL Product Type
   {"bucket_code": "NC_LD", "source_type": "doctype_query", "source_config": {"doctype": "AL Product Type", "fieldname": "nc_ld_rate", "aggregate": "first", "filters": [["name", "=", "{inputs.product_type}"]]}, "depends_on": ["product_type"]}
   
   // CP_VAN_CHUYEN: query bảng giá
   {"bucket_code": "CP_VAN_CHUYEN", "source_type": "doctype_query", "source_config": {"doctype": "Transport Rate", "fieldname": "rate_per_km", "aggregate": "first", "filters": [["from_location", "=", "{inputs.kho_xuat}"]]}}
   ```

3. Tạo `AL Cost Template` + child table `AL Cost Template Line`, nhập CT-01-STANDARD (14 dòng). 🆕 Công thức dùng `NC_SX_PCT` (không có `$` prefix).

**DoD:** Đọc lại từng dòng Cost Template, đối chiếu công thức với B.7.3. Đặc biệt kiểm tra NC_SX, NC_LD, PROFIT dùng tên biến không có `$`.

---

### G6 — Formula Set `BOM_LINE` *(0.5 ngày)*

Trong Formula Builder, tạo Formula Set mã `BOM_LINE` với 3 dòng (B.4.2):
- `unit_qty = lookup_calc_pattern(calc_pattern, width, height, weight_per_unit)`
- `total_qty = unit_qty * qty`
- `line_total = total_qty * unit_price`

**DoD:** Chốt chữ ký hàm `lookup_calc_pattern(calc_pattern_code, width, height, weight_per_unit)` — đây là contract giữa Formula Set và code Python G11.

---

### G7 — Bom Item, Bom Set, BOM, BOM Version *(2 ngày)* — 🆕 v28.3

1. **AL Bom Item** (B.2): DocType thống nhất cho NHOM/KINH/VTP/PK với các field: `slug`, `category`, `width`, `height`, `qty`, `item_selection_mode`, `item_code`, `item_rule`, `cost_bucket`, `calc_pattern`, `price_base_item`, `rule_input_expr`
2. **AL Bom Set** (B.3.1): `set_code`, `set_name`, `product_type`, `brand`, 🆕 `profile_system` (Link→AL Profile System), child table `al_bom_items`
3. **AL BOM** (B.3.2): `bom_code`, `bom_set`, `default_cost_template`
4. **AL BOM Version** (B.12): `bom`, `version_name`, `valid_from`, `workflow_state`, `profile_set_snapshot`, `cost_template_snapshot`

**🆕 v28.3 — Lưu ý quan trọng khi nhập Bom Set:**
- Gán `profile_system = XINGFA_55` cho BS-CDMQ-2C
- Gán `product_type = DOOR` (để resolve NC_SX_PCT, NC_LD_PCT, PROFIT_MARGIN)

**Nhập 17 dòng Bom Item cho BS-CDMQ-2C** (Phần F.3) — đây là bảng quan trọng nhất.

**DoD:** Đối chiếu từng dòng với F.3. Đặc biệt 4 dòng `item_selection_mode=Rule` phải đúng `rule_input_expr`. Bom Set đã có `profile_system` và `product_type`.

---

### G8 — ConfigSnapshot + Formula Snapshot DocType 🆕 *(1 ngày)*

> **FB v30:** Snapshot đã có persistence qua DocType `Formula Snapshot`. AlumGlass chỉ cần
> wrapper mỏng `ConfigSnapshot` để lưu thêm metadata nghiệp vụ.

1. **DocType `Formula Snapshot` (của FB)** — đã có sẵn sau khi `bench migrate`:
   - Tất cả data field là `JSON` (= MariaDB LONGTEXT, không giới hạn)
   - `snapshot_id`, `engine_meta`, `dag_structure`, `formulas`, `business_input`, `outputs`, `execution_trace`, `audit_trail`
   - **Không cần tạo** — FB tự quản lý

2. **DocType `ConfigSnapshot` (AlumGlass wrapper)** — tạo mới:
   - `fb_snapshot_id` (Data) → Link tới `Formula Snapshot`
   - `bom_version_id`, `rule_version_ids`
   - `quotation_item_name`, `calculation_timestamp`
   - **Gọn hơn trước**: không cần `inputs_json`, `result_json`, `enterprise_snapshot_json` (đã có trong `Formula Snapshot`)

3. **Test ngay:**
   ```python
   from formula_builder.formula_utils import SnapshotManager
   # Submit → DB
   docname = SnapshotManager.submit(snap, title="Test", ...)
   # Load ← DB
   snap2 = SnapshotManager.load(docname)
   assert snap2.verify()
   ```

**DoD:** `SnapshotManager.submit()` → record trong `tabFormula Snapshot`; `load()` → `verify()` True.

---

### G9 — Code: `fb_handlers.py` — Custom FB Handlers *(1 ngày)*

**NEW v28.2:** Đăng ký handler qua `fb_source_types` hook + `@register_source` decorator (C.4.9).

```python
# alumglass/hooks.py
fb_source_types = [
    "alumglass.fb_handlers.aluminum_price_composite",
    "alumglass.fb_handlers.glass_master_data",
    "alumglass.fb_handlers.cost_bucket_aggregate",
]

# alumglass/fb_handlers.py
from formula_builder.api.source_type_registry import register_source

@register_source("aluminum_price_composite",
    label="Aluminum Price (Composite Key)",
    description="Look up aluminum price by color + origin + thickness + surface",
    config_schema={...},
    app="alumglass",
    batchable=True,
    fingerprint_fn=lambda cfg: f"nhom_price:{cfg.get('price_list')}",
    supports_transform=True,
    supports_cache=True,
    default_cache_ttl=300,
)
def _handle_aluminum_price(binding, doc, resolved_so_far):
    ...
```

**DoD:**
- [ ] Handler được FB auto-discover (không cần gọi `register_handlers()` thủ công)
- [ ] `SourceTypeRegistry.get_instance().has("aluminum_price_composite")` → True
- [ ] Test resolve với input mẫu → trả về đúng giá

---

### G10 — Code: `data_source_resolver.py` *(1 ngày)* — 🆕 v28.3

**NEW v28.3:** DataSourceResolver — lớp mỏng ủy thác cho FB BatchBindingResolver + thêm offset/product_type resolution (C.4.5, C.4.6).

```python
# alumglass/engine/data_source_resolver.py (~120 dòng)
from formula_builder.api.batch_binding_resolver import BatchBindingResolver

class DataSourceResolver:
    def resolve_all(self, bom_items, inputs, bucket_definitions,
                    profile_system_code=None, product_type=None):  # 🆕
        bindings = self._build_bindings(bucket_definitions, bom_items, inputs)
        # 🆕 v28.3: offset từ AL Profile System
        bindings += self._build_offset_bindings(profile_system_code)
        # 🆕 v28.3: NC_SX_PCT, NC_LD_PCT, PROFIT_MARGIN từ AL Product Type
        bindings += self._build_product_type_bindings(product_type)
        resolver = BatchBindingResolver(cache_ttl=300)
        return resolver.resolve_all_batch(bindings, pre_resolved=inputs)
```

**🆕 Test đặc biệt cho v28.3:**
- [ ] `resolve_all()` với XINGFA_55 → OFFSET_FRAME=48, OFFSET_GLASS=90
- [ ] `resolve_all()` với ALUMIL_M9560 → OFFSET_FRAME=44, OFFSET_GLASS=86
- [ ] `resolve_all()` với product_type=DOOR → NC_SX_PCT=0.08, NC_LD_PCT=0.12

**DoD:**
- [ ] Gọi `resolve_all()` với 17 dòng BOM → `row_literals` đầy đủ `weight_per_unit`, `unit_price`, `glass_thick`, `glass_type`
- [ ] 🆕 OFFSET_FRAME, NC_SX_PCT, PROFIT_MARGIN được resolve scoped đúng
- [ ] Bom Set không có profile_system → fallback về default (backward compat)
- [ ] Số query ≤ 5 (xác nhận batch hoạt động)
- [ ] Cache hoạt động: lần 2 nhanh hơn lần 1

---

### G11 — Code: `lookup_calc_pattern` + `cost_handlers.py` *(1 ngày)*

1. **`lookup_calc_pattern`** (C.4.1): dispatch table Python thuần — **KHÔNG gọi ngược engine**
2. **`cost_handlers.py`**: Các hàm xử lý nghiệp vụ đặc thù (nếu cần):
   - `get_aluminum_market_price(brand, color)`
   - `get_glass_thickness(glass_code)`
   - `get_coating_cost(total_kg, color, surface_type)`

**DoD:**
- [ ] Unit test 4 pattern `lookup_calc_pattern` pass
- [ ] Code review: grep `FlexibleFormulaEngine` trong file → rỗng
- [ ] Các hàm trong `cost_handlers.py` có thể gọi từ `custom_function` source type

---

### G12 — Code: `BomOrchestrator` 7 phase + API *(3 ngày)*

**NEW v28.2:** 7 phase (giảm từ 11), B2 dùng DataSourceResolver, B4+B6 dùng FB engine.

| Phase | Việc | Test riêng |
|---|---|---|
| **B0** | Version pinning — query `AL BOM Version` theo `valid_from` | Test trả về đúng version |
| **B1** | Gather inputs: Quotation + Global Variables + Calculation Rules | So `inputs` với bảng kỳ vọng |
| **B2** | **Pre-fetch qua DataSourceResolver** (C.4.6) — 1 dòng gọi `resolver.resolve_all()` | So `row_literals` 17 dòng, ≤5 queries |
| **B3** | Build Bom Engine — `FormulaEngine` với cross-row reference | Đếm số formulas (~100) |
| **B4** | Calculate Bom Items — `engine.calculate(inputs)` | So bảng 17 dòng với F.4 |
| **B5** | Gom Cost Bucket — Python loop gom `line_total` theo `cost_bucket` | So 4 số VL_NHOM/VL_KINH/VL_VTP/VL_PK |
| **B6** | Cost Template — `FlexibleFormulaEngine` với `global_formulas` | So 14 dòng → GIA_VAT |
| **B7** | Save child table + SnapshotManager.submit() 🆕 | Load lại snapshot, verify() True, trace đủ 14 dòng Cost |

**API:**
```python
@frappe.whitelist()
def calculate_bom(quotation_item_name):
    orch = BomOrchestrator(quotation_item_name)
    return orch.run()
```

**DoD:** `calculate_bom()` với input chuẩn → **GIA_VAT = 22,717,289 VND** (±1 VND).

---

### G13 — Client Script UI *(0.5 ngày)*

Thêm nút "Tính giá" trên Quotation Item, gọi `calculate_bom()`, hiển thị kết quả.

**DoD:** Bấm nút → hiển thị GIA_VAT + 17 dòng chi tiết.

---

### G14 — Script seed demo data *(1 ngày)*

Viết `alumglass/setup/seed_demo_data.py` — script idempotent tạo toàn bộ master data + BOM mẫu.

**DoD:** Xóa hết data, chạy script, `calculate_bom()` vẫn ra đúng 22,717,289.

---

### G15 — Kiểm thử số liệu & sensitivity *(2 ngày)*

Chạy toàn bộ checklist sensitivity test (Phần F.6, H.8):

- [ ] BOM chuẩn → GIA_VAT = 22,717,289
- [ ] `canh_ngang` = 702,950; `canh_dung` = 1,191,110
- [ ] Đổi `aluminum_color` → DARK: 10 dòng NHOM đổi giá 118,000
- [ ] Đổi `aluminum_origin` → DOMESTIC: giá 98,000
- [ ] Đổi kính 8mm → Rule chọn C3209-20 + KEO-TT-02
- [ ] Đổi kích thước: W_mm=3000, H_mm=2800 → tất cả tính lại đúng
- [ ] **NEW:** Thêm Cost Bucket `CP_BAO_HANH` (formula) → chỉ cần 1 record AL Cost Bucket + 1 dòng Cost Template, không code
- [ ] **NEW:** Test pipeline: giá nhôm = base → tax → margin
- [ ] **NEW:** Test fallback: API sập → dùng cache → dùng default
- [ ] **🆕 v28.3:** Đổi `profile_system` từ XINGFA_55 → ALUMIL_M9560 → offset khác, GIA_VAT khác
- [ ] **🆕 v28.3:** Thêm hệ profile mới (XINGFA_60) → tạo 1 record AL Profile System → 0 dòng code
- [ ] **🆕 v28.3:** BOM Set không có profile_system → fallback về default từ AL Calculation Rule (backward compat)
- [ ] **🆕 v28.3:** Test NC_SX_PCT từ AL Product Type → đổi nc_pct từ 0.08 → 0.10 → NC_SX thay đổi
- [ ] 🆕 **Snapshot: submit** snapshot → record trong `tabFormula Snapshot`
- [ ] 🆕 **Snapshot: load + verify** → `snap.verify()` True, trace 14 dòng Cost khớp
- [ ] 🆕 **Snapshot: compare** 2 snapshot (T7 vs T12) → diff hiển thị delta + delta%
- [ ] 🆕 **Snapshot: query_from_db()** → list không load execution_trace
- [ ] 🆕 **Snapshot: trace_level** `cost_only` → trace < 5KB, vẫn đủ 14 dòng Cost

**DoD:** Toàn bộ checklist pass.

---

### G16 — Kiểm thử hiệu năng *(1 ngày)*

- [ ] 17 dòng BOM → ≤5 batch queries (xác nhận BatchBindingResolver hoạt động)
- [ ] 50 dòng curtain wall → ≤7 queries
- [ ] Cache hit lần 2: nhanh hơn lần 1 ≥50%
- [ ] 20 BOM đồng thời: không N+1, thời gian tuyến tính

**DoD:** Báo cáo số query + thời gian. Không có N+1.

---

### G17 — UAT nghiệp vụ + go-live *(2 ngày)*

1. Người nghiệp vụ test với số liệu thật
2. Đào tạo: nhập Quotation, bấm "Tính giá", đọc kết quả, **thêm Cost Bucket mới không cần dev**
3. Go-live: backup → migrate → production

**DoD:** Người nghiệp vụ xác nhận giá khớp cách tính thủ công. Tự tạo được Cost Bucket mới.

---

## 5. KẾ HOẠCH KIỂM THỬ

| Cấp độ | Khi nào | Nội dung | Tiêu chí |
|---|---|---|---|
| **Unit test** | G9-G12 | Từng hàm, từng phase BomOrchestrator | Mỗi hàm ≥1 test case so số liệu tay |
| **Integration test** | G15 | `calculate_bom()` end-to-end | GIA_VAT = 22,717,289 (±1 VND) |
| **Sensitivity test** | G15 | Đổi input: màu, xuất xứ, kính, kích thước | Kết quả thay đổi đúng hướng |
| **Flexibility test** | G15 | Thêm Cost Bucket mới qua UI (không code) | 5 phút, không deploy |
| **Composite test** | G15 | Pipeline, conditional, fallback hoạt động | Kết quả đúng như tính tay |
| **Performance test** | G16 | Batch query count, cache hit rate | ≤5 queries cho 17 dòng BOM |
| **UAT** | G17 | Số liệu thật | Người nghiệp vụ xác nhận |

---

## 6. CỔNG NGHIỆM THU CUỐI (🆕 v28.3)

Dự án hoàn thành khi **tất cả** điều sau đúng:

1. [ ] `calculate_bom()` chuẩn → **GIA_VAT = 22,717,289 VND** (±1 VND) với XINGFA_55
2. [ ] Toàn bộ checklist G13 pass
3. [ ] **Không có N+1 query** (batch query ≤5 cho 17 dòng)
4. [ ] DataSourceResolver hoạt động — thêm Cost Bucket mới không cần code
5. [ ] `lookup_calc_pattern` không gọi ngược engine (code review)
6. [ ] 🆕 SnapshotManager.submit() → DB; load() → verify() True
7. [ ] 🆕 Trace 14 dòng Cost khớp GIA_VAT = 22,717,289; trace_level=cost_only < 5KB
8. [ ] 🆕 Compare 2 snapshot → diff hiển thị inputs_changed + outputs_changed + delta%
9. [ ] Script seed chạy từ site trống ra đúng kết quả
10. [ ] Người nghiệp vụ UAT với số liệu thật — xác nhận văn bản
11. [ ] **NEW:** User tự tạo được Cost Bucket `CP_BAO_HANH` (formula) trong 5 phút, không cần dev
12. [ ] **🆕 v28.3:** Đổi `profile_system` từ XINGFA_55 → ALUMIL_M9560 → GIA_VAT thay đổi đúng (offset khác)
13. [ ] **🆕 v28.3:** Thêm hệ profile mới (XINGFA_60) → 1 record AL Profile System → 0 dòng code, 0 deploy
14. [ ] **🆕 v28.3:** Đổi `nc_pct` trong AL Product Type → NC_SX thay đổi trong Cost Template
15. [ ] **🆕 v28.3:** BOM Set cũ không có profile_system → fallback về default từ AL Calculation Rule (backward compat)
16. [ ] **🆕 v28.3:** Không còn NC_SX_PCT, NC_LD_PCT, PROFIT_MARGIN trong Formula Global Variable

---

## 7. KẾ HOẠCH RỦI RO

| Rủi ro | XS | Ảnh hưởng | Dự phòng |
|---|---|---|---|
| FB không hỗ trợ `safe_funcs` như giả định | Thấp (đã xác nhận v31) | Cao | Xác nhận API trước G9; fallback: pre-compute bằng Python |
| Nhập sai 1 trong 17 dòng Bom Item | Cao | Cao | Import từ fixture JSON, không nhập tay; đối chiếu ký tự từng dòng |
| Tái diễn lỗi gọi đệ quy engine | Thấp | Cao | Code review bắt buộc: grep `FlexibleFormulaEngine` trong `formula_handlers.py` |
| Sai ranh giới Dynamic Item Rule | Trung bình | Trung bình | Test riêng biên: 10.38, 10.39, 16, 16.01 |
| BatchBindingResolver không gom được query | Thấp | Trung bình | Kiểm tra `@batchable` decorator + `fingerprint_fn` đúng |
| Số liệu thật khác mẫu | Cao | Thấp | Kiến trúc tách data khỏi code → chỉ nhập lại, không sửa code |
| User không quen cấu hình JSON | Trung bình | Trung bình | Đào tạo + cung cấp template JSON mẫu cho từng loại bucket |

---

## 8. CHECKLIST TỔNG HỢP

```
[ ] G0  Cài formula_builder v31 + alumglass, xác nhận API
[ ] G1  Item Group (6) + Brand (3)
[ ] G2  🆕 AL Profile System (2) + AL Color Standard (4) + AL Calculation Rule (4, fallback) + AL Product Type (1, có profit_margin) + Formula Global Variable (3, đã thu hẹp)
[ ] G3  AL Glass Type (5) + Glass Master (2) + Dynamic Item Rule (2, test biên) + Slug Library (17) + Quantity Calc Method (4)
[ ] G4  Item (17) + Item Price (15) + Custom Fields + Server Script validate
[ ] G5  AL Cost Bucket (14, có source_type/source_config, 🆕 NC_SX/NC_LD dùng doctype_query) + AL Cost Template (14 dòng, 🆕 công thức không có $)
[ ] G6  Formula Set BOM_LINE (3 dòng, chốt contract)
[ ] G7  🆕 AL Bom Item + Bom Set BS-CDMQ-2C (có profile_system=XINGFA_55, product_type=DOOR, 17 dòng) + BOM + BOM Version
[ ] G8  🆕 Formula Snapshot (FB, tự động) + ConfigSnapshot DocType (wrapper AlumGlass)
[ ] G9  fb_handlers.py (đăng ký qua @register_source, test auto-discovery)
[ ] G10 🆕 data_source_resolver.py (BatchBindingResolver + offset binding + product_type binding, ≤5 queries)
[ ] G11 lookup_calc_pattern (dispatch table, KHÔNG gọi engine) + cost_handlers.py
[ ] G12 BomOrchestrator 7 phase (B0→B7, 🆕 B1 không load offset, B2 resolve scoped, GIA_VAT = 22,717,289)
[ ] G13 Client Script nút "Tính giá"
[ ] G14 seed_demo_data.py (idempotent, 🆕 bao gồm AL Profile System + AL Product Type)
[ ] G15 🆕 Test số liệu + sensitivity + profile system change + product type change + flexibility
[ ] G16 Test hiệu năng (batch query, cache, không N+1)
[ ] G17 UAT số liệu thật + đào tạo + go-live

CỔNG CUỐI: GIA_VAT = 22,717,289 VND với XINGFA_55 — KHÔNG ĐẠT → CHƯA XONG.
```

---

*Kế hoạch này cập nhật từ v27 lên v28.2, bổ sung các tính năng mới của Formula Builder v30 (BatchBindingResolver, SourceTypeRegistry, Composite Types, Transform Layer, 🆕 SnapshotManager.submit()/load() persistence) và thiết kế DataSourceResolver trong AlumGlass. Mọi số liệu, công thức, tên field tham chiếu từ `v28.md`.*
