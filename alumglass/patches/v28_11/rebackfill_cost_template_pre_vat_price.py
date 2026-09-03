# -*- coding: utf-8 -*-
"""D7 — Re-backfill `cost_template_snapshot` bổ sung cờ `is_pre_vat_price`.

Patch v28_10 re-backfill snapshot khi thêm cờ `is_final_price`. Lần này thêm
cờ MỚI `is_pre_vat_price` trên AL Cost Template Item (dòng "giá trước VAT" —
engine `_resolve_pre_vat_price`), snapshot build bằng code CŨ (chưa có field)
→ published version ĐÃ CÓ từ trước sẽ THIẾU cờ → engine không nhận diện được
dòng pre-VAT nếu config thay đổi sau này.

Giống hệt lưu ý v28_10:
- Backfill dùng config HIỆN TẠI (không phải config tại thời điểm publish gốc).
- Ghi đè TOÀN BỘ `cost_template_snapshot` (config hiện tại của AL Cost
  Template) — mục tiêu bổ sung field mới vào snapshot đã tồn tại. Không đụng
  field khác → không vi phạm `_guard_published_immutability`.
- Idempotent: chạy lại nhiều lần cho kết quả giống hệt (luôn dùng config hiện
  tại). KHÔNG có dòng nào flag is_pre_vat_price=1 → snapshot tương đương cũ
  (cờ mặc định 0) → golden-safe.

Chạy SAU seed v28_9/v28_10 (post_model_sync thứ tự khai báo trong patches.txt).
"""
import json

import frappe


def execute():
    versions = frappe.get_all(
        "AL BOM Version",
        filters={"workflow_state": "Published"},
        pluck="name",
    )
    if not versions:
        return

    updated = 0
    for version_name in versions:
        old_raw = frappe.db.get_value(
            "AL BOM Version", version_name, "cost_template_snapshot")
        if not old_raw:
            continue
        try:
            old = json.loads(old_raw) if isinstance(old_raw, str) else old_raw
            template_code = old.get("template_code")
        except (ValueError, TypeError):
            continue
        if not template_code or not frappe.db.exists("AL Cost Template", template_code):
            continue

        ct = frappe.get_cached_doc("AL Cost Template", template_code)
        new_snapshot = json.dumps({
            "template_code": ct.template_code,
            "template_name": ct.template_name,
            "items": [{
                "line_code": i.line_code,
                "line_label": i.line_label,
                "calc_formula": i.calc_formula,
                "cost_bucket": i.cost_bucket,
                "is_final_price": i.get("is_final_price", 0),
                "is_pre_vat_price": i.get("is_pre_vat_price", 0),
            } for i in ct.items],
        }, indent=2)
        frappe.db.set_value(
            "AL BOM Version", version_name,
            "cost_template_snapshot", new_snapshot,
            update_modified=False,
        )
        updated += 1

    if updated:
        frappe.db.commit()
    frappe.logger("alumglass").info(
        "D7 rebackfill_cost_template_pre_vat_price: updated %d version(s)"
        % updated
    )
