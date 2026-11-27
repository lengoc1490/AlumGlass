"""Test THUẦN (kiểm cấu trúc) cho B4 + B5 — hai thay đổi "chỉ còn một đường".

Vì sao kiểu kiểm này: hai việc dưới đây **bỏ một đường cũ** trong mã đọc tiền.
Chạy đúng số phải có site + 2 mốc giá chuẩn (B0). Ở máy không có site, thứ
kiểm được — và cũng là thứ dễ tái phát nhất — là **đường cũ không quay lại**:

  B4  · danh mục biến là đường CHÍNH kể cả khi record chưa gán hồ sơ
      (`all_sources`), ⛔ còn nhánh "không hồ sơ ⇒ trả rỗng".
  B4b · lớp resolve biến hệ ⛔ ghi đè giá trị Formula Builder đã resolve.
  B5  · ⛔ còn fallback "lấy số từ AL Rule CONSTANT" khi biến hệ thiếu nguồn.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_b4_b5_one_path.py
"""
import os
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _src(rel):
    with open(os.path.join(_APP_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class TestB4MotDuong(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = _src("alumglass/api/variable_catalog.py")
        cls.api = _src("alumglass/api/__init__.py")

    def test_catalog_chay_duoc_khi_chua_gan_ho_so(self):
        self.assertIn("all_sources=False", self.catalog)
        # Nhánh cũ: không hồ sơ ⇒ trả danh mục RỖNG để caller chạy legacy.
        self.assertNotIn("return _empty_result(fieldname=fieldname)", self.catalog)

    def test_api_van_truyen_duoc_all_sources(self):
        self.assertIn("all_sources=1 if all_sources else 0", self.api)

    def test_api_khong_con_cat_duong_khi_thieu_ho_so(self):
        start = self.api.index("def _get_catalog_context")
        rest = self.api[start + 10:]
        end = rest.index("\ndef ") if "\ndef " in rest else len(rest)
        block = rest[:end]
        # Nhánh cũ: "profile rỗng ⇒ trả None để chạy legacy".
        self.assertNotIn("if not profile:", block)

    def test_duong_du_phong_la_duong_loi(self):
        """Legacy chỉ được chạy khi danh mục lỗi — comment phải nói rõ."""
        self.assertIn("Đường DỰ PHÒNG", self.api)


class TestB4bKhongDeGiaTri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orch = _src("alumglass/engine/bom_orchestrator.py")

    def test_loc_bien_da_co_gia_tri_la_vo_dieu_kien(self):
        # Bản cũ: chỉ lọc khi `fill_missing_only` ⇒ nhánh đầy đủ resolve lại
        # rồi update đè giá trị FB.
        self.assertNotIn("if fill_missing_only:\n            system_vars_to_query",
                         self.orch)
        self.assertIn("system_vars_to_query = [sv for sv in system_vars",
                      self.orch)


class TestB5KhongLaySoTuRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orch = _src("alumglass/engine/bom_orchestrator.py")

    def test_khong_con_fallback_rule_constant(self):
        self.assertNotIn('rule_type == "CONSTANT"', self.orch)
        self.assertNotIn('fallback_code = sv["var_name"].replace("_", "-")',
                         self.orch)

    def test_co_canh_bao_bien_he_thieu_nguon(self):
        self.assertIn('"bien_he_chua_co_nguon:', self.orch)

    def test_chi_bao_bien_khai_nguon(self):
        """⛔ làm ngập cảnh báo cho biến cấu hình không khai nguồn."""
        idx = self.orch.index('"bien_he_chua_co_nguon:')
        window = self.orch[idx - 700:idx]
        self.assertIn('sv.get("source_doctype")', window)


if __name__ == "__main__":
    unittest.main(verbosity=2)
