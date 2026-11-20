# -*- coding: utf-8 -*-
"""Test THUẦN cho patch `v28_14.seed_bom_profile` (profile `P_BOM_DEFAULT`).

Không cần site: `frappe` được stub trong bộ nhớ, patch được nạp lại bằng
`importlib` cho từng ca. Hằng số (`FORMULA_FIELDS`, `ENGINE_SYNTHETIC_FIELDS`,
`_ROW_LITERALS`, danh sách adapter) đọc từ CHÍNH MÃ NGUỒN — ⛔ không chép tay,
để lần sau thêm field/nguồn biến thì test tự bắt được lệch.

CÁCH CHẠY
---------
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_seed_bom_profile.py
Hoặc qua bench:
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_seed_bom_profile
"""
import importlib
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

# rules.py là THUẦN Python (không import frappe) — dùng để biết giá trị
# default_action hợp lệ mà không cần stub.
from alumglass.variable_sources.rules import EXCLUDE_ALL  # noqa: E402

_PATCH_REL = "alumglass/patches/v28_14/seed_bom_profile.py"
_OLD_PATCH_REL = "alumglass/patches/v28_14/seed_variable_catalog.py"
_BOM_ITEM_REL = "alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.py"
_RULE_JSON_REL = (
    "alumglass/al_master_data/doctype/al_variable_profile_rule/"
    "al_variable_profile_rule.json")

PROFILE_DOCTYPE = "AL Variable Profile"
BOM_SET = "AL Bom Set"

# `slug_reference` KHÔNG phải adapter biến — references xử lý riêng
# (xem variable_sources/rules.py::active_source_kinds). Đây là ngoại lệ DUY
# NHẤT được phép; test bên dưới kiểm nó không nằm trong sổ adapter và có
# trong options của doctype rule.
REFERENCE_KIND = "slug_reference"

_FAKE_MODULES = (
    "frappe",
    "frappe.model",
    "frappe.model.document",
)


# ══════════════════════════════════════════════════════════════════════
# Stub frappe — chỉ đủ bề mặt mà patch + al_bom_item.py chạm tới
# ══════════════════════════════════════════════════════════════════════
class _FakeDoc(object):
    """Đứng thay `frappe.get_doc(...)` — chỉ cần flags + insert()."""

    def __init__(self, values, state):
        self.values = values
        self.flags = types.SimpleNamespace()
        self._state = state

    def insert(self):
        self._state["inserts"].append(self.values)
        self._state["profiles"].add(self.values["profile_code"])


class _FakeDB(object):
    def __init__(self, state):
        self.state = state

    def exists(self, doctype, filters=None):
        if doctype == "DocType":
            return True if filters in self.state["doctypes"] else None
        if doctype == PROFILE_DOCTYPE:
            return True if filters in self.state["profiles"] else None
        return None

    def has_column(self, doctype, column):
        return column in self.state["columns"].get(doctype, set())

    def set_value(self, doctype, name, field, value, update_modified=True):
        self.state["set_value_calls"].append({
            "doctype": doctype,
            "name": name,
            "field": field,
            "value": value,
            "update_modified": update_modified,
        })
        # Giả lập DB ghi thật: lần chạy sau phải thấy cột đã có giá trị.
        for row in self.state["records"].get(doctype, []):
            if row["name"] == name:
                row[field] = value

    def commit(self):
        self.state["commits"] += 1


def _default_state(**overrides):
    """Trạng thái DB giả: 2 Bom Set trống profile + đã có doctype/column."""
    state = {
        "doctypes": {PROFILE_DOCTYPE},
        "profiles": set(),
        "columns": {BOM_SET: {"variable_profile"}},
        "records": {
            BOM_SET: [
                {"name": "BOM-001", "variable_profile": ""},
                {"name": "BOM-002", "variable_profile": ""},
            ],
        },
        "set_value_calls": [],
        "inserts": [],
        "commits": 0,
    }
    state.update(overrides)
    return state


def _build_frappe_stub(state):
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    frappe.db = _FakeDB(state)
    frappe.get_doc = lambda values=None, *a, **k: _FakeDoc(
        dict(values or {}), state)
    frappe.get_all = lambda doctype, fields=None, **k: [
        dict(row) for row in state["records"].get(doctype, [])]
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    frappe.whitelist = lambda *a, **k: (lambda fn: fn)
    frappe.msgprint = lambda *a, **k: None
    frappe._ = lambda s: s

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")

    class Document(object):
        pass

    document.Document = Document
    model.document = document
    frappe.model = model
    return frappe


def _load_source(module_name, rel_path):
    """Nạp file .py theo đường dẫn thành module mang tên `module_name`."""
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
        sys.modules["frappe.model"] = frappe.model
        sys.modules["frappe.model.document"] = frappe.model.document
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


# ── Đọc hằng số từ mã nguồn ───────────────────────────────────────────
def _bom_item_constants():
    with _Stubbed():
        mod = _load_source(
            "alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item",
            _BOM_ITEM_REL)
        return tuple(mod.FORMULA_FIELDS), tuple(mod.ENGINE_SYNTHETIC_FIELDS)


def _old_patch_module():
    with _Stubbed():
        return _load_source(
            "alumglass.patches.v28_14.seed_variable_catalog", _OLD_PATCH_REL)


def _registered_adapter_kinds():
    """source_kind đã đăng ký thật trong registry (import adapters để chạy decorator)."""
    with _Stubbed():
        importlib.import_module("alumglass.variable_sources.adapters")
    from alumglass.variable_sources.registry import get_adapters
    return {a.source_kind for a in get_adapters()}


def _rule_doctype_source_kinds():
    """Options của `AL Variable Profile Rule.source_kind` — nguồn chuẩn của UI."""
    with open(os.path.join(_APP_ROOT, _RULE_JSON_REL), encoding="utf-8") as fh:
        doc = json.load(fh)
    for field in doc.get("fields", []):
        if field.get("fieldname") == "source_kind":
            return {
                line.strip() for line in (field.get("options") or "").splitlines()
                if line.strip()
            }
    raise AssertionError("Không tìm thấy field source_kind trong doctype JSON")


class TestProfileDefinition(unittest.TestCase):
    """Nội dung profile phải bám đúng runtime B4."""

    @classmethod
    def setUpClass(cls):
        with _Stubbed():
            cls.patch = _load_source(
                "alumglass.patches.v28_14.seed_bom_profile", _PATCH_REL)

    def test_profile_code_khong_trung_profile_cu(self):
        old = _old_patch_module()
        old_codes = {cfg["profile_code"] for cfg in old._PROFILES}
        self.assertNotIn(self.patch.PROFILE_CODE, old_codes)
        self.assertEqual(old_codes, {"P_COST_TEMPLATE_DEFAULT",
                                     "P_ACCESSORY_DEFAULT"})

    def test_default_action_dung_hang_so_rules(self):
        self.assertEqual(self.patch.DEFAULT_ACTION, EXCLUDE_ALL)

    def test_source_kind_la_don_vi_hop_le(self):
        allowed = _registered_adapter_kinds() | {REFERENCE_KIND}
        for action, kind, ref, group, sort_order in self.patch.RULES:
            self.assertIn(kind, allowed,
                          "source_kind lạ trong profile: %s" % kind)
            self.assertEqual(action, "Include")

    def test_slug_reference_dung_la_ngoai_le_duy_nhat(self):
        """Chỉ `slug_reference` được phép KHÔNG phải adapter, và phải có trong options."""
        adapters = _registered_adapter_kinds()
        options = _rule_doctype_source_kinds()
        self.assertNotIn(REFERENCE_KIND, adapters)
        self.assertIn(REFERENCE_KIND, options)
        used = {kind for _a, kind, _r, _g, _s in self.patch.RULES}
        self.assertEqual(used - adapters, {REFERENCE_KIND})
        self.assertTrue(used <= options, "source_kind không có trong options: %s"
                        % (used - options))

    def test_source_ref_auto_viet_hoa(self):
        for action, kind, ref, group, sort_order in self.patch.RULES:
            if ref in ("*", "items"):
                continue
            self.assertEqual(ref, "AUTO",
                             "source_ref phải là AUTO viết HOA: %r" % ref)
            self.assertEqual(ref, ref.upper())

    def test_thu_tu_group_va_sort_order(self):
        sort_orders = [row[4] for row in self.patch.RULES]
        self.assertEqual(sort_orders, sorted(sort_orders))
        self.assertEqual(len(set(sort_orders)), len(sort_orders))
        for row in self.patch.RULES:
            self.assertTrue(row[3].strip(), "Thiếu group_label: %s" % (row,))

    def test_cross_row_fields_trong_superset_cua_bom_set(self):
        """Mọi field cross-row phải được engine B4 THẬT SỰ tạo."""
        formula_fields, synthetic_fields = _bom_item_constants()
        row_literals = {row[0] for row in _old_patch_module()._ROW_LITERALS}
        allowed = set(formula_fields) | set(synthetic_fields) | row_literals

        declared = set(json.loads(self.patch.CROSS_ROW[0]["fields"]))
        self.assertTrue(declared <= allowed,
                        "Field engine không tạo: %s" % (declared - allowed))
        # Và phải phủ đủ: 4 field công thức + 3 synthetic + 7 row literal
        # (2026-11-20: thêm `total_thick_mm` — tên chuẩn trùng field nguồn — và
        # `max_area_m2`; `glass_thick` giữ làm alias cũ cho rule đã viết).
        self.assertEqual(declared, {
            "width", "height", "qty",                 # FORMULA_FIELDS
            "unit_qty", "total_qty", "line_total",    # ENGINE_SYNTHETIC_FIELDS
            "unit_price", "weight_per_unit",
            "total_thick_mm", "glass_thick", "glass_type", "max_area_m2",
            "calc_pattern", "scrap_pct",
        })
        self.assertNotIn("show_condition", declared)

    def test_cross_row_cau_hinh(self):
        row = self.patch.CROSS_ROW[0]
        self.assertEqual(row["table_field"], "items")
        self.assertEqual(row["id_field"], "slug")
        self.assertEqual(row["label_field"], "line_name")
        self.assertEqual(row["include_index_form"], 1)
        self.assertEqual(row["enabled"], 1)
        self.assertIsInstance(row["fields"], str)

    def test_khong_co_rule_bi_cam(self):
        """⛔ cost_bucket (B5), row_literal trần (không có ở B4), cost_template_line (B6)."""
        kinds = {row[1] for row in self.patch.RULES}
        for banned in ("cost_bucket", "row_literal", "cost_template_line"):
            self.assertNotIn(banned, kinds,
                             "Profile B4 không được gợi ý %s" % banned)


class TestExecute(unittest.TestCase):
    """`execute()` phải idempotent và chịu được môi trường thiếu."""

    def _run(self, state=None):
        ctx = _Stubbed(state)
        with ctx:
            module = ctx.load(
                "alumglass.patches.v28_14.seed_bom_profile", _PATCH_REL)
            module.execute()
        return module, ctx.state

    def test_execute_idempotent_hai_lan(self):
        state = _default_state()
        state["records"][BOM_SET].append(
            {"name": "BOM-003", "variable_profile": "P_ADMIN"})

        module, state = self._run(state)
        self.assertEqual(len(state["inserts"]), 1)
        self.assertEqual(state["profiles"], {module.PROFILE_CODE})
        self.assertEqual(len(state["set_value_calls"]), 2,
                         "Chỉ gán 2 bản ghi đang trống")
        assigned_names = {c["name"] for c in state["set_value_calls"]}
        self.assertEqual(assigned_names, {"BOM-001", "BOM-002"})
        for call in state["set_value_calls"]:
            self.assertEqual(call["value"], module.PROFILE_CODE)
            self.assertFalse(call["update_modified"],
                             "⛔ không được làm modified của chứng từ nhảy")

        # Lần 2: không tạo thêm profile, không ghi lại bản ghi đã gán.
        module2, state2 = self._run(state)
        self.assertEqual(len(state2["inserts"]), 1)
        self.assertEqual(len(state2["set_value_calls"]), 2)

    def test_insert_bat_ignore_permissions(self):
        state = _default_state()
        ctx = _Stubbed(state)
        with ctx:
            module = ctx.load(
                "alumglass.patches.v28_14.seed_bom_profile", _PATCH_REL)
            spy = {}

            class _SpyDoc(object):
                def __init__(self, values):
                    self.values = values
                    self.flags = types.SimpleNamespace()

                def insert(self):
                    spy["ignore_permissions"] = getattr(
                        self.flags, "ignore_permissions", None)

            ctx.frappe.get_doc = lambda values=None, *a, **k: _SpyDoc(
                dict(values or {}))
            module._ensure_profile()

        self.assertIs(spy["ignore_permissions"], True)

    def test_khong_ghi_de_profile_admin_da_sua(self):
        state = _default_state(profiles={"P_BOM_DEFAULT"})
        module, state = self._run(state)
        self.assertEqual(state["inserts"], [],
                         "⛔ không được tạo lại/ghi đè profile đã có")
        self.assertEqual(len(state["set_value_calls"]), 2,
                         "Vẫn phải chạy bước gán khi profile đã tồn tại")

    def test_bo_qua_gan_khi_chua_co_cot(self):
        state = _default_state(columns={})
        _module, state = self._run(state)
        self.assertEqual(len(state["inserts"]), 1,
                         "Profile vẫn phải được tạo")
        self.assertEqual(state["set_value_calls"], [],
                         "Chưa có cột ⇒ bỏ qua bước gán, không nổ")

    def test_throw_khi_thieu_doctype_profile(self):
        state = _default_state(doctypes=set())
        with self.assertRaises(RuntimeError) as ctx:
            self._run(state)
        self.assertIn("post_model_sync", str(ctx.exception))
        self.assertEqual(state["inserts"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
