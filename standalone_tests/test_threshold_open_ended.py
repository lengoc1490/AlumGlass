# -*- coding: utf-8 -*-
"""Standalone test — dải ngưỡng MỞ PHÍA TRÊN ("Đến bỏ trống = trở lên").

Nhãn cột trên form `AL Rule Threshold Row` là **"Đến (bỏ trống = trở lên)"**,
nhưng trước 2026-11-25 engine đọc `to_value` rỗng thành 0 bằng `_num("")`:
  - `validate_threshold_rows` đòi đủ 'Từ' và 'Đến' ⇒ không lưu được;
  - `match_threshold_row` so `val < 0` ⇒ dải mở không bao giờ khớp, còn lưới
    tương thích `val == _num(to)` lại khớp SAI giá trị 0;
  - `warn_threshold_gaps` / `_threshold_miss_message` báo khe hở và "trên
    dải cao nhất — dải cuối kết thúc ở 0" sai.

Phủ (mỗi nhóm đều có ĐỐI CHỨNG ÂM — cố tình làm hỏng thì test phải đỏ):
  (1) `match_threshold_row` — dải mở khớp `val >= from`, ⛔ khớp 0 oan.
  (2) `validate_threshold_rows` — cho phép dải cuối mở, chặn dải mở ở giữa,
      `from` vẫn bắt buộc, `from > to` chỉ kiểm khi dải đóng.
  (3) `warn_threshold_gaps` — dải mở không có khe phía trên.
  (4) `ALRule._threshold_miss_message` — dải cuối mở ⛔ câu "trên dải cao
      nhất"; dải cuối đóng vẫn có câu đó.
  (5) `ALRule.preview()` — `matched.to is None`, `rows[-1]["to"] is None`,
      `is_match` đúng dòng.
  (6) JSON field `to_value` — bỏ `reqd`, giữ nhãn "Đến (bỏ trống = trở lên)".

CÁCH CHẠY (không cần site):
    PYTHONPATH=/home/nxc/myfrappe/apps/formula_builder:/home/nxc/myfrappe/apps:/home/nxc/myfrappe/apps/alumglass \
        python3 standalone_tests/test_threshold_open_ended.py
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

from alumglass.al_formula_rules import rule_engine  # noqa: E402
from alumglass.al_formula_rules.doctype.al_rule.al_rule import (  # noqa: E402
    ALRule,
    _threshold_miss_message,
)


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


def _raised(callable_):
    """Chạy và trả câu lỗi; None nếu KHÔNG throw (đối chứng âm)."""
    try:
        callable_()
    except STUB.ValidationError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 — phân biệt "đỏ vì lỗi khác"
        return "LỖI KHÁC: %r" % (exc,)
    return None


# ═══════════════════════════════════════════════════════════════════
# Dựng ALRule thật (controller) nạp bằng dict — như test_rule_preview
# ═══════════════════════════════════════════════════════════════════
def _rule(threshold_rows, result_type="NUMBER", **extra):
    data = {
        "rule_code": "RULE-DAI-MO",
        "rule_name": "Quy tắc dải mở",
        "rule_description": "",
        "input_label": "Độ dày kính",
        "input_unit": "mm",
        "output_label": "Kết quả",
        "is_active": 1,
        "rule_type": "THRESHOLD",
        "result_type": result_type,
        "constant_value": None,
        "threshold_rows": list(threshold_rows or []),
        "lookup_rows": [],
    }
    data.update(extra)
    doc = ALRule()
    doc._data = data
    for key, value in data.items():
        setattr(doc, key, value)
    return doc


def _row(from_value, to_value, result=0):
    """Dòng ngưỡng; `to_value = None` nghĩa là ô "Đến" để TRỐNG."""
    return {"from_value": from_value, "to_value": to_value,
            "result_value": result}


# ═══════════════════════════════════════════════════════════════════
# (1) match_threshold_row
# ═══════════════════════════════════════════════════════════════════
OPEN_ROWS = [_row(0, 10, 100), _row(10, None, 200)]


def test_dai_mo_khop_moi_gia_tri_tu_from_tro_len():
    for value in (10, 10.0001, 25.5, 999999):
        row = rule_engine.match_threshold_row(OPEN_ROWS, value)
        assert row is not None, value
        assert row["result_value"] == 200, (value, row)
    # `resolve_threshold` (đường tính giá) cũng phải trả đúng kết quả.
    assert rule_engine.resolve_threshold(
        OPEN_ROWS, 12345, "result_value") == 200


def test_dai_mo_khong_khop_0_oan():
    """ĐỐI CHỨNG ÂM cho `_num("") = 0`: lưới tương thích ⛔ được khớp giá trị 0."""
    rows = [_row(10, None, 200)]
    for value in (0, 0.0, 9.999):
        assert rule_engine.match_threshold_row(rows, value) is None, value
        assert rule_engine.resolve_threshold(
            rows, value, "result_value") is None, value


def test_dai_mo_from_0_van_khop_gia_tri_0():
    """0 là giá trị THẬT (không phải "rỗng") ⇒ dải mở từ 0 khớp 0."""
    rows = [_row(0, None, 200)]
    assert rule_engine.match_threshold_row(rows, 0)["result_value"] == 200


def test_dai_dong_giu_nguyen_hanh_vi_cu():
    """ĐỐI CHỨNG DƯƠNG: dải đóng hết ⇒ không khớp trên dải cao nhất."""
    rows = [_row(0, 10, 100), _row(10, 20, 200)]
    assert rule_engine.match_threshold_row(rows, 5)["result_value"] == 100
    assert rule_engine.match_threshold_row(rows, 10)["result_value"] == 200
    assert rule_engine.match_threshold_row(rows, 20.5) is None


# ═══════════════════════════════════════════════════════════════════
# (2) validate_threshold_rows
# ═══════════════════════════════════════════════════════════════════
def test_validate_cho_phep_dai_cuoi_mo():
    MSGPRINTS.clear()
    error = _raised(lambda: rule_engine.validate_threshold_rows(
        OPEN_ROWS, "result_value", "AL Rule"))
    assert error is None, error
    # Chạm biên liền nhau (to của dải trước = from dải sau) ⇒ ⛔ khe hở.
    assert MSGPRINTS == [], MSGPRINTS


def test_validate_throw_khi_dai_mo_khong_o_cuoi():
    """Dải mở ở GIỮA nuốt mọi dải trên nó ⇒ chặn lúc Lưu."""
    rows = [_row(0, None, 100), _row(10, 20, 200)]
    error = _raised(lambda: rule_engine.validate_threshold_rows(
        rows, "result_value", "AL Rule"))
    assert error is not None, "dải mở không ở cuối mà ⛔ bị chặn"
    assert "dải mở" in error and "CUỐI" in error, error


def test_validate_throw_khi_thieu_from():
    """`Từ` VẪN bắt buộc dù `Đến` được bỏ trống."""
    rows = [_row(None, None, 100)]
    error = _raised(lambda: rule_engine.validate_threshold_rows(
        rows, "result_value", "AL Rule"))
    assert error is not None, "thiếu 'Từ' mà ⛔ bị chặn"
    assert "'Từ'" in error, error


def test_validate_throw_khi_from_lon_hon_to_dai_dong():
    rows = [_row(20, 10, 100)]
    error = _raised(lambda: rule_engine.validate_threshold_rows(
        rows, "result_value", "AL Rule"))
    assert error is not None, "dải đóng ngược mà ⛔ bị chặn"
    assert "lớn hơn" in error, error


def test_validate_dai_mo_chi_can_from_khong_so_sanh_to():
    """`from > to` chỉ kiểm dải ĐÓNG — dải mở không có `to` để so."""
    MSGPRINTS.clear()
    rows = [_row(9999, None, 100)]
    error = _raised(lambda: rule_engine.validate_threshold_rows(
        rows, "result_value", "AL Rule"))
    assert error is None, error


def test_validate_to_bang_0_la_gia_tri_that():
    """`to_value = 0` là ĐÓNG ở 0, ⛔ phải "rỗng"."""
    MSGPRINTS.clear()
    rows = [_row(-10, 0, 100)]
    error = _raised(lambda: rule_engine.validate_threshold_rows(
        rows, "result_value", "AL Rule"))
    assert error is None, error


def test_al_rule_validate_dau_cuoi_voi_dai_mo():
    """Đường thật `ALRule.validate()` — dải mở cuối lưu được."""
    STUB.set_get_all("AL Variable Library", [])
    doc = _rule(OPEN_ROWS)
    doc.validate()  # ⛔ throw
    assert doc.threshold_rows[1]["to_value"] is None


# ═══════════════════════════════════════════════════════════════════
# (3) warn_threshold_gaps
# ═══════════════════════════════════════════════════════════════════
def test_warn_khong_bao_khe_khi_dai_cuoi_mo():
    MSGPRINTS.clear()
    rule_engine.warn_threshold_gaps(OPEN_ROWS, "Cảnh báo khe hở")
    assert MSGPRINTS == [], MSGPRINTS


def test_warn_bao_khe_khi_hai_dai_dong_co_khe():
    """ĐỐI CHỨNG DƯƠNG: dải đóng có khe thật ⇒ vẫn phải cảnh báo."""
    MSGPRINTS.clear()
    rule_engine.warn_threshold_gaps(
        [_row(0, 10, 100), _row(10.5, 20, 200)], "Cảnh báo khe hở")
    assert len(MSGPRINTS) == 1, MSGPRINTS
    assert "KHE HỞ" in MSGPRINTS[0]["message"], MSGPRINTS


def test_warn_khong_bao_khe_khi_lien_nhau_va_dai_mo():
    MSGPRINTS.clear()
    rule_engine.warn_threshold_gaps(
        [_row(0, 10, 100), _row(10, 20, 200), _row(20, None, 300)],
        "Cảnh báo khe hở")
    assert MSGPRINTS == [], MSGPRINTS


def test_warn_bo_qua_dong_to_rong_khong_o_cuoi():
    """ĐỐI CHỨNG ÂM cho `_num("")=0` ở bước dò khe.

    Dữ liệu dạng này bị `validate_threshold_rows` chặn (dải mở không ở cuối),
    nhưng `warn_threshold_gaps` vẫn phải chịu được — câu "khe 0 – 10" là bịa.
    """
    MSGPRINTS.clear()
    rule_engine.warn_threshold_gaps(
        [_row(5, None, 100), _row(10, 20, 200)], "Cảnh báo khe hở")
    assert MSGPRINTS == [], MSGPRINTS


# ═══════════════════════════════════════════════════════════════════
# (4) ALRule._threshold_miss_message
# ═══════════════════════════════════════════════════════════════════
def test_miss_khong_bao_tren_dai_cao_nhat_khi_dai_cuoi_mo():
    """Dải cuối MỞ (+∞) ⇒ ⛔ giá trị nào "nằm trên dải cao nhất"."""
    message = _threshold_miss_message(
        OPEN_ROWS, 1000000000, "Độ dày kính")
    assert "trên dải cao nhất" not in message, message
    assert "kết thúc ở 0" not in message, message
    # Vẫn là câu người-đọc-được (⛔ rỗng, ⛔ mã kỹ thuật).
    assert message and "Độ dày kính" in message, message


def test_miss_bao_tren_dai_cao_nhat_khi_dai_cuoi_dong():
    """ĐỐI CHỨNG DƯƠNG: dải cuối ĐÓNG ⇒ vẫn nêu "trên dải cao nhất"."""
    rows = [_row(0, 10, 100), _row(10, 20, 200)]
    message = _threshold_miss_message(rows, 20.5, "Độ dày kính")
    assert "trên dải cao nhất" in message, message
    assert "20" in message, message


def test_miss_bo_qua_dong_to_rong_khi_do_khe():
    """Dòng `to` rỗng ⛔ được coi là kết thúc ở 0 khi dò khe."""
    # Dữ liệu (không hợp lệ qua validate) nhưng hàm phải chịu được.
    rows = [_row(5, None, 100), _row(10, 20, 200)]
    message = _threshold_miss_message(rows, 7, "Độ dày kính")
    assert "trống khoảng 0" not in message, message
    assert "0 – 10" not in message, message


def test_miss_khe_that_van_bao_khi_hai_dai_dong():
    """ĐỐI CHỨNG DƯƠNG của (4): khe thật giữa 2 dải đóng vẫn báo."""
    rows = [_row(0, 10, 100), _row(10.39, 20, 200)]
    message = _threshold_miss_message(rows, 10.2, "Độ dày kính")
    assert "trống khoảng" in message, message
    assert "10,39" in message, message


# ═══════════════════════════════════════════════════════════════════
# (5) ALRule.preview
# ═══════════════════════════════════════════════════════════════════
def test_preview_dai_mo_tra_khop_va_to_none():
    STUB.set_get_all("AL Variable Library", [])
    out = _rule(OPEN_ROWS).preview(25)
    assert out["success"] is True, out
    assert out["matched"] == {"kind": "range", "from": 10, "to": None,
                             "key": None}, out["matched"]
    assert out["result"] == {"value": 200}, out["result"]
    assert out["message"] == "", out["message"]
    assert out["rows"][-1]["to"] is None, out["rows"][-1]
    assert out["rows"][-1]["from"] == 10, out["rows"][-1]
    assert [row["is_match"] for row in out["rows"]] == [0, 1], out["rows"]


def test_preview_dai_dong_khop_dung_dong():
    """ĐỐI CHỨNG ÂM: giá trị trong dải đóng ⛔ bị tô sang dải mở."""
    STUB.set_get_all("AL Variable Library", [])
    out = _rule(OPEN_ROWS).preview(5)
    assert out["matched"] == {"kind": "range", "from": 0, "to": 10,
                             "key": None}, out["matched"]
    assert out["result"] == {"value": 100}, out
    assert [row["is_match"] for row in out["rows"]] == [1, 0], out["rows"]


def test_preview_gia_tri_0_voi_dai_mo_khong_khop():
    """ĐỐI CHỨNG ÂM cho bug `_num("")=0` trên màn Thử tra."""
    STUB.set_get_all("AL Variable Library", [])
    out = _rule([_row(10, None, 200)]).preview(0)
    assert out["matched"] is None, out["matched"]
    assert out["result"] is None, out
    assert out["rows"][0]["is_match"] == 0, out["rows"][0]
    assert "dải thấp nhất" in out["message"], out["message"]


def test_preview_gia_tri_rat_lon_khop_dai_mo():
    STUB.set_get_all("AL Variable Library", [])
    out = _rule([_row(0, 10, 100), _row(10, None, 200)]).preview(10 ** 12)
    assert out["matched"]["to"] is None, out["matched"]
    assert out["result"] == {"value": 200}, out
    assert out["message"] == "", out["message"]


# ═══════════════════════════════════════════════════════════════════
# (6) JSON — field `to_value` không còn bắt buộc
# ═══════════════════════════════════════════════════════════════════
def test_threshold_row_json_to_value_khong_bat_buoc():
    path = os.path.join(
        _REPO_ROOT, "alumglass", "al_formula_rules", "doctype",
        "al_rule_threshold_row", "al_rule_threshold_row.json")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    by_name = {field["fieldname"]: field for field in data["fields"]}
    to_field = by_name["to_value"]
    # Nhãn + mô tả GIỮ NGUYÊN (nhãn đã nói "bỏ trống = trở lên").
    assert to_field["label"] == "Đến (bỏ trống = trở lên)", to_field
    assert not to_field.get("reqd"), to_field
    # `Từ` vẫn bắt buộc.
    assert by_name["from_value"].get("reqd") == 1, by_name["from_value"]


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
