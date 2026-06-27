# AlumGlass ERP v17.0 — Đặc Tả Thiết Kế Chuẩn Triển Khai (FINAL)

> **App name:** `aluglass` (Frappe custom app, chạy trên ERPNext core)
> **Phiên bản:** v17.0 — Kế thừa v16.0
> **Phụ thuộc bắt buộc:** `formula_builder` (Frappe app — Formula Engine v29.1+)
> **Trạng thái:** FINAL — Đặc tả triển khai đầy đủ
> **Tổng DocType:** 34 DocType (thêm 10 so với v16)
> **Phase:** Phase 1–3 + Module mở rộng v17

> *"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi."*

---

## CHANGELOG v17.0 — So với v16.0

v16.0 hoàn chỉnh kiến trúc lõi (1 bảng al_lines, DAG giải quyết thứ tự, glass_thick inject tự động). v17.0 bổ sung toàn bộ các module nghiệp vụ còn thiếu để hệ thống sẵn sàng triển khai thực tế quy mô doanh nghiệp:

| # | Module v17 mới / cải tiến | Mô tả | DocType mới |
|---|---|---|---|
| 1 | **Reporting & Dashboard** | Báo cáo doanh số, phân tích BOM, hiệu suất Sales | 3 DocType |
| 2 | **BOM Version Control** | Lịch sử thay đổi, so sánh phiên bản, rollback BOM | 2 DocType |
| 3 | **Approval Workflow** | Quy trình duyệt BOM mới, giá đặc biệt, discount | 2 DocType |
| 4 | **AL Discount Rule** | Chiết khấu theo khách hàng / dự án / sản lượng | 1 DocType |
| 5 | **Material Planning (MRP Lite)** | Tổng hợp vật tư từ pool Quotation/SO đã chốt | 1 DocType |
| 6 | **Multi Price List** | Nhiều bảng giá bán: retail, project, partner | Dùng ERPNext core |
| 7 | **Notification & Alert Engine** | Cảnh báo giá hết hạn, stock threshold nhôm kính | 1 DocType |
| 8 | **AL Glass Inventory Bridge** | Kết nối kính cắt thực tế → tồn kho Phase 3 | 2 DocType (Phase 3) |
| 9 | **Cost Variance Analysis** | So sánh giá Quotation vs thực tế mua vật tư | 1 DocType |
| 10 | **Sales Analytics Module** | KPI Sales, conversion rate, margin tracking | Frappe Chart + Report |

> **Kế thừa không phá vỡ (Non-Breaking)**
> ✓ Toàn bộ 24 DocType v16 giữ nguyên — v17 CHỈ THÊM, không sửa schema lõi
> ✓ BomOrchestrator 6 bước, ProfileInterpreter 2-pass, VariableResolver inject glass_thick: không thay đổi
> ✓ FormulaEngine DAG, ConfigSnapshot, explain() audit trail: không thay đổi
> ✓ Migration v15→v16 script vẫn có hiệu lực; v17 thêm migration script riêng cho DocType mới

---

## MỤC LỤC

I. Triết lý & Quyết định kiến trúc v17
II. Kiến trúc 6 tầng & Luồng xử lý mở rộng
III. Danh sách 34 DocType
IV. Thiết kế chi tiết từng DocType
V. Custom Fields (cập nhật v17)
VI. Master Data chuẩn v17
VII. Logic nghiệp vụ chi tiết v17
VIII. BomOrchestrator v17 — 6 bước + Module hooks
IX. Reporting & Dashboard — Đặc tả đầy đủ
X. BOM Version Control — Đặc tả đầy đủ
XI. Approval Workflow — Đặc tả đầy đủ
XII. AL Discount Rule — Đặc tả đầy đủ
XIII. Material Planning (MRP Lite) — Đặc tả đầy đủ
XIV. Cost Variance Analysis — Đặc tả đầy đủ
XV. Notification & Alert Engine — Đặc tả đầy đủ
XVI. Sales Analytics Module — Đặc tả đầy đủ
XVII. Phase 3 — AL Glass Inventory Bridge
XVIII. ConfigSnapshot & Audit Trail (v17 bổ sung)
XIX. Luồng UI/Dialog (v17 bổ sung)
XX. Ví dụ tính toán kiểm chứng v17
XXI. Cấu trúc thư mục app v17
XXII. Lộ trình triển khai v17 (Phase 1–4)
XXIII. Rủi ro & Điểm theo dõi v17
XXIV. Phân quyền & Vai trò v17
XXV. Tích hợp luồng ERPNext v17
XXVI. Checklist thiết lập BOM sản phẩm mới v17
XXVII. Sơ đồ ERD & Sequence v17
XXVIII. Phụ lục: Migration v16 → v17

---

## I. TRIẾT LÝ & QUYẾT ĐỊNH KIẾN TRÚC v17

### 1.1 Mười lăm nguyên tắc thiết kế (v17 bổ sung 3 nguyên tắc)

| # | Nguyên tắc | Mô tả | Hệ quả thực tế |
|---|---|---|---|
| 1 | Zero Python trong DB | Không một dòng Python nào lưu trong DB — giữ từ v11 | Đội kỹ thuật setup BOM không cần code |
| 2 | Chọn Item trực tiếp | Chọn thẳng mã Item — giữ từ v11 | Tránh ánh xạ kép khi debug giá |
| 3 | `show_condition` thay `if/elif` | Nhiều dòng cùng vai trò + điều kiện hiển thị — giữ từ v11 | Thêm biến thể = thêm 1 dòng |
| 4 | Tách biệt vật liệu, thống nhất bảng | NHOM/KINH/VTP/PK chung al_lines, sort tự do — v16 | Vừa rõ ràng vừa linh hoạt |
| 5 | DAG là nguồn sự thật về thứ tự tính | Engine tự xây DAG, admin khai báo tự nhiên — v16 | Không bao giờ ép Python làm việc của toán học |
| 6 | Kính đa tấm là tập hợp panel động | 1 dòng kính nở ra N panel tại runtime — v14 | Đáp ứng vách kính nhiều ô |
| 7 | Giá kính tách khỏi kích thước sản xuất | Giá = m² × đơn giá đại diện — v14 | Phase 3 phát triển độc lập |
| 8 | Phụ kiện: mặc định + thay thế | PK Set chuẩn + Sales chọn substitute — v14 | Vừa chuẩn vừa linh hoạt |
| 9 | Phụ thuộc chéo qua context phẳng | `glass_thick_{prefix}` inject, mọi formula đều tham chiếu — v16 | Debug = print(inputs_dict) |
| 10 | Rule là thư viện dùng chung | Rule tái sử dụng giữa nhiều Profile Set — v11 | Khai báo 1 lần, dùng nhiều BOM |
| 11 | Formula Engine là lõi DUY NHẤT | Mọi tính toán qua FormulaEngine — không eval — v14 | Bảo mật, DAG, explain() xuyên suốt |
| 12 | Minh bạch tuyệt đối | ConfigSnapshot + explain() cho mọi con số — v15 | Sales/kế toán tin được số liệu |
| **13** | **Module độc lập, hook không phá lõi** | Module v17 (Reporting, Discount, MRP) kết nối qua hook events và API riêng — không sửa BomOrchestrator | Thêm tính năng = thêm module, không sửa engine lõi |
| **14** | **BOM Version = immutable snapshot** | Mỗi lần publish BOM tạo snapshot bất biến; so sánh diff rõ ràng trước khi apply | Audit trail đầy đủ từ BOM tới giá bán tới hóa đơn |
| **15** | **Approval trước khi hiệu lực** | BOM mới, giá đặc biệt, discount lớn đều cần workflow duyệt trước khi Sales áp dụng | Kiểm soát rủi ro kinh doanh + audit compliance |

### 1.2 Quyết định kiến trúc v16 (kế thừa không đổi)

**QĐ-1: Formula Engine duy nhất** — giữ nguyên từ v15.

**QĐ-2: Không tạo DocType "AL Product"** — giữ nguyên.

**QĐ-3: `show_condition` → nhánh DAG** — giữ nguyên.

**QĐ-4: Panel Expansion — `panel_count_formula`** — giữ nguyên.

**QĐ-5: AL BOM mang `representative_item`** — giữ nguyên.

**QĐ-6: Màu nhôm là biến định giá (Rule LOOKUP), không phải Item Variant** — giữ nguyên.

**QĐ-7: Custom Field `al_*` nhân bản sang SO/SI Item** — giữ nguyên.

**QĐ-8: 1 bảng con `al_lines` thống nhất thay 3 bảng riêng** — giữ nguyên.

**QĐ-9: Biến `glass_thick_{prefix}` tự động inject, không qua VariableResolver** — giữ nguyên.

**QĐ-10: Không bắt buộc thứ tự khai báo — 2-pass scan tên biến** — giữ nguyên.

### 1.3 Quyết định kiến trúc v17 (QĐ-11 đến QĐ-15)

**QĐ-11: Module Pattern — Event Hook thay vì sửa Orchestrator**

Mỗi module v17 (Reporting, Discount, MRP...) đăng ký hook vào BomOrchestrator qua event sau khi calculate() hoàn thành. Orchestrator không biết module; module tự subscribe. Pattern: `after_calculate(result, quotation_item, bom_doc)`. Lý do: bảo vệ engine lõi khỏi feature creep; mỗi module testable độc lập.

**QĐ-12: BOM Version là Immutable Document**

Khi admin nhấn 'Publish BOM', hệ thống tạo AL BOM Version snapshot chứa full JSON của Profile Set, Variable Set, PK Set, Cost Template tại thời điểm đó. Version có hash SHA-256. BOM chính vẫn mutable để sửa; chỉ Version mới là bất biến. Quotation lưu `version_id` thay vì trỏ thẳng BOM để giá cũ không bị ảnh hưởng khi BOM thay đổi.

**QĐ-13: Discount Stack — Không ghép vào Formula Engine**

Chiết khấu (AL Discount Rule) áp dụng SAU khi FormulaEngine tính xong GIA_BAN. Không inject discount vào DAG. Lý do: discount phụ thuộc business logic (hợp đồng, khách VIP, dự án) không phải kỹ thuật sản phẩm; tách biệt giúp audit rõ ràng 'giá kỹ thuật' vs 'giá thương mại'. `GIA_BAN_THUONG_MAI = GIA_BAN × (1 - discount_pct/100)`.

**QĐ-14: MRP Lite — Aggregate, không Manufacturing Order**

AL Material Planning không tạo Manufacturing Order (để Phase 3). MRP Lite chỉ tổng hợp vật tư từ danh sách Quotation/SO đã chọn → xuất ra danh sách mua hàng. Mục tiêu Phase 1-2: giúp mua hàng dự phòng vật tư trước khi đơn hàng chốt chính thức.

**QĐ-15: Cost Variance — So sánh Quotation vs Purchase**

AL Cost Variance so sánh đơn giá vật tư tại thời điểm Quotation (từ ConfigSnapshot) vs đơn giá mua thực tế (từ Purchase Invoice). Chênh lệch được phân loại: normal variance (<5%), caution (5-15%), alert (>15%). Dữ liệu này feed vào Reporting Dashboard.

---

## II. KIẾN TRÚC 6 TẦNG & LUỒNG XỬ LÝ MỞ RỘNG

### 2.1 Sơ đồ 6 tầng

```
TẦNG 6 — MODULE LAYER (★ MỚI v17)
  AL Reporting Engine      — Dashboard, KPI, báo cáo Quotation/SO/SI
  BOM Version Manager      — snapshot, diff, rollback
  Approval Workflow Engine — BOM / giá đặc biệt / discount lớn
  Discount Stack           — AL Discount Rule, áp dụng sau FormulaEngine
  MRP Lite Aggregator      — tổng hợp vật tư từ Quotation pool
  Notification Engine      — cảnh báo giá, tồn kho, deadline
  Cost Variance Analyzer   — so sánh Quotation vs Purchase thực tế
  Sales Analytics Engine   — KPI, conversion, margin per Sales

TẦNG 5 — PRESENTATION (Frappe Web UI)
  BOM Dialog / Glass Selector / PK Substitute UI / Cost Template Selector
  EnrichedExplain          — truy vết số liệu qua explain()
  ★ MỚI: Dashboard Widget / BOM Version Diff UI / Approval Inbox / Discount Selector

TẦNG 4 — ORCHESTRATION (aluglass.engine)
  VariableResolver v2 / ProfileInterpreter v2 / PkResolver / CostAccumulator
  SnapshotBuilder / BomOrchestrator 6 bước
  ★ MỚI: Module Hook Registry — after_calculate() event bus

TẦNG 3 — FORMULA ENGINE (formula_builder) ★ KHÔNG SỬA
  FormulaEngine (DAG, IncrementalContext, explain(), snapshot_with_trace())
  BASE_FUNCS 80+, FormulaValidator, SecurityValidator

TẦNG 2 — RULE ENGINE & VARIABLE BINDING
  AL Calculation Rule (CONSTANT/FORMULA/LOOKUP/THRESHOLD)
  AL Variable Binding (source_type, resolve_priority ASC)
  ★ MỚI: AL Discount Rule (stack, không vào DAG)

TẦNG 1 — MASTER DATA (34 DocType)
  ERPNext core: Item, Brand, Price List, Item Price, Item Group
  aluglass lõi (v16): AL Glass Master, AL Profile Set, AL Profile Line, AL PK Set,
                       AL BOM, AL Cost Template, ConfigSnapshot, ...
  ★ MỚI v17: AL BOM Version, AL BOM Change Log, AL Discount Rule,
              AL Material Plan, AL Material Plan Line, AL Cost Variance,
              AL Alert Config, AL Dashboard Config, AL Sales KPI
```

### 2.2 Luồng xử lý đầy đủ khi Sales nhấn "Tính giá"

```
[1] Sales nhấn "Tính giá" trong BOM Dialog
          │
          ▼
[2] VariableResolver.resolve(quotation_item, bom_doc)
     → inputs_dict đầy đủ (bindings + glass_thick_{prefix} cho mọi dòng KINH)
          │
          ▼
[3] ProfileInterpreter.pass1_scan(al_lines, inputs_dict)
     → variable_registry, panel_counts
          │
          ▼
[4] ProfileInterpreter.pass2_build(al_lines, inputs_dict, ...)
     → all_formulas (NHOM + KINH + aggregates + max_glass_thick + VTP + PK_inline)
     → bucket_acc
          │
          ▼
[5] PkResolver.build_formulas(bom_doc.pk_set, ...)
     → formulas_pk, warnings[]
          │
          ▼
[6] CostAccumulator.build_bucket_and_template_formulas(bucket_acc, cost_template)
     → formulas_bucket, formulas_cost_template
     → FormulaEngine.calculate(inputs_dict)  ← DUY NHẤT 1 LẦN
     → SnapshotBuilder.persist()
          │
          ▼
[Hook A] DiscountStack.apply(result, quotation_item, bom_doc)
     → al_discount_pct, al_gia_thuong_mai, approval check
          │
[Hook B] BOMVersionManager.link_version(quotation_item, bom_doc)
     → al_bom_version (freeze giá theo snapshot version)
          │
[Hook C] CostVarianceAnalyzer.register(quotation_item)
     → đăng ký reference cho so sánh sau Purchase Invoice
          │
[Hook D] NotificationEngine.check_alerts(result, bom_doc)
     → kiểm tra PRICE_CHANGE? LOW_STOCK? VARIANCE_ALERT?
          │
          ▼
[Ghi kết quả vào Quotation Item + hiển thị Dialog]
```

### 2.3 Phụ thuộc chéo Nhôm ↔ Kính — cách DAG xử lý

```
Ví dụ thực tế: 1 cửa có 2 loại kính
  - Kính cánh (kinh_canh): 8.38mm, kích thước W_mm-86 × H_mm-86
  - Kính ô cố định (kinh_oc): 10mm, kích thước khác

inputs_dict sau VariableResolver:
  W_mm = 2500, H_mm = 3100
  glass_thick_kinh_canh = 8.38   ← inject từ GL Glass Master
  glass_thick_kinh_oc   = 10.0   ← inject từ GL Glass Master

Formulas sinh ra (thứ tự khai báo theo sort_order admin):
  # NHOM (sort 10-70) — có thể dùng glass_thick_kinh_canh:
  nhom_0060_active = glass_thick_kinh_canh <= 10.38          # Nẹp mỏng
  nhom_0061_active = glass_thick_kinh_canh > 10.38 and ...   # Nẹp dày
  nhom_0062_active = glass_thick_kinh_oc > 10.38             # Nẹp ô cố định

  # KINH (sort 80-100) — nhưng glass_thick đã inject trước vào inputs:
  kinh_canh_W = W_mm - 86
  kinh_oc_W   = W_mm - 50

  max_glass_thick_mm = max(kinh_canh_0_glass_thick_mm, kinh_oc_0_glass_thick_mm) = 10.0

DAG tính đúng vì glass_thick là inputs (đã inject trước), không phải formula
→ không có circular dependency dù nhôm khai báo trước kính
```

---

## III. DANH SÁCH 34 DOCTYPE

| STT | DocType | Loại | Mục đích | So với v16 |
|---|---|---|---|---|
| 1 | AL Variable Group | Master | Nhóm biến | Không đổi |
| 2 | AL Material Type | Master | Loại vật tư + calc method | Không đổi |
| 3 | AL Glass Type | Master | Phân loại kính | Không đổi |
| 4 | AL Glass Layer Type | Master | Loại lớp kính — Phase 3 | Không đổi |
| 5 | AL Glass Master | Master | Thông số kỹ thuật kính (total_thick_mm) | Không đổi |
| 6 | AL Glass Layer Line | Child | Cấu trúc lớp kính — Phase 3 | Không đổi |
| 7 | AL Product Type | Master | Loại sản phẩm | Không đổi |
| 8 | AL Variable Library | Master | Thư viện biến toàn cục | Không đổi |
| 9 | AL Variable Set | Master | Tập biến cho 1 loại BOM | Không đổi |
| 10 | AL Variable Set Detail | Child | Dòng con Variable Set | Không đổi |
| 11 | AL Variable Binding | Master | Nguồn + thứ tự resolve biến | Không đổi |
| 12 | AL Cost Bucket | Master | Tài khoản chi phí | Không đổi |
| 13 | AL Calculation Rule | Master | Luật tính toán | Không đổi |
| 14 | AL Rule Threshold Row | Child | Bảng ngưỡng | Không đổi |
| 15 | AL Rule Lookup Row | Child | Bảng tra cứu | Không đổi |
| 16 | AL Rule Sequence Item | Child | Danh sách Rule con | Không đổi |
| 17 | AL Profile Line | Child | Dòng vật tư thống nhất (NHOM/KINH/VTP/PK) | Không đổi — lõi v16 |
| 18 | AL Profile Set | Master | Tập hợp al_lines | Không đổi |
| 19 | AL PK Set | Master | Bộ phụ kiện tái sử dụng | Không đổi |
| 20 | AL PK Line | Child | Dòng phụ kiện + substitution | Không đổi |
| 21 | AL BOM | Master | Liên kết Variable Set + Profile Set + PK Set + Cost Template | Không đổi |
| 22 | AL Cost Template | Master | Công thức tính giá thành | Không đổi |
| 23 | AL Cost Template Line | Child | Dòng chi phí | Không đổi |
| 24 | ConfigSnapshot | Master | Lưu tham chiếu EnterpriseSnapshot | Không đổi |
| **25** | **AL BOM Version** | **Master** | Snapshot bất biến của BOM tại thời điểm publish | **★ MỚI v17** |
| **26** | **AL BOM Change Log** | **Child** | Ghi chú thay đổi từng version BOM | **★ MỚI v17** |
| **27** | **AL Discount Rule** | **Master** | Luật chiết khấu theo khách/dự án/sản lượng | **★ MỚI v17** |
| **28** | **AL Discount Rule Line** | **Child** | Bảng tier chiết khấu | **★ MỚI v17** |
| **29** | **AL Material Plan** | **Master** | Kế hoạch vật tư tổng hợp từ Quotation/SO pool | **★ MỚI v17** |
| **30** | **AL Material Plan Line** | **Child** | Dòng vật tư trong kế hoạch | **★ MỚI v17** |
| **31** | **AL Cost Variance** | **Master** | So sánh giá Quotation vs Purchase thực tế | **★ MỚI v17** |
| **32** | **AL Alert Config** | **Master** | Cấu hình cảnh báo giá/tồn kho/workflow | **★ MỚI v17** |
| **33** | **AL Dashboard Config** | **Master** | Cấu hình widget dashboard cho từng vai trò | **★ MỚI v17** |
| **34** | **AL Sales KPI** | **Master** | Đo lường KPI Sales: target, actual, margin | **★ MỚI v17** |

**Tổng: 34 DocType (tăng 10 so với v16 — 24 DocType lõi giữ nguyên, 10 DocType module mới)**

---

## IV. THIẾT KẾ CHI TIẾT TỪNG DOCTYPE

### 4.1 AL Variable Group

| fieldname | fieldtype | Mô tả |
|---|---|---|
| group_code | Data (reqd, unique) | KICH_THUOC, SO_LUONG, VAT_LIEU, CANH_CUA, VACH |
| group_name | Data | |
| sort_order | Int | |

### 4.2 AL Material Type

| fieldname | fieldtype | Mô tả |
|---|---|---|
| type_code | Data (reqd, unique) | NHOM_PROFILE, KINH, VTP, PHU_KIEN |
| type_name | Data | |
| default_bucket | Link → AL Cost Bucket | Bucket mặc định khi dòng không khai báo cost_bucket |
| calc_method | Select | BY_KG_M / BY_M2 / BY_UNIT / BY_METER |

### 4.3 AL Glass Type

| fieldname | fieldtype | Mô tả |
|---|---|---|
| type_code | Data (reqd, unique) | DON, CUONG_LUC, HOP, LOWE, LAM |
| type_name | Data | |

### 4.4 AL Glass Layer Type (Phase 3)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| layer_code | Data (reqd, unique) | GLASS, AIR_GAP, INTERLAYER |
| layer_name | Data | |

### 4.5 AL Glass Master

| fieldname | fieldtype | Mô tả |
|---|---|---|
| glass_code | Data (reqd, unique) | KINH-DON-8, KINH-CL-10, KINH-HOP-24… |
| glass_name | Data | |
| total_thick_mm | Float | **Nguồn gốc của glass_thick_mm** — ProfileInterpreter tra trực tiếp |
| glass_type | Link → AL Glass Type | |
| has_complex_structure | Check | Bật nếu có glass_layers |
| u_value | Float | U-value (W/m²K) — Phase 3 |
| shgc | Float | Solar Heat Gain Coefficient — Phase 3 |
| vlt | Float | Visible Light Transmittance (%) — Phase 3 |
| glass_layers | Table → AL Glass Layer Line | Cấu trúc lớp — Phase 3 |

### 4.6 AL Glass Layer Line (child of AL Glass Master — Phase 3)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| sort_order | Int (reqd) | Thứ tự lớp từ ngoài vào trong |
| layer_type | Link → AL Glass Layer Type (reqd) | |
| thickness_mm | Float | Chiều dày lớp (mm) |
| description | Small Text | |

### 4.7 AL Product Type

| fieldname | fieldtype | Mô tả |
|---|---|---|
| type_code | Data (reqd, unique) | CUA_DI, CUA_SO, CUA_LUA, CUA_MAT_HAT, VACH_KINH |
| type_name | Data | |
| nc_pct | Float (default 12) | % NC sản xuất mặc định |
| nc_ld_rate | Currency | Đơn giá NC lắp đặt (đ/m²) |
| description | Small Text | |

### 4.8 AL Variable Library

| fieldname | fieldtype | Mô tả |
|---|---|---|
| var_code | Data (reqd, unique) | W_mm, H_mm, SL, n_canh, do_day… |
| var_label | Data | Nhãn hiển thị trong Dialog |
| var_group | Link → AL Variable Group | |
| var_type | Select | `FLOAT` / `INT` / `STR` / `BOOL` |
| default_val | Data | Giá trị mặc định |
| options | Data | Danh sách Select: "2.0mm,1.4mm,1.2mm" |
| ui_widget | Select | `Text` / `Select` / `Number` / `Toggle` |
| description | Small Text | |

### 4.9 AL Variable Set

| fieldname | fieldtype | Mô tả |
|---|---|---|
| set_code | Data (reqd, unique) | VAR-CUA-DI, VAR-VACH-KINH… |
| set_name | Data | |
| al_var_details | Table → AL Variable Set Detail | |

### 4.10 AL Variable Set Detail (child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| variable | Link → AL Variable Library (reqd) | |
| is_required | Check | |
| override_default | Data | Ghi đè default_val của Library |
| depends_on | Code | Điều kiện hiển thị field trong Dialog |
| sort_order | Int | |

### 4.11 AL Variable Binding

| fieldname | fieldtype | Mô tả |
|---|---|---|
| binding_code | Data (reqd, unique) | BND-W-MM, BND-DG-NHOM… |
| variable_name | Data (reqd) | Tên biến trong inputs_dict |
| variable_label | Data | |
| source_type | Select | Quotation Input / BOM Variable / BOM Attribute / Rule Engine Result / Computed / Context Inject |
| resolve_priority | Int (default 50) | **Nhỏ hơn = resolve trước** |
| source_config | JSON | `{"fieldname":"al_W_mm"}` hoặc `{"rule_code":"TRA-GIA-NHOM","args":["brand","mau_nhom"]}` |
| data_type | Select | Float / String / Integer / Boolean |
| is_active | Check (default 1) | |
| description | Small Text | |

> `glass_thick_{prefix}` và `max_glass_thick_mm` **không có Binding** — inject trực tiếp bởi VariableResolver.

### 4.12 AL Cost Bucket

| fieldname | fieldtype | Mô tả |
|---|---|---|
| bucket_code | Data (reqd, unique) | VL_NHOM, VL_KINH, TONG_VL, GIA_THANH… |
| bucket_name | Data | |
| bucket_role | Select | `LEAF` (tích lũy trực tiếp) / `AGGREGATE` (tổng hợp) |
| parent_bucket | Link → AL Cost Bucket | |
| sort_order | Int | |
| report_group | Data | "A. Vật liệu", "B. Nhân công"… |

### 4.13 AL Calculation Rule

| fieldname | fieldtype | Mô tả |
|---|---|---|
| rule_code | Data (reqd, unique) | QTY-KHUNG-DUNG, TRA-GIA-NHOM, XF55-OFFSET-W… |
| rule_name | Data | |
| rule_type | Select (reqd) | `CONSTANT` / `FORMULA` / `THRESHOLD` / `LOOKUP` / `SEQUENCE` |
| description | Text | |
| is_active | Check (default 1) | |
| *(CONSTANT)* constant_value | Data | Giá trị hằng số (số hoặc chuỗi) |
| *(FORMULA)* formula_expression | Code | Cú pháp FormulaEngine: "H_m * 2 * SL" |
| *(THRESHOLD)* threshold_input_var | Data | Tên biến đầu vào |
| *(THRESHOLD)* threshold_rows | Table → AL Rule Threshold Row | |
| *(LOOKUP)* lookup_key_1_var | Data | Tên biến key 1 |
| *(LOOKUP)* lookup_key_2_var | Data | Tên biến key 2 |
| *(LOOKUP)* lookup_rows | Table → AL Rule Lookup Row | |
| *(LOOKUP)* lookup_default | Data | Giá trị mặc định nếu không khớp |
| *(SEQUENCE)* sequence_items | Table → AL Rule Sequence Item | |

### 4.14 AL Rule Threshold Row (child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| from_value | Float | Ngưỡng từ |
| to_value | Float | Ngưỡng đến (0 = không giới hạn) |
| result_value | Data | Giá trị trả về |

### 4.15 AL Rule Lookup Row (child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| key_1 | Data | Giá trị key 1 |
| key_2 | Data | Giá trị key 2 |
| key_3 | Data | Giá trị key 3 |
| result_value | Data | Giá trị trả về |

### 4.16 AL Rule Sequence Item (child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| rule | Link → AL Calculation Rule | Rule con |
| sort_order | Int | |

### 4.17 AL Profile Line ★ TRUNG TÂM CỦA v16 (giữ nguyên)

Mỗi dòng đại diện cho 1 vật tư trong BOM: có thể là nhôm, kính, VTP, hoặc phụ kiện nội tuyến.

#### Trường chung (tất cả line_type)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| sort_order | Int | ✓ | Thứ tự hiển thị. Admin đặt tự do. Không ảnh hưởng thứ tự tính |
| line_type | Select | ✓ | `NHOM` / `KINH` / `VTP` / `PK` |
| line_name | Data | ✓ | "Khung bao đứng", "Kính cánh", "Gioăng cánh"... |
| slug | Data | | Auto-generate từ sort_order + line_name. **Unique trong Profile Set** |
| group_tag | Data | | KHUNG / CANH / NEP / KINH_CANH / KINH_OC / GIOANG... |
| show_condition | Code | | Boolean expression FormulaEngine. Có thể dùng `glass_thick_kinh_canh`, `max_glass_thick_mm`... |
| cost_bucket | Link → AL Cost Bucket | | Trống = dùng default_bucket của AL Material Type |
| is_active | Check (default 1) | | Master on/off cho dòng này |

#### Trường riêng NHOM (line_type = NHOM)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| item_code | Link → Item | ✓ | Mã biên dạng nhôm. `Item.al_item_type` = NHOM_PROFILE |
| quantity_rule | Link → AL Calculation Rule | | Ưu tiên hơn qty_formula |
| qty_formula | Code | | `H_m * 2 * qty`. Có thể tham chiếu `glass_thick_{prefix}` |
| price_type | Select | | `Rule` / `Item Price` / `Fixed` |
| price_rule | Link → AL Calculation Rule | | Dùng khi price_type = Rule |
| fixed_price | Currency | | Dùng khi price_type = Fixed |

#### Trường riêng KINH (line_type = KINH)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| ctx_inject_prefix | Data | ✓ | Tiền tố biến: `kinh_canh`, `kinh_oc`. **Unique trong Profile Set. Không kết thúc bằng chữ số.** Biến `glass_thick_{prefix}` tự động inject |
| default_glass_master | Link → AL Glass Master | ✓ | Kính mặc định. Nguồn `total_thick_mm` |
| width_rule | Link → AL Calculation Rule | | |
| height_rule | Link → AL Calculation Rule | | |
| width_formula | Code | | VD: `W_mm - 86` |
| height_formula | Code | | VD: `H_mm - 86` |
| panel_count_formula | Code | | Số panel độc lập. `(n_do_dung+1)*(n_do_ngang+1)` cho vách nhiều ô. **Chỉ tham chiếu biến priority ≤ 40** |
| panel_glass_override_allowed | Check (default 0) | | Sales chọn kính riêng từng panel |
| qty_per_panel_formula | Code (default "1") | | Số tấm giống nhau trong 1 panel |
| price_type | Select | | `Item Price` / `Rule` / `Fixed` |
| price_list | Link → Price List | | |
| price_rule | Link → AL Calculation Rule | | |
| fixed_price | Currency | | |
| cut_fee_pct | Float (default 0) | | Phí cắt kính (%) |

> **Biến tự động sinh:**
> - `glass_thick_{prefix}` — inject vào inputs_dict từ `AL Glass Master.total_thick_mm`
> - `{prefix}_total_perimeter_m`, `{prefix}_total_m2`, `{prefix}_total_qty`
> - `max_glass_thick_mm` — sinh sau khi xong tất cả dòng KINH

#### Trường riêng VTP (line_type = VTP)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| item_code | Link → Item | ✓ | `Item.al_item_type` = VTP |
| quantity_rule | Link → AL Calculation Rule | | |
| qty_formula | Code | | `ALL_KINH_total_perimeter_m * 2`, `kinh_canh_total_perimeter_m * 2` |
| price_type | Select | | `Item Price` / `Fixed` / `Rule` |
| price_list | Link → Price List | | |
| fixed_price | Currency | | |

#### Trường riêng PK (line_type = PK — PK nội tuyến)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| item_code | Link → Item | ✓ | `Item.al_item_type` = PHU_KIEN |
| sl_formula | Code | ✓ | `1`, `n_canh * qty` |
| price_list | Link → Price List | | |
| allow_substitute | Check (default 0) | | Sales được đổi item khác |
| substitute_item_group | Link → Item Group | | Giới hạn nhóm item thay thế |

### 4.18 AL Profile Set

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| set_code | Data | ✓ | Unique. `PS-CUA-DI-XF55`, `PS-VACH-XF65`... |
| set_name | Data | ✓ | |
| product_type | Link → AL Product Type | | |
| brand | Link → Brand | | |
| version | Data (default "1.0") | | |
| **al_lines** | **Table → AL Profile Line** | | **1 bảng con duy nhất** |

### 4.19 AL PK Set, AL PK Line

**AL PK Set:**

| fieldname | fieldtype | Mô tả |
|---|---|---|
| set_code | Data (reqd, unique) | |
| set_name | Data | |
| product_type | Link → AL Product Type | |
| al_pk_lines | Table → AL PK Line | |

**AL PK Line:**

| fieldname | fieldtype | Mô tả |
|---|---|---|
| item_code | Link → Item (reqd) | Item mặc định |
| sl_formula | Code (reqd) | Công thức số lượng |
| price_list | Link → Price List | |
| cost_bucket | Link → AL Cost Bucket | |
| allow_substitute | Check (default 0) | |
| substitute_item_group | Link → Item Group | |

### 4.20 AL BOM (cập nhật v17)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| bom_code | Data (reqd, unique) | |
| bom_name | Data | |
| product_type | Link → AL Product Type | |
| brand | Link → Brand | |
| representative_item | Link → Item (reqd) | Item phi tồn kho đại diện (QĐ-5) |
| variable_set | Link → AL Variable Set | |
| profile_set | Link → AL Profile Set | |
| pk_set | Link → AL PK Set | Optional |
| default_cost_template | Link → AL Cost Template | |
| thumbnail | Attach Image | |
| is_active | Check (default 1) | |
| **current_version** | **Link → AL BOM Version** | **★ MỚI v17 — version đang Published** |
| **total_versions** | **Int** | **Tổng số version đã publish (read-only)** |
| **last_published_on** | **Datetime** | **Ngày publish lần cuối (read-only)** |
| **requires_approval_for_new_version** | **Check** | **BOM version mới cần duyệt trước khi Published** |
| **assigned_discount_rules** | **JSON** | **Danh sách AL Discount Rule mặc định** |

### 4.21 AL Cost Template, AL Cost Template Line

**AL Cost Template:**

| fieldname | fieldtype | Mô tả |
|---|---|---|
| template_code | Data (reqd, unique) | CT-01-STANDARD, CT-02-PREMIUM… |
| template_name | Data | |
| product_type | Link → AL Product Type | |
| al_lines | Table → AL Cost Template Line | |

**AL Cost Template Line:**

| fieldname | fieldtype | Mô tả |
|---|---|---|
| sort_order | Int | |
| line_code | Data | GIA_THANH, GIA_BAN, DON_GIA_M2… |
| line_label | Data | Tên hiển thị trên báo giá |
| calc_formula | Code | "TONG_VL + TONG_NC + TONG_OH", "GIA_BAN * 1.10"... |
| cost_bucket | Link → AL Cost Bucket | |
| is_subtotal | Check | |
| show_on_quotation | Check (default 1) | |

### 4.22 ConfigSnapshot

| fieldname | fieldtype | Mô tả |
|---|---|---|
| snapshot_id | Data (unique) | frappe.generate_hash(length=16) |
| formula_engine_snapshot_id | Data | snapshot_id của EnterpriseSnapshot trong formula_builder |
| formula_engine_payload_hash | Data | Cache payload_hash |
| **enterprise_snapshot_json** | Long Text | Serialize toàn bộ EnterpriseSnapshot.to_json() |
| profile_set | Link → AL Profile Set | |
| profile_set_hash | Data | Hash riêng của Profile Set (drift detection nhanh) |
| pk_set | Link → AL PK Set | |
| pk_overrides_json | JSON | Bản sao al_pk_overrides tại thời điểm báo giá |
| rule_set_hashes | JSON | {rule_code: hash} |
| glass_master_hashes | JSON | {glass_code: hash} |
| variable_bindings_hash | Data | |
| cost_template | Link → AL Cost Template | |
| cost_template_hash | Data | |
| created_at | Datetime | |
| quotation | Link → Quotation | |
| quotation_item_name | Data | |
| drift_detected | Check | |
| drift_details | JSON | |

### 4.25 AL BOM Version ★ MỚI v17

Snapshot bất biến của toàn bộ cấu hình BOM tại thời điểm admin nhấn 'Publish'. Quotation Item lưu `version_id` thay vì trỏ trực tiếp BOM.

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| name | Data | ✓ | Auto-generated: BOM-VER-YYYY-NNNNN |
| bom | Link → AL BOM | ✓ | BOM nguồn |
| version_number | Int | ✓ | Tự tăng theo BOM (v1, v2, v3...) |
| status | Select | ✓ | Draft / Published / Deprecated / Pending Approval / Rejected |
| published_on | Datetime | | Ngày publish |
| published_by | Link → User | | Người publish |
| profile_set_snapshot | JSON | ✓ | Full JSON của AL Profile Set tại thời điểm publish |
| variable_set_snapshot | JSON | ✓ | Full JSON của AL Variable Set |
| pk_set_snapshot | JSON | | Full JSON của AL PK Set (nếu có) |
| cost_template_snapshot | JSON | ✓ | Full JSON của AL Cost Template |
| snapshot_hash | Data | ✓ | SHA-256 của toàn bộ snapshot |
| change_summary | Small Text | | Tóm tắt thay đổi so với version trước |
| approved_by | Link → User | | Người duyệt |
| is_rollback_of | Link → AL BOM Version | | Trỏ version gốc nếu đây là rollback |
| al_change_logs | Table → AL BOM Change Log | | Danh sách thay đổi chi tiết |

**Logic nghiệp vụ AL BOM Version:**
- Khi status = 'Published': set immutable flag → không cho sửa các snapshot fields
- AL BOM có thể có nhiều version; chỉ 1 version mới nhất status='Published' là active
- Khi Quotation được tạo: tự động gắn `version_id` = BOM version Published mới nhất
- Nếu BOM Version bị Deprecated: Quotation cũ vẫn giữ `version_id` cũ
- Rollback: tạo version mới từ snapshot của version cũ; không xóa version nào

### 4.26 AL BOM Change Log ★ MỚI v17 (child of AL BOM Version)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| change_type | Select | FIELD_CHANGE / LINE_ADDED / LINE_REMOVED / LINE_MODIFIED / FORMULA_CHANGED / PRICE_CHANGED / ROLLBACK |
| changed_by | Link → User | |
| changed_on | Datetime | |
| target_doctype | Data | DocType bị ảnh hưởng: AL Profile Line / AL Calculation Rule... |
| target_record | Data | Tên record bị thay đổi |
| field_name | Data | Field cụ thể bị thay đổi |
| old_value | Small Text | Giá trị cũ (JSON serialize) |
| new_value | Small Text | Giá trị mới (JSON serialize) |
| impact_estimate | Select | LOW / MEDIUM / HIGH |

### 4.27 AL Discount Rule ★ MỚI v17

Quản lý chiết khấu có cấu trúc, áp dụng SAU khi FormulaEngine tính xong GIA_BAN.

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| name | Data | ✓ | Auto-generated: DISC-YYYY-NNNNN |
| rule_name | Data | ✓ | Tên quy tắc chiết khấu |
| rule_type | Select | ✓ | CUSTOMER_TIER / PROJECT / VOLUME / SEASONAL / MANUAL |
| applies_to_bom | Link → AL BOM | | Trống = áp dụng mọi BOM |
| applies_to_customer_group | Link → Customer Group | | |
| applies_to_customer | Link → Customer | | Ưu tiên cao hơn group |
| min_amount | Currency | | Ngưỡng giá trị đơn hàng tối thiểu |
| max_amount | Currency | | 0 = không giới hạn |
| discount_pct | Float | | Chiết khấu cố định (%) |
| stackable | Check | | Có thể cộng dồn với rule khác? Default: No |
| priority | Int | ✓ | Số nhỏ = ưu tiên cao |
| valid_from | Date | | |
| valid_to | Date | | |
| requires_approval | Check | | Phải được duyệt trước khi áp dụng |
| approval_threshold_pct | Float | | Nếu discount > ngưỡng này → bắt buộc approval |
| al_discount_tiers | Table → AL Discount Rule Line | | Bảng tier (cho rule_type = VOLUME) |

### 4.28 AL Discount Rule Line ★ MỚI v17 (child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| min_qty | Float | Số lượng tối thiểu (bộ) |
| max_qty | Float | 0 = không giới hạn |
| discount_pct | Float | Chiết khấu (%) cho tier này |
| note | Small Text | |

### 4.29 AL Material Plan ★ MỚI v17

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| name | Data | ✓ | Auto-generated: MRP-YYYY-NNNNN |
| plan_name | Data | ✓ | |
| plan_date | Date | ✓ | |
| status | Select | ✓ | Draft / Confirmed / Purchased |
| source_type | Select | ✓ | QUOTATION / SALES_ORDER / MIXED |
| quotation_list | JSON | | Danh sách Quotation name được chọn |
| so_list | JSON | | Danh sách SO name được chọn |
| aggregation_method | Select | ✓ | BY_ITEM / BY_ITEM_GROUP / BY_BOM |
| include_safety_stock_pct | Float | | Tỷ lệ % dự phòng |
| notes | Small Text | | |
| al_plan_lines | Table → AL Material Plan Line | ✓ | |
| total_nhom_value | Currency | | Tổng giá trị nhôm ước tính |
| total_kinh_value | Currency | | Tổng giá trị kính ước tính |
| total_vtp_value | Currency | | Tổng giá trị VTP ước tính |
| total_pk_value | Currency | | Tổng giá trị PK ước tính |
| grand_total_value | Currency | | Tổng giá trị vật tư ước tính |

### 4.30 AL Material Plan Line ★ MỚI v17 (child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| item_code | Link → Item | |
| item_name | Data | |
| item_type | Data | NHOM / KINH / VTP / PK |
| uom | Link → UOM | |
| total_qty_gross | Float | Tổng số lượng thô |
| safety_stock_qty | Float | Số lượng dự phòng |
| total_qty_net | Float | gross + safety |
| current_stock_qty | Float | Tồn kho hiện tại (từ ERPNext Bin) |
| qty_to_purchase | Float | net - current_stock |
| estimated_unit_price | Currency | Từ Item Price hoặc LPO gần nhất |
| estimated_total | Currency | |
| source_quotations | JSON | Danh sách Quotation/SO đóng góp |

### 4.31 AL Cost Variance ★ MỚI v17

| fieldname | fieldtype | Mô tả |
|---|---|---|
| quotation_item | Link → Quotation Item | |
| config_snapshot | Link → ConfigSnapshot | |
| purchase_invoice | Link → Purchase Invoice | |
| item_code | Link → Item | |
| quoted_unit_price | Currency | Từ ConfigSnapshot |
| actual_unit_price | Currency | Từ Purchase Invoice |
| variance_amount | Currency | actual - quoted |
| variance_pct | Float | (actual - quoted) / quoted × 100 |
| variance_status | Select | NORMAL (<5%) / CAUTION (5-15%) / ALERT (>15%) / FAVORABLE (<-5%) |
| impact_on_margin | Currency | qty × variance_amount |
| reviewed_by | Link → User | |
| review_note | Small Text | |

### 4.32 AL Alert Config ★ MỚI v17

| fieldname | fieldtype | Mô tả |
|---|---|---|
| alert_type | Select | PRICE_CHANGE / LOW_STOCK / BOM_EXPIRY / VARIANCE_ALERT / APPROVAL_PENDING / DISCOUNT_EXCEEDED |
| alert_name | Data | |
| is_active | Check | |
| threshold_value | Float | Ngưỡng kích hoạt (% hoặc số lượng) |
| notify_roles | JSON | Danh sách vai trò nhận thông báo |
| notify_users | JSON | Danh sách user cụ thể |
| notification_channel | Select | EMAIL / FRAPPE_NOTIFICATION / BOTH |
| frequency | Select | REALTIME / DAILY_DIGEST / WEEKLY |
| max_total_discount_pct | Float | Ngưỡng tổng chiết khấu tối đa |

### 4.33 AL Dashboard Config ★ MỚI v17

| fieldname | fieldtype | Mô tả |
|---|---|---|
| role | Link → Role | Vai trò áp dụng dashboard |
| widgets | JSON | `[{type, title, report, filters, position}]` |
| default_date_range | Select | THIS_MONTH / THIS_QUARTER / THIS_YEAR / CUSTOM |
| refresh_interval_sec | Int | 0 = không tự refresh |

### 4.34 AL Sales KPI ★ MỚI v17

| fieldname | fieldtype | Mô tả |
|---|---|---|
| sales_user | Link → User | |
| kpi_period | Select | MONTHLY / QUARTERLY / YEARLY |
| period_label | Data | 2025-Q1, 2025-06... |
| target_amount | Currency | Doanh số mục tiêu |
| actual_amount | Currency | Doanh số thực tế (từ SO đã Submitted) |
| target_quotations | Int | |
| actual_quotations | Int | |
| conversion_rate_target | Float | Tỷ lệ chuyển đổi Quotation→SO mục tiêu (%) |
| conversion_rate_actual | Float | Tỷ lệ chuyển đổi thực tế (%) |
| avg_margin_target_pct | Float | |
| avg_margin_actual_pct | Float | (GIA_BAN - GIA_THANH)/GIA_BAN |
| avg_discount_pct | Float | Trung bình chiết khấu trong kỳ |
| last_calculated_on | Datetime | Auto từ scheduled job |

---

## V. CUSTOM FIELDS TRÊN ERPNEXT CORE

### 5.1 Custom Fields trên Item

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| al_item_type | Select | | `NHOM_PROFILE` / `KINH` / `VTP` / `PHU_KIEN` |
| al_glass_master | Link → AL Glass Master | | Bắt buộc nếu al_item_type = KINH |
| al_kg_per_m | Float | | Bắt buộc nếu al_item_type = NHOM_PROFILE |

### 5.2 Custom Fields trên Quotation Item (v17 đầy đủ)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_bom | Link → AL BOM | BOM sản phẩm Sales chọn |
| al_W_mm | Float | Chiều rộng (mm) |
| al_H_mm | Float | Chiều cao (mm) |
| al_mau_nhom | Data | Màu nhôm |
| al_bom_vars | JSON | `{"n_canh": 2, "do_day": "2.0mm"}` |
| al_glass_selections | JSON | `{"kinh_canh": "KINH-DON-8", "kinh_oc": "KINH-CL-10"}` |
| al_pk_overrides | JSON | `{"BANLE-XF55": "BANLE-XF55-INOX"}` |
| al_cost_template_override | Link → AL Cost Template | Để trống = BOM default |
| al_vl_nhom | Currency | Tổng giá trị nhôm |
| al_vl_kinh | Currency | Tổng giá trị kính |
| al_vl_vtp | Currency | Tổng giá trị VTP |
| al_vl_pk | Currency | Tổng giá trị phụ kiện |
| al_tong_vl | Currency | TONG_VL |
| al_gia_thanh | Currency | GIA_THANH |
| al_gia_ban | Currency | GIA_BAN |
| al_gia_vat | Currency | GIA_VAT |
| al_don_gia_m2 | Currency | GIA_BAN / m² |
| al_config_snapshot | Link → ConfigSnapshot | |
| al_recalculate | Button | Trigger tính giá lại |
| **al_bom_version** | **Link → AL BOM Version** | **★ MỚI v17 — version BOM áp dụng** |
| **al_discount_rule** | **Link → AL Discount Rule** | **★ MỚI v17** |
| **al_discount_pct** | **Float** | **★ MỚI v17 — tổng % chiết khấu** |
| **al_gia_thuong_mai** | **Currency** | **★ MỚI v17 — GIA_BAN × (1 - discount)** |
| **al_cost_variance_ref** | **Link → AL Cost Variance** | **★ MỚI v17** |
| **al_approval_status** | **Select** | **★ MỚI v17 — PENDING / APPROVED / REJECTED** |
| **al_approved_by** | **Link → User** | **★ MỚI v17** |
| **al_approval_note** | **Small Text** | **★ MỚI v17** |

### 5.3 Custom Fields trên Sales Order Item / Sales Invoice Item

Y hệt Quotation Item, trừ `al_recalculate` không tạo. Thêm `al_source_quotation_item` (Data, ẩn). Tất cả field al_* kể cả các field v17 mới đều copy sang khi convert QT→SO→SI.

---

## VI. MASTER DATA CHUẨN v17

### 6.1 AL Variable Group

| group_code | group_name | sort_order |
|---|---|---|
| KICH_THUOC | Kích thước | 10 |
| SO_LUONG | Số lượng | 20 |
| VAT_LIEU | Vật liệu | 30 |
| CANH_CUA | Cánh cửa | 40 |
| VACH | Vách kính | 50 |

### 6.2 AL Variable Binding — Bảng resolve_priority chuẩn

| source_type | priority | Ví dụ |
|---|---|---|
| Quotation Input | 10 | W_mm, H_mm, qty, mau_nhom |
| BOM Attribute | 20 | brand |
| BOM Variable | 30 | n_canh, do_day, huong_mo, co_nguong |
| Computed đơn giản | 40 | W_m, H_m |
| Rule Engine Result (LOOKUP) | 60 | don_gia_nhom |
| Computed phức tạp | 70 | canh_rong_mm |

> `glass_thick_{prefix}` **không có Binding** — inject trực tiếp bởi VariableResolver từ AL Glass Master (QĐ-9).

### 6.3 AL Calculation Rule — CONSTANT (chọn lọc)

| rule_code | constant_value | Mô tả |
|---|---|---|
| XF55-OFFSET-W | 86 | Offset chiều rộng kính cánh XF55 |
| XF55-OFFSET-H | 86 | Offset chiều cao kính cánh XF55 |
| XF65-VACH-OFFSET-W | 50 | Offset kính vách XF65 |

### 6.4 AL Calculation Rule — FORMULA (chọn lọc)

| rule_code | formula_expression | Mô tả |
|---|---|---|
| QTY-KHUNG-DUNG | `(H_m * 2) * qty` | Số lượng thanh khung đứng |
| QTY-KHUNG-NGANG | `(W_m + 0.043*2) * qty` | Số lượng thanh khung ngang |
| QTY-CANH-DUNG | `(H_m - 0.043*2) * n_canh * qty` | Số lượng thanh cánh đứng |
| QTY-CANH-NGANG | `(W_m/n_canh - 0.043*2) * n_canh * qty` | Số lượng thanh cánh ngang |
| QTY-NEP-DUNG | `(H_m - 0.043*2) * n_canh * qty * 2` | Số lượng nẹp kính đứng |
| QTY-NEP-NGANG | `(W_m/n_canh - 0.043*2) * n_canh * qty * 2` | Số lượng nẹp kính ngang |

### 6.5 AL Calculation Rule — LOOKUP: TRA-GIA-NHOM

Tra theo (brand, mau_nhom) → đơn giá nhôm đ/kg.

| key_1 (brand) | key_2 (mau_nhom) | result_value (đ/kg) |
|---|---|---|
| XF-NK | STD | 113,000 |
| XF-NK | DAK | 118,000 |
| XF-NK | VG | 125,000 |
| ALUMIL | STD | 135,000 |
| ALUMIL | DAK | 142,000 |

### 6.6 AL Cost Bucket

| bucket_code | bucket_name | bucket_role | parent_bucket | report_group |
|---|---|---|---|---|
| VL_NHOM | Nhôm profile | LEAF | TONG_VL | A. Vật liệu |
| VL_KINH | Kính | LEAF | TONG_VL | A. Vật liệu |
| VL_VTP | Vật tư phụ | LEAF | TONG_VL | A. Vật liệu |
| VL_PK | Phụ kiện | LEAF | TONG_VL | A. Vật liệu |
| TONG_VL | Tổng vật liệu | AGGREGATE | | A. Vật liệu |
| NC_SX | NC sản xuất | LEAF | TONG_NC | B. Nhân công |
| NC_LD | NC lắp đặt | LEAF | TONG_NC | B. Nhân công |
| TONG_NC | Tổng nhân công | AGGREGATE | | B. Nhân công |
| OH_HH | Hao hụt vật liệu | LEAF | TONG_OH | C. Overhead |
| OH_CUT_KINH | Phí cắt kính | LEAF | TONG_OH | C. Overhead |
| OH_VC | Vận chuyển | LEAF | TONG_OH | C. Overhead |
| OH_BH | Bảo hành | LEAF | TONG_OH | C. Overhead |
| TONG_OH | Tổng overhead | AGGREGATE | | C. Overhead |
| GIA_THANH | Giá thành | AGGREGATE | | D. Tổng hợp |
| GIA_BAN | Giá bán | AGGREGATE | | D. Tổng hợp |
| GIA_VAT | Giá có VAT 10% | AGGREGATE | | D. Tổng hợp |

### 6.7 AL Cost Template — CT-01-STANDARD

| sort | line_code | line_label | calc_formula | cost_bucket | is_subtotal |
|---|---|---|---|---|---|
| 10 | VL_NHOM | Vật liệu nhôm | VL_NHOM | VL_NHOM | 0 |
| 20 | VL_KINH | Vật liệu kính | VL_KINH | VL_KINH | 0 |
| 30 | VL_VTP | Vật tư phụ | VL_VTP | VL_VTP | 0 |
| 40 | VL_PK | Phụ kiện | VL_PK | VL_PK | 0 |
| 50 | TONG_VL | **Tổng vật liệu** | VL_NHOM + VL_KINH + VL_VTP + VL_PK | TONG_VL | 1 |
| 55 | TONG_M2 | Tổng diện tích (m²) | W_m * H_m * qty | | 0 |
| 60 | NC_SX | NC sản xuất (12%) | TONG_VL * 0.12 | NC_SX | 0 |
| 70 | NC_LD | NC lắp đặt | TONG_M2 * 180000 | NC_LD | 0 |
| 80 | TONG_NC | **Tổng nhân công** | NC_SX + NC_LD | TONG_NC | 1 |
| 90 | OH_HH | Hao hụt VL (1%) | TONG_VL * 0.01 | OH_HH | 0 |
| 100 | OH_CUT_KINH | Phí cắt kính | OH_CUT_KINH | OH_CUT_KINH | 0 |
| 110 | OH_VC | Vận chuyển | 500000 | OH_VC | 0 |
| 120 | OH_BH | Bảo hành (0.5%) | TONG_VL * 0.005 | OH_BH | 0 |
| 130 | TONG_OH | **Tổng overhead** | OH_HH + OH_CUT_KINH + OH_VC + OH_BH | TONG_OH | 1 |
| 140 | GIA_THANH | **Giá thành** | TONG_VL + TONG_NC + TONG_OH | GIA_THANH | 1 |
| 150 | PROFIT | Lợi nhuận (15%) | GIA_THANH * 0.15 | | 0 |
| 160 | GIA_BAN | **Giá bán** | GIA_THANH + PROFIT | GIA_BAN | 1 |
| 165 | DON_GIA_M2 | Đơn giá/m² | GIA_BAN / TONG_M2 | | 0 |
| 170 | GIA_VAT | **Giá có VAT** | GIA_BAN * 1.10 | GIA_VAT | 1 |

### 6.8a AL Glass Master — Thông số kỹ thuật chuẩn

| glass_code | glass_name | total_thick_mm | glass_type | u_value | shgc |
|---|---|---|---|---|---|
| KINH-DON-8 | Kính đơn 8mm | 8.0 | DON | 5.8 | 0.86 |
| KINH-DON-10 | Kính đơn 10mm | 10.0 | DON | 5.8 | 0.86 |
| KINH-CL-10 | Kính cường lực 10mm | 10.0 | CUONG_LUC | 5.8 | 0.86 |
| KINH-CL-12 | Kính cường lực 12mm | 12.0 | CUONG_LUC | 5.8 | 0.86 |
| KINH-HOP-24 | Kính hộp 6+12A+6mm | 24.0 | HOP | 2.7 | 0.62 |
| KINH-LOWE-24 | Kính Low-E 6+12A+6mm | 24.0 | LOWE | 1.4 | 0.32 |
| KINH-LOWE-28 | Kính Low-E 6+16A+6mm | 28.0 | LOWE | 1.1 | 0.28 |

> **Điểm quan trọng:** `total_thick_mm` chính là giá trị được inject vào `glass_thick_{prefix}` trong inputs_dict. Với kính hộp và Low-E, đây là tổng chiều dày cả cấu trúc (kính + khe khí + kính) — quyết định loại nẹp và gioăng cần dùng.

### 6.8 Item — Kính

| item_code | item_name | al_item_type | al_glass_master | uom | rate (đ/m²) |
|---|---|---|---|---|---|
| KINH-DON-8 | Kính đơn 8mm | KINH | KINH-DON-8 | M2 | 250,000 |
| KINH-DON-10 | Kính đơn 10mm | KINH | KINH-DON-10 | M2 | 320,000 |
| KINH-CL-10 | Kính cường lực 10mm | KINH | KINH-CL-10 | M2 | 550,000 |
| KINH-CL-12 | Kính cường lực 12mm | KINH | KINH-CL-12 | M2 | 650,000 |
| KINH-HOP-24 | Kính hộp 6+12A+6mm | KINH | KINH-HOP-24 | M2 | 820,000 |
| KINH-LOWE-24 | Kính Low-E 6+12A+6mm | KINH | KINH-LOWE-24 | M2 | 1,150,000 |
| KINH-LOWE-28 | Kính Low-E 6+16A+6mm | KINH | KINH-LOWE-28 | M2 | 1,350,000 |

### 6.9 Item — Nhôm Xingfa NK

| item_code | item_name | brand | al_item_type | al_kg_per_m |
|---|---|---|---|---|
| C3318-20 | Khung bao đứng CĐ 2.0mm | XF-NK | NHOM_PROFILE | 1.257 |
| C3318-14 | Khung bao đứng CĐ 1.4mm | XF-NK | NHOM_PROFILE | 0.980 |
| C3303-20 | Cánh mở ngoài 2.0mm | XF-NK | NHOM_PROFILE | 1.045 |
| C3332-20 | Cánh mở trong 2.0mm | XF-NK | NHOM_PROFILE | 1.102 |
| C3350-20 | Ngưỡng cửa đi 2.0mm | XF-NK | NHOM_PROFILE | 1.520 |
| C3200-20 | Đố đứng cửa đi 2.0mm | XF-NK | NHOM_PROFILE | 1.080 |
| C3209-20 | Nẹp kính ≤10.38mm | XF-NK | NHOM_PROFILE | 0.198 |
| C3210-20 | Nẹp kính 11–16mm | XF-NK | NHOM_PROFILE | 0.245 |
| C3211-20 | Nẹp kính IGU >16mm | XF-NK | NHOM_PROFILE | 0.312 |
| C6001-20 | Khung bao đứng vách 65 | XF-NK | NHOM_PROFILE | 1.450 |
| C6002-20 | Khung ngang vách 65 | XF-NK | NHOM_PROFILE | 1.380 |
| C6003-20 | Đố đứng vách 65 | XF-NK | NHOM_PROFILE | 1.120 |
| C6011-20 | Nẹp kính vách >16mm | XF-NK | NHOM_PROFILE | 0.310 |

### 6.10 Item — VTP & Phụ kiện

| item_code | item_name | al_item_type | uom | rate (đ) |
|---|---|---|---|---|
| GIO-EPDM-CU | Gioăng cánh EPDM | VTP | Meter | 15,000 |
| GIO-EPDM-KH | Gioăng khung EPDM | VTP | Meter | 12,000 |
| GIO-EPDM-K8 | Gioăng kính 8mm EPDM | VTP | Meter | 10,000 |
| GIO-EPDM-K24 | Gioăng kính 24mm EPDM | VTP | Meter | 22,000 |
| KEO-SI-DEN | Keo silicon đen | VTP | Tube | 65,000 |
| XOP-PHI10 | Xốp chèn phi 10mm | VTP | Meter | 5,000 |
| VIT-LD-7.5x100 | Vít lắp đặt 7.5×100mm | VTP | Bộ | 18,000 |
| KHOA-XF55 | Khóa cửa đi XF55 | PHU_KIEN | Cái | 350,000 |
| BANLE-XF55 | Bản lề cửa đi XF55 | PHU_KIEN | Bộ | 120,000 |
| TAY-NAM-XF55 | Tay nắm cửa đi XF55 | PHU_KIEN | Bộ | 180,000 |
| TAY-NAM-XF55-INOX | Tay nắm Inox XF55 | PHU_KIEN | Bộ | 250,000 |
| TAY-NAM-XF55-VANG | Tay nắm vàng XF55 | PHU_KIEN | Bộ | 320,000 |

### 6.11 AL Profile Set — PS-CUA-DI-XF55 (minh họa đầy đủ)

**al_lines (sort theo nghề: Nhôm → Kính → PK → VTP):**

| sort | line_type | line_name | slug | Trường đặc trưng |
|---|---|---|---|---|
| 10 | NHOM | Khung bao đứng (2.0mm) | nhom_0010 | item=C3318-20, show_cond=`do_day=='2.0mm'`, qty_rule=QTY-KHUNG-DUNG |
| 11 | NHOM | Khung bao đứng (1.4mm) | nhom_0011 | item=C3318-14, show_cond=`do_day=='1.4mm'`, qty_rule=QTY-KHUNG-DUNG |
| 20 | NHOM | Khung ngang trên | nhom_0020 | item=C3303-20, show_cond=`do_day=='2.0mm'`, qty_rule=QTY-KHUNG-NGANG |
| 30 | NHOM | Ngưỡng dưới (có ngưỡng) | nhom_0030 | item=C3350-20, show_cond=`co_nguong=='Yes'`, qty_rule=QTY-KHUNG-NGANG |
| 31 | NHOM | Ngưỡng dưới (không ngưỡng) | nhom_0031 | item=C3303-20, show_cond=`co_nguong=='No' and do_day=='2.0mm'`, qty_rule=QTY-KHUNG-NGANG |
| 35 | NHOM | Đố đứng | nhom_0035 | item=C3200-20, show_cond=`n_do_dung > 0`, qty_rule=QTY-DOC-DUNG |
| 40 | NHOM | Cánh đứng (mở ngoài) | nhom_0040 | item=C3303-20, show_cond=`huong_mo=='Out' and do_day=='2.0mm'`, qty_rule=QTY-CANH-DUNG |
| 41 | NHOM | Cánh đứng (mở trong) | nhom_0041 | item=C3332-20, show_cond=`huong_mo=='In' and do_day=='2.0mm'`, qty_rule=QTY-CANH-DUNG |
| 50 | NHOM | Cánh ngang | nhom_0050 | item=C3303-20, qty_rule=QTY-CANH-NGANG |
| **60** | **NHOM** | **Nẹp kính mỏng ≤10.38mm** | nhom_0060 | item=C3209-20, **show_cond=`glass_thick_kinh_canh <= 10.38`**, qty_rule=QTY-NEP-DUNG |
| **61** | **NHOM** | **Nẹp kính vừa 11–16mm** | nhom_0061 | item=C3210-20, **show_cond=`glass_thick_kinh_canh > 10.38 and glass_thick_kinh_canh <= 16`**, qty_rule=QTY-NEP-DUNG |
| **62** | **NHOM** | **Nẹp kính IGU >16mm** | nhom_0062 | item=C3211-20, **show_cond=`glass_thick_kinh_canh > 16`**, qty_rule=QTY-NEP-DUNG |
| 70 | NHOM | Nẹp kính ngang ≤10.38mm | nhom_0070 | item=C3209-20, show_cond=`glass_thick_kinh_canh <= 10.38`, qty_rule=QTY-NEP-NGANG |
| 71 | NHOM | Nẹp kính ngang 11–16mm | nhom_0071 | item=C3210-20, show_cond=`glass_thick_kinh_canh > 10.38 and glass_thick_kinh_canh <= 16`, qty_rule=QTY-NEP-NGANG |
| 72 | NHOM | Nẹp kính ngang >16mm | nhom_0072 | item=C3211-20, show_cond=`glass_thick_kinh_canh > 16`, qty_rule=QTY-NEP-NGANG |
| **80** | **KINH** | **Kính cánh** | **kinh_canh** | default_glass=KINH-DON-8, prefix=`kinh_canh`, width_formula=`W_mm-86`, height_formula=`H_mm-86`, qty_formula=`n_canh * qty` |
| **90** | **KINH** | **Kính ô thông gió** | **kinh_oc** | default_glass=KINH-CL-10, prefix=`kinh_oc`, show_cond=`co_oc_thong_gio=='Yes'`, width_formula=`W_mm-50`, height_formula=`200` |
| 100 | VTP | Gioăng cánh | vtp_0100 | item=GIO-EPDM-CU, qty_formula=`kinh_canh_total_perimeter_m * 2` |
| 110 | VTP | Gioăng khung | vtp_0110 | item=GIO-EPDM-KH, qty_rule=QTY-GIO-KHUNG |
| 120 | VTP | Gioăng kính mỏng | vtp_0120 | item=GIO-EPDM-K8, show_cond=`max_glass_thick_mm <= 10.38`, qty_formula=`ALL_KINH_total_perimeter_m * 2` |
| 121 | VTP | Gioăng kính dày | vtp_0121 | item=GIO-EPDM-K24, show_cond=`max_glass_thick_mm > 16`, qty_formula=`ALL_KINH_total_perimeter_m * 2` |
| 130 | VTP | Keo silicon | vtp_0130 | item=KEO-SI-DEN, qty_rule=QTY-KEO-SI |
| 140 | VTP | Xốp chèn | vtp_0140 | item=XOP-PHI10, qty_rule=QTY-XOP |
| 150 | VTP | Vít lắp đặt | vtp_0150 | item=VIT-LD-7.5x100, qty_rule=QTY-VIT-LD |

### 6.12 AL Discount Rule — Master Data chuẩn

| name | rule_type | applies_to_customer_group | discount_pct | priority | requires_approval |
|---|---|---|---|---|---|
| DISC-RETAIL-STD | CUSTOMER_TIER | Retail | 0 | 100 | No |
| DISC-PROJECT-5 | PROJECT | (mọi khách) | 5 | 50 | No |
| DISC-PROJECT-10 | PROJECT | Project Partners | 10 | 40 | Yes (>8%) |
| DISC-VOLUME-TIER | VOLUME | (mọi khách) | 0 (xem tier) | 30 | No |
| DISC-SEASONAL-Q4 | SEASONAL | (mọi khách) | 3 | 80 | No |

**Tier cho DISC-VOLUME-TIER:**

| min_qty (bộ) | max_qty (bộ) | discount_pct |
|---|---|---|
| 1 | 9 | 0% |
| 10 | 29 | 3% |
| 30 | 99 | 5% |
| 100 | 0 (không giới hạn) | 8% |

### 6.13 AL Alert Config — Cấu hình mặc định

| alert_type | threshold_value | notify_roles | frequency |
|---|---|---|---|
| PRICE_CHANGE | 5% | AluGlass Kỹ Thuật, AluGlass Admin | REALTIME |
| LOW_STOCK | 50kg | AluGlass Admin | DAILY_DIGEST |
| VARIANCE_ALERT | 15% | AluGlass Admin, Kế toán | REALTIME |
| APPROVAL_PENDING | 24h | AluGlass Admin | DAILY_DIGEST |
| DISCOUNT_EXCEEDED | 8% | AluGlass Admin | REALTIME |

### 6.14 AL BOM — Master Data mẫu

| bom_code | bom_name | brand | product_type | variable_set | profile_set | pk_set | default_cost_template |
|---|---|---|---|---|---|---|---|
| BOM-CUA-DI-XF55-1C | Cửa đi mở quay 1 cánh XF55 | XF-NK | CUA_DI | VAR-CUA-DI | PS-CUA-DI-XF55 | PK-CUA-DI-XF55-1C | CT-01-STANDARD |
| BOM-CUA-DI-XF55-2C | Cửa đi mở quay 2 cánh XF55 | XF-NK | CUA_DI | VAR-CUA-DI | PS-CUA-DI-XF55 | PK-CUA-DI-XF55-2C | CT-01-STANDARD |
| BOM-MAT-HAT-ALUMIL | Cửa mở hất Alumil 1 cánh | ALUMIL | CUA_MAT_HAT | VAR-CUA-MAT-HAT | PS-MAT-HAT-ALUMIL | PK-MAT-HAT-AL | CT-01-STANDARD |
| BOM-VACH-XF65 | Vách kính cố định XF65 | XF-NK | VACH_KINH | VAR-VACH-KINH | PS-VACH-KINH-XF65 | (trống) | CT-01-STANDARD |
| BOM-VACH-XF65-COMPLEX | Vách kính phức tạp (panel expansion) | XF-NK | VACH_KINH | VAR-VACH-KINH | PS-VACH-XF65-COMPLEX | (trống) | CT-01-STANDARD |



### 7.1 VariableResolver v2 — Inject glass_thick

```python
def resolve(self, quotation_item, bom_doc):
    # Bước 1: resolve biến thông thường theo priority
    inputs_dict = self._resolve_bindings(quotation_item, bom_doc)

    # Bước 2: inject glass_thick cho mọi dòng KINH
    profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
    glass_selections = frappe.parse_json(quotation_item.al_glass_selections or "{}")

    for line in profile_set.al_lines:
        if line.line_type != "KINH":
            continue
        prefix = line.ctx_inject_prefix
        glass_code = glass_selections.get(prefix) or line.default_glass_master
        if glass_code:
            thick = frappe.db.get_value("AL Glass Master", glass_code, "total_thick_mm") or 0
            inputs_dict[f"glass_thick_{prefix}"] = float(thick)

    return inputs_dict
```

### 7.2 ProfileInterpreter v2 — 2-pass

#### Pass 1: Scan — đăng ký tên biến

```python
def pass1_scan(self, al_lines, inputs_dict, glass_selections):
    variable_registry = {}
    panel_counts = {}

    for line in sorted(al_lines, key=lambda l: l.sort_order):
        if not line.is_active:
            continue
        slug = line.slug

        if line.line_type == "NHOM":
            variable_registry[slug] = [
                f"{slug}_active", f"{slug}_qty",
                f"{slug}_kg", f"{slug}_dg", f"{slug}_tt"
            ]
        elif line.line_type == "KINH":
            prefix = line.ctx_inject_prefix
            N = self._eval_panel_count(line, inputs_dict)
            panel_counts[slug] = N
            if N == 1:
                vars = [f"{prefix}_W", f"{prefix}_H", f"{prefix}_qty",
                        f"{prefix}_glass_thick_mm", f"{prefix}_m2",
                        f"{prefix}_dg", f"{prefix}_tt", f"{prefix}_cut",
                        f"{prefix}_total_perimeter_m", f"{prefix}_total_m2"]
            else:
                vars = []
                for i in range(N):
                    vars += [f"{prefix}_{i}_W", f"{prefix}_{i}_H",
                             f"{prefix}_{i}_glass_thick_mm",
                             f"{prefix}_{i}_m2", f"{prefix}_{i}_tt"]
                vars += [f"{prefix}_total_perimeter_m", f"{prefix}_total_m2"]
            variable_registry[slug] = vars
        elif line.line_type == "VTP":
            variable_registry[slug] = [
                f"{slug}_active", f"{slug}_qty", f"{slug}_dg", f"{slug}_tt"
            ]
        elif line.line_type == "PK":
            variable_registry[slug] = [
                f"pk_{slug}_qty", f"pk_{slug}_dg", f"pk_{slug}_tt"
            ]

    return variable_registry, panel_counts
```

#### Pass 2: Build formulas

```python
def pass2_build(self, al_lines, inputs_dict, variable_registry, panel_counts, glass_selections, pk_overrides):
    formulas = []
    bucket_acc = defaultdict(list)
    all_panel_thick_vars = []

    for line in sorted(al_lines, key=lambda l: l.sort_order):
        if not line.is_active:
            continue
        slug = line.slug

        if line.line_type == "NHOM":
            formulas += self._build_nhom(line, slug, inputs_dict, bucket_acc)
        elif line.line_type == "KINH":
            N = panel_counts.get(slug, 1)
            prefix = line.ctx_inject_prefix
            new_formulas, thick_vars = self._build_kinh(
                line, slug, prefix, N, inputs_dict, glass_selections, bucket_acc
            )
            formulas += new_formulas
            all_panel_thick_vars += thick_vars
        elif line.line_type == "VTP":
            formulas += self._build_vtp(line, slug, bucket_acc)
        elif line.line_type == "PK":
            formulas += self._build_pk_inline(line, slug, pk_overrides, bucket_acc)

    formulas += self._build_kinh_aggregates(al_lines, panel_counts)

    if all_panel_thick_vars:
        formulas.append({
            "name": "max_glass_thick_mm",
            "formula": f"max({','.join(all_panel_thick_vars)})"
        })

    return formulas, bucket_acc
```

#### _build_nhom — Sinh formula cho dòng NHOM

```python
def _build_nhom(self, line, slug, inputs_dict, bucket_acc):
    formulas = []
    # Active condition
    show_cond = line.show_condition.strip() if line.show_condition else "True"
    formulas.append({"name": f"{slug}_active", "formula": show_cond})

    # Quantity
    if line.quantity_rule:
        qty_expr = self._eval_rule_as_formula(line.quantity_rule)
    else:
        qty_expr = line.qty_formula or "0"
    formulas.append({"name": f"{slug}_qty",
                     "formula": f"IF({slug}_active, {qty_expr}, 0)"})

    # kg/m — hằng số từ DB
    kg_per_m = frappe.db.get_value("Item", line.item_code, "al_kg_per_m") or 0
    formulas.append({"name": f"{slug}_kg", "formula": str(float(kg_per_m))})

    # Đơn giá
    if line.price_type == "Fixed":
        dg_expr = str(float(line.fixed_price or 0))
    elif line.price_type == "Rule":
        dg_expr = self._eval_rule_as_formula(line.price_rule)
    else:  # Item Price — dùng don_gia_nhom từ LOOKUP
        dg_expr = "don_gia_nhom"
    formulas.append({"name": f"{slug}_dg", "formula": dg_expr})

    # Thành tiền
    formulas.append({"name": f"{slug}_tt",
                     "formula": f"{slug}_qty * {slug}_kg * {slug}_dg"})

    # Bucket
    bucket = line.cost_bucket or "VL_NHOM"
    bucket_acc[bucket].append(f"{slug}_tt")
    return formulas
```

#### _build_kinh — Sinh formula cho dòng KINH (với Panel Expansion)

```python
def _build_kinh(self, line, slug, prefix, N, inputs_dict, glass_selections, bucket_acc):
    formulas = []
    all_thick_vars = []
    glass_thick_var = f"glass_thick_{prefix}"  # đã inject vào inputs_dict

    for i in range(N):
        p = f"{prefix}_{i}" if N > 1 else prefix

        # glass_thick từng panel (có thể override nếu panel_glass_override_allowed)
        panel_key = f"{prefix}__{i}" if N > 1 else prefix
        override_glass = glass_selections.get(panel_key)
        default_glass = glass_selections.get(prefix) or line.default_glass_master
        if override_glass and override_glass != default_glass:
            thick = frappe.db.get_value("AL Glass Master", override_glass, "total_thick_mm") or 0
            formulas.append({"name": f"{p}_glass_thick_mm", "formula": str(float(thick))})
        else:
            formulas.append({"name": f"{p}_glass_thick_mm", "formula": glass_thick_var})
        all_thick_vars.append(f"{p}_glass_thick_mm")

        # Chiều rộng
        if line.width_rule:
            w_expr = self._eval_rule_as_formula(line.width_rule)
        else:
            w_expr = line.width_formula or "W_mm"
        formulas.append({"name": f"{p}_W", "formula": w_expr})

        # Chiều cao
        if line.height_rule:
            h_expr = self._eval_rule_as_formula(line.height_rule)
        else:
            h_expr = line.height_formula or "H_mm"
        formulas.append({"name": f"{p}_H", "formula": h_expr})

        # Số lượng
        qty_expr = line.qty_per_panel_formula or "1"
        formulas.append({"name": f"{p}_qty", "formula": qty_expr})

        # Diện tích m²
        formulas.append({"name": f"{p}_m2",
                         "formula": f"{p}_W * {p}_H / 1000000 * {p}_qty"})

        # Đơn giá kính (hằng số từ Item Price)
        glass_code = glass_selections.get(panel_key) or default_glass
        dg = self._get_glass_price(glass_code, line.price_list) or 0
        formulas.append({"name": f"{p}_dg", "formula": str(float(dg))})

        # Thành tiền
        formulas.append({"name": f"{p}_tt", "formula": f"{p}_m2 * {p}_dg"})

        # Phí cắt kính
        cut_pct = line.cut_fee_pct or 0
        formulas.append({"name": f"{p}_cut",
                         "formula": f"{p}_tt * {cut_pct / 100}"})

        bucket_acc["VL_KINH"].append(f"{p}_tt")
        bucket_acc["OH_CUT_KINH"].append(f"{p}_cut")

    return formulas, all_thick_vars

def _build_kinh_aggregates(self, al_lines, panel_counts):
    """Sinh formula tổng hợp cho từng dòng kính và toàn bộ."""
    formulas = []
    all_prefixes = []

    for line in al_lines:
        if line.line_type != "KINH" or not line.is_active:
            continue
        prefix = line.ctx_inject_prefix
        slug = line.slug
        N = panel_counts.get(slug, 1)
        all_prefixes.append(prefix)

        if N == 1:
            formulas.append({
                "name": f"{prefix}_total_perimeter_m",
                "formula": f"({prefix}_W + {prefix}_H) / 1000"
            })
            formulas.append({
                "name": f"{prefix}_total_m2",
                "formula": f"{prefix}_m2"
            })
        else:
            perimeter_parts = [f"({prefix}_{i}_W + {prefix}_{i}_H)/1000" for i in range(N)]
            m2_parts = [f"{prefix}_{i}_m2" for i in range(N)]
            formulas.append({
                "name": f"{prefix}_total_perimeter_m",
                "formula": " + ".join(perimeter_parts)
            })
            formulas.append({
                "name": f"{prefix}_total_m2",
                "formula": " + ".join(m2_parts)
            })

    # Tổng toàn bộ kính
    if all_prefixes:
        formulas.append({
            "name": "ALL_KINH_total_perimeter_m",
            "formula": " + ".join(f"{p}_total_perimeter_m" for p in all_prefixes)
        })
        formulas.append({
            "name": "ALL_KINH_total_m2",
            "formula": " + ".join(f"{p}_total_m2" for p in all_prefixes)
        })

    return formulas
```

#### _build_vtp — Sinh formula cho dòng VTP

```python
def _build_vtp(self, line, slug, bucket_acc):
    formulas = []
    show_cond = line.show_condition.strip() if line.show_condition else "True"
    formulas.append({"name": f"{slug}_active", "formula": show_cond})

    if line.quantity_rule:
        qty_expr = self._eval_rule_as_formula(line.quantity_rule)
    else:
        qty_expr = line.qty_formula or "0"
    formulas.append({"name": f"{slug}_qty",
                     "formula": f"IF({slug}_active, {qty_expr}, 0)"})

    # Đơn giá VTP
    if line.price_type == "Fixed":
        dg_expr = str(float(line.fixed_price or 0))
    elif line.price_type == "Rule":
        dg_expr = self._eval_rule_as_formula(line.price_rule)
    else:
        dg = self._get_item_price(line.item_code, line.price_list) or 0
        dg_expr = str(float(dg))
    formulas.append({"name": f"{slug}_dg", "formula": dg_expr})

    formulas.append({"name": f"{slug}_tt",
                     "formula": f"{slug}_qty * {slug}_dg"})

    bucket = line.cost_bucket or "VL_VTP"
    bucket_acc[bucket].append(f"{slug}_tt")
    return formulas
```

### 7.3 show_condition → Nhánh DAG

Mỗi `show_condition` được sinh thành `{slug}_active = <show_condition>` trong DAG. Nhờ 2-pass scan, tên biến `glass_thick_kinh_canh` đã được đăng ký từ Pass 1 — khi ProfileInterpreter gặp dòng NHOM có `show_condition = "glass_thick_kinh_canh <= 10.38"` ở Pass 2, tên biến này đã hợp lệ.

FormulaEngine xây DAG: `nhom_0060_active` phụ thuộc `glass_thick_kinh_canh`, mà `glass_thick_kinh_canh` là input (đã có trong `inputs_dict`). Không có circular dependency.

### 7.4 Nhiều loại kính — Context đầy đủ

```
Sản phẩm có 2 dòng kính (kinh_canh 8.38mm + kinh_oc 10mm):

inputs_dict (sau VariableResolver.resolve):
  W_mm = 2500, H_mm = 3100, n_canh = 1, qty = 1
  glass_thick_kinh_canh = 8.38   ← inject từ KINH-DON-8
  glass_thick_kinh_oc   = 10.0   ← inject từ KINH-CL-10

Formulas sinh ra (ví dụ dòng nẹp sort 60):
  nhom_0060_active = glass_thick_kinh_canh <= 10.38         → True  (8.38 ≤ 10.38)
  nhom_0061_active = glass_thick_kinh_canh > 10.38 and ...  → False
  nhom_0062_active = glass_thick_kinh_canh > 16             → False

Formulas dòng kính:
  kinh_canh_W              = W_mm - 86   → 2414
  kinh_canh_glass_thick_mm = glass_thick_kinh_canh → 8.38
  kinh_oc_W                = W_mm - 50   → 2450
  kinh_oc_glass_thick_mm   = glass_thick_kinh_oc   → 10.0

max_glass_thick_mm = max(kinh_canh_glass_thick_mm, kinh_oc_glass_thick_mm) → 10.0

Gioăng kính (VTP):
  vtp_0120_active = max_glass_thick_mm <= 10.38  → True (10.0 ≤ 10.38)
  vtp_0121_active = max_glass_thick_mm > 16      → False

KẾT QUẢ: Nẹp dùng loại ≤10.38mm, Gioăng dùng loại mỏng — đúng nghiệp vụ
```

### 7.5 AL Calculation Rule — cách inline vào FormulaEngine

| rule_type | Cách xử lý |
|---|---|
| CONSTANT | Gán trực tiếp vào inputs_dict |
| FORMULA | Inline thành formula trong formulas_list |
| THRESHOLD | Inline thành `IFS(...)` |
| LOOKUP | Tra Python → kết quả vào inputs_dict |
| SEQUENCE | Mỗi sequence_item = 1 formula |

### 7.4 Module Hook Registry — Event Bus Pattern ★ MỚI v17

```python
# aluglass/engine/module_registry.py

_hooks: Dict[str, List[callable]] = defaultdict(list)

def register_hook(event: str, fn: callable):
    _hooks[event].append(fn)

def fire_hooks(event: str, **kwargs):
    for fn in _hooks.get(event, []):
        try:
            fn(**kwargs)
        except Exception as e:
            frappe.log_error(f'Hook {fn.__name__}: {e}')

# Trong BomOrchestrator.run() sau bước 6:
fire_hooks('after_calculate', result=result, quotation_item=qi, bom_doc=bom_doc)

# Trong module discount __init__.py:
register_hook('after_calculate', DiscountStack.apply)
```

### 7.5 BOM Version Manager ★ MỚI v17

```python
class BOMVersionManager:
    def publish(self, bom_doc, change_summary='', reviewer=None):
        # 1. Lấy toàn bộ snapshot
        ps_snap = frappe.get_doc('AL Profile Set', bom_doc.profile_set).as_dict()
        vs_snap = frappe.get_doc('AL Variable Set', bom_doc.variable_set).as_dict()
        ct_snap = frappe.get_doc('AL Cost Template', bom_doc.default_cost_template).as_dict()
        pk_snap = frappe.get_doc('AL PK Set', bom_doc.pk_set).as_dict() if bom_doc.pk_set else {}

        # 2. Serialize & hash
        payload = json.dumps({'ps': ps_snap, 'vs': vs_snap, 'ct': ct_snap, 'pk': pk_snap}, sort_keys=True)
        snap_hash = hashlib.sha256(payload.encode()).hexdigest()

        # 3. Tạo AL BOM Version
        version_number = frappe.db.count('AL BOM Version', {'bom': bom_doc.name}) + 1
        ver = frappe.new_doc('AL BOM Version')
        ver.bom = bom_doc.name
        ver.version_number = version_number
        ver.profile_set_snapshot = payload
        ver.snapshot_hash = snap_hash
        ver.change_summary = change_summary
        ver.status = 'Draft' if bom_doc.requires_approval_for_new_version else 'Published'
        ver.insert(ignore_permissions=True)

        # 4. Cập nhật BOM.current_version nếu Published
        if ver.status == 'Published':
            bom_doc.db_set('current_version', ver.name)
        return ver
```

### 7.6 DiscountStack.apply() ★ MỚI v17

```python
class DiscountStack:
    @staticmethod
    def apply(result, quotation_item, bom_doc, **kwargs):
        customer = frappe.db.get_value('Quotation', quotation_item.parent, 'party_name')
        cg = frappe.db.get_value('Customer', customer, 'customer_group')
        qty = quotation_item.qty or 1
        amount = result.get('GIA_BAN', 0)

        # Tìm rules applicable
        rules = frappe.get_all('AL Discount Rule', filters={'is_active': 1},
                               order_by='priority asc')
        applicable = [r for r in rules if _rule_matches(r, customer, cg, bom_doc, amount)]

        # Resolve stack
        total_disc = 0.0
        applied_rule = None
        for r in applicable:
            rule_doc = frappe.get_doc('AL Discount Rule', r.name)
            disc = _get_discount_pct(rule_doc, qty)
            if not rule_doc.stackable:
                total_disc = disc; applied_rule = r.name; break
            else:
                total_disc += disc; applied_rule = applied_rule or r.name

        # Check max_total_discount
        max_disc = frappe.db.get_single_value('AL Alert Config', 'max_total_discount_pct') or 15
        total_disc = min(total_disc, max_disc)

        # Ghi vào quotation_item
        gia_ban_thuong_mai = amount * (1 - total_disc / 100)
        quotation_item.db_set('al_discount_pct', total_disc)
        quotation_item.db_set('al_gia_thuong_mai', gia_ban_thuong_mai)
        quotation_item.db_set('al_discount_rule', applied_rule)

        # Trigger approval nếu cần
        if total_disc > (rule_doc.approval_threshold_pct or 0):
            quotation_item.db_set('al_approval_status', 'PENDING')
```

### 7.7 MRP Lite — Aggregation Logic ★ MỚI v17

```python
class MRPAggregator:
    def aggregate(self, plan_doc):
        item_acc: Dict[str, dict] = {}

        sources = (plan_doc.quotation_list or []) + (plan_doc.so_list or [])
        for src_name in sources:
            items = self._get_bom_items_from_snapshot(src_name)
            for item in items:
                key = item['item_code']
                if key not in item_acc:
                    item_acc[key] = {'qty': 0, 'type': item['type'], 'uom': item['uom'], 'sources': []}
                item_acc[key]['qty'] += item['qty']
                item_acc[key]['sources'].append(src_name)

        # Apply safety stock
        safety_pct = (plan_doc.include_safety_stock_pct or 0) / 100
        for key, data in item_acc.items():
            gross = data['qty']
            safety = gross * safety_pct
            net = gross + safety
            current_stock = frappe.db.get_value('Bin', {'item_code': key}, 'actual_qty') or 0
            to_purchase = max(0, net - current_stock)
            data.update({'qty_gross': gross, 'safety': safety, 'qty_net': net,
                         'current_stock': current_stock, 'to_purchase': to_purchase})

        return item_acc

    def _get_bom_items_from_snapshot(self, source_name):
        """Đọc vật tư từ ConfigSnapshot — không đọc lại Profile Set hiện tại."""
        items = []
        qi_list = frappe.get_all('Quotation Item',
                                 filters={'parent': source_name},
                                 fields=['al_config_snapshot', 'al_W_mm', 'al_H_mm', 'qty'])
        for qi in qi_list:
            if not qi.al_config_snapshot:
                continue
            snap = frappe.get_doc('ConfigSnapshot', qi.al_config_snapshot)
            enterprise_snap = json.loads(snap.enterprise_snapshot_json)
            for var_name, value in enterprise_snap.get('formulas', {}).items():
                if '_qty' in var_name and not var_name.startswith('kinh_'):
                    item_code = self._resolve_item_code_from_slug(var_name, snap)
                    if item_code:
                        items.append({'item_code': item_code, 'qty': value * qi.qty, 'type': 'NHOM', 'uom': 'Kg'})
        return items
```

---

## VIII. BOMORCHESTR ATOR v17 — 6 BƯỚC + MODULE HOOKS

| Bước | Component v17 | Chi tiết | Thay đổi so với v16 |
|---|---|---|---|
| 1 | VariableResolver.resolve() | inputs_dict đầy đủ + inject glass_thick_{prefix} | Không đổi |
| 2 | ProfileInterpreter.pass1_scan() | variable_registry, panel_counts | Không đổi |
| 3 | ProfileInterpreter.pass2_build() | all_formulas theo sort_order, DAG tự xử lý | Không đổi |
| 4 | PkResolver.build_formulas() | formulas_pk, warnings | Không đổi |
| 5 | CostAccumulator.build_bucket_and_template_formulas() | formulas_bucket, formulas_cost_template | Không đổi |
| 6 | FormulaEngine.calculate() + SnapshotBuilder.persist() | DUY NHẤT 1 lần calculate() | Không đổi |
| **Hook A** | **DiscountStack.apply()** | Áp chiết khấu, ghi al_discount_pct, al_gia_thuong_mai | **★ MỚI v17** |
| **Hook B** | **BOMVersionManager.link_version()** | Gắn al_bom_version vào Quotation Item | **★ MỚI v17** |
| **Hook C** | **CostVarianceAnalyzer.register()** | Đăng ký reference cho so sánh sau | **★ MỚI v17** |
| **Hook D** | **NotificationEngine.check_alerts()** | Kiểm tra và phát cảnh báo | **★ MỚI v17** |

> **Nguyên tắc Module Hook:**
> - BomOrchestrator KHÔNG import module nào từ Tầng 6 — không bị phụ thuộc ngược
> - Mỗi module tự register hook khi app load (hooks.py → `__init__.py`)
> - Nếu hook thất bại: log error, không block kết quả tính giá trả về Sales
> - Hooks chạy tuần tự theo thứ tự register: A → B → C → D
> - Timeout per hook: 5 giây. Vượt quá → log warning, bỏ qua hook đó

---

## IX. REPORTING & DASHBOARD — ĐẶC TẢ ĐẦY ĐỦ

### 9.1 Danh sách Reports

| Report Name | Loại | Dữ liệu nguồn | Vai trò truy cập |
|---|---|---|---|
| AL Quotation Summary | Script Report | Quotation + Quotation Item al_* | Sales, Admin |
| AL BOM Price Analysis | Script Report | ConfigSnapshot + al_lines + Rule | Kỹ Thuật, Admin |
| AL Sales Pipeline | Script Report | Quotation → SO → SI conversion | Sales, Admin |
| AL Material Cost Variance | Script Report | AL Cost Variance + Purchase Invoice | Admin, Kế toán |
| AL Material Requirements | Script Report | AL Material Plan + Bin | Admin, Mua hàng |
| AL BOM Version History | List Report | AL BOM Version + AL BOM Change Log | Kỹ Thuật, Admin |
| AL Discount Utilization | Script Report | Quotation Item al_discount_* fields | Sales, Admin |
| AL Sales KPI Dashboard | Dashboard | Quotation + SO + SI + AL Sales KPI | Sales, Admin |
| AL Glass Consumption | Script Report | SO Item + AL Profile Line KINH | Kỹ Thuật, Kho |
| AL Cost Variance Alert | Alert Report | AL Cost Variance variance_status=ALERT | Admin, Kế toán |

### 9.2 Dashboard Widgets theo Vai trò

#### AluGlass Admin Dashboard

| Widget | Loại | Metric chính |
|---|---|---|
| Doanh số tháng này | Number | Tổng GIA_VAT SO đã Submitted tháng hiện tại |
| Quotation → SO Rate | Gauge | % Quotation chuyển thành SO (30 ngày) |
| Top 5 BOM theo doanh số | Bar Chart | BOM name vs tổng GIA_BAN |
| Cost Variance Alert | Alert List | Danh sách variance > 15% chưa review |
| Pending Approvals | Count Badge | Số Quotation Item al_approval_status=PENDING |
| Material Plan Status | List | AL Material Plan Draft/Confirmed gần nhất |
| Sales Pipeline | Funnel Chart | Quotation Draft → Submitted → SO → SI |
| BOM Version Activity | Timeline | BOM version publish 30 ngày gần nhất |

#### AluGlass Sales Dashboard

| Widget | Loại | Metric chính |
|---|---|---|
| Quotation của tôi | Number | Tổng Quotation tháng này của user đăng nhập |
| KPI cá nhân | Progress Bar | Actual vs Target từ AL Sales KPI |
| Discount đang dùng | Pie Chart | Phân bổ % discount theo rule type |
| Pending Approval của tôi | List | Quotation Item chờ duyệt discount |
| Top sản phẩm bán | Bar Chart | BOM vs số lượng Quotation trong tháng |

#### AluGlass Kỹ Thuật Dashboard

| Widget | Loại | Metric chính |
|---|---|---|
| BOM đang active | Number | Số BOM có current_version Published |
| BOM Version mới nhất | List | 5 BOM version publish gần nhất |
| Alert giá kính | Alert List | Glass Item có price thay đổi > 5% so với ConfigSnapshot |
| BOM sắp hết hạn | List | BOM version quá 180 ngày chưa review |
| Glass Consumption | Bar Chart | Tiêu thụ kính theo loại trong tháng |

---

## X. BOM VERSION CONTROL — ĐẶC TẢ ĐẦY ĐỦ

### 10.1 Vòng đời BOM Version

| Trạng thái | Mô tả | Chuyển sang |
|---|---|---|
| Draft | Version mới tạo, chưa duyệt | Published (nếu không cần duyệt) hoặc gửi duyệt |
| Pending Approval | Đang chờ duyệt | Published (approved) / Rejected |
| Published | Active — Quotation mới dùng version này | Deprecated |
| Deprecated | Không dùng nữa — GIỮ NGUYÊN để Quotation cũ tham chiếu | — |
| Rejected | Bị từ chối — quay về Draft để sửa | Draft |

### 10.2 Diff Tool — So sánh 2 phiên bản BOM

```python
# API: aluglass.modules.version.compare_versions(ver_a_name, ver_b_name) → DiffResult

DiffResult = {
    'added_lines': [{'slug': '...', 'line_type': 'NHOM', ...}],
    'removed_lines': [{'slug': '...', ...}],
    'modified_lines': [{'slug': '...', 'changes': [{'field': 'qty_formula', 'old': '...', 'new': '...'}]}],
    'formula_changes': [{'rule': 'QTY-KHUNG-DUNG', 'old': '...', 'new': '...'}],
    'price_changes': [{'item_code': 'C3318', 'old_price': 113000, 'new_price': 118000, 'change_pct': 4.4}],
    'summary': 'Thêm 2 dòng VTP, sửa formula nẹp kính, giá nhôm +4.4%'
}
```

### 10.3 Rollback

```python
def rollback(self, target_version_name, requester):
    # 1. Lấy target_version.profile_set_snapshot + variable_set_snapshot + ...
    # 2. Restore AL Profile Set từ JSON snapshot (delete old al_lines, recreate)
    # 3. Publish version mới (version_number = max + 1) với is_rollback_of = target_version
    # 4. Ghi AL BOM Change Log: change_type=ROLLBACK
    # 5. Phát notification tới AluGlass Kỹ Thuật
    # LƯU Ý: Rollback TẠO VERSION MỚI, không xóa version nào
```

---

## XI. APPROVAL WORKFLOW — ĐẶC TẢ ĐẦY ĐỦ

### 11.1 Hai loại Approval cần thiết

| Loại | Trigger | Approver | Timeout | Hành động nếu quá hạn |
|---|---|---|---|---|
| BOM Version Approval | BOM.requires_approval_for_new_version=1 và nhấn Publish | AluGlass Admin | 48h | Escalate → Director; gửi email nhắc |
| Discount Approval | al_discount_pct > approval_threshold_pct | AluGlass Admin | 24h | Notify Admin; Sales không thể submit Quotation |

### 11.2 Luồng Discount Approval

| Bước | Actor | Hành động | Kết quả |
|---|---|---|---|
| 1 | Sales | Nhập kích thước, bấm Tính giá. Chọn discount rule > threshold | Hệ thống set al_approval_status=PENDING; khóa Quotation Item |
| 2 | System | Tạo Frappe Notification cho AluGlass Admin + gửi email | Admin nhận yêu cầu duyệt |
| 3 | Admin | Xem Quotation, kiểm tra giá, nhấn Approve hoặc Reject | al_approval_status=APPROVED/REJECTED |
| 4a | System (Approved) | Mở khóa Quotation Item; Sales có thể submit | Quotation tiếp tục bình thường |
| 4b | System (Rejected) | Notify Sales với al_approval_note | Sales điều chỉnh rồi tính lại |

### 11.3 Hook before_submit Quotation

```python
# hooks.py
doc_events = {
    'Quotation': {
        'before_submit': 'aluglass.modules.approval.check_pending_approvals'
    }
}

# aluglass/modules/approval.py
def check_pending_approvals(doc, method):
    pending = [i for i in doc.items if i.get('al_approval_status') == 'PENDING']
    if pending:
        frappe.throw(_(
            'Có {0} dòng chờ duyệt discount. Vui lòng chờ Admin duyệt trước khi Submit.'
        ).format(len(pending)))
```

---

## XII. AL DISCOUNT RULE — ĐẶC TẢ ĐẦY ĐỦ

### 12.1 Các loại Discount Rule

| rule_type | Mô tả | Trường match | Discount xác định bởi |
|---|---|---|---|
| CUSTOMER_TIER | Chiết khấu theo nhóm khách hàng cố định | applies_to_customer_group, applies_to_customer | discount_pct (cố định) |
| PROJECT | Chiết khấu dự án — Admin gán thủ công | applies_to_customer hoặc trống | discount_pct hoặc nhập tay |
| VOLUME | Chiết khấu theo số lượng — dùng bảng tier | min_qty ≤ qty ≤ max_qty | AL Discount Rule Line tier |
| SEASONAL | Chiết khấu theo kỳ — valid_from/valid_to | Tự động theo ngày | discount_pct (cố định) |
| MANUAL | Admin nhập trực tiếp % discount — cần approval | Không auto-match | Nhập tay trong Dialog |

### 12.2 Stack Resolution — Ưu tiên áp dụng

| Trường hợp | Kết quả |
|---|---|
| Chỉ 1 rule match | Áp discount_pct của rule đó |
| Nhiều rule, tất cả stackable=No | Lấy rule priority thấp nhất (số nhỏ = ưu tiên cao) |
| Nhiều rule, có rule stackable=Yes | Cộng dồn tất cả stackable + lấy 1 non-stackable priority cao nhất |
| Tổng discount > max_total_discount_pct | Cap tại max_total_discount_pct; ghi cảnh báo |
| MANUAL rule được thêm vào | Cộng thêm vào stack; nếu tổng > threshold → yêu cầu approval |

---

## XIII. MATERIAL PLANNING (MRP LITE) — ĐẶC TẢ ĐẦY ĐỦ

### 13.1 Luồng tạo Material Plan

| Bước | Actor | Hành động |
|---|---|---|
| 1 | AluGlass Admin | Tạo AL Material Plan mới, chọn source_type |
| 2 | Admin | Chọn danh sách Quotation / SO cần tổng hợp vật tư |
| 3 | Admin | Chọn aggregation_method và include_safety_stock_pct |
| 4 | System | MRPAggregator.aggregate() đọc ConfigSnapshot → tổng hợp al_plan_lines |
| 5 | Admin | Review al_plan_lines, điều chỉnh qty_to_purchase nếu cần |
| 6 | Admin | Nhấn Confirm → status = Confirmed |
| 7 | Admin (tùy chọn) | Nhấn Generate Purchase Order → tạo ERPNext Purchase Order |
| 8 | System | Sau khi Purchase Invoice posted: tự tạo AL Cost Variance cho từng item |

> **Nguyên tắc quan trọng:** MRPAggregator không đọc lại Profile Set hiện tại mà đọc từ ConfigSnapshot đã lưu — đảm bảo số lượng khớp đúng giá đã báo cho khách.

### 13.2 Generate Purchase Order từ Material Plan

```python
def generate_purchase_orders(self, plan_doc):
    """Tạo PO theo từng supplier từ Material Plan đã Confirmed."""
    supplier_items = defaultdict(list)

    for line in plan_doc.al_plan_lines:
        if line.qty_to_purchase <= 0:
            continue
        # Tra supplier mặc định của item
        supplier = frappe.db.get_value('Item Default', {
            'parent': line.item_code,
            'company': frappe.defaults.get_user_default('Company')
        }, 'default_supplier')

        if not supplier:
            # Tra từ Item Supplier List
            supplier_row = frappe.db.get_value('Item Supplier',
                {'parent': line.item_code}, 'supplier')
            supplier = supplier_row or 'UNKNOWN'

        supplier_items[supplier].append({
            'item_code': line.item_code,
            'qty': line.qty_to_purchase,
            'uom': line.uom,
            'rate': line.estimated_unit_price,
        })

    pos = []
    for supplier, items in supplier_items.items():
        if supplier == 'UNKNOWN':
            frappe.log_error(f'Material Plan {plan_doc.name}: some items have no default supplier')
            continue
        po = frappe.new_doc('Purchase Order')
        po.supplier = supplier
        po.schedule_date = frappe.utils.add_days(frappe.utils.today(), 7)
        for item in items:
            po.append('items', item)
        po.insert()
        pos.append(po.name)

    plan_doc.db_set('status', 'Purchased')
    return pos
```

---

## XIV. COST VARIANCE ANALYSIS — ĐẶC TẢ ĐẦY ĐỦ

### 14.1 Trigger tạo AL Cost Variance

```python
# hooks.py
doc_events = {
    'Purchase Invoice': {
        'on_submit': 'aluglass.modules.cost_variance.on_purchase_invoice_submit'
    }
}

def on_purchase_invoice_submit(doc, method):
    for item in doc.items:
        qi_list = find_related_quotation_items(item.item_code, doc.posting_date)
        for qi in qi_list:
            create_cost_variance(qi, item, doc)

def find_related_quotation_items(item_code, posting_date):
    """Tìm Quotation Items dùng item này trong vòng 90 ngày trước posting_date."""
    since = frappe.utils.add_days(posting_date, -90)
    return frappe.db.sql("""
        SELECT qi.name, qi.al_config_snapshot, qi.qty
        FROM `tabQuotation Item` qi
        JOIN `tabQuotation` q ON qi.parent = q.name
        WHERE qi.al_config_snapshot IS NOT NULL
          AND q.docstatus = 1
          AND q.transaction_date >= %s
          AND JSON_CONTAINS(
            (SELECT enterprise_snapshot_json FROM `tabConfigSnapshot`
             WHERE name = qi.al_config_snapshot),
            JSON_QUOTE(%s), '$.inputs'
          )
    """, (since, item_code), as_dict=True)

def create_cost_variance(qi, pi_item, pi_doc):
    """Tạo AL Cost Variance record, tránh duplicate."""
    existing = frappe.db.exists('AL Cost Variance', {
        'quotation_item': qi.name,
        'purchase_invoice': pi_doc.name,
        'item_code': pi_item.item_code
    })
    if existing:
        return  # Không tạo trùng

    snap = frappe.get_doc('ConfigSnapshot', qi.al_config_snapshot)
    enterprise_snap = json.loads(snap.enterprise_snapshot_json)

    # Lấy giá đã báo từ ConfigSnapshot
    quoted_price = enterprise_snap.get('inputs', {}).get(
        f'don_gia_{pi_item.item_code.lower().replace("-", "_")}', 0
    ) or pi_item.rate  # fallback

    actual_price = pi_item.rate
    variance_pct = ((actual_price - quoted_price) / quoted_price * 100) if quoted_price else 0

    if variance_pct < -5:
        status = 'FAVORABLE'
    elif variance_pct < 5:
        status = 'NORMAL'
    elif variance_pct < 15:
        status = 'CAUTION'
    else:
        status = 'ALERT'

    cv = frappe.new_doc('AL Cost Variance')
    cv.quotation_item = qi.name
    cv.config_snapshot = qi.al_config_snapshot
    cv.purchase_invoice = pi_doc.name
    cv.item_code = pi_item.item_code
    cv.quoted_unit_price = quoted_price
    cv.actual_unit_price = actual_price
    cv.variance_amount = actual_price - quoted_price
    cv.variance_pct = variance_pct
    cv.variance_status = status
    cv.impact_on_margin = (actual_price - quoted_price) * qi.qty
    cv.insert(ignore_permissions=True)
```

### 14.3 Báo cáo AL Material Cost Variance

Script Report tổng hợp theo kỳ (date range):

| Cột | Nguồn | Ghi chú |
|---|---|---|
| item_code, item_name | AL Cost Variance | |
| item_type | Item.al_item_type | NHOM / KINH / VTP / PK |
| avg_quoted_price | trung bình quoted_unit_price trong kỳ | |
| avg_actual_price | trung bình actual_unit_price trong kỳ | |
| avg_variance_pct | trung bình variance_pct | |
| max_variance_pct | max variance_pct trong kỳ | |
| total_impact_on_margin | tổng impact_on_margin trong kỳ | Số âm = lợi, số dương = mất |
| count_normal | số record status=NORMAL | |
| count_caution | số record status=CAUTION | |
| count_alert | số record status=ALERT | Cần highlight đỏ |
| reviewed_pct | % record đã được reviewed_by điền | KPI chất lượng review |

Filters: date_from, date_to, item_type, variance_status, reviewed_only

| variance_pct | variance_status | Hành động tự động | Màu hiển thị |
|---|---|---|---|
| < 5% | NORMAL | Không cần action | Xanh lá |
| 5% – 15% | CAUTION | Gửi email Daily Digest cho Admin | Vàng cam |
| > 15% | ALERT | REALTIME notification; hiển thị Dashboard Alert | Đỏ |
| < -5% (giá thực thấp hơn) | FAVORABLE | Ghi chú; không cần action | Xanh dương |

---

## XV. NOTIFICATION & ALERT ENGINE — ĐẶC TẢ ĐẦY ĐỦ

### 15.1 NotificationEngine.check_alerts() — Logic kiểm tra

| Alert Type | Kiểm tra | Điều kiện trigger | Nội dung thông báo |
|---|---|---|---|
| PRICE_CHANGE | Item Price hiện tại vs giá trong ConfigSnapshot gần nhất | Chênh lệch > threshold_value% | Item {X} thay đổi giá {old}→{new} ({pct}%). Cần xem xét lại BOM liên quan. |
| LOW_STOCK | Frappe Bin.actual_qty cho Item nhôm/kính | actual_qty < threshold_value | Tồn kho {item} còn {qty} dưới mức tối thiểu {threshold}. |
| BOM_EXPIRY | AL BOM Version.published_on so với hôm nay | Ngày publish > 180 ngày | BOM {name} chưa được review trong {days} ngày. |
| VARIANCE_ALERT | AL Cost Variance.variance_status | Có record mới status=ALERT chưa review | Biến động giá bất thường: {item} +{pct}%, ảnh hưởng margin {amount}. |
| APPROVAL_PENDING | Quotation Item.al_approval_status=PENDING | Pending > timeout_hours (24h) | Yêu cầu duyệt discount từ {sales_user} đã chờ {hours} giờ. |

### 15.1a Code NotificationEngine

```python
# aluglass/modules/notification/notification_engine.py

class NotificationEngine:
    @staticmethod
    def check_alerts(result, bom_doc, **kwargs):
        """Hook D — chạy sau FormulaEngine.calculate()."""
        alerts = frappe.get_all('AL Alert Config',
                                filters={'is_active': 1},
                                fields=['*'])
        for alert in alerts:
            if alert.alert_type == 'PRICE_CHANGE':
                NotificationEngine._check_price_change(alert, bom_doc)
            elif alert.alert_type == 'LOW_STOCK':
                NotificationEngine._check_low_stock(alert)

    @staticmethod
    def _check_price_change(alert, bom_doc):
        """So sánh Item Price hiện tại vs giá trong ConfigSnapshot gần nhất."""
        recent_snaps = frappe.get_all('ConfigSnapshot',
            filters={'profile_set': bom_doc.profile_set},
            order_by='created_at desc', limit=1)
        if not recent_snaps:
            return
        snap = frappe.get_doc('ConfigSnapshot', recent_snaps[0].name)
        old_prices = json.loads(snap.enterprise_snapshot_json).get('inputs', {})

        kinh_items = frappe.get_all('AL Profile Line', filters={
            'parent': bom_doc.profile_set, 'line_type': 'KINH'
        }, fields=['default_glass_master'])

        for kinh in kinh_items:
            item_code = frappe.db.get_value('AL Glass Master',
                                            kinh.default_glass_master, 'name')
            if not item_code:
                continue
            current_price = frappe.db.get_value('Item Price',
                {'item_code': item_code}, 'price_list_rate') or 0
            old_price = old_prices.get(f'don_gia_{item_code.lower()}', current_price)
            if old_price and abs(current_price - old_price) / old_price * 100 > alert.threshold_value:
                NotificationEngine._send(alert, {
                    'item': item_code,
                    'old': old_price, 'new': current_price,
                    'pct': round((current_price - old_price) / old_price * 100, 1)
                })

    @staticmethod
    def _check_low_stock(alert):
        """Kiểm tra Bin.actual_qty cho tất cả Item nhôm/kính."""
        nhom_items = frappe.get_all('Item',
            filters={'al_item_type': ['in', ['NHOM_PROFILE', 'KINH']]},
            fields=['name'])
        for item in nhom_items:
            qty = frappe.db.get_value('Bin',
                {'item_code': item.name}, 'actual_qty') or 0
            if qty < alert.threshold_value:
                NotificationEngine._send(alert, {
                    'item': item.name, 'qty': qty,
                    'threshold': alert.threshold_value
                })

    @staticmethod
    def _send(alert, context):
        roles = json.loads(alert.notify_roles or '[]')
        users = json.loads(alert.notify_users or '[]')
        # Expand roles to users
        for role in roles:
            role_users = frappe.get_all('Has Role', filters={'role': role},
                                        fields=['parent'])
            users += [u.parent for u in role_users]
        users = list(set(users))

        channel = alert.notification_channel or 'FRAPPE_NOTIFICATION'
        for user in users:
            if channel in ('FRAPPE_NOTIFICATION', 'BOTH'):
                frappe.publish_realtime('aluglass_alert', context, user=user)
            if channel in ('EMAIL', 'BOTH'):
                frappe.sendmail(recipients=[user],
                                subject=f'AluGlass Alert: {alert.alert_name}',
                                message=str(context))
```

### 15.2 Channels

| Channel | Cơ chế | Cấu hình |
|---|---|---|
| FRAPPE_NOTIFICATION | frappe.publish_realtime + Frappe Notification DocType | Hiển thị trong bell icon Frappe sidebar |
| EMAIL | Frappe Email Queue (frappe.sendmail) | Template email trong Frappe Email Template |
| BOTH | Gửi cả 2 kênh song song | Combine cả 2 cấu hình trên |

---

## XVI. SALES ANALYTICS MODULE — ĐẶC TẢ ĐẦY ĐỦ

### 16.1 AL Sales KPI — Schema (xem mục 4.34)

### 16.2 Scheduled Jobs — Cập nhật KPI và Variance

| Job | Frequency | Logic |
|---|---|---|
| update_sales_kpi | Daily 1:00 AM | Tính lại AL Sales KPI cho tất cả users có record trong kỳ hiện tại |
| check_price_change_alerts | Daily 9:00 AM | So sánh Item Price vs ConfigSnapshot gần nhất; phát PRICE_CHANGE alert |
| check_low_stock_alerts | Daily 8:00 AM | Kiểm tra Bin.actual_qty vs AL Alert Config threshold |
| generate_daily_digest | Daily 7:00 PM | Gom CAUTION variance trong ngày → gửi email digest cho Admin |
| deprecate_old_bom_versions | Weekly Monday | BOM Version Published > 365 ngày → đánh dấu needs_review=1 |

### 16.2 Scheduled Jobs — Cập nhật KPI và Variance

| Job | Frequency | Logic |
|---|---|---|
| update_sales_kpi | Daily 1:00 AM | Tính lại AL Sales KPI cho tất cả users có record trong kỳ hiện tại |
| check_price_change_alerts | Daily 9:00 AM | So sánh Item Price vs ConfigSnapshot gần nhất; phát PRICE_CHANGE alert |
| check_low_stock_alerts | Daily 8:00 AM | Kiểm tra Bin.actual_qty vs AL Alert Config threshold |
| generate_daily_digest | Daily 7:00 PM | Gom CAUTION variance trong ngày → gửi email digest cho Admin |
| deprecate_old_bom_versions | Weekly Monday | BOM Version Published > 365 ngày → đánh dấu needs_review=1 |

### 16.3 KPI Calculator — Logic đầy đủ

```python
# aluglass/modules/analytics/kpi_calculator.py

def update_all_kpi(period_type='MONTHLY'):
    """Scheduled job: cập nhật KPI cho tất cả sales user trong kỳ hiện tại."""
    period_label = _get_period_label(period_type)
    date_from, date_to = _get_period_dates(period_type)

    users = frappe.get_all('User',
        filters={'enabled': 1},
        fields=['name']
    )
    for user in users:
        _update_user_kpi(user.name, period_type, period_label, date_from, date_to)

def _update_user_kpi(user, period_type, period_label, date_from, date_to):
    # Tìm hoặc tạo KPI record
    kpi_name = frappe.db.exists('AL Sales KPI', {
        'sales_user': user,
        'kpi_period': period_type,
        'period_label': period_label
    })
    if not kpi_name:
        kpi = frappe.new_doc('AL Sales KPI')
        kpi.sales_user = user
        kpi.kpi_period = period_type
        kpi.period_label = period_label
        kpi.insert(ignore_permissions=True)
        kpi_name = kpi.name

    kpi = frappe.get_doc('AL Sales KPI', kpi_name)

    # Quotation thực tế
    quotations = frappe.get_all('Quotation', filters={
        'owner': user,
        'docstatus': 1,
        'transaction_date': ['between', [date_from, date_to]]
    }, fields=['name', 'grand_total'])

    kpi.actual_quotations = len(quotations)

    # Doanh số từ SO (chỉ SO đã Submitted, liên kết từ Quotation của user)
    q_names = [q.name for q in quotations]
    so_items = frappe.get_all('Sales Order Item', filters={
        'prevdoc_docname': ['in', q_names]
    }, fields=['parent', 'prevdoc_docname', 'amount'])

    unique_converted = set(i.prevdoc_docname for i in so_items)
    kpi.conversion_rate_actual = (
        len(unique_converted) / len(quotations) * 100 if quotations else 0
    )

    so_parents = set(i.parent for i in so_items)
    so_totals = frappe.get_all('Sales Order', filters={
        'name': ['in', list(so_parents)],
        'docstatus': 1
    }, fields=['grand_total'])
    kpi.actual_amount = sum(s.grand_total for s in so_totals)

    # Margin thực tế
    gia_ban_sum = 0
    gia_thanh_sum = 0
    for q in quotations:
        items = frappe.get_all('Quotation Item', filters={'parent': q.name},
                               fields=['al_gia_ban', 'al_gia_thanh'])
        gia_ban_sum += sum(i.al_gia_ban or 0 for i in items)
        gia_thanh_sum += sum(i.al_gia_thanh or 0 for i in items)

    kpi.avg_margin_actual_pct = (
        (gia_ban_sum - gia_thanh_sum) / gia_ban_sum * 100
        if gia_ban_sum else 0
    )

    # Discount trung bình
    disc_vals = frappe.get_all('Quotation Item', filters={
        'parent': ['in', q_names],
        'al_discount_pct': ['>', 0]
    }, fields=['al_discount_pct'])
    kpi.avg_discount_pct = (
        sum(d.al_discount_pct for d in disc_vals) / len(disc_vals)
        if disc_vals else 0
    )

    kpi.last_calculated_on = frappe.utils.now()
    kpi.save(ignore_permissions=True)
```

### 16.4 Conversion Rate Tracking

```python
# Công thức tính conversion_rate_actual:
quotations = frappe.get_all('Quotation', filters={'owner': user, 'docstatus': 1, ...})
quotation_names = [q.name for q in quotations]
so_linked = frappe.get_all('Sales Order Item',
                           filters={'prevdoc_docname': ['in', quotation_names]})
unique_converted = len(set(i.prevdoc_docname for i in so_linked))
conversion_rate = unique_converted / len(quotations) * 100
```

---

## XVII. PHASE 3 — AL GLASS INVENTORY BRIDGE

Hai DocType này được thiết kế schema ở v17 nhưng chỉ implement khi bắt đầu Phase 3.

### 17.1 AL Glass Cut Order

| fieldname | fieldtype | Mô tả |
|---|---|---|
| name | Data | Auto-generated: GCO-YYYY-NNNNN |
| sales_order | Link → Sales Order | SO liên kết |
| status | Select | Pending / In Cutting / Cut Done / Installed |
| al_glass_cut_lines | Table → AL Glass Cut Line | |

### 17.2 AL Glass Cut Line (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| glass_master | Link → AL Glass Master | |
| width_mm | Float | Chiều rộng thực tế cần cắt (từ ConfigSnapshot) |
| height_mm | Float | Chiều cao thực tế cần cắt |
| qty | Float | Số lượng tấm |
| area_m2 | Float | Diện tích m² |
| item_variant | Link → Item | Item Variant tồn kho sau cắt |
| batch_no | Link → Batch | |
| stock_entry | Link → Stock Entry | Stock Entry xuất kho kính |

> **Lưu ý Phase 3:**
> - AL Glass Cut Order được tạo từ Sales Order sau khi Submit
> - Chiều rộng/cao lấy từ ConfigSnapshot — không tính lại
> - Phase 3 mới bổ sung Item Variant tồn kho theo màu nhôm (QĐ-6 v15)

---

## XVIII. CONFIGSNAPSHOT & AUDIT TRAIL (v17 BỔ SUNG)

### 18.1 EnterpriseSnapshot v17 — Bổ sung trường

ConfigSnapshot giữ nguyên từ v16. v17 bổ sung thêm vào `enterprise_snapshot_json`:

| Trường mới | Kiểu | Mô tả |
|---|---|---|
| bom_version_id | str | Tên AL BOM Version áp dụng |
| bom_version_hash | str | snapshot_hash của BOM Version |
| discount_applied | dict | `{'rule': str, 'pct': float, 'gia_thuong_mai': float}` |
| discount_approval_ref | str | Tham chiếu approval nếu có |
| calculation_timestamp | str | ISO datetime lúc tính giá |

### 18.2 verify() mở rộng v17

```python
def verify(config_snapshot_name) -> VerifyResult:
    snap = frappe.get_doc('ConfigSnapshot', config_snapshot_name)
    data = json.loads(snap.enterprise_snapshot_json)

    # v16: verify profile_set_hash
    profile_ok = verify_profile_set(data)

    # v17 mới: verify BOM Version snapshot_hash
    bom_ver_id = data.get('bom_version_id')
    bom_ver_ok = True
    if bom_ver_id:
        current_hash = frappe.db.get_value('AL BOM Version', bom_ver_id, 'snapshot_hash')
        bom_ver_ok = (current_hash == data.get('bom_version_hash'))

    return VerifyResult(profile_ok=profile_ok, bom_version_ok=bom_ver_ok,
                        drifted=not (profile_ok and bom_ver_ok))
```

---

## XIX. LUỒNG UI/DIALOG ĐẦY ĐỦ

### 19.0 BOM Dialog — Cấu trúc hiển thị (lõi v16)

```
[Kích thước]
  Chiều rộng (mm)     ← al_W_mm
  Chiều cao (mm)      ← al_H_mm
  Số lượng (bộ)       ← qty

[Thông số kỹ thuật]   ← từ AL Variable Set (sort_order)
  Số cánh / Độ dày nhôm / Hướng mở / Có ngưỡng / Có ô thông gió / ...
  (Mỗi biến hiển thị theo depends_on trong AL Variable Set Detail)

[Loại kính]           ← sinh từ các dòng line_type=KINH trong al_lines
  Với mỗi dòng KINH:
    Tên dòng (line_name): "Kính cánh" / "Kính ô thông gió" ...
    Link chọn glass_master (mặc định = default_glass_master)
    Nếu panel_glass_override_allowed=1: Grid N ô chọn kính riêng từng panel

[Màu nhôm]            ← al_mau_nhom

[Phụ kiện]            ← từ AL PK Set + dòng line_type=PK trong al_lines
  Hiển thị từng dòng, cho phép substitute nếu allow_substitute=1

[Cost Template]       ← al_cost_template_override (default = BOM.default_cost_template)
```

**API endpoints lõi (v16 không đổi):**

| method | Mô tả |
|---|---|
| `aluglass.engine.orchestrator.get_bom_dialog_config` | Config Dialog: KINH lines, PK lines, Variable Set |
| `aluglass.engine.orchestrator.calculate_quotation_item` | Tính giá, ghi fields, trả kết quả |
| `aluglass.engine.orchestrator.get_explain_tree` | explain() cho formula cụ thể |



### 19.1 BOM Dialog v17 — Thành phần mới

| Thành phần | Hiển thị khi | Chức năng |
|---|---|---|
| BOM Version Badge | Luôn hiển thị | 'Phiên bản BOM: v3 (published 15/06/2025)' + link xem diff |
| Discount Section | BOM có Discount Rule applicable | Hiển thị discount + % + GIA_BAN_THUONG_MAI. Nút 'Xem chi tiết rule' |
| Approval Status | al_approval_status = PENDING | Badge 'Chờ duyệt' màu cam. Disable nút Submit Quotation |
| Cost Variance Indicator | Đã có Purchase Invoice liên quan | Badge 'Variance: +3.2%' màu tương ứng status |
| Material Plan Link | Quotation Item thuộc 1 Material Plan | Link 'Thuộc kế hoạch vật tư: MRP-2025-001' |

### 19.2 API Endpoints mới v17

| method | Mô tả |
|---|---|
| aluglass.modules.version.get_bom_version_info | Info BOM Version hiện tại + link diff |
| aluglass.modules.version.compare_versions | So sánh 2 version → DiffResult JSON |
| aluglass.modules.discount.get_applicable_discounts | Discount rule match cho Quotation Item |
| aluglass.modules.discount.apply_manual_discount | Sales nhập discount MANUAL |
| aluglass.modules.approval.approve_discount | Admin duyệt discount |
| aluglass.modules.approval.reject_discount | Admin từ chối discount + note |
| aluglass.modules.mrp.create_material_plan | Tạo Material Plan từ QT/SO list |
| aluglass.modules.mrp.get_plan_summary | Tổng hợp vật tư cho plan |
| aluglass.modules.analytics.get_sales_kpi | KPI của user trong kỳ |
| aluglass.modules.analytics.get_dashboard_data | Data cho Dashboard widget theo role |

---

## XX. VÍ DỤ TÍNH TOÁN KIỂM CHỨNG v17

### Ví dụ 1–5 (kế thừa v15 — kết quả không đổi)

| # | Mô tả | W×H | Kính | GIA_VAT (đ) | Ghi chú |
|---|---|---|---|---|---|
| 1 | Cửa đi 1 cánh XF55, kính đơn 8mm, màu STD | 1200×2400 | KINH-DON-8 | 7,607,851 | panel_count_formula trống → 1 panel |
| 2 | Cửa đi 2 cánh XF55, kính hộp 24mm, không ngưỡng | 1500×2400 | KINH-HOP-24 | ~19,228,000 | max_glass_thick = 24 → nẹp C3211-20 |
| 3 | Cửa mở hất Alumil, Low-E 24mm, màu DAK | 790×1404 | KINH-LOWE-24 | 5,982,308 | |
| 4 | Vách cố định XF65, 3×2 ô, Low-E 24mm | 3600×3000 | KINH-LOWE-24 | 29,727,323 | QTY-KINH-VACH = (n_do_dung+1)*(n_do_ngang+1)*qty |
| 5 | Cửa 1 cánh XF55, 1 đố đứng, 2 kính (HOP-24+CL-10), màu VG | 1200×2400 | 2 loại | 10,111,649 | max(24,10)=24 → nẹp IGU |

### Ví dụ A — 2 loại kính, nẹp tự động

**Input:** BOM-CUA-DI-XF55-1C, W=2500mm, H=3100mm, co_oc_thong_gio="Yes"
**al_glass_selections:** `{"kinh_canh": "KINH-DON-8", "kinh_oc": "KINH-CL-10"}`

```
glass_thick_kinh_canh = 8.38
glass_thick_kinh_oc   = 10.0
nhom_0060_active = (8.38 <= 10.38) → True  → nẹp C3209 active
max_glass_thick_mm = max(8.38, 10.0) = 10.0
vtp_0120_active = (10.0 <= 10.38) → True  → gioăng mỏng active
```

### Ví dụ B — Kính IGU 24mm, nẹp tự chuyển

**Input:** `al_glass_selections: {"kinh_canh": "KINH-HOP-24"}`

```
glass_thick_kinh_canh = 24.0
nhom_0060_active = False, nhom_0061_active = False, nhom_0062_active = True
→ Nẹp C3211-20 IGU active
vtp_0121_active = (24.0 > 16) → True → gioăng dày active
```

### Ví dụ C — PK Substitution

**PK Set PK-CUA-DI-XF55-1C:**

| item_code mặc định | sl_formula | allow_substitute | substitute_item_group |
|---|---|---|---|
| KHOA-XF55 | 1 * qty | 0 | — |
| BANLE-XF55 | 3 * qty | 1 | Bản lề cửa đi |
| TAY-NAM-XF55 | 1 * qty | 1 | Tay nắm cửa đi |

Sales chọn tay nắm vàng: `al_pk_overrides = {"TAY-NAM-XF55": "TAY-NAM-XF55-VANG"}`

**PkResolver xử lý:**
```
KHOA-XF55:    actual_item = KHOA-XF55    (không có override)
              pk_0000_qty = 1, pk_0000_dg = 350,000 → pk_0000_tt = 350,000

BANLE-XF55:   actual_item = BANLE-XF55   (không có override)
              pk_0001_qty = 3, pk_0001_dg = 120,000 → pk_0001_tt = 360,000

TAY-NAM-XF55: override có → actual_item = TAY-NAM-XF55-VANG
              Validate: allow_substitute=1 ✓
                        TAY-NAM-XF55-VANG thuộc group "Tay nắm cửa đi" ✓
                        is_active=1, al_item_type=PHU_KIEN ✓
              pk_0002_qty = 1, pk_0002_dg = 320,000 → pk_0002_tt = 320,000

VL_PK = 350,000 + 360,000 + 320,000 = 1,030,000
(so với 890,000 nếu dùng mặc định TAY-NAM-XF55)
```

**Trường hợp override không hợp lệ** (ví dụ Sales cố gắng đổi KHOA-XF55):
```
PkResolver bỏ qua override, dùng KHOA-XF55 gốc
warnings = ["Dòng phụ kiện 'KHOA-XF55' không cho phép thay thế (allow_substitute=0); đã dùng item mặc định."]
Phép tính vẫn chạy bình thường, Sales thấy toast cảnh báo nhẹ
```

### Ví dụ D — Panel Expansion: Vách kính 3×2 ô, mỗi ô kính khác nhau

**Input:** BOM-VACH-XF65-COMPLEX, W=3600mm, H=3000mm, n_do_dung=2, n_do_ngang=1, khe_do=50

**Profile Line dòng kính (1 dòng duy nhất):**
```
line_name              = "Ô vách"
ctx_inject_prefix      = "kinh_vach"
panel_count_formula    = "(n_do_dung+1)*(n_do_ngang+1)"   → N = 6
width_formula          = "(W_mm-(n_do_dung+1)*khe_do)/(n_do_dung+1)"   → 1150mm
height_formula         = "(H_mm-(n_do_ngang+1)*khe_do)/(n_do_ngang+1)" → 1450mm
panel_glass_override_allowed = 1
default_glass_master   = KINH-CL-10
cut_fee_pct            = 3
```

**Glass Selector UI hiển thị 6 ô chọn kính.** Sales chọn ô số 4 (giữa hàng dưới) là Low-E:
```json
al_glass_selections = {
  "kinh_vach__0": "KINH-CL-10",
  "kinh_vach__1": "KINH-CL-10",
  "kinh_vach__2": "KINH-CL-10",
  "kinh_vach__3": "KINH-CL-10",
  "kinh_vach__4": "KINH-LOWE-24",
  "kinh_vach__5": "KINH-CL-10"
}
```

**Formula sinh ra (trích):**
```
kinh_vach_0_W = 1150, kinh_vach_0_H = 1450, kinh_vach_0_qty = 1
kinh_vach_0_glass_thick_mm = 10          (KINH-CL-10)
kinh_vach_0_m2 = 1150 * 1450 / 1000000  = 1.6675 m²
kinh_vach_0_dg = 550000
kinh_vach_0_tt = 1.6675 * 550000        = 917,125đ
...
kinh_vach_4_glass_thick_mm = 24          ★ KHÁC — KINH-LOWE-24
kinh_vach_4_dg = 1150000                 ★ KHÁC — giá Low-E
kinh_vach_4_tt = 1.6675 * 1150000       = 1,917,625đ
...
max_glass_thick_mm = max(10,10,10,10,24,10) = 24
```

**Hành vi nghiệp vụ đúng:** dù chỉ 1/6 ô dùng kính dày, toàn bộ vách phải dùng nẹp IGU (C6011-20) — nẹp phải đủ rộng cho ô dày nhất. `max_glass_thick_mm = 24` đảm bảo điều này.

**Gioăng kính (VTP) — admin chỉ viết 1 lần:**
```
qty_formula    = "ALL_KINH_total_perimeter_m * 2"
show_condition = "max_glass_thick_mm > 16"
→ Active: True (24 > 16) → gioăng IGU được chọn đúng
```

### Ví dụ Đ — explain() Truy vết minh bạch

**Tình huống:** Sales nghi ngờ tại sao nẹp kính vách lại là loại IGU đắt hơn.

```python
exp = engine.explain("nhom_0050_tt", inputs)   # C6011-20 Nẹp kính đứng vách
print(exp.to_text())
```

**Kết quả cây giải thích:**
```
nhom_0050_tt = 630,540.0
├── nhom_0050_active = (max_glass_thick_mm > 16) → True
│   └── max_glass_thick_mm = max(kinh_vach_0_glass_thick_mm, ..., kinh_vach_4_glass_thick_mm, ...) → 24
│       └── kinh_vach_4_glass_thick_mm = 24   ← panel số 4 (ô giữa hàng dưới, kính Low-E)
├── nhom_0050_qty = IF(nhom_0050_active, H_m*(n_do_dung+1)*2*qty, 0) → 18.0
│   ├── H_m = H_mm/1000 = 3000/1000 → 3.0
│   ├── n_do_dung = 2 [from inputs]
│   └── qty = 1 [from inputs]
├── nhom_0050_kg = 0.310
└── nhom_0050_dg = don_gia_nhom = 113,000
    └── (LOOKUP TRA-GIA-NHOM: brand=XF-NK, mau_nhom=STD → 113,000)
```

Sales nhìn ngay thấy `kinh_vach_4_glass_thick_mm = 24` là nguyên nhân. Không cần hỏi lập trình viên.

### Ví dụ E — Discount tự động theo volume + cần approval (★ MỚI v17)

| Bước | Chi tiết | Kết quả |
|---|---|---|
| Input | BOM-CUA-DI-XF55-1C, W=2500, H=3100, qty=50 bộ, Customer: Công ty ABC (Project Partners) | — |
| FormulaEngine | GIA_BAN = 8,500,000đ/bộ | GIA_BAN = 8,500,000đ |
| Hook A - DiscountStack | Match: DISC-PROJECT-10 (10%, requires_approval) + DISC-VOLUME-TIER tier qty=50 (5%, stackable) | total_disc = 15% → cap tại 15% |
| Approval trigger | total_disc=15% > approval_threshold=8% → al_approval_status=PENDING | Quotation Item bị khóa |
| Admin duyệt | Admin approve discount 15% | al_approval_status=APPROVED |
| GIA_BAN_THUONG_MAI | 8,500,000 × (1 - 15%) = 7,225,000đ/bộ | Tổng 50 bộ = 361,250,000đ |
| Hook B | al_bom_version = BOM-VER-2025-00003 | Freeze giá theo BOM Version v3 |

### Ví dụ F — BOM Version Diff + Rollback (★ MỚI v17)

| Tình huống | Chi tiết |
|---|---|
| v2 → v3: Kỹ thuật tăng giá nhôm C3318 từ 113,000 → 118,000 đ/kg | BOM Version v3 published. Quotation mới tự dùng v3. |
| Phát hiện sai: giá chưa được Giám đốc duyệt | Admin rollback về v2 |
| BOMVersionManager.rollback('BOM-VER-2025-00002') | Tạo v4 từ snapshot v2. v3 Deprecated. v4 Published. |
| Quotation cũ (trỏ v2) và Quotation mới (trỏ v4) | Đều dùng giá nhôm 113,000 — nhất quán. |
| Quotation đang trỏ v3 | ConfigSnapshot.verify() báo 'drift detected'. Sales được alert. |

### Ví dụ G — Material Plan + Cost Variance (★ MỚI v17)

```
Đầu tháng 7: Admin tổng hợp vật tư cho 5 Quotation đã Submitted
→ MRP tổng hợp: Nhôm C3318: 850kg, Kính KINH-DON-8: 45m²
→ Tồn kho: C3318: 200kg → qty_to_purchase: 650kg (+ 5% safety = 682.5kg)

Cuối tháng: Purchase Invoice nhôm C3318 giá 120,000đ/kg
→ Quoted giá: 113,000đ/kg (từ ConfigSnapshot)
→ Variance: +6.2% → status = CAUTION
→ Impact on margin: 682.5 kg × 7,000đ/kg = 4,777,500đ giảm margin
→ Gửi CAUTION email digest cho Admin vào 7:00 PM
```

---

## XXI. CẤU TRÚC THƯ MỤC APP v17

```
aluglass/
├── hooks.py
├── requirements.txt
├── aluglass/
│   ├── engine/                          # Core engine — KHÔNG SỬA
│   │   ├── variable_resolver.py
│   │   ├── rule_engine.py
│   │   ├── profile_interpreter.py
│   │   ├── pk_resolver.py
│   │   ├── cost_accumulator.py
│   │   ├── snapshot_builder.py
│   │   ├── orchestrator.py              # BomOrchestrator 6 bước + fire_hooks()
│   │   └── module_registry.py           # ★ MỚI v17 — hook event bus
│   ├── modules/                          # ★ MỚI v17 — Module Layer
│   │   ├── __init__.py                   # Register all hooks
│   │   ├── version/
│   │   │   ├── bom_version_manager.py
│   │   │   └── api.py                   # compare_versions, rollback
│   │   ├── discount/
│   │   │   ├── discount_stack.py
│   │   │   └── api.py
│   │   ├── approval/
│   │   │   ├── approval_engine.py
│   │   │   └── api.py
│   │   ├── mrp/
│   │   │   ├── mrp_aggregator.py
│   │   │   └── api.py
│   │   ├── cost_variance/
│   │   │   ├── variance_analyzer.py
│   │   │   └── api.py
│   │   ├── notification/
│   │   │   ├── notification_engine.py
│   │   │   └── alert_rules.py
│   │   └── analytics/
│   │       ├── kpi_calculator.py
│   │       └── api.py
│   ├── doctype/
│   │   ├── al_variable_group/
│   │   ├── al_material_type/
│   │   ├── al_glass_type/
│   │   ├── al_glass_layer_type/
│   │   ├── al_glass_master/
│   │   ├── al_glass_layer_line/
│   │   ├── al_product_type/
│   │   ├── al_variable_library/
│   │   ├── al_variable_set/
│   │   ├── al_variable_set_detail/
│   │   ├── al_variable_binding/
│   │   ├── al_cost_bucket/
│   │   ├── al_calculation_rule/
│   │   ├── al_rule_threshold_row/
│   │   ├── al_rule_lookup_row/
│   │   ├── al_rule_sequence_item/
│   │   ├── al_profile_line/
│   │   ├── al_profile_set/
│   │   ├── al_pk_set/
│   │   ├── al_pk_line/
│   │   ├── al_bom/
│   │   ├── al_cost_template/
│   │   ├── al_cost_template_line/
│   │   ├── config_snapshot/
│   │   ├── al_bom_version/              # ★ MỚI
│   │   ├── al_bom_change_log/           # ★ MỚI
│   │   ├── al_discount_rule/            # ★ MỚI
│   │   ├── al_discount_rule_line/       # ★ MỚI
│   │   ├── al_material_plan/            # ★ MỚI
│   │   ├── al_material_plan_line/       # ★ MỚI
│   │   ├── al_cost_variance/            # ★ MỚI
│   │   ├── al_alert_config/             # ★ MỚI
│   │   ├── al_dashboard_config/         # ★ MỚI
│   │   └── al_sales_kpi/               # ★ MỚI
│   ├── reports/                          # ★ MỚI v17
│   │   ├── al_quotation_summary/
│   │   ├── al_bom_price_analysis/
│   │   ├── al_sales_pipeline/
│   │   ├── al_material_cost_variance/
│   │   ├── al_material_requirements/
│   │   ├── al_bom_version_history/
│   │   ├── al_discount_utilization/
│   │   └── al_glass_consumption/
│   ├── scheduled_tasks.py               # ★ MỚI v17
│   ├── fixtures/
│   │   ├── al_variable_group.json
│   │   ├── al_glass_type.json
│   │   ├── al_glass_master.json
│   │   ├── al_variable_library.json
│   │   ├── al_variable_binding.json
│   │   ├── al_calculation_rule.json
│   │   ├── al_cost_bucket.json
│   │   ├── al_cost_template.json
│   │   ├── al_alert_config.json         # ★ MỚI
│   │   └── al_discount_rule.json        # ★ MỚI (rules mặc định)
│   └── custom_fields/
│       ├── item_custom_fields.json
│       ├── quotation_item_custom_fields.json
│       ├── sales_order_item_custom_fields.json
│       ├── sales_invoice_item_custom_fields.json
│       ├── quotation_item_v17.json      # ★ MỚI fields v17
│       └── al_bom_v17.json             # ★ MỚI fields v17
└── public/
    └── js/
        ├── quotation_item.js            # Cập nhật: thêm discount section, version badge
        ├── bom_dialog.js               # Cập nhật: thêm approval UI
        └── dashboard.js                # ★ MỚI — dashboard widgets
```

---

## XXII. LỘ TRÌNH TRIỂN KHAI v17 (PHASE 1–4)

### Phase 1 — Core Engine (tuần 1–12, kế thừa từ v16)

Hoàn thành đúng tiêu chí Phase 1 v16 — không thay đổi. 24 DocType lõi, BomOrchestrator 6 bước, 8 ví dụ kiểm chứng PASS.

**Tiêu chí hoàn thành Phase 1:**
- 5 ví dụ cũ (v15) + ví dụ A, B, C, D chạy đúng
- Thứ tự khai báo al_lines không ảnh hưởng kết quả tính
- Không có `eval()`/`simpleeval` trong code `aluglass`
- explain() trả cây đúng

### Phase 2 — Module v17 (tuần 13–24)

| Tuần | Module | Deliverable | Tiêu chí hoàn thành |
|---|---|---|---|
| 13–14 | BOM Version Control | AL BOM Version + Change Log + publish/rollback/diff | Diff chính xác; rollback tạo version mới; verify() phát hiện drift |
| 15–16 | Approval Workflow | AL Approval Engine + hook before_submit Quotation | Discount > threshold bị chặn; Admin approve/reject; email notification |
| 17–18 | AL Discount Rule + DiscountStack | Discount Rule DocType + DiscountStack.apply() hook | 5 rule_type hoạt động; stack resolution đúng; cap max_total_discount |
| 19–20 | Reporting Basic | 5 Script Report đầu tiên + Dashboard Config | Report chạy đúng; Dashboard hiển thị đúng widget theo role |
| 21–22 | MRP Lite + Cost Variance | AL Material Plan + Aggregator + AL Cost Variance | Aggregate đúng từ ConfigSnapshot; Variance tính đúng; status phân loại đúng |
| 23–24 | Notification Engine + Sales Analytics | NotificationEngine + AL Alert Config + AL Sales KPI + scheduled tasks | Alert REALTIME hoạt động; KPI tính đúng; scheduled job chạy đúng giờ |

### Phase 3 — Production (tuần 25–36)

| Tuần | Công việc |
|---|---|
| 25–28 | AL Glass Inventory Bridge (Glass Cut Order + Cut Line) + Stock Entry integration |
| 29–32 | Item Variant tồn kho theo màu nhôm (QĐ-6 v15 Phase 3) + ánh xạ item_code + màu → Variant |
| 33–36 | Manufacturing Integration: Work Order từ SO, BOM ERPNext production BOM, costing thực tế |

### Phase 4 — Optimization (tuần 37+)

| Tuần | Công việc |
|---|---|
| 37–40 | Performance: Batch frappe.db.get_all cho MRP; Redis cache Dashboard data; lazy-load ConfigSnapshot |
| 41–44 | Advanced Analytics: ML-based price prediction; supplier performance tracking; win/loss analysis |
| 45+ | API mở rộng: REST API cho mobile app Sales; webhook integration với ERP supplier |

---

## XXIII. RỦI RO & ĐIỂM THEO DÕI v17

| # | Rủi ro | Mức độ | Xử lý |
|---|---|---|---|
| 1 | Slug không unique trong Profile Set | Cao | Validate khi lưu; auto-generate từ sort_order + line_name |
| 2 | ctx_inject_prefix kết thúc bằng số | TB | Validate regex `[0-9]$` khi lưu dòng KINH |
| 3 | glass_thick_{prefix} không inject được | TB | Validate khi lưu: scan show_condition tìm biến glass_thick_* |
| 4 | Rollback BOM Version restore Profile Set sai | Cao | Unit test riêng cho rollback; dry-run mode trước khi apply thật |
| 5 | DiscountStack vòng lặp vô hạn khi rule stackable | TB | Cap max_total_discount; giới hạn số rule trong 1 stack ≤ 10 |
| 6 | MRP Aggregator timeout khi Quotation pool lớn >500 | TB | Xử lý batch 50 Quotation/lần; chạy async background job |
| 7 | Cost Variance tạo trùng khi Purchase Invoice amend | TB | Check unique (quotation_item, purchase_invoice, item_code) trước khi insert |
| 8 | Notification storm khi nhiều alert cùng trigger | Thấp | Rate limit: max 5 email/phút/recipient; group tương tự vào 1 email |
| 9 | BOM Version snapshot quá lớn (>5MB JSON) | Thấp | Compress JSON (gzip); store BLOB nếu cần; warn nếu >1MB |
| 10 | Approval workflow bypass bởi Admin tự approve cho mình | TB | Frappe permission: approver phải khác requester; log audit khi self-approve |
| 11 | Tồn kho theo màu nhôm Phase 3 | Cao khi Phase 3 | Viết ánh xạ riêng; không tái sử dụng TRA-GIA-NHOM cho tồn kho |
| 12 | Migrate v15→v16→v17 đồng thời | Cao khi migrate | Chạy tuần tự: patch v15→v16 trước, verify, rồi patch v16→v17 |

---

## XXIV. PHÂN QUYỀN & VAI TRÒ v17

| Vai trò | DocType được phép | Hành động đặc biệt |
|---|---|---|
| AluGlass Admin | Tất cả — Full access | Approve/Reject discount; Publish BOM Version; Tạo Material Plan; Review Cost Variance; Cấu hình AL Alert Config |
| AluGlass Kỹ Thuật | AL Profile Set, AL Profile Line, AL Calculation Rule, AL Glass Master, AL BOM, AL BOM Version | So sánh BOM Version diff; rollback; khai báo al_lines tự do sort_order |
| AluGlass Sales | Read-only cấu hình. Quotation (tạo/sửa). AL Discount Rule (read-only) | Chọn BOM, nhập kích thước, chọn kính/PK, xem explain(); chọn discount rule; không thể approve discount của mình |
| AluGlass Kế Toán | Read-only Quotation, SO, SI, ConfigSnapshot, AL Cost Variance | Xem báo cáo AL Material Cost Variance; review variance |
| AluGlass Mua Hàng | AL Material Plan (tạo/sửa), Read-only SO, Quotation | Tạo Material Plan; tạo Purchase Order từ Material Plan |
| AluGlass Director | Read-only tất cả; Approve BOM Version nếu requires_approval | Approve BOM Version mới khi Kỹ Thuật không có quyền tự publish |

> **Nguyên tắc phân quyền v17:**
> - Sales KHÔNG được sửa AL Calculation Rule, AL Profile Set, AL Discount Rule
> - Approver PHẢI khác Requester — Frappe validate trước khi approve
> - BOM Version Publish: Kỹ Thuật tự publish nếu `requires_approval_for_new_version=0`; ngược lại phải qua Director
> - Audit log: mọi thay đổi AL BOM Version đều tạo AL BOM Change Log tự động

---

## XXV. TÍCH HỢP LUỒNG ERPNEXT v17

### 25.1 Luồng đầy đủ v17

| Bước | ERPNext DocType | aluglass Module | Ghi chú |
|---|---|---|---|
| Báo giá | Quotation + Quotation Item | BomOrchestrator + DiscountStack + BOMVersionManager | Sales chọn BOM, nhập kích thước, Tính giá. Kết quả lưu al_* + ConfigSnapshot + BOM Version |
| Chuyển đổi QT→SO | Sales Order (Get Items From Quotation) | Hook copy_al_fields (QĐ-7 v15) | Toàn bộ al_* field copy sang SO Item; al_bom_version cũng copy |
| Chuyển đổi SO→SI | Sales Invoice (Get Items From SO) | Hook copy_al_fields | al_* field copy sang SI Item; giá không tính lại |
| Mua vật tư | Purchase Order → Purchase Invoice | Trigger CostVarianceAnalyzer.on_purchase_invoice_submit | Tự tạo AL Cost Variance sau khi PI submit |
| Kế hoạch vật tư | AL Material Plan → Purchase Order | MRPAggregator + Generate PO | Admin tạo Plan từ QT/SO pool → Generate PO → Purchase |
| Sản xuất (Phase 3) | Work Order + Stock Entry | AL Glass Cut Order + Glass Cut Line | Cắt kính theo ConfigSnapshot; xuất kho đúng Variant |
| Báo cáo | Frappe Report | AL Reporting Engine + Scripts | 10 report tự động từ dữ liệu al_* + core ERPNext |

### 25.2 hooks.py đầy đủ v17

```python
# aluglass/hooks.py

app_name = 'aluglass'

doc_events = {
    'Quotation': {
        'before_submit': 'aluglass.modules.approval.check_pending_approvals',
    },
    'Sales Order': {
        'before_insert': 'aluglass.engine.orchestrator.copy_al_fields_to_so',
    },
    'Sales Invoice': {
        'before_insert': 'aluglass.engine.orchestrator.copy_al_fields_to_si',
    },
    'Purchase Invoice': {
        'on_submit': 'aluglass.modules.cost_variance.on_purchase_invoice_submit',
    },
    'AL BOM Version': {
        'after_insert': 'aluglass.modules.version.on_version_created',
        'on_update': 'aluglass.modules.version.on_version_status_changed',
    },
}

scheduler_events = {
    'daily': [
        'aluglass.scheduled_tasks.update_sales_kpi',
        'aluglass.scheduled_tasks.check_price_change_alerts',
        'aluglass.scheduled_tasks.check_low_stock_alerts',
        'aluglass.scheduled_tasks.generate_daily_digest',
    ],
    'weekly': [
        'aluglass.scheduled_tasks.deprecate_old_bom_versions',
    ],
}

# Module hooks registered at import time
from aluglass.modules import register_all_hooks  # noqa
```

### 25.3 scheduled_tasks.py đầy đủ v17

```python
# aluglass/scheduled_tasks.py

import frappe
from aluglass.modules.analytics.kpi_calculator import update_all_kpi
from aluglass.modules.cost_variance.variance_analyzer import check_variance_alerts
from aluglass.modules.notification.alert_rules import (
    check_price_change_alerts_job,
    check_low_stock_alerts_job,
    generate_daily_digest_job,
    deprecate_old_bom_versions_job
)

def update_sales_kpi():
    """Daily 1:00 AM — Cập nhật KPI tất cả Sales user."""
    update_all_kpi('MONTHLY')
    frappe.db.commit()

def check_price_change_alerts():
    """Daily 9:00 AM — So sánh Item Price vs ConfigSnapshot."""
    check_price_change_alerts_job()
    frappe.db.commit()

def check_low_stock_alerts():
    """Daily 8:00 AM — Kiểm tra tồn kho nhôm/kính."""
    check_low_stock_alerts_job()
    frappe.db.commit()

def generate_daily_digest():
    """Daily 7:00 PM — Gom CAUTION variance → email digest Admin."""
    generate_daily_digest_job()
    frappe.db.commit()

def deprecate_old_bom_versions():
    """Weekly Monday — Đánh dấu BOM Version > 365 ngày cần review."""
    deprecate_old_bom_versions_job()
    frappe.db.commit()
```

| Bước | Việc cần làm | DocType | Bỏ qua nếu... |
|---|---|---|---|
| 1 | Xác định loại sản phẩm | AL Product Type | Có sẵn |
| 2 | Tạo/kiểm tra Glass Master cho từng loại kính | AL Glass Master | Có sẵn |
| 3 | Tạo Item kính + Item Price | Item, Item Price | Có sẵn |
| 4 | Tạo Item nhôm + al_kg_per_m | Item | Có sẵn |
| 5 | Tạo Item VTP/PK nếu mới | Item | Có sẵn |
| 6 | Tạo biến mới trong AL Variable Library nếu cần | AL Variable Library | Có sẵn |
| 7 | Tạo AL Variable Set + Detail | AL Variable Set | Có sẵn |
| 8 | Kiểm tra AL Variable Binding | AL Variable Binding | Có sẵn |
| 9 | Tạo AL Calculation Rule cần dùng | AL Calculation Rule | Có sẵn |
| 10a | Tạo AL Profile Set → khai báo al_lines: Nhôm (sort 10–70) với show_condition dùng glass_thick_{prefix} | AL Profile Set, AL Profile Line | — bắt buộc |
| 10b | Kính (sort 80–100): ctx_inject_prefix unique per loại kính | AL Profile Line | — bắt buộc |
| 10c | PK inline (sort 100+) nếu có | AL Profile Line | Sản phẩm không có PK inline |
| 10d | VTP (sort 110–200): qty_formula dùng `{prefix}_total_perimeter_m` | AL Profile Line | — bắt buộc |
| 11 | Kiểm tra show_condition: biến glass_thick_{prefix} đúng tên prefix dòng kính | Validate trong form | — luôn thực hiện |
| 12 | Tạo AL PK Set nếu phụ kiện phức tạp | AL PK Set | PK đơn giản dùng inline |
| 13 | Chọn AL Cost Template | AL Cost Template | Dùng CT-01-STANDARD |
| 14 | Tạo AL BOM — liên kết tất cả | AL BOM | — bắt buộc |
| **15 ★** | **Publish BOM Version đầu tiên (v1)** | AL BOM Version | **★ MỚI v17 — bắt buộc** |
| **16 ★** | **Cấu hình AL Discount Rule nếu BOM có ưu đãi đặc thù** | AL Discount Rule | Nếu dùng rule chung |
| **17 ★** | **Cấu hình AL Alert Config cho giá kính BOM này nếu giá biến động cao** | AL Alert Config | Dùng cấu hình chung |
| 18 | Tạo Quotation test, chọn BOM, nhập kích thước | Quotation | — luôn thực hiện |
| 19 | Đổi kính sang loại dày → nẹp và gioăng tự chuyển đúng | Test | — bắt buộc |
| 20 | Đối chiếu với Excel ±0.5%; dùng explain() truy ngược nếu sai | EnrichedExplain | — luôn thực hiện |
| **21 ★** | **Kiểm tra BOM Version badge trong Dialog hiển thị đúng v1** | BOM Dialog UI | **★ MỚI v17** |

---

## XXVII. SƠ ĐỒ ERD & SEQUENCE v17

### 27.1 ERD mở rộng v17

```
AL_BOM ──── AL_BOM_VERSION (1:N) ──── AL_BOM_CHANGE_LOG (1:N per version)
  │               │
  │           snapshot: profile_set_snapshot / variable_set_snapshot / snapshot_hash
  │
  └── AL_PROFILE_SET ──── AL_PROFILE_LINE (al_lines: NHOM/KINH/VTP/PK)

QUOTATION_ITEM
  ├── al_bom → AL_BOM
  ├── al_bom_version → AL_BOM_VERSION      (★ MỚI v17)
  ├── al_config_snapshot → CONFIG_SNAPSHOT
  ├── al_discount_rule → AL_DISCOUNT_RULE  (★ MỚI v17)
  ├── al_discount_pct, al_gia_thuong_mai   (★ MỚI v17)
  └── al_approval_status / al_approved_by  (★ MỚI v17)

AL_DISCOUNT_RULE ──── AL_DISCOUNT_RULE_LINE (1:N tier)
  └── applies_to_customer / applies_to_customer_group / applies_to_bom

AL_MATERIAL_PLAN ──── AL_MATERIAL_PLAN_LINE (1:N)
  └── quotation_list, so_list → [Quotation / Sales_Order]
                               → reads ConfigSnapshot → aggregate items

AL_COST_VARIANCE
  ├── quotation_item → QUOTATION_ITEM
  ├── purchase_invoice → PURCHASE_INVOICE
  └── config_snapshot → CONFIG_SNAPSHOT

AL_SALES_KPI
  └── sales_user → USER
```

### 27.2 Sequence — Tính giá v17 đầy đủ (6 bước + 4 hooks)

```
Sales ──► BOM Dialog ──► API calculate_quotation_item
                              │
                         BomOrchestrator.run()
                              │
    ┌──────────┬──────────────┼──────────────┬────────────┐
    │          │              │              │            │
  Bước 1    Bước 2         Bước 3        Bước 4      Bước 5
  Var       pass1_scan     pass2_build   PkResolver  CostAccum
  Resolver  var_registry   all_formulas  warnings    template
  +inject   panel_counts   (DAG độc lập)             formulas
  glass_thick
    └──────────┴──────────────┴──────────────┴────────────┘
                              │
                           Bước 6
                    FormulaEngine.calculate()  ← 1 LẦN DUY NHẤT
                    + SnapshotBuilder.persist()
                              │
              ┌───────────────┴───────────────┐
              │                               │
           Hook A                          Hook B
       DiscountStack.apply()         BOMVersionManager.link_version()
       → al_discount_pct            → al_bom_version
       → al_gia_thuong_mai          → verify snapshot_hash
       → approval check
              │                               │
           Hook C                          Hook D
   CostVarianceAnalyzer.register()   NotificationEngine.check_alerts()
   → al_cost_variance_ref           → PRICE_CHANGE? LOW_STOCK?
                              │
              ← CalculationResult (result + discount + version + warnings)
                              │
                    Ghi Quotation Item fields
                    Hiển thị Dialog: giá + badge version + discount section
```

### 27.3 Sơ đồ DAG ví dụ — Cửa đi 1 cánh, 2 loại kính

```
inputs_dict (không phải formula):
  W_mm, H_mm, qty, n_canh, do_day, huong_mo, co_nguong
  W_m, H_m, don_gia_nhom
  glass_thick_kinh_canh = 8.38    ← inject từ AL Glass Master
  glass_thick_kinh_oc   = 10.0    ← inject từ AL Glass Master

DAG (FormulaEngine tự xây):

  glass_thick_kinh_canh (INPUT) ──┬──► nhom_0060_active ──► nhom_0060_qty ──► nhom_0060_tt
                                  ├──► nhom_0061_active ──► nhom_0061_qty ──► nhom_0061_tt
                                  └──► nhom_0062_active ──► nhom_0062_qty ──► nhom_0062_tt

  W_mm (INPUT) ──► kinh_canh_W ──► kinh_canh_m2 ──► kinh_canh_tt ──► VL_KINH
                └► kinh_oc_W   ──► kinh_oc_m2   ──► kinh_oc_tt   ──►/

  kinh_canh_glass_thick_mm ──┐
  kinh_oc_glass_thick_mm   ──┴──► max_glass_thick_mm ──► vtp_0120_active ──► vtp_0120_qty
                                                       ──► vtp_0121_active ──► vtp_0121_qty

  VL_NHOM + VL_KINH + VL_VTP + VL_PK ──► TONG_VL ──► GIA_THANH ──► GIA_BAN
                                                                          │
                                                                       Hook A
                                                               DiscountStack.apply()
                                                               → GIA_BAN_THUONG_MAI
```

---

## XXVIII. PHỤ LỤC: MIGRATION v16 → v17

### 28.1 Checklist migration

| Bước | Công việc | Ghi chú |
|---|---|---|
| 1 | Backup toàn bộ database | Bắt buộc — không bỏ qua |
| 2 | Verify v16 đang chạy đúng: 8 ví dụ kiểm chứng v16 PASS 100% | Không migrate nếu v16 chưa stable |
| 3 | Chạy patch tạo 10 DocType mới | `aluglass/patches/v17_0/create_new_doctypes.py` |
| 4 | Chạy patch thêm Custom Fields mới vào Quotation Item và AL BOM | `aluglass/patches/v17_0/add_custom_fields_v17.py` |
| 5 | Chạy patch tạo AL BOM Version v1 cho tất cả BOM hiện có | `aluglass/patches/v17_0/create_initial_bom_versions.py` |
| 6 | Chạy patch import fixtures AL Alert Config mặc định | `bench execute aluglass.patches.v17_0.import_fixtures` |
| 7 | Register module hooks (restart Frappe worker) | `bench restart` |
| 8 | Test: Tạo Quotation test, verify BOM Version badge hiển thị, verify hooks hoạt động | — luôn thực hiện |
| 9 | Test: Tạo Discount Rule test, verify DiscountStack.apply() hoạt động | — luôn thực hiện |
| 10 | Verify: 8 ví dụ kiểm chứng v16 vẫn PASS sau migration v17 | Non-breaking check |

### 28.2 Script migration chính — create_initial_bom_versions.py

```python
# aluglass/patches/v17_0/create_initial_bom_versions.py
import frappe, json, hashlib

def execute():
    from aluglass.modules.version.bom_version_manager import BOMVersionManager
    mgr = BOMVersionManager()

    for bom in frappe.get_all('AL BOM', fields=['name']):
        bom_doc = frappe.get_doc('AL BOM', bom.name)
        # Tạo version v1 Published cho tất cả BOM hiện có
        ver = mgr.publish(
            bom_doc,
            change_summary='Initial version — migrated from v16',
        )
        # Force Published (bỏ qua approval workflow cho migration)
        ver.db_set('status', 'Published')
        bom_doc.db_set('current_version', ver.name)
        print(f'BOM {bom.name}: created version {ver.name}')

    frappe.db.commit()
    print('Migration v16→v17: BOM Versions created')
```

### 28.3 Phụ lục: Migration v15 → v16 (vẫn có hiệu lực)

```python
# aluglass/patches/v16_0/merge_profile_lines.py
import frappe

def execute():
    for ps in frappe.get_all("AL Profile Set", fields=["name"]):
        doc = frappe.get_doc("AL Profile Set", ps.name)
        new_lines = []
        sort = 10

        # Nhôm → sort 10-70
        for line in (doc.al_nhom_lines or []):
            new_lines.append({
                "sort_order": sort, "line_type": "NHOM",
                "line_name": line.line_name, "slug": f"nhom_{sort:04d}",
                "show_condition": line.show_condition, "item_code": line.item_code,
                "quantity_rule": line.quantity_rule, "qty_formula": line.qty_formula,
                "price_type": line.price_type, "price_rule": line.price_rule,
                "fixed_price": line.fixed_price, "cost_bucket": line.cost_bucket,
                "is_active": line.is_active,
            })
            sort += 1

        sort = 80
        for line in (doc.al_kinh_lines or []):
            new_lines.append({
                "sort_order": sort, "line_type": "KINH",
                "line_name": line.line_name, "slug": f"kinh_{sort:04d}",
                "ctx_inject_prefix": line.ctx_inject_prefix,
                "default_glass_master": line.default_glass_master,
                "width_rule": line.width_rule, "height_rule": line.height_rule,
                "width_formula": line.width_formula, "height_formula": line.height_formula,
                "panel_count_formula": line.panel_count_formula,
                "panel_glass_override_allowed": line.panel_glass_override_allowed,
                "qty_per_panel_formula": line.qty_per_panel_formula,
                "price_type": line.price_type, "price_list": line.price_list,
                "cut_fee_pct": line.cut_fee_pct, "is_active": line.is_active,
                "cost_bucket": "VL_KINH",
            })
            sort += 1

        sort = 110
        for line in (doc.al_vtp_lines or []):
            new_lines.append({
                "sort_order": sort, "line_type": "VTP",
                "line_name": line.line_name, "slug": f"vtp_{sort:04d}",
                "show_condition": line.show_condition, "item_code": line.item_code,
                "quantity_rule": line.quantity_rule, "qty_formula": line.qty_formula,
                "price_type": line.price_type, "price_list": line.price_list,
                "cost_bucket": line.cost_bucket, "is_active": line.is_active,
            })
            sort += 1

        doc.set("al_nhom_lines", [])
        doc.set("al_kinh_lines", [])
        doc.set("al_vtp_lines", [])
        doc.set("al_lines", new_lines)
        doc.save(ignore_permissions=True)

    frappe.db.commit()
    print("Migration v15→v16 complete")
```

### 28.4 Backfill al_bom_version cho Quotation cũ (tùy chọn)

```python
# Tùy chọn: gán al_bom_version = v1 của BOM tương ứng cho Quotation cũ
# Không bắt buộc vì Quotation cũ đã có ConfigSnapshot đủ audit trail

def backfill_quotation_bom_versions():
    items = frappe.get_all('Quotation Item',
                           filters={'al_bom': ['!=', '']},
                           fields=['name', 'al_bom'])
    for item in items:
        v1 = frappe.db.get_value('AL BOM Version',
                                  {'bom': item.al_bom, 'version_number': 1}, 'name')
        if v1:
            frappe.db.set_value('Quotation Item', item.name, 'al_bom_version', v1)
    frappe.db.commit()
```

---

*AlumGlass ERP v17.0 — Đặc tả thiết kế chuẩn triển khai*
*Kế thừa v11.0 → v13.0 → v14.0 → v15.0 → v16.0 → v17.0*
*App: `aluglass` · Phụ thuộc: `formula_builder` (formula_utils v29.1+)*
*"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi."*
