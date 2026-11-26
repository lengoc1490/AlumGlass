# -*- coding: utf-8 -*-
"""Standalone test — CHẶNG 3 "quy tắc tự khai tra theo cái gì" (phần SERVER).

Thiết kế: `docs/design/tra-cuu-quy-tac-de-hieu.md` §7.

Phủ:
  (1) Engine phân giải đầu vào: ROW (có/không `rule_input_row`, alias độ dày
      kính), GLOBAL (inputs / dữ liệu chính dòng), đường cũ `rule_input_expr`,
      quy tắc đang TẮT.
  (2) `b3_build_formulas` viết lại `lookup_rule('MÃ')` một tham số khi quy
      tắc khai biến TOÀN CỤC — và KHÔNG viết lại khi quy tắc khai ROW/chưa
      khai; tính tiền không đổi so với dạng 2 tham số.
  (3) `_qty_rule_trace` dạng MỘT tham số.
  (4) Validation: một tham số + chưa khai biến ⇒ cảnh báo; ROW + một tham số
      ⇒ cảnh báo; hợp lệ ⇒ KHÔNG cảnh báo; AL Bom Set cảnh báo thiếu
      `rule_input_row`.
  (5) `AL Rule` — field mới + `validate()` tự suy `input_scope`/nhãn;
      `preview()` trả thêm khoá + câu "nhập giá trị để thử".
  (6) Patch `infer_rule_input_variable`: điền đúng khi ĐỒNG NHẤT, ⛔ điền khi
      mơ hồ, idempotent, `dry_run` chỉ đọc, chịu bảng/cột thiếu.

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_rule_input_variable.py
"""
import json
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
from alumglass.al_formula_rules import rule_input  # noqa: E402
from alumglass.patches.v1_0 import infer_rule_input_variable as patch  # noqa: E402
import alumglass.engine.bom_orchestrator as eo  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# Stub bổ sung — throw đúng lớp, hứng msgprint, hứng db.set_value (có kwarg)
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

#: `frappe.db.set_value` của stub cũ ⛔ nhận `update_modified` — patch thật
#: truyền kwarg này, nên bọc lại (ghi lại y hệt lời gọi để test kiểm).
SET_VALUE_CALLS = []
_ORIGINAL_DB_SET_VALUE = STUB.db.set_value


def _db_set_value(doctype, name, field_or_dict, value=None, **kwargs):
    SET_VALUE_CALLS.append((doctype, name, field_or_dict, value))
    return _ORIGINAL_DB_SET_VALUE(doctype, name, field_or_dict, value)


STUB.db.set_value = _db_set_value


# ═══════════════════════════════════════════════════════════════════
# Dựng dữ liệu
# ═══════════════════════════════════════════════════════════════════
VARIABLES = [
    {"name": "glass_thick", "category": "Row Literals",
     "var_label": "Độ dày kính"},
    {"name": "total_thick_mm", "category": "Row Literals",
     "var_label": "Độ dày kính"},
    {"name": "glass_type", "category": "Row Literals",
     "var_label": "Loại kính"},
    {"name": "H_mm", "category": "Kích thước", "var_label": "Chiều cao"},
    # Biến THEO DÒNG nhưng engine KHÔNG nạp ở bước chọn mã — chọn vào quy
    # tắc ROW là ra 0 âm thầm (lỗ hổng đã vá).
    {"name": "width", "category": "Row Literals", "var_label": "Chiều rộng"},
    {"name": "height", "category": "Row Literals",
     "var_label": "Chiều cao cánh"},
    {"name": "unit_qty", "category": "Row Literals",
     "var_label": "SL đơn vị"},
]


def _register_rule(code, **fields):
    base._reset_stub()
    data = {
        "rule_name": fields.pop("rule_name", "Quy tắc thử"),
        "rule_type": fields.pop("rule_type", "THRESHOLD"),
        "result_type": fields.pop("result_type", "NUMBER"),
        "is_active": fields.pop("is_active", 1),
        "resolve": fields.pop("resolve", lambda value: 4),
    }
    data.update(fields)
    STUB.set_doc("AL Rule", code, data)
    STUB.set_get_all("AL Variable Library", VARIABLES)
    return data


def _orch(bom_items=None, glass_data=None, row_literals=None, inputs=None,
          resolved=None, matches=None, rule_names=None, rule_meta=None,
          item_names=None):
    orch = object.__new__(eo.BomOrchestrator)
    orch.bom_items = list(bom_items or [])
    orch._glass_data = dict(glass_data or {})
    orch.row_literals = dict(row_literals or {})
    orch.inputs = dict(inputs or {})
    orch._resolved_rule_items = dict(resolved or {})
    orch._rule_matches = dict(matches or {})
    orch._rule_names = dict(rule_names or {})
    orch._rule_meta = dict(rule_meta or {})
    orch._item_names = dict(item_names or {})
    return orch


ITEM_ROW = {
    "slug": "nep_kinh_tren", "line_name": "Nẹp kính trên", "idx": 1,
    "item_rule": "RULE-NEP", "item_selection_mode": "Rule",
    "rule_input_expr": "",
}


# ═══════════════════════════════════════════════════════════════════
# (1) Engine phân giải đầu vào
# ═══════════════════════════════════════════════════════════════════
def test_row_doc_tu_dong_chon():
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="glass_thick",
        input_scope="ROW", input_label="Độ dày kính")
    orch = _orch(
        bom_items=[{"slug": "kinh_tren", "line_name": "Kính trên"}],
        glass_data={"kinh_tren": {"glass_thick": 10}})
    item = dict(ITEM_ROW, rule_input_row="kinh_tren")
    assert orch._resolve_rule_input_for_item(item, orch._glass_data) == 10


def test_row_alias_doc_dau_kinh_ten_chuan():
    """Rule khai `total_thick_mm` mà dữ liệu dòng chỉ có `glass_thick`."""
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="total_thick_mm",
        input_scope="ROW")
    orch = _orch(row_literals={"kinh_tren": {"glass_thick": 12}})
    item = dict(ITEM_ROW, rule_input_row="kinh_tren")
    assert orch._resolve_rule_input_for_item(item) == 12


def test_row_alias_nguoc_lai():
    """Rule khai tên CŨ mà dữ liệu chỉ có tên CHUẨN."""
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="glass_thick",
        input_scope="ROW")
    orch = _orch(row_literals={"kinh_tren": {"total_thick_mm": 8}})
    item = dict(ITEM_ROW, rule_input_row="kinh_tren")
    assert orch._resolve_rule_input_for_item(item) == 8


def test_row_thieu_rule_input_row_lui_ve_bieu_thuc_cu():
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="glass_thick",
        input_scope="ROW")
    orch = _orch(glass_data={
        "kinh_tren": {"glass_thick": 10},
        "kinh_duoi": {"glass_thick": 6},
    })
    item = dict(ITEM_ROW, rule_input_expr="items.kinh_duoi.glass_thick")
    assert orch._resolve_rule_input_for_item(item, orch._glass_data) == 6, (
        "thiếu 'Lấy từ dòng' phải dùng biểu thức cũ, ⛔ đoán dòng")


def test_row_thieu_ca_hai_khong_co_dau_vao():
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="glass_thick",
        input_scope="ROW")
    orch = _orch()
    assert orch._resolve_rule_input_for_item(dict(ITEM_ROW)) is None


def test_global_lay_tu_inputs():
    _register_rule(
        "RULE-BANLE", input_variable="H_mm", input_scope="GLOBAL",
        input_label="Chiều cao")
    orch = _orch(inputs={"H_mm": 3200, "W_mm": 900})
    assert orch._resolve_rule_input_for_item(
        dict(ITEM_ROW, item_rule="RULE-BANLE")) == 3200


def test_global_thieu_inputs_thi_lay_du_lieu_chinh_dong():
    _register_rule(
        "RULE-BANLE", input_variable="H_mm", input_scope="GLOBAL")
    orch = _orch(
        inputs={"W_mm": 900},  # KHÔNG có H_mm
        row_literals={"nep_kinh_tren": {"H_mm": 2000}})
    assert orch._resolve_rule_input_for_item(
        dict(ITEM_ROW, item_rule="RULE-BANLE")) == 2000


def test_global_thieu_ca_hai_khong_co_dau_vao():
    _register_rule(
        "RULE-BANLE", input_variable="H_mm", input_scope="GLOBAL")
    orch = _orch(inputs={"W_mm": 900})
    assert orch._resolve_rule_input_for_item(
        dict(ITEM_ROW, item_rule="RULE-BANLE")) is None


def test_rule_chua_khai_bien_giu_nguyen_duong_cu():
    """ĐỐI CHỨNG ÂM: rule cũ (không khai biến) phải dùng `rule_input_expr`."""
    _register_rule("RULE-NEP", result_type="ITEM")  # ⛔ input_variable
    orch = _orch(glass_data={"kinh_tren": {"glass_thick": 10}})
    item = dict(ITEM_ROW, rule_input_expr="items.kinh_tren.glass_thick")
    assert orch._resolve_rule_input_for_item(item, orch._glass_data) == 10


def test_rule_khong_doc_duoc_giu_nguyen_duong_cu():
    """Mã rule sai ⇒ ⛔ chết: rơi về `rule_input_expr` như trước bản vá."""
    base._reset_stub()
    orch = _orch(glass_data={"kinh_tren": {"glass_thick": 10}})
    item = dict(ITEM_ROW, rule_input_expr="items.kinh_tren.glass_thick")
    assert orch._resolve_rule_input_for_item(item, orch._glass_data) == 10


def test_rule_tat_van_phan_giai_duoc_dau_vao():
    """Đầu vào ⛔ phụ thuộc trạng thái bật/tắt; rule tắt chỉ mất KẾT QUẢ."""
    _register_rule(
        "RULE-BANLE", is_active=0, input_variable="H_mm",
        input_scope="GLOBAL", input_label="Chiều cao",
        rule_name="Số bản lề")
    orch = _orch(inputs={"H_mm": 2600}, rule_names={
        "RULE-BANLE": "Số bản lề"})
    parts = orch._rule_trace_parts(
        dict(ITEM_ROW, item_rule="RULE-BANLE"))
    assert parts["input_value"] == 2600, parts
    text = orch._rule_trace_text(parts)
    assert text == ('Chiều cao = 2.600 → không có mã nào khớp · '
                    'theo quy tắc "Số bản lề".'), text


def test_trace_global_va_ket_qua():
    """Câu trace biến toàn cục: `Chiều cao = …` — ⛔ `items.`, ⛔ mã rule."""
    _register_rule(
        "RULE-BANLE", input_variable="H_mm", input_scope="GLOBAL",
        input_label="Chiều cao", result_type="ITEM", rule_name="Số bản lề")
    orch = _orch(
        inputs={"H_mm": 3200},
        resolved={("RULE-BANLE", 3200): "PK-02"},
        rule_names={"RULE-BANLE": "Số bản lề"},
        item_names={"PK-02": "Bản lề inox"})
    parts = orch._rule_trace_parts(dict(ITEM_ROW, item_rule="RULE-BANLE"))
    text = orch._rule_trace_text(parts)
    assert text == ('Chiều cao = 3.200 → "Bản lề inox" (PK-02) · '
                    'theo quy tắc "Số bản lề".'), text
    assert "items." not in text and "RULE-" not in text, text
    raw = orch._rule_trace_text_raw(parts)
    assert raw == "H_mm = 3200 → RULE-BANLE → PK-02", raw


def test_trace_row_dung_cau_dong_va_nhan():
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="glass_thick",
        input_scope="ROW", input_label="Độ dày kính",
        rule_name="Chọn nẹp")
    orch = _orch(
        bom_items=[{"slug": "kinh_tren", "line_name": "Kính trên"}],
        glass_data={"kinh_tren": {"glass_thick": 10}},
        resolved={("RULE-NEP", 10): "NEP-10"},
        rule_names={"RULE-NEP": "Chọn nẹp"},
        item_names={"NEP-10": "Nẹp nhôm 10mm"})
    item = dict(ITEM_ROW, rule_input_row="kinh_tren")
    text = orch._rule_trace_text(orch._rule_trace_parts(item))
    assert text == ('Độ dày kính của dòng "Kính trên" = 10 mm → '
                    '"Nẹp nhôm 10mm" (NEP-10) · theo quy tắc "Chọn nẹp".'), \
        text


def test_trace_chua_co_gia_tri_khong_bia_so():
    """§7.6 — GLOBAL thiếu giá trị: câu RIÊNG, ⛔ "không có mã nào khớp".

    Người đọc phải biết việc thật là thiếu THÔNG SỐ ĐẦU VÀO của báo giá,
    ⛔ phải đi sửa bảng quy tắc.
    """
    _register_rule(
        "RULE-BANLE", input_variable="H_mm", input_scope="GLOBAL",
        input_label="Chiều cao", rule_name="Số bản lề")
    orch = _orch(inputs={}, rule_names={"RULE-BANLE": "Số bản lề"})
    parts = orch._rule_trace_parts(dict(ITEM_ROW, item_rule="RULE-BANLE"))
    assert parts["input_missing"] == "no_global_value", parts
    assert parts["input_found"] is False, parts
    text = orch._rule_trace_text(parts)
    assert text == ("Chưa có Chiều cao cho lượt tính này nên chưa chọn được "
                    "mã — kiểm tra thông số đầu vào của báo giá."), text
    # ⛔ bịa "= 0" / "= —", ⛔ đổ lỗi cho bảng quy tắc.
    assert "= 0" not in text and "= —" not in text, text
    assert "không có mã nào khớp" not in text, text


# ═══════════════════════════════════════════════════════════════════
# (2) b3_build_formulas — viết lại lời gọi MỘT tham số
# ═══════════════════════════════════════════════════════════════════
def test_viet_lai_khi_global():
    _register_rule("RULE-BANLE", input_variable="H_mm",
                   input_scope="GLOBAL")
    orch = _orch()
    out = orch._inject_declared_rule_input("lookup_rule('RULE-BANLE') * 2")
    assert out == "lookup_rule('RULE-BANLE', H_mm) * 2", out


def test_viet_lai_giu_loai_nhay():
    _register_rule("RULE-BANLE", input_variable="H_mm",
                   input_scope="GLOBAL")
    orch = _orch()
    out = orch._inject_declared_rule_input('lookup_rule("RULE-BANLE")')
    assert out == 'lookup_rule("RULE-BANLE", H_mm)', out


def test_khong_viet_lai_khi_row():
    """ĐỐI CHỨNG ÂM: quy tắc ROW ⛔ được tự đoán dòng ⇒ giữ nguyên."""
    _register_rule("RULE-NEP", result_type="ITEM",
                   input_variable="glass_thick", input_scope="ROW")
    orch = _orch()
    expr = "lookup_rule('RULE-NEP')"
    assert orch._inject_declared_rule_input(expr) == expr


def test_khong_viet_lai_khi_chua_khai_bien():
    """ĐỐI CHỨNG ÂM: rule cũ ⛔ bị chèn biến (không có biến nào để chèn)."""
    _register_rule("RULE-NEP", result_type="ITEM")
    orch = _orch()
    expr = "lookup_rule('RULE-NEP')"
    assert orch._inject_declared_rule_input(expr) == expr


def test_khong_dung_toi_loi_goi_hai_tham_so():
    _register_rule("RULE-BANLE", input_variable="H_mm",
                   input_scope="GLOBAL")
    orch = _orch()
    expr = "lookup_rule('RULE-BANLE', W_mm) * 2"
    assert orch._inject_declared_rule_input(expr) == expr


def _prepare_ban_le(scope="GLOBAL", formula="lookup_rule('RULE-BANLE-QTY')"):
    """Fixture phụ kiện, đổi quy tắc + công thức theo kịch bản."""
    orch = base._prepare_with_accessories({"H_mm": 2600, "n_panel": 2})
    # Nhãn biến cho câu giải thích "số cánh" (b1 đọc AL Variable Library).
    rows = list(STUB.get_all_rows.get("AL Variable Library", []))
    rows += [{"var_name": "n_panel", "var_label": "Số cánh", "var_type": "Int"},
             {"var_name": "H_mm", "var_label": "Chiều cao", "var_type": "Float"}]
    STUB.set_get_all("AL Variable Library", rows)
    STUB.docs[("AL Accessory Set", "ACC-1")]._data["items"][1][
        "qty_formula"] = formula + " * n_panel"
    STUB.docs[("AL Rule", "RULE-BANLE-QTY")]._data.update({
        "rule_name": "Số bản lề theo chiều cao",
        "input_label": "Chiều cao", "input_unit": "mm",
        "input_variable": "H_mm" if scope else "",
        "input_scope": scope or "",
    })
    return orch


def test_b3_viet_lai_va_tinh_tien_khong_doi():
    """`lookup_rule('MÃ') * n_panel` (GLOBAL) = `lookup_rule('MÃ', H_mm) * n_panel`."""
    orch = _prepare_ban_le("GLOBAL")
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    assert orch._line_formulas["ban_le"]["qty"] == (
        "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel"), \
        orch._line_formulas["ban_le"]["qty"]
    orch.b4_calculate_bom_items()
    by_slug = {row["slug"]: row for row in orch.bom_result}
    assert by_slug["ban_le"]["qty"] == 8, by_slug["ban_le"]
    assert by_slug["ban_le"]["total_qty"] == 8, by_slug["ban_le"]
    assert by_slug["ban_le"]["qty_rule_trace"] == (
        'Chọn số lượng theo quy tắc "Số bản lề theo chiều cao": '
        'Chiều cao = 2.600 mm → 4 × số cánh 2 = 8.'), \
        by_slug["ban_le"]["qty_rule_trace"]


def test_b3_khong_viet_lai_khi_rule_row():
    """ĐỐI CHỨNG ÂM ở tầng b3 thật: ROW ⇒ công thức giữ 1 tham số."""
    orch = _prepare_ban_le("ROW")
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    assert orch._line_formulas["ban_le"]["qty"] == (
        "lookup_rule('RULE-BANLE-QTY') * n_panel"), \
        orch._line_formulas["ban_le"]["qty"]


def test_b3_golden_hai_tham_so_khong_doi():
    """Đối chứng: công thức 2 tham số (dữ liệu hiện có) vẫn ra đúng số cũ."""
    orch = _prepare_ban_le(
        "GLOBAL", formula="lookup_rule('RULE-BANLE-QTY', H_mm)")
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    by_slug = {row["slug"]: row for row in orch.bom_result}
    assert by_slug["ban_le"]["qty"] == 8, by_slug["ban_le"]


# ═══════════════════════════════════════════════════════════════════
# (3) _qty_rule_trace — dạng MỘT tham số
# ═══════════════════════════════════════════════════════════════════
LABELS = {"H_mm": "Chiều cao", "n_panel": "Số cánh"}


def _qty_orch(formula, labels=None):
    orch = object.__new__(eo.BomOrchestrator)
    orch._line_formulas = {"ban_le": {"qty": formula}}
    orch._var_labels = dict(labels or {})
    return orch


def test_qty_trace_mot_tham_so_global():
    _register_rule(
        "RULE-H", input_variable="H_mm", input_scope="GLOBAL",
        input_label="Chiều cao", input_unit="mm",
        rule_name="Số bản lề")
    orch = _qty_orch("lookup_rule('RULE-H') * n_panel", LABELS)
    display, raw = orch._qty_rule_trace(
        "ban_le", 8, {"H_mm": 2600, "n_panel": 2})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'Chiều cao = 2.600 mm → 4 × số cánh 2 = 8.'), display
    assert "H_mm=2600" in raw and "rule=4" in raw, raw


def test_qty_trace_mot_tham_so_nhan_tu_var_library():
    """Rule chưa khai `input_label` ⇒ nhãn lấy `AL Variable Library`."""
    _register_rule(
        "RULE-H", input_variable="H_mm", input_scope="GLOBAL",
        rule_name="Số bản lề")
    orch = _qty_orch("lookup_rule('RULE-H')", LABELS)
    display, _raw = orch._qty_rule_trace("ban_le", 4, {"H_mm": 2600})
    assert display == ('Chọn số lượng theo quy tắc "Số bản lề": '
                       'Chiều cao = 2.600 → 4.'), display


def test_qty_trace_mot_tham_so_chua_khai_bien_thi_rong():
    """ĐỐI CHỨNG ÂM: ⛔ bịa biến — vết để trống, cảnh báo đã có ở validate."""
    _register_rule("RULE-H", rule_name="Số bản lề")
    orch = _qty_orch("lookup_rule('RULE-H')", LABELS)
    assert orch._qty_rule_trace(
        "ban_le", 4, {"H_mm": 2600}) == ("", "")


def test_qty_trace_mot_tham_so_rule_row_thi_rong():
    _register_rule(
        "RULE-H", input_variable="glass_thick", input_scope="ROW",
        rule_name="Số bản lề")
    orch = _qty_orch("lookup_rule('RULE-H')", LABELS)
    assert orch._qty_rule_trace(
        "ban_le", 4, {"H_mm": 2600}) == ("", "")


# ═══════════════════════════════════════════════════════════════════
# (4) Validation
# ═══════════════════════════════════════════════════════════════════
RULES = [
    {"name": "RULE-G", "rule_name": "Bản lề", "result_type": "NUMBER",
     "is_active": 1, "input_variable": "H_mm", "input_scope": "GLOBAL",
     "input_label": "Chiều cao"},
    {"name": "RULE-NOVAR", "rule_name": "Chưa khai biến",
     "result_type": "NUMBER", "is_active": 1, "input_variable": "",
     "input_scope": "GLOBAL", "input_label": ""},
    {"name": "RULE-ROW", "rule_name": "Nẹp theo dòng", "result_type": "NUMBER",
     "is_active": 1, "input_variable": "glass_thick", "input_scope": "ROW",
     "input_label": "Độ dày kính"},
]


def _load_rules():
    base._reset_stub()
    STUB.set_get_all("AL Rule", RULES)


def test_validate_mot_tham_so_rule_global_khong_canh_bao():
    _load_rules()
    assert fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-G') * n_panel") == []


def test_validate_mot_tham_so_chua_khai_bien_canh_bao():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes("lookup_rule('RULE-NOVAR')")
    assert len(warnings) == 1, warnings
    assert "MỘT tham số" in warnings[0], warnings[0]
    assert "Tra theo" in warnings[0], warnings[0]
    assert "<b>Chọn công thức</b>" in warnings[0], warnings[0]


def test_validate_mot_tham_so_rule_row_canh_bao_kem_cach_sua():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes("lookup_rule('RULE-ROW')")
    assert len(warnings) == 1, warnings
    message = warnings[0]
    assert "TỪNG DÒNG" in message, message
    # Nhãn dữ liệu lấy từ metadata quy tắc — ⛔ câu cứng
    # "Độ dày kính hoặc Loại kính" (biến theo dòng không chỉ có 2 loại đó).
    assert "Độ dày kính" in message, message
    assert "Loại kính" not in message, message
    # Hướng dẫn theo THAO TÁC, ⛔ dạy viết code (`items.…`).
    assert "<b>Chọn công thức</b>" in message, message
    assert "<b>Tra quy tắc theo giá trị</b>" in message, message
    assert "<b>Chọn dòng lấy dữ liệu</b>" in message, message
    assert "items." not in message and "&lt;" not in message, message
    # Nêu HẬU QUẢ nếu bỏ qua.
    assert "không có mã vật tư" in message, message


def test_validate_hai_tham_so_rule_chua_khai_bien_khong_canh_bao():
    """Tương thích ngược: dạng 2 tham số cũ ⛔ bị cảnh báo oan."""
    _load_rules()
    assert fv.validate_lookup_rule_codes(
        "lookup_rule('RULE-NOVAR', H_mm)") == []


def test_validate_van_bao_ma_sai_khi_mot_tham_so():
    _load_rules()
    warnings = fv.validate_lookup_rule_codes("lookup_rule('RULE-MAT')")
    assert len(warnings) == 1, warnings
    assert "không tìm thấy" in warnings[0], warnings[0]


def test_parse_lookup_rule_calls_dem_tham_so_dung():
    arities = rule_input.lookup_rule_arities(
        "lookup_rule('A') + lookup_rule('B', H_mm) "
        "+ roundup(lookup_rule('C', H_mm / 2), 0)")
    assert arities == {"A": {1}, "B": {2}, "C": {2}}, arities
    # Nối chuỗi / biến ⛔ phải coi là mã literal.
    assert rule_input.lookup_rule_arities(
        "lookup_rule('A' + suffix, x)") == {}


def _bom_set(items):
    from alumglass.al_bom_engine.doctype.al_bom_set.al_bom_set import ALBomSet

    doc = ALBomSet()
    doc._data = {"name": "BOM-THU"}
    doc.items = list(items)
    return doc


def test_bom_set_canh_bao_thieu_lay_tu_dong():
    """§7.6 — câu cảnh báo chỉ nút NHÌN THẤY, ⛔ tên field ẩn."""
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([base.FakeDoc({
        "slug": "nep", "idx": 2, "line_name": "Nẹp kính",
        "item_selection_mode": "Rule", "item_rule": "RULE-ROW",
        "rule_input_expr": "", "rule_input_row": ""})])
    doc._warn_rule_input_row()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    message = MSGPRINTS[0]["message"]
    assert "Dòng 2 — Nẹp kính" in message, message
    # Nút THẬT trên form (ô `rule_input_row` bị ẩn) — ⛔ nhắc tên field.
    assert "<b>Chọn dòng lấy dữ liệu</b>" in message, message
    assert "rule_input_row" not in message, message
    assert "Lấy từ dòng" not in message, message
    assert "Độ dày kính" in message, message
    assert "thành tiền chưa đúng" in message, message


def test_bom_set_canh_bao_bieu_thuc_nang_cao_bi_bo_qua():
    """§7.6 — đã chọn dòng ⇒ biểu thức cũ KHÔNG còn được dùng: nói rõ."""
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([base.FakeDoc({
        "slug": "nep", "idx": 2, "line_name": "Nẹp kính",
        "item_selection_mode": "Rule", "item_rule": "RULE-ROW",
        "rule_input_expr": "items.kinh_tren.glass_thick",
        "rule_input_row": "kinh_tren"})])
    doc._warn_rule_input_row()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    message = MSGPRINTS[0]["message"]
    assert "biểu thức nâng cao" in message, message
    assert "bị bỏ qua" in message, message
    assert "rule_input_expr" not in message, message


def test_bom_set_rule_global_co_bieu_thuc_cu_canh_bao_bi_bo_qua():
    """§7.6 — GLOBAL tự lấy thông số lượt tính ⇒ biểu thức cũ bị bỏ qua."""
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([base.FakeDoc({
        "slug": "ban_le", "idx": 3, "line_name": "Bản lề",
        "item_selection_mode": "Rule", "item_rule": "RULE-G",
        "rule_input_expr": "items.kinh_tren.glass_thick",
        "rule_input_row": ""})])
    doc._warn_rule_input_row()
    assert len(MSGPRINTS) == 1, MSGPRINTS
    assert "biểu thức nâng cao" in MSGPRINTS[0]["message"], MSGPRINTS


def test_bom_set_da_chon_dong_thi_khong_canh_bao():
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([base.FakeDoc({
        "slug": "nep", "idx": 2, "line_name": "Nẹp kính",
        "item_selection_mode": "Rule", "item_rule": "RULE-ROW",
        "rule_input_expr": "", "rule_input_row": "kinh_tren"})])
    doc._warn_rule_input_row()
    assert MSGPRINTS == [], MSGPRINTS


def test_bom_set_con_bieu_thuc_cu_thi_khong_canh_bao():
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([base.FakeDoc({
        "slug": "nep", "idx": 2, "line_name": "Nẹp kính",
        "item_selection_mode": "Rule", "item_rule": "RULE-ROW",
        "rule_input_expr": "items.kinh_tren.glass_thick",
        "rule_input_row": ""})])
    doc._warn_rule_input_row()
    assert MSGPRINTS == [], MSGPRINTS


def test_bom_set_rule_global_thi_khong_canh_bao():
    _load_rules()
    MSGPRINTS.clear()
    doc = _bom_set([base.FakeDoc({
        "slug": "ban_le", "idx": 3, "line_name": "Bản lề",
        "item_selection_mode": "Rule", "item_rule": "RULE-G",
        "rule_input_expr": "", "rule_input_row": ""})])
    doc._warn_rule_input_row()
    assert MSGPRINTS == [], MSGPRINTS


# ═══════════════════════════════════════════════════════════════════
# (5) AL Rule — field mới, validate, preview
# ═══════════════════════════════════════════════════════════════════
def _rule(**extra):
    data = {
        "rule_code": "RULE-THU", "rule_name": "Quy tắc thử",
        "rule_type": "CONSTANT", "result_type": "NUMBER",
        "constant_value": 1, "is_active": 1,
        "threshold_rows": [], "lookup_rows": [],
    }
    data.update(extra)
    doc = ALRule()
    doc._data = data
    for key, value in data.items():
        setattr(doc, key, value)
    return doc


def test_rule_validate_suy_scope_row_va_dien_nhan():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rule = _rule(input_variable="total_thick_mm", input_label="")
    rule.validate()
    assert rule.input_scope == "ROW", rule.input_scope
    assert rule.input_label == "Độ dày kính", rule.input_label


def test_rule_validate_suy_scope_global_va_giu_nhan_tu_dat():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rule = _rule(input_variable="H_mm", input_label="Chiều cao thông thuỷ")
    rule.validate()
    assert rule.input_scope == "GLOBAL", rule.input_scope
    # Nhãn người dùng đã đặt ⇒ ⛔ ghi đè.
    assert rule.input_label == "Chiều cao thông thuỷ", rule.input_label


def test_rule_validate_khong_khai_bien_thi_global():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rule = _rule()
    rule.validate()
    assert rule.input_scope == "GLOBAL", rule.input_scope


def test_rule_preview_bao_thieu_gia_tri_dung_nhan_bien():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rule = _rule(
        rule_type="THRESHOLD", input_variable="total_thick_mm",
        input_scope="ROW", input_label="Độ dày kính",
        threshold_rows=[
            {"from_value": 0, "to_value": 10, "result_value": 100}])
    out = rule.preview()
    assert out["success"] is True, out
    assert out["message"] == ("Quy tắc tra theo Độ dày kính — nhập giá trị "
                              "để thử."), out["message"]
    assert out["input_variable"] == "total_thick_mm", out
    assert out["input_scope"] == "ROW", out


def test_rule_preview_nhan_lay_tu_var_library_khi_trong():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rule = _rule(
        rule_type="THRESHOLD", input_variable="H_mm", input_scope="GLOBAL",
        input_label="",
        threshold_rows=[
            {"from_value": 0, "to_value": 3000, "result_value": 4}])
    out = rule.preview()
    assert out["message"] == (
        "Quy tắc tra theo Chiều cao — nhập giá trị để thử."), out["message"]


def test_rule_preview_rule_chua_khai_bien_giu_cau_cu():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    out = _rule(
        rule_type="THRESHOLD", input_label="Độ dày kính",
        threshold_rows=[
            {"from_value": 0, "to_value": 10, "result_value": 100}]).preview()
    assert out["message"] == "Nhập Độ dày kính cần tra để xem kết quả.", out
    assert out["input_variable"] == "" and out["input_scope"] == "", out


def test_api_preview_rule_tra_kem_hai_field_moi():
    """API whitelist chỉ uỷ quyền controller — khoá mới phải đi ra ngoài."""
    base._reset_stub()
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rule = _rule(
        rule_type="THRESHOLD", input_variable="H_mm", input_scope="GLOBAL",
        input_label="Chiều cao",
        threshold_rows=[
            {"from_value": 0, "to_value": 3000, "result_value": 4}])
    original_get_doc = STUB.get_doc
    original_permission = getattr(STUB, "has_permission", None)
    STUB.get_doc = lambda doctype, name: rule
    STUB.has_permission = lambda *args, **kwargs: True
    import alumglass.api as api

    try:
        out = api.preview_rule("RULE-THU", 2600)
    finally:
        STUB.get_doc = original_get_doc
        if original_permission is None:
            del STUB.has_permission
        else:
            STUB.has_permission = original_permission
        base._reset_stub()
    assert out["input_variable"] == "H_mm", out
    assert out["input_scope"] == "GLOBAL", out
    assert out["input_label"] == "Chiều cao", out
    assert out["result"] == {"value": 4}, out


def test_al_rule_json_co_hai_field_moi():
    import json

    path = os.path.join(
        _REPO_ROOT, "alumglass", "al_formula_rules", "doctype", "al_rule",
        "al_rule.json")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    by_name = {field["fieldname"]: field for field in data["fields"]}
    variable = by_name["input_variable"]
    assert variable["fieldtype"] == "Link", variable
    assert variable["options"] == "AL Variable Library", variable
    assert variable["label"] == "Tra theo", variable
    scope = by_name["input_scope"]
    assert scope["fieldtype"] == "Select", scope
    assert scope["options"] == "ROW\nGLOBAL", scope
    assert scope["label"] == "Phạm vi dữ liệu tra", scope
    assert scope.get("read_only") == 1, scope
    assert scope.get("hidden") == 1, scope
    assert scope.get("default") == "GLOBAL", scope
    order = data["field_order"]
    # Nhóm "Tra theo" phải nằm LIỀN nhau trong 1 section. ⚠ Không chốt thứ tự
    # tuyệt đối giữa 3 ô: `input_scope` (ô ẩn, máy tự suy) do file AL Rule của
    # phần giao diện bố trí — thêm/bớt ô ẩn giữa 2 ô kia ⛔ được làm đỏ test
    # của phần máy chủ.
    group = order[order.index("section_input"):order.index("column_input")]
    assert {"input_variable", "input_scope", "input_label"} <= set(group), group


# ═══════════════════════════════════════════════════════════════════
# (6) Patch infer_rule_input_variable
# ═══════════════════════════════════════════════════════════════════
PATCH_BASE_VARIABLES = [
    {"name": "glass_thick", "category": "Row Literals",
     "var_label": "Độ dày kính (tên cũ)"},
    {"name": "total_thick_mm", "category": "Row Literals",
     "var_label": "Độ dày kính"},
    {"name": "glass_type", "category": "Row Literals",
     "var_label": "Loại kính"},
    {"name": "width", "category": "Row Literals", "var_label": "Chiều rộng"},
    {"name": "H_mm", "category": "Kích thước", "var_label": "Chiều cao"},
    {"name": "W_mm", "category": "Kích thước", "var_label": "Chiều rộng"},
]

EMPTY_FORMULA_TABLES = (
    "AL Accessory Item", "AL Cost Template Item",
    "AL Quantity Calc Method", "Formula Global Variable",
)


def _patch_setup(rules, item_rows=None, formula_rows=None, variables=None):
    base._reset_stub()
    SET_VALUE_CALLS.clear()
    STUB.set_get_all("AL Rule", list(rules))
    STUB.set_get_all("AL Bom Item", list(item_rows or []))
    STUB.set_get_all(
        "AL Variable Library",
        list(PATCH_BASE_VARIABLES if variables is None else variables))
    for doctype in EMPTY_FORMULA_TABLES:
        STUB.set_get_all(doctype, [])
    for doctype, rows in (formula_rows or {}).items():
        STUB.set_get_all(doctype, list(rows))


def _rule_row(name, result_type="NUMBER", **extra):
    row = {"name": name, "rule_code": name, "result_type": result_type,
           "input_variable": "", "input_scope": "", "input_label": ""}
    row.update(extra)
    return row


def _item_row(name, slug, rule, expr):
    return {"name": name, "slug": slug, "item_rule": rule,
            "rule_input_expr": expr, "rule_input_row": ""}


def test_patch_item_dien_khi_dong_nhat():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[
            _item_row("I1", "nep_tren", "RULE-NEP",
                      "items.kinh_tren.glass_thick"),
            _item_row("I2", "nep_duoi", "RULE-NEP",
                      "items.kinh_duoi.glass_thick"),
        ])
    summary = patch.execute()
    assert summary["rules_to_update"] == 1, summary
    assert summary["rules_written"] == 1, summary
    assert summary["item_rows_written"] == 2, summary
    rule_calls = [c for c in SET_VALUE_CALLS if c[0] == "AL Rule"]
    assert len(rule_calls) == 1, SET_VALUE_CALLS
    _doctype, name, payload, _value = rule_calls[0]
    assert name == "RULE-NEP", rule_calls
    # `glass_thick` là TÊN CŨ (nhãn "Độ dày kính (tên cũ)") ⇒ ghi tên CHUẨN
    # `total_thick_mm` (nhãn "Độ dày kính"); engine alias 2 chiều nên ⛔ đổi số.
    assert payload == {
        "input_variable": "total_thick_mm",
        "input_scope": "ROW",
        "input_label": "Độ dày kính",
    }, payload
    row_calls = {c[1]: c for c in SET_VALUE_CALLS if c[0] == "AL Bom Item"}
    assert row_calls["I1"][2:] == ("rule_input_row", "kinh_tren"), row_calls
    assert row_calls["I2"][2:] == ("rule_input_row", "kinh_duoi"), row_calls


def test_patch_item_giu_glass_thick_khi_library_thieu_ten_chuan():
    """⛔ có `total_thick_mm` trong danh mục ⇒ giữ `glass_thick` (dữ liệu thật)."""
    variables = [row for row in PATCH_BASE_VARIABLES
                 if row["name"] != "total_thick_mm"]
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[_item_row("I1", "nep_tren", "RULE-NEP",
                             "items.kinh_tren.glass_thick")],
        variables=variables)
    summary = patch.execute()
    assert summary["rules_written"] == 1, summary
    payload = SET_VALUE_CALLS[0][2]
    assert payload["input_variable"] == "glass_thick", payload
    assert payload["input_scope"] == "ROW", payload
    assert payload["input_label"] == "Độ dày kính (tên cũ)", payload


def test_patch_item_khong_dien_khi_hai_field_khac_nhau():
    """ĐỐI CHỨNG ÂM: 2 field khác nhau ⇒ ⛔ đoán."""
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[
            _item_row("I1", "nep_tren", "RULE-NEP",
                      "items.kinh_tren.glass_thick"),
            _item_row("I2", "nep_duoi", "RULE-NEP",
                      "items.kinh_duoi.glass_type"),
        ])
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary
    assert summary["item_rows_written"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS
    assert any("NHIỀU field" in item["reason"]
               for item in summary["skipped_detail"]), summary


def test_patch_item_khong_dien_khi_bieu_thuc_la_khong_phai_tham_chieu():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[
            _item_row("I1", "nep_tren", "RULE-NEP", ""),
            _item_row("I2", "nep_duoi", "RULE-NEP",
                      "items.kinh_duoi.glass_thick"),
        ])
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS


def test_patch_item_giu_rule_input_row_da_co():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[{
            "name": "I1", "slug": "nep_tren", "item_rule": "RULE-NEP",
            "rule_input_expr": "items.kinh_tren.glass_thick",
            "rule_input_row": "kinh_duoi",
        }])
    patch.execute()
    assert not [c for c in SET_VALUE_CALLS if c[0] == "AL Bom Item"], \
        SET_VALUE_CALLS


def test_patch_number_dien_khi_moi_loi_goi_cung_token():
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Accessory Item": [
                {"name": "A1",
                 "qty_formula": "lookup_rule('RULE-QTY', H_mm) * n_panel"}],
            "AL Bom Item": [
                {"name": "B1", "qty": "lookup_rule(\"RULE-QTY\", H_mm)"}],
        })
    summary = patch.execute()
    assert summary["rules_written"] == 1, summary
    _doctype, name, payload, _value = SET_VALUE_CALLS[0]
    assert name == "RULE-QTY", SET_VALUE_CALLS
    assert payload["input_variable"] == "H_mm", payload
    assert payload["input_scope"] == "GLOBAL", payload
    assert payload["input_label"] == "Chiều cao", payload


def test_patch_number_khong_dien_khi_hai_token_khac_nhau():
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Accessory Item": [
                {"name": "A1", "qty_formula": "lookup_rule('RULE-QTY', H_mm)"}],
            "AL Bom Item": [
                {"name": "B1", "qty": "lookup_rule('RULE-QTY', W_mm)"}],
        })
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS


def test_patch_number_khong_dien_khi_tham_so_phuc_tap():
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Bom Item": [
                {"name": "B1", "qty": "lookup_rule('RULE-QTY', H_mm / 2)"}],
        })
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary


def test_patch_number_khong_dien_khi_loi_goi_mot_tham_so():
    """Patch ⛔ suy được biến từ lời gọi một tham số ⇒ bỏ qua."""
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Cost Template Item": [
                {"name": "C1", "calc_formula": "lookup_rule('RULE-QTY')"}],
        })
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary


def test_patch_number_quet_du_cac_nguon_cong_thuc():
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Quantity Calc Method": [
                {"name": "M1", "calc_fn": "lookup_rule('RULE-QTY', H_mm)"}],
            "Formula Global Variable": [
                {"name": "G1",
                 "formula_expr": "lookup_rule('RULE-QTY', H_mm) * 2"}],
        })
    summary = patch.execute()
    assert summary["rules_written"] == 1, summary
    assert SET_VALUE_CALLS[0][2]["input_variable"] == "H_mm", SET_VALUE_CALLS


def test_patch_dry_run_khong_ghi():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[_item_row("I1", "nep_tren", "RULE-NEP",
                             "items.kinh_tren.glass_thick")])
    summary = patch.dry_run()
    assert summary["dry_run"] is True, summary
    assert summary["rules_to_update"] == 1, summary
    assert summary["item_rows_to_update"] == 1, summary
    assert summary["planned"]["rules"][0]["input_variable"] == \
        "total_thick_mm", summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS


def _reflect_writes():
    """Mô phỏng DB: áp các lời gọi `set_value` vào dữ liệu stub."""
    for doctype, name, field_or_dict, value in SET_VALUE_CALLS:
        if isinstance(field_or_dict, dict):
            updates = dict(field_or_dict)
        else:
            updates = {field_or_dict: value}
        for row in STUB.get_all_rows.get(doctype, []):
            if row.get("name") == name:
                row.update(updates)
                break


def test_patch_idempotent_lan_hai():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[
            _item_row("I1", "nep_tren", "RULE-NEP",
                      "items.kinh_tren.glass_thick"),
            _item_row("I2", "nep_duoi", "RULE-NEP",
                      "items.kinh_duoi.glass_thick"),
        ])
    first = patch.execute()
    assert first["rules_written"] == 1, first
    _reflect_writes()
    SET_VALUE_CALLS.clear()
    second = patch.execute()
    assert second["rules_written"] == 0, second
    assert second["item_rows_written"] == 0, second
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS


def test_patch_khong_ghi_de_gia_tri_da_co():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM", input_variable="glass_type",
                         input_scope="ROW", input_label="Loại kính")],
        item_rows=[_item_row("I1", "nep_tren", "RULE-NEP",
                             "items.kinh_tren.glass_thick")])
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS


def test_patch_chiu_duoc_bang_cot_thieu():
    """Site chưa migrate / doctype chưa cài ⇒ bỏ nhánh đó, ⛔ chết patch."""
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Bom Item": [
                {"name": "B1", "qty": "lookup_rule('RULE-QTY', H_mm)"}],
        })
    original_get_all = STUB.get_all

    def flaky(doctype, *args, **kwargs):
        if doctype in ("AL Accessory Item", "Formula Global Variable"):
            raise RuntimeError("bảng/cột chưa tồn tại")
        if doctype == "AL Bom Item" and "rule_input_row" in (
                kwargs.get("fields") or []):
            raise RuntimeError("cột rule_input_row chưa tồn tại")
        return original_get_all(doctype, *args, **kwargs)

    STUB.get_all = flaky
    try:
        summary = patch.execute()
    finally:
        STUB.get_all = original_get_all
    assert summary["rules_written"] == 1, summary
    assert SET_VALUE_CALLS[0][2]["input_variable"] == "H_mm", SET_VALUE_CALLS
    # Cột `rule_input_row` thiếu ⇒ chỉ bỏ phần slug, ⛔ lỗi.
    assert summary["errors"] == [], summary


def test_patch_khong_doc_duoc_al_rule_thi_khong_lam_gi():
    base._reset_stub()
    SET_VALUE_CALLS.clear()

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    original_get_all = STUB.get_all
    STUB.get_all = boom
    try:
        summary = patch.execute()
    finally:
        STUB.get_all = original_get_all
    assert summary["rules_to_update"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS


# ═══════════════════════════════════════════════════════════════════
# (7) Biến theo dòng engine KHÔNG đọc được ở bước chọn mã
# ═══════════════════════════════════════════════════════════════════
#: ĐÚNG hợp khoá `glass_data` ∪ `row_literals` mà b2 nạp cho mỗi dòng.
ROW_RESOLVABLE_EXPECTED = frozenset({
    "total_thick_mm", "glass_thick", "glass_type", "max_area_m2",
    "glass_name", "glass_type_name",
    "weight_per_unit", "unit_price", "calc_pattern", "item_code",
    "scrap_pct", "has_weight", "color", "supplier_location",
    "install_position", "cut_angle", "note",
})


def test_row_resolvable_variables_dung_hop_engine_doc():
    assert rule_input.ROW_RESOLVABLE_VARIABLES == ROW_RESOLVABLE_EXPECTED, \
        sorted(rule_input.ROW_RESOLVABLE_VARIABLES)
    for name in ROW_RESOLVABLE_EXPECTED:
        assert rule_input.is_row_variable_resolvable(name), name
    # Biến là KẾT QUẢ công thức / cột không nằm trong 2 nguồn ⇒ ⛔ đọc được.
    for name in ("width", "height", "qty", "unit_qty", "total_qty",
                 "line_total"):
        assert not rule_input.is_row_variable_resolvable(name), name
    assert rule_input.is_row_variable_resolvable(" glass_type "), (
        "phải bỏ khoảng trắng trước khi so")
    assert not rule_input.is_row_variable_resolvable(""), "chuỗi rỗng"


API_VARIABLES = [
    {"name": "width", "category": "Row Literals", "var_label": "Chiều rộng"},
    {"name": "unit_qty", "category": "Row Literals",
     "var_label": "SL đơn vị"},
    {"name": "total_thick_mm", "category": "Row Literals",
     "var_label": "Độ dày kính"},
    {"name": "glass_type", "category": "Row Literals",
     "var_label": "Loại kính"},
    {"name": "H_mm", "category": "Kích thước", "var_label": "Chiều cao (mm)"},
]


def _api_with_variables(rows=None, permitted=True):
    base._reset_stub()
    STUB.set_get_all("AL Variable Library", list(rows or API_VARIABLES))
    original_permission = getattr(STUB, "has_permission", None)
    STUB.has_permission = lambda *args, **kwargs: permitted
    import alumglass.api as api

    return api, original_permission


def _restore_api(original_permission):
    if original_permission is None:
        if hasattr(STUB, "has_permission"):
            del STUB.has_permission
    else:
        STUB.has_permission = original_permission
    base._reset_stub()


def test_api_get_rule_input_variables_co_co_resolvable():
    api, original = _api_with_variables()
    try:
        rows = api.get_rule_input_variables()
    finally:
        _restore_api(original)
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {"width", "unit_qty", "total_thick_mm",
                            "glass_type", "H_mm"}, by_name
    # width/unit_qty KHÔNG đọc được ở bước chọn mã.
    assert by_name["width"]["resolvable"] is False, by_name["width"]
    assert by_name["unit_qty"]["resolvable"] is False, by_name["unit_qty"]
    for name in ("total_thick_mm", "glass_type", "H_mm"):
        assert by_name[name]["resolvable"] is True, by_name[name]
    assert by_name["width"]["scope"] == "ROW", by_name["width"]
    assert by_name["H_mm"]["scope"] == "GLOBAL", by_name["H_mm"]
    assert by_name["glass_type"]["label"] == "Loại kính", by_name["glass_type"]
    assert by_name["H_mm"]["category"] == "Kích thước", by_name["H_mm"]
    # Sắp xếp: đọc được TRƯỚC (theo nhãn), rồi không đọc được (theo nhãn).
    assert [row["name"] for row in rows] == [
        "H_mm", "glass_type", "total_thick_mm", "width", "unit_qty"], rows
    assert [row["resolvable"] for row in rows] == [
        True, True, True, False, False], rows


def test_api_get_rule_input_variables_kiem_quyen():
    api, original = _api_with_variables(permitted=False)
    try:
        try:
            api.get_rule_input_variables()
        except (STUB.ValidationError, STUB.PermissionError) as exc:
            assert "không có quyền" in str(exc), exc
        else:
            raise AssertionError("thiếu quyền đọc AL Rule mà API vẫn trả dữ liệu")
    finally:
        _restore_api(original)


def test_rule_validate_canh_bao_bien_khong_doc_duoc():
    """⛔ throw; một msgprint nêu đúng việc cần làm."""
    STUB.set_get_all("AL Variable Library", VARIABLES)
    MSGPRINTS.clear()
    rule = _rule(input_variable="width", input_label="")
    rule.validate()  # ⛔ được throw
    assert rule.input_scope == "ROW", rule.input_scope
    assert rule.input_label == "Chiều rộng", rule.input_label
    assert len(MSGPRINTS) == 1, MSGPRINTS
    message = MSGPRINTS[0]["message"]
    # Câu TRUNG TÍNH: nêu nhãn biến đang chọn + ô "Tra theo" (danh sách đã
    # lọc đúng dữ liệu engine đọc được), ⛔ kể tên "Độ dày kính / Loại kính".
    assert message == (
        "Dữ liệu tra 'Chiều rộng' chưa có giá trị ở bước chọn mã nên quy tắc sẽ "
        "không tra được — chọn một dữ liệu khác trong ô <b>Tra theo</b> "
        "(danh sách chỉ mời dữ liệu hệ thống đọc được ở bước chọn mã)."), \
        message
    assert "Độ dày kính" not in message and "Loại kính" not in message, message
    assert "AL Rule" in (MSGPRINTS[0]["title"] or ""), MSGPRINTS


def test_rule_validate_bien_doc_duoc_thi_khong_canh_bao():
    """ĐỐI CHỨNG ÂM: biến engine đọc được ⇒ ⛔ cảnh báo."""
    STUB.set_get_all("AL Variable Library", VARIABLES)
    MSGPRINTS.clear()
    rule = _rule(input_variable="glass_type", input_label="")
    rule.validate()
    assert MSGPRINTS == [], MSGPRINTS
    assert rule.input_scope == "ROW", rule.input_scope


def test_preview_tra_kem_input_resolvable():
    STUB.set_get_all("AL Variable Library", VARIABLES)
    rows = [{"from_value": 0, "to_value": 10, "result_value": 1}]

    bad = _rule(rule_type="THRESHOLD", input_variable="width",
                input_scope="ROW", input_label="Chiều rộng",
                threshold_rows=rows).preview(5)
    assert bad["input_resolvable"] is False, bad

    good = _rule(rule_type="THRESHOLD", input_variable="glass_type",
                 input_scope="ROW", input_label="Loại kính",
                 threshold_rows=rows).preview(5)
    assert good["input_resolvable"] is True, good

    legacy = _rule(rule_type="THRESHOLD", threshold_rows=rows).preview(5)
    assert legacy["input_resolvable"] is True, legacy


def test_patch_item_bo_qua_bien_khong_doc_duoc():
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[_item_row("I1", "nep_tren", "RULE-NEP",
                             "items.kinh_tren.width")])
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS
    assert any("không đọc được" in item["reason"]
               for item in summary["skipped_detail"]), summary


def test_patch_item_van_dien_bien_doc_duoc():
    """Đối chứng dương: `glass_type` (đọc được) vẫn được điền."""
    _patch_setup(
        rules=[_rule_row("RULE-NEP", "ITEM")],
        item_rows=[_item_row("I1", "nep_tren", "RULE-NEP",
                             "items.kinh_tren.glass_type")])
    summary = patch.execute()
    assert summary["rules_written"] == 1, summary
    assert SET_VALUE_CALLS[0][2]["input_variable"] == "glass_type", \
        SET_VALUE_CALLS


def test_patch_number_bo_qua_token_bien_dong():
    """Token biến theo dòng ⇒ ⛔ suy thành "quy tắc tra theo" của công thức."""
    _patch_setup(
        rules=[_rule_row("RULE-QTY")],
        formula_rows={
            "AL Accessory Item": [
                {"name": "A1",
                 "qty_formula": "lookup_rule('RULE-QTY', glass_type)"}],
        })
    summary = patch.execute()
    assert summary["rules_written"] == 0, summary
    assert SET_VALUE_CALLS == [], SET_VALUE_CALLS
    assert any("biến theo dòng" in item["reason"]
               for item in summary["skipped_detail"]), summary


# ═══════════════════════════════════════════════════════════════════
# (8) §7.6 — THIẾU NGUỒN DỮ LIỆU TRA (vòng UX thứ 2 chấm CHẶN)
# ═══════════════════════════════════════════════════════════════════
#: Câu cảnh báo/giải thích ⛔ được chứa bất kỳ thứ kỹ thuật nào dưới đây.
KY_THUAT_CAM = ("items.", "glass_thick", "glass_type", "rule_input_row",
                "rule_input_expr", "RULE-NEP", "kinh_duoi", "kinh_tren")


def _missing_parts(item_extra=None, rule=None, **orch_kwargs):
    """Dựng parts của 1 dòng Rule theo kịch bản §7.6."""
    data = {
        "result_type": "ITEM", "input_variable": "glass_thick",
        "input_scope": "ROW", "input_label": "Độ dày kính",
        "rule_name": "Chọn nẹp",
    }
    data.update(rule or {})
    _register_rule("RULE-NEP", **data)
    kwargs = {
        "bom_items": [{"slug": "kinh_tren", "line_name": "Kính trên"}],
        "glass_data": {"kinh_tren": {"glass_thick": 10}},
        "rule_names": {"RULE-NEP": "Chọn nẹp"},
    }
    kwargs.update(orch_kwargs)
    orch = _orch(**kwargs)
    item = dict(ITEM_ROW)
    item.update(item_extra or {})
    return orch, orch._rule_trace_parts(item)


def test_missing_no_source_row_cau_va_co():
    """ROW, chưa chọn dòng ⇒ câu "chưa chọn dòng lấy …", giữ biến + phạm vi."""
    orch, parts = _missing_parts()
    assert parts["input_missing"] == "no_source_row", parts
    # Bất biến §7.6 (1): input_variable/scope KHÔNG rơi mất.
    assert parts["input_variable"] == "glass_thick", parts
    assert parts["input_scope"] == "ROW", parts
    assert parts["input_found"] is False, parts
    text = orch._rule_trace_text(parts)
    assert text == (
        'Chọn mã theo quy tắc "Chọn nẹp" nhưng chưa chọn dòng lấy Độ dày '
        "kính — chọn dòng chứa dữ liệu trong bộ BOM."), text
    assert "không có mã nào khớp" not in text, text


def test_missing_no_source_row_rule_chua_dat_ten():
    """Quy tắc chưa đặt tên ⇒ "Chọn mã theo quy tắc nhưng …" (⛔ ngoặc rỗng)."""
    orch, parts = _missing_parts(rule={"rule_name": ""},
                                 rule_names={})
    text = orch._rule_trace_text(parts)
    assert text == (
        "Chọn mã theo quy tắc nhưng chưa chọn dòng lấy Độ dày kính — chọn "
        "dòng chứa dữ liệu trong bộ BOM."), text
    assert '""' not in text, text


def test_missing_row_gone_cau_va_co():
    """Dòng nguồn đã mất khỏi bộ BOM ⇒ câu "không còn trong bộ BOM"."""
    orch, parts = _missing_parts({"rule_input_row": "kinh_duoi"})
    assert parts["input_missing"] == "row_gone", parts
    assert parts["ref_slug"] == "kinh_duoi", parts
    text = orch._rule_trace_text(parts)
    assert text == (
        "Dòng đã chọn để lấy Độ dày kính không còn trong bộ BOM — chọn lại "
        "dòng lấy dữ liệu."), text
    assert "kinh_duoi" not in text, text


def test_missing_row_no_data_cau_va_co():
    """Dòng nguồn CÓ nhưng không mang biến ⇒ câu nêu tên dòng + lối xử lý."""
    orch, parts = _missing_parts(
        {"rule_input_row": "kinh_tren"},
        rule={"input_variable": "glass_type", "input_label": "Loại kính"})
    assert parts["input_missing"] == "row_no_data", parts
    assert parts["ref_slug"] == "kinh_tren", parts
    text = orch._rule_trace_text(parts)
    assert text == (
        'Dòng "Kính trên" không có Loại kính — chọn dòng khác hoặc bổ sung '
        "dữ liệu cho dòng đó."), text
    assert "kinh_tren" not in text, text


def test_missing_row_no_data_khong_biet_ten_dong_thi_khong_neu_slug():
    """ĐỐI CHỨNG ÂM: dòng nguồn không có tên ⇒ "Dòng đã chọn …", ⛔ slug."""
    orch, parts = _missing_parts(
        {"rule_input_row": "kinh_tren"},
        rule={"input_variable": "glass_type", "input_label": "Loại kính"},
        bom_items=[{"slug": "kinh_tren"}])  # ⛔ line_name
    text = orch._rule_trace_text(parts)
    assert text == (
        "Dòng đã chọn không có Loại kính — chọn dòng khác hoặc bổ sung dữ "
        "liệu cho dòng đó."), text
    assert "kinh_tren" not in text and '""' not in text, text


def test_missing_no_global_value_cau_va_co():
    orch, parts = _missing_parts(
        rule={"input_variable": "H_mm", "input_scope": "GLOBAL",
              "input_label": "Chiều cao"},
        inputs={"W_mm": 900}, glass_data={})
    assert parts["input_missing"] == "no_global_value", parts
    assert parts["input_variable"] == "H_mm", parts
    assert parts["input_scope"] == "GLOBAL", parts
    text = orch._rule_trace_text(parts)
    assert text == (
        "Chưa có Chiều cao cho lượt tính này nên chưa chọn được mã — kiểm "
        "tra thông số đầu vào của báo giá."), text
    assert "H_mm" not in text, text


def test_missing_khong_nhan_nao_lo_ky_thuat():
    """Gom 4 nhánh: ⛔ mã rule / slug / tên field / `items.` trong câu."""
    cases = [
        _missing_parts()[1],
        _missing_parts({"rule_input_row": "kinh_duoi"})[1],
        _missing_parts({"rule_input_row": "kinh_tren"},
                       rule={"input_variable": "glass_type",
                             "input_label": "Loại kính"})[1],
    ]
    orch = _orch()
    for parts in cases:
        text = orch._rule_trace_text(parts)
        for bad in KY_THUAT_CAM:
            assert bad not in text, (bad, text)
        raw = orch._rule_trace_text_raw(parts)
        # Bản kỹ thuật GIỮ dạng cũ nhưng phải nói rõ chưa có nguồn.
        assert "(chưa có nguồn)" in raw, raw


def test_missing_co_expr_lui_duoc_thi_giu_hanh_vi_cu():
    """ĐỐI CHỨNG ÂM: có `rule_input_expr` lùi được ⇒ ⛔ gắn missing."""
    _register_rule(
        "RULE-NEP", result_type="ITEM", input_variable="glass_thick",
        input_scope="ROW", input_label="Độ dày kính", rule_name="Chọn nẹp")
    orch = _orch(
        glass_data={"kinh_tren": {"glass_thick": 10}},
        resolved={("RULE-NEP", 10): "NEP-10"},
        rule_names={"RULE-NEP": "Chọn nẹp"},
        item_names={"NEP-10": "Nẹp 10"})
    parts = orch._rule_trace_parts(dict(
        ITEM_ROW, rule_input_expr="items.kinh_tren.glass_thick"))
    assert parts["input_missing"] == "", parts
    assert parts["input_found"] is True, parts
    text = orch._rule_trace_text(parts)
    assert "không có mã nào khớp" not in text, text
    assert '"Nẹp 10" (NEP-10)' in text, text


def test_co_gia_tri_nhung_bang_quy_tac_khong_phu_van_la_khong_khop():
    """§7.6 dòng cuối: ĐÃ có giá trị, bảng không phủ ⇒ GIỮ câu "không khớp"."""
    orch, parts = _missing_parts(
        {"rule_input_row": "kinh_tren"},
        resolved={},  # bảng quy tắc ⛔ phủ giá trị 10
    )
    assert parts["input_missing"] == "", parts
    assert parts["input_found"] is True, parts
    text = orch._rule_trace_text(parts)
    assert text == (
        'Độ dày kính của dòng "Kính trên" = 10 mm → không có mã nào khớp · '
        'theo quy tắc "Chọn nẹp".'), text


def test_missing_global_con_bieu_thuc_cu_van_la_thieu_nguon():
    """GLOBAL ⛔ có đường lùi `rule_input_expr` ⇒ vẫn là thiếu nguồn.

    Engine chỉ đọc `inputs` của lượt tính cho biến toàn cục; biểu thức cũ
    KHÔNG được dùng. Vì vậy câu "không có mã nào khớp" ở đây là giải thích
    sai (bảng quy tắc chưa hề được hỏi).
    """
    orch, parts = _missing_parts(
        {"rule_input_expr": "items.kinh_tren.glass_thick"},
        rule={"input_variable": "H_mm", "input_scope": "GLOBAL",
              "input_label": "Chiều cao"},
        inputs={}, glass_data={})
    assert parts["input_missing"] == "no_global_value", parts
    text = orch._rule_trace_text(parts)
    assert "không có mã nào khớp" not in text, text
    assert "kiểm tra thông số đầu vào" in text, text


def test_rule_source_flags_tach_hai_trang_thai():
    """Cờ: `rule_input_missing` (chưa khai) ≠ `rule_source_missing` (thiếu nguồn)."""
    Flags = eo.BomOrchestrator._rule_source_flags
    # (a) Quy tắc CÓ khai, thiếu nguồn.
    _, declared = _missing_parts()
    flags = Flags(declared, True)
    assert flags["rule_input_missing"] == 0, flags
    assert flags["rule_source_missing"] == 1, flags
    assert flags["rule_missing_reason"] == "no_source_row", flags
    assert flags["rule_input_found"] is False, flags
    assert flags["rule_input_label"] == "Độ dày kính", flags

    # (b) Quy tắc CHƯA khai gì cả (không biến) + dòng không biểu thức.
    _register_rule("RULE-NEP", result_type="ITEM")
    orch = _orch(rule_names={})
    parts = orch._rule_trace_parts(dict(ITEM_ROW))
    flags = Flags(parts, True)
    assert flags["rule_input_missing"] == 1, flags
    assert flags["rule_source_missing"] == 0, flags
    assert flags["rule_missing_reason"] == "", flags
    assert orch._rule_trace_text(parts) == \
        "Dòng này chưa khai báo quy tắc chọn mã.", parts

    # (c) Đọc được đủ ⇒ cả hai cờ 0.
    _, ok = _missing_parts(
        {"rule_input_row": "kinh_tren"},
        resolved={("RULE-NEP", 10): "NEP-10"})
    flags = Flags(ok, True)
    assert (flags["rule_input_missing"], flags["rule_source_missing"]) == (0, 0), flags
    assert flags["rule_input_found"] is True, flags

    # (d) Dòng KHÔNG chọn mã theo Rule ⇒ ⛔ mang cờ của dòng Rule.
    flags = Flags({"input_missing": "no_source_row",
                   "input_variable": "glass_thick"}, False)
    assert flags["rule_source_missing"] == 0, flags
    assert flags["rule_input_missing"] == 0, flags


# ═══════════════════════════════════════════════════════════════════
# (9) Engine: cảnh báo `dynamic_rule_thieu_nguon:*` + cờ trên dòng kết quả
# ═══════════════════════════════════════════════════════════════════
RULE_SOURCE_GLASS = {
    "slug": "kinh_tren", "line_name": "Kính trên", "item_code": "KINH-01",
    "price_base_item": "", "default_glass_master": "",
    "item_selection_mode": "Manual", "category": "VL_KINH",
    "cost_bucket": "VL_KINH", "calc_pattern": "AREA",
    "width": "2000", "height": "1000", "qty": "2",
    "show_condition": "", "item_condition_formula": "", "rule_input_expr": "",
}

RULE_SOURCE_NEP = {
    "slug": "nep", "line_name": "Nẹp kính", "item_code": "",
    "price_base_item": "", "default_glass_master": "",
    "item_selection_mode": "Rule", "item_rule": "RULE-NEP",
    "rule_input_expr": "", "category": "VL_NHOM", "cost_bucket": "VL_NHOM",
    "calc_pattern": "LENGTH_ONLY", "width": "1000", "height": "0", "qty": "1",
    "show_condition": "", "item_condition_formula": "",
}


def _prepare_rule_source_orch(rule_row_extra=None, rule_extra=None):
    """Fixture engine: dòng kính GM-01 8 mm + 1 dòng chọn mã theo Rule."""
    base._prepare_orchestrator()
    st = base._STUB
    rule_row = dict(RULE_SOURCE_NEP)
    rule_row.update(rule_row_extra or {})
    st.set_doc("AL BOM Version", "ALBOMV-1", {
        "bom": "BOM-1",
        "bom_set_snapshot": json.dumps(
            {"items": [RULE_SOURCE_GLASS, rule_row]}),
        "cost_template_snapshot": json.dumps({"items": []}),
    })
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom": "BOM-1", "al_bom_version": "ALBOMV-1", "parent": "QTN-1",
        "al_bom_vars": json.dumps({
            "extra_vars": {},
            "glass_master_map": {"__slug__kinh_tren": "GM-01"}}),
    })
    st.set_get_all("Item", [
        {"name": "KINH-01", "weight_per_unit": 15.0,
         "item_name": "Kính cường lực"},
        {"name": "GM-01", "weight_per_unit": 15.0,
         "item_name": "Kính trắng 8 mm"},
        {"name": "NEP-8", "weight_per_unit": 0.5, "item_name": "Nẹp 8"},
    ])
    st.set_get_all("Item Price", [
        {"name": "IP-0", "item_code": "GM-01", "price_list_rate": 300000,
         "price_list": "Standard Selling"},
        {"name": "IP-1", "item_code": "KINH-01", "price_list_rate": 300000,
         "price_list": "Standard Selling"},
        {"name": "IP-3", "item_code": "NEP-8", "price_list_rate": 50000,
         "price_list": "Standard Selling"},
    ])
    st.set_get_all("AL Glass Master", [
        {"name": "GM-01", "glass_name": "Kính trắng 8 mm",
         "total_thick_mm": 8, "glass_type": "Clear", "max_area_m2": 6.6}])
    st.set_get_all("AL Glass Type", [
        {"name": "Clear", "type_name": "Kính trong"}])
    st.set_get_all("AL Quantity Calc Method", [
        {"name": "AREA", "output_unit": "m²",
         "calc_pattern_name": "Tính theo diện tích"},
        {"name": "LENGTH_ONLY", "output_unit": "m",
         "calc_pattern_name": "Tính theo chiều dài"},
    ])
    st.set_get_all("AL Material Category", [
        {"name": "VL_KINH", "default_scrap_pct": 0.03,
         "requires_glass_master": 1},
        {"name": "VL_NHOM", "default_scrap_pct": 0.02},
    ])
    rule = {
        "rule_name": "Chọn nẹp", "result_type": "ITEM",
        "rule_type": "THRESHOLD", "is_active": 1,
        "input_variable": "glass_thick", "input_scope": "ROW",
        "input_label": "Độ dày kính",
        "threshold_rows": [
            {"from_value": 0, "to_value": 10, "result_item": "NEP-8"}],
        "resolve": lambda value: "NEP-%d" % int(value),
    }
    rule.update(rule_extra or {})
    st.set_doc("AL Rule", "RULE-NEP", rule)
    return base.BomOrchestrator("QI-0001")


def _run_b2(orch):
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    return orch


def _run_to_b4_rule_source(orch):
    _run_b2(orch)
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    return orch


def _rule_source_warnings(orch):
    return {k: v for k, v in orch.bom_engine_errors.items()
            if k.startswith("dynamic_rule_thieu_nguon:")}


def test_b2_canh_bao_dynamic_rule_thieu_nguon():
    """ROW thiếu dòng nguồn ⇒ cảnh báo engine ra `errors` (⛔ im lặng)."""
    orch = _run_b2(_prepare_rule_source_orch())
    warnings = _rule_source_warnings(orch)
    key = "dynamic_rule_thieu_nguon:RULE-NEP:nep"
    assert key in warnings, warnings
    message = warnings[key]
    assert "Nẹp kính" in message, message          # tên DÒNG
    assert "Độ dày kính" in message, message       # nhãn dữ liệu thiếu
    assert "Chọn dòng lấy dữ liệu" in message, message
    assert "thành tiền chưa đúng" in message, message
    for bad in ("nep\"", "RULE-NEP", "glass_thick", "rule_input_row"):
        assert bad not in message, (bad, message)


def test_b2_khong_canh_bao_khi_resolve_duoc():
    """ĐỐI CHỨNG ÂM: chọn đúng dòng ⇒ resolve ra mã, ⛔ cảnh báo thiếu nguồn."""
    orch = _run_b2(_prepare_rule_source_orch({"rule_input_row": "kinh_tren"}))
    assert _rule_source_warnings(orch) == {}, orch.bom_engine_errors
    assert orch.row_literals["nep"]["item_code"] == "NEP-8", \
        orch.row_literals["nep"]


def test_b2_canh_bao_rule_chua_khai_tra_theo_gi():
    """Quy tắc CŨ: chưa khai biến + dòng không biểu thức ⇒ cảnh báo RIÊNG."""
    orch = _run_b2(_prepare_rule_source_orch(rule_extra={
        "input_variable": "", "input_scope": "", "input_label": ""}))
    warnings = _rule_source_warnings(orch)
    key = "dynamic_rule_thieu_nguon:RULE-NEP:nep"
    assert key in warnings, warnings
    assert "chưa khai tra theo dữ liệu nào" in warnings[key], warnings[key]
    assert '"Tra theo"' in warnings[key], warnings[key]


def test_b4_dong_thieu_nguon_co_co_va_item_code_rong():
    """Dòng kết quả: thiếu nguồn ⇒ cờ đúng, `item_code` RỖNG (⛔ slug)."""
    orch = _run_to_b4_rule_source(_prepare_rule_source_orch())
    line = {row["slug"]: row for row in orch.bom_result}["nep"]
    assert line["item_code"] == "", line
    assert line["rule_source_missing"] == 1, line
    assert line["rule_input_missing"] == 0, line
    assert line["rule_missing_reason"] == "no_source_row", line
    assert line["rule_input_found"] is False, line
    assert line["rule_input_label"] == "Độ dày kính", line
    assert "chưa chọn dòng lấy Độ dày kính" in line["rule_trace"], line
    assert "nep" not in line["rule_trace"], line["rule_trace"]


def test_b4_dong_chua_khai_gi_ca_thi_co_rule_input_missing():
    """ĐỐI CHỨNG ÂM của cờ: quy tắc chưa khai ⇒ `rule_input_missing` = 1."""
    orch = _run_to_b4_rule_source(_prepare_rule_source_orch(rule_extra={
        "input_variable": "", "input_scope": "", "input_label": ""}))
    line = {row["slug"]: row for row in orch.bom_result}["nep"]
    assert line["rule_input_missing"] == 1, line
    assert line["rule_source_missing"] == 0, line
    assert line["rule_missing_reason"] == "", line
    assert line["rule_trace"] == "Dòng này chưa khai báo quy tắc chọn mã.", line


# ═══════════════════════════════════════════════════════════════════
# (10) `explain_bom_line` — bước "Chọn mã vật tư" theo trạng thái nguồn
# ═══════════════════════════════════════════════════════════════════
EXPLAIN_TRACE = (
    'Chọn mã theo quy tắc "Chọn nẹp" nhưng chưa chọn dòng lấy Độ dày kính '
    "— chọn dòng chứa dữ liệu trong bộ BOM.")


def _explain(line_extra):
    line = {
        "slug": "nep", "line_label": "Nẹp kính",
        "item_selection_mode": "Rule", "item_rule": "RULE-NEP",
        "rule_name": "Chọn nẹp", "rule_input_label": "Độ dày kính",
        "item_code": "", "line_total": 0, "unit_price": 0,
        "lookup_facts": {"code_source": "rule", "glass_used": 0},
        "price_trace": "",
    }
    line.update(line_extra)
    base._reset_stub()
    STUB.has_permission = lambda *args, **kwargs: True
    import alumglass.api as api
    try:
        return api.explain_bom_line(
            "new-preview", "nep", result_json=json.dumps({"lines": [line]}),
            parent="QTN-1")
    finally:
        del STUB.has_permission
        base._reset_stub()


def _step(result, key):
    for step in result["steps"]:
        if step["key"] == key:
            return step
    return None


def test_explain_thieu_nguon_cau_warning_va_missing():
    out = _explain({
        "rule_trace": EXPLAIN_TRACE, "rule_source_missing": 1,
        "rule_missing_reason": "no_source_row", "rule_input_found": False,
    })
    step = _step(out, "item_code")
    assert step is not None, out
    assert step["detail"] == EXPLAIN_TRACE, step
    assert step.get("severity") == "warning", step
    assert "item_code" in out["missing"], out
    # ⛔ bước "quy tắc khớp" giả: bảng quy tắc chưa hề được hỏi.
    assert _step(out, "rule") is None, out
    # Thành tiền = 0 mà có cảnh báo ⇒ client biết số 0 này ⛔ đáng tin.
    assert out.get("warn_zero_price") is True, out


def test_explain_chua_khai_tra_theo_cau_cho_quan_tri():
    out = _explain({
        "rule_input_missing": 1, "rule_source_missing": 0})
    step = _step(out, "item_code")
    assert step is not None, out
    assert "chưa khai tra theo dữ liệu nào" in step["detail"], step
    assert '"Tra theo"' in step["detail"], step
    assert "viết công thức" not in step["detail"], step
    assert "item_code" in out["missing"], out
    assert _step(out, "rule") is not None, out


def test_explain_dong_binh_thuong_khong_warning():
    """ĐỐI CHỨNG ÂM: có mã + không thiếu nguồn ⇒ ⛔ warning ở bước chọn mã."""
    out = _explain({
        "item_code": "NEP-8", "rule_trace": (
            'Độ dày kính của dòng "Kính trên" = 8 mm → "Nẹp 8" (NEP-8) · '
            'theo quy tắc "Chọn nẹp".')})
    step = _step(out, "item_code")
    assert step is not None, out
    assert "severity" not in step, step
    assert "item_code" not in out["missing"], out


def test_result_display_tra_du_co_cho_client():
    """`get_result_display` phải chở cờ trạng thái nguồn ra client."""
    import alumglass.api as api
    base._reset_stub()
    STUB.has_permission = lambda *args, **kwargs: True
    STUB.set_doc("Quotation Item", "QI-9", {"parent": "QTN-1"})
    data = {"lines": [{
        "slug": "nep", "line_label": "Nẹp kính", "item_code": "",
        "rule_trace": EXPLAIN_TRACE, "rule_input_label": "Độ dày kính",
        "rule_input_found": 0, "rule_input_missing": 0,
        "rule_source_missing": 1, "rule_missing_reason": "no_source_row",
    }]}
    try:
        out = api.get_result_display(
            "QI-9", result_json=json.dumps(data))
    finally:
        del STUB.has_permission
        base._reset_stub()
    line = out["lines"][0]
    assert line["rule_source_missing"] == 1, line
    assert line["rule_missing_reason"] == "no_source_row", line
    assert line["rule_input_found"] is False, line
    assert line["rule_input_label"] == "Độ dày kính", line
    assert line["rule_trace"] == EXPLAIN_TRACE, line


# ═══════════════════════════════════════════════════════════════════
# (11) `get_rule_input_variables` — cờ `computed` (§7.6)
# ═══════════════════════════════════════════════════════════════════
COMPUTED_VARIABLES = [
    {"name": "total_thick_mm", "category": "Row Literals",
     "var_label": "Độ dày kính"},
    {"name": "glass_type", "category": "Row Literals",
     "var_label": "Loại kính"},
    {"name": "weight_per_unit", "category": "Row Literals",
     "var_label": "Trọng lượng riêng"},
    {"name": "unit_price", "category": "Row Literals",
     "var_label": "Đơn giá"},
    {"name": "width", "category": "Row Literals", "var_label": "Chiều rộng"},
    {"name": "H_mm", "category": "Kích thước", "var_label": "Chiều cao"},
]


def test_api_get_rule_input_variables_co_computed():
    api, original = _api_with_variables(rows=COMPUTED_VARIABLES)
    try:
        rows = api.get_rule_input_variables()
    finally:
        _restore_api(original)
    by_name = {row["name"]: row for row in rows}
    # Field của AL Glass Master ⇒ ⛔ "engine tính từ dòng".
    for name in ("total_thick_mm", "glass_type"):
        assert by_name[name]["computed"] is False, by_name[name]
    # Biến engine nạp cho MỌI dòng BOM ⇒ computed.
    for name in ("weight_per_unit", "unit_price"):
        assert by_name[name]["computed"] is True, by_name[name]
    # Không đọc được ở bước chọn mã ⇒ ⛔ computed (đã có `resolvable=False`).
    assert by_name["width"]["computed"] is False, by_name["width"]
    # Biến toàn cục ⇒ ⛔ computed.
    assert by_name["H_mm"]["computed"] is False, by_name["H_mm"]
    # Các key cũ giữ nguyên.
    assert by_name["total_thick_mm"]["resolvable"] is True, by_name


def test_variable_library_json_co_title_field():
    """§7.6/I — ô Link "Tra theo" phải hiện NHÃN, ⛔ mã biến."""
    path = os.path.join(
        _REPO_ROOT, "alumglass", "al_master_data", "doctype",
        "al_variable_library", "al_variable_library.json")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["title_field"] == "var_label", data.get("title_field")
    assert data["search_fields"] == "var_label,var_name", \
        data.get("search_fields")
    assert data["show_title_field_in_link"] == 1, \
        data.get("show_title_field_in_link")
    # ⛔ đổi fieldname nào.
    names = {field["fieldname"] for field in data["fields"]}
    assert {"var_name", "var_label", "category"} <= names, names


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
