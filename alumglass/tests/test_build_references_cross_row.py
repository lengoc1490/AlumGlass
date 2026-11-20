# -*- coding: utf-8 -*-
"""Test THUẦN: `build_references` chỉ sinh field khai trong cross_row.fields.

Bối cảnh bug (2026-11-20): server `build_references` lọc ĐÚNG theo
`AL Variable Profile.cross_row.fields` (mặc định profile `P_BOM_DEFAULT` chỉ
12 field), nhưng client `_ContextBuilder.build` (formula_builder) tự sinh
`siblingItems` = MỌI field meta của MỌI bảng con ⇒ autocomplete vẫn hiện
`line_name`, `price_type`, `fixed_price`... Test này CHỐT HỢP ĐỒNG phía server
để bản vá client (al_formula_refs.js) không lọc bừa:
  - mọi field trong references phải nằm trong CROSS_ROW_FIELDS của patch seed;
  - có ĐỦ 12 field × 2 dạng (slug + index) cho mỗi dòng;
  - KHÔNG sinh field ngoài danh sách (đặc biệt `line_name`/`price_type`/
    `fixed_price` — field thật của AL Bom Item nhưng KHÔNG khai cross-row).

Không cần site: stub `frappe` + `alumglass.variable_sources.context`, nạp
adapter và patch seed từ CHÍNH MÃ NGUỒN (không chép tay danh sách field).

CÁCH CHẠY
---------
    cd ~/myfrappe/apps/alumglass
    python3 alumglass/tests/test_build_references_cross_row.py
Hoặc qua bench:
    bench --site <site> run-tests --app alumglass \
        --module alumglass.tests.test_build_references_cross_row
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

_PATCH_REL = "alumglass/patches/v28_14/seed_bom_profile.py"
_ADAPTERS_REL = "alumglass/variable_sources/adapters.py"

_TOUCHED_MODULES = (
    "frappe",
    "frappe.model",
    "frappe.model.document",
    "alumglass",
    "alumglass.variable_sources",
    "alumglass.variable_sources.registry",
    "alumglass.variable_sources.rules",
    "alumglass.variable_sources.context",
    "alumglass.variable_sources.adapters",
    "alumglass.patches",
    "alumglass.patches.v28_14",
    "alumglass.patches.v28_14.seed_bom_profile",
)

# Field THẬT trên AL Bom Item nhưng CỐ Ý không nằm trong cross_row.fields —
# nếu lọt vào references nghĩa là allowlist bị bỏ qua.
_FORBIDDEN_FIELDS = (
    "line_name", "price_type", "fixed_price", "slug", "item_code",
    "cost_bucket", "qty_formula", "item_condition_formula", "note",
)


def _load_source(module_name, rel_path):
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_APP_ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_frappe_stub():
    """Stub tối thiểu: `frappe.get_doc` cho patch seed, get_meta trả rỗng."""
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []

    class _FakeDoc(object):
        def __init__(self, values=None):
            self.values = dict(values or {})
            self.flags = types.SimpleNamespace()

        def insert(self):
            return self

    class _FakeMeta(object):
        def get(self, key, default=None):
            return [] if key == "fields" else default

        def get_field(self, fieldname):
            return None

        def get_table_fields(self):
            return []

    frappe.get_doc = lambda values=None, *a, **k: _FakeDoc(values)
    frappe.get_meta = lambda *a, **k: _FakeMeta()
    frappe.get_all = lambda *a, **k: []
    frappe.get_cached_doc = lambda *a, **k: None
    frappe.log_error = lambda *a, **k: None
    frappe.get_traceback = lambda: ""
    frappe.throw = lambda msg=None, *a, **k: (_ for _ in ()).throw(
        RuntimeError(msg))
    frappe.whitelist = lambda *a, **k: (lambda fn: fn)
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


def _build_context_stub():
    """Thay `variable_sources/context.py` — test không chạm DB."""
    ctx = types.ModuleType("alumglass.variable_sources.context")
    ctx.detect_slug_field = lambda child_doctype: "slug"
    ctx.get_field_label = lambda doctype, fieldname: fieldname or ""
    ctx.get_scalar_fieldnames = (
        lambda doctype: list(_BOM_ITEM_SCALAR_FIELDS)
        if doctype == "AL Bom Item" else [])
    return ctx


# Field vô hướng của `AL Bom Item` (rút gọn, đủ để chứng minh cross_row.fields
# RỖNG = "mọi field" — gồm cả line_name/price_type/fixed_price vốn KHÔNG nằm
# trong cross_row.fields mặc định của P_BOM_DEFAULT).
_BOM_ITEM_SCALAR_FIELDS = (
    "slug", "line_name", "item_code", "qty", "unit_qty", "unit_price",
    "line_total", "price_type", "fixed_price", "note", "calc_pattern",
    "glass_thick", "glass_type",
)


class _Stubbed(object):
    """Cài stub + nạp module, KHÔI PHỤC nguyên trạng khi thoát."""

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        self._saved = {n: sys.modules.get(n) for n in _TOUCHED_MODULES}
        frappe = _build_frappe_stub()
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = frappe.model
        sys.modules["frappe.model.document"] = frappe.model.document
        # Registry sổ đăng ký adapter là state toàn cục — chụp lại để trả về.
        from alumglass.variable_sources import registry
        self._registry_state = (
            dict(registry._ADAPTERS), list(registry._ADAPTER_SEQ))
        return self

    def __exit__(self, *exc):
        from alumglass.variable_sources import registry
        registry._ADAPTERS.clear()
        registry._ADAPTERS.update(self._registry_state[0])
        del registry._ADAPTER_SEQ[:]
        registry._ADAPTER_SEQ.extend(self._registry_state[1])
        for name, old in self._saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        return False


class FakeCtx(object):
    """Context tối thiểu đủ cho `build_references` (nhánh cross_row)."""

    doctype = "AL Bom Set"

    def __init__(self, rows):
        self._rows = list(rows)

    def get_doc(self):
        return self

    def get(self, key, default=None):
        return self._rows if key == "items" else default

    def get_child_rows(self, table_field=None):
        return self._rows if table_field == "items" else []

    def get_child_doctype(self, table_field):
        return "AL Bom Item" if table_field == "items" else None


BOM_ROWS = [
    {"slug": "kinh_canh", "line_name": "Kính cạnh", "glass_thick": 8,
     "glass_type": "Temper", "qty": 2, "unit_price": 250000,
     "line_total": 500000, "price_type": "fixed", "fixed_price": 1},
    {"slug": "kinh_tren", "line_name": "Kính trên", "glass_thick": 10,
     "glass_type": "Thường", "qty": 1, "unit_price": 300000,
     "line_total": 300000, "price_type": "fixed", "fixed_price": 2},
]


def _field_of_ref(name):
    """`items.<slug>.<field>` / `items[idx].<field>` → field."""
    tail = name.split(".", 1)[1] if "." in name else ""
    return tail.split(".", 1)[-1]


class TestBuildReferencesCrossRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stub = _Stubbed()
        cls._stub.__enter__()
        try:
            patch = _load_source(
                "alumglass.patches.v28_14.seed_bom_profile", _PATCH_REL)
            cls.patch = patch
            cls.profile = patch._build_profile_doc().values
            sys.modules["alumglass.variable_sources.context"] = _build_context_stub()
            cls.adapters = _load_source(
                "alumglass.variable_sources.adapters", _ADAPTERS_REL)
        except Exception:
            cls._stub.__exit__(None, None, None)
            raise

    @classmethod
    def tearDownClass(cls):
        cls._stub.__exit__(None, None, None)

    def setUp(self):
        self.refs = self.adapters.build_references(FakeCtx(BOM_ROWS), self.profile)
        self.names = [r["name"] for r in self.refs]

    # ── Hợp đồng chính ─────────────────────────────────────────────
    def test_chi_sinh_field_trong_cross_row_fields(self):
        allowed = set(self.patch.CROSS_ROW_FIELDS)
        seen = {_field_of_ref(n) for n in self.names}
        self.assertTrue(seen, "references rỗng — cấu hình cross_row không chạy")
        self.assertEqual(
            seen - allowed, set(),
            "reference sinh field NGOÀI cross_row.fields: %s" % (seen - allowed))

    def test_khong_co_field_cam(self):
        fields = {_field_of_ref(n) for n in self.names}
        leaked = fields & set(_FORBIDDEN_FIELDS)
        self.assertEqual(leaked, set(),
                         "field không khai cross-row bị gợi ý: %s" % leaked)

    def test_du_12_field_x_2_dang_cho_moi_dong(self):
        for row in BOM_ROWS:
            slug = row["slug"]
            for field in self.patch.CROSS_ROW_FIELDS:
                self.assertIn("items.%s.%s" % (slug, field), self.names)
                idx = BOM_ROWS.index(row)
                self.assertIn("items[%d].%s" % (idx, field), self.names)

    def test_dung_2_bang_khong_sinh_bang_khac(self):
        tables = set()
        for name in self.names:
            table = name.split(".", 1)[0].split("[", 1)[0]
            tables.add(table)
        self.assertEqual(tables, {"items"})

    def test_tong_so_reference(self):
        # 2 dòng × 12 field × 2 dạng
        expected = len(BOM_ROWS) * len(self.patch.CROSS_ROW_FIELDS) * 2
        self.assertEqual(len(self.refs), expected)

    # ── Ca đối chứng: cross_row.fields là nguồn quyết định ─────────
    def test_thu_hep_fields_thi_reference_thu_hep_theo(self):
        profile = dict(self.profile)
        profile["cross_row"] = [dict(
            self.patch.CROSS_ROW[0],
            fields=json.dumps(["glass_thick", "glass_type"]),
        )]
        refs = self.adapters.build_references(FakeCtx(BOM_ROWS), profile)
        fields = {_field_of_ref(r["name"]) for r in refs}
        self.assertEqual(fields, {"glass_thick", "glass_type"})
        self.assertEqual(len(refs), len(BOM_ROWS) * 2 * 2)

    def test_fields_rong_thi_sinh_rong_khong_hen_qua_muc(self):
        """`fields` rỗng = mọi field vô hướng (hành vi cũ) — ⛔ không được hẹp.

        Client lọc theo allowlist = đúng danh sách references server trả; nếu
        server trả rộng (fields rỗng) thì client phải giữ nguyên, không áp
        thêm danh sách cứng nào.
        """
        profile = dict(self.profile)
        profile["cross_row"] = [dict(self.patch.CROSS_ROW[0], fields="")]
        refs = self.adapters.build_references(FakeCtx(BOM_ROWS), profile)
        fields = {_field_of_ref(r["name"]) for r in refs}
        self.assertEqual(fields, set(_BOM_ITEM_SCALAR_FIELDS))
        # Các field KHÔNG khai trong cross_row.fields mặc định vẫn phải có mặt
        # khi fields rỗng (chứng minh "rộng", không bị hẹp).
        for name in ("line_name", "price_type", "fixed_price"):
            self.assertIn(name, fields)
        self.assertEqual(
            len(refs), len(BOM_ROWS) * len(_BOM_ITEM_SCALAR_FIELDS) * 2)

    def test_tat_cross_row_vao_exclude_all_thi_khong_goi_y(self):
        profile = dict(self.profile)
        profile["cross_row"] = []
        profile["default_action"] = "EXCLUDE_ALL"
        refs = self.adapters.build_references(FakeCtx(BOM_ROWS), profile)
        self.assertEqual(refs, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
