# -*- coding: utf-8 -*-
"""P1 — Backfill `pricing_dimension_snapshot` cho AL BOM Version cũ.

BOM Version Published trước patch P1 sẽ có `pricing_dimension_snapshot` rỗng
(NULL/""). Engine vẫn fallback query LIVE (có warning log) nhưng không đảm bảo
báo giá tái lập được. Patch này chạy 1 lần (Frappe track trong `tabPatch Log`),
điền snapshot cho MỌI version Published còn rỗng.

QUAN TRỌNG (quyết định ghi nhận trong docs/design/p1-pricing-dimension-versioning.md):
- Backfill dùng config Pricing Dimension **HIỆN TẠI**, KHÔNG phải config tại đúng
  thời điểm publish gốc (dữ liệu đó không còn lưu ở đâu). Với BOM Version cũ,
  nếu config đã đổi từ lúc publish → backfill không "sửa sai" được quá khứ, chỉ
  chặn sai lệch từ giờ trở đi.
- Chỉ `set_value` field mới (đang rỗng → set lần đầu hợp lệ), KHÔNG đụng field
  khác → không vi phạm `_guard_published_immutability`.
- Idempotent: filter `pricing_dimension_snapshot` rỗng → chạy lại nhiều lần cũng
  không ghi đè snapshot đã có.
"""
import json

import frappe


def execute():
    versions = frappe.get_all(
        "AL BOM Version",
        filters={
            "workflow_state": "Published",
            "pricing_dimension_snapshot": ["in", ["", None]],
        },
        pluck="name",
    )
    if not versions:
        return

    dimensions = frappe.get_all(
        "AL Pricing Dimension",
        fields=["dimension_code", "dimension_type", "custom_fieldname"],
        order_by="dimension_code",
    )
    mappings = frappe.get_all(
        "AL Variable Dimension Mapping",
        fields=["variable_name", "pricing_dimension", "price_multiplier",
                "material_category"],
        order_by="variable_name",
    )
    snapshot = json.dumps(
        {
            "captured_at": frappe.utils.now_datetime().isoformat(),
            "dimensions": dimensions,
            "mappings": mappings,
            "backfilled": True,  # đánh dấu rõ: không phải snapshot gốc tại publish
        },
        default=str,
    )

    for name in versions:
        frappe.db.set_value(
            "AL BOM Version", name, "pricing_dimension_snapshot", snapshot,
            update_modified=False,
        )

    frappe.db.commit()
    frappe.logger("alumglass").info(
        "Backfilled pricing_dimension_snapshot cho %d AL BOM Version." % len(versions)
    )
