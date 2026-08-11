# Tài liệu Luồng Kế toán Bán hàng Đầy đủ: Sales Order → Exchange Rate Revaluation

> Tài liệu này mô tả chi tiết toàn bộ logic kế toán từ Sales Order, Delivery Note, Sales Invoice, Payment Entry (Receive), Journal Entry đến Exchange Rate Revaluation — bao gồm GL Entries, Stock Ledger, Outstanding, Deferred Revenue, Loyalty Points, POS.

---

## MỤC LỤC

1. [Sơ đồ Tổng quan Luồng Nghiệp vụ](#1-sơ-đồ-tổng-quan)
2. [Sales Order — Không tạo GL Entry](#2-sales-order)
3. [Delivery Note — Kế toán Xuất kho](#3-delivery-note)
4. [Sales Invoice — Kế toán Doanh thu & Công nợ](#4-sales-invoice)
5. [Deferred Revenue — Doanh thu Chưa Thực hiện](#5-deferred-revenue)
6. [Payment Entry (Receive) — Thu tiền Khách hàng](#6-payment-entry-receive)
7. [Journal Entry — Bút toán Điều chỉnh](#7-journal-entry)
8. [Exchange Rate Revaluation — Đánh giá lại Tỷ giá](#8-exchange-rate-revaluation)
9. [GL Engine Trung tâm](#9-gl-engine-trung-tâm)
10. [Bảng tổng hợp Tài khoản Kế toán](#10-bảng-tổng-hợp-tài-khoản)
11. [Tóm tắt Luồng End-to-End](#11-tóm-tắt-luồng-end-to-end)
12. [Các Tình huống Đặc biệt](#12-các-tình-huống-đặc-biệt)

---

## 1. Sơ đồ Tổng quan

### 1.1. Chuỗi Kế thừa Class

```
SalesOrder           → SellingController → StockController → AccountsController → TransactionBase → Document
DeliveryNote         → SellingController → StockController → AccountsController → ...
SalesInvoice         → SellingController → StockController → AccountsController → ...
PaymentEntry         → AccountsController → TransactionBase → Document
JournalEntry         → AccountsController → TransactionBase → Document
ExchangeRateRevaluation → Document (không có AccountsController — tạo JE thay vì GL Entry trực tiếp)
```

### 1.2. Luồng Nghiệp vụ & Kế toán

```
Sales Order (Đơn hàng)
  │
  │ → KHÔNG tạo GL Entry
  │ → Chỉ cập nhật reserved_qty trong Bin
  │ → Có thể nhận Advance (Journal Entry hoặc Payment Entry)
  │
  ▼
Delivery Note (Xuất kho / Giao hàng)
  │
  │ → Tạo Stock Ledger Entries (SLE): actual_qty = -qty (xuất kho)
  │ → Tạo GL Entries (nếu perpetual inventory):
  │     Debit:  Cost of Goods Sold (COGS) / Expense Account
  │     Credit: Warehouse Account (giảm hàng tồn kho)
  │ → Chưa ghi nhận doanh thu — chưa ảnh hưởng Receivable
  │
  ▼
Sales Invoice (Hóa đơn bán hàng) ← TÀI LIỆU KẾ TOÁN CHÍNH
  │
  │ → GL Entries:
  │     Debit:  Receivable Account (công nợ khách hàng)
  │     Credit: Income Account (doanh thu)
  │     Credit: Tax Account (thuế đầu ra)
  │
  │ → Nếu update_stock=1 + perpetual inventory:
  │     Debit:  COGS Account (giá vốn)
  │     Credit: Warehouse Account (giảm kho)
  │
  │ → Nếu is_pos=1: thêm bút toán thanh toán POS
  │ → Nếu redeem_loyalty_points: ghi nhận chi phí loyalty
  │ → Nếu enable_discount_accounting: ghi nhận discount riêng
  │
  ▼
Payment Entry (Receive) — Thu tiền từ Khách hàng
  │
  │ → GL Entries:
  │     Debit:  Bank/Cash Account (tiền vào)
  │     Credit: Receivable Account (giảm công nợ)
  │
  │ → Nếu có chênh lệch tỷ giá: tạo JE "Exchange Gain Or Loss"
  │
  ▼
Journal Entry (Bút toán điều chỉnh — tùy chọn)
  │ → Debit/Credit trực tiếp các tài khoản
  │ → Dùng cho: điều chỉnh, kết chuyển, khấu hao, advance allocation
  │
  ▼
Exchange Rate Revaluation (Đánh giá lại tỷ giá cuối kỳ)
  │
  │ → Tạo Journal Entries:
  │     + Zero Balance JV (tài khoản có 1 bên = 0)
  │     + Revaluation JV (tài khoản có số dư cả 2 loại tiền)
  │     → Cả 2 đều ghi nhận vào Unrealized Exchange Gain/Loss Account
  │
  ▼
Period Closing Voucher (Kết chuyển cuối kỳ)
```

---

## 2. Sales Order

**File:** `erpnext/selling/doctype/sales_order/sales_order.py`
**Class:** `SalesOrder(SellingController)`
**Cây kế thừa:** `SellingController → StockController → AccountsController → TransactionBase → Document`

### 2.1. Vòng đời

| Sự kiện | Mô tả |
|---------|-------|
| `validate()` | Kiểm tra customer, items, delivery dates, credit limit, pricing rules |
| `on_submit()` | `check_credit_limit()`, `update_reserved_qty()`, `update_project()`, `update_prevdoc_status(Quotation)`, `update_blanket_order()`, `update_linked_doc()` |
| `on_cancel()` | Đảo ngược các cập nhật, bỏ qua GL Entry |

### 2.2. ✅ GL Entries

**Sales Order KHÔNG tạo GL Entries.** Là chứng từ kế hoạch bán hàng, không ảnh hưởng đến số dư tài khoản.

Tuy nhiên, SO ảnh hưởng đến **Bin** (tồn kho khả dụng):
- Khi SO submit: `reserved_qty` trong Bin tăng lên (dự trữ hàng cho đơn)
- Khi DN/SI submit: `reserved_qty` giảm, `delivered_qty` tăng

> `ignore_linked_doctypes` trong `on_cancel` có chứa "GL Entry", "Stock Ledger Entry", "Payment Ledger Entry" — xác nhận SO không liên quan đến các bút toán này.

### 2.3. Advance từ Khách hàng (trên SO)

SO có thể nhận Advance Payment qua:
1. **Payment Entry** với `payment_type = "Receive"` và tham chiếu đến SO
2. **Journal Entry** với dòng accounts có reference đến SO

Cả 2 đều cập nhật `advance_paid` trên SO, và được allocate khi SI submit qua `update_against_document_in_jv()`.

---

## 3. Delivery Note

**File:** `erpnext/stock/doctype/delivery_note/delivery_note.py`
**Class:** `DeliveryNote(SellingController)`

### 3.1. Vòng đời

#### `on_submit(self)`:

```
1. validate_packed_qty()
2. update_pick_list_status()
3. validate_approving_authority()
4. update_prevdoc_status()              → Cập nhật delivered_qty lên SO
5. update_billing_status()
6. check_credit_limit()
7. update_stock_ledger()                ← ⭐ Tạo SLE (actual_qty = -qty)
8. make_gl_entries()                    ← ⭐ GL Entries (perpetual inventory)
9. repost_future_sle_and_gle()
```

#### `on_cancel(self)`:

```
1. super().on_cancel()
2. check_sales_order_on_hold_or_close()
3. check_next_docstatus()
4. update_prevdoc_status()              ← Đảo ngược delivered_qty
5. update_billing_status()
6. update_stock_ledger()                ← SLE hủy
7. cancel_packing_slips()
8. make_gl_entries_on_cancel()
9. repost_future_sle_and_gle()
```

### 3.2. Stock Ledger Entries (SLE)

`update_stock_ledger()` trong `SellingController` tạo SLE cho từng dòng:

```
SellingController.update_stock_ledger()
  → get_sl_entries(d, {...})
      actual_qty = -qty (xuất kho)
      incoming_rate = 0 (xuất, không nhập)
      outgoing_rate = d.incoming_rate (valuation rate tại thời điểm xuất)

  → Với serialized item: giảm Serial No, valuation rate từ Serial No
  → Với packed items: giảm kho cho từng packed item riêng
  → Với is_return: actual_qty = +qty (nhập lại kho)
```

### 3.3. GL Entries — StockController (Perpetual Inventory)

Delivery Note chỉ tạo GL entries khi:
1. **Perpetual inventory** được bật cho công ty (`erpnext.is_perpetual_inventory_enabled(company) = True`)
2. **update_stock = 1** (luôn true cho DN)

Logic GL trong `StockController.get_gl_entries()`:

```
Với mỗi dòng item, lấy SLE map cho item_row.name:

  Debit:  Expense Account (COGS)     ← stock_value_difference
  Credit: Warehouse Account           ← stock_value_difference

  (Debit và Credit được đảo dấu trong code:
   - GL entry 1: Debit Warehouse Account, Credit Expense Account (với debit = -stock_value_difference)
   - Net effect: Debit Expense, Credit Warehouse)

  Nếu internal transfer (target_warehouse):
    Debit:  Target Warehouse Account  ← stock_value_difference
    Credit: Source Warehouse Account  ← stock_value_difference

  Nếu có rounding diff trong internal transfer:
    Debit:  Default Expense Account   ← sle_rounding_diff
    Credit: Warehouse Asset Account   ← sle_rounding_diff
```

### 3.4. Bảng GL Entry Chuẩn cho DN

**Xuất kho bán hàng (Perpetual Inventory):**

```
Debit:  Cost of Goods Sold / Expense Account   ← stock_value_difference
Credit: Warehouse Account                       ← stock_value_difference
```

**Internal Transfer (chuyển kho nội bộ):**

```
Debit:  Target Warehouse Account     ← stock_value_difference
Credit: Source Warehouse Account     ← stock_value_difference
```

**Phiếu trả hàng (Return — nhập lại kho):**

```
Debit:  Warehouse Account            ← stock_value_difference
Credit: Cost of Goods Sold Account   ← stock_value_difference
```

### 3.5. Lưu ý Quan trọng

| Tính chất | Mô tả |
|-----------|-------|
| Doanh thu? | ❌ KHÔNG — DN chưa ghi nhận doanh thu |
| Công nợ KH? | ❌ KHÔNG — DN chưa ảnh hưởng Receivable |
| Khi nào tạo GL? | Chỉ khi perpetual inventory được bật |
| Khi tắt perpetual? | DN không tạo GL Entry — chỉ có SLE |

---

## 4. Sales Invoice

**File:** `erpnext/accounts/doctype/sales_invoice/sales_invoice.py`
**Class:** `SalesInvoice(SellingController)`

### 4.1. Đây là Chứng từ Kế toán Chính

Sales Invoice là trung tâm của kế toán bán hàng — nó ghi nhận:
- **Doanh thu** (Income Account)
- **Công nợ khách hàng** (Receivable Account)
- **Thuế đầu ra** (Tax Account)
- **Giá vốn hàng bán** (COGS — nếu perpetual + update_stock)
- **Thanh toán POS** (nếu is_pos)
- **Loyalty points** (nếu redeem)
- **Chiết khấu** (nếu enable_discount_accounting)
- **Điều chỉnh làm tròn** (Round Off Account)

### 4.2. Vòng đời

#### `on_submit(self)` — Thứ tự đầy đủ:

```
1. validate_pos_paid_amount()
2. validate_approving_authority()
3. check_prev_docstatus()
4. update_status_updater_args()
5. update_prevdoc_status()                ← Cập nhật delivered_qty trên SO
6. update_billing_status_in_dn()          ← Cập nhật billed_amt trên DN
7. clear_unallocated_mode_of_payments()
8. [Nếu update_stock=1]:
     update_stock_ledger()                ← SLE (nếu perpetual: ghi nhận COGS)
9. make_gl_entries()                      ← ⭐⭐ GL Entries CHÍNH
10. [Nếu update_stock=1]: repost_future_sle_and_gle()
11. update_against_document_in_jv()       ← Phân bổ Advance Payments
12. update_time_sheet()
13. update_company_current_month_sales()
14. update_linked_doc()
15. make_loyalty_point_entry()            ← Ghi nhận loyalty points
16. [Nếu redeem]: apply_loyalty_points()
17. process_common_party_accounting()
```

#### `on_cancel(self)`:

```
1. update_prevdoc_status()                ← Đảo ngược delivered_qty
2. update_billing_status_in_dn()
3. [Nếu update_stock=1]: update_stock_ledger() → SLE hủy
4. make_gl_entries_on_cancel()
5. [Nếu update_stock=1]: repost_future_sle_and_gle()
6. delete_loyalty_point_entry()
```

### 4.3. `make_gl_entries()` — Orchestrator

```python
def make_gl_entries(self, gl_entries=None, from_repost=False):
    if not gl_entries:
        gl_entries = self.get_gl_entries()

    if gl_entries:
        update_outstanding = "No" if (self.is_pos or self.write_off_account
                                        or self.redeem_loyalty_points) else "Yes"

        if self.docstatus == 1:
            make_gl_entries(gl_entries, update_outstanding=update_outstanding, ...)
            self.make_exchange_gain_loss_journal()   # ← JE riêng nếu có

        elif self.docstatus == 2:
            make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

        if update_outstanding == "No":
            update_voucher_outstanding(...)          # ← Cập nhật thủ công
```

### 4.4. `get_gl_entries()` — Thứ tự 11 bước

```python
def get_gl_entries(self, warehouse_account=None):
    gl_entries = []

    1.  make_customer_gl_entry(gl_entries)                  # Debit Receivable
    2.  make_tax_gl_entries(gl_entries)                     # Credit Tax
    3.  make_internal_transfer_gl_entries(gl_entries)       # Inter-company
    4.  make_item_gl_entries(gl_entries)                    # Credit Income + COGS
    5.  make_precision_loss_gl_entry(gl_entries)            # Round Off
    6.  make_discount_gl_entries(gl_entries)                # Discount Account
    7.  merge_similar_entries(gl_entries)                   # Gộp entries giống nhau
    8.  make_loyalty_point_redemption_gle(gl_entries)       # Loyalty
    9.  make_pos_gl_entries(gl_entries)                     # POS payments
    10. make_write_off_gl_entry(gl_entries)                 # Write-off (POS)
    11. make_gle_for_rounding_adjustment(gl_entries)        # Rounding

    return gl_entries
```

### 4.5. Chi tiết từng Bút toán

#### 4.5.1. `make_customer_gl_entry()`

```
Debit:  Receivable Account (self.debit_to)  ← base_grand_total
  party_type = "Customer"
  party = self.customer
  against = self.against_income_account
  against_voucher = self.name (hoặc return_against nếu is_return)
  against_voucher_type = self.doctype
```

- Dùng `rounded_total` nếu có rounding adjustment, nếu không dùng `grand_total`
- Internal transfer: bỏ qua (không tạo customer GL entry)
- Return: `against_voucher` trỏ về hóa đơn gốc

#### 4.5.2. `make_tax_gl_entries()`

```
Với mỗi dòng thuế có base_tax_amount_after_discount_amount != 0:

  Credit: Tax Account Head              ← base_amount
    against = self.customer
    cost_center = tax.cost_center
```

Không phân biệt Add/Deduct như bên mua — thuế đầu ra luôn là Credit (nợ phải trả với nhà nước).

#### 4.5.3. `make_item_gl_entries()` — Logic Per-Item

```
item d
│
├── Fixed asset (is_fixed_asset):
│   ├── is_return:
│   │   → get_gl_entries_on_asset_regain()
│   │   (đảo ngược disposal: Debit Asset, Credit Income)
│   └── Không phải return:
│       → depreciate_asset() — tính khấu hao đến ngày bán
│       → get_gl_entries_on_asset_disposal()
│       Debit:  Accumulated Depreciation (xóa khấu hao lũy kế)
│       Debit:  Cash/Receivable (giá bán)
│       Credit: Asset Cost (xóa nguyên giá)
│       Credit: Gain/Loss on Disposal (lãi/lỗ thanh lý)
│
└── Non-fixed asset (thường):
    ├── is_internal_transfer?
    │   → Bỏ qua, không ghi nhận doanh thu
    │
    ├── enable_deferred_revenue?
    │   → Credit Deferred Revenue Account (thay vì Income Account)
    │
    └── Thường:
        Credit: Income Account            ← base_net_amount
          against = self.customer
          cost_center = item.cost_center

Sau khi xử lý tất cả items, nếu update_stock=1 + perpetual inventory:
  → super().get_gl_entries() = StockController.get_gl_entries()
      Debit:  COGS / Expense Account      ← stock_value_difference
      Credit: Warehouse Account            ← stock_value_difference
```

#### 4.5.4. `make_precision_loss_gl_entry()`

Xử lý sai số làm tròn đa tiền tệ (base_net_total ≠ net_total × conversion_rate):

```
Debit:  Round Off Account              ← precision_loss
```

#### 4.5.5. `make_discount_gl_entries()`

Chỉ chạy khi `enable_discount_accounting = 1` trong Selling Settings:

```
Với mỗi item có discount_amount và discount_account:
  Debit:  Discount Account              ← discount_amount
  Credit: Income Account                ← discount_amount (giảm doanh thu)
```

#### 4.5.6. `make_loyalty_point_redemption_gle()`

Khi `redeem_loyalty_points = 1`:

```
Credit: Receivable Account             ← loyalty_amount (giảm công nợ)
Debit:  Loyalty Redemption Account     ← loyalty_amount (chi phí loyalty)
```

#### 4.5.7. `make_pos_gl_entries()`

Khi `is_pos = 1`:

Cho mỗi phương thức thanh toán (cash, card, v.v.):

```
Credit: Receivable Account             ← payment.base_amount (giảm công nợ)
Debit:  Payment Mode Account           ← payment.base_amount (ghi nhận tiền)
```

Nếu `post_change_gl_entries` được bật và có `change_amount`:

```
Debit:  Receivable Account             ← base_change_amount
Credit: Account for Change Amount      ← base_change_amount
```

#### 4.5.8. `make_write_off_gl_entry()`

Chỉ cho POS (is_pos = 1):

```
Credit: Receivable Account             ← base_write_off_amount
Debit:  Write Off Account              ← base_write_off_amount
```

#### 4.5.9. `make_gle_for_rounding_adjustment()`

Nếu có rounding adjustment:

```
Credit: Round Off Account              ← base_rounding_adjustment
```

#### 4.5.10. `make_internal_transfer_gl_entries()`

Cho inter-company transfer có taxes:

```
Debit:  Unrealized Profit/Loss Account   ← total_taxes_and_charges
```

### 4.6. GL Entry Chuẩn cho SI

**Hóa đơn bán hàng thường (Stock item, perpetual inventory):**

```
Debit:  Receivable Account (Customer)   ← base_grand_total
Credit: Income Account                  ← base_net_total (doanh thu)
Credit: Tax Account                     ← base_total_taxes (thuế đầu ra)
--- Nếu perpetual inventory + update_stock ---
Debit:  COGS Account                    ← stock_value_difference
Credit: Warehouse Account               ← stock_value_difference
```

**Hóa đơn POS (bán lẻ thu tiền ngay):**

```
Debit:  Receivable Account              ← base_grand_total
Credit: Income Account                  ← base_net_total
Credit: Tax Account                     ← taxes
Debit (POS): Cash/Bank Account          ← payment amount
Credit (POS): Receivable Account        ← payment amount
```

**Hóa đơn trả hàng (Credit Note):**

```
Credit: Receivable Account              ← base_grand_total (đảo ngược)
Debit:  Income Account                  ← base_net_total (đảo ngược)
Debit:  Tax Account                     ← taxes (đảo ngược)
```

**Hóa đơn có Loyalty Redemption:**

```
Debit:  Receivable Account              ← grand_total - loyalty
Credit: Income Account                  ← net_total
Credit: Tax Account                     ← taxes
Credit: Receivable Account              ← loyalty_amount
Debit:  Loyalty Redemption Account      ← loyalty_amount
```

### 4.7. Discount Accounting

Khi `enable_discount_accounting = 1` trong Selling Settings:

- Mỗi item có `discount_amount` và `discount_account`
- Discount được hạch toán riêng (không net vào income):

```
GL entries bổ sung:
  Debit:  Discount Account (item.discount_account)    ← discount_amount
  Credit: Income Account (item.income_account)        ← discount_amount

→ Income Account vẫn ghi nhận base_net_amount (chưa trừ discount)
→ Discount Account ghi nhận khoản chiết khấu
→ Net income = Income - Discount
```

**Lưu ý:** Khi discount accounting bật, `get_amount_and_base_amount()` trả về số tiền **đã bao gồm discount** khác với khi không bật.

### 4.8. Deferred Revenue (Doanh thu Chưa Thực hiện)

Khi `item.enable_deferred_revenue = 1`:

- Tại submit: `income_account` được thay bằng `deferred_revenue_account`
- Định kỳ chạy "Process Deferred Accounting" để kết chuyển dần:

```
Tại submit SI:
  Credit: Deferred Revenue Account      ← base_net_amount (thay vì Income)

Khi process deferred accounting (hàng tháng):
  Debit:  Deferred Revenue Account      ← phần doanh thu của tháng
  Credit: Income Account                ← phần doanh thu của tháng
```

### 4.9. Exchange Gain/Loss Journal từ SI

Sau khi GL entries được post, SI gọi `make_exchange_gain_loss_journal()`:

- Kiểm tra advance allocation có chênh lệch tỷ giá không
- Nếu có: tạo JE với `voucher_type = "Exchange Gain Or Loss"`

```python
def make_exchange_gain_loss_journal(self):
    # Kiểm tra từng advance allocation
    for advance in self.advances:
        if advance.exchange_gain_loss:
            # Tạo JE
            # Debit/Credit: Receivable Account
            # Debit/Credit: Exchange Gain/Loss Account
```

Chênh lệch tỷ giá trên hóa đơn gốc (không qua advance) chỉ được ghi nhận tại thời điểm **Payment Entry** (khi khách hàng thanh toán với tỷ giá khác).

### 4.10. Advance Payment Allocation

Khi SI submit, nếu có advance payments (đã nhận trước từ khách hàng), `update_against_document_in_jv()` xử lý phân bổ:

```
1. Với mỗi dòng trong self.advances có allocated_amount > 0:
2. Lấy Journal Entry / Payment Entry gốc
3. Gọi reconcile_against_document():
   a. Hủy JE cũ (nếu là JE)
   b. Tạo JE mới — tách thành 2 phần: allocated + unallocated
   c. Ghi nhận exchange gain/loss nếu multi-currency
4. Cập nhật outstanding trên advance document
```

### 4.11. Cập nhật Outstanding Amounts

Sau GL entries được tạo:

- `update_outstanding = "Yes"` → GL Engine tự động tạo Payment Ledger Entry
- `update_outstanding = "No"` (POS/Write-off/Loyalty) → gọi thủ công `update_voucher_outstanding()`

Outstanding amount = tổng Payment Ledger entries cho (voucher, account, party):

```sql
SELECT SUM(amount) FROM `tabPayment Ledger Entry`
WHERE against_voucher_type = 'Sales Invoice'
  AND against_voucher = 'SINV-xxxxx'
  AND company = '...'
```

- Invoice tạo Payment Ledger Entry với `amount = base_grand_total` (dương)
- Payment tạo với `amount = -allocated_amount` (âm)
- Outstanding = tổng các amount


---

## 5. Deferred Revenue

**File:** `erpnext/accounts/deferred_revenue.py`

### 5.1. Khi nào áp dụng?

Khi item trên Sales Invoice có `enable_deferred_revenue = 1`:

- Doanh thu chưa được ghi nhận ngay
- Thay vào đó, ghi vào tài khoản **Deferred Revenue Account** (công nợ phải trả)
- Định kỳ kết chuyển dần sang Income Account

### 5.2. Tại SI Submit

```python
# Trong make_item_gl_entries() của Sales Invoice:
income_account = (
    item.income_account
    if (not item.enable_deferred_revenue or self.is_return)
    else item.deferred_revenue_account   # ← Ghi vào deferred thay vì income
)
```

GL Entry:

```
Credit: Deferred Revenue Account        ← base_net_amount
```

### 5.3. Xử lý Định kỳ — `book_deferred_income_or_expense()`

**Trigger:** "Process Deferred Accounting" doctype (Scheduled Job hoặc thủ công)

```python
def book_deferred_income_or_expense(doc):
    # Tính số tiền deferred cho kỳ hiện tại
    for item in doc.items:
        if item.enable_deferred_revenue and item.service_start_date and item.service_end_date:
            # Phân bổ theo ngày hoặc theo tháng
            if based_on = "Months":
                monthly_amount = base_amount / total_months
            elif based_on = "Days":
                monthly_amount = base_amount * (days_in_period / total_days)

            # Tạo GL entries
            make_gl_entries([
                {
                    "account": deferred_revenue_account,
                    "debit": monthly_amount,           # Giảm deferred
                    "cost_center": item.cost_center,
                },
                {
                    "account": income_account,
                    "credit": monthly_amount,          # Ghi nhận doanh thu
                    "cost_center": item.cost_center,
                }
            ])
```

Nếu `book_deferred_entries_via_journal_entry = 1`:

```python
def book_revenue_via_journal_entry():
    # Tạo Journal Entry thay vì GL Entry trực tiếp
    JE: voucher_type = "Deferred Revenue"
        Debit:  Deferred Revenue Account   ← monthly_amount
        Credit: Income Account             ← monthly_amount
```

### 5.4. GL Entries Định kỳ

```
Mỗi kỳ (tháng):
  Debit:  Deferred Revenue Account        ← monthly_amount
  Credit: Income Account                  ← monthly_amount

→ Deferred Revenue giảm dần
→ Income tăng dần
→ Đến cuối kỳ dịch vụ: Deferred Revenue = 0, Income = tổng doanh thu
```

---

## 6. Payment Entry (Receive)

**File:** `erpnext/accounts/doctype/payment_entry/payment_entry.py`
**Class:** `PaymentEntry(AccountsController)`

### 6.1. Payment Type = "Receive"

"Receive" dùng để ghi nhận tiền thu từ khách hàng, giảm công nợ phải thu.

### 6.2. Vòng đời

#### `on_submit(self)`:

```
1. super().on_submit()
2. make_gl_entries()                    ← ⭐ GL Entries
3. update_outstanding_amounts()         ← Cập nhật outstanding trên SIs
4. update_payment_schedule()
5. update_advance_paid()                ← Cập nhật advance_paid trên SO/SI
```

#### `on_cancel(self)`:

```
1. make_gl_entries(cancel=1)            ← Đảo ngược GL
2. update_outstanding_amounts()         ← Khôi phục outstanding
3. delink_advance_entry_references()
```

### 6.3. `build_gl_map()` cho Receive

```python
def build_gl_map(self):
    gl_entries = []
    1. add_party_gl_entries(gl_entries)    # Credit Receivable
    2. add_bank_gl_entries(gl_entries)     # Debit Bank
    3. add_deductions_gl_entries(gl_entries)
    4. add_tax_gl_entries(gl_entries)
    return gl_entries
```

### 6.4. Chi tiết GL Entries (Receive mode)

#### `add_party_gl_entries()` — Credit Receivable

```python
dr_or_cr = "credit"  # Receivable là Asset → credit để giảm

for each reference (Sales Invoice):
  Credit: Receivable Account (self.party_account)  ← allocated_amount
    against_voucher_type = d.reference_doctype (Sales Invoice)
    against_voucher = d.reference_name
    party_type = "Customer"
    party = self.party

if unallocated_amount:
  Credit: Receivable Account              ← base_unallocated_amount
  (không có against_voucher — outstanding balance)
```

#### `add_bank_gl_entries()` — Debit Bank

```
Debit:  Paid To Account (Bank/Cash)      ← base_received_amount
```

#### `add_deductions_gl_entries()` — Phí

```
Debit:  Deduction Account               ← amount
```

#### `add_tax_gl_entries()` — Thuế

```
If Add:
  Debit:  Tax Account                   ← tax_amount
If Deduct:
  Credit: Tax Account                   ← tax_amount
```

### 6.5. GL Entry Chuẩn cho PE (Receive)

**Thu tiền từ khách hàng (Receive — có tham chiếu):**

```
Debit:  Bank Account                    ← received_amount (tiền vào)
Credit: Receivable Account (Customer)   ← allocated_amount (giảm công nợ)
```

**Thu tiền không có tham chiếu (unallocated):**

```
Debit:  Bank Account                    ← received_amount
Credit: Receivable Account (Customer)   ← received_amount
  → outstanding balance dương trên Receivable = tiền khách hàng còn dư
```

### 6.6. Exchange Gain/Loss trên PE

Tính toán chênh lệch tỷ giá:

```python
# Trong calculate_base_allocated_amount_for_reference():
allocated_amount_in_company_currency = d.allocated_amount × source_exchange_rate
base_allocated_amount = d.allocated_amount × reference_exchange_rate
# (reference_exchange_rate = tỷ giá của SI gốc)

d.exchange_gain_loss = base_allocated_amount - allocated_amount_in_company_currency
```

Sau GL entries, `make_exchange_gain_loss_journal()` tạo JE:

```
Với mỗi reference có exchange_gain_loss != 0:
  Tạo Journal Entry (voucher_type = "Exchange Gain Or Loss"):

    Nếu là Receive + gain (lãi):
      Debit:  Receivable Account         ← exchange_gain_loss
      Credit: Exchange Gain/Loss Account ← exchange_gain_loss

    Nếu là Receive + loss (lỗ):
      Credit: Receivable Account         ← exchange_gain_loss
      Debit:  Exchange Gain/Loss Account ← exchange_gain_loss
```

### 6.7. Cập nhật Outstanding Amounts

```python
def update_outstanding_amounts(self):
    for d in self.get("references"):
        update_voucher_outstanding(
            d.reference_doctype,           # "Sales Invoice"
            d.reference_name,              # "SINV-xxxx"
            account=self.party_account,    # Receivable Account
            party_type="Customer",
            party=self.customer,
        )
```

---

## 7. Journal Entry

**File:** `erpnext/accounts/doctype/journal_entry/journal_entry.py`
**Class:** `JournalEntry(AccountsController)`

### 7.1. Vai trò trong Luồng Bán hàng

JE được dùng trong các tình huống:

| Mục đích | Ví dụ |
|----------|-------|
| Ghi nhận advance từ khách hàng | Debit Bank, Credit Receivable (unallocated) |
| Điều chỉnh doanh thu | Debit Income, Credit Receivable |
| Kết chuyển deferred revenue | Debit Deferred Revenue, Credit Income |
| Xóa nợ khách hàng | Debit Bad Debt, Credit Receivable |
| Ghi nhận lãi/lỗ tỷ giá | Debit/Credit Exchange G/L Account |

### 7.2. Advance Payment bằng Journal Entry

Khi khách nhận advance qua JE (không qua Payment Entry):

```
Debit:  Bank Account                    ← amount
Credit: Receivable Account (Customer)  ← amount
  (against_voucher_type = "Sales Order")
  (against_voucher = SO-xxxx)

→ SO.advance_paid tăng lên
→ Khi SI submit, advance được allocate qua update_against_document_in_jv()
```

### 7.3. Xóa nợ Khách hàng

```
Debit:  Bad Debt Expense / Allowance    ← outstanding_amount
Credit: Receivable Account (Customer)  ← outstanding_amount
```

---

## 8. Exchange Rate Revaluation

**File:** `erpnext/accounts/doctype/exchange_rate_revaluation/exchange_rate_revaluation.py`
**Class:** `ExchangeRateRevaluation(Document)`

(Luồng giống hệt bên mua — xem tài liệu accounting_purchase_full_flow.md)

### 8.1. Tác động đến tài khoản Bán hàng

Các tài khoản bán hàng bị ảnh hưởng bởi revaluation:

| Tài khoản | Root Type | Loại |
|-----------|-----------|------|
| Receivable (Debtors) | Asset | Ngoại tệ |
| Income Account | Income | (thường không reval — là P&L) |
| Tax Account (VAT Payable) | Liability | Có thể reval |
| Deferred Revenue | Liability | Có thể reval |
| Bank Account (NH ngoại tệ) | Asset | Có thể reval |

### 8.2. Ví dụ Revaluation cho Receivable

**Giả sử:** Receivable (Debtors - USD) có số dư 10,000 USD, tỷ giá cũ 23,000, tỷ giá mới 24,500.

**Gain/Loss** = 10,000 × (24,500 - 23,000) = 15,000,000 (lãi chưa thực hiện)

```
Revaluation JV:

Row 1: Debtors - USD         Debit: 10,000 USD  @ 24,500 (= 245,000,000 VND)
Row 2: Debtors - USD         Credit: 10,000 USD @ 23,000 (= 230,000,000 VND)
Row 3: Unrealized Exch Gain  Credit: 15,000,000 VND

→ Net: Debtors tăng 15,000,000 VND
      Unrealized Gain ghi nhận 15,000,000 VND
```

---

## 9. GL Engine Trung tâm

**File:** `erpnext/accounts/general_ledger.py`

(Chi tiết xem tài liệu accounting_purchase_full_flow.md — phần này giống hệt)

### 9.1. `make_gl_entries()`

Entry point cho mọi doctype:

```python
def make_gl_entries(gl_map, cancel=0, adv_adj=0, merge_entries=True,
                    update_outstanding="Yes", from_repost=False):
    if cancel:
        make_reverse_gl_entries(...)
        return

    validate_accounting_periods(gl_map)
    validate_disabled_accounts(gl_map)
    gl_map = process_gl_map(gl_map, merge_entries)

    if update_outstanding == "Yes":
        from erpnext.accounts.doctype.payment_ledger import payment_ledger
        payment_ledger.create_payment_ledger_entries(gl_map)  # ← Tạo Payment Ledger

    save_entries(gl_map, adv_adj, update_outstanding, from_repost)
```

### 9.2. Payment Ledger cho Sales

Khi SI/PE được tạo với `update_outstanding = "Yes"`, Payment Ledger tạo entries:

**Sales Invoice:**
```
Payment Ledger Entry:
  posting_date, account=Receivable, party_type=Customer, party=customer
  amount = +base_grand_total (dương = invoice)
  against_voucher_type = "Sales Invoice"
  against_voucher = SI name
```

**Payment Entry (Receive):**
```
Payment Ledger Entry:
  posting_date, account=Receivable, party_type=Customer, party=customer
  amount = -allocated_amount (âm = payment)
  against_voucher_type = "Sales Invoice"
  against_voucher = SI name
```

**Outstanding = SUM(amount):**
- Nếu > 0: khách còn nợ
- Nếu = 0: đã thanh toán đủ
- Nếu < 0: khách trả thừa (credit balance)

---

## 10. Bảng tổng hợp Tài khoản Kế toán

### 10.1. Ma trận GL Entry Bán hàng

| Giai đoạn | Tình huống | Debit | Credit |
|-----------|-----------|-------|--------|
| **DN** | Xuất kho (perpetual inventory) | COGS / Expense Account | Warehouse Account |
| **DN** | Internal transfer | Target WH Account | Source WH Account |
| **DN** | DN Return | Warehouse Account | COGS / Expense Account |
| **SI** | Ghi nhận công nợ | Receivable Account | — |
| **SI** | Ghi nhận doanh thu (thường) | — | Income Account |
| **SI** | Ghi nhận doanh thu (deferred) | — | Deferred Revenue Account |
| **SI** | Thuế đầu ra | — | Tax Account |
| **SI** | COGS (perpetual + update_stock) | COGS / Expense Account | Warehouse Account |
| **SI** | Discount accounting | Discount Account | Income Account |
| **SI** | Loyalty redemption | Loyalty Redemption Account | Receivable Account |
| **SI** | POS payment | Cash/Bank Account | Receivable Account |
| **SI** | POS write-off | Write Off Account | Receivable Account |
| **SI** | POS change amount | Receivable Account | Change Amount Account |
| **SI** | Rounding adjustment | — | Round Off Account |
| **SI** | Precision loss | Round Off Account | — |
| **SI** | Internal transfer (tax) | Unrealized P/L Account | — |
| **SI** | Fixed asset disposal | Accum. Depr + Receivable | Asset Cost + Gain/Loss |
| **SI** | Return (Credit Note) | Income Account + Tax | Receivable Account |
| **Deferred** | Kết chuyển deferred → income | Deferred Revenue Account | Income Account |
| **PE** | Thu tiền từ KH | Bank Account | Receivable Account |
| **PE** | Phí ngân hàng | Deduction Account | — |
| **PE** | Thuế (Add) | Tax Account | — |
| **PE** | Thuế (Deduct) | — | Tax Account |
| **PE** | Chênh lệch tỷ giá (realized) | Receivable / Exch G/L | Exch G/L / Receivable |
| **JE** | Advance từ KH | Bank Account | Receivable Account |
| **JE** | Xóa nợ | Bad Debt Account | Receivable Account |
| **ERR** | Zero balance JV | Account (ngoại tệ) | Unrealized Exch G/L |
| **ERR** | Revaluation JV | Account @ rate mới | Account @ rate cũ + Unrealized G/L |

### 10.2. Bảng Tài khoản Đặc biệt

| Tài khoản | Cấu hình ở đâu | Mục đích |
|-----------|---------------|----------|
| Receivable (Debtors) | Company / Customer | Công nợ phải thu KH |
| Income Account | Item Defaults | Doanh thu bán hàng |
| Deferred Revenue Account | Item Defaults | Doanh thu chưa thực hiện |
| COGS / Default Expense | Company | Giá vốn hàng bán |
| Warehouse Account | Warehouse | Tài khoản hàng tồn kho |
| Round Off Account | Company | Sai số làm tròn |
| Write Off Account | Company | Xóa nợ POS |
| Discount Account | Item (Selling) | Chiết khấu bán hàng |
| Loyalty Redemption Acct | Loyalty Program | Chi phí loyalty |
| Unrealized P/L | Company | Chuyển giá nội bộ |
| Exchange Gain/Loss | Company | Lãi/lỗ tỷ giá thực hiện |
| Unrealized Exch G/L | Company | Lãi/lỗ tỷ giá chưa thực hiện |
| Bad Debt Account | Company | Nợ xấu |


---

## 11. Tóm tắt Luồng End-to-End

### 11.1. Luồng Chi tiết từng Bước

**Bước 1: Sales Order (Đơn hàng)**

```
Người dùng: tạo SO, chọn customer, items, số lượng, đơn giá
Hệ thống: validate, check credit limit, update reserved_qty
Kế toán: KHÔNG ảnh hưởng
Tồn kho (Bin): reserved_qty tăng lên
```

**Bước 2: Delivery Note (Giao hàng / Xuất kho)**

```
Người dùng: tạo DN từ SO, xác nhận giao hàng
Hệ thống:
  SLE: INSERT Stock Ledger Entry với actual_qty = -qty (xuất kho)
  SLE Engine: Tính outgoing_rate (FIFO / Moving Average)

  Nếu perpetual inventory:
    GL:
      Debit:  COGS / Expense Account   ← stock_value_difference
      Credit: Warehouse Account         ← stock_value_difference

  Repost: Nếu có SLE tương lai
Tồn kho (Bin): delivered_qty tăng, reserved_qty giảm
```

**Bước 3: Sales Invoice (Hóa đơn bán hàng — tài liệu kế toán chính)**

```
Người dùng: tạo SI từ DN (hoặc độc lập), xác nhận giá, thuế

Hệ thống:
  GL:
    Bước 1 — Công nợ & Doanh thu:
      Debit:  Receivable Account       ← base_grand_total
      Credit: Income Account            ← base_net_total
      Credit: Tax Account               ← total_taxes

    Bước 2 — Giá vốn (nếu perpetual + update_stock):
      Debit:  COGS / Expense Account    ← stock_value_difference
      Credit: Warehouse Account          ← stock_value_difference

    Bước 3 — Các bút toán bổ sung:
      [POS payments, Loyalty, Discount, Rounding, Write-off...]

  Payment Ledger: Tạo entry với amount = +base_grand_total
  Outstanding: base_grand_total — chưa thanh toán
  Advance allocation: phân bổ advance payments nếu có
```

**Bước 4: Payment Entry (Receive) — Thu tiền**

```
Người dùng: tạo PE, chọn SI, nhập số tiền thu
Hệ thống:
  GL:
    Debit:  Bank Account                ← received_amount
    Credit: Receivable Account          ← allocated_amount (giảm công nợ)

  Nếu có chênh lệch tỷ giá:
    → Journal Entry (Exchange Gain Or Loss)

  Payment Ledger: Tạo entry với amount = -allocated_amount
  Outstanding: giảm (hoặc về 0)
```

**Bước 5: Journal Entry (Điều chỉnh — nếu cần)**

```
Dùng cho: advance payments, xóa nợ, kết chuyển deferred revenue,
          điều chỉnh sai sót, ghi nhận lãi/lỗ tỷ giá
```

**Bước 6: Exchange Rate Revaluation (Đánh giá lại tỷ giá cuối kỳ)**

```
Chạy cuối tháng/quý/năm:
  ERR fetch tài khoản ngoại tệ (Receivable, Bank, Deferred Revenue...)
  Tính gain/loss theo tỷ giá mới
  Submit ERR → gọi Make Journal Entry
  2 JEs được tạo: Zero Balance + Revaluation
  Cả 2 ghi nhận vào Unrealized Exchange Gain/Loss
```

### 11.2. Sơ đồ Luồng GL Entry Tổng hợp

```
Thời gian ──────────────────────────────────────────────────────►

SO submit:
  (Không GL Entry)

DN submit (nếu perpetual):
  COGS (Dr) ───────────────────────────┐
  WH Account (Cr) ─────────────────────┤
                                        │
SI submit:
  Receivable (Dr) ─────────────────────┤
  Income (Cr) ─────────────────────────┤
  Tax (Cr) ────────────────────────────┤
  [COGS (Dr) + WH (Cr)] (nếu có)       │
  [POS payments / Loyalty / Discount]   │
                                        │
PE submit (Receive):
  Bank (Dr) ───────────────────────────┤
  Receivable (Cr) ─────────────────────┤
  + JE Exchange G/L (nếu có diff)       │
                                        │
ERR submit:
  + JE Zero Balance (nếu có)            │
  + JE Revaluation (nếu có)             │
  → Ghi nhận Unrealized G/L             │
                                        ▼
                               Period Closing Voucher
```

### 11.3. Vòng đời của Receivable

```
1. SI submit:
   Receivable (Dr) = base_grand_total
   → Outstanding = base_grand_total

2. PE submit (Receive — thanh toán 1 phần):
   Receivable (Cr) = allocated_amount
   → Outstanding = base_grand_total - allocated_amount

3. PE submit (Receive — thanh toán đủ):
   Receivable (Cr) = remaining_amount
   → Outstanding = 0

4. SI cancel (trước khi thanh toán):
   → make_reverse_gl_entries() — đảo ngược tất cả GL của SI
   → Receivable về 0

5. Write-off (xóa nợ):
   Credit Receivable (Dr âm = Cr dương)
   Outstanding về 0
```

### 11.4. Key File Paths

| Component | File Path |
|-----------|-----------|
| Sales Order | `erpnext/selling/doctype/sales_order/sales_order.py` |
| Delivery Note | `erpnext/stock/doctype/delivery_note/delivery_note.py` |
| Sales Invoice | `erpnext/accounts/doctype/sales_invoice/sales_invoice.py` |
| Deferred Revenue | `erpnext/accounts/deferred_revenue.py` |
| Payment Entry | `erpnext/accounts/doctype/payment_entry/payment_entry.py` |
| Journal Entry | `erpnext/accounts/doctype/journal_entry/journal_entry.py` |
| Exchange Rate Reval. | `erpnext/accounts/doctype/exchange_rate_revaluation/exchange_rate_revaluation.py` |
| GL Engine | `erpnext/accounts/general_ledger.py` |
| Stock Controller | `erpnext/controllers/stock_controller.py` |
| Accounts Controller | `erpnext/controllers/accounts_controller.py` |
| Selling Controller | `erpnext/controllers/selling_controller.py` |

---

## 12. Các Tình huống Đặc biệt

### 12.1. POS (Point of Sale)

POS Invoice là Sales Invoice với `is_pos = 1`:

- Phải có ít nhất 1 phương thức thanh toán
- Tạo GL entries payment ngay tại submit
- Có thể có write-off (xóa nợ POS)
- Có thể có change amount
- Không tạo outstanding (update_outstanding = "No")

### 12.2. Internal Transfer (Inter-Company)

Khi bán hàng giữa các công ty cùng tập đoàn:

- KHÔNG ghi nhận doanh thu (bỏ qua income account)
- KHÔNG ghi nhận công nợ (bỏ qua customer GL entry)
- Thuế được ghi vào Unrealized Profit/Loss Account
- Chỉ ghi nhận GL cho kho: Debit target WH, Credit source WH

### 12.3. Fixed Asset Disposal (Thanh lý Tài sản Cố định)

Khi bán tài sản cố định qua Sales Invoice:

- `get_gl_entries_on_asset_disposal()` tạo:
  - Debit: Accumulated Depreciation (xóa khấu hao lũy kế)
  - Credit: Asset Cost (xóa nguyên giá)
  - Credit: Gain on Disposal (nếu lãi)
  - Debit: Loss on Disposal (nếu lỗ)
- Nếu return: `get_gl_entries_on_asset_regain()` đảo ngược

### 12.4. Credit Note (Hóa đơn trả lại)

`is_return = True` trên Sales Invoice:

- Đảo ngược receivable: Credit Receivable (thay vì Debit)
- Đảo ngược doanh thu: Debit Income (thay vì Credit)
- Đảo ngược thuế: Debit Tax (thay vì Credit)
- Nếu update_stock: nhập lại kho (SLE với actual_qty = +qty)

### 12.5. Consolidated Invoice (POS Merge)

Khi POS Closing Entry gộp nhiều POS invoice thành 1 consolidated invoice:

- `is_consolidated = True`
- Không cho cancel riêng lẻ — phải cancel POS Closing Entry
- Loyalty points chỉ xử lý trên consolidated invoice

### 12.6. Common Party Accounting

Khi `enable_common_party_accounting` bật và Customer cũng là Supplier của công ty:

- Tạo Journal Entry tự động để bù trừ công nợ
- Debit Payable (giảm nợ NCC) = Credit Receivable (giảm nợ KH)

### 12.7. Loyalty Points

- Khi submit SI (không phải return): tạo Loyalty Point Entry
- Khi redeem: `make_loyalty_point_redemption_gle()` tạo GL:
  - Credit Receivable (giảm công nợ)
  - Debit Loyalty Redemption Account (chi phí)
- Khi cancel SI: xóa loyalty point entries tương ứng

---

_Tài liệu được tổng hợp từ mã nguồn ERPNext/Frappe (tháng 6/2026)._
_Phiên bản: v15+. Mục đích: tham khảo nội bộ._

