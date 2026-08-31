# -*- coding: utf-8 -*-
"""Validate công thức DÙNG CHUNG cho mọi doctype có field Formula Builder
(Small Text). Trước bản vá này, AL Cost Template validate CÔNG THỨC RIÊNG
(viết tay trong al_cost_template.py) — module này tách ra để tái dùng cho
AL Bom Set/AL Bom Item, AL Accessory Set/Item, AL Alert Config, v.v. mà
KHÔNG copy lại logic.

⚠ Cross-row `items.slug.field`: FormulaValidator (formula_builder/formula_utils/
security.py) CHẶN mọi truy cập `.attr` không nằm trong whitelist
{'get','keys','values','items','to_dict'} — `.slug`/`.field` KHÔNG được phép.
Engine thật (bom_orchestrator._normalize_items_ref, FormulaEngineCore) luôn
normalize `items.slug.field` → `slug__field` (namespace FLAT) TRƯỚC khi
validate/compile. Module này bắt buộc làm y hệt — dùng chung
formula_builder.table_formula_builder.normalize_global, không tự viết lại.
"""
import frappe
from formula_builder.formula_utils import BASE_FUNCS, FormulaValidator

# Hàm custom alumglass inject qua FlexibleFormulaEngine/FormulaEngine
# custom_functions — PHẢI đồng bộ tay với:
#   - bom_orchestrator.py (SAFE FUNCS dùng chung B4+B6, đầu file)
#   - public/js/cost_template.js -> customFns (fetch động qua
#     alumglass.api.get_allowed_formula_functions, xem api/__init__.py)
ALUMGLASS_CUSTOM_FUNCS = frozenset({"lookup_rule", "lookup_calc_pattern", "roundup"})
VALIDATOR_ALLOWED_FUNCS = frozenset(set(BASE_FUNCS.keys()) | ALUMGLASS_CUSTOM_FUNCS)


def normalize_cross_row(expr):
    """items.slug.field -> slug__field — DÙNG ĐÚNG hàm engine thật dùng
    (formula_builder.table_formula_builder.normalize_global), fallback regex
    y hệt bom_orchestrator._normalize_items_ref nếu import lỗi.
    """
    if not expr or "items." not in expr:
        return expr
    try:
        from formula_builder.table_formula_builder import normalize_global
        return normalize_global(expr)
    except Exception:
        import re
        return re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)


def build_known_names(doctype, docname, cross_row_slugs=None, cross_row_fields=None):
    """Universe biến hợp lệ cho 1 doctype/record.

    - Nguồn chính: get_formula_context(doctype, docname) — Cost Bucket,
      System/User Var, Formula Global Var, Row Literals, FVB binding...
      (KHÔNG hardcode biến nào, xem alumglass/api/__init__.py).
    - cross_row_slugs / cross_row_fields (optional): nếu doctype có
      cross-row reference kiểu `items.slug.field` (vd AL Bom Set), truyền
      vào để bổ sung {slug}__{field} — CHÍNH XÁC namespace FLAT mà
      FormulaEngineCore dùng lúc chạy thật. Không truyền = doctype không
      có cross-row (vd AL Cost Template, AL Alert Config, AL Accessory Set).
    """
    try:
        from alumglass.api import get_formula_context
        ctx = get_formula_context(doctype, docname)
        names = {v["name"] for v in (ctx.get("variables") or []) if v.get("name")}
    except Exception as exc:
        frappe.log_error(
            f"{doctype} validate: lỗi build known_names — {exc}",
            "AlumGlass Formula Validate",
        )
        names = set()

    if cross_row_slugs and cross_row_fields:
        for slug in cross_row_slugs:
            if not slug:
                continue
            for field in cross_row_fields:
                names.add(f"{slug}__{field}")

    return names


def check_formula(formula, known_names, label="", allow_cross_row=False,
                   extra_known_names=None):
    """Validate 1 công thức. Trả về list[str] lỗi (rỗng = hợp lệ).

    KHÔNG tự throw — caller quyết định frappe.throw()/msgprint() theo bảng
    "chặn cứng hay chỉ cảnh báo" (xem HUONG_DAN_INJECT_VALIDATE.md mục 3.4).
    """
    formula = (formula or "").strip()
    if not formula:
        return []  # rỗng: field-required tự lo riêng (không phải việc của validator công thức)

    expr = normalize_cross_row(formula) if allow_cross_row else formula

    names = set(known_names)
    if extra_known_names:
        names |= set(extra_known_names)

    validator = FormulaValidator(allowed_functions=VALIDATOR_ALLOWED_FUNCS)
    result = validator.validate(expr, known_names=names)
    if result.errors:
        prefix = f"{label}: " if label else ""
        return [f"{prefix}{e}" for e in result.errors]
    return []


def check_formula_fields(row_or_doc, fields, known_names, allow_cross_row=False,
                          extra_known_names=None):
    """Validate nhiều field công thức trên CÙNG 1 row/doc. Trả list[str] lỗi."""
    errors = []
    for fn in fields:
        formula = row_or_doc.get(fn)
        errs = check_formula(formula, known_names, label=fn,
                              allow_cross_row=allow_cross_row,
                              extra_known_names=extra_known_names)
        errors.extend(errs)
    return errors
