# -*- coding: utf-8 -*-
"""PHASE 1 "Preview tính giá KHÔNG ghi DB" — test standalone.

BỐI CẢNH (Owner chốt 2026-11-21, design `docs/design/preview-khong-ghi-db.md`)
─────────────────────────────────────────────────────────────────────────────
Preview (kể cả auto-preview 700 ms sau mỗi lần sửa tham số) ⛔ KHÔNG được ghi
một byte nào xuống DB. DB chỉ đổi khi người dùng bấm Lưu báo giá.

Bộ test này kiểm 5 bất biến:
  (i)   preview ⛔ gọi `frappe.db.set_value`/`commit` — 0 lần, kể cả nhiều lượt;
  (ii)  kết quả preview TRÙNG TỪNG SỐ với `calculate_bom` (cùng tham số, cùng
        fixture): buckets/cost_template/lines/gia_vat/gia_ban;
  (iii) dòng MỚI (không có tên trong DB) preview chạy được, ⛔ ghi DB;
  (iv)  mã BOM/Version client gửi mà KHÔNG có quyền đọc ⇒ bị chặn bằng
        PermissionError (⛔ không phải 500 / lỗi kỹ thuật);
  (v)   `calc_meta.params_hash` đổi khi `al_bom_vars` đổi, KHÔNG đổi khi chỉ
        đổi thứ tự key / thụt lề JSON (chuẩn hoá `sort_keys`);
  (vi)  nhánh BOM lớn (async) ⛔ không set status/job id, chỉ publish realtime
        cho ĐÚNG user đã enqueue.

VÌ SAO ĐẶT Ở `standalone_tests/`
──────────────────────────────────
`bench run-tests --app alumglass` os.walk toàn bộ package `alumglass/` ⇒ file
stub `frappe` nằm trong package sẽ thay `sys.modules["frappe"]` và phá cả lượt
chạy test của site. Thư mục này nằm NGOÀI package nên bench không collect (xem
docstring `standalone_tests/test_phase_b_fbmax.py`).

MÁY NÀY KHÔNG CÓ SITE CÀI ALUMGLASS ⇒ bộ test chạy trên stub `frappe` của
`test_phase_b_fbmax.py`, KHÔNG phải site thật. Vì vậy:
  · (ii) chứng minh "2 đường dùng CHUNG engine, ra cùng số" — NÓ KHÔNG phải
    chứng minh số vàng 2C/4C của production. Số vàng 2C (22 717 289) và 4C
    CHƯA được khoá trên máy này (xem báo cáo job + cách đo trên site).

CÁCH CHẠY (không cần site):
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=/home/nxc/myfrappe/apps \\
        /home/nxc/myfrappe/env/bin/python standalone_tests/test_preview_bom_no_persist.py
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
# Bổ sung stub — chỉ những gì `preview_bom` cần mà base chưa có.
# ⛔ KHÔNG sửa `test_phase_b_fbmax.py`: bộ đó là nền dùng chung, sửa vào sẽ
# làm đổi ý nghĩa 29 ca của nó.
# ═══════════════════════════════════════════════════════════════════

class _FakeDict(dict):
    """`frappe._dict` tối thiểu — dòng MỚI của preview dựng bằng `_dict`."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


def _fake_set_value(self, doctype, name, field_or_dict, value=None,
                    update_modified=True):
    """Nhận thêm `update_modified` (B7 truyền) và GHI LẠI được field.

    Ghi lại là cần thiết để ca "preview rồi Lưu" và ca đối chứng `modified`
    nhìn thấy đúng giá trị thật, không chỉ đếm lời gọi. Với dict thì hợp nhất
    từng field vào doc đang đăng ký.
    """
    self._owner.set_value_calls.append((doctype, name, field_or_dict, value))
    doc = self._owner.docs.get((doctype, name))
    if doc is None or not isinstance(field_or_dict, dict):
        return
    for field, val in field_or_dict.items():
        doc._data[field] = val


base.FakeDB.set_value = _fake_set_value


class _FakeMeta:
    def has_field(self, fieldname):
        return True


def _install_api_stubs():
    """Gắn các API Frappe mà `preview_bom` chạm tới."""
    STUB._dict = _FakeDict
    STUB.session = types.SimpleNamespace(user="preview-tester@example.com")
    STUB.enqueue_calls = []
    STUB.realtime_calls = []
    STUB.set_user_calls = []
    STUB.denied = set()          # {(doctype, ptype, doc)} → từ chối

    def _has_permission(doctype=None, ptype="read", doc=None, user=None,
                        verbose=False, throw=False, *,
                        parent_doctype=None, ignore_share_permissions=False):
        """Chữ ký THẬT của `frappe.has_permission` v14/v16.

        Stub cũ `(*args, **kwargs)` nhận MỌI kwarg ⇒ lời gọi sai tên
        (`raise_exception=`) lọt qua test rồi 500 trên site thật (2026-11-23).
        """
        if (doctype, ptype, doc) in STUB.denied:
            return False
        return True

    def _throw(*args, **kwargs):
        """`frappe.throw(msg, ExcClass)` phải ném ĐÚNG lớp exception.

        Stub gốc ném `Exception` trơn ⇒ không phân biệt được "bị chặn quyền"
        (PermissionError, 403) với "lỗi hạ tầng" (500) — đúng thứ ca (iv) cần.
        """
        exc_type = kwargs.get("exc")
        for arg in args[1:]:
            if isinstance(arg, type) and issubclass(arg, BaseException):
                exc_type = arg
        message = args[0] if args else "frappe.throw"
        raise (exc_type or Exception)(message)

    STUB.has_permission = _has_permission
    STUB.throw = _throw
    STUB.set_user = lambda user: STUB.set_user_calls.append(user)
    STUB.generate_hash = lambda length=8: ("h" * (length - 1)) + str(
        len(STUB.enqueue_calls))
    STUB.enqueue = lambda **kwargs: STUB.enqueue_calls.append(kwargs)
    STUB.publish_realtime = lambda event, message=None, user=None, **kw: (
        STUB.realtime_calls.append(
            {"event": event, "message": message, "user": user})
    )


_install_api_stubs()


# ═══════════════════════════════════════════════════════════════════
# Fixture — mirror `_prepare_orchestrator` của base, thêm phần Quotation
# để nhánh `persist=True` (B7) chạy được và ta so được 2 đường.
# ═══════════════════════════════════════════════════════════════════

def _prepare(extra=None):
    """Dựng fixture ĐẦY ĐỦ cho B0→B7, trả orchestrator (persist=True).

    `extra` mặc định = `base.EXTRA` (VAT_RATE, PROFIT_MARGIN, kích thước…) —
    dùng CÙNG bộ tham số với `_params()` để 2 đường so được với nhau.
    """
    orch = base._prepare_orchestrator(base.EXTRA if extra is None else extra)
    # `_reset_stub` xoá data của stub nhưng KHÔNG xoá bộ đếm của ta.
    STUB.enqueue_calls = []
    STUB.realtime_calls = []
    STUB.set_user_calls = []
    STUB.denied = set()

    # B7 (`_recalculate_quotation_totals`) cần Quotation có dòng + hàm tính
    # tổng. Stub base chỉ có {"docstatus": 0} ⇒ dựng thêm tối thiểu.
    row = base.FakeDoc({
        "name": "QI-0001", "rate": 0, "qty": 1, "item_name": "Sản phẩm",
        "precision": (lambda fieldname: 2),
    }, "QI-0001")
    parent = STUB.docs[("Quotation", "QTN-1")]
    parent._data["items"] = [row]
    parent._data["meta"] = _FakeMeta()
    parent._data["set_total_in_words"] = lambda: None

    def _calculate_totals():
        total = 0.0
        for item in parent._data["items"]:
            total += float(item.get("rate") or 0) * float(item.get("qty") or 1)
        parent._data["grand_total"] = total
        parent._data["total"] = total

    parent._data["calculate_taxes_and_totals"] = _calculate_totals
    return orch


def _params(extra=None, **overrides):
    """Params y như client gửi: đúng 5 field + định danh cha."""
    extra = base.EXTRA if extra is None else extra
    params = {
        "al_bom": "BOM-1",
        "al_bom_version": "ALBOMV-1",
        "al_bom_vars": json.dumps({"extra_vars": dict(extra)}),
        "item_code": "",
        "item_name": "Sản phẩm",
        "qty": 1,
        "uom": "Cái",
        "parent": "QTN-1",
        "parenttype": "Quotation",
    }
    params.update(overrides)
    return params


def _preview(extra=None, name="QI-0001", **overrides):
    from alumglass.engine.bom_orchestrator import BomOrchestrator
    return BomOrchestrator(
        quotation_item_name=name, params=_params(extra, **overrides),
        persist=False,
    ).run()


# ═══════════════════════════════════════════════════════════════════
# (i) Preview ⛔ ghi DB — kể cả nhiều lượt với tham số khác nhau
# ═══════════════════════════════════════════════════════════════════

def test_preview_khong_ghi_db_mot_byte_nao():
    """3 lượt preview (tham số khác nhau) ⇒ 0 `set_value`, 0 `commit`."""
    _prepare()
    modified_before = STUB.docs[("Quotation", "QTN-1")]._data.get("modified")
    docs_before = dict(STUB.docs)

    _preview()
    _preview(al_bom_version="ALBOMV-1",
             al_bom_vars=json.dumps({"extra_vars": dict(base.EXTRA, VAT_RATE=0.2)}))
    _preview(al_bom_vars=json.dumps({"extra_vars": dict(base.EXTRA, PROFIT_MARGIN=0.5)}))

    assert STUB.set_value_calls == [], (
        "preview KHÔNG được ghi DB, nhưng đã gọi set_value: %s"
        % (STUB.set_value_calls,))
    assert STUB.commit_count == 0, (
        "preview KHÔNG được commit, nhưng đã commit %d lần" % STUB.commit_count)
    assert set(STUB.docs) == set(docs_before), "preview KHÔNG được tạo/xoá doc nào"
    assert STUB.docs[("Quotation", "QTN-1")]._data.get("modified") == modified_before, (
        "`modified` của Quotation cha ⛔ được nhảy khi preview")


# ═══════════════════════════════════════════════════════════════════
# (ii) Preview TRÙNG TỪNG SỐ với calculate_bom (cùng tham số, cùng fixture)
# ═══════════════════════════════════════════════════════════════════

def test_preview_trung_so_voi_calculate_bom():
    """`persist=False` vs `persist=True` trên cùng fixture ⇒ bằng nhau từng key.

    Đường `persist=True` dùng đúng `BomOrchestrator(...).run()` mà
    `alumglass.api.calculate_bom` gọi (B0→B7).
    """
    orch = _prepare()
    preview = _preview()

    live = orch.run()  # calculate_bom: B0→B7, GHI DB (đối chứng)
    assert STUB.set_value_calls, "đối chứng: đường tính+Lưu PHẢI có ghi DB"
    assert STUB.commit_count == 1, "đối chứng: đường tính+Lưu commit đúng 1 lần"

    for key in ("buckets", "cost_template", "lines", "gia_vat", "gia_ban"):
        assert preview[key] == live[key], (
            "key %r lệch giữa preview và calculate_bom:\n  preview=%r\n  live=%r"
            % (key, preview[key], live[key]))

    # Không được "bằng nhau vì cùng rỗng" — chốt thêm 3 mốc có số thật.
    assert preview["buckets"].get("VL_KINH") == 1200000.0, preview["buckets"]
    assert preview["cost_template"].get("GIA_THANH") == 2400000.0, preview["cost_template"]
    assert len(preview["lines"]) == 2, preview["lines"]

    assert preview["calc_meta"]["preview"] is True
    assert live["calc_meta"]["preview"] is False
    assert preview["calc_meta"]["params_hash"] == live["calc_meta"]["params_hash"], (
        "cùng tham số ⇒ cùng params_hash (preview rồi Lưu phải khớp được)")


# ═══════════════════════════════════════════════════════════════════
# (iii) Dòng MỚI — chạy được, ⛔ tạo dòng, ⛔ ghi DB
# ═══════════════════════════════════════════════════════════════════

def test_dong_moi_preview_chay_duoc_khong_ghi_db():
    """`quotation_item_name=None` + cha thật ⇒ có kết quả, 0 dòng được tạo."""
    _prepare()
    rows_before = len([k for k in STUB.docs if k[0] == "Quotation Item"])

    result = _preview(name=None)

    assert result["buckets"].get("VL_KINH") == 1200000.0, result["buckets"]
    assert len(result["lines"]) == 2
    assert STUB.set_value_calls == []
    assert STUB.commit_count == 0
    rows_after = len([k for k in STUB.docs if k[0] == "Quotation Item"])
    assert rows_after == rows_before, "preview dòng mới KHÔNG được tạo dòng Quotation Item"


def test_api_preview_dong_moi_va_cha_new():
    """API: dòng mới, cha `new-…` ⇒ cần quyền `create` trên Quotation."""
    _prepare()
    result = api.preview_bom("", json.dumps(_params(parent="new-quotation-1")))
    assert result["calc_meta"]["preview"] is True
    assert result["buckets"].get("VL_NHOM") == 1200000.0
    assert STUB.set_value_calls == [], "API preview ⛔ ghi DB"

    # Không có quyền tạo báo giá ⇒ bị chặn, ⛔ không chạy engine.
    STUB.denied = {("Quotation", "create", None)}
    try:
        api.preview_bom("", json.dumps(_params(parent="new-quotation-1")))
    except base.FakeFrappe.PermissionError as exc:
        assert "quyền tạo báo giá" in str(exc)
    else:
        raise AssertionError("thiếu quyền `create` mà vẫn preview được")
    finally:
        STUB.denied = set()

    # API dòng mới trên báo giá ĐÃ LƯU (cha thật) cũng chạy, ⛔ tạo dòng.
    result2 = api.preview_bom("", json.dumps(_params()))
    assert result2["buckets"].get("VL_KINH") == 1200000.0


# ═══════════════════════════════════════════════════════════════════
# (iv) Quyền — client gửi mã BOM/Version không có quyền đọc ⇒ bị chặn
# ═══════════════════════════════════════════════════════════════════

def test_thieu_quyen_doc_bom_client_gui_bi_chan():
    _prepare()
    STUB.denied = {("AL BOM", "read", "BOM-2")}
    try:
        api.preview_bom("QI-0001", json.dumps(_params(al_bom="BOM-2")))
    except base.FakeFrappe.PermissionError as exc:
        assert "AL BOM" in str(exc)
    else:
        raise AssertionError("mã BOM ngoài quyền mà vẫn trả kết quả")

    STUB.denied = {("AL BOM Version", "read", "ALBOMV-9")}
    try:
        api.preview_bom("QI-0001", json.dumps(_params(al_bom_version="ALBOMV-9")))
    except base.FakeFrappe.PermissionError as exc:
        assert "AL BOM Version" in str(exc)
    else:
        raise AssertionError("mã BOM Version ngoài quyền mà vẫn trả kết quả")
    finally:
        STUB.denied = set()

    # Mã KHÔNG tồn tại ⇒ câu người-đọc-được (⛔ 404 tiếng Anh của get_doc).
    original_has_permission = STUB.has_permission

    def _missing_bom(doctype, ptype="read", doc=None, **kwargs):
        if doctype == "AL BOM":
            raise base.FakeFrappe.DoesNotExistError("AL BOM not found")
        return True

    STUB.has_permission = _missing_bom
    try:
        api.preview_bom("QI-0001", json.dumps(_params(al_bom="BOM-KHONG-CO")))
    except base.FakeFrappe.ValidationError as exc:
        assert "Không tìm thấy" in str(exc), str(exc)
    else:
        raise AssertionError("mã BOM không tồn tại mà vẫn trả kết quả")
    finally:
        STUB.has_permission = original_has_permission


def test_thieu_quyen_doc_quotation_bi_chan():
    _prepare()
    STUB.denied = {("Quotation", "read", "QTN-1")}
    try:
        api.preview_bom("QI-0001", json.dumps(_params()))
    except base.FakeFrappe.PermissionError:
        pass
    else:
        raise AssertionError("không có quyền đọc báo giá mà vẫn preview được")
    finally:
        STUB.denied = set()


def test_bao_gia_da_submit_bi_chan():
    """Cha docstatus=1 ⇒ chặn SỚM, ⛔ không đọc/tính."""
    _prepare()
    STUB.docs[("Quotation", "QTN-1")]._data["docstatus"] = 1
    try:
        api.preview_bom("QI-0001", json.dumps(_params()))
    except Exception as exc:  # stub `frappe.throw` ném Exception với câu tiếng Việt
        assert "đã gửi khách" in str(exc), str(exc)
    else:
        raise AssertionError("báo giá đã submit mà vẫn tính lại giá")
    assert STUB.set_value_calls == []


def test_params_hong_tra_cau_nguoi_doc_duoc():
    """JSON hỏng ⇒ ValidationError (417), ⛔ 500/⛔ lộ thông điệp kỹ thuật."""
    _prepare()
    try:
        api.preview_bom("QI-0001", "{khong-phai-json")
    except base.FakeFrappe.ValidationError as exc:
        assert "Tham số tính giá bị hỏng" in str(exc)
        assert "json" not in str(exc).lower(), "⛔ phơi lỗi kỹ thuật của json.loads"
    else:
        raise AssertionError("params hỏng mà không báo lỗi")


# ═══════════════════════════════════════════════════════════════════
# (v) params_hash — chuẩn hoá sort_keys
# ═══════════════════════════════════════════════════════════════════

def test_params_hash_chuan_hoa():
    from alumglass.engine.bom_orchestrator import compute_params_hash

    vars_a = json.dumps({"extra_vars": {"B": 2, "A": 1}}, sort_keys=True)
    vars_b = '{\n  "extra_vars": {\n    "A": 1,\n    "B": 2\n  }\n}'
    assert compute_params_hash("BOM-1", "V1", "SP", vars_a) == \
        compute_params_hash("BOM-1", "V1", "SP", vars_b), (
        "thứ tự key / thụt lề JSON ⛔ được làm đổi params_hash (sort_keys)")

    vars_c = json.dumps({"extra_vars": {"A": 1, "B": 3}}, sort_keys=True)
    assert compute_params_hash("BOM-1", "V1", "SP", vars_a) != \
        compute_params_hash("BOM-1", "V1", "SP", vars_c), "đổi giá trị ⇒ hash phải đổi"

    assert compute_params_hash("BOM-1", "V1", "SP", vars_a) != \
        compute_params_hash("BOM-2", "V1", "SP", vars_a), "đổi BOM ⇒ hash phải đổi"

    # ⚠ Ghi nhận KHÁC design §8.7: "2400" (chuỗi) và 2400 (số) cho hash KHÁC
    # nhau, vì engine nhận đúng kiểu client gửi và 2 kiểu có thể cho kết quả
    # khác. Ép kiểu ở đây sẽ khiến hash nói "cùng tham số" khi thực ra không.
    number_hash = compute_params_hash("BOM-1", "V1", "SP", {"X": 2400})
    string_hash = compute_params_hash("BOM-1", "V1", "SP", {"X": "2400"})
    assert number_hash != string_hash


def test_calc_meta_doi_khi_vars_doi():
    _prepare()
    a = _preview()
    b = _preview(al_bom_vars=json.dumps({"extra_vars": dict(base.EXTRA, VAT_RATE=0.5)}))
    assert a["calc_meta"]["params_hash"] != b["calc_meta"]["params_hash"]
    assert a["calc_meta"]["computed_at"].endswith("Z")
    assert a["calc_meta"]["engine"] == "alumglass.bom_orchestrator"


# ═══════════════════════════════════════════════════════════════════
# (vi) Nhánh BOM lớn (async) — ⛔ ghi DB, publish ĐÚNG user
# ═══════════════════════════════════════════════════════════════════

def test_async_preview_khong_ghi_db_va_publish_dung_user():
    _prepare()
    params = _params()

    # API chọn nhánh async khi số dòng BOM > ngưỡng.
    from alumglass.api import _enqueue_preview
    response = _enqueue_preview(params, 999)

    assert response["async"] is True
    assert response["job_id"]
    assert STUB.set_value_calls == [], "nhánh BOM lớn ⛔ được ghi status/job id"
    assert STUB.commit_count == 0
    assert len(STUB.enqueue_calls) == 1, STUB.enqueue_calls
    job = STUB.enqueue_calls[0]
    assert job["method"] == "alumglass.api._run_preview_job"
    assert job["params"] == params, "payload chụp params MỘT LẦN lúc enqueue"
    assert job["user"] == "preview-tester@example.com"

    # Job nền: publish CHỈ cho user đã enqueue, kèm params_hash, ⛔ ghi DB.
    result = _preview()
    from alumglass.engine import bom_orchestrator as engine_mod
    original = engine_mod.BomOrchestrator

    class _FakeOrchestrator(object):
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def run(self):
            assert self.kwargs.get("persist") is False, (
                "job preview PHẢI chạy persist=False")
            return result

    engine_mod.BomOrchestrator = _FakeOrchestrator
    try:
        api._run_preview_job(params, "job-1", "preview-tester@example.com")
    finally:
        engine_mod.BomOrchestrator = original

    assert STUB.set_user_calls == ["preview-tester@example.com"]
    assert STUB.set_value_calls == [], "job nền preview ⛔ ghi DB"
    assert len(STUB.realtime_calls) == 1
    event = STUB.realtime_calls[0]
    assert event["event"] == "alumglass_bom_calc_done"
    assert event["user"] == "preview-tester@example.com", "⛔ broadcast chung"
    assert event["message"]["status"] == "Success"
    assert event["message"]["preview"] is True
    assert event["message"]["params_hash"] == result["calc_meta"]["params_hash"]


def test_async_preview_loi_bao_cau_nguoi_doc_duoc():
    _prepare()
    from alumglass.engine import bom_orchestrator as engine_mod
    original = engine_mod.BomOrchestrator

    class _Boom(object):
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            raise RuntimeError("stack trace noi bo")

    engine_mod.BomOrchestrator = _Boom
    try:
        api._run_preview_job(_params(), "job-2", "preview-tester@example.com")
    finally:
        engine_mod.BomOrchestrator = original

    assert STUB.set_value_calls == []
    event = STUB.realtime_calls[-1]
    assert event["message"]["status"] == "Failed"
    assert "stack" not in event["message"]["error"].lower(), (
        "⛔ phơi stack trace ra người dùng")
    assert "báo quản trị" in event["message"]["error"] or \
        "thử lại" in event["message"]["error"]


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
