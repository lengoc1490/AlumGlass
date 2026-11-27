"""Test THUẦN cho patch `v1_0.drop_variable_settings_tables` (R3 — xoá bảng cũ).

Không cần site: `frappe` được stub trong bộ nhớ, patch nạp lại bằng
`importlib` cho từng ca.

Bảo vệ 4 tính chất — mỗi ca có ĐỐI CHỨNG ÂM (làm hỏng đúng một điều kiện,
cổng phải chặn hoặc phải im):

  1. CHƯA GỘP ĐỦ ⇒ throw, ⛔ xoá gì (biến còn ở bảng con mà Library không có).
  2. `default_profile` có giá trị mà chưa hồ sơ `is_default` ⇒ throw.
  3. Đủ dữ liệu ⇒ xoá DocType record, xoá `tabSingles`, DROP 3 bảng, và
     ghi tệp sao lưu trước khi xoá.
  4. IDEMPOTENT: bảng không còn ⇒ chạy lại không lỗi, không DROP gì thêm.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_drop_variable_settings_tables.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

_PATCH_REL = "alumglass/patches/v1_0/drop_variable_settings_tables.py"
_FAKE_MODULES = ("frappe",)

LIB = "AL Variable Library"
PROFILE = "AL Variable Profile"
SETTINGS = "AL Variable Settings"
COMMON = "AL Common Variable"
ROW = "AL Row Literal"


class _Throw(Exception):
    """`frappe.throw` trong stub — patch phải dừng ở đây."""


class _FakeDB:
    def __init__(self, state):
        self.state = state

    # ── schema ──────────────────────────────────────────────────────
    def table_exists(self, doctype, cached=True):
        return doctype in self.state["tables"]

    def has_column(self, doctype, column):
        return column in self.state["columns"].get(doctype, ())

    # ── đọc ─────────────────────────────────────────────────────────
    def sql(self, query, values=None, as_dict=False):
        self.state["queries"].append((query, values))
        normalized = " ".join(query.split()).lower()
        if normalized.startswith("delete from `tabsingles`"):
            self.state["singles_cleared"].append(values)
            self.state["singles"] = {}
            return []
        if "from `tabal variable library`" in normalized:
            return [{"var_name": v} for v in self.state["library_names"]]
        if "tabal common variable" in normalized:
            return [dict(r) for r in self.state["rows"].get(COMMON, [])]
        if "tabal row literal" in normalized:
            return [dict(r) for r in self.state["rows"].get(ROW, [])]
        if "from `tabal variable profile`" in normalized:
            return [{"name": n} for n in self.state["default_profiles"]]
        if "from `tabsingles`" in normalized:
            return [{"field": k, "value": v}
                    for k, v in self.state["singles"].items()]
        return []

    def sql_ddl(self, statement):
        self.state["ddl"].append(statement)

    # ── ghi ─────────────────────────────────────────────────────────
    def exists(self, doctype, name=None, *args, **kwargs):
        if doctype == "DocType":
            return name if name in self.state["doctypes"] else None
        return None

    def commit(self):
        self.state["commits"] += 1

    def has_column_safe(self, *args):
        return True


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)

    def _throw(message, *args, **kwargs):
        state["thrown"].append(message)
        raise _Throw(message)

    frappe.throw = _throw
    frappe.get_traceback = lambda: "traceback"
    frappe.log_error = lambda *a, **k: state["log_errors"].append(
        k.get("title") or (a[0] if a else ""))
    frappe.delete_doc = lambda doctype, name, force=False, ignore_permissions=False: (
        state["deleted"].append((doctype, name)))
    frappe.get_site_path = lambda *parts: state["site_path"]
    frappe.utils = types.SimpleNamespace(
        now_datetime=lambda: types.SimpleNamespace(
            strftime=lambda fmt: "20261127_101500"),
    )
    # Patch gọi lại patch gộp — thay bằng hàm đếm, ⛔ nạp patch thật.
    merge = types.ModuleType(
        "alumglass.patches.v1_0.merge_variable_settings_into_library")
    merge.execute = lambda: state["merge_calls"].append(1)
    sys.modules[
        "alumglass.patches.v1_0.merge_variable_settings_into_library"] = merge
    return frappe


def _load(state):
    saved = {n: sys.modules.get(n) for n in _FAKE_MODULES}
    saved_merge = sys.modules.get(
        "alumglass.patches.v1_0.merge_variable_settings_into_library")
    sys.modules["frappe"] = _build_frappe(state)
    sys.modules.pop(
        "alumglass.patches.v1_0.drop_variable_settings_tables", None)
    spec = importlib.util.spec_from_file_location(
        "alumglass.patches.v1_0.drop_variable_settings_tables",
        os.path.join(_APP_ROOT, _PATCH_REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved, saved_merge


def _restore(saved, saved_merge):
    for name, old in saved.items():
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old
    if saved_merge is None:
        sys.modules.pop(
            "alumglass.patches.v1_0.merge_variable_settings_into_library", None)
    else:
        sys.modules[
            "alumglass.patches.v1_0.merge_variable_settings_into_library"] = (
                saved_merge)


def _default_state(**over):
    """Site ĐÃ gộp đủ: 2 biến còn ở bảng con đều có trong Library."""
    state = {
        "tables": {SETTINGS, COMMON, ROW, LIB, PROFILE},
        "columns": {
            COMMON: {"name", "parent", "parentfield", "parenttype", "idx",
                     "var_name", "var_label", "var_type", "group_label",
                     "sort_order", "is_active", "description"},
            ROW: {"name", "parent", "parentfield", "parenttype", "idx",
                  "var_name", "var_label", "var_type", "group_label",
                  "sort_order", "is_active", "description",
                  "source_doctype", "source_field"},
            PROFILE: {"is_default", "is_active"},
        },
        "rows": {
            COMMON: [{"name": "CV1", "var_name": "W_mm", "var_type": "Float"}],
            ROW: [{"name": "RL1", "var_name": "unit_price",
                   "var_type": "Float",
                   "source_doctype": "Item Price",
                   "source_field": "price_list_rate"}],
        },
        "library_names": {"W_mm", "unit_price", "glass_master"},
        "singles": {"default_profile": "P_BOM_DEFAULT"},
        "default_profiles": {"P_BOM_DEFAULT"},
        "doctypes": {SETTINGS, COMMON, ROW},
        "site_path": tempfile.mkdtemp(prefix="al_backup_"),
        "deleted": [],
        "ddl": [],
        "queries": [],
        "thrown": [],
        "log_errors": [],
        "commits": 0,
        "merge_calls": [],
        "singles_cleared": [],
    }
    state.update(over)
    return state


class TestGate(unittest.TestCase):
    def test_thieu_bien_trong_library_thi_dung(self):
        """ĐỐI CHỨNG ÂM: bỏ 1 tên khỏi Library ⇒ throw, ⛔ xoá gì."""
        state = _default_state(library_names={"unit_price"})
        mod, saved, saved_merge = _load(state)
        try:
            with self.assertRaises(_Throw):
                mod.execute()
        finally:
            _restore(saved, saved_merge)
        self.assertFalse(state["ddl"], "đã DROP bảng dù dữ liệu chưa gộp đủ")
        self.assertFalse(state["deleted"], "đã xoá DocType dù cổng chặn")
        self.assertIn("W_mm", state["thrown"][0])

    def test_default_profile_chua_chuyen_thi_dung(self):
        """ĐỐI CHỨNG ÂM: default_profile có giá trị, chưa hồ sơ is_default."""
        state = _default_state(default_profiles=set())
        mod, saved, saved_merge = _load(state)
        try:
            with self.assertRaises(_Throw):
                mod.execute()
        finally:
            _restore(saved, saved_merge)
        self.assertFalse(state["ddl"])
        message = state["thrown"][0]
        # Câu chữ hướng người vận hành: nhãn màn hình + việc cần làm.
        self.assertIn("Hồ sơ mặc định", message)
        self.assertIn("Đang dùng", message)
        self.assertIn("bench --site", message)

    def test_default_profile_rong_thi_qua(self):
        """`default_profile` rỗng ⇒ không đòi hồ sơ mặc định (điều kiện đủ)."""
        state = _default_state(singles={}, default_profiles=set())
        mod, saved, saved_merge = _load(state)
        try:
            mod.execute()
        finally:
            _restore(saved, saved_merge)
        self.assertEqual(len(state["ddl"]), 3)


class TestHappyPath(unittest.TestCase):
    def setUp(self):
        self.state = _default_state()
        self.mod, self.saved, self.saved_merge = _load(self.state)
        self.mod.execute()

    def tearDown(self):
        _restore(self.saved, self.saved_merge)
        for name in os.listdir(self.state["site_path"]):
            path = os.path.join(self.state["site_path"], name)
            if os.path.isfile(path):
                os.unlink(path)
        os.rmdir(self.state["site_path"])

    def test_chay_lai_patch_gop_truoc_khi_xoa(self):
        """Phiên migrate đứt giữa đường vẫn được cứu — gộp chạy lại."""
        self.assertEqual(self.state["merge_calls"], [1])

    def test_sao_luu_du_lieu_truoc_khi_xoa(self):
        backups = [n for n in os.listdir(self.state["site_path"])
                   if n.endswith(".json")]
        self.assertEqual(len(backups), 1)
        payload = json.load(
            open(os.path.join(self.state["site_path"], backups[0]),
                 encoding="utf-8"))
        self.assertEqual(payload["singles"]["default_profile"],
                         "P_BOM_DEFAULT")
        self.assertEqual(payload[ROW][0]["source_field"], "price_list_rate")

    def test_xoa_doctype_record_con_truoc_cha_sau(self):
        names = [name for _, name in self.state["deleted"]]
        self.assertEqual(names, [COMMON, ROW, SETTINGS])

    def test_xoa_dong_singles(self):
        self.assertEqual(self.state["singles_cleared"], [(SETTINGS,)])

    def test_drop_du_3_bang(self):
        self.assertEqual(len(self.state["ddl"]), 3)
        for doctype in (COMMON, ROW, SETTINGS):
            self.assertIn("DROP TABLE IF EXISTS `tab%s`" % doctype,
                          self.state["ddl"])

    def test_idempotent_khi_bang_khong_con(self):
        """ĐỐI CHỨNG ÂM: chạy lại ⇒ không DROP/Singles thêm, không lỗi."""
        before = len(self.state["ddl"])
        self.state["tables"] = set()
        self.mod.execute()
        self.assertEqual(len(self.state["ddl"]), before)
        # Lượt sau vẫn dọn nốt dòng Singles nếu còn sót — nhưng KHÔNG DROP.
        self.assertEqual(len(self.state["singles_cleared"]), 2)

    def test_gate_chi_kiem_bien_con_trong_bang(self):
        """Không còn dòng nào ở bảng con ⇒ cổng rỗng, vẫn xoá được."""
        self.assertFalse(self.state["thrown"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
