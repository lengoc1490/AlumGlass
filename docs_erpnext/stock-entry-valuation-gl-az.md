\# Stock Entry — Giá trị kho \& GL Entry từ A–Z



> \*\*Ngôn ngữ:\*\* Tiếng Việt

> \*\*Mã nguồn tham chiếu:\*\* ERPNext v15 tại `\~/myfrappe/apps/erpnext`

> \*\*Mục đích:\*\* Tài liệu chi tiết — giải thích \*từ A đến Z\* luồng tạo Stock Entry, cách tính giá trị kho (valuation), cách sinh Stock Ledger Entry (SLE) và GL Entry (GL), đặc biệt là vai trò của \*\*Additional Costs\*\* — chi phí tăng thêm có đi thẳng vào giá trị kho của `t\_warehouse` hay không.

> \*\*Đối tượng:\*\* Lập trình viên Frappe/ERPNext, kế toán, tư vấn triển khai.



\---



\## Mục lục



1\. \[Tổng quan — Stock Entry là gì](#1-tổng-quan--stock-entry-là-gì)

2\. \[Bảng field chính của Stock Entry \& Stock Entry Detail](#2-bảng-field-chính-của-stock-entry--stock-entry-detail)

3\. \[Các Purpose (mục đích) nghiệp vụ chuẩn](#3-các-purpose-mục-đích-nghiệp-vụ-chuẩn)

4\. \[Luồng tổng thể khi Submit](#4-luồng-tổng-thể-khi-submit)

5\. \[Bước 0 — Tính giá trị trên Stock Entry (`calculate\_rate\_and\_amount`)](#5-bước-0--tính-giá-trị-trên-stock-entry-calculate\_rate\_and\_amount)

6\. \[Bước 1 — Tạo Stock Ledger Entry](#6-bước-1--tạo-stock-ledger-entry)

7\. \[Bước 1.5 — Valuation Engine — tính lại giá trị kho khi ghi SLE](#7-bước-15--valuation-engine--tính-lại-giá-trị-kho-khi-ghi-sle)

8\. \[Bước 2 — Tạo GL Entry](#8-bước-2--tạo-gl-entry)

9\. \[Additional Costs — phân tích chuyên sâu](#9-additional-costs--phân-tích-chuyên-sâu)

10\. \[Ví dụ nghiệp vụ có số liệu](#10-ví-dụ-nghiệp-vụ-có-số-liệu)

11\. \[Cơ chế Repost (định giá lại) \& ngoại lệ](#11-cơ-chế-repost-định-giá-lại--ngoại-lệ)

12\. \[Custom Override tại các app nội bộ](#12-custom-override-tại-các-app-nội-bộ)

13\. \[Checklist \& quy trình nghiệp vụ chuẩn](#13-checklist--quy-trình-nghiệp-vụ-chuẩn)

14\. \[Lưu ý kế toán \& sai lầm thường gặp](#14-lưu-ý-kế-toán--sai-lầm-thường-gặp)

15\. \[Q\&A — Giải thích chuyên sâu](#15-qa--giải-thích-chuyên-sâu)

16\. \[Material Transfer + Additional Cost — Tình huống \& Hạch toán chuẩn (4 tài khoản)](#16-material-transfer-additional-cost-tình-huống-hạch-toán-chuẩn-4-tài-khoản)

17\. \[Nghiên cứu case thực tế — NXK-2608-0009-1 (frappe-dev nxc16)](#17-nghiên-cứu-case-thực-tế--nxk-2608-0009-1-frappe-dev-nxc16)

18\. \[Kết luận chuẩn nghiệp vụ kế toán — A hay B? \& phương án xử lý](#18-kết-luận-chuẩn-nghiệp-vụ-kế-toán--a-hay-b-phương-án-xử-lý)



\---



\## 1. Tổng quan — Stock Entry là gì



\*\*Stock Entry\*\* là chứng từ kho tổng hợp trong ERPNext, dùng để ghi nhận \*\*mọi sự biến động kho\*\*:

\- Nhập kho (Material Receipt)

\- Xuất kho (Material Issue)

\- Chuyển kho nội bộ (Material Transfer)

\- Chuyển kho để sản xuất / nhập thành phẩm (Material Transfer for Manufacture, Manufacture)

\- Đóng gói lại (Repack)

\- Gửi nguyên vật liệu thuê ngoài (Send to Subcontractor)

\- Tiêu hao vật tư (Material Consumption for Manufacture)



Mỗi Stock Entry khi submit tạo ra \*\*2 dòng dữ liệu hệ thống\*\*:



| Tầng | Doctype | Vai trò |

|---|---|---|

| Tồn kho (định lượng) | `Stock Ledger Entry` (SLE) | Ghi nhận thay đổi \*\*số lượng\*\* và \*\*giá trị\*\* tồn kho theo từng item + warehouse |

| Kế toán (định giá) | `GL Entry` (GL) | Ghi nhận \*\*bút toán\*\* vào các tài khoản (kho, chi phí...) — chỉ khi công ty bật \*\*Perpetual Inventory\*\* |



\*\*File nguồn chính:\*\*



| File | Vai trò |

|---|---|

| `erpnext/stock/doctype/stock\_entry/stock\_entry.py` | Class `StockEntry` — validate, tính giá trị, tạo SLE/GL |

| `erpnext/stock/stock\_ledger.py` | Valuation engine — tính lại giá trị khi mỗi SLE ghi |

| `erpnext/stock/valuation.py` | Thuật toán FIFO/LIFO (bin queue) |

| `erpnext/controllers/stock\_controller.py` | Class cha — sinh GL Entry chung cho mọi chứng từ kho |

| `erpnext/stock/utils.py` | Hàm lấy giá nhập, phương pháp định giá |

| `erpnext/controllers/taxes\_and\_totals.py` | `init\_landed\_taxes\_and\_totals` — chuẩn hoá additional\_costs (tỷ giá, base\_amount) |



\---



\## 2. Bảng field chính của Stock Entry \& Stock Entry Detail



\### 2.1. Stock Entry (cấp chứng từ) — các field liên quan định giá



| Field | Type | Ý nghĩa |

|---|---|---|

| `purpose` | Select | Mục đích — quyết định cách tính giá (xem §3) |

| `stock\_entry\_type` | Link | Loại chứng từ (gắn với purpose) |

| `posting\_date` / `posting\_time` | Date / Time | Thời điểm ghi sổ — dùng để xác định SLE trước/sau |

| `additional\_costs` | Table (`Landed Cost Taxes and Charges`) | Chi phí tăng thêm (đối tượng chính của tài liệu này) |

| `total\_additional\_costs` | Currency | Tổng chi phí tăng thêm (quy nội tệ) |

| `total\_incoming\_value` | Currency | Tổng giá trị nhập (dòng có `t\_warehouse`) |

| `total\_outgoing\_value` | Currency | Tổng giá trị xuất (dòng có `s\_warehouse`) |

| `value\_difference` | Currency | Chênh lệch Incoming − Outgoing |



\*\*Child table `additional\_costs`\*\* (dùng đúng child table của Landed Cost Voucher):



| Field | Type | Ý nghĩa |

|---|---|---|

| `description` | Small Text | Mô tả khoản phí (vd: "Phí vận chuyển", "Non stock items") |

| `expense\_account` | Link → Account | \*\*Tài khoản chi phí\*\* của khoản phí (VD: 641 – Chi phí vận chuyển) |

| `amount` | Currency | Số tiền theo `account\_currency` |

| `account\_currency` | Link → Currency | Ngoại tệ của tài khoản phí |

| `exchange\_rate` | Float | Tỷ giá quy đổi |

| `base\_amount` | Currency | `amount × exchange\_rate` — số tiền quy nội tệ (dùng để phân bổ) |



\### 2.2. Stock Entry Detail (child — một dòng item)



| Field | Type | Ý nghĩa |

|---|---|---|

| `s\_warehouse` | Link → Warehouse | Kho nguồn (xuất) |

| `t\_warehouse` | Link → Warehouse | Kho đích (nhập) |

| `qty` | Float | Số lượng theo UOM |

| `conversion\_factor` | Float | Hệ số quy đổi |

| `transfer\_qty` | Float | Số lượng theo Stock UOM = `qty × conversion\_factor` |

| `basic\_rate` | Currency | Đơn giá \*\*cơ bản\*\* (chưa cộng phí) |

| `basic\_amount` | Currency | `transfer\_qty × basic\_rate` |

| `additional\_cost` | Currency | Phần chi phí tăng thêm \*\*phân bổ cho dòng này\*\* |

| `amount` | Currency | `basic\_amount + additional\_cost` |

| `valuation\_rate` | Currency | `basic\_rate + additional\_cost / transfer\_qty` — \*\*giá nhập vào kho\*\* |

| `expense\_account` | Link → Account | Difference Account — tài khoản đối ứng cho item |

| `is\_finished\_item` | Check | Thành phẩm (Manufacture/Repack) |

| `is\_scrap\_item` | Check | Phế phẩm |

| `allow\_zero\_valuation\_rate` | Check | Cho phép định giá = 0 |



> \*\*Mối quan hệ "tam giác" cốt lõi cần nhớ:\*\*

> ```

> basic\_amount  = transfer\_qty × basic\_rate

> additional\_cost = (basic\_amount / Σ incoming basic\_amount) × total\_additional\_costs   ← phân bổ theo tỷ trọng

> amount        = basic\_amount + additional\_cost

> valuation\_rate = basic\_rate + additional\_cost / transfer\_qty

> ```



\---



\## 3. Các Purpose (mục đích) nghiệp vụ chuẩn



| Purpose | s\_warehouse | t\_warehouse | Cách tính basic\_rate dòng nhập | Ghi chú |

|---|---|---|---|---|

| \*\*Material Receipt\*\* | ✗ | ✓ | `get\_valuation\_rate()` — lấy giá SLE cuối / Item master / Item Price | Nhập kho tự do |

| \*\*Material Issue\*\* | ✓ | ✗ | — | Xuất kho, outgoing rate lấy `get\_incoming\_rate()` |

| \*\*Material Transfer\*\* | ✓ | ✓ | `get\_valuation\_rate()` (cùng item, cùng/khác kho) | Chuyển kho nội bộ |

| \*\*Material Transfer for Manufacture\*\* | ✓ | ✓ | `get\_valuation\_rate()` | Đưa NVL vào nơi sản xuất |

| \*\*Material Consumption for Manufacture\*\* | ✓ | ✗ | — | Tiêu hao NVL theo BOM |

| \*\*Manufacture\*\* | ✓ (NVL) + ✓ (scrap) | ✓ (FG) | `get\_basic\_rate\_for\_manufactured\_item()` — `(outgoing − scrap)/qty` | Nhập thành phẩm |

| \*\*Repack\*\* | ✓ | ✓ | `get\_basic\_rate\_for\_repacked\_items()` | Đóng gói lại |

| \*\*Send to Subcontractor\*\* | ✓ | ✓ | — | Gửi NVL thuê ngoài |

| \*\*Receive at Subcontractor\*\* (subcontracting) | ✓ | ✓ | từ Subcontracting Receipt | Nhận SP từ thầu phụ |



Nguồn: `validate\_purpose()` — `stock\_entry.py:253`.



\---



\## 4. Luồng tổng thể khi Submit



```

Owner/User submit Stock Entry

&#x20;       │

&#x20;       ▼

StockEntry.on\_submit()                        \[stock\_entry.py:169]

├── 1. update\_stock\_ledger()                  \[:172]  → tạo SLE + valuation

│        └─ get\_sle\_for\_source\_warehouse()    \[:1197]

│        └─ get\_sle\_for\_target\_warehouse()    \[:1218]

│        └─ make\_sl\_entries()                 \[:1186]  → SLE submit

│                └─ valuation engine          \[stock\_ledger.py:551 process\_sle]

│

├── 2. update\_work\_order() / subcontract / pick list...  \[:173-185]

│

├── 3. make\_gl\_entries()                      \[:179]

│        └─ (chỉ khi Perpetual Inventory)     \[stock\_controller.py:69]

│              ├─ StockEntry.get\_gl\_entries() \[stock\_entry.py:1234]

│              │     ├─ super().get\_gl\_entries()  \[stock\_controller.py:148] — GL theo stock\_value\_difference

│              │     └─ GL cho additional\_costs   \[:1250-1308]

│              └─ make\_gl\_entries(...)        \[ghi GL vào tabGL Entry]

│

└── 4. repost\_future\_sle\_and\_gle()            \[:181]  → kiểm tra \& repost nếu có SLE/GL tương lai

```



\*\*Điều kiện để sinh GL\*\* — `stock\_controller.py:81-85`:



```python

if (

&#x20;   cint(erpnext.is\_perpetual\_inventory\_enabled(self.company))   # Perpetual Inventory ON

&#x20;   or provisional\_accounting\_for\_non\_stock\_items

&#x20;   or is\_asset\_pr                                                # item là tài sản cố định

):

&#x20;   warehouse\_account = get\_warehouse\_account\_map(self.company)

&#x20;   ...

&#x20;   gl\_entries = self.get\_gl\_entries(warehouse\_account)

&#x20;   make\_gl\_entries(gl\_entries, ...)

```



> \*\*Quan trọng:\*\* Nếu công ty \*\*không bật Perpetual Inventory\*\* thì Stock Entry \*\*không sinh GL\*\* — giá trị kho chỉ nằm ở SLE. GL chỉ có khi bật "Perpetual Inventory" trong Company.



\---



\## 5. Bước 0 — Tính giá trị trên Stock Entry (`calculate\_rate\_and\_amount`)



Hàm `calculate\_rate\_and\_amount()` — `stock\_entry.py:686`, được gọi từ `validate()` khi save/submit:



```python

def calculate\_rate\_and\_amount(self, reset\_outgoing\_rate=True, raise\_error\_if\_no\_rate=True):

&#x20;   self.set\_basic\_rate(reset\_outgoing\_rate, raise\_error\_if\_no\_rate)   # ① đơn giá cơ bản

&#x20;   init\_landed\_taxes\_and\_totals(self)                                  # ② chuẩn hoá additional\_costs

&#x20;   self.distribute\_additional\_costs()                                  # ③ phân bổ phí

&#x20;   self.update\_valuation\_rate()                                        # ④ gộp phí vào amount \& valuation\_rate

&#x20;   self.set\_total\_incoming\_outgoing\_value()                            # ⑤ tổng In/Out + value\_difference

&#x20;   self.set\_total\_amount()                                             # ⑥ tổng tiền

```



\### ① `set\_basic\_rate()` — `:694`



1\. \*\*Outgoing (dòng có `s\_warehouse`)\*\* → `set\_rate\_for\_outgoing\_items()` `:751`:

&#x20;  - Gọi `get\_incoming\_rate()` (`utils.py:270`) để lấy giá hiện hành của kho nguồn:

&#x20;    - Serial → `get\_avg\_purchase\_rate(serial\_no)` (bình quân giá mua serial)

&#x20;    - Batch → `get\_batch\_incoming\_rate()`

&#x20;    - FIFO/LIFO → lấy giá từ `stock\_queue` của SLE trước (`\_get\_fifo\_lifo\_rate`)

&#x20;    - Moving Average → lấy `valuation\_rate` của SLE trước

&#x20;  - `basic\_amount = transfer\_qty × basic\_rate`; cộng vào `outgoing\_items\_cost` nếu dòng \*\*không\*\* có t\_warehouse (`:762`).

2\. \*\*Finished item\*\* (Manufacture/Repack):

&#x20;  - Manufacture → `get\_basic\_rate\_for\_manufactured\_item()` `:794`:

&#x20;    ```

&#x20;    basic\_rate = (outgoing\_items\_cost − scrap\_items\_cost) / finished\_item\_qty

&#x20;    ```

&#x20;    (nếu cài `material\_consumption`, lấy NVL từ BOM — `:798-802`)

&#x20;  - Repack → `get\_basic\_rate\_for\_repacked\_items()` `:784`: `outgoing\_items\_cost / finished\_item\_qty`.

3\. \*\*Incoming thường (dòng chỉ có `t\_warehouse`)\*\* → `get\_valuation\_rate()` (`stock\_ledger.py:1435`): giá SLE cuối cùng (>= 0) của item+warehouse; nếu không có → Item `valuation\_rate` → `standard\_rate` → Item Price. Nếu không có rate và Perpetual Inventory ON → throw "Valuation Rate Missing" (`:1499-1529`).

4\. `allow\_zero\_valuation\_rate` → `basic\_rate = 0` (`:708-710`).



\### ② `init\_landed\_taxes\_and\_totals()` — `taxes\_and\_totals.py:1126`



Chuẩn hoá child `additional\_costs` (dùng chung với Landed Cost Voucher):

\- `account\_currency` = currency của `expense\_account` (`:1134`)

\- `exchange\_rate` = 1 nếu cùng nội tệ, ngược lại lấy tỷ giá từ hệ thống (`:1141`)

\- `base\_amount = amount × exchange\_rate` (`:1157`)



\### ③ `distribute\_additional\_costs()` — `:806`



Phần này là \*\*trái tim của câu hỏi "chi phí có vào kho không"\*\* — chi tiết ở §9.



\### ④ `update\_valuation\_rate()` — `:830`



```python

d.amount = basic\_amount + additional\_cost

d.valuation\_rate = basic\_rate + (additional\_cost / transfer\_qty)   # không làm tròn — tránh mất precision

```



\### ⑤ `set\_total\_incoming\_outgoing\_value()` — `:837`



```

total\_incoming\_value = Σ amount (dòng có t\_warehouse)

total\_outgoing\_value = Σ amount (dòng có s\_warehouse)

value\_difference     = total\_incoming\_value − total\_outgoing\_value

```



\---



\## 6. Bước 1 — Tạo Stock Ledger Entry



`update\_stock\_ledger()` — `stock\_entry.py:1172`:



```python

finished\_item\_row = self.get\_finished\_item\_row()            # dòng is\_finished\_item (Manufacture/Repack)

self.get\_sle\_for\_source\_warehouse(sl\_entries, finished\_item\_row)   # SLE xuất trước

self.get\_sle\_for\_target\_warehouse(sl\_entries, finished\_item\_row)   # SLE nhập sau

if self.docstatus == 2: sl\_entries.reverse()               # cancel → đảo ngược

self.make\_sl\_entries(sl\_entries)

```



\### 6.1. SLE cho kho nguồn — `get\_sle\_for\_source\_warehouse()` `:1197`



Với mỗi dòng có `s\_warehouse`:



```python

{

&#x20;   "warehouse":    s\_warehouse,

&#x20;   "actual\_qty":   -transfer\_qty,        # xuất → âm

&#x20;   "incoming\_rate": 0,                    # xuất không có incoming\_rate

}

```



\- Nếu dòng \*\*có cả t\_warehouse\*\* → `dependant\_sle\_voucher\_detail\_no = d.name` (`:1209`) — liên kết SLE xuất với dòng item để sau này recalc theo dòng.

\- Ngược lại nếu là FG row khác → trỏ tới `finished\_item\_row.name` (`:1214`).



\### 6.2. SLE cho kho đích — `get\_sle\_for\_target\_warehouse()` `:1218`



```python

{

&#x20;   "warehouse":     t\_warehouse,

&#x20;   "actual\_qty":    +transfer\_qty,

&#x20;   "incoming\_rate": flt(d.valuation\_rate),     # ★★★ ĐIỂM MẤU CHỐT

}

```



\*\*`incoming\_rate` của SLE kho đích = `valuation\_rate` của Stock Entry Detail\*\* — mà `valuation\_rate` \*\*đã gộp additional cost\*\* (§5-④). Đây chính là đường dẫn khiến chi phí tăng thêm đi thẳng vào giá trị kho đích.



\- Nếu dòng có `s\_warehouse` hoặc là dòng FG → `sle.recalculate\_rate = 1` (`:1230`): báo cho valuation engine biết cần \*\*tính lại rate từ chứng từ\*\* (không dùng rate tĩnh).



\### 6.3. Hàm tạo dict SLE — `get\_sl\_entries()` `stock\_controller.py:422`



Điền các field chuẩn: `item\_code`, `warehouse`, `posting\_date/time`, `voucher\_type/no`, `voucher\_detail\_no`, `actual\_qty`, `stock\_uom`, `incoming\_rate`, `company`, `batch\_no`, `serial\_no`, `project`, `is\_cancelled`, cộng inventory dimensions.



\### 6.4. Ghi SLE — `make\_sl\_entries()` `stock\_ledger.py:29` → `make\_entry()` `:161`



\- Với cancel: đảo dấu `actual\_qty`, nạp lại rate bằng `get\_incoming\_outgoing\_rate\_for\_cancel()` (`:53-65`).

\- Gọi `make\_entry()` → `sle.submit()` → kích hoạt \*\*valuation engine\*\* (§7).



\---



\## 7. Bước 1.5 — Valuation Engine — tính lại giá trị kho khi ghi SLE



Đây là phần hệ thống \*\*tự tính lại giá trị tồn kho\*\* cho mỗi kho khi có SLE mới. Điểm vào: `process\_sle()` — `stock\_ledger.py:551`.



\### 7.1. `process\_sle()` — `:551`



Trình tự:

1\. Lấy trạng thái hiện tại của warehouse (`wh\_data`) từ `self.data\[warehouse]` — bao gồm `qty\_after\_transaction`, `valuation\_rate`, `stock\_value`, `prev\_stock\_value`, `stock\_queue`.

2\. \*\*`get\_dynamic\_incoming\_outgoing\_rate()`\*\* (`:730`): nếu `sle.recalculate\_rate == 1` → gọi `get\_incoming\_outgoing\_rate\_from\_transaction()` (`:740`) → với Stock Entry, gọi `recalculate\_amounts\_in\_stock\_entry()` (`stock\_ledger.py:857`) rồi \*\*đọc lại `valuation\_rate` từ Stock Entry Detail\*\* (`:745`). → Đây là cơ chế "giá nhập động": khi entry có `recalculate\_rate`, giá nhập SLE lấy \*\*đúng giá đã gộp phí\*\* từ chứng từ.

3\. \*\*Chọn phương pháp định giá\*\* (`:594-627`):

&#x20;  - Có Serial No → `get\_serialized\_values()` (`:962`)

&#x20;  - Có Batch + `use\_batchwise\_valuation` → `update\_batched\_values()` (`:1120`)

&#x20;  - Moving Average → `get\_moving\_average\_values()` (`:1033`)

&#x20;  - FIFO/LIFO → `update\_queue\_values()` (`:1072`)

&#x20;  - Stock Reconciliation (không batch/serial) → gán thẳng `valuation\_rate`/`stock\_value` (`:608-618`)

4\. \*\*Tính `stock\_value\_difference`\*\* (`:633`):



&#x20;  ```python

&#x20;  stock\_value\_difference = self.wh\_data.stock\_value - self.wh\_data.prev\_stock\_value

&#x20;  ```



&#x20;  → ghi vào SLE (`:643`). Đây chính là số tiền dùng cho GL sau này.

5\. \*\*`update\_outgoing\_rate\_on\_transaction()`\*\* (`:831`) — với dòng xuất của Stock Entry, gọi `update\_rate\_on\_stock\_entry()` (`:850`) → `recalculate\_amounts\_in\_stock\_entry()` để cập nhật lại rate trên chứng từ (vòng hồi tiếp).



\### 7.2. Moving Average — `get\_moving\_average\_values()` `:1033`



```

Nhập (actual\_qty > 0):

&#x20;   nếu tồn trước <= 0:   valuation\_rate = incoming\_rate

&#x20;   ngược lại:

&#x20;       new\_stock\_value = (qty\_after × valuation\_rate) + (actual\_qty × incoming\_rate)

&#x20;       valuation\_rate   = new\_stock\_value / new\_qty



Xuất (actual\_qty < 0):

&#x20;   new\_stock\_value = (qty\_after × valuation\_rate) + (actual\_qty × outgoing\_rate)

&#x20;   valuation\_rate   = new\_stock\_value / new\_qty      (nếu new\_qty > 0)

```



→ Moving Average: mỗi lần nhập với giá mới sẽ \*\*kéo giá bình quân\*\* về gần giá mới. Phí tăng thêm làm `incoming\_rate` cao hơn → kéo giá bình quân lên.



\### 7.3. FIFO / LIFO — `update\_queue\_values()` `:1072` + `valuation.py`



\- `FIFOValuation.add\_stock(qty, rate)`: thêm bin `\[qty, rate]` vào cuối queue.

\- `remove\_stock(qty, outgoing\_rate, rate\_generator)`: lấy từ đầu queue (FIFO) / cuối queue (LIFO) theo từng lớp giá.

\- `stock\_value = Σ (bin.qty × bin.rate)`; `stock\_value\_difference = stock\_value − prev\_stock\_value` (`:1107`).

\- Sau đó `valuation\_rate = stock\_value / qty\_after\_transaction` (`:1118`).



→ Với FIFO/LIFO, phí tăng thêm làm `incoming\_rate` của bin nhập cao hơn → \*\*chính bin đó\*\* (lớp giá mới) được định giá cao hơn khi xuất sau này.



\### 7.4. Batchwise — `update\_batched\_values()` `:1120`



```

Nhập: stock\_value\_difference = incoming\_rate × actual\_qty

Xuất: outgoing\_rate = get\_batch\_incoming\_rate(...);  stock\_value\_difference = outgoing\_rate × actual\_qty

```



\### 7.5. Serialized — `get\_serialized\_values()` `:962`



```

Nhập: stock\_value\_change = actual\_qty × incoming\_rate

Xuất: dùng avg purchase rate của các serial (get\_incoming\_value\_for\_serial\_nos)

```



\---



\## 8. Bước 2 — Tạo GL Entry



\### 8.1. Điều kiện kích hoạt — `stock\_controller.py:69`



Perpetual Inventory ON (hoặc provisional accounting / item là asset) → mới sinh GL.



\### 8.2. `StockEntry.get\_gl\_entries()` — `stock\_entry.py:1234`



```python

gl\_entries = super().get\_gl\_entries(warehouse\_account)   # base entries

\# ... thêm GL cho additional\_costs

return process\_gl\_map(gl\_entries)

```



\### 8.3. Base entries — `StockController.get\_gl\_entries()` `stock\_controller.py:148`



1\. `get\_stock\_ledger\_details()` (`:330`): lấy \*\*toàn bộ SLE\*\* của voucher kèm `stock\_value\_difference`.

2\. `get\_voucher\_details()` (`:278`): lấy dòng item + `expense\_account`, `cost\_center`, `project`.

3\. Với mỗi (item\_row, SLE) — nếu kho SLE có tài khoản (`warehouse\_account\[sle.warehouse]`):



&#x20;  ```python

&#x20;  # Dòng 1 — Nợ tài khoản kho

&#x20;  {

&#x20;      "account":  warehouse\_account\[sle.warehouse]\["account"],   # VD: 152 – Hàng tồn kho

&#x20;      "debit":    flt(sle.stock\_value\_difference),

&#x20;      "against":  expense\_account,

&#x20;  }

&#x20;  # Dòng 2 — Có tài khoản chi phí của item (Difference Account)

&#x20;  {

&#x20;      "account":  expense\_account,                                # VD: 621 – Chi phí NVL

&#x20;      "debit":   -1 \* flt(sle.stock\_value\_difference),           # tức Credit

&#x20;  }

&#x20;  ```



&#x20;  Nguồn: `:177-211`.



4\. Nếu kho không có tài khoản → throw "Warehouse {0} is not linked to any account..." (`:261-268`).

5\. `process\_gl\_map()` (`general\_ledger.py:166`): phân bổ theo Cost Center Allocation, gộp dòng giống nhau (`merge\_similar\_entries`), đảo debit/credit nếu âm (`toggle\_debit\_credit\_if\_negative`).



> \*\*Nội dung quan trọng:\*\* `stock\_value\_difference` \*\*đã bao gồm phần additional cost\*\* (vì incoming\_rate = valuation\_rate đã gộp phí). Nên base GL cho tài khoản kho \*\*đã ghi nợ trọn phần phí\*\*. GL bổ sung cho additional\_costs chỉ để "tách" phần phí ra khỏi Difference Account của item (xem §9).



\### 8.4. Ghi GL — `make\_gl\_entries()` `general\_ledger.py`



Ghi từng dòng vào `tabGL Entry`, tự cân đối, gán `is\_cancelled` khi hủy. Khi cancel chứng từ → `make\_reverse\_gl\_entries()` (`stock\_controller.py:71`).



\---



\## 9. Additional Costs — phân tích chuyên sâu



> \*\*Câu hỏi chính:\*\* Khi thêm chi phí tăng thêm (`additional\_costs`) vào Stock Entry, chi phí đó \*\*có trực tiếp đi vào giá trị kho của `t\_warehouse` không?\*\*

>

> \*\*Trả lời ngắn gọn: CÓ.\*\* Chi phí tăng thêm được \*\*vốn hoá (capitalize) vào giá trị tồn kho của `t\_warehouse`\*\*, ở cả tầng SLE (giá trị kho) lẫn tầng GL (tài khoản kho ghi nợ đầy đủ). Không ghi nhận thẳng vào chi phí phát sinh (ngoại trừ trường hợp ngoại lệ ở §9.4).



\### 9.1. Phân bổ phí cho từng dòng item — `distribute\_additional\_costs()` `stock\_entry.py:806`



```python

total\_additional\_costs = Σ base\_amount của bảng additional\_costs      # :811



if purpose in ("Repack", "Manufacture"):

&#x20;   incoming\_items\_cost = Σ basic\_amount của dòng is\_finished\_item    # :813-814

else:

&#x20;   incoming\_items\_cost = Σ basic\_amount của dòng có t\_warehouse      # :816



if not incoming\_items\_cost:

&#x20;   return                                                            # :818-819  ← ngoại lệ!



for d in items:

&#x20;   if (Repack/Manufacture và không phải is\_finished\_item): d.additional\_cost = 0; continue

&#x20;   if không có t\_warehouse: d.additional\_cost = 0; continue

&#x20;   d.additional\_cost = (d.basic\_amount / incoming\_items\_cost) × total\_additional\_costs   # :828

```



\*\*Quy tắc phân bổ: theo tỷ trọng `basic\_amount`\*\* — dòng nào có `basic\_amount` lớn thì chịu nhiều phí hơn.



\### 9.2. Gộp phí vào giá trị kho — `update\_valuation\_rate()` `:830`



```python

d.amount          = basic\_amount + additional\_cost

d.valuation\_rate  = basic\_rate + (additional\_cost / transfer\_qty)

```



→ Sau đó `valuation\_rate` được dùng làm `incoming\_rate` của SLE t\_warehouse (`:1226`) → giá trị kho tăng đúng bằng phần phí (§7).



\### 9.3. GL cho additional\_costs — `stock\_entry.py:1250-1308`



Với mỗi dòng phí `t` và mỗi dòng item nhập `d` (có `t\_warehouse`, hoặc is\_finished\_item với Manufacture/Repack):



```python

multiply\_based\_on = d.basic\_amount if total\_basic\_amount else d.qty

divide\_based\_on   = total\_basic\_amount (hoặc Σ qty nếu total\_basic\_amount = 0)



\# Phần phí của dòng item d ứng với tài khoản phí t

amount\[expense\_account=t.expense\_account] += (t.amount × multiply\_based\_on) / divide\_based\_on

base\_amount\[...]                          += (t.base\_amount × multiply\_based\_on) / divide\_based\_on

```



Rồi tạo 2 GL bổ sung (`:1280-1308`):



```python

\# GL 1 — Credit tài khoản chi phí của khoản phí

{

&#x20;   "account":  t.expense\_account,           # VD: 641 – Chi phí vận chuyển

&#x20;   "credit":   amount,                      # Credit khoản phí

&#x20;   "against":  d.expense\_account,

}



\# GL 2 — Debit (thể hiện bằng credit âm) vào Difference Account của item

{

&#x20;   "account":  d.expense\_account,           # VD: 621 – Chi phí NVL

&#x20;   "credit":  -1 × base\_amount,             # tức là Debit

&#x20;   "against":  t.expense\_account,

}

```



\*\*Vì sao phải thêm 2 GL này?\*\* — Bởi base GL đã nợ tài khoản kho \*\*trọn phần phí\*\* (SVD gồm phí). Nếu không thêm GL bù, phần phí sẽ "rơi" vào Difference Account của item (621) — sai nghiệp vụ. Thêm 2 GL này để \*\*chuyển phần phí ra khỏi Difference Account của item sang tài khoản phí\*\*:



```

BASE GL:            Warehouse Asset (152) Nợ (basic + phí)     /   621 Có (basic + phí)

\+ ADDITIONAL GL 1:  641 Có (phí)

\+ ADDITIONAL GL 2:  621 Nợ (phí)      ← triệt tiêu phần phí đã ghi vào 621

─────────────

NET:                Warehouse Asset (152) Nợ (basic + phí)

&#x20;                   621 Có (basic)                        ← item chỉ chịu chi phí cơ bản

&#x20;                   641 Có (phí)                          ← khoản phí tách riêng, nhưng vốn hoá vào kho

```



\### 9.4. Các trường hợp ngoại lệ — phải biết



| Tình huống | Hệ quả | Chi phí có vào kho? |

|---|---|---|

| \*\*`incoming\_items\_cost = 0`\*\* (`:818`) — không dòng t\_warehouse nào có `basic\_amount` (vd nhập với basic\_rate = 0) | `distribute\_additional\_costs` return sớm → `additional\_cost = 0`, `valuation\_rate` \*\*không\*\* gộp phí | \*\*KHÔNG\*\* vào giá trị kho. Nhưng GL vẫn post additional\_costs (phân bổ theo \*\*qty\*\* thay vì basic\_amount, `:1244-1262`) → tài khoản phí vẫn bị Credit, item expense vẫn bị Debit → \*\*phí nằm ngoài giá trị kho\*\* |

| \*\*Material Issue / Consumption\*\* — không dòng t\_warehouse nào | `distribute\_additional\_costs` tự xoá `additional\_costs = \[]` (`:808-809`) | Không có phí (bị xoá) |

| \*\*Manufacture/Repack\*\* | Cơ sở phân bổ là `is\_finished\_item`, không phải mọi dòng t\_warehouse; scrap bị loại (`:813-814`, `:795`) | Có — vào giá FG |

| \*\*Material Transfer\*\* (vừa s vừa t) | `recalculate\_rate = 1` → SLE t\_warehouse lấy lại `valuation\_rate` từ chứng từ (đã gộp phí) | Có — vào kho đích |

| \*\*Chi phí vận hành / non-stock item trong sản xuất\*\* | `add\_additional\_cost()` (`bom.py:1192`) tự nạp vào `additional\_costs` | Có — qua đúng con đường này vào giá FG |



> \*\*Kết luận nghiệp vụ:\*\* Với quy trình nhập kho/ chuyển kho/ sản xuất thông thường, \*\*additional\_costs đi trực tiếp vào chi phí kho (giá trị tồn kho) của `t\_warehouse`\*\*. Chỉ khi `basic\_amount` của dòng nhập = 0 thì phí mới không được vốn hoá mà trở thành chi phí phát sinh (GL vẫn ghi) — cần kiểm tra trước khi dùng phí cùng item giá 0.



\---



\## 10. Ví dụ nghiệp vụ có số liệu



\### 10.1. Material Receipt + Additional Cost (đơn giản nhất)



\*\*Giả định:\*\* Công ty Perpetual Inventory. Nhập 10 cái NVL, `basic\_rate = 100`. Thêm phí vận chuyển 100 (tài khoản 641).



\*\*Tính trên chứng từ:\*\*



| Dòng | basic\_rate | transfer\_qty | basic\_amount | additional\_cost | amount | valuation\_rate |

|---|---|---|---|---|---|---|

| NVL-A | 100 | 10 | 1.000 | (1.000/1.000)×100 = \*\*100\*\* | \*\*1.100\*\* | 100 + 100/10 = \*\*110\*\* |



\*\*SLE tạo ra:\*\*



| SLE | warehouse | actual\_qty | incoming\_rate | stock\_value\_difference |

|---|---|---|---|---|

| 1 | 152-Kho NVL | +10 | \*\*110\*\* | \*\*+1.100\*\* |



\*\*GL tạo ra:\*\*



| Account | Debit | Credit |

|---|---|---|

| 152 – Hàng tồn kho (Warehouse Asset) | \*\*1.100\*\* | |

| 621 – Chi phí NVL (Difference Account) | | 1.000 |

| 641 – Chi phí vận chuyển (Additional) | | 100 |



→ Giá trị kho tăng \*\*1.100\*\* (bao gồm 100 phí vận chuyển). Item chỉ chịu 1.000.



\### 10.2. Manufacture — FG với additional cost (chi phí vận hành)



\*\*Giả định:\*\* Xuất NVL 100, chi phí vận hành thêm 20 (nạp qua `add\_additional\_cost` `bom.py:1192`). FG = 1 cái.



```

outgoing\_items\_cost = 100

basic\_rate FG = (100 − 0 scrap) / 1 = 100

additional\_cost FG = (100/100) × 20 = 20

valuation\_rate FG = 100 + 20/1 = 120

```



SLE FG: `incoming\_rate = 120`, `stock\_value\_difference = +120`.

GL: Nợ 152-Thành phẩm = 120; Có 621 = 100; Có 641 (điện/nước vận hành) = 20.



\### 10.3. Material Transfer + Additional Cost (chuyển kho)



\*\*Giả định:\*\* Chuyển 5 cái NVL-A (giá bình quân hiện hành 110) từ Kho 1 sang Kho 2, phí chuyển 50.



```

basic\_rate dòng chuyển = get\_incoming\_rate() = 110

basic\_amount = 550

additional\_cost = (550/550) × 50 = 50

valuation\_rate = 110 + 50/5 = 120

```



\- SLE Kho 1: `actual\_qty = −5`, outgoing theo giá bình quân hiện hành.

\- SLE Kho 2: `incoming\_rate = 120`, SVD = +600 (5 × 120).

\- GL: Nợ 152-Kho 2 = 600; Có 152-Kho 1 = 550; Có 641 = 50.

\- `recalculate\_rate = 1` → hệ thống recalc lại rate từ chứng từ (§7.1-2).



> ⚠️ Ví dụ trên là \*\*tình huống chuẩn\*\* (giá được tự lấy → `basic\_amount > 0`). Khi `basic\_amount = 0`, phí \*\*không\*\* vào t\_warehouse mà bị Nợ vào `expense\_account` (SE Detail) — xem bảng hạch toán chuẩn 2 tình huống tại \*\*\[§16](#16-material-transfer-additional-cost-tình-huống-hạch-toán-chuẩn-4-tài-khoản)\*\*.



\---



\## 11. Cơ chế Repost (định giá lại) \& ngoại lệ



\### 11.1. Khi nào cần repost



`repost\_future\_sle\_and\_gle()` — `stock\_controller.py:896`:

\- Submit bình thường: kiểm tra `future\_sle\_exists()` hoặc `repost\_required\_for\_queue()` → nếu có SLE/GL "tương lai" (posting sau chứng từ này) bị ảnh hưởng → tạo `Repost Item Valuation` job.

\- Cancel (docstatus = 2): `force = True` → luôn repost.

\- Landed Cost Voucher / Stock Reconciliation thay đổi giá quá khứ → repost toàn chuỗi.



\### 11.2. Luồng repost



```

repost\_future\_sle\_and\_gle()

→ create\_repost\_item\_valuation\_entry(args)          \[hoặc item-wise]

→ repost\_future\_sle()  \[stock\_ledger.py:176]

&#x20;    → với từng (item, warehouse) chạy update\_entries\_after → process\_sle lại từng SLE

&#x20;    → khi có dependant\_sle\_voucher\_detail\_no → lan truyền sang dòng liên quan

→ sau đó repost GL tương ứng

```



→ Phí tăng thêm thay đổi → incoming\_rate của SLE đích thay đổi → mọi SLE xuất sau đó được tính lại → GL được cập nhật lại. \*\*Hệ thống tự đảm bảo nhất quán giá trị kho theo thời gian.\*\*



\---



\## 12. Custom Override tại các app nội bộ



Mã chuẩn ERPNext có thể bị ghi đè (override) ở các app cài trong site. Kiểm tra `hooks.py` của từng app:



| App | Override | Nội dung ảnh hưởng |

|---|---|---|

| `eupapp` | `EupStockEntry` (`overrides/stock\_entry.py`) | `validate` bổ sung operating cost từ BOM vào `additional\_costs` (`:211`), `before\_submit` (`:345`), `on\_submit` (`:424`), `on\_cancel` (`:472`), vị trí kho (`update\_vitri\_kho`), yêu cầu sản xuất (`update\_ycsx`)... |

| `eupapp` | `EupStockLedgerEntry` (`overrides/stock\_ledger\_entry.py`) | Override SLE |

| `ybmapp` | `YbmStockEntry` | `autoname`, `get\_sle\_for\_source/target\_warehouse` override (`ybm\_stock/.../stock\_entry.py:113,129`), `set\_transfer\_qty` |

| `intaccount` | trỏ sang `EupStockEntry` | Dùng chung logic eupapp |



> \*\*Khi phân tích luồng trên production, luôn kiểm tra `hooks.py`\*\* của site đang chạy trước khi kết luận — đặc biệt nếu eupapp/ybmapp có mặt.



\---



\## 13. Checklist \& quy trình nghiệp vụ chuẩn



\### 13.1. Quy trình chuẩn để kiểm tra 1 Stock Entry



1\. \*\*Chuẩn bị:\*\* Công ty bật Perpetual Inventory? Tất cả warehouse có tài khoản (`warehouse\_account`)? Item có `valuation\_method` (hoặc Stock Settings mặc định)?

2\. \*\*Tạo chứng từ:\*\* chọn `purpose` đúng; điền s/t\_warehouse; nếu cần phí → thêm dòng `additional\_costs` (expense\_account + amount).

3\. \*\*Save\*\* → hệ thống chạy `calculate\_rate\_and\_amount` — xem `basic\_rate`, `basic\_amount`, `additional\_cost`, `amount`, `valuation\_rate` có đúng không.

4\. \*\*Submit\*\* → hệ thống tạo SLE + GL.

5\. \*\*Kiểm tra SLE:\*\* `Stock Ledger Report` / `tabStock Ledger Entry` — `incoming\_rate`, `stock\_value\_difference`, `qty\_after\_transaction`, `valuation\_rate` sau giao dịch.

6\. \*\*Kiểm tra GL:\*\* `General Ledger` / `tabGL Entry` cho voucher — tài khoản kho Nợ, item expense Có (basic), tài khoản phí Có (phí).

7\. \*\*Kiểm tra số dư kho (Bin/Item Balance):\*\* `stock\_value` tăng đúng `stock\_value\_difference`.



\### 13.2. Checklist khi muốn phí "vào giá trị kho"



\- \[ ] Dòng item nhập có `t\_warehouse` \*\*và\*\* `basic\_amount > 0` (nếu basic\_amount = 0 → phí không vốn hoá, §9.4).

\- \[ ] `expense\_account` của mỗi khoản phí là tài khoản \*\*chi phí\*\* hợp lệ (không phải tài khoản kho).

\- \[ ] `additional\_costs` được điền trước khi save (để `distribute\_additional\_costs` chạy đúng lúc validate).

\- \[ ] Với Manufacture/Repack: chỉ dòng `is\_finished\_item` mới nhận phí — đánh dấu đúng dòng FG.



\### 13.3. Thứ tự tái tính toán khi thay đổi phí sau submit



Không nên sửa `additional\_costs` trực tiếp trên chứng từ đã submit. Thay vào đó:

\- Cancel chứng từ → sửa phí → resubmit; hoặc

\- Dùng \*\*Landed Cost Voucher\*\* để bổ sung phí cho Purchase Receipt (chứng từ phí chuyên biệt); hoặc

\- Nếu dùng custom "Phân bổ lại" (xem `stock\_entry.md` custom patch trong apps) → dùng nút phân bổ lại trước khi submit.



\---



\## 14. Lưu ý kế toán \& sai lầm thường gặp



1\. \*\*Nhầm lẫn "phí vào giá trị kho" ở tầng GL:\*\* Nợ tài khoản kho = SVD \*\*đã gồm phí\*\*; đừng tìm "Nợ tài khoản phí" — tài khoản phí (641) luôn \*\*Có\*\*, vì phí đã được chuyển vào giá trị hàng tồn kho.

2\. \*\*basic\_amount = 0 là cái bẫy:\*\* Phí vẫn sinh GL nhưng không tăng giá trị kho → tồn kho có giá trị không phản ánh chi phí thực (dễ xảy ra với item giá 0 / allowance zero rate).

3\. \*\*Material Issue/Consumption không dùng additional\_costs được\*\* — hệ thống tự xoá; muốn hạch toán chi phí phát sinh dùng Journal Entry.

4\. \*\*Perpetual Inventory tắt → không có GL.\*\* Nếu kế toán thấy thiếu bút toán, kiểm tra Company → Perpetual Inventory trước.

5\. \*\*Warehouse phải có tài khoản\*\* — nếu không, submit sẽ throw "Warehouse ... is not linked to any account".

6\. \*\*Rounding:\*\* `valuation\_rate` không làm tròn (`:835`) để tránh lệch giá trị; `stock\_value\_difference` được gom rounding ở GL cho internal transfer (`stock\_controller.py:215-259`).

7\. \*\*Khi phân tích production có eupapp/ybmapp\*\*, đừng bỏ qua override — kiểm tra `hooks.py` (§12).



\---



\## 15. Q\&A — Giải thích chuyên sâu



> Phần này trả lời 3 câu hỏi cốt lõi mà kế toán / lập trình viên thường hỏi khi đọc GL của Stock Entry. Trả lời dựa trực tiếp trên mã nguồn.



\---



\### Q1. Vì sao GL Entry của Stock Entry luôn có \*\*1 bên là tài khoản đối ứng của warehouse\*\* (kho), \*\*1 bên là `expense\_account` trong Stock Entry Detail\*\* (Difference Account)?



\*\*Trả lời:\*\* Đây là \*\*nguyên tắc Perpetual Inventory (kiểm kê thường xuyên)\*\*. Mọi biến động kho phải ghi nhận:

\- \*\*1 bên (Nợ/Có) vào tài khoản kho\*\* — phản ánh \*\*giá trị tài sản tồn kho thay đổi\*\*.

\- \*\*1 bên đối ứng vào `expense\_account` của dòng item\*\* — là \*\*tài khoản "cân bằng" (balancing account)\*\*, nơi giá trị kia "đi đến" hoặc "đến từ".



Vì Stock Entry \*\*không\*\* là chứng từ mua/bán (không có nhà cung cấp / phải trả người bán), nên bên đối ứng \*\*không thể\*\* là tài khoản công nợ. Thay vào đó ERPNext dùng \*\*Difference Account\*\* — cái tên phản ánh đúng vai trò: nó \*\*hấp thụ phần chênh lệch\*\* chưa được giải thích bởi một kho khác.



Bản chất khác nhau theo purpose (`stock\_controller.py:148-211` — mỗi SLE sinh 2 dòng GL):



```python

\# Với MỖI SLE (xuất hoặc nhập):

Dòng 1 → Nợ tài khoản kho của SLE:      debit = sle.stock\_value\_difference

Dòng 2 → Nợ âm (tức Có) expense\_account: debit = -1 × sle.stock\_value\_difference

```



| Purpose | Tài khoản kho (bên 1) | `expense\_account` (bên 2) = \*\*ý nghĩa\*\* | Ghi chú |

|---|---|---|---|

| \*\*Material Issue\*\* | Có 152 (kho giảm) | Nợ \*\*expense\*\* (vd 621 Chi phí NVL) — giá trị hàng xuất thành \*\*chi phí\*\* | Đúng nghĩa "kho giảm, chi phí tăng" |

| \*\*Material Receipt\*\* | Nợ 152 (kho tăng) | Có \*\*expense\*\* — giá trị hàng nhập "đến từ" tài khoản chi phí/đối ứng | Doanh nghiệp mua hàng hạch toán ngoài, kho chỉ nhận giá trị |

| \*\*Material Transfer\*\* | Nợ 152-Kho đích + Có 152-Kho nguồn | \*\*triệt tiêu (net = 0)\*\* — vì SLE xuất và SLE nhập cùng dùng \*\*chung\*\* `expense\_account` | → chỉ còn \*\*tài sản ↔ tài sản\*\* (xem giải thích dưới) |

| \*\*Manufacture\*\* | Nợ 152-Thành phẩm + Có 152-NVL | triệt tiêu (các dòng NVL và FG dùng chung) | Chuyển giá trị NVL → FG |



\*\*Vì sao Material Transfer chỉ còn "Nợ kho đích / Có kho nguồn"?\*\*



Một dòng chuyển kho (có cả `s\_warehouse` và `t\_warehouse`) sinh \*\*2 SLE cùng `expense\_account`\*\* (mặc định từ Item / Stock Adjustment Account — `stock\_entry.py:1411,1423`):



```

SLE xuất  (source):  Nợ 152-Kho nguồn = -X (tức Có X)      ; Nợ expense = +X

SLE nhập  (target):  Nợ 152-Kho đích  = +Y                 ; Nợ expense = -Y (tức Có Y)

```

Nếu X = Y (cùng giá trị) → cột `expense\_account` \*\*Nợ X rồi Có X = 0\*\*. Kết quả GL gọn lại:

```

Nợ 152-Kho đích    Y

Có  152-Kho nguồn  X

```

→ Đây là \*\*bút toán tài sản ↔ tài sản\*\* thuần tuý, không ảnh hưởng lãi/lỗ. (Khi X ≠ Y do rounding → sinh thêm dòng "Rounding gain/loss" — `stock\_controller.py:215-259`.)



> \*\*Tóm tắt Q1:\*\* Bên 1 (tài khoản kho) = giá trị tồn kho thay đổi; bên 2 (`expense\_account` của SE Detail) = tài khoản cân bằng, đại diện cho chi phí/đối ứng của dòng item; với transfer nó tự triệt tiêu.



\---



\### Q2. Khi có `additional\_costs`, vì sao GL phát sinh thêm \*\*1 cặp: `expense\_account` trong SE Detail ↔ `expense\_account` trong additional\_costs\*\*?



\*\*Trả lời:\*\* Cặp GL bổ sung này là \*\*bút toán "tái phân loại" (reclassification)\*\*, mục đích \*\*chuyển phần chi phí tăng thêm ra khỏi Difference Account của item, ghi nhận vào đúng tài khoản chi phí của khoản phí\*\* — trong khi \*\*tổng giá trị vẫn được vốn hoá vào kho\*\*.



Lý do sâu xa (nhìn từ base GL — `stock\_controller.py:148-211`):



1\. `stock\_value\_difference` của SLE đích \*\*đã bao gồm cả additional cost\*\* (vì `incoming\_rate = valuation\_rate` đã gộp phí — §9.2).

2\. Nên \*\*base GL\*\* đã ghi:

&#x20;  ```

&#x20;  Nợ 152 – Hàng tồn kho (Warehouse Asset)   basic + phí     ← vốn hoá trọn phí vào kho

&#x20;  Có 621 – Difference Account của item       basic + phí     ← (chỉ là bên đối ứng cân bằng)

&#x20;  ```

3\. Nhưng theo nghiệp vụ, khoản phí (vd phí vận chuyển) thuộc về \*\*tài khoản phí của nó\*\* (vd 641), \*\*không\*\* thuộc Difference Account của item (621). Nếu để nguyên, 621 sẽ bị credit "nhầm" phần phí → sai bản chất chi phí.



→ Vì vậy `StockEntry.get\_gl\_entries()` thêm \*\*2 GL bù trừ\*\* (`stock\_entry.py:1280-1308`):



```python

\# GL bổ sung 1 — Có tài khoản chi phí của khoản phí (t.expense\_account)

{"account": t.expense\_account,  "credit":  amount, ...}   # t = dòng additional\_costs



\# GL bổ sung 2 — Nợ (thể hiện credit âm) Difference Account của item (d.expense\_account)

{"account": d.expense\_account,  "credit": -1 × base\_amount, ...}  # d = dòng SE Detail

```



\*\*Net-effect khi gộp base + bổ sung:\*\*



| Account | Base GL | + Addl GL | \*\*Kết quả NET\*\* |

|---|---|---|---|

| 152 – Hàng tồn kho (kho) | Nợ basic+phí | — | \*\*Nợ basic+phí\*\* (phí đã vốn hoá vào kho) |

| 621 – Difference Account item | Có basic+phí | Nợ phí | \*\*Có basic\*\* (item chỉ chịu chi phí cơ bản) |

| 641 – tài khoản phí (additional) | — | Có phí | \*\*Có phí\*\* (khoản phí tách riêng, nhưng vẫn nằm trong giá trị kho) |



\*\*Diễn giải nghiệp vụ:\*\* Cặp GL `SE Detail expense\_account ↔ additional\_costs expense\_account` = "lấy phần phí ra khỏi chỗ đối ứng của item, đưa sang tài khoản phí". Nó \*\*không\*\* thêm/bớt giá trị — chỉ \*\*định tuyến lại\*\* bên đối ứng, còn giá trị vào kho (152) giữ nguyên trọn vẹn.



> \*\*Điều kiện để cặp GL này sinh ra\*\* (`:1250-1262`): phí chỉ phân bổ cho dòng item \*\*có `t\_warehouse`\*\* (hoặc `is\_finished\_item` với Manufacture/Repack). Nếu dòng nhập có `basic\_amount = 0` → phân bổ theo \*\*qty\*\* (`:1262`) và phí \*\*không\*\* vào giá trị kho (xem Q3 / §9.4).



\---



\### Q3. Chi phí additional\_costs có \*\*trực tiếp đi vào giá trị kho của `t\_warehouse`\*\* không? Có làm \*\*tăng `incoming\_rate` trong SLE\*\* không?



\*\*Trả lời: CÓ — cả hai.\*\*



\*\*Bước 1 — Phí được gộp vào `valuation\_rate` của dòng item\*\* (`update\_valuation\_rate`, `stock\_entry.py:830-835`):



```python

d.amount          = basic\_amount + additional\_cost

d.valuation\_rate  = basic\_rate + (additional\_cost / transfer\_qty)   # ← phí nằm ngay trong đơn giá

```



\*\*Bước 2 — `valuation\_rate` này chính là `incoming\_rate` của SLE kho đích\*\* (`get\_sle\_for\_target\_warehouse`, `stock\_entry.py:1218-1227`):



```python

sle = {

&#x20;   "warehouse":     t\_warehouse,

&#x20;   "actual\_qty":    +transfer\_qty,

&#x20;   "incoming\_rate": flt(d.valuation\_rate),     # ★ = valuation\_rate ĐÃ GỘP PHÍ

}

```



→ \*\*`incoming\_rate` của SLE t\_warehouse TĂNG\*\* đúng bằng `additional\_cost / transfer\_qty`.



\*\*Bước 3 — Giá trị kho tăng trọn phần phí\*\* (valuation engine, §7):



\- Moving Average (`stock\_ledger.py:1033`): `new\_stock\_value = (qty × rate) + (actual\_qty × incoming\_rate)` → `stock\_value` tăng `actual\_qty × incoming\_rate` (gồm phí).

\- FIFO/LIFO (`update\_queue\_values` `:1072`): bin nhập được tạo với `rate = incoming\_rate` (gồm phí) → `stock\_value = Σ bin.qty × bin.rate` tăng theo.

\- `stock\_value\_difference` = giá trị mới − giá trị cũ → \*\*gồm phần phí\*\* (`:633`).

\- GL: Nợ 152 tài khoản kho = `stock\_value\_difference` → \*\*kho vốn hoá trọn phí\*\* (Q2).



\*\*Minh hoạ số (Material Receipt, 10 cái, basic 100, phí 100):\*\*



| Trước khi có phí | Sau khi có phí |

|---|---|

| `valuation\_rate = 100` | `valuation\_rate = 100 + 100/10 = 110` |

| SLE: `incoming\_rate = 100`, SVD = +1.000 | SLE: `incoming\_rate = 110`, SVD = \*\*+1.100\*\* |

| GL: Nợ 152 = 1.000 | GL: Nợ 152 = \*\*1.100\*\* |



\*\*Ngoại lệ khi phí KHÔNG vào giá trị kho (và không tăng incoming\_rate):\*\*



\- \*\*Dòng nhập có `basic\_amount = 0`\*\* (vd item giá 0 / Allow Zero Valuation Rate) → `distribute\_additional\_costs()` return sớm (`:818-819`), `additional\_cost = 0`, `valuation\_rate` \*\*không\*\* gộp phí → `incoming\_rate` SLE \*\*không\*\* tăng → phí \*\*không\*\* vốn hoá. Nhưng \*\*GL vẫn post\*\* cặp additional (phân bổ theo qty, `:1244-1262`) → tài khoản phí vẫn bị Có, Difference Account vẫn bị Nợ → phí thành \*\*chi phí phát sinh ngoài kho\*\* (trong P\&L), không nằm trên Bảng cân đối.

\- \*\*Material Issue / Material Consumption\*\* (không có dòng t\_warehouse nào) → `additional\_costs` bị \*\*xoá sạch\*\* (`:808-809`), không có phí.



> \*\*Tóm tắt Q3:\*\* Phí đi \*\*trực tiếp\*\* vào giá trị kho t\_warehouse và \*\*tăng incoming\_rate\*\* trong SLE, vì `valuation\_rate` gộp phí được dùng làm `incoming\_rate`. Chỉ khi `basic\_amount = 0` thì phí mới bị "rơi ra ngoài" giá trị kho (chỉ còn hạch toán vào P\&L).



\---



\## 16. Material Transfer + Additional Cost — Tình huống \& Hạch toán chuẩn (4 tài khoản)



> Phần này trả lời câu hỏi: \*"Khi chuyển kho có chi phí tăng thêm, có 4 tài khoản: s\_warehouse, t\_warehouse, `expense\_account` (SE Detail), `expense\_account` (additional\_costs). Theo tôi hiểu thì phí sẽ đẩy giá trị vào t\_warehouse = phí, còn `expense\_account` (SE Detail) giữ nguyên — đúng không? Test thực tế lại thấy giá trị cũng tăng ở `expense\_account` (SE Detail)?"\*

>

> \*\*Đáp ngắn:\*\* Đúng — \*\*trong tình huống chuẩn\*\* (basic\_amount > 0), phí đi vào t\_warehouse và `expense\_account` (SE Detail) \*\*triệt tiêu về 0\*\*. Cái test bạn thấy là \*\*tình huống ngoại lệ\*\* khi `basic\_amount = 0` → phí \*\*không\*\* vào kho mà bị Nợ vào `expense\_account` (SE Detail). Cả hai đều đã được kiểm chứng trên site dev EuP bằng phiếu thật (mục 16.2, 16.3).



\---



\### 16.1. Vì sao có "4 tài khoản" và mối quan hệ của chúng



Một dòng chuyển kho (Material Transfer — cùng dòng có `s\_warehouse` + `t\_warehouse`) khi thêm `additional\_costs` sẽ động chạm \*\*4 tài khoản\*\*:



| # | Tài khoản | Vai trò | Ghi chú |

|---|---|---|---|

| 1 | Tài khoản \*\*s\_warehouse\*\* (kho nguồn) | Giá trị hàng rời khỏi kho | Từ SLE xuất (`stock\_value\_difference` âm) |

| 2 | Tài khoản \*\*t\_warehouse\*\* (kho đích) | Giá trị hàng nhập vào kho | Từ SLE nhập (`stock\_value\_difference` dương) — \*\*nơi phí cần vào\*\* |

| 3 | \*\*`expense\_account` trong SE Detail\*\* | \*\*Difference Account\*\* — tài khoản cân bằng của dòng item | Mặc định từ Item / Stock Adjustment Account (`stock\_entry.py:1411,1423`) |

| 4 | \*\*`expense\_account` trong additional\_costs\*\* | Tài khoản chi phí của khoản phí (vd 6238 Phí vận chuyển) | Ghi Có khi phí được vốn hoá |



Cơ chế trung tâm (đã trình bày ở §7–§9, Q1–Q3):



```

phí → distribute\_additional\_costs() → d.additional\_cost

&#x20;   → update\_valuation\_rate():  valuation\_rate = basic\_rate + additional\_cost / transfer\_qty

&#x20;   → get\_sle\_for\_target\_warehouse(): incoming\_rate = valuation\_rate   (★ phí nằm trong incoming\_rate)

&#x20;   → SLE đích: stock\_value\_difference tăng trọn phí → GL Nợ t\_warehouse

```



`expense\_account` (SE Detail) chỉ là \*\*bên cân bằng\*\*: với mỗi SLE, GL ghi \*"Nợ tài khoản kho = SVD, Nợ âm expense = SVD"\* (`stock\_controller.py:148-211`). Nó \*\*triệt tiêu về 0\*\* khi giá trị xuất (kho nguồn) và giá trị nhập (kho đích) được nối qua cùng một tài khoản — \*\*chỉ khi phí thực sự được vốn hoá vào t\_warehouse\*\*. Nếu phí không vốn hoá được, `expense\_account` (SE Detail) trở thành "bãi đỗ" cho phần phí đó.



\---



\### 16.2. Tình huống A (CHUẨN) — `basic\_amount > 0` → phí vào t\_warehouse ✓



\*\*Điều kiện:\*\* dòng item chuyển có `basic\_rate > 0` (hệ thống tự lấy giá từ kho nguồn, hoặc người dùng nhập giá thủ công) → `basic\_amount = transfer\_qty × basic\_rate > 0`.



\*\*Test thực tế (site dev EuP, phiếu `NXK-2608-0012`):\*\* item `10114131612`, chuyển 1 từ \*\*BTP - EuP\*\* (1552) → \*\*Vật tư EUP - EuP\*\* (1531), `basic\_rate = 54497.354`, `allow\_zero\_valuation\_rate = 0`, phí \*\*100\*\* trên tài khoản \*\*6238\*\*.



\*\*GL Entry thực tế sau submit:\*\*



| Tài khoản | Nợ | Có | Nguồn |

|---|---|---|---|

| 1552 – BánThành phẩm nhập kho - EUP (\*\*s\_warehouse\*\*) | — | \*\*54497.354\*\* | SLE xuất (−54497.354) |

| 1531 – Công cụ, dụng cụ - EuP (\*\*t\_warehouse\*\*) | \*\*54597.354\*\* | — | SLE nhập (+54597.354 = basic + phí) |

| 6238 – Chi phí bằng tiền khác - EuP (\*\*tài khoản phí\*\*) | — | \*\*100\*\* | GL additional (`stock\_entry.py:1280`) |

| 6321 – Giá vốn bán hàng hóa - EUP (\*\*expense\_account SE Detail\*\*) | — | — | \*\*TRIỆT TIÊU = 0\*\* |



\*\*SLE thực tế:\*\* SLE đích có `incoming\_rate = 54597.354` (= 54497.354 + 100), `stock\_value\_difference = +54597.354` → \*\*t\_warehouse nhận trọn basic + phí\*\*. SLE nguồn `stock\_value\_difference = −54497.354`.



\*\*Bút toán chuẩn (journal-equivalent):\*\*



```

Nợ  1531 – t\_warehouse (Vật tư EUP)    54597.354   (= basic 54497.354 + phí 100)

Có  1552 – s\_warehouse (BTP)           54497.354   (giá trị rời khỏi kho nguồn)

Có  6238 – tài khoản phí                 100       (phí đã vốn hoá vào t\_warehouse)

```



> ✅ \*\*Hiểu biết của bạn là ĐÚNG trong tình huống này:\*\* phí đẩy trọn giá trị vào t\_warehouse, `expense\_account` (SE Detail) \*\*giữ nguyên (net = 0)\*\*, tài khoản phí được Có.



\---



\### 16.3. Tình huống B (NGOẠI LỆ) — `basic\_amount = 0` → phí bị Nợ vào `expense\_account` (SE Detail) ✗



\*\*Điều kiện:\*\* dòng item chuyển có `basic\_rate = 0` → `basic\_amount = 0`. Nguyên nhân thường gặp: item giá 0, hoặc \*\*Allow Zero Valuation Rate\*\* được tick, hoặc trên site EuP \*\*giá không được tự lấy\*\* (xem 16.4).



\*\*Test thực tế (site dev EuP, phiếu `NXK-2608-0011`):\*\* cùng item, cùng kho, cùng phí 100 — nhưng `basic\_rate = 0`, `allow\_zero\_valuation\_rate = 1`.



\*\*GL Entry thực tế sau submit:\*\*



| Tài khoản | Nợ | Có | Nguồn |

|---|---|---|---|

| 1552 – BánThành phẩm nhập kho - EUP (\*\*s\_warehouse\*\*) | — | \*\*54497.354\*\* | SLE xuất (−54497.354) |

| 1531 – Công cụ, dụng cụ - EuP (\*\*t\_warehouse\*\*) | — | — | \*\*KHÔNG có gì!\*\* |

| 6238 – Chi phí bằng tiền khác - EuP (\*\*tài khoản phí\*\*) | — | \*\*100\*\* | GL additional (phân bổ theo \*\*qty\*\*) |

| 6321 – Giá vốn bán hàng hóa - EUP (\*\*expense\_account SE Detail\*\*) | \*\*54597.354\*\* | — | \*\*Nợ trọn basic + phí\*\* |



\*\*SLE thực tế:\*\* SLE đích có `incoming\_rate = 0`, `stock\_value\_difference = 0` → \*\*t\_warehouse không nhận giá trị nào\*\*. Phí 100 \*\*không\*\* vào kho.



> ❌ \*\*Đây chính là hiện tượng bạn quan sát thấy:\*\* giá trị \*\*tăng ở `expense\_account` (SE Detail)\*\* thay vì t\_warehouse. Phí trở thành \*\*chi phí phát sinh\*\* (nằm trong P\&L), \*\*không\*\* nằm trên Bảng cân đối kế toán.



\*\*Vì sao xảy ra (theo mã nguồn):\*\*

1\. `distribute\_additional\_costs()` — `stock\_entry.py:806`:

&#x20;  ```

&#x20;  incoming\_items\_cost = Σ basic\_amount (các dòng có t\_warehouse)  = 0

&#x20;  if not incoming\_items\_cost: return          # ← return sớm, phí KHÔNG phân bổ

&#x20;  ```

&#x20;  → `d.additional\_cost = 0`, `valuation\_rate = basic\_rate + 0 = 0`.

2\. SLE đích nhận `incoming\_rate = valuation\_rate = 0` → `stock\_value\_difference = 0` → \*\*không có GL Nợ t\_warehouse\*\*.

3\. Nhưng `StockEntry.get\_gl\_entries()` \*\*vẫn post cặp GL additional\*\* — vì `total\_basic\_amount = 0` nên phân bổ theo \*\*qty\*\* (`:1244-1262`): Nợ `expense\_account` (SE Detail) / Có tài khoản phí.

4\. Kết quả: phần phí 100 \*\*đọng lại ở `expense\_account` (SE Detail)\*\* (cùng với basic từ SLE xuất), không được chuyển vào t\_warehouse.



\---



\### 16.4. Vì sao trên site EuP tình huống B dễ xảy ra (root cause)



Trên ERPNext \*\*chuẩn\*\*, Material Transfer tự lấy giá từ kho nguồn (`set\_rate\_for\_outgoing\_items` → `get\_incoming\_rate`), nên `basic\_amount > 0` và phí tự vốn hoá — tình huống B hiếm. Nhưng trên site EuP có \*\*2 yếu tố custom\*\* khiến `basic\_rate = 0` thành trạng thái mặc định:



1\. \*\*eupapp tắt tự lấy giá cho dòng xuất\*\* — `eupapp/.../overrides/stock\_entry.py:1515` `set\_rate\_for\_outgoing\_items`: phần `get\_incoming\_rate(...)` bị \*\*comment\*\* (chỉ còn `basic\_amount = transfer\_qty × basic\_rate`). → Dòng chuyển kho \*\*không tự điền giá\*\* từ kho nguồn; nếu người dùng không nhập `basic\_rate` thì nó là \*\*0\*\*.



2\. \*\*Property Setter mặc định `allow\_zero\_valuation\_rate = 1`\*\* — `eupapp/eup\_stock/custom/stock\_entry\_detail.json:2284-2298` (`Stock Entry Detail-allow\_zero\_valuation\_rate-default`, value = `"1"`). → Dòng item mới \*\*mặc định tick "Allow Zero Valuation Rate"\*\*; kết hợp với (1) thì `basic\_rate` bị ép về 0 / không được lấy.



> UI chuẩn ERPNext có thể tự tắt flag này khi chọn `s\_warehouse` (`stock\_entry.js:744-747`), nhưng nếu tạo phiếu qua API/import/script (hoặc flow eupapp tự sinh phiếu từ YCSX/WO/Bảng cộng đơn — vd `yeu\_cau\_xuat\_hang.py:1588`, `work\_order.py:665` đặt `allow\_zero\_valuation\_rate: 1`) thì dòng vẫn giữ mặc định → phí rơi ra ngoài kho.



\---



\### 16.5. Cách hạch toán chuẩn \& hướng xử lý



\*\*Để phí VÀO giá trị kho (đúng nghiệp vụ):\*\*



\- \[ ] Dòng item chuyển phải có `basic\_rate > 0` (nhập giá thủ công, hoặc đảm bảo hệ thống tự lấy). Kiểm tra sau khi Save: `basic\_amount > 0`.

\- \[ ] Bỏ tick \*\*Allow Zero Valuation Rate\*\* trên dòng (nếu item không phải loại giá 0).

\- \[ ] Điền `additional\_costs` \*\*trước\*\* khi Save (để `distribute\_additional\_costs` chạy đúng lúc validate).

\- \[ ] Sau Save, xem trước `valuation\_rate` của dòng đích: phải bằng `basic\_rate + phí/qty`. Nếu `additional\_cost = 0` → phí sẽ không vào kho (tình huống B).

\- \[ ] Sau Submit, kiểm tra GL: t\_warehouse Nợ đủ (basic + phí), `expense\_account` (SE Detail) net = 0, tài khoản phí Có.



\*\*Nếu đã lỡ post theo tình huống B (phí đọng ở `expense\_account` SE Detail), sửa theo 1 trong 3 cách:\*\*



| Cách | Thao tác | Ghi chú |

|---|---|---|

| 1. Cancel \& resubmit | Cancel phiếu → nhập đúng `basic\_rate` / bỏ tick Allow Zero → resubmit | Chuẩn nhất khi phiếu vừa mới post, chưa ảnh hưởng chuỗi |

| 2. Journal Entry bù trừ | `Nợ t\_warehouse (1531) 100 / Có expense\_account (6321) 100` | Chuyển phần phí từ P\&L vào giá trị kho; phải tự tính + ghi chú rõ |

| 3. Landed Cost Voucher | Tạo LCV bổ sung phí cho dòng (nếu là Purchase Receipt) | Phương án chuẩn của ERPNext cho phí phát sinh sau nhập kho |



> \*\*Nguyên tắc kế toán cần nhớ:\*\* Nếu khoản phí là chi phí vận chuyển/logistics của hàng nhập → \*\*phải vốn hoá vào giá trị hàng tồn kho\*\* (bản chất "giá gốc hàng tồn kho" theo chuẩn mực kế toán). Nếu để phí rơi vào P\&L ngay lúc chuyển kho thì \*\*giá trị kho không phản ánh chi phí thực\*\* — sai nguyên tắc giá gốc, đồng thời làm \*\*giá vốn hàng bán sau này thấp hơn\*\* và \*\*chi phí phát sinh tăng ngay trong kỳ\*\*.



\---



\### 16.6. Bảng so sánh hai tình huống (cùng 1 giao dịch: basic 54497.354 + phí 100)



| Hạng mục | A — Chuẩn (`basic\_amount > 0`) | B — Ngoại lệ (`basic\_amount = 0`) |

|---|---|---|

| `distribute\_additional\_costs` | Chạy: `additional\_cost = 100` | Return sớm: `additional\_cost = 0` (`:818`) |

| `valuation\_rate` dòng đích | `54497.354 + 100 = 54597.354` | `0` |

| SLE đích `incoming\_rate` | \*\*54597.354\*\* | \*\*0\*\* |

| SLE đích `stock\_value\_difference` | \*\*+54597.354\*\* | \*\*0\*\* |

| GL t\_warehouse (1531) | \*\*Nợ 54597.354\*\* | \*(không có)\* |

| GL s\_warehouse (1552) | Có 54497.354 | Có 54497.354 |

| GL tài khoản phí (6238) | Có 100 | Có 100 |

| GL `expense\_account` SE Detail (6321) | \*\*net = 0\*\* | \*\*Nợ 54597.354\*\* (phí đọng ở đây) |

| Phí vào giá trị kho? | ✅ Có | ❌ Không (phí vào P\&L) |

| Kết quả trên Bảng cân đối | Phí nằm trong tài sản tồn kho | Phí là chi phí trong kỳ |



\---



\## 17. Nghiên cứu case thực tế — NXK-2608-0009-1 (frappe-dev nxc16, ERPNext 14.92.14)



> Case do TESTER1 tạo để QA "S1a Qty canonical (GL parity)". Đây là phiếu \*\*Material Transfer\*\*

> có phí tăng thêm, đủ 4 tài khoản, tạo đủ GL + SLE nhưng \*\*phí chưa phân bổ chuẩn vào t\_warehouse\*\*

> (giá trị kho BTP không tăng dù GL đã ghi nhận phí). Mục này đối chiếu \*\*dữ liệu thật\*\* với \*\*code core\*\*

> để trả lời "tại sao".



\### 17.1 Mô tả phiếu \& dữ liệu thật (trạng thái live, `is\_cancelled=0`)



\- \*\*Type:\*\* Material Transfer — 3 dòng: `10101012107 × 1`, `10114131612 × 1`, `504010195 × 25`

&#x20; (Vật tư EUP → BTP), `allow\_zero\_valuation\_rate = 1`.

\- \*\*`expense\_account` SE Detail:\*\* `2443 - Cầm cố, thế chấp`.

\- \*\*`additional\_costs`:\*\* 1 dòng `expense\_account = 3333 - Thuế XNK`, `base\_amount = 5,000,000`,

&#x20; `custom\_total\_allocated\_amount = 6,000,000`; `total\_additional\_costs = 5,000,000`.



Bảng \*\*SE Detail hiện tại\*\* (gọi `distribute\_additional\_costs` + `update\_valuation\_rate` = chạy trên bản copy in-memory để so sánh):



| Item | `basic\_rate` | `additional\_cost` (trên phiếu) | `valuation\_rate` (trên phiếu) | `amount` (trên phiếu) | Core sẽ tính `valrate` | Core sẽ tính `amount` |

|---|---|---|---|---|---|---|

| 10101012107 | 18,571.429 | 222,222.222 | \*\*44,497.354\*\* | 44,497.355 | 92,184.114 | 92,184.115 |

| 10114131612 | 28,571.429 | 222,222.222 | \*\*54,497.354\*\* | 54,497.355 | 141,821.713 | 141,821.714 |

| 504010195 | 48,571.429 | 5,555,555.556 | \*\*74,497.354\*\* | 1,862,433.862 | 241,096.910 | 6,027,422.744 |

| \*\*Σ đích\*\* | | \*\*6,000,000\*\* (chia theo \*\*Qty\*\*) | | \*\*1,961,428.572\*\* | | \*\*6,261,428.573\*\* (gồm phí 5M) |



\- `additional\_cost` trên phiếu = \*\*6,000,000\*\* chia theo \*\*Qty\*\* (6,000,000/27) — không phải chia theo `basic\_amount`.

\- `valuation\_rate` trên phiếu = \*\*giá BTP đang tồn kho\*\* (44,497.354 / 54,497.354 / 74,497.354) — KHÔNG phải `basic\_rate + additional\_cost/qty`.

\- `amount` = `valuation\_rate × transfer\_qty` → \*\*phí 6M bị kẹt ở cột `additional\_cost`, không vào `amount`/`valuation\_rate`\*\*.



\### 17.2 Lớp SLE / giá trị kho — phí KHÔNG vào t\_warehouse



\- SLE đích (BTP) `incoming\_rate` = 44,497.354 / 54,497.354 / 74,497.354 → `stock\_value\_difference` Σ = \*\*+1,961,428.57\*\* (không phí).

\- SLE nguồn (Vật tư EUP) Σ = \*\*−1,261,428.571\*\*.

\- Bin BTP xác nhận \*\*không đổi\*\*: 10101012107→44,497.354, 10114131612→54,497.354, 504010195→74,497.354.



→ \*\*Phí 6,000,000 không đi vào giá trị tồn kho BTP.\*\* Đây chính là "chưa phân bổ chuẩn vào t\_warehouse" mà Owner quan sát thấy.



\*\*Vì sao ở code core:\*\* bước duy nhất đưa phí vào giá trị kho là `update\_valuation\_rate()` (`stock\_entry.py:830`):



```python

d.amount = d.basic\_amount + d.additional\_cost

d.valuation\_rate = flt(d.basic\_rate) + (flt(d.additional\_cost) / flt(d.transfer\_qty))

```



Hàm này chỉ chạy ngay sau `distribute\_additional\_costs()` (tính `additional\_cost` từ bảng `additional\_costs` theo `basic\_amount`). Trên phiếu này:

1\. `additional\_cost` được ghi \*\*bằng cơ chế custom\*\* (`custom\_total\_allocated\_amount`, chia theo Qty = 6M) — khác hoàn toàn `total\_additional\_costs = 5M`.

2\. `valuation\_rate`/`amount` bị \*\*set cứng = giá BTP cũ\*\* → nếu `update\_valuation\_rate` chạy trước, kết quả bị ghi đè; nếu chạy sau, nó sẽ tính lại theo `additional\_cost` nhưng phiếu không giữ kết quả đó.



Kết quả: \*\*`incoming\_rate` của SLE đích lấy thẳng `valuation\_rate` của dòng\*\* → không có phí → giá trị kho không tăng.



\### 17.3 Lớp GL — GL live KHÔNG do code core hiện tại sinh ra



Lịch sử GL của phiếu (theo từng vòng submit/cancel) cho thấy \*\*2 cấu trúc khác nhau với CÙNG dữ liệu\*\*:



| Vòng | 1552 (t\_warehouse) | 2443 (expense SE Detail) | 1531 (s\_warehouse) | 3333 (phí) | Nguồn gốc |

|---|---|---|---|---|---|

| \*\*09:10:28\*\* (submit bị cancel) | Nợ \*\*1,961,428.57\*\* | Nợ \*\*5,300,000.001\*\* | Có 1,261,428.571 | Có \*\*6,000,000\*\* | ✅ \*\*Đúng code core\*\* |

| \*\*09:37:46\*\* (live) | Nợ \*\*7,961,428.57\*\* | Có \*\*699,999.999\*\* | Có 1,261,428.571 | Có \*\*6,000,000\*\* | ⚠️ \*\*Không phải code core\*\* |



\- \*\*09:10:28\*\* chính là output chuẩn của `StockEntry.get\_gl\_entries` (`stock\_entry.py:1234`):

&#x20; - Phần base (từ SLE): 1552 Nợ Σ SVD đích = 1,961,428.57; 1531 Có Σ|SVD nguồn| = 1,261,428.571; 2443 Có chênh lệch (|nguồn| − đích) = 699,999.999.

&#x20; - Phần additional: 3333 Có 6,000,000; \*\*2443 Nợ 6,000,000\*\* (phí đi vào `expense\_account` của SE Detail).

&#x20; - Net 2443 = Nợ 6,000,000 − Có 699,999.999 = \*\*Nợ 5,300,000.001\*\* ✓ khớp tuyệt đối.

\- \*\*09:37:46 (live)\*\*: phí 6,000,000 bị dời khỏi 2443 sang \*\*1552\*\* (t\_warehouse) → 1552 = 1,961,428.57 + 6,000,000 = 7,961,428.57. Cấu trúc này giống \*\*vốn hoá phí vào kho\*\* (như Landed Cost) nhưng \*\*không có bất kỳ code nào trong repo eupapp hiện tại sinh ra nó\*\*:

&#x20; - `make\_gl\_entries` override của `EupStockEntry` \*\*đã comment\*\* (`stock\_entry.py:1449`); `make\_gl\_entries\_inventory` (:1889) là \*\*module-level dead code\*\*, không phải override class (đã xác minh `has\_make\_gl=False` trên class đang chạy).

&#x20; - `get\_gl\_entries` core v14 luôn đưa phí vào `d.expense\_account` (2443).

&#x20; - Không có Server Script, không có `runtime\_patch`, `EupGLEntry` chỉ no-op `validate\_currency`.



→ \*\*GL live được tạo bằng cách truyền một danh sách `gl\_entries` custom vào `make\_gl\_entries(gl\_entries=...)`\*\* (tham số này core cho phép) hoặc sửa trực tiếp GL — đúng tinh thần script QA "GL parity" của TESTER1. Vì GL được dựng tay nhưng \*\*SLE/Bin không được tính lại\*\*, kết quả là \*\*GL lệch giá trị kho 6,000,000\*\*.



\### 17.4 Ba kịch bản hạch toán cho chuyển kho có phí



| Kịch bản | 1552 (t\_warehouse) | 1531 (s\_warehouse) | 3333 (phí) | 2443 (expense SE Detail) | GL = SLE? |

|---|---|---|---|---|---|

| \*\*A. Chuẩn core (phí = chi phí, không vốn hoá)\*\* | Nợ 1,961,428.57 | Có 1,261,428.571 | Có 5,000,000 (hoặc 6M) | Nợ = phí − chênh lệch | ✅ |

| \*\*B. Chuẩn vốn hoá phí vào kho\*\* (`update\_valuation\_rate` chạy đúng) | Nợ \*\*6,261,428.57\*\* | Có 1,261,428.571 | Có \*\*5,000,000\*\* | \*\*≈ 0\*\* (triệt tiêu) | ✅ |

| \*\*C. Trạng thái live NXK-2608-0009-1 (lệch)\*\* | Nợ 7,961,428.57 | Có 1,261,428.571 | Có 6,000,000 | Có 699,999.999 | ❌ \*\*lệch 6,000,000\*\* |



\- \*\*Kịch bản B\*\* là cái Owner mong đợi ("phí đẩy giá trị vào t\_warehouse, expense\_account giữ nguyên"). Muốn đạt được: phí phải vào `amount`/`valuation\_rate` của SE Detail → `update\_valuation\_rate` phải chạy và giữ kết quả → SLE đích `incoming\_rate` tăng → GL đích tăng theo. Khi đó 2443 tự về \~0 vì phần "chênh lệch" mà nó đang gánh đã được phí bù đắp.

\- \*\*Kịch bản C\*\* xảy ra khi GL được "vốn hoá" một mình (custom GL list) mà SLE không đổi → mất cân đối giữa sổ kế toán (1552) và giá trị kho (Bin/SLE).



\### 17.5 Kết luận \& hướng xử lý chuẩn



1\. \*\*Nguyên nhân "chưa phân bổ chuẩn vào t\_warehouse":\*\* phí được ghi vào cột `additional\_cost` (cơ chế custom, chia theo Qty = 6M) nhưng \*\*không được cộng vào `valuation\_rate`/`amount`\*\* — bước `update\_valuation\_rate()` (core) không chạy/không giữ kết quả → SLE đích `incoming\_rate` giữ giá BTP cũ → giá trị kho BTP không tăng.

2\. \*\*Bất nhất GL–kho:\*\* GL live ghi nhận phí 6M nợ 1552 (vốn hoá) trong khi SLE/Bin không có phí → \*\*GL lệch giá trị kho 6,000,000\*\*. GL này không do code core hiện tại tạo (đã đối chiếu với cycle 09:10:28 chuẩn).

3\. \*\*Hạch toán chuẩn cần đạt\*\* (kịch bản B): `1552 Nợ 6,261,428.57 | 1531 Có 1,261,428.571 | 3333 Có 5,000,000 | 2443 ≈ 0`, kèm SLE đích `incoming\_rate` = basic + phí/qty → \*\*GL và giá trị kho khớp nhau\*\*. \*\*Về chuẩn kế toán Việt Nam: chọn B — thuế nhập khẩu bắt buộc vốn hoá vào giá gốc hàng tồn kho (VAS 02 / TT 200/2014), KHÔNG có phương án A cho loại phí này.\*\* Chi tiết căn cứ + phương án xử lý chuẩn xem \[§18](#18-kết-luận-chuẩn-nghiệp-vụ-kế-toán--a-hay-b-phương-án-xử-lý).

4\. \*\*Hành động đề xuất:\*\* thống nhất một trong hai chuẩn (A hoặc B) cho eupapp, đảm bảo bước `update\_valuation\_rate` (hoặc logic tương đương) chạy đúng khi có phí; \*\*không dựng GL tay\*\* trong flow submit — nếu cần GL "vốn hoá" thì phải tính lại SLE cùng lúc. Phiếu TEST hiện tại nên cancel + tạo lại theo chuẩn đã chọn.



\---



\## 18. Kết luận chuẩn nghiệp vụ kế toán — A hay B? \& phương án xử lý



\### 18.1 Câu trả lời ngắn gọn



\*\*Chọn B — vốn hoá phí vào giá trị kho (t\_warehouse).\*\*



Loại phí trong NXK-2608-0009-1 là \*\*thuế nhập khẩu\*\* (`3333 - Thuế xuất, nhập khẩu`). Theo Chuẩn mực kế toán Việt Nam \*\*VAS 02 — Hàng tồn kho\*\* và \*\*Thông tư 200/2014/TT-BTC\*\*, thuế nhập khẩu là \*\*chi phí thu mua, bắt buộc tính vào giá gốc hàng tồn kho\*\* — KHÔNG phải chi phí trong kỳ. Kịch bản A chỉ đúng khi phí là chi phí thuần (bán hàng/quản lý) — không áp dụng cho thuế nhập khẩu.



\### 18.2 Căn cứ pháp lý \& nguyên tắc kế toán



| Căn cứ | Nội dung |

|---|---|

| \*\*VAS 02\*\* (Chuẩn mực Hàng tồn kho) | Giá gốc hàng tồn kho = chi phí mua + chi phí chế biến + chi phí liên quan trực tiếp khác để đưa hàng đến \*\*địa điểm và trạng thái hiện tại\*\*. Thuế nhập khẩu nằm trong chi phí mua. |

| \*\*TT 200/2014/TT-BTC\*\* (Điều 15) | Chi phí mua gồm giá mua, \*\*các loại thuế không được hoàn lại\*\* (thuế nhập khẩu, thuế TTĐB, thuế BVMT...) và chi phí vận chuyển, bốc dỡ... |

| Bản chất nghiệp vụ | Thuế nhập khẩu là \*\*nghĩa vụ nộp Nhà nước\*\* → ghi \*\*Có 3333\*\* (thuế phải nộp). Đối ứng đúng là \*\*tài sản hàng tồn kho\*\* (Nợ 152/153/155) — \*\*không phải chi phí trong kỳ\*\*. |



→ Bản ghi chuẩn: \*\*Nợ TK hàng tồn kho, Có 3333\*\* — đúng chữ ký của Kịch bản B.



\### 18.3 Vì sao A sai trong case này



Kịch bản A đưa thuế nhập khẩu vào `expense\_account` của SE Detail (2443) như chi phí trong kỳ. Sai vì:

1\. Thuế nhập khẩu không được hoàn lại → phải nằm trong giá gốc, không phải chi phí kỳ.

2\. Làm \*\*hàng tồn kho thiếu 6,000,000\*\* trên Bảng cân đối kế toán.

3\. 2443 là \*\*Cầm cố, thế chấp\*\* (tài khoản phải thu) → nếu phí rơi vào đây, tạo \*\*khoản phải thu không có thực\*\*, sai bản chất tài khoản.



\### 18.4 Bản hạch toán chuẩn (Kịch bản B) — với X = số thuế thật



Giả định số thuế thực tế là \*\*X\*\* (phải xác minh 5,000,000 hay 6,000,000 — xem 18.6):



| TK | Nợ | Có | Diễn giải |

|---|---|---|---|

| 1552 (BTP / t\_warehouse) | \*\*1,261,428.571 + X\*\* | — | Giá trị hàng chuyển vào + thuế vốn hoá vào kho |

| 1531 (Vật tư / s\_warehouse) | — | \*\*1,261,428.571\*\* | Xuất kho Vật tư theo giá gốc |

| 3333 (Thuế XNK) | — | \*\*X\*\* | Thuế nhập khẩu phải nộp |

| 2443 (expense SE Detail) | — | — | \*\*Triệt tiêu ≈ 0\*\* (không còn vai trò) |



Với X = 6,000,000: \*\*Nợ 1552: 7,261,428.571 | Có 1531: 1,261,428.571 | Có 3333: 6,000,000\*\* — cân đối, và SLE đích `incoming\_rate` = basic + X/qty → \*\*giá trị kho BTP tăng đúng X → GL = SLE\*\*.



\### 18.5 Phương án xử lý chuẩn nghiệp vụ (đề xuất triển khai)



\*\*4 lỗi đang tồn tại trên phiếu cần sửa:\*\*



| # | Lỗi | Hậu quả |

|---|---|---|

| 1 | `total\_additional\_costs` (5M) ≠ `custom\_total\_allocated\_amount` (6M) | Số thuế mâu thuẫn, không xác định được giá trị vốn hoá |

| 2 | `update\_valuation\_rate()` không chạy / không giữ kết quả | Phí không vào `valuation\_rate`/`amount` → SLE không tăng → \*\*GL–kho lệch 6M\*\* |

| 3 | `expense\_account` SE Detail = 2443 (Cầm cố/thế chấp) | Sai bản chất tài khoản (tài khoản phải thu) |

| 4 | GL được dựng tay (custom `gl\_entries`) | Không qua core → mất nhất quán, không repost được |



\*\*Quy trình chuẩn (chuẩn nhất — khuyến nghị):\*\*



| Bước | Nội dung | Công cụ |

|---|---|---|

| 1 | \*\*Vốn hoá thuế nhập khẩu tại khâu nhập kho\*\* (hàng vào Vật tư EUP): Nợ 152, Có 3333 → giá Vật tư EUP đã gồm thuế | \*\*Landed Cost Voucher / NxCostAllocation\*\* (công cụ ERPNext đúng đắn, có audit trail + repost) |

| 2 | Chuyển kho (Material Transfer) chỉ \*\*dịch chuyển giá trị\*\*: Nợ 1552, Có 1531 — \*\*không phí, không 3333\*\* | Stock Entry thuần |

| 3 | Chặn `additional\_costs` gán thuế nhập khẩu lên phiếu chuyển (validate) | eupapp hook |



\*\*Nếu vẫn gom thuế vào phiếu chuyển (không qua LCV) — đường tối thiểu:\*\* phải làm đủ (a) sửa `base\_amount`/`total\_additional\_costs` = số thuế thật, bỏ `custom\_total\_allocated\_amount` trùng; (b) đảm bảo `update\_valuation\_rate()` chạy và ghi đè đúng để `amount`/`valuation\_rate` gồm phí → SLE đích tăng; (c) thay `expense\_account` 2443 bằng tài khoản hợp lý (trong B tài khoản này tiến về 0); (d) \*\*bỏ hẳn dựng GL tay\*\* — để core sinh GL từ SLE (GL tự khớp).



\*\*Xử lý phiếu hiện tại (NXK-2608-0009-1):\*\*

1\. \*\*Cancel\*\* phiếu (xoá GL/SLE dựng sai).

2\. Tạo lại theo 1 trong 2 đường: (1) LCV/NxCostAllocation vốn hoá thuế tại khâu nhập → transfer thuần; hoặc (2) transfer + phí đúng số liệu + `update\_valuation\_rate` chạy đúng.

3\. Sau khi tạo lại, \*\*đối chiếu GL = SLE\*\*: Σ SVD đích = Nợ 1552.



\### 18.6 Số thuế thật là 5,000,000 hay 6,000,000?



\- `total\_additional\_costs` (5M) và `custom\_total\_allocated\_amount` (6M) đang \*\*khác nhau\*\* trên cùng phiếu.

\- Phải xác nhận với bộ phận thuế / số liệu nhập khẩu: \*\*số thuế nhập khẩu thực tế phải nộp\*\*.

\- Sau khi có X, dùng đúng X ở mọi nơi: `base\_amount`, `total\_additional\_costs`, GL 3333, giá trị vốn hoá vào t\_warehouse.



\---



\## Phụ lục A — Bản đồ hàm nhanh (cheat sheet)



| Chức năng | Hàm | File:Line |

|---|---|---|

| Entry point submit | `StockEntry.on\_submit` | `stock\_entry.py:169` |

| Tính giá trị chứng từ | `calculate\_rate\_and\_amount` | `stock\_entry.py:686` |

| Đơn giá cơ bản | `set\_basic\_rate` | `stock\_entry.py:694` |

| Rate dòng xuất | `set\_rate\_for\_outgoing\_items` | `stock\_entry.py:751` |

| Rate FG (Manufacture) | `get\_basic\_rate\_for\_manufactured\_item` | `stock\_entry.py:794` |

| \*\*Phân bổ phí\*\* | `distribute\_additional\_costs` | `stock\_entry.py:806` |

| Gộp phí vào amount/rate | `update\_valuation\_rate` | `stock\_entry.py:830` |

| Tổng In/Out + chênh lệch | `set\_total\_incoming\_outgoing\_value` | `stock\_entry.py:837` |

| Tạo SLE | `update\_stock\_ledger` / `get\_sle\_for\_source\_warehouse` / `get\_sle\_for\_target\_warehouse` | `stock\_entry.py:1172/1197/1218` |

| GL của Stock Entry (+ phí) | `StockEntry.get\_gl\_entries` | `stock\_entry.py:1234` |

| GL nền (mọi chứng từ kho) | `StockController.get\_gl\_entries` | `stock\_controller.py:148` |

| Điều kiện sinh GL | `StockController.make\_gl\_entries` | `stock\_controller.py:69` |

| Dict SLE chuẩn | `get\_sl\_entries` | `stock\_controller.py:422` |

| Valuation chính | `process\_sle` | `stock\_ledger.py:551` |

| Rate động khi recalc | `get\_dynamic\_incoming\_outgoing\_rate` / `get\_incoming\_outgoing\_rate\_from\_transaction` | `stock\_ledger.py:730/740` |

| Recalc rate trên chứng từ | `recalculate\_amounts\_in\_stock\_entry` | `stock\_ledger.py:857` |

| Moving Average | `get\_moving\_average\_values` | `stock\_ledger.py:1033` |

| FIFO/LIFO | `update\_queue\_values` | `stock\_ledger.py:1072` |

| Batchwise | `update\_batched\_values` | `stock\_ledger.py:1120` |

| Lấy giá nhập cho dòng xuất | `get\_incoming\_rate` | `utils.py:270` |

| Lấy valuation rate fallback | `get\_valuation\_rate` | `stock\_ledger.py:1435` |

| Chuẩn hoá additional\_costs | `init\_landed\_taxes\_and\_totals` | `taxes\_and\_totals.py:1126` |

| Repost chuỗi | `repost\_future\_sle\_and\_gle` | `stock\_controller.py:896` |

| Nạp phí vận hành/non-stock cho Manufacture | `add\_additional\_cost` | `bom.py:1192` |



\---



\*Tài liệu được tổng hợp từ mã nguồn ERPNext v15 — luôn đối chiếu với mã đang chạy thực tế khi có custom override.\*



