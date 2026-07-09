# AlumGlass ERP — ĐẶC TẢ HỢP NHẤT (CANONICAL v24 — "Core-First Edition")

> **App:** `aluglass` (Frappe custom app trên ERPNext core) + phụ thuộc `formula_builder` (Formula Engine)
> **Phiên bản:** v24 — hợp nhất v17→v23 + đợt tái cấu trúc "Core-First" (loại bỏ mọi custom trùng lặp với ERPNext core: Quality Inspection, Warranty Claim, Pricing Rule, Payment Schedule, Workflow Engine, Accounting Dimension).
> **Triết lý thay đổi so với v23:** v23 đã đúng về *nghiệp vụ*. v24 sửa về *kiến trúc triển khai* — với tiêu chí: **"Nếu ERPNext core đã có DocType/engine giải quyết đúng bản chất vấn đề, dùng core + custom field/hook. Chỉ tạo DocType mới cho phần core không có khái niệm tương đương."**
> **Phạm vi:** Master Data → Rule/Formula Engine → BOM/Báo giá → Mua vật tư → Sản xuất → Thi công → Thanh quyết toán → Kế toán lãi lỗ → AI toàn dự án.
> **Định dạng:** Thiết kế cấu trúc + quy trình (không code) — sẵn sàng để đội dev chuyển thành DocType JSON + Python hooks + Client Script.
> **Đánh dấu phiên bản:** ★v18…★v23 = giữ nguyên để truy vết nguồn gốc quyết định. **★v24 = thay đổi ở đợt tái cấu trúc Core-First này.**

> *"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi. Tồn kho theo thực tế vật lý (Batch). Kích thước theo thực tế công trình (Site Survey). Phạm vi hợp đồng thay đổi có kiểm soát (Change Order). Version có hiệu lực theo thời gian (valid_from). Sản xuất không cắt khi chưa có hàng (Material Check). Minh bạch từ báo giá tới quyết toán. AI luôn đề xuất, không quyết định. **Không viết lại thứ core đã làm tốt.***"

---

## MỤC LỤC

- **PHẦN A — NỀN TẢNG:** I. Nguyên tắc thiết kế (31, gồm 2 nguyên tắc mới ★v24) + QĐ-21→30 · II. Kiến trúc tổng thể · III. Danh mục DocType (custom mới + core được tái sử dụng) · III-B. Bảng ánh xạ "Core thay Custom" ★v24
- **PHẦN B — TẦNG 1: MASTER DATA:** IV. DocType nền tảng · V. Custom Fields trên ERPNext core (mở rộng ★v24) · VI. Master Data mẫu
- **PHẦN C — TẦNG 2-3: RULE & FORMULA ENGINE:** VII-IX
- **PHẦN D — TẦNG 4-4.5: ORCHESTRATION:** X-XV
- **PHẦN E — TẦNG 5: PRESENTATION:** XVI
- **PHẦN F — TẦNG 6: MODULE NGHIỆP VỤ:** XVII-XXVIII (nhiều mục viết lại theo core: Discount §XIX→Pricing Rule, Milestone Billing §XXVII→Payment Schedule, QC §25.9→Quality Inspection, Warranty→Warranty Claim core)
- **PHẦN G — TẦNG 7: AI:** XXIX
- **PHẦN H — VẬN HÀNH:** XXX. ConfigSnapshot · XXXI. Quy trình đầu-cuối · XXXII. Phân quyền · XXXIII. Ví dụ kiểm chứng · XXXIV. Lộ trình triển khai · XXXV. Rủi ro · XXXVI. Checklist Go-live · XXXVII. Kế toán: Cost Bucket vs Cost Center vs Accounting Dimension ★v24 · XXXVIII. Warehouse & vị trí lưu kho ★v24

---
---

# PHẦN A — NỀN TẢNG

## I. NGUYÊN TẮC THIẾT KẾ (31 NGUYÊN TẮC BẤT BIẾN)

*(Nguyên tắc #1-29 giữ nguyên như bản v23 — xem lịch sử quyết định trong Phụ lục nội bộ; không lặp lại toàn văn ở đây để tránh trùng lặp tài liệu. Bổ sung 2 nguyên tắc mới:)*

| # | Nguyên tắc | Hệ quả thực tế |
|---|---|---|
| **30 ★v24** | **Không tạo DocType/engine mới nếu ERPNext core đã có khái niệm tương đương đúng bản chất** — chỉ mở rộng bằng Custom Field + Custom Doctype liên kết (Link) + Hook. Trước khi thiết kế bất kỳ DocType mới nào, phải trả lời: "Core đã có gì gần với cái này chưa, và tại sao không đủ?" | Áp dụng ngay: QC → `Quality Inspection`, Bảo hành → `Warranty Claim`, Chiết khấu → `Pricing Rule`, Lịch thanh toán → `Payment Schedule`, Duyệt version → `Workflow` — xem §III-B |
| **31 ★v24** | **Chi phí thực tế (actual cost) trong mọi báo cáo lãi lỗ PHẢI đọc từ GL Entry** (đã gắn `project` + `cost_center` + Accounting Dimension), **KHÔNG BAO GIỜ tính lại từ AL Cost Bucket** | AL Cost Bucket chỉ là cấu trúc *ước tính* trong công thức giá bán — không phải sổ kế toán. Tránh 2 nguồn sự thật (dual source of truth) — xem §XXXVII |

**Quyết định kiến trúc bổ sung (QĐ-28 → QĐ-30, ★v24):**

| Mã | Quyết định | Vấn đề giải quyết |
|---|---|---|
| **QĐ-28 ★v24** | **Thay AL Discount Rule bằng `Pricing Rule` (core)** + 1 hook validate tổng % chiết khấu trên Quotation, so với ngưỡng trong `AL Alert Config`, chặn submit nếu vượt trừ khi có `al_discount_approval_ref` | v23 tự làm lại discount stack trong khi core đã hỗ trợ đầy đủ tier theo Customer/Customer Group/Territory/Item Group + valid_from/valid_upto + priority. Được miễn phí: Coupon Code, Pricing Rule Log, áp dụng đồng bộ trên cả Quotation/SO/SI |
| **QĐ-29 ★v24** | **Thay AL Milestone Billing Plan/Line bằng `Payment Schedule` (core, child table trên Sales Order/Sales Invoice)** + thêm 2 custom field trên Payment Schedule: `al_trigger_type`, `al_trigger_value`, `al_is_released` để kiểm soát *khi nào* được phép xuất hóa đơn cho từng đợt | v23 tự làm lại toàn bộ lịch thanh toán trong khi core đã có Payment Schedule + engine xuất hóa đơn theo lịch + báo cáo công nợ/aging. Vấn đề thực sự cần giải quyết không phải "có lịch thanh toán" mà là "khi nào được phép bấm nút xuất hóa đơn" — đó là 2 field bổ sung, không phải 2 DocType mới |
| **QĐ-30 ★v24** | **Thay AL Quality Check bằng `Quality Inspection` (core)** + `Quality Inspection Template` riêng cho ngành (QC Cắt Kính, QC Lắp Cửa) + custom field `al_production_order_bridge` | Core đã có đầy đủ: bộ tiêu chí (Quality Inspection Parameter), Accepted/Rejected, gắn vào Stock Entry/Work Order. Không cần DocType QC riêng |
| **QĐ-31 ★v24** | **Thay AL Warranty Claim bằng `Warranty Claim` (core, module Support)** + custom field `al_installation_order`, `al_defect_category`, `al_warranty_policy` | Core đã có Customer/Item/Serial No/Complaint Date/Resolution/Status — chỉ thiếu 3 field đặc thù ngành |
| **QĐ-32 ★v24** | **Dùng `Workflow` (core) cho vòng đời Approval của `AL BOM Version` và `AL Dynamic Item Rule Version`** thay vì field `approval_status`/`approved_by` tự chế rải rác nhiều DocType | Được miễn phí: Approval Inbox ("My Approvals"), email tự động, Workflow Log audit, không cần code lại state machine |
| **QĐ-33 ★v24** | **Thêm `default_expense_account` (Link → Account) trên `AL Cost Bucket`** | Vá gap: trước đây Cost Bucket không trỏ tới Account nào, khiến Cost Variance Analysis phải tự dò ánh xạ. Giờ đối chiếu ước tính vs thực tế qua đúng Account |
| **QĐ-34 ★v24** | **Không tạo DocType Warehouse Location.** Vị trí lưu trữ vật lý (kệ/dãy) trong 1 Warehouse dùng custom field `al_bin_location` (Data) trên `Batch` và `Stock Entry Detail`. Warehouse Tree (core) chỉ dùng cho tách kho có ý nghĩa kế toán (theo khu vực vật tư hoặc theo công trình) | Tách bạch 2 khái niệm khác nhau: Warehouse = đơn vị kế toán tồn kho (ảnh hưởng valuation); Bin location = thông tin tìm kiếm vật lý (không ảnh hưởng giá trị) — xem §XXXVIII |
| **QĐ-35 ★v24** | **Change Order khi Approved sẽ tạo thêm 1 Sales Order bổ sung** (link cùng Project/Customer), không sửa trực tiếp giá trị hợp đồng gốc bằng con số cộng dồn thủ công | Giữ tính bất biến từng SO (Nguyên tắc #14); GL/Payment Schedule/Invoice tự động đi theo core |

---

## II. KIẾN TRÚC TỔNG THỂ — 8 TẦNG + 1 TẦNG AI (không đổi cấu trúc so với v23, chỉ đổi thành phần bên trong Tầng 6)

```
TẦNG 7 — AI LAYER (xuyên suốt qua AI Hooks Framework: after_calculate / before_quotation_submit / daily_ai_analysis)

TẦNG 6 — MODULE LAYER (Hook-based)
  6A Commercial : BOM Version Control (+Workflow core ★v24) · Pricing Rule (core, thay Discount Rule ★v24) ·
                  Notification & Alert · Sales Analytics · Reporting & Dashboard
  6B Supply     : Material Planning (MRP Lite) · Cost Variance Analysis · Supplier Price List
  6C Production : Cutting Standard/Plan · Site Survey · Quality Inspection (core, thay AL Quality Check ★v24) ·
                  Production Order Bridge (ERPNext Work Order)
  6D Field Ops  : Installation Order/Progress/Cost · Warranty Claim (core, thay AL Warranty Claim ★v24)
  6E Financial  : Payment Schedule (core, thay Milestone Billing ★v24) · Change Order (tạo SO bổ sung ★v24) ·
                  Handover Acceptance · Project Financial Config · Labor Cost Variance · Project Profitability Snapshot

TẦNG 5 — PRESENTATION (Frappe Web UI + Mobile)
TẦNG 4.5 — DYNAMIC ITEM RESOLVER
TẦNG 4 — ORCHESTRATION (aluglass.engine) — BomOrchestrator 9 bước, không đổi
TẦNG 3 — FORMULA ENGINE (formula_builder) — bất biến tuyệt đối, không đổi
TẦNG 2 — RULE ENGINE & VARIABLE BINDING — không đổi
TẦNG 1 — MASTER DATA
  ERPNext core: Item, Batch, Brand, Price List, Item Price, Item Group, Customer, Project, Cost Center,
                Accounting Dimension, Quality Inspection, Warranty Claim, Pricing Rule, Payment Schedule,
                Workflow, Employee, Work Order, Subcontracting Order...
  aluglass lõi: AL Glass Master, AL Profile Set/Line, AL PK Set/Line, AL BOM, AL Cost Template, ConfigSnapshot...
```

**Nguyên tắc kiến trúc cốt lõi (không đổi):** Tầng 1-4 giữ nguyên tuyệt đối. Tầng 6 là nơi duy nhất được mở rộng, và từ v24, mỗi module trong Tầng 6 phải khai báo rõ **"dùng core gì + custom field gì"** trước khi được phép tạo DocType mới (Nguyên tắc #30).

---

## III-B. BẢNG ÁNH XẠ "CORE THAY CUSTOM" — TRA CỨU NHANH ★v24

Đây là bảng quan trọng nhất của v24. Đội dev dùng bảng này để biết chính xác cái gì đã bị loại bỏ, cái gì thay thế.

| Custom DocType v23 (ĐÃ LOẠI BỎ) | Thay bằng Core | Custom field bổ sung trên Core | Lý do |
|---|---|---|---|
| ~~AL Quality Check~~ | `Quality Inspection` + `Quality Inspection Template` | `al_production_order_bridge` (Link) trên Quality Inspection | Core đã có gate Accepted/Rejected, tham số kiểm tra, lịch sử |
| ~~AL Warranty Claim~~ | `Warranty Claim` (module Support) | `al_installation_order`, `al_defect_category`, `al_warranty_policy` | Core đã có đủ Customer/Item/Complaint/Resolution/Status |
| ~~AL Discount Rule~~ + ~~AL Discount Rule Line~~ | `Pricing Rule` | *(không cần thêm field — dùng nguyên trạng)* | Core đã có tier, priority, valid_from, áp dụng đa chứng từ |
| ~~AL Milestone Billing Plan~~ + ~~AL Milestone Billing Line~~ | `Payment Schedule` (child table Sales Order/Sales Invoice) | `al_trigger_type` (Select), `al_trigger_value` (Data), `al_is_released` (Check) trên Payment Schedule | Core đã có lịch thanh toán + engine xuất hóa đơn theo lịch |
| *(field `approval_status` tự chế trên nhiều DocType)* | `Workflow` (Workflow State/Action) | Giữ `valid_from`, `snapshot_hash` (field nghiệp vụ); bỏ field điều khiển trạng thái tự chế | Core đã có Approval Inbox, Workflow Log |
| *(chưa có khái niệm)* | `Accounting Dimension` (tùy chọn, khai báo mới: "Product Type" hoặc "Brand") | — | Cho phép lọc P&L theo loại cửa/hệ nhôm mà không cần Cost Center ảo |
| *(ý tưởng "Warehouse Location" bị loại bỏ trước khi thiết kế)* | Warehouse Tree (core, chỉ cho tách kho có ý nghĩa kế toán) | `al_bin_location` (Data) trên `Batch` + `Stock Entry Detail` | Tránh nổ số lượng Warehouse như lỗi Item Variant theo màu |

**Những gì GIỮ NGUYÊN vì core không có khái niệm tương đương** (không đổi so với v23): AL BOM/Cost Template/Profile/PK Set/Line, ConfigSnapshot, AL Dynamic Item Rule (+Version), AL BOM Version, AL Cutting Standard/Plan, AL Site Survey, AL Change Order, AL Material Trace (field trên Batch), AL Supplier Price List, AL Project Profitability Snapshot, AL Color Standard, AL Installation Order/Progress/Cost, AL Labor Cost Variance, AL Project Financial Config, AL AI Suggestion Log/Interaction Log.

---

## III. DANH MỤC DOCTYPE (v24 — sau khi loại bỏ trùng lặp)

### Tầng 1 — Master Data: 24 DocType custom (giảm 0 — không đổi so với v23, các DocType Master vẫn cần)

*(Danh sách không đổi so với v23 — AL Variable Group, Material Type, Glass Type/Layer Type, Glass Master/Layer Line, Product Type, Variable Library/Set/Detail, Cost Bucket, Profile Line/Set, PK Set/Line, AL BOM, Cost Template/Line, ConfigSnapshot, Alert Config, Cutting Standard, Installation Team, Project Financial Config, AL Color Standard, AL Project Warehouse Map, AL Supplier Price List/Line — xem chi tiết trường ở PHẦN B)*

### Tầng 2 — Rule & Variable Binding: 10 DocType (không đổi)

*(AL Calculation Rule + 3 child, AL Dynamic Item Rule + Version + 2 child — không đổi so với v23; xem PHẦN C)*

### Tầng 6 — Module nghiệp vụ: **19 DocType custom (giảm từ 25 xuống 19 — loại bỏ 6 DocType: AL Quality Check, AL Warranty Claim, AL Milestone Billing Plan, AL Milestone Billing Line, AL Discount Rule, AL Discount Rule Line)**

| # | DocType | Nhóm | Trạng thái |
|---|---|---|---|
| 35 | AL BOM Version | 6A | Giữ, dùng Workflow core cho approval ★v24 |
| 36 | AL BOM Change Log | 6A | Giữ nguyên |
| 37-38 | AL Material Plan (+Line) | 6B | Giữ nguyên |
| 39 | AL Cost Variance | 6B | Giữ, đọc GL qua `default_expense_account` ★v24 |
| 40-41 | AL Dashboard Config, AL Sales KPI | 6A | **Khuyến nghị thay bằng Number Card/Dashboard Chart (core) — xem ghi chú §XXIII** |
| 42-45 | AL Aluminum/Glass Cutting Plan (+Line) | 6C | Giữ nguyên |
| 46-47 | AL Glass Cut Order/Line | 6C | Giữ nguyên |
| 48 | AL Production Order Bridge | 6C | Giữ, thêm field liên kết Quality Inspection ★v24 |
| 65-66 | AL Site Survey (+Line) | 6C | Giữ nguyên |
| ~~70~~ | ~~AL Quality Check~~ | 6C | **LOẠI BỎ ★v24 → dùng `Quality Inspection` core** |
| 49-51 | AL Installation Order/Line/Progress | 6D | Giữ nguyên |
| 52 | AL Installation Cost Actual | 6D | Giữ nguyên |
| ~~53~~ | ~~AL Warranty Claim~~ | 6D | **LOẠI BỎ ★v24 → dùng `Warranty Claim` core** |
| ~~54-55~~ | ~~AL Milestone Billing Plan/Line~~ | 6E | **LOẠI BỎ ★v24 → dùng `Payment Schedule` core + field** |
| 56 | AL Labor Cost Variance | 6E | Giữ nguyên |
| 57 | AL Project Profitability Snapshot | 6E | Giữ, khẳng định đọc GL (Nguyên tắc #31) |
| 67-68 | AL Change Order (+Line) | 6E | Giữ, hành vi Approve tạo SO bổ sung ★v24 |
| 69 | AL Handover Acceptance | 6E | Giữ nguyên |
| ~~33-34~~ | ~~AL Discount Rule (+Line)~~ | 6A | **LOẠI BỎ ★v24 → dùng `Pricing Rule` core** |

**Tổng DocType custom mới: 24 (Master) + 10 (Rule) + 19 (Module) + 2 (AI Governance) = 55 DocType** (giảm từ 70 xuống 55 — giảm ~21% khối lượng code phải viết/bảo trì, nhờ tận dụng 6 engine core).

---
---

# PHẦN B — TẦNG 1: MASTER DATA (chi tiết trường)

*(Toàn bộ §IV.1 → §IV.22 giữ nguyên 100% so với v23 — không có thay đổi kiến trúc ở các Master Data này. Xem lại bản v23 để tra cứu trường chi tiết của: AL Variable Group/Material Type/Glass Type/Glass Master/Product Type/Variable Library/Variable Set/Cost Bucket/Profile Line/Profile Set/PK Set/PK Line/AL BOM/Cost Template/ConfigSnapshot/Alert Config/Cutting Standard/Installation Team/Project Financial Config.)*

**Chỉ 1 thay đổi trong PHẦN B:**

### 4.11 AL Cost Bucket (Master) — BỔ SUNG FIELD ★v24

| fieldname | fieldtype | Mô tả |
|---|---|---|
| bucket_code | Data (unique) | VL_NHOM, VL_KINH, TONG_VL, GIA_THANH... |
| bucket_name | Data | |
| bucket_role | Select | LEAF / AGGREGATE |
| parent_bucket | Link → AL Cost Bucket | |
| sort_order | Int | |
| report_group | Data | "A. Vật liệu", "B. Nhân công"... |
| **`default_expense_account`** | **Link → Account** | **★v24 (QĐ-33).** Chỉ bắt buộc với `bucket_role=LEAF`. Dùng để đối chiếu chi phí ước tính (Cost Bucket, trong công thức giá) với chi phí thực tế (GL Entry qua Account này) trong Cost Variance Analysis (§XXI) — không cần bảng ánh xạ thủ công riêng |

*(§4.23, §4.24, §4.25 — Tồn kho màu Batch, Supplier Price List, Material Trace — giữ nguyên 100% so với v23, không có thay đổi kiến trúc.)*

### V. Custom Fields trên ERPNext core — BỔ SUNG ★v24

Ngoài các custom field đã có ở v23 (Item, Quotation Item, Sales Order Item, Quotation, Sales Order), v24 bổ sung:

#### 5.5 Batch (bổ sung so với §4.25 v23)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_bin_location | Data | ★v24 (QĐ-34). Vị trí vật lý trong kho (VD: "A1-03") — không ảnh hưởng valuation/kế toán, chỉ để tìm kiếm |

#### 5.6 Stock Entry Detail
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_bin_location | Data | ★v24. Ghi lại vị trí sau mỗi lần nhập/xuất/chuyển, phục vụ truy vết lịch sử vị trí nếu cần |

#### 5.7 Quality Inspection (core) — thay cho AL Quality Check ★v24
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_production_order_bridge | Link → AL Production Order Bridge | Liên kết ngược tới lệnh sản xuất |

#### 5.8 Warranty Claim (core) — thay cho AL Warranty Claim ★v24
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_installation_order | Link → AL Installation Order | |
| al_defect_category | Select | Thấm nước / Kẹt bản lề / Nứt kính / Khác |
| al_warranty_policy | Link → AL Warranty Policy | |

#### 5.9 Payment Schedule (core, child table Sales Order/Sales Invoice) — thay cho Milestone Billing ★v24
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_trigger_type | Select | PROGRESS_PCT / INSTALLED_M2 / HANDOVER_SIGNED / MANUAL |
| al_trigger_value | Data | VD: "50" (%) hoặc "120" (m²) — rỗng nếu MANUAL |
| al_is_released | Check | Mặc định 0. Hook tự động bật khi điều kiện `al_trigger_type` đạt — mở khóa nút "Create Sales Invoice against this schedule" (client-side validate, chặn nếu chưa release) |

#### 5.10 Sales Order (bổ sung so với v23)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_change_order_parent | Link → Sales Order | ★v24 (QĐ-35). Trỏ về SO gốc nếu SO này được sinh ra từ 1 AL Change Order đã duyệt |

---
---

# PHẦN C — TẦNG 2-3: RULE & FORMULA ENGINE

*(Không đổi so với v23 — §VII AL Calculation Rule, §VIII AL Dynamic Item Rule + Version, §IX Formula Variable Binding giữ nguyên toàn bộ. Chỉ 1 thay đổi về CƠ CHẾ DUYỆT:)*

## VIII-A. Vòng đời Version dùng Workflow (core) thay vì field tự chế ★v24 (QĐ-32)

Thay vì tự quản lý `status` (Draft/Pending Approval/Published/Deprecated/Rejected) bằng field Select và code Python kiểm tra chuyển trạng thái thủ công, v24 khai báo 1 **Workflow chuẩn** dùng chung cho cả `AL BOM Version` và `AL Dynamic Item Rule Version`:

**Workflow "Version Approval Workflow":**
```
Draft --(Submit for Approval)--> Pending Approval --(Approve)--> Published
                                        |
                                        +--(Reject)--> Rejected --(Revise)--> Draft
Published --(Publish New Version)--> Deprecated  [tự động, không qua Workflow Action thủ công]
```

- Field `status` trên cả 2 DocType đổi thành **Workflow State field** (do Frappe Workflow tự quản lý), field `workflow_state` là nguồn sự thật duy nhất.
- Vai trò `Director` được gán quyền thực hiện Workflow Action "Approve"/"Reject" (qua Workflow permission, không cần code kiểm tra Role thủ công).
- Giữ nguyên các field nghiệp vụ thuần túy: `valid_from`, `valid_to`, `snapshot_hash`, `snapshot_version`, `rule_snapshot_json`/`bom_snapshot_json` — đây là dữ liệu, không phải điều khiển luồng, nên không đưa vào Workflow.
- Chuyển `Published → Deprecated` khi có version mới Published **vẫn là hook tự động** (không phải Workflow Action do người dùng bấm) — giữ nguyên logic cũ, chỉ đổi cách quản lý 4 trạng thái đầu.

**Lợi ích tức thì:** Approval Inbox ("My Approvals" trong Frappe Desk) tự động liệt kê mọi `AL BOM Version`/`AL Dynamic Item Rule Version` đang chờ duyệt của từng Director — không cần code lại UI "hộp thư duyệt".

---
---

# PHẦN D — TẦNG 4-4.5: ORCHESTRATION

*(§X VariableResolver, §XI ProfileInterpreter, §XII PkResolver, §XIII Dynamic Item Resolver, §XIV CostAccumulator, §XV BomOrchestrator — giữ nguyên 100% so với v23. Đây là lõi bất biến, không bị ảnh hưởng bởi đợt tái cấu trúc Core-First vì không có phần nào trong Tầng 4 trùng với core ERPNext — tầng này là engine tính giá riêng của ngành, core không có khái niệm tương đương.)*

**BomOrchestrator — 9 bước (nhắc lại, không đổi):**

```
B0: VersionPinningResolver — resolve BOM Version + Rule Version theo valid_from (QĐ-26)
B1: VariableResolver — build inputs_dict
B2: DynamicItemResolver — resolve item cho dòng Rule/Formula mode
B3: ProfileInterpreter Pass 1 — scan, xây variable_registry
B4: ProfileInterpreter Pass 2 — build công thức đầy đủ
B5: PkResolver — resolve phụ kiện + override
B6: CostAccumulator — gom bucket_acc
B7: FormulaEngine.calculate() — tính DAG 1 lần duy nhất
B8: SnapshotBuilder.persist() — ghi ConfigSnapshot bất biến
```

Hooks A-D (sau B7/B8, không chặn luồng): Discount hiển thị (nay đọc trực tiếp từ Pricing Rule engine core — xem §XIX), Version badge, Notification.
Hooks E-F (khi Sales Order Submit): tạo AL Installation Order, tạo Payment Schedule mặc định (nay dùng core — xem §XXVII), đẩy vào Production Pool.

---
---

# PHẦN E — TẦNG 5: PRESENTATION

*(Không đổi so với v23 — BOM Dialog, Glass Selector, PK Panel, Sales Override Panel, Version Badge, Diff Viewer, Production Board, Installation Mobile Checklist, Project P&L Dashboard.*

**1 điểm bổ sung ★v24:** BOM Dialog hiển thị chiết khấu áp dụng đọc trực tiếp từ **Pricing Rule engine** (hàm `get_pricing_rule_for_item` của core) thay vì tự tính từ AL Discount Rule — giao diện người dùng không đổi, chỉ đổi nguồn dữ liệu backend.)*

---
---

# PHẦN F — TẦNG 6: MODULE NGHIỆP VỤ

## XVII. BOM Version Control

*(Giữ nguyên toàn bộ logic §XVII v23: valid_from/valid_to, snapshot_hash, Diff Tool `compare_versions()`. Thay đổi duy nhất: vòng đời 4 trạng thái đầu (Draft/Pending/Published/Rejected) nay do Workflow (core) quản lý — xem §VIII-A.)*

## XVIII. Approval Workflow

*(Đổi tên khái niệm: "Approval Workflow" từ v23 nay CHÍNH LÀ Workflow (core) áp dụng cho AL BOM Version, AL Dynamic Item Rule Version, và có thể mở rộng cho AL Change Order nếu cần nhiều cấp duyệt. Không còn là 1 module tự viết riêng.)*

**Mức duyệt chiết khấu vượt ngưỡng** (khác với duyệt Version) vẫn dùng cơ chế đơn giản: field `al_discount_approval_ref` (Data, ghi số phê duyệt thủ công hoặc link tới 1 bản ghi duyệt email/chat) trên Quotation — không cần Workflow đầy đủ cho trường hợp này vì tần suất thấp và cần linh hoạt.

## XIX. Chiết khấu — DÙNG `Pricing Rule` (CORE) ★v24 (QĐ-28)

### 19.1 Vì sao thay thế
AL Discount Rule (v23) tự làm lại: `rule_type` (CUSTOMER_TIER/PROJECT/VOLUME), `discount_pct`, `priority`, `requires_approval`. Toàn bộ tính năng này **Pricing Rule (core) đã có sẵn và mạnh hơn**:
- Áp theo Customer / Customer Group / Territory / Item / Item Group / Brand
- Tier theo số lượng (`Price Discount Scheme` với `min_qty`/`max_qty`)
- `valid_from`/`valid_upto`, `priority`, `disable`
- Áp dụng đồng bộ trên Quotation/Sales Order/Sales Invoice (v23 chỉ áp ở Quotation)
- Coupon Code (nếu sau này cần mã giảm giá theo chiến dịch)

### 19.2 Cấu hình thay thế bảng mẫu v23

| Pricing Rule (core) | Tương đương v23 |
|---|---|
| `Pricing Rule` với `applicable_for=Customer Group`, `discount_percentage` | DISC-RETAIL-STD |
| `Pricing Rule` với `applicable_for=Project` (qua Customer field custom hoặc Territory) | DISC-PROJECT-10, `priority=40` |
| `Price Discount Scheme` con của Pricing Rule, có `Pricing Rule Item Code`/tier theo `qty` | DISC-VOLUME-TIER (1-9=0%, 10-29=3%, 30-99=5%, ≥100=8%) |

### 19.3 Hook bổ sung: chặn tổng chiết khấu vượt ngưỡng

Vì Pricing Rule (core) cho phép cộng dồn nhiều rule (`priority` xác định thứ tự, không tự chặn tổng %), cần 1 validate hook riêng:

```
on Quotation.validate():
    total_discount_pct = tổng % discount đã áp dụng từ mọi Pricing Rule active trên Quotation
    threshold = AL Alert Config['DISCOUNT_EXCEEDED'].threshold_value  (mặc định 8%)
    if total_discount_pct > threshold and not al_discount_approval_ref:
        throw("Tổng chiết khấu {total_discount_pct}% vượt ngưỡng {threshold}%. Cần phê duyệt trước khi submit.")
```

### 19.4 Điều gì KHÔNG đổi
Cơ chế Sales Override (§QĐ-22, `allow_sales_override`/`override_item_group` trên Profile Line/PK Line) — đây là kiểm soát *chọn item*, khác hoàn toàn với *chiết khấu giá*, không liên quan tới Pricing Rule.

## XX. Material Planning (MRP Lite)

*(Không đổi so với v23 — §XX vẫn dùng logic (item gốc, color_code) 2 nhánh is_standard_stock, gắn `project` trên Material Request. Chỉ bổ sung: khi tạo Purchase Order từ MRP Lite, dòng PO kế thừa `al_bin_location` gợi ý mặc định nếu công ty có quy ước khu vực lưu kho theo loại vật tư — xem §XXXVIII.)*

## XXI. Cost Variance Analysis — BỔ SUNG NGUỒN DỮ LIỆU ★v24

*(Logic so sánh "giá Quotation vs giá Purchase" giữ nguyên. Bổ sung: mọi actual cost trong `AL Cost Variance` giờ truy vấn qua GL Entry lọc theo `Account = AL Cost Bucket.default_expense_account` (§4.11 QĐ-33) thay vì cộng dồn thủ công từ Purchase Invoice Item — đảm bảo khớp tuyệt đối với sổ cái kế toán, không lệch do làm tròn hoặc bỏ sót bút toán điều chỉnh.)*

## XXII. Notification & Alert Engine

*(Không đổi so với v23.)*

## XXIII. Sales Analytics / Reporting & Dashboard — GHI CHÚ KHUYẾN NGHỊ ★v24

`AL Dashboard Config` và `AL Sales KPI` (v23) có thể thay bằng tổ hợp core: `Number Card` (cho từng chỉ số KPI) + `Dashboard Chart` + `Dashboard` (gom theo vai trò) + `Workspace`. Chỉ giữ lại DocType custom nếu có logic tổng hợp phi chuẩn (ví dụ công thức KPI riêng biệt của ngành không biểu diễn được bằng Report Builder/Query Report). Khuyến nghị: thử dùng core trước, chỉ quay lại custom nếu chứng minh được giới hạn cụ thể.

## XXIV. Reporting & Dashboard
*(Không đổi.)*

## XXV. Module Sản Xuất (Cutting & Production)

*(§25.1 → §25.7 — Cutting Standard/Plan, Site Survey — giữ nguyên 100% so với v23.)*

### 25.8 Material Check Hook (không đổi logic, làm rõ theo P0 đã thống nhất)

3 điều kiện hard block trước khi Confirm Cutting Plan:
- (a) Batch đã có trong kho đủ số lượng
- (b) `deposit_status=Paid` cho màu `is_standard_stock=0`
- (c) PO/Subcontracting Order **đã Submit hoặc Approved** (không yêu cầu đã Receipt — nếu chờ Receipt sẽ thành vòng lặp, vì lúc Receipt xong thì điều kiện (a) đã tự động cover) cho dòng `is_outsourced=1`

**Quyền tắt `enforce_material_check`:** Field này nằm trên `AL Project Financial Config`, mặc định bật (giá trị 1). Quyền thay đổi field **chỉ dành cho vai trò Director** (thiết lập qua field-level permission, permlevel=1, chỉ Role Director có quyền write). Mọi thay đổi được ghi vào `AL BOM Change Log` (dùng chung cơ chế audit đã có, `target_doctype=AL Project Financial Config`) — không cần bảng log riêng.

### 25.9 Quality Gate — DÙNG `Quality Inspection` (CORE) ★v24 (QĐ-30)

**Thay thế hoàn toàn AL Quality Check.** Cấu hình:

1. Tạo `Quality Inspection Template` riêng cho ngành: "QC Cắt Kính" (tiêu chí: kích thước đúng dung sai, không nứt/mẻ cạnh, đúng độ dày), "QC Lắp Cửa" (tiêu chí: độ vuông góc, khe hở gioăng, vận hành trơn tru).
2. Mỗi template có các `Quality Inspection Parameter` tương ứng (Numeric hoặc Pass/Fail).
3. Custom field `al_production_order_bridge` (Link) trên `Quality Inspection` để liên kết ngược lệnh sản xuất.

**Luồng tạo tự động:**
```
Khi AL Glass Cut Order chuyển sang "Cut Done":
  → Hệ thống tự động tạo Quality Inspection (inspection_type=In Process,
     quality_inspection_template="QC Cắt Kính", reference_type/reference_name = Cut Order,
     al_production_order_bridge = <bridge tương ứng>, status=Pending)
  → QC nhập kết quả từng parameter → submit → status=Accepted/Rejected
```

**Gate bắt buộc:** `AL Production Order Bridge.production_stage` không được chuyển sang "Ready to Install" nếu Quality Inspection liên kết chưa `status=Accepted`. Nếu `Rejected` → tự động tạo cảnh báo (dùng `AL Alert Config`) cho Quản lý Sản xuất, không tự động tạo lại Cutting Plan (con người quyết định cắt lại hay xử lý khác).

**Lợi ích:** miễn phí báo cáo QC theo thời gian/theo đội, không cần code UI nhập kết quả QC riêng, tương thích luôn với Stock Entry/Purchase Receipt nếu sau này cần QC đầu vào vật tư từ NCC (dùng cùng 1 engine).

## XXVI. Module Thi Công (Field Operations)

*(§26.1 → §26.2 giữ nguyên. Làm rõ công thức §26.3 theo P0 đã thống nhất:)*

### 26.3 Công thức `cumulative_pct` (AL Installation Progress)

```
cumulative_pct = SUM(pct_completed_this_entry) của tất cả Progress entries đã ghi (append-only),
                 cap tại 100%
```
Không tính trung bình theo hạng mục — mỗi Progress entry ghi % hoàn thành tổng thể tại thời điểm đó, cộng dồn tuyệt đối (không phải trung bình).

## XXVII. Thanh Quyết Toán — DÙNG `Payment Schedule` (CORE) ★v24 (QĐ-29)

### 27.-1. Vì sao thay thế
`AL Milestone Billing Plan`/`Line` (v23) tự làm lại toàn bộ lịch thanh toán (due_date, %, số tiền) — chính xác là những gì `Payment Schedule` (core, có sẵn trên Sales Order/Sales Invoice) đã làm, kèm engine xuất hóa đơn theo lịch, báo cáo công nợ, aging report có sẵn.

### 27.0. Cấu hình mới: Payment Schedule + Trigger Condition

Khi Sales Order Submit (Hook E, §XV), hệ thống tự động tạo các dòng `Payment Schedule` dựa trên `AL BOM.default_milestone_billing_template` (JSON, ví dụ: `[{"pct": 30, "trigger": "MANUAL"}, {"pct": 40, "trigger": "PROGRESS_PCT", "value": 50}, {"pct": 25, "trigger": "INSTALLED_M2", "value": "ALL"}, {"pct": 5, "trigger": "HANDOVER_SIGNED"}]`), điền vào field core `invoice_portion`/`payment_amount`/`due_date` + field custom `al_trigger_type`/`al_trigger_value`/`al_is_released` (§V.5.9).

**Luồng release:**
```
Khi AL Installation Progress ghi nhận cumulative_pct đạt ngưỡng al_trigger_value (nếu trigger=PROGRESS_PCT)
  → Hook set al_is_released=1 cho dòng Payment Schedule tương ứng
Khi tổng m² lắp đặt (từ AL Installation Progress) đạt al_trigger_value (nếu trigger=INSTALLED_M2)
  → tương tự
Khi AL Handover Acceptance được ký (nếu trigger=HANDOVER_SIGNED)
  → tương tự
Nếu trigger=MANUAL → Sales/PM tự set al_is_released=1 thủ công (VD đợt tạm ứng ban đầu)
```

**Validate:** Client Script trên nút "Create Sales Invoice against this schedule" (tính năng core) kiểm tra `al_is_released=1` trước khi cho phép — nếu chưa release, hiển thị lý do (VD "Chưa đạt 50% tiến độ, hiện tại 32%").

### 27.0-B. AL Change Order — tạo Sales Order bổ sung ★v24 (QĐ-35)

**Thay đổi hành vi so với v23:** khi `AL Change Order` chuyển sang Approved (qua Workflow hoặc approval đơn giản tùy mức giá trị), hệ thống **không sửa trực tiếp một con số tổng hợp** mà:

1. Tự động tạo 1 **Sales Order mới** (`al_change_order_parent` trỏ về SO gốc, cùng `Customer`, cùng `Project`).
2. Các dòng trong SO mới lấy từ `AL Change Order Line` (thêm/bớt/đổi hạng mục), mỗi dòng có `new_bom_version` (nếu có, không đổi so với v23) làm căn cứ tính giá qua BomOrchestrator bình thường.
3. SO bổ sung có `Payment Schedule` riêng (thường 1 đợt duy nhất hoặc theo thỏa thuận riêng của phát sinh).
4. Báo cáo tổng giá trị hợp đồng = SUM(`grand_total`) của SO gốc + mọi SO có `al_change_order_parent` trỏ về nó — dùng Query Report, không lưu số tổng hợp tĩnh nào.

**Lợi ích:** Giữ tính bất biến (Nguyên tắc #14) cho từng SO; toàn bộ GL Entry, Payment Schedule, Sales Invoice đi theo đúng luồng chuẩn ERPNext, không có "con số ma" bị sửa tay.

## XXVIII. Module Kế Toán Lãi Lỗ (Project Profitability)

*(Giữ nguyên cấu trúc `AL Project Profitability Snapshot` — event-driven (PI/SE/Installation Cost submit) + scheduled weekly. Khẳng định lại theo Nguyên tắc #31 ★v24:)*

> **`actual_material_cost`, `actual_labor_cost`, `actual_overhead` trong Snapshot PHẢI truy vấn từ GL Entry** (lọc theo `project`, `cost_center`, và `Account` tương ứng — có thể dùng `default_expense_account` của Cost Bucket làm bộ lọc gợi ý, §QĐ-33), **không được cộng dồn lại từ AL Cost Bucket hay ConfigSnapshot**. ConfigSnapshot chỉ cung cấp số liệu **ước tính** (`estimated_material_cost`...) để tính `margin_drift_vs_quoted` — không phải nguồn actual.

`field-level permission` (permlevel=1) trên các field tài chính nhạy cảm — giữ nguyên như v23 (§28.8), không đổi.

---
---

# PHẦN G — TẦNG 7: AI

*(Không đổi so với v23 — AI Hooks Framework (QĐ-23), AL AI Suggestion Log, AL AI Interaction Log, ma trận AI-First. 1 ghi chú bổ sung: nếu dùng `daily_ai_analysis` cho AI Cutting Optimization (bài toán nesting 2D nặng), nên tách thành Background Job riêng của Frappe (`frappe.enqueue`, queue="long") thay vì chạy trong khung timeout 60s của hook chuẩn — tránh timeout giữa chừng.)*

---
---

# PHẦN H — VẬN HÀNH

## XXX. ConfigSnapshot & Audit Trail

*(Không đổi so với v23 — §4.17, bao gồm `compressed_snapshot`, `snapshot_version`, Schema Registry. Bổ sung 1 dòng làm rõ theo P1 đã thống nhất: Migration function được đăng ký vào 1 Python dict toàn cục `snapshot_migration_registry = {version: migrate_func}` trong module `aluglass`; `compare_versions()` kiểm tra `snapshot_version` của 2 snapshot, nếu khác nhau thì áp lần lượt các migrate_func theo thứ tự tăng dần trước khi diff; mọi migrate_func có unit test roundtrip.)*

## XXXI. Quy trình đầu-cuối (End-to-End)

*(Không đổi luồng nghiệp vụ tổng thể: Lead → Báo giá → Chốt đơn → Mua → SX → QC → Thi công → Thanh toán → Quyết toán. Cập nhật tên hệ thống dùng ở mỗi bước theo bảng ánh xạ core §III-B: bước "Chốt đơn" tạo Payment Schedule (không phải Milestone Billing Plan); bước "QC" dùng Quality Inspection; bước phát sinh dùng Change Order → tạo SO bổ sung.)*

## XXXII. Phân quyền & Vai trò

*(Không đổi bảng vai trò tổng thể. Bổ sung: quyền Approve trên `AL BOM Version`/`AL Dynamic Item Rule Version` nay cấu hình qua Workflow permission (Role Director gắn với Workflow State "Pending Approval" → action "Approve"/"Reject") thay vì kiểm tra Role bằng code Python.)*

## XXXIII. Ví dụ kiểm chứng

*(Giữ nguyên các kịch bản kiểm thử của v23, bổ sung kịch bản mới ★v24:*
- *Kiểm chứng: tạo Pricing Rule 3 tầng (Customer Group + Volume tier + Project) trên cùng 1 Quotation, xác nhận tổng discount áp đúng priority và hook chặn khi vượt ngưỡng 8% mà chưa có `al_discount_approval_ref`.*
- *Kiểm chứng: Payment Schedule tự động release đúng lúc `AL Installation Progress` đạt 50%, và bị khóa (không cho xuất hóa đơn) khi chưa đạt.*
- *Kiểm chứng: Quality Inspection Rejected → Production Order Bridge không chuyển "Ready to Install", cảnh báo đúng vai trò.*
- *Kiểm chứng: Change Order Approved → tạo đúng 1 SO mới với `al_change_order_parent` trỏ đúng SO gốc, tổng giá trị hợp đồng trên báo cáo bằng đúng tổng 2 SO.)*

## XXXIV. Lộ trình triển khai

| Phase | Nội dung | Ghi chú ★v24 |
|---|---|---|
| Phase 0 | Master Data + Rule/Formula Engine + BomOrchestrator | Không đổi |
| Phase 1 | BOM Version (+Workflow core), Material Check Hook, khóa SO field | Bổ sung cấu hình Workflow thay vì code approval |
| Phase 2 | Pricing Rule (thay Discount Rule), Payment Schedule (thay Milestone Billing), Site Survey, Change Order | **Thay đổi lớn nhất so với v23 — ưu tiên làm sớm để tránh phải migrate dữ liệu billing về sau** |
| Phase 3 | Quality Inspection (thay AL Quality Check), Warranty Claim (thay AL Warranty Claim), Cost Bucket → Account mapping | |
| Phase 4 | AI Layer, Dashboard (đánh giá dùng Number Card/Workspace trước khi code riêng) | |

## XXXV. Rủi ro & điểm theo dõi

*(Giữ nguyên 33 rủi ro của v23, bổ sung:)*

| # | Rủi ro mới ★v24 | Mức độ | Giải pháp |
|---|---|---|---|
| R34 | Nhân sự dev quen tự code, có thể vô tình tạo lại DocType trùng core trong tương lai (VD thêm tính năng mới lại không tra core trước) | P1 | Checklist bắt buộc trước khi tạo DocType mới: "Đã tra core chưa? Lý do core không đủ là gì?" — đưa vào code review template |
| R35 | Payment Schedule (core) có giới hạn UI so với Milestone Billing tự chế (VD không có màn hình riêng cho PM xem trực quan) | P2 | Có thể bổ sung Report Builder/Query Report riêng để hiển thị trực quan hơn, không cần custom DocType lưu trữ dữ liệu |

## XXXVI. Checklist Go-live

*(Giữ nguyên toàn bộ checklist v23, bổ sung các mục ★v24:)*

- [ ] Đã cấu hình Workflow "Version Approval Workflow" cho AL BOM Version và AL Dynamic Item Rule Version, test đủ 4 trạng thái
- [ ] Đã tạo Pricing Rule tương đương đầy đủ 3 loại discount cũ (Customer Group/Project/Volume), test tổng hợp đa tầng
- [ ] Đã cấu hình Payment Schedule + trigger condition cho ít nhất 1 AL BOM mẫu, test đủ 4 loại trigger (MANUAL/PROGRESS_PCT/INSTALLED_M2/HANDOVER_SIGNED)
- [ ] Đã tạo Quality Inspection Template "QC Cắt Kính" và "QC Lắp Cửa" với đầy đủ tham số, test luồng tự động tạo khi Cut Done
- [ ] Đã cấu hình custom field trên Warranty Claim (core), test luồng từ Installation Order
- [ ] Đã thêm `default_expense_account` cho toàn bộ AL Cost Bucket có `bucket_role=LEAF`
- [ ] Đã test Change Order Approved tạo đúng SO bổ sung, không sửa số liệu SO gốc
- [ ] Đã verify hành vi "Batch Wise Valuation" thực tế, phân biệt 2 lớp (a) vật lý (b) kế toán (kế thừa từ R27 v23)
- [ ] Đã xác nhận quyền tắt `enforce_material_check` giới hạn đúng Role Director, có audit log

## XXXVII. Cost Bucket vs Cost Center vs Accounting Dimension ★v24

Đây là phần thường bị nhầm lẫn nhất khi triển khai — cần quán triệt rõ cho cả đội dev và đội kế toán trước khi go-live.

### 37.1 Bản chất khác nhau

| | AL Cost Bucket | Cost Center (core) | Accounting Dimension (core) |
|---|---|---|---|
| Tầng | Tính giá / Ước tính (trước giao dịch) | Kế toán / GL thực tế | Mở rộng đa chiều cho GL Entry |
| Sống ở đâu | Formula Engine, ConfigSnapshot, Quotation | GL Entry, Journal Entry | GL Entry, Stock Ledger Entry |
| Có giao dịch tiền thật không | Không — thuần công thức | Có | Có |
| Trả lời câu hỏi | "Giá bán cấu thành từ đâu?" | "Chi phí thuộc bộ phận nào?" | "Lọc P&L theo chiều khác (VD loại sản phẩm) mà không tạo Cost Center ảo" |
| Ví dụ | VL_NHOM = 45tr (ước tính) | Xưởng sản xuất, Đội thi công 1 | Dimension "Product Type" để lọc lãi theo loại cửa |

### 37.2 Quy tắc bắt buộc

1. **Cost Bucket không bao giờ là nguồn actual cost.** Nó chỉ cấu thành công thức giá bán (baseline ước tính trong ConfigSnapshot). Xem Nguyên tắc #31.
2. **Cost Center đại diện cho bộ phận/đội, cố định, xuyên suốt nhiều dự án** (Xưởng, Đội thi công 1, Đội thi công 2, Kinh doanh). **Project đại diện cho từng công trình/hợp đồng**, thay đổi liên tục. Hai chiều này độc lập, luôn dùng song song trên mọi GL Entry.
3. **Nếu cần báo cáo lãi theo loại sản phẩm/hệ nhôm** (không phải theo bộ phận, không phải theo công trình) → khai báo 1 **Accounting Dimension mới** (VD "Product Type" hoặc "Brand", kế thừa giá trị từ Item/Sales Order Item khi GL Entry được tạo) — **không** map việc này qua Cost Bucket hay tạo thêm Cost Center ảo cho từng loại sản phẩm.
4. **Cost Bucket → Account** (qua `default_expense_account`, QĐ-33) là cầu nối duy nhất giữa 2 tầng — dùng để đối chiếu variance, không dùng để thay thế vai trò của Cost Center/Dimension trong báo cáo tài chính chính thức.

## XXXVIII. Warehouse & vị trí lưu kho ★v24

### 38.1 Nguyên tắc phân biệt

| Nhu cầu | Giải pháp |
|---|---|
| Tách kho có ý nghĩa kế toán (ảnh hưởng Stock Ledger/valuation) — theo khu vực vật tư (Kho Nhôm/Kho Kính/Kho PK) hoặc theo công trình | **Warehouse Tree (core)** — đã đúng ở §4.23.4 AL Project Warehouse Map, tạo warehouse con dạng `"NHOM - {project}"` |
| Biết vị trí vật lý (kệ/dãy) của 1 batch trong 1 Warehouse — chỉ để tìm nhanh, KHÔNG ảnh hưởng giá trị/kế toán | **Custom field `al_bin_location` (Data) trên Batch + Stock Entry Detail** — KHÔNG tạo Warehouse hay DocType riêng cho từng kệ |

### 38.2 Vì sao không dùng Warehouse Tree cho vị trí kệ

Nếu tạo 1 Warehouse cho mỗi kệ/rack, sẽ lặp lại đúng lỗi kiến trúc đã sửa ở §4.23 (Item Variant theo màu): số lượng Warehouse phình to theo số vị trí vật lý, và mỗi lần đổi chỗ để vật tư (không đổi chủ sở hữu/giá trị) lại bắt buộc phải làm Stock Entry (Material Transfer) — sai bản chất, vì đây không phải giao dịch kế toán.

### 38.3 Khi nào MỚI cần DocType riêng (`AL Bin Location`)

Chỉ cân nhắc khi thực sự cần: nhiều vị trí cho cùng 1 batch cùng lúc, pick-path tối ưu, reservation theo từng ô kệ, multi-bin putaway rule tự động. Đây là bài toán WMS (Warehouse Management System) chuyên sâu, ngoài phạm vi nhu cầu thực tế của ngành nhôm kính (thường chỉ cần biết "ở dãy nào" để công nhân tìm nhanh) — **không triển khai trong phạm vi v24**, để dành cho giai đoạn sau nếu công ty mở rộng quy mô kho lớn.

---

## PHỤ LỤC: TÓM TẮT THAY ĐỔI v23 → v24

| Hạng mục | v23 | v24 |
|---|---|---|
| Tổng số DocType custom | 70 | 55 (giảm ~21%) |
| Quản lý chiết khấu | AL Discount Rule (tự code) | Pricing Rule (core) + hook chặn ngưỡng |
| Lịch thanh toán | AL Milestone Billing Plan/Line (tự code) | Payment Schedule (core) + trigger field |
| QC | AL Quality Check (tự code) | Quality Inspection (core) + template ngành |
| Bảo hành | AL Warranty Claim (tự code) | Warranty Claim (core) + custom field |
| Duyệt version | Field tự chế (status/approved_by) | Workflow (core) |
| Cost Bucket ↔ kế toán | Không có cầu nối | `default_expense_account` (Link → Account) |
| Vị trí kho | Chưa thiết kế | `al_bin_location` trên Batch (không tạo Warehouse/DocType mới) |
| Change Order | Sửa số tổng hợp trực tiếp | Tạo Sales Order bổ sung, giữ bất biến |

**Kết luận:** v24 không thay đổi bất kỳ logic nghiệp vụ nào đã được xác nhận đúng qua các vòng review trước (tính giá, DAG, versioning, material check, site survey, cost variance, profitability). Thay đổi duy nhất là **cách hiện thực hóa 6 module** để tận dụng engine core sẵn có, giảm khối lượng code, giảm rủi ro bug, và được thừa hưởng miễn phí các tính năng báo cáo/audit/UI mà ERPNext đã xây dựng và kiểm chứng qua hàng nghìn triển khai thực tế trên toàn cầu.