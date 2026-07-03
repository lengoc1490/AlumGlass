# AlumGlass ERP v21.0 — Đặc Tả Thiết Kế Tổng Hợp & Mở Rộng (Phiên Bản Đầy Đủ)

> **App:** `aluglass` (Frappe custom app trên ERPNext core) + phụ thuộc `formula_builder`
> **Phiên bản:** v21.0 — Hợp nhất & Nâng cấp từ v17/v18/v19/v20
> **Tổng DocType:** 63 | **Tổng field:** ~650 | **Kiến trúc:** 8 tầng + AI Layer xuyên suốt
> **Phạm vi:** Lead → Báo giá → Chốt đơn → Mua vật tư → Sản xuất (cắt) → Thi công → Thanh quyết toán → Kế toán lãi lỗ → AI xuyên suốt

*"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi. Tồn kho theo thực tế vật lý (Batch). Minh bạch từ báo giá tới quyết toán. AI luôn đề xuất, không quyết định."*

---

## 1. 25 Nguyên tắc thiết kế hợp nhất
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

**Bổ sung v18-v21:**
| # | Nguyên tắc | Nguồn | Hệ quả thực tế |
|---|---|---|---|
| 16 | DynamicItemResolver dùng FormulaEngine.evaluate_single() | v18 | Không tự xây eval sandbox riêng |
| 17 | Formula Variable Binding (FB) thay AL Variable Binding | v18 | 12 source types, resolve theo DAG topology |
| 18 | AL Calculation Rule: giữ THRESHOLD/LOOKUP, CONSTANT/FORMULA có thể migrate | v18 | Không bắt buộc migrate, không xóa rule_type cũ |
| 19 | Cost Template + Formula Set là tùy chọn, có fallback | v18 | Không bắt buộc migrate toàn bộ cùng lúc |
| 20 | AL Dynamic Item Rule = immutable versioned (giống BOM Version) | v19 | Sửa Rule không ảnh hưởng tới Quotation đang mở |
| 21 | AI luôn là đề xuất, không tự ghi vào snapshot/version nào | v19 | Mọi output qua AL AI Suggestion Log rồi Approval |
| 22 | Màu (nhôm/phụ kiện) là thuộc tính GIAO DỊCH (Batch + Project) | v20 | Không tạo Item Variant theo màu |
| 23 | Mọi dữ liệu vận hành phải có nhãn (structured) cho AI học | v20 | Feedback loop bắt buộc cho AL AI Suggestion Log |
| 24 | Sales Override phải được kiểm soát: allow_sales_override + override_item_group | v21 | Chặn override sai nhóm, sai loại |
| 25 | AI là trợ lý, không thay thế con người — mọi đề xuất cần xác nhận | v21 | Áp dụng cho mọi use case AI |

## 2. Schema đầy đủ 34 DocType lõi (Tầng 1 + Tầng 2)
Kế thừa từ thiết kế v17 mục IV. Đây là schema đầy đủ từng field của tất cả DocType nền tảng.

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


---

## 2. Quyết định kiến trúc mới (QĐ-21 đến QĐ-25)

### QĐ-21: ConfigSnapshot Compressed (Nén gzip)
**Vấn đề:** enterprise_snapshot_json (Long Text) đạt 1-5MB/BOM. Với 10.000 Quotation, ~10-50GB.
**Giải pháp:** Thêm compressed_snapshot (Long Text) — JSON nén gzip base64, giảm 70-80% dung lượng.
**Cách hoạt động:** SnapshotBuilder.persist() lưu cả 2 field (enterprise_snapshot_json cũ + compressed_snapshot mới). get_snapshot_data() ưu tiên đọc compressed; fallback về cũ nếu không có.

### QĐ-22: Sales Override Kiểm Soát
**Vấn đề:** v18 cho Sales override item nhưng thiếu kiểm soát — dễ override sai loại (NHOM → PHU_KIEN).
**Giải pháp:** Bổ sung 2 field trên AL Profile Line và AL PK Line:
- allow_sales_override (Check, default 1 cho NHOM/VTP, 0 cho PK)
- override_item_group (Link → Item Group)
**Thứ tự ưu tiên resolve item v21:** Sales Override (nếu allow_sales_override=1 và override_item_group khớp) → Dynamic Rule/Formula result → item_fallback → item_code (Fixed mode) → Error (dừng BomOrchestrator).
**Logic kiểm tra:** allow_sales_override=0 → từ chối. override_item_group != rỗng → kiểm tra item thuộc nhóm. Item disabled → từ chối. al_item_type không khớp line_type → từ chối.

### QĐ-23: AI Hooks Framework
**Vấn đề:** Use case AI trong v19/v20 không có cơ chế can thiệp chuẩn hóa — mỗi AI tự implement theo cách riêng.
**Giải pháp:** Module Hook pattern cho AI — 3 hook points:
1. after_calculate (sau FormulaEngine.calculate(), 10s timeout) — Pricing Advisor, Cutting precompute
2. before_quotation_submit (trước Quotation.submit(), 5s timeout) — Config Validator kiểm tra item
3. daily_ai_analysis (scheduled 00:00, 60s timeout) — Project Health Score, Cutting Optimization batch
**Nguyên tắc:** AI Hook KHÔNG chặn luồng chính. Nếu lỗi hoặc timeout → log error, không block user. Mọi output ghi vào AL AI Suggestion Log (nếu là suggestion) hoặc AL AI Interaction Log (nếu là tra cứu). Mỗi module AI tự đăng ký hook — không sửa BomOrchestrator.

### QĐ-24: CostAccumulator v2 với Fallback Logging
**Vấn đề:** Khi Formula Set lỗi (không tìm thấy, lỗi runtime), CostAccumulator fallback về AL Cost Template Line nhưng không cảnh báo → user không biết config sai.
**Giải pháp:** CostAccumulator v2 với logging chi tiết:
- Formula Set không tồn tại → log error → fallback
- Formula Set eval lỗi → log error + stack trace → fallback  
- Fallback >3 lần/ngày cho cùng 1 template → CRITICAL alert → Push Notification cho Admin

### QĐ-25: DynamicItemResolver v2 — Rule Versioning + Sales Override Priority
**Vấn đề:** DynamicItemResolver v18 không dùng rule version (đọc live threshold_rows/lookup_rows), không kiểm soát Sales Override.
**Giải pháp:** DynamicItemResolver v2:
- Rule mode: đọc từ rule.current_version.rule_snapshot_json (immutable) — không đọc live rows
- Sales Override: kiểm tra allow_sales_override + override_item_group
- Formula mode: FormulaEngine.evaluate_single() — giữ nguyên từ v18
- Kết quả trả về dict {item_code, source, rule_version, warning}

## 3. Schema mới v18: Dynamic Item Selection
### 4.0 AL Dynamic Item Rule ★ — DocType Mới Quan Trọng Nhất v18

Đây là DocType cho phép người dùng **map điều kiện → item bằng bảng trực quan**, không cần viết code. Giống như `AL Calculation Rule (LOOKUP/THRESHOLD)` nhưng đầu ra là **Item Code** thay vì giá trị số.

#### AL Dynamic Item Rule (Master)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ | Unique. `NEP-KINH-THEO-DO-DAY`, `TAY-NAM-THEO-BRAND-MAU`, `GIOANG-THEO-LOAI-KINH` |
| rule_name | Data | ✓ | Tên hiển thị: "Nẹp kính theo độ dày kính" |
| rule_type | Select | ✓ | `THRESHOLD` / `LOOKUP` |
| **THRESHOLD fields:** | | | |
| input_variable | Data | | Tên biến trong inputs_dict. VD: `glass_thick_kinh_canh`, `max_glass_thick_mm` |
| threshold_rows | Table → AL Dynamic Item Threshold Row | | Bảng ngưỡng số → item |
| **LOOKUP fields:** | | | |
| lookup_key_1_var | Data | | Tên biến key 1. VD: `brand`, `mau_nhom`, `huong_mo` |
| lookup_key_2_var | Data | | Tên biến key 2 (optional) |
| lookup_rows | Table → AL Dynamic Item Lookup Row | | Bảng tra cứu key-value → item |
| **Chung:** | | | |
| default_item | Link → Item | ✓ | Item fallback nếu không khớp điều kiện nào |
| is_active | Check (default 1) | | Bật/tắt rule |
| description | Small Text | | Mô tả cách dùng rule |

#### AL Dynamic Item Threshold Row (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| from_value | Float | Giá trị từ (0 = không giới hạn dưới) |
| to_value | Float | Giá trị đến (0 = không giới hạn trên) |
| operator | Select | `≤` / `<` / `≥` / `>` / `=` |
| item_code | Link → Item (reqd) | Item được chọn khi điều kiện khớp |
| note | Data | Ghi chú: "Nẹp mỏng cho kính đơn" |

#### AL Dynamic Item Lookup Row (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| key_1 | Data | Giá trị key 1 |
| key_2 | Data | Giá trị key 2 (optional) |
| item_code | Link → Item (reqd) | Item được chọn khi cả 2 key khớp |
| note | Data | Ghi chú |

#### Ví dụ Master Data — AL Dynamic Item Rule

**Rule 1: NEP-KINH-THEO-DO-DAY (THRESHOLD)**

| from_value | to_value | operator | item_code | note |
|---|---|---|---|---|
| 0 | 10.38 | ≤ | C3209-20 | Nẹp mỏng ≤10.38mm |
| 10.39 | 16.0 | ≤ | C3210-20 | Nẹp vừa 11-16mm |
| 16.01 | 24.0 | ≤ | C3211-20 | Nẹp IGU 16-24mm |
| 24.01 | 0 | > | C3211-24 | Nẹp IGU >24mm |
| **input_variable:** glass_thick_kinh_canh | **default_item:** C3209-20 | | | |

**Rule 2: TAY-NAM-THEO-BRAND-MAU (LOOKUP)**

| key_1 (brand) | key_2 (mau_nhom) | item_code |
|---|---|---|
| XF-NK | STD | TAY-NAM-XF55-STD |
| XF-NK | DAK | TAY-NAM-XF55-DAK |
| XF-NK | VG | TAY-NAM-XF55-VG |
| XF-NK | INOX | TAY-NAM-XF55-INOX |
| ALUMIL | STD | TAY-NAM-ALU-STD |
| ALUMIL | INOX | TAY-NAM-ALU-INOX |
| **lookup_key_1_var:** brand | **lookup_key_2_var:** mau_nhom | **default_item:** TAY-NAM-XF55-STD |

**Rule 3: BANLE-THEO-HUONG-MO (LOOKUP)**

| key_1 (huong_mo) | item_code |
|---|---|
| Out | BANLE-XF55-OUT |
| In | BANLE-XF55-IN |
| **lookup_key_1_var:** huong_mo | **lookup_key_2_var:** (trống) | **default_item:** BANLE-XF55-OUT |

**Rule 4: GIOANG-KINH-THEO-LOAI (LOOKUP)**

| key_1 (glass_type) | item_code |
|---|---|
| CUONG_LUC | GIO-EPDM-CL |
| HOP | GIO-EPDM-HOP |
| LOWE | GIO-EPDM-LOWE |
| DON | GIO-EPDM-THUONG |
| **lookup_key_1_var:** (từ glass_type của glass_master) | **lookup_key_2_var:** (trống) | **default_item:** GIO-EPDM-THUONG |

#### Cập nhật AL Profile Line — `item_selection_mode` thành 3 options

Trường `item_selection_mode` đổi từ `Fixed/Dynamic` thành `Fixed/Rule/Formula`:

| fieldname | fieldtype | default | reqd | Mô tả |
|---|---|---|---|---|
| **item_selection_mode** | **Select (Fixed/Rule/Formula)** | **Fixed** | | **★ MỞ RỘNG: thêm Rule** |
| item_code | Link → Item | | khi Fixed | Item cố định (Fixed mode) |
| **item_rule** | **Link → AL Dynamic Item Rule** | | **khi Rule** | **★ MỚI: chọn rule từ dropdown** |
| **item_condition_formula** | **Small Text** | | **khi Formula** | Công thức IF lồng (Formula mode) |
| item_fallback | Link → Item | | khi Rule/Formula | Item dự phòng |

#### Cập nhật AL PK Line — tương tự

| fieldname | fieldtype | default | Mô tả |
|---|---|---|---|
| **item_selection_mode** | **Select (Fixed/Rule/Formula)** | **Fixed** | **★ MỞ RỘNG** |
| item_code | Link → Item | | khi Fixed |
| **item_rule** | **Link → AL Dynamic Item Rule** | | **khi Rule** |
| **item_condition_formula** | **Small Text** | | **khi Formula** |
| item_fallback | Link → Item | | khi Rule/Formula |


### 4.1 AL Profile Line — Schema v18 (đầy đủ)

#### Trường chung

| fieldname | fieldtype | default | reqd | Thay đổi vs v17 |
|---|---|---|---|---|
| sort_order | Int | | ✓ | Không đổi |
| line_type | Select (NHOM/KINH/VTP/PK) | | ✓ | Không đổi |
| line_name | Data | | ✓ | Không đổi |
| slug | Data | | | Không đổi |
| group_tag | Data | | | Không đổi |
| **show_condition** | **Small Text** | | | **★ Code→Small Text** |
| cost_bucket | Link → AL Cost Bucket | | | Không đổi |
| is_active | Check | 1 | | Không đổi |
| **item_selection_mode** | **Select (Fixed/Dynamic)** | **Fixed** | | **★ MỚI v18** |
| **item_condition_formula** | **Small Text** | | | **★ MỚI v18** |
| **item_fallback** | **Link → Item** | | | **★ MỚI v18** |

#### Trường riêng NHOM

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | khi Fixed | Không đổi |
| quantity_rule | Link → AL Calculation Rule | | Không đổi |
| **qty_formula** | **Small Text** | | **★ Code→Small Text** |
| price_type | Select (Rule/Item Price/Fixed) | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |

#### Trường riêng KINH

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| ctx_inject_prefix | Data | ✓ | Không đổi |
| default_glass_master | Link → AL Glass Master | ✓ | Không đổi |
| width_rule | Link → AL Calculation Rule | | Không đổi |
| height_rule | Link → AL Calculation Rule | | Không đổi |
| **width_formula** | **Small Text** | | **★ Code→Small Text** |
| **height_formula** | **Small Text** | | **★ Code→Small Text** |
| **panel_count_formula** | **Small Text** | | **★ Code→Small Text** |
| panel_glass_override_allowed | Check | | Không đổi |
| **qty_per_panel_formula** | **Small Text** | | **★ Code→Small Text** |
| price_type | Select | | Không đổi |
| price_list | Link → Price List | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |
| cut_fee_pct | Float | | Không đổi |

#### Trường riêng VTP

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| quantity_rule | Link → AL Calculation Rule | Không đổi |
| **qty_formula** | **Small Text** | **★ Code→Small Text** |
| price_type | Select | Không đổi |
| price_list | Link → Price List | Không đổi |
| fixed_price | Currency | Không đổi |

#### Trường riêng PK (inline)

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| **sl_formula** | **Small Text** | **★ Code→Small Text** |
| price_list | Link → Price List | Không đổi |
| allow_substitute | Check | Không đổi |
| substitute_item_group | Link → Item Group | Không đổi |


### 4.2 AL PK Line — Schema v18

| fieldname | fieldtype | default | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | | Không đổi |
| **sl_formula** | **Small Text** | | **★ Code→Small Text** |
| price_list | Link → Price List | | Không đổi |
| cost_bucket | Link → AL Cost Bucket | | Không đổi |
| allow_substitute | Check | | Không đổi |
| substitute_item_group | Link → Item Group | | Không đổi |
| **item_selection_mode** | **Select (Fixed/Dynamic)** | **Fixed** | **★ MỚI v18** |
| **item_condition_formula** | **Small Text** | | **★ MỚI v18** |
| **item_fallback** | **Link → Item** | | **★ MỚI v18** |



---

## 4. Custom Fields trên ERPNext Core
























### AL Project Warehouse Map (Master — tùy chọn, mới v20)

Dành cho công ty muốn tách bạch vật lý (không chỉ tách bạch dữ liệu qua Batch) — nhà xưởng có khu vực riêng cho từng công trình lớn:

| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | Dự án |
| warehouse | Link → Warehouse | Warehouse con tự động tạo dạng "NHOM - {project.name}" |
| auto_created | Check | Đánh dấu warehouse được tạo tự động |
| close_on_project_complete | Check | Tự động chuyển tồn kho còn lại về kho tổng khi Project đóng |

**Nguyên tắc:** Đây là lớp tùy chọn (opt-in theo từng Project qua `AL Project Financial Config.use_project_warehouse`), không bắt buộc. Công ty quy mô nhỏ dùng Batch là đủ, không cần thêm Warehouse con.

### Tác động tới MRP Lite (cập nhật v20)

| Trước (sai) | Sau (v20-v21, đúng) |
|---|---|
| MRP Lite tổng hợp theo item_variant (tiết diện + màu) | MRP Lite tổng hợp theo cặp (item_gốc, color_code) |
| Đề xuất mua theo từng biến thể | 2 nhánh: is_standard_stock=1 → cộng dồn tồn kho đệm; is_standard_stock=0 → Material Request gắn project, không gộp chung giữa các dự án |
| PO 1 dòng = 1 Item Variant | PO 1 dòng = Item gốc, color_code + project là field bổ sung → Purchase Receipt tự động tạo Batch |

### Tác động tới Sản xuất/Cắt (không đổi định giá)

- **Định giá bán vẫn dùng LOOKUP TRA-GIA-NHOM theo (brand, màu)** — không đổi, v17 đã làm đúng (QĐ-6). Chỉ sửa tầng tồn kho vật lý, không đụng tầng giá bán.
- Cutting Plan khi xuất kho để cắt: chọn đúng item (tiết diện) + được hệ thống gợi ý batch_no phù hợp (đúng màu yêu cầu, ưu tiên batch đã reserve cho đúng project).

### Migration Item Variant → Batch (chi tiết)
1. Với mỗi Item Variant hiện có (tiết diện × màu): tạo 1 Batch trên Item gốc, gán al_color = màu tương ứng.
2. Chuyển toàn bộ tồn kho hiện tại (Stock Reconciliation) sang Item gốc + Batch mới.
3. Disable Item Variant cũ (disabled=1) — KHÔNG XÓA (giữ lịch sử giao dịch).
4. Cập nhật PO/Material Request đang mở sang Item gốc + field color_code/project.
5. Kiểm tra: không còn Item Variant màu nào active trong hệ thống.

## P0. ★ Sửa lỗi Kiến trúc Tồn kho Batch-màu

### Nguyên tắc #22
Màu (nhôm/phụ kiện) là thuộc tính GIAO DỊCH (Batch + Project), KHÔNG BAO GIỜ là trục biến thể (Attribute) của Item Master.

### AL Color Standard (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| color_code | Data (unique) | RAL9016, VANGO-OC-CHO-01 |
| color_name | Data | Tên hiển thị |
| applies_to | Select | NHOM_PROFILE / PHU_KIEN |
| is_standard_stock | Check | Được phép tồn kho đệm (safety stock) |
| default_safety_stock_qty | Float | Chỉ áp dụng nếu is_standard_stock=1 |
| surcharge_rule | Link → AL Calculation Rule | Rule LOOKUP giá theo màu (TRA-GIA-NHOM) |

### Cơ chế Batch thay cho Item Variant
1. Item Master: 1 Item = 1 tiết diện nhôm. Custom field al_is_color_variable (Check) đánh dấu Item áp dụng Batch-màu.
2. Bật Has Batch No cho Item NHOM_PROFILE (tính năng ERPNext core).
3. Custom field trên Batch: al_color (Link → AL Color Standard), al_source_project (Link → Project), al_is_reserved_for_project (Check).
4. Bật Batch Wise Valuation (tính năng ERPNext core) → giá vốn thực tế theo đúng lô màu.
5. Số lượng Item Master KHÔNG tăng — chỉ Batch tăng (nhẹ, không overhead).

### Tác động MRP Lite
| Trước (sai) | Sau (v20-v21, đúng) |
|---|---|
| MRP tổng hợp theo item_variant (tiết diện + màu) | MRP tổng hợp theo (item_gốc, color_code) |
| Đề xuất mua theo từng biến thể | 2 nhánh: is_standard_stock=1 → cộng dồn tồn kho đệm; is_standard_stock=0 → Material Request gắn project |

### Migration path (Item Variant → Batch)
1. Quét Item có Attribute Màu → danh sách variant cần migrate
2. Với mỗi variant: tạo AL Color Standard (nếu chưa có) → tạo Batch trên Item gốc → Stock Reconciliation → disable variant cũ (disabled=1, KHÔNG XÓA)
3. Cập nhật PO/Material Request đang mở sang Item gốc + color_code

### Lợi ích
- Item Master ổn định (~100-300 Item), không tăng đột biến
- Giá vốn chính xác theo từng lô nhờ Batch Wise Valuation
- Tồn kho đúng bản chất vật lý (Item = tiết diện, Màu = lô)
- Truy vết được theo dự án qua al_source_project

## 5. Schema Module nghiệp vụ (Production, Field Ops, Billing, P&L)

## XXVI. MODULE THI CÔNG (FIELD OPERATIONS)

### 26.1 AL Installation Order (Master) — Vòng đời
Draft → Scheduled → In Progress → (On Hold ↔ In Progress) → Completed → chuyển giao Warranty.

| fieldname | fieldtype |
|---|---|
| sales_order | Link → Sales Order (reqd) |
| project | Link → Project (ERPNext core) |
| installation_team | Link → AL Installation Team |
| planned_start / planned_end | Date |
| al_installation_lines | Table → AL Installation Order Line |
| overall_progress_pct | Percent (read-only, tính từ Progress log) |

### 26.2 AL Installation Order Line (Child)
`sales_order_item` (Link), `hang_muc` (Data), `planned_nc_ld_cost` (Currency — copy từ `AL Product Type.nc_ld_rate × diện tích` tại thời điểm chốt SO, **immutable**), `status` (Pending/Installing/Done/Rework).

### 26.3 AL Installation Progress (Master, append-only)
`installation_order` (Link), `progress_date`, `pct_completed_this_entry`, `cumulative_pct` (computed), `photos` (Table Attach Image), `notes`, `recorded_by`.

### 26.4 AL Installation Cost Actual (Master)
`installation_order`, `cost_type` (Nhân công/Vận chuyển/Thiết bị/Khác), `actual_amount`, `source_doc` (Dynamic Link → Expense Claim/Journal Entry/Purchase Invoice).

### 26.5 AL Warranty Policy / AL Warranty Claim
**Policy:** `policy_code`, `product_type`, `warranty_months`, `coverage_scope`, `exclusions`.
**Claim:** `sales_order`, `installation_order`, `issue_description`, `repair_cost`, `root_cause_category` (dùng cho AI Anomaly Detection §XXIX).

### 26.6 Luồng
| Bước | Actor | Hành động |
|---|---|---|
| 1 | (Hook E, tự động khi SO Submit) | Tạo Installation Order Draft |
| 2 | Quản lý Thi công | Gán `installation_team`, `planned_start/end` → Scheduled |
| 3 | Đội Thi công (mobile) | Bắt đầu → In Progress; ghi `AL Installation Progress` định kỳ (≥1 ảnh nếu ≥50%) |
| 4 | System | Cập nhật `overall_progress_pct`; kiểm tra Milestone Billing (§XXVII) |
| 5 | Quản lý Thi công | Xác nhận 100% → Completed |
| 6 | System | Kích hoạt `AL Warranty Policy` theo `product_type` |
| 7 | (nếu có lỗi) | Tạo `AL Warranty Claim`, ghi `repair_cost` → feed Project Profitability (§XXVIII) |

---

## XXIX. TẦNG AI TOÀN DIỆN

### 29.1 Nguyên tắc quản trị (Nguyên tắc #21)
AI không bao giờ ghi trực tiếp vào bất kỳ DocType immutable nào (ConfigSnapshot, BOM/Rule Version, Project Profitability Snapshot). Mọi output → `AL AI Suggestion Log` → con người xác nhận qua **đúng** Approval Workflow đã có — không xây flow riêng cho AI.

### 29.2 AL AI Suggestion Log (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| suggestion_type | Select | ITEM_RULE_GENERATE / QUOTATION_DRAFT / DISCOUNT_SUGGEST / CUTTING_OPTIMIZATION / PROJECT_RISK_FLAG / PK_SUGGEST / ANOMALY_DETECT / WIN_LOSS_INSIGHT |
| context_reference | Dynamic Link | Quotation/AL BOM/AL Installation Order/AL Project Profitability Snapshot liên quan |
| ai_output_json | Long Text | |
| confidence_score | Float | |
| status | Select | Proposed / Accepted / Modified / Rejected |
| reviewed_by | Link User | |
| feedback_note | Small Text | Dữ liệu huấn luyện lại |

### 29.3 Use case theo ưu tiên (ROI thực tế, không theo độ dễ)

| Ưu tiên | Use case | Module | Input | Output đi qua |
|---|---|---|---|---|
| **P0** | **AI Cutting Optimization** (thuật toán tối ưu, không nhất thiết LLM) | Sản xuất §XXV | ConfigSnapshot + AL Cutting Standard | `AL Aluminum/Glass Cutting Plan` — Sản xuất review & confirm |
| **P0** | **AI Project Health Score** | P&L §XXVIII | Project Profitability Snapshot + Cost/Labor Variance + số lần rework | Cảnh báo Director qua NotificationEngine |
| P1 | AI-assisted BOM/Rule Configuration | Dynamic Item Rule §VIII | Mô tả tự nhiên + available_items | Tạo **Draft version** (chưa Published) — Kỹ thuật viên review rồi Publish |
| P1 | AI Quotation Copilot | Sales | Mô tả yêu cầu khách + BOM library (RAG) | Quotation **Draft** — Sales review trước Submit |
| P1 | AI Win/Loss Analysis | Sales Analytics | Quotation Won/Lost + `al_loss_reason` | Báo cáo, không hành động tự động |
| P2 | AI Anomaly Detection mở rộng | Cost/Labor Variance + Warranty | Toàn bộ variance/warranty data | Flag Dashboard |
| P2 | AI phân tích ảnh nghiệm thu | Field Ops §XXVI | `AL Installation Progress.photos` | Gợi ý lỗi lắp đặt — không tự tạo Warranty Claim |
| P3 | AI Demand Forecasting | MRP Lite §XX | Lịch sử PI + Material Plan | Gợi ý `qty_to_purchase` — Admin vẫn Confirm |
| P3 | AI Config Validator | BOM | Scan Profile Set | Danh sách issue (vd Dynamic mode thiếu `item_fallback`) |
| P3 | AI PK Suggester | PK Set | BOM tương tự | Gợi ý top-5 PK theo tần suất |

### 29.4 Điều kiện tiên quyết
- `Quotation.al_loss_reason` (§5.4) phải có trước khi làm AI Win/Loss.
- ≥3-6 tháng lịch sử Cutting Plan trước khi AI Cutting Optimization đủ tín hiệu học theo đặc thù xưởng thực tế.
- ≥1 năm dữ liệu Installation + P&L trước khi AI Demand Forecasting đáng tin cậy.

---
---

# PHẦN H — VẬN HÀNH

## XXX. CONFIGSNAPSHOT & AUDIT TRAIL — CHUỖI XUYÊN SUỐT

```
ConfigSnapshot (giá bán)
  → chứa: bom_version_id/hash, rule_version_ids{rule_code:version}, discount_applied
     ↓ tham chiếu
AL Aluminum/Glass Cutting Plan (kích thước cắt = biến đổi qua AL Cutting Standard)
     ↓ tham chiếu
AL Installation Order Line (planned_nc_ld_cost chốt cứng tại thời điểm SO)
     ↓ đối chiếu với
AL Installation Cost Actual + AL Cost Variance (vật tư) + AL Labor Cost Variance
     ↓ tổng hợp định kỳ vào
AL Project Profitability Snapshot (immutable)
```

`explain()` (FormulaEngine) trả lời **"tại sao giá bán ra con số này"**. `AL Project Profitability Snapshot.explain_variance()` (§28.5) trả lời **"tại sao dự án lãi/lỗ"** — cùng triết lý cây giải thích, khác tầng vận hành.

**`verify()` mở rộng:** kiểm tra `profile_set_hash` (v16) + `bom_version.snapshot_hash` (v17) + **`rule_version.snapshot_hash` cho từng `rule_code` trong `rule_version_ids` (★v19)** → `drifted = not (profile_ok and bom_ver_ok and all(rule_ver_ok))`.

---

## XXXI. QUY TRÌNH NGHIỆP VỤ ĐẦU-CUỐI

```
[1] LEAD → [2] BÁO GIÁ (BomOrchestrator 9 bước + Hook A-D)
    → ConfigSnapshot + BOM Version + Rule Version đều ghim
    → Discount Stack + Approval nếu cần

[3] CHỐT ĐƠN (SO Submit)
    → copy_al_fields (không đổi)
    → Hook E: tạo Installation Order (Draft) + Milestone Billing Plan
    → Hook F: đăng ký vào Cutting Plan pool

[4] MUA VẬT TƯ: Material Plan → PO → PI → Cost Variance vật tư tự tạo

[5] SẢN XUẤT: Cutting Plan (đọc ConfigSnapshot, tối ưu — có AI hỗ trợ) → Cut Order → Stock Entry

[6] THI CÔNG: Installation Order Scheduled → In Progress
    → Installation Progress (mobile, append-only) → overall_progress_pct
    → Installation Cost Actual song song

[7] THANH TOÁN THEO TIẾN ĐỘ: Milestone Billing Line tự Ready to Bill khi đạt ngưỡng
    → Kế toán xuất Sales Invoice từng đợt (bị chặn nếu vượt tiến độ)

[8] NGHIỆM THU & BẢO HÀNH: Installation Order Completed → Warranty Policy kích hoạt
    → Warranty Claim nếu có lỗi phát sinh

[9] QUYẾT TOÁN & P&L: Project Profitability Snapshot tổng hợp toàn bộ
    → margin_drift_vs_quoted đối chiếu cam kết ban đầu
    → Đóng Project, snapshot cuối lưu vĩnh viễn cho audit
```

---

## XXXII. PHÂN QUYỀN & VAI TRÒ (ĐẦY ĐỦ)

| Vai trò | DocType chính | Hành động đặc biệt |
|---|---|---|
| AluGlass Admin | Toàn quyền | Approve/Reject discount; Publish BOM/Rule Version (nếu không cần Director); Tạo Material Plan; Review Cost Variance |
| AluGlass Kỹ Thuật | Profile Set/Line, Calculation Rule, Glass Master, BOM, BOM Version, **Dynamic Item Rule + Version** | So sánh diff; rollback; publish version (nếu không cần duyệt) |
| AluGlass Sales | Read-only cấu hình; Quotation tạo/sửa; Discount Rule read-only | Chọn BOM, nhập kích thước, chọn kính/PK, xem explain(), chọn discount; **không** approve discount của mình; nhập `al_loss_reason` khi đóng Quotation thua |
| AluGlass Kế Toán | Read-only Quotation/SO/SI/ConfigSnapshot; AL Cost Variance; **Milestone Billing (xuất SI), Project Profitability (read)** ★v19 | Xem/review variance; xuất hóa đơn theo đợt (bị hệ thống kiểm soát) |
| AluGlass Mua Hàng | Material Plan tạo/sửa; Read-only SO/Quotation | Tạo PO từ Material Plan |
| AluGlass Director | Read-only toàn bộ; Approve BOM/**Rule Version** nếu `requires_approval` | **Nhận MARGIN_DRIFT alert; Approve Milestone Billing Plan template** ★v19 |
| **AluGlass Sản Xuất ★v19** | Cutting Standard (read), Aluminum/Glass Cutting Plan (tạo/sửa), Production Order Bridge | Confirm Cutting Plan; không sửa ConfigSnapshot nguồn |
| **AluGlass Đội Thi Công ★v19** (mobile) | Installation Order (read hạng mục được giao), Installation Progress (tạo) | Chỉ ghi thêm (append-only); không sửa/xóa record cũ; không sửa giá/BOM |
| **AluGlass Quản lý Thi công ★v19** | Installation Order đầy đủ, Installation Team, Warranty Claim | Gán đội, duyệt hoàn thành, xử lý bảo hành |

**Nguyên tắc bất biến:** Sales KHÔNG sửa Calculation Rule/Profile Set/Dynamic Item Rule/Discount Rule. Approver PHẢI khác Requester. Mọi thay đổi BOM Version/Rule Version tự động ghi Change Log.

---

## XXXIII. VÍ DỤ KIỂM CHỨNG (BẮT BUỘC PASS TRƯỚC GO-LIVE)

| # | Kịch bản | Kết quả kỳ vọng |
|---|---|---|
| 1-5 | 5 ví dụ cơ bản (đơn cánh, đa cánh, nhiều loại kính, vách cố định, kính hỗn hợp) | Giá tính đúng, không đổi khi đảo `sort_order` |
| A | 2 loại kính, nẹp tự động theo độ dày | `nhom_0060_active`/`0061`/`0062` đúng theo `glass_thick_kinh_canh` |
| B | Kính IGU 24mm, nẹp tự chuyển | Nẹp IGU + gioăng dày active đúng |
| C | PK Substitution hợp lệ/không hợp lệ | Override đúng nhóm được áp; sai nhóm bị bỏ qua + warning |
| D | Panel Expansion vách 3×2 ô, 1 ô kính khác | `max_glass_thick_mm` đúng = giá trị lớn nhất; nẹp chọn theo max |
| Đ | `explain()` truy vết | Cây giải thích hiển thị đúng nguyên nhân sâu nhất |
| E | Discount volume + approval | Stack đúng, cap đúng, approval trigger đúng |
| F | BOM Version diff + rollback | Diff chính xác; rollback tạo version mới, không xóa |
| G | Material Plan + Cost Variance | Aggregate đúng từ ConfigSnapshot; variance phân loại đúng |
| **H ★v19** | Sửa Rule, publish version mới, Quotation cũ đang mở | Quotation cũ **vẫn dùng version cũ**, không đổi giá đột ngột |
| **I ★v19** | Cutting Plan cho 1 SO có 20 thanh cùng profile | Đề xuất cắt giảm phế liệu so với cắt tuần tự thủ công (baseline) |
| **J ★v19** | Installation Progress đạt 70%, Milestone trigger 70% | Milestone Line tự chuyển `Ready to Bill`; xuất SI vượt 70% bị chặn |
| **K ★v19** | Project hoàn thành, có 1 Warranty Claim | Project Profitability Snapshot trừ đúng `warranty_cost_to_date`; `margin_drift_vs_quoted` tính đúng |

---

## XXXIV. LỘ TRÌNH TRIỂN KHAI (PHASE 1–7)

| Phase | Nội dung | Điều kiện hoàn thành |
|---|---|---|
| **1 — Core Engine** | Tầng 1-4: Master Data, Rule/Formula Engine, Orchestration 7 bước gốc | Ví dụ 1-5 + A-D PASS; không `eval()`; `explain()` đúng |
| **2 — Module Commercial** | BOM Version, Approval, Discount, Reporting cơ bản, MRP Lite, Cost Variance, Notification, Sales Analytics | Ví dụ E-G PASS |
| **2.5 — Vá Rule Versioning (P0, bắt buộc trước Phase 3)** | §VIII đầy đủ: AL Dynamic Item Rule Version + luồng publish/approve/diff | Ví dụ H PASS; migration tạo version v1 cho mọi rule hiện có |
| **3 — Sản Xuất** | Cutting Standard, Aluminum/Glass Cutting Plan, Cut Order | Ví dụ I PASS; phế liệu đo được giảm so với baseline |
| **4 — Thi Công + Thanh Quyết Toán** | Installation Team/Order/Progress/Cost, Warranty, Milestone Billing | Ví dụ J PASS; mobile app hoạt động |
| **5 — Kế Toán Lãi Lỗ** | Project Financial Config, Labor Cost Variance, Project Profitability Snapshot | Ví dụ K PASS; đối chiếu khớp ≥3 dự án thí điểm với báo cáo thủ công |
| **6 — AI P0-P1** | Cutting Optimization, Project Health Score, BOM/Rule AI-assist, Quotation Copilot | Mọi suggestion qua `AL AI Suggestion Log` + Approval; không có đường tắt |
| **7 — AI P2-P3 + Tối ưu hiệu năng** | Anomaly Detection mở rộng, ảnh nghiệm thu, Demand Forecasting; cache Redis, nén ConfigSnapshot JSON | Theo nhu cầu thực tế, sau khi đủ dữ liệu lịch sử |

---

## XXXV. RỦI RO & ĐIỂM THEO DÕI (HỢP NHẤT TOÀN BỘ)

| # | Rủi ro | Mức độ | Xử lý |
|---|---|---|---|
| R1 | Slug không unique trong Profile Set | Cao | Validate khi lưu, auto-generate |
| R2 | `ctx_inject_prefix` kết thúc bằng số | TB | Validate regex khi lưu |
| R3 | `glass_thick_{prefix}` không inject được | TB | Validate scan `show_condition` khi lưu |
| R4 | Rollback BOM Version restore sai | Cao | Unit test riêng; dry-run trước khi apply |
| R5 | DiscountStack vòng lặp vô hạn | TB | Cap `max_total_discount_pct`; giới hạn ≤10 rule/stack |
| R6 | MRP Aggregator timeout pool lớn | TB | Batch 50 Quotation/lần; async job |
| R7 | Cost Variance tạo trùng khi PI amend | TB | Check unique trước insert |
| R8 | Notification storm | Thấp | Rate limit 5 email/phút/người; group vào 1 email |
| R9 | ConfigSnapshot JSON quá lớn (>5MB) | Thấp | Nén gzip; BLOB nếu cần; warn >1MB |
| R10 | Approval bypass tự duyệt cho mình | TB | Validate Approver≠Requester; log audit |
| R11 | Formula trả về item không tồn tại/disabled | Med | `item_fallback` bắt buộc; validate tồn tại; log+alert |
| R12 | Circular: formula Dynamic tham chiếu biến slug do DAG tính | High | Regex reject tại form save |
| R13 | Sales override item sai loại | Med | Validate `al_item_type` trong resolver |
| R14 | **Rule sửa ảnh hưởng ngay Quotation đang mở** | **Đã vá — §VIII versioning** | Version + Diff Tool + tùy chọn hồi tố có cảnh báo |
| R15 | Migration FB Binding sai type | Med | Test định lượng ≥100 Quotation thật, không chỉ 8 ví dụ |
| R16 ★v19 | Cutting Optimization đề xuất phương án không khả thi (máy không hỗ trợ) | TB | Luôn qua review Sản xuất trước khi in phiếu; không tự động hoàn toàn |
| R17 ★v19 | Installation Progress ghi sai % (báo cáo vội) | TB | Bắt buộc ảnh nếu ≥50%; Quản lý Thi công review định kỳ |
| R18 ★v19 | Milestone Billing chặn nhầm hóa đơn hợp lệ (tạm ứng đầu) | Cao nếu sai | `trigger_type=MANUAL/DATE` không bị chặn bởi validation tiến độ |
| R19 ★v19 | Project Profitability sai do Overhead Allocation cấu hình nhầm | TB | Snapshot giữ `overhead_allocated` tách riêng, dễ audit/điều chỉnh |
| R20 ★v19 | AI Suggestion Log phình to, không ai review | Thấp | Dashboard riêng; auto-archive sau 30 ngày không phản hồi |
| R21 | Tồn kho theo màu nhôm (Item Variant) | Cao khi Phase 3 | Viết ánh xạ riêng; không tái dùng TRA-GIA-NHOM cho tồn kho |
| R22 | Migrate nhiều version đồng thời (v16→v17→v18→v19) | Cao khi migrate | Chạy tuần tự, verify từng bước trước khi qua bước sau |

---

## XXXVI. CHECKLIST GO-LIVE

- [ ] Toàn bộ ví dụ kiểm chứng §XXXIII (1-5, A-K) PASS 100%
- [ ] Migration Rule Versioning hoàn tất — mọi `AL Dynamic Item Rule` có `current_version` (điều kiện go-live, không bỏ qua)
- [ ] Test migration định lượng VariableResolver v2↔v3 trên ≥100 Quotation thật
- [ ] `AL Cutting Standard` khai báo đầy đủ cho mọi profile nhôm + loại kính đang dùng
- [ ] `AL Milestone Billing Plan` template mặc định đã duyệt với Kế toán trưởng
- [ ] `AL Project Profitability Snapshot` chạy thí điểm ≥3 dự án đã hoàn thành, đối chiếu khớp báo cáo thủ công hiện tại
- [ ] Không có `eval()`/`simpleeval` ở bất kỳ đâu trong code `aluglass`
- [ ] Toàn bộ AI use case Phase 6 có `AL AI Suggestion Log` + đi qua Approval Workflow
- [ ] Phân quyền Đội Thi Công (mobile, append-only) đã test không cho sửa/xóa record cũ
- [ ] Approver ≠ Requester được validate ở cả BOM Version, Rule Version, Discount Approval
- [ ] Backup toàn bộ database trước mọi bước migration; verify bước trước khi qua bước sau (R22)
- [ ] `explain()` hiển thị đúng cho mọi loại con số: giá bán (FormulaEngine) và lãi/lỗ dự án (`explain_variance()`)

---

*AlumGlass ERP — Master Design v19 · Tài liệu triển khai duy nhất, tự thân*
*Kế thừa: v11 → v13 → v14 → v15 → v16 → v17 → v18 → v19*
*"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi. Minh bạch từ báo giá tới quyết toán."*



---

## 6. Master Data mẫu chuẩn (để triển khai)

## 7. AL Dynamic Item Rule — Schema & Versioning
### 4.0 AL Dynamic Item Rule ★ — DocType Mới Quan Trọng Nhất v18

Đây là DocType cho phép người dùng **map điều kiện → item bằng bảng trực quan**, không cần viết code. Giống như `AL Calculation Rule (LOOKUP/THRESHOLD)` nhưng đầu ra là **Item Code** thay vì giá trị số.

#### AL Dynamic Item Rule (Master)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ | Unique. `NEP-KINH-THEO-DO-DAY`, `TAY-NAM-THEO-BRAND-MAU`, `GIOANG-THEO-LOAI-KINH` |
| rule_name | Data | ✓ | Tên hiển thị: "Nẹp kính theo độ dày kính" |
| rule_type | Select | ✓ | `THRESHOLD` / `LOOKUP` |
| **THRESHOLD fields:** | | | |
| input_variable | Data | | Tên biến trong inputs_dict. VD: `glass_thick_kinh_canh`, `max_glass_thick_mm` |
| threshold_rows | Table → AL Dynamic Item Threshold Row | | Bảng ngưỡng số → item |
| **LOOKUP fields:** | | | |
| lookup_key_1_var | Data | | Tên biến key 1. VD: `brand`, `mau_nhom`, `huong_mo` |
| lookup_key_2_var | Data | | Tên biến key 2 (optional) |
| lookup_rows | Table → AL Dynamic Item Lookup Row | | Bảng tra cứu key-value → item |
| **Chung:** | | | |
| default_item | Link → Item | ✓ | Item fallback nếu không khớp điều kiện nào |
| is_active | Check (default 1) | | Bật/tắt rule |
| description | Small Text | | Mô tả cách dùng rule |

#### AL Dynamic Item Threshold Row (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| from_value | Float | Giá trị từ (0 = không giới hạn dưới) |
| to_value | Float | Giá trị đến (0 = không giới hạn trên) |
| operator | Select | `≤` / `<` / `≥` / `>` / `=` |
| item_code | Link → Item (reqd) | Item được chọn khi điều kiện khớp |
| note | Data | Ghi chú: "Nẹp mỏng cho kính đơn" |

#### AL Dynamic Item Lookup Row (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| key_1 | Data | Giá trị key 1 |
| key_2 | Data | Giá trị key 2 (optional) |
| item_code | Link → Item (reqd) | Item được chọn khi cả 2 key khớp |
| note | Data | Ghi chú |

#### Ví dụ Master Data — AL Dynamic Item Rule

**Rule 1: NEP-KINH-THEO-DO-DAY (THRESHOLD)**

| from_value | to_value | operator | item_code | note |
|---|---|---|---|---|
| 0 | 10.38 | ≤ | C3209-20 | Nẹp mỏng ≤10.38mm |
| 10.39 | 16.0 | ≤ | C3210-20 | Nẹp vừa 11-16mm |
| 16.01 | 24.0 | ≤ | C3211-20 | Nẹp IGU 16-24mm |
| 24.01 | 0 | > | C3211-24 | Nẹp IGU >24mm |
| **input_variable:** glass_thick_kinh_canh | **default_item:** C3209-20 | | | |

**Rule 2: TAY-NAM-THEO-BRAND-MAU (LOOKUP)**

| key_1 (brand) | key_2 (mau_nhom) | item_code |
|---|---|---|
| XF-NK | STD | TAY-NAM-XF55-STD |
| XF-NK | DAK | TAY-NAM-XF55-DAK |
| XF-NK | VG | TAY-NAM-XF55-VG |
| XF-NK | INOX | TAY-NAM-XF55-INOX |
| ALUMIL | STD | TAY-NAM-ALU-STD |
| ALUMIL | INOX | TAY-NAM-ALU-INOX |
| **lookup_key_1_var:** brand | **lookup_key_2_var:** mau_nhom | **default_item:** TAY-NAM-XF55-STD |

**Rule 3: BANLE-THEO-HUONG-MO (LOOKUP)**

| key_1 (huong_mo) | item_code |
|---|---|
| Out | BANLE-XF55-OUT |
| In | BANLE-XF55-IN |
| **lookup_key_1_var:** huong_mo | **lookup_key_2_var:** (trống) | **default_item:** BANLE-XF55-OUT |

**Rule 4: GIOANG-KINH-THEO-LOAI (LOOKUP)**

| key_1 (glass_type) | item_code |
|---|---|
| CUONG_LUC | GIO-EPDM-CL |
| HOP | GIO-EPDM-HOP |
| LOWE | GIO-EPDM-LOWE |
| DON | GIO-EPDM-THUONG |
| **lookup_key_1_var:** (từ glass_type của glass_master) | **lookup_key_2_var:** (trống) | **default_item:** GIO-EPDM-THUONG |

#### Cập nhật AL Profile Line — `item_selection_mode` thành 3 options

Trường `item_selection_mode` đổi từ `Fixed/Dynamic` thành `Fixed/Rule/Formula`:

| fieldname | fieldtype | default | reqd | Mô tả |
|---|---|---|---|---|
| **item_selection_mode** | **Select (Fixed/Rule/Formula)** | **Fixed** | | **★ MỞ RỘNG: thêm Rule** |
| item_code | Link → Item | | khi Fixed | Item cố định (Fixed mode) |
| **item_rule** | **Link → AL Dynamic Item Rule** | | **khi Rule** | **★ MỚI: chọn rule từ dropdown** |
| **item_condition_formula** | **Small Text** | | **khi Formula** | Công thức IF lồng (Formula mode) |
| item_fallback | Link → Item | | khi Rule/Formula | Item dự phòng |

#### Cập nhật AL PK Line — tương tự

| fieldname | fieldtype | default | Mô tả |
|---|---|---|---|
| **item_selection_mode** | **Select (Fixed/Rule/Formula)** | **Fixed** | **★ MỞ RỘNG** |
| item_code | Link → Item | | khi Fixed |
| **item_rule** | **Link → AL Dynamic Item Rule** | | **khi Rule** |
| **item_condition_formula** | **Small Text** | | **khi Formula** |
| item_fallback | Link → Item | | khi Rule/Formula |

### 4.1 AL Profile Line — Schema v18 (đầy đủ)

#### Trường chung

| fieldname | fieldtype | default | reqd | Thay đổi vs v17 |
|---|---|---|---|---|
| sort_order | Int | | ✓ | Không đổi |
| line_type | Select (NHOM/KINH/VTP/PK) | | ✓ | Không đổi |
| line_name | Data | | ✓ | Không đổi |
| slug | Data | | | Không đổi |
| group_tag | Data | | | Không đổi |
| **show_condition** | **Small Text** | | | **★ Code→Small Text** |
| cost_bucket | Link → AL Cost Bucket | | | Không đổi |
| is_active | Check | 1 | | Không đổi |
| **item_selection_mode** | **Select (Fixed/Dynamic)** | **Fixed** | | **★ MỚI v18** |
| **item_condition_formula** | **Small Text** | | | **★ MỚI v18** |
| **item_fallback** | **Link → Item** | | | **★ MỚI v18** |

#### Trường riêng NHOM

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | khi Fixed | Không đổi |
| quantity_rule | Link → AL Calculation Rule | | Không đổi |
| **qty_formula** | **Small Text** | | **★ Code→Small Text** |
| price_type | Select (Rule/Item Price/Fixed) | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |

#### Trường riêng KINH

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| ctx_inject_prefix | Data | ✓ | Không đổi |
| default_glass_master | Link → AL Glass Master | ✓ | Không đổi |
| width_rule | Link → AL Calculation Rule | | Không đổi |
| height_rule | Link → AL Calculation Rule | | Không đổi |
| **width_formula** | **Small Text** | | **★ Code→Small Text** |
| **height_formula** | **Small Text** | | **★ Code→Small Text** |
| **panel_count_formula** | **Small Text** | | **★ Code→Small Text** |
| panel_glass_override_allowed | Check | | Không đổi |
| **qty_per_panel_formula** | **Small Text** | | **★ Code→Small Text** |
| price_type | Select | | Không đổi |
| price_list | Link → Price List | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |
| cut_fee_pct | Float | | Không đổi |

#### Trường riêng VTP

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| quantity_rule | Link → AL Calculation Rule | Không đổi |
| **qty_formula** | **Small Text** | **★ Code→Small Text** |
| price_type | Select | Không đổi |
| price_list | Link → Price List | Không đổi |
| fixed_price | Currency | Không đổi |

#### Trường riêng PK (inline)

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| **sl_formula** | **Small Text** | **★ Code→Small Text** |
| price_list | Link → Price List | Không đổi |
| allow_substitute | Check | Không đổi |
| substitute_item_group | Link → Item Group | Không đổi |

### 4.2 AL PK Line — Schema v18

| fieldname | fieldtype | default | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | | Không đổi |
| **sl_formula** | **Small Text** | | **★ Code→Small Text** |
| price_list | Link → Price List | | Không đổi |
| cost_bucket | Link → AL Cost Bucket | | Không đổi |
| allow_substitute | Check | | Không đổi |
| substitute_item_group | Link → Item Group | | Không đổi |
| **item_selection_mode** | **Select (Fixed/Dynamic)** | **Fixed** | **★ MỚI v18** |
| **item_condition_formula** | **Small Text** | | **★ MỚI v18** |
| **item_fallback** | **Link → Item** | | **★ MỚI v18** |

### 4.3 AL Cost Template Line — Schema v18

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| sort_order | Int | Không đổi |
| line_code | Data | Không đổi |
| line_label | Data | Không đổi |
| **calc_formula** | **Small Text** | **★ Code→Small Text** |
| cost_bucket | Link → AL Cost Bucket | Không đổi |
| is_subtotal | Check | Không đổi |
| show_on_quotation | Check (default 1) | Không đổi |

### 4.4 AL Calculation Rule — Schema v18

| fieldname | fieldtype | Ghi chú |
|---|---|---|
| rule_code | Data | Không đổi |
| rule_name | Data | Không đổi |
| rule_type | Select | Không đổi |
| is_active | Check | Không đổi |
| constant_value | Data | Không đổi |
| **formula_expression** | **Small Text** | **★ Code→Small Text** |
| threshold_input_var | Data | Không đổi |
| threshold_rows | Table | Không đổi |
| lookup_key_1_var | Data | Không đổi |
| lookup_key_2_var | Data | Không đổi |
| lookup_rows | Table | Không đổi |
| lookup_default | Data | Không đổi |
| sequence_items | Table | Không đổi |

### 4.5 AL Cost Template — Schema v18 (bổ sung)

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| template_code | Data | Không đổi |
| template_name | Data | Không đổi |
| product_type | Link → AL Product Type | Không đổi |
| **formula_set** | **Link → Formula Set (optional)** | **★ MỚI v18** |
| al_lines | Table → AL Cost Template Line | Không đổi |

### 4.6 Quotation Item — Custom Field mới v18

| fieldname | fieldtype | Ghi chú |
|---|---|---|
| **al_sales_item_overrides** | **JSON** | **★ MỚI v18 — `{slug: item_code}`. UI xử lý qua JS.** |
| (tất cả field v17 khác) | | Không đổi |

### 4.7 Validation Rules

```python
# alumglass/doctype/al_profile_line/al_profile_line.py

def validate(doc):
    """Validate AL Profile Line — v18 với 3 chế độ."""

    # 1. Rule mode validation
    if doc.item_selection_mode == "Rule":
        if not doc.item_rule:
            frappe.throw("Item Rule bắt buộc khi chọn Rule mode")
        if doc.line_type in ("NHOM", "PK") and not doc.item_fallback:
            frappe.throw("Item Fallback bắt buộc khi chọn Rule mode cho NHOM/PK")
        if doc.line_type == "KINH":
            frappe.throw("KINH line không hỗ trợ Rule mode. Dùng Glass Selector.")
        # Validate rule tồn tại và active
        if not frappe.db.get_value("AL Dynamic Item Rule",
                                    {"rule_code": doc.item_rule, "is_active": 1}, "name"):
            frappe.throw(f"AL Dynamic Item Rule '{doc.item_rule}' không tồn tại hoặc không active")

    # 2. Formula mode validation
    if doc.item_selection_mode == "Formula":
        if not doc.item_condition_formula:
            frappe.throw("Item Condition Formula bắt buộc khi chọn Formula mode")
        if doc.line_type in ("NHOM", "PK") and not doc.item_fallback:
            frappe.throw("Item Fallback bắt buộc khi chọn Formula mode cho NHOM/PK")
        if doc.line_type == "KINH":
            frappe.throw("KINH line không hỗ trợ Formula mode. Dùng Glass Selector.")
        from alumglass.engine.dynamic_item_resolver import validate_item_condition_formula
        validate_item_condition_formula(doc.item_condition_formula)

    # 3. Fixed mode validation
    if doc.item_selection_mode == "Fixed" and doc.line_type in ("NHOM", "PK"):
        if not doc.item_code:
            frappe.throw("Item Code bắt buộc khi chọn Fixed mode")

    # 4. show_condition syntax check (áp dụng cho tất cả mode)
    if doc.show_condition:
        from formula_builder.formula_utils import FormulaValidator
        result = FormulaValidator().validate_formula(doc.show_condition)
        if not result.is_valid:
            frappe.throw(f"show_condition không hợp lệ: {result.error_message}")
```

---

## 5. DYNAMIC ITEM RESOLVER — 3 CHẾ ĐỘ

### 5.0 Tổng quan 3 chế độ

```
┌──────────────────────────────────────────────────────────────────┐
│              3 CHẾ ĐỘ ITEM SELECTION — DỄ → KHÓ                  │
│                                                                  │
│  FIXED              RULE (★ MỚI v18)         FORMULA             │
│  Chọn 1 item cứng   Bảng điều kiện → item    Viết IF lồng        │
│  (giống v17)        (KHÔNG CẦN CODE)         (Power user)        │
│                                                                  │
│  item_code =        item_rule =              item_condition_     │
│  "C3209-20"         "NEP-KINH-THEO-DO-DAY"   formula = "IF(..)"  │
│                                                                  │
│  Dùng cho:           Dùng cho:                Dùng cho:           │
│  Khung, cánh,        Nẹp, gioăng, keo,       Logic phức tạp      │
│  item cố định        tay nắm, khóa, bản lề   không table được    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.1 Thiết kế

```
DynamicItemResolver (Tầng 4.5)
├── resolve(profile_lines, pk_lines, inputs_dict, sales_overrides) → injected_dict
│   ├── _prefetch_candidates() — collect tất cả item cần load metadata
│   ├── _batch_load_metadata(item_codes) — 1 query cho tất cả items + prices
│   ├── _resolve_item(line, inputs_dict, sales_override) → item_code
│   │   ├── Priority 1: sales_override (validate exists)
│   │   ├── Priority 2a (★ MỚI): _evaluate_rule(item_rule) — table lookup, KHÔNG CODE
│   │   ├── Priority 2b: FormulaEngine.evaluate_single(item_condition_formula)
│   │   ├── Priority 3: item_fallback
│   │   └── Priority 4: item_code default
│   └── _get_item_metadata(item_code) → {kg_per_m, price, uom}
│
│   _evaluate_rule(rule_doc, inputs_dict) → item_code
│   ├── THRESHOLD: Duyệt threshold_rows, so sánh input_variable với from/to/operator
│   └── LOOKUP:    Duyệt lookup_rows, so sánh key_1/key_2 với inputs_dict
│
│ ĐIỂM KHÁC BIỆT VS DRAFT v1:
│   ✅ 3 chế độ: Fixed / Rule / Formula
│   ✅ Rule mode: table-based, KHÔNG parsing formula
│   ✅ Rule mode: dùng chung giữa các BOM (thư viện rule)
│   ✅ Dùng FormulaEngine.evaluate_single() cho Formula mode
│   ✅ Batch DB query (không N+1)
│   ✅ _exists_cache là Set (O(1) lookup)
```

### 5.2 Full Implementation

```python
# alumglass/engine/dynamic_item_resolver.py
"""
DynamicItemResolver v18 — Pre-Resolution Phase với 3 chế độ.

Chế độ Rule (★ MỚI): Map điều kiện → item bằng bảng — KHÔNG CẦN VIẾT CODE.
Chế độ Formula:      Viết IF lồng tự do qua FormulaEngine.
Chế độ Fixed:        Item cố định (giống v17).
"""

import frappe
from frappe import _
from frappe.utils import flt
from typing import Any, Dict, List, Optional, Set


class DynamicItemResolver:
    """Resolve item_code cho Dynamic/Rule/Formula lines trước DAG."""

    def __init__(self):
        self._item_cache: Dict[str, Dict] = {}
        self._exists_cache: Set[str] = set()
        self._rule_cache: Dict[str, Any] = {}  # Cache rule docs

    def resolve(
        self,
        profile_lines: List[Any],
        pk_lines: List[Any],
        inputs_dict: Dict[str, Any],
        sales_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Resolve tất cả items — Fixed mode bỏ qua, chỉ xử lý Rule/Formula."""
        sales_overrides = sales_overrides or {}
        injected: Dict[str, Any] = {}

        # === Prefetch candidates ===
        candidates = self._prefetch_candidates(profile_lines, pk_lines, sales_overrides)
        if candidates:
            self._batch_load_metadata(candidates)

        # === Resolve Profile Lines ===
        for line in profile_lines:
            if not getattr(line, "is_active", 1):
                continue
            if getattr(line, "line_type", "") == "KINH":
                continue
            mode = getattr(line, "item_selection_mode", "Fixed")
            if mode == "Fixed":
                continue  # ProfileInterpreter xử lý Fixed mode

            slug = getattr(line, "slug", "") or f"line_{line.idx}"
            sales_override = sales_overrides.get(slug)
            resolved = self._resolve_item(line, inputs_dict, sales_override)

            injected[f"{slug}_item_code"] = resolved
            meta = self._get_item_metadata(resolved)
            if meta:
                injected[f"{slug}_kg_per_m"] = meta.get("kg_per_m", 0)
                injected[f"{slug}_price"] = meta.get("price", 0)

        # === Resolve PK Lines ===
        for idx, line in enumerate(pk_lines):
            mode = getattr(line, "item_selection_mode", "Fixed")
            if mode == "Fixed":
                continue
            pk_slug = f"pk_{idx:04d}"
            resolved = self._resolve_item(line, inputs_dict, None)
            injected[f"{pk_slug}_item_code"] = resolved
            meta = self._get_item_metadata(resolved)
            if meta:
                injected[f"{pk_slug}_price"] = meta.get("price", 0)

        return injected

    # ═══════════════════════════════════════════
    # ITEM RESOLUTION — Priority Chain
    # ═══════════════════════════════════════════

    def _resolve_item(
        self, line: Any, inputs_dict: Dict[str, Any],
        sales_override: Optional[str] = None,
    ) -> str:
        """Priority: Sales override > Rule/Formula > fallback > default."""
        slug = getattr(line, "slug", "unknown")
        mode = getattr(line, "item_selection_mode", "Fixed")

        # Priority 1: Sales override (cao nhất)
        if sales_override:
            if self._item_exists(sales_override):
                return sales_override
            frappe.log_error(
                title="Sales override item không tồn tại",
                message=f"Line: {slug}, override: {sales_override} — fallback"
            )

        # Priority 2a: RULE — Table-based, KHÔNG CODE (★ MỚI v18)
        if mode == "Rule" and getattr(line, "item_rule", None):
            resolved = self._evaluate_rule(line.item_rule, inputs_dict, slug)
            if resolved and self._item_exists(resolved):
                return resolved
            if resolved:
                frappe.log_error(
                    title="Rule resolved to non-existent item",
                    message=f"Line: {slug}, rule: {line.item_rule}, result: {resolved}"
                )

        # Priority 2b: FORMULA — FormulaEngine (power user)
        if mode == "Formula":
            formula = (getattr(line, "item_condition_formula", "") or "").strip()
            if formula:
                resolved = self._evaluate_via_formula_engine(formula, inputs_dict, slug)
                if resolved and self._item_exists(resolved):
                    return resolved
                if resolved:
                    frappe.log_error(
                        title="Formula resolved to non-existent item",
                        message=f"Line: {slug}, result: '{resolved}'"
                    )

        # Priority 3: item_fallback
        fallback = getattr(line, "item_fallback", None)
        if fallback and self._item_exists(fallback):
            return fallback

        # Priority 4: item_code default (Fixed mode)
        default_item = getattr(line, "item_code", None)
        if default_item and self._item_exists(default_item):
            return default_item

        frappe.throw(_(
            "Không thể resolve item cho dòng '{0}'. "
            "Kiểm tra item_rule / item_condition_formula / item_fallback / item_code."
        ).format(slug))

    # ═══════════════════════════════════════════
    # RULE EVALUATION — Table-based (★ MỚI v18)
    # ═══════════════════════════════════════════

    def _evaluate_rule(
        self, rule_code: str, inputs_dict: Dict[str, Any], slug: str
    ) -> Optional[str]:
        """Evaluate AL Dynamic Item Rule — table lookup, không parse formula.

        Hỗ trợ 2 loại rule:
        - THRESHOLD: So sánh input_variable với from/to/operator → chọn item
        - LOOKUP:    So sánh key_1/key_2 với inputs_dict → chọn item

        Returns:
            str: item_code nếu khớp, None nếu không khớp dòng nào.
        """
        # Cache rule doc
        if rule_code not in self._rule_cache:
            rule = frappe.db.get_value(
                "AL Dynamic Item Rule",
                {"rule_code": rule_code, "is_active": 1},
                ["name", "rule_type", "input_variable",
                 "lookup_key_1_var", "lookup_key_2_var", "default_item"],
                as_dict=True,
            )
            if not rule:
                frappe.log_error(
                    title=f"Dynamic Item Rule not found: {rule_code}",
                    message=f"Line: {slug}"
                )
                return None
            self._rule_cache[rule_code] = rule
        else:
            rule = self._rule_cache[rule_code]

        # === THRESHOLD ===
        if rule.rule_type == "THRESHOLD":
            var_name = rule.input_variable
            if not var_name:
                frappe.log_error(
                    title=f"THRESHOLD rule missing input_variable: {rule_code}",
                    message=f"Line: {slug}"
                )
                return rule.default_item

            input_val = flt(inputs_dict.get(var_name, 0))

            # Load threshold rows
            rows = frappe.get_all(
                "AL Dynamic Item Threshold Row",
                filters={"parent": rule.name},
                fields=["from_value", "to_value", "operator", "item_code"],
                order_by="from_value asc",
            )

            for row in rows:
                from_v = flt(row.from_value or 0)
                to_v = flt(row.to_value or 0)
                op = row.operator or "<="

                matched = False
                if op == "<=":
                    # from_v <= input_val <= to_v (to_v=0 → không giới hạn)
                    upper = to_v if to_v > 0 else float("inf")
                    matched = from_v <= input_val <= upper
                elif op == "<":
                    upper = to_v if to_v > 0 else float("inf")
                    matched = (from_v < input_val) if not to_v else (from_v < input_val <= upper)
                elif op == ">=":
                    matched = input_val >= from_v
                elif op == ">":
                    matched = input_val > from_v
                elif op == "=":
                    matched = input_val == from_v

                if matched:
                    return row.item_code

            # No match → default
            return rule.default_item

        # === LOOKUP ===
        if rule.rule_type == "LOOKUP":
            key1 = str(inputs_dict.get(rule.lookup_key_1_var, ""))
            key2 = str(inputs_dict.get(rule.lookup_key_2_var, "")) if rule.lookup_key_2_var else ""

            rows = frappe.get_all(
                "AL Dynamic Item Lookup Row",
                filters={"parent": rule.name},
                fields=["key_1", "key_2", "item_code"],
            )

            for row in rows:
                rk1 = str(row.key_1 or "")
                rk2 = str(row.key_2 or "")
                k1_match = (not rk1 or key1 == rk1)
                k2_match = (not rk2 or key2 == rk2)
                if k1_match and k2_match:
                    return row.item_code

            # No match → default
            return rule.default_item

        return rule.default_item

    # ═══════════════════════════════════════════
    # FORMULA ENGINE INTEGRATION (QĐ-16)
    # ═══════════════════════════════════════════

    def _evaluate_via_formula_engine(
        self, formula: str, context: Dict[str, Any], slug: str
    ) -> Optional[str]:
        """Evaluate qua FormulaEngine — engine DUY NHẤT (chỉ dùng cho Formula mode)."""
        try:
            from formula_builder.formula_utils import FormulaEngine
            engine = FormulaEngine()

            if hasattr(engine, "evaluate_single"):
                result = engine.evaluate_single(formula=formula, context=context)
                return str(result).strip().strip("'\"") if result is not None else None

            # Fallback: dùng calculate() với 1 formula
            result = engine.calculate(
                formulas=[{"name": "_item_result", "formula": formula}],
                inputs=context,
            )
            val = result.get("_item_result")
            return str(val).strip("'\"") if val is not None else None

        except Exception as e:
            frappe.log_error(
                title="DynamicItemResolver: formula evaluation failed",
                message=f"Slug: {slug}, formula: {formula[:200]}, error: {type(e).__name__}: {e}"
            )
            return None

    # ═══════════════════════════════════════════
    # ITEM METADATA — BATCH LOADING
    # ═══════════════════════════════════════════

    def _prefetch_candidates(
        self, profile_lines, pk_lines, sales_overrides
    ) -> Set[str]:
        """Collect tất cả item codes có thể cần."""
        candidates = set()
        for line in profile_lines:
            for attr in ("item_code", "item_fallback"):
                v = getattr(line, attr, None)
                if v: candidates.add(v)
            # Thêm item từ rule rows (nếu rule đã được load)
            if getattr(line, "item_rule", None):
                candidates.add(getattr(line, "item_fallback", None) or "")
        for line in pk_lines:
            for attr in ("item_code", "item_fallback"):
                v = getattr(line, attr, None)
                if v: candidates.add(v)
        candidates.update(v for v in sales_overrides.values() if v)
        candidates.discard(None)
        candidates.discard("")
        return candidates

    def _batch_load_metadata(self, item_codes: Set[str]) -> None:
        """Load metadata trong 2 queries (items + prices)."""
        uncached = item_codes - set(self._item_cache.keys())
        if not uncached:
            return
        items = frappe.get_all(
            "Item",
            filters={"name": ["in", list(uncached)], "disabled": 0},
            fields=["name", "al_kg_per_m", "al_item_type", "stock_uom"],
        )
        if not items:
            return
        loaded = [i.name for i in items]
        prices = frappe.get_all(
            "Item Price",
            filters={"item_code": ["in", loaded], "selling": 1},
            fields=["item_code", "price_list_rate"],
            order_by="valid_from desc",
        )
        price_map = {}
        for p in prices:
            if p.item_code not in price_map:
                price_map[p.item_code] = flt(p.price_list_rate)
        for item in items:
            self._item_cache[item.name] = {
                "item_code": item.name,
                "kg_per_m": flt(item.al_kg_per_m or 0),
                "item_type": item.al_item_type,
                "uom": item.stock_uom,
                "price": price_map.get(item.name, 0),
            }
            self._exists_cache.add(item.name)

    def _get_item_metadata(self, item_code: str) -> Optional[Dict]:
        if not item_code: return None
        if item_code not in self._item_cache:
            self._batch_load_metadata({item_code})
        return self._item_cache.get(item_code)

    def _item_exists(self, item_code: str) -> bool:
        if not item_code: return False
        if item_code in self._exists_cache: return True
        exists = frappe.db.get_value("Item", {"name": item_code, "disabled": 0}, "name")
        if exists: self._exists_cache.add(item_code)
        return bool(exists)

    def clear_cache(self):
        self._item_cache.clear()
        self._exists_cache.clear()
        self._rule_cache.clear()


# ═══════════════════════════════════════════
# VALIDATOR (cập nhật cho Rule mode)
# ═══════════════════════════════════════════

def validate_item_condition_formula(formula: str) -> bool:
    """Validate item_condition_formula cho Formula mode."""
    if not formula or not formula.strip():
        return True
    try:
        from formula_builder.formula_utils import FormulaValidator
        result = FormulaValidator().validate_formula(formula)
        if not result.is_valid:
            frappe.throw(_("Công thức không hợp lệ: {0}").format(result.error_message))
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(_("Lỗi validate công thức: {0}").format(str(e)))

    import re
    slug_pattern = re.compile(r'\b([a-z]+_\d{4}_\w+)\b')
    matches = slug_pattern.findall(formula)
    if matches:
        frappe.throw(_(
            "item_condition_formula không được tham chiếu biến tính toán: {0}. "
            "Chỉ dùng biến đầu vào (W_mm, H_mm, glass_thick_*, do_day, n_canh, ...)."
        ).format(", ".join(set(matches))))

---

## 6. VARIABLERESOLVER v3

### 6.1 FB Integration + Custom Handlers

```python
# alumglass/engine/variable_resolver.py — v3

import frappe, json
from frappe.utils import flt

class VariableResolver:
    """v3: Dùng Formula Variable Binding (FB native, DAG topology)."""

    def resolve(self, quotation_item, bom_doc):
        # ─── Bước 1: FB resolve_bindings_with_deps (DAG topo thay priority) ───
        from formula_builder.api.data_source_registry import resolve_bindings_with_deps
        bindings = frappe.get_all(
            "Formula Variable Binding",
            filters={"is_active": 1},
            fields=["*"],
            order_by="resolve_priority asc",
        )
        inputs_dict = resolve_bindings_with_deps(bindings, quotation_item)

        # ─── Bước 2: BOM Variables + Quotation inputs (domain-specific) ───
        inputs_dict.update(self._resolve_bom_variables(bom_doc, quotation_item))
        inputs_dict.update(self._resolve_quotation_inputs(quotation_item))

        # ─── Bước 3: glass_thick injection (giữ nguyên từ v16/v17) ───
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        glass_selections = self._safe_json(quotation_item, "al_glass_selections")
        for line in profile_set.al_lines:
            if line.line_type != "KINH":
                continue
            prefix = line.ctx_inject_prefix
            glass_code = glass_selections.get(prefix) or line.default_glass_master
            if glass_code:
                thick = frappe.db.get_value("AL Glass Master", glass_code, "total_thick_mm") or 0
                inputs_dict[f"glass_thick_{prefix}"] = float(thick)

        return inputs_dict

    def _resolve_bom_variables(self, bom_doc, quotation_item):
        result = {}
        bom_vars = self._safe_json(quotation_item, "al_bom_vars")
        if not bom_doc.variable_set:
            return result
        for detail in frappe.get_doc("AL Variable Set", bom_doc.variable_set).al_var_details:
            var_code = detail.variable
            result[var_code] = (
                bom_vars.get(var_code)
                or detail.override_default
                or frappe.db.get_value("AL Variable Library", var_code, "default_val")
            )
        return result

    def _resolve_quotation_inputs(self, quotation_item):
        W = flt(quotation_item.get("al_W_mm", 0))
        H = flt(quotation_item.get("al_H_mm", 0))
        return {
            "W_mm": W, "H_mm": H, "qty": flt(quotation_item.get("qty", 1)),
            "W_m": W / 1000, "H_m": H / 1000,
            "mau_nhom": quotation_item.get("al_mau_nhom", ""),
        }

    @staticmethod
    def _safe_json(doc, fieldname):
        raw = doc.get(fieldname) or "{}"
        return json.loads(raw) if isinstance(raw, str) else (raw or {})


# ═══════════════════════════════════════════
# CUSTOM HANDLERS — Đăng ký vào FB data_source_registry
# ═══════════════════════════════════════════

def _handle_bom_variable(source_config, resolved_so_far, context):
    """Handler: đọc biến từ al_bom_vars JSON của Quotation Item."""
    var_code = source_config.get("var_code")
    quotation_item = context.get("_quotation_item")
    if not var_code or not quotation_item:
        return None
    bom_vars = json.loads(quotation_item.get("al_bom_vars") or "{}")
    return bom_vars.get(var_code)


def _handle_rule_engine_lookup(source_config, resolved_so_far, context):
    """Handler: tra AL Calculation Rule LOOKUP/THRESHOLD."""
    rule_code = source_config.get("rule_code")
    arg_mapping = source_config.get("args", {})
    if not rule_code:
        return None

    rule = frappe.db.get_value(
        "AL Calculation Rule",
        {"rule_code": rule_code, "is_active": 1},
        ["name", "rule_type", "lookup_default", "threshold_input_var"],
        as_dict=True,
    )
    if not rule:
        return None

    if rule.rule_type == "LOOKUP":
        key_values = {k: resolved_so_far.get(v, "") for k, v in arg_mapping.items()}
        rows = frappe.get_all("AL Rule Lookup Row",
            filters={"parent": rule.name},
            fields=["key_1", "key_2", "key_3", "result_value"])
        for row in rows:
            if all(not key_values.get(f"key_{i}") or
                   str(key_values[f"key_{i}"]) == str(row.get(f"key_{i}") or "")
                   for i in range(1, 4)):
                return flt(row.result_value or 0)
        return flt(rule.lookup_default or 0)

    if rule.rule_type == "THRESHOLD":
        val = flt(resolved_so_far.get(rule.threshold_input_var, 0))
        rows = frappe.get_all("AL Rule Threshold Row",
            filters={"parent": rule.name},
            fields=["from_value", "to_value", "result_value"],
            order_by="from_value asc")
        for row in rows:
            if row.from_value <= val and (not row.to_value or val <= row.to_value):
                return flt(row.result_value or 0)
        return flt(rule.lookup_default or 0)

    return None


def register_custom_handlers():
    """Đăng ký 2 custom handlers vào FB data_source_registry."""
    try:
        from formula_builder.api.data_source_registry import DATA_SOURCE_HANDLERS
        DATA_SOURCE_HANDLERS["bom_variable"] = _handle_bom_variable
        DATA_SOURCE_HANDLERS["rule_engine_lookup"] = _handle_rule_engine_lookup
        frappe.logger().info("AlumGlass: Registered custom FB handlers")
    except ImportError:
        frappe.logger().warning("AlumGlass: FB not available — handlers skipped")
    except Exception as e:
        frappe.log_error(title="FB handler registration failed", message=str(e))
```

### 6.2 Source Type Mapping — AL → FB

| AL source_type | FB source_type / Handler | Ghi chú |
|---|---|---|
| Quotation Input | `linked_doctype_field` | Đọc field từ Quotation Item |
| BOM Variable | `bom_variable` (custom) | Đọc từ al_bom_vars JSON |
| BOM Attribute | `linked_doctype_field` | Đọc field từ AL BOM |
| Rule Engine Result | `rule_engine_lookup` (custom) | Tra LOOKUP/THRESHOLD |
| Computed | `computed` (FB native, DAG) | Mạnh hơn: topological sort |
| Context Inject | — (giữ nguyên) | glass_thick injection |

**FB source types mới user có thể dùng (12 thay vì 5):**
`constant`, `linked_doctype_field`, `whole_doctype`, `child_table_aggregate`, `global_default`, `session_variable`, `doctype_query`, `custom_function`, `dynamic_link`, `computed` + 2 custom handlers.

---

## 7. DAG INTEGRATION

### 7.1 Vị trí Dynamic Item trong toàn bộ flow

```
TRƯỚC DAG — Tầng 4.5 (DynamicItemResolver):
  inputs_dict (sau VariableResolver) bao gồm:
    W_mm=1500, H_mm=2400, qty=1, n_canh=2, do_day="2.0mm"
    glass_thick_kinh_canh=24.0    ← inject từ AL Glass Master
    don_gia_nhom=180000           ← resolve từ FB Variable Binding (LOOKUP)
    ★ nhom_0060_item_code="C3211-20"   ← DynamicItemResolver
    ★ nhom_0060_kg_per_m=0.312         ← DynamicItemResolver
    ★ nhom_0060_price=113000            ← DynamicItemResolver

VÀO DAG — FormulaEngine thấy item như hằng số:
  nhom_0060_active = (show_condition_formula)   # Boolean
  nhom_0060_qty    = H_m * 2 * qty
  nhom_0060_kg     = nhom_0060_kg_per_m         # Constant
  nhom_0060_dg     = nhom_0060_price            # Constant
  nhom_0060_tt     = nhom_0060_qty * nhom_0060_kg * nhom_0060_dg
  VL_NHOM = nhom_0010_tt + nhom_0020_tt + ... + nhom_0060_tt
  GIA_BAN = (VL_NHOM + VL_KINH + VL_VTP + VL_PK) * markup

SAU DAG — Module Hooks (v17):
  Hook A: DiscountStack.apply() → GIA_BAN_THUONG_MAI
  Hook B: BOMVersionManager.link_version()
  Hook C: CostVarianceAnalyzer.register()
  Hook D: NotificationEngine.check_alerts()
```

### 7.2 Tránh Circular Dependency

```
QUY TẮC: item_condition_formula CHỈ dùng biến từ inputs_dict (đã có trước DAG):

✅ ĐƯỢC PHÉP:
  glass_thick_kinh_canh   — INPUT (inject từ GlassMaster)
  W_mm, H_mm, qty         — INPUT (từ Quotation)
  n_canh, do_day          — INPUT (từ BOM Variables)
  don_gia_nhom            — INPUT (từ FB Variable Binding LOOKUP)

❌ BỊ REJECT (validate tại form save):
  nhom_0060_qty           — COMPUTED bởi DAG (slug pattern: word_NNNN_suffix)
  nhom_0060_tt            — COMPUTED bởi DAG
  TONG_VL, GIA_BAN        — COMPUTED bởi DAG

ENFORCE: validate_item_condition_formula() scan pattern r'\b[a-z]+_\d{4}_\w+\b'
→ Bất kỳ match nào → throw ValidationError ngay khi admin save.
```

### 7.3 Dependency Resolve Timeline

```
t=0: VariableResolver.resolve()        → inputs_dict cơ bản + glass_thick injection
t=1: DynamicItemResolver.resolve()     → FE.evaluate_single() → inject item_code, kg, price
t=2: ProfileInterpreter.pass1_scan()   → variable_registry, panel_counts
t=3: ProfileInterpreter.pass2_build()  → build formulas với item đã resolved
t=4: PkResolver.build_formulas()       → formulas_pk
t=5: CostAccumulator.build()           → formulas_cost (Formula Set hoặc legacy)
t=6: FormulaEngine.calculate()         → DAG execute — DUY NHẤT 1 LẦN
t=7: SnapshotBuilder.persist()         → lưu ConfigSnapshot + item_context vào audit trail
t=8: Hooks A→D                         → Discount, Version, Variance, Notification
```

---

## 8. BOM ORCHESTRATOR v18 — 7 BƯỚC

```python
# alumglass/engine/orchestrator.py — BomOrchestrator v18

class BomOrchestrator:
    """BomOrchestrator v18 — 7 bước + Module Hooks."""

    def run(self, quotation_item, bom_doc):
        from alumglass.engine.variable_resolver import VariableResolver
        from alumglass.engine.dynamic_item_resolver import DynamicItemResolver
        from alumglass.engine.profile_interpreter import ProfileInterpreter
        from alumglass.engine.pk_resolver import PkResolver
        from alumglass.engine.cost_accumulator import CostAccumulator
        from alumglass.engine.snapshot_builder import SnapshotBuilder
        from alumglass.engine.module_registry import fire_hooks
        from formula_builder.formula_utils import FormulaEngine

        # Config
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        pk_set = frappe.get_doc("AL PK Set", bom_doc.pk_set) if bom_doc.pk_set else None
        glass_selections = VariableResolver._safe_json(quotation_item, "al_glass_selections")
        pk_overrides = VariableResolver._safe_json(quotation_item, "al_pk_overrides")
        sales_overrides = VariableResolver._safe_json(quotation_item, "al_sales_item_overrides")

        # ═══ BƯỚC 1: VariableResolver v3 ═══
        var_resolver = VariableResolver()
        inputs_dict = var_resolver.resolve(quotation_item, bom_doc)

        # ═══ BƯỚC 2: DynamicItemResolver ★ MỚI v18 ═══
        active_lines = [ln for ln in profile_set.al_lines if getattr(ln, "is_active", 1)]
        pk_lines = pk_set.al_pk_lines if pk_set else []
        item_resolver = DynamicItemResolver()
        item_context = item_resolver.resolve(
            profile_lines=active_lines, pk_lines=pk_lines,
            inputs_dict=inputs_dict, sales_overrides=sales_overrides,
        )
        inputs_dict.update(item_context)

        # ═══ BƯỚC 3: ProfileInterpreter Pass 1 ═══
        interpreter = ProfileInterpreter()
        variable_registry, panel_counts = interpreter.pass1_scan(
            active_lines, inputs_dict, glass_selections)

        # ═══ BƯỚC 4: ProfileInterpreter Pass 2 ═══
        all_formulas, bucket_acc = interpreter.pass2_build(
            active_lines, inputs_dict, variable_registry,
            panel_counts, glass_selections)

        # ═══ BƯỚC 5: PkResolver ═══
        formulas_pk, pk_warnings = PkResolver().build_formulas(bom_doc, pk_overrides)
        all_formulas.extend(formulas_pk)

        # ═══ BƯỚC 6: CostAccumulator v2 ═══
        formulas_cost = CostAccumulator().build_bucket_and_template_formulas(
            bucket_acc=bucket_acc,
            cost_template_name=bom_doc.default_cost_template,
        )
        all_formulas.extend(formulas_cost)

        # ═══ BƯỚC 7: FormulaEngine.calculate() + SnapshotBuilder ═══
        engine = FormulaEngine()
        result = engine.calculate(formulas=all_formulas, inputs=inputs_dict)
        snapshot = SnapshotBuilder().persist(
            quotation_item=quotation_item, bom_doc=bom_doc,
            inputs_dict=inputs_dict, result=result,
            item_context=item_context,  # ★ Audit trail: Dynamic Item resolve info
        )

        # Ghi Quotation Item
        self._write_result(quotation_item, result, snapshot, pk_warnings)

        # ═══ HOOKS A→D (v17 — không đổi) ═══
        fire_hooks("after_calculate",
                   result=result, quotation_item=quotation_item,
                   bom_doc=bom_doc)

        return result, pk_warnings

    def _write_result(self, qi, result, snapshot, warnings):
        qi.db_set("al_config_snapshot", snapshot.name)
        for field in ["al_vl_nhom", "al_vl_kinh", "al_vl_vtp", "al_vl_pk",
                       "al_tong_vl", "al_gia_thanh", "al_gia_ban", "al_gia_vat"]:
            bucket = field.replace("al_", "").upper() if field != "al_tong_vl" else "TONG_VL"
            if bucket in result:
                qi.db_set(field, flt(result[bucket]))
```

---

## 9. COSTACCUMULATOR v2 + PROFILEINTERPRETER UPDATE

### 9.1 CostAccumulator v2 — Formula Set Integration

```python
# alumglass/engine/cost_accumulator.py — v2

class CostAccumulator:
    def build_bucket_and_template_formulas(self, bucket_acc, cost_template_name):
        formulas = []

        # Bucket formulas (giữ nguyên v17)
        for bucket_code, var_list in bucket_acc.items():
            if var_list:
                formulas.append({"name": bucket_code, "formula": " + ".join(var_list)})

        if not cost_template_name:
            return formulas

        template = frappe.get_cached_doc("AL Cost Template", cost_template_name)

        # ★ v18: Dùng Formula Set nếu có (QĐ-19)
        if template.get("formula_set"):
            try:
                from formula_builder.api.variable_resolver import VariableResolver as FBResolver
                fb_resolver = FBResolver()
                set_formulas = fb_resolver._get_formula_set_output(template.formula_set)
                formulas.extend(set_formulas)
                return formulas
            except Exception as e:
                frappe.log_error(
                    title="CostAccumulator: Formula Set failed, falling back to al_lines",
                    message=str(e))

        # Fallback: AL Cost Template Line (backward compat)
        for line in (template.al_lines or []):
            if line.calc_formula:
                formulas.append({
                    "name": line.line_code or f"cost_{line.sort_order}",
                    "formula": line.calc_formula,
                })

        return formulas
```

### 9.2 ProfileInterpreter — Dynamic Item Check

```python
# Trong pass2_build — cập nhật cho Dynamic Item

def pass2_build(self, lines, inputs_dict, variable_registry, panel_counts, glass_selections):
    all_formulas = []
    bucket_acc = defaultdict(list)

    for line in lines:
        slug = line.slug
        line_type = line.line_type

        if line_type == "NHOM":
            # ★ v18: Check Dynamic mode
            if getattr(line, "item_selection_mode", "Fixed") == "Dynamic":
                # kg_per_m và price đã inject vào inputs_dict bởi DynamicItemResolver
                kg_var = f"{slug}_kg_per_m"
                price_var = f"{slug}_price"
            else:
                # Fixed mode — v17 logic: đọc trực tiếp từ Item
                item = frappe.get_cached_doc("Item", line.item_code)
                kg_val = flt(item.al_kg_per_m or 0)
                # Inject như constant vào inputs_dict
                inputs_dict[f"{slug}_kg_per_m"] = kg_val
                kg_var = f"{slug}_kg_per_m"
                # Đơn giá: Fixed / Rule / Item Price
                price_val = self._resolve_price(line, inputs_dict)
                inputs_dict[f"{slug}_price"] = price_val
                price_var = f"{slug}_price"

            # show_condition → active
            if line.show_condition:
                all_formulas.append({"name": f"{slug}_active", "formula": line.show_condition})
            else:
                inputs_dict[f"{slug}_active"] = 1

            # qty
            qty_expr = self._get_qty_formula(line)
            all_formulas.append({
                "name": f"{slug}_qty",
                "formula": f"IF({slug}_active, {qty_expr}, 0)"
            })

            # thành tiền
            all_formulas.append({
                "name": f"{slug}_tt",
                "formula": f"{slug}_qty * {kg_var} * {price_var}"
            })

            bucket_acc[line.cost_bucket or "VL_NHOM"].append(f"{slug}_tt")

        # KINH, VTP, PK: logic v17 không đổi
        # ...

    return all_formulas, bucket_acc
```

---

## 10. MIGRATION SCRIPTS

### 10.1 Patch 1 — Alter 9 Formula Fields: Code → Small Text

```python
# aluglass/patches/v18_0/alter_formula_fields_to_small_text.py
import frappe

FIELD_MAP = [
    ("AL Profile Line", "show_condition"),
    ("AL Profile Line", "qty_formula"),
    ("AL Profile Line", "width_formula"),
    ("AL Profile Line", "height_formula"),
    ("AL Profile Line", "panel_count_formula"),
    ("AL Profile Line", "qty_per_panel_formula"),
    ("AL PK Line", "sl_formula"),
    ("AL Cost Template Line", "calc_formula"),
    ("AL Calculation Rule", "formula_expression"),  # ★ Bổ sung vs draft v1
]

def execute():
    print("v18 Migration: Alter 9 formula fields Code → Small Text")
    for doctype, fieldname in FIELD_MAP:
        if frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname}):
            frappe.db.set_value("DocField",
                {"parent": doctype, "fieldname": fieldname},
                "fieldtype", "Small Text")
            print(f"  OK: {doctype}.{fieldname}")
        else:
            print(f"  SKIP: {doctype}.{fieldname} — not found")
    frappe.clear_cache()
    frappe.db.commit()
    print("v18: Formula fields standardized")
```

### 10.2 Patch 2 — Add Dynamic Item + AL Dynamic Item Rule Fields

```python
# aluglass/patches/v18_0/add_dynamic_item_fields.py
import frappe

def execute():
    print("v18 Migration: Adding Dynamic Item fields + AL Dynamic Item Rule DocTypes")

    # === AL Profile Line: cập nhật item_selection_mode + thêm item_rule ===
    _add_or_update_field("AL Profile Line", {
        "fieldname": "item_selection_mode", "fieldtype": "Select",
        "label": "Item Selection Mode", "options": "Fixed\nRule\nFormula",
        "default": "Fixed", "insert_after": "is_active",
        "description": "Fixed: chọn item cứng. Rule: dùng bảng điều kiện. Formula: viết IF lồng.",
    })
    _add_fields("AL Profile Line", [
        {"fieldname": "item_rule", "fieldtype": "Link",
         "label": "Item Rule", "options": "AL Dynamic Item Rule",
         "insert_after": "item_selection_mode",
         "depends_on": "eval:doc.item_selection_mode=='Rule'",
         "description": "Chọn rule từ thư viện — KHÔNG cần viết code."},
        {"fieldname": "item_condition_formula", "fieldtype": "Small Text",
         "label": "Item Condition Formula", "insert_after": "item_rule",
         "depends_on": "eval:doc.item_selection_mode=='Formula'",
         "description": "Công thức IF lồng. Ví dụ: IF(glass_thick_kinh_canh <= 10.38, 'C3209-20', 'C3211-20')"},
        {"fieldname": "item_fallback", "fieldtype": "Link", "options": "Item",
         "label": "Item Fallback", "insert_after": "item_condition_formula",
         "depends_on": "eval:['Rule','Formula'].includes(doc.item_selection_mode)",
         "description": "Item dùng khi Rule/Formula không resolve được."},
    ])

    # === AL PK Line: tương tự ===
    _add_or_update_field("AL PK Line", {
        "fieldname": "item_selection_mode", "fieldtype": "Select",
        "label": "Item Selection Mode", "options": "Fixed\nRule\nFormula",
        "default": "Fixed", "insert_after": "item_code",
    })
    _add_fields("AL PK Line", [
        {"fieldname": "item_rule", "fieldtype": "Link",
         "label": "Item Rule", "options": "AL Dynamic Item Rule",
         "insert_after": "item_selection_mode",
         "depends_on": "eval:doc.item_selection_mode=='Rule'"},
        {"fieldname": "item_condition_formula", "fieldtype": "Small Text",
         "label": "Item Condition Formula", "insert_after": "item_rule",
         "depends_on": "eval:doc.item_selection_mode=='Formula'"},
        {"fieldname": "item_fallback", "fieldtype": "Link", "options": "Item",
         "label": "Item Fallback", "insert_after": "item_condition_formula",
         "depends_on": "eval:['Rule','Formula'].includes(doc.item_selection_mode)"},
    ])

    # === AL Cost Template ===
    _add_fields("AL Cost Template", [
        {"fieldname": "formula_set", "fieldtype": "Link", "options": "Formula Set",
         "label": "Formula Set (optional)", "insert_after": "product_type"},
    ])

    # === Tạo AL Dynamic Item Rule DocType (nếu chưa có) ===
    _create_dynamic_item_rule_doctype()

    frappe.db.commit()
    print("v18: Dynamic Item fields + Rule DocTypes added")


def _create_dynamic_item_rule_doctype():
    """Tạo DocType AL Dynamic Item Rule nếu chưa tồn tại."""
    if frappe.db.exists("DocType", "AL Dynamic Item Rule"):
        print("  SKIP: AL Dynamic Item Rule DocType exists")
        return

    # Tạo DocType
    dt = frappe.new_doc("DocType")
    dt.name = "AL Dynamic Item Rule"
    dt.module = "AlumGlass"
    dt.istable = 0
    dt.is_submittable = 0
    dt.naming_rule = "By fieldname"
    dt.autoname = "field:rule_code"
    dt.engine = "InnoDB"
    dt.fields = [
        {"fieldname": "rule_code", "fieldtype": "Data", "label": "Rule Code",
         "reqd": 1, "unique": 1},
        {"fieldname": "rule_name", "fieldtype": "Data", "label": "Rule Name", "reqd": 1},
        {"fieldname": "rule_type", "fieldtype": "Select",
         "label": "Rule Type", "options": "THRESHOLD\nLOOKUP", "reqd": 1},
        {"fieldname": "input_variable", "fieldtype": "Data",
         "label": "Input Variable",
         "depends_on": "eval:doc.rule_type=='THRESHOLD'",
         "description": "Tên biến trong inputs_dict. VD: glass_thick_kinh_canh"},
        {"fieldname": "column_break_1", "fieldtype": "Column Break"},
        {"fieldname": "lookup_key_1_var", "fieldtype": "Data",
         "label": "Key 1 Variable",
         "depends_on": "eval:doc.rule_type=='LOOKUP'",
         "description": "Tên biến key 1. VD: brand"},
        {"fieldname": "lookup_key_2_var", "fieldtype": "Data",
         "label": "Key 2 Variable",
         "depends_on": "eval:doc.rule_type=='LOOKUP'",
         "description": "Tên biến key 2 (optional). VD: mau_nhom"},
        {"fieldname": "section_break_threshold", "fieldtype": "Section Break",
         "label": "Threshold Rows",
         "depends_on": "eval:doc.rule_type=='THRESHOLD'"},
        {"fieldname": "threshold_rows", "fieldtype": "Table",
         "label": "Threshold Rows", "options": "AL Dynamic Item Threshold Row",
         "depends_on": "eval:doc.rule_type=='THRESHOLD'"},
        {"fieldname": "section_break_lookup", "fieldtype": "Section Break",
         "label": "Lookup Rows",
         "depends_on": "eval:doc.rule_type=='LOOKUP'"},
        {"fieldname": "lookup_rows", "fieldtype": "Table",
         "label": "Lookup Rows", "options": "AL Dynamic Item Lookup Row",
         "depends_on": "eval:doc.rule_type=='LOOKUP'"},
        {"fieldname": "section_break_default", "fieldtype": "Section Break"},
        {"fieldname": "default_item", "fieldtype": "Link",
         "label": "Default Item", "options": "Item", "reqd": 1,
         "description": "Item dùng khi không có điều kiện nào khớp"},
        {"fieldname": "is_active", "fieldtype": "Check", "label": "Is Active", "default": "1"},
        {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
    ]
    dt.permissions = [
        {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
    ]
    dt.insert(ignore_permissions=True)

    # Tạo child DocTypes
    _create_child_doctype("AL Dynamic Item Threshold Row", [
        {"fieldname": "from_value", "fieldtype": "Float", "label": "From", "reqd": 0},
        {"fieldname": "to_value", "fieldtype": "Float", "label": "To (0=unlimited)", "reqd": 0},
        {"fieldname": "operator", "fieldtype": "Select",
         "label": "Op", "options": "≤\n<\n≥\n>\n=", "default": "≤", "reqd": 1},
        {"fieldname": "item_code", "fieldtype": "Link",
         "label": "Item", "options": "Item", "reqd": 1},
        {"fieldname": "note", "fieldtype": "Data", "label": "Note"},
    ])

    _create_child_doctype("AL Dynamic Item Lookup Row", [
        {"fieldname": "key_1", "fieldtype": "Data", "label": "Key 1", "reqd": 1},
        {"fieldname": "key_2", "fieldtype": "Data", "label": "Key 2", "reqd": 0},
        {"fieldname": "item_code", "fieldtype": "Link",
         "label": "Item", "options": "Item", "reqd": 1},
        {"fieldname": "note", "fieldtype": "Data", "label": "Note"},
    ])

    print("  OK: Created AL Dynamic Item Rule + 2 child DocTypes")


def _create_child_doctype(name, fields):
    if frappe.db.exists("DocType", name):
        print(f"  SKIP: {name} exists")
        return
    dt = frappe.new_doc("DocType")
    dt.name = name
    dt.module = "AlumGlass"
    dt.istable = 1
    dt.engine = "InnoDB"
    dt.fields = fields
    dt.insert(ignore_permissions=True)
    print(f"  OK: Created child DocType: {name}")


def _add_or_update_field(doctype, field_def):
    """Add or update a custom field (for changing existing field options)."""
    if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_def["fieldname"]}):
        cf = frappe.get_doc("Custom Field", {"dt": doctype, "fieldname": field_def["fieldname"]})
        for k, v in field_def.items():
            cf.set(k, v)
        cf.save(ignore_permissions=True)
        print(f"  UPDATED: {doctype}.{field_def['fieldname']}")
    elif frappe.db.exists("DocField", {"parent": doctype, "fieldname": field_def["fieldname"]}):
        frappe.db.set_value("DocField",
            {"parent": doctype, "fieldname": field_def["fieldname"]},
            field_def)
        print(f"  UPDATED: {doctype}.{field_def['fieldname']} (core field)")
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = doctype
        for k, v in field_def.items():
            cf.set(k, v)
        cf.insert(ignore_permissions=True)
        print(f"  OK: Added {doctype}.{field_def['fieldname']}")


def _add_fields(doctype, fields):
    for f in fields:
        _add_or_update_field(doctype, f)
```

### 10.3 Patch 3 — Sales Override Custom Field

```python
# aluglass/patches/v18_0/add_sales_override_field.py
import frappe

def execute():
    if frappe.db.exists("Custom Field", {"dt": "Quotation Item", "fieldname": "al_sales_item_overrides"}):
        print("SKIP: al_sales_item_overrides exists")
        return
    cf = frappe.new_doc("Custom Field")
    cf.dt = "Quotation Item"
    cf.fieldname = "al_sales_item_overrides"
    cf.fieldtype = "JSON"
    cf.label = "Sales Item Overrides"
    cf.insert_after = "al_pk_overrides"
    cf.description = "Sales override item cho Dynamic rows. Format: {slug: item_code}"
    cf.hidden = 1
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
    print("OK: al_sales_item_overrides added")
```

### 10.4 Patch 4 — Migrate AL Variable Binding → FB

```python
# aluglass/patches/v18_0/migrate_variable_bindings.py
import frappe, json

SOURCE_TYPE_MAP = {
    "Quotation Input": "linked_doctype_field",
    "BOM Variable": "bom_variable",
    "BOM Attribute": "linked_doctype_field",
    "Rule Engine Result": "rule_engine_lookup",
    "Computed": "computed",
    "Context Inject": None,
}

def execute():
    bindings = frappe.get_all("AL Variable Binding", fields=["*"])
    print(f"v18 Migration: {len(bindings)} AL Bindings → Formula Variable Binding")

    for al_b in bindings:
        fb_type = SOURCE_TYPE_MAP.get(al_b.source_type)
        if fb_type is None:
            print(f"  SKIP: {al_b.binding_code} (source_type={al_b.source_type})")
            continue
        if frappe.db.exists("Formula Variable Binding", {"variable_name": al_b.variable_name}):
            continue

        fb = frappe.new_doc("Formula Variable Binding")
        fb.variable_name = al_b.variable_name
        fb.variable_label = al_b.variable_label
        fb.source_type = fb_type
        fb.resolve_priority = al_b.resolve_priority
        fb.data_type = al_b.data_type
        fb.is_active = al_b.is_active

        if al_b.source_type == "BOM Variable":
            fb.source_config = json.dumps({"var_code": al_b.variable_name})
        elif al_b.source_type in ("Quotation Input", "BOM Attribute"):
            old = json.loads(al_b.source_config or "{}")
            fb.source_config = json.dumps({"fieldname": old.get("fieldname", al_b.variable_name)})
        else:
            fb.source_config = al_b.source_config

        fb.insert(ignore_permissions=True)
        print(f"  OK: {al_b.variable_name} ({al_b.source_type} → {fb_type})")

    frappe.db.commit()
    print("v18: Variable Binding migration complete")
```

### 10.5 Migration Checklist

| Bước | Công việc | Script | Prio |
|---|---|---|---|
| 1 | **Backup database** | — | P0 BẮT BUỘC |
| 2 | Verify v17 stable (8 ví dụ PASS) | Manual | P0 |
| 3 | Register 2 custom FB handlers | hooks.py → register_custom_handlers() | P0 |
| 4 | Alter 9 fields: Code → Small Text | patches/v18_0/alter_formula_fields_to_small_text.py | P0 |
| 5 | **Tạo 3 DocType: AL Dynamic Item Rule + 2 Child** | patches/v18_0/add_dynamic_item_fields.py | P0 |
| 6 | Add Dynamic Item + Rule fields + update item_selection_mode | (cùng script) | P0 |
| 7 | Add `al_sales_item_overrides` | patches/v18_0/add_sales_override_field.py | P0 |
| 7 | Migrate AL → FB Variable Bindings | patches/v18_0/migrate_variable_bindings.py | P1 |
| 8 | Deploy engine files (Resolver, Orchestrator, ...) | engine/*.py | P0 |
| 9 | `bench migrate` + `bench restart` | — | P0 |
| 10 | Test: 8 ví dụ v17 PASS (Fixed mode) | Manual | P0 |
| 11 | Test: Dynamic item resolve đúng | Manual | P0 |
| 12 | Test: Sales override priority chain | Manual | P0 |

---

## 11. IMPLEMENTATION CHECKLIST

### Phase 1 — Engine Core (3-4 ngày)

| # | Task | File | Notes |
|---|---|---|---|
| 1.1 | Viết fb_handlers.py (2 custom handlers) | `engine/fb_handlers.py` | register_custom_handlers() |
| 1.2 | **Viết DynamicItemResolver (3 chế độ: Rule + Formula + Fixed)** | `engine/dynamic_item_resolver.py` | Xem §5.2 |
| 1.3 | **Viết `_evaluate_rule()` — THRESHOLD + LOOKUP** | (cùng file) | Table-based, không parse formula |
| 1.4 | Cập nhật VariableResolver v3 | `engine/variable_resolver.py` | resolve_bindings_with_deps() |
| 1.5 | Cập nhật BomOrchestrator (7 bước) | `engine/orchestrator.py` | Thêm bước 2 |
| 1.6 | **Cập nhật ProfileInterpreter — handle 3 mode** | `engine/profile_interpreter.py` | Fixed/Rule/Formula trong pass2_build |
| 1.7 | Cập nhật CostAccumulator v2 | `engine/cost_accumulator.py` | Formula Set fallback |

### Phase 2 — DocTypes + Migration (2-3 ngày)

| # | Task | File | Notes |
|---|---|---|---|
| 2.1 | **Tạo 3 DocType mới: AL Dynamic Item Rule + 2 Child Tables** | `doctype/al_dynamic_item_rule/` | THRESHOLD + LOOKUP |
| 2.2 | **Tạo 4 Rule fixtures mặc định (nẹp, tay nắm, bản lề, gioăng)** | `fixtures/al_dynamic_item_rule.json` | Rule mẫu cho user |
| 2.3 | Patch: alter 9 formula fields Code→Small Text | `patches/v18_0/alter_formula_fields_to_small_text.py` | |
| 2.4 | **Patch: add item_rule + update item_selection_mode options** | `patches/v18_0/add_dynamic_item_fields.py` | Fixed/Rule/Formula |
| 2.5 | Patch: add sales override field | `patches/v18_0/add_sales_override_field.py` | |
| 2.6 | Patch: migrate AL→FB bindings | `patches/v18_0/migrate_variable_bindings.py` | |
| 2.7 | Update hooks.py | `aluglass/hooks.py` | |
| 2.8 | Update AL Profile Line form layout (Rule section) | Customize Form | |

### Phase 3 — Testing (2-3 ngày)

| # | Test Case | Expected Result |
|---|---|---|
| 3.1 | 8 ví dụ kiểm chứng v17 (Fixed mode) | PASS 100% |
| 3.2 | **Rule THRESHOLD: resolve đúng item theo glass_thick** | C3209/C3210/C3211 theo ngưỡng |
| 3.3 | **Rule LOOKUP: resolve đúng item theo brand + màu** | TAY-NAM-XF55-INOX khi brand=XF-NK, màu=INOX |
| 3.4 | Priority: Sales override > Rule > Formula > fallback > default | Override thắng |
| 3.5 | Rule không khớp → fallback item | Không crash, dùng default_item |
| 3.6 | Formula tham chiếu slug variable → reject | ValidationError |
| 3.7 | Item disabled → fallback hoạt động | Log warning |
| 3.8 | Thay đổi Rule (thêm ngưỡng mới) → tất cả BOM tự cập nhật | Resolve đúng với ngưỡng mới |
| 3.9 | Batch DB với 20+ Dynamic rows | ≤2 queries |
| 3.10 | Formula Set trong Cost Template | evaluate đúng, explain() OK |
| 3.11 | **Fixed mode = identical to v17 output** | 100% match |
| 3.12 | **Rule mode returns same item as Fixed mode với cùng input** | 100% match (cùng logic, khác cách setup) |

### Phase 4 — UI (2-3 ngày)

| # | Task | File | Prio |
|---|---|---|---|
| 4.1 | Monaco editor cho Small Text formula fields | `public/js/bom_dialog.js` | P1 |
| 4.2 | **Rule selector dropdown trong Profile Line form** | (cùng file) | **P0** |
| 4.3 | **Rule "Test" button: nhập input → preview item được chọn** | (cùng file) | **P0** |
| 4.4 | Resolved item display trong BOM Dialog (badge) | `public/js/quotation_item.js` | P1 |
| 4.5 | Sales Override Panel (dropdown per row) | (cùng file) | P2 |
| 4.6 | Error toast khi Rule/Formula fail | (cùng file) | P1 |
| 4.7 | Fixed/Rule/Formula toggle switch với UI khác nhau | (cùng file) | P1 |

### Phase 5 — Documentation (1 ngày)

| # | Task |
|---|---|
| 5.1 | Update CLAUDE.md với v18 changes |
| 5.2 | Update IMPLEMENTATION_PLAN.md |
| 5.3 | Viết migration guide cho admin |
| 5.4 | Viết ví dụ Dynamic Item tutorial |

### Phase 6 — Deploy & Monitor (ongoing)

| # | Task |
|---|---|
| 6.1 | Deploy lên staging, verify full pipeline |
| 6.2 | Monitor performance: DynamicItemResolver timing |
| 6.3 | Monitor errors: formula evaluation failures |
| 6.4 | Deploy production, monitor 1 tuần |

---

## 12. RISK & EDGE CASES

### 12.1 Risk Matrix

| # | Risk | Sev | Like | Mitigation |
|---|---|---|---|---|
| R1 | Formula trả về item không tồn tại | Med | Med | item_fallback bắt buộc. _item_exists() validate. Log + alert. |
| R2 | Circular: formula dùng slug variable | High | Low | Slug-pattern regex reject tại form save. |
| R3 | FE.evaluate_single() chưa có trong FB | High | Low | Fallback calculate() với 1 formula. Xem code §5.2. |
| R4 | Performance: 100+ Dynamic rows | Low | Low | Batch DB, item_cache. <200ms cho 100 rows. |
| R5 | FB Binding migration sai type | Med | Med | Test 8 ví dụ. Rollback flag: dùng AL bindings cũ. |
| R6 | Sales override item sai loại (NHOM→KINH) | Med | Med | Validate al_item_type trong resolver. |
| R7 | Code→Small Text gây data loss | Low | V.Low | Cả 2 đều là TEXT type. Chỉ update meta. |
| R8 | FB API thay đổi | Med | Low | Pin FB version trong requirements.txt. |
| R9 | BOM cũ quá nhiều Fixed rows → Dynamic conversion | Low | Low | Admin tự chọn convert. Tool AI-assisted suggestion. |
| R10 | Multi-tenant item khác company | Med | Low | Frappe Item global. v19: company-specific mapping. |

### 12.2 Edge Cases

```
CASE 1: Formula resolve item bị disabled
  → _item_exists() return False (filter disabled=0)
  → Skip formula, fall về fallback → log warning

CASE 2: Cả formula và fallback đều fail
  → frappe.throw("Không thể resolve item cho dòng {slug}")
  → BomOrchestrator dừng, UI hiển thị error dialog

CASE 3: Sales override item sai al_item_type
  → Validate trong DynamicItemResolver: check al_item_type match line_type
  → NHOM line chỉ nhận NHOM_PROFILE items

CASE 4: Panel Expansion + Dynamic Item
  → Item resolved 1 lần, tất cả panels dùng cùng item
  → pass2_build expand panels bình thường

CASE 5: Dynamic Item cho KINH line
  → KHÔNG hỗ trợ — KINH chọn qua Glass Selector
  → Validate: throw nếu KINH + Dynamic mode

CASE 6: item_condition_formula quá dài (>500 chars)
  → Warn tại validate; reject nếu >1000 chars
  → Admin nên dùng AL Calculation Rule LOOKUP thay IF chain

CASE 7: glass_thick_{prefix} chưa có khi evaluate formula
  → glass_thick inject luôn chạy TRƯỚC DynamicItemResolver (Bước 1 → Bước 2)
  → Nếu prefix không có trong glass_selections → dùng default_glass_master

CASE 8: Dynamic Item + show_condition cùng dòng
  → show_condition vẫn hoạt động bình thường (quyết định active/inactive)
  → Nếu show_condition=False → dòng inactive, DynamicItemResolver bỏ qua

CASE 9: Rule THRESHOLD — input_variable không có trong inputs_dict
  → flt(inputs_dict.get(var_name, 0)) = 0
  → Kết quả: so sánh với from=0, to=10.38 → khớp dòng đầu tiên
  → Log warning: "Input variable 'glass_thick_xyz' not found, defaulting to 0"

CASE 10: Rule LOOKUP — key variable không có trong inputs_dict
  → key = "" → row.key_1 = "" → khớp (empty match)
  → Nếu không có empty row → fallback về default_item
  → Không throw lỗi — để BOM vẫn tính được

CASE 11: Admin xóa Rule đang được dùng bởi BOM
  → AL Dynamic Item Rule không có "on delete cascade"
  → DynamicItemResolver: rule not found → log error → dùng fallback
  → Admin nên deprecate rule (is_active=0) thay vì xóa

CASE 12: Rule có item_code đã bị disabled
  → _item_exists() return False
  → Bỏ qua row đó → kiểm tra row tiếp theo → nếu không row nào khớp → fallback
  → Log warning khi item được reference nhưng disabled
```

---

## 13. ADVANCED UPGRADE

### 13.1 Performance Optimization

```python
# 1. CACHE FORMULA COMPILE
# ────────────────────────
# item_condition_formula compiled 1 lần, tái sử dụng
class CachingDynamicItemResolver(DynamicItemResolver):
    _formula_compile_cache: Dict[str, Any] = {}

    def _evaluate_via_formula_engine(self, formula, context, slug):
        if slug not in self._formula_compile_cache:
            from formula_builder.formula_utils import FormulaEngine
            self._formula_compile_cache[slug] = FormulaEngine().compile(formula)
        return self._formula_compile_cache[slug].evaluate(context)


# 2. DAG TOPOLOGY CACHE
# ─────────────────────
class DAGCache:
    _dag_cache: Dict[str, Any] = {}

    @classmethod
    def get_or_build(cls, profile_set_name, modified, formulas, inputs_dict):
        key = f"{profile_set_name}:{modified}"
        if key not in cls._dag_cache:
            from formula_builder.formula_utils import FormulaEngine
            cls._dag_cache[key] = FormulaEngine().build_dag(formulas, inputs_dict)
        return cls._dag_cache[key]


# 3. REDIS CACHE cho item metadata (TTL 5 phút)
def _get_item_metadata_redis(item_code):
    from frappe.utils.caching import redis_cache
    @redis_cache(ttl=300)
    def _load(item_code):
        return frappe.db.get_value("Item", item_code, ["al_kg_per_m", "al_item_type"])
    return _load(item_code)
```

### 13.2 AI Integration — Tầng 7

```python
# 1. AI GENERATE ITEM CONDITION FORMULA
def ai_generate_item_formula(description: str, available_items: List[Dict],
                              available_vars: List[str]) -> str:
    """Admin mô tả → AI sinh item_condition_formula."""
    prompt = f"""Generate FormulaEngine formula for item selection:
Description: {description}
Available items: {json.dumps(available_items, ensure_ascii=False)}
Available variables: {available_vars}
Return ONLY the formula string. Use IF(condition, "ITEM-CODE", fallback) syntax."""
    response = frappe.call_ai_api(prompt=prompt)
    validate_item_condition_formula(response.strip())
    return response.strip()


# 2. AI DETECT SAI CONFIG
def ai_validate_bom(bom_name: str) -> List[Dict]:
    """AI scan BOM → potential issues."""
    issues = []
    bom = frappe.get_doc("AL BOM", bom_name)
    profile_set = frappe.get_doc("AL Profile Set", bom.profile_set)
    for line in profile_set.al_lines:
        if line.item_selection_mode == "Dynamic" and not line.item_fallback:
            issues.append({"severity": "error", "line": line.slug,
                           "message": "Dynamic mode without item_fallback"})
    return issues


# 3. AI SUGGEST PK
def ai_suggest_pk(product_type: str, brand: str) -> List[str]:
    """Đề xuất phụ kiện từ pattern BOM tương tự."""
    similar = frappe.get_all("AL BOM", filters={"product_type": product_type},
                             fields=["pk_set"], limit=10)
    pk_freq: Dict[str, int] = {}
    for bom in similar:
        if bom.pk_set:
            for line in frappe.get_doc("AL PK Set", bom.pk_set).al_pk_lines:
                pk_freq[line.item_code] = pk_freq.get(line.item_code, 0) + 1
    return [item for item, _ in sorted(pk_freq.items(), key=lambda x: x[1], reverse=True)[:5]]
```

### 13.3 Platform Direction — Sau v18

```
v18 đạt được:
  ✓ 100% formula fields là Small Text
  ✓ Dynamic Item Selection — giảm 60-75% dòng BOM
  ✓ FormulaEngine là engine DUY NHẤT — không raw eval(), không Python code
  ✓ FB Variable Binding + DAG topology — resolve đúng thứ tự
  ✓ Config-driven 100% — admin tự cấu hình BOM
  ✓ AI-ready — explain() + structured config + Tầng 7 hooks
  ✓ Backward compatible — v17 data chạy nguyên

v19 roadmap:
  → AI-powered BOM Generator: mô tả sản phẩm → AI tạo Profile Set hoàn chỉnh
  → Multi-factory: 1 BOM template → nhiều factory với item mapping
  → Real-time pricing: giá nhôm/kính realtime → auto-inject
  → BOM Marketplace: chia sẻ Profile Set template
  → 3D Visualization: BOM config → 3D render

Platform thesis: "Manufacturing ERP = Low-code Platform + Domain DSL + FormulaEngine"
v18 là bước cuối cùng để đạt Zero-Dev-Required cho cấu hình BOM mới.
```

---

## APPENDIX A: Field Mapping v17 → v18

| DocType | fieldname | v17 Type | v18 Type | Ghi chú |
|---|---|---|---|---|
| AL Profile Line | show_condition | Code | Small Text | ★ #1 |
| AL Profile Line | qty_formula | Code | Small Text | ★ #2 |
| AL Profile Line | width_formula | Code | Small Text | ★ #3 |
| AL Profile Line | height_formula | Code | Small Text | ★ #4 |
| AL Profile Line | panel_count_formula | Code | Small Text | ★ #5 |
| AL Profile Line | qty_per_panel_formula | Code | Small Text | ★ #6 |
| AL PK Line | sl_formula | Code | Small Text | ★ #7 |
| AL Cost Template Line | calc_formula | Code | Small Text | ★ #8 |
| AL Calculation Rule | formula_expression | Code | Small Text | ★ #9 |
| AL Profile Line | item_selection_mode | — | Select (Fixed/Rule/Formula) | ★ MỚI (mở rộng 3 options) |
| AL Profile Line | item_rule | — | Link → AL Dynamic Item Rule | ★ MỚI (Rule mode) |
| AL Profile Line | item_condition_formula | — | Small Text | ★ MỚI (Formula mode) |
| AL Profile Line | item_fallback | — | Link → Item | ★ MỚI |
| AL PK Line | item_selection_mode | — | Select (Fixed/Rule/Formula) | ★ MỚI |
| AL PK Line | item_rule | — | Link → AL Dynamic Item Rule | ★ MỚI |
| AL PK Line | item_condition_formula | — | Small Text | ★ MỚI |
| AL PK Line | item_fallback | — | Link → Item | ★ MỚI |
| AL Cost Template | formula_set | — | Link → Formula Set | ★ MỚI (optional) |
| Quotation Item | al_sales_item_overrides | — | JSON | ★ MỚI |
| **★ AL Dynamic Item Rule** | **—** | **—** | **DocType mới** | **★ MỚI (Master)** |
| **★ AL Dynamic Item Threshold Row** | **—** | **—** | **DocType mới** | **★ MỚI (Child)** |
| **★ AL Dynamic Item Lookup Row** | **—** | **—** | **DocType mới** | **★ MỚI (Child)** |

**Tổng: 3 DocType mới + 9 field đổi + 8 field thêm = 20 thay đổi schema**

## APPENDIX B: Ví dụ — 3 Chế Độ Item Selection

### B.1 Cùng 1 bài toán "chọn nẹp kính theo độ dày" — 3 cách

#### Cách 1: FIXED (dễ nhất — giống v17, 3 dòng riêng biệt)

```
Dòng 60: Nẹp kính ≤10.38mm
  item_selection_mode: Fixed
  item_code: C3209-20
  show_condition: glass_thick_kinh_canh <= 10.38

Dòng 61: Nẹp kính 11-16mm
  item_selection_mode: Fixed
  item_code: C3210-20
  show_condition: glass_thick_kinh_canh > 10.38 and glass_thick_kinh_canh <= 16

Dòng 62: Nẹp kính >16mm
  item_selection_mode: Fixed
  item_code: C3211-20
  show_condition: glass_thick_kinh_canh > 16

→ 3 dòng cho 1 vị trí × 4 vị trí (đứng trái/phải, ngang trên/dưới) = 12 dòng
→ Dễ hiểu, ai cũng làm được
→ Nhược: nhiều dòng, thay đổi ngưỡng phải sửa từng dòng
```

#### Cách 2: RULE-BASED ★★★ KHUYẾN NGHỊ — 1 dòng, không code

```
Bước 1: Tạo AL Dynamic Item Rule (làm 1 lần):
  ┌──────────────────────────────────────────────┐
  │ Rule Code: NEP-KINH-THEO-DO-DAY             │
  │ Rule Type: THRESHOLD                         │
  │ Input Variable: glass_thick_kinh_canh        │
  │                                              │
  │ ┌──────┬───────┬────┬──────────────────┐    │
  │ │ From │ To    │ Op │ Item             │    │
  │ ├──────┼───────┼────┼──────────────────┤    │
  │ │ 0    │ 10.38 │ ≤  │ C3209-20         │    │
  │ │ 10.39│ 16.0  │ ≤  │ C3210-20         │    │
  │ │ 16.01│ 24.0  │ ≤  │ C3211-20         │    │
  │ │ 24.01│ 0     │ >  │ C3211-24         │    │
  │ └──────┴───────┴────┴──────────────────┘    │
  │ Default Item: C3209-20                       │
  └──────────────────────────────────────────────┘

Bước 2: Trong AL Profile Line — CHỈ 1 DÒNG:
  Dòng 60: Nẹp kính
    item_selection_mode: Rule
    item_rule: NEP-KINH-THEO-DO-DAY   ← chọn từ dropdown!
    item_fallback: C3209-20

→ 1 dòng cho 1 vị trí × 4 vị trí = 4 dòng (GIẢM 67%!)
→ Tạo rule 1 lần → dùng cho mọi BOM (CUA-DI, CUA-SO, VACH...)
→ Thêm ngưỡng mới (>24mm) = thêm 1 dòng trong rule → toàn bộ BOM tự cập nhật
→ Admin KHÔNG cần biết cú pháp IF
```

#### Cách 3: FORMULA — 1 dòng, linh hoạt nhất (power user)

```
Dòng 60: Nẹp kính (Dynamic by Formula)
  item_selection_mode: Formula
  item_condition_formula:
    IF(glass_thick_kinh_canh <= 10.38, "C3209-20",
    IF(glass_thick_kinh_canh <= 16, "C3210-20",
    IF(glass_thick_kinh_canh <= 24, "C3211-20", "C3211-24")))
  item_fallback: C3209-20

→ 1 dòng, linh hoạt nhất
→ Có thể dùng biến phức tạp:
    IF(AND(glass_thick > 16, do_day == '2.0mm'), "C3211-20", "C3210-14")
→ Dành cho kỹ thuật viên cao cấp
```

### B.2 Ví dụ LOOKUP: Tay nắm theo brand + màu

```
Bước 1: Tạo AL Dynamic Item Rule:
  Rule Code: TAY-NAM-THEO-BRAND-MAU
  Rule Type: LOOKUP
  Key 1 Variable: brand
  Key 2 Variable: mau_nhom

  ┌──────────┬──────────┬───────────────────┐
  │ brand    │ mau_nhom │ item_code         │
  ├──────────┼──────────┼───────────────────┤
  │ XF-NK    │ STD      │ TAY-NAM-XF55-STD  │
  │ XF-NK    │ DAK      │ TAY-NAM-XF55-DAK  │
  │ XF-NK    │ VG       │ TAY-NAM-XF55-VG   │
  │ XF-NK    │ INOX     │ TAY-NAM-XF55-INOX │
  │ ALUMIL   │ STD      │ TAY-NAM-ALU-STD   │
  │ ALUMIL   │ INOX     │ TAY-NAM-ALU-INOX  │
  └──────────┴──────────┴───────────────────┘
  Default Item: TAY-NAM-XF55-STD

Bước 2: Trong AL Profile Line:
  Dòng: Tay nắm
    item_selection_mode: Rule
    item_rule: TAY-NAM-THEO-BRAND-MAU
    item_fallback: TAY-NAM-XF55-STD

→ Sales chọn brand=ALUMIL, mau_nhom=INOX → tự động resolve ra TAY-NAM-ALU-INOX
→ Thêm brand mới = thêm 1 dòng trong rule
→ Tất cả BOM dùng chung 1 rule
```

### B.3 Tổng kết: Khi nào dùng chế độ nào?

| Tình huống | Chế độ | Lý do |
|---|---|---|
| Khung bao, cánh — item không bao giờ thay đổi | Fixed | Đơn giản nhất, không cần logic |
| Nẹp kính — thay đổi theo độ dày (ngưỡng số) | **Rule THRESHOLD** | Bảng trực quan, tái sử dụng |
| Tay nắm, bản lề — thay đổi theo brand/màu/hướng mở | **Rule LOOKUP** | Bảng key-value, tái sử dụng |
| Gioăng — thay đổi theo loại kính (cường lực/thường/hộp) | **Rule LOOKUP** | Dễ maintain, không code |
| Logic phức tạp: vừa theo độ dày vừa theo độ dày nhôm | Formula | Rule không đủ express |
| Cần gọi hàm custom (ví dụ: market_price()) | Formula | Chỉ Formula mới gọi được hàm |

## APPENDIX C: So sánh Draft v18 vs Final v18

| Vấn đề | Draft v1 | Final v2 |
|---|---|---|
| Số field Code → Small Text | 8 | **9** (+`formula_expression`) |
| DynamicItemResolver engine | Raw `eval()` + custom sandbox | **FormulaEngine.evaluate_single()** |
| FB Variable Binding | Không đề cập | **Tích hợp + 2 custom handlers** |
| Cost Template + Formula Set | Không đề cập | **formula_set field + CostAccumulator v2** |
| Batch DB query | Từng item một (N+1) | **Batch query + exists_cache** |
| Validate formula | Custom regex + token blacklist | **FormulaEngine.validate() + slug pattern** |
| VariableResolver | Chưa update | **v3 với resolve_bindings_with_deps()** |
| AL Calculation Rule | Không đổi | **formula_expression → Small Text** |
| Sales Override | Chỉ JSON field | **JSON field + UI spec (Phase 4)** |
| Migration cho FB bindings | Không có | **Patch 4: AL → FB auto-migrate** |

## APPENDIX D: Kế thừa Không Phá Vỡ từ v17

### 34 DocType v17 — Giữ nguyên, chỉ thêm fields

| STT | DocType | v17 | v18 |
|---|---|---|---|
| 1-16 | AL Variable Group → AL Rule Sequence Item | Giữ nguyên | Giữ nguyên |
| 17 | **AL Profile Line** | — | +3 fields (item_selection_mode, item_condition_formula, item_fallback); 6 fields Code→Small Text |
| 18 | AL Profile Set | Giữ nguyên | Giữ nguyên |
| 19-20 | AL PK Set, AL PK Line | — | PK Line: +3 fields, sl_formula Code→Small Text |
| 21-24 | AL BOM, AL Cost Template, Line, ConfigSnapshot | — | Cost Template: +formula_set; Line: calc_formula Code→Small Text |
| 25-34 | 10 Module DocType v17 | Giữ nguyên | Giữ nguyên |

### Engine — Giữ nguyên, cập nhật

| File | v17 | v18 |
|---|---|---|
| variable_resolver.py | v2 (priority-based) | v3 (FB DAG-topo + glass_thick) |
| dynamic_item_resolver.py | — | ★ MỚI |
| profile_interpreter.py | v2 (Fixed item only) | v2.1 (Dynamic mode check) |
| pk_resolver.py | v1 | v1 (hỗ trợ Dynamic PK) |
| cost_accumulator.py | v1 | v2 (+Formula Set) |
| orchestrator.py | 6 bước | 7 bước (+Dynamic Item) |
| snapshot_builder.py | v1 | v1 (+item_context) |
| rule_engine.py | v1 | v1 (không đổi) |
| module_registry.py | v1 | v1 (không đổi) |
| fb_handlers.py | v1 | v1 (không đổi) |

### Hooks & Scheduled Tasks — Không đổi

### 8 Ví dụ Kiểm chứng — PASS 100% với Fixed mode

### Module v17 (7 modules) — Không bị ảnh hưởng

---

## APPENDIX E: v17 REVIEW — Khuyến nghị đã Tích hợp

| # | Khuyến nghị REVIEW | Priority | Status v18 |
|---|---|---|---|
| 1 | Thay AL Variable Binding = FB Variable Binding | P0 | ✅ Tích hợp (QĐ-17, VariableResolver v3, Patch 4) |
| 2 | Tách Cost Template: Formula Set + UI | P1 | ✅ Optional (QĐ-19, CostAccumulator v2) |
| 3 | Dùng FlexibleFormulaEngine cho Cost | P2 | 🔲 Chưa (giữ legacy fallback) |
| 4 | Dùng DialogBuilder schema DSL | P3 | 🔲 v19 |
| 5 | CONSTANT/FORMULA/SEQUENCE → FB equivalent | P4 | ✅ Optional (QĐ-18, admin tự chọn) |
| 6 | Đăng ký 2 custom handlers (bom_variable, rule_engine_lookup) | P0 | ✅ Tích hợp (§6.1) |
| 7 | DAG topology thay priority tuần tự | P0 | ✅ Qua FB resolve_bindings_with_deps() |
| 8 | Giữ ProfileInterpreter 2-pass | — | ✅ Giữ nguyên (domain-specific) |
| 9 | Giữ show_condition → DAG branching | — | ✅ Giữ nguyên |
| 10 | Giữ glass_thick injection | — | ✅ Giữ nguyên |

### Code Reduction (so với v17 nếu fully adopt FB)

| Metric | v17 | v18 (post-migration) | Change |
|---|---|---|---|
| AL Variable Binding DocType | Active | Kept (data) / Logic → FB | — |
| Source types available | 5 | 12 | +140% |
| VariableResolver code | ~180 dòng | ~100 dòng | -44% |
| Rule Engine code | ~90 dòng | ~60 dòng | -33% |
| Cost Accumulator code | ~70 dòng | ~70 dòng | ±0 (thêm FS path) |
| New: DynamicItemResolver | — | ~150 dòng | +150 |
| New: fb_handlers.py | — | ~80 dòng | +80 |

---

*AlumGlass v18 Upgrade Specification — FULL & COMPREHENSIVE*
*Kế thừa: v11 → v13 → v14 → v15 → v16 → v17 → v18*
*Input: v17 FINAL (3049 dòng) + v17 REVIEW (812 dòng) + Draft v1 + Phản biện v2*
*"Zero Python in DB. FormulaEngine DUY NHẤT. Dynamic Item Selection. Config-driven 100%. Ready to implement."*
*Ngày: 2026-06-29*

## 8. BOM Version Control & Approval Workflow
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

## 9. ★ Sửa lỗi P0: Tồn kho Batch-màu

## VII. MODULE SẢN XUẤT (PRODUCTION & CUTTING) — cập nhật theo §IV

Giữ nguyên toàn bộ nội dung v19 §V (Nguyên tắc P-1, P-2; `AL Cutting Standard`; luồng Cutting Plan 6 bước; `AL Production Order Bridge`), chỉ thay đổi các điểm chạm tồn kho:

| Thành phần | Thay đổi |
|---|---|
| `AL Glass Cutting Plan Line` / `AL Aluminum Cutting Plan Line` | Trường `item_variant` → `item` (gốc) + `batch_no` (§IV.3) |
| Bước 6 (ghi nhận phế liệu/offcut) | Offcut > `min_offcut_reusable_mm` nhập kho phụ **cùng Item gốc**, Batch riêng đánh dấu `al_color` kế thừa từ batch đã cắt — offcut không tạo Item mới, chỉ tạo Batch mới trong kho phụ |
| Phiếu cắt in cho xưởng | Hiển thị rõ `màu (từ Batch)` + `dự án nguồn` trên phiếu để công nhân không nhầm lẫn giữa các lô màu đang cắt song song |

Toàn bộ phần còn lại (Cutting Standard, thuật toán tối ưu 1D/2D, quy trình review-confirm không tự động trừ kho) giữ nguyên nội dung v19.

---

## 10. Quy trình nghiệp vụ đầu-cuối

## 11. Phân quyền & Vai trò

## 12. AI First — Chiến lược toàn dự án

## 13. Ví dụ kiểm chứng (bắt buộc PASS trước go-live)

## 14. Risk Matrix & Edge Cases

## 15. Implementation Checklist & Migration





---

# PHẦN BỔ SUNG — CÁC THÀNH PHẦN CÒN THIẾU


Phần này tổng hợp các thành phần Orchestrator, Module nghiệp vụ, và Hướng dẫn sử dụng còn thiếu trong tài liệu chính.


---

## X. VARIABLERESOLVER v3

**Nhiệm vụ:** Xây `inputs_dict` đầy đủ trước khi ProfileInterpreter chạy.

**Quy trình:**
1. Gọi `resolve_bindings_with_deps()` (FB) → resolve theo DAG topology thay vì priority thủ công — vẫn tôn trọng thứ tự nguồn dữ liệu (Quotation Input trước, Computed sau).
2. Với mỗi dòng `line_type=KINH` trong Profile Set: lấy `glass_code` từ `al_glass_selections` (hoặc `default_glass_master`) → tra `AL Glass Master.total_thick_mm` → inject `glass_thick_{prefix}` vào `inputs_dict`.
3. Trả về `inputs_dict` hoàn chỉnh cho Tầng 4.5.

> `glass_thick_{prefix}` **luôn luôn** là bước cuối, sau mọi Binding khác — đảm bảo Tầng 4.5 (Dynamic Item Resolver) và ProfileInterpreter có đủ dữ liệu khi cần so sánh độ dày kính.

---

## XI. PROFILEINTERPRETER v2 — 2-PASS

### Pass 1 — Scan (`pass1_scan`)
Quét toàn bộ `al_lines`, không quan tâm thứ tự khai báo:
- Xây `variable_registry`: tập hợp mọi biến được tham chiếu trong `show_condition`/`qty_formula`/công thức khác.
- Với dòng KINH có `panel_count_formula`: tính `panel_counts[prefix]` = số panel thực tế (đánh giá qua FormulaEngine với `inputs_dict` hiện có — chỉ tham chiếu biến priority ≤ 40, tức Input/Computed đơn giản).

### Pass 2 — Build (`pass2_build`)
Với mỗi dòng theo `sort_order` (chỉ ảnh hưởng hiển thị, không ảnh hưởng DAG):
- **NHOM:** sinh `{slug}_active` (từ show_condition), `{slug}_qty` (từ qty_rule/qty_formula), `{slug}_kg`, `{slug}_dg` (đơn giá), `{slug}_tt` (thành tiền) → gom vào `bucket_acc[cost_bucket]`.
- **KINH:** với mỗi panel (1 → N từ `panel_counts`): sinh `{prefix}_{i}_W`, `{prefix}_{i}_H`, `{prefix}_{i}_m2`, `{prefix}_{i}_glass_thick_mm`, `{prefix}_{i}_dg`, `{prefix}_{i}_tt`. Sau khi hết mọi dòng KINH: sinh `max_glass_thick_mm = max(...)`.
- **VTP:** tương tự NHOM, `qty_formula` có thể tham chiếu `ALL_KINH_total_perimeter_m`, `max_glass_thick_mm`.
- **PK (nội tuyến):** tương tự, ưu tiên override từ `al_pk_overrides`.
- Trả `all_formulas` (list gửi vào FormulaEngine) + `bucket_acc` (dict cho CostAccumulator).

**Nguyên tắc bất biến:** Kết quả tính toán **không phụ thuộc thứ tự khai báo** `sort_order` trong Profile Set — chỉ phụ thuộc vào DAG mà FormulaEngine tự xây từ tên biến. Đây là điều kiện kiểm chứng bắt buộc trước go-live (§XXXVI).

---

## XII. PKRESOLVER

**Nhiệm vụ:** Xử lý `AL PK Set` + override từ Sales.

**Quy trình:**
1. Với mỗi `AL PK Line`: xác định `actual_item` = override (nếu có trong `al_pk_overrides` VÀ `allow_substitute=1` VÀ item thuộc `substitute_item_group`) hoặc `item_code` mặc định.
2. Nếu override không hợp lệ: bỏ qua, dùng mặc định, ghi `warnings[]` — không throw lỗi, Sales thấy toast cảnh báo nhẹ.
3. Sinh `pk_{n}_qty`, `pk_{n}_dg`, `pk_{n}_tt` → gom vào `bucket_acc['VL_PK']`.
4. Trả `formulas_pk`, `warnings[]`.

---

## XIII. DYNAMIC ITEM RESOLVER — 3 CHẾ ĐỘ (Tầng 4.5, Pre-Resolution Phase)

**Vị trí trong luồng:** chạy **sau** VariableResolver (đã có `inputs_dict` đầy đủ kể cả `glass_thick_*`), **trước** ProfileInterpreter pass2_build. Đây là "Option A: Pre-Resolution Phase" — không sửa FormulaEngine, giữ nguyên Tầng 3 (Nguyên tắc #16).

| Chế độ | Cơ chế | Ai dùng |
|---|---|---|
| **Fixed** | Bỏ qua — ProfileInterpreter tự đọc `item_code` như bình thường | Mọi người |
| **Rule** | Đọc `AL Dynamic Item Rule.current_version.rule_snapshot_json` (§VIII) → so khớp THRESHOLD/LOOKUP bằng phép so sánh trực tiếp, **không parse formula** | Kỹ thuật viên |
| **Formula** | `FormulaEngine.evaluate_single(item_condition_formula, inputs_dict)` — chỉ tham chiếu biến INPUT, không tham chiếu biến slug do DAG tính (validate khi lưu, reject nếu vi phạm) | Kỹ thuật cao cấp |

**Thứ tự ưu tiên khi resolve item cho 1 dòng:**
```
Sales override (al_sales_item_overrides[slug], nếu al_item_type khớp line_type)
  > Kết quả Dynamic (Rule/Formula mode)
  > item_fallback
  > lỗi (throw, dừng BomOrchestrator, UI hiển thị error dialog)
```

**Edge cases bắt buộc xử lý** (tổng hợp từ thực tế vận hành):
| Case | Xử lý |
|---|---|
| Formula/Rule trả về item bị disabled | Bỏ qua kết quả, dùng `item_fallback`, log warning |
| Cả formula/rule và fallback đều fail | `throw` — dừng, không tính giá sai |
| Sales override sai `al_item_type` (NHOM→KINH) | Validate, reject, dùng kết quả gốc |
| Dynamic mode cho dòng KINH | **Không hỗ trợ** — validate khi lưu Profile Line, throw nếu vi phạm |
| `item_condition_formula` quá dài (>500 ký tự) | Warn khi lưu; reject nếu >1000 ký tự — khuyến nghị chuyển sang Rule mode |
| `input_variable`/`lookup_key` không có trong `inputs_dict` | THRESHOLD: default về 0 (so khớp dòng đầu) + log warning. LOOKUP: key rỗng, khớp dòng rỗng nếu có, ngược lại fallback |
| Admin xóa Rule đang dùng | Không cascade delete — resolver: rule not found → fallback → log error. Khuyến nghị deprecate (`is_active=0`) thay vì xóa |
| Panel Expansion + Dynamic Item | Item resolve 1 lần, mọi panel dùng chung |

**Hiệu năng:** batch DB lookup cho item metadata, cache theo `(item_code)` TTL ngắn (Redis, 5 phút) — mục tiêu <200ms cho 100 dòng Dynamic.

---

## XIV. COSTACCUMULATOR v2

**Nhiệm vụ:** Từ `bucket_acc` (do ProfileInterpreter/PkResolver gom) + `AL Cost Template` → sinh formula cấp Bucket và cấp Cost Template.

**Quy trình:**
1. Với mỗi `bucket_code` trong `bucket_acc`: sinh formula `{bucket_code} = var1 + var2 + ...`.
2. Nếu `AL Cost Template.formula_set` có giá trị (★v18, optional): dùng Formula Set của `formula_builder` sinh formula cấp template. Nếu lỗi (Formula Set không tồn tại/lỗi runtime): `log_error` mức CRITICAL + **cờ cảnh báo UI** "Cost Template đang dùng fallback mode" (vá gap từ REVIEW cũ) + notify Admin nếu fallback >3 lần/ngày → fallback về `AL Cost Template Line`.
3. Nếu không có `formula_set`: dùng trực tiếp `AL Cost Template Line.calc_formula`.
4. Trả về toàn bộ `formulas` gửi vào `FormulaEngine.calculate()` — **đây là lần gọi FormulaEngine DUY NHẤT trong toàn bộ luồng tính giá.**

---

## XV. BOMORCHESTRATOR — QUY TRÌNH 9 BƯỚC (v19)

| Bước | Component | Chi tiết |
|---|---|---|
| 1 | VariableResolver.resolve() | `inputs_dict` đầy đủ + `glass_thick_{prefix}` |
| 2 ★v18 | DynamicItemResolver.resolve() | Pre-resolve item cho dòng Dynamic → inject `{slug}_item_code`, `{slug}_kg_per_m`, `{slug}_price` vào `inputs_dict` |
| 3 | ProfileInterpreter.pass1_scan() | `variable_registry`, `panel_counts` |
| 4 | ProfileInterpreter.pass2_build() | `all_formulas` (NHOM+KINH+VTP+PK_inline), `bucket_acc` |
| 5 | PkResolver.build_formulas() | `formulas_pk`, `warnings[]` |
| 6 | CostAccumulator.build_bucket_and_template_formulas() | `formulas_bucket`, `formulas_cost_template` |
| 7 | **FormulaEngine.calculate() + SnapshotBuilder.persist()** | **DUY NHẤT 1 lần calculate()** — ghi `ConfigSnapshot` |
| Hook A | DiscountStack.apply() | `al_discount_pct`, `al_gia_thuong_mai`, approval check |
| Hook B | BOMVersionManager.link_version() | Gắn `al_bom_version` |
| Hook C | CostVarianceAnalyzer.register() | Đăng ký reference so sánh sau |
| Hook D | NotificationEngine.check_alerts() | PRICE_CHANGE/LOW_STOCK/VARIANCE_ALERT/... |
| **Hook E ★v19** | *(Trigger: `Sales Order.on_submit`, không phải lúc tính giá)* Field Ops bootstrap | Tạo `AL Installation Order` (Draft) + `AL Milestone Billing Plan` (từ template mặc định) |
| **Hook F ★v19** | *(Trigger: `Sales Order.on_submit`)* Production bootstrap | Đăng ký reference vào pool chờ `AL Aluminum/Glass Cutting Plan` |

**Nguyên tắc Module Hook (bất biến từ v17, áp dụng cho mọi hook kể cả E/F):**
- BomOrchestrator KHÔNG import module Tầng 6 — mỗi module tự đăng ký hook khi app load.
- Hook thất bại → log error, không chặn kết quả tính giá trả về Sales.
- Hooks A→D chạy tuần tự theo thứ tự đăng ký, timeout 5 giây/hook.
- Hooks E/F chạy độc lập trên event `Sales Order.on_submit`, không phụ thuộc A→D.

---
---

# PHẦN E — TẦNG 5: PRESENTATION

## XVI. BOM DIALOG & UI FLOW

### 16.1 Cấu trúc BOM Dialog (khi Sales tạo/sửa Quotation Item)

```
[Kích thước]        al_W_mm, al_H_mm, qty
[Thông số kỹ thuật]  sinh từ AL Variable Set theo sort_order + depends_on
[Loại kính]          1 khối chọn/panel cho mỗi dòng line_type=KINH
                      (Grid N ô nếu panel_glass_override_allowed=1)
[Màu nhôm]           al_mau_nhom
[Phụ kiện]           từ AL PK Set — cho phép substitute nếu allow_substitute=1
[Dynamic Item Preview ★v18] hiển thị item đã resolve cho dòng Rule/Formula,
                      kèm nút "Sales Override" nếu được phép
[Cost Template]      al_cost_template_override (mặc định = BOM.default_cost_template)
[BOM Version Badge]  "Phiên bản BOM: v3 (published 15/06)" + link Diff
[Rule Version Badge ★v19] "Nẹp kính rule v2 (published 20/06)" — hiển thị khi dòng dùng Rule mode
[Discount Section]   nếu có Discount Rule applicable
[Approval Status]    badge nếu al_approval_status=PENDING
[Cost Variance Indicator] nếu có Purchase Invoice liên quan
```

### 16.2 API Endpoints (đặt tên method, không phải code)

| method | Mô tả |
|---|---|
| `aluglass.engine.orchestrator.get_bom_dialog_config` | Config Dialog: KINH lines, PK lines, Variable Set |
| `aluglass.engine.orchestrator.calculate_quotation_item` | Chạy BomOrchestrator 9 bước, ghi field, trả kết quả |
| `aluglass.engine.orchestrator.get_explain_tree` | `explain()` cho formula cụ thể |
| `aluglass.modules.version.get_bom_version_info` / `compare_versions` | BOM Version info + Diff |
| `aluglass.modules.rule_version.get_rule_version_info` / `compare_rule_versions` ★v19 | Tương tự cho Dynamic Item Rule |
| `aluglass.modules.discount.get_applicable_discounts` / `apply_manual_discount` | |
| `aluglass.modules.approval.approve_discount` / `reject_discount` / `approve_rule_version` ★v19 | |
| `aluglass.modules.mrp.create_material_plan` / `get_plan_summary` | |
| `aluglass.modules.analytics.get_sales_kpi` / `get_dashboard_data` | |
| `aluglass.modules.production.create_cutting_plan` / `get_cutting_optimization` ★v19 | |
| `aluglass.modules.installation.create_order` / `record_progress` / `get_order_status` ★v19 | |
| `aluglass.modules.billing.check_milestone_ready` / `get_billing_status` ★v19 | |
| `aluglass.modules.financial.get_project_profitability` / `explain_variance` ★v19 | |

### 16.3 Mobile UI riêng cho Đội Thi Công ★v19
Giao diện tối giản (Frappe mobile hoặc PWA riêng): danh sách `AL Installation Order` được giao → chọn hạng mục → nhập % hoàn thành + chụp ảnh → Submit (tạo record `AL Installation Progress` mới, append-only, không sửa được sau khi gửi).

---
---

# PHẦN F — TẦNG 6: MODULE NGHIỆP VỤ

## XVII. BOM VERSION CONTROL

### 17.1 Vòng đời (giống hệt pattern dùng lại cho Rule Version §VIII)
Draft → Pending Approval → Published → Deprecated; Rejected → Draft.

### 17.2 AL BOM Version — trường
`bom` (Link), `version_number` (Int), `status` (Select), `published_on/by`, `profile_set_snapshot` (JSON), `variable_set_snapshot` (JSON), `pk_set_snapshot` (JSON), `cost_template_snapshot` (JSON), `snapshot_hash` (Data), `change_summary`, `approved_by`, `is_rollback_of` (Link, self), `al_change_logs` (Table).

### 17.3 AL BOM Change Log (Child, dùng chung cho BOM & Rule version — thêm field `change_target_type`)
`change_type` (Select: FIELD_CHANGE/LINE_ADDED/LINE_REMOVED/LINE_MODIFIED/FORMULA_CHANGED/PRICE_CHANGED/ROLLBACK), `changed_by`, `changed_on`, `target_doctype`, `target_record`, `field_name`, `old_value`, `new_value`, `impact_estimate` (LOW/MEDIUM/HIGH), **`change_target_type` (Select: BOM/RULE ★v19)**.

### 17.4 Diff Tool
`compare_versions(ver_a, ver_b)` → `{added_lines, removed_lines, modified_lines, formula_changes, price_changes, summary}`.

### 17.5 Rollback
Tạo version mới (`version_number = max+1`, `is_rollback_of = target`) từ snapshot cũ — **không xóa version nào**. Ghi Change Log `change_type=ROLLBACK`. Notify Kỹ Thuật.

---

## XVIII. APPROVAL WORKFLOW

### 18.1 Ba loại Approval (mở rộng từ 2 loại v17)
| Loại | Trigger | Approver | Timeout | Quá hạn |
|---|---|---|---|---|
| BOM Version Approval | `requires_approval_for_new_version=1` + Publish | Admin (escalate Director) | 48h | Escalate + email nhắc |
| Discount Approval | `al_discount_pct > approval_threshold_pct` | Admin | 24h | Notify; Sales không submit được |
| **Rule Version Approval ★v19** | `AL Dynamic Item Rule.requires_approval_for_new_version=1` + Publish | Director | 48h | Escalate + email nhắc |

### 18.2 Luồng Discount Approval
1. Sales tính giá, discount > threshold → `al_approval_status=PENDING`, khóa Quotation Item.
2. System tạo Notification + email cho Admin.
3. Admin Approve/Reject.
4. Approved → mở khóa; Rejected → notify Sales kèm `al_approval_note`.

### 18.3 Hook `before_submit` Quotation
Chặn Submit nếu còn dòng `al_approval_status=PENDING`.

### 18.4 Nguyên tắc phân quyền Approval
Approver PHẢI khác Requester (validate trước khi approve); log audit khi phát hiện self-approve.

---

## XIX. AL DISCOUNT RULE

### 19.1 5 loại rule_type
CUSTOMER_TIER / PROJECT / VOLUME (dùng `AL Discount Rule Line` tier) / SEASONAL / MANUAL.

### 19.2 Stack Resolution
| Trường hợp | Kết quả |
|---|---|
| 1 rule match | Áp `discount_pct` |
| Nhiều rule, tất cả `stackable=No` | Lấy `priority` thấp nhất |
| Có rule `stackable=Yes` | Cộng dồn stackable + 1 non-stackable ưu tiên cao nhất |
| Tổng > `max_total_discount_pct` | Cap tại ngưỡng, cảnh báo |
| MANUAL thêm vào | Cộng vào stack; vượt threshold → approval |

`GIA_BAN_THUONG_MAI = GIA_BAN × (1 - discount_pct/100)` — tính **sau** FormulaEngine, không vào DAG (Nguyên tắc kiến trúc: tách biệt "giá kỹ thuật" và "giá thương mại").

---

## XX. MATERIAL PLANNING (MRP LITE)

### 20.1 Luồng
Admin chọn Quotation/SO pool → `MRPAggregator.aggregate()` đọc **ConfigSnapshot** (không đọc lại Profile Set hiện tại — đảm bảo khớp giá đã báo khách) → `AL Material Plan Line` → Admin review/điều chỉnh → Confirm → (tùy chọn) Generate Purchase Order theo supplier mặc định của từng item.

### 20.2 Trạng thái
Draft → Confirmed → Purchased.

---

## XXI. COST VARIANCE ANALYSIS (VẬT TƯ)

### 21.1 Trigger
`Purchase Invoice.on_submit` → với mỗi item → tìm Quotation Item liên quan (trong 90 ngày trước posting_date, dùng snapshot) → tạo `AL Cost Variance` (check unique `quotation_item + purchase_invoice + item_code` tránh trùng).

### 21.2 Phân loại
| variance_pct | status | Hành động |
|---|---|---|
| < -5% | FAVORABLE | Ghi chú |
| -5% đến 5% | NORMAL | Không action |
| 5-15% | CAUTION | Email Daily Digest |
| > 15% | ALERT | Realtime notification |

---

## XXII. NOTIFICATION & ALERT ENGINE

### 22.1 Alert Type
PRICE_CHANGE, LOW_STOCK, BOM_EXPIRY, VARIANCE_ALERT, APPROVAL_PENDING, DISCOUNT_EXCEEDED, **MARGIN_DRIFT ★v19**, **INSTALLATION_DELAY ★v19**.

### 22.2 Channel
FRAPPE_NOTIFICATION (bell icon + `publish_realtime`), EMAIL (`frappe.sendmail`), BOTH.

### 22.3 Scheduled Jobs
| Job | Tần suất |
|---|---|
| update_sales_kpi | Daily 1:00 |
| check_price_change_alerts | Daily 9:00 |
| check_low_stock_alerts | Daily 8:00 |
| generate_daily_digest | Daily 19:00 |
| deprecate_old_bom_versions | Weekly |
| **update_project_profitability_snapshot ★v19** | **Weekly + event-driven** |
| **check_margin_drift_alerts ★v19** | **Daily** |
| **check_installation_delay ★v19** | **Daily** |

---

## XXIII. SALES ANALYTICS

`AL Sales KPI`: `sales_user`, `kpi_period`, `period_label`, `target_amount/actual_amount`, `target_quotations/actual_quotations`, `conversion_rate_target/actual`, `avg_margin_target_pct/actual_pct`, `avg_discount_pct`, `last_calculated_on`. Cập nhật qua scheduled job `update_sales_kpi`, tính từ Quotation/SO Submitted của user trong kỳ.

---

## XXIV. REPORTING & DASHBOARD

### 24.1 Danh sách Report (mở rộng)
AL Quotation Summary · AL BOM Price Analysis · AL Sales Pipeline · AL Material Cost Variance · AL Material Requirements · AL BOM Version History · AL Discount Utilization · AL Sales KPI Dashboard · AL Glass Consumption · AL Cost Variance Alert · **AL Rule Version History ★v19** · **AL Cutting Efficiency ★v19** (% phế liệu theo kỳ) · **AL Installation Progress Report ★v19** · **AL Project Profitability Dashboard ★v19** · **AL Margin Drift Alert ★v19**.

### 24.2 Dashboard theo vai trò
Admin / Sales / Kỹ Thuật (đã có ở v17) + **Director Dashboard ★v19** (Project Profitability, Margin Drift Alert, Installation Progress toàn công ty) + **Sản Xuất Dashboard ★v19** (Cutting Plan pending, hiệu suất cắt) + **Quản lý Thi công Dashboard ★v19** (Installation Order theo trạng thái, đội thi công đang bận/rảnh).

---

## XXV. MODULE SẢN XUẤT (CUTTING & PRODUCTION)

### 25.1 Nguyên tắc riêng
> **P-1:** Kích thước cắt = phép biến đổi từ kích thước tính giá (ConfigSnapshot) qua công thức khai báo trong `AL Cutting Standard.cutting_tolerance_formula` (qua FormulaEngine, Nguyên tắc #11) — không hardcode.
> **P-2:** Cutting Plan là đề xuất tối ưu, người phụ trách luôn review trước khi Confirm (không tự động trừ kho).

### 25.2 AL Aluminum Cutting Plan (Master)
`plan_name`, `plan_date`, `status` (Draft/Confirmed/Cut Done), `source_so_list` (JSON), `al_plan_lines` (Table), `total_waste_pct` (computed).

**AL Aluminum Cutting Plan Line (Child):** `profile_item_code`, `stock_bar_length_mm`, `segments_json` (danh sách đoạn cắt từ thuật toán 1D bin packing), `waste_length_mm`, `waste_pct`, `reusable_offcut` (Check).

### 25.3 AL Glass Cutting Plan (Master) — bài toán nesting 2D
`plan_name`, `plan_date`, `status`, `jumbo_sheet_ref` (Link → AL Cutting Standard), `al_plan_lines` (Table).

**AL Glass Cutting Plan Line (Child):** `glass_master`, `panel_layout_json` (tọa độ đặt tấm trên jumbo sheet), `width_mm`, `height_mm`, `qty`, `waste_pct`.

### 25.4 AL Glass Cut Order / AL Glass Cut Line (chính thức hóa từ Phase 3 v17)
**AL Glass Cut Order:** `sales_order` (Link), `status` (Pending/In Cutting/Cut Done/Installed), `al_glass_cut_lines` (Table).
**AL Glass Cut Line:** `glass_master`, `width_mm`, `height_mm` (từ ConfigSnapshot — không tính lại), `qty`, `area_m2`, `item_variant`, `batch_no`, `stock_entry`.

### 25.5 AL Production Order Bridge (tùy chọn — công ty quy mô lớn)
`sales_order`, `work_order` (Link → ERPNext Work Order), `sync_status`, `production_stage` (Cutting/Assembly/QC/Ready to Install).

### 25.6 Luồng
| Bước | Actor | Hành động |
|---|---|---|
| 1 | Sản xuất | Chọn SO pool cần cắt → tạo Cutting Plan (Nhôm/Kính) |
| 2 | System | Đọc ConfigSnapshot → danh sách đoạn/tấm cần cắt |
| 3 | System (optimization/AI §XXIX) | Đề xuất phương án cắt tối ưu, giảm phế liệu |
| 4 | Sản xuất | Review, điều chỉnh (ưu tiên offcut tồn kho) |
| 5 | Sản xuất | Confirm → in phiếu cắt → tạo/cập nhật Cut Order |
| 6 | System | Phế liệu > `min_offcut_reusable_mm` → nhập kho phụ (Item Variant riêng) |
| 7 | Kho | Stock Entry xuất kho theo Cut Order sau khi cắt xong |

---

## XXVII. MODULE THANH QUYẾT TOÁN (MILESTONE BILLING)

### 27.1 Nguyên tắc S-1
Tận dụng `Payment Schedule` sẵn có của ERPNext — module này chỉ thêm lớp kiểm soát không cho xuất hóa đơn vượt tiến độ nghiệm thu.

### 27.2 AL Milestone Billing Plan (Master)
`sales_order` (Link, reqd), `total_contract_value`, `al_milestone_lines` (Table), `retention_pct` (giữ lại bảo hành, 5-10%), `retention_release_condition` (Small Text).

### 27.3 AL Milestone Billing Line (Child)
`milestone_name` (vd "Tạm ứng 30%", "Hoàn thành 70%", "Nghiệm thu bàn giao"), `billing_pct`, `trigger_type` (MANUAL/INSTALLATION_PROGRESS_PCT/DATE), `trigger_value`, `status` (Not Ready/Ready to Bill/Invoiced/Paid), `sales_invoice` (Link).

### 27.4 Luồng
| Bước | Actor | Hành động |
|---|---|---|
| 1 | (Hook, sau khi `AL Installation Progress` save) | Kiểm tra `cumulative_pct` vs `trigger_value` các dòng `Not Ready` |
| 2 | System | Đạt ngưỡng → `Ready to Bill`, notify Kế toán |
| 3 | Kế toán | Xuất Sales Invoice đúng `billing_pct` |
| 4 | System | **Chặn** nếu tổng % đã invoice > tổng % tiến độ đã nghiệm thu (trừ dòng `MANUAL`/`DATE`) |
| 5 | Kế toán | Cuối dự án: xuất hóa đơn giữ lại bảo hành theo `retention_release_condition` |

---

## XXVIII. MODULE KẾ TOÁN LÃI LỖ THEO CÔNG TRÌNH (PROJECT PROFITABILITY)

### 28.1 AL Project Financial Config
Đã đặc tả §4.22.

### 28.2 AL Labor Cost Variance (Master)
`installation_order` (Link), `planned_cost` (từ `AL Installation Order Line.planned_nc_ld_cost`, immutable), `actual_cost` (tổng từ `AL Installation Cost Actual`), `variance_pct` (computed), `variance_status` (NORMAL/CAUTION/ALERT — dùng chung ngưỡng 5%/15% như Cost Variance vật tư).

### 28.3 AL Project Profitability Snapshot (Master, immutable)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| project / sales_order | Link | |
| snapshot_date | Datetime | |
| revenue_recognized | Currency | Tổng SI đã submit |
| material_cost_quoted | Currency | GIA_THANH từ ConfigSnapshot gốc |
| material_cost_actual | Currency | Từ Purchase Invoice thực tế |
| labor_install_cost_actual | Currency | Từ `AL Installation Cost Actual` |
| warranty_cost_to_date | Currency | Từ `AL Warranty Claim.repair_cost` |
| overhead_allocated | Currency | Theo `AL Project Financial Config` |
| gross_profit | Currency (computed) | revenue − material_actual − labor_actual − warranty − overhead |
| gross_margin_pct | Float (computed) | |
| **margin_drift_vs_quoted** | **Float (computed)** | **So với margin đã báo giá ban đầu — con số quan trọng nhất cho Director** |

### 28.4 Trigger tạo Snapshot
Scheduled weekly cho mọi Project đang mở · On-demand (nút "Recalculate") · Event-driven khi SI/PI/Installation Cost Actual mới submit.

### 28.5 explain_variance() — cây giải thích tầng nghiệp vụ
Trả breakdown: bao nhiêu % lệch margin đến từ vật tư / nhân công / bảo hành — cùng triết lý "cây giải thích" như `explain()` của FormulaEngine nhưng vận hành ở Tầng 6E, không phải Tầng 3.

### 28.6 Báo cáo
AL Project Profitability Dashboard (Director/Admin/Kế toán) · AL Margin Drift Alert (Director, realtime khi `margin_drift_vs_quoted` vượt ngưỡng cấu hình trong `AL Project Financial Config`).

---
---

# PHẦN G — TẦNG 7: AI

## VII. AL CALCULATION RULE — ĐẦY ĐỦ

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ unique | |
| rule_name | Data | ✓ | |
| rule_type | Select | ✓ | CONSTANT / FORMULA / THRESHOLD / LOOKUP / SEQUENCE |
| description | Text | | |
| is_active | Check (default 1) | | |
| constant_value | Data | (CONSTANT) | |
| formula_expression | **Small Text** *(★v18: đổi từ Code)* | (FORMULA) | |
| threshold_input_var | Data | (THRESHOLD) | |
| threshold_rows | Table → AL Rule Threshold Row | (THRESHOLD) | |
| lookup_key_1_var / lookup_key_2_var | Data | (LOOKUP) | |
| lookup_rows | Table → AL Rule Lookup Row | (LOOKUP) | |
| lookup_default | Data | (LOOKUP) | |
| sequence_items | Table → AL Rule Sequence Item | (SEQUENCE) | |

**AL Rule Threshold Row:** `from_value` (Float), `to_value` (Float, 0=không giới hạn), `result_value` (Data).
**AL Rule Lookup Row:** `key_1/key_2/key_3` (Data), `result_value` (Data).
**AL Rule Sequence Item:** `rule` (Link), `sort_order` (Int).

**Định hướng migrate (Nguyên tắc #18):** THRESHOLD/LOOKUP giữ nguyên vĩnh viễn (table-based UX không có FB equivalent tương đương về mặt trải nghiệm người dùng). CONSTANT/FORMULA có thể migrate sang Formula Global Variable của `formula_builder` khi Admin chủ động chọn — không bắt buộc, không xóa rule_type nào.

---

## VIII. AL DYNAMIC ITEM RULE — CÓ VERSIONING (VÁ GAP P0)

### 8.1 AL Dynamic Item Rule (Master)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ unique | `NEP-KINH-THEO-DO-DAY`, `TAY-NAM-THEO-BRAND-MAU` |
| rule_name | Data | ✓ | |
| rule_type | Select | ✓ | THRESHOLD / LOOKUP |
| input_variable | Data | (THRESHOLD) | vd `glass_thick_kinh_canh`, `max_glass_thick_mm` |
| threshold_rows | Table → AL Dynamic Item Threshold Row | (THRESHOLD, **đang soạn thảo — chưa publish**) | |
| lookup_key_1_var / lookup_key_2_var | Data | (LOOKUP) | |
| lookup_rows | Table → AL Dynamic Item Lookup Row | (LOOKUP, **đang soạn thảo**) | |
| default_item | Link → Item | ✓ | Fallback nếu không khớp |
| is_active | Check (default 1) | | |
| description | Small Text | | |
| **current_version** | **Link → AL Dynamic Item Rule Version** | | **★ Version đang Published — dùng khi resolve runtime** |
| **requires_approval_for_new_version** | **Check** | | **★ Nếu bật → publish version mới cần Director duyệt** |
| **total_versions** | **Int (read-only)** | | ★ |

> **Điểm mấu chốt:** `threshold_rows`/`lookup_rows` trên chính DocType `AL Dynamic Item Rule` là **vùng soạn thảo (working copy)** — Kỹ thuật viên sửa thoải mái ở đây. **DynamicItemResolver KHÔNG BAO GIỜ đọc trực tiếp từ đây tại runtime** — nó luôn đọc từ `current_version.rule_snapshot_json` (bất biến). Đây là điểm khác biệt sống còn so với thiết kế v18 gốc.

### 8.2 AL Dynamic Item Rule Version (Master — MỚI, immutable)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule | Link → AL Dynamic Item Rule | ✓ | |
| version_number | Int | ✓ | Tự tăng |
| status | Select | ✓ | Draft / Pending Approval / Published / Deprecated / Rejected |
| rule_snapshot_json | Long Text | ✓ | Full JSON: rule_type, threshold_rows/lookup_rows, default_item tại thời điểm publish |
| snapshot_hash | Data | ✓ | SHA-256 |
| change_summary | Small Text | | |
| is_rollback_of | Link → AL Dynamic Item Rule Version | | |
| published_on / published_by | Datetime / Link User | | |
| approved_by | Link → User | | |

### 8.3 AL Dynamic Item Threshold Row / AL Dynamic Item Lookup Row (Child — working copy)

**Threshold Row:** `from_value` (Float), `to_value` (Float), `operator` (Select: ≤/</≥/>/=), `item_code` (Link → Item, reqd), `note` (Data).
**Lookup Row:** `key_1` (Data), `key_2` (Data, optional), `item_code` (Link → Item, reqd), `note` (Data).

### 8.4 Vòng đời Version (giống hệt AL BOM Version để tái dùng pattern)

| Trạng thái | Chuyển sang |
|---|---|
| Draft | Pending Approval (nếu `requires_approval_for_new_version=1`) hoặc Published thẳng |
| Pending Approval | Published / Rejected |
| Published | Deprecated (khi có version mới Published) |
| Deprecated | — (giữ vĩnh viễn để BOM cũ tham chiếu) |
| Rejected | quay về Draft |

### 8.5 Quy trình sửa Rule

| Bước | Actor | Hành động |
|---|---|---|
| 1 | Kỹ thuật viên | Sửa `threshold_rows`/`lookup_rows` trên `AL Dynamic Item Rule` (working copy) |
| 2 | Kỹ thuật viên | Nhấn "Publish Version" |
| 3 | System | Snapshot toàn bộ → tạo `AL Dynamic Item Rule Version` mới, tính `snapshot_hash` |
| 4 | System | Nếu `requires_approval_for_new_version=1` → status=Pending Approval → dùng **Approval Workflow §XVIII** với `approval_target_type=RULE_VERSION` |
| 5 | Admin | Sau Published: chọn "Áp dụng cho BOM mới từ nay" (mặc định, chỉ update `current_version`) hoặc **"Áp dụng hồi tố"** — hiển thị Diff Tool (tái dùng cơ chế `compare_versions()` của BOM Version, áp cho Rule) liệt kê BOM/Quotation đang mở bị ảnh hưởng |
| 6 | System | Version cũ → Deprecated; ghi `AL BOM Change Log` với `target_doctype=AL Dynamic Item Rule` |

### 8.6 Hành vi DynamicItemResolver (không đổi cấu trúc, chỉ đổi nguồn đọc)

Tầng 4.5 (§XIII) khi gặp `item_selection_mode=Rule`:
1. Lấy `AL Profile Line.item_rule` → `AL Dynamic Item Rule.current_version`
2. Parse `rule_snapshot_json` (không đọc `threshold_rows`/`lookup_rows` sống)
3. So khớp `input_variable`/`lookup_key` với `inputs_dict` → trả `item_code`
4. Ghi `rule_version_ids[rule_code] = version_name` vào `ConfigSnapshot` (§XXX)

---

## IX. FORMULA VARIABLE BINDING — TÍCH HỢP FB

VariableResolver v3 (§X) gọi `formula_builder.api.variable_resolver.resolve_bindings_with_deps()` thay vì tự resolve theo `priority` thủ công. Hai custom handler cần đăng ký vào `data_source_registry` của `formula_builder`:

| Handler | Nguồn dữ liệu | Thay thế cho |
|---|---|---|
| `bom_variable` | Đọc từ `AL Variable Set`/`al_bom_vars` | AL Variable Binding source_type=`BOM Variable` |
| `rule_engine_lookup` | Gọi `AL Calculation Rule` (LOOKUP/THRESHOLD) | AL Variable Binding source_type=`Rule Engine Result` |

`AL Variable Binding` DocType **giữ nguyên, không xóa** (Nguyên tắc #17) — dữ liệu cũ vẫn còn, chỉ đổi đường resolve. Migration script tạo Formula Variable Binding tương ứng cho mỗi `AL Variable Binding` hiện có.

---
---

# PHẦN D — TẦNG 4-4.5: ORCHESTRATION

## AL AI Interaction Log (Schema chi tiết)


Đây là DocType mới v21, tách biệt khỏi AL AI Suggestion Log.


| fieldname | fieldtype | reqd | Mô tả |

|---|---|---|---|

| interaction_type | Select | ✓ | RAG_QUERY / VOICE_INPUT / IMAGE_ANALYSIS |

| input_text | Text | | Câu hỏi/input của người dùng (tiếng Việt có dấu) |

| output_text | Long Text | | Phản hồi từ AI |

| context_reference | Dynamic Link | | Tài liệu / DocType liên quan |

| token_count | Int | | Số token tiêu thụ (phục vụ theo dõi chi phí) |

| model_used | Data | | Tên model AI đã dùng (GPT-4, Claude 3.5...) |

| user | Link → User | ✓ | Người dùng thực hiện tương tác |

| timestamp | Datetime | ✓ | Thời điểm tương tác |

| feedback_rating | Int | | Đánh giá của người dùng (1-5 sao) |


---

## Hướng dẫn sử dụng (User Guide) — dành cho người không code


### 1. Cách Kỹ thuật viên tạo AL Dynamic Item Rule bằng UI


**Mục đích:** Tạo luật tự động chọn Item dựa trên điều kiện, không cần viết code.


**Ví dụ thực tế:** "Với mỗi loại cửa, nếu kính dày ≤10.38mm thì dùng nẹp C3209, nếu dày 11-16mm thì dùng nẹp C3210, nếu >16mm thì dùng nẹp C3211"


**Các bước thực hiện:**

1. Vào menu: **AL Dynamic Item Rule → New**

2. Nhập `rule_code`: `NEP-KINH-THEO-DO-DAY` (mã tự đặt, không trùng với rule khác)

3. Nhập `rule_name`: "Nẹp kính theo độ dày kính"

4. Chọn `rule_type`: **THRESHOLD** (vì điều kiện dựa trên ngưỡng số)

5. Nhập `input_variable`: `glass_thick_kinh_canh` (tên biến — cần hỏi KTV cao cấp hơn để biết tên biến chính xác)

6. Thêm các dòng vào bảng `threshold_rows`:

   - Dòng 1: from=0, to=10.38, operator=≤, item=C3209-20, note="Nẹp mỏng cho kính đơn"

   - Dòng 2: from=10.39, to=16, operator=≤, item=C3210-20, note="Nẹp vừa cho kính cường lực"

   - Dòng 3: from=16.01, to=0 (không giới hạn), operator=>, item=C3211-20, note="Nẹp IGU cho kính hộp"

7. Chọn `default_item`: C3209-20 (dùng khi không có điều kiện nào khớp)

8. **Lưu** → nhấn **"Publish Version"** → nếu cần duyệt thì chờ duyệt → Sau Published, Rule sẵn sàng dùng


**Sau đó:** Vào AL Profile Line, chọn `item_selection_mode = Rule`, `item_rule = NEP-KINH-THEO-DO-DAY`. Từ nay mỗi khi Sales tính giá, hệ thống tự động chọn đúng nẹp dựa trên độ dày kính.


### 2. Cách Sales override item trong BOM Dialog


**Điều kiện để override:** Chỉ override được nếu dòng đó có `allow_sales_override = 1` (NHOM/VTP thường được phép, PK mặc định không được phép).


**Các bước:**

1. Trong BOM Dialog, nhập kích thước, chọn kính, chọn phụ kiện

2. Kéo xuống phần **"Item Preview"** — danh sách các item đã được hệ thống tự động chọn

3. Bên cạnh dòng có thể override sẽ có nút **"Đổi Item"** (màu xanh)

4. Click nút → popup hiện ra danh sách item được phép (đã lọc theo `override_item_group`)

5. Chọn item khác → xác nhận

6. Hệ thống tự động tính lại giá. Nhấn **"Tính lại"** để xem giá mới


**Lưu ý quan trọng:**

- Nếu dòng PK không có nút "Đổi Item" → do Admin đã tắt quyền override cho PK đó

- Nếu override sai loại (ví dụ NHOM → KINH) → hệ thống từ chối, hiện cảnh báo

- Sales chỉ override được trong phạm vi `override_item_group` cho phép


### 3. Cách sử dụng AI Assistant


**AI gợi ý Rule (Dynamic Item Rule):**

1. Vào **AL Dynamic Item Rule** → nhấn nút **"AI Gợi ý"** (góc phải màn hình)

2. Nhập mô tả tự nhiên bằng tiếng Việt:

   - "Khi kính dày <=10.38 dùng nẹp C3209, từ 10.39-16 dùng C3210, >16 dùng C3211"

3. AI tự động sinh ra bảng threshold_rows tương ứng

4. Kiểm tra lại kết quả → chỉnh sửa nếu cần → Publish Version


**AI gợi ý Discount (Pricing Advisor):**

1. Trong BOM Dialog, sau khi tính giá xong

2. AI Pricing Advisor hiển thị gợi ý: "Margin hiện tại 25%, có thể giảm tối đa 8% trước khi cần Approval cấp cao hơn"

3. Sales xem gợi ý, có thể áp dụng hoặc bỏ qua

4. Gợi ý KHÔNG tự động áp dụng — Sales phải chủ động chọn


**AI Quotation Copilot:**

1. Khi tạo Quotation mới, chat với AI Copilot: "Khách muốn cửa đi XF55 cho nhà ống 4m"

2. AI gợi ý BOM phù hợp nhất từ thư viện (RAG)

3. Sales chọn BOM, hệ thống tự động điền thông số kích thước


### 4. Cách quản lý tồn kho Batch-màu cho người dùng Mua hàng và Kho


**Nguyên tắc cốt lõi:** Mỗi Item nhôm chỉ có 1 mã duy nhất (theo tiết diện). Màu sắc được quản lý qua Batch, không phải qua Item Variant.


**Nhập kho (Purchase Receipt):**

1. Tạo Purchase Order cho Item nhôm: VD Item=C3318-20, số lượng=100kg

2. Khi tạo Purchase Receipt: nhập Batch ID mới (VD: `C3318-20-RAL9016-DUAN-A`)

3. Gán các field trên Batch:

   - `al_color` = RAL9016 (chọn từ danh mục AL Color Standard)

   - `al_source_project` = DUAN-A (dự án mua cho)

   - `al_is_reserved_for_project` = ✅ (tick vào nếu mua riêng cho dự án)

4. Hệ thống tự động bật Batch Wise Valuation — giá vốn tính theo lô thực tế


**Xuất kho (Stock Entry cho Sản xuất):**

1. Chọn Item gốc (VD: C3318-20)

2. Hệ thống hiển thị danh sách Batch có sẵn → chọn Batch đúng màu yêu cầu

3. Nếu Batch có `al_is_reserved_for_project=1` → chỉ được xuất cho đúng dự án đó

4. Hệ thống chặn xuất nhầm dự án khác


**Kiểm tra tồn kho:**

1. Vào **Stock Report** → chọn Item → xem tồn kho theo Batch

2. Mỗi Batch hiển thị: số lượng, màu (al_color), dự án nguồn (al_source_project), ngày nhập

3. Có thể lọc theo dự án để xem tồn kho riêng của từng công trình


**Xử lý khi hết màu:**

1. Mua thêm: Tạo PO mới → Purchase Receipt → tạo Batch mới (cùng Item, cùng màu, có thể khác dự án)

2. Hệ thống không cấm tạo Batch trùng màu — chỉ cấm xuất nhầm dự án


**Lợi ích so với Item Variant cũ:**

- Item Master chỉ ~100-300 Item (số tiết diện), không tăng đột biến theo màu

- Giá vốn chính xác theo từng lô nhờ Batch Wise Valuation

- Tồn kho phản ánh đúng bản chất vật lý (Item = tiết diện, Màu = lô hàng)

- Truy vết được lịch sử theo dự án qua al_source_project



---

# PHẦN BỔ SUNG — Orchestration & Module Nghiệp Vụ

# PHẦN D — TẦNG 4-4.5: ORCHESTRATION

## Hướng dẫn sử dụng (User Guide)

### 1. Tạo AL Dynamic Item Rule bằng UI
1. Vào AL Dynamic Item Rule → New → nhập rule_code, rule_name
2. Chọn THRESHOLD (nếu điều kiện số) hoặc LOOKUP (nếu điều kiện giá trị)
3. Thêm dòng vào bảng threshold_rows/lookup_rows
4. Chọn default_item → Lưu → Publish Version

### 2. Sales override item trong BOM Dialog
- Chỉ override được nếu allow_sales_override=1
- Click "Đổi Item" → chọn từ danh sách (đã lọc theo override_item_group)
- Hệ thống tự động tính lại giá

### 3. Sử dụng AI Assistant
- AI gợi ý Rule: Trong AL Dynamic Item Rule → "AI Gợi ý" → nhập mô tả tự nhiên
- AI gợi ý Discount: Trong BOM Dialog → AI Pricing Advisor hiển thị gợi ý

### 4. Quản lý tồn kho Batch-màu
- Nhập kho: Tạo PO → PR → tạo Batch (al_color, al_source_project)
- Xuất kho: Chọn Item gốc → chọn Batch → Stock Entry
- Batch Wise Valuation giúp giá vốn chính xác theo từng lô
