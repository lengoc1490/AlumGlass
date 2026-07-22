# TÀI LIỆU CHUẨN AlumGlass v27_FULL — GỘP TOÀN BỘ v26_new.md + CẢI TIẾN v27 + VÍ DỤ TRIỂN KHAI FULL A-Z
## Sản phẩm mẫu: Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)

> Đây là bản **hợp nhất đầy đủ nhất**, gộp:
> 1. **Toàn bộ nội dung tài liệu gốc `v26_new.md`** (kiến trúc, 14 quyết định thiết kế ban đầu, master data, BOM, BomOrchestrator, tích hợp Formula Builder, ví dụ tính toán, checklist, khuyến nghị của Grok) — **không bỏ sót mục nào**;
> 2. **Toàn bộ cải tiến & sửa lỗi của bản chuẩn v27** (sửa lỗi kiến trúc `lookup_calc_pattern` gọi đệ quy vào engine, sửa 2 sai số cộng dồn trong ví dụ tính toán, hướng dẫn triển khai Frappe/ERPNext chi tiết);
> 3. **Phần bổ sung mới**: giải thích cơ chế Formula Engine (DAG, topological sort, cross-row reference), số liệu thật ở từng phase B0→B8, ví dụ tính toán mở rộng từng phép thay số, bảng "bẫy" triển khai và cheat-sheet.
>
> Mọi nội dung của `v26_new.md` và của bản v27 gốc đều được **giữ nguyên vẹn**, phần nào là bổ sung mới được đánh dấu rõ **"(BỔ SUNG)"**. Toàn bộ số liệu trong tài liệu này đã được sửa 2 sai số cộng dồn và 1 lỗi kiến trúc so với bản `v26_new.md`/Grok gốc — chi tiết ở Changelog (mục 0) và Phụ lục (mục 10).

---

## MỤC LỤC

0. [Changelog — những gì thay đổi và tại sao](#0)
1. [Tổng quan kiến trúc & nguyên tắc thiết kế](#1)
2. [Master Data đầy đủ (15 bảng, tạo theo đúng thứ tự)](#2)
3. [Sản phẩm mẫu & cấu hình BOM (17 dòng, bản chuẩn cuối)](#3)
4. **(BỔ SUNG)** [Formula Engine hoạt động như thế nào — DAG, topological sort, cross-row reference](#4)
5. [BomOrchestrator — chi tiết từng phase B0→B8, kèm số liệu thật của ví dụ](#5)
6. [Tích hợp Formula Builder — handlers đã sửa lỗi kiến trúc](#6)
7. [Ví dụ tính toán đầy đủ — mở rộng từng phép thay số, số liệu đã sửa](#7)
8. [Hướng dẫn triển khai từng bước trên Frappe/ERPNext](#8)
9. [Checklist kiểm thử](#9)
10. [Phụ lục: Bảng đối chiếu lỗi đã sửa](#10)
11. **(BỔ SUNG)** [Những "bẫy" triển khai cần tránh & Cheat-sheet tóm tắt 1 trang](#11)
12. **(TỪ v26_new.md)** [Các khuyến nghị bổ sung từ Grok & trạng thái xử lý](#12)

---

<a name="0"></a>
## 0. CHANGELOG — THAY ĐỔI Ở BẢN NÀY

### 0.1. Lỗi #1 (kiến trúc) — `lookup_calc_pattern()` gọi lại `FlexibleFormulaEngine.evaluate_single()`

Đây là **lỗi đã từng bị phát hiện và sửa ở một lượt review trước**, nhưng bản do Grok tạo lại đã **tái tạo đúng lỗi này dưới hình hài mới** (đổi tên hàm nhưng cùng bản chất sai). Cụ thể, đoạn code gốc ở mục 5.1 (tài liệu v26):

```python
def lookup_calc_pattern(calc_pattern_code, width=None, height=None, trong_luong_rieng=None):
    ...
    from formula_builder import FlexibleFormulaEngine
    result = FlexibleFormulaEngine.evaluate_single(formula, {...})
    return result
```

**Vì sao đây là lỗi, không phải chi tiết vặt:**

1. `lookup_calc_pattern` **tự nó** là một hàm được đăng ký vào `BASE_FUNCS` — tức là nó được **gọi TỪ BÊN TRONG** một lượt `engine.calculate()` đang chạy (khi engine evaluate node `so_luong_don_vi` trong DAG). Gọi ngược lại engine (`FlexibleFormulaEngine.evaluate_single`) từ bên trong chính một hàm mà engine đang thực thi là **gọi đệ quy vào engine**, không phải gọi một tiện ích độc lập.
2. Một lần gọi engine "con" như vậy sẽ **không có** context/registry của lần gọi engine "cha" (child_table_configs, các hàm custom khác đã đăng ký, cache biến, v.v.) — trừ khi tự khởi tạo lại toàn bộ, gây tốn hiệu năng (parse + build DAG cho 1 công thức 1 dòng, lặp lại cho từng slug × mỗi lần tính).
3. Nó phá vỡ khả năng `explain()`/`get_trace()` của engine cha vì phép tính bên trong xảy ra trong một "phiên" engine hoàn toàn tách biệt, không nằm trong DAG chính — dữ liệu trace trả về sẽ thiếu bước này.
4. Vì chỉ có **4 pattern cố định, đã biết trước** (`LENGTH_TO_WEIGHT`, `AREA`, `LENGTH_ONLY`, `COUNT`), không có lý do gì phải "diễn giải công thức dạng chuỗi bằng engine" — đây là bài toán dispatch bảng tra cứu đơn giản, dùng engine cho việc này là dùng dao mổ trâu giết gà, đồng thời gây ra chính lỗi kiến trúc nêu trên.

**Cách sửa (áp dụng trong mục 6 bên dưới):** thay lời gọi đệ quy engine bằng **dispatch table thuần Python**, không phụ thuộc engine. `calc_formula` trong `AL Quantity Calc Method` vẫn giữ lại **chỉ để hiển thị/tài liệu hóa cho người dùng** (đọc hiểu công thức là gì), không dùng để "evaluate" nữa.

### 0.2. Lỗi #2 và #3 (số học) — 2 sai số cộng dồn trong bảng ví dụ tính toán (mục 7 bản gốc)

Rà soát lại toàn bộ 17 dòng bằng tính tay + Python, phát hiện **2 dòng bị sai** ở cột `thành tiền` (các dòng còn lại đều đúng):

| slug | Công thức đúng | Giá trị ĐÚNG | Giá trị SAI trong bản gốc | Chênh lệch |
|---|---|---|---|---|
| `canh_ngang` | `6.2208 kg × 113,000` | **702,950** | 702,550 | **-400** |
| `canh_dung` | `10.5408 kg × 113,000` | **1,191,110** | 1,190,110 | **-1,000** |

Hai sai số này cộng dồn qua toàn bộ chuỗi tính (`VL_NHOM → TONG_VL → NC_SX/NC_LD/OH_VC/OH_QLY → GIA_THANH → PROFIT → GIA_BAN → VAT → GIA_VAT`, vì mọi bước sau đều là % nhân trên `TONG_VL` hoặc `GIA_THANH`/`GIA_BAN`), dẫn tới kết quả cuối `GIA_VAT` lệch **đúng 2,261đ** (22,717,289 đúng thay vì 22,715,028 trong bản gốc). Chi tiết đối chiếu từng bước ở [Phụ lục 10](#10).

> **Bài học lưu ý cho lần review sau:** khi một AI (Grok hoặc bất kỳ) "review lại" một tài liệu đã có ví dụ số cụ thể, phải **tính lại từ đầu bằng công cụ (Python/Excel)**, không chỉ đọc và tin bảng số có sẵn — sai số kiểu gõ nhầm 1 chữ số (702,**9**50 → 702,**5**50) rất dễ lọt qua vì "nhìn có vẻ hợp lý".

### 0.3. Những gì được GIỮ NGUYÊN từ các bản trước (đã đúng, không đổi)

| # | Cải tiến | Nguồn |
|---|---|---|
| 1 | `price_attrs` của nhóm NHOM lấy từ 4 biến `AL Variable Set` (`mau_nhom`, `xuat_xu_nhom`, `do_day_nhom`, `be_mat_nhom`) thay vì JSON lặp lại trên 8 dòng | Review E |
| 2 | `glass_thick`/`glass_type` ghi thành field literal ngay trên dòng KINH ở B2.5, đọc qua `items.kinh_tren.glass_thick` — 1 cú pháp cross-row duy nhất, không dùng biến phẳng | Review F |
| 3 | `accessory_finish`, `accessory_material` là Select field có validate, không phải JSON tự do | Review E |
| 4 | Tách `B2a` (Rule không cross-row) và `B2b` (Rule cross-row, chạy sau B2.5) | Review Grok — giữ lại vì đúng |
| 5 | `AL Quantity Calc Method` thay `IF()` lồng nhau | Review trước |
| 6 | Batch query giá qua `price_lookup`, gom cost bucket bằng Python (không SUMIF) | v26 gốc |

### 0.4. (BỔ SUNG) Thay đổi ở bản FULL này so với v27 gốc

| # | Bổ sung | Vị trí |
|---|---|---|
| 1 | Thêm mục 4 giải thích **cơ chế DAG / topological sort / cross-row reference** — vì sao engine bắt buộc phải giải theo đồ thị phụ thuộc, không thể tính tuần tự theo `sort` | Mục 4 |
| 2 | Mỗi phase B0→B8 được bổ sung **số liệu thật của đúng ví dụ CDMQ-2C-TRANSOM** thay vì chỉ mô tả lý thuyết suông | Mục 5 |
| 3 | Bảng tính 17 dòng được **mở rộng thành phép thay số từng bước** cho 8 dòng đại diện mọi loại (NHOM đơn giản, NHOM có offset, NHOM chia cánh, KINH, NHOM cross-row, VTP cross-row, VTP đếm cái, PHỤ KIỆN) | Mục 7 |
| 4 | Thêm bảng **"bẫy triển khai"** đúc kết từ toàn bộ lỗi đã từng gặp, và **cheat-sheet 1 trang** để tra cứu nhanh | Mục 11 |
| 5 | Không sửa/xóa bất kỳ nội dung nào của bản v27 gốc — chỉ chèn thêm | Toàn bài |

---

<a name="1"></a>
## 1. TỔNG QUAN KIẾN TRÚC & NGUYÊN TẮC THIẾT KẾ

### 1.1. Ba tầng hệ thống

| Thành phần | Vai trò | Loại |
|---|---|---|
| **Formula Builder** | Engine tính toán DAG, xử lý công thức, tham chiếu chéo | App độc lập, **bất biến** — không sửa code app này, chỉ đăng ký thêm hàm/handler từ AlumGlass |
| **AlumGlass** | Orchestration nghiệp vụ nhôm kính, master data, BomOrchestrator | Frappe Custom App |
| **ERPNext Core** | Item, Item Price, Batch, Workflow, Stock | Nền tảng |

**(BỔ SUNG) Cách hiểu trực quan về 3 tầng này:** Formula Builder giống như một "máy tính bảng Excel tổng quát" — nó không biết "kính" hay "nhôm" là gì, chỉ biết tên biến và công thức. AlumGlass đóng vai trò "người nhập liệu thông minh" — nó đọc master data nghiệp vụ (Item, giá, quy tắc chọn phụ kiện...), dịch tất cả thành ngôn ngữ mà Formula Builder hiểu (`formulas` + `inputs`), giao cho Formula Builder tính, rồi nhận lại kết quả để làm tiếp việc nghiệp vụ (gom nhóm chi phí, tính giá bán). ERPNext Core chỉ là kho lưu trữ dữ liệu gốc (Item, giá...), không tham gia tính toán.

### 1.2. Nguyên tắc bất biến xuyên suốt tài liệu

1. **Một nguồn chân lý cho mỗi loại dữ liệu.** Màu/xuất xứ/độ dày/bề mặt nhôm là thuộc tính **cấp Quotation**, khai báo 1 lần trong `AL Variable Set`, không lặp lại trên từng dòng BOM.
2. **Một cú pháp tham chiếu chéo duy nhất:** `items.<slug>.<field>` — áp dụng cho MỌI trường hợp (kích thước tính bằng công thức lẫn dữ liệu tra từ master), không có ngoại lệ dùng biến phẳng đặt tên riêng.
3. **`slug` là khóa định danh dòng BOM**, ổn định qua thời gian, không phụ thuộc thứ tự (`sort` chỉ dùng để hiển thị).
4. **Không dùng engine để tính những gì có thể tính bằng Python thuần** khi số pattern cố định và hữu hạn (xem mục 0.1) — chỉ dùng engine cho DAG thật sự cần giải theo thứ tự phụ thuộc (width/height/qty/so_luong_don_vi/tong_so_luong/thanh_tien của toàn bộ BOM).
5. **Không bùng nổ Item.** Biến thể màu/xuất xứ/bề mặt xử lý qua `Item Price` + Custom Fields + composite key, không tạo Item riêng cho từng tổ hợp.
6. **Mọi hằng số nghiệp vụ (offset, %NC, %OH...) đều là data** (`AL Calculation Rule`, `Formula Global Variable`), không hard-code trong Python hay trong công thức.

### 1.3. (TỪ v26_new.md) Toàn bộ 14 quyết định thiết kế ban đầu (v26 + bổ sung), kèm lý do

Đây là bảng quyết định thiết kế gốc từ tài liệu `v26_new.md` — liệt kê lại nguyên vẹn ở đây để không mất lịch sử "vì sao hệ thống được thiết kế như vậy", đối chiếu với 6 nguyên tắc bất biến ở mục 1.2 (là bản rút gọn/khái quát hóa của chính 14 quyết định này qua các lượt review sau).

| # | Quyết định | Lý do |
|---|---|---|
| 1 | Dùng `slug` làm định danh duy nhất trong BOM Line | Tham chiếu chéo ổn định, không bị ảnh hưởng bởi thứ tự |
| 2 | Tên cột là `width`, `height`, `qty` (không `dim1_formula`) | Người dùng hiểu ngay ý nghĩa kích thước |
| 3 | Cross-row reference: `items.<slug>.<field>` | Đúng cú pháp Formula Builder, nhất quán |
| 4 | Gom cost bucket ở Python, không dùng `SUMIF` | Hiệu năng tốt, công thức đơn giản |
| 5 | Tra giá bằng batch query + composite key, đăng ký handler `price_lookup` vào Formula Builder | Tránh N+1, tận dụng core, hỗ trợ explain() |
| 6 | Item Price + Custom Fields cho giá đa thuộc tính | Tận dụng core, linh hoạt, không bùng nổ Item |
| 7 | AL Slug Library để tái sử dụng slug | Nhất quán, tiết kiệm thời gian |
| 8 | Formula Set `BOM_LINE` + đăng ký `lookup_calc_pattern` vào BASE_FUNCS | Dùng chung, dễ bảo trì, traceable |
| 9 | Đưa `mau_nhom`, `xuat_xu_nhom`, `do_day_nhom`, `be_mat_nhom` vào Variable Set | Tránh lặp JSON trên nhiều dòng |
| 10 | Dùng `calc_pattern` (Link → AL Quantity Calc Method) thay cho IF() lồng nhau | Dễ mở rộng, dễ bảo trì |
| 11 | Dùng field Select cho accessory_finish, accessory_material | Thay JSON tự do, có validate nhập liệu |
| 12 | Tham chiếu `glass_thick` và `glass_type` qua `items.kinh_tren.glass_thick` | Nhất quán với cross-row, không dùng biến phẳng |
| 13 | Formalize BomOrchestrator thành các phase rõ ràng (B0 → B8) | Dễ hiểu, dễ test, dễ mở rộng |
| 14 | Đăng ký handlers custom vào Formula Builder: `price_lookup`, `glass_lookup`, `lookup_calc_pattern` | Tăng traceability, hỗ trợ explain() |

> **Lưu ý quan trọng (đã sửa ở bản v27/v27_FULL):** quyết định #5, #8, #14 ở trên — về việc đăng ký `lookup_calc_pattern` — mô tả đúng Ý ĐỊNH thiết kế (dùng chung, traceable), nhưng **cách triển khai cụ thể ở bản v26 gốc bị sai kiến trúc** (gọi đệ quy vào engine — xem mục 0.1). Ý định "dùng chung, traceable" vẫn đúng và được giữ nguyên; chỉ có *cách hiện thực hóa* được sửa thành dispatch table Python thuần (mục 6.1), không đổi quyết định thiết kế.

---

<a name="2"></a>
## 2. MASTER DATA ĐẦY ĐỦ

> Thứ tự tạo dưới đây **chính là thứ tự phải làm khi triển khai** — DocType sau tham chiếu DocType trước.

### 2.1. Item Group (Core ERPNext)

| item_group | parent_item_group | is_group |
|---|---|---|
| NHOM_PROFILE | (root) | 1 |
| NHOM_XINGFA | NHOM_PROFILE | 0 |
| NHOM_ALUMIL | NHOM_PROFILE | 0 |
| KINH | (root) | 0 |
| PHU_KIEN | (root) | 0 |
| VAT_TU_PHU | (root) | 0 |

*(BỔ SUNG) Vai trò: chỉ dùng để phân loại Item trong báo cáo tồn kho/mua hàng của ERPNext — không ảnh hưởng tới công thức tính giá.*

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

*(BỔ SUNG) Vai trò: danh mục màu chuẩn hóa, dùng làm giá trị hợp lệ cho field `custom_mau_sac` trên Item Price (mục 2.7) và biến `mau_nhom` trong Variable Set (mục 2.15) — nhờ đây UI validate được, không cho gõ tự do "trắng"/"White"/"TRANG" lẫn lộn.*

### 2.4. AL Calculation Rule (DocType custom) — hằng số hình học

| rule_code | rule_name | rule_type | constant_value |
|---|---|---|---|
| OFFSET-FRAME | Khe hở khung-cánh | CONSTANT | 48 |
| OFFSET-GLASS | Khe hở cánh-kính | CONSTANT | 90 |
| OFFSET-FIXED | Khe hở khung-kính cố định | CONSTANT | 50 |
| OFFSET-DO-NGANG | Khe hở đố ngang | CONSTANT | 48 |

*(BỔ SUNG) Vai trò: các con số kỹ thuật gia công (đơn vị mm) dùng để trừ hao khi tính kích thước cắt cánh/kính từ kích thước khung bao. Nạp vào công thức dưới dạng `$OFFSET_FRAME`, `$OFFSET_GLASS`... Đây là **data**, không hard-code trong code — đổi hệ profile khác chỉ cần sửa bảng này.*

### 2.5. Formula Global Variable (DocType của Formula Builder — dùng chung mọi BOM)

| var_name | value_source | constant_value |
|---|---|---|
| VAT_RATE | CONSTANT | 0.10 |
| PROFIT_MARGIN | CONSTANT | 0.16 |
| NC_SX_PCT | CONSTANT | 0.08 |
| NC_LD_PCT | CONSTANT | 0.12 |
| OH_VC_PCT | CONSTANT | 0.03 |
| OH_QLY_PCT | CONSTANT | 0.03 |

*(BỔ SUNG) Vai trò: các tỷ lệ % kinh doanh (nhân công, overhead, lợi nhuận, thuế), dùng ở tầng Cost Template (mục 7), tham chiếu bằng cú pháp `$TEN_BIEN`.*

### 2.6. Item (Core ERPNext)

**a) Mã đại diện dùng để tra giá (không có trọng lượng vật lý riêng)**

| item_code | item_name | item_group | brand | stock_uom | al_item_type | al_is_color_variable |
|---|---|---|---|---|---|---|
| NHOM-XINGFA | Nhôm Xingfa (đại diện) | NHOM_XINGFA | XINGFA | Kg | NHOM_PROFILE | 0 |
| NHOM-ALUMIL | Nhôm Alumil (đại diện) | NHOM_ALUMIL | ALUMIL | Kg | NHOM_PROFILE | 0 |
| TAY_NAM_KINLONG | Tay nắm Kinlong (đại diện) | PHU_KIEN | KINLONG | Cái | PHU_KIEN | 0 |

**b) Profile vật lý cụ thể (có trọng lượng/mét, màu qua Batch nếu cần theo dõi tồn kho theo màu)**

| item_code | item_name | item_group | brand | stock_uom | weight_per_unit (kg/m) | al_item_type | al_is_color_variable |
|---|---|---|---|---|---|---|---|
| XF55-KB-20 | Khung bao H55 2.0mm | NHOM_XINGFA | XINGFA | Mét | 1.257 | NHOM_PROFILE | 1 |
| XF55-CANH-20 | Cánh mở quay 2.0mm | NHOM_XINGFA | XINGFA | Mét | 1.350 | NHOM_PROFILE | 1 |
| C3211-20 | Nẹp kính >16mm | NHOM_XINGFA | XINGFA | Mét | 0.312 | NHOM_PROFILE | 1 |
| C3210-20 | Nẹp kính 11–16mm | NHOM_XINGFA | XINGFA | Mét | 0.245 | NHOM_PROFILE | 1 |
| C3209-20 | Nẹp kính ≤10.38mm | NHOM_XINGFA | XINGFA | Mét | 0.198 | NHOM_PROFILE | 1 |
| KINH-LOWE-24 | Kính Low-E 24mm | KINH | – | M2 | – | KINH | 0 |
| KINH-DON-8 | Kính dán 8mm | KINH | – | M2 | – | KINH | 0 |
| KEO-TT-01 | Keo trung tính (Low-E) | VAT_TU_PHU | – | Mét | – | VTP | 0 |
| KEO-TT-02 | Keo thường | VAT_TU_PHU | – | Mét | – | VTP | 0 |
| GIO-EPDM-55 | Gioăng EPDM 55 | VAT_TU_PHU | – | Mét | – | VTP | 0 |
| VIT-TK-35X16 | Vít tự khoan 3.5x16 | VAT_TU_PHU | – | Cái | – | VTP | 0 |
| KL-MZS20 | Tay nắm Kinlong MZS20 | PHU_KIEN | KINLONG | Cái | – | PHU_KIEN | 0 |
| KL-KHOA-01 | Khóa Kinlong 01 | PHU_KIEN | KINLONG | Cái | – | PHU_KIEN | 0 |
| KL-T-MJ06 | Bản lề cối MJ06 | PHU_KIEN | KINLONG | Cái | – | PHU_KIEN | 0 |

*(BỔ SUNG) Vì sao tách (a) và (b)? Vì một profile nhôm cụ thể (ví dụ `XF55-KB-20`) được tra giá theo mã "đại diện" (`NHOM-XINGFA`) + tổ hợp (màu, xuất xứ, độ dày, bề mặt) trong Item Price — thay vì tạo Item riêng cho từng tổ hợp màu × xuất xứ × profile (sẽ bùng nổ số lượng Item). `weight_per_unit` của (b) dùng để tính khối lượng vật lý thật; giá tiền/kg lại lấy từ (a) qua composite key.*

### 2.7. Item Price (Core ERPNext + Custom Fields)

**Custom Fields thêm vào Item Price:**
- `custom_mau_sac` (Link → AL Color Standard)
- `custom_xuat_xu` (Select: IMPORT / DOMESTIC)
- `custom_do_day` (Int)
- `custom_be_mat` (Select: POWDER_COATED / ANODIZED / WOOD_GRAIN)

**Ràng buộc:** Server Script validate chặn trùng tổ hợp `(item_code, price_list, custom_mau_sac, custom_xuat_xu, custom_do_day, custom_be_mat)` (code đầy đủ ở mục 8.4).

**Dữ liệu mẫu:**

| item_code | price_list | price_list_rate | custom_mau_sac | custom_xuat_xu | custom_do_day | custom_be_mat |
|---|---|---|---|---|---|---|
| NHOM-XINGFA | Standard Selling | **113,000** | **WHITE** | **IMPORT** | **20** | **POWDER_COATED** |
| NHOM-XINGFA | Standard Selling | 118,000 | DARK | IMPORT | 20 | POWDER_COATED |
| NHOM-XINGFA | Standard Selling | 145,000 | WOOD | IMPORT | 20 | WOOD_GRAIN |
| NHOM-XINGFA | Standard Selling | 98,000 | WHITE | DOMESTIC | 20 | POWDER_COATED |
| NHOM-ALUMIL | Standard Selling | 135,000 | WHITE | IMPORT | 20 | POWDER_COATED |
| TAY_NAM_KINLONG | Standard Selling | 210,000 | – | – | – | – |
| KINH-LOWE-24 | Standard Selling | 1,150,000 | – | – | – | – |
| KINH-DON-8 | Standard Selling | 550,000 | – | – | – | – |
| KEO-TT-01 | Standard Selling | 45,000 | – | – | – | – |
| KEO-TT-02 | Standard Selling | 30,000 | – | – | – | – |
| GIO-EPDM-55 | Standard Selling | 1,250 | – | – | – | – |
| VIT-TK-35X16 | Standard Selling | 850 | – | – | – | – |
| KL-MZS20 | Standard Selling | 210,000 | – | – | – | – |
| KL-KHOA-01 | Standard Selling | 350,000 | – | – | – | – |
| KL-T-MJ06 | Standard Selling | 180,000 | – | – | – | – |

*(BỔ SUNG) Dòng in đậm là dòng thực sự được dùng trong ví dụ tính toán ở mục 7, vì báo giá mẫu chọn `mau_nhom=WHITE, xuat_xu_nhom=IMPORT, do_day_nhom=20, be_mat_nhom=POWDER_COATED` → toàn bộ 10 dòng nhôm trong BOM đều tra ra **113,000đ/kg**.*

### 2.8. AL Glass Master (DocType custom)

| glass_code | glass_name | total_thick_mm | glass_type |
|---|---|---|---|
| KINH-LOWE-24 | Kính Low-E 24mm | **24** | **LOWE** |
| KINH-DON-8 | Kính dán 8mm | 8 | DON |

*(BỔ SUNG) Bảng này tách riêng khỏi Item vì độ dày/loại kính là dữ liệu kỹ thuật dùng để **chọn phụ kiện đi kèm** (nẹp, keo), không phải thuộc tính giá.*

### 2.9. AL Dynamic Item Rule (DocType custom — version qua Workflow)

**Rule 1: Chọn nẹp theo độ dày kính** (`RULE-NEP-GLASSTHICK` – THRESHOLD)

| from_value | to_value | item_code |
|---|---|---|
| 0 | 10.38 | C3209-20 |
| 10.39 | 16 | C3210-20 |
| **16.01** | **999** | **C3211-20** |

**Rule 2: Chọn keo theo loại kính** (`RULE-KEO-GLASSTYPE` – LOOKUP)

| key_1 | result_item |
|---|---|
| **LOWE** | **KEO-TT-01** |
| DON | KEO-TT-02 |

*(BỔ SUNG) Kính trong ví dụ này dày 24mm, loại LOWE → cả 2 rule trả về `C3211-20` (nẹp) và `KEO-TT-01` (keo) — chi tiết cách engine tra ra 2 kết quả này ở B2b, mục 5.*

### 2.10. AL Slug Library (DocType custom)

| slug | label | line_type | description |
|---|---|---|---|
| khung_ngang_tren | Khung ngang trên | NHOM | Thanh khung bao phía trên |
| khung_ngang_duoi | Khung ngang dưới | NHOM | Thanh khung bao phía dưới |
| khung_dung | Khung đứng | NHOM | Thanh khung bao đứng (2 bên) |
| do_ngang | Đố ngang | NHOM | Thanh ngang ngăn cách ô kính cố định và cánh |
| canh_ngang | Cánh ngang | NHOM | Thanh ngang của cánh cửa |
| canh_dung | Cánh đứng | NHOM | Thanh đứng của cánh cửa |
| kinh_tren | Kính cố định trên | KINH | Tấm kính phía trên đố |
| kinh_duoi | Kính cánh dưới | KINH | Tấm kính của mỗi cánh |
| nep_kinh_tren | Nẹp kính trên | NHOM | Nẹp giữ kính cố định |
| nep_kinh_duoi | Nẹp kính dưới | NHOM | Nẹp giữ kính cánh |
| keo_tren | Keo dán kính trên | VTP | Keo dùng cho kính cố định |
| keo_duoi | Keo dán kính dưới | VTP | Keo dùng cho kính cánh |
| gioang | Gioăng | VTP | Gioăng bao quanh khung |
| vit | Vít | VTP | Vít lắp ráp |
| tay_nam | Tay nắm | PHU_KIEN | Tay nắm cửa |
| khoa | Khóa | PHU_KIEN | Khóa cửa |
| ban_le | Bản lề | PHU_KIEN | Bản lề cửa |

*(BỔ SUNG) `slug` là định danh **duy nhất và ổn định** của mỗi dòng BOM — không đổi theo thời gian, không phụ thuộc thứ tự hiển thị (`sort`). Đây là "tên biến" mà mọi công thức cross-row (`items.<slug>.<field>`) sẽ tham chiếu tới.*

### 2.11. AL Quantity Calc Method (DocType mới)

> **(BỔ SUNG) Lưu ý kiến trúc quan trọng:** 4 công thức dưới đây **chỉ để hiển thị/tài liệu hóa cho người dùng đọc hiểu**, KHÔNG được dùng để "eval chuỗi bằng engine" lúc chạy thật. Việc tính toán thật sự dùng dispatch table Python cố định (mục 6.1). Lý do chi tiết ở mục 0.1 và mục 4.3.

| calc_pattern_code | calc_formula | Ghi chú |
|---|---|---|
| LENGTH_TO_WEIGHT | `(width/1000)*trong_luong_rieng` | NHOM, THEP, INOX |
| AREA | `(width/1000)*(height/1000)` | KINH |
| LENGTH_ONLY | `width/1000` | VTP đo theo mét (gioăng, keo) |
| COUNT | `1` | VTP đo theo cái (vít), PHU_KIEN |

### 2.12. AL Cost Bucket (DocType custom)

| bucket_code | bucket_name | bucket_role | parent_bucket | report_group |
|---|---|---|---|---|
| VL_NHOM | Vật liệu nhôm | LEAF | TONG_VL | A. Vật liệu |
| VL_KINH | Vật liệu kính | LEAF | TONG_VL | A. Vật liệu |
| VL_VTP | Vật tư phụ | LEAF | TONG_VL | A. Vật liệu |
| VL_PK | Phụ kiện | LEAF | TONG_VL | A. Vật liệu |
| TONG_VL | Tổng vật liệu | AGGREGATE | | A. Vật liệu |
| NC_SX | Nhân công sản xuất | LEAF | TONG_NC | B. Nhân công |
| NC_LD | Nhân công lắp đặt | LEAF | TONG_NC | B. Nhân công |
| TONG_NC | Tổng nhân công | AGGREGATE | | B. Nhân công |
| OH_VC | Overhead vận chuyển | LEAF | TONG_OH | C. Overhead |
| OH_QLY | Overhead quản lý | LEAF | TONG_OH | C. Overhead |
| TONG_OH | Tổng overhead | AGGREGATE | | C. Overhead |
| GIA_THANH | Giá thành | AGGREGATE | | D. Tổng hợp |
| GIA_BAN | Giá bán chưa VAT | AGGREGATE | | D. Tổng hợp |
| GIA_VAT | Giá bán có VAT | AGGREGATE | | D. Tổng hợp |

*(BỔ SUNG) Mỗi dòng trong 17 dòng BOM (mục 3) được gán vào đúng 1 bucket LEAF (VL_NHOM/VL_KINH/VL_VTP/VL_PK). Sau khi engine tính xong `thanh_tien` cho từng dòng, Python cộng dồn theo bucket ở phase B6 — thay thế hoàn toàn công thức `SUMIF` (vừa chậm vừa khó bảo trì khi BOM lớn).*

### 2.13. Formula Set (DocType của Formula Builder)

**Mã:** `BOM_LINE`  
**Label:** Công thức dòng BOM

**Các dòng công thức (child table):**

| var_name | formula | description |
|---|---|---|
| `so_luong_don_vi` | `lookup_calc_pattern(calc_pattern, width, height, trong_luong_rieng)` | Tính khối lượng/đơn vị dựa trên pattern |
| `tong_so_luong` | `so_luong_don_vi * qty` | Tổng khối lượng |
| `thanh_tien` | `tong_so_luong * don_gia` | Thành tiền |

*(BỔ SUNG) Đây chính là 3 công thức mà Formula Builder sẽ tính cho **từng dòng trong 17 dòng**, dùng chung 1 khuôn — khác nhau chỉ ở `width`, `height`, `qty`, `calc_pattern`, `trong_luong_rieng`, `don_gia` của từng dòng. Hàm `lookup_calc_pattern` được đăng ký vào `BASE_FUNCS`/`extra_funcs` của Formula Builder (xem mục 6).*

### 2.14. AL Cost Template (DocType custom)

**Mã:** `CT-01-STANDARD`

| line_code | calc_formula | is_subtotal | cost_bucket |
|---|---|---|---|
| TONG_VL | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` | 1 | TONG_VL |
| TONG_M2 | `(W_mm/1000)*(H_mm/1000)` | 0 | – |
| NC_SX | `$NC_SX_PCT * TONG_VL` | 0 | NC_SX |
| NC_LD | `$NC_LD_PCT * TONG_VL` | 0 | NC_LD |
| TONG_NC | `NC_SX + NC_LD` | 1 | TONG_NC |
| OH_VC | `$OH_VC_PCT * TONG_VL` | 0 | OH_VC |
| OH_QLY | `$OH_QLY_PCT * (TONG_VL + TONG_NC)` | 0 | OH_QLY |
| TONG_OH | `OH_VC + OH_QLY` | 1 | TONG_OH |
| GIA_THANH | `TONG_VL + TONG_NC + TONG_OH` | 1 | GIA_THANH |
| PROFIT | `$PROFIT_MARGIN * GIA_THANH` | 0 | – |
| GIA_BAN | `GIA_THANH + PROFIT` | 1 | GIA_BAN |
| DON_GIA_M2 | `GIA_BAN / TONG_M2` | 0 | – |
| VAT | `$VAT_RATE * GIA_BAN` | 0 | – |
| GIA_VAT | `GIA_BAN + VAT` | 1 | GIA_VAT |

*(BỔ SUNG) Đây là "kim tự tháp giá" — mỗi dòng dùng lại kết quả của (các) dòng phía trên. Engine tự nhận ra thứ tự tính đúng nhờ DAG (mục 4). Toàn bộ mục 7 sẽ đi theo đúng 14 dòng này.*

### 2.15. AL Variable Set (`VS-CDMQ`)

| var_name | var_label | var_type | default_val | Ghi chú |
|---|---|---|---|---|
| W_mm | Chiều rộng (mm) | FLOAT | 2400 | |
| H_mm | Chiều cao (mm) | FLOAT | 2600 | |
| TransomHeight_mm | Chiều cao ô kính trên (mm) | FLOAT | 600 | |
| n_canh | Số cánh | INT | 2 | |
| mau_nhom | Màu nhôm | LINK (AL Color Standard) | WHITE | Dùng chung cho NHOM |
| xuat_xu_nhom | Xuất xứ nhôm | SELECT | IMPORT | Dùng chung |
| do_day_nhom | Độ dày sơn/anode | INT | 20 | Dùng chung |
| be_mat_nhom | Bề mặt hoàn thiện | SELECT | POWDER_COATED | Dùng chung |

*(BỔ SUNG) Vì sao 4 biến màu/xuất xứ/độ dày/bề mặt nằm ở đây thay vì lặp lại trên từng dòng BOM? Vì trong thực tế nghiệp vụ, toàn bộ khung + cánh + nẹp của 1 bộ cửa luôn cùng 1 màu — khai báo 1 lần ở cấp báo giá, để mọi dòng nhôm tự "thừa hưởng" khi tra giá, thay vì phải nhập lại JSON màu trên từng dòng (dễ gõ sai, khó sửa hàng loạt khi đổi màu).*

---

<a name="3"></a>
## 3. SẢN PHẨM MẪU & CẤU HÌNH BOM (BẢN CHUẨN CUỐI, 17 DÒNG)

### 3.1. Thông tin sản phẩm

- **Tên sản phẩm:** Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)
- **Mã BOM:** BOM-CDMQ-2C
- **Mã Profile Set:** PS-CDMQ-2C
- **Mã Variable Set:** VS-CDMQ
- **Cost Template:** CT-01-STANDARD
- **Brand mặc định:** XINGFA
- **Source mặc định:** IMPORT
- **Màu mặc định:** WHITE
- **Độ dày mặc định:** 20mm
- **Bề mặt mặc định:** POWDER_COATED

### 3.2. `AL Profile Line` — 17 dòng

**Cột:** `sort`, `slug`, `line_type`, `width`, `height`, `qty`, `item_selection_mode`, `item_code`/`item_rule`, `cost_bucket`, `calc_pattern`, `price_base_item`, `price_attrs_override`, `accessory_finish`, `accessory_material`

| sort | slug | line_type | width | height | qty | item_selection_mode | item_code / rule | cost_bucket | calc_pattern | price_base_item |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | khung_ngang_tren | NHOM | `W_mm` | | `1` | Fixed | XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 20 | khung_ngang_duoi | NHOM | `W_mm` | | `1` | Fixed | XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 30 | khung_dung | NHOM | `H_mm` | | `2` | Fixed | XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 40 | do_ngang | NHOM | `W_mm - 2*$OFFSET_DO_NGANG` | | `1` | Fixed | XF55-KB-20 | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 50 | canh_ngang | NHOM | `W_mm/n_canh - $OFFSET_FRAME` | | `2*n_canh` | Fixed | XF55-CANH-20 | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 60 | canh_dung | NHOM | `(H_mm-TransomHeight_mm) - $OFFSET_FRAME` | | `2*n_canh` | Fixed | XF55-CANH-20 | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 70 | kinh_tren | KINH | `W_mm - 2*$OFFSET_FIXED` | `TransomHeight_mm - $OFFSET_FIXED` | `1` | Fixed | KINH-LOWE-24 | VL_KINH | AREA | – |
| 80 | kinh_duoi | KINH | `W_mm/n_canh - $OFFSET_GLASS` | `(H_mm-TransomHeight_mm) - $OFFSET_GLASS` | `n_canh` | Fixed | KINH-LOWE-24 | VL_KINH | AREA | – |
| 90 | nep_kinh_tren | NHOM | `2*(items.kinh_tren.width + items.kinh_tren.height)` | | `2` | Rule (input=`items.kinh_tren.glass_thick`) | RULE-NEP-GLASSTHICK | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 100 | nep_kinh_duoi | NHOM | `2*(items.kinh_duoi.width + items.kinh_duoi.height)` | | `2*n_canh` | Rule (input=`items.kinh_duoi.glass_thick`) | RULE-NEP-GLASSTHICK | VL_NHOM | LENGTH_TO_WEIGHT | NHOM-XINGFA |
| 110 | keo_tren | VTP | `2*(items.kinh_tren.width + items.kinh_tren.height)` | | `1` | Rule (input=`items.kinh_tren.glass_type`) | RULE-KEO-GLASSTYPE | VL_VTP | LENGTH_ONLY | – |
| 120 | keo_duoi | VTP | `2*(items.kinh_duoi.width + items.kinh_duoi.height)` | | `n_canh` | Rule (input=`items.kinh_duoi.glass_type`) | RULE-KEO-GLASSTYPE | VL_VTP | LENGTH_ONLY | – |
| 130 | gioang | VTP | `items.khung_ngang_tren.width + items.khung_ngang_duoi.width + 2*items.khung_dung.width` | | `1` | Fixed | GIO-EPDM-55 | VL_VTP | LENGTH_ONLY | – |
| 140 | vit | VTP | | | `10*n_canh + 8` | Fixed | VIT-TK-35X16 | VL_VTP | COUNT | – |
| 150 | tay_nam | PHU_KIEN | | | `1` | Fixed | KL-MZS20 | VL_PK | COUNT | TAY_NAM_KINLONG |
| 160 | khoa | PHU_KIEN | | | `1` | Fixed | KL-KHOA-01 | VL_PK | COUNT | – |
| 170 | ban_le | PHU_KIEN | | | `roundup(H_mm/700,0)*n_canh` | Fixed | KL-T-MJ06 | VL_PK | COUNT | – |

**Ghi chú quan trọng (không được làm sai khi nhập liệu):**
- Các dòng NHOM **không có cột `price_attributes` JSON** — 10 dòng nhôm tra giá bằng context chung từ `AL Variable Set` (`mau_nhom`, `xuat_xu_nhom`, `do_day_nhom`, `be_mat_nhom`), qua hàm `resolve_price_attrs()` ở mục 5 (B2.5).
- `price_attrs_override` chỉ dùng khi 1 dòng cụ thể **cố tình khác** cả BOM (hiếm gặp) — để trống với 16/17 dòng trên.
- Dòng `tay_nam` là **ngoại lệ duy nhất** dùng `accessory_finish=SATIN`, `accessory_material=STAINLESS` (2 field Select riêng, độc lập với màu khung nhôm — đúng thực tế nghiệp vụ).
- Input của `Rule` luôn dùng cú pháp `items.<slug>.<field>` — không có ngoại lệ.

**(BỔ SUNG) 3 điều quan trọng cần nhìn ra trong bảng này:**

1. **Cột `width`/`height`/`qty` là công thức, không phải số cố định** — chúng được tính dựa trên biến của Variable Set (`W_mm`, `H_mm`...) và hằng số offset (`$OFFSET_FRAME`...). Đây là lý do đổi kích thước cửa thì toàn bộ BOM tự tính lại.
2. **`items.<slug>.<field>` là cách một dòng "nhìn" sang dòng khác** — ví dụ dòng 90 (`nep_kinh_tren`) cần biết `width` và `height` **đã được tính xong** của dòng 70 (`kinh_tren`) để tính chu vi nẹp. Đây gọi là **tham chiếu chéo (cross-row reference)** — chính là lý do phải cần một engine giải DAG, không thể tính tuần tự từ trên xuống dưới một cách ngây thơ.
3. **`item_selection_mode = Rule`** (dòng 90, 100, 110, 120) nghĩa là Item không cố định — nó được **tra động** dựa trên input là dữ liệu của dòng khác (`items.kinh_tren.glass_thick`). Đây là lý do 2 Rule ở mục 2.9 tồn tại.

---

<a name="4"></a>
## 4. (BỔ SUNG) FORMULA ENGINE HOẠT ĐỘNG NHƯ THẾ NÀO?

### 4.1. Engine nhận vào gì, trả ra gì?

Engine (`FlexibleFormulaEngine`) không biết gì về "cửa nhôm". Nó chỉ nhận 2 thứ:

- **`formulas`**: một dictionary, ví dụ (rút gọn, chỉ lấy dòng `khung_ngang_tren` và `do_ngang` để minh họa):
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
      # ... lặp lại cho từng slug (đây chính là "row_literals" từ B2.5, xem mục 5)
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

**Vì sao đây là điều bắt buộc, không thể tính "từ trên xuống dưới theo `sort`"?** Vì `sort=90` (`nep_kinh_tren`) phụ thuộc vào kết quả của `sort=70` (`kinh_tren`) — nếu chỉ đơn giản tính tuần tự theo `sort` thì trùng hợp đúng thứ tự ở ví dụ này, nhưng **không có gì đảm bảo điều đó luôn đúng** với BOM khác (ví dụ nếu người thiết kế đặt `nep_kinh_tren` ở `sort=15`, tính trước `kinh_tren`, sẽ ra lỗi "biến chưa tồn tại" nếu tính ngây thơ theo thứ tự nhập liệu). DAG giải quyết vấn đề này một cách tổng quát — **không phụ thuộc thứ tự người dùng nhập**, chỉ phụ thuộc *quan hệ toán học thật sự* giữa các biến.

### 4.3. Vì sao `lookup_calc_pattern` KHÔNG được gọi ngược lại engine?

Nhắc lại từ mục 0.1 (bài học chung cho việc đăng ký hàm custom vào bất kỳ engine DAG nào):

- `lookup_calc_pattern(calc_pattern, width, height, trong_luong_rieng)` bản thân nó **là một hàm được engine gọi** khi nó đang tính node `so_luong_don_vi` (tức là engine đang *ở giữa* một lượt `calculate()`).
- Nếu bên trong hàm này lại **quay lại gọi `FlexibleFormulaEngine.evaluate_single(...)`** để "diễn giải" chuỗi công thức lấy từ bảng `AL Quantity Calc Method`, thì đây là **gọi đệ quy vào chính engine đang chạy** — vừa chậm, vừa làm hỏng khả năng `explain()`/trace của lượt tính "cha".
- **Cách làm đúng:** vì chỉ có đúng 4 pattern cố định và đã biết trước, `lookup_calc_pattern` chỉ cần là **1 dispatch table Python thuần** (if/elif), không đụng gì tới engine (code đầy đủ ở mục 6.1).

Hàm này được truyền vào engine lúc khởi tạo qua tham số `extra_funcs` — engine gọi nó như một hàm toán học bình thường (giống `sum()`, `roundup()`), không biết và không cần biết bên trong nó làm gì.

### 4.4. Cross-row reference hoạt động ra sao?

Cú pháp `items.<slug>.<field>` được engine hiểu nhờ cấu hình `child_table_configs={"items": {"id_field": "slug"}}` lúc khởi tạo — nó báo cho engine biết: *"có một bảng con tên là `items`, mỗi dòng của nó được định danh bằng field `slug`, và công thức có thể tham chiếu chéo giữa các dòng bằng cú pháp `items.<slug>.<field>`"*. Nhờ vậy dòng 90 viết được công thức `items.kinh_tren.width + items.kinh_tren.height` mà không cần biết trước `kinh_tren` được tính ra bao nhiêu — engine tự lo phần đó qua DAG.

---

<a name="5"></a>
## 5. BOMORCHESTRATOR — CHI TIẾT TỪNG PHASE (KÈM SỐ LIỆU THẬT)

```python
class BomOrchestrator:
    PHASES = [
        "B0_VERSION_PINNING",
        "B1_VARIABLE_RESOLVER",
        "B2A_RULE_RESOLVER_NO_CROSS",
        "B2_5_PRE_FETCH_MASTER",
        "B2B_RULE_RESOLVER_POST",
        "B3_PROFILE_SCAN",
        "B4_BUILD_FORMULAS",
        "B5_ENGINE_CALCULATE",
        "B6_GOM_COST_BUCKET",
        "B7_COST_TEMPLATE",
        "B8_SAVE_RESULTS",
    ]
```

**Input của người dùng cho ví dụ này (Quotation):**
```
W_mm = 2400          H_mm = 2600          TransomHeight_mm = 600      n_canh = 2
mau_nhom = WHITE      xuat_xu_nhom = IMPORT      do_day_nhom = 20      be_mat_nhom = POWDER_COATED
```

### B0 — Version Pinning
Xác định phiên bản hiệu lực của BOM (`AL BOM Version`), các Rule (`AL Dynamic Item Rule Version`), và Formula Global Variable dựa trên `valid_from` và ngày tạo Quotation. Lưu `bom_version_id`, `rule_version_ids`.

*(BỔ SUNG) Với ví dụ này: chốt `bom_version_id = BOM-CDMQ-2C-v1`, không có version Rule nào khác 1. Mục đích: nếu sau này đổi giá hoặc đổi offset, báo giá cũ vẫn tính ra đúng số cũ khi mở lại (tái lập được).*

### B1 — VariableResolver
Thu thập biến từ **Quotation Input** (W_mm, H_mm, TransomHeight_mm, n_canh, mau_nhom, …). Lấy hằng số từ `AL Calculation Rule` (nếu chưa có trong Variable Set). Lấy biến từ `Formula Global Variable` ($NC_SX_PCT, …). **Lưu ý:** Chưa inject `glass_thick`/`glass_type` – sẽ làm ở B2.5.

*(BỔ SUNG) Kết quả B1 cho ví dụ này:*
```
inputs = {
  W_mm: 2400, H_mm: 2600, TransomHeight_mm: 600, n_canh: 2,
  mau_nhom: "WHITE", xuat_xu_nhom: "IMPORT", do_day_nhom: 20, be_mat_nhom: "POWDER_COATED",
  OFFSET_FRAME: 48, OFFSET_GLASS: 90, OFFSET_FIXED: 50, OFFSET_DO_NGANG: 48,
  NC_SX_PCT: 0.08, NC_LD_PCT: 0.12, OH_VC_PCT: 0.03, OH_QLY_PCT: 0.03,
  PROFIT_MARGIN: 0.16, VAT_RATE: 0.10
}
```

### B2a — Rule Resolver (không cross-row)
Duyệt các dòng có `item_selection_mode = "Rule"` nhưng input **không** chứa `items.`. Trong ví dụ này không có, nên bỏ qua.

*(BỔ SUNG) Phase chạy nhưng không làm gì với BOM CDMQ-2C-TRANSOM — cả 2 Rule của BOM này đều là cross-row. Phase vẫn được giữ trong pipeline vì BOM khác (ví dụ chọn phụ kiện theo trọng lượng cánh, không phụ thuộc dòng nào khác) có thể cần.*

### B2.5 — Pre-fetch Master Data
**Bước này được cải tiến để đăng ký handlers vào Formula Builder (xem Phần 6).**

Thực hiện:
- Đọc các dòng `NHOM` để lấy `trong_luong_rieng` từ Item.
- Đọc các dòng `KINH` để lấy `glass_thick` và `glass_type` từ `AL Glass Master`.
- Đọc các dòng có `price_base_item` để lấy giá từ `Item Price` (batch query).
- **Cách tra giá:** Dùng composite key từ `base_item` + các thuộc tính (màu, xuất xứ, …) và query một lần.
- Ghi kết quả vào `row_literals` (dictionary lưu theo slug).
- Sau đó, đưa `row_literals` vào `inputs` dưới dạng các biến literal: `trong_luong_rieng_{slug}`, `don_gia_{slug}`, `glass_thick_{slug}`, `glass_type_{slug}`.

```python
def b2_5_pre_fetch_master(profile_lines, inputs, resolved_items):
    row_literals = {}

    # 1) Trọng lượng riêng cho các dòng NHOM/THEP/INOX (batch query 1 lần)
    nhom_item_codes = list({
        resolved_items.get(l.slug, l.item_code)
        for l in profile_lines if l.line_type == "NHOM"
    })
    weight_map = {
        d.item_code: d.weight_per_unit
        for d in frappe.db.get_all(
            "Item", filters={"item_code": ["in", nhom_item_codes]},
            fields=["item_code", "weight_per_unit"]
        )
    }

    # 2) Giá cho các dòng có price_base_item — composite key, batch query
    base_items = list({l.price_base_item for l in profile_lines if l.price_base_item})
    price_map = _batch_price_lookup(base_items, price_list="Standard Selling")

    for line in profile_lines:
        row_literals.setdefault(line.slug, {})

        if line.line_type == "NHOM":
            item_code = resolved_items.get(line.slug, line.item_code)
            row_literals[line.slug]["trong_luong_rieng"] = weight_map.get(item_code)

        if line.price_base_item:
            attrs = resolve_price_attrs(line, inputs)   # xem hàm bên dưới
            row_literals[line.slug]["don_gia"] = price_map.get(
                _composite_key(line.price_base_item, attrs)
            )

        # 3) glass_thick / glass_type — ghi literal NGAY TRÊN DÒNG KINH
        if line.line_type == "KINH":
            glass_code = resolved_items.get(line.slug, line.item_code)
            glass = frappe.db.get_value(
                "AL Glass Master", {"glass_code": glass_code},
                ["total_thick_mm", "glass_type"], as_dict=True
            )
            row_literals[line.slug]["glass_thick"] = glass.total_thick_mm
            row_literals[line.slug]["glass_type"] = glass.glass_type

    return row_literals


def resolve_price_attrs(line, inputs):
    """Nguồn chân lý duy nhất cho price attrs của dòng NHOM/THEP/INOX."""
    if line.price_attrs_override:
        return json.loads(line.price_attrs_override)
    if line.line_type in ("NHOM", "THEP", "INOX"):
        return {
            "color": inputs.get("mau_nhom"),
            "source": inputs.get("xuat_xu_nhom"),
            "thickness": inputs.get("do_day_nhom"),
            "surface": inputs.get("be_mat_nhom"),
        }
    if line.line_type == "PHU_KIEN" and (line.accessory_finish or line.accessory_material):
        return {"finish": line.accessory_finish, "material": line.accessory_material}
    return None
```

*(BỔ SUNG) Kết quả B2.5 (`row_literals`) cho ví dụ CDMQ-2C-TRANSOM:*

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

> Với `mau_nhom=WHITE, xuat_xu_nhom=IMPORT, do_day_nhom=20, be_mat_nhom=POWDER_COATED`, cả 10 dòng nhôm tra ra cùng đơn giá **113,000đ/kg** (đúng dòng in đậm ở Item Price mục 2.7). Dòng `tay_nam` dùng `accessory_finish=SATIN, accessory_material=STAINLESS` (độc lập màu khung), tra ra **210,000đ/cái**. Dòng `nep_kinh_tren`/`nep_kinh_duoi`: `trong_luong_rieng=0.312` ứng với Item nẹp **sẽ được Rule chọn** ở B2b (đã biết trước sẽ là `C3211-20` vì `glass_thick=24 > 16.01`); `don_gia=113,000` vì `price_base_item=NHOM-XINGFA` — giá/kg như nhau cho mọi profile Xingfa cùng màu.

`row_literals` sau đó được nạp vào `inputs` dưới đúng cú pháp cross-row `items.<slug>.<field>` — ví dụ `inputs["items.kinh_tren.glass_thick"] = 24`.

### B2b — Rule Resolver (có cross-row)
Resolve các Rule mà input có tham chiếu `items.`. Ví dụ: `nep_kinh_tren` dùng `items.kinh_tren.glass_thick` – lúc này `glass_thick` đã có trong row_literals. Tra Rule và gán `item_code` tương ứng.

```python
for line in profile_lines:
    if line.item_selection_mode == "Rule" and "items." in line.rule_input_expr:
        input_value = resolve_cross_row_ref(line.rule_input_expr, row_literals)
        resolved_items[line.slug] = apply_dynamic_rule(line.item_rule, input_value)
```

*(BỔ SUNG) Kết quả B2b cho ví dụ này:*

| Dòng | Input dùng để tra | Rule | Kết quả |
|---|---|---|---|
| nep_kinh_tren | `items.kinh_tren.glass_thick = 24` | RULE-NEP-GLASSTHICK (THRESHOLD, khoảng 16.01–999) | **C3211-20** |
| nep_kinh_duoi | `items.kinh_duoi.glass_thick = 24` | RULE-NEP-GLASSTHICK | **C3211-20** |
| keo_tren | `items.kinh_tren.glass_type = LOWE` | RULE-KEO-GLASSTYPE (LOOKUP) | **KEO-TT-01** |
| keo_duoi | `items.kinh_duoi.glass_type = LOWE` | RULE-KEO-GLASSTYPE | **KEO-TT-01** |

### B3 — ProfileInterpreter Pass 1 (Scan)
Duyệt tất cả dòng, xác định các biến cần tính: `{slug}.width`, `{slug}.height`, `{slug}.qty`. Phát hiện tham chiếu chéo (`items.`) để ghi nhận phụ thuộc. Xác định `calc_pattern` cho từng dòng.

*(BỔ SUNG) Với ví dụ này, B3 nhận diện được 4 quan hệ phụ thuộc cross-row: `nep_kinh_tren`←`kinh_tren`, `nep_kinh_duoi`←`kinh_duoi`, `keo_tren`←`kinh_tren`, `keo_duoi`←`kinh_duoi`, cộng thêm `gioang` phụ thuộc `khung_ngang_tren`, `khung_ngang_duoi`, `khung_dung` — đây là thông tin engine dùng để xây DAG đúng ở B5.*

### B4 — Build Formulas
Xây dựng dictionary `formulas` cho Formula Engine:
- Công thức width/height/qty lấy từ Profile Line.
- Công thức tính khối lượng và thành tiền lấy từ Formula Set `BOM_LINE` (dùng hàm `lookup_calc_pattern`).
- Các biến literal (trong_luong_rieng, don_gia, glass_thick, glass_type) đã có trong `inputs`.

*(BỔ SUNG) Kết quả B4 là 1 dictionary `formulas` với khoảng 17×6=102 biến (width, height, qty, so_luong_don_vi, tong_so_luong, thanh_tien × 17 dòng, một số dòng không có height nên ít hơn) — ví dụ minh họa ở mục 4.1.*

### B5 — Engine Calculate
Khởi tạo `FlexibleFormulaEngine` với `child_table_configs` (table_key="items", id_field="slug"). Gọi `engine.calculate(formulas, inputs)`. Engine parse, xây DAG, sắp xếp tô-pô, tính toán và trả về `result`.

```python
engine = FlexibleFormulaEngine(
    child_table_configs={"items": {"id_field": "slug"}},
    extra_funcs={"lookup_calc_pattern": lookup_calc_pattern},
)
result = engine.calculate(formulas, inputs)
```

*(BỔ SUNG) Kết quả đầy đủ của B5 — bảng tính 17 dòng mở rộng từng phép thay số — nằm ở mục 7.*

### B6 — Gom Cost Bucket (Python)
Duyệt từng slug, lấy `thanh_tien` từ `result`. Gom theo `cost_bucket` để có `VL_NHOM`, `VL_KINH`, `VL_VTP`, `VL_PK`. Đồng thời tạo `line_results` (list chi tiết) để lưu child table.

```python
def b6_gom_cost_bucket(profile_lines, result):
    buckets = defaultdict(float)
    line_results = []
    for line in profile_lines:
        tt = result["items"][line.slug]["thanh_tien"]
        buckets[line.cost_bucket] += tt
        line_results.append({"slug": line.slug, **result["items"][line.slug]})
    return dict(buckets), line_results
```

*(BỔ SUNG) Kết quả B6 cho ví dụ này: `VL_NHOM=4,895,431`, `VL_KINH=6,330,980`, `VL_VTP=836,400`, `VL_PK=2,000,000` (chi tiết cách cộng từng dòng ở mục 7.2).*

### B7 — Cost Template
Lấy công thức từ `AL Cost Template`. Tạo `cost_formulas` và tính với engine (dùng inputs đã có `VL_*`). Kết quả: TONG_VL, NC_SX, GIA_BAN, VAT, GIA_VAT, …

*(BỔ SUNG) Kết quả đầy đủ 14 bước của B7 nằm ở mục 7.3, kết thúc bằng `GIA_VAT = 22,717,289đ`.*

### B8 — Save Results
Lưu child table `al_bom_line_results` vào Quotation Item. Lưu `ConfigSnapshot` với đầy đủ inputs, formulas, result, DAG structure, trace (dùng `engine.get_trace()` và `engine.get_dag_structure()` nếu Formula Builder hỗ trợ).

---

<a name="6"></a>
## 6. TÍCH HỢP FORMULA BUILDER – ĐĂNG KÝ HANDLERS ĐÃ SỬA LỖI KIẾN TRÚC

### 6.1. `lookup_calc_pattern` — ĐÃ SỬA (không còn gọi đệ quy vào engine)

**File:** `alumglass/formula_handlers.py` (đăng ký vào engine của AlumGlass qua `extra_funcs`, **không** sửa code app Formula Builder)

```python
import frappe

_CALC_METHOD_CACHE = {}

def _get_calc_formula_text(calc_pattern_code):
    """Chỉ để hiển thị/audit — KHÔNG dùng để evaluate."""
    if calc_pattern_code not in _CALC_METHOD_CACHE:
        _CALC_METHOD_CACHE[calc_pattern_code] = frappe.db.get_value(
            "AL Quantity Calc Method", {"calc_pattern_code": calc_pattern_code}, "calc_formula"
        )
    return _CALC_METHOD_CACHE[calc_pattern_code]


def lookup_calc_pattern(calc_pattern_code, width=None, height=None, trong_luong_rieng=None):
    """
    Tính số lượng đơn vị (kg / m2 / m / cái) theo 1 trong 4 pattern cố định.

    QUAN TRỌNG: hàm này được đăng ký vào BASE_FUNCS/extra_funcs của Formula Builder,
    tức là nó chạy TỪ BÊN TRONG một lượt engine.calculate() đang xử lý DAG.
    KHÔNG được gọi ngược lại engine (FlexibleFormulaEngine.evaluate_single hay bất kỳ
    phương thức nào của engine) từ đây — đó là lỗi đệ quy/kiến trúc đã từng xảy ra
    (xem mục 0.1 của tài liệu). Toàn bộ phép tính ở đây dùng số học Python thuần.
    """
    if not calc_pattern_code:
        return 0

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

    frappe.throw(
        f"calc_pattern_code '{calc_pattern_code}' chưa được hỗ trợ. "
        f"Công thức khai báo trong AL Quantity Calc Method: {_get_calc_formula_text(calc_pattern_code)}"
    )
```

> Nếu sau này có pattern thứ 5+ (ví dụ tính theo chu vi tam giác cho vách kính chéo), **thêm 1 nhánh `if` mới** vào đúng hàm này — không quay lại cách "eval chuỗi công thức bằng engine con".

### 6.2. `price_lookup` và `glass_lookup` — đăng ký vào `data_source_registry` (giữ nguyên từ v26)

```python
def _handle_price_lookup(source_config, context):
    """Tra giá từ Item Price theo base_item + attributes (đọc cache đã batch ở B2.5)."""
    base_item = source_config.get("base_item")
    attrs = source_config.get("attrs", {})
    if not base_item:
        return None
    ordered_attrs = ["color", "source", "thickness", "surface", "finish", "material"]
    parts = [base_item] + [str(attrs.get(a, "NULL")) for a in ordered_attrs]
    key = "|".join(parts)
    return _get_price_map([base_item]).get(key)


def _handle_glass_lookup(source_config, context):
    glass_code = source_config.get("glass_code")
    if not glass_code:
        return None
    return frappe.db.get_value(
        "AL Glass Master", {"glass_code": glass_code},
        ["total_thick_mm", "glass_type"], as_dict=True
    )
```

Hai handler này **không bắt buộc** dùng trong luồng B2.5 (vốn dùng batch query trực tiếp để tối ưu hiệu năng) — chúng tồn tại để các công thức khác trong tương lai có thể tái sử dụng nguồn dữ liệu này một cách nhất quán, có `explain()`.

### 6.3. Sử dụng trong BomOrchestrator

- Ở B2.5, thay vì tự query, có thể dùng các handler này nếu muốn công thức được trace.
- Tuy nhiên, do pre-fetch là bước tối ưu hiệu năng, vẫn nên giữ batch query và chỉ đưa kết quả vào inputs.
- Việc đăng ký handler giúp cho các công thức trong tương lai (nếu có) có thể dùng các nguồn dữ liệu này một cách nhất quán.

---

<a name="7"></a>
## 7. VÍ DỤ TÍNH TOÁN ĐẦY ĐỦ — MỞ RỘNG TỪNG PHÉP THAY SỐ (SỐ LIỆU ĐÃ SỬA)

### 7.1. Inputs

```
W_mm=2400, H_mm=2600, TransomHeight_mm=600, n_canh=2
mau_nhom=WHITE, xuat_xu_nhom=IMPORT, do_day_nhom=20, be_mat_nhom=POWDER_COATED
OFFSET_FRAME=48, OFFSET_GLASS=90, OFFSET_FIXED=50, OFFSET_DO_NGANG=48
```

### 7.2. (BỔ SUNG) B5 — Mở rộng từng phép thay số cho 8 dòng đại diện mọi loại

#### a) Dòng NHOM đơn giản — `khung_ngang_tren`
- `width = W_mm = 2400`; `qty = 1`
- `calc_pattern = LENGTH_TO_WEIGHT`, `trong_luong_rieng = 1.257` (từ B2.5)
- `so_luong_don_vi = lookup_calc_pattern("LENGTH_TO_WEIGHT", 2400, None, 1.257) = (2400/1000) × 1.257 = 2.4 × 1.257 = 3.0168 kg`
- `tong_so_luong = 3.0168 × 1 = 3.0168 kg`
- `don_gia = 113,000` (từ B2.5, theo tổ hợp WHITE/IMPORT/20/POWDER_COATED)
- `thanh_tien = 3.0168 × 113,000 = 340,898`

#### b) Dòng NHOM có offset — `do_ngang`
- `width = W_mm - 2×$OFFSET_DO_NGANG = 2400 - 2×48 = 2400 - 96 = 2304`; `qty = 1`
- `so_luong_don_vi = (2304/1000) × 1.257 = 2.304 × 1.257 = 2.8961 kg`
- `tong_so_luong = 2.8961 × 1 = 2.8961 kg`
- `thanh_tien = 2.8961 × 113,000 = 327,259`

#### c) Dòng NHOM chia theo số cánh — `canh_ngang`
- `width = W_mm/n_canh - $OFFSET_FRAME = 2400/2 - 48 = 1200 - 48 = 1152`
- `qty = 2×n_canh = 2×2 = 4` *(mỗi cánh có 2 thanh ngang: trên + dưới)*
- `so_luong_don_vi = (1152/1000) × 1.350 = 1.152 × 1.350 = 1.5552 kg` *(dùng profile `XF55-CANH-20`, trọng lượng riêng 1.350 kg/m — khác khung 1.257 kg/m)*
- `tong_so_luong = 1.5552 × 4 = 6.2208 kg`
- `thanh_tien = 6.2208 × 113,000 = 702,950`

#### d) Dòng KINH — `kinh_tren`
- `width = W_mm - 2×$OFFSET_FIXED = 2400 - 2×50 = 2300`
- `height = TransomHeight_mm - $OFFSET_FIXED = 600 - 50 = 550`; `qty = 1`
- `calc_pattern = AREA` → `so_luong_don_vi = (2300/1000) × (550/1000) = 2.3 × 0.55 = 1.265 m²`
- `tong_so_luong = 1.265 × 1 = 1.265 m²`; `don_gia = 1,150,000`
- `thanh_tien = 1.265 × 1,150,000 = 1,454,750`

#### e) Dòng NHOM cross-row — `nep_kinh_tren` (minh họa rõ nhất cơ chế DAG)
- **Item được chọn động qua Rule** (đã resolve ở B2b): `glass_thick = items.kinh_tren.glass_thick = 24` → Rule trả `C3211-20` (0.312 kg/m)
- `width = 2×(items.kinh_tren.width + items.kinh_tren.height)` — **đọc trực tiếp kết quả đã tính ở mục (d)**, không tính lại: `= 2×(2300+550) = 2×2850 = 5700`
- `qty = 2` *(2 nẹp mỗi kính: trên + dưới)*
- `so_luong_don_vi = (5700/1000) × 0.312 = 5.7 × 0.312 = 1.7784 kg`
- `tong_so_luong = 1.7784 × 2 = 3.5568 kg`
- `thanh_tien = 3.5568 × 113,000 = 401,918`

#### f) Dòng VTP cross-row — `keo_tren`
- **Item động qua Rule**: `glass_type = items.kinh_tren.glass_type = "LOWE"` → `KEO-TT-01` (45,000đ/m)
- `width = 2×(items.kinh_tren.width + items.kinh_tren.height) = 5700` *(cùng công thức chu vi như nẹp, dùng lại kết quả của `kinh_tren`)*
- `qty = 1`; `calc_pattern = LENGTH_ONLY` → `so_luong_don_vi = 5700/1000 = 5.7 m`
- `tong_so_luong = 5.7 × 1 = 5.7 m`
- `thanh_tien = 5.7 × 45,000 = 256,500`

#### g) Dòng VTP đo theo cái — `vit`
- `qty = 10×n_canh + 8 = 10×2 + 8 = 28`
- `calc_pattern = COUNT` → `so_luong_don_vi = 1` *(không phụ thuộc width/height)*
- `tong_so_luong = 1 × 28 = 28 cái`
- `thanh_tien = 28 × 850 = 23,800`

#### h) Dòng PHỤ KIỆN — `ban_le`
- `qty = roundup(H_mm/700, 0) × n_canh = roundup(2600/700, 0) × 2 = roundup(3.714, 0) × 2 = 4 × 2 = 8` *(làm tròn lên: mỗi 700mm chiều cao cần thêm 1 bản lề)*
- `so_luong_don_vi = 1` (COUNT); `tong_so_luong = 1 × 8 = 8 cái`
- `thanh_tien = 8 × 180,000 = 1,440,000`

### 7.3. Kết quả B5 (FormulaEngine) – bảng tính chi tiết, ĐÃ SỬA 2 DÒNG (in đậm)

| slug | width | height | qty | so_luong_don_vi | tong_so_luong | thanh_tien |
|---|---|---|---|---|---|---|
| khung_ngang_tren | 2400 | – | 1 | 3.0168 kg | 3.0168 kg | 340,898 |
| khung_ngang_duoi | 2400 | – | 1 | 3.0168 kg | 3.0168 kg | 340,898 |
| khung_dung | 2600 | – | 2 | 3.2682 kg | 6.5364 kg | 738,613 |
| do_ngang | 2304 | – | 1 | 2.8961 kg | 2.8961 kg | 327,259 |
| **canh_ngang** | 1152 | – | 4 | 1.5552 kg | 6.2208 kg | **702,950** |
| **canh_dung** | 1952 | – | 4 | 2.6352 kg | 10.5408 kg | **1,191,110** |
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

> Kiểm chứng nhanh: `canh_ngang` = 6.2208 kg × 113,000 = 702,950.4 → **702,950**. `canh_dung` = 10.5408 kg × 113,000 = 1,191,110.4 → **1,191,110**. (Bản gốc v26/Grok ghi nhầm 702,550 và 1,190,110.)
>
> *(BỔ SUNG) Dòng `canh_dung`: `width = (H_mm - TransomHeight_mm) - $OFFSET_FRAME = (2600-600)-48 = 1952`, `qty=2×n_canh=4`, `so_luong_don_vi=(1952/1000)×1.350=2.6352 kg`, `tong_so_luong=2.6352×4=10.5408 kg`. Các dòng `nep_kinh_duoi`, `keo_duoi`, `gioang`, `kinh_duoi` áp dụng đúng cơ chế cross-row/offset như các ví dụ (b)–(f) ở trên, chỉ khác slug tham chiếu.*

### 7.4. Gom cost bucket (B6) — ĐÃ SỬA

| Bucket | Các dòng cộng vào (BỔ SUNG) | Tổng (VND) | So với bản gốc |
|---|---|---|---|
| **VL_NHOM** | khung_ngang_tren+khung_ngang_duoi+khung_dung+do_ngang+canh_ngang+canh_dung+nep_kinh_tren+nep_kinh_duoi = 340,898+340,898+738,613+327,259+702,950+1,191,110+401,918+851,785 | **4,895,431** | gốc: 4,894,031 → **+1,400** |
| VL_KINH | kinh_tren+kinh_duoi = 1,454,750+4,876,230 | 6,330,980 | không đổi |
| VL_VTP | keo_tren+keo_duoi+gioang+vit = 256,500+543,600+12,500+23,800 | 836,400 | không đổi |
| VL_PK | tay_nam+khoa+ban_le = 210,000+350,000+1,440,000 | 2,000,000 | không đổi |

### 7.5. Cost Template (B7) — kết quả cuối, ĐÃ SỬA, theo đúng thứ tự DAG

*(BỔ SUNG) Thứ tự dưới đây chính là thứ tự tô-pô mà engine sẽ chạy — mỗi dòng chỉ dùng kết quả của (các) dòng phía trên nó:*

| # | line_code | Công thức thay số (BỔ SUNG) | Kết quả (VND) | So với bản gốc |
|---|---|---|---|---|
| 1 | TONG_VL | `4,895,431 + 6,330,980 + 836,400 + 2,000,000` | **14,062,811** | gốc: 14,061,411 (+1,400) |
| 2 | TONG_M2 | `(2400/1000)×(2600/1000) = 2.4×2.6` | 6.24 m² | – |
| 3 | NC_SX | `0.08 × 14,062,811` | 1,125,025 | gốc: 1,124,913 |
| 4 | NC_LD | `0.12 × 14,062,811` | 1,687,537 | gốc: 1,687,369 |
| 5 | TONG_NC | `1,125,025 + 1,687,537` | **2,812,562** | gốc: 2,812,282 |
| 6 | OH_VC | `0.03 × 14,062,811` | 421,884 | gốc: 421,842 |
| 7 | OH_QLY | `0.03 × (14,062,811+2,812,562) = 0.03×16,875,373` | 506,261 | gốc: 506,211 |
| 8 | TONG_OH | `421,884 + 506,261` | **928,145** | gốc: 928,053 |
| 9 | GIA_THANH | `14,062,811 + 2,812,562 + 928,145` | **17,803,518** | gốc: 17,801,746 |
| 10 | PROFIT | `0.16 × 17,803,518` | 2,848,563 | gốc: 2,848,279 |
| 11 | GIA_BAN | `17,803,518 + 2,848,563` | **20,652,081** | gốc: 20,650,025 |
| 12 | DON_GIA_M2 | `20,652,081 / 6.24` | 3,309,628 | gốc: 3,309,299 |
| 13 | VAT | `0.10 × 20,652,081` | 2,065,208 | gốc: 2,065,003 |
| 14 | GIA_VAT | `20,652,081 + 2,065,208` | **22,717,289** | gốc: 22,715,028 → **chênh lệch +2,261đ** |

**Giá bán cuối cùng (có VAT) đúng phải là 22,717,289đ — không phải 22,715,028đ như bản gốc.**

*(BỔ SUNG) Vì sao thứ tự này bắt buộc, không thể tính `OH_QLY` trước `TONG_NC`? Vì công thức `OH_QLY = $OH_QLY_PCT * (TONG_VL + TONG_NC)` tham chiếu trực tiếp tới `TONG_NC` — DAG buộc `TONG_NC` (và cả `NC_SX`, `NC_LD` mà nó phụ thuộc) phải tính xong trước. Đây là minh chứng thứ hai (sau mục 4.2 và 7.2.e) cho thấy DAG không phải chi tiết kỹ thuật phụ — nó là lý do duy nhất khiến hệ thống tính đúng thứ tự dù công thức được nhập theo bất kỳ trật tự nào trong bảng cấu hình.*

---

<a name="8"></a>
## 8. HƯỚNG DẪN TRIỂN KHAI TỪNG BƯỚC TRÊN FRAPPE/ERPNext

### 8.1. Chuẩn bị app & dependency
```bash
# Formula Builder đã có sẵn, cài vào site trước
bench get-app formula_builder <path-or-git-url>
bench --site your-site install-app formula_builder

# Tạo app AlumGlass (nếu chưa có)
bench new-app alumglass
bench --site your-site install-app alumglass
```

### 8.2. Tạo các DocType custom (thứ tự bắt buộc — DocType sau tham chiếu DocType trước)

Thứ tự tạo qua UI (Desk → New DocType) hoặc qua `bench make-app`/JSON fixture, đúng theo mục 2:

1. `AL Color Standard`
2. `AL Calculation Rule`
3. `AL Glass Master`
4. `AL Dynamic Item Rule` (+ `AL Dynamic Item Rule Version` nếu version hóa qua Workflow)
5. `AL Slug Library`
6. `AL Quantity Calc Method`
7. `AL Cost Bucket`
8. `AL Cost Template` (child table riêng cho các dòng công thức)
9. `AL Variable Set` (child table `AL Variable Set Item`)
10. `AL Profile Line` (child table, gắn vào `AL Profile Set`)
11. `AL Profile Set`
12. `AL BOM` (liên kết Profile Set + Variable Set + Cost Template)
13. `AL BOM Version` (version hóa BOM)
14. `ConfigSnapshot` (lưu kết quả tính + trace)

> Mỗi DocType custom nên có ít nhất field `is_active`/`valid_from` để hỗ trợ B0 (version pinning).

### 8.3. Custom Fields trên DocType chuẩn ERPNext

**Trên `Item Price`:**
```python
# alumglass/patches/add_item_price_fields.py (hoặc qua Customize Form UI)
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

create_custom_fields({
    "Item Price": [
        {
            "fieldname": "custom_mau_sac", "label": "Màu sắc",
            "fieldtype": "Link", "options": "AL Color Standard",
            "insert_after": "price_list_rate"
        },
        {
            "fieldname": "custom_xuat_xu", "label": "Xuất xứ",
            "fieldtype": "Select", "options": "IMPORT\nDOMESTIC",
            "insert_after": "custom_mau_sac"
        },
        {
            "fieldname": "custom_do_day", "label": "Độ dày (micron)",
            "fieldtype": "Int", "insert_after": "custom_xuat_xu"
        },
        {
            "fieldname": "custom_be_mat", "label": "Bề mặt",
            "fieldtype": "Select",
            "options": "POWDER_COATED\nANODIZED\nWOOD_GRAIN",
            "insert_after": "custom_do_day"
        },
    ]
})
```

**Trên `Item`:** `al_item_type` (Select: NHOM_PROFILE/KINH/VTP/PHU_KIEN), `al_is_color_variable` (Check).

### 8.4. Server Script chặn trùng Item Price

```python
# Server Script, DocType Event = Before Save, Document Type = Item Price
def validate_unique_price_combo(doc, method=None):
    filters = {
        "item_code": doc.item_code,
        "price_list": doc.price_list,
        "custom_mau_sac": doc.custom_mau_sac,
        "custom_xuat_xu": doc.custom_xuat_xu,
        "custom_do_day": doc.custom_do_day,
        "custom_be_mat": doc.custom_be_mat,
        "name": ["!=", doc.name],
    }
    if frappe.db.exists("Item Price", filters):
        frappe.throw(
            f"Đã tồn tại giá cho tổ hợp {doc.item_code} / {doc.custom_mau_sac} / "
            f"{doc.custom_xuat_xu} / {doc.custom_do_day} / {doc.custom_be_mat} "
            f"trong bảng giá {doc.price_list}."
        )
```

### 8.5. Nhập Master Data

Dùng `bench execute` với fixture JSON, hoặc nhập tay qua Desk UI theo đúng bảng dữ liệu ở mục 2.1 → 2.15 (thứ tự từ trên xuống, vì các bảng sau tham chiếu Link tới bảng trước).

Khuyến nghị: viết 1 script `alumglass/setup/seed_demo_data.py` chạy 1 lần qua `bench execute alumglass.setup.seed_demo_data.run` để tái lập toàn bộ dữ liệu mẫu này cho môi trường test/demo, tránh nhập tay lặp lại.

### 8.6. Cài đặt `BomOrchestrator`

Đặt file `alumglass/bom_orchestrator.py` với class như mục 5, đăng ký thành API:
```python
@frappe.whitelist()
def calculate_bom(quotation_item_name):
    orchestrator = BomOrchestrator(quotation_item_name)
    return orchestrator.run_all_phases()
```

Gắn vào form Quotation Item (client script) để gọi khi người dùng bấm "Tính giá" hoặc tự động khi lưu.

### 8.7. Đăng ký `extra_funcs` vào Formula Builder engine

Trong lúc khởi tạo engine ở B5, truyền `lookup_calc_pattern` (mục 6.1) vào tham số `extra_funcs`/`safe_funcs` mà **Formula Builder đã hỗ trợ sẵn** (không sửa code app Formula Builder) — kiểm tra tài liệu app Formula Builder của bạn về tên tham số chính xác (`extra_funcs`, `custom_functions`, hay cơ chế đăng ký khác), vì tài liệu này không có quyền giả định cấu trúc nội bộ của app đó.

### 8.8. Chạy thử & đối chiếu

Chạy `calculate_bom()` với input ở mục 7.1, đối chiếu từng dòng với bảng 7.3–7.5. Nếu lệch bất kỳ số nào so với bảng đã sửa ở tài liệu này — không phải bản gốc — thì có lỗi trong lúc cài đặt cần rà lại.

---

<a name="9"></a>
## 9. CHECKLIST KIỂM THỬ

### 9.1. Master Data
- [ ] Item Group, Brand, AL Color Standard, AL Calculation Rule, Formula Global Variable
- [ ] Item (đại diện + profile cụ thể), Item Price (+ custom fields + validate chặn trùng)
- [ ] AL Glass Master, AL Dynamic Item Rule (2 rule), AL Slug Library (17 slug)
- [ ] AL Quantity Calc Method (4 record — chỉ để hiển thị, không dùng để eval)
- [ ] AL Cost Bucket (14 bucket), AL Cost Template (CT-01-STANDARD, 14 dòng)
- [ ] Formula Set BOM_LINE (3 công thức)
- [ ] AL Variable Set VS-CDMQ (8 biến)
- [ ] AL Profile Set PS-CDMQ-2C (17 dòng, đúng bảng mục 3)
- [ ] AL BOM BOM-CDMQ-2C

### 9.2. Cấu hình kỹ thuật
- [ ] `lookup_calc_pattern` đăng ký vào engine bằng dispatch table thuần Python (mục 6.1) — **xác nhận KHÔNG có lời gọi ngược vào FlexibleFormulaEngine bên trong hàm này**
- [ ] `price_lookup`, `glass_lookup` đăng ký vào `data_source_registry` (tùy chọn, không bắt buộc cho luồng chính)
- [ ] Server Script validate Item Price hoạt động (thử tạo trùng tổ hợp → phải bị chặn)
- [ ] BomOrchestrator chạy đủ 11 phase B0→B8, không phase nào bị bỏ qua âm thầm

### 9.3. Kiểm thử số liệu — **giá trị kỳ vọng đã được sửa**
- [ ] Chạy BOM với W=2400, H=2600, n_canh=2, TransomHeight=600, mau_nhom=WHITE → **GIA_VAT phải bằng 22,717,289đ** (không phải 22,715,028đ của bản gốc — xem mục 10 nếu ra số khác)
- [ ] Dòng `canh_ngang` thành tiền phải ra **702,950** (không phải 702,550)
- [ ] Dòng `canh_dung` thành tiền phải ra **1,191,110** (không phải 1,190,110)
- [ ] Đổi `mau_nhom` → DARK ở 1 chỗ duy nhất (Variable Set/Quotation) → toàn bộ 8 dòng NHOM tự đổi giá sang 118,000, không cần sửa tay dòng nào
- [ ] Đổi `xuat_xu_nhom` → DOMESTIC → giá NHOM chuyển sang 98,000 (nếu tổ hợp có trong Item Price, nếu không → fallback lỗi rõ ràng, không âm thầm trả 0)
- [ ] Đổi tổ hợp glass_thick (thử kính khác 24mm) → Rule `RULE-NEP-GLASSTHICK` chọn đúng nẹp tương ứng
- [ ] `tay_nam` với accessory_finish/material Select → nhập giá trị không hợp lệ phải bị Frappe chặn ngay lúc nhập (không đợi tới lúc tính BOM)
- [ ] Test hiệu năng: chạy BOM cho 20 sản phẩm đồng thời, đo thời gian — xác nhận không có N+1 query (nhờ batch query ở B2.5)

---

<a name="10"></a>
## 10. PHỤ LỤC — BẢNG ĐỐI CHIẾU LỖI ĐÃ SỬA (TRƯỚC / SAU)

| Vị trí | Trước (bản gốc v26/Grok) | Sau (bản chuẩn này) | Nguyên nhân |
|---|---|---|---|
| `lookup_calc_pattern()` | Gọi `FlexibleFormulaEngine.evaluate_single()` từ bên trong 1 hàm đang chạy trong engine | Dispatch table Python thuần, không đụng tới engine | Lỗi kiến trúc tái diễn — đã từng bị phát hiện & sửa 1 lần, Grok tái tạo lại dưới tên hàm khác |
| `canh_ngang` thành tiền | 702,550 | **702,950** | Sai số học (lệch 400) |
| `canh_dung` thành tiền | 1,190,110 | **1,191,110** | Sai số học (lệch 1,000) |
| `VL_NHOM` | 4,894,031 | **4,895,431** | Cộng dồn từ 2 dòng trên |
| `TONG_VL` | 14,061,411 | **14,062,811** | Cộng dồn |
| `GIA_THANH` | 17,801,746 | **17,803,518** | Cộng dồn qua %NC + %OH |
| `GIA_BAN` | 20,650,025 | **20,652,081** | Cộng dồn qua %PROFIT |
| `GIA_VAT` (kết quả cuối) | 22,715,028 | **22,717,289** | Chênh lệch cuối cùng: **+2,261đ** |

**Quy trình đề xuất để tránh lặp lại lỗi này:** mọi lần một bảng ví dụ số được sửa hoặc review lại, phải chạy lại toàn bộ 17 dòng bằng script (Python/Excel có công thức, không gõ tay), rồi mới cập nhật bảng trong tài liệu — không copy số cũ và chỉ sửa các dòng "tưởng là" bị ảnh hưởng.

---

<a name="11"></a>
## 11. (BỔ SUNG) NHỮNG "BẪY" TRIỂN KHAI CẦN TRÁNH & CHEAT-SHEET TÓM TẮT

### 11.1. Bảng "bẫy" triển khai

| # | Bẫy | Vì sao xảy ra | Cách tránh |
|---|---|---|---|
| 1 | Gọi lại engine bên trong 1 hàm mà chính engine đang gọi (`lookup_calc_pattern`) | Nhầm giữa "hàm tiện ích thuần" và "một lượt tính DAG mới" | Chỉ dùng dispatch table Python thuần cho các pattern hữu hạn, đã biết trước (mục 4.3, 6.1) |
| 2 | Tính tuần tự theo cột `sort` thay vì để engine giải DAG | Nhìn có vẻ "chạy từ trên xuống là ổn" với ví dụ cụ thể này | Luôn để engine tự sắp xếp tô-pô — không giả định thứ tự nhập liệu là thứ tự tính đúng (mục 4.2) |
| 3 | Sai số cộng dồn không bị phát hiện (ví dụ: gõ nhầm 702,**5**50 thay vì 702,**9**50) | Số liệu sai ở 1 dòng chi tiết sẽ lan qua `TONG_VL → GIA_THANH → GIA_BAN → GIA_VAT` vì các bước sau đều là % nhân dồn | Luôn tính lại toàn bộ bằng script (Python/Excel công thức) mỗi khi sửa ví dụ, không copy số cũ rồi sửa tay từng dòng "tưởng bị ảnh hưởng" |
| 4 | Query giá/trọng lượng riêng lẻ cho từng dòng BOM (N+1 query) | Viết code lặp `for line in lines: frappe.db.get_value(...)` | Batch query 1 lần cho toàn bộ danh sách item_code/base_item cần, như B2.5 |
| 5 | Lặp lại JSON màu/xuất xứ/độ dày/bề mặt trên từng dòng NHOM | Tưởng mỗi dòng cần khai báo riêng | Khai báo 1 lần ở `AL Variable Set` cấp báo giá, các dòng NHOM tự thừa hưởng qua `resolve_price_attrs()` |
| 6 | Trùng tổ hợp Item Price (2 dòng giá cho cùng 1 tổ hợp màu/xuất xứ) | Không có ràng buộc unique | Server Script `validate` chặn trùng `(item_code, price_list, mau_sac, xuat_xu, do_day, be_mat)` |
| 7 | Dùng biến phẳng đặt tên riêng (`glass_thick_kinh_tren`) thay vì cross-row | Quen cách viết code thủ tục | Luôn dùng đúng 1 cú pháp `items.<slug>.<field>` cho mọi tham chiếu chéo, không ngoại lệ |

### 11.2. Cheat-sheet tóm tắt 1 trang

```
INPUT:  W_mm=2400  H_mm=2600  TransomHeight_mm=600  n_canh=2
        mau_nhom=WHITE  xuat_xu_nhom=IMPORT  do_day_nhom=20  be_mat_nhom=POWDER_COATED

B0-B1:  Chốt version + gom input + hằng số offset/%  vào `inputs`
B2a:    (không có dòng nào cần — bỏ qua)
B2.5:   Batch query 1 lần: trọng lượng riêng, đơn giá (theo composite key màu/xuất xứ...),
        glass_thick=24 & glass_type=LOWE (ghi literal lên dòng kinh_tren/kinh_duoi)
B2b:    Resolve 2 Rule cross-row → nẹp=C3211-20, keo=KEO-TT-01
B3-B4:  Ghép công thức width/height/qty (từ Profile Line) + 3 công thức Formula Set BOM_LINE
B5:     engine.calculate() → DAG tự sắp thứ tự, tính 17 dòng (bảng chi tiết mục 7.3)
B6:     Gom theo cost_bucket → VL_NHOM=4,895,431  VL_KINH=6,330,980
                                VL_VTP=836,400     VL_PK=2,000,000
B7:     Cost Template (14 bước, engine tính theo DAG) → GIA_VAT = 22,717,289đ
B8:     Lưu child table + ConfigSnapshot (để tái lập chính xác về sau)

KẾT QUẢ CUỐI:  GIA_VAT = 22,717,289 đ   (DON_GIA_M2 = 3,309,628 đ/m², chưa VAT)
```

---

<a name="12"></a>
## 12. (TỪ v26_new.md) CÁC KHUYẾN NGHỊ BỔ SUNG TỪ GROK & TRẠNG THÁI XỬ LÝ

Đây là bảng khuyến nghị gốc ở mục 8 của tài liệu `v26_new.md`, giữ lại nguyên vẹn kèm **cột trạng thái đã cập nhật** phản ánh đúng những gì đã thực sự được xử lý qua các lượt review tới bản v27_FULL này (một số khuyến nghị ban đầu tưởng đã xong nhưng thực chất mắc lỗi kiến trúc, đã được sửa lại đúng ở đây).

| # | Khuyến nghị | Trạng thái ở bản `v26_new.md` gốc | Trạng thái THẬT SỰ ở bản v27_FULL này |
|---|---|---|---|
| 1 | Đăng ký `price_lookup`, `glass_lookup` vào data_source_registry | "Đã đề xuất trong phần 5" | Giữ nguyên — đã đăng ký, xem mục 6.2. Không bắt buộc dùng trong luồng chính (B2.5 dùng batch query trực tiếp để tối ưu hiệu năng) |
| 2 | Đăng ký `lookup_calc_pattern` vào BASE_FUNCS | "Đã đề xuất trong phần 5" | **Đã sửa lại đúng** — bản `v26_new.md` gốc triển khai sai (gọi đệ quy `FlexibleFormulaEngine.evaluate_single()` từ bên trong hàm, mục 0.1); ở đây đã thay bằng dispatch table Python thuần (mục 6.1) |
| 3 | Formalize BomOrchestrator phases | "Đã thực hiện (phần 4)" | Giữ nguyên, bổ sung thêm số liệu thật ở từng phase (mục 5) |
| 4 | Thêm giới hạn max panels (configurable) | "Nên thêm trong Phase 1" | Chưa triển khai trong ví dụ CDMQ-2C-TRANSOM này — vẫn là khuyến nghị mở cho các BOM nhiều cánh/nhiều panel hơn |
| 5 | Bổ sung `snapshot_with_trace()` vào ConfigSnapshot | "Nên thêm trong Phase 1" | Vẫn là khuyến nghị mở — B8 (mục 5) hiện mô tả lưu `engine.get_trace()`/`get_dag_structure()` nếu Formula Builder hỗ trợ, nhưng hàm `snapshot_with_trace()` cụ thể chưa được viết ra trong tài liệu này |
| 6 | Document glass_thick injection order | "Đã ghi chú ở B1 và B2.5" | Giữ nguyên, làm rõ thêm bằng bảng `row_literals` có số liệu thật (mục 5, B2.5) |
| 7 | price_attrs_override ưu tiên Variable Set | "Đã áp dụng trong logic resolve" | Giữ nguyên — xem hàm `resolve_price_attrs()` mục 5 (B2.5): kiểm tra `price_attrs_override` trước, mới tới logic mặc định theo `line_type` |
| 8 | Thêm explain mẫu trong tài liệu | "Đã có bảng tính chi tiết" | Mở rộng đáng kể — mục 7.2 giờ có phép thay số từng bước cho 8 loại dòng đại diện, không chỉ bảng kết quả cuối |

> **Bài học đúc kết:** khuyến nghị #2 ở trên là ví dụ điển hình cho thấy "đã đề xuất/đã thực hiện" trong 1 bản tài liệu không đồng nghĩa với "đã đúng" — cần luôn kiểm tra lại phần triển khai cụ thể (code), không chỉ tin vào mô tả trạng thái bằng lời.

---

**Tài liệu này (v27_FULL) là bản chuẩn duy nhất, đầy đủ nhất để triển khai AlumGlass cho sản phẩm CDMQ-2C-TRANSOM — gộp trọn vẹn nội dung `v26_new.md` gốc, toàn bộ cải tiến/sửa lỗi của v27, và phần giải thích cơ chế engine + ví dụ mở rộng từng bước. Mọi bản trước (`v26_new.md`, các bản review trung gian, bản `AlumGlass_v27_CHUAN_TRIEN_KHAI.md` gốc chưa gộp) coi như đã được hợp nhất và thay thế hoàn toàn bởi tài liệu này — không cần tham chiếu ngược lại bất kỳ bản nào trong số đó.**
