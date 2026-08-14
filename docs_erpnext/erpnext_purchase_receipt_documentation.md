# Tài liệu Tổng hợp ERPNext/Frappe - Purchase Receipt từ A–Z

> Tài liệu này mô tả chi tiết toàn bộ các lớp (class), hàm (function), luồng logic và tích hợp của **Purchase Receipt** — từ nghiệp vụ cụ thể đến nền tảng, bao gồm Stock Ledger, GL Entries, Repost và các Service mới.

---

## Sơ đồ Kế thừa

```
PurchaseReceipt
  └─ BuyingController
       └─ SubcontractingController
            └─ StockController
                 └─ AccountsController
                      └─ TransactionBase
                           └─ StatusUpdater
                                └─ Document
                                     └─ BaseDocument
```

---

## Sơ đồ Service Dependencies

```
PurchaseReceipt
  ├─ services/gl_composer.py          → PurchaseReceiptGLComposer
  ├─ services/provisional_accounting.py → ProvisionalAccountingService
  ├─ services/billing_status.py       → BillingStatusService
  └─ services/stock_reservation.py    → StockReservationService
```

---

## 1. PurchaseReceipt (`purchase_receipt.py`)

Lớp xử lý toàn bộ nghiệp vụ **Phiếu Nhận Hàng** trong ERPNext. Kể từ phiên bản mới, các logic phức tạp đã được tách ra thành các **Service class** riêng biệt.

---

### 1.1. Cấu hình Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo đối tượng và thiết lập `status_updater` — danh sách cấu hình dùng để đồng bộ số liệu tích lũy lên các tài liệu liên kết:

**Cấu hình cập nhật (thường):**

| Source           | Source Field      | Target                | Target Field    | Mô tả                                          |
| ---------------- | ----------------- | --------------------- | --------------- | ---------------------------------------------- |
| PR Item          | `received_qty`    | PO Item               | `received_qty`  | Đồng bộ số lượng đã nhận lên PO → `per_received` |
| PR Item          | `stock_qty`       | Material Request Item | `received_qty`  | Cập nhật phần trăm nhận cho MR                 |
| PR Item          | `received_qty`    | PI Item               | `received_qty`  | Đồng bộ nhận hàng cho PI → `per_received`      |
| PR Item          | `received_qty`    | Delivery Note Item    | `received_qty`  | Cập nhật cho DN (internal transfer)            |

**Cấu hình bổ sung khi `is_return = True`:**

| Source           | Source Field          | Target       | Target Field    | Mô tả                              |
| ---------------- | --------------------- | ------------ | --------------- | ---------------------------------- |
| PR Item (return) | `-1 * qty`            | PO Item      | `returned_qty`  | Cộng dồn số lượng đã trả lên PO    |
| PR Item (return) | `-1 * received_stock_qty` | PR Item gốc | `returned_qty` | Tính `per_returned` trên PR gốc   |

> **Điểm đặc biệt:** `second_source_extra_cond` trong cấu hình PO Item lọc thêm PI có `update_stock = 1`, đảm bảo không đếm trùng số lượng nhận từ PI khi đã có PR.

---

### 1.2. Vòng đời Tài liệu (Lifecycle Events)

#### `before_validate(self)`

Nếu `apply_putaway_rule = True` và không phải phiếu trả hàng:

- Gọi `apply_putaway_rule(doctype, items, company)` để phân bổ hàng vào đúng vị trí kho theo quy tắc Putaway.
- Kết quả là danh sách `items` với `warehouse` đã được gán tự động.

#### `validate(self)`

Điều phối toàn bộ kiểm tra hợp lệ theo thứ tự:

1. `validate_posting_time()` — Kiểm tra thời gian ghi sổ.
2. `validate_posting_date_with_po()` — Ngày PR không được sớm hơn ngày PO.
3. `super().validate()` — Chạy validate của `BuyingController` (gồm các validate tồn kho, UOM, giá trị).
4. `set_status()` — Đặt trạng thái Draft nếu chưa submit.
5. `po_required()` — Nếu Buying Settings yêu cầu PO bắt buộc, kiểm tra từng dòng.
6. `validate_items_quality_inspection()` — Validate Quality Inspection liên kết.
7. `validate_with_previous_doc()` — So sánh nhà cung cấp, công ty, tiền tệ, UOM với PO.
8. `validate_uom_is_integer()` — Kiểm tra UOM yêu cầu số nguyên.
9. `validate_cwip_accounts()` — Kiểm tra tài khoản CWIP cho tài sản cố định.
10. `ProvisionalAccountingService(self).validate_provisional_expense_account()` — Điền `provisional_expense_account` mặc định cho mặt hàng không phải tồn kho.
11. `check_for_on_hold_or_closed_status()` — PO không được ở trạng thái On Hold/Closed.
12. Kiểm tra `posting_date` không được là ngày tương lai.
13. `get_current_stock()` — Lấy tồn kho hiện tại cho các mặt hàng có `batch_no`.
14. `reset_default_field_value()` — Đồng bộ các trường warehouse mặc định xuống bảng con.

#### `on_submit(self)`

Thực thi lần lượt:

1. `super().on_submit()` — Gọi submit của `BuyingController`.
2. `validate_approving_authority()` — Kiểm tra quyền duyệt từ Authorization Control.
3. `update_prevdoc_status()` — Cập nhật `received_qty`, `per_received` trên PO và MR (gọi `StatusUpdater.update_qty()`).
4. `update_billing_status()` — Cập nhật `billed_amt`, `per_billed` (nếu chưa billing 100%). Nếu đã billing 100%, set `status = "Completed"` trực tiếp.
5. `make_bundle_for_sales_purchase_return()` — Tạo Serial/Batch Bundle cho phiếu trả hàng.
6. `make_bundle_using_old_serial_batch_fields()` — Tương thích với dữ liệu Serial/Batch cũ.
7. `update_stock_ledger()` — **Cập nhật Stock Ledger Entries** (phải chạy SAU `update_prevdoc_status`).
8. `make_gl_entries()` — Tạo GL Entries kế toán.
9. `repost_future_sle_and_gle()` — Repost SLE/GLE tương lai nếu cần.
10. `set_consumed_qty_in_subcontract_order()` — Cập nhật số lượng nguyên liệu tiêu thụ trong Subcontract Order.
11. `StockReservationService(self).reserve_stock()` — Đặt dự trữ tồn kho từ PR.
12. `update_received_qty_if_from_pp()` — Cập nhật `received_qty` trong Production Plan Sub Assembly Item.

> **Thứ tự quan trọng:** `update_stock_ledger()` phải chạy sau `update_prevdoc_status()` vì việc tính `ordered_qty` và `reserved_qty_for_subcontract` trong Bin phụ thuộc vào `ordered_qty` đã được cập nhật trong PO.

#### `on_cancel(self)`

Thực thi ngược lại `on_submit`:

1. `super().on_cancel()` — Gọi cancel của `BuyingController`.
2. `check_for_on_hold_or_closed_status()` — Kiểm tra PO không ở trạng thái đặc biệt.
3. Kiểm tra không có Purchase Invoice đã nộp liên kết với PR này.
4. `update_prevdoc_status()` — Đảo ngược cập nhật trên PO/MR.
5. `update_billing_status()` — Đặt lại trạng thái billing.
6. `update_stock_ledger()` — Tạo SLE hủy (đảo ngược).
7. `make_gl_entries_on_cancel()` — Tạo GL Entries đảo ngược.
8. `repost_future_sle_and_gle()` — Repost lại SLE/GLE tương lai.
9. `delete_auto_created_batches()` — Xóa Batch đã tự động tạo.
10. `set_consumed_qty_in_subcontract_order()` — Cập nhật lại số lượng nguyên liệu.
11. `update_received_qty_if_from_pp()` — Cập nhật lại Production Plan.

> `ignore_linked_doctypes` được đặt để cho phép hủy mà không cần xóa liên kết GL Entry, SLE, Repost Item Valuation và Serial/Batch Bundle.

#### `before_cancel(self)`

- Gọi `remove_amount_difference_with_purchase_invoice()`: Reset `amount_difference_with_purchase_invoice = 0` cho tất cả dòng trước khi hủy.

---

### 1.3. Validation Chi tiết

#### `validate_uom_is_integer(self)`

Gọi `super()` hai lần:

- Kiểm tra `qty` và `received_qty` phải là số nguyên khi UOM yêu cầu.
- Kiểm tra `stock_qty` phải là số nguyên khi Stock UOM yêu cầu.

#### `validate_cwip_accounts(self)`

Với mỗi dòng mặt hàng là tài sản cố định (`is_fixed_asset = True`) và bật CWIP accounting:

- Kiểm tra tài khoản `asset_received_but_not_billed` tồn tại trong cài đặt công ty.
- Kiểm tra tài khoản `capital_work_in_progress_account` của asset category.
- Mục đích: cải thiện UX bằng cách báo lỗi tài khoản **trước** khi tự động tạo tài sản.

#### `validate_with_previous_doc(self)`

So sánh các trường với Purchase Order:

- Cấp cha (PO): `supplier`, `company`, `currency` phải khớp.
- Cấp con (PO Item): `project`, `uom`, `item_code` phải khớp.

Nếu `maintain_same_rate = True` trong Buying Settings và không phải phiếu trả hàng hoặc internal transfer: gọi `validate_rate_with_reference_doc()` để so sánh đơn giá.

#### `validate_items_quality_inspection(self)`

Với từng dòng có `quality_inspection`:

- QI phải có `reference_type = "Purchase Receipt"` và `reference_name = self.name`.
- QI phải có `item_code` khớp với dòng mặt hàng.

#### `po_required(self)`

Nếu `po_required = "Yes"` trong Buying Settings và không phải internal transfer: từng dòng mặt hàng bắt buộc phải có `purchase_order`.

#### `get_already_received_qty(self, po, po_detail)`

Query tổng `qty` đã nhận từ các PR đã nộp khác (không phải PR hiện tại) cho một `purchase_order_item`. Dùng trong logic kiểm tra over-receipt.

---

### 1.4. GL Entries

#### `get_gl_entries(self, inventory_account_map=None, via_landed_cost_voucher=False)`

Delegate hoàn toàn cho `PurchaseReceiptGLComposer(self).compose(...)`. Đây là điểm vào duy nhất để lấy GL Entries của PR.

#### `add_provisional_gl_entry(self, item, gl_entries, posting_date, provisional_account, reverse=0, item_amount=None)`

Delegate cho `ProvisionalAccountingService(self).add_provisional_gl_entry(...)`. Được gọi từ cả PR (khi submit) và PI (khi đảo ngược bút toán tạm thời).

---

### 1.5. Cập nhật Tài sản Cố định

#### `update_assets(self, item, valuation_rate)`

Khi PR có `landed_cost_voucher_amount` cho tài sản cố định: cập nhật `net_purchase_amount` và `purchase_amount` trên Asset records liên kết.

```python
purchase_amount = valuation_rate × asset.asset_quantity
```

Lấy danh sách Asset theo `purchase_receipt`, `item_code`, và `purchase_receipt_item` (bao gồm cả `""` để tương thích dữ liệu cũ).

---

### 1.6. Trạng thái và Billing

#### `update_billing_status(self, update_modified=True)`

Delegate cho `BillingStatusService(self).update_billing_status(update_modified)`.

#### `update_status(self, status)`

Cập nhật trạng thái PR và gửi notification realtime:

```python
self.set_status(update=True, status=status)
self.notify_update()
clear_doctype_notifications(self)
```

#### `enable_recalculate_rate_in_sles(self)`

Đặt `recalculate_rate = 1` trên tất cả SLE của PR này (ngoại trừ rejected warehouses). Được gọi bởi `adjust_incoming_rate_for_pr()` trong `billing_status.py` khi PI điều chỉnh incoming rate của PR.

---

### 1.7. Hàm Hỗ trợ Module-level

#### `get_stock_value_difference(voucher_no, voucher_detail_no, warehouse)`

Query `stock_value_difference` từ SLE dựa trên voucher và warehouse. Dùng trong GL Composer để tính giá trị chênh lệch kho thực tế từ SLE (chính xác hơn tính từ `base_net_amount`).

#### `update_regional_gl_entries(gl_list, doc)` `@erpnext.allow_regional`

Hook cho các bút toán khu vực (regional). Mặc định không làm gì, có thể override cho từng quốc gia.

---

### 1.8. Hàm Whitelist Công khai

| Hàm                                       | Mô tả                                                      |
| ----------------------------------------- | ---------------------------------------------------------- |
| `update_purchase_receipt_status(docname, status)` | Cập nhật trạng thái PR (Closed, To Bill, v.v.)     |
| `make_lcv(doctype, docname)`              | Tạo Landed Cost Voucher từ PR, tự động lấy items từ PR     |

---

## 2. PurchaseReceiptGLComposer (`services/gl_composer.py`)

Service class xây dựng GL Entries cho PR. Kế thừa từ `BaseStockGLComposer` nhưng **không dùng** vòng lặp GL cơ sở — PR có logic per-item riêng biệt.

---

### 2.1. Điểm Vào Chính

#### `compose(self, inventory_account_map=None, via_landed_cost_voucher=False) → list`

Xây dựng toàn bộ GL Entries theo thứ tự:

1. `_make_item_gl_entries(gl_entries, inventory_account_map)` — Bút toán kho/tài sản cho từng mặt hàng.
2. `_make_tax_gl_entries(gl_entries, via_landed_cost_voucher)` — Bút toán thuế Valuation.
3. `doc.set_gl_entry_for_purchase_expense(gl_entries)` — Bút toán chi phí mua hàng (inherited).
4. `update_regional_gl_entries(gl_entries, doc)` — Bút toán khu vực.
5. `process_gl_map(gl_entries, from_repost=...)` — Hợp nhất và chuẩn hóa bút toán.

---

### 2.2. `_make_item_gl_entries` — Logic Per-Item

Với mỗi dòng mặt hàng `d`, logic rẽ nhánh như sau:

```
Dòng mặt hàng d
├── Không phải stock item + provisional_accounting bật + có provisional_expense_account
│   └── → add_provisional_gl_entry()         [Kế toán tạm thời cho non-stock]
├── Stock item (perpetual inventory) HOẶC Fixed asset (không có PI liên kết)
│   ├── is_fixed_asset = True
│   │   ├── stock_asset_account_name = d.expense_account
│   │   └── stock_value_diff = base_net_amount + item_tax_amount + landed_cost_voucher_amount
│   └── Là stock item thông thường
│       ├── stock_value_diff = get_stock_value_difference(...)  [từ SLE thực tế]
│       └── stock_asset_account_name = warehouse account
│
│   → make_item_asset_inward_gl_entry()       [DEBIT kho/tài sản]
│   → make_stock_received_but_not_billed_entry() [CREDIT SRBNB/ARBNB hoặc from_warehouse]
│   → make_landed_cost_gl_entries()           [CREDIT LCV accounts nếu có]
│   → make_amount_difference_entry()          [CREDIT SRBNB nếu có chênh lệch PI rate]
│   → make_sub_contracting_gl_entries()       [CREDIT supplier_warehouse nếu gia công]
│   → make_divisional_loss_gl_entry()         [DEBIT/CREDIT loss account nếu có sai lệch]
└── Warehouse không có tài khoản kế toán → cảnh báo
```

#### `make_item_asset_inward_gl_entry(item, stock_value_diff, stock_asset_account_name)`

Tạo bút toán **Debit** vào tài khoản kho hoặc tài khoản tài sản:

```
Debit:  Warehouse Account (hoặc Asset Account)   ← stock_value_diff
Credit: (ngầm định, đối ứng với SRBNB/ARBNB)
```

#### `make_stock_received_but_not_billed_entry(item) → outgoing_amount`

Tạo bút toán **Credit** vào SRBNB (Stock Received But Not Billed) hoặc ARBNB:

- **Internal transfer**: Credit vào tài khoản của `from_warehouse` (thay vì SRBNB) với `outgoing_amount` lấy từ SLE thực tế.
- **Có `rejected_qty` và `set_valuation_rate_for_rejected_materials`**: Cộng thêm giá trị kho từ chối vào `outgoing_amount`.
- **Có `purchase_invoice` liên kết và tỷ giá khác nhau**: Tạo thêm hai bút toán bù sai lệch tỷ giá vào SRBNB và `exchange_gain_loss_account`.
- **Phiếu trả hàng có `return_qty_from_rejected_warehouse` và không set valuation cho hàng từ chối**: Trả về `0.0` (không hạch toán).

```
Credit: SRBNB Account (hoặc from_warehouse account)   ← -outgoing_amount (debit âm)
```

#### `make_landed_cost_gl_entries(item)`

Nếu `landed_cost_voucher_amount > 0` và có `landed_cost_entries`:

```
Credit: LCV Account (mỗi tài khoản LCV)   ← amount từ LCV
```

Lấy `landed_cost_entries` từ `doc.get_item_account_wise_lcv_entries()`.

#### `make_amount_difference_entry(item)`

Nếu `amount_difference_with_purchase_invoice != 0` (chênh lệch giữa PI rate và PR rate):

```
Credit: SRBNB Account   ← amount_difference_with_purchase_invoice
```

Cơ chế này cho phép PR "cập nhật" giá trị kho khi PI được tạo với giá khác PR.

#### `make_sub_contracting_gl_entries(item)`

Nếu có `rm_supp_cost` (chi phí nguyên liệu gia công) và có `supplier_warehouse_account`:

```
Credit: Supplier Warehouse Account   ← rm_supp_cost
```

Giảm trừ giá trị nguyên liệu đã cung cấp cho nhà gia công khỏi tài khoản kho nhà cung cấp.

#### `make_divisional_loss_gl_entry(item, outgoing_amount)`

Tính `divisional_loss` = chênh lệch giữa giá trị lý thuyết và `stock_value_diff` thực tế từ SLE:

```python
valuation_amount_as_per_doc = (
    outgoing_amount
    + landed_cost_voucher_amount
    + rm_supp_cost
    + item_tax_amount
    + amount_difference_with_purchase_invoice
)
divisional_loss = valuation_amount_as_per_doc - stock_value_diff
```

Nếu có `divisional_loss`: Tạo bút toán Debit vào `default_expense_account` (hoặc SRBNB):

```
Debit: Default Expense Account   ← divisional_loss
```

Mục đích: Hấp thụ sai số làm tròn và các chênh lệch nhỏ giữa giá trị kế toán và SLE.

---

### 2.3. `_make_tax_gl_entries` — Bút toán Thuế Valuation

Xử lý các dòng thuế có `category` là `"Valuation"` hoặc `"Valuation and Total"`:

1. Tính tổng `negative_expense_to_be_booked` = tổng `item_tax_amount` của tất cả dòng.
2. Với từng dòng thuế có `valuation_tax`: Phân bổ `applicable_amount` theo tỷ lệ so với tổng valuation tax.
3. Dòng thuế cuối nhận phần còn lại (`amount_including_divisional_loss`) để tránh sai số làm tròn.

```
Credit: Tax Account Head   ← applicable_amount
```

Đây là bút toán **đối ứng** với `item_tax_amount` đã được tính vào `stock_value_diff` của từng dòng. Net effect: thuế valuation được hạch toán thông qua kho chứ không qua chi phí trực tiếp.

---

## 3. ProvisionalAccountingService (`services/provisional_accounting.py`)

Service xử lý kế toán tạm thời cho mặt hàng **không phải tồn kho** nhận qua PR.

---

### 3.1. `validate_provisional_expense_account(self)`

Khi công ty bật `enable_provisional_accounting_for_non_stock_items`:

- Lấy `default_provisional_account` từ cài đặt công ty.
- Điền vào `provisional_expense_account` cho mọi dòng chưa có giá trị.

---

### 3.2. `add_provisional_gl_entry(self, item, gl_entries, posting_date, provisional_account, reverse=0, item_amount=None)`

Tạo **hai bút toán** cho một dòng mặt hàng non-stock:

**Khi PR submit (`reverse = 0`):**

```
Debit:  Expense Account      ← base_amount (ghi nhận chi phí tạm thời)
Credit: Provisional Account  ← base_amount (tài khoản tạm thời chờ hóa đơn)
```

**Khi PI submit (`reverse = 1`):**

```
Debit:  Provisional Account  ← item_amount (đảo ngược tạm thời)
Credit: Expense Account      ← item_amount (xóa chi phí tạm thời)
```

Khi `reverse = 1`:
- `amount = item_amount` (có thể là partial billing — chỉ đảo phần đã lập hóa đơn).
- `expense_account` được lấy lại từ **PR Item gốc** (dùng `pr_detail` để tra cứu) thay vì từ PI Item.
- `multiplication_factor = -1` đảo chiều Debit/Credit.

> **Lưu ý:** `voucher_detail_no = item.name` được set trong cả hai chiều, cho phép `cancel_provisional_entries()` trong PI tìm đúng GL Entry của PR để đánh dấu `is_cancelled`.

---

## 4. BillingStatusService (`services/billing_status.py`)

Service theo dõi và cập nhật trạng thái lập hóa đơn (billing) giữa PR và PI.

---

### 4.1. `update_billing_status(self, update_modified=True)`

Điểm vào chính để cập nhật `billed_amt` và `per_billed`:

1. Với các dòng có `purchase_invoice` và `purchase_invoice_item`: Ghi `billed_amt = amount` trực tiếp.
2. Với các dòng có `purchase_order_item` (không có PI trực tiếp): Thu thập `po_details` và gọi `update_billed_amount_based_on_po()`.
3. Gọi `update_billing_percentage()` cho tất cả PR bị ảnh hưởng (bao gồm PR hiện tại và các PR khác liên kết cùng PO).

---

### 4.2. `update_billed_amount_based_on_po(po_details, update_modified, pr_doc) → list`

Phân bổ `billed_amt` từ PO xuống từng dòng PR theo thuật toán **FIFO** (theo `posting_date + posting_time + name`):

1. Lấy tổng billed amount từ PI → PO (`get_billed_amount_against_po`).
2. Lấy tất cả PR Items liên kết với các PO Items đó (`get_purchase_receipts_against_po_details`).
3. Lấy billed amount trực tiếp từ PI → PR (`get_billed_amount_against_pr`).
4. Với mỗi PR Item, phân bổ theo logic:
   - Nếu đã có billed trực tiếp từ PI (`billed_amt_against_pr`): ưu tiên dùng.
   - Phần còn lại từ PO: phân bổ theo tỷ lệ `qty / total_billed_qty_against_po`.
   - Cập nhật `po_billed_amt_details` để PR tiếp theo được phân bổ đúng.

---

### 4.3. `update_billing_percentage(pr_doc, update_modified, adjust_incoming_rate=False)`

Tính lại `per_billed` và xử lý over-billing:

```python
percent_billed = round(100 * (total_billed_amount / (total_amount or 1)), 6)
pr_doc.db_set("per_billed", percent_billed)
```

Logic tính `total_amount`:

- `pending_amount = item.amount - returned_qty × rate`
- Nếu `bill_for_rejected_quantity_in_purchase_invoice = True`: cộng thêm `rejected_qty × rate`.
- `total_billable_amount = pending_amount` (hoặc `billed_amt` nếu đã over-bill).

Nếu `adjust_incoming_rate = True`:

- Tính `amount_difference_with_purchase_invoice` cho từng dòng PR Item (chênh lệch giữa giá PI và giá PR).
- Gọi `adjust_incoming_rate_for_pr()` để cập nhật `valuation_rate` và repost SLE/GLE.

---

### 4.4. `adjust_incoming_rate_for_pr(doc)`

Chuỗi xử lý khi PI rate khác PR rate:

1. `doc.update_valuation_rate(reset_outgoing_rate=False)` — Tính lại valuation rate với giá PI.
2. `item.db_update()` — Ghi lại từng dòng PR Item.
3. `doc.enable_recalculate_rate_in_sles()` — Đặt `recalculate_rate = 1` trên SLE của PR.
4. `doc.repost_future_sle_and_gle(force=True)` — Repost bắt buộc để cập nhật SLE/GLE.

---

### 4.5. Helper Queries

| Hàm                                              | Mô tả                                                    |
| ------------------------------------------------ | -------------------------------------------------------- |
| `get_purchase_receipts_against_po_details`       | Lấy PR Items đã nộp liên kết với PO Items, sắp xếp FIFO |
| `get_billed_amount_against_pr`                   | Tổng amount từ PI Items trực tiếp liên kết PR Items     |
| `get_billed_amount_against_po`                   | Tổng amount từ PI Items liên kết PO Items (không qua PR) |
| `get_billed_qty_amount_against_purchase_receipt` | Tổng qty + base_net_amount từ PI Items → PR Items        |
| `get_billed_qty_amount_against_purchase_order`   | Tổng qty + base_net_amount từ PI Items → PO Items        |
| `get_item_wise_returned_qty`                     | Tổng qty đã trả theo từng PR Item name                   |

---

## 5. Stock Ledger — Cơ chế Hoạt động trong PR

### 5.1. Luồng Tạo SLE

`update_stock_ledger()` trong `BuyingController` tạo SLE cho từng dòng:

```
BuyingController.update_stock_ledger()
  → get_sl_entries(d, {...})          ← tạo SLE dict cho dòng d
  │   actual_qty = +received_qty (nhập kho)
  │   incoming_rate = d.valuation_rate
  │
  ├── Nếu d.from_warehouse:           ← chuyển kho nội bộ
  │   SLE âm tại from_warehouse (actual_qty = -received_qty)
  │
  ├── Nếu d.rejected_qty:             ← hàng từ chối
  │   SLE tại rejected_warehouse (actual_qty = +rejected_qty)
  │
  ├── Nếu is_return:                  ← phiếu trả hàng
  │   actual_qty = -returned_qty
  │   outgoing_rate = get_rate_for_return() hoặc Moving Average
  │
  └── Nếu subcontracting:
      make_sl_entries_for_supplier_warehouse()
      SLE âm tại supplier_warehouse cho từng nguyên liệu tiêu thụ

→ make_sl_entries(sl_entries)
    → stock_ledger.make_sl_entries()
```

### 5.2. `update_entries_after` — Tính toán Giá trị Tồn kho

Sau khi SLE được insert, `repost_current_voucher()` gọi `update_entries_after` để tính:

**Moving Average:**
```
new_rate = (old_qty × old_rate + in_qty × in_rate) / (old_qty + in_qty)
new_stock_value = new_qty × new_rate
```

**FIFO/LIFO (Queue-based):**
```
stock_queue = [[qty1, rate1], [qty2, rate2], ...]
FIFO: xuất từ đầu queue
LIFO: xuất từ cuối queue
stock_value_difference = new_stock_value - prev_stock_value
```

**Serialized:**
```
incoming: stock_value_change = qty × incoming_rate
outgoing: lấy purchase_rate từ Serial No records
```

---

### 5.3. `recalculate_rate` Flag

Khi SLE có `recalculate_rate = 1` (được set bởi `enable_recalculate_rate_in_sles()`):

- Trong `get_incoming_outgoing_rate_from_transaction()`, hệ thống tính lại `incoming_rate` từ transaction gốc thay vì dùng giá trị đã lưu.
- Điều này đảm bảo khi PI điều chỉnh giá, SLE của PR được recalculate chính xác.

---

### 5.4. `update_qty_in_future_sle` — Lan truyền Thay đổi

Sau mỗi SLE được xử lý, `update_qty_in_future_sle()` cập nhật `qty_after_transaction` của tất cả SLE tương lai:

```sql
UPDATE `tabStock Ledger Entry`
SET qty_after_transaction = qty_after_transaction + {actual_qty}
WHERE item_code = %s
  AND warehouse = %s
  AND voucher_no != %s
  AND is_cancelled = 0
  AND posting_datetime > %s
```

Giới hạn đến `next_stock_reco` nếu có Stock Reconciliation tiếp theo (để không vượt qua điểm reset tồn kho).

---

## 6. Repost — Cơ chế Cập nhật Lịch sử

### 6.1. `repost_future_sle_and_gle(self, force=False)`

Trong `StockController`:

```python
def repost_future_sle_and_gle(self, force=False):
    if not force and not future_sle_exists(self.args):
        return

    if item_based_reposting:
        # Tạo Repost Item Valuation cho từng cặp item-warehouse
        create_item_wise_repost_entries(
            items_to_repost=items_to_repost,
            company=self.company,
            based_on_payment_terms=...,
        )
    else:
        # Tạo một Repost Item Valuation tổng
        create_repost_item_valuation_entry(args)
```

### 6.2. Repost Item Valuation Document

Background worker xử lý Repost Item Valuation theo thứ tự:

1. Lấy tất cả SLE từ `posting_date` của PR trở đi cho các cặp `item_code + warehouse` liên quan.
2. Với mỗi SLE: Gọi lại `update_entries_after()` để tính toán lại giá trị tồn kho.
3. Sau khi repost SLE: Repost GL Entries tương ứng.
4. Đánh dấu Repost Item Valuation là `Completed`.

### 6.3. Khi nào Repost được kích hoạt?

| Sự kiện                             | Lý do Repost                                        |
| ----------------------------------- | --------------------------------------------------- |
| PR submit với SLE tương lai tồn tại | SLE mới ảnh hưởng đến valuation rate của SLE sau    |
| PR cancel                           | Đảo ngược ảnh hưởng của SLE cũ lên SLE sau         |
| PI điều chỉnh giá PR (adjust rate)  | `recalculate_rate = 1` + `force=True` repost       |
| Landed Cost Voucher                 | LCV thay đổi `valuation_rate` của các dòng PR      |

### 6.4. `future_sle_exists(args, sl_entries=None)`

Kiểm tra SLE tương lai bằng cách tra cứu `frappe.local.future_sle` (cache in-request). Nếu chưa cache: query database cho các cặp item-warehouse từ chứng từ hiện tại.

---

## 7. Mối quan hệ PR ↔ PI — Luồng Kế toán

### 7.1. Trường hợp Thông thường (Stock Item)

**Khi PR submit:**
```
Debit:  Warehouse Account    ← stock_value_diff (từ SLE)
Credit: SRBNB Account        ← base_net_amount
Credit: Valuation Tax Account ← item_tax_amount (nếu có)
```

**Khi PI submit (liên kết PR):**
```
Debit:  SRBNB Account        ← offset credit từ PR
Credit: Supplier Account     ← công nợ nhà cung cấp
```

**Net effect qua cả hai chứng từ:**
```
Debit:  Warehouse Account    ← hàng nhập kho
Credit: Supplier Account     ← nợ nhà cung cấp
```

### 7.2. Trường hợp Provisional Accounting (Non-Stock Item)

**Khi PR submit:**
```
Debit:  Expense Account      ← ghi nhận chi phí tạm thời
Credit: Provisional Account  ← treo tài khoản tạm thời
```

**Khi PI submit — đảo ngược bút toán tạm:**
```
Debit:  Provisional Account  ← đảo ngược
Credit: Expense Account      ← đảo ngược
Debit:  Expense Account      ← chi phí thực tế
Credit: Supplier Account     ← công nợ nhà cung cấp
```

**Khi PI cancel — `cancel_provisional_entries()` trong PI:**
```python
UPDATE `tabGL Entry`
SET is_cancelled = 1
WHERE voucher_type = 'Purchase Receipt'
  AND voucher_no IN (purchase_receipts)
  AND voucher_detail_no IN (pi_item_names)
```
> GL Entry của **PR** bị đánh `is_cancelled` trực tiếp để khôi phục bút toán tạm.

### 7.3. Trường hợp PI điều chỉnh Giá (adjust_incoming_rate)

Khi PI có giá khác PR và `adjust_incoming_rate` được bật:

1. `update_billing_percentage(adjust_incoming_rate=True)` tính `amount_difference_with_purchase_invoice`.
2. `adjust_incoming_rate_for_pr()` cập nhật `valuation_rate` của PR và repost SLE.
3. Khi PR GL được repost: `make_amount_difference_entry()` tạo bút toán điều chỉnh SRBNB.

```
Credit: SRBNB Account   ← amount_difference_with_purchase_invoice
```

---

## 8. Trạng thái Purchase Receipt

### 8.1. `status` Field

Các giá trị trạng thái hợp lệ:

| Trạng thái       | Điều kiện                                      |
| ---------------- | ---------------------------------------------- |
| `Draft`          | `docstatus = 0`                                |
| `To Bill`        | Nộp, chưa lập hóa đơn (`per_billed < 100`)    |
| `Partly Billed`  | Nộp, đã lập một phần hóa đơn                  |
| `Completed`      | Nộp, đã lập đủ hóa đơn (`per_billed = 100`)   |
| `Return`         | Là phiếu trả hàng (`is_return = True`)         |
| `Return Issued`  | Đã có phiếu trả hàng được phát hành           |
| `Closed`         | Đóng thủ công qua `update_purchase_receipt_status` |
| `Cancelled`      | `docstatus = 2`                                |

### 8.2. Điều kiện Cập nhật Trạng thái trong `on_submit`

```python
if flt(self.per_billed) < 100:
    self.update_billing_status()   # Tính per_billed và set status
else:
    self.db_set("status", "Completed")  # Bypass update_billing_status
```

---

## 9. Stock Reservation (`services/stock_reservation.py`)

`StockReservationService(self).reserve_stock()` — được gọi sau khi SLE và GL được tạo xong.

Chức năng: Tạo Stock Reservation Entries cho các dòng PR có liên kết đặt hàng cần dự trữ tồn kho.

---

## 10. Tích hợp Production Plan

#### `update_received_qty_if_from_pp(self)`

Sau khi submit/cancel PR, cập nhật `received_qty` trong **Production Plan Sub Assembly Item**:

1. Tìm PO Items có `production_plan_sub_assembly_item`.
2. Tính tổng `received_qty / (qty / fg_item_qty)` theo từng sub assembly item.
3. Ghi lại vào `Production Plan Sub Assembly Item.received_qty`.

Cho phép Production Plan theo dõi tiến độ nhận hàng cho các sub assembly.

---

## 11. Tóm tắt Luồng Xử lý Khi Nộp Purchase Receipt

```
PurchaseReceipt.submit()
  ↓ Document._submit() → docstatus = 1 → save()
  ↓ run_before_save_methods()
      → before_validate()         [PurchaseReceipt]
          → apply_putaway_rule()  ← phân bổ warehouse tự động
      → validate()                [PurchaseReceipt]
          → validate_posting_time, validate_posting_date_with_po
          → super().validate()    [BuyingController]
              → validate_items, validate_accepted_rejected_qty
              → update_valuation_rate()   ← tính valuation_rate
          → po_required, validate_items_quality_inspection
          → validate_with_previous_doc   ← so sánh với PO
          → ProvisionalAccountingService.validate_provisional_expense_account()
      → before_submit()           [inherited stubs]
  ↓ _validate()                   [BaseDocument]
      → _validate_mandatory, _validate_links, _validate_selects
  ↓ db_update()                   [BaseDocument]
  ↓ update_children()             [Document]
  ↓ run_post_save_methods()
      → on_update()               [inherited]
      → on_submit()               [PurchaseReceipt]
          ↓
          1. validate_approving_authority()
          ↓
          2. update_prevdoc_status()          [StatusUpdater]
              → update_qty()
                  → Cộng received_qty vào PO Item
                  → Tính per_received trên PO
                  → Kiểm tra over-receipt allowance
          ↓
          3. update_billing_status()          [BillingStatusService]
              → update_billed_amount_based_on_po()
                  → Query PI Items liên kết
                  → Phân bổ billed_amt theo FIFO
              → update_billing_percentage()
                  → Tính per_billed
                  → set_status(update=True)
          ↓
          4. make_bundle_for_sales_purchase_return()
             make_bundle_using_old_serial_batch_fields()
          ↓
          5. update_stock_ledger()            [BuyingController]
              → Với mỗi dòng mặt hàng:
                  get_sl_entries()            [StockController]
                      → Tạo SLE dict
                      → update_inventory_dimensions()
              → make_sl_entries()
                  → stock_ledger.make_sl_entries()
                      → validate_cancellation()
                      → make_entry()          ← INSERT SLE vào DB
                      → repost_current_voucher()
                          → update_entries_after()
                              → initialize_previous_data()
                              → process_sle()
                                  → [Moving Average / FIFO / LIFO / Serialized]
                                  → db_update() SLE
                                  → update_outgoing_rate_on_transaction()
                          → update_qty_in_future_sle()
                      → update_bin_qty()      ← cập nhật Bin
          ↓
          6. make_gl_entries()               [StockController → PurchaseReceipt]
              → PurchaseReceiptGLComposer.compose()
                  → _make_item_gl_entries()
                      → Với stock item:
                          make_item_asset_inward_gl_entry()  Debit Warehouse
                          make_stock_received_but_not_billed_entry()  Credit SRBNB
                          make_landed_cost_gl_entries()
                          make_amount_difference_entry()
                          make_sub_contracting_gl_entries()
                          make_divisional_loss_gl_entry()
                      → Với non-stock + provisional accounting:
                          add_provisional_gl_entry()
                              Debit Expense Account
                              Credit Provisional Account
                  → _make_tax_gl_entries()   Credit Tax Accounts (Valuation)
                  → set_gl_entry_for_purchase_expense()
                  → update_regional_gl_entries()
                  → process_gl_map()         ← merge + chuẩn hóa
              → general_ledger.make_gl_entries()  ← INSERT GL Entry vào DB
          ↓
          7. repost_future_sle_and_gle()     [StockController]
              → future_sle_exists()          ← kiểm tra có SLE tương lai không
              → create_item_wise_repost_entries()
                  → INSERT Repost Item Valuation
                  → Background worker xử lý sau
          ↓
          8. set_consumed_qty_in_subcontract_order()  [SubcontractingController]
          ↓
          9. StockReservationService.reserve_stock()
          ↓
          10. update_received_qty_if_from_pp()
```

---

## 12. Tóm tắt Luồng Khi Hủy Purchase Receipt

```
PurchaseReceipt.cancel()
  ↓ before_cancel()
      → remove_amount_difference_with_purchase_invoice()  ← reset về 0
  ↓ _cancel() → docstatus = 2
  ↓ on_cancel()
      → check_for_on_hold_or_closed_status()
      → Kiểm tra PI đã nộp? → ném lỗi nếu có
      → update_prevdoc_status()  ← đảo ngược received_qty trên PO
      → update_billing_status()  ← cập nhật lại per_billed
      → update_stock_ledger()    ← tạo SLE hủy (actual_qty đảo ngược)
      → make_gl_entries_on_cancel()
          → make_reverse_gl_entries()  ← tất cả GL Entry của PR
      → repost_future_sle_and_gle()   ← repost lại SLE/GLE sau PR
      → delete_auto_created_batches()
      → set_consumed_qty_in_subcontract_order()
      → update_received_qty_if_from_pp()
```

---

## 13. Bảng Mapping Tài khoản Kế toán

| Tình huống                    | Debit                      | Credit                       |
| ----------------------------- | -------------------------- | ---------------------------- |
| Nhập kho hàng tồn kho         | Warehouse Account          | SRBNB Account                |
| Nhập kho có LCV               | Warehouse Account          | SRBNB + LCV Accounts         |
| Nhập kho gia công             | Warehouse Account          | SRBNB + Supplier WH Account  |
| Nhận tài sản cố định          | Asset Account              | ARBNB Account                |
| Non-stock + provisional       | Expense Account            | Provisional Account          |
| Thuế Valuation                | (đã vào Warehouse Account) | Tax Account Head             |
| Sai lệch làm tròn             | Default Expense Account    | (offset)                     |
| Chênh lệch tỷ giá (PI link)   | SRBNB + Exchange Gain/Loss | (offset)                     |
| Điều chỉnh giá PI             | (offset)                   | SRBNB Account                |

---

_Tài liệu được tổng hợp từ mã nguồn ERPNext/Frappe phiên bản develop (tháng 6/2026). Để biết thêm chi tiết, tham khảo trực tiếp:_
- `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py`
- `erpnext/stock/doctype/purchase_receipt/services/gl_composer.py`
- `erpnext/stock/doctype/purchase_receipt/services/provisional_accounting.py`
- `erpnext/stock/doctype/purchase_receipt/services/billing_status.py`
- `erpnext/stock/doctype/purchase_receipt/services/stock_reservation.py`
- `erpnext/controllers/buying_controller.py`
- `erpnext/stock/stock_ledger.py`
