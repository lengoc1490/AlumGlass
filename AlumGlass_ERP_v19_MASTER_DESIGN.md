# AlumGlass ERP v19 — MASTER DESIGN (Đặc tả triển khai đầy đủ, đầu-cuối)

> **App name:** `aluglass` (Frappe custom app trên ERPNext core) + `formula_builder` (engine phụ thuộc)
> **Phiên bản:** v19.0 MASTER — hợp nhất v17 FINAL + v18 Upgrade Spec + Senior Review, vá các gap P0, bổ sung toàn bộ vòng đời còn thiếu
> **Trạng thái:** Sẵn sàng dùng làm tài liệu triển khai thực tế (chưa gồm code — thiết kế cấu trúc + quy trình)
> **Phạm vi:** Báo giá → BOM → Mua vật tư → Sản xuất → Thi công → Thanh quyết toán → Kế toán lãi lỗ → AI toàn dự án

> *"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi. Minh bạch từ báo giá tới quyết toán."*

---

## MỤC LỤC

0. Cách dùng tài liệu này
I. Nguyên tắc thiết kế hợp nhất (21 nguyên tắc, v11→v19)
II. Kiến trúc tổng thể — Sơ đồ tầng đầy đủ (8 tầng)
III. Danh mục DocType tổng hợp (Core + Module cũ + Module mới)
IV. VÁ GAP P0: Versioning cho AL Dynamic Item Rule
V. Module Sản Xuất (Production & Cutting)
VI. Module Thi Công (Field Operations / Installation)
VII. Module Thanh Quyết Toán (Milestone Billing)
VIII. Module Kế Toán Lãi Lỗ theo Công trình (Project Profitability)
IX. Quy trình nghiệp vụ đầu-cuối (Lead → Quyết toán → Đóng sổ)
X. Tầng AI toàn diện (thiết kế theo từng module + nguyên tắc quản trị)
XI. BomOrchestrator v19 — Cập nhật hook cho Production/Installation
XII. ConfigSnapshot & Audit Trail — Mở rộng tới quyết toán
XIII. Phân quyền & Vai trò (mở rộng)
XIV. Lộ trình triển khai tổng thể (Phase 1–7)
XV. Rủi ro & Điểm theo dõi (hợp nhất, đã cập nhật)
XVI. Checklist Go-live

---

## 0. CÁCH DÙNG TÀI LIỆU NÀY

Tài liệu này **không thay thế** v17 FINAL và v18 Upgrade Spec — nó là lớp hợp nhất (consolidation layer) đứng trên cả hai:

- **Phần đã đúng và đầy đủ trong v17/v18** (Formula Engine, ProfileInterpreter, DAG, 3 chế độ Item Selection, Discount Stack, Approval, MRP Lite, Cost Variance, Notification, Sales Analytics): **giữ nguyên, chỉ dẫn chiếu lại**, không lặp lại chi tiết code — tham khảo file gốc khi implement.
- **Phần cần vá (P0)**: đặc tả đầy đủ tại đây, ưu tiên implement **trước khi go-live**, không đợi v20.
- **Phần hoàn toàn mới** (Sản xuất, Thi công, Thanh quyết toán, P&L, AI toàn diện): đặc tả đầy đủ cấu trúc DocType + quy trình tại đây, sẵn sàng để team code hóa.

**Nguyên tắc bất biến khi implement:** mọi module mới đều phải tuân thủ Nguyên tắc #13 (Module Hook, không sửa Orchestrator lõi) và Nguyên tắc #14 (immutable snapshot cho mọi thứ ảnh hưởng đến giá/chi phí đã cam kết với khách hoặc nhà cung cấp).

---

## I. NGUYÊN TẮC THIẾT KẾ HỢP NHẤT (21 NGUYÊN TẮC)

| # | Nguyên tắc | Nguồn | Ghi chú v19 |
|---|---|---|---|
| 1 | Zero Python trong DB | v11 | Không đổi |
| 2 | Chọn Item trực tiếp (+ Dynamic từ v18) | v11/v18 | Không đổi |
| 3 | `show_condition` thay `if/elif` | v11 | Không đổi |
| 4 | Tách vật liệu, thống nhất bảng `al_lines` | v16 | Không đổi |
| 5 | DAG là nguồn sự thật về thứ tự tính | v16 | Không đổi |
| 6 | Kính đa tấm là tập hợp panel động | v14 | Không đổi |
| 7 | Giá kính tách khỏi kích thước sản xuất | v14 | **v19: kích thước sản xuất thực tế (cắt) tách tiếp khỏi kích thước tính giá — xem §V** |
| 8 | Phụ kiện: mặc định + thay thế | v14 | Không đổi |
| 9 | Phụ thuộc chéo qua context phẳng | v16 | Không đổi |
| 10 | Rule là thư viện dùng chung | v11 | Không đổi |
| 11 | Formula Engine là lõi DUY NHẤT | v14/v18 | Không đổi — áp dụng cả DynamicItemResolver |
| 12 | Minh bạch tuyệt đối (ConfigSnapshot + explain()) | v15 | **v19: mở rộng minh bạch tới Rule Version, Production, Installation, Settlement — không chỉ dừng ở giá bán** |
| 13 | Module độc lập, hook không phá lõi | v17 | **v19: áp dụng cho toàn bộ module mới (Production/Installation/Settlement/P&L)** |
| 14 | BOM Version = immutable snapshot | v17 | Không đổi |
| 15 | Approval trước khi hiệu lực | v17 | Không đổi |
| 16 | DynamicItemResolver dùng FormulaEngine.evaluate_single() | v18 | Không đổi |
| 17 | Formula Variable Binding thay AL Variable Binding | v18 | Không đổi |
| 18 | AL Calculation Rule — tinh gọn, không xóa | v18 | Không đổi |
| 19 | Cost Template + Formula Set — optional | v18 | Không đổi |
| **20 ★** | **AL Dynamic Item Rule = immutable versioned, giống BOM Version** | **v19 MỚI (P0)** | Tái dùng pattern BOMVersionManager — xem §IV |
| **21 ★** | **AI luôn là đề xuất, không tự ghi vào bất kỳ snapshot/version nào mà không qua Approval Workflow đã có sẵn** | **v19 MỚI** | Áp dụng cho mọi use case AI ở §X |

---

## II. KIẾN TRÚC TỔNG THỂ — SƠ ĐỒ TẦNG ĐẦY ĐỦ (8 TẦNG)

Kiến trúc **không thêm tầng lõi mới** — mọi mở rộng nghiệp vụ (Sản xuất, Thi công, Thanh quyết toán, P&L) đều là **module trong Tầng 6**, đăng ký qua Hook Registry, đúng Nguyên tắc #13. Đây là quyết định kiến trúc quan trọng nhất của v19: **không phá vỡ triết lý "6 tầng lõi bất biến"** đã được v16-v18 bảo vệ nghiêm ngặt.

```
TẦNG 7 — AI LAYER
  (v18 đã có) AI Formula Generator · AI Config Validator · AI PK Suggester
  ★ MỚI v19:  AI Quotation Copilot · AI Win/Loss Analysis · AI Cutting Optimization
              AI Project Health Score · AI Anomaly Detection (mở rộng sang nhân công/thi công)
  Nguyên tắc quản trị: mọi output AI đi qua Approval Workflow (Tầng 6A) — không ghi thẳng

TẦNG 6 — MODULE LAYER (Hook-based, không phá lõi)
  6A. Commercial   (v17, không đổi): BOM Version · Approval · Discount Stack · Notification · Sales Analytics
  6B. Supply       (v17, không đổi): MRP Lite · Cost Variance (vật tư)
  6C. Production ★MỚI: Cutting Optimization · AL Glass Inventory Bridge (chính thức hóa) · Manufacturing Bridge
  6D. Field Ops  ★MỚI: Installation Order/Progress · Warranty Tracking
  6E. Financial  ★MỚI: Milestone Billing · Project Profitability (P&L) · Labor/Install Cost Variance

TẦNG 5 — PRESENTATION
  BOM Dialog · Glass Selector · PK Panel · Version Badge · Approval Inbox · Discount Selector
  ★ MỚI: Production Board (Kanban cắt) · Installation Mobile Checklist · Project P&L Dashboard

TẦNG 4.5 — DYNAMIC ITEM RESOLVER (v18, không đổi cấu trúc — chỉ vá versioning §IV)
  Fixed / Rule (nay có version) / Formula — Pre-Resolution Phase

TẦNG 4 — ORCHESTRATION
  VariableResolver v3 · ProfileInterpreter v2 · PkResolver · CostAccumulator v2
  BomOrchestrator — 7 bước (v18) + 2 hook mới cho Production/Installation (§XI)

TẦNG 3 — FORMULA ENGINE (formula_builder) — KHÔNG SỬA, giữ nguyên tuyệt đối

TẦNG 2 — RULE ENGINE & VARIABLE BINDING
  AL Calculation Rule · Formula Variable Binding
  AL Dynamic Item Rule ★ nay có version (§IV) · AL Discount Rule

TẦNG 1 — MASTER DATA
  ERPNext core + 34 DocType v17 + 3 DocType v18 (Dynamic Item Rule)
  ★ MỚI v19: AL Cutting Standard · AL Installation Team · AL Warranty Policy · AL Project Financial Config
```

**Vì sao không thêm "Tầng 8 — Production"?** Vì làm vậy sẽ phá nguyên tắc cốt lõi "engine lõi bất biến, module mở rộng qua hook" đã được chứng minh đúng qua v16-v18. Sản xuất/Thi công/Thanh quyết toán đều là **hệ quả nghiệp vụ sau khi giá đã chốt** — chúng tiêu thụ dữ liệu từ ConfigSnapshot/BOM Version, không cần chạm vào Tầng 1-4. Xếp chúng vào Tầng 6 (Module) giữ tính nhất quán kiến trúc và cho phép team Production làm việc độc lập với team Formula/Pricing.

---

## III. DANH MỤC DOCTYPE TỔNG HỢP

### 3.1 Core + Module cũ (không đổi — xem v17 FINAL / v18 Spec)

34 DocType v17 + 3 DocType v18 (`AL Dynamic Item Rule`, `AL Dynamic Item Threshold Row`, `AL Dynamic Item Lookup Row`) — **giữ nguyên schema**, chỉ bổ sung field version ở §IV.

### 3.2 DocType mới v19 — theo module

| # | DocType | Loại | Module | Mục đích |
|---|---|---|---|---|
| 38 | **AL Dynamic Item Rule Version** | Master | Vá gap | Snapshot bất biến của Rule tại thời điểm publish |
| 39 | **AL Cutting Standard** | Master | Production | Quy cách thanh nhôm chuẩn (chiều dài phôi, dung sai cắt) theo profile |
| 40 | **AL Glass Cutting Plan** | Master | Production | Kế hoạch cắt kính tối ưu (nesting) từ pool SO |
| 41 | **AL Glass Cutting Plan Line** | Child | Production | Từng tấm cắt trong kế hoạch, gắn item_variant/batch |
| 42 | **AL Aluminum Cutting Plan** | Master | Production | Kế hoạch cắt nhôm tối ưu (cutting-stock) theo thanh phôi |
| 43 | **AL Aluminum Cutting Plan Line** | Child | Production | Từng đoạn cắt, phế liệu (offcut) |
| 44 | **AL Glass Cut Order** *(chính thức hóa từ Phase 3 v17)* | Master | Production | Lệnh cắt gắn với SO cụ thể |
| 45 | **AL Glass Cut Line** *(kế thừa v17 Phase 3)* | Child | Production | Chi tiết từng tấm |
| 46 | **AL Production Order Bridge** | Master | Production | Liên kết SO → ERPNext Work Order, đồng bộ trạng thái |
| 47 | **AL Installation Team** | Master | Field Ops | Đội thi công (nhân sự, năng lực, khu vực phụ trách) |
| 48 | **AL Installation Order** | Master | Field Ops | Lệnh thi công theo SO/hạng mục công trình |
| 49 | **AL Installation Order Line** | Child | Field Ops | Từng hạng mục lắp đặt (liên kết Quotation Item/BOM) |
| 50 | **AL Installation Progress** | Master | Field Ops | Nhật ký tiến độ, % hoàn thành, ảnh nghiệm thu |
| 51 | **AL Installation Cost Actual** | Master | Field Ops | Chi phí nhân công/thi công thực tế theo Installation Order |
| 52 | **AL Warranty Policy** | Master | Field Ops | Chính sách bảo hành theo loại sản phẩm |
| 53 | **AL Warranty Claim** | Master | Field Ops | Yêu cầu bảo hành, chi phí sửa lỗi |
| 54 | **AL Milestone Billing Plan** | Master | Settlement | Kế hoạch thanh toán theo đợt, gắn Payment Schedule ERPNext |
| 55 | **AL Milestone Billing Line** | Child | Settlement | Từng đợt: % giá trị, điều kiện kích hoạt, trạng thái |
| 56 | **AL Project Financial Config** | Master | Financial | Cấu hình cách phân bổ chi phí gián tiếp theo dự án |
| 57 | **AL Project Profitability Snapshot** | Master | Financial | Snapshot P&L theo Project/SO tại một thời điểm (immutable, giống ConfigSnapshot) |
| 58 | **AL Labor Cost Variance** | Master | Financial | So sánh `nc_ld_rate` dự toán vs chi phí nhân công/thi công thực tế |
| 59 | **AL AI Suggestion Log** | Master | AI Governance | Ghi nhận mọi đề xuất AI + trạng thái chấp nhận/từ chối (RLHF-ready) |

> **Tổng: 37 DocType (v17+v18) + 22 DocType mới v19 = 59 DocType.** Số lượng lớn nhưng đúng tinh thần "mỗi module độc lập, không phình engine lõi" — Tầng 1-4 không đổi 1 dòng.

---

## IV. VÁ GAP P0: VERSIONING CHO AL DYNAMIC ITEM RULE

Đây là điều kiện go-live, không phải cải tiến sau. Thiết kế tái dùng nguyên pattern `AL BOM Version` đã có, đảm bảo team không cần học pattern mới.

### 4.1 AL Dynamic Item Rule — bổ sung field

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `current_version` | Link → AL Dynamic Item Rule Version | Version đang Published |
| `requires_approval_for_new_version` | Check | Nếu bật → publish version mới phải qua Director duyệt (giống BOM Version) |

### 4.2 AL Dynamic Item Rule Version (Master — MỚI)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `rule` | Link → AL Dynamic Item Rule (reqd) | |
| `version_number` | Int (reqd) | Tăng dần |
| `status` | Select | Draft / Pending Approval / Published / Deprecated / Rejected — **y hệt vòng đời AL BOM Version §X.1 v17** |
| `rule_snapshot_json` | Long Text | Full JSON: rule_type, threshold_rows/lookup_rows, default_item tại thời điểm publish |
| `snapshot_hash` | Data | SHA-256, dùng cho `verify()` |
| `change_summary` | Small Text | Admin tự mô tả thay đổi |
| `is_rollback_of` | Link → AL Dynamic Item Rule Version | Nếu version này sinh ra từ rollback |
| `published_on` / `published_by` | Datetime / Link User | |

### 4.3 Thay đổi hành vi DynamicItemResolver

- `AL Profile Line.item_rule` **vẫn trỏ tới `AL Dynamic Item Rule`** (rule_code) như v18 — không đổi UX cho Kỹ thuật viên.
- Khi resolve tại runtime: DynamicItemResolver đọc **`rule.current_version.rule_snapshot_json`**, không đọc trực tiếp `threshold_rows`/`lookup_rows` live. Điều này đảm bảo:
  - Quotation đang mở/tính lại luôn dùng đúng version đã Published tại thời điểm đó.
  - `ConfigSnapshot` lưu thêm `rule_version_ids: {rule_code: version_name}` — mở rộng minh bạch đúng Nguyên tắc #12.

### 4.4 Luồng sửa Rule (song song với luồng sửa BOM đã quen thuộc)

| Bước | Actor | Hành động |
|---|---|---|
| 1 | Kỹ thuật viên | Sửa threshold_rows/lookup_rows trên `AL Dynamic Item Rule` (đang ở trạng thái làm việc, chưa publish) |
| 2 | Kỹ thuật viên | Nhấn "Publish Version" → hệ thống snapshot, tạo `AL Dynamic Item Rule Version` mới |
| 3 | System | Nếu `requires_approval_for_new_version=1` → Pending Approval → Director duyệt (dùng lại Approval Workflow §XI v17, chỉ thêm `approval_target_type=RULE_VERSION`) |
| 4 | Admin | Sau khi Published: chọn "Áp dụng cho BOM mới từ nay" (mặc định) hoặc **"Áp dụng hồi tố"** — nếu chọn hồi tố, hệ thống hiển thị **Diff Tool** (tái dùng `compare_versions()` §X.2 v17, áp cho Rule) liệt kê các BOM/Quotation đang mở sẽ bị ảnh hưởng, yêu cầu xác nhận rõ ràng trước khi áp dụng |
| 5 | System | Ghi `AL BOM Change Log`-tương-đương cho Rule (dùng chung DocType, thêm `change_target_type` field) |

### 4.5 Migration

- Patch tạo `AL Dynamic Item Rule Version` v1 (Published) cho **mọi Rule hiện có** trước khi bật tính năng mới — pattern giống hệt `create_initial_bom_versions.py` (v17 §28.2), đổi tên DocType.

---

## V. MODULE SẢN XUẤT (PRODUCTION & CUTTING)

### 5.1 Mục tiêu & phạm vi

Chính thức hóa và mở rộng "Phase 3" vốn chỉ có 2 DocType sơ khai trong v17. Mục tiêu kép:
1. **Chuyển đổi ConfigSnapshot → lệnh sản xuất thực tế** (cắt nhôm, cắt kính, gia công) — không tính lại giá, chỉ đọc kích thước đã snapshot.
2. **Tối ưu vật liệu** — đây là nơi AI/optimization có ROI cao nhất (§X.3).

### 5.2 Nguyên tắc thiết kế riêng cho Production

> **Nguyên tắc P-1:** Kích thước SẢN XUẤT (cắt thực tế) là một phép biến đổi từ kích thước TÍNH GIÁ (ConfigSnapshot), không phải một nguồn số liệu độc lập. Công thức "kích thước cắt = kích thước thiết kế − trừ hao gia công" phải được khai báo qua FormulaEngine (đúng Nguyên tắc #11), lưu trong `AL Cutting Standard`, **không hardcode trong Production module**.

> **Nguyên tắc P-2:** Kế hoạch cắt (Cutting Plan) là **đề xuất tối ưu**, không tự động trừ kho. Người phụ trách sản xuất luôn review trước khi Confirm — tương tự MRP Lite (Nguyên tắc: Aggregate, không tự động hành động).

### 5.3 AL Cutting Standard (Master)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `applies_to` | Select | NHOM_PROFILE / KINH |
| `item_group` hoặc `profile_code` | Link | Áp dụng cho nhóm item nào |
| `stock_bar_length_mm` (NHOM) | Float | Chiều dài phôi chuẩn, ví dụ 6000mm |
| `saw_kerf_mm` (NHOM) | Float | Độ hao do lưỡi cưa |
| `jumbo_sheet_size` (KINH) | Data | Kích thước tấm lớn chuẩn, vd "3210x2250" |
| `edge_trim_mm` (KINH) | Float | Trừ hao mép cắt |
| `min_offcut_reusable_mm` | Float | Ngưỡng phế liệu còn dùng lại được (để không tính là hao phí 100%) |

### 5.4 AL Aluminum Cutting Plan / Plan Line

Sinh từ pool SO đã chốt (giống MRP Lite nhưng ở mức chi tiết cắt, không phải mua hàng):

| Bước quy trình | Actor | Mô tả |
|---|---|---|
| 1 | Sản xuất | Chọn danh sách SO/Installation Order cần cắt → tạo `AL Aluminum Cutting Plan` |
| 2 | System | Đọc `ConfigSnapshot` từng dòng NHOM → danh sách đoạn cắt cần thiết (item_code, chiều dài, số lượng) |
| 3 | System (Optimization) | Chạy thuật toán cutting-stock (1D bin packing) → đề xuất cách cắt từ thanh phôi 6m, tối thiểu hóa phế liệu → ghi vào `AL Aluminum Cutting Plan Line` (mỗi dòng: mã phôi, danh sách đoạn cắt, % hao phí) |
| 4 | Sản xuất | Review, điều chỉnh thủ công nếu cần (ví dụ ưu tiên dùng offcut còn tồn kho) |
| 5 | Sản xuất | Confirm → in phiếu cắt cho xưởng; cập nhật `AL Glass Cut Order`/tương đương cho nhôm |
| 6 | System | Ghi nhận phế liệu (offcut) > `min_offcut_reusable_mm` vào kho phụ (Item Variant "phế liệu tái sử dụng") |

### 5.5 AL Glass Cutting Plan / AL Glass Cut Order (mở rộng Phase 3 v17)

Giữ nguyên schema `AL Glass Cut Order`/`AL Glass Cut Line` đã có trong v17, bổ sung:
- `AL Glass Cutting Plan` (Master) đứng trước Cut Order — vai trò tối ưu nesting trên tấm jumbo, tương tự Aluminum Cutting Plan nhưng bài toán 2D (thay vì 1D).
- Liên kết `Stock Entry` khi cắt xong → cập nhật tồn kho Item Variant theo đúng batch.

### 5.6 AL Production Order Bridge

Cầu nối sang ERPNext Manufacturing core (Work Order, BOM sản xuất) khi công ty cần track thời gian/công đoạn sản xuất chính thức trong ERPNext:

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `sales_order` | Link → Sales Order | |
| `work_order` | Link → Work Order (ERPNext core) | |
| `sync_status` | Select | Not Synced / Synced / Error |
| `production_stage` | Select | Cutting / Assembly / QC / Ready to Install |

> **Quyết định kiến trúc:** Không bắt buộc dùng ERPNext Work Order đầy đủ nếu công ty chưa cần theo dõi công đoạn chi tiết — `AL Aluminum/Glass Cutting Plan` đã đủ vận hành xưởng cắt vừa/nhỏ. Bridge này là **tùy chọn** cho công ty quy mô lớn cần tích hợp sâu MES/Work Order.

---

## VI. MODULE THI CÔNG (FIELD OPERATIONS / INSTALLATION)

### 6.1 AL Installation Team (Master)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `team_name` | Data | |
| `team_leader` | Link → Employee/User | |
| `members` | Table (Employee) | |
| `region` | Data | Khu vực phụ trách |
| `capacity_m2_per_day` | Float | Năng lực lắp đặt tham khảo (dùng cho lập lịch) |

### 6.2 AL Installation Order (Master) — Vòng đời

| Trạng thái | Mô tả | Chuyển sang |
|---|---|---|
| Draft | Tạo từ SO, chưa lên lịch | Scheduled |
| Scheduled | Đã gán đội thi công + ngày dự kiến | In Progress |
| In Progress | Đang thi công, có `AL Installation Progress` ghi nhận | Completed / On Hold |
| On Hold | Tạm dừng (chờ vật tư, thời tiết, tranh chấp) | In Progress |
| Completed | Nghiệm thu xong, 100% hạng mục | Warranty (chuyển giao bảo hành) |

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `sales_order` | Link → Sales Order (reqd) | |
| `project` | Link → Project (ERPNext core) | Khuyến nghị dùng Project core để tận dụng report sẵn có |
| `installation_team` | Link → AL Installation Team | |
| `planned_start` / `planned_end` | Date | |
| `al_installation_lines` | Table → AL Installation Order Line | |
| `overall_progress_pct` | Percent (read-only, tính từ Progress log) | |

### 6.3 AL Installation Order Line (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `sales_order_item` | Link → Sales Order Item | Liên kết ngược tới BOM/ConfigSnapshot gốc |
| `hang_muc` | Data | Tên hạng mục công trình (vd "Tầng 3 - Trục A-B") |
| `planned_nc_ld_cost` | Currency | Copy từ `AL Product Type.nc_ld_rate × diện tích` tại thời điểm chốt SO (immutable — không tính lại) |
| `status` | Select | Pending / Installing / Done / Rework |

### 6.4 AL Installation Progress (Master — nhật ký, append-only)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `installation_order` | Link | |
| `progress_date` | Date | |
| `pct_completed_this_entry` | Float | % hoàn thành ghi nhận trong lần cập nhật này |
| `cumulative_pct` | Float (computed) | Tổng % lũy kế |
| `photos` | Table (Attach Image) | Ảnh nghiệm thu — **input cho AI phân tích ảnh §X.4** |
| `notes` | Small Text | |
| `recorded_by` | Link User | Thường là team leader qua mobile app |

> **Thiết kế append-only** (giống ConfigSnapshot): mỗi lần cập nhật tiến độ là 1 record mới, không sửa record cũ — đảm bảo audit trail tiến độ thật, tránh tranh chấp "đã báo hoàn thành bao nhiêu % vào ngày nào" với khách hàng/nhà thầu phụ.

### 6.5 AL Installation Cost Actual

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `installation_order` | Link | |
| `cost_type` | Select | Nhân công / Vận chuyển / Thiết bị / Khác |
| `actual_amount` | Currency | |
| `source_doc` | Dynamic Link (Expense Claim / Journal Entry / Purchase Invoice) | |

→ Feed trực tiếp vào **AL Labor Cost Variance** (§VIII) và **Project Profitability** (§VIII).

### 6.6 AL Warranty Policy & AL Warranty Claim

| DocType | Field chính | Mục đích |
|---|---|---|
| `AL Warranty Policy` | `product_type`, `warranty_months`, `coverage_scope` | Chính sách theo `AL Product Type` |
| `AL Warranty Claim` | `sales_order`, `installation_order`, `issue_description`, `repair_cost`, `root_cause_category` | Ghi nhận lỗi + chi phí sửa — `root_cause_category` dùng cho AI Anomaly Detection §X.4 phát hiện lỗi lặp lại theo BOM/nhà cung cấp/đội thi công |

---

## VII. MODULE THANH QUYẾT TOÁN (MILESTONE BILLING)

### 7.1 Nguyên tắc thiết kế

> **Nguyên tắc S-1:** Không phát minh cơ chế thanh toán mới — tận dụng `Payment Schedule` sẵn có của ERPNext Sales Order/Invoice (milestone payment terms đã là tính năng core). Module này chỉ thêm **lớp kiểm soát**: không cho phép xuất hóa đơn đợt tiếp theo vượt quá % nghiệm thu thực tế.

### 7.2 AL Milestone Billing Plan (Master)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `sales_order` | Link → Sales Order (reqd) | |
| `total_contract_value` | Currency | |
| `al_milestone_lines` | Table → AL Milestone Billing Line | |
| `retention_pct` | Percent | % giữ lại bảo hành (thường 5-10%) |
| `retention_release_condition` | Small Text | Điều kiện giải phóng tiền giữ lại |

### 7.3 AL Milestone Billing Line (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `milestone_name` | Data | "Tạm ứng 30%", "Hoàn thành 70% khối lượng", "Nghiệm thu bàn giao" |
| `billing_pct` | Percent | % giá trị hợp đồng của đợt này |
| `trigger_type` | Select | MANUAL / INSTALLATION_PROGRESS_PCT / DATE |
| `trigger_value` | Data | Nếu `INSTALLATION_PROGRESS_PCT`: ngưỡng % (vd "70") liên kết `overall_progress_pct` của Installation Order |
| `status` | Select | Not Ready / Ready to Bill / Invoiced / Paid |
| `sales_invoice` | Link → Sales Invoice | Gán sau khi xuất hóa đơn đợt này |

### 7.4 Luồng kiểm soát billing theo tiến độ

| Bước | Actor | Hành động |
|---|---|---|
| 1 | System (Hook trên `AL Installation Progress` sau khi save) | Kiểm tra `cumulative_pct` của Installation Order vs `trigger_value` các Milestone Line còn `Not Ready` |
| 2 | System | Nếu đạt ngưỡng → chuyển status → `Ready to Bill`, notify Kế toán |
| 3 | Kế toán | Xuất Sales Invoice cho đúng `billing_pct` giá trị hợp đồng |
| 4 | System | Validate: **chặn xuất hóa đơn nếu tổng % đã invoice > tổng % tiến độ đã nghiệm thu** (trừ đợt tạm ứng đầu ban đầu — trigger_type=MANUAL/DATE không bị chặn) |
| 5 | Kế toán | Cuối dự án: xuất hóa đơn giữ lại bảo hành theo `retention_release_condition` (thường sau khi hết hạn `AL Warranty Policy` hoặc theo điều khoản hợp đồng) |

---

## VIII. MODULE KẾ TOÁN LÃI LỖ THEO CÔNG TRÌNH (PROJECT PROFITABILITY)

Đây là module tôi đánh giá **giá trị kinh doanh cao nhất còn thiếu** trong toàn bộ thiết kế trước đó — trả lời câu hỏi "công ty có đang lãi thật không".

### 8.1 AL Project Financial Config (Master)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `project` | Link → Project | |
| `overhead_allocation_method` | Select | NONE / PCT_OF_REVENUE / FIXED_AMOUNT |
| `overhead_allocation_value` | Float | |

### 8.2 AL Labor Cost Variance (Master)

So sánh dự toán vs thực tế cho nhân công — mở rộng khái niệm Cost Variance (v17 chỉ có vật tư) sang nhân công/thi công:

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `installation_order` | Link | |
| `planned_cost` | Currency | Từ `AL Installation Order Line.planned_nc_ld_cost` (immutable, chốt tại thời điểm SO) |
| `actual_cost` | Currency | Tổng từ `AL Installation Cost Actual` |
| `variance_pct` | Float (computed) | |
| `variance_status` | Select | NORMAL / CAUTION / ALERT — **dùng chung ngưỡng 5%/15% như Cost Variance vật tư (v17 §14.3) để nhất quán báo cáo** |

### 8.3 AL Project Profitability Snapshot (Master — immutable, giống ConfigSnapshot)

Đây là "ConfigSnapshot của tầng tài chính" — tổng hợp định kỳ hoặc theo trigger (khi có SI mới / PI mới / Installation Cost mới), **không tính lại các con số đã snapshot trước đó**:

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `project` / `sales_order` | Link | |
| `snapshot_date` | Datetime | |
| `revenue_recognized` | Currency | Tổng Sales Invoice đã submit liên quan |
| `material_cost_quoted` | Currency | Từ ConfigSnapshot gốc (GIA_THANH tại thời điểm báo giá) |
| `material_cost_actual` | Currency | Từ Purchase Invoice thực tế (đối chiếu Cost Variance §XIV v17) |
| `labor_install_cost_actual` | Currency | Từ `AL Installation Cost Actual` |
| `warranty_cost_to_date` | Currency | Từ `AL Warranty Claim.repair_cost` |
| `overhead_allocated` | Currency | Theo `AL Project Financial Config` |
| `gross_profit` | Currency (computed) | `revenue_recognized − material_cost_actual − labor_install_cost_actual − warranty_cost_to_date − overhead_allocated` |
| `gross_margin_pct` | Float (computed) | |
| `margin_drift_vs_quoted` | Float (computed) | So với margin đã báo giá ban đầu (từ ConfigSnapshot `GIA_BAN` vs `GIA_THANH`) — **đây là con số quan trọng nhất cho Ban Giám đốc** |

### 8.4 Luồng tạo Snapshot

| Trigger | Tần suất |
|---|---|
| Scheduled job hàng tuần cho mọi Project đang mở | Tự động |
| Thủ công bất kỳ lúc nào (Admin/Kế toán nhấn "Recalculate Snapshot") | On-demand |
| Tự động khi Sales Invoice / Purchase Invoice / Installation Cost Actual mới được submit | Event-driven (hook) |

### 8.5 Báo cáo mới

| Report | Nguồn | Vai trò |
|---|---|---|
| AL Project Profitability Dashboard | AL Project Profitability Snapshot | Director, Admin, Kế toán |
| AL Margin Drift Alert | `margin_drift_vs_quoted` < ngưỡng cấu hình | Director (realtime alert — tái dùng NotificationEngine v17, thêm `alert_type=MARGIN_DRIFT`) |

---

## IX. QUY TRÌNH NGHIỆP VỤ ĐẦU-CUỐI (LEAD → QUYẾT TOÁN → ĐÓNG SỔ)

```
[1] LEAD / CƠ HỘI
     → (tùy chọn CRM ERPNext hoặc nhập tay)

[2] BÁO GIÁ (Quotation)
     → BomOrchestrator 7 bước (v18) + Hook A-D (v17) chạy như cũ
     → ConfigSnapshot + AL BOM Version + AL Dynamic Item Rule Version (★ mới §IV) đều được ghim
     → Discount Stack + Approval nếu cần

[3] CHỐT ĐƠN (SO)
     → Copy al_* fields (không đổi, QĐ-7 v15)
     → ★ MỚI: Tạo AL Milestone Billing Plan (mặc định theo template hợp đồng)
     → ★ MỚI: Tạo AL Installation Order Line (dự thảo, planned_nc_ld_cost chốt từ Quotation)

[4] MUA VẬT TƯ
     → AL Material Plan (không đổi v17) → PO → PI
     → Cost Variance vật tư tự tạo (không đổi v17)

[5] ★ MỚI — SẢN XUẤT
     → AL Aluminum/Glass Cutting Plan đọc ConfigSnapshot → tối ưu cắt → AL Glass/Aluminum Cut Order
     → (tùy chọn) AL Production Order Bridge đồng bộ ERPNext Work Order

[6] ★ MỚI — THI CÔNG
     → AL Installation Order chuyển Scheduled → In Progress
     → AL Installation Progress ghi nhận định kỳ (mobile) → overall_progress_pct cập nhật
     → AL Installation Cost Actual ghi nhận song song

[7] ★ MỚI — THANH TOÁN THEO TIẾN ĐỘ
     → Milestone Billing Line tự chuyển Ready to Bill khi đạt ngưỡng tiến độ
     → Kế toán xuất Sales Invoice từng đợt

[8] NGHIỆM THU & BẢO HÀNH
     → Installation Order → Completed
     → AL Warranty Policy kích hoạt; AL Warranty Claim ghi nhận nếu có lỗi phát sinh

[9] ★ MỚI — QUYẾT TOÁN & KẾ TOÁN LÃI LỖ
     → AL Project Profitability Snapshot tổng hợp toàn bộ (vật tư thực + nhân công thực + bảo hành + overhead)
     → margin_drift_vs_quoted đối chiếu với cam kết ban đầu lúc báo giá
     → Đóng Project trong ERPNext, snapshot cuối cùng lưu vĩnh viễn cho audit
```

---

## X. TẦNG AI TOÀN DIỆN

### 10.1 Nguyên tắc quản trị (áp dụng cho mọi use case dưới đây)

Theo Nguyên tắc #21: **AI không bao giờ tự ghi vào bất kỳ DocType immutable nào** (ConfigSnapshot, BOM Version, Rule Version, Project Profitability Snapshot). Mọi output AI đi qua `AL AI Suggestion Log` trước, sau đó **con người xác nhận** qua đúng cơ chế Approval Workflow đã có — không xây "AI approval flow" riêng.

### 10.2 AL AI Suggestion Log (Master)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `suggestion_type` | Select | ITEM_RULE_GENERATE / QUOTATION_DRAFT / DISCOUNT_SUGGEST / CUTTING_OPTIMIZATION / PROJECT_RISK_FLAG / PK_SUGGEST / ANOMALY_DETECT |
| `context_reference` | Dynamic Link | Quotation / AL BOM / AL Installation Order / AL Project Profitability Snapshot liên quan |
| `ai_output_json` | Long Text | Đề xuất thô từ AI |
| `confidence_score` | Float | |
| `status` | Select | Proposed / Accepted / Modified / Rejected |
| `reviewed_by` | Link User | |
| `feedback_note` | Small Text | Dùng cho huấn luyện lại (RLHF-style) |

### 10.3 Use case theo module (sắp theo ROI thực tế, không theo độ dễ)

| Ưu tiên | Use case | Module liên quan | Input | Output → đi qua |
|---|---|---|---|---|
| **P0 (ROI vật chất cao nhất)** | **AI Cutting Optimization** | Sản xuất (§V) | ConfigSnapshot (danh sách đoạn cần cắt) + AL Cutting Standard | `AL Aluminum/Glass Cutting Plan` — Admin sản xuất review & confirm, không tự động |
| **P0** | **AI Project Health Score** | P&L (§VIII) | AL Project Profitability Snapshot + AL Labor/Cost Variance + số lần rework | Cảnh báo Director qua NotificationEngine — không tự hành động |
| **P1** | AI-assisted BOM/Rule Configuration (v18 đã thiết kế) | BOM/Dynamic Item Rule | Mô tả tự nhiên + available_items | `AL Dynamic Item Rule` **Draft version** (không Published) — Kỹ thuật viên review rồi mới Publish (§IV) |
| **P1** | AI Quotation Copilot | Sales | Mô tả yêu cầu khách + BOM library (RAG) | Quotation **Draft** — Sales bắt buộc review trước Submit |
| **P1** | AI Win/Loss Analysis | Sales Analytics | Quotation Won/Lost + `quotation_loss_reason` (★ field mới cần bổ sung vào Quotation) | Báo cáo — không hành động tự động |
| **P2** | AI Anomaly Detection mở rộng | Cost Variance + Labor Cost Variance + Warranty Claim | Toàn bộ variance/warranty data | Flag trong Dashboard — Admin/Kế toán review |
| **P2** | AI phân tích ảnh nghiệm thu | Field Ops (§VI) | `AL Installation Progress.photos` | Gợi ý lỗi lắp đặt phổ biến — không tự tạo Warranty Claim, chỉ đề xuất |
| **P3** | AI Demand Forecasting | MRP Lite | Lịch sử PI + Material Plan | Gợi ý `qty_to_purchase` trong Material Plan — Admin vẫn Confirm |

### 10.4 Điều kiện tiên quyết còn thiếu (bổ sung so với v18)

- `Quotation.al_loss_reason` (Select: Giá cao / Chậm tiến độ / Đối thủ / Khách đổi ý / Khác) — **cần thêm field này trước khi làm AI Win/Loss**, hiện không tồn tại ở đâu trong 59 DocType.
- Dữ liệu Cutting Standard + tối thiểu 3-6 tháng lịch sử Cutting Plan trước khi AI Cutting Optimization có đủ tín hiệu để học pattern tối ưu theo đặc thù xưởng thực tế (khác với optimization thuần lý thuyết).

---

## XI. BOMORCHESTRATOR v19 — CẬP NHẬT HOOK

BomOrchestrator **không đổi 7 bước core** (v18). Chỉ bổ sung 2 hook mới trong Tầng 6, chạy **sau khi SO được Submit** (không phải sau khi tính giá Quotation — khác với Hook A-D chạy ngay lúc tính giá):

| Hook | Trigger | Module | Hành động |
|---|---|---|---|
| **Hook E** | `Sales Order.on_submit` | Field Ops | Tạo `AL Installation Order` (Draft) + `AL Milestone Billing Plan` (từ template mặc định theo `AL Product Type`/hợp đồng) |
| **Hook F** | `Sales Order.on_submit` | Production | Đăng ký reference cho `AL Aluminum/Glass Cutting Plan` pool (chưa tạo plan ngay — chờ gom nhiều SO để tối ưu cắt theo lô) |

> Đúng Nguyên tắc #13: BomOrchestrator không import Tầng 6 — các module tự đăng ký hook vào `Sales Order.on_submit` qua `hooks.py`, không sửa code lõi.

---

## XII. CONFIGSNAPSHOT & AUDIT TRAIL — MỞ RỘNG TỚI QUYẾT TOÁN

Chuỗi minh bạch giờ kéo dài xuyên suốt: mỗi record ở tầng dưới **tham chiếu ngược** record đã snapshot ở tầng trên, không tính toán lại:

```
ConfigSnapshot (giá bán)
   ↓ tham chiếu
AL BOM Version + AL Dynamic Item Rule Version (★ mới — item đã chọn)
   ↓ tham chiếu
AL Aluminum/Glass Cutting Plan (kích thước cắt — biến đổi từ ConfigSnapshot qua AL Cutting Standard)
   ↓ tham chiếu
AL Installation Order Line (planned_nc_ld_cost chốt cứng)
   ↓ đối chiếu với
AL Installation Cost Actual + AL Cost Variance (vật tư) + AL Labor Cost Variance
   ↓ tổng hợp vào
AL Project Profitability Snapshot (immutable, định kỳ)
```

`explain()` của FormulaEngine (Tầng 3) vẫn chỉ trả lời **"tại sao giá bán ra con số này"**. Với câu hỏi **"tại sao dự án này lãi/lỗ"**, cần một hàm mới ở Tầng 6E:

```
AL Project Profitability Snapshot.explain_variance()
  → Trả về breakdown: bao nhiêu % lệch margin đến từ vật tư, bao nhiêu từ nhân công,
    bao nhiêu từ bảo hành — dùng chung triết lý "cây giải thích" như explain() của FormulaEngine,
    nhưng vận hành ở tầng nghiệp vụ, không phải tầng công thức.
```

---

## XIII. PHÂN QUYỀN & VAI TRÒ (MỞ RỘNG)

| Vai trò mới | DocType được phép | Hành động đặc biệt |
|---|---|---|
| **AluGlass Sản Xuất** | AL Cutting Standard (read), AL Aluminum/Glass Cutting Plan (tạo/sửa), AL Production Order Bridge | Confirm Cutting Plan; không sửa ConfigSnapshot nguồn |
| **AluGlass Đội Thi Công** (thường qua mobile) | AL Installation Order (read hạng mục được giao), AL Installation Progress (tạo) | Chỉ ghi nhận tiến độ + ảnh; không sửa giá/BOM |
| **AluGlass Quản lý Thi công** | AL Installation Order (đầy đủ), AL Installation Team, AL Warranty Claim | Gán đội, duyệt hoàn thành, xử lý bảo hành |
| **AluGlass Director** *(mở rộng vai trò v17 đã có)* | + AL Project Profitability Snapshot (read), AL Milestone Billing Plan (approve), AL Dynamic Item Rule Version (approve nếu `requires_approval`) | Nhận `MARGIN_DRIFT` alert |

> **Nguyên tắc mới:** Đội Thi Công (thường không phải nhân viên văn phòng, dùng mobile) chỉ có quyền **ghi thêm** (`AL Installation Progress`), không có quyền sửa bất kỳ record nào đã tạo trước đó — nhất quán với thiết kế append-only §6.4.

---

## XIV. LỘ TRÌNH TRIỂN KHAI TỔNG THỂ (PHASE 1–7)

| Phase | Nội dung | Điều kiện hoàn thành |
|---|---|---|
| **Phase 1** | Core Engine (v16-v18, đã có đặc tả đầy đủ) | 8 ví dụ kiểm chứng PASS; Không eval() |
| **Phase 2** | Module Commercial (v17: Version/Approval/Discount/Reporting/MRP/CostVariance/Notification/Analytics) | Như lộ trình v17 §XXII |
| **Phase 2.5 ★ MỚI (chèn trước Phase 3, KHÔNG sau)** | **Vá gap P0: AL Dynamic Item Rule Versioning (§IV)** | Migration tạo version v1 cho mọi rule hiện có; `explain()` hiển thị đúng rule_version_id |
| **Phase 3** | Module Sản Xuất (§V) — Cutting Standard, Cutting Plan (1D + 2D optimization), Cut Order | Cutting Plan giảm phế liệu đo được so với cắt thủ công (baseline) |
| **Phase 4** | Module Thi Công + Thanh Quyết Toán (§VI, §VII) | Installation Progress mobile hoạt động; Milestone Billing chặn đúng invoice vượt tiến độ |
| **Phase 5** | Module Kế Toán Lãi Lỗ (§VIII) | Project Profitability Snapshot chạy được cho ≥3 dự án thí điểm, đối chiếu thủ công khớp |
| **Phase 6** | AI Layer P0-P1 (§X): Cutting Optimization AI, Project Health Score, BOM/Rule AI-assist, Quotation Copilot | AI suggestion qua đúng Approval Workflow, có `AL AI Suggestion Log` đầy đủ |
| **Phase 7** | AI Layer P2-P3 + Optimization hiệu năng (cache, Redis, nén ConfigSnapshot JSON — nợ kỹ thuật từ v17 §3.6 REVIEW) | Theo nhu cầu thực tế sau khi có đủ dữ liệu lịch sử |

> **Thay đổi quan trọng so với lộ trình v17/v18 gốc:** Phase 2.5 (vá Rule Versioning) được chèn **trước** Phase 3, không phải để "sau này" — vì Phase 6 (AI sinh Rule) sẽ khuếch đại rủi ro version-drift nếu Phase 2.5 chưa xong.

---

## XV. RỦI RO & ĐIỂM THEO DÕI (HỢP NHẤT)

Kế thừa toàn bộ Risk Matrix v17 §XXIII + v18 §12.1 (không lặp lại ở đây — xem file gốc). Bổ sung rủi ro riêng cho phạm vi v19:

| # | Rủi ro | Mức độ | Xử lý |
|---|---|---|---|
| R-P1 | Cutting Optimization đề xuất phương án không khả thi thực tế (máy cắt không hỗ trợ góc/độ dài đó) | TB | AI/optimization luôn qua review của Sản xuất trước khi in phiếu cắt; không tự động hóa hoàn toàn ở Phase 3 |
| R-P2 | Installation Progress ghi nhận sai % do đội thi công vội báo cáo | TB | Ảnh bắt buộc kèm mỗi lần cập nhật ≥50%; Quản lý Thi công review định kỳ |
| R-P3 | Milestone Billing chặn nhầm hóa đơn hợp lệ (vd tạm ứng đầu dự án chưa có tiến độ) | Cao nếu sai | `trigger_type=MANUAL/DATE` không bị chặn bởi tiến độ — chỉ `INSTALLATION_PROGRESS_PCT` mới áp dụng validation |
| R-P4 | Project Profitability Snapshot sai do Overhead Allocation cấu hình nhầm | TB | Snapshot luôn giữ `overhead_allocated` tách riêng dòng, dễ audit/điều chỉnh mà không ảnh hưởng revenue/material đã chốt |
| R-P5 | AI Suggestion Log phình to, không ai review | Thấp | Dashboard riêng "AI Suggestions chờ review", auto-archive sau 30 ngày không phản hồi |

---

## XVI. CHECKLIST GO-LIVE

- [ ] 8 ví dụ kiểm chứng v17 + ví dụ A-G PASS 100%
- [ ] **Migration Rule Versioning hoàn tất, mọi Rule có current_version** (điều kiện go-live v18, không được bỏ qua)
- [ ] Test migration định lượng: so sánh output VariableResolver v2 vs v3 trên ≥100 Quotation thật (không chỉ 8 ví dụ tổng hợp)
- [ ] Cutting Standard khai báo đầy đủ cho toàn bộ profile nhôm + loại kính đang dùng
- [ ] Milestone Billing Plan template mặc định đã duyệt với Kế toán trưởng trước khi áp dụng SO thật
- [ ] Project Profitability Snapshot chạy thí điểm ≥3 dự án đã hoàn thành, đối chiếu khớp với báo cáo thủ công hiện tại của Kế toán
- [ ] Toàn bộ AI use case Phase 6 đã có `AL AI Suggestion Log` + đi qua Approval Workflow — không có đường tắt AI ghi trực tiếp
- [ ] Phân quyền Đội Thi Công (mobile, append-only) đã test không cho sửa/xóa record cũ
