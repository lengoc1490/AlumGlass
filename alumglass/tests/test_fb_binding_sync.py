"""Test THUẦN cho B4 — đồng bộ `Formula Variable Binding` từ master data.

Bốn điều phải giữ:
  1. Kế hoạch đúng: hằng số số → binding `constant` toàn cục; biến hệ có nguồn
     `AL Profile System` / `AL Product Type` → binding `linked_doctype_field`
     ở phạm vi `AL Bom Set`.
  2. ⛔ seed bừa: hằng số không phải kiểu số, biến hệ có nguồn lạ, biến thiếu
     `source_field` ⇒ KHÔNG vào kế hoạch.
  3. `dry_run` ⛔ ghi gì; chạy thật thì tạo; chạy lần hai ⛔ tạo trùng.
  4. Một binding lỗi ⛔ chặn các binding khác.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_fb_binding_sync.py
"""
import importlib.util
import json
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_REL = "alumglass/fb_binding_sync.py"


class _FakeDB:
    def __init__(self, state):
        self.state = state

    def exists(self, doctype, filters=None):
        key = (
            (filters or {}).get("variable_name"),
            (filters or {}).get("applies_to_doctype") or "",
            int((filters or {}).get("is_global") or 0),
        )
        return True if key in self.state["existing"] else None

    def commit(self):
        self.state["commits"] += 1


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)

    def get_all(doctype, filters=None, fields=None, **kw):
        return state["rows"].get(doctype, [])

    def get_doc(values):
        state["docs"].append(values)
        key = (values["variable_name"], values.get("applies_to_doctype") or "",
               int(values.get("is_global") or 0))
        if key in state["raise_on"]:
            raise RuntimeError("giả lập lỗi insert")
        state["existing"].add(key)
        return types.SimpleNamespace(insert=lambda **k: None)

    frappe.get_all = get_all
    frappe.get_doc = get_doc
    frappe.as_json = json.dumps
    frappe.get_traceback = lambda: ""
    frappe.log_error = lambda msg, title=None: state["logs"].append(msg)
    return frappe


def _load(state):
    saved = {n: sys.modules.get(n) for n in ("frappe",)}
    sys.modules["frappe"] = _build_frappe(state)
    name = "alumglass.fb_binding_sync"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, os.path.join(_APP_ROOT, _REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved


def _restore(saved):
    for name, old in saved.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old


def _state():
    return {
        "rows": {
            "Formula Global Variable": [
                {"var_name": "VAT_RATE", "label": "Thuế VAT", "var_type": "Float",
                 "constant_value": "10"},
                {"var_name": "GHI_CHU", "label": "Ghi chú", "var_type": "Data",
                 "constant_value": "abc"},
                {"var_name": "TRONG", "label": "Rỗng", "var_type": "Float",
                 "constant_value": ""},
            ],
            "AL Variable Library": [
                {"var_name": "OFFSET_FRAME", "var_label": "Offset khung",
                 "var_type": "Float", "source_doctype": "AL Profile System",
                 "source_field": "offset_frame", "default_value": "0"},
                {"var_name": "NC_SX_PCT", "var_label": "NC SX",
                 "var_type": "Float", "source_doctype": "AL Product Type",
                 "source_field": "nc_sx_pct", "default_value": ""},
                {"var_name": "LA_SO", "var_label": "Nguồn lạ",
                 "var_type": "Float", "source_doctype": "Item",
                 "source_field": "weight_per_unit", "default_value": ""},
                {"var_name": "THIEU_FIELD", "var_label": "Thiếu field",
                 "var_type": "Float", "source_doctype": "AL Profile System",
                 "source_field": "", "default_value": ""},
            ],
        },
        "existing": set(),
        "raise_on": set(),
        "docs": [],
        "logs": [],
        "commits": 0,
    }


class TestPlan(unittest.TestCase):
    def test_ke_hoach_dung(self):
        state = _state()
        mod, saved = _load(state)
        try:
            planned = mod.plan()
        finally:
            _restore(saved)
        by_name = {p["variable_name"]: p for p in planned}
        self.assertEqual(set(by_name), {"VAT_RATE", "OFFSET_FRAME", "NC_SX_PCT"})

        vat = by_name["VAT_RATE"]
        self.assertEqual(vat["source_type"], "constant")
        self.assertEqual(vat["is_global"], 1)
        self.assertEqual(vat["applies_to_doctype"], "")
        self.assertEqual(vat["source_config"], {"value": "10"})

        off = by_name["OFFSET_FRAME"]
        self.assertEqual(off["source_type"], "linked_doctype_field")
        self.assertEqual(off["applies_to_doctype"], "AL Bom Set")
        self.assertEqual(off["source_config"], {
            "link_field": "profile_system",
            "target_doctype": "AL Profile System",
            "target_field": "offset_frame",
        })

    def test_bo_qua_hang_khong_dung(self):
        state = _state()
        mod, saved = _load(state)
        try:
            names = {p["variable_name"] for p in mod.plan()}
        finally:
            _restore(saved)
        for bad in ("GHI_CHU", "TRONG", "LA_SO", "THIEU_FIELD"):
            self.assertNotIn(bad, names)


class TestSync(unittest.TestCase):
    def test_dry_run_khong_ghi(self):
        state = _state()
        mod, saved = _load(state)
        try:
            result = mod.sync(dry_run=True)
        finally:
            _restore(saved)
        self.assertEqual(state["docs"], [])
        self.assertEqual(state["commits"], 0)
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["planned"]), 3)

    def test_tao_roi_lan_hai_khong_trung(self):
        state = _state()
        mod, saved = _load(state)
        try:
            first = mod.sync(dry_run=False)
            second = mod.sync(dry_run=False)
        finally:
            _restore(saved)
        self.assertEqual(sorted(first["created"]),
                         ["NC_SX_PCT", "OFFSET_FRAME", "VAT_RATE"])
        self.assertEqual(second["created"], [])
        self.assertEqual(len(state["docs"]), 3)
        self.assertEqual(state["commits"], 1)

    def test_mot_binding_loi_khong_chan_cai_khac(self):
        state = _state()
        state["raise_on"] = {("OFFSET_FRAME", "AL Bom Set", 0)}
        mod, saved = _load(state)
        try:
            result = mod.sync(dry_run=False)
        finally:
            _restore(saved)
        self.assertEqual(sorted(result["created"]), ["NC_SX_PCT", "VAT_RATE"])
        self.assertIn("OFFSET_FRAME", result["skipped"])
        self.assertTrue(state["logs"], "lỗi phải được ghi log, ⛔ nuốt im lặng")


if __name__ == "__main__":
    unittest.main(verbosity=2)
