"""Test THUẦN cho patch B10 — cấp quyền `AL Variable Profile` / `AL Formula Field`.

Kiểm:
  1. Cấp đúng nhân vật: Technical Admin ghi được; BOM Manager CHỈ ĐỌC.
  2. Hạ được quyền `write` cũ do vòng lặp module cấp (dùng `_set_full_docperm`).
  3. Idempotent: chạy 2 lần ⛔ không tạo bản ghi trùng.
  4. Thiếu Role / DocType ⇒ bỏ qua, ⛔ không ném.

Chạy:
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_grant_config_permissions.py
"""

import importlib.util
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
	sys.path.insert(0, _APP_ROOT)

_PATCH_REL = "alumglass/patches/v1_0/grant_config_permissions.py"
_PATCH_MOD = "alumglass.patches.v1_0.grant_config_permissions"
_ROLES_MOD = "alumglass.setup.install_roles"

TARGET_DOCTYPES = ("AL Variable Profile", "AL Formula Field")


# ══════════════════════════════════════════════════════════════════════
# Stub frappe
# ══════════════════════════════════════════════════════════════════════
class _Perm(dict):
	"""Bản ghi Custom DocPerm giả — gán thuộc tính cũng ghi vào dict."""

	def __init__(self, state):
		super().__init__()
		object.__setattr__(self, "_state", state)

	def __setattr__(self, key, value):
		if key.startswith("_"):
			object.__setattr__(self, key, value)
		else:
			self[key] = value

	def insert(self, ignore_permissions=False):
		self._state["counter"] += 1
		self["name"] = "CDP-%04d" % self._state["counter"]
		self._state["docperms"].append(self)


class _FakeDB:
	def __init__(self, state):
		self.state = state

	def exists(self, doctype, name=None):
		if isinstance(name, dict):
			for record in self.state["docperms"]:
				if all(record.get(key) == value for key, value in name.items()):
					return record["name"]
			return None
		if doctype == "DocType":
			return name if name in self.state["doctypes"] else None
		if doctype == "Role":
			return name if name in self.state["roles"] else None
		return None

	def set_value(self, doctype, name, values):
		for record in self.state["docperms"]:
			if record["name"] == name:
				record.update(values)
				return

	def commit(self):
		self.state["commits"] += 1


class _FakeFrappe(types.ModuleType):
	def __init__(self, state):
		super().__init__("frappe")
		self.__path__ = []
		self.state = state
		self.db = _FakeDB(state)

	def new_doc(self, doctype):
		return _Perm(self.state)


def _build_state(doctypes=None, roles=None, docperms=None):
	return {
		"doctypes": set(doctypes if doctypes is not None else TARGET_DOCTYPES),
		"roles": set(roles if roles is not None else ("AL BOM Manager", "AL Technical Admin")),
		"docperms": list(docperms or []),
		"counter": 0,
		"commits": 0,
	}


def _load_patch(state):
	saved = {}
	for name in ("frappe", _PATCH_MOD, _ROLES_MOD):
		saved[name] = sys.modules.get(name)
	sys.modules["frappe"] = _FakeFrappe(state)
	sys.modules.pop(_PATCH_MOD, None)
	sys.modules.pop(_ROLES_MOD, None)
	spec = importlib.util.spec_from_file_location(_PATCH_MOD, os.path.join(_APP_ROOT, _PATCH_REL))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module, saved


def _restore(saved):
	for name, old in saved.items():
		if old is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = old


def _find(state, doctype, role, permlevel=0):
	for record in state["docperms"]:
		if (
			record.get("parent") == doctype
			and record.get("role") == role
			and record.get("permlevel") == permlevel
		):
			return record
	return None


class TestGrantConfigPermissions(unittest.TestCase):
	def _run(self, state):
		module, saved = _load_patch(state)
		try:
			module.execute()
		finally:
			_restore(saved)
		return state

	def test_cap_dung_nhan_vat(self):
		state = self._run(_build_state())
		self.assertEqual(len(state["docperms"]), 4)
		for doctype in TARGET_DOCTYPES:
			admin = _find(state, doctype, "AL Technical Admin")
			manager = _find(state, doctype, "AL BOM Manager")
			self.assertIsNotNone(admin, doctype)
			self.assertIsNotNone(manager, doctype)
			self.assertEqual(admin["write"], 1, doctype)
			self.assertEqual(admin["create"], 1, doctype)
			self.assertEqual(admin["read"], 1, doctype)
			self.assertEqual(manager["read"], 1, doctype)
			self.assertEqual(manager["write"], 0, doctype)
			self.assertEqual(manager["create"], 0, doctype)

	def test_ha_quyen_write_cu_cua_module_loop(self):
		"""BOM Manager đã có full quyền (module loop) ⇒ phải bị HẠ."""
		state = _build_state()
		state["docperms"] = [
			{
				"name": "CDP-OLD",
				"parent": "AL Variable Profile",
				"role": "AL BOM Manager",
				"permlevel": 0,
				"read": 1,
				"write": 1,
				"create": 1,
				"delete": 1,
			}
		]
		self._run(state)
		manager = _find(state, "AL Variable Profile", "AL BOM Manager")
		self.assertEqual(manager["name"], "CDP-OLD", "phải CẬP NHẬT, không tạo mới")
		self.assertEqual(manager["write"], 0)
		self.assertEqual(manager["create"], 0)
		self.assertEqual(manager["delete"], 0)
		self.assertEqual(manager["read"], 1)
		# 3 record mới + 1 cập nhật.
		self.assertEqual(len(state["docperms"]), 4)

	def test_idempotent_chay_hai_lan(self):
		state = _build_state()
		self._run(state)
		first = len(state["docperms"])
		self._run(state)
		self.assertEqual(len(state["docperms"]), first, "chạy lại không được tạo bản ghi trùng")
		self.assertEqual(
			sorted(r["name"] for r in state["docperms"]), ["CDP-0001", "CDP-0002", "CDP-0003", "CDP-0004"]
		)

	def test_thieu_vai_thi_bo_qua_ca_doctype(self):
		"""Thiếu AL BOM Manager ⇒ không cấp Technical Admin nửa vời."""
		state = _build_state(roles=("AL Technical Admin",))
		try:
			self._run(state)
		except Exception as exc:
			self.fail("patch không được ném: %r" % exc)
		self.assertEqual(len(state["docperms"]), 0)

	def test_thieu_bom_manager_khong_ha_quyen_cu(self):
		"""Thiếu vai thay thế ⇒ ⛔ KHÔNG hạ quyền BOM Manager (tránh khoá đường sửa)."""
		state = _build_state(roles=("AL BOM Manager",))
		state["docperms"] = [
			{
				"name": "CDP-OLD",
				"parent": "AL Variable Profile",
				"role": "AL BOM Manager",
				"permlevel": 0,
				"read": 1,
				"write": 1,
				"create": 1,
			}
		]
		self._run(state)
		manager = _find(state, "AL Variable Profile", "AL BOM Manager")
		self.assertEqual(manager["write"], 1, "không được hạ khi thiếu Technical Admin")
		self.assertEqual(manager["create"], 1)
		self.assertEqual(len(state["docperms"]), 1)

	def test_thieu_doctype_bo_qua_khong_nem(self):
		state = _build_state(doctypes=("AL Variable Profile",))
		try:
			self._run(state)
		except Exception as exc:
			self.fail("patch không được ném: %r" % exc)
		self.assertEqual(len(state["docperms"]), 2)
		self.assertTrue(all(r["parent"] == "AL Variable Profile" for r in state["docperms"]))

	def test_co_commit_va_permlevel_0(self):
		state = self._run(_build_state())
		self.assertGreaterEqual(state["commits"], 1)
		for record in state["docperms"]:
			self.assertEqual(record["permlevel"], 0)


if __name__ == "__main__":
	unittest.main(verbosity=2)
