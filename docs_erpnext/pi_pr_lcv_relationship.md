# Chi tiết Quan hệ PI ↔ PR ↔ LCV và Hạch toán Kế toán Chuyên sâu

> Tài liệu này tập trung vào mối quan hệ 3 chiều giữa **Purchase Invoice (PI)**, **Purchase Receipt (PR)**, và **Landed Cost Voucher (LCV)** — cách chúng tương tác, ảnh hưởng lẫn nhau, và hạch toán kế toán ở từng luồng. Đây là phần chuyên sâu bổ sung cho tài liệu tổng thể `accounting_purchase_full_flow.md`.

---

## MỤC LỤC

1. [Tổng quan về Ma trận Quan hệ](#1-tổng-quan)
2. [PR → PI — Luồng Cơ bản (Stock Item)](#2-pr--pi-cơ-bản)
3. [PR → LCV → PI — Luồng Có Chi phí Thêm](#3-pr--lcv--pi)
4. [LCV → PR — Cơ chế Hủy và Tạo lại GL](#4-lcv--pr-hủy-tạo-lại-gl)
5. [PI → PR — Auto Accounting cho Stock Items](#5-pi--pr-perpetual-inventory)
6. [PI → PR — Provisional Accounting cho Non-Stock Items](#6-pi--pr-provisional)
7. [PI → PR — Exchange Rate Difference](#7-pi--pr-tỷ-giá)
8. [PI Cancel → PR — Khôi phục Provisional Entries](#8-pi-cancel--pr)
9. [Bảng tổng hợp GL Entries theo Mọi Tình huống](#9-bảng-tổng-hợp)
10. [Service Layer — Các Service Phụ Trợ](#10-service-layer)

---
## 1. Tổng quan về Ma trận Quan hệ

### 1.1. Sơ đồ quan hệ 3 chiều

```
                    ┌───────────────────┐
                    │  LANDED COST      │
                    │   VOUCHER (LCV)   │
                    └────────┬──────────┘
                             │
                    Liên kết │ qua Purchase Receipts table
                             ▼
┌─────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  PURCHASE   │────►│  PURCHASE RECEIPT │────►│ PURCHASE INVOICE │
│   ORDER     │     │       (PR)        │     │      (PI)        │
│   (PO)      │     └───────────────────┘     └──────────────────┘
└─────────────┘              │                         │
                             │                         │
              Cập nhật:      │           Cập nhật:     │
              received_qty   │           billed_qty    │
              per_received   │           per_billed    │
                             ▼                         ▼
                    ┌──────────────────────────────────────┐
                    │          GL ENGINE                   │
                    │  (general_ledger.py)                 │
                    │                                      │
                    │  PR:  WH Dr | SRBNB Cr               │
                    │  LCV: Hủy GL cũ → Tạo GL mới         │
                    │  PI:  Expense Dr | Payable Cr        │
                    └──────────────────────────────────────┘
```

### 1.2. File paths quan trọng

| Component | File Path |
|-----------|-----------|
| PR (Doctype) | `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py` |
| PR GL Composer (trong PR) | `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py` — `make_item_gl_entries()` |
| PR Provisional Accounting (trong PR) | `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py` — `add_provisional_gl_entry()` |
| PR Billing Status (trong PR) | `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py` — `update_billing_status()` |
| LCV | `erpnext/stock/doctype/landed_cost_voucher/landed_cost_voucher.py` |
| PI | `erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py` |
| GL Engine | `erpnext/accounts/general_ledger.py` |
| Stock Controller | `erpnext/controllers/stock_controller.py` |
| Accounts Controller | `erpnext/controllers/accounts_controller.py` |

### 1.3. Các biến trạng thái quyết định hành vi

| Biến | Doctype | Ảnh hưởng |
|------|---------|-----------|
| `update_stock` | PI | Có cập nhật tồn kho không? |
| `is_paid` | PI | Có thanh toán ngay không? |
| `is_return` | PR / PI | Có phải trả hàng không? |
| `auto_accounting_for_stock` | Company | Perpetual inventory được bật? |
| `via_landed_cost_voucher` | PR (param) | Được LCV gọi? (thay đổi cách tạo GL) |
| `distribute_charges_based_on` | LCV | Qty / Amount / Distribute Manually |

### 1.4. Liên kết dữ liệu giữa các chứng từ

| Liên kết | Field (Source → Target) | Bảng |
|----------|------------------------|------|
| PO → PR | `pr_item.purchase_order` → `po.name` | PO Item |
| PR → PI | `pi_item.purchase_receipt` → `pr.name` | PI Item |
| PR → PI (dòng) | `pi_item.pr_detail` → `pr_item.name` | PI Item |
| PR → LCV | `lcv_pr.receipt_document` → `pr.name` | LCV Purchase Receipts |
| PI → PR (số lượng) | `pr_item.billed_qty` = sum(`pi_item.qty`) | PR Item |
| PI → PO (số lượng) | `po_item.billed_qty` = sum(`pi_item.qty`) | PO Item |

---

## 2. PR → PI — Luồng Cơ bản (Stock Item, Perpetual Inventory)

Đây là luồng phổ biến nhất: mua hàng tồn kho với perpetual inventory được bật và PI có `update_stock=1`.

### 2.1. Khi PR Submit

PR tạo GL Entry tạm thời ghi nhận hàng đã nhập kho:

```
PR submit (Stock Item, Perpetual Inventory):

  Debit:  Warehouse Account (156)       ← stock_value_difference (valuation_rate × qty)
  Credit: Stock Received But Not Billed (3311)  ← base_net_amount

  + Nếu có thuế valuation (e.g., thuế nhập khẩu):
    Credit: Tax Account (e.g., 33312)   ← item_tax_amount
```

**Giải thích:**
- **Warehouse Account (156 — Hàng hóa):** Tăng giá trị hàng tồn kho do nhập
- **SRBNB (3311 — Hàng nhận chưa có hóa đơn):** Tài khoản đệm (clearing account) — ghi nhận công nợ tạm thời, chờ PI đến
- **Tax Account (valuation):** Thuế tính vào giá vốn (không qua Expense)

### 2.2. Khi PI Submit (liên kết với PR)

PI ghi nhận công nợ thực tế và chi phí thực tế. Với perpetual inventory + `update_stock=1`:

```
PI submit (Stock Item, update_stock=1, perpetual inventory):

  — Ghi nhận chi phí (dựa trên stock value từ SLE) —
  Debit:  Expense Account (632)         ← warehouse_debit_amount

  — Ghi nhận công nợ NCC —
  Credit: Payable Account (331)         ← base_grand_total

  — Thuế đầu vào —
  Debit:  Tax Account (1331)            ← tax_amount

  — Rounding (nếu có) —
  Debit/Credit: Round Off Account       ← base_rounding_adjustment
```

### 2.3. SRBNB — Nó đi đâu?

**Điểm mấu chốt:** PI **KHÔNG tự động xóa SRBNB**. Cơ chế như sau:

1. PI ghi `Expense Account (Dr) | Payable Account (Cr)` — ghi nhận chi phí thực
2. SRBNB vẫn còn số dư Credit từ PR (không được xóa trực tiếp)
3. Khi `update_billing_status_in_pr()` chạy → gọi `adjust_incoming_rate_for_pr()`:
   - Nếu PI rate = PR rate → không có adjustment → SRBNB tồn tại song song
   - Nếu PI rate ≠ PR rate → có adjustment entries → SRBNB được điều chỉnh

**Khi nào SRBNB thực sự được xóa?**
- Khi có bút toán điều chỉnh từ PI (nếu rate khác nhau)
- Khi PI cancel → `cancel_provisional_entries()` đánh `is_cancelled=1` → PR repost
- Qua Period Closing Voucher (kết chuyển cuối kỳ)

### 2.4. Ví dụ cụ thể

**Giả sử:** Mua 10 cái bút, giá 10,000/cái (chưa VAT), VAT 10%.

**PR submit:**
```
  WH Account (156):     Dr 100,000
  SRBNB (3311):         Cr 100,000
```

**PI submit (từ PR, giá 10,000, VAT 10%):**
```
  Expense Account (632): Dr 100,000
  Payable Account (331):  Cr 110,000
  VAT Input (1331):       Dr 10,000
```

**Net effect:**
- Giá trị kho: 100,000 (từ PR) — không đổi
- Chi phí: 100,000 (từ PI) — ghi nhận vào Expense
- Công nợ NCC: 110,000 (gốc + VAT)
- SRBNB: còn 100,000 (dư Credit — chờ xử lý cuối kỳ)

> **Lưu ý:** Trong ERPNext perpetual inventory, PI `make_item_gl_entries()` khi gặp stock item + perpetual + `update_stock=1` sẽ ghi Expense Account thay vì chạm vào Warehouse Account. SRBNB được clear gián tiếp qua cơ chế adjustment/repost chứ không phải trực tiếp trong PI.

---

## 3. PR → LCV → PI — Luồng Có Chi phí Thêm

### 3.1. Thứ tự đúng

```
  PR submit (hàng đã vào kho — giá vốn gốc)

  LCV submit (chi phí thêm — vận chuyển, bảo hiểm, thuế NK)

  PI submit (hóa đơn thực tế từ NCC)
```

**Quan trọng:** LCV **phải** submit trước PI. Nếu PI đã submit trước, bạn không thể thêm LCV sau — phải cancel PI, thêm LCV, rồi tạo lại PI.

### 3.2. LCV không tạo GL Entry riêng

LCV kế thừa từ `Document`, KHÔNG có `AccountsController` — do đó **không có `make_gl_entries()` riêng**.

Cơ chế: LCV **hủy GL cũ của PR và tạo lại GL mới** với giá vốn điều chỉnh.

### 3.3. Chi tiết từng bước — LCV submit

```python
def update_landed_cost(self):
    for d in self.get("purchase_receipts"):
        doc = frappe.get_doc(d.receipt_document_type, d.receipt_document)

        # Step 1: Gán chi phí LCV lên từng dòng PR Item
        doc.set_landed_cost_voucher_amount()
        # → item.landed_cost_voucher_amount = item.applicable_charges

        # Step 2: Tính lại valuation_rate
        # → item.valuation_rate = (base_amount + landed_cost_voucher_amount) / qty
        doc.update_valuation_rate(reset_outgoing_rate=False)

        # Step 3: Ghi DB
        for item in doc.get("items"):
            item.db_update()

        # Step 4: Cập nhật Serial No purchase_rate
        self.update_rate_in_serial_no_for_non_asset_items(doc)

    for d in self.get("purchase_receipts"):
        doc = frappe.get_doc(d.receipt_document_type, d.receipt_document)

        # Step 5a: HỦY SLE cũ
        doc.docstatus = 2
        doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)

        # Step 5b: HỦY GL entries cũ
        doc.make_gl_entries_on_cancel()

        # Step 6a: TẠO LẠI SLE mới
        doc.docstatus = 1
        doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)

        # Step 6b: TẠO LẠI GL entries mới
        doc.make_gl_entries(via_landed_cost_voucher=True)

        # Step 6c: Repost các SLE/GLE tương lai
        doc.repost_future_sle_and_gle()
```

### 3.4. GL thay đổi thế nào?

**Trước LCV — GL của PR:**
```
  WH Account (156):     Dr 100,000
  SRBNB (3311):         Cr 100,000
```

**LCV submit** — vận chuyển 5,000, thuế nhập khẩu 2,000:

```
— HỦY GL cũ —
  WH Account (156):     Cr 100,000
  SRBNB (3311):         Dr 100,000

— TẠO LẠI GL mới (via_landed_cost_voucher=True) —
  WH Account (156):     Dr 107,000    (100,000 + 5,000 + 2,000)
  SRBNB (3311):         Cr 100,000    (giá trị gốc — KHÔNG thay đổi)
  LCV - Vận chuyển:    Cr 5,000      (tài khoản charge)
  LCV - Thuế NK:       Cr 2,000      (tài khoản charge)
```

**Net effect:** Giá trị kho tăng 7,000. SRBNB giữ nguyên. Phần tăng thêm credit vào các tài khoản LCV.

### 3.5. Kế tiếp — PI submit

**PI submit (giá gốc 10,000/cái × 10, VAT 10%):**
```
  Expense (632):        Dr 100,000    (chi phí dựa trên stock value từ PR)
  Payable (331):        Cr 110,000    (công nợ)
  VAT Input (1331):     Dr 10,000     (thuế đầu vào)
```

**Net effect:**
```
  WH (156):        Dr 107,000    (kho = gốc + LCV)
  SRBNB (3311):    Cr 100,000    (chờ xử lý)
  LCV-VC (x):      Cr 5,000      (tài khoản charge vận chuyển)
  LCV-TNK (y):     Cr 2,000      (tài khoản charge thuế NK)
  Expense (632):   Dr 100,000    (chi phí hàng hóa)
  Payable (331):   Cr 110,000    (công nợ NCC)
  VAT In (1331):   Dr 10,000     (thuế đầu vào)
```

---

## 4. LCV → PR — Cơ chế Hủy và Tạo lại GL

### 4.1. Tại sao LCV phải hủy cả SLE?

LCV ảnh hưởng đến cả tồn kho và kế toán:
- `valuation_rate` thay đổi → SLE cần cập nhật giá vốn
- Stock value thay đổi → GL entries của PR cần tạo lại

### 4.2. Tác động đến SLE

Khi `update_stock_ledger()` gọi với `via_landed_cost_voucher=True`:

```python
sle = get_sl_entries(d, {
    "actual_qty": actual_qty,
    "incoming_rate": d.valuation_rate,      # RATE MỚI (đã bao gồm LCV)
    "recalculate_rate": 1 if via_landed_cost_voucher else 0,
})
```

- `incoming_rate` = valuation_rate mới (đã bao gồm LCV)
- `recalculate_rate = 1` — báo hiệu rate đã được tính lại

### 4.3. Tác động đến Queue Repost

`repost_future_sle_and_gle()`:
- Nếu item đã xuất kho sau PR → SLE xuất kho được tính lại với rate mới
- Nếu có PI submit sau PR → GL entries của PI cũng được repost

### 4.4. LCV Cancel — Đảo ngược

```python
def on_cancel(self):
    self.update_landed_cost()  # Cùng method — chỉ khác chiều xử lý
```

Khi LCV cancel:
1. `set_landed_cost_voucher_amount()` đặt lại = 0
2. `update_valuation_rate()` tính lại rate KHÔNG bao gồm LCV
3. Hủy GL của PR (từ lần tạo lại trước)
4. Tạo lại GL mới với giá vốn gốc

→ Giá trị kho quay về trạng thái trước LCV.

### 4.5. Phân bổ chi phí LCV

| Phương thức | Công thức | Dùng khi |
|-------------|-----------|----------|
| Qty | `applicable_charges = total_charges × (item_qty / total_qty)` | Chi phí theo số lượng (vận chuyển theo kg, container) |
| Amount | `applicable_charges = total_charges × (item_amount / total_amount)` | Chi phí theo giá trị (bảo hiểm, thuế theo %) |
| Distribute Manually | Người dùng tự nhập | Chi phí đặc thù |

---

## 5. PI → PR — Auto Accounting cho Stock Items

### 5.1. Logic trong make_item_gl_entries()

```python
def make_item_gl_entries(self, gl_entries):
    for d in self.get("items"):
        if d.is_fixed_asset:
            continue

        warehouse_account = get_warehouse_account(d.warehouse)
        if not warehouse_account:
            continue

        if d.from_warehouse:
            make_internal_transfer_gl_entry(gl_entries, d)
        else:
            # Stock item + perpetual + update_stock=1
            if self.auto_accounting_for_stock and self.update_stock:
                make_stock_adjustment_entry(gl_entries, d)
                make_landed_cost_entries(gl_entries, d)
                make_sub_contracting_entries(gl_entries, d)
            else:
                make_expense_gl_entry(gl_entries, d)

        # Chênh lệch tỷ giá
        make_exchange_rate_adjustment(gl_entries, d)
```

### 5.2. make_stock_adjustment_entry()

Phương thức cốt lõi — quyết định Expense Account được ghi nhận thế nào:

```python
def make_stock_adjustment_entry(gl_entries, item):
    stock_amount = get_stock_amount_from_sle(item)
    # warehouse_debit_amount = valuation_rate × qty × conv_factor

    if abs(item.warehouse_debit_amount - stock_amount) > precision:
        # Chênh lệch → COGS adjustment
        discrepancy = item.warehouse_debit_amount - stock_amount
        gl_entries.append(GL_Entry(
            account=item.expense_account,
            debit=discrepancy if discrepancy > 0 else 0,
            credit=discrepancy if discrepancy < 0 else 0,
        ))
        item.warehouse_debit_amount = stock_amount

    # Ghi nhận Expense chính
    gl_entries.append(GL_Entry(
        account=item.expense_account,
        debit=item.warehouse_debit_amount,
    ))
```

### 5.3. make_landed_cost_entries()

Khi PR đã có LCV (item có `landed_cost_voucher_entries`):

```python
def make_landed_cost_entries(gl_entries, item):
    for lcv_entry in item.get("landed_cost_voucher_entries") or []:
        gl_entries.append(GL_Entry(
            account=lcv_entry.landed_cost_account,
            credit=lcv_entry.base_amount,
        ))
```

### 5.4. Ví dụ — PI rate khác PR rate + LCV

**PR submit (rate=10,000/cái, 10 cái):**
```
  WH (156):          Dr 100,000
  SRBNB (3311):      Cr 100,000
```

**LCV submit (vận chuyển 5,000):**
```
  — Hủy GL cũ —
  WH (156):          Cr 100,000
  SRBNB (3311):      Dr 100,000

  — Tạo GL mới —
  WH (156):          Dr 105,000
  SRBNB (3311):      Cr 100,000
  LCV-VC:            Cr 5,000
```

**PI submit (rate=11,000/cái, VAT 10%):**
```
  — Expense (dựa trên stock value 105,000) —
  Expense (632):        Dr 105,000

  — Chênh lệch giá: (11,000-10,000) × 10 = 10,000 —
  Expense (632):        Dr 10,000

  — Ghi nhận công nợ: 11,000 × 10 × 1.1 = 121,000 —
  Payable (331):        Cr 121,000
  VAT Input (1331):     Dr 11,000
```

---

## 6. PI → PR — Provisional Accounting cho Non-Stock Items

### 6.1. Điều kiện kích hoạt

- Item là **Non-Stock** (không quản lý tồn kho)
- **Provisional Accounting** được bật trong Company
- Có `provisional_expense_account` được cấu hình

### 6.2. PR submit — Bút toán tạm

```
PR submit (Non-Stock, Provisional = True):

  Debit:  Expense Account             ← base_amount
  Credit: Provisional Account (338)   ← base_amount
```

**Giải thích:** Ghi nhận chi phí dự kiến dựa trên giá tạm (thường từ PO). Khi PI đến, sẽ đảo ngược và thay thế.

### 6.3. PI submit — Đảo ngược + Ghi nhận thực tế

```
PI submit (Non-Stock, có PR tham chiếu):

  Bước 1 — Đảo ngược bút toán tạm của PR:
    Debit:  Provisional Account (338)   ← base_amount (của PR)
    Credit: Expense Account             ← base_amount (của PR)

  Bước 2 — Ghi nhận chi phí thực + công nợ:
    Debit:  Expense Account             ← base_net_amount (của PI)
    Credit: Payable Account (331)       ← base_grand_total
```

### 6.4. Ví dụ

**PR submit (giá tạm 10,000):**
```
  Expense (627):        Dr 10,000
  Provisional (338):    Cr 10,000
```

**PI submit (giá thực 10,500, VAT 10%):**
```
  — Đảo ngược tạm —
  Provisional (338):    Dr 10,000
  Expense (627):        Cr 10,000

  — Ghi nhận thực —
  Expense (627):        Dr 10,500
  Payable (331):        Cr 11,550
  VAT Input (1331):     Dr 1,050
```

**Net effect:**
```
  Expense (627):     Dr 10,500    (chi phí thực tế — cuối cùng)
  Payable (331):     Cr 11,550    (công nợ NCC)
  VAT Input (1331):  Dr 1,050     (thuế)
  Provisional (338): = 0          (đã đảo ngược)
```

---

## 7. PI → PR — Exchange Rate Difference

### 7.1. Nguyên nhân

Khi `conversion_rate` của PI khác với PR (tỷ giá tại thời điểm nhập hàng ≠ tỷ giá tại thời điểm nhận hóa đơn).

### 7.2. Cách ERPNext xử lý

```python
# Trong make_item_gl_entries() của PI
if d.pr_detail:
    pr_rate = get_rate_from_pr(d.pr_detail)
    pi_rate = self.conversion_rate

    if abs(pi_rate - pr_rate) > precision:
        item_amount_base = flt(d.get("base_net_amount"))
        pr_item_amount_base = flt(d.get("stock_amount"))  # từ SLE của PR
        discrepancy = item_amount_base - pr_item_amount_base

        if abs(discrepancy) > precision:
            gl_entries.append({
                "account": d.expense_account,
                "debit": discrepancy if discrepancy > 0 else 0,
                "credit": discrepancy if discrepancy < 0 else 0,
                "against": get_exchange_gain_loss_account(),
            })
```

### 7.3. Ví dụ

**PR submit (tỷ giá 23,000, giá 10 USD × 10 cái):**
```
  WH (156):        Dr 2,300,000   (10 × 10 × 23,000)
  SRBNB (3311):    Cr 2,300,000
```

**PI submit (tỷ giá 24,000, giá 10.5 USD × 10, VAT 10%):**
```
  — Expense dựa trên stock value —
  Expense (632):       Dr 2,300,000

  — Chênh lệch giá: (10.5-10) × 10 × 24,000 = 120,000 —
  Expense (632):       Dr 120,000

  — Chênh lệch tỷ giá: (10 × 10 × 24,000) - 2,300,000 = 100,000 —
  Expense (632):       Dr 100,000
  Exchange G/L:        Cr 100,000

  — Công nợ —
  Payable (331):       Cr 2,772,000   (10.5 × 10 × 24,000 × 1.1)
  VAT Input (1331):    Dr 252,000     (10.5 × 10 × 24,000 × 0.1)
```

## 8. PI Cancel → PR — Khôi phục Provisional Entries

### 8.1. Khi PI bị Cancel — cơ chế đặc biệt

Khi PI cancel, nó thực hiện 2 việc:
1. **Đảo ngược GL entries của chính nó** — `make_reverse_gl_entries(voucher_type="Purchase Invoice", voucher_no=self.name)`
2. **Đánh dấu `is_cancelled=1` trên GL entries của PR** — `cancel_provisional_entries()`

### 8.2. cancel_provisional_entries()

```python
def cancel_provisional_entries(self):
    """Khi PI cancel: đánh dấu is_cancelled=1 trên GL entries của PR"""
    for d in self.get("items"):
        if d.pr_detail:
            frappe.db.sql("""
                UPDATE `tabGL Entry`
                SET is_cancelled = 1
                WHERE voucher_type = 'Purchase Receipt'
                  AND voucher_no = %s
                  AND voucher_detail_no = %s
                  AND is_cancelled = 0
            """, (d.purchase_receipt, d.pr_detail))
```

### 8.3. Tại sao cần?

Khi PI (stock item, perpetual) submit, nó ghi nhận Expense Account nhưng **không xóa GL entries của PR**. PR vẫn giữ WH Account Dr và SRBNB Cr — nhưng ý nghĩa kế toán của chúng đã bị "override" bởi PI.

Khi PI cancel:
1. GL entries của PI bị đảo ngược → Expense/Payable biến mất
2. Cần khôi phục lại GL entries của PR (vì bây giờ PR là chứng từ duy nhất còn hiệu lực)
3. `is_cancelled=1` đánh dấu GL entries cũ của PR là vô hiệu — chờ repost để tạo lại

### 8.4. Luồng đầy đủ — PI cancel → PR repost

```
PI cancel:
  1. make_reverse_gl_entries()        → Đảo ngược GL của PI
  2. cancel_provisional_entries()     → is_cancelled=1 on PR GL entries

Khi PR được repost (manual hoặc qua background job):
  3. make_gl_entries() on PR          → Tạo lại GL entries mới
     Debit:  WH Account
     Credit: SRBNB
     → Bút toán tạm thời xuất hiện lại
```

### 8.5. Non-Stock + Provisional — cancel khác

Với non-stock + provisional accounting, cancel đơn giản hơn:
- PI đã đảo ngược provisional entries của PR khi submit
- Khi PI cancel: đảo ngược GL của PI → provisional entries của PR **tự động** xuất hiện lại (vì chúng chưa bao giờ bị xóa)

---

## 9. Bảng tổng hợp GL Entries theo Mọi Tình huống

### 9.1. Ma trận đầy đủ PR

| Tình huống PR | Debit | Credit | Khi nào |
|--------------|-------|--------|---------|
| Stock item, perpetual | WH Account | SRBNB | Submit |
| Non-stock, provisional | Expense Account | Provisional Account | Submit |
| Internal transfer | Target WH Account | Source WH Account | Submit |
| Fixed asset | Asset Account | ARBNB | Submit |
| Valuation tax | (vào WH Account) | Tax Account | Submit |
| Divisional loss | Default Expense Account | — | Submit |
| Return (is_return) | SRBNB | WH Account | Submit (đảo ngược) |
| Qua LCV (via_landed_cost_voucher=True) | WH Account (gốc + LCV) | SRBNB (gốc) + LCV Account (LCV) | LCV submit |

### 9.2. Ma trận đầy đủ PI

| Tình huống PI | Debit | Credit | Ghi chú |
|--------------|-------|--------|---------|
| Stock item, perpetual, update_stock | Expense Account | — | Thay SRBNB |
| Stock item, không perpetual | Expense Account | — | Ghi nhận chi phí trực tiếp |
| Non-stock, provisional (đảo ngược) | Provisional Account | Expense Account | Hoàn nhập tạm |
| Non-stock, provisional (ghi thực) | Expense Account | — | Chi phí thực tế |
| Non-stock, không provisional | Expense Account | — | Chi phí trực tiếp |
| Ghi nhận công nợ | — | Payable Account | Supplier |
| Internal transfer | Target WH Account | Source WH Account | |
| Internal transfer tax | — | Unrealized P/L | |
| Stock adjustment (chênh lệch) | COGS Account | — | |
| Thuế Add | Tax Account | — | |
| Thuế Deduct | — | Tax Account | |
| Thuế Valuation | — | Tax Account | |
| LCV entries | — | LCV Account | Kế thừa từ PR |
| Subcontract cost | — | Supplier WH Account | |
| Write-off | Payable Account | Write Off Account | |
| Rounding | Round Off Account | — | |
| Chênh lệch tỷ giá (PR≠PI) | Expense Account | Exchange G/L | Có thể debit hoặc credit |
| is_paid (thanh toán ngay) | Payable Account | Cash/Bank Account | |

### 9.3. Ma trận LCV

| Tình huống LCV | Hành động |
|----------------|-----------|
| Submit | Hủy GL cũ của PR → Tạo lại GL mới với WH tăng thêm LCV phần, Credit vào LCV Account |
| Cancel | Hủy GL mới của PR → Tạo lại GL cũ (không LCV) |

### 9.4. Sơ đồ số dư tài khoản qua các bước

```
Tài khoản:       Trước    PR       LCV      PI       PE       Sau
─────────────────────────────────────────────────────────────────────
WH Account (156)     0   +100K    +107K   +107K   +107K   +107K
SRBNB (3311)         0   +100K    +100K   +100K   +100K   +100K
LCV - Vận chuyển     0      0       +5K     +5K     +5K     +5K
LCV - Thuế NK        0      0       +2K     +2K     +2K     +2K
Expense (632)        0      0        0    +100K   +100K   +100K
VAT Input (1331)     0      0        0     +10K    +10K    +10K
Payable (331)        0      0        0    +110K   +110K   +110K
Bank (112)          1M      0        0        0    -110K   +890K

→ Cột cuối: Balance sheet cân bằng? Kiểm tra:
  Asset:   156(107K) + 1331(10K) + 112(890K) = 1,007K
  Liab:    3311(100K) + LCV(7K) + 331(110K) = 217K
  Equity:  Expense(100K) làm giảm Equity
  → 1,007K - 217K - 100K = 690K = Equity ban đầu ✓
```

---

## 10. Service Layer — Các Service Phụ Trợ

### 10.1. Quan trọng: Không có Service Layer riêng

**Các file `services/gl_composer.py`, `provisional_accounting.py`, `billing_status.py`, `stock_reservation.py` không tồn tại trong code thực tế.**

Tất cả logic GL entries của Purchase Receipt nằm **trong một file duy nhất**:
- **`erpnext/stock/doctype/purchase_receipt/purchase_receipt.py`**

### 10.2. `update_billing_status()` — method của PR (dòng 737-751)

```python
def update_billing_status(self, update_modified=True):
    updated_pr = [self.name]
    for d in self.get("items"):
        if d.get("purchase_invoice") and d.get("purchase_invoice_item"):
            d.db_set("billed_amt", d.amount, update_modified=update_modified)
        elif d.purchase_order_item:
            po_details.append(d.purchase_order_item)

    if po_details:
        updated_pr += update_billed_amount_based_on_po(po_details, update_modified, self)

    for pr in set(updated_pr):
        pr_doc = self if (pr == self.name) else frappe.get_doc("Purchase Receipt", pr)
        update_billing_percentage(pr_doc, update_modified=update_modified)
```

**Hàm cấp module (cùng file):**
- `update_billed_amount_based_on_po()` — dòng 768: FIFO allocation từ PO
- `update_billing_percentage()` — dòng 888: `per_billed = billed / total * 100`
- `adjust_incoming_rate_for_pr()` — dòng 930: hủy/tạo lại GL khi giá thay đổi
- `get_billed_amount_against_pr()` — dòng 845: query billed amount từ PI items
- `get_billed_amount_against_po()` — dòng 863: query billed amount từ PO

### 10.3. `add_provisional_gl_entry()` — method của PR (dòng 608-654)

```python
def add_provisional_gl_entry(self, item, gl_entries, posting_date,
                             provisional_account, reverse=0, item_amount=None):
    multiplication_factor = 1
    amount = item.base_amount
    if reverse:
        multiplication_factor = -1
        amount = item_amount

    # Credit: Provisional Account
    self.add_gl_entry(gl_entries=gl_entries,
        account=provisional_account, credit=multiplication_factor * amount, ...)

    # Debit: Expense Account
    self.add_gl_entry(gl_entries=gl_entries,
        account=expense_account, debit=multiplication_factor * amount, ...)
```

**Được gọi từ:**
- PR `make_item_gl_entries()` (dòng 539-540) — khi PR submit
- PI `make_provisional_gl_entry()` (dòng 1062-1079) — khi PI submit để đảo ngược

### 10.4. `get_gl_entries()` — method của PR (dòng 310-319)

```python
def get_gl_entries(self, warehouse_account=None, via_landed_cost_voucher=False):
    gl_entries = []
    self.make_item_gl_entries(gl_entries, warehouse_account=warehouse_account)
    self.make_tax_gl_entries(gl_entries, via_landed_cost_voucher)
    update_regional_gl_entries(gl_entries, self)
    return process_gl_map(gl_entries)
```

**Không có PurchaseReceiptGLComposer.** Các nested functions bên trong `make_item_gl_entries()`:
- `make_item_asset_inward_gl_entry()` — Debit WH / Asset Account
- `make_stock_received_but_not_billed_entry()` — Credit SRBNB (qua debit âm)
- `make_landed_cost_gl_entries()` — Credit LCV Account
- `make_rate_difference_entry()` — Credit SRBNB (rate diff từ PI)
- `make_sub_contracting_gl_entries()` — Credit Supplier WH
- `make_divisional_loss_gl_entry()` — Debit Default Expense (chênh lệch)

**Data flow:**
```
PR.get_gl_entries()
  → make_item_gl_entries()
    → per item:
      non-stock + provisional → add_provisional_gl_entry()
      stock/perpetual → nested functions (6 functions ở trên)
    → warehouse validation
  → make_tax_gl_entries()
    → valuation tax allocation
  → update_regional_gl_entries()
  → process_gl_map() — merge, normalize, cost center allocation
```

---

## 11. Tổng kết — Flow Decision Tree

### 11.1. Khi PI submit — quyết định xử lý item

```
PI item
│
├── is_fixed_asset?
│   └── Yes → Xử lý theo Asset (không trong scope này)
│
├── Stock item?
│   ├── Yes + update_stock=1 + perpetual inventory?
│   │   ├── Có PR tham chiếu?
│   │   │   ├── Yes → Expense Account Dr (override SRBNB + ghi nhận chi phí)
│   │   │   │         + Xử lý chênh lệch (rate diff, exchange diff)
│   │   │   └── No  → Expense Account Dr (không có PR — ghi nhận trực tiếp)
│   │   ├── Có LCV amount? → Credit: LCV Account
│   │   └── Internal transfer? → Target WH Dr | Source WH Cr
│   │
│   ├── Yes + không update_stock?
│   │   └── Expense Account Dr (chỉ ghi nhận chi phí, không stock)
│   │
│   └── No (non-stock)?
│       ├── Có PR + provisional?
│       │   ├── Yes → Đảo ngược provisional → Ghi nhận thực tế
│       │   └── No  → Expense Account Dr trực tiếp
│       └── Không PR? → Expense Account Dr
│
├── Có exchange rate diff (PR conversion_rate ≠ PI conversion_rate)?
│   └── Yes → Expense Account Dr/Cr + Exchange G/L Account Cr/Dr
│
└── is_paid=1?
    └── Yes → Thêm bút toán Payable Dr | Cash/Bank Cr
```

### 11.2. Thứ tự ưu tiên liên kết

```
Khi tạo PI từ PR:
  1. Nếu PR đã có LCV → kế thừa landed_cost_voucher_amount
  2. Nếu PR có valuation tax → kế thừa tax info
  3. Nếu PR có serial/batch → kế thừa serial/batch nos
  4. Billing status → đánh dấu dòng PR là đã billed
  5. Nếu PI rate ≠ PR rate → adjustment entries
  6. Nếu PI conversion_rate ≠ PR conversion_rate → exchange gain/loss
```

---

## 12. Các Edge Cases Quan trọng

### 12.1. PR không có PO (Manual Receipt)

Khi PR tạo thủ công (không từ PO):
- Không có `pr_items.purchase_order_item` → `billing_status` tính khác
- Không có committed qty update
- GL entries giống PR có PO

### 12.2. PR có nhiều PI (Partial Billing)

```
PR: 10 cái @ 10,000 = 100,000
  ├── PI#1: 5 cái @ 10,000 = 50,000  (billed_qty=5, per_billed=50%)
  │   → Expense Dr 50,000 | Payable Cr 55,000
  ├── PI#2: 3 cái @ 10,500 = 31,500  (billed_qty=8, per_billed=80%)
  │   → Expense Dr 31,500 + chênh lệch | Payable Cr 34,650
  └── PI#3: 2 cái @ 10,000 = 20,000  (billed_qty=10, per_billed=100%)
      → Expense Dr 20,000 | Payable Cr 22,000
```

Mỗi PI chỉ tác động đến phần giá trị tương ứng với số lượng của nó trên PR.

### 12.3. LCV sau PI (hủy PI là điều kiện tiên quyết)

**Quan trọng:** ERPNext **không cho phép** LCV liên kết với PR đã có PI nộp. Nếu cần thêm LCV sau PI:
1. Cancel PI
2. Thêm LCV vào PR
3. Submit LCV (hủy/tạo lại GL PR)
4. Tạo lại PI từ PR (với giá mới bao gồm LCV)

> Trong thực tế, message lỗi: "Landed Cost Voucher không thể được tạo cho Purchase Receipt đã có hóa đơn"

### 12.4. PI Cancel → LCV vẫn còn

Khi PI cancel:
- GL entries của PI bị đảo ngược
- cancel_provisional_entries() đánh is_cancelled=1 trên GL của PR
- LCV **không bị ảnh hưởng** — valuation rate của PR vẫn giữ nguyên
- Khi PR được repost: GL mới của PR bao gồm cả LCV amount (vì PR items vẫn có landed_cost_voucher_amount)

### 12.5. LCV Cancel → Cần làm gì với PI?

LCV cancel hoạt động độc lập với PI:
- Nếu PI chưa nộp (draft): cancel LCV → PR quay về giá gốc → PI lấy giá mới
- Nếu PI đã nộp: **cần cancel PI trước**, sau đó cancel LCV, rồi tạo lại PI

---

## Phụ lục: Key Code Paths

### A.1. PR make_gl_entries flow

```
PR.make_gl_entries(via_landed_cost_voucher)
  → PR.get_gl_entries(via_landed_cost_voucher)
    → _make_item_gl_entries
      → per item:
        non-stock + provisional → add_provisional_gl_entry
        stock → Debit: WH Account, Credit: SRBNB
      → if via_landed_cost_voucher: thêm Credit: LCV Account
    → _make_tax_gl_entries
    → set_gl_entry_for_purchase_expense (divisional loss)
    → update_regional_gl_entries (regional add-ons)
    → process_gl_map (merge, normalize, cost center allocation)
  → make_gl_entries(gl_entries) — lưu vào DB
```

### A.2. PI make_gl_entries flow

```
PI.make_gl_entries()
  → get_gl_entries()
    → make_supplier_gl_entry — Credit: Payable Account
    → make_item_gl_entries — per item:
        stock + perpetual + update_stock:
          → make_stock_adjustment_entry — Expense Dr
          → make_landed_cost_entries — Credit LCV Account (nếu có)
          → make_sub_contracting_entries — Credit Supplier WH (nếu có)
          → exchange rate diff adjustment
        non-stock + provisional:
          → đảo ngược provisional entries
          → ghi nhận Expense thực tế
        non-stock (không provisional):
          → Expense Dr trực tiếp
    → make_precision_loss_gl_entry
    → make_tax_gl_entries
    → make_internal_transfer_gl_entries
    → merge_similar_entries
    → make_payment_gl_entries (nếu is_paid)
    → make_write_off_gl_entry (nếu có write-off)
    → make_gle_for_rounding_adjustment
  → make_gl_entries(gl_entries) — lưu vào DB + tạo Payment Ledger
  → make_exchange_gain_loss_journal — JE riêng cho realized gain/loss
```

### A.3. LCV update_landed_cost flow

```
LCV.update_landed_cost()
  → PR.set_landed_cost_voucher_amount() — set landed_cost_voucher_amount
  → PR.update_valuation_rate() — tính lại rate
  → PR.update_rate_in_serial_no() — cập nhật Serial No purchase_rate
  → PR docstatus=2:
    → PR.update_stock_ledger(via_landed_cost_voucher) — HỦY SLE
    → PR.make_gl_entries_on_cancel() — HỦY GL
  → PR docstatus=1:
    → PR.update_stock_ledger(via_landed_cost_voucher) — TẠO LẠI SLE
    → PR.make_gl_entries(via_landed_cost_voucher) — TẠO LẠI GL
  → PR.repost_future_sle_and_gle() — Cập nhật tương lai
```

---

_Tài liệu chuyên sâu về PI ↔ PR ↔ LCV — bổ sung cho accounting_purchase_full_flow.md_
_ERPNext v15+, tháng 6/2026_
