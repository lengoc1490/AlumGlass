# -*- coding: utf-8 -*-
"""D3 — Seed Formula Variable Binding (FVB) từ AL Variable Library + Formula Global Variable.

Bật FB-max (B1.4 `_resolve_fb_context`) mà KHÔNG đụng engine: engine đã có sẵn
luồng merge FVB → Variable Library (fallback). Patch này tạo FVB records để
`get_live_context` resolve được global constant + system variable.

2 nhóm binding được seed (data-driven — đọc từ master data HIỆN TẠI):

Group 1 — GLOBAL CONSTANT (is_global=1, applies_to_doctype=""):
    Từ Formula Global Variable (is_active=1, value_source="CONSTANT", var_type
    số). Source = "constant", source_config={"value": constant_value}.
    → resolve được ở MỌI scope (quotation item, bom set, ...).

Group 2 — SYSTEM VARIABLE từ AL Variable Library (is_system=1) có
    source_doctype + source_field:
    - AL Profile System → link_field="profile_system" (OFFSET_FRAME, OFFSET_GLASS,
      OFFSET_FIXED, OFFSET_DO_NGANG)
    - AL Product Type  → link_field="product_type"  (NC_SX_PCT, NC_LD_PCT,
      PROFIT_MARGIN)
    Source = "linked_doctype_field", source_config={"link_field", "target_doctype",
    "target_field"}, applies_to_doctype="AL Bom Set" — vì AL Bom Set là doc duy
    nhất trong chuỗi Quotation Item → AL BOM → AL BOM Version → AL BOM → AL Bom Set
    có link trực tiếp tới Profile System / Product Type (engine D3 đã đổi scope
    `_resolve_fb_context` sang "AL Bom Set"). KHÔNG dùng scope "Quotation Item"
    vì Quotation Item không có link tới 2 doctype này.

QUYẾT ĐỊNH default_value (ghi nhận trong docs/design/fvb-seed.md):
    - Group 1: default_value = constant_value (giống value resolve được).
    - Group 2: default_value = default_value từ Variable Library (đúng chữ spec
      "default_value từ Variable Library"). Với OFFSET_* đây là "" — engine
      `_resolve_fb_context` (sửa cùng job D3) bỏ qua chuỗi rỗng + scope AL Bom
      Set resolve được link thật → không override giá trị thật từ 1.3.

BACKWARD-COMPAT: Variable Library vẫn là fallback. Nếu một system var KHÔNG có
FVB tương ứng (vd source_doctype khác 2 doctype trên, hoặc bị bỏ qua) → engine
1.3 `_resolve_system_variables` vẫn resolve như cũ. Golden 2C (22,717,289) / 4C
(47,430,808) không đổi.

Idempotent: check tồn tại theo (variable_name, applies_to_doctype, is_global)
trước khi insert; wrap try/except từng record; commit 1 lần cuối.
"""

import frappe

# ── nguồn resolve hợp lệ cho system var ở scope AL Bom Set ──────────────
_LINK_BY_SOURCE_DOCTYPE = {
    "AL Profile System": "profile_system",
    "AL Product Type": "product_type",
}

# map var_type AL Variable Library → data_type Formula Variable Binding
_DTYPE_MAP = {
    "Float": "Float",
    "Int": "Int",
    "Currency": "Currency",
    "Check": "Check",
    "Data": "Data",
    "Select": "Data",
    "Link": "Data",
}

# data_type chỉ seed cho global constant dạng số
_NUMERIC_DTYPES = ("Float", "Int", "Currency", "Percent")


def _binding_exists(variable_name, applies_to_doctype, is_global):
    return frappe.db.exists("Formula Variable Binding", {
        "variable_name": variable_name,
        "applies_to_doctype": applies_to_doctype or "",
        "is_global": 1 if is_global else 0,
    })


def _insert(variable_name, variable_label, source_type, source_config,
            applies_to_doctype, data_type, default_value, is_global):
    """Insert 1 FVB nếu chưa tồn tại (idempotent)."""
    if _binding_exists(variable_name, applies_to_doctype, is_global):
        return False
    try:
        frappe.get_doc({
            "doctype": "Formula Variable Binding",
            "variable_name": variable_name,
            "variable_label": variable_label or variable_name,
            "source_type": source_type,
            "source_config": frappe.as_json(source_config),
            "resolve_priority": 100,
            "batch_group": "",
            "applies_to_doctype": applies_to_doctype or "",
            "applies_to_field": "",
            "data_type": data_type,
            "default_value": default_value if default_value is not None else "",
            "is_global": 1 if is_global else 0,
            "is_active": 1,
        }).insert(ignore_permissions=True, ignore_mandatory=True)
        return True
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "AlumGlass D3: seed FVB thất bại %s (%s)" % (variable_name, applies_to_doctype),
        )
        return False


def execute():
    created = 0
    skipped = 0

    # ── Group 1 — Global constant từ Formula Global Variable ───────────
    globals_ = frappe.get_all(
        "Formula Global Variable",
        filters={"is_active": 1, "value_source": "CONSTANT"},
        fields=["var_name", "label", "var_type", "constant_value"],
    ) or []
    for gv in globals_:
        var_name = gv.get("var_name")
        if not var_name:
            skipped += 1
            continue
        dtype = gv.get("var_type") or "Float"
        if dtype not in _NUMERIC_DTYPES:
            skipped += 1
            continue
        cval = gv.get("constant_value")
        if cval is None or str(cval).strip() == "":
            skipped += 1
            continue
        if _insert(
            var_name,
            gv.get("label") or var_name,
            "constant",
            {"value": cval},
            "",
            dtype,
            cval,
            True,  # is_global
        ):
            created += 1
        else:
            skipped += 1

    # ── Group 2 — System variable từ AL Variable Library ───────────────
    system_vars = frappe.get_all(
        "AL Variable Library",
        filters={"is_system": 1},
        fields=["var_name", "var_label", "var_type",
                "source_doctype", "source_field", "default_value"],
    ) or []
    for sv in system_vars:
        var_name = sv.get("var_name")
        source_doctype = sv.get("source_doctype") or ""
        source_field = sv.get("source_field") or ""
        if not var_name or not source_field:
            skipped += 1
            continue
        link_field = _LINK_BY_SOURCE_DOCTYPE.get(source_doctype)
        if not link_field:
            # system var nguồn khác (chưa có doc trung gian) → KHÔNG seed FVB,
            # engine 1.3 vẫn fallback Variable Library như cũ (backward-compat).
            skipped += 1
            continue
        dtype = _DTYPE_MAP.get(sv.get("var_type") or "Float", "Float")
        if _insert(
            var_name,
            sv.get("var_label") or var_name,
            "linked_doctype_field",
            {
                "link_field": link_field,
                "target_doctype": source_doctype,
                "target_field": source_field,
            },
            "AL Bom Set",
            dtype,
            sv.get("default_value"),
            False,  # is_global
        ):
            created += 1
        else:
            skipped += 1

    frappe.db.commit()
    frappe.logger("alumglass").info(
        "D3 seed_fvb_from_variable_library: created %d FVB, skipped %d."
        % (created, skipped)
    )
