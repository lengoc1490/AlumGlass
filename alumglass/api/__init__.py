import json
import frappe
from frappe import _


@frappe.whitelist()
def calculate_bom(quotation_item_name):
    """Tính BOM cho 1 dòng báo giá - trả về GIA_VAT + chi tiết.

    Đây là API chính được gọi từ nút "Tính giá" trên Quotation Item.

    P2 (async): đếm số dòng BOM từ bom_set_snapshot của version pin:
      - ≤ ASYNC_BOM_THRESHOLD → chạy ĐỒNG BỘ (giữ nguyên hành vi cũ 100%),
        trả về response chuẩn hoá {buckets, cost_template, lines}.
      - > ngưỡng → `frappe.enqueue(queue="long", timeout=600)` + trả về
        {async: True, job_id, status: "Queued", message}. Client nhận kết quả
        qua realtime event "alumglass_bom_calc_done".
    """
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


def _normalize_bom_response(result):
    """C4 — Chuẩn hoá response sync: luôn đủ 3 key dialog cần.

    Client tự chọn key động (buckets / cost_template / lines) — chỉ đảm bảo
    key luôn tồn tại để UI không gãy khi engine trả thiếu field.
    """
    result = dict(result or {})
    result.setdefault("buckets", {})
    result.setdefault("cost_template", {})
    result.setdefault("lines", [])
    return result


def _estimate_bom_line_count(qi):
    """P2 — Đếm nhanh số dòng BOM từ bom_set_snapshot của version pin.

    KHÔNG load BomOrchestrator chỉ để đếm (tránh lãng phí). Version chưa pin
    → đếm 0 → chạy sync. Không parse được → đếm 0 (an toàn, sync).
    """
    bom_version = qi.get("al_bom_version")
    if not bom_version and qi.get("al_bom"):
        bom_version = frappe.db.get_value("AL BOM", qi.al_bom, "current_version")
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

    frappe.enqueue(
        method="alumglass.api._run_bom_calculation_job",
        queue="long",
        timeout=600,  # 10 phút — đủ cho BOM rất lớn
        job_name=job_id,
        qi_name=qi.name,
        job_id=job_id,
        user=frappe.session.user,
    )

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
    except Exception:
        error_trace = frappe.get_traceback()
        frappe.db.set_value(
            "Quotation Item", qi_name,
            {"al_calc_status": "Failed", "al_calc_error": error_trace[:1000]},
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
                "error": str(error_trace)[-500:],
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
    from alumglass.al_bom_engine.doctype.al_cost_template.al_cost_template import preview_cost_template as _preview
    return _preview(template_code, inputs_json)


@frappe.whitelist()
def get_slug_info(slug):
    """Lấy thông tin Slug Library."""
    from alumglass.al_bom_engine.doctype.al_bom_item.al_bom_item import get_slug_info as _get
    return _get(slug)


@frappe.whitelist()
def resolve_item_rule(rule_code, input_value):
    """Tra cứu Item từ Dynamic Item Rule."""
    from alumglass.al_formula_rules.doctype.al_dynamic_item_rule.al_dynamic_item_rule import resolve_item
    return resolve_item(rule_code, input_value)


@frappe.whitelist()
def get_bom_structure(bom_code):
    """Lấy toàn bộ cấu trúc BOM."""
    from alumglass.al_bom_engine.doctype.al_bom.al_bom import get_bom_structure as _get
    return _get(bom_code)


@frappe.whitelist()
def get_cost_template_context(template_code=None):
    """[DEPRECATED] Dùng get_formula_context thay thế."""
    return get_formula_context("AL Cost Template", None)


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


def _get_live_context_vars(doctype, docname=None):
    """B6 FB-max: lấy context autocomplete từ get_live_context (nguồn chính FB).

    Trả về dict response của formula_builder.api.formula_builder.get_live_context,
    hoặc {} nếu FB không dùng được (lỗi/thiếu permission) — caller fallback cũ.
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
        })
        return get_live_context(scope) or {}
    except Exception:
        return {}


@frappe.whitelist()
def get_formula_context(doctype, docname=None):
    """★ DATA-DRIVEN: Lấy context variables cho autocomplete formula fields.

    B6 FB-max: autocomplete lấy từ 1 nguồn chính là get_live_context (FVB + doc
    fields + global vars) — thay vì chỉ liệt kê tay. Các nguồn AL-specific
    (Cost Bucket, Row Literals, Common Vars, Slug Library, Variable Set) giữ làm
    fallback backward-compat cho tới khi FVB seed (D3) — không làm mất biến UI.

    Không hardcode biến nào — mọi biến được khám phá động từ DB.
    Người dùng thêm biến mới = thêm record vào bảng tương ứng, không cần sửa code.

    Nguồn biến (theo thứ tự ưu tiên):
    0. ★ get_live_context (FB-max B6) — Formula Variable Binding resolve thật
    1. Cost Bucket codes — từ AL Cost Bucket (động, user thêm được)
    2. System Variables — từ AL Variable Library (is_system=1)
    3. User Variables — từ AL Variable Library (is_system=0), lọc theo Variable Set của doctype
    4. Formula Global Variables — từ Formula Builder
    5. Row Literals — các biến engine inject per-row (weight_per_unit, unit_price...)
    6. Common Vars — W_mm, H_mm, n_panel, TONG_M2
    7. Formula Variable Bindings — per-doctype bindings từ Formula Builder
    8. Slug Library — cho cross-row reference

    Args:
        doctype: Tên doctype đang mở (vd: "AL Cost Template", "AL Bom Set")
        docname: Tên record (để resolve giá trị thực tế nếu có)
    """
    variables = []
    references = []

    # Resolve giá trị thực tế từ document (khi có docname)
    resolved = _resolve_doc_values(doctype, docname) if docname else {}

    # ── 0. ★ FB-max (B6): nguồn chính từ get_live_context ────────────
    fb_ctx = _get_live_context_vars(doctype, docname)
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
    for uv in frappe.get_all("AL Variable Library",
                             filters={"is_system": 0},
                             fields=["var_name", "var_label", "var_type",
                                     "default_value", "description"],
                             order_by="var_name"):
        variables.append({"name": uv["var_name"],
            "label": f"{uv['var_name']} — {uv.get('var_label') or ''}",
            "value": "—", "type": uv.get("var_type") or "Float",
            "source": "local", "source_type": "variable_library",
            "group": "User Variables",
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

    # ── 5. Row Literals ─────────────────────────────────────────────
    for name, label, vtype in [
        ("weight_per_unit", "TL riêng (kg/m)", "Float"),
        ("unit_price", "Đơn giá", "Float"), ("unit_qty", "SL đơn vị", "Float"),
        ("total_qty", "Tổng SL", "Float"), ("line_total", "Thành tiền", "Float"),
        ("scrap_pct", "% Hao hụt", "Float"), ("glass_thick", "Độ dày kính", "Float"),
        ("glass_type", "Loại kính", "Data"), ("calc_pattern", "Pattern", "Data"),
    ]:
        variables.append({"name": name, "label": f"{name} — {label}",
            "value": "—", "type": vtype, "source": "local",
            "source_type": "row_literal", "group": "Row Literals",
            "value_source": "Engine inject per-row khi chạy BomOrchestrator B2",
            "description": "Tự động inject — mỗi dòng BOM có giá trị riêng",})

    # ── 6. Common BOM Variables ─────────────────────────────────────
    for name, label, vtype in [
        ("W_mm", "Chiều rộng (mm)", "Float"), ("H_mm", "Chiều cao (mm)", "Float"),
        ("n_panel", "Số cánh", "Int"), ("TransomHeight_mm", "Cao ô kính", "Float"),
        ("SideLiteWidth", "Rộng vách kính", "Float"),
        ("SideLiteHeight", "Cao vách kính", "Float"),
        ("installation_height_m", "Cao lắp đặt (m)", "Float"),
        ("TONG_M2", "Tổng diện tích (m²)", "Float"),
    ]:
        variables.append({"name": name, "label": f"{name} — {label}",
            "value": "—", "type": vtype, "source": "local",
            "source_type": "common_var", "group": "BOM Input Variables",
            "value_source": "Người dùng nhập khi mở dialog Tham số BOM",
            "description": "BOM input variable — giá trị đến từ user",})

    # ── 7. Formula Variable Bindings ────────────────────────────────
    for b in frappe.get_all("Formula Variable Binding",
                            filters=[["is_active", "=", 1],
                                     ["applies_to_doctype", "in", ["", doctype]]],
                            fields=["variable_name", "variable_label", "data_type",
                                    "default_value", "source_type", "applies_to_doctype"],
                            order_by="resolve_priority"):
        variables.append({"name": b["variable_name"],
            "label": b.get("variable_label") or b["variable_name"],
            "value": b.get("default_value"), "type": b.get("data_type") or "Float",
            "source": "local", "source_type": b.get("source_type") or "binding",
            "group": "Formula Bindings" if not b.get("applies_to_doctype") else f"Bindings · {doctype}",
            "value_source": "Default từ Formula Variable Binding" if not b.get("applies_to_doctype")
                else f"Binding cho {doctype}",
            "description": f"Formula Variable Binding · {b.get('source_type', '')}",})

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
        frappe.get_all("AL Variable Dimension Mapping", pluck="variable_name")
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

    # ── Dedup (B6 FB-max): entry FB (đầu) giữ — các nguồn cũ trùng tên bỏ qua ──
    seen_names = set()
    deduped = []
    for v in variables:
        n = v.get("name", "")
        if not n or n in seen_names:
            continue
        seen_names.add(n)
        deduped.append(v)
    variables = deduped

    return {
        "doctype": doctype,
        "docname": docname,
        "variables": variables,
        "references": references,
        "total_sources": len({v["source_type"] for v in variables}),
        "total_variables": len(variables),
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


@frappe.whitelist()
def get_variable_set_for_bom(bom_code):
    """Lấy danh sách biến từ Variable Set của BOM.

    Flow: BOM → Bom Set → Variable Set → Variable Set Items + System vars từ Library.
    Mỗi variable được resolve từ AL Variable Library (source of truth — label, type,
    link_doctype, select_options, default_value), fallback về field denormalize của
    AL Variable Set Item nếu item không link tới Library record.
    Trả về list biến để JS dialog tự sinh form fields + thông tin BOM/Bom Set/Variable Set
    + thông tin mở rộng (Hệ profile, Hãng nhôm, Phụ kiện) cho phần read-only của dialog.
    """
    if not bom_code:
        return {"variables": []}

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
    #     Child table `system_variables` ưu tiên, fallback offset_* cứng.
    if profile_system_code:
        try:
            ps_doc = frappe.get_cached_doc("AL Profile System", bom_set.profile_system)
            profile_vals = {}
            for row in ps_doc.get("system_variables") or []:
                if row.get("is_active") and row.get("value") not in (None, ""):
                    profile_vals[row.get("variable")] = row.get("value")
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
        frappe.get_all("AL Variable Dimension Mapping", pluck="variable_name")
    )
    for v in variables:
        v["is_pricing_dimension"] = v.get("var_name") in _pricing_dim_vars

    # ── 3. V6 P11 — glass_groups: MỖI dòng KINH luôn có đúng 1 selector độc
    # lập trong "Kính theo vị trí", KHÔNG bắt buộc phải cấu hình sẵn
    # `default_glass_master` trên AL Bom Set (xem glass_group_resolver.py để
    # hiểu công thức rep — PHẢI khớp 100% với bom_orchestrator.py).
    from alumglass.al_bom_engine.glass_group_resolver import glass_group_rep

    glass_groups = []
    _seen_rep = set()
    slug_labels_kinh = _get_slug_labels()
    for item in bom_set.get("items", []) or []:
        if (item.get("category") or "").upper() != "KINH":
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
            label = slug_labels_kinh.get(slug) or slug
            default_val = ""  # không có mã mặc định — bắt buộc user tự chọn

        glass_groups.append({
            "rep": rep,
            "label": label,
            "default": default_val,
            "slug": item.get("slug") or "",
            "is_real_master": is_real_master,
        })

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


@frappe.whitelist()
def get_result_display(quotation_item_name):
    """Display model cho renderer dùng chung (Phase 2 — A4 + B).

    Args:
        quotation_item_name: tên Quotation Item đã có al_bom_result.

    Returns:
        {
          "summary": {gia_vat, gia_ban, line_count, calculated},
          "lines": [{slug, label, item_code, width, height, qty, unit_qty,
                     total_qty, unit_price, line_total, cost_bucket, bucket_name}],
          "buckets": [{bucket_code, bucket_name, value}],
          "cost_template": [{line_code, line_label, calc_formula, value,
                             is_subtotal, bucket_code, bucket_name, trace}],
          "errors": {bom_items, cost_template}
        }
    """
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
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
            "label": slug_labels.get(slug, slug),
            "item_code": ln.get("item_code", "") or "",
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
        if _k.startswith("_") or _k in ("extra_vars", "accessory_set", "glass_master"):
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
        "errors": data.get("errors", {}) or {},
    }
