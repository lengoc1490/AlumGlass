# -*- coding: utf-8 -*-
"""cross_row_fields của AL Bom Set validate — phủ đúng field engine B3 inject.

Bối cảnh: `ALBomSet._validate_child_formulas()` từng truyền
`cross_row_fields=FORMULA_FIELDS` ("width","height","qty","show_condition")
cho `build_known_names` ⇒ công thức `items.<slug>.unit_price`,
`items.<slug>.glass_thick`, `items.<slug>.total_qty`... CHẠY ĐƯỢC lúc
runtime (engine `b3_build_formulas` inject thật) nhưng bị validate chặn oan
"Biến không khai báo". Từ bản vá này, `cross_row_fields` là superset:
FORMULA_FIELDS + row literal đang bật (AL Variable Settings) + synthetic
`unit_qty/total_qty/line_total`.

CÁCH CHẠY
---------
Không cần site (tự stub frappe + catalog như test_safe_eval_a3.py):
    python3 alumglass/tests/test_bom_set_cross_row_known_fields.py
Hoặc qua bench:
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_bom_set_cross_row_known_fields
"""
import importlib.util
import os
import sys
import types
import unittest


# ── Stub tối thiểu khi chạy standalone (không có site / không có frappe) ──
_USED_FAKE_MODULES = (
    "frappe",
    "frappe.model",
    "frappe.model.document",
    "alumglass",
    "alumglass.al_bom_engine",
    "alumglass.al_bom_engine.doctype",
    "alumglass.al_bom_engine.doctype.al_bom_item",
    "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item",
    "alumglass.al_bom_engine.doctype.al_bom_set",
    "alumglass.al_bom_engine.doctype.al_bom_set.al_bom_set",
    "alumglass.al_bom_engine.formula_validate",
    "alumglass.api",
    "alumglass.api.variable_catalog",
    "alumglass.al_formula_rules",
    "alumglass.al_formula_rules.rule_engine",
    "alumglass.al_formula_rules.rule_input",
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_source(module_name, rel_path):
    """Nạp 1 file .py theo đường dẫn thành module mang tên `module_name`."""
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_REPO_ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _LoadWithStubs:
    """Nạp al_bom_set.py + al_bom_item.py THẬT, stub các phụ thuộc bên ngoài.

    Chỉ dùng khi môi trường KHÔNG có frappe (chạy `python3` trần). Mọi module
    ghi vào `sys.modules` được khôi phục nguyên trạng khi thoát context.
    """

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        self._saved = {name: sys.modules.get(name) for name in _USED_FAKE_MODULES}

        frappe = types.ModuleType("frappe")
        frappe.__path__ = []
        frappe.whitelist = lambda *a, **k: (lambda fn: fn)
        frappe.throw = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError(a[0] if a else "frappe.throw"))
        frappe.msgprint = lambda *a, **k: None
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

        # Package alumglass — chỉ cần `__path__` để import lồng nhau qua spec.
        for name in ("alumglass", "alumglass.al_bom_engine",
                     "alumglass.al_bom_engine.doctype",
                     "alumglass.al_bom_engine.doctype.al_bom_item",
                     "alumglass.al_bom_engine.doctype.al_bom_set",
                     "alumglass.api"):
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            sys.modules[name] = pkg

        # formula_validate: stub — test này chỉ kiểm WIRING cross_row_fields,
        # logic build_known_names/FormulaValidator không thuộc phạm vi.
        fv = types.ModuleType("alumglass.al_bom_engine.formula_validate")
        fv.build_known_names = lambda *a, **k: set()
        fv.check_formula_fields = lambda *a, **k: []
        fv.validate_rule_input_expr = lambda *a, **k: []
        # al_bom_set.py (HEAD) import thêm 4 hàm này — thiếu stub thì test
        # nổ ImportError trước khi kiểm được gì (hỏng sẵn, không liên quan B2).
        fv.load_rule_meta = lambda *a, **k: {}
        fv.lookup_rule_codes = lambda *a, **k: []
        fv.row_reference_label = lambda *a, **k: ""
        fv.validate_lookup_rule_codes = lambda *a, **k: []
        sys.modules["alumglass.al_bom_engine.formula_validate"] = fv

        # catalog: giá trị mặc định, test tự đổi qua `catalog.get_row_literal_names`.
        catalog = types.ModuleType("alumglass.api.variable_catalog")
        catalog.get_row_literal_names = lambda: []
        sys.modules["alumglass.api.variable_catalog"] = catalog
        sys.modules["alumglass.api"].variable_catalog = catalog
        self.catalog = catalog

        # al_bom_set.py (HEAD) import `rule_engine` cho NHÃN câu cảnh báo.
        # Stub đủ hàm được gọi; logic không thuộc phạm vi test wiring này.
        pkg = types.ModuleType("alumglass.al_formula_rules")
        pkg.__path__ = []
        rule_engine = types.ModuleType("alumglass.al_formula_rules.rule_engine")
        rule_engine.rule_input_label = lambda *a, **k: ""
        rule_engine.INPUT_LABEL_FALLBACK = "dữ liệu quy tắc đọc"
        rule_input = types.ModuleType(
            "alumglass.al_formula_rules.rule_input")
        rule_input.find_bare_row_variables = lambda *a, **k: []
        pkg.rule_engine = rule_engine
        pkg.rule_input = rule_input
        sys.modules["alumglass.al_formula_rules"] = pkg
        sys.modules["alumglass.al_formula_rules.rule_engine"] = rule_engine
        sys.modules["alumglass.al_formula_rules.rule_input"] = rule_input

        _load_source(
            "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item",
            "alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.py")
        self.al_bom_set = _load_source(
            "alumglass.al_bom_engine.doctype.al_bom_set.al_bom_set",
            "alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.py")
        return self

    def __exit__(self, *exc):
        for name, old in self._saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        return False


class TestCrossRowKnownFields(unittest.TestCase):
    """Helper `_cross_row_known_fields()` + wiring trong `_validate_child_formulas`."""

    def setUp(self):
        self._ctx = _LoadWithStubs().__enter__()
        self.mod = self._ctx.al_bom_set
        self.item_mod = sys.modules[
            "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item"]
        self.catalog = self._ctx.catalog

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    # ── Helper ────────────────────────────────────────────────────────
    def test_base_fields_always_present(self):
        """Luôn có FORMULA_FIELDS + synthetic engine (kể cả catalog rỗng)."""
        fields = set(self.mod._cross_row_known_fields())
        self.assertTrue(set(self.item_mod.FORMULA_FIELDS) <= fields)
        self.assertTrue(
            {"unit_qty", "total_qty", "line_total"} <= fields,
            f"Thiếu synthetic engine: {fields}")

    def test_row_literals_from_catalog(self):
        """Row literal đang bật trong AL Variable Settings được bổ sung."""
        self.catalog.get_row_literal_names = lambda: [
            "unit_price", "glass_thick", "glass_type"]
        fields = set(self.mod._cross_row_known_fields())
        self.assertTrue(
            {"unit_price", "glass_thick", "glass_type"} <= fields,
            f"Thiếu row literal: {fields}")

    def test_catalog_empty_or_none(self):
        """Catalog rỗng / None → vẫn trả base, KHÔNG nổ."""
        for value in ([], None, ()):
            self.catalog.get_row_literal_names = lambda v=value: v
            fields = set(self.mod._cross_row_known_fields())
            self.assertTrue(set(self.item_mod.FORMULA_FIELDS) <= fields)

    def test_catalog_failure_ignored(self):
        """Catalog lỗi (site chưa migrate / thiếu helper) → bỏ qua nguồn đó."""
        def _boom():
            raise ImportError("chưa có helper")
        self.catalog.get_row_literal_names = _boom
        fields = set(self.mod._cross_row_known_fields())
        self.assertIn("unit_qty", fields)

    def test_sorted_tuple_no_duplicates(self):
        """Trả tuple đã sắp xếp, không trùng (build_known_names lặp slug × field)."""
        self.catalog.get_row_literal_names = lambda: ["unit_price", "unit_price"]
        fields = self.mod._cross_row_known_fields()
        self.assertIsInstance(fields, tuple)
        self.assertEqual(list(fields), sorted(set(fields)))

    # ── Wiring trong validate ─────────────────────────────────────────
    def test_validate_passes_superset_to_build_known_names(self):
        """`_validate_child_formulas` truyền SUPERSET, không phải FORMULA_FIELDS trơ."""
        self.catalog.get_row_literal_names = lambda: ["unit_price", "glass_thick"]
        captured = {}

        def _fake_build_known_names(doctype, docname, cross_row_slugs=None,
                                    cross_row_fields=None, fieldname=None):
            captured["fields"] = tuple(cross_row_fields or ())
            captured["slugs"] = tuple(cross_row_slugs or ())
            return set()

        self.mod.build_known_names = _fake_build_known_names
        self.mod.check_formula_fields = lambda *a, **k: []

        doc = self.mod.ALBomSet.__new__(self.mod.ALBomSet)
        doc.name = "TEST-BOM-SET"
        doc.items = [types.SimpleNamespace(
            slug="kinh_tren", idx=1, item_selection_mode="Rule")]

        doc._validate_child_formulas()

        self.assertEqual(captured["slugs"], ("kinh_tren",))
        self.assertTrue(
            {"unit_price", "glass_thick", "unit_qty", "total_qty",
             "line_total"} <= set(captured["fields"]),
            f"cross_row_fields chưa phủ field engine inject: {captured['fields']}")

    def test_validate_still_validates_formula_fields_only(self):
        """Mở rộng known_names, KHÔNG đổi danh sách field bị validate chính."""
        validated = []

        self.mod.build_known_names = lambda *a, **k: set()

        def _fake_check(item, fields, known_names, allow_cross_row=False):
            validated.append(tuple(fields))
            return []

        self.mod.check_formula_fields = _fake_check

        doc = self.mod.ALBomSet.__new__(self.mod.ALBomSet)
        doc.name = "TEST-BOM-SET"
        doc.items = [types.SimpleNamespace(
            slug="kinh_tren", idx=1, item_selection_mode="Rule")]

        doc._validate_child_formulas()

        self.assertEqual(validated, [tuple(self.item_mod.FORMULA_FIELDS)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
