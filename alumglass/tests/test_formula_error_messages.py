"""Test THUẦN cho câu báo lỗi công thức (`engine/formula_messages.py`).

Lỗi thật cần chặn (Owner báo 2026-11-28): bảng tham số báo giá hiện nguyên
câu Python `name 'OFFSET_FRAME' is not defined` — người dùng không biết biến
nào, không biết sửa ở đâu, và mã nội bộ bị phơi ra màn hình.

Chạy:
    python3 alumglass/tests/test_formula_error_messages.py
"""
import os
import sys
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from alumglass.engine.formula_messages import (  # noqa: E402
    MISSING_NAME_RE, humanize_errors, humanize_formula_error,
    humanize_unknown_variable, missing_name, unchosen_glass_message)


class TestMissingName(unittest.TestCase):
    def test_bat_dung_ten_bien(self):
        self.assertEqual(
            missing_name("name 'OFFSET_FRAME' is not defined"),
            "OFFSET_FRAME")

    def test_bat_duoc_ten_co_gach_duoi_va_so(self):
        self.assertEqual(
            missing_name("name 'NC_SX_PCT2' is not defined"), "NC_SX_PCT2")

    def test_loi_khac_tra_rong(self):
        """ĐỐI CHỨNG ÂM: lỗi không phải thiếu biến ⇒ ⛔ nhận nhầm."""
        for message in (
            "unsupported operand type(s) for -: 'str' and 'float'",
            "division by zero",
            "",
            None,
        ):
            self.assertIsNone(missing_name(message), message)

    def test_regex_khong_khop_chuoi_rac(self):
        self.assertIsNone(MISSING_NAME_RE.search("something else entirely"))


class TestHumanize(unittest.TestCase):
    def test_cau_co_nhan_va_ma_bien(self):
        text = humanize_formula_error("OFFSET_FRAME", "Khe hở khung-cánh")
        self.assertIn("Khe hở khung-cánh", text)
        self.assertIn("OFFSET_FRAME", text)
        self.assertIn("Thư viện biến", text)

    def test_khong_phoi_cau_python(self):
        text = humanize_formula_error("OFFSET_FRAME", "Khe hở khung-cánh")
        self.assertNotIn("is not defined", text)
        self.assertNotIn("name '", text)

    def test_khong_co_nhan_thi_chi_hien_ten(self):
        text = humanize_formula_error("NC_LD_PCT", "")
        self.assertIn("NC_LD_PCT", text)
        self.assertNotIn("()", text)

    def test_nhan_trung_ten_thi_khong_lap(self):
        text = humanize_formula_error("PROFIT_MARGIN", "PROFIT_MARGIN")
        self.assertEqual(text.count("PROFIT_MARGIN"), 1)


class TestUnknownVariable(unittest.TestCase):
    """Biến KHÔNG có trong thư viện ⇒ câu khác (phải khai biến trước)."""

    def test_cau_noi_ro_bien_chua_duoc_khai(self):
        text = humanize_unknown_variable("Bien_La")
        self.assertIn("Bien_La", text)
        self.assertIn("Thư viện biến", text)
        self.assertIn("chưa có giá trị nào mang tên này", text)

    def test_khac_cau_thieu_gia_tri(self):
        known = humanize_formula_error("Bien_La", "Biến lạ")
        unknown = humanize_unknown_variable("Bien_La")
        self.assertNotEqual(known, unknown)


class TestUnchosenGlass(unittest.TestCase):
    def test_cau_chi_viec_chon_kinh(self):
        text = unchosen_glass_message("Kính cường lực 8 ly")
        self.assertIn("Kính cường lực 8 ly", text)
        self.assertIn("chọn kính", text)
        # ⛔ đẩy người dùng đi sửa bảng giá — đó ⛔ phải nguyên nhân.
        self.assertNotIn("bảng giá", text)


class TestHumanizeErrors(unittest.TestCase):
    """Bảng lỗi của FormulaEngine → bảng câu người đọc."""

    def _lookup(self, known_vars, labels=None):
        labels = labels or {}

        def lookup(var_name):
            if var_name in known_vars:
                return True, labels.get(var_name, "")
            return False, ""
        return lookup

    def test_doi_loi_thieu_bien_va_giu_loi_khac(self):
        errors = {
            "canh_ngang__width": "name 'OFFSET_FRAME' is not defined",
            "kinh_tren__width": "division by zero",
        }
        out = humanize_errors(
            errors, self._lookup({"OFFSET_FRAME"},
                                 {"OFFSET_FRAME": "Khe hở khung-cánh"}))
        self.assertIn("Khe hở khung-cánh", out["canh_ngang__width"])
        self.assertNotIn("is not defined", out["canh_ngang__width"])
        # ĐỐI CHỨNG ÂM: lỗi khác giữ nguyên văn, ⛔ bị đổi thành câu thiếu biến.
        self.assertEqual(out["kinh_tren__width"], "division by zero")

    def test_bien_chua_khai_dung_cau_khac(self):
        out = humanize_errors(
            {"f": "name 'LA_BIEN' is not defined"}, self._lookup(set()))
        self.assertIn("mang tên này", out["f"])

    def test_bang_rong(self):
        self.assertEqual(humanize_errors({}, self._lookup(set())), {})
        self.assertEqual(humanize_errors(None, self._lookup(set())), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
