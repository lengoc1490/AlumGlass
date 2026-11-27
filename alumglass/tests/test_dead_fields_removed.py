"""Test THUẦN cho B6/R5 — gỡ 6 ô chết + patch đếm dữ liệu cũ.

Hai việc kiểm:
  1. 6 field **không còn** trong JSON `AL Bom Item` / `AL Color Standard`
     (cả `fields` lẫn `field_order`), và JS không còn `set_query` trỏ tới.
  2. Patch `v1_0.count_dead_fields` **đếm được** dữ liệu cũ, **in + ghi log**
     khi có, và ⛔ **không ném** (gỡ field không làm mất cột; chặn migrate là
     phản ứng sai).

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_dead_fields_removed.py
"""
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

_BOM_REL = "alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.json"
_COLOR_REL = "alumglass/al_master_data/doctype/al_color_standard/al_color_standard.json"
_BOM_JS_REL = "alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.js"
_PATCH_REL = "alumglass/patches/v1_0/count_dead_fields.py"

DEAD_BOM = ("price_rule", "formula_set", "panel_count_formula",
            "qty_per_panel_formula", "panel_glass_override_allowed")
DEAD_COLOR = ("surcharge_rule",)


def _doc(rel):
    with open(os.path.join(_APP_ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


class TestFieldsRemoved(unittest.TestCase):
    def test_khong_con_trong_doctype_json(self):
        for rel, names in ((_BOM_REL, DEAD_BOM), (_COLOR_REL, DEAD_COLOR)):
            doc = _doc(rel)
            fields = {f.get("fieldname") for f in doc.get("fields", [])}
            order = set(doc.get("field_order") or [])
            for name in names:
                self.assertNotIn(name, fields, "%s còn trong fields" % name)
                self.assertNotIn(name, order, "%s còn trong field_order" % name)

    def test_json_van_hop_le(self):
        self.assertTrue(_doc(_BOM_REL).get("fields"))
        self.assertTrue(_doc(_COLOR_REL).get("fields"))

    def test_js_khong_con_set_query_price_rule(self):
        with open(os.path.join(_APP_ROOT, _BOM_JS_REL),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn('set_query("price_rule"', src)


# ══════════════════════════════════════════════════════════════════════
# Patch đếm — stub frappe
# ══════════════════════════════════════════════════════════════════════
class _FakeDB:
    def __init__(self, state):
        self.state = state

    def exists(self, doctype, name=None):
        if doctype == "DocType":
            return True if name in self.state["doctypes"] else None
        return True if doctype in self.state["doctypes"] else None

    def has_column(self, doctype, column):
        return column in self.state["columns"].get(doctype, set())

    def sql(self, query, *a, **k):
        for field, info in self.state["values"].items():
            if "`%s`" % field in query:
                if query.lower().startswith("select count(*)"):
                    return [(info["count"],)]
                return [(name,) for name in info["names"]]
        return [(0,)] if query.lower().startswith("select count(*)") else []


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.log_error = lambda msg, title=None: state["logs"].append(
        (msg, title))
    frappe.get_traceback = lambda: ""
    return frappe


def _load_patch(state):
    saved = {n: sys.modules.get(n) for n in ("frappe",)}
    sys.modules["frappe"] = _build_frappe(state)
    sys.modules.pop("alumglass.patches.v1_0.count_dead_fields", None)
    spec = importlib.util.spec_from_file_location(
        "alumglass.patches.v1_0.count_dead_fields",
        os.path.join(_APP_ROOT, _PATCH_REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved


def _restore(saved):
    for name, old in saved.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old


class TestCountPatch(unittest.TestCase):
    def _run(self, values):
        state = {
            "doctypes": {"AL Bom Item", "AL Color Standard"},
            "columns": {
                "AL Bom Item": set(DEAD_BOM),
                "AL Color Standard": set(DEAD_COLOR),
            },
            "values": values,
            "logs": [],
        }
        mod, saved = _load_patch(state)
        try:
            mod.execute()
        finally:
            _restore(saved)
        return state

    def test_dem_va_ghi_log_khi_co_du_lieu(self):
        state = self._run({
            "surcharge_rule": {"count": 2,
                               "names": ["BLACK", "WHITE"]},
        })
        self.assertTrue(state["logs"])
        msg = state["logs"][0][0]
        self.assertIn("AL Color Standard.surcharge_rule", msg)
        self.assertIn("2 dòng", msg)
        self.assertIn("BLACK", msg)

    def test_khong_no_khi_co_du_lieu(self):
        """Đối chứng âm: có dữ liệu vẫn KHÔNG được chặn migrate."""
        try:
            self._run({"price_rule": {"count": 5, "names": ["A"]}})
        except Exception as exc:
            self.fail("patch không được ném: %r" % exc)

    def test_cot_khong_ton_tai_thi_bo_qua(self):
        state = {
            "doctypes": {"AL Bom Item", "AL Color Standard"},
            "columns": {"AL Bom Item": set(), "AL Color Standard": set()},
            "values": {},
            "logs": [],
        }
        mod, saved = _load_patch(state)
        try:
            mod.execute()
        finally:
            _restore(saved)
        self.assertEqual(state["logs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
