# -*- coding: utf-8 -*-
"""
A3a + A4 — RCE fix (import FB safe_eval) + register_source 3 handler.

CÁCH CHẠY
---------
Không cần site:
    python3 -m pytest alumglass/tests/test_safe_eval_a3.py -v
    (tự stub frappe nếu chạy standalone)

Hoặc qua bench (khi site đã có, sau A1):
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_safe_eval_a3
"""
import inspect
import sys
import types


# ── Minimal frappe stub — chỉ dùng khi chạy standalone (không có site) ──
def _install_frappe_stub():
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []

    def _throw(msg, exc=None):
        cls = exc or Exception
        raise cls(msg)

    frappe.throw = _throw
    frappe.whitelist = lambda *a, **k: (a[0] if a else (lambda f: f))
    frappe.get_doc = lambda *a, **k: None
    frappe.get_cached_value = lambda *a, **k: None
    frappe.get_all = lambda *a, **k: []
    frappe.get_value = lambda *a, **k: None
    frappe.get_installed_apps = lambda: []
    frappe.get_hooks = lambda *a, **k: []
    frappe.log_error = lambda *a, **k: None
    frappe.get_traceback = lambda: ""
    frappe.PermissionError = PermissionError
    frappe.ValidationError = type("ValidationError", (Exception,), {})

    db = types.ModuleType("frappe.db")
    db.get_value = lambda *a, **k: None
    frappe.db = db

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")
    document.Document = type("Document", (), {})
    model.document = document
    frappe.model = model

    sys.modules["frappe"] = frappe
    sys.modules["frappe.db"] = db
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document


if "frappe" not in sys.modules:
    _install_frappe_stub()

# ── Import các module cần test (sau khi có frappe) ─────────────────────
from alumglass.al_formula_rules.doctype.al_quantity_calc_method import (  # noqa: E402
    al_quantity_calc_method as qcm,
)
from alumglass.al_bom_engine.doctype.al_cost_template import (  # noqa: E402
    al_cost_template as ct,
)

# Import fb_handlers ngay tại module level để @register_source chạy 1 lần
# (cả 2 test A4 đều dùng chung SourceTypeRegistry singleton).
import alumglass.fb_handlers  # noqa: E402,F401  (trigger @register_source)

# Seed calc_fn trong seed_demo_data.py _calc_methods() — 4 lambda thuần số học.
SEED_CALC = {
    "LENGTH_TO_WEIGHT": ("lambda w,h,tlr,**kw: (w/1000)*tlr", {"w": 2000, "h": 0, "tlr": 1.5}, 3.0),
    "AREA": ("lambda w,h,tlr,**kw: (w/1000)*(h/1000)", {"w": 2000, "h": 1000, "tlr": 0}, 2.0),
    "LENGTH_ONLY": ("lambda w,h,tlr,**kw: w/1000", {"w": 2500, "h": 0, "tlr": 0}, 2.5),
    "COUNT": ("lambda w,h,tlr,**kw: 1", {"w": 0, "h": 0, "tlr": 0}, 1),
}

# Payload RCE — tất cả phải bị ValueError khi compile an toàn.
RCE_BODIES = [
    "().__class__.__base__.__subclasses__()",   # sandbox-escape chain
    "().__class__.__mro__",                      # dunder attr
    "lambda: 1",                                 # nested lambda
    "getattr(x, '__class__')",                   # getattr traversal
    "open('/etc/passwd')",                       # forbidden name
    "__import__('os').system('id')",             # import + method call
    "[].__class__",                              # dunder attr
]


# ═══════════════════════════════════════════════════════════════════════
# A3a — Calc method
# ═══════════════════════════════════════════════════════════════════════

def test_seed_calc_fns_compile_and_eval():
    """4 seed calc_fn (lambda) → compile an toàn → eval ra đúng giá trị."""
    for code, (fn_str, scope, expected) in SEED_CALC.items():
        expr = qcm._compile_calc_fn(fn_str)
        val = expr.eval(scope)
        assert abs(val - expected) < 1e-9, f"{code}: {val} != {expected}"


def test_lookup_calc_pattern_matches_old_lambda_semantics():
    """lookup_calc_pattern: scope w/h/tlr + extra_vars = **kw của lambda cũ."""
    qcm._calc_fn_cache.clear()
    qcm._calc_fn_cache["LENGTH_TO_WEIGHT"] = qcm._compile_calc_fn(
        "lambda w,h,tlr,extra,**kw: (w/1000)*tlr + extra"
    )
    try:
        val = qcm.lookup_calc_pattern(
            "LENGTH_TO_WEIGHT", width=2000, height=1000,
            weight_per_unit=1.5, extra=5,
        )
        assert abs(val - 8.0) < 1e-9, val
    finally:
        qcm._calc_fn_cache.clear()


def test_non_lambda_calc_fn_rejected():
    """calc_fn không phải lambda → ValueError."""
    for bad in ["w + h", "def f(): pass", ""]:
        try:
            qcm._compile_calc_fn(bad)
        except ValueError:
            continue
        raise AssertionError(f"calc_fn không hợp lệ không bị chặn: {bad!r}")


def test_calc_rce_payloads_rejected():
    """Body chứa payload RCE → compile an toàn phải ValueError."""
    for body in RCE_BODIES:
        fn_str = f"lambda w,h,tlr,**kw: {body}"
        try:
            qcm._compile_calc_fn(fn_str)
        except ValueError:
            continue
        raise AssertionError(f"RCE payload không bị chặn trong calc_fn: {body}")


# ═══════════════════════════════════════════════════════════════════════
# A3b — Cost template preview
# ═══════════════════════════════════════════════════════════════════════

class _Item:
    def __init__(self, line_code, formula, is_subtotal=0):
        self.line_code = line_code
        self.calc_formula = formula
        self.is_subtotal = is_subtotal


class _Template:
    def __init__(self, items):
        self.items = items


def _patch_get_doc(template):
    import frappe
    orig = frappe.get_doc
    frappe.get_doc = lambda doctype, name: template
    return orig


def test_preview_cost_template_arithmetic_and_string_coerce():
    """(A+B)*1.1 với input chuỗi-số → coerce float, không nối chuỗi."""
    template = _Template([
        _Item("C", "100"),
        _Item("A", "10"),
        _Item("B", "(A + C) * 1.1"),
        _Item("TONG", "A + B"),
    ])
    import frappe
    orig = _patch_get_doc(template)
    try:
        res = ct.preview_cost_template("CT-01-STANDARD", '{"C": "100"}')
        assert res["A"]["result"] == 10, res
        assert abs(res["B"]["result"] - 121.0) < 1e-9, res
        assert abs(res["TONG"]["result"] - 131.0) < 1e-9, res
        assert "error" not in res["B"], res
    finally:
        frappe.get_doc = orig


def test_preview_cost_template_forward_ref_is_error():
    """Tham chiếu biến chưa có trong ctx → error entry (như hành vi cũ)."""
    template = _Template([_Item("B", "(A + C) * 1.1")])
    import frappe
    orig = _patch_get_doc(template)
    try:
        res = ct.preview_cost_template("CT-01-STANDARD", "{}")
        assert "error" in res["B"], res
    finally:
        frappe.get_doc = orig


def test_preview_cost_template_rce_rejected():
    """Payload RCE trong calc_formula → compile chặn → error entry (không eval)."""
    template = _Template([_Item("X", "().__class__.__base__.__subclasses__()")])
    import frappe
    orig = _patch_get_doc(template)
    try:
        res = ct.preview_cost_template("CT-01-STANDARD", "{}")
        assert "error" in res["X"], f"RCE phải bị chặn: {res}"
    finally:
        frappe.get_doc = orig


def test_is_number():
    assert ct._is_number("100.5")
    assert ct._is_number("1e3")
    assert ct._is_number("-12")
    assert not ct._is_number("10mm")
    assert not ct._is_number("ABC")
    assert not ct._is_number(100)
    assert not ct._is_number(None)


# ═══════════════════════════════════════════════════════════════════════
# A4 — register_source 3 handler
# ═══════════════════════════════════════════════════════════════════════

def test_register_source_three_handlers():
    """fb_handlers → 3 source type được đăng ký (central + legacy dict)."""
    from formula_builder.api.source_type_registry import SourceTypeRegistry
    from formula_builder.api.data_source_registry import _data_source_handlers

    registry = SourceTypeRegistry.get_instance()
    source_types = ["aluminum_price_composite", "glass_master_data", "cost_bucket_aggregate"]

    for st in source_types:
        assert registry.has(st), f"Thiếu source_type: {st}"
        d = registry.get(st)
        assert d.app == "alumglass", st
        assert d.label, st
        assert isinstance(d.config_schema, dict), st
        # Registry gọi handler với signature (binding, doc, resolved_so_far)
        sig = list(inspect.signature(d.handler).parameters)
        assert sig == ["binding", "doc", "resolved_so_far"], f"{st}: {sig}"
        # legacy dict backward-compat
        assert st in _data_source_handlers, f"Legacy dict thiếu: {st}"

    # batchable + fingerprint theo yêu cầu
    assert registry.get("aluminum_price_composite").batchable is True
    assert registry.get("glass_master_data").batchable is True
    fp1 = registry.get("aluminum_price_composite").fingerprint_fn
    fp2 = registry.get("glass_master_data").fingerprint_fn
    assert fp1({"price_list": "A", "material_category": "B"}) == fp1({"price_list": "A", "material_category": "B"})
    assert fp1({"price_list": "A", "material_category": "B"}) != fp1({"price_list": "A", "material_category": "C"})
    assert fp2({"glass_code": "KINH-LOWE-24"}) == fp2({"glass_code": "KINH-LOWE-24"})

    # config_schema: enum pricing_mode
    errs = registry.validate_source_config(
        "aluminum_price_composite", {"price_list": "Standard Selling", "pricing_mode": "multiplier_chain"}
    )
    assert errs == [], errs
    errs = registry.validate_source_config("aluminum_price_composite", {"pricing_mode": "bogus"})
    assert any("pricing_mode" in e for e in errs), errs


def test_register_source_metadata_deprecated():
    """cost_bucket_aggregate giữ đăng ký, description ghi deprecated."""
    from formula_builder.api.source_type_registry import SourceTypeRegistry
    registry = SourceTypeRegistry.get_instance()
    d = registry.get("cost_bucket_aggregate")
    assert d is not None
    assert "DEPRECATED" in d.description
    assert "aggregate_from_items" in d.description
