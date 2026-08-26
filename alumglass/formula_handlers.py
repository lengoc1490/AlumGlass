# -*- coding: utf-8 -*-
"""AlumGlass — Formula Handlers: lookup_calc_pattern HYBRID (DB-first + PATTERN_FORMULAS).

🆕 v28.8 (hướng A — Owner chốt 2026-08-18, job calc-pattern-hybrid-fallback):
- **DB-first**: đọc `calc_fn` từ `AL Quantity Calc Method` record → admin kỹ thuật tự
  thêm pattern mới không cần code.
- **PATTERN_FORMULAS fallback**: 12 pattern built-in + 2 alias legacy
  (AREA≡AREA_M2, LENGTH_ONLY≡LENGTH_M) → Bom Item seed reference AREA/LENGTH_ONLY
  vẫn resolve → zero-risk golden.
- **Negative cache**: code đã xác nhận không có DB record → không query lại DB mỗi lần.
- **Bảo mật**: nhánh DB GIỮ `compile_expression` (safe_eval của formula_builder) — KHÔNG
  dùng `eval(..., {"__builtins__": {}})` (sandbox myth, bị escape bởi
  `().__class__.__base__.__subclasses__()`). `_validate_calc_fn` (AST whitelist) là
  defense-in-depth khi lưu record.

Module path: `alumglass.formula_handlers`. `al_quantity_calc_method.py` re-export từ đây
để giữ nguyên import path trong `bom_orchestrator.py` (B4 dòng 814 / B6 dòng 989).
"""
import ast

import frappe
from formula_builder.security.safe_eval import ExpressionPolicy, compile_expression


# ──────────────────────────────────────────────────────────
# 14 PATTERN BUILT-IN (12 spec + 2 alias legacy)
# ──────────────────────────────────────────────────────────
PATTERN_FORMULAS = {
    # Nhóm A — Tuyến tính
    "LENGTH_TO_WEIGHT": lambda w, h, tlr, **kw: (w / 1000) * tlr,
    "LENGTH_M":         lambda w, h, tlr, **kw: w / 1000,
    "HEIGHT_M":         lambda w, h, tlr, **kw: h / 1000,
    "LENGTH_TO_PIECES": lambda w, h, tlr, **kw: (w / 1000) / kw.get("piece_length", 1),
    # Nhóm B — Diện tích
    "AREA_M2":          lambda w, h, tlr, **kw: (w / 1000) * (h / 1000),
    "AREA_TO_WEIGHT":   lambda w, h, tlr, **kw: (w / 1000) * (h / 1000) * tlr,
    # Nhóm C — Chu vi
    "PERIMETER_M":      lambda w, h, tlr, **kw: 2 * (w + h) / 1000,
    # Nhóm D — Thể tích
    "VOLUME_M3":        lambda w, h, tlr, **kw: (w / 1000) * (h / 1000) * kw.get("depth", 0) / 1000,
    # Nhóm E — Đếm / Bộ
    "COUNT":            lambda w, h, tlr, **kw: 1,
    "SET":              lambda w, h, tlr, **kw: 1,
    "COUNT_PER_LENGTH": lambda w, h, tlr, **kw: (w / 1000) / kw.get("spacing", 1),
    "COUNT_PER_AREA":   lambda w, h, tlr, **kw: (w / 1000) * (h / 1000) / kw.get("area_per_piece", 1),
    # Alias legacy (seed cũ dùng) — map về pattern spec, GIÁ TRỊ NHẬN BIẾT
    "AREA":             lambda w, h, tlr, **kw: (w / 1000) * (h / 1000),
    "LENGTH_ONLY":      lambda w, h, tlr, **kw: w / 1000,
}

# Nhóm hiển thị (group) fallback khi record DB chưa điền field `group` (Phase 2).
# Matrix v28.md §C.4 (Phase 1a): A-Tuyến tính / B-Diện tích / C-Chu vi / D-Thể tích / E-Đếm.
_GROUP_BY_KEY = {
    "LENGTH_TO_WEIGHT": "A-Tuyến tính",
    "LENGTH_M":         "A-Tuyến tính",
    "HEIGHT_M":         "A-Tuyến tính",
    "LENGTH_TO_PIECES": "A-Tuyến tính",
    "LENGTH_ONLY":      "A-Tuyến tính",
    "AREA_M2":          "B-Diện tích",
    "AREA_TO_WEIGHT":   "B-Diện tích",
    "AREA":             "B-Diện tích",
    "PERIMETER_M":      "C-Chu vi",
    "VOLUME_M3":        "D-Thể tích",
    "COUNT":            "E-Đếm",
    "SET":              "E-Đếm",
    "COUNT_PER_LENGTH": "E-Đếm",
    "COUNT_PER_AREA":   "E-Đếm",
}

# Hàm được phép gọi trong body calc_fn (backward-compat với namespace cũ).
_CALC_ALLOWED_FUNCTIONS = ("abs", "min", "max", "round")

# Policy compile riêng cho calc_fn: cho phép kw.get(...) (method call qua attribute
# không-dunder). Vì sao cần: PATTERN_FORMULAS spec dùng `kw.get("depth", 0)` — nếu giữ
# DEFAULT_POLICY (forbid_method_calls=True) thì body chứa kw.get bị ValueError khi
# compile → DB-first path vỡ cho pattern kw-based (VOLUME_M3, LENGTH_TO_PIECES, ...).
# An toàn: vẫn chặn dunder attribute (allowed_attributes=None → mọi attr bắt đầu "__"
# bị từ chối), vẫn chặn FORBIDDEN_NAMES (import/open/getattr/os/sys/...), vẫn giới hạn
# allowed_functions. Scope chỉ chứa data value (w/h/tlr/extra_vars/kw) — method call
# trên chúng là an toàn.
_CALC_EXPRESSION_POLICY = ExpressionPolicy(
    allow_attribute=True,
    forbid_method_calls=False,
    allowed_functions=_CALC_ALLOWED_FUNCTIONS,
)

# Cache pattern đã compile từ DB (positive) + negative cache (không có DB record).
_DB_PATTERN_CACHE = {}      # code -> SafeExpression (positive)
_NEGATIVE_CACHE = set()     # code đã xác nhận không có DB record (tránh query lại)


# ──────────────────────────────────────────────────────────
# _compile_calc_fn — compile chuỗi lambda an toàn (safe_eval)
# ──────────────────────────────────────────────────────────
def _compile_calc_fn(fn_str):
    """Compile calc_fn (chuỗi lambda từ DB) → SafeExpression của FB safe_eval.

    Giữ backward-compat: calc_fn trong DB vẫn là chuỗi lambda
    ("lambda w,h,tlr,**kw: ..."). Parse AST → lấy body expression → compile
    an toàn (FB chặn Lambda node → không truyền thẳng chuỗi lambda vào
    compile_expression).

    Raises:
        ValueError: nếu calc_fn không phải lambda hoặc body chứa cấu trúc
        không cho phép (import / lambda lồng / dunder attr / getattr / ...).
    """
    fn_str = (fn_str or "").strip()
    if not fn_str:
        raise ValueError("calc_fn rỗng")
    try:
        tree = ast.parse(fn_str, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"calc_fn không phải biểu thức hợp lệ: {e.msg}") from e
    if not isinstance(tree.body, ast.Lambda):
        raise ValueError(
            f"calc_fn phải là lambda, nhận: {type(tree.body).__name__}"
        )
    body_source = ast.unparse(tree.body.body)
    return compile_expression(
        body_source,
        allowed_functions=_CALC_ALLOWED_FUNCTIONS,
        policy=_CALC_EXPRESSION_POLICY,
    )


# ──────────────────────────────────────────────────────────
# _validate_calc_fn — AST whitelist (defense-in-depth khi lưu)
# ──────────────────────────────────────────────────────────
def _validate_calc_fn(calc_fn_text):
    """Validate calc_fn trước khi lưu — chỉ cho phép lambda với phép toán cơ bản.

    Được gọi từ validate hook của AL Quantity Calc Method DocType.
    Chỉ cho phép: lambda (1 tầng), w, h, tlr, kw, số, +, -, *, /, **, (), kw.get()
    Từ chối: import, exec, eval, getattr, open, lambda lồng, dunder attribute,
    os, sys, subprocess...

    Args:
        calc_fn_text: chuỗi lambda từ form. Rỗng → OK (sẽ dùng fallback PATTERN_FORMULAS).

    Raises:
        frappe.ValidationError: nếu calc_fn chứa cấu trúc/name không được phép.
    """
    if not calc_fn_text or not calc_fn_text.strip():
        return  # empty is OK — will use fallback

    if not calc_fn_text.strip().startswith("lambda"):
        frappe.throw(
            "calc_fn phải bắt đầu bằng 'lambda'. "
            "Ví dụ: lambda w, h, tlr, **kw: (w/1000) * tlr"
        )

    # Parse AST để kiểm tra cấu trúc
    try:
        tree = ast.parse(calc_fn_text.strip(), mode="eval")
    except SyntaxError as e:
        frappe.throw(f"calc_fn có lỗi cú pháp Python: {e}")

    # Walk AST — chỉ cho phép các node an toàn (copy spec v28.md C.4.1).
    ALLOWED_NODES = {
        ast.Lambda, ast.arguments, ast.arg, ast.BinOp, ast.UnaryOp,
        ast.Mult, ast.Div, ast.Add, ast.Sub, ast.Pow,
        ast.Num, ast.Constant, ast.Name, ast.Load, ast.Call,
        ast.Attribute, ast.keyword, ast.Expression, ast.Dict,
        ast.Subscript, ast.Index, ast.Slice, ast.Tuple, ast.List,
        ast.USub, ast.UAdd, ast.And, ast.Or, ast.Compare,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.IfExp, ast.Is, ast.IsNot,
    }
    FORBIDDEN_NAMES = {
        "exec", "eval", "compile", "__import__", "open", "file",
        "input", "raw_input", "getattr", "setattr", "delattr",
        "hasattr", "__builtins__", "__builtin__", "__dict__",
        "__class__", "__bases__", "__subclasses__", "__globals__",
        "__code__", "__closure__", "os", "sys", "subprocess",
        "shutil", "importlib", "builtins",
    }
    ALLOWED_NAMES = {"w", "h", "tlr", "kw", "True", "False", "None"}

    lambda_count = 0
    for node in ast.walk(tree):
        # Chỉ cho phép ĐÚNG 1 lambda (node gốc). Lambda lồng trong body bị chặn.
        if isinstance(node, ast.Lambda):
            lambda_count += 1
        if type(node) not in ALLOWED_NODES:
            frappe.throw(
                f"calc_fn chứa cấu trúc không được phép: {type(node).__name__}. "
                f"Chỉ được dùng phép toán cơ bản (+, -, *, /, **) và kw.get()."
            )
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                frappe.throw(f"calc_fn chứa tên hàm bị cấm: '{node.id}'")
            if node.id not in ALLOWED_NAMES and not node.id.startswith("_"):
                frappe.throw(
                    f"calc_fn chứa biến không được phép: '{node.id}'. "
                    f"Chỉ được dùng: w, h, tlr, kw"
                )
        # Dunder attribute (obj.__class__) luôn cấm — defense-in-depth ngoài FB.
        if isinstance(node, ast.Attribute) and getattr(node, "attr", "").startswith("__"):
            frappe.throw(
                f"calc_fn chứa truy cập thuộc tính dunder bị cấm: '{node.attr}'"
            )
    if lambda_count > 1:
        frappe.throw("calc_fn không được chứa lambda lồng bên trong body")


# ──────────────────────────────────────────────────────────
# lookup_calc_pattern — HYBRID: cache → DB → PATTERN_FORMULAS → ValueError
# ──────────────────────────────────────────────────────────
def lookup_calc_pattern(calc_pattern_code, width=None, height=None,
                        weight_per_unit=None, extra_vars=None, **extra_kwargs):
    """Tính số lượng đơn vị theo pattern — HYBRID DB-first + PATTERN_FORMULAS fallback.

    Thứ tự: cache (positive) → DB → PATTERN_FORMULAS → ValueError.
    Negative cache để không query DB lại mỗi lần cho code không có record.

    Args:
        calc_pattern_code: pattern code (vd: LENGTH_TO_WEIGHT, AREA_M2)
        width: mm
        height: mm
        weight_per_unit: kg/m (cho LENGTH_TO_WEIGHT)
        extra_vars: dict biến phụ (VD {'depth': 50}) — Formula Builder
            normalize_formula chuyển mọi '=' thành '==' nên KHÔNG dùng được
            keyword args trong formula → truyền dict positional (V6 Phase 1d).
        **extra_kwargs: tham số mở rộng (backward-compat — call trực tiếp
            Python vẫn dùng keyword như cũ: depth=50)

    Returns:
        số lượng đơn vị (float).

    Raises:
        ValueError: nếu pattern không có DB record lẫn built-in.
    """
    code = calc_pattern_code
    # Merge extra_vars (dict positional từ formula) vào kwargs
    extra_vars = extra_vars or {}
    if isinstance(extra_vars, dict):
        for k, v in extra_vars.items():
            extra_kwargs.setdefault(k, v)
    # 1. Cache positive
    if code in _DB_PATTERN_CACHE:
        expr = _DB_PATTERN_CACHE[code]
    elif code in _NEGATIVE_CACHE:
        expr = None
    else:
        # 2. DB-first — get_value trả None nếu record không tồn tại hoặc calc_fn null.
        #    calc_fn rỗng thì coi như không có → fallback. (KHÔNG dùng frappe.db.exists —
        #    tiết kiệm 1 query, tương thích frappe stub của test_safe_eval_a3.)
        fn_str = frappe.db.get_value("AL Quantity Calc Method", code, "calc_fn")
        if fn_str and fn_str.strip():
            expr = _compile_calc_fn(fn_str)          # compile_expression (safe_eval), KHÔNG eval
            _DB_PATTERN_CACHE[code] = expr
        else:
            _NEGATIVE_CACHE.add(code)
            expr = None
    # 3. Fallback PATTERN_FORMULAS (built-in code)
    if expr is None:
        builtin = PATTERN_FORMULAS.get(code)
        if builtin is not None:
            w, h, tlr = (width or 0), (height or 0), (weight_per_unit or 0)
            return builtin(w, h, tlr, **extra_vars)
        raise ValueError(
            f"Unknown calc pattern: '{code}'. Available: "
            f"{', '.join(sorted(set(PATTERN_FORMULAS) | set(_DB_PATTERN_CACHE)))}. "
            f"Tạo record AL Quantity Calc Method hoặc liên hệ DEV thêm PATTERN_FORMULAS."
        )
    # eval qua safe_eval scope (giống code hiện tại)
    scope = {"w": width, "h": height, "tlr": weight_per_unit,
             "abs": abs, "min": min, "max": max, "round": round}
    scope.update(extra_kwargs)                  # tương đương **kw của lambda cũ (name trực tiếp)
    scope["kw"] = dict(extra_kwargs)            # kw.get('depth', 0) — **kw của lambda spec
    return expr.eval(scope)


# ──────────────────────────────────────────────────────────
# get_available_patterns — filter A (attribute-derived) + B (group)
# ──────────────────────────────────────────────────────────
def _derive_pattern_filter(cat_doc):
    """Derive set calc_pattern cho phép từ attributes AL Material Category.

    Quy tắc (spec Phase 5 — KHÔNG child doctype, chỉ đọc flags có sẵn):
      - has_weight          → nhóm weight (LENGTH_TO_WEIGHT, AREA_TO_WEIGHT, VOLUME_M3)
      - has_dimensions & !weight → (AREA/AREA_M2, LENGTH_ONLY/LENGTH_M, PERIMETER_M)
      - requires_glass_master → AREA/AREA_M2
      - !has_dimensions     → (COUNT, SET)
    """
    allowed = set()
    has_weight = cat_doc.get("has_weight")
    has_dimensions = cat_doc.get("has_dimensions")
    if has_weight:
        allowed |= {"LENGTH_TO_WEIGHT", "AREA_TO_WEIGHT", "VOLUME_M3"}
    elif has_dimensions:  # has_dimensions và không weight
        allowed |= {"AREA", "AREA_M2", "LENGTH_ONLY", "LENGTH_M", "PERIMETER_M"}
    if cat_doc.get("requires_glass_master"):
        allowed |= {"AREA", "AREA_M2"}
    if not has_dimensions:
        allowed |= {"COUNT", "SET"}
    return allowed


def get_available_patterns(category_code=None):
    """Trả về pattern khả dụng cho UI dropdown (Bom Item `calc_pattern`).

    - Pool = record DB (AL Quantity Calc Method) + PATTERN_FORMULAS, dedup, sort.
    - Filter A: nếu truyền `category_code`, derive set pattern theo attributes
      AL Material Category (`has_weight` / `has_dimensions` / `requires_glass_master`).
    - Filter B: gắn `group` (Tuyến tính/Diện tích/Chu vi/Thể tích/Đếm-Bộ) từ field
      `group` của DB hoặc map theo key pattern.

    Returns:
        list[dict]: {calc_pattern_code, calc_pattern_name, group, output_unit, sort_order}
    """
    patterns = []
    seen = set()

    # Từ DB
    for p in frappe.get_all(
        "AL Quantity Calc Method",
        fields=["calc_pattern_code", "calc_pattern_name", "group",
                "output_unit", "sort_order"],
        order_by="sort_order",
    ):
        code = p["calc_pattern_code"]
        if code in seen:
            continue
        patterns.append({
            "calc_pattern_code": code,
            "calc_pattern_name": p["calc_pattern_name"] or code,
            "group": p.get("group") or _GROUP_BY_KEY.get(code, ""),
            "output_unit": p.get("output_unit") or "",
            "sort_order": p.get("sort_order") or 0,
        })
        seen.add(code)

    # Từ PATTERN_FORMULAS (built-in chưa có DB record)
    for code in sorted(PATTERN_FORMULAS.keys()):
        if code in seen:
            continue
        patterns.append({
            "calc_pattern_code": code,
            "calc_pattern_name": code,
            "group": _GROUP_BY_KEY.get(code, ""),
            "output_unit": "",
            "sort_order": 99,
        })
        seen.add(code)

    # Filter A — attribute-derived theo category
    if category_code:
        cat_doc = frappe.get_cached_doc("AL Material Category", category_code)
        allowed = _derive_pattern_filter(cat_doc)
        if allowed:
            patterns = [p for p in patterns if p["calc_pattern_code"] in allowed]

    # Sort: sort_order ASC, rồi theo code (ổn định cho dropdown).
    patterns.sort(key=lambda p: (p["sort_order"], p["calc_pattern_code"]))
    return patterns


# ──────────────────────────────────────────────────────────
# clear_calc_fn_cache
# ──────────────────────────────────────────────────────────
def clear_calc_fn_cache():
    """Clear cả 2 cache (positive + negative) — gọi khi AL Quantity Calc Method đổi."""
    _DB_PATTERN_CACHE.clear()
    _NEGATIVE_CACHE.clear()
