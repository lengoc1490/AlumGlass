# -*- coding: utf-8 -*-
"""cross_row_fields của `AL Accessory Set` — phủ đúng field engine B3 inject.

Bối cảnh: `ALAccessorySet._validate_item_formulas()` truyền
`cross_row_fields=_cross_row_fields()`; trước bản vá, hàm này lấy MỌI field vô
hướng từ meta `AL Accessory Item` (`slug, item_code, qty, qty_formula,
calc_pattern, cost_bucket, unit_price, default_color, supplier_location,
install_position, note`) — THIẾU `unit_qty/total_qty/line_total`.

Nhưng engine B3 (`bom_orchestrator.b3_build_formulas`) LUÔN tạo 3 khoá
synthetic `{slug}__unit_qty`, `{slug}__total_qty`, `{slug}__line_total` cho
MỌI dòng, kể cả dòng phụ kiện (`_load_accessories` append vào `bom_items`) ⇒
công thức `items.<slug>.total_qty` CHẠY ĐÚNG lúc runtime vẫn bị chặn oan
"Biến không khai báo". Nặng nhất: seed profile `P_ACCESSORY_DEFAULT` gợi ý
chính `total_qty`/`line_total` trong `cross_row.fields` — người dùng làm theo
gợi ý là bị chặn khi Lưu.

Từ bản vá này `_cross_row_fields()` = meta của `AL Accessory Item` ∪
`ENGINE_SYNTHETIC_FIELDS` (fallback cũng vậy).

CÁCH CHẠY
---------
Không cần site (tự stub frappe + context, giống
test_bom_set_cross_row_known_fields.py):
    python3 alumglass/tests/test_accessory_cross_row_known_fields.py
Hoặc qua bench:
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_accessory_cross_row_known_fields
"""
import importlib.util
import json
import os
import sys
import types
import unittest

# Field type được coi là "vô hướng" — đồng bộ với
# alumglass/variable_sources/context.py::get_scalar_fieldnames.
_SCALAR_FIELDTYPES = {"Data", "Int", "Float", "Currency", "Percent", "Check",
                      "Select", "Link", "Date", "Datetime", "Time"}
_SKIP_FIELDS = {"name", "owner", "creation", "modified", "modified_by",
                "docstatus", "idx", "parent", "parenttype", "parentfield",
                "doctype", "amended_from"}

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_APPS_ROOT = os.path.dirname(_REPO_ROOT)
_ACCESSORY_ITEM_DOCTYPE = (
    "alumglass/al_bom_engine/doctype/al_accessory_item/al_accessory_item.json")
_SEED_PATCH = "alumglass/patches/v28_14/seed_variable_catalog.py"

_USED_MODULES = (
    "frappe",
    "frappe.model",
    "frappe.model.document",
    "alumglass",
    "alumglass.al_bom_engine",
    "alumglass.al_bom_engine.doctype",
    "alumglass.al_bom_engine.doctype.al_bom_item",
    "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item",
    "alumglass.al_bom_engine.doctype.al_accessory_set",
    "alumglass.al_bom_engine.doctype.al_accessory_set.al_accessory_set",
    "alumglass.al_bom_engine.formula_validate",
    "alumglass.variable_sources",
    "alumglass.variable_sources.context",
    "alumglass.api",
)


def _load_source(module_name, rel_path):
    """Nạp 1 file .py theo đường dẫn thành module mang tên `module_name`."""
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_REPO_ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _meta_scalar_fieldnames():
    """Field vô hướng THẬT của `AL Accessory Item`, đọc từ JSON của doctype.

    Mô phỏng đúng luật lọc của `get_scalar_fieldnames()` (loại field layout +
    Small Text/JSON/Table) — đọc từ nguồn sự thật (JSON doctype) thay vì
    hardcode ở test, để đổi meta là test bắt được.
    """
    with open(os.path.join(_REPO_ROOT, _ACCESSORY_ITEM_DOCTYPE),
              encoding="utf-8") as handle:
        doctype = json.load(handle)
    out = []
    for field in doctype.get("fields") or []:
        if field.get("fieldtype") not in _SCALAR_FIELDTYPES:
            continue
        if field.get("fieldname") in _SKIP_FIELDS:
            continue
        out.append(field.get("fieldname"))
    return out


class _LoadWithStubs:
    """Nạp al_accessory_set.py + al_bom_item.py + formula_validate.py THẬT.

    Chỉ stub thứ nằm NGOÀI repo: `frappe`, `alumglass.variable_sources.context`
    (nguồn field vô hướng) và `alumglass.api.get_formula_context` (nguồn biến
    toàn cục — test này không cần Cost Bucket/User Var thật). Mọi module ghi
    vào `sys.modules` được khôi phục nguyên trạng khi thoát context.
    """

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        self._saved = {name: sys.modules.get(name) for name in _USED_MODULES}

        frappe = types.ModuleType("frappe")
        frappe.__path__ = []
        frappe.whitelist = lambda *a, **k: (lambda fn: fn)
        frappe.throw = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError(a[0] if a else "frappe.throw"))
        frappe.msgprint = lambda *a, **k: None
        frappe.log_error = lambda *a, **k: None
        frappe._ = lambda s: s

        model = types.ModuleType("frappe.model")
        model.__path__ = []
        document = types.ModuleType("frappe.model.document")

        class _Document(object):
            pass

        document.Document = _Document
        model.document = document
        frappe.model = model
        for name, mod in (("frappe", frappe), ("frappe.model", model),
                          ("frappe.model.document", document)):
            sys.modules[name] = mod

        # Package alumglass — chỉ cần `__path__` để nạp module con qua spec.
        for name in ("alumglass", "alumglass.al_bom_engine",
                     "alumglass.al_bom_engine.doctype",
                     "alumglass.al_bom_engine.doctype.al_bom_item",
                     "alumglass.al_bom_engine.doctype.al_accessory_set",
                     "alumglass.variable_sources",
                     "alumglass.api"):
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            sys.modules[name] = pkg

        # Context: meta thật của AL Accessory Item (xem _meta_scalar_fieldnames).
        context = types.ModuleType("alumglass.variable_sources.context")
        context.get_scalar_fieldnames = (
            lambda doctype: list(_meta_scalar_fieldnames())
            if doctype == "AL Accessory Item" else [])
        sys.modules["alumglass.variable_sources.context"] = context
        sys.modules["alumglass.variable_sources"].context = context

        # api.get_formula_context: rỗng (test này kiểm wiring cross-row, không
        # kiểm nguồn biến toàn cục).
        api = sys.modules["alumglass.api"]
        api.get_formula_context = lambda *a, **k: {"variables": []}
        self.api = api

        # formula_validate THẬT (cần formula_builder trên sys.path — app lõi,
        # không import frappe). Thiếu formula_builder thì rơi về stub và các
        # test đầu-cuối tự skip.
        formula_builder_root = os.path.join(_APPS_ROOT, "formula_builder")
        if os.path.isdir(formula_builder_root) and formula_builder_root not in sys.path:
            sys.path.insert(0, formula_builder_root)
        self.real_validate = True
        try:
            self.formula_validate = _load_source(
                "alumglass.al_bom_engine.formula_validate",
                "alumglass/al_bom_engine/formula_validate.py")
        except Exception:
            self.real_validate = False
            fv = types.ModuleType("alumglass.al_bom_engine.formula_validate")
            fv.build_known_names = lambda *a, **k: set()
            fv.check_formula_fields = lambda *a, **k: []
            fv.check_formula = lambda *a, **k: []
            # al_accessory_set.py (HEAD) import thêm 4 hàm này — thiếu stub
            # thì test nổ ImportError trước khi kiểm được gì.
            fv.load_rule_meta = lambda *a, **k: {}
            fv.lookup_rule_codes = lambda *a, **k: []
            fv.row_reference_label = lambda *a, **k: ""
            fv.validate_lookup_rule_codes = lambda *a, **k: []
            sys.modules["alumglass.al_bom_engine.formula_validate"] = fv
            self.formula_validate = fv

        _load_source(
            "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item",
            "alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.py")
        self.accessory = _load_source(
            "alumglass.al_bom_engine.doctype.al_accessory_set.al_accessory_set",
            "alumglass/al_bom_engine/doctype/al_accessory_set/al_accessory_set.py")
        return self

    def __exit__(self, *exc):
        for name, old in self._saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        return False


class TestAccessoryCrossRowFields(unittest.TestCase):
    """`_cross_row_fields()` + wired qua `build_known_names`/`check_formula`."""

    def setUp(self):
        self._ctx = _LoadWithStubs().__enter__()
        self.mod = self._ctx.accessory
        self.fv = self._ctx.formula_validate

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    # ── Nội dung danh sách ────────────────────────────────────────────
    def test_contains_meta_and_synthetic_fields(self):
        """Có field meta dùng thật + 3 synthetic engine luôn tạo."""
        fields = set(self.mod._cross_row_fields())
        self.assertTrue(
            {"qty", "unit_price", "calc_pattern"} <= fields,
            f"Thiếu field meta: {sorted(fields)}")
        self.assertTrue(
            {"unit_qty", "total_qty", "line_total"} <= fields,
            f"Thiếu synthetic engine: {sorted(fields)}")

    def test_excludes_qty_formula(self):
        """`qty_formula` là CHUỖI CÔNG THỨC — engine ⛔ không inject
        `{slug}__qty_formula`, nên không được nằm trong universe biến.

        (Chạy ở nhánh META — nhánh fallback cố tình permissive, xem
        _FALLBACK_CROSS_ROW_FIELDS.)
        """
        self.assertNotIn("qty_formula", set(self.mod._cross_row_fields()))

    def test_no_duplicates(self):
        """Không trùng tên (build_known_names lặp slug × field)."""
        fields = self.mod._cross_row_fields()
        self.assertIsInstance(fields, tuple)
        self.assertEqual(len(fields), len(set(fields)))

    def test_fallback_includes_synthetic(self):
        """Không đọc được meta (site chưa migrate) → fallback VẪN có synthetic."""
        sys.modules.pop("alumglass.variable_sources.context", None)
        sys.modules["alumglass.variable_sources"].__dict__.pop("context", None)
        fields = set(self.mod._cross_row_fields())
        self.assertTrue(
            {"unit_qty", "total_qty", "line_total"} <= fields,
            f"Fallback thiếu synthetic: {sorted(fields)}")
        self.assertTrue({"qty", "unit_price", "calc_pattern"} <= fields)

    # ── Ca seed profile P_ACCESSORY_DEFAULT ───────────────────────────
    def test_seed_profile_cross_row_fields_all_known(self):
        """MỌI field `P_ACCESSORY_DEFAULT.cross_row.fields` phải hợp lệ.

        Đây là ca thật: profile gợi ý `total_qty`/`line_total` trong
        autocomplete `items.<slug>.<field>` — chúng không có trong meta
        `AL Accessory Item`, nên trước bản vá người dùng làm theo gợi ý là bị
        chặn khi Lưu.
        """
        seed = _load_source(
            "alumglass.patches.v28_14.seed_variable_catalog", _SEED_PATCH)
        profile = None
        for cfg in seed._PROFILES:
            if cfg.get("profile_code") == "P_ACCESSORY_DEFAULT":
                profile = cfg
                break
        self.assertIsNotNone(
            profile, "Không tìm thấy profile P_ACCESSORY_DEFAULT trong seed")

        suggested = set()
        for cross_row in profile.get("cross_row") or ():
            raw = cross_row.get("fields")
            if isinstance(raw, str):
                suggested |= set(json.loads(raw))
            elif raw:
                suggested |= set(raw)
        self.assertTrue(suggested, "Profile không khai cross_row.fields")

        known = set(self.mod._cross_row_fields())
        self.assertEqual(
            suggested - known, set(),
            "Profile gợi ý field mà validate vẫn chặn: "
            f"{sorted(suggested - known)}")

    # ── Đầu-cuối qua build_known_names + validator THẬT ───────────────
    def _known_names(self, slug="x"):
        return self.fv.build_known_names(
            "AL Accessory Set", "TEST-ACC-SET",
            cross_row_slugs=[slug], cross_row_fields=self.mod._cross_row_fields())

    def test_total_qty_not_unknown_anymore(self):
        """`items.x.total_qty` KHÔNG còn bị coi là biến lạ (đối chứng dương)."""
        if not self._ctx.real_validate:
            self.skipTest("Không có formula_builder — bỏ qua kiểm validator thật")
        names = self._known_names()
        self.assertIn("x__total_qty", names)
        errs = self.fv.check_formula(
            "items.x.total_qty * 2", names, allow_cross_row=True)
        self.assertEqual(errs, [], f"Chặn oan items.x.total_qty: {errs}")

    def test_unit_qty_and_line_total_not_unknown(self):
        """`unit_qty`/`line_total` cũng phải qua validate."""
        if not self._ctx.real_validate:
            self.skipTest("Không có formula_builder — bỏ qua kiểm validator thật")
        names = self._known_names()
        for expr in ("items.x.unit_qty + 1", "items.x.line_total / 2"):
            self.assertEqual(
                self.fv.check_formula(expr, names, allow_cross_row=True), [],
                f"Chặn oan: {expr}")

    def test_unknown_field_still_blocked(self):
        """Đối chứng ÂM: field không tồn tại VẪN bị chặn (nới đúng mức)."""
        if not self._ctx.real_validate:
            self.skipTest("Không có formula_builder — bỏ qua kiểm validator thật")
        names = self._known_names()
        errs = self.fv.check_formula(
            "items.x.khong_ton_tai * 2", names, allow_cross_row=True)
        self.assertTrue(errs, "Field lạ phải bị chặn — bản vá nới quá tay")

    def test_validate_passes_superset_to_build_known_names(self):
        """`_validate_item_formulas` truyền superset cho build_known_names."""
        captured = {}

        def _fake_build_known_names(doctype, docname, cross_row_slugs=None,
                                    cross_row_fields=None, fieldname=None):
            captured["fields"] = tuple(cross_row_fields or ())
            captured["slugs"] = tuple(cross_row_slugs or ())
            return set()

        self.mod.build_known_names = _fake_build_known_names
        self.mod.check_formula_fields = lambda *a, **k: []

        doc = self.mod.ALAccessorySet.__new__(self.mod.ALAccessorySet)
        doc.name = "TEST-ACC-SET"
        doc.items = [types.SimpleNamespace(slug="tay_nam", idx=1)]

        doc._validate_item_formulas()

        self.assertEqual(captured["slugs"], ("tay_nam",))
        self.assertTrue(
            {"qty", "unit_price", "total_qty", "line_total"} <= set(captured["fields"]),
            f"cross_row_fields chưa phủ field engine inject: {captured['fields']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
