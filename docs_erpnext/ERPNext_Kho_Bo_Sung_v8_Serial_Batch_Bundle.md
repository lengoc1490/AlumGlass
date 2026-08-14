# [BỔ SUNG v8] SERIAL AND BATCH BUNDLE — CẬP NHẬT CHO AlumGlass (Frappe/ERPNext v16)

> Phần này bổ sung vào cuối tài liệu gốc (sau Mục 27 — Tồn âm), đánh số tiếp
> theo là **Mục 28**. Viết riêng theo yêu cầu: hiện tại AlumGlass **chưa tận
> dụng Serial and Batch Bundle (SABB)**.
>
> **Lưu ý về phương pháp:** tài liệu gốc của bạn dựa trên việc đọc trực tiếp
> code thật của Frappe/ERPNext **v14.92.14** (`myfrappe`/`eupapp`). Phần bổ
> sung này viết cho **kiến trúc SABB** — cơ chế đã thay đổi đáng kể từ v14
> sang v15/v16 (AlumGlass build trên `version-16` theo README của bạn). Tôi
> mô tả đúng kiến trúc và API theo tài liệu/hành vi chính thức của Frappe
> v15+, nhưng **không có quyền đọc trực tiếp source code v16 thật của bạn**
> như cách tài liệu gốc đã làm — bạn cần verify lại các tên method/field cụ
> thể trên đúng bench v16 đang chạy trước khi triển khai, đúng tinh thần
> "code thật" mà tài liệu gốc đã theo suốt.

---

<a name="28"></a>
## 28. TRƯỚC TIÊN — SỬA 1 MÂU THUẪN TRONG TÀI LIỆU GỐC (Mục 21.3.2)

Mục 21.3.2 của tài liệu gốc khuyến nghị **"Item Variant (khuyến nghị cao
nhất)"** cho nhôm và kính, với attribute Màu sắc + Kích thước cố định trên
từng Variant.

Điều này **mâu thuẫn trực tiếp** với quyết định kiến trúc bạn vừa chốt cho
AlumGlass: *"Item Variant sẽ không thể dùng được vì nó sẽ bùng nổ biến thể...
màu theo công trình chứ không cố định."* Đây là kết luận đúng, và nó đúng vì
đúng lý do kỹ thuật: `Item Attribute Value` — nền tảng của Item Variant —
bắt buộc phải là **tập giá trị hữu hạn, khai báo trước** trong Item
Attribute. Màu sơn tĩnh điện theo mã RAL riêng của từng công trình là
**open-ended set**, không enumerate được vào Item Attribute mà không phải
tạo Attribute Value mới liên tục (mỗi công trình lại thêm N giá trị mới vào
danh mục dùng chung toàn hệ thống — về lâu dài đây chính là "bùng nổ biến
thể" bạn đã chỉ ra, chỉ là bùng nổ ở Attribute Value thay vì ở Item).

**Khuyến nghị: đánh dấu Mục 21.3.2 là DEPRECATED cho AlumGlass**, thay bằng
mô hình đã áp dụng: 1 Item chung theo hãng/hệ profile (VD: `NHOM-XINGFA-55`)
+ **Batch** (màu, xuất xứ, lô nhập) + **Inventory Dimension** (vị trí kho) +
**Project** (trường core). Mục 21.3.1 (khai báo Inventory Dimension) và Mục
22.2.3 (Serial No cho kính phi chuẩn) của tài liệu gốc **vẫn đúng và không
cần sửa** — chỉ riêng 21.3.2 (Item Variant) là điểm cần loại bỏ khỏi lộ
trình khuyến nghị.

---

## 29. SERIAL AND BATCH BUNDLE — KIẾN TRÚC THAY ĐỔI SO VỚI v14

### 29.1 Vấn đề cốt lõi: điểm nối giữa Document Row và Stock Ledger đã đổi

Ở v14 (bản tài liệu gốc phân tích), Stock Entry Detail / Purchase Receipt
Item / Delivery Note Item có field `batch_no` và `serial_no` **trực tiếp
trên chính dòng đó**. `get_sl_entries()` đọc thẳng 2 field này để ghi vào
Stock Ledger Entry.

Từ Frappe v15 trở đi (áp dụng cho `version-16` bạn đang dùng), với mọi Item
có `has_batch_no=1` hoặc `has_serial_no=1`, dòng chứng từ **không còn ghi
trực tiếp** `batch_no`/`serial_no` nữa. Thay vào đó:

```
Document Row (Stock Entry Detail / PR Item / DN Item / SR Item)
        │
        │ field: serial_and_batch_bundle  (Link → Serial and Batch Bundle)
        ▼
┌─────────────────────────────────────────────┐
│  Serial and Batch Bundle (doctype mới)       │
│  - item_code, warehouse                      │
│  - type_of_transaction: Inward / Outward     │
│  - voucher_type, voucher_no (liên kết ngược) │
│  - avg_rate (tổng hợp)                       │
│                                               │
│  Child table: Serial and Batch Entry         │
│  ┌─────────────────────────────────────┐     │
│  │ serial_no | batch_no | qty | rate   │     │
│  │ G-2025-001 |  —      |  1  | 350000 │     │
│  │  —         | BATCH-01|  50 | 113000 │     │
│  └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
        │
        ▼
   Stock Ledger Entry (SLE) — vẫn có cột serial_no/batch_no
   như trước, nhưng được ĐIỀN TỪ Bundle tại lúc submit,
   không phải đọc trực tiếp từ Document Row nữa
```

**Điểm quan trọng cho phân tích Inventory Dimension của bạn (Mục 14-16 tài
liệu gốc):** logic valuation (Moving Average/FIFO trên warehouse pool), Bin
update, và cách Inventory Dimension gắn vào SLE **về bản chất không đổi** —
Inventory Dimension vẫn là field độc lập, đi kèm trên SLE như trước, không
phụ thuộc vào việc batch/serial đi qua Bundle hay không. Cái đổi là **cách
document row cung cấp batch_no/serial_no cho engine** — và đây chính là chỗ
mọi override code custom (`eupapp`, và bất kỳ code AlumGlass nào tự tạo
Stock Entry qua `frappe.get_doc()`) phải cập nhật, nếu không sẽ lỗi validate
ngay khi submit.

### 29.2 Vì sao đây là gap thực sự nguy hiểm cho AlumGlass, không chỉ lý thuyết

`AL Manufacturing` module của bạn có `Cutting Plan (Alu+Glass)` và
`Production Order Bridge` — đây gần như chắc chắn là nơi code **tự động
sinh Stock Entry (Repack)** để chuyển "thanh nhôm 6m" → "các đoạn cắt +
offcut", hoặc "tấm kính lớn" → "các tấm cắt nhỏ" (đúng như Mục 22.1.5 và
22.2.2 tài liệu gốc mô tả bằng Stock Entry Repack).

Nếu code hiện tại (hoặc code bạn định viết) tạo Stock Entry kiểu:

```python
# ❌ CÁCH CŨ (v14) — sẽ lỗi validate trên v16 nếu Item có has_serial_no=1
se = frappe.get_doc({
    "doctype": "Stock Entry",
    "stock_entry_type": "Repack",
    "items": [
        {"item_code": "NHOM-XINGFA-55", "s_warehouse": "Kho NVL",
         "qty": 6, "batch_no": "BATCH-2026-001"},   # ← trực tiếp gán batch_no
        {"item_code": "NHOM-XINGFA-55", "t_warehouse": "Kho TP",
         "qty": 4, "batch_no": "BATCH-2026-001"},
        {"item_code": "NHOM-XINGFA-55-OFFCUT", "t_warehouse": "Kho Phế",
         "qty": 2, "serial_no": "OFFCUT-20260811-001"},  # ← trực tiếp gán serial_no
    ],
})
se.insert()
se.submit()
```

...trên v16, dòng nào thuộc Item có `has_batch_no`/`has_serial_no=1` sẽ cần
`serial_and_batch_bundle` thay vì gán trực tiếp field — nếu code cũ đang
dùng pattern trên, submit sẽ throw validation error ngay tại production
(không phải lỗi âm thầm — đây là điểm tốt, nhưng vẫn là điểm cần sửa trước
khi go-live cho tính năng Cutting Plan tự động).

### 29.3 Cách tạo Bundle đúng — pattern chuẩn cho AlumGlass

```python
def make_serial_and_batch_bundle(item_code, warehouse, entries,
                                   type_of_transaction, voucher_type,
                                   voucher_no=None, voucher_detail_no=None):
    """
    entries: list[dict] — mỗi dict là 1 dòng Serial and Batch Entry.
      - Cho item chỉ có Batch:  {"batch_no": "BATCH-2026-001", "qty": 50}
      - Cho item chỉ có Serial: {"serial_no": "G-2025-001", "qty": 1}
      - type_of_transaction: "Inward" (nhập) hoặc "Outward" (xuất)
    """
    bundle = frappe.get_doc({
        "doctype": "Serial and Batch Bundle",
        "item_code": item_code,
        "warehouse": warehouse,
        "type_of_transaction": type_of_transaction,
        "voucher_type": voucher_type,
        "voucher_no": voucher_no,          # có thể để trống, gán sau khi biết SE name
        "voucher_detail_no": voucher_detail_no,
        "entries": entries,
    })
    bundle.insert()
    return bundle.name


def make_cutting_repack_entry(source_batch_no, cut_pieces, offcut_qty,
                               source_item, target_item, offcut_item,
                               warehouse, project):
    """
    Ví dụ: cắt 1 lô nhôm (batch) thành N thanh ngắn + offcut.
    Đây là pattern nên dùng trong AL Cutting Plan Alu thay cho gán trực tiếp.
    """
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Repack"
    se.al_project = project  # custom field hiện có

    # Dòng nguồn — xuất từ batch gốc
    row_source = se.append("items", {
        "item_code": source_item,
        "s_warehouse": warehouse,
        "qty": cut_pieces["total_length_m"],
    })

    # Dòng thành phẩm — nhập thanh đã cắt, VẪN thuộc batch gốc (giữ trace màu/lô)
    row_target = se.append("items", {
        "item_code": target_item,
        "t_warehouse": warehouse,
        "qty": cut_pieces["usable_length_m"],
    })

    # Dòng offcut — mỗi đoạn thừa là 1 Serial No riêng (để trace theo
    # al_piece_length_mm, al_is_offcut, al_parent_cut_id như custom field
    # bạn đã có sẵn trên Serial No)
    row_offcut = se.append("items", {
        "item_code": offcut_item,
        "t_warehouse": warehouse,
        "qty": offcut_qty,
    })

    se.insert()  # insert TRƯỚC để có se.name cho voucher_no

    # Gắn Bundle cho từng dòng SAU khi có se.name + row.name (voucher_detail_no)
    row_source.serial_and_batch_bundle = make_serial_and_batch_bundle(
        item_code=source_item, warehouse=warehouse,
        entries=[{"batch_no": source_batch_no,
                  "qty": -cut_pieces["total_length_m"]}],  # âm cho Outward
        type_of_transaction="Outward",
        voucher_type="Stock Entry", voucher_no=se.name,
        voucher_detail_no=row_source.name,
    )
    row_target.serial_and_batch_bundle = make_serial_and_batch_bundle(
        item_code=target_item, warehouse=warehouse,
        entries=[{"batch_no": source_batch_no,   # giữ nguyên batch → giữ màu/lô
                  "qty": cut_pieces["usable_length_m"]}],
        type_of_transaction="Inward",
        voucher_type="Stock Entry", voucher_no=se.name,
        voucher_detail_no=row_target.name,
    )
    row_offcut.serial_and_batch_bundle = make_serial_and_batch_bundle(
        item_code=offcut_item, warehouse=warehouse,
        entries=[
            {"serial_no": f"OFFCUT-{se.name}-{i:03d}", "qty": 1}
            for i in range(1, int(offcut_qty) + 1)
        ],
        type_of_transaction="Inward",
        voucher_type="Stock Entry", voucher_no=se.name,
        voucher_detail_no=row_offcut.name,
    )

    se.save()
    se.submit()
    return se.name
```

> **Verify trước khi dùng thật**: tên field chính xác (`voucher_detail_no`,
> `type_of_transaction`, thứ tự insert bundle trước/sau khi có `se.name`) có
> thể lệch vài chi tiết nhỏ giữa các minor version của v15/v16. Cách chắc
> chắn nhất: tạo 1 Stock Entry Repack **thủ công qua UI** trên chính bench
> AlumGlass, xem network tab / `frappe.get_doc("Stock Entry", "...")` sau
> khi submit để lấy đúng cấu trúc field — đúng phương pháp "đối chiếu code
> thật" mà tài liệu gốc đã làm cho Stock Reconciliation.

### 29.4 Điều KHÔNG đổi — tin tốt cho custom field đã có

Toàn bộ custom field bạn đã thiết kế:

- Trên **Batch**: `al_color`, `al_source_project`, `al_trace_stage`, `al_bin_location`
- Trên **Serial No**: `al_piece_length_mm`, `al_is_offcut`, `al_parent_cut_id`

**Không cần sửa gì cả.** SABB là doctype trung gian nối *document row* với
*stock ledger* — nó không thay thế Batch/Serial No doctype, cũng không di
chuyển field. Batch và Serial No vẫn là master data độc lập, custom field
trên đó hoạt động y hệt trước và sau khi có SABB. Đây là lý do nên tách rõ
2 khái niệm khi review code: "Batch/Serial No" (master data, ổn định) vs
"cách document row liên kết với chúng" (đã đổi, cần sửa code tạo giao dịch).

### 29.5 Tác động đến các Mục 13-17 (Phương án D/E — override Stock Reconciliation)

Đây là điểm cần cảnh báo rõ nhất: Mục 14 (Phương án E) và Mục 17 (kế hoạch
migration LLE) của tài liệu gốc mô tả chi tiết `get_sle_for_items()`,
`update_stock_ledger()` dựa trên code v14.92.14 — nơi Stock Reconciliation
Item có field `batch_no` trực tiếp. Trên v15/v16, **Stock Reconciliation
Item cũng đã chuyển sang dùng `serial_and_batch_bundle`** cho item có
batch/serial tracking. Nghĩa là:

- Toàn bộ đoạn code trích dẫn ở Mục 1-2 (`validate_inventory_dimension()`,
  `get_sle_for_items()`) **cần đọc lại trên đúng version thật của bench
  AlumGlass** trước khi áp dụng bất kỳ Phương án D/E nào — vì tên hàm có
  thể giữ nguyên nhưng nội dung xử lý bundle bên trong đã khác đáng kể so
  với bản v14.92.14 đã trích.
- Đây không phải lý do bỏ Phương án E — nguyên lý (Inventory Dimension core
  + override chỉ phần cần thiết cho periodic reconciliation) vẫn đúng. Chỉ
  là **bước 1 của Phase 0 (Chuẩn bị)** trong kế hoạch migration (Mục 17.2)
  cần thêm 1 việc: đọc lại `stock_reconciliation.py` và
  `serial_and_batch_bundle.py` **trên đúng v16**, không dùng nguyên các
  trích dẫn v14 trong tài liệu này làm căn cứ kỹ thuật cuối cùng.

---

## 30. CHECKLIST TRIỂN KHAI CHO ALUMGLASS

- [ ] **Sửa Mục 21.3.2**: đánh dấu deprecated, ghi chú lý do (Mục 28 ở trên)
- [ ] Audit toàn bộ code trong `al_manufacturing/` (Cutting Plan Alu, Cutting Plan Glass, Production Order Bridge) xem có chỗ nào đang gán trực tiếp `batch_no`/`serial_no` vào Stock Entry Detail — nếu có, sửa theo pattern Mục 29.3
- [ ] Xác nhận trên chính bench v16: field `serial_and_batch_bundle` có mặt trên Stock Entry Detail / Purchase Receipt Item / Delivery Note Item / Stock Reconciliation Item (mở Item nào có `has_batch_no=1`, tạo thử 1 Stock Entry qua UI, xem cấu trúc thật)
- [ ] Test riêng: nhập kho nhôm theo lô (Batch) qua SABB, xuất bán 1 phần lô đó, xác nhận `al_color` trên Batch vẫn hiển thị đúng trong báo cáo tồn kho
- [ ] Test riêng: kính phi chuẩn — mỗi tấm 1 Serial No qua SABB, custom field `al_piece_length_mm` vẫn ghi/đọc đúng
- [ ] Với các phần đã tự viết dựa trên Mục 13-17 (nếu có) — review lại theo cảnh báo ở Mục 29.5 trước khi đưa vào production
- [ ] Cập nhật lại Mục lục tài liệu gốc, thêm Mục 28-30 vào danh sách

---

*Bổ sung — 2026-08-11 | Dựa trên kiến trúc Serial and Batch Bundle chính
thức của Frappe v15+. Khuyến nghị verify lại với code thật trên bench v16
của bạn trước khi triển khai, theo đúng phương pháp tài liệu gốc đã dùng.*
