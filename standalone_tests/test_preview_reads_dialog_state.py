# -*- coding: utf-8 -*-
"""PHASE 1.5 "Preview không ghi DB" — 3 API ĐỌC phải thấy trạng thái DIALOG.

BỐI CẢNH (Owner chốt 2026-11-21, tiếp ngay sau phase 1)
─────────────────────────────────────────────────────────
Trước phase 1, mỗi lượt preview đều ghi `al_bom_vars`/`al_bom` xuống DB, nên
các API CHỈ ĐỌC luôn thấy tham số người dùng đang sửa. Nay preview ⛔ không
ghi DB ⇒ chúng đọc bản CŨ/rỗng. Ba lỗ phải đóng:

  1. `get_variable_set_for_bom` — dialog mở lên lấy biến/kính/`saved` từ DB
     ⇒ dòng mới hoặc vừa sửa tham số thấy danh sách biến & mã kính ĐÃ LƯU.
     Sửa: tham số tuỳ chọn `params` (whitelist như `preview_bom`) — có params
     ⇒ dựng ngữ cảnh từ params, ⛔ không đọc `al_bom_vars` trong DB.
  2. `get_glass_master_price` — giá kính cạnh ô chọn tra theo `al_bom_vars`
     trong DB ⇒ hiện giá của mã cũ / "chưa có giá". Sửa cùng cách.
     ⛔ Nguồn duy nhất của bảng giá/tiền tệ vẫn là Quotation cha trong DB.
  3. `explain_bom_line` — nút "Vì sao ra số này?" đọc `al_bom_result` trong DB
     ⇒ dòng vừa preview chưa lưu bị giải thích bằng kết quả CŨ. Sửa: nhận
     `result_json` (như `get_result_display`); dòng MỚI cũng giải thích được
     từ kết quả trong tay (cổng quyền: `read` trên Quotation cha).

RÀNG BUỘC CHUNG
───────────────
  - Mọi tham số mới TUỲ CHỌN: ⛔ không truyền ⇒ hành vi y như trước.
  - ⛔ Không đổi công thức/tính toán, ⛔ không ghi DB, ⛔ không đổi hình dạng
    response.
  - Params client gửi ⛔ KHÔNG được đổi khách hàng/tiền tệ/bảng giá, ⛔ KHÔNG
    được là đường vòng bỏ kiểm quyền (mã BOM/Version client gửi vẫn bị kiểm
    `read` như `preview_bom`).
  - JSON hỏng ⇒ CÂU người-đọc-được (417), ⛔ 500, ⛔ phơi chi tiết kỹ thuật.

VÌ SAO ĐẶT Ở `standalone_tests/`
────────────────────────────────
`bench run-tests --app alumglass` os.walk toàn bộ package `alumglass/` (kể cả
`alumglass/tests/`) ⇒ file stub `frappe` nằm trong package sẽ thay
`sys.modules["frappe"]` và phá cả lượt chạy test của site. Thư mục này nằm
NGOÀI package nên bench không collect (xem docstring
`standalone_tests/test_phase_b_fbmax.py`).

CÁCH CHẠY (không cần site):
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=/home/nxc/myfrappe/apps \\
        /home/nxc/myfrappe/env/bin/python standalone_tests/test_preview_reads_dialog_state.py
"""
import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for _path in (_HERE, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_phase_b_fbmax as base  # noqa: E402  (cài stub `frappe` khi import)

api = base.api
STUB = base._STUB


# ═══════════════════════════════════════════════════════════════════
# Stub bổ sung — chỉ những gì 3 API đọc cần mà base chưa có.
# ⛔ KHÔNG sửa `test_phase_b_fbmax.py` (bộ nền dùng chung của 29 ca khác).
# ═══════════════════════════════════════════════════════════════════

class _FakeDict(dict):
    """`frappe._dict` tối thiểu — dòng preview dựng bằng `_dict` khi có params."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


def _install_api_stubs():
    STUB._dict = _FakeDict
    STUB.session = types.SimpleNamespace(user="preview-tester@example.com")
    STUB.denied = set()          # {(doctype, ptype, doc)} → từ chối

    def _has_permission(doctype, ptype="read", doc=None, user=None,
                        raise_exception=False):
        return (doctype, ptype, doc) not in STUB.denied

    def _throw(*args, **kwargs):
        """`frappe.throw(msg, ExcClass)` phải ném ĐÚNG lớp exception.

        Stub gốc ném `Exception` trơn ⇒ không phân biệt được "bị chặn quyền"
        (PermissionError) với "lỗi hạ tầng" (500) — đúng thứ các ca quyền và
        ca "JSON hỏng ⇒ 417" cần.
        """
        exc_type = kwargs.get("exc")
        for arg in args[1:]:
            if isinstance(arg, type) and issubclass(arg, BaseException):
                exc_type = arg
        message = args[0] if args else "frappe.throw"
        raise (exc_type or Exception)(message)

    STUB.has_permission = _has_permission
    STUB.throw = _throw
    STUB.log_error = lambda *a, **k: None


_install_api_stubs()


# ═══════════════════════════════════════════════════════════════════
# Fixture
# ═══════════════════════════════════════════════════════════════════

# Dòng BOM kính có mã mặc định GM-01 ⇒ 1 nhóm chọn kính (rep = GM-01).
SNAP_ITEMS = [{
    "slug": "kinh_tren", "item_code": "KINH-01", "default_glass_master": "GM-01",
    "item_selection_mode": "Manual", "category": "VL_KINH",
    "cost_bucket": "VL_KINH", "calc_pattern": "AREA",
    "width": "2000", "height": "1000", "qty": "2",
    "show_condition": "", "item_condition_formula": "", "rule_input_expr": "",
    "price_base_item": "",
}]

COST_ITEMS = [
    {"line_code": "TONG_VL", "calc_formula": "VL_KINH"},
    {"line_code": "GIA_BAN", "calc_formula": "TONG_VL"},
    {"line_code": "GIA_VAT", "calc_formula": "GIA_BAN"},
]

# DB (bản ĐÃ LƯU — CŨ): chọn GM-01, màu "Den".
DB_VARS = {
    "glass_master_map": {"GM-01": "GM-01"},
    "extra_vars": {"GLASS_COLOR": "Den"},
}
# Dialog (bản ĐANG SỬA — CHƯA lưu): chọn GM-02, màu "Trang".
DIALOG_VARS = {
    "glass_master_map": {"GM-01": "GM-02"},
    "extra_vars": {"GLASS_COLOR": "Trang"},
}


def _params(vars_dict=None, **overrides):
    """Params y như client gửi (whitelist của `preview_bom`)."""
    params = {
        "al_bom": "BOM-1",
        "al_bom_version": "ALBOMV-1",
        "al_bom_vars": json.dumps(DIALOG_VARS if vars_dict is None else vars_dict),
        "item_code": "SP-01",
        "item_name": "Sản phẩm",
        "parent": "QTN-1",
        "parenttype": "Quotation",
    }
    params.update(overrides)
    return params


def _setup():
    """Dựng fixture từ đầu cho mỗi ca (không để ca trước rò sang ca sau)."""
    base._reset_stub()
    STUB.denied = set()

    st = STUB
    st.set_doc("Quotation", "QTN-1", {
        "docstatus": 0, "currency": "VND", "company": "Công ty 1"})
    st.set_doc("Quotation Item", "QI-0001", {
        "al_bom": "BOM-1",
        "al_bom_version": "ALBOMV-1",
        "al_bom_vars": json.dumps(DB_VARS),
        "item_code": "SP-01",
        "item_name": "Sản phẩm",
        "parent": "QTN-1",
        "al_bom_result": json.dumps(DB_RESULT),
    })
    st.set_doc("AL BOM", "BOM-1", {
        "bom_code": "BOM-1", "bom_name": "BOM 1",
        "bom_set": "ALBS-1", "current_version": "ALBOMV-1"})
    st.set_doc("AL BOM Version", "ALBOMV-1", {
        "bom": "BOM-1",
        "bom_set_snapshot": json.dumps({"items": SNAP_ITEMS}),
        "cost_template_snapshot": json.dumps({"items": COST_ITEMS}),
    })
    st.set_doc("AL Bom Set", "ALBS-1", {
        "set_code": "BS-1", "set_name": "Bộ 1",
        "items": SNAP_ITEMS, "profile_system": "", "brand": "",
        "default_accessory_set": "",
    })
    st.set_doc("AL Glass Master", "GM-01", {"glass_name": "Kính trắng 8ly"})
    st.set_doc("AL Glass Master", "GM-02", {"glass_name": "Kính cường lực"})
    st.set_get_all("AL Glass Master", [
        {"name": "GM-01", "glass_name": "Kính trắng 8ly"},
        {"name": "GM-02", "glass_name": "Kính cường lực"},
    ])
    st.set_get_all("AL Material Category", [
        {"name": "VL_KINH", "requires_glass_master": 1},
    ])
    st.set_get_all("AL Slug Library", [
        {"slug": "kinh_tren", "label": "Kính trên"},
    ])
    # ── Giá kính (composite theo GLASS_COLOR) ──────────────────────
    # GM-01: 1 dòng giá "trần" (không dimension) → 100 000.
    # GM-02: 2 dòng — "Trang" 350 000, trần 200 000. Chọn Trang ⇒ 350 000;
    #        Den (DB cũ) ⇒ rơi về dòng trần ⇒ 200 000. Nhờ vậy trạng thái
    #        DB và trạng thái DIALOG cho 2 GIÁ KHÁC NHAU (phân biệt được).
    st.set_get_all("Item Price", [
        {"name": "IP-GM01", "item_code": "GM-01", "price_list": "Standard Selling",
         "price_list_rate": 100000},
        {"name": "IP-GM02-TRANG", "item_code": "GM-02",
         "price_list": "Standard Selling", "price_list_rate": 350000,
         "custom_glass_color": "Trang"},
        {"name": "IP-GM02-BASE", "item_code": "GM-02",
         "price_list": "Standard Selling", "price_list_rate": 200000},
    ])
    st.set_get_all("AL Variable Dimension Mapping", [
        {"variable_name": "GLASS_COLOR", "pricing_dimension": "PD-1",
         "material_category": "", "price_multiplier": 1, "is_active": 1},
    ])
    st.set_get_all("AL Pricing Dimension", [
        {"name": "PD-1", "custom_fieldname": "custom_glass_color"},
    ])


# Kết quả DB (CŨ — giá 111 000) và kết quả DIALOG (MỚI — giá 222 000).
# Cùng slug để `explain_bom_line` phân biệt được 2 nguồn.
def _result_payload(line_total, price_trace):
    return {
        "buckets": {"VL_KINH": line_total},
        "cost_template": {"TONG_VL": line_total},
        "lines": [{
            "slug": "kinh_tren", "item_code": "KINH-01", "item_name": "Kính trên",
            "item_selection_mode": "Manual",
            "width": 2000, "height": 1000, "qty": 2,
            "unit_qty": 2, "total_qty": 4,
            "unit_price": line_total / 4.0, "line_total": line_total,
            "cost_bucket": "VL_KINH", "unit": "m2",
            "price_trace": price_trace,
            "lookup_facts": {"code_source": "item_code", "price_match": "plain_row"},
        }],
    }


DB_RESULT = _result_payload(111000.0, "Giá theo bảng giá cũ.")
DIALOG_RESULT = _result_payload(222000.0, "Giá theo tham số người dùng đang sửa.")


def _glass_group(result, rep="GM-01"):
    groups = result.get("glass_groups") or []
    for g in groups:
        if g.get("rep") == rep:
            return g
    raise AssertionError(
        "không có glass_group rep=%r trong %r" % (rep, groups))


# ═══════════════════════════════════════════════════════════════════
# (1) `get_variable_set_for_bom` — có params ⇒ đọc TRẠNG THÁI DIALOG
# ═══════════════════════════════════════════════════════════════════

def test_variable_set_params_lay_trang_thai_dialog():
    """Có params ⇒ `saved`/`effective_code`/giá theo biến dialog, ⛔ không DB."""
    _setup()
    result = api.get_variable_set_for_bom(
        "BOM-1", "QI-0001", params=json.dumps(_params()))

    group = _glass_group(result)
    assert group["saved"] == "GM-02", group
    assert group["effective_code"] == "GM-02", group
    assert group["effective_source"] == "saved", group
    assert group["effective_name"] == "Kính cường lực", group
    # GLASS_COLOR = "Trang" (params) ⇒ khớp dòng giá 350 000, KHÔNG phải
    # 100 000 của GM-01 (DB) hay 200 000 (dòng trần GM-02).
    assert group["price"] == 350000, group
    assert group["has_price"] is True, group
    assert group["price_approx"] is False, group

    assert STUB.set_value_calls == [], "API đọc ⛔ được ghi DB"


def test_variable_set_khong_params_van_doc_db_nhu_cu():
    """⛔ Không truyền params ⇒ giữ NGUYÊN hành vi cũ (đọc `al_bom_vars` DB)."""
    _setup()
    result = api.get_variable_set_for_bom("BOM-1", "QI-0001")

    group = _glass_group(result)
    assert group["saved"] == "GM-01", group
    assert group["effective_code"] == "GM-01", group
    assert group["effective_source"] == "saved", group
    assert group["price"] == 100000, group
    assert STUB.set_value_calls == []


def test_variable_set_dong_moi_dung_params():
    """Dòng MỚI chưa có trong DB: có params ⇒ vẫn dựng đúng nhóm kính + giá.

    ⛔ Không params ⇒ hợp đồng cũ (`saved=""`, mọi nhóm "chưa có báo giá").
    """
    _setup()
    # Cổng quyền dòng mới: `read` trên Quotation cha (QTN-1) — có trong stub.
    result = api.get_variable_set_for_bom(
        "BOM-1", None, params=json.dumps(_params()))
    group = _glass_group(result)
    assert group["saved"] == "GM-02", group
    assert group["effective_code"] == "GM-02", group
    assert group["price"] == 350000, group

    # Hành vi cũ: dòng mới, ⛔ params ⇒ không có ngữ cảnh báo giá của dòng,
    # nên `saved=""` + giá là dòng Item Price THÔ (`price_approx=True`).
    legacy = api.get_variable_set_for_bom("BOM-1", None)
    legacy_group = _glass_group(legacy)
    assert legacy_group["saved"] == "", legacy_group
    assert legacy_group["effective_source"] == "bom_default", legacy_group
    assert legacy_group["price_approx"] is True, legacy_group


def test_variable_set_dong_moi_thieu_quyen_cha_bi_chan():
    """Dòng mới + params ⇒ quyền `read` trên Quotation cha vẫn phải chạy."""
    _setup()
    STUB.denied = {("Quotation", "read", "QTN-1")}
    try:
        api.get_variable_set_for_bom(
            "BOM-1", None, params=json.dumps(_params()))
    except base.FakeFrappe.PermissionError:
        pass
    else:
        raise AssertionError("thiếu quyền đọc báo giá cha mà vẫn trả dữ liệu")
    finally:
        STUB.denied = set()


def test_variable_set_thieu_quyen_bom_client_gui_bi_chan():
    """Params ⛔ KHÔNG được là đường vòng dò biến/BOM ngoài quyền."""
    _setup()
    STUB.denied = {("AL BOM", "read", "BOM-SECRET")}
    try:
        api.get_variable_set_for_bom(
            "BOM-1", "QI-0001", params=json.dumps(_params(al_bom="BOM-SECRET")))
    except base.FakeFrappe.PermissionError as exc:
        assert "AL BOM" in str(exc), str(exc)
    else:
        raise AssertionError("mã BOM ngoài quyền mà vẫn trả danh sách biến")
    finally:
        STUB.denied = set()

    STUB.denied = {("AL BOM Version", "read", "ALBOMV-SECRET")}
    try:
        api.get_variable_set_for_bom(
            "BOM-1", "QI-0001",
            params=json.dumps(_params(al_bom_version="ALBOMV-SECRET")))
    except base.FakeFrappe.PermissionError as exc:
        assert "AL BOM Version" in str(exc), str(exc)
    else:
        raise AssertionError("mã BOM Version ngoài quyền mà vẫn trả dữ liệu")
    finally:
        STUB.denied = set()


# ═══════════════════════════════════════════════════════════════════
# (2) `get_glass_master_price` — có params ⇒ giá theo biến dialog
# ═══════════════════════════════════════════════════════════════════

def test_glass_price_params_dung_bien_dialog():
    """Giá mã GM-02: params ("Trang") ⇒ 350 000; không params (DB "Den") ⇒ 200 000."""
    _setup()
    with_params = api.get_glass_master_price(
        "QI-0001", "GM-02", params=json.dumps(_params()))
    assert with_params["success"] is True, with_params
    assert with_params["price"] == 350000, with_params
    assert with_params["has_price"] is True, with_params
    assert with_params["approx"] is False, with_params
    assert with_params["price_list"] == "Standard Selling", with_params

    legacy = api.get_glass_master_price("QI-0001", "GM-02")
    assert legacy["price"] == 200000, legacy
    assert legacy["approx"] is False, legacy
    assert STUB.set_value_calls == []


def test_glass_price_params_khong_doi_bang_gia_tien_te():
    """Params lén `price_list`/`currency`/`customer` ⇒ BỊ BỎ (nguồn: DB)."""
    _setup()
    params = _params(price_list="Bảng giá lạ", currency="USD", customer="KH-LA")
    result = api.get_glass_master_price(
        "QI-0001", "GM-02", params=json.dumps(params))
    assert result["price_list"] == "Standard Selling", result
    assert result["price"] == 350000, result

    parsed = api._parse_preview_params(json.dumps(params))
    for banned in ("price_list", "currency", "customer"):
        assert banned not in parsed, "%r lọt qua whitelist: %r" % (banned, parsed)


def test_glass_price_thieu_quyen_bom_client_gui_bi_chan():
    _setup()
    STUB.denied = {("AL BOM", "read", "BOM-SECRET")}
    try:
        api.get_glass_master_price(
            "QI-0001", "GM-02", params=json.dumps(_params(al_bom="BOM-SECRET")))
    except base.FakeFrappe.PermissionError as exc:
        assert "AL BOM" in str(exc), str(exc)
    else:
        raise AssertionError("mã BOM ngoài quyền mà vẫn trả giá kính")
    finally:
        STUB.denied = set()


# ═══════════════════════════════════════════════════════════════════
# (3) `explain_bom_line` — `result_json` thay cho bản DB cũ
# ═══════════════════════════════════════════════════════════════════

def test_explain_result_json_dung_ket_qua_vua_tinh():
    """Có `result_json` ⇒ giải thích ĐÚNG kết quả đó (khác bản DB)."""
    _setup()
    from_db = api.explain_bom_line("QI-0001", "kinh_tren")
    assert from_db["success"] is True, from_db
    assert from_db["line_total"] == 111000.0, from_db

    from_arg = api.explain_bom_line(
        "QI-0001", "kinh_tren", result_json=json.dumps(DIALOG_RESULT))
    assert from_arg["success"] is True, from_arg
    assert from_arg["line_total"] == 222000.0, from_arg
    # Chuỗi giải thích lấy từ trace của KẾT QUẢ MỚI (⛔ không phải bản DB).
    price_step = [s for s in from_arg["steps"] if s["key"] == "price"][0]
    assert price_step["detail"] == DIALOG_RESULT["lines"][0]["price_trace"], price_step
    # Hình dạng response không đổi.
    assert set(from_arg) >= {"success", "slug", "label", "item_code",
                             "line_total", "steps", "missing"}
    assert STUB.set_value_calls == []


def test_explain_dong_moi_khong_co_ten_van_giai_thich_duoc():
    """Dòng MỚI (`new-…`/rỗng) + `result_json` + `parent` ⇒ giải thích được."""
    _setup()
    result = api.explain_bom_line(
        "", "kinh_tren", result_json=json.dumps(DIALOG_RESULT),
        parent="QTN-1")
    assert result["success"] is True, result
    assert result["line_total"] == 222000.0, result

    # Tên dòng `new-…` cũng coi là dòng mới.
    result2 = api.explain_bom_line(
        "new-quotation-item-3", "kinh_tren",
        result_json=json.dumps(DIALOG_RESULT), parent="QTN-1")
    assert result2["success"] is True, result2

    # Dòng MỚI mà KHÔNG có kết quả trong tay ⇒ câu trạng thái + lối xử lý,
    # ⛔ không rơi xuống đọc DB rồi báo "không tìm thấy dòng".
    empty = api.explain_bom_line("", "kinh_tren", parent="QTN-1")
    assert empty["success"] is False, empty
    assert "Preview tính giá" in empty["message"], empty


def test_explain_dong_moi_thieu_quyen_cha_bi_chan():
    _setup()
    STUB.denied = {("Quotation", "read", "QTN-1")}
    try:
        api.explain_bom_line(
            "", "kinh_tren", result_json=json.dumps(DIALOG_RESULT),
            parent="QTN-1")
    except base.FakeFrappe.PermissionError:
        pass
    else:
        raise AssertionError("thiếu quyền đọc báo giá cha mà vẫn giải thích")
    finally:
        STUB.denied = set()


def test_explain_dong_cu_van_kiem_quyen_tren_cha_that():
    """Dòng ĐÃ LƯU ⇒ `parent` client gửi ⛔ được dùng thay cổng quyền thật."""
    _setup()
    calls = []
    original = api._require_quotation_item_permission

    def _record(name, ptype="read"):
        calls.append((name, ptype))
        return original(name, ptype=ptype)

    api._require_quotation_item_permission = _record
    try:
        api.explain_bom_line(
            "QI-0001", "kinh_tren", result_json=json.dumps(DIALOG_RESULT),
            parent="QTN-KHAC")
    finally:
        api._require_quotation_item_permission = original
    assert calls == [("QI-0001", "read")], calls


# ═══════════════════════════════════════════════════════════════════
# (d) JSON hỏng ⇒ câu người-đọc-được (417), ⛔ 500 / chi tiết kỹ thuật
# ═══════════════════════════════════════════════════════════════════

def _assert_readable(exc, expected_phrase):
    message = str(exc)
    assert expected_phrase in message, message
    for technical in ("Traceback", "json.decoder", "JSONDecodeError",
                      "Expecting value", "Expecting property name",
                      "line 1 column"):
        assert technical not in message, "lộ chi tiết kỹ thuật %r: %s" % (
            technical, message)


def test_result_json_hong_tra_cau_nguoi_doc_duoc():
    _setup()
    for broken in ("{khong-phai-json", '{"lines": '):
        try:
            api.explain_bom_line(
                "QI-0001", "kinh_tren", result_json=broken)
        except base.FakeFrappe.ValidationError as exc:
            _assert_readable(exc, "bị hỏng")
        else:
            raise AssertionError("result_json hỏng mà không báo lỗi")

    # Dòng MỚI + JSON hỏng cũng phải là câu người-đọc-được.
    try:
        api.explain_bom_line(
            "", "kinh_tren", result_json="{khong-phai-json", parent="QTN-1")
    except base.FakeFrappe.ValidationError as exc:
        _assert_readable(exc, "bị hỏng")
    else:
        raise AssertionError("dòng mới + result_json hỏng mà không báo lỗi")


def test_params_hong_tra_cau_nguoi_doc_duoc():
    _setup()
    try:
        api.get_variable_set_for_bom("BOM-1", "QI-0001", params="{khong-phai-json")
    except base.FakeFrappe.ValidationError as exc:
        _assert_readable(exc, "Tham số tính giá bị hỏng")
    else:
        raise AssertionError("params (variable set) hỏng mà không báo lỗi")

    try:
        api.get_glass_master_price("QI-0001", "GM-02", params="{khong-phai-json")
    except base.FakeFrappe.ValidationError as exc:
        _assert_readable(exc, "Tham số tính giá bị hỏng")
    else:
        raise AssertionError("params (giá kính) hỏng mà không báo lỗi")


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
