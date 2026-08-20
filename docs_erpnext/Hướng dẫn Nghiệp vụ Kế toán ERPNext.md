# Hướng dẫn Nghiệp vụ Kế toán ERPNext — Toàn tập

> **Ngôn ngữ:** Tiếng Việt
> **Phiên bản:** ERPNext (dựa trên mã nguồn Frappe/ERPNext)
> **Mục đích:** Tài liệu tham khảo đầy đủ về quy trình nghiệp vụ kế toán, hạch toán Nợ/Có, giải thích bản chất kế toán cho từng nghiệp vụ
> **Phạm vi:** Mua hàng, Bán hàng, Kho, Tiền tệ & Tỷ giá, Nội bộ, Phân bổ chi phí, Doanh thu/Chi phí hoãn lại, Thuế, Thanh toán, Kết chuyển cuối kỳ

---

## Mục lục

1. [Tổng quan hệ thống tài khoản](#1-tong-quan-he-thong-tai-khoan)
2. [Mua hàng (Purchase to Pay)](#2-mua-hang-purchase-to-pay)
3. [Bán hàng (Order to Cash)](#3-ban-hang-order-to-cash)
4. [Kho & Tồn kho (Inventory)](#4-kho--ton-kho-inventory)
5. [Phân bổ chi phí — Landed Cost Voucher](#5-phan-bo-chi-phi--landed-cost-voucher)
6. [Doanh thu & Chi phí hoãn lại (Deferred Accounting)](#6-doanh-thu--chi-phi-hoan-lai-deferred-accounting)
7. [Thuế (Tax Accounting)](#7-thue-tax-accounting)
8. [Thanh toán (Payment Entry & Reconciliation)](#8-thanh-toan-payment-entry--reconciliation)
9. [Nhiều tiền tệ & Tỷ giá (Multi-currency & FX)](#9-nhieu-tien-te--ty-gia-multi-currency--fx)
10. [Mua bán nội bộ (Inter-company)](#10-mua-ban-noi-bo-inter-company)
    - 10.7. Mua bán nội bộ qua kho A → B → End Customer (hạch toán chi tiết)
    - 10.7.7. Các phương án triển khai (PA1-PA4) — so sánh và khuyến nghị
    - 10.8. Mua bán nội bộ — không qua kho (dịch vụ, lãi vay, phân bổ CP)
    - 10.9. Hàng gửi bán (Consignment)
11. [Kết chuyển cuối kỳ (Period Closing)](#11-ket-chuyen-cuoi-ky-period-closing)
12. [Báo cáo tài chính](#12-bao-cao-tai-chinh)

---

## 1. Tổng quan hệ thống tài khoản

### 1.1. Các tài khoản kế toán mặc định trong ERPNext

ERPNext sử dụng hệ thống tài khoản (Chart of Accounts) với cấu trúc cây phân cấp. Mỗi Công ty (Company) có một bộ tài khoản riêng.

| Loại tài khoản | Nhóm | Ví dụ |
|---|---|---|
| **Application of Funds (Tài sản)** | Asset | Tiền mặt, Tiền gửi NH, Kho, Phải thu KH, Chi phí trả trước |
| **Source of Funds (Nguồn vốn)** | Liability & Equity | Phải trả NB, Phải trả thuế, Vốn góp, Lợi nhuận giữ lại |
| **Income (Doanh thu)** | Income | Doanh thu bán hàng, Doanh thu tài chính |
| **Expenditure (Chi phí)** | Expense | Giá vốn hàng bán (COGS), Chi phí QLDN, Chi phí bán hàng |

### 1.2. Các tài khoản đặc thù trong ERPNext

Khi bật **Perpetual Inventory** (Kiểm kê vĩnh viễn) ở Company, các tài khoản sau được cấu hình:

| Trường | Ý nghĩa | Bản chất kế toán |
|---|---|---|
| `default_inventory_account` | Tài khoản hàng tồn kho | Tài sản (Asset) — giá trị hàng tồn trong kho |
| `stock_adjustment_account` | Tài khoản điều chỉnh kho | Doanh thu/Chi phí (P&L) — bù trừ cho chênh lệch kho |
| `stock_received_but_not_billed` | Hàng nhận nhưng chưa có hóa đơn | Nợ phải trả (Liability) — hàng về trước hóa đơn về sau |
| `default_expense_account` | Tài khoản chi phí mặc định (COGS) | Chi phí (Expense) — giá vốn hàng bán |
| `exchange_gain_loss_account` | Lãi/lỗ tỷ giá thực tế | Doanh thu/Chi phí tài chính — chênh lệch tỷ giá khi thanh toán |
| `unrealized_exchange_gain_loss_account` | Lãi/lỗ tỷ giá chưa thực hiện | Doanh thu/Chi phí tài chính — đánh giá lại cuối kỳ |

### 1.3. Nguyên tắc hạch toán cơ bản

ERPNext hoạt động theo **nguyên tắc kế toán kép (double-entry)**:
- Mỗi giao dịch có ít nhất 1 tài khoản Nợ (Debit) và 1 tài khoản Có (Credit)
- Tổng số tiền bên Nợ = Tổng số tiền bên Có
- Phương trình kế toán: **Tài sản = Nợ phải trả + Vốn chủ sở hữu**

Ghi nhớ: **Debit** = bên trái, **Credit** = bên phải. Ý nghĩa của Nợ/Có phụ thuộc vào loại tài khoản:

| Loại TK | Tăng | Giảm |
|---|---|---|
| Asset (Tài sản) | **Debit** (+) | Credit (-) |
| Expense (Chi phí) | **Debit** (+) | Credit (-) |
| Liability (Nợ phải trả) | Credit (+) | **Debit** (-) |
| Equity (Vốn) | Credit (+) | **Debit** (-) |
| Income (Doanh thu) | Credit (+) | **Debit** (-) |

---

## 2. Mua hàng (Purchase to Pay)

### 2.1. Tổng quan quy trình

Quy trình mua hàng đầy đủ trong ERPNext gồm các bước:

```
Material Request (Yêu cầu mua hàng)
    | (Không có hạch toán kế toán)
    v
Purchase Order (Đơn đặt hàng)
    | (Không có hạch toán kế toán)
    v
Purchase Receipt (Nhập kho) --- chỉ khi Kiểm kê vĩnh viễn (Perpetual Inventory)
    | (Có hạch toán)
    v
Purchase Invoice (Hóa đơn mua hàng)
    | (Có hạch toán chính)
    v
Payment Entry (Thanh toán)
```

### 2.2. Yêu cầu Mua hàng (Material Request)

**Không có hạch toán kế toán.** Material Request chỉ là chứng từ nội bộ, chỉ cập nhật số lượng đặt hàng trong kho (Bin).

### 2.3. Đơn đặt hàng (Purchase Order)

**Không có hạch toán kế toán.** Purchase Order là chứng từ cam kết mua hàng, chỉ cập nhật `ordered_qty` trong kho.

**Ngoại lệ:** Nếu là đơn nội bộ (Inter-company Purchase) thì vẫn không có GL Entry ở PO. GL Entry chỉ xuất hiện ở Invoice.

### 2.4. Nhập kho (Purchase Receipt)

**Chỉ tạo GL Entry khi bật Perpetual Inventory (enable_perpetual_inventory = True).**

#### 2.4.1. Nhập kho thường — hàng mua từ nhà cung cấp

**Hạch toán:**

```
Nợ  Tài khoản hàng tồn kho (Warehouse Account)     [stock_value_difference]
Có  Hàng nhận chưa có hóa đơn (Stock Received But Not Billed)  [base_net_amount]
```

**Giải thích bản chất:**
- **Nợ Tài khoản hàng tồn kho:** Hàng đã về kho, giá trị tồn kho tăng lên. Đây là tài sản của doanh nghiệp.
- **Có Hàng nhận chưa có hóa đơn:** Hàng đã về nhưng chưa có hóa đơn của NCC. Đây là một khoản **Nợ phải trả** (Liability) — doanh nghiệp đang nợ NCC số tiền hàng.

**Ví dụ cụ thể:**
Doanh nghiệp mua 100 sản phẩm X, đơn giá 50.000đ, tổng 5.000.000đ. Hàng đã về kho A.

```
Nợ  TK "Hàng tồn kho - Kho A"        5.000.000
Có  TK "Hàng nhận chưa có hóa đơn"   5.000.000
```

#### 2.4.2. Thuế giá trị gia tăng (VAT) trên Purchase Receipt

Thuế ở Purchase Receipt được xử lý đặc biệt: nó được **ghi giảm vào thuế đầu vào** (không hạch toán vào kho).

Nếu thuế có `category = "Valuation"` hoặc `"Valuation and Total"`:

```
Có  TK "Thuế GTGT đầu vào"     [số thuế]
```

**Ví dụ:** Mua hàng 5.000.000đ, thuế GTGT 10% = 500.000đ.

```
Nợ  TK "Hàng tồn kho - Kho A"        5.000.000
Có  TK "Hàng nhận chưa có hóa đơn"   5.000.000
Có  TK "Thuế GTGT đầu vào"              500.000  (đây là phần valuation tax)
```

#### 2.4.3. Chênh lệch tỷ giá (Rate Difference)

Khi Purchase Receipt có tỷ giá khác với Purchase Order, và Purchase Invoice đã tồn tại, chênh lệch tỷ giá được hạch toán vào `exchange_gain_loss_account`:

```
Có  TK "Hàng nhận chưa có hóa đơn"   [chênh lệch tỷ giá]
```

#### 2.4.4. Chi phí phân bổ (Landed Cost)

Khi có Landed Cost Voucher, Purchase Receipt được **cập nhật lại giá trị kho**:

```
Có  TK "Chi phí vận chuyển / Hải quan"   [số tiền phân bổ]
```

#### 2.4.5. Khoản mất phân chia (Divisional Loss)

Khi tổng giá trị hạch toán không khớp với `stock_value_difference`, phần chênh lệch được đưa vào:

```
Nợ  TK "Chi phí mặc định (COGS)"         [khoản mất phân chia]
```

#### 2.4.6. Mua nội bộ (Internal Transfer) khi Nhập kho

Ở Purchase Receipt, nếu có `from_warehouse` (hàng chuyển từ công ty con sang):

```
Nợ  TK "Kho nhận"              [giá trị]
Có  TK "Kho chuyển"            [giá trị]
```

### 2.5. Hóa đơn mua hàng (Purchase Invoice)

Purchase Invoice là chứng từ tạo nhiều GL Entry nhất trong quy trình mua hàng.

#### 2.5.1. Hạch toán cơ bản

Khi submit Purchase Invoice, ERPNext gọi `get_gl_entries()` thực hiện theo thứ tự:

1. **make_supplier_gl_entry()** — Ghi nhận công nợ NCC
2. **make_item_gl_entries()** — Ghi nhận chi phí / hàng tồn kho cho từng item
3. **make_tax_gl_entries()** — Ghi nhận thuế
4. **make_precision_loss_gl_entry()** — Làm tròn
5. **make_discount_gl_entries()** — Ghi nhận chiết khấu
6. **make_write_off_gl_entry()** — Xóa nợ (write-off)

#### 2.5.2. Hạch toán tổng thể

**Mua hàng dịch vụ (Service Item) — không vào kho:**

```
Nợ  TK "Chi phí QLDN / Chi phí bán hàng"    [giá trị hàng]
Nợ  TK "Thuế GTGT đầu vào"                   [thuế]
Có  TK "Phải trả nhà cung cấp"               [tổng cộng]
```

**Mua hàng hóa (Stock Item) — có Perpetual Inventory:**

Trường hợp 1: **Đã nhập kho trước (PR tồn tại)**
Tài khoản chi phí sẽ là `"Stock Received But Not Billed"` để đảo ngược định khoản từ Purchase Receipt:

```
Nợ  TK "Hàng nhận chưa có hóa đơn"           [giá trị hàng]  --- ĐẢO NGƯỢC SRNB
Nợ  TK "Thuế GTGT đầu vào"                   [thuế]
Có  TK "Phải trả nhà cung cấp"               [tổng cộng]
```

**Giải thích:** Purchase Receipt trước đó đã ghi:
- Nợ Hàng tồn kho / Có Hàng nhận chưa có hóa đơn

Bây giờ Purchase Invoice ghi:
- Nợ Hàng nhận chưa có hóa đơn (làm giảm công nợ SRNB)
- Có Phải trả NCC (công nợ thực)

Khi cả PR và PI cùng tồn tại, tài khoản **Hàng nhận chưa có hóa đơn về 0**:
- PR: Có 5.000.000
- PI: Nợ 5.000.000
- Số dư = 0 (hợp lý: hàng đã về, hóa đơn đã có)

Trường hợp 2: **Chưa nhập kho (không có PR)**
Tài khoản chi phí cũng là `"Stock Received But Not Billed"`, nhưng ý nghĩa khác:

```
Nợ  TK "Hàng nhận chưa có hóa đơn"           [giá trị hàng]
Nợ  TK "Thuế GTGT đầu vào"                   [thuế]
Có  TK "Phải trả nhà cung cấp"               [tổng cộng]
```

**Giải thích:** Đây là trường hợp hóa đơn về trước hàng. Tài khoản SRNB tạm thời dùng để theo dõi hàng đang đi đường. Khi Purchase Receipt được tạo sau, nó sẽ:
- Nợ Hàng tồn kho
- Có SRNB (làm giảm SRNB)

Trường hợp 3: **Hóa đơn mua hàng có update_stock = 1**
Khi `update_stock = 1` trong Purchase Invoice, nó đồng thời nhập kho và hạch toán giống như Purchase Receipt:

```
Nợ  TK "Hàng tồn kho - Kho A"                [giá trị]
Nợ  TK "Thuế GTGT đầu vào"                   [thuế]
Có  TK "Phải trả nhà cung cấp"               [tổng cộng]
```

#### 2.5.3. Ví dụ cụ thể: Mua hàng có thuế

**Tình huống:** Mua 100 sp X, đơn giá 50.000đ, thuế GTGT 10%. Cả hàng và hóa đơn về cùng lúc (update_stock = 1).

**Purchase Invoice:**

| Tài khoản | Nợ | Có |
|---|---|---|
| Hàng tồn kho - Kho A | 5.000.000 | |
| Thuế GTGT đầu vào | 500.000 | |
| Phải trả NCC | | 5.500.000 |

#### 2.5.4. Mua tài sản cố định

Khi item là tài sản cố định:
- Sử dụng tài khoản `Fixed Asset` hoặc `CWIP (Construction Work in Progress)` từ Asset Category
- Nếu PR đã hạch toán vào `"Asset Received But Not Billed"`, PI sẽ đảo ngược tài khoản đó

#### 2.5.5. Chiết khấu thuế (Withholding Tax / TDS)

Khi nhà cung cấp có `tax_withholding_category` được cấu hình, ERPNext tự động tính TDS:

```
Nợ  TK "Chi phí / Hàng tồn kho"              [net_total]
Nợ  TK "Thuế GTGT đầu vào"                   [thuế khác]
Có  TK "Phải trả NCC"                        [net_total - TDS + thuế]
Có  TK "Thuế TNCN / TDS phải nộp"            [TDS]
```

#### 2.5.6. Điều chỉnh làm tròn (Precision Loss)

Khi có chênh lệch do làm tròn số thập phân:

```
Nợ  TK "Tài khoản làm tròn"                   [số làm tròn]
Có  TK "Phải trả NCC"                         [số làm tròn]
```

#### 2.5.7. Ghi nhận write-off (Xóa nợ)

```
Nợ  TK "Phải trả NCC"                         [số write-off]
Có  TK "Tài khoản xóa nợ"                     [số write-off]
```

### 2.6. Thanh toán (Payment Entry)

Xem chi tiết ở [Phần 8](#8-thanh-toan-payment-entry--reconciliation).

**Hạch toán cơ bản cho thanh toán NCC:**

```
Nợ  TK "Phải trả NCC"                         [số tiền đã phân bổ]
Có  TK "Tiền gửi Ngân hàng"                   [số tiền đã thanh toán]
```

### 2.7. Hàng mua trả lại / Debit Note

Khi tạo Purchase Invoice với `is_return = 1`:

**Hạch toán đảo ngược:**

```
Nợ  TK "Phải trả NCC"                         [giảm công nợ]
Có  TK "Chi phí / Hàng tồn kho"               [giảm chi phí]
Có  TK "Thuế GTGT đầu vào"                    [giảm thuế khấu trừ]
```

### 2.8. Mua hàng không qua kho (Direct Expense)

Khi mua dịch vụ (tư vấn, bảo hiểm, thuê mướn...) và `update_stock = 0`:

```
Nợ  TK "Chi phí QLDN / Chi phí bán hàng"     [giá trị]
Nợ  TK "Thuế GTGT đầu vào"                   [thuế]
Có  TK "Phải trả NCC"                        [tổng cộng]
```

### 2.9. Mua hàng với Discount

Khi bật `enable_discount_accounting` trong Buying Settings:

**Chiết khấu từng item:**

```
Nợ  TK "Tài khoản chiết khấu"                [số chiết khấu]
Có  TK "Chi phí / Hàng tồn kho"              [số chiết khấu]  --- giảm chi phí
```

**Chiết khấu tổng (Additional Discount):**

```
Có  TK "Tài khoản chiết khấu thêm"           [số chiết khấu]
Nợ  TK "Phải trả NCC"                        [số chiết khấu]  --- giảm công nợ
```

---

## 3. Bán hàng (Order to Cash)

### 3.1. Tổng quan quy trình

```
Sales Order (Đơn đặt hàng)
    | (Không có hạch toán kế toán)
    v
Delivery Note (Xuất kho) --- chỉ khi Kiểm kê vĩnh viễn
    | (Có hạch toán COGS)
    v
Sales Invoice (Hóa đơn bán hàng)
    | (Có hạch toán chính)
    v
Payment Entry (Thu tiền)
```

### 3.2. Đơn bán hàng (Sales Order)

**Không có hạch toán kế toán.** Sales Order chỉ:
- Cập nhật `reserved_qty` trong Bin (đặt trước hàng cho đơn hàng)
- Kiểm tra hạn mức tín dụng (credit limit)
- Tạo project (nếu có)

Không có GL Entry được tạo.

### 3.3. Xuất kho (Delivery Note)

**Chỉ tạo GL Entry khi bật Perpetual Inventory.**

#### 3.3.1. Hạch toán COGS

```
Nợ  TK "Giá vốn hàng bán (COGS)"              [stock_value_difference]
Có  TK "Hàng tồn kho - Kho X"                [stock_value_difference]
```

**Giải thích bản chất:**
- **Nợ COGS:** Giá vốn của hàng hóa đã xuất đi được ghi nhận vào chi phí.
- **Có Hàng tồn kho:** Tài sản kho giảm xuống vì hàng đã xuất cho khách.

**Ví dụ:** Xuất kho A 100 sp X, giá vốn 40.000đ/sp = 4.000.000đ.

```
Nợ  TK "Giá vốn hàng bán"                   4.000.000
Có  TK "Hàng tồn kho - Kho A"              4.000.000
```

#### 3.3.2. Chuyển kho nội bộ (Internal Transfer)

Khi có `target_warehouse`, Delivery Note xử lý như chuyển kho:

```
Nợ  TK "Kho đích"                            [stock_value_difference]
Có  TK "Kho nguồn"                           [stock_value_difference]
```

### 3.4. Hóa đơn bán hàng (Sales Invoice)

Sales Invoice là chứng từ tạo nhiều GL Entry nhất trong quy trình bán hàng.

#### 3.4.1. Hạch toán tổng thể

```
Nợ  TK "Phải thu khách hàng"                  [tổng cộng (gross)]
Có  TK "Doanh thu bán hàng"                   [giá trị hàng]
Có  TK "Thuế GTGT đầu ra"                     [thuế]
```

**Giải thích:**
- **Nợ Phải thu KH:** Khách hàng còn nợ doanh nghiệp số tiền hàng + thuế. Đây là tài sản (Asset).
- **Có Doanh thu:** Ghi nhận doanh thu từ việc bán hàng. Đây là thu nhập (Income).
- **Có Thuế GTGT đầu ra:** Số thuế phải nộp cho Nhà nước. Đây là công nợ (Liability).

#### 3.4.2. Ví dụ cụ thể: Bán hàng chịu

**Tình huống:** Bán 50 sp X, đơn giá 100.000đ, thuế GTGT 10%, chưa thu tiền.

```
Nợ  TK "Phải thu khách hàng"                5.500.000
Có  TK "Doanh thu bán hàng"                 5.000.000
Có  TK "Thuế GTGT đầu ra"                     500.000
```

#### 3.4.3. Khi có Xuất kho (update_stock = 1)

Nếu Sales Invoice có `update_stock = 1`, nó tự động xuất kho và ghi COGS:

```
Nợ  TK "Phải thu khách hàng"                5.500.000
Có  TK "Doanh thu bán hàng"                 5.000.000
Có  TK "Thuế GTGT đầu ra"                     500.000

-- Đồng thời ghi nhận COGS:
Nợ  TK "Giá vốn hàng bán (COGS)"            2.000.000  (50 sp * 40.000)
Có  TK "Hàng tồn kho - Kho A"              2.000.000
```

#### 3.4.4. Doanh thu hoãn lại (Deferred Revenue)

Khi `enable_deferred_revenue = 1`, doanh thu tạm thời chuyển vào tài khoản doanh thu chưa thực hiện:

```
Nợ  TK "Phải thu khách hàng"                5.500.000
Có  TK "Doanh thu chưa thực hiện"           5.000.000
Có  TK "Thuế GTGT đầu ra"                     500.000
```

#### 3.4.5. Bán hàng trả lại / Credit Note

Khi tạo Sales Invoice với `is_return = 1`:

```
   TK "Phải thu KH"          (Có -5.500.000)  --- giá trị âm = giảm phải thu
   TK "Doanh thu"            (Nợ -5.000.000)  --- giá trị âm = giảm doanh thu
   TK "Thuế GTGT đầu ra"     (Nợ -500.000)    --- giá trị âm = giảm thuế
```

Nếu có `update_stock`:
```
Nợ  TK "Hàng tồn kho"                      2.000.000  (hàng nhập lại kho)
Có  TK "Giá vốn hàng bán"                  2.000.000  (giảm COGS)
```

### 3.5. Thu tiền (Payment Entry)

Xem chi tiết ở [Phần 8](#8-thanh-toan-payment-entry--reconciliation).

**Hạch toán cơ bản cho thu tiền từ khách hàng:**

```
Nợ  TK "Tiền gửi Ngân hàng"                  [số tiền nhận được]
Có  TK "Phải thu khách hàng"                 [số tiền phân bổ]
```

### 3.6. Bán hàng với Discount

#### 3.6.1. Chiết khấu từng item

```
Nợ  TK "Tài khoản chiết khấu"               [số chiết khấu]
Có  TK "Doanh thu bán hàng"                 [số chiết khấu]  --- giảm doanh thu
```

#### 3.6.2. Chiết khấu tổng (Additional Discount)

```
Nợ  TK "Tài khoản chiết khấu thêm"          [số chiết khấu]
Có  TK "Phải thu khách hàng"                [số chiết khấu]  --- giảm phải thu
```

### 3.7. POS (Point of Sale)

**Hạch toán POS khi thanh toán bằng tiền mặt:**

```
Nợ  TK "Phải thu khách hàng"                [tổng cộng]
Có  TK "Doanh thu bán hàng"                 [giá trị hàng]
Có  TK "Thuế GTGT đầu ra"                   [thuế]

Nợ  TK "Tiền mặt"                           [số tiền mặt nhận]
Có  TK "Phải thu khách hàng"               [số tiền mặt]
```

### 3.8. Điểm thưởng (Loyalty Points)

Khi khách hàng đổi điểm thưởng:

```
Nợ  TK "Tài khoản điểm thưởng"               [số điểm * tỷ lệ quy đổi]
Có  TK "Phải thu khách hàng"                 [giảm công nợ]
```

---

## 4. Kho & Tồn kho (Inventory)

### 4.1. Hệ thống Kiểm kê vĩnh viễn (Perpetual Inventory)

Khi bật `enable_perpetual_inventory = 1` ở Company, mọi biến động kho đều được ghi nhận GL Entry ngay lập tức.

#### 4.1.1. Cấu hình tài khoản kho

| Tài khoản | Mục đích | Bản chất |
|---|---|---|
| Warehouse Account | Ghi nhận giá trị tồn kho | Tài sản (Asset) |
| Expense Account (COGS) | Ghi nhận giá vốn | Chi phí (Expense) |
| Stock Adjustment Account | Điều chỉnh tồn kho | Chi phí / Thu nhập |
| Stock Received But Not Billed | Công nợ tạm thời | Nợ phải trả (Liability) |

#### 4.1.2. Nguyên tắc hạch toán chung cho mọi biến động kho

```
Nợ  TK "Hàng tồn kho - Kho A"            [stock_value_difference]
Có  TK "Tài khoản chi phí / điều chỉnh"   [stock_value_difference]
```

Nếu giá trị `stock_value_difference` âm (hàng ra khỏi kho): đổi chiều Nợ/Có.

### 4.2. Các loại phiếu kho (Stock Entry)

#### 4.2.1. Nhập kho (Material Receipt)

Hàng từ bên ngoài vào kho, không kèm hóa đơn mua hàng:

```
Nợ  TK "Hàng tồn kho - Kho A"            [giá trị]
Có  TK "Chi phí / Điều chỉnh kho"        [giá trị]
```

#### 4.2.2. Xuất kho (Material Issue)

Hàng xuất khỏi kho để sử dụng nội bộ (sản xuất, tiêu hao):

```
Nợ  TK "Chi phí sản xuất / QLDN"         [giá trị]
Có  TK "Hàng tồn kho - Kho A"            [giá trị]
```

#### 4.2.3. Chuyển kho (Material Transfer)

Chuyển hàng giữa các kho trong cùng công ty:

```
Nợ  TK "Hàng tồn kho - Kho B (đích)"     [giá trị]
Có  TK "Hàng tồn kho - Kho A (nguồn)"    [giá trị]
```

**Không ảnh hưởng đến Báo cáo KQHĐKD (P&L)** — chỉ thay đổi cơ cấu tài sản.

#### 4.2.4. Sản xuất (Manufacture)

Nhập kho thành phẩm, xuất nguyên vật liệu:

```
Nợ  TK "Hàng tồn kho - Kho thành phẩm"   [giá trị thành phẩm]
Có  TK "Hàng tồn kho - Kho NVL"          [giá trị NVL tiêu hao]
Có  TK "Chi phí điều chỉnh"              [chênh lệch (nếu có)]
```

#### 4.2.5. Đóng gói lại (Repack)

Tương tự sản xuất nhưng không có scrap cost adjustment.

#### 4.2.6. Gửi gia công (Send to Subcontractor)

Chuyển NVL sang kho nhà cung cấp gia công:

```
Nợ  TK "Hàng tồn kho - Kho NCC"          [giá trị NVL]
Có  TK "Hàng tồn kho - Kho mình"         [giá trị NVL]
```

#### 4.2.7. Nhận hàng gia công (Subcontracting Receipt)

Khi nhận thành phẩm từ NCC gia công (dùng doctype riêng: Subcontracting Receipt):

```
Nợ  TK "Hàng tồn kho - Kho thành phẩm"   [giá trị = NVL + phí gia công]
Có  TK "Hàng tồn kho - Kho NCC"          [giá trị NVL đã tiêu hao]
Có  TK "Chi phí (COGS)"                  [chênh lệch]
```

### 4.3. Nhập kho đầu kỳ (Opening Stock)

Dùng Stock Entry với purpose = "Opening Stock":

```
Nợ  TK "Hàng tồn kho - Kho A"            [giá trị tồn đầu kỳ]
Có  TK "Tài khoản bảng CĐKT"              [giá trị tồn đầu kỳ]
```

**Lưu ý quan trọng:** Tài khoản đối ứng phải là **Balance Sheet** account (không phải P&L) vì đây là số dư đầu kỳ, không phải chi phí.

### 4.4. Kiểm kê kho (Stock Reconciliation)

Khi phát hiện chênh lệch giữa sổ sách và thực tế:

**Nếu giá trị tồn kho tăng:**
```
Nợ  TK "Hàng tồn kho - Kho A"            [chênh lệch]
Có  TK "Điều chỉnh kho"                   [chênh lệch]
```

**Nếu giá trị tồn kho giảm:**
```
Nợ  TK "Điều chỉnh kho"                   [chênh lệch]
Có  TK "Hàng tồn kho - Kho A"            [chênh lệch]
```

### 4.5. Phương pháp tính giá (Valuation Method)

#### 4.5.1. FIFO (First In, First Out)

- Hàng nhập trước được xuất trước
- Khi xuất kho, giá trị lấy từ lớp (layer) nhập đầu tiên trong queue
- Hàng tồn cuối kỳ phản ánh giá của những lô nhập gần nhất

**Cách hoạt động của FIFO queue:**
- Nhập 10 sp * 10.000đ = queue: [[10, 10000]]
- Nhập 10 sp * 12.000đ = queue: [[10, 10000], [10, 12000]]
- Xuất 8 sp = pop 8 từ front: 8 * 10.000đ = 80.000đ, queue còn: [[2, 10000], [10, 12000]]
- Nhập 5 sp * 11.000đ = queue: [[2, 10000], [10, 12000], [5, 11000]]

#### 4.5.2. Moving Average (Bình quân di động)

- Mỗi lần nhập, giá trị trung bình được tính lại:
  `new_rate = (old_qty * old_rate + incoming_qty * incoming_rate) / new_qty`
- Khi xuất, giá xuất = giá trung bình hiện tại
- Không duy trì queue như FIFO

#### 4.5.3. Ảnh hưởng đến GL Entry

**FIFO**: COGS phản ánh giá thực tế của từng lớp hàng xuất.
**Moving Average**: COGS phản ánh giá bình quân tại thời điểm xuất.

### 4.6. Hàng có Serial No & Batch

#### 4.6.1. Hàng có Serial No

- Mỗi sản phẩm theo dõi riêng lẻ (Serial No)
- Khi nhập: `stock_value_difference = qty * incoming_rate`
- Khi xuất: giá trị lấy từ `purchase_rate` của từng Serial No

**GL Entry vẫn giống tổng quát** — không có tài khoản riêng cho Serial. Chỉ khác ở cách tính `stock_value_difference`.

#### 4.6.2. Hàng có Batch và định giá theo Batch

Khi `Batch.use_batchwise_valuation = 1`:
- Mỗi batch có giá riêng (bình quân di động riêng cho từng batch)
- Khi xuất: giá xuất = giá bình quân của batch cụ thể đó

---

## 5. Phân bổ chi phí — Landed Cost Voucher

### 5.1. Mục đích

Khi mua hàng nhập khẩu hoặc mua hàng có các chi phí phát sinh thêm (vận chuyển, bảo hiểm, hải quan, kiểm định...), các chi phí này cần được **phân bổ vào giá trị hàng tồn kho** (vốn hóa vào tài sản), không phải ghi nhận là chi phí trong kỳ.

### 5.2. Cấu hình

**Landed Cost Voucher** có các trường:
- Purchase Receipt: chọn PR cần phân bổ
- Purchase Invoice: hoặc chọn PI (nếu chưa có PR)
- Taxes and Charges: bảng chi phí (tên chi phí, tài khoản, số tiền)
- `distribute_charges_based_on`: Amount (theo giá trị), Quantity (theo số lượng), hoặc Distribute Manually

### 5.3. Cách tính phân bổ

Công thức:
```
item.applicable_charges = item.{based_on_field} * (tổng_chi_phí / tổng_cơ_sở_phân_bổ)
```

- **Theo Amount**: dựa trên tỷ trọng giá trị từng item trong tổng giá trị lô hàng
- **Theo Quantity**: dựa trên tỷ trọng số lượng từng item
- **Thủ công**: người dùng tự nhập

Item cuối cùng hấp thụ phần chênh lệch làm tròn.

### 5.4. Hạch toán chi tiết

Khi Landed Cost Voucher được submit, nó thực hiện theo trình tự:

1. **Hủy Purchase Receipt** (docstatus = 2) — đảo ngược tất cả GL và SL entries cũ
2. **Tính toán lại valuation_rate** mới:
   `valuation_rate = (base_net_amount + item_tax_amount + landed_cost_voucher_amount) / stock_qty`
3. **Submit lại Purchase Receipt** (docstatus = 1) — tạo GL và SL entries mới với giá trị đã cập nhật

**GL Entries từ LCV (qua Purchase Receipt được re-submit):**

**Phân bổ chi phí vào kho:**
```
Nợ  TK "Hàng tồn kho"                      [giá trị cũ + chi phí LC]
Có  TK "Phải trả NCC / Stock Received But Not Billed"   [giá trị cũ]
Có  TK "Chi phí vận chuyển / Hải quan"     [chi phí LC phân bổ]
```

**Hoặc trực tiếp hơn:**

Khoản chi phí phân bổ được ghi như một credit bổ sung vào tài khoản chi phí tương ứng:

```
Có  TK "Chi phí vận chuyển"                [số tiền LC phân bổ]
```

Điều này làm tăng giá trị hàng tồn kho (vì debit vào warehouse account tăng lên tương ứng).

### 5.5. Ví dụ cụ thể

**Tình huống:** Mua 2 loại hàng:
- Sp A: 100 cái * 50.000đ = 5.000.000đ
- Sp B: 50 cái * 100.000đ = 5.000.000đ
- Chi phí vận chuyển: 1.000.000đ
- Phân bổ theo Amount

**Tính toán:**
- Tổng giá trị: 10.000.000đ
- Sp A: 5.000.000/10.000.000 = 50% → 500.000đ
- Sp B: 5.000.000/10.000.000 = 50% → 500.000đ

**GL Entry sau LCV:**

Purchase Receipt được re-submit với giá trị mới:

Sp A: giá trị kho = 5.000.000 + 500.000 = 5.500.000đ
Sp B: giá trị kho = 5.000.000 + 500.000 = 5.500.000đ

```
Nợ  TK "Hàng tồn kho - Kho A (Sp A)"        5.500.000
Nợ  TK "Hàng tồn kho - Kho B (Sp B)"        5.500.000
Có  TK "Hàng nhận chưa có hóa đơn"          10.000.000  (giá gốc)
Có  TK "Chi phí vận chuyển"                  1.000.000  (chi phí LC)
```

### 5.6. Ảnh hưởng đến báo cáo

- **Trước LCV:** Hàng tồn kho = 10.000.000đ (chưa bao gồm chi phí vận chuyển)
- **Sau LCV:** Hàng tồn kho = 11.000.000đ (đã vốn hóa chi phí vận chuyển)
- Chi phí vận chuyển **không xuất hiện trên P&L** vì đã được vốn hóa vào tài sản

### 5.7. Quan hệ với Purchase Invoice

Landed Cost Voucher có thể liên kết với Purchase Invoice (nếu chưa có Purchase Receipt). Khi PI có LCV:
- Trong `make_item_gl_entries()` của PI, một credit entry bổ sung được tạo cho tài khoản chi phí LC
- Điều này đảm bảo chi phí LC được phản ánh đúng trong giá vốn sau này

---

## 6. Doanh thu & Chi phí hoãn lại (Deferred Accounting)

### 6.1. Bản chất kế toán của Deferred

**Nguyên tắc cơ sở dồn tích (Accrual Basis):** Doanh thu và chi phí phải được ghi nhận vào đúng kỳ mà dịch vụ được thực hiện, không phải thời điểm xuất hóa đơn hay nhận tiền.

**Khi nào cần Deferred:**
- Bán gói dịch vụ trả trước (bảo hành, bảo trì, thuê nhà 12 tháng)
- Mua dịch vụ trả trước (thuê văn phòng, thuê bao SaaS)

### 6.2. Doanh thu hoãn lại (Deferred Revenue) — Sales Invoice

#### 6.2.1. Cấu hình

Item có `enable_deferred_revenue = 1` với:
- `service_start_date` — ngày bắt đầu cung cấp dịch vụ
- `service_end_date` — ngày kết thúc cung cấp dịch vụ
- `deferred_revenue_account` — tài khoản doanh thu chưa thực hiện (Liability)

#### 6.2.2. Hạch toán tại thời điểm xuất hóa đơn

Khi Sales Invoice được submit với deferred revenue:

```
Nợ  TK "Phải thu khách hàng"                [tổng hóa đơn]
Có  TK "Doanh thu chưa thực hiện"           [giá trị hàng]  (thay vì Doanh thu)
Có  TK "Thuế GTGT đầu ra"                   [thuế]
```

**Giải thích bản chất:**
Doanh thu chưa thực hiện là tài khoản **Nợ phải trả (Liability)**. Tại sao là nợ phải trả?
- Doanh nghiệp đã nhận được quyền đòi tiền (hoặc đã nhận tiền) nhưng chưa thực hiện dịch vụ
- Doanh nghiệp đang **nợ khách hàng** N tháng dịch vụ
- Nếu không thực hiện, phải trả lại tiền

#### 6.2.3. Hạch toán hàng tháng (quá trình ghi nhận)

Quá trình này chạy qua **Process Deferred Accounting** (tự động hàng tháng hoặc thủ công).

**Hàng tháng, khi một phần dịch vụ đã được thực hiện:**

```
Nợ  TK "Doanh thu chưa thực hiện"           [số tiền phân bổ]
Có  TK "Doanh thu bán hàng"                 [số tiền phân bổ]
```

**Ví dụ:** Bán gói bảo trì 12 tháng giá 120 triệu, xuất hóa đơn 01/01/2026.

Thời điểm xuất hóa đơn (01/01/2026):
```
Nợ  TK "Phải thu KH"                      120.000.000
Có  TK "Doanh thu chưa thực hiện"         120.000.000
```

Hàng tháng (31/01, 28/02, 31/03...):
```
Nợ  TK "Doanh thu chưa thực hiện"          10.000.000
Có  TK "Doanh thu bán hàng"               10.000.000
```

Sau 12 tháng, tài khoản "Doanh thu chưa thực hiện" = 0.

### 6.3. Chi phí hoãn lại (Deferred Expense) — Purchase Invoice

#### 6.3.1. Cấu hình

Item có `enable_deferred_expense = 1` với:
- `service_start_date` — ngày bắt đầu nhận dịch vụ
- `service_end_date` — ngày kết thúc nhận dịch vụ
- `deferred_expense_account` — tài khoản chi phí trả trước (Asset)

#### 6.3.2. Hạch toán tại thời điểm nhận hóa đơn

Khi Purchase Invoice được submit với deferred expense:

```
Nợ  TK "Chi phí trả trước"                 [giá trị hàng]  (thay vì Chi phí)
Nợ  TK "Thuế GTGT đầu vào"                 [thuế]
Có  TK "Phải trả NCC"                      [tổng hóa đơn]
```

**Giải thích bản chất:**
Chi phí trả trước là tài khoản **Tài sản (Asset)**. Tại sao là tài sản?
- Doanh nghiệp đã trả tiền (hoặc có nghĩa vụ trả tiền) trước khi nhận dịch vụ
- Doanh nghiệp có **quyền được sử dụng dịch vụ** trong N tháng tới
- Đây là một lợi ích kinh tế trong tương lai → tài sản

#### 6.3.3. Hạch toán hàng tháng (quá trình phân bổ)

**Hàng tháng, khi một phần dịch vụ đã được sử dụng:**

```
Nợ  TK "Chi phí QLDN / Chi phí bán hàng"   [số tiền phân bổ]
Có  TK "Chi phí trả trước"                  [số tiền phân bổ]
```

**Ví dụ:** Thuê văn phòng 12 tháng giá 240 triệu, hóa đơn 01/01/2026.

Thời điểm nhận hóa đơn (01/01/2026):
```
Nợ  TK "Chi phí trả trước (242)"          240.000.000
Có  TK "Phải trả NCC"                     240.000.000
```

Hàng tháng (31/01, 28/02...):
```
Nợ  TK "Chi phí QLDN"                      20.000.000
Có  TK "Chi phí trả trước (242)"            20.000.000
```

Sau 12 tháng, tài khoản "Chi phí trả trước" = 0.

### 6.4. Cách tính số tiền phân bổ

ERPNext hỗ trợ 2 phương pháp:

#### 6.4.1. Theo ngày (Days-based)

```
base_amount = item.base_net_amount * số_ngày_trong_kỳ / tổng_số_ngày_dịch_vụ
```

Phân bổ đều theo số ngày thực tế của từng kỳ.

#### 6.4.2. Theo tháng (Months-based)

```
total_months = (số tháng từ start đến end)
prorate_factor = số_ngày_trong_kỳ / tổng_số_ngày_trong_tháng
actual_months = làm_tròn(total_months * prorate_factor)
base_amount = item.base_net_amount / actual_months
```

Kỳ cuối cùng luôn được tính là phần còn lại để tránh sai số làm tròn.

### 6.5. Xử lý đặc biệt

#### 6.5.1. Service Stop Date

Nếu item có `service_stop_date` (ngày kết thúc sớm), quá trình ghi nhận dừng lại tại ngày này. Các kỳ sau không được ghi nhận nữa.

#### 6.5.2. Đóng băng kỳ kế toán (`acc_frozen_upto`)

Nếu ngày ghi nhận rơi vào kỳ đã đóng băng, hệ thống tự động postpone sang kỳ tiếp theo.

#### 6.5.3. Hủy (Cancel)

Các GL entries đã tạo từ deferred sẽ được đảo ngược.

### 6.6. Cấu hình tại Accounts Settings

- `book_deferred_entries_via_journal_entry`: Nếu = 1, tạo Journal Entry thay vì GL Entry trực tiếp
- `submit_journal_entries`: Nếu = 1, tự động submit JE
- `book_deferred_entries_based_on`: "Days" hoặc "Months"
- `automatically_process_deferred_accounting_entry`: Bật/tắt tự động chạy deferred hàng tháng

### 6.7. Hạch toán khi dùng Journal Entry

**Ví dụ Deferred Revenue — Journal Entry (tháng 1, 10.000.000đ):**

| JE | Tài khoản | Nợ | Có | Tham chiếu |
|---|---|---|---|---|
| JE-2026-0001 | Doanh thu chưa thực hiện | 10.000.000 | | SI-2026-0001 |
| JE-2026-0001 | Doanh thu bán hàng | | 10.000.000 | SI-2026-0001 |

**Ví dụ Deferred Expense — Journal Entry (tháng 1, 20.000.000đ):**

| JE | Tài khoản | Nợ | Có | Tham chiếu |
|---|---|---|---|---|
| JE-2026-0001 | Chi phí QLDN | 20.000.000 | | PI-2026-0001 |
| JE-2026-0001 | Chi phí trả trước | | 20.000.000 | PI-2026-0001 |

---

## 7. Thuế (Tax Accounting)

### 7.1. Phân loại thuế trong ERPNext

Thuế trong ERPNext được quản lý qua **Sales Taxes and Charges** (cho bán hàng) và **Purchase Taxes and Charges** (cho mua hàng). Mỗi dòng thuế có các trường:

| Trường | Ý nghĩa |
|---|---|
| `category` | "Total" (vào P&L), "Valuation" (vào giá trị kho), "Valuation and Total" (cả hai) |
| `add_deduct_tax` | "Add" (cộng thêm), "Deduct" (trừ đi) |
| `charge_type` | Cách tính: "Actual", "On Net Total", "On Previous Row Amount", v.v. |
| `account_head` | Tài khoản kế toán cho thuế này |

### 7.2. Thuế đầu ra (Output Tax) — Bán hàng

#### 7.2.1. Bản chất

Thuế GTGT đầu ra là khoản thuế doanh nghiệp thu hộ Nhà nước từ khách hàng. Doanh nghiệp có trách nhiệm nộp lại cho Nhà nước.

**Tài khoản thuế đầu ra phải là tài khoản Liability (Nợ phải trả).**

#### 7.2.2. Hạch toán trên Sales Invoice

Khi xuất hóa đơn bán hàng:

```
Nợ  TK "Phải thu khách hàng"                [tổng hóa đơn gồm cả thuế]
Có  TK "Doanh thu bán hàng"                 [giá trị không thuế]
Có  TK "Thuế GTGT đầu ra"                   [số thuế]
```

**Ví dụ:** Bán hàng 10.000.000đ, thuế GTGT 10% = 1.000.000đ.

```
Nợ  TK "Phải thu KH"                       11.000.000
Có  TK "Doanh thu bán hàng"                10.000.000
Có  TK "Thuế GTGT đầu ra"                   1.000.000
```

**Giải thích:** Tài khoản thuế đầu ra được Có (tăng lên) — đây là khoản nợ phải trả cho Nhà nước.

#### 7.2.3. Khi hủy hóa đơn / Credit Note

Đảo ngược: ghi Nợ vào tài khoản thuế đầu ra (giảm nợ phải trả).

### 7.3. Thuế đầu vào (Input Tax) — Mua hàng

#### 7.3.1. Bản chất

Thuế GTGT đầu vào là khoản thuế doanh nghiệp đã trả khi mua hàng. Doanh nghiệp được khấu trừ (trừ vào) số thuế đầu ra phải nộp.

**Tài khoản thuế đầu vào có thể là Asset (Tài sản — thuế được khấu trừ) hoặc Expense (Chi phí — thuế không được khấu trừ).**

#### 7.3.2. Hạch toán trên Purchase Invoice

Khi nhận hóa đơn mua hàng:

```
Nợ  TK "Chi phí / Hàng tồn kho"            [giá trị không thuế]
Nợ  TK "Thuế GTGT đầu vào"                 [số thuế]
Có  TK "Phải trả NCC"                      [tổng hóa đơn gồm cả thuế]
```

**Ví dụ:** Mua hàng 10.000.000đ, thuế GTGT 10% = 1.000.000đ.

```
Nợ  TK "Hàng tồn kho"                      10.000.000
Nợ  TK "Thuế GTGT đầu vào"                  1.000.000
Có  TK "Phải trả NCC"                      11.000.000
```

**Giải thích:** Tài khoản thuế đầu vào được Nợ (tăng lên) — đây là tài sản (doanh nghiệp sẽ được khấu trừ sau này).

#### 7.3.3. Thuế đầu vào và hàng tồn kho

Khi thuế có `category = "Valuation"`, thuế được vốn hóa vào giá trị hàng tồn kho:

```
Nợ  TK "Hàng tồn kho"                      [giá trị gồm cả thuế]
Nợ  TK "Thuế GTGT đầu vào"                 [thuế (nếu được khấu trừ)]
Có  TK "Phải trả NCC"                      [tổng cộng]
```

### 7.4. Khấu trừ thuế (Withholding Tax / TDS)

#### 7.4.1. Cấu hình

Tax Withholding Category xác định:
- `account_head` — Tài khoản TDS phải nộp (Liability)
- `rate` — Tỷ lệ khấu trừ
- Ngưỡng áp dụng (thresholds)

#### 7.4.2. Hạch toán trên Purchase Invoice

Khi mua hàng từ NCC bị khấu trừ thuế:

```
Nợ  TK "Chi phí / Hàng tồn kho"            [net_total]
Nợ  TK "Thuế GTGT đầu vào"                 [thuế]
Nợ  TK "Phải trả NCC" (giảm)              [TDS]
Có  TK "Phải trả NCC"                      [net_total - TDS + thuế]
Có  TK "Thuế TNCN/TDS phải nộp"            [TDS]
```

**Ví dụ:** Mua 10.000.000đ, thuế GTGT 10%, TDS 5%.

```
Nợ  TK "Chi phí"                           10.000.000
Nợ  TK "Thuế GTGT đầu vào"                  1.000.000
Có  TK "Phải trả NCC"                      10.500.000
Có  TK "TDS phải nộp"                         500.000    (= 10.000.000 * 5%)
```

Doanh nghiệp chỉ trả NCC 10.500.000đ (thay vì 11.000.000đ) vì 500.000đ đã được khấu trừ và nộp thẳng cho Nhà nước.

#### 7.4.3. Khi thanh toán (Payment Entry with TDS)

```
Nợ  TK "TDS phải nộp"                      [số TDS]
Có  TK "Tiền gửi Ngân hàng"                [số TDS]
```

### 7.5. Thuế trên Advances (TDS/TCS)

Khi thanh toán tạm ứng cho NCC, TDS vẫn được tính. Hệ thống:
1. Tính TDS trên số tiền tạm ứng
2. Khi hóa đơn chính thức được tạo, TDS đã khấu trừ từ advance được phân bổ vào hóa đơn

---

## 8. Thanh toán (Payment Entry & Reconciliation)

### 8.1. Payment Entry — các loại

| Loại | Mục đích | Bản chất |
|---|---|---|
| **Receive** | Thu tiền từ khách hàng | Giảm phải thu, tăng tiền |
| **Pay** | Trả tiền cho nhà cung cấp | Giảm phải trả, giảm tiền |
| **Internal Transfer** | Chuyển tiền giữa các tài khoản | Tài sản này tăng, tài sản kia giảm |

### 8.2. Hạch toán chi tiết

#### 8.2.1. Thu tiền từ khách hàng (Receive)

**Hạch toán cơ bản:**

```
Nợ  TK "Tiền gửi NH / Tiền mặt"             [số tiền nhận được]
Có  TK "Phải thu khách hàng"                [số tiền phân bổ cho hóa đơn]
```

**Giải thích bản chất:**
- **Nợ Tiền:** Tài sản tăng lên (tiền về tài khoản ngân hàng)
- **Có Phải thu KH:** Tài sản giảm xuống (khách hàng đã trả nợ)

**Nếu có unallocated amount (tiền thừa chưa phân bổ):**

```
Nợ  TK "Tiền gửi NH"                        [tổng tiền nhận]
Có  TK "Phải thu KH"                        [phân bổ cho hóa đơn 1]
Có  TK "Phải thu KH"                        [phân bổ cho hóa đơn 2]
Có  TK "Phải thu KH"                        [unallocated amount — tạm thời]
```

#### 8.2.2. Trả tiền cho NCC (Pay)

```
Nợ  TK "Phải trả NCC"                       [số tiền phân bổ]
Có  TK "Tiền gửi NH"                        [số tiền đã trả]
```

**Giải thích bản chất:**
- **Nợ Phải trả NCC:** Nợ phải trả giảm (đã trả bớt nợ cho NCC)
- **Có Tiền:** Tài sản giảm (tiền ra khỏi ngân hàng)

#### 8.2.3. Chuyển tiền nội bộ (Internal Transfer)

```
Nợ  TK "TK NH đích"                         [số tiền nhận]
Có  TK "TK NH nguồn"                        [số tiền chuyển]
```

Không ảnh hưởng đến P&L.

### 8.3. Các khoản khấu trừ (Deductions)

Khi thanh toán có phí (phí ngân hàng, hoa hồng...):

```
Nợ  TK "Phải trả NCC"                       [phân bổ]
Nợ  TK "Phí ngân hàng"                      [phí]
Có  TK "Tiền gửi NH"                        [tổng tiền trả]
```

### 8.4. Unallocated Amount

Khi nhận tiền từ khách hàng nhưng chưa xác định sẽ trừ vào hóa đơn nào:
- Số tiền này tạm thời nằm ở tài khoản Phải thu KH (Credit balance)
- Khi thực hiện **Payment Reconciliation**, nó sẽ được phân bổ vào các hóa đơn cụ thể

### 8.5. Payment Reconciliation vs Payment Entry

| | Payment Entry | Payment Reconciliation |
|---|---|---|
| Bản chất | Ghi nhận luồng tiền thực tế | Công cụ phân bổ số dư |
| Tạo GL Entry? | Có (trực tiếp) | Không (chỉ cập nhật tham chiếu) |
| Khi nào dùng | Khi có giao dịch ngân hàng | Khi cần match payment với invoice |

**Payment Reconciliation hoạt động:**
1. Hủy (cancel) Payment Entry / Journal Entry cũ
2. Cập nhật tham chiếu (link tới hóa đơn cụ thể)
3. Submit lại — GL Entry được tạo lại với tham chiếu mới

### 8.6. Xóa nợ (Write-off)

Khi khách hàng không thể thanh toán toàn bộ:

```
Nợ  TK "Phải thu KH"                        [giảm phải thu]
Có  TK "Chi phí xóa nợ"                     [tăng chi phí]
```

Hoặc trên Payment Entry:
```
Nợ  TK "Phải thu KH"                        [allocated amount]
Nợ  TK "Xóa nợ"                            [write-off amount]
Có  TK "Tiền gửi NH"                        [tổng tiền nhận thực tế]
```

---

## 9. Nhiều tiền tệ & Tỷ giá (Multi-currency & FX)

### 9.1. Tổng quan

ERPNext hỗ trợ đầy đủ giao dịch đa tiền tệ:
- Hóa đơn bán/mua bằng ngoại tệ
- Thanh toán bằng ngoại tệ
- Đánh giá lại số dư ngoại tệ cuối kỳ

**Các khái niệm chính:**
- **Transaction Currency:** Tiền tệ của giao dịch (ví dụ USD)
- **Company Currency:** Tiền tệ hạch toán của công ty (ví dụ VND)
- **conversion_rate:** Tỷ giá quy đổi (số lượng company currency / 1 transaction currency)
- **base_grand_total:** Tổng số bằng company currency (= grand_total * conversion_rate)
- **grand_total:** Tổng số bằng transaction currency

### 9.2. Hạch toán hóa đơn bằng ngoại tệ

#### 9.2.1. Sales Invoice bằng USD (Company currency = VND)

**Tình huống:** Bán hàng 1.000 USD, tỷ giá 25.000 VND/USD, thuế 10%.

```
Nợ  TK "Phải thu KH" - USD           1.100 USD / 27.500.000 VND
Có  TK "Doanh thu"                   1.000 USD / 25.000.000 VND
Có  TK "Thuế GTGT đầu ra"              100 USD /  2.500.000 VND
```

GL Entry lưu cả 2 giá trị:
- `debit/credit`: giá trị bằng VND (company currency)
- `debit_in_account_currency / credit_in_account_currency`: giá trị bằng USD

#### 9.2.2. Purchase Invoice bằng USD

```
Nợ  TK "Chi phí / Hàng tồn kho"             1.000 USD / 25.000.000 VND
Nợ  TK "Thuế GTGT đầu vào"                    100 USD /  2.500.000 VND
Có  TK "Phải trả NCC" - USD                1.100 USD / 27.500.000 VND
```

### 9.3. Thanh toán bằng ngoại tệ — phát sinh lãi/lỗ tỷ giá

#### 9.3.1. Bản chất

Khi tỷ giá tại thời điểm thanh toán khác với tỷ giá tại thời điểm xuất hóa đơn, chênh lệch phát sinh — gọi là **lãi/lỗ tỷ giá thực tế (Realized FX Gain/Loss)**.

**Ví dụ:**
- Hóa đơn bán 1.000 USD, tỷ giá 25.000 → 25.000.000 VND
- Khách hàng thanh toán sau 30 ngày, tỷ giá lúc đó 25.500
- Khách hàng trả 1.000 USD = 25.500.000 VND

**Hạch toán thu tiền:**

```
Nợ  TK "Tiền gửi NH - USD"            1.000 USD / 25.500.000 VND
Có  TK "Phải thu KH"                   1.000 USD / 25.000.000 VND  (giá trị invoice)
Có  TK "Lãi tỷ giá"                                      500.000 VND
```

**Giải thích:**
- Chênh lệch 500.000 VND (25.500.000 - 25.000.000) là lãi tỷ giá
- Đây là thu nhập tài chính (do đồng VND mất giá so với USD)

**Ngược lại, nếu tỷ giá giảm:**

```
Nợ  TK "Tiền gửi NH - USD"            1.000 USD / 24.500.000 VND
Nợ  TK "Lỗ tỷ giá"                                       500.000 VND
Có  TK "Phải thu KH"                   1.000 USD / 25.000.000 VND
```

#### 9.3.2. Cách ERPNext tính lãi/lỗ tỷ giá

ERPNext so sánh:
- `base_allocated_amount` = `allocated_amount * tỷ_giá_thanh_toán`
- `allocated_amount_in_pe_exchange_rate` = `allocated_amount * tỷ_giá_hóa_đơn`

Chênh lệch = `base_allocated_amount - allocated_amount_in_pe_exchange_rate`

Journal Entry được tạo tự động với `voucher_type = "Exchange Gain Or Loss"`:

```
Nợ/Có  TK "Phải thu KH" / "Phải trả NCC"   [chênh lệch]
Có/Nợ  TK "Lãi/Lỗ tỷ giá"                   [chênh lệch]
```

### 9.4. Đánh giá lại tỷ giá cuối kỳ (Exchange Rate Revaluation)

#### 9.4.1. Mục đích

Cuối kỳ (tháng/quý/năm), các số dư tài khoản có gốc ngoại tệ cần được đánh giá lại theo tỷ giá cuối kỳ. Phần chênh lệch là **lãi/lỗ tỷ giá chưa thực hiện (Unrealized FX Gain/Loss)**.

#### 9.4.2. Phạm vi áp dụng

Tất cả tài khoản **Balance Sheet** có `account_currency != company_currency`, ngoại trừ tài khoản loại "Stock".

Bao gồm:
- Phải thu khách hàng (Receivables)
- Phải trả nhà cung cấp (Payables)
- Tiền gửi ngân hàng ngoại tệ
- Các tài khoản Bảng CĐKT khác có ngoại tệ

#### 9.4.3. Cách tính

```
current_exchange_rate = current_balance (VND) / balance_in_account_currency (USD)
new_exchange_rate = tỷ giá cuối kỳ
new_balance = balance_in_account_currency * new_exchange_rate
gain_loss = new_balance - current_balance
```

#### 9.4.4. Hạch toán

Hai loại Journal Entry:

**(A) Revaluation Journal (số dư khác 0 ở cả 2 loại tiền):**

```
Dòng 1: TK "Phải thu KH - USD"               [balance_in_AC] @ tỷ giá mới (Nợ)
Dòng 2: TK "Phải thu KH - USD"               [balance_in_AC] @ tỷ giá cũ (Có)
Dòng 3: TK "Lãi/Lỗ tỷ giá chưa thực hiện"    [gain/loss] (cân bằng)
```

Dòng 1 và 2 triệt tiêu nhau ở số dư ngoại tệ, nhưng chênh lệch về VND tạo ra gain/loss ở dòng 3.

**(B) Zero Balance Journal (số dư = 0 ở 1 bên):**

Khi tài khoản có số dư VND nhưng số dư ngoại tệ = 0 (hoặc ngược lại):

```
Dòng 1: TK "Phải thu KH - USD"               [balance_in_VND] (xóa số dư)
Dòng 2: TK "Lãi/Lỗ tỷ giá chưa thực hiện"    [gain/loss]
```

#### 9.4.5. Tài khoản sử dụng

| Loại | Tài khoản | Khi nào |
|---|---|---|
| Realized Gain/Loss | `exchange_gain_loss_account` | Khi thanh toán thực tế |
| Unrealized Gain/Loss | `unrealized_exchange_gain_loss_account` | Khi đánh giá lại cuối kỳ |

Unrealized entries sẽ được đảo ngược khi hóa đơn được thanh toán thực tế.

### 9.5. Ví dụ tổng hợp: Toàn bộ vòng đời hóa đơn ngoại tệ

**Tình huống:**
- 01/01/2026: Bán hàng 1.000 USD, tỷ giá 25.000, chưa thu tiền
- 31/01/2026: Đánh giá lại cuối tháng, tỷ giá 25.200
- 15/02/2026: Khách thanh toán 1.000 USD, tỷ giá 25.100

**Bước 1 — 01/01: Xuất hóa đơn**
```
Nợ  TK "Phải thu KH"        1.000 USD / 25.000.000 VND
Có  TK "Doanh thu"          1.000 USD / 25.000.000 VND
```

**Bước 2 — 31/01: Đánh giá lại (tỷ giá mới 25.200)**
```
Số dư Phải thu KH: 1.000 USD * 25.200 = 25.200.000 VND
Lãi chưa thực hiện: 25.200.000 - 25.000.000 = 200.000 VND

Nợ  TK "Phải thu KH"                                   200.000 VND
Có  TK "Lãi tỷ giá chưa thực hiện"                     200.000 VND
```

**Bước 3 — 15/02: Khách thanh toán**
```
Số tiền nhận: 1.000 USD * 25.100 = 25.100.000 VND
Giá trị sổ sách: 25.200.000 VND (sau revaluation)
Lỗ thực tế: 25.100.000 - 25.200.000 = -100.000 VND

Trước hết, đảo ngược unrealized entry:
Nợ  TK "Lãi tỷ giá chưa thực hiện"                     200.000 VND
Có  TK "Phải thu KH"                                   200.000 VND

Sau đó, ghi nhận thanh toán và realized gain/loss:
Nợ  TK "Tiền gửi NH"        1.000 USD / 25.100.000 VND
Nợ  TK "Lỗ tỷ giá"                                     100.000 VND
Có  TK "Phải thu KH"        1.000 USD / 25.000.000 VND
```

---

## 10. Mua bán nội bộ (Inter-company)

### 10.1. Tổng quan

Mua bán nội bộ (Inter-company transaction) là giao dịch giữa các công ty trong cùng tập đoàn. ERPNext hỗ trợ tự động tạo chứng từ đối ứng.

**Nguyên tắc:**
- Công ty A (bán) và Công ty B (mua) phải có **cùng loại tiền tệ** (validation bắt buộc)
- Mỗi bên hạch toán độc lập theo sổ sách của mình
- Giao dịch nội bộ cần được loại trừ khi lập báo cáo hợp nhất

### 10.2. Quy trình

```
Công ty A (Bán)                          Công ty B (Mua)
===============                          ===============

Sales Invoice (SI)  <---inter-company---> Purchase Invoice (PI)
  - Internal Customer = Cty B              - Internal Supplier = Cty A
  - represents_company = Cty B             - represents_company = Cty A
```

**Hoặc:**

```
Sales Order (SO) <---inter-company---> Purchase Order (PO)
  - Đơn hàng nội bộ                        - Đơn hàng nội bộ
```

### 10.3. Hạch toán bên Bán (Sales Invoice — Công ty A)

Khi Công ty A bán hàng cho Công ty B (internal customer), `is_internal_transfer()` trả về True nếu:
- `is_internal_supplier = 1` (với Purchase Invoice) hoặc
- `represents_company = company`

**Với is_internal_transfer = True:**

**(A) Không ghi nhận doanh thu từ item:**

Dòng `if not self.is_internal_transfer()` trong Sales Invoice bỏ qua việc ghi nhận income account cho item:

```
Bỏ qua: Có  TK "Doanh thu"       [item amount]
```

**(B) Vẫn ghi nhận phải thu khách hàng:**

```
Nợ  TK "Phải thu KH - Cty B"               [tổng hóa đơn]
```

**(C) Ghi nhận Unrealized Profit thông qua thuế/ship:**

```
Nợ  TK "Lợi nhuận chưa thực hiện (nội bộ)"     [tổng thuế + phí]
Có  TK "Phải thu KH - Cty B"                     [tổng thuế + phí]
```

### 10.4. Hạch toán bên Mua (Purchase Invoice — Công ty B)

Công ty B nhận hóa đơn từ Công ty A:

```
Nợ  TK "Hàng tồn kho / Chi phí"            [giá trị hàng]
Nợ  TK "Thuế GTGT đầu vào"                 [thuế]
Có  TK "Phải trả NCC - Cty A"              [tổng hóa đơn]
```

Nếu là hàng chuyển kho nội bộ (có từ_warehouse / đến_warehouse):

```
Nợ  TK "Hàng tồn kho - Kho nhận"
Có  TK "Hàng tồn kho - Kho chuyển"
```

### 10.5. Loại trừ nội bộ khi hợp nhất báo cáo

Khi lập báo cáo hợp nhất (Consolidated Financial Statements), các giao dịch nội bộ cần được loại trừ:

1. **Doanh thu nội bộ**: Loại trừ doanh thu của Cty A với chi phí tương ứng của Cty B
2. **Phải thu / Phải trả nội bộ**: Loại trừ số dư phải thu KH (Cty A) với phải trả NCC (Cty B)
3. **Lợi nhuận chưa thực hiện**: Nếu hàng tồn kho của Cty B chưa bán ra ngoài, lợi nhuận nội bộ phải được loại trừ

ERPNext hỗ trợ báo cáo hợp nhất qua:
- **Consolidated Balance Sheet**
- **Consolidated Profit and Loss Statement**
- Các công ty con được đánh dấu là "Group Company" hoặc có liên kết Parent-Subsidiary

### 10.6. Hạn chế

- Hai công ty phải cùng loại tiền tệ (không hỗ trợ giao dịch nội bộ khác tiền tệ)
- Tự động tạo chứng từ đối ứng khi submit (SI tạo PI và ngược lại)
- Giá chuyển giao (transfer pricing) được xác định từ hóa đơn gốc

### 10.7. Mua bán nội bộ qua kho — Chu trình đầy đủ A → B → End Customer

#### 10.7.1. Tổng quan

Đây là quy trình phổ biến trong tập đoàn: **Công ty A** (sản xuất/nhập khẩu) bán hàng cho **Công ty B** (phân phối), và **Công ty B** bán ra cho khách hàng cuối.

Đặc điểm:
- Hàng đi từ kho A sang kho B (chuyển kho nội bộ)
- Giá chuyển giao thường là giá vốn (valuation rate), không có lãi trên giao dịch nội bộ
- Cả hai công ty cùng trên một hệ thống ERPNext
- Khi B bán ra ngoài, toàn bộ lợi nhuận được ghi nhận ở B

#### 10.7.2. Cơ chế Internal Transfer

ERPNext phát hiện đây là giao dịch nội bộ qua phương thức `is_internal_transfer()`:

```python
if self.doctype == "Sales Invoice":
    # Kiểm tra Customer có is_internal_customer = 1
    # và represents_company == company của SI
elif self.doctype == "Purchase Invoice":
    # Kiểm tra Supplier có is_internal_supplier = 1
    # và represents_company == company của PI
```

Khi `is_internal_transfer()` trả về True:
- **Không ghi nhận doanh thu** (income account) bên bán
- **Không ghi nhận phải thu / phải trả** nội bộ
- **Không ghi nhận chi phí** bên mua
- Giá trị hàng chuyển từ kho A sang kho B theo **đúng giá vốn** (valuation rate)

#### 10.7.3. Cơ chế chuyển giá (set_incoming_rate)

**Bên bán (A's Delivery Note / Sales Invoice):**
- `incoming_rate` = giá vốn thực tế từ kho A (lấy từ Stock Ledger Entry)
- `rate` của item bị **ghi đè** bằng `incoming_rate`
- Discount, margin bị xóa về 0

**Bên mua (B's Purchase Receipt / Purchase Invoice):**
- `incoming_rate` lấy từ A's Delivery Note (nếu có inter-company reference)
- Hoặc lấy từ Stock Ledger qua `get_incoming_rate()` cho `from_warehouse` (kho A)
- Giá mua = đúng giá vốn, không có markup

#### 10.7.4. Luồng chứng từ

```
Công ty A (Bán)                          Công ty B (Mua)
================                         ================

Delivery Note (A)                         Purchase Receipt (B)
  - target_warehouse = "Kho B"             - from_warehouse = "Kho A"
  - is_internal_customer = 1               - is_internal_supplier = 1
  - represents_company = "Cty B"           - represents_company = "Cty A"
         │                                          │
         └───────────(Tự động tạo)───────────────────┘
         
Sales Invoice (A)                          Purchase Invoice (B)
  - target_warehouse = "Kho B"             - from_warehouse = "Kho A"
  - is_internal_customer = 1               - is_internal_supplier = 1
         │                                          │
         └───────────(Tự động tạo)───────────────────┘
         
Sau đó B bán ra ngoài:
Delivery Note (B) → Sales Invoice (B) → End Customer
  (Chuẩn, không còn nội bộ)
```

#### 10.7.5. Hạch toán chi tiết từng bước

**Giả định:**
- Sản phẩm X: giá vốn (valuation rate) = 100.000đ
- A bán cho B: số lượng 1, giá 100.000đ (giá vốn, không lãi)
- Thuế GTGT 12% = 12.000đ
- Kho A và kho B khác nhau, Perpetual Inventory bật cho cả 2 công ty

---

**Bước 1A — Delivery Note (A) xuất kho chuyển cho B**

GL Entries (từ StockController.get_gl_entries — vì có target_warehouse):

```
Nợ  TK "Hàng tồn kho - Kho B (Cty B)"        100.000
Có  TK "Hàng tồn kho - Kho A (Cty A)"        100.000
```

Hàng được chuyển từ kho A sang kho B. **Không ảnh hưởng P&L** — chỉ thay đổi cơ cấu tài sản. Tài sản của tập đoàn không thay đổi.

**Purchase Receipt (B) nhận hàng từ A (tự động tạo):**

```
Nợ  TK "Hàng tồn kho - Kho B"                100.000
Có  TK "Hàng tồn kho - Kho A"                100.000
```

---

**Bước 1B — Sales Invoice (A) — hóa đơn bán cho B**

Vì `is_internal_transfer() = True`:

```
Nợ  TK "Hàng tồn kho - Kho B"                100.000    (stock GL)
Có  TK "Hàng tồn kho - Kho A"                100.000    (stock GL)

Nợ  TK "Lợi nhuận chưa thực hiện (nội bộ)"     12.000    (thuế)
Có  TK "Thuế GTGT đầu ra"                       12.000    (thuế)
```

**Lưu ý quan trọng:**
- **Không có** Nợ "Phải thu KH" (bỏ qua customer GL entry)
- **Không có** Có "Doanh thu" (bỏ qua income GL entry)
- Chỉ có chuyển kho (stock) và thuế
- Thuế được bù trừ qua tài khoản "Lợi nhuận chưa thực hiện"

**Purchase Invoice (B) — hóa đơn mua từ A (tự động tạo):**

```
Nợ  TK "Hàng tồn kho - Kho B"                100.000    (stock GL)
Có  TK "Hàng tồn kho - Kho A"                100.000    (stock GL)

Nợ  TK "Thuế GTGT đầu vào"                      12.000
Có  TK "Lợi nhuận chưa thực hiện (nội bộ)"     12.000
```

**Lưu ý:**
- **Không có** Có "Phải trả NCC" (bỏ qua supplier GL entry)
- **Không có** Nợ "Chi phí" (bỏ qua expense GL entry)
- Thuế được bù trừ qua tài khoản "Lợi nhuận chưa thực hiện"

---

**Bước 2 — B bán ra End Customer**

**(A) Delivery Note (B):**

```
Nợ  TK "Giá vốn hàng bán (COGS)"              100.000
Có  TK "Hàng tồn kho - Kho B"                 100.000
```

**(B) Sales Invoice (B):**

```
Nợ  TK "Phải thu khách hàng"                   224.000  (giả sử giá bán 200.000 + thuế 12%)
Có  TK "Doanh thu bán hàng"                    200.000
Có  TK "Thuế GTGT đầu ra"                       24.000

Nợ  TK "Giá vốn hàng bán"                      100.000
Có  TK "Hàng tồn kho - Kho B"                  100.000
```

#### 10.7.6. Kết quả tổng hợp cho Tập đoàn

| Bút toán | Giá trị | Ảnh hưởng P&L Tập đoàn |
|---|---|---|
| A chuyển kho → B | 100.000 | Không (chuyển nội bộ) |
| A xuất hóa đơn cho B | (thuế 12.000) | Không (lãi/lỗ nội bộ triệt tiêu) |
| B nhập kho từ A | 100.000 | Không |
| B bán ra End Customer (doanh thu) | 200.000 | Lãi 100.000 |

**Lợi nhuận tập đoàn hợp nhất:** 100.000đ (chỉ xuất hiện khi B bán ra ngoài). Không có lợi nhuận nội bộ cần loại trừ.

### 10.7.7. Các phương án triển khai Intercompany trên thực tế

Tài liệu này tổng hợp từ nghiên cứu triển khai thực tế tại doanh nghiệp, so sánh 4 phương án từ đơn giản đến chuẩn chỉnh.

#### 10.7.7.1. Bối cảnh

| Yếu tố | Giá trị |
|---|---|
| Công ty A | Bên bán nội bộ (sản xuất/nhập khẩu) |
| Công ty B | Bên mua nội bộ, bán lại cho khách cuối |
| Khách hàng C | Khách cuối |
| Sản phẩm | SP01, số lượng 100 |
| Giá nội bộ | 1.000đ/sp |
| Giá bán khách | 1.200đ/sp |
| Kho A | Kho của Công ty A |
| Kho thương mại B | Kho nhận hàng của Công ty B |
| Kho chờ bán B | Kho trung chuyển / transit của B |

---

#### 10.7.7.2. Phương án 1 — Invoice-driven (Update Stock)

Còn gọi là **"PI là PR"** — Hóa đơn kiêm phiếu nhập kho.

**Sequence:**
```
A: SI (update_stock=1)
    → System auto tạo PI cho B
    → B submit PI (update_stock=1) → tự động nhập kho B
B: SE (chuyển Kho thương mại → Kho chờ bán)
B: SI bán khách (update_stock=1)
```

**Hạch toán:**

**A — Sales Invoice (update_stock=1):**
```
Nợ  TK "Phải thu KH (B)"        100.000
Có  TK "Doanh thu"              100.000

Nợ  TK "Giá vốn hàng bán"        ?
Có  TK "Hàng tồn kho - Kho A"    ?
```

**B — Purchase Invoice (update_stock=1):**
```
Nợ  TK "Hàng tồn kho - Kho TM"  100.000
Có  TK "Phải trả NCC (A)"       100.000
```

**B — Chuyển kho (Stock Entry):**
```
Nợ  TK "Hàng tồn kho - Chờ bán"
Có  TK "Hàng tồn kho - Kho TM"
```

**B — Bán khách (SI, update_stock=1):**
```
Nợ  TK "Phải thu KH (C)"         84.000    (70sp * 1.200)
Có  TK "Doanh thu"               84.000

Nợ  TK "Giá vốn hàng bán"       70.000    (70sp * 1.000)
Có  TK "Hàng tồn kho - Chờ bán" 70.000
```

**Nhận xét:**
- ❌ Không có Purchase Receipt riêng — PI kiêm luôn nhập kho
- ❌ Không có GRNI (Goods Received Not Invoiced)
- ❌ Không audit được hàng đã về nhưng chưa có hóa đơn
- ⚠️ Tồn kho ảo nếu PI chưa submit kịp nhưng hàng đã về
- ✅ Đơn giản, nhanh, phù hợp nội bộ tin tưởng

---

#### 10.7.7.3. Phương án 2 — DN + PI + SE

**Sequence:**
```
A: DN → SI (riêng)
B: PI (update_stock=1) → nhập kho
B: SE (chuyển Kho thương mại → Kho chờ bán)
B: SI bán khách
```

**Hạch toán:**

**A — Delivery Note:**
```
Nợ  TK "Giá vốn hàng bán"        ?
Có  TK "Hàng tồn kho - Kho A"    ?
```

**A — Sales Invoice:**
```
Nợ  TK "Phải thu KH (B)"        100.000
Có  TK "Doanh thu"              100.000
```

**B — Purchase Invoice (update_stock=1):**
```
Nợ  TK "Hàng tồn kho"           100.000
Có  TK "Phải trả NCC (A)"       100.000
```

**Nhận xét:**
- ❌ Vẫn không có Purchase Receipt
- ❌ Vẫn thiếu GRNI
- ❌ Sai nguyên lý ERP chuẩn (stock movement ≠ invoice)

---

#### 10.7.7.4. Phương án 3 — Chuẩn ERP (PO → PR → PI)

**Sequence:**
```
A: SO → DN → SI
B: PO → PR → PI
B: SE (chuyển Kho TM → Kho chờ bán)
B: SO → DN → SI (bán khách)
```

**Flow chi tiết:**

**Bước 1 — A bán:**

```
DN (A) → Giảm kho A, ghi COGS
  Nợ  TK "Giá vốn hàng bán"
  Có  TK "Hàng tồn kho - Kho A"

SI (A) → Ghi doanh thu
  Nợ  TK "Phải thu KH (B)"
  Có  TK "Doanh thu"
```

**Bước 2 — B mua (nhập kho trước, hóa đơn sau):**

```
PO (B) → Đặt hàng A (không GL Entry)

PR (B) → Nhập kho
  Nợ  TK "Hàng tồn kho - Kho TM"     100.000
  Có  TK "Hàng nhận chưa có HĐ (GRNI)" 100.000
    → GRNI: Goods Received Not Invoiced (công nợ tạm)
```

**Bước 3 — B nhận hóa đơn:**

```
PI (B) → Ghi nhận công nợ chính thức
  Nợ  TK "Hàng nhận chưa có HĐ (GRNI)"  100.000
  Có  TK "Phải trả NCC (A)"             100.000
    → GRNI về 0 (hàng đã về, hóa đơn đã có)
```

**Bước 4 — Chuyển kho:**
```
SE (B) → Kho TM → Kho chờ bán
  Nợ  TK "Hàng tồn kho - Chờ bán"
  Có  TK "Hàng tồn kho - Kho TM"
```

**Bước 5 — B bán khách:**
```
DN (B) → Xuất kho, ghi COGS
  Nợ  TK "Giá vốn hàng bán"            70.000  (70sp)
  Có  TK "Hàng tồn kho - Chờ bán"      70.000

SI (B) → Ghi doanh thu
  Nợ  TK "Phải thu KH (C)"             84.000
  Có  TK "Doanh thu"                   84.000
```

**Ví dụ số cho B:**
```
PR: +100 sp × 1.000 = +100.000 (tồn kho tăng)
PI: ghi nợ A 100.000
Bán 70 sp: Doanh thu 84.000, Giá vốn 70.000
Tồn cuối kỳ: 30sp × 1.000 = 30.000
```

**Ưu điểm:**
- ✅ Chuẩn kế toán — tách biệt receipt và invoice
- ✅ Có GRNI — audit được hàng về chưa có hóa đơn
- ✅ Audit tốt — dễ kiểm tra số dư GRNI
- ✅ Không tồn kho ảo

**Nhược điểm:**
- ❌ Nhiều bước, user dễ nhầm
- ❌ Cần training kỹ

---

#### 10.7.7.5. Phương án 4 — Hybrid (Đề xuất: Chuẩn ERP nhưng đơn giản hóa)

**Nguyên lý:** Backend vẫn đầy đủ PO→PR→PI, Frontend user chỉ thấy tối thiểu.

**Sequence:**
```
A: DN + SI
    → System tự động tạo:
        - PR cho B (từ DN của A)
        - PI cho B (từ SI của A)
B: SE (Kho TM → Kho chờ bán)
B: SI bán khách
```

**Hạch toán:** Giống Phương án 3 (chuẩn ERP).

**Bên trong hệ thống:**
| User thấy | System tạo |
|---|---|
| A submit DN | Auto tạo PR cho B |
| A submit SI | Auto tạo PI cho B |
| B submit PI | Cập nhật tồn kho + công nợ |

**Ưu điểm:**
- ✅ Chuẩn ERP (có PR, có GRNI)
- ✅ User đơn giản (B chỉ thấy PI)
- ✅ Không tồn kho ảo
- ✅ Audit được
- ✅ Phù hợp mở rộng sau này

#### 10.7.7.6. Ma trận so sánh 4 phương án

| Tiêu chí | PA1 | PA2 | PA3 | PA4 |
|---|---|---|---|---|
| Chuẩn ERP | ❌ | ❌ | ✅ | ✅ |
| Có PR/GRNI | ❌ | ❌ | ✅ | ✅ |
| Audit (hàng về chưa HĐ) | ❌ | ❌ | ✅ | ✅ |
| Đơn giản cho user | ✅ | ✅ | ❌ | ✅ |
| Tồn kho ảo | ⚠️ | ⚠️ | ❌ | ❌ |
| Kiểm soát hàng thực | ❌ | ❌ | ✅ | ✅ |

#### 10.7.7.7. Lộ trình triển khai khuyến nghị

```
Ngắn hạn (1-3 tháng): Giữ PA1 + validate chặt
  → Chấp nhận rủi ro, tập trung vận hành

Trung hạn (3-6 tháng): Thêm Stock Entry (PA2)
  → Phân tách kho rõ hơn

Dài hạn (6-12 tháng): Chuyển Hybrid (PA4)
  → Chuẩn ERP, tự động hóa backend
```

**Nguyên tắc vàng của ERP:** 
> **Stock movement ≠ Invoice** — Chuyển động kho và hóa đơn là hai nghiệp vụ riêng biệt, không gộp làm một.

### 10.8. Mua bán nội bộ — Trường hợp không qua kho

Không phải giao dịch nội bộ nào cũng có hàng hóa vật chất. Các trường hợp phổ biến:

#### 10.8.1. Dịch vụ nội bộ (Inter-company Service)

Công ty A cung cấp dịch vụ cho Công ty B (phí quản lý, tư vấn, chia sẻ nhân sự...).

**Bên A — Sales Invoice (dịch vụ, không update_stock):**
```
Nợ  TK "Phải thu KH (B)"            [phí dịch vụ + thuế]
Có  TK "Doanh thu dịch vụ"          [phí dịch vụ]
Có  TK "Thuế GTGT đầu ra"            [thuế]
```

**Bên B — Purchase Invoice (dịch vụ, không update_stock):**
```
Nợ  TK "Chi phí quản lý"            [phí dịch vụ]
Nợ  TK "Thuế GTGT đầu vào"          [thuế]
Có  TK "Phải trả NCC (A)"           [phí dịch vụ + thuế]
```

Đặc điểm:
- Không có chứng từ kho (DN, PR, SE)
- Hạch toán thẳng vào chi phí / doanh thu
- Vẫn có thể áp dụng inter-company nếu cấu hình Internal Customer/Supplier

#### 10.8.2. Lãi vay nội bộ (Inter-company Loan Interest)

Khi Công ty A cho Công ty B vay và tính lãi:

**A — Journal Entry (thu lãi cho vay nội bộ):**
```
Nợ  TK "Phải thu KH (B)"            [lãi vay]
Có  TK "Doanh thu tài chính"        [lãi vay]
```

**B — Journal Entry (trả lãi vay nội bộ):**
```
Nợ  TK "Chi phí tài chính"          [lãi vay]
Có  TK "Phải trả NCC (A)"           [lãi vay]
```

#### 10.8.3. Phân bổ chi phí chung nội bộ (Cost Allocation)

Khi Công ty A (công ty mẹ / văn phòng điều hành) phân bổ chi phí quản lý cho các công ty con:

**A — Sales Invoice:**
```
Nợ  TK "Phải thu KH (B)"            [phần chi phí phân bổ]
Có  TK "Doanh thu khác"             [phần chi phí phân bổ]
```

Hoặc dùng Journal Entry với tài khoản trung gian nếu không muốn ghi nhận doanh thu:

```
Nợ  TK "Phải thu nội bộ (B)"
Có  TK "Tài khoản trung gian phân bổ"
```

**B — Purchase Invoice / Journal Entry:**
```
Nợ  TK "Chi phí QLDN"               [phần chi phí nhận phân bổ]
Có  TK "Phải trả nội bộ (A)"
```

#### 10.8.4. Lưu ý về thuế cho dịch vụ nội bộ

- Dịch vụ nội bộ giữa các công ty trong cùng tập đoàn vẫn phải xuất hóa đơn và chịu thuế GTGT (theo quy định từng nước)
- Giá dịch vụ phải đảm bảo nguyên tắc **giao dịch độc lập (arm's length principle)** để tránh bị điều chỉnh thuế
- Kiểm tra quy định về **chuyển giá (transfer pricing)** khi cung cấp dịch vụ nội bộ

### 10.9. Hàng gửi bán (Consignment) — Hàng gửi đại lý

#### 10.9.1. Bản chất nghiệp vụ

Hàng gửi bán là hình thức **Công ty A** (chủ hàng) gửi hàng cho **Đại lý B** để bán hộ. Đặc điểm:
- **Quyền sở hữu hàng vẫn thuộc về A** — B chỉ là người giữ hộ và bán hộ
- B chỉ trả tiền cho A khi hàng thực sự được bán cho khách hàng cuối
- B được hưởng **hoa hồng** trên doanh số bán được
- Hàng tồn tại kho của B vẫn là tài sản của A (trên sổ sách của A)

#### 10.9.2. ERPNext không có module Consignment chuẩn

ERPNext **không có** doctype "Consignment Note" hoặc "Sales on Consignment" riêng. Tuy nhiên, có thể triển khai bằng 2 cách:

#### 10.9.3. Cách 1: Dùng tài khoản kho riêng (khuyến nghị)

Tạo một kho "Hàng gửi bán - Đại lý B" thuộc sở hữu của Công ty A, nhưng đặt tại địa điểm của B.

**Bước 1 — Chuyển hàng đến Đại lý B (Stock Entry - Material Transfer):**

```
Nợ  TK "Hàng tồn kho - Hàng gửi bán (Đại lý B)"    100.000
Có  TK "Hàng tồn kho - Kho A"                        100.000
```

**Bước 2 — Khi đại lý B báo đã bán được hàng:**
A tạo **Sales Invoice** trực tiếp đến khách hàng cuối (hoặc đến đại lý B), đồng thời xuất kho từ "Hàng gửi bán - Đại lý B".

Cách 2a: A bán thẳng cho End Customer (A lập hóa đơn gửi thẳng cho khách hàng cuối):

```
Nợ  TK "Phải thu khách hàng cuối"                    200.000
Có  TK "Doanh thu bán hàng"                          200.000
Có  TK "Thuế GTGT đầu ra"                             24.000

Nợ  TK "Giá vốn hàng bán"                            100.000
Có  TK "Hàng tồn kho - Hàng gửi bán (Đại lý B)"     100.000
```

Cách 2b: A bán cho Đại lý B, B bán cho khách hàng cuối (xem quy trình nội bộ ở mục 10.7).

**Bước 3 — Hoa hồng đại lý:**
A ghi nhận chi phí hoa hồng phải trả cho B:

```
Nợ  TK "Chi phí hoa hồng"                             10.000  (giả sử 5% hoa hồng)
Có  TK "Phải trả Đại lý B"                             10.000
```

**Hạch toán tổng thể (bên A):**

| Thời điểm | Nợ | Có | Giá trị |
|---|---|---|---|
| Gửi hàng | Hàng gửi bán - Kho B | Hàng tồn kho - Kho A | 100.000 |
| Bán được hàng | Phải thu KH cuối | Doanh thu | 200.000 |
| Bán được hàng | Giá vốn | Hàng gửi bán - Kho B | 100.000 |
| Hoa hồng | Chi phí hoa hồng | Phải trả Đại lý B | 10.000 |

**Trên Báo cáo tài chính của A:**
- **Trước khi bán:** Hàng tồn kho = 100.000 (tài sản), không có doanh thu
- **Sau khi bán:** Hàng tồn kho = 0, Doanh thu = 200.000, Chi phí = 110.000 (COGS + hoa hồng)

#### 10.9.4. Cách 2: Dùng cơ chế Subcontracting

Sử dụng Stock Entry `purpose = "Send to Subcontractor"` để gửi hàng, và Purchase Receipt để nhận thành phẩm/hàng bán trả về.

**Nhược điểm:** Phức tạp hơn, cần quản lý vật tư tiêu hao, không phù hợp với bản chất consignment thuần túy.

#### 10.9.5. Hoa hồng đại lý qua Sales Partner

ERPNext có module **Sales Partner** để theo dõi hoa hồng:
- Mỗi đại lý B có thể là một Sales Partner
- Khi A lập hóa đơn, hệ thống tự động tính hoa hồng dựa trên `commission_rate`
- Tuy nhiên, hoa hồng này **chỉ mang tính thông tin (reporting)** — không tự động tạo GL Entry. Cần tạo Journal Entry thủ công để hạch toán hoa hồng

---

## 11. Kết chuyển cuối kỳ (Period Closing)

### 11.1. Mục đích

Cuối kỳ kế toán (tháng/quý/năm), cần thực hiện:
1. **Kết chuyển doanh thu, chi phí** vào tài khoản Xác định kết quả kinh doanh
2. **Kết chuyển lãi/lỗ** vào Lợi nhuận giữ lại (Retained Earnings)
3. **Khóa sổ** — ngăn chặn sửa đổi chứng từ trong kỳ đã khóa

### 11.2. Chuẩn bị trước khi kết chuyển

1. Kiểm tra tất cả giao dịch đã được ghi nhận đầy đủ
2. Đánh giá lại tỷ giá ngoại tệ (Exchange Rate Revaluation)
3. Phân bổ deferred revenue/expense
4. Hạch toán khấu hao tài sản cố định
5. Kiểm kê kho và điều chỉnh nếu cần

### 11.3. Period Closing Voucher — Hạch toán

Period Closing Voucher (PCV) thực hiện:

#### 11.3.1. Kết chuyển tài khoản Doanh thu và Chi phí

Với mỗi tài khoản P&L có số dư khác 0, tạo GL Entry để đưa số dư về 0:

```
Nợ  TK "Doanh thu bán hàng"                [số dư]  --- đưa về 0
Có  TK "Xác định KQKD"                    [số dư]
```

```
Nợ  TK "Xác định KQKD"                    [số dư]
Có  TK "Chi phí QLDN"                      [số dư]  --- đưa về 0
```

**Sau bước này:** Tất cả tài khoản doanh thu và chi phí có số dư = 0. Tài khoản "Xác định KQKD" phản ánh lãi hoặc lỗ.

#### 11.3.2. Kết chuyển lãi/lỗ vào Lợi nhuận giữ lại

Nếu lãi (Xác định KQKD có số dư Có):

```
Nợ  TK "Xác định KQKD"                    [lãi]
Có  TK "Lợi nhuận giữ lại"                [lãi]
```

Nếu lỗ (Xác định KQKD có số dư Nợ):

```
Nợ  TK "Lợi nhuận giữ lại"                [lỗ]
Có  TK "Xác định KQKD"                    [lỗ]
```

#### 11.3.3. Lưu kết quả Account Closing Balance

PCV lưu số dư của từng tài khoản (theo dimension: cost center, project, finance book) vào doctype **Account Closing Balance**.

**Account Closing Balance** lưu trữ:
- `account`: Tài khoản
- `cost_center`: Trung tâm chi phí
- `project`: Dự án
- `finance_book`: Sổ kế toán
- `period_closing_voucher`: Tham chiếu PCV
- `total_debit`, `total_credit`: Tổng số dư Nợ/Có
- `is_period_closing_voucher_entry`: = 1 nếu là kết chuyển P&L

### 11.4. Khóa sổ (Freeze Accounting)

Sau khi kết chuyển, ERPNext có thể khóa sổ để ngăn thay đổi:
- `Accounts Settings > acc_frozen_upto`: Khóa đến ngày nào
- Các chứng từ trong kỳ đã khóa không thể sửa hoặc hủy

### 11.5. Sơ đồ toàn bộ quy trình cuối kỳ

```
1. Ghi nhận hết giao dịch trong kỳ
   (PI, SI, PE, JE...)
        │
2. Đánh giá lại tỷ giá (Exchange Rate Revaluation)
        │
3. Phân bổ Deferred (Process Deferred Accounting)
        │
4. Tính khấu hao TSCĐ (Asset Depreciation)
        │
5. Phân bổ chi phí (LCV, Cost Allocation)
        │
6. Kiểm kê kho (Stock Reconciliation)
        │
7. Tạo Period Closing Voucher
   ├── Kết chuyển Doanh thu → Xác định KQKD
   ├── Kết chuyển Chi phí → Xác định KQKD  
   ├── Kết chuyển Lãi/Lỗ → Lợi nhuận giữ lại
   └── Lưu Account Closing Balance
        │
8. Khóa sổ (set acc_frozen_upto)
```

### 11.6. Ví dụ kết chuyển

**Tình huống cuối năm 2026:**
- Doanh thu: 5.000.000.000đ
- Chi phí: 3.800.000.000đ
- Lãi: 1.200.000.000đ

**Bước 1 — Kết chuyển doanh thu:**

```
Nợ  TK "Doanh thu bán hàng"                5.000.000.000
Có  TK "Xác định kết quả KD"               5.000.000.000
```

**Bước 2 — Kết chuyển chi phí:**

```
Nợ  TK "Xác định kết quả KD"               3.800.000.000
Có  TK "Chi phí QLDN"                      2.000.000.000
Có  TK "Giá vốn hàng bán"                  1.500.000.000
Có  TK "Chi phí khác"                        300.000.000
```

**Bước 3 — Kết chuyển lãi vào Lợi nhuận giữ lại:**

Số dư "Xác định KQKD" = 5.000.000.000 - 3.800.000.000 = 1.200.000.000 (Có = lãi)

```
Nợ  TK "Xác định kết quả KD"               1.200.000.000
Có  TK "Lợi nhuận giữ lại"                 1.200.000.000
```

**Sau kết chuyển:**
- Tất cả tài khoản Doanh thu và Chi phí = 0
- "Xác định KQKD" = 0
- "Lợi nhuận giữ lại" tăng 1.200.000.000đ

---

## 12. Báo cáo tài chính

### 12.1. Các báo cáo chính trong ERPNext

| Báo cáo | Mục đích | Dữ liệu từ |
|---|---|---|
| **General Ledger** | Số dư chi tiết từng tài khoản | GL Entry |
| **Trial Balance** | Bảng cân đối số phát sinh | GL Entry |
| **Profit and Loss** | Báo cáo KQHĐKD | Tài khoản Income & Expense |
| **Balance Sheet** | Bảng CĐKT | Tài khoản Asset, Liability, Equity |
| **Cash Flow** | Báo cáo lưu chuyển tiền tệ | GL Entry (phân loại) |
| **AR/AP Aging** | Công nợ phải thu/phải trả theo tuổi nợ | GL Entry |
| **Deferred Revenue & Expense** | Doanh thu/CP hoãn lại theo kỳ | GL Entry + Process Deferred |
| **Sales/Purchase Register** | Sổ nhật ký bán/mua | Invoice + Tax |

### 12.2. General Ledger (Sổ cái)

**Nguồn dữ liệu:** Từ bảng `tabGL Entry`.

Các trường:
- `posting_date`, `account`, `debit`, `credit`, `voucher_type`, `voucher_no`
- `party_type`, `party`: Thông tin đối tác
- `against`: Tài khoản đối ứng
- `cost_center`, `project`: Thông tin chi phí

### 12.3. Trial Balance (Bảng cân đối số phát sinh)

Hiển thị số dư đầu kỳ, phát sinh, số dư cuối kỳ của từng tài khoản.

**Công thức tính số dư:**
```
Số dư cuối kỳ = Số dư đầu kỳ + Phát sinh Nợ - Phát sinh Có
(cộng cho tài khoản Asset/Expense, trừ cho Liability/Equity/Income)
```

### 12.4. Balance Sheet (Bảng CĐKT)

**Cấu trúc:**

```
TÀI SẢN (Application of Funds)
  ├── Tài sản ngắn hạn
  │   ├── Tiền mặt
  │   ├── Phải thu KH
  │   ├── Hàng tồn kho
  │   └── Chi phí trả trước
  └── Tài sản dài hạn
      ├── TSCĐ (Nguyên giá - Khấu hao)
      └── Đầu tư dài hạn

NGUỒN VỐN (Source of Funds)
  ├── Nợ phải trả
  │   ├── Phải trả NCC
  │   ├── Thuế phải nộp
  │   └── Doanh thu chưa thực hiện
  └── Vốn chủ sở hữu
      ├── Vốn góp
      └── Lợi nhuận giữ lại
```

### 12.5. Profit & Loss (Báo cáo KQHĐKD)

**Cấu trúc:**

```
DOANH THU
  Doanh thu bán hàng              xxx
  Giảm trừ doanh thu              (xxx)
  ---
  Doanh thu thuần                 xxx

CHI PHÍ
  Giá vốn hàng bán (COGS)         (xxx)
  Lợi nhuận gộp                   xxx
  Chi phí bán hàng                (xxx)
  Chi phí QLDN                    (xxx)
  ---
  Lợi nhuận từ HĐKD               xxx
  Doanh thu tài chính              xxx
  Chi phí tài chính               (xxx)
  ---
  Lợi nhuận trước thuế            xxx
  Thuế TNDN                       (xxx)
  ---
  Lợi nhuận sau thuế              xxx
```

### 12.6. Cash Flow (Báo cáo lưu chuyển tiền tệ)

ERPNext xây dựng báo cáo CF dựa trên phân loại tài khoản và GL Entry:
- **Operating activities:** Tài khoản Income/Expense liên quan đến hoạt động kinh doanh
- **Investing activities:** Mua/bán TSCĐ, đầu tư
- **Financing activities:** Vay, trả nợ, tăng vốn

### 12.7. AR/AP Aging (Công nợ theo tuổi)

**Phân tích công nợ theo khoảng thời gian:**
- 0-30 ngày
- 31-60 ngày
- 61-90 ngày
- Trên 90 ngày

Dữ liệu lấy từ `tabGL Entry` với các bộ lọc:
- `party_type = "Customer"` (AR) hoặc `"Supplier"` (AP)
- `voucher_type = "Sales Invoice"` hoặc `"Purchase Invoice"`
- Outstanding amount tính từ GL entries

### 12.8. Deferred Revenue & Expense Report

Báo cáo thể hiện:
- Doanh thu/Chi phí hoãn lại đã ghi nhận trong kỳ
- Số dư còn lại chưa ghi nhận
- Dự kiến ghi nhận trong tương lai (with_upcoming_postings filter)

---

## Phụ lục: Ma trận GL Entry đầy đủ

### Mua hàng

| Chứng từ | Nợ | Có | Ghi chú |
|---|---|---|---|
| Purchase Receipt | Hàng tồn kho | Hàng nhận chưa có HĐ | Perpetual Inventory |
| PR - Thuế valuation | (không) | Thuế GTGT đầu vào | Nếu có tax valuation |
| Purchase Invoice (có PR) | Hàng nhận chưa có HĐ | Phải trả NCC | Đảo ngược SRNB |
| Purchase Invoice (không PR) | Hàng nhận chưa có HĐ | Phải trả NCC | |
| PI - Thuế (Add) | Thuế GTGT đầu vào | Phải trả NCC | |
| PI - TDS (Deduct) | Phải trả NCC | TDS phải nộp | |
| PI - Cash payment | Phải trả NCC | Tiền/Ngân hàng | is_paid = 1 |
| Payment Entry (Pay) | Phải trả NCC | Tiền/Ngân hàng | |
| Debit Note (Return) | Phải trả NCC | Chi phí/Hàng tồn kho | Giá trị âm |
| Landed Cost Voucher | Hàng tồn kho (tăng) | Chi phí LC | Qua re-submit PR |

### Bán hàng

| Chứng từ | Nợ | Có | Ghi chú |
|---|---|---|---|
| Delivery Note | Giá vốn (COGS) | Hàng tồn kho | Perpetual Inventory |
| Sales Invoice | Phải thu KH | Doanh thu / DT chưa TH | |
| SI - Thuế | (trong Phải thu KH) | Thuế GTGT đầu ra | |
| SI - Discount item | Tài khoản chiết khấu | Doanh thu | Nếu bật discount accounting |
| SI - Discount tổng | Chiết khấu thêm | Phải thu KH | |
| SI - update_stock | COGS | Hàng tồn kho | Thêm so với thường |
| SI - Loyalty points | Điểm thưởng | Phải thu KH | |
| POS - Tiền mặt | Tiền mặt | Phải thu KH | Xóa công nợ |
| Payment Entry (Receive) | Tiền/Ngân hàng | Phải thu KH | |
| Credit Note (Return) | (giá trị âm các TK) | (giá trị âm các TK) | Đảo ngược SI |

### Kho & Điều chỉnh

| Chứng từ | Nợ | Có | Ghi chú |
|---|---|---|---|
| Material Receipt | Hàng tồn kho | Chi phí/Điều chỉnh | |
| Material Issue | Chi phí/Điều chỉnh | Hàng tồn kho | |
| Material Transfer | Hàng tồn kho (đích) | Hàng tồn kho (nguồn) | |
| Manufacture | Hàng tồn kho (TP) | Hàng tồn kho (NVL) | |
| Opening Stock | Hàng tồn kho | TK Bảng CĐKT | is_opening = Yes |
| Stock Reconciliation | Hàng tồn kho | Điều chỉnh kho | |
| Stock Receipt (Subcontract) | Hàng tồn kho (TP) | Hàng tồn kho (NCC) | |

### Tiền tệ & Kết chuyển

| Chứng từ | Nợ | Có | Ghi chú |
|---|---|---|---|
| PE - FX Gain | Tiền/NH | Phải thu KH / Lãi TG | Tỷ giá tăng |
| PE - FX Loss | Phải thu KH / Lỗ TG | Tiền/NH | Tỷ giá giảm |
| Revaluation (non-zero) | TK ngoại tệ (tỷ giá mới) | TK ngoại tệ (tỷ giá cũ) | + Unrealized GL |
| Period Closing | Doanh thu/CP → XĐKQKD | XĐKQKD | Đóng tài khoản P&L |
| Period Closing (lãi) | XĐKQKD | Lợi nhuận giữ lại | |
| Period Closing (lỗ) | Lợi nhuận giữ lại | XĐKQKD | |

---

> **Tài liệu tham khảo:** Mã nguồn ERPNext tại `/home/nxc/myfrappe/apps/erpnext/erpnext/` — các file chính:
> - `accounts/doctype/sales_invoice/sales_invoice.py`
> - `accounts/doctype/purchase_invoice/purchase_invoice.py`
> - `controllers/accounts_controller.py`
> - `controllers/stock_controller.py`
> - `stock/doctype/purchase_receipt/purchase_receipt.py`
> - `stock/doctype/stock_entry/stock_entry.py`
> - `accounts/doctype/payment_entry/payment_entry.py`
> - `accounts/deferred_revenue.py`
> - `accounts/doctype/exchange_rate_revaluation/exchange_rate_revaluation.py`
> - `accounts/doctype/period_closing_voucher/period_closing_voucher.py`
> - `stock/doctype/landed_cost_voucher/landed_cost_voucher.py`
