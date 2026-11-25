# -*- coding: utf-8 -*-
"""CHẶNG 2A/2C — kiểm DocType CHUẨN `AL Rule` (gộp rule về một chỗ).

BỐI CẢNH
────────
`AL Rule` thay cho cặp doctype rule song song trước đây (đã xoá 2026-11-23).
Cột kết quả do `result_type` quyết định:

    NUMBER ⇒ `result_value` (trên 2 bảng con DÙNG CHUNG)
    ITEM   ⇒ `result_item`

Bộ test chứng minh:
  (1) `resolve()` đúng cho NUMBER và ITEM (CONSTANT / THRESHOLD / LOOKUP),
      giữ nguyên ngữ nghĩa biên `[from, to)` + lưới tương thích dữ liệu cũ;
  (2) `is_active = 0` ⇒ `resolve()` trả None (cả 2 loại kết quả);
  (3) validate: đúng cột kết quả theo `result_type`; thiếu cột kết quả ⇒ throw;
      dòng mang CẢ HAI cột kết quả ⇒ throw;
  (4) cấm `result_type = ITEM` + `rule_type = CONSTANT`;
  (5) `from > to` ⇒ throw; chạm biên / `from == to` ⇒ hợp lệ (⛔ throw).

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_al_rule.py
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

from alumglass.al_formula_rules.doctype.al_rule.al_rule import (  # noqa: E402
    ALRule,
    RESULT_FIELD_BY_TYPE,
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
# Dựng rule
# ═══════════════════════════════════════════════════════════════════
def _make_rule(
    result_type="NUMBER",
    rule_type="THRESHOLD",
    threshold_rows=None,
    lookup_rows=None,
    constant_value=None,
    active=1,
):
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
    doc.threshold_rows = threshold_rows if threshold_rows is not None else []
    doc.lookup_rows = lookup_rows if lookup_rows is not None else []
    return doc


def _threshold_rows(field, values=(100, 200), upper_open=True):
    """2 dải liền nhau; `upper_open=False` là kiểu dữ liệu CŨ có khe 0.1."""
    second_from = 10 if upper_open else 10.1
    return [
        {"from_value": 0, "to_value": 10, field: values[0]},
        {"from_value": second_from, "to_value": 20, field: values[1]},
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
# (1) resolve() — NUMBER
# ═══════════════════════════════════════════════════════════════════
def test_result_field_suy_tu_result_type():
    assert RESULT_FIELD_BY_TYPE == {"NUMBER": "result_value", "ITEM": "result_item"}
    assert _make_rule(result_type="NUMBER").result_field == "result_value"
    assert _make_rule(result_type="ITEM", rule_type="LOOKUP").result_field == "result_item"


def test_number_threshold_resolve_dung_bien():
    doc = _make_rule(threshold_rows=_threshold_rows("result_value"))
    for input_value, expected in ((0, 100), (9.99, 100), (10, 200),
                                  (19.99, 200), (20, 200), (21, None)):
        actual = doc.resolve(input_value)
        assert actual == expected, (
            "NUMBER input %r: mong %r, nhận %r"
            % (input_value, expected, actual))


def test_number_du_lieu_cu_kieu_dong_van_khop():
    """Lưới tương thích: rule cũ khai [0,10] + [10.1,20] với input 10."""
    doc = _make_rule(threshold_rows=_threshold_rows("result_value", upper_open=False))
    assert doc.resolve(10) == 100, "input đúng biên dưới phải khớp (lưới tương thích)"
    assert doc.resolve(10.05) is None, "nằm trong khe 10→10.1 thì không khớp dòng nào"
    assert doc.resolve(20) == 200, "biên trên dải cuối khớp theo lưới tương thích"


def test_number_constant_va_lookup_resolve():
    constant = _make_rule(
        rule_type="CONSTANT", constant_value=48, threshold_rows=[])
    assert constant.resolve(None) == 48, "CONSTANT phải trả constant_value kể cả input rỗng"

    lookup = _make_rule(
        rule_type="LOOKUP",
        lookup_rows=[
            {"key_field": "LOWE", "result_value": "1.2"},
            {"key_field": "DON", "result_value": "0.9"},
        ],
    )
    assert lookup.resolve("LOWE") == "1.2"
    assert lookup.resolve("KING") is None


def test_sort_theo_from_value_khong_theo_thu_tu_luu():
    rows = list(reversed(_threshold_rows("result_value")))
    doc = _make_rule(threshold_rows=rows)
    assert doc.resolve(5) == 100
    assert doc.resolve(15) == 200


# ═══════════════════════════════════════════════════════════════════
# (1b) resolve() — ITEM
# ═══════════════════════════════════════════════════════════════════
def test_item_threshold_resolve_tra_ma():
    doc = _make_rule(
        result_type="ITEM",
        threshold_rows=_threshold_rows(
            "result_item", values=("C3209-20", "C3211-20")),
    )
    for input_value, expected in ((0, "C3209-20"), (9.99, "C3209-20"),
                                  (10, "C3211-20"), (19.99, "C3211-20"),
                                  (20, "C3211-20"), (21, None)):
        actual = doc.resolve(input_value)
        assert actual == expected, (
            "ITEM input %r: mong %r, nhận %r"
            % (input_value, expected, actual))


def test_item_lookup_resolve_tra_ma():
    doc = _make_rule(
        result_type="ITEM",
        rule_type="LOOKUP",
        lookup_rows=[
            {"key_field": "LOWE", "result_item": "KEO-TT-01"},
            {"key_field": "DON", "result_item": "KEO-TT-02"},
        ],
    )
    assert doc.resolve("LOWE") == "KEO-TT-01"
    assert doc.resolve("DON") == "KEO-TT-02"
    assert doc.resolve("KHAC") is None


def test_item_threshold_input_rong_tra_none():
    doc = _make_rule(
        result_type="ITEM",
        threshold_rows=_threshold_rows("result_item", values=("A", "B")),
    )
    assert doc.resolve(None) is None
    assert doc.resolve("") is None


# ═══════════════════════════════════════════════════════════════════
# (2) is_active = 0 ⇒ None
# ═══════════════════════════════════════════════════════════════════
def test_rule_tat_resolve_tra_none():
    number = _make_rule(
        threshold_rows=_threshold_rows("result_value"), active=0)
    item = _make_rule(
        result_type="ITEM",
        threshold_rows=_threshold_rows("result_item", values=("A", "B")),
        active=0)
    assert number.resolve(5) is None, "rule TẮT mà vẫn trả giá trị"
    assert item.resolve(5) is None, "rule TẮT mà vẫn trả mã vật tư"

    # Đối chứng dương: bật lại ⇒ có kết quả.
    assert _make_rule(
        threshold_rows=_threshold_rows("result_value"), active=1).resolve(5) == 100


def test_rule_tat_constant_va_lookup_cung_tra_none():
    constant = _make_rule(
        rule_type="CONSTANT", constant_value=7, active=0)
    assert constant.resolve(None) is None, "CONSTANT tắt vẫn trả giá trị"

    lookup = _make_rule(
        rule_type="LOOKUP",
        lookup_rows=[{"key_field": "K", "result_value": "9"}],
        active=0,
    )
    assert lookup.resolve("K") is None


# ═══════════════════════════════════════════════════════════════════
# (3) validate — cột kết quả
# ═══════════════════════════════════════════════════════════════════
def test_validate_hop_le_hai_loai():
    _make_rule(threshold_rows=_threshold_rows("result_value")).validate()
    _make_rule(
        result_type="ITEM",
        threshold_rows=_threshold_rows("result_item", values=("A", "B")),
    ).validate()
    _make_rule(
        rule_type="LOOKUP",
        lookup_rows=[{"key_field": "K", "result_value": "1"}],
    ).validate()
    _make_rule(
        result_type="ITEM",
        rule_type="LOOKUP",
        lookup_rows=[{"key_field": "K", "result_item": "ITEM-K"}],
    ).validate()


def test_constant_value_0_la_gia_tri_hop_le():
    """`0` KHÔNG được coi là thiếu (bẫy truthiness)."""
    _make_rule(rule_type="CONSTANT", constant_value=0).validate()


def test_constant_thieu_gia_tri_bi_chan():
    _assert_throws(
        lambda: _make_rule(rule_type="CONSTANT", constant_value=None).validate(),
        "Giá trị cố định", "CONSTANT thiếu constant_value")


def test_thieu_cot_ket_qua_bi_chan():
    _assert_throws(
        lambda: _make_rule(
            threshold_rows=[{"from_value": 0, "to_value": 10}]).validate(),
        "Giá trị kết quả", "NUMBER thiếu result_value")

    _assert_throws(
        lambda: _make_rule(
            result_type="ITEM",
            threshold_rows=[{"from_value": 0, "to_value": 10}]).validate(),
        "Mã vật tư", "ITEM thiếu result_item")

    _assert_throws(
        lambda: _make_rule(
            rule_type="LOOKUP",
            lookup_rows=[{"key_field": "K"}]).validate(),
        "Giá trị kết quả", "LOOKUP NUMBER thiếu result_value")


def test_dong_mang_ca_hai_cot_ket_qua_bi_chan():
    """Đúng MỘT cột kết quả mỗi dòng — 2 cột là mơ hồ, ⛔ cho lưu."""
    _assert_throws(
        lambda: _make_rule(threshold_rows=[
            {"from_value": 0, "to_value": 10,
             "result_value": 100, "result_item": "ITEM-A"},
        ]).validate(),
        "phải để trống", "NUMBER dòng mang cả result_item")

    _assert_throws(
        lambda: _make_rule(
            result_type="ITEM",
            threshold_rows=[
                {"from_value": 0, "to_value": 10,
                 "result_item": "ITEM-A", "result_value": 100},
            ],
        ).validate(),
        "phải để trống", "ITEM dòng mang cả result_value")

    _assert_throws(
        lambda: _make_rule(
            rule_type="LOOKUP",
            lookup_rows=[
                {"key_field": "K", "result_value": "1", "result_item": "ITEM-K"},
            ],
        ).validate(),
        "phải để trống", "LOOKUP dòng mang cả 2 cột")


def test_thieu_dong_bi_chan():
    _assert_throws(
        lambda: _make_rule(threshold_rows=[]).validate(),
        "ít nhất 1 dòng", "THRESHOLD rỗng")
    _assert_throws(
        lambda: _make_rule(rule_type="LOOKUP", lookup_rows=[]).validate(),
        "ít nhất 1 dòng", "LOOKUP rỗng")


# ═══════════════════════════════════════════════════════════════════
# (4) Cấm ITEM + CONSTANT
# ═══════════════════════════════════════════════════════════════════
def test_cam_item_constant():
    _assert_throws(
        lambda: _make_rule(
            result_type="ITEM", rule_type="CONSTANT", constant_value=1).validate(),
        "quy tắc CONSTANT không dùng được với Loại kết quả = ITEM",
        "ITEM+CONSTANT",
    )
    # Đối chứng dương: NUMBER+CONSTANT vẫn hợp lệ.
    _make_rule(result_type="NUMBER", rule_type="CONSTANT", constant_value=1).validate()


def test_result_type_va_rule_type_sai_bi_chan():
    _assert_throws(
        lambda: _make_rule(result_type="TEXT").validate(),
        "NUMBER hoặc ITEM", "result_type lạ")
    _assert_throws(
        lambda: _make_rule(rule_type="MAGIC").validate(),
        "Kiểu quy tắc", "rule_type lạ")


# ═══════════════════════════════════════════════════════════════════
# (5) Biên dải ngưỡng
# ═══════════════════════════════════════════════════════════════════
def test_from_lon_hon_to_bi_chan():
    _assert_throws(
        lambda: _make_rule(threshold_rows=[
            {"from_value": 20, "to_value": 10, "result_value": 100},
        ]).validate(),
        "'Từ'", "from > to")


def test_cham_bien_va_from_bang_to_hop_le():
    """Đối chứng dương: chạm biên KHÔNG throw; from == to là dải rỗng hợp lệ."""
    _make_rule(threshold_rows=[
        {"from_value": 0, "to_value": 10, "result_value": 100},
        {"from_value": 10, "to_value": 20, "result_value": 200},
    ]).validate()

    _make_rule(threshold_rows=[
        {"from_value": 10, "to_value": 10, "result_value": 100},
    ]).validate()


def test_chong_lap_bi_chan():
    _assert_throws(
        lambda: _make_rule(threshold_rows=[
            {"from_value": 0, "to_value": 10, "result_value": 100},
            {"from_value": 5, "to_value": 20, "result_value": 200},
        ]).validate(),
        "chồng lấp", "chồng lấp")


# ═══════════════════════════════════════════════════════════════════
# (6) HỢP ĐỒNG JSON — tra cứu hiện TÊN quy tắc + quyền cho role thật
# ═══════════════════════════════════════════════════════════════════
def _rule_json():
    """Đọc thẳng `al_rule.json` — đây là thứ Frappe sync DocPerm/field từ."""
    import json

    path = os.path.join(
        _REPO_ROOT, "alumglass", "al_formula_rules", "doctype", "al_rule",
        "al_rule.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_json_title_field_la_ten_quy_tac():
    """Ô Item Rule hiện TÊN quy tắc (⛔ mã nội bộ) nhờ `title_field`."""
    data = _rule_json()
    assert data.get("title_field") == "rule_name", (
        "thiếu `title_field = rule_name` ⇒ ô chọn Item Rule hiện `rule_code`: %r"
        % (data.get("title_field"),))
    assert data.get("show_title_field_in_link") == 1, (
        "thiếu `show_title_field_in_link` ⇒ Frappe ⛔ dùng title_field ở ô Link")


def test_json_khong_cho_doi_ten_vi_ma_la_hop_dong_cong_thuc():
    """UX1 🟡6: mã rule là hợp đồng với công thức ⇒ ⛔ cho rename."""
    assert _rule_json().get("allow_rename") == 0, (
        "`allow_rename` phải = 0: đổi mã quy tắc sẽ làm công thức đang trỏ "
        "tới nó gãy")


def test_json_cap_quyen_cho_al_bom_manager():
    """Sau deploy role nghiệp vụ phải ĐỌC được AL Rule.

    `install_roles` chỉ chạy ở `after_install` (⛔ `after_migrate`) nên site
    đã cài KHÔNG được cấp lại quyền. Frappe sync DocPerm từ JSON khi migrate
    ⇒ role thật phải có block trong JSON, nếu không AL BOM Manager mất quyền
    đọc ⇒ tra rule hỏng ngay sau deploy.
    """
    from alumglass.setup.install_roles import MODULE_PERMISSIONS

    expected = MODULE_PERMISSIONS["AL Formula Rules"]["AL BOM Manager"]
    perms = {perm.get("role"): perm
             for perm in (_rule_json().get("permissions") or [])}

    assert "System Manager" in perms, (
        "block System Manager bị mất khỏi JSON: %r" % (sorted(perms),))

    bom = perms.get("AL BOM Manager")
    assert bom, (
        "thiếu DocPerm 'AL BOM Manager' trong al_rule.json ⇒ site đã cài "
        "mất quyền đọc AL Rule sau migrate (chỉ còn System Manager)")
    for field, value in expected.items():
        assert bom.get(field) == value, (
            "quyền '%s' của AL BOM Manager lệch MODULE_PERMISSIONS["
            "'AL Formula Rules']: JSON=%r, kỳ vọng=%r"
            % (field, bom.get(field), value))


def _row_json(name):
    """Đọc JSON của 1 bảng con dùng chung."""
    import json

    path = os.path.join(
        _REPO_ROOT, "alumglass", "al_formula_rules", "doctype", name,
        name + ".json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_bang_con_hien_cot_ket_qua_khi_parent_khong_co_result_type():
    """⛔ ẩn cột kết quả khi parent KHÔNG khai `result_type`.

    `depends_on` kiểu `eval:` chạy với scope `{doc, parent}`
    (`frappe/public/js/frappe/form/grid_row.js:779`). Parent của 2 bảng con
    này có thể là form cũ / bản ghi import tay ⛔ khai `result_type`. Nếu
    biểu thức chỉ là `parent.result_type=='NUMBER'` thì
    `undefined == 'NUMBER'` ⇒ false ⇒ cột kết quả BỊ ẨN, admin mất luôn ô
    để sửa.

    Vì vậy biểu thức PHẢI có nhánh "parent không khai result_type ⇒ hiện".
    Ca này khoá lại để lần sau ai rút gọn biểu thức sẽ thành ĐỎ.
    """
    for name in ("al_rule_threshold_row", "al_rule_lookup_row"):
        fields = {field.get("fieldname"): field
                  for field in (_row_json(name).get("fields") or [])}
        for fieldname, expected in (
                ("result_value", "'NUMBER'"), ("result_item", "'ITEM'")):
            depends_on = fields[fieldname].get("depends_on") or ""
            assert depends_on.startswith("eval:!parent"), (
                "%s.%s: `depends_on` thiếu nhánh 'parent rỗng' ⇒ form cũ "
                "(⛔ có result_type) làm ẩn cột kết quả: %r"
                % (name, fieldname, depends_on))
            assert "!parent.result_type" in depends_on, (
                "%s.%s: thiếu nhánh 'parent ⛔ khai result_type ⇒ HIỆN': %r"
                % (name, fieldname, depends_on))
            assert "|| parent.result_type==" + expected in depends_on, (
                "%s.%s: thiếu nhánh hiện theo đúng kiểu %s: %r"
                % (name, fieldname, expected, depends_on))


# ═══════════════════════════════════════════════════════════════════
# (7) Cổng "sai loại rule" phải chạy ở AL Bom Set.validate (lối đi THẬT)
# ═══════════════════════════════════════════════════════════════════
# Vì sao kiểm ở đây: Frappe v14 KHÔNG gọi `validate()` của dòng con khi lưu
# chứng từ cha (xem chú thích trong `ALBomSet.validate`), nên đoạn kiểm trong
# `ALBomItem.validate` là mã CHẾT trên đường thật. Nếu ai bỏ lời gọi khỏi
# `ALBomSet.validate`, các ca dưới đây thành ĐỎ.
def _bom_item(rule_code, slug="kinh_tren", idx=1):
    return base.FakeDoc({
        "slug": slug, "idx": idx,
        "item_selection_mode": "Rule",
        "item_rule": rule_code,
        "rule_input_expr": "items.%s.glass_thick" % slug,
    })


def _bom_set(items):
    """Bom Set tối thiểu — bỏ 2 bước cần master data đầy đủ, giữ đúng cổng cần kiểm.

    `_validate_child_formulas` / `_warn_rule_input_expr` đã có bộ test riêng
    (test_phase_b_fbmax, test trong repo) — ở đây chốt việc GỌI cổng rule.
    """
    from alumglass.al_bom_engine.doctype.al_bom_set.al_bom_set import ALBomSet

    doc = ALBomSet()
    doc._data = {"name": "BOM-THU"}
    doc.items = list(items)
    doc._validate_child_formulas = lambda: None
    doc._warn_rule_input_expr = lambda: None
    return doc


def _register_rules(rows):
    """Nạp bảng `AL Rule` cho stub (1 lượt `frappe.get_all`, ⛔ N+1)."""
    base._reset_stub()
    STUB.set_get_all("AL Rule", rows)


def test_bom_set_chan_dong_tro_rule_tinh_gia():
    """Dòng Rule trỏ quy tắc NUMBER ⇒ chặn lưu, câu nêu TÊN + đường đi."""
    _register_rules([
        {"name": "RULE-GIA", "result_type": "NUMBER", "rule_name": "Giá màu"}])

    message = _assert_throws(
        lambda: _bom_set([_bom_item("RULE-GIA")]).validate(),
        "quy tắc TÍNH GIÁ TRỊ", "Bom Set dòng trỏ rule NUMBER")

    assert "Giá màu" in message, (
        "câu lỗi phải nêu TÊN quy tắc: %s" % message)
    assert "RULE-GIA" not in message, (
        "câu lỗi phơi mã nội bộ: %s" % message)
    assert "Loại kết quả = ITEM" in message, message
    assert "Item Selection Mode sang Fixed/Formula" in message, message


def test_bom_set_nhan_dong_tro_rule_chon_ma():
    """Đối chứng dương: rule ITEM ⇒ ⛔ chặn nhầm."""
    _register_rules([
        {"name": "RULE-NEP", "result_type": "ITEM", "rule_name": "Nẹp theo dày"}])

    _bom_set([_bom_item("RULE-NEP")]).validate()  # ⛔ được throw


def test_bom_set_chan_dong_tro_ma_khong_ton_tai():
    """Mã rule không tồn tại ⇒ câu riêng (⛔ lọt xuống bước tính giá)."""
    _register_rules([])

    message = _assert_throws(
        lambda: _bom_set([_bom_item("RULE-MAT")]).validate(),
        "không tìm thấy quy tắc 'RULE-MAT'", "Bom Set dòng trỏ mã sai")
    assert "chọn lại quy tắc chọn mã vật tư" in message, message


def test_bom_set_bo_qua_dong_khong_dung_rule():
    """Dòng mode khác Rule ⛔ bị tra bảng `AL Rule` (tránh chặn oan)."""
    _register_rules([])
    doc = _bom_set([
        base.FakeDoc({"slug": "kinh_tren", "idx": 1,
                      "item_selection_mode": "Fixed", "item_code": "KINH-01"}),
    ])
    doc.validate()  # ⛔ được throw


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
