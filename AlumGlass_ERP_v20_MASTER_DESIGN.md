# AlumGlass ERP v20 — MASTER DESIGN (Tài liệu triển khai chính thức, hợp nhất)

> **App:** `aluglass` (Frappe custom app trên ERPNext + HRMS core) + `formula_builder` (engine công thức dùng chung)
> **Phiên bản:** v20.0 — hợp nhất v17 FINAL + v17 REVIEW + v18 Upgrade Spec + v19 MASTER, **vá 1 lỗi kiến trúc nghiêm trọng (tồn kho theo màu)**, bổ sung **Chiến lược AI-First toàn dự án**
> **Vai trò tài liệu:** Đây là **bản duy nhất, chính thức** dùng để triển khai thực tế. Các file v17/v18/v19 trước đó chuyển sang trạng thái *lưu trữ tham khảo lịch sử thiết kế* — không dùng để code hóa nữa.
> **Phạm vi nghiệp vụ:** Lead → Báo giá (tính giá động) → Chốt đơn → Mua vật tư → Sản xuất (cắt) → Thi công → Thanh quyết toán → Kế toán lãi lỗ theo công trình → AI xuyên suốt toàn bộ vòng đời.

> *"Khai báo theo thứ tự tư duy nghề, tính theo thứ tự DAG, mở rộng theo module không phá lõi, tồn kho theo thực tế vật lý không theo lý thuyết biến thể, minh bạch từ báo giá tới quyết toán, và AI luôn đề xuất chứ không quyết định."*

---

## MỤC LỤC

0. Tóm tắt đánh giá của Kiến trúc sư trưởng (Senior Review Summary)
I. Nguyên tắc thiết kế hợp nhất (23 nguyên tắc, v11 → v20)
II. Kiến trúc tổng thể — 8 tầng + 1 tầng AI xuyên suốt
III. Danh mục DocType tổng hợp (59 → 63, có sửa/xóa)
IV. ★ SỬA LỖI KIẾN TRÚC P0: Tồn kho Nhôm/Vật tư KHÔNG theo biến thể màu
V. Dynamic Item Rule — Versioning (giữ nguyên từ v19)
VI. Formula Engine, ProfileInterpreter, DAG, 3 chế độ chọn Item (dẫn chiếu v17/v18, không lặp)
VII. Module Sản Xuất (Production & Cutting) — cập nhật theo §IV
VIII. Module Thi Công (Field Operations / Installation)
IX. Module Thanh Quyết Toán (Milestone Billing)
X. Module Kế Toán Lãi Lỗ theo Công trình (Project Profitability)
XI. Quy trình nghiệp vụ đầu-cuối (Lead → Quyết toán → Đóng sổ)
XII. ★ CHIẾN LƯỢC AI-FIRST TOÀN DỰ ÁN (mở rộng lớn so với v19)
XIII. BomOrchestrator v20 — Tổng hợp toàn bộ hook
XIV. ConfigSnapshot & Audit Trail — chuỗi minh bạch đầy đủ
XV. Phân quyền & Vai trò
XVI. Lộ trình triển khai tổng thể (Phase 0–8)
XVII. Rủi ro & Điểm theo dõi (hợp nhất, đã cập nhật theo §IV)
XVIII. Checklist Go-live

---

## 0. TÓM TẮT ĐÁNH GIÁ CỦA KIẾN TRÚC SƯ TRƯỞNG

Đã đọc kỹ 5 tài liệu nguồn (v17 FINAL, v17 REVIEW, v18 Upgrade Spec, v19 MASTER DESIGN, v19 MASTER FULL). Đánh giá tổng thể: **đây là một trong những thiết kế ERP ngành nhôm kính trên Frappe/ERPNext chín muồi nhất tôi từng review** — triết lý "engine lõi bất biến, mở rộng qua module/hook", Formula Engine làm nguồn sự thật duy nhất, ConfigSnapshot bất biến, versioning cho BOM và Rule, đều là các quyết định kiến trúc đúng đắn và đã được kiểm chứng qua nhiều vòng lặp (v11 → v19). Không đề xuất viết lại — chỉ vá và mở rộng.

**Điểm mạnh giữ nguyên 100%:**
- Zero Python trong DB, Formula Engine là engine tính toán duy nhất.
- Tách biệt kích thước TÍNH GIÁ (ConfigSnapshot) khỏi kích thước SẢN XUẤT (Cutting Standard) — đúng bản chất nghiệp vụ nhôm kính (kích thước báo giá là kích thước hoàn thiện/thông thủy, kích thước cắt phải trừ hao gia công, roong, gioăng).
- Milestone Billing tận dụng Payment Schedule core thay vì phát minh lại — đúng tinh thần "không phá lõi ERPNext".
- Nguyên tắc AI chỉ đề xuất (#21) — bắt buộc với ngành có giá trị hợp đồng lớn, sai số giá là rủi ro tài chính thật.

**Lỗi kiến trúc nghiêm trọng duy nhất phát hiện (P0 — phải sửa trước Phase 3):**
Tài liệu nguồn tự mâu thuẫn với chính nguyên tắc của nó. QĐ-6 (v15) tuyên bố đúng: *"Màu nhôm là biến định giá (Rule LOOKUP), không phải Item Variant"* — nhưng đến Phase 3 (AL Glass/Aluminum Inventory Bridge, cả ở v17 §XVII, v19 §V.5, v19 FULL §XVII), thiết kế lại quay về dùng **Item Variant tồn kho theo màu nhôm**, đúng như v17 tự flag ở Risk R21/R11: *"Tồn kho theo màu nhôm (Item Variant) — Cao khi Phase 3"* nhưng chưa từng thiết kế giải pháp thay thế, chỉ ghi chú "viết ánh xạ riêng" mà không nói ánh xạ đó là gì.

Đây chính xác là vấn đề bạn nêu: **màu nhôm là thuộc tính theo dự án cụ thể (project-specific), không phải thuộc tính cố định của item.** Một hệ Item Variant chuẩn ERPNext (Item Template × Attribute "Màu") sẽ nhân bản: mỗi profile nhôm (thường 150-300 mã tiết diện) × mỗi màu thực tế công ty từng làm (hàng trăm mã RAL/vân gỗ, vì khách có thể yêu cầu màu bất kỳ) = **hàng chục nghìn Item ảo**, phần lớn chỉ dùng 1 lần cho 1 dự án rồi không bao giờ dùng lại — phá vỡ mọi báo cáo tồn kho, MRP, và định giá bình quân gia quyền (Item Variant vô nghĩa về mặt vòng quay vốn).

**Giải pháp trong tài liệu này:** §IV thiết kế lại hoàn toàn tầng tồn kho nhôm/vật tư theo mô hình **"Item = tiết diện vật lý, Màu = thuộc tính giao dịch (Batch + Project), không phải trục biến thể của Item Master"**. Đây là thay đổi kiến trúc quan trọng nhất của v20.

**Yêu cầu thứ hai — AI-First toàn dự án:** v18/v19 đã có tầng AI (Tầng 7) nhưng dừng ở mức "danh sách use case theo module". v20 nâng cấp thành **chiến lược AI-First xuyên suốt vòng đời** (§XII) — không chỉ AI sinh Rule/BOM, mà AI hỗ trợ từ đọc bản vẽ kiến trúc ra BOM nháp, tư vấn bán hàng, dự báo giá vật tư, đến trợ lý nội bộ tra cứu toàn bộ tri thức công ty — với governance nhất quán tuyệt đối: **AI luôn là "người đề xuất cấp dưới", không bao giờ là "người ký duyệt"**.

Mọi phần khác của v19 (Sản xuất, Thi công, Thanh quyết toán, P&L, Rule Versioning, kiến trúc 8 tầng) được **giữ nguyên và mang vào v20**, chỉ cập nhật những điểm chạm tới tồn kho màu (đánh dấu ★§IV).

---

## I. NGUYÊN TẮC THIẾT KẾ HỢP NHẤT (23 NGUYÊN TẮC)

| # | Nguyên tắc | Nguồn | Ghi chú v20 |
|---|---|---|---|
| 1 | Zero Python trong DB | v11 | Không đổi |
| 2 | Chọn Item trực tiếp (+ Dynamic từ v18) | v11/v18 | Không đổi |
| 3 | `show_condition` thay `if/elif` | v11 | Không đổi |
| 4 | Tách vật liệu, thống nhất bảng `al_lines` | v16 | Không đổi |
| 5 | DAG là nguồn sự thật về thứ tự tính | v16 | Không đổi |
| 6 | Kính đa tấm là tập hợp panel động | v14 | Không đổi |
| 7 | Giá kính tách khỏi kích thước sản xuất | v14/v19 | Không đổi |
| 8 | Phụ kiện: mặc định + thay thế | v14 | Không đổi |
| 9 | Phụ thuộc chéo qua context phẳng | v16 | Không đổi |
| 10 | Rule là thư viện dùng chung | v11 | Không đổi |
| 11 | Formula Engine là lõi DUY NHẤT | v14/v18 | Không đổi |
| 12 | Minh bạch tuyệt đối (ConfigSnapshot + explain()) | v15/v19 | Mở rộng tới Rule Version, Production, Installation, Settlement, P&L |
| 13 | Module độc lập, hook không phá lõi | v17/v19 | Áp dụng cho toàn bộ module (kể cả AI Layer) |
| 14 | BOM Version = immutable snapshot | v17 | Không đổi |
| 15 | Approval trước khi hiệu lực | v17 | Không đổi |
| 16 | DynamicItemResolver dùng FormulaEngine.evaluate_single() | v18 | Không đổi |
| 17 | Formula Variable Binding thay AL Variable Binding | v18 | Không đổi |
| 18 | AL Calculation Rule — tinh gọn, không xóa | v18 | Không đổi |
| 19 | Cost Template + Formula Set — optional | v18 | Không đổi |
| 20 | AL Dynamic Item Rule = immutable versioned | v19 | Không đổi — xem §V |
| 21 | AI luôn đề xuất, không tự ghi vào snapshot/version | v19 | **v20: mở rộng thành chiến lược đầy đủ §XII, vẫn cùng 1 nguyên tắc bất biến** |
| **22 ★** | **Màu (nhôm/phụ kiện) là thuộc tính GIAO DỊCH (Batch + Project), KHÔNG BAO GIỜ là trục biến thể (Attribute) của Item Master** | **v20 MỚI (P0 — sửa lỗi)** | Xem §IV — nguyên tắc quan trọng thứ 2 sau #11 |
| **23 ★** | **Mọi dữ liệu vận hành phải sinh ra ở dạng "sạch cho AI học" (structured, có nhãn kết quả đúng/sai)** | **v20 MỚI** | Feedback loop bắt buộc cho `AL AI Suggestion Log` — không có dữ liệu sạch thì AI-First chỉ là khẩu hiệu |

---

## II. KIẾN TRÚC TỔNG THỂ — 8 TẦNG + 1 TẦNG AI XUYÊN SUỐT

Giữ nguyên quyết định kiến trúc quan trọng nhất từ v19: **không thêm tầng lõi mới cho nghiệp vụ, mọi mở rộng (Sản xuất, Thi công, Thanh quyết toán, P&L, Tồn kho màu) đều là module ở Tầng 6, đăng ký qua hook.** v20 chỉ đổi cách vẽ Tầng 7 — từ "danh sách use case" thành "dải AI chạy dọc toàn bộ chồng tầng", vì AI-First đúng nghĩa không phải là 1 tầng đứng trên cùng mà là năng lực chạm vào mọi tầng bên dưới nó (đọc dữ liệu Tầng 1, đề xuất vào Tầng 2/6, không bao giờ ghi trực tiếp vào Tầng 3/4).

```
┌─────────────────────────────────────────────────────────────────────┐
│ TẦNG 7 — AI LAYER (chạy dọc, đọc mọi tầng bên dưới, chỉ ghi qua      │
│ AL AI Suggestion Log → Approval Workflow — KHÔNG BAO GIỜ ghi thẳng) │
│  Sales/Quotation · Rule/BOM Authoring · Purchasing/MRP · Production  │
│  Cutting Optimization · Field Ops · Billing/P&L · Nội bộ (RAG)      │
│  → chi tiết đầy đủ §XII                                             │
└─────────────────────────────────────────────────────────────────────┘
TẦNG 6 — MODULE LAYER (Hook-based, không phá lõi)
  6A. Commercial  (v17): BOM Version · Approval · Discount Stack · Notification · Sales Analytics
  6B. Supply      (v17, ★ cập nhật §IV): MRP Lite (theo Item gốc + Batch màu) · Cost Variance
  6C. Production  (v19, ★ cập nhật §IV): Cutting Optimization · Manufacturing Bridge
  6D. Field Ops   (v19): Installation Order/Progress · Warranty Tracking
  6E. Financial   (v19): Milestone Billing · Project Profitability (P&L) · Labor/Install Cost Variance
  6F. Inventory ★MỚI v20: Batch-Color Manager · Project Warehouse Manager (§IV)

TẦNG 5 — PRESENTATION
  BOM Dialog · Glass Selector · PK Panel · Version Badge · Approval Inbox · Discount Selector
  Production Board (Kanban cắt) · Installation Mobile Checklist · Project P&L Dashboard
  ★MỚI v20: Color/Batch Picker trong PO/Material Request · AI Copilot Panel (mọi màn hình)

TẦNG 4.5 — DYNAMIC ITEM RESOLVER (v18, giữ cấu trúc — chỉ vá versioning §V)
  Fixed / Rule (có version) / Formula — Pre-Resolution Phase

TẦNG 4 — ORCHESTRATION
  VariableResolver v3 · ProfileInterpreter v2 · PkResolver · CostAccumulator v2
  BomOrchestrator — 7 bước lõi + hook mở rộng (§XIII)

TẦNG 3 — FORMULA ENGINE (formula_builder) — KHÔNG SỬA, giữ nguyên tuyệt đối

TẦNG 2 — RULE ENGINE & VARIABLE BINDING
  AL Calculation Rule (LOOKUP giá theo màu — TRA-GIA-NHOM, giữ nguyên QĐ-6)
  Formula Variable Binding · AL Dynamic Item Rule (có version) · AL Discount Rule

TẦNG 1 — MASTER DATA
  ERPNext core + 34 DocType v17 + 3 DocType v18 + 22 DocType v19
  ★MỚI v20: AL Color Standard · (xóa khỏi thiết kế: mọi Item Variant theo màu — §IV)
```

**Vì sao AI là "dải xuyên suốt" chứ không phải Tầng 8 riêng?** Vì đặt AI thành 1 tầng đóng kín (như v18/v19 vẽ) vô tình gợi ý rằng AI chỉ có 1 điểm chạm (sau khi mọi thứ tính xong). Thực tế AI-First nghĩa là AI có thể được gọi *từ trong* Tầng 5 (Sales đang gõ báo giá), *từ trong* Tầng 2 (kỹ thuật viên đang định nghĩa Rule), *từ trong* Tầng 6B (nhân viên mua hàng đang lập Material Plan) — miễn là điểm ghi dữ liệu luôn đi qua `AL AI Suggestion Log` (Nguyên tắc #21, không đổi).

---

## III. DANH MỤC DOCTYPE TỔNG HỢP

### 3.1 Kế thừa nguyên vẹn (không đổi schema)
34 DocType v17 + 3 DocType v18 (Dynamic Item Rule + 2 child) + toàn bộ 22 DocType v19 (Production/Field Ops/Settlement/Financial/AI Governance — xem danh sách đầy đủ #38-59 trong v19 MASTER DESIGN §III.2, **giữ nguyên tất cả trừ các field bị sửa ở bảng dưới**).

### 3.2 DocType mới v20

| # | DocType | Loại | Module | Mục đích |
|---|---|---|---|---|
| 60 | **AL Color Standard** | Master | Inventory (§IV) | Danh mục màu chuẩn công ty dùng (RAL/vân gỗ), đánh dấu màu nào được phép tồn kho đệm |
| 61 | **AL Project Warehouse Map** | Master | Inventory (§IV) | Ánh xạ Project ↔ Warehouse con dùng riêng cho dự án (tùy chọn, không bắt buộc) |
| 62 | **AL AI Interaction Log** | Master | AI Governance (§XII) | Log mọi lượt AI Copilot tương tác (không phải suggestion ghi vào hệ thống — dùng cho phân tích sử dụng/chi phí token, tách khỏi `AL AI Suggestion Log` vốn chỉ ghi đề xuất có tính ghi dữ liệu) |
| 63 | **AL Drawing Import** | Master | AI/Sales (§XII) | Lưu file bản vẽ khách gửi + kết quả AI trích xuất kích thước, liên kết Quotation nháp sinh ra |

### 3.3 DocType/field bị SỬA (P0 — thay thế thiết kế cũ)

| DocType | Field/thiết kế cũ (v17/v19) | Thay bằng (v20) |
|---|---|---|
| `AL Glass Cut Line` | `item_variant: Link → Item` (Item Variant tồn kho theo màu) | `item: Link → Item` (mã gốc, không đổi theo màu) + `batch_no: Link → Batch` (mang màu qua Batch, xem §IV.3) |
| `AL Aluminum Cutting Plan Line` (v19) | ngầm định dùng Item Variant theo màu | `item: Link → Item` (mã tiết diện gốc) + `batch_no: Link → Batch` + `color_code: Link → AL Color Standard` (denormalize để báo cáo nhanh, không phải nguồn sự thật — nguồn sự thật là Batch) |
| Item (custom field) | *(chưa có, thiếu)* | ★ thêm `al_is_color_variable` (Check) — đánh dấu Item nào (chủ yếu NHOM_PROFILE, một số PHU_KIEN) áp dụng cơ chế Batch-màu, khác với Item cố định 1 màu (VD: gioăng đen luôn là đen → không cần) |

> **Tổng v20: 59 DocType (v17+v18+v19) + 4 DocType mới − 0 DocType xóa (chỉ sửa field) = 63 DocType.**

---

## IV. ★ SỬA LỖI KIẾN TRÚC P0: TỒN KHO NHÔM/VẬT TƯ KHÔNG THEO BIẾN THỂ MÀU

### 4.1 Phân tích bản chất nghiệp vụ

Ba sự thật vận hành của ngành nhôm kính mà thiết kế tồn kho phải tôn trọng:

1. **Số lượng tiết diện nhôm hữu hạn và ổn định** (mỗi hệ profile ~30-80 mã tiết diện: khung, cánh, nẹp...). Đây là trục biến thể hợp lệ duy nhất về mặt vật lý-kỹ thuật (khác tiết diện = khác khuôn đùn, khác item thật sự).
2. **Số lượng màu gần như vô hạn và theo yêu cầu khách hàng** (RAL, vân gỗ, mạ tĩnh điện theo mẫu riêng) — đa phần công ty chỉ giữ tồn kho đệm cho 3-8 màu phổ biến nhất (trắng, đen, ghi xám, vân gỗ óc chó...), còn lại **mua đúng số lượng theo từng dự án, giao thẳng công trình hoặc xưởng, không nhập kho tổng lâu dài**.
3. **Một thanh nhôm màu X mua cho dự án A không thể dùng cho dự án B** (khác lô sơn, có thể lệch tông) — nên vẫn cần **truy vết theo lô** dù không cần **nhân bản Item Master**.

Kết luận kiến trúc: đơn vị quản lý tồn kho đúng là **Item (theo tiết diện) + Batch (mang màu + dự án nguồn)**, không phải **Item Variant (theo tiết diện × màu)**. Đây chính là khác biệt giữa "biến thể sản phẩm" (Attribute cố định của Item, đúng cho sản phẩm bán lẻ như áo có Size/Color) và "lô hàng có thuộc tính riêng" (Batch, đúng cho vật tư sản xuất theo đơn hàng) — ERPNext hỗ trợ tốt cả hai, vấn đề của thiết kế cũ là **chọn sai cơ chế**.

### 4.2 AL Color Standard (Master — mới)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `color_code` | Data (unique) | VD: `RAL9016`, `VANGO-OC-CHO-01` |
| `color_name` | Data | Tên hiển thị |
| `applies_to` | Select | NHOM_PROFILE / PHU_KIEN |
| `is_standard_stock` | Check | Nếu bật → được phép có tồn kho đệm an toàn (safety stock) trong MRP Lite; nếu tắt → **bắt buộc make-to-order theo dự án**, MRP Lite không được đề xuất mua trước khi có SO |
| `default_safety_stock_qty` | Float | Chỉ áp dụng nếu `is_standard_stock=1` |
| `surcharge_rule` | Link → AL Calculation Rule | Trỏ tới rule LOOKUP giá theo màu (TRA-GIA-NHOM, không đổi so với QĐ-6 — surcharge giá và tồn kho vật lý là 2 mối quan tâm tách biệt hoàn toàn) |

### 4.3 Cơ chế Batch thay cho Item Variant

- Item Master của NHOM_PROFILE: **1 Item = 1 tiết diện**, không nhân theo màu. `al_is_color_variable=1` đánh dấu các Item này (khác gioăng/keo luôn 1 màu cố định).
- Bật **"Has Batch No"** cho các Item này trong ERPNext (tính năng core, không cần code mới).
- Khi tạo Purchase Receipt/Stock Entry nhập kho: tạo **Batch mới** cho mỗi lô màu, với custom field trên Batch:

| fieldname (custom field trên Batch) | fieldtype | Mô tả |
|---|---|---|
| `al_color` | Link → AL Color Standard | Màu thực tế của lô này |
| `al_source_project` | Link → Project | Dự án lô này được mua cho (rỗng nếu là tồn kho đệm màu chuẩn) |
| `al_is_reserved_for_project` | Check | Nếu bật → chỉ được xuất kho cho đúng `al_source_project`, hệ thống chặn xuất nhầm dự án khác (validate ở Stock Entry) |

- **Định giá (valuation):** bật "Batch Wise Valuation" (tính năng core ERPNext/Frappe) cho các Item này → giá vốn thực tế theo đúng lô màu đã mua, không bị trộn bình quân gia quyền giữa các màu khác nhau — giải quyết luôn bài toán "giá vốn nhôm màu hiếm bị pha loãng bởi giá nhôm màu phổ biến" mà cơ chế Item thường (non-batch) sẽ mắc phải.
- **Số lượng Item Master không đổi theo số dự án đã làm** — đúng yêu cầu chống "tăng đột biến mã item". Số lượng Batch tăng theo số lô nhập, nhưng Batch là dữ liệu giao dịch nhẹ (không kèm theo overhead cấu hình lại Formula/Rule/Cost Template như Item mới), không ảnh hưởng hiệu năng hay độ phức tạp cấu hình hệ thống.

### 4.4 AL Project Warehouse Map (Master — mới, tùy chọn)

Dành cho công ty muốn tách bạch vật lý (không chỉ tách bạch dữ liệu qua Batch) — ví dụ nhà xưởng có khu vực riêng cho từng công trình lớn:

| fieldname | fieldtype | Mô tả |
|---|---|---|
| `project` | Link → Project | |
| `warehouse` | Link → Warehouse | Warehouse con tự động tạo dạng `"NHOM - {project.name}"` |
| `auto_created` | Check | |
| `close_on_project_complete` | Check | Tự động chuyển tồn kho còn lại (nếu có, thường là phế liệu/dư) về kho tổng khi Project đóng |

> **Nguyên tắc:** đây là lớp tùy chọn (opt-in theo từng Project qua `AL Project Financial Config.use_project_warehouse`), không bắt buộc — công ty quy mô nhỏ dùng Batch là đủ, không cần thêm Warehouse con.

### 4.5 Tác động tới MRP Lite (v17, không đổi core — chỉ đổi input)

| Trước (sai) | Sau (v20) |
|---|---|
| MRP Lite tổng hợp nhu cầu theo `item_variant` (tiết diện+màu) → đề xuất mua theo từng biến thể | MRP Lite tổng hợp theo `(item gốc, color_code)` — **cặp giá trị**, không phải Item riêng — với 2 nhánh: (a) nếu `color.is_standard_stock=1` → cộng dồn vào nhu cầu tồn kho đệm chung; (b) nếu `is_standard_stock=0` → luôn tạo Material Request **gắn `project`**, không gộp chung giữa các dự án dù cùng màu (vì rủi ro lệch tông sơn giữa các lô dù cùng mã màu danh nghĩa) |
| Purchase Order 1 dòng = 1 Item Variant | Purchase Order 1 dòng = 1 Item gốc, `color_code` + `project` là field bổ sung trên dòng PO (không phải trên Item) → khi Purchase Receipt tạo Batch tự động gán đúng màu/dự án từ dòng PO này |

### 4.6 Tác động tới Sản xuất/Cắt (§VII) và định giá (không đổi)

- **Định giá bán vẫn dùng LOOKUP TRA-GIA-NHOM theo (brand, màu)** — hoàn toàn không đổi, đây là phần v17 đã làm đúng (QĐ-6). §IV chỉ sửa tầng **tồn kho vật lý**, không đụng tầng **giá bán**.
- Cutting Plan (§VII) khi xuất kho để cắt: chọn đúng `item` (tiết diện) + được hệ thống gợi ý `batch_no` phù hợp (đúng màu yêu cầu của dòng ConfigSnapshot, ưu tiên batch đã reserve cho đúng project nếu có) — không còn khái niệm "tìm Item Variant đúng màu".

### 4.7 Migration cho dữ liệu cũ (nếu đã lỡ tạo Item Variant theo màu ở giai đoạn thử nghiệm)

1. Với mỗi Item Variant hiện có (tiết diện×màu): tạo 1 Batch trên Item gốc, gán `al_color` = màu tương ứng, chuyển toàn bộ tồn kho hiện tại (Stock Entry loại Material Transfer/Repack nếu ERPNext yêu cầu, hoặc Stock Reconciliation) sang Item gốc + Batch mới.
2. Vô hiệu hóa (`disabled=1`) toàn bộ Item Variant cũ sau khi migrate xong, **không xóa** (giữ lịch sử giao dịch cũ tham chiếu được).
3. Cập nhật mọi Purchase Order/Material Request đang mở (chưa hoàn thành) trỏ sang Item gốc + field `color_code`/`project` mới trước khi Go-live Phase 3.

---

## V. DYNAMIC ITEM RULE — VERSIONING (giữ nguyên từ v19)

Toàn bộ thiết kế Vá Gap P0 của v19 (`AL Dynamic Item Rule Version`, versioning immutable giống BOM Version, luồng Publish/Approval/Rollback, migration tạo v1 cho rule hiện có) **giữ nguyên 100%**, không có thay đổi liên quan tới §IV. Tham khảo chi tiết đầy đủ tại v19 MASTER DESIGN §IV (được đính kèm làm phụ lục lịch sử thiết kế, không lặp lại ở đây để tránh hai nguồn sự thật).

Tóm tắt bất biến cần nhớ khi code hóa:
- `AL Dynamic Item Rule.current_version` → Link tới `AL Dynamic Item Rule Version` đang Published.
- Runtime resolve đọc `rule_snapshot_json` của version, không đọc live threshold/lookup rows.
- `ConfigSnapshot` lưu thêm `rule_version_ids: {rule_code: version_name}`.
- Migration bắt buộc trước go-live: mọi Rule hiện có phải có version v1 Published.

---

## VI. FORMULA ENGINE, PROFILEINTERPRETER, DAG, 3 CHẾ ĐỘ CHỌN ITEM

Không đổi so với v17/v18 — đây là phần lõi đã kiểm chứng qua 8 ví dụ PASS 100% và không nằm trong phạm vi review lần này. Dẫn chiếu:
- Formula Engine / DAG / VariableResolver v3: v18 Upgrade Spec §5-§9.
- 3 chế độ chọn Item (Fixed/Rule/Formula) + ví dụ minh họa: v18 Upgrade Spec Phụ lục B.
- Cost Template, Cost Bucket, AL Calculation Rule mẫu (bao gồm TRA-GIA-NHOM — **không đổi bởi §IV**): v19 MASTER FULL §VI.

---

## VII. MODULE SẢN XUẤT (PRODUCTION & CUTTING) — cập nhật theo §IV

Giữ nguyên toàn bộ nội dung v19 §V (Nguyên tắc P-1, P-2; `AL Cutting Standard`; luồng Cutting Plan 6 bước; `AL Production Order Bridge`), chỉ thay đổi các điểm chạm tồn kho:

| Thành phần | Thay đổi |
|---|---|
| `AL Glass Cutting Plan Line` / `AL Aluminum Cutting Plan Line` | Trường `item_variant` → `item` (gốc) + `batch_no` (§IV.3) |
| Bước 6 (ghi nhận phế liệu/offcut) | Offcut > `min_offcut_reusable_mm` nhập kho phụ **cùng Item gốc**, Batch riêng đánh dấu `al_color` kế thừa từ batch đã cắt — offcut không tạo Item mới, chỉ tạo Batch mới trong kho phụ |
| Phiếu cắt in cho xưởng | Hiển thị rõ `màu (từ Batch)` + `dự án nguồn` trên phiếu để công nhân không nhầm lẫn giữa các lô màu đang cắt song song |

Toàn bộ phần còn lại (Cutting Standard, thuật toán tối ưu 1D/2D, quy trình review-confirm không tự động trừ kho) giữ nguyên nội dung v19.

---

## VIII. MODULE THI CÔNG (FIELD OPERATIONS / INSTALLATION)

Giữ nguyên 100% nội dung v19 §VI: `AL Installation Team`, `AL Installation Order` (vòng đời Draft→Scheduled→In Progress→On Hold→Completed→Warranty), `AL Installation Order Line`, `AL Installation Progress` (append-only, ảnh bắt buộc), `AL Installation Cost Actual`, `AL Warranty Policy`/`AL Warranty Claim`. Không có điểm chạm với §IV (thi công không quản lý tồn kho theo màu — chỉ tiêu thụ vật tư đã xuất kho từ Sản xuất).

---

## IX. MODULE THANH QUYẾT TOÁN (MILESTONE BILLING)

Giữ nguyên 100% nội dung v19 §VII: Nguyên tắc S-1 (tận dụng Payment Schedule core), `AL Milestone Billing Plan`/`Line`, luồng kiểm soát billing theo tiến độ 5 bước, retention.

---

## X. MODULE KẾ TOÁN LÃI LỖ THEO CÔNG TRÌNH (PROJECT PROFITABILITY)

Giữ nguyên 100% nội dung v19 §VIII: `AL Project Financial Config`, `AL Labor Cost Variance`, `AL Project Profitability Snapshot` (immutable, các trường `revenue_recognized`/`material_cost_quoted`/`material_cost_actual`/`labor_install_cost_actual`/`warranty_cost_to_date`/`overhead_allocated`/`gross_profit`/`gross_margin_pct`/`margin_drift_vs_quoted`), luồng tạo snapshot (scheduled/on-demand/event-driven), báo cáo Dashboard + Margin Drift Alert.

**Một bổ sung nhỏ do §IV:** `material_cost_actual` giờ tính chính xác hơn nhờ Batch Wise Valuation (§4.3) — giá vốn thực nhôm màu hiếm không còn bị pha loãng bởi bình quân gia quyền chung, nên `margin_drift_vs_quoted` phản ánh đúng thực tế hơn so với thiết kế cũ (vốn sẽ sai lệch nếu dùng Item Variant có valuation gộp).

---

## XI. QUY TRÌNH NGHIỆP VỤ ĐẦU-CUỐI (LEAD → QUYẾT TOÁN → ĐÓNG SỔ)

```
[1] LEAD / CƠ HỘI
     → (tùy chọn CRM ERPNext hoặc nhập tay)
     → ★v20: AI Drawing Import — khách gửi bản vẽ/ảnh mặt bằng → AI trích xuất kích thước
       sơ bộ → tạo Quotation nháp (§XII.2)

[2] BÁO GIÁ (Quotation)
     → BomOrchestrator (7 bước lõi + Hook A-D thương mại)
     → ConfigSnapshot + AL BOM Version + AL Dynamic Item Rule Version đều được ghim
     → Discount Stack + Approval nếu cần
     → ★v20: AI Quotation Copilot hỗ trợ Sales soạn nhanh, AI Pricing Advisor gợi ý dư địa
       đàm phán dựa trên margin hiện tại (§XII.2)

[3] CHỐT ĐƠN (SO)
     → Copy al_* fields
     → Tạo AL Milestone Billing Plan + AL Installation Order Line (draft)

[4] MUA VẬT TƯ
     → AL Material Plan (★v20: theo Item gốc + color_code + project, §IV.5) → PO → Purchase
       Receipt tạo Batch theo màu (§IV.3) → PI
     → Cost Variance vật tư (nay chính xác hơn nhờ Batch Wise Valuation)
     → ★v20: AI Purchasing Assistant cảnh báo biến động giá nhôm/kính, đề xuất thời điểm mua

[5] SẢN XUẤT
     → AL Aluminum/Glass Cutting Plan đọc ConfigSnapshot → tối ưu cắt (★v20: chọn đúng
       Batch theo màu/dự án, §VII) → AL Glass/Aluminum Cut Order
     → ★v20: AI Cutting Optimization đề xuất phương án cắt tối ưu phế liệu

[6] THI CÔNG
     → AL Installation Order Scheduled → In Progress
     → AL Installation Progress ghi nhận định kỳ (mobile, ★v20: có thể nhập bằng giọng nói
       qua AI, §XII.2) → overall_progress_pct cập nhật
     → AL Installation Cost Actual ghi nhận song song

[7] THANH TOÁN THEO TIẾN ĐỘ
     → Milestone Billing Line tự chuyển Ready to Bill khi đạt ngưỡng tiến độ
     → Kế toán xuất Sales Invoice từng đợt

[8] NGHIỆM THU & BẢO HÀNH
     → Installation Order → Completed
     → AL Warranty Policy kích hoạt; AL Warranty Claim ghi nhận nếu có lỗi
     → ★v20: AI phân tích ảnh nghiệm thu + AI Root Cause Clustering trên Warranty Claim

[9] QUYẾT TOÁN & KẾ TOÁN LÃI LỖ
     → AL Project Profitability Snapshot tổng hợp (vật tư thực — chính xác hơn nhờ §IV —
       + nhân công thực + bảo hành + overhead)
     → margin_drift_vs_quoted đối chiếu cam kết ban đầu
     → ★v20: AI Project Health Score cảnh báo sớm cho Director trong suốt vòng đời, không
       chỉ tại thời điểm quyết toán
     → Đóng Project, đóng AL Project Warehouse (nếu dùng, §IV.4), snapshot cuối lưu vĩnh viễn
```

---

## XII. ★ CHIẾN LƯỢC AI-FIRST TOÀN DỰ ÁN

### 12.1 Nguyên tắc quản trị bất biến (không đổi so với Nguyên tắc #21 v19)

Dù mở rộng rất nhiều use case so với v19, **quy tắc quản trị không đổi 1 chữ**: AI không bao giờ ghi trực tiếp vào bất kỳ DocType immutable nào (ConfigSnapshot, BOM Version, Rule Version, Project Profitability Snapshot, Installation Progress đã submit). Mọi output AI đi qua `AL AI Suggestion Log` (nếu là đề xuất có khả năng ghi dữ liệu nghiệp vụ) hoặc `AL AI Interaction Log` (nếu chỉ là tương tác/tra cứu, không sinh ra thay đổi dữ liệu) → con người xác nhận qua Approval Workflow đã có sẵn.

Bổ sung 3 nguyên tắc quản trị AI mới cho v20:

- **AI-G1 — Không huấn luyện lại mô hình bằng dữ liệu giá/hợp đồng nhạy cảm gửi ra ngoài công ty** nếu dùng model bên thứ ba: ưu tiên cấu hình Zero Data Retention (nếu dùng Anthropic API) hoặc self-host cho các tác vụ chạm dữ liệu tài chính/khách hàng. Các tác vụ không nhạy cảm (đọc bản vẽ công khai, tra cứu quy chuẩn kỹ thuật) có thể dùng API thường.
- **AI-G2 — Mọi Copilot AI phải nêu rõ nguồn dữ liệu đã dùng để trả lời** (RAG citation) khi trả lời câu hỏi nghiệp vụ — tránh AI "bịa" thông số kỹ thuật/giá mà không có căn cứ, đặc biệt nguy hiểm trong ngành có sai số kích thước = hỏng sản phẩm.
- **AI-G3 — Mọi module mới phải tự sinh dữ liệu feedback có nhãn** (Nguyên tắc #23): ví dụ `AL AI Suggestion Log.status` (Accepted/Modified/Rejected) không chỉ để audit mà là **input bắt buộc** cho việc tinh chỉnh prompt/model theo quý — nếu không ai review, dashboard "AI Suggestions chờ review" (đã có ở v19 R-P5) phải cảnh báo, không được để tồn đọng.

### 12.2 Ma trận AI theo toàn bộ vòng đời (mở rộng so với danh sách use case rời rạc của v19)

| Giai đoạn | Use case AI | Input | Output → qua |
|---|---|---|---|
| **Tiền báo giá** ★MỚI | **AI Drawing-to-BOM**: khách gửi bản vẽ CAD/ảnh mặt bằng/PDF kiến trúc → AI thị giác trích xuất kích thước ô cửa, đề xuất cấu hình BOM gần đúng nhất trong thư viện | File upload (`AL Drawing Import`) | Quotation **Draft**, Sales bắt buộc kiểm tra kích thước thực tế trước khi Submit — không bao giờ dùng số AI đọc để chốt giá mà chưa đo lại |
| **Báo giá** (v19 đã có) | AI Quotation Copilot | Mô tả yêu cầu khách + BOM library (RAG) | Quotation Draft |
| **Báo giá** ★MỚI | **AI Pricing/Negotiation Advisor**: đọc margin hiện tại, lịch sử discount đã duyệt cho khách hàng tương tự → gợi ý dư địa giảm giá còn lại trước khi cần Approval cấp cao hơn | ConfigSnapshot + Discount history | Gợi ý hiển thị inline trong BOM Dialog — không tự áp dụng discount |
| **Kỹ thuật/Rule** (v19 đã có) | AI-assisted BOM/Rule Configuration | Mô tả tự nhiên + available_items | `AL Dynamic Item Rule` **Draft version** |
| **Bán hàng — phân tích** (v19 đã có) | AI Win/Loss Analysis | `Quotation.al_loss_reason` | Báo cáo |
| **Mua hàng** ★MỚI | **AI Purchasing/Price Forecast Assistant**: theo dõi biến động giá nhôm phôi/kính nguyên liệu (tương quan giá nhôm LME nếu công khai), cảnh báo thời điểm nên mua trước cho các màu `is_standard_stock=1` | Lịch sử PI + nguồn giá thị trường công khai | Gợi ý trong Material Plan — Admin Confirm |
| **Mua hàng** (v19 đã có, cải tiến) | AI Demand Forecasting (MRP) | Lịch sử PI + Material Plan (★v20: theo Item gốc + color_code, không còn nhiễu bởi hàng nghìn biến thể) | Gợi ý `qty_to_purchase` |
| **Sản xuất** (v19 đã có, ROI cao nhất) | AI Cutting Optimization | ConfigSnapshot + Cutting Standard | `Cutting Plan` — Sản xuất review & confirm |
| **Thi công** ★MỚI | **AI Voice-to-Progress**: đội thi công đọc tiến độ bằng giọng nói (tiếng Việt) qua mobile thay vì gõ tay, AI chuyển thành `AL Installation Progress` draft | Ghi âm ngắn tại công trường | Progress entry **Draft**, team leader xác nhận trước khi submit (vẫn append-only, không phá nguyên tắc §6.4 v19) |
| **Thi công** (v19 đã có) | AI phân tích ảnh nghiệm thu | `AL Installation Progress.photos` | Gợi ý lỗi lắp đặt phổ biến |
| **Tài chính** (v19 đã có) | AI Project Health Score | Profitability Snapshot + Variance + rework count | Cảnh báo Director |
| **Bảo hành** ★MỚI | **AI Root Cause Clustering**: gom nhóm các `AL Warranty Claim` theo mẫu lỗi lặp lại (cùng BOM/nhà cung cấp/đội thi công/lô batch màu) | Toàn bộ Warranty Claim lịch sử | Báo cáo xu hướng cho Director/Sản xuất — không tự tạo hành động khắc phục |
| **Xuyên suốt** (v19 đã có) | AI Anomaly Detection | Cost/Labor/Warranty Variance | Flag Dashboard |
| **Nội bộ** ★MỚI | **AI Trợ lý tri thức công ty (RAG nội bộ)**: chatbot cho nhân viên tra cứu quy trình, thư viện BOM/Rule đã publish, chính sách bảo hành, hướng dẫn dùng hệ thống — không truy cập số liệu tài chính nếu người hỏi không có quyền (tôn trọng phân quyền §XV khi trả lời) | Toàn bộ tài liệu vận hành đã publish + DocType metadata | Trả lời trực tiếp trong chat nội bộ, có citation nguồn (AI-G2) |

### 12.3 Thứ tự ưu tiên triển khai AI (ROI thực tế, không phải độ dễ code)

| Ưu tiên | Use case | Lý do ưu tiên |
|---|---|---|
| **P0** | AI Cutting Optimization | ROI vật chất trực tiếp, đo được ngay (giảm % phế liệu) |
| **P0** | AI Project Health Score | Ngăn lỗ trước khi quyết toán, giá trị phòng ngừa cao nhất |
| **P1** | AI Drawing-to-BOM | Rút ngắn thời gian báo giá — thường là khâu chậm nhất trong sales cycle ngành nhôm kính |
| **P1** | AI-assisted BOM/Rule Configuration | Đã kiểm chứng thiết kế từ v18, rủi ro triển khai thấp |
| **P1** | AI Quotation Copilot + Pricing Advisor | Tăng tốc độ chốt đơn, nhưng cần dữ liệu discount lịch sử đủ lớn mới hữu ích |
| **P2** | AI Purchasing/Price Forecast | Cần ≥6 tháng lịch sử PI mới có tín hiệu |
| **P2** | AI Voice-to-Progress | Tiện lợi vận hành, không phải yếu tố sống còn — làm sau khi mobile app cơ bản ổn định |
| **P2** | AI phân tích ảnh nghiệm thu + Root Cause Clustering | Cần dữ liệu Warranty Claim đủ lớn |
| **P3** | AI Trợ lý tri thức nội bộ (RAG) | Giá trị tăng dần theo khối lượng tài liệu — làm sau khi hệ thống vận hành ổn định, có đủ tài liệu để RAG |
| **P3** | AI Win/Loss Analysis, Anomaly Detection mở rộng | Giữ nguyên như v19, không đổi ưu tiên |

### 12.4 Điều kiện tiên quyết còn thiếu

- `Quotation.al_loss_reason` (v19 đã nêu) — vẫn cần bổ sung trước AI Win/Loss.
- Dữ liệu `AL Color Standard` + lịch sử Batch (§IV) phải sẵn sàng **trước** AI Purchasing Assistant — nếu chưa làm §IV thì input của AI này vẫn bị nhiễu bởi Item Variant cũ.
- Tối thiểu 3-6 tháng lịch sử Cutting Plan trước khi AI Cutting Optimization học được pattern thực tế xưởng (không đổi so với v19).
- Kho tài liệu vận hành (SOP, chính sách) phải được số hóa và cập nhật trước khi triển khai AI Trợ lý tri thức nội bộ — RAG trên tài liệu cũ/sai còn hại hơn không có AI.

---

## XIII. BOMORCHESTRATOR v20 — TỔNG HỢP TOÀN BỘ HOOK

Không đổi cấu trúc 7 bước lõi (v18) + Hook A-D (thương mại, v17) + Hook E/F (Field Ops/Production bootstrap, v19). §IV không thêm hook mới vào Orchestrator — thay đổi tồn kho màu nằm hoàn toàn ở Tầng 6B/6F (Material Plan, Purchase Order, Cutting Plan), các tầng tiêu thụ ConfigSnapshot chứ không phải tầng sinh ra ConfigSnapshot, đúng tinh thần "không phá lõi tính giá".

| Hook | Trigger | Module | Hành động |
|---|---|---|---|
| A-D | Lúc tính giá Quotation | Commercial | Discount, BOM Version link, Cost Variance register, Notification |
| E | `Sales Order.on_submit` | Field Ops | Tạo `AL Installation Order` (Draft) + `AL Milestone Billing Plan` |
| F | `Sales Order.on_submit` | Production | Đăng ký reference vào pool `Cutting Plan` |

---

## XIV. CONFIGSNAPSHOT & AUDIT TRAIL — CHUỖI MINH BẠCH ĐẦY ĐỦ

```
ConfigSnapshot (giá bán, kích thước tính giá)
   ↓ tham chiếu
AL BOM Version + AL Dynamic Item Rule Version (item đã chọn tại thời điểm chốt)
   ↓ tham chiếu
AL Aluminum/Glass Cutting Plan (kích thước cắt, qua AL Cutting Standard)
   ↓ ★v20: chọn Item gốc + Batch (màu/dự án) — KHÔNG còn Item Variant
   ↓ tham chiếu
AL Installation Order Line (planned_nc_ld_cost chốt cứng)
   ↓ đối chiếu với
AL Installation Cost Actual + AL Cost Variance (vật tư, ★v20 chính xác hơn nhờ Batch Wise
Valuation) + AL Labor Cost Variance
   ↓ tổng hợp vào
AL Project Profitability Snapshot (immutable, định kỳ)
```

`explain()` của FormulaEngine trả lời "tại sao giá bán ra con số này". `AL Project Profitability Snapshot.explain_variance()` (v19, không đổi) trả lời "tại sao dự án lãi/lỗ". v20 không thêm hàm minh bạch mới — chuỗi tham chiếu đã đủ để trace ngược từ P&L tới ConfigSnapshot gốc, kể cả khi tồn kho được quản lý qua Batch thay vì Item Variant.

---

## XV. PHÂN QUYỀN & VAI TRÒ

Kế thừa nguyên vẹn bảng vai trò v19 §XIII (AluGlass Sản Xuất, Đội Thi Công, Quản lý Thi công, Director). Bổ sung v20:

| Vai trò mới/mở rộng | DocType được phép | Hành động đặc biệt |
|---|---|---|
| **AluGlass Mua Hàng** *(làm rõ vai trò, trước đây gộp chung Admin)* | `AL Color Standard` (read), `AL Project Warehouse Map` (read), Material Plan/PO (đầy đủ) | Không được tạo Batch `al_is_reserved_for_project=0` cho màu có `is_standard_stock=0` — hệ thống chặn, đúng §4.5 |
| **AluGlass Director** *(mở rộng thêm)* | + `AL Color Standard` (approve màu mới được thêm vào danh mục chuẩn) | Việc thêm 1 màu mới vào `AL Color Standard` với `is_standard_stock=1` (tức là công ty sẽ giữ tồn kho đệm cho màu đó) là quyết định tài chính — cần Director duyệt, không phải nhân viên mua hàng tự quyết |

---

## XVI. LỘ TRÌNH TRIỂN KHAI TỔNG THỂ (PHASE 0–8)

| Phase | Nội dung | Điều kiện hoàn thành |
|---|---|---|
| **Phase 0 ★MỚI v20 — chèn TRƯỚC mọi phase khác** | **Sửa lỗi kiến trúc tồn kho màu (§IV)**: tạo `AL Color Standard`, bật Batch cho Item nhôm/vật tư áp dụng, migration nếu đã lỡ tạo Item Variant | Không còn Item Variant theo màu nào tồn tại trong hệ thống trước khi Phase 3 (Sản xuất) bắt đầu; MRP Lite chạy thử với dữ liệu Batch cho ≥1 dự án thí điểm khớp thủ công |
| Phase 1 | Core Engine (v16-v18) | 8 ví dụ kiểm chứng PASS; Không eval() |
| Phase 2 | Module Commercial (v17) | Như lộ trình v17 |
| Phase 2.5 | Rule Versioning (§V) | Migration v1 cho mọi Rule hiện có |
| Phase 3 | Module Sản Xuất (§VII, đã cập nhật theo §IV) | Cutting Plan giảm phế liệu đo được; **không phát sinh Item mới trong toàn bộ Phase 3** (tiêu chí nghiệm thu bổ sung của §IV) |
| Phase 4 | Module Thi Công + Thanh Quyết Toán (§VIII, §IX) | Installation Progress mobile hoạt động; Milestone Billing đúng |
| Phase 5 | Module Kế Toán Lãi Lỗ (§X) | Profitability Snapshot chạy được ≥3 dự án thí điểm |
| Phase 6 | AI Layer P0-P1 (§XII.3) | AI suggestion qua đúng Approval Workflow, có `AL AI Suggestion Log`/`AL AI Interaction Log` đầy đủ |
| Phase 7 | AI Layer P2 (§XII.3) | Có đủ dữ liệu lịch sử tiên quyết (§12.4) |
| Phase 8 | AI Layer P3 + tối ưu hiệu năng | Theo nhu cầu thực tế |

> **Thay đổi quan trọng nhất so với lộ trình v19:** Phase 0 (sửa tồn kho màu) bắt buộc chạy **trước cả Phase 1** vì đây là quyết định về Item Master — càng để muộn, càng nhiều Purchase Order/Material Request/Batch cũ phải migrate lại, và Phase 3 (Sản xuất) sẽ trực tiếp phụ thuộc vào cơ chế này ngay từ thiết kế `Cutting Plan Line`.

---

## XVII. RỦI RO & ĐIỂM THEO DÕI (HỢP NHẤT, ĐÃ CẬP NHẬT)

Kế thừa Risk Matrix v17 + v18 §12.1 + v19 §XV (không lặp lại — xem file lịch sử). Cập nhật/thêm mới cho v20:

| # | Rủi ro | Mức độ | Xử lý |
|---|---|---|---|
| R-C1 ★ | Team thói quen cũ (đã quen tư duy Item Variant theo màu từ bản thử nghiệm trước) vô tình tạo lại Item mới theo màu ngoài quy trình chuẩn | Cao nếu không đào tạo | Validation ở Item Master: chặn tạo Item mới trùng `item_group=NHOM_PROFILE` có tên chứa mã màu trong `color_code` danh mục `AL Color Standard`; đào tạo lại quy trình mua hàng trước Phase 0 go-live |
| R-C2 ★ | Batch Wise Valuation làm tăng số lượng Batch cần theo dõi, có thể gây nhiễu UI nếu 1 dự án dùng nhiều màu nhỏ lẻ | TB | Giới hạn hiển thị Batch theo `al_source_project` khi user đang thao tác trong ngữ cảnh 1 dự án; archive Batch đã xuất hết + đóng dự án |
| R-C3 ★ | `is_standard_stock` bị bật tùy tiện cho quá nhiều màu → quay lại vấn đề tồn kho phình to (dù không phình Item, vẫn phình vốn lưu kho) | TB | Bắt buộc Director duyệt khi bật cờ này (§XV); rà soát định kỳ quý bởi Kế toán |
| R-A1 ★ | AI Drawing-to-BOM đọc sai kích thước từ bản vẽ mờ/không chuẩn → Sales tin tưởng quá mức, bỏ qua bước đo thực tế | Cao nếu sai | Quotation sinh từ AI Drawing Import luôn gắn badge cảnh báo "Chưa xác minh kích thước thực tế", chặn Submit SO cho tới khi Sales tick xác nhận đã đối chiếu hiện trường |
| R-A2 ★ | AI Trợ lý tri thức nội bộ trả lời dựa trên tài liệu cũ/lỗi thời (v17/v18/v19 các bản trước) nếu không dọn dẹp kho tài liệu | TB | Chỉ index tài liệu v20 trở đi vào RAG; đánh dấu rõ các file v17-v19 là "lưu trữ lịch sử — không dùng cho RAG" |

Toàn bộ risk còn lại (R-P1 đến R-P5 sản xuất/thi công/billing/P&L/AI Suggestion Log, không đổi so với v19) giữ nguyên.

---

## XVIII. CHECKLIST GO-LIVE

- [ ] **★Phase 0: Không còn Item Variant theo màu nào trong hệ thống** — kiểm tra bằng script quét toàn bộ Item có Attribute "Màu"/tương đương, phải trả về 0 kết quả
- [ ] `AL Color Standard` khai báo đầy đủ cho toàn bộ màu công ty đang dùng, đã phân loại đúng `is_standard_stock`
- [ ] Batch Wise Valuation đã bật và test cho ≥1 chu kỳ mua-cắt-xuất kho hoàn chỉnh
- [ ] 8 ví dụ kiểm chứng v17 + ví dụ A-G (v19) PASS 100%
- [ ] Migration Rule Versioning hoàn tất, mọi Rule có `current_version`
- [ ] Test migration định lượng VariableResolver v2 vs v3 trên ≥100 Quotation thật
- [ ] Cutting Standard khai báo đầy đủ cho toàn bộ profile nhôm + loại kính đang dùng
- [ ] Milestone Billing Plan template mặc định đã duyệt với Kế toán trưởng
- [ ] Project Profitability Snapshot chạy thí điểm ≥3 dự án đã hoàn thành, đối chiếu khớp báo cáo thủ công (★v20: đặc biệt kiểm tra `material_cost_actual` đúng nhờ Batch Valuation, không lệch như thiết kế Item Variant cũ)
- [ ] Toàn bộ AI use case Phase 6 có `AL AI Suggestion Log`/`AL AI Interaction Log` + đi qua Approval Workflow — không có đường tắt AI ghi trực tiếp
- [ ] Phân quyền Đội Thi Công (mobile, append-only) đã test không cho sửa/xóa record cũ
- [ ] `AL Drawing Import` → Quotation nháp có badge cảnh báo bắt buộc xác minh kích thước, đã test chặn Submit SO khi chưa xác nhận
- [ ] Đào tạo đội Mua hàng + Sản xuất về quy trình Batch-màu mới trước khi tắt hoàn toàn quy trình Item Variant cũ (nếu đã từng dùng thử nghiệm)

---

*Hết tài liệu v20. Các file v17 FINAL, v17 REVIEW, v18 Upgrade Spec, v19 MASTER DESIGN, v19 MASTER FULL được giữ lại làm tài liệu lưu trữ lịch sử thiết kế, không dùng để code hóa song song với file này nhằm tránh hai nguồn sự thật.*
