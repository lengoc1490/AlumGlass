# LỚP S — CƠ CHẾ TÍNH GIÁ DỰ KIẾN SẢN XUẤT & MAPPING 3 LỚP

> Tài liệu giải thích cơ chế, dùng để brief DEV/SA. Đi kèm `PHAN-BIEN-gia-thanh-3-lop.md`.
> Mọi tham chiếu code đã kiểm chứng trên repo (ERPNext v14.92.14 — đích v16 cần chạy lại).

---

## 1. S LÀ GÌ — MỘT CÔNG THỨC, BA TẦNG

Giá thành định mức của một dòng hàng luôn có dạng:

```
Chi phí = Σ ( LƯỢNG_i × ĐƠN_GIÁ_i )
```

Chia làm ba tầng, **mỗi tầng lấy dữ liệu từ một nguồn khác nhau**:

| Tầng | Câu hỏi | Nguồn | Ai sở hữu |
|---|---|---|---|
| **1. LƯỢNG** | Cần bao nhiêu kg nhôm, m² kính, giờ công? | Công thức BOM + hao hụt | Kỹ thuật / sản xuất |
| **2. ĐƠN GIÁ** | Mỗi đơn vị đó giá bao nhiêu? | Chính sách giá theo *profile* | Mua hàng / kế toán |
| **3. TỔNG HỢP** | Cộng lại thành nhóm nào, ra giá thành bao nhiêu? | Cost Template + bucket | Kế toán giá thành |

**Điểm cốt lõi:** Q và S **dùng chung tầng 1**, khác nhau ở tầng 2 và cách cộng ở tầng 3.
Vì vậy chênh lệch Q–S **luôn giải thích được** bằng một số hữu hạn tham số — không phải "hai hệ thống
ra hai số".

Trong code, tầng 1 đã tồn tại đầy đủ. Mỗi dòng của `al_bom_result` (`bom_orchestrator.py:2253`) chứa:

```
slug · item_code · width · height · qty · unit_qty · total_qty · unit_price · line_total
     · cost_bucket · unit · weight_per_unit · trace
```

`total_qty` **đã gồm hao hụt**, `trace` đã ghi công thức đã dùng. Nghĩa là tầng 1 **không cần xây lại**.

---

## 2. BỐN TRỤC KHÁC BIỆT GIỮA Q VÀ S

Chỉ có bốn, và mỗi trục là một cấu hình — không phải một nhánh code.

### Trục 1 — ĐƠN GIÁ VẬT TƯ

| | Q | S |
|---|---|---|
| Nguồn | `Item Price` bảng **giá bán**, có composite key theo màu | Giá vốn kho / giá mua gần nhất / bảng giá mua |
| Trong code | `_fetch_composite_prices()` / `_fetch_composite_prices_via_fb()` | Cần thêm `PriceResolver` |
| Cấu hình | `AL Cost Profile.price_basis = SELLING_PRICE_LIST` | `= VALUATION_RATE / LAST_PURCHASE_RATE / BUYING_PRICE_LIST` |

**Ba lựa chọn giá vốn — chọn cái nào?**

| `price_basis` | Ý nghĩa | Dùng khi |
|---|---|---|
| `VALUATION_RATE` | Bình quân gia quyền **hiện tại** của kho | **Khuyến nghị mặc định.** Là ước lượng tốt nhất về giá mình sắp phải trả |
| `LAST_PURCHASE_RATE` | Giá lần mua gần nhất | Khi giá biến động mạnh và tồn kho cũ làm bình quân lệch |
| `BUYING_PRICE_LIST` | Bảng giá nhà cung cấp đã đàm phán | Khi có hợp đồng khung |

⚠ Bẫy: giá vốn kho **không có** khi vật tư chưa từng nhập (hàng mới). Phải có fallback chain:
`VALUATION_RATE → LAST_PURCHASE_RATE → BUYING_PRICE_LIST → LỖI` (không được rơi về 0).

### Trục 2 — HAO HỤT

| | Q | S |
|---|---|---|
| Nguồn | `AL Material Category.default_scrap_pct` (ước lượng theo nhóm) | **Cutting Plan** (bài toán cắt thật) hoặc định mức nhóm |
| Đơn vị áp dụng | Từng dòng BOM | Cấp **lô cắt**, phân bổ về dòng |
| Cấu hình | `AL Cost Profile.scrap_mode = CATEGORY_DEFAULT` | `= CUTTING_PLAN / FIXED_PCT / NONE` |

**Công thức đúng:**

```
gross_qty = net_qty × (1 + scrap_pct)
```

⚠ **Cấm cộng hai lần.** Nếu `scrap_pct` lấy từ Cutting Plan thì nó phải được định nghĩa là
`(lượng_cần_mua / lượng_tịnh) − 1`. Nếu Cutting Plan trả về **số cây / số kg cần mua** trực tiếp
thì dùng thẳng con số đó, **không nhân thêm gì**:

```
gross_qty = cutting_plan.required_qty_of(item)      ← dùng thẳng
```

Ba trạng thái phải phân biệt được trên dữ liệu:

| Trạng thái | Ý nghĩa | Hành vi |
|---|---|---|
| `FROM_CUTTING_PLAN` | Có plan thật | Dùng số của plan |
| `FROM_STANDARD` | Chưa có plan, dùng định mức nhóm | Tính, nhưng **đánh dấu là ước lượng** |
| `FROM_QUOTATION` | Không có gì, dùng % của báo giá | Tính, **cảnh báo rõ** |

### Trục 3 — NHÂN CÔNG

| | Q | S |
|---|---|---|
| Cách tính | % × tổng vật liệu (`NC_SX_PCT = 8%`) | **Σ (giờ công × đơn giá giờ)** hoặc định mức công/bộ |
| Nguồn giờ | — | BOM Operation / bảng định mức công theo loại sản phẩm |
| Cấu hình | `labor_mode = PERCENT_OF_MATERIAL` | `= OPERATIONS` hoặc `= PIECE_RATE` |

**Công thức:**

```
# Chế độ OPERATIONS (chi tiết)
labor = Σ_op ( hours_op × rate_op )      # rate_op: Operation / Workstation / biến FB

# Chế độ PIECE_RATE (thực dụng — khuyến nghị cho xưởng VN)
labor = Σ_op ( piece_rate_op × số_bộ )   # đơn giá khoán/công đoạn, đọc từ bảng định mức
```

**Chọn chế độ nào?** Xem §4.4 của bản phản biện: nếu công nhân không bấm giờ thì `OPERATIONS`
chỉ là số nhập tay giả dạng tự động. `PIECE_RATE` trung thực hơn và khớp với cách trả lương thật.

### Trục 4 — LỢI NHUẬN & VAT

| | Q | S |
|---|---|---|
| `PROFIT`, `VAT` | Có | **Không có** |
| Cấu hình | `include_profit_vat = 1` | `= 0` |

Ngoài ra Q có thêm **chi phí chung mode** khác S (Q: % vật liệu; S: theo driver m²/giờ công).

---

## 3. CƠ CHẾ HAI BẢN S₀ / S₁

### 3.1 Vì sao phải hai bản

Nếu S chạy theo giá vốn hiện hành và cập nhật liên tục, thì **A − S phần giá luôn ≈ 0 theo định nghĩa**
— mất hoàn toàn khả năng phát hiện mua đắt/rẻ.

Nhưng nếu S đứng yên mãi, thì khi giá nhôm tăng 15% bạn vẫn nhìn con số cũ và tưởng đơn này lãi.

→ Cần cả hai, nhưng **phải tách bạch**.

### 3.2 Định nghĩa

| | **S₀ — định mức khoá** | **S₁ — dự báo sống** |
|---|---|---|
| Tính khi | Sales Order **Submit** (hoặc lúc "Release") | Mỗi khi đầu vào đổi |
| Đơn giá dùng | Giá vốn **tại thời điểm khoá** | Giá vốn **hiện tại** |
| Thay đổi được không | **Không.** Chỉ đổi qua hành động "Tái chuẩn hoá" (có lý do + người duyệt) | Luôn cập nhật |
| Dùng để | Đo chênh lệch A−S₀, tính "lợi nhuận kế hoạch thực" | Cảnh báo "đơn đang đắt lên", quyết định mua, tái báo giá |
| Sinh revision | Có (mỗi lần tái chuẩn hoá) | Không |

### 3.3 Lưu ở đâu

**Một DocType `AL Cost Plan`, một bản ghi cho mỗi dòng SO.** Không phải hai DocType.

```
AL Cost Plan
├─ sales_order, sales_order_item, project, item_code, qty
├─ al_bom, al_bom_version, config_snapshot        ← kế thừa từ Quotation
├─ cost_profile
├─ standard_locked_on, locked_by, lock_reason     ← S₀
├─ current_calculated_on                          ← S₁
├─ structure_json                                 ← cấu trúc dòng hàng (xem 3.4)
├─ standard_amount, current_amount                ← hai con số
├─ standard_breakdown_json, current_breakdown_json
└─ errors_json
```

Bảng con `AL Cost Plan Line` **chỉ cần một bảng**, mục đích duy nhất: trả lời câu
*"giá nhôm đổi → những Cost Plan nào bị ảnh hưởng?"*. Khoá `(item_code, plan)` có index.

```
AL Cost Plan Line
├─ item_code (index), uom
├─ net_qty, gross_qty, scrap_pct, scrap_source
├─ unit_price, amount
├─ cost_bucket
```

Bảng `operations` / `buckets` / `template_lines` **không cần** — chúng nằm trong `structure_json`.
Đây là chỗ tài liệu gốc thiết kế nặng hơn cần thiết (xem §4 bản phản biện).

### 3.4 `structure_json` — trái tim của cơ chế

Đây là **phần dùng chung** giữa S₀ và S₁: số lượng đã tính, chưa nhân giá.

```json
{
  "lines": [
    {"slug": "khung_ngang", "item_code": "NHOM-XINGFA", "uom": "kg",
     "net_qty": 5.5296, "scrap_pct": 0.115, "scrap_source": "CUTTING_PLAN",
     "gross_qty": 6.1655, "cost_bucket": "VL_NHOM"},
    {"slug": "kinh_canh", "item_code": "KINH-8LY", "uom": "m2",
     "net_qty": 4.6920, "scrap_pct": 0.0, "scrap_source": "PROCESSOR_CUT",
     "gross_qty": 4.6920, "cost_bucket": "VL_KINH"}
  ],
  "operations": [
    {"operation": "CAT_NHOM", "hours": 1.2, "rate": 95000, "cost_bucket": "NC_SX"}
  ],
  "drivers": {"m2_giao": 6.24, "gio_cong_tt": 8.6},
  "template_version": "STANDARD-CD",
  "resolved_inputs": { "...": "toàn bộ biến đã resolve" }
}
```

**Quy tắc bất di bất dịch:**
- `structure_json` được tính **một lần** (khi SO Submit hoặc khi BOM/định mức cắt đổi).
- `standard_amount` và `current_amount` = **cùng structure × hai bộ đơn giá**.
- Đổi giá **không** làm structure đổi ⇒ **không cần chạy lại engine BOM**, chỉ chạy lại tầng 2.

Đây là lý do "realtime" trở nên rẻ: bạn không tính lại BOM, bạn chỉ nhân lại.

### 3.5 Vòng đời

```
SO Submit
   └─► compute() → structure_json + S₀ (khoá giá tại thời điểm này)
         └─► AL Cost Plan: standard_amount, current_amount = S₀

Item Price / Stock Ledger đổi (debounce 60s)
   └─► chỉ chạy tầng 2 trên structure_json có sẵn
         └─► current_amount cập nhật.  standard_amount ĐỨNG YÊN.
         └─► nếu |current/standard − 1| > ngưỡng (mặc định 5%)
               → publish_realtime cảnh báo cho người phụ trách đơn

Cutting Plan đổi / BOM Version đổi
   └─► structure_json đổi → phải chạy lại engine
         └─► S₀ xử lý thế nào?  ← XEM 3.6

Release (thả sản xuất)
   └─► khoá: standard_amount trở thành mốc đo lường chính thức
```

### 3.6 Câu hỏi khó: Cutting Plan đổi SAU khi đã khoá S₀

Đây là tình huống sẽ xảy ra thật (cắt thử xong mới biết bố cục tối ưu). Ba lựa chọn:

| Cách xử lý | Khi nào dùng |
|---|---|
| **Giữ S₀ cũ, tạo S₀ mới có revision** | Chuẩn. Báo cáo chênh lệch dùng S₀ mới nhất trước Release |
| Khoá cứng, không cho đổi | Khi đã Release — mọi thay đổi đi qua Change Order |
| Ghi đè | **Không bao giờ.** Mất khả năng truy vết |

Quy tắc: **trước Release ⇒ được tái chuẩn hoá (có ghi vết). Sau Release ⇒ đóng băng.**

---

## 4. CÔNG THỨC TÍNH TỪNG KHỐI

### 4.1 Vật tư

```
for line in bom_result:                          # tầng 1 — có sẵn
    net_qty   = line.total_qty / (1 + scrap_cũ)  # hoặc đọc thẳng net nếu có
    scrap     = scrap_resolver(line, profile)    # trục 2
    gross_qty = net_qty × (1 + scrap)
    price     = price_resolver(line.item_code, profile, as_of)   # trục 1
    amount    = gross_qty × price
    → bucket  = line.cost_bucket
```

Xử lý lỗi: nếu `price is None` ⇒ **ghi vào `errors_json`, không được coi là 0**.
Profile S bật `strict_errors` ⇒ không cho khoá S₀ khi còn lỗi cứng.

### 4.2 Nhân công

```
# OPERATIONS
for op in operations:
    amount = op.hours × op.rate
    bucket = op.cost_bucket        # thường NC_SX hoặc MAY_THI_CONG

# PIECE_RATE
amount = piece_rate(sản_phẩm, công_đoạn) × qty
```

### 4.3 Lắp đặt

```
amount = số_người × giờ × đơn_giá_đội × hệ_số_độ_cao(installation_height_m)
```

Hệ số độ cao lấy từ **cùng bảng rule** mà báo giá đang dùng (`lookup_rule('RULE-HEIGHT-MULT', h)`)
— nếu Q và S dùng hai bảng rule khác nhau thì chênh lệch Q–S sẽ có một phần không giải thích được.

### 4.4 Chi phí chung

```
# Theo %           (Q đang dùng)
overhead = pct × (vật_liệu + nhân_công)

# Theo driver      (S nên dùng)
overhead = driver_value × rate_per_driver
  driver: m2_giao | gio_cong_truc_tiep | gia_tri_vat_lieu
```

Driver và rate **phải là cùng một nguồn cấu hình** với `AL Cost Allocation Rule` dùng khi phân bổ
thực tế cuối kỳ — nếu không, S và A sẽ dùng hai thước đo khác nhau và chênh lệch là giả.

### 4.5 Tổng hợp

```
Cost Template (loại STANDARD):
  TONG_VL   = VL_NHOM + VL_KINH + VL_PK
  TONG_NC   = NC_SX + NC_LD
  TONG_OH   = OH_SX + OH_VANCHUYEN
  GIA_THANH = TONG_VL + TONG_NC + TONG_OH          ← is_final_price = 1
```

---

## 5. MAPPING GIỮA 3 LỚP — NGUYÊN TẮC

### 5.1 Nguyên tắc gốc: **không map 3 lớp với nhau**

Sai lầm phổ biến là nghĩ phải map Q↔S↔A. Không phải.

**Đúng:** mỗi lớp map **một lần** về một **lưới chung**, rồi so sánh trên lưới.

```
                    LƯỚI CHUNG
              (project, bucket, account, kỳ)
                    ▲    ▲    ▲
        ┌───────────┘    │    └───────────┐
        │                │                │
   Q (bucket→account)  S (đã có bucket)  A (account→bucket)
```

### 5.2 Điểm mấu chốt ít ai nói: **hai chiều mapping có độ tin cậy KHÁC NHAU**

| Lớp | Có sẵn (đo được) | Phải suy ra (là phép biến đổi) |
|---|---|---|
| **Q** | **bucket** — engine BOM tính ra | account — chia theo trọng số |
| **S** | **bucket** — engine tính ra | account — **1:1 nếu thiết kế bucket theo tài khoản** |
| **A** | **account** — sổ cái ghi | bucket — **suy luận** từ vật tư/tài khoản |

Nghĩa là: **Q và S đo cột bucket; A đo cột account.** Hai bên đo hai chiều khác nhau, và mọi ô còn
lại là số suy ra. Đây là lý do bắt buộc phải có mapping — và cũng là lý do **phải giảm thiểu trọng số**.

Đưa lên báo cáo, mỗi ô cần một nhãn nguồn:

| Nhãn | Nghĩa | Ví dụ |
|---|---|---|
| ● **Đo** | Số tính từ dữ liệu gốc | S theo bucket; A theo account |
| ◐ **Suy 1 bước** | Một phép biến đổi xác định (1:1) | S theo account (bucket→account 1:1) |
| ○ **Phân bổ** | Chia theo trọng số giả định | Q theo account; A theo bucket |

Không có nhãn này, kế toán sẽ tranh cãi số của một phép chia 40/60 như thể đó là sự thật.

### 5.3 Thiết kế bucket để mapping S là **1:1** — cách giảm 80% độ phức tạp

Nếu bộ bucket của S được đặt **trùng ranh giới tài khoản**, thì `bucket → account` là ánh xạ 1:1,
không cần trọng số, không cần công thức, không cần ai duyệt.

| Bucket | Tài khoản | Tỷ lệ |
|---|---|---|
| `VL_NHOM` | 621 | 1:1 |
| `VL_KINH` | 621 | 1:1 |
| `VL_PK` | 621 | 1:1 |
| `NC_SX` | 622 | 1:1 |
| `NC_LD` | 622 | 1:1 |
| `MAY_THI_CONG` | 623 | 1:1 |
| `CHUNG` | 627 | 1:1 |
| `LAM_LAI` | 627 | 1:1 |
| `SCRAP_REC` | 621 (dấu −) | 1:1 |

Chỉ **Q** mới cần trọng số, vì Q gộp chi phí chung vào một dòng `OH_QLY` phục vụ mục đích bán hàng:

| Nguồn | Đích | Tỷ lệ | Ghi chú |
|---|---|---|---|
| `OH_QLY` (Q) | 627 | 40% | **Giả định** — ghi rõ trên báo cáo |
| `OH_QLY` (Q) | 642 | 60% | **Giả định** |

Nếu không muốn số giả định, cách sạch hơn: **đừng đưa Q lên cột tài khoản**. So Q với A ở cấp bucket,
và chỉ so S với A ở cấp tài khoản. Bớt một phép chia bịa, bớt một nguồn tranh cãi.

### 5.4 A lấy bucket từ đâu — thứ tự ưu tiên

```
1. Dimension trên dòng chứng từ (người dùng chọn / rule đã gán)
2. Item → AL Material Category → default_cost_bucket
3. Account + voucher_type + chiều nợ/có → AL Cost Mapping Rule
4. UNMAPPED          ← luôn hiển thị, không bao giờ im lặng
```

Chi tiết kỹ thuật đã kiểm chứng: `AL Cost Bucket` là **Accounting Dimension**, field sinh ra trên
`Stock Entry Detail`, `Purchase Receipt Item`, `Purchase Invoice Item`, `Journal Entry Account`,
`Landed Cost Item`… (`erpnext/hooks.py:513`). Khi ghi sổ, `merge_similar_entries()` gộp bút toán
**theo danh sách dimension**, nên bucket của từng dòng **không bị trộn** khi gộp. Điều này có nghĩa
thiết kế khả thi — không cần collector tự tách dòng.

### 5.5 Thuật toán dựng lưới

```
BƯỚC 1 — Chuẩn hoá mỗi nguồn về (bucket, account, cost_center, amount)

  Q/S:  bucket  = có sẵn từ Cost Template
        account = bucket_to_account(bucket, layer, ngày)     # 1:1 hoặc có trọng số

  A:    account = có sẵn từ GL Entry
        bucket  = dimension ?? item_category ?? account_rule ?? UNMAPPED

BƯỚC 2 — Chia theo trọng số (chỉ khi 1 → nhiều)
        amount_ba = amount × w_bucket × w_account
        Σw = 100% (bắt buộc); dư làm tròn → largest remainder

BƯỚC 3 — Cộng dồn vào lưới
        grain = (project, sales_order_item?, bucket, account, cost_center, period)
```

### 5.6 Làm tròn — bắt buộc dùng largest remainder

Chia 346.257 theo 40/60:

```
sai (làm tròn từng phần):  138.503 + 207.754 = 346.257  ✔ (may mắn)
sai (làm tròn xuống):      138.502 + 207.754 = 346.256  ✘ lệch 1 đồng
```

Với VND không thập phân, dùng **largest remainder**: chia nguyên, dồn các đồng dư vào dòng có phần
lẻ lớn nhất. Viết **một hàm dùng chung** cho mọi chỗ chia (bucket, account, allocation, phân bổ về dòng SO).

### 5.7 Kiểm tra — phải là phép đối chứng độc lập, không phải hằng đẳng thức

| Kiểm | Đối chứng | Bắt được |
|---|---|---|
| Đóng với sổ cái | `Σ Cost Fact(account) == Σ GL Entry(project, account, kỳ)` | Collector bỏ sót/nhân đôi |
| Đóng với kho | `Σ Fact(VL_*) == Σ Stock Ledger.stock_value_difference(project)` | Giá trị xuất kho lệch GL |
| Phủ | `Σ GL có project − Σ Fact = 0` | Mất tiền im lặng |
| **Đối chứng dương** | Cố tình map sai 1 tài khoản → báo cáo **phải đỏ** | Phép kiểm là tautology |

---

## 6. VÍ DỤ CHẠY SUỐT — 1 bộ `CDMQ-2C` 2400×2600

### 6.1 Tầng 1 — LƯỢNG (dùng chung, engine BOM)

| Slug | Công thức | Tịnh | Hao hụt Q | Hao hụt S | Gồm Q | Gồm S |
|---|---|---:|---:|---:|---:|---:|
| `khung_ngang` | (2400−2×48)mm × 1,2 kg/m × 2 | 5,5296 kg | 20% | 11,5% | 6,6355 | 6,1655 |
| `kinh_canh` | (…/2−2×66) × (2600−300) mm × 2 | 4,6920 m² | 5% | 0%¹ | 4,9266 | 4,6920 |

¹ kính mua **gia công cắt sẵn** ⇒ hao hụt phía bạn = 0 (xem §4.2 bản phản biện).

### 6.2 Tầng 2 — ĐƠN GIÁ

| | Q | S |
|---|---:|---:|
| Nhôm | 113.000 đ/kg (bảng giá bán) | 109.800 đ/kg (giá vốn kho) |
| Kính | 725.000 đ/m² | 702.000 đ/m² |

### 6.3 Tầng 3 — THÀNH TIỀN

| Dòng | Q | S |
|---|---:|---:|
| `khung_ngang` | 6,6355 × 113.000 = **749.814** | 6,1655 × 109.800 = **676.972** |
| `kinh_canh` | 4,9266 × 725.000 = **3.571.785** | 4,6920 × 702.000 = **3.293.784** |
| … | | |
| `TONG_VL` | 10.124.468 | 9.315.504 |
| `NC_SX` | 8% × 10.124.468 = **809.957** | 1,2h×95.000 + 5,0h×110.000 + 2,4h×105.000 = **916.000** |
| `NC_LD` | 6% × TONG_VL × 1,0 = **607.468** | 2 × 2,5h × 120.000 = **600.000** |
| `OH_VC` | 3% × TONG_VL = **303.734** | 6,24 m² × 28.000 = **174.720** |
| `OH_QLY` | 3% × (VL+NC) = **346.257** | 2,5% × (VL+NC) = **270.788** |
| `OH_SX` | — | 8,6 giờ × 28.000 = **240.800** |
| **GIÁ THÀNH** | **12.191.884** | **11.517.812** |

**Đọc chênh lệch Q→S (−674.072):**

| Nguyên nhân | Tác động |
|---|---:|
| Giá vật tư thấp hơn (giá vốn < giá bán) | −583.000 (xấp xỉ) |
| Hao hụt nhôm thấp hơn (11,5% < 20%) | −182.000 |
| Nhân công S cao hơn Q | +298.000 |
| Chi phí chung S thấp hơn Q | −147.000 |

Mỗi con số **truy được về đúng một trục cấu hình**. Đó là toàn bộ giá trị của việc dùng chung engine.

### 6.4 Mapping ra lưới

| Nguồn | Bucket | Tài khoản | Số tiền | Nhãn |
|---|---|---|---:|---|
| Q | `VL_NHOM` | 621 (1:1) | 4.681.237 | ● đo bucket / ◐ suy account |
| S | `VL_NHOM` | 621 (1:1) | 3.849.xxx | ● / ◐ |
| A — Stock Entry xuất nhôm | `VL_NHOM` (từ vật tư) | 621 | 8.879.632 | ◐ suy bucket / ● đo account |
| A — PI thuê cẩu, chỉ có Project | `MAY_THI_CONG` (từ rule 627+PI) | 627 | 600.000 | ○ suy luận |
| A — PI không match rule nào | **`UNMAPPED`** | 627 | ? | ○ **cảnh báo** |

---

## 7. BẢY CÁI BẪY PHẢI XỬ LÝ

| # | Bẫy | Hành vi đúng |
|---|---|---|
| 1 | **Giá không có** (hàng mới chưa nhập) | Lỗi cứng + chặn khoá S₀. **Không được = 0** |
| 2 | **Lỗi công thức FB** | Trả 0 im lặng — bật `strict_errors`, banner đỏ trên form |
| 3 | **Vật tư chưa có nhóm** (`AL Material Category` trống) | Bucket = `UNMAPPED`, hiện trên báo cáo |
| 4 | **Cutting Plan chưa có** | Fallback định mức nhóm, đánh dấu `FROM_STANDARD` |
| 5 | **BOM tuần hoàn / slug trùng** | Chặn khi lưu BOM, không chặn lúc tính |
| 6 | **Nhiều dòng SO cùng item** | Index `(item_code, plan)`; cập nhật theo lô |
| 7 | **Chứng từ hạch toán lùi ngày** | Snapshot A đánh dấu `Stale`, chạy lại idempotent theo checksum |

---

## 8. CẤU HÌNH BẰNG FORMULA BUILDER — CHỖ NÀO, KHÔNG CHỖ NÀO

| Đưa vào FB | Để trong code Python |
|---|---|
| Đơn giá giờ, đơn giá khoán | Công thức chênh lệch (giá/lượng/hiệu suất) |
| % chi phí chung, % hao hụt mặc định | Chiều dấu (+/−), thứ tự tính |
| Hệ số độ cao, hệ số sản phẩm | Largest remainder |
| Tỷ lệ trích bảo hành | Logic chọn bucket, fallback chain |
| Ngưỡng cảnh báo | Điều kiện khoá S₀ |

**Lý do:** FB biến lỗi công thức thành **0**. Một công thức chênh lệch trả 0 trông y hệt "không có
chênh lệch". Bốn dòng Python thì test được; một binding sai thì im lặng.

Cấu hình cần thiết, đã kiểm chứng là làm được:
- `aggregate_from_items` hỗ trợ `rows_source: doctype_query` + `filters` ⇒ query `Bin.valuation_rate` được.
- `AL Cost Bucket.source_type` hiện có: `aggregate_from_items · formula · doctype_query · custom_function ·
  constant · pipeline · conditional · fallback_chain`.

---

## 9. TÓM TẮT CƠ CHẾ TRONG 6 DÒNG

```
1. Tầng 1 (LƯỢNG) có sẵn trong al_bom_result — không xây lại.
2. S = cùng tầng 1, đổi 4 trục: giá · hao hụt · nhân công · lãi/VAT.
3. structure_json lưu tầng 1; S₀ và S₁ chỉ là hai bộ đơn giá trên cùng structure.
4. S₀ khoá lúc SO Submit, bất biến (trừ tái chuẩn hoá có ghi vết); S₁ sống.
5. Đổi giá ⇒ chỉ nhân lại tầng 2, không chạy lại engine BOM, không sinh revision.
6. Mapping: mỗi lớp map MỘT LẦN về lưới (project, bucket, account, kỳ); bucket thiết kế
   trùng ranh giới tài khoản để phép map của S là 1:1; chỉ Q cần trọng số.
```
