# -*- coding: utf-8 -*-
"""C2 — Migrate FVB `cost_bucket_aggregate` → `aggregate_from_items` (platform).

Bối cảnh (de-xuat §3B + fb_source_type_contract §9):
- `cost_bucket_aggregate` là handler CŨ viết tay trong `fb_handlers.py` — gom
  `line_total` theo `cost_bucket` (filter_by + sum_field) từ Bom Items của
  `AL BOM Version.bom_set_snapshot`.
- Formula Builder đã có source_type CHUẨN `aggregate_from_items` (config
  schema registry ~line 2726) làm đúng việc đó với `rows_source="snapshot"` +
  `snapshot_doctype`/`snapshot_field`/`rows_path` + `aggregate="sum"` +
  `value_field` + multi-field `filters`. C2 = migration: KHÔNG còn handler
  alumglass riêng (sau patch này, `fb_handlers.py` chỉ còn 2 handler).

Bản vá quét FVB có `source_type="cost_bucket_aggregate"` và REWRITE sang
`aggregate_from_items` (config CHUẨN platform — khớp contract DEV2
`formula_builder/docs/aggregate_from_items.md` mục migration + schema registry):
    source_config mới = {
        "rows_source": "snapshot",
        "snapshot_doctype": "AL BOM Version",
        # Legacy handler đọc resolved_so_far["bom_version"] → tên snapshot doc
        # phải là template {{resolved.bom_version}} (schema hỗ trợ template).
        "snapshot_name": "{{resolved.bom_version}}",
        # snapshot_field set TƯỜNG MINH (default platform là "snapshot" —
        # legacy đọc field "bom_set_snapshot", không được để default).
        "snapshot_field": "bom_set_snapshot",
        "rows_path": "items",
        "aggregate": "sum",
        # value_field bắt buộc trong schema (required) — set = sum_field cũ
        # (default "line_total"). sum_field chỉ là alias khi value_field rỗng.
        "value_field": sum_field (mặc định "line_total"),
        "filters": [[k, "=", v] cho từng cặp filter_by cũ],
    }
    default_value / data_type / applies_to_* / resolve_priority GIỮ NGUYÊN.

FVB không phải dạng này (aluminum_price_composite/glass_master_data/
linked_doctype_field...) → KHÔNG đụng. Đúng 1 record cũ seed từ composite
price (`COMPOSITE_MATERIAL_PRICE`) có source_type khác → bỏ qua.

Idempotent: rewrite source_config cùng 1 giá trị mỗi lần chạy → chạy lại
không đổi gì. Không tạo/xóa FVB record.
"""
import json

import frappe


def _rewrite_config(old_cfg):
    """source_config cost_bucket_aggregate → aggregate_from_items."""
    filter_by = old_cfg.get("filter_by") or {}
    filters = []
    if isinstance(filter_by, dict):
        for k, v in filter_by.items():
            if k:
                filters.append([k, "=", v])
    elif isinstance(filter_by, list):
        # phòng trường hợp lưu dạng list (k="=", v) sẵn — giữ nguyên
        for row in filter_by:
            if row and len(row) >= 3:
                filters.append(list(row[:3]))
    sum_field = old_cfg.get("sum_field") or "line_total"
    return {
        "rows_source": "snapshot",
        "snapshot_doctype": "AL BOM Version",
        # Template tường minh: resolved_so_far phải có key "bom_version"
        # (đúng key legacy handler đọc). Schema fallback nếu rỗng là
        # resolved_so_far[snapshot_doctype] / doc[snapshot_doctype].
        "snapshot_name": "{{resolved.bom_version}}",
        "snapshot_field": "bom_set_snapshot",
        "rows_path": "items",
        "aggregate": "sum",
        "value_field": sum_field,
        "filters": filters,
    }


def execute():
    bindings = frappe.get_all(
        "Formula Variable Binding",
        filters={"source_type": "cost_bucket_aggregate"},
        fields=["name", "source_config"],
    ) or []
    if not bindings:
        return

    migrated = 0
    skipped = 0
    for b in bindings:
        raw = b.get("source_config")
        try:
            cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (ValueError, TypeError):
            skipped += 1
            continue
        if not isinstance(cfg, dict):
            skipped += 1
            continue
        new_cfg = _rewrite_config(cfg)
        frappe.db.set_value(
            "Formula Variable Binding", b["name"],
            {
                "source_type": "aggregate_from_items",
                "source_config": json.dumps(new_cfg, ensure_ascii=False),
            },
            update_modified=False,
        )
        migrated += 1

    if migrated:
        frappe.db.commit()
    frappe.logger("alumglass").info(
        "C2 migrate cost_bucket_aggregate→aggregate_from_items: migrated=%d "
        "skipped=%d" % (migrated, skipped)
    )
