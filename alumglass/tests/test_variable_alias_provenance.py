# -*- coding: utf-8 -*-
"""Test THUẦN cho Pha 1 — alias độ dày kính + nguồn biến + patch v28_15.

Không cần site: `frappe` được stub trong bộ nhớ và KHÔI PHỤC nguyên trạng khi
thoát (cùng khuôn `test_build_references_cross_row.py`) — nhờ vậy file nằm
trong package `alumglass/tests/` mà `bench run-tests` vẫn collect được.

Phủ:
  1. `field_provenance` — bảng nguồn + ghi đè theo dòng.
  2. Adapter `row_literal` — `value_source`/`provenance` có "Nguồn: …".
  3. `_append_references` — nhãn gợi ý chéo dòng kèm nguồn.
  4. `_resolve_rule_input_for_item` — `total_thick_mm` và alias `glass_thick`
     trả CÙNG giá trị cho cùng một dòng kính.
  5. Patch v28_15 — chạy 2 lần không nhân đôi dòng/field, chỉ đổi nhãn cũ.

CÁCH CHẠY
---------
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_variable_alias_provenance.py
Hoặc qua bench:
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_variable_alias_provenance
"""
import importlib
import importlib.util
import json
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

_TOUCHED_MODULES = (
    "frappe",
    "frappe.model",
    "frappe.model.document",
    "alumglass",
    "alumglass.engine",
    "alumglass.engine.bom_orchestrator",
    "alumglass.al_bom_engine",
    "alumglass.al_bom_engine.glass_group_resolver",
    "alumglass.al_bom_engine.color_group_resolver",
    "alumglass.variable_sources",
    "alumglass.variable_sources.registry",
    "alumglass.variable_sources.rules",
    "alumglass.variable_sources.context",
    "alumglass.variable_sources.field_provenance",
    "alumglass.variable_sources.adapters",
    "alumglass.patches",
    "alumglass.patches.v28_15",
    "alumglass.patches.v28_15.sync_variable_sources_and_fields",
)


class FakeRow(dict):
    """Dòng child table: vừa `row.get(...)` vừa `row.field = ...`."""

    def __getattr__(self, name):
        return self.get(name)

    def __setattr__(self, name, value):
        self[name] = value


class FakeSettings(object):
    """AL Variable Settings tối thiểu: append + save + đếm lần ghi."""

    def __init__(self, row_literals):
        self._rows = [FakeRow(r) for r in row_literals]
        self.saved = 0
        self.flags = types.SimpleNamespace()

    def get(self, key, default=None):
        if key == "row_literals":
            return self._rows
        return default

    def append(self, key, row):
        if key != "row_literals":
            raise AssertionError("unexpected append key: %s" % key)
        self._rows.append(FakeRow(row))

    def save(self):
        self.saved += 1


class FakeProfile(object):
    def __init__(self, name, cross_rows):
        self.name = name
        self._cross = [FakeRow(r) for r in cross_rows]
        self.saved = 0
        self.flags = types.SimpleNamespace()

    def get(self, key, default=None):
        if key == "cross_row":
            return self._cross
        return default

    def save(self):
        self.saved += 1


class FakeDB(object):
    def exists(self, *args, **kwargs):
        return True

    def has_column(self, *args, **kwargs):
        return True

    def commit(self):
        pass


def _build_frappe_stub():
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = FakeDB()
    frappe.get_all = lambda *a, **k: []
    frappe.get_single = lambda *a, **k: None
    frappe.get_doc = lambda *a, **k: None
    frappe.get_cached_doc = lambda *a, **k: None
    frappe.log_error = lambda *a, **k: None
    frappe.logger = lambda *a, **k: types.SimpleNamespace(
        error=lambda *aa, **kk: None,
        warning=lambda *aa, **kk: None,
        info=lambda *aa, **kk: None)
    frappe.get_traceback = lambda: ""
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    frappe.whitelist = lambda *a, **k: (lambda fn: fn)
    frappe._ = lambda s: s
    frappe.local = types.SimpleNamespace()
    frappe.conf = {}

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")

    class Document(object):
        pass

    document.Document = Document
    model.document = document
    frappe.model = model
    return frappe


def _build_context_stub():
    ctx = types.ModuleType("alumglass.variable_sources.context")
    ctx.detect_slug_field = lambda child_doctype: "slug"
    ctx.get_field_label = lambda doctype, fieldname: fieldname or ""
    ctx.get_scalar_fieldnames = lambda doctype: []
    return ctx


class _Stubbed(object):
    """Cài stub + nạp module, KHÔI PHỤC nguyên trạng khi thoát."""

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        self._saved = {n: sys.modules.get(n) for n in _TOUCHED_MODULES}
        frappe = _build_frappe_stub()
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = frappe.model
        sys.modules["frappe.model.document"] = frappe.model.document
        # Xoá module cũ để import lại với stub mới (tránh dính frappe thật
        # nếu test khác đã nạp trước).
        for name in list(sys.modules):
            if name == "alumglass" or name.startswith("alumglass."):
                if name not in self._saved or self._saved.get(name) is None:
                    sys.modules.pop(name, None)
        sys.modules["alumglass.variable_sources.context"] = _build_context_stub()
        return frappe

    def __exit__(self, *exc):
        for name, old in self._saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        return False


# ══════════════════════════════════════════════════════════════════════
# 1. field_provenance
# ══════════════════════════════════════════════════════════════════════
class TestFieldProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stub = _Stubbed()
        cls._stub.__enter__()
        try:
            from alumglass.variable_sources import field_provenance as fp
            cls.fp = fp
        except Exception:
            cls._stub.__exit__(None, None, None)
            raise

    @classmethod
    def tearDownClass(cls):
        cls._stub.__exit__(None, None, None)

    def test_standard_map(self):
        self.assertEqual(
            self.fp.describe_source("total_thick_mm"),
            "AL Glass Master.total_thick_mm")
        # Alias cũ trỏ CÙNG field nguồn ⇒ cùng giá trị, khác nhãn.
        self.assertEqual(
            self.fp.describe_source("glass_thick"),
            "AL Glass Master.total_thick_mm")
        self.assertEqual(
            self.fp.describe_source("max_area_m2"),
            "AL Glass Master.max_area_m2")
        self.assertEqual(
            self.fp.describe_source("scrap_pct"),
            "AL Material Category.default_scrap_pct")
        self.assertEqual(
            self.fp.describe_source("unit_price"),
            "Item Price.price_list_rate")
        self.assertEqual(
            self.fp.describe_source("weight_per_unit"),
            "Item.weight_per_unit")
        self.assertEqual(
            self.fp.describe_source("calc_pattern"),
            "AL Bom Item.calc_pattern")
        self.assertEqual(
            self.fp.describe_source("has_weight"),
            "AL Material Category.has_weight")

    def test_row_override_wins(self):
        row = {"source_doctype": "Custom Doc", "source_field": "custom_field"}
        self.assertEqual(
            self.fp.describe_source("total_thick_mm", row),
            "Custom Doc.custom_field")
        # Chỉ khai 1 nửa ⇒ KHÔNG dùng (tránh nguồn nửa vời) — rơi về bảng.
        self.assertEqual(
            self.fp.describe_source(
                "total_thick_mm", {"source_doctype": "X", "source_field": ""}),
            "AL Glass Master.total_thick_mm")

    def test_unknown_var_and_note(self):
        self.assertEqual(self.fp.describe_source("khong_co"), "")
        self.assertEqual(self.fp.provenance_note("khong_co"), "")
        self.assertEqual(
            self.fp.provenance_note("glass_thick"),
            "Nguồn: AL Glass Master.total_thick_mm")


# ══════════════════════════════════════════════════════════════════════
# 2-3. Adapter row_literal + references
# ══════════════════════════════════════════════════════════════════════
class FakeCtx(object):
    doctype = "AL Bom Set"

    def __init__(self, rows=None, settings_rows=None):
        self._rows = list(rows or [])
        self._settings_rows = list(settings_rows or [])

    def get_doc(self):
        return self

    def get(self, key, default=None):
        return self._rows if key == "items" else default

    def get_current_row(self):
        return None

    def get_settings_table(self, name):
        return self._settings_rows if name == "row_literals" else []

    def get_child_rows(self, table_field=None):
        return self._rows if table_field == "items" else []

    def get_child_doctype(self, table_field):
        return "AL Bom Item" if table_field == "items" else None


class TestAdapterProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stub = _Stubbed()
        cls._stub.__enter__()
        try:
            cls.adapters = importlib.import_module(
                "alumglass.variable_sources.adapters")
        except Exception:
            cls._stub.__exit__(None, None, None)
            raise

    @classmethod
    def tearDownClass(cls):
        cls._stub.__exit__(None, None, None)

    def test_row_literal_standard_source(self):
        ctx = FakeCtx(settings_rows=[
            {"var_name": "glass_thick", "var_label": "Độ dày kính (tên cũ)",
             "var_type": "Float", "is_active": 1},
        ])
        candidates = self.adapters.row_literal(ctx)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["value_source"],
                         "Nguồn: AL Glass Master.total_thick_mm")
        self.assertIn("Nguồn: AL Glass Master.total_thick_mm",
                      candidates[0]["provenance"])

    def test_row_literal_row_override(self):
        ctx = FakeCtx(settings_rows=[
            {"var_name": "custom_x", "is_active": 1,
             "source_doctype": "My Doc", "source_field": "my_field"},
        ])
        candidate = self.adapters.row_literal(ctx)[0]
        self.assertEqual(candidate["value_source"],
                         "Nguồn: My Doc.my_field")

    def test_row_literal_unknown_var_keeps_old_text(self):
        ctx = FakeCtx(settings_rows=[
            {"var_name": "unit_qty", "is_active": 1},
        ])
        candidate = self.adapters.row_literal(ctx)[0]
        # UX (B11): câu người đọc, ⛔ không lộ tên lớp/phase nội bộ.
        self.assertEqual(
            candidate["value_source"],
            "Hệ thống tự điền khi tính giá")

    def test_reference_labels_include_source(self):
        ctx = FakeCtx(rows=[{"slug": "kinh_tren", "item_code": "KINH-01"}])
        profile = {"cross_row": [{
            "table_field": "items",
            "id_field": "slug",
            "label_field": "item_code",
            "fields": json.dumps(
                ["width", "glass_thick", "total_thick_mm", "max_area_m2"]),
            "include_index_form": 1,
            "enabled": 1,
        }]}
        refs = self.adapters.build_references(ctx, profile)
        by_name = {r["name"]: r for r in refs}

        # Alias `glass_thick` là TÊN CŨ của chính field nguồn — UX (B12)
        # không lặp hậu tố nguồn, tránh một dòng hai lần "nguồn".
        self.assertNotIn(
            "(nguồn:", by_name["items.kinh_tren.glass_thick"]["label"])
        self.assertIn(
            "(nguồn: AL Glass Master.total_thick_mm)",
            by_name["items.kinh_tren.total_thick_mm"]["label"])
        self.assertIn(
            "(nguồn: AL Glass Master.max_area_m2)",
            by_name["items[0].max_area_m2"]["label"])
        # `width` là field công thức của chính dòng — không có nguồn ngoài.
        self.assertNotIn("(nguồn:", by_name["items.kinh_tren.width"]["label"])


# ══════════════════════════════════════════════════════════════════════
# 4. Alias khi resolve rule_input_expr
# ══════════════════════════════════════════════════════════════════════
class TestRuleInputAlias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stub = _Stubbed()
        cls._stub.__enter__()
        try:
            from alumglass.engine.bom_orchestrator import BomOrchestrator
            cls.BomOrchestrator = BomOrchestrator
        except Exception:
            cls._stub.__exit__(None, None, None)
            raise

    @classmethod
    def tearDownClass(cls):
        cls._stub.__exit__(None, None, None)

    def test_both_names_same_value_same_item(self):
        orch = self.BomOrchestrator("QI-TEST")
        glass_data = {"kinh_tren": {
            "total_thick_mm": 8,
            "glass_thick": 8,          # alias cũ — cùng giá trị
            "glass_type": "Temper",
            "max_area_m2": 6.6,
        }}
        item_new = {"rule_input_expr": "items.kinh_tren.total_thick_mm"}
        item_old = {"rule_input_expr": "items.kinh_tren.glass_thick"}
        self.assertEqual(
            orch._resolve_rule_input_for_item(item_new, glass_data), 8)
        self.assertEqual(
            orch._resolve_rule_input_for_item(item_old, glass_data), 8)

    def test_max_area_resolves(self):
        orch = self.BomOrchestrator("QI-TEST")
        glass_data = {"kinh_tren": {
            "total_thick_mm": 8, "glass_thick": 8, "max_area_m2": 6.6}}
        item = {"rule_input_expr": "items.kinh_tren.max_area_m2"}
        self.assertEqual(
            orch._resolve_rule_input_for_item(item, glass_data), 6.6)

    def test_fallback_to_row_literals(self):
        """Không truyền glass_data → đọc row_literals (đã có alias)."""
        orch = self.BomOrchestrator("QI-TEST")
        orch.row_literals = {
            "kinh_tren": {"total_thick_mm": 10, "glass_thick": 10}}
        item = {"rule_input_expr": "items.kinh_tren.total_thick_mm"}
        self.assertEqual(orch._resolve_rule_input_for_item(item), 10)


# ══════════════════════════════════════════════════════════════════════
# 5. Patch v28_15 — idempotent
# ══════════════════════════════════════════════════════════════════════
class TestPatchV2815(unittest.TestCase):
    def setUp(self):
        self._stub = _Stubbed()
        self.frappe = self._stub.__enter__()
        self.settings = FakeSettings([
            # Nhãn vẫn là seed cũ → phải đổi.
            {"var_name": "glass_thick", "var_label": "Độ dày kính",
             "var_type": "Float", "is_active": 1},
            # Chưa có nguồn → phải điền.
            {"var_name": "unit_price", "var_label": "Đơn giá",
             "var_type": "Float", "is_active": 1},
            # Đã có nguồn tay → PHẢI giữ nguyên.
            {"var_name": "scrap_pct", "var_label": "% Hao hụt",
             "var_type": "Float", "is_active": 1,
             "source_doctype": "My Category", "source_field": "scrap"},
            # max_area_m2 đã có (v28_14 bản trước có thể đã seed).
            {"var_name": "max_area_m2", "var_label": "Khổ kính tối đa (m²)",
             "var_type": "Float", "is_active": 1},
        ])
        self.profiles = {
            "P_BOM_DEFAULT": FakeProfile("P_BOM_DEFAULT", [
                {"table_field": "items",
                 "fields": json.dumps(["width", "glass_thick"])},
            ]),
            "P_EMPTY": FakeProfile("P_EMPTY", [
                {"table_field": "items", "fields": ""},
            ]),
            "P_NO_CROSS": FakeProfile("P_NO_CROSS", []),
        }
        self.frappe.get_single = lambda *a, **k: self.settings
        self.frappe.get_all = lambda doctype, *a, **k: (
            list(self.profiles) if doctype == "AL Variable Profile" else [])
        self.frappe.get_doc = lambda doctype, name: self.profiles[name]
        self.patch = importlib.import_module(
            "alumglass.patches.v28_15.sync_variable_sources_and_fields")

    def tearDown(self):
        self._stub.__exit__(None, None, None)

    def test_row_literals_idempotent(self):
        self.patch._sync_row_literals()
        rows = self.settings.get("row_literals")
        names = [r.get("var_name") for r in rows]

        # Thêm đúng 1 dòng (total_thick_mm); max_area_m2 đã có.
        self.assertEqual(names.count("total_thick_mm"), 1)
        self.assertEqual(names.count("max_area_m2"), 1)

        by_name = {r.get("var_name"): r for r in rows}
        self.assertEqual(by_name["glass_thick"].get("var_label"),
                         "Độ dày kính (tên cũ)")
        self.assertEqual(by_name["glass_thick"].get("source_field"),
                         "total_thick_mm")
        self.assertEqual(by_name["unit_price"].get("source_doctype"),
                         "Item Price")
        # Nguồn khai tay KHÔNG bị đè.
        self.assertEqual(by_name["scrap_pct"].get("source_doctype"),
                         "My Category")
        self.assertEqual(by_name["scrap_pct"].get("source_field"), "scrap")
        self.assertEqual(self.settings.saved, 1)

        # Lần 2: không thay đổi gì.
        self.patch._sync_row_literals()
        self.assertEqual([r.get("var_name") for r in rows], names)
        self.assertEqual(self.settings.saved, 1)

    def test_profiles_idempotent(self):
        self.patch._sync_profiles()
        profile = self.profiles["P_BOM_DEFAULT"]
        fields = json.loads(profile.get("cross_row")[0].get("fields"))
        self.assertIn("total_thick_mm", fields)
        self.assertIn("max_area_m2", fields)
        self.assertEqual(fields.count("total_thick_mm"), 1)
        self.assertEqual(profile.saved, 1)

        # `fields` rỗng = "mọi field" — KHÔNG được biến thành allowlist.
        self.assertEqual(
            self.profiles["P_EMPTY"].get("cross_row")[0].get("fields"), "")
        self.assertEqual(self.profiles["P_EMPTY"].saved, 0)
        self.assertEqual(self.profiles["P_NO_CROSS"].saved, 0)

        self.patch._sync_profiles()
        self.assertEqual(profile.saved, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
