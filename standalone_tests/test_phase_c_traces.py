# -*- coding: utf-8 -*-
"""PHASE 2 — test standalone cho `rule_trace` / `price_trace` + alias B3.

File này DÙNG LẠI stub của `standalone_tests/test_phase_b_fbmax.py` (cùng
FakeFrappe/FakeDB + `_prepare_orchestrator`) — import module đó trước để cài
stub `frappe`, rồi thay snapshot BOM bằng bộ dòng có kính + 2 dòng Rule.

Vì sao đặt ở `standalone_tests/` (ngoài package `alumglass/`)
──────────────────────────────────────────────────────────────
`bench run-tests` walk toàn bộ package `alumglass/`; file stub frappe nằm
trong đó sẽ phá cả lượt chạy test của site. Thư mục này nằm ngoài package.

CÁCH CHẠY (không cần site):
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=/home/nxc/myfrappe/apps \\
        /home/nxc/myfrappe/env/bin/python standalone_tests/test_phase_c_traces.py

Phủ:
  - B3 bơm `{slug}__total_thick_mm` / `{slug}__max_area_m2` → công thức
    width/qty dùng `items.X.total_thick_mm` / `items.X.max_area_m2` ra ĐÚNG số.
  - `rule_trace` đúng cho dòng Rule (2 tên biến cùng giá trị) và "" cho dòng
    Fixed.
  - `price_trace` có mã + bảng giá + dòng Item Price + giá.
  - Dữ liệu vết đi vào JSON lưu kết quả (`b7_save_results`).
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_phase_b_fbmax as base  # noqa: E402  (cài stub frappe khi import)

BomOrchestrator = base.BomOrchestrator

# Dòng kính dùng CHÍNH các biến mới trong công thức width/qty:
#   width = items.kinh_tren.total_thick_mm * 100  → 8 × 100 = 800
#   qty   = items.kinh_tren.max_area_m2           → 6.6
GLASS_ITEM = {
    "slug": "kinh_tren", "line_name": "Kính trên",
    "item_code": "KINH-01", "price_base_item": "",
    # Kính chọn theo VỊ TRÍ (glass_master_map) — đường thật của dialog: rep là
    # khoá `__slug__…` vì dòng không cấu hình default_glass_master.
    "default_glass_master": "", "item_selection_mode": "Manual",
    "category": "VL_KINH", "cost_bucket": "VL_KINH", "calc_pattern": "AREA",
    "width": "items.kinh_tren.total_thick_mm * 100",
    "height": "1000",
    "qty": "items.kinh_tren.max_area_m2",
    "show_condition": "", "item_condition_formula": "", "rule_input_expr": "",
}

# Hai dòng Rule CÙNG rule + CÙNG dòng kính, khác TÊN biến (chuẩn / alias cũ)
# → phải resolve ra CÙNG item_code.
RULE_ITEM_NEW_NAME = {
    "slug": "nep_moi", "line_name": "Nẹp mới",
    "item_code": "", "price_base_item": "",
    "default_glass_master": "", "item_selection_mode": "Rule",
    "item_rule": "RULE-NEP",
    "rule_input_expr": "items.kinh_tren.total_thick_mm",
    "category": "VL_NHOM", "cost_bucket": "VL_NHOM",
    "calc_pattern": "LENGTH_ONLY",
    "width": "1000", "height": "0", "qty": "1",
    "show_condition": "", "item_condition_formula": "",
}
RULE_ITEM_OLD_NAME = {
    "slug": "nep_cu", "line_name": "Nẹp cũ",
    "item_code": "", "price_base_item": "",
    "default_glass_master": "", "item_selection_mode": "Rule",
    "item_rule": "RULE-NEP",
    "rule_input_expr": "items.kinh_tren.glass_thick",
    "category": "VL_NHOM", "cost_bucket": "VL_NHOM",
    "calc_pattern": "LENGTH_ONLY",
    "width": "1000", "height": "0", "qty": "1",
    "show_condition": "", "item_condition_formula": "",
}
BOM_ITEMS = [GLASS_ITEM, RULE_ITEM_NEW_NAME, RULE_ITEM_OLD_NAME]


def _run_to_b4(rule_name="Nẹp theo độ dày kính"):
    """Dựng orchestrator với snapshot riêng, chạy B0→B4.

    `rule_name` cho phép dựng ca rule CHƯA đặt tên (xem
    `test_rule_trace_empty_rule_name_no_rule_code`).
    """
    base._prepare_orchestrator()
    st = base._STUB

    st.set_doc("AL BOM Version", "ALBOMV-1", {
        "bom": "BOM-1",
        "bom_set_snapshot": json.dumps({"items": BOM_ITEMS}),
        "cost_template_snapshot": json.dumps({"items": []}),
    })
    # Kính chọn theo vị trí: giá tra theo mã GM-01 (được gom vào lô query giá
    # qua glass_master_map — đúng đường dialog "Kính theo vị trí").
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom": "BOM-1", "al_bom_version": "ALBOMV-1", "parent": "QTN-1",
        "al_bom_vars": json.dumps({
            "extra_vars": {},
            "glass_master_map": {"__slug__kinh_tren": "GM-01"},
        }),
    })
    st.set_get_all("Item", [
        {"name": "KINH-01", "weight_per_unit": 15.0,
         "item_name": "Kính cường lực"},
        {"name": "NEP-8", "weight_per_unit": 0.5, "item_name": "Nẹp 8"},
    ])
    st.set_get_all("Item Price", [
        # Dòng kính tra giá theo MÃ KÍNH ĐÃ RESOLVE (GM-01) — đúng đường
        # engine: `lit.item_code` của dòng kính = glass master.
        {"name": "IP-0", "item_code": "GM-01",
         "price_list_rate": 300000, "price_list": "Standard Selling"},
        # Item code gốc vẫn phải có giá: nhánh fallback chạy allow_missing=False
        # nên mã không có dòng Item Price sẽ THROW (đúng hành vi engine).
        {"name": "IP-1", "item_code": "KINH-01",
         "price_list_rate": 300000, "price_list": "Standard Selling"},
        {"name": "IP-3", "item_code": "NEP-8",
         "price_list_rate": 50000, "price_list": "Standard Selling"},
    ])
    st.set_get_all("AL Glass Master", [
        {"name": "GM-01", "glass_name": "Kính trắng 8 mm",
         "total_thick_mm": 8, "glass_type": "Clear", "max_area_m2": 6.6},
    ])
    st.set_get_all("AL Glass Type", [
        {"name": "Clear", "type_name": "Kính trong"},
    ])
    st.set_get_all("AL Quantity Calc Method", [
        {"name": "AREA", "output_unit": "m²",
         "calc_pattern_name": "Tính theo diện tích"},
        {"name": "LENGTH_ONLY", "output_unit": "m",
         "calc_pattern_name": "Tính theo chiều dài"},
    ])
    # VL_KINH PHẢI là category kính → glass_data mới nạp từ GM-01.
    st.set_get_all("AL Material Category", [
        {"name": "VL_KINH", "default_scrap_pct": 0.03,
         "requires_glass_master": 1},
        {"name": "VL_NHOM", "default_scrap_pct": 0.02},
    ])
    # Rule THRESHOLD giả lập: input 8 → NEP-8 (cùng mã cho cả 2 tên biến).
    st.set_doc("AL Dynamic Item Rule", "RULE-NEP", {
        "rule_name": rule_name,
        "rule_type": "THRESHOLD",
        "threshold_rows": [
            {"from_value": 0, "to_value": 10, "result_item": "NEP-8"}],
        "resolve": lambda value: "NEP-%d" % int(value),
    })

    orch = BomOrchestrator("QI-0001")
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    return orch


def _line(orch, slug):
    for row in orch.bom_result:
        if row.get("slug") == slug:
            return row
    raise AssertionError("không có dòng %s trong %s" % (
        slug, [r.get("slug") for r in orch.bom_result]))


class _FakeMeta(object):
    """Meta tối thiểu cho `_recalculate_quotation_totals` (không field tổng)."""

    def has_field(self, fieldname):
        return False


def _enable_b7_stub():
    """Bù 2 chỗ stub còn thiếu để chạy được b7 (KHÔNG đụng logic engine).

    - `FakeDB.set_value` chưa nhận `update_modified=` (Frappe thật có).
    - `frappe.has_permission` chưa có (API explain dùng để kiểm quyền).
    """
    st = base._STUB

    def set_value(doctype, name, field_or_dict, value=None, **kwargs):
        st.set_value_calls.append((doctype, name, field_or_dict, value))

    st.db.set_value = set_value
    st.has_permission = lambda *a, **k: True

    row = base.FakeDoc({"name": "QI-0001", "item_name": "Kính",
                        "item_code": "KINH-01"})
    row.precision = lambda field: 2
    row.price_list_rate = 0
    row.discount_percentage = 0
    row.discount_amount = 0
    row.margin_type = None
    row.margin_rate_or_amount = 0
    st.set_doc("Quotation", "QTN-1", {
        "docstatus": 0,
        "items": [row],
        "calculate_taxes_and_totals": lambda: None,
        "set_total_in_words": lambda: None,
        "meta": _FakeMeta(),
    })


def _run_to_b7():
    orch = _run_to_b4()
    orch.b5_aggregate_cost_buckets()
    orch.b6_calculate_cost_template()
    _enable_b7_stub()
    orch.b7_save_results()
    return orch


def _saved_al_bom_result():
    for call in base._STUB.set_value_calls:
        doctype, _name, fields, _value = call
        if doctype == "Quotation Item" and isinstance(fields, dict) \
                and "al_bom_result" in fields:
            return fields["al_bom_result"]
    raise AssertionError(base._STUB.set_value_calls)


# ═══════════════════════════════════════════════════════════════════
# B3 — alias đi vào namespace công thức
# ═══════════════════════════════════════════════════════════════════
def test_b3_alias_literals_in_context():
    orch = _run_to_b4()
    assert orch.inputs["kinh_tren__total_thick_mm"] == 8, \
        orch.inputs.get("kinh_tren__total_thick_mm")
    assert orch.inputs["kinh_tren__glass_thick"] == 8, \
        orch.inputs.get("kinh_tren__glass_thick")
    assert orch.inputs["kinh_tren__max_area_m2"] == 6.6, \
        orch.inputs.get("kinh_tren__max_area_m2")
    # Nested items (backward compat) cũng có cả 2 tên.
    items = orch.inputs["items"]["kinh_tren"]
    assert items["total_thick_mm"] == 8, items
    assert items["glass_thick"] == 8, items


def test_b3_formula_uses_new_names():
    orch = _run_to_b4()
    glass = _line(orch, "kinh_tren")
    # Công thức đọc ĐÚNG biến mới (không ra 0).
    assert glass["width"] == 800, glass
    assert glass["qty"] == 6.6, glass


def test_b2_rule_alias_resolves_same_item():
    orch = _run_to_b4()
    assert _line(orch, "nep_moi")["item_code"] == "NEP-8", \
        _line(orch, "nep_moi")
    assert _line(orch, "nep_cu")["item_code"] == "NEP-8", \
        _line(orch, "nep_cu")


# ═══════════════════════════════════════════════════════════════════
# Phase 2 — rule_trace / price_trace
# ═══════════════════════════════════════════════════════════════════
def test_rule_trace_rule_lines():
    """Câu HIỂN THỊ: nhãn quy tắc/dòng/vật tư, ⛔ không mã rule/biểu thức."""
    orch = _run_to_b4()
    expected = ('Quy tắc "Nẹp theo độ dày kính": độ dày kính của dòng '
                '"Kính trên" = 8 mm → chọn mã "Nẹp 8" (NEP-8).')
    assert _line(orch, "nep_moi")["rule_trace"] == expected, \
        _line(orch, "nep_moi")["rule_trace"]
    # Alias `glass_thick` ra CÙNG câu người đọc (nhãn "Độ dày kính").
    assert _line(orch, "nep_cu")["rule_trace"] == expected, \
        _line(orch, "nep_cu")["rule_trace"]
    # Dữ liệu kỹ thuật vẫn được giữ cho support.
    assert "RULE-NEP" in _line(orch, "nep_moi")["rule_trace_raw"], \
        _line(orch, "nep_moi")["rule_trace_raw"]


def test_rule_trace_empty_rule_name_no_rule_code():
    """Rule CHƯA đặt tên ⇒ câu hiển thị dùng fallback "Quy tắc chọn mã",
    ⛔ không rơi về mã rule (`RULE-NEP`) — mã rule chỉ sống trong `*_raw`."""
    orch = _run_to_b4(rule_name="")
    trace = _line(orch, "nep_moi")["rule_trace"]
    assert trace.startswith("Quy tắc chọn mã:"), trace
    assert "RULE-NEP" not in trace, trace
    assert "RULE-NEP" in _line(orch, "nep_moi")["rule_trace_raw"], \
        _line(orch, "nep_moi")["rule_trace_raw"]


def test_rule_trace_fixed_line_empty():
    orch = _run_to_b4()
    assert _line(orch, "kinh_tren")["rule_trace"] == "", \
        _line(orch, "kinh_tren")["rule_trace"]


def test_price_trace_fixed_line():
    orch = _run_to_b4()
    trace = _line(orch, "kinh_tren")["price_trace"]
    assert 'Bảng giá "Standard Selling"' in trace, trace
    assert "300.000 đ" in trace, trace
    # ⛔ Không docname Item Price trong chuỗi hiển thị.
    assert "IP-0" not in trace, trace
    assert "IP-0" in _line(orch, "kinh_tren")["price_trace_raw"], \
        _line(orch, "kinh_tren")["price_trace_raw"]


def test_price_trace_rule_line():
    orch = _run_to_b4()
    trace = _line(orch, "nep_moi")["price_trace"]
    assert 'Bảng giá "Standard Selling"' in trace, trace
    assert "50.000 đ" in trace, trace
    assert "IP-3" not in trace, trace


def test_price_trace_multiplier_chain():
    """multiplier_chain: ghi rõ giá gốc × hệ số = giá (định dạng người đọc)."""
    orch = BomOrchestrator("QI-TEST")
    orch._price_info = {"NHOM-01": {
        "price_list": "Standard Selling",
        "row": {"name": "IP-9"},
        "row_name": "IP-9",
        "dim_fieldnames": {},
        "price": 130000,
        "base_price": 100000,
        "multiplier": 1.3,
    }}
    trace = orch._build_price_trace(
        {"slug": "vien_nhom", "item_code": "NHOM-01", "unit_price": 0},
        {"item_code": "NHOM-01", "unit_price": 130000})
    assert "giá gốc 100.000 đ × hệ số 1,3 = 130.000 đ" in trace, trace
    assert "IP-9" not in trace, trace


def test_price_trace_uses_price_base_item():
    """Dòng khai mã đại diện: trace phải kể dòng giá của `price_base_item`,
    KHÔNG phải dòng giá của `item_code` (tiền thật lấy theo pbi)."""
    orch = BomOrchestrator("QI-TEST")
    orch._price_info = {
        "NHOM-XINGFA": {
            "price_list": "Standard Selling", "row": {"name": "IP-PBI"},
            "row_name": "IP-PBI", "dim_fieldnames": {}, "price": 120000},
        # Dòng giá của mã HIỂN THỊ — nếu trace đọc nhầm mã này là SAI.
        "XF55-KB-20": {
            "price_list": "Standard Selling", "row": {"name": "IP-ITEM"},
            "row_name": "IP-ITEM", "dim_fieldnames": {}, "price": 999000},
    }
    trace = orch._build_price_trace(
        {"slug": "khung_duoi", "item_code": "XF55-KB-20",
         "price_base_item": "NHOM-XINGFA", "item_selection_mode": "Manual"},
        {"item_code": "XF55-KB-20", "unit_price": 120000})
    assert "NHOM-XINGFA" in trace, trace
    assert "mã đại diện" in trace, trace
    assert "120.000 đ" in trace, trace
    assert "IP-PBI" not in trace, trace
    assert "IP-ITEM" not in trace, trace


def _set_saved_lines(lines):
    """Gắn `al_bom_result` giả + quyền đọc để test `explain_bom_line`."""
    base._reset_stub()
    st = base._STUB
    st.has_permission = lambda *a, **k: True
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom_result": json.dumps({"lines": lines}),
        "parent": "QTN-1",
        "al_bom_vars": "{}",
    })
    st.set_doc("Quotation", "QTN-1", {"docstatus": 0})


def test_explain_keys_match_missing():
    """Mỗi step có `key` ổn định; `missing` chứa ĐÚNG các key đó."""
    import alumglass.api as api

    _set_saved_lines([{
        "slug": "nep", "item_code": "NEP-8",
        "rule_trace": ('Quy tắc "Nẹp theo độ dày kính": độ dày kính = '
                       '8 mm → chọn mã "Nẹp 8" (NEP-8).'),
        "price_trace": 'Bảng giá "Standard Selling" · giá 50.000 đ',
        "rule_trace_raw": "items.kinh_tren.total_thick_mm = 8 → RULE-NEP → NEP-8",
        "price_trace_raw": "IP-3 / NEP-8 / 50000",
        "rule_name": "Nẹp theo độ dày kính", "rule_match": "dải 6 – 10",
        "item_selection_mode": "Rule",
        "width": 1000, "height": 0, "qty": 1, "unit_qty": 1, "total_qty": 1,
        "unit_price": 50000, "line_total": 50000, "cost_bucket": "VL_NHOM",
        "calc_pattern": "LENGTH_ONLY", "calc_pattern_name": "Tính theo chiều dài",
        "is_glass_row": 0,
    }])
    result = api.explain_bom_line("QI-0001", "nep")
    keys = [s["key"] for s in result["steps"]]
    assert keys == ["item_code", "glass_source", "rule", "price",
                    "quantity", "line_total"], keys
    assert result["missing"] == [], result["missing"]
    for key in result["missing"]:
        assert key in keys, (key, keys)


def test_explain_glass_row_without_glass_info():
    """Dòng KÍNH thiếu thông số ⇒ câu ĐÚNG chỗ sửa (không ngõ cụt) +
    missing `glass_source`."""
    import alumglass.api as api

    _set_saved_lines([{
        "slug": "kinh_tren", "item_code": "GM-01", "is_glass_row": 1,
        "rule_trace": "", "price_trace": "Mã 'GM-01' · giá 300000",
        "width": 0, "height": 0, "qty": 0, "unit_qty": 0, "total_qty": 0,
        "unit_price": 300000, "line_total": 0, "cost_bucket": "VL_KINH",
    }])
    result = api.explain_bom_line("QI-0001", "kinh_tren")
    glass_step = result["steps"][1]
    assert glass_step["key"] == "glass_source", glass_step
    # Câu chỉ ĐÚNG chỗ sửa, không chỉ nói điều kiện.
    assert "Dòng kính chưa chọn kính nên chưa tính được khối lượng" \
        in glass_step["detail"], glass_step
    assert '"Tham số BOM"' in glass_step["detail"], glass_step
    assert '"Kính theo vị trí"' in glass_step["detail"], glass_step
    assert '"Tính giá"' in glass_step["detail"], glass_step
    assert "không dùng dữ liệu kính" not in glass_step["detail"], glass_step
    assert "glass_source" in result["missing"], result["missing"]
    # Số 0 ở đây do SỐ LƯỢNG = 0 (thiếu thông số kính), KHÔNG phải thiếu giá
    # ⇒ ⛔ không bật cờ "thiếu giá"; việc cần làm đã nêu ở bước 2.
    assert not result.get("warn_zero_price"), result
    # Báo giá MỚI (có `price_trace`) thiếu dữ liệu kính KHÔNG phải dữ liệu cũ
    # ⇒ ⛔ không được báo "tính trước khi có phần giải thích" (bấm Tính giá
    # cũng không đổi gì — nguyên nhân thật là chưa chọn kính).
    assert "hint" not in result, result
    for key in result["missing"]:
        assert key in [s["key"] for s in result["steps"]], result["missing"]


def test_price_trace_zero_price_sentence():
    """Engine KHÔNG tra được dòng giá ⇒ câu CẢNH BÁO (nêu tên bảng giá để
    kiểm) — ⛔ không phải "giá 0 đ" trần trông y số thật."""
    orch = BomOrchestrator("QI-TEST")
    orch._price_info = {"NEP-9": {
        "price_list": "Standard Selling", "row": None, "row_name": "",
        "dim_fieldnames": {}, "price": 0}}
    trace = orch._build_price_trace(
        {"slug": "nep", "item_code": "NEP-9", "unit_price": 0},
        {"item_code": "NEP-9", "unit_price": 0})
    assert "Chưa tìm được dòng giá cho mã này" in trace, trace
    assert "đang tạm tính 0 đ, thành tiền chưa đúng" in trace, trace
    assert 'Kiểm tra bảng giá "Standard Selling" hoặc báo quản trị.' \
        in trace, trace


def test_price_trace_base_item_uses_item_name():
    """Câu "giá tra theo mã đại diện" dùng TÊN vật tư (đã nạp ở batch query),
    ⛔ không phơi mã trần."""
    orch = BomOrchestrator("QI-TEST")
    orch._item_names = {"NHOM-XINGFA": "Nhôm Xingfa 55"}
    orch._price_info = {"NHOM-XINGFA": {
        "price_list": "Standard Selling", "row": {"name": "IP-PBI"},
        "row_name": "IP-PBI", "dim_fieldnames": {}, "price": 120000}}
    trace = orch._build_price_trace(
        {"slug": "khung_duoi", "item_code": "XF55-KB-20",
         "price_base_item": "NHOM-XINGFA", "item_selection_mode": "Manual"},
        {"item_code": "XF55-KB-20", "unit_price": 120000})
    assert 'Giá tra theo mã đại diện "Nhôm Xingfa 55"' in trace, trace
    assert "NHOM-XINGFA" not in trace, trace


def test_explain_zero_price_line_warns():
    """Dòng tạm tính 0 đ: bước 4 mang `severity: "warning"` + cờ tổng
    `warn_zero_price`; ⛔ KHÔNG vào `missing` (dữ liệu CÓ, chỉ là số chưa
    đúng)."""
    import alumglass.api as api

    _set_saved_lines([{
        "slug": "nep", "item_code": "NEP-9", "is_glass_row": 0,
        "rule_trace": "", "price_trace": (
            'Bảng giá "Standard Selling" · Chưa tìm được dòng giá cho mã '
            'này — đang tạm tính 0 đ, thành tiền chưa đúng. Kiểm tra bảng '
            'giá "Standard Selling" hoặc báo quản trị.'),
        "width": 1000, "height": 0, "qty": 1, "unit_qty": 1, "total_qty": 1,
        "unit_price": 0, "line_total": 0, "cost_bucket": "VL_NHOM",
    }])
    result = api.explain_bom_line("QI-0001", "nep")
    price_step = result["steps"][3]
    assert price_step["key"] == "price", price_step
    assert price_step.get("severity") == "warning", price_step
    # ⛔ KHÔNG vào missing — missing nghĩa là "chưa lưu dữ liệu".
    assert "price" not in result["missing"], result["missing"]
    # Các bước khác KHÔNG bị gắn warning.
    assert [s.get("severity") for s in result["steps"]].count("warning") == 1, \
        result["steps"]
    assert result.get("warn_zero_price") is True, result


def test_explain_fixed_line_step1_name_step3_not_repeated():
    """Dòng Fixed: bước 1 ra TÊN vật tư (engine nạp từ batch query sẵn có —
    mã kính lấy `glass_name` của AL Glass Master), bước 3 nói việc KHÁC,
    ⛔ không lặp lại y hệt câu của bước 1."""
    import alumglass.api as api

    orch = _run_to_b7()
    # Engine nạp tên cho mã đã resolve từ batch ĐÃ CÓ (không N+1).
    assert orch._item_names.get("GM-01") == "Kính trắng 8 mm", orch._item_names

    saved = _saved_al_bom_result()
    base._STUB.set_doc("Quotation Item", "QI-0001", {
        "al_bom_result": saved, "parent": "QTN-1"})
    base._STUB.set_doc("Quotation", "QTN-1", {"docstatus": 0})

    result = api.explain_bom_line("QI-0001", "kinh_tren")
    step1 = result["steps"][0]
    step3 = result["steps"][2]
    assert step1["detail"] == 'Dùng mã cố định "Kính trắng 8 mm" (GM-01).', \
        step1
    assert "Dùng mã cố định" not in step3["detail"], step3
    assert step3["detail"] != step1["detail"], (step1, step3)
    assert "không dùng quy tắc chọn mã" in step3["detail"], step3


def test_explain_legacy_line_has_hint():
    """Dòng KHÔNG có bất kỳ căn cứ nào (`rule_trace`/`price_trace` và cả bản
    `*_raw`) ⇒ là báo giá cũ thật ⇒ CÓ `hint` hướng dẫn bấm "Tính giá"."""
    import alumglass.api as api

    _set_saved_lines([{
        "slug": "kinh_tren", "item_code": "GM-01",
        "width": 0, "height": 0, "qty": 0, "unit_qty": 0, "total_qty": 0,
        "unit_price": 300000, "line_total": 0, "cost_bucket": "VL_KINH",
    }])
    result = api.explain_bom_line("QI-0001", "kinh_tren")
    assert result["success"] is True, result
    assert result["missing"], result
    hint = result.get("hint") or ""
    assert hint, result
    assert "Tính giá" in hint, hint
    # `hint` cũng không phơi mã kỹ thuật.
    for bad in ("RULE-", "items.", "kinh_tren"):
        assert bad not in hint, (bad, hint)


def test_explain_rule_alias_reads_total_thick_fallback():
    """Dữ liệu CŨ: dòng kính chỉ có `total_thick_mm`; rule dùng alias
    `glass_thick` ⇒ bước 2 vẫn nêu được giá trị qua fallback."""
    import alumglass.api as api

    _set_saved_lines([
        {
            "slug": "kinh_tren", "item_code": "GM-01", "is_glass_row": 1,
            "line_label": "Kính trên",
            "glass_master": "GM-01", "total_thick_mm": 8,
            "glass_type_name": "Kính trong", "max_area_m2": 6.6,
        },
        {
            "slug": "nep", "item_code": "NEP-8", "is_glass_row": 0,
            "rule_trace": "items.kinh_tren.glass_thick = 8 → RULE-NEP → NEP-8",
            "price_trace": "Mã 'NEP-8' · giá 50000",
            "width": 1000, "height": 0, "qty": 1, "unit_qty": 1,
            "total_qty": 1, "unit_price": 50000, "line_total": 50000,
            "cost_bucket": "VL_NHOM", "calc_pattern": "LENGTH_ONLY",
        },
    ])
    result = api.explain_bom_line("QI-0001", "nep")
    glass_step = result["steps"][1]
    assert glass_step["key"] == "glass_source", glass_step
    assert "Kính trên" in glass_step["detail"], glass_step
    assert "kinh_tren" not in glass_step["detail"], glass_step
    assert "Độ dày kính = 8 mm" in glass_step["detail"], glass_step
    assert "glass_source" not in result["missing"], result["missing"]


def test_traces_saved_in_result_json():
    """b7 lưu nguyên `lines` vào al_bom_result — trace phải có trong JSON."""
    _run_to_b7()
    saved = json.loads(_saved_al_bom_result())
    by_slug = {row.get("slug"): row for row in saved["lines"]}
    # Hiển thị: nhãn nghiệp vụ. Kỹ thuật: `*_raw` giữ cho support.
    assert by_slug["nep_moi"]["rule_trace"].endswith(
        'chọn mã "Nẹp 8" (NEP-8).'), by_slug["nep_moi"]
    assert "RULE-NEP" in by_slug["nep_moi"]["rule_trace_raw"], by_slug
    assert "50.000 đ" in by_slug["nep_moi"]["price_trace"], by_slug["nep_moi"]
    assert "IP-3" not in by_slug["nep_moi"]["price_trace"], by_slug["nep_moi"]
    assert "IP-3" in by_slug["nep_moi"]["price_trace_raw"], by_slug["nep_moi"]
    # Alias + cờ nhận biết dòng kính đi vào JSON lưu.
    assert by_slug["kinh_tren"]["is_glass_row"] == 1, by_slug["kinh_tren"]
    assert by_slug["kinh_tren"]["glass_thick"] == 8, by_slug["kinh_tren"]
    assert by_slug["kinh_tren"]["total_thick_mm"] == 8, by_slug["kinh_tren"]
    assert by_slug["nep_moi"]["is_glass_row"] == 0, by_slug["nep_moi"]


def test_explain_bom_line_6_steps():
    import alumglass.api as api

    _run_to_b7()
    saved = _saved_al_bom_result()
    base._STUB.set_doc("Quotation Item", "QI-0001", {
        "al_bom_result": saved, "parent": "QTN-1"})
    base._STUB.set_doc("Quotation", "QTN-1", {"docstatus": 0})

    result = api.explain_bom_line("QI-0001", "nep_moi")
    assert result["success"] is True, result
    assert len(result["steps"]) == 6, result["steps"]
    titles = [s["title"] for s in result["steps"]]
    assert titles == [
        "Chọn mã vật tư",
        "Nguồn giá trị kính",
        "Quy tắc khớp → mã vật tư",
        "Tra giá",
        "Tính số lượng",
        "Thành tiền và rổ chi phí",
    ], titles
    assert [s["key"] for s in result["steps"]] == [
        "item_code", "glass_source", "rule", "price", "quantity",
        "line_total"], result["steps"]
    # Bước 2 đọc dòng kính từ CÙNG JSON (không tính lại engine).
    glass_step = result["steps"][1]["detail"]
    assert "Kính trên" in glass_step, glass_step
    assert "kinh_tren" not in glass_step, glass_step
    assert "8 mm" in glass_step, glass_step
    # Bước 5/6 số liệu đúng + nhãn cách tính (⛔ không mã LENGTH_ONLY).
    assert "Tính theo chiều dài" in result["steps"][4]["detail"], \
        result["steps"][4]
    assert "LENGTH_ONLY" not in result["steps"][4]["detail"], result["steps"][4]
    assert "50.000 đ" in result["steps"][5]["detail"], result["steps"][5]
    assert result["missing"] == [], result["missing"]
    assert "hint" not in result, result


def test_explain_bom_line_unknown_slug():
    import alumglass.api as api

    base._STUB.has_permission = lambda *a, **k: True
    base._STUB.set_doc("Quotation Item", "QI-0001", {
        "al_bom_result": json.dumps({"lines": []}), "parent": "QTN-1"})
    base._STUB.set_doc("Quotation", "QTN-1", {"docstatus": 0})
    result = api.explain_bom_line("QI-0001", "khong_ton_tai")
    assert result["success"] is False, result
    # Message người đọc; slug chỉ vào log, ⛔ không trả ra.
    assert "Không tìm thấy dòng vật tư" in result["message"], result
    assert "khong_ton_tai" not in result["message"], result


def test_explain_bom_line_checks_permission():
    """Phải đi qua ĐÚNG hàm kiểm quyền dùng chung với get_result_display."""
    import alumglass.api as api

    calls = []

    def _deny(name, ptype="read"):
        calls.append((name, ptype))
        raise RuntimeError("không có quyền")

    original = api._require_quotation_item_permission
    api._require_quotation_item_permission = _deny
    try:
        try:
            api.explain_bom_line("QI-0001", "bat_ky")
            raise AssertionError("phải bị chặn bởi cổng quyền")
        except RuntimeError:
            pass
    finally:
        api._require_quotation_item_permission = original
    assert calls == [("QI-0001", "read")], calls


def test_price_trace_dimension_business_labels():
    """Dimension trong trace phải là NHÃN + giá trị người đọc:
    `Màu sắc: Trắng`, `Độ dày kính: 8 mm` — ⛔ không enum `WHITE`, ⛔ docname."""
    base._STUB.set_get_all("AL Variable Dimension Mapping", [
        {"variable_name": "mau_sac", "pricing_dimension": "PD-COLOR",
         "is_active": 1},
        {"variable_name": "total_thick_mm", "pricing_dimension": "PD-THICK",
         "is_active": 1},
    ])
    base._STUB.set_get_all("AL Pricing Dimension", [
        {"name": "PD-COLOR", "dimension_name": "Màu sắc",
         "custom_fieldname": "custom_color",
         "link_doctype": "AL Color Standard"},
        {"name": "PD-THICK", "dimension_name": "Độ dày kính",
         "custom_fieldname": "custom_thick",
         "link_doctype": ""},
    ])
    base._STUB.set_doc("AL Color Standard", "WHITE", {"color_name": "Trắng"})

    orch = BomOrchestrator("QI-TEST")
    orch._price_info = {"NEP-8": {
        "price_list": "Standard Selling", "row_name": "IP-3",
        "row": {"name": "IP-3", "custom_color": "WHITE", "custom_thick": 8},
        "dim_fieldnames": {"mau_sac": "custom_color",
                           "total_thick_mm": "custom_thick"},
        "price": 50000,
    }}
    trace = orch._build_price_trace(
        {"slug": "nep_moi", "item_code": "NEP-8", "unit_price": 0},
        {"item_code": "NEP-8", "unit_price": 50000})
    assert "Màu sắc: Trắng" in trace, trace
    assert "Độ dày kính: 8 mm" in trace, trace
    assert "50.000 đ" in trace, trace
    # ⛔ Mã kỹ thuật: enum màu, docname Item Price, mã dimension.
    for bad in ("WHITE", "IP-3", "PD-COLOR", "PD-THICK"):
        assert bad not in trace, (bad, trace)


def test_display_strings_have_no_technical_codes():
    """CHỐNG TÁI PHÁT: mọi chuỗi NGƯỜI ĐỌC không chứa mã kỹ thuật."""
    forbidden = ("RULE-", "IP-0", "IP-3", "items.", "kinh_", "LENGTH_ONLY")

    orch = _run_to_b7()
    displayed = []
    for line in orch.bom_result:
        displayed.append(line.get("rule_trace") or "")
        displayed.append(line.get("price_trace") or "")

    saved = _saved_al_bom_result()
    base._STUB.set_doc("Quotation Item", "QI-0001", {
        "al_bom_result": saved, "parent": "QTN-1"})
    base._STUB.set_doc("Quotation", "QTN-1", {"docstatus": 0})
    import alumglass.api as api
    result = api.explain_bom_line("QI-0001", "nep_moi")
    displayed.append(result.get("hint") or "")
    for step in result["steps"]:
        displayed.append(step.get("title") or "")
        displayed.append(step.get("detail") or "")

    for text in displayed:
        for bad in forbidden:
            assert bad not in text, (bad, text)


# ═══════════════════════════════════════════════════════════════════
# Pha 3 — dòng kính lấy mã theo ĐƯỜNG MẶC ĐỊNH (`default_glass_master`)
# ═══════════════════════════════════════════════════════════════════
# Bug đo được trước Pha 3: dòng kính KHÔNG có `item_code`, chỉ khai
# `default_glass_master="GM-01"` + `glass_master_map` rỗng → engine resolve
# đúng mã GM-01 nhưng KHÔNG tra giá/trọng lượng cho mã đó ⇒ unit_price = 0,
# weight = 0, line_total = 0 (đường `glass_master_map` thì ra 300 000 đ).
# Owner chốt "cách B": bổ sung mã mặc định vào đường tra giá NHƯNG đi đường
# cho phép thiếu (`allow_missing=True`) — thiếu giá chỉ cảnh báo, ⛔ không throw.
def _default_glass_case_items():
    """Bộ dòng BOM của ca mặc định: dòng kính KHÔNG có item_code."""
    glass = dict(GLASS_ITEM)
    glass["item_code"] = ""
    glass["default_glass_master"] = "GM-01"
    return [glass, RULE_ITEM_NEW_NAME, RULE_ITEM_OLD_NAME]


def _run_default_glass_case(with_price=True, with_dimensions=False,
                            with_dim_value=True):
    """Chạy B0→B4 cho dòng kính lấy mã kính theo ĐƯỜNG MẶC ĐỊNH.

    `with_price=False` = KHÔNG có dòng Item Price cho GM-01 (ca "mã kính
    chưa có giá") — engine phải chạy tiếp với giá 0 + cảnh báo.
    `with_dimensions=True` = bật 1 pricing dimension (màu sắc) + 2 dòng giá
    cho GM-01 (một dòng gắn màu, một dòng "trần") để kiểm GIÁ COMPOSITE —
    đường có nhiều khả năng lệch nhất giữa dialog và engine.
    """
    base._prepare_orchestrator()
    st = base._STUB
    items = _default_glass_case_items()

    st.set_doc("AL BOM Version", "ALBOMV-1", {
        "bom": "BOM-1",
        "bom_set_snapshot": json.dumps({"items": items}),
        "cost_template_snapshot": json.dumps({"items": []}),
    })
    extra_vars = {"mau_sac": "WHITE"} if (with_dimensions and with_dim_value) else {}
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom": "BOM-1", "al_bom_version": "ALBOMV-1", "parent": "QTN-1",
        "al_bom_vars": json.dumps({
            "extra_vars": extra_vars,
            # Map RỖNG — đúng ca Owner đo: kính lấy theo mã mặc định của dòng.
            "glass_master_map": {},
        }),
    })
    st.set_get_all("Item", [
        # Trọng lượng của dòng kính phải lấy theo MÃ KÍNH (GM-01), không phải
        # mã giữ chỗ (dòng không có item_code).
        {"name": "GM-01", "weight_per_unit": 20.0,
         "item_name": "Kính trắng 8 mm"},
        {"name": "NEP-8", "weight_per_unit": 0.5, "item_name": "Nẹp 8"},
    ])
    price_rows = [
        {"name": "IP-3", "item_code": "NEP-8",
         "price_list_rate": 50000, "price_list": "Standard Selling"},
        {"name": "IP-1", "item_code": "KINH-01",
         "price_list_rate": 300000, "price_list": "Standard Selling"},
    ]
    if with_price:
        price_rows.insert(0, {
            "name": "IP-0", "item_code": "GM-01",
            "price_list_rate": 300000, "price_list": "Standard Selling"})
    if with_dimensions:
        # Dòng giá GẮN MÀU (WHITE) giá cao hơn dòng "trần" — engine phải chọn
        # dòng gắn màu khi inputs.mau_sac = WHITE.
        price_rows.append({
            "name": "IP-0W", "item_code": "GM-01",
            "price_list_rate": 320000, "price_list": "Standard Selling",
            "custom_color": "WHITE"})
    st.set_get_all("Item Price", price_rows)
    st.set_get_all("AL Glass Master", [
        {"name": "GM-01", "glass_name": "Kính trắng 8 mm",
         "total_thick_mm": 8, "glass_type": "Clear", "max_area_m2": 6.6},
    ])
    st.set_get_all("AL Glass Type", [
        {"name": "Clear", "type_name": "Kính trong"},
    ])
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
    if with_dimensions:
        # 1 pricing dimension "màu sắc" → Item Price có `custom_color`.
        st.set_get_all("AL Variable Dimension Mapping", [
            {"variable_name": "mau_sac", "pricing_dimension": "PD-COLOR",
             "is_active": 1},
        ])
        st.set_get_all("AL Pricing Dimension", [
            {"name": "PD-COLOR", "dimension_name": "Màu sắc",
             "custom_fieldname": "custom_color", "link_doctype": ""},
        ])
    st.set_doc("AL Dynamic Item Rule", "RULE-NEP", {
        "rule_name": "Nẹp theo độ dày kính",
        "rule_type": "THRESHOLD",
        "threshold_rows": [
            {"from_value": 0, "to_value": 10, "result_item": "NEP-8"}],
        "resolve": lambda value: "NEP-%d" % int(value),
    })

    orch = BomOrchestrator("QI-0001")
    orch.b0_version_pinning()
    orch.b1_gather_inputs()
    orch.b2_prefetch_master_data()
    orch.b3_build_formulas()
    orch.b4_calculate_bom_items()
    return orch


def test_default_glass_master_gets_price_and_weight():
    """Đường MẶC ĐỊNH phải ra ĐÚNG số như đường `glass_master_map`.

    Đo trước Pha 3: unit_price=0 · weight=0 · line_total=0 (map: 300 000 /
    1 584 000). Sau khi vá: 300 000 · 20 · 1 584 000, ⛔ không throw.
    """
    orch = _run_default_glass_case(with_price=True)
    glass = _line(orch, "kinh_tren")
    assert glass["item_code"] == "GM-01", glass
    assert glass["unit_price"] == 300000, glass
    assert glass["weight_per_unit"] == 20.0, glass
    assert glass["line_total"] == 1584000, glass
    # Mã kính CÓ giá ⇒ ⛔ không sinh cảnh báo thiếu giá.
    assert not [k for k in orch.bom_engine_errors
                if k == "thieu_gia_item:GM-01"], orch.bom_engine_errors


def test_default_glass_master_missing_price_warns_without_throw():
    """Mã kính mặc định CHƯA có dòng Item Price: chạy tiếp với giá 0 và
    cảnh báo `thieu_gia_item:GM-01` NỔI LÊN (mã này CÓ được đọc giá —
    ⛔ không được nuốt như mã kính giữ chỗ)."""
    orch = _run_default_glass_case(with_price=False)
    glass = _line(orch, "kinh_tren")
    assert glass["item_code"] == "GM-01", glass
    assert glass["unit_price"] == 0, glass
    assert "thieu_gia_item:GM-01" in orch.bom_engine_errors, \
        orch.bom_engine_errors
    # Dòng Rule vẫn tính được (cả lần tính KHÔNG bị dừng vì mã kính thiếu giá).
    assert _line(orch, "nep_moi")["item_code"] == "NEP-8", _line(orch, "nep_moi")


# ═══════════════════════════════════════════════════════════════════
# Pha 3 — hợp đồng dialog: glass_groups + get_glass_master_price
# ═══════════════════════════════════════════════════════════════════
_GLASS_LINE_NO_DEFAULT = {
    "slug": "kinh_tren", "line_name": "Kính trên",
    "item_code": "KINH-01", "price_base_item": "",
    "default_glass_master": "", "item_selection_mode": "Manual",
    "category": "VL_KINH", "cost_bucket": "VL_KINH", "calc_pattern": "AREA",
    "width": "1000", "height": "1000", "qty": "1",
    "show_condition": "", "item_condition_formula": "", "rule_input_expr": "",
}


def _setup_glass_group_case(line, saved_map=None, override=""):
    """Dựng stub đủ cho `get_variable_set_for_bom` + tra giá kính."""
    base._prepare_orchestrator()
    st = base._STUB
    st.set_doc("AL BOM Version", "ALBOMV-1", {
        "bom": "BOM-1",
        "bom_set_snapshot": json.dumps({"items": [line]}),
        "cost_template_snapshot": json.dumps({"items": []}),
    })
    vars_ = {"extra_vars": {}}
    if saved_map is not None:
        vars_["glass_master_map"] = saved_map
    if override:
        vars_["glass_master"] = override
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom": "BOM-1", "al_bom_version": "ALBOMV-1", "parent": "QTN-1",
        "al_bom_vars": json.dumps(vars_),
    })
    st.set_doc("AL BOM", "BOM-1", {
        "current_version": "ALBOMV-1", "bom_set": "ALBS-1",
        "bom_code": "BOM-1", "bom_name": "BOM kính",
    })
    st.set_doc("AL Bom Set", "ALBS-1", {
        "set_code": "ALBS-1", "set_name": "Bộ BOM kính", "items": [line],
    })
    st.has_permission = lambda *a, **k: True
    st.set_get_all("AL Glass Master", [
        {"name": "GM-01", "glass_name": "Kính trắng 8 mm",
         "total_thick_mm": 8, "glass_type": "Clear", "max_area_m2": 6.6},
        {"name": "GM-02", "glass_name": "Kính xanh 8 mm",
         "total_thick_mm": 8, "glass_type": "Clear", "max_area_m2": 6.6},
        {"name": "GM-03", "glass_name": "Kính dán 10 mm",
         "total_thick_mm": 10, "glass_type": "Clear", "max_area_m2": 6.6},
    ])
    st.set_get_all("Item", [
        {"name": "KINH-01", "weight_per_unit": 15.0,
         "item_name": "Kính giữ chỗ"},
    ])
    st.set_get_all("Item Price", [
        {"name": "IP-0", "item_code": "GM-01",
         "price_list_rate": 300000, "price_list": "Standard Selling"},
        {"name": "IP-2", "item_code": "GM-02",
         "price_list_rate": 250000, "price_list": "Standard Selling"},
        {"name": "IP-3", "item_code": "GM-03",
         "price_list_rate": 280000, "price_list": "Standard Selling"},
        {"name": "IP-4", "item_code": "KINH-01",
         "price_list_rate": 120000, "price_list": "Standard Selling"},
    ])
    st.set_get_all("AL Variable Library", [])
    st.set_get_all("AL Variable Dimension Mapping", [])
    st.set_get_all("AL Slug Library", [])
    st.set_get_all("AL Material Category", [
        {"name": "VL_KINH", "default_scrap_pct": 0.03,
         "requires_glass_master": 1},
    ])
    return st


def _one_glass_group(result):
    groups = result.get("glass_groups") or []
    assert len(groups) == 1, result
    return groups[0]


def test_glass_groups_effective_code_saved():
    """Đường 1 — user đã chọn kính cho vị trí (`glass_master_map`)."""
    import alumglass.api as api

    line = dict(_GLASS_LINE_NO_DEFAULT)
    _setup_glass_group_case(line, saved_map={"__slug__kinh_tren": "GM-02"})
    group = _one_glass_group(api.get_variable_set_for_bom("BOM-1", "QI-0001"))
    assert group["rep"] == "__slug__kinh_tren", group
    assert group["saved"] == "GM-02", group
    assert group["effective_code"] == "GM-02", group
    assert group["effective_source"] == "saved", group
    assert group["effective_name"] == "Kính xanh 8 mm", group
    assert group["effective_is_glass_master"] is True, group
    assert group["price"] == 250000, group
    assert group["has_price"] is True, group
    assert group["price_list"] == "Standard Selling", group
    assert group["price_approx"] is False, group


def test_glass_groups_effective_code_override():
    """Đường 2 — mã kính global cũ (`glass_master`), chưa chọn theo vị trí."""
    import alumglass.api as api

    line = dict(_GLASS_LINE_NO_DEFAULT)
    _setup_glass_group_case(line, saved_map={}, override="GM-03")
    group = _one_glass_group(api.get_variable_set_for_bom("BOM-1", "QI-0001"))
    assert group["saved"] == "", group
    assert group["effective_code"] == "GM-03", group
    assert group["effective_source"] == "override", group
    assert group["effective_is_glass_master"] is True, group
    assert group["price"] == 280000, group


def test_glass_groups_effective_code_bom_default():
    """Đường 3 — mã khai sẵn trên dòng BOM (`default_glass_master`)."""
    import alumglass.api as api

    line = dict(_GLASS_LINE_NO_DEFAULT)
    line["item_code"] = ""
    line["default_glass_master"] = "GM-01"
    _setup_glass_group_case(line, saved_map={})
    group = _one_glass_group(api.get_variable_set_for_bom("BOM-1", "QI-0001"))
    assert group["rep"] == "GM-01", group
    assert group["saved"] == "", group
    assert group["effective_code"] == "GM-01", group
    assert group["effective_source"] == "bom_default", group
    assert group["effective_name"] == "Kính trắng 8 mm", group
    assert group["effective_is_glass_master"] is True, group
    assert group["price"] == 300000, group
    assert group["has_price"] is True, group


def test_glass_groups_effective_code_item_code():
    """Đường 4 — không có kính nào được chọn ⇒ engine dùng `item_code` dòng."""
    import alumglass.api as api

    line = dict(_GLASS_LINE_NO_DEFAULT)
    _setup_glass_group_case(line, saved_map={})
    group = _one_glass_group(api.get_variable_set_for_bom("BOM-1", "QI-0001"))
    assert group["saved"] == "", group
    assert group["effective_code"] == "KINH-01", group
    assert group["effective_source"] == "item_code", group
    # Mã GIỮ CHỖ của dòng BOM — có trong Item nhưng KHÔNG có trong
    # AL Glass Master ⇒ dialog ⛔ không được nhét vào control Link kính.
    assert group["effective_is_glass_master"] is False, group
    assert group["effective_name"] == "Kính giữ chỗ", group
    assert group["price"] == 120000, group


def test_get_glass_master_price_matches_engine_unit_price():
    """🔴 GIÁ DIALOG == GIÁ ENGINE: cùng mã, cùng inputs, cùng bảng giá."""
    import alumglass.api as api

    orch = _run_default_glass_case(with_price=True)
    engine_line = _line(orch, "kinh_tren")
    base._STUB.has_permission = lambda *a, **k: True

    result = api.get_glass_master_price("QI-0001", "GM-01")
    assert result["success"] is True, result
    assert result["code"] == "GM-01", result
    assert result["name"] == "Kính trắng 8 mm", result
    assert result["has_price"] is True, result
    assert result["approx"] is False, result
    assert result["note"] == "", result
    assert result["price_list"] == "Standard Selling", result
    assert result["price"] == engine_line["unit_price"] == 300000, \
        (result, engine_line)


def test_get_glass_master_price_matches_engine_with_dimension():
    """🔴 CA KHÓ NHẤT: có pricing dimension (màu sắc) + 2 dòng giá cho mã kính.

    Engine chọn dòng gắn màu (`custom_color = WHITE`) → 320 000. API dialog MUST
    ra ĐÚNG con số đó, ⛔ không phải dòng "trần" 300 000.
    """
    import alumglass.api as api

    orch = _run_default_glass_case(with_price=True, with_dimensions=True)
    engine_line = _line(orch, "kinh_tren")
    assert engine_line["unit_price"] == 320000, engine_line
    base._STUB.has_permission = lambda *a, **k: True

    result = api.get_glass_master_price("QI-0001", "GM-01")
    assert result["success"] is True, result
    assert result["price"] == engine_line["unit_price"] == 320000, \
        (result, engine_line)
    # Dimension đã áp được ⇒ KHÔNG phải "xấp xỉ".
    assert result["approx"] is False, result


def test_get_glass_master_price_approx_when_dimension_missing():
    """Thiếu giá trị dimension ⇒ trả dòng Item Price THÔ + `approx=True` +
    câu "sẽ chốt khi hệ thống tính lại giá" (⛔ không im lặng trả số khác
    engine; ⛔ không chỉ vào nút "Tính giá" — dialog không có nút đó)."""
    import alumglass.api as api

    _run_default_glass_case(with_price=True, with_dimensions=True,
                            with_dim_value=False)
    base._STUB.has_permission = lambda *a, **k: True

    result = api.get_glass_master_price("QI-0001", "GM-01")
    assert result["success"] is True, result
    # Dòng giá "trần" (không gắn màu) — engine cũng ra đúng số này với cùng
    # inputs, nhưng API nói rõ là CHƯA áp đủ dimension.
    assert result["price"] == 300000, result
    assert result["has_price"] is True, result
    assert result["approx"] is True, result
    assert "sẽ chốt khi hệ thống tính lại giá" in result["note"], result
    # ⛔ Không chỉ vào nút không tồn tại trên dialog.
    assert "Tính giá" not in result["note"], result


def test_glass_groups_without_quotation_item_keeps_contract():
    """Gọi KIỂU CŨ (chỉ `bom_code`): field cũ giữ nguyên + field mới vẫn có
    mặt, giá đi đường XẤP XỈ (⛔ không vỡ hợp đồng của dialog bản cũ)."""
    import alumglass.api as api

    _setup_glass_group_case(dict(_GLASS_LINE_NO_DEFAULT), saved_map={})
    result = api.get_variable_set_for_bom("BOM-1")
    group = _one_glass_group(result)
    # Field cũ — hợp đồng trước Pha 3.
    assert group["rep"] == "__slug__kinh_tren", group
    assert group["slug"] == "kinh_tren", group
    assert group["is_real_master"] is False, group
    assert group["default"] == "", group
    # Field mới — "chưa có báo giá" ⇒ xấp xỉ.
    assert group["saved"] == "", group
    assert group["effective_code"] == "KINH-01", group
    assert group["effective_source"] == "item_code", group
    assert group["effective_is_glass_master"] is False, group
    assert group["price_approx"] is True, group
    assert group["price"] == 120000, group


def test_get_glass_master_price_checks_permission():
    """Phải đi qua ĐÚNG cổng quyền dùng chung với calculate_bom."""
    import alumglass.api as api

    calls = []

    def _deny(name, ptype="read"):
        calls.append((name, ptype))
        raise RuntimeError("không có quyền")

    original = api._require_quotation_item_permission
    api._require_quotation_item_permission = _deny
    try:
        try:
            api.get_glass_master_price("QI-0001", "GM-01")
            raise AssertionError("phải bị chặn bởi cổng quyền")
        except RuntimeError:
            pass
    finally:
        api._require_quotation_item_permission = original
    assert calls == [("QI-0001", "read")], calls


def test_get_glass_master_price_zero_rate_is_a_real_price():
    """Dòng Item Price có THẬT với giá 0 đồng (hàng tặng/kính giá 0) KHÔNG
    được báo "chưa có giá" — `has_price` = CÓ DÒNG GIÁ, ⛔ không phải price > 0."""
    import alumglass.api as api

    st = _setup_glass_group_case(dict(_GLASS_LINE_NO_DEFAULT), saved_map={})
    for row in st.get_all_rows["Item Price"]:
        if row["item_code"] == "GM-01":
            row["price_list_rate"] = 0
    base._STUB.has_permission = lambda *a, **k: True

    result = api.get_glass_master_price("QI-0001", "GM-01")
    assert result["success"] is True, result
    assert result["price"] == 0, result
    assert result["has_price"] is True, result      # giá 0 là giá THẬT
    assert "chưa có giá" not in result["note"], result


def test_get_glass_master_price_no_row_means_has_price_false():
    """KHÔNG có dòng Item Price nào ⇒ `has_price = False` (đối chứng của ca
    giá 0 ở trên — 2 trạng thái phải phân biệt được)."""
    import alumglass.api as api

    st = _setup_glass_group_case(dict(_GLASS_LINE_NO_DEFAULT), saved_map={})
    st.get_all_rows["Item Price"] = [
        r for r in st.get_all_rows["Item Price"]
        if r["item_code"] != "GM-01"]
    base._STUB.has_permission = lambda *a, **k: True

    result = api.get_glass_master_price("QI-0001", "GM-01")
    assert result["success"] is True, result
    assert result["price"] == 0, result
    assert result["has_price"] is False, result
    assert 'bảng giá "Standard Selling"' in result["note"], result


def test_get_glass_master_price_missing_price_note():
    """Mã kính CHƯA có giá ⇒ nói rõ tên bảng giá cần kiểm, ⛔ không bịa số."""
    import alumglass.api as api

    _run_default_glass_case(with_price=False)
    base._STUB.has_permission = lambda *a, **k: True

    result = api.get_glass_master_price("QI-0001", "GM-01")
    assert result["success"] is True, result
    assert result["price"] == 0, result
    assert result["has_price"] is False, result
    assert 'bảng giá "Standard Selling"' in result["note"], result


def test_get_glass_master_price_unknown_code():
    """Mã kính không tồn tại ⇒ câu người đọc, ⛔ không phơi mã kỹ thuật."""
    import alumglass.api as api

    base._STUB.has_permission = lambda *a, **k: True
    result = api.get_glass_master_price("QI-0001", "GM-KHONG-CO")
    assert result == {"success": False, "message": "Không tìm thấy mã kính này."}, \
        result


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
