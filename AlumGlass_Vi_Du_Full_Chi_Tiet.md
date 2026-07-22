# VÍ DỤ FULL A-Z: TỪ MASTER DATA ĐẾN GIÁ BÁN CUỐI CÙNG
## Sản phẩm: Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)

> Tài liệu này dựa trên bản **v27 — CHUẨN TRIỂN KHAI** (bản đã sửa lỗi kiến trúc `lookup_calc_pattern` và 2 sai số cộng dồn của bản v26/Grok). Mục tiêu: đi từ **con số 0** — chưa có gì trong hệ thống — cho tới khi ra được **giá bán có VAT = 22,717,289đ**, giải thích **tại sao mỗi con số lại ra như vậy**, và **engine tính toán vận hành như thế nào ở bên dưới**.
>
> Cách đọc: mỗi phần đều có ví dụ số cụ thể đi kèm ngay bên cạnh phần lý thuyết — không có phần nào chỉ mô tả suông.

---

## MỤC LỤC

1. Bức tranh tổng thể — 3 tầng hệ thống và dữ liệu chảy qua chúng như thế nào
2. Toàn bộ Master Data cần tạo trước (kèm giải thích từng bảng dùng để làm gì)
3. Cấu hình sản phẩm mẫu — BOM 17 dòng
4. Formula Engine hoạt động như thế nào (DAG, topological sort, cross-row reference)
5. BomOrchestrator — 11 phase, mỗi phase kèm số liệu thật của ví dụ này
6. Bảng tính chi tiết toàn bộ 17 dòng (mở rộng từng phép thay số)
7. Cost Template — từ tổng vật liệu ra giá bán có VAT
8. Kiểm tra chéo & những "bẫy" cần tránh khi triển khai
9. Tóm tắt một trang (cheat-sheet)

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
              │   BomOrchestrator    │   ◄── app AlumGlass, 11 phase B0→B8
              │  (chuẩn bị dữ liệu)  │
              └──────────┬───────────┘
                         │  formulas={...}, inputs={...}
                         ▼
              ┌─────────────────────┐
              │   Formula Builder    │   ◄── app độc lập, chỉ biết DAG
              │  engine.calculate()  │
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

### 2.12. AL Cost Bucket (DocType custom) — cây phân loại chi phí

| bucket_code | bucket_name | bucket_role | parent_bucket |
|---|---|---|---|
| VL_NHOM | Vật liệu nhôm | LEAF | TONG_VL |
| VL_KINH | Vật liệu kính | LEAF | TONG_VL |
| VL_VTP | Vật tư phụ | LEAF | TONG_VL |
| VL_PK | Phụ kiện | LEAF | TONG_VL |
| TONG_VL | Tổng vật liệu | AGGREGATE | – |
| NC_SX | Nhân công sản xuất | LEAF | TONG_NC |
| NC_LD | Nhân công lắp đặt | LEAF | TONG_NC |
| TONG_NC | Tổng nhân công | AGGREGATE | – |
| OH_VC | Overhead vận chuyển | LEAF | TONG_OH |
| OH_QLY | Overhead quản lý | LEAF | TONG_OH |
| TONG_OH | Tổng overhead | AGGREGATE | – |
| GIA_THANH | Giá thành | AGGREGATE | – |
| GIA_BAN | Giá bán chưa VAT | AGGREGATE | – |
| GIA_VAT | Giá bán có VAT | AGGREGATE | – |

*Mỗi dòng BOM (17 dòng ở phần 3) được gán vào đúng 1 `cost_bucket` LEAF (VL_NHOM / VL_KINH / VL_VTP / VL_PK). Sau khi engine tính xong `thanh_tien` cho từng dòng, Python cộng dồn theo bucket — đây là bước B6, thay thế hoàn toàn cho việc dùng công thức `SUMIF` (vừa chậm vừa khó bảo trì khi số dòng BOM lớn).*

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

## 5. BOMORCHESTRATOR — 11 PHASE, VỚI SỐ LIỆU THẬT CỦA VÍ DỤ NÀY

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
**Chưa** có `glass_thick`/`glass_type`/`trong_luong_rieng`/`don_gia` — các giá trị này cần **tra cứu từ database**, thuộc về B2.5.

### B2a — Rule Resolver (không cross-row)
Quét 17 dòng tìm dòng nào `item_selection_mode=Rule` mà input **không** chứa `items.`. Trong ví dụ này **không có dòng nào** thuộc loại này (cả 2 Rule đều cross-row) — phase chạy nhưng không làm gì. Giữ lại vì BOM khác (ví dụ chọn phụ kiện theo trọng lượng cánh) có thể cần.

### B2.5 — Pre-fetch Master Data (quan trọng nhất về hiệu năng)

Đây là bước **query database 1 lần duy nhất cho mỗi loại dữ liệu** (không lặp query cho từng dòng — tránh N+1):

1. **Trọng lượng riêng** — gom tất cả `item_code` của các dòng NHOM (`XF55-KB-20`, `XF55-CANH-20`), query 1 lần `Item.weight_per_unit`.
2. **Giá** — gom tất cả `price_base_item` cần tra (`NHOM-XINGFA`, `TAY_NAM_KINLONG`), ghép với `resolve_price_attrs()`:
   - Với dòng NHOM: `{color: mau_nhom, source: xuat_xu_nhom, thickness: do_day_nhom, surface: be_mat_nhom}` = `{WHITE, IMPORT, 20, POWDER_COATED}` → tra trong Item Price ra **113,000đ/kg** cho toàn bộ 10 dòng nhôm.
   - Với dòng `tay_nam`: dùng `accessory_finish=SATIN`, `accessory_material=STAINLESS` (không liên quan màu khung) → tra ra **210,000đ/cái**.
   - Query bằng **composite key** `base_item|color|source|thickness|surface|finish|material`, 1 lần cho toàn bộ danh sách `base_items`.
3. **glass_thick / glass_type** — với 2 dòng KINH (`kinh_tren`, `kinh_duoi`), tra `AL Glass Master` theo `KINH-LOWE-24` → `{total_thick_mm: 24, glass_type: "LOWE"}`, ghi **trực tiếp lên chính dòng đó** (không tạo biến global riêng tên).

**Kết quả B2.5 (`row_literals`) — bảng dữ liệu literal cho từng slug:**

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

> Lưu ý dòng `nep_kinh_tren`/`nep_kinh_duoi`: `trong_luong_rieng=0.312` và `don_gia=113,000` được điền **trước cả khi biết Item cụ thể là gì** — vì công thức tra giá dùng `price_base_item=NHOM-XINGFA` (giá/kg là như nhau cho mọi profile Xingfa cùng màu, không phụ thuộc profile nào), còn `trong_luong_rieng` lấy theo Item nẹp **sẽ được Rule chọn** ở B2b. Trên thực tế, hệ thống lấy `weight_per_unit` của Item đã resolve — ở đây đã biết trước Rule sẽ chọn `C3211-20` (0.312 kg/m) vì `glass_thick=24 > 16.01`.

Toàn bộ các giá trị này sau đó được nạp vào `inputs` dưới đúng cú pháp `items.<slug>.<field>` — ví dụ `inputs["items.kinh_tren.glass_thick"] = 24`.

### B2b — Rule Resolver (cross-row)
Bây giờ `glass_thick`/`glass_type` đã có trong `row_literals`, 2 Rule được tra:

| Dòng | Input dùng để tra | Rule | Kết quả |
|---|---|---|---|
| nep_kinh_tren | `items.kinh_tren.glass_thick = 24` | RULE-NEP-GLASSTHICK (THRESHOLD, khoảng 16.01–999) | **C3211-20** |
| nep_kinh_duoi | `items.kinh_duoi.glass_thick = 24` | RULE-NEP-GLASSTHICK | **C3211-20** |
| keo_tren | `items.kinh_tren.glass_type = LOWE` | RULE-KEO-GLASSTYPE (LOOKUP) | **KEO-TT-01** |
| keo_duoi | `items.kinh_duoi.glass_type = LOWE` | RULE-KEO-GLASSTYPE | **KEO-TT-01** |

### B3 — ProfileInterpreter Pass 1 (Scan)
Duyệt toàn bộ 17 dòng, với mỗi dòng xác định 3 biến cần engine tính: `items.<slug>.width`, `items.<slug>.height` (nếu có), `items.<slug>.qty`; đồng thời phát hiện các tham chiếu `items.` để biết dòng nào phụ thuộc dòng nào (phục vụ việc engine xây DAG đúng ở B5).

### B4 — Build Formulas
Ghép công thức `width`/`height`/`qty` lấy nguyên văn từ cột tương ứng trong `AL Profile Line` (mục 3) với 3 công thức chuẩn từ Formula Set `BOM_LINE` (mục 2.13), tạo ra dictionary `formulas` đầy đủ 17×6 = 102 biến (width, height, qty, so_luong_don_vi, tong_so_luong, thanh_tien × 17 dòng — một số dòng không có `height` nên ít hơn). Biến literal (`trong_luong_rieng`, `don_gia`, `glass_thick`, `glass_type`, `calc_pattern`) đã có sẵn trong `inputs` từ B2.5/B2b.

### B5 — Engine Calculate
```python
engine = FlexibleFormulaEngine(
    child_table_configs={"items": {"id_field": "slug"}},
    extra_funcs={"lookup_calc_pattern": lookup_calc_pattern},
)
result = engine.calculate(formulas, inputs)
```
Engine parse 102 công thức, xây DAG, sắp xếp tô-pô, tính tuần tự theo đúng thứ tự đó. Kết quả chi tiết từng dòng ở **phần 6**.

### B6 — Gom Cost Bucket (Python thuần)
```python
buckets = defaultdict(float)
for line in profile_lines:
    buckets[line.cost_bucket] += result["items"][line.slug]["thanh_tien"]
```
Kết quả (xem phần 6.3 để đối chiếu từng dòng):

| Bucket | Tổng (VND) |
|---|---|
| VL_NHOM | 4,895,431 |
| VL_KINH | 6,330,980 |
| VL_VTP | 836,400 |
| VL_PK | 2,000,000 |

### B7 — Cost Template
Đưa 4 số trên vào `inputs`, chạy engine lần 2 với 14 công thức của `CT-01-STANDARD` (mục 2.14) — DAG lần này nhỏ hơn nhiều, không có child table. Kết quả đầy đủ ở **phần 7**.

### B8 — Save Results
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

## 7. COST TEMPLATE — TỪ TỔNG VẬT LIỆU RA GIÁ BÁN CÓ VAT (B6 + B7)

### 7.1. B6 — Gom cost bucket

Cộng cột "thành tiền" của bảng 6.9 theo `cost_bucket` mà mỗi dòng được gán ở mục 3:

| Bucket | Các dòng cộng vào | Tổng (VND) |
|---|---|---|
| **VL_NHOM** | khung_ngang_tren + khung_ngang_duoi + khung_dung + do_ngang + canh_ngang + canh_dung + nep_kinh_tren + nep_kinh_duoi | 340,898+340,898+738,613+327,259+702,950+1,191,110+401,918+851,785 = **4,895,431** |
| **VL_KINH** | kinh_tren + kinh_duoi | 1,454,750+4,876,230 = **6,330,980** |
| **VL_VTP** | keo_tren + keo_duoi + gioang + vit | 256,500+543,600+12,500+23,800 = **836,400** |
| **VL_PK** | tay_nam + khoa + ban_le | 210,000+350,000+1,440,000 = **2,000,000** |

### 7.2. B7 — Tính từng dòng Cost Template, theo đúng thứ tự DAG

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

## 8. KIỂM TRA CHÉO & NHỮNG "BẪY" CẦN TRÁNH KHI TRIỂN KHAI

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

## 9. TÓM TẮT MỘT TRANG

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
