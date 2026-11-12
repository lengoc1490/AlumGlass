# ĐỀ XUẤT GIẢI PHÁP — KIỂM SOÁT LỢI NHUẬN CÔNG TRÌNH NHÔM KÍNH

> Bản đề xuất để ra quyết định. Thay thế cách tiếp cận trong `gia-ban-gia-dinh-muc-thuc-te.md`,
> dựa trên phản biện `PHAN-BIEN-gia-thanh-3-lop.md` và cơ chế `GIAI-THICH-LOP-S-VA-MAPPING.md`.
> Mục tiêu do Owner xác định: **quản trị tức thời** — biết rủi ro và lợi nhuận dự kiến ngay bây giờ,
> dùng thực tế để hiệu chỉnh định mức.

---

## 1. TÓM TẮT ĐỀ XUẤT

### Vấn đề thật

Không phải "cần một hệ thống giá thành 3 lớp". Vấn đề là: **công ty ký giá bán trước, mua vật tư sau,
và trong khoảng giữa hai việc đó không ai biết mình đang lãi hay lỗ.**

Với biên lợi nhuận 8–15% và nhôm chiếm ~45% giá thành, một cú tăng giá nhôm 10% xoá sạch 4,5 điểm
biên. Doanh nghiệp hiện chỉ biết điều đó **sau khi công trình xong** — quá muộn để làm gì.

### Giải pháp

Một **vòng điều khiển lợi nhuận**, không phải một hệ thống báo cáo:

```
   S_live  ──►  quyết định hôm nay (nhận đơn? mua ngay? cảnh báo?)
     │
     ▼
  S_release  ──►  vận hành  ──►  A (thực tế)
                                    │
                                    ▼
                        tách chênh lệch → chỉ hiệu chỉnh ĐỊNH MỨC LƯỢNG
                        (nhắm P20 — mức tốt nhất đạt được, không phải trung bình)
                                    │
                                    └──►  S_live kỳ sau chính xác hơn
```

### Ba câu hệ thống trả lời

| Thời điểm | Câu hỏi | Trả lời bằng |
|---|---|---|
| Trước khi ký | "Ký giá này lãi bao nhiêu, rủi ro ở đâu?" | **S_live** + độ nhạy giá |
| Trong khi làm | "Đang lãi hay đang lỗ?" | **Tiến độ chi phí vs tiến độ khối lượng** |
| Sau khi xong | "Vì sao lệch, lần sau định mức thế nào?" | **A − S_release** tách 4 thành phần → hiệu chỉnh |

### Điều khác biệt cốt lõi so với thiết kế cũ

Thiết kế cũ xây **một hệ thống thứ hai** để tính giá thành, song song với engine BOM đã có.
Đề xuất này **thêm một bộ đơn giá thứ hai lên hệ thống đã có** — vì tầng số lượng đã tồn tại đầy đủ
trong `al_bom_result` (`bom_orchestrator.py:2253`: `total_qty` đã gồm hao hụt, `cost_bucket` đã có,
`trace` đã ghi công thức).

Kết quả: ít hơn khoảng **60–70% code**, không có hai nguồn sự thật cho cùng một số lượng, và S_live
cập nhật **gần như miễn phí** vì chỉ nhân lại chứ không chạy lại BOM.

---

## 2. SẢN PHẨM BÀN GIAO — BỐN THỨ NGƯỜI DÙNG THẤY

### ① Thẻ lợi nhuận đơn hàng (trên từng dòng Sales Order)

```
┌──────────────────────────────────────────────────────────────┐
│  SO-2026-0042 · P-HN-0042 · Cửa đi 2 cánh CDMQ-2C · 5 bộ    │
├──────────────────────────────────────────────────────────────┤
│   Doanh thu        Chi phí dự kiến      Lãi dự kiến          │
│   119,3 tr         94,3 tr              25,0 tr              │
│                                         biên 21,0%  ●        │
├──────────────────────────────────────────────────────────────┤
│   Độ nhạy:  nhôm +10%  →  biên −4,6 điểm  (còn 16,4%)        │
│   Vật tư:   ████████░░  78% đã chốt giá, 22% đang phơi       │
│   ⚠ 2 dòng chưa có giá vốn — đang dùng giá ước               │
├──────────────────────────────────────────────────────────────┤
│  Nhóm           Định mức    Hiện tại    Lệch      Nguồn giá   │
│  Nhôm           42,7 tr     44,2 tr     +3,5%     giá vốn lô  │
│  Kính           23,7 tr     26,1 tr    +10,2%     HĐ gia công │
│  Phụ kiện        8,9 tr      9,2 tr     +4,1%     giá vốn     │
│  Nhân công SX    5,7 tr      6,0 tr     +5,3%     định mức    │
│  Lắp đặt         4,7 tr      4,8 tr     +2,1%     HĐ đội      │
│  Chung + DP      3,7 tr      3,9 tr     +5,4%     phân bổ     │
│  ─────────────────────────────────────────────────────────   │
│  Giá thành      89,4 tr     94,3 tr     +5,5%                 │
└──────────────────────────────────────────────────────────────┘
```

Nút: `Tính lại` · `Xem cấu trúc` (drill từng dòng vật tư + công thức) · `Khoá kế hoạch` (= Release)

### ② Bảng phơi rủi ro — màn hình của BGĐ

| Công trình | Doanh thu đã chốt | Chi phí đã chốt | **Chi phí đang phơi** | Biên hiện tại | Biên nếu nhôm +10% |
|---|---:|---:|---:|---:|---:|
| P-HN-0042 | 119,3 | 73,6 | **20,7** | 21,0% | 16,4% |
| P-HN-0051 | 86,0 | 12,0 | **58,2** | 14,2% | **8,1%** ⚠ |
| … | | | | | |
| **Tổng** | **1.842** | **1.105** | **612** | 16,8% | **12,4%** |

Hai con số cần nhìn mỗi tuần: **tổng tiền đang phơi** và **biên nếu giá nhôm +10%**.
Đây là con số trả lời "công ty đang rủi ro bao nhiêu vì giá vật tư" — thiết kế cũ không có.

### ③ So sánh kế hoạch vs thực tế (theo công trình)

| Nhóm | S_release | A thực tế | Lệch | Giá | Lượng | Hiệu suất |
|---|---:|---:|---:|---:|---:|---:|
| Nhôm | 42,7 | 44,2 | +1,5 | +0,7 | +0,8 | — |
| Kính | 23,7 | 26,1 | +2,4 | +0,2 | +2,2 | — |
| Nhân công SX | 5,7 | 6,7 | +1,0 | +0,3 | — | +0,7 |
| Làm lại | 1,4 (DP) | 3,2 | +1,8 | — | — | — |
| … | | | | | | |

Mỗi ô lệch **bấm vào được để xem chứng từ nguồn**. Cột "Làm lại" là dòng riêng, không giấu trong vật tư.

### ④ Báo cáo hiệu chỉnh định mức — vòng học

| Loại sản phẩm | Chỉ tiêu | Định mức (P20) | Thực tế (median) | Khoảng cách | Xu hướng |
|---|---|---:|---:|---:|---|
| Cửa đi 2 cánh | Hao hụt nhôm | 11,5% | 14,2% | **+2,7 đ** | ↑ xấu |
| Cửa đi 2 cánh | Giờ lắp ráp / bộ | 5,0 h | 5,8 h | +0,8 h | → |
| Vách kính | Hao hụt kính | 0%¹ | 4,1% | +4,1 đ | ↑ xấu |
| Vách kính | Giờ lắp kính / bộ | 2,4 h | 2,3 h | −0,1 h | ↓ tốt |

¹ kính mua gia công cắt sẵn ⇒ định mức 0; hao hụt thực tế = **vỡ / sai kích thước**, phải xử lý ở vận hành.

**Định mức tiến về P20 (mức 20% đơn tốt nhất), không tiến về median.** Xem §8.2 — đây là điều
quan trọng nhất trong toàn bộ đề xuất.

---

## 3. MÔ HÌNH VẬN HÀNH — NĂM NGHI THỨC QUẢN TRỊ

Hệ thống chỉ có giá trị nếu nó gắn vào nhịp làm việc. Năm nghi thức:

| Nhịp | Ai | Xem gì | Quyết định gì |
|---|---|---|---|
| **Khi báo giá** | Kinh doanh + BGĐ | Biên dự kiến, độ nhạy giá | Chốt giá / thêm dự phòng / từ chối |
| **Thứ Hai hằng tuần** | BGĐ + Mua hàng | Bảng phơi rủi ro | Mua chốt giá trước hay chờ; đơn nào cần đàm phán lại |
| **Khi thả sản xuất** | Quản lý SX | S_release, định mức giờ công | Duyệt kế hoạch / yêu cầu xem lại |
| **Hằng tháng** | Kế toán + QL dự án | So sánh S_release vs A | Xác nhận số, tìm nguyên nhân lệch |
| **Hằng quý** | BGĐ + Kỹ thuật + SX | Báo cáo hiệu chỉnh | Duyệt định mức mới, đặt mục tiêu giảm hao hụt |

**Nếu công ty không cam kết được nghi thức "thứ Hai" và "hằng quý", đừng làm hệ thống này.**
Nó sẽ có dữ liệu nhưng không ai dùng — đó là kịch bản thất bại phổ biến nhất.

---

## 4. KIẾN TRÚC KỸ THUẬT

### 4.1 Ba tầng, một engine

```
TẦNG 1 — LƯỢNG          (đã có, không xây lại)
  BomOrchestrator B0–B5  →  lines[]: net_qty, gross_qty, cost_bucket, trace
  + ScrapResolver        →  hao hụt theo profile
  →  structure_json

TẦNG 2 — ĐƠN GIÁ         (mới, nhỏ)
  PriceResolver          →  giá theo profile + trạng thái mua (chưa mua/đã PO/đã nhập)

TẦNG 3 — TỔNG HỢP        (đã có)
  AL Cost Template       →  bucket → nhóm → giá thành
```

`S_live` và `S_release` = **cùng structure_json × hai bộ đơn giá**.
Đổi giá ⇒ chỉ chạy tầng 2 + 3. Không chạy lại BOM. Không revision.

### 4.2 Phân tách `compute` khỏi `persist` (bắt buộc làm trước)

`b7_save_results()` hiện gọi `frappe.db.commit()` (`bom_orchestrator.py:2635`) và ghi thẳng vào
`Quotation Item`. Trước khi tái dùng cho Sales Order phải:

1. Bỏ `frappe.db.commit()` khỏi engine — nếu không sẽ commit giữa transaction `Sales Order.on_submit`.
2. Tách `compute()` trả về `CostResult` thuần dữ liệu, và `persist()` ghi DB riêng.
3. Tổng quát hoá `_qi_doc` (9 chỗ) thành `source_doc` để nhận cả Quotation Item và Sales Order Item.

Đây là **Pha 0** — không thấy được trên UI nhưng là điều kiện của mọi thứ sau.

### 4.3 Ranh giới với ERPNext — không làm lại cái core đã làm

| Việc | Ai làm |
|---|---|
| BOM động theo kích thước, hao hụt, định mức công | **AlumGlass** |
| Dự báo chi phí sống, độ nhạy, phơi rủi ro | **AlumGlass** |
| Hiệu chỉnh định mức từ thực tế | **AlumGlass** |
| BOM thực thi, Work Order, Job Card | **ERPNext** |
| Tồn kho, giá vốn, bút toán, dimension, P&L | **ERPNext** |
| Phân bổ chi phí chung, khoá kỳ | **ERPNext** (Journal Entry tay theo mẫu) |

**Không** xây engine sinh Journal Entry phân bổ trong giai đoạn này — rủi ro kiểm toán cao, giá trị
quản trị tức thời bằng 0.

---

## 5. MÔ HÌNH DỮ LIỆU

Năm DocType mới, ba mở rộng. Không có DocType nào trong danh sách "không xây" ở §9.

### 5.1 `AL Cost Profile` (mới — nhỏ, ~11 field)

| Field | Kiểu | Giá trị |
|---|---|---|
| `profile_code` | Data (unique) | `QUOTATION`, `STANDARD` |
| `cost_template` | Link AL Cost Template | |
| `price_basis` | Select | `SELLING_PRICE_LIST` / `VALUATION_RATE` / `LAST_PURCHASE_RATE` / `BUYING_PRICE_LIST` |
| `price_fallback_chain` | JSON | thứ tự dự phòng — **cấm rơi về 0** |
| `scrap_mode` | Select | `CATEGORY_DEFAULT` / `CUTTING_PLAN` / `FIXED_PCT` |
| `glass_purchase_mode` | Select | `PROCESSOR_CUT` (hao hụt 0) / `SHEET_NESTING` |
| `labor_mode` | Select | `PERCENT_OF_MATERIAL` / `OPERATIONS` / `PIECE_RATE` |
| `overhead_mode` | Select | `PERCENT` / `DRIVER_BASED` |
| `include_landed_cost` | Check | |
| `strict_errors` | Check | chặn khoá khi còn lỗi cứng |
| `is_default` | Check | |

### 5.2 `AL Cost Plan` (mới — một bản ghi / dòng Sales Order)

| Nhóm | Field |
|---|---|
| Khoá | `sales_order`, `sales_order_item`, `project`, `item_code`, `qty`, `product_type` |
| Nguồn | `al_bom`, `al_bom_version`, `config_snapshot`, `cost_profile` |
| **Cấu trúc** | `structure_json`, `structure_calculated_on`, `structure_trigger` |
| **S_live** | `live_amount`, `live_calculated_on`, `live_breakdown_json`, `live_errors_json`, `live_stale` |
| **S_release** | `release_amount`, `released_on`, `released_by`, `release_snapshot_json`, `status` |
| **Quản trị** | `revenue`, `margin`, `margin_pct`, `exposure_amount`, `risk_flags_json` |

`risk_flags_json`: `["MISSING_PRICE:2", "MARGIN_BELOW_10", "PRICE_EXPOSURE_HIGH"]` — để báo cáo lọc,
không phải quét lại.

### 5.3 `AL Cost Plan Line` (mới — bảng con, mục đích duy nhất: tra cứu)

| Field | Ghi chú |
|---|---|
| `plan`, `item_code` **(index)** | trả lời "giá mặt hàng này đổi → đơn nào bị ảnh hưởng" |
| `uom`, `net_qty`, `gross_qty`, `scrap_pct`, `scrap_source` | |
| `cost_bucket`, `last_price`, `last_price_source`, `price_status` | `UNPRICED` / `ESTIMATED` / `PO` / `RECEIVED` |

Không có bảng `buckets`, `operations`, `template_lines` — chúng nằm trong `structure_json`.
Đây là chỗ giảm mạnh nhất so với thiết kế cũ.

### 5.4 `AL Cost Standard` (mới — **nơi vòng học ghi vào**)

Thiết kế cũ **không có chỗ này**. Không có nó thì "hiệu chỉnh S" không có đích đến.

| Field | Ghi chú |
|---|---|
| `product_type`, `metric`, `scope_key` | vd `CDMQ-2C` · `SCRAP_NHOM` · `slug=khung_dung` |
| `standard_value` | **định mức đang áp dụng** (P20 đã duyệt) |
| `p20_value`, `median_value`, `sample_size`, `measured_period` | số đo để ra quyết định |
| `valid_from`, `valid_to`, `approved_by`, `approved_on`, `approval_note` | có hiệu lực + có người chịu trách nhiệm |
| `status` | `Draft` / `Active` / `Superseded` |

### 5.5 `AL Cost Fact` (mới — chi phí thực tế đã chuẩn hoá)

| Field | Ghi chú |
|---|---|
| `project`, `sales_order`, `period_from`, `period_to`, `posting_date` | khoá |
| `account`, `cost_bucket`, `cost_center`, `item_code` | |
| `qty`, `uom`, `amount`, `fact_type` | `DIRECT` / `ALLOCATED` / `VARIANCE` |
| **`is_measured`** | `1` = đọc từ sổ; `0` = suy luận từ rule. **Bắt buộc có** — xem §8.4 |
| `source_doctype`, `source_name`, `gl_entry` | truy ngược |
| `is_estimated`, `stale` | hàng giao thẳng, chứng từ lùi ngày |

**Grain là công trình, không phải dòng Sales Order.** Dòng SO là số phân bổ theo tỷ trọng định mức,
và phải ghi rõ điều đó trên báo cáo.

### 5.6 Mở rộng DocType có sẵn

| DocType | Thêm | Mục đích |
|---|---|---|
| **Sales Order Item** | `al_bom`, `al_bom_version`, `al_bom_vars`, `al_config_snapshot`, `al_cost_plan` | Giữ BOM qua SO. Kiểm chứng: `mapper.map_fields()` tự copy field trùng tên → chỉ cần khai báo |
| **AL Cost Template Item** | `layer` (`Q`/`S`/`BOTH`) | **Thay** cho `template_type` ở cấp template — tránh phải nhân đôi template mỗi Product Type |
| **AL Cost Bucket** | `bucket_type`, `is_planning_only` | `MATERIAL/LABOR/MACHINE/OVERHEAD/UNPLANNED/RECOVERY` |
| **Accounting Dimension** | tạo `AL Cost Bucket` | Field sinh tự động trên `Stock Entry Detail`, `Purchase Receipt Item`, `Purchase Invoice Item`, `Journal Entry Account`, `Landed Cost Item`. Đã kiểm chứng: `merge_similar_entries()` gộp theo dimension nên bucket từng dòng không bị trộn |

---

## 6. CÔNG THỨC

### 6.1 Giá thành định mức

```
Với mỗi dòng vật tư:
   net_qty   = công thức BOM                    (đã có)
   scrap     = ScrapResolver(item, profile)     (trục hao hụt)
   gross_qty = net_qty × (1 + scrap)            ← hoặc dùng thẳng số Cutting Plan
   price     = PriceResolver(item, profile, as_of, trạng_thái_mua)
   amount    = gross_qty × price
   bucket    = line.cost_bucket

Nhân công:
   OPERATIONS   : Σ (giờ_op × đơn_giá_op)
   PIECE_RATE   : Σ (đơn_giá_khoán_op × số_bộ)

Lắp đặt:
   số_người × giờ × đơn_giá_đội × hệ_số_độ_cao(h)

Chi phí chung:
   PERCENT      : pct × (vật_liệu + nhân_công)
   DRIVER_BASED : driver × rate      (m² giao | giờ công TT)

Dự phòng làm lại:
   rate_dp × giá_trị_sản_xuất        ← dòng RIÊNG, không giấu trong % hao hụt

Giá thành = Σ nhóm
```

### 6.2 Các con số quản trị

```
margin_now        = (revenue − live_amount) / revenue
độ_nhạy(1% nhôm)  = VL_NHOM / revenue
exposure          = giá_trị_vật_tư_chưa_chốt  (price_status ∈ {UNPRICED, ESTIMATED})
biên_sau_sốc(10%) = margin_now − 10 × độ_nhạy
```

### 6.3 Phân tách chênh lệch — chỉ một thành phần được nạp lại

```
S_release − A = chênh_giá + chênh_lượng + chênh_đơn_giá_công + chênh_hiệu_suất + làm_lại
```

| Thành phần | Nạp lại định mức? | Xử lý |
|---|---|---|
| Chênh giá | **Không** | Rủi ro thị trường — S_live đã bắt. Đo bằng báo cáo mua hàng |
| Chênh đơn giá công | **Không** | Cập nhật **đơn giá giờ**, không phải định mức giờ |
| Chênh hiệu suất | **Không** | KPI sản xuất, không phải định mức |
| Làm lại | **Không** | KPI chất lượng; định mức dự phòng hiệu chỉnh riêng theo tỷ lệ lịch sử |
| **Chênh lượng** | **Có, có điều kiện** | Chỉ khi P20 chứng minh mức cũ sai |

### 6.4 Hiệu chỉnh định mức

```
định_mức_mới = P20( lượng_thực_tế / bộ , theo product_type & slug, 6 tháng )
```

**Không dùng median.** Xem §8.2.

---

## 7. LỘ TRÌNH

| Pha | Nội dung | Thời gian | Nghiệm thu (đo được) |
|---|---|---|---|
| **0** | Bỏ `commit()` khỏi engine · tách `compute`/`persist` · tổng quát hoá `_qi_doc` · thêm field SO Item · sửa `aggregate_requirements` (đang lỗi SQL vì đọc cột chưa tồn tại) | **1 tuần** | Tạo SO từ báo giá giữ nguyên `al_bom*` (test tự động) · submit SO không commit giữa transaction |
| **1** | `AL Cost Profile`, `AL Cost Plan` (chỉ S_live), `PriceResolver`, `ScrapResolver` · Thẻ lợi nhuận trên dòng SO · độ nhạy giá | **2–3 tuần** | Mở SO thấy giá thành < 2s · đổi 1 Item Price → mọi đơn mở cập nhật < 60s · không có giá = 0 mà không cảnh báo · đối chứng: ΔS = lượng × Δgiá |
| **1b** | Bảng **phơi rủi ro** toàn công ty + cảnh báo biên | **3–5 ngày** | Một màn hình, số tổng khớp Σ theo đơn |
| **2** | `S_release` (khoá) · Accounting Dimension `AL Cost Bucket` · hook gán bucket · collector → `AL Cost Fact` · báo cáo so sánh theo công trình | **3–4 tuần** ⚠ | Σ Fact = GL theo (project, account), lệch < 0,1% · **đối chứng dương**: cố tình map sai → báo cáo đỏ |
| **3** | `AL Cost Standard` · báo cáo hiệu chỉnh P20 vs median · quy trình duyệt định mức | **2 tuần** | Mỗi Product Type có ≥ 10 đơn hoàn thành · khoảng cách P20–median hiện và có xu hướng |
| **4** | Lưới Q·S·A theo tài khoản (cho kế toán) + mapping rule đầy đủ | **3–4 tuần** | Kế toán xác nhận khớp P&L |
| **5** | Phân bổ chi phí chung, hấp thụ qua Work Order | **chỉ khi 1–4 ổn định ≥ 2 kỳ** | |

⚠ Pha 2 phụ thuộc **cổng dữ liệu** (§10) — có thể dừng ở đây nhiều tháng nếu dữ liệu chưa sạch.

**Mốc có giá trị sử dụng: hết Pha 1 ≈ 3–4 tuần.** Đây là lúc hệ thống bắt đầu trả lời được câu hỏi
"đơn này lãi bao nhiêu" — phần lớn giá trị nằm ở đây, không phải ở Pha 4–5.

**Tổng để hoàn chỉnh vòng học (Pha 0–3): 8–10 tuần làm việc thực tế**, chưa kể dọn dữ liệu.

---

## 8. BỐN ĐIỀU QUYẾT ĐỊNH THÀNH BẠI

### 8.1 S_live phải dùng **giá đã mua của chính đơn đó**, không dùng bình quân kho

| Trạng thái đơn | Giá dùng | Ý nghĩa |
|---|---|---|
| Chưa mua | Giá thị trường hiện tại | Đang phơi rủi ro |
| Đã có PO | Giá trên PO | Đã chốt một phần |
| Đã nhập kho cho đơn | **Giá vốn lô đã nhập cho đơn này** | Đã chốt |

Nếu dùng bình quân kho, đơn đã mua xong vẫn "nhảy" khi kho nhập lô khác — người quản trị đơn
mất niềm tin ngay lần đầu.

### 8.2 Hiệu chỉnh nhắm **P20**, không nhắm **median**

Đây là điều quan trọng nhất trong toàn bộ đề xuất.

Nếu mỗi kỳ lấy hao hụt thực tế bình quân làm định mức mới, thì S tiến sát A rất nhanh — và bạn vừa
**hợp thức hoá sự kém hiệu quả**. Hao hụt 20% vì làm ẩu trở thành "định mức 20%", không còn ai có
động lực về 12%. Đây là lỗi kinh điển của quản trị định mức, và với mục tiêu "hiệu chỉnh S để tiến
sát A" thì **gần như chắc chắn sẽ xảy ra** nếu không chặn từ đầu.

Quy tắc: định mức tiến về **mức mà 20% đơn tốt nhất đạt được** — chứng minh khả thi, không phải mơ.

Và phải hiển thị **hai đường mãi mãi**:

| Đường | Nghĩa | Trách nhiệm |
|---|---|---|
| Định mức (P20) | Mức phải đạt | Kỹ thuật chốt |
| Thực tế (median) | Mức đang đạt | Sản xuất chịu |
| Khoảng cách | Kém hiệu quả | KPI cải tiến |

### 8.3 Dòng "dự phòng làm lại" phải là dòng riêng

Vỡ kính, sai kích thước, phải tháo lắp lại là chi phí **có thật và dự báo được** trong ngành này.
Nếu giấu trong % hao hụt, S sẽ luôn thấp hơn A và vòng hiệu chỉnh sẽ hiệu chỉnh nhầm chỗ.

### 8.4 Phải phân biệt "số đo" và "số suy luận" trên mọi báo cáo

| Nhãn | Nghĩa | Ví dụ |
|---|---|---|
| ● **Đo** | Đọc từ dữ liệu gốc | A theo tài khoản; S theo nhóm |
| ◐ **Suy 1 bước** | Biến đổi xác định | bucket → tài khoản (1:1) |
| ○ **Phân bổ** | Chia theo trọng số giả định | A theo nhóm (suy từ vật tư); dòng SO |

Field `AL Cost Fact.is_measured` và nhãn trên báo cáo là bắt buộc. Không có nó, kế toán sẽ tranh cãi
một phép chia 40/60 như thể đó là sự thật.

---

## 9. PHẠM VI KHÔNG LÀM (giai đoạn này)

| Không làm | Vì sao |
|---|---|
| Revision + state machine cho S | S_live không cần lịch sử. S_release đóng băng thì chỉ 1 bản |
| Trigger realtime đầy đủ (mọi Item Price, mọi Bin) | S_live chỉ nhân lại tầng 2 — debounce 60s là đủ. Không cần hàng đợi phức tạp |
| 12 bucket + mapping nhiều–nhiều có trọng số | 6 nhóm là đủ cho quản trị. Trọng số chỉ dùng cho Q, và ghi rõ là giả định |
| `AL Cost Allocation Run` sinh Journal Entry | Rủi ro kiểm toán cao, giá trị quản trị tức thời bằng 0. Dùng JE tay theo mẫu |
| Hấp thụ chi phí qua `additional_costs` của ERPNext | v14 chỉ tạo **1 dòng** vào `Company.default_expense_account`, không dimension, không tách công đoạn → không dùng được cho phân tích |
| Job Card time log làm nguồn nhân công thực tế | Xưởng không bấm giờ. Dùng bảng lương/chấm công phân bổ theo tổ–công trình; Job Card chỉ cho máy CNC |
| Vật liệu hoá BOM cho **mọi** dòng SO | Chỉ tạo lúc Release. BOM đã submit là bất biến → không dùng được cho S_live |
| So sánh Q·S·A ở grain dòng Sales Order | Dòng SO là số phân bổ. Grain thật là công trình |

---

## 10. CỔNG DỮ LIỆU (điều kiện vào Pha 2)

Phải đo **trên dữ liệu thật** trước khi cam kết Pha 2:

| Chỉ số | Ngưỡng | Nếu không đạt |
|---|---|---|
| % chứng từ chi phí có `Project` | ≥ 95% | **Dừng Pha 2** — lớp A sẽ hụt chi phí |
| % vật tư có `AL Material Category` | ≥ 90% | Làm sạch master data trước |
| Dòng `UNMAPPED` / tháng | < 2% tổng chi phí | Mapping chưa đủ, chưa công bố báo cáo |
| Có bảng chấm công theo tổ–công trình | ≥ 3 tháng | Nhân công A sẽ là số bịa |
| % dòng tồn kho nhôm/kính có giá vốn đúng | ≥ 95% | S_live sai từ gốc |

**Nói thẳng với Owner điều này trước khi bắt đầu**, đừng phát hiện giữa dự án.

---

## 11. RỦI RO

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Dữ liệu không đủ sạch cho lớp A | **Cao** | Cổng dữ liệu §10; Pha 1 vẫn có giá trị độc lập |
| Hiệu chỉnh định mức = hợp thức hoá hao hụt | **Cao** | P20 thay median; hai đường hiển thị; duyệt theo quý |
| Không có chủ sở hữu hệ thống | **Cao** | Chỉ định "kế toán giá thành"; nghi thức thứ Hai hằng tuần |
| Giá vốn kho trống với hàng mới | Trung bình | `price_fallback_chain`, cấm rơi về 0, `strict_errors` |
| Sai khác v14 ↔ v16 | Trung bình | Chạy lại kiểm chứng trên v16 trước Pha 2 (lõi GL/dimension) |
| Cắt gộp vs chi phí theo dòng SO | Trung bình | Grain công trình, dòng SO là phân bổ, ghi rõ |
| Kỳ vọng "tận dụng tối đa core" | Trung bình | Nói rõ: ERPNext v14 **không có** standard costing — lớp S là phần tự xây phải nuôi |

---

## 12. QUYẾT ĐỊNH CẦN CHỐT

| # | Câu hỏi | Ảnh hưởng | Đề xuất của tôi |
|---|---|---|---|
| 1 | Mô hình hạch toán: **sản xuất** (154→155→632) hay **xây lắp** (154→giá thành công trình)? | Có TK 623 hay không; grain; toàn bộ báo cáo kế toán | Xác nhận với kế toán trưởng. Mặc định đề xuất: **xây lắp** cho phần lắp đặt, sản xuất cho phần cửa |
| 2 | Nhân công thực tế: **bảng lương phân bổ** hay **Job Card**? | Độ khả thi của lớp A | **Bảng lương phân bổ** theo tổ–công trình |
| 3 | Có cam kết nghi thức **thứ Hai hằng tuần** + **họp hiệu chỉnh hằng quý** không? | Toàn bộ giá trị sử dụng | Nếu không cam kết → làm Pha 1 (thẻ lợi nhuận) rồi dừng |
| 4 | Phạm vi: dừng ở đâu? | Ngân sách, thời gian | **Dừng ở Pha 3** (vòng học hoàn chỉnh). Pha 4–5 mở sau |
| 5 | Ai là **chủ sở hữu** hệ thống trong công ty? | Sống hay chết sau 6 tháng | Phải có tên, không phải "phòng kế toán" |

---

## 13. NGUỒN LỰC & THỜI GIAN

| Vai | Việc | Thời lượng |
|---|---|---|
| **SA1** | Chốt mô hình dữ liệu, review kiến trúc đầu mỗi pha | 2–3 ngày |
| **DEV1** (lead) | Engine: tách compute/persist, PriceResolver, ScrapResolver, Cost Plan | 60% Pha 0–2 |
| **DEV2** | Báo cáo, thẻ lợi nhuận, bảng phơi rủi ro, export | 60% Pha 1–3 |
| **BA1** | Chốt định mức với kỹ thuật, quy trình hiệu chỉnh, tài liệu dùng | Pha 3 |
| **TESTER1** | Test đối chứng dương, test idempotent, regression BOM | Mỗi pha |
| **UX1** | Gate trải nghiệm trước khi công bố mỗi màn hình | Cuối Pha 1, 1b, 2, 3 |

**Hai mốc bàn giao:**
- **Tuần 4:** thẻ lợi nhuận trên mỗi đơn + bảng phơi rủi ro → BGĐ dùng được ngay.
- **Tuần 10:** vòng học hoàn chỉnh (S_release, A theo công trình, báo cáo hiệu chỉnh).

---

## 14. MỘT TRANG TÓM TẮT

**Xây gì:** một vòng điều khiển lợi nhuận, không phải hệ thống báo cáo.
**Bằng cách nào:** thêm một bộ đơn giá thứ hai lên engine BOM đã có, không xây engine thứ hai.
**Người dùng thấy gì:** thẻ lợi nhuận trên từng đơn · bảng phơi rủi ro của BGĐ · so sánh kế hoạch–thực
tế theo công trình · báo cáo hiệu chỉnh định mức.
**Bao lâu:** dùng được sau 3–4 tuần (Pha 1), hoàn chỉnh sau 8–10 tuần (Pha 0–3).
**Rủi ro lớn nhất:** dữ liệu nguồn không sạch (cổng §10) và hiệu chỉnh định mức theo median
(phải dùng P20).
**Không làm:** revision/state machine, 12 bucket, allocation run tự sinh bút toán, Job Card làm
nguồn nhân công, so sánh ở grain dòng SO.
**Quyết định cần:** mô hình hạch toán · nguồn nhân công · cam kết nghi thức quản trị · phạm vi ·
người chủ sở hữu.
