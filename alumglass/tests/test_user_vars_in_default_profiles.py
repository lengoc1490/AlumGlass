"""Test THUẦN cho patch `v1_0.user_vars_in_default_profiles` (B3b/Đ3).

Không cần site: `frappe` được stub trong bộ nhớ, patch nạp lại bằng
`importlib` cho từng ca. Danh sách profile mặc định đọc từ CHÍNH hai patch
seed (`seed_variable_catalog`, `seed_bom_profile`) — ⛔ không chép tay, để
lần sau đổi mã profile thì test tự bắt được lệch.

CÁCH CHẠY
---------
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_user_vars_in_default_profiles.py
Hoặc qua bench:
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_user_vars_in_default_profiles
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

from alumglass.variable_sources.rules import (  # noqa: E402
    INCLUDE_ALL,
    active_source_kinds,
)

_PATCH_REL = "alumglass/patches/v1_0/user_vars_in_default_profiles.py"
_SEED_BOM_PROFILE_REL = "alumglass/patches/v28_14/seed_bom_profile.py"
_SEED_CATALOG_REL = "alumglass/patches/v28_14/seed_variable_catalog.py"

PROFILE_DOCTYPE = "AL Variable Profile"
CONSTANT_DOCTYPE = "Formula Global Variable"
CONSTANT_ROLE = "AL BOM Manager"
SOURCE_KIND = "variable_library_user"

_FAKE_MODULES = ("frappe",)


# ══════════════════════════════════════════════════════════════════════
# Stub frappe — chỉ đủ bề mặt patch + `_upsert_docperm` chạm tới
# ══════════════════════════════════════════════════════════════════════
class _FakeProfileDoc(object):
    def __init__(self, values, state):
        self.values = values
        self.flags = types.SimpleNamespace()
        self._state = state

    def get(self, key, default=None):
        return self.values.get(key, default)

    def append(self, table, row):
        self.values.setdefault(table, []).append(dict(row))

    def save(self):
        self._state["saves"].append(self.values)
        self._state["profiles"][self.values["name"]] = self.values


class _FakeDocPerm(object):
    def __init__(self, state):
        self.state = state
        self.values = {}

    def update(self, values):
        self.values.update(values)

    def insert(self, ignore_permissions=False):
        # `_upsert_docperm` gán `parent`/`role`/`permlevel` thành THUỘC TÍNH
        # rồi mới `.update(perm_values)` — phải gộp cả hai nguồn.
        values = dict(self.values)
        for key in ("parent", "role", "permlevel"):
            if hasattr(self, key):
                values[key] = getattr(self, key)
        values.setdefault("permlevel", 0)
        perm_key = (values.get("parent"), values.get("role"),
                    values.get("permlevel", 0))
        self.state["docperms"][perm_key] = values


class _FakeDB(object):
    def __init__(self, state):
        self.state = state

    def exists(self, doctype, filters=None):
        if doctype == "DocType":
            return True if filters in self.state["doctypes"] else None
        if doctype == "Role":
            return True if filters in self.state["roles"] else None
        if doctype == "Custom DocPerm":
            key = (
                filters.get("parent"),
                filters.get("role"),
                filters.get("permlevel", 0),
            )
            return True if key in self.state["docperms"] else None
        if doctype == PROFILE_DOCTYPE:
            return True if filters in self.state["profiles"] else None
        return None

    def set_value(self, doctype, name, values):
        key = (name, values.get("role"), values.get("permlevel", 0))
        self.state["docperms"][key] = dict(values)

    def commit(self):
        self.state["commits"] += 1


def _profile(code, rules=None):
    return {
        "name": code,
        "profile_code": code,
        "default_action": "EXCLUDE_ALL",
        "rules": [dict(row) for row in (rules or [])],
    }


def _default_state(**overrides):
    state = {
        "doctypes": {PROFILE_DOCTYPE, CONSTANT_DOCTYPE},
        "roles": {CONSTANT_ROLE},
        "profiles": {
            "P_BOM_DEFAULT": _profile("P_BOM_DEFAULT", [
                {"source_kind": "variable_library_system",
                 "action": "Include", "is_active": 1},
                {"source_kind": "slug_reference",
                 "action": "Include", "is_active": 1},
            ]),
            "P_COST_TEMPLATE_DEFAULT": _profile(
                "P_COST_TEMPLATE_DEFAULT", [
                    {"source_kind": "cost_bucket",
                     "action": "Include", "is_active": 1},
                ]),
            "P_ACCESSORY_DEFAULT": _profile("P_ACCESSORY_DEFAULT", [
                {"source_kind": "row_literal",
                 "action": "Include", "is_active": 1},
            ]),
        },
        "docperms": {},
        "saves": [],
        "commits": 0,
    }
    state.update(overrides)
    return state


def _build_frappe_stub(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.get_doc = lambda doctype_or_values=None, name=None, *a, **k: (
        _FakeProfileDoc(state["profiles"][name], state)
        if name is not None else _FakeProfileDoc(dict(doctype_or_values), state)
    )
    frappe.new_doc = lambda doctype: _FakeDocPerm(state)
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    frappe._ = lambda s: s
    return frappe


def _load_source(module_name, rel_path):
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_APP_ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _Stubbed(object):
    """Cài stub frappe + nạp module, KHÔI PHỤC nguyên trạng khi thoát."""

    def __init__(self, state=None):
        self.state = state or _default_state()
        self._saved = {}

    def __enter__(self):
        self._saved = {n: sys.modules.get(n) for n in _FAKE_MODULES}
        frappe = _build_frappe_stub(self.state)
        sys.modules["frappe"] = frappe
        # `setup.install_roles` bind `frappe` lúc import ⇒ phải nạp lại theo
        # stub hiện tại, nếu không ca sau dùng nhầm stub của ca trước.
        sys.modules.pop("alumglass.setup.install_roles", None)
        sys.modules.pop("alumglass.patches.v1_0.user_vars_in_default_profiles",
                        None)
        self.frappe = frappe
        return self

    def load(self, module_name, rel_path):
        return _load_source(module_name, rel_path)

    def __exit__(self, *exc):
        for name, old in self._saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        return False


def _load_patch(state=None):
    stubbed = _Stubbed(state)
    stubbed.__enter__()
    mod = stubbed.load(
        "alumglass.patches.v1_0.user_vars_in_default_profiles", _PATCH_REL)
    return stubbed, mod


def _seed_profile_codes():
    """Mã 3 profile mặc định — đọc từ chính 2 patch seed."""
    with _Stubbed() as stubbed:
        catalog = stubbed.load(
            "alumglass.patches.v28_14.seed_variable_catalog", _SEED_CATALOG_REL)
        bom = stubbed.load(
            "alumglass.patches.v28_14.seed_bom_profile", _SEED_BOM_PROFILE_REL)
        codes = {cfg["profile_code"] for cfg in catalog._PROFILES}
        codes.add(bom.PROFILE_CODE)
    return codes


def _rules_of(profile, source_kind):
    return [row for row in profile["rules"]
            if (row.get("source_kind") or "").strip() == source_kind]


class TestIncludeUserLibrary(unittest.TestCase):
    """Rule mới: đúng nguồn, đúng nhóm, idempotent, tôn trọng admin."""

    def test_them_rule_cho_ca_3_profile_mac_dinh(self):
        state = _default_state()
        stubbed, patch = _load_patch(state)
        try:
            self.assertEqual(set(patch.PROFILE_RULES), _seed_profile_codes())
            patch.execute()
        finally:
            stubbed.__exit__()

        for code in patch.PROFILE_RULES:
            rows = _rules_of(state["profiles"][code], SOURCE_KIND)
            self.assertEqual(len(rows), 1, code)
            row = rows[0]
            self.assertEqual(row["action"], "Include")
            self.assertEqual(row["source_ref"], "*")
            self.assertEqual(row["is_active"], 1)
            self.assertEqual(row["group_label"],
                             patch.PROFILE_RULES[code][0])
            self.assertEqual(row["sort_order"],
                             patch.PROFILE_RULES[code][1])

    def test_chay_lai_khong_nhan_doi(self):
        state = _default_state()
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
            patch.execute()
        finally:
            stubbed.__exit__()

        for code in patch.PROFILE_RULES:
            self.assertEqual(
                len(_rules_of(state["profiles"][code], SOURCE_KIND)), 1, code)

    def test_admin_da_include_thi_khong_dong_vao(self):
        state = _default_state()
        profile = state["profiles"]["P_BOM_DEFAULT"]
        profile["rules"].append({
            "source_kind": SOURCE_KIND, "action": "Include",
            "source_ref": "W_mm", "sort_order": 99, "is_active": 1,
        })
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
        finally:
            stubbed.__exit__()

        rows = _rules_of(profile, SOURCE_KIND)
        self.assertEqual(len(rows), 1)
        # Giữ nguyên rule admin đã đặt (ref hẹp `W_mm`, sort 99).
        self.assertEqual(rows[0]["source_ref"], "W_mm")
        self.assertEqual(rows[0]["sort_order"], 99)
        self.assertNotIn("group_label", rows[0])

    def test_admin_da_exclude_thi_ton_trong(self):
        """Exclude là quyết định ẩn có chủ ý — ⛔ thêm Include đối nghịch."""
        state = _default_state()
        profile = state["profiles"]["P_ACCESSORY_DEFAULT"]
        profile["rules"].append({
            "source_kind": SOURCE_KIND, "action": "Exclude", "is_active": 1,
        })
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
        finally:
            stubbed.__exit__()

        rows = _rules_of(profile, SOURCE_KIND)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "Exclude")

    def test_profile_chua_co_thi_bo_qua(self):
        state = _default_state()
        del state["profiles"]["P_COST_TEMPLATE_DEFAULT"]
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
        finally:
            stubbed.__exit__()

        self.assertIn("P_BOM_DEFAULT", state["profiles"])
        self.assertNotIn("P_COST_TEMPLATE_DEFAULT", state["profiles"])

    def test_thieu_doctype_profile_thi_throw(self):
        """Đối chứng âm: patches.txt sai thứ tự ⇒ phải nổ, ⛔ bỏ qua im lặng."""
        state = _default_state(doctypes={CONSTANT_DOCTYPE})
        stubbed, patch = _load_patch(state)
        try:
            with self.assertRaises(RuntimeError):
                patch.execute()
        finally:
            stubbed.__exit__()


class TestConstantPermission(unittest.TestCase):
    """R4: bảng hằng số ở `formula_builder` nhưng BOM Manager phải mở được."""

    def test_cap_quyen_cho_bom_manager(self):
        state = _default_state()
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
        finally:
            stubbed.__exit__()

        key = (CONSTANT_DOCTYPE, CONSTANT_ROLE, 0)
        self.assertIn(key, state["docperms"])
        perms = state["docperms"][key]
        for action in ("read", "write", "create", "delete", "report",
                       "export"):
            self.assertEqual(perms.get(action), 1, action)

    def test_thieu_role_thi_khong_cap(self):
        state = _default_state(roles=set())
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
        finally:
            stubbed.__exit__()

        self.assertEqual(state["docperms"], {})

    def test_thieu_formula_builder_thi_khong_cap_va_khong_no(self):
        state = _default_state(doctypes={PROFILE_DOCTYPE})
        stubbed, patch = _load_patch(state)
        try:
            patch.execute()
        finally:
            stubbed.__exit__()

        self.assertEqual(state["docperms"], {})
        # Rule biến người dùng vẫn được thêm — 2 việc độc lập.
        self.assertEqual(
            len(_rules_of(state["profiles"]["P_BOM_DEFAULT"], SOURCE_KIND)), 1)


class TestNoProfileShowsAll(unittest.TestCase):
    """Đ3: "không gán profile ⇒ hiện tất cả" — khoá hành vi ở tầng luật."""

    ALL = {"variable_library_system", "variable_library_user",
           "variable_set", "common_var", "formula_global", "fvb_scope",
           "row_literal", "slug_reference"}

    def test_profile_rong_include_all_chay_moi_nguon(self):
        kinds = active_source_kinds([], INCLUDE_ALL, self.ALL)
        self.assertIn(SOURCE_KIND, kinds)
        # `slug_reference` không phải adapter biến — xử lý riêng.
        self.assertEqual(kinds, self.ALL - {"slug_reference"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
