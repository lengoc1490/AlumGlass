# -*- coding: utf-8 -*-
"""Standalone test — "AL Rule tự mô tả" phần SERVER.

Phủ:
  (1) `ALRule.preview()` — hợp đồng `docs/design/tra-cuu-quy-tac-de-hieu.md`
      §3.2 cho THRESHOLD (khớp giữa / biên / khe hở / rule tắt / không có
      dòng), LOOKUP (khoá khớp / khoá không khớp), ITEM (item_code + tên),
      CONSTANT.
  (2) `formula_validate.validate_lookup_rule_codes()` — mã đúng / mã sai /
      rule tắt / sai result_type / tham số không phải literal (⛔ cảnh báo) /
      nhiều lời gọi trong 1 biểu thức.
  (3) Câu trace dùng `input_label` của quy tắc (thay tên field kỹ thuật).

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_rule_preview.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_phase_b_fbmax as base  # noqa: E402  (cài stub `frappe` khi import)

STUB = base._STUB

from alumglass.al_bom_engine import formula_validate as fv  # noqa: E402
from alumglass.al_formula_rules.doctype.al_rule.al_rule import (  # noqa: E402
    ALRule,
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
    raise (exc_type or STUB.ValidationError)(args[0] if args else "frappe.throw")


STUB.throw = _throw

MSGPRINTS = []


def _msgprint(message, **kwargs):
    MSGPRINTS.append({"message": message, "title": kwargs.get("title")})


STUB.msgprint = _msgprint


# ═══════════════════════════════════════════════════════════════════
# Dựng AL Rule cho test
# ═══════════════════════════════════════════════════════════════════
def _rule(rule_type="THRESHOLD", result_type="NUMBER", active=1,
          threshold_rows=None, lookup_rows=None, constant_value=None,
          **extra):
    """ALRule thật (controller) nhưng nạp bằng dict — không cần site."""
    data = {
        "rule_code": extra.pop("rule_code", "RULE-NEP-GLASSTHICK"),
        "rule_name": extra.pop("rule_name", "Chọn nẹp theo độ dày kính"),
        "rule_description": extra.pop(
            "rule_description", "Chọn mã nẹp theo độ dày kính"),
        "input_label": extra.pop("input_label", "Độ dày kính"),
        "input_unit": extra.pop("input_unit", "mm"),
        "output_label": extra.pop("output_label", "Mã nẹp"),
        "is_active": active,
        "rule_type": rule_type,
        "result_type": result_type,
        "constant_value": constant_value,
        "threshold_rows": list(threshold_rows or []),
        "lookup_rows": list(lookup_rows or []),
    }
    data.update(extra)
    doc = ALRule()
    doc._data = data
    # Stub `Document` không có __getattr__ ⇒ gán thuộc tính thật (như
    # test_al_rule.py đang làm).
    for key, value in data.items():
        setattr(doc, key, value)
    return doc


#: Rule mẫu có KHE 10,38 – 10,39 (đúng kiểu dữ liệu cũ cần cảnh báo).
THRESHOLD_ROWS = [
    {"from_value": 0, "to_value": 10.38, "result_value": 100},
    {"from_value": 10.39, "to_value": 17, "result_value": 200},
    {"from_value": 17, "to_value": 20, "result_value": 300},
]


def _threshold_rule(**kwargs):
    return _rule(threshold_rows=THRESHOLD_ROWS, result_type="NUMBER", **kwargs)


# ═══════════════════════════════════════════════════════════════════
# (1) preview — THRESHOLD
# ═══════════════════════════════════════════════════════════════════
def test_preview_threshold_khop_dai_giua():
    out = _threshold_rule().preview(12)
    assert out["success"] is True, out
    assert out["matched"] == {"kind": "range", "from": 10.39, "to": 17,
                             "key": None}, out["matched"]
    assert out["result"] == {"value": 200}, out["result"]
    assert out["message"] == "", out["message"]
    # Bảng đủ để client vẽ + tô đúng dòng khớp.
    assert len(out["rows"]) == 3, out["rows"]
    assert [row["is_match"] for row in out["rows"]] == [0, 1, 0], out["rows"]
    assert out["rows"][1]["result_text"] == "200", out["rows"][1]
    # Nhãn tự mô tả đi kèm hợp đồng.
    assert out["input_label"] == "Độ dày kính", out
    assert out["input_unit"] == "mm", out
    assert out["output_label"] == "Mã nẹp", out
    assert out["rule_description"] == "Chọn mã nẹp theo độ dày kính", out


def test_preview_threshold_khop_bien():
    rule = _threshold_rule()
    # `to` của dải 1 (10.38) → lưới tương thích dữ liệu cũ (biên trên ĐÓNG).
    out = rule.preview(10.38)
    assert out["matched"]["from"] == 0 and out["matched"]["to"] == 10.38, out
    assert out["result"] == {"value": 100}, out
    # `from` của dải 2 → nửa mở.
    out = rule.preview(10.39)
    assert out["matched"]["from"] == 10.39, out
    # 17 = from dải 3 (chạm biên, dải TRÊN thắng).
    out = rule.preview(17)
    assert out["matched"]["from"] == 17 and out["matched"]["to"] == 20, out
    assert out["result"] == {"value": 300}, out


def test_preview_threshold_khe_ho_n_ro_dai_trong():
    """10,385 rơi vào khe 10,38 – 10,39 ⇒ câu nêu ĐÚNG dải trống."""
    out = _threshold_rule().preview(10.385)
    assert out["success"] is True, out
    assert out["matched"] is None, out["matched"]
    assert out["result"] is None, out["result"]
    assert "10,38" in out["message"] and "10,39" in out["message"], out["message"]
    assert "trống" in out["message"], out["message"]
    # ⛔ không phơi mã kỹ thuật của rule/mã quy tắc.
    assert "RULE-" not in out["message"], out["message"]
    # Bảng vẫn đủ để client vẽ, không dòng nào được tô.
    assert [row["is_match"] for row in out["rows"]] == [0, 0, 0], out["rows"]


def test_preview_threshold_ngoai_dai_cao_nhat():
    out = _threshold_rule().preview(20.5)
    assert out["matched"] is None, out
    assert "20,5" in out["message"] and "dải cao nhất" in out["message"], \
        out["message"]


def test_preview_threshold_nho_hon_dai_thap_nhat():
    out = _threshold_rule().preview(-1)
    assert out["matched"] is None, out
    assert "dải thấp nhất" in out["message"], out["message"]


def test_preview_threshold_khong_phai_so():
    out = _threshold_rule().preview("abc")
    assert out["success"] is True, out
    assert out["matched"] is None, out
    assert "không phải là số" in out["message"], out["message"]


def test_preview_nhan_dau_phay_thap_phan_kieu_viet():
    """Ô "Thử tra" là ô CHỮ ⇒ người dùng gõ `12,5`/`10,385` phải hiểu đúng."""
    rule = _threshold_rule()
    out = rule.preview("12,5")
    assert out["matched"] is not None, out
    assert out["result"] == {"value": 200}, out["result"]

    out = rule.preview("10,385")
    assert "10,38" in out["message"] and "10,39" in out["message"], \
        out["message"]


def test_preview_nhan_dau_cham_phan_cach_nghin_kieu_viet():
    """`2.000,5` = 2000,5 (dấu chấm phân cách nghìn) — không phải 2,0005."""
    out = _threshold_rule().preview("2.000,5")
    assert out["matched"] is None, out
    assert "2000,5" in out["message"], out["message"]
    assert "dải cao nhất" in out["message"], out["message"]


def test_preview_chua_nhap_gia_tri():
    out = _threshold_rule().preview()
    assert out["success"] is True, out
    assert out["matched"] is None and out["result"] is None, out
    assert "Độ dày kính" in out["message"], out["message"]


def test_preview_rule_tat_van_tra_duoc_bang():
    out = _threshold_rule(active=0).preview(12)
    assert out["success"] is True, out
    assert out["is_active"] == 0, out
    assert out["matched"] is None and out["result"] is None, out
    assert "đang tắt" in out["message"], out["message"]
    # Câu chỉ đúng ô cần bật — nhãn phải là nhãn ĐANG CÓ trên form.
    assert "Đang dùng?" in out["message"], out["message"]
    # Vẫn trả bảng để quản trị thấy cấu hình hiện có.
    assert len(out["rows"]) == 3, out["rows"]
    assert [row["is_match"] for row in out["rows"]] == [0, 0, 0], out["rows"]


def test_preview_rule_khong_co_dong():
    out = _rule(threshold_rows=[]).preview(5)
    assert out["success"] is True, out
    assert out["rows"] == [], out
    assert "chưa có dòng ngưỡng" in out["message"], out["message"]
    # Mục cần mở phải gọi bằng nhãn trên form ("Bảng ngưỡng").
    assert "Bảng ngưỡng" in out["message"], out["message"]


# ═══════════════════════════════════════════════════════════════════
# (1b) preview — LOOKUP
# ═══════════════════════════════════════════════════════════════════
LOOKUP_ROWS = [
    {"key_field": "LOWE", "result_value": 1.5},
    {"key_field": "HIGH", "result_value": 2.5},
]


def test_preview_lookup_khoa_khop():
    out = _rule(rule_type="LOOKUP", lookup_rows=LOOKUP_ROWS).preview("HIGH")
    assert out["matched"] == {"kind": "key", "from": None, "to": None,
                             "key": "HIGH"}, out["matched"]
    assert out["result"] == {"value": 2.5}, out["result"]
    assert [row["is_match"] for row in out["rows"]] == [0, 1], out["rows"]
    assert out["rows"][0]["key"] == "LOWE", out["rows"][0]


def test_preview_lookup_khoa_khong_khop_neu_khoa_dang_co():
    out = _rule(rule_type="LOOKUP", lookup_rows=LOOKUP_ROWS).preview("MID")
    assert out["success"] is True, out
    assert out["matched"] is None and out["result"] is None, out
    assert "MID" in out["message"], out["message"]
    assert "LOWE" in out["message"] and "HIGH" in out["message"], out["message"]


def test_preview_lookup_khong_phan_biet_so_va_chuoi():
    """Dữ liệu form có thể là số/chuỗi — so khớp như `resolve()`."""
    out = _rule(rule_type="LOOKUP", lookup_rows=[
        {"key_field": "10", "result_value": 7},
    ]).preview(10)
    assert out["result"] == {"value": 7}, out


# ═══════════════════════════════════════════════════════════════════
# (1c) preview — ITEM + CONSTANT
# ═══════════════════════════════════════════════════════════════════
ITEM_ROWS = [
    {"from_value": 0, "to_value": 10, "result_item": "C3209-20"},
    {"from_value": 10, "to_value": 20, "result_item": "C3210-20"},
]


def test_preview_item_tra_ma_va_ten():
    base._reset_stub()
    STUB.set_doc("Item", "C3209-20", {"item_name": "Nẹp nhôm 10mm"})
    STUB.set_doc("Item", "C3210-20", {"item_name": "Nẹp nhôm 12mm"})

    out = _rule(result_type="ITEM", threshold_rows=ITEM_ROWS).preview(8)
    assert out["result"] == {
        "item_code": "C3209-20", "item_name": "Nẹp nhôm 10mm"}, out["result"]
    assert out["rows"][0]["result_text"] == "Nẹp nhôm 10mm (C3209-20)", \
        out["rows"][0]
    assert out["rows"][1]["result_text"] == "Nẹp nhôm 12mm (C3210-20)", \
        out["rows"][1]


def test_preview_item_khong_tra_duoc_ten_van_tra_ma():
    base._reset_stub()  # không đăng ký Item ⇒ tên rỗng
    out = _rule(result_type="ITEM", threshold_rows=ITEM_ROWS).preview(8)
    assert out["result"] == {"item_code": "C3209-20", "item_name": ""}, out
    assert out["rows"][0]["result_text"] == "C3209-20", out["rows"][0]


def test_preview_constant():
    out = _rule(rule_type="CONSTANT", result_type="NUMBER",
                constant_value=0.12).preview(999)
    assert out["matched"] == {"kind": "constant", "from": None, "to": None,
                             "key": None}, out["matched"]
    assert out["result"] == {"value": 0.12}, out["result"]
    assert out["rows"] == [], out
    assert out["message"] == "", out["message"]


def test_preview_result_type_sai_bao_cau_nguoi_doc():
    out = _rule(rule_type="CONSTANT", result_type="TEXT",
                constant_value=1).preview(1)
    assert out["success"] is True, out
    assert out["result"] is None, out
    assert "Loại kết quả" in out["message"], out["message"]


# ═══════════════════════════════════════════════════════════════════
# (2) validate_lookup_rule_codes
# ═══════════════════════════════════════════════════════════════════
RULES = [
    {"name": "RULE-OK", "rule_name": "Số bản lề", "result_type": "NUMBER",
     "is_active": 1},
    {"name": "RULE-TAT", "rule_name": "Quy tắc đang tắt",
     "result_type": "NUMBER", "is_active": 0},
    {"name": "RULE-MA", "rule_name": "Chọn mã nẹp", "result_type": "ITEM",
     "is_active": 1},
]


def _load_rules():
    base._reset_stub()
    STUB.set_get_all("AL Rule", RULES)


def test_ma_dung_khong_canh_bao():
    _load_rules()
    assert fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-OK', H_mm) * n_panel") == []


def test_ma_sai_canh_bao_kem_loi_sua():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-MAT', H_mm)")
    assert len(warnings) == 1, warnings
    assert "RULE-MAT" in warnings[0], warnings[0]
    assert "không tìm thấy" in warnings[0], warnings[0]
    # Lối sửa phải chỉ ĐÚNG tên nút/hộp có thật trên form (đổi 2026-11-25:
    # nút là "🧩 Chọn công thức", nhánh quy tắc "Tra quy tắc theo giá trị").
    assert ("<b>Chọn công thức</b> → <b>Tra quy tắc theo giá trị</b>"
            in warnings[0]), warnings[0]
    assert "*Chọn công thức*" not in warnings[0], (
        "msgprint là HTML — markdown *…* sẽ hiện nguyên dấu sao: %s"
        % warnings[0])
    assert "Chèn tra quy tắc" not in warnings[0], warnings[0]


def test_rule_tat_canh_bao():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes("lookup_rule('RULE-TAT', 1)")
    assert len(warnings) == 1, warnings
    assert "đang tắt" in warnings[0], warnings[0]
    assert "Quy tắc đang tắt" in warnings[0], warnings[0]
    assert ("<b>Chọn công thức</b> → <b>Tra quy tắc theo giá trị</b>"
            in warnings[0]), warnings[0]
    assert "*Chọn công thức*" not in warnings[0], (
        "msgprint là HTML — markdown *…* sẽ hiện nguyên dấu sao: %s"
        % warnings[0])
    assert "Chèn tra quy tắc" not in warnings[0], warnings[0]


def test_sai_result_type_canh_bao():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-MA', 1)", expect_result_type="NUMBER")
    assert len(warnings) == 1, warnings
    assert "mã vật tư" in warnings[0] and "cần số" in warnings[0], warnings[0]
    assert ("<b>Chọn công thức</b> → <b>Tra quy tắc theo giá trị</b>"
            in warnings[0]), warnings[0]
    assert "*Chọn công thức*" not in warnings[0], (
        "msgprint là HTML — markdown *…* sẽ hiện nguyên dấu sao: %s"
        % warnings[0])
    assert "Chèn tra quy tắc" not in warnings[0], warnings[0]


def test_tham_so_khong_phai_literal_khong_canh_bao():
    _load_rules()
    # Biến, chuỗi nối, và lời gọi 2 tham số đều KHÔNG phải mã literal.
    for expr in (
        "lookup_rule(rule_var, H_mm)",
        "lookup_rule('RULE-' + suffix, H_mm)",
        "lookup_rule2('RULE-MAT', H_mm)",
        "mylookup_rule('RULE-MAT', H_mm)",
    ):
        assert fv.validate_lookup_rule_codes(expr) == [], expr


def test_nhieu_loi_goi_trong_mot_bieu_thuc():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-OK', H_mm) + lookup_rule('RULE-MAT', W_mm) "
        "+ lookup_rule(\"RULE-MAT\", 1)")
    assert len(warnings) == 1, warnings  # mã trùng chỉ báo 1 lần
    assert "RULE-MAT" in warnings[0], warnings[0]


def test_dung_hai_loai_nhay_deu_quet_duoc():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes('lookup_rule("RULE-MAT", 1)')
    assert len(warnings) == 1, warnings


def test_rule_meta_truyen_san_khong_goi_db_lai():
    base._reset_stub()
    STUB.set_get_all("AL Rule", [])  # DB rỗng ⇒ nếu đọc DB sẽ báo "không thấy"
    # Truyền meta ĐÃ có sẵn ⇒ hàm ⛔ đọc DB lần nữa, dùng đúng meta này.
    meta = {"RULE-OK": RULES[0]}
    assert fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-OK', 1)", rule_meta=meta) == []


def test_load_rule_meta_loi_db_tra_none():
    base._reset_stub()

    def _boom(*a, **k):
        raise RuntimeError("db down")

    STUB.get_all = _boom
    try:
        assert fv.load_rule_meta(["RULE-OK"]) is None
        # → validate phải IM LẶNG (⛔ cảnh báo "mã không tồn tại" oan).
        assert fv.validate_lookup_rule_codes("lookup_rule('RULE-OK', 1)") == []
    finally:
        del STUB.get_all


# ═══════════════════════════════════════════════════════════════════
# (2b) Caller cảnh báo 1 msgprint/lần lưu (AL Bom Set / Accessory Set)
# ═══════════════════════════════════════════════════════════════════
def _bom_set(items):
    from alumglass.al_bom_engine.doctype.al_bom_set.al_bom_set import ALBomSet

    doc = ALBomSet()
    doc._data = {"name": "BOM-THU"}
    doc.items = list(items)
    return doc


def test_bom_set_canh_bao_ma_quy_tac_sai():
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([
        base.FakeDoc({"slug": "ban_le", "idx": 1,
                      "item_selection_mode": "Formula",
                      "item_rule": None,
                      "rule_input_expr": "",
                      "qty": "lookup_rule('RULE-MAT', H_mm) * n_panel"}),
    ])
    doc._warn_lookup_rule_codes()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    assert "RULE-MAT" in MSGPRINTS[0]["message"], MSGPRINTS
    assert "ban_le" in MSGPRINTS[0]["message"], MSGPRINTS


def test_accessory_set_canh_bao_ma_quy_tac_tat():
    _load_rules()
    MSGPRINTS.clear()
    from alumglass.al_bom_engine.doctype.al_accessory_set.al_accessory_set import (
        ALAccessorySet)

    doc = ALAccessorySet()
    doc._data = {"name": "PK-1"}
    doc.items = [base.FakeDoc({
        "slug": "ban_le", "idx": 1,
        "qty_formula": "lookup_rule('RULE-TAT', H_mm) * n_panel"})]
    doc._warn_lookup_rule_codes()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    assert "đang tắt" in MSGPRINTS[0]["message"], MSGPRINTS


def test_bom_set_khong_co_ma_literal_thi_khong_msgprint():
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([
        base.FakeDoc({"slug": "ban_le", "idx": 1, "qty": "H_mm/1000 * 2"}),
    ])
    doc._warn_lookup_rule_codes()
    assert MSGPRINTS == [], MSGPRINTS


def test_cost_template_gop_canh_bao_vao_msgprint_co_san():
    """AL Cost Template: cảnh báo mã nằm CÙNG msgprint công thức (⛔ spam)."""
    _load_rules()
    MSGPRINTS.clear()
    from alumglass.al_bom_engine.doctype.al_cost_template.al_cost_template import (
        ALCostTemplate)

    doc = ALCostTemplate()
    doc._data = {"name": "CT-1"}
    doc.items = [base.FakeDoc({
        "line_code": "NC_LD",
        "calc_formula": "0.12 * TONG_VL "
                        "* lookup_rule('RULE-MAT', installation_height_m)"})]
    doc._build_known_names = lambda: {"TONG_VL", "installation_height_m"}
    doc.validate()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    assert "RULE-MAT" in MSGPRINTS[0]["message"], MSGPRINTS
    assert "NC_LD" in MSGPRINTS[0]["message"], MSGPRINTS


# ═══════════════════════════════════════════════════════════════════
# (2c) API whitelist `alumglass.api.preview_rule`
# ═══════════════════════════════════════════════════════════════════
def _api_rule_doc():
    rule = _rule(result_type="ITEM", threshold_rows=[
        {"from_value": 0, "to_value": 10, "result_item": "C3209-20"}])
    return rule


def test_api_preview_rule_uy_quyen_controller_va_kiem_quyen():
    base._reset_stub()
    rule = _api_rule_doc()
    STUB.set_doc("AL Rule", "RULE-NEP-GLASSTHICK", rule._data)
    original_get_doc = STUB.get_doc
    STUB.get_doc = lambda doctype, name: rule
    STUB.has_permission = lambda *a, **k: True

    import alumglass.api as api

    out = api.preview_rule("RULE-NEP-GLASSTHICK", 8)
    assert out["success"] is True, out
    assert out["result"]["item_code"] == "C3209-20", out["result"]
    assert out["input_label"] == "Độ dày kính", out

    MSGPRINTS.clear()
    STUB.has_permission = lambda *a, **k: False
    try:
        api.preview_rule("RULE-NEP-GLASSTHICK", 8)
    except (STUB.ValidationError, STUB.PermissionError) as exc:
        # `_require_doctype_read_permission` hiện ném ValidationError (câu
        # người-đọc-được) — nhận cả 2 lớp, miễn là CHẶN và câu nêu quyền.
        assert "không có quyền" in str(exc), exc
    else:
        raise AssertionError("thiếu quyền đọc AL Rule mà API vẫn trả dữ liệu")
    finally:
        STUB.get_doc = original_get_doc
        base._reset_stub()


# ═══════════════════════════════════════════════════════════════════
# (2d) explain_bom_line — nối `rule_description` vào bước quy tắc
# ═══════════════════════════════════════════════════════════════════
def test_explain_bom_line_them_rule_description():
    import json

    base._reset_stub()
    STUB.has_permission = lambda *a, **k: True
    import alumglass.api as api

    line = {
        "slug": "nep_kinh_tren", "item_code": "NEP-10", "item_name": "Nẹp 10",
        "item_selection_mode": "Rule",
        "rule_trace": ('Quy tắc "Chọn nẹp theo độ dày kính": độ dày kính của '
                       'dòng "Kính trên" = 10 mm → chọn mã "Nẹp 10" (NEP-10).'),
        "rule_trace_raw": "items.kinh_tren.glass_thick = 10 → RULE-NEP → NEP-10",
        "rule_name": "Chọn nẹp theo độ dày kính",
        "rule_description": "Chọn mã nẹp theo độ dày kính",
        "rule_match": "dải 0 – 10",
        "price_trace": "Bảng giá Standard Selling 1.000 đ",
        "unit_price": 1000, "total_qty": 2, "line_total": 2000,
    }
    out = api.explain_bom_line(
        "new-1", "nep_kinh_tren",
        result_json=json.dumps({"lines": [line]}), parent="QTN-1")
    assert out["success"] is True, out
    rule_step = [s for s in out["steps"] if s["key"] == "rule"][0]
    # Câu cũ GIỮ NGUYÊN, chỉ nối thêm mô tả.
    assert rule_step["detail"].startswith(
        'Quy tắc "Chọn nẹp theo độ dày kính" khớp dải 0 – 10 → chọn mã '
        '"Nẹp 10" (NEP-10).'), rule_step["detail"]
    assert rule_step["detail"].endswith("Chọn mã nẹp theo độ dày kính."), \
        rule_step["detail"]
    assert "RULE-NEP" not in rule_step["detail"], rule_step["detail"]
    STUB.has_permission = lambda *a, **k: True


# ═══════════════════════════════════════════════════════════════════
# (3) Câu trace ưu tiên `input_label` của quy tắc
# ═══════════════════════════════════════════════════════════════════
def _bare_orchestrator(input_label="", input_unit="", rule_description=""):
    orch = object.__new__(eo.BomOrchestrator)
    orch.bom_items = [{"slug": "kinh_tren", "line_name": "Kính trên"}]
    orch._glass_data = {"kinh_tren": {"glass_thick": 10}}
    orch.row_literals = {}
    orch._resolved_rule_items = {("RULE-NEP", 10): "NEP-10"}
    orch._rule_matches = {}
    orch._rule_names = {"RULE-NEP": "Chọn nẹp theo độ dày kính"}
    orch._rule_meta = {"RULE-NEP": {
        "rule_name": "Chọn nẹp theo độ dày kính",
        "input_label": input_label,
        "input_unit": input_unit,
        "output_label": "Mã nẹp",
        "rule_description": rule_description,
    }}
    orch._item_names = {"NEP-10": "Nẹp nhôm 10mm"}
    return orch


ITEM_RULE_ROW = {
    "item_rule": "RULE-NEP",
    "rule_input_expr": "items.kinh_tren.glass_thick",
    "item_selection_mode": "Rule",
}


def test_trace_uu_tien_gia_tri_va_ket_qua_truoc_quy_tac():
    """Thứ tự câu: `giá trị → kết quả` TRƯỚC, `· theo quy tắc "…"` SAU.

    Client hiển thị tối đa 2 dòng — cắt đuôi phải chỉ mất tên quy tắc.
    """
    orch = _bare_orchestrator(input_label="Độ dày kính")
    text = orch._rule_trace_text(orch._rule_trace_parts(ITEM_RULE_ROW))
    assert text == ('Độ dày kính của dòng "Kính trên" = 10 mm → '
                    '"Nẹp nhôm 10mm" (NEP-10) · theo quy tắc '
                    '"Chọn nẹp theo độ dày kính".'), text
    arrow = text.index("→")
    assert text.index('theo quy tắc "') > arrow, text


def test_trace_rule_cu_chua_khai_nhan_giu_nguyen_nhan_field():
    """Đối chứng âm của (3): rule chưa khai `input_label` ⇒ nhãn field."""
    orch = _bare_orchestrator()
    text = orch._rule_trace_text(orch._rule_trace_parts(ITEM_RULE_ROW))
    assert text == ('độ dày kính của dòng "Kính trên" = 10 mm → '
                    '"Nẹp nhôm 10mm" (NEP-10) · theo quy tắc '
                    '"Chọn nẹp theo độ dày kính".'), text


def test_trace_khong_khop_van_gia_tri_truoc_quy_tac():
    orch = _bare_orchestrator(input_label="Độ dày kính")
    orch._resolved_rule_items = {}  # không mã nào khớp
    text = orch._rule_trace_text(orch._rule_trace_parts(ITEM_RULE_ROW))
    assert text == ('Độ dày kính của dòng "Kính trên" = 10 mm → không có mã '
                    'nào khớp · theo quy tắc "Chọn nẹp theo độ dày kính".'), \
        text


# ═══════════════════════════════════════════════════════════════════
# (4) qty_rule_trace — "con số số lượng ở đâu ra"
# ═══════════════════════════════════════════════════════════════════
def _qty_orch(formula, labels=None):
    orch = object.__new__(eo.BomOrchestrator)
    orch._line_formulas = {"ban_le": {"qty": formula}}
    orch._var_labels = dict(labels or {})
    return orch


def _register_qty_rule(code="RULE-H", result=4, active=1, name="Số bản lề",
                       input_label="Chiều cao", input_unit="", resolver=None):
    base._reset_stub()
    STUB.set_doc("AL Rule", code, {
        "rule_name": name,
        "rule_type": "THRESHOLD",
        "result_type": "NUMBER",
        "is_active": active,
        "input_label": input_label,
        "input_unit": input_unit,
        "resolve": resolver or (lambda value: result),
    })


LABELS = {"H_mm": "Chiều cao", "n_panel": "Số cánh"}


def test_qty_rule_trace_dang_don_gian():
    _register_qty_rule()
    orch = _qty_orch("lookup_rule('RULE-H', H_mm)", LABELS)
    display, raw = orch._qty_rule_trace("ban_le", 4, {"H_mm": 2600})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'Chiều cao = 2.600 → 4.'), display
    assert "RULE-H" not in display, display
    assert "lookup_rule('RULE-H', H_mm)" not in display, display
    assert "rule=4" in raw and "H_mm=2600" in raw and "qty=4" in raw, raw
    assert "lookup_rule('RULE-H', H_mm)" in raw, raw


def test_qty_rule_trace_co_multiplier_bien():
    _register_qty_rule()
    orch = _qty_orch(
        "lookup_rule('RULE-H', H_mm) * n_panel", LABELS)
    display, raw = orch._qty_rule_trace(
        "ban_le", 8, {"H_mm": 2600, "n_panel": 2})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'Chiều cao = 2.600 → 4 × số cánh 2 = 8.'), display
    assert "n_panel=2" in raw, raw


def test_qty_rule_trace_multiplier_la_so():
    _register_qty_rule()
    orch = _qty_orch("lookup_rule('RULE-H', H_mm) * 2", LABELS)
    display, _raw = orch._qty_rule_trace("ban_le", 8, {"H_mm": 2600})
    assert display.endswith("→ 4 × 2 = 8."), display


def test_qty_rule_trace_don_vi_cua_rule():
    _register_qty_rule(input_unit="mm")
    orch = _qty_orch("lookup_rule('RULE-H', H_mm)", LABELS)
    display, _raw = orch._qty_rule_trace("ban_le", 4, {"H_mm": 2600})
    assert "Chiều cao = 2.600 mm → 4." in display, display


def test_qty_rule_trace_khong_khop_dang_thi_rong():
    """Công thức KHÔNG phải dạng đơn giản ⇒ ⛔ đoán, để trống vết."""
    _register_qty_rule()
    for formula in (
        "lookup_rule('RULE-H', H_mm) + 1",
        "lookup_rule('RULE-H', H_mm / 2)",
        "roundup(lookup_rule('RULE-H', H_mm), 0)",
        "lookup_rule('RULE-H', H_mm) * n_panel * 2",
        "safe_div(lookup_rule('RULE-H', H_mm), 2)",
    ):
        orch = _qty_orch(formula, LABELS)
        assert orch._qty_rule_trace(
            "ban_le", 8, {"H_mm": 2600, "n_panel": 2}) == ("", ""), formula


def test_qty_rule_trace_rule_khong_ton_tai_thi_rong():
    base._reset_stub()
    orch = _qty_orch("lookup_rule('RULE-MAT', H_mm)", LABELS)
    assert orch._qty_rule_trace("ban_le", 4, {"H_mm": 2600}) == ("", "")


def test_qty_rule_trace_rule_tat_cau_khong_so_ket_qua():
    """Rule tắt ⇒ câu nêu tên + giá trị đem tra, ⛔ bịa '→ 0 = 0'."""
    _register_qty_rule(active=0)
    orch = _qty_orch("lookup_rule('RULE-H', H_mm) * n_panel", LABELS)
    display, raw = orch._qty_rule_trace(
        "ban_le", 8, {"H_mm": 2600, "n_panel": 2})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'Chiều cao = 2.600.'), display
    assert "→" not in display, display
    assert "= 8" not in display, display
    assert "rule=?" in raw, raw


def test_qty_rule_trace_thieu_gia_tri_khong_bia_so():
    # resolver mô phỏng THRESHOLD thật: thiếu đầu vào ⇒ không có kết quả.
    _register_qty_rule(resolver=lambda value: None if value is None else 4)
    orch = _qty_orch("lookup_rule('RULE-H', H_mm)", LABELS)
    display, _raw = orch._qty_rule_trace("ban_le", 4, {})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'theo Chiều cao.'), display


def test_qty_rule_trace_rule_khong_khop_khong_bia_ket_qua():
    _register_qty_rule(resolver=lambda value: None)
    orch = _qty_orch("lookup_rule('RULE-H', H_mm)", LABELS)
    display, _raw = orch._qty_rule_trace("ban_le", 0, {"H_mm": 2600})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'Chiều cao = 2.600.'), display
    assert "→" not in display, display


def test_qty_rule_trace_bom_result_that_co_du_ca_hai_dang():
    """B4 thật (fixture phụ kiện): ban_le có vết, tay_nam (qty thường) rỗng."""
    orch = base._prepare_with_accessories({"H_mm": 2600, "n_panel": 2})
    rows = list(STUB.get_all_rows.get("AL Variable Library", []))
    rows += [{"var_name": "n_panel", "var_label": "Số cánh", "var_type": "Int"},
             {"var_name": "H_mm", "var_label": "Chiều cao", "var_type": "Float"}]
    STUB.set_get_all("AL Variable Library", rows)
    STUB.docs[("AL Rule", "RULE-BANLE-QTY")]._data.update({
        "rule_name": "Số bản lề theo chiều cao",
        "input_label": "Chiều cao", "input_unit": "mm",
    })
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    by_slug = {row["slug"]: row for row in orch.bom_result}
    assert by_slug["ban_le"]["qty_rule_trace"] == (
        'Chọn số lượng theo quy tắc "Số bản lề theo chiều cao": '
        'Chiều cao = 2.600 mm → 4 × số cánh 2 = 8.'), \
        by_slug["ban_le"]["qty_rule_trace"]
    assert by_slug["ban_le"]["qty"] == 8, by_slug["ban_le"]
    assert by_slug["tay_nam"]["qty_rule_trace"] == "", by_slug["tay_nam"]
    assert by_slug["tay_nam"]["qty_rule_trace_raw"] == "", by_slug["tay_nam"]


# ═══════════════════════════════════════════════════════════════════
# (5) explain_bom_line — bước "Quy tắc tính số lượng"
# ═══════════════════════════════════════════════════════════════════
QUANTITY_TRACE = ('Chọn số lượng theo quy tắc "Số bản lề theo chiều cao": '
                  'Chiều cao = 2.600 mm → 4 × số cánh 2 = 8.')


def _explain_line(**extra):
    import json

    base._reset_stub()
    STUB.has_permission = lambda *a, **k: True
    import alumglass.api as api

    line = {
        "slug": "ban_le", "item_code": "PK-02", "item_name": "Bản lề",
        "item_selection_mode": "Fixed",
        "price_trace": "Bảng giá Standard Selling 180.000 đ",
        "unit_price": 180000, "total_qty": 8, "line_total": 1440000,
        "width": 0, "height": 0, "qty": 8, "unit_qty": 1,
        "calc_pattern": "COUNT", "calc_pattern_name": "Đếm",
    }
    line.update(extra)
    return api.explain_bom_line(
        "new-1", "ban_le", result_json=json.dumps({"lines": [line]}),
        parent="QTN-1")


def test_explain_them_buoc_quy_tac_tinh_so_luong():
    out = _explain_line(qty_rule_trace=QUANTITY_TRACE)
    keys = [s["key"] for s in out["steps"]]
    assert keys == ["item_code", "price", "quantity", "qty_rule",
                    "line_total"], keys
    step = [s for s in out["steps"] if s["key"] == "qty_rule"][0]
    assert step["title"] == "Quy tắc tính số lượng", step
    assert step["detail"] == QUANTITY_TRACE, step
    # Bước mới nằm NGAY SAU "Tính số lượng".
    assert keys.index("qty_rule") == keys.index("quantity") + 1, keys


def test_explain_khong_them_buoc_khi_dong_khong_dung_quy_tac():
    out = _explain_line()  # không có qty_rule_trace
    keys = [s["key"] for s in out["steps"]]
    assert "qty_rule" not in keys, keys
    assert out["missing"] == [], out["missing"]


# ═══════════════════════════════════════════════════════════════════
# (6) Câu cảnh báo: HTML + tiền tố dòng tìm được sau khi đóng hộp
# ═══════════════════════════════════════════════════════════════════
def test_row_reference_label_co_so_dong_va_ten():
    assert fv.row_reference_label(base.FakeDoc({
        "idx": 3, "line_name": "Bản lề", "slug": "ban_le"})) == \
        "Dòng 3 — Bản lề"
    # Không có line_name ⇒ ưu tiên item_code, rồi slug.
    assert fv.row_reference_label(base.FakeDoc({
        "idx": 4, "item_code": "PK-02", "slug": "ban_le"})) == \
        "Dòng 4 — PK-02"
    assert fv.row_reference_label(base.FakeDoc({
        "idx": 5, "slug": "ban_le"})) == "Dòng 5 — ban_le"
    assert fv.row_reference_label(None) == "Dòng ?"


def test_canh_bao_dung_html_khong_dau_sao():
    _load_rules()
    for expr in ("lookup_rule('RULE-MAT', 1)",
                 "lookup_rule('RULE-TAT', 1)",
                 "lookup_rule('RULE-MA', 1)"):
        warning = fv.validate_lookup_rule_codes(expr)[0]
        assert "<b>Chọn công thức</b> → <b>Tra quy tắc theo giá trị</b>" in \
            warning, warning
        assert "*" not in warning, warning


def test_msgprint_al_bom_set_dung_tien_to_dong_idx_va_ten():
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([
        base.FakeDoc({"slug": "ban_le", "idx": 2, "line_name": "Bản lề",
                      "qty": "lookup_rule('RULE-MAT', H_mm)"}),
    ])
    doc._warn_lookup_rule_codes()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    assert "Dòng 2 — Bản lề:" in MSGPRINTS[0]["message"], MSGPRINTS
    assert "<b>Chọn công thức</b>" in MSGPRINTS[0]["message"], MSGPRINTS


def test_get_result_display_pass_through_qty_rule_trace():
    """Panel xem trước nhận `qty_rule_trace` (client không phải đọc JSON thô)."""
    import json

    base._reset_stub()
    STUB.has_permission = lambda *a, **k: True
    STUB.set_doc("Quotation Item", "QI-0001", {"parent": "QTN-1"})
    STUB.set_doc("Quotation", "QTN-1", {"docstatus": 0})
    import alumglass.api as api

    payload = json.dumps({"lines": [{
        "slug": "ban_le", "item_code": "PK-02", "qty": 8,
        "qty_rule_trace": QUANTITY_TRACE,
        "qty_rule_trace_raw": "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel",
    }]})
    out = api.get_result_display("QI-0001", result_json=payload)
    line = out["lines"][0]
    assert line["qty_rule_trace"] == QUANTITY_TRACE, line
    assert "RULE-BANLE-QTY" in line["qty_rule_trace_raw"], line
    # Data cũ thiếu key ⇒ "" (client bỏ qua, ⛔ KeyError).
    old = api.get_result_display("QI-0001", result_json=json.dumps(
        {"lines": [{"slug": "cu", "qty": 1}]}))
    assert old["lines"][0]["qty_rule_trace"] == "", old["lines"][0]


# ═══════════════════════════════════════════════════════════════════
# (7) AL Rule — nhãn tiếng Việt trên form/list
# ═══════════════════════════════════════════════════════════════════
def test_al_rule_json_nhan_tieng_viet():
    import json

    path = os.path.join(
        _REPO_ROOT, "alumglass", "al_formula_rules", "doctype", "al_rule",
        "al_rule.json")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    labels = {f["fieldname"]: f.get("label") for f in data["fields"]}
    expected = {
        "rule_code": "Mã quy tắc",
        "rule_name": "Tên quy tắc",
        "rule_type": "Kiểu quy tắc",
        "result_type": "Loại kết quả",
        "constant_value": "Giá trị cố định",
        "current_version": "Phiên bản hiện tại",
        "is_active": "Đang dùng?",
        "threshold_rows": "Bảng ngưỡng",
        "lookup_rows": "Bảng tra",
        "rule_description": "Mô tả nghiệp vụ",
        "input_label": "Tên dữ liệu đem tra",
        "input_unit": "Đơn vị",
        "output_label": "Kết quả trả về",
    }
    for fieldname, label in expected.items():
        assert labels.get(fieldname) == label, (
            "%s: nhãn còn tiếng Anh/lệch — %r" % (fieldname, labels.get(fieldname)))

    in_list = [f["fieldname"] for f in data["fields"] if f.get("in_list_view")]
    assert in_list == ["rule_code", "rule_name", "input_label", "output_label",
                       "rule_type", "result_type", "is_active"], in_list


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
            print("        "
                  + traceback.format_exc().strip().replace("\n", "\n        "))
            failed.append(name)
    print("\n" + "=" * 60)
    print("  TOTAL: %d  PASS: %d  FAIL: %d" % (len(funcs), passed, len(failed)))
    if failed:
        print("  FAILED: %s" % (failed,))
        sys.exit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _main()
