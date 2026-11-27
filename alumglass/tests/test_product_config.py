"""Test THUẦN cho B8/Đ1 — API "Cấu hình sản phẩm" (chỉ đọc).

Kiểm 4 điều bắt buộc của thiết kế:
  1. Đủ dữ liệu ⇒ 7 khối `ok=True`, `link` đúng route Desk, nhãn ưu tiên TÊN.
  2. Một khối thiếu bản ghi ⇒ CHỈ khối đó `ok=False` + câu tiếng Việt; khối
     khác còn nguyên.
  3. Một khối ném exception ⇒ không ném ra ngoài, khối khác còn nguyên.
  4. `error` ⛔ KHÔNG chứa traceback / tên exception / đường dẫn tệp.

Chạy:
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=~/myfrappe/apps/formula_builder python3 \
        alumglass/tests/test_product_config.py
"""

import importlib.util
import os
import sys
import types
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
	sys.path.insert(0, _APP_ROOT)

_API_REL = "alumglass/api/product_config.py"
_API_MOD = "alumglass.api.product_config"

WHITELISTED = []


# ══════════════════════════════════════════════════════════════════════
# Stub frappe
# ══════════════════════════════════════════════════════════════════════
class _Stop(Exception):
	"""Đại diện `frappe.throw` — chỉ để test thấy đã chặn."""


class _Doc(dict):
	def __getattr__(self, item):
		try:
			return self[item]
		except KeyError:
			raise AttributeError(item)


class _FakeDB:
	def __init__(self, state):
		self.state = state

	def exists(self, doctype, name=None):
		records = self.state["records"].get(doctype) or {}
		return name in records


class _FakeFrappe(types.ModuleType):
	def __init__(self, state):
		super().__init__("frappe")
		self.__path__ = []
		self.state = state
		self.db = _FakeDB(state)
		self.utils = types.SimpleNamespace(now=lambda: "2026-11-27 16:00:00")
		# `from frappe import _` cần thuộc tính này trên module.
		self._ = self._translate

	def _translate(self, message, *args, **kwargs):
		return message

	def whitelist(self, *args, **kwargs):
		def decorator(fn):
			WHITELISTED.append(fn.__name__)
			return fn

		return decorator

	def get_doc(self, doctype, name=None, *args, **kwargs):
		key = (doctype, name)
		if key in self.state["raise_on"]:
			raise self.state["raise_on"][key]
		record = (self.state["records"].get(doctype) or {}).get(name)
		if record is None:
			raise RuntimeError("record not found: %s %s" % (doctype, name))
		return _Doc(record)

	def has_permission(self, doctype, ptype="read", doc=None, *args, **kwargs):
		allowed = self.state["allowed"].get(doctype, True)
		if callable(allowed):
			return allowed(doc)
		return allowed

	def log_error(self, message, title=None):
		self.state["logs"].append((message, title))

	def get_traceback(self):
		return (
			"Traceback (most recent call last):\n"
			'  File "/home/nxc/site/apps/alumglass/x.py", line 3\n'
			"ZeroDivisionError: division by zero"
		)

	def throw(self, message, exc=None, title=None):
		raise _Stop(message)


def _build_state(records, allowed=None, raise_on=None):
	return {
		"records": records,
		"allowed": allowed or {},
		"raise_on": raise_on or {},
		"logs": [],
	}


def _full_records():
	return {
		"AL BOM": {
			"BOM-1": {
				"name": "BOM-1",
				"bom_name": "Cửa đi 2 cánh",
				"bom_code": "BOM-1",
				"is_active": 1,
				"bom_set": "SET-1",
				"pk_set": "ACC-1",
				"default_cost_template": "CT-1",
			},
		},
		"AL Bom Set": {
			"SET-1": {
				"name": "SET-1",
				"set_name": "Bộ BOM cửa đi",
				"set_code": "SET-1",
				"default_accessory_set": "ACC-1",
				"variable_set": "VAR-1",
				"variable_profile": "PROF-1",
				"items": [
					{"item_rule": "RULE-1"},
					{"item_rule": "RULE-2"},
					{"item_rule": ""},
				],
			},
		},
		"AL Accessory Set": {
			"ACC-1": {
				"name": "ACC-1",
				"set_name": "Bộ phụ kiện cửa đi",
				"set_code": "ACC-1",
				"variable_set": "VAR-1",
				"variable_profile": "PROF-1",
				"items": [{}, {}],
			},
		},
		"AL Variable Set": {
			"VAR-1": {
				"name": "VAR-1",
				"set_name": "Biến cửa đi",
				"set_code": "VAR-1",
				"items": [{}, {}],
			},
		},
		"AL Cost Template": {
			"CT-1": {
				"name": "CT-1",
				"template_name": "Mẫu giá cửa đi",
				"template_code": "CT-1",
				"variable_profile": "PROF-1",
				"items": [{}],
			},
		},
		"AL Variable Profile": {
			"PROF-1": {
				"name": "PROF-1",
				"profile_name": "Hồ sơ cửa đi",
				"profile_code": "PROF-1",
				"rules": [{}, {}],
			},
		},
		"AL Rule": {
			"RULE-1": {
				"name": "RULE-1",
				"rule_name": "Số bản lề theo chiều cao",
				"rule_code": "RULE-1",
			},
			"RULE-2": {
				"name": "RULE-2",
				"rule_name": "Hệ số nhân công theo độ cao",
				"rule_code": "RULE-2",
			},
		},
	}


def _load(state):
	saved = {}
	for name in ("frappe", _API_MOD):
		saved[name] = sys.modules.get(name)
	sys.modules["frappe"] = _FakeFrappe(state)
	sys.modules.pop(_API_MOD, None)
	spec = importlib.util.spec_from_file_location(_API_MOD, os.path.join(_APP_ROOT, _API_REL))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module, saved


def _restore(saved):
	for name, old in saved.items():
		if old is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = old


class _Base(unittest.TestCase):
	def run_api(self, records=None, allowed=None, raise_on=None, docname="BOM-1", doctype=None):
		state = _build_state(records or _full_records(), allowed, raise_on)
		module, saved = _load(state)
		self.addCleanup(_restore, saved)
		result = module.get_product_config(doctype=doctype, docname=docname)
		return result, state

	@staticmethod
	def by_key(result):
		return {block["key"]: block for block in result["blocks"]}


class TestFullConfig(_Base):
	def test_du_7_khoi_va_deu_ok(self):
		result, _ = self.run_api()
		self.assertTrue(result["ok"])
		self.assertEqual(len(result["blocks"]), 7)
		for block in result["blocks"]:
			self.assertTrue(block["ok"], "%s phải ok" % block["key"])
			self.assertEqual(block["error"], "", block["key"])

	def test_link_dung_route_desk(self):
		result, _ = self.run_api()
		blocks = self.by_key(result)
		expected = {
			"product": "/app/al-bom/BOM-1",
			"bom_set": "/app/al-bom-set/SET-1",
			"accessory_set": "/app/al-accessory-set/ACC-1",
			"variable_set": "/app/al-variable-set/VAR-1",
			"cost_template": "/app/al-cost-template/CT-1",
			"variable_profile": "/app/al-variable-profile/PROF-1",
			"rules": "/app/al-rule/RULE-1",
		}
		for key, link in expected.items():
			self.assertEqual(blocks[key]["link"], link, key)

	def test_uu_tien_ten_kem_ma(self):
		result, _ = self.run_api()
		blocks = self.by_key(result)
		self.assertEqual(blocks["bom_set"]["label"], "Bộ BOM cửa đi")
		self.assertEqual(blocks["bom_set"]["code"], "SET-1")
		self.assertEqual(blocks["cost_template"]["label"], "Mẫu giá cửa đi")
		self.assertEqual(blocks["variable_profile"]["label"], "Hồ sơ cửa đi")

	def test_detail_dem_dong(self):
		result, _ = self.run_api()
		blocks = self.by_key(result)
		self.assertEqual(blocks["bom_set"]["detail"], "3 dòng vật tư")
		self.assertEqual(blocks["variable_set"]["detail"], "2 biến")
		self.assertEqual(blocks["variable_profile"]["detail"], "2 quy tắc lọc")

	def test_quy_tac_co_nhieu_muc_va_link_tung_muc(self):
		result, _ = self.run_api()
		rules = self.by_key(result)["rules"]
		self.assertTrue(rules["ok"])
		self.assertEqual(len(rules["children"]), 2)
		self.assertEqual(
			[c["label"] for c in rules["children"]],
			["Số bản lề theo chiều cao", "Hệ số nhân công theo độ cao"],
		)
		self.assertEqual(rules["children"][1]["link"], "/app/al-rule/RULE-2")
		self.assertIn("2 quy tắc đang dùng", rules["detail"])

	def test_khong_co_quy_tac_la_trang_thai_hop_le(self):
		records = _full_records()
		records["AL Bom Set"]["SET-1"]["items"] = [{"item_rule": ""}]
		result, _ = self.run_api(records=records)
		rules = self.by_key(result)["rules"]
		self.assertTrue(rules["ok"], "không dùng quy tắc KHÔNG phải lỗi")
		self.assertEqual(rules["link"], "")
		self.assertIn("không dùng quy tắc nào", rules["detail"])

	def test_san_pham_ngung_dung_duoc_bao(self):
		records = _full_records()
		records["AL BOM"]["BOM-1"]["is_active"] = 0
		result, _ = self.run_api(records=records)
		self.assertIn("ngừng dùng", self.by_key(result)["product"]["detail"])

	def test_thieu_ten_thi_dung_ma(self):
		records = _full_records()
		records["AL Bom Set"]["SET-1"]["set_name"] = ""
		result, _ = self.run_api(records=records)
		block = self.by_key(result)["bom_set"]
		self.assertEqual(block["label"], "SET-1")
		self.assertEqual(block["code"], "SET-1")

	def test_api_duoc_whitelist(self):
		self.run_api()
		self.assertIn("get_product_config", WHITELISTED)


class TestBlockIsolation(_Base):
	def test_thieu_ban_ghi_chi_hong_mot_khoi(self):
		records = _full_records()
		del records["AL Cost Template"]["CT-1"]
		result, _ = self.run_api(records=records)
		blocks = self.by_key(result)
		self.assertFalse(blocks["cost_template"]["ok"])
		self.assertIn("mẫu tính giá", blocks["cost_template"]["error"])
		self.assertIn("xoá", blocks["cost_template"]["error"])
		for key in ("product", "bom_set", "accessory_set", "variable_set", "variable_profile", "rules"):
			self.assertTrue(blocks[key]["ok"], key)
		# Trang vẫn coi sản phẩm đọc được.
		self.assertTrue(result["ok"])

	def test_mot_khoi_nem_loi_khong_lam_hong_trang(self):
		state = _build_state(
			_full_records(), raise_on={("AL Variable Profile", "PROF-1"): RuntimeError("boom")}
		)
		module, saved = _load(state)
		self.addCleanup(_restore, saved)
		result = module.get_product_config(docname="BOM-1")
		blocks = self.by_key(result)
		self.assertFalse(blocks["variable_profile"]["ok"])
		for key in ("product", "bom_set", "accessory_set", "variable_set", "cost_template", "rules"):
			self.assertTrue(blocks[key]["ok"], key)
		self.assertTrue(state["logs"], "lỗi phải được ghi log ở server")

	def test_khoi_quy_tac_doc_duoc_thi_state_ok(self):
		"""Đối chứng âm: khối quy tắc đọc được ⛔ được mang state 'error'."""
		result, _ = self.run_api()
		block = self.by_key(result)["rules"]
		self.assertTrue(block["ok"])
		self.assertEqual(block["state"], "ok")
		self.assertEqual(block["error"], "")

	def test_khoi_chua_gan_la_trang_thai_rieng(self):
		"""Chưa gắn ⛔ phải giống "không đọc được": có việc phải làm, không phải sự cố."""
		records = _full_records()
		records["AL BOM"]["BOM-1"].pop("pk_set")
		records["AL Bom Set"]["SET-1"].pop("default_accessory_set")
		result, _ = self.run_api(records=records)
		block = self.by_key(result)["accessory_set"]
		self.assertEqual(block["state"], "empty")
		self.assertIn("chưa gắn", block["error"])
		self.assertTrue(block["fix_link"].endswith("/BOM-1"),
		                "phải có đường mở sản phẩm để gắn")

	def test_ban_ghi_bi_xoa_la_loi_doc(self):
		"""(đối chứng âm) Liên kết trỏ bản ghi đã xoá ⇒ state='error', ⛔ 'empty'."""
		records = _full_records()
		del records["AL Cost Template"]["CT-1"]
		result, _ = self.run_api(records=records)
		block = self.by_key(result)["cost_template"]
		self.assertEqual(block["state"], "error")
		self.assertIn("xoá", block["error"])

	def test_san_pham_ngung_dung_bao_cam(self):
		records = _full_records()
		records["AL BOM"]["BOM-1"]["is_active"] = 0
		result, _ = self.run_api(records=records)
		block = self.by_key(result)["product"]
		self.assertEqual(block["state"], "warning")
		self.assertIn("ngừng dùng", block["detail"])

	def test_khong_co_quyen_chi_hong_khoi_do(self):
		result, _ = self.run_api(allowed={"AL Bom Set": False})
		blocks = self.by_key(result)
		self.assertFalse(blocks["bom_set"]["ok"])
		self.assertIn("quyền", blocks["bom_set"]["error"])
		self.assertTrue(blocks["accessory_set"]["ok"])

	def test_khong_doc_duoc_san_pham_thi_noi_ro_phu_thuoc(self):
		result, _ = self.run_api(docname="BOM-MAT")
		self.assertFalse(result["ok"])
		blocks = self.by_key(result)
		self.assertFalse(blocks["product"]["ok"])
		for key, block in blocks.items():
			self.assertFalse(block["ok"], key)
		self.assertIn("không đọc được sản phẩm", blocks["bom_set"]["error"])

	def test_doctype_khac_bi_chan(self):
		state = _build_state(_full_records())
		module, saved = _load(state)
		self.addCleanup(_restore, saved)
		with self.assertRaises(_Stop):
			module.get_product_config(doctype="Item", docname="ITEM-1")

	def test_thieu_docname_bi_chan(self):
		state = _build_state(_full_records())
		module, saved = _load(state)
		self.addCleanup(_restore, saved)
		with self.assertRaises(_Stop):
			module.get_product_config(docname="")


class TestNoTracebackLeak(_Base):
	def _all_errors(self, result):
		messages = []
		for block in result["blocks"]:
			if block["error"]:
				messages.append(block["error"])
			for child in block.get("children") or []:
				if child.get("error"):
					messages.append(child["error"])
		return messages

	def test_exception_khong_lo_traceback(self):
		state = _build_state(
			_full_records(),
			raise_on={("AL Variable Profile", "PROF-1"): ZeroDivisionError("division by zero")},
		)
		module, saved = _load(state)
		self.addCleanup(_restore, saved)
		result = module.get_product_config(docname="BOM-1")
		messages = self._all_errors(result)
		self.assertTrue(messages)
		for message in messages:
			for forbidden in (
				"Traceback",
				"ZeroDivisionError",
				"division by",
				".py",
				"/home/",
				"RuntimeError",
			):
				self.assertNotIn(forbidden, message)

	def test_ban_ghi_bi_xoa_khong_lo_ma_loi(self):
		records = _full_records()
		del records["AL Rule"]["RULE-2"]
		result, _ = self.run_api(records=records)
		messages = self._all_errors(result)
		self.assertTrue(messages)
		for message in messages:
			for forbidden in ("Traceback", "DoesNotExistError", "None", ".py", "/home/"):
				self.assertNotIn(forbidden, message)

	def test_cau_loi_la_tieng_viet(self):
		records = _full_records()
		del records["AL Accessory Set"]["ACC-1"]
		result, _ = self.run_api(records=records)
		messages = self._all_errors(result)
		self.assertTrue(messages)
		self.assertTrue(any("Không đọc được" in m for m in messages))


if __name__ == "__main__":
	unittest.main(verbosity=2)
