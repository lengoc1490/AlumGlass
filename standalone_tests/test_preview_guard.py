# -*- coding: utf-8 -*-
"""PHASE 2 (nửa MÁY CHỦ) "Lưu khi tham số lệch ⇒ TỰ TÍNH LẠI dòng lệch".

BỐI CẢNH (Owner chốt 2026-11-21 — design `docs/design/preview-khong-ghi-db.md`
§9.1 câu 3, ghi chú triển khai §9.2/§9.5)
─────────────────────────────────────────────────────────────────────────────
Phase 1 đã bỏ mọi đường ghi DB khỏi preview: kết quả BOM nằm trên FORM, DB chỉ
đổi khi bấm Lưu. Vì vậy lúc Lưu phải trả lời được một câu: *"con số đang lưu có
được tính từ đúng tham số đang lưu không?"* — bằng `calc_meta.params_hash`
(SHA-256 của `al_bom` / `al_bom_version` / `item_code` / `al_bom_vars`).

Bộ test này kiểm handler `alumglass.api.preview_guard.validate_preview_freshness`
(gắn vào doc event `Quotation.validate` của `hooks.py`):

  (a) hash KHỚP ⇒ 0 lượt engine, doc KHÔNG đổi một byte;
  (b) hash LỆCH (hoặc thiếu `al_bom_result`) ⇒ engine 1 lượt, dòng nhận
      `al_bom_result`/`al_gia_ban`/`al_gia_vat`/`rate` mới + hash khớp lại;
      ⛔ 0 lần `db.set_value`, ⛔ 0 lần `commit`;
  (c) engine ném lỗi ⇒ `ValidationError` có số dòng + mã hàng + câu hướng dẫn,
      ⛔ không lộ traceback/lỗi kỹ thuật;
  (d) dòng KHÔNG có `al_bom` ⇒ bỏ qua (⛔ tự đặt giá);
  (e) `docstatus = 1` ⇒ không làm gì, kể cả khi hash lệch;
  (f) 2 dòng, 1 khớp + 1 lệch ⇒ chỉ tính lại ĐÚNG 1 dòng;
  (g) hash chỉ tính từ 4 field: đổi `qty`/`rate` KHÔNG phải lệch; đổi
      `al_bom_vars` LÀ lệch;
  (h) tổng tiền báo giá được tính lại ĐÚNG 1 lần sau khi `rate` đổi (ERPNext
      tính tổng TRƯỚC doc event validate ⇒ không tính lại thì lưu tổng CŨ).

VÌ SAO ĐẶT Ở `standalone_tests/`
──────────────────────────────────
`bench run-tests --app alumglass` os.walk toàn bộ package `alumglass/` ⇒ tệp
stub `frappe` nằm trong package sẽ thay `sys.modules["frappe"]` và phá lượt chạy
test của site. Thư mục này nằm NGOÀI package (xem docstring
`standalone_tests/test_phase_b_fbmax.py`).

MÁY NÀY KHÔNG CÓ SITE CÀI ALUMGLASS ⇒ chạy trên stub `frappe` của
`test_phase_b_fbmax.py`. Vì vậy các ca dưới đây chứng minh ĐƯỜNG ĐI (gọi/không
gọi engine, ghi/không ghi DB, thông điệp lỗi), ⛔ KHÔNG chứng minh số vàng
2C/4C trên production (xem §10 của design).

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_preview_guard.py
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

STUB = base._STUB

from alumglass.engine import bom_orchestrator as engine_mod  # noqa: E402
from alumglass.engine.bom_orchestrator import compute_params_hash  # noqa: E402
from alumglass.api import preview_guard as guard  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# Stub bổ sung — chỉ những gì handler cần mà base chưa đủ.
# ⛔ KHÔNG sửa `test_phase_b_fbmax.py`: bộ đó là nền dùng chung.
# ═══════════════════════════════════════════════════════════════════

def _install_guard_stubs():
    """`frappe.throw(msg, ExcClass)` phải ném ĐÚNG lớp exception.

    Stub gốc ném `Exception` trơn ⇒ không phân biệt được "báo lỗi người-đọc-
    được" (ValidationError = 417) với "lỗi hạ tầng". Ca (c) cần đúng lớp này.
    """
    def _throw(*args, **kwargs):
        exc_type = kwargs.get("exc")
        for arg in args[1:]:
            if isinstance(arg, type) and issubclass(arg, BaseException):
                exc_type = arg
        message = args[0] if args else "frappe.throw"
        raise (exc_type or Exception)(message)

    STUB.throw = _throw

    class _FakeDict(dict):
        """`frappe._dict` tối thiểu — engine dựng `_qi_doc` cho đường preview."""

        def __getattr__(self, key):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)

    STUB._dict = _FakeDict


_install_guard_stubs()


# ── Dòng Quotation Item tối thiểu: `get` + `set` như Document thật ──
class _Row(object):
    def __init__(self, **data):
        self._data = dict(data)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class _Doc(object):
    """Báo giá tối thiểu: `get("items")`, `docstatus`, đếm lượt tính tổng."""

    def __init__(self, rows, name="QTN-1", docstatus=0):
        self._data = {"name": name, "docstatus": docstatus, "items": rows}
        self.totals_calls = 0

    def get(self, key, default=None):
        return self._data.get(key, default)

    def calculate_taxes_and_totals(self):
        self.totals_calls += 1


class _EngineSpy(object):
    """Đếm lượt gọi engine; tuỳ chọn ném lỗi ở `run()`."""

    def __init__(self, fail_with=None):
        self.calls = []
        self.fail_with = fail_with
        self._original = None

    def __enter__(self):
        self._original = engine_mod.BomOrchestrator
        spy = self

        class _Wrapped(object):
            def __init__(self, *args, **kwargs):
                spy.calls.append({"args": args, "kwargs": kwargs})
                self._impl = (None if spy.fail_with
                              else spy._original(*args, **kwargs))

            def run(self):
                if spy.fail_with:
                    raise spy.fail_with
                return self._impl.run()

        engine_mod.BomOrchestrator = _Wrapped
        return self

    def __exit__(self, *exc_info):
        engine_mod.BomOrchestrator = self._original
        return False


# ═══════════════════════════════════════════════════════════════════
# Fixture — dùng nguyên bộ dữ liệu của base (BOM-1 / ALBOMV-1 / giá)
# ═══════════════════════════════════════════════════════════════════
_VARS = json.dumps({"extra_vars": dict(base.EXTRA)})

# Engine ra các số này với fixture của base (xem `EXPECTED_BUCKETS`):
# GIA_THANH = 2 400 000; GIA_BAN = 2.88M; GIA_VAT = 288 000.
_EXPECTED_GIA_BAN = 2880000.0
_EXPECTED_GIA_VAT = 288000.0


def _setup():
    """Dựng lại fixture đầy đủ (docs + master data) của base."""
    base._prepare_orchestrator(base.EXTRA)


def _hash_for(row, version):
    """Hash với version TƯỜNG MINH — test ⛔ được gọi vào helper của guard.

    Cố ý tính độc lập: nếu test lấy kỳ vọng từ `preview_guard._effective_version`
    thì đột biến hàm đó sẽ làm kỳ vọng "tự sửa theo" và đối chứng âm vô cảm.
    """
    return compute_params_hash(
        row.get("al_bom"), version,
        row.get("item_code"), row.get("al_bom_vars"),
    )


def _hash_of(row):
    return _hash_for(row, row.get("al_bom_version") or "")


def _stored_result(row, hash_value=None, as_dict=False):
    """`al_bom_result` "đã lưu" với hash khớp tham số hiện tại của dòng."""
    payload = {
        "buckets": {"VL_KINH": 1},
        "cost_template": {},
        "lines": [],
        "errors": {},
        "calc_meta": {
            "params_hash": hash_value if hash_value is not None else _hash_of(row),
            "computed_at": "2026-11-21T00:00:00Z",
            "preview": True,
            "engine": "alumglass.bom_orchestrator",
        },
    }
    return payload if as_dict else json.dumps(payload)


def _row(name="QI-0001", **overrides):
    data = {
        "name": name,
        "idx": 1,
        "parent": "QTN-1",
        "parenttype": "Quotation",
        "doctype": "Quotation Item",
        "al_bom": "BOM-1",
        "al_bom_version": "ALBOMV-1",
        "al_bom_vars": _VARS,
        "item_code": "SP-01",
        "item_name": "Khung nhôm 55",
        "qty": 1,
        "uom": "Cái",
        "rate": 0,
        "al_gia_ban": 0,
        "al_gia_vat": 0,
        "al_bom_result": "",
        "al_calc_status": "",
        "al_calc_error": "",
    }
    data.update(overrides)
    return _Row(**data)


def _assert_no_db_write():
    assert STUB.set_value_calls == [], (
        "handler ⛔ được ghi DB qua db.set_value: %s" % (STUB.set_value_calls,))
    assert STUB.commit_count == 0, (
        "handler ⛔ được commit, nhưng đã commit %d lần" % STUB.commit_count)


def _retarget_bom_version(new_version="ALBOMV-2"):
    """Đăng ký version mới (cùng snapshot) và cho `AL BOM` trỏ sang nó — mô
    phỏng "BOM xuất bản version mới" trong lúc dòng báo giá để trống version."""
    source = STUB.docs[("AL BOM Version", "ALBOMV-1")]._data
    data = {k: v for k, v in source.items() if k != "name"}
    STUB.set_doc("AL BOM Version", new_version, data)
    STUB.docs[("AL BOM", "BOM-1")]._data["current_version"] = new_version


# ═══════════════════════════════════════════════════════════════════
# (a) Hash khớp ⇒ 0 lượt engine, doc không đổi
# ═══════════════════════════════════════════════════════════════════

def test_a_hash_khop_khong_goi_engine_khong_doi_doc():
    _setup()
    row = _row(al_bom_result=_stored_result(_row()))
    doc = _Doc([row])
    before = dict(row._data)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert spy.calls == [], (
        "hash khớp mà vẫn chạy engine: %s" % (spy.calls,))
    assert row._data == before, "dòng bị sửa dù hash khớp: %s" % (row._data,)
    assert doc.totals_calls == 0, "hash khớp ⇒ ⛔ tính lại tổng tiền"
    _assert_no_db_write()


def test_a_al_bom_result_dang_object_van_khop():
    """Form có thể gửi `al_bom_result` là OBJECT (không phải chuỗi) — vẫn khớp."""
    _setup()
    row = _row()
    row.set("al_bom_result", _stored_result(row, as_dict=True))
    before = dict(row._data)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))

    assert spy.calls == [], "object JSON cùng hash mà vẫn tính lại"
    assert row._data == before
    _assert_no_db_write()


def test_a_bao_gia_khong_co_dong_nao():
    _setup()
    doc = _Doc([])
    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)
    assert spy.calls == []
    assert doc.totals_calls == 0
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (b) Hash lệch / thiếu kết quả ⇒ tính lại đúng 1 dòng, ghi vào DOC
# ═══════════════════════════════════════════════════════════════════

def test_b_thieu_ket_qua_thi_tinh_lai_va_gan_vao_doc():
    _setup()
    row = _row()  # al_bom_result = "" ⇒ dòng "lệch"
    doc = _Doc([row])
    docs_before = dict(STUB.docs)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1, "phải tính lại ĐÚNG 1 lần: %s" % (spy.calls,)
    call = spy.calls[0]
    assert call["kwargs"].get("persist") is False, (
        "tính lại lúc Lưu PHẢI chạy persist=False (⛔ ghi DB ngầm)")
    assert call["kwargs"].get("quotation_item_name") == "QI-0001", call["kwargs"]
    params = call["kwargs"].get("params") or {}
    assert params.get("al_bom") == "BOM-1"
    assert params.get("al_bom_vars") == _VARS
    assert params.get("parent") == "QTN-1"

    payload = json.loads(row.get("al_bom_result"))
    for key in ("buckets", "cost_template", "lines", "errors", "calc_meta"):
        assert key in payload, "al_bom_result thiếu khoá %r: %s" % (key, payload)
    assert payload["calc_meta"]["params_hash"] == _hash_of(row), (
        "hash trong calc_meta phải khớp tham số ĐANG LƯU")
    assert payload["calc_meta"]["params_hash"] == _hash_of(_row())
    assert payload["calc_meta"]["preview"] is False
    assert payload["calc_meta"]["recomputed_on_save"] is True
    assert payload["buckets"].get("VL_KINH") == 1200000.0, payload["buckets"]

    assert row.get("al_gia_ban") == _EXPECTED_GIA_BAN, row._data
    assert row.get("al_gia_vat") == _EXPECTED_GIA_VAT, row._data
    assert row.get("rate") == _EXPECTED_GIA_BAN, "rate = giá TRƯỚC VAT"
    assert row.get("al_calc_status") == "Success"
    assert row.get("al_calc_error") == ""
    assert doc.totals_calls == 1, "rate đổi ⇒ phải tính lại tổng tiền ĐÚNG 1 lần"

    _assert_no_db_write()
    assert set(STUB.docs) == set(docs_before), "engine preview ⛔ tạo/xoá doc nào"


def test_b_hash_lech_thi_tinh_lai():
    _setup()
    row = _row()
    row.set("al_bom_result", _stored_result(row, hash_value="hash-cu-sai"))
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1
    payload = json.loads(row.get("al_bom_result"))
    assert payload["calc_meta"]["params_hash"] == _hash_of(row)
    assert payload["calc_meta"]["params_hash"] != "hash-cu-sai"
    _assert_no_db_write()


def test_b_json_hong_coi_nhu_chua_co_ket_qua():
    _setup()
    row = _row(al_bom_result="{khong-phai-json")
    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))
    assert len(spy.calls) == 1, "JSON hỏng ⇒ phải tính lại, ⛔ lưu giá cũ im lặng"
    assert json.loads(row.get("al_bom_result"))["calc_meta"]["params_hash"] == _hash_of(row)


def test_b_dong_moi_chua_luu_khong_ep_luu_dong():
    """Dòng `new-…` ⇒ ⛔ truyền tên cho engine (⛔ `frappe.get_doc` dòng chưa có)."""
    _setup()
    row = _row(name="new-quotation-item-7")
    row.set("__islocal", 1)
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1
    assert spy.calls[0]["kwargs"].get("quotation_item_name") is None, (
        "dòng chưa lưu ⛔ được truyền tên: %s" % (spy.calls[0]["kwargs"],))
    assert row.get("al_gia_ban") == _EXPECTED_GIA_BAN
    _assert_no_db_write()


def test_b_lan_hai_khong_tinh_lai_lai():
    """Validate chạy 2 lượt trong 1 request (insert sau save) ⇒ lượt 2 miễn phí."""
    _setup()
    row = _row()
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)
        assert len(spy.calls) == 1
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1, (
        "lượt validate thứ 2 phải thấy hash đã khớp (⛔ tính lại lần nữa): %s"
        % (spy.calls,))
    assert doc.totals_calls == 1, "lượt 2 không đổi giá ⇒ ⛔ tính lại tổng"
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (c) Engine ném lỗi ⇒ ValidationError người-đọc-được
# ═══════════════════════════════════════════════════════════════════

def test_c_engine_loi_bao_dong_va_ma_hang_khong_lo_traceback():
    _setup()
    row = _row(al_bom_result="")  # dòng lệch ⇒ có đi vào engine
    doc = _Doc([row])
    before = dict(row._data)

    with _EngineSpy(fail_with=RuntimeError("key 'chi_tiet' lạc trong stack")):
        try:
            guard.validate_preview_freshness(doc)
        except base.FakeFrappe.ValidationError as exc:
            message = str(exc)
        else:
            raise AssertionError("engine lỗi mà vẫn lưu báo giá với giá cũ")

    assert "Dòng 1" in message, message
    assert "SP-01" in message, "câu lỗi phải nêu mã hàng: %s" % message
    assert "Khung nhôm 55" in message, "câu lỗi nên nêu tên hàng: %s" % message
    assert "Preview tính giá" in message and "lưu lại" in message, message
    lowered = message.lower()
    for leak in ("traceback", "runtimeerror", "key 'chi_tiet'", "stack"):
        assert leak not in lowered, "⛔ phơi lỗi kỹ thuật %r: %s" % (leak, message)
    assert row._data == before, "lỗi ⇒ ⛔ được ghi dở kết quả vào dòng"
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (d) Dòng không có al_bom ⇒ bỏ qua
# ═══════════════════════════════════════════════════════════════════

def test_d_dong_khong_co_bom_bi_bo_qua():
    _setup()
    row = _row(al_bom="", al_bom_version="", al_bom_result="")
    doc = _Doc([row])
    before = dict(row._data)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert spy.calls == [], "dòng không chọn BOM mà vẫn đi tính giá"
    assert row._data == before, "⛔ tự đặt giá cho dòng không chọn BOM"
    assert doc.totals_calls == 0
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (e) docstatus = 1 ⇒ không làm gì (submit có luồng riêng)
# ═══════════════════════════════════════════════════════════════════

def test_e_da_submit_thi_khong_lam_gi():
    _setup()
    row = _row(al_bom_result="")  # hash lệch
    doc = _Doc([row], docstatus=1)
    before = dict(row._data)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert spy.calls == [], "báo giá đã submit mà vẫn tính lại giá"
    assert row._data == before
    assert doc.totals_calls == 0
    _assert_no_db_write()


def test_e_da_huy_thi_khong_lam_gi():
    _setup()
    row = _row(al_bom_result="")
    doc = _Doc([row], docstatus=2)
    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)
    assert spy.calls == []
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (f) 2 dòng: 1 khớp + 1 lệch ⇒ chỉ tính lại 1 dòng
# ═══════════════════════════════════════════════════════════════════

def test_f_chi_tinh_lai_dong_lech():
    _setup()
    matched = _row(name="QI-0001")
    matched.set("al_bom_result", _stored_result(matched))
    stale = _row(name="new-quotation-item-2", idx=2, al_bom_result="")
    doc = _Doc([matched, stale])
    matched_before = dict(matched._data)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1, "chỉ được tính lại ĐÚNG dòng lệch: %s" % (spy.calls,)
    assert spy.calls[0]["kwargs"].get("quotation_item_name") is None
    assert matched._data == matched_before, "dòng khớp ⛔ được đụng tới"
    assert stale.get("al_gia_ban") == _EXPECTED_GIA_BAN
    assert doc.totals_calls == 1, "1 lô ⇒ tính tổng ĐÚNG 1 lần"
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (g) Hash chỉ tính từ 4 field: qty/rate KHÔNG, al_bom_vars CÓ
# ═══════════════════════════════════════════════════════════════════

def test_g_doi_qty_hay_rate_khong_phai_lech():
    _setup()
    row = _row(qty=5, rate=123456)
    row.set("al_bom_result", _stored_result(row))
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert spy.calls == [], (
        "đổi số lượng/đơn giá KHÔNG làm kết quả BOM cũ sai ⇒ ⛔ tính lại")
    assert doc.totals_calls == 0
    _assert_no_db_write()


def test_g_doi_bien_bom_la_lech():
    _setup()
    row = _row()
    row.set("al_bom_result", _stored_result(row))
    row.set("al_bom_vars",
            json.dumps({"extra_vars": dict(base.EXTRA, VAT_RATE=0.5)}))

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))

    assert len(spy.calls) == 1, "đổi biến BOM ⇒ tham số lệch ⇒ phải tính lại"
    payload = json.loads(row.get("al_bom_result"))
    assert payload["calc_meta"]["params_hash"] == _hash_of(row)
    _assert_no_db_write()


def test_g_doi_bom_hoac_version_la_lech():
    _setup()
    for field, value in (("al_bom", "BOM-KHAC"), ("al_bom_version", "ALBOMV-KHAC")):
        _setup()
        row = _row()
        row.set("al_bom_result", _stored_result(row))
        row.set(field, value)
        with _EngineSpy() as spy:
            try:
                guard.validate_preview_freshness(_Doc([row]))
            except base.FakeFrappe.ValidationError:
                # Mã BOM/version lạ không có trong fixture ⇒ engine ném; điều
                # cần chứng minh là handler ĐÃ coi dòng này là lệch.
                assert len(spy.calls) == 1, field
                continue
        assert len(spy.calls) == 1, "đổi %s phải coi là lệch" % field


# ═══════════════════════════════════════════════════════════════════
# (h) Version hiệu lực: dòng để trống `al_bom_version`
# ═══════════════════════════════════════════════════════════════════

def test_h_version_hieu_luc_doi_thi_tinh_lai_va_ghim():
    """BOM đổi `current_version` ⇒ dòng trống version phải bị coi là LỆCH.

    Đây là lỗ đúng/sai: hash chỉ lấy `al_bom_version` của dòng (rỗng) thì BOM
    lên version mới mà guard vẫn thấy "khớp" ⇒ giá cũ nằm lại im lặng.
    """
    _setup()
    row = _row(al_bom_version="")
    # Kết quả đã lưu ứng với version hiệu lực LÚC ĐÓ (ALBOMV-1).
    row.set("al_bom_result", _stored_result(row, hash_value=_hash_for(row, "ALBOMV-1")))
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)
    assert spy.calls == [], (
        "hash phải tính version HIỆU LỰC (ALBOMV-1) ⇒ dòng phải được coi là "
        "khớp, nhưng engine đã chạy: %s" % (spy.calls,))
    assert row.get("al_bom_version") == "", "khớp ⇒ ⛔ được ghim gì vào dòng"
    _assert_no_db_write()

    # BOM xuất bản version mới — dòng vẫn để trống version.
    _retarget_bom_version("ALBOMV-2")

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))
    assert len(spy.calls) == 1, (
        "BOM đổi version hiện hành mà guard KHÔNG tính lại ⇒ giá cũ nằm lại")
    assert row.get("al_bom_version") == "ALBOMV-2", (
        "tính lại xong phải GHIM version hiệu lực xuống dòng: %r"
        % (row.get("al_bom_version"),))
    payload = json.loads(row.get("al_bom_result"))
    assert payload["calc_meta"]["params_hash"] == _hash_for(row, "ALBOMV-2")
    assert payload["calc_meta"]["params_hash"] != _hash_for(row, "ALBOMV-1")
    assert row.get("al_gia_ban") == _EXPECTED_GIA_BAN
    _assert_no_db_write()


def test_i_sau_khi_ghim_luu_lan_hai_khong_tinh_lai():
    """Ghim xong ⇒ Lưu lần 2 liên tiếp (không đổi gì) phải 0 lượt engine.

    Bắt đúng kiểu cài sai: ghim version nhưng lại lưu hash tính từ version
    RỖNG ⇒ mỗi lần Lưu đều lệch ⇒ tính lại vô hạn.
    """
    _setup()
    row = _row(al_bom_version="")
    row.set("al_bom_result", _stored_result(row, hash_value=_hash_for(row, "ALBOMV-1")))
    _retarget_bom_version("ALBOMV-2")

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))
    assert len(spy.calls) == 1, "lượt đầu phải tính lại"
    assert row.get("al_bom_version") == "ALBOMV-2"

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))
    assert spy.calls == [], (
        "Lưu lần 2 sau khi ghim version phải KHỚP (⛔ tính lại vô hạn): %s"
        % (spy.calls,))

    # Lần 3: BOM xuất bản tiếp version mới. Dòng đã GHIM V2 ⇒ giá neo ở V2,
    # ⛔ trôi theo `current_version` (đúng nghĩa "version pinning" của B0).
    _retarget_bom_version("ALBOMV-3")
    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))
    assert spy.calls == [], (
        "dòng đã ghim ALBOMV-2 ⇒ đổi current_version KHÔNG được kéo giá đi: %s"
        % (spy.calls,))
    assert row.get("al_bom_version") == "ALBOMV-2"


# ═══════════════════════════════════════════════════════════════════
# (j) patch / install / migrate ⇒ bỏ qua
# ═══════════════════════════════════════════════════════════════════

def test_j_patch_install_migrate_bo_qua():
    for flag in ("in_patch", "in_install", "in_migrate"):
        _setup()
        row = _row(al_bom_result="")  # dòng lệch
        doc = _Doc([row])
        before = dict(row._data)
        STUB.flags = types.SimpleNamespace(**{flag: True})
        try:
            with _EngineSpy() as spy:
                guard.validate_preview_freshness(doc)
        finally:
            STUB.flags = types.SimpleNamespace()

        assert spy.calls == [], (
            "%s=True (thao tác hệ thống) mà vẫn tính lại giá: %s"
            % (flag, spy.calls))
        assert row._data == before, "%s ⇒ ⛔ đụng vào dòng" % flag
        assert doc.totals_calls == 0
        _assert_no_db_write()


def test_j_khong_phai_thao_tac_he_thong_thi_van_chay():
    """Đối chứng dương: flags RỖNG ⇒ guard vẫn làm việc (ca (j) không xanh giả)."""
    _setup()
    row = _row(al_bom_result="")
    STUB.flags = types.SimpleNamespace()
    try:
        with _EngineSpy() as spy:
            guard.validate_preview_freshness(_Doc([row]))
    finally:
        STUB.flags = types.SimpleNamespace()
    assert len(spy.calls) == 1, "flags rỗng mà guard bỏ qua ⇒ (j) vô cảm"
    _assert_no_db_write()


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
