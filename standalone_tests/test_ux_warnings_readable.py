# -*- coding: utf-8 -*-
"""UX vòng 3 — câu cảnh báo/lỗi phải ĐỌC ĐƯỢC (3 lỗi mức CHẶN).

BỐI CẢNH (UX1 chấm CHẶN, 2026-11-25)
────────────────────────────────────
  1. `ALBomSet._warn_rule_input_row` lấy TÊN BIẾN KỸ THUẬT làm nhãn khi quy
     tắc chưa có `input_label` ⇒ người dùng đọc "… tra theo total_thick_mm
     của từng dòng …". Tên biến ⛔ bao giờ được làm nhãn: rỗng hoặc trùng
     đúng tên biến ⇒ câu chung "dữ liệu quy tắc đọc".
  2. `alumglass.api.get_result_display` KHÔNG pass `item_selection_mode` ⇒
     nhánh `item_selection_mode === "Rule"` phía client là nhánh CHẾT: dòng
     chọn mã theo quy tắc mà thiếu mã sẽ hiện slug thay vì "Chưa tra được mã".
  3. Enum thô (CONSTANT/THRESHOLD/LOOKUP/NUMBER/ITEM) trong câu lỗi server
     ⇒ người dùng thấy "quy tắc THRESHOLD cần ít nhất 1 dòng".

Mỗi nhóm có ĐỐI CHỨNG ÂM (khôi phục hành vi cũ ⇒ phép kiểm phải đỏ), để
⛔ xanh giả khi ai đó revert bản vá.

VÌ SAO ĐẶT Ở `standalone_tests/` (NGOÀI package `alumglass/`)
──────────────────────────────────────────────────────────────
File stub `frappe` nằm trong package sẽ thay `sys.modules["frappe"]` khi
bench collect test ⇒ phá cả lượt chạy test của site. Xem docstring
`standalone_tests/test_phase_b_fbmax.py`.

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps:/home/nxc/myfrappe/apps/alumglass \\
        python3 standalone_tests/test_ux_warnings_readable.py
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_phase_b_fbmax as base  # noqa: E402  (cài stub `frappe` khi import)

STUB = base._STUB
api = base.api

from alumglass.al_bom_engine import formula_validate as fv  # noqa: E402
from alumglass.al_bom_engine.doctype.al_bom_set.al_bom_set import (  # noqa: E402
    ALBomSet,
)
from alumglass.al_formula_rules import rule_engine  # noqa: E402
from alumglass.al_formula_rules import rule_input  # noqa: E402
from alumglass.al_formula_rules.doctype.al_rule.al_rule import (  # noqa: E402
    ALRule,
    resolve_item,
)
import alumglass.engine.bom_orchestrator as eo  # noqa: E402


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
# Trợ giúp chung
# ═══════════════════════════════════════════════════════════════════
VAR = "total_thick_mm"

#: Enum THÔ ⛔ được xuất hiện trong bất kỳ câu nào người dùng đọc.
ENUM_WORDS = ("CONSTANT", "THRESHOLD", "LOOKUP", "NUMBER", "ITEM")

#: Tên field nội bộ ⛔ được lộ ra câu người dùng đọc.
INTERNAL_FIELDS = ("threshold_rows", "lookup_rows", "result_value",
                   "result_item", "input_variable", "constant_value")


def _assert_readable(message, label):
    """Câu người-dùng-đọc: ⛔ enum thô, ⛔ tên field nội bộ."""
    assert isinstance(message, str) and message.strip(), (
        "%s: câu rỗng" % label)
    for word in ENUM_WORDS:
        assert not re.search(r"\b%s\b" % word, message), (
            "%s: còn enum thô %r trong câu: %s" % (label, word, message))
    for field in INTERNAL_FIELDS:
        assert field not in message, (
            "%s: lộ tên field nội bộ %r: %s" % (label, field, message))


def _message(fn, label):
    """Chạy `fn` — trả câu lỗi đã throw (assert phải throw)."""
    try:
        fn()
    except STUB.ValidationError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 — phân biệt lỗi hạ tầng
        raise AssertionError(
            "%s: ném %s thay vì ValidationError: %s"
            % (label, type(exc).__name__, exc))
    raise AssertionError("%s: KHÔNG throw (dữ liệu sai vẫn lưu được)" % label)


# ═══════════════════════════════════════════════════════════════════
# (1) ALBomSet — cảnh báo "dòng chọn mã thiếu nguồn dữ liệu tra"
# ═══════════════════════════════════════════════════════════════════
def _rule_row(label="", scope="ROW", name="RULE-NEP", var=VAR):
    """1 dòng `AL Rule` như `load_rule_meta` trả (dict thường)."""
    return {
        "name": name,
        "rule_name": "Nẹp theo độ dày",
        "result_type": "ITEM",
        "is_active": 1,
        "input_variable": var,
        "input_scope": scope,
        "input_label": label,
    }


def _run_row_warning(rule_row, expr="", row_slug=""):
    """Dựng Bom Set 1 dòng Rule rồi chạy `_warn_rule_input_row`."""
    base._reset_stub()
    STUB.set_get_all("AL Rule", [rule_row])
    item = base.FakeDoc({
        "idx": 3,
        "slug": "nep_doc",
        "line_name": "Nẹp dọc",
        "item_selection_mode": "Rule",
        "item_rule": rule_row["name"],
        "rule_input_row": row_slug,
        "rule_input_expr": expr,
    })
    doc = ALBomSet()
    doc._data = {"name": "BOM-THU"}
    doc.items = [item]
    MSGPRINTS.clear()
    doc._warn_rule_input_row()
    assert len(MSGPRINTS) == 1, (
        "mong đúng 1 cảnh báo, nhận %d: %r" % (len(MSGPRINTS), MSGPRINTS))
    return MSGPRINTS[0]["message"]


def test_canh_bao_nhan_rong_khong_lo_ten_bien():
    """`input_label` RỖNG ⇒ "dữ liệu quy tắc đọc", ⛔ `total_thick_mm`."""
    message = _run_row_warning(_rule_row(label=""))
    assert "dữ liệu quy tắc đọc" in message, message
    assert VAR not in message, "câu cảnh báo phơi tên biến kỹ thuật: %s" % message
    assert "Nẹp theo độ dày" in message, (
        "câu vẫn phải nêu TÊN quy tắc để người dùng biết sửa cái nào: %s"
        % message)
    assert "chưa chọn dòng lấy dữ liệu" in message, message
    _assert_readable(message, "BOM Set — nhãn rỗng")


def test_canh_bao_nhan_trung_ten_bien_khong_lo_ten_bien():
    """`input_label` TRÙNG ĐÚNG tên biến (kể cả hoa/thường, khoảng trắng)."""
    for label in (VAR, VAR.upper(), "  %s  " % VAR):
        message = _run_row_warning(_rule_row(label=label))
        assert "dữ liệu quy tắc đọc" in message, (label, message)
        assert VAR not in message, (label, message)
        assert VAR.upper() not in message, (label, message)


def test_canh_bao_global_nhan_rong_khong_lo_ten_bien():
    """Nhánh GLOBAL (biểu thức nâng cao bị bỏ qua) cũng ⛔ phơi tên biến."""
    message = _run_row_warning(
        _rule_row(label="", scope="GLOBAL"),
        expr="items.nep_doc.glass_thick")
    assert "dữ liệu quy tắc đọc" in message, message
    assert VAR not in message, message
    assert "biểu thức" in message and "bị bỏ qua" in message, message


def test_canh_bao_giu_nhan_that_khi_co():
    """ĐỐI CHỨNG DƯƠNG: có nhãn người-đọc thật ⇒ giữ nguyên, ⛔ thay bằng câu chung."""
    message = _run_row_warning(_rule_row(label="Độ dày kính"))
    assert "Độ dày kính" in message, message
    assert "dữ liệu quy tắc đọc" not in message, message


def test_doi_chung_am_khoi_phuc_fallback_cu_thi_lo_ten_bien():
    """ĐỐI CHỨNG ÂM: trả lại fallback CŨ (`or var`) ⇒ câu LỘ tên biến.

    Chứng minh phép kiểm ở trên KHÔNG xanh giả: nếu ai revert bản vá, ca
    `test_canh_bao_nhan_rong_khong_lo_ten_bien` sẽ đỏ đúng vì tên biến.
    """
    original = rule_engine.rule_input_label

    def _old_fallback(rule):
        return ((rule.get("input_label") or "").strip()
                or rule.get("input_variable"))

    rule_engine.rule_input_label = _old_fallback
    try:
        message = _run_row_warning(_rule_row(label=""))
    finally:
        rule_engine.rule_input_label = original
    assert VAR in message, (
        "fallback cũ phải lộ %r — nếu không, đối chứng âm vô nghĩa: %s"
        % (VAR, message))


def test_rule_input_label_khong_bao_gio_tra_ten_bien():
    """Hàm dùng chung: mọi dạng "không có nhãn" ⇒ câu chung."""
    for label in ("", "   ", VAR, VAR.upper(), " %s " % VAR, None):
        got = rule_engine.rule_input_label(
            {"input_variable": VAR, "input_label": label})
        assert got == rule_engine.INPUT_LABEL_FALLBACK, (label, got)
    assert rule_engine.rule_input_label(
        {"input_variable": VAR, "input_label": "Độ dày kính"}) == "Độ dày kính"
    # Quy tắc chưa khai biến: ⛔ bịa nhãn — trả câu chung.
    assert rule_engine.rule_input_label({}) == rule_engine.INPUT_LABEL_FALLBACK


# ═══════════════════════════════════════════════════════════════════
# (2) get_result_display — đủ khoá cho client nhận ra DÒNG RULE
# ═══════════════════════════════════════════════════════════════════
RULE_LINE = {
    "slug": "nep_doc",
    "item_code": "",
    "item_selection_mode": "Rule",
    "line_label": "",
    "item_name": "",
    "width": 0, "height": 0, "qty": 0,
    "unit_qty": 0, "total_qty": 0, "unit_price": 0, "line_total": 0,
    "cost_bucket": "",
    "rule_trace": "Quy tắc tra theo Độ dày kính: chưa chọn dòng lấy dữ liệu.",
    "rule_input_label": "Độ dày kính",
    "rule_input_found": 0,
    "rule_input_missing": 0,
    "rule_source_missing": 1,
    "rule_missing_reason": "no_source_row",
}


def _display(payload):
    base._reset_stub()
    # Bảng slug RỖNG: nhãn `label` phải rỗng, ⛔ rơi về slug.
    STUB.set_get_all("AL Slug Library", [])
    STUB.set_get_all("AL Cost Bucket", [])
    STUB.set_doc("Quotation Item", "QI-RULE", {
        "al_bom_result": json.dumps(payload), "al_bom_vars": "{}",
    })
    original = api._require_quotation_item_permission
    api._require_quotation_item_permission = (
        lambda name, ptype="read": "QTN-1")
    try:
        return api.get_result_display("QI-RULE")
    finally:
        api._require_quotation_item_permission = original


def test_display_tra_item_selection_mode_va_co_thieu_nguon():
    """Dòng Rule: đủ `item_selection_mode` + cờ/reason đi ra NGUYÊN."""
    out = _display({"lines": [dict(RULE_LINE)], "buckets": {},
                    "cost_template": {}})
    line = out["lines"][0]
    assert line["item_selection_mode"] == "Rule", line
    assert line["rule_source_missing"] == 1, line
    assert line["rule_missing_reason"] == "no_source_row", line
    assert line["rule_input_label"] == "Độ dày kính", line
    assert line["rule_input_missing"] == 0, line
    assert line["rule_input_found"] is False, line
    # ⛔ slug làm nhãn: không có nhãn đọc được ⇒ "" cho client tự fallback.
    assert line["label"] == "", line
    assert line["label"] != "nep_doc", (
        "nhãn rơi về slug kỹ thuật: %r" % line["label"])
    assert line["line_label"] == "" and line["item_name"] == "", line


def test_display_giu_line_label_va_item_name_goc():
    """`line_label`/`item_name` là nguồn của `label` — phải đi ra nguyên."""
    payload = {"lines": [dict(RULE_LINE, line_label="Nẹp dọc",
                              item_name="Nẹp nhôm",
                              item_selection_mode="Fixed")],
               "buckets": {}, "cost_template": {}}
    line = _display(payload)["lines"][0]
    assert line["label"] == "Nẹp dọc", line
    assert line["line_label"] == "Nẹp dọc", line
    assert line["item_name"] == "Nẹp nhôm", line
    assert line["item_selection_mode"] == "Fixed", line


# ═══════════════════════════════════════════════════════════════════
# (3) Câu lỗi server — nhãn tiếng Việt thay enum thô
# ═══════════════════════════════════════════════════════════════════
def _make_rule(result_type="NUMBER", rule_type="THRESHOLD",
               threshold_rows=None, lookup_rows=None, constant_value=None):
    doc = ALRule()
    doc._data = {
        "is_active": 1,
        "rule_type": rule_type,
        "result_type": result_type,
        "constant_value": constant_value,
    }
    doc.rule_type = rule_type
    doc.result_type = result_type
    doc.constant_value = constant_value
    doc.threshold_rows = threshold_rows if threshold_rows is not None else []
    doc.lookup_rows = lookup_rows if lookup_rows is not None else []
    return doc


def test_loi_loai_ket_qua_dung_nhan_tieng_viet():
    message = _message(
        lambda: _make_rule(result_type="TEXT").validate(), "result_type lạ")
    _assert_readable(message, "result_type lạ")
    assert "\"Số\"" in message and "\"Mã vật tư\"" in message, message


def test_loi_kieu_quy_tac_dung_nhan_tieng_viet():
    message = _message(
        lambda: _make_rule(rule_type="MAGIC").validate(), "rule_type lạ")
    _assert_readable(message, "rule_type lạ")
    for label in ("Hằng số", "Tra theo dải", "Tra theo bảng"):
        assert label in message, (label, message)


def test_loi_hang_so_tra_ma_dung_nhan():
    message = _message(
        lambda: _make_rule(result_type="ITEM", rule_type="CONSTANT",
                           constant_value=1).validate(),
        "ITEM+CONSTANT")
    _assert_readable(message, "ITEM+CONSTANT")
    assert "Hằng số" in message and "Mã vật tư" in message, message
    assert "Tra theo dải" in message and "Tra theo bảng" in message, message


def test_loi_thieu_dong_dung_nhan_va_chi_dung_muc():
    message = _message(
        lambda: _make_rule(threshold_rows=[]).validate(), "THRESHOLD rỗng")
    _assert_readable(message, "THRESHOLD rỗng")
    assert "tra theo dải" in message, message
    assert "ít nhất 1 dòng điều kiện" in message, message
    # Việc cần làm: chỉ đúng MỤC trên form.
    assert "Bảng ngưỡng" in message, message

    message = _message(
        lambda: _make_rule(rule_type="LOOKUP", lookup_rows=[]).validate(),
        "LOOKUP rỗng")
    _assert_readable(message, "LOOKUP rỗng")
    assert "tra theo bảng" in message and "Bảng tra" in message, message


def test_loi_dong_thieu_cot_ket_qua_dung_nhan():
    message = _message(
        lambda: _make_rule(result_type="ITEM", rule_type="LOOKUP",
                           lookup_rows=[{"key_field": "K"}]).validate(),
        "thiếu result_item")
    _assert_readable(message, "thiếu result_item")
    assert "Mã vật tư" in message and "Loại kết quả" in message, message


def test_engine_dong_nguong_va_khe_ho_dung_nhan():
    """`rule_engine` — câu lỗi/cảnh báo dải cũng ⛔ enum thô."""
    cases = [
        ([{"from_value": 0, "to_value": 10}], "thiếu cột kết quả"),
        ([{"to_value": 10, "result_value": 1}], "thiếu Từ"),
        ([{"from_value": 20, "to_value": 10, "result_value": 1}],
         "Từ > Đến"),
        ([{"from_value": 0, "to_value": 10, "result_value": 1},
          {"from_value": 5, "to_value": 20, "result_value": 2}], "chồng lấp"),
    ]
    for rows, label in cases:
        message = _message(
            lambda rows=rows: rule_engine.validate_threshold_rows(
                rows, "result_value", "AL Rule"),
            label)
        _assert_readable(message, label)

    # Dải mở → cảnh báo KHE HỞ (msgprint, ⛔ throw).
    MSGPRINTS.clear()
    rule_engine.warn_threshold_gaps([
        {"from_value": 0, "to_value": 10, "result_value": 1},
        {"from_value": 11, "to_value": 20, "result_value": 2},
    ], "AL Rule — Cảnh báo khe hở")
    assert len(MSGPRINTS) == 1, MSGPRINTS
    message = MSGPRINTS[0]["message"]
    assert "KHE HỞ" in message, message
    assert "Threshold" not in message, message
    assert "`to`" not in message, (
        "câu cảnh báo lộ tên field `to`: %s" % message)
    _assert_readable(message, "cảnh báo khe hở")


def test_api_resolve_item_sai_loai_dung_nhan():
    base._reset_stub()
    STUB.set_doc("AL Rule", "RULE-GIA", {
        "result_type": "NUMBER", "rule_type": "CONSTANT",
        "rule_name": "Giá màu", "constant_value": 1,
    })
    message = _message(lambda: resolve_item("RULE-GIA", 5),
                       "resolve_item rule NUMBER")
    _assert_readable(message, "resolve_item rule NUMBER")
    assert "Giá màu" in message, message
    assert "Mã vật tư" in message, message


def test_doi_chung_am_anh_xa_nhan_bi_thay_bang_enum():
    """ĐỐI CHỨNG ÂM: đổi nhãn về chính enum ⇒ câu PHẢI lộ enum.

    Chứng minh câu lỗi dùng BẢNG NHÃN DÙNG CHUNG thật (⛔ phải câu viết
    tay đúng chữ), nên revert bảng nhãn là bị bắt ngay.
    """
    original = dict(rule_engine.RULE_TYPE_LABELS)
    rule_engine.RULE_TYPE_LABELS["THRESHOLD"] = "THRESHOLD"
    try:
        message = _message(
            lambda: _make_rule(threshold_rows=[]).validate(),
            "đối chứng âm nhãn")
    finally:
        rule_engine.RULE_TYPE_LABELS.clear()
        rule_engine.RULE_TYPE_LABELS.update(original)
    assert "THRESHOLD" in message.upper(), (
        "ánh xạ nhãn chưa được dùng để dựng câu: %s" % message)


# ═══════════════════════════════════════════════════════════════════
# (4) Nhãn dữ liệu đem tra — MỘT BẢN dùng chung (rule_input / engine)
# ═══════════════════════════════════════════════════════════════════
# Ba đường rò còn lại (2026-11-25): `rule_input.rule_input_config` điền nhãn
# bằng tên biến, `bom_orchestrator` chép tay chuỗi dự phòng, và
# `AL Rule.input_label` ĐÃ LƯU = tên biến đi thẳng ra `rule_input_label`
# (client hiển thị). Nay cả ba đi qua `rule_input.readable_input_label`.
def _set_var_library(rows):
    base._reset_stub()
    STUB.set_get_all("AL Variable Library", rows)


def _var_row(var_label):
    return {"name": VAR, "category": "Row Literals", "var_label": var_label}


def test_rule_input_config_nhan_du_phong_khi_thieu_nhan_doc_duoc():
    """`var_label` rỗng / trắng / trùng tên biến ⇒ nhãn dự phòng, ⛔ tên biến."""
    for var_label in ("", "   ", VAR, VAR.upper(), " %s " % VAR, None):
        _set_var_library([_var_row(var_label)])
        cfg = rule_input.rule_input_config(
            {"input_variable": VAR, "input_label": ""})
        assert cfg["input_label"] == rule_input.INPUT_LABEL_FALLBACK, (
            var_label, cfg)
        assert VAR not in cfg["input_label"], cfg
        assert VAR.upper() not in cfg["input_label"], cfg


def test_rule_input_config_giu_nhan_that_va_nhan_da_luu_trung_bien():
    """Nhãn thật giữ nguyên; nhãn ĐÃ LƯU sẵn = tên biến (dữ liệu cũ) ⛔ lọt."""
    _set_var_library([_var_row("Độ dày kính")])
    cfg = rule_input.rule_input_config(
        {"input_variable": VAR, "input_label": ""})
    assert cfg["input_label"] == "Độ dày kính", cfg

    cfg = rule_input.rule_input_config(
        {"input_variable": VAR, "input_label": VAR})
    assert cfg["input_label"] == rule_input.INPUT_LABEL_FALLBACK, cfg


def test_doi_chung_am_rule_input_config_quay_lai_or_var():
    """ĐỐI CHỨNG ÂM: trả `var_label or var` cũ ⇒ nhãn LỘ tên biến."""
    original = rule_input.readable_input_label

    def _old(label, var_name=""):
        return (str(label or "").strip() or str(var_name or "").strip())

    rule_input.readable_input_label = _old
    try:
        _set_var_library([_var_row("")])
        cfg = rule_input.rule_input_config(
            {"input_variable": VAR, "input_label": ""})
    finally:
        rule_input.readable_input_label = original
    assert cfg["input_label"] == VAR, cfg


def _light_rule_orch():
    """Orchestrator tối thiểu cho `_rule_trace_parts` (không chạy cả B1→B7)."""
    orch = object.__new__(eo.BomOrchestrator)
    orch.bom_items = [{"slug": "nep", "line_name": "Nẹp kính", "idx": 2}]
    orch.row_literals = {"nep": {"glass_thick": 8}}
    orch.inputs = {}
    orch._glass_data = {"nep": {"glass_thick": 8, "total_thick_mm": 8}}
    orch._resolved_rule_items = {}
    orch._rule_matches = {}
    orch._rule_names = {}
    orch._rule_meta = {}
    orch._item_names = {}
    orch._rule_input_cfg = {}
    return orch


RULE_TRACE_ITEM = {
    "slug": "nep", "item_rule": "RULE-NEP", "item_selection_mode": "Rule",
    "rule_input_row": "", "rule_input_expr": "",
}


def test_rule_trace_parts_nhan_da_luu_la_ten_bien_khong_lot():
    """`AL Rule.input_label` lưu là tên biến ⇒ `rule_input_label` đọc được."""
    orch = _light_rule_orch()
    orch._rule_input_cfg = {"RULE-NEP": {
        "input_variable": "glass_thick", "input_scope": "ROW",
        "input_label": "glass_thick"}}
    orch._rule_meta = {"RULE-NEP": {
        "rule_name": "Chọn nẹp", "input_label": "glass_thick",
        "input_variable": "glass_thick"}}

    parts = orch._rule_trace_parts(dict(RULE_TRACE_ITEM))
    assert parts["input_label"] == rule_input.INPUT_LABEL_FALLBACK, parts
    assert "glass_thick" not in parts["input_label"], parts

    flags = orch._rule_source_flags(parts, True)
    assert flags["rule_input_label"] == rule_input.INPUT_LABEL_FALLBACK, flags
    assert "glass_thick" not in flags["rule_input_label"], flags


def test_engine_meta_nhan_da_luu_la_ten_bien_khong_lot():
    """Đường THẬT: `_resolve_dynamic_item` đọc AL Rule có `input_label`=biến."""
    base._reset_stub()
    STUB.set_doc("AL Rule", "RULE-NEP", {
        "rule_name": "Chọn nẹp",
        "rule_type": "THRESHOLD",
        "result_type": "ITEM",
        "is_active": 1,
        "input_variable": "glass_thick",
        "input_scope": "ROW",
        "input_label": "glass_thick",
        "resolve": lambda value: "NEP-8",
    })
    orch = _light_rule_orch()
    orch._resolve_dynamic_item("RULE-NEP", 8)
    label = orch._rule_meta["RULE-NEP"]["input_label"]
    assert label == rule_input.INPUT_LABEL_FALLBACK, label
    assert "glass_thick" not in label, label


def test_doi_chung_am_engine_meta_quay_lai_or_var():
    """ĐỐI CHỨNG ÂM cho đường THẬT: `or var` cũ ⇒ `_rule_meta` giữ tên biến."""
    original = rule_input.readable_input_label

    def _old(label, var_name=""):
        return (str(label or "").strip() or str(var_name or "").strip())

    rule_input.readable_input_label = _old
    try:
        base._reset_stub()
        STUB.set_doc("AL Rule", "RULE-NEP", {
            "rule_name": "Chọn nẹp",
            "rule_type": "THRESHOLD",
            "result_type": "ITEM",
            "is_active": 1,
            "input_variable": "glass_thick",
            "input_scope": "ROW",
            "input_label": "glass_thick",
            "resolve": lambda value: "NEP-8",
        })
        orch = _light_rule_orch()
        orch._resolve_dynamic_item("RULE-NEP", 8)
    finally:
        rule_input.readable_input_label = original
    assert orch._rule_meta["RULE-NEP"]["input_label"] == "glass_thick"


def test_rule_engine_dung_chung_mot_ban_nhan():
    """`rule_engine` chỉ re-export hằng/hàm của `rule_input` (⛔ bản thứ hai)."""
    assert rule_engine.INPUT_LABEL_FALLBACK is rule_input.INPUT_LABEL_FALLBACK
    assert rule_engine.readable_input_label is rule_input.readable_input_label
    assert rule_engine.rule_input_label(
        {"input_variable": VAR, "input_label": VAR}
    ) == rule_input.INPUT_LABEL_FALLBACK


# ═══════════════════════════════════════════════════════════════════
# (5) `formula_validate.validate_lookup_rule_codes` — nhãn dòng
# ═══════════════════════════════════════════════════════════════════
# Câu cảnh báo `lookup_rule('MÃ')` MỘT tham số trên quy tắc ROW trước đây
# tự dựng nhãn `input_label or "dữ liệu của dòng"` ⇒ nhãn ĐÃ LƯU = tên biến
# (dữ liệu cũ điền tay) lọt ra người dùng. Nay qua hàm đọc-được dùng chung.
def _register_lookup_rules(rows):
    base._reset_stub()
    STUB.set_get_all("AL Rule", rows)


def _lookup_warning(rule):
    _register_lookup_rules([rule])
    warnings = fv.validate_lookup_rule_codes("lookup_rule('RULE-NEP')")
    assert len(warnings) == 1, warnings
    return warnings[0]


def _lookup_row_rule(**extra):
    row = {
        "name": "RULE-NEP", "rule_name": "Nẹp theo độ dày",
        "result_type": "NUMBER", "is_active": 1,
        "input_variable": VAR, "input_scope": "ROW", "input_label": "",
    }
    row.update(extra)
    return row


def test_lookup_rule_row_nhan_da_luu_la_ten_bien_khong_lot():
    message = _lookup_warning(_lookup_row_rule(input_label=VAR))
    assert "dữ liệu quy tắc đọc" in message, message
    assert VAR not in message, "câu cảnh báo phơi tên biến: %s" % message
    assert "TỪNG DÒNG" in message, message
    assert "<b>Chọn dòng lấy dữ liệu</b>" in message, message


def test_lookup_rule_row_nhan_rong_dung_cau_chung():
    """Nhãn rỗng ⇒ câu chung (trước đây là "dữ liệu của dòng")."""
    message = _lookup_warning(_lookup_row_rule(input_label=""))
    assert "dữ liệu quy tắc đọc" in message, message
    assert "dữ liệu của dòng" not in message, message


def test_lookup_rule_row_nhan_that_giu_nguyen():
    """ĐỐI CHỨNG DƯƠNG: nhãn người dùng đặt ⇒ giữ nguyên."""
    message = _lookup_warning(_lookup_row_rule(input_label="Độ dày kính"))
    assert "Độ dày kính" in message, message
    assert "dữ liệu quy tắc đọc" not in message, message


def test_lookup_rule_chua_khai_bien_giu_nguyen_hanh_vi_cu():
    """Đường LEGACY (chưa khai biến) ⛔ bị đổi câu: nhánh riêng, ⛔ nhãn."""
    message = _lookup_warning(_lookup_row_rule(
        input_variable="", input_scope="", input_label=""))
    assert "chưa khai tra theo dữ liệu nào" in message, message
    assert "dữ liệu quy tắc đọc" not in message, message
    assert "MỘT tham số" in message, message


def test_doi_chung_am_lookup_rule_nhan_quay_lai_fallback_cu():
    """ĐỐI CHỨNG ÂM: trả `input_label or "dữ liệu của dòng"` cũ ⇒ lộ tên biến."""
    original = rule_input.readable_input_label

    def _old(label, var_name=""):
        return str(label or "").strip() or "dữ liệu của dòng"

    rule_input.readable_input_label = _old
    try:
        message = _lookup_warning(_lookup_row_rule(input_label=VAR))
    finally:
        rule_input.readable_input_label = original
    assert VAR in message, (
        "fallback cũ phải lộ %r — nếu không, đối chứng âm vô nghĩa: %s"
        % (VAR, message))


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
            passed += 1
            print("  PASS  %s" % name)
        except Exception:
            failed.append(name)
            print("  FAIL  %s" % name)
            traceback.print_exc()
    print("\n%s" % ("=" * 60))
    print("  TOTAL: %d  PASS: %d  FAIL: %d" % (len(funcs), passed, len(failed)))
    if failed:
        print("  FAILED: %s" % failed)
        raise SystemExit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _main()
