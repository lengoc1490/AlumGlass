"""Test THUẦN cho bộ nạp biến theo dòng (B3a) — `engine/row_literal_loader.py`.

Hai bảo đảm:
  1. Biến KHAI MỚI trong Library có giá trị đúng theo `source_doctype.field`
     mà ⛔ phải sửa Python (điều kiện nghiệm thu B3a).
  2. Tên LÕI engine đã dựng **không bị ghi đè** (giữ nguyên số tiền), và
     thiếu nguồn thì **báo**, ⛔ gán 0.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_row_literal_loader.py
"""
import importlib.util
import os
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_REL = "alumglass/engine/row_literal_loader.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "row_literal_loader_test", os.path.join(_APP_ROOT, _REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCollectDefs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def test_bo_dong_thieu_nguon(self):
        defs = self.mod.collect_defs([
            {"var_name": "ok", "source_doctype": "AL Bom Item",
             "source_field": "note"},
            {"var_name": "no_field", "source_doctype": "AL Bom Item"},
            {"var_name": "", "source_doctype": "AL Bom Item",
             "source_field": "note"},
            {"var_name": "no_doctype", "source_field": "note"},
        ])
        self.assertEqual([d["name"] for d in defs], ["ok"])

    def test_nhan_mac_dinh_la_ten(self):
        defs = self.mod.collect_defs([
            {"var_name": "x", "source_doctype": "Item",
             "source_field": "weight_per_unit"},
        ])
        self.assertEqual(defs[0]["label"], "x")


class TestFill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def test_dien_bien_moi_tu_nguon(self):
        lit = {"unit_price": 100}
        defs = [
            {"name": "cut_angle", "label": "Góc cắt",
             "source_doctype": "AL Bom Item", "source_field": "cut_angle"},
            {"name": "max_area_m2", "label": "Khổ tối đa",
             "source_doctype": "AL Glass Master",
             "source_field": "max_area_m2"},
        ]
        sources = {
            "AL Bom Item": {"cut_angle": "45"},
            "AL Glass Master": {"max_area_m2": 3.2},
        }
        lit, missing = self.mod.fill_literals(lit, defs, sources)
        self.assertEqual(lit["cut_angle"], "45")
        self.assertEqual(lit["max_area_m2"], 3.2)
        self.assertEqual(missing, [])

    def test_khong_ghi_de_ten_loi(self):
        """Đối chứng âm: tên engine đã dựng giữ nguyên giá trị cũ."""
        lit = {"unit_price": 100}
        defs = [{"name": "unit_price", "label": "Đơn giá",
                 "source_doctype": "AL Bom Item", "source_field": "x"}]
        lit, missing = self.mod.fill_literals(
            lit, defs, {"AL Bom Item": {"x": 999}})
        self.assertEqual(lit["unit_price"], 100)
        self.assertEqual(missing, [])

    def test_thieu_nguon_thi_bao_khong_gan_0(self):
        lit = {}
        defs = [{"name": "new_var", "label": "Biến mới",
                 "source_doctype": "DocType Không Có",
                 "source_field": "f"}]
        lit, missing = self.mod.fill_literals(lit, defs, {})
        self.assertNotIn("new_var", lit)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["name"], "new_var")
        self.assertIn("khong_co_nguon", missing[0]["reason"])

    def test_thieu_field_thi_bao(self):
        lit = {}
        defs = [{"name": "v", "label": "V",
                 "source_doctype": "AL Bom Item", "source_field": "abc"}]
        lit, missing = self.mod.fill_literals(
            lit, defs, {"AL Bom Item": {"note": "x"}})
        self.assertNotIn("v", lit)
        self.assertIn("thieu_field", missing[0]["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
