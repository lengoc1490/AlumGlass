# -*- coding: utf-8 -*-
"""
Backfill AL Profile System Variable (child table) từ 4 field offset_* cũ.

Mapping (theo Variable Library source_field hiện tại):
    offset_frame    -> OFFSET_FRAME
    offset_glass    -> OFFSET_GLASS
    offset_fixed    -> OFFSET_FIXED
    offset_crossbar -> OFFSET_DO_NGANG

Idempotent: chỉ backfill cho profile CHƯA có row nào trong system_variables.
POST_model_sync (child table đã sync trước khi patch chạy).
"""

import frappe

OFFSET_MAP = [
    ("offset_frame", "OFFSET_FRAME"),
    ("offset_glass", "OFFSET_GLASS"),
    ("offset_fixed", "OFFSET_FIXED"),
    ("offset_crossbar", "OFFSET_DO_NGANG"),
]


def execute():
    profiles = frappe.get_all(
        "AL Profile System",
        fields=["name", "system_code", "offset_frame", "offset_glass", "offset_fixed", "offset_crossbar"],
        order_by="name asc",
    )
    updated = 0
    skipped = 0
    for p in profiles:
        existing = frappe.get_all(
            "AL Profile System Variable",
            filters={"parent": p["name"]},
            limit=1,
        )
        if existing:
            skipped += 1
            continue

        rows = []
        for fieldname, var_name in OFFSET_MAP:
            val = p.get(fieldname)
            if val is None:
                continue
            # Float lưu trực tiếp dạng số — tránh mất precision khi round
            rows.append(
                {
                    "variable": var_name,
                    "value": str(val),
                    "is_active": 1,
                }
            )

        if not rows:
            skipped += 1
            continue

        doc = frappe.get_doc("AL Profile System", p["name"])
        doc.set("system_variables", rows)
        doc.flags.ignore_permissions = True
        doc.save()
        updated += 1

    frappe.db.commit()
    print(f"backfill_profile_system_variables: {updated} updated, {skipped} skipped")
