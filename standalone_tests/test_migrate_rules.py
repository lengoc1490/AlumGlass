# -*- coding: utf-8 -*-
"""CHẶNG 2A/2C — kiểm patch `migrate_rules_to_al_rule`.

BỐI CẢNH
────────
Patch chép dữ liệu 2 doctype cũ sang `AL Rule`:

    AL Calculation Rule  → result_type NUMBER (cột `result_value`)
    AL Dynamic Item Rule → result_type ITEM   (cột `result_item`)

`AL Dynamic Item Rule Version` ⇒ `AL Rule Version` (giữ `rule` = mã rule).

Bộ test chứng minh:
  (1) migrate ĐỦ 2 loại (CONSTANT / THRESHOLD / LOOKUP) + giữ mã / tên /
      rule_type / is_active / constant_value;
  (2) IDEMPOTENT: chạy 2 lần không nhân đôi;
  (3) trùng `rule_code` giữa 2 nguồn ⇒ THROW nêu danh sách mã, KHÔNG ghi gì;
  (4) cùng mã nhưng khác `result_type` ⇒ THROW nêu mã + 2 loại;
  (5) ⛔ xoá/đổi bản ghi 2 bảng cũ (đường cứu hộ);
  (6) patch KHÔNG tự `frappe.db.commit()`;
  (7) ĐỐI CHỨNG ÂM thật (đột biến rồi khôi phục) cho các phép kiểm dễ xanh
      giả: cổng trùng mã, tính idempotent, cờ `is_active`, và đường đọc SQL
      thô khi DocType record đã mất;
  (8) CHẶNG 2C:
      (a) đọc bằng SQL THÔ khi DocType record KHÔNG còn nhưng bảng còn dữ
          liệu (⛔ chết vì meta);
      (b) copy bản ghi version sang `AL Rule Version`, giữ `rule` = mã rule;
          bỏ qua version mồ côi (không có `AL Rule` cùng mã); idempotent;
      (c) `dry_run` có `version_rows` / `orphan_version_rows`, ⛔ đổi khoá cũ.

CÁCH CHẠY (không cần site):
    python3 standalone_tests/test_migrate_rules.py
"""

import os
import re
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ═══════════════════════════════════════════════════════════════════
# Stub `frappe` — chỉ đủ bề mặt patch dùng tới, ghi lại trạng thái để kiểm
# ═══════════════════════════════════════════════════════════════════
class FrappeThrow(Exception):
    """`frappe.throw` — câu lỗi người-đọc-được."""


class FakeDoc:
    def __init__(self, doctype, data=None):
        self.doctype = doctype
        self._data = dict(data or {})
        self.name = self._data.get("name") or self._data.get("rule_code")

    def get(self, key, default=None):
        if key == "name":
            return self._data.get("name", self.name)
        return self._data.get(key, default)

    def append(self, field, row):
        self._data.setdefault(field, []).append(row)

    def insert(self, ignore_permissions=False):
        if self.doctype == "AL Rule":
            # `autoname: field:rule_code`
            self.name = self._data.get("rule_code")
        elif self.doctype == "AL Rule Version":
            STORE.version_seq += 1
            self.name = "VER-%04d" % STORE.version_seq
        STORE.add(self)
        _register_inserted_child_rows(self)
        return self


#: Bảng con của `AL Rule` đích (nơi dòng migrate được ghi vào).
_TARGET_CHILD_TABLES = {
    "threshold_rows": "AL Rule Threshold Row",
    "lookup_rows": "AL Rule Lookup Row",
}

#: Bảng con của từng NGUỒN (dòng nguồn nằm ở đây, lọc theo parenttype).
_SOURCE_CHILD_TABLES = {
    "AL Calculation Rule": {
        "threshold_rows": "AL Rule Threshold Row",
        "lookup_rows": "AL Rule Lookup Row",
    },
    "AL Dynamic Item Rule": {
        "threshold_rows": "AL Dynamic Item Rule Threshold Row",
        "lookup_rows": "AL Dynamic Item Rule Lookup Row",
    },
}


def _register_inserted_child_rows(doc):
    """Đăng ký dòng con của bản ghi VỪA TẠO vào bảng con tương ứng."""
    for field, table in _TARGET_CHILD_TABLES.items():
        for index, row in enumerate(doc.get(field) or [], start=1):
            data = dict(row)
            data.update({
                "parent": doc.name,
                "parenttype": doc.doctype,
                "idx": index,
            })
            STORE.child_docs.setdefault(table, []).append(data)


class Store:
    def __init__(self):
        self.reset()

    def reset(self):
        self.docs = {}          # doctype -> [FakeDoc]
        self.child_docs = {}    # child doctype -> [dict có parent/parenttype/idx]
        self.commit_calls = 0
        self.version_seq = 0
        # Bảng CHƯA tồn tại (vd dry_run chạy trước migrate, hoặc doctype cũ
        # đã bị gỡ) — `FakeDB.table_exists` đọc tập này.
        self.missing_tables = set()
        # DocType RECORD đã bị xoá nhưng BẢNG vẫn còn: `get_all`/`get_doc`
        # (đường meta) phải chết, còn `db.sql` vẫn đọc được.
        self.missing_doctype_records = set()

    def add(self, doc):
        self.docs.setdefault(doc.doctype, []).append(doc)

    def rows(self, doctype):
        return self.docs.get(doctype, [])

    def seed_child_rows(self, table, parent, parenttype, rows):
        for index, row in enumerate(rows or [], start=1):
            data = dict(row)
            data.update({
                "parent": parent,
                "parenttype": parenttype,
                "idx": index,
            })
            self.child_docs.setdefault(table, []).append(data)

    def find(self, doctype, filters):
        for doc in self.rows(doctype):
            if isinstance(filters, dict):
                if all(doc.get(key) == value for key, value in filters.items()):
                    return doc
            elif doc.name == filters:
                return doc
        return None


STORE = Store()

_SELECT_RE = re.compile(
    r"^\s*select\s+(?P<cols>.+?)\s+from\s+`tab(?P<table>[^`]+)`"
    r"(?:\s+where\s+(?P<where>.+?))?"
    r"(?:\s+order\s+by\s+(?P<order>.+?))?\s*$",
    re.IGNORECASE | re.DOTALL)

_WHERE_PARENT_RE = re.compile(
    r"^`parent`\s*=\s*%s\s+and\s+`parenttype`\s*=\s*%s$", re.IGNORECASE)


def _row_value(row, column):
    if isinstance(row, dict):
        return row.get(column)
    return row.get(column)


class FakeDB:
    def exists(self, doctype, filters, *args, **kwargs):
        doc = STORE.find(doctype, filters)
        return doc.name if doc is not None else None

    def get_value(self, doctype, filters, field, *args, **kwargs):
        doc = STORE.find(doctype, filters)
        return None if doc is None else doc.get(field)

    def table_exists(self, doctype, *args, **kwargs):
        return doctype not in STORE.missing_tables

    def sql(self, query, values=None, as_dict=False, *args, **kwargs):
        """Mini-SQL đủ cho các câu patch phát ra (xem `_SELECT_RE`)."""
        match = _SELECT_RE.match(query)
        assert match, "stub SQL không hiểu câu: %r" % query
        table = match.group("table")
        columns = [
            column.strip().strip("`")
            for column in match.group("cols").split(",")
        ]

        if table in STORE.child_docs or table in (
                "AL Rule Threshold Row", "AL Rule Lookup Row",
                "AL Dynamic Item Rule Threshold Row",
                "AL Dynamic Item Rule Lookup Row"):
            source = list(STORE.child_docs.get(table, []))
        else:
            source = list(STORE.rows(table))

        where = (match.group("where") or "").strip()
        if where:
            where_match = _WHERE_PARENT_RE.match(where)
            assert where_match, "stub SQL chưa hỗ trợ WHERE: %r" % where
            parent, parenttype = tuple(values or ())
            source = [
                row for row in source
                if _row_value(row, "parent") == parent
                and _row_value(row, "parenttype") == parenttype
            ]

        if match.group("order"):
            order_field = match.group("order").strip().strip("`")
            source = sorted(
                source, key=lambda row: _row_value(row, order_field) or "")

        if as_dict:
            return [
                {column: _row_value(row, column) for column in columns}
                for row in source
            ]
        return [
            tuple(_row_value(row, column) for column in columns)
            for row in source
        ]

    def commit(self, *args, **kwargs):
        STORE.commit_calls += 1


class FakeFrappe:
    def __init__(self):
        self.db = FakeDB()

    def get_all(self, doctype, fields=None, pluck=None, order_by=None, limit=None,
                *args, **kwargs):
        _assert_doctype_record_alive(doctype)
        rows = STORE.rows(doctype)
        if pluck:
            return [row.get(pluck) for row in rows]
        return [{field: row.get(field) for field in (fields or [])} for row in rows]

    def get_doc(self, doctype, name=None):
        # Dạng `frappe.get_doc({...})` dùng để TẠO bản ghi mới.
        if isinstance(doctype, dict):
            data = dict(doctype)
            doc_type = data.pop("doctype")
            return FakeDoc(doc_type, data)
        _assert_doctype_record_alive(doctype)
        doc = STORE.find(doctype, name)
        if doc is None:
            raise FakeFrappe.DoesNotExistError("%s %s" % (doctype, name))
        return doc

    def throw(self, message, *args, **kwargs):
        raise FrappeThrow(message)

    class DoesNotExistError(Exception):
        pass


def _assert_doctype_record_alive(doctype):
    if doctype in STORE.missing_doctype_records:
        raise FakeFrappe.DoesNotExistError(
            "DocType %s không còn (chỉ bảng còn)" % doctype)


def _install_frappe_stub():
    # Module app import với stub cũ (nếu pytest chạy chung 1 tiến trình) phải
    # được bỏ đi, ⛔ để patch bind nhầm module `frappe` khác.
    for name in [n for n in list(sys.modules)
                 if n == "alumglass" or n.startswith("alumglass.")]:
        del sys.modules[name]

    fake = FakeFrappe()
    module = types.ModuleType("frappe")
    module.db = fake.db
    module.get_all = fake.get_all
    module.get_doc = fake.get_doc
    module.throw = fake.throw
    module.whitelist = lambda *a, **k: (a[0] if a else (lambda fn: fn))
    module.DoesNotExistError = FakeFrappe.DoesNotExistError
    sys.modules["frappe"] = module
    return module


FRAPPE = _install_frappe_stub()

import alumglass.patches.v1_0.migrate_rules_to_al_rule as patch_mod  # noqa: E402

NUMBER_SOURCE = "AL Calculation Rule"
ITEM_SOURCE = "AL Dynamic Item Rule"
VERSION_SOURCE = "AL Dynamic Item Rule Version"
VERSION_TARGET = "AL Rule Version"
TARGET = "AL Rule"


# ═══════════════════════════════════════════════════════════════════
# Dựng dữ liệu nguồn
# ═══════════════════════════════════════════════════════════════════
def _seed(doctype, rule_code, rule_type="THRESHOLD", threshold_rows=None,
          lookup_rows=None, is_active=1, constant_value=None, rule_name=None):
    doc = FakeDoc(doctype, {
        "rule_code": rule_code,
        "rule_name": ("Tên của " + rule_code) if rule_name is None else rule_name,
        "rule_type": rule_type,
        "is_active": is_active,
        "constant_value": constant_value,
        "threshold_rows": list(threshold_rows or []),
        "lookup_rows": list(lookup_rows or []),
    })
    STORE.add(doc)
    tables = _SOURCE_CHILD_TABLES[doctype]
    STORE.seed_child_rows(
        tables["threshold_rows"], rule_code, doctype, threshold_rows)
    STORE.seed_child_rows(
        tables["lookup_rows"], rule_code, doctype, lookup_rows)
    return doc


def _seed_number(rule_code="RULE-NUM", **kwargs):
    _seed(NUMBER_SOURCE, rule_code, **kwargs)


def _seed_item(rule_code="RULE-ITEM", **kwargs):
    _seed(ITEM_SOURCE, rule_code, **kwargs)


def _seed_version(rule_code, version_name="v1", valid_from="2026-01-01 00:00:00",
                  workflow_state="Published", snapshot='{"a": 1}'):
    STORE.add(FakeDoc(VERSION_SOURCE, {
        "rule": rule_code,
        "version_name": version_name,
        "valid_from": valid_from,
        "workflow_state": workflow_state,
        "rule_snapshot_json": snapshot,
    }))


def _targets():
    return {doc.get("rule_code"): doc for doc in STORE.rows(TARGET)}


def _versions():
    return list(STORE.rows(VERSION_TARGET))


def _assert_throws(fn, needle, label):
    try:
        fn()
    except FrappeThrow as exc:
        message = str(exc)
        assert needle in message, "%s: câu lỗi thiếu %r: %s" % (
            label, needle, message)
        return message
    raise AssertionError("%s: KHÔNG throw (lỗi im lặng)" % label)


def _fresh():
    STORE.reset()


# ═══════════════════════════════════════════════════════════════════
# (1) Migrate đủ 2 loại + giữ field
# ═══════════════════════════════════════════════════════════════════
def test_migrate_du_hai_loai():
    _fresh()
    _seed_number("RULE-NUM-T", threshold_rows=[
        {"from_value": 0, "to_value": 10, "result_value": 100}])
    _seed_number("RULE-NUM-C", rule_type="CONSTANT", constant_value=48)
    _seed_number("RULE-NUM-L", rule_type="LOOKUP", lookup_rows=[
        {"key_field": "LOWE", "result_value": "1.2"}])
    _seed_item("RULE-ITEM-T", threshold_rows=[
        {"from_value": 0, "to_value": 10, "result_item": "C3209-20"}])
    _seed_item("RULE-ITEM-L", rule_type="LOOKUP", lookup_rows=[
        {"key_field": "LOWE", "result_item": "KEO-TT-01"}])

    patch_mod.execute()

    targets = _targets()
    assert set(targets) == {
        "RULE-NUM-T", "RULE-NUM-C", "RULE-NUM-L",
        "RULE-ITEM-T", "RULE-ITEM-L"}, targets

    for code in ("RULE-NUM-T", "RULE-NUM-C", "RULE-NUM-L"):
        assert targets[code].get("result_type") == "NUMBER", code
    for code in ("RULE-ITEM-T", "RULE-ITEM-L"):
        assert targets[code].get("result_type") == "ITEM", code

    # Dòng con: đúng cột kết quả, ⛔ lẫn cột của loại kia.
    number_row = targets["RULE-NUM-T"].get("threshold_rows")[0]
    assert number_row.get("result_value") == 100, number_row
    assert number_row.get("result_item") is None, number_row

    item_row = targets["RULE-ITEM-T"].get("threshold_rows")[0]
    assert item_row.get("result_item") == "C3209-20", item_row
    assert item_row.get("result_value") is None, item_row

    number_lookup = targets["RULE-NUM-L"].get("lookup_rows")[0]
    assert number_lookup.get("key_field") == "LOWE"
    assert number_lookup.get("result_value") == "1.2"
    assert number_lookup.get("result_item") is None

    item_lookup = targets["RULE-ITEM-L"].get("lookup_rows")[0]
    assert item_lookup.get("result_item") == "KEO-TT-01"
    assert item_lookup.get("result_value") is None


def test_giu_ma_ten_loai_co_tat_constant():
    _fresh()
    _seed_number("RULE-GIU", rule_type="CONSTANT", constant_value=90,
                 is_active=0)

    patch_mod.execute()

    target = _targets()["RULE-GIU"]
    assert target.get("rule_code") == "RULE-GIU", "mã rule phải giữ nguyên"
    assert target.get("rule_name") == "Tên của RULE-GIU", "tên rule phải giữ nguyên"
    assert target.get("rule_type") == "CONSTANT", "rule_type phải giữ nguyên"
    assert target.get("is_active") == 0, "is_active=0 phải giữ nguyên"
    assert target.get("constant_value") == 90, "constant_value phải giữ nguyên"


def test_rule_name_rong_thi_dien_ma_rule():
    """`rule_name` nay là field reqd ⇒ nguồn chưa đặt tên vẫn phải migrate được.

    Lý do: `AL Rule.rule_name` BẮT BUỘC (ô Item Rule cần nhãn người-đọc-được).
    Không điền gì ⇒ `insert` bị `reqd` chặn ⇒ patch chết GIỮA ĐƯỜNG, để lại
    một phần dữ liệu đã migrate. Điền `rule_code` là lựa chọn an toàn: bản ghi
    vẫn phân biệt được, quản trị đổi tên sau trên form.
    """
    _fresh()
    _seed_number("RULE-KHONG-TEN", rule_name="")

    patch_mod.execute()

    target = _targets()["RULE-KHONG-TEN"]
    assert target.get("rule_name") == "RULE-KHONG-TEN", (
        "`rule_name` rỗng ⇒ phải điền `rule_code`, nhận %r"
        % (target.get("rule_name"),))


def test_ket_qua_bang_0_khong_bi_bo():
    """`result_value = 0` là giá trị HỢP LỆ — bẫy truthiness."""
    _fresh()
    _seed_number("RULE-ZERO", threshold_rows=[
        {"from_value": 0, "to_value": 10, "result_value": 0}])

    patch_mod.execute()

    row = _targets()["RULE-ZERO"].get("threshold_rows")[0]
    assert row.get("result_value") == 0, row


# ═══════════════════════════════════════════════════════════════════
# (2) Idempotent
# ═══════════════════════════════════════════════════════════════════
def test_idempotent_chay_hai_lan():
    _fresh()
    _seed_number("RULE-I1")
    _seed_item("RULE-I2")

    patch_mod.execute()
    first = len(STORE.rows(TARGET))
    patch_mod.execute()
    second = len(STORE.rows(TARGET))

    assert first == 2, first
    assert second == first, "chạy lại nhân đôi bản ghi: %d → %d" % (first, second)


def test_cung_ma_cung_loai_thi_bo_qua():
    _fresh()
    _seed_number("RULE-BQ")
    patch_mod.execute()
    before = _targets()["RULE-BQ"]

    # Thêm 1 nguồn khác loại KHÔNG trùng mã để lần chạy sau vẫn chạy tiếp.
    _seed_item("RULE-BQ-ITEM")
    patch_mod.execute()

    assert _targets()["RULE-BQ"] is before, "bản ghi đã có bị ghi lại"


# ═══════════════════════════════════════════════════════════════════
# (3) Cổng chặn trùng mã
# ═══════════════════════════════════════════════════════════════════
def test_trung_ma_throw_co_danh_sach_va_khong_ghi_gi():
    _fresh()
    _seed_number("RULE-DUP")
    _seed_item("RULE-DUP")
    _seed_number("RULE-OK")

    message = _assert_throws(patch_mod.execute, "RULE-DUP", "trùng mã")

    assert "rule_code" in message, message
    assert "Đổi" in message, "câu lỗi phải có hướng dẫn xử lý: %s" % message
    assert STORE.rows(TARGET) == [], (
        "cổng phải chặn TRƯỚC khi ghi — đã tạo %d bản ghi"
        % len(STORE.rows(TARGET)))


def test_trung_nhieu_ma_liet_ke_du():
    _fresh()
    for code in ("RULE-A", "RULE-B"):
        _seed_number(code)
        _seed_item(code)

    message = _assert_throws(patch_mod.execute, "RULE-A", "2 mã trùng")
    assert "RULE-B" in message, "thiếu mã trùng thứ 2: %s" % message


# ═══════════════════════════════════════════════════════════════════
# (4) Cùng mã khác result_type
# ═══════════════════════════════════════════════════════════════════
def test_cung_ma_khac_loai_throw():
    _fresh()
    # `AL Rule` đã có sẵn (vd tạo tay / lần migrate trước của nhánh khác).
    STORE.add(FakeDoc(TARGET, {
        "rule_code": "RULE-X", "rule_type": "THRESHOLD",
        "result_type": "NUMBER", "threshold_rows": [],
    }))
    _seed_item("RULE-X")

    message = _assert_throws(patch_mod.execute, "RULE-X", "khác result_type")

    assert "NUMBER" in message and "ITEM" in message, message
    assert len(STORE.rows(TARGET)) == 1, "⛔ tạo thêm bản ghi khi xung đột"


# ═══════════════════════════════════════════════════════════════════
# (5) Không xoá/đổi bảng cũ  +  (6) không tự commit
# ═══════════════════════════════════════════════════════════════════
def test_khong_xoa_bang_cu():
    _fresh()
    _seed_number("RULE-G1")
    _seed_item("RULE-G2")

    patch_mod.execute()

    assert [d.get("rule_code") for d in STORE.rows(NUMBER_SOURCE)] == ["RULE-G1"]
    assert [d.get("rule_code") for d in STORE.rows(ITEM_SOURCE)] == ["RULE-G2"]


def test_khong_tu_commit():
    _fresh()
    _seed_number("RULE-C1")

    patch_mod.execute()

    assert STORE.commit_calls == 0, (
        "patch KHÔNG được tự commit (%d lần) — phá rollback của migrate"
        % STORE.commit_calls)


# ═══════════════════════════════════════════════════════════════════
# (8a) Đọc bằng SQL THÔ khi DocType record KHÔNG còn, bảng vẫn còn
# ═══════════════════════════════════════════════════════════════════
def test_doc_record_mat_bang_con_van_doc_duoc():
    """DocType record bị xoá nhưng bảng còn ⇒ patch VẪN phải đọc được.

    Đây là ca thật của chặng 2C: patch xoá DocType chạy ở lần migrate trước,
    bảng cũ còn làm đường cứu hộ; nếu patch migrate phụ thuộc meta DocType
    (`frappe.get_all`/`get_doc`) thì chết đúng lúc cần cứu hộ nhất.
    """
    _fresh()
    _seed_number("RULE-SQL", threshold_rows=[
        {"from_value": 0, "to_value": 10, "result_value": 250}])
    _seed_item("RULE-SQL-ITEM", lookup_rows=[
        {"key_field": "LOWE", "result_item": "ITEM-SQL"}])

    STORE.missing_doctype_records.update({NUMBER_SOURCE, ITEM_SOURCE})

    patch_mod.execute()

    targets = _targets()
    assert set(targets) == {"RULE-SQL", "RULE-SQL-ITEM"}, targets
    assert targets["RULE-SQL"].get("threshold_rows")[0].get("result_value") == 250
    assert (targets["RULE-SQL-ITEM"].get("lookup_rows")[0].get("result_item")
            == "ITEM-SQL")


def test_doi_chung_am_doc_qua_meta_thi_chet():
    """Đối chứng âm: đổi đường đọc sang `frappe.get_all` (qua meta) ⇒ ĐỎ."""
    _fresh()
    _seed_number(
        "RULE-META", threshold_rows=[
            {"from_value": 0, "to_value": 10, "result_value": 250}])
    STORE.missing_doctype_records.add(NUMBER_SOURCE)

    original = patch_mod._select

    def _select_qua_meta(doctype, columns, where=None, values=(), order_by=None):
        if where:
            return original(doctype, columns, where, values, order_by)
        return frappe_get_all_rows(doctype, columns)

    patch_mod._select = _select_qua_meta
    try:
        failed = None
        try:
            patch_mod.execute()
        except FakeFrappe.DoesNotExistError as exc:
            failed = str(exc)
        created = len(STORE.rows(TARGET))
    finally:
        patch_mod._select = original

    assert failed and "không còn" in failed, (
        "đường meta phải chết khi DocType record mất — nhận %r" % (failed,))
    assert created == 0, (
        "đột biến vẫn ghi được %d bản ghi ⇒ ca (8a) ⛔ thật sự đo đường đọc"
        % created)

    # Khôi phục ⇒ chạy lại được trên dữ liệu sạch.
    _fresh()
    _seed_number(
        "RULE-META", threshold_rows=[
            {"from_value": 0, "to_value": 10, "result_value": 250}])
    STORE.missing_doctype_records.add(NUMBER_SOURCE)
    patch_mod.execute()
    assert _targets()["RULE-META"].get("threshold_rows")[0].get("result_value") == 250


def frappe_get_all_rows(doctype, columns):
    rows = FRAPPE.get_all(doctype, fields=list(columns))
    return [
        {column: row.get(column) for column in columns} for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════
# (8b) Copy bản ghi version
# ═══════════════════════════════════════════════════════════════════
def test_copy_version_rows_giu_rule_la_ma_rule():
    _fresh()
    _seed_item("RULE-V1")
    _seed_version("RULE-V1", version_name="v1",
                  valid_from="2026-01-01 00:00:00", workflow_state="Published")
    _seed_version("RULE-V1", version_name="v2",
                  valid_from="2026-06-01 00:00:00", workflow_state="Draft")

    patch_mod.execute()

    versions = _versions()
    assert len(versions) == 2, "phải chép đủ 2 bản ghi version: %s" % (versions,)
    for version in versions:
        assert version.get("rule") == "RULE-V1", version.get("rule")
        assert version.get("rule_snapshot_json") == '{"a": 1}'
    assert sorted(v.get("version_name") for v in versions) == ["v1", "v2"]


def test_version_mo_coi_khong_chep():
    """Version của rule KHÔNG có `AL Rule` cùng mã ⇒ ⛔ chép."""
    _fresh()
    _seed_item("RULE-CO")
    _seed_version("RULE-CO", version_name="v1")
    _seed_version("RULE-MO-COI", version_name="v-orphan")

    patch_mod.execute()

    rules = {v.get("rule") for v in _versions()}
    assert rules == {"RULE-CO"}, (
        "chép cả version mồ côi (rule không tồn tại): %s" % (rules,))


def test_version_idempotent_chay_hai_lan():
    _fresh()
    _seed_item("RULE-V2")
    _seed_version("RULE-V2", version_name="v1")

    patch_mod.execute()
    first = len(_versions())
    patch_mod.execute()
    second = len(_versions())

    assert first == 1, first
    assert second == first, "chạy lại nhân đôi version: %d → %d" % (first, second)


# ═══════════════════════════════════════════════════════════════════
# (7) ĐỐI CHỨNG ÂM — đột biến rồi khôi phục
#     Mỗi ca chứng minh phép kiểm tương ứng CÓ RĂNG: gỡ hành vi đi thì
#     trạng thái sai xuất hiện thật, khôi phục thì hết.
# ═══════════════════════════════════════════════════════════════════
def test_doi_chung_am_cong_trung_ma():
    """Gỡ cổng ⇒ migrate ghi DỞ rồi mới chết ở lớp chặn xung đột phía sau.

    Đây chính là giá trị của cổng: cổng bảo đảm "thà không ghi gì" thay vì
    để lại `AL Rule` đã tạo cho mã KHÔNG trùng trong cùng lượt chạy.
    """
    _fresh()
    _seed_number("RULE-DUP")
    _seed_item("RULE-DUP")
    _seed_number("RULE-OK")
    _assert_throws(patch_mod.execute, "RULE-DUP", "cổng trùng mã (gốc)")
    assert STORE.rows(TARGET) == [], (
        "cổng trùng mã (gốc) phải chặn TRƯỚC khi ghi")

    original = patch_mod._assert_no_duplicate_codes
    patch_mod._assert_no_duplicate_codes = lambda number_codes, item_codes: None
    try:
        leaked = None
        try:
            patch_mod.execute()   # đột biến: bỏ cổng
        except FrappeThrow as exc:
            leaked = str(exc)
        partial = len(STORE.rows(TARGET))
    finally:
        patch_mod._assert_no_duplicate_codes = original

    assert leaked and "RULE-DUP" in leaked, (
        "đột biến bỏ cổng mà KHÔNG có lớp chặn nào phía sau ⇒ phép kiểm gốc "
        "không thật sự bắt lỗi: %r" % (leaked,))
    assert partial > 0, (
        "bỏ cổng mà vẫn không ghi dở (partial=%r) ⇒ phép kiểm 'chặn trước "
        "khi ghi' không thật sự đo được điều nó tuyên bố" % partial)

    # Khôi phục ⇒ cổng chặn lại trên dữ liệu sạch, không ghi gì.
    _fresh()
    _seed_number("RULE-DUP")
    _seed_item("RULE-DUP")
    _seed_number("RULE-OK")
    _assert_throws(patch_mod.execute, "RULE-DUP", "cổng trùng mã (khôi phục)")
    assert STORE.rows(TARGET) == []


def test_doi_chung_am_idempotent():
    _fresh()
    _seed_number("RULE-IDEM")
    patch_mod.execute()
    patch_mod.execute()
    assert len(STORE.rows(TARGET)) == 1, "idempotent (gốc)"

    original = patch_mod._target_rules
    patch_mod._target_rules = lambda: {}
    try:
        patch_mod.execute()   # đột biến: quên bản ghi đã có
        duplicated = len(STORE.rows(TARGET))
    finally:
        patch_mod._target_rules = original

    assert duplicated == 2, (
        "đột biến quên bản ghi đã có mà không nhân đôi ⇒ phép kiểm "
        "idempotent không thật sự đọc `_target_rules` (count=%r)"
        % duplicated)

    patch_mod.execute()
    assert len(STORE.rows(TARGET)) == duplicated, (
        "khôi phục xong chạy lại vẫn nhân đôi")


def test_doi_chung_am_co_is_active():
    _fresh()
    _seed_number("RULE-TAT", is_active=0)
    patch_mod.execute()
    assert _targets()["RULE-TAT"].get("is_active") == 0, "is_active (gốc)"

    original = patch_mod._build_data

    def _broken(source_row, source, threshold_rows, lookup_rows):
        data = original(source_row, source, threshold_rows, lookup_rows)
        data["is_active"] = 1         # đột biến: luôn bật
        return data

    patch_mod._build_data = _broken
    try:
        _fresh()
        _seed_number("RULE-TAT", is_active=0)
        patch_mod.execute()
        mutated = _targets()["RULE-TAT"].get("is_active")
    finally:
        patch_mod._build_data = original

    assert mutated == 1, (
        "đột biến ép is_active=1 mà kết quả vẫn 0 ⇒ patch ⛔ dùng "
        "`_build_data` để chép cờ (mutated=%r)" % mutated)

    _fresh()
    _seed_number("RULE-TAT", is_active=0)
    patch_mod.execute()
    assert _targets()["RULE-TAT"].get("is_active") == 0, "is_active (khôi phục)"


# ═══════════════════════════════════════════════════════════════════
# (8c) dry_run — kiểm TRƯỚC khi deploy (chỉ đọc)
#     Vì sao: patch chạy ở [post_model_sync]; mã trùng/xung đột làm
#     `bench migrate` chết GIỮA lượt trong khi mã mới đã deploy.
# ═══════════════════════════════════════════════════════════════════
def test_dry_run_sach_tra_ok_va_khong_ghi():
    _fresh()
    _seed_number("RULE-N1")
    _seed_number("RULE-N2")
    _seed_item("RULE-I1")

    result = patch_mod.dry_run()

    assert result["number_rules"] == 2, result
    assert result["item_rules"] == 1, result
    assert result["duplicate_codes"] == [], result
    assert result["existing_in_al_rule"] == 0, result
    assert result["conflict_codes"] == [], result
    assert result["ok"] is True, result
    assert STORE.rows(TARGET) == [], (
        "dry_run KHÔNG được ghi — đã tạo %d bản ghi `AL Rule`"
        % len(STORE.rows(TARGET)))
    assert STORE.commit_calls == 0, (
        "dry_run KHÔNG được commit (%d lần)" % STORE.commit_calls)


def test_dry_run_co_version_rows_va_khoa_cu_giu_nguyen():
    _fresh()
    _seed_item("RULE-DV")
    patch_mod.execute()            # đưa RULE-DV vào `AL Rule`
    _seed_version("RULE-DV", version_name="v1")
    _seed_version("RULE-DV", version_name="v2")

    result = patch_mod.dry_run()

    assert result["version_rows"] == 2, result
    assert result["orphan_version_rows"] == [], result
    # Khoá cũ ⛔ được đổi tên/mất.
    for key in ("number_rules", "item_rules", "duplicate_codes",
                "existing_in_al_rule", "conflict_codes", "al_rule_ready", "ok"):
        assert key in result, "dry_run mất khoá cũ %r: %s" % (key, result)


def test_dry_run_bao_version_mo_coi():
    _fresh()
    _seed_item("RULE-CO")
    patch_mod.execute()          # đưa RULE-CO vào `AL Rule`
    _seed_version("RULE-CO", version_name="v1")
    _seed_version("RULE-LAC", version_name="v-lac")

    result = patch_mod.dry_run()

    assert result["version_rows"] == 2, result
    assert result["orphan_version_rows"] == ["RULE-LAC"], result


def test_dry_run_khi_al_rule_chua_tao_khong_bao_orphan():
    """Chạy TRƯỚC migrate: bảng `AL Rule` chưa có ⇒ chưa phân biệt mồ côi."""
    _fresh()
    STORE.missing_tables.add(TARGET)
    _seed_number("RULE-N1")
    _seed_item("RULE-V")
    _seed_version("RULE-V", version_name="v1")

    result = patch_mod.dry_run()

    assert result["al_rule_ready"] is False, result
    assert result["version_rows"] == 1, result
    assert result["orphan_version_rows"] == [], result
    assert result["ok"] is True, result


def test_dry_run_phat_hien_trung_ma_va_khong_throw():
    _fresh()
    _seed_number("RULE-DUP")
    _seed_item("RULE-DUP")
    _seed_number("RULE-OK")

    result = patch_mod.dry_run()   # ⛔ được throw — chỉ báo trong dict

    assert result["duplicate_codes"] == ["RULE-DUP"], result
    assert result["ok"] is False, result
    assert STORE.rows(TARGET) == [], "dry_run ghi dù chỉ để kiểm"


def test_dry_run_phat_hien_conflict_result_type():
    _fresh()
    # `AL Rule` đã có bản ghi CÙNG mã nhưng KHÁC loại ⇒ lượt migrate thật
    # sẽ `throw` ở nhánh xung đột.
    STORE.add(FakeDoc(TARGET, {
        "rule_code": "RULE-X", "rule_type": "THRESHOLD",
        "result_type": "NUMBER", "threshold_rows": [],
    }))
    _seed_item("RULE-X")
    _seed_number("RULE-MOI")

    result = patch_mod.dry_run()

    assert result["conflict_codes"] == ["RULE-X"], result
    assert result["existing_in_al_rule"] == 1, result
    assert result["ok"] is False, result
    assert len(STORE.rows(TARGET)) == 1, "dry_run ⛔ được tạo bản ghi mới"


def test_dry_run_cung_ma_cung_loai_la_idempotent_khong_conflict():
    _fresh()
    STORE.add(FakeDoc(TARGET, {
        "rule_code": "RULE-BQ", "rule_type": "THRESHOLD",
        "result_type": "NUMBER", "threshold_rows": [],
    }))
    _seed_number("RULE-BQ")
    _seed_item("RULE-MOI")

    result = patch_mod.dry_run()

    assert result["existing_in_al_rule"] == 1, result
    assert result["conflict_codes"] == [], result
    assert result["ok"] is True, result


def test_dry_run_khi_bang_al_rule_chua_tao():
    """Chạy TRƯỚC migrate: bảng `AL Rule` chưa có ⇒ 0, ⛔ chết."""
    _fresh()
    STORE.missing_tables.add(TARGET)
    _seed_number("RULE-N1")

    result = patch_mod.dry_run()

    assert result["al_rule_ready"] is False, result
    assert result["existing_in_al_rule"] == 0, result
    assert result["conflict_codes"] == [], result
    assert result["ok"] is True, result


def test_dry_run_khi_nguon_da_bi_go():
    """Site đã gỡ 2 doctype cũ ⇒ 0/0, chỉ đọc, ⛔ chết."""
    _fresh()
    STORE.missing_tables.update({NUMBER_SOURCE, ITEM_SOURCE, VERSION_SOURCE})

    result = patch_mod.dry_run()

    assert result["number_rules"] == 0, result
    assert result["item_rules"] == 0, result
    assert result["version_rows"] == 0, result
    assert result["duplicate_codes"] == [], result
    assert result["ok"] is True, result


def test_doi_chung_am_dry_run_bo_nhanh_conflict():
    """Gỡ nhánh conflict ⇒ ca phát hiện xung đột loại phải ĐỎ."""
    _fresh()
    STORE.add(FakeDoc(TARGET, {
        "rule_code": "RULE-X", "rule_type": "THRESHOLD",
        "result_type": "NUMBER", "threshold_rows": [],
    }))
    _seed_item("RULE-X")

    goc = patch_mod.dry_run()
    assert goc["conflict_codes"] == ["RULE-X"], goc
    assert goc["ok"] is False, goc

    original = patch_mod._existing_conflicts

    def _bo_nhanh_conflict(codes_by_type):
        existing, _conflicts = original(codes_by_type)
        return existing, []          # đột biến: quên nhánh conflict

    patch_mod._existing_conflicts = _bo_nhanh_conflict
    try:
        dot_bien = patch_mod.dry_run()
    finally:
        patch_mod._existing_conflicts = original

    assert dot_bien["conflict_codes"] == [], dot_bien
    assert dot_bien["ok"] is True, (
        "bỏ nhánh conflict mà `ok` vẫn False ⇒ phép kiểm không đọc đúng "
        "nhánh conflict: %r" % (dot_bien,))

    # Khôi phục ⇒ phát hiện lại xung đột.
    assert patch_mod.dry_run()["conflict_codes"] == ["RULE-X"]


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════
def _main():
    import traceback

    funcs = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    passed, failed = 0, []
    for name, fn in funcs:
        try:
            fn()
            print("  PASS  " + name)
            passed += 1
        except Exception:
            print("  FAIL  " + name)
            print("        " + traceback.format_exc().strip().replace("\n", "\n        "))
            failed.append(name)
    print("\n" + "=" * 60)
    print("  TOTAL: %d  PASS: %d  FAIL: %d" % (len(funcs), passed, len(failed)))
    if failed:
        print("  FAILED: %s" % (failed,))
        sys.exit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _main()
