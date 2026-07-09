# KẾ HOẠCH TRIỂN KHAI CHI TIẾT — AlumGlass ERP (app `aluglass`)
**Nền tảng:** Frappe Framework v16 + ERPNext v16 + Frappe HRMS v16, phụ thuộc app `formula_builder` (đã xây xong, có thể nâng cấp thêm)
**Dựa trên:** AlumGlass_ERP_CANONICAL_v26.md — 62 DocType custom, Phase 0-4 (§XXXIV), 16 kịch bản kiểm chứng (§XXXIII), 13 rủi ro (§XXXV)

---

## 0. GIẢ ĐỊNH & NGUYÊN TẮC KHUNG

1. `formula_builder` đã cài, đã có: `FormulaEngine` (DAG, `evaluate_single()`, `explain()`, `snapshot_with_trace()`), `EnterpriseSnapshot`, `data_source_registry`, `resolve_bindings_with_deps()`. **Không sửa app này trong Phase 0-3** — chỉ *tiêu thụ* API và đăng ký thêm 2 custom handler vào `data_source_registry` (VariableResolver v3, §IX). Mọi nhu cầu mở rộng formula_builder (nếu phát sinh) phải qua một nhánh riêng, versioned, không sửa trực tiếp core DAG.
2. Vì đang trên **Frappe/ERPNext v16** (phát hành 12/1/2026), tận dụng các tính năng mới thay vì tự code lại:
   - **Role-based field masking (core, v16)** → dùng trực tiếp cho yêu cầu Gap 3 (permlevel=1 trên field tài chính, §24.1) thay vì tự viết logic redact trong Script Report ở những chỗ Report View/List View chuẩn đủ dùng. Vẫn giữ nguyên tắc: Script Report bắt buộc tự check Role cho các báo cáo tổng hợp phức tạp mà field masking core không phủ tới (aggregation qua SQL thô).
   - **Serial & Batch Traceability Report (core, v16)** → dùng làm nền cho một phần yêu cầu Material Trace (§4.25) và đối chiếu offcut (Gap 2, §4.26) trước khi quyết định có cần Query Report riêng hay không.
   - **Stock Reservation cho Work Order (core, v16)** → đánh giá dùng thay/thay thế một phần logic tự chế trong Material Check Hook (điều kiện (a) Batch đủ tồn kho) — xem mục 3.2 (Phase 1) để quyết định điểm tích hợp thay vì viết lại.
   - **MRP workflow mới (core, v16)** → đánh giá dùng làm lớp dưới cho `AL Material Plan` (Phase 1) thay vì code MRP Lite hoàn toàn từ đầu; `AL Material Plan Line` có thể chỉ là lớp phủ theo `(item, color_code, project)` trên kết quả MRP core.
   - Kiểm tra tương thích app `formula_builder` với Frappe v16 **trước Phase 0** (bench update thử trên staging) — nêu rõ trong Bước 1 dưới đây.
3. Không lặp lại toàn bộ đặc tả field trong tài liệu này — kế hoạch chỉ nêu **trình tự, phụ thuộc, tiêu chí hoàn thành (DoD), và điểm rủi ro/kiểm thử** cho từng bước. Đặc tả chi tiết field vẫn tra cứu CANONICAL v26.
4. Đơn vị thời gian dưới đây là **sprint 2 tuần**, chỉ mang tính tham khảo trình tự — điều chỉnh theo năng lực đội thực tế.

---

## BƯỚC 1 — CHUẨN BỊ HẠ TẦNG & MÔI TRƯỜNG (trước Phase 0, ~3-5 ngày)

| # | Việc | Chi tiết | DoD |
|---|---|---|---|
| 1.1 | Dựng bench v16 | `frappe-bench` version-16 branch cho `frappe`, `erpnext`, `hrms` | `bench version` báo đúng 3 app version-16 |
| 1.2 | Cài `formula_builder` lên bench v16 (staging) | `bench get-app` + `bench install-app`; chạy toàn bộ test suite sẵn có của `formula_builder` | Test suite pass 100%; nếu app dùng API/hook nào của Frappe đã đổi ở v16 (kiểm tra changelog Caffeine architecture, hooks.py signature) → sửa ngay ở staging, KHÔNG trì hoãn sang Phase 0 |
| 1.3 | Scaffold app `aluglass` | `bench new-app aluglass`; khai `formula_builder` là `required_apps` trong `hooks.py` | App cài được kèm dependency check |
| 1.4 | Thiết lập CI + quy ước code | Pre-commit, lint, migration test (roundtrip cho `snapshot_migration_registry` — chuẩn bị khung ngay từ đầu dù Phase 0 chưa cần) | Pipeline CI chạy được trên PR đầu tiên |
| 1.5 | Site staging riêng cho AlumGlass, seed Company/Fiscal Year/Chart of Accounts VN | Dữ liệu test, không đụng site production khác | Site sẵn sàng cho Phase 0 |
| 1.6 | Xác nhận Role/User Permission khung ban đầu | Tạo trước các Role: Kỹ thuật viên, Director, Sales, Quản lý Sản xuất, QC, Quản lý Thi công/Đội thi công, Kế toán, Admin (§XXXII) — chưa gán quyền chi tiết, chỉ tạo khung | 8 Role tồn tại trong hệ thống |

**Điểm dừng bắt buộc:** không sang Phase 0 nếu 1.2 chưa xanh — vì toàn bộ Tầng 2-4 phụ thuộc trực tiếp `formula_builder`.

---

## PHASE 0 — MASTER DATA + RULE/FORMULA ENGINE + BOMORCHESTRATOR
**Mục tiêu:** kiểm chứng được **Kịch bản #1** (§XXXIII: kết quả BomOrchestrator không đổi khi xáo trộn `sort_order`). Không phụ thuộc 6 gap đã đóng ở v26 → làm được ngay, không chờ.

### Trình tự dựng DocType (Tầng 1 → Tầng 2 → Tầng 4)
1. **Master Data nền (không phụ thuộc lẫn nhau):** AL Variable Group, AL Material Type, AL Glass Type, AL Glass Layer Type, AL Product Type, AL Cost Bucket, AL Color Standard.
2. **Master Data cấp 2 (phụ thuộc bước 1):** AL Glass Master + AL Glass Layer Line, AL Variable Library, AL Variable Set + AL Variable Set Detail.
3. **Trung tâm hệ thống:** AL Profile Line (child) → AL Profile Set; AL PK Line (child) → AL PK Set; AL Cost Template Line (child) → AL Cost Template.
4. **AL BOM** (liên kết Variable Set + Profile Set + PK Set + Cost Template) — DocType lắp ráp cuối Tầng 1.
5. **ConfigSnapshot** — dựng schema field theo §IV.17, gắn `snapshot_version=1` khởi điểm cho môi trường mới (không phải 24 như trong tài liệu — đó là version tại thời điểm viết tài liệu tham chiếu; nhóm dev **tự định nghĩa số bắt đầu** cho hệ thống của mình và tăng dần theo lần đổi schema thật).
6. **Tầng 2 — Rule Engine:** AL Calculation Rule + 3 child (Threshold/Lookup/Sequence Row); AL Dynamic Item Rule + Version + 2 child.
7. **Custom Fields trên core (Tầng 1 phần mở rộng, §V):** Item, Quotation Item, Quotation, Sales Order Item, Sales Order — chỉ các field cần cho Phase 0 (bỏ qua field thuộc Phase 1-3 như `al_bin_location`, `al_trigger_type`... để tránh field "chết" chưa dùng).
8. **Tầng 4 — Orchestration:** VariableResolver v3 (đăng ký handler vào `data_source_registry` của formula_builder), ProfileInterpreter v2 (2-pass), PkResolver, CostAccumulator v2, SnapshotBuilder, BomOrchestrator (lắp B0→B8 theo đúng thứ tự §XV — B0 VersionPinning có thể để **stub** ở Phase 0 vì BOM Version thật sự chưa có Workflow tới Phase 1; tạm dùng `bom.modified` làm mốc valid_from placeholder, ghi rõ TODO Phase 1).

### Test bắt buộc trước khi đóng Phase 0
- Kịch bản #1 (§XXXIII-1): PASS bắt buộc.
- Unit test `FormulaEngine.explain()` trả đúng breakdown cho ≥3 BOM mẫu có độ phức tạp khác nhau (đơn giản/nhiều panel kính/nhiều PK override).
- Unit test roundtrip cho `snapshot_migration_registry` (dù chưa có migrate_func thật, khung test phải chạy được với 1 migrate_func no-op).

### DoD Phase 0
- Tạo được 1 Quotation hoàn chỉnh qua BOM Dialog, giá tính đúng, `explain()` minh bạch từng con số, ConfigSnapshot ghi đủ field, không lỗi khi xáo trộn `sort_order`.

---

## PHASE 1 — BOM VERSION + WORKFLOW + MATERIAL CHECK HOOK + KHÓA SO FIELD + SITE SURVEY
**Mục tiêu:** kiểm chứng **Kịch bản #2, #3, #4**.

### Trình tự
1. **AL BOM Version** (§XVII) + Workflow "Version Approval Workflow" (core, dùng chung cho cả AL Dynamic Item Rule Version — dựng Workflow này **một lần duy nhất**, đăng ký cho cả 2 DocType).
2. Nâng cấp B0 (VersionPinningResolver) từ stub → thật: resolve theo `valid_from` so với `Quotation.creation_date`; dựng badge UI "Đang dùng BOM vX... có bản mới".
3. **AL BOM Change Log** — ghi nhận mọi thay đổi version + thay đổi `enforce_material_check` (chuẩn bị trước cho bước 6).
4. **Hook E-F khi Sales Order Submit:** tạo AL Installation Order (chỉ header, chưa cần đủ Field Ops), khóa field kích thước trên Sales Order Item (chỉ sửa qua Change Order — Change Order thật sự code ở Phase 2, Phase 1 chỉ cần cơ chế khóa field hoạt động).
5. **AL Cutting Standard** (master, gồm `survey_tolerance_mm`).
6. **AL Site Survey + AL Site Survey Line** — gate `within_tolerance`; hook tự động tạo `AL Design Revision` (Draft, `source_type=SITE_SURVEY_DEVIATION`) khi lệch — nghĩa là **AL Design Revision (§27.4) phải dựng sớm hơn lộ trình gốc ở XXXIV, ngay trong Phase 1**, chỉ ở mức schema + hook tạo Draft (chưa cần luồng Applied/Change Order đầy đủ, việc đó chờ Phase 2). Ghi chú rõ cho đội dev: đừng để Site Survey gate "treo" vì thiếu DocType đích.
7. **AL Project Financial Config** (`enforce_material_check` mặc định bật, quyền tắt chỉ Role Director).
8. **Material Check Hook (hard block)** — 3 điều kiện (a)(b)(c) theo §25.8. **Quyết định tích hợp v16:** đánh giá dùng Stock Reservation for Work Order (core v16) cho điều kiện (a) thay vì tự truy vấn Batch — nếu Stock Reservation core đã đủ chính xác theo `al_color`+`project`, dùng lại; nếu không phủ được điều kiện theo màu/project, giữ nguyên truy vấn Batch tùy biến như tài liệu mô tả. Ghi quyết định vào `AL BOM Change Log`-style ADR (Architecture Decision Record) nội bộ để Phase sau không hỏi lại.
9. **Cutting Plan (khung tối thiểu, chưa cần thuật toán nesting tối ưu đầu thừa — việc đó Phase 3):** đủ để gọi được Material Check Hook và test kịch bản #3.

### Test bắt buộc
- Kịch bản #2, #3, #4 (§XXXIII) PASS.
- Test riêng: tắt `enforce_material_check` chỉ Role Director thực hiện được, có ghi `AL BOM Change Log`.

### DoD Phase 1
- Không thể Confirm Cutting Plan khi thiếu 1 trong 3 điều kiện Material Check; Site Survey lệch dung sai chặn đúng và sinh Design Revision Draft; Quotation cũ giữ nguyên version dù có Publish version mới giữa chừng.

---

## PHASE 2 — PRICING RULE + PAYMENT SCHEDULE + CHANGE ORDER
**Mục tiêu:** kiểm chứng **Kịch bản #5, #6, #8**.
**Điều kiện tiên quyết bắt buộc (theo khuyến nghị v26, §XXXIV ghi chú):** trước khi mở Phase 2, phải **khóa xong thiết kế trên giấy** cho 3 gap mức P0 ảnh hưởng trực tiếp Cost Bucket/Formula:
- R8 — tỷ giá ngoại tệ (`fx_change_pct`/`base_price_change_pct` trên AL Supplier Price List Line, §IV.24)
- R9 — phế liệu/đầu thừa nhôm (cơ chế Serial No chồng Batch, §4.26) — chỉ cần chốt thiết kế, **code thuật toán nesting để Phase 3**
- R10 — permlevel=1 trên Query Report (§24.1) — tận dụng role-based field masking v16, chốt quy tắc coding cho Script Report

Không code Cost Template/Cost Variance/Payment thật với tiền thật trước khi 3 mục trên được rà lại bởi đội kỹ thuật + kế toán (workshop 1 buổi, có biên bản).

### Trình tự
1. **Pricing Rule (core)** thay AL Discount Rule — cấu hình Customer Group + Volume + Project theo §19.1; hook chặn tổng chiết khấu vượt ngưỡng (§19.2) — field `al_discount_approval_ref` trên Quotation.
2. **AL Supplier Price List + Line** (§IV.24) — chốt xong thiết kế R8, code field `fx_change_pct`/`base_price_change_pct`.
3. **Payment Schedule (core) + custom field `al_trigger_type/al_trigger_value/al_is_released`** (§5.10, §27.1) — hook tạo tự động từ `AL BOM.default_milestone_billing_template` khi SO Submit; 4 loại trigger; Client Script validate nút "Create Sales Invoice".
4. **AL Handover Acceptance** (§27.2) — cần dựng trước vì trigger `HANDOVER_SIGNED` phụ thuộc nó, dù thi công đầy đủ chưa xong tới Phase 3 (chỉ cần AL Installation Order tồn tại làm Link).
5. **AL Change Order + AL Change Order Line** (§27.3) — bao gồm luôn field Gap 5 (`requires_scrap_writeoff`/`scrap_writeoff_amount`) và validate theo `al_trace_stage` — dù `al_trace_stage` đầy đủ (offcut Serial No) chưa hoàn thiện tới Phase 3, **validate logic if/else vẫn code được ở Phase 2** vì chỉ cần field `al_trace_stage` tồn tại trên Batch (đã có custom field từ §4.23.3, dựng ở Phase 0/1); phần tự động sinh Serial No offcut khi tick `requires_scrap_writeoff` sẽ nối vào ở Phase 3.
6. **Hoàn thiện AL Design Revision** — chuyển từ "chỉ tạo Draft" (Phase 1) sang đầy đủ luồng Confirmed → Applied, validate `has_price_impact` ↔ `linked_change_order`, trigger BomOrchestrator recalculation.
7. **AL AI Suggestion Log** (schema tối thiểu) — cần có trước để AI Purchasing/Price Forecast (Phase 4) có nơi ghi, nhưng ở Phase 2 chỉ cần tồn tại DocType cho hook `fx_change_pct` vượt ngưỡng ghi vào (chưa cần AI thật, có thể stub bằng rule ngưỡng đơn giản).

### Test bắt buộc
- Kịch bản #5, #6, #8 PASS.
- Kịch bản #11 (Design Revision has_price_impact=0/1) PASS.
- Kịch bản #12 (Gap 1 tỷ giá) — ít nhất phần validate `fx_change_pct` vượt ngưỡng tạo đúng 1 AL AI Suggestion Log, chưa cần AI đề xuất thông minh.

### DoD Phase 2
- Change Order Approved tạo đúng 1 SO bổ sung với `al_change_order_parent`; Payment Schedule tự động release đúng lúc; chiết khấu 3 tầng áp đúng priority + chặn ngưỡng.

---

## PHASE 3 — QUALITY INSPECTION + WARRANTY CLAIM + COST BUCKET→ACCOUNT + MATERIAL TRACE
**Mục tiêu:** kiểm chứng **Kịch bản #7, #9, #10**, hiện thực hóa thuật toán nesting Gap 2.

### Trình tự
1. **Quality Inspection (core) + Quality Inspection Template** "QC Cắt Kính"/"QC Lắp Cửa" + custom field `al_production_order_bridge` (§25.9) — luồng tự động khi Cut Done; gate `production_stage → Ready to Install`.
2. **AL Production Order Bridge ↔ Work Order (core)** — hoàn thiện liên kết đầy đủ (Phase 1 mới chỉ có khung Cutting Plan).
3. **Thuật toán nesting 1D ưu tiên đầu thừa (Gap 2, §25.10, QĐ-38)** — code đúng **1 điểm sửa** trong `AL Aluminum Cutting Plan`: match `Serial No` (`al_is_offcut=1`, `al_piece_length_mm`) trước khi mở thanh mới. Đây là thay đổi thuật toán, cần review riêng, không gộp chung PR với việc khác.
4. **Serial No offcut sinh qua Stock Entry Repack** (§4.26) — nối vào luồng Change Order Gap 5 đã code khung ở Phase 2 (khi `requires_scrap_writeoff=1` → sinh Serial No thật).
5. **Warranty Claim (core, module Support)** thay AL Warranty Claim — custom field `al_installation_order`, `al_defect_category`, `al_warranty_policy`, `al_repair_stock_entry`/`al_repair_journal_entry` (Gap 6, QĐ-42) — hook default `project`/`cost_center`/`account=OH_BH.default_expense_account`.
6. **AL Installation Order/Line, AL Installation Progress (append-only, `cumulative_pct`), AL Installation Cost Actual** — hoàn thiện đầy đủ Field Ops (Phase 1-2 mới có khung).
7. **Cost Bucket → Account mapping** — gán `default_expense_account` cho **toàn bộ** AL Cost Bucket có `bucket_role=LEAF` (điều kiện Checklist Go-live).
8. **AL Cost Variance** (gộp Labor Cost Variance, Gap 4, §XXI) — truy vấn GL Entry lọc theo Account+project+cost_center, thêm `installation_team`/`actual_hours`, `report_group="B. Nhân công"`.
9. **Material Trace hoàn thiện** (`al_trace_stage`, `al_trace_last_updated` trên Batch, §4.25) — đối chiếu với **Serial & Batch Traceability Report (core, v16)**: dùng report core làm lớp hiển thị/đối chiếu chéo, không tạo report trùng lặp.
10. **Batch Wise Valuation kiểm chứng thực tế trên v16** (R1, §XXXV) — verify 100% trước khi dựa vào cho P&L; nếu không đạt, dùng Stock Ledger chi tiết làm nguồn đối chiếu.

### Test bắt buộc
- Kịch bản #7, #9, #10, #13 (Gap 2+5), #16 (Gap 6) PASS.

### DoD Phase 3
- QC Rejected chặn đúng "Ready to Install"; offcut sinh đúng Serial No và được ưu tiên khớp ở lần cắt kế tiếp; Change Order trên dòng đã CUT/INSTALLED bị chặn/yêu cầu writeoff đúng; chi phí bảo hành chảy đúng vào GL qua `OH_BH.default_expense_account`.

---

## PHASE 4 — AI LAYER + DASHBOARD + ACCOUNTING DIMENSION (nếu cần)
**Mục tiêu:** kiểm chứng **Kịch bản #14, #15** + hoàn thiện AI use case.

### Trình tự
1. **AI Hooks Framework** (`after_calculate` 10s, `before_quotation_submit` 5s, `daily_ai_analysis` 60s — tách `frappe.enqueue(queue="long")` cho tác vụ nặng như AI Cutting Optimization).
2. **AL AI Suggestion Log / AL AI Interaction Log** hoàn thiện đầy đủ workflow Approval cho suggestion.
3. Triển khai dần từng AI use case theo độ ưu tiên kinh doanh (gợi ý thứ tự: AI Config Validator → AI Pricing/Negotiation Advisor → AI Quotation Copilot → AI Cutting Optimization → AI Purchasing/Price Forecast → AI Win/Loss → AI Anomaly Detection → AI Project Health Score → AI Voice-to-Progress → AI Root Cause Clustering → AI Drawing-to-BOM → AI PK Suggester → RAG nội bộ). Mỗi use case là 1 sprint độc lập, không chặn nhau.
4. **Dashboard/KPI:** ưu tiên `Number Card` + `Dashboard Chart` + `Workspace` (core) trước; chỉ tạo `AL Dashboard Config`/`AL Sales KPI` custom nếu chứng minh Report Builder/Query Report không biểu diễn được công thức KPI cần thiết.
5. **Accounting Dimension** (VD "Product Type"/"Brand") — chỉ khai báo nếu công ty thật sự cần lọc P&L theo chiều này (§XXXVII.2).
6. **Field-level permission permlevel=1** cho `AL Project Profitability Snapshot` (`actual_material_cost`, `actual_labor_cost`, `gross_profit`, `margin_drift_vs_quoted`) — kết hợp role-based field masking v16 + Role Permission Manager, không code riêng nếu core đủ dùng.
7. **Final Design Register** (Query Report tổng hợp 3 nguồn: Sales Order Item active + Design Revision Applied mới nhất + Site Survey Line, §XXIV) — dựng cuối cùng vì phụ thuộc dữ liệu đủ từ mọi phase trước.

### Test bắt buộc
- Kịch bản #14, #15 PASS. Toàn bộ 16 kịch bản (§XXXIII) chạy lại một lượt tổng thể (regression) trước khi vào Checklist Go-live.

---

## CHECKLIST GO-LIVE (tổng hợp, xem đầy đủ ở §XXXVI của CANONICAL v26)
Trước khi bấm nút go-live, xác nhận **tất cả** các mục sau — không mục nào được đánh dấu "để sau":
- [ ] 16/16 kịch bản kiểm chứng PASS trên môi trường staging giống production nhất có thể
- [ ] Workflow "Version Approval Workflow" test đủ Approve/Reject/Revise cho cả BOM Version và Rule Version
- [ ] Pricing Rule thay đủ 3 loại discount cũ + hook chặn ngưỡng
- [ ] Payment Schedule test đủ 4 loại trigger
- [ ] Quality Inspection Template test đủ luồng tự động khi Cut Done
- [ ] Warranty Claim test đủ luồng từ Installation Order
- [ ] `default_expense_account` gán đủ cho mọi Cost Bucket LEAF
- [ ] Change Order Approved test tạo đúng SO bổ sung
- [ ] Quyền tắt `enforce_material_check` giới hạn đúng Role Director, có audit log
- [ ] Actual cost trong P&L Snapshot khớp GL Entry tuyệt đối, không lệch Cost Bucket
- [ ] AL Design Revision: test đủ 3 source_type, validate has_price_impact ↔ linked_change_order
- [ ] fx_change_pct/base_price_change_pct tính đúng, tạo đúng AI Suggestion Log
- [ ] Serial No offcut sinh đúng qua Stock Entry Repack; nesting ưu tiên đầu thừa
- [ ] Script Report permlevel=1 test giả lập Role Sales → cột bị ẩn/redact đúng
- [ ] AL Cost Variance lọc report_group Nhân công trả đúng dữ liệu
- [ ] AL Change Order Line chặn đúng theo al_trace_stage (CUT/INSTALLED)
- [ ] Warranty Claim default đúng project/cost_center/account khi tạo Stock Entry/Journal Entry sửa chữa

**4 việc song song trước khi Phase 0 kết thúc (theo KẾT LUẬN của tài liệu, không thuộc thiết kế nghiệp vụ nhưng bắt buộc cho vận hành dự án):**
1. ERD tổng thể quan hệ 62 DocType (khuyến nghị: vẽ ngay sau khi Phase 0 xong, dùng chính danh sách DocType đã dựng thật, không vẽ trước khi code vì dễ lệch).
2. Definition of Done chi tiết theo từng Phase (bảng DoD ở trên trong tài liệu này là điểm khởi đầu — mở rộng thành checklist test case cụ thể theo công cụ QA đội dùng).
3. Kế hoạch import Master Data thật (50-200 profile × N brand) — làm song song từ Phase 0, không chờ hết Phase 0 mới bắt đầu nhập liệu mẫu thật.
4. Ma trận phân quyền Read/Write/Create/Submit/Cancel/Amend theo DocType × Role — dựng dần theo từng Phase (không chờ tới cuối), review lại toàn bộ trước go-live.

---

## GHI CHÚ RỦI RO CẦN THEO DÕI XUYÊN SUỐT (không lặp chi tiết, xem §XXXV)
- R1 (Batch Wise Valuation), R3 (dev tự tạo DocType trùng core — checklist bắt buộc "core đã có gì gần cái này chưa"), R4 (AI Cutting Optimization timeout), R5 (Payment Schedule UI hạn chế → bổ sung Query Report), R6 (Schema Registry di trú), R7 (Material Trace hook lỗi thầm lặng — cần log + cảnh báo riêng).
- Với hạ tầng v16 cụ thể: theo dõi thêm rủi ro **tương thích `formula_builder` với Caffeine architecture** của Frappe v16 (đã xử lý ở Bước 1.2) và rủi ro **trùng lặp chức năng** giữa MRP core mới của v16 và `AL Material Plan` tự chế — quyết định rõ ràng ranh giới ở Phase 1, tránh 2 hệ thống MRP chạy song song gây nhiễu dữ liệu.

---

## TÓM TẮT TRÌNH TỰ (nhìn nhanh)

```
Bước 1: Ha tang v16 + kiem tra tuong thich formula_builder
   |
Phase 0: Master Data + Rule/Formula Engine + BomOrchestrator 9 buoc [Kich ban #1]
   |
Phase 1: BOM Version+Workflow + Material Check Hook + khoa SO field + Site Survey
         (Design Revision: dung schema+hook Draft som o day)          [Kich ban #2,3,4]
   |
   +-- (Rao chan bat buoc: khoa thiet ke R8/R9/R10 truoc khi qua Phase 2)
   |
Phase 2: Pricing Rule + Payment Schedule + Change Order + Design Revision day du [#5,6,8,11,12]
   |
Phase 3: Quality Inspection + Warranty Claim + Cost Bucket->Account
         + Material Trace + thuat toan nesting offcut (Gap 2)         [#7,9,10,13,16]
   |
Phase 4: AI Layer + Dashboard + Accounting Dimension (neu can)        [#14,15 + regression 16/16]
   |
Checklist Go-live (tat ca muc, khong tru)
   |
GO-LIVE
```
