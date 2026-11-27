import json
import frappe
from frappe import _

# Registry field công thức (thay FORMULA_DOCTYPE_REGISTRY hardcode trong JS).
# DEV3 tiêu thụ qua `frappe.call("alumglass.api.get_formula_fields", ...)`.
# Import ở đây để endpoint có mặt trên module `alumglass.api` như API khác.
from alumglass.api.formula_registry import get_formula_fields  # noqa: F401
from alumglass.al_formula_rules import rule_input
from alumglass.variable_sources.field_provenance import (
    display_label,
    display_unit,
)


@frappe.whitelist()
def calculate_bom(quotation_item_name):
    """Tính BOM cho 1 dòng báo giá - trả về GIA_VAT + chi tiết.

    Đây là API chính được gọi từ nút "Tính giá" trên Quotation Item.

    F1 — cổng `read` trên Quotation cha: chặn người ngoài cuộc gọi API (mục
    tiêu thật của F1), đồng thời vẫn cho `AL BOM Manager` làm việc vì role này
    có `read` trên Quotation (xem install_roles.py). Đường ghi kết quả là
    `frappe.db.set_value()` trong `BomOrchestrator.b7_save_results`
    (engine/bom_orchestrator.py) — hàm này KHÔNG kiểm quyền của Frappe, nên
    cổng `read` ở API là chốt QUYỀN duy nhất; vì vậy KHÔNG siết lên `write` và
    KHÔNG dựa vào tầng dưới. Kiểm TRƯỚC khi load doc.
    F-docstatus — chốt `assert_quotation_item_editable` (engine) đặt NGAY SAU
    cổng quyền: chặn tính giá lên báo giá ĐÃ SUBMIT / ĐÃ HUỶ trước mọi tính
    toán. `frappe.db.set_value()` bỏ qua cơ chế chặn chứng từ đã submit của
    Frappe nên phải tự chốt; chốt thật nằm ở `b7_save_results` (sát lệnh ghi).

    P2 (async): đếm số dòng BOM từ bom_set_snapshot của version pin:
      - ≤ ASYNC_BOM_THRESHOLD → chạy ĐỒNG BỘ (giữ nguyên hành vi cũ 100%),
        trả về response chuẩn hoá {buckets, cost_template, lines}.
      - > ngưỡng → `frappe.enqueue(queue="long", timeout=600)` + trả về
        {async: True, job_id, status: "Queued", message}. Client nhận kết quả
        qua realtime event "alumglass_bom_calc_done".
    """
    _require_quotation_item_permission(quotation_item_name, ptype="read")

    # F-docstatus — chốt SỚM (trước mọi tính toán): không bắt người dùng chờ tính
    # xong mới báo lỗi, và không hiện số liệu sẽ không được lưu. Chốt thật vẫn
    # nằm ở b7_save_results (sát lệnh ghi) — chỗ này chỉ là lưới trước cho UX.
    from alumglass.engine.bom_orchestrator import assert_quotation_item_editable
    assert_quotation_item_editable(quotation_item_name)

    qi = frappe.get_doc("Quotation Item", quotation_item_name)

    line_count = _estimate_bom_line_count(qi)
    threshold = _get_async_threshold()

    if line_count <= threshold:
        # HÀNH VI CŨ — giữ nguyên 100% (BOM nhỏ/vừa), chỉ chuẩn hoá response (C4)
        from alumglass.engine.bom_orchestrator import BomOrchestrator
        result = BomOrchestrator(quotation_item_name).run()
        return _normalize_bom_response(result)

    # HÀNH VI MỚI — BOM lớn, chạy background
    return _enqueue_bom_calculation(qi)


# ═══════════════════════════════════════════════════════════════════════════
# PREVIEW tính giá — ⛔ KHÔNG GHI DB (Owner chốt 2026-11-21, phase 1)
# ═══════════════════════════════════════════════════════════════════════════
# `calculate_bom` ở trên là đường "tính + LƯU" (B7 ghi 4 field + tổng cha +
# commit). `preview_bom` dùng CHUNG engine nhưng `persist=False`: B0→B6 chạy y
# hệt, B7 bị bỏ ⇒ kết quả chỉ nằm trong response (và trên dòng phía client tới
# khi người dùng bấm Lưu báo giá). ⛔ Không set_value, ⛔ không commit, ⛔ không
# tạo Version/Comment, ⛔ không ghi status/job id — kể cả nhánh BOM lớn (mất kết
# quả thì bấm tính lại, Owner chốt).

#: Field của dòng Quotation Item client được phép gửi lên cho preview.
#: ⛔ Mọi field khác (currency, price_list, customer, company…) bị BỎ — bối
#: cảnh giá luôn đọc từ Quotation cha trong DB, nếu không client đổi được
#: tham số để xem giá của bảng giá/khách hàng khác.
_PREVIEW_ALLOWED_ROW_FIELDS = (
    "al_bom", "al_bom_version", "al_bom_vars",
    "item_code", "item_name", "qty", "uom", "stock_uom",
)

#: Khoá BỐI CẢNH GIÁ chỉ dành cho MÁY CHỦ (`alumglass.api.preview_guard` lấy
#: từ chính doc báo giá đang lưu rồi truyền vào engine). Client gửi lên thì
#: ⛔ BỎ TUYỆT ĐỐI: nếu lọt, client đổi được tiền tệ/bảng giá/khách hàng để
#: xem giá của bối cảnh khác (và làm giá lưu khác giá engine tính).
_SERVER_CONTEXT_PARAM_KEYS = (
    "_currency", "_price_list", "_company",
    "_conversion_rate", "_plc_conversion_rate", "_customer",
)


@frappe.whitelist()
def preview_bom(quotation_item_name=None, params=None):
    """Tính thử BOM cho 1 dòng báo giá — ⛔ KHÔNG ghi DB.

    Args:
        quotation_item_name: tên dòng ĐÃ LƯU; rỗng/`new-…` = dòng mới (chưa
            có trong DB).
        params: JSON (chuỗi hoặc dict) tham số người dùng đang thấy trên
            dialog: `al_bom`, `al_bom_version`, `al_bom_vars`, `item_code`,
            `item_name`, `qty`, `uom`, và với dòng mới là `parent` /
            `parenttype`.

    Trả về:
        - đồng bộ: như `calculate_bom` (buckets/cost_template/lines/errors/
          gia_vat/gia_ban) + `calc_meta` {params_hash, computed_at, preview}.
        - BOM lớn: {async: True, job_id, status, message} — kết quả về qua
          realtime CHỈ cho user đã enqueue; ⛔ không field nào được ghi.

    Thứ tự chốt (theo yêu cầu Owner):
        (a) dòng cũ ⇒ `read` trên Quotation cha + chặn cha đã submit/huỷ;
        (b) dòng mới ⇒ cha thật: `read` trên cha; cha `new-…`: `create` trên
            Quotation + docstatus 0;
        (c) mã `al_bom`/`al_bom_version` CLIENT GỬI LÊN ⇒ phải có quyền `read`
            trên chính chứng từ đó (chặn dùng preview để dò BOM ngoài quyền).
    """
    params = _parse_preview_params(params)
    row_name = (quotation_item_name or "").strip()
    is_existing = bool(row_name) and not row_name.startswith("new-")

    if is_existing:
        parent = _require_quotation_item_permission(row_name, ptype="read")
        from alumglass.engine.bom_orchestrator import assert_quotation_item_editable
        assert_quotation_item_editable(row_name)
        row_values = _preview_row_values_from_db(row_name)
    else:
        parent = (params.get("parent") or "").strip()
        _require_quotation_permission(parent, ptype="read")
        from alumglass.engine.bom_orchestrator import assert_parent_editable
        assert_parent_editable(parent)
        row_values = {}

    # Gộp: giá trị đã lưu (dòng cũ) ← params client gửi (chỉ field cho phép).
    engine_params = dict(row_values)
    for field in _PREVIEW_ALLOWED_ROW_FIELDS:
        if field in params and params[field] is not None:
            engine_params[field] = params[field]
    engine_params["parent"] = parent
    engine_params["parenttype"] = "Quotation"
    engine_params["name"] = row_name or "new-preview-item"

    # (c) Quyền trên BOM/Version — CHỈ kiểm mã CLIENT gửi (mã đọc từ DB của
    # dòng đã lưu vốn đã được bảo vệ bởi quyền `read` trên Quotation, và kiểm
    # thêm sẽ chặn oan các vai trò đang dùng `calculate_bom` hôm nay).
    if "al_bom" in params:
        _require_doc_read_permission(
            "AL BOM", engine_params.get("al_bom"),
            " nên không xem trước được giá của mã BOM này")
    if "al_bom_version" in params:
        _require_doc_read_permission(
            "AL BOM Version", engine_params.get("al_bom_version"),
            " nên không xem trước được giá của phiên bản BOM này")

    line_count = _estimate_bom_line_count(engine_params)
    threshold = _get_async_threshold()

    if line_count <= threshold:
        from alumglass.engine.bom_orchestrator import BomOrchestrator
        result = BomOrchestrator(
            quotation_item_name=(row_name if is_existing else None),
            params=engine_params,
            persist=False,
        ).run()
        return _normalize_bom_response(result)

    return _enqueue_preview(engine_params, line_count)


def _parse_preview_params(params):
    """Chuẩn hoá `params` của `preview_bom` → dict chỉ gồm field cho phép.

    Chấp nhận chuỗi JSON (client gửi qua `frappe.call`) lẫn dict. JSON hỏng ⇒
    câu người-đọc-được (ValidationError = 417), ⛔ không 500, ⛔ không lộ
    thông điệp `json.loads`.
    """
    if not params:
        return {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except (ValueError, TypeError):
            frappe.throw(
                _("Tham số tính giá bị hỏng nên chưa tính được. Đóng bảng tham số rồi mở lại và bấm \"Preview tính giá\"."),
                frappe.ValidationError,
            )
    if not isinstance(params, dict):
        frappe.throw(
            _("Tham số tính giá không hợp lệ. Đóng bảng tham số rồi mở lại và bấm \"Preview tính giá\"."),
            frappe.ValidationError,
        )
    out = {k: v for k, v in params.items()
           if k in _PREVIEW_ALLOWED_ROW_FIELDS or k in ("parent", "parenttype")}
    # Lọc TƯỜNG MINH lần nữa các khoá bối cảnh giá của máy chủ: allowlist ở
    # trên đã loại chúng, nhưng nếu sau này ai thêm khoá `_…` vào allowlist
    # thì đây là chốt chặn cuối (⛔ client không được đổi tiền tệ/bảng giá).
    for key in _SERVER_CONTEXT_PARAM_KEYS:
        out.pop(key, None)
    # `al_bom_vars` client gửi dạng chuỗi JSON; nhận cả dict (form gửi object).
    bom_vars = out.get("al_bom_vars")
    if isinstance(bom_vars, dict):
        out["al_bom_vars"] = json.dumps(bom_vars, sort_keys=True)
    return out


def _bom_vars_dict(raw):
    """`al_bom_vars` (chuỗi JSON / dict) → dict; rỗng hoặc hỏng ⇒ `{}`.

    Dùng cho đường phase 1.5 (params client gửi = trạng thái dialog). Cùng
    quy tắc chịu lỗi với đường đọc `al_bom_vars` trong DB và với engine B1:
    JSON hỏng ⇒ coi như "chưa chọn gì" (dialog vẫn mở được), ⛔ không 500.
    """
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _has_permission_no_throw(doctype, ptype="read", doc=None):
    """Hỏi quyền mà KHÔNG ném khi thiếu quyền — chạy được cả Frappe v13 và v14+.

    `frappe.has_permission` đổi TÊN kwarg kiểm-soát-ném giữa các bản Frappe
    (v13 một tên, v14/v15/v16 tên khác — bản v14+ là `throw`). Truyền tên
    của bản này lên bản kia là `TypeError` NGAY trên site thật, ⛔ không phải
    chỉ mất tính năng — đã xảy ra 2026-11-23: dialog "Tham số BOM" 500 trên
    Frappe v16 vì lời gọi còn truyền kwarg của bản v13.

    Cách an toàn: ⛔ KHÔNG truyền kwarg kiểm-soát-ném nào cả. Mặc định của
    MỌI bản Frappe đều là "trả False khi thiếu quyền", nên bỏ hẳn kwarg là
    tương đương về hành vi mà không phụ thuộc tên gọi.

    `TypeError` được ném lại có chủ đích: đó là lỗi LẬP TRÌNH (sai chữ ký),
    phải nổi lên để test bắt — ⛔ không nuốt thành "không có quyền".
    `DoesNotExistError` cũng ném lại để người gọi còn phân biệt "mã không
    tồn tại" với "thiếu quyền" mà báo đúng câu.

    Ca hồi quy: `standalone_tests/test_preview_reads_dialog_state.py` (18a-18d).
    """
    try:
        return bool(frappe.has_permission(doctype, ptype, doc))
    except frappe.DoesNotExistError:
        raise
    except TypeError:
        raise
    except Exception:
        # Bản Frappe lỡ ném lỗi quyền thay vì trả False ⇒ coi như KHÔNG có
        # quyền (chặn lại) — ⛔ để thành 500 trên màn hình người dùng.
        return False


def _require_quotation_permission(parent, ptype="read"):
    """Cổng quyền cho DÒNG MỚI (chưa có dòng trong DB, chỉ có tên cha).

    - Cha đã lưu ⇒ hỏi quyền `ptype` trên chính báo giá đó.
    - Cha `new-…` (báo giá chưa lưu) ⇒ chưa tồn tại để phân quyền, chỉ cần
      người dùng được TẠO báo giá. ⛔ Không cho qua khi thiếu quyền `create`.
    """
    parent = (parent or "").strip()
    if not parent:
        frappe.throw(
            _("Chưa xác định được báo giá chứa dòng cần tính giá. Mở lại báo giá rồi thử lại."),
            frappe.ValidationError,
        )
    if parent.startswith("new-"):
        if not _has_permission_no_throw("Quotation", ptype="create"):
            frappe.throw(_("Bạn không có quyền tạo báo giá nên không tính giá được"),
                         frappe.PermissionError)
        return parent
    if not _has_permission_no_throw("Quotation", ptype=ptype, doc=parent):
        frappe.throw(_("Bạn không có quyền truy cập báo giá này"), frappe.PermissionError)
    return parent


def _require_doc_read_permission(doctype, name, consequence=""):
    """Chặn user dùng preview để dò giá của BOM/Version NGOÀI quyền đọc.

    Khác `_require_doctype_read_permission` (kiểm quyền cấp DOCTYPE): ở đây
    kiểm quyền trên ĐÚNG bản ghi client gửi lên — user có quyền đọc module
    nhưng bị giới hạn theo bản ghi thì vẫn phải bị chặn.
    """
    if not name:
        return
    try:
        allowed = _has_permission_no_throw(doctype, "read", name)
    except frappe.DoesNotExistError:
        # Mã client gửi KHÔNG tồn tại ⇒ câu người-đọc-được (⛔ 404 tiếng Anh).
        frappe.throw(
            _("Không tìm thấy {0} '{1}' để tính giá. Chọn lại rồi thử lại.").format(_(doctype), name),
            frappe.ValidationError,
        )
        return
    if not allowed:
        frappe.throw(
            _("Bạn không có quyền xem {0} '{1}'{2}").format(_(doctype), name, consequence),
            frappe.PermissionError,
        )


def _preview_row_values_from_db(quotation_item_name):
    """Đọc các field engine cần từ dòng ĐÃ LƯU (giá trị nền cho preview).

    `params` client gửi sẽ phủ lên các field này; field nào client không gửi
    thì giữ giá trị đang lưu. Chỉ đọc — khái niệm "preview" không được ghi.
    """
    fields = list(_PREVIEW_ALLOWED_ROW_FIELDS)
    values = frappe.db.get_value("Quotation Item", quotation_item_name, fields) or []
    return {field: value for field, value in zip(fields, values)
            if value is not None}


def _enqueue_preview(engine_params, line_count):
    """Xếp preview BOM lớn vào queue long — ⛔ KHÔNG ghi DB (kể cả status/job id).

    Hệ quả Owner đã chấp nhận: đóng tab giữa chừng ⇒ mất kết quả, mở lại bấm
    tính lại. Đổi lại, ⛔ không còn dòng nào kẹt "Queued" vì worker chết.
    """
    job_id = "albom-preview-%s-%s" % (
        engine_params.get("name") or "new", frappe.generate_hash(length=8))

    try:
        # ⛔ truyền `job_name=`: Frappe v16 có thể đã bỏ tham số này, rơi vào
        # `**kwargs` ⇒ chuyển tiếp vào hàm job ⇒ TypeError ⇒ MỌI preview BOM
        # lớn Failed. Chỉ dùng `job_id` (có ở cả v14 lẫn v16).
        frappe.enqueue(
            method="alumglass.api._run_preview_job",
            queue="long",
            timeout=600,
            params=engine_params,
            job_id=job_id,
            user=frappe.session.user,
        )
    except Exception:
        frappe.log_error(
            title="AlumGlass enqueue preview BOM failed: %s" % job_id,
            message=frappe.get_traceback(),
        )
        frappe.throw(_(
            "Không xếp được việc tính thử vào hàng đợi — vui lòng thử lại, "
            "nếu vẫn lỗi hãy báo quản trị."
        ))

    return {
        "async": True,
        "job_id": job_id,
        "status": "Queued",
        "message": _(
            "BOM có {0} dòng — đang tính trong nền, kết quả sẽ hiện tự động khi "
            "xong. Kết quả chỉ hiện trong phiên này và CHƯA được lưu."
        ).format(line_count),
    }


def _run_preview_job(params, job_id, user):
    """Chạy preview trong RQ worker (queue long) — KHÔNG whitelist, ⛔ KHÔNG ghi DB.

    `frappe.set_user(user)` bắt buộc: worker mặc định chạy bằng Administrator
    ⇒ bỏ qua toàn bộ role-based access. Kết quả publish CHỈ cho user đã
    enqueue (⛔ broadcast) — người khác không đoán được job_id để nghe lén.
    """
    try:
        frappe.set_user(user)
        from alumglass.engine.bom_orchestrator import BomOrchestrator
        result = BomOrchestrator(
            quotation_item_name=(
                params.get("name") if not str(params.get("name") or "").startswith("new-") else None
            ),
            params=params,
            persist=False,
        ).run()
    except Exception as exc:
        error_trace = frappe.get_traceback()
        user_message = _bom_error_message(exc)
        frappe.log_error(
            title="AlumGlass async preview failed: %s" % job_id,
            message=error_trace,
        )
        frappe.publish_realtime(
            event="alumglass_bom_calc_done",
            message={
                "job_id": job_id,
                "qi_name": params.get("name") or "",
                "status": "Failed",
                "error": user_message,
                "preview": True,
            },
            user=user,
        )
        return

    normalized = _normalize_bom_response(result)
    frappe.publish_realtime(
        event="alumglass_bom_calc_done",
        message={
            "job_id": job_id,
            "qi_name": params.get("name") or "",
            "status": "Success",
            "result": normalized,
            "params_hash": (normalized.get("calc_meta") or {}).get("params_hash"),
            "preview": True,
        },
        user=user,
    )


def _normalize_bom_response(result):
    """C4 — Chuẩn hoá response sync: luôn đủ 3 key dialog cần.

    Client tự chọn key động (buckets / cost_template / lines) — chỉ đảm bảo
    key luôn tồn tại để UI không gãy khi engine trả thiếu field.

    F2 — trường `errors` giữ NGUYÊN hình dạng engine trả về
    ({bom_items: {...}, cost_template: {...}}) — DEV-E đọc đúng hình dạng này.
    Chỉ setdefault khi engine KHÔNG trả key, để client khỏi phải tự kiểm null.
    `BomOrchestrator._build_response()` trả `errors` cùng `gia_vat`/`gia_ban`
    (giá máy chủ đã ghi xuống dòng ở `b7_save_results`); key thiếu (engine bản
    cũ) ⇒ client tự rơi về `cost_template.GIA_BAN`/`GIA_VAT`.
    """
    result = dict(result or {})
    result.setdefault("buckets", {})
    result.setdefault("cost_template", {})
    result.setdefault("lines", [])
    result.setdefault("errors", {})
    return result


def _require_quotation_item_permission(quotation_item_name, ptype="read"):
    """F1/D1 — Chặn user không có quyền trên Quotation cha của dòng báo giá.

    `frappe.get_doc("Quotation Item", ...)` KHÔNG kiểm quyền, mà Quotation Item
    là child table nên kiểm quyền trực tiếp trên nó vô nghĩa — phải leo lên
    Quotation cha rồi hỏi `frappe.has_permission(doctype, ptype, doc=parent)`
    (doc truyền dạng tên chuỗi được — xem frappe/permissions.py:127-130).
    Administrator / System Manager đi qua bình thường — has_permission tự cho.

    Trả về tên Quotation cha để caller dùng lại nếu cần.
    """
    parent = frappe.db.get_value("Quotation Item", quotation_item_name, "parent")
    if not parent:
        frappe.throw(
            _("Không tìm thấy dòng báo giá {0}").format(quotation_item_name),
            frappe.DoesNotExistError,
        )
    if not frappe.has_permission("Quotation", ptype=ptype, doc=parent):
        frappe.throw(_("Bạn không có quyền truy cập báo giá này"), frappe.PermissionError)
    return parent


def _require_doctype_read_permission(doctype, consequence=""):
    """F1 — Chặn user không có quyền ĐỌC `doctype` gọi API trả dữ liệu của nó.

    Dùng cho các endpoint nhận tham số trỏ thẳng vào 1 chứng từ (BOM, Cost
    Template, Slug Library...) mà trước đây ai đã đăng nhập cũng gọi được.
    `consequence` là mệnh đề nói rõ vì sao bị chặn (khớp văn phong thông báo
    quyền đã có trong app — xem api/excel_io.py) để người dùng biết đường xử lý.
    """
    if not doctype:
        return
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("Bạn không có quyền xem {0}{1}").format(_(doctype), consequence))


def _bom_error_message(exc):
    """D2 — Đổi exception thành MỘT CÂU tiếng Việt người-đọc-được.

    ⛔ KHÔNG bao giờ trả stack trace / tên class / mã lỗi ra UI. Stack vẫn được
    ghi vào `frappe.log_error` ở chỗ gọi để còn chẩn đoán (luật User-Delight:
    lỗi phải kèm hành động, không phơi mã kỹ thuật).
    """
    # 1. Chia cho 0 — lỗi công thức hay gặp nhất, phải nói rõ đường sửa.
    try:
        from formula_builder.formula_utils.errors import FormulaZeroDivisionError
    except Exception:
        FormulaZeroDivisionError = None
    if FormulaZeroDivisionError and isinstance(exc, FormulaZeroDivisionError):
        return _("Công thức chia cho 0 — kiểm tra lại kích thước/số lượng đầu vào (W, H, số cánh…).")

    # 2. Lỗi nghiệp vụ do frappe.throw(...) — thông điệp đã là câu tiếng Việt
    #    người đọc được, dùng luôn (cắt bớt nếu lỡ dài).
    if isinstance(exc, frappe.ValidationError):
        message = str(exc).strip()
        if message:
            return message[:300]

    # 3. Còn lại: câu chung, ⛔ không lộ chi tiết kỹ thuật.
    return _("Tính giá thất bại, vui lòng thử lại hoặc báo quản trị.")


def _estimate_bom_line_count(qi):
    """P2 — Đếm nhanh số dòng BOM từ bom_set_snapshot của version pin.

    `qi` là doc Quotation Item HOẶC dict params của preview (chỉ cần `.get`
    `al_bom`/`al_bom_version`) — nhờ vậy đường preview đếm được TRƯỚC khi
    tính mà ⛔ không phải đọc/ghi dòng nào.

    KHÔNG load BomOrchestrator chỉ để đếm (tránh lãng phí). Version chưa pin
    → đếm 0 → chạy sync. Không parse được → đếm 0 (an toàn, sync).
    """
    bom_version = qi.get("al_bom_version")
    if not bom_version and qi.get("al_bom"):
        # `qi` ở đường preview là DICT THUẦN (`engine_params`) — chỉ có `.get`,
        # ⛔ không có truy cập thuộc tính. Dùng `qi.al_bom` ở đây ném
        # AttributeError ⇒ preview 500 đúng với dòng có `al_bom` mà chưa pin
        # `al_bom_version` (ca 2026-11-23).
        bom_version = frappe.db.get_value("AL BOM", qi.get("al_bom"), "current_version")
    if not bom_version:
        return 0
    snapshot_raw = frappe.get_cached_value(
        "AL BOM Version", bom_version, "bom_set_snapshot"
    )
    if not snapshot_raw:
        return 0
    try:
        data = json.loads(snapshot_raw) if isinstance(snapshot_raw, str) else snapshot_raw
        items = data.get("bom_items", data.get("items", [])) or []
        return len(items)
    except (ValueError, TypeError):
        return 0


def _get_async_threshold():
    """P2 — Đọc ASYNC_BOM_THRESHOLD (Formula Global Variable). Fallback 150."""
    value = frappe.db.get_value(
        "Formula Global Variable", "ASYNC_BOM_THRESHOLD", "constant_value"
    )
    try:
        return int(value)
    except (TypeError, ValueError):
        return 150


def _enqueue_bom_calculation(qi):
    """P2 — Enqueue BOM lớn sang queue long, trả về job_id cho client."""
    job_id = "albom-%s-%s" % (qi.name, frappe.generate_hash(length=8))

    frappe.db.set_value(
        "Quotation Item", qi.name,
        {
            "al_calc_status": "Queued",
            "al_calc_job_id": job_id,
            "al_calc_error": "",
        },
        update_modified=False,
    )
    frappe.db.commit()

    # D3 — enqueue PHẢI nằm trong try: Redis/worker chết ⇒ enqueue ném lỗi, nếu
    # để ngoài try thì dòng báo giá kẹt "Queued" vĩnh viễn, `al_calc_error` rỗng
    # và người dùng không có đường xử lý.
    try:
        # ⛔ truyền `job_name=`: Frappe v16 có thể đã bỏ tham số này, rơi vào
        # `**kwargs` ⇒ chuyển tiếp vào hàm job ⇒ TypeError ⇒ mọi lượt tính BOM
        # lớn Failed. Chỉ dùng `job_id` (có ở cả v14 lẫn v16).
        frappe.enqueue(
            method="alumglass.api._run_bom_calculation_job",
            queue="long",
            timeout=600,  # 10 phút — đủ cho BOM rất lớn
            qi_name=qi.name,
            job_id=job_id,
            user=frappe.session.user,
        )
    except Exception:
        error_trace = frappe.get_traceback()
        message = _(
            "Không xếp được việc tính giá vào hàng đợi — vui lòng thử lại, "
            "nếu vẫn lỗi hãy báo quản trị."
        )
        frappe.db.set_value(
            "Quotation Item", qi.name,
            {"al_calc_status": "Failed", "al_calc_error": message},
            update_modified=False,
        )
        frappe.db.commit()
        frappe.log_error(
            title="AlumGlass enqueue BOM calc failed: %s" % qi.name,
            message=error_trace,
        )
        frappe.throw(message)

    return {
        "async": True,
        "job_id": job_id,
        "status": "Queued",
        "message": _(
            "BOM có {0} dòng — đang tính trong nền, kết quả sẽ hiện tự động khi xong."
        ).format(_estimate_bom_line_count(qi)),
    }


def _run_bom_calculation_job(qi_name, job_id, user):
    """P2 — Chạy trong RQ worker (queue long). KHÔNG whitelist.

    Bắt buộc `frappe.set_user(user)` trước khi gọi BomOrchestrator — nếu không
    job chạy với quyền Administrator mặc định của worker, bỏ qua toàn bộ
    role-based access. Set status + commit TRƯỚC khi publish realtime.
    set_user nằm TRONG try để nếu user không hợp lệ → item chuyển Failed
    (không kẹt mãi ở Queued).
    """
    try:
        frappe.set_user(user)

        frappe.db.set_value(
            "Quotation Item", qi_name, "al_calc_status", "Running",
            update_modified=False,
        )
        frappe.db.commit()

        from alumglass.engine.bom_orchestrator import BomOrchestrator
        result = BomOrchestrator(qi_name).run()

        frappe.db.set_value(
            "Quotation Item", qi_name, "al_calc_status", "Success",
            update_modified=False,
        )
        frappe.db.commit()
    except Exception as exc:
        error_trace = frappe.get_traceback()
        # D2 — chỉ ghi CÂU tiếng Việt ngắn vào field hiển thị cho người dùng;
        # stack trace giữ nguyên trong frappe.log_error bên dưới.
        user_message = _bom_error_message(exc)
        frappe.db.set_value(
            "Quotation Item", qi_name,
            {"al_calc_status": "Failed", "al_calc_error": user_message},
            update_modified=False,
        )
        frappe.db.commit()
        frappe.log_error(
            title="AlumGlass async BOM calc failed: %s" % qi_name,
            message=error_trace,
        )
        frappe.publish_realtime(
            event="alumglass_bom_calc_done",
            message={
                "job_id": job_id,
                "qi_name": qi_name,
                "status": "Failed",
                "error": user_message,
            },
            user=user,
        )
        return

    frappe.publish_realtime(
        event="alumglass_bom_calc_done",
        message={
            "job_id": job_id,
            "qi_name": qi_name,
            "status": "Success",
            "result": _normalize_bom_response(result),
        },
        user=user,
    )


@frappe.whitelist()
def preview_cost_template(template_code, inputs_json):
    """Xem trước kết quả Cost Template với inputs giả định."""
    # F1 — preview trả KẾT QUẢ công thức (giá) nên phải có quyền đọc template.
    _require_doctype_read_permission(
        "AL Cost Template", " nên không xem trước được công thức giá")
    from alumglass.al_bom_engine.doctype.al_cost_template.al_cost_template import preview_cost_template as _preview
    return _preview(template_code, inputs_json)


@frappe.whitelist()
def get_slug_info(slug):
    """Lấy thông tin Slug Library."""
    # F1 — dữ liệu trả về là của AL Slug Library ⇒ kiểm quyền đọc chính nó.
    _require_doctype_read_permission(
        "AL Slug Library", " nên không tra được thông tin slug")
    from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import get_slug_info as _get
    return _get(slug)


@frappe.whitelist()
def resolve_item_rule(rule_code, input_value):
    """Tra cứu Item từ quy tắc chọn mã (AL Rule, result_type = ITEM)."""
    # F1 — rule tra item/giá thuộc AL Formula Rules (theo thiết kế chỉ nhóm
    # quản trị BOM được xem) ⇒ kiểm quyền đọc chính doctype rule.
    _require_doctype_read_permission(
        "AL Rule", " nên không tra được quy tắc chọn mã sản phẩm")
    # Chặng 2B: `AL Rule` gộp cả rule trả SỐ lẫn rule chọn MÃ — hàm
    # `resolve_item` của controller kiểm `result_type == "ITEM"` và throw câu
    # người-đọc-được khi sai loại. Hợp đồng trả về giữ nguyên
    # `{item_code, item_name}` (integration/caller ngoài đang dùng).
    from alumglass.al_formula_rules.doctype.al_rule.al_rule import resolve_item
    return resolve_item(rule_code, input_value)


@frappe.whitelist()
def preview_rule(rule_code, input_value=None):
    """Thử tra 1 giá trị trên `AL Rule` — dùng cho nút "Thử tra" của form.

    Hợp đồng trả về: xem `ALRule.preview()` (thiết kế
    `docs/design/tra-cuu-quy-tac-de-hieu.md` §3.2). Logic nằm ở controller để
    form và API dùng CHUNG một nguồn.

    Quyền: đọc `AL Rule` (cùng cổng với `resolve_item_rule`). Trạng thái
    NGHIỆP VỤ (rule tắt / không khớp / chưa có dòng) ⇒ `success: True` +
    `message` người-đọc-được, ⛔ throw.
    """
    _require_doctype_read_permission(
        "AL Rule", " nên không thử tra được quy tắc")
    try:
        doc = frappe.get_doc("AL Rule", rule_code)
    except frappe.DoesNotExistError:
        frappe.throw(_(
            "Không tìm thấy quy tắc \"{0}\" — chọn lại quy tắc trong danh sách."
        ).format(rule_code))
    return doc.preview(input_value)


#: Biến THEO DÒNG ánh xạ thẳng sang cột của `AL Glass Master` — giá trị có
#: được là nhờ ĐÃ CHỌN KÍNH cho dòng, nên chỉ dòng kính mới có. Các biến theo
#: dòng còn lại do engine tự TÍNH/nạp cho MỌI dòng BOM (xem
#: `rule_input.ROW_RESOLVABLE_VARIABLES`) ⇒ `computed = True`, client cho chọn
#: mọi dòng BOM thay vì chỉ dòng kính (§7.6).
_GLASS_MASTER_VARIABLES = frozenset({
    "total_thick_mm", "glass_thick", "glass_type", "max_area_m2",
    "glass_name", "glass_type_name",
})


@frappe.whitelist()
def get_rule_input_variables():
    """Danh mục biến để quy tắc khai "Tra theo" — kèm cờ ĐỌC ĐƯỢC.

    Trả list `[{name, label, category, scope, resolvable, computed}]`, sắp
    xếp: biến đọc được TRƯỚC, rồi theo nhãn.

    `resolvable = False` nghĩa là biến THEO DÒNG mà engine KHÔNG nạp ở bước
    chọn mã (vd `width`, `qty`, `unit_qty`, `total_qty`, `line_total`) —
    chọn nó cho quy tắc sẽ ra 0 ÂM THẦM; client phải cảnh báo trước khi lưu.
    Biến toàn cục luôn `True` (engine đọc từ inputs của lượt tính).

    `computed = True` (§7.6): biến THEO DÒNG đọc được, nhưng giá trị do engine
    TÍNH/nạp cho MỌI dòng BOM (`weight_per_unit`, `unit_price`, `scrap_pct`,
    `calc_pattern`, `item_code`, `color`, `supplier_location`,
    `install_position`, `cut_angle`, `note`, `has_weight`) — ⛔ phải field của
    `AL Glass Master`. Client dùng cờ này để cho chọn MỌI dòng BOM thay vì
    chỉ dòng kính; biến kính (`total_thick_mm`, `glass_type`…) vẫn `False`.

    Quyền: đọc `AL Rule` — cùng cổng với `preview_rule` (danh mục biến chỉ
    dùng cho cấu hình quy tắc, ⛔ mở cho user lạ).
    """
    _require_doctype_read_permission(
        "AL Rule", " nên không xem được danh mục biến tra cứu")
    try:
        rows = frappe.get_all(
            "AL Variable Library",
            fields=["name", "var_label", "group_label"],
        ) or []
    except Exception as exc:  # noqa: BLE001 — lỗi hạ tầng ⛔ phơi ra UI
        frappe.log_error(
            "get_rule_input_variables: không đọc được AL Variable Library — %s"
            % exc,
            "AlumGlass API",
        )
        return []

    out = []
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        category = (row.get("group_label") or "").strip()
        scope = (rule_input.ROW_SCOPE
                 if category == rule_input.ROW_LITERAL_CATEGORY
                 else rule_input.GLOBAL_SCOPE)
        resolvable = (True if scope == rule_input.GLOBAL_SCOPE
                      else rule_input.is_row_variable_resolvable(name))
        computed = bool(
            scope == rule_input.ROW_SCOPE and resolvable
            and name not in _GLASS_MASTER_VARIABLES)
        out.append({
            "name": name,
            "label": (row.get("var_label") or "").strip() or name,
            "category": category,
            "scope": scope,
            "resolvable": resolvable,
            "computed": computed,
        })
    out.sort(key=lambda item: (
        0 if item["resolvable"] else 1,
        item["label"].casefold(),
        item["name"],
    ))
    return out


@frappe.whitelist()
def get_bom_structure(bom_code):
    """Lấy toàn bộ cấu trúc BOM."""
    # F1 — cấu trúc BOM là dữ liệu của AL BOM ⇒ kiểm quyền đọc AL BOM.
    _require_doctype_read_permission("AL BOM", " nên không xem được cấu trúc BOM")
    from alumglass.al_bom_engine.doctype.al_bom.al_bom import get_bom_structure as _get
    return _get(bom_code)


@frappe.whitelist()
def get_cost_template_context(template_code=None):
    """[DEPRECATED] Dùng get_formula_context thay thế."""
    # F1 — không cần kiểm quyền riêng: uỷ quyền hẳn cho get_formula_context,
    # nơi đã kiểm allowlist doctype + quyền đọc "AL Cost Template".
    return get_formula_context("AL Cost Template", None)


# F1 — `get_formula_context(doctype, docname)` đọc field của chứng từ theo CẶP
# DO CLIENT TRUYỀN ⇒ ⛔ không được tin. Chỉ cho đọc trong miền AlumGlass (lọc
# theo MODULE, không hardcode từng tên doctype — thêm doctype AL mới không phải
# sửa file này), các doctype của formula_builder mà form công thức dùng thật
# (vd Formula Global Variable), và Quotation/Quotation Item — 2 doctype nghiệp
# vụ mà các field công thức AL gắn vào.
_FORMULA_CONTEXT_ALLOWED_MODULE_PREFIX = "AL "
_FORMULA_CONTEXT_ALLOWED_MODULES = ("Formula Builder",)
_FORMULA_CONTEXT_ALLOWED_DOCTYPES = ("Quotation", "Quotation Item")


def _assert_formula_context_doctype(doctype):
    """F1 — Chặn `get_formula_context` đọc doctype ngoài miền cho phép.

    Trước đây client truyền doctype nào cũng được ⇒ đọc được field của MỌI
    chứng từ (User, System Settings, File...). Nay phải thoả CẢ HAI:
      1. doctype nằm trong miền cho phép (theo module), và
      2. user có quyền ĐỌC chính doctype đó.
    Doctype không tồn tại ⇒ module "" ⇒ bị chặn luôn.
    """
    if not doctype:
        # ⛔ Không có doctype thì không có gì để kiểm quyền; nếu cho qua, người
        # gọi rỗng doctype vẫn nhận trọn bộ biến + cost bucket ⇒ chặn hẳn.
        frappe.throw(_("Thiếu loại chứng từ cần lấy danh sách biến công thức."))

    if doctype not in _FORMULA_CONTEXT_ALLOWED_DOCTYPES:
        # Đọc module thẳng từ DB (không dùng frappe.get_meta: doctype không tồn
        # tại sẽ ném DoesNotExistError với thông điệp kỹ thuật tiếng Anh).
        # Doctype không tồn tại ⇒ module "" ⇒ rơi vào nhánh chặn bên dưới.
        module = frappe.db.get_value("DocType", doctype, "module") or ""
        if not (module.startswith(_FORMULA_CONTEXT_ALLOWED_MODULE_PREFIX)
                or module in _FORMULA_CONTEXT_ALLOWED_MODULES):
            frappe.throw(_(
                "Không lấy được danh sách biến công thức cho loại chứng từ {0}."
            ).format(doctype))

    _require_doctype_read_permission(
        doctype, " nên không lấy được danh sách biến công thức")


def _resolve_doc_values(doctype, docname):
    """Resolve giá trị THỰC TẾ (Profile System, Product Type...) cho
    autocomplete/preview trong Formula Builder.

    ★ FIX (audit gap): trước đây hardcode `if doctype == "AL Bom Set"` +
    mapping field→tên biến bằng tay (`"offset_crossbar".upper()` =
    "OFFSET_CROSSBAR" — SAI, biến thật seed trong AL Variable Library và
    dùng trong công thức là "OFFSET_DO_NGANG"). Nay dùng ĐÚNG 1 nguồn với
    bom_orchestrator._resolve_system_variables() (AL Variable Library
    is_system=1 + source_doctype/source_field + override system_variables
    trên AL Profile System) qua module dùng chung system_variable_resolver
    — xem đó để hiểu đầy đủ. Không còn hardcode tên doctype nào: tự dò field
    Link trên `doctype` trỏ tới đúng source_doctype mà System Variable cần.
    """
    vals = {}
    # Khi tạo mới record, docname là tên tạm (vd: new-al-bom-set-xxx) → chưa tồn tại trong DB.
    # Tránh gọi get_cached_doc với docname không tồn tại vì Frappe sẽ throw DoesNotExistError.
    if not docname or not frappe.db.exists(doctype, docname):
        return vals
    try:
        from alumglass.al_bom_engine.system_variable_resolver import (
            resolve_source_record_names, resolve_system_variable_values)
        source_records = resolve_source_record_names(doctype, docname)
        vals = resolve_system_variable_values(source_records)
    except Exception:
        # R9 — KHÔNG nuốt exception im lặng: ghi log đủ context (doctype, docname,
        # traceback) để chẩn đoán khi resolve Profile System/Product Type lỗi.
        # VẪN trả `vals` rỗng khi lỗi — fallback an toàn hiện tại phải giữ.
        frappe.log_error(
            frappe.get_traceback(),
            title="AlumGlass _resolve_doc_values failed: %s %s" % (doctype, docname),
        )
    return vals


def _get_live_context_vars(doctype, docname=None, fieldname=None):
    """B6 FB-max: lấy context autocomplete từ get_live_context (nguồn chính FB).

    Trả về dict response của formula_builder.api.formula_builder.get_live_context,
    hoặc {} nếu FB không dùng được (lỗi/thiếu permission) — caller fallback cũ.

    `fieldname` (field công thức đang sửa) được đưa vào SCOPE JSON để luật
    `applies_to_field` của Formula Variable Binding có tác dụng thật — trước
    đây scope thiếu fieldname nên `binding_matches_scope(..., field="")` cho
    qua MỌI binding có khai `applies_to_field` (lọc theo field vô hiệu).
    """
    import json as _json
    try:
        from formula_builder.api.formula_builder import get_live_context
    except Exception:
        return {}
    try:
        scope = _json.dumps({
            "current_doctype": doctype or "",
            "current_docname": docname or "",
            "fieldname": fieldname or "",
        })
        return get_live_context(scope) or {}
    except Exception:
        return {}


def _library_variable_entries(table_field, default_group):
    """Biến của 1 loại (row literal / biến người dùng nhập) — DATA-DRIVEN.

    Nguồn DUY NHẤT: `AL Variable Library` (qua `variable_sources/catalog_rows`).
    Bảng Settings đã bị xoá 2026-11-27 nên ⛔ còn danh sách cứng dự phòng:
    biến đã khai mà không hiện là lỗi cần sửa, ⛔ che bằng tuple cũ.

    Dòng đang TẮT hết ⇒ trả [] (tôn trọng cấu hình admin).
    """
    from alumglass.variable_sources import catalog_rows

    kind = (catalog_rows.KIND_ROW if table_field == "row_literals"
            else catalog_rows.KIND_COMMON)
    return [
        {
            "name": row["var_name"],
            "label": row.get("var_label") or "",
            "type": row.get("var_type") or "",
            "group": row.get("group_label") or default_group,
            "description": row.get("description") or "",
        }
        for row in catalog_rows.active_rows(kind)
        if row.get("var_name")
    ]


def _is_empty_formula_value(value):
    """True nếu giá trị chưa phải giá trị thật (None/rỗng/gạch ngang)."""
    if isinstance(value, str):
        return value.strip() in ("", "—", "-")
    return value is None


def _binding_scope_fields(v):
    """Phạm vi field của 1 biến lấy từ Formula Variable Binding.

    `only_fields` (catalog trả sẵn) thắng; nếu không có thì suy từ
    `applies_to_field` — dữ liệu có thể là list hoặc chuỗi phân tách bằng `,`
    hoặc `|`. Trả [] = biến áp cho MỌI field (hành vi cũ, không lọc gì).
    """
    only = v.get("only_fields")
    if isinstance(only, str):
        raw = only.strip()
        # Catalog lưu `only_fields` dạng JSON list (Small Text) — API khác có
        # thể trả list thật; chấp nhận cả chuỗi phân tách `,`/`|`.
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                only = parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                only = []
        else:
            only = [x.strip() for x in raw.replace(",", "|").split("|")
                    if x.strip()]
    if not only:
        raw = v.get("applies_to_field")
        if raw:
            only = [
                x.strip()
                for x in str(raw).replace(",", "|").split("|")
                if x.strip()
            ]
    return list(only or [])


def _normalize_catalog_variable(v):
    """Bảo đảm biến từ catalog có ĐỦ key mà JS đang đọc (không vỡ autocomplete).

    Catalog (DEV1) trả candidate dict theo spec; hàm này chỉ điền mặc định cho
    key thiếu/rỗng, KHÔNG đổi ngữ nghĩa dữ liệu catalog trả về.
    """
    v = dict(v)
    v["label"] = v.get("label") or v.get("name") or ""
    if v.get("value") is None:
        # Giữ tương thích legacy: UI hiển thị "—" khi chưa resolve được giá trị.
        v["value"] = "—"
    v["type"] = v.get("type") or "Float"
    v["source"] = v.get("source") or "local"
    v["source_type"] = v.get("source_type") or "catalog"
    v["group"] = v.get("group") or ""
    v["value_source"] = (
        v.get("value_source") or v.get("provenance") or "Variable Catalog")
    v["description"] = v.get("description") or v.get("provenance") or ""
    v["is_pricing_dimension"] = bool(v.get("is_pricing_dimension"))
    # Phạm vi field (luôn là list để client lọc) — [] = không lọc.
    v["only_fields"] = _binding_scope_fields(v)
    v["hide_all"] = bool(v.get("hide_all"))
    return v


def _get_catalog_context(doctype, docname=None, fieldname=None,
                         child_table=None, row_index=None,
                         all_sources=False):
    """Lấy context từ Variable Catalog — ĐƯỜNG ĐỌC CHÍNH (B4).

    Trả None CHỈ khi không đọc được danh mục (module chưa có / lỗi). Record
    chưa gán hồ sơ vẫn có danh mục ĐẦY ĐỦ (hồ sơ chỉ để thu hẹp) — trước B4
    chỗ này cố ý trả None để caller chạy đường legacy 8 nhóm.

    `all_sources=True` ⇒ bỏ qua hồ sơ (dùng cho VALIDATE: vũ trụ biến hợp lệ
    ⛔ được thu hẹp bởi bộ lọc gợi ý).
    """
    try:
        from alumglass.api.variable_catalog import get_variable_catalog
    except Exception:
        # Chưa có module — chạy đường dự phòng, KHÔNG log ồn ào (đây là trạng
        # thái hợp lệ khi site chưa migrate).
        return None
    try:
        cat = get_variable_catalog(
            doctype, docname,
            child_table=child_table, row_index=row_index,
            fieldname=fieldname,
            all_sources=1 if all_sources else 0) or {}
    except Exception:
        # Danh mục lỗi ⇒ vẫn phải có danh sách cho autocomplete/validate,
        # ⛔ trả rỗng làm người dùng mất hết gợi ý.
        frappe.log_error(
            frappe.get_traceback(),
            title="AlumGlass get_variable_catalog failed: %s" % doctype,
        )
        return None

    profile = cat.get("profile")

    variables = [
        _normalize_catalog_variable(v)
        for v in (cat.get("variables") or []) if v.get("name")
    ]
    references = [
        r for r in (cat.get("references") or []) if r.get("name")
    ]
    meta = dict(cat.get("meta") or {})
    if profile:
        meta.setdefault(
            "profile_code",
            profile.get("code") if isinstance(profile, dict) else str(profile))
    meta.setdefault("fieldname", fieldname or "")

    return {
        "doctype": doctype,
        "docname": docname,
        "variables": variables,
        "references": references,
        "total_sources": len({
            v.get("source_type") for v in variables if v.get("source_type")}),
        "total_variables": len(variables),
        "profile": profile,
        "meta": meta,
    }


@frappe.whitelist()
def get_formula_context(doctype, docname=None, fieldname=None,
                        child_table=None, row_index=None,
                        include_all_sources=False):
    """★ DATA-DRIVEN: Lấy context variables cho autocomplete formula fields.

    HAI ĐƯỜNG (spec Variable Catalog):
      A. Record có gán `variable_profile` → `alumglass.api.variable_catalog`
         quyết định danh sách biến (lọc theo rule, nhóm theo `group_label`,
         có provenance + thống kê). Đường này trả thêm `profile` + `meta`.
      B. Record CHƯA gán profile (hoặc catalog chưa có) → đường legacy 8 nhóm
         bên dưới, giữ nguyên hành vi cũ (tương thích ngược tuyệt đối).

    B6 FB-max: autocomplete lấy từ 1 nguồn chính là get_live_context (FVB + doc
    fields + global vars) — thay vì chỉ liệt kê tay. Các nguồn AL-specific
    (Cost Bucket, Row Literals, Common Vars, Slug Library, Variable Set) giữ làm
    fallback backward-compat cho tới khi FVB seed (D3) — không làm mất biến UI.

    Không hardcode biến nào — mọi biến được khám phá động từ DB.
    Người dùng thêm biến mới = thêm record vào bảng tương ứng, không cần sửa code.

    Nguồn biến (đường legacy, theo thứ tự ưu tiên):
    0. ★ get_live_context (FB-max B6) — Formula Variable Binding resolve thật
    1. Cost Bucket codes — từ AL Cost Bucket (động, user thêm được)
    2. System Variables — từ AL Variable Library (is_system=1)
    3. User Variables — từ AL Variable Library (is_system=0), lọc theo Variable Set của doctype
    4. Formula Global Variables — từ Formula Builder
    5. Row Literals — `AL Variable Library` category Row Literals (engine inject per-row
       khi chạy B2); tuple cũ chỉ là fallback khi site chưa migrate
    6. Common Vars — `AL Variable Library` `is_input=1` (W_mm, H_mm...);
       tuple cũ chỉ là fallback khi site chưa migrate
    7. Formula Variable Bindings — per-doctype bindings từ Formula Builder
    8. Slug Library — cho cross-row reference

    Args:
        doctype: Tên doctype đang mở (vd: "AL Cost Template", "AL Bom Set")
        docname: Tên record (để resolve giá trị thực tế / đọc `variable_profile`)
        fieldname: Field công thức đang sửa (để lọc `only_fields` của profile
            và cho luật `applies_to_field` của FVB) — optional, backward compat.
        child_table: Child table đang sửa (vd "items") — cho catalog lấy binding
            scope của dòng con; bỏ trống = hành vi cũ (chỉ scope doctype).
        row_index: Chỉ số dòng (0-based) trong `child_table` — optional.
        include_all_sources: True ⇒ BỎ QUA catalog, luôn chạy đường legacy
            (universe biến ĐẦY ĐỦ như trước bản vá). Dùng cho VALIDATE —
            profile chỉ được lọc GỢI Ý, không được thu hẹp universe hợp lệ
            (nếu không: bật profile là chặn oan công thức đang chạy).

    F1 — `doctype` do client truyền nên phải qua allowlist + kiểm quyền đọc
    (xem `_assert_formula_context_doctype`) TRƯỚC khi resolve bất cứ thứ gì.
    """
    _assert_formula_context_doctype(doctype)

    # ── Đường CHÍNH: Variable Catalog (B4 — một đường đọc duy nhất) ─────
    # Record chưa gán hồ sơ vẫn có danh mục ĐẦY ĐỦ; `include_all_sources=True`
    # (validate) ⇒ bỏ qua hồ sơ, giữ nguyên vũ trụ biến hợp lệ.
    catalog_ctx = _get_catalog_context(
        doctype, docname, fieldname, child_table=child_table,
        row_index=row_index, all_sources=include_all_sources)
    if catalog_ctx:
        return catalog_ctx

    # ── Đường DỰ PHÒNG (legacy 8 nhóm) — chỉ còn chạy khi danh mục KHÔNG đọc
    #    được (module chưa có / vừa lỗi). Đây ⛔ phải là đường bình thường;
    #    nếu log_error "get_variable_catalog failed" xuất hiện thì đó là sự cố
    #    cần sửa, không phải trạng thái chạy được.
    variables = []
    references = []

    # Resolve giá trị thực tế từ document (khi có docname)
    resolved = _resolve_doc_values(doctype, docname) if docname else {}

    # ── 0. ★ FB-max (B6): nguồn chính từ get_live_context ────────────
    fb_ctx = _get_live_context_vars(doctype, docname, fieldname=fieldname)
    for v in fb_ctx.get("variables") or []:
        name = v.get("name", "")
        if not name:
            continue
        variables.append({
            "name": name,
            "label": v.get("label") or name,
            "value": v.get("value", "—"),
            "type": v.get("type") or "Float",
            "source": v.get("source") or "local",
            "source_type": v.get("source_type") or "binding",
            "group": ("Bindings · FB (global)" if v.get("is_global")
                      else f"Bindings · {doctype}"),
            "value_source": "Resolve từ Formula Variable Binding (get_live_context)",
            "description": f"Formula Variable Binding · {v.get('source_type', '')}",
            # Phạm vi field của binding — client lọc ([] = áp cho mọi field).
            "only_fields": _binding_scope_fields(v),
            # Binding khai "ẩn ở MỌI field" (DEV3 trả kèm live context).
            "hide_all": bool(v.get("hide_all")),
        })

    # ── 1. Cost Bucket codes ────────────────────────────────────────
    for b in frappe.get_all("AL Cost Bucket",
                            fields=["bucket_code", "bucket_name", "bucket_role",
                                    "report_group", "sort_order"], order_by="sort_order"):
        variables.append({"name": b["bucket_code"],
            "label": f"{b['bucket_code']} — {b.get('bucket_name', '')}",
            "value": "—", "type": "Float", "source": "local",
            "source_type": "cost_bucket", "group": b.get("report_group") or "Cost Bucket",
            "value_source": "Tính tự động khi chạy BomOrchestrator B4-B5",
            "description": f"Cost Bucket ({b.get('bucket_role', '')}) · giá trị được tính khi engine chạy",})

    # ── 2. System Variables — resolve giá trị thực từ document nếu có
    # Phase 3d (v28_11): var đã seed FVB (D3/D6) → KHÔNG mô tả nguồn resolve là
    # "engine resolve từ source_doctype.source_field khi chạy BOM" nữa — nguồn
    # resolve thật của nó là Formula Variable Binding (get_live_context, cùng
    # source link nhưng qua layer FVB). Var CHƯA seed (fallback engine 1.3) →
    # giữ mô tả cũ (safe fallback). Entry FB (đầu) vẫn giữ khi dedup bên dưới.
    seeded_fb = set(frappe.get_all(
        "Formula Variable Binding",
        filters={"is_active": 1},
        pluck="variable_name",
    ) or [])
    for sv in frappe.get_all("AL Variable Library",
                             filters={"is_system": 1},
                             fields=["var_name", "var_label", "var_type",
                                     "default_value", "description",
                                     "source_doctype", "source_field"],
                             order_by="var_name"):
        actual = resolved.get(sv["var_name"])
        val = actual if actual is not None else sv.get("default_value")
        if actual is not None:
            src = f"ĐÃ RESOLVE từ {doctype} '{docname}'"
        elif sv["var_name"] in seeded_fb:
            src = "Default · Resolve qua Formula Variable Binding (get_live_context) khi chạy BOM"
        else:
            src = (f"Default · Engine resolve từ {sv.get('source_doctype','')}.{sv.get('source_field','')} khi chạy BOM")
        variables.append({"name": sv["var_name"],
            "label": f"{sv['var_name']} — {sv.get('var_label') or ''}",
            "value": val, "type": sv.get("var_type") or "Float",
            "source": "local", "source_type": "variable_library",
            "group": "System Variables", "value_source": src,
            "description": sv.get("description") or f"AL Variable Library · is_system=1",})

    # ── 3. User Variables ───────────────────────────────────────────
    # Sau B2, Library chứa cả common (is_input=1) và row literal
    # (category=Row Literals) — hai loại đó có nhóm 5/6 riêng bên dưới.
    # `KIND_USER` đã loại chúng ⇒ ⛔ hiện trùng 2 lần trong autocomplete.
    from alumglass.variable_sources import catalog_rows as _catalog_rows
    for uv in _catalog_rows.active_rows(_catalog_rows.KIND_USER):
        name = uv.get("var_name") or ""
        if not name:
            continue
        variables.append({"name": name,
            "label": f"{name} — {uv.get('var_label') or ''}".rstrip(" —"),
            "value": "—", "type": uv.get("var_type") or "Float",
            "source": "local", "source_type": "variable_library",
            "group": uv.get("group_label") or "User Variables",
            "value_source": "Người dùng nhập khi mở dialog Tham số BOM",
            "description": uv.get("description") or "AL Variable Library · User variable",})

    # ── 4. Formula Global Variables ─────────────────────────────────
    for gv in frappe.get_all("Formula Global Variable",
                             fields=["var_name", "constant_value"], order_by="var_name"):
        variables.append({"name": gv["var_name"],
            "label": f"{gv['var_name']} — Hằng số toàn cục",
            "value": gv.get("constant_value"), "type": "Float",
            "source": "local", "source_type": "formula_global_var",
            "group": "Formula Global Variables",
            "value_source": "Hằng số toàn cục · Formula Global Variable",
            "description": "Formula Builder Global Variable",})

    # ── 5. Row Literals — nguồn: AL Variable Library (category Row Literals) ──
    # Trước bản vá: tuple cứng 9 tên. Nay đọc DỮ LIỆU (patch v28_14 seed từ
    # `AL Variable Library` là nguồn duy nhất (bảng Settings đã bị xoá).
    for entry in _library_variable_entries(
            "row_literals", "Row Literals"):
        name = entry["name"]
        label = entry.get("label") or ""
        variables.append({
            "name": name,
            "label": f"{name} — {label}" if label else name,
            "value": "—", "type": entry.get("type") or "Float",
            "source": "local", "source_type": "row_literal",
            "group": entry.get("group") or "Row Literals",
            "value_source": "Engine inject per-row khi chạy BomOrchestrator B2",
            "description": entry.get("description")
                or "Tự động inject — mỗi dòng BOM có giá trị riêng",
        })

    # ── 6. Common BOM Variables — nguồn: Library `is_input=1` ──
    for entry in _library_variable_entries(
            "common_variables", "BOM Input Variables"):
        name = entry["name"]
        label = entry.get("label") or ""
        variables.append({
            "name": name,
            "label": f"{name} — {label}" if label else name,
            "value": "—", "type": entry.get("type") or "Float",
            "source": "local", "source_type": "common_var",
            "group": entry.get("group") or "BOM Input Variables",
            "value_source": "Người dùng nhập khi mở dialog Tham số BOM",
            "description": entry.get("description")
                or "BOM input variable — giá trị đến từ user",
        })

    # ── 7. Formula Variable Bindings ────────────────────────────────
    for b in frappe.get_all("Formula Variable Binding",
                            filters=[["is_active", "=", 1],
                                     ["applies_to_doctype", "in", ["", doctype]]],
                            fields=["variable_name", "variable_label", "data_type",
                                    "default_value", "source_type", "applies_to_doctype",
                                    "applies_to_field"],
                            order_by="resolve_priority"):
        variables.append({"name": b["variable_name"],
            "label": b.get("variable_label") or b["variable_name"],
            "value": b.get("default_value"), "type": b.get("data_type") or "Float",
            "source": "local", "source_type": b.get("source_type") or "binding",
            "group": "Formula Bindings" if not b.get("applies_to_doctype") else f"Bindings · {doctype}",
            "value_source": "Default từ Formula Variable Binding" if not b.get("applies_to_doctype")
                else f"Binding cho {doctype}",
            "description": f"Formula Variable Binding · {b.get('source_type', '')}",
            # Phạm vi field của binding — client lọc ([] = áp cho mọi field).
            "only_fields": _binding_scope_fields(b),})

    # ── 8. ★ Variable Set của document hiện tại ──────────────────────
    # V6 P10: KHÔNG hardcode danh sách doctype nữa — _inject_variable_set_vars
    # tự dò field Link phù hợp trên chính doctype (xem _resolve_variable_set_name).
    if docname:
        _inject_variable_set_vars(variables, doctype, docname, resolved)

    # ── 2c. V6 P10: đánh dấu biến nào là Pricing Dimension (DATA-DRIVEN) ──
    # Lấy trực tiếp từ AL Variable Dimension Mapping — bảng này VỐN ĐÃ là
    # nguồn cấu hình duy nhất cho "biến X là 1 dimension tra giá", được dùng
    # bởi cả BomOrchestrator (engine/bom_orchestrator.py) lẫn
    # fb_handlers.aluminum_price_composite. Dialog (quotation.js) không tự
    # quyết định/hardcode tên biến nữa — chỉ đọc cờ này. Thêm dimension mới
    # (kể cả cho kính) = thêm 1 record Mapping, KHÔNG cần sửa code JS.
    pricing_dim_vars = set(
        frappe.get_all("AL Variable Dimension Mapping", filters={"is_active": 1}, pluck="variable_name")
    )
    for v in variables:
        v["is_pricing_dimension"] = v["name"] in pricing_dim_vars

    # ── 9. Slug Library ─────────────────────────────────────────────
    slugs = frappe.get_all("AL Slug Library",
                           fields=["slug", "label", "category", "group_tag"],
                           order_by="group_tag, slug")
    for s in slugs:
        references.append({
            "name": f"items.{s['slug']}.{{field}}",
            "label": f"{s['slug']} — {s.get('label', '')}",
            "doctype": "AL Bom Item",
            "group": s.get("group_tag") or "Unknown",
            "category": s.get("category") or "",
        })

    # ── Dedup (B6 FB-max): entry ĐẦU giữ metadata + vị trí nhóm ──────────
    # ⛔ Không đổi thứ tự nhóm. Khác hành vi cũ ở ĐÚNG 1 điểm: entry đầu có
    # giá trị rỗng/None (vd binding FB resolve hụt) mà entry sau có giá trị
    # thật (Library/Cost Bucket) → lấy giá trị của entry sau, GIỮ metadata +
    # nhóm của entry đầu. Mọi ca khác vẫn bỏ entry sau như cũ.
    # Mọi lần bỏ đều ghi vết vào `meta.duplicates` — không bỏ im lặng.
    seen = {}
    deduped = []
    duplicates = []
    duplicates_by_name = {}
    for v in variables:
        n = v.get("name", "")
        if not n:
            continue
        kept = seen.get(n)
        if kept is not None:
            entry = duplicates_by_name.get(n)
            if entry is None:
                entry = {
                    "name": n,
                    "kept": kept.get("source_type") or "",
                    "dropped": [],
                    "value_taken_from_dropped": False,
                }
                duplicates_by_name[n] = entry
                duplicates.append(entry)
            dropped_source = v.get("source_type") or ""
            if dropped_source and dropped_source not in entry["dropped"]:
                entry["dropped"].append(dropped_source)

            # Hợp PHẠM VI FIELD của 2 nguồn trùng tên (entry đầu giữ vị trí +
            # metadata): nếu MỘT nguồn không giới hạn field (only_fields rỗng
            # + không hide_all) ⇒ biến không giới hạn; cả hai hide_all ⇒
            # hide_all; còn lại hợp danh sách field. Nếu không hợp, binding
            # global (không giới hạn) bị binding field-scope đứng trước che
            # ⇒ biến ẩn oan ở các field khác.
            kept_hide = bool(kept.get("hide_all"))
            new_hide = bool(v.get("hide_all"))
            kept_only = kept.get("only_fields") or []
            new_only = v.get("only_fields") or []
            if not kept_hide and not new_hide and (not kept_only or not new_only):
                kept["only_fields"] = []
                kept["hide_all"] = False
            elif kept_hide and new_hide:
                kept["only_fields"] = []
                kept["hide_all"] = True
            else:
                merged_only = list(kept_only)
                for field_name in new_only:
                    if field_name not in merged_only:
                        merged_only.append(field_name)
                kept["only_fields"] = merged_only
                kept["hide_all"] = False

            if (_is_empty_formula_value(kept.get("value"))
                    and not _is_empty_formula_value(v.get("value"))):
                kept["value"] = v["value"]
                entry["value_taken_from_dropped"] = True
            continue
        seen[n] = v
        deduped.append(v)
    variables = deduped

    return {
        "doctype": doctype,
        "docname": docname,
        "variables": variables,
        "references": references,
        "total_sources": len({v["source_type"] for v in variables}),
        "total_variables": len(variables),
        # Đường legacy: không có profile (caller/JS dùng cờ này để biết danh
        # sách biến là bộ 8 nhóm cũ hay bộ lọc theo profile).
        "profile": None,
        "meta": {"duplicates": duplicates, "fieldname": fieldname or ""},
    }


@frappe.whitelist()
def get_allowed_formula_functions():
    """★ DATA-DRIVEN: trả về danh sách hàm custom AlumGlass được whitelist
    trong công thức (lookup_rule, lookup_calc_pattern, roundup...).

    Nguồn DUY NHẤT: alumglass.al_bom_engine.formula_validate.ALUMGLASS_CUSTOM_FUNCS
    — trước đây danh sách này lặp tay ở 3 nơi (al_cost_template.py,
    formula_validate.py, cost_template.js) — dễ lệch pha khi thêm hàm mới.
    Từ giờ chỉ cần sửa Python 1 chỗ (formula_validate.py); JS fetch qua API
    này (xem public/js/cost_template.js -> validateViaFB), không cần sửa tay.
    """
    from alumglass.al_bom_engine.formula_validate import ALUMGLASS_CUSTOM_FUNCS
    return {"custom_functions": sorted(ALUMGLASS_CUSTOM_FUNCS)}


def _resolve_variable_set_name(doctype, docname):
    """Tìm variable_set áp dụng cho (doctype, docname) — KHÔNG hardcode tên
    doctype nào. Tự dò theo field trên chính doctype:
      1. Doctype có field Link -> "AL Variable Set" (tên field gì cũng được)
         → lấy giá trị trực tiếp.
      2. Không có (1) nhưng có field Link -> "AL Bom Set" → đi qua 1 hop,
         lấy variable_set của AL Bom Set đó (case AL BOM / AL Bom Engine).
      3. Không có (1)/(2) nhưng có field Link -> "AL Product Type" và record
         đã chọn product_type → lấy AL Variable Set đang bật khớp product_type
         (xem quy tắc chọn cố định ở nhánh 3 bên dưới).
    Thêm doctype mới muốn dùng Variable Set = thêm đúng 1 field Link tương
    ứng trên doctype đó trong Doctype Builder — KHÔNG cần sửa file này.
    """
    meta = frappe.get_meta(doctype)

    def _find_link_field(target_doctype):
        for f in meta.get("fields", []):
            if f.fieldtype == "Link" and f.options == target_doctype:
                return f.fieldname
        return None

    direct_field = _find_link_field("AL Variable Set")
    if direct_field:
        return frappe.db.get_value(doctype, docname, direct_field)

    bom_set_field = _find_link_field("AL Bom Set")
    if bom_set_field:
        bom_set_name = frappe.db.get_value(doctype, docname, bom_set_field)
        if bom_set_name:
            return frappe.db.get_value("AL Bom Set", bom_set_name, "variable_set")

    # 3. Không có field Link trực tiếp: suy ra theo `product_type`.
    #    Doctype có field Link -> "AL Product Type" và record đã chọn giá trị
    #    ⇒ lấy AL Variable Set đang bật có CÙNG product_type.
    #    Quy tắc chọn khi nhiều bộ cùng khớp (cố định, có chủ đích):
    #    `modified desc` = bộ vừa được cập nhật gần nhất thắng (admin sửa bộ
    #    nào thì bộ đó đang là bộ dùng thật); chốt thêm `name asc` để kết quả
    #    ỔN ĐỊNH giữa các lần gọi (không phụ thuộc thứ tự DB trả về).
    #    KHÔNG hardcode tên doctype nghiệp vụ nào khác — chỉ 2 doctype cấu
    #    hình đã có trong hệ (AL Variable Set / AL Product Type).
    product_type_field = _find_link_field("AL Product Type")
    if product_type_field:
        product_type = frappe.db.get_value(doctype, docname, product_type_field)
        if product_type:
            matched = frappe.get_all(
                "AL Variable Set",
                filters={"product_type": product_type, "is_active": 1},
                order_by="modified desc, name asc",
                limit=1,
                pluck="name",
            )
            if matched:
                return matched[0]

    return None


def _inject_variable_set_vars(variables, doctype, docname, resolved=None):
    """Resolve Variable Set từ document hiện tại và inject các biến."""
    resolved = resolved or {}
    try:
        variable_set_name = _resolve_variable_set_name(doctype, docname)
    except Exception:
        variable_set_name = None
    if not variable_set_name or not frappe.db.exists("AL Variable Set", variable_set_name):
        return
    try:
        vs = frappe.get_cached_doc("AL Variable Set", variable_set_name)
        for item in vs.items:
            var_name = item.get("variable") or item.get("var_name")
            if not var_name:
                continue
            lib_info = frappe.db.get_value("AL Variable Library", var_name,
                                           ["var_label", "var_type", "default_value"], as_dict=True)
            variables.append({
                "name": var_name,
                "label": f"{var_name} — {item.get('var_label') or (lib_info.get('var_label') if lib_info else '')}",
                "value": "—",
                "type": item.get("var_type") or (lib_info.get("var_type") if lib_info else "Float"),
                "source": "local", "source_type": "variable_set",
                "group": f"Variable Set · {vs.set_code or variable_set_name}",
                "value_source": f"Từ Variable Set '{vs.set_name or variable_set_name}' — user nhập khi mở dialog",
                "description": f"Variable Set · '{vs.set_name or variable_set_name}'",
            })
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# Pha 3 — GIÁ KÍNH cho dialog: MỘT đường giá duy nhất với engine
# ═══════════════════════════════════════════════════════════════════
# Vì sao phải gom 1 chỗ: dialog "Kính theo vị trí" hiển thị giá của mã kính
# cho người dùng chọn. Nếu API tự tra giá bằng câu SQL riêng, dialog có thể
# hiện 1 đằng còn bấm "Tính giá" ra 1 nẻo (đúng ca bug đã xảy ra: dòng kính
# ăn theo `default_glass_master` ra 0 đ). Nên mọi chỗ cần "giá của mã kính
# theo báo giá hiện tại" đều đi qua `_resolve_glass_price()` — hàm này dùng
# CHÍNH `BomOrchestrator` (b0+b1+snapshot) và `price_for_code()` của engine.

_GLASS_PRICE_APPROX_NOTE = (
    "Giá thực tế còn phụ thuộc màu/độ dày — sẽ chốt khi hệ thống tính lại giá.")


def _glass_price_note_missing(price_list):
    """Câu "chưa có giá" — nêu TÊN bảng giá để người dùng biết chỗ kiểm."""
    if price_list:
        return 'Mã kính này chưa có giá trong bảng giá "%s".' % price_list
    return "Mã kính này chưa có giá trong bảng giá đang dùng."


def _prepare_glass_price_context(quotation_item_name, params=None):
    """Dựng ngữ cảnh tra giá của 1 dòng báo giá → `(orch, qi)`.

    `orch` = BomOrchestrator đã chạy b0+b1+snapshot (đủ `inputs`, danh sách
    dòng BOM, category kính). Trả `(None, qi)` khi KHÔNG dựng được — VD dòng
    báo giá chưa lưu `al_bom_vars`, BOM chưa có version, hoặc lỗi cấu hình.
    Caller khi đó rơi về dòng Item Price thô + `approx=True` (KHÔNG im lặng
    trả một con số khác giá engine mà không nói).

    `params` (TUỲ CHỌN — phase 1.5): tham số dòng ĐANG NẰM TRÊN DIALOG (đã lọc
    whitelist qua `_parse_preview_params`). Có params ⇒ dựng `_qi_doc` từ
    params (persist=False) thay vì đọc `al_bom_vars` trong DB, nhờ vậy dialog
    tra giá theo biến người dùng ĐANG SỬA (preview không còn ghi DB trước).
    ⛔ Tiền tệ/bảng giá/khách hàng KHÔNG đến từ client — `_parse_preview_params`
    loại các khoá `_…`; bối cảnh giá chỉ do `preview_guard` (máy chủ, đọc từ
    chính doc báo giá đang lưu) hoặc DB của Quotation cha cung cấp.
    Không truyền ⇒ giữ NGUYÊN hành vi cũ (đọc DB).
    """
    if not quotation_item_name and not params:
        return None, None
    from alumglass.engine.bom_orchestrator import BomOrchestrator

    qi = None
    if quotation_item_name:
        try:
            qi = frappe.get_doc("Quotation Item", quotation_item_name)
        except Exception:
            qi = None
    try:
        if params:
            orch = BomOrchestrator(
                quotation_item_name=quotation_item_name or None,
                params=params, persist=False)
        else:
            orch = BomOrchestrator(quotation_item_name)
        orch.prepare_price_context()
        return orch, qi or orch._qi_doc
    except Exception as exc:
        frappe.log_error(
            title="AlumGlass: không dựng được ngữ cảnh giá kính (dialog)",
            message="Quotation Item %s — %s" % (quotation_item_name or "(dòng mới)", exc))
        return None, qi


def _raw_glass_price_row(code, price_list):
    """Dòng Item Price THÔ (chưa áp composite dimension) — `(price, row)`."""
    if not code:
        return 0, None
    rows = frappe.get_all(
        "Item Price",
        filters={"item_code": code, "price_list": price_list},
        fields=["name", "item_code", "price_list_rate", "currency",
                "valid_from", "valid_upto"],
    )
    from alumglass.engine.composite_pricing import filter_price_rows
    valid_rows = filter_price_rows(rows)
    if not valid_rows:
        return 0, None
    return valid_rows[0]["price_list_rate"], valid_rows[0]


def _resolve_glass_price(quotation_item_name, glass_code, context=None,
                         context_attempted=False, params=None):
    """Giá của 1 MÃ KÍNH theo báo giá hiện tại — KHỚP giá engine sẽ tính.

    Trả dict: `price`, `price_list`, `has_price`, `approx`, `note`,
    `row_name` (tên dòng Item Price, chỉ dùng cho log/support).

    - Đủ ngữ cảnh (inputs + dimension đã có giá trị) → tra ĐÚNG thuật toán
      composite của b2 (`price_for_code`) ⇒ `approx=False`.
    - Thiếu ngữ cảnh (chưa lưu biến, thiếu dimension…) → dòng Item Price thô
      + `approx=True` + `note` nói rõ "sẽ chốt khi hệ thống tính lại giá".

    `context_attempted=True`: caller ĐÃ thử dựng ngữ cảnh (kể cả khi kết quả
    là None) — ⛔ không thử lại (gọi nhiều nhóm sẽ lặp lại phần dựng đắt và
    nhân bản log lỗi).
    `params` (TUỲ CHỌN — phase 1.5): chỉ dùng khi caller KHÔNG truyền
    `context` — dựng ngữ cảnh từ trạng thái dialog thay vì đọc DB.
    """
    from alumglass.engine.bom_orchestrator import _default_price_list

    if not glass_code:
        return {"price": 0, "price_list": "", "has_price": False,
                "approx": False, "note": "", "row_name": ""}

    if context is not None:
        orch = context
    elif context_attempted:
        orch = None
    else:
        orch, _qi = _prepare_glass_price_context(quotation_item_name, params=params)

    if orch is not None:
        price_list = orch._active_price_list()
        # Dimension PHẢI lấy giống hệt b2 batch #2: `_category_by_code()` của
        # mã rồi `_dim_fieldnames_for_category()`. Mã kính thường KHÔNG phải
        # `item_code` của dòng BOM nào ⇒ category rỗng ⇒ engine áp TOÀN BỘ
        # mapping (nhánh `if not category` của `_dim_fieldnames_for_category`).
        # Dùng đúng biểu thức này mới ra CÙNG giá với engine.
        dim_fieldnames = orch._dim_fieldnames_for_category(
            orch._category_by_code().get(glass_code, ""))
        missing_dims = [v for v in dim_fieldnames
                        if orch.inputs.get(v) in (None, "")]
        if not missing_dims:
            price, price_list, row = orch.price_for_code(glass_code)
            # `has_price` = CÓ DÒNG GIÁ hợp lệ, ⛔ KHÔNG phải `price > 0`:
            # dòng Item Price = 0 đồng là giá THẬT (hàng tặng/kính giá 0) —
            # báo "chưa có giá" cho ca đó là nói sai và đẩy người dùng đi
            # kiểm bảng giá vô ích. `bool(price)` chỉ để giữ đúng ca FB
            # binding trả giá mà KHÔNG có dòng Item Price.
            has_price = row is not None or bool(price)
            return {
                "price": price,
                "price_list": price_list,
                "has_price": has_price,
                "approx": False,
                "note": "" if has_price else _glass_price_note_missing(price_list),
                "row_name": (row or {}).get("name") or "",
            }
        # Thiếu giá trị dimension → chưa áp được composite ⇒ nói rõ là xấp xỉ.
        price, row = orch.raw_price_row(glass_code, price_list)
    else:
        price_list = _default_price_list()
        price, row = _raw_glass_price_row(glass_code, price_list)

    # Cùng quy tắc: có DÒNG giá (kể cả rate = 0) ⇒ `has_price = true`.
    has_price = row is not None
    return {
        "price": price,
        "price_list": price_list,
        "has_price": has_price,
        "approx": True,
        # Có dòng giá nhưng CHƯA áp composite dimension → nói rõ là xấp xỉ.
        # Không có dòng giá → câu "chưa có giá" (việc cần làm rõ ràng hơn).
        "note": (_GLASS_PRICE_APPROX_NOTE if has_price
                 else _glass_price_note_missing(price_list)),
        "row_name": (row or {}).get("name") or "",
    }


@frappe.whitelist()
def get_glass_master_price(quotation_item_name, glass_code, params=None):
    """Giá của 1 mã kính theo ĐÚNG ngữ cảnh báo giá — dialog hỏi khi đổi kính.

    Trả `{success, code, name, price, price_list, has_price, approx, note}`.
    Giá PHẢI khớp giá engine sẽ tính (cùng inputs, cùng bảng giá, cùng thuật
    toán composite) — xem `_resolve_glass_price`.

    F1 — kiểm quyền ĐỌC trên Quotation cha của dòng báo giá trước khi tra.

    `params` (TUỲ CHỌN — phase 1.5): tham số dòng ĐANG NẰM TRÊN DIALOG
    (`_parse_preview_params`: `al_bom`, `al_bom_version`, `al_bom_vars`,
    `item_code`, `item_name`). Có params ⇒ tra giá theo biến người dùng đang
    sửa thay vì `al_bom_vars` trong DB. ⛔ Không truyền ⇒ hành vi y như trước.
    ⛔ Params KHÔNG được đổi bảng giá/tiền tệ: `_parse_preview_params` loại
    tường minh các khoá bối cảnh giá của máy chủ; ngữ cảnh giá dựng cho dòng
    ĐÃ LƯU nên Quotation cha luôn đọc từ DB; mã BOM/Version client gửi còn bị
    kiểm `read` (chống dùng API để dò giá của BOM ngoài quyền).
    """
    quotation_item_name = (quotation_item_name or "").strip()
    glass_code = (glass_code or "").strip()
    # Cổng quyền chạy TRƯỚC mọi xử lý tham số (tham số mới ⛔ không được là
    # đường vòng bỏ kiểm quyền).
    _require_quotation_item_permission(quotation_item_name, ptype="read")
    params = _parse_preview_params(params)

    # Cùng cổng với `preview_bom` (mục c): mã BOM/Version do CLIENT gửi lên
    # ⇒ phải đọc được chính chứng từ đó. Mã đọc từ DB của dòng đã lưu không
    # cần kiểm lại (đã bảo vệ bằng quyền `read` trên Quotation).
    if "al_bom" in params:
        _require_doc_read_permission(
            "AL BOM", params.get("al_bom"),
            " nên không xem được giá kính của mã BOM này")
    if "al_bom_version" in params:
        _require_doc_read_permission(
            "AL BOM Version", params.get("al_bom_version"),
            " nên không xem được giá kính của phiên bản BOM này")

    gm_rows = []
    if glass_code:
        gm_rows = frappe.get_all(
            "AL Glass Master", filters={"name": glass_code},
            fields=["name", "glass_name"])
    if not gm_rows:
        # Câu người đọc, ⛔ không phơi tên API/field kỹ thuật.
        return {"success": False, "message": "Không tìm thấy mã kính này."}

    glass_name = gm_rows[0].get("glass_name") or ""
    resolved = _resolve_glass_price(quotation_item_name, glass_code, params=params)
    return {
        "success": True,
        "code": glass_code,
        "name": glass_name,
        "price": resolved["price"],
        "price_list": resolved["price_list"],
        "has_price": resolved["has_price"],
        "approx": resolved["approx"],
        "note": resolved["note"],
    }


@frappe.whitelist()
def get_variable_set_for_bom(bom_code, quotation_item_name=None, params=None):
    """Lấy danh sách biến từ Variable Set của BOM.

    Flow: BOM → Bom Set → Variable Set → Variable Set Items + System vars từ Library.
    Mỗi variable được resolve từ AL Variable Library (source of truth — label, type,
    link_doctype, select_options, default_value), fallback về field denormalize của
    AL Variable Set Item nếu item không link tới Library record.
    Trả về list biến để JS dialog tự sinh form fields + thông tin BOM/Bom Set/Variable Set
    + thông tin mở rộng (Hệ profile, Hãng nhôm, Phụ kiện) cho phần read-only của dialog.

    F1 — `bom_code` do client truyền ⇒ kiểm quyền đọc AL BOM trước khi đọc.

    Pha 3 (hợp đồng dialog): `quotation_item_name` TUỲ CHỌN — truyền tên dòng
    báo giá đang mở để mỗi phần tử `glass_groups` mang thêm trạng thái thật
    của báo giá đó (`saved` / `effective_code` / `effective_source` /
    `effective_name` / `price` / `price_list` / `has_price` / `price_approx`).
    ⛔ Không truyền ⇒ các field này vẫn có mặt nhưng là trạng thái "chưa có
    báo giá" (giá 0, `price_approx=True`) — dialog cũ không vỡ hợp đồng.

    Phase 1.5 (2026-11-21): `params` TUỲ CHỌN — tham số dòng ĐANG NẰM TRÊN
    DIALOG (cùng whitelist với `preview_bom`). Preview ⛔ không ghi DB nữa,
    nên đọc `al_bom_vars` trong DB sẽ ra bản CŨ/rỗng; có params ⇒ dựng ngữ
    cảnh (biến, `glass_master_map`, `glass_master`, giá kính) từ CHÍNH trạng
    thái dialog. ⛔ Không truyền ⇒ giữ nguyên hành vi cũ (đọc DB).
    Dòng MỚI (`new-…`/không tên) + params ⇒ cần `parent` và bị kiểm quyền
    `read` trên Quotation cha (cùng cổng với `preview_bom`).
    """
    if not bom_code:
        return {"variables": []}

    # Cổng quyền chạy trước khi xử lý tham số nào — kiểm trên ĐÚNG bản ghi
    # `bom_code` (không phải cấp DOCTYPE): user có quyền đọc module nhưng bị
    # giới hạn theo bản ghi thì vẫn phải bị chặn, cùng nguyên tắc `preview_bom`.
    _require_doc_read_permission(
        "AL BOM", bom_code,
        " nên không lấy được danh sách biến của BOM này")

    params = _parse_preview_params(params)
    row_name = (quotation_item_name or "").strip()
    is_existing = bool(row_name) and not row_name.startswith("new-")

    # Cùng cổng với `preview_bom` (mục c): mã BOM/Version do CLIENT gửi trong
    # params ⇒ phải đọc được chính chứng từ đó (params có thể mở ngữ cảnh giá
    # theo một BOM/Version khác `bom_code`).
    if "al_bom" in params:
        _require_doc_read_permission(
            "AL BOM", params.get("al_bom"),
            " nên không xem được danh sách biến theo mã BOM này")
    if "al_bom_version" in params:
        _require_doc_read_permission(
            "AL BOM Version", params.get("al_bom_version"),
            " nên không xem được danh sách biến theo phiên bản BOM này")

    bom = frappe.get_cached_doc("AL BOM", bom_code)
    if not bom.bom_set:
        return {
            "bom_code": getattr(bom, "bom_code", bom_code),
            "bom_name": getattr(bom, "bom_name", ""),
            "bom_set": "",
            "bom_set_code": "",
            "bom_set_name": "",
            "variable_set_code": "",
            "variable_set_name": "",
            "profile_system_code": "",
            "profile_system_name": "",
            "brand": "",
            "accessory_set_code": "",
            "accessory_set_name": "",
            "variables": [],
        }

    bom_set = frappe.get_cached_doc("AL Bom Set", bom.bom_set)

    # ── Thông tin mở rộng: Hệ profile, Hãng nhôm, Phụ kiện (accessory set) ──
    # Bom Set thiếu field tương ứng → trả rỗng (dialog hiển thị "—"), không crash.
    profile_system_code = ""
    profile_system_name = ""
    if bom_set.get("profile_system"):
        try:
            ps = frappe.get_cached_doc("AL Profile System", bom_set.profile_system)
            profile_system_code = ps.system_code or bom_set.profile_system
            profile_system_name = ps.system_name or ""
        except frappe.DoesNotExistError:
            profile_system_code = bom_set.profile_system
            profile_system_name = ""

    # brand là Link → Brand (autoname theo brand name) → chính là tên hãng nhôm.
    brand = bom_set.get("brand") or ""

    accessory_set_code = ""
    accessory_set_name = ""
    if bom_set.get("default_accessory_set"):
        try:
            acc = frappe.get_cached_doc("AL Accessory Set", bom_set.default_accessory_set)
            accessory_set_code = acc.set_code or bom_set.default_accessory_set
            accessory_set_name = acc.set_name or ""
        except frappe.DoesNotExistError:
            accessory_set_code = bom_set.default_accessory_set
            accessory_set_name = ""

    variables = []

    # ── 1. User variables từ Variable Set (resolve từ Library) ────
    vs_code = ""
    vs_name = ""
    if bom_set.get("variable_set"):
        vs = frappe.get_cached_doc("AL Variable Set", bom_set.variable_set)
        vs_code = vs.set_code
        vs_name = vs.set_name
        for item in vs.items:
            # Link tới AL Variable Library → lấy record để resolve label/type/options
            lib = None
            if getattr(item, "variable", None):
                try:
                    lib = frappe.get_cached_doc("AL Variable Library", item.variable)
                except frappe.DoesNotExistError:
                    lib = None

            var_name = getattr(item, "variable", None) or getattr(item, "var_name", None) or ""
            var_label = (lib.var_label if lib else None) or item.var_label or var_name
            var_type = (lib.var_type if lib else None) or item.var_type or "Data"
            link_doctype = (lib.link_doctype if lib else None) or item.link_doctype or ""
            select_options = (lib.select_options if lib else None) or item.select_options or ""
            default_value = item.default_value or (lib.default_value if lib else "") or ""

            variables.append({
                "var_name": var_name,
                "var_label": var_label,
                "var_type": var_type,
                "link_doctype": link_doctype,
                "select_options": select_options,
                "default_value": default_value,
                "is_required": item.is_required or 0,
                "sort_order": item.sort_order or 0,
                "is_system": 0,
            })

    # ── 2. System variables từ AL Variable Library (DATA-DRIVEN) ──
    for sv in frappe.get_all("AL Variable Library",
                              filters={"is_system": 1},
                              fields=["var_name", "var_label", "var_type",
                                      "default_value", "description",
                                      "link_doctype", "select_options"]):
        variables.append({
            "var_name": sv["var_name"],
            "var_label": sv.get("var_label") or sv["var_name"],
            "var_type": sv.get("var_type") or "Float",
            "link_doctype": sv.get("link_doctype") or "",
            "select_options": sv.get("select_options") or "",
            "default_value": sv.get("default_value") or "",
            "is_required": 0,
            "sort_order": 999,
            "is_system": True,
        })

    # ── 2b. V6 P5 (Phase 1c): overlay giá trị hệ profile vào default_value của
    #     system vars — dialog hiển thị đúng giá trị theo profile đã chọn.
    #     Child table `system_variables` ưu tiên; phần field của profile đọc
    #     DATA-DRIVEN từ AL Variable Library (source_doctype="AL Profile
    #     System" + source_field) — trước đây map CỨNG 4 cặp offset_* và đã
    #     SAI tên (offset_crossbar→OFFSET_DO_NGANG là ca điển hình). Thêm
    #     biến hệ profile = thêm 1 record Library, không sửa code.
    if profile_system_code:
        try:
            ps_doc = frappe.get_cached_doc("AL Profile System", bom_set.profile_system)
            profile_vals = {}
            for row in ps_doc.get("system_variables") or []:
                if row.get("is_active") and row.get("value") not in (None, ""):
                    profile_vals[row.get("variable")] = row.get("value")

            profile_sys_vars = frappe.get_all(
                "AL Variable Library",
                filters={"is_system": 1, "source_doctype": "AL Profile System"},
                fields=["var_name", "source_field"],
            )
            for sv in profile_sys_vars:
                source_field = sv.get("source_field")
                if not source_field:
                    continue
                val = ps_doc.get(source_field)
                if val is not None and sv["var_name"] not in profile_vals:
                    profile_vals[sv["var_name"]] = val

            # Fallback 4 tên CŨ chỉ khi Library CHƯA có dòng nào map "AL Profile
            # System" (site chưa seed) — giữ dialog có giá trị như trước, và
            # tự hết hiệu lực ngay khi Library được seed.
            if not profile_sys_vars:
                for fname, vname in (
                    ("offset_frame", "OFFSET_FRAME"),
                    ("offset_glass", "OFFSET_GLASS"),
                    ("offset_fixed", "OFFSET_FIXED"),
                    ("offset_crossbar", "OFFSET_DO_NGANG"),
                ):
                    val = ps_doc.get(fname)
                    if val is not None and vname not in profile_vals:
                        profile_vals[vname] = val

            for v in variables:
                if v.get("var_name") in profile_vals:
                    v["default_value"] = profile_vals[v["var_name"]]
        except frappe.DoesNotExistError:
            pass

    # ── 2c. V6 P10: đánh dấu biến nào là Pricing Dimension (DATA-DRIVEN) ──
    # Lấy trực tiếp từ AL Variable Dimension Mapping — bảng này VỐN ĐÃ là
    # nguồn cấu hình duy nhất cho "biến X là 1 dimension tra giá", được dùng
    # bởi cả BomOrchestrator (engine/bom_orchestrator.py) lẫn
    # fb_handlers.aluminum_price_composite. Dialog (quotation.js _var_to_field)
    # không tự quyết định/hardcode tên biến nữa — chỉ đọc cờ này. Thêm
    # dimension mới (kể cả cho kính) = thêm 1 record Mapping, KHÔNG cần sửa
    # code JS.
    _pricing_dim_vars = set(
        frappe.get_all("AL Variable Dimension Mapping", filters={"is_active": 1}, pluck="variable_name")
    )
    for v in variables:
        v["is_pricing_dimension"] = v.get("var_name") in _pricing_dim_vars

    # ── 3. V6 P11 — glass_groups: MỖI dòng KINH luôn có đúng 1 selector độc
    # lập trong "Kính theo vị trí", KHÔNG bắt buộc phải cấu hình sẵn
    # `default_glass_master` trên AL Bom Set (xem glass_group_resolver.py để
    # hiểu công thức rep — PHẢI khớp 100% với bom_orchestrator.py).
    from alumglass.al_bom_engine.glass_group_resolver import glass_group_rep
    from alumglass.al_bom_engine.glass_group_resolver import fetch_glass_category_codes

    glass_groups = []
    _seen_rep = set()
    slug_labels_kinh = _get_slug_labels()
    _glass_cats = fetch_glass_category_codes(
        {it.get("category", "") for it in bom_set.get("items", []) or [] if it.get("category")})

    # ── 3b. Pha 3 + phase 1.5 — trạng thái THẬT của kính cho báo giá đang mở.
    # `saved`/`glass_master` đọc từ `al_bom_vars`; phần effective/giá dùng
    # CHUNG đường với engine (xem `_resolve_glass_price`).
    # Thứ tự nguồn (phase 1.5):
    #   1. `params` client gửi (trạng thái DIALOG — preview không ghi DB nữa)
    #   2. dòng ĐÃ LƯU ⇒ đọc `al_bom_vars` trong DB (hành vi cũ)
    #   3. ⛔ không có gì ⇒ hợp đồng cũ: field mới có mặt nhưng giá 0.
    _saved_glass_map = {}
    _glass_override_code = ""
    _glass_price_context = None
    if params:
        # Dòng mới (chưa có tên) ⇒ cổng quyền trên Quotation cha, y hệt
        # `preview_bom`: dòng chưa tồn tại thì không có quyền nào để hỏi trên
        # chính nó. Dòng đã lưu vẫn đi qua `_require_quotation_item_permission`
        # bên dưới — params ⛔ không được thay cổng đó.
        if not is_existing:
            _require_quotation_permission(
                params.get("parent"), ptype="read")
        elif row_name:
            _require_quotation_item_permission(row_name, ptype="read")

        _vars = _bom_vars_dict(params.get("al_bom_vars"))
        _saved_map = _vars.get("glass_master_map")
        if isinstance(_saved_map, dict):
            _saved_glass_map = _saved_map
        _glass_override_code = _vars.get("glass_master") or ""
        _glass_price_context, _qi_doc = _prepare_glass_price_context(
            row_name if is_existing else None, params=params)
    elif is_existing:
        # Quyền: cùng cổng `read` trên Quotation cha như calculate_bom.
        _require_quotation_item_permission(row_name, ptype="read")
        try:
            _qi = frappe.get_doc("Quotation Item", row_name)
            _raw_vars = _qi.get("al_bom_vars")
            _vars = json.loads(_raw_vars) if isinstance(_raw_vars, str) and _raw_vars else {}
            if isinstance(_vars, dict):
                _saved_map = _vars.get("glass_master_map")
                if isinstance(_saved_map, dict):
                    _saved_glass_map = _saved_map
                _glass_override_code = _vars.get("glass_master") or ""
        except (frappe.DoesNotExistError, ValueError):
            # `al_bom_vars` hỏng JSON / dòng đã bị xoá ⇒ coi như "chưa chọn gì"
            # (đường tra giá vẫn chạy; ⛔ không làm sập cả dialog).
            _saved_glass_map = {}
            _glass_override_code = ""
        # ⛔ KHÔNG unpack vào `_`: `_` là hàm dịch của Frappe (`from frappe import _`)
        # — gán vào nó biến CỤC BỘ che mất hàm dịch của CẢ hàm này, mọi `_("…")`
        # phía sau (kể cả trong closure `_add_color_group`) nổ
        # "'QuotationItem' object is not callable".
        _glass_price_context, _qi_doc = _prepare_glass_price_context(row_name)

    for item in bom_set.get("items", []) or []:
        if item.get("category") not in _glass_cats:
            continue
        rep, is_real_master = glass_group_rep(item)
        if rep in _seen_rep:
            continue
        _seen_rep.add(rep)

        if is_real_master:
            label = rep
            try:
                gm = frappe.get_cached_doc("AL Glass Master", rep)
                label = gm.glass_name or rep
            except frappe.DoesNotExistError:
                pass
            default_val = rep
        else:
            slug = item.get("slug") or ""
            # Nhãn nhóm chọn kính, ưu tiên dữ liệu NGƯỜI ĐỌC: nhãn slug library
            # → tên dòng BOM → tên vật tư. Slug chỉ là chốt cuối (kỹ thuật).
            label = slug_labels_kinh.get(slug) or item.get("line_name") or ""
            if not label and item.get("item_code"):
                try:
                    label = frappe.get_cached_value(
                        "Item", item["item_code"], "item_name") or ""
                except frappe.DoesNotExistError:
                    label = ""
            label = label or slug
            default_val = ""  # không có mã mặc định — bắt buộc user tự chọn

        # ── Mã kính engine SẼ dùng cho báo giá này (ĐÚNG thứ tự ưu tiên của
        # `BomOrchestrator._resolve_glass_override`): đã chọn ở dialog →
        # override global cũ → mặc định khai trên dòng BOM → item_code dòng.
        saved_code = _saved_glass_map.get(rep) or ""
        if saved_code:
            effective_code, effective_source = saved_code, "saved"
        elif _glass_override_code:
            effective_code, effective_source = _glass_override_code, "override"
        elif is_real_master:
            effective_code, effective_source = rep, "bom_default"
        elif item.get("item_code"):
            effective_code, effective_source = item["item_code"], "item_code"
        else:
            effective_code, effective_source = "", "none"

        glass_groups.append({
            "rep": rep,
            "label": label,
            "default": default_val,
            "slug": item.get("slug") or "",
            "is_real_master": is_real_master,
            "saved": saved_code,
            "effective_code": effective_code,
            "effective_source": effective_source,
            # Mã engine sẽ dùng có là AL Glass Master THẬT không — điền ở
            # mục 3c (đã query sẵn bảng đó, ⛔ không thêm query). Cờ này để
            # dialog KHÔNG nhét mã giữ chỗ (`item_code` dòng BOM, VD KINH-01)
            # vào control Link → AL Glass Master (giá trị không có trong
            # danh mục, người dùng hiểu là lỗi).
            "effective_is_glass_master": False,
            "effective_name": "",
            "price": 0,
            "price_list": "",
            "has_price": False,
            "price_approx": not bool(_glass_price_context),
        })

    # ── 3c. Bổ sung TÊN + GIÁ cho từng nhóm — batch, ⛔ không N+1 ─────
    if glass_groups:
        _codes = sorted({g["effective_code"] for g in glass_groups
                         if g["effective_code"]})
        _names = {}
        _glass_master_codes = set()
        if _codes:
            for gm in frappe.get_all(
                    "AL Glass Master", filters={"name": ("in", _codes)},
                    fields=["name", "glass_name"]):
                # Có record ⇒ mã THẬT là glass master (cờ cho dialog).
                _glass_master_codes.add(gm["name"])
                if gm.get("glass_name"):
                    _names[gm["name"]] = gm["glass_name"]
            _missing_names = [c for c in _codes if c not in _names]
            if _missing_names:
                for it in frappe.get_all(
                        "Item", filters={"name": ("in", _missing_names)},
                        fields=["name", "item_name"]):
                    if it.get("item_name"):
                        _names[it["name"]] = it["item_name"]
        for group in glass_groups:
            code = group["effective_code"]
            group["effective_is_glass_master"] = bool(
                code) and code in _glass_master_codes
            group["effective_name"] = _names.get(code, "") if code else ""
            price_info = _resolve_glass_price(
                row_name or None, code, context=_glass_price_context,
                context_attempted=bool(params) or bool(row_name))
            group["price"] = price_info["price"]
            group["price_list"] = price_info["price_list"]
            group["has_price"] = price_info["has_price"]
            group["price_approx"] = price_info["approx"]

    # ── 4. Q2 — color_groups: "Màu sắc theo vị trí", nhóm theo
    # material_category (Nhôm/Kính/Phụ kiện/Vật tư phụ...) để dialog vẽ
    # section riêng cho từng nhóm. Dòng KHÔNG cấu hình `default_color`
    # (color_group_rep trả None) = luôn dùng 1 màu cố định — KHÔNG có
    # selector (khác glass_groups: không có fallback theo slug, vì đây là
    # lựa chọn CÓ CHỦ ĐÍCH của admin, không phải thiếu cấu hình).
    from alumglass.al_bom_engine.color_group_resolver import color_group_rep

    color_groups = []
    _seen_color_rep = set()
    _category_label_cache = {}

    def _category_label(code):
        if not code:
            return ""
        if code not in _category_label_cache:
            try:
                _category_label_cache[code] = (
                    frappe.get_cached_doc("AL Material Category", code).category_name or code
                )
            except frappe.DoesNotExistError:
                _category_label_cache[code] = code
        return _category_label_cache[code]

    def _add_color_group(item, category_code, category_label):
        rep = color_group_rep(item)
        if not rep or rep in _seen_color_rep:
            return
        _seen_color_rep.add(rep)
        label = rep
        try:
            cs = frappe.get_cached_doc("AL Color Standard", rep)
            label = cs.color_name or rep
        except frappe.DoesNotExistError:
            pass
        color_groups.append({
            "rep": rep,
            "label": label,
            "default": rep,
            "slug": item.get("slug") or "",
            "category": category_code,
            "category_label": category_label or _("Khác"),
        })

    for item in bom_set.get("items", []) or []:
        cat_code = item.get("category") or ""
        _add_color_group(item, cat_code, _category_label(cat_code))

    # Phụ kiện: KHÔNG nằm trong bom_set.items — đọc riêng từ AL Accessory Set
    # (dùng đúng bộ đã resolve accessory_set_code ở trên).
    if bom_set.get("default_accessory_set"):
        from alumglass.al_bom_engine.fb_config import get_named_constant
        accessory_category_code = get_named_constant("DEFAULT_ACCESSORY_CATEGORY", default="")
        try:
            acc_doc = frappe.get_cached_doc("AL Accessory Set", bom_set.default_accessory_set)
            for acc_item in (acc_doc.get("items") or []):
                _add_color_group(acc_item, accessory_category_code, _("Phụ kiện"))
        except frappe.DoesNotExistError:
            pass

    return {
        "bom_code": getattr(bom, "bom_code", bom_code),
        "bom_name": getattr(bom, "bom_name", ""),
        "bom_set": bom.bom_set,
        "bom_set_code": bom_set.set_code,
        "bom_set_name": bom_set.set_name,
        "variable_set_code": vs_code,
        "variable_set_name": vs_name,
        "profile_system_code": profile_system_code,
        "profile_system_name": profile_system_name,
        "brand": brand,
        "accessory_set_code": accessory_set_code,
        "accessory_set_name": accessory_set_name,
        # V6 Phase 1: thông tin sản phẩm (ảnh + mã) cho đầu dialog
        "representative_item": getattr(bom, "representative_item", ""),
        "item_code": _get_item_code(bom),
        "item_name": _get_item_name(bom),
        "item_image": _get_item_image(bom),
        # V6 Phase 1: Cost Template (default) cho field editable
        "cost_template": getattr(bom, "default_cost_template", ""),
        "cost_template_code": _get_cost_template_code(bom),
        "cost_template_name": _get_cost_template_name(bom),
        "glass_groups": glass_groups,
        "color_groups": color_groups,
        "variables": sorted(variables, key=lambda v: (
            v.get("is_system", False), v.get("sort_order", 0))),
    }


def _get_item_code(bom):
    """Mã sản phẩm: ưu tiên representative_item của BOM → Item.item_code."""
    rep = getattr(bom, "representative_item", "")
    if not rep:
        return ""
    try:
        return frappe.db.get_value("Item", rep, "item_code") or rep
    except Exception:
        return rep


def _get_item_name(bom):
    rep = getattr(bom, "representative_item", "")
    if not rep:
        return ""
    try:
        return frappe.db.get_value("Item", rep, "item_name") or ""
    except Exception:
        return ""


def _get_item_image(bom):
    """Ảnh sản phẩm: Item.image → fallback attachment đầu tiên."""
    rep = getattr(bom, "representative_item", "")
    if not rep:
        return ""
    try:
        img = frappe.db.get_value("Item", rep, "image") or ""
        if img:
            return img
        files = frappe.get_list(
            "File",
            filters={"attached_to_doctype": "Item", "attached_to_name": rep},
            fields=["file_url"], order_by="creation", limit=1,
        )
        return (files[0].get("file_url") or "") if files else ""
    except Exception:
        return ""


def _get_cost_template_code(bom):
    ct = getattr(bom, "default_cost_template", "")
    if not ct:
        return ""
    try:
        return frappe.db.get_value("AL Cost Template", ct, "template_code") or ct
    except Exception:
        return ct


def _get_cost_template_name(bom):
    ct = getattr(bom, "default_cost_template", "")
    if not ct:
        return ""
    try:
        return frappe.db.get_value("AL Cost Template", ct, "template_name") or ""
    except Exception:
        return ""


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def product_item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
    """Server-side query cho Link field "Mã sản phẩm" (PA B).

    Trả về Item thuộc Item Group `SAN_PHAM` + MỌI group con của nó (lọc theo
    cây Item Group qua `lft/rgt`). Owner chốt PA B 2026-08-23 — thay filter JS
    `{item_group: "SAN_PHAM"}` đơn giản bằng phương thức này.

    Ghi chú data cũ (đã chốt): Item NHOM-XINGFA thuộc group NHOM_XINGFA (vật
    liệu nhôm) sẽ KHÔNG search lại được trong dropdown — Owner chấp nhận.

    Contract giống `erpnext.controllers.queries.item_query`: được gọi qua
    `frappe.desk.search.search_widget` với tham số
    (doctype, txt, searchfield, start, page_length, filters, as_dict).
    Trả list tuple/rows tương thích `build_for_autosuggest`.
    """
    doctype = "Item"
    txt = txt or ""

    # ── 1. Tập Item Group: SAN_PHAM + mọi group con (qua lft/rgt) ──
    san_pham = frappe.db.exists("Item Group", "SAN_PHAM")
    group_names = [san_pham]
    if san_pham:
        root = frappe.get_cached_doc("Item Group", san_pham)
        # Descendants: lft > root.lft AND rgt < root.rgt (group con + cháu...).
        # Exclude chính root (vì đã có) — nhưng không bắt buộc; để "in" trùng vô hại.
        descendants = frappe.get_all(
            "Item Group",
            filters={"lft": [">", root.lft], "rgt": ["<", root.rgt]},
            pluck="name",
        )
        group_names += descendants

    # ── 2. Item trong các group đó (name = item_code) ──
    items = frappe.get_all(
        "Item",
        filters={
            "item_group": ["in", group_names],
            "disabled": 0,
            "has_variants": 0,
        },
        fields=["name", "item_name"],
        order_by="name",
        limit_page_length=page_len,
    )

    # ── 3. Lọc theo txt (item_code / item_name chứa txt) ──
    txt_lower = txt.lower()
    filtered = [
        it for it in items
        if not txt or txt_lower in (it["name"] or "").lower()
        or txt_lower in (it["item_name"] or "").lower()
    ]

    if as_dict:
        return filtered
    return [(it["name"], it["item_name"] or "") for it in filtered]


# ══════════════════════════════════════════════════════════════════════
# V6 Phase 2 — get_result_display: display model cho renderer dùng chung
# ══════════════════════════════════════════════════════════════════════
# Trả về cấu trúc hiển thị (label + công thức + trace) từ al_bom_result
# đã lưu. KHÔNG tính lại — ItemParamDialog (preview) và BOMDialog (kết quả)
# cùng gọi hàm này + renderer JS dùng chung → không duplicate label logic.
# ──────────────────────────────────────────────────────────────────────

import re as _re

# Biến formula thường viết hoa (VL_NHOM) nhưng cũng có dạng W_mm/H_mm (chữ
# thường phần sau) và installation_height_m (chữ thường đầu). Dùng [A-Za-z_]
# làm ký tự đầu + skip hàm/filter bên dưới để không nhầm lookup_rule/roundup.
_TRACE_TOKEN = _re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{1,40})\b")
_TRACE_SKIP = ("TONG_", "GIA_", "PROFIT", "VAT", "DON_GIA", "NC_", "OH_", "CP")


def _get_slug_labels():
    """slug → label (AL Slug Library). Trả về {} nếu chưa có doctype/record."""
    try:
        return {
            r["slug"]: r["label"] for r in frappe.get_all(
                "AL Slug Library", fields=["slug", "label"])
        }
    except Exception:
        return {}


def _get_bucket_names():
    """bucket_code → bucket_name (AL Cost Bucket)."""
    try:
        return {
            r["bucket_code"]: r["bucket_name"] for r in frappe.get_all(
                "AL Cost Bucket", fields=["bucket_code", "bucket_name"])
        }
    except Exception:
        return {}


def _get_cost_template_display(qi):
    """line_code → {label, formula, bucket} từ cost_template_snapshot.

    Đọc SNAPSHOT của version pin (nguồn công thức THỰC ĐÃ DÙNG), không đọc
    AL Cost Template live (tránh lệch khi template đổi sau khi pin version).
    """
    out = {}
    version_name = qi.get("al_bom_version")
    if not version_name and qi.get("al_bom"):
        version_name = frappe.db.get_value("AL BOM", qi.al_bom, "current_version")
    if not version_name:
        return out
    snap_raw = frappe.get_cached_value(
        "AL BOM Version", version_name, "cost_template_snapshot")
    if not snap_raw:
        return out
    try:
        snap = json.loads(snap_raw) if isinstance(snap_raw, str) else snap_raw
    except (ValueError, TypeError):
        return out
    for item in snap.get("items", []) or []:
        code = item.get("line_code", "")
        if not code:
            continue
        out[code] = {
            "label": item.get("line_label") or code,
            "formula": item.get("calc_formula", "") or "",
            "bucket": item.get("cost_bucket", "") or "",
        }
    return out


def _build_trace(formula, ctx):
    """Trace dạng HTML-safe string: formula → thay token bằng giá trị.

    V6 P8 (Phase 1e): thay MỌI token có giá trị số trong ctx (kể cả line-code
    cost template / bucket — chính là giá trị đã resolve) → trace đọc được
    "8% × TONG_VL(1,000,000) = 80,000" (JS renderer định dạng % + dấu phẩy).
    Fallback display cho data cũ chưa có cost_template_trace lưu sẵn.
    Token không có trong ctx → giữ nguyên tên (trailing input / lookup_rule).
    """
    if not formula:
        return ""

    def _sub(m):
        token = m.group(1)
        if token in ctx and isinstance(ctx[token], (int, float)):
            val = ctx[token]
            if isinstance(val, float):
                val = round(val, 4)
            return f"{token}={val}"
        return token

    return _TRACE_TOKEN.sub(_sub, formula)


# Câu msgid (dịch lúc ném lỗi — `_()` ở đây chạy trong REQUEST, ⛔ không lúc
# import module, để không phụ thuộc thứ tự nạp frappe).
_RESULT_JSON_BROKEN_MESSAGE = (
    "Kết quả tính giá lưu trên dòng này bị hỏng nên không hiển thị được — "
    "không phải do bạn nhập sai. Bấm \"Preview tính giá\" để tính lại."
)


def _parse_result_json_arg(result_json):
    """Chuỗi JSON kết quả do client gửi lên → dict.

    Nguồn: `al_bom_result` ĐANG NẰM TRÊN DÒNG Quotation Item phía client (dialog
    mở lại đọc từ dòng, ⛔ không đọc DB). Chấp nhận cả dict (Frappe tự parse khi
    form gửi object) lẫn chuỗi JSON.

    JSON hỏng/nội dung không phải object ⇒ `frappe.throw` CÂU người-đọc-được
    (ValidationError = HTTP 417): ⛔ không 500, ⛔ không phơi traceback hay
    thông điệp `json.loads` kỹ thuật.
    """
    if isinstance(result_json, dict):
        return result_json
    try:
        data = json.loads(result_json or "{}")
    except (ValueError, TypeError):
        frappe.throw(_(_RESULT_JSON_BROKEN_MESSAGE), frappe.ValidationError)
    if not isinstance(data, dict):
        frappe.throw(_(_RESULT_JSON_BROKEN_MESSAGE), frappe.ValidationError)
    return data


@frappe.whitelist()
def get_result_display(quotation_item_name, result_json=None):
    """Display model cho renderer dùng chung (Phase 2 — A4 + B).

    Args:
        quotation_item_name: tên Quotation Item đã có al_bom_result.
        result_json: (tuỳ chọn) chuỗi JSON kết quả ĐANG NẰM TRÊN DÒNG Quotation
            Item phía client. Khi truyền, dựng display từ CHÍNH chuỗi đó thay vì
            đọc `al_bom_result` trong DB — mở lại dialog phải thấy đúng kết quả
            của dòng, kể cả khi dòng mới hơn bản đã lưu. Không truyền ⇒ giữ
            nguyên hành vi cũ (đọc DB).

    Returns:
        {
          "summary": {gia_vat, gia_ban, line_count, calculated},
          "lines": [{slug, label, line_label, item_name, item_code,
                     item_selection_mode, width, height, qty, unit_qty,
                     total_qty, unit_price, line_total, cost_bucket,
                     bucket_name}],
          "buckets": [{bucket_code, bucket_name, value}],
          "cost_template": [{line_code, line_label, calc_formula, value,
                             is_subtotal, bucket_code, bucket_name, trace}],
          "errors": {bom_items, cost_template}
        }

    D1 — endpoint này trả TOÀN BỘ giá thành + công thức (`calc_formula`) + trace
    của mọi dòng báo giá ⇒ phải có quyền `read` trên Quotation cha, nếu không
    bất kỳ user đã đăng nhập nào cũng đọc được bí mật giá thành.
    """
    _require_quotation_item_permission(quotation_item_name, ptype="read")

    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    if result_json:
        # JSON do client gửi lên (đọc từ dòng) → dựng display từ đó. Hỏng thì
        # báo CÂU người-đọc-được (frappe.throw = 417, ⛔ không 500, ⛔ không
        # phơi traceback) kèm lối xử lý, thay vì hiện panel trống khó hiểu.
        data = _parse_result_json_arg(result_json)
    else:
        raw = qi.get("al_bom_result")
        data = {}
        if raw:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                data = {}

    slug_labels = _get_slug_labels()
    bucket_names = _get_bucket_names()
    template_display = _get_cost_template_display(qi)

    # ── Lines ──
    # V6 P8 (Phase 1e): pass-through unit/weight_per_unit/has_weight/trace —
    # renderer cột ĐVT/Trọng lượng + trace line vật tư. Data cũ thiếu → "—".
    lines = []
    for ln in data.get("lines", []) or []:
        slug = ln.get("slug", "") or ""
        bk = ln.get("cost_bucket", "") or ""
        lines.append({
            "slug": slug,
            # Nhãn dòng: ưu tiên tên slug (AL Slug Library) → nhãn dòng do
            # cấu hình BOM đặt → tên vật tư. ⛔ Fallback về `slug` trần —
            # không có nhãn đọc được thì để "" cho client tự hiện câu chung
            # ("dòng vật tư"), vì slug là mã kỹ thuật của người cấu hình.
            "label": (slug_labels.get(slug) or ln.get("line_label")
                      or ln.get("item_name") or ""),
            # Pass-through 2 nguồn của `label` — client cần bản gốc để hiển
            # thị riêng (vd "Dòng 3 — Nẹp") mà ⛔ phải tự đoán từ `label`.
            "line_label": ln.get("line_label", "") or "",
            "item_name": ln.get("item_name", "") or "",
            "item_code": ln.get("item_code", "") or "",
            # `Rule` / `Fixed` / `Formula` — client dùng để biết dòng chọn mã
            # theo QUY TẮC (nhánh hiện "Chưa tra được mã" + hộp giải thích).
            # Thiếu khoá này thì nhánh `item_selection_mode === "Rule"` phía
            # client là nhánh CHẾT ⇒ dòng Rule thiếu mã hiện slug.
            "item_selection_mode": ln.get("item_selection_mode", "") or "",
            "width": ln.get("width", 0),
            "height": ln.get("height", 0),
            "qty": ln.get("qty", 0),
            "unit_qty": ln.get("unit_qty", 0),
            "total_qty": ln.get("total_qty", 0),
            "unit_price": ln.get("unit_price", 0),
            "line_total": ln.get("line_total", 0),
            "cost_bucket": bk,
            "bucket_name": bucket_names.get(bk, bk),
            "unit": ln.get("unit", "") or "",
            "weight_per_unit": ln.get("weight_per_unit", 0) or 0,
            "has_weight": 1 if ln.get("has_weight") else 0,
            "trace": ln.get("trace", "") or "",
            # Q2: màu sắc (đã resolve theo vị trí) + nơi cấp vật tư/vị trí lắp
            # đặt/góc cắt/ghi chú — khai báo tĩnh trên AL Bom Item/AL Accessory
            # Item, pass-through nguyên văn (không cần resolve label thêm).
            "color": ln.get("color", "") or "",
            "supplier_location": ln.get("supplier_location", "") or "",
            "install_position": ln.get("install_position", "") or "",
            "cut_angle": ln.get("cut_angle", "") or "",
            "note": ln.get("note", "") or "",
            # Phase 2 (2026-11-20): vết tra cứu — pass-through, data cũ thiếu
            # key ⇒ "" (client bỏ qua). Xem API `explain_bom_line` để biết
            # từng bước giải thích.
            "rule_trace": ln.get("rule_trace", "") or "",
            "price_trace": ln.get("price_trace", "") or "",
            # §7.6 — trạng thái nguồn tra của dòng. Client hiện "Chưa tra được
            # mã" theo cờ, ⛔ tự dò chữ trong `rule_trace` (câu sẽ đổi).
            # Data cũ thiếu key ⇒ 0/""/False (coi như bình thường).
            "rule_input_label": ln.get("rule_input_label", "") or "",
            "rule_input_found": bool(ln.get("rule_input_found")),
            "rule_input_missing": 1 if ln.get("rule_input_missing") else 0,
            "rule_source_missing": 1 if ln.get("rule_source_missing") else 0,
            "rule_missing_reason": ln.get("rule_missing_reason", "") or "",
            # Căn cứ SỐ LƯỢNG khi qty formula dùng `lookup_rule(...)` dạng
            # đơn giản — data cũ thiếu key ⇒ "" (client bỏ qua).
            "qty_rule_trace": ln.get("qty_rule_trace", "") or "",
            "qty_rule_trace_raw": ln.get("qty_rule_trace_raw", "") or "",
        })

    # ── Buckets ──
    buckets = []
    for code, val in (data.get("buckets", {}) or {}).items():
        buckets.append({
            "bucket_code": code,
            "bucket_name": bucket_names.get(code, code),
            "value": val,
        })

    # ── Cost Template ──
    ctx = dict(data.get("buckets", {}) or {})
    ctx.update(data.get("cost_template", {}) or {})
    # Gộp thêm biến đầu vào từ al_bom_vars (W_mm/H_mm/installation_height_m...)
    # → trace dễ đọc hơn. Chỉ lấy giá trị số; bỏ các key cấu hình dạng _x.
    try:
        _vars = json.loads(qi.get("al_bom_vars") or "{}") if isinstance(
            qi.get("al_bom_vars"), str) else (qi.get("al_bom_vars") or {})
    except (ValueError, TypeError):
        _vars = {}
    for _k, _v in _vars.items():
        if _k.startswith("_") or _k in ("extra_vars", "accessory_set", "glass_master",
                                          "glass_master_map", "color_master_map", "aluminum_color"):
            continue
        if isinstance(_v, (int, float)) and not isinstance(_v, bool):
            ctx.setdefault(_k, _v)
    _extra = _vars.get("extra_vars") if isinstance(_vars, dict) else {}
    if isinstance(_extra, dict):
        for _k, _v in _extra.items():
            if isinstance(_v, (int, float)) and not isinstance(_v, bool):
                ctx.setdefault(_k, _v)
    # V6 P8 (Phase 1e): ưu tiên trace LƯU SẴN từ engine (build lúc tính với ctx
    # đầy đủ) → fallback build tại display cho data cũ. cost_template_units
    # (line_code → ĐVT) pass-through — seed chưa có, hiển thị "—".
    stored_trace = data.get("cost_template_trace", {}) or {}
    stored_units = data.get("cost_template_units", {}) or {}
    cost_template = []
    ct_map = data.get("cost_template", {}) or {}
    for code, val in ct_map.items():
        ti = template_display.get(code, {})
        bk = ti.get("bucket", "") or ""
        is_subtotal = code.startswith(("TONG_", "GIA_")) or code in ("PROFIT",) or code.startswith("VAT")
        cost_template.append({
            "line_code": code,
            "line_label": ti.get("label") or code,
            "calc_formula": ti.get("formula", "") or "",
            "value": val,
            "is_subtotal": is_subtotal,
            "bucket_code": bk,
            "bucket_name": bucket_names.get(bk, bk),
            "unit": stored_units.get(code, "") or "",
            "trace": stored_trace.get(code) or _build_trace(
                ti.get("formula", "") or "", ctx),
        })

    return {
        "summary": {
            "gia_vat": data.get("gia_vat", 0),
            # D7: ưu tiên gia_ban resolve theo cờ (engine lưu khi tính). Data
            # cũ (pre-D7) thiếu key → fallback GIA_BAN như hành vi trước đây.
            "gia_ban": data.get("gia_ban",
                                (data.get("cost_template") or {}).get("GIA_BAN", 0)),
            "line_count": len(lines),
            "calculated": bool(data.get("lines") or data.get("cost_template")),
        },
        "lines": lines,
        "buckets": buckets,
        "cost_template": cost_template,
        # V6 P8: ĐVT cost template (line_code → unit) — seed chưa có → renderer "—"
        "cost_template_units": dict(stored_units),
        # F2 — giữ nguyên `errors` engine lưu trong al_bom_result
        # ({bom_items: {...}, cost_template: {...}}); thiếu → {} cho client.
        "errors": data.get("errors", {}) or {},
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 2 (2026-11-20) — Giải thích 1 dòng kết quả tính giá
# ══════════════════════════════════════════════════════════════════════
def _fmt_number(value):
    """Số kiểu Việt Nam: 50000 → "50.000", 6.6 → "6,6"."""
    if value is None or isinstance(value, bool):
        return "—"
    if isinstance(value, (int, float)):
        rounded = round(float(value), 4)
        if rounded == int(rounded):
            return "{:,}".format(int(rounded)).replace(",", ".")
        return ("{:,.4f}".format(rounded).rstrip("0").rstrip(".")
                .replace(",", "|").replace(".", ",").replace("|", "."))
    text = str(value).strip()
    return text or "—"


def _fmt_money(value):
    text = _fmt_number(value)
    return text if text == "—" else text + " đ"


def _fmt_with_unit(value, unit):
    text = _fmt_number(value)
    return text if text == "—" else text + (unit or "")


def _glass_detail(line):
    """Câu mô tả thông số kính ĐÃ LƯU — nhãn người đọc.

    ⛔ Không phơi mã enum (`glass_type` là Link) hay docname; tên kính/loại
    kính lấy từ engine đã resolve sẵn trong `al_bom_result`.
    """
    if not line:
        return ""
    glass_master = line.get("glass_master") or ""
    glass_name = line.get("glass_master_name") or ""
    # Đọc cả 2 tên (dữ liệu cũ chỉ có một trong hai).
    thick = (line.get("total_thick_mm") or line.get("glass_thick") or 0)
    glass_type_name = line.get("glass_type_name") or ""
    max_area = line.get("max_area_m2", 0) or 0
    if not (glass_master or glass_name or thick or glass_type_name or max_area):
        return ""
    if glass_name and glass_master:
        source = 'Kính "%s" (mã %s)' % (glass_name, glass_master)
    elif glass_name:
        source = 'Kính "%s"' % glass_name
    elif glass_master:
        source = "Kính (mã %s)" % glass_master
    else:
        source = "Kính đã chọn"
    bits = []
    if thick:
        bits.append("độ dày %s" % _fmt_with_unit(thick, " mm"))
    if glass_type_name:
        bits.append('loại "%s"' % glass_type_name)
    if max_area:
        bits.append("khổ tối đa %s" % _fmt_with_unit(max_area, " m²"))
    if not bits:
        return source + "."
    return "%s: %s." % (source, ", ".join(bits))


@frappe.whitelist()
def explain_bom_line(quotation_item_name, slug, result_json=None, parent=None):
    """Giải thích 1 dòng đã tính giá, đọc từ `al_bom_result` đã lưu.

    ⛔ KHÔNG tính lại engine: mọi số liệu lấy từ JSON kết quả. Nhờ vậy phần
    giải thích luôn khớp đúng con số người dùng đang thấy, kể cả khi cấu hình
    BOM đã đổi sau lần tính.

    `result_json` (TUỲ CHỌN — phase 1.5): chuỗi `al_bom_result` ĐANG NẰM TRÊN
    DÒNG phía client (cùng hợp đồng với `get_result_display`). Có ⇒ giải thích
    từ CHÍNH kết quả đó, vì preview ⛔ không ghi DB nên bản trong DB có thể CŨ
    hơn kết quả người dùng đang thấy (thậm chí chưa từng có). ⛔ Không truyền
    ⇒ giữ nguyên hành vi cũ (đọc DB).
    `parent` (TUỲ CHỌN): Quotation cha — CHỈ dùng cho dòng MỚI (chưa có tên
    trong DB) để kiểm quyền `read`. Dòng đã lưu ⇒ luôn kiểm trên cha thật của
    dòng, ⛔ không tin `parent` client gửi.

    Chuỗi trả về là chuỗi HIỂN THỊ: nhãn nghiệp vụ đã resolve, ⛔ không có
    slug/mã rule/biểu thức/docname Item Price. Dữ liệu kỹ thuật nằm trong
    `al_bom_result` (`rule_trace_raw`, `price_trace_raw`) cho support.

    Returns:
        {"success": True, "slug", "label", "item_code", "line_total",
         "steps": [{"step", "key", "title", "detail", "severity"?}, ...],
         "missing": [<key của bước thiếu>],
         "warn_zero_price": <True CHỈ khi line_total = 0 VÀ có bước
                            `severity: "warning"` — vd engine không tra được
                            dòng giá, đang tạm tính 0 đ>,
         "hint": <CHỈ khi thiếu VÀ là báo giá cũ (is_legacy)>}
        hoặc {"success": False, "message"} khi không có dòng.
    """
    from alumglass.engine.bom_orchestrator import ZERO_PRICE_TRACE_PREFIX

    row_name = (quotation_item_name or "").strip()
    is_existing = bool(row_name) and not row_name.startswith("new-")

    if is_existing:
        # Dòng đã lưu: cổng quyền trên cha THẬT của dòng (tra DB), ⛔ không
        # dùng `parent` client gửi.
        _require_quotation_item_permission(row_name, ptype="read")
        qi = frappe.get_doc("Quotation Item", row_name)
    else:
        # Dòng MỚI: không có dòng trong DB để hỏi quyền ⇒ kiểm `read` trên
        # Quotation cha client khai (cha `new-…` ⇒ cần quyền TẠO báo giá).
        qi = None
        _require_quotation_permission(parent, ptype="read")
        if not result_json:
            # Chưa có kết quả nào trong tay ⇒ nói đúng trạng thái + lối xử lý
            # (⛔ rơi xuống đọc DB rồi trả "không tìm thấy dòng" khó hiểu).
            return {
                "success": False,
                "message": "Dòng này chưa có kết quả tính giá để giải thích. "
                           "Bấm \"Preview tính giá\" rồi thử lại.",
            }

    if result_json:
        # JSON do client gửi lên (đọc từ dòng) → giải thích từ đó. Hỏng thì
        # báo CÂU người-đọc-được (frappe.throw = 417, ⛔ không 500, ⛔ không
        # phơi traceback) thay vì hiện bảng trống khó hiểu.
        data = _parse_result_json_arg(result_json)
    else:
        raw = qi.get("al_bom_result") if qi is not None else None
        data = {}
        if raw:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                data = {}
    if not isinstance(data, dict):
        data = {}

    lines = data.get("lines", []) or []
    line = None
    for candidate in lines:
        if isinstance(candidate, dict) and (candidate.get("slug") or "") == slug:
            line = candidate
            break
    if line is None:
        # Slug chỉ để ghi log kỹ thuật, ⛔ không trả ra người dùng.
        frappe.logger("alumglass").info(
            "explain_bom_line: không tìm thấy slug=%s trong Quotation Item %s",
            slug, quotation_item_name)
        return {
            "success": False,
            "message": "Không tìm thấy dòng vật tư cần giải thích trong kết "
                       "quả tính giá.",
        }

    slug_labels = _get_slug_labels()
    bucket_names = _get_bucket_names()
    lines_by_slug = {
        (ln.get("slug") or ""): ln for ln in lines if isinstance(ln, dict)}

    steps = []
    missing = []

    def add_step(key, title, detail, is_missing=False, severity=None):
        """1 bước giải thích. `key` ổn định để client tô xám đúng bước thiếu
        (`missing` chứa CHÍNH các key này).

        `severity="warning"` = bước có số liệu CHƯA ĐÚNG nhưng KHÔNG phải
        "chưa lưu dữ liệu" (vd đang tạm tính 0 đ) — client tô hổ phách, ⛔
        không đưa vào `missing` (missing nghĩa là dữ liệu cũ chưa có).
        """
        step = {
            "step": len(steps) + 1,
            "key": key,
            "title": title,
            "detail": detail,
        }
        if severity:
            step["severity"] = severity
        steps.append(step)
        if is_missing:
            missing.append(key)

    item_code = line.get("item_code") or ""
    item_name = line.get("item_name") or ""
    rule_trace = line.get("rule_trace") or ""
    price_trace = line.get("price_trace") or ""
    is_rule_row = (line.get("item_selection_mode") or "") == "Rule"
    # §7.6 — HAI trạng thái khác nhau, ⛔ gộp:
    #   `rule_missing`      = quy tắc chưa khai tra theo dữ liệu nào;
    #   `rule_source_missing` = đã khai nhưng lượt tính KHÔNG có nguồn
    #     (chưa chọn dòng / dòng đã mất / dòng không mang dữ liệu / GLOBAL
    #     thiếu thông số) ⇒ câu phải chỉ việc chọn dòng, ⛔ "không mã nào khớp".
    rule_missing = bool(line.get("rule_input_missing"))
    rule_source_missing = bool(line.get("rule_source_missing"))
    rule_trace_blank = (
        "Chưa có dữ liệu để chọn mã — chọn dòng lấy dữ liệu trong bộ BOM.")
    # Báo giá tính trước bản vá: KHÔNG có căn cứ nào (cả chuỗi hiển thị lẫn
    # bản kỹ thuật). Chỉ thiếu `*_raw` mà vẫn có chuỗi hiển thị thì KHÔNG phải
    # dữ liệu cũ — bước 3 vẫn giải thích được.
    is_legacy = (
        not rule_trace and not price_trace
        and "rule_trace_raw" not in line and "price_trace_raw" not in line)

    def phrase_for(code, name):
        if name and code:
            return '"%s" (%s)' % (name, code)
        return '"%s"' % (name or code)

    def item_phrase():
        return phrase_for(item_code, item_name)

    # ── Sự thật tra cứu đã lưu (báo giá mới) ────────────────────────
    # `lookup_facts` = engine ghi lại ĐÚNG nhánh đã chạy cho dòng này
    # (`code_source`, `price_match`, `match_dims`, `glass_used`). Báo giá cũ
    # không có khoá này ⇒ suy từ những gì còn lưu.
    facts = line.get("lookup_facts")
    if not isinstance(facts, dict):
        facts = {}
    code_source = facts.get("code_source") or ""
    if not code_source:
        code_source = "rule" if is_rule_row else "item_code"

    # ── Bước "chọn mã vật tư" — theo ĐÚNG nguồn mã đã dùng ─────────
    if code_source == "manual_price":
        # Dòng nhập giá tay: engine KHÔNG tra mã nào ⇒ ⛔ không có bước này.
        pass
    elif code_source == "rule":
        if rule_missing:
            add_step("item_code", "Chọn mã vật tư",
                     "Quy tắc chọn mã của dòng này chưa khai tra theo dữ "
                     "liệu nào — báo quản trị bổ sung ô \"Tra theo\" trong "
                     "quy tắc.", not item_code)
        elif rule_source_missing:
            # Thiếu NGUỒN (⛔ phải "không khớp"): câu của engine đã đúng
            # trạng thái + chỉ việc phải làm; đánh `warning` vì số tiền
            # chưa đúng, và đưa vào `missing` khi dòng chưa có mã.
            add_step("item_code", "Chọn mã vật tư",
                     rule_trace or rule_trace_blank,
                     not item_code, severity="warning")
        elif rule_trace:
            add_step("item_code", "Chọn mã vật tư", rule_trace)
        elif item_code:
            add_step("item_code", "Chọn mã vật tư",
                     "Dùng mã cố định %s." % item_phrase())
        else:
            add_step("item_code", "Chọn mã vật tư",
                     "Không có dữ liệu lưu cho bước này", True)
    elif (code_source == "price_base_item"
            and facts.get("price_base_item") and not item_code):
        # CHỈ dòng KHÔNG có mã riêng mới cần câu "mã đại diện": bước 1 mang
        # tiêu đề "Chọn mã vật tư" nên phải nói mã CỦA DÒNG, còn câu "giá tra
        # theo mã đại diện …" đã có ở bước giá — in lại ở đây là lặp một vế.
        add_step("item_code", "Chọn mã vật tư",
                 "Giá tra theo mã đại diện %s." % phrase_for(
                     facts.get("price_base_item") or "",
                     facts.get("price_base_item_name") or ""))
    elif item_code:
        add_step("item_code", "Chọn mã vật tư",
                 "Dùng mã cố định %s." % item_phrase())
    else:
        add_step("item_code", "Chọn mã vật tư",
                 "Không có dữ liệu lưu cho bước này", True)

    # ── Dòng này có THẬT SỰ dùng dữ liệu kính hay không ─────────────
    # Câu giải thích phải theo DÒNG: dòng nhôm/phụ kiện ⛔ không có bước
    # "Nguồn giá trị kính" (kể cả câu "không áp dụng" — người đọc chỉ cần
    # thấy bước có thật, ⛔ không cần biết bước không tồn tại).
    own_glass = _glass_detail(line)
    is_glass_row = bool(line.get("is_glass_row"))
    # Dòng khác đọc thông số kính của DÒNG KÍNH mà rule trỏ tới — slug lấy
    # từ `rule_trace_raw` (bản kỹ thuật còn nguyên `items.<slug>.<field>`;
    # chuỗi hiển thị đã thay slug bằng nhãn dòng).
    ref_match = _re.search(
        r'items\.([\w-]+)\.([\w]+)',
        line.get("rule_trace_raw") or rule_trace)
    ref_slug = ref_match.group(1) if ref_match else ""
    ref_field = ref_match.group(2) if ref_match else ""
    ref_line = lines_by_slug.get(ref_slug) if ref_slug else None
    ref_glass = _glass_detail(ref_line)
    ref_is_glass = bool(ref_glass or (ref_line or {}).get("is_glass_row"))
    if "glass_used" in facts:
        # Sự thật engine đã ghi lúc tính: dòng này có đọc dữ liệu kính hay
        # không. ⛔ Không suy lại từ chữ nghĩa của trace.
        uses_glass = bool(facts.get("glass_used"))
    else:
        uses_glass = bool(own_glass or is_glass_row or ref_is_glass)

    # ── Bước "nguồn giá trị kính" — CHỈ khi dòng dùng dữ liệu kính ───
    # Dòng nhôm/phụ kiện ⛔ không có bước này (kể cả câu "không áp dụng"):
    # bước không tồn tại thì ⛔ không in ra lời giải thích cho nó.
    if uses_glass:
        ref_label = (slug_labels.get(ref_slug)
                     or (ref_line or {}).get("line_label")
                     or (ref_line or {}).get("item_name")
                     or "dòng được tham chiếu")
        if own_glass:
            # `own_glass` đã mở đầu bằng chữ "Kính …" — ⛔ không lặp "kính Kính".
            add_step("glass_source", "Nguồn giá trị kính",
                     "Dòng này dùng %s" % own_glass)
        elif is_glass_row:
            # Dòng KÍNH nhưng chưa lưu thông số (chưa chọn kính / chưa cấu
            # hình mã mặc định) — câu phải chỉ ĐÚNG chỗ sửa: người dùng đọc
            # xong biết bấm ở đâu, không phải ngõ cụt ("chưa chọn kính" mà
            # không nói chọn ở đâu).
            add_step(
                "glass_source", "Nguồn giá trị kính",
                'Dòng kính chưa chọn kính nên chưa tính được khối lượng — mở '
                '"Tham số BOM" → mục "Kính theo vị trí" để chọn kính, rồi bấm '
                '"Tính giá".', True)
        elif ref_glass:
            # Dòng nẹp/keo KHÔNG tự có thông số kính — rule_input_expr trỏ
            # sang dòng kính. Đọc dòng đó từ CÙNG JSON kết quả (không tính
            # lại engine).
            detail = 'Giá trị lấy từ dòng "%s" — %s' % (ref_label, ref_glass)
            if ref_field:
                ref_value = (ref_line or {}).get(ref_field)
                # Alias: dữ liệu cũ chỉ có 1 trong 2 tên (total_thick_mm /
                # glass_thick) — đọc tên còn lại thay vì bỏ trống.
                if ref_value is None:
                    if ref_field == "glass_thick":
                        ref_value = (ref_line or {}).get("total_thick_mm")
                    elif ref_field == "total_thick_mm":
                        ref_value = (ref_line or {}).get("glass_thick")
                if ref_value is not None:
                    if ref_field == "glass_type":
                        shown = (ref_line or {}).get("glass_type_name") or ""
                    else:
                        shown = _fmt_with_unit(
                            ref_value, display_unit(ref_field))
                    if shown:
                        detail += " Giá trị dùng để chọn mã: %s = %s." % (
                            display_label(ref_field), shown)
            add_step("glass_source", "Nguồn giá trị kính", detail)
        else:
            # `uses_glass` đúng nhờ cờ `is_glass_row` của DÒNG ĐƯỢC THAM
            # CHIẾU, nhưng dòng đó chưa lưu thông số kính ⇒ thiếu dữ liệu.
            add_step(
                "glass_source", "Nguồn giá trị kính",
                'Không có dữ liệu lưu cho bước này — dòng "%s" không lưu '
                "thông số kính." % ref_label, True)

    # ── Bước "quy tắc khớp → mã" — CHỈ khi mã đi ra từ Rule ─────────
    # Dòng dùng mã cố định / mã đại diện / giá nhập tay ⛔ không có bước này:
    # câu "không dùng quy tắc…" không thêm thông tin nào.
    rule_name = line.get("rule_name") or ""
    rule_match = line.get("rule_match") or ""
    rule_description = (line.get("rule_description") or "").strip()
    base = ('Quy tắc "%s"' % rule_name) if rule_name else "Quy tắc chọn mã"

    def with_rule_description(detail):
        """Nối MÔ TẢ NGHIỆP VỤ của quy tắc vào câu giải thích (nếu có).

        Chỉ nối thêm — câu hiện tại giữ nguyên. Rule cũ chưa khai mô tả ⇒
        trả đúng câu cũ. ⛔ đưa `rule_code`/biểu thức vào đây.
        """
        if not rule_description:
            return detail
        if detail and not detail.endswith((".", "!", "?")):
            detail += "."
        tail = rule_description
        if not tail.endswith((".", "!", "?")):
            tail += "."
        return "%s %s" % (detail, tail)

    if code_source == "rule":
        if is_legacy:
            add_step("rule", "Quy tắc khớp → mã vật tư",
                     "Chưa lưu căn cứ chọn mã của dòng này.", True)
        elif rule_missing:
            add_step("rule", "Quy tắc khớp → mã vật tư",
                     "Dòng này chưa khai báo quy tắc chọn mã.", True)
        elif rule_source_missing:
            # ⛔ in "không có mã nào khớp": bảng quy tắc CHƯA HỀ được hỏi vì
            # lượt tính chưa có giá trị đem tra. Bước "Chọn mã vật tư" ngay
            # trên đã nêu đúng trạng thái + việc phải làm — in lại là lặp.
            pass
        elif item_code:
            if rule_match:
                detail = "%s khớp %s → chọn mã %s." % (
                    base, rule_match, item_phrase())
            else:
                detail = "%s đã khớp → chọn mã %s." % (base, item_phrase())
            add_step("rule", "Quy tắc khớp → mã vật tư",
                     with_rule_description(detail))
        else:
            add_step("rule", "Quy tắc khớp → mã vật tư",
                     with_rule_description(
                         "%s: không có mã nào khớp." % base))

    # ── Bước tra giá ────────────────────────────────────────────────
    if price_trace:
        # Engine không tra được dòng giá ⇒ câu đã là CẢNH BÁO "tạm tính 0 đ".
        # Đánh dấu riêng bằng `severity`, ⛔ KHÔNG đưa key vào `missing`
        # (missing mang nghĩa "chưa lưu dữ liệu" — ở đây dữ liệu có, chỉ là
        # số tiền chưa đúng).
        zero_price = bool(
            ZERO_PRICE_TRACE_PREFIX
            and ZERO_PRICE_TRACE_PREFIX in price_trace)
        add_step("price", "Tra giá", price_trace,
                 severity="warning" if zero_price else None)
    else:
        add_step("price", "Tra giá",
                 "Không có dữ liệu lưu cho bước này", True)

    # ── Bước tính số lượng ──────────────────────────────────────────
    pattern_name = line.get("calc_pattern_name") or ""
    quantity_keys = ("width", "height", "qty", "unit_qty", "total_qty")
    has_quantity = any(line.get(k) is not None for k in quantity_keys)
    if pattern_name or has_quantity:
        head = ('Cách tính "%s"' % pattern_name) if pattern_name             else "Cách tính"
        detail = "%s: rộng %s × cao %s, SL %s" % (
            head,
            _fmt_number(line.get("width")),
            _fmt_number(line.get("height")),
            _fmt_number(line.get("qty")))
        scrap_pct = line.get("scrap_pct", 0) or 0
        if scrap_pct:
            detail += ", hao hụt %s%%" % _fmt_number(scrap_pct)
        detail += " → SL đơn vị %s; tổng SL %s%s" % (
            _fmt_number(line.get("unit_qty")),
            _fmt_number(line.get("total_qty")),
            (" %s" % line.get("unit")) if line.get("unit") else "")
        add_step("quantity", "Tính số lượng", detail)
    else:
        add_step("quantity", "Tính số lượng",
                 "Không có dữ liệu lưu cho bước này", True)

    # ── Bước "quy tắc tính số lượng" — CHỈ khi công thức số lượng dùng
    #    `lookup_rule(...)` dạng đơn giản. Dòng không dùng quy tắc ⇒ ⛔ thêm
    #    bước (không hiện "chưa lưu" cho thứ dòng đó không hề dùng).
    qty_rule_trace = line.get("qty_rule_trace") or ""
    if qty_rule_trace:
        add_step("qty_rule", "Quy tắc tính số lượng", qty_rule_trace)

    # ── Bước thành tiền + Nhóm chi phí ────────────────────────────────
    if "line_total" in line:
        bucket = line.get("cost_bucket") or ""
        detail = "%s × %s = %s" % (
            _fmt_money(line.get("unit_price")),
            _fmt_number(line.get("total_qty")),
            _fmt_money(line.get("line_total")))
        if bucket:
            detail += " → Nhóm chi phí %s" % (
                bucket_names.get(bucket) or "nhóm chưa đặt tên")
        else:
            detail += " → chưa gán Nhóm chi phí"
        add_step("line_total", "Thành tiền và Nhóm chi phí", detail)
    else:
        add_step("line_total", "Thành tiền và Nhóm chi phí",
                 "Không có dữ liệu lưu cho bước này", True)

    result = {
        "success": True,
        "slug": slug,
        # Không trả slug trần ra nhãn hiển thị.
        "label": (slug_labels.get(slug) or line.get("line_label")
                  or item_name or "Dòng vật tư"),
        "item_code": item_code,
        "line_total": line.get("line_total", 0),
        "steps": steps,
        "missing": missing,
    }
    # Cờ tổng cho client: thành tiền = 0 MÀ có cảnh báo ⇒ "số 0 này không
    # đáng tin". Client đọc CỜ NÀY, ⛔ không tự dò chuỗi tiếng Việt.
    line_total = line.get("line_total", 0) or 0
    has_warning = any(s.get("severity") == "warning" for s in steps)
    if line_total == 0 and has_warning:
        result["warn_zero_price"] = True
    # `hint` chỉ đúng khi thiếu là do DỮ LIỆU CŨ: báo giá mới cũng có thể thiếu
    # (vd dòng kính chưa chọn kính) — lúc đó bấm "Tính giá" không đổi gì, câu
    # "tính trước khi có phần giải thích" là sai nguyên nhân.
    if missing and is_legacy:
        result["hint"] = (
            "Báo giá này được tính trước khi có phần giải thích. Bấm nút "
            '"Tính giá" để cập nhật căn cứ.')
    return result


# ══════════════════════════════════════════════════════════════════════
# F3 — doc_events cho "AL Quantity Calc Method" (khai trong hooks.py)
# ══════════════════════════════════════════════════════════════════════
# `formula_handlers.clear_calc_fn_cache()` xoá cache calc_fn (cả cache dương +
# cache âm) nhưng TRƯỚC ĐÂY không nơi nào gọi ⇒ sửa calc_fn xong hệ thống vẫn
# dùng bản cũ tới khi cache hết hạn. Controller của doctype này do DEV khác sở
# hữu nên 2 hàm nối cache nằm ở đây, chỉ gọi đúng 1 việc — ⛔ KHÔNG đụng cổng
# vai trò chặn đổi calc_fn ở controller.
# Import trong hàm để tránh vòng import lúc nạp app.
# ──────────────────────────────────────────────────────────────────────

def on_calc_method_change(doc, method=None):
    """Hook doc_events `on_update`: AL Quantity Calc Method vừa đổi → xoá cache calc_fn."""
    from alumglass.formula_handlers import clear_calc_fn_cache
    clear_calc_fn_cache()


def on_calc_method_trash(doc, method=None):
    """Hook doc_events `on_trash`: AL Quantity Calc Method bị xoá → xoá cache calc_fn."""
    from alumglass.formula_handlers import clear_calc_fn_cache
    clear_calc_fn_cache()