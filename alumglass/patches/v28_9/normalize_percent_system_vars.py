# -*- coding: utf-8 -*-
"""Phase 0b — Chuẩn hoá hệ số % lưu PHẦN TRĂM NGUYÊN (8/12/16/3/3/10).

Trước: system var phần trăm lưu dạng decimal (0.08/0.12/0.16/0.10/0.03/0.03).
Sau:  lưu phần trăm nguyên (8/12/16/10/3/3) — engine `_normalize_percent_inputs`
      chia 100 → 0.08 trước khi dùng. Golden-safe: 8/100 = 0.08 (giá trị không đổi).

Patch idempotent + an toàn mixed-data: chỉ đổi value ≤ 1 (dạng decimal), giữ
nguyên value > 1 (đã là phần trăm nguyên). Chạy lại nhiều lần không ghi đè sai.

Phạm vi:
1. AL Variable Library.default_value (NC_SX_PCT/NC_LD_PCT/PROFIT_MARGIN/VAT_RATE/OH_VC_PCT/OH_QLY_PCT)
2. AL Product Type.nc_pct / nc_ld_rate / profit_margin
3. Formula Global Variable.constant_value (VAT_RATE/OH_VC_PCT/OH_QLY_PCT)
"""
import frappe

# var_name → phần trăm nguyên đích
_PERCENT_VARS = {
    "NC_SX_PCT": 8,
    "NC_LD_PCT": 12,
    "PROFIT_MARGIN": 16,
    "VAT_RATE": 10,
    "OH_VC_PCT": 3,
    "OH_QLY_PCT": 3,
}


def _to_pct(value, expected_pct):
    """Trả phần trăm nguyên nếu value đang là decimal (≤1); giữ nguyên nếu > 1."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if abs(num) <= 1:
        # giữ nguyên type gốc (str cho Data field, số cho Float field)
        return expected_pct if isinstance(value, (int, float)) else str(expected_pct)
    return value


def execute():
    # 1. AL Variable Library.default_value
    for var_name, pct in _PERCENT_VARS.items():
        rows = frappe.get_all(
            "AL Variable Library",
            filters={"var_name": var_name},
            fields=["name", "default_value"])
        for r in rows:
            new_val = _to_pct(r.get("default_value"), pct)
            if new_val != r.get("default_value"):
                frappe.db.set_value(
                    "AL Variable Library", r["name"], "default_value", new_val,
                    update_modified=False)

    # 2. AL Product Type (Float)
    for field, pct in [("nc_pct", 8), ("nc_ld_rate", 12), ("profit_margin", 16)]:
        for pt in frappe.get_all("AL Product Type", fields=["name", field]):
            new_val = _to_pct(pt.get(field), pct)
            if new_val != pt.get(field):
                frappe.db.set_value(
                    "AL Product Type", pt["name"], field, new_val,
                    update_modified=False)

    # 3. Formula Global Variable.constant_value
    for var_name, pct in [("VAT_RATE", 10), ("OH_VC_PCT", 3), ("OH_QLY_PCT", 3)]:
        for gv in frappe.get_all(
                "Formula Global Variable",
                filters={"var_name": var_name},
                fields=["name", "constant_value"]):
            new_val = _to_pct(gv.get("constant_value"), pct)
            if new_val != gv.get("constant_value"):
                frappe.db.set_value(
                    "Formula Global Variable", gv["name"], "constant_value",
                    new_val, update_modified=False)

    frappe.db.commit()
