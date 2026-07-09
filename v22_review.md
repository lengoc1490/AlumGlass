# ĐÁNH GIÁ KIẾN TRÚC ALUMGLASS v22 — Senior Architect Review

> **Ngày:** 2026-07-03
> **Người đánh giá:** Senior Architect ERPNext (hiểu nghiệp vụ nhôm kính: tính giá, mua bán, sản xuất, thi công, thanh quyết toán, kế toán lãi lỗ)
> **Tài liệu gốc:** `v22.md` (Canonical, 1756 dòng)

---

## 1. CHẤM ĐIỂM TỔNG THỂ: 8.5/10

Đây là một trong những thiết kế custom ERPNext **chín nhất** cho ngành nhôm kính. 27 nguyên tắc nhất quán, kiến trúc 8 tầng với DAG làm backbone, immutable versioning xuyên suốt, và hook-based module không phá lõi — đạt tầm enterprise-grade.

---

## 2. 5 QUYẾT ĐỊNH XUẤT SẮC

### 2.1 Tồn kho màu = Batch, không phải Item Variant (§4.23)
Quyết định **can đảm và chính xác nhất** trong toàn bộ thiết kế. Một công ty có 200 tiết diện × 50 màu = 10.000 Item Variant, 80% chỉ dùng 1 lần, báo cáo tồn kho vô nghĩa. Batch + `al_is_reserved_for_project` + Batch Wise Valuation trả lại đúng bản chất vật lý của ngành: tiết diện là trục cố định, màu là thuộc tính giao dịch.

### 2.2 DAG topology thay priority thủ công (§IX)
Bỏ `priority` number để dùng `FormulaVariableBinding` DAG của `formula_builder` loại bỏ cả lớp bug "quên đánh priority". Đây là bước tiến kiến trúc mà ít thiết kế ERPNext custom nào làm được.

### 2.3 Site Survey → chặn Cutting Plan (§25.7, Nguyên tắc #26)
Bắt đúng nỗi đau #1 ngành nhôm kính: sai số công trình. Tách `survey_tolerance_mm` (dung sai khảo sát) khỏi `cutting_tolerance_formula` (dung sai gia công) là quyết định rất tinh tế — chỉ người có kinh nghiệm thực địa mới nghĩ ra.

### 2.4 Handover Acceptance tách khỏi tiến độ nội bộ (§27.5)
Chuẩn về mặt pháp lý/kế toán. Dùng % tiến độ tự ghi của đội thi công để xuất hóa đơn milestone là rủi ro công nợ — khách hàng tranh chấp khối lượng thực tế, toàn bộ billing schedule vỡ. Handover Acceptance là chứng từ pháp lý độc lập.

### 2.5 Hook-based Module (Tầng 6, Nguyên tắc #13)
Tầng 1-4 giữ nguyên tuyệt đối, mọi mở rộng nằm ở Tầng 6 dưới dạng hook đăng ký. Pattern này giúp hệ thống mở rộng vô hạn mà lõi không phình — đáng giá hơn bất kỳ tính năng đơn lẻ nào.

---

## 3. LỖ HỔNG P0 — PHẢI SỬA TRƯỚC GO-LIVE

### 🔴 P0-1: Cutting Plan không kiểm tra Material Availability trước Confirm

**Hiện trạng:** Cutting Plan đọc ConfigSnapshot → danh sách item + batch → đề xuất cắt. Không có bước kiểm tra material availability thực tế trước khi Confirm.

**Kịch bản lỗi:**
1. MRP tạo Material Plan cho màu `is_standard_stock=0`, `deposit_status=Pending`
2. Sản xuất tạo Cutting Plan và Confirm khi batch chưa về kho
3. Cắt xong nhưng không có hàng để ráp → bán thành phẩm nằm chờ → trễ tiến độ
4. Nếu đã xuất kho SO nhưng chưa có PI → âm tồn kho ảo trên sổ sách
5. `AL Installation Order.planned_start` sai vì phụ thuộc vào ngày có hàng thực tế

**Giải pháp: Material Check Hook (hard block) trước Confirm Cutting Plan:**

```
Trước khi Cutting Plan Draft → Confirmed:
  1. Với mỗi dòng có batch_no cố định → kiểm tra qty available trong stock
  2. Với dòng is_outsourced=1 → kiểm tra PO/Subcontracting Order tương ứng đã đặt
  3. Với dòng màu is_standard_stock=0 → kiểm tra deposit_status=Paid
  4. Vượt qua tất cả → Confirm. Không → hard block + thông báo cụ thể dòng nào thiếu
```

Hook này là **hard block** (không phải soft warning) vì hậu quả của Confirm khi chưa có hàng là không thể đảo ngược: phiếu cắt đã in, công nhân đã setup máy, bán thành phẩm nằm chờ gây tắc dây chuyền.

### 🔴 P0-2: Khóa field `al_W_mm`/`al_H_mm` trên SO sau khi tạo từ Quotation

**Hiện trạng:** SO copy field từ Quotation qua hook `copy_al_fields`, nhưng không khóa field sau khi copy. Nếu SO cho sửa `al_W_mm`/`al_H_mm` tự do, toàn bộ cơ chế Site Survey → BOM Revision sẽ bị vòng qua bằng "cửa sau" này.

**Giải pháp:**
- Field `al_W_mm`/`al_H_mm`/`al_bom_vars` trên SO Item → **read-only** sau khi SO Submit
- Mọi thay đổi kích thước phải đi qua luồng: Site Survey → BOM Revision → ConfigSnapshot mới → Change Order (§27.0)
- Validate ở SO `before_save`: nếu `al_config_snapshot` đã có và field thay đổi → reject

Đây là hệ quả trực tiếp của Nguyên tắc #26 (Site Survey) — không có ngoại lệ.

### 🔴 P0-3: Verify Batch Wise Valuation thực tế → sửa R27

**Bối cảnh:** R27 trong thiết kế gốc cảnh báo rằng "Batch Wise Valuation" của ERPNext có thể không tách giá vốn tuyệt đối theo batch trong mọi report (chỉ đúng trong Stock Ledger, vẫn bình quân hóa ở Gross Profit/Item report). Toàn bộ §4.23 phụ thuộc vào giả định này đúng.

**Giải pháp điều chỉnh R27 (từ review kiến trúc sư — tách 2 mục tiêu):**

Mục tiêu của §4.23 thực chất gồm 2 lớp độc lập:
- **(a) Mục tiêu vật lý:** không lắp nhầm màu — quan trọng nhất, Batch đạt được 100%
- **(b) Mục tiêu kế toán:** giá vốn chính xác tuyệt đối theo batch — quan trọng nhưng ít nghiêm trọng hơn nếu sai lệch nhỏ

Nếu verify cho thấy ERPNext chỉ đạt (a) mà chưa đạt (b) hoàn hảo, hệ thống **vẫn có giá trị lớn** (tránh sự cố lắp sai màu) — không cần đại tu sang giải pháp khác. Sửa R27 để phản ánh 2 lớp này thay vì "được ăn cả, ngã về không".

**Hành động:** test đối chiếu Gross Profit theo batch cho ≥1 Item có ≥2 màu trên đúng version ERPNext đang dùng trước khi coi P0 đã xong.

---

## 4. VẤN ĐỀ P1 — NÊN LÀM TRONG PHASE 1-3

### 🟡 P1-1: Version pinning theo `valid_from` pattern của ERPNext

**Hiện trạng:** BomOrchestrator đọc `current_version` sống tại thời điểm `calculate()`. Quotation Draft không được bảo vệ — nếu Kỹ thuật publish version mới giữa lúc Sales đang làm, giá có thể nhảy.

**Phản biện từ Senior Architect:** BOM trong ngành nhôm kính do Kỹ thuật tạo, **rất ít thay đổi đột ngột** — không giống như Item Price biến động theo thị trường hàng ngày. Pattern `valid_from`/`valid_to` của ERPNext Item Price là đủ dùng, không cần cơ chế cache pinning phức tạp.

**Giải pháp:** Thêm `valid_from` (Date/DateTime, mặc định = `published_on`) và `valid_to` (tự set khi version mới Publish) vào `AL BOM Version` và `AL Dynamic Item Rule Version`.

```
Với mỗi Quotation Draft:
  → Lấy current_version của BOM/Rule
  → Nếu current_version.valid_from > Quotation.creation_date:
      → Dùng version có valid_from <= creation_date (version tại thời điểm tạo)
      → Badge: "Đang dùng BOM v3 (đã có v4 từ 15/06)"
  → Ngược lại: dùng current_version
```

**Ưu điểm so với cache pinning:**
- Deterministic: cùng creation_date luôn resolve ra cùng version
- Không phụ thuộc TTL, không sợ cache hết hạn
- Audit được: nhìn `valid_from` là biết thời điểm chuyển version
- Đúng tinh thần "dùng ERPNext core pattern" — Item Price đã làm y hệt

**Phase:** Làm trong Phase 2 (cùng BOM Version Control), không chặn Phase 1.

### 🟡 P1-2: Project + Cost Center — ERPNext có sẵn, cần hook enforce

**Đánh giá lại:** ERPNext đã có `project` và `cost_center` trên Purchase Invoice, Stock Entry, Journal Entry — **không cần custom field nào**. Đây không phải lỗ hổng thiết kế.

**Cái thiếu là cơ chế tự động populate:**

1. Hook `before_save` trên Purchase Invoice: nếu PI item ← PO ← Material Plan ← SO → tự động set `project` + `cost_center`
2. Hook tương tự trên Stock Entry: nếu SE Detail ← Cut Order ← SO → tự động populate `project`
3. Validate cứng: nếu item thuộc dự án có `AL Project Financial Config` → `project` không được để trống khi submit

**Kết luận:** Rút khỏi danh sách lỗ hổng — đây là vấn đề triển khai hook, không phải thiết kế. Bổ sung vào checklist go-live.

### 🟡 P1-3: QC gate trước Installation

Thiết kế đã có `production_stage` (Cutting/Assembly/QC/Ready to Install) trong `AL Production Order Bridge` nhưng chưa có DocType ghi nhận kết quả QC. Cần bổ sung:

- **AL Quality Check** (DocType nhẹ): `production_order_bridge` (Link), `check_date`, `checked_by` (Link Employee), `result` (Passed/Failed/Rework), `defect_notes` (Small Text)
- Hook: `AL Installation Order` không thể chuyển `In Progress` nếu `production_stage != "Ready to Install"` (QC chưa passed)

### 🟡 P1-4: new_bom_version trên Change Order Line

`AL Change Order Line.bom_reference` hiện là optional Link → AL BOM. Cần thêm `new_bom_version` (Link → AL BOM Version) để làm chặt liên kết: khi phát sinh thay đổi BOM, Change Order tham chiếu chính xác version BOM mới đã publish — không chỉ tham chiếu BOM master.

### 🟡 P1-5: INSTALLED_M2 trigger cho Milestone Billing

Nhiều hợp đồng thanh toán theo m² lắp đặt thực tế thay vì %. Thêm `trigger_type=INSTALLED_M2` vào `AL Milestone Billing Line`: khi `AL Installation Progress` ghi nhận đủ m² đã lắp → milestone Ready to Bill. Triển khai đơn giản, rủi ro thấp.

### 🟡 P1-6: Field-level permission cho dữ liệu giá vốn

Frappe hỗ trợ `permlevel` trên field + Role Permission Manager sẵn có. Sales chỉ thấy giá bán, không thấy giá vốn. Các field cần bảo vệ:
- `AL Cost Template Line.actual_cost`
- `AL Project Profitability Snapshot.*`
- `AL Cost Variance.variance_pct`

Dễ triển khai, đúng tinh thần Nguyên tắc #1.

### 🟡 P1-7: Material Trace Log (xuất kho → cắt → lắp)

Thất thoát vật tư giữa kho→xưởng→công trình là rủi ro tài chính lớn (5% nhôm = 100 triệu trên dự án 2 tỷ). Tận dụng Batch/Stock Ledger có sẵn thay vì tự xây DocType riêng:

- Custom field `al_trace_stage` (Select: ISSUED/CUT/INSTALLED/RETURNED/LOST) trên **Batch**
- Hook tự động update: Stock Entry submit → ISSUED, Cutting Plan confirm → CUT, Installation Order Line Done → INSTALLED
- Cảnh báo: Batch đã ISSUED > X ngày chưa INSTALLED, tổng INSTALLED < ISSUED - RETURNED cuối dự án

### 🟡 P1-8: Snapshot schema versioning

Khi cấu trúc snapshot JSON thay đổi giữa các phiên bản phần mềm (VD: v22 thêm `survey_tolerance_mm` vào Cutting Standard snapshot), snapshot cũ không được migrate → Diff Tool crash hoặc sai. Giải pháp:

- `snapshot_version` (Int) trên mọi snapshot-bearing DocType
- Snapshot Schema Registry: map `snapshot_version → migrate_func(old_data) → new_data`
- `compare_versions()`: nếu schema khác → migrate về schema mới nhất trước khi diff
- Mọi migration function phải có roundtrip test (migrate lên rồi xuống → khớp ban đầu)

---

## 5. VẤN ĐỀ P2 — CÂN NHẮC SAU (PHASE 5+)

### 🟢 P2-1: Subcontracting — dùng ERPNext native

ERPNext (v14+) có Subcontracting Order/Receipt native. Thay vì tự xây quy trình PO gia công từ đầu:
- Thêm field `subcontracting_order` (Link) trên `AL Cutting Plan Line` cho dòng `is_outsourced=1`
- Tận dụng luồng Subcontracting Order → Subcontracting Receipt có sẵn
- Đúng tinh thần "tận dụng core" như đã làm với Payment Schedule (§27.1)

### 🟢 P2-2: Cost Index — tách price variance khỏi usage variance

Nếu dự án kéo dài qua đợt biến động giá LME, `explain_variance()` cần phân biệt "mua đắt do thị trường" vs "dùng nhiều hơn dự toán":
- `AL Cost Index` (Master): item_code, valid_from_month, base_price, actual_price
- `CostAccumulator.attach_cost_index()` → optional metadata trong ConfigSnapshot
- `AL Supplier Price List` (§4.24) đã có dữ liệu nguồn

**Mức độ ưu tiên P2** (không phải P1 như reviewer khác đề xuất) vì: (a) chu kỳ dự án nhôm kính thường 2-4 tháng, hiếm khi vượt 12 tháng; (b) `AL Supplier Price List` đã cho phép tính thủ công khi cần; (c) cần ≥6 tháng dữ liệu PI mới đủ tín hiệu.

### 🟢 P2-3: MRP lead time → installation scheduling

`AL Material Plan Line.supplier_confirmed_lead_time_days` hiện chỉ cảnh báo trễ. Nên dùng để tính `earliest_install_date_advised` (field mới trên `AL Installation Order`, chỉ tham khảo, không chặn).

### 🟢 P2-4: Labor rate revision cho dự án dài

`AL Installation Order Line.planned_nc_ld_cost` immutable từ SO. Với dự án >6 tháng, nhân công có thể biến động. Thêm `revised_nc_ld_rate` tùy chọn + `AL Labor Cost Variance` hiển thị 2 lát cắt: variance vs plan và variance vs revised.

### 🟢 P2-5: Overhead theo giờ máy/m²

`overhead_allocation_method` hiện có NONE/PCT_OF_REVENUE/FIXED_AMOUNT. Có thể mở rộng thêm MACHINE_HOUR và PER_M2 nếu phát sinh nhu cầu thực tế.

### 🟢 P2-6: Cảnh báo PROJECT_DELAY/MATERIAL_SHORTAGE

Thêm `alert_type` mới vào `AL Alert Config` đã có sẵn. Độ ưu tiên thấp, không gấp.

### 🟢 P2-7: Điều chuyển vật tư giữa dự án

Hợp lý nhưng ít xảy ra (mỗi dự án thường đặt màu riêng vì sợ lệch tông). Có thể để Phase sau khi có nhu cầu thực tế.

---

## 6. KHÔNG THÊM VÀO THIẾT KẾ

| # | Mục | Lý do |
|---|---|---|
| ❌ | MRP Cache table | Premature optimization — chưa có bằng chứng MRP chậm. QĐ-21 (compressed_snapshot) đã xử lý đúng vấn đề hiệu năng. Cache riêng tạo nguồn dữ liệu thứ hai cần đồng bộ → vi phạm single source of truth. Chỉ xem xét nếu Phase 6+ đo được MRP >X giây với Y Quotation. |
| ❌ | Thay Batch bằng Cost Center/Serial No cho tồn kho màu | Hai bài toán khác nhau không thay thế được nhau. Cost Center giải quyết "chi phí thuộc dự án nào", Batch giải quyết "giá vốn 2 màu không bị trộn". Serial No cho nhôm thanh/kính tấm (vật tư đo theo mét/m²) là overhead vận hành không thực tế. |

---

## 7. ĐÁNH GIÁ CHI TIẾT CÁC ĐỀ XUẤT TỪ REVIEW KIẾN TRÚC SƯ

### Nhóm A — Đã áp dụng / đưa vào khuyến nghị trên

| # | Đề xuất gốc | Trạng thái |
|---|---|---|
| 2.2 | Version pinning khi mở Quotation | → P1-1: điều chỉnh sang `valid_from` pattern |
| 2.3 | Khóa field trên SO | → P0-2: giữ nguyên |
| 2.5 | Project/Cost Center bắt buộc | → P1-2: ERPNext có sẵn, chỉ cần hook enforce + checklist |
| 2.7 | Field-level permission giá vốn | → P1-6: giữ nguyên |
| 2.12 | QC trước thi công | → P1-3: giữ nguyên |
| 2.13 | INSTALLED_M2 trigger | → P1-5: giữ nguyên |
| 2.6 | new_bom_version trên Change Order Line | → P1-4: giữ nguyên |

### Nhóm B — Phản biện đúng, không áp dụng nguyên văn

| # | Đề xuất gốc | Kết luận |
|---|---|---|
| 2.1 | Batch Wise Valuation → Cost Center/Serial No | **Bác bỏ.** Cost Center giải quyết bài toán khác. Serial No không thực tế cho vật tư đo mét/m². Giữ nguyên §4.23, sửa R27 theo 2 lớp (vật lý vs kế toán). |

### Nhóm C — Hoãn hoặc điều chỉnh

| # | Đề xuất gốc | Kết luận |
|---|---|---|
| 2.11 | Subcontracting | → P2-1: đúng hướng nhưng dùng ERPNext native, không tự xây |
| 2.10 | MRP Cache | → Không thêm |
| 2.9 | PROJECT_DELAY/MATERIAL_SHORTAGE alert | → P2-6 |
| 2.4 | Overhead theo giờ máy/m² | → P2-5 |
| 2.8 | Điều chuyển vật tư giữa dự án | → P2-7 |

---

## 8. ĐÁNH GIÁ 7 VẤN ĐỀ KỸ THUẬT TỪ DEEP REVIEW

| # | Vấn đề | Đánh giá | Đưa vào |
|---|---|---|---|
| 1 | BomOrchestrator không pin version | Đúng. Điều chỉnh: dùng `valid_from` thay vì cache pinning | P1-1 |
| 2 | Cutting Plan không kiểm tra material availability | Đúng, critical | P0-1 |
| 3 | Snapshot schema versioning | Rất đúng — chỉ người từng migrate thực tế mới nghĩ ra | P1-8 |
| 4 | Cost Template không tách price vs usage variance | Đúng, nhưng hạ xuống P2 | P2-2 |
| 5 | MRP không tính lead time → scheduling | Đúng | P2-3 |
| 6 | Thiếu material trace log | Đúng, nâng lên P1 vì rủi ro tài chính thực tế lớn | P1-7 |
| 7 | Labor rate revision | Đúng | P2-4 |

---

## 9. TỔNG HỢP KHUYẾN NGHỊ THEO PHASE

```
PHASE 0 (trước mọi phase khác):
  ✅ §4.23 — Sửa tồn kho màu (Batch + AL Color Standard)
  ✅ P0-3 — Verify Batch Wise Valuation thực tế, sửa R27 theo 2 lớp

PHASE 1 (Core Engine):
  ✅ Tầng 1-4: Master Data, Rule/Formula Engine, Orchestration
  🔴 P0-1 — Material Check Hook trước Confirm Cutting Plan
  🔴 P0-2 — Khóa field al_W_mm/al_H_mm trên SO

PHASE 2 (Module Commercial + Version Control):
  🟡 P1-1 — Version pinning valid_from trên BOM/Rule Version
  🟡 P1-8 — Snapshot schema versioning + Schema Registry
  🟡 P1-2 — Hook enforce Project/CostCenter trên PI/SE/JE

PHASE 3 (Sản Xuất + Site Survey):
  🟡 P1-3 — QC gate trước Installation
  🟡 P1-6 — Field-level permission giá vốn

PHASE 4 (Thi Công + Thanh Quyết Toán):
  🟡 P1-4 — new_bom_version trên Change Order Line
  🟡 P1-5 — INSTALLED_M2 trigger
  🟡 P1-7 — Material Trace Log (Batch hook)

PHASE 5+ (Kế toán Lãi Lỗ + Tối ưu):
  🟢 P2-1 → P2-7 — Subcontracting, Cost Index, Lead time, Labor revision...
```

---

## 10. KẾT LUẬN

**v22 đã sẵn sàng cho Phase 0-1 triển khai**, với điều kiện 3 mục P0 được xử lý trước hoặc trong Phase 1:

1. **P0-1** — Material Check Hook trước Confirm Cutting Plan
2. **P0-2** — Khóa field kích thước trên SO
3. **P0-3** — Verify Batch Wise Valuation + sửa R27

Thiết kế tổng thể vững, 27 nguyên tắc nhất quán, DAG backbone đúng đắn. Điểm yếu nhất nằm ở **biên giới giữa các module** — nơi các tình huống liên module (MRP → Cutting Plan → Installation) chưa được xử lý đủ sâu. Đây là phần khó nhất của mọi ERP và v22 đã làm tốt hơn phần lớn thiết kế cùng loại.

Với các điều chỉnh P0/P1 ở trên, v23 sẽ đạt độ chín cho triển khai production toàn diện.

---

*Đánh giá này bổ sung và điều chỉnh một phần các review trước đó, dựa trên phản biện thực tế từ kiến trúc sư trưởng am hiểu ERPNext và nghiệp vụ nhôm kính.*
