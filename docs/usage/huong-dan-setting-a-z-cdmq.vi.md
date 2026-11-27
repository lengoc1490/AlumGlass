# Hướng dẫn setting A–Z — dựng một sản phẩm từ đầu

> **Dành cho:** người cấu hình sản phẩm (BOM Manager) và quản trị kỹ thuật.
> **Ví dụ xuyên suốt:** hai sản phẩm đã có sẵn trong bộ dữ liệu mẫu —
> **CDMQ-2C** (cửa đi 2 cánh + ô kính cố định) và **CDMQ-4C** (cửa đi 4 cánh + 2 ô kính + vách bên).
> **Ngày soạn:** 2026-11-27 · **Phạm vi:** app `alumglass`.
>
> **Mức kiểm chứng:** nội dung viết từ mã + dữ liệu seed trong working tree. Máy soạn tài liệu
> **không có site cài `alumglass`**, nên các con số dưới đây là **mốc chuẩn trong bộ seed** — khi
> chạy trên site của bạn, đối chiếu theo §12. Nếu màn hình khác mô tả, xem
> [../ops/cap-nhat-ma-va-cache.md](../ops/cap-nhat-ma-va-cache.md) trước khi kết luận tài liệu sai.

---

## 0. Đọc trước 60 giây

Một sản phẩm trong AlumGlass dựng qua **9 bước** — mỗi bước là một form riêng, nối với nhau theo đúng
thứ tự dưới đây. Tạo sai thứ tự thì ô chọn sẽ trống hoặc ra cảnh báo.

```
 ① Danh mục slug        →  ② Mã vật tư + giá   →  ③ Thư viện biến
        ↓                        ↓                        ↓
 ④ Bộ biến  ────────►  ⑤ Bộ BOM  ────────►  ⑥ Bộ phụ kiện
                              ↓
                    ⑦ Mẫu tính giá
                              ↓
                    ⑧ Hồ sơ biến (lọc gợi ý)
                              ↓
                    ⑨ Sản phẩm (AL BOM)  →  tính giá
```

**Sáu câu để nhớ vai** (bước ①–② là dữ liệu nền, không phải form cấu hình sản phẩm):

| Mảnh | Nó trả lời câu hỏi |
|---|---|
| **Thư viện biến** | "Có những biến nào, kiểu gì, ai nhập?" |
| **Bộ biến** | "Sản phẩm này hỏi người báo giá những gì, mặc định bao nhiêu?" |
| **Bộ BOM / Bộ phụ kiện** | "Cần vật tư gì, tính chiều dài/diện tích/số lượng theo công thức nào?" |
| **Mẫu tính giá** | "Từ tiền vật tư, cộng nhân công / overhead / lợi nhuận / VAT ra giá bán thế nào?" |
| **Hồ sơ biến** | "Trong ô công thức, gợi ý biến nào (thu hẹp danh sách)?" |
| **Sản phẩm** | "Gói cuối cùng: trỏ tới bộ BOM + bộ phụ kiện + mẫu tính giá nào." |

**Quyền cần có:**

| Phần việc | Nhân vật (role) |
|---|---|
| Slug, Thư viện biến, Bộ biến, Bộ BOM, Bộ phụ kiện, Mẫu tính giá, Sản phẩm | **AL BOM Manager** — đọc + sửa |
| Hồ sơ biến, Trường công thức, Cách tính | **AL Technical Admin** — đọc + sửa (AL BOM Manager chỉ đọc) |
| Hằng số toàn cục (`Formula Global Variable`: VAT, overhead) | **AL BOM Manager** — đọc + sửa |
| Tất cả | **System Manager** làm được mọi việc |

Thiếu quyền thì nút **Lưu** bị từ chối kèm câu "Bạn không có quyền…" — xin cấp đúng role ở bảng trên,
cấp `AL Technical Admin` cho người chỉ sửa BOM sẽ **không** mở được các form đó.

---

## 1. Danh mục slug — đặt tên cho từng dòng vật tư

**Mở:** tìm kiếm `AL Slug Library`.

Slug là **mã nội bộ** của một dòng trong bộ BOM (ví dụ `khung_ngang_tren`). Dòng BOM bắt buộc phải
trỏ tới một slug đã khai — nếu chưa khai, ô chọn trống.

Bộ dữ liệu mẫu dùng hai nhóm slug:

| Nhóm | Dùng cho | Slug mẫu |
|---|---|---|
| **CDMQ-2C** | cửa 2 cánh + 1 ô kính | `khung_ngang_tren`, `khung_ngang_duoi`, `khung_dung`, `do_ngang`, `canh_ngang`, `canh_dung`, `kinh_tren`, `kinh_duoi`, `nep_kinh_tren`, `nep_kinh_duoi`, `keo_tren`, `keo_duoi`, `gioang`, `vit` |
| **Phụ kiện** (dùng ở §6) | tay nắm, khóa, bản lề | `tay_nam`, `khoa`, `ban_le` |
| **CDMQ-4C** | 4 cánh + 2 ô kính + vách bên | thêm `khung_dung_trai/phai`, `do_ngang_tren/duoi`, `canh_dung_c1…c4`, `canh_ngang_c1…c4`, `kinh_fixed_top/bottom`, `kinh_canh`, `kinh_sidelite`, `nep_kinh_canh/sidelite`, `keo_canh/sidelite` |

Mỗi slug có: **Slug Code** (mã), **Label** (tên người đọc), **Material Category** (nhóm vật tư:
`NHOM` / `KINH` / `VTP` / `PK`), **Group Tag** — danh sách chọn (`KHUNG` / `CANH` / `GLASS` / `NEP` / `KEO` /
`GIOANG` / `VIT` / `PK`).

> **Làm gì khi thêm sản phẩm mới:** thêm slug **trước**, rồi mới mở Bộ BOM. Thêm slug sau cũng được,
> nhưng dòng BOM đã lưu sẽ hiện cảnh báo slug không còn.

---

## 2. Mã vật tư (Item) và bảng giá

Đây là dữ liệu ERPNext chuẩn, không phải form riêng của AlumGlass.

Với mỗi mã vật tư cần: **Item** (mã, tên, nhóm hàng, đơn vị tính, trọng lượng riêng nếu tính theo kg)
và **Item Price** (bảng giá `Standard Selling`).

Bộ dữ liệu mẫu (giá bán, VND):

| Mã | Tên | ĐVT | Đơn giá |
|---|---|---|---|
| `NHOM-XINGFA` | Nhôm Xingfa (đại diện) — **mã sản phẩm bán** của cả bộ (dùng ở §9) | Kg | 113.000 |
| `XF55-KB-20` | Khung bao H55 2.0mm | Kg | 113.000 |
| `XF55-CANH-20` | Cánh mở quay 2.0mm | Kg | 113.000 |
| `C3211-20` / `C3210-20` / `C3209-20` | Nẹp kính >16 / 11–16 / ≤10,38mm | Kg | 113.000 |
| `KINH-LOWE-24` | Kính Low-E 24mm | m² | 1.150.000 |
| `KINH-DON-8` | Kính dán 8mm | m² | 550.000 |
| `KEO-TT-01` / `KEO-TT-02` | Keo trung tính / keo thường | m | 45.000 / 30.000 |
| `GIO-EPDM-55` | Gioăng EPDM 55 | m | 1.250 |
| `VIT-TK-35X16` | Vít tự khoan 3,5×16 | cái | 850 |
| `KL-MZS20` | Tay nắm Kinlong | cái | 210.000 |
| `KL-KHOA-01` | Khóa Kinlong | cái | 350.000 |
| `KL-T-MJ06` | Bản lề cối MJ06 | cái | 180.000 |

**Mẹo kiểm nhanh:** mở dialog **📐 Tham số BOM** của một dòng báo giá → bấm **🖥️ Preview tính giá** →
xem cột **thành tiền** của từng dòng. Dòng nào ra 0 mà vẫn có số lượng thì gần như chắc chắn mã vật tư
**chưa có Item Price** ở bảng giá đang dùng (hoặc dòng kính chưa có *Kính mặc định*).

---

## 3. Thư viện biến — nơi DUY NHẤT khai biến

**Mở:** `AL Variable Library`.

> 🔴 Trước 2026-11-27 có màn `AL Variable Settings` cho việc này. **Màn đó đã bị xoá hẳn** — không
> còn DocType, không còn bảng. Mọi biến khai ở **Thư viện biến**.

### 3.1 Hai ô quyết định — đừng lẫn vai của chúng

| Ô trên form | Quyết định điều gì |
|---|---|
| **Dùng ở** (bắt buộc chọn) | Biến hiện ở **đâu**: trong dialog Tham số BOM · gắn theo từng dòng BOM · hay là biến toàn đơn |
| **System Variable?** (ô đánh dấu) | Máy có **tự đi lấy giá trị** từ bản ghi nguồn hay không |

**Dùng ở** có ba lựa chọn:

| Dùng ở | Nghĩa | Ví dụ trong bộ mẫu |
|---|---|---|
| **Người dùng nhập** | Người báo giá điền khi mở dialog Tham số BOM | `W_mm`, `H_mm`, `n_panel`, `aluminum_color` |
| **Từng dòng** | Máy tự inject cho mỗi dòng BOM (không ai nhập tay) | `unit_price`, `weight_per_unit`, `glass_thick`, `calc_pattern` |
| **Toàn đơn** | Biến dùng chung cả đơn — **hằng số** hoặc **biến hệ thống** | `VAT_RATE` (hằng số), `OFFSET_FRAME` (hệ thống) |

> 🔴 **"Toàn đơn" ⛔ KHÔNG tự biến thành biến hệ thống.** Muốn máy tự lấy giá trị (ví dụ khe hở khung
> lấy từ hệ nhôm) thì phải tích ô **System Variable?** — xem §3.5. Thiếu ô đó, biến chỉ là biến
> thường: máy coi như người dùng nhập, không đi lấy giá trị, và **không có cảnh báo nào** ⇒ giá sai
> âm thầm.

### 3.2 Nhóm hiển thị — MỘT ô duy nhất

Mỗi biến có đúng **một** ô **Nhóm hiển thị** (danh sách chọn): *Kích thước · Cấu hình · Màu sắc ·
Xuất xứ · Kỹ thuật · Thi công · Thông số nhập · System · Row Literals*.

**Nhóm chỉ là cách gom để dễ tìm** trong danh sách gợi ý và trong ô công thức — ⛔ đổi cách tính,
⛔ đổi giá trị. Chọn nhóm nào gần nghĩa nhất; không chắc thì **để trống**, máy tự xếp theo `Dùng ở`
(*Người dùng nhập* → **Thông số nhập**, còn lại → **Cấu hình**).

> 🔴 Trước 2026-11-27 có **hai** ô cùng nghĩa (`Category` và `Nhóm hiển thị`) — nay gộp còn **một**.
> **Không còn ô `Category`** để tìm; dữ liệu cũ đã được tự chuyển sang ô này nên bạn không mất nhóm.
>
> `Row Literals` là nhóm do máy đặt cho biến theo dòng (`Dùng ở` = *Từng dòng*) — ô nhóm **tự ẩn**
> trong trường hợp đó, ⛔ chọn tay.

### 3.3 Kiểu dữ liệu — và ô giá trị hiện tương ứng

Khai ô **Type** thế nào thì ô giá trị ở bộ biến hiện đúng kiểu đó:

| Type | Ô giá trị hiện thành | Cần khai thêm |
|---|---|---|
| **Select** | Danh sách chọn | **Select Options** — mỗi dòng một lựa chọn |
| **Link** | Ô chọn bản ghi | **Link Doctype** — doctype đích |
| **Float / Int / Currency / Percent** | Ô nhập số | — |
| **Check** | Ô đánh dấu | — |
| **Data** | Ô nhập chữ | — |

> ⚠️ Khai **Select mà bỏ trống Select Options**, hoặc **Link mà bỏ trống Link Doctype** ⇒ ô giá trị
> **giữ ô chữ** và hiện câu giải thích ngay dưới ô. Đây là chủ ý: thà nhập chữ còn hơn một ô chọn
> rỗng bấm không được. Khai đủ rồi mở lại bộ biến là ô tự đổi kiểu.

### 3.4 Biến người dùng nhập của CDMQ-2C / CDMQ-4C

| Biến | Nhãn | Kiểu | Mặc định 2C | Mặc định 4C |
|---|---|---|---|---|
| `W_mm` | Chiều rộng (mm) | Float | 2400 | 3600 |
| `H_mm` | Chiều cao (mm) | Float | 2600 | 3200 |
| `TransomHeight_mm` | Cao ô kính cố định (mm) | Float | 600 | — (2C dùng) |
| `TransomHeightTop` | Cao ô kính trên (mm) | Float | — | 600 |
| `TransomHeightBottom` | Cao ô kính dưới (mm) | Float | — | 400 |
| `SideLiteWidth` | Rộng vách kính (mm) | Float | — | 800 |
| `SideLiteHeight` | Cao vách kính (mm) | Float | — | 2800 |
| `n_panel` | Số cánh | Int | 2 | 4 |
| `aluminum_color` | Màu nhôm | Link → `AL Color Standard` | WHITE | DARK |
| `aluminum_origin` | Xuất xứ nhôm | Select `IMPORT` / `DOMESTIC` | IMPORT | IMPORT |
| `aluminum_thickness` | Độ dày nhôm (micron) | Float | 20 | 20 |
| `aluminum_surface` | Bề mặt hoàn thiện | Select `POWDER_COATED` / `ANODIZED` / `WOOD_GRAIN` | POWDER_COATED | POWDER_COATED |
| `installation_height_m` | Chiều cao lắp đặt (m) | Float | 3 | 15 |
| `glass_master` | Loại kính | Link → `AL Glass Master` | (trống) | KINH-LOWE-24 |
| `accessory_set` | Bộ phụ kiện | Link → `AL Accessory Set` | (trống) | ACC-CDMQ-4C |

### 3.5 Biến hệ thống — tích "System Variable?" rồi khai nguồn

Biến hệ thống **không ai nhập tay**: máy đọc từ bản ghi nguồn. Làm đúng 3 bước, **theo thứ tự**:

1. Tích ô **System Variable?** — 🔴 đây là công tắc quyết định máy tự đi lấy giá trị. **Thiếu ô này,
   biến chỉ là biến thường và giá sẽ sai mà không có cảnh báo.**
2. Chọn **Source Doctype** (bảng nguồn), rồi điền **Source Field** (tên cột trong bảng đó).
   Form **chặn khi đã chọn Source Doctype mà để trống Source Field**.
   · **Biến hằng số** (ví dụ phụ phí cố định 2%): tích `System Variable?`, **để trống cả hai ô nguồn**
     và điền **Default Value** — máy dùng đúng giá trị đó.
3. Chọn **Dùng ở** = **Toàn đơn** nếu biến dùng chung cả đơn.

Khai nguồn nhưng **không tìm ra giá trị** (bản ghi nguồn trống, hoặc bộ BOM chưa gắn hệ nhôm/loại sản
phẩm) ⇒ khi tính giá có **cảnh báo "Thiếu giá trị cho biến …"**, nêu đúng tên biến.

> 🔴 **Ba hằng số `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` có HAI bản.** Bản đang có hiệu lực là
> **`Formula Global Variable`** (gõ tên này vào ô tìm kiếm; quyền **AL BOM Manager**).
> Dòng cùng tên trong Thư viện biến chỉ là **dự phòng khi chưa có hằng số** — **sửa ô Default Value ở
> Thư viện biến sẽ KHÔNG đổi giá.** Muốn đổi VAT/overhead: sửa ở `Formula Global Variable`.

| Biến | Lấy từ | Giá trị theo bộ mẫu |
|---|---|---|
| `OFFSET_FRAME` | `AL Profile System` → `offset_frame` | 48 (hệ XINGFA 55) |
| `OFFSET_GLASS` | `AL Profile System` → `offset_glass` | 90 |
| `OFFSET_FIXED` | `AL Profile System` → `offset_fixed` | 50 |
| `OFFSET_DO_NGANG` | `AL Profile System` → `offset_crossbar` | 48 |
| `NC_SX_PCT` | `AL Product Type` → `nc_pct` | 8 (%) |
| `NC_LD_PCT` | `AL Product Type` → `nc_ld_rate` | 12 (%) |
| `PROFIT_MARGIN` | `AL Product Type` → `profit_margin` | 16 (%) |
| `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` | hằng số (`Formula Global Variable`) | 10 / 3 / 3 (%) |

> **Nhập phần trăm kiểu gì cũng được** (8 hay 0.08 đều thành 8%) **với điều kiện** máy nhận ra đó là
> biến phần trăm: tên kết thúc bằng `_PCT` / `_RATE` / `_MARGIN`, **hoặc** ô **Type** khai là *Percent*.
> Thiếu cả hai ⇒ máy không chia 100 và giá **sai 100 lần**. Đặt tên `phu_phi` mà không khai Type = Percent
> là đúng cái bẫy này; đặt `phu_phi_PCT` hoặc khai Type là xong.

---

## 4. Bộ biến — sản phẩm này hỏi những gì

**Mở:** `AL Variable Set` → `VS-CDMQ` (2 cánh) hoặc `VS-CDMQ-4C` (4 cánh).

Bộ biến là **danh sách chọn từ Thư viện biến**: mỗi dòng chọn một biến, đặt **giá trị mặc định**, có
**bắt buộc** hay không, và **thứ tự hiện** trong dialog.

### 4.1 `VS-CDMQ` — 11 dòng (bản 2 cánh)

| # | Biến | Mặc định | Bắt buộc |
|---|---|---|---|
| 10 | `W_mm` | 2400 | ✔ |
| 20 | `H_mm` | 2600 | ✔ |
| 30 | `TransomHeight_mm` | 600 | |
| 40 | `n_panel` | 2 | ✔ |
| 50 | `aluminum_color` | WHITE | ✔ |
| 60 | `aluminum_origin` | IMPORT | ✔ |
| 70 | `aluminum_thickness` | 20 | |
| 80 | `aluminum_surface` | POWDER_COATED | |
| 90 | `glass_master` | (trống) | |
| 100 | `accessory_set` | (trống) | |
| 110 | `installation_height_m` | 3 | |

### 4.2 `VS-CDMQ-4C` — 14 dòng (bản 4 cánh)

**14 dòng = 11 dòng của bản 2 cánh, BỎ `TransomHeight_mm`, THÊM 4 biến** `TransomHeightTop` (600),
`TransomHeightBottom` (400), `SideLiteWidth` (800), `SideLiteHeight` (2800). Ngoài ra khác giá trị mặc
định: `n_panel` = 4 · `aluminum_color` = DARK · `installation_height_m` = 15 ·
`glass_master` = KINH-LOWE-24 · `accessory_set` = ACC-CDMQ-4C.

### 4.3 Làm theo từng bước

1. **New** → **Set Code** (vd `VS-MOI-01`), **Set Name**, **Product Type** (`DOOR`).
2. Bảng **Variables** → **Add Row** → chọn **Variable** (biến).
3. Ô **Default Value (override)** (giá trị) tự đổi kiểu theo biến vừa chọn:
   Select → danh sách · Link → chọn bản ghi · Float/Int → ô số.
4. Điền **Default Value** (để trống ⇒ dialog báo giá dùng giá trị mặc định của Thư viện biến).
5. Đặt **Sort Order** để dialog hỏi theo ý bạn; đánh **Required?** cho biến không được bỏ trống.
6. **Lưu**.

> **Lỗi hay gặp:** chọn biến rồi mà ô giá trị vẫn là ô chữ ⇒ biến đó khai thiếu *Select Options* hoặc
> *Link Doctype* ở Thư viện biến. Câu giải thích hiện ngay dưới ô.

---

## 5. Bộ BOM — trái tim của sản phẩm

**Mở:** `AL Bom Set` → `BS-CDMQ-2C` (14 dòng) / `BS-CDMQ-4C` (22 dòng).

Mỗi dòng = **một loại vật tư**, gồm: slug, cách chọn mã, **công thức chiều rộng**, **công thức chiều
cao**, **công thức số lượng**, **cách tính** (kg / m² / m / đếm), **nhóm chi phí**, **giá lấy ở đâu**.

### 5.1 Ô trong một dòng

| Ô (nhãn trên form) | Ý nghĩa | Ví dụ (`khung_dung`) |
|---|---|---|
| **Slug** | Dòng này là gì (khai ở §1) | `khung_dung` |
| **Material Category** (nhóm vật tư) | Tự lấy từ slug | `NHOM` |
| **Item Selection Mode** (cách chọn mã) | `Fixed` = mã cố định · `Rule` = máy chọn theo quy tắc · `Formula` = mã do công thức trả về | `Fixed` |
| **Item Code** (mã vật tư) | Để trống khi Cách chọn = Rule | `XF55-KB-20` |
| **Width Formula (FB syntax)** (công thức rộng) | Tính bằng mm | `H_mm` |
| **Height Formula (FB syntax)** (công thức cao) | Tính bằng mm | (trống) |
| **Qty Formula (FB syntax)** (số lượng) | Công thức hoặc số | `2` |
| **Calc Pattern** (cách tính) | Mã cách tính (xem §5.3) | `LENGTH_TO_WEIGHT` |
| **Cost Bucket** (nhóm chi phí) | Đổ vào nhóm nào của mẫu tính giá | `VL_NHOM` |
| **Price Type** (loại giá) | `Item Price` = theo bảng giá · `Fixed` = không cần giá · `Rule` | `Item Price` |
| **Price Base Item** (mã tra giá) | Mã dùng để tra giá khi mã hàng đổi theo quy tắc | `NHOM-XINGFA` |

### 5.2 Công thức — dùng được 3 thứ

1. **Biến của bộ biến:** `W_mm`, `H_mm`, `n_panel`, `OFFSET_FRAME`,…
2. **Dòng khác trong cùng bộ:** `items.<slug>.width`, `items.<slug>.height`,
   `items.<slug>.qty` — ví dụ nẹp kính dài đúng bằng chu vi tấm kính:
   `2*(items.kinh_tren.width + items.kinh_tren.height)`
3. **Hàm an toàn:** `safe_div(a, b, 0)` (chia, mẫu 0 ⇒ trả 0), `lookup_rule('RULE-…', giá_trị)`.

### 5.3 Cách tính — 6 cái dùng nhiều nhất

| Mã | Nghĩa | Dùng cho dòng nào |
|---|---|---|
| `LENGTH_TO_WEIGHT` | (rộng mm / 1000) × trọng lượng riêng | nhôm, nẹp |
| `AREA_M2` | (rộng/1000) × (cao/1000) → m² | kính |
| `LENGTH_M` | rộng mm / 1000 → mét | keo, gioăng |
| `COUNT` | đếm số cái (dùng ô Số lượng) | vít, phụ kiện rời |
| `LENGTH_TO_PIECES` | mét dài / chiều dài mỗi đoạn | cắt thanh |
| `COUNT_PER_LENGTH` | mét dài / khoảng cách | vít theo mét |

> ⚠️ Trên ô chọn bạn sẽ thấy **thêm** `AREA` (tên đầy đủ "Diện tích m2 (legacy)") và `LENGTH_ONLY`
> ("Mét dài (legacy)") — hai mã này chỉ để giữ dữ liệu cũ, công thức y hệt `AREA_M2` / `LENGTH_M`.
> Bản mới dùng **`AREA_M2` / `LENGTH_M`**. (Dữ liệu mẫu dùng tên cũ cho đúng với bộ seed.)

> Đổi công thức của một cách tính: mở **`AL Quantity Calc Method`**. Ô **"Công thức tính"** là nguồn
> chính (cú pháp Formula Builder, ví dụ `(w/1000)*tlr`); ô **"Python Lambda (nâng cao)"** chỉ còn là
> đường lùi cho dữ liệu cũ.
>
> Để trống ô **Công thức tính** thì mở cách tính đó sẽ thấy **dải cam ngay trên form** nhắc chuyển
> công thức sang ô đó — làm đúng theo dải cam là xong (⛔ không cần đọc nhật ký kỹ thuật).

### 5.4 Hai dòng đáng chú ý

**Dòng Rule — chọn mã theo quy tắc.** Bản 2 cánh có `nep_kinh_tren`: mã nẹp phụ thuộc **độ dày kính**:

```
Quy tắc:      RULE-NEP-GLASSTHICK   (khoảng giá trị → mã hàng)
Đầu vào:      items.kinh_tren.glass_thick
Kết quả:      ≤ 10,38mm → C3209-20 · 10,39–16mm → C3210-20 · > 16mm → C3211-20
```

Dòng `keo_*` tương tự nhưng tra theo **loại kính** (`RULE-KEO-GLASSTYPE`: LOWE → keo trung tính,
DON → keo thường).

**Dòng kính — có nguồn độ dày.** Dòng `kinh_tren` gắn **Default Glass Master** (kính mặc định) =
`KINH-LOWE-24` và **CTX Inject Prefix** (tiền tố inject) = `kinh_tren`: nhờ vậy các dòng khác đọc
được `items.kinh_tren.glass_thick` (= 24).

### 5.5 Làm theo từng bước

1. **New** → **Set Code**, **Set Name**, **Product Type**, **Profile System** (hệ nhôm — `XINGFA_55`),
   **Variable Set** (§4), **Default Accessory Set** (§6).
2. Bảng **Items** → **Add Row**: chọn **Slug** → **Material Category** tự điền.
3. **Item Selection Mode** = `Fixed` ⇒ chọn **Item Code**; = `Rule` ⇒ chọn **Quy tắc chọn mã**, rồi:
   · quy tắc tra theo dữ liệu **của một dòng khác** ⇒ bấm **Chọn dòng lấy dữ liệu** và chọn dòng nguồn
     (ví dụ dòng kính). Đây là đường chính — ô **Rule Input Expression** khi đó **bị bỏ qua**;
   · quy tắc không gắn dòng nào ⇒ mới điền **Rule Input Expression** (`items.<slug>.<field>`).
4. Điền **Width / Height / Qty Formula**.
5. Chọn **Calc Pattern** đúng đơn vị (nhôm/kg, kính/m², keo/m, vít/cái).
6. **Lưu** — hệ thống kiểm công thức và **cảnh báo** nếu dùng biến mà engine không có.

> **Cảnh báo công thức** *"Công thức dùng biến theo dòng không đúng dạng"*: viết `unit_price` trực tiếp
> trong công thức của **bộ BOM** sẽ không có giá trị (biến theo dòng chỉ tồn tại bên trong từng dòng).
> Dùng `items.<slug>.unit_price`.

---

## 6. Bộ phụ kiện — tay nắm, khóa, bản lề

**Mở:** `AL Accessory Set` → `ACC-CDMQ-2C` / `ACC-CDMQ-4C`.

| Dòng | Mã | SL 2C | SL 4C | Ghi chú |
|---|---|---|---|---|
| `tay_nam` | `KL-MZS20` | 1 | 4 | 4C: mỗi cánh một tay nắm |
| `khoa` | `KL-KHOA-01` | 1 | 1 | |
| `ban_le` | `KL-T-MJ06` | công thức | công thức | `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel` |

### 6.1 Làm theo từng bước

1. **New** → **Set Code** (vd `ACC-MOI-01`), **Set Name**, **Product Type** (`DOOR`).
2. **Variable Set** — 🔴 chọn **đúng bộ biến của sản phẩm** (`VS-CDMQ` / `VS-CDMQ-4C`). Công thức số
   lượng ở đây dùng `H_mm`, `n_panel` — hai biến này chỉ có khi bộ biến đã gắn.
3. Bảng **Items** → **Add Row**: chọn **Slug** (`tay_nam`, `khoa`, `ban_le` — xem §1).
4. Chọn **Item Code**, điền **Qty** (số cố định) **hoặc** **Qty Formula** (công thức). Đã có công thức
   thì ô số lượng để trống.
5. **Lưu**.

**Vì sao bản lề dùng công thức:** số bản lề phụ thuộc chiều cao cửa.

```
RULE-BANLE-QTY:   0–2100mm → 2/cánh · 2101–2700mm → 4/cánh · 2701mm trở lên → 4/cánh
2C: H_mm 2600 → 4 × 2 cánh = 8 bản lề  → VL_PK = 1.440.000 (bản lề) + 210.000 + 350.000 = 2.000.000
4C: H_mm 3200 → 4 × 4 cánh = 16 bản lề
```

> 🔴 **Mốc nhạy cảm:** bậc 2101–2700 phải là **4**, không phải 3. Đổi thành 3 là giá 2 cánh lệch
> khoảng 581.540 đồng — và lệch đúng mốc kiểm ở §12.

---

## 7. Mẫu tính giá — từ vật tư ra giá bán

**Mở:** `AL Cost Template` → `CT-01-STANDARD` (14 dòng, dùng chung cho cả hai sản phẩm).

Mỗi dòng có: **Line Code** (mã dòng), **Calc Formula** (công thức), **Cost Bucket** (nhóm chi phí),
**Is Subtotal?** (đánh dấu dòng tổng).

| Line Code | Calc Formula | Cost Bucket |
|---|---|---|
| `TONG_VL` | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` | Tổng vật liệu |
| `TONG_M2` | `(W_mm/1000)*(H_mm/1000)` | — (chỉ để tính đơn giá m²) |
| `NC_SX` | `NC_SX_PCT * TONG_VL` | Nhân công SX |
| `NC_LD` | `NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` | Nhân công LĐ |
| `TONG_NC` | `NC_SX + NC_LD` | Tổng nhân công |
| `OH_VC` | `OH_VC_PCT * TONG_VL` | Overhead VC |
| `OH_QLY` | `OH_QLY_PCT * (TONG_VL + TONG_NC)` | Overhead QL |
| `TONG_OH` | `OH_VC + OH_QLY` | Tổng overhead |
| `GIA_THANH` | `TONG_VL + TONG_NC + TONG_OH` | Giá thành |
| `PROFIT` | `PROFIT_MARGIN * GIA_THANH` | — |
| `GIA_BAN` | `GIA_THANH + PROFIT` | Giá bán chưa VAT |
| `DON_GIA_M2` | `safe_div(GIA_BAN, TONG_M2, 0)` | — |
| `VAT` | `VAT_RATE * GIA_BAN` | — |
| `GIA_VAT` | `GIA_BAN + VAT` | Giá bán có VAT |

**Hệ số nhân công theo độ cao** (`RULE-HEIGHT-MULT`): 0–10 m → 1,0 · 10,1–30 m → 1,2 · 30,1–60 m → 1,5 · trên 60 m → 2,0.

Nhờ vậy 4C lắp ở **15 m** chịu **×1,2** cho nhân công lắp đặt, còn 2C lắp ở **3 m** là ×1,0.

---

## 8. Hồ sơ biến — thu hẹp danh sách gợi ý trong ô công thức

**Mở:** `AL Variable Profile`. Bộ dữ liệu mẫu có **3 hồ sơ mặc định**:

| Hồ sơ | Áp cho |
|---|---|
| `P_BOM_DEFAULT` | Bộ BOM / Bộ phụ kiện |
| `P_COST_TEMPLATE_DEFAULT` | Mẫu tính giá |
| `P_ACCESSORY_DEFAULT` | Bộ phụ kiện |

Hồ sơ **chỉ lọc gợi ý** — ⛔ không đổi giá trị tính, ⛔ không chặn công thức đã viết.

1. Bảng **Rules** → **Add Row** → chọn **Hành động** (`Include` / `Exclude`) và **Nguồn biến**.
   ⚠️ Ô **Nguồn biến** hiện **mã tiếng Anh thô** — bảng dịch các giá trị hay dùng:

   | Giá trị trên ô | Nghĩa |
   |---|---|
   | `variable_library_user` | Biến người dùng nhập / biến cấu hình (Thư viện biến) |
   | `variable_library_system` | Biến hệ thống (`System Variable?` = tích) |
   | `variable_set` | Biến của **bộ biến** đang gắn |
   | `row_literal` | Biến theo từng dòng BOM |
   | `common_var` | Biến dùng chung cả đơn |

   *(Đây là nợ trải nghiệm của sản phẩm: ô này chưa có nhãn tiếng Việt. Bảng trên giúp bạn chọn đúng
   trong lúc chờ sửa.)*
2. Bật **Hồ sơ mặc định** trên đúng một hồ sơ: hồ sơ đó áp cho mọi chứng từ **chưa gán hồ sơ riêng**
   (chỉ áp cho doctype có ô "Variable Profile").
3. Bấm **Xem trước** để thấy đúng danh sách biến mà form sẽ nhận, kèm nguồn từng biến.
   Ô **Doctype xem trước** gợi ý sẵn loại chứng từ cần xem.

> Sản phẩm chưa gán hồ sơ ⇒ ô công thức hiện **toàn bộ** biến. Trang *Cấu hình sản phẩm* hiện khối
> "Hồ sơ biến" ở trạng thái **Chưa gắn** (xám) — bình thường, không phải lỗi.

---

## 9. Sản phẩm — gói cuối

**Mở:** `AL BOM` → `BOM-CDMQ-2C` / `BOM-CDMQ-4C`.

| Ô (nhãn trên form) | 2C | 4C |
|---|---|---|
| **BOM Code** | `BOM-CDMQ-2C` | `BOM-CDMQ-4C` |
| **BOM Name** | Cửa đi 2 cánh mở quay + ô kính | Cửa đi 4 cánh mở quay + 2 ô kính + vách kính |
| **Product Type** | DOOR | DOOR |
| **Brand** | XINGFA | XINGFA |
| **Mã sản phẩm** (Representative Item — Link tới **Item** bán ra, ⛔ không phải mã BOM) | `NHOM-XINGFA` | `NHOM-XINGFA` |
| **BOM Set** | `BS-CDMQ-2C` | `BS-CDMQ-4C` |
| **Default Cost Template** | `CT-01-STANDARD` | `CT-01-STANDARD` |

Sản phẩm mới: **New** → điền các ô trên → **Lưu** → tạo **Phiên bản giá** (`AL BOM Version`,
trạng thái *Published*) trước khi báo giá.

Sau khi lưu, bấm **"Cấu hình sản phẩm"** để xem trang tổng hợp (§10).

---

## 10. Kiểm cấu hình bằng trang "Cấu hình sản phẩm"

**Mở:** trên form `AL BOM` → nút **"Cấu hình sản phẩm"**. Không thấy nút (bản cũ) thì gõ
`al-product-config` vào ô tìm kiếm.

Trang **chỉ đọc**, gom 7 khối. Mỗi khối có một trạng thái và một nút đúng việc:

| Nhãn trên khối | Màu | Nghĩa | Nút |
|---|---|---|---|
| **Đọc được** | xanh lá | có dữ liệu | **Mở** form tương ứng |
| **Chưa gắn** | xám | sản phẩm chưa nối tới mảnh đó — bình thường, chưa phải lỗi | **Mở sản phẩm để gắn** |
| **Đang ngừng dùng** | vàng | đọc đủ cấu hình, nhưng sản phẩm đã tắt — báo giá mới nên cân nhắc | **Mở** |
| **Không đọc được** | cam | lỗi đọc, hoặc bản ghi đã bị xoá | **Tải lại** |

Khối lỗi **không** làm hỏng các khối khác. Nếu một khối báo **"Chưa xác định được {tên khối} vì không
đọc được sản phẩm"** thì nguyên nhân nằm ở khối **Sản phẩm**, không phải ở khối đó.

---

## 11. Tính giá và đọc kết quả

1. Mở **Báo giá** (Quotation) → **Add Row** → chọn **mã hàng (Item)** như mọi dòng báo giá. (Dòng hàng
   ⛔ không chọn mã BOM — BOM chọn ở bước sau, bên trong cửa sổ tham số.)
2. Bấm vào dòng để mở rộng → bấm **📐 Tham số BOM** (cũng có nút 📐 nhỏ ở góc phải ô mã hàng; bấm đúp
   vào dòng cũng mở).
3. Trong cửa sổ, chọn **BOM** = `BOM-CDMQ-2C` / `BOM-CDMQ-4C` và **BOM Version**. Cửa sổ hiện đúng danh
   sách biến của bộ biến (§4) — điền kích thước / số cánh / màu / cao lắp đặt…
4. Ngừng sửa vài giây — hệ thống **tự tính lại** (dòng nhắc vàng "Tham số vừa đổi — đang tự động tính
   lại giá…").
5. Đọc kết quả: **VL_NHOM · VL_KINH · VL_VTP · VL_PK** (vật tư) → **TONG_VL** → nhân công → overhead →
   **GIA_THANH** → **GIA_BAN** → **GIA_VAT**. Muốn xem rộng: bấm **🖥️ Preview tính giá**.
6. Bấm **Áp dụng vào dòng** để đưa tham số + kết quả xuống dòng hàng (báo giá **vẫn chưa lưu** —
   bấm **Lưu** trên báo giá mới ghi lại).

> Muốn tính **cả báo giá một lượt** sau khi các dòng đã có tham số: menu **AlumGlass → Tính giá**
> (chỉ hiện khi báo giá còn nháp). Nút này **không mở** cửa sổ tham số — nó tính lại mọi dòng đã có
> tham số. Xem trước không ghi gì: **AlumGlass → Preview giá**.

Nếu có cảnh báo vàng, đọc kỹ: nó luôn nói **biến nào** và **cần làm gì** (thường là khai nguồn dữ
liệu cho biến, rồi tính lại).

---

## 12. Hai mốc kiểm để biết cấu hình còn đúng

Sau khi cài/dời dữ liệu, tính thử hai sản phẩm mẫu với đúng tham số dưới đây. **Giá phải khớp**
(dung sai dưới 1.000 đồng — do làm tròn):

| Sản phẩm | Tham số tính | **GIA_VAT phải bằng** |
|---|---|---|
| **CDMQ-2C** | W 2400 · H 2600 · 2 cánh · ô kính 600 · WHITE · IMPORT · dày 20 · POWDER_COATED | **22.717.289** |
| **CDMQ-4C** | W 3600 · H 3200 · 4 cánh · ô trên 600 · ô dưới 400 · vách 800×2800 · DARK · IMPORT · dày 20 · POWDER_COATED · cao lắp 15 m | **47.430.808** |

Lệch nhiều thì soi theo thứ tự: **VL_PK** (bản lề — §6) → **VL_NHOM** (trọng lượng riêng của mã nhôm) →
**VL_KINH** (diện tích kính, hệ số phụ kiện) → **% nhân công / overhead / VAT** (§3.5).

---

## 13. Bảng so sánh nhanh 2C ↔ 4C

| | CDMQ-2C | CDMQ-4C |
|---|---|---|
| Kích thước mặc định | 2400×2600 | 3600×3200 |
| Số cánh | 2 | 4 |
| Ô kính | 1 ô trên | 1 ô trên + 1 ô dưới |
| Vách bên | — | 800×2800 |
| Màu nhôm | WHITE (×1,00) | DARK (×1,08) |
| Cao lắp đặt | 3 m (×1,0) | 15 m (×1,2) |
| Số dòng BOM | 14 | 22 |
| Bộ biến | `VS-CDMQ` (11) | `VS-CDMQ-4C` (14) |
| Bộ phụ kiện | `ACC-CDMQ-2C` | `ACC-CDMQ-4C` |
| Mốc GIA_VAT | 22.717.289 | 47.430.808 |

---

## 14. Lỗi thường gặp — hiện tượng → nguyên nhân → làm gì

| Hiện tượng | Nguyên nhân thường gặp | Làm gì |
|---|---|---|
| Ô **giá trị** trong bộ biến vẫn là ô chữ dù biến là Select/Link | Thư viện biến thiếu *Select Options* / *Link Doctype* | Khai đủ ở §3.3 rồi mở lại bộ biến |
| Dialog báo giá **không hiện** biến nào | Bộ biến chưa có dòng, hoặc sản phẩm chưa gắn bộ biến | Kiểm khối "Bộ biến" ở §10 |
| Cảnh báo **"Thiếu giá trị cho biến …"** khi tính | Biến hệ thống **đã khai Source Doctype/Source Field** nhưng không ra giá trị: bản ghi nguồn để trống, hoặc bộ BOM chưa gắn hệ nhôm / loại sản phẩm | Kiểm bản ghi nguồn (hệ nhôm, loại sản phẩm) và ô nguồn ở Thư viện biến (§3.5) rồi tính lại |
| Dòng nẹp/keo có **mã hàng trống** | Quy tắc chọn mã chưa có khoảng giá trị phủ hết, hoặc đầu vào quy tắc không đọc được | Kiểm `RULE-NEP-GLASSTHICK` / `RULE-KEO-GLASSTYPE`; kiểm dòng kính có *Kính mặc định* |
| Cảnh báo công thức *"Công thức dùng biến theo dòng không đúng dạng"* | Công thức bộ BOM viết `unit_price` thay vì `items.<slug>.unit_price` | Sửa công thức |
| Dòng chọn mã theo quy tắc nhưng **mã hàng trống**, có câu "chưa chọn **dòng lấy dữ liệu**" | Quy tắc tra theo dữ liệu một dòng mà chưa chỉ dòng nguồn | Bấm **Chọn dòng lấy dữ liệu** (§5.5) |
| Giá lệch vài trăm nghìn ở bản 2 cánh | Bậc `RULE-BANLE-QTY` 2101–2700 bị sửa (phải = 4) | Trả bậc về 4 (§6) |
| Giá lệch khoảng 100 lần | Biến phần trăm **không nhận ra là phần trăm**: tên không kết thúc `_PCT/_RATE/_MARGIN` và Type chưa khai *Percent* | Đổi tên hoặc khai Type = Percent (§3.5) |
| Cột **thành tiền** của dòng = 0 dù có số lượng | Mã vật tư chưa có **Item Price** ở bảng giá đang dùng | Thêm giá (§2) |
| Nút **Lưu** bị từ chối, báo không có quyền | Tài khoản thiếu quyền trên DocType | Nhờ quản trị cấp quyền (§0) |
| Trang *Cấu hình sản phẩm* có khối **Không đọc được** (cam) | Bản ghi đã bị xoá, hoặc tài khoản không có quyền đọc | Đọc câu lỗi trên khối; bấm **Tải lại**; nếu vẫn lỗi, báo quản trị |

---

## 15. Danh sách kiểm trước khi báo giá một sản phẩm mới

- [ ] Slug của mọi dòng BOM đã có trong **Danh mục slug**.
- [ ] Mọi mã vật tư đã có **Item Price**.
- [ ] Biến dùng trong bộ biến đã có trong **Thư viện biến**, đúng kiểu, đủ *Select Options* / *Link Doctype*.
- [ ] Biến hệ thống đã khai **nguồn** và bản ghi nguồn có giá trị.
- [ ] Bộ BOM lưu **không còn cảnh báo** về biến / công thức.
- [ ] Bộ phụ kiện đã gắn đúng bộ biến (nếu dùng `n_panel`, `H_mm`).
- [ ] Sản phẩm đã gắn **Bộ BOM** + **Mẫu tính giá mặc định**, đã có **Phiên bản giá Published**.
- [ ] Trang *Cấu hình sản phẩm*: 7 khối **xanh lá** (khối **xám "Chưa gắn"** là chấp nhận được nếu bạn cố ý không dùng mảnh đó).
- [ ] Tính thử một bộ tham số và đối chiếu mốc §12 (nếu là sản phẩm mẫu).

---

## 16. Liên quan

- [Cấu hình sản phẩm và tạo sản phẩm từ mẫu](cau-hinh-san-pham-va-tao-tu-mau.vi.md) — trang tổng hợp + nhân bản sản phẩm.
- [Thiết kế gộp nơi cấu hình biến và công thức](../design/gop-noi-cau-hinh-bien-va-tinh-toan.md) — **tài liệu kỹ thuật**, đọc khi cần hiểu vì sao chỉ còn một nơi khai biến.
- [Cập nhật mã và cache](../ops/cap-nhat-ma-va-cache.md) — việc cần làm sau mỗi lần cập nhật app.
- [Hướng dẫn setting biến trên UI](../variable-catalog/huong-dan-setting-bien.md) — chi tiết hồ sơ biến, rule, xem trước.
