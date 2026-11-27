"""Test THUẦN cho `variable_sources.catalog_rows` (B2/R3).

Trọng tâm: BA LOẠI BIẾN RỜI NHAU. Nếu `user_variables` nuốt row literal thì
hồ sơ BOM (đã mở `variable_library_user` ở B3b) sẽ mời người dùng viết
`unit_price` — công thức B4 chạy ra 0 âm thầm.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_catalog_rows.py
"""
import importlib
import importlib.util
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

_MOD_REL = "alumglass/variable_sources/catalog_rows.py"

_FAKE_MODULES = ("frappe",)


def _lib_row(name, **over):
    row = {
        "name": name, "var_name": name, "var_label": name,
        "var_type": "Float", "group_label": "Kích thước",
        "sort_order": 0, "is_active": 1, "description": "",
        "source_doctype": "", "source_field": "", "default_value": None,
        "is_input": 0,
    }
    row.update(over)
    return row


def _settings_row(name, **over):
    """Dòng của bảng Settings CŨ — chỉ để chứng minh nó ⛔ còn được đọc."""
    row = {
        "var_name": name, "var_label": name, "var_type": "Float",
        "group_label": "Thông số nhập", "sort_order": 10,
        "is_active": 1, "description": "",
        "source_doctype": "", "source_field": "",
    }
    row.update(over)
    return row


class _FakeSettings:
    def __init__(self, common, rows):
        self._common = common
        self._rows = rows

    def get(self, table):
        return self._common if table == "common_variables" else self._rows


class _FakeDB:
    def __init__(self, state):
        self.state = state

    def has_column(self, doctype, column):
        return self.state["migrated"]

    def exists(self, doctype, filters=None):
        # `catalog_rows` chốt mốc bằng Patch Log — stub trả cùng cờ.
        return True if self.state["migrated"] else None


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.get_all = lambda doctype, filters=None, fields=None, **k: [
        dict(row) for row in state["library"]]
    frappe.get_cached_doc = lambda doctype: state["settings"]
    frappe.log_error = lambda *a, **k: None
    return frappe


def _load(state):
    saved = {n: sys.modules.get(n) for n in _FAKE_MODULES}
    sys.modules["frappe"] = _build_frappe(state)
    sys.modules.pop("alumglass.variable_sources.catalog_rows", None)
    spec = importlib.util.spec_from_file_location(
        "alumglass.variable_sources.catalog_rows",
        os.path.join(_APP_ROOT, _MOD_REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved


def _restore(saved):
    for name, old in saved.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old


def _default_state(**over):
    state = {
        "migrated": True,
        "library": [
            _lib_row("W_mm", is_input=1),
            _lib_row("unit_price", group_label="Row Literals"),
            _lib_row("glass_master", group_label="Cấu hình"),
        ],
        "settings": _FakeSettings(
            common=[_settings_row("W_mm")],
            rows=[_settings_row("unit_price", group_label="Row Literals")],
        ),
    }
    state.update(over)
    return state


class TestPartition(unittest.TestCase):
    def setUp(self):
        self.state = _default_state()
        self.mod, self.saved = _load(self.state)

    def tearDown(self):
        _restore(self.saved)

    def test_ba_loai_roi_nhau(self):
        common = {r["var_name"] for r in
                  self.mod.rows_for(self.mod.KIND_COMMON)}
        rows = {r["var_name"] for r in self.mod.rows_for(self.mod.KIND_ROW)}
        users = {r["var_name"] for r in
                 self.mod.rows_for(self.mod.KIND_USER)}
        self.assertEqual(common, {"W_mm"})
        self.assertEqual(rows, {"unit_price"})
        self.assertEqual(users, {"glass_master"})
        # Đối chứng âm: không tên nào nằm 2 loại (nếu không, autocomplete
        # hiện trùng và `dedupe_candidates` báo "trùng tên" vô ích).
        self.assertFalse(common & rows)
        self.assertFalse(common & users)
        self.assertFalse(rows & users)

    def test_user_khong_bao_gio_chua_row_literal(self):
        users = self.mod.active_names(self.mod.KIND_USER)
        self.assertNotIn("unit_price", users)

    def test_category_row_literal_thang_co_is_input(self):
        """Một dòng bật cả 2 cờ vẫn chỉ thuộc MỘT loại (ROW)."""
        self.state["library"].append(_lib_row(
            "LAI", group_label="Row Literals", is_input=1))
        common = {r["var_name"] for r in
                  self.mod.rows_for(self.mod.KIND_COMMON)}
        rows = {r["var_name"] for r in self.mod.rows_for(self.mod.KIND_ROW)}
        users = {r["var_name"] for r in
                 self.mod.rows_for(self.mod.KIND_USER)}
        self.assertNotIn("LAI", common)
        self.assertNotIn("LAI", users)
        self.assertIn("LAI", rows)

    def test_row_literal_giu_nguon_va_nhom(self):
        row = self.mod.active_rows(self.mod.KIND_ROW)[0]
        self.assertEqual(row["group_label"], "Row Literals")
        self.assertEqual(row["is_input"], 0)

    def test_common_la_bien_nguoi_dung_nhap(self):
        row = self.mod.active_rows(self.mod.KIND_COMMON)[0]
        self.assertEqual(row["is_input"], 1)

    def test_dong_tat_bi_loai_khoi_active(self):
        self.state["library"].append(
            _lib_row("OLD_VAR", category="Cấu hình", is_active=0))
        users = self.mod.active_names(self.mod.KIND_USER)
        self.assertNotIn("OLD_VAR", users)
        # `rows_for` vẫn thấy — caller phân biệt "admin tắt hết" với "chưa khai".
        self.assertIn("OLD_VAR", [r["var_name"] for r in
                                 self.mod.rows_for(self.mod.KIND_USER)])

    def test_sap_theo_sort_order_roi_ten(self):
        self.state["library"].extend([
            _lib_row("B_VAR", group_label="Cấu hình", sort_order=20),
            _lib_row("A_VAR", group_label="Cấu hình", sort_order=10),
        ])
        names = [n for n in self.mod.active_names(self.mod.KIND_USER)
                 if n in ("A_VAR", "B_VAR")]
        self.assertEqual(names, ["A_VAR", "B_VAR"])


class TestMotNguon(unittest.TestCase):
    """Bảng Settings đã BỊ XOÁ (2026-11-27) — còn đúng MỘT nguồn: Library.

    Dòng "GHOST" chỉ nằm trong bảng Settings (bảng vật lý hoặc stub) ⛔ được
    sống lại; đọc vào bảng không tồn tại chỉ tạo lỗi SQL lúc chạy.
    """

    def test_khong_doc_settings(self):
        state = _default_state(settings=_FakeSettings(
            common=[_settings_row("GHOST")],
            rows=[_settings_row("GHOST_ROW", group_label="Row Literals")],
        ))
        mod, saved = _load(state)
        try:
            common = mod.active_names(mod.KIND_COMMON)
            rows = mod.active_names(mod.KIND_ROW)
        finally:
            _restore(saved)
        self.assertEqual(common, ["W_mm"])
        self.assertEqual(rows, ["unit_price"])

    def test_khong_con_duong_lui_settings(self):
        """Không còn hàm đọc bảng Settings trong module."""
        mod, saved = _load(_default_state())
        try:
            for name in ("_rows_from_settings", "_rows_from_library_legacy",
                         "is_library_migrated"):
                self.assertFalse(hasattr(mod, name), name)
        finally:
            _restore(saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
