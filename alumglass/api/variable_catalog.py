# -*- coding: utf-8 -*-
"""Variable Catalog API — điểm vào DUY NHẤT cho danh mục biến công thức.

Luồng: resolve profile → chạy adapter của các nguồn được phép → áp rule →
dedupe → gom nhóm + references.

⚠️ Đây là lớp GỢI Ý / LỌC, KHÔNG phải nguồn giá trị lúc tính giá. Sửa hay
xoá profile chỉ đổi danh sách người dùng thấy, không đổi số tiền của BOM
(xem `nguon_bien_tham_chieu.md` §8.8).
"""
import frappe
from frappe import _

# Import để CHẠY decorator đăng ký adapter (không dùng trực tiếp tên khác).
from alumglass.variable_sources import adapters as _adapters  # noqa: F401
from alumglass.variable_sources.context import CatalogContext
from alumglass.variable_sources.registry import get_adapters
from alumglass.variable_sources.rules import (
    INCLUDE_ALL,
    active_source_kinds,
    build_groups,
    dedupe_candidates,
    select_candidates,
    to_int,
)

PROFILE_DOCTYPE = "AL Variable Profile"
SETTINGS_DOCTYPE = "AL Variable Settings"
PRICING_MAPPING_DOCTYPE = "AL Variable Dimension Mapping"

_RULE_FIELDS = (
    "action", "source_kind", "source_ref", "name_prefix", "name_regex",
    "category_tag", "var_type", "source_type", "group_label", "sort_order",
    "only_fields", "require_value", "is_active",
)

_CROSS_ROW_FIELDS = (
    "table_field", "id_field", "label_field", "fields",
    "include_index_form", "enabled",
)


# ══════════════════════════════════════════════════════════════════════
# Guard + resolve profile
# ══════════════════════════════════════════════════════════════════════
def _assert_doctype_allowed(doctype):
    """Dùng CHUNG guard với `get_formula_context` (allowlist module + quyền đọc).

    Không tự viết lại: mọi thay đổi chính sách bảo mật phải áp cho cả 2 API.
    """
    from alumglass.api import _assert_formula_context_doctype
    _assert_formula_context_doctype(doctype)


def _find_profile_field(doctype):
    """Field Link đầu tiên trên doctype trỏ tới AL Variable Profile."""
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return None
    for field in meta.get("fields") or []:
        if field.fieldtype == "Link" and field.options == PROFILE_DOCTYPE:
            return field.fieldname
    return None


def _load_profile(profile_code):
    """Document profile đang dùng; None nếu không có / đã tắt."""
    code = (profile_code or "").strip() if isinstance(profile_code, str) else profile_code
    if not code:
        return None
    try:
        if not frappe.db.exists(PROFILE_DOCTYPE, code):
            return None
        doc = frappe.get_cached_doc(PROFILE_DOCTYPE, code)
    except Exception:
        return None
    if not doc.get("is_active"):
        return None
    return doc


def _resolve_profile_doc(doctype, docname=None, profile=None):
    """Thứ tự resolve: explicit → Link trên doc → `AL Variable Settings.default_profile`.

    ⛔ `default_profile` CHỈ áp cho doctype đã khai field Link tới
    `AL Variable Profile`. Doctype không có field đó ⇒ trả `None` ngay: nếu
    không, một default profile toàn cục sẽ tự bật cho MỌI doctype (kể cả
    doctype không liên quan) và làm autocomplete đổi hành vi ngoài ý muốn.

    `docname` chỉ cần khi đọc giá trị Link; khi chưa có docname (vd validate
    lúc chưa lưu) vẫn dùng default nếu doctype đã khai field.
    """
    doc = _load_profile(profile)
    if doc is not None:
        return doc

    fieldname = _find_profile_field(doctype)
    if not fieldname:
        return None

    if docname:
        try:
            value = frappe.db.get_value(doctype, docname, fieldname)
        except Exception:
            value = None
        doc = _load_profile(value)
        if doc is not None:
            return doc

    # R3/B2: hồ sơ mặc định nay là `AL Variable Profile.is_default` (trước đây
    # là Single `AL Variable Settings.default_profile`). Đọc is_default TRƯỚC,
    # chỉ rơi về Single khi site chưa migrate hoặc chưa bật hồ sơ nào — giữ
    # nguyên hành vi cũ trong một chu kỳ.
    default_profile = None
    try:
        rows = frappe.get_all(
            "AL Variable Profile",
            filters={"is_default": 1, "is_active": 1},
            pluck="name",
            order_by="modified desc",
            limit=1,
        ) or []
        default_profile = rows[0] if rows else None
    except Exception:
        # Cột `is_default` chưa có (site chưa migrate B2) — rơi về Single.
        default_profile = None

    if not default_profile:
        try:
            default_profile = frappe.db.get_single_value(
                SETTINGS_DOCTYPE, "default_profile")
        except Exception:
            default_profile = None
    return _load_profile(default_profile)


def _row_payload(row, fields):
    return {field: row.get(field) for field in fields}


def _profile_payload(profile_doc):
    """Profile → dict thuần (rules/cross_row là list dict) cho rule + adapter."""
    if profile_doc is None:
        return None
    return {
        "code": profile_doc.name,
        "name": profile_doc.get("profile_name") or profile_doc.name,
        "default_action": profile_doc.get("default_action") or INCLUDE_ALL,
        "rules": [_row_payload(row, _RULE_FIELDS)
                  for row in profile_doc.get("rules") or []],
        "cross_row": [_row_payload(row, _CROSS_ROW_FIELDS)
                      for row in profile_doc.get("cross_row") or []],
    }


def _public_profile(payload):
    """Shape profile trả về client (spec §4)."""
    if not payload:
        return None
    return {
        "code": payload.get("code"),
        "name": payload.get("name"),
        "default_action": payload.get("default_action"),
    }


def _as_flag(value, default=True):
    """Tham số từ HTTP có thể là chuỗi "false"/"0"."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no")
    return bool(value)


# ══════════════════════════════════════════════════════════════════════
# Nhân chung: chạy adapter + lọc + dedupe
# ══════════════════════════════════════════════════════════════════════
def _run_adapters(ctx, kinds):
    """Chạy các adapter thuộc `kinds`; lỗi 1 nguồn không làm mất nguồn khác."""
    raw = []
    for adapter in get_adapters():
        if adapter.source_kind not in kinds:
            continue
        try:
            produced = adapter.fn(ctx) or []
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                title="Variable catalog adapter lỗi: %s" % adapter.source_kind)
            continue
        for candidate in produced:
            candidate.setdefault("adapter_order", adapter.order)
            raw.append(candidate)
    return raw


def _enrich_pricing_dimension(variables):
    """Gắn cờ `is_pricing_dimension` từ AL Variable Dimension Mapping (nguồn duy nhất)."""
    try:
        names = set(frappe.get_all(
            PRICING_MAPPING_DOCTYPE,
            filters={"is_active": 1},
            pluck="variable_name",
        ) or [])
    except Exception:
        names = set()
    for variable in variables:
        variable["is_pricing_dimension"] = variable.get("name") in names


def _build_catalog(doctype, docname=None, child_table=None, row_index=None,
                   fieldname=None, include_values=True, profile=None,
                   all_sources=False):
    """Dựng danh mục biến cho 1 ngữ cảnh.

    `all_sources=True` (B4): ⛔ không lọc theo hồ sơ — chạy MỌI adapter và giữ
    mọi biến. Dùng cho (a) record chưa gán hồ sơ và (b) validate — vũ trụ biến
    hợp lệ ⛔ được thu hẹp bởi hồ sơ (hồ sơ chỉ để GIẤU bớt gợi ý).

    `profile` = None + `all_sources=False` ⇒ vẫn dựng đủ như `all_sources=True`
    (xem B4: một đường đọc duy nhất, hồ sơ chỉ là bộ lọc thu hẹp).
    """
    profile_doc = None if all_sources else _resolve_profile_doc(
        doctype, docname, profile)
    profile_payload = None if all_sources else _profile_payload(profile_doc)

    ctx = CatalogContext(
        doctype, docname=docname, child_table=child_table,
        row_index=row_index, fieldname=fieldname, profile=profile_payload)

    rules = (profile_payload or {}).get("rules") or []
    default_action = (profile_payload or {}).get("default_action") or INCLUDE_ALL

    all_kinds = [adapter.source_kind for adapter in get_adapters()]
    if profile_payload is None:
        # Không có hồ sơ ⇒ KHÔNG lọc: mọi nguồn, giữ tất cả.
        kinds = all_kinds
        rules = []
        default_action = INCLUDE_ALL
    else:
        kinds = active_source_kinds(rules, default_action, all_kinds)

    raw = _run_adapters(ctx, kinds)
    selected, stats = select_candidates(
        raw, rules, fieldname=fieldname, default_action=default_action)
    variables, duplicates = dedupe_candidates(selected)
    _enrich_pricing_dimension(variables)

    # Thứ tự phẳng = thứ tự nhóm (sort_order) → group → name; nhóm do rule quyết.
    variables.sort(key=lambda v: (
        to_int(v.get("sort_order"), 100),
        v.get("group") or "",
        v.get("name") or "",
    ))

    references = _adapters.build_references(ctx, profile_payload)

    if not _as_flag(include_values, True):
        # Ẩn giá trị nhưng GIỮ has_value để client vẫn biết biến nào có dữ liệu.
        for variable in variables:
            variable["value"] = "—"

    return {
        "success": True,
        "profile": _public_profile(profile_payload),
        "variables": variables,
        "groups": build_groups(variables),
        "references": references,
        "meta": {
            "total": len(variables),
            "excluded_by_rules": stats.get("excluded_by_rules", 0),
            "duplicates": duplicates,
            "profile_code": profile_payload.get("code") if profile_payload else None,
            "fieldname": fieldname or "",
            "child_table": child_table or "",
            "row_index": row_index,
            "source_kinds": sorted(kinds),
            # B4: True ⇒ danh sách KHÔNG bị hồ sơ thu hẹp (chưa gán hồ sơ hoặc
            # đang validate). Client dùng cờ này để nói đúng vì sao thấy nhiều.
            "all_sources": profile_payload is None or all_sources,
        },
    }


# ══════════════════════════════════════════════════════════════════════
# API công khai
# ══════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_variable_catalog(doctype, docname=None, child_table=None,
                         row_index=None, fieldname=None,
                         include_values=True, profile=None,
                         all_sources=0):
    """Danh mục biến cho autocomplete/validate của 1 field công thức.

    Trả `variables` (phẳng, tương thích đường cũ), `groups` (đã gom theo
    `group_label`), `references` (biến chéo dòng) và `meta` (thống kê lọc +
    danh sách trùng tên đã bị loại — không bao giờ bỏ im lặng).

    Chưa gán hồ sơ ⇒ danh sách ĐẦY ĐỦ (B4: một đường đọc duy nhất).
    `all_sources=1` ⇒ bỏ qua hồ sơ, dùng cho VALIDATE (hồ sơ chỉ thu hẹp gợi ý,
    ⛔ được thu hẹp vũ trụ biến hợp lệ).
    """
    _assert_doctype_allowed(doctype)
    return _build_catalog(
        doctype, docname=docname, child_table=child_table,
        row_index=row_index, fieldname=fieldname,
        include_values=include_values, profile=profile,
        all_sources=bool(int(all_sources or 0)))


@frappe.whitelist()
def sync_fb_bindings(dry_run=1):
    """B4 — đồng bộ `Formula Variable Binding` từ master data (idempotent).

    Gọi sau khi thêm **hằng số** (`Formula Global Variable`) hoặc **biến hệ có
    nguồn** (`AL Variable Library`) để Formula Builder resolve được ngay —
    ⛔ phải đợi kỳ `bench migrate` sau.

    `dry_run=1` (mặc định) ⇒ chỉ trả kế hoạch, ⛔ ghi gì.
    """
    if ("System Manager" not in (frappe.get_roles() or [])
            and "AL Technical Admin" not in (frappe.get_roles() or [])):
        frappe.throw(
            "Chỉ quản trị hệ thống được đồng bộ Formula Variable Binding."
        )
    from alumglass.fb_binding_sync import sync

    return sync(dry_run=bool(int(dry_run or 0)))


@frappe.whitelist()
def get_row_literal_names():
    """Tên các row literal đang bật.

    Nguồn: `AL Variable Library` (category "Row Literals") sau B2;
    `variable_sources/catalog_rows.py` tự đọc `AL Variable Settings` khi site
    chưa migrate. DEV2 dùng cho cảnh báo `rule_input_expr` — biết biến nào
    engine THẬT SỰ inject theo dòng, thay vì hardcode danh sách trong code.
    Thêm literal mới = thêm 1 dòng Library, không sửa Python.

    Fallback `[]` khi chưa đọc được (site chưa migrate, lỗi DB).
    """
    from alumglass.variable_sources import catalog_rows

    try:
        return catalog_rows.active_names(catalog_rows.KIND_ROW)
    except Exception:
        return []


@frappe.whitelist()
def get_variable_profile(doctype, docname=None):
    """Profile đang áp cho (doctype, docname) — None nếu chưa gán."""
    _assert_doctype_allowed(doctype)
    profile_doc = _resolve_profile_doc(doctype, docname)
    return _public_profile(_profile_payload(profile_doc))


@frappe.whitelist()
def preview_variable_catalog(profile, doctype, docname=None, child_table=None,
                             row_index=None, fieldname=None):
    """Admin xem trước danh mục của 1 profile — cùng shape với API chính."""
    if not frappe.has_permission(PROFILE_DOCTYPE, "read"):
        frappe.throw(_("Bạn không có quyền xem trước danh mục biến."),
                     frappe.PermissionError)
    _assert_doctype_allowed(doctype)
    return _build_catalog(
        doctype, docname=docname, child_table=child_table,
        row_index=row_index, fieldname=fieldname,
        include_values=True, profile=profile)


@frappe.whitelist()
def explain_variable(variable_name, doctype, docname=None, child_table=None,
                     row_index=None, fieldname=None):
    """Giải thích "vì sao tôi thấy / không thấy biến này".

    Trả MỌI nguồn có cùng tên biến (kể cả nguồn bị rule loại) + nguồn đang
    thắng sau dedupe. Chỉ đọc — không thay đổi gì.
    """
    _assert_doctype_allowed(doctype)
    name = (variable_name or "").strip()
    if not name:
        frappe.throw(_("Thiếu tên biến cần giải thích."))

    profile_payload = _profile_payload(
        _resolve_profile_doc(doctype, docname))
    ctx = CatalogContext(
        doctype, docname=docname, child_table=child_table,
        row_index=row_index, fieldname=fieldname, profile=profile_payload)

    # explain chạy TẤT CẢ adapter: người dùng cần thấy cả nguồn bị loại.
    all_kinds = [adapter.source_kind for adapter in get_adapters()]
    raw = _run_adapters(ctx, set(all_kinds))
    mine = [candidate for candidate in raw
            if candidate.get("name") == name]

    if profile_payload is None:
        selected = list(raw)
        stats = {"excluded_by_rules": 0}
    else:
        selected, stats = select_candidates(
            raw, profile_payload.get("rules") or [],
            fieldname=fieldname,
            default_action=profile_payload.get("default_action") or INCLUDE_ALL)

    selected_keys = {
        (c.get("name"), c.get("source_kind"), c.get("source_ref"),
         to_int(c.get("adapter_order"), 1000))
        for c in selected
    }
    selected_mine = [c for c in selected if c.get("name") == name]
    kept, _duplicates = dedupe_candidates(selected_mine)
    kept_key = None
    if kept:
        winner = kept[0]
        kept_key = (winner.get("name"), winner.get("source_kind"),
                    winner.get("source_ref"),
                    to_int(winner.get("adapter_order"), 1000))

    sources = []
    for candidate in mine:
        key = (candidate.get("name"), candidate.get("source_kind"),
               candidate.get("source_ref"),
               to_int(candidate.get("adapter_order"), 1000))
        sources.append({
            "name": candidate.get("name"),
            "source_kind": candidate.get("source_kind"),
            "source_ref": candidate.get("source_ref"),
            "provenance": candidate.get("provenance"),
            "type": candidate.get("type"),
            "value": candidate.get("value"),
            "has_value": candidate.get("has_value"),
            "group": candidate.get("group"),
            "selected": key in selected_keys,
            "kept": key == kept_key,
        })

    return {
        "success": True,
        "variable": name,
        "profile": _public_profile(profile_payload),
        "sources": sources,
        "kept": next((s for s in sources if s["kept"]), None),
        "meta": {
            "total_sources": len(sources),
            "excluded_by_rules": stats.get("excluded_by_rules", 0),
            "legacy_fallback": profile_payload is None,
        },
    }
