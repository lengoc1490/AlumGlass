# Hướng Dẫn Tính Toán Giá Thành — NxCost Period (A–Z)

> **Phiên bản:** EuP/eupapp · **Module:** `NxCostPeriod`  
> **Mục tiêu:** Tài liệu tham chiếu đầy đủ, từ khái niệm đến từng dòng code, cho kế toán và developer.

---

## Mục Lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Mô hình toán học](#2-mô-hình-toán-học)
3. [Vòng đời Document (Lifecycle)](#3-vòng-đời-document-lifecycle)
4. [Bước 1 — Lấy dữ liệu (get_cost_details)](#4-bước-1--lấy-dữ-liệu-get_cost_details)
5. [Bước 2 — Phân bổ chi phí gián tiếp CPC](#5-bước-2--phân-bổ-chi-phí-gián-tiếp-cpc)
6. [Bước 3 — Tính giá thành (calculate)](#6-bước-3--tính-giá-thành-calculate)
7. [Bước 4 — Submit: Cập nhật Stock & GL](#7-bước-4--submit-cập-nhật-stock--gl)
8. [Bước 5 — Tạo Journal Entry kết chuyển](#8-bước-5--tạo-journal-entry-kết-chuyển)
9. [Hủy (Cancel)](#9-hủy-cancel)
10. [Validation rules](#10-validation-rules)
11. [Giải thích các trường dữ liệu chính](#11-giải-thích-các-trường-dữ-liệu-chính)
12. [Sơ đồ luồng tổng thể](#12-sơ-đồ-luồng-tổng-thể)

---

## 1. Tổng Quan Kiến Trúc

```
NxCostPeriod (Document)
│
├── costing_sheet_details[]   ← Chi phí gián tiếp (CPC) theo tài khoản GL
│   ├── account               ← Tài khoản kế toán
│   ├── component_code        ← Mã thành phần chi phí
│   ├── allocate_base_on      ← Machine hours / Production volume
│   ├── allocated_amount      ← Số tiền phân bổ
│   └── cost_item (JSON)      ← Chi tiết phân bổ theo từng WO
│
└── json_data (JSON)          ← Dữ liệu tính toán chính
    └── data[]                ← List LSX (Work Orders)
        ├── voucher_name      ← Mã Work Order
        ├── direct_cost       ← Chi phí trực tiếp (từ GL Entry)
        ├── indirect_cost     ← Chi phí gián tiếp đã phân bổ
        ├── finish_goods_qty  ← Số lượng TP xuất kho
        ├── semi_finish_goods_qty ← Số lượng BTP xuất kho
        ├── fn_unit_cost      ← Đơn giá thành phẩm (ẩn số x_i)
        ├── semi_unit_cost    ← Đơn giá BTP
        └── semi_product_input_detail[] ← Danh sách BTP/TP tiêu hao từ WO khác
```

**Nguồn dữ liệu đầu vào:**

| Bảng | Vai trò |
|------|---------|
| `tabGL Entry` | Chi phí trực tiếp theo Work Order |
| `tabNxCost Component` / `Item` | Danh mục thành phần chi phí, phương pháp phân bổ |
| `tabBao cao ca San luong` | Giờ máy, sản lượng thực tế theo ca |
| `tabStock Entry Detail` | Số lượng TP/BTP xuất kho (Manufacture) |
| `tabBatch` | Liên kết batch → Work Order |
| `tabWork Order` | Thông tin LSX, production_item, sf_item_code |

---

## 2. Mô Hình Toán Học

### Phương trình cơ bản cho LSX i

```
x_i = DC_i/TQ_i  +  IC_i/FG_i
      + Σ_{j ∈ BTP, is_fg=0}  (qty_j × SUC_j) / FG_i     ← hằng số b_fn
      + Σ_{j ∈ TP,  is_fg=1}  (qty_j × x_j)   / FG_i     ← ẩn số (coeff)
```

**Trong đó:**

| Ký hiệu | Ý nghĩa |
|---------|---------|
| `x_i` | Đơn giá thành phẩm của LSX i (fn_unit_cost) |
| `DC_i` | Tổng chi phí trực tiếp của LSX i |
| `TQ_i` | Tổng số lượng xuất kho (TP + BTP) = FG_i + SFG_i |
| `IC_i` | Chi phí gián tiếp đã phân bổ (indirect_cost) |
| `FG_i` | Số lượng thành phẩm (finish_goods_qty) |
| `SUC_j` | Đơn giá BTP của LSX j = DC_j / TQ_j |
| `qty_j` | Số lượng BTP/TP từ LSX j tiêu hao vào LSX i |

### Dạng ma trận

```
(I − A) · x = b

A[i][j] = qty_fg_ij / FG_i      (chỉ khi is_fg=1, tức TP → TP)
b[i]    = DC_i/TQ_i + IC_i/FG_i + Σ(BTP_j × SUC_j)/FG_i
```

### 4 tình huống giải hệ

| Tình huống | Cách xử lý | Ví dụ |
|-----------|-----------|-------|
| **Độc lập** | x = b | LSX không dùng BTP/TP từ LSX khác |
| **Tuần tự** | x = b + Σ(coeff × x_dep đã giải) | LSX A dùng TP từ LSX B (B giải trước) |
| **Quay vòng** | Gaussian (I−A)x=b, fallback Gauss-Seidel | LSX A và B dùng TP của nhau |
| **Hỗn hợp** | Kết hợp tuần tự + Gaussian theo SCC | Nhóm phức tạp |

Thuật toán **Tarjan SCC** (Strongly Connected Components) tự động phát hiện nhóm quay vòng. Engine `solve_linear_on_graph` xử lý toàn bộ 4 trường hợp.

---

## 3. Vòng Đời Document (Lifecycle)

```
DRAFT
  │
  ├─► get_cost_details()           ← Lấy dữ liệu từ DB
  ├─► update_costing_sheet_details() ← Lấy chi phí gián tiếp CPC
  ├─► calculate()                  ← Tính giá thành
  │
  ▼
[before_submit]
  ├─► validate_work_order_complete() ← WO phải ở trạng thái Complete
  └─► validate_repost_item_valuation() ← Không được có repost đang chạy

[on_submit]
  ├─► update_gl_entry()            ← Đánh dấu custom_allocated trên GL
  ├─► update_stock()               ← Ghi incoming_rate vào SLE, repost
  └─► make_journal_entry()         ← Tạo JE kết chuyển WIP

SUBMITTED
  │
[before_cancel]
  └─► update_ref_nxcost_period()   ← Xóa against_voucher trên GL

[on_cancel]
  ├─► cancel_journal_entry()       ← Hủy JE kết chuyển
  ├─► update_gl_entry()            ← Hoàn trả custom_allocated
  └─► cancel_gl_entry()            ← Reset SLE rates, repost lại
```

---

## 4. Bước 1 — Lấy Dữ Liệu (`get_cost_details`)

### 4.1 Luồng quyết định

```python
if docstatus == 1:          # Document đã submit
    → Đọc json_data đã lưu (không query lại DB)
elif voucher_type == "Work Order":
    → _fetch_cost_data_from_db()   # Query DB
```

### 4.2 Query SQL chính (`_fetch_cost_data_from_db`)

Query gồm 4 CTE (Common Table Expression) chạy song song:

#### CTE 1: `bcc_data` — Giờ máy & Sản lượng
```sql
SELECT bccsl.work_order,
       SUM(bccsl.total_time)    AS total_time,     -- Tổng giờ máy
       SUM(bccsl.actual_output) AS actual_output    -- Tổng sản lượng thực tế
FROM `tabBao cao ca San luong` bccsl
JOIN `tabBao cao ca san xuat` bccsx ...
WHERE bccsx.date BETWEEN '{pf}' AND '{pt}'
GROUP BY bccsl.work_order
```

#### CTE 2: `direct_account` — Danh sách tài khoản chi phí trực tiếp
```sql
SELECT cci.account, cc.component_code, cc.component_name, cc.method
FROM `tabNxCost Component Item` cci
JOIN `tabNxCost Component` cc ...
WHERE cc.company = '{co}'
  AND (cc.method = 'Trực tiếp' OR account không thuộc Gián tiếp)
GROUP BY cci.account
```
> Logic: Tài khoản được phân loại "Trực tiếp" nếu có trong NxCost Component method='Trực tiếp', HOẶC không nằm trong danh sách "Gián tiếp" của công ty.

#### CTE 3: `gl_data` — Chi phí trực tiếp từ GL Entry
```sql
SELECT gl.work_order,
       SUM(CASE WHEN da.account IS NOT NULL THEN gl.debit - gl.credit ELSE 0 END) AS direct_cost,
       CONCAT('[', GROUP_CONCAT(...), ']') AS gl_entries   -- JSON chi tiết từng GL
FROM `tabGL Entry` gl
JOIN `tabWork Order` wo  ON wo.name = gl.work_order
JOIN `tabItem` item      ON item.name = wo.production_item
JOIN `tabItem Group` ig  ON ig.name = item.item_group
LEFT JOIN direct_account da ON da.account = gl.account
WHERE gl.posting_date BETWEEN '{pf}' AND '{pt}'
  AND ig.custom_cost_object_type = 'Work Order'
GROUP BY gl.work_order
HAVING MAX(CASE WHEN da.account IS NOT NULL THEN 1 ELSE 0 END) = 1
       -- Chỉ lấy WO có ít nhất 1 GL entry thuộc direct_account
```

#### CTE 4: `incomming_stock` — Số lượng xuất kho
```sql
SELECT se.work_order AS wo_name,
    SUM(CASE WHEN item = sf_item_code AND purpose='Manufacture' THEN qty ELSE 0 END) AS btp_qty,
    SUM(CASE WHEN item = production_item AND purpose='Manufacture' THEN qty ELSE 0 END) AS tp_qty,
    SUM(CASE WHEN purpose='Material Consumption for Manufacture' AND batch thuộc WO hiện kỳ
             THEN qty ELSE 0 END) AS semi_product_input,
    GROUP_CONCAT(DISTINCT ...) AS semi_product_input_detail,  -- JSON danh sách WO nguồn BTP
    GROUP_CONCAT(DISTINCT ...) AS voucher_detail_no,           -- Mã SED để update SLE
    GROUP_CONCAT(DISTINCT ...) AS sf_item_code,
    GROUP_CONCAT(DISTINCT ...) AS sf_batch_no
FROM `tabStock Entry Detail` sed
JOIN `tabStock Entry` se ...
JOIN `tabWork Order` wo ON wo.name = se.work_order
WHERE se.posting_date BETWEEN '{pf}' AND '{pt}'
  AND pu.purpose IN ('Manufacture', 'Material Transfer for Manufacture',
                     'Material Consumption for Manufacture')
GROUP BY se.work_order
```

#### SELECT cuối — Merge tất cả CTE
```sql
SELECT gl_data.work_order AS voucher_name,
       gl_data.production_item, gl_data.base_product_type,
       COALESCE(bcc.total_time, 0)    AS total_time,
       COALESCE(bcc.actual_output, 0) AS actual_output,
       COALESCE(ist.tp_qty, 0)        AS finish_goods_qty,
       COALESCE(ist.btp_qty, 0)       AS semi_finish_goods_qty,
       (gl_data.direct_cost - cost_reduction_factor) AS direct_cost,
       ...
FROM gl_data
LEFT JOIN incomming_stock ist ON ist.wo_name = gl_data.work_order
LEFT JOIN bcc_data bcc ON bcc.work_order = gl_data.work_order
LEFT JOIN `tabBatch` batch ON batch.work_order = gl_data.work_order
GROUP BY gl_data.work_order
ORDER BY gl_data.actual_end_date
```

### 4.3 Xử lý sau query (Python)

```
raw data[]
  │
  ├─ Parse semi_product_input_detail → _semi_cache dict
  ├─ topo_sort (để hiển thị theo thứ tự phụ thuộc)
  ├─ Aggregate gl_entries → comp_sums (theo component_code)
  ├─ Merge sf_batch_no + extend_batch_no (dedup)
  └─ semi_product_input_value = 0 (sẽ tính ở calculate_detail)
```

**`topo_sort`:** Sắp xếp hiển thị để WO nguồn hiện trước WO đích. Không ảnh hưởng đến tính toán (engine SCC không yêu cầu thứ tự).

---

## 5. Bước 2 — Phân Bổ Chi Phí Gián Tiếp CPC (`update_costing_sheet_details`)

### 5.1 Lấy GL Entries chi phí gián tiếp

```sql
SELECT gl.account, com.component_code, com.allocate_base_on,
       SUM(gl.debit - gl.credit)                    AS total_amount,
       SUM((gl.debit - gl.credit) - gl.custom_allocated) AS unallocated_amount,
       CONCAT('[', GROUP_CONCAT(...), ']')           AS details
FROM `tabGL Entry` gl
JOIN NxCost Component (method='Gián tiếp') ...
WHERE IFNULL(gl.work_order, '') = ''     -- Không thuộc WO (chi phí chung)
  AND IFNULL(je.name, '') = ''           -- Không phải JE kết chuyển
  AND (gl.debit - gl.credit) != gl.custom_allocated  -- Còn số chưa phân bổ
GROUP BY gl.account, base_product_type, allocate_base_on
```

### 5.2 Phân bổ cho từng WO (`_allocate_work_orders`)

```
Với mỗi GL entry gián tiếp:
  1. Lọc WO theo base_product_type (nếu có)
  2. Tính tổng: total_hours = Σ total_time * cost_adjustment
                total_qty   = Σ actual_output * cost_adjustment

  Nếu allocate_base_on = "Machine hours":
    allocate_cpc_i = unallocated_amount × (total_time_i × adj_i) / total_hours

  Nếu allocate_base_on = "Production volume":
    allocate_cpc_i = unallocated_amount × (actual_output_i × adj_i) / total_qty

  → Lưu vào wo_amounts[voucher_name] += allocate_cpc_i
```

### 5.3 Lưu vào costing_sheet_details

Mỗi hàng `costing_sheet_details` lưu:
- `account`, `component_code`, `allocated_amount`, `unallocated_amount`
- `cost_item` (JSON): `{total_hours, total_qty, work_orders: [...]}`
- `details` (JSON): danh sách GL Entry name + amount gốc

---

## 6. Bước 3 — Tính Giá Thành (`calculate`)

### 6.1 Luồng tổng quát

```python
calculate()
  │
  ├─ recalculate_costing_sheet_details()  → wo_amounts dict
  │    └─ _allocate_work_orders() cho từng costing_sheet row
  │
  └─ calculate_detail(json_data, wo_amounts)
       │
       ├─ Bước A: Tính indirect_cost, cpc_unit, semi_unit_cost cho mỗi WO
       ├─ Bước B: Định nghĩa 4 callbacks
       ├─ Bước C: solve_linear_on_graph() → fn_unit_cost cho mỗi WO
       └─ Bước D: Tính sum_data (tổng hợp)
```

### 6.2 Bước A — Tiền tính (pre-compute)

```python
for item in data:
    wo     = item["voucher_name"]
    fg_qty  = finish_goods_qty
    sfg_qty = semi_finish_goods_qty
    tq      = fg_qty + sfg_qty

    # 1. Gán indirect_cost từ wo_amounts (CPC đã phân bổ)
    item["indirect_cost"] = wo_amounts.get(wo, 0)

    # 2. CPC đơn vị
    item["cpc_unit"] = indirect_cost / fg_qty  (hoặc 0)

    # 3. Đơn giá BTP (hằng số thuần, không phụ thuộc x_j)
    item["semi_unit_cost"] = direct_cost / tq  (nếu sfg_qty > 0)
```

### 6.3 Bước B — 4 Callbacks

#### `b_fn(wo, item)` → Hằng số b_i

```
b_i = DC_i/TQ_i                          (chi phí trực tiếp đơn vị)
    + IC_i/FG_i                           (chi phí gián tiếp đơn vị)
    + Σ_{j∈BTP} (qty_j × SUC_j) / FG_i   (đóng góp BTP, is_fg=0)
```
> **Lưu ý:** BTP (is_fg=0) dùng `semi_unit_cost` = hằng số, tính được ngay.  
> TP (is_fg=1) không tính ở đây — engine xử lý qua `coeff_fn`.

#### `deps_fn(item)` → Danh sách phụ thuộc

```python
return [(d["work_order"], d) for d in detail_cache[wo]
        if d["work_order"] in data_map and d["qty"] > 0]
```
Trả tất cả inputs (cả BTP lẫn TP) để engine xây đồ thị.

#### `coeff_fn(wo, dep_wo, detail)` → Hệ số A[i][j]

```python
if not detail["is_fg"]:    # BTP → hệ số = 0 (đã tính trong b_fn)
    return 0.0
return qty / FG_i           # TP → hệ số vào ma trận A
```

#### `output_fn(wo, x, item, resolved)` → Ghi kết quả

```python
item["fn_unit_cost"] = x
item["total_cost"]   = x * FG_i
```

### 6.4 Bước C — `solve_linear_on_graph`

Engine tự động:
1. Xây đồ thị phụ thuộc từ `deps_fn`
2. Tarjan SCC → phân nhóm quay vòng / tuần tự
3. Giải từng SCC:
   - **Size 1 (độc lập/tuần tự):** `x = b + Σ(coeff × x_dep đã giải)`
   - **Size > 1 (quay vòng):** Gaussian Elimination `(I−A)x=b`, fallback Gauss-Seidel

### 6.5 Bước D — Post-process

```python
for item in data:
    # Tính semi_product_input_value = Σ(qty_j × giá_j)
    for detail in detail_cache[wo]:
        if is_fg:  spiv += qty * resolved[dep_wo]    # TP: dùng fn_unit_cost đã giải
        else:      spiv += qty * dep["semi_unit_cost"] # BTP: dùng hằng số

    item["semi_product_input_value"]    = spiv
    item["imp_finish_goods_value"]      = fg_qty * fn_unit_cost
    item["imp_semi_finish_goods_value"] = sfg_qty * semi_unit_cost

# Tổng hợp sum_data
sum_data = {
    fg_qty, sfg_qty,
    tvfg  = Σ(fg_qty  × fn_unit_cost),    # Tổng giá trị TP
    tvsfg = Σ(sfg_qty × semi_unit_cost),  # Tổng giá trị BTP
    cip   = Σ total_cost,                  # Chi phí SX trong kỳ
    tc    = o_wip + cip - c_wip - cr,      # Tổng giá vốn
}
```

---

## 7. Bước 4 — Submit: Cập Nhật Stock & GL

### 7.1 `update_gl_entry` — Đánh dấu phân bổ

```python
for row in costing_sheet_details:
    for vc in json.loads(row.details):
        allocated += vc["value"] * row.allocated_amount / row.unallocated_amount
        frappe.db.set_value("GL Entry", vc["entry_name"], {"custom_allocated": allocated})
```

### 7.2 `update_stock` — Ghi giá vào SLE

```python
for item in json_data["data"]:
    fn_cost   = item["fn_unit_cost"]    # Giá TP
    semi_cost = item["semi_unit_cost"]  # Giá BTP

    # Lấy Stock Ledger Entry qua voucher_detail_no + item_code + batch_no
    sle_data = get_ref_voucher(voucher_detail_nos, item_codes, batch_nos)

    for sle in sle_data:
        frappe.db.set_value("Stock Ledger Entry", sle.name, {
            "incoming_rate":          unit_cost,
            "stock_value_difference": unit_cost * actual_qty,
        })
        # Ghi log để có thể hoàn tác khi cancel

# Sau khi ghi tất cả SLE → Repost Item Valuation để cập nhật Moving Average
create_item_wise_repost_entries()
execute_repost_item_valuation()
```

### 7.3 `create_item_wise_repost_entries`

```python
for (item_code, warehouse) in unique_pairs:
    re = new Repost Item Valuation(
        based_on     = "Item and Warehouse",
        posting_date = period_from_date,   # Repost từ đầu kỳ
    )
    re.submit()
execute_repost_item_valuation()  # Chạy ngay
```

---

## 8. Bước 5 — Tạo Journal Entry Kết Chuyển (`make_journal_entry`)

```
Credit: Từng tài khoản chi phí (costing_sheet_details)
Debit:  Tài khoản WIP (Company.custom_default_wip_account)

Voucher type: "Production costs transfer"
Posting date: period_to_date
```

Chỉ tạo 1 JE duy nhất. Kiểm tra trước khi tạo để tránh duplicate (`validate_ref_journal_entry`).

---

## 9. Hủy (Cancel)

```
before_cancel:
  → Xóa against_voucher trên GL Entry

on_cancel:
  1. cancel_journal_entry()      → Hủy JE kết chuyển
  2. update_gl_entry()           → Giảm custom_allocated trên GL (hoàn trả)
  3. cancel_gl_entry():
     a. make_reverse_gl_entries() → Tạo GL đảo ngược
     b. Reset SLE: incoming_rate = outgoing_rate = valuation_rate = 0
     c. Repost Item Valuation lại
```

---

## 10. Validation Rules

| Rule | Thời điểm | Điều kiện |
|------|-----------|-----------|
| WO phải Complete | before_submit | Status không được là Draft/Submitted/In Process/Stopped/Closed/Cancelled |
| Phải có giờ máy | before_submit | Nếu finish_goods_qty > 0 thì total_time phải > 0 |
| Không có Repost đang chạy | before_submit | Repost Item Valuation Queued/In Progress trong kỳ phải = 0 |
| Không tạo JE trùng | on_submit | Không được có JE reference cùng document đã tồn tại |

---

## 11. Giải Thích Các Trường Dữ Liệu Chính

| Trường | Nguồn | Ý nghĩa |
|--------|-------|---------|
| `direct_cost` | GL Entry (work_order IS NOT NULL, direct account) | Chi phí trực tiếp của LSX |
| `indirect_cost` | Phân bổ CPC từ costing_sheet_details | Chi phí gián tiếp đã phân bổ |
| `finish_goods_qty` | SED purpose='Manufacture', item=production_item | SL thành phẩm xuất kho |
| `semi_finish_goods_qty` | SED purpose='Manufacture', item=sf_item_code | SL bán thành phẩm xuất kho |
| `total_time` | Báo cáo ca sản lượng | Tổng giờ máy trong kỳ |
| `actual_output` | Báo cáo ca sản lượng | Tổng sản lượng thực tế |
| `semi_unit_cost` | DC / (FG+SFG) | Đơn giá BTP (tính sớm, là hằng số) |
| `fn_unit_cost` | Giải hệ tuyến tính | Đơn giá thành phẩm |
| `semi_product_input_detail` | GL query GROUP_CONCAT | JSON danh sách WO nguồn BTP/TP được tiêu hao |
| `is_fg` | Batch.work_order == production_item | 1=TP, 0=BTP |
| `cost_adjustment` | Item.custom_cost_adjustment | Hệ số điều chỉnh phân bổ (mặc định = 1) |
| `sf_batch_no` | SED + tabBatch | Batch số BTP, dùng để link SLE khi update stock |
| `voucher_detail_no` | SED.name (Manufacture) | Mã SED để map SLE cần update |

---

## 12. Sơ Đồ Luồng Tổng Thể

```
┌─────────────────────────────────────────────────────────────────┐
│                        DRAFT DOCUMENT                            │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
[1] get_cost_details()
    ├── Query 4 CTE SQL
    │     ├── bcc_data    → giờ máy, sản lượng
    │     ├── direct_account → tài khoản trực tiếp
    │     ├── gl_data     → chi phí trực tiếp từ GL
    │     └── incomming_stock → qty TP/BTP, semi_product_input_detail
    ├── topo_sort → sắp xếp hiển thị
    └── Lưu json_data → save()
          │
          ▼
[2] update_costing_sheet_details()
    ├── Query GL Entry gián tiếp (work_order = NULL)
    ├── Phân bổ theo Machine Hours / Production Volume
    └── Lưu costing_sheet_details[]
          │
          ▼
[3] calculate()
    ├── recalculate_costing_sheet_details() → wo_amounts
    └── calculate_detail()
          ├── Pre-compute: indirect_cost, semi_unit_cost
          ├── solve_linear_on_graph (SCC + Gaussian)
          │     ├── Độc lập:  x = b
          │     ├── Tuần tự: x = b + Σcoeff×x_dep
          │     └── Quay vòng: (I−A)x=b
          ├── Post-compute: semi_product_input_value, imp_*
          └── Lưu fn_unit_cost, total_cost → save()
          │
          ▼
[4] SUBMIT
    ├── validate_work_order_complete()
    ├── validate_repost_item_valuation()
    ├── update_gl_entry()    → custom_allocated
    ├── update_stock()
    │     ├── SLE.incoming_rate = fn_unit_cost (hoặc semi_unit_cost)
    │     └── Repost Item Valuation
    └── make_journal_entry()
          Credit: Cost accounts
          Debit:  WIP account
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SUBMITTED DOCUMENT                          │
└─────────────────────────────────────────────────────────────────┘
          │ (cancel)
          ▼
[5] CANCEL
    ├── Xóa against_voucher
    ├── Hủy Journal Entry
    ├── Hoàn trả custom_allocated
    ├── Reset SLE rates → 0
    └── Repost Item Valuation
```

---

*Tài liệu này được tạo từ source code `nxcost_period.py` phiên bản EuP eupapp.*
