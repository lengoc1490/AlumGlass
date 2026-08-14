# Tài liệu Tổng hợp ERPNext/Frappe — Stock, Account, Buying, Selling

> Tài liệu chi tiết toàn bộ logic xử lý JS + Python cho các module quan trọng: `purchase_receipt`, `delivery_note`, `stock_entry`, `stock_reconciliation`, `sales_invoice`, `purchase_order`, `sales_order`.

---

## Sơ đồ Kế thừa Tổng quan

```
Module Stock:
  PurchaseReceipt  → BuyingController  → SubcontractingController → StockController → AccountsController → TransactionBase → StatusUpdater → Document → BaseDocument
  DeliveryNote     → SellingController → StockController          → AccountsController → TransactionBase → StatusUpdater → Document → BaseDocument
  StockEntry       → StockController  → AccountsController        → TransactionBase → StatusUpdater → Document → BaseDocument
  StockReconciliation → StockController → AccountsController      → TransactionBase → StatusUpdater → Document → BaseDocument

Module Buying:
  PurchaseOrder    → BuyingController  → SubcontractingController → StockController → AccountsController → TransactionBase → StatusUpdater → Document → BaseDocument

Module Selling:
  SalesOrder       → SellingController → AccountsController       → TransactionBase → StatusUpdater → Document → BaseDocument

Module Accounts:
  SalesInvoice     → SellingController → StockController          → AccountsController → TransactionBase → StatusUpdater → Document → BaseDocument
```

---

# MODULE STOCK

---

## 1. PurchaseReceipt (`purchase_receipt.py` + `purchase_receipt.js`)

Lớp xử lý toàn bộ nghiệp vụ **Phiếu Nhập kho từ Nhà cung cấp** (Goods Receipt Note).

### 1.1. Cấu hình Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo `status_updater` với 4 cấu hình đồng bộ số lượng:

1. **PO Item → `received_qty`**: Cộng `received_qty` từ PR Item vào PO Item (`purchase_order_item`). Tính `per_received` trên PO. `second_source`: PI có `update_stock = 1` cũng được tính.
2. **Material Request Item → `received_qty`**: Cập nhật `per_received` trên Material Request.
3. **PI Item → `received_qty`**: Cập nhật PR lên PI (khi có `purchase_invoice_item`).
4. **Delivery Note Item → `received_qty`**: Dùng cho internal transfer (DN → PR nội bộ).

Khi `is_return = True`, bổ sung thêm:
- Cập nhật `returned_qty` trên PO Item (trừ `qty`).
- Cập nhật `returned_qty` + `per_returned` trên PR gốc.

---

### 1.2. Vòng đời Tài liệu

#### `before_validate(self)`

Nếu `apply_putaway_rule = True` và không phải return: Gọi `apply_putaway_rule()` để tự động phân bổ hàng vào các warehouse theo quy tắc Putaway (dựa trên capacity và ưu tiên).

#### `validate(self)`

Điều phối tuần tự:
- `validate_posting_time()` — Kiểm tra thời gian ghi sổ.
- `validate_posting_date_with_po()` — Ngày PR không được trước ngày PO.
- `super().validate()` — Gọi `BuyingController.validate()` (validate_items, update_valuation_rate, v.v.).
- `set_status()` — Tính trạng thái hiện tại.
- `po_required()` — Nếu Buying Settings yêu cầu PO bắt buộc: mỗi dòng phải có `purchase_order`.
- `validate_items_quality_inspection()` — Kiểm tra Quality Inspection phải trỏ đúng vào PR này và đúng `item_code`.
- `validate_with_previous_doc()` — So sánh nhà cung cấp, công ty, tiền tệ với PO; so sánh project, UOM, item_code với PO Item.
- `validate_uom_is_integer()` — UOM + stock UOM số lượng phải là số nguyên (nếu applicable).
- `validate_cwip_accounts()` — Với mặt hàng tài sản cố định bật CWIP: kiểm tra tài khoản `asset_received_but_not_billed` và `capital_work_in_progress_account` phải tồn tại.
- `validate_provisional_expense_account()` — Nếu công ty bật `enable_provisional_accounting_for_non_stock_items`: điền `provisional_expense_account` từ default nếu chưa có.
- `check_for_on_hold_or_closed_status()` — PO không được ở trạng thái On Hold hoặc Closed.
- Không cho phép ngày ghi sổ là ngày tương lai.
- `get_current_stock()` — Lấy số tồn kho hiện tại.
- `reset_default_field_value()` cho `set_warehouse`, `rejected_warehouse`, `set_from_warehouse`.

#### `validate_with_previous_doc(self)`

So sánh với PO:
- PO: `supplier`, `company`, `currency` phải khớp.
- PO Item: `project`, `uom`, `item_code` phải khớp.
- Nếu `maintain_same_rate = True` và không phải return, không phải internal: kiểm tra đơn giá khớp PO.

#### `on_submit(self)`

Thực thi tuần tự:
1. `super().on_submit()` — Gọi `BuyingController.on_submit()`.
2. Kiểm tra quyền duyệt (`Authorization Control`).
3. `update_prevdoc_status()` — Cập nhật `received_qty`, `per_received` trên PO Item.
4. Cập nhật billing status:
   - Nếu `per_billed < 100`: gọi `update_billing_status()`.
   - Nếu `per_billed = 100`: đặt status = "Completed".
5. `make_bundle_for_sales_purchase_return()` — Tạo Serial and Batch Bundle cho return.
6. `make_bundle_using_old_serial_batch_fields()` — Chuyển đổi serial/batch cũ sang bundle mới.
7. `update_stock_ledger()` — Tạo Stock Ledger Entries.
8. `make_gl_entries()` — Tạo GL Entries kế toán.
9. `repost_future_sle_and_gle()` — Repost SLE/GLE tương lai nếu cần.
10. `set_consumed_qty_in_subcontract_order()` — Cập nhật `consumed_qty` trong Subcontracting Order.
11. `reserve_stock()` — Đặt trước tồn kho cho Sales Order và Production Plan liên kết.
12. `update_received_qty_if_from_pp()` — Cập nhật `received_qty` cho Production Plan Sub Assembly Item.

#### `on_cancel(self)`

Thực thi ngược lại:
1. `super().on_cancel()`.
2. Kiểm tra PO không bị On Hold/Closed.
3. Kiểm tra không có PI đã nộp liên kết → ném lỗi nếu có.
4. `update_prevdoc_status()` — Khôi phục qty trên PO.
5. `update_billing_status()`.
6. `update_stock_ledger()` — Đảo ngược SLE.
7. `make_gl_entries_on_cancel()` — Đảo ngược GL Entries.
8. `repost_future_sle_and_gle()`.
9. Bỏ qua các liên kết khi cancel (GL Entry, SLE, Repost Item Valuation, Serial and Batch Bundle).
10. `delete_auto_created_batches()` — Xóa Batch tự động tạo.
11. `set_consumed_qty_in_subcontract_order()`.

#### `before_cancel(self)`

Gọi `remove_amount_difference_with_purchase_invoice()` — Reset `amount_difference_with_purchase_invoice = 0` trên tất cả items.

---

### 1.3. GL Entries Kế toán

#### `get_gl_entries(self, inventory_account_map, via_landed_cost_voucher=False)`

Ủy quyền cho `PurchaseReceiptGLComposer(self).compose(...)` — đây là class riêng trong `services/gl_composer.py`.

**Các bút toán điển hình khi submit PR:**

Với mặt hàng **tồn kho** (Perpetual Inventory enabled):
```
Debit:  Stock/Warehouse Account         (giá trị nhập kho)
Credit: Stock Received But Not Billed   (SRBNB — tài khoản tạm)
```

Với mặt hàng **non-stock** và `enable_provisional_accounting_for_non_stock_items`:
```
Debit:  Expense Account / SRBNB
Credit: Provisional Account             (tài khoản tạm thời)
```

Với **tài sản cố định** (CWIP enabled):
```
Debit:  Capital Work In Progress Account (CWIP)
Credit: Asset Received But Not Billed   (ARBNB)
```

#### `add_provisional_gl_entry(self, item, gl_entries, posting_date, provisional_account, reverse=0, item_amount=None)`

Tạo bút toán provisional cho mặt hàng non-stock:
- Khi `reverse=0` (PR submit): Credit `provisional_account`, Debit `expense_account`.
- Khi `reverse=1` (PI submit gọi ngược lại): Đảo chiều, Credit `expense_account`, Debit `provisional_account`. Lấy `expense_account` từ PR Item gốc (theo `pr_detail`).

---

### 1.4. Cập nhật Billing Status

#### `update_billing_status(self, update_modified=True)`

Cập nhật `billed_amt` trên từng PR Item:

1. Nếu có `purchase_invoice` và `purchase_invoice_item` trực tiếp: `db_set("billed_amt", d.amount)`.
2. Nếu có `purchase_order_item`: gọi `update_billed_amount_based_on_po(po_details, ...)`.
3. Sau đó gọi `update_billing_percentage(pr_doc)` để tính lại `per_billed`.

#### `update_billed_amount_based_on_po(po_details, update_modified, pr_doc)` (module-level)

Phân bổ số tiền đã lập hóa đơn (từ PI) vào từng PR Item theo cơ chế **FIFO** (theo ngày ghi sổ PR):

1. Lấy tổng `billed_amt` theo `po_detail` từ các PI đã nộp (không có `pr_detail`).
2. Lấy tổng `billed_amt` trực tiếp theo `pr_detail` từ PI.
3. Phân bổ số tiền từ PO vào từng PR theo thứ tự thời gian, cho đến hết số tiền.

#### `update_billing_percentage(pr_doc, update_modified, adjust_incoming_rate)` (module-level)

Tính `per_billed`:
- Tính `total_amount` (pending_amount = amount - returned_amount) và `total_billed_amount`.
- `per_billed = (total_billed_amount / total_amount) * 100`.
- Nếu `adjust_incoming_rate = True`: điều chỉnh `amount_difference_with_purchase_invoice` cho từng item, sau đó gọi `adjust_incoming_rate_for_pr()`.

#### `adjust_incoming_rate_for_pr(doc)` (module-level)

Sau khi PI được submit, tính lại `valuation_rate` cho PR items dựa trên giá thực tế PI, rồi `repost_future_sle_and_gle(force=True)`.

---

### 1.5. Stock Reservation

#### `reserve_stock(self)`

Gọi `reserve_stock_for_sales_order()` và `reserve_stock_for_production_plan()`.

#### `reserve_stock_for_sales_order(self)`

Nếu `enable_stock_reservation` và `auto_reserve_stock_for_sales_order_on_purchase`: với mỗi item có `sales_order` và `sales_order_item`, tạo **Stock Reservation Entry** liên kết SO → PR.

#### `reserve_stock_for_production_plan(self)`

Nếu `enable_stock_reservation`: với items có `material_request_item` liên kết với Production Plan, tạo Stock Reservation và chuyển đặt trước sang Work Order.

---

### 1.6. Tài sản Cố định

#### `update_assets(self, item, valuation_rate)`

Cập nhật `net_purchase_amount` và `purchase_amount` = `valuation_rate × asset_quantity` cho tất cả Asset records liên kết với PR và item này.

---

### 1.7. Hàm Tiện ích Công khai (Whitelist)

| Hàm                                          | Mô tả                                                    |
|----------------------------------------------|----------------------------------------------------------|
| `update_purchase_receipt_status(docname, status)` | Đóng/mở PR theo trạng thái (Close/Unclose)          |
| `make_lcv(doctype, docname)`                 | Tạo Landed Cost Voucher từ PR với các thông tin cơ bản   |
| `get_stock_value_difference(voucher_no, ...)` | Lấy `stock_value_difference` từ SLE tương ứng           |

---

### 1.8. JS — Giao diện Người dùng

**Thiết lập (setup):**
- `custom_make_buttons`: `Stock Entry → Return`, `Purchase Invoice → Purchase Invoice`, `Landed Cost Voucher`.
- Query filter cho `wip_composite_asset` (asset_type = Composite Asset, docstatus = 0).
- Query filter cho `taxes_and_charges` theo company.

**refresh:**

- Nếu `docstatus=1`, `is_return=1`, `per_billed ≠ 100`: thêm nút **Debit Note** (gọi `make_purchase_invoice`).
- Nếu `docstatus=1`, `is_internal_supplier`, chưa có `inter_company_reference`: thêm nút **Delivery Note** (gọi `make_inter_company_delivery_note`).
- Nếu `docstatus=0`, `maintain_same_rate`: các dòng có PO thì trường `rate` bị read_only.
- Nếu `docstatus=1`: nút **Landed Cost Voucher** (gọi `make_lcv`).
- Gọi `add_custom_buttons()`.

**add_custom_buttons:**
- Draft: nút **Get Items From → Purchase Invoice** (map từ PI có `update_stock=0`, `per_received < 100`).

**company trigger:**
- Toggle hiển thị cột account head.

---

## 2. DeliveryNote (`delivery_note.py` + `delivery_note.js`)

Lớp xử lý nghiệp vụ **Phiếu Xuất kho cho Khách hàng** (Delivery Note).

### 2.1. Cấu hình Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo `status_updater` với 3 cấu hình:

1. **SO Item → `delivered_qty`**: Cộng `qty` từ DN Item vào SO Item (`so_detail`). Tính `per_delivered`. `second_source`: SI có `update_stock=1` cũng tính. `overflow_type = "delivery"`.
2. **SI Item → `delivered_qty`**: Cập nhật `delivered_qty` trên SI Item (`si_detail`). `no_allowance = 1` (không cho vượt quá).
3. **Pick List Item → `delivered_qty`**: Cập nhật `per_delivered` trên Pick List.

Khi `is_return = True`, bổ sung:
- Cập nhật `returned_qty` trên SO Item (`-1 * qty`).
- Cập nhật `returned_qty` + `per_returned` trên DN gốc (`dn_detail`, `-1 * stock_qty`).

---

### 2.2. Validation

#### `validate(self)`

Tuần tự:
- `validate_posting_time()`.
- `super().validate()` — `SellingController.validate()`.
- `validate_references()` → `validate_sales_order_references()` + `validate_sales_invoice_references()`: đảm bảo SO/SI reference hợp lệ.
- `validate_expense_account()` — Kiểm tra tài khoản chi phí.
- `set_status()`.
- `so_required()` — Nếu Selling Settings yêu cầu SO bắt buộc.
- `validate_proj_cust()` — Project phải thuộc về Customer.
- `check_sales_order_on_hold_or_close()`.
- `validate_warehouse()` — Warehouse bắt buộc.
- `validate_uom_is_integer()`.
- `validate_with_previous_doc()` — So sánh với SO (customer, company, project, currency), SO Item (item_code, uom, conversion_factor), SI và SI Item tương tự.
- `set_serial_and_batch_bundle_from_pick_list()`.
- `make_packing_list(self)` — Tạo Packed Items từ Product Bundle.
- `update_current_stock()` — Lấy `actual_qty` hiện tại cho từng item-warehouse.
- `validate_against_stock_reservation_entries()` — Kiểm tra số lượng không vượt quá Stock Reservation.
- `reset_default_field_value("set_warehouse", "items", "warehouse")`.

#### `validate_with_previous_doc(self)`

So sánh với SO: `customer`, `company`, `project`, `currency` phải khớp.
So sánh với SO Item: `item_code`, `uom`, `conversion_factor` phải khớp.
So sánh với SI và SI Item tương tự.
Nếu `maintain_same_sales_rate` và không phải return/internal: kiểm tra giá khớp SO và SI.

#### `validate_expense_account(self)`

Với mỗi item tồn kho: phải có `expense_account`. Tài khoản phải là P&L và không phải Balance Sheet.

---

### 2.3. Vòng đời Submit / Cancel

#### `on_submit(self)`

1. `validate_packed_qty()` — Số lượng packed phải đủ.
2. `update_pick_list_status()` — Cập nhật trạng thái Pick List.
3. Kiểm tra quyền duyệt.
4. `update_prevdoc_status()` — Cập nhật `delivered_qty`, `per_delivered` trên SO.
5. `update_billing_status()` — Cập nhật `billed_amt`, `per_billed` trên DN.
6. Nếu không phải return: `check_credit_limit()`.
7. Nếu là return và `issue_credit_note`: `make_return_invoice()` — Tự động tạo Credit Note.
8. Tạo Serial/Batch Bundle.
9. `validate_standalone_serial_nos_customer()`.
10. `update_stock_reservation_entries()` — Tiêu thụ Stock Reservation Entries liên quan.
11. `update_stock_ledger()` — Tạo SLE (actual_qty âm — hàng xuất).
12. `make_gl_entries()` — Tạo GL Entries.
13. `repost_future_sle_and_gle()`.

#### `on_cancel(self)`

1. `super().on_cancel()`.
2. Kiểm tra SO không bị hold/close.
3. `check_next_docstatus()` — Không có SI đã nộp liên kết.
4. `update_prevdoc_status()`.
5. `update_billing_status()`.
6. `update_stock_reservation_entries()` — Phục hồi reservation.
7. `update_stock_ledger()` — Đảo ngược SLE.
8. `cancel_packing_slips()` — Hủy Packing Slip liên kết.
9. `update_pick_list_status()`.
10. `make_gl_entries_on_cancel()`.
11. `repost_future_sle_and_gle()`.
12. `delete_auto_created_batches()`.

---

### 2.4. Cập nhật Billing Status

#### `update_billing_status(self, update_modified=True)`

Cập nhật `billed_amt`, `per_billed` trên DN và `billing_status` trên SO liên kết dựa trên SI đã nộp.

Hàm module-level `update_billed_amount_based_on_so(so_detail)` dùng logic tương tự PR: phân bổ từ SO về từng DN item.

---

### 2.5. Hàm Tiện ích

| Hàm                                     | Mô tả                                           |
|-----------------------------------------|-------------------------------------------------|
| `update_delivery_note_status(docname, status)` | Đóng/mở DN                               |
| `make_return_invoice(self)`             | Tạo Credit Note từ Return DN                    |
| `check_credit_limit(self)`              | Kiểm tra hạn mức tín dụng khách hàng            |

---

### 2.6. JS — Giao diện Người dùng

**setup:**
- `custom_make_buttons`: Packing Slip, Installation Note, Sales Invoice, Stock Entry (Return), Shipment.
- Query filter warehouse theo company.
- Query filter transporter và driver.
- Query filter `expense_account` và `cost_center` theo company (khi Perpetual Inventory).
- `packed_items` không thể thêm/xóa dòng thủ công.

**refresh:**
- `docstatus=1`, `is_return=1`, `per_billed≠100`: nút **Credit Note** (gọi `make_sales_invoice` từ mapper).
- `docstatus=1`, chưa có `inter_company_reference`, `frappe.model.can_create("Purchase Receipt")`:
  - Nếu `is_internal_customer`: nút **Internal/Inter Company Purchase Receipt** (gọi `make_inter_company_purchase_receipt`).

**DeliveryNoteController (JS Class — kế thừa SellingController):**
- `setup()`: Gọi `setup_accounting_dimension_triggers()`, `setup_posting_date_time_check()`.
- `refresh()`: Với DN submitted, không phải return, `per_billed < 100`: nút **Sales Invoice** (create). Nút **Return** (tạo Stock Entry). Nút **Shipment**. Nút **Packing Slip** (nếu có `has_unpacked_items`).
- `make_delivery_trip()`: Mở Delivery Trip từ DN.

---

## 3. StockEntry (`stock_entry.py` + `stock_entry.js`)

Lớp xử lý toàn bộ nghiệp vụ **Phiếu Kho** với nhiều mục đích khác nhau.

### 3.1. Kiến trúc Purpose-based

#### `_configure_purpose_class(self)`

Stock Entry dùng **Strategy Pattern** — mỗi purpose được xử lý bởi một class riêng:

| Purpose                              | Class Python                               |
|--------------------------------------|--------------------------------------------|
| Manufacture                          | `ManufactureStockEntry`                    |
| Repack                               | `RepackStockEntry`                         |
| Material Transfer                    | `MaterialTransferStockEntry`               |
| Material Transfer for Manufacture    | `MaterialTransferForManufactureStockEntry` |
| Material Consumption for Manufacture | `MaterialConsumptionForManufactureStockEntry` |
| Disassemble                          | `DisassembleStockEntry`                    |
| Send to Subcontractor                | `SendToSubcontractorStockEntry`            |
| Material Issue                       | `MaterialIssueStockEntry`                  |
| Material Receipt                     | `MaterialReceiptStockEntry`                |

Nếu purpose = "Material Transfer" và `transfer_for_material_request()` = True: dùng `MaterialRequestStockEntry`.

---

### 3.2. Validation

#### `validate(self)`

1. Gọi `self.purpose_cls(self).validate()` nếu có — purpose class tự validate logic riêng.
2. `validate_duplicate_serial_and_batch_bundle("items")`.
3. `validate_posting_time()`.
4. `validate_item()` — Kiểm tra mặt hàng còn hoạt động, không disabled.
5. `validate_customer_provided_item()` — Hàng của khách cung cấp không xuất nhập kho.
6. `set_transfer_qty()` — Tính `transfer_qty = qty × conversion_factor`.
7. `validate_uom_is_integer()`.
8. `validate_warehouse_of_sabb()` — Serial Batch Bundle phải khớp warehouse.
9. `validate_source_stock_entry()` — Với Transfer Transit: kiểm tra stock entry gốc.
10. `validate_bom()` — Với Manufacture/Repack: BOM phải tồn tại và active.
11. `set_process_loss_qty()` — Tính `process_loss_qty` cho Manufacture.
12. Với Manufacture/Repack: `mark_finished_and_secondary_items()`, `validate_finished_goods()` hoặc `validate_job_card_fg_item()`.
13. `validate_batch()` — Batch phải thuộc item, chưa hết hạn.
14. `validate_inspection()` — QI bắt buộc nếu cài đặt.
15. `validate_fg_completed_qty()` — qty hàng thành phẩm phải hợp lệ.
16. `validate_difference_account()` — Tài khoản chênh lệch bắt buộc cho Manufacture/Repack.
17. `validate_job_card_item()` — Item trong Job Card phải khớp.
18. `set_purpose_for_stock_entry()` — Đảm bảo purpose được set.
19. `clean_serial_nos()`.
20. `validate_serialized_batch()`.
21. `calculate_rate_and_amount()` — Tính giá và số tiền.
22. `validate_putaway_capacity(self)`.
23. `validate_closed_subcontracting_order()`.

#### `validate_item(self)`

Với từng dòng item: kiểm tra `disabled = 0`, `has_variants = 0`, `is_stock_item = 1` (trừ non-stock purposes), item tồn tại trong database.

#### `validate_source_stock_entry(self)`

Với Transit Transfer: `outgoing_stock_entry` phải là SE loại "Material Transfer" trạng thái submitted.

#### `validate_finished_goods(self)`

Với Manufacture: chỉ được có một dòng finished item. Với Repack: kiểm tra số lượng finished item > 0. Với Process Loss: `process_loss_qty` không vượt `fg_completed_qty`.

---

### 3.3. Tính Giá (Rate Calculation)

#### `calculate_rate_and_amount(self, reset_outgoing_rate=True, raise_error_if_no_rate=True)`

Gọi `set_basic_rate()` → `set_rate_for_outgoing_items()` → `distribute_additional_costs()` → `update_valuation_rate()` → `set_total_incoming_outgoing_value()` → `set_total_amount()`.

#### `set_basic_rate(self, reset_outgoing_rate=True, raise_error_if_no_rate=True)`

Với từng dòng:
- Nếu có `s_warehouse` (xuất kho): gọi `set_rate_for_outgoing_items()` — lấy outgoing rate từ SLE.
- Nếu có `t_warehouse` (nhập kho): gọi `_set_incoming_item_rate()`.

#### `_set_incoming_item_rate(self, d, outgoing_items_cost, raise_error_if_no_rate, zero_valuation_items)`

- Manufacture/Repack: dùng `get_basic_rate_for_manufactured_item()` — phân bổ chi phí nguyên liệu vào thành phẩm.
- Material Transfer: rate = outgoing rate từ dòng nguồn.
- Material Receipt: rate từ `valuation_rate` hoặc item default.

#### `get_basic_rate_for_manufactured_item(self, finished_item_qty, outgoing_items_cost=0) → float`

Tính giá thành phẩm sản xuất:

```
rate = (outgoing_items_cost + additional_costs) / finished_item_qty
```

Nếu có Work Order: có thể thêm chi phí overhead từ Manufacturing Settings. Gọi `_get_rm_cost_for_manufacture()` để lấy chi phí nguyên liệu.

#### `set_rate_for_outgoing_items(self, reset_outgoing_rate=True, raise_error_if_no_rate=True)`

Lấy `outgoing_rate` = giá trị xuất kho từ SLE thực tế (theo phương pháp định giá tồn kho: MA/FIFO/LIFO).

#### `distribute_additional_costs(self)`

Phân bổ chi phí phát sinh (`additional_costs`) vào từng dòng thành phẩm theo tỷ lệ `amount`.

#### `update_valuation_rate(self, reset_outgoing_rate=True)`

Tính `valuation_rate = (amount + additional_cost_per_qty * qty) / transfer_qty` cho từng dòng nhập kho.

---

### 3.4. Stock Ledger

#### `update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False)`

Điểm vào chính:
1. `get_sle_for_source_warehouse(sl_entries, finished_item_row)` — SLE xuất kho trước.
2. `get_sle_for_target_warehouse(sl_entries, finished_item_row)` — SLE nhập kho sau.
3. Nếu cancel: đảo ngược danh sách `sl_entries`.
4. `make_sl_entries(sl_entries, allow_negative_stock)`.

#### `get_sle_for_source_warehouse(self, sl_entries, finished_item_row)`

Với mỗi dòng có `s_warehouse`:
- Tạo SLE: `actual_qty = -transfer_qty`, `incoming_rate = 0`.
- Nếu có `t_warehouse`: đặt `dependant_sle_voucher_detail_no = d.name` (SLE nguồn phụ thuộc SLE đích để lấy đúng outgoing rate).
- Nếu là finished item row khác: `dependant_sle_voucher_detail_no = finished_item_row.name`.

#### `get_sle_for_target_warehouse(self, sl_entries, finished_item_row)`

Với mỗi dòng có `t_warehouse`:
- Tạo SLE: `actual_qty = +transfer_qty`, `incoming_rate = valuation_rate`.
- Nếu có `s_warehouse` hoặc là finished item: `recalculate_rate = 1`.
- Với Material Transfer/Send to Subcontractor: tạo package Inward cho `t_warehouse`.

---

### 3.5. GL Entries

#### `get_gl_entries(self, inventory_account_map)`

Ủy quyền cho `StockEntryGLComposer(self).compose(inventory_account_map)`.

**GL Entries theo Purpose:**

| Purpose            | Bút toán chính                                           |
|--------------------|----------------------------------------------------------|
| Material Receipt   | Debit Warehouse Account, Credit Expense/Difference Account |
| Material Issue     | Debit Expense Account, Credit Warehouse Account         |
| Material Transfer  | Debit Target Warehouse, Credit Source Warehouse         |
| Manufacture        | Debit FG Warehouse, Credit RM Warehouse + Credit Additional Costs Account |
| Repack             | Debit FG Warehouse, Credit RM Warehouse                 |

---

### 3.6. Vòng đời Submit / Cancel

#### `before_submit(self)`

`StockEntrySABB(self).make_serial_and_batch_bundle_for_outward()` — Tạo bundle Outward cho tất cả dòng có `s_warehouse`.

#### `on_submit(self)`

1. `purpose_cls.on_submit()` nếu có.
2. `make_bundle_using_old_serial_batch_fields()`.
3. `adjust_stock_reservation_entries_for_return()`.
4. `update_stock_reservation_entries()`.
5. `update_stock_ledger()`.
6. `make_stock_reserve_for_wip_and_fg()` — Đặt trước tồn kho WIP/FG cho Work Order.
7. `reserve_stock_for_subcontracting()`.
8. `update_subcontracting_order_status()`.
9. `update_pick_list_status()`.
10. `make_gl_entries()`.
11. `repost_future_sle_and_gle()`.
12. `update_cost_in_project()` — Cập nhật chi phí Project.
13. `update_quality_inspection()` — Đánh dấu QI liên kết.
14. `super().on_submit_subcontracting_inward()`.

#### `on_cancel(self)`

1. `purpose_cls.on_cancel()` nếu có.
2. Và các bước ngược lại tương tự `on_submit`.

---

### 3.7. Quản lý Item Chi tiết

#### `get_item_details(self, args, for_update=False)`

Server-side API lấy thông tin item:
1. `_fetch_item_data(args)` — Lấy từ Item master.
2. `_build_item_ret(args, item, ...)` — Build dict return.
3. `_apply_account_defaults(ret)` — Điền expense/income account.
4. `_resolve_subcontract_item(args, ret)` — Với subcontracting.

#### `get_items(self)`

Tự động điền items từ BOM cho Manufacture/Repack: lấy tất cả nguyên liệu từ BOM, tính qty theo `fg_completed_qty`.

#### `set_items_for_stock_in(self)`

Với Transit Transfer (End Transit): lấy danh sách items từ SE gốc (`outgoing_stock_entry`).

---

### 3.8. Hàm Tiện ích Công khai (Whitelist)

| Hàm                        | Mô tả                                           |
|----------------------------|-------------------------------------------------|
| `get_item_details(args)`   | Lấy thông tin item cho dòng SE                  |
| `get_items()`              | Tự động điền items từ BOM                       |
| `get_stock_and_rate()`     | Lấy qty và rate hiện tại                        |

---

### 3.9. JS — Giao diện Người dùng

**Custom Buttons theo purpose (refresh):**

- Manufacture + has Work Order: nút **Work Order** (view), **Job Card** (view).
- Manufacture + Job Card: nút **Alternate Item**, **End Transit**.
- Material Transfer (Transit): nút **End Transit**.
- Submit + nhiều purpose: nút **View Stock Ledger**.
- draft: nút **Get Items from BOM**, **Explode BOM items**.

**StockEntryController (JS Class):**
- `setup()`: Thiết lập các field triggers.
- `s_warehouse / t_warehouse trigger`: Tự động lấy rate khi thay đổi warehouse.
- `item_code trigger`: Gọi `get_item_details()` server-side.
- `qty / basic_rate trigger`: Tính lại amount.
- `purpose trigger`: Reset form fields tùy purpose.

---

## 4. StockReconciliation (`stock_reconciliation.py` + `stock_reconciliation.js`)

Lớp xử lý **Kiểm kê Tồn kho** (điều chỉnh số lượng và giá trị tồn kho).

### 4.1. Validation

#### `validate(self)`

1. `validate_items_exist()` — Phải có ít nhất một dòng item.
2. Điền `expense_account` từ `stock_adjustment_account` của Company nếu chưa có.
3. Điền `cost_center` từ Company nếu chưa có.
4. `validate_posting_time()`.
5. `set_current_serial_and_batch_bundle()` — Lấy serial/batch hiện tại của kho (dùng để tính chênh lệch).
6. `set_new_serial_and_batch_bundle()` — Tạo bundle cho số lượng mới.
7. `validate_duplicate_serial_and_batch_bundle("items")`.
8. `remove_items_with_no_change()` — Bỏ qua các dòng qty và valuation_rate không thay đổi.
9. `validate_data()` — Kiểm tra dữ liệu từng dòng.
10. `change_row_indexes()`.
11. `validate_expense_account()` — Tài khoản chi phí phải là P&L.
12. `validate_customer_provided_item()`.
13. `set_zero_value_for_customer_provided_items()`.
14. `clean_serial_nos()`.
15. `set_total_qty_and_amount()`.
16. `validate_putaway_capacity(self)`.
17. `validate_inventory_dimension()` — Không dùng inventory dimension (chỉ dùng cho opening entries).
18. `validate_uom_is_integer("stock_uom", "qty")`.
19. Nếu `_action = "submit"`: `validate_reserved_stock()`.

#### `validate_data(self)`

Với từng dòng:
- Item tồn tại, là stock item, không disabled.
- Warehouse tồn tại, là stock warehouse.
- qty ≥ 0 (không âm).
- valuation_rate ≥ 0.
- Nếu qty > 0 và valuation_rate = 0 và không `allow_zero_valuation_rate`: ném lỗi.
- Không có duplicate item-warehouse trong cùng phiếu.

#### `remove_items_with_no_change(self)`

So sánh qty và valuation_rate với trạng thái tồn kho hiện tại (từ SLE cuối cùng). Nếu không thay đổi: xóa dòng đó khỏi `items`. Cho phép giữ lại nếu serial/batch thay đổi.

---

### 4.2. Stock Ledger

#### `update_stock_ledger(self, allow_negative_stock=False)`

Với mỗi dòng item:
1. Nếu qty = 0 và valuation_rate = 0 và current_qty = 0: gọi `make_adjustment_entry()`.
2. Nếu item có serial/batch: gọi `get_sle_for_serialized_items()`.
3. Else: lấy `previous_sle` (SLE gần nhất), so sánh qty và valuation_rate. Nếu thay đổi: tạo SLE mới.
4. Gọi `make_sl_entries(sl_entries)`.

#### `get_sle_for_items(self, row, serial_nos=None, current_bundle=True)`

Tạo dict SLE với:
- `actual_qty = qty - current_qty` (chênh lệch).
- `stock_value_difference = qty * valuation_rate - current_qty * current_valuation_rate`.
- `incoming_rate = valuation_rate` nếu nhập; `outgoing_rate` nếu xuất.

#### `make_adjustment_entry(self, row, sl_entries)`

Khi qty = 0 và valuation_rate = 0: lấy `stock_value_difference` từ kho hiện tại, tạo SLE với `actual_qty = 0`, `stock_value_difference = -difference_amount`, `is_adjustment_entry = 1` (chỉ điều chỉnh giá trị không thay đổi qty).

#### `get_sle_for_serialized_items(self, row, sl_entries)`

Với item có serial/batch:
- Dùng `current_serial_and_batch_bundle` (bundle hiện tại trong kho).
- Dùng `serial_and_batch_bundle` (bundle mới theo kiểm kê).
- Tạo hai SLE: một Outward (bundle cũ), một Inward (bundle mới).

---

### 4.3. GL Entries

#### `get_gl_entries(self, inventory_account_map=None)`

Tạo cặp bút toán cho mỗi SLE:
- `stock_value_difference > 0`: Debit Warehouse Account, Credit Expense Account (`stock_adjustment_account`).
- `stock_value_difference < 0`: Debit Expense Account, Credit Warehouse Account.

---

### 4.4. Vòng đời Submit / Cancel

#### `on_submit(self)`

1. `make_bundle_for_current_qty()` — Tạo Serial/Batch Bundle cho qty hiện tại (dùng để tính Outward SLE).
2. `make_bundle_using_old_serial_batch_fields()`.
3. `update_stock_ledger()`.
4. `make_gl_entries()`.
5. `repost_future_sle_and_gle()`.

#### `on_cancel(self)`

1. `validate_reserved_stock()` — Không hủy nếu có stock reservation.
2. `make_sle_on_cancel()` — Tạo SLE đảo ngược (không gọi `update_stock_ledger`).
3. `make_gl_entries_on_cancel()`.
4. `repost_future_sle_and_gle()`.
5. `delete_auto_created_batches()`.

#### `make_sle_on_cancel(self)`

Tạo SLE đảo ngược: với mỗi SLE cũ, tạo SLE mới ngược chiều để khôi phục trạng thái trước kiểm kê.

---

### 4.5. Quản lý Serial/Batch Bundle

#### `set_current_serial_and_batch_bundle(self, voucher_detail_no=None, save=False)`

Với mỗi item có serial/batch: lấy danh sách serial nos / batch nos hiện có trong kho, tạo hoặc cập nhật `current_serial_and_batch_bundle` (loại Outward — ghi nhận hàng xuất ra để điều chỉnh).

#### `set_new_serial_and_batch_bundle(self)`

Tạo `serial_and_batch_bundle` (loại Inward) cho số lượng mới theo kiểm kê.

#### `update_valuation_rate_for_serial_no(self)`

Cập nhật `purchase_rate` trên Serial No record dựa trên `valuation_rate` mới trong Stock Reco.

---

### 4.6. Hàm Tiện ích Công khai (Whitelist)

| Hàm                                            | Mô tả                                         |
|------------------------------------------------|-----------------------------------------------|
| `get_items(warehouse, company)`                | Lấy danh sách tất cả items trong warehouse    |
| `get_stock_balance_for(item_code, warehouse, posting_date, posting_time, batch_no)` | Lấy qty và valuation_rate hiện tại |
| `get_itemwise_batch(warehouse, posting_date, company, item_code)` | Lấy qty theo từng batch     |
| `get_difference_account(purpose, company)`     | Lấy tài khoản chênh lệch tương ứng            |

---

### 4.7. JS — Giao diện Người dùng

**setup:**
- Query filter warehouse theo company.
- Query filter `expense_account` theo company.

**refresh:**
- Nếu `docstatus=0`: nút **Get Items** (gọi `get_items()` từ warehouse).
- Nếu `docstatus=1`: nút **View Stock Ledger**.

**item_code / warehouse trigger:**
- Gọi `get_stock_balance_for()` để điền `current_qty` và `current_valuation_rate`.

---

# MODULE ACCOUNTS

---

## 5. SalesInvoice (`sales_invoice.py` + `sales_invoice.js`)

Lớp xử lý toàn bộ nghiệp vụ **Hóa đơn Bán hàng**.

### 5.1. Cấu hình Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo `status_updater` phức tạp bao gồm các cấu hình:
- DN Item → `billed_qty` (qua `dn_detail`): Tính `per_billed` trên Delivery Note.
- SO Item → `billed_qty` (qua `so_detail`): Tính `billing_status` trên Sales Order.
- Nếu `update_stock=1` + `is_return`: thêm cấu hình trả hàng.

---

### 5.2. Validation

#### `validate(self)`

Tuần tự:
- `validate_auto_set_posting_time()` — Với POS: tự động set posting time.
- `super().validate()` — `AccountsController.validate()` (taxes, totals, payment schedule...).
- `is_subcontracted()` — Phát hiện có phải SI gia công không.
- `so_dn_required()` — SO/DN bắt buộc nếu cài đặt (trừ POS/Debit Note).
- `SalesTaxWithholding(self).on_validate()` — Tính TCS (Tax Collected at Source).
- `validate_proj_cust()`.
- `POSService(self).validate_pos_return()`.
- `validate_with_previous_doc()` — So sánh với SO/DN.
- `validate_uom_is_integer()`.
- `check_sales_order_on_hold_or_close()`.
- `validate_debit_to_acc()` — Tài khoản debit phải là Receivable type.
- `clear_unallocated_advances()`.
- `FixedAssetService(self).validate_fixed_asset()` — Kiểm tra tài sản cố định.
- `FixedAssetService(self).set_income_account_for_fixed_assets()`.
- `validate_item_cost_centers()`.
- `check_conversion_rate()`.
- `validate_accounts()` — Kiểm tra income account.
- `validate_inter_company_party()`.
- Nếu `is_pos`: `validate_pos()`, `validate_pos_opening_entry()`.
- `validate_dropship_item()`.
- Nếu `update_stock`: `validate_warehouse()`, `update_current_stock()`.
- `validate_delivery_note()`.
- Nếu có deferred revenue: `validate_service_stop_date()`.
- `set_against_income_account()` — Tổng hợp tài khoản thu nhập.
- `BillingValidationService(self).validate_multiple_billing()` — Kiểm tra không overbilled trên DN.
- `validate_update_stock_for_pick_list_reference()`.
- `set_serial_and_batch_bundle_from_pick_list()`.
- `update_packing_list()`.
- `TimesheetBillingService(self).set_billing_hours_and_amount()`.
- `set_status()`.
- Validate loyalty points, POS amounts.
- `validate_subcontracted_sales_order()`.

#### `validate_debit_to_acc(self)`

Tài khoản "Debit To" (tài khoản phải thu):
- Phải là Balance Sheet account.
- Phải có `account_type = Receivable`.
- Phải thuộc company hiện tại.
- Phải có `party_type = Customer`.
- Cập nhật `party_account_currency`.

#### `validate_with_previous_doc(self)`

So sánh với SO: `customer`, `company`, `project`, `currency`, `selling_price_list`.
So sánh với SO Item: `item_code`, `uom`, `conversion_factor`.
So sánh với DN và DN Item tương tự.
Nếu `maintain_same_sales_rate` và không phải return: kiểm tra giá khớp SO/DN.

#### `so_dn_required(self)`

Nếu Selling Settings bật `so_required`/`dn_required`: từng dòng phải có `sales_order`/`delivery_note` (trừ exception theo customer/item group).

---

### 5.3. Vòng đời Submit / Cancel

#### `before_submit(self)`

`POSService(self).validate_pos_paid_amount()` — Với POS: số tiền thu phải bằng grand total (trừ write off).

#### `on_submit(self)`

1. `POSService(self).validate_pos_paid_amount()`.
2. Kiểm tra quyền duyệt.
3. `check_prev_docstatus()` — DN và SO phải đã nộp.
4. Bỏ qua `status_updater` nếu là return và không `update_billed_amount_in_sales_order`.
5. `SalesTaxWithholding(self).on_submit()` — Xử lý TCS.
6. `update_status_updater_args()`.
7. `update_prevdoc_status()` — Cập nhật `billed_qty`, `per_billed` trên DN và SO.
8. `update_billing_status_in_dn()`.
9. `clear_unallocated_mode_of_payments()` — POS: xóa mode of payment chưa phân bổ.
10. Nếu `update_stock=1`: Tạo bundles, `update_stock_reservation_entries()`, `update_stock_ledger()`.
11. `FixedAssetService(self).split_asset_based_on_sale_qty()` — Tách tài sản nếu bán một phần.
12. `FixedAssetService(self).process_asset_depreciation()` — Tính khấu hao đến ngày bán.
13. `make_gl_entries()`.
14. Nếu `update_stock=1`: `repost_future_sle_and_gle()`, `update_pick_list_status()`.
15. Nếu không phải return: `update_billing_status_for_zero_amount_refdoc()` cho DN và SO. `check_credit_limit()`.
16. Nếu không phải POS/return: `update_against_document_in_jv()` — Liên kết JV ứng trước.
17. `TimesheetBillingService(self).update_time_sheet()`.
18. Nếu `sales_update_frequency = "Each Transaction"`: `update_company_current_month_sales()`, `update_project()`.
19. `update_linked_doc()` — Liên kết SI inter-company.
20. Xử lý coupon code (used).
21. Xử lý Loyalty Points (earn/redeem).
22. `process_common_party_accounting()`.
23. `update_billed_qty_in_scio()` — Cập nhật qty đã lập hóa đơn trong Subcontracting Inward Order.

#### `on_cancel(self)`

1. `check_if_created_using_pos_and_pos_closing_entry_generated()` — Không hủy nếu POS closing entry đã tạo.
2. `check_if_consolidated_invoice()`.
3. Đảo ngược GL, SLE, stock reservation.
4. `TimesheetBillingService(self).update_time_sheet(None)`.
5. Xử lý loyalty points (undo).
6. `unlink_inter_company_doc()`.

#### `on_update_after_submit(self)`

Nếu các trường kế toán thay đổi (debit_to, write_off): repost lại GL Entries.

---

### 5.4. GL Entries

#### `make_gl_entries(self, gl_entries=None, from_repost=False)`

Điểm vào chính:
- `docstatus=1`: `get_gl_entries()` → `make_gl_entries()` → `make_exchange_gain_loss_journal()`.
- `docstatus=2`: `make_reverse_gl_entries()`.
- Sau đó `update_customer_outstanding()`.

#### `get_gl_entries(self, inventory_account_map=None)`

Tổng hợp:
1. `make_customer_gl_entry()` — Debit Receivable Account (khách hàng).
2. `make_item_gl_entries()` — Credit Income Accounts, Debit COGS (nếu update_stock).
3. `make_tax_gl_entries()` — Bút toán thuế.
4. `make_internal_transfer_gl_entries()`.
5. `make_regional_gl_entries()`.
6. `merge_similar_entries()`.
7. `make_payment_gl_entries()` — POS: Credit tiền mặt/ngân hàng.
8. `make_write_off_gl_entry()` — Nếu có write_off_amount.
9. `make_gle_for_rounding_adjustment()`.

---

### 5.5. Cập nhật Billing Status Delivery Note

#### `update_billing_status_in_dn(self, update_modified=True)`

Cập nhật `billed_amt` trên từng DN Item dựa trên SI đã nộp. Gọi `update_billing_percentage()` trên từng DN liên quan.

---

### 5.6. POS — Point of Sale

#### `validate_pos(self)`

Với POS: phải có `payments` (mode of payment), `debit_to` phải là customer account.

#### `set_pos_fields(self, for_validate=False)`

Điền thông tin POS: `debit_to`, warehouse, income account, expense account từ POS Profile.

#### `POSService` (class service riêng)

Xử lý toàn bộ logic POS tách biệt: validate paid amount, validate pos return, check consolidated invoice, check pos closing entry.

---

### 5.7. Trạng thái Hóa đơn

#### `set_status(self, update=False, status=None, update_modified=True)`

Xác định:
- `Cancelled` (docstatus=2)
- `Draft`
- `Return` (is_return=1)
- `Credit Note Issued`
- `Paid` (outstanding_amount = 0)
- `Overdue` (quá due_date)
- `Partly Paid`
- `Unpaid`
- `Internal Transfer`

---

### 5.8. Hàm Tiện ích Công khai (Whitelist)

| Hàm                                            | Mô tả                                            |
|------------------------------------------------|--------------------------------------------------|
| `make_return_doc(source_name, target_doc)`     | Tạo Credit Note từ Sales Invoice                 |
| `make_inter_company_purchase_invoice(source_name, target_doc)` | Tạo PI inter-company từ SI        |
| `get_bank_cash_account(mode_of_payment, company)` | Lấy tài khoản ngân hàng/tiền mặt             |
| `get_loyalty_programs(customer)`               | Lấy danh sách loyalty program của khách hàng     |

---

### 5.9. JS — Giao diện Người dùng

**SalesInvoiceController (JS Class — kế thừa SellingController):**

**refresh() — Buttons chính:**
- `docstatus=1`, `outstanding_amount>0`: nút **Payment** (tạo Payment Entry).
- `docstatus=1`, không phải return, `per_billed<100`:
  - Nút **Delivery Note** (Get Items From).
  - Nút **Sales Order** (Get Items From).
- `docstatus=1`, `is_return=1`: nút **Credit Note** (return).
- `docstatus=1`, `is_internal_customer`, không có `inter_company_invoice_reference`: nút **Inter Company Purchase Invoice**.
- `docstatus=1`: nút **Dunning** (nếu có plugin), nút **Return / Credit Note**.

**Triggers:**
- `customer`: Lấy thông tin khách hàng, tài khoản debit_to, payment terms.
- `update_stock`: Toggle visibility warehouse column.
- `is_pos`: Toggle POS-specific fields.
- `debit_to`: Validate account.

---

# MODULE BUYING

---

## 6. PurchaseOrder (`purchase_order.py` + `purchase_order.js`)

Lớp xử lý nghiệp vụ **Đơn đặt hàng Mua**.

### 6.1. Cấu hình Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo `status_updater`:
- **MR Item → `ordered_qty`**: Cập nhật `per_ordered` trên Material Request. `global_allowance_field = "over_order_allowance"` từ Buying Settings. `item_allowance_field = "over_order_allowance"`.

Nếu `is_subcontracted`: `source_field` chuyển sang `fg_item_qty` thay vì `stock_qty`.

---

### 6.2. Validation

#### `validate(self)`

1. `super().validate()` — `BuyingController.validate()`.
2. `set_status()`.
3. `validate_supplier()` — Kiểm tra nhà cung cấp không bị block/prevent PO.
4. `validate_schedule_date()` — Schedule date phải sau transaction date.
5. `validate_for_items(self)` (module-level) — Validate từng item.
6. `check_for_on_hold_or_closed_status("Material Request", "material_request")`.
7. `validate_uom_is_integer()`.
8. `validate_with_previous_doc()`.
9. `validate_minimum_order_qty()`.
10. `validate_against_blanket_order()`.
11. `validate_fg_item_for_subcontracting()`.
12. Điền `advance_payment_status = "Not Initiated"` nếu chưa có.
13. `validate_inter_company_party()`.
14. `reset_default_field_value("set_warehouse", "items", "warehouse")`.

#### `validate_supplier(self)`

Kiểm tra:
- Nếu `prevent_pos = True` và Supplier Scorecard là Restricted: ném lỗi.
- Nếu `warn_pos = True`: hiện cảnh báo.

#### `validate_minimum_order_qty(self)`

Với mỗi item có `minimum_order_qty`: nếu `qty < minimum_order_qty`, cảnh báo hoặc ném lỗi tùy cài đặt.

#### `validate_fg_item_for_subcontracting(self)`

Với PO gia công: mỗi dòng phải có `fg_item` là mặt hàng gia công có Subcontracting BOM active.

#### `validate_with_previous_doc(self)`

So sánh với Supplier Quotation: `supplier`, `company`, `currency`.
So sánh với SQ Item: `project`, `item_code`, `uom`, `conversion_factor`.
So sánh với MR: `company`.
So sánh với MR Item: `project`, `item_code` (nếu không gia công).
Nếu `maintain_same_rate`: kiểm tra giá khớp SQ.

---

### 6.3. Vòng đời Submit / Cancel

#### `on_submit(self)`

1. `super().on_submit()` — `BuyingController.on_submit()` (set last purchase rate).
2. Nếu `is_against_so()`: `update_status_updater()` — Thêm cấu hình cập nhật `ordered_qty` lên SO Item.
3. Nếu `is_against_pp()`: `update_status_updater_if_from_pp()` — Thêm cấu hình cập nhật Production Plan.
4. `update_prevdoc_status()` — Cập nhật `ordered_qty`, `per_ordered` trên MR.
5. Nếu không phải subcontracted: `update_requested_qty()` — Cập nhật `ordered_qty` trong Bin.
6. `update_ordered_qty()` — Cập nhật số lượng đã đặt hàng trong Bin.
7. `validate_budget()` — Kiểm tra ngân sách.
8. Kiểm tra quyền duyệt.
9. `update_blanket_order()` — Cập nhật `ordered_qty` trên Blanket Order.
10. `update_linked_doc()` — Liên kết PO inter-company với SO.
11. `auto_create_subcontracting_order()` — Nếu cài đặt bật: tự động tạo Subcontracting Order.

#### `on_cancel(self)`

1. Bỏ qua GL Entry, Payment Ledger Entry liên kết.
2. `super().on_cancel()`.
3. Cập nhật status updater nếu từ SO/PP.
4. Với drop ship: `set_received_qty_to_zero_for_drop_ship_items()` + `update_receiving_percentage()`.
5. Kiểm tra MR không bị hold/closed.
6. `db_set("status", "Cancelled")`.
7. `update_prevdoc_status()`.
8. Nếu không subcontracted: `update_requested_qty()`.
9. `update_ordered_qty()`.
10. `update_blanket_order()`.
11. `unlink_inter_company_doc()`.

---

### 6.4. Cập nhật Số lượng

#### `update_ordered_qty(self, po_item_rows=None)`

Cập nhật `ordered_qty` trong **Bin** cho từng item-warehouse liên quan trong PO.

#### `update_status_updater(self)`

Khi PO liên kết với SO (drop ship): thêm cấu hình cập nhật `ordered_qty` trên SO Item và tính `per_ordered` trên SO.

#### `update_status_updater_if_from_pp(self)`

Khi PO từ Production Plan: cập nhật `ordered_qty` trên PP Sub Assembly Item.

#### `update_delivered_qty_in_sales_order(self)`

Với drop ship items: cập nhật `delivered_qty` = `received_qty` trên SO Item.

---

### 6.5. Trạng thái

Trạng thái PO được xác định bởi `set_status()`:
- `Draft`, `Submitted`, `Cancelled`
- `On Hold` (`on_hold = True`)
- `Closed` (manual close)
- `Completed` (tất cả items đã nhận đủ + đã lập hóa đơn)
- `To Receive and Bill` (chưa nhận và chưa lập hóa đơn)
- `To Receive` (chưa nhận, đã lập hóa đơn một phần)
- `To Bill` (đã nhận, chưa lập hóa đơn)
- `Delivered` (drop ship — đã giao cho khách)

---

### 6.6. Hàm Tiện ích Công khai (Whitelist)

| Hàm                                           | Mô tả                                             |
|-----------------------------------------------|---------------------------------------------------|
| `close_or_unclose_purchase_orders(names, status)` | Đóng/mở nhiều PO cùng lúc                    |
| `update_status(status, name)`                 | Cập nhật trạng thái PO                            |
| `item_last_purchase_rate(name, conversion_rate, item_code, conversion_factor)` | Lấy giá mua cuối cùng |
| `get_list_context(context)`                   | Context cho portal web PO                         |

---

### 6.7. JS — Giao diện Người dùng

**PurchaseOrderController (JS Class — kế thừa BuyingController):**

**refresh() — Buttons chính (docstatus=1):**
- Nút **Update Items** (nếu `can_update_items`).
- Nếu `per_received < 100`:
  - Nút **Purchase Receipt** (gọi `make_purchase_receipt()`).
  - Nút **Stop** hoặc **Unstop** (theo trạng thái).
- Nếu `per_billed < 100`:
  - Nút **Purchase Invoice** (gọi `make_purchase_invoice()`).
- Nút **Subcontracting Order** (nếu là subcontracted và chưa có).
- Nút **Sales Order** (nếu inter-company).
- Nút **Close** / **Re-open** (theo trạng thái).

**make_purchase_receipt():**
```javascript
frappe.model.open_mapped_doc({
    method: "erpnext.buying.doctype.purchase_order.mapper.make_purchase_receipt",
    frm: cur_frm
});
```

**make_purchase_invoice():**
```javascript
frappe.model.open_mapped_doc({
    method: "erpnext.buying.doctype.purchase_order.mapper.make_purchase_invoice",
    frm: cur_frm
});
```

**Triggers:**
- `supplier`: Lấy thông tin nhà cung cấp, địa chỉ, điều khoản thanh toán.
- `item_code`: Lấy thông tin item, giá, UOM.
- `schedule_date`: Validate ngày.

---

# MODULE SELLING

---

## 7. SalesOrder (`sales_order.py` + `sales_order.js`)

Lớp xử lý nghiệp vụ **Đơn đặt hàng Bán**.

### 7.1. Cấu hình Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo `status_updater`:
- **Quotation Item → `ordered_qty`**: Cộng `stock_qty` từ SO Item vào Quotation Item (`quotation_item`).

---

### 7.2. Validation

#### `validate(self)`

1. `super().validate()` — `SellingController.validate()`.
2. `validate_delivery_date()` — Ngày giao hàng phải sau transaction date.
3. `validate_proj_cust()`.
4. `validate_po()` — Kiểm tra PO từ khách hàng.
5. `validate_uom_is_integer()`.
6. `validate_for_items()` — Validate từng item.
7. `validate_warehouse()` — Warehouse bắt buộc nếu item tồn kho.
8. `validate_drop_ship()` — Drop ship phải có nhà cung cấp.
9. `validate_reserved_stock()`.
10. `validate_serial_no_based_delivery()`.
11. `validate_against_blanket_order()`.
12. `validate_inter_company_party()`.
13. Validate coupon code.
14. `make_packing_list(self)`.
15. `validate_with_previous_doc()`.
16. `validate_fg_item_for_subcontracting()`.
17. `set_status()`.
18. Điền `billing_status = "Not Billed"`, `delivery_status = "Not Delivered"`, `advance_payment_status = "Not Requested"` nếu chưa có.
19. `reset_default_field_value()`.
20. Nếu không subcontracted: `enable_auto_reserve_stock()`.

#### `validate_po(self)`

Kiểm tra PO number của khách hàng:
- Nếu bắt buộc PO (`po_required` trong Customer Settings): kiểm tra `po_no` đã điền.
- Nếu không có thêm thay đổi: cảnh báo nếu PO đã tồn tại trong SO khác của cùng khách hàng.

#### `validate_for_items(self)`

Với mỗi item:
- Không phải nhóm hàng (`is_group = 0`).
- Là `is_sales_item = 1`.
- Nếu Product Bundle: `product_bundle_has_stock_item()` phải có ít nhất một item tồn kho.

#### `validate_with_previous_doc(self)`

So sánh với Quotation: `company`, `currency`, `selling_price_list`.
So sánh với Quotation Item: `item_code`, `uom`, `conversion_factor`.

#### `enable_auto_reserve_stock(self)`

Nếu `auto_reserve_stock = True` trong Stock Settings và đây là SO mới: tự động set `reserve_stock = 1`.

---

### 7.3. Vòng đời Submit / Cancel

#### `on_submit(self)`

1. `super().update_prevdoc_status()` — Cập nhật `ordered_qty` trên Quotation.
2. `check_credit_limit()` — Kiểm tra hạn mức tín dụng.
3. `update_reserved_qty()` — Cập nhật `reserved_qty` trong Bin.
4. `delete_removed_delivery_schedule_items()`.
5. Kiểm tra quyền duyệt.
6. `update_project()` — Nếu `sales_update_frequency = "Each Transaction"`.
7. `update_prevdoc_status("submit")` — Cập nhật `enquiry_status` trên Opportunity/Lead.
8. `update_blanket_order()`.
9. `update_linked_doc()` — Liên kết SO inter-company với PO.
10. Xử lý coupon code.
11. Nếu `reserve_stock` và không subcontracted: `create_stock_reservation_entries()`.

#### `on_cancel(self)`

1. Bỏ qua GL Entry, Stock Ledger Entry, Payment Ledger Entry liên kết.
2. `super().on_cancel()`.
3. `super().update_prevdoc_status()`.
4. Không hủy nếu `status = "Closed"`.
5. `delete_delivery_schedule_items()`.
6. `check_nextdoc_docstatus()` — DN/SI liên kết không được submitted.
7. `update_reserved_qty()` — Giải phóng reserved_qty.
8. `update_project()`.
9. `update_prevdoc_status("cancel")`.
10. `db_set("status", "Cancelled")`.
11. `update_blanket_order()`.
12. `cancel_stock_reservation_entries()`.
13. `unlink_inter_company_doc()`.
14. Undo coupon code.

---

### 7.4. Quản lý Tồn kho Đặt trước

#### `update_reserved_qty(self, so_item_rows=None)`

Cập nhật `reserved_qty` trong **Bin** cho từng item-warehouse trong SO. Chỉ tính các items tồn kho, không phải drop ship.

#### `create_stock_reservation_entries(self, items_details=None, from_voucher_type=None, notify=True)`

Tạo Stock Reservation Entries cho từng SO Item:
- Lấy `unreserved_qty` = qty - reserved_qty.
- Tạo SRE với qty tương ứng.
- Hỗ trợ reserve theo Serial No.
- Cập nhật `reserved_qty` và `stock_reserved_qty` sau khi tạo.

#### `cancel_stock_reservation_entries(self, sre_list=None, notify=True)`

Hủy tất cả Stock Reservation Entries liên kết với SO.

#### `has_unreserved_stock(self, table_name="items") → bool`

Kiểm tra còn item nào chưa được reserve đủ số lượng không.

---

### 7.5. Delivery Schedule

#### `create_delivery_schedule(self, child_row, schedules)`

Tạo Delivery Schedule Items cho SO Item: phân bổ qty theo lịch giao hàng.

#### `update_delivery_date_based_on_schedule(self, child_row, first_delivery_date)`

Cập nhật `delivery_date` của SO Item = ngày giao hàng đầu tiên trong lịch.

---

### 7.6. Trạng thái

`set_status()` xác định:
- `Draft`, `Cancelled`
- `On Hold`
- `Completed` (tất cả giao + lập hóa đơn đủ)
- `Closed` (manual close)
- `To Deliver and Bill`
- `To Deliver`
- `To Bill`

`on_update_after_submit(self)`:
- Kiểm tra thay đổi sau submit (supplier cho drop ship).
- Nếu thay đổi `supplier`: `validate_supplier_after_submit()`.

---

### 7.7. Cập nhật Delivery và Billing Status

#### `update_delivery_status(self)`

Tính `per_delivered` dựa trên tổng `delivered_qty` từ DN và SI (có update_stock). Cập nhật `delivery_status` trên SO.

#### `update_picking_status(self)`

Cập nhật `per_picked` dựa trên Pick List Items liên kết.

---

### 7.8. Hàm Tiện ích Công khai (Whitelist)

| Hàm                                              | Mô tả                                             |
|--------------------------------------------------|---------------------------------------------------|
| `close_or_unclose_sales_orders(names, status)`   | Đóng/mở nhiều SO cùng lúc                         |
| `update_status(status, name)`                    | Cập nhật trạng thái SO                            |
| `get_work_order_items(sales_order, for_raw_material_request)` | Lấy danh sách items cần sản xuất |
| `update_produced_qty_in_so_item(so, so_item)`    | Cập nhật `produced_qty` trên SO Item              |
| `get_events(start, end, filters)`                | Lấy events cho Calendar view (delivery dates)      |
| `get_stock_reservation_status()`                 | Lấy trạng thái stock reservation                  |

---

### 7.9. JS — Giao diện Người dùng

**SalesOrderController (JS Class — kế thừa SellingController):**

**refresh() — Buttons chính (docstatus=1):**

- **Update Items** (nếu `can_update_items`).
- `per_delivered < 100`:
  - **Delivery Note** (gọi `make_delivery_note_based_on_delivery_date()`).
  - **Delivery Note (Grouped by Dates)** (nếu có delivery schedule).
  - **Work Order** (nếu có manufacture item).
  - **Pick List** (create pick list).
- `per_billed < 100`:
  - **Sales Invoice** (gọi `make_sales_invoice()`).
- **Purchase Order** (nếu inter-company, chưa có).
- **Maintenance Schedule**, **Maintenance Visit**, **Project**.
- **Stock Reservation**: **Reserve Stock**, **Unreserve Stock** (nếu có unreserved qty).
- **Close** / **Re-open** (theo trạng thái).

**make_delivery_note(delivery_dates, for_reserved_stock=false):**
```javascript
frappe.model.open_mapped_doc({
    method: "erpnext.selling.doctype.sales_order.mapper.make_delivery_note",
    frm: cur_frm
});
```

**make_sales_invoice():**
```javascript
frappe.model.open_mapped_doc({
    method: "erpnext.selling.doctype.sales_order.mapper.make_sales_invoice",
    frm: cur_frm
});
```

**Triggers:**
- `customer`: Lấy thông tin khách hàng, delivery date, địa chỉ, payment terms, credit limit.
- `item_code`: Lấy thông tin item, giá, UOM.
- `delivery_date`: Validate ngày giao hàng.
- `reserve_stock`: Toggle hiển thị reserved qty.

---

# PHỤ LỤC: Luồng Xử lý Tích hợp

## A. Luồng Mua hàng Đầy đủ

```
Material Request (MR)
  ↓ status_updater: per_ordered
Purchase Order (PO)
  ├── on_submit: update_ordered_qty (Bin), update_prevdoc_status (MR)
  ↓ status_updater: per_received, per_billed
Purchase Receipt (PR)
  ├── on_submit:
  │   ├── update_prevdoc_status (PO: received_qty, per_received)
  │   ├── update_billing_status (per_billed)
  │   ├── update_stock_ledger (SLE: +qty vào kho)
  │   └── make_gl_entries:
  │       ├── Debit: Warehouse Account (SRBNB)
  │       └── Credit: Stock Received But Not Billed
  ↓ per_billed cập nhật khi có PI
Purchase Invoice (PI)
  ├── on_submit:
  │   ├── update_prevdoc_status (PR, PO)
  │   ├── update_billing_status_in_pr (billed_amt, per_billed)
  │   ├── [nếu update_stock] update_stock_ledger
  │   └── make_gl_entries:
  │       ├── Debit: Stock Received But Not Billed (đảo SRBNB)
  │       ├── Debit: Provisional Account (đảo provisional nếu có)
  │       └── Credit: Supplier/Payable Account
  └── [adjust_incoming_rate] → repost_future_sle_and_gle trên PR
```

## B. Luồng Bán hàng Đầy đủ

```
Quotation
  ↓ status_updater: ordered_qty
Sales Order (SO)
  ├── on_submit: update_reserved_qty (Bin), check_credit_limit
  │   create_stock_reservation_entries (nếu reserve_stock=1)
  ↓ status_updater: per_delivered, billing_status
Delivery Note (DN)
  ├── on_submit:
  │   ├── update_prevdoc_status (SO: delivered_qty, per_delivered)
  │   ├── update_billing_status (per_billed)
  │   ├── update_stock_reservation_entries (tiêu thụ SRE)
  │   ├── update_stock_ledger (SLE: -qty xuất kho)
  │   └── make_gl_entries:
  │       ├── Debit: COGS (Cost of Goods Sold)
  │       └── Credit: Warehouse Account
  ↓ billing_status cập nhật khi có SI
Sales Invoice (SI)
  ├── on_submit:
  │   ├── update_prevdoc_status (DN, SO)
  │   ├── update_billing_status_in_dn (billed_amt, per_billed)
  │   ├── [nếu update_stock] update_stock_ledger
  │   └── make_gl_entries:
  │       ├── Debit: Customer/Receivable Account
  │       └── Credit: Income Account
  │       [POS]: Credit Cash/Bank
```

## C. Luồng Kiểm kê Tồn kho

```
Stock Reconciliation
  ├── validate:
  │   ├── set_current_serial_and_batch_bundle (lấy trạng thái hiện tại)
  │   ├── set_new_serial_and_batch_bundle (trạng thái mới)
  │   └── remove_items_with_no_change (lọc dòng không thay đổi)
  ├── on_submit:
  │   ├── update_stock_ledger:
  │   │   actual_qty = new_qty - current_qty
  │   │   stock_value_diff = new_qty*new_rate - current_qty*current_rate
  │   └── make_gl_entries:
  │       ├── [tăng giá trị] Debit Warehouse, Credit Stock Adjustment
  │       └── [giảm giá trị] Debit Stock Adjustment, Credit Warehouse
  └── repost_future_sle_and_gle
```

## D. Các Phương pháp Định giá Tồn kho (Stock Valuation Methods)

```
Moving Average (MA):
  new_rate = (old_qty × old_rate + in_qty × in_rate) / (old_qty + in_qty)

FIFO (First In First Out):
  stock_queue = [[10, 100.0], [5, 110.0], ...]
  Xuất: lấy từ đầu queue (lô nhập sớm nhất)

LIFO (Last In First Out):
  stock_queue = [[10, 100.0], [5, 110.0], ...]
  Xuất: lấy từ cuối queue (lô nhập muộn nhất)

Serialized Items:
  Mỗi Serial No có purchase_rate riêng
  Xuất: lấy purchase_rate của từng Serial No
```

---

*Tài liệu được tổng hợp từ mã nguồn ERPNext/Frappe phiên bản develop (tháng 6/2026). Để biết thêm chi tiết, tham khảo trực tiếp source code tại: https://github.com/frappe/erpnext*
