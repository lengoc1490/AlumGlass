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
import alumglass.api as api_mod  # noqa: E402


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

    # `preview_bom` kiểm quyền trên Quotation cha (`_require_quotation_item_
    # permission` / `_require_doc_read_permission`). Stub base không có hàm
    # này; ca (o-e) cần gọi API thật nên phải cung cấp.
    STUB.has_permission = (
        lambda doctype=None, ptype="read", doc=None, **kwargs: True)

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


class _RecordRow(_Row):
    """Dòng Quotation Item có thêm `precision(field)` như Document thật."""

    def precision(self, fieldname):
        return 2


class _Doc(object):
    """Báo giá tối thiểu: `get("items")`, `docstatus`, đếm lượt tính tổng.

    `reprice_from_list=True` mô phỏng ERPNext GHI ĐÈ `rate` bằng
    `price_list_rate` trong `calculate_taxes_and_totals` — đúng lỗi cần chặn.
    """

    def __init__(self, rows, name="QTN-1", docstatus=0,
                 reprice_from_list=False, in_words_raises=False, **fields):
        self._data = {"name": name, "docstatus": docstatus, "items": rows}
        # Field báo giá khác (currency / selling_price_list / company…) —
        # dùng cho ca (o): bối cảnh giá phải lấy từ CHÍNH doc đang lưu.
        self._data.update(fields)
        self.totals_calls = 0
        self.in_words_calls = []
        self.grand_total = 0
        self.reprice_from_list = reprice_from_list
        self.in_words_raises = in_words_raises

    def get(self, key, default=None):
        return self._data.get(key, default)

    def calculate_taxes_and_totals(self):
        self.totals_calls += 1
        if self.reprice_from_list:
            for row in self._data["items"]:
                row.set("rate", row.get("price_list_rate"))
        self.grand_total = sum(
            float(row.get("rate") or 0) * float(row.get("qty") or 1)
            for row in self._data["items"])

    def set_total_in_words(self):
        """ERPNext set `in_words` bằng tổng HIỆN TẠI của doc."""
        if self.in_words_raises:
            raise RuntimeError("bản ERPNext này không có hàm")
        self.in_words_calls.append(self.grand_total)


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
# (k) Số tiền bằng chữ phải khớp tổng MỚI (reviewer độc lập 2026-11-23)
# ═══════════════════════════════════════════════════════════════════

def _row_doc(**overrides):
    """Dòng có `precision(field)` như Document thật (để kiểm so sánh rate)."""
    return _RecordRow(**_row(**overrides)._data)


def test_k_tinh_lai_rate_cap_nhat_in_words():
    """ERPNext set `in_words` TRƯỚC doc event ⇒ guard phải gọi lại sau khi đổi rate."""
    _setup()
    row = _row_doc(al_bom_result="")
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1, spy.calls
    assert row.get("rate") == _EXPECTED_GIA_BAN, row._data
    assert doc.in_words_calls == [doc.grand_total], (
        "phải gọi set_total_in_words SAU khi tính lại tổng: %s vs %s"
        % (doc.in_words_calls, doc.grand_total))
    assert doc.grand_total == _EXPECTED_GIA_BAN, doc.grand_total
    _assert_no_db_write()


def test_k_set_total_in_words_loi_khong_lam_hong_luot_luu():
    """Bản ERPNext không có/lỗi `set_total_in_words` ⇒ ⛔ làm hỏng lượt Lưu."""
    _setup()
    row = _row_doc(al_bom_result="")
    doc = _Doc([row], in_words_raises=True)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)  # ⛔ được ném

    assert len(spy.calls) == 1
    assert row.get("rate") == _EXPECTED_GIA_BAN
    assert doc.in_words_calls == [], "hàm lỗi ⇒ ⛔ có bản ghi 'đã cập nhật'"
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (l) `rate` bị ERPNext ghi đè bằng giá bảng ⇒ chặn, ⛔ lưu im lặng
# ═══════════════════════════════════════════════════════════════════

def test_l_rate_bi_thay_bang_gia_bang_thi_chan():
    """Giá tính = 0, `price_list_rate` = 100 ⇒ `calculate_taxes_and_totals`
    ghi đè `rate` ⇒ phải báo câu người-đọc-được kèm số dòng + mã hàng."""
    _setup()
    row = _row_doc(al_bom_result="", price_list_rate=100)
    doc = _Doc([row], reprice_from_list=True)

    try:
        with _EngineSpy() as spy:
            guard.validate_preview_freshness(doc)
    except base.FakeFrappe.ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "rate bị thay bằng giá bảng mà vẫn lưu báo giá (rate=%r, giá bán=%r)"
            % (row.get("rate"), row.get("al_gia_ban")))

    assert "giá bán vừa tính bị hệ thống thay bằng giá bảng" in message, message
    assert "Dòng 1" in message, message
    assert "Khung nhôm 55" in message, "câu lỗi phải nêu tên hàng: %s" % message
    for leak in ("traceback", "attributeerror", "runtimeerror"):
        assert leak not in message.lower(), "⛔ phơi lỗi kỹ thuật: %s" % message
    assert len(spy.calls) == 1, "vẫn phải tính đúng 1 lượt rồi mới kiểm"
    _assert_no_db_write()


def test_l_rate_khop_gia_ban_thi_khong_chan():
    """Đối chứng dương: `rate` đúng bằng `al_gia_ban` ⇒ đi qua bình thường."""
    _setup()
    row = _row_doc(al_bom_result="")
    doc = _Doc([row])

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1
    assert row.get("rate") == row.get("al_gia_ban") == _EXPECTED_GIA_BAN
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (m) Ngưỡng số dòng — ⛔ để Lưu 50 dòng thành 50 lượt engine đồng bộ
# ═══════════════════════════════════════════════════════════════════

def _set_async_threshold(value):
    """Ghi ngưỡng vào Formula Global Variable (đúng nguồn `_get_async_threshold`)."""
    STUB.set_doc("Formula Global Variable", "ASYNC_BOM_THRESHOLD",
                 {"constant_value": str(value)})


def test_m_so_dong_lech_vuot_nguong_thi_chan_khong_goi_engine():
    _setup()
    _set_async_threshold(2)
    rows = [_row(name="new-quotation-item-%d" % i, idx=i, al_bom_result="")
            for i in (1, 2, 3)]
    doc = _Doc(rows)
    before = [dict(row._data) for row in rows]

    with _EngineSpy() as spy:
        try:
            guard.validate_preview_freshness(doc)
        except base.FakeFrappe.ValidationError as exc:
            message = str(exc)
        else:
            raise AssertionError("3 dòng lệch (ngưỡng 2) mà vẫn tính trong lúc Lưu")

    assert spy.calls == [], "chặn ngưỡng mà vẫn gọi engine: %s" % (spy.calls,)
    assert "3 dòng cần tính lại giá" in message, message
    assert "Tính giá" in message and "Lưu lại" in message, message
    assert [row._data for row in rows] == before, "chặn ⇒ ⛔ đụng dòng"
    assert doc.totals_calls == 0
    _assert_no_db_write()


def test_m_tong_so_dong_vuot_nguong_cung_chan():
    """Chỉ 1 dòng lệch nhưng TỔNG số dòng vượt ngưỡng ⇒ vẫn chặn."""
    _setup()
    _set_async_threshold(2)
    rows = []
    for i in (1, 2):
        row = _row(name="QI-%04d" % i, idx=i)
        row.set("al_bom_result", _stored_result(row))
        rows.append(row)
    rows.append(_row(name="new-quotation-item-3", idx=3, al_bom_result=""))

    with _EngineSpy() as spy:
        try:
            guard.validate_preview_freshness(_Doc(rows))
        except base.FakeFrappe.ValidationError as exc:
            message = str(exc)
        else:
            raise AssertionError("tổng 3 dòng > ngưỡng 2 mà vẫn tính")

    assert spy.calls == []
    assert "1 dòng cần tính lại giá" in message, message
    _assert_no_db_write()


def test_m_duoi_nguong_van_chay():
    """Đối chứng dương: 1 dòng lệch, ngưỡng 2 ⇒ chạy bình thường."""
    _setup()
    _set_async_threshold(2)
    row = _row(al_bom_result="")

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(_Doc([row]))

    assert len(spy.calls) == 1, "dưới ngưỡng mà bị chặn: %s" % (spy.calls,)
    assert row.get("al_gia_ban") == _EXPECTED_GIA_BAN
    _assert_no_db_write()


# ═══════════════════════════════════════════════════════════════════
# (n) Data Import — ⛔ tính lại giá / ⛔ ghi đè rate của tệp import
# ═══════════════════════════════════════════════════════════════════

def test_n_data_import_bo_qua():
    _setup()
    row = _row(al_bom_result="")
    doc = _Doc([row])
    before = dict(row._data)

    STUB.flags = types.SimpleNamespace(in_import=True)
    try:
        with _EngineSpy() as spy:
            guard.validate_preview_freshness(doc)
    finally:
        STUB.flags = types.SimpleNamespace()

    assert spy.calls == [], (
        "Data Import gọi doc.save() ⇒ ⛔ tính lại (sẽ ghi đè rate của tệp): %s"
        % (spy.calls,))
    assert row._data == before, "⛔ đụng dòng trong lượt import"
    assert doc.totals_calls == 0
    _assert_no_db_write()


def test_n_khong_phai_import_thi_van_chay():
    """Đối chứng dương: `in_import=False` ⇒ guard vẫn làm việc."""
    _setup()
    row = _row(al_bom_result="")
    STUB.flags = types.SimpleNamespace(in_import=False)
    try:
        with _EngineSpy() as spy:
            guard.validate_preview_freshness(_Doc([row]))
    finally:
        STUB.flags = types.SimpleNamespace()
    assert len(spy.calls) == 1, "in_import=False mà guard bỏ qua ⇒ (n) vô cảm"
    _assert_no_db_write()



# ═══════════════════════════════════════════════════════════════════
# (o) Bối cảnh giá của báo giá MỚI — lấy từ CHÍNH doc đang lưu
# ═══════════════════════════════════════════════════════════════════
# Lỗi gốc: `_row_params` chỉ đẩy field của DÒNG + `parent`. Báo giá MỚI chưa
# có dòng trong DB ⇒ engine không đọc được `Quotation.currency` /
# `selling_price_list` ⇒ `_doc_currency()` / `_default_price_list()` rơi về
# mặc định site ⇒ chọn Item Price KHÁC TIỀN TỆ ⇒ giá lưu khác giá đã preview
# và ghi Error Log.

_PRICE_CONTEXT_DOC = dict(
    currency="USD",
    selling_price_list="Standard Selling USD",
    company="NXC",
    conversion_rate=25000,
    plc_conversion_rate=25000,
    customer="KH-01",
)

_CONTEXT_PARAM_KEYS = (
    "_currency", "_price_list", "_company",
    "_conversion_rate", "_plc_conversion_rate", "_customer",
)


def _set_quotation_field(field, value, name="QTN-1"):
    """Ghi 1 field của Quotation cha trong DB stub."""
    STUB.docs[("Quotation", name)]._data[field] = value


def _set_selling_price_list(value="Standard Selling"):
    STUB.db.set_single_value("Selling Settings", "selling_price_list", value)


def _register_usd_price_list(price_list="Standard Selling USD"):
    """Thêm bảng giá USD (Price List + Item Price) vào fixture của base.

    Cần cho ca (30a): báo giá USD phải tra được bảng giá USD — nếu engine
    không nhận `_price_list` thì nó tra "Standard Selling" (VND) và ca đỏ
    ngay ở khâu so giá, đó chính là điều cần chứng minh.
    """
    STUB.set_doc("Price List", price_list, {"currency": "USD"})
    rows = [dict(r) for r in STUB.get_all_rows.get("Item Price", [])]
    for idx, row in enumerate(list(rows), 1):
        rows.append({
            "name": "IP-USD-%d" % idx,
            "item_code": row["item_code"],
            "price_list_rate": row["price_list_rate"],
            "price_list": price_list,
            "currency": "USD",
        })
    STUB.set_get_all("Item Price", rows)


def _stale_row(**overrides):
    """Dòng LỆCH hash ⇒ chắc chắn đi vào engine (để spy bắt params)."""
    return _row(name="new-quotation-item-1", al_bom_result="", **overrides)


def test_o_a_bao_gia_moi_truyen_boi_canh_gia_tu_doc():
    """(30a) Báo giá MỚI: `doc.currency`/`selling_price_list` phải tới engine."""
    _setup()
    # Bảng giá USD có thật trong fixture: engine phải tra ĐÚNG bảng giá của
    # doc (nếu còn rơi về "Standard Selling" thì params không tới nơi).
    _register_usd_price_list()
    doc = _Doc([_stale_row()], **_PRICE_CONTEXT_DOC)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    assert len(spy.calls) == 1, spy.calls
    params = spy.calls[0]["kwargs"].get("params") or {}
    assert params.get("_currency") == "USD", params
    assert params.get("_price_list") == "Standard Selling USD", params
    assert params.get("_company") == "NXC", params
    assert params.get("_conversion_rate") == 25000, params
    assert params.get("_plc_conversion_rate") == 25000, params
    assert params.get("_customer") == "KH-01", params
    # Bối cảnh giá KHÔNG được làm mất định danh dòng/cha.
    assert params.get("al_bom") == "BOM-1"
    assert params.get("parent") == "QTN-1"
    _assert_no_db_write()


def test_o_b_bao_gia_tien_te_mac_dinh_truyen_dung_gia_tri_doc():
    """(30b) Hành vi CHỌN: truyền ĐÚNG giá trị doc đang có, KỂ CẢ mặc định.

    ⛔ Không so với Global Defaults để bỏ khoá: nguồn sự thật là chính doc
    đang lưu; so sánh sẽ tốn thêm lượt đọc cấu hình mà không đổi kết quả (và
    dễ bỏ sót khi mặc định site đổi giữa chừng). Khoá doc KHÔNG có giá trị
    (None/rỗng) thì ⛔ đưa vào — tránh field rác trong params.
    """
    _setup()
    doc = _Doc([_stale_row()], currency="VND", selling_price_list="",
               company=None)

    with _EngineSpy() as spy:
        guard.validate_preview_freshness(doc)

    params = spy.calls[0]["kwargs"].get("params") or {}
    assert params.get("_currency") == "VND", params
    assert "_price_list" not in params, params
    assert "_company" not in params, params
    assert "_customer" not in params, params
    _assert_no_db_write()


def test_o_c_engine_uu_tien_params_hon_db():
    """(30c) CA THEN CHỐT: DB nói VND, params nói USD ⇒ engine dùng USD."""
    _setup()
    _set_quotation_field("currency", "VND")
    _set_selling_price_list("Standard Selling")

    orch = engine_mod.BomOrchestrator(
        quotation_item_name=None,
        params={"_currency": "USD", "_price_list": "Standard Selling USD"},
        persist=False,
    )
    orch._qi_doc = STUB._dict({"parent": "QTN-1"})

    assert orch._doc_currency() == "USD", (
        "engine phải ưu tiên `_currency` trong params (bối cảnh doc đang lưu), "
        "nhưng đọc DB VND")
    assert orch._active_price_list() == "Standard Selling USD", (
        "engine phải ưu tiên `_price_list` trong params thay Selling Settings")
    _assert_no_db_write()


def test_o_d_khong_co_params_thi_doc_db_nhu_cu():
    """(30d) Đối chứng dương: KHÔNG có khoá `_…` ⇒ đường đọc DB y như trước."""
    _setup()
    _set_quotation_field("currency", "VND")
    _set_selling_price_list("Standard Selling")

    orch = engine_mod.BomOrchestrator(
        quotation_item_name=None, params={}, persist=False)
    orch._qi_doc = STUB._dict({"parent": "QTN-1"})

    assert orch._doc_currency() == "VND", (
        "không có params mà không đọc Quotation.currency từ DB")
    assert orch._active_price_list() == "Standard Selling", (
        "không có params mà không đọc Selling Settings")
    _assert_no_db_write()


def test_o_e_client_gui_khoa_boi_canh_gia_bi_bo():
    """(30e) BẢO MẬT: client gửi `_currency: USD` qua `preview_bom` ⇒ bị BỎ.

    Báo giá VND + bảng giá mặc định ⇒ engine nhận params KHÔNG có khoá `_…`
    và vẫn resolve tiền tệ VND từ DB. Nếu ai đó thêm các khoá này vào
    allowlist (hoặc bỏ chốt lọc), ca này đỏ.
    """
    _setup()
    _set_quotation_field("currency", "VND")
    _set_selling_price_list("Standard Selling")

    forged = {
        "al_bom": "BOM-1",
        "al_bom_version": "ALBOMV-1",
        "al_bom_vars": _VARS,
        "item_code": "SP-01",
        "qty": 1,
        "parent": "QTN-1",
        "parenttype": "Quotation",
        "_currency": "USD",
        "_price_list": "Standard Selling USD",
        "_company": "Cong ty gia",
        "_conversion_rate": 99,
        "_plc_conversion_rate": 99,
        "_customer": "KH-GIA",
    }

    parsed = api_mod._parse_preview_params(json.dumps(forged))
    for key in _CONTEXT_PARAM_KEYS:
        assert key not in parsed, (
            "client gửi %r mà `_parse_preview_params` vẫn giữ: %s" % (key, parsed))

    with _EngineSpy() as spy:
        api_mod.preview_bom("QI-0001", json.dumps(forged))

    assert len(spy.calls) == 1, spy.calls
    sent = spy.calls[0]["kwargs"].get("params") or {}
    for key in _CONTEXT_PARAM_KEYS:
        assert key not in sent, (
            "client gửi %r mà engine vẫn nhận được: %s" % (key, sent))

    # Vẫn dùng ĐÚNG bối cảnh của DB (VND + bảng giá mặc định của site).
    orch = engine_mod.BomOrchestrator(params=dict(sent), persist=False)
    orch._qi_doc = STUB._dict({"parent": sent.get("parent") or "QTN-1"})
    assert orch._doc_currency() == "VND", (
        "tiền tệ phải đọc từ Quotation.currency (VND), không phải từ client")
    assert orch._active_price_list() == "Standard Selling"
    _assert_no_db_write()


def test_o_f_cau_loi_co_loi_thoat_bo_ma_bom():
    """(30f) Không tính lại được ⇒ câu lỗi phải nêu lối thoát "bỏ mã BOM"."""
    _setup()
    row = _stale_row()
    doc = _Doc([row])

    with _EngineSpy(fail_with=RuntimeError("BOM Version không có snapshot")):
        try:
            guard.validate_preview_freshness(doc)
        except base.FakeFrappe.ValidationError as exc:
            message = str(exc)
        else:
            raise AssertionError("engine lỗi mà vẫn lưu báo giá với giá cũ")

    assert "bỏ mã BOM khỏi dòng" in message, message
    assert "Lưu lại" in message, message
    for leak in ("traceback", "runtimeerror", "snapshot"):
        assert leak not in message.lower(), "⛔ phơi lỗi kỹ thuật: %s" % message
    _assert_no_db_write()


def test_o_g_khoa_boi_canh_gia_khong_lot_vao_doc_gia():
    """(30g) Khoá `_…` chỉ là bối cảnh, ⛔ được thành field rác của `_qi_doc`.

    `_build_preview_doc` dựng doc giả cho engine: dòng MỚI chỉ nhận
    `PREVIEW_ROW_FIELDS` + định danh cha; dòng ĐÃ LƯU nhận bản sao DB. Khoá
    `_currency`… lọt vào doc giả sẽ thành field rác (engine đọc nhầm / meta
    lạ) — phải kiểm cả 2 nhánh.
    """
    context = {key: "gia-tri" for key in _CONTEXT_PARAM_KEYS}

    # Nhánh dòng MỚI: dựng doc từ params.
    orch = engine_mod.BomOrchestrator(
        quotation_item_name=None,
        params=dict(context, al_bom="BOM-1", al_bom_version="ALBOMV-1",
                    parent="QTN-1", parenttype="Quotation"),
        persist=False,
    )
    new_doc = orch._build_preview_doc()
    for key in _CONTEXT_PARAM_KEYS:
        assert key not in new_doc, (
            "khoá bối cảnh %r lọt vào doc giả của dòng mới: %s"
            % (key, dict(new_doc)))
    assert new_doc.get("al_bom") == "BOM-1"

    # Nhánh dòng ĐÃ LƯU: phủ params lên bản sao DB.
    _setup()
    orch = engine_mod.BomOrchestrator(
        quotation_item_name="QI-0001",
        params=dict(context, al_bom="BOM-1", al_bom_version="ALBOMV-1",
                    parent="QTN-1", parenttype="Quotation"),
        persist=False,
    )
    saved_doc = orch._build_preview_doc()
    for key in _CONTEXT_PARAM_KEYS:
        assert key not in saved_doc, (
            "khoá bối cảnh %r lọt vào doc giả của dòng đã lưu: %s"
            % (key, dict(saved_doc)))
    assert saved_doc.get("al_bom") == "BOM-1"


def test_o_h_danh_sach_khoa_boi_canh_khop_nhau():
    """(30h) 3 danh sách khoá `_…` phải KHỚP — lệch là lỗ âm thầm.

    - `preview_guard._PRICE_CONTEXT_FIELDS` sinh ra khoá cho engine;
    - `engine.SERVER_CONTEXT_KEYS` là khoá engine đọc;
    - `api._SERVER_CONTEXT_PARAM_KEYS` là khoá bị chặn từ client.
    Danh sách client bị chặn phải PHỦ danh sách engine đọc, nếu không client
    gửi được một khoá mà engine vẫn nghe theo.
    """
    guard_keys = {key for key, _field in guard._PRICE_CONTEXT_FIELDS}
    engine_keys = set(engine_mod.BomOrchestrator.SERVER_CONTEXT_KEYS)
    blocked_keys = set(api_mod._SERVER_CONTEXT_PARAM_KEYS)

    assert guard_keys == engine_keys, (
        "preview_guard dựng khoá %s nhưng engine đọc %s"
        % (sorted(guard_keys), sorted(engine_keys)))
    assert engine_keys <= blocked_keys, (
        "engine đọc khoá mà `_parse_preview_params` KHÔNG chặn từ client: %s"
        % sorted(engine_keys - blocked_keys))


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
