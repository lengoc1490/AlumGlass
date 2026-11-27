"""Test THUẦN cho B7/Đ5 — `calc_expr` là nguồn chính, `calc_fn` còn là đường lùi.

Bốn bảo đảm:
  1. **Không đổi số tiền**: 14 biểu thức `CALC_EXPR` cho CÙNG kết quả với 14
     lambda `PATTERN_FORMULAS` trên nhiều bộ số (kể cả THIẾU biến phụ).
  2. **Ưu tiên đúng**: có cả hai ô ⇒ engine dùng `calc_expr`; chỉ có `calc_fn`
     ⇒ dùng `calc_fn` + ghi cảnh báo MỘT lần.
  3. **Cấu hình sai phải lộ**: `calc_expr` hỏng ⇒ ném lỗi, ⛔ im lặng rơi xuống
     `calc_fn` để ra số khác.
  4. **Patch điền đúng chỗ**: chỉ điền ô trống khi `calc_fn` khớp seed; ⛔ đè
     công thức riêng của site; chạy lại lần 2 không đổi gì.

Chạy:
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=~/myfrappe/apps python3 alumglass/tests/test_calc_expr_b7.py
"""
import importlib.util
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_APPS_ROOT = os.path.dirname(_APP_ROOT)
for _p in (_APPS_ROOT, _APP_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_PATCH_REL = "alumglass/patches/v1_0/backfill_calc_expr.py"


# ── frappe stub (chỉ khi chạy standalone) ────────────────────────────────
class _FakeDB:
    def __init__(self):
        self.records = {}          # name -> {"calc_expr": ..., "calc_fn": ...}
        self.columns = set()
        self.writes = []           # (name, field, value)

    def has_column(self, doctype, column):
        return column in self.columns

    def exists(self, doctype, name=None):
        if doctype == "DocType":
            return True
        return name in self.records

    def get_value(self, doctype, name, field, *a, **k):
        if isinstance(field, (list, tuple)):
            row = self.records.get(name, {})
            return [row.get(f) for f in field]
        return self.records.get(name, {}).get(field)

    def set_value(self, doctype, name, field, value=None, **k):
        self.records.setdefault(name, {})[field] = value
        self.writes.append((name, field, value))


def _install_frappe_stub():
    if "frappe" in sys.modules:
        return
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    frappe.msgprint = lambda *a, **k: None
    frappe.logs = []
    frappe.log_error = lambda msg, title=None: frappe.logs.append((msg, title))
    frappe.get_traceback = lambda: ""
    frappe.db = _FakeDB()
    sys.modules["frappe"] = frappe


_install_frappe_stub()

from alumglass import formula_handlers as fh

# Bộ số mẫu: có đủ biến phụ / thiếu biến phụ / số lẻ / số 0.
SAMPLES = [
    (2000, 1000, 1.5, {"depth": 10, "piece_length": 0.6,
                       "spacing": 1, "area_per_piece": 1}),
    (0, 0, 0, {}),                       # thiếu HẾT biến phụ
    (1234, 567, 2.7, {"depth": 3}),
    (6000, 2500, 0.85, {"piece_length": 6, "spacing": 0.5,
                        "area_per_piece": 2}),
    (2500, 0, 0, {"piece_length": 1}),
]


def _expr_result(code, w, h, tlr, extra):
    expr = fh._compile_calc_expr(fh.CALC_EXPR[code])
    extra = dict(extra)
    for name, default in fh._OPTIONAL_VAR_DEFAULTS.items():
        if extra.get(name) in (None, ""):
            extra[name] = default
    scope = {"w": w, "h": h, "tlr": tlr}
    scope.update(extra)
    scope["kw"] = dict(extra)
    return expr.eval(scope)


class TestExprBangLambda(unittest.TestCase):
    def test_du_14_pattern(self):
        self.assertEqual(set(fh.CALC_EXPR), set(fh.PATTERN_FORMULAS))

    def test_cung_ket_qua_tren_moi_bo_so(self):
        for code, builtin in fh.PATTERN_FORMULAS.items():
            for w, h, tlr, extra in SAMPLES:
                with self.subTest(code=code, w=w, h=h):
                    expected = builtin(w, h, tlr, **extra)
                    actual = _expr_result(code, w, h, tlr, extra)
                    self.assertAlmostEqual(
                        actual, expected, places=9,
                        msg=f"{code}: expr={actual} lambda={expected}")

    def test_thieu_bien_phu_khong_no(self):
        """Đối chứng dương cho mặc định: không truyền piece_length vẫn ra số."""
        val = _expr_result("LENGTH_TO_PIECES", 6000, 0, 0, {})
        self.assertAlmostEqual(val, 6.0, places=9)
        val = _expr_result("COUNT_PER_AREA", 6000, 1000, 0, {})
        self.assertAlmostEqual(val, 6.0, places=9)
        # depth thiếu → mặc định 0 ⇒ thể tích 0 (khớp kw.get('depth', 0))
        self.assertAlmostEqual(_expr_result("VOLUME_M3", 2000, 1000, 0, {}), 0.0)

    def test_bien_phu_rong_khong_no(self):
        """Ô biến phụ để trống (None / "") ⇒ lấy mặc định, ⛔ TypeError."""
        val = _expr_result("LENGTH_TO_PIECES", 6000, 0, 0,
                           {"piece_length": None})
        self.assertAlmostEqual(val, 6.0, places=9)
        val = _expr_result("VOLUME_M3", 2000, 1000, 0, {"depth": ""})
        self.assertAlmostEqual(val, 0.0, places=9)


class TestLookupUuTien(unittest.TestCase):
    def setUp(self):
        fh.clear_calc_fn_cache()
        fh.frappe.logs.clear()
        fh.frappe.db = _FakeDB()

    def tearDown(self):
        fh.clear_calc_fn_cache()
        fh.frappe.db = _FakeDB()

    def _db(self, records):
        db = _FakeDB()
        db.records = records
        fh.frappe.db = db
        return db

    def test_co_ca_hai_thi_dung_calc_expr(self):
        self._db({"LENGTH_TO_WEIGHT": {
            "calc_expr": "(w/1000)*tlr",
            "calc_fn": "lambda w,h,tlr,**kw: (w/1000)*tlr + 999",
        }})
        val = fh.lookup_calc_pattern(
            "LENGTH_TO_WEIGHT", width=2000, weight_per_unit=1.5)
        self.assertAlmostEqual(val, 3.0, places=9)
        self.assertEqual(fh._DB_EXPR_KIND["LENGTH_TO_WEIGHT"], "calc_expr")
        self.assertEqual(fh.frappe.logs, [])

    def test_chi_co_calc_fn_thi_dung_va_canh_bao_mot_lan(self):
        self._db({"LENGTH_TO_WEIGHT": {
            "calc_fn": "lambda w,h,tlr,**kw: (w/1000)*tlr + 999",
        }})
        for _ in range(3):
            val = fh.lookup_calc_pattern(
                "LENGTH_TO_WEIGHT", width=2000, weight_per_unit=1.5)
            self.assertAlmostEqual(val, 1002.0, places=9)
        self.assertEqual(fh._DB_EXPR_KIND["LENGTH_TO_WEIGHT"], "calc_fn")
        self.assertEqual(len(fh.frappe.logs), 1, "cảnh báo chỉ ghi 1 lần")

    def test_calc_expr_hong_thi_nem_khong_roi_xuong_calc_fn(self):
        """Đối chứng âm: cấu hình sai phải lộ, ⛔ lặng lẽ đổi sang số khác."""
        self._db({"LENGTH_TO_WEIGHT": {
            "calc_expr": "(w/1000)*(",
            "calc_fn": "lambda w,h,tlr,**kw: 1",
        }})
        with self.assertRaises(Exception):
            fh.lookup_calc_pattern(
                "LENGTH_TO_WEIGHT", width=2000, weight_per_unit=1.5)
        self.assertNotIn("LENGTH_TO_WEIGHT", fh._DB_PATTERN_CACHE)

    def test_rong_ca_hai_thi_roi_ve_builtin(self):
        self._db({})
        val = fh.lookup_calc_pattern(
            "AREA_M2", width=2000, height=1000)
        self.assertAlmostEqual(val, 2.0, places=9)
        self.assertIn("AREA_M2", fh._NEGATIVE_CACHE)


def _load_patch(db):
    """Nạp patch với db giả — patch import `alumglass.formula_handlers` (đã có)."""
    import frappe as frappe_mod
    frappe_mod.db = db
    spec = importlib.util.spec_from_file_location(
        "backfill_calc_expr_test", os.path.join(_APP_ROOT, _PATCH_REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPatch(unittest.TestCase):
    def _state(self):
        db = _FakeDB()
        db.columns = {"calc_expr"}
        db.records = {
            # khớp seed → phải điền
            "LENGTH_TO_WEIGHT": {
                "calc_expr": "",
                "calc_fn": "lambda w,h,tlr,**kw: (w/1000)*tlr"},
            # admin đã khai → giữ nguyên
            "AREA_M2": {
                "calc_expr": "w/1000", "calc_fn": None},
            # công thức riêng của site → ⛔ đụng
            "COUNT": {
                "calc_expr": "",
                "calc_fn": "lambda w,h,tlr,**kw: 2"},
            # chưa có record
        }
        return db

    def test_dien_dung_cho(self):
        db = self._state()
        _load_patch(db).execute()
        self.assertEqual(db.records["LENGTH_TO_WEIGHT"]["calc_expr"],
                         "(w/1000)*tlr")
        # giữ nguyên công thức admin đã khai
        self.assertEqual(db.records["AREA_M2"]["calc_expr"], "w/1000")
        # KHÔNG đè công thức riêng
        self.assertEqual(db.records["COUNT"]["calc_expr"], "")
        self.assertNotIn("SET", [w[0] for w in db.writes])

    def test_chay_lan_hai_khong_doi_gi(self):
        db = self._state()
        mod = _load_patch(db)
        mod.execute()
        first = len(db.writes)
        mod.execute()
        self.assertEqual(len(db.writes), first, "lần 2 phải không ghi gì")

    def test_thieu_cot_thi_bo_qua(self):
        db = _FakeDB()
        db.columns = set()
        db.records = self._state().records
        _load_patch(db).execute()
        self.assertEqual(db.writes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
