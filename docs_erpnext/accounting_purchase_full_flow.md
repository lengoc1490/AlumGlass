# Tài liệu Luồng Kế toán Mua hàng Đầy đủ: Purchase Order → Exchange Rate Revaluation

> Tài liệu này mô tả chi tiết toàn bộ logic kế toán từ Purchase Order, Purchase Receipt, Purchase Invoice, Landed Cost Voucher, Payment Entry, Journal Entry đến Exchange Rate Revaluation — bao gồm GL Entries, Stock Ledger, Outstanding, và các service liên quan.

---

## MỤC LỤC

1. [Sơ đồ Tổng quan Luồng Nghiệp vụ](#1-sơ-đồ-tổng-quan)
2. [Purchase Order — Không tạo GL Entry](#2-purchase-order)
3. [Purchase Receipt — Kế toán Hàng nhập kho](#3-purchase-receipt)
4. [Landed Cost Voucher — Điều chỉnh Giá vốn](#4-landed-cost-voucher)
5. [Purchase Invoice — Kế toán Công nợ Nhà cung cấp](#5-purchase-invoice)
6. [Payment Entry — Thanh toán Nhà cung cấp](#6-payment-entry)
7. [Journal Entry — Bút toán Điều chỉnh Tổng hợp](#7-journal-entry)
8. [Exchange Rate Revaluation — Đánh giá lại Tỷ giá](#8-exchange-rate-revaluation)
9. [GL Engine — process_gl_map và make_gl_entries](#9-gl-engine-trung-tâm)
10. [Bảng tổng hợp Tài khoản Kế toán theo Tình huống](#10-bảng-tổng-hợp-tài-khoản)
11. [Tóm tắt Luồng End-to-End](#11-tóm-tắt-luồng-end-to-end)

---

## 1. Sơ đồ Tổng quan

### 1.1. Chuỗi Kế thừa Class

```
PurchaseOrder        → BuyingController → SubcontractingController → StockController → AccountsController → TransactionBase → Document
PurchaseReceipt      → BuyingController → SubcontractingController → StockController → AccountsController → ...
PurchaseInvoice      → BuyingController → SubcontractingController → StockController → AccountsController → ...
LandedCostVoucher    → Document (không có AccountsController — không tự tạo GL Entry)
PaymentEntry         → AccountsController → TransactionBase → Document
JournalEntry         → AccountsController → TransactionBase → Document
ExchangeRateRevaluation → Document (không có AccountsController — tạo Journal Entry thay vì GL Entry trực tiếp)
```

### 1.2. Luồng Nghiệp vụ & Kế toán

```
Purchase Order (Đặt hàng)
  │
  │ → KHÔNG tạo GL Entry
  │ → Chỉ cập nhật committed_qty, ordered_qty trong Bin
  │
  ▼
Purchase Receipt (Nhận hàng)
  │
  │ → Tạo Stock Ledger Entries (SLE)
  │ → Tạo GL Entries:
  │     Debit:  Warehouse Account (giá trị hàng nhập)
  │     Credit: Stock Received But Not Billed (SRBNB)
  │     Credit: Valuation Tax Accounts (thuế tính vào giá vốn)
  │     Credit: Landed Cost Accounts (nếu có LCV cũ)
  │
  ▼
Landed Cost Voucher (Chi phí mua hàng phát sinh thêm — vận chuyển, bảo hiểm...)
  │
  │ → Hủy GL Entries cũ của PR
  │ → Cập nhật valuation_rate + SLE
  │ → Tạo lại GL Entries mới của PR với giá vốn điều chỉnh
  │
  ▼
Purchase Invoice (Hóa đơn mua hàng)
  │
  │ → Tạo GL Entries (điều chỉnh items, taxes)
  │     Debit:  Expense Account (chi phí hàng hóa)
  │     Debit:  Tax Accounts (thuế đầu vào)
  │     Credit: Payable Account / Supplier (công nợ nhà cung cấp)
  │
  │ → Nếu update_stock=1 + perpetual inventory:
  │     + Hủy bút toán SRBNB từ PR
  │     + Ghi nhận Expense Account thực tế
  │
  │ → Nếu is_paid=1: tạo thêm bút toán thanh toán
  │     Debit:  Payable Account (giảm công nợ)
  │     Credit: Cash/Bank Account
  │
  ▼
Payment Entry (Phiếu thanh toán)
  │
  │ → Tạo GL Entries:
  │     Debit:  Payable Account (giảm công nợ nhà cung cấp)
  │     Credit: Cash/Bank Account
  │
  │ → Nếu có chênh lệch tỷ giá: tạo thêm Journal Entry "Exchange Gain Or Loss"
  │
  ▼
Journal Entry (Bút toán điều chỉnh — tùy chọn)
  │
  │ → Debit/Credit trực tiếp các tài khoản kế toán
  │ → Dùng cho: điều chỉnh sai sót, phân bổ chi phí, kết chuyển...
  │
  ▼
Exchange Rate Revaluation (Đánh giá lại tỷ giá cuối kỳ)
  │
  │ → Không tạo GL Entry trực tiếp
  │ → Tạo Journal Entries:
  │     + Zero Balance JV: cho tài khoản có 1 bên = 0
  │     + Revaluation JV: cho tài khoản có số dư cả 2 loại tiền
  │     → Cả 2 đều ghi nhận vào Unrealized Exchange Gain/Loss Account
  │
  ▼
[Kết chuyển cuối kỳ — Realized Gain/Loss qua Period Closing Voucher]
```

---

## 2. Purchase Order

**File:** `erpnext/buying/doctype/purchase_order/purchase_order.py`
**Class:** `PurchaseOrder(BuyingController)`
**Cây kế thừa:** `BuyingController → SubcontractingController → StockController → AccountsController → TransactionBase → Document`

### 2.1. Vòng đời

| Sự kiện | Mô tả |
|---------|-------|
| `validate()` | Kiểm tra supplier, schedule dates, items, tax withholding, budget, subcontracting |
| `on_submit()` | Cập nhật `requested_qty`, `ordered_qty` trên Material Request Item, validate budget, update Blanket Order |
| `on_cancel()` | Đảo ngược các cập nhật trên |
| `update_status()` | Đổi trạng thái PO (On Hold, Closed, v.v.) |

### 2.2. ✅ GL Entries

**Purchase Order KHÔNG tạo GL Entries.** Nó là chứng từ kế hoạch mua hàng thuần túy, không ảnh hưởng đến số dư tài khoản kế toán.

Tuy nhiên, PO ảnh hưởng đến **Bin** (tồn kho khả dụng):
- Khi PO submit: `ordered_qty` trong Bin tăng lên.
- Khi PR submit: `ordered_qty` giảm, `received_qty` tăng.

> `ignore_linked_doctypes` trong `on_cancel` có chứa "GL Entry" — xác nhận PO không liên quan đến GL Entry.

### 2.3. Cập nhật Trạng thái

| Trạng thái PO | Ý nghĩa |
|---------------|---------|
| `Draft` | Chưa duyệt |
| `To Deliver and Bill` | Chờ nhận hàng và hóa đơn |
| `To Bill` | Đã nhận hàng, chờ hóa đơn |
| `Completed` | Đã nhận đủ và hóa đơn đủ |
| `On Hold` | Tạm giữ (không cho tạo PR/PI mới) |
| `Closed` | Đóng (kết thúc) |
| `Cancelled` | Hủy |

---

## 3. Purchase Receipt

**File:** `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py`
**Services:**
- `services/gl_composer.py` → `PurchaseReceiptGLComposer`
- `services/provisional_accounting.py` → `ProvisionalAccountingService`
- `services/billing_status.py` → `BillingStatusService`
- `services/stock_reservation.py` → `StockReservationService`

**Class:** `PurchaseReceipt(BuyingController)`

### 3.1. Cấu hình StatusUpdater

Trong `__init__`, PR thiết lập `status_updater` để đồng bộ số lượng tích lũy lên các chứng từ liên kết:

| Source | Source Field | Target | Target Field | Mục đích |
|--------|-------------|--------|-------------|----------|
| PR Item | `received_qty` | PO Item | `received_qty` | Tính `per_received` trên PO |
| PR Item | `stock_qty` | Material Request Item | `received_qty` | Cập nhật tiến độ MR |
| PR Item | `received_qty` | PI Item | `received_qty` | Đồng bộ với Purchase Invoice |
| PR Item | `received_qty` | Delivery Note Item | `received_qty` | Internal transfer |

Khi `is_return = True`:
| Source | Source Field | Target | Target Field |
|--------|-------------|--------|-------------|
| PR Item (return) | `-1 * qty` | PO Item | `returned_qty` |
| PR Item (return) | `-1 * received_stock_qty` | PR Item gốc | `returned_qty` + `per_returned` |

### 3.2. Vòng đời

#### `on_submit(self)` — Thứ tự thực thi:

```
1. super().on_submit()               → BuyingController.on_submit()
2. validate_approving_authority()    → Kiểm tra quyền duyệt
3. update_prevdoc_status()          → Cập nhật received_qty lên PO/MR
4. update_billing_status()          → Tính per_billed, set status
5. make_bundle_for_sales_purchase_return()  → Serial/Batch Bundle
6. make_bundle_using_old_serial_batch_fields()
7. update_stock_ledger()            → ⭐ Tạo SLE (phải chạy sau bước 3)
8. make_gl_entries()                → ⭐ Tạo GL Entries
9. repost_future_sle_and_gle()      → Repost SLE/GLE tương lai nếu cần
10. set_consumed_qty_in_subcontract_order()
11. StockReservationService.reserve_stock()
12. update_received_qty_if_from_pp()
```

#### `on_cancel(self)` — Đảo ngược:

```
1. before_cancel() → remove_amount_difference_with_purchase_invoice()
2. super().on_cancel()
3. check_for_on_hold_or_closed_status()
4. Kiểm tra không có PI đã nộp
5. update_prevdoc_status()           → Đảo ngược received_qty
6. update_billing_status()
7. update_stock_ledger()             → SLE hủy (actual_qty = -received_qty)
8. make_gl_entries_on_cancel()       → make_reverse_gl_entries()
9. repost_future_sle_and_gle()
10. delete_auto_created_batches()
11. set_consumed_qty_in_subcontract_order()
12. update_received_qty_if_from_pp()
```

### 3.3. Stock Ledger Entries (SLE)

`update_stock_ledger()` trong `BuyingController` tạo SLE cho từng dòng:

```
BuyingController.update_stock_ledger()
  → get_sl_entries(d, {...})
      actual_qty = +received_qty (nhập kho)
      incoming_rate = d.valuation_rate

  → Với internal transfer (from_warehouse):
      SLE âm tại from_warehouse (actual_qty = -received_qty)

  → Với rejected_qty:
      SLE dương tại rejected_warehouse (actual_qty = +rejected_qty)

  → Với is_return:
      actual_qty = -returned_qty
      outgoing_rate = get_rate_for_return() hoặc Moving Average

  → Với subcontracting:
      make_sl_entries_for_supplier_warehouse()
      SLE âm tại supplier_warehouse cho nguyên liệu tiêu thụ

  → make_sl_entries(sl_entries)
      → stock_ledger.make_sl_entries()
```

### 3.4. GL Entries — PurchaseReceiptGLComposer

**File:** `erpnext/stock/doctype/purchase_receipt/services/gl_composer.py`

`get_gl_entries()` → delegate cho `PurchaseReceiptGLComposer.compose()`:

```python
def compose(self, inventory_account_map=None, via_landed_cost_voucher=False):
    1. _make_item_gl_entries(gl_entries, inventory_account_map)
    2. _make_tax_gl_entries(gl_entries, via_landed_cost_voucher)
    3. doc.set_gl_entry_for_purchase_expense(gl_entries)
    4. update_regional_gl_entries(gl_entries, doc)
    5. process_gl_map(gl_entries, from_repost=...)
```

#### 3.4.1. `_make_item_gl_entries` — Per-Item Logic

```
Dòng mặt hàng d
├── Non-stock + provisional_accounting + có provisional_expense_account
│   └── add_provisional_gl_entry()
│       Debit:  Expense Account      ← base_amount
│       Credit: Provisional Account  ← base_amount
│
├── Stock item (perpetual inventory) HOẶC Fixed asset
│   │
│   ├── make_item_asset_inward_gl_entry()
│   │   Debit:  Warehouse/Asset Account  ← stock_value_diff (từ SLE)
│   │
│   ├── make_stock_received_but_not_billed_entry()
│   │   → Internal transfer: Credit from_warehouse_account
│   │   → Có PI liên kết + tỷ giá khác: thêm bút toán chênh lệch tỷ giá
│   │   → Thường: Credit SRBNB Account ← base_net_amount
│   │
│   ├── make_landed_cost_gl_entries()    (nếu có LCV amount)
│   │   Credit: LCV Account ← amount từ LCV
│   │
│   ├── make_amount_difference_entry()   (nếu có amount_difference_with_purchase_invoice)
│   │   Credit: SRBNB Account ← amount_difference
│   │
│   ├── make_sub_contracting_gl_entries() (nếu có rm_supp_cost)
│   │   Credit: Supplier Warehouse Account ← rm_supp_cost
│   │
│   └── make_divisional_loss_gl_entry()
│       Debit: Default Expense Account ← divisional_loss (sai số làm tròn)
│
└── Warehouse không có tài khoản → cảnh báo
```

#### 3.4.2. `_make_tax_gl_entries` — Thuế Valuation

Xử lý các dòng thuế có `category = "Valuation"` hoặc `"Valuation and Total"`:

```
Với từng dòng thuế valuation:
  Credit: Tax Account Head ← applicable_amount

Net effect: Thuế valuation được hạch toán thông qua kho (vào Warehouse Account)
chứ không qua chi phí trực tiếp.
```

#### 3.4.3. Bảng GL Entry Chuẩn cho PR

**Trường hợp Thường (Stock Item):**

```
Debit:  Warehouse Account     ← stock_value_difference (từ SLE)
Credit: SRBNB Account         ← base_net_amount
Credit: Tax Account (Valuation) ← item_tax_amount (nếu có)
```

**Trường hợp Non-Stock + Provisional Accounting:**

```
Debit:  Expense Account       ← base_amount
Credit: Provisional Account   ← base_amount
```

**Internal Transfer:**

```
Debit:  Target Warehouse Account    ← stock_value_diff
Credit: Source Warehouse Account    ← -outgoing_amount (debit âm, tức credit)
```

**Phiếu trả hàng (Return):**

```
Debit:  SRBNB Account     ← đảo ngược (credit âm)
Credit: Warehouse Account ← đảo ngược (debit âm)
```

### 3.5. Billing Status Service

**File:** `erpnext/stock/doctype/purchase_receipt/services/billing_status.py`

`update_billing_status()`:
1. Dòng có `purchase_invoice` trực tiếp: ghi `billed_amt = amount`.
2. Dòng có `purchase_order_item` (không có PI trực tiếp): phân bổ `billed_amt` từ PO theo **FIFO**.
3. Gọi `update_billing_percentage()` để tính `per_billed`.

Khi PI điều chỉnh giá (rate khác PR):
- `adjust_incoming_rate_for_pr()`:
  1. `update_valuation_rate(reset_outgoing_rate=False)` — tính lại valuation rate.
  2. `enable_recalculate_rate_in_sles()` — set `recalculate_rate = 1` trên SLE.
  3. `repost_future_sle_and_gle(force=True)` — cập nhật SLE/GLE.

### 3.6. Trạng thái Purchase Receipt

| Trạng thái | Điều kiện |
|------------|-----------|
| `Draft` | docstatus = 0 |
| `To Bill` | Đã nộp, `per_billed < 100` |
| `Completed` | Đã nộp, `per_billed = 100` |
| `Return` | `is_return = True` |
| `Return Issued` | Đã có phiếu trả hàng |
| `Closed` | Đóng thủ công |
| `Cancelled` | docstatus = 2 |

---

## 4. Landed Cost Voucher

**File:** `erpnext/stock/doctype/landed_cost_voucher/landed_cost_voucher.py`
**Class:** `LandedCostVoucher(Document)` — kế thừa trực tiếp từ `Document`, KHÔNG có `AccountsController`

### 4.1. Vòng đời

| Sự kiện | Mô tả |
|---------|-------|
| `validate()` | Kiểm tra receipt documents, gọi `init_landed_taxes_and_totals()`, `set_applicable_charges_on_item()` |
| `on_submit()` | Gọi `validate_applicable_charges_for_item()` → `update_landed_cost()` |
| `on_cancel()` | Gọi `update_landed_cost()` — cùng method, docstatus quyết định chiều xử lý |

### 4.2. Core Logic — `update_landed_cost()`

Đây là phương thức quan trọng nhất. Nó **không tạo GL Entry riêng** cho LCV, mà **hủy và tạo lại GL Entries của PR** với giá vốn điều chỉnh.

```python
def update_landed_cost(self):
    for d in self.get("purchase_receipts"):
        doc = frappe.get_doc(d.receipt_document_type, d.receipt_document)

        # 1. Set landed_cost_voucher_amount trên PR Item
        doc.set_landed_cost_voucher_amount()

        # 2. Tính lại valuation_rate
        doc.update_valuation_rate(reset_outgoing_rate=False)

        # 3. Ghi từng dòng PR Item
        for item in doc.get("items"):
            item.db_update()

        # 4. Cập nhật purchase_rate trên Serial No (non-asset)
        self.update_rate_in_serial_no_for_non_asset_items(doc)

    for d in self.get("purchase_receipts"):
        doc = frappe.get_doc(d.receipt_document_type, d.receipt_document)

        # 5. HỦY: tạo SLE + GL đảo ngược (docstatus=2)
        doc.docstatus = 2
        doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
        doc.make_gl_entries_on_cancel()

        # 6. TẠO LẠI: SLE + GL mới (docstatus=1)
        doc.docstatus = 1
        doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
        if d.receipt_document_type == "Purchase Receipt":
            doc.make_gl_entries(via_landed_cost_voucher=True)
        else:
            doc.make_gl_entries()
        doc.repost_future_sle_and_gle()
```

### 4.3. Ảnh hưởng đến GL Entries của PR

Trước LCV:

```
Debit:  Warehouse Account     ← value gốc
Credit: SRBNB Account         ← value gốc
```

Sau LCV khi PR GL được tạo lại (với tham số `via_landed_cost_voucher=True`):

```
Debit:  Warehouse Account     ← value GỐC + landed_cost_voucher_amount
Credit: SRBNB Account         ← value gốc
Credit: LCV Account           ← landed_cost_voucher_amount (từ LCV entries)
```

Net effect: Giá trị kho tăng thêm phần chi phí mua hàng, đối ứng vào tài khoản chi phí của LCV thay vì SRBNB.

### 4.4. Phân bổ Chi phí

Chi phí LCV được phân bổ dựa trên trường `distribute_charges_based_on`:
- `Qty` (số lượng): theo tỷ lệ số lượng từng item
- `Amount` (giá trị): theo tỷ lệ base_amount từng item
- `Distribute Manually`: người dùng tự nhập

```python
def set_applicable_charges_on_item(self):
    for item in self.get("items"):
        # Tính applicable_charges dựa trên tỷ lệ
        item.applicable_charges = total_charges * (item.qty_or_amount / grand_total_qty_or_amount)
```

### 4.5. Điểm đặc biệt

| Tính chất | Mô tả |
|-----------|-------|
| `is_submittable` | Có — LCV là submittable document |
| Tạo GL Entry trực tiếp? | KHÔNG — thông qua việc hủy/tạo lại GL của PR |
| Ảnh hưởng đến SLE | Có — gọi `update_stock_ledger()` với `via_landed_cost_voucher=True` |
| Repost | Gọi `repost_future_sle_and_gle()` sau khi tạo lại GL |
| Serial No | Cập nhật `purchase_rate` trên Serial No cho non-asset items |


---

## 5. Purchase Invoice

**File:** `erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py`
**Class:** `PurchaseInvoice(BuyingController)`

### 5.1. Cấu hình Khởi tạo

Trong `__init__`, PI thiết lập `status_updater` để đồng bộ lên PR và PO:

| Source | Source Field | Target | Target Field |
|--------|-------------|--------|-------------|
| PI Item | `qty` | PR Item | `billed_qty` |
| PI Item | `qty` | PO Item | `billed_qty` |

PI cũng quản lý các biến trạng thái quan trọng:
- `credit_to` — tài khoản phải trả (Payable Account)
- `against_expense_account` — chuỗi nối các tài khoản chi phí
- `auto_accounting_for_stock` — perpetual inventory được bật?

### 5.2. Vòng đời

#### `on_submit(self)` — Thứ tự thực thi:

```
1. super().on_submit()
2. check_prev_docstatus()
3. update_status_updater_args()
4. update_prevdoc_status()              → Cập nhật billed_qty lên PR/PO
5. update_against_document_in_jv()
6. update_billing_status_for_zero_amount_refdoc("PR")
7. update_billing_status_for_zero_amount_refdoc("PO")
8. update_billing_status_in_pr()
9. [Nếu update_stock=1]: update_stock_ledger()
10. [Nếu update_stock=1]: set_consumed_qty_in_subcontract_order()
11. [Nếu update_stock=1]: update_serial_nos_after_submit()
12. make_gl_entries()                   ← ⭐ Tạo GL Entries
13. [Nếu update_stock=1]: repost_future_sle_and_gle()
14. update_project()
15. update_linked_doc()
16. update_advance_tax_references()
17. process_common_party_accounting()
```

#### `on_cancel(self)`:

```
1. check_if_return_invoice_linked_with_payment_entry()
2. super().on_cancel()
3. check_on_hold_or_closed_status()
4. update_prevdoc_status()              ← Đảo ngược billed_qty
5. update_billing_status_in_pr()
6. [Nếu update_stock=1]: update_stock_ledger() → SLE hủy
7. [Nếu update_stock=1]: delete_auto_created_batches()
8. make_gl_entries_on_cancel()
9. [Nếu update_stock=1]: repost_future_sle_and_gle()
10. db_set("status", "Cancelled")
```

### 5.3. `make_gl_entries()` — Orchestrator

```python
def make_gl_entries(self, gl_entries=None, from_repost=False):
    update_outstanding = "No" if (cint(self.is_paid) or self.write_off_account) else "Yes"

    if self.docstatus == 1:
        if not gl_entries:
            gl_entries = self.get_gl_entries()
        if gl_entries:
            make_gl_entries(
                gl_entries, update_outstanding=update_outstanding, merge_entries=False
            )
            self.make_exchange_gain_loss_journal()

    elif self.docstatus == 2:
        make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
        self.cancel_provisional_entries()    # ← Đánh is_cancelled=1 trên GL Entry của PR

    self.update_supplier_outstanding(update_outstanding)
```

### 5.4. `get_gl_entries()` — Thứ tự các bút toán

```python
def get_gl_entries(self, warehouse_account=None):
    gl_entries = []

    1. make_supplier_gl_entry(gl_entries)
    2. make_item_gl_entries(gl_entries)
    3. make_precision_loss_gl_entry(gl_entries)
    4. make_tax_gl_entries(gl_entries)
    5. make_internal_transfer_gl_entries(gl_entries)
    6. make_regional_gl_entries(gl_entries, self)
    7. merge_similar_entries(gl_entries)
    8. make_payment_gl_entries(gl_entries)
    9. make_write_off_gl_entry(gl_entries)
    10. make_gle_for_rounding_adjustment(gl_entries)

    return gl_entries
```

### 5.5. Chi tiết từng Bút toán

#### 5.5.1. `make_supplier_gl_entry()`

```
Credit: Payable Account (self.credit_to)  ← base_grand_total
  party_type = "Supplier"
  party = self.supplier
  against_voucher = self.name (hoặc return_against nếu is_return)
  against = self.against_expense_account
```

#### 5.5.2. `make_item_gl_entries()` — Logic chính

Cho từng dòng item, luồng xử lý phụ thuộc vào loại item và cấu hình:

```
item d
│
├── Stock item + update_stock=1 + perpetual inventory:
│   │
│   ├── from_warehouse (internal transfer):
│   │   Debit:  Target Warehouse Account  ← warehouse_debit_amount (valuation_rate × qty × conv_factor)
│   │   Credit: Source Warehouse Account  ← base_net_amount (debit âm)
│   │   [Thêm nếu không phải internal transfer]:
│   │   Debit:  Expense Account           ← base_net_amount
│   │
│   ├── Thường (không from_warehouse):
│   │   Debit:  Expense Account           ← warehouse_debit_amount
│   │
│   ├── Stock adjustment entry (nếu warehouse_debit_amount ≠ stock value từ SLE):
│   │   Debit:  Cost of Goods Sold Account ← chênh lệch
│   │   + set warehouse_debit_amount = stock_amount (từ SLE)
│   │
│   ├── Landed cost entries (nếu có LCV):
│   │   Credit: LCV Account               ← base_amount từ landed_cost_entries
│   │
│   └── Subcontracting (nếu có rm_supp_cost):
│       Credit: Supplier Warehouse Account ← rm_supp_cost
│
├── Stock item (không update_stock):
│   Debit:  Expense Account               ← base_net_amount
│
├── Non-stock item (provisional accounting):
│   Debit:  Expense Account               ← amount
│   [Thêm nếu có PR liên kết + provisional entry]:
│     Đảo ngược bút toán tạm của PR:
│       Debit:  Provisional Account       ← item_amount (reverse)
│       Credit: Expense Account           ← item_amount (reverse)
│
├── Non-stock item (không provisional):
│   Debit:  Expense Account               ← base_net_amount
│
└── Xử lý chênh lệch tỷ giá (nếu conversion_rate khác với PR):
    Debit:  Expense Account               ← discrepancy
    Credit: Exchange Gain/Loss Account    ← discrepancy
```

#### 5.5.3. `make_precision_loss_gl_entry()`

Xử lý sai số làm tròn trong tính toán số lượng.

#### 5.5.4. `make_tax_gl_entries()`

```
Với từng dòng thuế:
│
├── Category = "Total" hoặc "Valuation and Total":
│   Debit:  Tax Account Head              ← base_amount (nếu add_deduct_tax = "Add")
│   Credit: Tax Account Head              ← base_amount (nếu add_deduct_tax = "Deduct")
│
├── Category = "Valuation" hoặc "Valuation and Total" (auto accounting):
│   [Tích lũy valuation_tax, phát hành sau]
│   Credit: Tax Account Head              ← valuation tax amount
│   (đối ứng với negative_expense_to_be_booked đã ghi nhận từ item entries)
│
└── Nếu update_stock=1 + perpetual:
    Credit: Tax Account Head              ← valuation_tax[tax] (ghi lần 2 cho stock items)
```

#### 5.5.5. `make_internal_transfer_gl_entries()`

```
Nếu internal transfer và có taxes:
  Credit: Unrealized Profit/Loss Account  ← total_taxes_and_charges
```

#### 5.5.6. `make_payment_gl_entries()`

Chỉ chạy khi `is_paid = 1`:

```
Debit:  Payable Account                   ← base_paid_amount (giảm công nợ)
Credit: Cash/Bank Account                 ← base_paid_amount
```

#### 5.5.7. `make_write_off_gl_entry()`

```
Debit:  Payable Account                   ← base_write_off_amount
Credit: Write Off Account                 ← base_write_off_amount
```

#### 5.5.8. `make_gle_for_rounding_adjustment()`

```
Debit:  Round Off Account                 ← base_rounding_adjustment
```

### 5.6. Exchange Gain/Loss Journal từ PI

Sau khi GL entries được tạo, PI gọi `make_exchange_gain_loss_journal()` — phương thức này được kế thừa từ `AccountsController`:

```python
def make_exchange_gain_loss_journal(self):
    # Xác định chênh lệch tỷ giá giữa PI và Payment Entry tham chiếu
    # Tạo Journal Entry voucher_type="Exchange Gain Or Loss" nếu có chênh lệch
```

Phương thức này kiểm tra:
- PI có liên kết Payment Entry hoặc advance không?
- Tỷ giá giữa PI và các tham chiếu đó khác nhau không?
- Nếu có: tạo JE ghi nhận lãi/lỗ chênh lệch tỷ giá đã thực hiện.

### 5.7. GL Entry Chuẩn cho PI

**KPI thường (Stock item, update_stock=1, có PR):**

```
Debit:  Expense Account                ← base_net_amount (xóa SRBNB, ghi nhận chi phí)
Credit: Payable Account (Supplier)     ← base_grand_total
  [+ Tax entries, + Rounding entries]
```

**KPI thường (Non-stock item, có provisional accounting + PR):**

```
Debit:  Provisional Account            ← amount (đảo ngược bút toán tạm từ PR)
Credit: Expense Account                ← amount (đảo ngược)
Debit:  Expense Account                ← amount (ghi nhận chi phí thực)
Credit: Payable Account (Supplier)     ← base_grand_total
```

**KPI với is_paid=1 (mua hàng trả tiền mặt):**

```
Debit:  Expense Account / Stock        ← value
Debit:  Tax Accounts                   ← tax
Credit: Cash/Bank Account              ← thanh toán ngay
```

**KPI trả hàng (Debit Note):**

```
Debit:  Payable Account (Supplier)     ← giảm công nợ
Credit: Expense Account / Stock        ← đảo ngược chi phí
```

### 5.8. Cancellation & Provisional Entries

Khi PI bị hủy (`on_cancel`), `cancel_provisional_entries()` đánh dấu `is_cancelled = 1` trên GL Entries của **Purchase Receipt** (không phải của PI):

```python
UPDATE `tabGL Entry`
SET is_cancelled = 1
WHERE voucher_type = 'Purchase Receipt'
  AND voucher_no IN (purchase_receipts)
  AND voucher_detail_no IN (pi_item_names)
```

Điều này khôi phục lại bút toán tạm thời của PR — khi PR được tạo lại (repost), bút toán tạm sẽ hiện lại.

### 5.9. Bảng GL Entry Mapping cho PI

| Tình huống | Debit | Credit |
|------------|-------|--------|
| Ghi nhận công nợ NCC | — | Payable Account |
| Chi phí hàng hóa (stock, có update_stock) | Expense Account | — |
| Chi phí hàng hóa (non-stock) | Expense Account | — |
| Internal transfer (from_warehouse → to_warehouse) | Target WH Account | Source WH Account |
| Điều chỉnh giá vốn (Stock adjustment) | COGS Account | — |
| Thuế GTGT đầu vào (Add) | Tax Account | — |
| Thuế (Deduct) | — | Tax Account |
| Internal transfer tax | — | Unrealized P/L Account |
| LCV từ PR cũ | — | LCV Account |
| Chi phí gia công (subcontract) | — | Supplier WH Account |
| Thanh toán ngay (is_paid) | Payable Account | Cash/Bank Account |
| Write-off | Payable Account | Write Off Account |
| Rounding adjustment | Round Off Account | — |
| Chênh lệch tỷ giá (PR ≠ PI rate) | Expense Account | Exchange Gain/Loss Account |
| Đảo ngược provisional (non-stock) | Provisional Account | Expense Account |


---

## 6. Payment Entry

**File:** `erpnext/accounts/doctype/payment_entry/payment_entry.py`
**Class:** `PaymentEntry(AccountsController)`

### 6.1. Các loại Payment Entry

| `payment_type` | Ý nghĩa |
|----------------|---------|
| `Pay` | Chi tiền — Thanh toán cho Supplier |
| `Receive` | Thu tiền — Nhận thanh toán từ Customer |
| `Internal Transfer` | Chuyển khoản nội bộ giữa 2 tài khoản ngân hàng/cash của cùng công ty |

### 6.2. Vòng đời

#### `on_submit(self)`:

```
1. super().on_submit()
2. make_gl_entries()                     ← ⭐ GL Entries
3. update_outstanding_amounts()          ← Cập nhật outstanding trên các tham chiếu
4. update_advance_paid()                 ← Cập nhật advance paid (PO/SO)
```

#### `on_cancel(self)`:

```
1. make_gl_entries(cancel=1)              ← Đảo ngược GL Entries
2. update_outstanding_amounts()          ← Khôi phục outstanding
3. delink_advance_entry_references()     ← Xóa liên kết advance
```

### 6.3. `make_gl_entries()` — Orchestrator

```python
def make_gl_entries(self, cancel=0, adv_adj=0):
    gl_entries = self.build_gl_map()
    gl_entries = process_gl_map(gl_entries)
    make_gl_entries(gl_entries, cancel=cancel, adv_adj=adv_adj)

    if cancel:
        cancel_exchange_gain_loss_journal(...)    # Hủy JE liên quan
    else:
        self.make_exchange_gain_loss_journal()    # Tạo JE nếu có chênh lệch tỷ giá
```

### 6.4. `build_gl_map()` — Thứ tự GL Entries

```python
def build_gl_map(self):
    gl_entries = []
    1. add_party_gl_entries(gl_entries)
    2. add_bank_gl_entries(gl_entries)
    3. add_deductions_gl_entries(gl_entries)
    4. add_tax_gl_entries(gl_entries)
    return gl_entries
```

#### 6.4.1. `add_party_gl_entries()`

Cho mỗi dòng tham chiếu (references) có `allocated_amount`:

**Payment Type = "Pay" (trả tiền cho Supplier):**
```
Debit:  Payable Account (Party Account)   ← allocated_amount_in_company_currency
  party_type = "Supplier"
  against_voucher = reference_name (PI number)
  against_voucher_type = "Purchase Invoice"
```

**Payment Type = "Receive" (thu tiền từ Customer):**
```
Credit: Receivable Account (Party Account) ← allocated_amount_in_company_currency
```

Nếu có `unallocated_amount` (số tiền không phân bổ):
```
Debit:  Payable Account [Pay]           ← base_unallocated_amount
  Credit: Receivable Account [Receive]
```

#### 6.4.2. `add_bank_gl_entries()`

**Payment Type = "Pay":**
```
Credit: Paid From Account (Bank/Cash)   ← base_paid_amount
```

**Payment Type = "Receive":**
```
Debit:  Paid To Account (Bank/Cash)     ← base_received_amount
```

**Payment Type = "Internal Transfer":**
```
Credit: Paid From Account               ← base_paid_amount
Debit:  Paid To Account                 ← base_received_amount
```

#### 6.4.3. `add_deductions_gl_entries()`

Cho mỗi dòng deduction (phí ngân hàng, phí giao dịch...):
```
Debit:  Deduction Account               ← amount
```

#### 6.4.4. `add_tax_gl_entries()`

Cho mỗi dòng tax (thuế GTGT, thuế TNCN...):
```
Payment Type = "Pay":
  Nếu Add:  Debit:  Tax Account          ← tax_amount
  Nếu Deduct: Credit: Tax Account        ← tax_amount
  Đối ứng: Party Account (ngược chiều)
```

### 6.5. Exchange Gain/Loss Journal từ PE

Sau khi GL entries được post, PE gọi `make_exchange_gain_loss_journal()`:

```python
def make_exchange_gain_loss_journal(self):
    # Kiểm tra từng dòng reference có chênh lệch tỷ giá không
    for d in self.get("references"):
        if d.exchange_gain_loss:
            # Tạo Journal Entry
            # Debit/Credit: Party Account (điều chỉnh công nợ)
            # Debit/Credit: Exchange Gain/Loss Account (ghi nhận lãi/lỗ)
```

### 6.6. GL Entry Chuẩn cho PE

**Thanh toán Supplier (Pay) — có tham chiếu đầy đủ:**

```
Debit:  Payable Account (Supplier)      ← allocated_amount (giảm công nợ)
Credit: Bank Account                    ← paid_amount (tiền ra khỏi ngân hàng)

[Tiếp theo — nếu có chênh lệch tỷ giá:]
Debit:  Exchange Gain/Loss Account      ← exchange_gain_loss
  Hoặc Credit: Exchange Gain/Loss Account
```

### 6.7. Cập nhật Outstanding Amounts

Sau khi GL entries được tạo, PE cập nhật `outstanding_amount` trên các tham chiếu:

```python
def update_outstanding_amounts(self):
    for d in self.get("references"):
        update_voucher_outstanding(
            d.reference_doctype,
            d.reference_name,
            account=self.party_account,
            party_type=self.party_type,
            party=self.party,
        )
```

Cơ chế: query GL Entry để tính tổng debit - credit cho cặp (voucher, account, party), cập nhật vào trường `outstanding_amount`.

---

## 7. Journal Entry

**File:** `erpnext/accounts/doctype/journal_entry/journal_entry.py`
**Class:** `JournalEntry(AccountsController)`

### 7.1. Mục đích

Journal Entry là chứng từ kế toán tổng hợp, cho phép ghi Nợ/Có trực tiếp vào bất kỳ tài khoản nào. Dùng cho:
- Điều chỉnh sai sót kế toán
- Phân bổ chi phí
- Kết chuyển lãi/lỗ
- Ghi nhận khấu hao
- Đánh giá lại tỷ giá (phiên bản thủ công, không qua Exchange Rate Revaluation)

### 7.2. Vòng đời

| Sự kiện | Mô tả |
|---------|-------|
| `validate()` | Kiểm tra party, multi-currency, debit/credit balance, references, accounts |
| `on_submit()` | `make_gl_entries()`, `update_advance_paid()`, `update_asset_value()` |
| `on_cancel()` | `make_gl_entries(1)`, `unlink_advance_entry_references()` |

### 7.3. `make_gl_entries()` — Đơn giản nhất

```python
def make_gl_entries(self, cancel=0, adv_adj=0):
    gl_map = self.build_gl_map()
    make_gl_entries(gl_map, adv_adj=adv_adj, cancel=cancel)
```

`build_gl_map()` đơn giản map từng dòng `accounts` table thành GL Entry dict:

```
Với mỗi dòng accounts row:
  GL Entry:
    account           = row.account
    party_type        = row.party_type
    party             = row.party
    debit             = row.debit
    credit            = row.credit
    debit_in_account_currency  = row.debit_in_account_currency
    credit_in_account_currency = row.credit_in_account_currency
    against_voucher_type       = row.reference_type
    against_voucher            = row.reference_name
    cost_center       = row.cost_center
    project           = row.project
```

### 7.4. GL Entry Chuẩn cho JE

**Bút toán điều chỉnh đơn giản:**
```
Debit:  Expense Account                  ← amount
Credit: Payable Account                  ← amount
```

**Kết chuyển chi phí:**
```
Debit:  Profit & Loss Account            ← total_expenses
Credit: Expense Account A                ← amount
Credit: Expense Account B                ← amount
```

**Ghi nhận khấu hao:**
```
Debit:  Depreciation Expense Account     ← amount
Credit: Accumulated Depreciation Account ← amount
```

---

## 8. Exchange Rate Revaluation

**File:** `erpnext/accounts/doctype/exchange_rate_revaluation/exchange_rate_revaluation.py`
**Class:** `ExchangeRateRevaluation(Document)` — kế thừa trực tiếp từ `Document`

### 8.1. Mục đích

Đánh giá lại số dư các tài khoản có gốc ngoại tệ vào cuối kỳ, ghi nhận lãi/lỗ chưa thực hiện (Unrealized Exchange Gain/Loss).

### 8.2. Loại tài khoản được đánh giá

Tất cả tài khoản Balance Sheet (Asset, Liability, Equity) có:
- `account_currency ≠ company_currency`
- `account_type ≠ "Stock"`
- `is_group = 0`

### 8.3. Vòng đời

| Sự kiện | Mô tả |
|---------|-------|
| Nạp dữ liệu | `fetch_and_calculate_accounts_data()` → `get_accounts_data()` |
| `validate()` | Gọi `set_total_gain_loss()` |
| `before_submit()` | Loại bỏ accounts không có gain/loss |
| `make_jv_entries()` ⭐ | Tạo Journal Entries (whitelist method — gọi bằng tay sau submit) |

> **Quan trọng:** Exchange Rate Revaluation KHÔNG tự động tạo Journal Entries khi submit. Bạn phải gọi `make_jv_entries()` sau submit (thường là qua nút bấm "Make Journal Entry").

### 8.4. `get_accounts_data()` — Lấy số dư tài khoản

```python
def get_accounts_data(self):
    # 1. Lấy danh sách tài khoản ngoại tệ
    accounts = query all non-group Balance Sheet accounts
              WHERE account_currency != company_currency
              AND account_type != 'Stock'

    # 2. Query GL Entry để lấy số dư
    SELECT
      account, party_type, party, account_currency,
      SUM(debit_in_account_currency) - SUM(credit_in_account_currency) AS balance_in_account_currency,
      SUM(debit) - SUM(credit) AS balance
    FROM `tabGL Entry`
    WHERE posting_date <= revaluation_date
      AND is_cancelled = 0
      AND account IN (accounts)
    GROUP BY account, party_type, party
    HAVING balance != balance_in_account_currency
```

### 8.5. `calculate_new_account_balance()` — Tính toán Gain/Loss

Cho mỗi tài khoản, chia làm 2 loại:

#### Loại 1: Non-zero Balance (cả base và account currency đều ≠ 0)

```python
current_exchange_rate = balance / balance_in_account_currency
new_exchange_rate = get_exchange_rate(account_currency, company_currency, posting_date)
new_balance_in_base_currency = balance_in_account_currency * new_exchange_rate
gain_loss = new_balance_in_base_currency - balance
```

#### Loại 2: Zero Balance (một trong 2 bên = 0)

```python
if balance != 0 and balance_in_account_currency == 0:
    # Base currency có số dư, account currency = 0
    gain_loss = 0 - balance  # Đưa balance về 0

elif balance == 0 and balance_in_account_currency != 0:
    # Account currency có số dư, base currency = 0
    current_exchange_rate = calculate_exchange_rate_using_last_gle()
    gain_loss = 0 - (current_exchange_rate * balance_in_account_currency)
```

### 8.6. `make_jv_entries()` — Tạo Journal Entries

Gồm 2 loại Journal Entry:

#### 8.6.1. Zero Balance JV — `make_jv_for_zero_balance()`

Dành cho tài khoản `zero_balance = True`:

```
Journal Entry (voucher_type = "Exchange Gain Or Loss", multi_currency = 1)

Trường hợp Account Currency có số dư (balance_in_account_currency > 0):
  Row 1: Account gốc (ngoại tệ)
    Debit/Credit: hết số dư account currency (đưa về 0)
    Exchange Rate = 0
  Row 2: Unrealized Exchange Gain/Loss Account
    Debit/Credit: abs(gain_loss) — ngược chiều với Row 1
    Exchange Rate = 1

Trường hợp Base Currency có số dư (balance > 0):
  Row 1: Account gốc
    Debit/Credit: hết số dư base currency (đưa về 0)
  Row 2: Unrealized Exchange Gain/Loss Account
    Debit/Credit: abs(gain_loss) — ngược chiều
```

#### 8.6.2. Revaluation JV — `make_jv_for_revaluation()`

Dành cho tài khoản `zero_balance = False`:

```
Journal Entry (voucher_type = "Exchange Rate Revaluation", multi_currency = 1)

Với mỗi tài khoản:
  Row 1 (NEW rate):
    Account: Tài khoản gốc
    Debit/Credit: abs(balance_in_account_currency)
    Exchange Rate = new_exchange_rate

  Row 2 (OLD rate):
    Account: Tài khoản gốc
    Debit/Credit: abs(balance_in_account_currency) (ngược chiều Row 1)
    Exchange Rate = current_exchange_rate

Row cuối (Balancing):
  Account: Unrealized Exchange Gain/Loss Account
  Debit: abs(gain_loss) nếu gain_loss < 0
  Credit: abs(gain_loss) nếu gain_loss > 0
  Exchange Rate = 1
```

### 8.7. Ví dụ Revaluation JV

**Giả sử:** Tài khoản "Debtors - USD" có số dư 10,000 USD, tỷ giá cũ 23,000, tỷ giá mới 24,000.
**Gain/Loss** = 10,000 × (24,000 - 23,000) = 10,000,000 (lãi chưa thực hiện)

```
Row 1: Debtors - USD           Debit: 10,000 USD  @ 24,000 (= 240,000,000 VND)
Row 2: Debtors - USD           Credit: 10,000 USD @ 23,000 (= 230,000,000 VND)
Row 3: Unrealized Exch Gain    Credit: 10,000,000 VND

Net effect: Debtors tăng 10,000,000 VND (do tỷ giá tăng)
           Unrealized Gain ghi nhận 10,000,000 VND
```

### 8.8. `set_total_gain_loss()` — Tổng hợp Kết quả

```python
def set_total_gain_loss(self):
    self.total_gain_loss = sum of abs(row.gain_loss) for all rows
    self.gain_loss_booked = sum of gain_loss where zero_balance = True
    self.gain_loss_unbooked = sum of gain_loss where zero_balance = False
```

---

## 9. GL Engine Trung tâm

**File:** `erpnext/accounts/general_ledger.py`

Module này được tất cả các accounting doctype (PI, PE, JE, PR) sử dụng để tạo GL Entries vào database.

### 9.1. `make_gl_entries()` — Entry Point Chính

```python
def make_gl_entries(gl_map, cancel=0, adv_adj=0, merge_entries=True,
                    update_outstanding="Yes", from_repost=False):
    if cancel:
        make_reverse_gl_entries(...)
        return

    # Validate
    validate_accounting_periods(gl_map)
    validate_disabled_accounts(gl_map)

    # Process (merge, normalize)
    gl_map = process_gl_map(gl_map, merge_entries)

    # Create Payment Ledger (nếu cần — cho PI/PE)
    if update_outstanding == "Yes":
        from erpnext.accounts.doctype.payment_ledger import payment_ledger
        payment_ledger.create_payment_ledger_entries(gl_map)

    # Save individual GL Entries
    save_entries(gl_map, adv_adj, update_outstanding, from_repost)
```

### 9.2. `process_gl_map()` — Chuẩn hóa GL Map

```python
def process_gl_map(gl_map, merge_entries=True, precision=None):
    # Bước 1: Phân bổ Cost Center Allocation
    if voucher_type != "Period Closing Voucher":
        gl_map = distribute_gl_based_on_cost_center_allocation(gl_map)

    # Bước 2: Merge entries giống nhau
    if merge_entries:
        gl_map = merge_similar_entries(gl_map)

    # Bước 3: Xử lý debit/credit âm
    gl_map = toggle_debit_credit_if_negative(gl_map)

    return gl_map
```

#### `distribute_gl_based_on_cost_center_allocation()`

Nếu Cost Center có Cost Center Allocation (phân bổ tỷ lệ cho các sub cost center):
```python
for sub_cost_center, percentage in allocation:
    new_gle = copy(gle)
    new_gle.cost_center = sub_cost_center
    new_gle.debit = gle.debit * percentage / 100
    new_gle.credit = gle.credit * percentage / 100
```

#### `merge_similar_entries()`

Merge các GL Entry có cùng:
- account, cost_center, party, party_type, voucher_detail_no
- against_voucher, against_voucher_type
- project, finance_book, accounting_dimensions

```python
same_head.debit += entry.debit
same_head.credit += entry.credit
```

Sau merge, loại bỏ entries có debit=0 AND credit=0 (ngoại trừ JE "Exchange Gain Or Loss").

#### `toggle_debit_credit_if_negative()`

Chuẩn hóa: nếu debit < 0 → chuyển thành credit dương, và ngược lại.

### 9.3. `save_entries()` — Lưu vào Database

```python
def save_entries(gl_map, adv_adj, update_outstanding, from_repost):
    # Xử lý chênh lệch debit-credit
    process_debit_credit_difference(gl_map)

    for entry in gl_map:
        make_entry(entry, adv_adj, update_outstanding, from_repost)
```

#### `process_debit_credit_difference()`

Tính tổng debit - tổng credit:
- Nếu chênh lệch trong phạm vi cho phép: tạo Round Off GL Entry
- Nếu vượt quá: raise error

#### `make_entry()` — Tạo GL Entry Document

```python
def make_entry(args, adv_adj, update_outstanding, from_repost):
    gle = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": args.posting_date,
        "account": args.account,
        "debit": args.debit,
        "credit": args.credit,
        "debit_in_account_currency": args.debit_in_account_currency,
        "credit_in_account_currency": args.credit_in_account_currency,
        "against_voucher": args.against_voucher,
        "against_voucher_type": args.against_voucher_type,
        "party_type": args.party_type,
        "party": args.party,
        "cost_center": args.cost_center,
        "project": args.project,
        "voucher_type": args.voucher_type,
        "voucher_no": args.voucher_no,
        "voucher_detail_no": args.voucher_detail_no,
        "against": args.against,
        "is_opening": args.is_opening or "No",
        "company": args.company,
        "finance_book": args.finance_book,
        "remarks": args.remarks,
    })
    gle.flags.ignore_permissions = True
    gle.flags.from_repost = from_repost
    gle.submit()
```

### 9.4. `make_reverse_gl_entries()` — Hủy GL

Khi hủy chứng từ:

```python
def make_reverse_gl_entries(voucher_type, voucher_no):
    original_entries = frappe.get_all("GL Entry", {
        "voucher_type": voucher_type,
        "voucher_no": voucher_no,
        "is_cancelled": 0
    })

    for entry in original_entries:
        # Tạo GL Entry mới với debit/credit đảo ngược
        make_entry({
            ...entry.fields...,
            "debit": entry.credit,       # Đảo ngược
            "credit": entry.debit,       # Đảo ngược
            "against_voucher": None,
        })
```

### 9.5. Payment Ledger

Khi PI/PE được tạo với `update_outstanding = "Yes"`, module Payment Ledger tạo thêm entries để track outstanding:

```python
payment_ledger.create_payment_ledger_entries(gl_map)
```

Payment Ledger Entry có cấu trúc:
- `posting_date`, `account`, `party_type`, `party`
- `amount` (dương cho invoice, âm cho payment)
- `against_voucher_type`, `against_voucher`
- `company`

Được dùng để tính `outstanding_amount` nhanh chóng mà không cần query GL Entry tổng hợp.

---

## 10. Bảng tổng hợp Tài khoản Kế toán

### 10.1. Ma trận GL Entry Đầy đủ

| Giai đoạn | Tình huống | Debit | Credit | Ghi chú |
|-----------|-----------|-------|--------|---------|
| **PR** | Nhập kho thường | Warehouse Account | SRBNB Account | Hàng tồn kho |
| **PR** | Internal transfer | Target WH Account | Source WH Account | Chuyển kho |
| **PR** | Non-stock + provisional | Expense Account | Provisional Account | Kế toán tạm thời |
| **PR** | Fixed asset | Asset Account | ARBNB Account | Tài sản cố định |
| **PR** | Thuế valuation | (vào Warehouse) | Tax Account | Qua stock value |
| **PR** | Divisional loss | Default Expense Acct | — | Sai số làm tròn |
| **PR** | Chênh lệch tỷ giá PI | SRBNB + Exch G/L | — | Khi PI đã link |
| **LCV** | Điều chỉnh giá PR | (Hủy GL cũ + Tạo lại GL mới) | | Không tạo GL riêng |
| **PI** | Ghi nhận công nợ | — | Payable Account | Supplier |
| **PI** | Chi phí (không update_stock) | Expense Account | — | Non-stock |
| **PI** | Chi phí (có update_stock) | Expense Account | — | Thay SRBNB của PR |
| **PI** | Internal transfer warehouse | Target WH Account | Source WH Account | |
| **PI** | Internal transfer tax | — | Unrealized P/L | |
| **PI** | Stock adjustment (chênh lệch) | COGS Account | — | |
| **PI** | Thuế "Add" | Tax Account | — | |
| **PI** | Thuế "Deduct" | — | Tax Account | |
| **PI** | Thuế valuation | — | Tax Account | |
| **PI** | LCV entries | — | LCV Account | |
| **PI** | Subcontract cost | — | Supplier WH Account | |
| **PI** | Write-off | Payable Account | Write Off Account | |
| **PI** | Rounding adjustment | Round Off Account | — | |
| **PI** | Chênh lệch tỷ giá PR≠PI | Expense Account | Exchange G/L Account | |
| **PI** | Đảo ngược provisional | Provisional Account | Expense Account | |
| **PI** | is_paid | Payable Account | Cash/Bank Account | |
| **PE** | Thanh toán Supplier | Payable Account | Cash/Bank Account | |
| **PE** | Thu từ Customer | Cash/Bank Account | Receivable Account | |
| **PE** | Internal transfer (PE) | Target Bank Account | Source Bank Account | |
| **PE** | Phí ngân hàng | Deduction Account | — | |
| **PE** | Thuế (Add) | Tax Account | — | |
| **PE** | Thuế (Deduct) | — | Tax Account | |
| **PE** | Chênh lệch tỷ giá (realized) | Payable/Receivable | Exchange G/L Account | Qua JE riêng |
| **JE** | Bút toán bất kỳ | Account A | Account B | Do người dùng định nghĩa |
| **ERR** | Zero balance JV | Account (ngoại tệ) | Unrealized Exch G/L | Đưa balance về 0 |
| **ERR** | Revaluation JV | Account @ rate mới | Account @ rate cũ + Unrealized G/L | |

### 10.2. Bảng Tài khoản Đặc biệt

| Tài khoản | Cấu hình ở đâu | Mục đích |
|-----------|---------------|----------|
| SRBNB (Stock Received But Not Billed) | Company | Tạm thời khi PR chưa có PI |
| ARBNB (Asset Received But Not Billed) | Company | Cho tài sản cố định |
| Payable Account | Company / Supplier | Công nợ nhà cung cấp |
| Expense Account | Item Defaults | Tài khoản chi phí mua hàng |
| Warehouse Account | Warehouse | Tài khoản hàng tồn kho |
| Provisional Account | Company | Kế toán tạm cho non-stock |
| Exchange Gain/Loss Account | Company | Lãi/lỗ tỷ giá đã thực hiện |
| Unrealized Exchange G/L | Company | Lãi/lỗ tỷ giá chưa thực hiện |
| Round Off Account | Company | Sai số làm tròn |
| Write Off Account | Company | Xóa nợ / bù trừ |
| LCV Account | Landed Cost Charges | Chi phí mua hàng thêm |


---

## 11. Tóm tắt Luồng End-to-End

### 11.1. Luồng Chi tiết từng Bước

**Bước 1: Purchase Order (Đặt hàng)**

```
Người dùng: tạo PO, chọn supplier, items, số lượng, đơn giá
Hệ thống: validate, lưu PO
Kế toán: KHÔNG ảnh hưởng — PO là chứng từ kế hoạch
Tồn kho (Bin): ordered_qty tăng lên
```

**Bước 2: Purchase Receipt (Nhận hàng)**

```
Người dùng: tạo PR từ PO (hoặc độc lập), nhập số lượng nhận
Hệ thống:
  SLE: INSERT Stock Ledger Entry với actual_qty = +received_qty
  SLE Engine: Tính valuation_rate (Moving Average / FIFO)
  GL:
      Debit:  Warehouse Account     ← stock_value_difference
      Credit: SRBNB Account         ← base_net_amount
  Repost: Nếu có SLE tương lai cho item-warehouse này
Tồn kho (Bin): received_qty tăng, ordered_qty giảm
```

**Bước 3: Landed Cost Voucher (Chi phí thêm — nếu có)**

```
Người dùng: tạo LCV, chọn PR, thêm charges (vận chuyển, thuế nhập khẩu...)
Hệ thống:
  1. Cập nhật landed_cost_voucher_amount trên từng PR Item
  2. Tính lại valuation_rate
  3. HỦY SLE cũ + GL cũ của PR
  4. TẠO LẠI SLE mới + GL mới của PR
      Debit:  Warehouse Account     ← value GỐC + LCV amount
      Credit: SRBNB Account         ← value gốc
      Credit: LCV Account           ← LCV amount
  5. Repost SLE/GLE tương lai
```

**Bước 4A: Purchase Invoice — Stock Item (Hóa đơn mua hàng, có update_stock)**

```
Người dùng: tạo PI từ PR, kiểm tra giá, nhập thuế
Hệ thống (nếu perpetual inventory và update_stock=1):
  GL:
      Debit:  Expense Account       ← base_net_amount (ghi nhận chi phí thực)
      Credit: Payable Account       ← base_grand_total (công nợ NCC)
      [+ các entries cho tax, rounding...]
  Nếu PI rate ≠ PR rate: tạo adjustment entries
      Debit:  Expense Account       ← discrepancy (chênh lệch giá)
      Credit: Exchange G/L Account  ← discrepancy

Outstanding: PI.paid_to_date = 0, outstanding_amount = base_grand_total
```

**Bước 4B: Purchase Invoice — Non-Stock Item (có Provisional Accounting)**

```
Người dùng: tạo PI từ PR
Hệ thống:
  1. Đảo ngược bút toán tạm của PR:
      Debit:  Provisional Account   ← amount (đảo ngược)
      Credit: Expense Account       ← amount (đảo ngược)
  2. Ghi nhận chi phí thực + công nợ:
      Debit:  Expense Account       ← base_net_amount
      Credit: Payable Account       ← base_grand_total

Nếu PI hủy: cancel_provisional_entries() đánh is_cancelled=1 trên GL Entry của PR
→ Khi PR repost, bút toán tạm xuất hiện lại
```

**Bước 5: Payment Entry (Thanh toán)**

```
Người dùng: tạo PE, chọn PI, nhập số tiền thanh toán
Hệ thống:
  GL:
      Debit:  Payable Account       ← allocated_amount (giảm công nợ)
      Credit: Bank Account          ← paid_amount (tiền ra khỏi NH)
  Nếu có chênh lệch tỷ giá:
      → Tạo Journal Entry (Exchange Gain Or Loss)

Outstanding: PI.outstanding_amount giảm (hoặc về 0 nếu thanh toán đủ)
```

**Bước 6: Journal Entry (Điều chỉnh — nếu cần)**

```
Người dùng: tạo JE, nhập debit/credit, chọn tài khoản
Hệ thống:
  GL: Tạo GL Entry trực tiếp theo từng dòng accounts table

Dùng cho: điều chỉnh sai sót, phân bổ, kết chuyển, khấu hao
```

**Bước 7: Exchange Rate Revaluation (Đánh giá lại tỷ giá cuối kỳ)**

```
Người dùng:
  1. Tạo ERR, chọn posting_date
  2. Fetch accounts → hệ thống tính gain/loss cho từng tài khoản ngoại tệ
  3. Submit ERR
  4. Gọi "Make Journal Entry" (make_jv_entries)

Hệ thống: tạo 2 Journal Entries:
  - Zero Balance JV: xóa số dư tài khoản có 1 bên = 0
  - Revaluation JV: điều chỉnh số dư cho tài khoản có cả 2 bên

Cả 2 JE đều ghi nhận vào Unrealized Exchange Gain/Loss Account
```

### 11.2. Sơ đồ Luồng GL Entry Tổng hợp

```
Thời gian ──────────────────────────────────────────────────────►

 PR submit:
   WH Account (Dr)  ─────────────────────┐
   SRBNB (Cr)       ─────────────────────┤
                                          ├───► Repost nếu cần
 LCV submit:                               │
   (Hủy GL cũ của PR)                      │
   (Tạo GL mới: WH + SRBNB + LCV)          │
                                          │
 PI submit:                                │
   Expense (Dr)  ─────────────────────────┤
   Payable (Cr) ──────────────────────────┤
   [Provisional đảo ngược nếu non-stock]   │
   [Exchange rate diff nếu có]             │
   [is_paid entries nếu có]                │
                                          │
 PI cancel:                                │
   Reverse GL của PI                        │
   is_cancelled=1 trên GL của PR            │
   → Khi PR repost → Provisional hiện lại   │
                                          │
 PE submit:                                │
   Payable (Dr) ──────────────────────────┤
   Bank (Cr) ─────────────────────────────┤
   + JE Exchange G/L (nếu có diff)         │
                                          │
 ERR submit:                               │
   + JE Zero Balance (nếu có)              │
   + JE Revaluation (nếu có)               │
   → Ghi nhận Unrealized G/L                │
                                          ▼
                                   Period Closing Voucher
                                   (Kết chuyển lãi/lỗ cuối kỳ)
```

### 11.3. Key File Paths

| Component | File Path |
|-----------|-----------|
| Purchase Order | `erpnext/buying/doctype/purchase_order/purchase_order.py` |
| Purchase Receipt | `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py` |
| PR GL Composer | `erpnext/stock/doctype/purchase_receipt/services/gl_composer.py` |
| PR Provisional Acct | `erpnext/stock/doctype/purchase_receipt/services/provisional_accounting.py` |
| PR Billing Status | `erpnext/stock/doctype/purchase_receipt/services/billing_status.py` |
| PR Stock Reservation | `erpnext/stock/doctype/purchase_receipt/services/stock_reservation.py` |
| Landed Cost Voucher | `erpnext/stock/doctype/landed_cost_voucher/landed_cost_voucher.py` |
| Purchase Invoice | `erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py` |
| Payment Entry | `erpnext/accounts/doctype/payment_entry/payment_entry.py` |
| Journal Entry | `erpnext/accounts/doctype/journal_entry/journal_entry.py` |
| Exchange Rate Reval. | `erpnext/accounts/doctype/exchange_rate_revaluation/exchange_rate_revaluation.py` |
| GL Engine | `erpnext/accounts/general_ledger.py` |
| Stock Controller | `erpnext/controllers/stock_controller.py` |
| Accounts Controller | `erpnext/controllers/accounts_controller.py` |
| Buying Controller | `erpnext/controllers/buying_controller.py` |

### 11.4. Cơ chế Outstanding Amount

Outstanding amount được tính từ **Payment Ledger**, không phải từ GL Entry:

```sql
SELECT SUM(amount) FROM `tabPayment Ledger Entry`
WHERE against_voucher_type = 'Purchase Invoice'
  AND against_voucher = 'INV-xxxx'
  AND company = 'My Company'
```

- Invoice tạo Payment Ledger Entry với `amount > 0` (dương)
- Payment tạo Payment Ledger Entry với `amount < 0` (âm) liên kết với invoice
- Outstanding = SUM(amount) — nếu = 0 thì invoice đã thanh toán đủ

`update_outstanding = "No"` được set khi `is_paid=1` hoặc có write-off — lúc đó hệ thống tự cập nhật outstanding trực tiếp qua `update_voucher_outstanding()`.

### 11.5. Chu kỳ Sống của SRBNB

```
1. PR submit:
   SRBNB (Cr)                          ← ghi nhận nợ tạm

2. PI submit (update_stock=1, perpetual inventory):
   Expense Account (Dr)                ← xóa SRBNB, ghi nhận chi phí thực
   → SRBNB không còn dư nợ

3. PR cancel (sau khi PI):
   → Bị chặn: không cho cancel PR khi đã có PI

4. PI cancel:
   → Reverse GL của PI
   → SRBNB xuất hiện lại qua repost
```

---

## 12. Các Tình huống Đặc biệt

### 12.1. Mua hàng Internal Transfer (cùng công ty)

- PO/PI được đánh dấu là internal supplier (cùng company hoặc inter-company)
- PR: không có SRBNB — debit target WH, credit source WH
- PI: không có SRBNB — debit target WH, credit source WH
- PI: tax được ghi vào Unrealized Profit/Loss Account (không vào chi phí)

### 12.2. Subcontracting (Gia công)

- PO có `is_subcontracted = "Yes"`
- PR có `supplier_warehouse` — nơi chứa nguyên liệu cấp cho nhà gia công
- Khi nhận thành phẩm:
  - SLE giảm nguyên liệu tại supplier_warehouse
  - SLE tăng thành phẩm tại finished goods warehouse
  - GL: debit finished goods WH, credit supplier WH (cho rm_supp_cost)

### 12.3. Phiếu trả hàng (Return)

- `is_return = True` trên PR hoặc PI
- PR Return: SLE âm tại warehouse, GL đảo ngược
- PI Return (Debit Note): đảo ngược expense + payable
- StatusUpdater cập nhật `returned_qty` trên PO và PR gốc

### 12.4. Mua hàng trả tiền ngay (is_paid)

- PI có `is_paid = 1`, chọn tài khoản cash/bank
- GL bao gồm cả bút toán thanh toán
- `update_outstanding = "No"` — outstanding được set = 0 ngay khi submit

### 12.5. Mua hàng trả chậm nhiều kỳ (Deferred Expense)

- Item có `enable_deferred_expense = True`
- Expense được ghi vào `deferred_expense_account` thay vì expense account thường
- Deferred Expense tự động phân bổ chi phí qua các kỳ bằng auto-recurring JE

---

_Tài liệu được tổng hợp từ mã nguồn ERPNext/Frappe (tháng 6/2026)._
_Phiên bản: v15+. Mục đích: tham khảo nội bộ._

