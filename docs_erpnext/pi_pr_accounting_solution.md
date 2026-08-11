# Giải pháp Hạch toán Chênh lệch PI ↔ PR và Xóa SRBNB

> **Phiên bản:** 1.0  
> **Ngày:** 2026-06-16  
> **Mục đích:** Tài liệu giải pháp chuẩn, không phụ thuộc override PI/PR core, xử lý toàn diện mọi nguyên nhân chênh lệch giữa Purchase Invoice và Purchase Receipt.  
> **Nguyên tắc:** Minimal core intervention, modular, maintainable.

---

## MỤC LỤC

1. [Bản chất Vấn đề Kế toán](#1-bản-chất-vấn-đề-kế-toán)
2. [Phân tích Luồng Core ERPNext](#2-phân-tích)
3. [Giải pháp Đề xuất](#3-giải-pháp)
4. [Thiết kế Kiến trúc](#4-kiến-trúc)
5. [Chi tiết Triển khai](#5-triển-khai)
6. [Hạch toán theo Từng Tình huống](#6-hạch-toán)
7. [So sánh Các Phương án](#7-so-sánh)
8. [Kế hoạch Triển khai](#8-triển-khai)
9. [Phụ lục](#9-phụ-lục)

---

## 1. Bản chất Vấn đề Kế toán

### 1.1. Hai nghiệp vụ độc lập

Mua hàng trong ERPNext gồm 2 nghiệp vụ kế toán riêng biệt:

| Nghiệp vụ | Chứng từ | Thời điểm | Ý nghĩa |
|-----------|---------|-----------|---------|
| **Nhập kho** | Purchase Receipt | Nhận hàng | Hàng hóa vào kho + Giá trị tồn kho tạm |
| **Mua hàng** | Purchase Invoice | Có hóa đơn | Chi phí thực tế + Công nợ nhà cung cấp |

Core ERPNext xử lý 2 nghiệp vụ này riêng biệt:
- PR: `WH Account Dr | SRBNB Cr` — hàng vào kho, nợ tạm
- PI: `Expense Account Dr | Payable Cr` — chi phí, công nợ thực

### 1.2. Vấn đề kế toán

Vì PR và PI độc lập, tồn tại 3 khác biệt có thể phát sinh:

| Loại chênh lệch | Nguyên nhân | Xử lý core hiện tại |
|-----------------|------------|-------------------|
| **Số lượng** | Nhận thiếu, trả lại | `billed_qty` tracking — không phải vấn đề |
| **Đơn giá (Rate)** | Giá PO khác giá hóa đơn | Core ghi Expense đúng amount PI → không vấn đề |
| **Tỷ giá (Exchange Rate)** | PR và PI khác tỷ giá | Core đã xử lý `discrepancy_caused_by_exchange_rate_difference` |
| **SRBNB tồn đọng** | PR chưa có PI hoặc chưa được clear | SRBNB không tự xóa |

### 1.3. Phát hiện quan trọng

> **Core ERPNext ĐÃ xử lý đúng phần chênh lệch amount và exchange rate trong GL entries của PI.**

Cụ thể:
- `PI.make_item_gl_entries()` khi `update_stock=0` (bắt buộc khi có PR tham chiếu) → ghi `Expense Dr base_net_amount` của PI → **đúng amount**
- `discrepancy_caused_by_exchange_rate_difference` → ghi thêm `Expense Dr/Cr + Exchange G/L Cr/Dr` → **đúng tỷ giá**
- `cancel_provisional_entries()` khi PI hủy → đánh `is_cancelled=1` trên GL entries của PR

**Vấn đề thực sự là SRBNB chưa được xử lý triệt để.**

### 1.4. Trạng thái SRBNB qua các tình huống

| Tình huống | PR GL | PI GL | SRBNB |
|-----------|-------|-------|-------|
| PR có PI, perpetual, có setting | WH Dr / SRBNB Cr | Expense Dr / Payable Cr | ✅ Đã xóa qua `adjust_incoming_rate_for_pr` |
| PR có PI, không perpetual / không setting | WH Dr / SRBNB Cr | Expense Dr / Payable Cr | ❌ Còn tồn |
| PR chưa có PI | WH Dr / SRBNB Cr | — | ❌ Còn tồn (đúng — chờ PI) |
| PR trả hàng (return) | SRBNB Dr / WH Cr | — | ⚠️ Tùy tình huống |

---

## 2. Phân tích Luồng Core ERPNext

### 2.1. Các trường hợp GL của PI

**Trường hợp 1: PI có PR tham chiếu + Stock item + Perpetual inventory**

```
PI.update_stock = 0 (bắt buộc — nếu có PR, validation throw)
PI.auto_accounting_for_stock = True (perpetual enabled)

make_item_gl_entries():
  → (update_stock=0) → FALSE → vào nhánh else (dòng 915)
  → Expense Account: Dr base_net_amount (từ PI item)
  → KHÔNG chạm WH Account, KHÔNG chạm SRBNB
```

**GL entries PI tạo:**
```text
Expense Account (632):   Dr base_net_amount (PI)
  [+ exchange rate diff entries nếu có — dòng 942-978]
Payable Account (331):   Cr base_grand_total
Tax Account (1331):      Dr tax_amount
```

**Trường hợp 2: PI có PR + Non-stock + Provisional**

```
make_item_gl_entries():
  → (stock_items) → FALSE → vào nhánh else (dòng 915)
  → make_provisional_gl_entry() — ĐẢO NGƯỢC provisional entries của PR
  → Expense Account: Dr amount (PI)
```

**GL entries PI tạo:**
```text
Provisional Account (338): Dr amount (PR) — đảo ngược
Expense Account:           Cr amount (PR) — đảo ngược
Expense Account:           Dr amount (PI) — ghi nhận thực
Payable Account:           Cr base_grand_total
```

**Trường hợp 3: PI không có PR (mua hàng trực tiếp)**

```
PI.update_stock có thể = 1
  → make_stock_adjustment_entry()
  → warehouse_debit_amount = valuation_rate × qty × conv_factor
  → Expense Dr warehouse_debit_amount
  → (Nếu có SLE và warehouse_debit_amount ≠ stock_amount)
    → COGS adjustment entry cho chênh lệch
```

### 2.2. Core xử lý chênh lệch tỷ giá

```python
# Purchase Invoice make_item_gl_entries, dòng 942-978
if item.get("purchase_receipt"):
    if (exchange_rate_map[item.purchase_receipt]
        and self.conversion_rate != exchange_rate_map[item.purchase_receipt]
        and item.net_rate == net_rate_map[item.pr_detail]):
        
        discrepancy = (item.qty * item.net_rate) * (pr_rate - pi_rate)
        
        # Expense: ghi nhận chênh lệch tỷ giá
        gl_entries.append(Expense Dr discrepancy)
        # Exchange G/L: đối ứng
        gl_entries.append(ExchangeGainLoss Cr discrepancy)
```

**Lưu ý:** Điều kiện `item.net_rate == net_rate_map[item.pr_detail]` nghĩa là tỷ giá chỉ được xử lý khi **net_rate không thay đổi** (chỉ có tỷ giá thay đổi). Nếu cả rate và tỷ giá đều thay đổi, khối này không chạy — chênh lệch được hấp thụ vào Expense Account tự nhiên.

---

## 3. Giải pháp Đề xuất

### 3.1. Yêu cầu

- ✅ Không sửa core PI, PR
- ✅ Xử lý được mọi nguyên nhân chênh lệch (rate, exchange rate, amount)
- ✅ Quản lý SRBNB triệt để
- ✅ Có thể bật/tắt độc lập
- ✅ Audit trail đầy đủ

### 3.2. Giải pháp tổng thể

Tạo một **doctype mới** `NxPurchaseInvoiceAdjustment` và một **process tự động** (background job) xử lý sau khi PI submit.

```
Giải pháp: Process riêng, chạy sau PI submit
─────────────────────────────────────────────

Bước 1: PI submit bình thường (core xử lý GL entries)
  → Core đã ghi Expense/Payable đúng amount

Bước 2: Process chạy (doc_events hoặc scheduler)
  → Đọc PR tham chiếu của PI
  → Tính toán chênh lệch between (PI amount) vs (PR amount * conversion)
  → Nếu SRBNB còn dư → tạo Journal Entry xóa SRBNB, đưa vào Expense
  → Nếu có chênh lệch chưa được hạch toán → tạo JE bổ sung
```

### 3.3. Các tình huống xử lý

| Tình huống | Hành động | Kết quả GL |
|-----------|-----------|-----------|
| **A. PR chưa có PI** | Không làm gì | SRBNB còn — chờ PI |
| **B. PI có PR, SRBNB còn dư CR** | Tạo JE xóa SRBNB | SRBNB Dr / Expense Cr (đưa về 0) |
| **C. PI có PR, chênh lệch rate + tỷ giá** | Core đã xử lý trong Expense | Expense Account đã đúng amount |
| **D. PI có PR, chênh lệch chưa hạch toán** | Tạo JE bổ sung | Price Diff Dr/Cr |
| **E. PR đã có LCV + PI** | Tính LCV vào giá trị | WH đã bao gồm LCV |

### 3.4. Nguyên lý kế toán

```text
Mục tiêu cuối cùng — GL entries phản ánh đúng 2 nghiệp vụ:

1. NHẬP KHO (PR):
   WH Account:     Dr giá trị hàng nhập
   SRBNB:          Cr giá trị hàng nhập (tạm thời — sẽ xóa khi có PI)

2. MUA HÀNG (PI):
   Expense:        Dr base_net_amount (giá hóa đơn)
   Payable:        Cr base_grand_total

3. XÓA SRBNB (khi đã có PI):
   SRBNB:          Dr giá trị PR (đưa về 0)
   Expense:        Cr giá trị PR (bù trừ — vì expense đã ghi nhận qua PI)

4. Nếu có chênh lệch giữa giá PR và PI (do rate, tỷ giá):
   → Đã được core ghi nhận tự nhiên qua Expense Account của PI
   → Không cần xử lý thêm
```

---

## 4. Thiết kế Kiến trúc

### 4.1. Doctype: NxPIAdjustmentLog

| Field | Type | Mục đích |
|-------|------|----------|
| `purchase_invoice` | Link → PI | PI được xử lý |
| `purchase_receipt` | Link → PR | PR tham chiếu |
| `pr_total_amount` | Currency | Tổng amount PR (base) |
| `pi_total_amount` | Currency | Tổng amount PI (base) |
| `srbnb_balance` | Currency | Số dư SRBNB còn |
| `exchange_rate_diff` | Currency | Chênh lệch tỷ giá |
| `rate_diff` | Currency | Chênh lệch đơn giá |
| `journal_entry` | Link → JE | JE đã tạo (nếu có) |
| `status` | Select | Pending / Processed / Skipped |
| `remarks` | Text | Ghi chú xử lý |

### 4.2. Process: Xóa SRBNB

Đây là process chính — tạo Journal Entry để xóa SRBNB khi đã có PI.

**Input:** PI đã submit, có PR tham chiếu, SRBNB > 0
**Output:** Journal Entry xóa SRBNB

```text
Journal Entry (voucher_type = "Journal Entry")
  Row 1: SRBNB Account (3311)   Dr = balance SRBNB
  Row 2: Expense Account (632)   Cr = balance SRBNB

Giải thích:
  - SRBNB Dr: giảm nợ tạm (đưa về 0)
  - Expense Cr: giảm chi phí vì PI đã ghi nhận Expense rồi
  → Nếu không làm, chi phí bị ghi nhận 2 lần: 1 lần qua SRBNB (từ PR), 1 lần qua Expense (từ PI)
```

**Khi nào tạo JE:**
- PI đã submit
- PR của item đó có GL entry với tài khoản SRBNB và `is_cancelled = 0`
- Chưa có JE xóa SRBNB nào được tạo (check trong NxPIAdjustmentLog)

### 4.3. Process: Ghi nhận chênh lệch còn lại (tùy chọn)

Nếu sau khi xóa SRBNB vẫn còn chênh lệch giữa PR và PI chưa được hạch toán:

```text
Công thức kiểm tra:
  discrepancy = (tổng base_net_amount PI) - (tổng base_net_amount PR)
  
Nếu discrepancy ≠ 0 và chưa được core xử lý:
  → Tạo JE bổ sung:
    discrepancy > 0: Expense Dr / Payable Cr (chi phí tăng thêm)
    discrepancy < 0: Payable Dr / Expense Cr (chi phí giảm)
```

---

## 5. Chi tiết Triển khai

### 5.1. Hook: doc_events Purchase Invoice

**File:** `eupapp/hooks.py`

```python
doc_events = {
    "Purchase Invoice": {
        "on_submit": "eupapp.eupapp.accounting.adjust_pi_pr.process_pi_submit"
    }
}
```

### 5.2. Module: accounting/adjust_pi_pr.py

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="Bash">
<｜｜DSML｜｜parameter name="command" string="true">mkdir -p /home/nxc/myfrappe/apps/eupapp/eupapp/eupapp/accounting
cat > /home/nxc/myfrappe/apps/eupapp/eupapp/eupapp/accounting/__init__.py << 'EOF'
# Accounting module for EuP custom
EOF
echo "Created module directory"
