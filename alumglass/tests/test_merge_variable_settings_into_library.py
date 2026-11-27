"""Test THUẦN cho patch `v1_0.merge_variable_settings_into_library` (B2/R3).

Không cần site: `frappe` được stub trong bộ nhớ, patch nạp lại bằng
`importlib` cho từng ca.

Bảo vệ 3 tính chất:
  1. Chép ĐỦ 2 bảng con sang Library, đúng dấu hiệu (`is_input` /
     `category = Row Literals`) và giữ `source_doctype`/`source_field`.
  2. ⛔ KHÔNG đè dữ liệu admin đã có (nhãn, default_value, is_system).
  3. Xung đột tên với biến HỆ THỐNG ⇒ báo, không ghi đè.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_merge_variable_settings_into_library.py
"""
import importlib.util
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

_PATCH_REL = "alumglass/patches/v1_0/merge_variable_settings_into_library.py"
_FAKE_MODULES = ("frappe",)

LIB = "AL Variable Library"
PROFILE = "AL Variable Profile"


class _FakeSettings:
    def __init__(self, common=None, rows=None, default_profile=None,
                 preview_doctype=None):
        self._tables = {
            "common_variables": common or [],
            "row_literals": rows or [],
        }
        self._values = {
            "default_profile": default_profile,
            "preview_doctype": preview_doctype,
        }

    def get(self, key):
        if key in self._tables:
            return self._tables[key]
        return self._values.get(key)

    def __getitem__(self, key):
        return self.get(key)


class _FakeNewDoc:
    def __init__(self, values, state):
        self.values = values
        self.flags = types.SimpleNamespace()
        self._state = state
        self.name = values.get("var_name")

    def insert(self):
        row = dict(self.values)
        row["name"] = self.name
        self._state["library"].append(row)
        self._state["inserted"].append(row)


class _FakeDB:
    def __init__(self, state):
        self.state = state

    def exists(self, doctype, name=None):
        if doctype == PROFILE:
            return True if name in self.state["profiles"] else None
        return None

    def has_column(self, doctype, column):
        return True

    def set_value(self, doctype, name, values, update_modified=True):
        self.state["set_values"].append((doctype, name, dict(values)))
        if doctype == LIB:
            for row in self.state["library"]:
                if row.get("name") == name or row.get("var_name") == name:
                    row.update(values)
        elif doctype == PROFILE:
            self.state["profile_updates"].update(values)

    def commit(self):
        self.state["commits"] += 1


def _library_row(name, **over):
    row = {
        "name": name, "var_name": name, "var_label": name,
        "var_type": "Float", "category": "Kích thước", "group_label": "",
        "sort_order": 0, "is_active": 1, "description": "",
        "source_doctype": "", "source_field": "", "default_value": "2400",
        "is_system": 0, "is_input": 0,
    }
    row.update(over)
    return row


def _default_state(**over):
    state = {
        "library": [
            _library_row("W_mm", var_label="Rộng", default_value="2400"),
            _library_row("weight_per_unit", category="",
                         default_value=None),
            _library_row("total_thick_mm", category="System",
                         is_system=1, var_label="Độ dày (hệ thống)"),
        ],
        "profiles": {"P_BOM_DEFAULT": {}},
        "profile_updates": {},
        "set_values": [],
        "inserted": [],
        "log_errors": [],
        "commits": 0,
        "settings": _FakeSettings(
            common=[
                {"var_name": "W_mm", "var_label": "Rộng", "var_type": "Float",
                 "group_label": "Thông số nhập", "sort_order": 10,
                 "is_active": 1, "description": ""},
                {"var_name": "NEW_COMMON", "var_label": "Biến mới",
                 "var_type": "Int", "group_label": "Thi công",
                 "sort_order": 20, "is_active": 1,
                 "description": "do người dùng nhập"},
            ],
            rows=[
                {"var_name": "weight_per_unit", "var_label": "TL riêng",
                 "var_type": "Float", "group_label": "Row Literals",
                 "sort_order": 10, "is_active": 1, "description": "",
                 "source_doctype": "Item", "source_field": "weight_per_unit"},
                {"var_name": "NEW_LITERAL", "var_label": "Literal mới",
                 "var_type": "Float", "group_label": "Row Literals",
                 "sort_order": 30, "is_active": 1, "description": "",
                 "source_doctype": "AL Glass Master",
                 "source_field": "total_thick_mm"},
                {"var_name": "total_thick_mm", "var_label": "Độ dày",
                 "var_type": "Float", "group_label": "Row Literals",
                 "sort_order": 40, "is_active": 1, "description": "",
                 "source_doctype": "AL Glass Master",
                 "source_field": "total_thick_mm"},
            ],
            default_profile="P_BOM_DEFAULT",
            preview_doctype="AL Bom Set",
        ),
    }
    state.update(over)
    return state


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.get_cached_doc = lambda doctype: state["settings"]
    frappe.get_all = lambda doctype, fields=None, order_by=None, **k: [
        dict(row) for row in state["library"]]
    frappe.get_doc = lambda values=None, *a, **k: _FakeNewDoc(
        dict(values or {}), state)
    frappe.log_error = lambda msg=None, title=None: state["log_errors"].append(
        (msg, title))
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    return frappe


def _load_patch(state):
    saved = {n: sys.modules.get(n) for n in _FAKE_MODULES}
    sys.modules["frappe"] = _build_frappe(state)
    sys.modules.pop("alumglass.patches.v1_0."
                    "merge_variable_settings_into_library", None)
    spec = importlib.util.spec_from_file_location(
        "alumglass.patches.v1_0.merge_variable_settings_into_library",
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


def _row(state, name):
    for row in state["library"]:
        if row.get("name") == name or row.get("var_name") == name:
            return row
    raise AssertionError("không có dòng %s" % name)


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.state = _default_state()
        self.patch, self.saved = _load_patch(self.state)
        self.patch.execute()

    def tearDown(self):
        _restore(self.saved)

    def test_chep_du_hai_bang_con(self):
        names = {row["var_name"] for row in self.state["library"]}
        self.assertIn("NEW_COMMON", names)
        self.assertIn("NEW_LITERAL", names)

    def test_common_co_co_is_input(self):
        row = _row(self.state, "NEW_COMMON")
        self.assertEqual(row["is_input"], 1)
        self.assertEqual(row["group_label"], "Thi công")
        self.assertEqual(row["group_label"], "Thi công")
        self.assertEqual(row["var_type"], "Int")

    def test_row_literal_dung_category_va_nguon(self):
        row = _row(self.state, "NEW_LITERAL")
        self.assertEqual(row["group_label"], "Row Literals")
        self.assertEqual(row["group_label"], "Row Literals")
        self.assertEqual(row["is_input"], 0)
        self.assertEqual(row["source_doctype"], "AL Glass Master")
        self.assertEqual(row["source_field"], "total_thick_mm")

    def test_dien_cho_trong_khong_de_du_lieu_admin(self):
        row = _row(self.state, "W_mm")
        self.assertEqual(row["is_input"], 1)
        self.assertEqual(row["group_label"], "Thông số nhập")
        # ⛔ không đè dữ liệu admin đã có.
        self.assertEqual(row["var_label"], "Rộng")
        self.assertEqual(row["default_value"], "2400")

    def test_dien_nguon_con_thieu_cho_row_literal_da_co(self):
        row = _row(self.state, "weight_per_unit")
        self.assertEqual(row["source_doctype"], "Item")
        self.assertEqual(row["source_field"], "weight_per_unit")
        self.assertEqual(row["group_label"], "Row Literals")

    def test_xung_dot_bien_he_thong_khong_ghi_de(self):
        row = _row(self.state, "total_thick_mm")
        self.assertEqual(row["is_system"], 1)
        self.assertEqual(row["category"], "System")
        self.assertEqual(row["var_label"], "Độ dày (hệ thống)")
        self.assertTrue(self.state["log_errors"])
        self.assertIn("total_thick_mm", self.state["log_errors"][0][0])

    def test_chuyen_ho_so_mac_dinh_va_preview(self):
        self.assertEqual(self.state["profile_updates"].get("is_default"), 1)
        self.assertEqual(self.state["profile_updates"].get("preview_doctype"),
                         "AL Bom Set")
        self.assertTrue(self.state["commits"])


class TestIdempotent(unittest.TestCase):
    def test_chay_hai_lan_khong_tao_them(self):
        state = _default_state()
        patch, saved = _load_patch(state)
        try:
            patch.execute()
            first = len(state["inserted"])
            patch.execute()
            second = len(state["inserted"])
        finally:
            _restore(saved)
        self.assertGreater(first, 0)
        self.assertEqual(second, first)

    def test_khong_co_settings_thi_bo_qua_va_khong_no(self):
        state = _default_state()
        # `get_cached_doc` ném ⇒ patch coi như site mới chưa seed.
        state["settings"] = None
        saved = {n: sys.modules.get(n) for n in _FAKE_MODULES}
        frappe = _build_frappe(state)
        frappe.get_cached_doc = lambda doctype: (_ for _ in ()).throw(
            RuntimeError("no doctype"))
        sys.modules["frappe"] = frappe
        spec = importlib.util.spec_from_file_location(
            "alumglass.patches.v1_0.merge_variable_settings_into_library",
            os.path.join(_APP_ROOT, _PATCH_REL))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        try:
            mod.execute()
        finally:
            _restore(saved)
        self.assertEqual(state["inserted"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
