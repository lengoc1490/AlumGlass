# -*- coding: utf-8 -*-
"""CHẶNG 1/2C — kiểm `al_formula_rules.rule_engine` + 4 lỗi vá.

BỐI CẢNH
────────
`AL Rule` gộp cả 2 loại kết quả (NUMBER trả `result_value`, ITEM trả
`result_item`) — cùng khái niệm "dải ngưỡng" nhưng trước đây mỗi doctype rule
tự chép sort / kiểm chồng lấp / cảnh báo khe hở / resolve. Chặng 1 gom về
`alumglass/al_formula_rules/rule_engine.py`; hai doctype cũ đã bị xoá
(2026-11-23), `AL Rule` là nơi duy nhất còn dùng.

Bộ test này chứng minh:
  (1) HAI loại kết quả cho CÙNG kết quả trên cùng dữ liệu biên `[0,10) [10,20]`
      với input 0 / 9.99 / 10 / 19.99 / 20 / 21;
  (2) Dữ liệu CŨ kiểu đóng `[0,10] [10.1,20]` với input 10 ⇒ vẫn khớp
      (hành vi cũ giữ nguyên — nếu mất, NV_LD về 0 ⇒ sai giá âm thầm);
  (3) `from > to` ⇒ throw (lỗi #1 — dữ liệu cũ từng cho lọt);
  (4) `is_active = 0` ⇒ `resolve()` trả None (lỗi #2) và engine ghi cảnh báo
      `lookup_rule_da_tat:*` / `dynamic_rule_da_tat:*`;
  (5) mã rule sai ⇒ `_resolve_dynamic_item` ⛔ chết lượt tính, trả None +
      cảnh báo `dynamic_rule_thieu_ma:*` (lỗi #3);
  (6) chồng lấp ⇒ throw; chạm biên ⇒ KHÔNG throw; khe hở ⇒ msgprint, KHÔNG
      throw;
  (7) câu cảnh báo `lookup_rule_thieu_ma` nêu MÃ đã thiếu + hậu quả + lối xử
      lý (⛔ phơi "AL Rule" trần).

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_rule_engine.py
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_phase_b_fbmax as base  # noqa: E402  (cài stub `frappe` khi import)

STUB = base._STUB

from alumglass.al_formula_rules import rule_engine  # noqa: E402

import alumglass.engine.bom_orchestrator as engine_mod  # noqa: E402
from alumglass.al_formula_rules.doctype.al_rule.al_rule import (  # noqa: E402
    ALRule,
)


# ═══════════════════════════════════════════════════════════════════
# Stub bổ sung — throw đúng lớp + hứng msgprint
# ═══════════════════════════════════════════════════════════════════
def _throw(*args, **kwargs):
    exc_type = kwargs.get("exc")
    for arg in args[1:]:
        if isinstance(arg, type) and issubclass(arg, BaseException):
            exc_type = arg
    message = args[0] if args else "frappe.throw"
    raise (exc_type or STUB.ValidationError)(message)


STUB.throw = _throw

MSGPRINTS = []


def _msgprint(message, **kwargs):
    MSGPRINTS.append({"message": message, "title": kwargs.get("title")})


STUB.msgprint = _msgprint


# ═══════════════════════════════════════════════════════════════════
# Dựng rule thật của `AL Rule` (stub Document đọc/ghi như nhau)
# ═══════════════════════════════════════════════════════════════════
def _make_rule(result_type="NUMBER", rows=None, active=1,
               rule_type="THRESHOLD", constant_value=None):
    doc = ALRule()
    doc._data = {
        "is_active": active,
        "rule_type": rule_type,
        "result_type": result_type,
        "constant_value": constant_value,
    }
    doc.rule_type = rule_type
    doc.result_type = result_type
    doc.constant_value = constant_value
    doc.threshold_rows = list(rows or [])
    doc.lookup_rows = []
    return doc


def _calc(rows, active=1):
    return _make_rule("NUMBER", rows, active=active)


def _dyn(rows, active=1):
    return _make_rule("ITEM", rows, active=active)


def _rows(field, upper_open=True, lower=0, upper=10):
    """2 dải liền nhau; `upper_open=True` là quy ước nửa mở đúng."""
    second_from = upper if upper_open else upper + 0.1
    value_a = 100 if field == "result_value" else "ITEM-A"
    value_b = 200 if field == "result_value" else "ITEM-B"
    return [
        {"from_value": lower, "to_value": upper, field: value_a},
        {"from_value": second_from, "to_value": upper + 10, field: value_b},
    ]


def _expected(field):
    value_a = 100 if field == "result_value" else "ITEM-A"
    value_b = 200 if field == "result_value" else "ITEM-B"
    return [
        (0, value_a),
        (9.99, value_a),
        (10, value_b),
        (19.99, value_b),
        (20, value_b),      # lưới tương thích biên trên ĐÓNG
        (21, None),
    ]


def _assert_throws(fn, needle, label):
    try:
        fn()
    except STUB.ValidationError as exc:
        message = str(exc)
        assert needle in message, "%s: câu lỗi thiếu %r: %s" % (
            label, needle, message)
        return message
    except Exception as exc:  # noqa: BLE001 — phân biệt lỗi hạ tầng
        raise AssertionError(
            "%s: ném %s thay vì ValidationError: %s"
            % (label, type(exc).__name__, exc))
    raise AssertionError("%s: KHÔNG throw (dữ liệu sai vẫn lưu được)" % label)


# ═══════════════════════════════════════════════════════════════════
# (1) Hai loại kết quả CÙNG kết quả trên dữ liệu biên
# ═══════════════════════════════════════════════════════════════════
def test_hai_loai_ket_qua_cung_ket_qua_tren_bien():
    calc = _calc(_rows("result_value"))
    dyn = _dyn(_rows("result_item"))

    for field, doc in (("result_value", calc), ("result_item", dyn)):
        for input_value, expected in _expected(field):
            actual = doc.resolve(input_value)
            assert actual == expected, (
                "%s/%s với input %r: mong %r, nhận %r"
                % (type(doc).__name__, doc.result_type, input_value,
                   expected, actual))


def test_hai_loai_ket_qua_tra_ve_giong_nhau_theo_cap():
    """Đối chứng chéo: mọi input phải phân loại về CÙNG dải ở 2 loại kết quả."""
    calc = _calc(_rows("result_value"))
    dyn = _dyn(_rows("result_item"))
    for input_value in (0, 9.99, 10, 19.99, 20, 21):
        calc_value = calc.resolve(input_value)
        dyn_value = dyn.resolve(input_value)
        calc_bucket = None if calc_value is None else (
            "A" if calc_value == 100 else "B")
        dyn_bucket = None if dyn_value is None else (
            "A" if dyn_value == "ITEM-A" else "B")
        assert calc_bucket == dyn_bucket, (
            "input %r: result_type=NUMBER chọn %r còn result_type=ITEM "
            "chọn %r — 2 loại lệch ngữ nghĩa biên"
            % (input_value, calc_bucket, dyn_bucket))


def test_sort_theo_from_value_khong_theo_thu_tu_luu():
    field = "result_value"
    rows = list(reversed(_rows(field)))
    doc = _calc(rows)
    assert doc.resolve(5) == 100, "sort phải theo from_value, ⛔ thứ tự lưu"
    assert doc.resolve(15) == 200


# ═══════════════════════════════════════════════════════════════════
# (2) Dữ liệu CŨ kiểu đóng có khe 0.1 — input đúng biên vẫn khớp
# ═══════════════════════════════════════════════════════════════════
def test_du_lieu_cu_kieu_dong_input_10_van_khop():
    calc = _calc(_rows("result_value", upper_open=False))
    dyn = _dyn(_rows("result_item", upper_open=False))

    assert calc.resolve(10) == 100, (
        "rule cũ khai [0,10] + [10.1,20]: input 10 PHẢI khớp dải dưới "
        "(lưới tương thích), nếu không NV_LD về 0 ⇒ sai giá")
    assert dyn.resolve(10) == "ITEM-A"
    # Input nằm trong KHE 10 → 10.1 vẫn không khớp dòng nào (hành vi cũ).
    assert calc.resolve(10.05) is None
    assert dyn.resolve(10.05) is None
    # Biên trên của dải cuối vẫn khớp theo lưới tương thích.
    assert calc.resolve(20) == 200
    assert dyn.resolve(20) == "ITEM-B"


# ═══════════════════════════════════════════════════════════════════
# (3) from > to ⇒ throw (cả 2 loại kết quả)
# ═══════════════════════════════════════════════════════════════════
def test_from_lon_hon_to_bi_chan_ca_hai_loai():
    bad_rows = [{"from_value": 20, "to_value": 10, "result_value": 100}]
    _assert_throws(
        lambda: _calc(bad_rows).validate(), "Dòng ngưỡng 1", "result_type=NUMBER")
    _assert_throws(
        lambda: _calc(bad_rows).validate(), "'Từ'", "result_type=NUMBER")

    bad_dyn = [{"from_value": 20, "to_value": 10, "result_item": "ITEM-A"}]
    _assert_throws(
        lambda: _dyn(bad_dyn).validate(), "Dòng ngưỡng 1", "result_type=ITEM")


def test_from_bang_to_khong_bi_chan():
    """Đối chứng dương: from == to là dải rỗng nhưng vẫn là khai hợp lệ."""
    rows = [{"from_value": 10, "to_value": 10, "result_value": 100}]
    _calc(rows).validate()
    _dyn([{"from_value": 10, "to_value": 10, "result_item": "ITEM-A"}]).validate()


# ═══════════════════════════════════════════════════════════════════
# (4) is_active = 0 ⇒ resolve() trả None (cả 2 doctype)
# ═══════════════════════════════════════════════════════════════════
def test_rule_tat_resolve_tra_none():
    calc = _calc(_rows("result_value"), active=0)
    dyn = _dyn(_rows("result_item"), active=0)
    assert calc.resolve(5) is None, "rule TẮT mà vẫn trả giá trị"
    assert dyn.resolve(5) is None, "rule TẮT mà vẫn trả mã vật tư"

    # Đối chứng dương: bật lại ⇒ có kết quả.
    assert _calc(_rows("result_value"), active=1).resolve(5) == 100
    assert _dyn(_rows("result_item"), active=1).resolve(5) == "ITEM-A"


def test_rule_tat_lookup_constant_cung_tra_none():
    constant = _make_rule(
        "NUMBER", [], active=0, rule_type="CONSTANT", constant_value=7)
    assert constant.resolve(None) is None, "CONSTANT rule tắt vẫn trả giá trị"

    lookup = _make_rule("ITEM", [], active=0, rule_type="LOOKUP")
    lookup.lookup_rows = [{"key_field": "K", "result_item": "ITEM-K"}]
    assert lookup.resolve("K") is None


# ═══════════════════════════════════════════════════════════════════
# (4b) Engine ghi cảnh báo khi rule đã tắt
# ═══════════════════════════════════════════════════════════════════
class _FakeRuleDoc(object):
    def __init__(self, active=1, result=None, result_type="NUMBER"):
        self._data = {"is_active": active, "rule_name": "Rule thử",
                      "result_type": result_type}
        self._result = result
        self.resolve_calls = []

    def get(self, key, default=None):
        return self._data.get(key, default)

    def resolve(self, value):
        self.resolve_calls.append(value)
        return self._result


class _WarningSpy(object):
    """Thay `_record_engine_warning` bằng bộ thu — không phụ thuộc frappe.local."""

    def __init__(self):
        self.warnings = {}
        self._original = None

    def __enter__(self):
        spy = self
        self._original = engine_mod._record_engine_warning

        def _record(key, message):
            spy.warnings[key] = message

        engine_mod._record_engine_warning = _record
        return self

    def __exit__(self, *exc_info):
        engine_mod._record_engine_warning = self._original
        return False


class _CachedDocPatch(object):
    def __init__(self, doc=None, missing=False):
        self.doc = doc
        self.missing = missing
        self._original = None

    def __enter__(self):
        self._original = STUB.get_cached_doc
        patch = self

        def _get_cached_doc(doctype, name):
            if patch.missing:
                raise STUB.DoesNotExistError("%s %s không tồn tại" % (doctype, name))
            return patch.doc

        STUB.get_cached_doc = _get_cached_doc
        return self

    def __exit__(self, *exc_info):
        STUB.get_cached_doc = self._original
        return False


def test_lookup_rule_da_tat_ghi_canh_bao_va_tra_0():
    rule = _FakeRuleDoc(active=0, result=None)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-TAT", 5)

    assert value == 0, "rule tắt phải tạm tính 0 cho lượt tính ⛔ chết: %r" % value
    assert "lookup_rule_da_tat:RULE-TAT" in spy.warnings, (
        "rule tắt mà KHÔNG có cảnh báo ⇒ người dùng tưởng giá đúng: %s"
        % (spy.warnings,))
    assert "tạm tính 0" in spy.warnings["lookup_rule_da_tat:RULE-TAT"]
    assert "lookup_rule_khong_khop:RULE-TAT" not in spy.warnings, (
        "rule TẮT đã có cảnh báo riêng — ⛔ báo chồng thêm 'không khớp': %s"
        % (spy.warnings,))


def test_lookup_rule_dang_bat_khong_canh_bao():
    """Đối chứng dương: rule bật ⇒ trả kết quả, KHÔNG cảnh báo."""
    rule = _FakeRuleDoc(active=1, result=42)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-BAT", 5)

    assert value == 42
    assert spy.warnings == {}, "rule bật mà vẫn cảnh báo: %s" % (spy.warnings,)


def test_dynamic_rule_da_tat_ghi_canh_bao_va_tra_none():
    rule = _FakeRuleDoc(active=0, result=None, result_type="ITEM")
    fake_self = types.SimpleNamespace(_rule_names={}, _rule_matches={})
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            fake_self, "RULE-DYN-TAT", 5)

    assert value is None, "rule tắt phải trả None: %r" % value
    assert "dynamic_rule_da_tat:RULE-DYN-TAT" in spy.warnings, spy.warnings


# ═══════════════════════════════════════════════════════════════════
# (5) Mã rule sai ⇒ `_resolve_dynamic_item` KHÔNG được chết
# ═══════════════════════════════════════════════════════════════════
def test_dynamic_rule_thieu_ma_ghi_canh_bao_va_tra_none():
    fake_self = types.SimpleNamespace(_rule_names={}, _rule_matches={})
    with _CachedDocPatch(missing=True), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            fake_self, "RULE-SAI", 5)

    assert value is None, (
        "mã rule sai ⇒ trả None (bỏ dòng), nhưng nhận %r" % value)
    key = "dynamic_rule_thieu_ma:RULE-SAI"
    assert key in spy.warnings, (
        "mã rule sai mà KHÔNG cảnh báo ⇒ lỗi cấu hình biến mất: %s"
        % (spy.warnings,))
    assert "Không tìm thấy quy tắc chọn mã" in spy.warnings[key]
    assert "tạm không có mã vật tư" in spy.warnings[key]


def test_lookup_rule_thieu_ma_cau_chu_khoa():
    """Mã rule không tồn tại: câu khoá mới (nêu mã + hậu quả + báo quản trị)."""
    with _CachedDocPatch(missing=True), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-MAT", 5)

    assert value == 0
    message = spy.warnings.get("lookup_rule_thieu_ma:RULE-MAT")
    assert message == (
        "Không tìm thấy quy tắc có mã 'RULE-MAT' (công thức tham chiếu sai "
        "mã?) — tạm tính 0, thành tiền chưa đúng. Báo quản trị kiểm tra "
        "công thức."), message


# ═══════════════════════════════════════════════════════════════════
# (6) Chồng lấp / chạm biên / khe hở
# ═══════════════════════════════════════════════════════════════════
def _validate(field, rows):
    rule_engine.validate_threshold_rows(rows, field, "Rule thử")


def test_chong_lap_bi_chan_ca_hai_loai():
    overlap = [
        {"from_value": 0, "to_value": 10, "result_value": 100},
        {"from_value": 5, "to_value": 20, "result_value": 200},
    ]
    _assert_throws(lambda: _validate("result_value", overlap),
                   "chồng lấp", "result_value")

    overlap_item = [
        {"from_value": 0, "to_value": 10, "result_item": "ITEM-A"},
        {"from_value": 5, "to_value": 20, "result_item": "ITEM-B"},
    ]
    _assert_throws(lambda: _validate("result_item", overlap_item),
                   "chồng lấp", "result_item")


def test_cham_bien_khong_throw():
    rows = [
        {"from_value": 0, "to_value": 10, "result_value": 100},
        {"from_value": 10, "to_value": 20, "result_value": 200},
    ]
    _validate("result_value", rows)  # ⛔ được ném
    _dyn([
        {"from_value": 0, "to_value": 10, "result_item": "ITEM-A"},
        {"from_value": 10, "to_value": 20, "result_item": "ITEM-B"},
    ]).validate()


def test_khe_ho_msgprint_khong_throw():
    del MSGPRINTS[:]
    rows = [
        {"from_value": 0, "to_value": 24, "result_value": 100},
        {"from_value": 24.1, "to_value": 30, "result_value": 200},
    ]
    _validate("result_value", rows)  # ⛔ được ném

    assert len(MSGPRINTS) == 1, "khe hở phải cảnh báo đúng 1 lần: %s" % (MSGPRINTS,)
    message = MSGPRINTS[0]["message"]
    assert "KHE HỞ" in message, message
    assert "trả rỗng" in message, message
    assert "[24 – 24.1]" in message, message
    assert MSGPRINTS[0]["title"] == "Rule thử — Cảnh báo khe hở", (
        "tiêu đề cảnh báo phải nêu tên doctype: %r" % (MSGPRINTS[0]["title"],))


def test_lien_mach_khong_canh_bao_khe_ho():
    """Đối chứng dương: dải liền mạch ⇒ 0 cảnh báo khe hở."""
    del MSGPRINTS[:]
    _validate("result_value", [
        {"from_value": 0, "to_value": 10, "result_value": 100},
        {"from_value": 10, "to_value": 20, "result_value": 200},
    ])
    assert MSGPRINTS == [], "dải liền mạch mà vẫn cảnh báo: %s" % (MSGPRINTS,)


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
