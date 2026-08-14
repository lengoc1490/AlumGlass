# Tài liệu Tổng hợp ERPNext/Frappe - Từ PurchaseInvoice đến BaseDocument

> Tài liệu này mô tả chi tiết toàn bộ các lớp (class), hàm (function) và tính năng theo thứ tự kế thừa từ nghiệp vụ cụ thể đến nền tảng.

---

## Sơ đồ Kế thừa

```
PurchaseInvoice
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

## 1. PurchaseInvoice (`purchase_invoice.py`)

Lớp xử lý toàn bộ nghiệp vụ **Hóa đơn Mua hàng** trong ERPNext.

### 1.1. Cấu hình khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo đối tượng và thiết lập `status_updater` để đồng bộ số lượng đã lập hóa đơn (`billed_amt`) lên **Purchase Order Item** thông qua trường `po_detail`. Tính toán `per_billed` (phần trăm đã xuất hóa đơn) dựa trên `amount`.

---

### 1.2. Vòng đời Tài liệu (Lifecycle Events)

#### `onload(self)`

- Tải thông tin `tax_withholding_category` của nhà cung cấp từ Supplier master.
- Nếu là tài liệu mới, khởi tạo danh sách `tax_withheld_vouchers` rỗng.

#### `before_save(self)`

- Nếu hóa đơn không bị giữ (`on_hold = False`), xóa `release_date`.

#### `on_submit(self)`

Thực thi lần lượt:

1. Kiểm tra trạng thái các tài liệu liên kết trước (`check_prev_docstatus`).
2. Bỏ qua cập nhật trạng thái nếu là hóa đơn trả hàng (`is_return`) và không cập nhật PO.
3. Cập nhật trạng thái các tài liệu trước (`update_prevdoc_status`).
4. Xác thực quyền duyệt từ `Authorization Control`.
5. Cập nhật chứng từ thanh toán liên kết (`update_against_document_in_jv`).
6. Cập nhật trạng thái lập hóa đơn cho các tài liệu có giá trị 0 (PR, PO).
7. Cập nhật phần trăm lập hóa đơn trong Purchase Receipt.
8. Nếu `update_stock = 1`: cập nhật Stock Ledger, xử lý Serial No, cập nhật Subcontract.
9. Tạo GL Entries kế toán.
10. Nếu `update_stock = 1`: repost SLE/GLE tương lai.
11. Cập nhật Project nếu cần.
12. Liên kết chứng từ inter-company.
13. Cập nhật tham chiếu TDS ứng trước.
14. Xử lý Common Party Accounting.

#### `on_update_after_submit(self)`

Kiểm tra xem các trường kế toán (tài khoản ngân hàng, write-off, trạng thái mở) có thay đổi sau khi nộp không. Nếu có, thực hiện repost lại bút toán kế toán.

#### `on_cancel(self)`

Thực thi ngược lại `on_submit`:

1. Kiểm tra hóa đơn trả hàng có liên kết với Payment Entry không.
2. Cập nhật trạng thái PO/PR.
3. Cập nhật Stock Ledger (nếu `update_stock = 1`).
4. Tạo GL Entries đảo ngược.
5. Đặt `status = 'Cancelled'`.
6. Hủy liên kết inter-company.
7. Cập nhật tham chiếu TDS ứng trước (cancel mode).

---

### 1.3. Validation

#### `validate(self)`

Điều phối toàn bộ các kiểm tra hợp lệ:

- Kiểm tra thời gian ghi sổ (`validate_posting_time`).
- Kiểm tra yêu cầu Purchase Order/Receipt bắt buộc.
- Validate thanh toán tiền mặt.
- Validate ngày dịch vụ deferred.
- Validate ngày giải phóng hóa đơn bị tạm giữ.
- Validate tỷ giá, tài khoản credit, tài khoản chi phí.
- Tính toán `per_received` (phần trăm đã nhận hàng).
- Validate inter-company, warehouse, UOM.

#### `validate_release_date(self)`

Đảm bảo `release_date` (ngày giải phóng hóa đơn bị hold) phải lớn hơn ngày hiện tại.

#### `validate_cash(self)`

- Bắt buộc phải có tài khoản tiền mặt/ngân hàng nếu có `paid_amount`.
- Đảm bảo `paid_amount + write_off_amount <= grand_total`.

#### `validate_credit_to_acc(self)`

Kiểm tra tài khoản "Credit To":

- Phải là tài khoản thuộc **Balance Sheet**.
- Phải có loại tài khoản là **Payable**.
- Cập nhật `party_account_currency`.

#### `validate_with_previous_doc(self)`

So sánh các trường quan trọng (nhà cung cấp, công ty, tiền tệ, dự án, mã hàng, UOM) giữa Purchase Invoice và các tài liệu tham chiếu (PO, PR). Nếu `maintain_same_rate` được bật, kiểm tra thêm đơn giá.

#### `validate_warehouse(self)`

Nếu `update_stock = True`, bắt buộc phải chỉ định warehouse cho từng mặt hàng tồn kho.

#### `validate_purchase_receipt_if_update_stock(self)`

Ngăn người dùng vừa chọn `update_stock` vừa liên kết với Purchase Receipt (không được phép cập nhật kho từ cả hai nơi).

#### `validate_supplier_invoice(self)`

- `bill_date` không được lớn hơn `posting_date`.
- Nếu bật kiểm tra tính duy nhất của số hóa đơn nhà cung cấp, kiểm tra trùng `bill_no` trong cùng năm tài chính.

#### `validate_expense_account(self)`

Duyệt qua từng dòng mặt hàng và gọi `validate_account_head` để đảm bảo tài khoản chi phí hợp lệ và thuộc đúng công ty.

#### `validate_write_off_account(self)`

Nếu có `write_off_amount` thì bắt buộc phải có `write_off_account`.

#### `validate_for_repost(self)`

Kiểm tra hợp lệ khi thực hiện repost kế toán: kiểm tra write-off account, expense account, loại chứng từ, deferred accounting.

#### `po_required(self)` / `pr_required(self)`

Nếu cài đặt trong **Buying Settings** yêu cầu PO/PR bắt buộc, kiểm tra từng dòng mặt hàng. Cho phép bypass nếu nhà cung cấp được cấu hình miễn trừ.

#### `check_on_hold_or_closed_status(self)`

Với mỗi dòng có Purchase Order nhưng không có Purchase Receipt, kiểm tra PO không ở trạng thái "On Hold" hoặc "Closed".

#### `check_prev_docstatus(self)`

Đảm bảo Purchase Order và Purchase Receipt tham chiếu đều ở trạng thái đã nộp (docstatus = 1).

---

### 1.4. Thiết lập Giá trị

#### `set_missing_values(self, for_validate=False)`

- Tự động điền `credit_to` từ tài khoản Supplier nếu chưa có.
- Tự động tính `due_date` dựa trên điều khoản thanh toán.
- Tự động bật `apply_tds` nếu nhà cung cấp có `tax_withholding_category`.

#### `set_expense_account(self, for_validate=False)`

Logic phức tạp để tự động xác định tài khoản chi phí cho từng dòng mặt hàng:

- **Mặt hàng tồn kho + update_stock**: Dùng tài khoản warehouse.
- **Mặt hàng tồn kho + có PR**: Kiểm tra GL Entry trong PR, dùng "Stock Received But Not Billed".
- **Mặt hàng tồn kho + không có PR**: Dùng "Stock Received But Not Billed".
- **Tài sản cố định**: Dùng "Asset Received But Not Billed" hoặc CWIP account.
- **Mặt hàng khác**: Bắt buộc phải có tài khoản chi phí.

#### `set_against_expense_account(self, force=False)`

Tổng hợp danh sách tài khoản chi phí từ các dòng mặt hàng, ghi vào trường `against_expense_account` (dùng trong GL Entry).

#### `set_percentage_received(self)`

Tính `per_received`: tổng `received_qty` / tổng `qty` × 100 cho các dòng có liên kết PR.

#### `create_remarks(self)`

Tự động tạo ghi chú nếu trống: "Against Supplier Invoice {bill_no} dated {bill_date}" hoặc "No Remarks".

---

### 1.5. Kế toán - GL Entries

#### `make_gl_entries(self, gl_entries=None, from_repost=False)`

Điểm vào chính để tạo/đảo ngược GL Entries:

- `docstatus = 1` (nộp): Gọi `get_gl_entries()` → `make_gl_entries()` → `make_exchange_gain_loss_journal()`.
- `docstatus = 2` (hủy): Gọi `make_reverse_gl_entries()` → `cancel_provisional_entries()`.
- Sau đó gọi `update_supplier_outstanding()`.

#### `get_gl_entries(self, warehouse_account=None)`

Tổng hợp toàn bộ GL Entries theo thứ tự:

1. `make_supplier_gl_entry` — Bút toán công nợ nhà cung cấp.
2. `make_item_gl_entries` — Bút toán chi phí từng mặt hàng.
3. `make_precision_loss_gl_entry` — Bút toán sai lệch làm tròn.
4. `make_tax_gl_entries` — Bút toán thuế.
5. `make_internal_transfer_gl_entries` — Bút toán chuyển kho nội bộ.
6. `make_regional_gl_entries` — Bút toán theo quy định địa phương.
7. `merge_similar_entries` — Gộp bút toán tương tự.
8. `make_payment_gl_entries` — Bút toán thanh toán tiền mặt.
9. `make_write_off_gl_entry` — Bút toán xóa nợ.
10. `make_gle_for_rounding_adjustment` — Bút toán làm tròn.

#### `make_supplier_gl_entry(self, gl_entries)`

Tạo bút toán **Credit** tài khoản nhà cung cấp (`credit_to`) cho toàn bộ giá trị hóa đơn. Xử lý cả trường hợp hóa đơn trả hàng (`against_voucher` trỏ về hóa đơn gốc) và hóa đơn nội bộ (bỏ qua).

#### `make_item_gl_entries(self, gl_entries)`

Xử lý bút toán chi phí phức tạp cho từng dòng mặt hàng:

- **Tồn kho + update_stock**: Bút toán Debit tài khoản warehouse, xử lý `from_warehouse`, subcontract cost, landed cost.
- **Tồn kho không update_stock**: Debit tài khoản chi phí (expense account), có thể thêm bút toán chênh lệch tỷ giá nếu tỷ giá thay đổi so với PR.
- **Kế toán tạm thời (provisional)**: Đảo ngược bút toán tạm thời từ PR.
- Xử lý thuế valuation chưa được hạch toán trong PR.

#### `make_tax_gl_entries(self, gl_entries)`

- Tạo bút toán cho thuế loại **Total** và **Valuation and Total**.
- Nếu có `negative_expense_to_be_booked` (thuế valuation chưa hạch toán trong PR), tạo bút toán Credit vào "Expenses Included In Valuation".
- Nếu `update_stock`, bút toán thuế valuation trực tiếp vào tài khoản thuế.

#### `make_payment_gl_entries(self, gl_entries)`

Nếu `is_paid = 1`: Tạo cặp bút toán Debit tài khoản nhà cung cấp + Credit tài khoản tiền mặt/ngân hàng.

#### `make_write_off_gl_entry(self, gl_entries)`

Nếu có `write_off_amount`: Tạo bút toán Debit tài khoản nhà cung cấp + Credit tài khoản write-off.

#### `make_gle_for_rounding_adjustment(self, gl_entries)`

Tạo bút toán cho phần chênh lệch làm tròn (`rounding_adjustment`), chỉ khi không phải internal transfer.

#### `make_internal_transfer_gl_entries(self, gl_entries)`

Với internal transfer có thuế: Tạo bút toán Credit vào `unrealized_profit_loss_account`.

#### `make_stock_adjustment_entry(self, gl_entries, item, ...)`

Điều chỉnh giá trị warehouse khi có chênh lệch giữa `valuation_rate × qty` và giá trị thực tế trong Stock Ledger Entry. Đặc biệt xử lý trường hợp hóa đơn trả hàng nội bộ.

#### `cancel_provisional_entries(self)`

Khi hủy hóa đơn, đánh dấu `is_cancelled = 1` cho các GL Entry tạm thời liên quan trong Purchase Receipt.

#### `update_supplier_outstanding(self, update_outstanding)`

Cập nhật số dư công nợ nhà cung cấp sau khi tạo GL Entries.

---

### 1.6. Cập nhật Trạng thái Liên kết

#### `update_billing_status_in_pr(self, update_modified=True)`

Cập nhật `billed_amt` trong từng dòng Purchase Receipt Item dựa trên tổng các hóa đơn đã nộp. Gọi `update_billing_percentage` để tính lại `per_billed` của PR.

#### `get_pr_details_billed_amt(self)`

Query tổng `amount` đã lập hóa đơn theo từng `pr_detail` (dòng PR), chỉ tính các hóa đơn đã nộp (docstatus = 1).

#### `update_status_updater_args(self)`

Nếu `update_stock = 1`, thêm cấu hình cập nhật `received_qty` vào `status_updater`. Nếu là hóa đơn trả hàng, thêm cập nhật `returned_qty`.

---

### 1.7. Tạm giữ Hóa đơn (Invoice Blocking)

#### `invoice_is_blocked(self)`

Trả về `True` nếu hóa đơn đang bị giữ (`on_hold`) và `release_date` chưa đến.

#### `block_invoice(self, hold_comment=None, release_date=None)`

Đặt `on_hold = 1`, lưu ghi chú và ngày giải phóng vào database.

#### `unblock_invoice(self)`

Đặt `on_hold = 0`, xóa `release_date`.

---

### 1.8. Khấu trừ Thuế tại Nguồn (TDS/TCS)

#### `set_tax_withholding(self)`

Điểm vào chính để tính TDS:

1. Xóa dữ liệu TDS cũ.
2. Lấy `tax_withholding_category` từ nhà cung cấp.
3. Gọi `get_party_tax_withholding_details()` để tính toán TDS.
4. Điều chỉnh TDS đã nộp từ các ứng trước (`allocate_advance_tds`).
5. Thêm/cập nhật dòng thuế trong bảng `taxes`.
6. Thêm các chứng từ đã khấu trừ vào `tax_withheld_vouchers`.
7. Tính toán lại tổng cộng.

#### `allocate_advance_tds(self, tax_withholding_details, advance_taxes)`

Phân bổ TDS đã nộp từ Payment Entry (ứng trước) vào hóa đơn hiện tại, giảm trừ vào `tax_withholding_details["tax_amount"]`.

#### `update_advance_tax_references(self, cancel=0)`

Cập nhật `allocated_amount` trong bảng **Advance Taxes and Charges** khi nộp hoặc hủy hóa đơn.

---

### 1.9. Kế toán Tạm thời (Provisional Accounting)

#### `get_provisional_accounts(self)`

Nếu công ty bật `enable_provisional_accounting_for_non_stock_items`:

- Tìm tất cả PR được liên kết.
- Lấy thông tin tài khoản tạm thời (`provisional_expense_account`) từ từng dòng PR.
- Kiểm tra xem bút toán tạm thời có tồn tại trong GL Entry không.
- Lưu vào `self.provisional_accounts`.

#### `make_provisional_gl_entry(self, gl_entries, item)`

Nếu dòng PR có bút toán tạm thời, tạo bút toán đảo ngược tương ứng trong hóa đơn mua hàng (xử lý cả partial billing).

---

### 1.10. Tài sản Cố định

#### `update_gross_purchase_amount_for_linked_assets(self, item)`

Với các tài sản cố định liên kết với hóa đơn, cập nhật `gross_purchase_amount` và `purchase_receipt_amount` = `valuation_rate × asset_quantity`.

---

### 1.11. Dự án

#### `update_project(self)`

Cập nhật `total_purchase_cost` trong Project: cộng thêm `base_net_amount` khi nộp, trừ đi khi hủy. Sử dụng `FOR UPDATE` để tránh race condition.

---

### 1.12. Trạng thái Hóa đơn

#### `set_status(self, update=False, status=None, update_modified=True)`

Xác định trạng thái hóa đơn:

- `Cancelled` (docstatus=2)
- `Internal Transfer` (internal supplier + same company)
- `Overdue` (quá hạn thanh toán)
- `Partly Paid` (thanh toán một phần)
- `Unpaid` (chưa thanh toán, chưa quá hạn)
- `Debit Note Issued` (đã phát hành phiếu ghi nợ)
- `Return` (hóa đơn trả hàng)
- `Paid` (đã thanh toán đủ)

---

### 1.13. Hàm Tiện ích Công khai (Whitelist Functions)

| Hàm                                                         | Mô tả                                                 |
| ----------------------------------------------------------- | ----------------------------------------------------- |
| `make_debit_note(source_name, target_doc)`                  | Tạo Debit Note (hóa đơn trả hàng) từ Purchase Invoice |
| `make_stock_entry(source_name, target_doc)`                 | Tạo Stock Entry từ Purchase Invoice                   |
| `change_release_date(name, release_date)`                   | Thay đổi ngày giải phóng hóa đơn bị hold              |
| `unblock_invoice(name)`                                     | Mở khóa hóa đơn bị tạm giữ                            |
| `block_invoice(name, release_date, hold_comment)`           | Tạm giữ hóa đơn                                       |
| `make_inter_company_sales_invoice(source_name, target_doc)` | Tạo Sales Invoice liên công ty tương ứng              |
| `make_purchase_receipt(source_name, target_doc)`            | Tạo Purchase Receipt từ hóa đơn (số lượng chưa nhận)  |

---

### 1.14. Hàm Hỗ trợ Module-level

#### `get_purchase_document_details(doc)`

Lấy thông tin tỷ giá và đơn giá từ tài liệu gốc (PR hoặc PI) để xử lý chênh lệch tỷ giá.

#### `make_regional_gl_entries(gl_entries, doc)`

Hook cho các bút toán khu vực (regional) — mặc định trả về không thay đổi, có thể override cho từng quốc gia.

---

## 2. BuyingController (`buying_controller.py`)

Lớp trung gian xử lý logic mua hàng dùng chung cho PurchaseInvoice, PurchaseOrder, PurchaseReceipt.

### 2.1. Validation

#### `validate(self)`

Điều phối các kiểm tra mua hàng:

- `set_rate_for_standalone_debit_note`: Lấy `incoming_rate` cho Debit Note độc lập (không có `return_against`).
- `validate_items`: Kiểm tra mặt hàng có phải `is_purchase_item` hoặc `is_sub_contracted_item`.
- `set_qty_as_per_stock_uom`: Tính `stock_qty = qty × conversion_factor`.
- `validate_stock_or_nonstock_items`: Nếu tất cả mặt hàng không phải tồn kho, đổi Tax Category thành "Total".
- `validate_warehouse`, `validate_from_warehouse`, `validate_rejected_warehouse`: Validate kho nhận, kho nguồn, kho từ chối.
- `validate_accepted_rejected_qty`: Kiểm tra `received_qty = qty + rejected_qty`.
- `validate_for_subcontracting`: Kiểm tra gia công (subcontracting).
- `update_valuation_rate`: Tính lại giá trị hàng tồn kho cho từng dòng.

#### `validate_stock_or_nonstock_items(self)`

Nếu tất cả mặt hàng không phải tồn kho và không phải tài sản cố định: đổi các dòng thuế loại "Valuation" hoặc "Valuation and Total" thành "Total" và cảnh báo người dùng.

#### `validate_from_warehouse(self)`

- Kho nguồn (`from_warehouse`) không được trùng kho đích (`warehouse`).
- Không được chọn kho nhà cung cấp khi đang cung cấp nguyên liệu cho gia công.

#### `validate_accepted_rejected_qty(self)`

Kiểm tra tổng `qty + rejected_qty = received_qty`. Nếu `received_qty = 0` nhưng có `qty` hoặc `rejected_qty`, tự động tính.

#### `validate_for_subcontracting(self)`

- Old flow: Bắt buộc `supplier_warehouse` với PR/PI gia công. Bắt buộc BOM cho mặt hàng gia công. Bắt buộc `reserve_warehouse` cho nguyên liệu.
- New flow: Xóa BOM khỏi các dòng không phải gia công.

#### `validate_asset_return(self)`

Ngăn tạo phiếu trả hàng nếu tài sản cố định liên kết chưa được hủy.

---

### 2.2. Cài đặt Giá trị

#### `set_missing_values(self, for_validate=False)`

- `set_supplier_from_item_default`: Tự động điền nhà cung cấp từ Item Default.
- `set_price_list_currency`: Thiết lập tiền tệ bảng giá và tỷ giá.
- Lấy thông tin chi tiết nhà cung cấp (địa chỉ, liên hệ, điều khoản).
- `set_missing_item_details`: Điền thông tin còn thiếu cho từng mặt hàng.

#### `set_rate_for_standalone_debit_note(self)`

Với Debit Note không có `return_against` và `update_stock = True`: lấy `incoming_rate` từ tồn kho tại thời điểm ghi sổ để làm đơn giá.

#### `set_landed_cost_voucher_amount(self)`

Cập nhật `landed_cost_voucher_amount` cho từng dòng từ **Landed Cost Voucher**.

#### `set_supplier_address(self)`

Render và ghi địa chỉ nhà cung cấp, địa chỉ giao hàng, địa chỉ thanh toán vào các trường hiển thị.

#### `set_total_in_words(self)`

Chuyển đổi `grand_total` hoặc `rounded_total` thành chữ bằng `money_in_words()`.

#### `set_incoming_rate(self)`

Với internal transfer: lấy đơn giá từ tài liệu bán hàng tương ứng (Delivery Note, Sales Invoice) thay vì giá mua thông thường. Cập nhật nếu không khớp và thông báo.

---

### 2.3. Cập nhật Giá trị Hàng Tồn kho

#### `update_valuation_rate(self, reset_outgoing_rate=True)`

Tính lại `valuation_rate` cho từng mặt hàng tồn kho:

```
valuation_rate = (base_net_amount + item_tax_amount + rm_supp_cost + landed_cost_voucher_amount) / qty_in_stock_uom
```

Phân bổ `item_tax_amount` theo tỷ lệ `base_net_amount` (mặt hàng cuối cùng nhận phần còn lại để tránh sai số làm tròn).

---

### 2.4. Stock Ledger

#### `update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False)`

Tạo danh sách SLE cho từng mặt hàng tồn kho:

- Xử lý `from_warehouse` (chuyển kho).
- Xử lý `rejected_qty` (kho từ chối).
- Xử lý hóa đơn trả hàng (lấy `outgoing_rate` phù hợp).
- Xử lý Serial No, Batch No.
- Gọi `make_sl_entries_for_supplier_warehouse` cho subcontracting.

#### `update_ordered_and_reserved_qty(self)`

Cập nhật số lượng đã đặt/dự trữ trong Purchase Order sau khi tạo SLE.

---

### 2.5. Tài sản Cố định

#### `process_fixed_asset(self)`

Với PR và PI (có `update_stock`): gọi `auto_make_assets` để tự động tạo tài sản cố định.

#### `auto_make_assets(self, asset_items)`

Với mỗi mặt hàng tài sản có `auto_create_assets = True` và `asset_naming_series`: tạo Asset record tự động (grouped hoặc từng cái một tùy `is_grouped_asset`).

#### `make_asset(self, row, is_grouped_asset=False)`

Tạo một Asset document với thông tin đầy đủ: mã hàng, danh mục tài sản, vị trí, nhà cung cấp, ngày mua, giá trị, số lượng.

#### `update_fixed_asset(self, field, delete_asset=False)`

Cập nhật liên kết tài liệu mua trên Asset record. Khi hủy và `delete_asset = True`: xóa Asset cùng các Asset Movement liên quan.

---

### 2.6. Ngân sách

#### `validate_budget(self)`

Với từng dòng mặt hàng, gọi `validate_expense_against_budget()` để kiểm tra ngân sách chi phí.

---

### 2.7. Cập nhật SL tại Kho Nhà Cung Cấp

#### `update_last_purchase_rate(self, is_submit=True/False)`

Cập nhật đơn giá mua cuối cùng trong Item master khi nộp/hủy PO hoặc PR.

---

## 3. SubcontractingController (`subcontracting_controller.py`)

Xử lý logic gia công (subcontracting) dùng chung cho Purchase Order, Purchase Receipt, Purchase Invoice, Subcontracting Order/Receipt.

### 3.1. Khởi tạo

#### `__init__(self, *args, **kwargs)`

Khởi tạo `subcontract_data` với thông tin về các doctype, trường liên kết tương ứng dựa trên `is_old_subcontracting_flow` (luồng gia công cũ dùng PO, luồng mới dùng Subcontracting Order).

### 3.2. Quản lý Nguyên liệu Cung cấp

#### `create_raw_materials_supplied(self, raw_material_table="supplied_items")`

Điểm vào chính để tạo bảng nguyên liệu cung cấp:

1. `__identify_change_in_item_table`: Tìm các dòng thay đổi so với lần lưu trước.
2. `__prepare_supplied_items`: Chuẩn bị danh sách nguyên liệu từ BOM hoặc Stock Transfer.
3. `__validate_supplied_items`: Kiểm tra Batch No và Serial No đã chuyển.

#### `get_available_materials(self)`

Tính toán nguyên liệu còn khả dụng tại kho nhà cung cấp:

- Lấy tất cả chuyển kho (`Send to Subcontractor`) cho các Subcontract Order liên quan.
- Trừ đi các nguyên liệu đã tiêu thụ (từ PR, PI, SCR đã nộp).
- Kết quả là `available_materials` dict với key `(item_code, subcontracted_item, order)`.

#### `__get_transferred_items(self)`

Query Stock Entry để lấy toàn bộ nguyên liệu đã chuyển cho nhà gia công, bao gồm cả các lần trả lại (Material Transfer return).

#### `__update_consumed_materials(self, doctype, return_consumed_items=False)`

Trừ đi các nguyên liệu đã ghi nhận tiêu thụ trong PR/PI/SCR đã nộp khỏi `available_materials`.

#### `set_consumed_qty_in_subcontract_order(self)`

Sau khi tạo SCR/PR/PI, cập nhật `consumed_qty` trong bảng **Supplied Items** của Subcontract Order.

---

### 3.3. Phân bổ Nguyên liệu

#### `__set_supplied_items(self)`

Điền nguyên liệu vào bảng `supplied_items`:

- **Theo BOM**: Tính qty = `qty_consumed_per_unit × item_qty × conversion_factor`.
- **Theo Material Transfer**: Phân bổ theo tỷ lệ `item_qty / qty_to_be_received`.

#### `__add_supplied_item(self, item_row, bom_item, qty)`

Thêm một dòng nguyên liệu vào bảng `supplied_items`, xử lý Batch No và Serial No từ `available_materials`.

#### `__set_batch_nos(self, bom_item, item_row, rm_obj, qty)` / `__set_serial_nos(self, item_row, rm_obj)`

Phân bổ Batch No và Serial No thực tế từ nguyên liệu đã chuyển cho từng dòng nguyên liệu.

---

### 3.4. Validation Nguyên liệu

#### `__validate_batch_no(self, row, key)` / `__validate_serial_no(self, row, key)`

Kiểm tra Batch No và Serial No được tiêu thụ phải khớp với nguyên liệu đã chuyển trong Subcontract Order. Ném lỗi rõ ràng nếu không khớp.

---

### 3.5. Stock Ledger cho Kho Nhà Cung Cấp

#### `make_sl_entries_for_supplier_warehouse(self, sl_entries)`

Tạo SLE âm (giảm tồn kho) tại `supplier_warehouse` cho từng nguyên liệu đã tiêu thụ. Chỉ áp dụng khi có `supplied_items`.

---

### 3.6. Tính toán Chi phí Nguyên liệu

#### `get_supplied_items_cost(self, item_row_id, reset_outgoing_rate=True)`

Tính tổng chi phí nguyên liệu cho một dòng mặt hàng gia công:

- Nếu `reset_outgoing_rate`: Lấy lại `incoming_rate` từ Stock Ledger để có giá chính xác.
- Tính `amount = consumed_qty × rate` cho từng dòng nguyên liệu.

---

### 3.7. Hàm Tiện ích Công khai

| Hàm                                                               | Mô tả                                           |
| ----------------------------------------------------------------- | ----------------------------------------------- |
| `make_rm_stock_entry(subcontract_order, rm_items, ...)`           | Tạo Stock Entry "Send to Subcontractor"         |
| `get_materials_from_supplier(subcontract_order, rm_details, ...)` | Tạo Stock Entry trả nguyên liệu từ nhà gia công |
| `make_return_stock_entry_for_subcontract(...)`                    | Tạo Stock Entry "Material Transfer" (return)    |

---

## 4. StockController (`stock_controller.py`)

Lớp xử lý tích hợp kế toán và tồn kho.

### 4.1. Validation Tồn kho

#### `validate(self)`

Kiểm tra chất lượng (QI), Serialized Batch, làm sạch Serial No, customer-provided items, Internal Transfer, Putaway capacity, reset conversion factor.

#### `validate_inspection(self)`

Với các mặt hàng yêu cầu QI (`inspection_required_before_purchase/delivery`):

- Cảnh báo nếu chưa có QI khi lưu.
- Ném lỗi nếu chưa có QI khi nộp.
- Kiểm tra QI đã nộp và không bị từ chối.

#### `validate_serialized_batch(self)`

Kiểm tra Serial No phải thuộc Batch No được chỉ định. Kiểm tra Batch chưa hết hạn.

#### `validate_internal_transfer(self)`

Với internal transfer: kiểm tra `target_warehouse`/`from_warehouse`, đơn tiền tệ (phải là tiền công ty), không có Packed Items.

#### `validate_internal_transfer_qty(self)`

So sánh số lượng nhận từ internal transfer với số lượng đã chuyển từ DN/SI gốc. Áp dụng `over_delivery_receipt_allowance`.

#### `validate_putaway_capacity(self)`

Kiểm tra quy tắc Putaway: nếu tổng qty đưa vào vượt capacity của quy tắc, ném lỗi "Over Receipt".

#### `reset_conversion_factor(self)`

Nếu UOM = Stock UOM, tự động reset `conversion_factor = 1.0`.

---

### 4.2. GL Entries cho Kho

#### `make_gl_entries(self, gl_entries=None, from_repost=False, via_landed_cost_voucher=False)`

Tạo GL Entries cho kho hàng nếu công ty bật Perpetual Inventory, Provisional Accounting, hoặc có tài sản cố định trong phiếu.

#### `get_gl_entries(self, warehouse_account=None, ...)`

Với mỗi dòng mặt hàng và SLE tương ứng:

- **Debit** tài khoản warehouse (`stock_value_difference` dương → hàng vào).
- **Credit** tài khoản chi phí (hoặc ngược lại khi hàng ra).
- Với internal transfer: xử lý thêm bút toán sai lệch làm tròn vào `default_expense_account`.

#### `get_stock_ledger_details(self)`

Query tất cả SLE thuộc chứng từ hiện tại, nhóm theo `voucher_detail_no`.

#### `get_voucher_details(self, default_expense_account, default_cost_center, sle_map)`

Lấy danh sách dòng mặt hàng để ghép với SLE. Đặc biệt xử lý **Stock Reconciliation**.

---

### 4.3. Stock Ledger Entries

#### `get_sl_entries(self, d, args)`

Tạo dict SLE với các thông tin: item_code, warehouse, posting_date/time, fiscal_year, actual_qty, incoming_rate, company, batch_no, serial_no, project, is_cancelled. Gọi `update_inventory_dimensions` để thêm chiều kho tùy chỉnh.

#### `update_inventory_dimensions(self, row, sl_dict)`

Gán giá trị các trường Inventory Dimension tùy chỉnh vào SLE dựa trên chiều (dimension) và hướng (vào/ra).

#### `make_sl_entries(self, sl_entries, allow_negative_stock=False, via_landed_cost_voucher=False)`

Wrapper gọi `stock_ledger.make_sl_entries()`.

#### `make_batches(self, warehouse_field)`

Tự động tạo Batch mới cho các mặt hàng có `has_batch_no = True` và `create_new_batch = True` khi nộp.

#### `delete_auto_created_batches(self)`

Khi hủy phiếu, xóa Batch đã tự động tạo và gỡ liên kết khỏi Serial No.

---

### 4.4. Repost

#### `repost_future_sle_and_gle(self, force=False)`

Nếu có SLE tương lai cần cập nhật hoặc bắt buộc repost:

- `item_based_reposting = True`: Tạo từng Repost Item Valuation cho từng cặp item-warehouse.
- `item_based_reposting = False`: Tạo một Repost Item Valuation tổng theo transaction.

---

### 4.5. Kiểm tra Chi phí

#### `check_expense_account(self, item)`

- Bắt buộc phải có `expense_account`.
- Với các doctype không phải PR/PI/Stock Entry: tài khoản phải là loại P&L.
- Nếu là P&L account, bắt buộc phải có `cost_center`.

---

### 4.6. Hàm Tiện ích

#### `make_quality_inspections(doctype, docname, items)` (whitelist)

Tạo Quality Inspection cho danh sách mặt hàng được chỉ định.

#### `future_sle_exists(args, sl_entries=None)`

Kiểm tra có SLE tương lai cho các cặp item-warehouse từ chứng từ hiện tại không (cache trong `frappe.local.future_sle`).

#### `repost_required_for_queue(doc)`

Kiểm tra xem có SLE tiêu thụ trùng lặp item-warehouse với queue-based valuation (FIFO/LIFO) không.

#### `create_repost_item_valuation_entry(args)` / `create_item_wise_repost_entries(...)`

Tạo Repost Item Valuation entry để background worker xử lý.

---

## 5. AccountsController (`accounts_controller.py`)

Lớp xử lý toàn bộ logic kế toán dùng chung.

### 5.1. Validation Chính

#### `validate(self)`

Điều phối hơn 30 validation bao gồm:

- `set_missing_values`: Điền giá trị mặc định.
- `ensure_supplier_is_not_blocked`: Kiểm tra nhà cung cấp không bị block.
- `validate_date_with_fiscal_year`: Ngày phải thuộc năm tài chính.
- `validate_party_accounts`: Tài khoản bên (khách/nhà cung cấp) không được trùng tài khoản mặt hàng.
- `calculate_taxes_and_totals`: Tính toán thuế và tổng cộng.
- `validate_return`: Kiểm tra hóa đơn trả hàng.
- `validate_all_documents_schedule`: Kiểm tra lịch thanh toán.
- `set_tax_withholding` (PO/PI): Tính TDS.
- Và nhiều validation khác.

#### `validate_against_voucher_outstanding(self)`

Với hóa đơn trả hàng: so sánh số dư công nợ của hóa đơn gốc với giá trị hóa đơn trả. Tự động bật `update_outstanding_for_self` nếu hóa đơn trả lớn hơn số dư.

#### `validate_inter_company_reference(self)`

Với internal transfer PR/PI: bắt buộc phải có `inter_company_reference` và từng dòng mặt hàng phải có tham chiếu đến DN Item hoặc SI Item.

#### `disable_pricing_rule_on_internal_transfer(self)`

Với internal transfer: tắt pricing rules để tránh ảnh hưởng giá nội bộ.

#### `validate_currency(self)` / `validate_party_account_currency(self)`

Đảm bảo tiền tệ hóa đơn khớp với tiền tệ tài khoản nhà cung cấp/khách hàng. Với tài khoản multi-currency, kiểm tra cài đặt cho phép.

---

### 5.2. Thanh toán và Ứng trước

#### `set_advances(self)`

Lấy danh sách Payment Entry và Journal Entry ứng trước chưa phân bổ hoặc đã phân bổ cho PO/SO. Tự động phân bổ vào ô `advances`.

#### `get_advance_entries(self, include_unallocated=True)`

Kết hợp Journal Entry ứng trước (`get_advance_journal_entries`) và Payment Entry ứng trước (`get_advance_payment_entries`).

#### `set_advance_gain_or_loss(self)`

Tính chênh lệch tỷ giá (`exchange_gain_loss`) cho từng khoản ứng trước nếu tỷ giá hóa đơn khác tỷ giá lúc thanh toán ứng trước.

#### `update_against_document_in_jv(self)`

Liên kết hóa đơn với các Journal Entry/Payment Entry ứng trước: hủy JE gốc, tách ra, ghi `against_voucher`, nộp lại.

---

### 5.3. Exchange Gain/Loss

#### `make_exchange_gain_loss_journal(self, args=None, dimensions_dict=None)`

Tạo Journal Entry loại "Exchange Gain or Loss" khi có chênh lệch tỷ giá:

- **Journal Entry**: Xử lý từng khoản `difference_amount` trong args.
- **Payment Entry**: Xử lý từng dòng trong `references` có `exchange_gain_loss != 0`.

#### `gain_loss_journal_already_booked(self, ...)`

Kiểm tra xem bút toán exchange gain/loss đã tồn tại chưa (tránh tạo trùng).

---

### 5.4. Lịch Thanh toán

#### `set_payment_schedule(self)`

Tạo lịch thanh toán dựa trên:

- Payment Terms Template.
- Hoặc lấy từ PO/SO liên kết nếu cài đặt `automatically_fetch_payment_terms`.
- Hoặc tạo một dòng đơn với toàn bộ giá trị.

#### `validate_payment_schedule_dates(self)` / `validate_payment_schedule_amount(self)`

Kiểm tra ngày không trùng nhau và tổng giá trị lịch thanh toán = grand total.

#### `set_due_date(self)`

Đặt `due_date` = ngày muộn nhất trong lịch thanh toán.

---

### 5.5. GL Dict

#### `get_gl_dict(self, args, account_currency=None, item=None)`

Tạo dict GL Entry chuẩn với: công ty, ngày, năm tài chính, loại chứng từ, số chứng từ, ghi chú, debit/credit, is_opening, party_type, party, project, accounting dimensions. Gọi `set_balance_in_account_currency` để tính giá trị theo tiền tệ tài khoản.

---

### 5.6. Kiểm tra Hóa đơn Vượt mức

#### `validate_multiple_billing(self, ref_dt, item_ref_dn, based_on)`

Kiểm tra tổng số tiền đã lập hóa đơn cho từng dòng tham chiếu không vượt quá `max_allowed_amt` (ref_amt × (1 + allowance%)). Phân biệt quyền vượt mức theo role.

---

### 5.7. Kế toán Chiết khấu

#### `make_discount_gl_entries(self, gl_entries)`

Nếu bật `enable_discount_accounting`: tạo bút toán riêng cho chiết khấu từng dòng (`discount_account`) và chiết khấu tổng (`additional_discount_account`).

---

### 5.8. Common Party Accounting

#### `process_common_party_accounting(self)`

Nếu bật `enable_common_party_accounting` và có Party Link: tự động tạo Journal Entry để đối trừ công nợ giữa khách hàng và nhà cung cấp là cùng một đối tác.

#### `create_advance_and_reconcile(self, party_link)`

Tạo JE với hai dòng: một dòng đối trừ công nợ phụ (secondary) và một dòng ứng trước công nợ chính (primary). Xử lý multi-currency qua tỷ giá chuyển đổi.

---

### 5.9. Hàm Tiện ích Công khai

| Hàm                                                       | Mô tả                                             |
| --------------------------------------------------------- | ------------------------------------------------- |
| `get_tax_rate(account_head)`                              | Lấy tax_rate và account_name từ Account           |
| `get_default_taxes_and_charges(master_doctype, ...)`      | Lấy bảng thuế mặc định của công ty                |
| `get_taxes_and_charges(master_doctype, master_name)`      | Lấy chi tiết bảng thuế từ template                |
| `get_payment_terms(terms_template, ...)`                  | Tính lịch thanh toán từ template                  |
| `update_invoice_status()`                                 | Cập nhật trạng thái Overdue hàng ngày (scheduler) |
| `update_child_qty_rate(parent_doctype, trans_items, ...)` | Cập nhật qty/rate trên PO/SO sau khi nộp          |

---

## 6. TransactionBase (`transaction_base.py`)

Lớp xử lý logic giao dịch dùng chung cho tất cả các loại phiếu.

### 6.1. Posting Time

#### `validate_posting_time(self)`

- Trong data import: đặt `set_posting_time = 1`.
- Nếu không cho phép chỉnh sửa: lấy thời gian hiện tại cho `posting_date` và `posting_time`.
- Validate định dạng `posting_time`.

### 6.2. Validation UOM

#### `validate_uom_is_integer(self, uom_field, qty_fields, child_dt=None)`

Với các UOM có `must_be_whole_number = True`: kiểm tra tất cả trường số lượng phải là số nguyên.

### 6.3. Validation Tài liệu Trước

#### `validate_with_previous_doc(self, ref)`

So sánh các trường quan trọng (nhà cung cấp, công ty, tiền tệ, dự án, mã hàng, UOM) giữa phiếu hiện tại và tài liệu tham chiếu. Hỗ trợ so sánh cả bảng cha và bảng con.

#### `compare_values(self, ref_doc, fields, doc=None)`

Lấy giá trị từ database của tài liệu tham chiếu và so sánh với giá trị hiện tại theo điều kiện (=, !=, v.v.).

### 6.4. Validation Đơn giá

#### `validate_rate_with_reference_doc(self, ref_details)`

Nếu `maintain_same_rate = True`: so sánh đơn giá với PO/PR tham chiếu. Hành động tùy thuộc `maintain_same_rate_action` (Stop hoặc Warn) và role được phép override.

### 6.5. Thiết lập Giá trị Mặc định

#### `reset_default_field_value(self, default_field, child_table, child_table_field)`

Nếu các dòng trong bảng con có giá trị khác nhau cho một trường, xóa giá trị mặc định ở cấp cha để tránh nhầm lẫn.

### 6.6. Xử lý Mặt hàng Tương tác (Server-side)

#### `process_item_selection(self, item_idx)`

API server-side khi người dùng chọn/thay đổi mặt hàng:

1. Lấy thông tin chi tiết mặt hàng (`fetch_item_details`).
2. Set giá trị cập nhật.
3. Xử lý đơn giá và chiết khấu.
4. Thêm thuế từ Item Tax Template.
5. Thêm mặt hàng miễn phí (free item).
6. Xử lý internal parties (lấy giá theo incoming rate).
7. Tính lại taxes và totals.

#### `fetch_item_details(self, item)`

Gọi `get_item_details()` với đầy đủ context (khách/nhà cung cấp, công ty, kho, tỷ giá, bảng giá) để lấy thông tin đầy đủ của mặt hàng.

---

## 7. StatusUpdater (`status_updater.py`)

Lớp quản lý cập nhật trạng thái và số lượng tích lũy giữa các tài liệu liên kết.

### 7.1. Cập nhật Số lượng

#### `update_prevdoc_status(self)`

Gọi `update_qty()` → `validate_qty()` để cập nhật và kiểm tra số lượng tích lũy.

#### `update_qty(self, update_modified=True)`

Với mỗi cấu hình trong `status_updater`:

- Tính `source_dt_value`: tổng `source_field` từ bảng nguồn.
- Cộng thêm `second_source_condition` nếu có.
- Cập nhật `target_field` trong bảng đích.
- Tính phần trăm (`_update_percent_field_in_targets`).

#### `_update_percent_field(self, args, update_modified=True)`

Tính `target_parent_field` (phần trăm): `sum(min(ref, actual)) / sum(ref) * 100`. Cập nhật status field (Not/Partly/Fully) nếu được cấu hình.

### 7.2. Validation Vượt mức

#### `validate_qty(self)`

Kiểm tra `target_field > target_ref_field` với tolerance `allowance`. Nếu vượt và không có quyền: ném `OverAllowanceError`.

#### `check_overflow_with_allowance(self, item, args)`

Tính `overflow_percent` và so sánh với `allowance` (item-level hoặc global). Nếu vượt và không có role phù hợp: ném lỗi. Nếu có role: cảnh báo.

### 7.3. Trạng thái

#### `set_status(self, update=False, status=None, update_modified=True)`

Duyệt qua `status_map` của doctype (theo thứ tự ngược), tìm trạng thái đầu tiên thỏa điều kiện. Thêm comment lịch sử khi trạng thái thay đổi.

### 7.4. Cập nhật Trạng thái Lập hóa đơn

#### `update_billing_status_for_zero_amount_refdoc(self, ref_dt)`

Cập nhật `per_billed` cho các PR/PO có `base_net_total = 0`.

---

## 8. Document (`document.py`)

Lớp cơ sở cho tất cả document trong Frappe, quản lý vòng đời đầy đủ.

### 8.1. Khởi tạo và Tải dữ liệu

#### `__init__(self, *args, **kwargs)`

- `Document("DocType", "name")`: Load từ database qua `load_from_db()`.
- `Document({"doctype": "X", ...})`: Khởi tạo từ dict.

#### `load_from_db(self)`

Load toàn bộ dữ liệu cha và con từ database. Với single doctype: dùng `get_singles_dict`. Với doctype thông thường: `get_value(..., "*")`. Sau đó load tất cả bảng con (child tables). Gọi `__setup__` ở cuối.

#### `reload(self)`

Wrapper gọi lại `load_from_db()`.

### 8.2. Insert và Save

#### `insert(self, ignore_permissions=None, ...)`

Quy trình insert document mới:

1. `_set_defaults`: Điền giá trị mặc định.
2. `set_user_and_timestamp`: Ghi owner, created timestamp.
3. `check_permission("create")`.
4. `run_method("before_insert")`.
5. `set_new_name`: Đặt tên theo naming series/autoname.
6. `run_before_save_methods`: Gọi `validate`, `before_save/submit`.
7. `_validate`: Validate mandatory, selects, unique, length, v.v.
8. `db_insert`: Ghi vào database.
9. Insert các bảng con.
10. `run_method("after_insert")`.
11. `run_post_save_methods`: `on_update`, webhook, notifications, version.

#### `_save(self, ignore_permissions=None, ignore_version=None)`

Quy trình lưu document đã tồn tại:

1. Kiểm tra quyền write.
2. `check_if_latest`: Kiểm tra timestamp và xác định action (save/submit/cancel/update_after_submit).
3. `run_before_save_methods`.
4. `_validate`.
5. `db_update`: Cập nhật database.
6. `update_children`: Đồng bộ bảng con.
7. `run_post_save_methods`.

### 8.3. Submit và Cancel

#### `submit(self)` / `_submit(self)`

Đặt `docstatus = 1` và gọi `save()`.

#### `cancel(self)` / `_cancel(self)`

Đặt `docstatus = 2` và gọi `save()`.

### 8.4. Vòng đời Sau Lưu

#### `run_before_save_methods(self)`

Dựa trên `_action`:

- `save`: Gọi `before_validate → validate → before_save`.
- `submit`: Gọi `before_validate → validate → before_submit`.
- `cancel`: Gọi `before_cancel`.
- `update_after_submit`: Gọi `before_update_after_submit`.

#### `run_post_save_methods(self)`

Dựa trên `_action`:

- `save`: Gọi `on_update`.
- `submit`: Gọi `on_update → on_submit`.
- `cancel`: Gọi `on_cancel → check_no_back_links_exist`.
- `update_after_submit`: Gọi `on_update_after_submit`.
- Sau đó: `clear_cache → notify_update → update_global_search → save_version → on_change`.

#### `run_method(self, method, *args, **kwargs)`

Thực thi method, sau đó chạy notifications, webhooks, server scripts liên quan.

### 8.5. Hook Pattern

#### `@Document.hook` / `composer(self, *args, **kwargs)`

Decorator cho phép các app khác thêm xử lý vào bất kỳ method nào thông qua `frappe.get_doc_hooks()`. Kết quả từ tất cả hooks được gộp vào `_return_value`.

### 8.6. Đồng bộ Bảng con

#### `update_children(self)` / `update_child_table(self, fieldname, df=None)`

Xóa các dòng không còn trong document, sau đó `db_update()` cho tất cả dòng còn lại.

### 8.7. Bảo mật và Quyền

#### `check_permission(self, permtype="read", permlevel=None)`

Kiểm tra quyền và ném `frappe.PermissionError` nếu không đủ quyền.

#### `validate_higher_perm_levels(self)`

Nếu user không có quyền ở permlevel > 0, reset các trường đó về giá trị gốc (từ database) hoặc mặc định (nếu là document mới).

#### `apply_fieldlevel_read_permissions(self)`

Xóa các trường không có quyền đọc khỏi object trước khi trả về client.

### 8.8. Lock Document

#### `lock(self, timeout=None)` / `unlock(self)`

Tạo/xóa lock file để ngăn chạy hành động song song trên cùng một document (dùng khi `queue_action`).

#### `queue_action(self, action, **kwargs)`

Đưa action vào background queue (RQ), lock document trước khi queue.

### 8.9. Phiên bản và Tracking

#### `save_version(self)`

Nếu doctype có `track_changes = True`: tạo Version document ghi lại diff giữa trạng thái cũ và mới.

#### `reset_seen(self)` / `add_seen(self, user=None)` / `add_viewed(self, user=None)`

Quản lý danh sách người dùng đã xem document (`_seen`, `View Log`).

### 8.10. db_set

#### `db_set(self, fieldname, value=None, update_modified=True, notify=False, commit=False)`

Cập nhật một trường trực tiếp vào database mà không qua validate. Kích hoạt `before_change` và `on_change`. Tùy chọn notify realtime và commit transaction.

---

## 9. BaseDocument (`base_document.py`)

Lớp nền tảng thấp nhất, quản lý cấu trúc dữ liệu document.

### 9.1. Quản lý Thuộc tính

#### `__init__(self, d)`

Khởi tạo từ dict, set `_table_fieldnames`, gọi `update(d)` và `__setup__` nếu có.

#### `update(self, d)` / `update_if_missing(self, d)`

`update`: Ghi đè tất cả giá trị. `update_if_missing`: Chỉ ghi nếu giá trị hiện tại là None và không trong `dont_update_if_missing`.

#### `get(self, key, filters=None, limit=None, default=None)`

Lấy giá trị theo key. Nếu có `filters` (dict): filter danh sách. Nếu `limit`: cắt kết quả.

#### `set(self, key, value, as_value=False)`

Ghi giá trị: Nếu key là child table fieldname và value là list, gọi `extend`. Các reserved keywords bị bỏ qua.

### 9.2. Quản lý Bảng con

#### `append(self, key, value=None)`

Thêm một dòng mới vào child table: khởi tạo document con với đúng doctype, set parent/parenttype/parentfield, tính idx.

#### `extend(self, key, value)`

Gọi `append` cho từng item trong iterable.

#### `remove(self, doc)`

Xóa một dòng khỏi child table và tính lại idx.

#### `_init_child(self, value, key)`

Khởi tạo document con: set doctype, parent info, docstatus, idx, đánh dấu `__islocal`.

### 9.3. Serialize/Deserialize

#### `get_valid_dict(self, sanitize=True, convert_dates_to_str=False, ignore_nulls=False, ignore_virtual=False)`

Lấy dict chỉ chứa các trường hợp lệ (từ meta), với xử lý đặc biệt cho Check (0/1), Int, JSON, Float, datetime, virtual fields.

#### `as_dict(self, no_nulls=False, no_default_fields=False, convert_dates_to_str=False, no_child_table_fields=False)`

Trả về dict đầy đủ bao gồm cả child tables (đệ quy). Thêm các key đặc biệt như `_user_tags`, `__islocal`, `__onload`.

#### `as_json(self)`

Gọi `frappe.as_json(self.as_dict())`.

### 9.4. Database Operations

#### `db_insert(self, ignore_if_duplicate=False)`

INSERT vào database với các cột hợp lệ. Xử lý collision: hash autoname retry tối đa 5 lần, unique key violation hiển thị thông báo rõ ràng.

#### `db_update(self)`

UPDATE database với tất cả cột hợp lệ (trừ `name`). Nếu là document mới (`__islocal`), gọi `db_insert`.

#### `db_update_all(self)`

Raw update cha và tất cả con, không qua validate.

### 9.5. Validate Nội bộ

#### `_validate(self)`

Validate toàn diện: mandatory, data fields, selects, non-negative, length, code fields, sync autoname, extract images, sanitize HTML, save passwords, workflow.

#### `_validate_mandatory(self)`

Kiểm tra tất cả trường `reqd = 1` không được rỗng, bao gồm cả parent/parenttype với child table.

#### `_validate_links(self)`

Với mỗi trường Link/Dynamic Link: kiểm tra giá trị tồn tại trong database, kiểm tra không liên kết đến document đã hủy, cập nhật fetch_from fields.

#### `_validate_selects(self)`

Với mỗi trường Select: giá trị phải nằm trong danh sách options.

#### `_validate_length(self)`

Kiểm tra độ dài: varchar không vượt max_length, int/bigint không vượt max value.

#### `_validate_update_after_submit(self)`

Với docstatus=1, kiểm tra các trường không có `allow_on_submit` không được thay đổi so với database.

#### `_sanitize_content(self)`

Sanitize HTML trong các trường Text/Small Text/Text Editor để phòng chống XSS.

#### `_save_passwords(self)`

Mã hóa và lưu trường Password vào `__Auth` table, thay thế bằng `*****` trên document.

### 9.6. Quyền và Permlevel

#### `get_permlevel_access(self, permission_type="write")`

Lấy danh sách permlevel mà user hiện tại được phép truy cập dựa trên roles.

#### `reset_values_if_no_permlevel_access(self, has_access_to, high_permlevel_fields)`

Reset các trường permlevel cao về giá trị gốc (từ DB hoặc default) nếu user không có quyền.

#### `validate_higher_perm_levels(self)` (override Document)

Kiểm tra permlevel ở cả cha và con, bỏ qua với Administrator.

### 9.7. Chiều Dữ liệu và Precision

#### `precision(self, fieldname, parentfield=None)`

Trả về độ chính xác float cho trường, cache kết quả trong `self._precision`.

#### `get_formatted(self, fieldname, doc=None, currency=None, absolute_value=False, translated=False, format=None)`

Trả về giá trị đã format theo fieldtype (Currency, Date, v.v.).

### 9.8. Controller Lookup

#### `get_controller(doctype)` (module-level function)

Tìm và trả về class Python tương ứng với doctype:

1. Kiểm tra `override_doctype_class` hooks.
2. Load module theo quy ước đặt tên (module/doctype/doctype.py).
3. Tìm class tên = DocType không dấu cách.
4. Cache trong `frappe.controllers[site]`.

---

## Tóm tắt Luồng Xử lý Khi Nộp Purchase Invoice

```
PurchaseInvoice.submit()
  ↓ Document._submit() → docstatus = 1 → save()
  ↓ run_before_save_methods()
      → validate()        [PurchaseInvoice.validate]
          → set_expense_account, validate_credit_to_acc, set_tax_withholding, ...
      → before_submit()   [inherited]
  ↓ _validate()           [BaseDocument]
  ↓ db_update()           [BaseDocument]
  ↓ update_children()     [Document]
  ↓ run_post_save_methods()
      → on_update()       [inherited stubs]
      → on_submit()       [PurchaseInvoice.on_submit]
          → check_prev_docstatus
          → update_prevdoc_status    [StatusUpdater]
              → update_qty → _update_children → _update_percent_field
          → update_billing_status_in_pr
          → update_stock_ledger      [BuyingController]
              → get_sl_entries → make_sl_entries [StockController]
          → make_gl_entries          [PurchaseInvoice]
              → get_gl_entries
                  → make_supplier_gl_entry
                  → make_item_gl_entries
                  → make_tax_gl_entries
                  → make_payment_gl_entries
                  → ...
              → make_gl_entries()    [general_ledger]
          → repost_future_sle_and_gle [StockController]
          → update_project
          → update_advance_tax_references
          → process_common_party_accounting [AccountsController]
```

---

_Tài liệu được tổng hợp từ mã nguồn ERPNext/Frappe phiên bản hiện tại. Để biết thêm chi tiết, tham khảo trực tiếp từng file source code._

===========================================PURCHASE INVOICE VA PURCHASE RECEIPT================================================
Có, đây là một trong những cơ chế phức tạp nhất của ERPNext. Để trả lời chính xác, tôi sẽ phân tích sâu từ code.

## Cơ chế 1: Purchase Invoice → Update GL Entry của Purchase Receipt

### Khi nào PI cập nhật GL của PR?

Có **hai trường hợp chính**:

---

### Trường hợp 1: Provisional Accounting (Kế toán Tạm thời)

Khi PR được tạo trước PI, nếu công ty bật `enable_provisional_accounting_for_non_stock_items`:

**Luồng trong PR (khi submit):**

```
PR.on_submit()
  → make_gl_entries()
      → add_provisional_gl_entry()
          → Debit:  Provisional Account  (tạm thời ghi nhận chi phí)
          → Credit: Supplier/Expense Account
```

**Luồng trong PI (khi submit) — đảo ngược bút toán tạm thời:**

```python
# purchase_invoice.py - make_item_gl_entries()
if provisional_accounting_for_non_stock_items:
    self.get_provisional_accounts()

for item in self.get("items"):
    ...
    if provisional_accounting_for_non_stock_items:
        self.make_provisional_gl_entry(gl_entries, item)
```

**`make_provisional_gl_entry()`** gọi ngược lại method của Purchase Receipt:

```python
def make_provisional_gl_entry(self, gl_entries, item):
    if item.purchase_receipt:
        pr_item = self.provisional_accounts.get(item.pr_detail, {})
        if pr_item.get("has_provisional_entry"):
            purchase_receipt_doc = frappe.get_cached_doc("Purchase Receipt", item.purchase_receipt)

            # Gọi method của PR để tạo GL đảo ngược
            purchase_receipt_doc.add_provisional_gl_entry(
                item,           # truyền item của PI (để xử lý partial billing)
                gl_entries,
                self.posting_date,
                pr_item.get("provisional_account"),
                reverse=1,      # ← đây là key: reverse=1
                item_amount=(
                    (min(item.qty, pr_item.get("qty")) * pr_item.get("rate"))
                    * purchase_receipt_doc.get("conversion_rate")
                ),
            )
```

**Kết quả GL khi PI submit:**

```
Debit:  Expense Account / SRBNB         ← chi phí thực tế
Credit: Supplier (Credit To)            ← công nợ nhà cung cấp
Debit:  Provisional Account             ← đảo ngược bút toán tạm
Credit: Expense Account                 ← đảo ngược bút toán tạm
```

---

### Trường hợp 2: `cancel_provisional_entries()` khi hủy PI

```python
def cancel_provisional_entries(self):
    rows = set()
    purchase_receipts = set()
    for d in self.items:
        if d.purchase_receipt:
            purchase_receipts.add(d.purchase_receipt)
            rows.add(d.name)

    if rows:
        gle = qb.DocType("GL Entry")
        gle_update_query = (
            qb.update(gle)
            .set(gle.is_cancelled, 1)
            .where(
                (gle.voucher_type == "Purchase Receipt")
                & (gle.voucher_no.isin(purchase_receipts))
                & (gle.voucher_detail_no.isin(rows))   # ← rows = PI item names
            )
        )
        gle_update_query.run()
```

> ⚠️ Đây là điểm **rất đặc biệt**: khi PI bị hủy, nó trực tiếp đánh dấu `is_cancelled = 1` trên **GL Entry của PR** (không phải của PI). Điều này khôi phục lại bút toán tạm thời trong PR.

---

### Trường hợp 3: Stock Received But Not Billed (SRBNB)

Đây là cơ chế phổ biến nhất cho mặt hàng tồn kho:

**Khi PR submit:**

```
Debit:  Warehouse Account       (stock value)
Credit: SRBNB Account           ← "treo" tạm ở đây
```

**Khi PI submit — `set_expense_account()` tự động detect:**

```python
# Kiểm tra SRBNB có được hạch toán trong PR không
negative_expense_booked_in_pr = frappe.db.sql("""
    select name from `tabGL Entry`
    where voucher_type='Purchase Receipt'
    and voucher_no=%s
    and account = %s""",
    (item.purchase_receipt, stock_not_billed_account),
)

if negative_expense_booked_in_pr:
    item.expense_account = stock_not_billed_account  # ← PI debit SRBNB để "xóa" credit của PR
```

**GL khi PI submit:**

```
Debit:  SRBNB Account           ← offset credit từ PR
Credit: Supplier (Credit To)    ← ghi nhận công nợ
```

**Kết quả net:**

```
PR: Debit Warehouse / Credit SRBNB
PI: Debit SRBNB   / Credit Supplier
Net: Debit Warehouse / Credit Supplier ✓
```

---

## Cơ chế 2: Stock Ledger — Cơ chế Tính toán Chi tiết

### Kiến trúc tổng thể

```
make_sl_entries()
  → validate_cancellation()
  → set_as_cancel() (nếu hủy)
  → future_sle_exists()

  for each sle:
    → make_entry()              ← tạo SLE record trong DB
    → repost_current_voucher()
        → update_entries_after()   ← TÍNH TOÁN CHÍNH
        → update_qty_in_future_sle()
    → update_bin_qty()
```

---

### `update_entries_after` — Trái tim của Stock Ledger

Đây là class xử lý toàn bộ tính toán giá trị tồn kho:

```python
class update_entries_after:
    def __init__(self, args, allow_zero_rate=False, ...):
        self.valuation_method = get_valuation_method(self.item_code)  # Moving Average / FIFO / LIFO
        self.initialize_previous_data(self.args)
        self.build()
```

#### `initialize_previous_data()`

```python
def initialize_previous_data(self, args):
    # Lấy SLE ngay trước thời điểm hiện tại
    previous_sle = get_previous_sle_of_current_voucher(args)

    warehouse_dict.previous_sle = previous_sle
    warehouse_dict.qty_after_transaction = flt(previous_sle.get("qty_after_transaction"))
    warehouse_dict.valuation_rate = flt(previous_sle.get("valuation_rate"))
    warehouse_dict.stock_value = flt(previous_sle.get("stock_value"))
    warehouse_dict.prev_stock_value = previous_sle.stock_value or 0.0
    warehouse_dict.stock_queue = json.loads(previous_sle.stock_queue or "[]")
    warehouse_dict.stock_value_difference = 0.0
```

#### `build()` — Xác định luồng xử lý

```python
def build(self):
    if self.args.get("sle_id"):
        # Chế độ real-time: chỉ xử lý SLE hiện tại
        self.process_sle_against_current_timestamp()
        if not future_sle_exists(self.args):
            self.update_bin()
    else:
        # Chế độ repost: xử lý SLE hiện tại + tất cả SLE tương lai
        entries_to_fix = self.get_future_entries_to_fix()

        while i < len(entries_to_fix):
            sle = entries_to_fix[i]
            self.process_sle(sle)
            self.update_bin_data(sle)

            # Nếu SLE có dependant (VD: transfer), thêm warehouse đó vào queue
            if sle.dependant_sle_voucher_detail_no:
                entries_to_fix = self.get_dependent_entries_to_fix(entries_to_fix, sle)
```

---

### `process_sle()` — Tính toán cho từng SLE

```python
def process_sle(self, sle):
    self.wh_data = self.data[sle.warehouse]

    # 1. Validate tồn kho âm
    if not self.validate_negative_stock(sle):
        self.wh_data.qty_after_transaction += flt(sle.actual_qty)
        return

    # 2. Lấy dynamic incoming/outgoing rate nếu cần recalculate
    if not self.args.get("sle_id"):
        self.get_dynamic_incoming_outgoing_rate(sle)

    # 3. Tính toán theo loại mặt hàng
    if get_serial_nos(sle.serial_no):
        self.get_serialized_values(sle)          # Serialized items
    elif sle.batch_no and use_batchwise_valuation:
        self.update_batched_values(sle)          # Batch items
    else:
        if valuation_method == "Moving Average":
            self.get_moving_average_values(sle)  # Moving Average
        else:
            self.update_queue_values(sle)        # FIFO / LIFO

    # 4. Tính stock_value_difference
    stock_value_difference = self.wh_data.stock_value - self.wh_data.prev_stock_value
    self.wh_data.prev_stock_value = self.wh_data.stock_value

    # 5. Cập nhật SLE trong DB
    sle.qty_after_transaction = self.wh_data.qty_after_transaction
    sle.valuation_rate = self.wh_data.valuation_rate
    sle.stock_value = self.wh_data.stock_value
    sle.stock_queue = json.dumps(self.wh_data.stock_queue)
    sle.stock_value_difference = stock_value_difference
    frappe.get_doc(sle).db_update()

    # 6. Cập nhật outgoing rate ngược lại lên transaction gốc
    if not self.args.get("sle_id"):
        self.update_outgoing_rate_on_transaction(sle)
```

---

### Ba phương pháp tính giá trị tồn kho

#### Moving Average

```python
def get_moving_average_values(self, sle):
    actual_qty = flt(sle.actual_qty)
    new_stock_qty = flt(self.wh_data.qty_after_transaction) + actual_qty

    if new_stock_qty >= 0:
        if actual_qty > 0:  # NHẬP KHO
            if self.wh_data.qty_after_transaction <= 0:
                # Kho đang âm → lấy luôn incoming_rate
                self.wh_data.valuation_rate = sle.incoming_rate
            else:
                # Bình thường: tính trung bình có trọng số
                new_stock_value = (
                    self.wh_data.qty_after_transaction * self.wh_data.valuation_rate
                    + actual_qty * sle.incoming_rate
                )
                self.wh_data.valuation_rate = new_stock_value / new_stock_qty

        elif sle.outgoing_rate:  # XUẤT KHO
            if new_stock_qty:
                new_stock_value = (
                    self.wh_data.qty_after_transaction * self.wh_data.valuation_rate
                    + actual_qty * sle.outgoing_rate  # actual_qty âm
                )
                self.wh_data.valuation_rate = new_stock_value / new_stock_qty
            else:
                self.wh_data.valuation_rate = sle.outgoing_rate

    # new_stock_qty < 0 (tồn kho âm)
    else:
        if self.wh_data.qty_after_transaction >= 0 and sle.outgoing_rate:
            self.wh_data.valuation_rate = sle.outgoing_rate
```

**Công thức:**

```
new_rate = (old_qty × old_rate + in_qty × in_rate) / (old_qty + in_qty)
```

---

#### FIFO / LIFO (Queue-based)

```python
def update_queue_values(self, sle):
    if self.valuation_method == "LIFO":
        stock_queue = LIFOValuation(self.wh_data.stock_queue)
    else:
        stock_queue = FIFOValuation(self.wh_data.stock_queue)

    _prev_qty, prev_stock_value = stock_queue.get_total_stock_and_value()

    if actual_qty > 0:      # NHẬP: thêm vào queue
        stock_queue.add_stock(qty=actual_qty, rate=incoming_rate)
    else:                   # XUẤT: lấy ra khỏi queue
        stock_queue.remove_stock(
            qty=abs(actual_qty),
            outgoing_rate=outgoing_rate,
            rate_generator=rate_generator  # fallback nếu queue rỗng
        )

    _qty, stock_value = stock_queue.get_total_stock_and_value()
    stock_value_difference = stock_value - prev_stock_value

    self.wh_data.stock_queue = stock_queue.state  # [[qty1, rate1], [qty2, rate2], ...]
    self.wh_data.stock_value = round_off_if_near_zero(
        self.wh_data.stock_value + stock_value_difference
    )

    if self.wh_data.qty_after_transaction:
        self.wh_data.valuation_rate = self.wh_data.stock_value / self.wh_data.qty_after_transaction
```

**Cấu trúc queue:**

```
stock_queue = [[10, 100.0], [5, 110.0], [8, 95.0]]
               ↑qty  ↑rate
```

- **FIFO**: xuất từ đầu queue (lô nhập trước xuất trước).
- **LIFO**: xuất từ cuối queue (lô nhập sau xuất trước).

---

#### Serialized Items

```python
def get_serialized_values(self, sle):
    if actual_qty > 0:  # NHẬP
        stock_value_change = actual_qty * incoming_rate
    else:               # XUẤT
        # Lấy purchase_rate từ Serial No records
        outgoing_value = self.get_incoming_value_for_serial_nos(sle, serial_nos)
        stock_value_change = -1 * outgoing_value

    new_stock_qty = self.wh_data.qty_after_transaction + actual_qty
    if new_stock_qty > 0:
        new_stock_value = (
            self.wh_data.qty_after_transaction * self.wh_data.valuation_rate
            + stock_value_change
        )
        if new_stock_value >= 0:
            self.wh_data.valuation_rate = new_stock_value / new_stock_qty
```

---

### `get_dynamic_incoming_outgoing_rate()` — Tính rate động

Đây là cơ chế **recalculate** rate từ transaction gốc khi repost:

```python
def get_incoming_outgoing_rate_from_transaction(self, sle):
    if sle.voucher_type == "Stock Entry":
        # Recalculate từ Stock Entry
        self.recalculate_amounts_in_stock_entry(sle.voucher_no, sle.voucher_detail_no)
        rate = frappe.db.get_value("Stock Entry Detail", sle.voucher_detail_no, "valuation_rate")

    elif sle.voucher_type in ("Purchase Receipt", "Purchase Invoice", ...):
        if frappe.get_cached_value(sle.voucher_type, sle.voucher_no, "is_return"):
            # Hóa đơn trả hàng → lấy rate theo phương pháp valuation
            if self.valuation_method == "Moving Average":
                rate = get_incoming_rate({...})   # lấy từ SLE trước đó
            else:
                rate = get_rate_for_return(...)   # lấy từ SLE của chứng từ gốc

        elif is_internal_transfer(sle):
            rate = get_incoming_rate_for_inter_company_transfer(sle)

        else:
            # Lấy valuation_rate từ dòng mặt hàng
            rate = frappe.db.get_value(
                sle.voucher_type + " Item",
                sle.voucher_detail_no,
                "valuation_rate"
            )

    return rate
```

---

### `update_outgoing_rate_on_transaction()` — Ghi ngược rate lên chứng từ

Sau khi tính toán xong, **ghi lại rate chính xác** lên transaction gốc:

```python
def update_outgoing_rate_on_transaction(self, sle):
    if sle.actual_qty and sle.voucher_detail_no:
        outgoing_rate = abs(sle.stock_value_difference) / abs(sle.actual_qty)

        if sle.actual_qty < 0 and sle.voucher_type == "Stock Entry":
            self.update_rate_on_stock_entry(sle, outgoing_rate)

        elif sle.voucher_type in ("Delivery Note", "Sales Invoice"):
            self.update_rate_on_delivery_and_sales_return(sle, outgoing_rate)

        elif sle.actual_qty < 0 and sle.voucher_type in ("Purchase Receipt", "Purchase Invoice"):
            self.update_rate_on_purchase_receipt(sle, outgoing_rate)
```

Với PR/PI là hàng trả (actual_qty < 0):

```python
def update_rate_on_purchase_receipt(self, sle, outgoing_rate):
    details = frappe.get_cached_value(sle.voucher_type, sle.voucher_no,
        ["is_internal_supplier", "is_return", "return_against"], as_dict=True)

    if details.is_internal_supplier or (details.is_return and not details.return_against):
        rate = outgoing_rate if details.is_return else sle.outgoing_rate
        frappe.db.set_value(f"{sle.voucher_type} Item", sle.voucher_detail_no,
                           "valuation_rate", rate)
```

---

### `update_qty_in_future_sle()` — Lan truyền thay đổi số lượng

```python
def update_qty_in_future_sle(args, allow_negative_stock=False):
    qty_shift = args.actual_qty

    # Với Stock Reconciliation: tính qty_shift khác
    if args.voucher_type == "Stock Reconciliation":
        qty_shift = get_stock_reco_qty_shift(args)

    # Tìm Stock Reco tiếp theo để giới hạn phạm vi update
    next_stock_reco_detail = get_next_stock_reco(args)
    if next_stock_reco_detail:
        datetime_limit_condition = get_datetime_limit_condition(detail)

    # UPDATE tất cả SLE tương lai
    frappe.db.sql(f"""
        update `tabStock Ledger Entry`
        set qty_after_transaction = qty_after_transaction + {qty_shift}
        where
            item_code = %(item_code)s
            and warehouse = %(warehouse)s
            and voucher_no != %(voucher_no)s
            and is_cancelled = 0
            and posting_datetime > %(posting_datetime)s
            {datetime_limit_condition}
    """, args)

    # Kiểm tra không có SLE nào bị âm sau update
    validate_negative_qty_in_future_sle(args, allow_negative_stock)
```

---

### Tóm tắt toàn bộ luồng

```
Khi PI submit (có PR liên kết):

1. set_expense_account()
   → Phát hiện SRBNB đã được credit trong PR
   → Đặt expense_account = SRBNB cho PI items

2. get_provisional_accounts()
   → Tìm bút toán provisional trong GL Entry của PR

3. make_gl_entries()
   → make_supplier_gl_entry: Credit Supplier
   → make_item_gl_entries:
       → make_provisional_gl_entry:  ← Đảo ngược GL của PR
           Debit Provisional Account
           Credit Expense Account
       → Normal GL:
           Debit SRBNB (= expense_account)
           Credit đã làm ở supplier GL

   Kết quả: PR GL + PI GL = net chính xác

4. cancel_provisional_entries() [khi hủy PI]
   → Đánh is_cancelled=1 trực tiếp trên GL Entry của PR
   → Khôi phục trạng thái PR như trước khi có PI

Stock Ledger khi PI submit (update_stock=1):
   → make_sl_entries()
   → make_entry() → repost_current_voucher()
   → update_entries_after():
       initialize_previous_data() ← lấy trạng thái kho trước
       process_sle():
           get_dynamic_incoming_outgoing_rate() ← lấy valuation_rate từ PI item
           [Moving Average / FIFO / LIFO / Serialized]
           db_update() SLE ← ghi kết quả vào DB
           update_outgoing_rate_on_transaction() ← ghi rate ngược lên PI item
   → update_qty_in_future_sle() ← lan truyền qty cho SLE sau
   → update_bin_qty() ← cập nhật Bin
```
