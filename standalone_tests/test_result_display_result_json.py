# -*- coding: utf-8 -*-
"""Test standalone cho `alumglass.api.get_result_display(..., result_json=...)`.

BỐI CẢNH (yêu cầu Owner 2026-11-21)
────────────────────────────────────
Dialog "Tham số BOM" mở lại phải dựng bảng kết quả từ **kết quả ĐANG NẰM TRÊN
DÒNG Quotation Item** (client đọc `frm.doc.items[i].al_bom_result`), ⛔ không
đọc lại DB — vì dòng có thể mang kết quả MỚI hơn bản đã lưu (vừa tính xong,
chưa bấm Lưu báo giá). Vì vậy API nhận thêm tham số tuỳ chọn `result_json`.
Ràng buộc:
  - có `result_json` ⇒ dựng display TỪ CHUỖI ĐÓ, khớp 100% với ca đọc từ DB
    cùng nội dung (cùng logic dựng bước / `lookup_facts` / severity);
  - JSON hỏng ⇒ CÂU người-đọc-được kèm lối xử lý (⛔ không 500, ⛔ không phơi
    traceback / thông điệp `json.loads` kỹ thuật);
  - không truyền ⇒ giữ NGUYÊN đường đọc DB cũ;
  - cổng quyền `read` trên Quotation cha vẫn phải chạy TRƯỚC mọi xử lý (tham
    số mới ⛔ không được là đường vòng bỏ kiểm quyền).

VÌ SAO ĐẶT Ở `standalone_tests/`
────────────────────────────────
`bench run-tests --app alumglass` os.walk toàn bộ package `alumglass/` (kể cả
`alumglass/tests/`) ⇒ một file stub `frappe` nằm trong package sẽ thay
`sys.modules["frappe"]` và phá cả lượt chạy test của site. Thư mục này nằm
NGOÀI package nên bench không collect (xem docstring
`standalone_tests/test_phase_b_fbmax.py`).

CÁCH CHẠY (không cần site):
    cd ~/myfrappe/apps/alumglass
    PYTHONPATH=/home/nxc/myfrappe/apps \\
        /home/nxc/myfrappe/env/bin/python standalone_tests/test_result_display_result_json.py
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

api = base.api

# Snapshot cost template của version pin — dùng để dựng label + công thức +
# trace của từng dòng cost template (nhánh `_get_cost_template_display`).
COST_SNAPSHOT = {
    "items": [
        {"line_code": "TONG_VL", "line_label": "Tổng vật liệu",
         "calc_formula": "VL_KINH + VL_NHOM", "cost_bucket": ""},
        {"line_code": "GIA_BAN", "line_label": "Giá bán",
         "calc_formula": "TONG_VL * (1 + PROFIT_MARGIN)", "cost_bucket": ""},
        {"line_code": "GIA_VAT", "line_label": "Giá có VAT",
         "calc_formula": "GIA_BAN * (1 + VAT_RATE)", "cost_bucket": ""},
    ]
}

# Kết quả engine trả về (đã chuẩn hoá) — nội dung dùng cho CẢ hai đường:
#   · đường DB:   al_bom_result của QI-DB
#   · đường tham số: result_json truyền vào khi gọi QI-ARG
RESULT_PAYLOAD = {
    "buckets": {"VL_KINH": 1000000.0, "VL_NHOM": 500000.0},
    "cost_template": {"TONG_VL": 1500000.0, "GIA_BAN": 2000000.0, "GIA_VAT": 2200000.0},
    "cost_template_trace": {"GIA_VAT": "GIA_BAN=2000000 * (1 + 0.1)"},
    "lines": [
        {
            "slug": "kinh_tren", "item_code": "KINH-01",
            "width": 2000, "height": 1000, "qty": 2,
            "unit_qty": 2, "total_qty": 4, "unit_price": 250000,
            "line_total": 1000000, "cost_bucket": "VL_KINH", "unit": "m2",
            "trace": "Rộng 2000 × Cao 1000",
        },
    ],
    "gia_vat": 2200000.0,
    "gia_ban": 2000000.0,
    "errors": {
        "bom_items": {"kinh_tren": "Kính vượt khổ tối đa"},
        "cost_template": {},
    },
}

# Nội dung KHÁC hẳn — dùng cho dòng KHÔNG truyền `result_json` để chứng minh
# nhánh đó vẫn đọc DB (⛔ không âm thầm lấy payload của tham số).
OTHER_PAYLOAD = {
    "buckets": {"VL_KINH": 1.0},
    "cost_template": {"GIA_BAN": 7.0, "GIA_VAT": 9.0},
    "lines": [],
    "gia_vat": 9.0,
    "gia_ban": 7.0,
    "errors": {},
}

_BOM_VARS = json.dumps({
    "W_mm": 2000, "H_mm": 1000, "VAT_RATE": 0.1, "PROFIT_MARGIN": 0.2,
    "extra_vars": {},
})


def _setup():
    """Dựng lại dữ liệu stub cho mỗi ca (không để ca trước rò sang ca sau)."""
    st = base._STUB
    st.get_all_rows = {}
    st.set_get_all("AL Slug Library", [
        {"slug": "kinh_tren", "label": "Kính trên"},
    ])
    st.set_get_all("AL Cost Bucket", [
        {"bucket_code": "VL_KINH", "bucket_name": "Vật liệu kính"},
    ])

    common = {"al_bom": "BOM-1", "al_bom_version": "ALBOMV-1", "al_bom_vars": _BOM_VARS}
    st.set_doc("Quotation Item", "QI-DB", dict(
        common, al_bom_result=json.dumps(RESULT_PAYLOAD, indent=2)))
    st.set_doc("Quotation Item", "QI-ARG", dict(
        common, al_bom_result=json.dumps(OTHER_PAYLOAD)))

    # `_get_cost_template_display` đọc snapshot version pin qua
    # `frappe.get_cached_value`; stub mặc định trả None ⇒ label/công thức rỗng
    # và ca "khớp 100%" sẽ so hai bên cùng rỗng (vô nghĩa). Cấp snapshot thật
    # để test có label + công thức + trace.
    st.get_cached_value = (
        lambda doctype, name=None, fieldname=None, *a, **k:
        json.dumps(COST_SNAPSHOT)
        if doctype == "AL BOM Version" and fieldname == "cost_template_snapshot"
        else None
    )

    # Cổng quyền: bỏ qua has_permission (stub không có) nhưng GHI LẠI lượt gọi
    # để ca riêng kiểm "tham số mới không được đi vòng kiểm quyền".
    calls = []
    api._require_quotation_item_permission = (
        lambda name, ptype="read": (calls.append((name, ptype)) or "QTN-1"))
    return calls


def _as_json(obj):
    """So sánh NGUYÊN nội dung — không phụ thuộc thứ tự key."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def test_result_json_khop_100_voi_duong_doc_db():
    """Display dựng từ `result_json` phải TRÙNG KHÍT bản đọc từ DB cùng nội dung."""
    _setup()
    from_db = api.get_result_display("QI-DB")
    from_arg = api.get_result_display("QI-ARG", result_json=json.dumps(RESULT_PAYLOAD))

    assert _as_json(from_db) == _as_json(from_arg), (
        "lệch giữa đường DB và đường result_json:\nDB : %s\nARG: %s"
        % (_as_json(from_db), _as_json(from_arg))
    )
    # Số liệu trong display là của PAYLOAD (⛔ không phải OTHER_PAYLOAD trong DB)
    assert from_arg["summary"]["gia_vat"] == 2200000.0, from_arg["summary"]
    assert from_arg["summary"]["gia_ban"] == 2000000.0, from_arg["summary"]
    assert from_arg["summary"]["line_count"] == 1, from_arg["summary"]
    assert from_arg["summary"]["calculated"] is True, from_arg["summary"]
    # Label + công thức + trace lấy từ snapshot (cùng logic, không phải bản rút gọn)
    vat_line = [r for r in from_arg["cost_template"] if r["line_code"] == "GIA_VAT"][0]
    assert vat_line["line_label"] == "Giá có VAT", vat_line
    assert vat_line["calc_formula"] == "GIA_BAN * (1 + VAT_RATE)", vat_line
    assert vat_line["trace"] == "GIA_BAN=2000000 * (1 + 0.1)", vat_line
    # Cảnh báo (severity) đi kèm đường tham số y như đường DB
    assert from_arg["errors"] == RESULT_PAYLOAD["errors"], from_arg["errors"]


def test_result_json_rong_thi_giu_duong_doc_db():
    """Không truyền `result_json` ⇒ đọc DB đúng như trước (không đổi hành vi)."""
    _setup()
    from_db = api.get_result_display("QI-ARG")
    assert _as_json(from_db) == _as_json(api.get_result_display("QI-ARG", result_json=None))
    assert from_db["summary"]["gia_vat"] == 9.0, from_db["summary"]
    assert from_db["summary"]["gia_ban"] == 7.0, from_db["summary"]
    assert from_db["summary"]["line_count"] == 0, from_db["summary"]


def test_result_json_nhan_ca_dict():
    """Frappe có thể tự parse tham số thành dict ⇒ vẫn dựng đúng như chuỗi JSON."""
    _setup()
    from_dict = api.get_result_display("QI-ARG", result_json=RESULT_PAYLOAD)
    from_str = api.get_result_display("QI-ARG", result_json=json.dumps(RESULT_PAYLOAD))
    assert _as_json(from_dict) == _as_json(from_str)
    assert from_dict["summary"]["gia_vat"] == 2200000.0, from_dict["summary"]


def _assert_readable_error(result_json):
    try:
        api.get_result_display("QI-DB", result_json=result_json)
    except Exception as exc:  # noqa: BLE001 — stub `frappe.throw` ném Exception
        message = str(exc)
    else:
        raise AssertionError("JSON hỏng phải bị chặn, ⛔ không trả display rỗng")

    assert "bị hỏng" in message, message
    # UX1 (2026-11-21): nói rõ KHÔNG phải lỗi do người dùng nhập sai.
    assert "không phải do bạn nhập sai" in message, message
    assert "Preview tính giá" in message, "câu lỗi phải kèm LỐI XỬ LÝ: %s" % message
    assert "Traceback" not in message, message
    # ⛔ Không phơi thông điệp kỹ thuật của json.loads
    for technical in ("Expecting value", "Expecting property name", "line 1 column",
                      "json.decoder", "JSONDecodeError"):
        assert technical not in message, "lộ chi tiết kỹ thuật %r: %s" % (technical, message)


def test_result_json_hong_tra_loi_nguoi_doc_duoc():
    """Chuỗi JSON hỏng ⇒ câu người-đọc-được, ⛔ không 500 / traceback."""
    _setup()
    _assert_readable_error("{khong-phai-json")
    _assert_readable_error('{"buckets": ')


def test_result_json_khong_phai_object_tra_loi_nguoi_doc_duoc():
    """JSON hợp lệ nhưng KHÔNG phải object (mảng/số) ⇒ cùng câu lỗi dễ hiểu."""
    _setup()
    _assert_readable_error("[1, 2, 3]")
    _assert_readable_error("123")


def test_result_json_khong_di_vong_cong_quyen():
    """Tham số mới ⛔ KHÔNG được bỏ qua cổng `read` trên Quotation cha."""
    calls = _setup()
    api.get_result_display("QI-ARG", result_json=json.dumps(RESULT_PAYLOAD))
    assert calls == [("QI-ARG", "read")], calls


def test_calculate_bom_response_co_gia_vat_gia_ban():
    """Response `calculate_bom` phải mang `gia_vat`/`gia_ban` của MÁY CHỦ.

    Client (`ItemParamDialog._write_result_to_row`) ghi `al_gia_vat` /
    `al_gia_ban` / `rate` xuống dòng từ 2 khoá này — đó là ĐÚNG giá trị
    `b7_save_results` ghi DB (tôn trọng cờ `is_final_price` / `is_pre_vat_price`).
    Thiếu khoá ⇒ client rơi về `cost_template.GIA_VAT`/`GIA_BAN` và có thể ghi
    SAI khi template đánh dấu dòng giá cuối ở line_code khác.
    """
    orch = base.BomOrchestrator.__new__(base.BomOrchestrator)
    orch.buckets = {}
    orch.cost_result = {"GIA_BAN": 2000000.0, "GIA_VAT": 2200000.0}
    orch.bom_result = []
    orch.gia_vat = 2200000.0
    # Snapshot rỗng ⇒ `_resolve_pre_vat_price` fallback dòng GIA_BAN (đường cũ).
    orch._cost_template_snapshot_items = []
    orch.bom_engine_errors = {}
    orch.cost_engine_errors = {}

    resp = orch._build_response()
    assert resp["gia_vat"] == 2200000.0, resp
    assert resp["gia_ban"] == 2000000.0, resp

    # Có cờ `is_pre_vat_price` ⇒ lấy theo dòng được đánh dấu, ⛔ không hardcode
    # GIA_BAN — client nhận đúng giá trị máy chủ đã ghi xuống `al_gia_ban`.
    orch.cost_result = {"GIA_BAN": 2000000.0, "GIA_CHUA_VAT": 1800000.0}
    orch._cost_template_snapshot_items = [
        {"line_code": "GIA_CHUA_VAT", "is_pre_vat_price": 1},
    ]
    assert orch._build_response()["gia_ban"] == 1800000.0


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
