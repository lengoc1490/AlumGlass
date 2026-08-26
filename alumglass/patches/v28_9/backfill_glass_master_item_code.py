# -*- coding: utf-8 -*-
"""Phase 1b — Backfill `item_code` cho AL Glass Master.

Trước: AL Glass Master chưa có field `item_code` → engine chèn line kính vào BOM
phải map tay mã Item. Sau: field `item_code` (Link → Item) đã thêm trên doctype;
patch này điền Item tương ứng cho mọi Glass Master còn trống.

Quy tắc backfill (ưu tiên giảm dần):
  1. Item có `name == glass_code` (VD: KINH-LOWE-24) — convention seed cùng tên.
  2. Item có `item_name == glass_name` (VD: "Kính Low-E 24mm").
  3. Không tìm thấy → để trống (không guess sai), chỉ log warning.

Idempotent: chỉ set khi `item_code` đang rỗng; chạy lại nhiều lần không ghi đè
item_code đã có (admin có thể đã sửa tay).
"""
import frappe


def execute():
    glass_masters = frappe.get_all(
        "AL Glass Master",
        filters={"item_code": ["in", ["", None]]},
        fields=["name", "glass_code", "glass_name"],
        order_by="name",
    )
    updated = 0
    skipped = 0
    for gm in glass_masters:
        item = None
        if gm.get("glass_code") and frappe.db.exists("Item", gm["glass_code"]):
            item = gm["glass_code"]
        elif gm.get("glass_name"):
            hit = frappe.db.get_value(
                "Item", {"item_name": gm["glass_name"]}, "name")
            if hit:
                item = hit
        if item:
            frappe.db.set_value(
                "AL Glass Master", gm["name"], "item_code", item,
                update_modified=False)
            updated += 1
        else:
            skipped += 1
            frappe.log_error(
                title="AL Glass Master backfill item_code — không tìm thấy Item",
                message=f"{gm['name']} (glass_code={gm.get('glass_code')}, "
                        f"glass_name={gm.get('glass_name')})",
            )
    frappe.db.commit()
    print(f"backfill_glass_master_item_code: {updated} updated, {skipped} skipped")
