# AlumGlass ERP — ĐẶC TẢ HỢP NHẤT (CANONICAL v25)

> **App:** `aluglass` (Frappe custom app trên ERPNext core) + phụ thuộc `formula_builder` (Formula Engine độc lập)
> **Phiên bản:** v25 — bản hợp nhất đầy đủ, tự thân (self-contained), không cần tham chiếu file khác. Đây là tài liệu duy nhất dùng để triển khai production.
> **Nguồn hợp nhất:** v25 được tạo bằng cách loại trùng lặp/rác giữa 3 bản nháp trước — v23 (lẫn nội dung chat/phân tích không liên quan ở đầu file và bị cắt cụt giữa câu ở cuối), v24 (chỉ là ghi chú thay đổi dạng diff, không tự đầy đủ), và v24 FINAL (bản hợp nhất tự thân) — đã đối chiếu từng mục để xác nhận không mất nội dung kỹ thuật, sau đó chuẩn hóa làm v25.
> **Triết lý cốt lõi:** Khai báo theo tư duy nghề, tính theo DAG, mở rộng theo module không phá lõi, tồn kho theo thực tế vật lý (Batch), kích thước theo thực tế công trình (Site Survey), phạm vi hợp đồng thay đổi có kiểm soát (Change Order), version có hiệu lực theo thời gian (valid_from), sản xuất không cắt khi chưa có hàng (Material Check), minh bạch từ báo giá tới quyết toán, AI luôn đề xuất không quyết định, **và không viết lại thứ ERPNext core đã làm tốt.**
> **Đánh dấu:** ★ = mới so với ERPNext/Frappe thuần. Các mốc lịch sử (v18…v24) không đánh dấu riêng lẻ trong v25 — mọi quyết định đã được hợp nhất thành 1 thiết kế thống nhất duy nhất.

---

## MỤC LỤC

- **PHẦN A — NỀN TẢNG:** I. Nguyên tắc thiết kế · II. Kiến trúc tổng thể · III. Danh mục DocType đầy đủ + bảng ánh xạ Core
- **PHẦN B — MASTER DATA:** IV. DocType nền tảng · V. Custom Fields trên ERPNext core · VI. Master Data mẫu
- **PHẦN C — RULE & FORMULA ENGINE:** VII. Calculation Rule · VIII. Dynamic Item Rule + Version + Workflow · IX. Formula Variable Binding
- **PHẦN D — ORCHESTRATION:** X. VariableResolver · XI. ProfileInterpreter · XII. PkResolver · XIII. Dynamic Item Resolver · XIV. CostAccumulator · XV. BomOrchestrator (9 bước)
- **PHẦN E — PRESENTATION:** XVI. BOM Dialog & UI Flow
- **PHẦN F — MODULE NGHIỆP VỤ:** XVII. BOM Version Control · XVIII. Approval (Workflow) · XIX. Chiết khấu (Pricing Rule) · XX. Material Planning · XXI. Cost Variance · XXII. Notification · XXIII. Analytics & Dashboard · XXIV. Reporting · XXV. Sản xuất (Cutting/QC/Site Survey) · XXVI. Thi công · XXVII. Thanh quyết toán (Payment Schedule/Change Order) · XXVIII. Kế toán lãi lỗ
- **PHẦN G — AI:** XXIX. Tầng AI toàn diện
- **PHẦN H — VẬN HÀNH:** XXX. ConfigSnapshot & Audit · XXXI. Quy trình đầu-cuối · XXXII. Phân quyền · XXXIII. Ví dụ kiểm chứng · XXXIV. Lộ trình triển khai · XXXV. Rủi ro · XXXVI. Checklist Go-live · XXXVII. Cost Bucket vs Cost Center vs Accounting Dimension · XXXVIII. Warehouse & vị trí lưu kho

---
---

# PHẦN A — NỀN TẢNG

## I. NGUYÊN TẮC THIẾT KẾ (31 NGUYÊN TẮC BẤT BIẾN)

| # | Nguyên tắc | Hệ quả thực tế |
|---|---|---|
| 1 | **Zero Python trong DB** — không formula/logic nào lưu dạng code Python thực thi trực tiếp | Đội kỹ thuật cấu hình BOM không cần biết lập trình |
| 2 | **Chọn Item trực tiếp (Fixed) hoặc gián tiếp qua Rule/Formula (Dynamic)** | Không có DocType "AL Product" trung gian — Item ERPNext là nguồn sự thật |
| 3 | **`show_condition` thay `if/elif`** | Biến thể sản phẩm = thêm 1 dòng, không sửa code |
| 4 | **1 bảng `al_lines` thống nhất** cho NHOM/KINH/VTP/PK, sort tự do | Vừa rõ ràng vừa linh hoạt, dễ audit |
| 5 | **DAG là nguồn sự thật về thứ tự tính toán** | FormulaEngine tự xây dựng đồ thị phụ thuộc; admin không cần khai theo thứ tự |
| 6 | **Kính đa tấm = tập hợp panel động** | 1 dòng khai báo → N panel sinh ra tại runtime (vách nhiều ô) |
| 7 | **Giá kính tách khỏi kích thước sản xuất** | Giá = m² × đơn giá đại diện; kích thước cắt thực tế là phép biến đổi riêng (§XXV) |
| 8 | **Phụ kiện: mặc định + thay thế có kiểm soát** | PK Set chuẩn + Sales override trong nhóm được phép |
| 9 | **Phụ thuộc chéo Nhôm↔Kính qua context phẳng** | `glass_thick_{prefix}` inject trước vào inputs, không gây circular dependency |
| 10 | **Rule là thư viện dùng chung** | Khai báo 1 lần, tái sử dụng nhiều BOM |
| 11 | **FormulaEngine là engine tính toán DUY NHẤT** | Không `eval()` rời rạc ở bất kỳ đâu |
| 12 | **Minh bạch tuyệt đối** | Mọi con số đều `explain()` được, từ giá bán tới lãi/lỗ dự án |
| 13 | **Module độc lập, hook không phá lõi** | Mọi tính năng mới đăng ký hook, không sửa Orchestrator |
| 14 | **Version = immutable snapshot** | Áp dụng cho BOM, Rule, và mọi cấu hình ảnh hưởng giá/chi phí đã cam kết |
| 15 | **Approval trước khi hiệu lực** | BOM mới, Rule mới, giá đặc biệt, discount lớn đều qua duyệt |
| 16 | **DynamicItemResolver dùng FormulaEngine.evaluate_single()** | Không tự xây eval sandbox riêng |
| 17 | **Formula Variable Binding (FB) thay AL Variable Binding cũ** | Dùng DAG topology của FB thay vì priority thủ công |
| 18 | **AL Calculation Rule — tinh gọn, không xóa loại rule cũ** | THRESHOLD/LOOKUP giữ bảng trực quan; CONSTANT/FORMULA có thể migrate sang FB Global Variable |
| 19 | **Cost Template + Formula Set — optional, có fallback** | Không bắt buộc migrate toàn bộ cùng lúc |
| 20 | **AL Dynamic Item Rule = immutable versioned** | Sửa Rule không ảnh hưởng tức thì tới Quotation đang mở |
| 21 | **AI luôn là đề xuất, không tự ghi vào bất kỳ snapshot/version nào** | Mọi output AI đi qua `AL AI Suggestion Log` rồi Approval |
| 22 | **Màu (nhôm/phụ kiện) là thuộc tính GIAO DỊCH (Batch + Project), KHÔNG BAO GIỜ là trục biến thể (Attribute) của Item Master** | Tránh nổ Item ảo — xem §IV.23 |
| 23 | **Mọi dữ liệu vận hành phải sinh ra ở dạng "sạch cho AI học"** | Feedback loop bắt buộc cho `AL AI Suggestion Log` |
| 24 | **Sales Override phải được kiểm soát tường minh** | `allow_sales_override` + `override_item_group` trên từng dòng — chặn override sai nhóm vật liệu |
| 25 | **AI là trợ lý, không thay thế con người** | Mọi đề xuất AI cần xác nhận người có thẩm quyền |
| 26 | **Kích thước tính giá ≠ kích thước sản xuất tại công trình thực** | Sai lệch vượt dung sai khảo sát phải chặn Cutting Plan, bắt buộc đi qua BOM Version mới |
| 27 | **Mọi thay đổi phạm vi hợp đồng sau chốt phải qua Change Order có duyệt** | Không ai sửa trực tiếp giá trị hợp đồng |
| 28 | **Không cắt khi chưa có hàng** — Material Check Hook (hard block) trước Cutting Plan Confirm | Vá lỗ hổng dây chuyền: cắt khi batch chưa về → trễ tiến độ, âm tồn kho ảo |
| 29 | **Version BOM/Rule có hiệu lực theo thời gian (`valid_from`/`valid_to`)**, không đọc `current_version` sống tại runtime | Quotation Draft luôn dùng đúng version tại thời điểm tạo, không bị "giá nhảy" |
| **30** | **Không tạo DocType/engine mới nếu ERPNext core đã có khái niệm tương đương đúng bản chất** | Trước khi thiết kế DocType mới: "Core đã có gì gần với cái này chưa, và tại sao không đủ?" |
| **31** | **Chi phí thực tế (actual cost) trong mọi báo cáo lãi lỗ PHẢI đọc từ GL Entry**, KHÔNG BAO GIỜ tính lại từ AL Cost Bucket | AL Cost Bucket chỉ là cấu trúc ước tính trong công thức giá — không phải sổ kế toán |

**Quyết định kiến trúc (QĐ-1 → QĐ-35, các quyết định vận hành/kỹ thuật quan trọng):**

| Mã | Quyết định | Vấn đề giải quyết |
|---|---|---|
| QĐ-6 | Màu nhôm là biến định giá qua Rule LOOKUP (surcharge), không phải Item Variant | Cơ sở cho toàn bộ §4.23 |
| QĐ-21 | **ConfigSnapshot Compressed** — `compressed_snapshot` (gzip base64) song song `enterprise_snapshot_json` | Giảm 70-80% dung lượng lưu trữ |
| QĐ-22 | **Sales Override Kiểm Soát** — `allow_sales_override` + `override_item_group` trên Profile Line/PK Line | Chặn override sai loại vật liệu |
| QĐ-23 | **AI Hooks Framework** — 3 hook chuẩn: `after_calculate` (10s), `before_quotation_submit` (5s), `daily_ai_analysis` (60s, nên tách Background Job nếu nặng) | Thống nhất cách AI cắm vào hệ thống, không chặn luồng chính |
| QĐ-24 | **CostAccumulator v2 — Fallback Logging** | Log mọi lần Formula Set lỗi phải fallback; >3 lần/ngày → CRITICAL alert |
| QĐ-25 | **DynamicItemResolver v2** — đọc `rule.current_version.rule_snapshot_json` (bất biến), tích hợp Sales Override | Không phá vỡ tính bất biến của Quotation cũ |
| QĐ-26 | **Version resolve theo `valid_from`** — BomOrchestrator dùng `Quotation.creation_date` so với `valid_from`, không đọc `current_version` sống | Đơn giản, deterministic, tái dùng pattern Item Price |
| QĐ-27 | **Material Check Hook (hard block)** — 3 điều kiện: batch đủ tồn kho, deposit đã trả, PO/Subcontracting đã đặt | Confirm khi chưa có hàng là không thể đảo ngược |
| **QĐ-28** | **Chiết khấu dùng `Pricing Rule` (core)** + hook validate tổng % vượt ngưỡng | Core đã có tier/priority/valid_from — không tự viết lại |
| **QĐ-29** | **Lịch thanh toán dùng `Payment Schedule` (core)** + field `al_trigger_type/al_trigger_value/al_is_released` | Core đã có engine xuất hóa đơn theo lịch, aging report |
| **QĐ-30** | **QC dùng `Quality Inspection` (core)** + Template riêng ngành + field liên kết Production Order Bridge | Core đã có gate Accept/Reject, tham số kiểm tra |
| **QĐ-31** | **Bảo hành dùng `Warranty Claim` (core)** + 3 custom field | Core đã có Customer/Item/Complaint/Resolution |
| **QĐ-32** | **Duyệt Version dùng `Workflow` (core)** thay field tự chế | Miễn phí Approval Inbox, Workflow Log |
| **QĐ-33** | **`default_expense_account` trên AL Cost Bucket** (Link → Account) | Cầu nối duy nhất giữa ước tính và GL thực tế |
| **QĐ-34** | **Không tạo DocType Warehouse Location** — dùng `al_bin_location` (Data) trên Batch/Stock Entry Detail | Tránh nổ số lượng Warehouse như lỗi Item Variant |
| **QĐ-35** | **Change Order Approved → tạo Sales Order bổ sung** (không sửa số liệu SO gốc) | Giữ tính bất biến từng SO (Nguyên tắc #14) |

---

## II. KIẾN TRÚC TỔNG THỂ — 8 TẦNG + 1 TẦNG AI XUYÊN SUỐT

```
TẦNG 7 — AI LAYER (xuyên suốt qua AI Hooks Framework: after_calculate / before_quotation_submit / daily_ai_analysis)
  AI Formula/Rule Generator · AI Config Validator · AI PK Suggester · AI Drawing-to-BOM
  AI Quotation Copilot · AI Pricing/Negotiation Advisor · AI Win/Loss Analysis · AI Cutting Optimization
  AI Purchasing/Price Forecast · AI Voice-to-Progress · AI Root Cause Clustering
  AI Project Health Score · AI Anomaly Detection · AI Trợ lý tri thức nội bộ (RAG)
  ⇒ Đề xuất ghi vào AL AI Suggestion Log · Tra cứu ghi vào AL AI Interaction Log

TẦNG 6 — MODULE LAYER (Hook-based, đăng ký qua hooks.py, không sửa Tầng 3-4)
  6A Commercial : BOM Version Control (+Workflow core) · Pricing Rule (core) · Notification & Alert ·
                  Sales Analytics · Reporting & Dashboard
  6B Supply     : Material Planning (MRP Lite) · Cost Variance Analysis · Supplier Price List
  6C Production : Cutting Standard/Plan (1D+2D) · Site Survey · Quality Inspection (core) ·
                  Production Order Bridge (ERPNext Work Order)
  6D Field Ops  : Installation Order/Progress/Cost · Warranty Claim (core)
  6E Financial  : Payment Schedule (core) · Change Order (→ SO bổ sung) · Handover Acceptance ·
                  Project Financial Config · Labor Cost Variance · Project Profitability Snapshot

TẦNG 5 — PRESENTATION (Frappe Web UI + Mobile)
  BOM Dialog · Glass Selector · PK Panel · Sales Override Panel · Version Badge ·
  Approval Inbox (core) · Diff Viewer · Production Board · Installation Mobile Checklist · Project P&L Dashboard

TẦNG 4.5 — DYNAMIC ITEM RESOLVER (Pre-Resolution Phase, trước DAG)
  Fixed / Rule (versioned) / Formula mode · item cache · batch DB lookup · sales override validate

TẦNG 4 — ORCHESTRATION (aluglass.engine)
  VariableResolver v3 · ProfileInterpreter v2 (2-pass) · PkResolver ·
  CostAccumulator v2 · SnapshotBuilder · BomOrchestrator — 9 bước (§XV)

TẦNG 3 — FORMULA ENGINE (formula_builder) — KHÔNG SỬA, bất biến tuyệt đối
  FormulaEngine: DAG · IncrementalContext · explain() · snapshot_with_trace() · evaluate_single()
  BASE_FUNCS 80+ · FormulaValidator · SecurityValidator

TẦNG 2 — RULE ENGINE & VARIABLE BINDING
  AL Calculation Rule (CONSTANT/FORMULA/THRESHOLD/LOOKUP/SEQUENCE)
  AL Dynamic Item Rule + AL Dynamic Item Rule Version (Workflow-managed)
  Formula Variable Binding (bom_variable, rule_engine_lookup)
  Pricing Rule (core, thay AL Discount Rule)

TẦNG 1 — MASTER DATA
  ERPNext core: Item, Batch, Brand, Price List, Item Price, Item Group, Customer, Project, Cost Center,
                Accounting Dimension, Quality Inspection, Warranty Claim, Pricing Rule, Payment Schedule,
                Workflow, Employee, Work Order, Subcontracting Order, Warehouse...
  aluglass lõi: AL Glass Master, AL Profile Set/Line, AL PK Set/Line, AL BOM, AL Cost Template, ConfigSnapshot...
  aluglass mở rộng: AL Cutting Standard, AL Installation Team, AL Warranty Policy, AL Project Financial Config,
                     AL Color Standard, AL Project Warehouse Map (tùy chọn)
```

**Quyết định kiến trúc cốt lõi:** Toàn bộ nghiệp vụ Sản xuất/Thi công/Quyết toán/Tài chính dự án nằm trong **Tầng 6** dưới dạng module hook. Tầng 1-4 giữ nguyên tuyệt đối qua mọi giai đoạn mở rộng. Từ mỗi module Tầng 6, quy tắc bắt buộc: **dùng core trước, chỉ custom phần core không có.**

---

## III. DANH MỤC DOCTYPE ĐẦY ĐỦ (55 DocType custom + Core được tái sử dụng)

### Tầng 1 — Master Data (24 DocType custom)

| # | DocType | Mô tả ngắn |
|---|---|---|
| 1 | AL Variable Group | Nhóm biến (Kích thước, Số lượng, Vật liệu...) |
| 2 | AL Material Type | Loại vật tư + phương pháp tính (kg/m², m², cái, mét) |
| 3 | AL Glass Type | Phân loại kính (đơn, cường lực, hộp, Low-E, laminate) |
| 4 | AL Glass Layer Type | Loại lớp kính (Phase nâng cao) |
| 5 | AL Glass Master | Thông số kỹ thuật kính, nguồn `glass_thick` |
| 6 | AL Glass Layer Line | Child — cấu trúc lớp kính chi tiết |
| 7 | AL Product Type | Loại sản phẩm (cửa đi, cửa sổ, vách kính...) |
| 8 | AL Variable Library | Thư viện biến toàn cục |
| 9 | AL Variable Set | Tập biến cho 1 loại BOM |
| 10 | AL Variable Set Detail | Child — dòng con Variable Set |
| 11 | AL Cost Bucket | Tài khoản chi phí (LEAF/AGGREGATE), có `default_expense_account` |
| 12 | AL Profile Line | Child — dòng vật tư thống nhất, trung tâm hệ thống |
| 13 | AL Profile Set | Tập hợp `al_lines` |
| 14 | AL PK Set | Bộ phụ kiện tái sử dụng |
| 15 | AL PK Line | Child — dòng phụ kiện |
| 16 | AL BOM | Liên kết Variable Set + Profile Set + PK Set + Cost Template |
| 17 | AL Cost Template | Master — công thức tính giá thành |
| 18 | AL Cost Template Line | Child — dòng chi phí |
| 19 | ConfigSnapshot | Audit trail bất biến cho mỗi lần tính giá |
| 20 | AL Alert Config | Cấu hình cảnh báo |
| 21 | AL Cutting Standard | Quy cách cắt chuẩn (phôi, dung sai, dung sai khảo sát) |
| 22 | AL Installation Team | Đội thi công |
| 23 | AL Warranty Policy | Chính sách bảo hành (policy — khác Warranty Claim của core) |
| 24 | AL Project Financial Config | Cấu hình phân bổ overhead + `enforce_material_check` |
| 25 | AL Color Standard | Danh mục màu chuẩn (RAL/vân gỗ) — thuộc tính giao dịch qua Batch |
| 26 | AL Project Warehouse Map | Ánh xạ kho tạm theo dự án (tùy chọn) |
| 27 | AL Supplier Price List | Bảng giá NCC theo brand/hệ profile |
| 28 | AL Supplier Price List Line | Child — từng dòng đơn giá NCC |

### Tầng 2 — Rule & Variable Binding (10 DocType custom)

| # | DocType | Mô tả |
|---|---|---|
| 29 | AL Calculation Rule | CONSTANT/FORMULA/THRESHOLD/LOOKUP/SEQUENCE |
| 30 | AL Rule Threshold Row | Child — bảng ngưỡng |
| 31 | AL Rule Lookup Row | Child — bảng tra cứu |
| 32 | AL Rule Sequence Item | Child — danh sách rule con |
| 33 | AL Dynamic Item Rule | Rule chọn Item (THRESHOLD/LOOKUP), quản lý qua Workflow |
| 34 | AL Dynamic Item Threshold Row | Child — ngưỡng số → item |
| 35 | AL Dynamic Item Lookup Row | Child — cặp key → item |
| 36 | AL Dynamic Item Rule Version | Snapshot bất biến của Rule |
| — | *(Pricing Rule — dùng core, không tạo DocType)* | Thay AL Discount Rule |
| — | *(Formula Variable Binding — thuộc app formula_builder)* | |

*(Đếm 8 DocType thực + 2 dòng ghi chú core)*

### Tầng 6 — Module nghiệp vụ (19 DocType custom)

| # | DocType | Nhóm | Mô tả |
|---|---|---|---|
| 37 | AL BOM Version | 6A | Snapshot bất biến BOM, quản lý qua Workflow |
| 38 | AL BOM Change Log | 6A | Nhật ký thay đổi (dùng chung BOM & Rule version, kể cả thay đổi `enforce_material_check`) |
| 39 | AL Material Plan | 6B | Kế hoạch vật tư tổng hợp |
| 40 | AL Material Plan Line | 6B | Dòng vật tư trong kế hoạch |
| 41 | AL Cost Variance | 6B | So sánh giá Quotation vs GL Entry thực tế |
| 42 | AL Aluminum Cutting Plan | 6C | Kế hoạch cắt nhôm tối ưu (1D) |
| 43 | AL Aluminum Cutting Plan Line | 6C | Từng đoạn cắt + phế liệu |
| 44 | AL Glass Cutting Plan | 6C | Kế hoạch cắt kính tối ưu (2D nesting) |
| 45 | AL Glass Cutting Plan Line | 6C | Từng tấm cắt |
| 46 | AL Glass Cut Order | 6C | Lệnh cắt gắn SO cụ thể |
| 47 | AL Glass Cut Line | 6C | Chi tiết tấm cắt |
| 48 | AL Production Order Bridge | 6C | Cầu nối ERPNext Work Order + liên kết Quality Inspection |
| 49 | AL Site Survey | 6C | Cổng đối chiếu kích thước thực tế công trình vs ConfigSnapshot |
| 50 | AL Site Survey Line | 6C | Từng hạng mục đo thực tế + độ lệch |
| 51 | AL Installation Order | 6D | Lệnh thi công |
| 52 | AL Installation Order Line | 6D | Hạng mục thi công |
| 53 | AL Installation Progress | 6D | Nhật ký tiến độ (append-only) |
| 54 | AL Installation Cost Actual | 6D | Chi phí thi công thực tế |
| 55 | AL Labor Cost Variance | 6E | Variance nhân công/thi công |
| — | AL Project Profitability Snapshot | 6E | P&L bất biến theo dự án *(đếm ở #56)* |
| — | AL Change Order | 6E | Phát sinh công trình có duyệt *(đếm ở #57)* |
| — | AL Change Order Line | 6E | Từng hạng mục phát sinh + `new_bom_version` *(đếm ở #58)* |
| — | AL Handover Acceptance | 6E | Biên bản nghiệm thu khách hàng ký *(đếm ở #59)* |

*(56-59: AL Project Profitability Snapshot, AL Change Order, AL Change Order Line, AL Handover Acceptance)*

### Tầng 7 — AI Governance (2 DocType)

| # | DocType | Mô tả |
|---|---|---|
| 60 | AL AI Suggestion Log | Ghi nhận mọi đề xuất AI cần Approval |
| 61 | AL AI Interaction Log | Ghi nhận tương tác tra cứu (RAG_QUERY/VOICE_INPUT/IMAGE_ANALYSIS) |

**Tổng: 61 DocType custom được đánh số + trường bổ sung `Quotation.al_loss_reason`.** *(Lưu ý: một vài DocType nhỏ như AL Rule Sequence Item có thể được đánh số linh hoạt tùy công cụ quản lý dự án của đội dev — con số quan trọng là **giảm khoảng 21% khối lượng so với cách làm tự-code-mọi-thứ (70 DocType)** nhờ 6 module dùng core.)*

### III-B. BẢNG ÁNH XẠ "CORE THAY CUSTOM" — GHI NHỚ BẮT BUỘC

| Nhu cầu nghiệp vụ | Dùng Core ERPNext | Custom field bổ sung |
|---|---|---|
| Kiểm tra chất lượng (QC) | `Quality Inspection` + `Quality Inspection Template` | `al_production_order_bridge` (Link) |
| Bảo hành công trình | `Warranty Claim` (module Support) | `al_installation_order`, `al_defect_category`, `al_warranty_policy` |
| Chiết khấu / khuyến mãi | `Pricing Rule` | *(không cần thêm field)* |
| Lịch thanh toán theo đợt | `Payment Schedule` (child table Sales Order/Sales Invoice) | `al_trigger_type`, `al_trigger_value`, `al_is_released` |
| Duyệt version (BOM/Rule) | `Workflow` (Workflow State/Action) | Giữ `valid_from`, `snapshot_hash` (dữ liệu nghiệp vụ) |
| Lọc P&L theo loại sản phẩm/hệ nhôm | `Accounting Dimension` (khai báo mới, VD "Product Type") | — |
| Vị trí vật lý trong kho (kệ/dãy) | *(không dùng Warehouse)* | `al_bin_location` (Data) trên `Batch` + `Stock Entry Detail` |
| Tách kho theo khu vực/công trình | `Warehouse` (Tree, core) | *(dùng `AL Project Warehouse Map` để tự động tạo warehouse con)* |
| Tồn kho theo Item + màu | `Batch` + `Batch Wise Valuation` (core) | `al_color`, `al_source_project`, `al_is_reserved_for_project`, `al_trace_stage`, `al_trace_last_updated`, `al_bin_location` |
| Sản xuất | `Work Order` (qua AL Production Order Bridge) | — |
| Mua hàng | `Purchase Order/Receipt/Invoice`, `Subcontracting Order` | `color_code`, `project` trên dòng PO (đã có sẵn qua Project field) |
| Dashboard/KPI | `Number Card`, `Dashboard Chart`, `Workspace` | *(khuyến nghị dùng trước khi tạo AL Dashboard Config riêng)* |

**Những gì PHẢI custom vì core không có khái niệm tương đương:** AL BOM/Cost Template/Profile/PK Set/Line, ConfigSnapshot, AL Dynamic Item Rule (+Version), AL BOM Version, AL Cutting Standard/Plan, AL Site Survey, AL Change Order, AL Material Trace (field trên Batch), AL Supplier Price List, AL Project Profitability Snapshot, AL Color Standard, AL Installation Order/Progress/Cost, AL Labor Cost Variance, AL Project Financial Config, AL AI Suggestion/Interaction Log — đây là phần "chất xám" thực sự của hệ thống, chiếm phần lớn công sức triển khai.

---
---

# PHẦN B — TẦNG 1: MASTER DATA (ĐẦY ĐỦ TRƯỜNG)

## IV.1 AL Variable Group (Master)
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| group_code | Data | ✓ unique | KICH_THUOC, SO_LUONG, VAT_LIEU, CANH_CUA, VACH |
| group_name | Data | | |
| sort_order | Int | | |

## IV.2 AL Material Type (Master)
| fieldname | fieldtype | reqd |
|---|---|---|
| type_code | Data | ✓ unique — NHOM_PROFILE, KINH, VTP, PHU_KIEN |
| type_name | Data | |
| default_bucket | Link → AL Cost Bucket | |
| calc_method | Select | BY_KG_M / BY_M2 / BY_UNIT / BY_METER |

## IV.3 AL Glass Type (Master)
| fieldname | fieldtype |
|---|---|
| type_code | Data (unique) — DON, CUONG_LUC, HOP, LOWE, LAM |
| type_name | Data |

## IV.4 AL Glass Layer Type (Master)
| fieldname | fieldtype |
|---|---|
| layer_code | Data (unique) — GLASS, AIR_GAP, INTERLAYER |
| layer_name | Data |

## IV.5 AL Glass Master (Master) — nguồn `glass_thick`
| fieldname | fieldtype | Mô tả |
|---|---|---|
| glass_code | Data (unique) | KINH-DON-8, KINH-CL-10, KINH-HOP-24... |
| glass_name | Data | |
| **total_thick_mm** | Float | **Nguồn gốc `glass_thick_{prefix}`** |
| glass_type | Link → AL Glass Type | |
| has_complex_structure | Check | Bật nếu có glass_layers |
| u_value / shgc / vlt | Float | Thông số nhiệt/quang (nâng cao) |
| glass_layers | Table → AL Glass Layer Line | Cấu trúc lớp (nâng cao) |

## IV.6 AL Glass Layer Line (Child của IV.5)
| fieldname | fieldtype |
|---|---|
| sort_order | Int (reqd) |
| layer_type | Link → AL Glass Layer Type (reqd) |
| thickness_mm | Float |
| description | Small Text |

## IV.7 AL Product Type (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| type_code | Data (unique) | CUA_DI, CUA_SO, CUA_LUA, CUA_MAT_HAT, VACH_KINH |
| type_name | Data | |
| nc_pct | Float (default 12) | % nhân công sản xuất mặc định |
| nc_ld_rate | Currency | Đơn giá nhân công lắp đặt (đ/m²) |
| default_warranty_policy | Link → AL Warranty Policy | |
| default_milestone_billing_template | JSON | Template % các đợt thanh toán + trigger (dùng cho Payment Schedule, §XXVII) |
| description | Small Text | |

## IV.8 AL Variable Library (Master)
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

## IV.9 AL Variable Set (Master)
| fieldname | fieldtype |
|---|---|
| set_code | Data (unique) |
| set_name | Data |
| al_var_details | Table → AL Variable Set Detail |

## IV.10 AL Variable Set Detail (Child)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| variable | Link → AL Variable Library (reqd) | |
| is_required | Check | |
| override_default | Data | |
| depends_on | Code | Điều kiện hiển thị |
| sort_order | Int | |

## IV.11 AL Cost Bucket (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| bucket_code | Data (unique) | VL_NHOM, VL_KINH, TONG_VL, GIA_THANH... |
| bucket_name | Data | |
| bucket_role | Select | LEAF / AGGREGATE |
| parent_bucket | Link → AL Cost Bucket | |
| sort_order | Int | |
| report_group | Data | "A. Vật liệu", "B. Nhân công"... |
| **`default_expense_account`** | **Link → Account** | **Chỉ bắt buộc với `bucket_role=LEAF`. Cầu nối duy nhất giữa Cost Bucket (ước tính) và GL Entry (thực tế) — dùng trong Cost Variance Analysis (§XXI) và validate ở §XXXVII** |

## IV.12 AL Profile Line (Child của AL Profile Set) ★ TRUNG TÂM HỆ THỐNG

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
| item_selection_mode | Select | | Fixed / Rule / Formula |
| item_rule | Link → AL Dynamic Item Rule | | Dùng khi mode = Rule |
| item_condition_formula | Small Text | | Dùng khi mode = Formula |
| item_fallback | Link → Item | | Bắt buộc nếu mode ≠ Fixed |
| allow_sales_override | Check | | Mặc định 1 cho NHOM/VTP, 0 cho PK |
| override_item_group | Link → Item Group | | Giới hạn nhóm Item Sales được phép chọn khi override |

**Trường riêng NHOM:**
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| item_code | Link → Item | ✓ nếu Fixed | `Item.al_item_type` = NHOM_PROFILE |
| quantity_rule | Link → AL Calculation Rule | | |
| qty_formula | Small Text | | Có thể tham chiếu `glass_thick_{prefix}` |
| price_type | Select | | Rule / Item Price / Fixed |
| price_rule | Link → AL Calculation Rule | | |
| fixed_price | Currency | | |

**Trường riêng KINH** *(luôn Fixed mode — không hỗ trợ Dynamic)*:
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

> **Biến tự động sinh:** `glass_thick_{prefix}`, `{prefix}_total_perimeter_m`, `{prefix}_total_m2`, `{prefix}_total_qty`, `max_glass_thick_mm`.

## IV.13 AL Profile Set (Master)
| fieldname | fieldtype | reqd |
|---|---|---|
| set_code | Data | ✓ unique |
| set_name | Data | ✓ |
| product_type | Link → AL Product Type | |
| brand | Link → Brand | |
| version | Data (default "1.0") | |
| al_lines | Table → AL Profile Line | |

## IV.14 AL PK Set / AL PK Line
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
| item_selection_mode / item_rule / item_condition_formula / item_fallback | (giống AL Profile Line) | |
| allow_sales_override / override_item_group | (giống AL Profile Line — mặc định 0 cho PK) | |

## IV.15 AL BOM (Master)
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
| default_installation_team | Link → AL Installation Team | |
| default_milestone_billing_template | JSON | Template % + trigger cho Payment Schedule (§XXVII) |

## IV.16 AL Cost Template / AL Cost Template Line
**AL Cost Template:** `template_code` (unique), `template_name`, `product_type` (Link), `formula_set` (Link → Formula Set, optional), `al_lines` (Table).

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

## IV.17 ConfigSnapshot (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| snapshot_id | Data (unique) | |
| formula_engine_snapshot_id / formula_engine_payload_hash | Data | Tham chiếu EnterpriseSnapshot của formula_builder |
| enterprise_snapshot_json | Long Text | Toàn bộ payload gốc |
| compressed_snapshot | Long Text | JSON nén gzip base64. `SnapshotBuilder.persist()` ghi cả 2; `get_snapshot_data()` ưu tiên đọc bản nén, fallback nếu rỗng |
| **snapshot_version** | Int | Phiên bản schema (hiện tại = 24). Dùng cho Snapshot Schema Registry: khi `compare_versions()` gặp 2 snapshot khác `snapshot_version` → tự động migrate về schema mới nhất trước khi diff. Migration function đăng ký trong dict toàn cục `snapshot_migration_registry = {version: migrate_func}`, mọi migrate_func có unit test roundtrip |
| profile_set / profile_set_hash | Link / Data | |
| pk_set / pk_overrides_json | Link / JSON | |
| rule_set_hashes / glass_master_hashes | JSON | `{code: hash}` |
| variable_bindings_hash | Data | |
| cost_template / cost_template_hash | Link / Data | |
| bom_version_id / bom_version_hash | Data | |
| rule_version_ids | JSON | `{rule_code: version_name}` |
| discount_applied | JSON | `{pricing_rule, pct, gia_thuong_mai}` — đọc từ Pricing Rule engine |
| discount_approval_ref | Data | |
| calculation_timestamp | Datetime | |
| created_at | Datetime | |
| quotation / quotation_item_name | Link / Data | |
| drift_detected | Check | |
| drift_details | JSON | |

## IV.18 AL Alert Config (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| alert_type | Select | PRICE_CHANGE / LOW_STOCK / BOM_EXPIRY / VARIANCE_ALERT / APPROVAL_PENDING / DISCOUNT_EXCEEDED / MARGIN_DRIFT / INSTALLATION_DELAY / SUPPLIER_PRICE_CHANGE / MATERIAL_TRACE_STALE |
| alert_name | Data | |
| is_active | Check | |
| threshold_value | Float | |
| notify_roles / notify_users | JSON | |
| notification_channel | Select | EMAIL / FRAPPE_NOTIFICATION / BOTH |
| frequency | Select | REALTIME / DAILY_DIGEST / WEEKLY |
| max_total_discount_pct | Float | |

## IV.19 AL Cutting Standard (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| applies_to | Select | NHOM_PROFILE / KINH |
| profile_code hoặc item_group | Data / Link | Phạm vi áp dụng |
| stock_bar_length_mm (NHOM) | Float | Chiều dài phôi chuẩn (vd 6000mm) |
| saw_kerf_mm (NHOM) | Float | Hao do lưỡi cưa |
| jumbo_sheet_size (KINH) | Data | vd "3210x2250" |
| edge_trim_mm (KINH) | Float | Trừ hao mép |
| min_offcut_reusable_mm | Float | Ngưỡng phế liệu tái dùng |
| cutting_tolerance_formula | Small Text | Công thức trừ hao gia công qua FormulaEngine |
| survey_tolerance_mm | Float | Ngưỡng sai lệch tối đa của AL Site Survey trước khi bắt buộc BOM Revision — khác với `cutting_tolerance_formula` |

## IV.20 AL Installation Team (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| team_name | Data | |
| team_leader | Link → Employee/User | |
| members | Table (Employee) | |
| region | Data | |
| capacity_m2_per_day | Float | |
| is_active | Check | |

## IV.21 AL Warranty Policy (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| policy_code | Data (unique) | |
| product_type | Link → AL Product Type | |
| warranty_months | Int | |
| coverage_scope | Small Text | Mô tả phạm vi bảo hành |
| exclusions | Small Text | |

*(Lưu ý: đây là Master **chính sách**, khác với `Warranty Claim` — DocType giao dịch của core dùng khi có khiếu nại thực tế, xem §V.8.)*

## IV.22 AL Project Financial Config (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | |
| overhead_allocation_method | Select | NONE / PCT_OF_REVENUE / FIXED_AMOUNT |
| overhead_allocation_value | Float | |
| margin_drift_alert_threshold_pct | Float | Ngưỡng cảnh báo lệch margin (mặc định -5%) |
| **enforce_material_check** | Check (default 1) | Bật/tắt Material Check Hook (§25.8). **Quyền thay đổi field này chỉ dành cho Role Director** (field-level permission, permlevel=1). Mọi thay đổi ghi vào `AL BOM Change Log` (target_doctype=AL Project Financial Config) |
| material_trace_stale_days | Int (default 14) | Ngưỡng cảnh báo Batch ISSUED quá lâu chưa INSTALLED (§4.25) |
| use_project_warehouse | Check | Bật → dùng AL Project Warehouse Map để tách kho vật lý theo dự án |

## IV.23 TỒN KHO NHÔM/VẬT TƯ THEO MÀU — KHÔNG DÙNG ITEM VARIANT

**Nguyên tắc:** đơn vị quản lý tồn kho đúng là **Item (theo tiết diện) + Batch (mang màu + dự án nguồn)**, không phải **Item Variant (theo tiết diện × màu)** — vì số lượng tiết diện nhôm hữu hạn (~30-80/hệ), trong khi số lượng màu gần như vô hạn và phần lớn mua theo yêu cầu từng dự án.

### 4.23.1 AL Color Standard (Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| color_code | Data (unique) | VD: `RAL9016`, `VANGO-OC-CHO-01` |
| color_name | Data | Tên hiển thị |
| applies_to | Select | NHOM_PROFILE / PHU_KIEN |
| is_standard_stock | Check | Bật → được phép có tồn kho đệm an toàn trong MRP Lite; tắt → bắt buộc make-to-order theo dự án |
| default_safety_stock_qty | Float | Chỉ áp dụng nếu `is_standard_stock=1` |
| surcharge_rule | Link → AL Calculation Rule | Trỏ rule LOOKUP giá theo màu (TRA-GIA-NHOM) — tách biệt hoàn toàn khỏi tồn kho vật lý |

### 4.23.2 Cơ chế Batch thay Item Variant
- Item Master NHOM_PROFILE: 1 Item = 1 tiết diện, không nhân theo màu. Field `al_is_color_variable=1` trên Item đánh dấu.
- Bật "Has Batch No" (core) cho các Item này.
- Khi Purchase Receipt/Stock Entry nhập kho: tạo Batch mới cho mỗi lô màu.
- Bật "Batch Wise Valuation" (core) — giá vốn thực tế theo đúng lô màu, không pha loãng bình quân gia quyền.

### 4.23.3 Custom field trên Batch (core)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_color | Link → AL Color Standard | Màu thực tế của lô |
| al_source_project | Link → Project | Dự án lô được mua cho |
| al_is_reserved_for_project | Check | Chỉ xuất kho cho đúng dự án |
| al_trace_stage | Select | ISSUED / CUT / INSTALLED / RETURNED / LOST — tự động cập nhật (§4.25) |
| al_trace_last_updated | Datetime | Timestamp lần cuối stage thay đổi |
| al_bin_location | Data | Vị trí vật lý (kệ/dãy), VD "A1-03" — chỉ để tìm kiếm, không ảnh hưởng kế toán (§XXXVIII) |

### 4.23.4 AL Project Warehouse Map (Master, tùy chọn)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | |
| warehouse | Link → Warehouse | Warehouse con tự tạo dạng `"NHOM - {project.name}"` |
| auto_created | Check | |
| close_on_project_complete | Check | Tự chuyển tồn kho còn lại về kho tổng khi Project đóng |

> Opt-in qua `AL Project Financial Config.use_project_warehouse` — công ty nhỏ dùng Batch là đủ.

### 4.23.5 Tác động MRP Lite
MRP Lite tổng hợp theo `(item gốc, color_code)`: (a) `is_standard_stock=1` → cộng dồn tồn kho đệm chung; (b) `is_standard_stock=0` → luôn tạo Material Request gắn `project`, không gộp giữa các dự án.

### 4.23.6 Tác động Sản xuất/Cắt và định giá
Định giá bán vẫn dùng LOOKUP TRA-GIA-NHOM theo (brand, màu) — không đổi. Cutting Plan xuất kho: chọn Item (tiết diện) + gợi ý `batch_no` đúng màu (ưu tiên batch đã reserve cho project).

## IV.24 AL SUPPLIER PRICE LIST — THEO DÕI BIẾN ĐỘNG GIÁ NHÔM THÔ

**AL Supplier Price List (Master):**
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| supplier | Link → Supplier | ✓ | |
| brand | Link → Brand | | |
| effective_date | Date | ✓ | |
| expiry_date | Date | | |
| currency | Link → Currency | ✓ | |
| exchange_rate_snapshot | Float | | Tỷ giá tham khảo tại thời điểm nhập |
| status | Select | | Draft / Active / Expired |
| al_price_lines | Table → AL Supplier Price List Line | | |

**AL Supplier Price List Line (Child):**
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| item_code | Link → Item | ✓ | |
| unit_price | Currency | ✓ | |
| price_change_pct | Float (read-only, computed) | | So với đơn giá cùng supplier+item ở bảng `Active` liền trước |
| notes | Small Text | | |

**Luồng cảnh báo:** khi `AL Supplier Price List` chuyển `status=Active`, tính `price_change_pct` từng dòng; vượt ngưỡng → dùng `AL Alert Config` (alert_type=`SUPPLIER_PRICE_CHANGE`) — chỉ là dữ liệu tham khảo, không tự ghi đè `AL Calculation Rule` (vẫn qua Approval Workflow).

## IV.25 MATERIAL TRACE — CUSTOM FIELD TRÊN BATCH (chi tiết hook)

**Hook tự động cập nhật `al_trace_stage`:**

| Transition | Trigger | Hành động |
|---|---|---|
| ISSUED | `Stock Entry.on_submit` (xuất kho cho Cut Order) | Cập nhật mọi Batch trong Stock Entry Detail → `ISSUED` |
| CUT | `AL Aluminum/Glass Cutting Plan.status = "Cut Done"` | Cập nhật Batch liên quan → `CUT` |
| INSTALLED | `AL Installation Order Line.status = "Done"` | Cập nhật Batch liên quan → `INSTALLED` |
| RETURNED | `Stock Entry.on_submit` (nhập kho trả lại) | Cập nhật Batch → `RETURNED` |
| LOST | Manual (kiểm kê phát hiện thiếu) | Cập nhật Batch → `LOST` kèm `al_trace_notes` |

**Cảnh báo tự động (dùng `AL Alert Config`):**

| Cảnh báo | Điều kiện | Mức |
|---|---|---|
| Batch `ISSUED` quá X ngày chưa `INSTALLED` | `al_trace_last_updated > material_trace_stale_days` (§IV.22) | WARNING |
| Tổng `INSTALLED` < `ISSUED` - `RETURNED` cuối dự án | Khi Project sắp đóng | CRITICAL — bắt buộc giải trình trước khi chốt sổ |

---

## V. CUSTOM FIELDS TRÊN ERPNEXT CORE

### 5.1 Item
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_item_type | Select | NHOM_PROFILE / KINH / VTP / PHU_KIEN |
| al_glass_master | Link → AL Glass Master | Bắt buộc nếu KINH |
| al_kg_per_m | Float | Bắt buộc nếu NHOM_PROFILE |
| al_is_color_variable | Check | Đánh dấu Item áp dụng cơ chế Batch-màu (§4.23) |

### 5.2 Quotation Item
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
| al_gia_thuong_mai | Currency | Giá sau chiết khấu (đọc từ Pricing Rule engine) |
| al_cost_variance_ref | Link → AL Cost Variance | |
| al_approval_status | Select | PENDING / APPROVED / REJECTED |
| al_approved_by | Link → User | |
| al_approval_note | Small Text | |
| al_sales_item_overrides | JSON | `{slug: item_code}` cho dòng Dynamic |

### 5.3 Sales Order Item / Sales Invoice Item
Y hệt Quotation Item (trừ `al_recalculate`), cộng `al_source_quotation_item` (Data, ẩn). Toàn bộ field `al_*` copy khi convert QT→SO→SI qua hook `copy_al_fields`.

### 5.4 Quotation (cấp Master)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_loss_reason | Select | Giá cao / Chậm tiến độ / Đối thủ / Khách đổi ý / Khác — dùng cho AI Win/Loss |
| al_discount_approval_ref | Data | Số phê duyệt khi tổng chiết khấu (Pricing Rule) vượt ngưỡng |

### 5.5 Sales Order
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_installation_order | Link → AL Installation Order | Tự tạo khi Submit |
| al_change_order_parent | Link → Sales Order | Trỏ về SO gốc nếu SO này sinh từ Change Order đã duyệt |

### 5.6 Batch — xem đầy đủ tại §4.23.3 và §4.25

### 5.7 Stock Entry Detail
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_bin_location | Data | Ghi lại vị trí sau mỗi lần nhập/xuất/chuyển |

### 5.8 Quality Inspection (core)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_production_order_bridge | Link → AL Production Order Bridge | Liên kết ngược lệnh sản xuất |

### 5.9 Warranty Claim (core, module Support)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_installation_order | Link → AL Installation Order | |
| al_defect_category | Select | Thấm nước / Kẹt bản lề / Nứt kính / Khác |
| al_warranty_policy | Link → AL Warranty Policy | |

### 5.10 Payment Schedule (core, child table Sales Order/Sales Invoice)
| fieldname | fieldtype | Mô tả |
|---|---|---|
| al_trigger_type | Select | PROGRESS_PCT / INSTALLED_M2 / HANDOVER_SIGNED / MANUAL |
| al_trigger_value | Data | VD "50" (%) hoặc "120" (m²) — rỗng nếu MANUAL |
| al_is_released | Check (default 0) | Hook tự bật khi điều kiện đạt — mở khóa nút "Create Sales Invoice against this schedule" |

---

## VI. MASTER DATA MẪU CHUẨN

### 6.1 AL Variable Group
| group_code | group_name | sort_order |
|---|---|---|
| KICH_THUOC | Kích thước | 10 |
| SO_LUONG | Số lượng | 20 |
| VAT_LIEU | Vật liệu | 30 |
| CANH_CUA | Cánh cửa | 40 |
| VACH | Vách kính | 50 |

### 6.2 Formula Variable Binding — Priority chuẩn
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

**CONSTANT:** `XF55-OFFSET-W`=86, `XF55-OFFSET-H`=86 (offset kích thước kính cánh).

**FORMULA:**
| rule_code | formula_expression |
|---|---|
| QTY-KHUNG-DUNG | `(H_m * 2) * qty` |
| QTY-KHUNG-NGANG | `(W_m + 0.043*2) * qty` |
| QTY-CANH-DUNG | `(H_m - 0.043*2) * n_canh * qty` |
| QTY-CANH-NGANG | `(W_m/n_canh - 0.043*2) * n_canh * qty` |
| QTY-NEP-DUNG | `(H_m - 0.043*2) * n_canh * qty * 2` |
| QTY-NEP-NGANG | `(W_m/n_canh - 0.043*2) * n_canh * qty * 2` |

**LOOKUP (TRA-GIA-NHOM):**
| brand | mau_nhom | result_value (đ/kg) |
|---|---|---|
| XF-NK | STD | 113,000 |
| XF-NK | DAK | 118,000 |
| XF-NK | VG | 125,000 |
| ALUMIL | STD | 135,000 |
| ALUMIL | DAK | 142,000 |

### 6.4 AL Cost Bucket mẫu (kèm `default_expense_account`)
| bucket_code | bucket_role | parent_bucket | report_group | default_expense_account |
|---|---|---|---|---|
| VL_NHOM | LEAF | TONG_VL | A. Vật liệu | "Nguyên vật liệu - Nhôm" |
| VL_KINH | LEAF | TONG_VL | A. Vật liệu | "Nguyên vật liệu - Kính" |
| VL_VTP | LEAF | TONG_VL | A. Vật liệu | "Nguyên vật liệu - Phụ" |
| VL_PK | LEAF | TONG_VL | A. Vật liệu | "Nguyên vật liệu - Phụ kiện" |
| TONG_VL | AGGREGATE | | A. Vật liệu | — |
| NC_SX / NC_LD | LEAF | TONG_NC | B. Nhân công | "Chi phí nhân công SX/Lắp đặt" |
| TONG_NC | AGGREGATE | | B. Nhân công | — |
| OH_HH / OH_CUT_KINH / OH_VC / OH_BH | LEAF | TONG_OH | C. Overhead | Account tương ứng |
| TONG_OH / GIA_THANH / GIA_BAN / GIA_VAT | AGGREGATE | | D. Tổng hợp | — |

### 6.5 AL Cost Template — CT-01-STANDARD
| sort | line_code | calc_formula | is_subtotal |
|---|---|---|---|
| 10-40 | VL_NHOM/VL_KINH/VL_VTP/VL_PK | (giá trị dòng) | 0 |
| 50 | TONG_VL | VL_NHOM + VL_KINH + VL_VTP + VL_PK | 1 |
| 55 | TONG_M2 | W_m * H_m * qty | 0 |
| 60 | NC_SX | TONG_VL * 0.12 | 0 |
| 70 | NC_LD | TONG_M2 * 180000 | 0 |
| 80 | TONG_NC | NC_SX + NC_LD | 1 |
| 90-120 | OH_HH/OH_CUT_KINH/OH_VC/OH_BH | (công thức) | 0 |
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

### 6.8 AL Profile Set mẫu — PS-CUA-DI-XF55
| sort | line_type | slug | Logic |
|---|---|---|---|
| 10-50 | NHOM | nhom_0010...0050 | Khung, cánh — show_condition theo `do_day`, `huong_mo`, `co_nguong` |
| 60 | NHOM | nhom_0060 | item=C3209-20, `show_condition = glass_thick_kinh_canh <= 10.38` |
| 61 | NHOM | nhom_0061 | item=C3210-20, `10.38 < glass_thick_kinh_canh <= 16` |
| 62 | NHOM | nhom_0062 | item=C3211-20, `glass_thick_kinh_canh > 16` |
| 80 | KINH | kinh_canh | prefix=`kinh_canh`, width=`W_mm-86`, height=`H_mm-86` |
| 90 | KINH | kinh_oc | prefix=`kinh_oc`, show_condition=`co_oc_thong_gio=='Yes'` |
| 100-150 | VTP | vtp_0100... | Gioăng, keo, xốp, vít |

### 6.9 Pricing Rule mẫu (thay AL Discount Rule)
| Pricing Rule | Cấu hình | Tương đương cũ |
|---|---|---|
| PR-RETAIL-STD | applicable_for=Customer Group, discount=0% | DISC-RETAIL-STD |
| PR-PROJECT-10 | applicable_for=Territory/Project field, discount=10%, priority=40 | DISC-PROJECT-10 (yêu cầu duyệt nếu >8% qua hook §19.3) |
| PR-VOLUME-TIER | Price Discount Scheme theo qty: 1-9=0%, 10-29=3%, 30-99=5%, ≥100=8% | DISC-VOLUME-TIER |

### 6.10 AL Alert Config mặc định
| alert_type | threshold_value | notify_roles | frequency |
|---|---|---|---|
| PRICE_CHANGE | 5% | Kỹ Thuật, Admin | REALTIME |
| VARIANCE_ALERT | 15% | Admin, Kế toán | REALTIME |
| DISCOUNT_EXCEEDED | 8% | Admin | REALTIME |
| MARGIN_DRIFT | -5% | Director, Admin | REALTIME |
| INSTALLATION_DELAY | 3 ngày trễ | Quản lý Thi công, Director | DAILY_DIGEST |
| SUPPLIER_PRICE_CHANGE | 5% | Mua hàng, Admin | REALTIME |
| MATERIAL_TRACE_STALE | 14 ngày | Quản lý Kho, Director | DAILY_DIGEST |

### 6.11 AL Cutting Standard mẫu
| applies_to | profile_code | stock_bar_length_mm | saw_kerf_mm |
|---|---|---|---|
| NHOM_PROFILE | XF-NK (mọi profile) | 6000 | 3 |

| applies_to | jumbo_sheet_size | edge_trim_mm | survey_tolerance_mm |
|---|---|---|---|
| KINH | 3210x2250 | 10 | 3 |

---
---

# PHẦN C — TẦNG 2-3: RULE & FORMULA ENGINE

## VII. AL CALCULATION RULE

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ unique | |
| rule_name | Data | ✓ | |
| rule_type | Select | ✓ | CONSTANT / FORMULA / THRESHOLD / LOOKUP / SEQUENCE |
| description | Text | | |
| is_active | Check (default 1) | | |
| constant_value | Data | (CONSTANT) | |
| formula_expression | Small Text | (FORMULA) | |
| threshold_input_var | Data | (THRESHOLD) | |
| threshold_rows | Table → AL Rule Threshold Row | (THRESHOLD) | |
| lookup_key_1_var / lookup_key_2_var | Data | (LOOKUP) | |
| lookup_rows | Table → AL Rule Lookup Row | (LOOKUP) | |
| lookup_default | Data | (LOOKUP) | |
| sequence_items | Table → AL Rule Sequence Item | (SEQUENCE) | |

**AL Rule Threshold Row:** `from_value`, `to_value` (0=không giới hạn), `result_value`.
**AL Rule Lookup Row:** `key_1/key_2/key_3`, `result_value`.
**AL Rule Sequence Item:** `rule` (Link), `sort_order`.

**Định hướng migrate:** THRESHOLD/LOOKUP giữ nguyên vĩnh viễn. CONSTANT/FORMULA có thể migrate sang Formula Global Variable khi Admin chủ động chọn — không bắt buộc.

## VIII. AL DYNAMIC ITEM RULE — VERSIONING QUA WORKFLOW

### 8.1 AL Dynamic Item Rule (Master)
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ unique | `NEP-KINH-THEO-DO-DAY`, `TAY-NAM-THEO-BRAND-MAU` |
| rule_name | Data | ✓ | |
| rule_type | Select | ✓ | THRESHOLD / LOOKUP |
| input_variable | Data | (THRESHOLD) | vd `glass_thick_kinh_canh`, `max_glass_thick_mm` |
| threshold_rows | Table → AL Dynamic Item Threshold Row | (working copy — chưa publish) | |
| lookup_key_1_var / lookup_key_2_var | Data | (LOOKUP) | |
| lookup_rows | Table → AL Dynamic Item Lookup Row | (working copy) | |
| default_item | Link → Item | ✓ | Fallback nếu không khớp |
| is_active | Check (default 1) | | |
| description | Small Text | | |
| current_version | Link → AL Dynamic Item Rule Version | | Version đang Published |
| total_versions | Int (read-only) | | |

> **Điểm mấu chốt:** `threshold_rows`/`lookup_rows` trên chính DocType này là **vùng soạn thảo**. DynamicItemResolver **KHÔNG BAO GIỜ** đọc trực tiếp — luôn đọc từ `current_version.rule_snapshot_json` (bất biến).

### 8.2 AL Dynamic Item Rule Version (Master, immutable)
| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule | Link → AL Dynamic Item Rule | ✓ | |
| version_number | Int | ✓ | Tự tăng |
| **workflow_state** | (managed bởi Workflow core) | ✓ | Draft / Pending Approval / Published / Deprecated / Rejected |
| rule_snapshot_json | Long Text | ✓ | Full JSON tại thời điểm publish |
| snapshot_hash | Data | ✓ | SHA-256 |
| snapshot_version | Int | | Schema version của snapshot |
| **valid_from** | Datetime | | Mặc định = `published_on`. BomOrchestrator dùng để resolve version theo `Quotation.creation_date` |
| **valid_to** | Datetime | | **Tự động set = `now()` khi version mới chuyển sang Published** (qua hook `on_update` khi Workflow Action "Approve" hoàn tất) — version hiện hành luôn để trống |
| change_summary | Small Text | | |
| is_rollback_of | Link → AL Dynamic Item Rule Version | | |
| published_on / published_by | Datetime / Link User | | |

### 8.3 Child tables (working copy)
**Threshold Row:** `from_value`, `to_value`, `operator` (≤/</≥/>/=), `item_code` (reqd), `note`.
**Lookup Row:** `key_1`, `key_2` (optional), `item_code` (reqd), `note`.

### 8.4 Vòng đời Version — Workflow "Version Approval Workflow" (core)

```
Draft --(Submit for Approval)--> Pending Approval --(Approve)--> Published
                                        |
                                        +--(Reject)--> Rejected --(Revise)--> Draft
Published --(hook tự động khi có version mới Published)--> Deprecated
```

- `workflow_state` là nguồn sự thật duy nhất cho 4 trạng thái đầu — quản lý bởi Workflow (core), không code state machine thủ công.
- Role `Director` được gán quyền Workflow Action "Approve"/"Reject" qua Workflow permission.
- Chuyển `Published → Deprecated` vẫn là hook tự động (không phải Workflow Action người dùng bấm).
- Dùng chung 1 Workflow này cho cả `AL BOM Version` (§XVII).

### 8.5 Quy trình sửa Rule
| Bước | Actor | Hành động |
|---|---|---|
| 1 | Kỹ thuật viên | Sửa `threshold_rows`/`lookup_rows` (working copy) |
| 2 | Kỹ thuật viên | Nhấn "Publish Version" |
| 3 | System | Snapshot toàn bộ → tạo `AL Dynamic Item Rule Version` mới, tính `snapshot_hash`, `workflow_state=Draft` |
| 4 | Kỹ thuật viên | Bấm Workflow Action "Submit for Approval" (nếu `requires_approval`) |
| 5 | Director | Workflow Action "Approve" (qua Approval Inbox core) → `valid_to` của version cũ tự set `now()`, version mới `Published` |
| 6 | Admin | Chọn áp dụng cho BOM mới từ nay (mặc định) hoặc áp dụng hồi tố (Diff Tool `compare_versions()` liệt kê BOM/Quotation bị ảnh hưởng) |
| 7 | System | Ghi `AL BOM Change Log` (target_doctype=AL Dynamic Item Rule) |

### 8.6 Hành vi DynamicItemResolver
Tầng 4.5 khi gặp `item_selection_mode=Rule`: (1) lấy `current_version` → (2) parse `rule_snapshot_json` (không đọc rows sống) → (3) so khớp `input_variable`/`lookup_key` → trả `item_code` → (4) ghi `rule_version_ids[rule_code]=version_name` vào ConfigSnapshot.

## IX. FORMULA VARIABLE BINDING

VariableResolver v3 gọi `formula_builder.api.variable_resolver.resolve_bindings_with_deps()` thay vì tự resolve theo `priority` thủ công. 2 custom handler đăng ký vào `data_source_registry`:

| Handler | Nguồn dữ liệu | Thay thế cho |
|---|---|---|
| `bom_variable` | Đọc từ `AL Variable Set`/`al_bom_vars` | AL Variable Binding source_type=`BOM Variable` |
| `rule_engine_lookup` | Gọi `AL Calculation Rule` (LOOKUP/THRESHOLD) | AL Variable Binding source_type=`Rule Engine Result` |

`AL Variable Binding` (DocType cũ) giữ nguyên, không xóa — chỉ đổi đường resolve. Migration script tạo Formula Variable Binding tương ứng.

---
---

# PHẦN D — TẦNG 4-4.5: ORCHESTRATION

## X. VARIABLERESOLVER v3

**Quy trình:**
1. Gọi `resolve_bindings_with_deps()` (FB) → resolve theo DAG topology.
2. Với mỗi dòng KINH: lấy `glass_code` từ `al_glass_selections` (hoặc `default_glass_master`) → tra `total_thick_mm` → inject `glass_thick_{prefix}`.
3. Trả về `inputs_dict` hoàn chỉnh cho Tầng 4.5.

> `glass_thick_{prefix}` luôn luôn là bước cuối, sau mọi Binding khác.

## XI. PROFILEINTERPRETER v2 — 2-PASS

**Pass 1 — Scan:** quét toàn bộ `al_lines`, xây `variable_registry`; tính `panel_counts[prefix]` cho dòng KINH có `panel_count_formula`.

**Pass 2 — Build:** với mỗi dòng theo `sort_order` (chỉ ảnh hưởng hiển thị):
- NHOM: sinh `{slug}_active/_qty/_kg/_dg/_tt` → gom `bucket_acc[cost_bucket]`.
- KINH: mỗi panel sinh `{prefix}_{i}_W/_H/_m2/_glass_thick_mm/_dg/_tt`; sau khi hết → `max_glass_thick_mm`.
- VTP: tương tự NHOM.
- PK (nội tuyến): tương tự, ưu tiên override.
- Trả `all_formulas` + `bucket_acc`.

**Nguyên tắc bất biến:** Kết quả **không phụ thuộc thứ tự khai báo** `sort_order` — chỉ phụ thuộc DAG. Kiểm chứng bắt buộc trước go-live (§XXXVI).

## XII. PKRESOLVER

1. Xác định `actual_item` = override hợp lệ hoặc `item_code` mặc định.
2. Override không hợp lệ → dùng mặc định, ghi `warnings[]`, không throw.
3. Sinh `pk_{n}_qty/_dg/_tt` → gom `bucket_acc['VL_PK']`.
4. Trả `formulas_pk`, `warnings[]`.

## XIII. DYNAMIC ITEM RESOLVER — 3 CHẾ ĐỘ (Tầng 4.5)

Chạy **sau** VariableResolver, **trước** ProfileInterpreter pass2_build.

| Chế độ | Cơ chế |
|---|---|
| Fixed | Bỏ qua — ProfileInterpreter đọc `item_code` bình thường |
| Rule | Đọc `current_version.rule_snapshot_json` → so khớp trực tiếp, không parse formula |
| Formula | `FormulaEngine.evaluate_single()` — chỉ tham chiếu biến INPUT |

**Thứ tự ưu tiên resolve item:**
```
Sales override (nếu al_item_type khớp line_type)
  > Kết quả Dynamic (Rule/Formula)
  > item_fallback
  > lỗi (throw, dừng BomOrchestrator)
```

**Edge cases:**
| Case | Xử lý |
|---|---|
| Formula/Rule trả item bị disabled | Bỏ qua, dùng fallback, log warning |
| Cả Dynamic và fallback fail | throw — dừng |
| Sales override sai `al_item_type` | Reject, dùng kết quả gốc |
| Dynamic mode cho dòng KINH | Không hỗ trợ — validate khi lưu |
| `item_condition_formula` >500 ký tự | Warn; >1000 → reject |
| `input_variable`/`lookup_key` thiếu trong inputs_dict | THRESHOLD: default 0 + warning. LOOKUP: fallback |

## XIV. COSTACCUMULATOR v2

Cộng dồn `bucket_acc` theo Cost Bucket. Nếu Formula Set (nếu dùng) lỗi/không tồn tại → fallback về `AL Cost Template Line`, **log chi tiết mọi lần fallback**; fallback >3 lần/ngày cùng 1 template → CRITICAL alert đẩy Push Notification Admin (QĐ-24).

## XV. BOMORCHESTRATOR — QUY TRÌNH 9 BƯỚC

```
B0: VersionPinningResolver — resolve BOM Version + Rule Version theo valid_from,
    so với Quotation.creation_date. Nếu có version mới hơn → badge
    "Đang dùng BOM v3 (đã có v4 từ 15/06)" + nút "Cập nhật lên BOM mới nhất"
B1: VariableResolver v3 — build inputs_dict đầy đủ (kể cả glass_thick_*)
B2: DynamicItemResolver — resolve item cho dòng Rule/Formula mode (Tầng 4.5)
B3: ProfileInterpreter Pass 1 — scan, xây variable_registry, panel_counts
B4: ProfileInterpreter Pass 2 — build công thức đầy đủ theo sort_order
B5: PkResolver — resolve phụ kiện + override
B6: CostAccumulator v2 — gom bucket_acc, fallback logging nếu cần
B7: FormulaEngine.calculate() — tính DAG 1 LẦN DUY NHẤT (không gọi lại)
B8: SnapshotBuilder.persist() — ghi ConfigSnapshot (cả compressed + raw), gồm rule_version_ids, bom_version_id
```

**Hooks không chặn luồng (A-D, sau B7/B8):** hiển thị chiết khấu (đọc từ Pricing Rule engine core), Version badge, Notification, AI `after_calculate` hook (timeout 10s).

**Hooks khi Sales Order Submit (E-F):**
- Tự động tạo `AL Installation Order` (link `Sales Order.al_installation_order`)
- Tự động tạo các dòng `Payment Schedule` (core) dựa trên `AL BOM.default_milestone_billing_template`, kèm field `al_trigger_type/al_trigger_value/al_is_released` (§XXVII)
- Đẩy vào Production Pool (tạo `AL Production Order Bridge` liên kết `Work Order`)
- Khóa các field kích thước trên Sales Order Item sau khi Submit (chỉ sửa được qua Change Order — §XXVII)

---
---

# PHẦN E — TẦNG 5: PRESENTATION

## XVI. BOM Dialog & UI Flow

- **BOM Dialog:** chọn BOM, nhập biến (theo `AL Variable Set`), chọn kính từng panel (Glass Selector), xem/ghi đè phụ kiện (PK Panel), xem chiết khấu áp dụng — **đọc trực tiếp từ Pricing Rule engine** (hàm `get_pricing_rule_for_item` của core), không tự tính.
- **Sales Override Panel:** hiển thị các dòng `allow_sales_override=1`, giới hạn item chọn theo `override_item_group`.
- **Version Badge:** hiển thị version BOM/Rule đang dùng (theo `valid_from`), cảnh báo nếu có version mới hơn.
- **Approval Inbox:** dùng "My Approvals" (core, từ Workflow) — không cần màn hình riêng.
- **Diff Viewer:** so sánh 2 version BOM/Rule (`compare_versions()`), highlight thay đổi.
- **Production Board:** Kanban trạng thái Cutting Plan/Cut Order theo `production_stage`.
- **Installation Mobile Checklist:** giao diện mobile cho đội thi công ghi `AL Installation Progress`.
- **Project P&L Dashboard:** hiển thị `AL Project Profitability Snapshot` mới nhất + xu hướng margin_drift.

---
---

# PHẦN F — TẦNG 6: MODULE NGHIỆP VỤ

## XVII. BOM Version Control

**AL BOM Version (Master, immutable):**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| bom | Link → AL BOM | |
| version_number | Int | Tự tăng |
| workflow_state | (Workflow core) | Draft / Pending Approval / Published / Deprecated / Rejected |
| bom_snapshot_json | Long Text | Toàn bộ cấu hình BOM tại thời điểm publish (Profile Set, PK Set, Cost Template, Variable Set — đầy đủ, không chỉ tham chiếu Link vì các Link có thể bị sửa sau) |
| snapshot_hash | Data | SHA-256 |
| snapshot_version | Int | |
| valid_from | Datetime | Mặc định = `published_on` |
| valid_to | Datetime | Tự động set `now()` khi version mới Published (hook, giống §8.2) |
| change_summary | Small Text | |
| is_rollback_of | Link → AL BOM Version | |
| published_on / published_by | Datetime / Link User | |

Vòng đời quản lý qua **cùng 1 Workflow "Version Approval Workflow"** dùng chung với AL Dynamic Item Rule Version (§8.4). Diff Tool `compare_versions()` dùng chung cho cả 2 loại version.

## XVIII. Approval — Workflow (core)

Toàn bộ approval cho BOM Version và Rule Version dùng Workflow (core), xem §8.4/§XVII. Riêng **duyệt chiết khấu vượt ngưỡng** (khác bản chất — tần suất cao, cần linh hoạt, không phải vòng đời version) dùng cơ chế đơn giản: field `al_discount_approval_ref` trên Quotation (§5.4), người có thẩm quyền ghi số phê duyệt thủ công sau khi xác nhận qua email/chat/Approval App riêng nếu công ty có.

## XIX. CHIẾT KHẤU — DÙNG `PRICING RULE` (CORE)

### 19.1 Cấu hình
Toàn bộ chiết khấu dùng `Pricing Rule` (core), áp dụng đồng bộ trên Quotation/Sales Order/Sales Invoice:
- Theo Customer/Customer Group/Territory: `Pricing Rule` với `discount_percentage`.
- Theo dự án: `Pricing Rule` với `priority` cao hơn, phạm vi áp dụng theo Project (qua field liên kết) hoặc Customer cụ thể.
- Theo số lượng (volume tier): `Price Discount Scheme` con của Pricing Rule với `min_qty`/`max_qty`.

### 19.2 Hook chặn tổng chiết khấu vượt ngưỡng
```
on Quotation.validate():
    total_discount_pct = tổng % discount từ mọi Pricing Rule đang active trên Quotation
    threshold = AL Alert Config['DISCOUNT_EXCEEDED'].threshold_value  (mặc định 8%)
    if total_discount_pct > threshold and not al_discount_approval_ref:
        throw("Tổng chiết khấu {total_discount_pct}% vượt ngưỡng {threshold}%. Cần phê duyệt trước khi submit.")
```

### 19.3 Điều không đổi
Sales Override (chọn item, §QĐ-22) là kiểm soát khác bản chất với chiết khấu giá — không liên quan Pricing Rule, giữ nguyên cơ chế `allow_sales_override`/`override_item_group`.

## XX. MATERIAL PLANNING (MRP LITE)

**AL Material Plan (Master):** tổng hợp nhu cầu vật tư từ các Sales Order đã Submit trong kỳ, theo `(item gốc, color_code)`.

**AL Material Plan Line (Child):**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| item_code | Link → Item | |
| color_code | Link → AL Color Standard | |
| project | Link → Project | Rỗng nếu là tồn kho đệm chuẩn |
| required_qty | Float | |
| available_batch_qty | Float (computed) | Tồn kho Batch khớp màu (+ project nếu reserved) |
| shortfall_qty | Float (computed) | |
| suggested_po_qty | Float | |
| al_bin_location_hint | Data | Gợi ý vị trí lưu kho mặc định theo quy ước công ty (nếu có) |

**Logic:** (a) `is_standard_stock=1` → cộng dồn tồn kho đệm chung, không phân biệt dự án; (b) `is_standard_stock=0` → luôn tạo Material Request/PO riêng gắn `project`, không gộp giữa các dự án dù cùng mã màu danh nghĩa.

## XXI. COST VARIANCE ANALYSIS

**AL Cost Variance (Master):** so sánh chi phí ước tính (từ ConfigSnapshot, theo Cost Bucket) với chi phí thực tế — **truy vấn qua GL Entry lọc theo `Account = AL Cost Bucket.default_expense_account`** (không cộng dồn thủ công từ Purchase Invoice Item) để đảm bảo khớp tuyệt đối với sổ cái, không lệch do làm tròn hoặc bỏ sót bút toán điều chỉnh.

| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | |
| cost_bucket | Link → AL Cost Bucket | |
| estimated_amount | Currency | Từ ConfigSnapshot |
| actual_amount | Currency | Từ GL Entry (theo `default_expense_account` + `project` + `cost_center`) |
| variance_pct | Float (computed) | |
| variance_alert_triggered | Check | |

## XXII. NOTIFICATION & ALERT ENGINE

Dùng chung `AL Alert Config` cho mọi loại cảnh báo trong toàn hệ thống (Nguyên tắc #13 — không tạo engine cảnh báo riêng cho từng module). Danh sách `alert_type` đầy đủ: xem §IV.18.

## XXIII. SALES ANALYTICS / DASHBOARD

Khuyến nghị dùng tổ hợp core: `Number Card` (từng chỉ số KPI) + `Dashboard Chart` + `Dashboard` (gom theo vai trò) + `Workspace`. Chỉ tạo DocType custom (`AL Dashboard Config`/`AL Sales KPI`) nếu chứng minh được công thức KPI không biểu diễn được bằng Report Builder/Query Report của core.

## XXIV. REPORTING

Dùng Query Report (core) cho các báo cáo tổng hợp: doanh thu theo Product Type/Brand (nếu có Accounting Dimension, §XXXVII), công nợ/aging (từ Payment Schedule), biến động giá NCC (từ AL Supplier Price List).

## XXV. MODULE SẢN XUẤT (CUTTING & PRODUCTION)

### 25.1-25.6 Cutting Plan (1D nhôm, 2D kính)
`AL Aluminum Cutting Plan(+Line)` tối ưu cắt 1D theo `AL Cutting Standard.stock_bar_length_mm`/`saw_kerf_mm`; `AL Glass Cutting Plan(+Line)` nesting 2D theo `jumbo_sheet_size`/`edge_trim_mm`. `AL Glass Cut Order/Line` gắn lệnh cắt cụ thể với Sales Order. `AL Production Order Bridge` liên kết `Work Order` (core).

### 25.7 AL Site Survey — Cổng đối chiếu kích thước thực tế

**AL Site Survey (Master):** khảo sát thực tế công trình trước khi cắt, đối chiếu với ConfigSnapshot.

**AL Site Survey Line (Child):**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| sales_order_item | Link → Sales Order Item | |
| measured_W_mm / measured_H_mm | Float | Kích thước đo thực tế |
| deviation_mm | Float (computed) | So với `al_W_mm`/`al_H_mm` gốc |
| within_tolerance | Check (computed) | So với `survey_tolerance_mm` (§IV.19) |

**Gate:** nếu `within_tolerance=0` cho bất kỳ dòng nào → **chặn Cutting Plan Confirm**, bắt buộc tạo `AL Change Order` (hoặc BOM Version mới cho dòng đó) — không được sửa tay ConfigSnapshot gốc (Nguyên tắc #26).

### 25.8 Material Check Hook (hard block)

Trước khi Confirm Cutting Plan, kiểm tra 3 điều kiện:

| Điều kiện | Chi tiết |
|---|---|
| (a) Batch đủ tồn kho | Batch đúng `al_color`, đủ `qty`, (nếu `al_is_reserved_for_project=1`) đúng `project` |
| (b) Deposit đã trả | Với màu `is_standard_stock=0`: `deposit_status=Paid` trên PO liên quan |
| (c) PO/Subcontracting đã đặt | Với dòng `is_outsourced=1`: PO/Subcontracting Order có `status ∈ {Submitted, Approved}` (tùy cấu hình quy trình mua hàng công ty) — **không yêu cầu đã Receipt**, vì lúc Receipt xong điều kiện (a) đã tự động cover |

Không đạt → **hard block**, không phải soft warning.

**Quyền tắt `enforce_material_check`:** field trên `AL Project Financial Config` (§IV.22), mặc định bật. Quyền thay đổi **chỉ Role Director** (field-level permission permlevel=1). Mọi thay đổi ghi vào `AL BOM Change Log`.

### 25.9 Quality Gate — DÙNG `QUALITY INSPECTION` (CORE)

**Cấu hình:**
1. `Quality Inspection Template`: "QC Cắt Kính" (kích thước đúng dung sai, không nứt/mẻ cạnh, đúng độ dày), "QC Lắp Cửa" (độ vuông góc, khe hở gioăng, vận hành trơn tru) — mỗi template có các `Quality Inspection Parameter` (Numeric hoặc Pass/Fail).
2. Custom field `al_production_order_bridge` (Link) trên `Quality Inspection` (§5.8).

**Luồng tự động:**
```
Khi AL Glass Cut Order chuyển "Cut Done":
  → Tự động tạo Quality Inspection (inspection_type=In Process,
     template="QC Cắt Kính", al_production_order_bridge=<bridge>, status=Pending)
  → QC nhập kết quả từng parameter → submit → status=Accepted/Rejected
```

**Gate:** `AL Production Order Bridge.production_stage` không chuyển "Ready to Install" nếu Quality Inspection liên kết chưa `Accepted`. Nếu `Rejected` → cảnh báo Quản lý Sản xuất (qua `AL Alert Config`), không tự động tạo lại Cutting Plan.

## XXVI. MODULE THI CÔNG (FIELD OPERATIONS)

**AL Installation Order/Order Line:** lệnh thi công + hạng mục, tạo tự động khi Sales Order Submit, gợi ý `AL Installation Team` từ `AL BOM.default_installation_team`.

**AL Installation Progress (append-only):**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| installation_order | Link → AL Installation Order | |
| entry_date | Date | |
| pct_completed_this_entry | Float | % hoàn thành ghi nhận trong lần cập nhật này |
| m2_completed_this_entry | Float | m² hoàn thành trong lần này |
| notes | Small Text | |
| **cumulative_pct** | Float (computed) | **= SUM(`pct_completed_this_entry`) của mọi Progress entry (append-only), cap tại 100%.** Không tính trung bình theo hạng mục — mỗi entry ghi % hoàn thành tổng thể tại thời điểm đó |

**AL Installation Cost Actual:** chi phí thực tế thi công (nhân công, vật tư phụ phát sinh tại công trình) — nguồn actual cho §XXVIII qua GL Entry gắn `project`+`cost_center`.

**Warranty Claim (core, module Support) — thay AL Warranty Claim:** khi có khiếu nại bảo hành, tạo `Warranty Claim` với `al_installation_order`, `al_defect_category`, `al_warranty_policy` (§5.9). Dùng nguyên trạng thái/luồng xử lý của core (Open → Work In Progress → Resolved/Cancelled).

## XXVII. THANH QUYẾT TOÁN — `PAYMENT SCHEDULE` (CORE) + CHANGE ORDER

### 27.1 Payment Schedule + Trigger Condition

Khi Sales Order Submit (Hook E, §XV), hệ thống tự động tạo các dòng `Payment Schedule` (core) dựa trên `AL BOM.default_milestone_billing_template` (JSON, ví dụ):
```json
[
  {"pct": 30, "trigger": "MANUAL"},
  {"pct": 40, "trigger": "PROGRESS_PCT", "value": 50},
  {"pct": 25, "trigger": "INSTALLED_M2", "value": "ALL"},
  {"pct": 5,  "trigger": "HANDOVER_SIGNED"}
]
```
Điền vào field core (`invoice_portion`, `payment_amount`, `due_date`) + custom field `al_trigger_type`/`al_trigger_value`/`al_is_released` (§5.10).

**Luồng release:**
```
PROGRESS_PCT: AL Installation Progress.cumulative_pct đạt al_trigger_value → al_is_released=1
INSTALLED_M2: tổng m² lắp đặt đạt al_trigger_value → al_is_released=1
HANDOVER_SIGNED: AL Handover Acceptance được ký → al_is_released=1
MANUAL: Sales/PM tự set thủ công (VD đợt tạm ứng ban đầu)
```

**Validate:** Client Script trên nút "Create Sales Invoice against this schedule" (core) kiểm tra `al_is_released=1` — nếu chưa, hiển thị lý do (VD "Chưa đạt 50% tiến độ, hiện tại 32%").

### 27.2 AL Handover Acceptance (Master)

Biên bản nghiệm thu khách hàng ký — **tách biệt khỏi tiến độ nội bộ** (`AL Installation Progress`), là gate pháp lý cho trigger `HANDOVER_SIGNED`.

| fieldname | fieldtype | Mô tả |
|---|---|---|
| installation_order | Link → AL Installation Order | |
| signed_date | Date | |
| customer_signature | Attach | |
| accepted_scope | Small Text | Mô tả phạm vi được nghiệm thu (có thể từng phần) |
| status | Select | Draft / Signed / Disputed |

### 27.3 AL Change Order — TẠO SALES ORDER BỔ SUNG

**AL Change Order (Master):**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | |
| original_sales_order | Link → Sales Order | |
| reason | Small Text | |
| workflow_state / status | Draft / Pending Approval / Approved / Rejected | Có thể dùng Workflow core nếu cần nhiều cấp duyệt |
| al_change_order_lines | Table → AL Change Order Line | |
| resulting_sales_order | Link → Sales Order (read-only) | Điền tự động sau khi Approved |

**AL Change Order Line (Child):**
| fieldname | fieldtype | Mô tả |
|---|---|---|
| change_type | Select | ADD_ITEM / REMOVE_ITEM / MODIFY_ITEM / PRICE_ADJUST |
| bom_reference | Link → AL BOM | |
| new_bom_version | Link → AL BOM Version | Bắt buộc nếu `change_type=ADD_ITEM/MODIFY_ITEM` và `bom_reference` có giá trị |
| quantity | Float | |
| unit_price | Currency | |
| notes | Small Text | |

**Hành vi khi Approved:**
1. Tự động tạo **1 Sales Order mới** (`al_change_order_parent` trỏ về SO gốc, cùng Customer, cùng Project).
2. Các dòng SO mới lấy từ `AL Change Order Line`, tính giá qua BomOrchestrator bình thường (dùng `new_bom_version` nếu có).
3. SO bổ sung có `Payment Schedule` riêng (thường 1 đợt hoặc theo thỏa thuận riêng).
4. Điền `resulting_sales_order` trên `AL Change Order`.

**Báo cáo tổng giá trị hợp đồng** = SUM(`grand_total`) của SO gốc + mọi SO có `al_change_order_parent` trỏ về nó — dùng Query Report, **không lưu số tổng hợp tĩnh nào** (giữ tính bất biến từng SO, Nguyên tắc #14).

## XXVIII. MODULE KẾ TOÁN LÃI LỖ (PROJECT PROFITABILITY)

**AL Project Profitability Snapshot (Master, immutable, event-driven + scheduled weekly):**

| fieldname | fieldtype | Mô tả |
|---|---|---|
| project | Link → Project | |
| snapshot_date | Datetime | |
| trigger_source | Select | PI_SUBMIT / SE_SUBMIT / INSTALLATION_COST_SUBMIT / SCHEDULED_WEEKLY |
| estimated_revenue | Currency | Từ tổng ConfigSnapshot của các Sales Order + Change Order thuộc project |
| estimated_cost | Currency | Từ ConfigSnapshot (theo Cost Bucket) — **chỉ dùng để tính margin_drift, KHÔNG phải actual** |
| **actual_material_cost** | Currency | **Truy vấn GL Entry** lọc `project`+`cost_center`+`Account` (Nguyên tắc #31) |
| **actual_labor_cost** | Currency | Tương tự, từ GL Entry liên quan `AL Installation Cost Actual`/Payroll |
| **actual_overhead** | Currency | Tương tự |
| gross_profit | Currency (computed) | Revenue thực nhận (Sales Invoice) − actual costs |
| margin_drift_vs_quoted | Float (computed) | So với margin ước tính ban đầu |
| explain_variance() | Method | So sánh từng thành phần gross_profit với ConfigSnapshot; phân tách 3 nhóm: vật tư / nhân công / overhead & bảo hành. Không phân tách price vs usage variance (để P2 sau) |

**Field-level permission (permlevel=1):** `actual_material_cost`, `actual_labor_cost`, `gross_profit`, `margin_drift_vs_quoted` — chỉ Role `Director`/`Kế toán trưởng` có quyền đọc đầy đủ; Sales/PM chỉ thấy trạng thái tổng quát (VD "Đạt kế hoạch"/"Lệch âm") qua Role Permission Manager (không code).

---
---

# PHẦN G — TẦNG 7: AI

## XXIX. Tầng AI toàn diện

**AI Hooks Framework (QĐ-23) — 3 hook chuẩn:**
| Hook | Thời điểm | Timeout | Use case |
|---|---|---|---|
| `after_calculate` | Sau `FormulaEngine.calculate()` | 10s | AI Config Validator, AI Pricing Advisor |
| `before_quotation_submit` | Trước `Quotation.submit()` | 5s | AI Quotation Copilot review nhanh |
| `daily_ai_analysis` | Scheduled 00:00 | 60s (nên tách Background Job riêng nếu nặng, VD AI Cutting Optimization nesting 2D — dùng `frappe.enqueue(queue="long")`) | AI Win/Loss, AI Anomaly Detection, AI Project Health Score |

**Nguyên tắc bất biến:** AI Hook **KHÔNG BAO GIỜ chặn luồng chính** — lỗi/timeout chỉ log, không block user. Mọi đề xuất AI ghi vào `AL AI Suggestion Log` (cần Approval trước khi ảnh hưởng số liệu chính thức) hoặc `AL AI Interaction Log` (tra cứu/RAG, không cần duyệt vì không ghi đè dữ liệu).

**Danh mục use case AI:** AI Formula/Rule Generator, AI Config Validator, AI PK Suggester, AI Drawing-to-BOM, AI Quotation Copilot, AI Pricing/Negotiation Advisor, AI Win/Loss Analysis (dùng `Quotation.al_loss_reason`), AI Cutting Optimization, AI Purchasing/Price Forecast (đọc `AL Supplier Price List`), AI Voice-to-Progress (ghi `AL Installation Progress`), AI Root Cause Clustering (từ `Warranty Claim`), AI Project Health Score, AI Anomaly Detection (vật tư qua Material Trace + nhân công + bảo hành), AI Trợ lý tri thức nội bộ (RAG).

---
---

# PHẦN H — VẬN HÀNH

## XXX. ConfigSnapshot & Audit Trail

Xem chi tiết trường tại §IV.17. Nguyên tắc bổ sung: **Schema Registry migration** — `snapshot_migration_registry` (Python dict `{version: migrate_func}`) trong module `aluglass`; `compare_versions()` kiểm tra `snapshot_version` của 2 snapshot, nếu khác nhau thì áp lần lượt migrate_func theo thứ tự tăng dần trước khi diff; mọi migrate_func có unit test roundtrip (migrate lên rồi xuống phải khớp dữ liệu gốc).

## XXXI. Quy trình đầu-cuối (End-to-End)

```
Lead → Báo giá (BomOrchestrator 9 bước, Pricing Rule áp chiết khấu)
     → Chốt đơn (Sales Order Submit → tạo Installation Order + Payment Schedule + Production Pool, khóa field kích thước)
     → Mua vật tư (MRP Lite → PO/Subcontracting, theo dõi qua Supplier Price List)
     → Site Survey (đối chiếu kích thước thực tế, gate trước khi cắt)
     → Sản xuất (Cutting Plan → Material Check Hook hard block → Cut Order → Quality Inspection gate)
     → Thi công (Installation Order/Progress, Material Trace theo Batch)
     → Thanh toán (Payment Schedule release theo trigger: % tiến độ / m² / handover)
     → Nghiệm thu (Handover Acceptance ký)
     → Phát sinh nếu có (Change Order Approved → Sales Order bổ sung)
     → Bảo hành nếu có (Warranty Claim core)
     → Quyết toán & Lãi lỗ (Project Profitability Snapshot, đọc GL Entry thực tế)
```

## XXXII. Phân quyền & Vai trò

| Vai trò | Quyền đặc thù |
|---|---|
| Kỹ thuật viên | Sửa working copy BOM/Rule, Publish Version (chuyển Draft→Pending Approval qua Workflow) |
| Director | Workflow Action Approve/Reject (BOM/Rule Version), duyệt chiết khấu vượt ngưỡng, **duy nhất có quyền tắt `enforce_material_check`**, đọc đầy đủ field tài chính permlevel=1 |
| Sales | BOM Dialog, Sales Override (trong giới hạn `allow_sales_override`), không thấy field tài chính chi tiết dự án |
| Quản lý Sản xuất | Cutting Plan, nhận cảnh báo Quality Inspection Rejected |
| QC | Nhập kết quả Quality Inspection |
| Quản lý Thi công / Đội thi công | Installation Order/Progress, Handover Acceptance |
| Kế toán | Cost Variance, Project Profitability (đọc), GL Entry |
| Admin | Cấu hình Master Data, Pricing Rule, Alert Config |

## XXXIII. Ví dụ kiểm chứng (Test Scenarios bắt buộc trước Go-live)

1. Kết quả BomOrchestrator không đổi khi xáo trộn `sort_order` của Profile Line (kiểm chứng DAG độc lập thứ tự khai báo).
2. Quotation Draft giữ nguyên version BOM/Rule dù Kỹ thuật Publish version mới giữa chừng (kiểm chứng `valid_from`).
3. Confirm Cutting Plan bị chặn khi Batch chưa đủ hàng / deposit chưa trả / PO gia công chưa đặt (Material Check Hook).
4. Site Survey lệch vượt `survey_tolerance_mm` → chặn Cutting Plan, bắt buộc Change Order/BOM Version mới.
5. Pricing Rule 3 tầng (Customer Group + Volume + Project) áp đúng priority; hook chặn khi tổng >8% mà chưa có `al_discount_approval_ref`.
6. Payment Schedule tự động release đúng lúc `cumulative_pct` đạt 50%; bị khóa khi chưa đạt.
7. Quality Inspection Rejected → Production Order Bridge không chuyển "Ready to Install"; cảnh báo đúng vai trò.
8. Change Order Approved → tạo đúng 1 Sales Order mới với `al_change_order_parent` đúng; báo cáo tổng giá trị hợp đồng = tổng 2 SO.
9. Batch Wise Valuation: đối chiếu Gross Profit theo batch cho ≥1 Item có ≥2 màu, phân biệt kết quả 2 lớp (a) vật lý (đúng) và (b) kế toán (có thể cần Stock Ledger chi tiết nếu báo cáo tổng hợp không đủ).
10. `AL Project Profitability Snapshot.actual_*` khớp tuyệt đối với Trial Balance/GL Entry lọc theo project — không lệch do tính lại từ Cost Bucket.

## XXXIV. Lộ trình triển khai

| Phase | Nội dung |
|---|---|
| Phase 0 | Master Data (Tầng 1) + Rule/Formula Engine (Tầng 2-3) + BomOrchestrator (Tầng 4) — kiểm chứng kịch bản #1 |
| Phase 1 | BOM Version + Workflow core, Material Check Hook, khóa SO field, Site Survey — kiểm chứng #2, #3, #4 |
| Phase 2 | Pricing Rule (thay Discount Rule), Payment Schedule (thay Milestone Billing), Change Order → SO bổ sung — kiểm chứng #5, #6, #8 |
| Phase 3 | Quality Inspection (thay AL Quality Check), Warranty Claim (thay AL Warranty Claim), Cost Bucket → Account mapping, Material Trace — kiểm chứng #7, #9, #10 |
| Phase 4 | AI Layer đầy đủ, Dashboard (ưu tiên Number Card/Workspace trước khi custom), Accounting Dimension nếu cần báo cáo theo Product Type |

## XXXV. Rủi ro & điểm theo dõi (tổng hợp, không lặp lại chi tiết từng rủi ro lịch sử)

| # | Rủi ro | Mức | Giải pháp |
|---|---|---|---|
| R1 | Batch Wise Valuation không hoàn hảo 100% ở một số version ERPNext | P0 | Verify thực tế trước go-live; nếu (b) kế toán không đạt 100%, dùng Stock Ledger chi tiết theo batch làm nguồn đối chiếu báo cáo, không đại tu giải pháp |
| R2 | `enforce_material_check` bị tắt tùy tiện | P0 | Giới hạn quyền Role Director + audit log |
| R3 | Nhân sự dev tự tạo lại DocType trùng core trong tương lai | P1 | Checklist bắt buộc trước khi tạo DocType mới: "Đã tra core chưa? Lý do core không đủ là gì?" |
| R4 | AI Cutting Optimization timeout trong khung `daily_ai_analysis` 60s | P1 | Tách Background Job riêng, timeout lớn hơn |
| R5 | Payment Schedule (core) có UI hạn chế hơn Milestone Billing tự chế trước đây | P2 | Bổ sung Query Report riêng để hiển thị trực quan, không cần custom DocType lưu trữ |
| R6 | Snapshot schema thay đổi giữa các đợt nâng cấp phần mềm | P1 | Schema Registry + roundtrip test bắt buộc cho mọi migrate_func |
| R7 | Material Trace (`al_trace_stage`) không được cập nhật đúng nếu hook lỗi thầm lặng | P1 | Log lỗi hook riêng, cảnh báo nếu Batch ISSUED không chuyển stage sau X ngày |

## XXXVI. Checklist Go-live

- [ ] Toàn bộ 10 kịch bản kiểm chứng ở §XXXIII đã PASS
- [ ] Workflow "Version Approval Workflow" cấu hình đủ 4 trạng thái, test Approve/Reject/Revise
- [ ] Pricing Rule thay thế đầy đủ 3 loại discount cũ, test cộng dồn đa tầng + hook chặn ngưỡng
- [ ] Payment Schedule + trigger condition test đủ 4 loại trigger
- [ ] Quality Inspection Template "QC Cắt Kính"/"QC Lắp Cửa" đầy đủ tham số, test luồng tự động khi Cut Done
- [ ] Warranty Claim (core) + custom field, test luồng từ Installation Order
- [ ] `default_expense_account` đã gán cho toàn bộ AL Cost Bucket có `bucket_role=LEAF`
- [ ] Change Order Approved test tạo đúng SO bổ sung
- [ ] Quyền tắt `enforce_material_check` giới hạn đúng Role Director, có audit log
- [ ] `al_bin_location` đã thêm trên Batch/Stock Entry Detail (nếu công ty cần theo dõi vị trí)
- [ ] Đã xác nhận actual cost trong Project Profitability Snapshot khớp GL Entry, không lệch Cost Bucket

## XXXVII. COST BUCKET vs COST CENTER vs ACCOUNTING DIMENSION

### 37.1 Bản chất khác nhau

| | AL Cost Bucket | Cost Center (core) | Accounting Dimension (core) |
|---|---|---|---|
| Tầng | Tính giá / Ước tính (trước giao dịch) | Kế toán / GL thực tế | Mở rộng đa chiều cho GL Entry |
| Sống ở đâu | Formula Engine, ConfigSnapshot, Quotation | GL Entry, Journal Entry | GL Entry, Stock Ledger Entry |
| Có giao dịch tiền thật không | Không — thuần công thức | Có | Có |
| Trả lời câu hỏi | "Giá bán cấu thành từ đâu?" | "Chi phí thuộc bộ phận nào?" | "Lọc P&L theo chiều khác (VD loại sản phẩm)?" |
| Ví dụ | VL_NHOM = 45tr (ước tính) | Xưởng sản xuất, Đội thi công 1 | Dimension "Product Type" để lọc lãi theo loại cửa |

### 37.2 Quy tắc bắt buộc
1. **Cost Bucket không bao giờ là nguồn actual cost** — chỉ cấu thành công thức giá bán (Nguyên tắc #31).
2. **Cost Center = bộ phận/đội** (cố định, xuyên suốt nhiều dự án). **Project = từng công trình/hợp đồng** (thay đổi liên tục). Hai chiều độc lập, dùng song song trên mọi GL Entry.
3. Cần báo cáo lãi theo loại sản phẩm/hệ nhôm → khai báo **Accounting Dimension mới** (VD "Product Type"/"Brand", kế thừa từ Item/Sales Order Item) — không map qua Cost Bucket, không tạo Cost Center ảo.
4. **`default_expense_account`** (Cost Bucket → Account) là cầu nối duy nhất giữa 2 tầng, chỉ dùng để đối chiếu variance (§XXI), không thay thế vai trò Cost Center/Dimension trong báo cáo tài chính chính thức.

## XXXVIII. WAREHOUSE & VỊ TRÍ LƯU KHO

### 38.1 Nguyên tắc phân biệt

| Nhu cầu | Giải pháp |
|---|---|
| Tách kho có ý nghĩa kế toán (ảnh hưởng Stock Ledger/valuation) — theo khu vực vật tư hoặc theo công trình | **Warehouse Tree (core)** — dùng `AL Project Warehouse Map` (§4.23.4) để tự tạo warehouse con `"NHOM - {project}"` |
| Biết vị trí vật lý (kệ/dãy) của 1 batch — chỉ để tìm nhanh, KHÔNG ảnh hưởng giá trị/kế toán | **Custom field `al_bin_location`** trên `Batch` + `Stock Entry Detail` — KHÔNG tạo Warehouse hay DocType riêng |

### 38.2 Vì sao không dùng Warehouse Tree cho vị trí kệ
Nếu tạo 1 Warehouse cho mỗi kệ/rack sẽ lặp lại lỗi kiến trúc đã sửa ở §4.23 (Item Variant theo màu): số lượng Warehouse phình to theo số vị trí vật lý, và mỗi lần đổi chỗ để vật tư (không đổi giá trị/chủ sở hữu) lại bắt buộc phải làm Stock Entry — sai bản chất vì đây không phải giao dịch kế toán.

### 38.3 Khi nào MỚI cần DocType riêng (`AL Bin Location`)
Chỉ khi thực sự cần: nhiều vị trí cho cùng 1 batch, pick-path tối ưu, reservation theo từng ô kệ, multi-bin putaway rule tự động — đây là bài toán WMS chuyên sâu, ngoài phạm vi v24. Không triển khai trong bản này.

---

## KẾT LUẬN

Tài liệu v25 này là bản duy nhất cần dùng để triển khai production, hợp nhất và loại trùng từ v23/v24/v24 FINAL. Nó giữ nguyên toàn bộ logic nghiệp vụ cốt lõi đã qua nhiều vòng review (tính giá theo DAG, versioning bất biến, tồn kho theo Batch-màu, Material Check, Site Survey, Change Order, Cost Variance, Project Profitability), đồng thời tối ưu cách hiện thực hóa 6 module bằng cách tận dụng engine có sẵn của ERPNext core (Quality Inspection, Warranty Claim, Pricing Rule, Payment Schedule, Workflow, Accounting Dimension), giảm khối lượng DocType custom từ 70 xuống còn khoảng 55-61, giảm rủi ro bug, và thừa hưởng miễn phí các tính năng báo cáo/audit/UI đã được kiểm chứng qua hàng nghìn triển khai ERPNext thực tế trên toàn cầu.

**Bước tiếp theo:** giao tài liệu này cho đội dev, bắt đầu Phase 0 theo lộ trình §XXXIV.
