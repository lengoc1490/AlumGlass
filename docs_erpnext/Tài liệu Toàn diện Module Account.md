# Tài liệu Toàn diện Module Account — ERPNext/Frappe
> **A-Z từ kiến trúc, logic Python, đến JS frontend; bao gồm hướng dẫn điều chỉnh, kế thừa và tích hợp class mới.**

---

## MỤC LỤC

1. [Kiến trúc Tổng quan & Cây Kế thừa](#1-kiến-trúc-tổng-quan)
2. [TransactionBase & StatusUpdater](#2-transactionbase--statusupdater)
3. [AccountsController (accounts_controller.py)](#3-accountscontroller)
4. [Hệ thống Thuế & Tính Toán (taxes_and_totals.py)](#4-hệ-thống-thuế--tính-toán)
5. [General Ledger Engine (general_ledger.py)](#5-general-ledger-engine)
6. [GL Entry (gl_entry.py)](#6-gl-entry)
7. [Accounts Utils (accounts/utils.py)](#7-accounts-utils)
8. [Party System (accounts/party.py)](#8-party-system)
9. [SalesInvoice — Python Chi tiết](#9-salesinvoice--python)
10. [SalesInvoice — JavaScript Chi tiết](#10-salesinvoice--javascript)
11. [PurchaseInvoice — Python Chi tiết](#11-purchaseinvoice--python)
12. [PurchaseInvoice — JavaScript Chi tiết](#12-purchaseinvoice--javascript)
13. [PaymentEntry — Python Chi tiết](#13-paymententry--python)
14. [JournalEntry — Python Chi tiết](#14-journalentry--python)
15. [JS Controllers: TransactionController & erpnext.accounts](#15-js-controllers)
16. [Luồng Dữ liệu Kế toán Tích hợp](#16-luồng-dữ-liệu-tích-hợp)
17. [Hướng dẫn Điều chỉnh, Kế thừa & Phát triển Class Mới](#17-hướng-dẫn-phát-triển-class-mới)
18. [Tích hợp Class Mới vào JS Frontend](#18-tích-hợp-vào-js-frontend)

---

## 1. Kiến trúc Tổng quan

### 1.1 Cây Kế thừa Python (đầy đủ)

```
frappe.model.document.Document (Frappe Core)
  └── frappe.model.document.BaseDocument
        └── erpnext.utilities.transaction_base.TransactionBase
              └── erpnext.controllers.accounts_controller.AccountsController
                    ├── erpnext.controllers.selling_controller.SellingController
                    │     └── SalesInvoice  (accounts/doctype/sales_invoice/sales_invoice.py)
                    │     └── DeliveryNote  (stock/doctype/delivery_note/delivery_note.py)
                    │     └── SalesOrder    (selling/doctype/sales_order/sales_order.py)
                    │
                    ├── erpnext.controllers.buying_controller.BuyingController
                    │     └── SubcontractingController
                    │           └── PurchaseInvoice (accounts/doctype/purchase_invoice/purchase_invoice.py)
                    │           └── PurchaseOrder   (buying/doctype/purchase_order/purchase_order.py)
                    │           └── PurchaseReceipt (stock/doctype/purchase_receipt/purchase_receipt.py)
                    │
                    └── (trực tiếp) PaymentEntry (accounts/doctype/payment_entry/payment_entry.py)
                    └── (trực tiếp) JournalEntry  (accounts/doctype/journal_entry/journal_entry.py)
```

### 1.2 Cây Kế thừa JavaScript

```
frappe.ui.form.Controller (Frappe Core)
  └── erpnext.taxes_and_totals     (public/js/controllers/taxes_and_totals.js)
        └── erpnext.TransactionController (public/js/controllers/transaction.js)
              ├── erpnext.buying.BuyingController
              │     └── erpnext.accounts.PurchaseInvoice (accounts/doctype/purchase_invoice/purchase_invoice.js)
              │
              └── erpnext.selling.SellingController
                    └── erpnext.accounts.SalesInvoiceController (accounts/doctype/sales_invoice/sales_invoice.js)
```

### 1.3 Sơ đồ File-to-Responsibility

| File | Vai trò |
|------|---------|
| `controllers/accounts_controller.py` | Base class kế toán: validate, GL dict, advance, payment schedule |
| `controllers/taxes_and_totals.py` | Tính thuế & tổng (class `calculate_taxes_and_totals`) |
| `accounts/general_ledger.py` | Ghi/hủy GL Entries, xử lý roundoff, cost center allocation |
| `accounts/doctype/gl_entry/gl_entry.py` | Validate GLE, cập nhật outstanding, frozen account |
| `accounts/utils.py` | Tiện ích: fiscal year, balance, reconcile, outstanding invoices |
| `accounts/party.py` | Thông tin party: address, account, due date, credit limit |
| `accounts/doctype/sales_invoice/sales_invoice.py` | Logic SI: submit/cancel, GL, TCS, POS, loyalty |
| `accounts/doctype/purchase_invoice/purchase_invoice.py` | Logic PI: submit/cancel, GL, TDS, provisional entries |
| `accounts/doctype/payment_entry/payment_entry.py` | Payment: GL, reconcile, advance, exchange gain/loss |
| `accounts/doctype/journal_entry/journal_entry.py` | JE: multi-purpose voucher, asset, inter-company |
| `public/js/controllers/transaction.js` | JS base: triggers item, tax, discount, warehouse |
| `public/js/controllers/accounts.js` | JS: tax validation, payment triggers, POS |

---

## 2. TransactionBase & StatusUpdater

**File:** `erpnext/utilities/transaction_base.py`

### 2.1 StatusUpdater — Cơ chế Cập nhật Chuỗi

`StatusUpdater` là cơ chế cốt lõi để đồng bộ trạng thái giữa các doctype trong chuỗi giao dịch. Mỗi doctype khai báo `self.status_updater` trong `__init__`.

**Cấu trúc một entry trong `status_updater`:**

```python
{
    "source_dt": "Sales Invoice Item",     # Child doctype nguồn
    "target_dt": "Sales Order Item",       # Child doctype đích (nơi cập nhật)
    "target_parent_dt": "Sales Order",     # Parent doctype đích
    "target_field": "billed_amt",          # Field cập nhật trên target_dt
    "target_ref_field": "amount",          # Field tham chiếu để tính %
    "target_parent_field": "per_billed",   # % field trên parent
    "join_field": "so_detail",             # Field FK trên source_dt → target_dt.name
    "source_field": "amount",              # Field lấy giá trị từ source_dt
    "percent_join_field": "sales_order",   # FK trên source_dt → target_parent_dt.name
    "status_field": "billing_status",      # Field trạng thái trên target_parent_dt
    "keyword": "Billed",                   # Từ khóa cho status
    "overflow_type": "billing",            # "billing" | "delivery"
    "second_source_dt": "...",             # Nguồn thứ hai (optional)
    "second_source_field": "...",
    "second_join_field": "...",
}
```

**Phương thức quan trọng:**

| Phương thức | Mô tả |
|-------------|-------|
| `update_prevdoc_status()` | Gọi khi submit: cộng qty/amount từ source lên target, tính % |
| `update_qty()` | Cập nhật qty trong Bin (tồn kho) |
| `validate_overstep()` | Kiểm tra qty/amount không vượt quá giới hạn cho phép |
| `get_allowance_for(fieldname)` | Lấy mức cho phép vượt (over_delivery_allowance, v.v.) |

---

## 3. AccountsController

**File:** `erpnext/controllers/accounts_controller.py`

Class trung tâm, tất cả doctype kế toán đều kế thừa.

### 3.1 Lifecycle Methods

#### `validate(self)`

Chuỗi validation đầy đủ:

```
validate_qty_is_not_zero()           → qty ≠ 0 (trừ return/debit note)
validate_zero_qty_for_return_invoices_with_stock()
set_missing_values(for_validate=True) → điền giá trị thiếu
remove_bundle_for_non_stock_invoices() → xóa bundle nếu không update_stock
ensure_supplier_is_not_blocked()     → nhà cung cấp không bị hold
validate_date_with_fiscal_year()     → ngày phải trong fiscal year
validate_deferred_start_and_end_date() → ngày dịch vụ hoãn hợp lệ
InternalTransferService.validate()   → kiểm tra internal transfer
set_incoming_rate()                  → (StockController) lấy incoming rate
init_internal_values()               → reset billed_amt, delivered_qty về 0
validate_against_voucher_outstanding() → kiểm tra return không vượt outstanding
TaxService.validate_enabled_taxes_and_charges()
TaxService.validate_tax_account_company()
TaxService.set_taxes_and_charges()   → điền taxes từ template
calculate_taxes_and_totals()         → TÍnh toán thuế & tổng (quan trọng nhất)
validate_value("base_grand_total", ">=", 0)
validate_return(self)               → validate return doc
validate_all_documents_schedule()   → payment schedule
PartyValidator.validate()           → validate party
validate_return_against_account()   → account phải khớp với original doc
[if SI/PI] set_advances()           → allocate advances automatically
set_advance_gain_or_loss()
validate_deferred_income_expense_account()
InternalTransferService.set_account()
[if PI] calculate_paid_amount()
validate_regional(self)             → hook vùng (GST, v.v.)
validate_einvoice_fields(self)      → e-invoice hook
apply_pricing_rule_on_transaction(self)
set_total_in_words()
set_default_letter_head()
validate_company_in_accounting_dimension()
```

#### `on_cancel(self)`

```
remove_from_bank_transaction()       → hủy liên kết Bank Transaction
cancel_system_generated_credit_debit_notes() → hủy JE auto-generated
cancel_exchange_gain_loss_journal()  → hủy JE exchange gain/loss
cancel_common_party_journal()        → hủy JE common party
unlink_ref_doc_from_payment_entries() → tháo liên kết PE (nếu cài đặt cho phép)
```

#### `on_trash(self)`

```
_remove_references_in_repost_doctypes()
_remove_references_in_unreconcile()
remove_serial_and_batch_bundle()
[nếu delete_linked_ledger_entries] → xóa GL, SLE, PLE
_remove_advance_payment_ledger_entries()
```

### 3.2 Phương thức Kế toán

#### `get_gl_dict(self, args, account_currency=None, item=None)`

**File gọi:** `accounts/services/base_gl_composer.py::get_gl_dict()`

Tạo dict cho một GL Entry với tất cả fields tiêu chuẩn:

```python
{
    "company": self.company,
    "posting_date": self.posting_date,
    "voucher_type": self.doctype,
    "voucher_no": self.name,
    "remarks": self.get("remarks") or self.get("remark"),
    "debit": 0,
    "credit": 0,
    "debit_in_account_currency": 0,
    "credit_in_account_currency": 0,
    "is_opening": self.get("is_opening") or "No",
    "party_type": None,
    "party": None,
    "project": args.get("project") or self.get("project"),
    "post_net_value": args.get("post_net_value"),
    # + tất cả accounting dimensions
    # + args (override)
}
```

#### `calculate_taxes_and_totals(self)`

Gọi `calculate_taxes_and_totals(self)` từ `taxes_and_totals.py`, sau đó gọi thêm `calculate_commission()` và `calculate_contribution()` cho SI/DN/SO.

#### `update_against_document_in_jv(self)`

Liên kết hóa đơn với phiếu ứng trước (advance):

1. Với mỗi advance có `allocated_amount > 0`, build args dict.
2. Gọi `reconcile_against_document(lst)` từ `accounts/utils.py`.
3. Tạo Payment Ledger Entries liên kết invoice ↔ advance.

#### `set_advances(self)`

Gọi `accounts/services/advances.py::set_advances()`:
1. Lấy danh sách advance entries chưa phân bổ cho party.
2. Điền vào bảng `advances` với các trường: reference_type, reference_name, advance_amount, allocated_amount.

### 3.3 Payment Schedule

#### `validate_all_documents_schedule(self)`

- SI/PI: gọi `validate_invoice_documents_schedule()`.
- SO/PO/Quotation: gọi `validate_non_invoice_documents_schedule()`.

#### `validate_invoice_documents_schedule(self)`

```
PaymentScheduleService.validate_payment_schedule_dates()
PaymentScheduleService.set_due_date()
PaymentScheduleService.set_payment_schedule()  → tính payment schedule từ template
PaymentScheduleService.validate_payment_schedule_amount()
validate_due_date()
validate_advance_entries()
```

### 3.4 Discount & Pricing

#### `apply_pricing_rule_on_items(self, item, pricing_rule_args)`

Áp dụng Pricing Rule lên từng item:
- `price_or_product_discount = "Price"`: cập nhật `discount_percentage`, `discount_amount`, `rate`.
- `free_item_data`: gọi `apply_pricing_rule_for_free_items()`.

#### `set_discount_amount_after_mapping(self, source_doc)`

Sau khi map từ doctype này sang doctype khác (VD: SO → SI), tính lại `discount_amount` không bị cộng dồn. Dùng SQL để tổng hợp discount đã áp dụng từ trước.

### 3.5 Accounting Dimensions

#### `validate_company_in_accounting_dimension(self)`

Với mỗi accounting dimension (Cost Center, Project, v.v.) có trường `company`: kiểm tra `dimension.company == self.company`. Áp dụng cho cả parent doc và tất cả child rows.

---

## 4. Hệ thống Thuế & Tính Toán

**File:** `erpnext/controllers/taxes_and_totals.py`

Class `calculate_taxes_and_totals` — không phải function mà là **class** có `__init__` gọi `calculate()` ngay.

### 4.1 Luồng Tính Toán Chính

```
__init__(doc)
  └── calculate()
        ├── _calculate()
        │     ├── validate_conversion_rate()         → kiểm tra conversion_rate
        │     ├── calculate_item_values()             → tính rate, amount, net_amount từng item
        │     ├── validate_item_tax_template()        → validate và auto-update tax template
        │     ├── update_item_tax_map()               → cập nhật item_tax_rate JSON
        │     ├── initialize_taxes()                  → reset tax fields về 0
        │     ├── determine_exclusive_rate()          → tính net_rate khi tax inclusive
        │     ├── calculate_net_total()               → total_net_weight, net_total
        │     ├── calculate_taxes()                   → tính tax_amount từng dòng thuế
        │     ├── adjust_grand_total_for_inclusive_tax()
        │     ├── calculate_totals()                  → grand_total, rounded_total
        │     └── calculate_total_net_weight()
        ├── set_discount_amount()
        ├── apply_discount_amount()                   → áp dụng discount lên items/taxes
        ├── calculate_shipping_charges()
        ├── calculate_total_advance()                 → tổng advances allocated
        └── set_item_wise_tax_breakup()
```

### 4.2 `calculate_item_values()`

Với từng item:

```python
# 1. Tính rate từ price_list_rate và discount
if item.discount_percentage == 100:
    item.rate = 0.0
elif item.price_list_rate:
    item.rate = price_list_rate * (1 - discount_percentage/100)
    item.discount_amount = price_list_rate * discount_percentage/100

# 2. Tính rate_with_margin (nếu có margin)
item.rate_with_margin, item.base_rate_with_margin = calculate_margin(item)
if rate_with_margin > 0:
    item.rate = rate_with_margin * (1 - discount_percentage/100)

# 3. Tính amount
item.amount = item.rate * item.qty
item.net_amount = item.amount

# 4. Convert sang base currency
for f in ["price_list_rate", "rate", "net_rate", "amount", "net_amount"]:
    item.base_{f} = item.{f} * doc.conversion_rate
```

### 4.3 `determine_exclusive_rate()`

Khi có tax `included_in_print_rate = 1`:

```python
# Với mỗi item, tính cumulated_tax_fraction từ tất cả inclusive taxes
# net_amount = amount / (1 + cumulated_tax_fraction)
item.net_amount = amount / (1 + cumulated_tax_fraction)
item.net_rate = net_amount / qty
```

### 4.4 `calculate_taxes()`

Với mỗi dòng thuế, theo `charge_type`:

| charge_type | Công thức |
|-------------|-----------|
| `Actual` | `tax_amount` = giá trị nhập thủ công |
| `On Net Total` | `tax_amount = net_total * rate/100` |
| `On Previous Row Amount` | `tax_amount = taxes[row_id-1].tax_amount * rate/100` |
| `On Previous Row Total` | `tax_amount = taxes[row_id-1].total * rate/100` |
| `On Item Quantity` | `tax_amount = Σ(item.qty * tax_rate)` |
| `On Paid Amount` | Tính sau khi biết paid_amount |

Mỗi dòng thuế lưu:
- `tax_amount`: tổng thuế
- `tax_amount_after_discount_amount`: sau khi áp discount
- `total`: running total (net_total + Σ tax đến dòng hiện tại)
- `item_wise_tax_detail`: JSON `{item_name: [tax_rate, tax_amount]}`

### 4.5 `apply_discount_amount()`

Khi `discount_amount > 0`:

```python
if apply_discount_on == "Net Total":
    # Phân bổ discount vào net_amount từng item theo tỷ lệ
    for item in items:
        item.net_amount -= discount * (item.net_amount / net_total)
    # Tính lại thuế

elif apply_discount_on == "Grand Total":
    # Phân bổ discount vào tax_amount từng dòng thuế theo tỷ lệ
    for tax in taxes:
        tax.tax_amount_after_discount_amount -= discount * (tax.total / grand_total)
```

### 4.6 `calculate_totals()`

```python
doc.net_total = Σ item.net_amount
doc.total_taxes_and_charges = Σ tax.tax_amount_after_discount_amount
doc.grand_total = net_total + total_taxes_and_charges
doc.base_grand_total = grand_total * conversion_rate
doc.rounded_total = round(grand_total) if not disable_rounded_total
doc.outstanding_amount = rounded_total - total_advance
```

### 4.7 Hàm Tiện ích Module-Level

| Hàm | File | Mô tả |
|-----|------|-------|
| `get_itemised_tax_breakup_html(doc)` | taxes_and_totals.py | HTML bảng thuế theo item |
| `get_round_off_applicable_accounts(company, account_list)` | taxes_and_totals.py | Accounts áp dụng roundoff |
| `get_itemised_tax(doc, with_tax_account)` | taxes_and_totals.py | Dict thuế theo item |
| `update_itemised_tax_data(doc)` | taxes_and_totals.py | Cập nhật tax data |
| `process_item_wise_tax_details(doc)` | taxes_and_totals.py | Xử lý item-wise tax details |

---

## 5. General Ledger Engine

**File:** `erpnext/accounts/general_ledger.py`

Đây là engine ghi sổ cái — mọi bút toán đều đi qua đây.

### 5.1 `make_gl_entries(gl_map, cancel, adv_adj, merge_entries, update_outstanding, from_repost)`

**Entry point chính** — được gọi từ mọi doctype submit.

```
Nếu không cancel:
  1. BudgetValidation(gl_map).validate()       → kiểm tra ngân sách
  2. make_acc_dimensions_offsetting_entry()    → tạo entries bù trừ accounting dimensions
  3. validate_accounting_period()              → kiểm tra accounting period không bị closed
  4. validate_disabled_accounts()             → accounts phải enabled
  5. process_gl_map()                          → merge, distribute, toggle negative
      ├── distribute_gl_based_on_cost_center_allocation() → phân bổ theo cost center allocation
      ├── merge_similar_entries()              → gộp entries cùng account/party/dimension
      └── toggle_debit_credit_if_negative()   → đảo chiều nếu âm
  6. create_payment_ledger_entry()             → tạo Payment Ledger Entries
  7. save_entries()                            → validate và save từng GLE
      ├── validate_cwip_accounts()
      ├── process_debit_credit_difference()   → kiểm tra debit == credit, tạo roundoff
      ├── check_freezing_date()               → ngày không bị freeze
      ├── validate_against_pcv()             → không trong Period Closing Voucher
      ├── validate_allowed_dimensions()       → dimensions hợp lệ
      └── make_entry()                        → tạo từng GL Entry document

Nếu cancel:
  make_reverse_gl_entries()                   → tạo reverse entries
```

### 5.2 `process_gl_map(gl_map, merge_entries, precision, from_repost)`

```
distribute_gl_based_on_cost_center_allocation(gl_map)
  → Nếu cost center có Cost Center Allocation: tách GLE thành nhiều dòng
    theo tỷ lệ phần trăm (VD: 60% Main, 40% Branch)

merge_similar_entries(gl_map)
  → Gộp các GLE có cùng merge_key:
    [account, cost_center, party, party_type, voucher_detail_no,
     against_voucher, against_voucher_type, project, finance_book,
     + accounting dimensions]

toggle_debit_credit_if_negative(gl_map)
  → Nếu debit < 0: swap sang credit (và ngược lại)
  → Nếu post_net_value: lấy net value
```

### 5.3 `process_debit_credit_difference(gl_map)`

```
1. Tính debit_credit_diff = Σ(debit) - Σ(credit)
2. allowance: JE/PE = 5 / 10^precision; others = 0.5
3. Nếu |diff| > allowance: raise error
4. Nếu |diff| >= 1/10^precision: tạo round-off GLE
   → get_round_off_account_and_cost_center(company)
   → Tạo GLE vào round_off_account với amount = diff
```

### 5.4 `make_reverse_gl_entries(gl_entries, voucher_type, voucher_no, ...)`

Khi hủy:
1. Lấy tất cả GLE gốc (chưa bị cancel).
2. Tạo Payment Ledger Entries ngược.
3. Validate accounting period.
4. Với mỗi GLE: tạo bản sao ngược (debit↔credit swap), đánh dấu `is_cancelled=1`.
5. Nếu `immutable_ledger_enabled`: không cancel GLE cũ, chỉ tạo mới ngược chiều.

### 5.5 `make_acc_dimensions_offsetting_entry(gl_map)`

Nếu accounting dimension có `automatically_post_balancing_accounting_entry = 1`:
- Với mỗi GLE và mỗi dimension có offsetting_account: tạo GLE bù trừ vào `offsetting_account`.
- Mục đích: đảm bảo balance sheet cân bằng theo từng dimension.

### 5.6 `distribute_gl_based_on_cost_center_allocation(gl_map, precision)`

Kiểm tra `Cost Center Allocation` cho từng cost_center:
- Nếu có allocation còn hiệu lực (valid_from ≤ posting_date): tách GLE thành N dòng theo tỷ lệ.
- Ví dụ: cost center "Head Office" được split 70% "HO" + 30% "Branch1".

---

## 6. GL Entry

**File:** `erpnext/accounts/doctype/gl_entry/gl_entry.py`

### 6.1 Validate (tự động khi save)

```python
# Trong gle.submit():
validate_balance_type(account, adv_adj)    → Balance type accounts (BRS) không debit/credit
validate_frozen_account(company, account)  → Account không bị frozen
validate_debit_credit_amount()             → debit + credit > 0
validate_account_currency()               → currency phải match account currency
```

### 6.2 `update_outstanding_amt(account, party_type, party, against_voucher_type, against_voucher, on_cancel)`

**Đây là hàm cốt lõi cập nhật `outstanding_amount` trên hóa đơn:**

```python
# 1. Lấy tất cả GLE liên quan đến against_voucher (không bị cancelled)
# 2. Tính balance = Σ(credit) - Σ(debit) cho SI
#               hoặc Σ(debit) - Σ(credit) cho PI
# 3. Cập nhật outstanding_amount = balance trên voucher document
# 4. Cập nhật status (Paid/Unpaid/Partly Paid) dựa trên outstanding_amount
```

### 6.3 `validate_balance_type(account, adv_adj)`

Accounts với `balance_must_be` = "Debit" hoặc "Credit": kiểm tra balance không sai chiều sau khi tạo GLE mới.

### 6.4 `update_against_account(voucher_type, voucher_no)`

Điền trường `against` trên GLE — ghi chú tài khoản đối ứng. Ví dụ: "Cash - ABC" khi debit Receivable.

---

## 7. Accounts Utils

**File:** `erpnext/accounts/utils.py`

### 7.1 Fiscal Year

#### `get_fiscal_year(date, fiscal_year, label, company, verbose, as_dict, boolean)`

Lấy fiscal year chứa `date`. Trả về `(year_name, year_start_date, year_end_date)`.

#### `validate_fiscal_year(date, fiscal_year, company, label, doc)`

Kiểm tra `date` nằm trong `fiscal_year`. Raise nếu không.

### 7.2 Account Balance

#### `get_balance_on(account, date, party_type, party, company, report_type, field, in_account_currency, cost_center, ignore_closing_entries, ignore_opening_entries)`

Lấy số dư tài khoản tại một ngày. Hỗ trợ:
- Balance sheet accounts: cộng dồn từ đầu.
- P&L accounts: chỉ tính trong fiscal year.
- `party_type + party`: lọc theo đối tượng.
- `ignore_closing_entries`: bỏ qua Period Closing Voucher.

### 7.3 Outstanding Invoices

#### `get_outstanding_invoices(party_type, party, account, common_filter, posting_date, min_outstanding, max_outstanding, accounting_dimensions_filter, limit, voucher_no, docstatus)`

Lấy danh sách hóa đơn còn outstanding (dùng để tạo Payment Entry):

```sql
SELECT voucher_no, posting_date, due_date, currency,
       invoice_amount, outstanding_amount, ...
FROM (
    SELECT gle.against_voucher,
           SUM(credit - debit) AS outstanding  -- SI
    FROM `tabGL Entry` gle
    WHERE gle.party_type = party_type
      AND gle.party = party
      AND gle.account = account
      AND is_cancelled = 0
    GROUP BY gle.against_voucher
) invoices
WHERE outstanding > 0
ORDER BY posting_date
```

### 7.4 Reconcile

#### `reconcile_against_document(args, active_dimensions)`

**Điểm vào chính để link payment với invoice:**

1. Với mỗi args entry: gọi `check_if_advance_entry_modified()` — kiểm tra advance JE chưa bị sửa.
2. Gọi `validate_allocated_amount()` — không vượt outstanding.
3. `update_reference_in_journal_entry()` hoặc `update_reference_in_payment_entry()` — cập nhật `against_voucher` trong GLE.
4. Tạo/cập nhật Payment Ledger Entries.
5. Tạo Exchange Gain/Loss Journal nếu cần.

#### `update_reference_in_payment_entry(d, payment_entry, do_not_save)`

Cập nhật GLE của Payment Entry để trỏ đúng `against_voucher`:
1. Cancel GLE cũ.
2. Tạo GLE mới với `against_voucher = invoice_name`, `against_voucher_type = "Sales Invoice"`.
3. Submit lại payment entry.

### 7.5 Exchange Gain/Loss

#### `cancel_exchange_gain_loss_journal(doc)`

Hủy JE exchange gain/loss liên kết với doc. Được gọi khi hủy SI/PI/PE.

### 7.6 Repost GL

#### `update_gl_entries_after(posting_date, posting_time, for_warehouses, for_items, company)`

Repost GL Entries cho tất cả voucher từ `posting_date` về sau, đảm bảo valuation rate đúng.

#### `repost_gle_for_stock_vouchers(stock_vouchers, posting_date, company, repost_doc)`

Repost GL cho danh sách stock vouchers cụ thể. Được gọi sau khi Stock Reconciliation hoặc khi điều chỉnh valuation.

---

## 8. Party System

**File:** `erpnext/accounts/party.py`

### 8.1 `get_party_details(party, account, party_type, company, posting_date, ...)`

Entry point lấy thông tin party khi chọn Customer/Supplier trên form.

Trả về dict gồm:
```python
{
    "customer" / "supplier": party_name,
    "customer_name" / "supplier_name": party.customer_name,
    "tax_id": party.tax_id,
    "payment_terms": party.payment_terms,
    "customer_address": default_billing_address,
    "shipping_address_name": default_shipping_address,
    "contact_person": default_contact,
    "currency": party.default_currency,
    "price_list": party.default_price_list,
    "debit_to" / "credit_to": party_account,
    "due_date": calculated_due_date,
    "selling_price_list" / "buying_price_list": price_list,
}
```

### 8.2 `get_party_account(party_type, party, company, include_advance)`

Lấy tài khoản Receivable/Payable cho party:

1. Kiểm tra `party.accounts` (accounts theo company) — ưu tiên nhất.
2. Fallback về `Company.default_receivable_account` hoặc `default_payable_account`.
3. Nếu `include_advance`: có thể trả về advance account.

### 8.3 `validate_party_accounts(doc)`

Với mỗi account trong `doc.accounts`:
- Account phải có `account_type = Receivable/Payable` phù hợp.
- Phải thuộc đúng company.

### 8.4 `set_taxes(party, party_type, posting_date, company, customer_group, ...)`

Xác định `taxes_and_charges` template cho transaction:

```
1. Kiểm tra Tax Category của địa chỉ (billing address)
2. Kiểm tra Tax Rule matching:
   - tax_type (Sales/Purchase)
   - customer/supplier
   - customer_group / supplier_group
   - billing_country, shipping_country
   - tax_category
3. Trả về Sales Tax Template hoặc Purchase Tax Template phù hợp nhất
```

### 8.5 Due Date Calculation

#### `get_due_date(posting_date, party_type, party, company, bill_date)`

```
1. Lấy payment_terms_template từ party
2. Nếu có template: gọi get_due_date_from_template()
3. Nếu không: due_date = posting_date + credit_days
```

#### `validate_due_date(posting_date, due_date, bill_date, template_name, doctype)`

Kiểm tra `due_date >= posting_date`. Với Payment Terms: kiểm tra theo template.

---

## 9. SalesInvoice — Python

**File:** `erpnext/accounts/doctype/sales_invoice/sales_invoice.py`

### 9.1 `__init__` — Status Updater

```python
self.status_updater = [
    {
        "source_dt": "Sales Invoice Item",
        "target_field": "billed_amt",
        "target_ref_field": "amount",
        "target_dt": "Sales Order Item",
        "join_field": "so_detail",
        "target_parent_dt": "Sales Order",
        "target_parent_field": "per_billed",
        "source_field": "amount",
        "percent_join_field": "sales_order",
        "status_field": "billing_status",
        "keyword": "Billed",
        "overflow_type": "billing",
    }
]
```

Khi `update_stock = 1`, bổ sung thêm:

```python
# Cập nhật delivered_qty cho DN Item
{
    "source_dt": "Sales Invoice Item",
    "target_dt": "Delivery Note Item",
    "join_field": "dn_detail",
    "target_field": "billed_qty",
    ...
}
```

### 9.2 `validate()` — Toàn bộ Chuỗi

```
validate_auto_set_posting_time()     → POS: auto set posting time = now
super().validate()                   → AccountsController.validate() (xem §3.1)
is_subcontracted()                   → detect SI có gia công không
so_dn_required()                     → bắt buộc SO/DN nếu cài đặt
SalesTaxWithholding(self).on_validate() → tính TCS
validate_proj_cust()                 → project thuộc customer
POSService.validate_pos_return()
validate_with_previous_doc()         → so sánh SO, SO Item, DN, DN Item
validate_uom_is_integer()
check_sales_order_on_hold_or_close()
validate_debit_to_acc()              → kiểm tra Debit To account
clear_unallocated_advances()
FixedAssetService.validate_fixed_asset()
FixedAssetService.set_income_account_for_fixed_assets()
validate_item_cost_centers()
check_conversion_rate()
validate_accounts()                  → income account phải là P&L
validate_inter_company_party()
validate_coupon_code()
[is_pos] validate_pos()
[is_created_using_pos] validate_full_payment()
validate_dropship_item()
[update_stock] validate_warehouse() + update_current_stock()
validate_delivery_note()             → DN không bị return
validate_service_stop_date()
set_against_income_account()         → gộp income accounts
BillingValidationService.validate_multiple_billing() → không overbill DN
validate_update_stock_for_pick_list_reference()
set_serial_and_batch_bundle_from_pick_list()
update_packing_list()
TimesheetBillingService.set_billing_hours_and_amount()
set_status()
[redeem_loyalty] validate_loyalty_points()
validate_subcontracted_sales_order()
```

### 9.3 `validate_debit_to_acc(self)`

```python
# 1. Nếu chưa có debit_to: lấy từ get_party_account("Customer", ...)
if not self.debit_to:
    self.debit_to = get_party_account("Customer", self.customer, self.company)

# 2. Kiểm tra account properties
account = frappe.get_cached_value("Account", self.debit_to,
    ["account_type", "report_type", "account_currency"])

# 3. Bắt buộc Balance Sheet
assert account.report_type == "Balance Sheet"

# 4. Bắt buộc Receivable type
assert account.account_type == "Receivable"

# 5. Lưu party_account_currency
self.party_account_currency = account.account_currency
```

### 9.4 `on_submit(self)` — Toàn bộ Chuỗi

```
POSService.validate_pos_paid_amount()   → POS: Σ payments == grand_total
Authorization Control.validate_approving_authority()
check_prev_docstatus()                  → DN, SO phải submitted
[is_return] tắt status_updater
SalesTaxWithholding.on_submit()         → tạo TCS entries
update_status_updater_args()            → nếu update_stock: thêm DN updater
update_prevdoc_status()                 → cập nhật billed_amt, per_billed trên SO Item và DN Item
update_billing_status_in_dn()           → cập nhật billed_amt, per_billed trên DN
clear_unallocated_mode_of_payments()    → POS: xóa payments chưa phân bổ
[update_stock=1]:
    make_bundle_for_sales_purchase_return()
    make_bundle_using_old_serial_batch_fields()
    validate_standalone_serial_nos_customer()
    update_stock_reservation_entries()
    update_stock_ledger()               → tạo SLE (actual_qty âm)
FixedAssetService.split_asset_based_on_sale_qty()
FixedAssetService.process_asset_depreciation()
make_gl_entries()                       → tạo GL Entries (xem §9.5)
[update_stock=1]: repost_future_sle_and_gle() + update_pick_list_status()
[không phải return]:
    update_billing_status_for_zero_amount_refdoc("Delivery Note")
    update_billing_status_for_zero_amount_refdoc("Sales Order")
    check_credit_limit()
[không phải POS, không phải return]:
    update_against_document_in_jv()     → liên kết advance payments
TimesheetBillingService.update_time_sheet(self.name)
[sales_update_frequency = "Each Transaction"]:
    update_company_current_month_sales()
    update_project()
update_linked_doc()                     → liên kết SI inter-company
update_coupon_code_count()
LoyaltyService.make_loyalty_point_entry() hoặc delete + re-create
process_common_party_accounting()
update_billed_qty_in_scio()
```

### 9.5 `make_gl_entries(self)` / `get_gl_entries(self)`

Ủy quyền cho `SalesInvoiceGLComposer(self).compose()` trong `services/gl_composer.py`.

**Bút toán điển hình SI submit:**

```
Trường hợp 1: SI thông thường
  Debit:  Customer Account (debit_to)   = grand_total
  Credit: Income Account               = net_amount (từng item)
  Credit: Tax Account                  = tax_amount (từng dòng thuế)

Trường hợp 2: SI có update_stock
  Thêm:
  Debit:  Cost of Goods Sold (expense_account)
  Credit: Warehouse Account (Stock Account)

Trường hợp 3: SI POS
  Debit:  Cash/Bank Account (payments)  = paid_amount
  Credit: Customer Account (debit_to)   = paid_amount
  [write_off]:
  Debit:  Write Off Account             = write_off_amount
  Credit: Customer Account (debit_to)   = write_off_amount

Trường hợp 4: Discount Accounting enabled
  Debit:  Discount Account              = discount_amount
  Credit: Income Account               = (net_amount - discount)

Trường hợp 5: Fixed Asset Sale
  Debit:  Asset Account                 = net_book_value
  Debit:  Accumulated Depreciation      = accumulated_dep
  Credit: Income Account               = sale_amount
  [gain] Credit: Capital Gains Account
  [loss] Debit:  Loss on Asset Disposal
```

### 9.6 `update_billing_status_in_dn(self, update_modified=True)`

Sau khi SI được submit/cancel:
1. Với mỗi SI Item có `dn_detail`: tổng hợp `billed_amt` từ tất cả SI Items liên kết.
2. Cập nhật `billed_amt` trên DN Item.
3. Tính lại `per_billed` trên Delivery Note.
4. Cập nhật `billing_status` trên DN.

### 9.7 TCS — Tax Collected at Source

#### `SalesTaxWithholding(self).on_validate()`

Tính TCS (Tax Collected at Source — thuế thu hộ):
1. Xác định `tax_withholding_category` từ customer.
2. Tính `taxable_amount` dựa trên items và ngưỡng cumulative.
3. Tạo dòng thuế TCS trong `tax_withholding_entries`.

#### `SalesTaxWithholding(self).on_submit()`

Tạo `Tax Withholding Entry` document để tracking.

### 9.8 Loyalty Points

#### `LoyaltyService(self).make_loyalty_point_entry()`

Khi submit SI (không phải return):
1. Tính `loyalty_points_earned = grand_total * conversion_factor / redemption_amount`.
2. Tạo `Loyalty Point Entry` document.

#### `LoyaltyService(self).apply_loyalty_points()`

Khi `redeem_loyalty_points = 1`:
1. Tạo GL Entry: Debit Loyalty Program Account, Credit Customer Account.
2. Giảm `outstanding_amount` tương ứng.

### 9.9 `set_status(self)`

```python
if docstatus == 2: return "Cancelled"
if docstatus == 0: return "Draft"
if is_return == 1: return "Return"
if credit_note_issued: return "Credit Note Issued"
if outstanding_amount == 0: return "Paid"
if outstanding_amount > 0 and due_date < today: return "Overdue"
if 0 < outstanding_amount < grand_total: return "Partly Paid"
return "Unpaid"
```

### 9.10 `on_cancel(self)` — Toàn bộ Chuỗi

```
check_if_return_invoice_linked_with_payment_entry() → không hủy nếu có PE
super().on_cancel()                                  → AccountsController.on_cancel()
check_sales_order_on_hold_or_close()
[is_return] tắt status_updater
update_status_updater_args()
update_prevdoc_status()
update_billing_status_in_dn()
[không phải return]:
    update_billing_status_for_zero_amount_refdoc()
SalesTaxWithholding.on_cancel()
[update_stock=1] update_stock_ledger()
FixedAssetService.process_asset_depreciation()      → reverse depreciation
make_gl_entries_on_cancel()                          → reverse GL
[update_stock=1] update_stock_reservation_entries() + repost_future_sle_and_gle()
db_set("status", "Cancelled")
update_coupon_code_count("cancelled")
LoyaltyService.delete_loyalty_point_entry()
unlink_inter_company_doc()
TimesheetBillingService.unlink_sales_invoice_from_timesheets()
delete_auto_created_batches()
update_billed_qty_in_scio()
```

---

## 10. SalesInvoice — JavaScript

**File:** `erpnext/accounts/doctype/sales_invoice/sales_invoice.js`

### 10.1 Khởi tạo — Module-level

```javascript
// Đăng ký tax validations cho "Sales Invoice"
erpnext.accounts.taxes.setup_tax_validations("Sales Invoice");
erpnext.accounts.payment_triggers.setup("Sales Invoice");
erpnext.accounts.pos.setup("Sales Invoice");
erpnext.accounts.taxes.setup_tax_filters("Sales Taxes and Charges");
erpnext.sales_common.setup_selling_controller();

// Định nghĩa tax_table cho TransactionController
cur_frm.cscript.tax_table = "Sales Taxes and Charges";
```

### 10.2 Class `SalesInvoiceController` — Methods

#### `setup(doc)`

```javascript
this.setup_accounting_dimension_triggers(); // Triggers cho accounting dimensions
this.setup_posting_date_time_check();        // Kiểm tra posting date/time
super.setup(doc);                            // TransactionController.setup()
this.frm.make_methods = {
    "Dunning": this.make_dunning.bind(this),
    "Invoice Discounting": this.make_invoice_discounting.bind(this),
};
```

#### `onload()`

```javascript
// Các doctypes không cần cancel confirmation khi cancel SI
this.frm.ignore_doctypes_on_cancel_all = [
    "POS Invoice", "Timesheet", "POS Invoice Merge Log",
    "POS Closing Entry", "Journal Entry", "Payment Entry",
    "Repost Payment Ledger", "Repost Accounting Ledger",
    "Unreconcile Payment", "Serial and Batch Bundle",
    "Bank Transaction", "Packing Slip"
];

// Nếu không có customer nhưng có debit_to: hiện debit_to trong print
if (!doc.customer && doc.debit_to) {
    frm.set_df_property("debit_to", "print_hide", 0);
}

// Setup warehouse query
erpnext.queries.setup_queries(frm, "Warehouse", ...);

// Nếu mới và is_pos: trigger is_pos ngay
if (doc.__islocal && doc.is_pos) {
    frm.script_manager.trigger("is_pos");
}
```

#### `refresh(doc)` — Buttons & State Management

```javascript
// Toggle required cho due_date (không cần cho return)
frm.toggle_reqd("due_date", !doc.is_return);

// Hiện GL và Stock Ledger buttons
this.show_general_ledger();
erpnext.accounts.ledger_preview.show_accounting_ledger_preview(frm);
if (doc.update_stock) this.show_stock_ledger();

// Buttons theo state
if (docstatus == 1 && outstanding_amount != 0 && can_create("Payment Entry")) {
    frm.add_custom_button("Payment", () => this.make_payment_entry(), "Create");
    frm.page.set_inner_btn_group_as_primary("Create");
}

if (docstatus == 1 && !is_return) {
    // Return / Credit Note
    if (outstanding_amount >= 0 || |outstanding| < grand_total) {
        frm.add_custom_button("Return / Credit Note", this.make_sales_return, "Create");
    }

    // Delivery Note (nếu có items chưa giao)
    if (!update_stock && has_undelivered_items) {
        frm.add_custom_button("Delivery Note", frm.cscript["Make Delivery Note"], "Create");
    }

    // Payment Request
    if (outstanding_amount > 0 && user_in_create("Payment Request")) {
        frm.add_custom_button("Payment Request", ..., "Create");
    }

    // Invoice Discounting
    if (outstanding_amount > 0) {
        frm.add_custom_button("Invoice Discounting", ..., "Create");
    }

    // Dunning (nếu quá hạn)
    if (payment_is_overdue) {
        frm.add_custom_button("Dunning", ..., "Create");
    }

    // Maintenance Schedule (cho SI liên quan thiết bị)
    frm.add_custom_button("Maintenance Schedule", ..., "Create");
}

// Get Items From (draft only)
this.toggle_get_items(); // → SO, Quotation, Timesheet, DN buttons

// Inter Company Invoice
if (docstatus == 1 && is_internal_customer && !inter_company_invoice_reference) {
    frm.add_custom_button(
        "Internal/Inter Company Purchase Invoice",
        () => this.make_inter_company_invoice(), "Create"
    );
}

// Unreconcile Payment button
erpnext.accounts.unreconcile_payment.add_unreconcile_btn(frm);
```

#### Triggers quan trọng

```javascript
// customer trigger
customer() {
    // Gọi get_party_details() server-side
    // Điền debit_to, payment_terms, price_list, address...
    erpnext.utils.get_party_details(frm, null, null, () => {
        me.apply_pricing_rule();
    });
}

// update_stock trigger
update_stock() {
    // Toggle visibility warehouse columns
    frm.set_df_property("update_stock", ..., frm.doc.update_stock);
    // Tạo/xóa các fields kho
}

// is_pos trigger
is_pos() {
    if (doc.is_pos) {
        // Load POS profile settings
        frm.call("set_missing_values");
        // Hiện POS payments section
        frm.set_df_property("payments", "hidden", 0);
    }
}

// debit_to trigger
debit_to() {
    // Validate account type
    if (doc.debit_to) frm.call("validate_debit_to_acc");
}

// payments.mode_of_payment trigger
// Khi thay đổi mode_of_payment trong bảng payments:
// → erpnext.accounts.pos.get_payment_mode_account()
// → Điền account cho mode đó
```

#### `make_sales_return()`

```javascript
frappe.model.open_mapped_doc({
    method: "erpnext.accounts.doctype.sales_invoice.mapper.make_return_doc",
    frm: cur_frm
});
```

#### `make_payment_entry()`

```javascript
// Kế thừa từ TransactionController
return frappe.call({
    method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
    args: {
        dt: frm.doc.doctype,
        dn: frm.doc.name,
    },
    callback: (r) => {
        var doc = frappe.model.sync(r.message)[0];
        frappe.set_route("Form", doc.doctype, doc.name);
    },
});
```

---

## 11. PurchaseInvoice — Python

**File:** `erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py`

### 11.1 `__init__` — Status Updater

```python
self.status_updater = [
    # Cập nhật billed_qty trên PO Item
    {
        "source_dt": "Purchase Invoice Item",
        "target_dt": "Purchase Order Item",
        "join_field": "po_detail",
        "target_field": "billed_qty",
        "target_ref_field": "qty",
        "source_field": "qty",
        "percent_join_field": "purchase_order",
        "overflow_type": "billing",
    },
    # Cập nhật billed_qty trên PR Item
    {
        "source_dt": "Purchase Invoice Item",
        "target_dt": "Purchase Receipt Item",
        "join_field": "pr_detail",
        "target_field": "billed_qty",
        ...
    },
]
```

### 11.2 `validate()` — Toàn bộ Chuỗi

```
validate_posting_time()
validate_posting_date_with_po()      → ngày PI không trước ngày PO
super().validate()                   → AccountsController.validate()
[không return]:
    po_required()                    → bắt buộc PO nếu cài đặt
    pr_required()                    → bắt buộc PR nếu cài đặt
    validate_supplier_invoice()      → validate bill_no, bill_date duplicate
[is_paid] validate_cash()           → kiểm tra cash purchase
validate_service_stop_date()
validate_release_date()              → PI bị hold: release_date phải hợp lệ
check_conversion_rate()
validate_credit_to_acc()             → kiểm tra Credit To account (Payable type)
clear_unallocated_advances()
check_for_on_hold_or_closed_status("Purchase Order")
validate_with_previous_doc()         → so sánh PO, PO Item, PR, PR Item
validate_uom_is_integer()
set_expense_account(for_validate=True) → tự động điền expense_account
validate_expense_account()
set_against_expense_account()        → gộp expense accounts
validate_write_off_account()
validate_write_off_cost_center()
BillingValidationService.validate_multiple_billing("Purchase Receipt") → không overbill PR
set_status()
validate_purchase_receipt_if_update_stock()
validate_inter_company_party()
reset_default_field_value()
PurchaseTaxWithholding.on_validate() → tính TDS
set_percentage_received()            → tính % đã nhận
```

### 11.3 `validate_credit_to_acc(self)`

```python
# Tương tự validate_debit_to_acc của SI nhưng cho Payable
if not self.credit_to:
    self.credit_to = get_party_account("Supplier", self.supplier, self.company)

account = frappe.get_cached_value("Account", self.credit_to, ...)

# Bắt buộc Balance Sheet
assert account.report_type == "Balance Sheet"

# Bắt buộc Payable type
assert account.account_type == "Payable"

self.party_account_currency = account.account_currency
```

### 11.4 `set_expense_account(self, for_validate=False)`

Tự động điền `expense_account` cho từng item nếu chưa có:

```python
for item in self.items:
    if not item.expense_account:
        if item.is_fixed_asset:
            item.expense_account = get_asset_account("asset_received_but_not_billed", ...)
        elif item.is_stock_item and perpetual_inventory:
            item.expense_account = get_stock_account(item.warehouse)
        else:
            item.expense_account = get_default_expense_account(item)
```

### 11.5 `validate_supplier_invoice(self)`

Kiểm tra `bill_no` và `bill_date`:
- Nếu Buying Settings `check_supplier_invoice_uniqueness = 1`: kiểm tra `bill_no + supplier` không duplicate với PI khác đã submitted.
- `bill_no` không được quá 140 ký tự (giới hạn GST Ấn Độ).

### 11.6 `on_submit(self)` — Toàn bộ Chuỗi

```
super().on_submit()                         → BuyingController.on_submit() → set last_purchase_rate
PurchaseTaxWithholding.on_submit()          → tạo TDS entries
check_prev_docstatus()                      → PR, PO phải submitted
[is_return] tắt status_updater
update_status_updater_args()
update_prevdoc_status()                     → cập nhật billed_qty, per_billed trên PO và PR
Authorization Control.validate_approving_authority()
[không phải return]:
    update_against_document_in_jv()        → liên kết advance payments
    update_billing_status_for_zero_amount_refdoc("Purchase Receipt")
    update_billing_status_for_zero_amount_refdoc("Purchase Order")
update_billing_status_in_pr()              → cập nhật billed_amt trên PR Item
[update_stock=1]:
    make_bundle_for_sales_purchase_return()
    make_bundle_using_old_serial_batch_fields()
    update_stock_ledger()
make_gl_entries()                          → tạo GL Entries
[update_stock=1] repost_future_sle_and_gle()
[project_update_frequency="Each Transaction"] update_project()
update_linked_doc()                        → liên kết PI inter-company
process_common_party_accounting()
```

### 11.7 `make_gl_entries(self)` / `get_gl_entries(self)`

Ủy quyền cho `PurchaseInvoiceGLComposer(self).compose()`.

**Bút toán điển hình PI submit:**

```
Trường hợp 1: PI thông thường
  Debit:  Expense Account             = net_amount (từng item)
  Debit:  Tax Account                 = tax_amount (từng dòng thuế input tax)
  Credit: Supplier Account (credit_to) = grand_total

Trường hợp 2: PI có update_stock (thay thế PR)
  Thêm:
  Debit:  Warehouse Account (Stock)   = valuation_amount
  Credit: Stock Received But Not Billed (SRBNB)

Trường hợp 3: PI liên kết với PR (không update_stock)
  Debit:  Stock Received But Not Billed (SRBNB) → đảo bút toán PR
  Credit: Supplier Account             = grand_total
  [adjust_incoming_rate]:
  Debit/Credit: Price Difference Account (chênh lệch giá PI vs PR)

Trường hợp 4: PI paid (cash purchase)
  Thêm:
  Debit:  Supplier Account             = paid_amount
  Credit: Cash/Bank Account            = paid_amount

Trường hợp 5: Provisional Accounting (non-stock items)
  (gọi trong PR.add_provisional_gl_entry khi PI submit)
  Debit:  Provisional Account          → đảo provisional entry từ PR
  Credit: Expense Account              = amount

Trường hợp 6: Fixed Asset (CWIP)
  Debit:  Asset Received But Not Billed (ARBNB) → đảo CWIP từ PR
  Credit: Supplier Account
  (asset được capitalized riêng qua Asset doctype)
```

### 11.8 `cancel_provisional_entries(self)`

Khi hủy PI đã link với PR có provisional accounting:
1. Lấy tất cả GL Entries provisional liên quan.
2. Gọi `add_provisional_gl_entry(item, ..., reverse=True)` trên PR → tạo GL đảo ngược.

### 11.9 `update_billing_status_in_pr(self, update_modified=True)`

Sau khi PI submit/cancel:
1. Với mỗi PI Item có `pr_detail`: tổng hợp `billed_amt`.
2. Cập nhật `billed_amt` trên PR Item.
3. Gọi `update_billing_percentage(pr_doc)` trên từng PR liên quan.
4. Nếu cần: gọi `adjust_incoming_rate_for_pr(pr_doc)` để điều chỉnh valuation rate.

### 11.10 `set_status(self)`

```python
if docstatus == 2: return "Cancelled"
if is_return: return "Return"
if is_on_hold: return "On Hold"
if outstanding_amount == 0: return "Paid"
if outstanding_amount > 0 and due_date < today: return "Overdue"
if 0 < outstanding_amount < grand_total: return "Partly Paid"
return "Unpaid"
```

### 11.11 `block_invoice(self, hold_comment, release_date)` / `unblock_invoice(self)`

- `block_invoice`: set `on_hold = 1`, `release_date`, `hold_comment`.
- `unblock_invoice`: set `on_hold = 0`, xóa `release_date`.
- PI bị hold không thể tạo Payment Entry cho đến khi unblock.

---

## 12. PurchaseInvoice — JavaScript

**File:** `erpnext/accounts/doctype/purchase_invoice/purchase_invoice.js`

### 12.1 Khởi tạo Module-level

```javascript
cur_frm.cscript.tax_table = "Purchase Taxes and Charges";
erpnext.accounts.payment_triggers.setup("Purchase Invoice");
erpnext.accounts.taxes.setup_tax_filters("Purchase Taxes and Charges");
erpnext.accounts.taxes.setup_tax_validations("Purchase Invoice");
erpnext.buying.setup_buying_controller();
```

### 12.2 Class `PurchaseInvoice` — Methods

#### `setup(doc)`

```javascript
this.setup_accounting_dimension_triggers();
this.setup_posting_date_time_check();
super.setup(doc);

// Indicator formatter: màu xanh nếu đã nhận đủ
if (doc.update_stock) {
    frm.set_indicator_formatter("item_code", (row) =>
        row.qty <= row.received_qty ? "green" : "orange"
    );
}

// Query filters
frm.set_query("unrealized_profit_loss_account", () => ({
    filters: { company: doc.company, is_group: 0, root_type: "Liability" }
}));

frm.set_query("expense_account", "items", () => ({
    query: "erpnext.controllers.queries.get_expense_account",
    filters: { company: doc.company, disabled: 0 }
}));
```

#### `refresh(doc)` — Buttons

```javascript
// Block/Unblock buttons (khi outstanding > 0)
if (docstatus == 1 && !is_return && outstanding_amount != 0) {
    if (doc.on_hold) {
        frm.add_custom_button("Change Release Date", ..., "Hold Invoice");
        frm.add_custom_button("Unblock Invoice", ..., "Create");
    } else {
        frm.add_custom_button("Block Invoice", ..., "Create");
    }
}

// Payment button
if (docstatus == 1 && outstanding_amount != 0 && !on_hold) {
    frm.add_custom_button("Payment", () => make_payment_entry(), "Create");
}

// Return / Debit Note
if (docstatus == 1 && !is_return && outstanding_amount >= 0) {
    frm.add_custom_button("Return / Debit Note", make_debit_note, "Create");
}

// Payment Request
if (docstatus == 1 && outstanding_amount > 0 && !is_return && !on_hold) {
    frm.add_custom_button("Payment Request", ..., "Create");
}

// Get Items From (draft)
if (docstatus == 0) {
    // Purchase Order
    frm.add_custom_button("Purchase Order", () => map_current_doc({
        method: "erpnext.buying.doctype.purchase_order.mapper.make_purchase_invoice",
        source_doctype: "Purchase Order",
        ...
    }), "Get Items From");

    // Purchase Receipt
    frm.add_custom_button("Purchase Receipt", () => map_current_doc({
        method: "erpnext.stock.doctype.purchase_receipt.mapper.make_purchase_invoice",
        ...
    }), "Get Items From");
}

// Inter Company Invoice
if (docstatus == 1 && !inter_company_invoice_reference && supplier.is_internal_supplier) {
    frm.add_custom_button("Inter Company Invoice", ..., "Create");
}
```

---

## 13. PaymentEntry — Python

**File:** `erpnext/accounts/doctype/payment_entry/payment_entry.py`

### 13.1 Cấu trúc Payment Entry

```
Payment Entry
├── party_type: Customer / Supplier / Employee / Shareholder
├── party: tên party
├── payment_type: Receive / Pay / Internal Transfer
├── paid_from: tài khoản nguồn
├── paid_to: tài khoản đích
├── paid_amount: số tiền
├── received_amount: số tiền nhận
├── references[]: danh sách hóa đơn phân bổ
│   ├── reference_doctype: Sales Invoice / Purchase Invoice / JE
│   ├── reference_name
│   ├── allocated_amount
│   └── outstanding_amount
└── deductions[]: chênh lệch/phí bank
    ├── account
    └── amount
```

### 13.2 `setup_party_account_field(self)`

Xác định `party_account_field` dựa trên `payment_type` và `party_type`:

```python
if payment_type == "Receive":
    party_account_field = "paid_from"   # Thu tiền từ khách: ghi có AR
elif payment_type == "Pay":
    party_account_field = "paid_to"     # Trả tiền cho NCC: ghi nợ AP
else:
    party_account_field = "paid_from"
```

### 13.3 `validate(self)` — Chuỗi

```
validate_payment_type()              → payment_type phải hợp lệ với party_type
validate_party_details()             → party tồn tại và không bị block
set_missing_values()                 → điền missing fields
set_exchange_rate()                  → lấy exchange rate ngày hôm đó
validate_payment_type_with_outstanding()
validate_allocated_amount()          → không phân bổ vượt outstanding
validate_allocated_amount_with_latest_data() → check lại với DB
validate_reference_documents()       → validate từng reference doc
validate_paid_invoices()             → hóa đơn phải submitted
set_amounts()                        → tính totals
validate_amounts()
set_status()
```

### 13.4 `set_amounts(self)`

```python
# 1. Tổng allocated amount
total_allocated_amount = Σ reference.allocated_amount

# 2. Unallocated amount
unallocated_amount = paid_amount - total_allocated_amount

# 3. Difference amount (exchange gain/loss + fees)
difference_amount = paid_amount - received_amount - deductions

# 4. Tính set_exchange_gain_loss()
```

### 13.5 `on_submit(self)` — Chuỗi

```
set_amounts_in_company_currency()
validate_amounts()
validate_duplicate_entry()
set_liability_account()             → Nếu dùng separate advance account
make_gl_entries()                   → tạo GL Entries
update_advance_paid()               → cập nhật advance_paid trên party
update_payment_schedule()           → cập nhật payment schedule trên invoices
set_status()
[if advance] update_payment_requests()
```

### 13.6 `build_gl_map(self)` / `make_gl_entries(self)`

Ủy quyền cho `PaymentEntryGLComposer(self).compose()`.

**Bút toán theo payment_type:**

```
Receive (Thu tiền từ khách):
  Debit:  paid_to (Bank/Cash)            = received_amount
  Credit: paid_from (AR - Customer)       = paid_amount
  [exchange gain/loss]:
  Debit/Credit: Exchange Gain/Loss Account

Pay (Trả tiền cho NCC):
  Debit:  paid_to (AP - Supplier)         = paid_amount
  Credit: paid_from (Bank/Cash)           = received_amount

Internal Transfer:
  Debit:  paid_to (Bank Account B)        = received_amount
  Credit: paid_from (Bank Account A)      = paid_amount

Deductions (bank charges, discount):
  Debit:  Deduction Account               = deduction_amount
  Credit/Debit: Party Account (adjust)
```

### 13.7 `make_advance_gl_entries(self, cancel=False)`

Khi `book_advance_payments_in_separate_party_account = True`:
- Tạo thêm GL Entries chuyển balance từ advance account sang regular party account khi payment được phân bổ cho invoice.

### 13.8 `update_payment_schedule(self, cancel=0)`

Sau khi PE submit, cập nhật `Payment Schedule` trên từng invoice:
- Đánh dấu payment schedule rows đã thanh toán.
- Cập nhật `paid_amount` và `outstanding` trên từng schedule row.

---

## 14. JournalEntry — Python

**File:** `erpnext/accounts/doctype/journal_entry/journal_entry.py`

### 14.1 Cấu trúc

```
Journal Entry
├── voucher_type: Bank Entry / Cash Entry / Credit Note / Debit Note
│                Journal Entry / Opening Entry / Contra Entry
│                Exchange Gain Or Loss / Write Off / Depreciation
├── accounts[]: danh sách bút toán
│   ├── account
│   ├── debit_in_account_currency / credit_in_account_currency
│   ├── party_type / party
│   ├── against_voucher_type / against_voucher
│   └── is_advance
└── multi_currency: 0/1
```

### 14.2 `validate(self)` — Chuỗi

```
validate_party()                    → party hợp lệ
validate_entries_for_advance()      → advance entries đúng format
validate_multi_currency()           → nếu multi_currency: account currency đúng
set_amounts_in_company_currency()   → tính base_debit/credit
set_exchange_rate()                 → lấy exchange rate
validate_debit_credit_amount()      → debit == credit
validate_total_debit_and_credit()   → tổng debit == tổng credit
validate_against_jv()               → không tự reference chính mình
validate_reference_doc()            → validate against_voucher
validate_orders()                   → SO/PO liên kết hợp lệ
validate_invoices()                 → SI/PI liên kết hợp lệ
set_against_account()               → điền trường 'against'
check_credit_limit()                → kiểm tra hạn mức
validate_cheque_info()              → Bank Entry: cheque_no và cheque_date
validate_inter_company_accounts()   → tài khoản inter-company khớp
validate_depr_account_and_depr_entry_voucher_type()
validate_stock_accounts()           → Stock Adjustment entry: phải có SLE
```

### 14.3 `on_submit(self)` — Chuỗi

```
make_gl_entries()                   → tạo GL Entries
update_asset_value()                → cập nhật asset value (Asset Adjustment)
update_asset_on_depreciation()      → ghi depreciation vào Asset
update_inter_company_jv()           → liên kết JE inter-company
update_invoice_discounting()        → cập nhật Invoice Discounting status
```

### 14.4 GL Entries của Journal Entry

JE tạo trực tiếp GLE từ mỗi dòng trong `accounts`:

```python
for d in self.accounts:
    gl_entry = {
        "account": d.account,
        "debit": d.debit,
        "credit": d.credit,
        "party_type": d.party_type,
        "party": d.party,
        "against_voucher_type": d.reference_type,
        "against_voucher": d.reference_name,
        "is_advance": d.is_advance,
        ...
    }
```

---

## 15. JS Controllers

### 15.1 `erpnext.TransactionController` (transaction.js)

Class JS trung tâm — tất cả doctype bán hàng và mua hàng đều kế thừa.

**Kế thừa:** `erpnext.taxes_and_totals` → `erpnext.TransactionController`

#### `setup()` — Đăng ký Triggers

```javascript
// item.rate trigger
frappe.ui.form.on(doctype + " Item", "rate", (frm, cdt, cdn) => {
    // Tính discount_percentage từ rate vs price_list_rate
    // Hoặc margin nếu rate > price_list_rate
    // Gọi calculate_taxes_and_totals()
    // Gọi get_item_tax_template() để validate tax template theo rate
});

// tax.rate, tax.tax_amount, tax.row_id, tax.included_in_print_rate triggers
// → calculate_taxes_and_totals()

// discount_amount trigger → calculate_taxes_and_totals()
// additional_discount_percentage trigger → tính discount_amount, rồi calculate

// items_add trigger
// → copy warehouse, target_warehouse, from_warehouse từ parent
// → copy accounting dimensions từ row đầu tiên
// → set use_serial_batch_fields nếu user mặc định

// return_against query
// → filter: docstatus=1, is_return=0, company, customer/supplier

// expense_account query
// → filter: company, report_type="Profit and Loss", is_group=0
```

#### `onload()`

```javascript
// Set default values cho doc mới
set_value("currency", default_currency);
set_value("price_list_currency", default_currency);
set_value("status", "Draft");
set_value("is_subcontracted", 0);
if (company && !amended_from) frm.trigger("company");
```

#### Phương thức quan trọng

```javascript
calculate_taxes_and_totals()
// → Gọi server-side: doc.calculate_taxes_and_totals()
// → Hoặc client-side calculation (xem taxes_and_totals.js)

get_item_details(item_code, ...)
// → frappe.call("erpnext.stock.get_item_details.get_item_details")
// → Điền rate, description, tax_template, income/expense account...

set_query_for_batch(doc, cdt, cdn)
// → Filter batch theo item_code và expiry_date

setup_quality_inspection()
// → Thêm nút "Quality Inspection(s)" trên draft forms

make_quality_inspection()
// → Tạo Quality Inspection documents cho các items
```

### 15.2 `erpnext.accounts.taxes` (accounts.js)

```javascript
erpnext.accounts.taxes = {
    // Đăng ký tax validations cho một doctype
    setup_tax_validations(doctype) {
        frappe.ui.form.on(doctype, {
            setup(frm) {
                // Conditional display rate/amount trong grid
                $(frm.wrapper).on("grid-row-render", ...);
            },
            onload(frm) {
                // Set query filter cho account_head trong taxes table
                frm.set_query("account_head", "taxes", (doc) => ({
                    query: "erpnext.controllers.queries.tax_account_query",
                    filters: { account_type: [...], company: doc.company }
                }));
            }
        });
    },

    // Validate một dòng tax
    validate_taxes_and_charges(cdt, cdn) {
        // charge_type = "Actual/On Net Total" → không được có row_id
        // charge_type = "On Previous Row..." → phải có row_id hợp lệ
    },

    // Thiết lập tax filter triggers
    setup_tax_filters(doctype) {
        frappe.ui.form.on(doctype, {
            account_head(frm, cdt, cdn) {
                // Khi chọn account_head: gọi get_tax_rate() server-side
                // Điền rate và description tự động
            },
            charge_type(frm, cdt, cdn) {
                // Toggle reqd/editable cho rate và tax_amount
            }
        });
    },

    // Validate tax inclusive
    validate_inclusive_tax(tax, frm) {
        // "Actual" không thể inclusive
        // On Previous Row Amount: row tham chiếu cũng phải inclusive
        // Valuation không thể inclusive
    }
};
```

### 15.3 `erpnext.accounts.payment_triggers` (accounts.js)

```javascript
erpnext.accounts.payment_triggers = {
    setup(doctype) {
        frappe.ui.form.on(doctype, {
            // Khi toggle allocate_advances_automatically:
            allocate_advances_automatically(frm) {
                frm.trigger("fetch_advances");
            },
            // Fetch advances server-side và điền vào bảng advances
            fetch_advances(frm) {
                if (frm.doc.allocate_advances_automatically) {
                    frappe.call({
                        doc: frm.doc,
                        method: "set_advances",
                        callback: () => refresh_field("advances")
                    });
                }
            }
        });
    }
};
```

### 15.4 `erpnext.accounts.pos` (accounts.js)

```javascript
erpnext.accounts.pos = {
    setup(doctype) {
        // Trigger khi thay đổi mode_of_payment trong bảng payments
        frappe.ui.form.on(doctype, {
            mode_of_payment(frm, cdt, cdn) {
                const d = locals[cdt][cdn];
                erpnext.accounts.pos.get_payment_mode_account(
                    frm, d.mode_of_payment,
                    (account) => frappe.model.set_value(cdt, cdn, "account", account)
                );
            }
        });
    },

    // Lấy account cho mode of payment
    get_payment_mode_account(frm, mode_of_payment, callback) {
        frappe.call({
            method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.get_bank_cash_account",
            args: { mode_of_payment, company: frm.doc.company },
            callback: (r) => {
                if (r.message) callback(r.message.account);
            }
        });
    }
};
```

---

## 16. Luồng Dữ liệu Tích hợp

### 16.1 Luồng GL Entry Đầy đủ

```
DocType.on_submit()
  └── make_gl_entries()
        └── get_gl_entries() → [list of gl_dict]
              └── GLComposer(self).compose()
                    ├── make_customer_gl_entry()    → Debit AR
                    ├── make_item_gl_entries()      → Credit Income, Debit COGS
                    ├── make_tax_gl_entries()        → Credit/Debit Tax Accounts
                    ├── make_payment_gl_entries()    → POS payments
                    └── make_write_off_gl_entry()    → Write off

        └── make_gl_entries(gl_map, cancel=False)  [general_ledger.py]
              ├── BudgetValidation.validate()
              ├── make_acc_dimensions_offsetting_entry()
              ├── validate_accounting_period()
              ├── validate_disabled_accounts()
              ├── process_gl_map()
              │     ├── distribute_gl_based_on_cost_center_allocation()
              │     ├── merge_similar_entries()
              │     └── toggle_debit_credit_if_negative()
              ├── create_payment_ledger_entry()     → Payment Ledger Entries
              └── save_entries()
                    ├── validate_cwip_accounts()
                    ├── process_debit_credit_difference()
                    │     └── make_round_off_gle() nếu cần
                    ├── check_freezing_date()
                    ├── validate_against_pcv()
                    ├── validate_allowed_dimensions()
                    └── make_entry() → GL Entry.submit()
                          └── validate_balance_type()
                          └── update_outstanding_amt()
                          └── validate_frozen_account()
```

### 16.2 Luồng Outstanding Amount

```
GL Entry submitted
  └── update_outstanding_amt(account, party_type, party, against_voucher_type, against_voucher)
        ├── Lấy tất cả GLE liên quan (is_cancelled=0)
        ├── Tính balance:
        │     SI: outstanding = Σ(credit_in_account_currency) - Σ(debit_in_account_currency)
        │     PI: outstanding = Σ(debit_in_account_currency) - Σ(credit_in_account_currency)
        └── DocType.db_set("outstanding_amount", balance)
            DocType.set_status()
```

### 16.3 Luồng Payment Reconciliation

```
Payment Entry submitted
  └── reconcile_against_document(lst)  [accounts/utils.py]
        ├── check_if_advance_entry_modified()
        ├── validate_allocated_amount()
        ├── update_reference_in_payment_entry()
        │     ├── Cancel GLE cũ của PE
        │     ├── Tạo GLE mới: against_voucher = Invoice
        │     └── Submit lại
        ├── create_payment_ledger_entry()  → PLE với against_voucher
        └── cancel_exchange_gain_loss_journal() nếu cần
              make_exchange_gain_loss_journal() nếu cần
```

### 16.4 Luồng Advance Payment

```
Customer trả trước (advance)
  → Payment Entry (Receive type, không có reference)
    → GLE: Debit Bank, Credit Customer AR
    → PLE: advance entry

SI submit
  → update_against_document_in_jv()  [accounts_controller.py]
      ├── Với mỗi advance.allocated_amount > 0
      └── reconcile_against_document([args])  [accounts/utils.py]
            ├── Cancel GLE advance: remove against_voucher
            ├── Tạo GLE mới: against_voucher = SI.name
            └── PLE: linked to SI
```

---

## 17. Hướng dẫn Phát triển Class Mới

### 17.1 Tạo Custom Document kế thừa AccountsController

Ví dụ: tạo `CustomSalesInvoice` với logic riêng.

```python
# custom_app/custom_app/doctype/custom_sales_invoice/custom_sales_invoice.py

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

class CustomSalesInvoice(SalesInvoice):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Thêm status updater mới nếu cần
        self.status_updater.append({
            "source_dt": "Custom Sales Invoice Item",
            "target_dt": "Custom Contract Item",
            "join_field": "contract_item",
            "target_field": "invoiced_qty",
            "source_field": "qty",
            "target_parent_dt": "Custom Contract",
            "target_parent_field": "per_invoiced",
            "overflow_type": "billing",
        })

    def validate(self):
        # Chạy custom validate trước
        self.validate_custom_fields()
        # Gọi parent validate
        super().validate()
        # Sau đó validate thêm
        self.validate_contract_reference()

    def validate_custom_fields(self):
        """Custom validation logic"""
        if self.custom_contract and not self.custom_contract_date:
            frappe.throw("Contract Date is required when Contract is set")

    def validate_contract_reference(self):
        """Kiểm tra items có đúng contract không"""
        for item in self.items:
            if item.custom_contract_item:
                contract_item = frappe.get_cached_value(
                    "Custom Contract Item",
                    item.custom_contract_item,
                    ["item_code", "remaining_qty"]
                )
                if contract_item.item_code != item.item_code:
                    frappe.throw(f"Row {item.idx}: Item code does not match contract")
                if item.qty > contract_item.remaining_qty:
                    frappe.throw(f"Row {item.idx}: Qty exceeds contract remaining qty")

    def on_submit(self):
        # Custom logic trước GL entries
        self.create_custom_entries()
        # Gọi parent (tạo GL entries, cập nhật status, v.v.)
        super().on_submit()
        # Custom logic sau GL entries
        self.notify_contract_manager()

    def create_custom_entries(self):
        """Tạo custom documents khi submit"""
        for item in self.items:
            if item.custom_contract_item:
                frappe.db.set_value(
                    "Custom Contract Item",
                    item.custom_contract_item,
                    "invoiced_qty",
                    frappe.db.get_value("Custom Contract Item",
                        item.custom_contract_item, "invoiced_qty") + item.qty
                )

    def get_gl_entries(self, inventory_account_map=None):
        """Override để thêm GL entries tùy chỉnh"""
        # Lấy GL entries từ parent
        gl_entries = super().get_gl_entries(inventory_account_map)

        # Thêm custom GL entry
        for item in self.items:
            if item.custom_commission_account:
                commission_amount = item.amount * 0.05  # 5% commission

                gl_entries.append(self.get_gl_dict({
                    "account": item.custom_commission_account,
                    "debit": commission_amount,
                    "debit_in_account_currency": commission_amount,
                    "against": self.customer,
                    "voucher_detail_no": item.name,
                    "remarks": f"Commission for {item.item_code}",
                    "cost_center": item.cost_center,
                    "project": item.project,
                }))

                gl_entries.append(self.get_gl_dict({
                    "account": self.debit_to,
                    "party_type": "Customer",
                    "party": self.customer,
                    "credit": commission_amount,
                    "credit_in_account_currency": commission_amount,
                    "against": item.custom_commission_account,
                    "voucher_detail_no": item.name,
                    "remarks": f"Commission for {item.item_code}",
                }))

        return gl_entries

    def on_cancel(self):
        # Đảo ngược custom logic
        self.reverse_custom_entries()
        super().on_cancel()

    def reverse_custom_entries(self):
        for item in self.items:
            if item.custom_contract_item:
                frappe.db.set_value(
                    "Custom Contract Item",
                    item.custom_contract_item,
                    "invoiced_qty",
                    frappe.db.get_value("Custom Contract Item",
                        item.custom_contract_item, "invoiced_qty") - item.qty
                )
```

### 17.2 Thêm Custom Service Layer (theo pattern ERPNext)

ERPNext dùng pattern Service classes để tách biệt logic:

```python
# custom_app/services/custom_tax_service.py

class CustomTaxService:
    """Service xử lý thuế đặc biệt của VN (VAT, PIT, CIT)"""

    def __init__(self, doc):
        self.doc = doc

    def on_validate(self):
        self.calculate_vat()
        self.calculate_withholding_tax()

    def calculate_vat(self):
        """Tính VAT theo quy định VN"""
        for item in self.doc.items:
            if item.is_vat_applicable:
                vat_rate = self.get_vat_rate(item.item_code)
                item.vat_amount = item.net_amount * vat_rate / 100

    def get_vat_rate(self, item_code):
        """Lấy VAT rate từ Item master"""
        vat_category = frappe.get_cached_value("Item", item_code, "custom_vat_category")
        rate_map = {"Standard": 10, "Reduced": 5, "Zero": 0, "Exempt": 0}
        return rate_map.get(vat_category, 10)

    def calculate_withholding_tax(self):
        """Tính thuế TNCN cho cá nhân"""
        if self.doc.party_type_custom == "Individual":
            for item in self.doc.items:
                if item.service_type:
                    item.withholding_tax = item.net_amount * 0.10  # 10% PIT
```

### 17.3 Customize bằng Frappe Hooks (không sửa core)

**Cách an toàn nhất — dùng hooks thay vì override:**

```python
# custom_app/hooks.py

doc_events = {
    "Sales Invoice": {
        "validate": "custom_app.overrides.sales_invoice.validate",
        "on_submit": "custom_app.overrides.sales_invoice.on_submit",
        "on_cancel": "custom_app.overrides.sales_invoice.on_cancel",
        "before_submit": "custom_app.overrides.sales_invoice.before_submit",
    },
    "GL Entry": {
        "before_insert": "custom_app.overrides.gl_entry.before_insert",
    }
}

override_doctype_class = {
    "Sales Invoice": "custom_app.overrides.custom_si.CustomSalesInvoice"
}
```

```python
# custom_app/overrides/sales_invoice.py

def validate(doc, method):
    """Được gọi sau validate() của SalesInvoice"""
    validate_custom_business_rules(doc)

def on_submit(doc, method):
    """Được gọi sau on_submit() của SalesInvoice"""
    create_custom_journal(doc)

def validate_custom_business_rules(doc):
    if doc.custom_po_number:
        # Kiểm tra PO number không duplicate
        existing = frappe.db.exists("Sales Invoice", {
            "custom_po_number": doc.custom_po_number,
            "customer": doc.customer,
            "docstatus": 1,
            "name": ("!=", doc.name)
        })
        if existing:
            frappe.throw(f"PO Number {doc.custom_po_number} already invoiced in {existing}")

def create_custom_journal(doc):
    """Tạo JE custom khi SI submit"""
    if doc.custom_commission_amount > 0:
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = doc.posting_date
        je.company = doc.company
        je.append("accounts", {
            "account": doc.custom_commission_payable_account,
            "credit": doc.custom_commission_amount,
            "party_type": "Supplier",
            "party": doc.custom_commission_agent,
        })
        je.append("accounts", {
            "account": doc.custom_commission_expense_account,
            "debit": doc.custom_commission_amount,
        })
        je.insert(ignore_permissions=True)
        je.submit()
        frappe.db.set_value("Sales Invoice", doc.name,
            "custom_commission_je", je.name)
```

### 17.4 Custom GL Composer

Để thêm bút toán hoàn toàn mới, tạo GL Composer riêng:

```python
# custom_app/services/custom_gl_composer.py

from erpnext.accounts.services.base_gl_composer import BaseGLComposer

class CustomSalesInvoiceGLComposer(BaseGLComposer):
    """GL Composer mở rộng cho Custom Sales Invoice"""

    def compose(self, inventory_account_map=None):
        # Lấy GL entries từ parent
        gl_entries = super().compose(inventory_account_map)

        # Thêm entries tùy chỉnh
        gl_entries += self.make_customs_duty_entries()
        gl_entries += self.make_export_incentive_entries()

        return gl_entries

    def make_customs_duty_entries(self):
        entries = []
        for item in self.doc.items:
            if item.customs_duty_amount:
                entries.append(self.doc.get_gl_dict({
                    "account": self.get_customs_duty_account(),
                    "debit": item.customs_duty_amount,
                    "against": self.doc.customer,
                    "voucher_detail_no": item.name,
                }, item=item))
                entries.append(self.doc.get_gl_dict({
                    "account": self.doc.debit_to,
                    "party_type": "Customer",
                    "party": self.doc.customer,
                    "credit": item.customs_duty_amount,
                    "against": self.get_customs_duty_account(),
                    "voucher_detail_no": item.name,
                }, item=item))
        return entries

    def get_customs_duty_account(self):
        return frappe.get_cached_value("Company", self.doc.company,
            "custom_customs_duty_account")


# Sử dụng trong CustomSalesInvoice
def get_gl_entries(self, inventory_account_map=None):
    from custom_app.services.custom_gl_composer import CustomSalesInvoiceGLComposer
    return CustomSalesInvoiceGLComposer(self).compose(inventory_account_map)
```

### 17.5 Custom Taxes and Totals

```python
# custom_app/overrides/taxes_and_totals.py

from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals as BaseCalc

class CustomCalculateTaxesAndTotals(BaseCalc):
    """Mở rộng logic tính toán thuế"""

    def _calculate(self):
        super()._calculate()
        # Thêm tính toán sau
        self.calculate_custom_charges()
        self.calculate_environmental_levy()

    def calculate_custom_charges(self):
        """Tính phụ phí tùy chỉnh"""
        if self.doc.get("custom_handling_charge_rate"):
            total_weight = sum(
                item.total_weight or 0
                for item in self.doc.items
            )
            self.doc.custom_handling_charge = (
                total_weight * self.doc.custom_handling_charge_rate
            )

    def calculate_environmental_levy(self):
        """Tính phí môi trường"""
        if self.doc.doctype in ("Sales Invoice", "Sales Order"):
            levy_items = [
                item for item in self.doc.items
                if frappe.get_cached_value("Item", item.item_code,
                    "custom_environmental_category")
            ]
            self.doc.custom_environmental_levy = sum(
                item.amount * 0.005  # 0.5%
                for item in levy_items
            )


# Đăng ký trong hooks.py
# override_whitelisted_methods = {
#     "erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals":
#         "custom_app.overrides.taxes_and_totals.CustomCalculateTaxesAndTotals"
# }
```

---

## 18. Tích hợp vào JS Frontend

### 18.1 Tạo Custom JS Controller

```javascript
// custom_app/public/js/custom_sales_invoice.js

// Mở rộng SalesInvoiceController
erpnext.accounts.CustomSalesInvoiceController = class CustomSalesInvoiceController
    extends erpnext.accounts.SalesInvoiceController {

    setup(doc) {
        super.setup(doc);
        // Thêm make_methods cho documents mới
        this.frm.make_methods = Object.assign(this.frm.make_methods || {}, {
            "Custom Commission Note": this.make_commission_note.bind(this),
        });
    }

    refresh(doc) {
        super.refresh();
        // Thêm buttons tùy chỉnh
        this.add_custom_buttons();
        // Cập nhật UI theo trạng thái
        this.update_custom_ui();
    }

    add_custom_buttons() {
        const doc = this.frm.doc;

        if (doc.docstatus === 1 && doc.custom_commission_amount > 0
                && !doc.custom_commission_je) {
            this.frm.add_custom_button(__("Commission Note"), () => {
                this.make_commission_note();
            }, __("Create"));
        }

        if (doc.docstatus === 0) {
            this.frm.add_custom_button(__("From Custom Contract"), () => {
                this.get_items_from_contract();
            }, __("Get Items From"));
        }
    }

    make_commission_note() {
        frappe.model.open_mapped_doc({
            method: "custom_app.doctype.custom_sales_invoice.mapper.make_commission_note",
            frm: this.frm,
        });
    }

    get_items_from_contract() {
        const me = this;
        // Dialog để chọn contract
        new frappe.ui.Dialog({
            title: __("Select Contract"),
            fields: [
                {
                    fieldname: "contract",
                    fieldtype: "Link",
                    options: "Custom Contract",
                    label: __("Contract"),
                    reqd: 1,
                    filters: {
                        customer: me.frm.doc.customer,
                        status: "Active",
                    }
                }
            ],
            primary_action_label: __("Get Items"),
            primary_action(values) {
                frappe.call({
                    method: "custom_app.doctype.custom_contract.custom_contract.get_items",
                    args: { contract: values.contract },
                    callback(r) {
                        if (r.message) {
                            r.message.forEach(item => {
                                const row = frappe.model.add_child(
                                    me.frm.doc, "Sales Invoice Item", "items"
                                );
                                frappe.model.set_value(row.doctype, row.name, {
                                    item_code: item.item_code,
                                    qty: item.qty,
                                    custom_contract_item: item.name,
                                });
                            });
                            me.frm.refresh_field("items");
                        }
                    }
                });
                this.hide();
            }
        }).show();
    }

    update_custom_ui() {
        const doc = this.frm.doc;
        // Ẩn/hiện fields tùy điều kiện
        this.frm.set_df_property(
            "custom_commission_section",
            "hidden",
            !doc.custom_has_commission
        );

        // Highlight nếu commission chưa xử lý
        if (doc.docstatus === 1
                && doc.custom_commission_amount > 0
                && !doc.custom_commission_je) {
            this.frm.dashboard.add_comment(
                __("Commission Note not yet created"),
                "yellow",
                true
            );
        }
    }

    // Override customer trigger để thêm logic
    customer() {
        // Gọi parent trước
        super.customer();

        // Sau đó thêm logic custom
        const me = this;
        if (this.frm.doc.customer) {
            frappe.db.get_value(
                "Customer",
                this.frm.doc.customer,
                ["custom_commission_rate", "custom_default_contract"],
                (r) => {
                    if (r) {
                        me.frm.set_value("custom_commission_rate",
                            r.custom_commission_rate);
                        if (r.custom_default_contract) {
                            me.frm.set_value("custom_default_contract",
                                r.custom_default_contract);
                        }
                    }
                }
            );
        }
    }

    // Thêm trigger cho field mới
    custom_commission_rate() {
        this.calculate_commission_amount();
    }

    calculate_commission_amount() {
        const doc = this.frm.doc;
        if (doc.custom_commission_rate && doc.net_total) {
            const commission = doc.net_total * doc.custom_commission_rate / 100;
            this.frm.set_value("custom_commission_amount",
                frappe.utils.flt(commission, precision("custom_commission_amount")));
        }
    }
};

// Đăng ký controller
frappe.ui.form.on("Custom Sales Invoice", {
    setup(frm) {
        frm.cscript = new erpnext.accounts.CustomSalesInvoiceController({ frm });
    }
});

// Hoặc nếu dùng cùng doctype "Sales Invoice" với custom fields:
// Extend existing controller
frappe.ui.form.on("Sales Invoice", {
    custom_commission_rate(frm) {
        // Tính commission khi thay đổi rate
        const commission = frm.doc.net_total * frm.doc.custom_commission_rate / 100;
        frm.set_value("custom_commission_amount",
            frappe.utils.flt(commission, precision("custom_commission_amount")));
    },

    refresh(frm) {
        // Thêm custom buttons mà không cần override toàn bộ controller
        if (frm.doc.docstatus === 1 && frm.doc.custom_commission_amount > 0) {
            frm.add_custom_button(__("Commission Note"), () => {
                frappe.model.open_mapped_doc({
                    method: "custom_app.mappers.make_commission_note",
                    frm: frm,
                });
            }, __("Create"));
        }
    }
});
```

### 18.2 Thêm Custom Field Triggers an toàn

```javascript
// Phương pháp an toàn nhất: extend qua frappe.ui.form.on()
// Không cần override cả controller

frappe.ui.form.on("Sales Invoice", {
    // Field-level trigger
    custom_project_budget(frm) {
        validate_budget_usage(frm);
    },

    // Item table trigger
    "items.custom_discount_override"(frm, cdt, cdn) {
        const item = locals[cdt][cdn];
        if (item.custom_discount_override > 30) {
            frappe.msgprint(__("Discount override exceeds 30%. Approval required."));
            frappe.model.set_value(cdt, cdn, "custom_requires_approval", 1);
        }
        frm.cscript.calculate_taxes_and_totals();
    },

    // Khi submit (before_submit không available qua form.on, dùng validate thay)
    validate(frm) {
        if (frm.doc._action === "submit") {
            // Logic chạy khi submit
            check_custom_approvals(frm);
        }
    }
});

function validate_budget_usage(frm) {
    if (!frm.doc.custom_project_budget || !frm.doc.customer) return;

    frappe.call({
        method: "custom_app.api.get_budget_usage",
        args: {
            project: frm.doc.custom_project_budget,
            company: frm.doc.company,
        },
        callback(r) {
            if (r.message) {
                const usage_pct = r.message.used_pct;
                const indicator_html = `
                    <div class="indicator ${usage_pct > 90 ? 'red' : usage_pct > 70 ? 'yellow' : 'green'}">
                        Budget Usage: ${usage_pct}%
                    </div>`;
                frm.dashboard.set_headline(indicator_html);
            }
        }
    });
}
```

### 18.3 Tích hợp Custom Calculations vào taxes_and_totals.js

```javascript
// Nếu cần custom calculation client-side
// Override method calculate_taxes_and_totals trong controller

erpnext.CustomTaxesController = class CustomTaxesController
    extends erpnext.taxes_and_totals {

    calculate_taxes_and_totals() {
        // Gọi parent calculation
        super.calculate_taxes_and_totals();

        // Sau đó thêm custom charges
        this.calculate_custom_environmental_levy();
        this.update_custom_totals();
    }

    calculate_custom_environmental_levy() {
        const doc = this.frm.doc;
        let levy = 0;

        doc.items.forEach(item => {
            if (item.custom_has_environmental_levy) {
                levy += item.amount * 0.005;
            }
        });

        // Set giá trị nhưng không trigger lại calculation
        frappe.model.set_value(
            doc.doctype, doc.name,
            "custom_environmental_levy",
            flt(levy, precision("custom_environmental_levy"))
        );
    }

    update_custom_totals() {
        const doc = this.frm.doc;
        // Cập nhật grand total sau custom charges
        frappe.model.set_value(
            doc.doctype, doc.name,
            "custom_grand_total_with_levy",
            flt(doc.grand_total + (doc.custom_environmental_levy || 0))
        );
    }
};
```

### 18.4 Server-side API Endpoints

```python
# custom_app/api.py

import frappe

@frappe.whitelist()
def get_budget_usage(project, company):
    """API endpoint để JS gọi"""
    if not frappe.has_permission("Project", "read", project):
        frappe.throw("Not permitted")

    budget = frappe.db.get_value("Project", project, "custom_total_budget")
    used = frappe.db.sql("""
        SELECT SUM(base_net_total) as used
        FROM `tabSales Invoice`
        WHERE custom_project_budget = %s
          AND company = %s
          AND docstatus = 1
    """, (project, company), as_dict=True)[0].used or 0

    return {
        "total_budget": budget,
        "used_amount": used,
        "used_pct": flt(used / budget * 100, 2) if budget else 0,
    }


@frappe.whitelist()
def make_commission_note(source_name, target_doc=None):
    """Tạo Commission Note từ Sales Invoice"""
    from frappe.model.mapper import get_mapped_doc

    def set_missing_values(source, target):
        target.commission_date = frappe.utils.today()
        target.custom_source_invoice = source.name

    def condition(obj):
        return obj.custom_commission_amount > 0

    return get_mapped_doc("Sales Invoice", source_name, {
        "Sales Invoice": {
            "doctype": "Commission Note",
            "field_map": {
                "name": "custom_source_invoice",
                "customer": "party",
                "custom_commission_agent": "agent",
                "custom_commission_amount": "commission_amount",
                "posting_date": "posting_date",
            },
            "condition": condition,
        },
    }, target_doc, set_missing_values)
```

### 18.5 Cấu trúc File tổng quát cho Custom Module

```
custom_app/
├── hooks.py                          # Đăng ký hooks
├── public/
│   └── js/
│       ├── custom_sales_invoice.js   # JS Controller
│       └── custom_purchase_invoice.js
├── overrides/
│   ├── sales_invoice.py              # Hook functions (validate, on_submit...)
│   ├── purchase_invoice.py
│   └── gl_entry.py
├── services/
│   ├── custom_gl_composer.py         # GL Composer mở rộng
│   ├── custom_tax_service.py         # Tax service
│   └── custom_payment_service.py
├── api.py                            # Whitelist API endpoints
└── doctype/
    └── custom_sales_invoice/         # Custom DocType nếu cần
        ├── custom_sales_invoice.py
        ├── custom_sales_invoice.js
        └── custom_sales_invoice.json
```

---

## Bảng Tổng kết: Hàm → File → Mô tả

| Hàm | File | Mô tả |
|-----|------|-------|
| `AccountsController.validate()` | accounts_controller.py | Chuỗi validate tổng quát |
| `AccountsController.get_gl_dict()` | accounts_controller.py | Tạo GL dict chuẩn |
| `AccountsController.update_against_document_in_jv()` | accounts_controller.py | Liên kết advance với invoice |
| `AccountsController.set_advances()` | accounts_controller.py | Lấy và điền advances |
| `calculate_taxes_and_totals.__init__()` | taxes_and_totals.py | Entry point tính thuế |
| `calculate_taxes_and_totals.calculate_item_values()` | taxes_and_totals.py | Tính rate, amount từng item |
| `calculate_taxes_and_totals.determine_exclusive_rate()` | taxes_and_totals.py | Tách thuế khỏi giá inclusive |
| `calculate_taxes_and_totals.calculate_taxes()` | taxes_and_totals.py | Tính tax_amount từng dòng thuế |
| `calculate_taxes_and_totals.apply_discount_amount()` | taxes_and_totals.py | Phân bổ discount |
| `make_gl_entries()` | general_ledger.py | Ghi GL Entries (entry point) |
| `process_gl_map()` | general_ledger.py | Merge, distribute, toggle negative |
| `make_reverse_gl_entries()` | general_ledger.py | Đảo ngược GL khi cancel |
| `process_debit_credit_difference()` | general_ledger.py | Kiểm tra balance, roundoff |
| `distribute_gl_based_on_cost_center_allocation()` | general_ledger.py | Split GL theo cost center allocation |
| `update_outstanding_amt()` | gl_entry.py | Cập nhật outstanding trên invoice |
| `get_balance_on()` | accounts/utils.py | Số dư tài khoản tại ngày |
| `reconcile_against_document()` | accounts/utils.py | Liên kết payment với invoice |
| `get_outstanding_invoices()` | accounts/utils.py | Danh sách invoices còn outstanding |
| `get_party_details()` | party.py | Thông tin party (address, account...) |
| `get_party_account()` | party.py | Tài khoản Receivable/Payable của party |
| `set_taxes()` | party.py | Xác định tax template từ Tax Rule |
| `SalesInvoice.validate_debit_to_acc()` | sales_invoice.py | Kiểm tra Debit To account |
| `SalesInvoice.on_submit()` | sales_invoice.py | Submit SI: GL, SLE, loyalty, TCS |
| `SalesInvoice.update_billing_status_in_dn()` | sales_invoice.py | Cập nhật per_billed trên DN |
| `SalesInvoice.get_gl_entries()` | sales_invoice.py | Ủy quyền SalesInvoiceGLComposer |
| `PurchaseInvoice.set_expense_account()` | purchase_invoice.py | Auto-fill expense account |
| `PurchaseInvoice.validate_supplier_invoice()` | purchase_invoice.py | Kiểm tra bill_no duplicate |
| `PurchaseInvoice.on_submit()` | purchase_invoice.py | Submit PI: GL, SLE, TDS, provisional |
| `PurchaseInvoice.update_billing_status_in_pr()` | purchase_invoice.py | Cập nhật per_billed trên PR |
| `PurchaseInvoice.cancel_provisional_entries()` | purchase_invoice.py | Đảo provisional entries từ PR |
| `PaymentEntry.build_gl_map()` | payment_entry.py | Ủy quyền PaymentEntryGLComposer |
| `PaymentEntry.update_payment_schedule()` | payment_entry.py | Cập nhật payment schedule trên invoice |
| `PaymentEntry.make_advance_gl_entries()` | payment_entry.py | GL cho advance book separately |
| `JournalEntry.on_submit()` | journal_entry.py | Submit JE: GL, asset update, inter-company |

---

*Tài liệu tổng hợp từ source code ERPNext/Frappe develop branch (tháng 6/2026). Mọi tham chiếu đến đường dẫn file là tương đối từ thư mục root của ERPNext.*