# Hướng dẫn Quy trình Kho (Inventory) ERPNext — Toàn tập

> **Ngôn ngữ:** Tiếng Việt
> **Phiên bản:** ERPNext (dựa trên mã nguồn Frappe/ERPNext)
> **Mục đích:** Tài liệu tham khảo đầy đủ về mọi quy trình nghiệp vụ kho — Nhập, Xuất, Chuyển kho, Kiểm kê, Hàng trả lại, Thuê ngoài (Subcontracting), Sản xuất, tích hợp Mua-Bán-Kế toán
> **Phạm vi:** Toàn bộ module Stock + kết nối Buying, Selling, Manufacturing, Subcontracting, Accounting

---

## Mục lục

1. [Tổng quan hệ thống kho](#1-tong-quan-he-thong-kho)
2. [Master Data (Danh mục)](#2-master-data-danh-muc)
3. [Stock Entry — Chứng từ kho tổng hợp](#3-stock-entry--chung-tu-kho-tong-hop)
4. [Quy trình Nhập kho](#4-quy-trinh-nhap-kho)
5. [Quy trình Xuất kho](#5-quy-trinh-xuat-kho)
6. [Quy trình Chuyển kho](#6-quy-trinh-chuyen-kho)
7. [Quy trình Kiểm kê (Stock Reconciliation)](#7-quy-trinh-kiem-ke)
8. [Quy trình Trả hàng (Returns)](#8-quy-trinh-tra-hang)
9. [Quy trình Thuê ngoài (Subcontracting)](#9-quy-trinh-thue-ngoai-subcontracting)
10. [Quy trình Sản xuất & Kho](#10-quy-trinh-san-xuat--kho)
11. [Pick List — Chuẩn bị hàng](#11-pick-list--chuan-bi-hang)
12. [Landed Cost — Phân bổ chi phí](#12-landed-cost--phan-bo-chi-phi)
13. [Kết nối với Kế toán](#13-ket-noi-voi-ke-toan)
14. [Quản lý định giá lại (Repost & Valuation)](#14-quan-ly-dinh-gia-lai)
15. [Stock Settings & Cấu hình](#15-stock-settings--cau-hinh)
16. [Báo cáo Kho](#16-bao-cao-kho)

---

## 1. Tổng quan hệ thống kho

### 1.1. Kiến trúc module Stock

Module Stock (Kho) là một trong những module cốt lõi của ERPNext, nằm tại `erpnext/stock/`. Nó quản lý toàn bộ vòng đời hàng hóa — từ nhập kho, xuất kho, chuyển kho, kiểm kê đến định giá tồn kho.

**Các thành phần chính:**

| Thành phần                   | Mô tả                                                                                         |
| ---------------------------- | --------------------------------------------------------------------------------------------- |
| **Doctype nghiệp vụ**        | Stock Entry, Delivery Note, Purchase Receipt, Material Request, Stock Reconciliation          |
| **Doctype master**           | Item, Warehouse, Serial No, Batch, Item Price, Price List                                     |
| **Stock Ledger Entry (SLE)** | Bảng ghi sổ cái kho — ghi nhận mọi thay đổi về số lượng và giá trị tồn kho                    |
| **Bin**                      | Bảng tồn kho tức thời (actual_qty, reserved_qty, ordered_qty, stock_value)                    |
| **Valuation Engine**         | Công cụ định giá tồn kho (FIFO, Moving Average) — nằm trong `stock/valuation.py`              |
| **Stock Controller**         | Lớp controller chung kết nối Stock với Accounting — nằm tại `controllers/stock_controller.py` |

**Các file Python quan trọng trong module Stock:**

| File                              | Vai trò                                                             |
| --------------------------------- | ------------------------------------------------------------------- |
| `stock/__init__.py`               | Khởi tạo module, role, warehouse account mapping                    |
| `stock/stock_ledger.py`           | Tạo SLE, định giá (FIFO/MA), engine `update_entries_after`          |
| `stock/valuation.py`              | FIFO queue valuation                                                |
| `stock/utils.py`                  | Hàm tiện ích: `get_bin()`, `get_incoming_rate()`                    |
| `stock/get_item_details.py`       | Lấy chi tiết item (giá, UOM, warehouse...)                          |
| `stock/reorder_item.py`           | Tự động tạo Material Request khi tồn kho thấp (cron 0h45 hằng ngày) |
| `controllers/stock_controller.py` | `make_gl_entries()`, `get_gl_entries()` — cầu nối Kho ↔ Kế toán     |

**Phân quyền (Roles):**

| Role                | Quyền                                          |
| ------------------- | ---------------------------------------------- |
| **Stock Manager**   | Toàn quyền — tạo, submit, hủy mọi chứng từ kho |
| **Stock User**      | Tạo, submit chứng từ kho (không hủy)           |
| **Item Manager**    | Quản lý danh mục Item                          |
| **Quality Manager** | Quản lý Quality Inspection                     |

### 1.2. Các khái niệm nền tảng

#### Stock Ledger Entry (SLE) — Trái tim của kho

SLE là doctype ghi nhận mọi thay đổi về số lượng và giá trị tồn kho. Mỗi giao dịch kho (nhập, xuất, chuyển, kiểm kê) đều tạo ra ít nhất một bản ghi SLE.

**Cấu trúc SLE:**

| Field                           | Ý nghĩa                                                             |
| ------------------------------- | ------------------------------------------------------------------- |
| `item_code`                     | Mã hàng hóa                                                         |
| `warehouse`                     | Mã kho                                                              |
| `actual_qty`                    | Số lượng thay đổi (+ nhập vào, - xuất ra)                           |
| `qty_after_transaction`         | Tồn kho sau giao dịch                                               |
| `valuation_rate`                | Đơn giá tồn kho tại thời điểm giao dịch                             |
| `stock_value`                   | Giá trị tồn kho sau giao dịch                                       |
| `stock_value_difference`        | **Chênh lệch giá trị — đây chính là số tiền sẽ ghi vào GL Entry**   |
| `voucher_type`                  | Loại chứng từ gốc (Stock Entry, Delivery Note, Purchase Receipt...) |
| `voucher_no`                    | Số chứng từ gốc                                                     |
| `voucher_detail_no`             | Dòng chi tiết trong chứng từ gốc                                    |
| `batch_no`                      | Số lô (nếu item quản lý theo lô)                                    |
| `serial_no`                     | Số serial (nếu item quản lý serial)                                 |
| `posting_date` / `posting_time` | Ngày giờ hạch toán                                                  |
| `is_cancelled`                  | Đã hủy hay chưa                                                     |
| `stock_queue`                   | FIFO queue (dạng JSON) — lưu [số lượng, đơn giá] cho từng lớp nhập  |

#### Bin — Bảng tồn kho tức thời

Bin là bảng tổng hợp tồn kho cho từng cặp Item-Warehouse. Khác với SLE (ghi lịch sử), Bin chỉ lưu **trạng thái hiện tại**.

| Field            | Ý nghĩa                                                   |
| ---------------- | --------------------------------------------------------- |
| `actual_qty`     | Tồn kho thực tế                                           |
| `ordered_qty`    | Số lượng đã đặt mua (PO đã submit)                        |
| `reserved_qty`   | Số lượng đã giữ (SO đã submit, dành cho production)       |
| `projected_qty`  | Tồn kho dự kiến = actual_qty + ordered_qty - reserved_qty |
| `stock_value`    | Giá trị tồn kho                                           |
| `valuation_rate` | Đơn giá tồn kho hiện tại                                  |

#### Định giá tồn kho (Valuation)

ERPNext hỗ trợ 3 phương pháp định giá:

1. **FIFO (First In, First Out):** Hàng nhập trước được xuất trước. Giá trị xuất kho lấy từ giá của lô nhập cũ nhất. Queue được lưu trong `stock_queue` của SLE.
2. **Moving Average (Bình quân động):** Giá trị tồn kho được tính bình quân sau mỗi lần nhập. Công thức: `valuation_rate_moi = (stock_value_cu + stock_value_difference) / qty_after_transaction`
3. **LIFO (Last In, First Out):** Hàng nhập sau được xuất trước. Cần cài plugin riêng (không có sẵn trong ERPNext core).

**Cách tính `stock_value_difference` theo Moving Average:**

- Khi **nhập**: tăng stock_value, `stock_value_difference = qty * rate`
- Khi **xuất**: giảm stock_value, `stock_value_difference = qty * current_valuation_rate` (hoặc FIFO rate)

#### Perpetual Inventory & Kết nối Kế toán

Khi bật **Perpetual Inventory** (Kiểm kê vĩnh viễn) ở Company:

- Mỗi giao dịch kho tạo GL Entry (bút toán kép)
- `stock_value_difference` trong SLE chính là số tiền ghi Nợ/Có
- Khi tắt: chỉ cập nhật SLE và Bin — không ảnh hưởng kế toán, COGS được tính cuối kỳ

**Nguyên tắc hạch toán cơ bản của kho:**

```
Nợ  Tài khoản hàng tồn kho (Asset)    [stock_value_difference]
Có  Tài khoản đối ứng (COGS/Expense)  [stock_value_difference]
```

Khi nhập kho:

- Nợ TK Hàng tồn kho (tăng tài sản) / Có TK Đối ứng

Khi xuất kho:

- Nợ TK Chi phí (COGS) / Có TK Hàng tồn kho (giảm tài sản)

### 1.3. Warehouse & Warehouse Account Mapping

**Warehouse** được tổ chức dưới dạng cây phân cấp (Nested Set) với các trường `lft`/`rgt`.

**Cấu trúc Warehouse:**

| Field              | Ý nghĩa                               |
| ------------------ | ------------------------------------- |
| `warehouse_name`   | Tên kho                               |
| `parent_warehouse` | Kho cha (cây phân cấp)                |
| `warehouse_type`   | Loại kho (Storage, Transit, WIP...)   |
| `account`          | Tài khoản kế toán riêng cho kho này   |
| `company`          | Công ty sở hữu                        |
| `is_group`         | Là kho nhóm (không chứa hàng thực tế) |
| `disabled`         | Vô hiệu hóa                           |

**Warehouse Account Mapping** (hàm `get_warehouse_account_map()` trong `stock/__init__.py`):

Thứ tự ưu tiên khi xác định tài khoản kế toán của một kho:

1. `account` field trên Warehouse (nếu có)
2. `account` của Warehouse cha (đệ quy)
3. `default_inventory_account` của Company
4. Tài khoản có `account_type = "Stock"` của Company

Kết quả được cache trong `frappe.flags.warehouse_account_map` và được `StockController.get_gl_entries()` sử dụng để biết tài khoản nào cần ghi Nợ/Có cho mỗi kho.

## 2. Master Data (Danh mục)

### 2.1. Item — Danh mục hàng hóa

Item là doctype quan trọng nhất trong module Stock. Mỗi hàng hóa, nguyên vật liệu, thành phẩm, dịch vụ đều là một Item.

**Các trường quan trọng liên quan đến kho:**

| Trường                   | Ý nghĩa                                          |
| ------------------------ | ------------------------------------------------ |
| `is_stock_item`          | Là hàng tồn kho (có theo dõi số lượng trong kho) |
| `is_sub_contracted_item` | Là hàng thuê ngoài gia công                      |
| `has_batch_no`           | Quản lý theo lô                                  |
| `has_serial_no`          | Quản lý theo số serial                           |
| `has_expiry_date`        | Có hạn sử dụng                                   |
| `shelf_life_in_days`     | Số ngày hạn sử dụng                              |
| `item_group`             | Nhóm hàng                                        |
| `stock_uom`              | Đơn vị tính tồn kho (chuẩn)                      |
| `valuation_method`       | Phương pháp định giá: FIFO / Moving Average      |
| `valuation_rate`         | Đơn giá tồn kho (mặc định từ Item master)        |
| `is_purchase_item`       | Có thể mua                                       |
| `is_sales_item`          | Có thể bán                                       |
| `is_manufactured_item`   | Có thể sản xuất                                  |
| `allow_alternative_item` | Cho phép Item thay thế                           |
| `default_warehouse`      | Kho mặc định                                     |
| `default_bom`            | BOM mặc định (cho sản xuất/thuê ngoài)           |

### 2.2. Warehouse — Danh mục kho

Warehouse được tổ chức cây phân cấp. Ví dụ:

```
Stores (Kho tổng)
├── Raw Materials (Nguyên vật liệu)
├── WIP (Bán thành phẩm)
├── Finished Goods (Thành phẩm)
├── Scrap (Phế liệu)
└── Transit (Đang vận chuyển)
```

**Kho quan trọng trong quy trình:**

| Loại kho               | Mục đích                                 |
| ---------------------- | ---------------------------------------- |
| **Source Warehouse**   | Kho nguồn — nơi lấy hàng khi xuất/chuyển |
| **Target Warehouse**   | Kho đích — nơi hàng đến khi nhập/chuyển  |
| **WIP Warehouse**      | Kho sản xuất dở dang (Work In Progress)  |
| **FG Warehouse**       | Kho thành phẩm                           |
| **Scrap Warehouse**    | Kho phế liệu                             |
| **Supplier Warehouse** | Kho nhà cung cấp (trong thuê ngoài)      |
| **Transit Warehouse**  | Kho trung chuyển                         |

### 2.3. Serial No — Quản lý theo số serial

Dùng cho các item cần theo dõi từng đơn vị riêng lẻ (thiết bị, điện thoại, máy móc...).

**Lifecycle của Serial No:**

```
Active (Trong kho)
  |-- Được tạo khi nhập kho (Purchase Receipt, Stock Entry Manufacture)
  |-- Có warehouse, chưa có delivery document
  |
Delivered (Đã bán)
  |-- Được gán khi xuất bán (Delivery Note, Sales Invoice)
  |-- Có delivery_document_type, delivery_document_no
  |
Expired (Hết hạn bảo hành)
  |-- warranty_expiry_date đã qua
```

**Nguyên tắc quan trọng:**

- Mỗi Serial No là duy nhất trên toàn hệ thống
- 1 Serial = 1 đơn vị (qty luôn là 1)
- Khi nhập: Serial No được tạo tự động (nếu có `serial_no_series`) hoặc nhập thủ công
- Khi xuất: Serial No phải thuộc warehouse xuất
- Khi trả hàng: Serial No phải giống với Serial No đã xuất
- Không thể nhập Serial No đã tồn tại trong kho khác

### 2.4. Batch — Quản lý theo lô

Dùng cho các item cần theo dõi theo lô (thực phẩm, dược phẩm, hóa chất...).

**Cách đặt tên Batch:**

- Người dùng tự nhập `batch_id`
- Tự động từ `batch_number_series` của Item
- Tự động từ Stock Settings (prefix + ".#####")
- Tự động hash 7 ký tự

**Nguyên tắc:**

- Nếu item `has_expiry_date = True`: `expiry_date = manufacturing_date + shelf_life_in_days`
- Khi xuất, Batch được chọn theo **FEFO (First Expiring First Out)**: lô gần hết hạn xuất trước
- Batch valuation: nếu phương pháp định giá không phải Moving Average, bắt buộc bật `use_batchwise_valuation`

### 2.5. UOM & UOM Conversion — Đơn vị tính

ERPNext hỗ trợ quy đổi giữa các đơn vị tính:

- **UOM Category**: Nhóm đơn vị tính (Khối lượng, Thể tích, Số lượng...)
- **UOM Conversion Detail**: Tỷ lệ quy đổi (1 thùng = 12 cái)

Trong mọi giao dịch kho:

- `qty`: Số lượng theo UOM nhập
- `transfer_qty`: Số lượng theo Stock UOM (tồn kho)
- `conversion_factor`: Hệ số quy đổi

### 2.6. Item Price — Giá hàng hóa

Item Price lưu giá cho từng Item theo từng Price List (bảng giá). Có thể có nhiều mức giá:

- Purchase Price List: giá mua
- Sales Price List: giá bán (bán buôn, bán lẻ...)

### 2.7. Item Default — Thiết lập mặc định

Item Default lưu cấu hình mặc định cho Item theo từng Công ty:

- `default_warehouse`: Kho mặc định
- `default_price_list`: Bảng giá mặc định
- `expense_account`: Tài khoản chi phí
- `income_account`: Tài khoản doanh thu
- `cost_center`: Trung tâm chi phí

## 3. Stock Entry — Chứng từ kho tổng hợp

Stock Entry là chứng từ kho linh hoạt nhất, có thể xử lý hầu hết các loại giao dịch kho. Đây là "con dao Thụy Sĩ" của module Stock.

### 3.1. Cấu trúc Stock Entry

| Trường                    | Loại                                  | Ý nghĩa                                  |
| ------------------------- | ------------------------------------- | ---------------------------------------- |
| `naming_series`           | Select                                | Mã số tự động (mặc định MAT-STE-.YYYY.-) |
| `stock_entry_type`        | Link (Stock Entry Type)               | Loại phiếu nhập/xuat                     |
| `purpose`                 | Select (hidden)                       | Mục đích — lấy từ Stock Entry Type       |
| `company`                 | Link (Company)                        | Công ty                                  |
| `posting_date`            | Date                                  | Ngày hạch toán                           |
| `posting_time`            | Time                                  | Giờ hạch toán                            |
| `set_posting_time`        | Check                                 | Cho phép sửa ngày giờ                    |
| `from_warehouse`          | Link (Warehouse)                      | Kho nguồn mặc định                       |
| `to_warehouse`            | Link (Warehouse)                      | Kho đích mặc định                        |
| `items`                   | Table (Stock Entry Detail)            | Danh sách dòng hàng hóa                  |
| `total_incoming_value`    | Currency                              | Tổng giá trị nhập                        |
| `total_outgoing_value`    | Currency                              | Tổng giá trị xuất                        |
| `value_difference`        | Currency                              | Chênh lệch = incoming - outgoing         |
| `additional_costs`        | Table (Landed Cost Taxes and Charges) | Chi phí bổ sung (cho Repack/Manufacture) |
| `work_order`              | Link (Work Order)                     | Lệnh sản xuất                            |
| `bom_no`                  | Link (BOM)                            | Định mức vật tư                          |
| `fg_completed_qty`        | Float                                 | Số lượng thành phẩm hoàn thành           |
| `process_loss_qty`        | Float                                 | Hao hụt sản xuất                         |
| `process_loss_percentage` | Percent                               | % hao hụt                                |
| `add_to_transit`          | Check                                 | Chuyển qua kho trung chuyển              |
| `apply_putaway_rule`      | Check                                 | Áp dụng quy tắc xếp kho                  |
| `is_opening`              | Select                                | Tồn kho đầu kỳ (No/Yes)                  |
| `pick_list`               | Link (Pick List)                      | Danh sách lấy hàng                       |
| `outgoing_stock_entry`    | Link (Stock Entry)                    | Phiếu chuyển đi (cho chuyển kho 2 bước)  |
| `amended_from`            | Link (Stock Entry)                    | Phiếu sửa đổi từ                         |

**Chi tiết một dòng trong Stock Entry Detail:**

| Trường                      | Ý nghĩa                                                       |
| --------------------------- | ------------------------------------------------------------- |
| `s_warehouse`               | Kho nguồn                                                     |
| `t_warehouse`               | Kho đích                                                      |
| `item_code`                 | Mã hàng                                                       |
| `qty`                       | Số lượng (theo UOM nhập)                                      |
| `transfer_qty`              | Số lượng theo Stock UOM                                       |
| `uom`                       | Đơn vị tính nhập                                              |
| `stock_uom`                 | Đơn vị tính tồn kho                                           |
| `conversion_factor`         | Hệ số quy đổi                                                 |
| `basic_rate`                | Đơn giá cơ bản                                                |
| `basic_amount`              | Thành tiền cơ bản                                             |
| `additional_cost`           | Chi phí bổ sung (phân bổ)                                     |
| `valuation_rate`            | Đơn giá tồn kho = basic_rate + additional_cost / transfer_qty |
| `amount`                    | Tổng tiền = basic_amount + additional_cost                    |
| `serial_no`                 | Số serial (phân cách bằng xuống dòng)                         |
| `batch_no`                  | Số lô                                                         |
| `is_finished_item`          | Là thành phẩm                                                 |
| `is_scrap_item`             | Là phế liệu                                                   |
| `expense_account`           | Tài khoản chi phí (difference account)                        |
| `cost_center`               | Trung tâm chi phí                                             |
| `allow_zero_valuation_rate` | Cho phép định giá bằng 0                                      |
| `against_stock_entry`       | Liên kết với Stock Entry khác (cho transfer)                  |
| `material_request`          | Yêu cầu vật tư gốc                                            |
| `original_item`             | Item gốc (khi dùng Item thay thế)                             |

### 3.2. 8 loại Purpose (Mục đích)

Stock Entry có 8 mục đích, mỗi mục đích có quy tắc xử lý riêng:

| #   | Purpose                                  | s_warehouse | t_warehouse   | Kết nối    | Mô tả                                                |
| --- | ---------------------------------------- | ----------- | ------------- | ---------- | ---------------------------------------------------- |
| 1   | **Material Issue**                       | Bắt buộc    | Không có      | -          | Xuất kho — giảm tồn nguồn, ghi nhận chi phí          |
| 2   | **Material Receipt**                     | Không có    | Bắt buộc      | -          | Nhập kho — tăng tồn đích, định giá incoming          |
| 3   | **Material Transfer**                    | Bắt buộc    | Bắt buộc      | -          | Chuyển kho trực tiếp                                 |
| 4   | **Material Transfer for Manufacture**    | Bắt buộc    | Bắt buộc      | Work Order | Chuyển NVL từ kho chính → WIP                        |
| 5   | **Material Consumption for Manufacture** | Bắt buộc    | Không có      | Work Order | Tiêu hao NVL trong sản xuất (continuous consumption) |
| 6   | **Manufacture**                          | Có (WIP)    | Bắt buộc (FG) | Work Order | Nhập thành phẩm + backflush NVL                      |
| 7   | **Repack**                               | Có          | Có            | -          | Đóng gói lại / Tái chế                               |
| 8   | **Send to Subcontractor**                | Bắt buộc    | Bắt buộc      | PO/SCO     | Chuyển NVL cho nhà thầu phụ                          |

### 3.3. Stock Entry Type — Tùy chỉnh loại phiếu

Stock Entry Type là doctype đơn giản cho phép người dùng tạo thêm loại phiếu tùy chỉnh. Mỗi type chỉ gồm:

- `purpose`: Chọn từ 8 mục đích
- `add_to_transit`: Checkbox (chỉ có ý nghĩa với Material Transfer)

### 3.4. Validate Flow — Quy trình kiểm tra khi submit

Khi người dùng Submit Stock Entry, hệ thống chạy tuần tự các bước kiểm tra:

```
validate()
├── validate_posting_time()       → Kiểm tra ngày giờ hạch toán
├── validate_purpose()            → Kiểm tra purpose hợp lệ
├── validate_item()               → Item tồn tại, là stock_item
├── validate_customer_provided_item()  → Item khách hàng cung cấp
├── set_transfer_qty()            → Tính transfer_qty = qty × conversion_factor
├── validate_uom_is_integer()     → UOM số nguyên
├── validate_warehouse()          → Kho nguồn/đích theo purpose
├── validate_work_order()         → Work Order tồn tại
├── validate_bom()                → BOM tồn tại
├── set_process_loss_qty()        → Tính hao hụt sản xuất
├── validate_purchase_order()     → PO tồn tại (thuê ngoài)
├── validate_subcontracting_order() → SCO tồn tại (thuê ngoài mới)
├── mark_finished_and_scrap_items() → Đánh dấu finished/scrap
├── validate_finished_goods()     → Kiểm tra thành phẩm
├── validate_with_material_request() → Kiểm tra MR
├── validate_batch()              → Batch hợp lệ, hạn sử dụng
├── validate_inspection()         → Quality Inspection
├── validate_fg_completed_qty()   → fg_completed_qty khớp
├── validate_difference_account() → Tài khoản chênh lệch
├── set_job_card_data()           → Dữ liệu từ Job Card
├── validate_serialized_batch()   → Serial/Batch hợp lệ
├── calculate_rate_and_amount()   → Tính đơn giá, thành tiền
└── validate_putaway_capacity()   → Sức chứa theo Putaway Rule
```

### 3.5. Submit Flow — Quy trình ghi sổ

```
on_submit()
├── update_stock_ledger()              → Ghi SLE cho từng dòng
│   ├── Tạo SLE với actual_qty = ± qty
│   ├── Gọi repost_current_voucher → update_entries_after()
│   │   └── Tính stock_value_difference dựa trên valuation method
│   └── Cập nhật Bin (actual_qty, stock_value, valuation_rate)
│
├── update_serial_nos_after_submit()   → Cập nhật Serial No
│   ├── Nhập: tạo Serial No mới, gán warehouse
│   └── Xuất: cập nhật trạng thái Serial No
│
├── update_work_order()                → Cập nhật Work Order
│   ├── produced_qty (Manufacture)
│   ├── material_transferred_for_manufacturing
│   └── update_status() → In Process / Completed
│
├── validate_subcontract_order()       → Kiểm tra SCO (thuê ngoài)
├── update_subcontract_order_supplied_items()  → Cập nhật NVL đã gửi
├── update_subcontracting_order_status()       → Cập nhật trạng thái SCO
├── update_pick_list_status()          → Cập nhật trạng thái Pick List
│
├── make_gl_entries()                  → Tạo GL Entry (nếu perpetual inventory)
│   ├── get_warehouse_account_map()    → Map kho → tài khoản
│   ├── get_stock_ledger_details()     → Lấy SLE của chứng từ này
│   ├── Với mỗi SLE:
│   │   ├── Nợ/Có TK hàng tồn kho (warehouse account)
│   │   └── Có/Nợ TK đối ứng (expense_account / target warehouse account)
│   │   Số tiền = stock_value_difference
│   └── Submit GL Entry
│
├── repost_future_sle_and_gle()        → Đánh giá lại SLE/GLE tương lai
├── update_cost_in_project()           → Cập nhật chi phí Project
├── validate_reserved_serial_no_consumption() → Serial No đã đặt trước
├── update_transferred_qty()           → Update transferred_qty cho chuyển kho
└── update_quality_inspection()        → Cập nhật Quality Inspection
```

### 3.6. Cancel Flow — Quy trình hủy

Khi hủy Stock Entry (Cancel), hệ thống thực hiện các bước đảo ngược:

1. `update_subcontract_order_supplied_items()` — đảo ngược NVL thuê ngoài
2. `update_subcontracting_order_status()` — đảo ngược trạng thái SCO
3. `update_work_order()` — trừ lại produced_qty
4. `update_stock_ledger()` — tạo SLE với `is_cancelled = 1`, actual_qty đảo dấu
5. `make_gl_entries_on_cancel()` — tạo GL Entry đảo ngược (`make_reverse_gl_entries`)
6. `repost_future_sle_and_gle()` — đánh giá lại
7. `update_cost_in_project()` — cập nhật chi phí Project
8. `update_transferred_qty()` — cập nhật transferred_qty
9. `update_quality_inspection()` — cập nhật Quality Inspection
10. `delete_auto_created_batches()` — xóa Batch tự động tạo
11. `delete_linked_stock_entry()` — xóa Stock Entry liên quan (chuyển kho 2 bước)

## 4. Quy trình Nhập kho

### 4.1. Nhập kho mua hàng (Purchase Receipt)

**Quy trình đầy đủ:**

```
Purchase Order (Đơn đặt hàng)
    ↓
Purchase Receipt (Nhập kho) ← Có hạch toán kế toán
    ↓
Purchase Invoice (Hóa đơn mua hàng) ← Có hạch toán
    ↓
Payment Entry (Thanh toán)
```

**Purchase Receipt là chứng từ nhập kho từ nhà cung cấp.** Khi submit, nó:

1. Tạo SLE cho mỗi item — tăng tồn kho
2. Tính incoming rate từ Purchase Order
3. Tạo GL Entry (nếu perpetual inventory):
   - Nợ TK Hàng tồn kho (Warehouse Account) / Có TK Hàng nhận chưa có hóa đơn (SRNB)
4. Cập nhật Bin (actual_qty +, ordered_qty -)

**Hạch toán chi tiết khi nhập kho mua hàng:**

| Nghiệp vụ               | Nợ              | Có                                           |
| ----------------------- | --------------- | -------------------------------------------- |
| Nhập kho thường         | TK Hàng tồn kho | Hàng nhận chưa có hóa đơn                    |
| Nhập kho + Thuế VAT     | TK Hàng tồn kho | Hàng nhận chưa có hóa đơn, Thuế GTGT đầu vào |
| Nhập kho từ công ty con | TK Kho nhận     | TK Kho chuyển                                |

### 4.2. Nhập kho từ sản xuất (Manufacture)

Xem chi tiết ở [Mục 10 — Quy trình Sản xuất & Kho](#10-quy-trinh-san-xuat--kho).

### 4.3. Nhập kho trả lại từ khách hàng (Sales Return)

Xem chi tiết ở [Mục 8 — Quy trình Trả hàng](#8-quy-trinh-tra-hang).

### 4.4. Nhập kho điều chỉnh từ kiểm kê

Xem chi tiết ở [Mục 7 — Quy trình Kiểm kê](#7-quy-trinh-kiem-ke).

### 4.5. Nhập kho đầu kỳ (Opening Stock)

Dùng Stock Reconciliation với `purpose = "Opening Stock"` để nhập tồn kho đầu kỳ. Đây là bước đầu tiên khi triển khai ERPNext.

## 5. Quy trình Xuất kho

### 5.1. Xuất kho bán hàng (Delivery Note)

**Quy trình đầy đủ:**

```
Sales Order (Đơn đặt hàng bán)
    ↓
Delivery Note (Xuất kho bán hàng) ← Có hạch toán
    ↓
Sales Invoice (Hóa đơn bán hàng) ← Có hạch toán chính
    ↓
Payment Entry (Thu tiền)
```

**Delivery Note là chứng từ xuất kho cho khách hàng.** Khi submit, nó:

1. Tạo SLE cho mỗi item — giảm tồn kho
2. Tính outgoing rate (FIFO/MA)
3. Tạo GL Entry (nếu perpetual inventory):
   - Nợ TK Giá vốn hàng bán (COGS) / Có TK Hàng tồn kho
4. Cập nhật Bin (actual_qty -, reserved_qty -)
5. Cập nhật trạng thái Sales Order

**Hạch toán Delivery Note:**

| Nghiệp vụ         | Nợ                         | Có              |
| ----------------- | -------------------------- | --------------- |
| Xuất kho bán hàng | TK Giá vốn hàng bán (COGS) | TK Hàng tồn kho |

### 5.2. Xuất kho cho sản xuất

Xem chi tiết ở [Mục 10](#10-quy-trinh-san-xuat--kho).

### 5.3. Xuất kho trả lại nhà cung cấp (Purchase Return)

Xem chi tiết ở [Mục 8](#8-quy-trinh-tra-hang).

### 5.4. Xuất kho hủy / thanh lý (Material Issue)

Dùng Stock Entry với `purpose = "Material Issue"`:

- `s_warehouse`: bắt buộc — kho xuất
- `t_warehouse`: không có
- Hạch toán: Nợ TK Chi phí (theo expense_account) / Có TK Hàng tồn kho

## 6. Quy trình Chuyển kho

### 6.1. Chuyển kho trực tiếp (1 bước)

Dùng Stock Entry với `purpose = "Material Transfer"`:

- `s_warehouse`: kho nguồn
- `t_warehouse`: kho đích
- Hạch toán: Nợ TK Kho đích / Có TK Kho nguồn

**Ví dụ:** Chuyển 100 sản phẩm từ Kho A sang Kho B:

```
Nợ  TK Hàng tồn kho — Kho B    5.000.000
Có  TK Hàng tồn kho — Kho A    5.000.000
```

### 6.2. Chuyển kho qua kho trung chuyển (2 bước)

Bật `add_to_transit = True` trên Stock Entry Type. Quy trình 2 bước:

**Bước 1 — Gửi hàng:** Stock Entry chuyển từ Kho A → Kho Trung chuyển

- `purpose = "Material Transfer"`
- `add_to_transit = True`
- `s_warehouse` = Kho A, `t_warehouse` = Kho Trung chuyển
- Sau submit: tạo ra 1 Stock Entry khác (outgoing_stock_entry) với `purpose = "Material Transfer"`, chưa submit

**Bước 2 — Nhận hàng:** Stock Entry chuyển từ Kho Trung chuyển → Kho B

- Người dùng nhập `per_transferred` (%) và submit
- Khi submit: cập nhật transferred_qty

**Hạch toán 2 bước:**

- Bước 1: Nợ TK Kho Trung chuyển / Có TK Kho A
- Bước 2: Nợ TK Kho B / Có TK Kho Trung chuyển

## 7. Quy trình Kiểm kê (Stock Reconciliation)

### 7.1. Tổng quan

Stock Reconciliation dùng để điều chỉnh số liệu tồn kho giữa hệ thống và thực tế, hoặc nhập tồn kho đầu kỳ.

**Có 2 mục đích:**

1. **Opening Stock:** Thiết lập tồn kho đầu kỳ (khi mới triển khai)
2. **Stock Reconciliation:** Điều chỉnh tồn kho định kỳ

### 7.2. Cấu trúc Stock Reconciliation

| Trường                | Ý nghĩa                                               |
| --------------------- | ----------------------------------------------------- |
| `purpose`             | Opening Stock / Stock Reconciliation                  |
| `items` (child table) | Danh sách item cần kiểm kê                            |
| `expense_account`     | Tài khoản chênh lệch (Stock Adjustment Account)       |
| `cost_center`         | Trung tâm chi phí                                     |
| `difference_amount`   | Tổng chênh lệch (read-only, auto-calculated)          |
| `scan_mode`           | Chế độ quét — khi bật, không tự động lấy tồn hiện tại |

**Chi tiết một dòng kiểm kê (Stock Reconciliation Item):**

| Trường                   | Ý nghĩa                                   |
| ------------------------ | ----------------------------------------- |
| `item_code`              | Mã hàng                                   |
| `warehouse`              | Mã kho                                    |
| `qty`                    | Số lượng thực tế (người dùng nhập)        |
| `valuation_rate`         | Đơn giá thực tế                           |
| `batch_no`               | Số lô (nếu có)                            |
| `serial_no`              | Số serial (nếu có)                        |
| `current_qty`            | Tồn kho hiện tại (read-only, auto-filled) |
| `current_valuation_rate` | Đơn giá hiện tại (read-only, auto-filled) |
| `current_amount`         | Giá trị hiện tại (read-only)              |

### 7.3. Quy trình kiểm kê

**Bước 1 — Tạo Stock Reconciliation mới**

- Chọn `purpose` = "Stock Reconciliation"
- Chọn Company, Expense Account, Cost Center
- Thêm các dòng item cần kiểm kê
- Hệ thống tự động điền `current_qty`, `current_valuation_rate`

**Bước 2 — Nhập số liệu thực tế**

- Nhập `qty` = số lượng thực tế đếm được
- Nhập `valuation_rate` nếu cần thay đổi giá
- Nhập `batch_no`, `serial_no` nếu quản lý theo lô/serial

**Bước 3 — Submit**

- Hệ thống tự động **xóa các dòng không có thay đổi** (`remove_items_with_no_change()`)
- Nếu tất cả dòng đều không thay đổi → báo lỗi `EmptyStockReconciliationItemsError`

**Bước 4 — Hệ thống xử lý**

- Với item không serial: tạo SLE với `qty_after_transaction` đúng bằng số kiểm kê
- Với item serial: xuất serial cũ → nhập serial mới
- Với item batch: tương tự 2 bước

### 7.4. Hạch toán kiểm kê

Khi `qty_thuc_te > qty_he_thong` (thừa):

```
Nợ  TK Hàng tồn kho (Asset)    [chênh lệch giá trị]
Có  TK Điều chỉnh kho (P&L)    [chênh lệch giá trị]
```

Khi `qty_thuc_te < qty_he_thong` (thiếu):

```
Nợ  TK Điều chỉnh kho (P&L)    [chênh lệch giá trị]
Có  TK Hàng tồn kho (Asset)    [chênh lệch giá trị]
```

### 7.5. Lưu ý khi kiểm kê

- **Số lượng lớn (>100 dòng):** Submit/Cancel được enqueue vào background job
- **Inventory Dimensions:** Nếu dùng, chỉ Opening Stock mới hoạt động — không thể điều chỉnh số lượng
- **Không thể duplicate item + warehouse** trong cùng một phiếu kiểm kê
- **Batch được tự động tạo** nếu chưa tồn tại
- **Số lượng phải >= 0** (không cho phép âm)

## 8. Quy trình Trả hàng (Returns)

### 8.1. Tổng quan

ERPNext hỗ trợ 2 loại trả hàng:

1. **Trả hàng mua (Purchase Return):** Trả lại hàng cho nhà cung cấp — dùng Purchase Receipt với `is_return = 1`
2. **Trả hàng bán (Sales Return):** Khách hàng trả lại hàng — dùng Delivery Note với `is_return = 1`

Cả 2 đều dùng chung module xử lý tại `controllers/sales_and_purchase_return.py`.

### 8.2. Nguyên tắc chung

Khi tạo chứng từ trả hàng:

- `is_return = 1` (đánh dấu là phiếu trả)
- `return_against` = số chứng từ gốc
- Số lượng = -1 × số lượng gốc (đã trừ số lượng đã trả trước đó)
- Giá không được vượt quá giá gốc (trừ trường hợp Moving Average)
- Batch/Serial No phải giống với chứng từ gốc
- **StockOverReturnError:** Không thể trả nhiều hơn số đã nhập/xuất trừ đi số đã trả

### 8.3. Trả hàng nhà cung cấp (Purchase Return)

**Cách tạo:**

- Từ Purchase Receipt gốc → nút "Create" → "Return"
- Hoặc tạo Purchase Receipt mới với `is_return = 1`, `return_against` = PR gốc

**Hạch toán khi submit Purchase Return:**

```
Nợ  TK Hàng nhận chưa có hóa đơn (SRNB)  [số tiền]
Có  TK Hàng tồn kho                       [số tiền]
```

**Tác động:**

- SLE: actual_qty âm (-) tại kho — hàng giảm (trả về NCC)
- Bin: actual_qty giảm
- Cập nhật `returned_qty` trên Purchase Order Item và Purchase Receipt Item gốc
- Cập nhật `per_returned` trên Purchase Receipt gốc

### 8.4. Trả hàng khách hàng (Sales Return)

**Cách tạo:**

- Từ Delivery Note gốc → nút "Create" → "Return"
- Hoặc tạo Delivery Note mới với `is_return = 1`, `return_against` = DN gốc

**Hạch toán khi submit Sales Return:**

```
Nợ  TK Hàng tồn kho                       [số tiền]
Có  TK Giá vốn hàng bán (COGS)           [số tiền]
```

**Automatic Credit Note:**
Nếu Delivery Note có `issue_credit_note = True`, hệ thống tự động tạo và submit Sales Invoice (Credit Note) khi submit Delivery Note return:

- Đảo ngược doanh thu và thuế
- Ghi nhận công nợ giảm

**Tác động:**

- SLE: actual_qty dương (+) tại kho — hàng về lại kho
- Bin: actual_qty tăng
- Cập nhật `returned_qty` trên Sales Order Item và Delivery Note Item gốc
- Nếu có `default_warehouse_for_sales_return` (Company setting), hàng về kho này thay vì kho gốc

## 9. Quy trình Thuê ngoài (Subcontracting)

### 9.1. Tổng quan

Subcontracting (Thuê ngoài/Gia công) là quy trình doanh nghiệp gửi nguyên vật liệu cho đối tác gia công và nhận lại thành phẩm. ERPNext hỗ trợ 2 luồng:

- **Luồng cũ (is_old_subcontracting_flow = True):** PO → Stock Entry → Purchase Receipt
- **Luồng mới (mặc định):** PO → Subcontracting Order (SCO) → Stock Entry → Subcontracting Receipt (SCR)

### 9.2. Doctype trong module Subcontracting

| Doctype                              | Vai trò                                     |
| ------------------------------------ | ------------------------------------------- |
| **Subcontracting Order (SCO)**       | Đơn hàng gia công — trung tâm của quy trình |
| Subcontracting Order Item            | Chi tiết thành phẩm cần gia công            |
| Subcontracting Order Service Item    | Dịch vụ gia công (item phi kho)             |
| Subcontracting Order Supplied Item   | Nguyên vật liệu đã cấp cho đối tác          |
| **Subcontracting Receipt (SCR)**     | Phiếu nhận thành phẩm gia công              |
| Subcontracting Receipt Item          | Chi tiết thành phẩm nhận về                 |
| Subcontracting Receipt Supplied Item | Nguyên vật liệu đã tiêu hao                 |

### 9.3. Quy trình đầy đủ

```
                     Purchase Order (is_subcontracted = True)
                               |
                               ↓
                     Subcontracting Order (SCO)
                        /                \
                       ↓                  ↓
           Stock Entry                 Subcontracting
      (Send to Subcontractor)           Receipt (SCR)
       — gửi NVL cho đối tác            — nhận thành phẩm
                       \                  /
                        ↓                ↓
                     Hoàn tất — Cập nhật trạng thái SCO
```

**Bước 1 — Cấu hình:**

- Item thành phẩm: `is_sub_contracted_item = 1`, có `default_bom`
- BOM chứa danh sách NVL cần cấp

**Bước 2 — Purchase Order:**

- Bật `is_subcontracted = True`
- Chọn service item (non-stock), chỉ định `fg_item` và `fg_item_qty`

**Bước 3 — Subcontracting Order (từ PO):**

- Hệ thống tự động map service items thành SCO items
- Tính toán NVL cần cấp từ BOM
- Khi submit SCO → cập nhật `ordered_qty`, `reserved_qty`

**Bước 4 — Stock Entry (Send to Subcontractor):**

- `purpose = "Send to Subcontractor"`
- `s_warehouse` = kho NVL của công ty
- `t_warehouse` = supplier warehouse (kho nhà thầu)
- Khi submit:
  - Cập nhật `supplied_items` trong SCO
  - Cập nhật trạng thái SCO: "Partial Material Transferred" / "Material Transferred"

**Bước 5 — Subcontracting Receipt:**

- Nhập thành phẩm từ nhà thầu
- Khi submit:
  - Tăng stock thành phẩm tại kho nhập
  - Giảm stock NVL tại Supplier Warehouse (backflush)
  - Cập nhật trạng thái SCO: "Partially Received" / "Completed"
  - Tạo GL entries

**Bước 6 (tùy chọn) — Trả NVL thừa:**

- Dùng Stock Entry `purpose = "Material Transfer"` với `is_return = 1` để nhận lại NVL thừa

### 9.4. Backflush trong Subcontracting

**Chế độ BOM (mặc định):** Khi tạo SCR, ERPNext tự động tính NVL tiêu hao = BOM × số lượng thành phẩm.

**Chế độ Material Transferred:** Khi tạo SCR, consumed qty = số NVL đã chuyển, phần dư được backflush tự động.

### 9.5. Các trạng thái của Subcontracting Order

| Trạng thái                   | Ý nghĩa                           |
| ---------------------------- | --------------------------------- |
| Draft → Open                 | Khi SCO được submit               |
| Partial Material Transferred | Đã chuyển một phần NVL            |
| Material Transferred         | Đã chuyển đủ NVL                  |
| Partially Received           | Đã nhận một phần thành phẩm       |
| Completed                    | Đã nhận đủ (per_received >= 100%) |
| Closed                       | Nhận đủ + NVL thừa đã trả         |
| Cancelled                    | Đã hủy                            |

## 10. Quy trình Sản xuất & Kho

### 10.1. Tổng quan

Quy trình sản xuất kết nối chặt chẽ với kho qua 3 loại Stock Entry và Work Order.

**Vòng đời sản xuất:**

```
BOM (Bill of Materials) — định mức vật tư
    ↓
Work Order (Lệnh sản xuất)
    ↓
[Pick List] — chuẩn bị NVL (tùy chọn)
    ↓
Stock Entry "Material Transfer for Manufacture" — chuyển NVL → WIP
    ↓
Stock Entry "Manufacture" — nhập thành phẩm + backflush NVL
    ↓
[Stock Entry "Material Consumption for Manufacture"] — tiêu hao bổ sung
```

### 10.2. Work Order (Lệnh sản xuất)

**Các trạng thái:**

| Trạng thái       | Điều kiện                                      |
| ---------------- | ---------------------------------------------- |
| Draft            | Chưa submit                                    |
| Not Started      | Đã submit, chưa chuyển NVL                     |
| In Process       | Đã chuyển NVL hoặc skip_transfer + có sản phẩm |
| Completed        | produced_qty + process_loss_qty >= qty         |
| Stopped / Closed | Thiết lập thủ công                             |
| Cancelled        | Đã hủy                                         |

**Các trường quan trọng liên quan kho:**

| Trường                                   | Ý nghĩa                                      |
| ---------------------------------------- | -------------------------------------------- |
| `wip_warehouse`                          | Kho WIP — chứa NVL đã xuất cho sản xuất      |
| `fg_warehouse`                           | Kho thành phẩm — nơi nhập SP sau SX          |
| `source_warehouse`                       | Kho nguồn NVL mặc định                       |
| `scrap_warehouse`                        | Kho phế liệu                                 |
| `skip_transfer`                          | Bỏ qua bước chuyển NVL — backflush trực tiếp |
| `transfer_material_against`              | "Work Order" hoặc "Job Card"                 |
| `material_transferred_for_manufacturing` | Số NVL đã chuyển (tự động)                   |
| `produced_qty`                           | Số thành phẩm đã SX (tự động)                |
| `process_loss_qty`                       | Hao hụt SX                                   |

### 10.3. Stock Entry "Material Transfer for Manufacture"

Chuyển nguyên vật liệu từ kho chính → kho WIP.

- `s_warehouse` = source_warehouse
- `t_warehouse` = wip_warehouse
- Gắn với Work Order

**Hạch toán:**

```
Nợ  TK Hàng tồn kho — WIP Warehouse    [giá trị NVL]
Có  TK Hàng tồn kho — Source Warehouse  [giá trị NVL]
```

### 10.4. Stock Entry "Manufacture"

Nhập thành phẩm và đồng thời trừ NVL (backflush). Đây là bước quan trọng nhất.

**Cách tính giá vốn thành phẩm:**

```
Giá vốn TP = (Tổng chi phí NVL - Giá trị phế liệu) / Số lượng thành phẩm
```

**Các thành phần trong Stock Entry Manufacture:**

1. **Raw materials:** s_warehouse = WIP, t_warehouse = None — NVL tiêu hao
2. **Finished goods:** s_warehouse = None, t_warehouse = FG — thành phẩm
3. **Scrap items:** s_warehouse = None, t_warehouse = Scrap — phế liệu
4. **Process loss:** fg_completed_qty - actual_fg_qty = process_loss_qty

**Hạch toán:**

```
Nợ  TK Hàng tồn kho — FG Warehouse         [giá trị thành phẩm]
Nợ  TK Hàng tồn kho — Scrap Warehouse      [giá trị phế liệu] (nếu có)
Có  TK Hàng tồn kho — WIP Warehouse         [giá trị NVL tiêu hao]
```

### 10.5. Backflush — Cơ chế tự động trừ NVL

**Chế độ 1 — "Material Transferred for Manufacture" (mặc định):**

- NVL được chuyển từ Source → WIP trước
- Khi Manufacture: ERPNext lấy NVL đang có trong WIP và tính số cần tiêu hao
- Công thức: `qty = (transferred_qty × fg_completed_qty) / remaining_qty_to_produce`

**Chế độ 2 — "BOM" (khi material_consumption = True):**

- Không cần chuyển NVL trước
- Khi Manufacture: ERPNext đọc BOM và trừ NVL trực tiếp từ Source Warehouse

### 10.6. Stock Entry "Material Consumption for Manufacture"

Dùng khi cần tiêu hao NVL bổ sung ngoài backflush (Continuous Material Consumption).

- `s_warehouse` bắt buộc (kho lấy NVL)
- `t_warehouse` = None
- Yêu cầu Manufacturing Settings.material_consumption = 1

## 11. Pick List — Chuẩn bị hàng

### 11.1. Tổng quan

Pick List là công cụ chuẩn bị hàng trước khi xuất kho, giúp xác định chính xác vị trí và số lượng cần lấy.

**Có 2 mục đích:**

1. **Delivery:** Chuẩn bị hàng cho Sales Order → tạo Delivery Note
2. **Material Transfer for Manufacture:** Chuẩn bị NVL cho sản xuất → tạo Stock Entry

### 11.2. Chức năng tự động xác định vị trí (set_item_locations)

Hàm `set_item_locations()` tự động:

1. Gom nhóm các item giống nhau
2. Xác định vị trí trong kho cho từng item
3. Với Serialized item: lấy Serial No theo FIFO
4. Với Batched item: lấy Batch theo FEFO (hạn gần nhất)
5. Với Serial + Batch: kết hợp cả 2

### 11.3. Tạo Stock Entry / Delivery Note từ Pick List

Pick List có thể tạo:

- Stock Entry với `purpose = "Material Transfer for Manufacture"` (cho sản xuất)
- Delivery Note (cho bán hàng)

## 12. Landed Cost — Phân bổ chi phí

### 12.1. Tổng quan

Landed Cost Voucher dùng để phân bổ các chi phí phát sinh (vận chuyển, bảo hiểm, hải quan...) vào giá trị hàng tồn kho.

### 12.2. Quy trình

1. Tạo Landed Cost Voucher
2. Chọn Purchase Receipt cần phân bổ
3. Nhập các khoản chi phí (vận chuyển, thuế nhập khẩu...)
4. Chọn phương thức phân bổ (theo số lượng, theo giá trị, theo thể tích...)
5. Submit → hệ thống cập nhật lại valuation_rate của item trong Purchase Receipt

### 12.3. Hạch toán

Khi submit Landed Cost Voucher:

```
Nợ  TK Hàng tồn kho (tăng giá trị)    [số chi phí phân bổ]
Có  TK Chi phí (vận chuyển, hải quan...)  [số chi phí phân bổ]
```

## 13. Kết nối với Kế toán

### 13.1. Luồng dữ liệu Kho → Kế toán

Mối quan hệ giữa Kho và Kế toán dựa trên luồng dữ liệu sau:

```
Stock Entry / Delivery Note / Purchase Receipt Submit
    ↓
Stock Ledger Entry (SLE) — ghi nhận thay đổi số lượng và giá trị
    ↓
stock_value_difference — chênh lệch giá trị (là cầu nối)
    ↓
StockController.get_gl_entries()
    ↓
General Ledger Entry (GL Entry) — bút toán kép
    ↓
Cập nhật số dư tài khoản — ảnh hưởng Bảng cân đối kế toán & P&L
```

### 13.2. Nguyên tắc hạch toán Perpetual Inventory

Khi bật Perpetual Inventory ở Company:

| Loại giao dịch    | Nợ                      | Có                      | Số tiền                |
| ----------------- | ----------------------- | ----------------------- | ---------------------- |
| Nhập kho mua hàng | TK Hàng tồn kho         | TK Hàng nhận chưa có HĐ | stock_value_difference |
| Xuất kho bán hàng | TK Giá vốn (COGS)       | TK Hàng tồn kho         | stock_value_difference |
| Chuyển kho        | TK Kho đích             | TK Kho nguồn            | stock_value_difference |
| Nhập kho SX (TP)  | TK Kho thành phẩm       | TK Kho WIP              | stock_value_difference |
| Kiểm kê (thiếu)   | TK Điều chỉnh kho       | TK Hàng tồn kho         | difference_amount      |
| Kiểm kê (thừa)    | TK Hàng tồn kho         | TK Điều chỉnh kho       | difference_amount      |
| Trả hàng NCC      | TK Hàng nhận chưa có HĐ | TK Hàng tồn kho         | stock_value_difference |
| Trả hàng KH       | TK Hàng tồn kho         | TK Giá vốn (COGS)       | stock_value_difference |

### 13.3. StockController.get_gl_entries() — Chi tiết

Phương thức `get_gl_entries()` trong `controllers/stock_controller.py`:

1. Gọi `get_stock_ledger_details()` để lấy tất cả SLE của chứng từ hiện tại
2. Nhóm SLE theo `voucher_detail_no`
3. Với mỗi SLE, lấy warehouse_account từ map `warehouse_account_map`
4. Tạo 2 GL Entry cho mỗi SLE:
   - GL1: Nợ/Có TK Hàng tồn kho (warehouse account) — số tiền = stock_value_difference
   - GL2: Có/Nợ TK đối ứng (expense_account hoặc target warehouse account)
5. Đảm bảo tổng Nợ = tổng Có

### 13.4. Các tài khoản quan trọng cho kho

| Tài khoản                       | Vai trò                                               |
| ------------------------------- | ----------------------------------------------------- |
| `default_inventory_account`     | Tài khoản hàng tồn kho (Asset)                        |
| `stock_adjustment_account`      | Tài khoản điều chỉnh kho (P&L) — dùng trong kiểm kê   |
| `stock_received_but_not_billed` | Hàng nhận chưa có hóa đơn (Liability) — dùng trong PR |
| `default_expense_account`       | Tài khoản chi phí mặc định / Giá vốn (COGS)           |
| `exchange_gain_loss_account`    | Lãi/lỗ tỷ giá cho giao dịch kho                       |

## 14. Quản lý định giá lại (Repost & Valuation)

### 14.1. Khi nào cần Repost?

Repost Item Valuation cần thiết khi:

- Giá của một giao dịch nhập kho trước đó thay đổi (ví dụ: Landed Cost được thêm vào)
- Phát hiện sai lệch giá trị tồn kho
- Sau khi hủy chứng từ cũ ảnh hưởng đến định giá FIFO/MA

### 14.2. Cách thức hoạt động

Repost Item Valuation — `doctype/repost_item_valuation/repost_item_valuation.py`:

**Bước 1 — Repost SLE:**

- Gọi `repost_future_sle()` từ `stock_ledger.py`
- Xử lý lại tất cả SLE từ thời điểm được chỉ định
- Tính lại `stock_value_difference` cho từng SLE

**Bước 2 — Repost GL Entry:**

- Gọi `repost_gle_for_stock_vouchers()` từ `accounts/utils.py`
- Với mỗi chứng từ bị ảnh hưởng:
  1. Lấy GL Entry hiện tại
  2. Tính GL Entry kỳ vọng (gọi `get_gl_entries()`)
  3. So sánh — nếu khác: xóa cũ, tạo mới

**2 chế độ repost:**

1. **Transaction:** Dựa trên một chứng từ cụ thể
2. **Item and Warehouse:** Repost toàn bộ lịch sử của item-warehouse

### 14.3. Stock Reposting Settings

Cấu hình trong Stock Settings:

- Tự động repost khi phát hiện sai lệch
- Giới hạn thời gian / số lượng cho repost hàng loạt

## 15. Stock Settings & Cấu hình

### 15.1. Stock Settings

**Truy cập:** Stock → Settings → Stock Settings

| Trường                  | Ý nghĩa                                               |
| ----------------------- | ----------------------------------------------------- |
| `item_naming_by`        | Cách đặt tên Item (Item Code / Naming Series)         |
| `default_warehouse`     | Kho mặc định cho toàn hệ thống                        |
| `allow_negative_stock`  | Cho phép tồn kho âm                                   |
| `auto_create_batch`     | Tự động tạo Batch khi cần                             |
| `auto_create_serial_no` | Tự động tạo Serial No                                 |
| `sample_quantity`       | Số lượng mẫu cho Quality Inspection                   |
| `valuation_method`      | Phương pháp định giá mặc định (FIFO / Moving Average) |
| `stock_uom`             | Đơn vị tính tồn kho mặc định                          |

### 15.2. Company Settings (liên quan đến kho)

| Trường                               | Ý nghĩa                                      |
| ------------------------------------ | -------------------------------------------- |
| `enable_perpetual_inventory`         | Bật kiểm kê vĩnh viễn (tạo GL Entry tự động) |
| `default_inventory_account`          | TK hàng tồn kho mặc định                     |
| `stock_adjustment_account`           | TK điều chỉnh kho                            |
| `stock_received_but_not_billed`      | TK hàng nhận chưa có hóa đơn                 |
| `default_expense_account`            | TK chi phí / giá vốn                         |
| `default_warehouse_for_sales_return` | Kho mặc định cho hàng trả lại                |

### 15.3. Buying Settings (liên quan đến kho)

- `backflush_raw_materials_of_subcontract_based_on`: BOM / Material Transferred

### 15.4. Manufacturing Settings (liên quan đến kho)

- `backflush_raw_materials_based_on`: Material Transferred / BOM
- `material_consumption`: Bật tiêu hao NVL liên tục
- `default_wip_warehouse`, `default_fg_warehouse`, `default_scrap_warehouse`
- `overproduction_percentage_for_work_order`: % cho phép SX vượt
- `job_card_excess_transfer`: Cho phép chuyển NVL vượt trong Job Card

## 16. Báo cáo Kho

### 16.1. Báo cáo tồn kho

| Tên báo cáo                      | Mô tả                                                   |
| -------------------------------- | ------------------------------------------------------- |
| **Stock Ledger**                 | Sổ cái kho — lịch sử giao dịch của từng item-warehouse  |
| **Stock Balance**                | Tồn kho hiện tại — số lượng, giá trị, đơn giá           |
| **Stock Projected Qty**          | Tồn kho dự kiến = actual + ordered - reserved - planned |
| **Stock Ageing**                 | Phân tích tuổi tồn kho                                  |
| **Stock Analytics**              | Phân tích tồn kho đa chiều                              |
| **Item Balance**                 | Số dư hàng hóa                                          |
| **Item Shortage Report**         | Hàng sắp hết (dưới reorder level)                       |
| **Warehouse Wise Stock Balance** | Tồn kho theo từng kho                                   |
| **Total Stock Summary**          | Tổng hợp giá trị tồn kho                                |

### 16.2. Báo cáo Serial No & Batch

| Tên báo cáo                    | Mô tả                                             |
| ------------------------------ | ------------------------------------------------- |
| **Serial No Ledger**           | Sổ cái Serial No                                  |
| **Serial No Status**           | Trạng thái từng Serial (Active/Delivered/Expired) |
| **Serial No Warranty Expiry**  | Serial sắp hết hạn bảo hành                       |
| **Batch Item Expiry Status**   | Trạng thái hạn dùng của Batch                     |
| **Batch Wise Balance History** | Lịch sử tồn kho theo Batch                        |

### 16.3. Báo cáo định giá

| Tên báo cáo                             | Mô tả                              |
| --------------------------------------- | ---------------------------------- |
| **FIFO Queue vs Qty After Transaction** | Kiểm tra FIFO queue                |
| **Incorrect Stock Value Report**        | Phát hiện sai lệch giá trị tồn kho |
| **Incorrect Serial No Valuation**       | Phát hiện Serial No định giá sai   |

### 16.4. Báo cáo xu hướng

| Tên báo cáo                                                         | Mô tả              |
| ------------------------------------------------------------------- | ------------------ |
| **Delivery Note Trends**                                            | Xu hướng xuất kho  |
| **Purchase Receipt Trends**                                         | Xu hướng nhập kho  |
| **Material Requests for which Supplier Quotations are not Created** | MR chưa có báo giá |

---

## Phụ lục

### A. Bảng ánh xạ Doctype — Nghiệp vụ

| Doctype                | Nghiệp vụ                          | Module         |
| ---------------------- | ---------------------------------- | -------------- |
| Stock Entry            | Nhập, xuất, chuyển, SX, thuê ngoài | Stock          |
| Delivery Note          | Xuất bán                           | Stock          |
| Purchase Receipt       | Nhập mua                           | Stock          |
| Stock Reconciliation   | Kiểm kê                            | Stock          |
| Material Request       | Yêu cầu vật tư                     | Stock          |
| Pick List              | Chuẩn bị hàng                      | Stock          |
| Packing Slip           | Đóng gói                           | Stock          |
| Shipment               | Vận chuyển                         | Stock          |
| Work Order             | Lệnh sản xuất                      | Manufacturing  |
| Subcontracting Order   | Đơn gia công                       | Subcontracting |
| Subcontracting Receipt | Nhận hàng gia công                 | Subcontracting |
| Landed Cost Voucher    | Phân bổ chi phí                    | Stock          |
| Purchase Order         | Đơn mua hàng                       | Buying         |
| Sales Order            | Đơn bán hàng                       | Selling        |
| Repost Item Valuation  | Định giá lại                       | Stock          |
| Quality Inspection     | Kiểm tra chất lượng                | Stock          |

### B. Luồng dữ liệu xuyên suốt các module

```
Material Request (Stock) ──→ Purchase Order (Buying)
    ↑ (reorder)                    ↓
                              Purchase Receipt (Stock) ──→ GL Entry (Accounts)
                                   ↓
                              Purchase Invoice (Accounts) ──→ GL Entry
                                   ↓
                              Payment Entry (Accounts)

Sales Order (Selling) ──→ Delivery Note (Stock) ──→ GL Entry
    ↓                            ↓
    │                       Sales Invoice (Accounts) ──→ GL Entry
    │                            ↓
    │                       Payment Entry (Accounts)
    ↓
Pick List (Stock) ──→ Delivery Note

Work Order (Manufacturing) ──→ Stock Entry "Transfer for Mfg" (Stock) ──→ GL Entry
    ↓                            ↓
    │                       Stock Entry "Manufacture" (Stock) ──→ GL Entry
    ↓
Job Card (Manufacturing)

BOM (Manufacturing) ──→ Work Order
    ↓
Stock Entry "Repack" (Stock)

Purchase Order (Subcontracted) ──→ Subcontracting Order (Subcontracting)
    ↓                                     ↓
Stock Entry "Send to Subcontractor" → Subcontracting Receipt → GL Entry

Stock Reconciliation (Stock) ──→ GL Entry
    ↓
Repost Item Valuation (Stock) ──→ Repost SLE + GL
```

### C. Các Role (Phân quyền)

| Role                  | Mô tả              | Quyền hạn                         |
| --------------------- | ------------------ | --------------------------------- |
| Stock Manager         | Quản lý kho        | Đầy đủ (tạo, submit, hủy, sửa)    |
| Stock User            | Nhân viên kho      | Tạo & submit chứng từ (không hủy) |
| Item Manager          | Quản lý hàng hóa   | CRUD Item, BOM                    |
| Quality Manager       | Quản lý chất lượng | Quality Inspection                |
| Manufacturing Manager | Quản lý SX         | Work Order, BOM                   |
| Manufacturing User    | Nhân viên SX       | Tạo Job Card, Stock Entry SX      |
| Purchase Manager      | Quản lý mua hàng   | PO, PR, PI                        |
| Purchase User         | Nhân viên mua hàng | Tạo PO, PR                        |
| Sales Manager         | Quản lý bán hàng   | SO, DN, SI                        |
| Sales User            | Nhân viên bán hàng | Tạo SO, DN                        |

---

> **Tài liệu tham khảo:** Mã nguồn ERPNext tại `erpnext/stock/`, `erpnext/controllers/`, `erpnext/accounts/`, `erpnext/manufacturing/`, `erpnext/subcontracting/`
> **Phiên bản tài liệu:** 1.0 — 2026-07-01
