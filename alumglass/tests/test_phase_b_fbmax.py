# -*- coding: utf-8 -*-
"""
PHASE B (FB-max) — test standalone cho B1→B6 (bom_orchestrator + api).

CÁCH CHẠY (không cần site — site dev chưa cài do A1 blocked):
    python3 -m pytest alumglass/tests/test_phase_b_fbmax.py -v

Hoặc chạy trực tiếp:
    python3 -m pytest -q alumglass/tests/test_phase_b_fbmax.py

Coverage tối thiểu theo dispatch DEV1_phase-b-fbmax.md:
    - B4: DotToSubscriptTransformer (normal + hyphen-slug fallback + nested items)
    - B5: on_error recovery (bom_engine_errors/cost_engine_errors + result vẫn tính)
          + aggregate_from_items (FB) vs Python sum fallback
    - B2: composite fallback (không binding → resolver cũ) + resolve path
    - B1: get_live_context + fallback (FVB trống → Variable Library)
    - B6: get_formula_context dùng get_live_context + dedup
"""
import ast
import json
import sys
import types


# ═══════════════════════════════════════════════════════════════════
# Frappe stub — stateful, cho phép test cấu hình dữ liệu per-doctype
# ═══════════════════════════════════════════════════════════════════

class FakeDoc:
    def __init__(self, data, name=None):
        self._data = dict(data or {})
        if name is not None:
            self._data["name"] = name
        self.name = self._data.get("name", "")

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)


class FakeFrappe:
    class DoesNotExistError(Exception):
        pass

    def __init__(self):
        self.get_all_rows = {}       # doctype -> [dict]
        self.docs = {}               # (doctype, name) -> FakeDoc
        self.cached_docs = {}        # (doctype, name) -> FakeDoc
        self.does_not_exist = set()  # (doctype, name) -> raise
        self.calc_fn = {}            # calc_pattern_code -> lambda string
        self.saved_snapshots = []
        self.set_value_calls = []
        self.commit_count = 0

    # ── registry helpers ────────────────────────────────────────────
    def set_get_all(self, doctype, rows):
        self.get_all_rows[doctype] = list(rows)

    def set_doc(self, doctype, name, data):
        doc = FakeDoc(data, name)
        self.docs[(doctype, name)] = doc
        self.cached_docs[(doctype, name)] = doc

    def set_rule(self, code, rule_type="CONSTANT", constant_value=0, resolve=None):
        d = {"rule_type": rule_type, "constant_value": constant_value}
        if resolve is not None:
            d["resolve"] = resolve
        self.set_doc("AL Calculation Rule", code, d)

    # ── filter applier (dict + list-of-3) ───────────────────────────
    @staticmethod
    def _match(row, filters):
        if not filters:
            return True
        if isinstance(filters, list):
            for cond in filters:
                if not isinstance(cond, (list, tuple)) or len(cond) < 3:
                    continue
                fld, _op, val = cond[0], cond[1], cond[2]
                if row.get(fld) != val:
                    return False
            return True
        for fld, val in filters.items():
            if (isinstance(val, (list, tuple)) and len(val) == 2
                    and val[0] == "in"):
                if row.get(fld) not in val[1]:
                    return False
            elif row.get(fld) != val:
                return False
        return True

    # ── frappe facade ───────────────────────────────────────────────
    def get_all(self, doctype, filters=None, fields=None, order_by=None, limit=None):
        rows = [dict(r) for r in self.get_all_rows.get(doctype, [])]
        return [r for r in rows if self._match(r, filters)]

    def get_cached_doc(self, doctype, name):
        if (doctype, name) in self.does_not_exist:
            raise self.DoesNotExistError(f"{doctype} {name} không tồn tại")
        return self.cached_docs[(doctype, name)]

    def get_doc(self, doctype, name):
        if (doctype, name) in self.does_not_exist:
            raise self.DoesNotExistError(f"{doctype} {name} không tồn tại")
        return self.docs[(doctype, name)]

    def new_doc(self, doctype, *args, **kwargs):
        doc = FakeDoc({}, None)
        doc.insert = lambda ignore_permissions=None: self._on_insert(doc)
        return doc

    def _on_insert(self, doc):
        self.saved_snapshots.append(doc)
        doc.name = f"CS-{len(self.saved_snapshots)}"
        return doc

    def throw(self, *a, **k):
        raise Exception(a[0] if a else "frappe.throw")

    def log_error(self, *a, **k):
        pass

    def get_traceback(self, *a, **k):
        return ""

    def whitelist(self, *a, **k):
        return a[0] if a else (lambda f: f)

    def get_installed_apps(self, *a, **k):
        return ["alumglass", "formula_builder"]

    def get_hooks(self, *a, **k):
        return {}

    def get_cached_value(self, *a, **k):
        return None

    def get_value(self, *a, **k):
        return None


class FakeDB:
    def __init__(self, owner):
        self._owner = owner

    def set_value(self, doctype, name, field_or_dict, value=None):
        self._owner.set_value_calls.append((doctype, name, field_or_dict, value))

    def commit(self, *a, **k):
        self._owner.commit_count += 1

    def get_value(self, doctype, name, field, *a, **k):
        if doctype == "AL Quantity Calc Method" and field == "calc_fn":
            return self._owner.calc_fn.get(name)
        return None

    def exists(self, doctype, name, *a, **k):
        return ((doctype, name) in self._owner.docs
                and (doctype, name) not in self._owner.does_not_exist)


_STUB = None


def _install_frappe_stub():
    global _STUB
    _STUB = FakeFrappe()
    _STUB.db = FakeDB(_STUB)
    sys.modules["frappe"] = _STUB
    sys.modules["frappe.db"] = _STUB.db
    _model = types.ModuleType("frappe.model")
    sys.modules["frappe.model"] = _model
    _document = types.ModuleType("frappe.model.document")
    _document.Document = type("Document", (), {
        "__init__": lambda self, *a, **k: setattr(self, "_data", {}),
        "get": lambda self, k, d=None: getattr(self, "_data", {}).get(k, d),
    })
    sys.modules["frappe.model.document"] = _document
    _utils = types.ModuleType("frappe.utils")
    _utils.now = lambda: "2026-08-18 10:00:00"
    _utils.flt = lambda v, d=None: v
    _utils.cstr = lambda v: str(v)
    sys.modules["frappe.utils"] = _utils
    _STUB.utils = _utils
    # Xóa các module app/FB import với stub frappe cũ (nếu pytest chạy chung)
    for name in list(sys.modules):
        if (name == "alumglass" or name.startswith("alumglass.")
                or name.startswith("formula_builder.")):
            del sys.modules[name]
    return _STUB


_install_frappe_stub()

# ── Import app modules (SAU khi có frappe stub) ─────────────────────
from formula_builder.api.batch_binding_resolver import (  # noqa: E402
    resolve_all_bindings_batch,
)
from formula_builder.api.formula_builder import get_live_context  # noqa: E402
from formula_builder.formula_utils.engine_core import (  # noqa: E402
    FormulaZeroDivisionError,
)
from formula_builder.formula_utils.engine_public import FormulaEngine  # noqa: E402

from alumglass.engine.bom_orchestrator import BomOrchestrator  # noqa: E402
import alumglass.api as api  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# Dữ liệu test — mirror seed_demo_data (bom items 2 dòng: kinh + nhôm)
# ═══════════════════════════════════════════════════════════════════

SNAP_ITEMS = [
    {
        "slug": "kinh_tren", "item_code": "KINH-01", "price_base_item": "",
        "default_glass_master": "GM-01", "item_selection_mode": "Manual",
        "category": "VL_KINH", "cost_bucket": "VL_KINH", "calc_pattern": "AREA",
        "width": "2000", "height": "1000", "qty": "2",
        "show_condition": "items.kinh_tren.glass_thick > 0",
        "item_condition_formula": "", "rule_input_expr": "",
    },
    {
        "slug": "vien_nhom", "item_code": "NHOM-01", "price_base_item": "",
        "default_glass_master": "", "item_selection_mode": "Manual",
        "category": "VL_NHOM", "cost_bucket": "VL_NHOM", "calc_pattern": "LENGTH_ONLY",
        "width": "2500", "height": "0", "qty": "4",
        "show_condition": "", "item_condition_formula": "",
        "rule_input_expr": "",
    },
]

COST_SNAPSHOT_ITEMS = [
    {"line_code": "TONG_VL", "calc_formula": "VL_NHOM + VL_KINH"},
    {"line_code": "TONG_NC", "calc_formula": "NC_SX + NC_LD"},
    {"line_code": "TONG_OH", "calc_formula": "OH_VC + OH_QLY"},
    {"line_code": "GIA_THANH", "calc_formula": "TONG_VL + TONG_NC + TONG_OH"},
    {"line_code": "GIA_BAN", "calc_formula": "GIA_THANH * (1 + PROFIT_MARGIN)"},
    {"line_code": "GIA_VAT", "calc_formula": "GIA_BAN * VAT_RATE"},
]

# User inputs per-slug (mirror dialog Tham số BOM)
EXTRA = {
    "kinh_tren__width": 2000, "kinh_tren__height": 1000, "kinh_tren__qty": 2,
    "vien_nhom__width": 2500, "vien_nhom__height": 0, "vien_nhom__qty": 4,
    "VAT_RATE": 0.1, "PROFIT_MARGIN": 0.2,
}

# Giá trị mong đợi (tính tay, mirror engine):
# kinh_tren: AREA = (2000/1000)*(1000/1000) = 2.0; total_qty = 2*2 = 4; line_total = 4*300000
# vien_nhom: LENGTH_ONLY = 2500/1000 = 2.5; total_qty = 2.5*4 = 10; line_total = 10*120000
EXPECTED_BUCKETS = {"VL_KINH": 1200000.0, "VL_NHOM": 1200000.0}
EXPECTED_GIA_VAT = 288000.0   # GIA_BAN = 2.4M * 1.2 = 2.88M; VAT = 2.88M * 0.1


def _reset_stub():
    _STUB.get_all_rows = {}
    _STUB.docs = {}
    _STUB.cached_docs = {}
    _STUB.does_not_exist = set()
    _STUB.calc_fn = {}
    _STUB.saved_snapshots = []
    _STUB.set_value_calls = []
    _STUB.commit_count = 0


def _prepare_orchestrator(extra=None):
    """Setup đầy đủ docs + master data → trả BomOrchestrator."""
    _reset_stub()
    st = _STUB
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom": "BOM-1", "al_bom_version": "ALBOMV-1",
        "al_bom_vars": json.dumps({"extra_vars": extra or {}}),
    })
    st.set_doc("AL BOM Version", "ALBOMV-1", {
        "bom": "BOM-1",
        "bom_set_snapshot": json.dumps({"items": SNAP_ITEMS}),
        "cost_template_snapshot": json.dumps({"items": COST_SNAPSHOT_ITEMS}),
    })
    st.set_doc("AL BOM", "BOM-1", {"current_version": "ALBOMV-1", "bom_set": "ALBS-1"})
    st.set_doc("AL Bom Set", "ALBS-1", {
        "profile_system": "ALPS-1", "product_type": "ALPT-1",
        "formula_fieldnames": None,
    })
    st.set_doc("AL Profile System", "ALPS-1", {
        "offset_frame": 20, "offset_glass": 10, "offset_fixed": 5,
        "offset_crossbar": 15,
    })
    st.set_doc("AL Product Type", "ALPT-1", {
        "nc_pct": 0.15, "nc_ld_rate": 0.08, "profit_margin": 0.2,
    })
    st.set_get_all("Item", [
        {"name": "KINH-01", "weight_per_unit": 15.0},
        {"name": "NHOM-01", "weight_per_unit": 1.2},
    ])
    st.set_get_all("Item Price", [
        {"name": "IP-1", "item_code": "KINH-01", "price_list_rate": 300000,
         "price_list": "Standard Selling"},
        {"name": "IP-2", "item_code": "NHOM-01", "price_list_rate": 120000,
         "price_list": "Standard Selling"},
    ])
    st.set_get_all("AL Glass Master", [
        {"name": "GM-01", "total_thick_mm": 6, "glass_type": "Clear"},
    ])
    st.set_get_all("AL Material Category", [
        {"name": "VL_KINH", "default_scrap_pct": 0.03},
        {"name": "VL_NHOM", "default_scrap_pct": 0.02},
    ])
    st.set_get_all("AL Variable Library", [
        {"var_name": "OFFSET_FRAME", "var_label": "Offset frame",
         "var_type": "Float", "source_doctype": "AL Profile System",
         "source_field": "offset_frame", "default_value": 0, "is_system": 1,
         "description": ""},
        {"var_name": "NC_SX_PCT", "var_label": "NC sx pct",
         "var_type": "Float", "source_doctype": "AL Product Type",
         "source_field": "nc_pct", "default_value": 0, "is_system": 1,
         "description": ""},
        {"var_name": "VAT_RATE", "var_label": "VAT rate",
         "var_type": "Float", "source_doctype": "", "source_field": "",
         "default_value": 0.1, "is_system": 1, "description": ""},
    ])
    st.calc_fn["AREA"] = "lambda w,h,tlr,**kw: (w/1000)*(h/1000)"
    st.calc_fn["LENGTH_ONLY"] = "lambda w,h,tlr,**kw: w/1000"
    # Mặc định KHÔNG có Formula Variable Binding → fallback path
    st.set_get_all("Formula Variable Binding", [])
    return BomOrchestrator("QI-0001")


def _run_to_b4(extra=None):
    """Chạy b0→b4, trả orch."""
    orch = _prepare_orchestrator(extra)
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    return orch


# ═══════════════════════════════════════════════════════════════════
# B4 — normalize_global (FB canonical cross-reference)
# ═══════════════════════════════════════════════════════════════════

def test_b4_dot_to_subscript_normal():
    """items.X.Y → X__Y (normalize_global — FB CANONICAL, flat namespace).

    ⚠ KHÔNG dùng DotToSubscriptTransformer: items.X.Y trong BOM là cross-
    reference tới FORMULA RESULT ({slug}__{field}), KHÔNG phải access nested
    dict resolve sẵn. Transform subscript → engine đọc nested items dict chỉ
    chứa literal (computed field=0) → nep/keo/gioang ra 0 → lệch golden.
    """
    orch = BomOrchestrator("QI-0001")
    norm = orch._normalize_items_ref("items.kinh_tren.glass_thick")
    assert norm == "kinh_tren__glass_thick", norm


def test_b4_dot_to_subscript_multi():
    orch = BomOrchestrator("QI-0001")
    norm = orch._normalize_items_ref("items.a.width + items.b.height * 2")
    assert norm == "a__width + b__height * 2", norm


def test_b4_hyphen_slug_uses_regex_fallback():
    """Slug có dấu '-' → normalize_global giữ nguyên (khớp regex cũ)."""
    orch = BomOrchestrator("QI-0001")
    norm = orch._normalize_items_ref("items.kinh-tren.glass_thick")
    assert norm == "kinh-tren__glass_thick", norm


def test_b4_no_items_ref_unchanged():
    orch = BomOrchestrator("QI-0001")
    assert orch._normalize_items_ref("a + b * 2") == "a + b * 2"
    assert orch._normalize_items_ref("") == ""


def test_b4_full_b3_nested_items_and_formulas():
    """b3_build_formulas: nested items dict (vestigial) + formula đã flatten."""
    orch = _run_to_b4(EXTRA)
    # nested items dict vẫn được inject (backward compat cho literal-only refs)
    items = orch.inputs.get("items")
    assert items["kinh_tren"]["glass_thick"] == 6, items
    assert items["kinh_tren"]["unit_price"] == 300000, items
    assert items["vien_nhom"]["qty"] == 4, items
    # formula show_condition flatten thành {slug}__{field} — FormulaEngine
    # resolve trong flat namespace (kinh_tren__glass_thick là formula-result).
    names = {f["name"]: f["formula"] for f in orch.bom_formulas}
    assert names["kinh_tren__show_condition"] == "kinh_tren__glass_thick > 0", \
        names.get("kinh_tren__show_condition")
    # B4 tính đúng giá trị
    assert orch.bom_result[0]["line_total"] == 1200000, orch.bom_result[0]
    assert orch.bom_result[1]["line_total"] == 1200000, orch.bom_result[1]


# ═══════════════════════════════════════════════════════════════════
# B5 — on_error recovery + structured errors
# ═══════════════════════════════════════════════════════════════════

def test_b5_on_error_default_recovers_bom():
    """1 formula lỗi (NameError) → on_error='default' → value=0 + error capture."""
    _reset_stub()
    engine = FormulaEngine(
        formulas=[
            {"name": "a", "formula": "1 + 2"},
            {"name": "b", "formula": "a * missing_var"},
            {"name": "c", "formula": "b + 100"},
        ],
        safe_funcs={},
        on_error="default",
        default_value=0,
        deterministic=True,
    )
    result = engine.calculate({})
    assert result["b"] == 0, result
    assert result["c"] == 100, result
    assert "b" in engine.last_errors, engine.last_errors


def test_b5_div_by_zero_always_fatal():
    """Div-by-zero LUÔN fatal bất kể on_error — không recover được."""
    _reset_stub()
    engine = FormulaEngine(
        formulas=[{"name": "a", "formula": "1/0"}],
        safe_funcs={},
        on_error="default",
        default_value=0,
        deterministic=True,
    )
    try:
        engine.calculate({})
        raise AssertionError("div-by-zero phải fatal")
    except FormulaZeroDivisionError:
        pass


def test_b5_full_flow_errors_captured_and_result_ok():
    """b4+b6 chạy đủ dù có formula lỗi → errors structured + result vẫn tính."""
    extra = dict(EXTRA)
    extra["vien_nhom__width"] = 0  # vô hại, chỉ để khác EXTRA
    orch = _prepare_orchestrator(extra)
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    # Bơm 1 formula lỗi vào bom_formulas để chứng minh recovery
    orch.b3_build_formulas()
    orch.bom_formulas.append({"name": "vien_nhom__bogus",
                              "formula": "missing_unknown_var + 1"})
    orch.b4_calculate_bom_items()
    assert orch.bom_engine_errors, "phải có lỗi trong bom_engine_errors"
    assert any("missing_unknown_var" in str(v)
               for v in orch.bom_engine_errors.values()), orch.bom_engine_errors
    assert orch.bom_result[0]["line_total"] == 1200000, orch.bom_result[0]
    # b6 vẫn tính ra GIA_VAT
    orch.b5_aggregate_cost_buckets()
    orch.b6_calculate_cost_template()
    assert orch.gia_vat == EXPECTED_GIA_VAT, orch.gia_vat
    # errors được ghi vào ConfigSnapshot qua result_json
    orch.b7_save_results()
    assert _STUB.saved_snapshots, "ConfigSnapshot phải được insert"
    full = json.loads(_STUB.saved_snapshots[0].result_json)
    assert full["errors"]["bom_items"], full["errors"]
    assert _STUB.commit_count == 1, "single commit (B1 fix)"


def test_b5_python_sum_fallback_when_no_config():
    """Bucket chưa có source_config → fallback sum Python (bảo toàn golden)."""
    orch = _run_to_b4(EXTRA)
    orch.b5_aggregate_cost_buckets()
    assert orch.buckets == EXPECTED_BUCKETS, orch.buckets


def test_b5_fb_aggregate_bucket_resolve():
    """Bucket có source_type='aggregate_from_items' + config → dùng FB value."""
    orch = _run_to_b4(EXTRA)
    _STUB.set_get_all("AL Cost Bucket", [
        {"bucket_code": "VL_KINH", "bucket_role": "LEAF",
         "source_type": "aggregate_from_items",
         "source_config": json.dumps({
             "table": "items", "key_field": "cost_bucket",
             "value_field": "line_total", "filter_key": "VL_KINH"})},
    ])
    import formula_builder.api.batch_binding_resolver as bbr
    orig = bbr.resolve_all_bindings_batch
    bbr.resolve_all_bindings_batch = lambda bindings, doc=None, pre_resolved=None: {
        "VL_KINH": 555.0,
    }
    try:
        fb = orch._resolve_cost_buckets_via_fb()
        assert fb == {"VL_KINH": 555.0}, fb
        orch.b5_aggregate_cost_buckets()
        assert orch.buckets["VL_KINH"] == 555.0, orch.buckets
        # bucket không có config → sum Python bình thường
        assert orch.buckets["VL_NHOM"] == 1200000.0, orch.buckets
    finally:
        bbr.resolve_all_bindings_batch = orig


# ═══════════════════════════════════════════════════════════════════
# B2 — composite price fallback + resolve path
# ═══════════════════════════════════════════════════════════════════

def test_b2_fallback_when_no_binding():
    """Không có Formula Variable Binding → FB trả None → resolver cũ."""
    orch = _run_to_b4(EXTRA)
    assert orch.row_literals["kinh_tren"]["unit_price"] == 300000, orch.row_literals
    assert orch.row_literals["vien_nhom"]["unit_price"] == 120000, orch.row_literals


def test_b2_fb_resolve_path():
    """Có binding composite_key_lookup → resolve qua FB → giá binding thắng."""
    orch = _prepare_orchestrator(EXTRA)
    _STUB.set_get_all("Formula Variable Binding", [
        {"name": "B-PRICE", "is_active": 1, "variable_name": "unit_price_binding",
         "variable_label": "Unit price", "source_type": "composite_key_lookup",
         "source_config": json.dumps({
             "table": "Item Price", "key_fields": ["item_code"],
             "value_field": "price_list_rate"}),
         "resolve_priority": 1, "applies_to_doctype": "Quotation Item",
         "applies_to_field": "", "is_global": 0, "data_type": "Float",
         "default_value": 0},
    ])
    import formula_builder.api.batch_binding_resolver as bbr
    orig = bbr.resolve_all_bindings_batch
    bbr.resolve_all_bindings_batch = lambda bindings, doc=None, pre_resolved=None: {
        "unit_price_binding": 999.0,
    }
    try:
        prices = orch._fetch_composite_prices_via_fb(["KINH-01", "NHOM-01"])
        assert prices == {"KINH-01": 999.0, "NHOM-01": 999.0}, prices
        # b2 integrate: binding thắng resolver cũ
        orch.b0_version_pinning()
        orch.b1_gather_inputs()
        orch.b2_prefetch_master_data()
        assert orch.row_literals["kinh_tren"]["unit_price"] == 999.0, \
            orch.row_literals["kinh_tren"]
    finally:
        bbr.resolve_all_bindings_batch = orig


def test_b2_composite_match_picks_best_row():
    """_match_composite_price: nhiều dòng Item Price → chọn khớp nhiều field nhất."""
    orch = BomOrchestrator("QI-0001")
    rows = [
        {"name": "IP-A", "price_list_rate": 100, "custom_mau": "", "custom_do_day": ""},
        {"name": "IP-B", "price_list_rate": 200, "custom_mau": "DEN", "custom_do_day": ""},
        {"name": "IP-C", "price_list_rate": 300, "custom_mau": "DEN", "custom_do_day": "6"},
    ]
    dims = {"MAU": "custom_mau", "DO_DAY": "custom_do_day"}
    orch.inputs["MAU"] = "DEN"
    orch.inputs["DO_DAY"] = "6"
    assert orch._match_composite_price("KINH-01", rows, dims) == 300
    orch.inputs["MAU"] = "TRANG"
    orch.inputs["DO_DAY"] = ""
    assert orch._match_composite_price("KINH-01", rows, dims) == 100  # fallback trần


# ═══════════════════════════════════════════════════════════════════
# B1 — get_live_context + fallback
# ═══════════════════════════════════════════════════════════════════

def test_b1_live_context_empty_fallback():
    """FVB chưa seed → get_live_context trả ít binding → resolver cũ (Variable Library)."""
    orch = _prepare_orchestrator(EXTRA)
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    # Variable Library vẫn resolve (profile system → OFFSET_FRAME = 20)
    assert orch.inputs["OFFSET_FRAME"] == 20, orch.inputs
    # VAT_RATE default từ Variable Library (không bị FB override)
    assert orch.inputs["VAT_RATE"] == 0.1, orch.inputs


def test_b1_live_context_overrides_when_fvb_seeded():
    """Có FVB → get_live_context trả variable → override Variable Library."""
    orch = _prepare_orchestrator(EXTRA)
    import formula_builder.api.formula_builder as fb_api
    orig = fb_api.get_live_context
    fb_api.get_live_context = lambda scope_json: {
        "success": True,
        "variables": [
            {"name": "VAT_RATE", "label": "VAT rate", "value": 0.08,
             "type": "Float", "source": "local", "source_type": "binding",
             "is_global": True},
        ],
    }
    try:
        fb_ctx = orch._resolve_fb_context()
        assert fb_ctx == {"VAT_RATE": 0.08}, fb_ctx
        orch.b0_version_pinning()
        orch.b1_gather_inputs()
        assert orch.inputs["VAT_RATE"] == 0.08, orch.inputs
    finally:
        fb_api.get_live_context = orig


def test_b1_live_context_exception_returns_empty():
    """get_live_context lỗi (vd thiếu permission) → {} → fallback resolver cũ."""
    orch = _prepare_orchestrator(EXTRA)
    import formula_builder.api.formula_builder as fb_api
    orig = fb_api.get_live_context
    fb_api.get_live_context = lambda scope_json: (_ for _ in ()).throw(
        PermissionError("denied"))
    try:
        assert orch._resolve_fb_context() == {}
        orch.b0_version_pinning()
        orch.b1_gather_inputs()
        assert orch.inputs["VAT_RATE"] == 0.1, orch.inputs
    finally:
        fb_api.get_live_context = orig


def test_b1_whole_object_variables_skipped():
    """Variable object (dict/list) không merge vào inputs (chỉ scalar)."""
    orch = _prepare_orchestrator(EXTRA)
    import formula_builder.api.formula_builder as fb_api
    orig = fb_api.get_live_context
    fb_api.get_live_context = lambda scope_json: {
        "success": True,
        "variables": [
            {"name": "VAT_RATE", "value": 0.08},
            {"name": "whole_qi", "value": {"some": "dict"}, "is_global": True},
            {"name": "list_var", "value": [1, 2, 3]},
        ],
    }
    try:
        fb_ctx = orch._resolve_fb_context()
        assert fb_ctx == {"VAT_RATE": 0.08}, fb_ctx
    finally:
        fb_api.get_live_context = orig


# ═══════════════════════════════════════════════════════════════════
# B6 — FlexibleFormulaEngine on_error + get_formula_context
# ═══════════════════════════════════════════════════════════════════

def test_b6_full_flow_gia_vat():
    """Toàn bộ b0→b7 chạy 1 mạch, GIA_VAT đúng, snapshot insert, single commit."""
    orch = _run_to_b4(EXTRA)
    orch.b5_aggregate_cost_buckets()
    orch.b6_calculate_cost_template()
    assert orch.gia_vat == EXPECTED_GIA_VAT, (orch.gia_vat, EXPECTED_GIA_VAT)
    assert orch.cost_engine_errors == {}, orch.cost_engine_errors
    orch.b7_save_results()
    assert len(_STUB.saved_snapshots) == 1
    snap = json.loads(_STUB.saved_snapshots[0].result_json)
    assert snap["cost_template"]["GIA_BAN"] == 2880000, snap["cost_template"]
    assert _STUB.commit_count == 1


def test_b6_cost_template_errors_captured():
    """Formula cost template có lỗi → cost_engine_errors ghi, GIA_VAT vẫn tính."""
    orch = _run_to_b4(EXTRA)
    # Bơm 1 formula lỗi (tham chiếu biến không tồn tại, chữ thường → không
    # được set default bởi referenced_codes regex)
    items = json.loads(orch.bom_version.cost_template_snapshot)["items"]
    items = items + [{"line_code": "BAD_LINE", "calc_formula": "GIA_BAN + unknown_zzz"}]
    orch.bom_version.cost_template_snapshot = json.dumps({"items": items})
    orch.b5_aggregate_cost_buckets()
    orch.b6_calculate_cost_template()
    assert orch.cost_engine_errors, orch.cost_engine_errors
    assert orch.gia_vat == EXPECTED_GIA_VAT, orch.gia_vat


def test_b6_api_get_formula_context_uses_fb_first():
    """get_formula_context: entry FB đứng đầu + dedup loại trùng tên nguồn cũ."""
    _reset_stub()
    _STUB.set_get_all("AL Cost Bucket", [
        {"bucket_code": "VL_KINH", "bucket_name": "Vật liệu kính",
         "bucket_role": "LEAF", "report_group": "Vật liệu", "sort_order": 1},
    ])
    _STUB.set_get_all("AL Variable Library", [
        {"var_name": "VAT_RATE", "var_label": "VAT", "var_type": "Float",
         "default_value": 0.1, "description": "", "is_system": 1,
         "source_doctype": "", "source_field": ""},
    ])
    _STUB.set_get_all("Formula Global Variable", [])
    _STUB.set_get_all("Formula Variable Binding", [])
    _STUB.set_get_all("AL Slug Library", [])

    import formula_builder.api.formula_builder as fb_api
    orig = fb_api.get_live_context
    fb_api.get_live_context = lambda scope_json: {
        "success": True,
        "variables": [
            {"name": "VAT_RATE", "label": "VAT rate", "value": 0.08,
             "type": "Float", "source": "local", "source_type": "binding",
             "is_global": True},
            {"name": "FB_ONLY_VAR", "label": "FB only", "value": 42.0,
             "type": "Float", "source": "local", "source_type": "binding",
             "is_global": False},
        ],
    }
    try:
        ctx = api.get_formula_context("AL Cost Template", None)
        names = [v["name"] for v in ctx["variables"]]
        # FB entry đứng đầu
        assert names[0] == "VAT_RATE", names[:3]
        assert names[1] == "FB_ONLY_VAR", names[:3]
        # dedup: VAT_RATE chỉ xuất hiện 1 lần (entry FB giữ, Variable Library bỏ)
        assert names.count("VAT_RATE") == 1, names
        assert "FB_ONLY_VAR" in names
        assert "VL_KINH" in names
    finally:
        fb_api.get_live_context = orig


def test_b6_api_fallback_when_fb_unavailable():
    """FB unavailable → API vẫn trả biến từ nguồn cũ (không mất biến UI)."""
    _reset_stub()
    _STUB.set_get_all("AL Cost Bucket", [])
    _STUB.set_get_all("AL Variable Library", [
        {"var_name": "VAT_RATE", "var_label": "VAT", "var_type": "Float",
         "default_value": 0.1, "description": "", "is_system": 1,
         "source_doctype": "", "source_field": ""},
    ])
    _STUB.set_get_all("Formula Global Variable", [])
    _STUB.set_get_all("Formula Variable Binding", [])
    _STUB.set_get_all("AL Slug Library", [])
    ctx = api.get_formula_context("AL Cost Template", None)
    names = [v["name"] for v in ctx["variables"]]
    assert "VAT_RATE" in names, names
    assert len(names) > 5, len(names)  # vẫn có row literals, common vars...


# ═══════════════════════════════════════════════════════════════════
# B1 — user variable defaults (is_system=0) — installation_height_m
# ═══════════════════════════════════════════════════════════════════

def test_b1_user_variable_default_applied_when_absent():
    """User variable (is_system=0) không có trong bom_vars → lấy default từ
    AL Variable Library. Golden CDMQ-2C: installation_height_m mặc định "3"
    → NC_LD resolve RULE-HEIGHT-MULT(3)=1.0 (nếu thiếu → NameError → NC_LD=0).
    """
    orch = _prepare_orchestrator(EXTRA)
    # Thêm user var installation_height_m (is_system=0, default 3)
    rows = list(_STUB.get_all_rows.get("AL Variable Library", []))
    rows.append({"var_name": "installation_height_m", "var_label": "H lắp đặt",
                 "var_type": "Float", "source_doctype": "", "source_field": "",
                 "default_value": 3, "is_system": 0, "description": ""})
    _STUB.set_get_all("AL Variable Library", rows)
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    assert orch.inputs.get("installation_height_m") == 3.0, orch.inputs.get(
        "installation_height_m")
    # User bom_vars ghi đè default (key do user nhập → default KHÔNG lấn)
    orch2 = _prepare_orchestrator(dict(EXTRA, **{"installation_height_m": 15}))
    _STUB.set_get_all("AL Variable Library", rows)
    orch2.b0_version_pinning()
    orch2.b1_gather_inputs()
    assert orch2.inputs.get("installation_height_m") == 15, orch2.inputs.get(
        "installation_height_m")


# ═══════════════════════════════════════════════════════════════════
# B2 — Accessory Set (VL_PK) — bước engine v28.7 THIẾU sau 7-phase rewrite
# ═══════════════════════════════════════════════════════════════════

def _prepare_with_accessories(extra=None):
    """Như _prepare_orchestrator nhưng có Bom Set.default_accessory_set +
    AL Accessory Set (tay_nam + ban_le) + RULE-BANLE-QTY THRESHOLD.
    """
    orch = _prepare_orchestrator(extra)
    _STUB.docs[("AL Bom Set", "ALBS-1")] = FakeDoc({
        "profile_system": "ALPS-1", "product_type": "ALPT-1",
        "formula_fieldnames": None, "default_accessory_set": "ACC-1",
    }, "ALBS-1")
    _STUB.cached_docs[("AL Bom Set", "ALBS-1")] = _STUB.docs[("AL Bom Set", "ALBS-1")]
    _STUB.set_doc("AL Accessory Set", "ACC-1", {
        "set_code": "ACC-1",
        "items": [
            {"slug": "tay_nam", "item_code": "PK-01", "qty": 1, "qty_formula": ""},
            {"slug": "ban_le", "item_code": "PK-02", "qty": 0,
             "qty_formula": "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel"},
        ],
    })
    # Item + Item Price cho phụ kiện
    _STUB.set_get_all("Item", [
        {"name": "KINH-01", "weight_per_unit": 15.0},
        {"name": "NHOM-01", "weight_per_unit": 1.2},
        {"name": "PK-01", "weight_per_unit": 0.0},
        {"name": "PK-02", "weight_per_unit": 0.0},
    ])
    _STUB.set_get_all("Item Price", [
        {"name": "IP-1", "item_code": "KINH-01", "price_list_rate": 300000,
         "price_list": "Standard Selling"},
        {"name": "IP-2", "item_code": "NHOM-01", "price_list_rate": 120000,
         "price_list": "Standard Selling"},
        {"name": "IP-3", "item_code": "PK-01", "price_list_rate": 210000,
         "price_list": "Standard Selling"},
        {"name": "IP-4", "item_code": "PK-02", "price_list_rate": 180000,
         "price_list": "Standard Selling"},
    ])
    # RULE-BANLE-QTY: H_mm=2600 → 4 (golden CDMQ-2C: 8 bản lề = 4×2)
    _STUB.set_doc("AL Calculation Rule", "RULE-BANLE-QTY", {
        "rule_type": "THRESHOLD",
        "resolve": lambda v: 4 if 2600 <= float(v) else 2,
    })
    # COUNT calc pattern (phụ kiện) — lookup_calc_pattern("COUNT", ...) → 1
    _STUB.calc_fn["COUNT"] = "lambda w,h,tlr,**kw: 1"
    return orch


def test_b2_accessories_loaded_from_accessory_set():
    """b2: phụ kiện được nạp từ AL Accessory Set → bom_items + row_literals."""
    orch = _prepare_with_accessories({"H_mm": 2600, "n_panel": 2})
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    slugs = {it.get("slug") for it in orch.bom_items}
    assert {"tay_nam", "ban_le"} <= slugs, slugs
    assert orch.row_literals["tay_nam"]["unit_price"] == 210000, orch.row_literals
    assert orch.row_literals["ban_le"]["unit_price"] == 180000, orch.row_literals
    assert orch.row_literals["ban_le"]["calc_pattern"] == "COUNT", orch.row_literals


def test_b2_accessories_b4_computes_vl_pk():
    """b2→b4: ban_le qty_formula resolve lookup_rule(RULE-BANLE-QTY,H_mm)*n_panel
    → 4×2=8 bản lề → VL_PK = tay_nam + ban_le = 210000 + 8×180000 = 1,650,000.
    """
    orch = _prepare_with_accessories({"H_mm": 2600, "n_panel": 2})
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    by_slug = {r["slug"]: r for r in orch.bom_result}
    assert by_slug["ban_le"]["total_qty"] == 8, by_slug["ban_le"]
    assert by_slug["ban_le"]["line_total"] == 1440000, by_slug["ban_le"]
    assert by_slug["tay_nam"]["line_total"] == 210000, by_slug["tay_nam"]
    # bucket VL_PK
    orch.b5_aggregate_cost_buckets()
    assert orch.buckets["VL_PK"] == 1650000, orch.buckets


def test_b2_no_accessory_set_no_crash():
    """Không có default_accessory_set + không có accessory_set → bỏ qua, không lỗi."""
    orch = _prepare_orchestrator(EXTRA)
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    assert all(it.get("cost_bucket") != "VL_PK" for it in orch.bom_items)


# ═══════════════════════════════════════════════════════════════════
# B6 — custom_functions (lookup_rule) — fix UNKNOWN_FUNCTION
# ═══════════════════════════════════════════════════════════════════

def test_b6_custom_functions_lookup_rule_in_cost_template():
    """B6 EngineConfig.custom_functions phải chứa lookup_rule — nếu KHÔNG,
    cost template NC_LD = NC_LD_PCT*TONG_VL*lookup_rule('RULE-HEIGHT-MULT',x)
    crash [ENGINE.UNKNOWN_FUNCTION] → NC_LD=0 (bug đã fix). Test xác nhận
    lookup_rule resolve được trong FlexibleFormulaEngine qua custom_functions.
    """
    orch = _prepare_orchestrator(EXTRA)
    # Thêm user var installation_height_m (is_system=0, default 3) — giống
    # seed thật, để NC_LD resolve được mult.
    rows = list(_STUB.get_all_rows.get("AL Variable Library", []))
    rows.append({"var_name": "installation_height_m", "var_label": "H lắp đặt",
                 "var_type": "Float", "source_doctype": "", "source_field": "",
                 "default_value": 3, "is_system": 0, "description": ""})
    _STUB.set_get_all("AL Variable Library", rows)
    _STUB.set_doc("AL Calculation Rule", "RULE-HEIGHT-MULT", {
        "rule_type": "THRESHOLD",
        "resolve": lambda v: 1.0 if float(v) <= 10 else 1.2,
    })
    # Cost template có dòng dùng lookup_rule (phải set SAU b0 vì bom_version
    # được gán trong b0_version_pinning)
    items = [
        {"line_code": "TONG_VL", "calc_formula": "VL_NHOM + VL_KINH"},
        {"line_code": "NC_LD", "calc_formula": "0.12 * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)"},
        {"line_code": "GIA_VAT", "calc_formula": "TONG_VL + NC_LD"},
    ]
    orch.b0_version_pinning()
    orch.bom_version.cost_template_snapshot = json.dumps({"items": items})
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    orch.b5_aggregate_cost_buckets()
    orch.b6_calculate_cost_template()
    # installation_height_m default "3" (user var default) → mult 1.0
    assert orch.inputs.get("installation_height_m") == 3.0, orch.inputs.get(
        "installation_height_m")
    assert orch.cost_engine_errors == {}, orch.cost_engine_errors
    # TONG_VL = 1.2M + 1.2M = 2.4M; NC_LD = 0.12*2.4M*1.0 = 288K; GIA_VAT = 2.688M
    assert abs(orch.gia_vat - 2688000) < 0.01, orch.gia_vat


# ═══════════════════════════════════════════════════════════════════
# Runner standalone (không cần pytest)
# ═══════════════════════════════════════════════════════════════════

def _main():
    import traceback
    funcs = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    passed, failed = 0, []
    for name, fn in funcs:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception:
            failed.append(name)
            print(f"  FAIL  {name}")
            traceback.print_exc()
    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {len(funcs)}  PASS: {passed}  FAIL: {len(failed)}")
    if failed:
        print(f"  FAILED: {failed}")
        raise SystemExit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _main()
