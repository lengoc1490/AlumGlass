"""Test THUẦN cho patch `v1_0.unify_variable_group` (một nhóm DUY NHẤT).

Bối cảnh: `AL Variable Library` từng có `category` và `group_label` cùng nghĩa.
Từ 2026-11-27 chỉ còn `group_label` (Select). Patch này đồng bộ dữ liệu cũ.

Chạy:
    python3 alumglass/tests/test_unify_variable_group.py
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

_PATCH_REL = "alumglass/patches/v1_0/unify_variable_group.py"
LIB = "AL Variable Library"


class _FakeDB:
    def __init__(self, state):
        self.state = state

    def has_column(self, doctype, column):
        return column in self.state["columns"]

    def set_value(self, doctype, name, field, value, update_modified=True):
        self.state["writes"].append((name, field, value))

    def commit(self):
        self.state["commits"] += 1


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.get_all = lambda doctype, fields=None, **k: [
        dict(row) for row in state["rows"]]
    frappe.get_traceback = lambda: "traceback"
    frappe.log_error = lambda *a, **k: state["log_errors"].append(k or a)
    return frappe


def _load(state):
    saved = sys.modules.get("frappe")
    sys.modules["frappe"] = _build_frappe(state)
    sys.modules.pop("alumglass.patches.v1_0.unify_variable_group", None)
    spec = importlib.util.spec_from_file_location(
        "alumglass.patches.v1_0.unify_variable_group",
        os.path.join(_APP_ROOT, _PATCH_REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved


def _restore(saved):
    if saved is None:
        sys.modules.pop("frappe", None)
    else:
        sys.modules["frappe"] = saved


def _state(rows, columns=("group_label", "category")):
    return {
        "rows": rows,
        "columns": set(columns),
        "writes": [],
        "log_errors": [],
        "commits": 0,
    }


class TestUnify(unittest.TestCase):
    def _run(self, state):
        mod, saved = _load(state)
        try:
            mod.execute()
        finally:
            _restore(saved)
        return state

    def test_lay_tu_category_khi_nhom_rong(self):
        state = self._run(_state([
            {"name": "A", "group_label": "", "category": "Thi công",
             "is_input": 0, "usage": ""},
        ]))
        self.assertEqual(state["writes"], [("A", "group_label", "Thi công")])

    def test_doi_ten_nhom_cu(self):
        state = self._run(_state([
            {"name": "W_mm", "group_label": "BOM Input Variables",
             "category": "BOM Input Variables", "is_input": 1, "usage": ""},
        ]))
        self.assertEqual(
            state["writes"], [("W_mm", "group_label", "Thông số nhập")])

    def test_bien_theo_dong_ve_row_literals(self):
        state = self._run(_state([
            {"name": "unit_price", "group_label": "", "category": "Row Literals",
             "is_input": 0, "usage": ""},
            {"name": "glass_type", "group_label": "", "category": "",
             "is_input": 0, "usage": "Từng dòng"},
        ]))
        self.assertEqual(
            sorted(state["writes"]),
            [("glass_type", "group_label", "Row Literals"),
             ("unit_price", "group_label", "Row Literals")])

    def test_bien_nguoi_dung_nhap_rong_nhom(self):
        state = self._run(_state([
            {"name": "H_mm", "group_label": "", "category": "",
             "is_input": 1, "usage": "Người dùng nhập"},
        ]))
        self.assertEqual(
            state["writes"], [("H_mm", "group_label", "Thông số nhập")])

    def test_idempotent_khong_ghi_lai(self):
        state = self._run(_state([
            {"name": "A", "group_label": "Kích thước", "category": "Kích thước",
             "is_input": 0, "usage": ""},
        ]))
        self.assertEqual(state["writes"], [])

    def test_dong_khong_suy_duoc_thi_de_yen(self):
        state = self._run(_state([
            {"name": "X", "group_label": "", "category": "",
             "is_input": 0, "usage": ""},
        ]))
        self.assertEqual(state["writes"], [])

    def test_nhom_la_duoc_quy_ve_mac_dinh(self):
        """Nhóm ngoài danh sách Select ⇒ quy về mặc định theo loại biến.

        Nếu ghi nguyên văn, Select sẽ chặn người dùng khi họ mở dòng đó Lưu.
        """
        state = self._run(_state([
            {"name": "A", "group_label": "Nhóm tự đặt", "category": "",
             "is_input": 1, "usage": "Người dùng nhập"},
            {"name": "B", "group_label": "Nhóm lạ khác", "category": "",
             "is_input": 0, "usage": "Toàn đơn"},
        ]))
        self.assertEqual(
            sorted(state["writes"]),
            [("A", "group_label", "Thông số nhập"),
             ("B", "group_label", "Cấu hình")])

    def test_chua_co_cot_group_label_thi_bo_qua(self):
        state = self._run(_state(
            [{"name": "A", "category": "Thi công"}],
            columns=("category",),
        ))
        self.assertEqual(state["writes"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
