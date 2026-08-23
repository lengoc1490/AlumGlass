---
title: "Item làm master data — Mã sản phẩm (AL BOM / Bom Set / Accessory Set)"
contexts:
  - "Form/AL BOM"
  - "Form/AL Bom Set"
  - "Form/AL Accessory Set"
tags: [khac]
doc_type: design
---

# Item làm master data — Mã sản phẩm (AL BOM / Bom Set / Accessory Set)

> **Job:** `2026-08-22_quotation-dialog-row-vars` (phần P2 data-model)
> **Trạng thái:** Implemented 2026-08-23 · **PA B đã chốt** (Owner 2026-08-23) ·
> chờ Owner verify migrate alumglass-dev

## Quyết định (đã chốt với Owner)

1. **AL BOM:** TÁI DÙNG `representative_item` (Link → Item có sẵn) — đổi label
   thành **"Mã sản phẩm"**, get_query lọc Item Group `SAN_PHAM` + group con
   (**PA B**). KHÔNG tạo field mới.
2. **Item Group `SAN_PHAM`** (group cha, tên tiếng Việt "Sản phẩm hoàn chỉnh"):
   tạo trong `setup/seed_demo_data.py` `_item_groups()`. Chỉ tạo group, KHÔNG seed
   Item sản phẩm mới (job khác). **Giữ tên code `SAN_PHAM`** (Owner chốt) — nhất
   quán với NHOM_PROFILE/NHOM_XINGFA/KINH, tên tiếng Việt trong description.
3. **Bom identity:** `item_code + brand + profile_system`. AL Bom Set vốn đã có
   `brand` + `profile_system` → chỉ thêm `item_code` cho đủ bộ.
4. **AL Bom Set + AL Accessory Set:** thêm field `item_code` (Link → Item, label
   "Mã sản phẩm", get_query lọc `SAN_PHAM` + group con).
5. **Filter "Mã sản phẩm" = PA B** (Owner chốt 2026-08-23): server-side
   whitelisted method `alumglass.api.product_item_query` trả Item thuộc
   `SAN_PHAM` + mọi group con. Thay filter JS đơn giản `{item_group: "SAN_PHAM"}`.

## Data model

| DocType | Field | Thay đổi |
|---|---|---|
| AL BOM | `representative_item` | Label "Representative Item" → **"Mã sản phẩm"** (giữ fieldname, giữ reqd). Description cập nhật. |
| AL Bom Set | `item_code` | **Mới** — Link → Item, label "Mã sản phẩm", in_list_view, sau `set_name`. |
| AL Accessory Set | `item_code` | **Mới** — Link → Item, label "Mã sản phẩm", in_list_view, sau `set_name`. |
| Item Group | `SAN_PHAM` | **Mới** — parent "All Item Groups", is_group=1, description "Sản phẩm hoàn chỉnh…". |

`get_query` cho cả 3 field trỏ tới server-side method **`alumglass.api.product_item_query`**
(qua `frm.set_query` trong doctype JS — xem bên dưới).

## Vì sao filter là server-side query method, không phải filter JS đơn giản

- **PA B (Owner chốt):** filter `SAN_PHAM` + mọi group con của nó. Filter JS
  `{item_group: "SAN_PHAM"}` chỉ lấy đúng group (không gồm group con) → không đủ.
- **DocField v14 KHÔNG có cột `get_query`** (kiểm tra `docfield.json` không có
  fieldname này) → không thể persist `get_query` trong file doctype JSON.
- → Đặt `frm.set_query("representative_item"/"item_code", ...)` trả
  `{query: "alumglass.api.product_item_query"}` trong `al_bom.js` /
  `al_bom_set.js` / `al_accessory_set.js`. Method này follow đúng contract
  `erpnext.controllers.queries.item_query` (whitelisted + validate_and_sanitize_search_inputs,
  nhận `(doctype, txt, searchfield, start, page_len, filters, as_dict)`) nên hoạt
  động với `frappe.desk.search.search_widget`.

## Method `alumglass.api.product_item_query`

- Bước 1: `frappe.db.exists("Item Group", "SAN_PHAM")`; nếu có → lấy cached doc
  root (có `lft`/`rgt`), query các Item Group có `lft > root.lft AND rgt < root.rgt`
  (descendants). Gộp thành `[SAN_PHAM] + descendants`.
- Bước 2: `frappe.get_all("Item", filters={"item_group": ["in", group_names],
  "disabled": 0, "has_variants": 0})`.
- Bước 3: lọc theo `txt` trên `name`/`item_name`.
- SAN_PHAM chưa có group con / chưa có Item → trả `[]` (không crash). Đã verify
  bằng probe (tạm insert 1 Item vào SAN_PHAM rồi rollback → method trả đúng item đó).

## ⚠ Dữ liệu cũ — NHOM-XINGFA không thuộc SAN_PHAM (đã chốt)

`BOM-CDMQ-2C.representative_item = NHOM-XINGFA` thuộc group `NHOM_XINGFA` (Item
đại diện VẬT LIỆU nhôm), KHÔNG phải sản phẩm hoàn chỉnh.

- **Trên form:** giá trị cũ vẫn hiển thị (Link field lưu docname, Frappe hiện
  value đã lưu). Người dùng chỉ **không search lại** được `NHOM-XINGFA` trong
  dropdown khi muốn đổi.
- **Quyết định Owner (PA B):** chấp nhận giới hạn này — không mở rộng method cho
  item ngoài SAN_PHAM. Không cần đổi lại.

## Item Group name = code

Item Group chuẩn ERPNext chỉ có `item_group_name` (unique, hiển thị). Theo
convention app (NHOM_PROFILE, NHOM_XINGFA, KINH…) đặt group name = **code**
(`SAN_PHAM`) — vừa làm key filter trong get_query, vừa hiển thị trên tree.
Tên tiếng Việt "Sản phẩm hoàn chỉnh" ghi trong `description`. **Owner đã chốt
giữ code `SAN_PHAM`** — không đổi tên.

## Files

- `alumglass/setup/seed_demo_data.py` — `_item_groups()` thêm group SAN_PHAM
- `alumglass/alumglass/api/__init__.py` — `product_item_query` (server-side query method)
- `alumglass/al_bom_engine/doctype/al_bom/al_bom.json` + `al_bom.js`
- `alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.json` + `al_bom_set.js`
- `alumglass/al_bom_engine/doctype/al_accessory_set/al_accessory_set.json` + `al_accessory_set.js`
