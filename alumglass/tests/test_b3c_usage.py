"""Test THUẦN cho B3c/Đ4 — ô "Dùng ở" tự suy + cảnh báo biến dòng dùng trần.

Phủ:
  1. `derive_usage` — dữ liệu cũ (is_system/is_input/category) → nhãn Việt.
  2. `flags_for_usage` — chọn nhãn → (is_input, category) đúng, rời Row Literals.
  3. `find_bare_row_variables` — bắt biến dòng viết trần; ⛔ bắt oan khi:
     `items.<dòng>.<cột>`, chuỗi literal `lookup_rule('…')`, tên hàm.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_b3c_usage.py
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

_LIB_REL = ("alumglass/al_master_data/doctype/al_variable_library/"
            "al_variable_library.py")
_RULE_INPUT_REL = "alumglass/al_formula_rules/rule_input.py"

FAKE = ("frappe", "frappe.model", "frappe.model.document")


def _build_frappe():
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    frappe.msgprint = lambda *a, **k: None
    frappe._ = lambda s: s
    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")

    class Document:
        pass

    document.Document = Document
    model.document = document
    frappe.model = model
    return frappe


def _load(rel, name):
    saved = {n: sys.modules.get(n) for n in FAKE}
    frappe = _build_frappe()
    sys.modules["frappe"] = frappe
    sys.modules["frappe.model"] = frappe.model
    sys.modules["frappe.model.document"] = frappe.model.document
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_APP_ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved


def _restore(saved):
    for name, old in saved.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old


class TestUsage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod, cls.saved = _load(_LIB_REL, "al_variable_library_b3c")

    @classmethod
    def tearDownClass(cls):
        _restore(cls.saved)

    def test_suy_tu_du_lieu_cu(self):
        m = self.mod
        self.assertEqual(m.derive_usage(1, 1, "Row Literals"), m.USAGE_GLOBAL)
        self.assertEqual(m.derive_usage(0, 0, "Row Literals"), m.USAGE_ROW)
        self.assertEqual(m.derive_usage(0, 1, "Kích thước"), m.USAGE_INPUT)
        self.assertEqual(m.derive_usage(0, 0, "Kích thước"), m.USAGE_GLOBAL)

    def test_chon_tung_dong_dua_ve_row_literals(self):
        is_input, group = self.mod.flags_for_usage(
            self.mod.USAGE_ROW, "Kích thước")
        self.assertEqual((is_input, group), (0, "Row Literals"))

    def test_chon_nguoi_dung_nhap_roi_khoi_row(self):
        # Rời "Từng dòng" ⇒ nhóm hiển thị cũ được GIỮ (⛔ để lại Row Literals).
        is_input, group = self.mod.flags_for_usage(
            self.mod.USAGE_INPUT, "Nhóm A")
        self.assertEqual(is_input, 1)
        self.assertEqual(group, "Nhóm A")

    def test_row_literals_bi_thay_khi_doi_loai(self):
        is_input, group = self.mod.flags_for_usage(
            self.mod.USAGE_INPUT, "Row Literals")
        self.assertEqual(is_input, 1)
        self.assertEqual(group, "Thông số nhập")

    def test_chon_toan_don_roi_khoi_row(self):
        is_input, group = self.mod.flags_for_usage(
            self.mod.USAGE_GLOBAL, "Row Literals")
        self.assertEqual(is_input, 0)
        self.assertEqual(group, "Cấu hình")


class TestBareRowVariables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod, cls.saved = _load(_RULE_INPUT_REL, "rule_input_b3c")

    @classmethod
    def tearDownClass(cls):
        _restore(cls.saved)

    def test_bat_bien_dong_viet_tran(self):
        found = self.mod.find_bare_row_variables(
            "unit_price * 2 + unit_qty", {"unit_price": "Đơn giá",
                                          "unit_qty": "SL đơn vị"})
        self.assertEqual(found, ["unit_price", "unit_qty"])

    def test_khong_bat_dang_cross_row(self):
        found = self.mod.find_bare_row_variables(
            "items.kinh.unit_price * 2", {"unit_price": "Đơn giá"})
        self.assertEqual(found, [])

    def test_khong_bat_trong_chuoi_literal(self):
        found = self.mod.find_bare_row_variables(
            "lookup_rule('RULE-UNIT_PRICE', items.kinh.unit_price)",
            {"unit_price": "Đơn giá"})
        self.assertEqual(found, [])

    def test_khong_bat_ten_ham(self):
        found = self.mod.find_bare_row_variables(
            "roundup(unit_price)", {"unit_price": "Đơn giá"})
        # `unit_price` nằm trong ngoặc, không phải lời gọi hàm ⇒ vẫn bắt.
        self.assertEqual(found, ["unit_price"])
        found2 = self.mod.find_bare_row_variables(
            "unit_price(1)", {"unit_price": "Đơn giá"})
        self.assertEqual(found2, [])

    def test_khong_trung_lap(self):
        found = self.mod.find_bare_row_variables(
            "unit_price + unit_price", {"unit_price": "Đơn giá"})
        self.assertEqual(found, ["unit_price"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
