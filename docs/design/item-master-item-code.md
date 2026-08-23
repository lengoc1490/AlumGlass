---
title: "Item làm master data — Mã sản phẩm (AL BOM / Bom Set / Accessory Set)"
contexts:
  - "Form/AL BOM"
  - "Form/AL Bom Set"
  - "Form/AL Accessory Set"
tags: [khac]
doc_type: design
---

# Item làm master data — Mã sản phẩm

> **Job:** `2026-08-22_quotation-dialog-row-vars` (phần P2 data-model)
> **Trạng thái:** Implemented 2026-08-23 · chờ Owner verify migrate alumglass-dev

## Quyết định (đã chốt với Owner)

1. **AL BOM:** TÁI DÙNG `representative_item` (Link → Item có sẵn) — đổi label
   thành **"Mã sản phẩm"**, thêm get_query lọc Item Group `SAN_PHAM`. KHÔNG tạo
   field mới.
2. **Item Group `SAN_PHAM`** (group cha, tên tiếng Việt "Sản phẩm hoàn chỉnh"):
   tạo trong `setup/seed_demo_data.py` `_item_groups()`. Chỉ tạo group, KHÔNG seed
   Item sản phẩm mới (job khác).
3. **Bom identity:** `item_code + brand + profile_system`. AL Bom Set vốn đã có
   `brand` + `profile_system` → chỉ thêm `item_code` cho đủ bộ.
4. **AL Bom Set + AL Accessory Set:** thêm field `item_code` (Link → Item, label
   "Mã sản phẩm", get_query lọc `SAN_PHAM`).

## Data model

| DocType | Field | Thay đổi |
|---|---|---|
| AL BOM | `representative_item` | Label "Representative Item" → **"Mã sản phẩm"** (giữ fieldname, giữ reqd). Description cập nhật. |
| AL Bom Set | `item_code` | **Mới** — Link → Item, label "Mã sản phẩm", in_list_view, sau `set_name`. |
| AL Accessory Set | `item_code` | **Mới** — Link → Item, label "Mã sản phẩm", in_list_view, sau `set_name`. |
| Item Group | `SAN_PHAM` | **Mới** — parent "All Item Groups", is_group=1, description "Sản phẩm hoàn chỉnh…". |

`get_query` filter `{"item_group": "SAN_PHAM"}` áp cho cả 3 field (qua `frm.set_query`
trong doctype JS — xem bên dưới).

## Vì sao get_query đặt trong doctype JS, không trong doctype JSON

- **DocField v14 KHÔNG có cột `get_query`** (kiểm tra `docfield.json` không có
  fieldname này) → không thể persist `get_query` trong file doctype JSON.
- Convention app (quotation.js override) dùng `set_query`/`get_query` ở client JS.
- → Đặt `frm.set_query("representative_item"/"item_code", ...)` trong file
  `al_bom.js` / `al_bom_set.js` / `al_accessory_set.js`.

## ⚠ Dữ liệu cũ — NHOM-XINGFA không thuộc SAN_PHAM

`BOM-CDMQ-2C.representative_item = NHOM-XINGFA` thuộc group `NHOM_XINGFA` (Item
đại diện VẬT LIỆU nhôm), KHÔNG phải sản phẩm hoàn chỉnh. Với get_query lọc cứng
`SAN_PHAM`:

- **Trên form:** giá trị cũ vẫn hiển thị (Link field lưu docname, Frappe hiện
  value đã lưu). Người dùng chỉ **không search lại** được `NHOM-XINGFA` trong
  dropdown.
- **Trạng thái:** đang chờ Elon/Owner chốt hướng. Các phương án (không filter
  cứng / filter Item Group con của SAN_PHAM / cho phép giá trị hiện tại vẫn
  search được qua server-side query method) — xem report DEV2
  `Elon_DEV2_item-master-ket-qua.md`.

## Item Group name = code

Item Group chuẩn ERPNext chỉ có `item_group_name` (unique, hiển thị). Theo
convention app (NHOM_PROFILE, NHOM_XINGFA, KINH…) đặt group name = **code**
(`SAN_PHAM`) — vừa làm key filter trong get_query, vừa hiển thị trên tree.
Tên tiếng Việt "Sản phẩm hoàn chỉnh" ghi trong `description`. Nếu Owner muốn
tree hiển thị tiếng Việt → phải đổi `item_group_name` (vỡ mọi filter/fixture
đang trỏ "SAN_PHAM") — cần cân nhắc.

## Files

- `alumglass/setup/seed_demo_data.py` — `_item_groups()` thêm group SAN_PHAM
- `alumglass/al_bom_engine/doctype/al_bom/al_bom.json` + `al_bom.js`
- `alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.json` + `al_bom_set.js`
- `alumglass/al_bom_engine/doctype/al_accessory_set/al_accessory_set.json` + `al_accessory_set.js`
