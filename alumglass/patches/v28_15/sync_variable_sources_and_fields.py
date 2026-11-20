# -*- coding: utf-8 -*-
"""v28_15 — Đồng bộ NGUỒN biến + alias độ dày kính trên site ĐANG CHẠY.

Vì sao phải là patch MỚI (không sửa v28_14)
───────────────────────────────────────────
Patch `v28_14.seed_variable_catalog` đã chạy và đã ghi Patch Log trên các site
hiện hữu ⇒ sửa `_ROW_LITERALS` ở đó CHỈ có tác dụng với site mới. Site đang
chạy cần một bước bù dữ liệu đã có, nên tách patch riêng.

Nội dung (đều ADDITIVE — không xoá dòng, không đổi cấu hình admin đã sửa tay):

  a. `AL Variable Settings.row_literals`
     · Bổ sung dòng còn thiếu: `total_thick_mm`, `max_area_m2` (kèm nguồn).
     · Điền `source_doctype` / `source_field` cho các dòng CHUẨN đang trống,
       lấy từ `alumglass.variable_sources.field_provenance` (một chỗ duy nhất).
     · Đổi nhãn `glass_thick` thành "Độ dày kính (tên cũ)" — CHỈ khi nhãn vẫn
       đúng giá trị seed cũ, để không đè nhãn admin đã sửa.

  b. `AL Variable Profile.cross_row`
     · Với mọi profile có `cross_row` và cột `fields` KHÔNG rỗng: thêm
       `total_thick_mm`, `max_area_m2` nếu chưa có.
     · `fields` RỖNG = "mọi field vô hướng" — ⛔ không đụng (đã bao trùm).
     · ⛔ Không tạo / không xoá profile.

Idempotent: chạy lần 2 không thêm dòng, không nhân đôi field, không đổi nhãn
lần nữa. Mọi bước ghi đều có điều kiện "chưa có mới ghi".
"""
import json

import frappe

from alumglass.variable_sources.field_provenance import ROW_LITERAL_SOURCES

#: Nhãn seed CŨ của `glass_thick` — chỉ đổi khi nhãn vẫn đúng giá trị này.
OLD_GLASS_THICK_LABEL = "Độ dày kính"
GLASS_THICK_LABEL = "Độ dày kính (tên cũ)"

#: Dòng literal còn thiếu trên site chạy v28_14 bản đầu (var_name, sort_order).
_EXTRA_ROW_LITERALS = (
    ("total_thick_mm", 65),
    ("max_area_m2", 100),
)

#: Field cross-row bổ sung cho các profile đã khai `fields` tường minh.
_CROSS_ROW_NEW_FIELDS = ("total_thick_mm", "max_area_m2")


def _clean(value):
    return (value or "").strip() if isinstance(value, str) else (value or "")


def _sync_row_literals():
    """Bù dòng literal + nguồn cho `AL Variable Settings`. Trả số thay đổi."""
    if not frappe.db.exists("DocType", "AL Variable Settings"):
        print("  · AL Variable Settings: chưa có DocType, bỏ qua")
        return 0
    if not frappe.db.has_column("AL Row Literal", "source_doctype"):
        # Patch khai ở [post_model_sync]; nhánh này chỉ xảy ra khi migrate sai
        # thứ tự — báo rõ thay vì lặng lẽ ghi dòng thiếu nguồn.
        print("  · AL Row Literal: chưa có cột source_doctype — bỏ qua "
              "(kiểm tra patches.txt: phải ở [post_model_sync])")
        return 0

    settings = frappe.get_single("AL Variable Settings")
    existing = {
        row.get("var_name"): row
        for row in (settings.get("row_literals") or [])
        if row.get("var_name")
    }

    changes = 0
    added = 0
    for name, sort_order in _EXTRA_ROW_LITERALS:
        if name in existing:
            continue
        source = ROW_LITERAL_SOURCES.get(name) or {}
        settings.append("row_literals", {
            "var_name": name,
            "var_label": source.get("label") or name,
            "var_type": "Float",
            "group_label": "Row Literals",
            "sort_order": sort_order,
            "is_active": 1,
            "source_doctype": source.get("doctype") or "",
            "source_field": source.get("field") or "",
            "description": "Engine inject theo từng dòng BOM khi tính giá",
        })
        added += 1
        changes += 1

    sources_filled = 0
    renamed = 0
    for name, row in existing.items():
        source = ROW_LITERAL_SOURCES.get(name)
        if source:
            if not _clean(row.get("source_doctype")):
                row.source_doctype = source["doctype"]
                sources_filled += 1
                changes += 1
            if not _clean(row.get("source_field")):
                row.source_field = source["field"]
                sources_filled += 1
                changes += 1
        if name == "glass_thick" \
                and _clean(row.get("var_label")) == OLD_GLASS_THICK_LABEL:
            row.var_label = GLASS_THICK_LABEL
            renamed += 1
            changes += 1

    if changes:
        settings.flags.ignore_permissions = True
        settings.save()

    print("  · Row literals: +%d dòng, điền nguồn %d field, đổi nhãn %d"
          % (added, sources_filled, renamed))
    return changes


def _parse_field_list(raw):
    """`cross_row.fields` → list[str], hoặc None khi rỗng/không hợp lệ."""
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, list) else None


def _sync_profiles():
    """Bổ sung 2 field cross-row cho profile đã khai `fields`. Trả số profile."""
    try:
        names = frappe.get_all("AL Variable Profile", pluck="name") or []
    except Exception:
        print("  · AL Variable Profile: không đọc được, bỏ qua")
        return 0

    changed_profiles = 0
    for name in names:
        try:
            doc = frappe.get_doc("AL Variable Profile", name)
        except frappe.DoesNotExistError:
            continue

        changed_rows = 0
        for row in (doc.get("cross_row") or []):
            fields = _parse_field_list(row.get("fields"))
            if fields is None:
                # Rỗng (hoặc hỏng) = "mọi field vô hướng" / không xác định —
                # ⛔ không tự thêm, tránh biến hành vi "mọi field" thành
                # allowlist chỉ 2 field.
                continue
            added = [f for f in _CROSS_ROW_NEW_FIELDS if f not in fields]
            if not added:
                continue
            fields.extend(added)
            row.fields = json.dumps(fields, ensure_ascii=False)
            changed_rows += 1

        if changed_rows:
            doc.flags.ignore_permissions = True
            doc.save()
            changed_profiles += 1
            print("  · Profile %s: bổ sung cross-row field cho %d dòng"
                  % (name, changed_rows))

    print("  · Profile cross-row: cập nhật %d profile" % changed_profiles)
    return changed_profiles


def execute():
    if not frappe.db.exists("DocType", "AL Variable Settings"):
        frappe.throw(
            "v28_15.sync_variable_sources_and_fields: chưa có doctype 'AL "
            "Variable Settings'. Patch này phải chạy ở [post_model_sync] sau "
            "khi sync doctype — kiểm tra lại alumglass/patches.txt."
        )

    print("v28_15 — đồng bộ nguồn biến + alias độ dày kính")
    _sync_row_literals()
    _sync_profiles()

    # Patch convention của repo: ghi sổ rồi commit ngay (patch runner không
    # tự commit với mọi đường chạy).
    frappe.db.commit()
    print("v28_15 — xong")
