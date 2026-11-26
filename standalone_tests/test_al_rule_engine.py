# -*- coding: utf-8 -*-
"""CHẶNG 2B — engine + API đọc `AL Rule` và GÁC LOẠI kết quả.

BỐI CẢNH
────────
`AL Rule` gộp cả rule trả SỐ (NUMBER) và rule trả MÃ VẬT TƯ (ITEM) về một
DocType, cột kết quả do `result_type` quyết định (hai doctype rule song song
trước đây đã bị xoá 2026-11-23). Chỗ đọc chỉ tra theo mã nên một rule SAI
LOẠI lọt vào đúng ô là chuyện có thật: công thức `lookup_rule()` trỏ vào
rule chọn mã ⇒ nhận chuỗi mã hoặc 0; ô Item Rule trỏ vào rule tính giá ⇒
dòng hàng mất mã.

Bộ test này chứng minh:
  (1) `_lookup_rule` gặp rule ITEM ⇒ cảnh báo `lookup_rule_sai_loai:*` + 0;
  (2) `_resolve_dynamic_item` gặp rule NUMBER ⇒ cảnh báo
      `dynamic_rule_sai_loai:*` + None;
  (3) fallback CONSTANT cho system variable CHỈ nhận rule NUMBER
      (rule ITEM không được ghi vào `self.inputs`);
  (4) API `resolve_item_rule` gặp rule NUMBER ⇒ throw câu người-đọc-được;
  (5) giữ nguyên hành vi cũ: rule TẮT ⇒ `*_da_tat`; mã sai ⇒ `*_thieu_ma`;
  (5b) rule ĐANG BẬT nhưng KHÔNG khớp dòng nào ⇒ cảnh báo
      `lookup_rule_khong_khop:*` + tạm tính 0 (⛔ trả 0 im lặng), và đối
      chứng dương: khớp dòng có kết quả 0 THẬT ⇒ KHÔNG cảnh báo;
  (5c) cùng ca đó cho rule chọn MÃ ⇒ cảnh báo `dynamic_rule_khong_khop:*`
      + None (⛔ im lặng để dòng hàng mất mã mà banner trống);
  (6) ĐỐI CHỨNG DƯƠNG: đúng loại ⇒ trả giá trị, KHÔNG cảnh báo.

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_al_rule_engine.py
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
FakeDoc = base.FakeDoc

import alumglass.engine.bom_orchestrator as engine_mod  # noqa: E402
from alumglass.al_bom_engine import system_variable_resolver as svr  # noqa: E402
from alumglass.al_formula_rules.doctype.al_rule.al_rule import (  # noqa: E402
    ALRule,
)


# ═══════════════════════════════════════════════════════════════════
# Stub bổ sung — throw đúng lớp, quyền luôn cho qua
# ═══════════════════════════════════════════════════════════════════
def _throw(*args, **kwargs):
    exc_type = kwargs.get("exc")
    for arg in args[1:]:
        if isinstance(arg, type) and issubclass(arg, BaseException):
            exc_type = arg
    message = args[0] if args else "frappe.throw"
    raise (exc_type or STUB.ValidationError)(message)


STUB.throw = _throw
STUB.has_permission = lambda *a, **k: True


class _CachedDocPatch(object):
    """Thay `frappe.get_cached_doc` bằng 1 doc cho sẵn (hoặc báo thiếu)."""

    def __init__(self, doc=None, missing=False):
        self.doc = doc
        self.missing = missing
        self._original = None

    def __enter__(self):
        self._original = STUB.get_cached_doc
        patch = self

        def _get_cached_doc(doctype, name):
            if patch.missing:
                raise STUB.DoesNotExistError(
                    "%s %s không tồn tại" % (doctype, name))
            return patch.doc

        STUB.get_cached_doc = _get_cached_doc
        return self

    def __exit__(self, *exc_info):
        STUB.get_cached_doc = self._original
        return False


class _WarningSpy(object):
    """Thu cảnh báo engine thay vì ghi vào `frappe.local`."""

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


def _rule_doc(result_type, rule_type="THRESHOLD", active=1, result=None,
              rule_type_attr=None):
    """Doc rule tối thiểu: `.get()` cho `result_type`, attr cho `rule_type`."""
    data = {
        "rule_name": "Rule thử",
        "result_type": result_type,
        "rule_type": rule_type_attr or rule_type,
        "is_active": active,
        "constant_value": 48,
    }
    doc = FakeDoc(data, "RULE-THU")
    doc.result_type = result_type
    doc.rule_type = data["rule_type"]
    doc.is_active = active
    doc.constant_value = 48
    doc.resolve = (lambda value: result) if result is not None \
        else (lambda value: None)
    return doc


def _dynamic_self():
    return types.SimpleNamespace(
        # `_rule_meta`: nhãn tự mô tả của AL Rule (input_label/output_label/
        # rule_description) mà `_resolve_dynamic_item` cache song song với
        # `_rule_names` — doc giả phải có đủ 2 map như instance thật.
        _rule_names={}, _rule_meta={}, _rule_matches={},
        # `_describe_rule_match` là staticmethod của class — doc giả không có
        # threshold_rows nên trả "" (đúng nhánh không mô tả được dòng khớp).
        _describe_rule_match=lambda doc, value: "")


# ═══════════════════════════════════════════════════════════════════
# (1) _lookup_rule — GÁC LOẠI
# ═══════════════════════════════════════════════════════════════════
def test_lookup_rule_gap_rule_item_tra_0_va_canh_bao():
    rule = _rule_doc("ITEM", result="C3209-20")
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-NEP", 8)

    assert value == 0, (
        "rule chọn mã lọt vào công thức phải tạm tính 0, nhận %r" % (value,))
    key = "lookup_rule_sai_loai:RULE-NEP"
    assert key in spy.warnings, (
        "rule SAI LOẠI mà không cảnh báo ⇒ người dùng tưởng giá đúng: %s"
        % (spy.warnings,))
    message = spy.warnings[key]
    assert "chọn mã vật tư" in message, message
    assert "tạm tính 0" in message, message
    # UX: câu cảnh báo nêu TÊN quy tắc, ⛔ phơi `rule_code` nội bộ.
    assert "Rule thử" in message, (
        "câu cảnh báo ⛔ nêu tên quy tắc (người dùng không biết sửa cái nào): %s"
        % message)
    assert "RULE-NEP" not in message, (
        "câu cảnh báo phơi mã nội bộ ra nhân viên báo giá: %s" % message)


def test_lookup_rule_dung_loai_number_tra_so_khong_canh_bao():
    """Đối chứng dương: rule NUMBER ⇒ trả giá trị, 0 cảnh báo."""
    rule = _rule_doc("NUMBER", result=42)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-SO", 5)

    assert value == 42, value
    assert spy.warnings == {}, spy.warnings


# ═══════════════════════════════════════════════════════════════════
# (2) _resolve_dynamic_item — GÁC LOẠI
# ═══════════════════════════════════════════════════════════════════
def test_dynamic_item_gap_rule_number_tra_none_va_canh_bao():
    rule = _rule_doc("NUMBER", result=100)
    orch = _dynamic_self()
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            orch, "RULE-GIA", 8)

    assert value is None, (
        "rule tính giá trị lọt vào ô chọn mã phải trả None, nhận %r"
        % (value,))
    key = "dynamic_rule_sai_loai:RULE-GIA"
    assert key in spy.warnings, (
        "rule SAI LOẠI mà không cảnh báo ⇒ dòng hàng mất mã âm thầm: %s"
        % (spy.warnings,))
    message = spy.warnings[key]
    assert "quy tắc tính giá trị" in message, message
    assert "không phải quy tắc chọn mã" in message, message
    # UX: hậu quả + lối xử lý + tên quy tắc (⛔ mã nội bộ).
    assert "tạm không có mã vật tư" in message, message
    assert "Báo quản trị sửa ô Item Rule" in message, message
    assert "Rule thử" in message, message
    assert "RULE-GIA" not in message, (
        "câu cảnh báo phơi mã nội bộ ra nhân viên báo giá: %s" % message)


def test_dynamic_item_dung_loai_item_tra_ma_khong_canh_bao():
    """Đối chứng dương: rule ITEM ⇒ trả mã + cache tên, 0 cảnh báo."""
    rule = _rule_doc("ITEM", result="C3209-20")
    orch = _dynamic_self()
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            orch, "RULE-NEP", 8)

    assert value == "C3209-20", value
    assert spy.warnings == {}, spy.warnings
    assert orch._rule_names["RULE-NEP"] == "Rule thử", orch._rule_names


# ═══════════════════════════════════════════════════════════════════
# (3) Fallback CONSTANT cho system variable — CHỈ nhận rule NUMBER
# ═══════════════════════════════════════════════════════════════════
def _resolve_fallback(rule_doc):
    """Chạy `_resolve_system_variables` với nguồn tối thiểu → trả inputs."""
    orch = object.__new__(engine_mod.BomOrchestrator)
    orch.inputs = {}
    orch._profile_child_vars = {}
    orch.profile_system_override = None
    orch._get_bom_set = lambda: types.SimpleNamespace(name="BOM-THU")

    system_vars = [{"var_name": "OFFSET_FRAME", "default_value": None}]
    original = (svr.fetch_system_vars, svr.resolve_source_record_names,
                svr.resolve_system_variable_values)
    svr.fetch_system_vars = lambda extra_fields=None: system_vars
    svr.resolve_source_record_names = lambda *a, **k: {}
    svr.resolve_system_variable_values = lambda *a, **k: {}
    try:
        with _CachedDocPatch(rule_doc):
            orch._resolve_system_variables()
    finally:
        (svr.fetch_system_vars, svr.resolve_source_record_names,
         svr.resolve_system_variable_values) = original
    return orch.inputs


def test_fallback_constant_bo_qua_rule_item():
    rule = _rule_doc("ITEM", rule_type="CONSTANT", result=None)
    inputs = _resolve_fallback(rule)
    assert "OFFSET_FRAME" not in inputs, (
        "rule chọn mã bị dùng làm GIÁ TRỊ biến ⇒ sai loại mà không ai thấy: %r"
        % (inputs,))


def test_fallback_constant_nhan_rule_number():
    """Đối chứng dương: rule NUMBER CONSTANT vẫn là fallback như cũ."""
    rule = _rule_doc("NUMBER", rule_type="CONSTANT")
    inputs = _resolve_fallback(rule)
    assert inputs.get("OFFSET_FRAME") == 48, inputs


# ═══════════════════════════════════════════════════════════════════
# (4) API `resolve_item_rule` — GÁC LOẠI
# ═══════════════════════════════════════════════════════════════════
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
    raise AssertionError("%s: KHÔNG throw (sai loại vẫn trả kết quả)" % label)


def test_api_resolve_item_rule_gap_rule_number_throw():
    from alumglass.api import resolve_item_rule

    rule = _rule_doc("NUMBER", result=100)
    with _CachedDocPatch(rule):
        message = _assert_throws(
            lambda: resolve_item_rule("RULE-GIA", 8),
            "không phải quy tắc chọn mã", "API rule NUMBER")

    assert "Rule thử" in message, (
        "câu lỗi phải NÊU TÊN quy tắc để người dùng biết sửa cái nào: %s"
        % message)
    # UX vòng 3: câu cho người dùng dùng NHÃN tiếng Việt, ⛔ phơi enum ITEM.
    assert "Mã vật tư" in message, message
    assert "ITEM" not in message, message


def test_api_resolve_item_rule_dung_loai_tra_hop_dong_cu():
    """Đối chứng dương: giữ NGUYÊN hình dạng trả `{item_code, item_name}`."""
    from alumglass.api import resolve_item_rule

    rule = _rule_doc("ITEM", result="C3209-20")
    STUB.set_doc("Item", "C3209-20", {"item_name": "Nẹp kính 10.38mm"})
    with _CachedDocPatch(rule):
        result = resolve_item_rule("RULE-NEP", 8)

    assert result == {"item_code": "C3209-20",
                      "item_name": "Nẹp kính 10.38mm"}, result


# ═══════════════════════════════════════════════════════════════════
# (5) Giữ nguyên hành vi cũ — TẮT / THIẾU MÃ
# ═══════════════════════════════════════════════════════════════════
def test_lookup_rule_da_tat_canh_bao_va_tra_0():
    rule = _rule_doc("NUMBER", active=0, result=None)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-TAT", 5)

    assert value == 0, value
    assert "lookup_rule_da_tat:RULE-TAT" in spy.warnings, spy.warnings
    assert "lookup_rule_khong_khop:RULE-TAT" not in spy.warnings, (
        "rule TẮT đã có cảnh báo riêng — ⛔ báo chồng thêm 'không khớp': %s"
        % (spy.warnings,))


# ═══════════════════════════════════════════════════════════════════
# (5b) Rule ĐANG BẬT nhưng KHÔNG khớp dòng nào ⇒ ⛔ trả 0 im lặng
# ═══════════════════════════════════════════════════════════════════
def test_lookup_rule_bat_khong_khop_canh_bao_va_tra_0():
    """Rule bật, không dòng nào khớp giá trị tra ⇒ cảnh báo + 0.

    Trước bản vá, `_lookup_rule` rơi thẳng về 0 trong im lặng ⇒ nhân viên báo
    giá tưởng giá đúng, thành tiền hụt mà không ai biết vì sao.
    """
    rule = _rule_doc("NUMBER", active=1, result=None)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-KHONG-KHOP", 999)

    assert value == 0, value
    key = "lookup_rule_khong_khop:RULE-KHONG-KHOP"
    assert key in spy.warnings, (
        "rule bật mà không khớp dòng nào ⇒ phải cảnh báo, nhận: %s"
        % (spy.warnings,))
    message = spy.warnings[key]
    assert "không có dòng nào khớp" in message, message
    assert "tạm tính 0" in message, message
    assert "thành tiền chưa đúng" in message, message
    assert "Báo quản trị kiểm tra lại dải/bảng tra" in message, message
    # ⛔ phơi mã nội bộ, và ⛔ báo chồng cảnh báo "đã tắt".
    assert "Rule thử" in message, message
    assert "RULE-KHONG-KHOP" not in message, (
        "câu cảnh báo phơi mã nội bộ: %s" % message)
    assert "lookup_rule_da_tat:RULE-KHONG-KHOP" not in spy.warnings, spy.warnings


def test_lookup_rule_khop_tra_0_that_khong_canh_bao():
    """Đối chứng DƯƠNG: khớp dòng có kết quả 0 THẬT ⇒ trả 0, KHÔNG cảnh báo.

    Phân biệt "không khớp" với "khớp nhưng kết quả bằng 0" — gộp hai ca này
    là báo nhầm, đúng lỗi mà bản vá phải tránh.
    """
    rule = _rule_doc("NUMBER", active=1, result=0)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-KHOP-0", 5)

    assert value == 0, value
    assert spy.warnings == {}, (
        "kết quả 0 THẬT (khớp dòng) ⛔ bị báo nhầm là không khớp: %s"
        % (spy.warnings,))


def test_dynamic_rule_da_tat_canh_bao_va_tra_none():
    rule = _rule_doc("ITEM", active=0, result=None)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            _dynamic_self(), "RULE-DYN-TAT", 5)

    assert value is None, value
    assert "dynamic_rule_da_tat:RULE-DYN-TAT" in spy.warnings, spy.warnings
    assert "dynamic_rule_khong_khop:RULE-DYN-TAT" not in spy.warnings, (
        "rule TẮT đã có cảnh báo riêng — ⛔ báo chồng thêm 'không khớp': %s"
        % (spy.warnings,))


# ═══════════════════════════════════════════════════════════════════
# (5c) Rule chọn MÃ đang BẬT nhưng KHÔNG khớp dòng nào ⇒ ⛔ None im lặng
# ═══════════════════════════════════════════════════════════════════
def test_dynamic_rule_khong_khop_canh_bao_va_tra_none():
    """Bang cảnh báo phải thấy được, ⛔ chỉ nằm trong `rule_trace`.

    Trước bản vá, nhánh này `return None` im lặng: dòng hàng mất mã vật tư ⇒
    giá 0, mà banner trống (câu "không có mã nào khớp" chỉ nằm trong trace,
    phải bấm "Vì sao ra số này?" mới thấy).
    """
    rule = _rule_doc("ITEM", active=1, result=None)
    with _CachedDocPatch(rule), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            _dynamic_self(), "RULE-KHONG-KHOP", 8)

    assert value is None, value
    key = "dynamic_rule_khong_khop:RULE-KHONG-KHOP"
    assert key in spy.warnings, (
        "rule BẬT mà không khớp dòng nào ⇒ phải cảnh báo, nhận: %s"
        % (spy.warnings,))
    message = spy.warnings[key]
    assert "không có dòng nào khớp" in message, message
    assert "tạm không có mã vật tư" in message, message
    assert "thành tiền chưa đúng" in message, message
    assert "Báo quản trị kiểm tra lại dải/bảng tra" in message, message
    # ⛔ phơi mã nội bộ, và ⛔ báo chồng cảnh báo "đã tắt".
    assert "Rule thử" in message, message
    assert "RULE-KHONG-KHOP" not in message, (
        "câu cảnh báo phơi mã nội bộ: %s" % message)
    assert "dynamic_rule_da_tat:RULE-KHONG-KHOP" not in spy.warnings, spy.warnings


def test_lookup_rule_thieu_ma_canh_bao_va_tra_0():
    with _CachedDocPatch(missing=True), _WarningSpy() as spy:
        value = engine_mod._lookup_rule("RULE-MAT", 5)

    assert value == 0, value
    assert "lookup_rule_thieu_ma:RULE-MAT" in spy.warnings, spy.warnings


def test_dynamic_rule_thieu_ma_canh_bao_va_tra_none():
    with _CachedDocPatch(missing=True), _WarningSpy() as spy:
        value = engine_mod.BomOrchestrator._resolve_dynamic_item(
            _dynamic_self(), "RULE-MAT", 5)

    assert value is None, value
    assert "dynamic_rule_thieu_ma:RULE-MAT" in spy.warnings, spy.warnings


# ═══════════════════════════════════════════════════════════════════
# (6) Controller `AL Rule` — `resolve()` chỉ trả cột đúng `result_type`
# ═══════════════════════════════════════════════════════════════════
def test_controller_item_rule_khong_tra_cot_so():
    doc = ALRule()
    doc._data = {"result_type": "ITEM", "rule_type": "THRESHOLD",
                 "is_active": 1}
    doc.result_type = "ITEM"
    doc.rule_type = "THRESHOLD"
    doc.threshold_rows = [
        {"from_value": 0, "to_value": 10, "result_item": "NEP-8"}]
    assert doc.resolve(8) == "NEP-8", doc.resolve(8)


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
            print("        " + traceback.format_exc().strip().replace(
                "\n", "\n        "))
            failed.append(name)
    print("\n" + "=" * 60)
    print("  TOTAL: %d  PASS: %d  FAIL: %d" % (len(funcs), passed, len(failed)))
    if failed:
        print("  FAILED: %s" % (failed,))
        sys.exit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _main()
