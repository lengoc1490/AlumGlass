# -*- coding: utf-8 -*-
"""B1 — MỘT nguồn duy nhất cho "field nào là field công thức".

Thiết kế: `docs/design/gop-noi-cau-hinh-bien-va-tinh-toan.md` mục B1 + §3 P1.

Trước bản vá có BA danh sách cùng trả lời một câu:
    1. `AL Formula Field` (11 bản ghi seed) — sổ đăng ký, editor JS đã dùng;
    2. `AL Bom Set.formula_fieldnames` (JSON mỗi bộ một danh sách);
    3. `DEFAULT_FORMULA_FIELDS` (6 tên cứng, bom_orchestrator.py).
Engine đọc (2) rồi rơi về (3); (1) không ai phía máy chủ đọc.

Thứ tự ưu tiên đã cài (`BomOrchestrator._resolve_formula_fieldnames`):
    1. Danh sách riêng của bộ CÓ giá trị ⇒ giữ hành vi cũ + cảnh báo
       `formula_fields_legacy_list:<mã bộ>` (B0 chưa đo ⇒ ⛔ đổi số tiền);
    2. Không có ⇒ sổ đăng ký `AL Formula Field` (items, is_active, sort_order);
    3. Sổ đăng ký RỖNG ⇒ DEFAULT + cảnh báo `formula_fields_fallback_registry`;
    4. Sổ đăng ký THIẾU field dòng BOM đang có công thức ⇒ dùng đúng registry
       + cảnh báo `formula_fields_registry_thieu:<field>` (⛔ tự thêm lại).

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_formula_field_registry.py
"""
import json
import os
import sys
import types
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_phase_b_fbmax as base  # noqa: E402  (cài stub `frappe` khi import)

STUB = base._STUB

from alumglass.api import formula_registry  # noqa: E402
import alumglass.engine.bom_orchestrator as eo  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# Stub: tôn trọng `order_by` của `frappe.get_all` cho AL Formula Field
# ═══════════════════════════════════════════════════════════════════
# Stub gốc bỏ qua `order_by` ⇒ nếu không vá, phép kiểm "thứ tự sort_order"
# là KIỂM RỖNG (rows trả về đúng thứ tự đăng ký, luôn khớp dù code sắp xếp
# sai). Chỉ sắp cho đúng 1 doctype để không đổi hành vi test khác.
_ORIG_GET_ALL = STUB.get_all


def _get_all_order_aware(doctype, filters=None, fields=None, order_by=None,
                         limit=None, pluck=None):
    rows = _ORIG_GET_ALL(doctype, filters=filters, fields=fields,
                         order_by=order_by, limit=limit, pluck=pluck)
    if doctype == "AL Formula Field" and order_by and "sort_order" in order_by:
        rows = sorted(rows, key=lambda r: (r.get("sort_order") or 0,
                                           r.get("fieldname") or ""))
    return rows


STUB.get_all = _get_all_order_aware


# ═══════════════════════════════════════════════════════════════════
# Fixture
# ═══════════════════════════════════════════════════════════════════
def _registry_row(fieldname, sort_order=10, child_table="items",
                  is_active=1, target_doctype="AL Bom Set"):
    return {
        "target_doctype": target_doctype,
        "child_table": child_table,
        "fieldname": fieldname,
        "id_field": "slug",
        "editor_opts": "{}",
        "sort_order": sort_order,
        "is_active": is_active,
    }


def _setup_registry(rows=None, meta=True):
    """Dựng môi trường đọc AL Formula Field. `rows=None` ⇒ bảng CHƯA tồn tại."""
    # `frappe.local` mới = xoá cache registry theo request (formula_registry).
    STUB.local = types.SimpleNamespace()
    STUB.get_all_rows.pop("AL Formula Field", None)
    STUB.docs.pop(("DocType", "AL Formula Field"), None)
    if rows is None:
        return
    STUB.set_doc("DocType", "AL Formula Field", {})
    STUB.set_get_all("AL Formula Field", rows)
    if meta:
        # Site thật có meta ⇒ code đọc cột `target_doctype`.
        STUB.set_meta_fields("AL Formula Field",
                             [{"fieldname": "target_doctype"}])


def _make_orch(formula_fieldnames=None, bom_items=None, set_code="ALBS-1"):
    """Orchestrator tối thiểu (không chạy b0/b1/b2) — đủ cho B1 + b3."""
    orch = object.__new__(eo.BomOrchestrator)
    orch._formula_fieldnames = None
    orch.bom_engine_errors = {}
    orch.bom_items = list(bom_items or [])
    orch.inputs = {}
    orch.row_literals = {}
    orch._line_formulas = defaultdict(dict)
    bom_set = base.FakeDoc({
        "name": set_code,
        "formula_fieldnames": formula_fieldnames,
    }, set_code)
    orch._get_bom_set = lambda: bom_set
    return orch


_BOM_ITEMS = [
    {"slug": "kinh_tren", "width": "2000", "height": "1000", "qty": "2",
     "show_condition": "", "item_condition_formula": "",
     "rule_input_expr": "", "calc_pattern": ""},
    {"slug": "vien_nhom", "width": "2500", "height": "0", "qty": "4",
     "show_condition": "", "item_condition_formula": "",
     "rule_input_expr": "", "calc_pattern": ""},
]

_SIX = ["width", "height", "qty", "show_condition",
        "item_condition_formula", "rule_input_expr"]


def _registry_six():
    return [_registry_row(name, sort_order=(i + 1) * 10)
            for i, name in enumerate(_SIX)]


# ═══════════════════════════════════════════════════════════════════
# (1) Không có danh sách riêng ⇒ dùng SỔ ĐĂNG KÝ (⛔ DEFAULT)
# ═══════════════════════════════════════════════════════════════════
def test_khong_danh_sach_rieng_thi_dung_so_dang_ky():
    """Registry khác DEFAULT ⇒ kết quả phải là registry, chứng minh ⛔ DEFAULT."""
    _setup_registry([
        _registry_row("he_so_phu", sort_order=10),
        _registry_row("width", sort_order=20),
        _registry_row("height", sort_order=30),
    ])
    orch = _make_orch(formula_fieldnames=None)

    fields = orch._resolve_formula_fieldnames()

    assert fields == ["he_so_phu", "width", "height"], fields
    assert "qty" not in fields, (
        "rơi về DEFAULT_FORMULA_FIELDS thay vì sổ đăng ký: %r" % (fields,))
    keys = set(orch.bom_engine_errors)
    assert not [k for k in keys if k.startswith("formula_fields_legacy_list")], keys
    assert "formula_fields_fallback_registry" not in keys, keys


def test_khong_danh_sach_rieng_va_so_dang_ky_day_du_khong_canh_bao():
    """ĐỐI CHỨNG ÂM: registry đủ field ⇒ KHÔNG cảnh báo thiếu (⛔ kêu tràn lan)."""
    _setup_registry(_registry_six())
    orch = _make_orch(formula_fieldnames=None, bom_items=_BOM_ITEMS)

    fields = orch._resolve_formula_fieldnames()

    assert fields == _SIX, fields
    assert orch.bom_engine_errors == {}, orch.bom_engine_errors


# ═══════════════════════════════════════════════════════════════════
# (2) Có danh sách riêng ⇒ giữ hành vi cũ + CẢNH BÁO
# ═══════════════════════════════════════════════════════════════════
def test_danh_sach_rieng_duoc_giu_va_co_canh_bao():
    """Bộ còn khai danh sách riêng ⇒ dùng nó (⛔ đổi số) + cảnh báo nêu mã bộ."""
    _setup_registry(_registry_six())
    orch = _make_orch(
        formula_fieldnames=json.dumps(["width", "qty"]),
        bom_items=_BOM_ITEMS)

    fields = orch._resolve_formula_fieldnames()

    assert fields == ["width", "qty"], fields
    key = "formula_fields_legacy_list:ALBS-1"
    assert key in orch.bom_engine_errors, orch.bom_engine_errors
    message = orch.bom_engine_errors[key]
    assert "ALBS-1" in message, message
    assert "Formula Fieldnames" in message, message
    # ⛔ cảnh báo rơi lưới / thiếu field khi đang dùng danh sách riêng.
    assert "formula_fields_fallback_registry" not in orch.bom_engine_errors


def test_danh_sach_rieng_rong_thi_khong_canh_bao_legacy():
    """ĐỐI CHỨNG ÂM: bỏ cảnh báo legacy ⇒ test (2) đỏ; ở đây key phải VẮNG.

    Cùng một fixture, chỉ đổi `formula_fieldnames` từ danh sách sang None ⇒
    khoá `formula_fields_legacy_list:*` biến mất. Nếu ai đó bỏ nhánh cảnh
    báo trong code, test (2) đỏ; nếu ai đó kêu vô điều kiện, test này đỏ.
    """
    _setup_registry(_registry_six())
    orch = _make_orch(formula_fieldnames=None, bom_items=_BOM_ITEMS)

    orch._resolve_formula_fieldnames()

    assert not [k for k in orch.bom_engine_errors
                if k.startswith("formula_fields_legacy_list")], \
        orch.bom_engine_errors


# ═══════════════════════════════════════════════════════════════════
# (3) Sổ đăng ký RỖNG ⇒ DEFAULT + cảnh báo TO (⛔ im lặng)
# ═══════════════════════════════════════════════════════════════════
def test_so_dang_ky_rong_thi_roi_luoi_du_phong_va_canh_bao():
    """Bảng AL Formula Field chưa có ⇒ DEFAULT + `formula_fields_fallback_registry`."""
    _setup_registry(rows=None)   # site chưa migrate
    orch = _make_orch(formula_fieldnames=None, bom_items=_BOM_ITEMS)

    fields = orch._resolve_formula_fieldnames()

    assert fields == eo.DEFAULT_FORMULA_FIELDS, fields
    key = "formula_fields_fallback_registry"
    assert key in orch.bom_engine_errors, orch.bom_engine_errors
    message = orch.bom_engine_errors[key]
    assert "AL Formula Field" in message, message
    assert message.lower().startswith("cảnh báo"), message


def test_so_dang_ky_rong_va_danh_sach_rieng_rong_thi_van_canh_bao():
    """ĐỐI CHỨNG ÂM: registry có dữ liệu ⇒ KHÔNG còn cảnh báo rơi lưới."""
    _setup_registry(_registry_six())
    orch = _make_orch(formula_fieldnames="", bom_items=_BOM_ITEMS)

    fields = orch._resolve_formula_fieldnames()

    assert fields == _SIX, fields
    assert "formula_fields_fallback_registry" not in orch.bom_engine_errors, \
        orch.bom_engine_errors


# ═══════════════════════════════════════════════════════════════════
# (4) Sổ đăng ký THIẾU field đang có công thức ⇒ cảnh báo, ⛔ tự thêm lại
# ═══════════════════════════════════════════════════════════════════
def test_so_dang_ky_thieu_field_thi_canh_bao_va_khong_tu_them():
    _setup_registry([
        _registry_row("width", sort_order=10),
        _registry_row("height", sort_order=20),
    ])
    orch = _make_orch(formula_fieldnames=None, bom_items=_BOM_ITEMS)

    fields = orch._resolve_formula_fieldnames()

    assert fields == ["width", "height"], fields
    assert "qty" not in fields, (
        "engine tự thêm lại field thiếu (phá 'một nguồn duy nhất'): %r" % (fields,))
    key = "formula_fields_registry_thieu:qty"
    assert key in orch.bom_engine_errors, orch.bom_engine_errors
    message = orch.bom_engine_errors[key]
    assert "'qty'" in message, message
    assert "AL Formula Field" in message, message
    # Câu cảnh báo nêu cách xử lý (thêm bản ghi) — ⛔ chỉ kêu mà không lối ra.
    assert "Thêm bản ghi" in message, message


def test_so_dang_ky_co_du_field_thi_khong_canh_bao_thieu():
    """ĐỐI CHỨNG ÂM: bỏ nhánh cảnh báo ⇒ test (4) đỏ; registry đủ ⇒ vắng key."""
    _setup_registry(_registry_six())
    orch = _make_orch(formula_fieldnames=None, bom_items=_BOM_ITEMS)

    orch._resolve_formula_fieldnames()

    assert not [k for k in orch.bom_engine_errors
                if k.startswith("formula_fields_registry_thieu")], \
        orch.bom_engine_errors


# ═══════════════════════════════════════════════════════════════════
# (5) Không đổi công thức/kết quả: danh sách riêng cũ == sổ đăng ký đầy đủ
# ═══════════════════════════════════════════════════════════════════
def _formula_pairs(orch):
    return [(f["name"], f["formula"]) for f in orch.bom_formulas]


def test_b3_danh_sach_rieng_cu_bang_so_dang_ky_day_du():
    """Cùng 6 field ⇒ danh sách formula (và kết quả B3) GIỐNG HỆT.

    Đây là cổng "⛔ đổi số tiền": 11 bản ghi seed của `AL Formula Field` khai
    ĐÚNG 6 field của `DEFAULT_FORMULA_FIELDS`, nên bộ đang chạy bằng danh
    sách riêng/`DEFAULT` phải ra y nguyên formula như trước.
    """
    _setup_registry(_registry_six())
    # (a) đường CŨ: danh sách riêng = 6 field
    old = _make_orch(formula_fieldnames=json.dumps(_SIX), bom_items=_BOM_ITEMS)
    old.b3_build_formulas()

    # (b) đường MỚI: sổ đăng ký = đúng 6 field đó
    new = _make_orch(formula_fieldnames=None, bom_items=_BOM_ITEMS)
    new.b3_build_formulas()

    assert old._formula_fieldnames == new._formula_fieldnames == _SIX
    assert _formula_pairs(old) == _formula_pairs(new), (
        "danh sách formula đổi khi chuyển sang sổ đăng ký:\nCŨ: %r\nMỚI: %r"
        % (_formula_pairs(old), _formula_pairs(new)))
    assert dict(old._line_formulas) == dict(new._line_formulas)
    # Formula phải thực sự có mặt (⛔ "bằng nhau vì cả hai cùng rỗng").
    names = [n for n, _f in _formula_pairs(new)]
    assert "kinh_tren__width" in names and "vien_nhom__qty" in names, names


# ═══════════════════════════════════════════════════════════════════
# (6) `get_formula_fieldnames` — lọc is_active/child_table, đúng sort_order
# ═══════════════════════════════════════════════════════════════════
def test_get_formula_fieldnames_loc_va_sap_thu_tu():
    _setup_registry([
        _registry_row("qty", sort_order=30),
        _registry_row("width", sort_order=10),
        _registry_row("height", sort_order=20),
        # is_active = 0 ⇒ bỏ
        _registry_row("show_condition", sort_order=25, is_active=0),
        # bảng con khác ⇒ bỏ khi lọc "items"
        _registry_row("qty_formula", sort_order=5, child_table="khac"),
    ])

    assert formula_registry.get_formula_fieldnames("AL Bom Set") == [
        "width", "height", "qty"]
    # Lọc đúng bảng con được yêu cầu
    assert formula_registry.get_formula_fieldnames("AL Bom Set", "khac") == [
        "qty_formula"]


def test_get_formula_fieldnames_khong_trung_va_bo_field_rong():
    _setup_registry([
        _registry_row("width", sort_order=10),
        _registry_row("width", sort_order=20),   # trùng fieldname
        _registry_row("", sort_order=30),        # rỗng
    ])

    assert formula_registry.get_formula_fieldnames("AL Bom Set") == ["width"]


def test_get_formula_fieldnames_chi_lay_doctype_duoc_hoi():
    _setup_registry([
        _registry_row("width", sort_order=10),
        _registry_row("qty_formula", sort_order=10,
                      target_doctype="AL Accessory Set"),
    ])

    assert formula_registry.get_formula_fieldnames("AL Bom Set") == ["width"]
    assert formula_registry.get_formula_fieldnames("AL Accessory Set") == [
        "qty_formula"]


def test_get_formula_fieldnames_site_chua_migrate_tra_rong():
    """Bảng chưa có ⇒ [] (engine tự KÊU + rơi lưới; hàm ⛔ tự chọn dự phòng)."""
    _setup_registry(rows=None)
    assert formula_registry.get_formula_fieldnames("AL Bom Set") == []


def test_get_formula_fields_hop_dong_cu_khong_doi():
    """Hàm cũ vẫn trả hợp đồng đầy đủ cho editor JS (⛔ phá JS)."""
    _setup_registry([
        _registry_row("width", sort_order=10),
        _registry_row("qty", sort_order=20, child_table=""),
    ])

    rows = formula_registry.get_formula_fields("AL Bom Set")

    assert [r["fieldname"] for r in rows] == ["width", "qty"]
    assert rows[0] == {
        "doctype": "AL Bom Set",
        "child_table": "items",
        "fieldname": "width",
        "id_field": "slug",
        "editor_opts": {},
        "sort_order": 10,
    }, rows[0]


# ═══════════════════════════════════════════════════════════════════
# Runner standalone (không cần pytest)
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
            print(f"  PASS  {name}")
        except Exception:
            failed.append(name)
            print(f"  FAIL  {name}")
            traceback.print_exc()
    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {len(funcs)}  PASS: {passed}  FAIL: {len(failed)}")
    if failed:
        print(f"  FAILED: {failed}")
        raise SystemExit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _main()
