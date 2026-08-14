# Giải pháp Quản lý Kho Đa chiều (Inventory Dimension) trong ERPNext — Bản v5

### Phiên bản cập nhật dựa trên kiểm tra code thực tế v14.92.14 trên myfrappe:
### Phân tích toàn diện valuation engine, repost, Bin, GL,
### và giải pháp thay thế Location Ledger (LLE) tự chế bằng Inventory Dimension native

> **Cập nhật so với v4:** bổ sung toàn bộ phần phân tích kiểm tra code core thực tế.
> Bổ sung các mục kiểm tra trực tiếp `stock_ledger.py`, `stock_controller.py`, `valuation.py`
> để xác nhận cách Inventory Dimension tương tác với Moving Average/FIFO valuation engine,
> Bin, GL Entry, và quy trình repost backdated.
> Bổ sung phân tích chiến lược thay thế Location Ledger (LLE) tự chế bằng Inventory Dimension,
> kế hoạch migration, và các tình huống sản xuất + kế toán.
> Bổ sung giải pháp custom cụ thể cho eupapp.

> **Tất cả phân tích dựa trên code thật đã đọc trực tiếp từ myfrappe.**
> - Frappe v14.101.1, ERPNext v14.92.14
> - eupapp (custom app chính) đang override StockReconciliation, StockEntry, StockLedgerEntry
> - Hệ thống Location Ledger (LLE) tự chế đang hoạt động song song

---

## MỤC LỤC

1. [Vấn đề cốt lõi — đối chiếu với code thật](#1)
2. [Giải phẫu kỹ thuật: đọc trực tiếp từ `stock_reconciliation.py`](#2)
3. [Ma trận tình huống thực tế](#3)
4. [Cách các ERP Tier-1 xử lý kiểm kê và Inventory Dimension — phân tích chuyên sâu](#4)
5. [Năm phương án giải pháp — so sánh và khuyến nghị](#5)
6. [Giải pháp A — Stock Entry thủ công (không code)](#6)
7. [Giải pháp B — Custom app: lớp UI kiểm kê sinh Stock Entry](#7)
8. [Câu hỏi trọng tâm: Chỉ đổi giá trị, không đổi Qty](#8)
9. [Ví dụ chi tiết theo từng tình huống](#9)
10. [Rủi ro, kiểm thử và checklist](#10)
11. [Lộ trình hành động](#11)
12. [Phụ lục: API/class thật đã xác minh](#12)
13. [Phương án D — Override class, giữ nguyên UI Stock Reconciliation (bổ sung từ v4)](#13)
14. **[MỚI] Phương án E — Dùng Inventory Dimension core, chỉ override Stock Reconciliation cho periodic](#14)**
15. **[MỚI] Kiểm tra code thật: Valuation Engine, Bin, GL với Inventory Dimension](#15)**
16. **[MỚI] Kiểm tra code thật: Repost backdated và ảnh hưởng đến tồn kho theo Dimension](#16)**
17. **[MỚI] Đối chiếu Inventory Dimension với Location Ledger (LLE) hiện tại](#17)**
18. **[MỚI] Chiến lược thay thế LLE bằng Inventory Dimension (kế hoạch migration)](#18)**
19. **[MỚI] Sản xuất, Kế toán và các tình huống đặc thù](#19)**
20. **[MỚI] Cách các ERP Tier-1 xử lý — và áp dụng vào giải pháp của ERPNext/eupapp](#20)**
21. **[MỚI v6] GIẢI PHÁP MỞ RỘNG CHO NGÀNH NHÔM KÍNH XÂY DỰNG — KHO ĐA CHIỀU, ĐA ĐƠN VỊ TÍNH](#21)**
22. **[MỚI v6] VÍ DỤ CỤ THỂ THEO TỪNG LOẠI VẬT TƯ](#22)**
23. **[MỚI v6] MA TRẬN TÌNH HUỐNG NGÀNH NHÔM KÍNH](#23)**
24. **[MỚI v6] PHƯƠNG ÁN KỸ THUẬT CHO DUAL-UOM & KÍCH THƯỚC PHI CHUẨN](#24)**
25. **[MỚI v6] CẬP NHẬT MỤC LỤC & KẾT LUẬN, LỘ TRÌNH KHUYẾN NGHỊ](#25)**
26. **[MỚI v7] PHÂN TÍCH CHUYÊN SÂU TỒN ÂM, XUẤT ÂM VỚI INVENTORY DIMENSION](#27)**
27. **Phân tích stack tồn âm core**
28. **Tồn âm Warehouse-level với Dimension**
29. **Tồn âm Dimension-level (dim âm, warehouse dương)**
30. **Tồn âm Future SLE (backdated + repost)**
31. **Chính sách per-warehouse negative của eupapp**
32. **Ma trận tình huống tồn âm đầy đủ (9 tình huống)**
33. **Ví dụ thực tế chi tiết**
34. **Giải pháp cho tồn âm có Dimension**
35. **Migration: từ per-warehouse policy sang Dimension**
36. **Checklist kiểm tra tồn âm với Dimension**

---

<a name="1"></a>
## 1. Vấn đề cốt lõi — đối chiếu với code thật

ERPNext có hai cơ chế ghi nhận thay đổi tồn kho:

| Cơ chế | Đường đi | Có tôn trọng Inventory Dimension không? |
|---|---|---|
| **Stock Entry** (Material Receipt/Issue/Transfer/Repack/Manufacture) | `StockController.get_sl_entries()` → `update_inventory_dimensions()` → `make_sl_entries()` → process_sle() | ✅ **Có, đầy đủ.** Dimension được tự động map từ row item vào SLE qua `update_inventory_dimensions()`, và valuation engine xử lý đúng trên warehouse-level pool |
| **Stock Reconciliation** | `update_stock_ledger()` → `get_sle_for_items()` → `make_sl_entries()` | ⚠️ **Có hỗ trợ field Dimension trên UI, nhưng bị chặn cứng** nếu `current_qty` tại tổ hợp (Item, Warehouse, Dimension) khác 0 |

**Trích nguyên văn điều kiện chặn** từ code thật (stock_reconciliation.py dòng 53-62):

```python
def validate_inventory_dimension(self):
    dimensions = get_inventory_dimensions()
    for dimension in dimensions:
        for row in self.items:
            if not row.batch_no and row.current_qty and row.get(dimension.get("fieldname")):
                frappe.throw(
                    _("Row #{0}: You cannot use the inventory dimension '{1}' in Stock "
                      "Reconciliation to modify the quantity or valuation rate. Stock "
                      "reconciliation with inventory dimensions is intended solely for "
                      "performing opening entries.")
                    .format(row.idx, bold(dimension.get("doctype")))
                )
```

**Điểm quan trọng cần hiểu đúng:** điều kiện chặn là `row.current_qty` khác 0 — tức là **đã tồn tại số dư ở đúng tổ hợp Dimension đó trước khi bạn submit**. Điều kiện **không phân biệt** bạn đang định đổi Qty hay chỉ đổi Valuation Rate — cả hai trường hợp đều bị chặn như nhau một khi Dimension đã có tồn kho từ trước.

**Điều ngược lại cũng đã xác minh được:** nếu **không dùng Dimension** (chỉ Item + Warehouse), Stock Reconciliation **đã hỗ trợ sẵn** case "Qty giữ nguyên, chỉ đổi Valuation Rate" mà không cần custom gì cả — xem chi tiết ở Mục 8.1.

---

<a name="2"></a>
## 2. Giải phẫu kỹ thuật: đọc trực tiếp từ `stock_reconciliation.py` (code thật v14.92.14)

```
                    ┌────────────────────────────────────┐
                    │   Stock Entry (tất cả Purpose)      │
                    └──────────────┬─────────────────────┘
                                   │
                   get_sl_entries() → update_inventory_dimensions()
                                   │
                    key = item_code + warehouse + batch
                        + serial_no + MỌI Inventory Dimension
                                   │
                    ┌──────────────┴──────────────┐
                    │   FIFO / Moving Average      │
                    │   áp dụng trên WAREHOUSE POOL │
                    │   (không phân theo dimension)  │
                    └──────────────────────────────┘
                                   │
                    SLE.vi_tri_kho = giá trị dimension
                    SLE.qty_after_transaction = qty sau cùng
                    SLE.valuation_rate = rate pool chung


                    ┌──────────────────────────────┐
                    │   Stock Reconciliation        │
                    └──────────────┬───────────────┘
                                   │
                    remove_items_with_no_change()
                    → get_stock_balance_for(inventory_dimensions_dict)
                      (so sánh row.qty/rate với số dư hệ thống
                       ĐÚNG theo dimension)
                                   │
                    validate_inventory_dimension()
                    → CHẶN nếu current_qty ≠ 0 tại combo có Dimension
                                   │
                    update_stock_ledger()
                    → get_sle_for_items() với logic:
                      • docstatus=1, has_dimensions, không batch:
                        actual_qty = row.qty (coi như 100% nhập mới)
                      → ĐÚNG cho opening, SAI cho periodic
                                   │
                    make_gl_entries()
                    → get_gl_entries() → get_stock_ledger_details()
                    → GL Entry dựa trên stock_value_difference
                      từ warehouse-level
```

**Vì sao core không đơn giản "tính delta rồi ghi actual_qty = delta" cho case có Dimension:**

Nhánh xử lý Dimension trong `get_sle_for_items()` (dòng 485-488) được viết cho đúng một kịch bản — **opening entry**, nơi `current_qty` tại combo đó = 0. Trong kịch bản đó, `actual_qty = row.qty` là đúng (toàn bộ số lượng nhập là mới, không có gì để trừ đi). Code hiện tại **chưa có nhánh riêng** cho "combo Dimension đã có tồn kho, giờ cần set lại thành số khác" — nếu bạn cưỡng ép bỏ qua `validate_inventory_dimension()` mà không sửa thêm `get_sle_for_items()`, hệ thống sẽ ghi `actual_qty = row.qty` (toàn bộ số mới) thay vì `delta` — gây **cộng dồn sai gấp đôi**.

---

<a name="3"></a>
## 3. Ma trận tình huống thực tế — toàn diện

### 3.1 Phân loại theo nghiệp vụ

| # | Nhóm | Tình huống | Có Dimension? | Hành vi core | Phương án xử lý | Pipeline |
|---|---|---|---|---|---|---|
| **NK1** | **Nhập kho** | Mua hàng từ PO, nhập vào 1 vị trí | ✅ | Core tự động: PR Item có `vi_tri_kho` → SLE ghi dimension | Không cần custom | PR → SLE → Bin → GL |
| **NK2** | **Nhập kho** | Mua hàng từ PO, nhập nhiều vị trí (chia lô) | ✅ | Core tự động: mỗi dòng PR Item 1 vị trí | Không cần custom | PR → SLE (nhiều dòng) |
| **NK3** | **Nhập kho** | Nhập tồn đầu kỳ (Opening) | ✅ | **SR gốc được phép** — current_qty=0 nên core không throw | Dùng thẳng SR với Purpose="Opening Stock" | SR → SLE (actual_qty=row.qty) → Bin → GL |
| **NK4** | **Nhập kho** | Nhập từ sản xuất (Manufacture Receipt) | ✅ | Core: SE Manufacture có `vi_tri_kho` trên TP | Không cần custom | SE → SLE → Bin → GL |
| **NK5** | **Nhập kho** | Nhập hàng trả lại (Return) | ✅ | Core: Sales Return tự động | Không cần custom | DN Return → SLE |

| **XK1** | **Xuất kho** | Xuất bán cho khách (DN) từ 1 vị trí | ✅ | Core tự động: DN Item có `vi_tri_kho` | Không cần custom | DN → SLE → Bin → GL |
| **XK2** | **Xuất kho** | Xuất bán từ nhiều vị trí | ✅ | Core: mỗi dòng DN Item = 1 vị trí | Không cần custom | DN (nhiều dòng) |
| **XK3** | **Xuất kho** | Xuất NVL sản xuất (Manufacture Issue) | ✅ | Core tự động: SE Manufacture có `vi_tri_kho` trên NVL | Không cần custom | SE → SLE → Bin → GL |
| **XK4** | **Xuất kho** | Xuất hàng mẫu, hủy, hao hụt | ✅ | Core: SE Material Issue có `vi_tri_kho` | Không cần custom | SE → SLE → Bin → GL |
| **XK5** | **Xuất kho** | Xuất trả nhà cung cấp | ✅ | Core: PR Return tự động | Không cần custom | PR Return → SLE |

| **CC1** | **Chuyển kho** | Chuyển từ Kệ A → Kệ B cùng Warehouse | ✅ | Core: SE Transfer: `s_vi_tri_kho`=A, `t_vi_tri_kho`=B → 2 SLE (+1 ở A, -1 ở B) | Không cần custom | SE → 2 SLE → Bin (same) → GL (0) |
| **CC2** | **Chuyển kho** | Chuyển từ Warehouse 1 → Warehouse 2, kèm vị trí | ✅ | Core: SE Transfer điền cả warehouse + dimension | Không cần custom | SE → 2 SLE → Bin (2 wh) → GL (transfer) |
| **CC3** | **Chuyển kho** | Chuyển NVL sang kho tạm cho SX | ✅ | Core: SE Material Transfer for Manufacture | Không cần custom | SE → SLE → Bin → GL |

| **KK1** | **Kiểm kê** | Kiểm kê opening stock (chưa có giao dịch) | ✅ | **SR gốc** — current_qty=0, không throw | Dùng thẳng SR Purpose="Opening Stock" | SR → SLE core pipeline |
| **KK2** | **Kiểm kê** | Kiểm kê định kỳ — thừa hàng tại 1 vị trí | ✅ | Core SR **CHẶN** (current_qty>0) | **Override SR** → sinh SE Material Receipt | SR → SE → SLE → Bin → GL |
| **KK3** | **Kiểm kê** | Kiểm kê định kỳ — thiếu hàng tại 1 vị trí | ✅ | Core SR **CHẶN** | **Override SR** → sinh SE Material Issue | SR → SE → SLE → Bin → GL |
| **KK4** | **Kiểm kê** | Kiểm kê — thừa vị trí A, thiếu vị trí B, cùng Item | ✅ | Core SR **CHẶN** | **Override SR** → match chéo → sinh SE Transfer | SR → SE Transfer → 2 SLE → Bin → GL |
| **KK5** | **Kiểm kê** | Kiểm kê — chỉ sai giá trị, qty đúng, có Dimension | ✅ | Core SR **CHẶN** (dù qty không đổi) | **Override SR** → sinh SLE actual_qty=0 với vi_tri_kho | SR → SLE (act=0) → update pool rate |
| **KK6** | **Kiểm kê** | Kiểm kê — item vừa có vị trí vừa không | ✅ + ❌ | Core SR **CHẶN** dòng có dimension; dòng không dimension vẫn dùng được | Override SR: xử lý 2 loại riêng | SR mixed → SE + SLE |
| **KK7** | **Kiểm kê** | Kiểm kê — warehouse không yêu cầu dimension | ❌ | Core SR hoạt động bình thường | Dùng SR gốc | SR → SLE core pipeline |
| **KK8** | **Kiểm kê** | Kiểm kê — chênh lệch do backdated đã được repost | ✅ | Sau repost, số liệu đã chính xác | Override SR sinh SE như bình thường | SR → SE → SLE (đã repost) |

| **ĐG1** | **Điều chỉnh giá trị** | Chỉ sai giá vốn, không đổi số lượng, không Dimension | ❌ | **SR gốc xử lý được** (Mục 8.1) | Dùng SR Purpose="Stock Reconciliation" | SR → SLE act=0 → Bin → GL |
| **ĐG2** | **Điều chỉnh giá trị** | Chỉ sai giá vốn, không đổi số lượng, CÓ Dimension | ✅ | Core SR **CHẶN** mặc dù qty không đổi | **Override SR** → SLE actual_qty=0 + vi_tri_kho + incoming_rate mới | SR → SLE (act=0, có dim) → AVCO pool update |
| **ĐG3** | **Điều chỉnh giá trị** | Điều chỉnh hồi tố giá vốn (backdated) | ✅ | Core repost tự động sau khi SLE được ghi | SLE actual_qty=0 với posting_date cũ | SLE → Repost → Update pool |

| **SX1** | **Sản xuất** | Nhập kho NVL từ PO, chờ SX | ✅ | Core: PR Item có `vi_tri_kho` | Không cần custom | PR → SLE (dim NVL) |
| **SX2** | **Sản xuất** | Xuất NVL vào sản xuất từ vị trí A | ✅ | Core: SE Manufacture/Material Consumption: `vi_tri_kho`=A | Không cần custom | SE → SLE (-qty ở dim A) |
| **SX3** | **Sản xuất** | Nhập thành phẩm từ SX vào vị trí B | ✅ | Core: SE Manufacture: `to_vi_tri_kho`=B | Không cần custom | SE → SLE (+qty ở dim B) |
| **SX4** | **Sản xuất** | Nhập bán thành phẩm từ công đoạn trước | ✅ | Core: SE Manufacture nhiều dòng | Không cần custom | SE → nhiều SLE |
| **SX5** | **Sản xuất** | Chốt NVL tiêu thụ cuối kỳ | ✅ | SE Material Consumption for Manufacture | Không cần custom | SE → SLE |
| **SX6** | **Sản xuất** | Trả lại NVL từ SX về kho | ✅ | Core: SE Material Transfer | Không cần custom | SE → SLE |

| **KT1** | **Kế toán** | Cuối kỳ — tính giá vốn | ✅/❌ | Core: GL Entry từ stock_value_difference warehouse-level | Không cần custom | SLE → GL Entry |
| **KT2** | **Kế toán** | Đánh giá lại tồn kho theo tỷ giá | ✅/❌ | Core: Exchange Rate Revaluation | Không cần custom | GL Entry riêng |
| **KT3** | **Kế toán** | Chênh lệch kiểm kê → hạch toán | ✅ | Stock Entry từ KK sinh GL Entry chuẩn | Không cần custom | SE → GL (Stock Adjustment Account) |

| **BC1** | **Báo cáo** | Xem tồn kho theo vị trí | ✅ | Core: Stock Balance Report filter `vi_tri_kho` | Không cần custom hoặc sửa report cũ | SLE query |
| **BC2** | **Báo cáo** | Xem sổ kho theo vị trí (Stock Ledger) | ✅ | Core: Stock Ledger Report filter dimension | Không cần custom | SLE query |
| **BC3** | **Báo cáo** | Xem tổng tồn kho warehouse (không phân vị trí) | ✅/❌ | Core: Bin.actual_qty là tổng | Không cần custom | Bin |
| **BC4** | **Báo cáo** | Xem giá trị tồn kho theo vị trí | ✅ | **KHÔNG CÓ** — valuation là pool chung | Cần báo cáo custom: SLE.qty * Bin.valuation_rate | SLE + Bin |
| **BC5** | **Báo cáo** | Báo cáo kiểm kê (đối chiếu hệ thống vs thực tế) | ✅ | Từ SR items + `get_stock_balance(dimension_dict)` | Cần custom report | Custom query |

| **NV1** | **Nghiệp vụ đặc thù** | Backdated entry (submit sai ngày) | ✅ | Core repost tự động — SLE có dimension giữ nguyên | Không cần custom | SLE → Repost → SLE mới |
| **NV2** | **Nghiệp vụ đặc thù** | Cancel chứng từ | ✅ | Core: hủy SLE → tạo SLE âm → repost | Với SR periodic: cancel SR → cancel SE đã sinh | SR → cancel SE → cancel SLE |
| **NV3** | **Nghiệp vụ đặc thù** | Sửa chứng từ sau submit (Amend) | ✅ | Core: cancel → amend (bản copy) | Với SR periodic: cancel chain + amend | SR amend → sinh SE mới |
| **NV4** | **Nghiệp vụ đặc thù** | Hàng gửi bán (Consignment) | ✅ | Core: Delivery Note có dimension | Không cần custom | DN → SLE ở consignment wh |
| **NV5** | **Nghiệp vụ đặc thù** | Hàng nhận gia công (Subcontracting) | ✅ | Core: Subcontracting Receipt/Stock Entry | Không cần custom | Subcontract → SLE |

### 3.2 Ma trận quyết định theo trạng thái tồn kho

| Trạng thái | delta_qty | delta_rate | Dimension | Hành động | Core tự xử lý? |
|---|---|---|---|---|---|
| **Không đổi** | =0 | =0 | Có/Không | **Bỏ qua** (remove row) | ✅ `remove_items_with_no_change()` |
| **Thiếu hàng** | <0 | Không đổi | ❌ | SE Material Issue | ✅ Luôn |
| **Thừa hàng** | >0 | Không đổi | ❌ | SE Material Receipt | ✅ Luôn |
| **Thiếu hàng** | <0 | Không đổi | ✅ | Override SR → SE Material Issue với `vi_tri_kho` | ⚠️ Cần override (KK3) |
| **Thừa hàng** | >0 | Không đổi | ✅ | Override SR → SE Material Receipt với `vi_tri_kho` | ⚠️ Cần override (KK2) |
| **Thiếu vị trí A, thừa vị trí B** | delta_A<0, delta_B>0, tổng=0 | Không đổi | ✅ | Override SR → SE Material Transfer A→B | ⚠️ Cần override (KK4) |
| **Đúng qty, sai rate** | =0 | ≠0 | ❌ | SR gốc (core xử lý) | ✅ (Mục 8.1) |
| **Đúng qty, sai rate** | =0 | ≠0 | ✅ | Override SR → SLE actual_qty=0, `vi_tri_kho`, `incoming_rate`=rate mới | ⚠️ Cần override (KK5) |
| **Thiếu + sai rate** | <0 | ≠0 | ✅ | Override SR → SE Material Issue + SLE actual_qty=0 cho phần rate | ⚠️ Cần override |
| **Thừa + sai rate** | >0 | ≠0 | ✅ | Override SR → SE Material Receipt + SLE actual_qty=0 cho phần rate | ⚠️ Cần override |
| **Chuyển warehouse + đổi vị trí** | qty chuyển | Không đổi | ✅ | SE Material Transfer (core) | ✅ Luôn (CC2) |

### 3.3 Ma trận quyết định theo loại kho

| Loại kho | `must_update_location` | Có dùng Dimension? | Cách xử lý SR | Ghi chú |
|---|---|---|---|---|
| **Kho NVL** | 1 | ✅ | Override → sinh SE | Validate bắt buộc `vi_tri_kho` |
| **Kho thành phẩm** | 1 | ✅ | Override → sinh SE | Validate bắt buộc `vi_tri_kho` |
| **Kho phế liệu** | 1 | ✅ | Override → sinh SE | Validate bắt buộc `vi_tri_kho` |
| **Kho tạm (WIP)** | 1 | ✅ | Override → sinh SE | Validate bắt buộc `vi_tri_kho` |
| **Kho hàng gửi** | 0 | ❌ | SR gốc | Không validate dimension |
| **Kho trung chuyển** | 0 | ❌ | SR gốc | Không validate dimension |
| **Kho ảo (Virtual)** | 0 | ❌ | SR gốc | Không validate dimension |
| **Kho lẻ (Retail)** | 0 | ❌ | SR gốc | Không validate dimension |

### 3.4 Ma trận xử lý theo phương pháp định giá

| Phương pháp | Dimension | Stock Entry (NK/XK/CC) | SR Opening | SR Periodic | Value-only adjustment |
|---|---|---|---|---|---|
| **Moving Average** | ❌ | ✅ Pool AVCO | ✅ Core | ✅ Core | ✅ Core (SLE act=0) |
| **Moving Average** | ✅ | ✅ Pool AVCO (chung warehouse) | ✅ Core | ⚠️ Override → sinh SE | ✅ SLE act=0 + dim |
| **FIFO** | ❌ | ✅ Queue warehouse | ✅ Core | ✅ Core | ✅ Core (SLE act=0) |
| **FIFO** | ✅ | ✅ Queue warehouse (chung) | ✅ Core | ⚠️ Override → sinh SE | ✅ SLE act=0 + dim (repost queue) |
| **Batch-wise Valuation** | ✅ (batch) | ✅ Core (use_batchwise_valuation=1) | ✅ Core | ✅ Core (batch_no có sẵn) | ✅ Core (batch riêng) |

### 3.5 Tổng hợp số lượng tình huống

| Nhóm | Tổng số tình huống | Core tự xử lý | Cần override SR |
|---|---|---|---|
| **Nhập kho** (NK1–NK5) | 5 | 5 | 0 |
| **Xuất kho** (XK1–XK5) | 5 | 5 | 0 |
| **Chuyển kho** (CC1–CC3) | 3 | 3 | 0 |
| **Kiểm kê** (KK1–KK8) | 8 | 2 | **6** |
| **Điều chỉnh giá trị** (ĐG1–ĐG3) | 3 | 1 | **2** |
| **Sản xuất** (SX1–SX6) | 6 | 6 | 0 |
| **Kế toán** (KT1–KT3) | 3 | 3 | 0 |
| **Báo cáo** (BC1–BC5) | 5 | 4 | 1 (BC4) |
| **Nghiệp vụ đặc thù** (NV1–NV5) | 5 | 5 | 0 |
| **TỔNG CỘNG** | **43** | **34 (79%)** | **9 (21%)** |

**Kết luận:** 79% tình huống đã được core xử lý hoàn toàn. Chỉ 21% (9/43) cần override Stock Reconciliation — đây là các tình huống kiểm kê định kỳ và điều chỉnh giá trị có Dimension.

### 3.6 Luồng xử lý chi tiết cho override SR (9 tình huống)

```
Stock Reconciliation submitted (Purpose = "Stock Reconciliation")
  │
  ├── has_dimension_items() == False?
  │   └── YES → super().on_submit() (core pipeline) ← KK7
  │
  ├── has_dimension_items() == True?
  │   └── Phân tích từng row:
  │       ├── delta_qty = row.qty - get_stock_balance(dimension_dict={...}).qty
  │       ├── delta_rate = row.valuation_rate - current_rate
  │       │
  │       ├── delta_qty == 0 AND delta_rate == 0 → skip row
  │       │
  │       ├── delta_qty == 0 AND delta_rate ≠ 0
  │       │   → SLE actual_qty=0, vi_tri_kho=dim_value, incoming_rate=row.valuation_rate
  │       │   ← ĐG2, KK5
  │       │
  │       ├── delta_qty > 0 AND delta_rate == 0
  │       │   → SE Material Receipt: qty=delta_qty, vi_tri_kho=dim_value
  │       │   ← KK2
  │       │
  │       ├── delta_qty < 0 AND delta_rate == 0
  │       │   → SE Material Issue: qty=abs(delta_qty), vi_tri_kho=dim_value
  │       │   ← KK3
  │       │
  │       ├── delta_qty > 0 AND delta_rate ≠ 0
  │       │   → SE Material Receipt + SLE actual_qty=0 cho phần rate
  │       │
  │       ├── delta_qty < 0 AND delta_rate ≠ 0
  │       │   → SE Material Issue + SLE actual_qty=0 cho phần rate
  │       │
  │       └── Cross-dimension matching:
  │           item có delta_A < 0 ở vị trí A VÀ delta_B > 0 ở vị trí B
  │           CÙNG (item, warehouse)
  │           → match min(abs(delta_A), delta_B) → SE Transfer A→B
  │           ← KK4
  │
  └── Post-processing:
      ├── Gán custom_source_stock_reconciliation trên SE
      ├── Ghi log audit: SR.name → generated SE list
      └── (Không gọi super().on_submit())
```

<a name="4"></a>
## 4. Cách các ERP Tier-1 xử lý kiểm kê — tổng quan

| Hệ thống | Công cụ kiểm kê | Cách sinh điều chỉnh | Dimension tracking |
|---|---|---|---|
| SAP | Physical Inventory Document theo Storage Bin | "Post difference" tạo Goods Movement cho từng chênh lệch | Valuation ở Plant-level; Bin chỉ track qty |
| Oracle NetSuite | Physical Inventory Adjustment | So khớp tag count với snapshot, tự sinh Material Transaction | Location-level valuation; Bin không ảnh hưởng cost |
| Dynamics 365 | Inventory Journal (Counting + Adjustment) | Post Counting Journal sinh Inventory Receipt/Issue | Storage dimensions phân loại Financial/Physical — chỉ Financial mới ảnh hưởng valuation |
| Odoo | Inventory Adjustment theo Location | Sinh Stock Moves | Valuation ở Warehouse-level, Location chỉ track qty |

**Nguyên tắc chung toàn ngành:** Không hệ thống Tier-1 nào định giá theo bin/sublocation. Valuation luôn ở warehouse/plant-level. Bin/location chỉ để track số lượng.

---

<a name="5"></a>
## 5. Năm phương án giải pháp — so sánh và khuyến nghị (cập nhật v5)

| Phương án | Can thiệp core? | Hỗ trợ Dimension | Tận dụng core pipeline? | Rủi ro nâng cấp | Khuyến nghị |
|---|---|---|---|---|---|
| **A. Stock Entry thủ công** | Không | ✅ Đầy đủ | ✅ Stock Entry core | Không có | Giải pháp tạm thời |
| **B. Custom app: DocType kiểm kê riêng** | Không | ✅ Đầy đủ | ✅ Stock Entry core | Trung bình | Có thể dùng |
| **C. Vá core** | Có (sửa core) | ⚠️ Sai logic delta | ❌ Không | Cao — rủi ro sai số | ❌ Không khuyến nghị |
| **D. Override class SR, sinh Stock Entry** (v4) | Không (hook) | ✅ Đầy đủ | ✅ Stock Entry core | Thấp–TB | ⭐⭐⭐ Tốt nếu không có LLE |
| **E. [MỚI] Dùng Inventory Dimension core, override SR periodic** | **Không** — dùng hook `override_doctype_class` | **✅ Đầy đủ — tận dụng core `update_inventory_dimensions()`** | **✅ Toàn bộ pipeline core: SLE → Bin → GL → Repost** | **Thấp** — chỉ override 1 class SR | **⭐⭐⭐⭐⭐ KHUYẾN NGHỊ CAO NHẤT** |

**Phương án E là phương án mới được bổ sung trong v5 sau khi kiểm tra code thật v14.92.14. Đây là phương án tối ưu nhất vì:**
1. **Tận dụng 100% core Inventory Dimension** — không cần LLE tự chế
2. **Tận dụng toàn bộ pipeline core** — SLE → Bin → GL → Repost (core tự xử lý)
3. **Chỉ custom đúng 1 chỗ duy nhất** — Stock Reconciliation periodic (sinh Stock Entry)
4. **Giữ nguyên UI Stock Reconciliation** — người dùng không thay đổi thao tác
5. **Dễ migrate từ LLE** — dữ liệu cũ được chuyển qua dimension field trên SLE

**Khuyến nghị lộ trình:** chạy **A ngay lập tức** làm giải pháp tạm → song song xây dựng **Phương án E** (gồm migration LLE → Dimension + override SR). **Không chọn C. Không xây thêm B hoặc D nếu đã có LLE — chuyển thẳng sang E để đồng bộ core.**

Chi tiết Phương án D (từ v4) ở [Mục 13](#13). Chi tiết Phương án E (mới) ở [Mục 14](#14).

---

<a name="6"></a>
## 6. Giải pháp A — Stock Entry thủ công (không code)

**Quy trình 4 bước:**
1. Xuất Stock Balance Report lọc theo Item + Warehouse + Dimension đang dùng → làm phiếu đối chiếu.
2. Kiểm đếm thực tế theo từng tổ hợp Dimension tại hiện trường.
3. Tính `Chênh lệch = Số lượng thực tế − Số lượng hệ thống`.
4. Tạo Stock Entry tương ứng:

| Trường hợp | Purpose | Hành động |
|---|---|---|
| Thừa (delta > 0) | `Material Receipt` | Nhập đúng Warehouse + Dimension |
| Thiếu (delta < 0) | `Material Issue` | Xuất đúng Warehouse + Dimension, chọn Cost Center hao hụt |
| Lệch vị trí, không lệch tổng | `Material Transfer` | Giữ nguyên Valuation |
| Chỉ lệch giá trị (Qty không đổi), **có Dimension** | Không dùng Stock Entry thường (Qty bắt buộc > 0 trong Stock Entry Detail) | Xem giải pháp chuyên biệt ở [Mục 8](#8) |

**Ưu điểm:** hỗ trợ đầy đủ Dimension, tôn trọng FIFO/Moving Average, audit trail rõ ràng, không rủi ro nâng cấp.
**Hạn chế:** thao tác thủ công, không có UI "nhập count → tự tính delta".

---

<a name="7"></a>
## 7. Giải pháp B — Custom app: lớp UI kiểm kê sinh Stock Entry

### 7.1 Nguyên tắc thiết kế
1. Xây một DocType **hoàn toàn mới** (ví dụ `Kiểm Kê Vị Trí`) — không override Stock Reconciliation gốc.
2. UI cho phép nhập Item, Warehouse, giá trị từng Inventory Dimension, và Số lượng đếm được.
3. Khi mở phiếu, hệ thống tự tính **Số lượng hệ thống** tại tổ hợp Dimension đó bằng `get_stock_balance()`.
4. Khi submit, hệ thống **tự sinh Stock Entry chuẩn** (Material Receipt/Issue/Transfer).
5. Trường hợp `delta == 0` nhưng cần đổi giá trị → xử lý riêng (Mục 8), không cố nhét vào Stock Entry.

### 7.2 So sánh với Phương án E
Phương án B tạo mới DocType, Phương án E tận dụng Stock Reconciliation hiện có. Nếu bạn đang dùng LLE, chuyển thẳng sang E (override SR) thay vì tạo DocType mới sẽ giảm số lượng code cần viết và người dùng không cần học UI mới.

---

<a name="8"></a>
## 8. Câu hỏi trọng tâm: Chỉ đổi giá trị, không đổi Qty — giải pháp chuẩn nhất

### 8.1 Trường hợp KHÔNG có Inventory Dimension — core đã hỗ trợ sẵn

Trong `update_stock_ledger()` core (dòng 316-321):
```python
if (
    previous_sle
    and row.qty == previous_sle.get("qty_after_transaction")
    and (row.valuation_rate == previous_sle.get("valuation_rate") or row.qty == 0)
) or (not previous_sle and not row.qty):
    continue   # bỏ qua — không có gì thay đổi
```

Nếu `row.qty` bằng đúng số hiện tại nhưng `valuation_rate` khác — điều kiện `continue` **không** được thoả (vì valuation_rate khác), nên hệ thống **vẫn ghi SLE** với `actual_qty = 0` (do không có Dimension nên không rơi vào nhánh has_dimensions), chỉ set lại valuation_rate mới. → **Dùng Stock Reconciliation gốc cho case không-dimension, không cần custom.**

### 8.2 Trường hợp CÓ Inventory Dimension — và giải pháp trong Phương án E

Với Inventory Dimension, `validate_inventory_dimension()` chặn mọi thao tác có `current_qty > 0`. Giải pháp trong Phương án E:

1. **Nếu dùng Stock Reconciliation periodic → override sinh Stock Entry** (giống Mục 13)
2. **Nếu delta_qty = 0, chỉ đổi valuation_rate:**
   - Ghi 1 SLE với `actual_qty = 0`, có dimension, có `incoming_rate` = rate mới
   - `stock_value_difference = (new_rate - old_rate) * qty`
   - Pipeline AVCO/FIFO core tự cập nhật pool rate
   - Phương án này sạch, audit trail 1 dòng, an toàn với Serial No

---

<a name="9"></a>
## 9. Ví dụ chi tiết theo từng tình huống

**Ví dụ 1 — Thiếu hàng đơn giản, không Dimension:** Stock Entry `Material Issue`.

**Ví dụ 2 — Thừa/thiếu chéo giữa 2 Kệ (có Dimension):** Item ITEM-002, Kho A. Kệ 1: system 50, actual 40 (thiếu 10); Kệ 2: system 30, actual 40 (thừa 10) → 1 Stock Entry `Material Transfer`: Source = Kho A/Kệ 1 → Target = Kho A/Kệ 2, Qty = 10.

**Ví dụ 3 — Chỉ sai giá vốn, không Dimension, Moving Average:** Dùng Stock Reconciliation gốc (core xử lý).

**Ví dụ 4 — Chỉ sai giá vốn, CÓ Dimension:** Item ITEM-004, Kho A, Dimension = "Kệ A-05", Qty hệ thống = thực tế = 200, Valuation Rate sai.
- **Phương án B/D/E:** Trong SR periodic → phát hiện delta_qty=0, rate khác → ghi SLE `actual_qty=0` với `vi_tri_kho="Kệ A-05"`, `incoming_rate` = rate mới → core tự update pool.

**Ví dụ 5 — Nhập tồn đầu kỳ (Opening), có Dimension:** Dùng Stock Reconciliation gốc, Purpose = "Opening Stock" → core pipeline chạy đúng.

**Ví dụ 6 — Backdated:** Stock Entry với posting_date quá khứ → core tự động repost.

---

<a name="10"></a>
## 10. Rủi ro, kiểm thử và checklist (cập nhật cho Phương án E)

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Dữ liệu LLE cũ không đồng bộ với dimension mới | 🔴 Cao | Script migration + repost; chạy song song 1 tuần |
| Stock Reconciliation dimension throw vẫn tồn tại | 🟡 TB | Override validate_inventory_dimension() để skip |
| Performance: sinh Stock Entry từ SR chậm nếu nhiều dòng | 🟡 TB | Queue background job (SR đã hỗ trợ queue_action) |
| User quen UI location_items → UI dimension mới | 🟡 TB | Training + đồng bộ dữ liệu trong thời gian chuyển |
| eupapp override xung đột với app khác | 🟢 Thấp | Chỉ eupapp override SR (đã kiểm tra) |

**Checklist test (bổ sung cho v4):**
- [ ] Test Opening Stock với Inventory Dimension (core pipeline)
- [ ] Test periodic SR: dimension có qty → sinh Material Receipt/Issue/Transfer
- [ ] Test value-only adjustment với dimension (SLE actual_qty=0)
- [ ] Test Cancel chain: SR periodic → cancel → Stock Entry tự động cancel
- [ ] Test FIFO valuation: nhập 2 dimension khác rate → xuất từ 1 dimension → rate pool chung
- [ ] Test AVCO valuation: nhập vào dim A rate 100, dim B rate 110 → pool rate 103.33
- [ ] Test Stock Balance Report với filter `vi_tri_kho`
- [ ] Test backdated entry có dimension → repost chạy đúng
- [ ] Test GL Entry: stock_value_difference warehouse-level (không phân dim)
- [ ] Test Stock Entry Manufacture với dimension NVL + TP
- [ ] Test Material Transfer giữa 2 dimension cùng warehouse

---

<a name="11"></a>
## 11. Lộ trình hành động (cập nhật cho Phương án E)

**Giai đoạn 0 — Chuẩn bị (3-5 ngày):**
- Cấu hình Inventory Dimension "Vị trí kho" trên UI
- Rà soát toàn bộ child table location (location_items, s_location, t_location)
- Viết script đồng bộ location → dimension field

**Giai đoạn 1 — Override Stock Reconciliation (5-7 ngày):**
- Sửa `EupStockReconciliation`: validate, on_submit (rẽ nhánh opening vs periodic), on_cancel
- Thêm `generate_stock_entries_from_items()`, `handle_value_only_rows()`
- Thêm field link ngược trên Stock Entry (custom_source_stock_reconciliation)

**Giai đoạn 2 — Sửa Stock Entry + tắt LLE (3-5 ngày):**
- Bỏ `update_location_ledger()` khỏi EupStockEntry
- Thêm validate dimension bắt buộc cho warehouse `must_update_location=1`
- Đánh dấu deprecated các file LLE

**Giai đoạn 3 — Migration dữ liệu (3-5 ngày):**
- Chạy script: LLE → gán vi_tri_kho vào SLE
- Đồng bộ Stock Reconciliation Item.vi_tri_kho từ Stock Reconciliation Location
- Đồng bộ Stock Entry Detail.vi_tri_kho từ Stock Entry Location
- Chạy repost cho các SLE đã cập nhật

**Giai đoạn 4 — Báo cáo + UAT (5-7 ngày):**
- Chuyển báo cáo location sang dùng dimension filter
- UAT với team kho + kế toán + sản xuất
- Đối chiếu số liệu song song 1 tuần
- Go-live

---

<a name="12"></a>
## 12. Phụ lục: API/class thật đã xác minh

**Core ERPNext v14.92.14 — đã đọc trực tiếp:**
- `erpnext.stock.doctype.stock_reconciliation.stock_reconciliation.StockReconciliation` — class gốc; đã đọc: `validate_inventory_dimension()`, `remove_items_with_no_change()`, `update_stock_ledger()`, `get_sle_for_items()`, `make_adjustment_entry()`
- `erpnext.stock.doctype.inventory_dimension.inventory_dimension.get_inventory_dimensions()` — đọc danh sách Dimension
- `erpnext.stock.doctype.inventory_dimension.inventory_dimension.update_inventory_dimensions()` — tự động map dimension từ row → SLE
- `erpnext.stock.utils.get_stock_balance()` — hỗ trợ `inventory_dimensions_dict` để filter qty theo dimension
- `erpnext.controllers.stock_controller.StockController` — `update_inventory_dimensions()`, `get_gl_entries()`, `repost_future_sle_and_gle()`, `make_sl_entries()`
- `erpnext.stock.stock_ledger` — `process_sle()`, `get_moving_average_values()`, `update_queue_values()`, `update_bin()`, `get_previous_sle()`
- `erpnext.stock.valuation.FIFOValuation`, `MovingAverageValuation` — warehouse-level pool
- `erpnext.stock.doctype.inventory_dimension.test_inventory_dimension` — test cho Inventory Dimension với Stock Entry, Purchase Receipt, Delivery Note

**eupapp (custom app chính) — đã đọc toàn bộ:**
- `eupapp.eupapp.doctype.overrides.stock_reconciliation.EupStockReconciliation` — override hiện tại (LLE)
- `eupapp.eupapp.doctype.overrides.stock_entry.EupStockEntry` — override hiện tại (LLE + validation)
- `eupapp.eupapp.doctype.overrides.stock_ledger_entry.EupStockLedgerEntry` — negative stock policy per-warehouse
- `eupapp.eup_stock.location_ledger` — LLE engine (sẽ bỏ)
- `eupapp.eup_stock.lle_sle_link` — liên kết LLE→SLE (sẽ bỏ)
- `eupapp.eup_stock.negative_policy` — negative stock per-warehouse (giữ)

---

<a name="13"></a>
## 13. Phương án D — Override class, giữ nguyên UI Stock Reconciliation (bổ sung từ v4)

Nội dung chi tiết Phương án D đã được trình bày trong v4 — vui lòng tham khảo tài liệu `ERPNext_Stock_Reconciliation_Inventory_Dimension_Giai_Phap_v4.md`. Tóm tắt:

**Cơ chế kỹ thuật:** `override_doctype_class` hook của Frappe, thay thế class `StockReconciliation` bằng class con, rẽ nhánh:
- `Purpose == "Opening Stock"` → dùng core pipeline (super().on_submit())
- `Purpose == "Stock Reconciliation"` (periodic) → không gọi super, sinh Stock Entry

**Khác biệt với Phương án E:** Phương án D sử dụng location (từ LLE), Phương án E sử dụng Inventory Dimension core. Khuyến nghị chọn E vì tận dụng được toàn bộ core pipeline.

---

<a name="14"></a>
## 14. [MỚI] Phương án E — Dùng Inventory Dimension core, chỉ override Stock Reconciliation cho periodic

Đây là phương án được đánh giá cao nhất trong v5. Tận dụng 100% core Inventory Dimension, chỉ custom đúng một phần: Stock Reconciliation khi Purpose = "Stock Reconciliation" (periodic).

### 14.1 Kiến trúc

```
ERPNext core (xử lý mọi thứ trừ SR periodic):
┌────────────────────────────────────────────────────────────┐
│  Stock Entry (mọi Purpose)                                 │
│  Purchase Receipt / Delivery Note / Sales Invoice           │
│  → get_sl_entries() + update_inventory_dimensions()        │
│    → SLE (có vi_tri_kho field)                             │
│      → process_sle() (AVCO/FIFO pool warehouse)            │
│        → Bin update + GL Entry + Repost                    │
└────────────────────────────────────────────────────────────┘

Override (chỉ Stock Reconciliation):
┌────────────────────────────────────────────────────────────┐
│  Stock Reconciliation (Purpose = "Stock Reconciliation"):  │
│    1. validate():                                          │
│       - remove_items_with_no_change() với dimension filter │
│       - Skip validate_inventory_dimension() core           │
│    2. on_submit():                                         │
│       - Tính delta theo từng dimension                     │
│       - Sinh Stock Entry (Material Receipt/Issue/Transfer) │
│       - Value-only → SLE actual_qty=0                      │
│    3. on_cancel():                                         │
│       - Cancel các Stock Entry đã sinh                     │
└────────────────────────────────────────────────────────────┘
```

### 14.2 So sánh Phương án E với D

| Tiêu chí | D (v4, dùng location) | E (v5, dùng Inventory Dimension) |
|---|---|---|
| **Cơ chế tracking vị trí** | LLE tự chế | Inventory Dimension core (field `vi_tri_kho` trên SLE) |
| **Repost backdated** | Không tự động | Core tự động (repost_future_sle_and_gle) |
| **Valuation** | Không có location-level | AVCO/FIFO pool warehouse-level |
| **Báo cáo** | 40+ báo cáo custom | Stock Balance/Stock Ledger mặc định filter dimension |
| **Code cần duy trì** | ~5000 dòng LLE | ~0 (chỉ override SR) |
| **Độ tin cậy** | Trung bình (nhiều lỗi đã phát hiện) | Cao (core đã test rộng) |
| **Khả năng mở rộng** | Chỉ location | Thêm dimension khác không cần code |

### 14.3 Các bước triển khai

**Bước 1 — Cấu hình Inventory Dimension:**
- Tạo Inventory Dimension "Vị trí kho", reference = "Vi tri kho", apply_to_all = ✅
- Core tự động thêm field `vi_tri_kho` + `to_vi_tri_kho` vào tất cả inventory documents

**Bước 2 — Override Stock Reconciliation validation:**
```python
def validate(self):
    # Bỏ gọi validate_inventory_dimension() core
    super().validate()  # nhưng skip dòng validate_inventory_dimension
    # Thêm remove_items_with_no_change_with_dimension()
```

**Bước 3 — Override Stock Reconciliation on_submit:**
```python
def on_submit(self):
    if self.purpose == "Opening Stock":
        return super().on_submit()
    # Periodic: sinh Stock Entry
    self.generate_stock_entries_from_items()
```

**Bước 4 — Tắt LLE + Migration dữ liệu (xem Mục 18)**

---

Các mục từ 15-20 tiếp nối trong phần đã xây dựng bên dưới.



### 14.1 Mô hình tổng quát

Sau khi kiểm tra trực tiếp code của `stock_ledger.py`, đây là cách core vận hành:

```
Stock Ledger Entry (SLE) chứa:
  - item_code, warehouse: key chính
  - vi_tri_kho: Inventory Dimension field (custom field, core tự thêm)
  - actual_qty, qty_after_transaction
  - valuation_rate, stock_value, stock_queue (FIFO)
  - stock_value_difference

Khi process_sle() chạy:
  self.wh_data = self.data[sle.warehouse]     ← KEY = WAREHOUSE, không phải (warehouse + dimension)
  
  → valuation_rate là MỘT giá trị chung cho toàn bộ warehouse (pool)
  → stock_queue (FIFO) cũng là queue chung của warehouse
  → qty_after_transaction: TỔNG số lượng của warehouse
```

**Ý nghĩa: Số lượng có thể được xem riêng theo dimension (qua get_stock_balance với filter), nhưng giá trị (valuation rate, stock queue) luôn là pool chung của warehouse.**

Đây chính xác là điều bạn mong muốn:
- **Số lượng (qty):** quản lý theo `(item_code + warehouse + dimension)`
- **Giá trị (valuation):** pool chung `(item_code + warehouse)`

### 14.2 Moving Average với Dimension (xác nhận từ code thật)

```python
# stock_ledger.py dòng 1033-1061
def get_moving_average_values(self, sle):
    actual_qty = flt(sle.actual_qty)
    new_stock_qty = flt(self.wh_data.qty_after_transaction) + actual_qty
    if new_stock_qty >= 0:
        if actual_qty > 0:
            if flt(self.wh_data.qty_after_transaction) <= 0:
                self.wh_data.valuation_rate = sle.incoming_rate
            else:
                new_stock_value = (self.wh_data.qty_after_transaction * self.wh_data.valuation_rate) + (
                    actual_qty * sle.incoming_rate
                )
                self.wh_data.valuation_rate = new_stock_value / new_stock_qty
```

- `self.wh_data` là **warehouse-level data** (đã xác nhận dòng 555)
- `self.wh_data.valuation_rate` là **một giá trị duy nhất cho cả warehouse**
- Khi nhập 10 unit vào dimension A với rate 100, và nhập 5 unit vào dimension B với rate 110:
  - `new_stock_qty = 15` (tổng warehouse)
  - `new_stock_value = (10*100) + (5*110) = 1550`
  - `valuation_rate = 1550/15 = 103.33` (pool chung)
  - SLE cho dim A: `qty_after_transaction=10, valuation_rate=103.33`
  - SLE cho dim B: `qty_after_transaction=5, valuation_rate=103.33`

### 14.3 FIFO với Dimension (xác nhận từ code thật)

```python
# stock_ledger.py dòng 1072-1118
def update_queue_values(self, sle):
    # stock_queue CŨNG là warehouse-level
    stock_queue = FIFOValuation(self.wh_data.stock_queue)  # queue chung warehouse
    _prev_qty, prev_stock_value = stock_queue.get_total_stock_and_value()
    
    if actual_qty > 0:
        stock_queue.add_stock(qty=actual_qty, rate=incoming_rate)
    else:
        stock_queue.remove_stock(...)
    
    self.wh_data.stock_queue = stock_queue.state
    self.wh_data.stock_value = round_off_if_near_zero(...)
    
    if self.wh_data.qty_after_transaction:
        self.wh_data.valuation_rate = self.wh_data.stock_value / self.wh_data.qty_after_transaction
```

- FIFO Queue là **chung cho warehouse**
- Khi xuất hàng từ dimension bất kỳ, queue lấy từ đầu (FIFO) hoặc cuối (LIFO) bất kể dimension
- `valuation_rate` tính từ `stock_value / qty_after_transaction` (pool)
- Dimension trong SLE chỉ có ý nghĩa cho qty, không cho valuation

### 14.4 Bin update (xác nhận từ code thật)

```python
# stock_ledger.py dòng 1224-1244
def update_bin_data(self, sle):
    bin_name = get_or_make_bin(sle.item_code, sle.warehouse)
    values_to_update = {
        "actual_qty": sle.qty_after_transaction,    # TỔNG qty warehouse
        "stock_value": sle.stock_value,
    }
    if sle.valuation_rate is not None:
        values_to_update["valuation_rate"] = sle.valuation_rate
    frappe.db.set_value("Bin", bin_name, values_to_update)
```

**Quan trọng:** Bin chỉ có actual_qty ở **warehouse-level** (không phân theo dimension). Nếu cần xem tồn kho theo dimension, phải query SLE trực tiếp qua `get_stock_balance()` với `inventory_dimensions_dict`.

### 14.5 GL Entry (xác nhận từ code thật)

```python
# stock_controller.py dòng 69-95
def make_gl_entries(self, gl_entries=None, from_repost=False, via_landed_cost_voucher=False):
    if cint(erpnext.is_perpetual_inventory_enabled(self.company)):
        warehouse_account = get_warehouse_account_map(self.company)
        if self.docstatus == 1:
            gl_entries = self.get_gl_entries(warehouse_account)
        make_gl_entries(gl_entries, from_repost=from_repost)

def get_gl_entries(self, warehouse_account=None, ...):
    sle_map = self.get_stock_ledger_details()    # SLE của voucher này
    for item_row in voucher_details:
        sle_list = sle_map.get(item_row.name)
        for sle in sle_list:
            if warehouse_account.get(sle.warehouse):
                # GL Entry: Dr/Cr Stock In Hand account
                # Amount = stock_value_difference
                # stock_value_difference = thay đổi stock_value warehouse-level
```

GL Entry dựa trên `stock_value_difference` từ warehouse-level. Khi có dimension, GL Entry **vẫn đúng** vì:
- `stock_value_difference` = thay đổi giá trị tồn kho của warehouse
- Dimension chỉ ảnh hưởng số lượng, không ảnh hưởng giá trị tổng
- Kế toán theo warehouse, không cần theo dimension

### 14.6 Tổng kết mô hình dữ liệu

```
Item + Warehouse (pool valuation: rate, stock_queue, stock_value, Bin)
  │
  ├── Dimension A: qty = 10, rate = rate_pool (chung)
  ├── Dimension B: qty = 5,  rate = rate_pool (chung)
  └── Dimension C: qty = 0,  rate = rate_pool (chung)
      
Bin (Item, Warehouse):
  actual_qty      = 15 (= tổng qty các dimension)
  valuation_rate  = rate_pool
  stock_value     = 15 * rate_pool

GL Entry:
  account         = Stock In Hand - Warehouse
  debit/credit    = stock_value_difference (warehouse-level)
  (không phân theo dimension)
```

### 14.7 get_stock_balance với Dimension (xác nhận từ code thật)

```python
# stock/utils.py dòng 94-153
def get_stock_balance(item_code, warehouse, posting_date=None, posting_time=None,
                      with_valuation_rate=False, inventory_dimensions_dict=None, ...):
    args = {"item_code": item_code, "warehouse": warehouse, ...}
    
    extra_cond = ""
    if inventory_dimensions_dict:
        for field, value in inventory_dimensions_dict.items():
            column = frappe.utils.sanitize_column(field)
            args[field] = value
            extra_cond += f" and {column} = %({field})s"
    
    last_entry = get_previous_sle(args, extra_cond=extra_cond)
    # Trả về qty_after_transaction tại đúng dimension đó
    # và valuation_rate (pool chung của warehouse)
```

→ Khi gọi `get_stock_balance(item_code, warehouse, dim_field=value)`:
- `qty_after_transaction` = số lượng **tại dimension đó**
- `valuation_rate` = **rate pool chung của warehouse**

---

<a name="15"></a>
## 15. [MỚI] Kiểm tra code thật: Repost backdated và ảnh hưởng đến tồn kho theo Dimension

### 15.1 Pipeline repost

```python
# stock_controller.py dòng 894-915
def repost_future_sle_and_gle(self, force=False):
    args = frappe._dict({
        "posting_date": self.posting_date,
        "posting_time": self.posting_time,
        "voucher_type": self.doctype,
        "voucher_no": self.name,
        "company": self.company,
    })
    if force or future_sle_exists(args) or repost_required_for_queue(self):
        item_based_reposting = cint(...)
        if item_based_reposting:
            create_item_wise_repost_entries(voucher_type=..., voucher_no=...)
        else:
            create_repost_item_valuation_entry(args)
```

Repost sử dụng `Repost Item Valuation` DocType:
- Queue item để xử lý bất đồng bộ
- Khi chạy, nó **gọi lại process_sle() cho từng SLE** từ thời điểm backdated đến nay
- SLE có dimension → `process_sle()` xử lý đúng vì:
  - `self.data` keyed bằng warehouse (dòng 555)
  - valuation_rate/stock_queue là warehouse-level
  - Dimension chỉ là field đi kèm, không ảnh hưởng valuation

### 15.2 Kiểm tra tính nhất quán khi backdated

Khi một Stock Entry backdated được submit:

1. Core phát hiện có future SLE → queue Repost Item Valuation
2. Repost chạy: đọc lại tất cả SLE từ thời điểm backdated → nay
3. Với mỗi SLE, chạy `process_sle()`:
   - AVCO: tính lại `valuation_rate` = pool chung
   - FIFO: tính lại `stock_queue` = queue chung
   - `Bin.actual_qty`, `Bin.stock_value` được update lại
   - GL Entry được update lại
4. Dimension field trong SLE **giữ nguyên** (không thay đổi khi repost)
5. `qty_after_transaction` trên SLE có dimension filter = số lượng cuối cùng tại dimension đó

→ **Repost với dimension: core tự động đúng, không cần custom.**

### 15.3 Trường hợp đặc biệt: Cancel Stock Reconciliation

Khi cancel SR (có dimension) mà dùng core pipeline (không qua sinh Stock Entry):

```python
# stock_reconciliation.py dòng 73-78
def on_cancel(self):
    self.ignore_linked_doctypes = ("GL Entry", "Stock Ledger Entry", "Repost Item Valuation")
    self.make_sle_on_cancel()
    self.make_gl_entries_on_cancel()
    self.repost_future_sle_and_gle()
```

Và `get_sle_for_items()` khi cancel với dimension (dòng 471-488):

```python
elif self.docstatus == 1 and has_dimensions and not row.batch_no:
    # Submit → actual_qty = row.qty (opening)
    data.actual_qty = row.qty
    data.qty_after_transaction = 0.0
```

Khi cancel, `make_sle_on_cancel()` gọi lại `get_sle_for_items()` với docstatus=2, branch khác:

```python
if self.docstatus == 2 and not row.batch_no:
    if row.current_qty:
        data.actual_qty = -1 * row.current_qty
        data.qty_after_transaction = flt(row.current_qty)
    else:
        data.actual_qty = row.qty
        data.qty_after_transaction = 0.0
```

**Với giải pháp sinh Stock Entry (Periodic SR):** Khi cancel SR periodic → cancel các Stock Entry đã sinh → core tự repost → đúng.

---

<a name="16"></a>
## 16. [MỚI] Đối chiếu Inventory Dimension với Location Ledger (LLE) hiện tại

### 16.1 Hiện trạng LLE trên eupapp

Sau khi kiểm tra code thật, LLE tự chế có các đặc điểm:

| Thành phần | File | Chức năng |
|---|---|---|
| **DocType Location Ledger Entry** | `eup_stock/doctype/location_ledger_entry/` | Bảng ghi sổ vị trí riêng |
| **DocType Location Bin** | `eup_stock/doctype/location_bin/` | Tồn kho theo vị trí |
| **DocType Vi tri kho** | `eup_stock/doctype/vi_tri_kho/` | Danh mục vị trí |
| **location_ledger.py** | `eup_stock/location_ledger.py` | Engine ghi LLE |
| **lle_sle_link.py** | `eup_stock/lle_sle_link.py` | Liên kết LLE → SLE |
| **Stock Reconciliation Location** | `eup_stock/doctype/stock_reconciliation_location/` | Child table SR chứa location |
| **Stock Entry Location** | `eup_stock/doctype/stock_entry_location/` | Child table SE chứa location |
| **Stock Reconciliation override** | `overrides/stock_reconciliation.py` | Gọi `update_location_ledger()` sau `on_submit()` |
| **Stock Entry override** | `overrides/stock_entry.py` | Gọi `update_location_ledger()` sau `on_submit()` |

### 16.2 So sánh LLE vs Inventory Dimension

| Tiêu chí | LLE (hiện tại) | Inventory Dimension (core) |
|---|---|---|
| **SLE integration** | Thủ công (qua lle_sle_link) | ✅ Core tự động ghi dimension field vào SLE |
| **Repost backdated** | ❌ Không tự động — LLE sai nếu có backdated | ✅ Core `repost_future_sle_and_gle()` tự repost SLE, không mất dimension |
| **Valuation** | ❌ Không có (location không có rate) | ✅ AVCO/FIFO pool chung, dimension chỉ ảnh hưởng qty |
| **Bin** | Location Bin riêng — không đồng bộ | ✅ Core Bin warehouse-level (qty tổng) |
| **Báo cáo** | Tự chế (nxstock_balance_location, location_ledger) | ✅ Stock Balance filter theo dimension |
| **Performance** | 2 pipeline (SLE + LLE) | 1 pipeline (SLE) |
| **Thêm dimension mới** | Phải tạo DocType + child table + code | ✅ Cấu hình qua UI, core tự thêm field |
| **Độ tin cậy** | Tự code — nhiều lỗi tiềm ẩn | ✅ Core ERPNext — đã test rộng |
| **Audit trail** | LLE riêng — khớp với SLE? | ✅ SLE là source of truth |
| **Số lượng code cần duy trì** | ~20 file, ~5000 dòng | ~0 (chỉ override SR cho periodic) |
| **Rủi ro migrate** | Có (đang chạy thực tế) | Có thể migrate dần |

### 16.3 Các vấn đề đã phát hiện trên LLE hiện tại

1. **`remove_items_with_no_change()` bị pass (no-op)**
   - File: `stock_reconciliation.py` override, dòng 196-197
   - Hậu quả: SR không tự động xoá dòng không thay đổi → user dễ nhầm
   - Core gốc có chức năng này và fetch `current_qty` + `current_valuation_rate` tự động

2. **`validate_inventory_dimension()` không được override**
   - File: `stock_reconciliation.py` override
   - Nếu Inventory Dimension được bật (dù chưa dùng), core throw → block SR
   - Cần override để skip vì dùng LLE thay vì Dimension

3. **Hai pipeline không đồng bộ**
   - SLE và LLE là 2 bảng riêng, liên kết qua FK `sle_entry` trong LLE
   - Nếu SLE bị repost (do backdated), LLE không tự động được repost
   - Các repair tool (`lle_qat_repair.py`, `lle_cleanup.py`, `lle_reconcile_default.py`) sinh ra để vá lỗi đồng bộ

4. **Location Bin không có valuation**
   - `Location Bin` chỉ có qty, không có `stock_value`, `valuation_rate`
   - Không thể tính giá trị tồn kho theo vị trí

5. **Code phức tạp, khó bảo trì**
   - ~40 báo cáo custom cho location
   - ~15 file test cho LLE
   - Mỗi lần core update có thể ảnh hưởng đến logic LLE

---

<a name="17"></a>
## 17. [MỚI] Chiến lược thay thế LLE bằng Inventory Dimension (kế hoạch migration)

### 17.1 Kiến trúc mục tiêu

```
ERPNext core pipeline (đã hỗ trợ đầy đủ dimension):
┌──────────────────────────────────────────────────────────────────┐
│  Stock Entry / Purchase Receipt / Delivery Note                  │
│  → get_sl_entries() → update_inventory_dimensions()              │
│    → SLE (có vi_tri_kho dimension)                               │
│      → process_sle() (AVCO/FIFO pool warehouse-level)            │
│        → Bin update (warehouse-level)                            │
│        → GL Entry (warehouse-level)                              │
│        → Repost (nếu backdated)                                  │
└──────────────────────────────────────────────────────────────────┘

Custom override (eupapp) — CHỈ xử lý Stock Reconciliation:
┌──────────────────────────────────────────────────────────────────┐
│  Stock Reconciliation (Purpose = "Stock Reconciliation"):        │
│    1. validate():                                                │
│       - remove_items_with_no_change()  (dùng get_stock_balance   │
│         với inventory_dimensions_dict)                           │
│       - KHÔNG gọi validate_inventory_dimension() core            │
│    2. on_submit():                                               │
│       - Phân tích delta theo dimension                           │
│       - Sinh Stock Entry tương ứng (Material Receipt/Issue/Transfer)│
│    3. on_cancel():                                               │
│       - Cancel các Stock Entry đã sinh                           │
└──────────────────────────────────────────────────────────────────┘
```

### 17.2 Kế hoạch migration chi tiết

#### Phase 0: Chuẩn bị (2-3 ngày)

1. **Cấu hình Inventory Dimension "Vị trí kho"**
   - Vào Inventory Dimension → New
   - Reference Document: "Vi tri kho" (DocType đã có sẵn)
   - Dimension Name: "Vị trí kho"
   - Apply to All Inventory Documents: ✅
   - Core tự động thêm custom field `vi_tri_kho` vào:
     - Stock Reconciliation Item
     - Stock Entry Detail
     - Purchase Receipt Item
     - Delivery Note Item
     - Sales Invoice Item
     - Stock Ledger Entry
   - Core tự động thêm `to_vi_tri_kho` và `from_vi_tri_kho` cho transfer docs

2. **Rà soát Stock Entry Location + Stock Reconciliation Location**
   - Giữ nguyên (không xoá) — dùng để UI hiện tại vẫn hoạt động trong thời gian chuyển đổi
   - Thêm custom field `vi_tri_kho` vào Stock Entry Detail và Stock Reconciliation Item
   - Đồng bộ dữ liệu: script copy `location` → `vi_tri_kho` trên các bảng con

3. **Tạo helper function đồng bộ location → dimension**
   ```python
   def sync_location_to_dimension(doc, method=None):
       """Đồng bộ từ location cũ sang dimension field mới"""
       dimension_field = "vi_tri_kho"
       # Stock Reconciliation: location_items → items.vi_tri_kho
       if doc.doctype == "Stock Reconciliation":
           for item in doc.items:
               if not item.get(dimension_field):
                   # Tìm location tương ứng
                   for loc_item in doc.get("location_items") or []:
                       if (loc_item.item_code == item.item_code 
                           and loc_item.warehouse == item.warehouse
                           and (loc_item.batch_no == item.batch_no or not loc_item.batch_no)):
                           item.db_set(dimension_field, loc_item.location)
                           break
   ```

#### Phase 1: Override Stock Reconciliation (5-7 ngày)

Chi tiết trong Mục 13 và Mục 18. Các thay đổi chính:

1. **`EupStockReconciliation.validate()`**
   - Replace `remove_items_with_no_change()` (dùng `get_stock_balance` với dimension_dict)
   - Skip `validate_inventory_dimension()` của core
   - Giữ nguyên các validate khác

2. **`EupStockReconciliation.on_submit()`**
   - Nếu Purpose = "Opening Stock" → `super().on_submit()` (core pipeline)
   - Nếu Purpose = "Stock Reconciliation" (periodic) → `generate_stock_entries_from_items()`
   - KHÔNG gọi `update_location_ledger()` (LLE cũ)

3. **`EupStockReconciliation.on_cancel()`**
   - Cancel các Stock Entry đã sinh
   - KHÔNG gọi `make_lle_on_cancel()`

#### Phase 2: Override Stock Entry (3-5 ngày)

1. **`EupStockEntry.on_submit()`**
   - Bỏ gọi `update_location_ledger()` (LLE cũ)
   - Thêm validate: warehouse có `must_update_location=1` → bắt buộc `vi_tri_kho`
   - Giữ nguyên các logic khác (cập nhật ycxh, công đơn, ...)

2. **`EupStockEntry.before_submit()`**
   - Bỏ `validate_warehouse_require_location()` (dùng location_items)
   - Thêm `validate_warehouse_require_dimension()` (dùng vi_tri_kho field)

#### Phase 3: Data Migration (3-5 ngày)

1. **Migration LLE → gán vi_tri_kho cho SLE**
   ```sql
   -- Với mỗi LLE, tìm SLE tương ứng và gán vi_tri_kho
   UPDATE `tabStock Ledger Entry` sle
   JOIN `tabLocation Ledger Entry` lle 
     ON lle.sle_entry = sle.name
   SET sle.vi_tri_kho = lle.location
   WHERE sle.vi_tri_kho IS NULL
     AND lle.location IS NOT NULL;
   ```

2. **Đồng bộ Stock Reconciliation Item**
   ```sql
   UPDATE `tabStock Reconciliation Item` sri
   JOIN `tabStock Reconciliation Location` srl
     ON srl.parent = sri.parent
     AND srl.item_code = sri.item_code
     AND srl.warehouse = sri.warehouse
     AND (srl.batch_no = sri.batch_no OR (srl.batch_no IS NULL AND sri.batch_no IS NULL))
   SET sri.vi_tri_kho = srl.location
   WHERE sri.vi_tri_kho IS NULL;
   ```

3. **Đồng bộ Stock Entry Detail**
   ```sql
   UPDATE `tabStock Entry Detail` sed
   JOIN `tabStock Entry Location` sel
     ON sel.parent = sed.parent
     AND sel.item_code = sed.item_code
     AND (sel.batch_no = sed.batch_no OR (sel.batch_no IS NULL AND sed.batch_no IS NULL))
   SET sed.vi_tri_kho = sel.s_location
   WHERE sed.vi_tri_kho IS NULL
     AND sel.s_location IS NOT NULL
     AND sel.s_warehouse = sed.s_warehouse;
   
   UPDATE `tabStock Entry Detail` sed
   JOIN `tabStock Entry Location` sel
     ON sel.parent = sed.parent
     AND sel.item_code = sed.item_code
     AND (sel.batch_no = sed.batch_no OR (sel.batch_no IS NULL AND sed.batch_no IS NULL))
   SET sed.to_vi_tri_kho = sel.t_location
   WHERE sed.to_vi_tri_kho IS NULL
     AND sel.t_location IS NOT NULL
     AND sel.t_warehouse = sed.t_warehouse;
   ```

#### Phase 4: Tắt LLE (2-3 ngày)

1. **Tắt sinh LLE trong Stock Reconciliation override**
   - Xoá `update_location_ledger()` và `update_location_ledger_remain()` khỏi `EupStockReconciliation`
   - Xoá `make_lle_on_cancel()`, `make_lle_on_cancel_remain()`
   - Xoá `get_lle_for_items()`, `get_lle_for_serialized_items()`

2. **Tắt sinh LLE trong Stock Entry override**
   - Xoá `update_location_ledger()` khỏi `EupStockEntry`
   - Xoá `get_ll_entries()`, `make_ll_entries()`

3. **Chuyển báo cáo từ LLE sang SLE dimension**
   - `nxstock_balance_location` → Stock Balance Report với filter `vi_tri_kho`
   - `location_ledger` → Stock Ledger Report với filter `vi_tri_kho`
   - Các báo cáo khác tương tự

#### Phase 5: UAT & Go-live (1 tuần)

- Chạy song song với LLE trong 1 tuần
- Đối chiếu số liệu: SLE.vi_tri_kho vs LLE.location
- Fix bug nếu có
- Go-live

### 17.3 File cần sửa trong eupapp

| File | Thay đổi | Mức độ |
|---|---|---|
| `eupapp/doctype/overrides/stock_reconciliation.py` | Override toàn bộ: `validate()`, `on_submit()`, `on_cancel()`, `remove_items_with_no_change()`, thêm `generate_stock_entries_from_items()` | 🔴 Lớn |
| `eupapp/doctype/overrides/stock_entry.py` | Bỏ `update_location_ledger()`, thêm validate dimension bắt buộc | 🟡 Vừa |
| `eupapp/doctype/overrides/stock_ledger_entry.py` | Giữ nguyên (per-warehouse negative stock) | 🟢 Giữ |
| `eup_stock/location_ledger.py` | Đánh dấu deprecated, giữ lại cho migration | 🟡 Vừa |
| `eup_stock/lle_sle_link.py` | Không cần dùng nữa | 🟢 Xoá |
| `eup_stock/negative_policy.py` | Giữ nguyên | 🟢 Giữ |
| `eup_stock/stock_ledger.py` | Có thể giảm tải | 🟢 Nhỏ |
| `eup_stock/utils.py` | Có thể giữ `get_batch_location_qty()` cho migration | 🟢 Nhỏ |

### 17.4 Các file KHÔNG cần sửa

- `erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py` (core)
- `erpnext/stock/doctype/inventory_dimension/inventory_dimension.py` (core)
- `erpnext/controllers/stock_controller.py` (core)
- `erpnext/stock/stock_ledger.py` (core)
- `erpnext/stock/valuation.py` (core)
- Bất kỳ file core nào khác

---

<a name="18"></a>
## 18. [MỚI] Sản xuất, Kế toán và các tình huống đặc thù

### 18.1 Sản xuất (Manufacture) với Dimension

Stock Entry Manufacture **đã hỗ trợ dimension sẵn** qua core `update_inventory_dimensions()`. Các tình huống:

| Purpose | Hành vi core với dimension | Tự động? |
|---|---|---|
| **Manufacture** (nhập TP) | `s_warehouse` (NVL) có dimension → ghi `vi_tri_kho` vào SLE âm; `t_warehouse` (TP) có dimension → ghi `to_vi_tri_kho` vào SLE dương | ✅ Core |
| **Material Consumption for Manufacture** | `s_warehouse` (NVL) có dimension | ✅ Core |
| **Material Transfer for Manufacture** | `s_warehouse` và `t_warehouse` có dimension | ✅ Core |

**Cần custom:** UI chọn dimension cho người dùng khi tạo Stock Entry Manufacture:
- Khi fetch items từ Work Order, tự động điền dimension từ item default hoặc BOM
- Nếu warehouse có `must_update_location=1`, bắt buộc nhập `vi_tri_kho` (đã validate ở Phase 2)

### 18.2 Kế toán (GL) với Dimension

Như đã phân tích ở Mục 14.5, GL Entry luôn ở warehouse-level. Dimension không ảnh hưởng đến kế toán:

```
Stock Entry (Material Receipt) 100 units, rate 50.000đ
→ SLE: vi_tri_kho = "Kệ A", actual_qty = 100, valuation_rate = 50.000
→ GL: Dr Stock In Hand (Warehouse) 5.000.000đ
      Cr Stock Adjustment 5.000.000đ
```

Khi xuất kho:

```
Stock Entry (Material Issue) 30 units từ "Kệ A"
→ SLE: vi_tri_kho = "Kệ A", actual_qty = -30, outgoing_rate = 50.000
→ GL: Dr Cost of Goods Sold 1.500.000đ
      Cr Stock In Hand (Warehouse) 1.500.000đ
```

**Kết luận:** Kế toán không cần custom — core đã xử lý đúng.

### 18.3 Các tình huống đặc thù

| Tình huống | Hành vi core | Cần custom? |
|---|---|---|
| **Nhập kho từ PO**, dimension = "Kệ A" | PR Item có `vi_tri_kho` → SLE ghi `vi_tri_kho` | ❌ Core tự động |
| **Xuất kho theo DN**, dimension = "Kệ A" | DN Item có `vi_tri_kho` → SLE ghi `vi_tri_kho` | ❌ Core tự động |
| **Chuyển kho** Kệ A → Kệ B | SE Detail: `vi_tri_kho`=A, `to_vi_tri_kho`=B → SLE: A (-qty), B (+qty) | ❌ Core tự động |
| **Kiểm kê** (periodic) | SR có dimension nhưng bị chặn | ✅ Override (Mục 13, 17) |
| **Điều chỉnh giá trị** (value-only) | Cần dimension + delta qty=0 | ✅ SLE actual_qty=0 (Mục 8) |
| **Sản xuất nhập TP** | SE Manufacture có dimension | ❌ Core tự động |
| **Sản xuất tiêu hao NVL** | SE Material Consumption có dimension | ❌ Core tự động |
| **Backdated entry** | Core repost tự động | ❌ Core tự động |

---

<a name="20"></a>
## 20. [MỚI] Cách các ERP Tier-1 xử lý — và áp dụng vào giải pháp của ERPNext/eupapp

### 20.1 Phân tích chuyên sâu cách SAP, Oracle NetSuite, Dynamics 365 xử lý Inventory Dimension

Sau khi nghiên cứu và đối chiếu giữa các hệ thống Tier-1 với ERPNext, dưới đây là bản phân tích chi tiết:

#### SAP S/4HANA

| Khái niệm | Cách SAP định nghĩa | Tương ứng trong ERPNext |
|---|---|---|
| **Plant (Nhà máy)** | Valuation area mặc định — giá trị tồn kho được quản lý ở cấp này | Warehouse (ERPNext warehouse ≈ SAP plant) |
| **Storage Location (Vị trí lưu trữ)** | Tổ chức trong Plant, có thể active valuation riêng (OMB2). Mặc định valuation ở Plant-level | Inventory Dimension (nếu cần valuation theo vị trí) |
| **Storage Bin (Kệ/Ô)** | Chỉ track số lượng, **không ảnh hưởng valuation**. Dùng trong EWM | Inventory Dimension (chỉ track qty, rate pool chung) |
| **Batch (Lô)** | Có thể active **Split Valuation** — định giá riêng theo batch (OMJJ) | Batch tracking — valuation riêng nếu `use_batchwise_valuation=1` |
| **Split Valuation** | Cho phép định giá riêng theo: procurement type, origin, batch | Inventory Dimension + valuation method |
| **MR21/MR22** | Giao dịch thay đổi giá trị tồn kho — **tách riêng khỏi physical movement** | SLE `actual_qty=0` — core đã hỗ trợ (Mục 8.1) |

**Cấu hình SAP (OBYC):**
```
Plant (valuation area)
  └── Storage Location (tài khoản GL riêng nếu active)
       └── Storage Bin (EWM — chỉ track qty, không valuation)
```

**Cách SAP xử lý kiểm kê (Physical Inventory):**
```
PI Document → Count → Post Difference
  → Nếu thừa: Goods Receipt (MB1C) → 561 movement type
  → Nếu thiếu: Goods Issue (MB1B) → 562 movement type
  → Chỉ đổi giá trị: MR21 (Price Change) — không movement
```

→ **Giống hệt giải pháp của ERPNext: Stock Entry = Goods Movement; value-only adjustment = MR21.**

#### Oracle NetSuite

| Khái niệm | NetSuite | ERPNext tương ứng |
|---|---|---|
| **Location** | Cấp valuation — mỗi Location có cost riêng | Warehouse |
| **Bin** | Chỉ track qty — không ảnh hưởng cost | Inventory Dimension (qty) |
| **Average Costing** | Mỗi Location có average cost riêng | AVCO pool per Warehouse |
| **FIFO** | Cost layers per Location | FIFO queue per Warehouse |

**Giới hạn NetSuite:** Bin location **không được hỗ trợ trong inventory valuation** — chỉ dùng để tổ chức vật lý. Báo cáo Inventory Valuation theo Bin là **không có sẵn** (chỉ có Bin-level qty, không có value).

#### Microsoft Dynamics 365

| Khái niệm | D365 | ERPNext tương ứng |
|---|---|---|
| **Site** | Cấp cao nhất | Warehouse (group) |
| **Warehouse** | Cấp valuation | Warehouse |
| **Location (bin)** | Storage dimension — **phân loại Financial/Physical** | Inventory Dimension |
| **Financial inventory dimension** | Ảnh hưởng valuation (site, warehouse) | Warehouse |
| **Physical inventory dimension** | Chỉ track qty (location, pallet, batch) | Inventory Dimension (qty) |

**Cấu hình D365 quan trọng:**
```
Storage Dimension Groups:
  - Site: financial inventory (valuation)
  - Warehouse: financial inventory (valuation)
  - Location: PHYSICAL inventory (chỉ qty)
  - Pallet ID: physical inventory (chỉ qty)
```

Dynamics phân loại storage dimensions thành 2 loại rõ rệt — "financial" (ảnh hưởng giá trị) và "physical" (chỉ số lượng). Đây là kiến trúc mà ERPNext cũng đang áp dụng: Warehouse là financial dimension, còn Inventory Dimension (do người dùng tạo) mang tính physical.

### 20.2 Nguyên tắc chuẩn toàn ngành

Từ phân tích 3 hệ thống Tier-1 (SAP, Oracle, Microsoft), có thể rút ra:

```
NGUYÊN TẮC VÀNG: Valuation Pool = Warehouse/Plant
  ____________________________________________________
  | Giá trị tồn kho (stock value) luôn được quản lý |
  | ở cấp warehouse/plant — không phân theo bin.     |
  | Bin/lot/dimension chỉ track số lượng.            |
  |__________________________________________________|
```

| Nguyên tắc | SAP | Oracle NS | D365 | ERPNext |
|---|---|---|---|---|
| Valuation = Warehouse/Plant | ✅ Plant | ✅ Location | ✅ Warehouse | ✅ Warehouse |
| Bin chỉ track qty | ✅ Bin (EWM) | ✅ Bin | ✅ Location (physical) | ✅ Inventory Dimension |
| Batch có thể định giá riêng | ✅ Split Valuation | ❌ Không | ✅ Batch dimension | ✅ use_batchwise_valuation |
| Kiểm kê tách biệt valuation | ✅ MR21/MR22 | ✅ Cost Adjustment | ✅ Inventory Journal | ✅ SLE actual_qty=0 |
| Giá trị theo bin | ❌ Không | ❌ Không | ❌ Không | ❌ Không (pool chung) |

### 20.3 Giải pháp của bạn — Đối chiếu với chuẩn ngành

Cách bạn đang thiết kế (và Phương án E của tài liệu này) **hoàn toàn khớp với chuẩn ngành**:

```
CÁCH BẠN LÀM (ERPNext + Inventory Dimension):
  ┌──────────────────────────────────────────────────────┐
  │  Warehouse (valuation pool):                         │
  │    - Stock value / Valuation rate / FIFO queue       │
  │    - GL Entry / Kế toán                             │
  │    - Bin.actual_qty = tổng qty warehouse            │
  │                                                      │
  │    ├── Dimension A (vd "Kệ A"): qty tracking        │
  │    │   - SLE.vi_tri_kho = "Kệ A"                    │
  │    │   - qty_after_transaction tại dim A            │
  │    │   - valuation_rate = pool rate chung            │
  │    │                                                │
  │    ├── Dimension B (vd "Kệ B"): qty tracking        │
  │    │   - SLE.vi_tri_kho = "Kệ B"                    │
  │    │   - qty_after_transaction tại dim B            │
  │    │   - valuation_rate = pool rate chung            │
  │    └── ...các dimension khác...                      │
  └──────────────────────────────────────────────────────┘

SO SÁNH VỚI SAP:
  Material A trong Plant P100:
    Plant-level: stock_value = 1000, avg_price = 50
      Storage Loc SL01: qty = 15 (chỉ qty, rate = 50)
      Storage Loc SL02: qty = 5  (chỉ qty, rate = 50)
  
  → GIỐNG HỆT ERPNext với Inventory Dimension!

SO SÁNH VỚI DYNAMICS 365:
  Item A trong Warehouse WH01:
    Financial dimension: Warehouse = WH01 (valuation pool)
    Physical dimension: Location = "Kệ A" (chỉ track qty)
  
  → GIỐNG HỆT ERPNext Inventory Dimension!
```

### 20.4 Những điểm ERPNext làm TỐT HƠN các hệ thống Tier-1

| Tính năng | SAP | Oracle NS | D365 | ERPNext |
|---|---|---|---|---|
| **Chi phí tạo dimension mới** | Cao (cần consultant, config) | Trung bình (Custom Segment) | Trung bình (Storage Dimension Group) | **Thấp** — chỉ cần tạo Inventory Dimension record |
| **Tích hợp với mọi chứng từ** | Phải config từng movement type | Phải custom | Phải setup mapping | **Tự động** — apply_to_all_doctypes |
| **Tự động ghi vào SLE** | Phải config | Không tự động | Phải setup | **✅ Core tự động** `update_inventory_dimensions()` |
| **Repost backdated** | Phải chạy batch job | Phải script | Batch job | **✅ Core tự động** `repost_future_sle_and_gle()` |
| **Kiểm kê theo dimension** | Cần custom program | Không hỗ trợ bin-level | Cần custom | **✅ Chỉ cần override SR** (Phương án E) |

### 20.5 Áp dụng vào eupapp — Kết luận

Chiến lược của bạn (dùng Inventory Dimension, qty theo dimension, rate pool chung warehouse) **không chỉ đúng — nó là chuẩn ngành ERP Tier-1**.

Những gì bạn đang làm:
1. ✅ **Số lượng theo dimension** → giống SAP Storage Bin, NetSuite Bin, D365 Location
2. ✅ **Valuation pool chung warehouse** → giống SAP Plant-level, NetSuite Location-level, D365 Warehouse-level
3. ✅ **Stock Reconciliation periodic → sinh Stock Entry** → giống SAP PI Document → Goods Movement
4. ✅ **Value-only adjustment → SLE actual_qty=0** → giống SAP MR21/MR22, NetSuite Cost Adjustment
5. ✅ **Tận dụng core pipeline SLE → GL → Bin → Repost** → giống tất cả ERP Tier-1

**Sự khác biệt duy nhất:** ERPNext làm việc này **linh hoạt và dễ dàng hơn** các hệ thống Tier-1 nhờ cơ chế Inventory Dimension tự động. Bạn không cần consultant SAP để config Split Valuation, không cần custom NetSuite để thêm segment — chỉ cần tạo 1 record Inventory Dimension và override 1 method.
---

<a name="21"></a>
## 21. [MỚI v6] GIẢI PHÁP MỞ RỘNG CHO NGÀNH NHÔM KÍNH XÂY DỰNG — KHO ĐA CHIỀU, ĐA ĐƠN VỊ TÍNH

### 21.1 Tổng quan yêu cầu ngành nhôm kính xây dựng

Ngành nhôm kính xây dựng có **đặc thù kho vận phức tạp** với nhiều loại vật tư có cách tính đơn vị, quy cách quản lý, và kiểu nhập/xuất khác nhau:

| Loại vật tư | Đơn vị mua | Đơn vị tồn kho | Đơn vị xuất | Quản lý theo | Cách tính giá |
|---|---|---|---|---|---|
| **Nhôm thanh (profile)** | kg | kg, m (dài) | kg, m (dài) | Màu sắc, Kích thước (dài×rộng), Dự án | kg |
| **Kính tấm** | m² | m², tấm | m², tấm | Kích thước (dài×rộng, có thể phức tạp), Độ dày, Màu sắc, Dự án | m² |
| **Vật tư phụ (keo, gioăng)** | cuộn/thùng | m, chai | m, chai | Cuộn → m; Thùng → chai | Đơn vị nhỏ nhất |
| **Phụ kiện (kẹp, nẹp, ốc vít)** | hộp/thùng | cái/bộ | cái/bộ | Quy cách, Dự án | cái/bộ |
| **Vật tư theo dự án** | kg/m² | kg/m² | kg/m² | Dự án (không phép trộn lẫn) | Theo dự án |


### 21.2 Mô hình Inventory Dimension đề xuất

Với ERPNext Inventory Dimension core, cần **3 Inventory Dimension** + trường `project` core có sẵn + cơ chế Dual-UOM (Item có 2 đơn vị tính song song):

#### Ma trận Dimension × Loại vật tư

| Inventory Dimension | Reference DocType | Nhôm | Kính | Keo/Gioăng | Phụ kiện |
|---|---|---|---|---|---|---|
| **mau_sac** (Màu sắc) | Item Attribute Value | ✅ Nhôm màu (đen, trắng, ghi...) | ✅ Kính màu, phủ | ❌ | ❌ |
| **kich_thuoc** (Kích thước) | Item Attribute Value | ✅ Dài × rộng × dày | ✅ Dài × rộng × dày, hình dạng | ✅ Dài/đường kính | ✅ Size |
| **vi_tri_kho** (Vị trí kho) | Warehouse Location (Site) | ✅ Kệ/lô | ✅ Giá/kệ đứng | ✅ Kệ con | ✅ Hộc tủ |

#### Cách xử lý Dual-UOM (song song 2 đơn vị tính)

ERPNext Inventory Dimension core không hỗ trợ Dual-UOM tự nhiên trong Inventory Dimension (mỗi SLE chỉ có 1 UOM + qty). Với vật tư có 2 UOM song song (nhôm: vừa tính kg vừa tính mét dài; gioăng: mua cuộn, xuất theo mét), có 3 phương án:

| Phương án | Mô tả | Ưu điểm | Nhược điểm | Khuyến nghị |
|---|---|---|---|---|
| **UOM1: Item riêng** | Tạo 2 Item: "Nhôm đen 40x80 - kg" và "Nhôm đen 40x80 - m" | Đơn giản, core hỗ trợ | Nhân đôi Item, khó đồng bộ | ❌ Không khuyến nghị |
| **UOM2: Conversion Factor** | 1 Item UOM=kg, thêm UOM=m với conversion factor dựa trên trọng lượng/mét | Chỉ 1 Item, core hỗ trợ | Factor cố định, không linh hoạt nếu trọng lượng thay đổi | ✅ Khuyến nghị cho nhôm thanh đều |
| **UOM3: Custom fields trên SLE** | Dimension `kich_thuoc` quản lý biến thể; thêm `qty_m` (mét) và `qty_kg` (kg) trên SLE | Track cả 2, linh hoạt | Cần custom code trên SLE + báo cáo | ✅ Khuyến nghị cho kính tấm phi chuẩn |

**Khuyến nghị cuối cùng:** Dùng UOM2 làm chính, kết hợp UOM3 cho kính tấm có kích thước phức tạp (phi chuẩn, không thể dùng conversion factor cố định).


### 21.3 Thiết kế Item và khai báo Dimension

#### 21.3.1 Cấu hình Inventory Dimension trên UI

Vào **Inventory Dimension** → tạo 2 dimension mới (nếu chưa có `vi_tri_kho`): **Màu sắc** và **Kích thước**. Trường **Project** đã có sẵn trên mọi chứng từ, không cần tạo thêm.

**Dimension "Màu sắc" (mau_sac):**
```
DocType: Item Attribute Value  (dùng Item Attribute có sẵn)
Fieldname: mau_sac
Apply to All Inventory Documents: Yes
```

**Dimension "Kích thước" (kich_thuoc):**
```
DocType: Item Attribute Value  (dùng Item Attribute "Kích Thước")
Fieldname: kich_thuoc
Apply to All Inventory Documents: Yes
```

**Lưu ý quan trọng:** Trường **Dự án (Project)** đã có sẵn trong ERPNext trên tất cả inventory documents (Stock Entry, Purchase Receipt, Delivery Note, Stock Reconciliation...). **Không cần tạo Inventory Dimension cho Dự án** — dùng trường `project` có sẵn.

#### 21.3.2 Cấu hình Item Template + Variant cho nhôm, kính

**Phương pháp Item Variant (khuyến nghị cao nhất):**

Dùng Item Variant của ERPNext cho nhôm và kính — mỗi tổ hợp (màu sắc × kích thước × độ dày) là một Variant. Dimension `vi_tri_kho` dùng Inventory Dimension; `project` dùng trường core có sẵn (vì thay đổi theo giao dịch, không cố định).

```
Item Template: ALUMINUM_PROFILE (Nhôm thanh định hình)
  ├── Attributes: Màu sắc, Kích thước (dài x rộng x dày), Độ dày
  ├── UOM: kg
  ├── Has Variants: Yes
  │
  ├── Variant: ALU-BLACK-40x80x1.4 (Nhôm đen 40x80 dày 1.4mm)
  │   ├── mau_sac: Đen
  │   ├── kich_thuoc: 40x80x1.4
  │   ├── project: DA-NHA-PHAT-2025 (điền khi nhập/xuất)
  │   └── vi_tri_kho: [điền khi nhập/xuất]
  │
  └── Variant: ALU-WHITE-25x50x1.2 (Nhôm trắng 25x50 dày 1.2mm)
      ├── mau_sac: Trắng
      ├── kich_thuoc: 25x50x1.2
      ├── project: DA-NHA-PHAT-2025 (điền khi nhập/xuất)
      └── vi_tri_kho: [điền khi nhập/xuất]
```

#### 21.3.3 Dual-UOM chi tiết cho nhôm thanh

Nhôm thanh mua từ nhà cung cấp theo **kg**, nhưng quản lý tồn kho và xuất theo **mét dài** (thanh dài 6m, 5.8m...). ERPNext hỗ trợ Item Conversion:

```
Item: ALU-BLACK-40x80x1.4
UOM (Stock):     kg
UOM (Purchase):  kg   (Nhà cung cấp tính kg)
UOM (Sales):     m    (Xuất bán/xuất dự án theo mét dài)

Conversion Factor: 1 kg = 2.5 m  (dựa trên trọng lượng 0.4 kg/mét)
  → Công thức: mét = kg × 2.5
  → Ví dụ: mua 100 kg = 250 mét dài
```

**Vấn đề với Conversion Factor cố định:** Trọng lượng riêng của nhôm khác nhau theo từng profile. Giải pháp:

1. **Gán Conversion Factor trên mỗi Item Variant** — tính từ trọng lượng riêng của profile đó
2. **Tạo UOM "m" (mét dài)"** với factor = 1 / (trọng lượng kg/mét)
3. **Khi nhập kho:** ghi qty theo kg (UOM chính), hệ thống tự convert ra mét
4. **Khi xuất kho:** user nhập số mét, hệ thống tự convert ngược ra kg

**Nếu profile có trọng lượng thay đổi theo từng lô (không cố định):** Chọn UOM3 — custom field `qty_m` trên SLE.


---

<a name="22"></a>
## 22. [MỚI v6] VÍ DỤ CỤ THỂ THEO TỪNG LOẠI VẬT TƯ — TẤT CẢ TÌNH HUỐNG & PHƯƠNG ÁN XỬ LÝ

### 22.1 NHÓM NHÔM THANH (ALUMINUM PROFILE)

Đặc thù:
- Mua theo kg, tồn kho theo kg + mét, xuất theo mét hoặc kg
- Giá tính theo kg
- Mỗi profile có trọng lượng riêng (kg/m) khác nhau
- Quản lý theo: Màu sắc × Kích thước profile × Dự án × Vị trí kho

#### 22.1.1 Nhập mua nhôm thanh từ nhà cung cấp

| Thông tin | Giá trị |
|---|---|
| Item | ALU-BLACK-40x80x1.4 (Nhôm đen 40x80 dày 1.4mm) |
| UOM mua | kg |
| Số lượng mua | 500 kg |
| Đơn giá | 85.000 đ/kg |
| Màu sắc | Đen (từ Item Variant) |
| Kích thước | 40x80x1.4 (từ Item Variant) |
| Dự án | DA-NHA-PHAT-2025 |
| Vị trí kho | Kệ A01-Nhom |
| Thanh dài | 6m/thanh → 500 kg = 208.33 thanh = 1.250 mét dài |

**Thao tác trên UI:**

1. Purchase Receipt (hoặc Purchase Invoice):
   - Item: ALU-BLACK-40x80x1.4
   - Qty: 500, UOM: kg
   - Rate: 85.000
   - **project:** DA-NHA-PHAT-2025
   - **vi_tri_kho:** Kệ A01-Nhom

2. **Core tự động ghi SLE:**
   ```
   SLE: item=ALU-BLACK-40x80x1.4, warehouse=Kho NVL
        actual_qty=500, UOM=kg, incoming_rate=85.000
        project=DA-NHA-PHAT-2025
        vi_tri_kho=Kệ A01-Nhom
        mau_sac=Đen, kich_thuoc=40x80x1.4
   ```

3. **Valuation:** AVCO pool cho warehouse "Kho NVL" được cập nhật
   - Giả sử trước đó đã có 300 kg rate 82.000:
   - New rate = (300×82.000 + 500×85.000) / 800 = 83.875 đ/kg

**Xử lý dual-UOM (mét):** Nếu dùng UOM2 với conversion factor, khi nhập 500 kg thì hệ thống tự ghi nhận 1.250 mét.

#### 22.1.2 Xuất kho nhôm thanh (bán hàng hoặc xuất thi công)

| Thông tin | Giá trị |
|---|---|
| Item | ALU-BLACK-40x80x1.4 |
| Số lượng | 150 kg (≈ 375 mét dài) |
| Dự án | DA-NHA-PHAT-2025 |
| Vị trí xuất | Kệ A01-Nhom (ưu tiên) |

**Tình huống 1 — Đủ hàng tại 1 vị trí:**
- Delivery Note (nếu bán) hoặc Stock Entry Material Issue (nếu xuất thi công)
- Điền `project`, `vi_tri_kho`, `kich_thuoc`, `mau_sac` đúng với tồn kho
- Core tự động: SLE actual_qty = -150, outgoing_rate = AVCO pool = 83.875
- GL Entry: Dr Cost of Goods Sold, Cr Stock In Hand

**Tình huống 2 — Hàng nằm rải rác nhiều vị trí, không đủ 1 chỗ:**
- Tạo Delivery Note với nhiều dòng, mỗi dòng 1 vị trí:
  - Dòng 1: qty=80, vi_tri_kho=Kệ A01-Nhom
  - Dòng 2: qty=70, vi_tri_kho=Kệ A02-Nhom
- Core tự động ghi 2 SLE, mỗi SLE có dimension riêng

**Tình huống 3 — Xuất sai dự án (không đúng project trên tồn kho):**
- Core vẫn cho xuất được vì valuation là pool warehouse-level
- Nhưng tồn kho theo dimension sẽ sai — **cần validate khi xuất/delivery**
- → **Custom validation:** nếu Item được theo dõi theo dự án, bắt buộc nhập `project` và kiểm tra tồn kho tại dimension đó

#### 22.1.3 Chuyển kho nhôm giữa 2 vị trí trong cùng warehouse

| Tình huống | Thao tác |
|---|---|
| Chuyển Kệ A01 → Kệ B01 cùng Kho NVL | Stock Entry Material Transfer: Source=A01, Target=B01, Qty=50 kg |
| Chuyển từ Kho NVL → Bãi công trình DA | Stock Entry Material Transfer: Source=Kho NVL/Kệ A01, Target=Bãi CT/DA-NHA-PHAT, Qty=200 kg |

**Điểm đặc biệt với trường `project`:**
- Khi chuyển từ kho tổng → bãi dự án: `project` trên dòng Source có thể khác `project` trên dòng Target (nếu dự án khác)
- Core tạo 2 SLE: 1 SLE âm ở dimension cũ, 1 SLE dương ở dimension mới
- Valuation rate pool chung warehouse — không ảnh hưởng

#### 22.1.4 Kiểm kê nhôm

Tích hợp với Ma trận từ Mục 3 (các tình huống KK1-KK8):

**Ví dụ KK2 — Kiểm kê định kỳ, thừa nhôm tại vị trí A:**
```
Item: ALU-BLACK-40x80x1.4
Vị trí: Kệ A01-Nhom
Hệ thống: 150 kg | Thực tế: 165 kg | Delta: +15 kg
Dự án: DA-NHA-PHAT-2025

Xử lý: Stock Reconciliation (Periodic)
→ Override SR phát hiện delta_qty > 0
→ Sinh Stock Entry Material Receipt: qty=15 kg
  project=DA-NHA-PHAT-2025, vi_tri_kho=Kệ A01-Nhom
  incoming_rate = AVCO pool hiện tại
```

**Ví dụ KK4 — Kiểm kê, thừa vị trí A, thiếu vị trí B (cùng Item, cùng dự án):**
```
Item: ALU-WHITE-25x50x1.2
Dự án: DA-NHA-PHAT-2025

Vị trí A: hệ thống 80 | thực tế 95 | delta +15
Vị trí B: hệ thống 120| thực tế 105| delta -15
Tổng:    hệ thống 200| thực tế 200| delta 0

Xử lý: Stock Reconciliation
→ Override SR phát hiện: cùng item + warehouse, delta_A=+15, delta_B=-15
→ Match chéo → Sinh Stock Entry Material Transfer: A → B, qty=15
  (không ảnh hưởng valuation, không ảnh hưởng GL)
```

**Ví dụ KK5 — Kiểm kê, đúng số lượng, sai giá trị, có Dimension:**
```
Item: ALU-BLACK-40x80x1.4
Vị trí: Kệ A01-Nhom, Dự án: DA-NHA-PHAT-2025
Qty hệ thống = Qty thực tế = 200 kg
Valuation rate hệ thống: 83.875 đ/kg
Valuation rate đúng phải: 86.000 đ/kg

Xử lý: Override SR
→ delta_qty = 0, delta_rate ≠ 0
→ Ghi SLE: actual_qty=0, incoming_rate=86.000
  project=DA-NHA-PHAT-2025, vi_tri_kho=Kệ A01-Nhom
  stock_value_difference = (86.000 - 83.875) × 200 = 425.000 đ
→ Core AVCO pool tự update rate lên 86.000
→ GL Entry: Dr/Cr Stock In Hand 425.000đ
```

#### 22.1.5 Nhôm tồn — cắt thanh dài thành thanh ngắn (Repack)

Nhôm mua thanh 6m, khi thi công cần cắt thành 2.4m, 1.8m, 1.2m... Đây là nghiệp vụ **Repack** trong ERPNext.

```
Stock Entry (Purpose: Repack):
  Item (Source): ALU-BLACK-40x80x1.4 (thanh 6m)
    qty = -100 kg (= -250 mét)
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Kệ A01-Nhom

  Item (Target): ALU-BLACK-40x80x1.4-CAT (thanh 2.4m) — Item riêng
    qty = +40 kg
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Kệ A01-Nhom

  Item (Target): ALU-BLACK-40x80x1.4-CAT2 (thanh 1.8m) — Item riêng
    qty = +35 kg
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Kệ A01-Nhom
  ... (hao hụt cắt = 25 kg hạch toán vào phế liệu)
```

**Giải pháp tối ưu hơn:** Không cần tạo Item mới cho mỗi kích thước cắt — dùng **Item Variant** với Attribute "Chiều dài cắt" = 2.4m, 1.8m, 1.2m. Khi đó dimension `kich_thuoc` trên Variant sẽ phân biệt được.


### 22.2 NHÓM KÍNH TẤM (GLASS SHEET)

Đặc thù:
- Mua theo m², tồn kho theo m² + tấm, xuất theo m²
- Giá tính theo m²
- Kích thước tấm kính rất đa dạng: 1000x800, 1200x600, tấm hình thang, tam giác (phi chuẩn)
- Quản lý theo: Kích thước (dài×rộng×dày) × Màu sắc × Độ dày × Dự án × Vị trí kho
- Conversion: 1 tấm kính = dài × rộng (m²). Nếu hình dạng phức tạp, m² = diện tích thực tế

#### 22.2.1 Mua kính — nhập kho

**Kính tấm chuẩn hình chữ nhật:**
```
Item: GLASS-CLEAR-5mm (Kính trắng 5mm)
  UOM Stock: m²
  Item Variant: kich_thuoc = "1000x800"  (tấm 1m x 0.8m = 0.8 m²/tấm)

Purchase Receipt:
  Qty: 50 tấm = 40 m² (50 × 0.8)
  Rate: 350.000 đ/m²
  UOM: m²
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Giá Kính-01
  mau_sac: Trắng trong
  kich_thuoc: 1000x800
```

**Kính tấm phi chuẩn (hình thang, tam giác, vát góc):**

Kính phi chuẩn không thể dùng Item Variant với kích thước cố định vì mỗi tấm có kích thước riêng. Giải pháp:

| Phương án | Mô tả | Khi nào dùng |
|---|---|---|
| **P1: Item riêng cho mỗi hình dạng** | Tạo Item "Kính cường lực 8mm hình thang" riêng | Khi hình dạng lặp lại nhiều lần (sản xuất hàng loạt) |
| **P2: Item tổng + Serial No + Custom field kích thước** | Tạo 1 Item "Kính cường lực 8mm", mỗi tấm = 1 Serial No. Thêm custom field `hinh_dang`, `kich_thuoc_that` trên mỗi Serial No | Khi mỗi tấm độc nhất (thi công theo đơn đặt hàng) — **khuyến nghị cao nhất** |
| **P3: Dùng Inventory Dimension "Kích thước" dạng text (dynamic)** | Dimension `kich_thuoc` tự do nhập "1200x800-hthang" | Khi cần lọc/báo cáo tồn kho theo kích thước thực tế |

#### 22.2.2 Cắt kính — xuất từ tấm lớn thành tấm nhỏ

ERPNext xử lý bằng **Stock Entry Repack** (giống nhôm):

```
Stock Entry (Purpose: Repack):

  Source: GLASS-FLOAT-5mm (Kính nổi 5mm)
    qty = -2.88 m² (1 tấm 1800x1600)
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Bàn cắt kính

  Target: GLASS-FLOAT-5mm-CUT (Kính nổi 5mm đã cắt)
    qty = +1.44 m² (2 tấm 800x900)
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Giá kính thành phẩm

  Target: (Tận dụng phế liệu)
    qty = +0.72 m² (2 tấm 800x450 dùng được)
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Giá kính phế liệu (nếu còn dùng được)

  Target: GLASS-SCRAP (Mảnh vụn kính vụn)
    qty = +0.72 m² (hao hụt cắt 25%)
    project = DA-NHA-PHAT-2025
    vi_tri_kho = Thùng phế liệu kính
```

**Lưu ý:** Hao hụt cắt kính thường 10-30% tùy độ phức tạp. Cần theo dõi tỷ lệ hao hụt để quản lý hiệu suất.

#### 22.2.3 Quản lý kính phi chuẩn — Serial No + Custom field

Đây là giải pháp cho kính có hình dạng phức tạp (mỗi tấm 1 kích thước riêng):

```
Item: GLASS-TEMPERED-8mm (Kính cường lực 8mm)
  Has Serial No: Yes
  Serial No: G-2025-001 (mỗi tấm = 1 Serial No)
  UOM: m²

Custom field trên Serial No:
  - hinh_dang: hình chữ nhật / hình thang / tam giác / vát góc / oval
  - dai_mm: 1200 (chiều dài mm)
  - rong_mm: 800 (chiều rộng mm, hoặc cạnh đáy)
  - cao_mm: (chiều cao với hình thang/tam giác)
  - dien_tich_m2: 0.96 (diện tích thực tế)
  - ghi_chu_cat: "Vát góc R50, khoét lỗ ống đồng D20"

Khi xuất kho:
  Stock Issue / Delivery Note
  - Item: GLASS-TEMPERED-8mm
  - Serial No: G-2025-001 (quét QR code)
  - project: DA-NHA-PHAT-2025
  - vi_tri_kho: Giá đứng Kính-02
```

#### 22.2.4 Kiểm kê kính

**Tình huống — Thừa/thiếu kính tấm:**
```
Item: GLASS-CLEAR-5mm (Kính trắng 5mm)
Kích thước: 1000x800
Dự án: DA-NHA-PHAT-2025

Vị trí Giá Kính-01:
  Hệ thống: 20 tấm (16 m²) | Thực tế: 18 tấm (14.4 m²) | Delta: -1.6 m²

Xử lý: Stock Reconciliation periodic
→ Override SR → sinh Stock Entry Material Issue: qty=1.6 m²
  mau_sac=Trắng, kich_thuoc=1000x800, project=DA-NHA-PHAT-2025
  vi_tri_kho=Giá Kính-01
```

**Tình huống — Kính phi chuẩn bị vỡ:**
```
Serial No: G-2025-001 (kính cường lực 8mm, 1.2m x 0.8m, 0.96 m²)
  → Bị vỡ trong quá trình thi công

Xử lý: Stock Entry Material Issue
  - Item: GLASS-TEMPERED-8mm
  - Serial No: G-2025-001
  - qty: 0.96 m²
  - project: DA-NHA-PHAT-2025
  - vi_tri_kho: (vị trí xuất)
  - Cost Center: Chi phí hao hụt thi công
```


### 22.3 NHÓM VẬT TƯ PHỤ (KEO, GIOĂNG, SILICONE)

Đặc thù:
- Mua cuộn/thùng → xuất theo mét hoặc chai → tồn kho theo mét/chai
- Mua: đơn vị lớn; Xuất: đơn vị nhỏ; Tồn: đơn vị nhỏ
- Quản lý theo: Dự án × Vị trí kho

#### 22.3.1 Gioăng cao su (Rubber Gasket)

| Thông số | Giá trị |
|---|---|
| Item | GASKET-EPDM-12mm (Gioăng EPDM 12mm) |
| Đơn vị mua | cuộn (1 cuộn = 100m) |
| Đơn vị tồn | m |
| Đơn vị xuất | m |
| Conversion | 1 cuộn = 100 m |

**Nhập mua:**
```
Purchase Receipt:
  Item: GASKET-EPDM-12mm
  Qty: 10 cuộn → 1.000 m (UOM Stock: m)
  Rate: 5.000 đ/m (tương đương 500.000 đ/cuộn)
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Kệ Gioăng-01
  kich_thuoc: 12mm
```

**Xuất thi công:**
```
Stock Entry Material Issue:
  Item: GASKET-EPDM-12mm
  Qty: 35 m
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Kệ Gioăng-01
  Cost Center: Thi công - DA-NHA-PHAT
```

#### 22.3.2 Keo silicone (Silicone Sealant)

| Thông số | Giá trị |
|---|---|
| Item | SILICONE-NEUTRAL-300ml (Keo silicone trung tính 300ml) |
| Đơn vị mua | thùng (1 thùng = 24 chai) |
| Đơn vị tồn | chai |
| Đơn vị xuất | chai |
| Conversion | 1 thùng = 24 chai |

**Nhập mua:**
```
Purchase Receipt:
  Item: SILICONE-NEUTRAL-300ml
  Qty: 5 thùng → 120 chai (UOM Stock: chai)
  Rate: 25.000 đ/chai (tương đương 600.000 đ/thùng)
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Kệ Keo-02
```

**Xuất thi công (lấy từng chai):**
```
Stock Entry Material Issue:
  Item: SILICONE-NEUTRAL-300ml
  Qty: 8 chai
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Kệ Keo-02
```

**Tình huống — Vỡ keo trong kho:**
```
Stock Entry Material Issue:
  Item: SILICONE-NEUTRAL-300ml
  Qty: 2 chai
  Reason: Vỡ keo trong quá trình bốc xếp
  Expense Account: Chi phí hao hụt kho
```


### 22.4 NHÓM PHỤ KIỆN NHÔM KÍNH

Đặc thù:
- Mua hộp/thùng → tồn cái/bộ → xuất cái/bộ
- Quản lý theo: Quy cách, Dự án, Vị trí kho

**Ví dụ — Kẹp kính (Glass Clamp):**
```
Item: CLAMP-GLASS-10mm (Kẹp kính 10mm)
  UOM Stock: cái
  Qty mua: 1 hộp = 50 cái
  Rate: 8.000 đ/cái

Purchase Receipt:
  Qty: 2 hộp = 100 cái
  Rate: 8.000 đ/cái
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Ngăn tủ PK-04
```

**Ví dụ — Tay nắm nhôm (Handle):**
```
Item: HANDLE-ALU-600mm (Tay nắm nhôm 600mm)
  UOM: cái
  Màu sắc: Bạc (Item Variant)
  Kích thước: 600mm (Item Variant)
  project: DA-NHA-PHAT-2025
  vi_tri_kho: Ngăn tủ PK-05

Xuất cho thi công: 12 cái
```

### 22.5 VẬT TƯ THEO DỰ ÁN (KHÔNG PHA TRỘN)

Đặc thù rất quan trọng trong ngành nhôm kính: **cùng 1 loại nhôm nhưng mua cho dự án khác nhau → không được phép trộn lẫn trong kho.**

| Yếu tố | Mô tả |
|---|---|
| Vấn đề | Nhôm đen 40x80 mua cho DA-A giá 80.000, DA-B giá 85.000. Nếu để chung 1 Item, AVCO pool sẽ làm sai giá vốn. |
| Giải pháp gốc | Dùng `project` làm Inventory Dimension (không cần — đã có sẵn) |
| **Giải pháp chuẩn** | **Dùng Warehouse riêng cho mỗi dự án** + trường `project` để track |

#### 22.5.1 Mô hình kho phân tách theo dự án

```
Kho NVL Trung tâm (warehouse cha)
  ├── Kho DA-NHA-PHAT-2025 (warehouse con)
  │   ├── Kệ A01-Nhom (vi_tri_kho)
  │   └── Giá Kính-01 (vi_tri_kho)
  │
  ├── Kho DA-TOA-NHA-BIDV (warehouse con)
  │   ├── Kệ A01-Nhom (vi_tri_kho)
  │   └── Giá Kính-01 (vi_tri_kho)
  │
  └── Kho DA-CHUNG-CU-2026 (warehouse con)
      ├── Kệ A03-Nhom (vi_tri_kho)
      └── Bãi Kính-02 (vi_tri_kho)
```

Khi đó:
- **Valuation pool riêng cho mỗi warehouse/dự án** → giá vốn chính xác
- **Trường `project`** (core) dùng để lọc báo cáo và validate
- **Dimension `vi_tri_kho`** quản lý vị trí vật lý trong từng kho

#### 22.5.2 Validation khi nhập/xuất

```python
def validate_project_warehouse_match(doc, method):
    """Đảm bảo project trên item khớp với warehouse dự án"""
    for item in doc.items:
        if item.get("project"):
            # Warehouse con phải thuộc dự án tương ứng
            warehouse_project = frappe.db.get_value("Warehouse",
                item.s_warehouse or item.t_warehouse, "project")
            if warehouse_project and warehouse_project != item.project:
                frappe.throw(f"Dòng {item.idx}: Warehouse {item.s_warehouse} "
                    f"không thuộc dự án {item.project}")
```

#### 22.5.3 Tình huống chuyển kho giữa 2 dự án

Có thể xảy ra khi: Dự án A thừa, dự án B thiếu, cấp quản lý quyết định điều chuyển.

```
Stock Entry Material Transfer:
  Source: Kho DA-NHA-PHAT/Kệ A01-Nhom
    Item: ALU-BLACK-40x80x1.4
    Qty: -50 kg
    project: DA-NHA-PHAT-2025 (cũ)
    vi_tri_kho: Kệ A01-Nhom

  Target: Kho DA-TOA-NHA-BIDV/Kệ A01-Nhom
    Item: ALU-BLACK-40x80x1.4
    Qty: +50 kg
    project: DA-TOA-NHA-BIDV (mới)
    vi_tri_kho: Kệ A01-Nhom
```

**Hạch toán:** Vì là 2 warehouse khác nhau, core tự động ghi GL Entry cho chuyển kho:
```
Dr Stock In Hand (DA-TOA-NHA-BIDV)    = 50 × rate_pool_cũ
Cr Stock In Hand (DA-NHA-PHAT-2025)   = 50 × rate_pool_cũ
```


---

<a name="23"></a>
## 23. [MỚI v6] MA TRẬN TÌNH HUỐNG NGÀNH NHÔM KÍNH (BỔ SUNG CHO MỤC 3)

### 23.1 Tổng hợp các tình huống mới cho ngành nhôm kính

**Chú thích:** `3 ID` = 3 Inventory Dimension (mau_sac, kich_thuoc, vi_tri_kho). Trường `project` là field core có sẵn, không phải Inventory Dimension.

| # | Nhóm | Tình huống | Dimension | Core tự xử lý? | Phương án |
|---|---|---|---|---|---|
| **NK-N1** | Nhập kho | Mua nhôm thanh (kg), nhập vào kho DA, 1 vị trí | ✅ 3 ID + project | ✅ Core | PR Item có đủ dimension + project |
| **NK-N2** | Nhập kho | Mua nhôm thanh, nhập nhiều vị trí | ✅ 3 ID + project | ✅ Core | PR nhiều dòng |
| **NK-N3** | Nhập kho | Mua kính tấm chuẩn (m²), nhập vào giá kệ | ✅ 3 ID + project | ✅ Core | PR Item + Serial |
| **NK-N4** | Nhập kho | Mua kính phi chuẩn (m²), mỗi tấm 1 kích thước | ✅ 3 ID + project + Serial | ✅ Core | PR + Serial No (hình dạng trong custom field) |
| **NK-N5** | Nhập kho | Mua gioăng cuộn, nhập chuyển đổi → mét | ✅ project, vi_tri, kich_thuoc | ✅ Core | PR + Item Conversion |
| **NK-N6** | Nhập kho | Mua keo thùng, nhập phân rã → chai | ✅ project, vi_tri | ✅ Core | PR + Item Conversion |
| **NK-N7** | Nhập kho | Nhập tồn đầu kỳ cho DA mới (Opening) | ✅ 3 ID + project | ✅ Core | SR Opening Stock |

| **XK-N1** | Xuất kho | Xuất nhôm thanh cho thi công (theo m hoặc kg) | ✅ 3 ID + project | ✅ Core | SE Material Issue |
| **XK-N2** | Xuất kho | Xuất kính tấm cho thi công (theo m²) | ✅ 3 ID + project + Serial | ✅ Core | SE Material Issue |
| **XK-N3** | Xuất kho | Xuất kính phi chuẩn (quét Serial No → tự động biết diện tích) | ✅ 3 ID + project + Serial | ✅ Core | SE Material Issue + Serial |
| **XK-N4** | Xuất kho | Xuất gioăng theo mét (trích từ cuộn) | ✅ 2 ID + project | ✅ Core | SE Material Issue |
| **XK-N5** | Xuất kho | Xuất phụ kiện (cái/bộ) cho thi công | ✅ 2 ID + project | ✅ Core | SE Material Issue |
| **XK-N6** | Xuất kho | Xuất nhôm trả nhà cung cấp (không đạt chất lượng) | ✅ 3 ID + project | ✅ Core | PR Return |

| **CC-N1** | Chuyển kho | Chuyển nhôm giữa 2 vị trí cùng DA | ✅ 3 ID + project | ✅ Core | SE Transfer |
| **CC-N2** | Chuyển kho | Chuyển nhôm giữa 2 DA khác nhau | ✅ 3 ID + project, khác warehouse | ✅ Core | SE Transfer (2 wh) |
| **CC-N3** | Chuyển kho | Chuyển kính từ kho tổng → bãi thi công DA | ✅ 3 ID + project | ✅ Core | SE Transfer |

| **SX-N1** | Sản xuất | Cắt nhôm thanh dài → ngắn (Repack) | ✅ 3 ID + project | ✅ Core | SE Repack |
| **SX-N2** | Sản xuất | Cắt kính tấm lớn → nhỏ (Repack) | ✅ 3 ID + project + Serial | ✅ Core | SE Repack |
| **SX-N3** | Sản xuất | Gia công nhôm (khoan, phay, đột lỗ) | ✅ 3 ID + project | ✅ Core | SE Manufacture |
| **SX-N4** | Sản xuất | Lắp ráp bộ phụ kiện (kẹp + ốc + gioăng) | ✅ project, vi_tri | ✅ Core | SE Manufacture |

| **KK-N1** | Kiểm kê | Kiểm kê nhôm — thừa vị trí A, thiếu vị trí B cùng DA | ✅ 3 ID + project | ⚠️ Override SR | KK4 → SE Transfer |
| **KK-N2** | Kiểm kê | Kiểm kê kính — thiếu tấm, có Serial | ✅ 3 ID + project + Serial | ⚠️ Override SR | KK3 → SE Material Issue |
| **KK-N3** | Kiểm kê | Kiểm kê nhôm — đúng qty, sai giá | ✅ 3 ID + project | ⚠️ Override SR | KK5 → SLE act=0 |
| **KK-N4** | Kiểm kê | Kiểm kê gioăng — sai số mét cuộn (thực tế cuộn 95m, hệ thống 100m) | ✅ project, vi_tri | ⚠️ Override SR | KK3 → SE Issue |

| **ĐG-N1** | Giá trị | Điều chỉnh giá nhôm do sai đơn giá mua | ✅ 3 ID + project | ⚠️ Override SR | ĐG2 → SLE act=0 |
| **ĐG-N2** | Giá trị | Điều chỉnh giá kính do nhập sai rate | ✅ 3 ID + project | ⚠️ Override SR | ĐG2 → SLE act=0 |

| **BC-N1** | Báo cáo | Tồn kho nhôm theo màu sắc × kích thước × dự án | ✅ 3 ID + project | ✅ Core | Stock Balance filter |
| **BC-N2** | Báo cáo | Tồn kho kính theo kích thước (m² + tấm) | ✅ 3 ID + project | ✅ Core | Stock Balance filter |
| **BC-N3** | Báo cáo | Tổng hợp vật tư theo dự án (toàn bộ NVL cho DA) | ✅ project | ✅ Core | Stock Balance filter `project` |
| **BC-N4** | Báo cáo | Giá trị tồn kho theo vị trí (bin-level) | ✅ 3 ID + project | BC4 — cần báo cáo custom | SLE qty × AVCO pool rate |
| **BC-N5** | Báo cáo | Hao hụt cắt nhôm/kính (Scrap rate) | ✅ 3 ID + project | ❌ Cần báo cáo custom | SE Repack + SLE |

| **NV-N1** | NV đặc thù | Nhập hàng sai dự án — cần chuyển | ✅ 3 ID + project | ✅ Core | SE Transfer (CC-N2) |
| **NV-N2** | NV đặc thù | Trả lại NVL thừa từ công trình về kho | ✅ 3 ID + project | ✅ Core | SE Material Transfer |
| **NV-N3** | NV đặc thù | Phế liệu nhôm (đầu mẩu, thanh vụn) nhập kho phế liệu | ✅ project, vi_tri | ✅ Core | SE Material Receipt (riêng Item phế liệu) |
| **NV-N4** | NV đặc thù | Hao hụt kính vỡ trong thi công | ✅ 3 ID + project | ✅ Core | SE Material Issue + Cost Center |

### 23.2 Thống kê bổ sung cho ngành nhôm kính

| Nhóm | Tổng | Core tự xử lý | Cần override/ custom |
|---|---|---|---|
| **Nhập kho** (NK-N1 → N7) | 7 | 7 | 0 |
| **Xuất kho** (XK-N1 → N6) | 6 | 6 | 0 |
| **Chuyển kho** (CC-N1 → N3) | 3 | 3 | 0 |
| **Sản xuất/gia công** (SX-N1 → N4) | 4 | 4 | 0 |
| **Kiểm kê** (KK-N1 → N4) | 4 | 0 | **4** |
| **Điều chỉnh giá** (ĐG-N1 → N2) | 2 | 0 | **2** |
| **Báo cáo** (BC-N1 → N5) | 5 | 3 | **2** (BC4, BC5) |
| **NV đặc thù** (NV-N1 → N4) | 4 | 4 | 0 |
| **TỔNG NGÀNH NHÔM KÍNH** | **35** | **27 (77%)** | **8 (23%)** |

Tỷ lệ này tương đồng với ma trận tổng thể ở Mục 3.5 (77% vs 79%). Điều này xác nhận: **giải pháp Inventory Dimension core + override SR là đủ cho ngành nhôm kính, không cần custom thêm pipeline nào khác.**


---

<a name="24"></a>
## 24. [MỚI v6] PHƯƠNG ÁN KỸ THUẬT CHO DUAL-UOM & KÍCH THƯỚC PHI CHUẨN

### 24.1 Phương án Dual-UOM nâng cao

#### 24.1.1 Kiến trúc custom field cho nhôm (theo dõi cả kg và mét)

Thêm 2 custom field trên **Stock Ledger Entry** và **Stock Entry Detail**:

```python
# custom_fields.py
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def add_dual_uom_fields():
    create_custom_fields({
        "Stock Ledger Entry": [
            {
                "fieldname": "qty_m",
                "label": "Số mét (m)",
                "fieldtype": "Float",
                "precision": 2,
                "insert_after": "actual_qty",
                "description": "Số mét dài đối với nhôm thanh",
                "read_only": 1,
            },
            {
                "fieldname": "weight_kg_per_m",
                "label": "Trọng lượng (kg/m)",
                "fieldtype": "Float",
                "precision": 4,
                "insert_after": "qty_m",
                "description": "Trọng lượng kg/mét của profile này",
                "read_only": 1,
            },
        ],
        "Stock Entry Detail": [
            {
                "fieldname": "qty_m",
                "label": "Số mét (m)",
                "fieldtype": "Float",
                "precision": 2,
                "insert_after": "qty",
                "description": "Số mét dài đối với nhôm thanh (tự tính khi có conversion factor)",
            },
        ],
        "Stock Reconciliation Item": [
            {
                "fieldname": "qty_m",
                "label": "Số mét (m)",
                "fieldtype": "Float",
                "precision": 2,
                "insert_after": "qty",
                "description": "Số mét dài đối với nhôm thanh",
            },
        ],
    })
```

#### 24.1.2 Logic tự động tính mét từ kg

```python
def auto_calc_qty_m(doc, method):
    """Khi người dùng nhập qty (kg), tự tính qty_m từ Item weight_per_m"""
    if doc.doctype == "Stock Entry Detail":
        if doc.qty and not doc.qty_m:
            weight_per_m = frappe.db.get_value("Item", doc.item_code,
                "weight_per_unit")  # hoặc custom field kg_per_m
            if weight_per_m and weight_per_m > 0:
                doc.qty_m = doc.qty / weight_per_m  # kg / (kg/m) = m
```

**Trên Item Variant:** Thêm field `weight_per_m` (kg/m) để lưu trọng lượng riêng của từng profile nhôm.

#### 24.1.3 Báo cáo Dual-UOM

View SQL để báo cáo tồn kho nhôm theo cả kg và mét:

```sql
SELECT
    sle.item_code,
    SUM(sle.actual_qty) AS total_kg,
    SUM(sle.custom_qty_m) AS total_m,
    sle.project,
    sle.mau_sac,
    sle.kich_thuoc,
    sle.vi_tri_kho,
    AVG(sle.valuation_rate) AS avg_rate_kg
FROM `tabStock Ledger Entry` sle
WHERE sle.item_code LIKE 'ALU-%'
  AND sle.docstatus = 1
  AND sle.is_cancelled = 0
GROUP BY sle.item_code, sle.project, sle.mau_sac, sle.kich_thuoc, sle.vi_tri_kho
ORDER BY sle.item_code, sle.project;
```

### 24.2 Phương án Serial No + Custom field cho kính phi chuẩn

#### 24.2.1 Custom field trên Serial No

```python
def add_serial_no_glass_fields():
    create_custom_fields({
        "Serial No": [
            {
                "fieldname": "glass_shape",
                "label": "Hình dạng kính",
                "fieldtype": "Select",
                "options": "\nHình chữ nhật\nHình thang\nTam giác\nHình tròn\nOval\nVát góc\nPhức tạp (custom)",
                "insert_after": "item_code",
            },
            {
                "fieldname": "dai_mm",
                "label": "Dài (mm)",
                "fieldtype": "Float",
                "precision": 0,
                "insert_after": "glass_shape",
            },
            {
                "fieldname": "rong_mm",
                "label": "Rộng (mm)",
                "fieldtype": "Float",
                "precision": 0,
                "insert_after": "dai_mm",
            },
            {
                "fieldname": "dien_tich_m2",
                "label": "Diện tích (m²)",
                "fieldtype": "Float",
                "precision": 4,
                "insert_after": "rong_mm",
            },
            {
                "fieldname": "glass_drawing",
                "label": "Bản vẽ kính",
                "fieldtype": "Attach",
                "insert_after": "dien_tich_m2",
                "description": "Upload bản vẽ CAD/PDF của tấm kính",
            },
            {
                "fieldname": "project",
                "label": "Dự án",
                "fieldtype": "Link",
                "options": "Project",
                "insert_after": "glass_drawing",
            },
        ],
    })
```

#### 24.2.2 Quy trình nhập kính phi chuẩn (P2)

```
Bước 1 — Mua kính tấm lớn:
  Purchase Receipt:
    Item: GLASS-FLOAT-8mm (Kính nổi 8mm)
    Qty: 10 tấm = 18 m² (mỗi tấm 1800x1000 = 1.8 m²)
    Không cần Serial No (tấm thô)

Bước 2 — Cắt/gia công → tạo Serial No cho từng tấm phi chuẩn:
  Stock Entry (Purpose: Repack):
    Source: GLASS-FLOAT-8mm
      qty = -18 m² (10 tấm lớn)

    Target: GLASS-TEMPERED-8mm-CUT (Kính cường lực 8mm đã cắt)
      qty = +14.4 m² (tận dụng 80%)
      Serial No: tự động sinh 10 Serial No

  → Sau khi sinh Serial No, cập nhật từng Serial No:
    - G-2025-001: hình_thang, dai=1200, rong=800, cao=600, dien_tich=0.72
    - G-2025-002: hinh_chu_nhat, dai=1000, rong=700, dien_tich=0.70
    - ...

Bước 3 — Xuất kho cho thi công:
  Stock Entry Issue (hoặc Delivery Note):
    Item: GLASS-TEMPERED-8mm-CUT
    Serial No: G-2025-001, G-2025-002, ... (quét QR code)
    → Tự động tính tổng m² từ dien_tich_m2 của các Serial No
    project = DA-NHA-PHAT-2025
```

### 24.3 Quản lý hao hụt cắt (Scrap/ Waste Tracking)

Khi cắt nhôm hoặc kính, luôn có hao hụt. Cần 1 Item phế liệu riêng để theo dõi:

```sql
-- Báo cáo hao hụt cắt nhôm
SELECT
    sle.item_code,
    sle.project,
    SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) AS qty_used,
    SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END) AS qty_input,
    ROUND(
        (SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) /
         NULLIF(SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END), 0))
        * 100, 2
    ) AS yield_percent,
    100 - ROUND(
        (SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) /
         NULLIF(SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END), 0))
        * 100, 2
    ) AS scrap_percent
FROM `tabStock Ledger Entry` sle
WHERE sle.voucher_type = 'Stock Entry'
  AND sle.voucher_no IN (
      SELECT name FROM `tabStock Entry` WHERE purpose = 'Repack'
  )
  AND sle.project = %(project)s
GROUP BY sle.item_code, sle.project;
```


---

<a name="25"></a>
## 25. [MỚI v6] CẬP NHẬT MỤC LỤC (bổ sung)

Bổ sung các mục mới từ v6 vào Mục lục:

```
21. [MỚI v6] GIẢI PHÁP MỞ RỘNG CHO NGÀNH NHÔM KÍNH XÂY DỰNG — KHO ĐA CHIỀU, ĐA ĐƠN VỊ TÍNH
    21.1 Tổng quan yêu cầu ngành nhôm kính xây dựng
    21.2 Mô hình Inventory Dimension đề xuất
    21.3 Thiết kế Item và khai báo Dimension

22. [MỚI v6] VÍ DỤ CỤ THỂ THEO TỪNG LOẠI VẬT TƯ
    22.1 Nhóm nhôm thanh (Aluminum Profile)
    22.2 Nhóm kính tấm (Glass Sheet)
    22.3 Nhóm vật tư phụ (Keo, Gioăng, Silicone)
    22.4 Nhóm phụ kiện nhôm kính
    22.5 Vật tư theo dự án (không pha trộn)

23. [MỚI v6] MA TRẬN TÌNH HUỐNG NGÀNH NHÔM KÍNH
    23.1 Tổng hợp các tình huống mới (35 tình huống)
    23.2 Thống kê bổ sung

24. [MỚI v6] PHƯƠNG ÁN KỸ THUẬT CHO DUAL-UOM & KÍCH THƯỚC PHI CHUẨN
    24.1 Phương án Dual-UOM nâng cao
    24.2 Phương án Serial No + Custom field cho kính phi chuẩn
    24.3 Quản lý hao hụt cắt (Scrap/Waste Tracking)

25. [MỚI v6] KẾT LUẬN VÀ LỘ TRÌNH KHUYẾN NGHỊ
```

---

<a name="26"></a>
## 26. [MỚI v6] KẾT LUẬN VÀ LỘ TRÌNH KHUYẾN NGHỊ

### 26.1 Đánh giá tổng thể

Sau khi bổ sung giải pháp cho ngành nhôm kính xây dựng với 3 Inventory Dimension + Project (Dự án, Màu sắc, Kích thước, Vị trí kho) và Dual-UOM, ta có:

| Số liệu | Giá trị |
|---|---|
| Tổng số tình huống đã phân tích (gốc + nhôm kính) | 78 (43 gốc + 35 nhôm kính) |
| Tỷ lệ core ERPNext tự xử lý | ~78% (61/78) |
| Tỷ lệ cần override Stock Reconciliation | ~14% (11/78) |
| Tỷ lệ cần custom báo cáo | ~5% (4/78) |
| Tỷ lệ cần custom field | ~3% (2/78) |

### 26.2 Lộ trình khuyến nghị cho ngành nhôm kính

**Phase 0 — Thiết lập nền tảng (1-2 tuần):**
1. Cấu hình 3 Inventory Dimension trên UI (Màu sắc, Kích thước, Vị trí kho) + trường project core
2. Tạo Item Template + Variants cho nhôm, kính, phụ kiện
3. Thiết lập Item Attribute: Màu sắc, Kích thước profile, Độ dày
4. Cấu hình Warehouse theo mô hình DA (Mục 22.5)
5. Thêm custom field `weight_per_m` trên Item cho Dual-UOM

**Phase 1 — Core pipeline (2 tuần):**
1. Test nhập mua (PR): nhôm, kính, gioăng, keo, phụ kiện với đủ 3 ID + project
2. Test xuất kho (SE Issue/DN): từng loại vật tư với dimension
3. Test chuyển kho (SE Transfer): cùng DA, khác DA
4. Test Repack: cắt nhôm, cắt kính
5. Test Manufacture: gia công lắp ráp phụ kiện

**Phase 2 — Override SR + Dual-UOM (1-2 tuần):**
1. Override Stock Reconciliation (kế thừa từ Phương án E — Mục 14)
2. Thêm custom field qty_m trên SLE/SE/SR
3. Code auto-calc qty_m từ weight_per_m
4. Test kiểm kê đầy đủ 4 tình huống (KK-N1 → N4)

**Phase 3 — Serial No kính phi chuẩn (1 tuần):**
1. Thêm custom field trên Serial No cho kính
2. Code sinh Serial No tự động khi Repack kính
3. Quy trình nhập kích thước/shape cho từng Serial No
4. Test xuất kho kính phi chuẩn bằng Serial

**Phase 4 — Báo cáo + UAT (1-2 tuần):**
1. Stock Balance theo (item + project + mau_sac + kich_thuoc + vi_tri_kho)
2. Báo cáo giá trị tồn kho theo vị trí (SLE qty × AVCO pool)
3. Báo cáo hao hụt cắt (Scrap rate)
4. Báo cáo tổng hợp NVL theo dự án
5. UAT với team kho, team thi công, kế toán

### 26.3 Tổng kết

| Yêu cầu ngành nhôm kính | Giải pháp | Mức độ hoàn thiện |
|---|---|---|
| ✅ Nhôm: kg-m, màu sắc, kích thước, DA, vị trí | 3 ID (mau_sac, kich_thuoc, vi_tri_kho) + project + Dual-UOM | Cao |
| ✅ Kính: m², tấm, kích thước phi chuẩn, DA | 3 ID + Serial No + Custom field + project | Cao (cần custom Serial) |
| ✅ Vật tư phụ: cuộn→m, thùng→chai | Item Conversion (UOM2) | Rất cao (core native) |
| ✅ Phụ kiện: cái/bộ, quy cách | 3 ID (kich_thuoc, vi_tri_kho) + project | Rất cao (core native) |
| ✅ Hao hụt cắt (scrap) | SE Repack + Item phế liệu | Cao |
| ✅ Warehouse riêng cho từng DA | Warehouse hierarchy + trường project | Rất cao |
| ✅ Kiểm kê định kỳ có dimension | Phương án E — override SR | Cao (đã thiết kế) |
| ✅ Giá vốn chính xác theo DA | AVCO pool per DA-warehouse | Rất cao |

**Kết luận:** ERPNext với 3 Inventory Dimension core (Màu sắc, Kích thước, Vị trí kho) + trường **Project** có sẵn + Stock Reconciliation override + Dual-UOM + Serial No custom là **giải pháp hoàn chỉnh, đủ mạnh và đúng chuẩn ERP Tier-1** cho ngành nhôm kính xây dựng.

> **Tài liệu được cập nhật lần cuối: 20/07/2026**
>
> **Phiên bản: v7 — bổ sung toàn diện phân tích tồn âm, xuất âm với Inventory Dimension**
>
> **Phiên bản v7 bổ sung:** Phân tích chi tiết 3 cấp độ tồn âm (warehouse, dimension, future SLE), ma trận 9 tình huống tồn âm, ví dụ thực tế code core, giải pháp dim-level âm bằng get_stock_balance(inventory_dimensions_dict), và quy trình migration từ per-warehouse negative policy sang Inventory Dimension.
>
> **Phiên bản trước: v6 — bổ sung toàn diện giải pháp cho ngành nhôm kính xây dựng**


# PHỤ LỤC v7: PHÂN TÍCH CHUYÊN SÂU TỒN ÂM, XUẤT ÂM VỚI INVENTORY DIMENSION

> **Bổ sung cho tài liệu:** ERPNext_Stock_Reconciliation_Inventory_Dimension_Giai_Phap_v5.md
> **Phân tích dựa trên code thật:** Frappe v14.101.1, ERPNext v14.92.14, eupapp

---

## MỤC LỤC (bổ sung Mục 27)

1. [Kiến trúc xử lý tồn âm trong core](#271)
2. [Phân tích stack tồn âm](#272)
3. [Tồn âm Warehouse-level với Dimension](#273)
4. [Tồn âm Dimension-level](#274)
5. [Tồn âm Future SLE](#275)
6. [Chính sách per-warehouse của eupapp](#276)
7. [Ma trận tình huống tồn âm đầy đủ](#277)
8. [Ví dụ thực tế chi tiết](#278)
9. [Giải pháp cho tồn âm có Dimension](#279)
10. [Migration: từ per-warehouse policy sang Dimension](#2710)
11. [Checklist kiểm tra tồn âm với Dimension](#2711)

---

<a name="27.1"></a>
## 27.1 Kiến trúc xử lý tồn âm trong core

### 27.1.1 Luồng xử lý (xác nhận từ code thật stock_ledger.py)

```
make_sl_entries(sl_entries, allow_negative_stock=False)
  |
  +-- make_entry(sle, allow_negative_stock, via_landed_cost_voucher)
  |     +-- SLE_Doc = frappe.get_doc({...})
  |     |     +-- process_sle() gọi self.validate_negative_stock(sle)
  |     |     |   - Check: wh_data.qty_after_transaction + actual_qty < 0
  |     |     |   - warehouse-level (self.wh_data = self.data[sle.warehouse])
  |     |     |   - KHÔNG check dimension-level
  |     |     |
  |     |     +-- get_moving_average_values() hoặc update_queue_values()
  |     |     |   - vẫn chỉ dùng warehouse-level data
  |     |     |
  |     |     +-- update_bin_data(sle)
  |     |         - Bin.actual_qty = sle.qty_after_transaction (warehouse-level)
  |     |
  |     +-- repost_current_voucher(args, allow_negative_stock)
  |           +-- update_qty_in_future_sle(args, allow_negative_stock)
  |                 +-- UPDATE SLE qty_after_transaction = qty + shift
  |                 |   WHERE item_code=X AND warehouse=Y
  |                 |   (KHÔNG filter dimension)
  |                 +-- validate_negative_qty_in_future_sle()
  |
  +-- SLE được insert vào DB
      - qty_after_transaction = tổng warehouse (pool chung)
      - valuation_rate = pool chung
      - vi_tri_kho = giá trị dimension (chỉ để track qty theo dim)
```

### 27.1.2 Điểm mấu chốt — self.wh_data được key bằng warehouse

Trích code thật stock_ledger.py dòng 551-555:

```python
def process_sle(self, sle):
    # previous sle data for this warehouse
    self.wh_data = self.data[sle.warehouse]     # <-- KEY = WAREHOUSE
```

**Hệ quả:** Mọi validate tồn âm, mọi tính toán valuation đều dùng `self.wh_data` là warehouse-level.
Dimension field `vi_tri_kho` chỉ được ghi vào SLE như một field đi kèm, không tham gia vào:
- `validate_negative_stock()` — chỉ check warehouse
- `get_moving_average_values()` — chỉ tính pool warehouse
- `update_queue_values()` — chỉ FIFO queue warehouse
- `update_bin_data()` — chỉ Bin warehouse

Đây là **thiết kế có chủ đích** của core ERPNext, hoàn toàn khớp với chuẩn ERP Tier-1 (SAP Bin chỉ track qty, Plant-level valuation).

### 27.1.3 validate_negative_stock() — code thật

stock_ledger.py dòng 710-728:

```python
def validate_negative_stock(self, sle):
    """validate negative stock for entries current datetime onwards
    will not consider cancelled entries"""
    diff = self.wh_data.qty_after_transaction + flt(sle.actual_qty)
    diff = flt(diff, self.flt_precision)
    diff_threshold = 0.0001
    if self.flt_precision > 4:
        diff_threshold = 10 ** (-1 * self.flt_precision)
    if diff < 0 and abs(diff) > diff_threshold:
        exc = sle.copy().update({"diff": diff})
        self.exceptions.setdefault(sle.warehouse, []).append(exc)
        return False
    else:
        return True
```

**Giải thích:**
- `diff` = tồn kho hiện tại + actual_qty mới, tính trên warehouse
- Nếu âm quá ngưỡng precision → ghi nhận exception (NHƯNG KHÔNG throw ngay — process_sle tiếp tục)
- Exceptions được xử lý sau ở `process_sle_against_current_timestamp()` (dòng 427): nếu có exception → ghi warning log, KHÔNG chặn transaction

### 27.1.4 process_sle_against_current_timestamp() — gọi validate

stock_ledger.py dòng 560-565:

```python
if (sle.serial_no and not self.via_landed_cost_voucher) or not cint(self.allow_negative_stock):
    # validate negative stock for serialized items, fifo valuation
    # or when negative stock is not allowed for moving average
    if not self.validate_negative_stock(sle):
        self.wh_data.qty_after_transaction += flt(sle.actual_qty)
        return
```

**Quan trọng:**
- Nếu `allow_negative_stock = True` → **BỎ QUA** validate_negative_stock() hoàn toàn
- Nếu `allow_negative_stock = False` → gọi validate, nếu âm thì vẫn cộng qty rồi return (tránh sai số)
- **KHÔNG throw exception ở đây** — chỉ ghi nhận exception để warning sau


<a name="27.2"></a>
## 27.2 Phân tích chi tiết stack tồn âm

### 27.2.1 Các điểm validate tồn âm trong core

| # | Điểm validate | File:Line | Scope | Hành vi khi âm |
|---|---|---|---|---|
| 1 | `validate_negative_stock()` | stock_ledger.py:710 | Warehouse-level `(item, warehouse)` | Ghi exception → warning log |
| 2 | `validate_negative_qty_in_future_sle()` | stock_ledger.py:1651 | Warehouse-level future SLE | **Throw** NegativeStockError |
| 3 | `process_sle()` check allow_negative_stock | stock_ledger.py:560 | Gate mở/tắt toàn bộ validate | Nếu allow=True → skip validate |
| 4 | `update_qty_in_future_sle()` | stock_ledger.py:1534 | Warehouse-level (UPDATE SQL) | Chạy validate_negative_qty_in_future_sle |
| 5 | `is_negative_stock_allowed()` | stock_ledger.py:1764 | Kiểm tra cấu hình toàn cục | Trả về True/False |

### 27.2.2 is_negative_stock_allowed() — core check

stock_ledger.py dòng 1764-1767:

```python
def is_negative_stock_allowed(*, item_code: str | None = None) -> bool:
    if cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock", cache=True)):
        return True
    if item_code and cint(frappe.db.get_value("Item", item_code, "allow_negative_stock", cache=True)):
        return True
    return False
```

**Core chỉ check 2 nguồn:**
1. **Stock Settings > allow_negative_stock** (global — toàn bộ hệ thống)
2. **Item > allow_negative_stock** (per-item — từng item riêng)

**Core KHÔNG hỗ trợ per-warehouse allow-negative.** Đây là lý do eupapp phải tự làm negative_policy.py.

### 27.2.3 validate_negative_qty_in_future_sle() — code thật

stock_ledger.py dòng 1651-1693:

```python
def validate_negative_qty_in_future_sle(args, allow_negative_stock=False):
    if allow_negative_stock or is_negative_stock_allowed(item_code=args.item_code):
        return  # Nếu được phép âm → bỏ qua

    if (args.voucher_type == "Stock Reconciliation"
        and args.actual_qty < 0
        and args.get("batch_no")
        and frappe.db.get_value("Stock Reconciliation Item", args.voucher_detail_no, "qty") > 0
    ):
        return  # Ngoại lệ cho Stock Reconciliation với batch

    if not (args.actual_qty < 0 or args.voucher_type == "Stock Reconciliation"):
        return  # Chỉ validate khi actual_qty < 0 hoặc SR

    neg_sle = get_future_sle_with_negative_qty(args)
    if is_negative_with_precision(neg_sle):
        message = _("{0} units of {1} needed in {2} on {3} {4} for {5}...")
        frappe.throw(message, NegativeStockError, title=_("Insufficient Stock"))
```

**Điểm quan trọng:**
- `get_future_sle_with_negative_qty()` query SLE với `item_code` và `warehouse` — **KHÔNG có dimension filter**
- Đây là validate chính chặn backdated entry gây âm trong tương lai
- Nếu `allow_negative_stock = True` (hoặc Item cho phép) → skip hoàn toàn

### 27.2.4 get_future_sle_with_negative_qty() — KHÔNG filter dimension

stock_ledger.py dòng 1712-1745:

```python
def get_future_sle_with_negative_qty(sle):
    SLE = frappe.qb.DocType("Stock Ledger Entry")
    query = (frappe.qb.from_(SLE)
        .select(SLE.qty_after_transaction, SLE.posting_date, SLE.posting_time,
                SLE.voucher_type, SLE.voucher_no)
        .where((SLE.item_code == sle.item_code)
            & (SLE.warehouse == sle.warehouse)
            ...
    ))
```

**Xác nhận: KHÔNG có filter theo dimension field.** Core chỉ validate warehouse-level. Nếu warehouse còn hàng nhưng dimension cụ thể đã hết, core vẫn cho phép xuất từ dimension đó.


<a name="27.3"></a>
## 27.3 Tồn âm Warehouse-level với Inventory Dimension

### 27.3.1 Định nghĩa

**Tồn âm warehouse-level:** `Bin.actual_qty < 0` cho (`item_code`, `warehouse`), bất kể dimension nào.

Đây là dạng tồn âm **nguy hiểm nhất** vì ảnh hưởng trực tiếp đến valuation engine.

### 27.3.2 Tác động đến Moving Average

stock_ledger.py dòng 1033-1070:

```python
def get_moving_average_values(self, sle):
    actual_qty = flt(sle.actual_qty)
    new_stock_qty = flt(self.wh_data.qty_after_transaction) + actual_qty

    if new_stock_qty >= 0:
        # Tính AVCO bình thường
        if actual_qty > 0:
            if flt(self.wh_data.qty_after_transaction) <= 0:
                self.wh_data.valuation_rate = sle.incoming_rate
            else:
                new_stock_value = (self.wh_data.qty_after_transaction * self.wh_data.valuation_rate) + (actual_qty * sle.incoming_rate)
                self.wh_data.valuation_rate = new_stock_value / new_stock_qty
        elif sle.outgoing_rate:
            ...
    else:
        # KHI TỒN ÂM: new_stock_qty < 0
        if flt(self.wh_data.qty_after_transaction) >= 0 and sle.outgoing_rate:
            self.wh_data.valuation_rate = sle.outgoing_rate
        if not self.wh_data.valuation_rate and actual_qty > 0:
            self.wh_data.valuation_rate = sle.incoming_rate
```

**Khi warehouse âm (new_stock_qty < 0):**
- valuation_rate được set = outgoing_rate (giá xuất) — không tính trung bình
- Điều này có thể gọi là "tạm giữ" rate — khi nhập hàng mới vào, nếu `qty_after_transaction <= 0` thì rate sẽ được **reset** = incoming_rate mới (mất toàn bộ lịch sử giá trước đó)

**Ví dụ cụ thể (tồn âm nguy hiểm):**
```
Đầu kỳ: tồn 0 kg, rate = 0
Giao dịch 1: Xuất 100 kg (tồn âm -100)
  → new_stock_qty = -100 < 0
  → valuation_rate = outgoing_rate (giả sử 90.000đ)
Giao dịch 2: Nhập 200 kg, incoming_rate = 95.000đ
  → new_stock_qty = -100 + 200 = 100 ≥ 0
  → qty_after_transaction <= 0 (vì -100) → valuation_rate = incoming_rate = 95.000đ
  → MẤT THÔNG TIN GIÁ CỦA outgoing_rate trước đó
```

**Hậu quả:** valuation_rate bị "reset" sai — giá vốn không còn phản ánh đúng chi phí thực tế.

### 27.3.3 Tác động đến FIFO

stock_ledger.py dòng 1072-1118:

```python
def update_queue_values(self, sle):
    actual_qty = flt(sle.actual_qty)
    self.wh_data.qty_after_transaction = round_off_if_near_zero(self.wh_data.qty_after_transaction + actual_qty)
    stock_queue = FIFOValuation(self.wh_data.stock_queue)
    _prev_qty, prev_stock_value = stock_queue.get_total_stock_and_value()

    if actual_qty > 0:
        stock_queue.add_stock(qty=actual_qty, rate=incoming_rate)
    else:
        def rate_generator():
            allow_zero_valuation_rate = self.check_if_allow_zero_valuation_rate(...)
            if not allow_zero_valuation_rate:
                return self.get_fallback_rate(sle)
            return 0.0
        stock_queue.remove_stock(qty=abs(actual_qty), outgoing_rate=outgoing_rate,
                                 rate_generator=rate_generator)

    _qty, stock_value = stock_queue.get_total_stock_and_value()
    stock_value_difference = stock_value - prev_stock_value
    self.wh_data.stock_queue = stock_queue.state
    self.wh_data.stock_value = round_off_if_near_zero(self.wh_data.stock_value + stock_value_difference)

    if self.wh_data.qty_after_transaction:
        self.wh_data.valuation_rate = self.wh_data.stock_value / self.wh_data.qty_after_transaction
```

**Khi FIFO queue rỗng (tồn âm):**
- `stock_queue.remove_stock()` với queue rỗng → dùng `rate_generator()` để lấy rate fallback
- `rate_generator()` gọi `get_fallback_rate()` — rate từ Item master hoặc last SLE
- `stock_value` có thể sai lệch vì không có queue thực tế để tính
- Khi nhập mới, queue được add_stock bình thường, nhưng stock_value lúc này = rate_fallback * qty_âm + rate_mới * qty_mới — không còn FIFO chính xác

**Kết luận:** Tồn âm warehouse-level làm hỏng cả AVCO lẫn FIFO. Đây là lý do các hệ thống Tier-1 không cho phép tồn âm ở cấp valuation.

### 27.3.4 Dimension có làm tồn tệ hơn không?

**KHÔNG.** Dimension không tham gia valuation, nên tồn âm warehouse-level với dimension KHÔNG khác gì tồn âm warehouse-level không dimension.

- Cùng 1 cơ chế validate_negative_stock
- Cùng 1 cách tính AVCO/FIFO
- Cùng 1 update_bin_data

**Dimension chỉ ảnh hưởng qty_after_transaction trên SLE ở cấp dimension query** (qua get_stock_balance với inventory_dimensions_dict), nhưng **KHÔNG** ảnh hưởng đến warehouse-level qty_after_transaction mà core dùng để validate.


<a name="27.4"></a>
## 27.4 Tồn âm Dimension-level (dim âm nhưng warehouse dương)

### 27.4.1 Định nghĩa

**Tồn âm dimension-level:** qty_after_transaction tại 1 tổ hợp (`item`, `warehouse`, `vi_tri_kho`) < 0, nhưng Bin.actual_qty tại (`item`, `warehouse`) > 0.

Đây là tình huống **phổ biến nhất** trong quản lý kho đa chiều và **AN TOÀN** cho valuation.

### 27.4.2 Nguyên nhân thường gặp

| Nguyên nhân | Ví dụ | Mức độ phổ biến |
|---|---|---|
| Nhập sai dimension | Nhập hàng vào Kệ A nhưng ghi nhầm là Kệ B. Khi xuất Kệ A, tồn dim A âm, dim B dương thừa | Cao |
| Chuyển kho không ghi nhận | Chuyển hàng Kệ A → Kệ B nhưng không tạo Stock Entry Transfer, chỉ xuất từ Kệ A | Cao |
| Kiểm kê không đồng bộ | Kiểm kê ghi nhận thừa Kệ A, thiếu Kệ B, nhưng không sinh chuyển kho bù trừ | Trung bình |
| Backdated entry không repost | Nhập hàng vào Kệ A ngày 1/7 với posting_date=1/6, trước đó đã xuất từ Kệ A ngày 5/6 → qty dim A âm | Trung bình |

### 27.4.3 Core có validate dim-level không?

**KHÔNG.** Core ERPNext KHÔNG validate tồn âm ở cấp dimension. Bằng chứng:

1. `validate_negative_stock()` (dòng 710) chỉ check `self.wh_data` — warehouse-level
2. `validate_negative_qty_in_future_sle()` (dòng 1651) query SLE chỉ `WHERE item_code=X AND warehouse=Y` — không filter dimension
3. `update_qty_in_future_sle()` (dòng 1534) UPDATE qty_after_transaction với `WHERE item_code=X AND warehouse=Y` — không filter dimension
4. `Bin` chỉ có khóa `(item_code, warehouse)` — không có dimension field

### 27.4.4 An toàn của dim-level tồn âm

**Dim-level tồn âm KHÔNG ảnh hưởng valuation vì:**
- `get_moving_average_values()` dùng `self.wh_data` (warehouse-level) — không thay đổi
- `update_queue_values()` dùng `self.wh_data.stock_queue` (queue chung) — không thay đổi
- `stock_value_difference` tính từ warehouse-level stock_value — không thay đổi
- GL Entry vẫn đúng (dựa trên stock_value_difference warehouse-level)

**Nhưng có vấn đề về nghiệp vụ:**
1. **Báo cáo kiểm kho sai** — qty âm tại 1 dimension = không thể đối chiếu với thực tế
2. **Không biết hàng thực sự ở đâu** — ERP ghi dim A âm, nhưng hàng thực tế ở dim B
3. **Không thể xuất âm cho khách hàng** — xuất bán đòi hỏi tồn thực tế > 0
4. **Valuation rate vẫn đúng nhưng audit trail không clear** — xuất từ dim âm vẫn lấy outgoing_rate = pool rate

### 27.4.5 Khi nào dim-level âm thực sự nguy hiểm?

Chỉ nguy hiểm khi **dim-level âm DẪN ĐẾN warehouse-level âm** vì:
- Nếu dim A âm -50 nhưng warehouse còn 200 ở dim B → OK, valuation vẫn đúng
- Nếu dim A âm -200 và warehouse chỉ còn 100 tổng → warehouse-level cũng âm -100 → VALUATION SAI

**Vậy nên:** validate dim-level tồn âm là **optional** — chỉ cần khi bạn muốn báo cáo dimension chính xác. Nó KHÔNG cần thiết cho valuation.

### 27.4.6 Giải pháp cho dim-level tồn âm

Dùng core `get_stock_balance()` với `inventory_dimensions_dict`:

```python
from erpnext.stock.utils import get_stock_balance

# Lấy tồn kho chính xác tại dimension
qty = get_stock_balance(
    item_code="ALU-BLACK-40x80",
    warehouse="Kho NVL",
    posting_date=today(),
    inventory_dimensions_dict={"vi_tri_kho": "Ke A01-Nhom"}
)
# Trả về: qty_after_transaction tại dimension đó
# Nếu < 0 → dim-level tồn âm
```

**Chiến lược xử lý:**
1. **Cho dim-level âm xảy ra** — core tự xử lý, không ảnh hưởng valuation
2. **Báo cáo phát hiện dim-level âm** — query SLE GROUP BY dimension
3. **Xử lý theo batch** — định kỳ (hàng tuần/tháng) kiểm tra và điều chỉnh bằng Stock Entry Transfer
4. **Ngăn chặn tái diễn** — cải tiến quy trình nhập/xuất, training người dùng


<a name="27.5"></a>
## 27.5 Tồn âm Future SLE (backdated + repost với Dimension)

### 27.5.1 Cơ chế repost backdated

Khi một chứng từ được submit với posting_date trong quá khứ:

```
stock_controller.py dòng 894-915:
  repost_future_sle_and_gle()
  -> future_sle_exists(args) — check nếu có SLE trong tương lai
  -> repost_required_for_queue() — check FIFO queue
  -> create_item_wise_repost_entries() hoặc create_repost_item_valuation_entry()
     -> Repost Item Valuation (DocType) được tạo
        -> Khi RIV chạy, nó gọi lại process_sle() cho tất cả SLE từ thời điểm backdated
```

**Repost với Inventory Dimension:**
- `create_item_wise_repost_entries()` query SLE qua `get_items_to_be_repost()`
- Nó group by `(item_code, warehouse)` — KHÔNG group by dimension
- Khi repost chạy, nó đọc lại SLE cũ (có dimension field) và chạy lại process_sle()
- `process_sle()` chiếu vào `self.data[sle.warehouse]` (warehouse-level) — dimension field chỉ là field đi kèm, không ảnh hưởng valuation

**Kết luận:** Repost với dimension hoàn toàn an toàn và tự động — core xử lý đúng.

### 27.5.2 Rủi ro đặc thù với dim-level khi repost

Tuy repost valuation đúng, nhưng có 1 rủi ro với **dim-level qty_after_transaction**:

```
Ví dụ:
- Ngày 1/6: Nhập 100 units vào Dim A
- Ngày 5/6: Xuất 30 units từ Dim A → dim A còn 70
- Ngày 10/6: Xuất 20 units từ Dim B (mặc dù dim B chưa có hàng — dim-level âm -20)
  → warehouse còn 70 (dim A 70 + dim B -20)
  → valuation vẫn đúng (pool = 70 units)

- Ngày 15/6: Nhập hồi tố (backdated) 50 units vào Dim B, posting_date = 1/6
  → Repost chạy: process_sle() cho SLE từ 1/6 đến nay
  → warehouse-level: qty được tính lại chính xác (vì +50)
  → dim-level: SLE cũ giữ nguyên dimension field
  → Sau repost: dim A=70, dim B=30 (vì đã cộng 50 vào dim B)
  → dim-level hết âm!
```

**Core tự sửa dim-level âm do backdated** — vì SLE cũ đã có `actual_qty` đúng dimension, khi repost chỉ tính lại `qty_after_transaction` warehouse-level. Nhưng dim-level qty_after_transaction trên SLE cũ KHÔNG được cập nhật lại (vì update_qty_in_future_sle UPDATE warehouse-level, không filter dimension).

**Hậu quả:** SLE cũ vẫn hiển thị qty_after_transaction cũ (có dim-level âm), dù valuation đã repost đúng.

**Giải pháp:** Khi cần dim-level chính xác, query qua `get_stock_balance()` với `inventory_dimensions_dict` — hàm này đọc SLE gần nhất tại dimension đó và trả về qty_after_transaction CHÍNH XÁC.

### 27.5.3 update_qty_in_future_sle() KHÔNG filter dimension

stock_ledger.py dòng 1534-1568:

```python
def update_qty_in_future_sle(args, allow_negative_stock=False):
    qty_shift = args.actual_qty
    if args.voucher_type == "Stock Reconciliation":
        qty_shift = get_stock_reco_qty_shift(args)

    next_stock_reco_detail = get_next_stock_reco(args)
    if next_stock_reco_detail:
        datetime_limit_condition = get_datetime_limit_condition(detail)

    frappe.db.sql(f"""
        update `tabStock Ledger Entry`
        set qty_after_transaction = qty_after_transaction + {qty_shift}
        where
            item_code = %(item_code)s
            and warehouse = %(warehouse)s
            and voucher_no != %(voucher_no)s
            and is_cancelled = 0
            ...
    """, args)
```

**Xác nhận:** UPDATE KHÔNG filter dimension. Mọi SLE trong tương lai cho (`item_code`, `warehouse`) đều được shift qty — bất kể dimension. Điều này đảm bảo dim-level không bị sai lệch do shift thiếu.


<a name="27.6"></a>
## 27.6 Chính sách per-warehouse negative của eupapp

### 27.6.1 negative_policy.py — thiết kế

eupapp đã custom chính sách tồn âm để hỗ trợ per-warehouse (core chỉ hỗ trợ global + per-item):

```python
# eup_stock/negative_policy.py
def is_negative_allowed(warehouse=None, item_code=None, company=None):
    """Thứ tự ưu tiên (cao → thấp):
    1. Warehouse.custom_allow_negative_stock = 1  → CHO ÂM (kho WIP/Sản xuất)
    2. Company.custom_allow_negative_stock = 1    → CHO ÂM (killswitch per-company)
    3. Stock Settings.allow_negative_stock = 1    → CHO ÂM toàn cục
    4. Mặc định                                     → CHẶN
    """
    # 1. Per-warehouse NGOẠI LỆ
    if warehouse and cint(frappe.db.get_value("Warehouse", warehouse,
            "custom_allow_negative_stock", cache=True)):
        return 1
    # 2. Company killswitch
    if company and cint(frappe.db.get_value("Company", company,
            "custom_allow_negative_stock", cache=True)):
        return 1
    # 3. Global Stock Settings
    if cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock", cache=True)):
        return 1
    return 0
```

### 27.6.2 EupStockLedgerEntry — tích hợp negative_policy

```python
# overrides/stock_ledger_entry.py
class EupStockLedgerEntry(StockLedgerEntry):
    @property
    def allow_negative_stock(self):
        from eupapp.eup_stock.negative_policy import is_negative_allowed
        if cint(getattr(self, "_allow_negative_stock", 0)):
            return 1    # explicit flag (repost/cleanup) → force allow
        return is_negative_allowed(self.warehouse, self.item_code, self.company)

    @allow_negative_stock.setter
    def allow_negative_stock(self, value):
        self._allow_negative_stock = value
```

**Cơ chế:** override `allow_negative_stock` property của StockLedgerEntry — thay vì đọc từ flag đơn giản, nó gọi `is_negative_allowed()` với warehouse cụ thể.

### 27.6.3 Vấn đề hiện tại: dimension-level KHÔNG được check

Cả core `validate_negative_stock()` và eupapp `EupStockLedgerEntry.allow_negative_stock` đều chỉ **warehouse-level**. Khi Inventory Dimension được bật:
- Nếu Kho NVL `custom_allow_negative_stock = 0` (chặn âm)
- Nhưng `get_stock_balance(item, warehouse)` trả về 100 (tổng warehouse dương)
- Xuất 50 từ Dim A (dim A chỉ có 30) → **KHÔNG bị chặn** vì warehouse còn 100 > 50
- Hậu quả: dim A còn -20, dim B còn 100, warehouse còn 80

Đây có thể coi là **tính năng** (cố tình chỉ validate warehouse-level) hoặc **lỗ hổng** (tùy góc nhìn nghiệp vụ).

### 27.6.4 Khuyến nghị cho eupapp với Inventory Dimension

| Mức độ | Validate | Cách làm | Rủi ro |
|---|---|---|---|
| **Tối thiểu** | Warehouse-level (core + negative_policy) | Giữ nguyên như hiện tại | Dim-level âm, báo cáo sai |
| **Trung bình** | Warehouse-level + cảnh báo dim-level âm | Thêm background job query SLE phát hiện dim âm, gửi notification | Không chặn kịp thời |
| **Cao nhất** | Warehouse-level + chặn dim-level âm | Thêm validate trong before_submit của Stock Entry, dùng `get_stock_balance(inventory_dimensions_dict=...)` để check dim-level | Chặn giao dịch hợp lệ (nếu dim âm do backdated chưa repost xong) — cần allow_override flag |

**Khuyến nghị:** Chọn mức **Trung bình** — cho dim-level âm xảy ra (an toàn cho valuation), nhưng có cảnh báo + báo cáo phát hiện để xử lý định kỳ.


<a name="27.7"></a>
## 27.7 Ma trận tình huống tồn âm đầy đủ

### 27.7.1 Ma trận (bổ sung cho Mục 3)

| # | Tình huống | Warehouse-level | Dim-level | Core validate | Ảnh hưởng valuation | Cho phép? | Giải pháp |
|---|---|---|---|---|---|---|---|
| **TA1** | Xuất vượt tồn warehouse (không dim) | Âm | N/A | ✅ Chặn nếu allow_negative_stock=False | 🔴 Hỏng AVCO/FIFO | ❌ Không | Tăng cường kiểm soát nhập/xuất |
| **TA2** | Xuất vượt tồn warehouse (có dim) | Âm | Âm | ✅ Chặn nếu allow_negative_stock=False | 🔴 Hỏng AVCO/FIFO | ❌ Không | Tăng cường kiểm soát nhập/xuất |
| **TA3** | Xuất vượt tồn dim A nhưng warehouse còn hàng ở dim B | Dương | Âm (A) | ❌ Bỏ qua | 🟢 Không ảnh hưởng | ⚠️ Có thể | Cảnh báo bằng báo cáo định kỳ |
| **TA4** | Nhập vào dim A đang âm → dim A hết âm | Dương | Về 0 hoặc dương | ❌ Bỏ qua | 🟢 Không ảnh hưởng | ✅ Được | Không cần xử lý |
| **TA5** | Backdated entry gây âm dim A trong quá khứ | Có thể âm hoặc dương | Có thể âm | ✅ Chặn warehouse-level | 🔴 Nếu warehouse âm | ❌ Nếu wh âm | Dùng allow_negative_stock nếu cố tình |
| **TA6** | Chuyển kho dim A → dim B (cùng warehouse) | Dương | A âm, B dương | ❌ Bỏ qua (warehouse không đổi) | 🟢 Không ảnh hưởng | ✅ Được | Tự sửa sau khi chuyển đúng |
| **TA7** | Kiểm kê — điều chỉnh dim A thiếu, dim B thừa | Dương | Có thể âm tạm thời | ❌ Bỏ qua | 🟢 Không ảnh hưởng | ✅ Được | Phương án E — sinh SE Transfer |
| **TA8** | Kho WIP cho phép âm (manufacture) | Âm | Âm | ✅ Cho phép (per-warehouse policy) | 🟡 Chấp nhận rủi ro cho WIP | ✅ Được | Cho phép vì WIP sẽ được nhập TP bù |
| **TA9** | Kho FG/NVL chặn âm, xuất sai dim | Dương | Âm | ❌ Bỏ qua (warehouse dương) | 🟢 Không ảnh hưởng | ⚠️ Nên cảnh báo | Thêm validate dim-level optional |

### 27.7.2 Thống kê

| Loại | Số tình huống | Core tự xử lý đúng | Cần custom |
|---|---|---|---|
| **An toàn (không ảnh hưởng valuation)** | 6 (TA3,4,6,7,8,9) | 4 | 2 (cảnh báo dim-level âm) |
| **Nguy hiểm (ảnh hưởng valuation)** | 2 (TA1,2) | 2 | 0 |
| **Cần chú ý đặc biệt** | 1 (TA5) | 1 | 0 |


<a name="27.8"></a>
## 27.8 Ví dụ thực tế chi tiết cho từng loại âm

### 27.8.1 Ví dụ TA1 — Xuất vượt tồn warehouse (không dimension)

**Item:** ALU-BLACK-40x80, **Kho:** Kho NVL
**Tồn hiện tại:** 100 kg
**GV:** 85.000 đồng/kg

**Giao dịch:**
```
Stock Entry Material Issue: 150 kg (vượt 50 kg)
  → actual_qty = -150
  → warehouse qty_after_transaction = 100 - 150 = -50
  → validate_negative_stock(): diff = -50 → exception ghi nhận
  → process_sle(): qty_after_transaction = -50
  → get_moving_average_values(): new_stock_qty = -50 < 0
    → valuation_rate = outgoing_rate (giả sử = 85.000)
  → Bin.actual_qty = -50
  → GL Entry: Dr COGS 12.750.000 (150 * 85.000)
               Cr Stock In Hand -12.750.000? (sai)
```

**Hậu quả:** 
- `stock_value` hiện tại = -50 * 85.000 = **-4.250.000** (âm!)
- `Bin.stock_value` âm
- Khi nhập 200 kg mới giá 90.000 → `valuation_rate` sẽ bị reset = 90.000 (mất lịch sử giá 85.000)
- Báo cáo tài chính sai

**Xử lý (khi đã xảy ra):**
1. Nhập bù hàng ngay lập tức để đưa tồn về ≥ 0
2. Kiểm tra GL Entry — có thể cần điều chỉnh thủ công
3. Điều tra nguyên nhân xuất vượt — cải tiến quy trình

### 27.8.2 Ví dụ TA3 — Xuất vượt tồn dim A, warehouse còn hàng (phổ biến nhất)

**Item:** ALU-BLACK-40x80, **Kho:** Kho NVL
**Tồn warehouse:** 200 kg (Dim A = 80 kg, Dim B = 120 kg)
**GV:** 85.000 đồng/kg

**Giao dịch:**
```
Stock Entry Material Issue: 100 kg từ Dim A
  → actual_qty = -100, vi_tri_kho = "Dim A"
  → warehouse qty_after_transaction = 200 - 100 = 100 (vẫn dương)
  → validate_negative_stock(): diff = 100 → KHÔNG có exception
  → get_moving_average_values(): new_stock_qty = 100 ≥ 0 → AVCO tính bình thường
  → Bin.actual_qty = 100 (đúng)
  → GL Entry: Dr COGS 8.500.000 = 100 * 85.000 (đúng)
               Cr Stock In Hand 8.500.000 (đúng)

  → SLE: vi_tri_kho = "Dim A", qty_after_transaction = 80 - 100 = -20 (dim-level âm!)
```

**Phân tích:**
- ✅ valuation vẫn chính xác (AVCO pool 85.000)
- ✅ Bin.actual_qty đúng (tổng warehouse còn 100)
- ✅ GL Entry đúng
- ❌ Dim A ghi -20 — sai lệch so với thực tế (hàng ở Dim A đã hết)

**Hậu quả nghiệp vụ:**
- Thủ kho kiểm Dim A: "Hệ thống báo -20, nhưng thực tế 0"
- Mất niềm tin vào số liệu kho
- Có thể dẫn đến xuất tiếp từ Dim A khi đã hết hàng thật

**Giải pháp tận dụng core — không cần validate dim-level:**
Dùng `get_stock_balance()` với `inventory_dimensions_dict` để query dim-level chính xác:

```python
from erpnext.stock.utils import get_stock_balance

# Query tồn kho chính xác tại Dim A (KHÔNG dùng Bin)
qty_dim_a = get_stock_balance(
    item_code="ALU-BLACK-40x80",
    warehouse="Kho NVL",
    inventory_dimensions_dict={"vi_tri_kho": "Dim A"}
)
# Trả về: -20 (dim-level âm)
```

Tuy nhiên, core không gọi get_stock_balance với dimension ở validate time — nó chỉ dùng `self.wh_data`. Nếu bạn muốn validate dim-level, phải override StockEntry.validate():

```python
def validate_dimension_negative_stock(self):
    """Kiểm tra dim-level tồn kho trước khi xuất"""
    for item in self.items:
        if item.s_warehouse and item.get("vi_tri_kho"):
            if flt(item.qty) <= 0:
                continue
            qty_at_dim = get_stock_balance(
                item.item_code, item.s_warehouse,
                inventory_dimensions_dict={"vi_tri_kho": item.vi_tri_kho}
            )
            if flt(qty_at_dim) <= 0:
                frappe.msgprint(
                    _("Cảnh báo: {0} tại {1} / {2} chỉ còn {3}, "
                      "bạn đang xuất {4}").format(
                        item.item_code, item.s_warehouse,
                        item.vi_tri_kho, qty_at_dim, item.qty
                    ),
                    title=_("Cảnh báo tồn kho theo vị trí"),
                    indicator="orange"
                )
```

### 27.8.3 Ví dụ TA5 — Backdated entry gây âm

**Item:** ALU-BLACK-40x80, **Kho:** Kho NVL
**Sequence thực tế (theo thời gian):**

```
Ngày 01/06: Nhập 100 kg vào Dim A, rate 85.000
Ngày 05/06: Xuất 30 kg từ Dim A → dim A còn 70, warehouse còn 70
Ngày 10/06: Nhập hồi tố (backdated ghi ngày 02/06) 50 kg vào Dim A, rate 90.000
```

**Luồng repost:**
```
1. Khi submit backdated (02/06):
   → process_sle() cho SLE mới (50 kg)
   → future_sle_exists() = True (có SLE ngày 05/06)
   → create_repost_item_valuation_entry() → queue RIV

2. RIV chạy: đọc lại SLE từ 02/06 → nay:
   SLE 02/06: actual_qty=50 → warehouse qty=50+...=150
   SLE 05/06: actual_qty=-30 → warehouse qty=120
   → AVCO tính lại: (100*85.000 + 50*90.000)/150 = 86.667
   → warehouse-level đúng!
```

**Tuy nhiên, dim-level có thể gặp vấn đề nếu giao dịch giữa 02/06 và 05/06 cũng dùng Dim A:**
```
- Nếu ngày 03/06 có giao dịch xuất 40 kg từ Dim A (không có hàng vì chưa nhập hồi tố)
  → SLE dim A: actual_qty=-40, qty_after_transaction_dim = -40
  → Sau repost: SLE 02/06 +50, SLE 03/06 -40 → dim A còn 10
  → qty_after_transaction của SLE 03/06 vẫn hiển thị -40 (vì update_qty_in_future_sle
     chỉ UPDATE warehouse-level, không filter dimension)
  → get_stock_balance(inventory_dimensions_dict={"vi_tri_kho": "Dim A"}) = 10 (ĐÚNG)
  → Nhưng SLE 03/06.qty_after_transaction = -40 (hiển thị lịch sử CŨ)
```

**Giải pháp tận dụng core:**
- Khi query dim-level, **LUÔN dùng `get_stock_balance()` với `inventory_dimensions_dict`**
- KHÔNG đọc trực tiếp `qty_after_transaction` từ SLE cũ nếu có backdated
- `get_stock_balance()` tìm SLE **gần nhất** tại dimension đó và trả về qty_after_transaction chính xác nhất


<a name="27.9"></a>
## 27.9 Giải pháp cho tồn âm có Inventory Dimension

### 27.9.1 Nguyên tắc

1. **Ưu tiên xử lý warehouse-level âm** — vì đây là vấn đề valuation thực sự
2. **Cho dim-level âm xảy ra tự nhiên** — an toàn, không ảnh hưởng valuation
3. **Phát hiện và xử lý dim-level âm định kỳ** — qua báo cáo, không qua transaction-time validate
4. **Tận dụng get_stock_balance(inventory_dimensions_dict)** cho mọi query dim-level

### 27.9.2 Phát hiện dim-level âm bằng báo cáo định kỳ

```sql
-- Báo cáo tồn kho theo dimension, phát hiện dim âm
SELECT
    sle.item_code,
    sle.warehouse,
    sle.vi_tri_kho,
    SUM(sle.actual_qty) AS current_qty
FROM `tabStock Ledger Entry` sle
WHERE
    sle.docstatus = 1
    AND sle.is_cancelled = 0
    AND sle.vi_tri_kho IS NOT NULL
GROUP BY
    sle.item_code,
    sle.warehouse,
    sle.vi_tri_kho
HAVING SUM(sle.actual_qty) < 0
ORDER BY current_qty ASC;
```

### 27.9.3 Xử lý dim-level âm bằng Stock Entry Transfer

Khi phát hiện dim A âm, dim B dương (cùng item, warehouse):

```python
def fix_negative_dimension(item, warehouse, dim_negative, dim_positive, qty):
    """Tạo Stock Entry Transfer để điều chỉnh dim âm"""
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company = frappe.get_cached_value("Warehouse", warehouse, "company")

    se.append("items", {
        "item_code": item,
        "s_warehouse": warehouse,
        "t_warehouse": warehouse,
        "qty": qty,
        "vi_tri_kho": dim_positive,    # source dimension
        "to_vi_tri_kho": dim_negative,  # target dimension
        "basic_rate": 0,  # không ảnh hưởng valuation
    })
    se.insert()
    se.submit()
```

**Core tạo 2 SLE:**
- SLE 1: `vi_tri_kho=dim_positive, actual_qty=-qty`
- SLE 2: `vi_tri_kho=dim_negative, actual_qty=+qty`
- `Bin.actual_qty`: không đổi (tổng warehouse giống nhau)
- GL Entry: không có (cùng warehouse)
- Valuation: không đổi

### 27.9.4 Chặn xuất khi warehouse-level âm — dùng core native

Chặn âm warehouse-level bằng cách set per-warehouse policy:

| Warehouse | custom_allow_negative_stock | Lý do |
|---|---|---|
| Kho NVL | 0 (CHẶN) | Hàng tồn giá trị cao, không cho âm |
| Kho FG | 0 (CHẶN) | Hàng thành phẩm, ảnh hưởng valuation |
| Kho WIP | 1 (CHO) | Tạm thời âm trước khi nhập TP |
| Kho Phế liệu | 1 (CHO) | Giá trị thấp, chấp nhận rủi ro |
| Kho Hàng gửi | 1 (CHO) | Không ảnh hưởng GL |

### 27.9.5 Fix tồn âm warehouse-level — script batch

```python
def fix_negative_warehouse(company=None, dry_run=True):
    """Phát hiện và đề xuất fix warehouse-level âm"""
    conditions = ""
    if company:
        conditions += f" AND wh.company = '{company}'"

    negative_items = frappe.db.sql(f"""
        SELECT bin.item_code, bin.warehouse, bin.actual_qty, bin.stock_value
        FROM `tabBin` bin
        JOIN `tabWarehouse` wh ON wh.name = bin.warehouse
        WHERE bin.actual_qty < 0
        AND IFNULL(wh.custom_allow_negative_stock, 0) = 0
        {conditions}
        ORDER BY bin.actual_qty ASC
    """, as_dict=1)

    if dry_run:
        for row in negative_items:
            print(f"- {row.item_code} @ {row.warehouse}: {row.actual_qty}")
        return negative_items

    for row in negative_items:
        # Tạo Stock Entry Receipt để đưa tồn về 0
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Receipt"
        se.company = frappe.get_cached_value("Warehouse", row.warehouse, "company")
        se.append("items", {
            "item_code": row.item_code,
            "t_warehouse": row.warehouse,
            "qty": abs(row.actual_qty),
            "basic_rate": 0,  # rate 0 để không ảnh hưởng AVCO
        })
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()
        frappe.db.commit()
```


<a name="27.10"></a>
## 27.10 Migration: từ per-warehouse policy cũ sang Inventory Dimension

### 27.10.1 Step 1 — Xác nhận cấu hình hiện tại

```python
# Kiểm tra các warehouse đang cho phép âm
warehouses = frappe.db.sql("""
    SELECT name, custom_allow_negative_stock, company
    FROM `tabWarehouse`
    WHERE custom_allow_negative_stock = 1
""", as_dict=1)

for wh in warehouses:
    print(f"{wh.name}: allow_negative = {wh.custom_allow_negative_stock}")
```

### 27.10.2 Step 2 — Thêm validate_dimension_negative_stock (optional)

Nếu muốn thêm cảnh báo dim-level âm, override Stock Entry:

```python
# overrides/stock_entry.py (bổ sung)
from erpnext.stock.utils import get_stock_balance

def validate_dimension_stock(self):
    """Cảnh báo nếu xuất vượt tồn dimension (chỉ warning, không chặn)"""
    from eupapp.eup_stock.negative_policy import is_negative_allowed

    for item in self.items:
        if item.s_warehouse and item.get("vi_tri_kho") and flt(item.qty) > 0:
            # Chỉ validate dimension-level nếu warehouse chặn âm
            if is_negative_allowed(warehouse=item.s_warehouse):
                continue

            qty_dim = get_stock_balance(
                item.item_code, item.s_warehouse,
                inventory_dimensions_dict={"vi_tri_kho": item.vi_tri_kho}
            )

            if flt(qty_dim) <= 0:
                frappe.msgprint(
                    _("Cảnh báo: {0} tại vị trí {1} trong kho {2} "
                      "đã hết (tồn = {3}). Bạn đang xuất {4}.").format(
                        frappe.bold(item.item_code),
                        frappe.bold(item.vi_tri_kho),
                        frappe.bold(item.s_warehouse),
                        qty_dim, item.qty
                    ),
                    title=_("Cảnh báo tồn kho theo vị trí"),
                    indicator="orange",
                )
```

**Giải thích:**
- Chỉ warning, không chặn — vì dim-level âm an toàn cho valuation
- Chỉ chạy khi warehouse chặn âm — nếu WIP cho âm thì bỏ qua
- Dùng `get_stock_balance(inventory_dimensions_dict=...)` — core native, đã tối ưu

### 27.10.3 Step 3 — Bổ sung báo cáo phát hiện dim-level âm

```sql
-- Stock Balance by Dimension Report
-- Phát hiện dim-level tồn âm
CREATE OR REPLACE VIEW `view_stock_balance_dimension` AS
SELECT
    sle.item_code,
    sle.warehouse,
    sle.vi_tri_kho,
    sle.mau_sac,
    sle.kich_thuoc,
    sle.project,
    SUM(sle.actual_qty) AS actual_qty,
    MAX(sle.valuation_rate) AS valuation_rate,
    SUM(sle.actual_qty) * MAX(sle.valuation_rate) AS stock_value
FROM `tabStock Ledger Entry` sle
WHERE
    sle.docstatus = 1
    AND sle.is_cancelled = 0
GROUP BY
    sle.item_code,
    sle.warehouse,
    sle.vi_tri_kho,
    sle.mau_sac,
    sle.kich_thuoc,
    sle.project
HAVING SUM(sle.actual_qty) > 0.001 OR SUM(sle.actual_qty) < -0.001
ORDER BY
    sle.item_code,
    sle.warehouse,
    sle.vi_tri_kho;
```


<a name="27.11"></a>
## 27.11 Checklist kiểm tra tồn âm với Dimension

### 27.11.1 Checklist cho team kỹ thuật

- [ ] Xác nhận `negative_policy.py` đang dùng đúng thứ tự ưu tiên (warehouse > company > global)
- [ ] Xác nhận `EupStockLedgerEntry.allow_negative_stock` override đúng property (không phải method)
- [ ] Kiểm tra: `get_stock_balance()` với `inventory_dimensions_dict` trả về dim-level qty chính xác
- [ ] Kiểm tra: sau khi backdated, `get_stock_balance(inventory_dimensions_dict)` trả về đúng (không dùng qty_after_transaction của SLE cũ)
- [ ] Xác nhận: các kho WIP/Sản xuất có `custom_allow_negative_stock = 1` — các kho khác = 0
- [ ] Nếu thêm validate dim-level: dùng `frappe.msgprint` (warning) thay vì `frappe.throw` (chặn)

### 27.11.2 Checklist cho team kho

- [ ] Biết rõ kho nào được phép âm (WIP, Phế liệu) và kho nào không (NVL, FG)
- [ ] Khi kiểm kho phát hiện dim-level âm → báo cáo để điều chỉnh bằng Stock Entry Transfer
- [ ] KHÔNG cố tạo Stock Entry điều chỉnh khi chưa xác nhận dim-level âm là do sai sót hay do quy trình
- [ ] Khi xuất kho, ưu tiên chọn dimension có tồn dương (tránh dim-level âm)

### 27.11.3 Test cases

```
Test case 1: TA1 — Xuất vượt tồn warehouse (không dim)
  Expected: Chặn nếu warehouse chặn âm
  Expected: Cho phép nếu warehouse cho âm

Test case 2: TA3 — Xuất vượt tồn dim A, warehouse còn hàng
  Expected: Cho phép (không chặn)
  Expected: Có warning (nếu đã thêm validate_dimension_stock)
  Expected: GL Entry đúng

Test case 3: TA5 — Backdated entry gây dim âm
  Expected: get_stock_balance(dimension) trả về đúng sau repost
  Expected: SLE cũ vẫn hiển thị qty_after_transaction cũ

Test case 4: TA8 — Kho WIP cho phép âm
  Expected: Xuất vượt warehouse được phép
  Expected: Nhập thành phẩm bù lại → valuation về đúng
```

### 27.11.4 Tổng kết

**Tồn âm với Inventory Dimension KHÔNG phải vấn đề kỹ thuật — nó là vấn đề quy trình.**

| Khía cạnh | Đánh giá |
|---|---|
| **Ảnh hưởng đến valuation** | ✅ Chỉ warehouse-level mới ảnh hưởng. Dim-level an toàn |
| **Core đã xử lý đúng?** | ✅ Core validate warehouse-level, không cần sửa |
| **Negative policy hiện tại** | ✅ Per-warehouse đã hoạt động, dùng được với dim |
| **Cần validate dim-level?** | ⚠️ Optional — chỉ warning, không chặn |
| **Cần fix dim-level âm?** | ✅ Định kỳ qua báo cáo + Stock Entry Transfer |
| **Rủi ro nâng cấp** | 🟢 Thấp — không sửa core, chỉ override SLE property |

---

> **Bổ sung lần cuối: 20/07/2026**
>
> **Phiên bản: v7 — bổ sung toàn diện phân tích tồn âm, xuất âm với Inventory Dimension**
>
> **Phân tích dựa trên code thật: stock_ledger.py, stock_controller.py, stock/utils.py, negative_policy.py, EupStockLedgerEntry**

