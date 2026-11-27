"""Test THUẦN cho B9/Đ2 — "Tạo sản phẩm từ mẫu" (`alumglass/product_clone.py`).

Sáu bảo đảm:
  (a) Bộ mới có mã mới, **số dòng con bằng nguồn** và nội dung dòng khớp từng ô
      (kể cả field không được mã nhắc tên — đúng tinh thần `copy_doc` theo meta).
  (b) `cloned_from` / `cloned_at` đúng ở cả 4 bộ, ⛔ đè lên bộ nguồn.
  (c) Mã trùng ⇒ ném lỗi tiếng Việt, ⛔ tạo gì (kể cả mã trùng ở bộ con).
  (d) `dry_run=True` ⇒ ⛔ insert (đếm = 0) nhưng kế hoạch đúng.
  (e) Snapshot rỗng / hỏng ⇒ lỗi rõ ràng, ⛔ đọc bộ đang sống; snapshot tốt thì
      dựng bộ mới từ đúng dữ liệu snapshot.
  (f) Site chưa migrate (thiếu cột cloned_from/cloned_at) ⇒ vẫn tạo được
      (đối chứng âm cho migration).

Chạy:
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=~/myfrappe/apps/formula_builder \
        python3 alumglass/tests/test_product_clone.py
"""
import copy
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

NOW = "2026-11-27 09:30:00.000000"
SOURCE_SET = "CDMQ-2C"

# ── Lược đồ giả: đủ field để kiểm copy theo meta ────────────────────────
SCHEMA = {
    "AL Bom Set": {
        "code": "set_code",
        "children": {"items": "AL Bom Item"},
        "fields": [
            "set_code", "set_name", "item_code", "product_type", "brand",
            "profile_system", "variable_set", "default_accessory_set",
            "version", "is_active", "variable_profile", "apply_scrap_pct",
            "formula_fieldnames", "items", "cloned_from", "cloned_at",
        ],
    },
    "AL Accessory Set": {
        "code": "set_code",
        "children": {"items": "AL Accessory Item"},
        "fields": [
            "set_code", "set_name", "item_code", "category", "cost_bucket",
            "product_type", "variable_set", "is_active", "variable_profile",
            "items", "cloned_from", "cloned_at",
        ],
    },
    "AL Cost Template": {
        "code": "template_code",
        "children": {"items": "AL Cost Template Item"},
        "fields": [
            "template_code", "template_name", "product_type", "is_active",
            "variable_profile", "items", "cloned_from", "cloned_at",
        ],
    },
    "AL Variable Set": {
        "code": "set_code",
        "children": {"items": "AL Variable Set Item"},
        "fields": [
            "set_code", "set_name", "product_type", "is_active", "items",
            "cloned_from", "cloned_at",
        ],
    },
    "AL Bom Item": {
        "code": None,
        "children": {},
        "fields": [
            "slug", "line_name", "category", "width", "height", "qty",
            "note", "supplier_location", "default_color", "calc_pattern",
            "item_code", "cut_angle",
        ],
    },
    "AL Accessory Item": {
        "code": None,
        "children": {},
        "fields": ["slug", "line_name", "qty", "note"],
    },
    "AL Cost Template Item": {
        "code": None,
        "children": {},
        "fields": ["line_code", "calc_formula"],
    },
    "AL Variable Set Item": {
        "code": None,
        "children": {},
        "fields": ["variable_name", "default_value"],
    },
    "AL BOM": {
        "code": "bom_code",
        "children": {},
        "fields": ["bom_code", "bom_name", "bom_set", "default_cost_template"],
    },
    "AL BOM Version": {
        "code": None,
        "children": {},
        "fields": ["bom", "version_name", "bom_set_snapshot"],
    },
}

CLONE_DOCTYPES = ("AL Bom Set", "AL Accessory Set", "AL Cost Template",
                  "AL Variable Set")


# ══════════════════════════════════════════════════════════════════════
# Frappe stub (chỉ chạy standalone)
# ══════════════════════════════════════════════════════════════════════
class FakeDoc:
    """Document giả: thuộc tính tự do + bảng con là list."""

    def __init__(self, doctype, data=None):
        object.__setattr__(self, "_doctype", doctype)
        for key, value in (data or {}).items():
            setattr(self, key, value)
        if "name" not in (data or {}):
            self.name = None
        for table in SCHEMA[doctype]["children"]:
            if not isinstance(getattr(self, table, None), list):
                setattr(self, table, [])

    @property
    def doctype(self):
        return self._doctype

    def get(self, field, default=None):
        return getattr(self, field, default)

    def set(self, field, value=None):
        if isinstance(field, dict):
            for key, val in field.items():
                setattr(self, key, val)
        else:
            setattr(self, field, value)

    def append(self, table, row):
        if isinstance(row, dict):
            row = FakeDoc(SCHEMA[self.doctype]["children"][table], row)
        getattr(self, table).append(row)
        return row

    def insert(self):
        frappe.db.insert(self)


def _row_data(row):
    """Dict dữ liệu của 1 dòng (bỏ thuộc tính nội bộ `_doctype`)."""
    return {key: value for key, value in row.__dict__.items()
            if key != "_doctype"}


class FakeDB:
    """Kho dữ liệu trong bộ nhớ + đếm insert."""

    def __init__(self):
        self.records = {doctype: {} for doctype in SCHEMA}
        self.columns = {doctype: {"cloned_from", "cloned_at"}
                        for doctype in CLONE_DOCTYPES}
        self.inserts = []

    def exists(self, doctype, name=None):
        return name in self.records.get(doctype, {})

    def has_column(self, doctype, column):
        return column in self.columns.get(doctype, set())

    def insert(self, doc):
        code_field = SCHEMA[doc.doctype]["code"]
        name = getattr(doc, code_field, None)
        if not name:
            raise RuntimeError("autoname rỗng cho %s" % doc.doctype)
        if name in self.records[doc.doctype]:
            raise RuntimeError("trùng tên %s %s" % (doc.doctype, name))
        doc.name = name
        self.records[doc.doctype][name] = doc
        self.inserts.append((doc.doctype, name))


class _Meta:
    def __init__(self, doctype):
        self._fields = [{"fieldname": field}
                        for field in SCHEMA[doctype]["fields"]]

    def get(self, key, default=None):
        if key == "fields":
            return self._fields
        return default


frappe = types.ModuleType("frappe")
frappe.__path__ = []


class ValidationError(Exception):
    pass


frappe.ValidationError = ValidationError
frappe.PermissionError = type("PermissionError", (Exception,), {})
frappe._ = lambda text, *args, **kwargs: text
frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe.utils = types.SimpleNamespace(now=lambda: NOW)
frappe.get_traceback = lambda: ""
frappe.logs = []
frappe.denied = set()
frappe.reads = []


def _throw(message=None, exc=None, title=None):
    raise ValidationError(message)


def _get_doc(doctype_or_dict, name=None):
    if isinstance(doctype_or_dict, dict):
        data = dict(doctype_or_dict)
        doctype = data.pop("doctype")
        return FakeDoc(doctype, data)
    frappe.reads.append(doctype_or_dict)
    record = frappe.db.records.get(doctype_or_dict, {}).get(name)
    if record is None:
        raise ValidationError("Không tìm thấy %s %s"
                              % (doctype_or_dict, name))
    return copy.deepcopy(record)


def _copy_doc(doc):
    """Bản giả của `frappe.copy_doc` — copy TOÀN BỘ theo meta, bỏ name/chứng từ."""
    new = copy.deepcopy(doc)
    new.name = None
    new.docstatus = 0
    for field in ("creation", "modified", "modified_by", "owner"):
        if hasattr(new, field):
            setattr(new, field, None)
    return new


def _new_doc(doctype):
    return FakeDoc(doctype)


def _get_meta(doctype):
    return _Meta(doctype)


def _get_all(doctype, filters=None, fields=None, limit_page_length=None,
             **kwargs):
    rows = []
    for record in frappe.db.records.get(doctype, {}).values():
        match = True
        for key, value in (filters or {}).items():
            if record.get(key) != value:
                match = False
                break
        if not match:
            continue
        if fields:
            rows.append({field: record.get(field) for field in fields})
        else:
            rows.append(_row_data(record))
    return rows


def _has_permission(doctype, ptype="read", *args, **kwargs):
    return (doctype, ptype) not in frappe.denied


def _log_error(message, title=None):
    frappe.logs.append((message, title))


frappe.throw = _throw
frappe.get_doc = _get_doc
frappe.copy_doc = _copy_doc
frappe.new_doc = _new_doc
frappe.get_meta = _get_meta
frappe.get_all = _get_all
frappe.has_permission = _has_permission
frappe.log_error = _log_error
frappe.db = FakeDB()
sys.modules["frappe"] = frappe

from alumglass import product_clone as pc

# ══════════════════════════════════════════════════════════════════════
# Dữ liệu mẫu
# ══════════════════════════════════════════════════════════════════════
SOURCE_ROWS = [
    {"slug": "khung_tren", "line_name": "Khung trên", "width": "1000",
     "height": "", "qty": "2", "note": "dòng 1",
     "supplier_location": "HCM", "default_color": "MAU-XANH",
     "cut_angle": "45"},
    {"slug": "khung_duoi", "line_name": "Khung dưới", "width": "1000",
     "qty": "2", "note": "dòng 2", "cut_angle": "45"},
    {"slug": "kinh", "line_name": "Kính", "width": "900", "height": "2000",
     "qty": "1", "note": "dòng 3"},
    {"slug": "ban_le", "line_name": "Bản lề", "width": "", "qty": "4",
     "note": "dòng 4"},
]
SNAPSHOT_ROWS = [
    {"slug": "khung_tren", "line_name": "Khung trên", "width": "1100",
     "qty": "2", "note": "snapshot 1", "field_da_go": "rác"},
    {"slug": "kinh", "line_name": "Kính", "width": "950", "height": "2100",
     "qty": "1", "note": "snapshot 2"},
]


def _stored(doctype, name, data, rows_field="items", rows=None):
    doc = FakeDoc(doctype, data)
    if rows is not None:
        setattr(doc, rows_field,
                [FakeDoc(SCHEMA[doctype]["children"][rows_field], row)
                 for row in rows])
    doc.name = name
    frappe.db.records[doctype][name] = doc
    return doc


def _seed():
    frappe.db = FakeDB()
    frappe.logs = []
    frappe.denied = set()
    frappe.reads = []
    _stored("AL Bom Set", SOURCE_SET, {
        "set_code": SOURCE_SET, "set_name": "Cửa đi 2 cánh",
        "item_code": "SP-CD-2C", "product_type": "PT-CUA-DI",
        "brand": "ALU", "profile_system": "ALUMIL_M9560",
        "variable_set": "VS-1", "default_accessory_set": "ACC-1",
        "version": "v9", "is_active": 1, "apply_scrap_pct": 1,
        "cloned_from": None, "cloned_at": None,
    }, rows=SOURCE_ROWS)
    _stored("AL Accessory Set", "ACC-1", {
        "set_code": "ACC-1", "set_name": "Phụ kiện chuẩn",
        "variable_set": "VS-1", "is_active": 1,
    }, rows=[
        {"slug": "tay_nam", "line_name": "Tay nắm", "qty": "1"},
        {"slug": "khoa", "line_name": "Khoá", "qty": "1"},
        {"slug": "ban_le", "line_name": "Bản lề", "qty": "3"},
    ])
    _stored("AL Variable Set", "VS-1", {
        "set_code": "VS-1", "set_name": "Biến chuẩn", "is_active": 1,
    }, rows=[
        {"variable_name": "W", "default_value": "1000"},
        {"variable_name": "H", "default_value": "2000"},
    ])
    _stored("AL Cost Template", "CT-1", {
        "template_code": "CT-1", "template_name": "Bộ giá chuẩn",
        "is_active": 1,
    }, rows=[
        {"line_code": "TONG_VL", "calc_formula": "a + b"},
        {"line_code": "GIA_VAT", "calc_formula": "a * 1.1"},
        {"line_code": "CP_NHANCONG", "calc_formula": "a * 0.2"},
    ])
    _stored("AL BOM", "BOM-1", {
        "bom_code": "BOM-1", "bom_set": SOURCE_SET,
        "default_cost_template": "CT-1",
    })
    _stored("AL BOM Version", "V-SNAP", {
        "version_name": "V-SNAP", "bom_set": "BOM-1",
        "bom_set_snapshot": json.dumps({
            "set_code": SOURCE_SET,
            "set_name": "Cửa đi 2 cánh (bản chốt)",
            "product_type": "PT-CUA-DI",
            "profile_system": "ALUMIL_M9560",
            "items": SNAPSHOT_ROWS,
        }),
    })
    _stored("AL BOM Version", "V-EMPTY", {
        "version_name": "V-EMPTY", "bom_set": "BOM-1",
        "bom_set_snapshot": "",
    })
    _stored("AL BOM Version", "V-BROKEN", {
        "version_name": "V-BROKEN", "bom_set": "BOM-1",
        "bom_set_snapshot": "{không phải json",
    })
    _stored("AL BOM Version", "V-NOROWS", {
        "version_name": "V-NOROWS", "bom_set": "BOM-1",
        "bom_set_snapshot": json.dumps({"set_code": SOURCE_SET, "items": []}),
    })


def _record(doctype, name):
    return frappe.db.records[doctype][name]


def _codes(result):
    return [(row["doctype"], row["code"]) for row in result["created"]]


class CloneTestBase(unittest.TestCase):
    def setUp(self):
        _seed()


# ══════════════════════════════════════════════════════════════════════
# (a) Tạo bộ mới — mã mới, đủ dòng, nội dung khớp, độc lập với nguồn
# ══════════════════════════════════════════════════════════════════════
class TestCloneProduct(CloneTestBase):
    def test_tao_du_bon_bo_voi_ma_moi(self):
        result = pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")

        self.assertTrue(result["ok"])
        self.assertFalse(result["dry_run"])
        self.assertEqual(_codes(result), [
            ("AL Bom Set", "CDMQ-MOI"),
            ("AL Variable Set", "CDMQ-MOI-VS"),
            ("AL Accessory Set", "CDMQ-MOI-ACC"),
            ("AL Cost Template", "CDMQ-MOI-CT"),
        ])
        self.assertEqual([row["rows"] for row in result["created"]],
                         [4, 2, 3, 3])
        self.assertEqual(result["source"]["set_code"], SOURCE_SET)

    def test_so_dong_con_bang_nguon_va_noi_dung_khop(self):
        pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")

        new_set = _record("AL Bom Set", "CDMQ-MOI")
        source_set = _record("AL Bom Set", SOURCE_SET)
        self.assertEqual(len(new_set.items), len(source_set.items))

        for new_row, old_row in zip(new_set.items, source_set.items, strict=False):
            self.assertEqual(_row_data(new_row), _row_data(old_row))
        # Field KHÔNG được mã nhắc tên vẫn đi theo (copy_doc theo meta):
        self.assertEqual(new_set.version, "v9")
        self.assertEqual(new_set.apply_scrap_pct, 1)
        self.assertEqual(new_set.brand, "ALU")
        self.assertEqual(new_set.items[0].supplier_location, "HCM")

    def test_bo_moi_doc_lap_voi_bo_nguon(self):
        pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")

        new_set = _record("AL Bom Set", "CDMQ-MOI")
        source_set = _record("AL Bom Set", SOURCE_SET)
        # Trỏ sang bộ con MỚI, không dùng chung bộ của bộ mẫu.
        self.assertEqual(new_set.default_accessory_set, "CDMQ-MOI-ACC")
        self.assertEqual(new_set.variable_set, "CDMQ-MOI-VS")
        # Bộ phụ kiện mới cũng phải dùng bộ biến mới, ⛔ trỏ về bộ biến của mẫu.
        self.assertEqual(_record("AL Accessory Set", "CDMQ-MOI-ACC")
                         .variable_set, "CDMQ-MOI-VS")
        self.assertEqual(source_set.default_accessory_set, "ACC-1")
        self.assertEqual(source_set.variable_set, "VS-1")

        # Sửa bộ mới ⇒ bộ nguồn không đổi.
        new_set.items[0].width = "9999"
        new_set.set_name = "Đã sửa"
        self.assertEqual(source_set.items[0].width, "1000")
        self.assertEqual(source_set.set_name, "Cửa đi 2 cánh")

    def test_tuy_chon_ma_rieng_va_json_string(self):
        result = pc.clone_product(
            SOURCE_SET, "CDMQ-OPT",
            options=json.dumps({
                "accessory_set": "ACC-RIENG",
                "variable_set": "VS-RIENG",
                "cost_template": "CT-RIENG",
            }))
        self.assertEqual(_codes(result), [
            ("AL Bom Set", "CDMQ-OPT"),
            ("AL Variable Set", "VS-RIENG"),
            ("AL Accessory Set", "ACC-RIENG"),
            ("AL Cost Template", "CT-RIENG"),
        ])
        self.assertEqual(_record("AL Bom Set", "CDMQ-OPT")
                         .default_accessory_set, "ACC-RIENG")

    def test_tuy_chon_la_thi_canh_bao(self):
        result = pc.clone_product(SOURCE_SET, "CDMQ-MOI",
                                  options={"accsessory_set": "GO-NHAM"})
        self.assertTrue(result["ok"])
        self.assertTrue(any("accsessory_set" in warning
                            for warning in result["warnings"]))

    def test_nhieu_bo_gia_thi_danh_so(self):
        _stored("AL BOM", "BOM-2", {
            "bom_code": "BOM-2", "bom_set": SOURCE_SET,
            "default_cost_template": "CT-2",
        })
        _stored("AL Cost Template", "CT-2", {
            "template_code": "CT-2", "template_name": "Bộ giá 2",
        }, rows=[{"line_code": "TONG_VL", "calc_formula": "a"}])

        result = pc.clone_product(SOURCE_SET, "CDMQ-MOI")
        cost_codes = [code for doctype, code in _codes(result)
                      if doctype == "AL Cost Template"]
        self.assertEqual(cost_codes, ["CDMQ-MOI-CT", "CDMQ-MOI-CT2"])


# ══════════════════════════════════════════════════════════════════════
# (b) Nguồn gốc
# ══════════════════════════════════════════════════════════════════════
class TestProvenance(CloneTestBase):
    def test_ghi_dung_nguon_goc_ca_bon_bo(self):
        pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")

        # Nguồn gốc là MÃ BỘ GỐC người-đọc-được (⛔ "DocType:tên" — chuỗi này
        # hiện thẳng trên form cho người dùng).
        expected = {
            "AL Bom Set": ("CDMQ-MOI", SOURCE_SET),
            "AL Accessory Set": ("CDMQ-MOI-ACC", "ACC-1"),
            "AL Variable Set": ("CDMQ-MOI-VS", "VS-1"),
            "AL Cost Template": ("CDMQ-MOI-CT", "CT-1"),
        }
        for doctype, (name, provenance) in expected.items():
            doc = _record(doctype, name)
            self.assertEqual(doc.cloned_from, provenance, doctype)
            self.assertEqual(doc.cloned_at, NOW, doctype)

    def test_khong_de_len_bo_nguon(self):
        pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")

        source_set = _record("AL Bom Set", SOURCE_SET)
        self.assertIsNone(source_set.cloned_from)
        self.assertIsNone(source_set.cloned_at)
        self.assertIsNone(getattr(
            _record("AL Accessory Set", "ACC-1"), "cloned_from", None))
        self.assertIsNone(getattr(
            _record("AL Variable Set", "VS-1"), "cloned_from", None))
        self.assertIsNone(getattr(
            _record("AL Cost Template", "CT-1"), "cloned_from", None))


# ══════════════════════════════════════════════════════════════════════
# (c) Mã trùng ⇒ dừng, ⛔ tạo gì
# ══════════════════════════════════════════════════════════════════════
class TestDuplicateCodes(CloneTestBase):
    def test_ma_bo_bom_trung(self):
        _stored("AL Bom Set", "CDMQ-MOI", {
            "set_code": "CDMQ-MOI", "set_name": "Đã có",
        }, rows=[{"slug": "x"}])

        with self.assertRaises(ValidationError) as ctx:
            pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Trùng")
        message = str(ctx.exception)
        self.assertIn("Mã bộ BOM", message)
        self.assertIn("đã có. Chọn mã khác.", message)
        self.assertEqual(frappe.db.inserts, [])

    def test_ma_bo_con_trung_van_dung_truoc_khi_tao(self):
        _stored("AL Variable Set", "CDMQ-MOI-VS", {
            "set_code": "CDMQ-MOI-VS", "set_name": "Đã có",
        }, rows=[{"variable_name": "W"}])

        with self.assertRaises(ValidationError) as ctx:
            pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Trùng bộ biến")
        self.assertIn("Mã bộ biến", str(ctx.exception))
        # ⛔ tạo nửa vời: chưa có bộ phụ kiện nào được insert.
        self.assertEqual(frappe.db.inserts, [])


# ══════════════════════════════════════════════════════════════════════
# (d) dry_run ⇒ ⛔ insert
# ══════════════════════════════════════════════════════════════════════
class TestDryRun(CloneTestBase):
    def test_dry_run_khong_insert(self):
        result = pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Xem trước",
                                  dry_run=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(frappe.db.inserts, [])
        self.assertEqual(_codes(result), [
            ("AL Bom Set", "CDMQ-MOI"),
            ("AL Variable Set", "CDMQ-MOI-VS"),
            ("AL Accessory Set", "CDMQ-MOI-ACC"),
            ("AL Cost Template", "CDMQ-MOI-CT"),
        ])
        self.assertEqual([row["rows"] for row in result["created"]],
                         [4, 2, 3, 3])
        self.assertNotIn("CDMQ-MOI", frappe.db.records["AL Bom Set"])

    def test_dry_run_van_bao_ma_trung(self):
        _stored("AL Bom Set", "CDMQ-MOI", {
            "set_code": "CDMQ-MOI", "set_name": "Đã có",
        }, rows=[{"slug": "x"}])
        with self.assertRaises(ValidationError):
            pc.clone_product(SOURCE_SET, "CDMQ-MOI", dry_run=True)
        self.assertEqual(frappe.db.inserts, [])


# ══════════════════════════════════════════════════════════════════════
# (e) Snapshot của AL BOM Version
# ══════════════════════════════════════════════════════════════════════
class TestCloneFromVersion(CloneTestBase):
    def test_snapshot_rong_thi_loi_ro_rang(self):
        with self.assertRaises(ValidationError) as ctx:
            pc.clone_from_version("V-EMPTY", "CDMQ-SNAP")
        message = str(ctx.exception)
        self.assertIn("bom_set_snapshot trống", message)
        self.assertIn("không tạo được", message)
        self.assertEqual(frappe.db.inserts, [])

    def test_snapshot_hong_thi_loi_ro_rang(self):
        with self.assertRaises(ValidationError) as ctx:
            pc.clone_from_version("V-BROKEN", "CDMQ-SNAP")
        self.assertIn("không đọc được", str(ctx.exception))
        self.assertEqual(frappe.db.inserts, [])

    def test_snapshot_khong_dong_dong_nao(self):
        with self.assertRaises(ValidationError) as ctx:
            pc.clone_from_version("V-NOROWS", "CDMQ-SNAP")
        self.assertIn("không có dòng BOM nào", str(ctx.exception))
        self.assertEqual(frappe.db.inserts, [])

    def test_snapshot_rong_khong_doc_bo_dang_song(self):
        for version in ("V-EMPTY", "V-BROKEN", "V-NOROWS"):
            frappe.reads = []
            with self.assertRaises(ValidationError):
                pc.clone_from_version(version, "CDMQ-SNAP")
            self.assertEqual(frappe.reads, ["AL BOM Version"],
                             "%s: ⛔ đọc bộ đang sống" % version)

    def test_tao_tu_snapshot_dung_du_lieu_snapshot(self):
        result = pc.clone_from_version(
            "V-SNAP", "CDMQ-SNAP", "Sản phẩm từ phiên bản")

        self.assertTrue(result["ok"])
        self.assertEqual(result["created"][0]["rows"], len(SNAPSHOT_ROWS))
        new_set = _record("AL Bom Set", "CDMQ-SNAP")
        self.assertEqual(new_set.set_name, "Sản phẩm từ phiên bản")
        self.assertEqual(new_set.product_type, "PT-CUA-DI")
        self.assertEqual(new_set.profile_system, "ALUMIL_M9560")
        self.assertFalse(new_set.get("item_code"))
        # Dữ liệu dòng lấy từ SNAPSHOT (width 1100), ⛔ bộ đang sống (1000).
        self.assertEqual(len(new_set.items), len(SNAPSHOT_ROWS))
        self.assertEqual(new_set.items[0].width, "1100")
        self.assertEqual(new_set.items[0].note, "snapshot 1")
        # Field không còn trên DocType bị bỏ + có cảnh báo.
        self.assertFalse(hasattr(new_set.items[0], "field_da_go"))
        self.assertTrue(any("Bỏ qua" in warning and "snapshot" in warning
                            for warning in result["warnings"]))

    def test_snapshot_khong_doc_bo_dang_song(self):
        frappe.reads = []
        pc.clone_from_version("V-SNAP", "CDMQ-SNAP")
        self.assertEqual(frappe.reads, ["AL BOM Version"])

    def test_snapshot_ghi_nguon_goc_la_version(self):
        pc.clone_from_version("V-SNAP", "CDMQ-SNAP")
        new_set = _record("AL Bom Set", "CDMQ-SNAP")
        self.assertEqual(new_set.cloned_from, "V-SNAP")
        self.assertEqual(new_set.cloned_at, NOW)

    def test_snapshot_trung_ma_thi_dung(self):
        _stored("AL Bom Set", "CDMQ-SNAP", {
            "set_code": "CDMQ-SNAP", "set_name": "Đã có",
        }, rows=[{"slug": "x"}])
        with self.assertRaises(ValidationError) as ctx:
            pc.clone_from_version("V-SNAP", "CDMQ-SNAP")
        self.assertIn("đã có. Chọn mã khác.", str(ctx.exception))
        self.assertEqual(frappe.db.inserts, [])


# ══════════════════════════════════════════════════════════════════════
# (f) Site chưa migrate — thiếu cột nguồn gốc vẫn tạo được
# ══════════════════════════════════════════════════════════════════════
class TestMissingProvenanceColumns(CloneTestBase):
    def test_thieu_cot_van_tao_duoc_va_canh_bao(self):
        frappe.db.columns = {}

        result = pc.clone_product(SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")

        self.assertTrue(result["ok"])
        self.assertEqual(len(frappe.db.inserts), 4)
        new_set = _record("AL Bom Set", "CDMQ-MOI")
        self.assertIsNone(getattr(new_set, "cloned_from", None))
        self.assertIsNone(getattr(new_set, "cloned_at", None))
        self.assertEqual(len(new_set.items), 4)
        self.assertTrue(any("dấu vết" in warning
                            for warning in result["warnings"]))

    def test_thieu_cot_khi_tao_tu_snapshot(self):
        frappe.db.columns = {}
        result = pc.clone_from_version("V-SNAP", "CDMQ-SNAP")
        self.assertTrue(result["ok"])
        new_set = _record("AL Bom Set", "CDMQ-SNAP")
        self.assertIsNone(getattr(new_set, "cloned_from", None))
        self.assertTrue(any("dấu vết" in warning
                            for warning in result["warnings"]))


# ══════════════════════════════════════════════════════════════════════
# API whitelisted — quyền + trả lỗi tiếng Việt (⛔ traceback)
# ══════════════════════════════════════════════════════════════════════
def _load_api():
    package = types.ModuleType("alumglass.api")
    package.__path__ = [os.path.join(_APP_ROOT, "alumglass", "api")]
    sys.modules["alumglass.api"] = package
    name = "alumglass.api.product_clone"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_APP_ROOT, "alumglass", "api", "product_clone.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestProductCloneApi(CloneTestBase):
    @classmethod
    def setUpClass(cls):
        cls.api = _load_api()

    def test_preview_tra_ke_hoach_va_khong_insert(self):
        plan = self.api.preview_product_clone(SOURCE_SET)
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["suggested_new_code"], SOURCE_SET + "-MOI")
        self.assertEqual(frappe.db.inserts, [])

    def test_preview_khong_co_quyen_doc(self):
        frappe.denied = {("AL Bom Set", "read")}
        result = self.api.preview_product_clone(SOURCE_SET)
        self.assertFalse(result["ok"])
        self.assertIn("quyền", result["error"])
        self.assertEqual(frappe.db.inserts, [])

    def test_create_khong_co_quyen_thi_khong_tao(self):
        frappe.denied = {("AL Bom Set", "create")}
        result = self.api.create_product_clone(
            SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")
        self.assertFalse(result["ok"])
        self.assertIn("không có quyền tạo bộ BOM", result["error"])
        self.assertEqual(frappe.db.inserts, [])

    def test_create_thanh_cong_tra_redirect(self):
        result = self.api.create_product_clone(
            SOURCE_SET, "CDMQ-MOI", "Cửa đi mới")
        self.assertTrue(result["ok"])
        self.assertEqual(result["redirect"],
                         {"doctype": "AL Bom Set", "name": "CDMQ-MOI"})

    def test_ma_trong_tu_dat_ma_chua_trung(self):
        """Để trống mã ⇒ máy tự đặt; lần hai ⛔ chết vì mã cũ (lỗi cũ)."""
        first = self.api.create_product_clone(SOURCE_SET, "", "Bản 1")
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["created"][0]["code"], SOURCE_SET + "-MOI")

        second = self.api.create_product_clone(SOURCE_SET, "", "Bản 2")
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["created"][0]["code"], SOURCE_SET + "-MOI2")

    def test_loi_dup_entry_khong_hien_ra_man_hinh(self):
        """Frappe bọc lỗi DB thành ValidationError ⇒ vẫn phải lọc."""
        original = self.api.clone_product

        def _boom(*args, **kwargs):
            raise ValidationError(
                "Duplicate entry 'CDMQ-MOI-VS' for key 'PRIMARY'")

        self.api.clone_product = _boom
        self.addCleanup(setattr, self.api, "clone_product", original)

        result = self.api.create_product_clone(SOURCE_SET, "CDMQ-MOI", "X")
        self.assertFalse(result["ok"])
        self.assertNotIn("Duplicate entry", result["error"])
        self.assertNotIn("PRIMARY", result["error"])
        self.assertTrue(frappe.logs)

    def test_loi_nghiep_vu_tra_cau_tieng_viet_khong_traceback(self):
        _stored("AL Bom Set", "CDMQ-MOI", {
            "set_code": "CDMQ-MOI", "set_name": "Đã có",
        }, rows=[{"slug": "x"}])
        result = self.api.create_product_clone(
            SOURCE_SET, "CDMQ-MOI", "Trùng")
        self.assertFalse(result["ok"])
        self.assertIn("đã có. Chọn mã khác.", result["error"])
        self.assertNotIn("Traceback", result["error"])
        # Lỗi nghiệp vụ (ValidationError) không đẩy rác vào Error Log.
        self.assertEqual(frappe.logs, [])

    def test_loi_la_khong_lo_chi_tiet_ky_thuat(self):
        original = self.api.clone_product

        def _boom(*args, **kwargs):
            raise RuntimeError(
                "pymysql.err.OperationalError: 1054 Unknown column")

        self.api.clone_product = _boom
        self.addCleanup(setattr, self.api, "clone_product", original)

        result = self.api.create_product_clone(SOURCE_SET, "CDMQ-MOI", "X")
        self.assertFalse(result["ok"])
        self.assertNotIn("pymysql", result["error"])
        self.assertNotIn("Unknown column", result["error"])
        self.assertIn("thử lại", result["error"].lower())
        # Chi tiết kỹ thuật đi Error Log, ⛔ ra màn hình.
        self.assertTrue(frappe.logs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
