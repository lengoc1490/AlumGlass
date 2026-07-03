# AlumGlass ERP — ĐẶC TẢ THIẾT KẾ TRIỂN KHAI TOÀN DIỆN (TÀI LIỆU DUY NHẤT)

> **App:** `aluglass` (Frappe custom app trên ERPNext core) + phụ thuộc `formula_builder` (Formula Engine)
> **Phiên bản:** MASTER v19 — Tài liệu triển khai đầy đủ, tự thân (self-contained), không cần tham chiếu file khác
> **Phạm vi:** Master Data → Rule/Formula Engine → BOM/Báo giá → Mua vật tư → Sản xuất → Thi công → Thanh quyết toán → Kế toán lãi lỗ → AI toàn dự án
> **Định dạng:** Thiết kế cấu trúc + quy trình (không code) — sẵn sàng để đội dev chuyển thành DocType JSON + Python

> *"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi. Minh bạch từ báo giá tới quyết toán."*

---

## MỤC LỤC

- **PHẦN A — NỀN TẢNG:** I. Nguyên tắc thiết kế · II. Kiến trúc tổng thể 8 tầng · III. Danh mục 59 DocType
- **PHẦN B — TẦNG 1: MASTER DATA:** IV. DocType nền tảng đầy đủ trường · V. Custom Fields trên ERPNext core · VI. Master Data mẫu chuẩn
- **PHẦN C — TẦNG 2-3: RULE & FORMULA ENGINE:** VII. AL Calculation Rule · VIII. AL Dynamic Item Rule (có versioning) · IX. Formula Variable Binding
- **PHẦN D — TẦNG 4-4.5: ORCHESTRATION:** X. VariableResolver · XI. ProfileInterpreter 2-pass · XII. PkResolver · XIII. Dynamic Item Resolver (3 chế độ) · XIV. CostAccumulator · XV. BomOrchestrator — quy trình 9 bước
- **PHẦN E — TẦNG 5: PRESENTATION:** XVI. BOM Dialog & UI Flow
- **PHẦN F — TẦNG 6: MODULE NGHIỆP VỤ:**
  - XVII. BOM Version Control
  - XVIII. Approval Workflow
  - XIX. AL Discount Rule
  - XX. Material Planning (MRP Lite)
  - XXI. Cost Variance Analysis (vật tư)
  - XXII. Notification & Alert Engine
  - XXIII. Sales Analytics
  - XXIV. Reporting & Dashboard
  - XXV. Module Sản Xuất (Cutting & Production)
  - XXVI. Module Thi Công (Field Operations)
  - XXVII. Module Thanh Quyết Toán (Milestone Billing)
  - XXVIII. Module Kế Toán Lãi Lỗ (Project Profitability)
- **PHẦN G — TẦNG 7: AI:** XXIX. Tầng AI toàn diện
- **PHẦN H — VẬN HÀNH:** XXX. ConfigSnapshot & Audit Trail xuyên suốt · XXXI. Quy trình đầu-cuối · XXXII. Phân quyền & Vai trò · XXXIII. Ví dụ kiểm chứng · XXXIV. Lộ trình triển khai · XXXV. Rủi ro & điểm theo dõi · XXXVI. Checklist Go-live

---
---

# PHẦN A — NỀN TẢNG

## I. NGUYÊN TẮC THIẾT KẾ (21 NGUYÊN TẮC BẤT BIẾN)

| # | Nguyên tắc | Hệ quả thực tế |
|---|---|---|
| 1 | **Zero Python trong DB** — không formula/logic nào lưu dạng code Python thực thi trực tiếp | Đội kỹ thuật cấu hình BOM không cần biết lập trình |
| 2 | **Chọn Item trực tiếp** (Fixed) hoặc gián tiếp qua Rule/Formula (Dynamic) | Không có DocType "AL Product" trung gian — Item ERPNext là nguồn sự thật |
| 3 | **`show_condition` thay `if/elif`** | Biến thể sản phẩm = thêm 1 dòng, không sửa code |
| 4 | **1 bảng `al_lines` thống nhất** cho NHOM/KINH/VTP/PK, sort tự do | Vừa rõ ràng vừa linh hoạt, dễ audit |
| 5 | **DAG là nguồn sự thật về thứ tự tính toán** | FormulaEngine tự xây dựng đồ thị phụ thuộc; admin không cần khai theo thứ tự |
| 6 | **Kính đa tấm = tập hợp panel động** | 1 dòng khai báo → N panel sinh ra tại runtime (vách nhiều ô) |
| 7 | **Giá kính tách khỏi kích thước sản xuất** | Giá = m² × đơn giá đại diện; kích thước cắt thực tế là phép biến đổi riêng (xem §XXV) |
| 8 | **Phụ kiện: mặc định + thay thế có kiểm soát** | PK Set chuẩn + Sales override trong nhóm được phép |
| 9 | **Phụ thuộc chéo Nhôm↔Kính qua context phẳng** | `glass_thick_{prefix}` inject trước vào inputs, không gây circular dependency |
| 10 | **Rule là thư viện dùng chung** | Khai báo 1 lần, tái sử dụng nhiều BOM |
| 11 | **FormulaEngine là engine tính toán DUY NHẤT** | Không `eval()` rời rạc ở bất kỳ đâu, kể cả Dynamic Item Resolver |
| 12 | **Minh bạch tuyệt đối** — mọi con số đều `explain()` được, từ giá bán tới lãi/lỗ dự án | ConfigSnapshot + Project Profitability Snapshot đều immutable, có audit trail |
| 13 | **Module độc lập, hook không phá lõi** | Mọi tính năng mới (kể cả Sản xuất/Thi công/Quyết toán) đăng ký hook, không sửa Orchestrator |
| 14 | **Version = immutable snapshot** | Áp dụng cho BOM, Rule, và mọi cấu hình ảnh hưởng giá/chi phí đã cam kết |
| 15 | **Approval trước khi hiệu lực** | BOM mới, Rule mới, giá đặc biệt, discount lớn đều qua duyệt |
| 16 | **DynamicItemResolver dùng FormulaEngine.evaluate_single()** | Không tự xây eval sandbox riêng |
| 17 | **Formula Variable Binding (FB) thay AL Variable Binding cũ** | Dùng DAG topology của FB thay vì priority thủ công |
| 18 | **AL Calculation Rule — tinh gọn, không xóa loại rule cũ** | THRESHOLD/LOOKUP giữ bảng trực quan; CONSTANT/FORMULA có thể migrate sang FB Global Variable |
| 19 | **Cost Template + Formula Set — optional, có fallback** | Không bắt buộc migrate toàn bộ cùng lúc |
| 20 | **AL Dynamic Item Rule = immutable versioned** (như BOM Version) | Sửa Rule không ảnh hưởng tức thì tới Quotation đang mở — xem §VIII |
| 21 | **AI luôn là đề xuất, không tự ghi vào bất kỳ snapshot/version nào** | Mọi output AI đi qua `AL AI Suggestion Log` rồi Approval Workflow đã có sẵn |

---

## II. KIẾN TRÚC TỔNG THỂ — 8 TẦNG

```
TẦNG 7 — AI LAYER
  AI Formula/Rule Generator · AI Config Validator · AI PK Suggester
  AI Quotation Copilot · AI Win/Loss Analysis · AI Cutting Optimization
  AI Project Health Score · AI Anomaly Detection (vật tư + nhân công + bảo hành)
  ⇒ Mọi output ghi vào AL AI Suggestion Log, không ghi trực tiếp

TẦNG 6 — MODULE LAYER (Hook-based, đăng ký qua hooks.py, không sửa Tầng 3-4)
  6A Commercial : BOM Version Control · Approval Workflow · Discount Stack ·
                  Notification & Alert · Sales Analytics · Reporting & Dashboard
  6B Supply     : Material Planning (MRP Lite) · Cost Variance Analysis (vật tư)
  6C Production : Cutting Standard/Plan (Nhôm 1D + Kính 2D) · Glass/Aluminum Cut Order ·
                  Production Order Bridge (ERPNext Work Order)
  6D Field Ops  : Installation Order/Progress/Cost · Warranty Policy/Claim
  6E Financial  : Milestone Billing · Project Financial Config ·
                  Labor Cost Variance · Project Profitability Snapshot

TẦNG 5 — PRESENTATION (Frappe Web UI + Mobile)
  BOM Dialog · Glass Selector · PK Panel · Sales Override Panel
  Version Badge · Approval Inbox · Discount Selector · Diff Viewer
  Production Board (Kanban cắt) · Installation Mobile Checklist · Project P&L Dashboard

TẦNG 4.5 — DYNAMIC ITEM RESOLVER (Pre-Resolution Phase, trước DAG)
  Fixed mode / Rule mode (versioned) / Formula mode
  Item cache · batch DB lookup · sales override validate · fallback logic

TẦNG 4 — ORCHESTRATION (aluglass.engine)
  VariableResolver v3 (FB integration) · ProfileInterpreter v2 (2-pass) ·
  PkResolver · CostAccumulator v2 (Formula Set optional) · SnapshotBuilder ·
  BomOrchestrator — quy trình 9 bước (§XV)

TẦNG 3 — FORMULA ENGINE (formula_builder) — KHÔNG SỬA, bất biến tuyệt đối
  FormulaEngine: DAG · IncrementalContext · explain() · snapshot_with_trace() · evaluate_single()
  BASE_FUNCS 80+ · FormulaValidator · SecurityValidator

TẦNG 2 — RULE ENGINE & VARIABLE BINDING
  AL Calculation Rule (CONSTANT/FORMULA/THRESHOLD/LOOKUP/SEQUENCE)
  AL Dynamic Item Rule + AL Dynamic Item Rule Version (★ versioned — §VIII)
  Formula Variable Binding (2 custom handler: bom_variable, rule_engine_lookup)
  AL Discount Rule (stack riêng, không vào DAG)

TẦNG 1 — MASTER DATA
  ERPNext core: Item, Brand, Price List, Item Price, Item Group, Customer, Project, Employee...
  aluglass lõi: AL Glass Master, AL Profile Set/Line, AL PK Set/Line, AL BOM, AL Cost Template, ConfigSnapshot...
  aluglass mở rộng: AL Cutting Standard, AL Installation Team, AL Warranty Policy, AL Project Financial Config...
```

**Quyết định kiến trúc cốt lõi:** Toàn bộ nghiệp vụ Sản xuất/Thi công/Quyết toán/Tài chính dự án đều nằm trong **Tầng 6** dưới dạng module hook — không có tầng lõi mới nào được thêm. Tầng 1-4 (Master Data → Formula Engine → Orchestration) giữ nguyên tuyệt đối qua mọi giai đoạn mở rộng, đảm bảo hệ thống không "phình lõi" theo thời gian.

---

## III. DANH MỤC 59 DOCTYPE (TỔNG HỢP THEO TẦNG)

### Tầng 1 — Master Data (20 DocType lõi + 4 mới)

| # | DocType | Loại | Mô tả ngắn |
|---|---|---|---|
| 1 | AL Variable Group | Master | Nhóm biến (Kích thước, Số lượng, Vật liệu...) |
| 2 | AL Material Type | Master | Loại vật tư + phương pháp tính (kg/m², m², cái, mét) |
| 3 | AL Glass Type | Master | Phân loại kính (đơn, cường lực, hộp, Low-E, laminate) |
| 4 | AL Glass Layer Type | Master | Loại lớp kính (Phase nâng cao) |
| 5 | AL Glass Master | Master | Thông số kỹ thuật kính, nguồn `glass_thick` |
| 6 | AL Glass Layer Line | Child (của #5) | Cấu trúc lớp kính chi tiết |
| 7 | AL Product Type | Master | Loại sản phẩm (cửa đi, cửa sổ, vách kính...) |
| 8 | AL Variable Library | Master | Thư viện biến toàn cục |
| 9 | AL Variable Set | Master | Tập biến cho 1 loại BOM |
| 10 | AL Variable Set Detail | Child (của #9) | Dòng con Variable Set |
| 11 | AL Cost Bucket | Master | Tài khoản chi phí (LEAF/AGGREGATE) |
| 12 | AL Profile Line | Child (của #14) | Dòng vật tư thống nhất — trung tâm hệ thống |
| 13 | AL Profile Set | Master | Tập hợp `al_lines` |
| 14 | AL PK Set | Master | Bộ phụ kiện tái sử dụng |
| 15 | AL PK Line | Child (của #14) | Dòng phụ kiện |
| 16 | AL BOM | Master | Liên kết Variable Set + Profile Set + PK Set + Cost Template |
| 17 | AL Cost Template | Master | Công thức tính giá thành |
| 18 | AL Cost Template Line | Child (của #17) | Dòng chi phí |
| 19 | ConfigSnapshot | Master | Audit trail bất biến cho mỗi lần tính giá |
| 20 | AL Alert Config | Master | Cấu hình cảnh báo |
| 21 ★ | AL Cutting Standard | Master | Quy cách cắt chuẩn (phôi, dung sai) |
| 22 ★ | AL Installation Team | Master | Đội thi công |
| 23 ★ | AL Warranty Policy | Master | Chính sách bảo hành |
| 24 ★ | AL Project Financial Config | Master | Cấu hình phân bổ overhead dự án |

### Tầng 2 — Rule & Variable Binding (7 DocType lõi + 3 mới)

| # | DocType | Loại | Mô tả |
|---|---|---|---|
| 25 | AL Calculation Rule | Master | CONSTANT/FORMULA/THRESHOLD/LOOKUP/SEQUENCE |
| 26 | AL Rule Threshold Row | Child | Bảng ngưỡng |
| 27 | AL Rule Lookup Row | Child | Bảng tra cứu |
| 28 | AL Rule Sequence Item | Child | Danh sách rule con |
| 29 | AL Dynamic Item Rule | Master | Rule chọn Item (THRESHOLD/LOOKUP) |
| 30 | AL Dynamic Item Threshold Row | Child | Ngưỡng số → item |
| 31 | AL Dynamic Item Lookup Row | Child | Cặp key → item |
| 32 ★ | AL Dynamic Item Rule Version | Master | Snapshot bất biến của Rule — vá gap P0 |
| 33 | AL Discount Rule | Master | Luật chiết khấu |
| 34 | AL Discount Rule Line | Child | Bảng tier chiết khấu |

*(Formula Variable Binding là DocType thuộc app `formula_builder`, không thuộc `aluglass` — dùng qua API `resolve_bindings_with_deps()`.)*

### Tầng 6 — Module nghiệp vụ (25 DocType)

| # | DocType | Nhóm | Mô tả |
|---|---|---|---|
| 35 | AL BOM Version | 6A | Snapshot bất biến BOM |
| 36 | AL BOM Change Log | 6A | Nhật ký thay đổi (dùng chung cho BOM & Rule version) |
| 37 | AL Material Plan | 6B | Kế hoạch vật tư tổng hợp |
| 38 | AL Material Plan Line | 6B | Dòng vật tư trong kế hoạch |
| 39 | AL Cost Variance | 6B | So sánh giá Quotation vs Purchase |
| 40 | AL Dashboard Config | 6A | Cấu hình widget theo vai trò |
| 41 | AL Sales KPI | 6A | KPI Sales |
| 42 ★ | AL Aluminum Cutting Plan | 6C | Kế hoạch cắt nhôm tối ưu (1D) |
| 43 ★ | AL Aluminum Cutting Plan Line | 6C | Từng đoạn cắt + phế liệu |
| 44 ★ | AL Glass Cutting Plan | 6C | Kế hoạch cắt kính tối ưu (2D nesting) |
| 45 ★ | AL Glass Cutting Plan Line | 6C | Từng tấm cắt |
| 46 | AL Glass Cut Order | 6C | Lệnh cắt gắn SO cụ thể |
| 47 | AL Glass Cut Line | 6C | Chi tiết tấm cắt |
| 48 ★ | AL Production Order Bridge | 6C | Cầu nối ERPNext Work Order |
| 49 ★ | AL Installation Order | 6D | Lệnh thi công |
| 50 ★ | AL Installation Order Line | 6D | Hạng mục thi công |
| 51 ★ | AL Installation Progress | 6D | Nhật ký tiến độ (append-only) |
| 52 ★ | AL Installation Cost Actual | 6D | Chi phí thi công thực tế |
| 53 ★ | AL Warranty Claim | 6D | Yêu cầu bảo hành |
| 54 ★ | AL Milestone Billing Plan | 6E | Kế hoạch thanh toán theo đợt |
| 55 ★ | AL Milestone Billing Line | 6E | Từng đợt thanh toán |
| 56 ★ | AL Labor Cost Variance | 6E | Variance nhân công/thi công |
| 57 ★ | AL Project Profitability Snapshot | 6E | P&L bất biến theo dự án |

### Tầng 7 — AI Governance (2 DocType)

| # | DocType | Mô tả |
|---|---|---|
| 58 ★ | AL AI Suggestion Log | Ghi nhận mọi đề xuất AI |
| 59 ★ | *(field bổ sung, không phải DocType riêng)* `Quotation.al_loss_reason` | Phục vụ AI Win/Loss |

**Tổng: 57 DocType chính thức + field bổ sung = phạm vi triển khai đầy đủ.** (★ = mới so với v17/v18, thiết kế đầy đủ trong tài liệu này)

---
---

# PHẦN B — TẦNG 1: MASTER DATA

## IV. DOCTYPE NỀN TẢNG — ĐẦY ĐỦ TRƯỜNG

### 4.1 AL Variable Group (Master)
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| group_code | Data | ✓ unique | KICH_THUOC, SO_LUONG, VAT_LIEU, CANH_CUA, VACH |
| group_name | Data | | |
| sort_order | Int | | |

### 4.2 AL Material Type (Master)
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| type_code | Data | ✓ unique | NHOM_PROFILE, KINH, VTP, PHU_KIEN |
| type_name | Data | | |
| default_bucket | Link → AL Cost Bucket | | Bucket mặc định |
| calc_method | Select | | BY_KG_M / BY_M2 / BY_UNIT / BY_METER |

### 4.3 AL Glass Type (Master)
| fieldname | fieldtype | reqd |
|---|---|---|
| type_code | Data | ✓ unique — DON, CUONG_LUC, HOP, LOWE, LAM |
| type_name | Data | |

### 4.4 AL Glass Layer Type (Master)
| fieldname | fieldtype |
|---|---|
| layer_code | Data (unique) — GLASS, AIR_GAP, INTERLAYER |
| layer_name | Data |

### 4.5 AL Glass Master (Master) — nguồn `glass_thick`
| fieldname | fieldtype | Mô tả |
|---|---|---|
| glass_code | Data (unique) | KINH-DON-8, KINH-CL-10, KINH-HOP-24... |
| glass_name | Data | |
| **total_thick_mm** | Float | **Nguồn gốc `glass_thick_{prefix}` — ProfileInterpreter tra trực tiếp** |
| glass_type | Link → AL Glass Type | |
| has_complex_structure | Check | Bật nếu có glass_layers |
| u_value / shgc / vlt | Float | Thông số nhiệt/quang (nâng cao) |
| glass_layers | Table → AL Glass Layer Line | Cấu trúc lớp (nâng cao) |

### 4.6 AL Glass Layer Line (Child của #5)
| fieldname | fieldtype |
|---|---|
| sort_order | Int (reqd) |
| layer_type | Link → AL Glass Layer Type (reqd) |
| thickness_mm | Float |
| description | Small Text |

### 4.7 AL Product Type (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| type_code | Data (unique) | CUA_DI, CUA_SO, CUA_LUA, CUA_MAT_HAT, VACH_KINH |
| type_name | Data | |
| nc_pct | Float (default 12) | % nhân công sản xuất mặc định |
| nc_ld_rate | Currency | Đơn giá nhân công lắp đặt (đ/m²) — dùng làm baseline cho §XXVIII |
| default_warranty_policy | Link → AL Warranty Policy | ★ v19 |
| default_milestone_template | Link → AL Milestone Billing Plan Template *(hoặc JSON template inline)* | ★ v19 |
| description | Small Text | |

### 4.8 AL Variable Library (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| var_code | Data (unique) | W_mm, H_mm, SL, n_canh, do_day... |
| var_label | Data | Nhãn hiển thị Dialog |
| var_group | Link → AL Variable Group | |
| var_type | Select | FLOAT / INT / STR / BOOL |
| default_val | Data | |
| options | Data | Danh sách Select |
| ui_widget | Select | Text / Select / Number / Toggle |
| description | Small Text | |

### 4.9 AL Variable Set (Master)
| fieldname | fieldtype |
|---|---|
| set_code | Data (unique) |
| set_name | Data |
| al_var_details | Table → AL Variable Set Detail |

### 4.10 AL Variable Set Detail (Child)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| variable | Link → AL Variable Library (reqd) | |
| is_required | Check | |
| override_default | Data | |
| depends_on | Code | Điều kiện hiển thị (JS convention Frappe — không đổi thành Small Text) |
| sort_order | Int | |

### 4.11 AL Cost Bucket (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| bucket_code | Data (unique) | VL_NHOM, VL_KINH, TONG_VL, GIA_THANH... |
| bucket_name | Data | |
| bucket_role | Select | LEAF / AGGREGATE |
| parent_bucket | Link → AL Cost Bucket | |
| sort_order | Int | |
| report_group | Data | "A. Vật liệu", "B. Nhân công"... |

### 4.12 AL Profile Line (Child của AL Profile Set) ★ TRUNG TÂM HỆ THỐNG

**Trường chung (mọi line_type):**
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| sort_order | Int | ✓ | Thứ tự hiển thị, không ảnh hưởng tính toán |
| line_type | Select | ✓ | NHOM / KINH / VTP / PK |
| line_name | Data | ✓ | |
| slug | Data | | Auto-generate, unique trong Profile Set |
| group_tag | Data | | KHUNG/CANH/NEP/KINH_CANH/KINH_OC/GIOANG... |
| show_condition | Small Text | | Boolean expression FormulaEngine |
| cost_bucket | Link → AL Cost Bucket | | Trống = default của Material Type |
| is_active | Check (default 1) | | |
| **item_selection_mode** | **Select** | | **Fixed / Rule / Formula (★ v18)** |
| **item_rule** | **Link → AL Dynamic Item Rule** | | Dùng khi mode = Rule (★ v18, nay có version §VIII) |
| **item_condition_formula** | **Small Text** | | Dùng khi mode = Formula (★ v18) |
| **item_fallback** | **Link → Item** | | Bắt buộc nếu mode ≠ Fixed |

**Trường riêng NHOM:**
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| item_code | Link → Item | ✓ nếu Fixed | `Item.al_item_type` = NHOM_PROFILE |
| quantity_rule | Link → AL Calculation Rule | | |
| qty_formula | Small Text | | Có thể tham chiếu `glass_thick_{prefix}` |
| price_type | Select | | Rule / Item Price / Fixed |
| price_rule | Link → AL Calculation Rule | | |
| fixed_price | Currency | | |

**Trường riêng KINH** *(luôn Fixed mode — không hỗ trợ Dynamic, xem Edge Case §XIII)*:
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| ctx_inject_prefix | Data | ✓ | Unique trong Profile Set, không kết thúc bằng chữ số |
| default_glass_master | Link → AL Glass Master | ✓ | Nguồn `total_thick_mm` |
| width_rule / height_rule | Link → AL Calculation Rule | | |
| width_formula / height_formula | Small Text | | VD `W_mm - 86` |
| panel_count_formula | Small Text | | `(n_do_dung+1)*(n_do_ngang+1)` |
| panel_glass_override_allowed | Check | | Sales chọn kính riêng từng panel |
| qty_per_panel_formula | Small Text (default "1") | | |
| price_type | Select | | Item Price / Rule / Fixed |
| price_list | Link → Price List | | |
| price_rule | Link → AL Calculation Rule | | |
| fixed_price | Currency | | |
| cut_fee_pct | Float (default 0) | | Phí cắt kính % |

**Trường riêng VTP:**
| fieldname | fieldtype | reqd |
|---|---|---|
| item_code | Link → Item | ✓ nếu Fixed |
| quantity_rule | Link → AL Calculation Rule | |
| qty_formula | Small Text | |
| price_type | Select | Item Price / Fixed / Rule |
| price_list | Link → Price List | |
| fixed_price | Currency | |

**Trường riêng PK (nội tuyến):**
| fieldname | fieldtype | reqd |
|---|---|---|
| item_code | Link → Item | ✓ nếu Fixed |
| sl_formula | Small Text | ✓ |
| price_list | Link → Price List | |
| allow_substitute | Check | |
| substitute_item_group | Link → Item Group | |

> **Biến tự động sinh (không cần khai báo Binding):** `glass_thick_{prefix}`, `{prefix}_total_perimeter_m`, `{prefix}_total_m2`, `{prefix}_total_qty`, `max_glass_thick_mm`.

### 4.13 AL Profile Set (Master)
| fieldname | fieldtype | reqd |
|---|---|---|
| set_code | Data | ✓ unique |
| set_name | Data | ✓ |
| product_type | Link → AL Product Type | |
| brand | Link → Brand | |
| version | Data (default "1.0") | |
| al_lines | Table → AL Profile Line | |

### 4.14 AL PK Set / AL PK Line
**AL PK Set:** `set_code` (unique), `set_name`, `product_type` (Link), `al_pk_lines` (Table).

**AL PK Line:**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| item_code | Link → Item (reqd nếu Fixed) | Item mặc định |
| sl_formula | Small Text (reqd) | |
| price_list | Link → Price List | |
| cost_bucket | Link → AL Cost Bucket | |
| allow_substitute | Check | |
| substitute_item_group | Link → Item Group | |
| **item_selection_mode / item_rule / item_condition_formula / item_fallback** | (giống AL Profile Line ★v18) | |

### 4.15 AL BOM (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| bom_code | Data (unique) | |
| bom_name | Data | |
| product_type | Link → AL Product Type | |
| brand | Link → Brand | |
| representative_item | Link → Item (reqd) | Item phi tồn kho đại diện |
| variable_set | Link → AL Variable Set | |
| profile_set | Link → AL Profile Set | |
| pk_set | Link → AL PK Set | Optional |
| default_cost_template | Link → AL Cost Template | |
| thumbnail | Attach Image | |
| is_active | Check (default 1) | |
| current_version | Link → AL BOM Version | Version đang Published |
| total_versions | Int (read-only) | |
| last_published_on | Datetime (read-only) | |
| requires_approval_for_new_version | Check | |
| assigned_discount_rules | JSON | Danh sách AL Discount Rule mặc định |
| **default_installation_team** | **Link → AL Installation Team** | ★ v19, gợi ý khi tạo Installation Order |
| **default_milestone_billing_template** | **JSON** | ★ v19, template % các đợt thanh toán mặc định |

### 4.16 AL Cost Template / AL Cost Template Line
**AL Cost Template:** `template_code` (unique), `template_name`, `product_type` (Link), `formula_set` (★v18, Link → Formula Set, optional), `al_lines` (Table).

**AL Cost Template Line:**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| sort_order | Int | |
| line_code | Data | GIA_THANH, GIA_BAN, DON_GIA_M2... |
| line_label | Data | Tên hiển thị báo giá |
| calc_formula | Small Text | "TONG_VL + TONG_NC + TONG_OH" |
| cost_bucket | Link → AL Cost Bucket | |
| is_subtotal | Check | |
| show_on_quotation | Check (default 1) | |

### 4.17 ConfigSnapshot (Master) — xem đầy đủ tại §XXX

| fieldname | fieldtype | Mô tả |
|---|---|---|
| snapshot_id | Data (unique) | |
| formula_engine_snapshot_id / formula_engine_payload_hash | Data | Tham chiếu EnterpriseSnapshot của formula_builder |
| enterprise_snapshot_json | Long Text | Toàn bộ payload |
| profile_set / profile_set_hash | Link / Data | |
| pk_set / pk_overrides_json | Link / JSON | |
| rule_set_hashes / glass_master_hashes | JSON | `{code: hash}` |
| variable_bindings_hash | Data | |
| cost_template / cost_template_hash | Link / Data | |
| **bom_version_id / bom_version_hash** | Data | ★ v17 |
| **rule_version_ids** | **JSON** | **★ v19 — `{rule_code: version_name}` — xem §VIII** |
| **discount_applied** | JSON | `{rule, pct, gia_thuong_mai}` |
| **discount_approval_ref** | Data | |
| calculation_timestamp | Datetime | |
| created_at | Datetime | |
| quotation / quotation_item_name | Link / Data | |
| drift_detected | Check | |
| drift_details | JSON | |

### 4.18 AL Alert Config (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| alert_type | Select | PRICE_CHANGE / LOW_STOCK / BOM_EXPIRY / VARIANCE_ALERT / APPROVAL_PENDING / DISCOUNT_EXCEEDED / **MARGIN_DRIFT (★v19)** / **INSTALLATION_DELAY (★v19)** |
| alert_name | Data | |
| is_active | Check | |
| threshold_value | Float | |
| notify_roles / notify_users | JSON | |
| notification_channel | Select | EMAIL / FRAPPE_NOTIFICATION / BOTH |
| frequency | Select | REALTIME / DAILY_DIGEST / WEEKLY |
| max_total_discount_pct | Float | |

### 4.19 AL Cutting Standard (Master) ★ v19
| fieldname | fieldtype | Mô tả |
|---|---|---|
| applies_to | Select | NHOM_PROFILE / KINH |
| profile_code hoặc item_group | Data / Link | Phạm vi áp dụng |
| stock_bar_length_mm (NHOM) | Float | Chiều dài phôi chuẩn (vd 6000mm) |
| saw_kerf_mm (NHOM) | Float | Hao do lưỡi cưa |
| jumbo_sheet_size (KINH) | Data | vd "3210x2250" |
| edge_trim_mm (KINH) | Float | Trừ hao mép |
| min_offcut_reusable_mm | Float | Ngưỡng phế liệu tái dùng |
| cutting_tolerance_formula | Small Text | Công thức trừ hao gia công qua FormulaEngine (Nguyên tắc P-1, §XXV) |

### 4.20 AL Installation Team (Master) ★ v19
| fieldname | fieldtype | Mô tả |
|---|---|---|
| team_name | Data | |
| team_leader | Link → Employee/User | |
| members | Table (Employee) | |
| region | Data | |
| capacity_m2_per_day | Float | |
| is_active | Check | |

### 4.21 AL Warranty Policy (Master) ★ v19
| fieldname | fieldtype | Mô tả |
|---|---|---|
| policy_code | Data (unique) | |
| product_type | Link → AL Product Type | |
| warranty_months | Int | |
| coverage_scope | Small Text | Mô tả phạm vi bảo hành |
| exclusions | Small Text | |

### 4.22 AL Project Financial Config (Master) ★ v19
| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | |
| overhead_allocation_method | Select | NONE / PCT_OF_REVENUE / FIXED_AMOUNT |
| overhead_allocation_value | Float | |
| margin_drift_alert_threshold_pct | Float | Ngưỡng cảnh báo lệch margin (mặc định -5%) |

---

## V. CUSTOM FIELDS TRÊN ERPNEXT CORE

### 5.1 Item
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_item_type | Select | NHOM_PROFILE / KINH / VTP / PHU_KIEN |
| al_glass_master | Link → AL Glass Master | Bắt buộc nếu KINH |
| al_kg_per_m | Float | Bắt buộc nếu NHOM_PROFILE |

### 5.2 Quotation Item — đầy đủ (tất cả trường qua các phiên bản)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_bom | Link → AL BOM | |
| al_W_mm / al_H_mm | Float | |
| al_mau_nhom | Data | |
| al_bom_vars | JSON | |
| al_glass_selections | JSON | |
| al_pk_overrides | JSON | |
| al_cost_template_override | Link → AL Cost Template | |
| al_vl_nhom / al_vl_kinh / al_vl_vtp / al_vl_pk | Currency | |
| al_tong_vl / al_gia_thanh / al_gia_ban / al_gia_vat / al_don_gia_m2 | Currency | |
| al_config_snapshot | Link → ConfigSnapshot | |
| al_recalculate | Button | |
| al_bom_version | Link → AL BOM Version | |
| al_discount_rule | Link → AL Discount Rule | |
| al_discount_pct | Float | |
| al_gia_thuong_mai | Currency | |
| al_cost_variance_ref | Link → AL Cost Variance | |
| al_approval_status | Select | PENDING / APPROVED / REJECTED |
| al_approved_by | Link → User | |
| al_approval_note | Small Text | |
| **al_sales_item_overrides** | **JSON** | **★ v18 — `{slug: item_code}` cho dòng Dynamic** |

### 5.3 Sales Order Item / Sales Invoice Item
Y hệt Quotation Item (trừ `al_recalculate`), cộng `al_source_quotation_item` (Data, ẩn). Toàn bộ field `al_*` copy khi convert QT→SO→SI qua hook `copy_al_fields`.

### 5.4 Quotation (cấp Master, không phải Item) ★ v19
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_loss_reason | Select | Giá cao / Chậm tiến độ / Đối thủ / Khách đổi ý / Khác — dùng cho AI Win/Loss (§XXIX) |

### 5.5 Sales Order ★ v19
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_installation_order | Link → AL Installation Order | Tự động tạo khi Submit (Hook E, §XV) |
| al_milestone_billing_plan | Link → AL Milestone Billing Plan | Tự động tạo khi Submit (Hook E) |

---

## VI. MASTER DATA MẪU CHUẨN (dùng để kiểm chứng & làm khung dữ liệu ban đầu)

### 6.1 AL Variable Group
| group_code | group_name | sort_order |
|---|---|---|
| KICH_THUOC | Kích thước | 10 |
| SO_LUONG | Số lượng | 20 |
| VAT_LIEU | Vật liệu | 30 |
| CANH_CUA | Cánh cửa | 40 |
| VACH | Vách kính | 50 |

### 6.2 Formula Variable Binding — Priority chuẩn (nguồn dữ liệu → thứ tự resolve)
| source_type | priority | Ví dụ |
|---|---|---|
| Quotation Input | 10 | W_mm, H_mm, qty, mau_nhom |
| BOM Attribute | 20 | brand |
| BOM Variable | 30 | n_canh, do_day, huong_mo, co_nguong |
| Computed đơn giản | 40 | W_m, H_m |
| Rule Engine Result (LOOKUP) | 60 | don_gia_nhom |
| Computed phức tạp | 70 | canh_rong_mm |

> `glass_thick_{prefix}` không có Binding — inject trực tiếp bởi VariableResolver.

### 6.3 AL Calculation Rule mẫu

**CONSTANT:**
| rule_code | constant_value | Mô tả |
|---|---|---|
| XF55-OFFSET-W | 86 | Offset chiều rộng kính cánh XF55 |
| XF55-OFFSET-H | 86 | Offset chiều cao |

**FORMULA:**
| rule_code | formula_expression | Mô tả |
|---|---|---|
| QTY-KHUNG-DUNG | `(H_m * 2) * qty` | Khung đứng |
| QTY-KHUNG-NGANG | `(W_m + 0.043*2) * qty` | Khung ngang |
| QTY-CANH-DUNG | `(H_m - 0.043*2) * n_canh * qty` | Cánh đứng |
| QTY-CANH-NGANG | `(W_m/n_canh - 0.043*2) * n_canh * qty` | Cánh ngang |
| QTY-NEP-DUNG | `(H_m - 0.043*2) * n_canh * qty * 2` | Nẹp kính đứng |
| QTY-NEP-NGANG | `(W_m/n_canh - 0.043*2) * n_canh * qty * 2` | Nẹp kính ngang |

**LOOKUP (TRA-GIA-NHOM):**
| key_1 (brand) | key_2 (mau_nhom) | result_value (đ/kg) |
|---|---|---|
| XF-NK | STD | 113,000 |
| XF-NK | DAK | 118,000 |
| XF-NK | VG | 125,000 |
| ALUMIL | STD | 135,000 |
| ALUMIL | DAK | 142,000 |

### 6.4 AL Cost Bucket
| bucket_code | bucket_role | parent_bucket | report_group |
|---|---|---|---|
| VL_NHOM / VL_KINH / VL_VTP / VL_PK | LEAF | TONG_VL | A. Vật liệu |
| TONG_VL | AGGREGATE | | A. Vật liệu |
| NC_SX / NC_LD | LEAF | TONG_NC | B. Nhân công |
| TONG_NC | AGGREGATE | | B. Nhân công |
| OH_HH / OH_CUT_KINH / OH_VC / OH_BH | LEAF | TONG_OH | C. Overhead |
| TONG_OH | AGGREGATE | | C. Overhead |
| GIA_THANH / GIA_BAN / GIA_VAT | AGGREGATE | | D. Tổng hợp |

### 6.5 AL Cost Template — CT-01-STANDARD
| sort | line_code | calc_formula | is_subtotal |
|---|---|---|---|
| 10 | VL_NHOM | VL_NHOM | 0 |
| 20 | VL_KINH | VL_KINH | 0 |
| 30 | VL_VTP | VL_VTP | 0 |
| 40 | VL_PK | VL_PK | 0 |
| 50 | TONG_VL | VL_NHOM + VL_KINH + VL_VTP + VL_PK | 1 |
| 55 | TONG_M2 | W_m * H_m * qty | 0 |
| 60 | NC_SX | TONG_VL * 0.12 | 0 |
| 70 | NC_LD | TONG_M2 * 180000 | 0 |
| 80 | TONG_NC | NC_SX + NC_LD | 1 |
| 90 | OH_HH | TONG_VL * 0.01 | 0 |
| 100 | OH_CUT_KINH | OH_CUT_KINH | 0 |
| 110 | OH_VC | 500000 | 0 |
| 120 | OH_BH | TONG_VL * 0.005 | 0 |
| 130 | TONG_OH | OH_HH + OH_CUT_KINH + OH_VC + OH_BH | 1 |
| 140 | GIA_THANH | TONG_VL + TONG_NC + TONG_OH | 1 |
| 150 | PROFIT | GIA_THANH * 0.15 | 0 |
| 160 | GIA_BAN | GIA_THANH + PROFIT | 1 |
| 165 | DON_GIA_M2 | GIA_BAN / TONG_M2 | 0 |
| 170 | GIA_VAT | GIA_BAN * 1.10 | 1 |

### 6.6 AL Glass Master mẫu
| glass_code | total_thick_mm | glass_type | rate (đ/m²) |
|---|---|---|---|
| KINH-DON-8 | 8.0 | DON | 250,000 |
| KINH-CL-10 | 10.0 | CUONG_LUC | 550,000 |
| KINH-HOP-24 | 24.0 | HOP | 820,000 |
| KINH-LOWE-24 | 24.0 | LOWE | 1,150,000 |

### 6.7 Item — Nhôm Xingfa NK mẫu
| item_code | al_kg_per_m | Mô tả |
|---|---|---|
| C3318-20 | 1.257 | Khung bao đứng 2.0mm |
| C3209-20 | 0.198 | Nẹp kính ≤10.38mm |
| C3210-20 | 0.245 | Nẹp kính 11–16mm |
| C3211-20 | 0.312 | Nẹp kính IGU >16mm |

### 6.8 AL Profile Set mẫu — PS-CUA-DI-XF55 (minh họa logic nẹp tự động theo độ dày kính)
| sort | line_type | slug | Logic |
|---|---|---|---|
| 10-50 | NHOM | nhom_0010...0050 | Khung, cánh — show_condition theo `do_day`, `huong_mo`, `co_nguong` |
| **60** | NHOM | nhom_0060 | item=C3209-20, `show_condition = glass_thick_kinh_canh <= 10.38` |
| **61** | NHOM | nhom_0061 | item=C3210-20, `10.38 < glass_thick_kinh_canh <= 16` |
| **62** | NHOM | nhom_0062 | item=C3211-20, `glass_thick_kinh_canh > 16` |
| 80 | KINH | kinh_canh | prefix=`kinh_canh`, width=`W_mm-86`, height=`H_mm-86` |
| 90 | KINH | kinh_oc | prefix=`kinh_oc`, show_condition=`co_oc_thong_gio=='Yes'` |
| 100-150 | VTP | vtp_0100... | Gioăng, keo, xốp, vít — nhiều dòng dùng `max_glass_thick_mm` |

### 6.9 AL Discount Rule mẫu
| name | rule_type | discount_pct | priority | requires_approval |
|---|---|---|---|---|
| DISC-RETAIL-STD | CUSTOMER_TIER | 0 | 100 | No |
| DISC-PROJECT-10 | PROJECT | 10 | 40 | Yes (>8%) |
| DISC-VOLUME-TIER | VOLUME | (xem tier) | 30 | No |

Tier DISC-VOLUME-TIER: 1-9 bộ = 0%, 10-29 = 3%, 30-99 = 5%, ≥100 = 8%.

### 6.10 AL Alert Config mặc định
| alert_type | threshold_value | notify_roles | frequency |
|---|---|---|---|
| PRICE_CHANGE | 5% | Kỹ Thuật, Admin | REALTIME |
| VARIANCE_ALERT | 15% | Admin, Kế toán | REALTIME |
| DISCOUNT_EXCEEDED | 8% | Admin | REALTIME |
| **MARGIN_DRIFT ★v19** | -5% | Director, Admin | REALTIME |
| **INSTALLATION_DELAY ★v19** | 3 ngày trễ | Quản lý Thi công, Director | DAILY_DIGEST |

### 6.11 AL Cutting Standard mẫu ★ v19
| applies_to | profile_code | stock_bar_length_mm | saw_kerf_mm |
|---|---|---|---|
| NHOM_PROFILE | XF-NK (mọi profile) | 6000 | 3 |

| applies_to | jumbo_sheet_size | edge_trim_mm |
|---|---|---|
| KINH | 3210x2250 | 10 |

---
---

# PHẦN C — TẦNG 2-3: RULE & FORMULA ENGINE

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
