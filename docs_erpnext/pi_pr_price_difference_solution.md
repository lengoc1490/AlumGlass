# Giải pháp: Hạch toán Chênh lệch Giá PI ↔ PR mà không hủy GL cũ

> **Phiên bản:** 1.0  
> **Ngày:** 2026-06-16  
> **Mục đích:** Tài liệu kỹ thuật giải pháp custom xử lý chênh lệch giá giữa Purchase Invoice và Purchase Receipt.

---

## MỤC LỤC

1. [Vấn đề & Nguyên nhân](#1-vấn-đề--nguyên-nhân)
2. [Phân tích Cơ chế Core ERPNext](#2-phân-tích-cơ-chế-core-erpnext)
3. [Nguyên tắc Giải pháp](#3-nguyên-tắc-giải-pháp)
4. [So sánh Luồng Cũ vs Mới](#4-so-sánh-luồng-cũ-vs-mới)
5. [Chi tiết Thay đổi Code](#5-chi-tiết-thay-đổi-code)
6. [Hạch toán Kế toán theo Từng Tình huống](#6-hạch-toán-kế-toán-theo-từng-tình-huống)
7. [Cấu hình Cần thiết](#7-cấu-hình-cần-thiết)
8. [Kế hoạch Kiểm thử](#8-kế-hoạch-kiểm-thử)
9. [Rủi ro & Giảm thiểu](#9-rủi-ro--giảm-thiểu)
10. [Phụ lục: Code đầy đủ](#10-phụ-lục-code-đầy-đủ)

---

## 1. Vấn đề & Nguyên nhân

### 1.1. Vấn đề

Khi Purchase Invoice (PI) có đơn giá khác Purchase Receipt (PR), ERPNext core **hủy toàn bộ GL Entries và Stock Ledger Entries của PR cũ**, sau đó tạo lại với giá mới.

**Các vấn đề phát sinh:**

| Vấn đề | Mô tả | Mức độ |
|--------|-------|--------|
| Mất dấu vết kiểm toán | GL Entries gốc của PR bị xóa — không thể truy xuất giá nhập kho ban đầu | Cao |
| Rủi ro dữ liệu | Queue repost có thể fail, gây lệch số dư tài khoản | Cao |
| Xung đột custom module | Module đã tham chiếu đến GL/SLE cũ bị ảnh hưởng | Trung |
| Thiếu minh bạch | Không thể thấy "giá gốc" và "phần điều chỉnh" riêng biệt | Trung |

### 1.2. Nguyên nhân gốc

Core ERPNext xem "giá mua hàng" và "giá nhập kho" là một — khi giá hóa đơn thay đổi, nó phải cập nhật cả giá trị kho. Trigger là setting:

```python
# Buying Settings → set_landed_cost_based_on_purchase_invoice_rate = 1
```

Khi PI submit, `update_billing_status_in_pr()` đọc setting này, dẫn đến `adjust_incoming_rate_for_pr()` — hàm hủy/tạo lại GL.

### 1.3. Kịch bản thực tế

```
PR: Nhận hàng — ghi nhận giá tạm (theo PO hoặc giá ước tính)
  ↓
PI: Hóa đơn về sau — giá khác do:
  - Chiết khấu chưa biết tại thời điểm nhập
  - Biến động tỷ giá
  - Phí vận chuyển phát sinh
  - Điều chỉnh giá sau đối soát
```

---

## 2. Phân tích Cơ chế Core ERPNext

### 2.1. Chuỗi gọi hàm

```
PurchaseInvoice.on_submit()
  └── update_billing_status_in_pr()             [PI:1484]
        └── set billed_amt trên PR Item
        └── update_billing_percentage(           [PR:888]
              adjust_incoming_rate = True
            )
              ├── rate_difference_with_purchase_invoice = billed_amt - amount
              └── adjust_incoming_rate_for_pr()  [PR:930]
                    ├── update_valuation_rate()  [buying_controller:241]
                    ├── docstatus=2 → hủy SLE+GL
                    ├── docstatus=1 → tạo lại SLE+GL
                    └── repost_future_sle_and_gle()
  └── make_gl_entries()                          [PI:624]
        └── get_gl_entries()
              ├── make_supplier_gl_entry()
              ├── make_item_gl_entries()
              │     └── make_stock_adjustment_entry()
              │           → warehouse_debit_amount (đã bao gồm rate diff)
              ├── make_tax_gl_entries()
              └── make_payment_gl_entries()
```

### 2.2. Core — adjust_incoming_rate_for_pr()

**File:** `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py:930`

```python
def adjust_incoming_rate_for_pr(doc):
    doc.update_valuation_rate(reset_outgoing_rate=False)
    for item in doc.get("items"):
        item.db_update()

    # HỦY
    doc.docstatus = 2
    doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
    doc.make_gl_entries_on_cancel()

    # TẠO LẠI
    doc.docstatus = 1
    doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
    doc.make_gl_entries()
    doc.repost_future_sle_and_gle()
```

### 2.3. Ví dụ tác động

**PR GL (giá 10,000 × 10 cái):**
```
WH Account (156):     Dr 100,000
SRBNB (3311):         Cr 100,000
```

**PI submit (giá 10,500) → core hủy và tạo lại:**
```
Bước 1 - HỦY GL cũ:
  WH:  Cr 100,000
  SRBNB: Dr 100,000

Bước 2 - TẠO GL mới (giá 10,500):
  WH:     Dr 105,000
  SRBNB:  Cr 100,000
  LCV:    Cr 5,000

→ KHÔNG CÒN trace giá gốc 10,000
```

---

## 3. Nguyên tắc Giải pháp

### 3.1. Triết lý kế toán

| Nguyên tắc | Áp dụng |
|------------|---------|
| **Giá gốc** (Historical Cost) | Giữ nguyên GL gốc của PR — giá nhập kho là giá tại thời điểm nhập |
| **Rõ ràng** (Transparency) | Chênh lệch giá ghi vào tài khoản Price Difference riêng |
| **Không hủy, chỉ thêm** | Không hủy GL/SLE cũ — chỉ thêm GL entry mới cho phần chênh lệch |
| **Phiếu nào việc nấy** | PR: giá nhập kho tạm, PI: giá hóa đơn thực tế |

### 3.2. Cơ chế mới

```
GIỮ NGUYÊN PR GL:
  WH Account:     Dr 100,000        ← giữ nguyên

PI GL bổ sung (chênh lệch 5,000):
  Expense:        Dr 100,000        ← dựa trên stock value (giá PR)
  Price Diff:     Dr 5,000          ← CHÊNH LỆCH (tài khoản riêng)
  Payable:        Cr 115,500
  VAT:            Dr 10,500

→ Tổng chi phí = 100,000 + 5,000 = 105,000 = giá PI
→ Trace: PR 10,000 + diff 500 = PI 10,500
```

### 3.3. Lưu ý về giá trị kho

Giá trị kho (WH Account) **giữ nguyên theo giá PR**:
- COGS khi xuất kho dùng valuation rate của PR
- Chênh lệch hạch toán riêng → cuối kỳ tổng hợp và điều chỉnh
- Nếu yêu cầu valuation rate chính xác theo PI (ảnh hưởng giá thành), cần giải pháp bổ sung riêng

---

## 4. So sánh Luồng Cũ vs Mới

### 4.1. Luồng Core

```
PR: giá 10,000 → WH Dr 100,000 | SRBNB Cr 100,000

PI: giá 10,500
  ├── adjust_incoming_rate_for_pr → HỦY GL cũ, TẠO GL mới
  │     WH: Dr 105,000 | SRBNB: Cr 100,000 | LCV: Cr 5,000
  └── PI GL:
        Expense: Dr 105,000 | Payable: Cr 115,500 | VAT: Dr 10,500

Kết quả:
  WH=105,000 | Expense=105,000 | SRBNB=100,000
  → Không thể biết giá gốc PR
```

### 4.2. Luồng Mới

```
PR: giá 10,000 → WH Dr 100,000 | SRBNB Cr 100,000 (GIỮ NGUYÊN)

PI: giá 10,500
  ├── [BỎ QUA] adjust_incoming_rate_for_pr → KHÔNG hủy GL
  └── PI GL:
        Expense:  Dr 100,000   (stock value)
        Price Diff: Dr 5,000   (CHÊNH LỆCH)
        Payable:  Cr 115,500
        VAT:      Dr 10,500

Kết quả:
  WH=100,000 | Expense=100,000 | Price Diff=5,000
  → Tổng chi phí = 105,000
  → Trace: PR=10,000 + diff=500 = PI=10,500
```

### 4.3. Bảng so sánh

| Tài khoản | Core | Mới | Giải thích |
|-----------|------|-----|------------|
| WH Account | 105,000 | 100,000 | Mới giữ giá gốc PR |
| Expense | 105,000 | 100,000 | Mới ghi theo stock value |
| Price Diff | — | 5,000 | Mới — riêng cho chênh lệch |
| Payable | 115,500 | 115,500 | Giống |
| SRBNB | 100,000 | 100,000 | Giống |

---

## 5. Chi tiết Thay đổi Code

### 5.1. Danh sách file

| # | File | Thay đổi | Dòng |
|---|------|----------|------|
| 1 | `eupapp/.../overrides/purchase_receipt.py` | Comment `adjust_incoming_rate_for_pr()` | ~1094-1096 |
| 2 | `eupapp/.../overrides/purchase_invoice.py` | Thêm logic price diff trong `make_item_gl_entries()` | 394-441 |

### 5.2. File 1 — Override PR

**File:** `eupapp/eupapp/eupapp/doctype/overrides/purchase_receipt.py`

```diff
         if update_modified:
             pr_doc.set_status(update=True)
             pr_doc.notify_update()

-        if adjust_incoming_rate:
-            adjust_incoming_rate_for_pr(pr_doc)
+        # EUP CUSTOM: Không hủy GL/SLE cũ. PI xử lý chênh lệch qua Price Difference Account.
+        #if adjust_incoming_rate:
+        #    adjust_incoming_rate_for_pr(pr_doc)
```

**Giải thích:**
- Core vẫn set `rate_difference_with_purchase_invoice` ở vòng lặp trên
- Chỉ vô hiệu hóa bước hủy/tạo lại GL
- Cần bật `set_landed_cost_based_on_purchase_invoice_rate=1` để core set `rate_difference`

### 5.3. File 2 — Override PI

**File:** `eupapp/eupapp/eupapp/doctype/overrides/purchase_invoice.py`

Thêm vào sau khi ghi Expense Account (dòng 392), trước khối LCV:

```python
                    # === EUP CUSTOM: Ghi nhận chênh lệch giá PI vs PR ===
                    if (
                        item.get("purchase_receipt")
                        and item.get("pr_detail")
                        and self.update_stock
                        and self.auto_accounting_for_stock
                        and item.item_code in stock_items
                    ):
                        pr_item_rate_diff = frappe.db.get_value(
                            "Purchase Receipt Item",
                            item.pr_detail,
                            "rate_difference_with_purchase_invoice"
                        )
                        if pr_item_rate_diff and abs(flt(pr_item_rate_diff)) > 0.001:
                            price_diff_account = frappe.db.get_value(
                                "Company", self.company,
                                "purchase_price_difference_account"
                            )
                            if not price_diff_account:
                                price_diff_account = item.expense_account
                            if flt(pr_item_rate_diff) > 0:
                                # PI > PR: chi phí tăng thêm
                                gl_entries.append(self.get_gl_dict({
                                    "account": price_diff_account,
                                    "against": self.supplier,
                                    "debit": flt(pr_item_rate_diff),
                                    "remarks": _("Price diff PI vs PR: {0}").format(item.pr_detail),
                                    "cost_center": item.cost_center,
                                    "project": item.project or self.project,
                                }, account_currency, item=item))
                            else:
                                # PI < PR: giảm chi phí
                                gl_entries.append(self.get_gl_dict({
                                    "account": price_diff_account,
                                    "against": self.supplier,
                                    "credit": abs(flt(pr_item_rate_diff)),
                                    "remarks": _("Price diff PI vs PR: {0}").format(item.pr_detail),
                                    "cost_center": item.cost_center,
                                    "project": item.project or self.project,
                                }, account_currency, item=item))
                    # === EUP CUSTOM END ===
```

### 5.4. Cấu hình Custom Field

Tạo Custom Field trên Company:

| Field | Giá trị |
|-------|---------|
| Doctype | Company |
| Fieldname | `purchase_price_difference_account` |
| Label | Purchase Price Difference Account |
| Fieldtype | Link |
| Options | Account |
| Insert After | `default_expense_account` |

Script tạo:

```python
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

create_custom_fields({
    "Company": [
        dict(
            fieldname="purchase_price_difference_account",
            label="Purchase Price Difference Account",
            fieldtype="Link",
            options="Account",
            insert_after="default_expense_account",
            description="TK ghi nhận chênh lệch giá PI vs PR"
        )
    ]
})
```

---

## 6. Hạch toán Kế toán theo Từng Tình huống

### 6.1. PI > PR (chênh lệch dương)

**Dữ liệu:** PR=10,000, PI=10,500, VAT=10%, 10 cái

```
PR GL (giữ nguyên):
  WH (156):      Dr 100,000
  SRBNB (3311):  Cr 100,000

PI GL:
  Expense (632):      Dr 100,000      ← stock value
  Price Diff (3388):   Dr 5,000       ← PI > PR
  Payable (331):      Cr 115,500      ← 10,500×10×1.1
  VAT Input (1331):   Dr 10,500
```

### 6.2. PI < PR (chênh lệch âm)

**Dữ liệu:** PR=10,000, PI=9,500, VAT=10%, 10 cái

```
PR GL (giữ nguyên):
  WH (156):      Dr 100,000
  SRBNB (3311):  Cr 100,000

PI GL:
  Expense (632):      Dr 100,000      ← stock value
  Payable (331):      Cr 104,500      ← 9,500×10×1.1
  VAT Input (1331):   Dr 9,500
  Price Diff (3388):  Cr 5,000        ← PI < PR (credit — giảm chi phí)
```

### 6.3. Có LCV trước PI

**Dữ liệu:** PR=10,000, LCV=2,000, PI=10,500, 10 cái

```
PR + LCV GL:
  WH (156):      Dr 102,000          ← 100,000 + 2,000
  SRBNB (3311):  Cr 100,000
  LCV account:   Cr 2,000

PI GL:
  Expense (632):      Dr 100,000      ← stock value gốc
  Payable (331):      Cr 115,500
  VAT Input (1331):   Dr 10,500

  # Chênh lệch:
  # LCV expense đã có 2,000
  # PI price diff = (10,500 - 10,000) × 10 = 5,000
  # Tổng chi phí thực: 100,000 + 5,000 = 105,000
  Price Diff (3388):   Dr 5,000
```

### 6.4. Có chênh lệch tỷ giá

**Dữ liệu:** PR=10 USD @ 23,000, PI=10 USD @ 24,000

```
PR GL:
  WH (156):      Dr 230,000
  SRBNB (3311):  Cr 230,000

PI GL:
  Expense (632):      Dr 230,000
  Expense (632):      Dr 10,000         ← tỷ giá chênh (core đã xử lý)
  Exchange G/L:       Cr 10,000
  Payable (331):      Cr 264,000        ← 10×24,000×1.1
  VAT Input (1331):   Dr 24,000
```

Phần tỷ giá core đã xử lý trong khối `discrepancy_caused_by_exchange_rate_difference`.

### 6.5. Non-Stock + Provisional

Không thay đổi — core vẫn xử lý bình thường.

---

## 7. Cấu hình Cần thiết

### 7.1. Bước 1: Tạo tài khoản kế toán

Vào **Chart of Accounts** → tạo tài khoản mới:

| Field | Giá trị |
|-------|---------|
| Account Name | `3388 - Chênh lệch giá mua hàng` |
| Type | `Expense Account` (hoặc `Other Expense`) |
| Parent Account | Chi phí mua hàng / Chi phí khác |

### 7.2. Bước 2: Tạo Custom Field

Tạo `purchase_price_difference_account` trên Company — chạy script hoặc thêm manual.

### 7.3. Bước 3: Cấu hình Company

Vào Company → chọn tài khoản vừa tạo ở trường mới.

### 7.4. Bước 4: Bật Buying Setting

```
Buying Settings → set_landed_cost_based_on_purchase_invoice_rate = 1
```

Setting này để core set `rate_difference_with_purchase_invoice` trên PR Item, dù `adjust_incoming_rate_for_pr` đã bị vô hiệu hóa.

### 7.5. Kiểm tra override class

Trong `hooks.py`, đảm bảo:

```python
override_doctype_class = {
    "Purchase Receipt": "eupapp.eupapp.doctype.overrides.purchase_receipt.EupPurchaseReceipt",
    "Purchase Invoice": "eupapp.eupapp.doctype.overrides.purchase_invoice.EupPurchaseInvoice",
}
```

---

## 8. Kế hoạch Kiểm thử

### 8.1. Test Case 1: PI = PR

| Bước | Hành động | Kỳ vọng |
|------|-----------|---------|
| 1 | Tạo PO, PR giá 10,000 | SL thành công |
| 2 | Submit PR | GL: WH Dr 100,000 / SRBNB Cr 100,000 |
| 3 | Tạo PI từ PR, giá 10,000 | rate_difference = 0 |
| 4 | Submit PI | GL: Expense Dr 100,000 / Payable Cr... |
| 5 | Kiểm tra GL | KHÔNG có Price Diff entry |
| 6 | Kiểm tra PR GL | KHÔNG bị thay đổi |

### 8.2. Test Case 2: PI > PR

| Bước | Hành động | Kỳ vọng |
|------|-----------|---------|
| 1 | PR giá 10,000, 10 cái | WH Dr 100,000 / SRBNB Cr 100,000 |
| 2 | PI giá 10,500, VAT 10% | rate_difference = 5,000 |
| 3 | Submit PI | Expense Dr 100,000, Price Diff Dr 5,000, Payable Cr 115,500 |
| 4 | Kiểm tra PR GL | GIỮ NGUYÊN — WH 100,000 |
| 5 | Kiểm tra PR SLE | GIỮ NGUYÊN — valuation rate 10,000 |

### 8.3. Test Case 3: PI < PR

| Bước | Hành động | Kỳ vọng |
|------|-----------|---------|
| 1 | PR giá 10,000 | WH Dr 100,000 |
| 2 | PI giá 9,500 | rate_difference = -5,000 |
| 3 | Submit PI | Expense Dr 100,000, Price Diff Cr 5,000 |
| 4 | Kiểm tra | Payable = 104,500, VAT = 9,500 |

### 8.4. Test Case 4: Có LCV + PI chênh lệch

| Bước | Hành động | Kỳ vọng |
|------|-----------|---------|
| 1 | PR giá 10,000 | WH Dr 100,000 |
| 2 | LCV vận chuyển 2,000 | WH điều chỉnh lên 102,000 |
| 3 | PI giá 10,500 | Price Diff Dr 5,000 (chênh lệch PI vs PR gốc) |

### 8.5. Test Case 5: Hủy PI

| Bước | Hành động | Kỳ vọng |
|------|-----------|---------|
| 1 | Cancel PI | GL entries của PI bị đảo ngược |
| 2 | Kiểm tra PR GL | KHÔNG bị ảnh hưởng |
| 3 | Kiểm tra PR SLE | KHÔNG bị ảnh hưởng |

---

## 9. Rủi ro & Giảm thiểu

### 9.1. Rủi ro

| Rủi ro | Mức | Mô tả | Giảm thiểu |
|--------|-----|-------|------------|
| Valuation rate không được cập nhật | Cao | `update_valuation_rate()` không chạy → COGS có thể không đúng | Chấp nhận — giá trị kho dùng giá PR, chênh lệch ghi riêng |
| Queue repost không chạy | Trung | SLE tương lai không được tính lại | Chấp nhận — không thay đổi SLE nên không cần repost |
| SRBNB không được xóa | Thấp | Nếu PI không chạm vào SRBNB | PI vẫn ghi nhận Expense Account như core bình thường |
| Lỗi syntax | Thấp | Code Python sai | Đã validate compile |
| Quên cấu hình tài khoản | Trung | Price Difference Account không có | Fallback vào expense account + log_error |

### 9.2. Giới hạn

1. **Valuation rate không được cập nhật trên PR** — nếu hàng đã xuất kho, COGS tính theo giá PR cũ
2. **Chênh lệch tồn ở tài khoản Price Difference** — cần kết chuyển/xử lý cuối kỳ
3. **Chỉ áp dụng cho stock item + perpetual inventory** — non-stock và fixed asset không bị ảnh hưởng

---

## 10. Phụ lục: Code đầy đủ

### 10.1. PR Override — phần liên quan

**File:** `eupapp/eupapp/eupapp/doctype/overrides/purchase_receipt.py`

```python
# Dòng ~1063-1096
def update_billing_percentage(pr_doc, update_modified=True, adjust_incoming_rate=False):
    total_amount, total_billed_amount = 0, 0
    item_wise_returned_qty = get_item_wise_returned_qty(pr_doc)

    for item in pr_doc.items:
        returned_qty = flt(item_wise_returned_qty.get(item.name))
        returned_amount = flt(returned_qty) * flt(item.rate)
        pending_amount = flt(item.amount) - returned_amount
        total_billable_amount = pending_amount if item.billed_amt <= pending_amount else item.billed_amt

        total_amount += total_billable_amount
        total_billed_amount += flt(item.billed_amt)

        if pr_doc.get("is_return") and not total_amount and total_billed_amount:
            total_amount = total_billed_amount

        if adjust_incoming_rate:
            adjusted_amt = 0.0
            if item.billed_amt:
                adjusted_amt = flt(item.billed_amt) - flt(item.amount)
            item.db_set("rate_difference_with_purchase_invoice", adjusted_amt, update_modified=False)

    percent_billed = round(100 * (total_billed_amount / (total_amount or 1)), 6)
    pr_doc.db_set("per_billed", percent_billed)

    if update_modified:
        pr_doc.set_status(update=True)
        pr_doc.notify_update()

    # EUP CUSTOM: Không hủy GL/SLE cũ. PI xử lý chênh lệch qua Price Difference Account.
    #if adjust_incoming_rate:
    #    adjust_incoming_rate_for_pr(pr_doc)
```

### 10.2. PI Override — phần chênh lệch

**File:** `eupapp/eupapp/eupapp/doctype/overrides/purchase_invoice.py`

```python
# Trong make_item_gl_entries(), sau khối ghi Expense Account, dòng 394-441
# === EUP CUSTOM: Ghi nhận chênh lệch giá PI vs PR ===
if (
    item.get("purchase_receipt")
    and item.get("pr_detail")
    and self.update_stock
    and self.auto_accounting_for_stock
    and item.item_code in stock_items
):
    pr_item_rate_diff = frappe.db.get_value(
        "Purchase Receipt Item",
        item.pr_detail,
        "rate_difference_with_purchase_invoice"
    )
    if pr_item_rate_diff and abs(flt(pr_item_rate_diff)) > 0.001:
        price_diff_account = frappe.db.get_value(
            "Company", self.company,
            "purchase_price_difference_account"
        )
        if not price_diff_account:
            price_diff_account = item.expense_account
            frappe.log_error(
                _("Purchase Price Difference Account not configured for {0}. Using Expense.").format(self.company),
                "Price Diff"
            )
        if flt(pr_item_rate_diff) > 0:
            # PI > PR: chi phí tăng thêm
            gl_entries.append(self.get_gl_dict({
                "account": price_diff_account,
                "against": self.supplier,
                "debit": flt(pr_item_rate_diff),
                "remarks": _("Price diff PI vs PR: {0}").format(item.pr_detail),
                "cost_center": item.cost_center,
                "project": item.project or self.project,
            }, account_currency, item=item))
        else:
            # PI < PR: giảm chi phí
            gl_entries.append(self.get_gl_dict({
                "account": price_diff_account,
                "against": self.supplier,
                "credit": abs(flt(pr_item_rate_diff)),
                "remarks": _("Price diff PI vs PR: {0}").format(item.pr_detail),
                "cost_center": item.cost_center,
                "project": item.project or self.project,
            }, account_currency, item=item))
# === EUP CUSTOM END ===
```

### 10.3. File tham khảo

- `accounting_purchase_full_flow.md` — Tài liệu tổng thể luồng mua hàng
- `pi_pr_lcv_relationship.md` — Tài liệu quan hệ PI ↔ PR ↔ LCV

---

*Tài liệu giải pháp — EuP Dev Team, tháng 6/2026*
*ERPNext v15+*
