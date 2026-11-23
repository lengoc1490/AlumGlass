# -*- coding: utf-8 -*-
"""CHẶNG 2C — kiểm patch `delete_legacy_rule_doctypes`.

BỐI CẢNH
────────
Patch chạy NGAY SAU `migrate_rules_to_al_rule` (cùng `[post_model_sync]`):
xoá **DocType record** của 5 doctype rule cũ, ⛔ DROP bảng dữ liệu.

Bộ test chứng minh:
  (1) CỔNG CHẶN: mã rule cũ CHƯA có `AL Rule` cùng mã ⇒ `throw` nêu mã,
      ⛔ xoá DocType nào; LỆCH `result_type` cũng throw;
  (2) Thứ tự xoá AN TOÀN: con/version TRƯỚC, cha SAU;
  (3) IDEMPOTENT: chạy 2 lần không lỗi, lần 2 không xoá lại;
  (3b) DỌN WORKFLOW: xoá đúng bản ghi `Workflow` cũ nếu có, giữ
      `AL Rule Version Workflow`, không có thì bỏ qua êm, lỗi ⇒ log + throw;
  (4) ⛔ DROP TABLE: không câu SQL nào là DROP;
  (5) Frappe từ chối xoá (còn Link) ⇒ log rõ + throw, ⛔ nuốt lỗi;
  (6) ĐỐI CHỨNG ÂM thật (đột biến rồi khôi phục):
      - bỏ cổng chặn ⇒ ca "thiếu mã" ĐỎ (dữ liệu bị xoá mà chưa migrate);
      - đảo thứ tự xoá ⇒ ca thứ tự ĐỎ;
      - bỏ lời gọi dọn Workflow ⇒ ca Workflow ĐỎ.

CÁCH CHẠY (không cần site):
    python3 standalone_tests/test_delete_legacy_rules.py
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
# Stub `frappe`
# ═══════════════════════════════════════════════════════════════════
class FrappeThrow(Exception):
    """`frappe.throw` — câu lỗi người-đọc-được."""


SELECT_RE = re.compile(
    r"^\s*select\s+(?P<cols>.+?)\s+from\s+`tab(?P<table>[^`]+)`"
    r"(?:\s+where\s+.+?)?"
    r"(?:\s+order\s+by\s+(?P<order>.+?))?\s*$",
    re.IGNORECASE | re.DOTALL)


class Store:
    def __init__(self):
        self.reset()

    def reset(self):
        # doctype -> [dict] dữ liệu bảng thật (kể cả bảng mồ côi).
        self.tables = {}
        # DocType record còn tồn tại (xoá được).
        self.doctype_records = set()
        # Workflow record đang có: {workflow_name: document_type}.
        self.workflows = {}
        # DocType mà Frappe từ chối xoá (còn Link) — giả lập lỗi.
        self.refuse = set()
        self.deleted = []          # [(doctype, name)]
        self.sql_queries = []
        self.logs = []             # [(message, title)]
        self.commit_calls = 0

    def seed(self, doctype, rows, record=True):
        self.tables[doctype] = list(rows)
        if record:
            self.doctype_records.add(doctype)


STORE = Store()


class FakeDB:
    def table_exists(self, doctype, *args, **kwargs):
        return doctype in STORE.tables

    def exists(self, doctype, name, *args, **kwargs):
        if doctype == "DocType":
            return name if name in STORE.doctype_records else None
        if doctype == "Workflow":
            return name if name in STORE.workflows else None
        return name if doctype in STORE.tables else None

    def sql(self, query, values=None, as_dict=False, *args, **kwargs):
        STORE.sql_queries.append(query)
        match = SELECT_RE.match(query)
        assert match, "stub SQL không hiểu câu: %r" % query
        table = match.group("table")
        columns = [
            column.strip().strip("`")
            for column in match.group("cols").split(",")
        ]
        rows = list(STORE.tables.get(table, []))
        if match.group("order"):
            field = match.group("order").strip().strip("`")
            rows = sorted(rows, key=lambda row: row.get(field) or "")
        if as_dict:
            return [{column: row.get(column) for column in columns} for row in rows]
        return [tuple(row.get(column) for column in columns) for row in rows]

    def commit(self, *args, **kwargs):
        STORE.commit_calls += 1


def _delete_doc(doctype, name=None, force=0, ignore_permissions=False, *a, **k):
    if name in STORE.refuse:
        raise Exception("LinkExistsError: %s còn bị Link tới" % name)
    STORE.deleted.append((doctype, name))
    if doctype == "DocType":
        STORE.doctype_records.discard(name)
    elif doctype == "Workflow":
        STORE.workflows.pop(name, None)
    return True


def _log_error(message=None, title=None, *a, **k):
    STORE.logs.append((message, title))


def _throw(message, *args, **kwargs):
    raise FrappeThrow(message)


def _install_frappe_stub():
    for name in [n for n in list(sys.modules)
                 if n == "alumglass" or n.startswith("alumglass.")]:
        del sys.modules[name]

    fake_db = FakeDB()
    module = types.ModuleType("frappe")
    module.db = fake_db
    module.delete_doc = _delete_doc
    module.log_error = _log_error
    module.throw = _throw
    module.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
    sys.modules["frappe"] = module
    return module


FRAPPE = _install_frappe_stub()

import alumglass.patches.v1_0.delete_legacy_rule_doctypes as patch_mod  # noqa: E402

NUMBER_SOURCE = "AL Calculation Rule"
ITEM_SOURCE = "AL Dynamic Item Rule"

CANONICAL_ORDER = [
    "AL Dynamic Item Rule Version",
    "AL Dynamic Item Rule Threshold Row",
    "AL Dynamic Item Rule Lookup Row",
    "AL Dynamic Item Rule",
    "AL Calculation Rule",
]


# ═══════════════════════════════════════════════════════════════════
# Dựng dữ liệu
# ═══════════════════════════════════════════════════════════════════
def _fresh():
    STORE.reset()


def _seed_target(rules):
    """`rules` = {rule_code: result_type} trong `AL Rule`."""
    STORE.seed(
        "AL Rule",
        [{"rule_code": code, "result_type": result_type}
         for code, result_type in rules.items()],
        record=True,
    )


def _seed_legacy(number_codes=(), item_codes=(), with_version_rows=True):
    STORE.seed(NUMBER_SOURCE, [{"rule_code": code, "name": code}
                               for code in number_codes])
    STORE.seed(ITEM_SOURCE, [{"rule_code": code, "name": code}
                             for code in item_codes])
    child_rows = [{"name": "ROW-1"}]
    STORE.seed("AL Dynamic Item Rule Threshold Row", child_rows)
    STORE.seed("AL Dynamic Item Rule Lookup Row", child_rows)
    if with_version_rows:
        STORE.seed("AL Dynamic Item Rule Version", [{"name": "VER-1"}])


def _seed_fully_migrated(number_codes=("R-N1", "R-N2"),
                         item_codes=("R-I1",)):
    targets = {}
    for code in number_codes:
        targets[code] = "NUMBER"
    for code in item_codes:
        targets[code] = "ITEM"
    _seed_target(targets)
    _seed_legacy(number_codes, item_codes)


def _seed_workflow(name, document_type="AL Dynamic Item Rule Version"):
    STORE.workflows[name] = document_type


def _assert_throws(fn, needle, label):
    try:
        fn()
    except FrappeThrow as exc:
        message = str(exc)
        assert needle in message, "%s: câu lỗi thiếu %r: %s" % (
            label, needle, message)
        return message
    raise AssertionError("%s: KHÔNG throw (lỗi im lặng)" % label)


# ═══════════════════════════════════════════════════════════════════
# (1) Cổng chặn
# ═══════════════════════════════════════════════════════════════════
def test_thieu_ma_trong_al_rule_thi_throw_va_khong_xoa():
    _fresh()
    _seed_target({"R-N1": "NUMBER"})            # thiếu R-N2
    _seed_legacy(("R-N1", "R-N2"), ("R-I1",))

    message = _assert_throws(patch_mod.execute, "R-N2", "thiếu mã")

    assert "AL Rule" in message, message
    assert STORE.deleted == [], (
        "cổng phải chặn TRƯỚC khi xoá — đã xoá: %s" % (STORE.deleted,))


def test_lech_result_type_thi_throw_neu_ma_va_hai_loai():
    _fresh()
    # Nguồn ITEM nhưng `AL Rule` cùng mã lại là NUMBER.
    _seed_target({"R-N1": "NUMBER", "R-I1": "NUMBER"})
    _seed_legacy(("R-N1",), ("R-I1",))

    message = _assert_throws(patch_mod.execute, "R-I1", "lệch result_type")

    assert "NUMBER" in message and "ITEM" in message, message
    assert STORE.deleted == [], "lệch loại mà vẫn xoá: %s" % (STORE.deleted,)


# ═══════════════════════════════════════════════════════════════════
# (2) Thứ tự xoá an toàn
# ═══════════════════════════════════════════════════════════════════
def test_xoa_dung_thu_tu_con_truoc_cha_sau():
    _fresh()
    _seed_fully_migrated()

    patch_mod.execute()

    assert [name for _doctype, name in STORE.deleted] == CANONICAL_ORDER, (
        "thứ tự xoá sai: %s" % ([name for _d, name in STORE.deleted],))


def test_xoa_bang_delete_doc_force_ignore_permissions():
    """Chỉ xoá DocType record qua `delete_doc`, ⛔ xoá bảng/dữ liệu khác."""
    _fresh()
    _seed_fully_migrated()

    patch_mod.execute()

    assert all(doctype == "DocType" for doctype, _name in STORE.deleted), (
        "phải chỉ xoá DocType record: %s" % (STORE.deleted,))


# ═══════════════════════════════════════════════════════════════════
# (3) Idempotent
# ═══════════════════════════════════════════════════════════════════
def test_idempotent_chay_hai_lan_khong_loi():
    _fresh()
    _seed_fully_migrated()

    patch_mod.execute()
    first = len(STORE.deleted)

    patch_mod.execute()          # lần 2: DocType record đã mất ⇒ bỏ qua
    second = len(STORE.deleted)

    assert first == len(CANONICAL_ORDER), first
    assert second == first, "chạy lại xoá thêm: %d → %d" % (first, second)


def test_idempotent_khi_doc_type_da_mat_tu_truoc():
    """DocType record đã mất (vd chạy tay lại patch) ⇒ bỏ qua êm."""
    _fresh()
    _seed_fully_migrated()
    STORE.doctype_records.clear()   # tất cả DocType record đã bị xoá trước đó

    patch_mod.execute()

    assert STORE.deleted == [], "không còn DocType record mà vẫn 'xoá': %s" % (
        STORE.deleted,)


# ═══════════════════════════════════════════════════════════════════
# (3b) Dọn Workflow mồ côi của doctype version cũ
# ═══════════════════════════════════════════════════════════════════
def test_xoa_workflow_cu_giu_workflow_moi():
    """Có Workflow cũ ⇒ xoá nó; `AL Rule Version Workflow` ⛔ bị đụng."""
    _fresh()
    _seed_fully_migrated()
    _seed_workflow("AL Dynamic Item Rule Version Workflow")
    _seed_workflow("AL Rule Version Workflow", "AL Rule Version")

    patch_mod.execute()

    assert "AL Dynamic Item Rule Version Workflow" not in STORE.workflows, (
        "Workflow cũ trỏ tới DocType đã xoá vẫn còn: %s" % (STORE.workflows,))
    assert "AL Rule Version Workflow" in STORE.workflows, (
        "xoá nhầm Workflow của `AL Rule Version`")
    deleted_workflows = [
        name for doctype, name in STORE.deleted if doctype == "Workflow"]
    assert deleted_workflows == ["AL Dynamic Item Rule Version Workflow"], (
        "chỉ được xoá đúng 1 Workflow cũ: %s" % (deleted_workflows,))


def test_khong_co_workflow_cu_khong_loi():
    """Đối chứng dương: site chưa từng có Workflow cũ ⇒ không lỗi, không xoá."""
    _fresh()
    _seed_fully_migrated()
    _seed_workflow("AL Rule Version Workflow", "AL Rule Version")

    patch_mod.execute()

    assert [name for d, name in STORE.deleted if d == "Workflow"] == [], (
        "xoá Workflow dù không có bản ghi cũ")


def test_workflow_idempotent_chay_hai_lan():
    _fresh()
    _seed_fully_migrated()
    _seed_workflow("AL Dynamic Item Rule Version Workflow")

    patch_mod.execute()
    first = [n for d, n in STORE.deleted if d == "Workflow"]
    patch_mod.execute()          # lần 2: Workflow đã mất ⇒ bỏ qua
    second = [n for d, n in STORE.deleted if d == "Workflow"]

    assert first == ["AL Dynamic Item Rule Version Workflow"], first
    assert second == first, "chạy lại xoá thêm Workflow: %s → %s" % (first, second)


def test_frappe_tu_choi_xoa_workflow_thi_log_va_throw():
    _fresh()
    _seed_fully_migrated()
    _seed_workflow("AL Dynamic Item Rule Version Workflow")
    STORE.refuse.add("AL Dynamic Item Rule Version Workflow")

    message = _assert_throws(
        patch_mod.execute, "AL Dynamic Item Rule Version Workflow",
        "từ chối xoá Workflow")

    assert STORE.logs, "phải ghi log lỗi trước khi throw"
    logged_message, title = STORE.logs[-1]
    assert "Workflow" in (logged_message or ""), logged_message
    assert title, "log thiếu tiêu đề"
    # DocType đã xoá xong trước đó — lỗi Workflow vẫn phải nổi lên.
    assert len([d for d, _n in STORE.deleted if d == "DocType"]) == len(
        CANONICAL_ORDER), STORE.deleted


def test_doi_chung_am_bo_xoa_workflow():
    """Bỏ lời gọi xoá Workflow ⇒ Workflow cũ còn lại ⇒ ca mới phải ĐỎ."""
    _fresh()
    _seed_fully_migrated()
    _seed_workflow("AL Dynamic Item Rule Version Workflow")

    original = patch_mod._delete_legacy_workflow
    patch_mod._delete_legacy_workflow = lambda: False
    try:
        patch_mod.execute()      # đột biến: quên dọn Workflow
        leaked = "AL Dynamic Item Rule Version Workflow" in STORE.workflows
    finally:
        patch_mod._delete_legacy_workflow = original

    assert leaked, (
        "bỏ lời gọi mà Workflow vẫn biến mất ⇒ ca dọn Workflow không thật sự "
        "đo hành vi xoá")

    # Khôi phục ⇒ dọn được.
    _fresh()
    _seed_fully_migrated()
    _seed_workflow("AL Dynamic Item Rule Version Workflow")
    patch_mod.execute()
    assert "AL Dynamic Item Rule Version Workflow" not in STORE.workflows


# ═══════════════════════════════════════════════════════════════════
# (4) ⛔ DROP TABLE
# ═══════════════════════════════════════════════════════════════════
def test_khong_drop_bang_du_lieu():
    _fresh()
    _seed_fully_migrated()
    tables_before = set(STORE.tables)

    patch_mod.execute()

    drops = [
        query for query in STORE.sql_queries
        if "drop" in query.lower()
    ]
    assert drops == [], "patch ⛔ được DROP bảng dữ liệu: %s" % (drops,)
    # Bảng mồ côi vẫn còn nguyên sau khi xoá DocType (đường cứu hộ 1 chu kỳ).
    assert set(STORE.tables) == tables_before, (
        "bảng dữ liệu bị mất khỏi store: %s"
        % (tables_before - set(STORE.tables),))


# ═══════════════════════════════════════════════════════════════════
# (5) Frappe từ chối xoá ⇒ log + throw, ⛔ nuốt lỗi
# ═══════════════════════════════════════════════════════════════════
def test_frappe_tu_choi_thi_log_ro_va_throw():
    _fresh()
    _seed_fully_migrated()
    STORE.refuse.add("AL Dynamic Item Rule")

    message = _assert_throws(patch_mod.execute, "AL Dynamic Item Rule", "từ chối")

    assert STORE.logs, "phải ghi log lỗi trước khi throw"
    logged_message, title = STORE.logs[-1]
    assert "AL Dynamic Item Rule" in (logged_message or ""), logged_message
    assert title, "log thiếu tiêu đề"
    # Dừng ngay tại DocType lỗi — ⛔ xoá tiếp 2 cha phía sau.
    assert [name for _d, name in STORE.deleted] == [
        "AL Dynamic Item Rule Version",
        "AL Dynamic Item Rule Threshold Row",
        "AL Dynamic Item Rule Lookup Row",
    ], STORE.deleted


# ═══════════════════════════════════════════════════════════════════
# (6) ĐỐI CHỨNG ÂM — đột biến rồi khôi phục
# ═══════════════════════════════════════════════════════════════════
def test_doi_chung_am_bo_cong_chan():
    """Bỏ cổng ⇒ xoá dù dữ liệu chưa migrate ⇒ ca 'thiếu mã' phải ĐỎ."""
    _fresh()
    _seed_target({"R-N1": "NUMBER"})
    _seed_legacy(("R-N1", "R-N2"), ("R-I1",))

    # Gốc: cổng chặn, không xoá gì.
    _assert_throws(patch_mod.execute, "R-N2", "cổng (gốc)")
    assert STORE.deleted == [], "cổng (gốc) vẫn xoá: %s" % (STORE.deleted,)

    original = patch_mod._assert_migrated
    patch_mod._assert_migrated = lambda: None
    try:
        patch_mod.execute()      # đột biến: bỏ cổng
        leaked = list(STORE.deleted)
    finally:
        patch_mod._assert_migrated = original

    assert leaked, (
        "bỏ cổng mà vẫn không xoá gì ⇒ ca 'thiếu mã' không thật sự đo cổng")
    # Dữ liệu chưa-migrate đã bị xoá ⇒ đây chính là hậu quả cổng ngăn được.

    # Khôi phục: cổng chặn lại.
    _fresh()
    _seed_target({"R-N1": "NUMBER"})
    _seed_legacy(("R-N1", "R-N2"), ("R-I1",))
    _assert_throws(patch_mod.execute, "R-N2", "cổng (khôi phục)")
    assert STORE.deleted == []


def test_doi_chung_am_dao_thu_tu_xoa():
    """Đảo thứ tự xoá ⇒ ca thứ tự phải ĐỎ (bắt được vì so đúng danh sách)."""
    _fresh()
    _seed_fully_migrated()

    original = patch_mod.DELETE_ORDER
    patch_mod.DELETE_ORDER = tuple(reversed(CANONICAL_ORDER))
    try:
        patch_mod.execute()
        mutated = [name for _d, name in STORE.deleted]
    finally:
        patch_mod.DELETE_ORDER = original

    assert mutated != CANONICAL_ORDER, (
        "đảo thứ tự mà danh sách vẫn khớp ⇒ ca thứ tự không thật sự đo thứ "
        "tự: %s" % (mutated,))
    assert mutated == list(reversed(CANONICAL_ORDER)), mutated

    # Khôi phục ⇒ đúng thứ tự lại.
    _fresh()
    _seed_fully_migrated()
    patch_mod.execute()
    assert [name for _d, name in STORE.deleted] == CANONICAL_ORDER


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
