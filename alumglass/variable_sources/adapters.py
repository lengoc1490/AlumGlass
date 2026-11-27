# -*- coding: utf-8 -*-
"""Adapter nguồn biến cho Variable Catalog — mỗi nguồn 1 hàm, đăng ký decorator.

Hợp đồng: `adapter(ctx) -> list[dict candidate]` (xem `make_candidate`).

Nguyên tắc:
- KHÔNG tự quyết định include/exclude — đó là việc của `rules.py` + profile.
- Adapter chỉ chịu trách nhiệm "nguồn này có những biến nào, giá trị bao nhiêu,
  đến từ đâu".
- Mọi lỗi DB/thiếu app phải nuốt tại chỗ (trả list rỗng) — catalog là lớp gợi
  ý, hỏng nó không được làm hỏng form người dùng.
"""
import frappe

from alumglass.variable_sources import catalog_rows
from alumglass.variable_sources.context import (
    detect_slug_field,
    get_field_label,
    get_scalar_fieldnames,
)
from alumglass.variable_sources.field_provenance import describe_source, get_source
from alumglass.variable_sources.registry import register_adapter
from alumglass.variable_sources.rules import (
    EXCLUDE_ALL,
    INCLUDE_ALL,
    as_bool,
    get_attr,
    is_empty_value,
    parse_json_list,
    split_pipe,
)

# Giá trị hiển thị khi chưa resolve được — giữ quy ước cũ của AlumGlass.
UNKNOWN_VALUE = "—"


def make_candidate(name, label=None, var_type="Float", value=None,
                   has_value=None, source_kind="", source_ref="", group="",
                   sort_order=100, provenance="", source="local",
                   source_type="", value_source="", description="",
                   adapter_order=100, category="", only_fields=None):
    """Dựng 1 candidate đúng shape của spec §3.

    `has_value` mặc định suy từ `value`; adapter nào biết chắc (vd binding
    resolve ra None) thì truyền tường minh.
    `only_fields` = phạm vi field do NGUỒN quy định (vd FVB `applies_to_field`);
    `[]` = không giới hạn. `hide_all=True` (do catalog gắn) = ẩn ở MỌI field.
    Profile rule sẽ GIAO thêm phạm vi của nó sau.
    """
    if has_value is None:
        has_value = not is_empty_value(value)
    return {
        "name": name,
        "label": label or name,
        "type": var_type or "Float",
        "value": UNKNOWN_VALUE if value is None else value,
        "has_value": bool(has_value),
        "source_kind": source_kind,
        "source_ref": source_ref or name,
        "group": group,
        "sort_order": sort_order,
        "provenance": provenance,
        "source": source,
        "source_type": source_type or source_kind,
        "value_source": value_source or provenance,
        "description": description or "",
        "category": category or "",
        "is_required": False,
        "is_pricing_dimension": False,
        # Field mà nguồn cho phép hiện biến này (client lọc theo field đang
        # sửa). Nguồn không khai ⇒ [] (không giới hạn).
        "only_fields": list(only_fields or []),
        # True = ẩn ở MỌI field (catalog gắn khi giao phạm vi nguồn × rule
        # rỗng). `[]` KHÔNG có nghĩa "ẩn" — hai khái niệm tách riêng.
        "hide_all": False,
        # Thứ tự adapter — dùng khi dedupe trùng tên (spec §4).
        "adapter_order": adapter_order,
    }


def _first_link_field(meta, target_doctype):
    """Fieldname Link ĐẦU TIÊN trỏ tới `target_doctype` (None nếu không có)."""
    if meta is None or not target_doctype:
        return None
    try:
        for field in meta.get("fields") or []:
            if field.fieldtype == "Link" and field.options == target_doctype:
                return field.fieldname
    except Exception:
        pass
    return None


def _row_value(row, fieldname, default=None):
    if row is None:
        return default
    try:
        return row.get(fieldname, default)
    except Exception:
        return default


# ══════════════════════════════════════════════════════════════════════
# 1. Formula Variable Binding (scope doctype/field)
# ══════════════════════════════════════════════════════════════════════
def _split_field_scope(value):
    """`applies_to_field` của FVB → list fieldname.

    Binding lưu dạng 1 fieldname hoặc danh sách ngăn `|`/`,`. Rỗng ⇒ [] = mọi
    field (giữ nguyên hành vi "không khai thì không giới hạn").
    """
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        raw = str(value).replace(",", "|")
    return split_pipe(raw)


def _dedupe_bindings(bindings):
    """Gộp binding trùng theo (variable_name, applies_to_doctype).

    `get_scope_bindings_multi` đã lọc scope, nhưng đường fallback (gọi
    `get_scope_bindings` cho từng doctype) có thể lặp binding global — gộp ở
    đây để không sinh 2 candidate y hệt.
    """
    seen = set()
    out = []
    for binding in bindings or []:
        key = (binding.get("variable_name"),
               binding.get("applies_to_doctype") or "")
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(binding)
    return out


@register_adapter("fvb_scope", label="Formula Variable Binding", order=10)
def fvb_scope(ctx):
    try:
        from formula_builder.api.binding_scope import (
            get_scope_bindings, get_scope_bindings_multi)
        from formula_builder.api.data_source_registry import (
            resolve_bindings_with_deps)
    except Exception:
        try:
            # Bản formula_builder cũ chưa có API multi-scope.
            from formula_builder.api.binding_scope import get_scope_bindings
            from formula_builder.api.data_source_registry import (
                resolve_bindings_with_deps)
            get_scope_bindings_multi = None
        except Exception:
            # Site không cài formula_builder → nguồn này rỗng, các nguồn khác chạy.
            return []

    # Khi sửa field TRÊN DÒNG CON, binding scope child doctype (vd
    # `AL Bom Item`) phải được lấy cùng binding scope cha — nếu chỉ hỏi
    # doctype cha thì mất sạch binding của dòng.
    child_doctype = ctx.get_child_doctype(ctx.child_table) if ctx.child_table else None
    scope_doctypes = [d for d in (ctx.doctype, child_doctype) if d]

    try:
        if get_scope_bindings_multi is not None:
            bindings = get_scope_bindings_multi(
                scope_doctypes, field=ctx.fieldname or "") or []
        else:
            merged = []
            for scope_doctype in scope_doctypes:
                merged.extend(
                    get_scope_bindings(scope_doctype, ctx.fieldname or "") or [])
            bindings = merged
    except Exception:
        frappe.log_error(frappe.get_traceback(),
                         title="Variable catalog: get_scope_bindings")
        return []

    bindings = _dedupe_bindings(bindings)
    if not bindings:
        return []

    parent_doc = ctx.get_doc()
    row = ctx.get_current_row() if child_doctype else None

    # Chia 2 nhóm để resolve ĐÚNG document: binding của dòng con đọc giá trị
    # trên dòng (row), binding còn lại đọc trên chứng từ cha.
    child_bindings = []
    other_bindings = []
    for binding in bindings:
        if child_doctype and binding.get("applies_to_doctype") == child_doctype:
            child_bindings.append(binding)
        else:
            other_bindings.append(binding)

    values = {}
    if other_bindings:
        try:
            values.update(
                resolve_bindings_with_deps(other_bindings, parent_doc) or {})
        except Exception:
            # Handler của FB có thể ném (thiếu bảng, sai cấu hình) — vẫn hiện
            # biến với giá trị default thay vì mất cả nguồn.
            frappe.log_error(frappe.get_traceback(),
                             title="Variable catalog: resolve_bindings_with_deps")

    child_values = {}
    if child_bindings and row is not None:
        try:
            child_values = resolve_bindings_with_deps(child_bindings, row) or {}
        except Exception:
            frappe.log_error(frappe.get_traceback(),
                             title="Variable catalog: resolve_bindings_with_deps (row)")
    if child_values:
        # Giá trị resolve từ DÒNG cụ thể hơn — đè lên bản resolve từ chứng từ
        # cha, nhưng chỉ khi có giá trị thật (None không được xoá giá trị cha).
        for name, value in child_values.items():
            if value is not None:
                values[name] = value

    child_ids = {id(binding) for binding in child_bindings}

    candidates = []
    # Phát candidate của dòng con TRƯỚC để dedupe (cùng sort/adapter order)
    # giữ bản cụ thể hơn khi cả hai cùng có giá trị.
    for binding in child_bindings + other_bindings:
        name = binding.get("variable_name")
        if not name:
            continue
        source_type = binding.get("source_type") or "binding"
        is_global = as_bool(binding.get("is_global"), False)
        scope_doctype = (binding.get("applies_to_doctype")
                         or (child_doctype if id(binding) in child_ids else ctx.doctype))

        value = child_values.get(name) if id(binding) in child_ids else None
        if value is None:
            value = values.get(name)
        if value is None:
            value = binding.get("default_value")

        group = ("Bindings · FB (global)" if is_global
                 else f"Bindings · {scope_doctype}")
        candidate = make_candidate(
            name,
            label=binding.get("variable_label") or name,
            var_type=binding.get("data_type") or "Float",
            value=value,
            has_value=value is not None,
            source_kind="fvb_scope",
            source_ref=name,
            group=group,
            sort_order=100,
            provenance=f"Formula Variable Binding · {source_type}"
                       + (f" · {scope_doctype}" if scope_doctype else ""),
            source="global" if is_global else "local",
            source_type=source_type,
            description=binding.get("description") or "",
            adapter_order=10,
            # `applies_to_field` của binding phải lọc được ở CLIENT kể cả khi
            # context chỉ fetch 1 lần cho cả form (spec §6.3 của formula_builder
            # không gửi fieldname theo từng lần gõ).
            only_fields=_split_field_scope(binding.get("applies_to_field")),
        )
        # Gắn scope để explain/preview phân biệt được 2 binding cùng tên.
        candidate["scope_doctype"] = binding.get("applies_to_doctype") or ""
        candidates.append(candidate)

    return candidates


# ══════════════════════════════════════════════════════════════════════
# 2. Cost Bucket
# ══════════════════════════════════════════════════════════════════════
@register_adapter("cost_bucket", label="Cost Bucket", order=20)
def cost_bucket(ctx):
    try:
        rows = frappe.get_all(
            "AL Cost Bucket",
            filters={"is_active": 1},
            fields=["bucket_code", "bucket_name", "bucket_role",
                    "report_group", "sort_order"],
            order_by="sort_order asc, bucket_code asc",
        ) or []
    except Exception:
        return []

    resolved = ctx.resolved
    candidates = []
    for row in rows:
        code = row.get("bucket_code")
        if not code:
            continue
        value = resolved.get(code)
        candidates.append(make_candidate(
            code,
            label=f"{code} — {row.get('bucket_name') or ''}".rstrip(" —"),
            var_type="Float",
            value=value,
            has_value=value is not None,
            source_kind="cost_bucket",
            source_ref=code,
            group=row.get("report_group") or "Cost Bucket",
            sort_order=row.get("sort_order") or 100,
            provenance="AL Cost Bucket",
            source_type="cost_bucket",
            value_source="Tính tự động khi chạy BomOrchestrator B4-B5",
            description=f"Cost Bucket ({row.get('bucket_role') or ''}) · "
                        f"giá trị được tính khi engine chạy",
            adapter_order=20,
        ))
    return candidates


# ══════════════════════════════════════════════════════════════════════
# 3-4. AL Variable Library — system / user
# ══════════════════════════════════════════════════════════════════════
def _library_candidates(ctx, rows, is_system, source_kind, group, order,
                        value_source):
    """Candidate từ danh sách dòng đã đọc sẵn.

    `rows` do caller quyết định nguồn: biến hệ đọc trực tiếp Library
    (`is_system=1`); biến người dùng đọc `catalog_rows` để KHÔNG trộn
    common/row-literal/user vào nhau (xem `variable_sources/catalog_rows.py`).
    """
    resolved = ctx.resolved if is_system else {}
    candidates = []
    for row in rows:
        name = (row.get("var_name") or "").strip()
        if not name:
            continue
        # Dòng bị tắt: ⛔ gợi ý. `is_active` rỗng (site chưa migrate) = bật.
        if not as_bool(row.get("is_active"), True):
            continue

        if is_system:
            actual = resolved.get(name)
            value = actual if actual is not None else (row.get("default_value") or None)
            if actual is not None:
                src = f"ĐÃ RESOLVE từ {ctx.doctype} '{ctx.docname}'"
            elif row.get("source_doctype") and row.get("source_field"):
                src = (f"Engine resolve từ {row.get('source_doctype')}."
                       f"{row.get('source_field')} khi chạy BOM")
            else:
                src = value_source
        else:
            value = None
            src = value_source

        candidates.append(make_candidate(
            name,
            label=f"{name} — {row.get('var_label') or ''}".rstrip(" —"),
            var_type=row.get("var_type") or "Float",
            value=value,
            has_value=value is not None,
            source_kind=source_kind,
            source_ref=name,
            group=row.get("group_label") or group,
            sort_order=row.get("sort_order") or 200,
            provenance="AL Variable Library",
            source_type="variable_library",
            value_source=src,
            description=row.get("description") or "",
            adapter_order=order,
            category=row.get("category") or "",
        ))
    return candidates


@register_adapter("variable_library_system", label="System Variable", order=30)
def variable_library_system(ctx):
    # ⛔ Đọc thêm cột mới (`is_active`/`group_label`/`sort_order`) ở đây: site
    # vừa deploy mã nhưng CHƯA migrate sẽ nổ `Unknown column` và adapter biến
    # hệ trả rỗng — mất toàn bộ biến hệ khỏi gợi ý. Bốn cột đó chỉ cần cho
    # nhánh người dùng (đã qua `catalog_rows`, nơi có kiểm cột).
    try:
        rows = frappe.get_all(
            "AL Variable Library",
            filters={"is_system": 1},
            fields=["var_name", "var_label", "var_type", "category",
                    "default_value", "description",
                    "source_doctype", "source_field"],
            order_by="var_name asc",
        ) or []
    except Exception:
        return []
    return _library_candidates(
        ctx, rows, True, "variable_library_system", "System Variables", 30,
        "Default · AL Variable Library (is_system=1)")


@register_adapter("variable_library_user", label="User Variable", order=40)
def variable_library_user(ctx):
    # `KIND_USER` = is_system=0, KHÔNG phải biến người dùng nhập (common) và
    # KHÔNG phải row literal — hai loại kia có adapter riêng, tránh chồng lấn.
    return _library_candidates(
        ctx, catalog_rows.active_rows(catalog_rows.KIND_USER), False,
        "variable_library_user", "User Variables", 40,
        "Người dùng nhập khi mở dialog Tham số BOM")


# ══════════════════════════════════════════════════════════════════════
# 5. AL Variable Set
# ══════════════════════════════════════════════════════════════════════
def resolve_variable_set_names(ctx):
    """Tên AL Variable Set áp dụng cho chứng từ hiện tại — DATA-DRIVEN.

    Thứ tự (theo yêu cầu điều phối):
      a. Field Link trên chính doctype trỏ thẳng `AL Variable Set`
         (AL Accessory Set.variable_set rơi đúng vào bước này).
      b. Không có (a): field Link trỏ `AL Bom Set` → lấy
         `AL Bom Set.variable_set`.
      c. Không có (b): field `product_type` (Link `AL Product Type`) có giá trị
         → lấy `AL Variable Set` đang dùng khớp product_type.
         Quy tắc cố định khi nhiều bản ghi khớp: `modified desc` (bản sửa gần
         nhất), KHÔNG đổi tuỳ dữ liệu.
    """
    names = []
    doc = ctx.get_doc()
    meta = ctx.meta if ctx.doctype else None

    def _add(name):
        name = (name or "").strip()
        if name and name not in names:
            names.append(name)

    if doc is not None and meta is not None:
        direct = _first_link_field(meta, "AL Variable Set")
        if direct:
            _add(_row_value(doc, direct))
        else:
            bom_field = _first_link_field(meta, "AL Bom Set")
            bom_name = _row_value(doc, bom_field) if bom_field else None
            if bom_name:
                try:
                    _add(frappe.db.get_value("AL Bom Set", bom_name, "variable_set"))
                except Exception:
                    pass

        product_type_field = None
        try:
            field = meta.get_field("product_type")
            if field is not None and field.fieldtype == "Link" \
                    and field.options == "AL Product Type":
                product_type_field = "product_type"
        except Exception:
            product_type_field = None

        if product_type_field:
            product_type = _row_value(doc, product_type_field)
            if product_type:
                try:
                    matched = frappe.get_all(
                        "AL Variable Set",
                        filters={"product_type": product_type, "is_active": 1},
                        pluck="name",
                        order_by="modified desc",
                        limit=1,
                    ) or []
                    if matched:
                        _add(matched[0])
                except Exception:
                    pass

    return names


def _explicit_variable_set_refs(profile):
    """Mã set khai tường minh trong rule Include (`source_ref` khác */AUTO)."""
    refs = []
    for rule in (profile or {}).get("rules") or []:
        if (get_attr(rule, "action") or "").strip().lower() == "exclude":
            continue
        if (get_attr(rule, "source_kind") or "").strip() != "variable_set":
            continue
        source_ref = (get_attr(rule, "source_ref") or "").strip()
        if not source_ref or source_ref == "*" or source_ref.upper() == "AUTO":
            continue
        for code in split_pipe(source_ref):
            if code and code.upper() != "AUTO" and code not in refs:
                refs.append(code)
    return refs


@register_adapter("variable_set", label="AL Variable Set", order=45)
def variable_set(ctx):
    set_names = _explicit_variable_set_refs(ctx.profile)
    for name in resolve_variable_set_names(ctx):
        if name not in set_names:
            set_names.append(name)

    candidates = []
    for set_name in set_names:
        try:
            if not frappe.db.exists("AL Variable Set", set_name):
                continue
            variable_set_doc = frappe.get_cached_doc("AL Variable Set", set_name)
        except Exception:
            continue

        set_code = variable_set_doc.get("set_code") or set_name
        set_label = variable_set_doc.get("set_name") or set_name
        for item in variable_set_doc.get("items") or []:
            var_name = item.get("variable")
            if not var_name:
                continue

            # Library là nguồn sự thật cho label/type; item có thể override.
            lib = None
            try:
                lib = frappe.get_cached_doc("AL Variable Library", var_name)
            except Exception:
                lib = None

            item_label = ((lib.get("var_label") if lib else None)
                          or item.get("var_label") or "")
            label = f"{var_name} — {item_label}".rstrip(" —") if item_label \
                else var_name

            value = ctx.resolved.get(var_name)
            candidates.append(make_candidate(
                var_name,
                label=label,
                var_type=(lib.get("var_type") if lib else None)
                         or item.get("var_type") or "Float",
                value=value,
                has_value=value is not None,
                source_kind="variable_set",
                source_ref=set_code,
                group=f"Variable Set · {set_code}",
                sort_order=item.get("sort_order") or 100,
                provenance=f"AL Variable Set {set_code}",
                source_type="variable_set",
                value_source=f"Từ Variable Set '{set_label}' — user nhập khi mở dialog",
                description=f"Variable Set · '{set_label}'",
                adapter_order=45,
                category=lib.get("category") if lib else "",
            ))
    return candidates


# ══════════════════════════════════════════════════════════════════════
# 6. Cost Template line
# ══════════════════════════════════════════════════════════════════════
def _resolve_cost_template(ctx):
    """Document AL Cost Template áp dụng cho ngữ cảnh hiện tại (hoặc None)."""
    if ctx.doctype == "AL Cost Template":
        return ctx.get_doc()

    field = _first_link_field(ctx.meta, "AL Cost Template") if ctx.doctype else None
    doc = ctx.get_doc()
    template_name = _row_value(doc, field) if (field and doc is not None) else None
    if not template_name:
        return None
    try:
        return frappe.get_cached_doc("AL Cost Template", template_name)
    except Exception:
        return None


@register_adapter("cost_template_line", label="Cost Template Line", order=50)
def cost_template_line(ctx):
    template = _resolve_cost_template(ctx)
    if template is None:
        return []

    rows = list(template.get("items") or [])
    # B6 tính TUẦN TỰ theo bảng: dòng đang sửa chỉ được thấy line phía TRƯỚC
    # nó (dùng line phía sau là tham chiếu vòng — luôn ra 0/None).
    if ctx.doctype == "AL Cost Template" and ctx.child_table == "items" \
            and ctx.row_index is not None:
        rows = rows[:ctx.row_index]

    candidates = []
    for index, row in enumerate(rows):
        line_code = row.get("line_code")
        if not line_code:
            continue
        candidates.append(make_candidate(
            line_code,
            label=f"{line_code} — {row.get('line_label') or ''}".rstrip(" —"),
            var_type="Float",
            value=None,
            source_kind="cost_template_line",
            source_ref=line_code,
            group="Cost Template Lines",
            sort_order=row.get("sort_order") or index,
            provenance="AL Cost Template Item",
            source_type="cost_template_line",
            value_source="Tính tuần tự khi BomOrchestrator chạy B6",
            description="Dòng giá thành tự định nghĩa (line_code)",
            adapter_order=50,
        ))
    return candidates


# ══════════════════════════════════════════════════════════════════════
# 7. Formula Global Variable
# ══════════════════════════════════════════════════════════════════════
@register_adapter("formula_global", label="Formula Global Variable", order=55)
def formula_global(ctx):
    try:
        rows = frappe.get_all(
            "Formula Global Variable",
            filters={"is_active": 1},
            fields=["var_name", "label", "var_type", "value_source",
                    "constant_value", "category", "description"],
            order_by="var_name asc",
        ) or []
    except Exception:
        return []

    candidates = []
    for row in rows:
        name = row.get("var_name")
        if not name:
            continue
        value_source_kind = (row.get("value_source") or "CONSTANT").upper()
        value = row.get("constant_value") if value_source_kind == "CONSTANT" else None
        candidates.append(make_candidate(
            name,
            label=f"{name} — {row.get('label') or 'Hằng số toàn cục'}",
            var_type=row.get("var_type") or "Float",
            value=value,
            has_value=value is not None,
            source_kind="formula_global",
            source_ref=name,
            group="Formula Global Variables",
            sort_order=100,
            provenance="Formula Global Variable",
            source="global",
            source_type="formula_global_var",
            value_source=f"Hằng số toàn cục · {value_source_kind}",
            description=row.get("description") or "Formula Builder Global Variable",
            adapter_order=55,
            category=row.get("category") or "",
        ))
    return candidates


# ══════════════════════════════════════════════════════════════════════
# 8-9. Row Literal / Common Variable — sau B2 nằm trong AL Variable Library
#     (`catalog_rows` lo phần tương thích: site chưa migrate đọc Settings)
# ══════════════════════════════════════════════════════════════════════
@register_adapter("row_literal", label="Row Literal", order=60)
def row_literal(ctx):
    rows = catalog_rows.active_rows(catalog_rows.KIND_ROW)
    current_row = ctx.get_current_row()
    doc = ctx.get_doc()

    candidates = []
    for row in rows:
        name = (row.get("var_name") or "").strip()
        if not name:
            continue

        # Giá trị chỉ lấy khi RẺ: dòng đang sửa, hoặc field cùng tên trên chứng từ.
        if current_row is not None:
            value = _row_value(current_row, name)
            provenance = f"{ctx.child_table} (dòng hiện tại)"
        elif doc is not None:
            value = _row_value(doc, name)
            provenance = f"{ctx.doctype} (chứng từ hiện tại)"
        else:
            value, provenance = None, "AL Bom Item (dòng hiện tại)"

        # Nguồn gốc (một chỗ duy nhất — field_provenance): ưu tiên cột
        # `source_doctype`/`source_field` khai trên dòng, không thì bảng mặc
        # định. Tooltip autocomplete đọc `value_source` ⇒ câu "Nguồn: …" hiện
        # ngay cho người cấu hình, không bắt họ mở tài liệu.
        source_desc = describe_source(name, row)
        if source_desc:
            value_source = "Nguồn: %s" % source_desc
            provenance = "%s · %s" % (provenance, value_source)
        else:
            value_source = "Hệ thống tự điền khi tính giá"

        candidates.append(make_candidate(
            name,
            label=f"{name} — {row.get('var_label') or ''}".rstrip(" —"),
            var_type=row.get("var_type") or "Float",
            value=value,
            has_value=value is not None,
            source_kind="row_literal",
            source_ref=name,
            group=row.get("group_label") or "Row Literals",
            sort_order=row.get("sort_order") or 300,
            provenance=provenance,
            source_type="row_literal",
            value_source=value_source,
            description=row.get("description")
                        or "Tự động inject — mỗi dòng BOM có giá trị riêng",
            adapter_order=60,
        ))
    return candidates


@register_adapter("common_var", label="Common Variable", order=70)
def common_var(ctx):
    rows = catalog_rows.active_rows(catalog_rows.KIND_COMMON)
    resolved = ctx.resolved

    candidates = []
    for row in rows:
        name = (row.get("var_name") or "").strip()
        if not name:
            continue
        value = resolved.get(name)
        candidates.append(make_candidate(
            name,
            label=f"{name} — {row.get('var_label') or ''}".rstrip(" —"),
            var_type=row.get("var_type") or "Float",
            value=value,
            has_value=value is not None,
            source_kind="common_var",
            source_ref=name,
            group=row.get("group_label") or "BOM Input Variables",
            sort_order=row.get("sort_order") or 300,
            provenance="AL Variable Library · người dùng nhập",
            source_type="common_var",
            value_source="Người dùng nhập khi mở dialog Tham số BOM",
            description=row.get("description") or "BOM input variable — giá trị đến từ user",
            adapter_order=70,
        ))
    return candidates


# ══════════════════════════════════════════════════════════════════════
# 10. Doctype field (chứng từ cha hoặc dòng đang sửa)
# ══════════════════════════════════════════════════════════════════════
@register_adapter("doctype_field", label="Doctype Field", order=80)
def doctype_field(ctx):
    doctype, row = ctx.get_field_scope()
    if not doctype:
        return []

    doc = ctx.get_doc()
    candidates = []
    for fieldname in get_scalar_fieldnames(doctype):
        if row is not None:
            value = _row_value(row, fieldname)
        elif doc is not None:
            value = _row_value(doc, fieldname)
        else:
            value = None
        field_type = "Data"
        try:
            field = frappe.get_meta(doctype).get_field(fieldname)
            if field is not None:
                field_type = field.fieldtype
        except Exception:
            pass
        candidates.append(make_candidate(
            fieldname,
            label=get_field_label(doctype, fieldname),
            var_type=field_type,
            value=value,
            has_value=value is not None,
            source_kind="doctype_field",
            source_ref=fieldname,
            group=f"Trường · {doctype}",
            sort_order=400,
            provenance=doctype,
            source_type="doctype_field",
            value_source=f"Field của {doctype}",
            description=f"{doctype}.{fieldname}",
            adapter_order=80,
        ))
    return candidates


# ══════════════════════════════════════════════════════════════════════
# References — biến chéo dòng `items.<slug>.<field>`
# ══════════════════════════════════════════════════════════════════════
def _slug_rule_tables(profile):
    """(tập bảng được include, tập bảng bị exclude) từ rule `slug_reference`."""
    include, exclude = None, set()
    for rule in (profile or {}).get("rules") or []:
        if not as_bool(get_attr(rule, "is_active"), True):
            continue
        if (get_attr(rule, "source_kind") or "").strip() != "slug_reference":
            continue
        tables = [t for t in split_pipe(get_attr(rule, "source_ref"))
                  if t and t != "*" and t.upper() != "AUTO"]
        if (get_attr(rule, "action") or "").strip().lower() == "exclude":
            exclude.update(tables)
        elif tables:
            include = (include or set()) | set(tables)
    return include, exclude


def _resolve_label_field(child_doctype, label_field):
    """Field nhãn của dòng: khai tường minh → line_name → item_code → không có.

    `AL Accessory Item` không có `line_name` nên nếu cấu hình chép từ tài liệu
    sẽ rơi về `item_code` — nhãn vẫn đọc được thay vì chỉ hiện slug.
    """
    if label_field and _has_field(child_doctype, label_field):
        return label_field
    for candidate in ("line_name", "item_code"):
        if _has_field(child_doctype, candidate):
            return candidate
    return None


def _append_references(refs, ctx, table, child_doctype, id_field, fields,
                       label_field=None, include_index_form=True):
    """Sinh references cho 1 child table — dạng slug và dạng index."""
    if not table or not child_doctype:
        return
    doc = ctx.get_doc()
    if doc is None:
        return

    id_field = id_field or detect_slug_field(child_doctype)
    fields = fields or get_scalar_fieldnames(child_doctype)
    label_field = _resolve_label_field(child_doctype, label_field)

    for index, row in enumerate(ctx.get_child_rows(table)):
        slug = (_row_value(row, id_field) or "").strip() if id_field else ""
        row_label = (_row_value(row, label_field) if label_field else "") or slug
        for fieldname in fields:
            field_label = get_field_label(child_doctype, fieldname)
            # Nguồn của biến chỉ hữu ích khi KHÁC doctype của chính dòng BOM
            # (trường công thức của dòng thì nguồn chính là dòng đó).
            # `glass_thick` đã có nhãn "(tên cũ)" ở nơi khác — ⛔ thêm nguồn
            # nữa sẽ rối; bỏ hậu tố cho biến này.
            source = get_source(fieldname)
            source_suffix = ""
            if source and fieldname != "glass_thick" \
                    and source["doctype"] != child_doctype:
                source_suffix = " (nguồn: %s.%s)" % (
                    source["doctype"], source["field"])
            if slug:
                name = f"{table}.{slug}.{fieldname}"
                refs.append({
                    "name": name,
                    "label": f"{field_label} — {row_label}{source_suffix}",
                    "insert": name,
                    "table": table,
                    "slug": slug,
                    "field": fieldname,
                })
            if include_index_form:
                name = f"{table}[{index}].{fieldname}"
                refs.append({
                    "name": name,
                    "label": f"{field_label} — hàng {index + 1}{source_suffix}",
                    "insert": name,
                    "table": table,
                    "idx": index,
                    "field": fieldname,
                })


def build_references(ctx, profile=None):
    """Sinh danh sách gợi ý biến chéo dòng.

    Thứ tự quyết định (spec §3.11 + §4):
      1. `cross_row` của profile (nếu có) — cấu hình tường minh.
      2. Không có cross_row nhưng CÓ rule Include `slug_reference` ⇒ chỉ sinh
         cho các bảng rule trỏ tới ("rule bật biến chéo cho bảng đó").
      3. Không có cả hai + default_action=INCLUDE_ALL ⇒ hành vi CŨ: mọi child
         table của doctype cha, field vô hướng, tự dò slug.
      4. Còn lại ⇒ không gợi ý (EXCLUDE_ALL = allowlist, không khai = không có).

    Rule `slug_reference` Exclude luôn loại bảng tương ứng ở mọi nhánh.
    """
    profile = profile or {}
    include_tables, exclude_tables = _slug_rule_tables(profile)

    cross_rows = [row for row in (profile.get("cross_row") or [])
                  if as_bool(get_attr(row, "enabled"), True)]
    cross_rows = [row for row in cross_rows
                  if (row.get("table_field") or "").strip()]
    if include_tables:
        cross_rows = [row for row in cross_rows
                      if (row.get("table_field") or "").strip() in include_tables]

    references = []
    if cross_rows:
        for row in cross_rows:
            table = (row.get("table_field") or "").strip()
            if table in exclude_tables:
                continue
            child_doctype = ctx.get_child_doctype(table)
            _append_references(
                references, ctx, table, child_doctype,
                (row.get("id_field") or "").strip() or None,
                parse_json_list(row.get("fields")),
                (row.get("label_field") or "").strip() or None,
                as_bool(row.get("include_index_form"), True),
            )
        return references

    # Không có cross_row tường minh: quyết định theo rule slug_reference /
    # default_action.
    if include_tables:
        table_names = include_tables
    else:
        default_action = (profile.get("default_action") or INCLUDE_ALL)
        if default_action == EXCLUDE_ALL or not ctx.doctype:
            return references
        table_names = None  # mọi child table — hành vi cũ

    try:
        table_fields = list(ctx.meta.get_table_fields())
    except Exception:
        table_fields = []
    for table_field in table_fields:
        table = table_field.fieldname
        if table in exclude_tables:
            continue
        if table_names is not None and table not in table_names:
            continue
        child_doctype = table_field.options
        label_field = "line_name" if _has_field(child_doctype, "line_name") else None
        _append_references(
            references, ctx, table, child_doctype,
            detect_slug_field(child_doctype),
            get_scalar_fieldnames(child_doctype),
            label_field,
            True,
        )
    return references


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).get_field(fieldname) is not None
    except Exception:
        return False
