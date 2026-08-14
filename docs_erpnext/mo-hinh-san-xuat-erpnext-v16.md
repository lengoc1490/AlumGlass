# CÁC MÔ HÌNH SẢN XUẤT TRONG ERPNEXT (FRAPPE v16)
### Phân tích chi tiết A-Z: Doctype, Flow, Ví dụ, Điểm mạnh/Hạn chế & Đề xuất mô hình kết hợp

> Tài liệu dành cho: Chủ doanh nghiệp sản xuất, Trưởng phòng vận hành/SCM, Solution Consultant/Implementer ERPNext, Đội chuyển đổi số.
> Phạm vi: Module **Manufacturing** trong ERPNext v16 (Frappe Framework), bao gồm liên kết với **Stock**, **Selling**, **Buying**, **Quality**, **Projects**.

---

## MỤC LỤC

1. [Tổng quan Module Manufacturing trong ERPNext v16](#1-tổng-quan-module-manufacturing-trong-erpnext-v16)
2. [Bản đồ Doctype & Quan hệ dữ liệu](#2-bản-đồ-doctype--quan-hệ-dữ-liệu)
3. [Các mô hình sản xuất chi tiết](#3-các-mô-hình-sản-xuất-chi-tiết)
   - 3.1 Make to Stock (MTS)
   - 3.2 Make to Order (MTO)
   - 3.3 Assemble to Order (ATO)
   - 3.4 Engineer to Order (ETO)
   - 3.5 Repetitive Manufacturing
   - 3.6 Batch Manufacturing
   - 3.7 Subcontracting / Job Work (Gia công ngoài)
   - 3.8 Process Manufacturing (hỗn hợp/liên tục)
4. [Bảng so sánh tổng hợp 8 mô hình](#4-bảng-so-sánh-tổng-hợp)
5. [Đề xuất các phương án kết hợp mô hình (Hybrid Models)](#5-đề-xuất-phương-án-kết-hợp-mô-hình)
6. [Cấu hình hệ thống liên quan (Manufacturing Settings)](#6-cấu-hình-hệ-thống-liên-quan)
7. [Khuyến nghị triển khai theo quy mô & ngành nghề](#7-khuyến-nghị-triển-khai)
8. [Checklist triển khai thực tế](#8-checklist-triển-khai-thực-tế)

---

## 1. TỔNG QUAN MODULE MANUFACTURING TRONG ERPNEXT v16

ERPNext tổ chức sản xuất theo nguyên lý **MRP II (Manufacturing Resource Planning)** đơn giản hóa, xoay quanh 4 trụ cột:

| Trụ cột | Doctype đại diện | Vai trò |
|---|---|---|
| **Định mức nguyên vật liệu** | `BOM` (Bill of Materials) | "Công thức" tạo ra sản phẩm |
| **Kế hoạch sản xuất** | `Production Plan` | Tính toán MRP: cần sản xuất bao nhiêu, cần mua bao nhiêu |
| **Lệnh sản xuất** | `Work Order` | Lệnh thực thi cho 1 mã hàng, 1 số lượng, 1 nhà máy |
| **Thực thi tại xưởng** | `Job Card` + `Stock Entry` | Ghi nhận thời gian, nhân công, NVL tiêu hao, thành phẩm nhập kho |

v16 kế thừa toàn bộ kiến trúc từ v14/v15 (đã hợp nhất "Subcontracting" mới thay cho mô hình cũ dùng PO trực tiếp) và bổ sung/ cải tiến:
- **Job Card** mạnh hơn: nhiều `Time Log`, Job Card Scrap Item, liên kết Workstation Type (chọn máy linh hoạt theo nhóm máy thay vì máy cố định).
- **Plant Floor / Manufacturing Dashboard** trực quan hơn để theo dõi Work Order theo trạng thái (Kanban).
- **Capacity Planning** (hoạch định năng lực) dựa trên Workstation working hours khi tạo Work Order.
- **Downtime Entry** để ghi nhận thời gian dừng máy → tính OEE (Overall Equipment Effectiveness) gần đúng.

---

## 2. BẢN ĐỒ DOCTYPE & QUAN HỆ DỮ LIỆU

### 2.1 Nhóm Doctype "Master" (Dữ liệu nền)

| Doctype | Chức năng |
|---|---|
| `Item` | Danh mục vật tư/thành phẩm/bán thành phẩm. Trường quan trọng: `is_stock_item`, `include_item_in_manufacturing`, `default_bom` |
| `BOM` | Định mức NVL + công đoạn (Operations) + chi phí (Costing) cho 1 Item |
| `BOM Item` | Dòng chi tiết NVL trong BOM (child table) |
| `Operation` | Danh mục công đoạn (VD: Cắt, Hàn, Sơn, Đóng gói) |
| `Routing` | Chuỗi Operation dùng chung cho nhiều BOM (tái sử dụng quy trình) |
| `Workstation` | Máy/trạm làm việc cụ thể, có giờ làm việc, chi phí giờ máy |
| `Workstation Type` | Nhóm các Workstation cùng chức năng (v14+), cho phép Job Card chọn máy trống bất kỳ trong nhóm |
| `Warehouse` | Kho: NVL, WIP (bán thành phẩm), thành phẩm |
| `Quality Inspection Template` | Mẫu tiêu chí kiểm tra chất lượng |

### 2.2 Nhóm Doctype "Kế hoạch & Lệnh"

| Doctype | Chức năng |
|---|---|
| `Production Plan` | Tổng hợp nhu cầu (từ Sales Order/Material Request/nhập tay) → chạy MRP → sinh Work Order + Material Request |
| `Production Plan Item` | Dòng sản phẩm cần sản xuất trong kế hoạch |
| `Material Request` | Yêu cầu vật tư (Purchase/Transfer/Manufacture) |
| `Work Order` | Lệnh sản xuất chính thức cho 1 Item + BOM + số lượng + kho nguồn/đích |
| `Work Order Operation` | Copy các Operation từ BOM/Routing vào Work Order để theo dõi tiến độ từng công đoạn |
| `Job Card` | Phiếu công việc thực thi cho 1 Operation của 1 Work Order, gán Workstation + nhân công |
| `Job Card Time Log` | Log thời gian bắt đầu/kết thúc thực tế của Job Card |
| `Job Card Scrap Item` | Vật tư phế phẩm phát sinh trong công đoạn |

### 2.3 Nhóm Doctype "Kho vận & Kế toán giá thành"

| Doctype | Chức năng |
|---|---|
| `Stock Entry` | Giao dịch kho — dùng nhiều loại (`purpose`): *Material Transfer for Manufacture*, *Manufacture*, *Material Consumption for Manufacture*, *Send to Subcontractor*, *Material Transfer* |
| `Stock Entry Detail` | Dòng chi tiết vật tư trong Stock Entry |
| `Serial No` / `Batch` | Theo dõi theo số seri/lô |
| `Quality Inspection` | Bản ghi kiểm tra chất lượng thực tế (gắn với Stock Entry/Delivery Note) |
| `Landed Cost Voucher` | Phân bổ chi phí phụ vào giá vốn NVL nhập khẩu |

### 2.4 Nhóm Doctype "Gia công ngoài" (Subcontracting – kiến trúc mới từ v14+)

| Doctype | Chức năng |
|---|---|
| `Purchase Order` (is_subcontracted) | Đơn hàng gia công gốc |
| `Subcontracting Order` | Sinh từ Purchase Order, quản lý NVL giao cho NCC gia công |
| `Subcontracting Receipt` | Nhận lại thành phẩm gia công + tiêu hao NVL đã giao |
| `Subcontracting BOM` | BOM áp dụng cho quy trình gia công |
| `Stock Entry (Send to Subcontractor)` | Xuất kho NVL giao NCC |

### 2.5 Sơ đồ quan hệ tổng quát (text-flow)

```
Item ── default_bom ──> BOM ──> BOM Item (NVL)
                          │
                          └──> Operation / Routing ──> Workstation / Workstation Type

Sales Order ─┐
Material Req ─┼──> Production Plan ──> MRP Engine ──┬──> Work Order ──> Job Card ──> Stock Entry (Manufacture)
Forecast ─────┘                                      └──> Material Request (mua/điều chuyển NVL thiếu)

Work Order ──> Stock Entry (Material Transfer for Manufacture) [xuất NVL vào WIP]
Work Order ──> Stock Entry (Manufacture) [nhập thành phẩm, tiêu hao NVL]
Work Order ──> Quality Inspection [nếu Item yêu cầu QC]

Purchase Order (subcontract=1) ──> Subcontracting Order ──> Stock Entry (Send to Subcontractor)
                                                         ──> Subcontracting Receipt ──> nhập kho thành phẩm gia công
```

---

## 3. CÁC MÔ HÌNH SẢN XUẤT CHI TIẾT

---

### 3.1 MAKE TO STOCK (MTS) — Sản xuất theo dự trữ tồn kho

#### Định nghĩa
Sản xuất **trước khi có đơn hàng**, dựa trên dự báo nhu cầu, mức tồn kho tối thiểu (reorder level) hoặc kế hoạch sản xuất định kỳ. Thành phẩm nhập kho chờ bán.

#### Đặc điểm
- Không gắn Sales Order vào Work Order (trường `sales_order` để trống).
- Dùng cho sản phẩm tiêu chuẩn, nhu cầu ổn định, vòng đời dài (FMCG, linh kiện phổ thông, đồ gia dụng).
- Rủi ro: tồn kho dư thừa nếu dự báo sai.

#### Doctype liên quan
`Item` (is_stock_item=1) → `BOM` → `Production Plan` (nguồn: "Material Request" hoặc "Manual/Item wise") → `Work Order` → `Stock Entry` → `Warehouse` (thành phẩm) → `Sales Order`/`Delivery Note` khi có khách mua.

#### Flow chi tiết

```
BƯỚC 1: Bộ phận Kế hoạch mở Production Plan
         → Get Items For (chọn "Sales Order" nếu có đơn dự kiến, hoặc nhập tay Item + Qty)
         → Chạy "Get Items to Manufacture" → hệ thống tự tính:
             Qty cần SX = Qty kế hoạch − Tồn kho hiện có − Qty đang SX dở dang

BƯỚC 2: Production Plan → "Create Work Order" (tự động theo từng Item + BOM mặc định)

BƯỚC 3: Work Order được duyệt (status: Draft → Submitted)
         → Bấm "Start" hoặc tạo Stock Entry loại "Material Transfer for Manufacture"
         → NVL rời kho Raw Material → chuyển vào kho WIP (Work In Progress)

BƯỚC 4: Job Card tự sinh theo từng Operation trong BOM
         → Công nhân xưởng bấm "Start" Job Card → Time Log ghi nhận
         → Hoàn tất Job Card → bấm "Complete"

BƯỚC 5: Khi tất cả Job Card hoàn tất (hoặc thủ công) 
         → Work Order → "Update Qty" → tạo Stock Entry loại "Manufacture"
         → Thành phẩm nhập kho Finished Goods, đồng thời NVL trong WIP bị trừ (backflush theo BOM)

BƯỚC 6: (Tuỳ chọn) Quality Inspection nếu Item bật "Quality Inspection Required"

BƯỚC 7: Thành phẩm nằm trong kho chờ Sales Order → khi có khách đặt → Delivery Note xuất thẳng từ tồn kho có sẵn (không cần chờ sản xuất)
```

#### Ví dụ minh họa
Công ty sản xuất **ghế nhựa Model A101**, dự báo bán 5,000 cái/tháng.
- Kế hoạch tháng 8/2026: Production Plan tạo cho Item "Ghế nhựa A101", Qty = 5,000, trừ tồn kho hiện có 800 cái → Qty cần SX = 4,200.
- Hệ thống dựa trên BOM (Nhựa PP hạt: 0.6kg/ghế, khung sắt: 1 bộ/ghế) tự tính NVL cần: 2,520 kg nhựa PP + 4,200 bộ khung sắt.
- Nếu tồn kho NVL không đủ → Production Plan tự sinh `Material Request` (Purchase) gửi phòng mua hàng.
- Work Order "WO-2026-00045" tạo cho 4,200 ghế, chia làm 3 đợt SX (Work Order Qty cho phép SX từng phần qua nhiều Stock Entry Manufacture).
- Cuối tháng, ghế nhập kho Finished Goods, chờ đơn hàng từ đại lý.

#### Điểm mạnh
- ✅ Đáp ứng đơn hàng **ngay lập tức** (giao hàng nhanh, tăng trải nghiệm khách hàng).
- ✅ Tối ưu hiệu suất máy móc — sản xuất lô lớn, giảm chi phí setup/lần chuyển đổi mã hàng.
- ✅ Dễ hoạch định năng lực nhà máy dài hạn.

#### Hạn chế
- ❌ Rủi ro tồn kho ứ đọng, chi phí lưu kho cao nếu dự báo sai.
- ❌ Không phù hợp sản phẩm tùy biến theo khách hàng (custom).
- ❌ Vốn lưu động bị "giam" trong hàng tồn kho.
- ❌ Nguy cơ lỗi thời (obsolete) với sản phẩm có vòng đời ngắn.

---

### 3.2 MAKE TO ORDER (MTO) — Sản xuất theo đơn đặt hàng

#### Định nghĩa
Chỉ bắt đầu sản xuất **sau khi có Sales Order xác nhận** từ khách hàng. NVL cũng có thể chỉ mua khi có đơn (Purchase to Order).

#### Đặc điểm
- Work Order **bắt buộc gắn `sales_order`** để truy vết (traceability) 1-1 giữa đơn hàng và lệnh sản xuất.
- Item Setting có thể bật cờ mặc định `Default Material Request Type = Purchase` kết hợp cờ ở Sales Order Item `ensure_delivery_based_on_produced_quantity`.
- Delivery Note chỉ được tạo dựa trên số lượng **đã sản xuất thực tế** (nếu bật ràng buộc).

#### Doctype liên quan
`Sales Order` → `Sales Order Item` → `Production Plan` (Get Items From = "Sales Order") → `Work Order` (trường sales_order được điền) → `Job Card` → `Stock Entry` → `Delivery Note`.

#### Flow chi tiết

```
BƯỚC 1: Khách hàng đặt hàng → tạo Sales Order (SO-2026-00312), Item = "Bàn gỗ theo yêu cầu B205", Qty = 50

BƯỚC 2: Production Plan → Get Items For = "Sales Order" → chọn SO-2026-00312
         → hệ thống load Item + BOM tương ứng + Qty = 50 (giữ nguyên liên kết Sales Order)

BƯỚC 3: Production Plan → Create Work Order
         → Work Order tự động điền trường "Sales Order" = SO-2026-00312 (Sales Order Item)
         → Kho đích Finished Goods có thể là kho riêng theo dự án/khách hàng nếu cần

BƯỚC 4: Nếu thiếu NVL → Production Plan sinh Material Request loại "Purchase"
         (Purchase to Order — chỉ mua đúng số lượng cần cho đơn này, không tồn kho dư)

BƯỚC 5: Thực thi Work Order như MTS (Material Transfer → Job Card → Manufacture)

BƯỚC 6: Khi Work Order hoàn tất → Sales Order hiển thị "Produced Qty"
         → Delivery Note chỉ cho phép giao tối đa bằng Produced Qty (nếu bật ràng buộc)
         → Đảm bảo không giao hàng chưa sản xuất xong
```

#### Ví dụ minh họa
Xưởng mộc nhận đơn 50 bộ bàn gỗ theo kích thước khách yêu cầu (B205 – dài 1.8m, gỗ sồi).
- Sales Order SO-2026-00312, giao hàng dự kiến 30 ngày.
- Production Plan liên kết SO này, tạo Work Order WO-2026-00098 với `sales_order` = SO-2026-00312.
- Thiếu gỗ sồi tấm → Material Request (Purchase) 50 x 2 tấm = 100 tấm, mua đúng số lượng, không dư kho.
- Khi Work Order hoàn tất 50 bàn → Delivery Note tạo, giao đúng 50 bàn cho khách, không dư tồn kho thành phẩm.

#### Điểm mạnh
- ✅ Không tồn kho thành phẩm dư thừa → giảm vốn lưu động, giảm rủi ro lỗi thời.
- ✅ Truy vết rõ ràng: 1 đơn hàng = 1 lệnh sản xuất = 1 lô NVL mua riêng (tốt cho tính giá thành chính xác theo đơn/dự án).
- ✅ Phù hợp sản phẩm có biến thể/tùy chỉnh vừa phải.

#### Hạn chế
- ❌ Thời gian giao hàng (lead time) dài hơn MTS vì phải chờ SX.
- ❌ Khó tối ưu hiệu suất máy nếu đơn hàng nhỏ lẻ, phân tán (nhiều lần chuyển đổi mã hàng/setup).
- ❌ Phụ thuộc năng lực dự báo lead time chính xác để cam kết ngày giao với khách.

---

### 3.3 ASSEMBLE TO ORDER (ATO) — Lắp ráp theo đơn hàng

#### Định nghĩa
Bán thành phẩm/linh kiện được sản xuất **trước theo MTS**, nhưng **lắp ráp cuối cùng** (final assembly) chỉ thực hiện khi có đơn hàng, cho phép tùy biến cấu hình sản phẩm cuối theo khách.

#### Đặc điểm
- Sử dụng **BOM nhiều cấp (Multi-level BOM)**: cấp con SX theo MTS, cấp cha (thành phẩm cuối) SX theo MTO.
- Thường kết hợp `Sales Order` với Item có thuộc tính (Item Variant/Attribute) để khách chọn cấu hình (màu, dung lượng, phụ kiện đi kèm).
- Điển hình: lắp ráp máy tính, xe máy, tủ bếp theo module.

#### Doctype liên quan
`Item` (Template + Variant, dùng `Item Attribute`) → `BOM` cấp 2 (cho từng cụm linh kiện, SX theo MTS trước) → `BOM` cấp 1 (thành phẩm cuối, chỉ có bước "Lắp ráp") → `Sales Order` → `Work Order` (cấp 1, MTO) → `Stock Entry`.

#### Flow chi tiết

```
GIAI ĐOẠN NỀN (MTS - chuẩn bị trước, không chờ đơn hàng):
  Production Plan (định kỳ) → Work Order cho các CỤM LINH KIỆN (VD: Khung xe, Động cơ, Bánh xe)
  → Stock Entry Manufacture → nhập kho bán thành phẩm (Sub-assembly) sẵn sàng

GIAI ĐOẠN LẮP RÁP (MTO - chỉ khi có đơn):
  BƯỚC 1: Khách chọn cấu hình qua Sales Order (VD: Xe máy màu Đỏ, phanh đĩa, vành đúc)
           → Item Variant tương ứng được chọn/tạo tự động theo Attribute

  BƯỚC 2: Production Plan (Get Items From = Sales Order) → Work Order LẮP RÁP
           → BOM cấp 1 chỉ gồm các Sub-assembly (không phải NVL thô) + 1 Operation "Lắp ráp hoàn thiện"

  BƯỚC 3: Stock Entry "Material Transfer for Manufacture" xuất các Sub-assembly có sẵn từ kho
           → Job Card "Lắp ráp" hoàn tất nhanh (thời gian ngắn, vì linh kiện đã có sẵn)

  BƯỚC 4: Stock Entry "Manufacture" → nhập thành phẩm hoàn chỉnh → Delivery Note giao khách
           (Lead time giao hàng RẤT NGẮN vì chỉ chờ lắp ráp, không chờ SX từ đầu)
```

#### Ví dụ minh họa
Hãng lắp ráp xe đạp thể thao:
- BOM cấp 2 (SX trước, MTS): "Khung xe carbon", "Bộ truyền động", "Bánh xe 27.5inch" — sản xuất hàng loạt, tồn kho sẵn.
- Khách đặt: Sales Order chọn Item Variant "Xe đạp Model X – Khung Đỏ – Phanh đĩa dầu – Vành carbon".
- Work Order lắp ráp WO-2026-00201 chỉ cần: 1 Khung Đỏ + 1 Bộ truyền động + 2 Bánh vành carbon + Operation "Lắp ráp & Test".
- Thời gian hoàn thành: 4 giờ (thay vì 5 ngày nếu sản xuất từ đầu) → giao khách trong ngày.

#### Điểm mạnh
- ✅ **Cân bằng** giữa tốc độ giao hàng (gần bằng MTS) và khả năng tùy biến (gần bằng MTO).
- ✅ Giảm tồn kho thành phẩm cuối (vốn có giá trị cao) nhưng vẫn giữ tồn kho cụm linh kiện (giá trị thấp hơn) để phản ứng nhanh.
- ✅ Rất phù hợp ngành có nhiều biến thể sản phẩm (điện tử, nội thất module, xe cộ).

#### Hạn chế
- ❌ Đòi hỏi thiết kế BOM nhiều cấp chuẩn xác, quản trị Item Variant phức tạp hơn.
- ❌ Cần dự báo tốt cho cấp Sub-assembly (vẫn có rủi ro tồn kho như MTS ở cấp linh kiện).
- ❌ Cấu hình `Item Attribute`/`Item Variant` trong Frappe nếu số lượng biến thể lớn (hàng nghìn tổ hợp) có thể làm phình dữ liệu Item.

---

### 3.4 ENGINEER TO ORDER (ETO) — Sản xuất theo thiết kế riêng

#### Định nghĩa
Sản phẩm **chưa tồn tại BOM chuẩn** — phải qua giai đoạn **thiết kế/kỹ thuật** riêng cho từng đơn hàng/dự án trước khi có thể lập BOM và sản xuất. Áp dụng cho công trình, máy móc đặc chủng, dự án cơ khí phi tiêu chuẩn.

#### Đặc điểm
- Bắt buộc kết hợp module **Projects** (`Project`, `Task`) để quản lý giai đoạn thiết kế trước khi ra BOM.
- BOM thường tạo **mới hoàn toàn cho từng dự án** (không tái sử dụng), đặt tên theo mã dự án.
- Chi phí kỹ thuật/thiết kế (engineering cost) cần hạch toán riêng, thường qua `Timesheet` gắn `Project`.

#### Doctype liên quan
`Opportunity`/`Quotation` → `Sales Order` → `Project` (tự động hoặc thủ công) → `Task` (giai đoạn thiết kế, phê duyệt bản vẽ) → `BOM` (tạo mới riêng cho dự án, `project` field) → `Production Plan`/`Work Order` (gắn `project`) → `Job Card` → `Stock Entry` → nghiệm thu.

#### Flow chi tiết

```
BƯỚC 1: Sales/Kỹ thuật nhận yêu cầu đặc thù → Quotation sơ bộ (giá tạm tính theo kinh nghiệm)
         → Khách chấp thuận → Sales Order được tạo, đồng thời Project tự sinh (Sales Order → Project)

BƯỚC 2: Project chứa các Task giai đoạn:
         "Khảo sát" → "Thiết kế bản vẽ 2D/3D" → "Phê duyệt khách hàng" → "Lập BOM & dự trù vật tư"
         (Kỹ sư dùng Timesheet để chấm công thiết kế, chi phí này có thể cộng vào giá thành dự án)

BƯỚC 3: Sau khi bản vẽ được duyệt → Kỹ sư tạo BOM MỚI, đặt tên "BOM-DUANXYZ-001", gắn field `Project`
         → Không dùng BOM có sẵn vì đây là thiết kế riêng biệt

BƯỚC 4: Production Plan / Work Order tạo trực tiếp từ BOM này, gắn `project` = "DUANXYZ"
         (Không nhất thiết cần Sales Order riêng lẻ theo dòng Item vì có thể là 1 hạng mục lớn)

BƯỚC 5: Thực thi SX như MTO, nhưng TOÀN BỘ chi phí (NVL + nhân công + thiết kế + giờ máy)
         được tổng hợp trên Project → xem báo cáo "Project Profitability"

BƯỚC 6: Nghiệm thu, bàn giao, đóng Project. BOM có thể lưu lại làm tham chiếu cho dự án tương lai
         tương tự (nhưng thường vẫn cần điều chỉnh lại)
```

#### Ví dụ minh họa
Công ty cơ khí nhận đơn chế tạo **1 dây chuyền băng tải đóng gói tự động** theo yêu cầu riêng của nhà máy thực phẩm.
- Quotation sơ bộ 800 triệu VNĐ dựa trên kinh nghiệm dự án tương tự.
- Sales Order được duyệt → Project "BT-2026-007" tự tạo.
- Task: Khảo sát mặt bằng (3 ngày) → Thiết kế bản vẽ CAD (10 ngày) → Duyệt khách hàng (2 ngày) → Lập BOM (2 ngày).
- BOM "BOM-BT2026007-Khung": thép hộp 40x80, motor giảm tốc, băng tải PVC, cảm biến quang... (thiết kế riêng, không dùng lại từ dự án khác).
- Work Order gắn Project "BT-2026-007" → SX 6 tuần → nghiệm thu tại nhà máy khách hàng.
- Báo cáo Project Profitability: Doanh thu 800tr − (NVL 420tr + Nhân công SX 90tr + Giờ thiết kế kỹ sư quy đổi 35tr + Chi phí khác 15tr) = Lợi nhuận gộp ~240tr.

#### Điểm mạnh
- ✅ Phù hợp tuyệt đối cho sản phẩm/công trình **độc nhất, phi tiêu chuẩn**.
- ✅ Quản lý được chi phí **thiết kế + kỹ thuật** — thứ mà MTS/MTO thông thường không tính đến.
- ✅ Tích hợp Project giúp theo dõi tiến độ đa giai đoạn (không chỉ riêng sản xuất).

#### Hạn chế
- ❌ Thời gian từ đơn hàng đến giao hàng **dài nhất** trong các mô hình.
- ❌ Khó ước tính giá thành chính xác trước khi thiết kế xong (rủi ro báo giá sai).
- ❌ Không tái sử dụng được BOM nhiều → tốn công thiết lập lại cho mỗi dự án.
- ❌ Đòi hỏi đội ngũ vận hành thành thạo cả Project module lẫn Manufacturing module.

---

### 3.5 REPETITIVE MANUFACTURING — Sản xuất lặp lại (liên tục, tốc độ cao)

#### Định nghĩa
Sản xuất khối lượng lớn, lặp đi lặp lại **cùng 1 sản phẩm/1 nhóm sản phẩm** trong thời gian dài, không cần lập Work Order riêng cho từng lô nhỏ như mô hình rời rạc (discrete).

#### Đặc điểm
- Có thể dùng **1 Work Order với số lượng lớn**, chia nhỏ SX qua nhiều lần Stock Entry "Manufacture" (mỗi ca/mỗi ngày 1 lần) mà không cần đóng Work Order.
- Kết hợp cờ **"Skip Material Transfer for Manufacture"** trong Manufacturing Settings → cho phép **Backflush** trực tiếp nguyên liệu từ kho Raw Material khi tạo Stock Entry "Manufacture" (bỏ qua bước chuyển kho WIP trung gian) — giảm thao tác nhập liệu.
- Phù hợp dây chuyền chạy liên tục (lắp ráp linh kiện điện tử, đóng chai nước giải khát, bao bì...).

#### Doctype liên quan
`Work Order` (Qty lớn, `transfer_material_against` = "Work Order" thay vì "Job Card") → nhiều `Stock Entry` (Manufacture) submit liên tiếp theo từng ca → `Job Card` (nếu vẫn muốn theo dõi công đoạn, nhưng thường đơn giản hóa) → cập nhật Manufacturing Settings `Backflush Raw Materials Based On = "BOM"` hoặc `"Material Transferred for Manufacture"`.

#### Flow chi tiết

```
BƯỚC 1: Bật cấu hình tại Manufacturing Settings:
         ☑ Backflush Raw Materials Based On = BOM
         ☑ (tuỳ chọn) Skip Material Transfer for Manufacture nếu muốn xuất NVL trực tiếp từ kho thô

BƯỚC 2: Tạo 1 Work Order lớn cho cả kế hoạch tuần/tháng
         VD: WO-2026-00500, Item "Chai nước 500ml", Qty kế hoạch = 100,000 chai

BƯỚC 3: Mỗi ca sản xuất (VD 8 tiếng), quản đốc tạo Stock Entry "Manufacture" NGAY từ Work Order
         nhập số lượng SẢN XUẤT THỰC TẾ trong ca (VD 12,000 chai/ca)
         → hệ thống tự backflush đúng tỷ lệ NVL theo BOM (nước, nắp chai, nhãn mác, vỏ chai)
         → KHÔNG cần đợi hoàn tất cả Job Card hay đóng Work Order

BƯỚC 4: Lặp lại Bước 3 nhiều lần trong ngày/tuần cho đến khi đạt tổng Qty kế hoạch
         (Work Order vẫn ở trạng thái "In Process" cho đến khi đủ số lượng)

BƯỚC 5: Khi đạt 100,000 chai → Work Order tự chuyển "Completed"
         Có thể theo dõi Downtime Entry nếu máy dừng giữa ca để tính hiệu suất (OEE)
```

#### Ví dụ minh họa
Nhà máy đóng chai nước giải khát:
- Work Order WO-2026-00500: SX 100,000 chai/tuần, chạy 3 ca/ngày x 6 ngày.
- Ca sáng thứ 2: Stock Entry Manufacture ghi nhận 4,000 chai → backflush tự động 4,000 lít nước lọc + 4,000 nắp + 4,000 nhãn.
- Không cần tạo Job Card riêng theo dõi thời gian cho từng chai — chỉ theo dõi tổng ca.
- Cuối tuần: Work Order hoàn tất khi đạt đủ 100,000 chai, kế toán ghi nhận giá thành trung bình cả tuần.

#### Điểm mạnh
- ✅ **Tối giản thao tác nhập liệu** — không cần mở/đóng nhiều Work Order nhỏ.
- ✅ Rất phù hợp dây chuyền tốc độ cao, sản lượng lớn, ít thay đổi mã hàng.
- ✅ Giảm tải hệ thống (ít Doctype record hơn discrete manufacturing khi SX số lượng cực lớn).

#### Hạn chế
- ❌ **Giảm khả năng truy vết chi tiết** theo từng lô nhỏ/ca cụ thể nếu không cấu hình Batch kỹ.
- ❌ Backflush tự động có thể gây sai lệch nhỏ nếu định mức BOM không chuẩn (hao hụt thực tế khác BOM).
- ❌ Khó áp dụng cho sản phẩm có nhiều biến thể thay đổi liên tục trong ngày.

---

### 3.6 BATCH MANUFACTURING — Sản xuất theo lô

#### Định nghĩa
Sản xuất theo **từng lô (Batch)** xác định, mỗi lô có mã số riêng để truy vết nguồn gốc, hạn sử dụng, chất lượng — phổ biến trong Dược phẩm, Thực phẩm, Hóa mỹ phẩm.

#### Đặc điểm
- Item bật `Has Batch No = 1`, có thể bật `Create New Batch` tự động khi Stock Entry Manufacture, hoặc yêu cầu nhập thủ công.
- Có thể gắn `Expiry Date`, `Manufacturing Date` cho từng Batch.
- Thường đi kèm bắt buộc **Quality Inspection** trước khi Batch được phép xuất bán.

#### Doctype liên quan
`Item` (Has Batch No) → `BOM` → `Work Order` → `Stock Entry (Manufacture)` sinh `Batch` mới tự động (naming series theo cấu hình) → `Quality Inspection` (gắn Batch) → `Delivery Note`/`Sales Invoice` (chọn đúng Batch khi xuất bán, có thể theo FIFO/FEFO).

#### Flow chi tiết

```
BƯỚC 1: Cấu hình Item "Thuốc giảm đau P500":
         ☑ Has Batch No = 1
         ☑ Create New Batch = 1 (tự tạo mã lô khi sản xuất)
         Batch Naming Series: "LOT-.YYYY.-.#####"

BƯỚC 2: Work Order SX 50,000 viên → Stock Entry "Manufacture"
         → hệ thống tự sinh Batch "LOT-2026-00012" gắn Manufacturing Date = hôm nay,
           Expiry Date = hôm nay + 24 tháng (theo cấu hình shelf life của Item)

BƯỚC 3: Quality Inspection bắt buộc trước khi Batch chuyển trạng thái "Sẵn sàng bán"
         → QC kiểm nghiệm mẫu → Pass/Fail → nếu Fail: Batch bị giữ (hold), tạo Stock Entry
           "Material Consumption"/hủy lô, ghi nhận phế phẩm

BƯỚC 4: Khi bán hàng, Delivery Note chọn Batch theo nguyên tắc FEFO (First Expiry First Out)
         → hệ thống có thể tự gợi ý Batch gần hết hạn nhất để xuất trước (qua Batch-wise valuation)

BƯỚC 5: Truy vết ngược (traceability): từ Batch thành phẩm → xem lại Stock Entry Manufacture gốc
         → biết chính xác Batch NVL đầu vào nào đã được dùng (nếu NVL cũng quản lý theo Batch)
         → phục vụ thu hồi sản phẩm (recall) khi cần
```

#### Ví dụ minh họa
Nhà máy dược phẩm sản xuất lô thuốc P500:
- Batch "LOT-2026-00012": SX 50,000 viên ngày 20/07/2026, HSD 20/07/2028.
- QC lấy mẫu kiểm nghiệm hàm lượng hoạt chất → Pass.
- 3 tháng sau phát hiện 1 lô NVL hoạt chất bị lỗi (từ NCC X) → truy vết ngược: Batch nào dùng NVL lô lỗi đó → chỉ thu hồi đúng "LOT-2026-00012", không ảnh hưởng các lô khác.

#### Điểm mạnh
- ✅ Truy vết chính xác 100% theo lô — bắt buộc với ngành có quy định pháp lý nghiêm (Dược, Thực phẩm).
- ✅ Quản lý hạn sử dụng, giảm rủi ro bán hàng hết hạn (FEFO).
- ✅ Hỗ trợ thu hồi sản phẩm (recall) nhanh, khoanh vùng chính xác.

#### Hạn chế
- ❌ Tăng khối lượng dữ liệu quản lý (mỗi lô là 1 record `Batch`).
- ❌ Yêu cầu kỷ luật nhập liệu cao (đúng Batch, đúng NVL nguồn) — nếu nhân viên nhập sai sẽ mất ý nghĩa truy vết.
- ❌ Có thể làm chậm thao tác xuất kho nếu không tự động hóa gợi ý FEFO.

---

### 3.7 SUBCONTRACTING / JOB WORK — Gia công thuê ngoài

#### Định nghĩa
Doanh nghiệp giao **NVL/bán thành phẩm** cho **Nhà cung cấp gia công (Subcontractor)** để họ thực hiện 1 phần/toàn bộ công đoạn sản xuất, sau đó nhận lại thành phẩm/bán thành phẩm.

#### Đặc điểm (kiến trúc mới từ v14/v15/v16 — khác hẳn v13 trở về trước)
- Không còn dùng `Purchase Receipt` với BOM đính kèm đơn giản như bản cũ, mà qua luồng chuyên biệt: `Subcontracting Order` → `Subcontracting Receipt`.
- `Purchase Order` cần bật cờ `Is Subcontracted = 1`.
- Cần khai báo **Service Item** (đại diện cho phí gia công) và **BOM** áp dụng cho từng thành phẩm gia công.

#### Doctype liên quan
`Item` (Finished Good gắn `default_bom`, cờ cho phép subcontract) → `Purchase Order` (is_subcontracted) → `Subcontracting Order` → `Stock Entry (Send to Subcontractor)` xuất NVL đến kho ảo của NCC (Supplier Warehouse) → NCC gia công → `Subcontracting Receipt` (nhận lại thành phẩm + tự động tiêu hao NVL đã giao theo BOM) → `Purchase Invoice` (thanh toán phí gia công).

#### Flow chi tiết

```
BƯỚC 1: Tạo Purchase Order cho NCC gia công "Công ty May X"
         ☑ Is Subcontracted = 1
         Item: "Áo sơ mi thành phẩm Model C" x 2,000 cái, BOM = "BOM-AoSoMi-C-001"
         (BOM này gồm: Vải, Chỉ, Cúc áo, Nhãn mác — nguyên liệu DN tự cấp cho NCC)

BƯỚC 2: Purchase Order → "Create Subcontracting Order"
         → Subcontracting Order thể hiện rõ NVL cần giao (Supplied Items) dựa theo BOM x Qty đặt

BƯỚC 3: Từ Subcontracting Order → tạo Stock Entry "Send to Subcontractor"
         → Xuất kho: 2,000m vải + 4,000 cuộn chỉ + 2,000 bộ cúc... chuyển đến
           "Kho ảo của Công ty May X" (Supplier Warehouse) — vẫn thuộc sở hữu DN, chỉ đổi vị trí

BƯỚC 4: NCC tiến hành gia công (ngoài hệ thống ERPNext của DN, hoặc NCC có thể có
         Subcontracting Portal riêng nếu tích hợp)

BƯỚC 5: Nhận hàng về → tạo Subcontracting Receipt
         → Nhập kho 2,000 áo sơ mi thành phẩm vào kho DN
         → Hệ thống TỰ ĐỘNG trừ tương ứng NVL đã giao (theo BOM) khỏi kho ảo NCC
         → Ghi nhận thêm phí gia công (Service Cost) vào giá vốn thành phẩm

BƯỚC 6: Purchase Invoice thanh toán phí gia công cho NCC (chỉ trả tiền công, không trả tiền NVL vì DN tự cấp)
```

#### Ví dụ minh họa
Doanh nghiệp may mặc thuê "Công ty May X" gia công 2,000 áo sơ mi:
- DN tự cấp vải + phụ liệu (đã mua sẵn tồn kho), chỉ trả phí công may 25,000đ/áo = 50 triệu VNĐ.
- Subcontracting Order: 2,000 áo, BOM tiêu hao 1.5m vải/áo → xuất 3,000m vải cho NCC.
- Sau 15 ngày, Subcontracting Receipt nhận 1,980 áo hoàn thiện (20 áo lỗi hỏng, được ghi nhận riêng phần chênh lệch NVL hao hụt).
- Giá vốn 1 áo = (Giá vải + phụ liệu phân bổ theo BOM) + (50 triệu / 1,980 áo phí gia công).

#### Điểm mạnh
- ✅ Tận dụng năng lực bên ngoài mà **không cần đầu tư máy móc/nhân công cố định**.
- ✅ Vẫn kiểm soát được NVL (vì DN tự cấp), quản lý tồn kho "ảo" tại NCC minh bạch, tách biệt Purchase Order thường và gia công.
- ✅ Linh hoạt mở rộng công suất theo mùa vụ (peak season) mà không tăng biên chế.

#### Hạn chế
- ❌ Kiến trúc `Subcontracting Order/Receipt` (v14+) **phức tạp hơn** nhiều so với Purchase Order thông thường — đội ngũ vận hành cần đào tạo kỹ.
- ❌ Khó kiểm soát chất lượng quy trình tại NCC (chỉ kiểm tra đầu ra qua Quality Inspection, không thấy công đoạn nội bộ NCC).
- ❌ Rủi ro thất thoát/gian lận NVL nếu không đối chiếu tồn kho ảo NCC định kỳ (backflush sai NVL tiêu hao thực tế).

---

### 3.8 PROCESS MANUFACTURING — Sản xuất theo quy trình liên tục/hỗn hợp

#### Định nghĩa
Khác với "Discrete Manufacturing" (sản xuất rời rạc, đếm được từng đơn vị: cái, chiếc), **Process Manufacturing** áp dụng cho ngành sản xuất theo **công thức pha trộn/phản ứng hóa học/nhiệt** — đầu ra không cố định tỷ lệ 1:1 với đầu vào (VD: hóa chất, thực phẩm chế biến, sơn, phân bón).

> Lưu ý: ERPNext **không có module Process Manufacturing chuyên biệt** như SAP PP-PI, nhưng có thể **mô phỏng** bằng cách kết hợp: BOM (Type = "Manufacture"), tỷ lệ hao hụt (Scrap Item), Batch, và Stock Entry loại "Manufacture" với hệ số quy đổi linh hoạt.

#### Đặc điểm
- BOM có thể khai báo `Process Loss (%)` hoặc dùng `BOM Scrap Item` để phản ánh hao hụt tự nhiên trong phản ứng/pha trộn.
- Đầu ra có thể là **nhiều sản phẩm đồng thời (Co-product/By-product)** — ERPNext hỗ trợ khai báo nhiều Item đầu ra trong 1 Stock Entry Manufacture (không giới hạn 1 BOM = 1 sản phẩm chính).
- Công thức (Formula) thường thay đổi theo lô nguyên liệu đầu vào (VD: độ ẩm gỗ, độ tinh khiết hóa chất) → cần điều chỉnh BOM linh hoạt trước mỗi lô SX (dùng "BOM Update Tool" hoặc tạo BOM version mới).

#### Doctype liên quan
`BOM` (với `Scrap Items`, `Process Loss Percentage`) → `Work Order` → `Stock Entry (Manufacture)` khai báo **nhiều dòng Item đầu ra** (sản phẩm chính + phụ phẩm) → `Batch` (bắt buộc để truy vết công thức đã dùng) → `Quality Inspection` (kiểm tra thông số hóa lý sau phản ứng).

#### Flow chi tiết

```
BƯỚC 1: Khai báo BOM "Sơn nước ngoại thất - Trắng":
         NVL: Nhựa Acrylic 40%, Bột màu TiO2 15%, Nước 30%, Phụ gia 15%
         Scrap/Process Loss: 2% (hao hụt bay hơi trong quá trình khuấy trộn nhiệt)

BƯỚC 2: Work Order SX theo mẻ (batch) 1,000 lít
         → Stock Entry "Material Transfer for Manufacture": xuất đúng tỷ lệ NVL cho mẻ

BƯỚC 3: Quy trình pha trộn thực tế (ngoài hệ thống): khuấy, gia nhiệt, kiểm tra độ nhớt

BƯỚC 4: Stock Entry "Manufacture" ghi nhận SẢN LƯỢNG THỰC TẾ (có thể lệch do hao hụt):
         Sản phẩm chính: 978 lít Sơn Trắng thành phẩm (Batch "SON-2026-0088")
         Phụ phẩm/By-product (nếu có): cặn sơn tái chế 5kg
         → Hệ thống backflush NVL theo BOM, phần chênh lệch (2%) được ghi nhận hao hụt

BƯỚC 5: Quality Inspection: đo độ nhớt, độ phủ, độ bóng → Pass → Batch được phép xuất bán
```

#### Ví dụ minh họa
Nhà máy sơn sản xuất mẻ sơn trắng ngoại thất 1,000 lít:
- Đầu vào: 400L Nhựa Acrylic + 150kg TiO2 + 300L nước + 150kg phụ gia.
- Sau khuấy trộn, hao hụt bay hơi 2% → thực tế thu được 978 lít thành phẩm + 5kg cặn tái chế bán phế liệu.
- Batch "SON-2026-0088" ghi nhận công thức đã dùng, phục vụ đối chiếu khi có khiếu nại chất lượng.

#### Điểm mạnh
- ✅ Linh hoạt ghi nhận sản lượng thực tế khác với kế hoạch (phản ánh đúng bản chất phản ứng/pha trộn).
- ✅ Hỗ trợ đa sản phẩm đầu ra (Co-product/By-product) trong cùng 1 lần SX.
- ✅ Kết hợp Batch + Quality Inspection đảm bảo kiểm soát công thức & chất lượng.

#### Hạn chế
- ❌ ERPNext **không có sẵn** công cụ tính công thức động (formula scaling) theo % nguyên liệu như phần mềm PP-PI chuyên dụng — phải tùy biến qua Custom Script/App riêng nếu quy trình phức tạp.
- ❌ Không hỗ trợ tốt "Recipe Management" với nhiều phiên bản công thức thử nghiệm (cần thêm Doctype tùy chỉnh nếu R&D nhiều).
- ❌ Quản lý hao hụt/phế phẩm động (biến thiên theo lô) yêu cầu kỷ luật ghi nhận cao, dễ sai lệch giá thành nếu không chuẩn hóa quy trình QC.

---

## 4. BẢNG SO SÁNH TỔNG HỢP

| Tiêu chí | MTS | MTO | ATO | ETO | Repetitive | Batch | Subcontracting | Process |
|---|---|---|---|---|---|---|---|---|
| **Kích hoạt SX** | Dự báo/tồn kho | Sales Order | Sales Order (lắp ráp) | Thiết kế → BOM riêng | Kế hoạch liên tục | Kế hoạch theo lô | Purchase Order gia công | Kế hoạch mẻ (batch công thức) |
| **Lead time giao hàng** | Rất ngắn | Dài | Ngắn | Rất dài | Ngắn (liên tục) | Trung bình | Phụ thuộc NCC | Trung bình |
| **Tồn kho thành phẩm** | Cao | Thấp/không | Thấp (chỉ tồn linh kiện) | Không | Cao (theo ca) | Theo lô, có HSD | Không (gia công hộ) | Theo mẻ |
| **Mức độ tùy biến SP** | Thấp | Trung bình | Cao | Rất cao (độc nhất) | Thấp | Trung bình | Theo yêu cầu DN | Trung bình |
| **Doctype đặc trưng** | Production Plan, Work Order | Sales Order↔Work Order | Multi-level BOM, Item Variant | Project, Task, BOM riêng | Work Order (Qty lớn), Backflush | Batch, Quality Inspection | Subcontracting Order/Receipt | BOM Scrap Item, Batch |
| **Độ phức tạp cấu hình** | Thấp | Trung bình | Cao | Cao | Trung bình | Trung bình | Cao | Cao |
| **Rủi ro chính** | Tồn kho ứ đọng | Chậm giao hàng | Sai lệch dự báo linh kiện | Báo giá sai, kéo dài dự án | Sai lệch backflush | Sai sót truy vết lô | Thất thoát NVL tại NCC | Sai lệch công thức/hao hụt |
| **Ngành phù hợp** | FMCG, linh kiện phổ thông | Nội thất đặt riêng, cơ khí vừa | Điện tử, xe cộ, nội thất module | Cơ khí công trình, máy đặc chủng | Đồ uống, bao bì, điện tử lắp nhanh | Dược, thực phẩm, mỹ phẩm | Dệt may, da giày, gia công cơ khí | Hóa chất, sơn, thực phẩm chế biến |

---

## 5. ĐỀ XUẤT PHƯƠNG ÁN KẾT HỢP MÔ HÌNH

Trong thực tế, **rất ít doanh nghiệp chỉ dùng 1 mô hình thuần túy**. Dưới đây là 3 phương án kết hợp phổ biến nhất khi triển khai ERPNext v16, kèm flow chi tiết.

---

### 5.1 PHƯƠNG ÁN A: MTS (linh kiện) + ATO (thành phẩm) + Subcontracting (1 số công đoạn)

**Bối cảnh áp dụng**: Doanh nghiệp sản xuất điện tử/nội thất module, có nhiều biến thể sản phẩm cuối, đồng thời thuê ngoài 1 số công đoạn không phải năng lực lõi (VD: sơn tĩnh điện, ép nhựa).

```
[Kế hoạch định kỳ] 
     │
     ▼
Production Plan (MTS) ──> Work Order SX các CỤM LINH KIỆN chính
     │                              │
     │                              ▼
     │                     1 số công đoạn giao gia công ngoài:
     │                     Purchase Order (is_subcontracted) ──> Subcontracting Order
     │                     ──> Stock Entry (Send to Subcontractor) ──> Subcontracting Receipt
     │                     ──> Nhập kho cụm linh kiện đã gia công (VD: khung đã sơn tĩnh điện)
     │                              │
     ▼                              ▼
   Kho Sub-assembly (tồn kho sẵn sàng, kết hợp cả SX nội bộ + gia công ngoài)
     │
     ▼
[Khách đặt hàng – Sales Order chọn cấu hình] ──> Production Plan (Get Items From = Sales Order)
     │
     ▼
Work Order LẮP RÁP (ATO) ──> Stock Entry Material Transfer (xuất Sub-assembly có sẵn)
     │
     ▼
Job Card "Lắp ráp hoàn thiện" ──> Stock Entry Manufacture ──> Quality Inspection
     │
     ▼
Delivery Note giao khách (lead time ngắn)
```

**Lợi ích kết hợp**: Vừa tận dụng thuê ngoài để giảm đầu tư máy móc công đoạn phụ (sơn, ép nhựa), vừa giữ tồn kho linh hoạt ở cấp linh kiện (không tồn thành phẩm cuối đắt tiền), vừa đáp ứng nhanh đơn hàng tùy biến.

**Lưu ý triển khai**: Cần đồng bộ `Warehouse` giữa kho SX nội bộ và kho nhận hàng gia công về để Production Plan tính đúng tồn kho khả dụng khi lập kế hoạch ATO.

---

### 5.2 PHƯƠNG ÁN B: ETO (giai đoạn đầu dự án) → chuyển sang MTO/Repetitive (giai đoạn nhân rộng)

**Bối cảnh áp dụng**: Doanh nghiệp cơ khí/công nghiệp phát triển sản phẩm mới theo đơn đặt hàng đầu tiên (thiết kế riêng), sau khi sản phẩm ổn định và có đơn hàng lặp lại → chuyển sang sản xuất hàng loạt.

```
GIAI ĐOẠN 1 - SẢN PHẨM MẪU (ETO):
Sales Order (đơn đầu tiên) ──> Project ──> Task (thiết kế, thử nghiệm)
     ──> BOM "BOM-SP-MOI-v1" (tạo mới, gắn Project)
     ──> Work Order thử nghiệm ──> SX mẫu, kiểm tra chất lượng, hiệu chỉnh thiết kế
     ──> BOM được CHUẨN HÓA (Update Tool) thành "BOM-SP-MOI-STANDARD"
                       │
                       ▼ (Khi khách đặt lại số lượng lớn hoặc SP được đưa vào danh mục bán chuẩn)
GIAI ĐOẠN 2 - NHÂN RỘNG (chuyển sang MTO hoặc Repetitive tùy sản lượng):
     Item được gỡ liên kết Project, dùng "BOM-SP-MOI-STANDARD" làm default_bom
     ──> Production Plan (Get Items From = Sales Order, không cần Project nữa)
     ──> Work Order thông thường (MTO nếu đơn lẻ, hoặc Repetitive nếu đơn hàng lặp lại đều đặn)
     ──> Backflush đơn giản hóa, không còn phát sinh chi phí thiết kế lặp lại
```

**Lợi ích kết hợp**: Tránh lãng phí thời gian thiết kế lại cho mỗi đơn hàng lặp lại; đồng thời vẫn giữ được lịch sử Project của sản phẩm mẫu ban đầu để tham chiếu kỹ thuật/cải tiến sau này.

**Lưu ý triển khai**: Cần quy trình rõ ràng về "tiêu chí chuyển pha" (VD: sau 3 đơn hàng lặp lại cùng cấu hình → được chuẩn hóa BOM), tránh tình trạng BOM dự án bị dùng mãi cho SX đại trà gây khó truy vết chi phí.

---

### 5.3 PHƯƠNG ÁN C: Batch Manufacturing + Subcontracting + Process Manufacturing (ngành Dược/Mỹ phẩm/Thực phẩm)

**Bối cảnh áp dụng**: Doanh nghiệp dược/mỹ phẩm tự pha chế công thức (Process) nhưng thuê ngoài công đoạn đóng gói/dập viên (Subcontracting), toàn bộ vẫn phải truy vết theo Batch tuân thủ quy định (GMP).

```
BƯỚC 1: Pha chế công thức (Process Manufacturing – nội bộ)
   BOM "Kem dưỡng da công thức F12" ──> Work Order SX mẻ 500kg bán thành phẩm (bulk)
   ──> Stock Entry Manufacture ──> Batch "BULK-2026-0034" (bán thành phẩm dạng khối,
       chưa đóng tuýp) ──> Quality Inspection (kiểm tra pH, độ nhớt) ──> Pass

BƯỚC 2: Gia công đóng gói (Subcontracting)
   Purchase Order (is_subcontracted, NCC = "Công ty Đóng gói Y")
   ──> Subcontracting Order: giao 500kg bulk (Batch BULK-2026-0034) + vỏ tuýp + hộp giấy
   ──> Stock Entry (Send to Subcontractor)
   ──> NCC đóng gói thành 10,000 tuýp kem 50g
   ──> Subcontracting Receipt: nhận về 10,000 tuýp, hệ thống SINH BATCH MỚI cho thành phẩm
       "FIN-2026-0155", đồng thời LIÊN KẾT ngược về Batch bulk gốc "BULK-2026-0034"
       (đảm bảo truy vết đầy đủ 2 cấp: bulk → thành phẩm đóng gói)

BƯỚC 3: Quality Inspection lần 2 cho thành phẩm đóng gói cuối cùng (kiểm tra bao bì, hạn sử dụng in ấn)
   ──> Pass ──> Batch "FIN-2026-0155" được phép nhập kho bán ra thị trường

BƯỚC 4: Khi bán hàng, Delivery Note xuất theo FEFO
   Nếu có khiếu nại/thu hồi ──> truy vết ngược: Tuýp lỗi ──> Batch FIN-2026-0155
   ──> Batch bulk gốc BULK-2026-0034 ──> xác định đúng mẻ pha chế + NCC đóng gói liên quan
```

**Lợi ích kết hợp**: Đáp ứng yêu cầu pháp lý truy vết 2 cấp (bulk + thành phẩm) trong khi vẫn tận dụng được năng lực đóng gói chuyên nghiệp của đối tác ngoài mà không cần đầu tư dây chuyền đóng gói riêng.

**Lưu ý triển khai**: Bắt buộc cấu hình `Has Batch No` cho CẢ Item bán thành phẩm (bulk) LẪN Item thành phẩm cuối; đồng thời huấn luyện kỹ nhân viên kho khi tạo Subcontracting Receipt phải chọn đúng Batch bulk đã gửi đi, tránh nhầm lẫn giữa các mẻ pha chế khác nhau.

---

## 6. CẤU HÌNH HỆ THỐNG LIÊN QUAN

Truy cập: **Manufacturing → Manufacturing Settings**

| Thiết lập | Ảnh hưởng đến mô hình |
|---|---|
| `Material Consumption for Manufacture` | Cho phép ghi nhận tiêu hao NVL độc lập với hoàn tất SX — hữu ích cho Repetitive & Process |
| `Backflush Raw Materials Based On` (BOM / Material Transferred) | Repetitive Manufacturing nên chọn "BOM" để tự động tính theo định mức chuẩn |
| `Yêu cầu Job Card cho từng Operation` (`Add Corresponding Row in Job Card`) | MTS/MTO/ETO nên bật để theo dõi tiến độ chi tiết; Repetitive có thể tắt bớt để đơn giản hóa |
| `Capacity Planning` | Quan trọng khi nhiều Work Order tranh chấp cùng 1 Workstation (mọi mô hình discrete) |
| `Overproduction Percentage` | Cho phép SX vượt kế hoạch X% — cần thiết cho Process Manufacturing (hao hụt/dư biến động) |
| `Default Warehouses` (WIP/FG/Scrap) | Nên tách riêng theo mô hình: kho WIP riêng cho ATO (sub-assembly), kho Batch riêng cho ngành Dược |
| `Set Default Basic Rate in Transfer Entries` | Ảnh hưởng chính xác giá thành khi kết hợp nhiều nguồn NVL (nội bộ + gia công ngoài) |

---

## 7. KHUYẾN NGHỊ TRIỂN KHAI

| Quy mô/Ngành | Mô hình chính đề xuất | Ghi chú |
|---|---|---|
| DN nhỏ, sản phẩm đơn giản, ít biến thể | MTS thuần | Đơn giản hóa vận hành, ưu tiên tốc độ giao hàng |
| DN vừa, sản phẩm có tùy biến vừa phải (nội thất, cơ khí đơn giản) | MTO hoặc MTO + Subcontracting | Kiểm soát vốn lưu động tốt hơn MTS |
| DN điện tử/xe cộ/nội thất module, nhiều biến thể | ATO + MTS (linh kiện) | Cân bằng tốc độ – tùy biến |
| DN cơ khí công trình, máy đặc chủng | ETO, tích hợp chặt Project | Bắt buộc dùng Project để kiểm soát chi phí thiết kế |
| Dây chuyền tốc độ cao (đồ uống, bao bì) | Repetitive Manufacturing | Giảm tải thao tác, tối ưu backflush |
| Dược phẩm/Mỹ phẩm/Thực phẩm | Batch + Process (+ Subcontracting nếu thuê đóng gói) | Bắt buộc truy vết theo quy định pháp lý |
| Dệt may/Da giày | MTO + Subcontracting | Tận dụng năng lực gia công vệ tinh |

---

## 8. CHECKLIST TRIỂN KHAI THỰC TẾ

- [ ] Xác định rõ **mô hình chính** áp dụng cho từng nhóm sản phẩm (không áp 1 mô hình cho toàn bộ danh mục).
- [ ] Chuẩn hóa **BOM** trước khi go-live (đặc biệt với BOM nhiều cấp cho ATO).
- [ ] Thiết lập đúng **Workstation/Workstation Type** và giờ làm việc thực tế để Capacity Planning chính xác.
- [ ] Với ngành có quy định pháp lý (Dược, Thực phẩm): bật `Has Batch No`, thiết kế Naming Series Batch chuẩn ngay từ đầu — **không đổi giữa chừng** vì ảnh hưởng truy vết lịch sử.
- [ ] Với Subcontracting: đào tạo kỹ nhân viên kho về `Subcontracting Order` vs `Subcontracting Receipt` (khác biệt lớn so với quy trình mua hàng thông thường).
- [ ] Với ETO: quy định rõ **tiêu chí chuyển từ Project-based BOM sang BOM chuẩn hóa** để tránh trùng lặp/khó truy vết chi phí.
- [ ] Kiểm thử kỹ **Backflush** (Repetitive/Process) trên dữ liệu thật trước khi go-live diện rộng — sai định mức BOM sẽ gây sai lệch giá thành hàng loạt.
- [ ] Thiết lập báo cáo giám sát: **Production Plan vs Actual**, **Work Order Cost vs BOM Cost**, **OEE (Downtime Entry)** để đánh giá hiệu quả sau triển khai.

---

*Tài liệu này tổng hợp dựa trên kiến trúc chuẩn của ERPNext/Frappe v16 (Manufacturing module). Khi triển khai thực tế, nên đối chiếu thêm với phiên bản cụ thể trong môi trường (Site) đang sử dụng vì một số nhãn trường (field label) hoặc cờ cấu hình có thể được đặt tên khác nhau giữa các bản vá (patch) trong cùng version 16.*
