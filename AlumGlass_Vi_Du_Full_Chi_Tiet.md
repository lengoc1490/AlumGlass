# VÍ DỤ FULL A-Z: TỪ MASTER DATA ĐẾN GIÁ BÁN CUỐI CÙNG
## Sản phẩm: Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)

> Tài liệu này dựa trên bản **v28.2 — CHUẨN TRIỂN KHAI** với **Formula Builder v30** (BatchBindingResolver, SourceTypeRegistry, 13 source types, Composite Types, Transform Layer, 🆕 SnapshotManager.submit()/load() persistence). Mục tiêu: đi từ **con số 0** — chưa có gì trong hệ thống — cho tới khi ra được **giá bán có VAT = 22,717,289đ**, giải thích **tại sao mỗi con số lại ra như vậy**, **engine tính toán vận hành như thế nào**, và **cách thêm nguồn data mới không cần code**.
>
> **Có gì mới so với bản cũ:** DataSourceResolver thay thế B2 hardcode, Cost Bucket có source_type/source_config, hỗ trợ pipeline/conditional/fallback_chain, transform layer, đăng ký custom handler qua hooks.py.
>
> Cách đọc: mỗi phần đều có ví dụ số cụ thể đi kèm ngay bên cạnh phần lý thuyết — không có phần nào chỉ mô tả suông.

---

## MỤC LỤC

1. Bức tranh tổng thể — 3 tầng hệ thống và dữ liệu chảy qua chúng như thế nào
2. Toàn bộ Master Data cần tạo trước (kèm giải thích từng bảng dùng để làm gì)
3. Cấu hình sản phẩm mẫu — BOM 17 dòng
4. Formula Engine hoạt động như thế nào (DAG, topological sort, cross-row reference)
5. BomOrchestrator — 7 phase (v28.2) với số liệu thật
6. Bảng tính chi tiết toàn bộ 17 dòng (mở rộng từng phép thay số)
7. Cost Template — từ tổng vật liệu ra giá bán có VAT
8. **NEW: Thêm nguồn data mới không cần code (FB v31)**
9. **NEW: Composite Types & Transform — áp dụng cho nhôm kính**
10. Kiểm tra chéo & những "bẫy" cần tránh khi triển khai
11. 🆕 Snapshot Persistence — Lưu & Khôi phục kết quả tính (FB v30)
12. Tóm tắt một trang (cheat-sheet v30)

---

## 1. BỨC TRANH TỔNG THỂ

Hệ thống gồm 3 tầng, mỗi tầng chỉ biết việc của mình — đây là điều quan trọng nhất cần hiểu trước khi đọc phần còn lại:

| Tầng | Vai trò | Có biết gì về "cửa nhôm" không? |
|---|---|---|
| **Formula Builder** | Một engine tính toán công thức tổng quát: nhận vào `formulas` (dictionary tên biến → chuỗi công thức) và `inputs` (dictionary tên biến → giá trị), tự xây một đồ thị phụ thuộc (DAG), sắp xếp thứ tự tính đúng, rồi trả về `result` | **Không biết gì cả.** Nó không biết "kính", "nhôm", "cánh cửa" là gì. Nó chỉ thấy biến số và công thức. |
| **AlumGlass** | App nghiệp vụ: biết BOM cửa nhôm kính gồm những gì, đọc master data, chuẩn bị `formulas`/`inputs` đúng định dạng rồi *giao* cho Formula Builder tính, sau đó *nhận lại* kết quả để gom nhóm chi phí, tính giá bán | Biết toàn bộ nghiệp vụ, nhưng **không tự tính công thức** — việc đó giao hẳn cho Formula Builder |
| **ERPNext Core** | Kho dữ liệu nền: Item, Item Price, Batch... | Chỉ lưu trữ, không tính toán nghiệp vụ |

**Vì sao phải tách như vậy?** Vì Formula Builder là app **bất biến** (dùng chung cho nhiều loại BOM khác nhau trong tương lai, không riêng gì nhôm kính) — AlumGlass không được sửa code của nó, chỉ được "cắm" thêm hàm tính riêng của mình vào (`extra_funcs`) và chuẩn bị dữ liệu đúng khuôn dạng mà nó yêu cầu.

**Dòng chảy dữ liệu tổng quát**, sẽ được minh họa bằng số liệu thật ở phần 5:

```
Người dùng nhập (Quotation)          Master Data (đã cấu hình sẵn)
  W_mm=2400, H_mm=2600  ─┐             AL Profile Line, AL Variable Set,
  n_canh=2, mau=WHITE   ─┼──────────►  AL Cost Template, Item Price, ...
                          │
                          ▼
              ┌─────────────────────┐
              │   BomOrchestrator    │   ◄── app AlumGlass, 7 phase B0→B7 (v28.2)
              │  (chuẩn bị dữ liệu)  │
              │  B2: DataSourceResolver│  ◄── gọi FB BatchBindingResolver
              └──────────┬───────────┘
                         │  formulas={...}, inputs={...}
                         ▼
              ┌─────────────────────┐
              │   Formula Builder v31│   ◄── app độc lập, chỉ biết DAG
              │  engine.calculate()  │       + BatchBindingResolver
              │  + SourceTypeRegistry│       + 13 source types
              └──────────┬───────────┘
                         │  result={...}
                         ▼
              ┌─────────────────────┐
              │   BomOrchestrator    │   ◄── gom cost bucket, tính Cost Template
              │  (xử lý kết quả)     │
              └──────────┬───────────┘
                         │
                         ▼
               GIA_VAT = 22,717,289đ
```

---

## 2. TOÀN BỘ MASTER DATA CẦN TẠO TRƯỚC

Đây là dữ liệu **cấu hình một lần**, dùng lại cho mọi báo giá sau này. Thứ tự dưới đây **chính là thứ tự phải tạo khi triển khai thật**, vì bảng sau tham chiếu (Link) tới bảng trước.

### 2.1. Item Group (Core ERPNext)

| item_group | parent_item_group | is_group |
|---|---|---|
| NHOM_PROFILE | (root) | 1 |
| NHOM_XINGFA | NHOM_PROFILE | 0 |
| NHOM_ALUMIL | NHOM_PROFILE | 0 |
| KINH | (root) | 0 |
| PHU_KIEN | (root) | 0 |
| VAT_TU_PHU | (root) | 0 |

*Dùng để phân loại Item trong báo cáo tồn kho/mua hàng — không ảnh hưởng trực tiếp tới công thức tính giá.*

### 2.2. Brand (Core ERPNext)

| brand | description |
|---|---|
| XINGFA | Nhôm Xingfa |
| ALUMIL | Nhôm Alumil |
| KINLONG | Phụ kiện Kinlong |

### 2.3. AL Color Standard (DocType custom)

| color_code | color_name | applies_to | is_standard_stock |
|---|---|---|---|
| WHITE | Trắng | NHOM_PROFILE | 1 |
| DARK | Đen | NHOM_PROFILE | 1 |
| GRAY | Ghi | NHOM_PROFILE | 1 |
| WOOD | Vân gỗ | NHOM_PROFILE | 0 |

*Đây là danh mục màu chuẩn hóa — dùng làm giá trị hợp lệ cho field `custom_mau_sac` trên Item Price (mục 2.7) và biến `mau_nhom` trong Variable Set (mục 2.15). Nhờ đây UI validate được, không cho gõ tự do "trắng", "White", "TRANG" lẫn lộn.*

### 2.4. AL Calculation Rule (DocType custom) — hằng số hình học (offset)

| rule_code | rule_name | rule_type | constant_value |
|---|---|---|---|
| OFFSET-FRAME | Khe hở khung-cánh | CONSTANT | 48 |
| OFFSET-GLASS | Khe hở cánh-kính | CONSTANT | 90 |
| OFFSET-FIXED | Khe hở khung-kính cố định | CONSTANT | 50 |
| OFFSET-DO-NGANG | Khe hở đố ngang | CONSTANT | 48 |

*Đây là các con số kỹ thuật gia công (đơn vị mm) dùng để trừ hao khi tính kích thước cắt của cánh/kính từ kích thước khung bao. Được nạp vào công thức dưới dạng biến `$OFFSET_FRAME`, `$OFFSET_GLASS`... — quan trọng: đây là **data**, không hard-code trong code, để sau này đổi hệ profile khác chỉ cần sửa bảng này, không cần sửa code.*

### 2.5. Formula Global Variable (DocType của Formula Builder — dùng chung mọi BOM trong hệ thống)

| var_name | value_source | constant_value |
|---|---|---|
| VAT_RATE | CONSTANT | 0.10 |
| PROFIT_MARGIN | CONSTANT | 0.16 |
| NC_SX_PCT | CONSTANT | 0.08 |
| NC_LD_PCT | CONSTANT | 0.12 |
| OH_VC_PCT | CONSTANT | 0.03 |
| OH_QLY_PCT | CONSTANT | 0.03 |

*Các tỷ lệ % kinh doanh (nhân công, overhead, lợi nhuận, thuế) — dùng ở tầng Cost Template (phần 7), tham chiếu bằng cú pháp `$TEN_BIEN` trong công thức.*

### 2.6. Item (Core ERPNext)

**a) Mã "đại diện" dùng để tra giá — không có trọng lượng vật lý riêng, vì bản thân nó không phải là hàng tồn kho mà là "gốc giá" cho nhiều biến thể màu/xuất xứ:**

| item_code | item_name | item_group | brand | stock_uom | al_item_type |
|---|---|---|---|---|---|
| NHOM-XINGFA | Nhôm Xingfa (đại diện) | NHOM_XINGFA | XINGFA | Kg | NHOM_PROFILE |
| NHOM-ALUMIL | Nhôm Alumil (đại diện) | NHOM_ALUMIL | ALUMIL | Kg | NHOM_PROFILE |
| TAY_NAM_KINLONG | Tay nắm Kinlong (đại diện) | PHU_KIEN | KINLONG | Cái | PHU_KIEN |

**b) Profile vật lý cụ thể — có trọng lượng/mét (dùng để tính khối lượng thật), màu quản lý qua Batch nếu cần theo dõi tồn kho theo màu:**

| item_code | item_name | weight_per_unit (kg/m) | al_item_type |
|---|---|---|---|
| XF55-KB-20 | Khung bao H55 2.0mm | 1.257 | NHOM_PROFILE |
| XF55-CANH-20 | Cánh mở quay 2.0mm | 1.350 | NHOM_PROFILE |
| C3211-20 | Nẹp kính >16mm | 0.312 | NHOM_PROFILE |
| C3210-20 | Nẹp kính 11–16mm | 0.245 | NHOM_PROFILE |
| C3209-20 | Nẹp kính ≤10.38mm | 0.198 | NHOM_PROFILE |
| KINH-LOWE-24 | Kính Low-E 24mm | – (đo m²) | KINH |
| KINH-DON-8 | Kính dán 8mm | – (đo m²) | KINH |
| KEO-TT-01 | Keo trung tính (Low-E) | – (đo mét) | VTP |
| KEO-TT-02 | Keo thường | – (đo mét) | VTP |
| GIO-EPDM-55 | Gioăng EPDM 55 | – (đo mét) | VTP |
| VIT-TK-35X16 | Vít tự khoan 3.5x16 | – (đo cái) | VTP |
| KL-MZS20 | Tay nắm Kinlong MZS20 | – (đo cái) | PHU_KIEN |
| KL-KHOA-01 | Khóa Kinlong 01 | – (đo cái) | PHU_KIEN |
| KL-T-MJ06 | Bản lề cối MJ06 | – (đo cái) | PHU_KIEN |

**Vì sao tách (a) và (b)?** Vì một profile nhôm cụ thể (ví dụ `XF55-KB-20`) sẽ được tra giá theo mã "đại diện" (`NHOM-XINGFA`) + tổ hợp (màu, xuất xứ, độ dày, bề mặt) trong Item Price — thay vì phải tạo một Item riêng cho từng tổ hợp màu × xuất xứ × profile (sẽ **bùng nổ số lượng Item**). `weight_per_unit` của (b) dùng để tính khối lượng vật lý thật; giá tiền/kg lại lấy từ (a) qua composite key.

### 2.7. Item Price (Core ERPNext + 4 Custom Field)

**Custom Field cần thêm vào Item Price:**

| fieldname | fieldtype | options |
|---|---|---|
| custom_mau_sac | Link | AL Color Standard |
| custom_xuat_xu | Select | IMPORT, DOMESTIC |
| custom_do_day | Int | – |
| custom_be_mat | Select | POWDER_COATED, ANODIZED, WOOD_GRAIN |

**Ràng buộc bắt buộc:** Server Script chặn trùng tổ hợp `(item_code, price_list, custom_mau_sac, custom_xuat_xu, custom_do_day, custom_be_mat)` — nếu không có ràng buộc này, hệ thống có thể vô tình có 2 dòng giá cho cùng 1 tổ hợp, engine sẽ không biết lấy dòng nào.

**Dữ liệu mẫu (đây là bảng giá thật được dùng trong ví dụ tính toán ở phần 6):**

| item_code | price_list_rate | custom_mau_sac | custom_xuat_xu | custom_do_day | custom_be_mat |
|---|---|---|---|---|---|
| NHOM-XINGFA | **113,000** | **WHITE** | **IMPORT** | **20** | **POWDER_COATED** |
| NHOM-XINGFA | 118,000 | DARK | IMPORT | 20 | POWDER_COATED |
| NHOM-XINGFA | 145,000 | WOOD | IMPORT | 20 | WOOD_GRAIN |
| NHOM-XINGFA | 98,000 | WHITE | DOMESTIC | 20 | POWDER_COATED |
| NHOM-ALUMIL | 135,000 | WHITE | IMPORT | 20 | POWDER_COATED |
| TAY_NAM_KINLONG | 210,000 | – | – | – | – |
| KINH-LOWE-24 | 1,150,000 | – | – | – | – |
| KINH-DON-8 | 550,000 | – | – | – | – |
| KEO-TT-01 | 45,000 | – | – | – | – |
| KEO-TT-02 | 30,000 | – | – | – | – |
| GIO-EPDM-55 | 1,250 | – | – | – | – |
| VIT-TK-35X16 | 850 | – | – | – | – |
| KL-MZS20 | 210,000 | – | – | – | – |
| KL-KHOA-01 | 350,000 | – | – | – | – |
| KL-T-MJ06 | 180,000 | – | – | – | – |

**Dòng in đậm là dòng thực sự được dùng trong ví dụ này**, vì báo giá mẫu chọn `mau_nhom=WHITE, xuat_xu_nhom=IMPORT, do_day_nhom=20, be_mat_nhom=POWDER_COATED` → tất cả 10 dòng nhôm trong BOM đều tra ra **113,000đ/kg**.

### 2.8. AL Glass Master (DocType custom)

| glass_code | total_thick_mm | glass_type |
|---|---|---|
| KINH-LOWE-24 | **24** | **LOWE** |
| KINH-DON-8 | 8 | DON |

*Bảng này tách riêng khỏi Item vì độ dày kính và loại kính là dữ liệu kỹ thuật dùng để **chọn phụ kiện đi kèm** (nẹp, keo) — không phải thuộc tính giá.*

### 2.9. AL Dynamic Item Rule (DocType custom)

**Rule 1 — chọn nẹp kính theo độ dày** (`RULE-NEP-GLASSTHICK`, kiểu THRESHOLD — tra theo khoảng giá trị):

| from_value | to_value | item_code |
|---|---|---|
| 0 | 10.38 | C3209-20 |
| 10.39 | 16 | C3210-20 |
| **16.01** | **999** | **C3211-20** |

**Rule 2 — chọn keo theo loại kính** (`RULE-KEO-GLASSTYPE`, kiểu LOOKUP — tra theo khóa đúng bằng):

| key_1 | result_item |
|---|---|
| **LOWE** | **KEO-TT-01** |
| DON | KEO-TT-02 |

*Kính trong ví dụ này dày 24mm, loại LOWE → cả hai rule sẽ trả về `C3211-20` (nẹp) và `KEO-TT-01` (keo) — xem cách engine tra ra 2 kết quả này ở B2b, phần 5.*

### 2.10. AL Slug Library (DocType custum) — 17 slug chuẩn

`slug` là **định danh duy nhất và ổn định** của mỗi dòng BOM — không đổi theo thời gian, không phụ thuộc thứ tự hiển thị (`sort`). Đây là "tên biến" mà mọi công thức cross-row sẽ tham chiếu tới.

| slug | line_type | Ý nghĩa |
|---|---|---|
| khung_ngang_tren | NHOM | Thanh khung bao phía trên |
| khung_ngang_duoi | NHOM | Thanh khung bao phía dưới |
| khung_dung | NHOM | Thanh khung bao đứng (2 bên) |
| do_ngang | NHOM | Thanh ngang ngăn ô kính cố định và cánh |
| canh_ngang | NHOM | Thanh ngang của cánh cửa |
| canh_dung | NHOM | Thanh đứng của cánh cửa |
| kinh_tren | KINH | Tấm kính cố định phía trên đố |
| kinh_duoi | KINH | Tấm kính của mỗi cánh |
| nep_kinh_tren | NHOM | Nẹp giữ kính cố định |
| nep_kinh_duoi | NHOM | Nẹp giữ kính cánh |
| keo_tren | VTP | Keo dán kính cố định |
| keo_duoi | VTP | Keo dán kính cánh |
| gioang | VTP | Gioăng bao quanh khung |
| vit | VTP | Vít lắp ráp |
| tay_nam | PHU_KIEN | Tay nắm cửa |
| khoa | PHU_KIEN | Khóa cửa |
| ban_le | PHU_KIEN | Bản lề cửa |

### 2.11. AL Quantity Calc Method (DocType custom) — 4 pattern cố định

| calc_pattern_code | Công thức (chỉ để hiển thị) | Áp dụng cho |
|---|---|---|
| LENGTH_TO_WEIGHT | `(width/1000) × trọng_lượng_riêng` | NHOM, THÉP, INOX — đo theo mét dài, quy đổi ra kg |
| AREA | `(width/1000) × (height/1000)` | KÍNH — đo theo m² |
| LENGTH_ONLY | `width/1000` | VTP đo theo mét (gioăng, keo) |
| COUNT | `1` | VTP đo theo cái (vít), PHỤ KIỆN |

> **Lưu ý kiến trúc quan trọng (đã được sửa ở bản v27):** 4 công thức trên **chỉ để người dùng đọc hiểu ý nghĩa**, KHÔNG được dùng để "diễn giải chuỗi bằng engine" lúc chạy thật. Lý do và cách làm đúng được giải thích chi tiết ở phần 4.3.

### 2.12. AL Cost Bucket (DocType custom) — cây phân loại chi phí + Data Source Definition (NEW v28.2)

**NEW v28.2:** Mỗi Cost Bucket có thêm 4 fields để định nghĩa nguồn dữ liệu — khai báo 1 lần, dùng cho mọi BOM:

| Field mới | Kiểu | Mô tả | Ví dụ |
|---|---|---|---|
| `source_type` | Select | aggregate_from_items / formula / doctype_query / custom_function / constant / pipeline / conditional / fallback_chain | `doctype_query` |
| `source_config` | JSON | Cấu hình nguồn (filters, fieldname, transform, steps...) | `{"doctype":"Item Price","fieldname":"price_list_rate",...}` |
| `depends_on` | JSON | Biến phụ thuộc cho DAG resolve | `["mau_nhom", "xuat_xu_nhom"]` |
| `batch_group` | Data | Nhóm batch query (cùng group → 1 query IN) | `ITEM_PRICE` |

**Bảng Cost Buckets với source_type:**

| bucket_code | bucket_name | bucket_role | parent_bucket | source_type | Ghi chú |
|---|---|---|---|---|---|
| VL_NHOM | Vật liệu nhôm | LEAF | TONG_VL | aggregate_from_items | Gom thanh_tien từ Bom Items |
| VL_KINH | Vật liệu kính | LEAF | TONG_VL | aggregate_from_items | Gom thanh_tien từ Bom Items |
| VL_VTP | Vật tư phụ | LEAF | TONG_VL | aggregate_from_items | Gom thanh_tien từ Bom Items |
| VL_PK | Phụ kiện | LEAF | TONG_VL | aggregate_from_items | Gom thanh_tien từ Bom Items |
| TONG_VL | Tổng vật liệu | AGGREGATE | – | formula | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` |
| NC_SX | Nhân công sản xuất | LEAF | TONG_NC | formula | `$NC_SX_PCT * TONG_VL` |
| NC_LD | Nhân công lắp đặt | LEAF | TONG_NC | formula | `$NC_LD_PCT * TONG_VL` |
| TONG_NC | Tổng nhân công | AGGREGATE | – | formula | `NC_SX + NC_LD` |
| OH_VC | Overhead vận chuyển | LEAF | TONG_OH | formula | `$OH_VC_PCT * TONG_VL` |
| OH_QLY | Overhead quản lý | LEAF | TONG_OH | formula | `$OH_QLY_PCT * (TONG_VL + TONG_NC)` |
| TONG_OH | Tổng overhead | AGGREGATE | – | formula | `OH_VC + OH_QLY` |
| GIA_THANH | Giá thành | AGGREGATE | – | formula | `TONG_VL + TONG_NC + TONG_OH` |
| GIA_BAN | Giá bán chưa VAT | AGGREGATE | – | formula | `GIA_THANH + PROFIT` |
| GIA_VAT | Giá bán có VAT | AGGREGATE | – | formula | `GIA_BAN + VAT` |

*Mỗi dòng BOM (17 dòng ở phần 3) được gán vào đúng 1 `cost_bucket` LEAF. Với bucket `aggregate_from_items`, DataSourceResolver tự động gom `thanh_tien` theo bucket. Với bucket `formula`, engine tính từ các bucket khác. Với bucket `doctype_query`, FB BatchBindingResolver tự động batch query + cache.*

**Ví dụ thêm bucket mới từ nguồn DB (không code):**

```json
// CP_VAN_CHUYEN: query bảng giá vận chuyển
{"bucket_code": "CP_VAN_CHUYEN", "bucket_role": "LEAF", "parent_bucket": "TONG_OH",
 "source_type": "doctype_query",
 "source_config": {"doctype": "Transport Rate", "fieldname": "rate_per_km", "aggregate": "first",
   "filters": [["from_location", "=", "{inputs.kho_xuat}"], ["to_district", "=", "{inputs.quan_cong_trinh}"]]},
 "batch_group": "TRANSPORT"}
```

### 2.13. Formula Set `BOM_LINE` (DocType của Formula Builder)

Đây là **3 công thức dùng chung cho MỌI dòng BOM**, bất kể dòng đó là nhôm, kính, hay phụ kiện:

| var_name | formula | Ý nghĩa |
|---|---|---|
| `so_luong_don_vi` | `lookup_calc_pattern(calc_pattern, width, height, trong_luong_rieng)` | Khối lượng/diện tích/chiều dài của **1 đơn vị** thanh/tấm |
| `tong_so_luong` | `so_luong_don_vi * qty` | Nhân với số lượng cần dùng |
| `thanh_tien` | `tong_so_luong * don_gia` | Nhân với đơn giá → ra tiền |

*Đây chính là 3 công thức mà Formula Builder sẽ tính cho **từng dòng trong 17 dòng**, dùng chung 1 khuôn — khác nhau chỉ ở `width`, `height`, `qty`, `calc_pattern`, `trong_luong_rieng`, `don_gia` của từng dòng.*

### 2.14. AL Cost Template `CT-01-STANDARD` (DocType custom)

| line_code | calc_formula | is_subtotal |
|---|---|---|
| TONG_VL | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` | 1 |
| TONG_M2 | `(W_mm/1000)*(H_mm/1000)` | 0 |
| NC_SX | `$NC_SX_PCT * TONG_VL` | 0 |
| NC_LD | `$NC_LD_PCT * TONG_VL` | 0 |
| TONG_NC | `NC_SX + NC_LD` | 1 |
| OH_VC | `$OH_VC_PCT * TONG_VL` | 0 |
| OH_QLY | `$OH_QLY_PCT * (TONG_VL + TONG_NC)` | 0 |
| TONG_OH | `OH_VC + OH_QLY` | 1 |
| GIA_THANH | `TONG_VL + TONG_NC + TONG_OH` | 1 |
| PROFIT | `$PROFIT_MARGIN * GIA_THANH` | 0 |
| GIA_BAN | `GIA_THANH + PROFIT` | 1 |
| DON_GIA_M2 | `GIA_BAN / TONG_M2` | 0 |
| VAT | `$VAT_RATE * GIA_BAN` | 0 |
| GIA_VAT | `GIA_BAN + VAT` | 1 |

*Đây là **công thức "kim tự tháp giá"** — mỗi dòng dùng lại kết quả của (các) dòng phía trên. Engine tự nhận ra thứ tự tính đúng nhờ DAG (xem phần 4). Toàn bộ tài liệu này sẽ đi theo đúng 14 dòng này ở phần 7.*

### 2.15. AL Variable Set `VS-CDMQ`

| var_name | var_type | default_val | Ý nghĩa |
|---|---|---|---|
| W_mm | FLOAT | 2400 | Chiều rộng ô cửa (mm) |
| H_mm | FLOAT | 2600 | Chiều cao ô cửa (mm) |
| TransomHeight_mm | FLOAT | 600 | Chiều cao ô kính cố định phía trên (mm) |
| n_canh | INT | 2 | Số cánh mở quay |
| mau_nhom | LINK → AL Color Standard | WHITE | Màu nhôm — dùng chung cho toàn bộ 10 dòng nhôm |
| xuat_xu_nhom | SELECT | IMPORT | Xuất xứ nhôm |
| do_day_nhom | INT | 20 | Độ dày lớp sơn/anode (micron) |
| be_mat_nhom | SELECT | POWDER_COATED | Kiểu bề mặt hoàn thiện |

**Vì sao 4 biến màu/xuất xứ/độ dày/bề mặt nằm ở đây thay vì lặp lại trên từng dòng BOM?** Vì trong thực tế nghiệp vụ, **toàn bộ khung + cánh + nẹp của 1 bộ cửa luôn cùng 1 màu** — khai báo 1 lần ở cấp báo giá, rồi để mọi dòng nhôm tự "thừa hưởng" khi tra giá, thay vì phải nhập lại JSON màu trên từng dòng (dễ gõ sai, khó sửa hàng loạt khi đổi màu).

---

## 3. CẤU HÌNH SẢN PHẨM MẪU — BOM 17 DÒNG (`AL Profile Set: PS-CDMQ-2C`)

Đây là bảng quan trọng nhất — nó chính là "công thức cắt" của sản phẩm, người thiết kế sản phẩm nhập 1 lần, dùng lại cho mọi báo giá sau này.

| sort | slug | line_type | width (mm) | height (mm) | qty | Cách chọn Item | cost_bucket | calc_pattern |
|---|---|---|---|---|---|---|---|---|
| 10 | khung_ngang_tren | NHOM | `W_mm` | – | `1` | Fixed: XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT |
| 20 | khung_ngang_duoi | NHOM | `W_mm` | – | `1` | Fixed: XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT |
| 30 | khung_dung | NHOM | `H_mm` | – | `2` | Fixed: XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT |
| 40 | do_ngang | NHOM | `W_mm - 2*$OFFSET_DO_NGANG` | – | `1` | Fixed: XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT |
| 50 | canh_ngang | NHOM | `W_mm/n_canh - $OFFSET_FRAME` | – | `2*n_canh` | Fixed: XF55-CANH-20 | VL_NHOM | LENGTH_TO_WEIGHT |
| 60 | canh_dung | NHOM | `(H_mm-TransomHeight_mm) - $OFFSET_FRAME` | – | `2*n_canh` | Fixed: XF55-CANH-20 | VL_NHOM | LENGTH_TO_WEIGHT |
| 70 | kinh_tren | KINH | `W_mm - 2*$OFFSET_FIXED` | `TransomHeight_mm - $OFFSET_FIXED` | `1` | Fixed: KINH-LOWE-24 | VL_KINH | AREA |
| 80 | kinh_duoi | KINH | `W_mm/n_canh - $OFFSET_GLASS` | `(H_mm-TransomHeight_mm) - $OFFSET_GLASS` | `n_canh` | Fixed: KINH-LOWE-24 | VL_KINH | AREA |
| 90 | nep_kinh_tren | NHOM | `2*(items.kinh_tren.width + items.kinh_tren.height)` | – | `2` | Rule (`items.kinh_tren.glass_thick`) → RULE-NEP-GLASSTHICK | VL_NHOM | LENGTH_TO_WEIGHT |
| 100 | nep_kinh_duoi | NHOM | `2*(items.kinh_duoi.width + items.kinh_duoi.height)` | – | `2*n_canh` | Rule (`items.kinh_duoi.glass_thick`) → RULE-NEP-GLASSTHICK | VL_NHOM | LENGTH_TO_WEIGHT |
| 110 | keo_tren | VTP | `2*(items.kinh_tren.width + items.kinh_tren.height)` | – | `1` | Rule (`items.kinh_tren.glass_type`) → RULE-KEO-GLASSTYPE | VL_VTP | LENGTH_ONLY |
| 120 | keo_duoi | VTP | `2*(items.kinh_duoi.width + items.kinh_duoi.height)` | – | `n_canh` | Rule (`items.kinh_duoi.glass_type`) → RULE-KEO-GLASSTYPE | VL_VTP | LENGTH_ONLY |
| 130 | gioang | VTP | `items.khung_ngang_tren.width + items.khung_ngang_duoi.width + 2*items.khung_dung.width` | – | `1` | Fixed: GIO-EPDM-55 | VL_VTP | LENGTH_ONLY |
| 140 | vit | VTP | – | – | `10*n_canh + 8` | Fixed: VIT-TK-35X16 | VL_VTP | COUNT |
| 150 | tay_nam | PHU_KIEN | – | – | `1` | Fixed: KL-MZS20 | VL_PK | COUNT |
| 160 | khoa | PHU_KIEN | – | – | `1` | Fixed: KL-KHOA-01 | VL_PK | COUNT |
| 170 | ban_le | PHU_KIEN | – | – | `roundup(H_mm/700,0)*n_canh` | Fixed: KL-T-MJ06 | VL_PK | COUNT |

**3 điều quan trọng cần nhìn ra trong bảng này:**

1. **Cột `width`/`height`/`qty` là công thức, không phải số cố định** — chúng được tính dựa trên biến của Variable Set (`W_mm`, `H_mm`...) và hằng số offset (`$OFFSET_FRAME`...). Đây là lý do đổi kích thước cửa thì toàn bộ BOM tự tính lại.
2. **`items.<slug>.<field>` là cách một dòng "nhìn" sang dòng khác** — ví dụ dòng 90 (`nep_kinh_tren`) cần biết `width` và `height` **đã được tính xong** của dòng 70 (`kinh_tren`) để tính chu vi nẹp. Đây gọi là **tham chiếu chéo (cross-row reference)** — chính là lý do phải cần một engine giải DAG, không thể tính tuần tự từ trên xuống dưới một cách ngây thơ (dòng 90 phải đợi dòng 70 tính xong trước).
3. **`item_selection_mode = Rule`** (dòng 90, 100, 110, 120) nghĩa là Item không cố định — nó được **tra động** dựa trên input là dữ liệu của dòng khác (`items.kinh_tren.glass_thick`). Đây là lý do 2 Rule ở mục 2.9 tồn tại.

---

## 4. FORMULA ENGINE HOẠT ĐỘNG NHƯ THẾ NÀO?

### 4.1. Engine nhận vào gì, trả ra gì?

Engine (`FlexibleFormulaEngine`) không biết gì về "cửa nhôm". Nó chỉ nhận 2 thứ:

- **`formulas`**: một dictionary, ví dụ (rút gọn, chỉ lấy dòng `khung_ngang_tren` và `do_ngang` để minh họa cách cross-row hoạt động):
  ```python
  formulas = {
      "items.khung_ngang_tren.width":  "W_mm",
      "items.khung_ngang_tren.qty":    "1",
      "items.do_ngang.width":          "W_mm - 2*$OFFSET_DO_NGANG",
      "items.do_ngang.qty":            "1",
      "items.<slug>.so_luong_don_vi":  "lookup_calc_pattern(calc_pattern, width, height, trong_luong_rieng)",
      "items.<slug>.tong_so_luong":    "so_luong_don_vi * qty",
      "items.<slug>.thanh_tien":       "tong_so_luong * don_gia",
      # ... lặp lại cho toàn bộ 17 slug
  }
  ```
- **`inputs`**: dictionary giá trị đã biết trước, ví dụ:
  ```python
  inputs = {
      "W_mm": 2400, "H_mm": 2600, "TransomHeight_mm": 600, "n_canh": 2,
      "OFFSET_FRAME": 48, "OFFSET_GLASS": 90, "OFFSET_FIXED": 50, "OFFSET_DO_NGANG": 48,
      "items.khung_ngang_tren.trong_luong_rieng": 1.257,
      "items.khung_ngang_tren.don_gia": 113000,
      "items.khung_ngang_tren.calc_pattern": "LENGTH_TO_WEIGHT",
      # ... lặp lại cho từng slug (đây chính là "row_literals" từ B2.5, xem phần 5)
  }
  ```

Engine trả về `result` — cùng cấu trúc như `formulas` nhưng mỗi ô đã được thay bằng **con số đã tính xong**.

### 4.2. DAG là gì và vì sao cần nó?

**DAG (Directed Acyclic Graph — đồ thị có hướng không chu trình)** là cách engine biểu diễn "cái gì phụ thuộc vào cái gì". Với ví dụ này:

```
W_mm ──────────────► items.khung_ngang_tren.width ──► so_luong_don_vi ──► tong_so_luong ──► thanh_tien
                                                              ▲
items.khung_ngang_tren.trong_luong_rieng ────────────────────┘

items.kinh_tren.width ──► items.nep_kinh_tren.width (= 2*(kinh_tren.width + kinh_tren.height))
items.kinh_tren.height ──┘                          │
                                                       ▼
                                          items.nep_kinh_tren.so_luong_don_vi ──► ... ──► thanh_tien
```

Engine làm 3 việc theo đúng thứ tự:

1. **Parse (đọc) từng công thức** — nhận diện biến nào được tham chiếu trong mỗi công thức (kể cả tham chiếu dạng `items.<slug>.<field>`).
2. **Xây DAG** — với mỗi công thức, tạo một "cạnh" nối từ các biến nó phụ thuộc tới chính nó. Ví dụ `items.nep_kinh_tren.width` có cạnh đi vào từ `items.kinh_tren.width` và `items.kinh_tren.height`.
3. **Sắp xếp tô-pô (topological sort)** — tính ra một **thứ tự tính hợp lệ duy nhất**: biến nào không phụ thuộc gì (như `W_mm`, hằng số) được tính trước; biến nào phụ thuộc biến khác chỉ được tính **sau khi** tất cả biến nó phụ thuộc đã có giá trị.

**Vì sao đây là điều bắt buộc, không thể tính "từ trên xuống dưới theo `sort`"?** Vì `sort=90` (`nep_kinh_tren`) phụ thuộc vào kết quả của `sort=70` (`kinh_tren`) — nếu chỉ đơn giản tính tuần tự theo `sort` thì trùng hợp đúng thứ tự ở ví dụ này, nhưng **không có gì đảm bảo điều đó luôn đúng** với BOM khác (ví dụ nếu người thiết kế đặt `nep_kinh_tren` ở `sort=15`, tính trước `kinh_tren` thì sẽ ra lỗi "biến chưa tồn tại" nếu tính ngây thơ theo thứ tự nhập liệu). DAG giải quyết vấn đề này một cách tổng quát — **không phụ thuộc thứ tự người dùng nhập**, chỉ phụ thuộc *quan hệ toán học thật sự* giữa các biến.

### 4.3. Vì sao `lookup_calc_pattern` KHÔNG được gọi ngược lại engine?

Đây là lỗi kiến trúc mà bản v26/Grok từng mắc ở phiên bản trước, đã được xác định và sửa trong v27 — đáng nhắc lại vì đây là **bài học chung cho việc đăng ký hàm custom vào bất kỳ engine DAG nào**:

- `lookup_calc_pattern(calc_pattern, width, height, trong_luong_rieng)` bản thân nó **là một hàm được engine gọi** khi nó đang tính node `so_luong_don_vi` (tức là engine đang *ở giữa* một lượt `calculate()`).
- Nếu bên trong hàm này lại **quay lại gọi `FlexibleFormulaEngine.evaluate_single(...)`** (khởi tạo một engine "con" để "diễn giải" chuỗi công thức `(width/1000)*trong_luong_rieng` lấy từ bảng `AL Quantity Calc Method`), thì đây là **gọi đệ quy vào chính engine đang chạy** — vừa chậm (parse + build DAG lại cho từng dòng × mỗi lần tính, dù chỉ có 4 pattern cố định), vừa làm hỏng khả năng `explain()`/trace của lượt tính "cha" (vì phép tính con nằm ngoài DAG chính).
- **Cách làm đúng:** vì chỉ có đúng 4 pattern cố định và đã biết trước, `lookup_calc_pattern` chỉ cần là **1 dispatch table Python thuần** (if/elif), không đụng gì tới engine:

```python
def lookup_calc_pattern(calc_pattern_code, width=None, height=None, trong_luong_rieng=None):
    w = (width or 0) / 1000
    h = (height or 0) / 1000
    tlr = trong_luong_rieng or 0
    if calc_pattern_code == "LENGTH_TO_WEIGHT":
        return w * tlr
    if calc_pattern_code == "AREA":
        return w * h
    if calc_pattern_code == "LENGTH_ONLY":
        return w
    if calc_pattern_code == "COUNT":
        return 1
    frappe.throw(f"calc_pattern_code '{calc_pattern_code}' chưa được hỗ trợ")
```

Hàm này được truyền vào engine lúc khởi tạo qua tham số `extra_funcs` — engine gọi nó như một hàm toán học bình thường (giống `sum()`, `roundup()`), không biết và không cần biết bên trong nó làm gì.

### 4.4. Cross-row reference hoạt động ra sao?

Cú pháp `items.<slug>.<field>` được engine hiểu nhờ cấu hình `child_table_configs={"items": {"id_field": "slug"}}` lúc khởi tạo — nó báo cho engine biết: *"có một bảng con tên là `items`, mỗi dòng của nó được định danh bằng field `slug`, và công thức có thể tham chiếu chéo giữa các dòng bằng cú pháp `items.<slug>.<field>`"*. Nhờ vậy dòng 90 viết được công thức `items.kinh_tren.width + items.kinh_tren.height` mà không cần biết trước `kinh_tren` được tính ra bao nhiêu — engine tự lo phần đó qua DAG.

---

## 5. BOMORCHESTRATOR — 7 PHASE (v28.2), VỚI SỐ LIỆU THẬT CỦA VÍ DỤ NÀY

**Input của người dùng (Quotation):**
```
W_mm = 2400          H_mm = 2600          TransomHeight_mm = 600      n_canh = 2
mau_nhom = WHITE      xuat_xu_nhom = IMPORT      do_day_nhom = 20      be_mat_nhom = POWDER_COATED
```

### B0 — Version Pinning
Xác định phiên bản hiệu lực (tại thời điểm tạo báo giá) của `AL BOM Version`, các Rule, và `Formula Global Variable`. Với ví dụ này: chốt `bom_version_id = BOM-CDMQ-2C-v1`, không có version Rule nào khác 1. Mục đích: nếu sau này đổi giá hoặc đổi offset, báo giá cũ **vẫn tính ra đúng số cũ** khi mở lại (tái lập được).

### B1 — VariableResolver
Gom toàn bộ input trên vào 1 dictionary `inputs`, cộng thêm hằng số từ `AL Calculation Rule`:
```
inputs = {
  W_mm: 2400, H_mm: 2600, TransomHeight_mm: 600, n_canh: 2,
  mau_nhom: "WHITE", xuat_xu_nhom: "IMPORT", do_day_nhom: 20, be_mat_nhom: "POWDER_COATED",
  OFFSET_FRAME: 48, OFFSET_GLASS: 90, OFFSET_FIXED: 50, OFFSET_DO_NGANG: 48,
  NC_SX_PCT: 0.08, NC_LD_PCT: 0.12, OH_VC_PCT: 0.03, OH_QLY_PCT: 0.03,
  PROFIT_MARGIN: 0.16, VAT_RATE: 0.10
}
```
**Chưa** có `glass_thick`/`glass_type`/`trong_luong_rieng`/`don_gia` — các giá trị này cần **tra cứu từ database**, thuộc về B2.

### B2 — Pre-fetch Master Data (DataSourceResolver + FB BatchBindingResolver) ← NEW v28.2

**Thay đổi lớn so với bản cũ:** B2 không còn là 85 dòng code batch query rời rạc (B2a + B2.5 + B2b cũ). Thay vào đó, **DataSourceResolver** — 1 lớp mỏng ~80 dòng — ủy thác toàn bộ việc gom nhóm query, cache, transform cho **FB BatchBindingResolver**:

```python
# alumglass/engine/data_source_resolver.py
from formula_builder.api.batch_binding_resolver import BatchBindingResolver

class DataSourceResolver:
    def resolve_all(self, bom_items, inputs, bucket_definitions):
        # 1. Build Formula Variable Bindings từ Cost Bucket definitions
        bindings = self._build_bindings(bucket_definitions, bom_items, inputs)
        # 2. Ủy thác FB — tự động gom nhóm → 4-5 batch queries
        resolver = BatchBindingResolver(cache_ttl=300)
        return resolver.resolve_all_batch(bindings, pre_resolved=inputs)
```

**Cơ chế hoạt động:**

```
COLLECT: Duyệt 17 Bom Items × Cost Bucket definitions
  → Thu thập TẤT CẢ data sources cần fetch:
    • 8 Item weights (dòng NHOM)
    • 13 Item Prices (composite key: màu, xuất xứ, độ dày, bề mặt)
    • 2 Glass Master (dòng KINH)
    • 4 Dynamic Rules (nep, keo)

GROUP: Gom theo batch_group
  → Batch 1: ITEM_WEIGHT — SELECT weight_per_unit FROM tabItem WHERE name IN (8 items)
  → Batch 2: ITEM_PRICE — SELECT price_list_rate FROM tabItem Price WHERE item_code IN (13 items) AND custom_mau_sac='WHITE' AND ...
  → Batch 3: GLASS_MASTER — SELECT * FROM tabAL Glass Master WHERE name IN (2 glasses)
  → Batch 4: RULES — RuleEngine.resolve_batch()

EXECUTE: 4 queries (thay vì 34 nếu gọi riêng lẻ)
  → Giảm 88% queries

INJECT: Map kết quả về row_literals
  → {slug__trong_luong_rieng: 1.257, slug__don_gia: 113000, ...}
```

**Kết quả B2 (`row_literals`):**

| slug | trong_luong_rieng | don_gia | glass_thick | glass_type |
|---|---|---|---|---|
| khung_ngang_tren | 1.257 | 113,000 | – | – |
| khung_ngang_duoi | 1.257 | 113,000 | – | – |
| khung_dung | 1.257 | 113,000 | – | – |
| do_ngang | 1.257 | 113,000 | – | – |
| canh_ngang | 1.350 | 113,000 | – | – |
| canh_dung | 1.350 | 113,000 | – | – |
| kinh_tren | – | 1,150,000 | **24** | **LOWE** |
| kinh_duoi | – | 1,150,000 | **24** | **LOWE** |
| nep_kinh_tren | 0.312 | 113,000 | – | – |
| nep_kinh_duoi | 0.312 | 113,000 | – | – |
| keo_tren | – | 45,000 | – | – |
| keo_duoi | – | 45,000 | – | – |
| gioang | – | 1,250 | – | – |
| vit | – | 850 | – | – |
| tay_nam | – | 210,000 | – | – |
| khoa | – | 350,000 | – | – |
| ban_le | – | 180,000 | – | – |

**Dynamic Rule cũng được resolve trong cùng B2** — khi `glass_thick`/`glass_type` đã có, RuleEngine chọn Item đúng (C3211-20, KEO-TT-01) và cập nhật `trong_luong_rieng` tương ứng.

> **Khác biệt chính:** Khi thêm Cost Bucket mới (VD: `CP_VAN_CHUYEN` query từ `Transport Rate`), B2 **không cần sửa code** — chỉ cần thêm 1 record AL Cost Bucket với `source_type=doctype_query` và `source_config` phù hợp. DataSourceResolver tự động thêm vào batch group tương ứng.

### B3 — Build Bom Engine (FormulaEngine với cross-row reference)

Dùng `FormulaEngine` trực tiếp (Path B — `build_cross_ref_engine`):

1. Duyệt 17 Bom Items, thu thập công thức `width`, `height`, `qty` từ mỗi dòng
2. Normalize cross-row reference: `items.kinh_tren.width` → `kinh_tren__width`
3. Inject literal values từ row_literals vào inputs với naming `{slug}__{field}`
4. Thêm 3 công thức từ Formula Set `BOM_LINE` cho mỗi dòng
5. Kết quả: ~100 formulas cho FormulaEngine

```python
engine = FormulaEngine(
    formulas=formulas,
    on_error="raise",
    deterministic=True,
    safe_funcs={"lookup_calc_pattern": lookup_calc_pattern},
)
```

### B4 — Calculate Bom Items (engine.calculate())

```python
result = engine.calculate(bom_inputs)
# → flat dict: {khung_ngang_tren__width: 2400, ..., khung_ngang_tren__thanh_tien: 340898, ...}
```

Engine tự động: parse ~100 công thức, build DAG (~93 nodes, ~120 edges), topological sort, evaluate. Kết quả chi tiết ở **phần 6**.

### B5 — Gom Cost Bucket (Python loop)

```python
buckets = defaultdict(float)
for item in self.bom_items:
    slug = item["slug"]
    thanh_tien = result.get(f"{slug}__thanh_tien", 0)
    bucket_code = item.get("cost_bucket")
    if bucket_code:
        buckets[bucket_code] += thanh_tien
```

| Bucket | Tổng (VND) |
|---|---|
| VL_NHOM | 4,895,431 |
| VL_KINH | 6,330,980 |
| VL_VTP | 836,400 |
| VL_PK | 2,000,000 |

### B6 — Cost Template (FlexibleFormulaEngine)

Đưa bucket values + inputs vào `FlexibleFormulaEngine` với 14 `global_formulas`:

```python
cost_inputs = {**user_inputs, **calc_rules, **global_vars, **buckets}
cost_config = EngineConfig(global_formulas=cost_template_formulas, extra_context=cost_inputs)
engine2 = FlexibleFormulaEngine(cost_config)
cost_result = engine2.calculate(cost_inputs)
```

Kết quả: `GIA_VAT = 22,717,289 VND`. Chi tiết ở **phần 7**.

### B7 — Save Results + Snapshot
Lưu chi tiết 17 dòng vào child table `al_bom_line_results` của Quotation Item; lưu toàn bộ `inputs`, `formulas`, `result`, `bom_version_id` vào `ConfigSnapshot` để có thể tái lập/giải trình lại chính xác sau này (kể cả khi giá hoặc offset đã đổi).

---

## 6. BẢNG TÍNH CHI TIẾT TOÀN BỘ 17 DÒNG (B5 — MỞ RỘNG TỪNG PHÉP THAY SỐ)

Dưới đây là cách engine tính **từng dòng**, viết ra đầy đủ phép thay số (không chỉ nêu kết quả) cho các dòng đại diện mỗi loại (`NHOM` đơn giản, `NHOM` cross-row, `KINH`, `VTP` cross-row, `PHU_KIEN`) — các dòng còn lại áp dụng đúng cùng cơ chế.

### 6.1. Dòng NHOM đơn giản — `khung_ngang_tren`
- `width = W_mm = 2400`
- `qty = 1`
- `calc_pattern = LENGTH_TO_WEIGHT`, `trong_luong_rieng = 1.257` (từ B2.5)
- `so_luong_don_vi = lookup_calc_pattern("LENGTH_TO_WEIGHT", 2400, None, 1.257) = (2400/1000) × 1.257 = 2.4 × 1.257 = 3.0168 kg`
- `tong_so_luong = 3.0168 × 1 = 3.0168 kg`
- `don_gia = 113,000` (từ B2.5, theo tổ hợp WHITE/IMPORT/20/POWDER_COATED)
- `thanh_tien = 3.0168 × 113,000 = 340,898`

### 6.2. Dòng NHOM có offset — `do_ngang`
- `width = W_mm - 2×$OFFSET_DO_NGANG = 2400 - 2×48 = 2400 - 96 = 2304`
- `qty = 1`
- `so_luong_don_vi = (2304/1000) × 1.257 = 2.304 × 1.257 = 2.8961 kg`
- `tong_so_luong = 2.8961 × 1 = 2.8961 kg`
- `thanh_tien = 2.8961 × 113,000 = 327,259`

### 6.3. Dòng NHOM chia theo số cánh — `canh_ngang`
- `width = W_mm/n_canh - $OFFSET_FRAME = 2400/2 - 48 = 1200 - 48 = 1152`
- `qty = 2×n_canh = 2×2 = 4` *(mỗi cánh có 2 thanh ngang: trên + dưới)*
- `so_luong_don_vi = (1152/1000) × 1.350 = 1.152 × 1.350 = 1.5552 kg` *(chú ý: `canh_ngang`/`canh_dung` dùng profile `XF55-CANH-20`, trọng lượng riêng 1.350 kg/m — khác với khung 1.257 kg/m)*
- `tong_so_luong = 1.5552 × 4 = 6.2208 kg`
- `thanh_tien = 6.2208 × 113,000 = 702,950`

### 6.4. Dòng KINH — `kinh_tren`
- `width = W_mm - 2×$OFFSET_FIXED = 2400 - 2×50 = 2400 - 100 = 2300`
- `height = TransomHeight_mm - $OFFSET_FIXED = 600 - 50 = 550`
- `qty = 1`
- `calc_pattern = AREA` → `so_luong_don_vi = (2300/1000) × (550/1000) = 2.3 × 0.55 = 1.265 m²`
- `tong_so_luong = 1.265 × 1 = 1.265 m²`
- `don_gia = 1,150,000` (giá kính Low-E 24mm)
- `thanh_tien = 1.265 × 1,150,000 = 1,454,750`

### 6.5. Dòng NHOM cross-row — `nep_kinh_tren` (đây là dòng minh họa rõ nhất cơ chế DAG)
- **Item được chọn động qua Rule** (đã resolve ở B2b): `glass_thick = items.kinh_tren.glass_thick = 24` → Rule trả về `C3211-20` (0.312 kg/m)
- `width = 2×(items.kinh_tren.width + items.kinh_tren.height)` — **đọc trực tiếp kết quả đã tính ở dòng 6.4**, không tính lại:
  `= 2×(2300 + 550) = 2×2850 = 5700`
- `qty = 2` *(2 nẹp mỗi kính: trên + dưới)*
- `so_luong_don_vi = (5700/1000) × 0.312 = 5.7 × 0.312 = 1.7784 kg`
- `tong_so_luong = 1.7784 × 2 = 3.5568 kg`
- `thanh_tien = 3.5568 × 113,000 = 401,918`

### 6.6. Dòng VTP cross-row — `keo_tren`
- **Item động qua Rule**: `glass_type = items.kinh_tren.glass_type = "LOWE"` → `KEO-TT-01` (45,000đ/m)
- `width = 2×(items.kinh_tren.width + items.kinh_tren.height) = 5700` *(cùng công thức chu vi như nẹp, dùng lại kết quả của `kinh_tren`)*
- `qty = 1`
- `calc_pattern = LENGTH_ONLY` → `so_luong_don_vi = 5700/1000 = 5.7 m`
- `tong_so_luong = 5.7 × 1 = 5.7 m`
- `thanh_tien = 5.7 × 45,000 = 256,500`

### 6.7. Dòng VTP đo theo cái — `vit`
- `qty = 10×n_canh + 8 = 10×2 + 8 = 28`
- `calc_pattern = COUNT` → `so_luong_don_vi = 1` *(không phụ thuộc width/height)*
- `tong_so_luong = 1 × 28 = 28 cái`
- `thanh_tien = 28 × 850 = 23,800`

### 6.8. Dòng PHỤ KIỆN — `ban_le`
- `qty = roundup(H_mm/700, 0) × n_canh = roundup(2600/700, 0) × 2 = roundup(3.714, 0) × 2 = 4 × 2 = 8` *(làm tròn lên: cứ mỗi 700mm chiều cao cần thêm 1 bản lề)*
- `so_luong_don_vi = 1` (COUNT)
- `tong_so_luong = 1 × 8 = 8 cái`
- `thanh_tien = 8 × 180,000 = 1,440,000`

### 6.9. Bảng tổng hợp toàn bộ 17 dòng

| slug | width | height | qty | so_luong_don_vi | tong_so_luong | thành tiền (VND) |
|---|---|---|---|---|---|---|
| khung_ngang_tren | 2400 | – | 1 | 3.0168 kg | 3.0168 kg | 340,898 |
| khung_ngang_duoi | 2400 | – | 1 | 3.0168 kg | 3.0168 kg | 340,898 |
| khung_dung | 2600 | – | 2 | 3.2682 kg | 6.5364 kg | 738,613 |
| do_ngang | 2304 | – | 1 | 2.8961 kg | 2.8961 kg | 327,259 |
| canh_ngang | 1152 | – | 4 | 1.5552 kg | 6.2208 kg | 702,950 |
| canh_dung | 1952 | – | 4 | 2.6352 kg | 10.5408 kg | 1,191,110 |
| kinh_tren | 2300 | 550 | 1 | 1.265 m² | 1.265 m² | 1,454,750 |
| kinh_duoi | 1110 | 1910 | 2 | 2.1201 m² | 4.2402 m² | 4,876,230 |
| nep_kinh_tren | 5700 | – | 2 | 1.7784 kg | 3.5568 kg | 401,918 |
| nep_kinh_duoi | 6040 | – | 4 | 1.88448 kg | 7.53792 kg | 851,785 |
| keo_tren | 5700 | – | 1 | 5.7 m | 5.7 m | 256,500 |
| keo_duoi | 6040 | – | 2 | 6.04 m | 12.08 m | 543,600 |
| gioang | 10000 | – | 1 | 10 m | 10 m | 12,500 |
| vit | – | – | 28 | 1 | 28 cái | 23,800 |
| tay_nam | – | – | 1 | 1 | 1 cái | 210,000 |
| khoa | – | – | 1 | 1 | 1 cái | 350,000 |
| ban_le | – | – | 8 | 1 | 8 cái | 1,440,000 |

*(Dòng `canh_dung`: `width = (H_mm - TransomHeight_mm) - $OFFSET_FRAME = (2600-600)-48 = 1952`; `nep_kinh_duoi`, `keo_duoi`, `gioang`, `kinh_duoi` áp dụng đúng cơ chế cross-row/offset như các ví dụ mở rộng ở trên, chỉ khác slug tham chiếu.)*

---

## 7. COST TEMPLATE — TỪ TỔNG VẬT LIỆU RA GIÁ BÁN CÓ VAT (B5 + B6)

### 7.1. B5 — Gom cost bucket

Cộng cột "thành tiền" của bảng 6.9 theo `cost_bucket` mà mỗi dòng được gán ở mục 3:

| Bucket | Các dòng cộng vào | Tổng (VND) |
|---|---|---|
| **VL_NHOM** | khung_ngang_tren + khung_ngang_duoi + khung_dung + do_ngang + canh_ngang + canh_dung + nep_kinh_tren + nep_kinh_duoi | 340,898+340,898+738,613+327,259+702,950+1,191,110+401,918+851,785 = **4,895,431** |
| **VL_KINH** | kinh_tren + kinh_duoi | 1,454,750+4,876,230 = **6,330,980** |
| **VL_VTP** | keo_tren + keo_duoi + gioang + vit | 256,500+543,600+12,500+23,800 = **836,400** |
| **VL_PK** | tay_nam + khoa + ban_le | 210,000+350,000+1,440,000 = **2,000,000** |

### 7.2. B6 — Tính từng dòng Cost Template, theo đúng thứ tự DAG

Engine tự xác định thứ tự đúng (không phải thứ tự liệt kê trong bảng mục 2.14) — nhưng để dễ đọc, thứ tự dưới đây **chính là thứ tự tô-pô mà engine sẽ chạy**, vì mỗi dòng chỉ dùng kết quả của dòng phía trên nó:

| # | line_code | Công thức thay số | Kết quả (VND) |
|---|---|---|---|
| 1 | TONG_VL | `4,895,431 + 6,330,980 + 836,400 + 2,000,000` | **14,062,811** |
| 2 | TONG_M2 | `(2400/1000) × (2600/1000) = 2.4 × 2.6` | 6.24 m² |
| 3 | NC_SX | `0.08 × 14,062,811` | 1,125,025 |
| 4 | NC_LD | `0.12 × 14,062,811` | 1,687,537 |
| 5 | TONG_NC | `1,125,025 + 1,687,537` | **2,812,562** |
| 6 | OH_VC | `0.03 × 14,062,811` | 421,884 |
| 7 | OH_QLY | `0.03 × (14,062,811 + 2,812,562) = 0.03 × 16,875,373` | 506,261 |
| 8 | TONG_OH | `421,884 + 506,261` | **928,145** |
| 9 | GIA_THANH | `14,062,811 + 2,812,562 + 928,145` | **17,803,518** |
| 10 | PROFIT | `0.16 × 17,803,518` | 2,848,563 |
| 11 | GIA_BAN | `17,803,518 + 2,848,563` | **20,652,081** |
| 12 | DON_GIA_M2 | `20,652,081 / 6.24` | 3,309,628 |
| 13 | VAT | `0.10 × 20,652,081` | 2,065,208 |
| 14 | GIA_VAT | `20,652,081 + 2,065,208` | **22,717,289** |

**Vì sao thứ tự này bắt buộc, không thể tính `OH_QLY` trước `TONG_NC`?** Vì công thức `OH_QLY = $OH_QLY_PCT * (TONG_VL + TONG_NC)` **tham chiếu trực tiếp** tới `TONG_NC` — DAG buộc `TONG_NC` (và cả `NC_SX`, `NC_LD` mà `TONG_NC` phụ thuộc) phải được tính xong trước. Đây là ví dụ thứ hai (sau phần 6.5) cho thấy DAG không phải là chi tiết kỹ thuật phụ — nó là **lý do duy nhất** khiến hệ thống tính đúng thứ tự dù công thức được nhập theo bất kỳ trật tự nào trong bảng cấu hình.

### 7.3. Kết quả cuối cùng

> **GIA_VAT = 22,717,289đ** — đây là giá bán đã bao gồm VAT 10%, hiển thị cho khách hàng trên báo giá.
> Giá/m² tham khảo (`DON_GIA_M2`, chưa VAT): **3,309,628đ/m²**.

---

## 8. THÊM NGUỒN DATA MỚI KHÔNG CẦN CODE (FB v31)

Đây là sức mạnh lớn nhất của thiết kế v28.2: **mọi Cost Bucket mới là 1 dòng khai báo JSON, không cần code Python, không cần deploy.**

### 8.1. Scenario 1: Thêm bucket CP_BAO_HANH (formula)

**Yêu cầu:** Dự phòng bảo hành = 2% giá thành.

**Cách làm (user, 3 phút):**
```
Bước 1: Tạo AL Cost Bucket
  bucket_code: CP_BAO_HANH
  bucket_role: LEAF
  parent_bucket: TONG_OH
  source_type: formula
  source_config: {"formula": "0.02 * GIA_THANH"}
  depends_on: ["GIA_THANH"]

Bước 2: Thêm 1 dòng vào Cost Template
  line_code: CP_BAO_HANH
  calc_formula: CP_BAO_HANH

Bước 3: Cập nhật TONG_OH
  calc_formula: OH_VC + OH_QLY + CP_BAO_HANH
```

→ **HOÀN THÀNH.** Không code, không deploy, không restart server.

### 8.2. Scenario 2: Thêm bucket CP_VAN_CHUYEN (DB query)

**Yêu cầu:** Tra bảng `Transport Rate` theo kho xuất + quận công trình.

**Cách làm (user, 5 phút):**
```json
// AL Cost Bucket
{
  "bucket_code": "CP_VAN_CHUYEN",
  "bucket_role": "LEAF",
  "parent_bucket": "TONG_OH",
  "source_type": "doctype_query",
  "source_config": {
    "doctype": "Transport Rate",
    "fieldname": "rate_per_km",
    "aggregate": "first",
    "filters": [
      ["from_location", "=", "{inputs.kho_xuat}"],
      ["to_district", "=", "{inputs.quan_cong_trinh}"],
      ["vehicle_type", "=", "{inputs.loai_xe}"]
    ]
  },
  "depends_on": ["kho_xuat", "quan_cong_trinh", "loai_xe"],
  "batch_group": "TRANSPORT"
}
```

→ FB BatchBindingResolver tự động gom query này vào batch group `TRANSPORT`. Nếu có 5 bucket khác cùng query `Transport Rate` → vẫn chỉ 1 query nhờ batch grouping.

### 8.3. Scenario 3: Thêm bucket CP_NHAN_CONG_CONG_TRINH (SUM từ doctype khác)

**Yêu cầu:** Tổng lương từ `Salary Slip` của công trình.

```json
{
  "bucket_code": "CP_NHAN_CONG",
  "source_type": "doctype_query",
  "source_config": {
    "doctype": "Salary Slip",
    "fieldname": "total_salary",
    "aggregate": "sum",
    "filters": [
      ["project", "=", "{inputs.project_code}"],
      ["docstatus", "=", 1]
    ]
  },
  "transform": {"round": -3}
}
```

### 8.4. Scenario 4: Đăng ký custom handler cho nghiệp vụ đặc thù

Khi `doctype_query` không đủ (VD: cần JOIN 2 bảng, gọi API ngoài), dev viết handler **1 lần**, user dùng **mãi mãi**:

```python
# alumglass/hooks.py
fb_source_types = ["alumglass.fb_handlers.get_coating_cost"]

# alumglass/fb_handlers.py
from formula_builder.api.source_type_registry import register_source

@register_source("get_coating_cost",
    label="Coating Cost Calculator",
    description="Calculate coating cost based on total kg + color + surface",
    config_schema={...},
    app="alumglass",
    batchable=True,
)
def _handle_coating_cost(binding, doc, resolved_so_far):
    cfg = json.loads(binding.get("source_config", "{}"))
    total_kg = float(resolved_so_far.get("TONG_KG_NHOM", 0))
    color = resolved_so_far.get("mau_nhom", "WHITE")
    surface = resolved_so_far.get("be_mat_nhom", "POWDER_COATED")
    rate = frappe.db.get_value("Coating Price",
        {"color": color, "surface": surface}, "price_per_kg") or 0
    return total_kg * rate
```

Sau đó user dùng:
```json
{"bucket_code": "CP_GIA_CONG_SON", "source_type": "get_coating_cost",
 "source_config": {}, "depends_on": ["TONG_KG_NHOM", "mau_nhom", "be_mat_nhom"]}
```

### 8.5. So sánh Trước/Sau

| Tiêu chí | Trước (hardcode) | Sau (FB v31 DataSourceResolver) |
|---|---|---|
| Thêm Cost Bucket formula | Sửa orchestrator.py | 1 record AL Cost Bucket |
| Thêm Cost Bucket DB query | Viết hàm batch query mới | JSON config doctype_query |
| Thay đổi nguồn data | Sửa code, test, deploy | Sửa source_config JSON |
| Thêm composite key | Code Python | Thêm filters trong doctype_query |
| Tự động batch query | Code tay từng loại | FB tự gom nhóm |
| Cache strategy | Tự implement Redis | Khai báo cache_ttl |
| Validate config | Lỗi runtime | JSON Schema validation |
| Thời gian | 2-4 giờ (cần dev) | 5-15 phút (user tự làm) |

---

## 9. COMPOSITE TYPES & TRANSFORM — ÁP DỤNG CHO NHÔM KÍNH (FB v31)

### 9.1. Pipeline: Tính giá nhôm full flow

**Yêu cầu:** Giá nhôm = (giá gốc USD × tỷ giá VND) × (1 + thuế) × (1 + margin), làm tròn đến 100đ.

**Trước đây:** Code Python multi-step trong orchestrator hoặc cost_handlers.

**Với FB v31:** 1 config JSON:

```json
{
  "bucket_code": "GIA_NHOM_FINAL",
  "source_type": "pipeline",
  "source_config": {
    "steps": [
      {
        "source_type": "doctype_query",
        "source_config": {
          "doctype": "Item Price", "fieldname": "price_list_rate",
          "filters": [["item_code", "=", "{inputs.price_base_item}"],
                      ["custom_mau_sac", "=", "{inputs.mau_nhom}"]]
        },
        "output_as": "raw_price"
      },
      {
        "source_type": "doctype_query",
        "source_config": {
          "doctype": "Currency Exchange", "fieldname": "exchange_rate",
          "filters": [["from_currency", "=", "USD"], ["to_currency", "=", "VND"]]
        },
        "output_as": "fx_rate"
      },
      {
        "source_type": "computed",
        "source_config": {"formula": "raw_price * fx_rate", "dependencies": ["raw_price", "fx_rate"]},
        "output_as": "price_vnd"
      },
      {
        "source_type": "computed",
        "source_config": {"formula": "price_vnd * (1 + tax) * (1 + margin)", "dependencies": ["price_vnd", "tax", "margin"]},
        "output_as": "final_price"
      }
    ],
    "merge_strategy": "last"
  },
  "transform": {"round": -2}
}
```

**Diễn giải:** Bước 1 lấy giá USD → Bước 2 lấy tỷ giá → Bước 3 quy đổi VND → Bước 4 áp thuế + margin. Tất cả trong 1 config, FB tự chạy tuần tự.

### 9.2. Conditional: Chi phí nhân công theo loại sản phẩm

**Yêu cầu:** Cửa đi 8%, cửa sổ 6%, vách kính 10%, cửa lùa 7%.

```json
{
  "bucket_code": "NC_SX_PCT",
  "source_type": "conditional",
  "source_config": {
    "branches": [
      {"condition": "product_type == 'CUA_DI'", "source_type": "constant", "source_config": {"value": 0.08}},
      {"condition": "product_type == 'CUA_SO'", "source_type": "constant", "source_config": {"value": 0.06}},
      {"condition": "product_type == 'VACH_KINH'", "source_type": "constant", "source_config": {"value": 0.10}},
      {"condition": "product_type == 'CUA_LUA'", "source_type": "constant", "source_config": {"value": 0.07}}
    ],
    "default": {"source_type": "constant", "source_config": {"value": 0.08}}
  }
}
```

### 9.3. Fallback Chain: Giá nhôm LME — resilience

**Yêu cầu:** Lấy giá nhôm từ API LME. Nếu API sập (timeout 3s) → dùng cache Redis. Nếu cache hết hạn → dùng giá manual 2500 USD/tấn.

```json
{
  "bucket_code": "GIA_NHOM_LME",
  "source_type": "fallback_chain",
  "source_config": {
    "chain": [
      {
        "source_type": "custom_function",
        "source_config": {"module": "alumglass.engine.cost_handlers", "function": "fetch_lme_price", "args": {"metal": "ALUMINUM"}},
        "label": "live_lme_api",
        "timeout_ms": 3000
      },
      {
        "source_type": "doctype_query",
        "source_config": {"doctype": "Cached Price", "fieldname": "price", "filters": [["key", "=", "LME_AL"]]},
        "label": "redis_cache"
      },
      {
        "source_type": "constant",
        "source_config": {"value": 2500},
        "label": "manual_override"
      }
    ]
  },
  "transform": {"multiply": 25000, "round": -2}
}
```

### 9.4. Transform Layer — Hậu xử lý không code

| Transform | Config | Kết quả |
|---|---|---|
| USD → VND | `{"multiply": 25000, "round": 0}` | 3.5 → 87,500 |
| mm → m | `{"divide": 1000, "round": 3}` | 2400 → 2.400 |
| Làm tròn giá đến 1000đ | `{"formula": "round(value / 1000, 0) * 1000"}` | 22717289 → 22717000 |
| Giá sau chiết khấu 10% | `{"formula": "value * 0.9", "round": 0}` | 113000 → 101700 |
| Kg → Tấn | `{"divide": 1000, "round": 4, "cast": "float"}` | 3016.8 → 3.0168 |

**Transform được áp dụng tự động** bởi `BatchBindingResolver._apply_transform()` sau mỗi lần resolve — không cần code Python xử lý hậu kỳ.

---

## 10. KIỂM TRA CHÉO & NHỮNG "BẪY" CẦN TRÁNH KHI TRIỂN KHAI

| # | Bẫy | Vì sao xảy ra | Cách tránh |
|---|---|---|---|
| 1 | Gọi lại engine bên trong 1 hàm mà chính engine đang gọi (`lookup_calc_pattern`) | Nhầm giữa "hàm tiện ích thuần" và "một lượt tính DAG mới" | Chỉ dùng dispatch table Python thuần cho các pattern hữu hạn, đã biết trước (phần 4.3) |
| 2 | Tính tuần tự theo cột `sort` thay vì để engine giải DAG | Nhìn có vẻ "chạy từ trên xuống là ổn" với ví dụ cụ thể này | Luôn để engine tự sắp xếp tô-pô — không giả định thứ tự nhập liệu là thứ tự tính đúng |
| 3 | Sai số cộng dồn không bị phát hiện (ví dụ: gõ nhầm 702,**5**50 thay vì 702,**9**50) | Số liệu sai ở 1 dòng chi tiết sẽ lan qua `TONG_VL → GIA_THANH → GIA_BAN → GIA_VAT` vì các bước sau đều là % nhân dồn | Luôn tính lại toàn bộ bằng script (Python/Excel công thức) mỗi khi sửa ví dụ, không copy số cũ rồi sửa tay từng dòng "tưởng bị ảnh hưởng" |
| 4 | Query giá/trọng lượng riêng lẻ cho từng dòng BOM (N+1 query) | Viết code lặp `for line in lines: frappe.db.get_value(...)` | Batch query 1 lần cho toàn bộ danh sách item_code/base_item cần, như B2.5 |
| 5 | Lặp lại JSON màu/xuất xứ/độ dày/bề mặt trên từng dòng NHOM | Tưởng mỗi dòng cần khai báo riêng | Khai báo 1 lần ở `AL Variable Set` cấp báo giá, các dòng NHOM tự thừa hưởng qua `resolve_price_attrs()` |
| 6 | Trùng tổ hợp Item Price (2 dòng giá cho cùng 1 tổ hợp màu/xuất xứ) | Không có ràng buộc unique | Server Script `validate` chặn trùng `(item_code, price_list, mau_sac, xuat_xu, do_day, be_mat)` |
| 7 | Dùng biến phẳng đặt tên riêng (`glass_thick_kinh_tren`) thay vì cross-row | Quen cách viết code thủ tục | Luôn dùng đúng 1 cú pháp `items.<slug>.<field>` cho mọi tham chiếu chéo, không ngoại lệ |

---

## 11. SNAPSHOT PERSISTENCE — LƯU VÀ KHÔI PHỤC KẾT QUẢ TÍNH (🆕 FB v30)

> **Mới từ Formula Builder v30:** `SnapshotManager.submit()` persist toàn bộ 5-layer snapshot
> vào DocType `Formula Snapshot` trong DB. Trước đây (v29) snapshot chỉ là in-memory, mất khi restart.
> Memory-first, Explicit-persist: tạo trong memory trước, chỉ submit khi cần lưu.

### 11.1. Flow tổng quát

```
B4+B6: engine.evaluate() → outputs
         │
         ▼
  SnapshotManager.create(engine, inputs, outputs, tag=ACTUAL, ...)
         │
         ▼
  ┌─────────────────────────────────┐
  │  EnterpriseSnapshot (MEMORY)    │
  │  5 layers: meta, context, DAG,  │
  │            trace, audit         │
  └─────────────┬───────────────────┘
                │
                │ User duyệt báo giá → B7 gọi submit()
                ▼
  ┌─────────────────────────────────┐
  │  tabFormula Snapshot (DB)       │
  │  engine_meta (JSON)    < 2KB   │
  │  dag_structure (JSON)  < 5KB   │
  │  formulas (JSON)       < 5KB   │
  │  business_input (JSON) < 2KB   │
  │  outputs (JSON)        < 2KB   │
  │  execution_trace (JSON) ~4KB   │  ← cost_only: 14 dòng Cost
  │  audit_trail (JSON)    < 1KB   │
  └─────────────┬───────────────────┘
                │
                │ 6 tháng sau — kiểm toán
                ▼
  snap = SnapshotManager.load("snap-id")
  assert snap.verify()  ← payload_hash khớp → dữ liệu nguyên vẹn
                │
                ▼
  Giải trình từng bước Cost:
    TONG_VL = 4,895,431+6,330,980+836,400+2,000,000 = 14,062,811
    NC_SX   = 0.08 × 14,062,811 = 1,125,025
    ...
    GIA_VAT = 20,652,081 + 2,065,208 = 22,717,289 ✅
```

### 11.2. Code trong B7 — tạo và submit snapshot

```python
from formula_builder.formula_utils import (
    SnapshotManager, SnapshotRegistry,
    SnapshotTag, SnapshotStatus, TraceLevel,
)

_registry = SnapshotRegistry()  # In-memory cho request hiện tại

def b7_save_snapshot(orchestrator, engine, inputs, outputs):
    """Lưu kết quả + snapshot vào DB."""

    # 1. Tạo snapshot trong MEMORY (nhanh, không I/O)
    snap = SnapshotManager.create(
        engine=engine,
        inputs=inputs,
        outputs=outputs,
        tag=SnapshotTag.ACTUAL,
        status=SnapshotStatus.APPROVED,
        created_by=frappe.session.user,
        source_doc=orchestrator.qi_name,       # "QTN-2026-00042"
        notes=f"CDMQ-2C — {inputs['W_mm']}×{inputs['H_mm']}, "
              f"{inputs['mau_nhom']}/{inputs['xuat_xu_nhom']}",
    )
    _registry.register(snap)

    # 2. SUBMIT — persist vào DB (CHỈ dòng này mới có I/O)
    docname = SnapshotManager.submit(
        snap=snap,
        title=f"Báo giá CDMQ-2C #{orchestrator.qi_name}",
        formula_set="BOM_LINE",
        source_doctype="Quotation",
        trace_level="cost_only",  # ← 14 dòng Cost, không trace 102 dòng BOM
    )
    frappe.db.commit()
    return docname
```

### 11.3. Dữ liệu snapshot thực tế trong DB cho CDMQ-2C

**`business_input` (JSON):**
```json
{
  "W_mm": 2400, "H_mm": 2600, "TransomHeight_mm": 600, "n_canh": 2,
  "mau_nhom": "WHITE", "xuat_xu_nhom": "IMPORT",
  "do_day_nhom": 20, "be_mat_nhom": "POWDER_COATED",
  "OFFSET_FRAME": 48, "OFFSET_GLASS": 90, "OFFSET_FIXED": 50,
  "NC_SX_PCT": 0.08, "NC_LD_PCT": 0.12, "OH_VC_PCT": 0.03,
  "OH_QLY_PCT": 0.03, "PROFIT_MARGIN": 0.16, "VAT_RATE": 0.10
}
```

**`outputs` (JSON):**
```json
{
  "VL_NHOM": 4895431, "VL_KINH": 6330980, "VL_VTP": 836400, "VL_PK": 2000000,
  "TONG_VL": 14062811, "TONG_NC": 2812562, "TONG_OH": 928145,
  "GIA_THANH": 17803518, "GIA_BAN": 20652081, "GIA_VAT": 22717289
}
```

**`execution_trace` (JSON, `cost_only` — 14 entries, ~4KB):**
```json
{
  "fields_evaluated": 93, "fields_skipped": 0, "total_exec_ms": 12.345,
  "entries": [
    {"field": "TONG_VL", "formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK",
     "old_value": null, "new_value": 14062811,
     "dep_values": {"VL_NHOM": 4895431, "VL_KINH": 6330980,
                    "VL_VTP": 836400, "VL_PK": 2000000}},
    {"field": "NC_SX", "formula": "NC_SX_PCT * TONG_VL",
     "old_value": null, "new_value": 1125025,
     "dep_values": {"NC_SX_PCT": 0.08, "TONG_VL": 14062811}},
    {"field": "GIA_THANH", "formula": "TONG_VL + TONG_NC + TONG_OH",
     "old_value": null, "new_value": 17803518,
     "dep_values": {"TONG_VL": 14062811, "TONG_NC": 2812562, "TONG_OH": 928145}},
    {"field": "GIA_VAT", "formula": "GIA_BAN + VAT",
     "old_value": null, "new_value": 22717289,
     "dep_values": {"GIA_BAN": 20652081, "VAT": 2065208}}
  ]
}
```

### 11.4. Audit — Load lại snapshot để giải trình

```python
# 6 tháng sau, kiểm toán hỏi: "Sao báo giá #042 là 22.7tr?"

snap = SnapshotManager.load("a1b2c3d4-...")

# 1. Verify toàn vẹn
assert snap.verify()  # ✅ True — payload_hash khớp, dữ liệu KHÔNG bị sửa

# 2. Xem input gốc
print(f"Kích thước: {snap.business_input['W_mm']}×{snap.business_input['H_mm']}")
# → 2400×2600
print(f"Màu: {snap.business_input['mau_nhom']}, "
      f"Xuất xứ: {snap.business_input['xuat_xu_nhom']}")
# → WHITE, IMPORT

# 3. Trace từng bước Cost — giải trình đầy đủ
for entry in snap.exec_trace.entries:
    if not entry.skipped:
        deps_str = ", ".join(f"{k}={v:,.0f}" if isinstance(v, (int, float))
                             else f"{k}={v}" for k, v in entry.dep_values.items())
        print(f"{entry.field}: {entry.formula}")
        print(f"  → {deps_str}")
        print(f"  = {entry.new_value:,.0f}")

# Output:
# TONG_VL: VL_NHOM + VL_KINH + VL_VTP + VL_PK
#   → VL_NHOM=4,895,431, VL_KINH=6,330,980, VL_VTP=836,400, VL_PK=2,000,000
#   = 14,062,811
# NC_SX: NC_SX_PCT * TONG_VL
#   → NC_SX_PCT=0.08, TONG_VL=14,062,811
#   = 1,125,025
# ...
# GIA_VAT: GIA_BAN + VAT
#   → GIA_BAN=20,652,081, VAT=2,065,208
#   = 22,717,289
```

### 11.5. Compare 2 snapshot — phát hiện chênh lệch giá

```python
# T7/2026: giá nhôm 113,000/kg → GIA_VAT = 22,717,289
snap_july = SnapshotManager.load("snap-july-2026")

# T12/2026: giá nhôm tăng lên 128,000/kg
snap_dec = SnapshotManager.load("snap-dec-2026")

diff = SnapshotManager.compare(snap_july, snap_dec)

# Kết quả:
print(f"Inputs thay đổi: {diff['summary']['inputs_changed_count']}")
# → 10 (10 dòng NHOM đổi giá)
print(f"GIA_VAT: {diff['outputs_changed']['GIA_VAT']['before']:,} → "
      f"{diff['outputs_changed']['GIA_VAT']['after']:,}")
# → 22,717,289 → 25,120,345
print(f"Delta: {diff['outputs_changed']['GIA_VAT']['delta_pct']}%")
# → +10.58%

# Giải trình:
# "Giá nhôm Xingfa WHITE/IMPORT/20micron tăng từ 113,000đ/kg (T7)
#  lên 128,000đ/kg (T12), kéo GIA_VAT tăng 2,403,056đ (+10.58%)"
```

### 11.6. TraceLevel — Kiểm soát dung lượng

| TraceLevel | Trace gì? | Dung lượng/snapshot | Dùng khi? |
|---|---|---|---|
| `full` | 102 BOM + 14 Cost | ~31 KB | Development, debug |
| `cost_only` | 14 Cost | **~4 KB** | **Production — recommended** |
| `summary` | Chỉ count | ~0.2 KB | Batch job, background |

### 11.7. Query snapshot từ DB

```sql
-- Tìm snapshot có GIA_VAT > 20tr
SELECT snapshot_id, title,
       JSON_EXTRACT(outputs, '$.GIA_VAT') AS gia_vat
FROM `tabFormula Snapshot`
WHERE CAST(JSON_EXTRACT(outputs, '$.GIA_VAT') AS DECIMAL(20,2)) > 20000000
ORDER BY creation DESC;

-- Tìm snapshot dùng màu WHITE
SELECT snapshot_id, title
FROM `tabFormula Snapshot`
WHERE JSON_EXTRACT(business_input, '$.mau_nhom') = 'WHITE';
```

---

## 12. TÓM TẮT MỘT TRANG (CHEAT-SHEET v30)

```
INPUT:  W_mm=2400  H_mm=2600  TransomHeight_mm=600  n_canh=2
        mau_nhom=WHITE  xuat_xu_nhom=IMPORT  do_day_nhom=20  be_mat_nhom=POWDER_COATED

B0-B1:  Chốt version + gom input + hằng số offset/%  vào `inputs`
B2:     Pre-fetch master data qua DataSourceResolver (BatchBindingResolver)
        → row_literals: trọng lượng riêng, đơn giá, glass_thick=24, glass_type=LOWE
        → Resolve 2 Rule → nẹp=C3211-20, keo=KEO-TT-01
B3-B4:  Ghép công thức width/height/qty (từ Bom Item) + 3 công thức Formula Set BOM_LINE
B5:     engine.calculate() → DAG tự sắp thứ tự, tính 17 dòng (bảng chi tiết mục 6.9)
B6:     Gom theo cost_bucket → VL_NHOM=4,895,431  VL_KINH=6,330,980
                                VL_VTP=836,400     VL_PK=2,000,000
B7:     Cost Template (14 bước, engine tính theo DAG) → GIA_VAT = 22,717,289đ
🆕 B8: SnapshotManager.create() → submit() → DB (trace_level=cost_only)
        → Load lại: snap.verify() ✅ → trace 14 dòng Cost → giải trình đầy đủ

KẾT QUẢ CUỐI:  GIA_VAT = 22,717,289 đ   (DON_GIA_M2 = 3,309,628 đ/m², chưa VAT)
```

```
INPUT:  W_mm=2400  H_mm=2600  TransomHeight_mm=600  n_canh=2
        mau_nhom=WHITE  xuat_xu_nhom=IMPORT  do_day_nhom=20  be_mat_nhom=POWDER_COATED

B0-B1:  Chốt version + gom input + hằng số offset/%  vào `inputs`
B2a:    (không có dòng nào cần — bỏ qua)
B2.5:   Batch query 1 lần: trọng lượng riêng, đơn giá (theo composite key màu/xuất xứ...),
        glass_thick=24 & glass_type=LOWE (ghi literal lên dòng kinh_tren/kinh_duoi)
B2b:    Resolve 2 Rule cross-row → nẹp=C3211-20, keo=KEO-TT-01
B3-B4:  Ghép công thức width/height/qty (từ Profile Line) + 3 công thức Formula Set BOM_LINE
B5:     engine.calculate() → DAG tự sắp thứ tự, tính 17 dòng (bảng chi tiết mục 6.9)
B6:     Gom theo cost_bucket → VL_NHOM=4,895,431  VL_KINH=6,330,980
                                VL_VTP=836,400     VL_PK=2,000,000
B7:     Cost Template (14 bước, engine tính theo DAG) → GIA_VAT = 22,717,289đ
B8:     Lưu child table + ConfigSnapshot (để tái lập chính xác về sau)

KẾT QUẢ CUỐI:  GIA_VAT = 22,717,289 đ   (DON_GIA_M2 = 3,309,628 đ/m², chưa VAT)
```

---

*Tài liệu tổng hợp và diễn giải chi tiết dựa trên bản chuẩn v27 (AlumGlass_v27_CHUAN_TRIEN_KHAI.md) — nguồn số liệu duy nhất, đã sửa 2 sai số cộng dồn và 1 lỗi kiến trúc so với bản v26/Grok gốc.*
