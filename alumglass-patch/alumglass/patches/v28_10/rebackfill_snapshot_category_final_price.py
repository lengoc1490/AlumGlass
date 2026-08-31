# -*- coding: utf-8 -*-
"""V6 P10 — Re-backfill `pricing_dimension_snapshot` + `cost_template_snapshot`
cho AL BOM Version ĐÃ CÓ snapshot (patch v28_9 chỉ backfill snapshot RỖNG,
nên bản vá thêm field `material_category` (AL Variable Dimension Mapping) và
`is_final_price` (AL Cost Template Item) không tự động lan tới các BOM
Version đã Published từ trước).

QUAN TRỌNG (giống lưu ý của patch v28_9):
- Backfill dùng config HIỆN TẠI, không phải config tại đúng thời điểm publish
  gốc. Nếu Pricing Dimension / Cost Template đã đổi từ lúc publish, patch này
  không "sửa sai" quá khứ, chỉ đảm bảo báo giá TỪ GIỜ trở đi lọc đúng
  material_category / is_final_price.
- Ghi đè TOÀN BỘ 2 field snapshot (không chỉ field rỗng) — khác v28_9 —
  vì mục tiêu là bổ sung field mới vào snapshot đã tồn tại. Không đụng field
  khác trên AL BOM Version → không vi phạm _guard_published_immutability.
- Idempotent theo nghĩa: chạy lại nhiều lần cho kết quả giống hệt (luôn dùng
  config hiện tại), không gây side-effect tích lũy.

Sau khi chạy patch này, có thể chạy lại golden test CDMQ-2C/4C để xác nhận
không có sai lệch khi bật lọc material_category cho các version cũ.
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
    pricing_snapshot = json.dumps(
        {
            "captured_at": frappe.utils.now_datetime().isoformat(),
            "dimensions": dimensions,
            "mappings": mappings,
        },
        indent=2,
    )

    for version_name in versions:
        frappe.db.set_value(
            "AL BOM Version", version_name,
            "pricing_dimension_snapshot", pricing_snapshot,
            update_modified=False,
        )

        # cost_template_snapshot: chỉ re-backfill nếu version có gắn Cost
        # Template (đọc lại từ chính snapshot cũ để biết template_code, tránh
        # phải trace ngược qua AL BOM/AL Bom Set).
        old_ct_raw = frappe.db.get_value(
            "AL BOM Version", version_name, "cost_template_snapshot")
        if not old_ct_raw:
            continue
        try:
            old_ct = json.loads(old_ct_raw) if isinstance(old_ct_raw, str) else old_ct_raw
            template_code = old_ct.get("template_code")
        except (ValueError, TypeError):
            continue
        if not template_code or not frappe.db.exists("AL Cost Template", template_code):
            continue

        ct = frappe.get_cached_doc("AL Cost Template", template_code)
        new_ct_snapshot = json.dumps({
            "template_code": ct.template_code,
            "template_name": ct.template_name,
            "items": [{
                "line_code": i.line_code,
                "line_label": i.line_label,
                "calc_formula": i.calc_formula,
                "cost_bucket": i.cost_bucket,
                "is_final_price": i.get("is_final_price", 0),
            } for i in ct.items],
        }, indent=2)
        frappe.db.set_value(
            "AL BOM Version", version_name,
            "cost_template_snapshot", new_ct_snapshot,
            update_modified=False,
        )

    frappe.db.commit()
