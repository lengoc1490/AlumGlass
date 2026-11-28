"""Test THUẦN cho patch `v1_0.repair_variable_library_list_sort`.

Lỗi thật cần chặn: mở danh sách `AL Variable Library` ném
`PermissionError: You do not have permission to access field: ...category`
vì lựa chọn sắp xếp cũ của người dùng (bảng `__UserSettings`) vẫn trỏ tới ô
`category` đã bỏ.

Bảo vệ 4 tính chất — mỗi nhóm có ĐỐI CHỨNG ÂM:

  1. Chỉ sửa khi trỏ tới ô KHÔNG còn (đúng ô ⇒ để yên).
  2. Sửa cả `filters` trỏ tới ô đã bỏ; điều kiện hợp lệ giữ nguyên.
  3. Sửa `DocType.sort_field` hỏng; xoá cache của người vừa sửa.
  4. IDEMPOTENT + không chặn migrate khi đọc hỏng.

Chạy:
    python3 alumglass/tests/test_repair_variable_library_list_sort.py
"""
import importlib.util
import json
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

_PATCH_REL = "alumglass/patches/v1_0/repair_variable_library_list_sort.py"
LIB = "AL Variable Library"

#: Các ô ĐANG có sau khi bỏ `category`.
_FIELDS = ("var_name", "var_label", "var_type", "is_system", "usage",
           "group_label", "is_input", "sort_order", "is_active",
           "link_doctype", "select_options", "source_doctype",
           "source_field", "source_link_field", "default_value",
           "description")


class _FakeMeta:
    def __init__(self, fields=_FIELDS, title_field="var_label"):
        self.fields = [types.SimpleNamespace(fieldname=f) for f in fields]
        self.title_field = title_field
        self.image_field = ""


class _FakeCache:
    def __init__(self, entries=None):
        self.deleted = []
        self.fail = False
        self.entries = entries or {}

    def hdel(self, name, key):
        if self.fail:
            raise RuntimeError("cache chết")
        self.deleted.append((name, key))
        self.entries.pop(key, None)

    def hgetall(self, name):
        return dict(self.entries)


class _FakeDB:
    def __init__(self, state):
        self.state = state

    def exists(self, doctype, name=None, *a, **k):
        return bool(self.state["installed"]) if doctype == "DocType" else None

    def get_value(self, doctype, name, field, *a, **k):
        return self.state["sort_field"]

    def set_value(self, doctype, name, field, value, update_modified=True):
        self.state["set_values"].append((doctype, name, field, value))

    def sql(self, query, values=None, as_dict=False):
        normalized = " ".join(query.split()).lower()
        if self.state["select_fails"] and "from `__usersettings`" in normalized:
            raise RuntimeError("bảng khoá")
        if "from `__usersettings`" in normalized:
            return [dict(r) for r in self.state["rows"]]
        if normalized.startswith("update `__usersettings`"):
            payload, user, doctype = values
            self.state["updates"].append((payload, user, doctype))
            # Ghi thật vào bản giả để lượt chạy thứ hai thấy dữ liệu đã sửa.
            for row in self.state["rows"]:
                if row["user"] == user:
                    row["data"] = payload
            return []
        return []

    def commit(self):
        self.state["commits"] += 1


def _build_frappe(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.get_meta = lambda doctype: _FakeMeta(fields=state["fields"])
    frappe.clear_cache = lambda *a, **k: state["cache_cleared"].append(k or a)
    frappe.cache = state["cache"]
    frappe.log_error = lambda *a, **k: state["log_errors"].append(
        k.get("title") or "")
    frappe.get_traceback = lambda: "traceback"
    return frappe


def _load(state):
    saved = sys.modules.get("frappe")
    sys.modules["frappe"] = _build_frappe(state)
    sys.modules.pop(
        "alumglass.patches.v1_0.repair_variable_library_list_sort", None)
    spec = importlib.util.spec_from_file_location(
        "alumglass.patches.v1_0.repair_variable_library_list_sort",
        os.path.join(_APP_ROOT, _PATCH_REL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, saved


def _restore(saved):
    if saved is None:
        sys.modules.pop("frappe", None)
    else:
        sys.modules["frappe"] = saved


def _state(**over):
    state = {
        "installed": True,
        "fields": _FIELDS,
        "sort_field": "group_label",
        "rows": [],
        "set_values": [],
        "updates": [],
        "cache_cleared": [],
        "log_errors": [],
        "commits": 0,
        "cache": _FakeCache(),
        "select_fails": False,
    }
    state.update(over)
    return state


def _row(user, data):
    return {"user": user, "data": data if isinstance(data, str)
            else json.dumps(data)}


class TestUserSettings(unittest.TestCase):
    def _run(self, state):
        mod, saved = _load(state)
        try:
            mod.execute()
        finally:
            _restore(saved)
        return state

    def test_sap_xep_cu_chuyen_ve_group_label(self):
        state = self._run(_state(rows=[
            _row("an", {"List": {"sort_by": "category", "sort_order": "desc"}}),
        ]))
        self.assertEqual(len(state["updates"]), 1)
        payload = json.loads(state["updates"][0][0])
        self.assertEqual(payload["List"]["sort_by"], "group_label")
        # Chiều sắp xếp người dùng đã chọn phải giữ nguyên.
        self.assertEqual(payload["List"]["sort_order"], "desc")

    def test_sap_xep_dung_thi_khong_ghi(self):
        """ĐỐI CHỨNG ÂM: ô còn tồn tại ⇒ không ghi, không xoá cache."""
        state = self._run(_state(rows=[
            _row("an", {"List": {"sort_by": "var_name", "sort_order": "asc"}}),
        ]))
        self.assertEqual(state["updates"], [])
        self.assertEqual(state["cache"].deleted, [])

    def test_khong_co_sap_xep_thi_de_yen(self):
        state = self._run(_state(rows=[
            _row("an", {"List": {"filters": []}}),
            _row("binh", "không phải json"),
            _row("chi", {"last_view": "List"}),
        ]))
        self.assertEqual(state["updates"], [])

    def test_bo_dieu_kien_loc_tro_toi_o_da_bo(self):
        state = self._run(_state(rows=[
            _row("an", {"List": {"sort_by": "category", "filters": [
                [LIB, "category", "=", "Thi công"],
                [LIB, "var_type", "=", "Float"],
            ]}}),
        ]))
        payload = json.loads(state["updates"][0][0])
        self.assertEqual(payload["List"]["filters"],
                         [[LIB, "var_type", "=", "Float"]])

    def test_xoa_cache_cua_nguoi_vua_sua(self):
        state = self._run(_state(rows=[
            _row("an", {"List": {"sort_by": "category"}}),
            _row("binh", {"List": {"sort_by": "category"}}),
            _row("chi", {"List": {"sort_by": "var_name"}}),
        ]))
        self.assertEqual(sorted(state["cache"].deleted), [
            ("_user_settings", "%s::an" % LIB),
            ("_user_settings", "%s::binh" % LIB),
        ])

    def test_khong_con_group_label_thi_lui_ve_modified(self):
        state = self._run(_state(
            fields=("var_name", "var_label"),
            rows=[_row("an", {"List": {"sort_by": "category"}})],
        ))
        payload = json.loads(state["updates"][0][0])
        self.assertEqual(payload["List"]["sort_by"], "modified")


class TestCache(unittest.TestCase):
    def _run(self, state):
        mod, saved = _load(state)
        try:
            mod.execute()
        finally:
            _restore(saved)
        return state

    def _cache(self, entries):
        return _FakeCache(entries)

    def test_cache_con_gia_tri_cu_thi_xoa(self):
        """Bản cũ có thể chỉ nằm ở Redis, chưa kịp đồng bộ xuống DB."""
        state = _state(rows=[])
        state["cache"] = self._cache({
            "%s::an" % LIB: json.dumps({"List": {"sort_by": "category"}}),
        })
        self._run(state)
        self.assertEqual(state["cache"].deleted,
                         [("_user_settings", "%s::an" % LIB)])

    def test_cache_gia_tri_dung_va_doctype_khac_thi_giu(self):
        """ĐỐI CHỨNG ÂM: sắp xếp hợp lệ hoặc của DocType khác ⇒ ⛔ xoá."""
        state = _state(rows=[])
        state["cache"] = self._cache({
            "%s::an" % LIB: json.dumps({"List": {"sort_by": "var_name"}}),
            "Item::an": json.dumps({"List": {"sort_by": "category"}}),
            "%s::binh" % LIB: json.dumps({"last_view": "List"}),
        })
        self._run(state)
        self.assertEqual(state["cache"].deleted, [])

    def test_gia_tri_cache_dang_bytes_van_doc_duoc(self):
        state = _state(rows=[])
        state["cache"] = self._cache({
            ("%s::an" % LIB).encode(): json.dumps(
                {"List": {"sort_by": "category"}}).encode(),
        })
        self._run(state)
        self.assertEqual(state["cache"].deleted,
                         [("_user_settings", "%s::an" % LIB)])


class TestDocTypeSortField(unittest.TestCase):
    def _run(self, state):
        mod, saved = _load(state)
        try:
            mod.execute()
        finally:
            _restore(saved)
        return state

    def test_sort_field_hong_thi_sua(self):
        state = self._run(_state(sort_field="category"))
        self.assertEqual(
            state["set_values"],
            [("DocType", LIB, "sort_field", "group_label")])
        self.assertTrue(state["cache_cleared"])

    def test_sort_field_dung_thi_de_yen(self):
        """ĐỐI CHỨNG ÂM: sort_field hợp lệ ⇒ không ghi."""
        state = self._run(_state(sort_field="group_label"))
        self.assertEqual(state["set_values"], [])


class TestBen(unittest.TestCase):
    def _run(self, state):
        mod, saved = _load(state)
        try:
            mod.execute()
            mod.execute()
        finally:
            _restore(saved)
        return state

    def test_idempotent(self):
        """Chạy 2 lượt ⇒ lượt sau không ghi thêm gì."""
        state = self._run(_state(rows=[
            _row("an", {"List": {"sort_by": "category"}}),
        ]))
        self.assertEqual(len(state["updates"]), 1)
        payload = json.loads(state["updates"][0][0])
        self.assertEqual(payload["List"]["sort_by"], "group_label")

    def test_doc_hong_thi_khong_nem(self):
        """⛔ chặn migrate vì bảng phụ đọc không được."""
        state = self._run(_state(select_fails=True, rows=[]))
        self.assertTrue(state["log_errors"], "phải ghi Error Log")
        self.assertEqual(state["updates"], [])

    def test_cache_chet_khong_nem(self):
        state = _state(rows=[
            _row("an", {"List": {"sort_by": "category"}}),
        ])
        state["cache"].fail = True
        self._run(state)
        self.assertEqual(len(state["updates"]), 1)

    def test_chua_cai_doctype_thi_bo_qua(self):
        state = self._run(_state(installed=False, sort_field="category"))
        self.assertEqual(state["set_values"], [])
        self.assertEqual(state["updates"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
