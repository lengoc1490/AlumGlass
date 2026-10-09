# -*- coding: utf-8 -*-
"""F19 — Sửa công thức chia-cho-0 của seed (n_panel = 0 ⇒ chết cả BOM).

Hai nhóm công thức cùng một lỗi "chia trần chưa chốt chia-cho-0":
  A. DON_GIA_M2 = "GIA_BAN / TONG_M2" — TONG_M2 = (W_mm/1000)*(H_mm/1000)
     ⇒ W hoặc H = 0 thì TONG_M2 = 0 ⇒ FormulaZeroDivisionError giết cả lượt
     tính BOM (xem comment bom_orchestrator b4: "Div-by-zero vẫn fatal
     (errors.py)").
  B. Chiều ngang cánh/kính = "W_mm/n_panel - OFFSET_*" — n_panel là Int reqd,
     Frappe coi 0 là hợp lệ nên người dùng gõ 0 là qua cửa ⇒ chia-cho-0.

Seed có guard `if _ex(...): return` ở _cost_template/_bom_items_and_set/
_bom_items_and_set_4c ⇒ sửa seed KHÔNG sửa được bản đã nạp vào DB ⇒ cần patch.

Mỗi nhóm công thức được lưu ở 2 chỗ, sửa CẢ HAI thì mới hết bệnh:
  A. DON_GIA_M2:
     1. Bảng con `AL Cost Template Item.calc_formula` (template sống) — là
        nguồn snapshot khi tạo AL BOM Version mới.
     2. `AL BOM Version.cost_template_snapshot` (bản snapshot B6 THỰC SỰ đọc
        khi tính giá — `b6_calculate_cost_template` dùng snapshot của version,
        KHÔNG đọc template sống trừ khi có `_cost_template` override).
  B. Chiều ngang cánh/kính:
     1. Bảng con `AL Bom Item.width` (Bom Set sống).
     2. `AL BOM Version.bom_set_snapshot` (JSON) — dòng con giữ công thức ở
        `items[].width` (xem al_bom_version._snapshot_item_row: meta-driven
        chụp mọi field dữ liệu của AL Bom Item).

CHỈ thay khi công thức khớp CHÍNH XÁC mẫu cũ sau khi chuẩn hoá khoảng trắng.
Công thức đã bị người dùng sửa tay ⇒ bỏ qua, không đụng (cả bảng con lẫn
snapshot).

Idempotent: chạy lại nhiều lần không ghi đè gì thêm (công thức đã đổi rồi thì
không còn khớp mẫu cũ). Không frappe.db.commit() — Frappe patch runner tự
commit.
"""
import json

import frappe

# ── Nhóm A — DON_GIA_M2 ────────────────────────────────────────────────
_OLD_CT = "GIA_BAN / TONG_M2"
_NEW_CT = "safe_div(GIA_BAN, TONG_M2, 0)"

# ── Nhóm B — chiều ngang cánh/kính (W_mm/n_panel ⇒ n_panel = 0 chết) ────
_OLD_W_FRAME = "W_mm/n_panel - OFFSET_FRAME"
_NEW_W_FRAME = "safe_div(W_mm, n_panel, 0) - OFFSET_FRAME"
_OLD_W_GLASS = "W_mm/n_panel - OFFSET_GLASS"
_NEW_W_GLASS = "safe_div(W_mm, n_panel, 0) - OFFSET_GLASS"

# Bảng ánh xạ cũ → mới cho field width của AL Bom Item / bom_set_snapshot
_WIDTH_FIXES = (
    (_OLD_W_FRAME, _NEW_W_FRAME),
    (_OLD_W_GLASS, _NEW_W_GLASS),
)


def _norm(s):
    """Chuẩn hoá khoảng trắng để so khớp chính xác mẫu cũ."""
    return " ".join((s or "").split())


def _fix_width(value):
    """Trả về (giá_trị_mới, có_khớp) — chỉ khớp khi bằng CHÍNH XÁC mẫu cũ."""
    nv = _norm(value)
    for old, new in _WIDTH_FIXES:
        if nv == _norm(old):
            return new, True
    return value, False


def execute():
    tpl_changed = 0

    # ── A1. Sửa bảng con AL Cost Template Item — mọi template, không chỉ
    # CT-01-STANDARD.
    rows = frappe.get_all(
        "AL Cost Template Item",
        filters={"parenttype": "AL Cost Template"},
        fields=["name", "parent", "calc_formula"],
    )
    for row in rows:
        if _norm(row.get("calc_formula")) == _norm(_OLD_CT):
            frappe.db.set_value(
                "AL Cost Template Item", row["name"], "calc_formula", _NEW_CT)
            tpl_changed += 1

    # ── A2. Sửa snapshot cost template trong AL BOM Version — đường B6 thực
    # sự đọc. Chỉ sửa TỪNG dòng khớp mẫu cũ (giữ nguyên mọi dòng khác + mọi
    # field khác của snapshot) — không re-backfill toàn bộ từ template sống
    # như v28_10/v28_11 vì ở đây chỉ cần vá đúng 1 công thức, và tôn trọng
    # "đã sửa tay thì bỏ qua".
    ct_snap_changed = 0
    versions = frappe.get_all(
        "AL BOM Version",
        filters={"workflow_state": "Published"},
        fields=["name", "cost_template_snapshot"],
    )
    for v in versions:
        raw = v.get("cost_template_snapshot")
        if not raw:
            continue
        try:
            snap = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            continue
        if not isinstance(snap, dict):
            continue
        items = snap.get("items")
        if not isinstance(items, list):
            continue
        dirty = False
        for item in items:
            if not isinstance(item, dict):
                continue
            if _norm(item.get("calc_formula")) == _norm(_OLD_CT):
                item["calc_formula"] = _NEW_CT
                dirty = True
        if dirty:
            # db.set_value ghi thẳng DB (giống v28_10/v28_11) — không đi qua
            # validate nên không vướng _guard_published_immutability. Đây là
            # backfill cố ý để vá lỗi, không phải sửa snapshot nghiệp vụ.
            frappe.db.set_value(
                "AL BOM Version", v["name"],
                "cost_template_snapshot", json.dumps(snap, indent=2),
                update_modified=False,
            )
            ct_snap_changed += 1

    # ── B1. Sửa bảng con AL Bom Item (Bom Set sống) — field width.
    bom_item_changed = 0
    rows = frappe.get_all(
        "AL Bom Item",
        filters={"parenttype": "AL Bom Set"},
        fields=["name", "parent", "width"],
    )
    for row in rows:
        new_val, matched = _fix_width(row.get("width"))
        if matched:
            frappe.db.set_value("AL Bom Item", row["name"], "width", new_val)
            bom_item_changed += 1

    # ── B2. Sửa bom_set_snapshot trong AL BOM Version (JSON, items[].width).
    # Chỉ sửa TỪNG dòng khớp mẫu cũ — giữ nguyên mọi dòng khác + mọi field
    # khác của snapshot (không re-backfill, không ghi đè bản sửa tay).
    bom_snap_changed = 0
    versions = frappe.get_all(
        "AL BOM Version",
        filters={"workflow_state": "Published"},
        fields=["name", "bom_set_snapshot"],
    )
    for v in versions:
        raw = v.get("bom_set_snapshot")
        if not raw:
            continue
        try:
            snap = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            continue
        if not isinstance(snap, dict):
            continue
        items = snap.get("items")
        if not isinstance(items, list):
            continue
        dirty = False
        for item in items:
            if not isinstance(item, dict):
                continue
            new_val, matched = _fix_width(item.get("width"))
            if matched:
                item["width"] = new_val
                dirty = True
        if dirty:
            # Ghi thẳng DB như v28_10/v28_11 — không đi qua validate nên
            # không vướng _guard_published_immutability. Backfill cố ý để vá
            # lỗi, không phải sửa snapshot nghiệp vụ.
            frappe.db.set_value(
                "AL BOM Version", v["name"],
                "bom_set_snapshot", json.dumps(snap, indent=2),
                update_modified=False,
            )
            bom_snap_changed += 1

    frappe.logger("alumglass").info(
        "F19 fix_cost_template_div_by_zero: %d cost template dòng, "
        "%d cost snapshot, %d bom item width, %d bom snapshot sửa"
        % (tpl_changed, ct_snap_changed, bom_item_changed, bom_snap_changed))
    print("fix_cost_template_div_by_zero: %d cost template dòng, "
          "%d cost snapshot, %d bom item width, %d bom snapshot sửa"
          % (tpl_changed, ct_snap_changed, bom_item_changed, bom_snap_changed))
