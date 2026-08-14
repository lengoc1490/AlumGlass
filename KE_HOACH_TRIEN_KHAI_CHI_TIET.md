# KẾ HOẠCH TRIỂN KHAI CHI TIẾT — ALUMGLASS ERP (THEO CHUẨN v28.6)

> **Tài liệu gốc tham chiếu:** `alumglass/v28.md` — AlumGlass ERP Tài liệu Hợp nhất Chuẩn Triển khai
> **Phiên bản kế hoạch:** v28.6 — 🆕 2026-08-01: Tái cấu trúc module (10 DocType về đúng module), tận dụng ERPNext Projects, CRM, Maintenance, HRMS
> **Sản phẩm mẫu:** Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)
> **Ngày:** 2026-07-27 (gốc) | 2026-08-01 (v28.6)

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
- **HRMS app đã cài** (nếu cần Employee, Attendance, Expense Claim) — AlumGlass không tự tạo module HR
- **ERPNext core modules đã active:** Projects, CRM, Maintenance, Accounts, Support

### 1.4 Cấu trúc Module (🆕 v28.6)

Sau review v28.6, các DocType đã được tái cấu trúc về đúng module:

| Chuyển DocType | Từ | Đến | Lý do |
|---|---|---|---|
| AL Supplier Price List + Item | AL Master Data | **AL Buying** | Nghiệp vụ mua hàng |
| AL Accessory Set + Item | AL Master Data | **AL BOM Engine** | Gần cấu trúc BOM |
| AL Cutting Standard | AL Master Data | **AL Manufacturing** | Nghiệp vụ sản xuất |
| AL Installation Team | AL Master Data | **AL Construction** | Nghiệp vụ thi công |
| AL Warranty Policy | AL Master Data | **AL Quality** | Nghiệp vụ bảo hành |
| AL Change Order | AL Account | **AL Construction** | Quản lý phát sinh dự án |
| AL Handover Acceptance | AL Account | **AL Construction** | Nghiệm thu thi công |
| AL Punchlist Item | AL Account | **AL Construction** | Danh sách lỗi thi công |

Chi tiết: xem `CAU_TRUC_MODULE_VA_DOCTYPE.md` (v1.1).

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

3. Tạo `AL Cost Template` + child table `AL Cost Template Item`, nhập CT-01-STANDARD (14 dòng). 🆕 Công thức dùng `NC_SX_PCT` (không có `$` prefix).

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
2. **AL Bom Set** (B.3.1): `set_code`, `set_name`, `product_type`, `brand`, 🆕 `profile_system` (Link→AL Profile System), child table `items`
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

---

# PHỤ LỤC — CƠ CHẾ BIẾN ĐỔI CÔNG THỨC → FORMULAS + CONTEXT

## P.1 NGUYÊN LÝ CỐT LÕI

**Mọi công thức dù viết kiểu gì (bare name, `$VAR`, `items.slug.field`), cuối cùng đều hội tụ về 2 thứ trước khi vào Engine:**

```
CÔNG THỨC NGƯỜI DÙNG VIẾT          SAU KHI RESOLVE
─────────────────────────          ─────────────────
VL_NHOM + VL_KINH                  "VL_NHOM + VL_KINH"
$OFFSET_FRAME                     "48"
items.kinh_tren.width + W_mm      "2300 + 2400"
NC_SX_PCT * TONG_VL               "0.08 * 14062811"

          │                              │
          ▼                              ▼
   1. Formula string (text)         2. Context dict (numbers)
```

**FormulaEngine/FormulaEngineCore chỉ nhìn thấy 2 thứ:**
- **`formula`**: chuỗi biểu thức toán học (có thể chứa biến hoặc hằng số)
- **`context`**: dict chứa giá trị thực tế của từng biến

**Engine không biết và không cần biết** biến đó là bare name, `$` prefix, hay slug reference — tất cả đã được resolve thành giá trị số trước khi vào.

---

## P.2 BOM LINE: NHIỀU TRƯỜNG CÔNG THỨC TRÊN CÙNG 1 ROW

### P.2.1 Bài toán

Mỗi dòng Bom Item có **5 trường công thức** (thực ra 3 trường input + 2 trường derived):

| Field | Ý nghĩa | Ai viết? | Ví dụ |
|---|---|---|---|
| `width` | Chiều dài (mm) | Người cấu hình BOM | `W_mm - 2*$OFFSET_FIXED` |
| `height` | Chiều cao (mm) | Người cấu hình BOM | `TransomHeight_mm - $OFFSET_FIXED` |
| `qty` | Số lượng (cái) | Người cấu hình BOM | `2*n_panel` |
| `unit_qty` (derived) | Số lượng đơn vị (kg/m2/m/cái) | **Tự động từ `calc_pattern`** | `(width/1000) * weight_per_unit` |
| `line_total` (derived) | Thành tiền (VND) | **Tự động từ `unit_qty * qty * unit_price`** | `3.0168 * 1 * 113000` |

Trong đó 3 trường `width`, `height`, `qty` là **công thức FB do người dùng viết**, còn `unit_qty` và `line_total` được sinh tự động bởi `BomOrchestrator` dựa trên `calc_pattern` (LENGTH_TO_WEIGHT, AREA, LENGTH_ONLY, COUNT).

### P.2.2 Kiến trúc Formula Set `BOM_LINE`

Mỗi dòng Bom Item không phải là 1 formula đơn lẻ, mà là **1 Formula Set** gồm 3 formulas:

```python
# Mỗi dòng Bom Item sinh ra 3 formulas trong Formula Set:
FORMULA_SET_BOM_LINE = [
    {"name": "{slug}__width",       "formula": "W_mm - 2*$OFFSET_FIXED"},
    {"name": "{slug}__height",      "formula": "TransomHeight_mm - $OFFSET_FIXED"},
    {"name": "{slug}__qty",         "formula": "2*n_panel"},
]
```

### P.2.3 Ví dụ cụ thể: dòng `kinh_tren` (dòng 70)

**Input (người cấu hình BOM viết):**

| Field | Công thức gốc |
|---|---|
| `slug` | `kinh_tren` |
| `width` | `W_mm - 2*$OFFSET_FIXED` |
| `height` | `TransomHeight_mm - $OFFSET_FIXED` |
| `qty` | `1` |
| `calc_pattern` | `AREA` |
| `item_code` | `KINH-LOWE-24` |
| `price_base_item` | `-` (giá tra trực tiếp từ item_code) |

**Bước 1: VariableResolver resolve `$VAR` và `items.slug.field`**

```
$OFFSET_FIXED → 50 (resolve từ AL Profile System qua doctype_query)
TransomHeight_mm → 600 (input từ user)
W_mm → 2400 (input từ user)

width  = "W_mm - 2*$OFFSET_FIXED"     → "2400 - 2*50"      → eval = 2300
height = "TransomHeight_mm - $OFFSET_FIXED" → "600 - 50"   → eval = 550
qty    = "1"                           → "1"                → eval = 1
```

**Bước 2: FormulaEngine nhận được gì?**

```python
# Context truyền vào Engine:
context = {
    "W_mm": 2400,
    "H_mm": 2600,
    "TransomHeight_mm": 600,
    "n_panel": 2,
    "OFFSET_FIXED": 50,
    "OFFSET_GLASS": 90,
    "OFFSET_FRAME": 48,
    "OFFSET_DO_NGANG": 48,
    # ... các biến khác
}

# Formulas cho dòng kinh_tren (3 formulas):
formulas_for_kinh_tren = [
    {"name": "kinh_tren__width",   "formula": "W_mm - 2*OFFSET_FIXED"},
    {"name": "kinh_tren__height",  "formula": "TransomHeight_mm - OFFSET_FIXED"},
    {"name": "kinh_tren__qty",     "formula": "1"},
]
```

**Bước 3: Engine tính toán**

```
┌─────────────────────────────────────────────────────────────────┐
│  DAG execution order (Kahn topological sort):                   │
│                                                                 │
│  Node 1: kinh_tren__width                                       │
│    formula: "W_mm - 2*OFFSET_FIXED"                             │
│    lookup context → W_mm=2400, OFFSET_FIXED=50                  │
│    eval: 2400 - 2*50 = 2400 - 100 = 2300                        │
│    → context["kinh_tren__width"] = 2300                         │
│                                                                 │
│  Node 2: kinh_tren__height                                      │
│    formula: "TransomHeight_mm - OFFSET_FIXED"                   │
│    lookup context → TransomHeight_mm=600, OFFSET_FIXED=50       │
│    eval: 600 - 50 = 550                                         │
│    → context["kinh_tren__height"] = 550                         │
│                                                                 │
│  Node 3: kinh_tren__qty                                         │
│    formula: "1"                                                 │
│    eval: 1                                                      │
│    → context["kinh_tren__qty"] = 1                              │
└─────────────────────────────────────────────────────────────────┘
```

**Bước 4: Sau Engine — BomOrchestrator tính derived fields (B4 output)**

Đây là bước **ngoài Engine**, do `lookup_calc_pattern` xử lý bằng Python thuần:

```python
# Sau khi Engine trả về result, BomOrchestrator dùng kết quả để tính unit_qty và line_total:

# Dòng kinh_tren: calc_pattern = AREA
width     = result.values["kinh_tren__width"]     # = 2300
height    = result.values["kinh_tren__height"]    # = 550
qty       = result.values["kinh_tren__qty"]       # = 1
item_code = "KINH-LOWE-24"                         # từ Bom Item
unit_price = frappe.get_value("Item Price", ..., "price_list_rate")  # = 1,150,000

# lookup_calc_pattern("AREA", width=2300, height=550):
unit_qty = (2300/1000) * (550/1000) = 1.265  # m2

# Tính line_total:
line_total = unit_qty * qty * unit_price
           = 1.265 * 1 * 1,150,000
           = 1,454,750  VND
```

### P.2.4 Toàn bộ 17 dòng → 51 formulas + context

```
INPUT (17 dòng Bom Item)
│
│  Mỗi dòng có: slug, width, height, qty, calc_pattern, item_code, ...
│
▼
┌──────────────────────────────────────────────────────────────────┐
│  BƯỚC 1: VARIABLE RESOLVER (resolve $VAR + items.slug.field)     │
│                                                                  │
│  Dòng 10: khung_ngang_tren  → width=2400, height=None, qty=1     │
│  Dòng 40: do_ngang          → width=W_mm-2*48=2304, qty=1        │
│  Dòng 50: canh_ngang        → width=W_mm/2-48=1152, qty=4        │
│  Dòng 70: kinh_tren         → width=2400-100=2300,               │
│                                height=600-50=550, qty=1          │
│  Dòng 90: nep_kinh_tren     → width=2*(2300+550)=5700, qty=2     │
│  ...                                                             │
│                                                                  │
│  TỔNG: 17 dòng × 3 fields (width/height/qty) = 51 formulas       │
│         (một số dòng height=None → bỏ qua field đó)              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BƯỚC 2: CHILD TABLE CONFIG → FLEXIBLE FORMULA ENGINE                       │
│                                                                             │
│  child_table_config = ChildTableConfig(                                     │
│      table_name="items",                                                    │
│      id_field="slug",        # ← key để cross-row reference                 │
│      rows=[                                                                 │
│          {"slug": "khung_ngang_tren", "idx": 0,                             │
│           "formulas": {                                                     │
│               "width": "W_mm",                                              │
│               "height": None,                                               │
│               "qty": "1"                                                    │
│           }},                                                               │
│          {"slug": "do_ngang", "idx": 3,                                     │
│           "formulas": {                                                     │
│               "width": "W_mm - 2*OFFSET_DO_NGANG",                          │
│               "height": None,                                               │
│               "qty": "1"                                                    │
│           }},                                                               │
│          {"slug": "kinh_tren", "idx": 6,                                    │
│           "formulas": {                                                     │
│               "width": "W_mm - 2*OFFSET_FIXED",                             │
│               "height": "TransomHeight_mm - OFFSET_FIXED",                  │
│               "qty": "1"                                                    │
│           }},                                                               │
│          {"slug": "nep_kinh_tren", "idx": 8,                                │
│           "formulas": {                                                     │
│               "width": "2*(items.kinh_tren.width + items.kinh_tren.height)",│
│               "height": None,                                               │
│               "qty": "2"                                                    │
│           }},                                                               │
│          ... 13 dòng còn lại ...                                            │
│      ]                                                                      │
│  )                                                                          │
│                                                                             │
│  LƯU Ý: Cross-row reference "items.kinh_tren.width"                         │
│  → VariableResolver normalize thành "kinh_tren__width"                      │
│  → DAG tự động phát hiện dependency:                                        │
│      nep_kinh_tren__width PHỤ THUỘC kinh_tren__width,                       │
│      kinh_tren__height                                                      │
│  → Engine tự động sắp xếp: tính kinh_tren trước,                            │
│    nep_kinh_tren sau                                                        │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  BƯỚC 3: ENGINE EVALUATE                                         │
│                                                                  │
│  EngineConfig(                                                   │
│      child_table_configs=[child_config],                         │
│      extra_context={  # ← global context, chung cho mọi dòng     │
│          "W_mm": 2400,                                           │
│          "H_mm": 2600,                                           │
│          "TransomHeight_mm": 600,                                │
│          "n_panel": 2,                                           │
│          "OFFSET_FIXED": 50,                                     │
│          "OFFSET_FRAME": 48,                                     │
│          "OFFSET_GLASS": 90,                                     │
│          "OFFSET_DO_NGANG": 48,                                  │
│          "aluminum_color": "WHITE",                              │
│          "aluminum_origin": "IMPORT",                            │
│      },                                                          │
│      on_error="raise",                                           │
│      deterministic=True,                                         │
│  )                                                               │
│                                                                  │
│  engine = FlexibleFormulaEngine(config)                          │
│  result = engine.calculate(extra_context)                        │
│                                                                  │
│  result.values = {                                               │
│      "khung_ngang_tren__width": 2400,                            │
│      "khung_ngang_tren__qty": 1,                                 │
│      "do_ngang__width": 2304,                                    │
│      "do_ngang__qty": 1,                                         │
│      "kinh_tren__width": 2300,                                   │
│      "kinh_tren__height": 550,                                   │
│      "kinh_tren__qty": 1,                                        │
│      "nep_kinh_tren__width": 5700,  # ← cross-row đã resolve     │
│      "nep_kinh_tren__qty": 2,                                    │
│      ...                                                         │
│  }                                                               │
│                                                                  │
│  KẾT QUẢ: ~51 giá trị trong result.values                        │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  BƯỚC 4: BOMORCHESTRATOR TÍNH DERIVED FIELDS (Python, ngoài FB)  │
│                                                                  │
│  for each dòng Bom Item:                                         │
│      width  = result.values[f"{slug}__width"]                    │
│      height = result.values.get(f"{slug}__height")               │
│      qty    = result.values[f"{slug}__qty"]                      │
│                                                                  │
│      # Gọi lookup_calc_pattern (dispatch table Python thuần)     │
│      unit_qty = lookup_calc_pattern(                             │
│          calc_pattern, width=width, height=height,               │
│          weight_per_unit=item.weight_per_unit                    │
│      )                                                           │
│                                                                  │
│      # Resolve unit_price                                        │
│      if price_base_item:                                         │
│          unit_price = get_item_price(price_base_item, ...)       │
│      else:                                                       │
│          unit_price = get_item_price(item_code, ...)             │
│                                                                  │
│      # Tính thành tiền                                           │
│      line_total = unit_qty * qty * unit_price                    │
│                                                                  │
│  Kết quả mỗi dòng: {width, height, qty, unit_qty, unit_price,    │
│                      line_total, item_code, ...}                 │
└──────────────────────────────────────────────────────────────────┘
```

### P.2.5 Vì sao unit_qty và line_total không phải là Formula Engine?

```
┌─────────────────────────────────────────────────────────────────┐
│  LÝ DO THIẾT KẾ: TÁCH ENGINE KHỎI DB QUERY                      │
│                                                                 │
│  Engine (FB) làm:                    Python (AlumGlass) làm:    │
│  ✓ Parse công thức toán học         ✓ Query Item Price từ DB   │
│  ✓ Build DAG dependency              ✓ Dispatch calc_pattern   │
│  ✓ Evaluate biểu thức số học         ✓ Gom cost bucket         │
│  ✓ Cross-row reference               ✓ Tra Rule Dynamic Item   │
│                                                                 │
│  NGUYÊN TẮC: Engine chỉ làm toán. Engine không query DB.        │
│  unit_price đến từ DB query → không nên đưa vào Engine.         │
│  unit_qty đến từ calc_pattern (có thể phức tạp, cần             │
│  weight_per_unit từ Item master) → dispatch table Python thuần. │
└─────────────────────────────────────────────────────────────────┘
```

---

## P.3 SO SÁNH 3 CON ĐƯỜNG → ENGINE

### P.3.1 Bom Line: `$VAR` + `items.slug.field`

```
INPUT:
  width = "W_mm - 2*$OFFSET_FIXED"
  dòng nep_kinh_tren: width = "2*(items.kinh_tren.width + items.kinh_tren.height)"

RESOLVE:
  1. VariableResolver.resolve("$OFFSET_FIXED") → 50
  2. VariableResolver.normalize("items.kinh_tren.width") → "kinh_tren__width"
     (slug "kinh_tren" + "__" + field "width")
  3. DAG phát hiện: nep_kinh_tren__width phụ thuộc kinh_tren__width, kinh_tren__height
     → Engine tự động sắp xếp thứ tự tính

FORMULAS (đưa vào EngineConfig.child_table_configs):
  {"name": "kinh_tren__width",     "formula": "W_mm - 2*OFFSET_FIXED"},
  {"name": "kinh_tren__height",    "formula": "TransomHeight_mm - OFFSET_FIXED"},
  {"name": "nep_kinh_tren__width", "formula": "2*(kinh_tren__width + kinh_tren__height)"},

CONTEXT (truyền vào extra_context):
  {W_mm: 2400, OFFSET_FIXED: 50, TransomHeight_mm: 600, ...}
```

### P.3.2 Cost Template: bare name

```
INPUT:
  TONG_VL = "VL_NHOM + VL_KINH + VL_VTP + VL_PK"
  NC_SX   = "NC_SX_PCT * TONG_VL"

RESOLVE:
  1. KHÔNG có VariableResolver — tất cả biến đã có sẵn giá trị
  2. VL_NHOM, VL_KINH... → từ B5 gom bucket (Python loop)
  3. NC_SX_PCT → từ AL Product Type, đã resolve ở B2
  4. TONG_VL → vừa được dòng trên tính ra → DAG tự động sắp xếp

FORMULAS (đưa vào EngineConfig.global_formulas):
  {"name": "TONG_VL",     "formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK"},
  {"name": "NC_SX",       "formula": "NC_SX_PCT * TONG_VL"},
  {"name": "GIA_VAT",     "formula": "GIA_BAN + VAT"},

CONTEXT (truyền vào extra_context):
  {VL_NHOM: 4895431, VL_KINH: 6330980, NC_SX_PCT: 0.08, ...}
```

### P.3.3 Bảng so sánh

| Tiêu chí | Bom Line | Cost Template | Global Formula bất kỳ |
|---|---|---|---|
| **Cú pháp biến** | `$OFFSET_FRAME`, `items.x.y` | `VL_NHOM`, `NC_SX_PCT` | Tùy ý |
| **Resolver** | VariableResolver (6 levels) | Không — inject thẳng | Không |
| **Engine config** | `child_table_configs` | `global_formulas` | `global_formulas` |
| **Cross-row** | Có (slug-based) | Không | Không |
| **DAG** | Tự động phát hiện dependency | Tự động từ thứ tự formulas | Tự động |
| **Derived fields** | unit_qty, line_total (Python) | Không có | Không có |
| **DB query trong Engine** | Không | Không | Không |
| **Ai resolve biến** | Engine + VariableResolver | BomOrchestrator B5 trước khi gọi Engine | Người gọi Engine |

---

## P.4 VÍ DỤ END-TO-END: TỪ INPUT → GIA_VAT

### Input (từ Quotation)

```python
user_inputs = {
    "W_mm": 2400,
    "H_mm": 2600,
    "TransomHeight_mm": 600,
    "n_panel": 2,
    "aluminum_color": "WHITE",
    "aluminum_origin": "IMPORT",
    "aluminum_thickness": 20,
    "aluminum_surface": "POWDER_COATED",
    "profile_system": "XINGFA_55",
    "product_type": "DOOR",
}
```

### Phase B1-B2: Gather inputs + resolve scoped vars

```python
# B1: Merge inputs
inputs = {**user_inputs}

# B2: Resolve scoped variables từ AL Profile System + AL Product Type
# (dùng BatchBindingResolver - 1 query thay vì N query)
scoped = resolve_all_bindings_batch(bindings, {
    "product_type": "DOOR",
    "profile_system": "XINGFA_55",
})

# Kết quả scoped:
inputs.update({
    "OFFSET_FRAME": 48,
    "OFFSET_GLASS": 90,
    "OFFSET_FIXED": 50,
    "OFFSET_DO_NGANG": 48,
    "NC_SX_PCT": 0.08,
    "NC_LD_PCT": 0.12,
    "PROFIT_MARGIN": 0.16,
})

# Global vars (vẫn từ Formula Global Variable):
inputs.update({
    "VAT_RATE": 0.10,
    "OH_VC_PCT": 0.03,
    "OH_QLY_PCT": 0.03,
})
```

### Phase B3-B4: Build EngineConfig → Calculate Bom Items

```python
# B3: Build ChildTableConfig từ 17 dòng AL Bom Item
child_config = ChildTableConfig(
    table_name="items",
    id_field="slug",
    rows=[...]  # 17 rows, mỗi row 1-3 formulas
)

# Tổng cộng: 51 formulas (17 dòng × ~3 fields)
#  - 17 width formulas
#  - 5 height formulas (chỉ dòng KINH có height)
#  - 17 qty formulas
#  - 12 derived formulas (OFFSET_*, ...) từ Bom Items

engine_config = EngineConfig(
    child_table_configs=[child_config],
    extra_context=inputs,   # chứa tất cả biến đã resolve
    on_error="raise",
    deterministic=True,
)

engine = FlexibleFormulaEngine(engine_config)
bom_result = engine.calculate(inputs)
# → bom_result.values: dict ~100 keys
#   khung_ngang_tren__width: 2400
#   khung_ngang_tren__qty: 1
#   kinh_tren__width: 2300
#   kinh_tren__height: 550
#   nep_kinh_tren__width: 5700  ← cross-row đã resolve
#   ...
```

### Phase B5: Gom cost bucket (Python loop, ngoài Engine)

```python
buckets = {"VL_NHOM": 0, "VL_KINH": 0, "VL_VTP": 0, "VL_PK": 0}

for row in bom_items:
    slug = row["slug"]
    bucket_code = row["cost_bucket"]  # VL_NHOM, VL_KINH, ...
    
    # Lấy giá trị đã tính từ Engine
    width = bom_result.values.get(f"{slug}__width")
    height = bom_result.values.get(f"{slug}__height")
    qty = bom_result.values.get(f"{slug}__qty")
    
    # Tính derived fields
    unit_qty = lookup_calc_pattern(row["calc_pattern"], width, height, ...)
    unit_price = get_item_price(row["item_code"], ...)
    line_total = unit_qty * qty * unit_price
    
    # Gom vào bucket
    buckets[bucket_code] += line_total

# Kết quả:
# buckets = {
#     "VL_NHOM": 4895431,   # 8 dòng nhôm
#     "VL_KINH": 6330980,   # 2 dòng kính
#     "VL_VTP": 836400,     # 4 dòng VTP
#     "VL_PK": 2000000,     # 3 dòng PK
# }
```

### Phase B6: Cost Template → Engine lần 2

```python
# Merge context cho Cost Template
cost_context = {**inputs, **buckets}
# → cost_context = {
#     W_mm: 2400, ..., 
#     VL_NHOM: 4895431, VL_KINH: 6330980, ...,
#     NC_SX_PCT: 0.08, VAT_RATE: 0.10, ...
# }

# Build global_formulas từ 14 dòng Cost Template
global_formulas = [
    {"name": "TONG_VL",     "formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK"},
    {"name": "TONG_M2",     "formula": "(W_mm/1000)*(H_mm/1000)"},
    {"name": "NC_SX",       "formula": "NC_SX_PCT * TONG_VL"},
    {"name": "NC_LD",       "formula": "NC_LD_PCT * TONG_VL"},
    # ... 10 dòng nữa ...
    {"name": "GIA_VAT",     "formula": "GIA_BAN + VAT"},
]

cost_config = EngineConfig(
    global_formulas=global_formulas,
    extra_context=cost_context,
    on_error="raise",
    deterministic=True,
)

engine2 = FlexibleFormulaEngine(cost_config)
cost_result = engine2.calculate(cost_context)
# → cost_result.values["GIA_VAT"] = 22,717,289
```

### Sơ đồ tổng thể dòng dữ liệu

```
Quotation Inputs                    Master Data (DB)
{W_mm, H_mm, color, ...}           {AL Bom Item, AL Cost Bucket,
                                    AL Calculation Rule, Item Price, ...}
         │                                    │
         └────────────┬───────────────────────┘
                      ▼
         ┌─────────────────────────┐
         │   BomOrchestrator       │
         │                         │
         │  B0: Version pinning    │
         │  B1: Gather inputs      │
         │  B2: Resolve scoped     │──────► BatchBindingResolver
         │  B3: Build Config       │             (1 query)
         │      ↓                  │
         │  ┌───────────────────┐  │
         │  │ FormulaEngine #1  │  │  ◄── Engine: 51 formulas Bom Items
         │  │ (Bom Items)       │  │      ChildTableConfig
         │  │ → ~100 values     │  │
         │  └───────┬───────────┘  │
         │          │              │
         │  B5: Gom bucket         │──────► Python loop 17 dòng
         │      ↓                  │         (lookup_calc_pattern +
         │  ┌───────────────────┐  │          get_item_price)
         │  │ FormulaEngine #2  │  │  ◄── Engine: 14 formulas Cost
         │  │ (Cost Template)   │  │      Template
         │  │ → GIA_VAT         │  │      global_formulas
         │  └───────────────────┘  │
         │                         │
         │  B7: Save Snapshot      │──────► SnapshotManager.submit()
         └────────────┬────────────┘
                      │
                      ▼
         GIA_VAT = 22,717,289 VND
         ConfigSnapshot (audit trail, tái lập được)
```

---

## P.5 TÓM TẮT

| Câu hỏi | Trả lời |
|---|---|
| **Bom Line nhiều trường formula trên 1 row thì Engine xử lý thế nào?** | Mỗi field (width/height/qty) là 1 formula riêng với naming convention `{slug}__{field}`. Tất cả được BomOrchestrator tự build thủ công rồi truyền vào `FormulaEngine` (dùng raw engine, không dùng ChildTableConfig). Cross-row reference (`items.kinh_tren.width`) được normalize thành `kinh_tren__width`. |
| **unit_qty và line_total có phải formula không?** | Đây là **synthetic formulas** — không có sẵn trong Bom Item DB, mà được BomOrchestrator tự sinh ra trong B3 dựa trên `calc_pattern`. Chúng là formulas thực sự (được Engine evaluate), nhưng công thức do dev viết chứ không do người dùng cấu hình. |
| **Bare name, $VAR, slug reference khác gì nhau khi vào Engine?** | Khác ở lớp resolve. Nhưng khi vào Engine, tất cả đều là **formula string + context dict**. Engine không biết biến từng là `$VAR` hay slug reference. |
| **Tại sao gọi Engine 2 lần (B4 + B6)?** | Vì 2 tập formulas khác loại: Bom Items dùng `FormulaEngine` trực tiếp (multi-field per row), Cost Template dùng `global_formulas` (flat). Và B6 cần kết quả B5 (gom bucket) — tức là có bước Python ở giữa. |
| **Ai tạo ra từng formula dict `{name, formula}`?** | **Developer viết code thủ công trong BomOrchestrator.** Không có cơ chế tự động nào đọc raw Bom Item data rồi sinh formulas. Xem P.6. |

---

## P.6 AI TẠO RA FORMULAS? — PHÂN TÍCH CHI TIẾT

### P.6.1 Câu hỏi

> "Cần tự viết code để tạo công thức formulas hay engine tự tạo ra từng công thức cụ thể cho width, height, qty...?"

**Trả lời ngắn: Developer phải tự viết code. Engine chỉ evaluate, không generate.**

### P.6.2 Ba mức độ tự động hóa của Formula Builder

Có 3 cơ chế tạo formulas trong hệ sinh thái FB, mỗi cái có mức độ tự động khác nhau:

```
MỨC ĐỘ TỰ ĐỘNG HÓA
────────────────────

  CAO  ┌──────────────────────────────────────────────────────────┐
       │ ③ ChildTableConfig + FlexibleFormulaEngine               │
       │    ──────────────────────────────────────────             │
       │   Dùng cho pattern: 1 công thức / 1 dòng                  │
       │   VD: Cost Template (global_formulas)                     │
       │                                                           │
       │   👤 Bạn khai báo: ChildTableConfig(formula_field="...",  │
       │                     id_field="...")                       │
       │   🤖 Engine tự động: loop rows, build {name, formula}     │
       │                                                           │
       │   ⚠️ Giới hạn: 1 formula/row, tên biến = prefix+row_id,  │
       │     inject literal (không DAG), không cross-row reference │
       └──────────────────────────────────────────────────────────┘

 TRUNG ┌──────────────────────────────────────────────────────────┐
 BÌNH  │② VariableResolver.build_cross_ref_engine()               │
       │    ────────────────────────────────────────              │
       │   Đọc formula_fields từ Settings → tự loop rows trong doc│
       │                                                          │
       │   🤖 Engine tự động: build {lr}__{field} cho mỗi dòng   │
       │   🤖 Tự normalize: items.slug.field → slug__field       │
       │                                                          │
       │    ⚠️ Giới hạn: gắn với Frappe doc/row object,           │
       │     không tạo được synthetic formulas (unit_qty, ...),   │
       │     không tách biệt khỏi frm.doc context                 │
       └──────────────────────────────────────────────────────────┘

 THẤP  ┌──────────────────────────────────────────────────────────┐
       │① Developer tự viết loop (BomOrchestrator B3)             │
       │    ────────────────────────────────────────              │
       │   Dùng cho: Bom Items (nhiều field formula/row,          │
       │     cross-row reference, synthetic formulas)             │
       │                                                          │
       │   👤 Dev tự viết: for item in bom_items:                 │
       │       for field in ["width","height","qty"]:             │
       │           formulas.append({name: f"{slug}__{field}",     │
       │                            formula: normalize(expr)})    │
       │                                                          │
       │   👤 Dev tự tạo synthetic: unit_qty, line_total          │
       │   🤖 Engine: DAG + topological sort + evaluate           │
       └──────────────────────────────────────────────────────────┘
```

### P.6.3 Vì sao Bom Line rơi vào mức ① (hoàn toàn thủ công)?

| Yêu cầu của Bom Item | ③ ChildTableConfig | ② VariableResolver | ① Tự code |
|---|---|---|---|
| Nhiều formula/row (width, height, qty) | ❌ Chỉ 1 `formula_field` | ✅ Đọc formula_fields từ Settings | ✅ Tự loop |
| Synthetic formulas (unit_qty, total_qty, line_total) | ❌ Không có cơ chế | ❌ Không có cơ chế | ✅ Tự viết |
| Cross-row reference (`items.kinh_tren.width`) | ❌ Inject literal → không có DAG | ✅ normalize + DAG | ✅ Gọi `_normalize_cross_ref()` |
| Tên formula pattern `{slug}__{field}` | ❌ Chỉ là `{prefix}{id_field}` | ✅ Đúng pattern | ✅ Tự build |
| Tách biệt khỏi Frappe doc (làm việc với dict) | ✅ | ❌ Gắn với `frm.doc` | ✅ |
| Inject literals từ Item master (weight_per_unit, ...) | ❌ Chỉ từ row fields | ❌ Auto-inject tất cả row fields | ✅ Tự control |

**Kết luận:** Bom Item cần **tất cả 6 yêu cầu**. Không cơ chế tự động nào đáp ứng đủ → phải tự code.

### P.6.4 Code thực tế: BomOrchestrator B3 — ~60 dòng Python

Đây là code mà developer phải viết trong `BomOrchestrator.b3_build_bom_engine()`:

```python
def b3_build_bom_engine(self):
    """
    B3: Xây dựng FormulaEngine cho Bom Items.

    ⚠️ TOÀN BỘ PHẦN BUILD FORMULAS LÀ CODE THỦ CÔNG.
    Engine (FormulaEngine) chỉ nhận list formulas đã được build sẵn.
    """
    formulas = []
    self.bom_inputs = dict(self.inputs)  # copy inputs vào context

    # ──────────────────────────────────────────────────────
    #  VÒNG LẶP NGOÀI: Developer tự viết, duyệt 17 dòng
    # ──────────────────────────────────────────────────────
    for item in self.bom_items:
        slug = item["slug"]          # VD: "kinh_tren"
        literals = self.row_literals.get(slug, {})

        # (a) INJECT LITERALS — Developer tự quyết định field nào cần inject
        #     Mục đích: đưa weight_per_unit, unit_price, calc_pattern...
        #     vào context để các formula khác dùng
        for key in ("weight_per_unit", "unit_price", "calc_pattern",
                     "glass_thick", "glass_type"):
            if key in literals:
                self.bom_inputs[f"{slug}__{key}"] = literals[key]

        # (b) BUILD FORMULAS TỪ BOM ITEM FIELDS — Developer tự viết
        #     Mỗi dòng Bom Item có 3 formula fields: width, height, qty
        #     → Mỗi field trở thành 1 formula dict {name, formula}
        formula_fields = {
            "width":  item.get("width"),    # "W_mm - 2*OFFSET_FIXED"
            "height": item.get("height"),   # "TransomHeight_mm - OFFSET_FIXED"
            "qty":    item.get("qty"),      # "1"
        }
        for field_name, expr in formula_fields.items():   # VÒNG LẶP LỒNG
            if expr and str(expr).strip():
                # Normalize cross-row reference:
                # "items.kinh_tren.width" → "kinh_tren__width"
                normalized = _normalize_cross_ref(str(expr))
                formulas.append({                         # ← TỰ BUILD TỪNG DICT
                    "name": f"{slug}__{field_name}",      #    "kinh_tren__width"
                    "formula": normalized,                #    "W_mm - 2*OFFSET_FIXED"
                })

        # (c) SYNTHETIC FORMULAS — Developer tự viết công thức
        #     Những formula này KHÔNG tồn tại trong Bom Item DB
        #     Chúng được SINH RA TỪ CODE dựa trên calc_pattern

        # unit_qty = lookup_calc_pattern(pattern, width, height, weight_per_unit, ...)
        formulas.append({
            "name": f"{slug}__unit_qty",
            "formula": (
                f"lookup_calc_pattern({slug}__calc_pattern, "
                f"{slug}__width, {slug}__height, "
                f"{slug}__weight_per_unit, 1, 1, 1, 1)"
            ),
        })

        # total_qty = unit_qty × qty
        formulas.append({
            "name": f"{slug}__total_qty",
            "formula": f"{slug}__unit_qty * ({slug}__qty or 1)",
        })

        # line_total = total_qty × unit_price
        formulas.append({
            "name": f"{slug}__line_total",
            "formula": f"{slug}__total_qty * ({slug}__unit_price or 0)",
        })

    # ──────────────────────────────────────────────────────
    #  KẾT QUẢ: 17 dòng × ~6 formulas = ~102 formula dicts
    #  ĐƯỢC BUILD HOÀN TOÀN THỦ CÔNG BỞI DEVELOPER
    # ──────────────────────────────────────────────────────

    self.bom_engine = FormulaEngine(
        formulas=formulas,         # ← List[Dict] do dev tạo
        context=self.bom_inputs,   # ← Dict do dev build
        on_error="raise",
        deterministic=True,
    )
```

### P.6.5 Phân công trách nhiệm

| Việc | Ai làm? | Tự động? |
|---|---|---|
| **Loop qua 17 dòng** Bom Item | **Developer** (`for item in self.bom_items`) | ❌ |
| **Loop qua các field** (width, height, qty) cho mỗi dòng | **Developer** (vòng lặp lồng) | ❌ |
| **Build formula dict** `{"name": "kinh_tren__width", "formula": "..."}` | **Developer** (`formulas.append(...)`) | ❌ |
| **Normalize cross-ref** `items.kinh_tren.width` → `kinh_tren__width` | **Developer** gọi helper `_normalize_cross_ref()` (regex 1 dòng) | Bán tự động |
| **Inject literals** (weight_per_unit, unit_price...) vào context | **Developer** (chọn field nào để inject) | ❌ |
| **Tạo synthetic formulas** (unit_qty, total_qty, line_total) | **Developer** (dựa trên calc_pattern) | ❌ |
| **Build DAG** từ list formulas | **Engine** | ✅ |
| **Topological sort** thứ tự tính | **Engine** | ✅ |
| **Detect cross-row dependency** | **Engine** (từ DAG) | ✅ |
| **Evaluate** từng formula với context | **Engine** | ✅ |
| **Trả về** `result.values` | **Engine** | ✅ |

### P.6.6 `_normalize_cross_ref()` — helper 1 dòng

```python
import re

def _normalize_cross_ref(expr: str) -> str:
    """Chuyển items.slug.field → slug__field trong công thức.

    VD: "2*(items.kinh_tren.width + items.kinh_tren.height)"
      → "2*(kinh_tren__width + kinh_tren__height)"
    """
    return re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)
```

**Lưu ý quan trọng:** Hàm này chỉ **biến đổi text trong formula string**. Nó KHÔNG tạo ra formula dict. Nó KHÔNG tự động phát hiện dependency. Việc DAG phát hiện `nep_kinh_tren__width` phụ thuộc `kinh_tren__width` là do Engine làm sau khi nhận toàn bộ formulas — không liên quan đến hàm này.

### P.6.7 Tại sao ChildTableConfig KHÔNG dùng được cho Bom Items?

`ChildTableConfig` (của FlexibleFormulaEngine) có vẻ giống với những gì Bom Items cần, nhưng thực tế nó xử lý pattern **đơn giản hơn nhiều**:

```python
# ChildTableConfig chỉ hỗ trợ pattern NÀY:
ChildTableConfig(
    table_key="items",
    formula_field="formula",     # ← CHỈ 1 cột chứa công thức
    id_field="line_ref",         # ← Tên biến = giá trị cột này
    row_fields=["qty", "price"], # ← Inject literal, KHÔNG DAG
    output_field="amount",       # ← Ghi kết quả vào cột này
)

# Engine tự động build:
# for row in rows:
#     name = row[id_field]                  # "K1"
#     formula = row[formula_field]           # "qty * rate"
#     formulas.append({"name": "K1", "formula": "qty * rate"})
#     context["K1__qty"] = row["qty"]       # INJECT LITERAL
#     context["K1__price"] = row["price"]   # INJECT LITERAL
```

**Khác biệt cốt lõi với Bom Items:**

| | ChildTableConfig | Bom Items cần |
|---|---|---|
| Số formula/row | 1 | 3-6 |
| Row fields xử lý | **Inject literal** (thay thế text) | **DAG variable** (tham chiếu chéo được) |
| Cross-row reference | ❌ Không thể (đã là literal) | ✅ Cần `items.x.y` → `x__y` |
| Synthetic formulas | ❌ Không có | ✅ unit_qty, total_qty, line_total |
| Tên formula | `prefix + id_field` | `{slug}__{field}` |

**Vì ChildTableConfig inject row fields dưới dạng literal**, nên `items.kinh_tren.width` khi gặp trong công thức của dòng `nep_kinh_tren` **sẽ không resolve được** — vì `kinh_tren__width` đã bị thay bằng số `2300` trong context, không còn là biến DAG. Điều này phá vỡ cross-row dependency.

### P.6.8 So sánh với Cost Template (dùng global_formulas)

Cost Template đơn giản hơn → tận dụng được `global_formulas`:

```python
# Cost Template: Developer chỉ cần build list formula từ DB
global_formulas = []
for line in cost_template_lines:           # ← Vẫn phải tự loop
    global_formulas.append({               # ← Vẫn phải tự build
        "name": line["line_code"],         #    "TONG_VL"
        "formula": line["calc_formula"],   #    "VL_NHOM + VL_KINH + VL_VTP + VL_PK"
    })

# Nhưng không cần:
# - Vòng lặp lồng (chỉ 1 formula/dòng)
# - Synthetic formulas
# - Normalize cross-ref (không có items.x.y)
# - Inject literals (tất cả đã có trong extra_context)
```

### P.6.9 Tóm tắt

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI TẠO FORMULAS?                             │
│                                                                 │
│  ┌─────────────────────┐     ┌─────────────────────────────────┐│
│  │  Bom Item DB        │     │  BomOrchestrator (DEV CODE)     ││
│  │                     │     │                                 ││
│  │  slug: kinh_tren    │     │  for item in bom_items:         ││
│  │  width: "W_mm-100"  │────→│    for f in [width,height,qty]: ││
│  │  height: "H_mm-50"  │     │      formulas.append({          ││
│  │  qty: "1"           │     │        name: f"{slug}__{f}",    ││
│  │  calc_pattern: AREA │     │        formula: normalize(expr) ││
│  └─────────────────────┘     │      })                         ││
│                              │    formulas.append({            ││
│  ┌─────────────────────┐     │      name: f"{slug}__unit_qty", ││
│  │  Cost Template DB   │     │      formula: "lookup_calc..."  ││
│  │                     │     │    })                           ││
│  │  line_code: TONG_VL │     │    ...                          ││
│  │  formula: "VL+..."   │────→│  engine = FormulaEngine(       ││
│  └─────────────────────┘     │    formulas=formulas,           ││
│                              │    context=self.bom_inputs      ││
│                              │  )                              ││
│                              └──────────────┬──────────────────┘│
│                                             │                   │
│                              ┌──────────────▼──────────────────┐│
│                              │  FormulaEngine (FB - BẤT BIẾN)  ││
│                              │                                 ││
│                              │  🤖 Build DAG                   ││
│                              │  🤖 Topological sort            ││
│                              │  🤖 Evaluate từng node          ││
│                              │  🤖 Trả về result.values        ││
│                              └─────────────────────────────────┘│
│                                                                 │
│  👤 = Developer viết code       🤖 = Engine tự động            │
└─────────────────────────────────────────────────────────────────┘
```

> **Nguyên tắc:** Engine giống như máy tính bỏ túi — nó nhận công thức và số, rồi tính ra kết quả. Còn việc **viết ra công thức gì, dùng biến gì, thứ tự ra sao** là việc của developer. Không có "AI" hay "magic" nào tự động dịch từ Bom Item data structure sang list of formulas.

---

## P.7 NHIỀU BẢNG CON THAM CHIẾU CHÉO + 1 ROW NHIỀU FORMULA

### P.7.1 Câu hỏi

> "Nếu nhiều bảng con tham chiếu chéo với nhau và 1 row nhiều formula thì sao? Ở giao diện vẫn dùng công thức dạng slug hoặc idx để hạn chế lỗi gõ sai công thức?"

**Trả lời ngắn:**
- **Về engine:** Cơ chế `_normalize_cross_ref` mở rộng tự nhiên cho nhiều bảng — `{table}.{slug}.{field}` → `{slug}__{field}`. Tất cả bảng con được "làm phẳng" (flatten) vào chung 1 namespace. Engine chỉ nhìn thấy tên biến `{slug}__{field}`, không biết và không cần biết biến đó đến từ bảng nào.
- **Về UI:** VẪN dùng slug hoặc idx để autocomplete — đây chính là cơ chế chống gõ sai. Monaco `CompletionRegistry` với trigger `.` và `[` sẽ gợi ý chính xác tên bảng → slug → field.

### P.7.2 Ví dụ mở rộng: Cửa nhôm 2 cánh có 3 bảng con

Giả sử tách BOM thành 3 bảng con thay vì 1 bảng `items` duy nhất:

```
┌─────────────────────────────────────────────────────────────────┐
│  AL BOM (parent doctype)                                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Bảng con 1: profiles (Profile nhôm)                      │  │
│  │  ┌──────────────┬────────┬────────┬──────┬──────────────┐ │  │
│  │  │ slug         │ width  │ height │ qty  │ calc_pattern │ │  │
│  │  ├──────────────┼────────┼────────┼──────┼──────────────┤ │  │
│  │  │ khung_ngang  │ W_mm   │ -      │ 2    │ LENGTH_TO_WT │ │  │
│  │  │ khung_dung   │ H_mm   │ -      │ 2    │ LENGTH_TO_WT │ │  │
│  │  │ do_ngang     │ W_mm-96│ -      │ 1    │ LENGTH_TO_WT │ │  │
│  │  │ canh_ngang   │ W_mm/2-│ -      │ 4    │ LENGTH_TO_WT │ │  │
│  │  │              │ 48     │        │      │              │ │  │
│  │  │ nep_kinh_tren│ 2*(    │ -      │ 2    │ LENGTH_TO_WT │ │  │
│  │  │              │ glasses│        │      │              │ │  │
│  │  │              │ .panel_│        │      │              │ │  │
│  │  │              │ top.w  │        │      │              │ │  │
│  │  │              │ +      │        │      │              │ │  │
│  │  │              │ glasses│        │      │              │ │  │
│  │  │              │ .panel_│        │      │              │ │  │
│  │  │              │ top.h) │        │      │              │ │  │
│  │  └──────────────┴────────┴────────┴──────┴──────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Bảng con 2: glasses (Kính)                               │  │
│  │  ┌──────────────┬────────────────────┬─────────┬──────┐   │  │
│  │  │ slug         │ width              │ height  │ qty  │   │  │
│  │  ├──────────────┼────────────────────┼─────────┼──────┤   │  │
│  │  │ panel_top    │ W_mm-2*OFFSET_FIXED│ TH_mm-  │ 1    │   │  │
│  │  │              │                    │ OFFSET_ │      │   │  │
│  │  │              │                    │ FIXED   │      │   │  │
│  │  │ panel_bottom │ profiles.canh_ngang│ H_mm-TH_│ 2    │   │  │
│  │  │              │ .width - OFFSET_GL │ mm-     │      │   │  │
│  │  │              │                    │ OFFSET_ │      │   │  │
│  │  │              │                    │ GL      │      │   │  │
│  │  └──────────────┴────────────────────┴─────────┴──────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Bảng con 3: accessories (Phụ kiện)                       │  │
│  │  ┌──────────────┬────────────────────────────┬──────┐     │  │
│  │  │ slug         │ qty                        │ ...  │     │  │
│  │  ├──────────────┼────────────────────────────┼──────┤     │  │
│  │  │ ban_le       │ roundup(H_mm/700,0)        │      │     │  │
│  │  │              │ * profiles.canh_dung.qty/2 │      │     │  │
│  │  │ khoa         │ profiles.canh_dung.qty/2   │      │     │  │
│  │  │ tay_nam      │ profiles.canh_dung.qty/2   │      │     │  │
│  │  └──────────────┴────────────────────────────┴──────┘     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Điểm quan trọng trong ví dụ này:**

| Dòng | Công thức | Loại tham chiếu |
|---|---|---|
| `profiles.nep_kinh_tren.width` | `2*(glasses.panel_top.width + glasses.panel_top.height)` | **Cross-table**: profiles → glasses |
| `glasses.panel_bottom.width` | `profiles.canh_ngang.width - OFFSET_GL` | **Cross-table**: glasses → profiles |
| `accessories.ban_le.qty` | `roundup(H_mm/700,0) * profiles.canh_dung.qty/2` | **Cross-table**: accessories → profiles |

### P.7.3 Cách Engine xử lý: Flatten tất cả về 1 namespace

**Nguyên tắc:** Engine không biết đến khái niệm "bảng con". Tất cả formulas từ mọi bảng được gom vào **1 list phẳng duy nhất**, với naming convention `{slug}__{field}`. Slug là unique toàn cục (được đảm bảo bởi AL Slug Library).

```
BA BẢNG CON TRONG DB              SAU KHI FLATTEN → 1 LIST FORMULAS
─────────────────────              ─────────────────────────────────

profiles:                         profiles__khung_ngang__width  = "W_mm"
  khung_ngang:                    profiles__khung_ngang__qty    = "2"
    width = "W_mm"                profiles__khung_dung__width   = "H_mm"
    qty = "2"                     profiles__khung_dung__qty     = "2"
  khung_dung:                     profiles__do_ngang__width     = "W_mm - 2*OFFSET_DO_NGANG"
    width = "H_mm"                profiles__do_ngang__qty       = "1"
    qty = "2"                     profiles__canh_ngang__width   = "W_mm/n_panel - OFFSET_FRAME"
  do_ngang:                       profiles__canh_ngang__qty     = "2*n_panel"
    width = "W_mm - 2*48"        profiles__nep_kinh_tren__width = "2*(panel_top__width + panel_top__height)"
    qty = "1"                     profiles__nep_kinh_tren__qty  = "2"
  canh_ngang:                     
    width = "W_mm/2 - 48"        glasses__panel_top__width      = "W_mm - 2*OFFSET_FIXED"
    qty = "4"                     glasses__panel_top__height     = "TransomHeight_mm - OFFSET_FIXED"
  nep_kinh_tren:                  glasses__panel_top__qty        = "1"
    width = "2*(glasses.panel_top.w + glasses.panel_top.h)"
    qty = "2"                     glasses__panel_bottom__width   = "canh_ngang__width - OFFSET_GL"
                                  glasses__panel_bottom__height  = "H_mm - TransomHeight_mm - OFFSET_GL"
glasses:                          glasses__panel_bottom__qty     = "n_panel"
  panel_top:
    width = "W_mm - 2*50"        accessories__ban_le__qty       = "roundup(H_mm/700,0) * canh_dung__qty / 2"
    height = "TransomH - 50"     accessories__khoa__qty          = "canh_dung__qty / 2"
    qty = "1"                     accessories__tay_nam__qty       = "canh_dung__qty / 2"
  panel_bottom:
    width = "profiles.canh_ngang.w - 90"
    height = "H_mm - TransomH - 90"
    qty = "n_panel"

accessories:
  ban_le:
    qty = "roundup(H/700,0) * profiles.canh_dung.qty / 2"
  khoa:
    qty = "profiles.canh_dung.qty / 2"
  tay_nam:
    qty = "profiles.canh_dung.qty / 2"
```

### P.7.4 Slug namespace: scoped theo bảng con, không phải unique toàn cục

**Vấn đề bạn nêu ra là chính xác.** Trong thiết kế hiện tại, AL Slug Library có `slug` là unique — nhưng đó là unique **trong toàn bộ hệ thống** (1 bảng `items` duy nhất). Khi mở rộng ra nhiều bảng con, không thể ép mọi slug unique toàn cục vì:

```
Tình huống thực tế:

  profiles:                           glasses:
    canh_ngang   ← slug "canh_ngang"    canh_ngang   ← ĐÂY LÀ KÍNH, không phải nhôm!
    canh_dung                           canh_duoi
    nep_kinh                            ...

→ Nếu slug unique toàn cục: "canh_ngang" chỉ được dùng 1 lần → vô lý!
  Kính cũng có "cánh ngang" (panel ngang của cửa kính).
  Không thể đặt tên khác đi chỉ vì trùng bảng!
```

**Giải pháp đúng: Slug unique trong phạm vi 1 bảng con, normalize giữ lại table prefix.**

#### Cơ chế: 2 lớp unique

```
LỚP 1 — AL SLUG LIBRARY (global registry)
──────────────────────────────────────────
  Mỗi slug có 2 thuộc tính:
    slug:     "canh_ngang"
    category: "NHOM" | "KINH" | "VTP" | "PK"

  Unique constraint: (slug) — nhưng đây là registry TOÀN CỤC.
  Một slug "canh_ngang" với category="NHOM" chỉ tồn tại 1 lần.

  ⚠️ Nhưng: "canh_ngang" với category="KINH" cũng không được phép
     vì slug field là unique — không phải (slug, category) unique.


LỚP 2 — TRONG PHẠM VI 1 BẢN GHI BOM (runtime)
────────────────────────────────────────────────
  Mỗi bảng con có namespace riêng:

  profiles:
    canh_ngang   ← OK, slug này thuộc bảng profiles
    canh_dung    ← OK

  glasses:
    panel_top    ← KHÔNG dùng "canh_ngang" vì slug đã đăng ký
    panel_bottom ← trong AL Slug Library với category=KINH

  → Trong thực tế, mỗi vai trò vật lý có slug RIÊNG.
    Không có chuyện 2 bảng cùng dùng 1 slug.
    "canh_ngang" luôn là nhôm → chỉ có trong profiles.
    "panel_top" luôn là kính → chỉ có trong glasses.


KẾT LUẬN THIẾT KẾ:
────────────────────
  Với AlumGlass, slug unique toàn cục LÀ ĐỦ vì:
  - Mỗi slug map 1-1 với 1 vai trò vật lý
  - "canh_ngang" = nhôm, "panel_top" = kính → không bao giờ trùng
  - AL Slug Library với unique constraint trên `slug` đảm bảo điều này

  NHƯNG: Về mặt kiến trúc tổng quát, nếu sau này có nhu cầu
  slug trùng tên giữa các bảng, giải pháp là GIỮ TABLE PREFIX
  trong engine namespace (xem P.7.4b bên dưới).
```

#### P.7.4b — Phương án dự phòng: Table-scoped slug với prefix

Nếu tương lai cần hỗ trợ slug trùng tên giữa các bảng con:

```python
# ── OPTION A: Slug unique toàn cục (HIỆN TẠI) ──
# AL Slug Library: slug field unique
# → profiles.canh_ngang.width → canh_ngang__width
# → glasses.panel_top.width   → panel_top__width
# ✅ Đơn giản, tên biến ngắn
# ❌ Không cho phép trùng slug giữa các bảng

def _normalize_cross_ref_v1(expr: str) -> str:
    """Bỏ table name — dùng khi slug unique toàn cục."""
    return re.sub(r'\w+\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)


# ── OPTION B: Slug unique trong bảng, giữ prefix (DỰ PHÒNG) ──
# AL Slug Library: unique constraint trên (table_name, slug) hoặc
#   mỗi bảng con tự quản lý slug namespace
# → profiles.canh_ngang.width → profiles__canh_ngang__width
# → glasses.canh_ngang.width  → glasses__canh_ngang__width
# ✅ Linh hoạt, không lo collision
# ❌ Tên biến dài hơn

def _normalize_cross_ref_v2(expr: str) -> str:
    """Giữ table name làm prefix — dùng khi slug scoped theo bảng."""
    return re.sub(r'(\w+)\.(\w[\w-]*)\.(\w+)', r'\1__\2__\3', expr)

# VD:
# "profiles.canh_ngang.width" → "profiles__canh_ngang__width"
# "glasses.panel_top.height"  → "glasses__panel_top__height"
```

**Bảng so sánh 2 phương án:**

| Tiêu chí | Option A (hiện tại) | Option B (dự phòng) |
|---|---|---|
| **Slug constraint** | Unique toàn cục | Unique trong bảng |
| **Tên biến Engine** | `canh_ngang__width` | `profiles__canh_ngang__width` |
| **Cross-table ref** | `glasses.panel_top.width` → `panel_top__width` | `glasses.panel_top.width` → `glasses__panel_top__width` |
| **Collision risk** | Có (nếu 2 bảng cùng slug) | Không |
| **Độ dài tên biến** | Ngắn | Dài hơn |
| **Phù hợp khi** | Mỗi slug = 1 vai trò vật lý duy nhất | Slug chỉ là tên gọi, có thể trùng context |
| **AlumGlass dùng?** | ✅ Hiện tại | Chỉ khi cần mở rộng |

> **Khuyến nghị:** Bắt đầu với Option A (đơn giản). Nếu sau này phát sinh nhu cầu slug trùng bảng, migrate sang Option B bằng cách đổi 1 dòng regex trong `_normalize_cross_ref()` + chạy script update formula text trong DB. Không cần thay đổi kiến trúc Engine.

### P.7.5 Code BomOrchestrator: Build formulas từ nhiều bảng con

```python
def b3_build_bom_engine(self):
    """
    B3: Build formulas từ NHIỀU bảng con.
    Cơ chế giống hệt 1 bảng — chỉ thêm vòng lặp ngoài cùng.
    """
    formulas = []
    self.bom_inputs = dict(self.inputs)

    # ── Định nghĩa các bảng con và field mapping ──
    TABLE_CONFIGS = {
        "profiles": {
            "formula_fields": ["width", "height", "qty"],  # Các field chứa công thức
            "literal_fields": ["weight_per_unit", "unit_price", "calc_pattern",
                               "glass_thick", "glass_type"],
            "calc_pattern": True,    # Bảng này có synthetic formulas
        },
        "glasses": {
            "formula_fields": ["width", "height", "qty"],
            "literal_fields": ["unit_price", "glass_thick", "glass_type"],
            "calc_pattern": "AREA",  # Tất cả dòng kính dùng AREA, không cần synthetic
        },
        "accessories": {
            "formula_fields": ["qty"],           # Chỉ có qty là công thức
            "literal_fields": ["unit_price"],
            "calc_pattern": "COUNT",             # Tất cả phụ kiện dùng COUNT
        },
    }

    # ── VÒNG LẶP NGOÀI CÙNG: duyệt từng bảng con ──
    for table_name, table_config in TABLE_CONFIGS.items():
        rows = getattr(self, f"bom_{table_name}")  # self.bom_profiles, self.bom_glasses, ...

        # ── VÒNG LẶP GIỮA: duyệt từng dòng trong bảng ──
        for item in rows:
            slug = item["slug"]  # Unique toàn cục: "khung_ngang", "panel_top", "ban_le"
            literals = self.row_literals.get(slug, {})

            # (a) Inject literal fields
            for key in table_config["literal_fields"]:
                if key in literals:
                    self.bom_inputs[f"{slug}__{key}"] = literals[key]

            # (b) Build formulas từ formula_fields của dòng
            for field_name in table_config["formula_fields"]:
                expr = item.get(field_name)
                if expr and str(expr).strip():
                    # ⚡ Cùng 1 hàm normalize, xử lý MỌI cross-reference
                    #    profiles.canh_ngang.width  → canh_ngang__width
                    #    glasses.panel_top.height   → panel_top__height
                    #    accessories.ban_le.qty     → ban_le__qty
                    normalized = _normalize_cross_ref(str(expr))
                    formulas.append({
                        "name": f"{slug}__{field_name}",
                        "formula": normalized,
                    })

            # (c) Synthetic formulas (chỉ cho bảng có calc_pattern động)
            if table_config.get("calc_pattern") == True:
                formulas.append({
                    "name": f"{slug}__unit_qty",
                    "formula": f"lookup_calc_pattern({slug}__calc_pattern, "
                               f"{slug}__width, {slug}__height, "
                               f"{slug}__weight_per_unit, 1, 1, 1, 1)",
                })
                formulas.append({
                    "name": f"{slug}__total_qty",
                    "formula": f"{slug}__unit_qty * ({slug}__qty or 1)",
                })
                formulas.append({
                    "name": f"{slug}__line_total",
                    "formula": f"{slug}__total_qty * ({slug}__unit_price or 0)",
                })

    # ── KẾT QUẢ ──
    # Tất cả formulas từ 3 bảng con → 1 list phẳng
    # Engine build DAG tự động, phát hiện cross-table dependency
    self.bom_engine = FormulaEngine(
        formulas=formulas,        # ← ~80 formula dicts từ 3 bảng
        context=self.bom_inputs,  # ← context chứa tất cả literals
        on_error="raise",
        deterministic=True,
    )
```

### P.7.6 `_normalize_cross_ref()` — 1 hàm, 2 chế độ

```python
import re

# ═══════════════════════════════════════════════════════════════
# OPTION A: Slug unique toàn cục → bỏ table name (HIỆN TẠI)
# ═══════════════════════════════════════════════════════════════

def _normalize_cross_ref(expr: str) -> str:
    """Chuyển {table}.{slug}.{field} → {slug}__{field}.

    Dùng khi slug unique TOÀN CỤC (AL Slug Library có unique constraint
    trên field slug). Table name chỉ có ý nghĩa ở UI, Engine không cần.

    VD:
      "profiles.canh_ngang.width"     → "canh_ngang__width"
      "glasses.panel_top.height"      → "panel_top__height"
      "items.kinh_tren.width"         → "kinh_tren__width"
      "2*(glasses.panel_top.width + glasses.panel_top.height)"
        → "2*(panel_top__width + panel_top__height)"
    """
    return re.sub(r'\w+\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)


# ═══════════════════════════════════════════════════════════════
# OPTION B: Slug unique trong bảng → giữ table prefix (DỰ PHÒNG)
# ═══════════════════════════════════════════════════════════════

def _normalize_cross_ref_scoped(expr: str) -> str:
    """Chuyển {table}.{slug}.{field} → {table}__{slug}__{field}.

    Dùng khi slug chỉ unique TRONG PHẠM VI 1 BẢNG CON.
    Table name trở thành namespace prefix trong Engine.

    VD:
      "profiles.canh_ngang.width" → "profiles__canh_ngang__width"
      "glasses.canh_ngang.width"  → "glasses__canh_ngang__width"
      → 2 biến KHÁC NHAU dù cùng slug "canh_ngang"
    """
    return re.sub(r'(\w+)\.(\w[\w-]*)\.(\w+)', r'\1__\2__\3', expr)
```

**Cách chuyển đổi giữa 2 option:** Chỉ cần đổi 1 dòng regex. Không cần sửa Engine, không cần sửa DAG, không cần sửa code BomOrchestrator (vì code chỉ gọi `_normalize_cross_ref()`). Nếu migrate, cần chạy script cập nhật formula text trong DB:

```sql
-- Migrate từ Option A → Option B:
-- Thay thế {slug}__{field} → {table}__{slug}__{field} trong tất cả công thức
-- (cần script Python để biết slug nào thuộc bảng nào)
```

### P.7.7 DAG tự động phát hiện cross-table dependency

```
Sau khi flatten tất cả formulas vào 1 list, Engine build DAG:

┌────────────────────────────────────────────────────────────────────┐
│  DAG (Engine tự động)                                              │
│                                                                    │
│  profiles__khung_ngang__width ──┐                                  │
│  profiles__khung_ngang__qty   ──┤                                  │
│  profiles__do_ngang__width    ──┤                                  │
│  profiles__canh_ngang__width  ──┼────┐                             │
│  profiles__canh_ngang__qty    ──┤    │                             │
│  profiles__canh_dung__width   ──┤    │                             │
│  profiles__canh_dung__qty     ──┘    │                             │
│                                      │  ← Cross-table dependency!  │
│  glasses__panel_top__width    ───────┤    glasses.panel_bottom.w   │
│  glasses__panel_top__height   ──┐    │    phụ thuộc                │
│  glasses__panel_top__qty      ──┤    │    profiles.canh_ngang.w    │
│                                  │    │                             │
│  glasses__panel_bottom__width ──┤    │    profiles.nep_kinh_tren.w │
│    phụ thuộc: canh_ngang__width◄┘    │    phụ thuộc                │
│  glasses__panel_bottom__height ──┐   │    glasses.panel_top.w/h    │
│  glasses__panel_bottom__qty   ──┤   │                             │
│                                  │   │                             │
│  profiles__nep_kinh_tren__width──┼───┘                             │
│    phụ thuộc: panel_top__width  ◄┘                                 │
│             panel_top__height                                      │
│  profiles__nep_kinh_tren__qty ───┐                                  │
│                                  │                                  │
│  accessories__ban_le__qty ───────┤                                  │
│    phụ thuộc: canh_dung__qty    ◄┘  ← Cross-table: accessories     │
│  accessories__khoa__qty ────────┐      phụ thuộc profiles           │
│    phụ thuộc: canh_dung__qty    │                                   │
│  accessories__tay_nam__qty ─────┘                                   │
│                                                                    │
│  TOPOLOGICAL ORDER Engine tự sắp xếp:                              │
│    1. profiles__* (các dòng không phụ thuộc)                       │
│    2. glasses__panel_top__* (chỉ phụ thuộc input)                  │
│    3. glasses__panel_bottom__* (phụ thuộc profiles)                │
│    4. profiles__nep_kinh_tren__* (phụ thuộc glasses) ← ENGINE      │
│       TỰ ĐỘNG PHÁT HIỆN: phải tính glasses trước profiles dòng này │
│    5. accessories__* (phụ thuộc profiles)                          │
│    6. Synthetic formulas: unit_qty → total_qty → line_total        │
└────────────────────────────────────────────────────────────────────┘
```

### P.7.8 UI: Slug/Idx autocomplete để chống gõ sai

Đây là lý do UI **VẪN dùng cú pháp `{table}.{slug}.{field}`** thay vì `{slug}__{field}`:

```
┌─────────────────────────────────────────────────────────────────┐
│  Monaco Editor trong form AL Bom Item                           │
│                                                                 │
│  Người dùng gõ:  profiles.canh_ngang.width + glasses.█          │
│                                                       │         │
│                                                       ▼         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🔍 Gợi ý (CompletionRegistry — trigger character ".")    │  │
│  │                                                          │  │
│  │ 📁 profiles        ← Bảng con                            │  │
│  │ 📁 glasses          ← Bảng con                            │  │
│  │ 📁 accessories      ← Bảng con                            │  │
│  │ 📁 items            ← Bảng con                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Sau khi chọn "glasses." → hiện tiếp:                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🔍 Gợi ý (trigger ".")                                   │  │
│  │                                                          │  │
│  │ glasses.panel_top      ← Slug trong bảng glasses         │  │
│  │ glasses.panel_bottom   ← Slug trong bảng glasses         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Sau khi chọn "glasses.panel_top." → hiện tiếp:                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🔍 Gợi ý (trigger ".")                                   │  │
│  │                                                          │  │
│  │ glasses.panel_top.width    = Float (mm)                  │  │
│  │ glasses.panel_top.height   = Float (mm)                  │  │
│  │ glasses.panel_top.qty      = Float (cái)                 │  │
│  │ glasses.panel_top.glass_thick = Float (mm)               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Kết quả: glasses.panel_top.width ← CHÍNH XÁC, không thể sai   │
└─────────────────────────────────────────────────────────────────┘
```

**Cơ chế autocomplete hoạt động qua 3 bước gõ `.`:**

```
Bước 1: Gõ <table>.
        → ContextBuilder trả về siblingItems: các bảng con của parent doctype
        → Mỗi bảng là 1 suggestion với tên table field

Bước 2: Gõ <table>.<slug>.
        → ContextBuilder lọc siblingItems theo table name
        → Mỗi dòng trong bảng đó là 1 suggestion với slug làm identifier
        (slug được lấy từ id_field đã cấu hình trong initGridField)

Bước 3: Gõ <table>.<slug>.<field>.
        → ContextBuilder lọc siblingItems theo table + slug
        → Mỗi formula field + literal field của dòng đó là 1 suggestion
```

### P.7.9 Luồng dữ liệu đầy đủ: UI → DB → Code → Engine

```
┌─────────────────────────────────────────────────────────────────┐
│  BƯỚC 1: NGƯỜI DÙNG VIẾT CÔNG THỨC (UI — Monaco Editor)       │
│                                                                 │
│  Người dùng gõ trong field "width" của dòng nep_kinh_tren:      │
│                                                                 │
│    2 * (glasses.panel_top.width + glasses.panel_top.height)     │
│         │                                                       │
│         └── Gõ "." → autocomplete hiện gợi ý:                   │
│             glasses (bảng con) → panel_top (slug) → width (field)
│                                                                 │
│  📌 Cú pháp: glasses.panel_top.width                            │
│     (có table.slug.field → rõ ràng, chống sai)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ Lưu vào DB
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  BƯỚC 2: LƯU TRONG DB (AL Bom Item)                            │
│                                                                 │
│  profiles.nep_kinh_tren:                                        │
│    slug: "nep_kinh_tren"                                        │
│    width: "2*(glasses.panel_top.width + glasses.panel_top.height)"
│    qty: "2"                                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ BomOrchestrator đọc từ DB
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  BƯỚC 3: BomOrchestrator B3 — Build formulas (CODE)            │
│                                                                 │
│  for table_name in ["profiles", "glasses", "accessories"]:      │
│      for item in rows:                                          │
│          slug = item["slug"]                                    │
│          for field_name in ["width", "height", "qty"]:          │
│              expr = item.get(field_name)                        │
│              normalized = _normalize_cross_ref(expr)            │
│              # "glasses.panel_top.width" → "panel_top__width"   │
│              # "glasses.panel_top.height" → "panel_top__height" │
│              formulas.append({                                  │
│                  "name": f"{slug}__{field_name}",               │
│                  "formula": normalized,                         │
│              })                                                 │
│                                                                 │
│  Kết quả normalize:                                             │
│    {name: "nep_kinh_tren__width",                               │
│     formula: "2*(panel_top__width + panel_top__height)"}        │
│                                                                 │
│  📌 Cú pháp đã normalize: panel_top__width                      │
│     (bỏ table name, dùng slug__field → phẳng cho Engine)        │
└────────────────────────────┬────────────────────────────────────┘
                             │ Truyền vào FormulaEngine
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  BƯỚC 4: FormulaEngine — DAG + Evaluate (FB - TỰ ĐỘNG)         │
│                                                                 │
│  Engine nhận list formulas:                                     │
│    {"name": "panel_top__width",  "formula": "W_mm - 2*50"},     │
│    {"name": "panel_top__height", "formula": "TransomH - 50"},   │
│    {"name": "nep_kinh_tren__width",                              │
│     "formula": "2*(panel_top__width + panel_top__height)"},     │
│    ...                                                           │
│                                                                 │
│  Engine:                                                        │
│    1. Parse formulas → phát hiện nep_kinh_tren__width           │
│       phụ thuộc panel_top__width, panel_top__height             │
│    2. Topological sort → tính panel_top trước, nep_kinh_tren sau│
│    3. Evaluate:                                                 │
│       panel_top__width  = 2400 - 100 = 2300                    │
│       panel_top__height = 600 - 50 = 550                       │
│       nep_kinh_tren__width = 2*(2300 + 550) = 5700             │
│                                                                 │
│  📌 Engine không biết panel_top thuộc bảng glasses              │
│     Engine không biết nep_kinh_tren thuộc bảng profiles         │
│     Engine chỉ thấy tên biến và dependency                      │
└─────────────────────────────────────────────────────────────────┘
```

### P.7.10 Bảng so sánh: 1 bảng con vs nhiều bảng con

| Tiêu chí | 1 bảng `items` (v28 hiện tại) | Nhiều bảng (mở rộng tương lai) |
|---|---|---|
| **Cú pháp UI** | `items.kinh_tren.width` | `glasses.panel_top.width`, `profiles.canh_ngang.width` |
| **Slug namespace** | Unique trong 1 bảng | **Unique toàn cục** (AL Slug Library đảm bảo) |
| **Normalize** | `items.kinh_tren.width` → `kinh_tren__width` | `glasses.panel_top.width` → `panel_top__width` |
| **Số vòng lặp** | 1 (items) | 3 (profiles, glasses, accessories) |
| **Số formula dicts** | ~102 | ~80 (ít hơn vì tách bảng, mỗi bảng ít field hơn) |
| **Cross-reference** | Cùng bảng | Cross-bảng (Engine không phân biệt) |
| **DAG** | Tự động, cùng namespace | **Tự động, cùng namespace** — Engine không biết khác bảng |
| **Code BomOrchestrator** | 1 vòng lặp | 2 vòng lặp lồng (bảng → dòng) |
| **Độ phức tạp code** | Thấp | Trung bình (thêm 1 vòng lặp + config) |

### P.7.11 Tại sao cần giữ cú pháp `{table}.{slug}.{field}` ở UI?

```
┌─────────────────────────────────────────────────────────────────┐
│  SO SÁNH HAI CÁCH VIẾT CÙNG 1 CÔNG THỨC                         │
│                                                                 │
│  Cách A: slug__field (engine format)                            │
│  ─────────────────────────────────────                           │
│    2 * (panel_top__width + panel_top__height)                   │
│                                                                 │
│    ❌ "panel_top" là cái gì? Kính? Nhôm? Phụ kiện?              │
│    ❌ Không có context → khó đọc, khó maintain                  │
│    ❌ Không có autocomplete theo ngữ cảnh bảng                   │
│    ❌ Có 50 slug → gõ "panel" ra 5 kết quả, không biết chọn ai  │
│                                                                 │
│  Cách B: table.slug.field (UI format)                           │
│  ─────────────────────────────────────                           │
│    2 * (glasses.panel_top.width + glasses.panel_top.height)     │
│                                                                 │
│    ✅ "glasses.panel_top.width" → Kính, tấm trên, chiều rộng    │
│    ✅ Autocomplete 3 cấp: bảng → slug → field                   │
│    ✅ Không thể gõ sai: mỗi dấu "." thu hẹp phạm vi             │
│    ✅ Người mới vào đọc hiểu ngay không cần tra cứu             │
│                                                                 │
│  ⚡ Engine không dùng format B. normalize() biến B → A.         │
│     UI giữ format B vì lợi ích con người.                       │
│     Engine dùng format A vì không cần context bảng.             │
└─────────────────────────────────────────────────────────────────┘
```

### P.7.12 Tóm tắt nguyên lý

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   NGUYÊN LÝ 1: UI ≠ Engine                                      │
│   ───────────────────────                                       │
│   UI:      glasses.panel_top.width    (có table context)        │
│   Engine:  panel_top__width           (phẳng, không context)    │
│   (hoặc:    glasses__panel_top__width nếu dùng Option B)        │
│                                                                 │
│   NGUYÊN LÝ 2: Slug namespace                                   │
│   ─────────────────────────────                                  │
│   Option A (hiện tại): Slug unique toàn cục qua AL Slug Library │
│     → {table}.{slug}.{field} → {slug}__{field}                 │
│   Option B (dự phòng): Slug unique trong phạm vi bảng con       │
│     → {table}.{slug}.{field} → {table}__{slug}__{field}        │
│   Cả 2 option đều dùng chung 1 cơ chế normalize.               │
│                                                                 │
│   NGUYÊN LÝ 3: Flatten trước khi vào Engine                     │
│   ────────────────────────────────────                           │
│   N bảng con → 1 list formulas phẳng.                           │
│   Engine không biết đến khái niệm "bảng con".                   │
│                                                                 │
│   NGUYÊN LÝ 4: DAG không quan tâm nguồn gốc biến                │
│   ────────────────────────────────────────                       │
│   Engine chỉ thấy: "A phụ thuộc B, C" → tính B, C trước.       │
│   Không quan tâm A từ bảng nào, B từ bảng nào.                  │
│                                                                 │
│   NGUYÊN LÝ 5: Code dev viết giống hệt dù 1 hay N bảng          │
│   ─────────────────────────────────────────────                  │
│   Chỉ thêm 1 vòng lặp ngoài cùng. Logic normalize, build        │
│   formula, inject literal — giống hệt.                          │
│                                                                 │
│   NGUYÊN LÝ 6: UI giữ table.slug.field để chống gõ sai          │
│   ────────────────────────────────────────────                   │
│   Autocomplete 3 cấp: gõ bảng → hiện slug → gõ field.           │
│   Mỗi dấu "." thu hẹp phạm vi gợi ý, không thể gõ sai.         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## P.8 TIỆN ÍCH MultiTableFormulaBuilder — ĐÓNG GÓI FORMULA BUILDER

### P.8.1 Vấn đề

Qua P.6 và P.7, ta thấy code build formulas từ Bom Items là **boilerplate lặp đi lặp lại**:
vòng lặp ngoài (bảng) → vòng lặp giữa (dòng) → vòng lặp trong (field) → normalize → inject literal → synthetic.
Code này sẽ bị copy-paste ở nhiều nơi: BomOrchestrator, Cost Template engine, custom modules...

**Giải pháp:** Đóng gói thành `MultiTableFormulaBuilder` — một utility class trong chính Formula Builder,
để mọi app (AlumGlass và các app khác) dùng chung, không phải viết lại.

### P.8.2 Vị trí trong Formula Builder

```
formula_builder/
  formula_builder/
    table_formula_builder.py          ← FILE MỚI: MultiTableFormulaBuilder class
    integration.py           ← ĐÃ CẬP NHẬT: export MultiTableFormulaBuilder
    flexible_formula_engine.py
    ...
```

**Import từ app khác:**
```python
from formula_builder.integration import (
    MultiTableFormulaBuilder,
    normalize_scoped,
    synthetic_for_pattern,
    build_engine_from_builder,
)
```

### P.8.3 API Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    MultiTableFormulaBuilder                     │
│                                                                 │
│  __init__(normalize_mode="scoped")                              │
│    → "scoped": giữ table prefix (Option B, AN TOÀN, mặc định)   │
│    → "global": bỏ table prefix (Option A, slug unique toàn cục) │
│    → normalize_fn=... : custom normalize (tối đa linh hoạt)     │
│                                                                 │
│  add_table(                                                     │
│      table_name,           # "profiles"                         │
│      rows,                 # List[dict] dữ liệu dòng            │
│      formula_fields,       # ["width", "height", "qty"]         │
│      id_field="slug",      # Field định danh dòng               │
│      literal_fields=[...], # Field cần inject vào context       │
│      synthetic_formulas=...,# Callback sinh thêm formulas       │
│      formula_builder=...,  # HOẶC: callback thay thế toàn bộ    │
│  ) → self (fluent)                                              │
│                                                                 │
│  build(base_context={}) → (formulas, context)                   │
│    → Trả về Tuple sẵn sàng cho FormulaEngine                    │
│                                                                 │
│  get_var_ref(table, slug, field) → str                          │
│    → "profiles__canh_ngang__width" (scoped mode)                │
│                                                                 │
│  report() → str                                                 │
│    → In cấu trúc builder (debug)                                │
└─────────────────────────────────────────────────────────────────┘
```

### P.8.4 Ví dụ: AlumGlass 3 bảng con

```python
from formula_builder.integration import (
    MultiTableFormulaBuilder,
    synthetic_for_pattern,
    build_engine_from_builder,
)

# ═══ Bước 1: Khởi tạo builder ═══
builder = MultiTableFormulaBuilder(normalize_mode="scoped")  # Option B — an toàn

# ═══ Bước 2: Thêm bảng profiles ═══
builder.add_table(
    table_name="profiles",
    rows=profile_rows,  # List[dict] từ DB
    formula_fields=["width", "height", "qty"],
    literal_fields=["weight_per_unit", "unit_price", "calc_pattern"],
    id_field="slug",
    synthetic_formulas=synthetic_for_pattern,  # ← callback có sẵn trong FB
)

# ═══ Bước 3: Thêm bảng glasses ═══
builder.add_table(
    table_name="glasses",
    rows=glass_rows,
    formula_fields=["width", "height", "qty"],
    literal_fields=["unit_price", "glass_thick", "glass_type"],
    id_field="slug",
    # glasses không cần synthetic vì AREA được tính riêng
)

# ═══ Bước 4: Thêm bảng accessories ═══
builder.add_table(
    table_name="accessories",
    rows=accessory_rows,
    formula_fields=["qty"],           # ← Chỉ có qty là công thức
    literal_fields=["unit_price"],
    id_field="slug",
)

# ═══ Bước 5: Build → Engine ═══
base_inputs = {
    "W_mm": 2400, "H_mm": 2600,
    "TransomHeight_mm": 600, "n_panel": 2,
    "OFFSET_FIXED": 50, "OFFSET_GLASS": 90,
    # ...
}

formulas, context = builder.build(base_context=base_inputs)

# formulas = [
#     {"name": "profiles__khung_ngang__width",  "formula": "W_mm"},
#     {"name": "profiles__khung_ngang__qty",    "formula": "2"},
#     {"name": "profiles__canh_ngang__width",   "formula": "W_mm/2 - OFFSET_FRAME"},
#     {"name": "profiles__nep_kinh_tren__width","formula": "2*(glasses__panel_top__width + glasses__panel_top__height)"},
#     {"name": "glasses__panel_top__width",     "formula": "W_mm - 2*OFFSET_FIXED"},
#     {"name": "glasses__panel_bottom__width",  "formula": "profiles__canh_ngang__width - OFFSET_GL"},
#     {"name": "accessories__ban_le__qty",      "formula": "roundup(H_mm/700,0) * profiles__canh_dung__qty / 2"},
#     {"name": "profiles__canh_ngang__unit_qty","formula": "lookup_calc_pattern(...)"},
#     {"name": "profiles__canh_ngang__line_total","formula": "profiles__canh_ngang__total_qty * (profiles__canh_ngang__unit_price or 0)"},
#     ...
# ]

# context = {
#     "W_mm": 2400, "H_mm": 2600, ...,
#     "profiles__khung_ngang__weight_per_unit": 1.257,
#     "profiles__khung_ngang__unit_price": 113000,
#     "profiles__khung_ngang__calc_pattern": "LENGTH_TO_WEIGHT",
#     ...
# }

engine = FormulaEngine(formulas=formulas, context=context)
result = engine.evaluate(context)

# Hoặc dùng convenience function:
engine, context = build_engine_from_builder(builder, base_inputs)
result = engine.evaluate(context)
```

### P.8.5 Ví dụ: Tự viết synthetic formulas

```python
def my_custom_synthetic(builder, table_name, slug, row, context, var_prefix, **kwargs):
    """Custom synthetic: thêm field đặc biệt cho bảng kính."""
    return [
        {
            "name": f"{var_prefix}__dien_tich",
            "formula": (
                f"({var_prefix}__width/1000) * ({var_prefix}__height/1000)"
            ),
        },
        {
            "name": f"{var_prefix}__line_total",
            "formula": (
                f"{var_prefix}__dien_tich * "
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
    synthetic_formulas=my_custom_synthetic,  # ← custom callback
)
```

### P.8.6 Ví dụ: Override toàn bộ logic build cho 1 bảng

```python
def build_taxes_table(builder, table_name, rows, context):
    """Custom logic build formulas cho bảng thuế (phức tạp, không theo pattern chuẩn)."""
    formulas = []
    for row in rows:
        tax_code = row["tax_code"]
        # Logic đặc biệt: tra tax rate từ DB, kết hợp với điều kiện...
        tax_rate = frappe.db.get_value("Tax Rule", ...)
        formulas.append({
            "name": f"TAX_{tax_code}",
            "formula": f"{tax_rate} * SUBTOTAL",
        })
    return formulas

builder.add_table(
    table_name="taxes",
    rows=tax_rows,
    formula_builder=build_taxes_table,  # ← Override toàn bộ
    # Không cần formula_fields, literal_fields, synthetic_formulas
    # vì formula_builder tự xử lý tất cả
)
```

### P.8.7 Ví dụ: Cost Template (1 bảng, 1 formula/row, không cross-ref)

```python
builder = MultiTableFormulaBuilder(normalize_mode="scoped")

builder.add_table(
    table_name="cost_template",
    rows=cost_template_lines,  # Mỗi dòng có line_code, calc_formula
    formula_fields=["calc_formula"],
    id_field="line_code",
    # Không cần literal_fields (tất cả đã có trong base_context)
    # Không cần synthetic_formulas
)

# Build với context đã có sẵn bucket values
cost_context = {
    "VL_NHOM": 4895431, "VL_KINH": 6330980,
    "NC_SX_PCT": 0.08, "VAT_RATE": 0.10,
    # ...
}

formulas, context = builder.build(base_context=cost_context)

# formulas = [
#     {"name": "cost_template__TONG_VL", "formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK"},
#     {"name": "cost_template__NC_SX",   "formula": "NC_SX_PCT * cost_template__TONG_VL"},
#     {"name": "cost_template__GIA_VAT", "formula": "cost_template__GIA_BAN + cost_template__VAT"},
# ]

# LƯU Ý: Với Cost Template dùng normalize_mode="scoped", các line_code
# được reference là "cost_template__TONG_VL" thay vì "TONG_VL".
# Nếu muốn giữ tên ngắn "TONG_VL", dùng normalize_mode="global".
```

### P.8.8 Bao quát những trường hợp nào?

| Trường hợp | MultiTableFormulaBuilder hỗ trợ? | Cách dùng |
|---|---|---|
| 1 bảng con, 1 formula/row | ✅ | `add_table(formula_fields=["formula"])` |
| 1 bảng con, nhiều formula/row | ✅ | `add_table(formula_fields=["width","height","qty"])` |
| Nhiều bảng con, mỗi bảng nhiều formula | ✅ | Gọi `add_table()` nhiều lần |
| Cross-row reference (cùng bảng) | ✅ | `items.kinh_tren.width` → normalize tự động |
| Cross-table reference (khác bảng) | ✅ | `glasses.panel_top.width` → normalize tự động |
| Synthetic formulas | ✅ | `synthetic_formulas=callback` |
| Literal injection | ✅ | `literal_fields=[...]` |
| Slug scoped theo bảng (Option B) | ✅ | `normalize_mode="scoped"` (mặc định) |
| Slug unique toàn cục (Option A) | ✅ | `normalize_mode="global"` |
| Custom normalize | ✅ | `normalize_fn=my_func` |
| Override toàn bộ logic build | ✅ | `formula_builder=my_func` |
| Phát hiện trùng tên formula | ✅ | Tự động raise ValueError |
| Debug cấu trúc | ✅ | `builder.report()` |
| Build thẳng ra FormulaEngine | ✅ | `build_engine_from_builder(builder, ctx)` |

### P.8.9 So sánh: Trước và sau khi có MultiTableFormulaBuilder

**TRƯỚC (tự code ~60 dòng, copy-paste):**
```python
# BomOrchestrator B3
formulas = []
for item in self.bom_items:
    slug = item["slug"]
    literals = self.row_literals.get(slug, {})
    for key in ("weight_per_unit", "unit_price", "calc_pattern"):
        if key in literals:
            self.bom_inputs[f"{slug}__{key}"] = literals[key]
    for field_name in ["width", "height", "qty"]:
        expr = item.get(field_name)
        if expr and str(expr).strip():
            normalized = _normalize_cross_ref(str(expr))
            formulas.append({"name": f"{slug}__{field_name}", "formula": normalized})
    formulas.append({"name": f"{slug}__unit_qty", "formula": f"lookup_calc_pattern(...)"})
    formulas.append({"name": f"{slug}__total_qty", "formula": f"..."})
    formulas.append({"name": f"{slug}__line_total", "formula": f"..."})
```

**SAU (dùng MultiTableFormulaBuilder, ~15 dòng):**
```python
builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table(
    table_name="items",
    rows=self.bom_items,
    formula_fields=["width", "height", "qty"],
    literal_fields=["weight_per_unit", "unit_price", "calc_pattern"],
    id_field="slug",
    synthetic_formulas=synthetic_for_pattern,
)
formulas, context = builder.build(base_context=self.inputs)
```

**Giảm ~45 dòng boilerplate cho MỖI nơi dùng. Nếu có 3 nơi (BomOrchestrator, Cost Template, Custom Module) → tiết kiệm ~135 dòng.**

### P.8.10 Nguyên tắc: Vẫn cho phép tự code khi cần

`MultiTableFormulaBuilder` không che giấu Engine. Nó chỉ đóng gói phần **build formulas**.
Kết quả trả về là `(formulas, context)` — 2 thứ mà Engine nhận vào.
Nếu logic quá phức tạp, bạn có thể:

1. **Dùng `formula_builder=...`** override toàn bộ cho 1 bảng
2. **Dùng `normalize_fn=...`** custom cách normalize
3. **Không dùng MultiTableFormulaBuilder** — tự build formulas như cũ rồi truyền thẳng vào Engine

```python
# Phương án hybrid: dùng builder cho hầu hết, tự code cho phần đặc biệt
builder = MultiTableFormulaBuilder(normalize_mode="scoped")
builder.add_table("profiles", profile_rows, ["width", "height", "qty"], ...)
builder.add_table("glasses", glass_rows, ["width", "height", "qty"], ...)
# Bảng taxes quá phức tạp → tự code
custom_tax_formulas = build_complex_tax_formulas(tax_rows)
# Build
formulas, context = builder.build(base_inputs)
formulas.extend(custom_tax_formulas)  # ← Merge thủ công
engine = FormulaEngine(formulas=formulas, context=context)
```
