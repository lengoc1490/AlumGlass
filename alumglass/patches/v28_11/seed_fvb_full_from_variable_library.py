# -*- coding: utf-8 -*-
"""D6 — Seed FVB FULL (mọi System Variable mappable) từ AL Variable Library.

Bối cảnh (de-xuat §3A + fb_source_type_contract §9):
Patch v28_9 `seed_fvb_from_variable_library` chỉ seed CỨNG 2 doctype nguồn
("AL Profile System" → profile_system, "AL Product Type" → product_type) —
với link_field hardcode. Những System Variable trỏ source_doctype KHÁC (vd
"AL Color Standard", "AL Glass Master", "Item", ...) NẾU người dùng thêm sau
này sẽ KHÔNG có FVB → engine luôn chạy resolver 1.3 (Variable Library) cho
chúng — vẫn đúng, nhưng không nằm trên layer resolve duy nhất (FVB).

Patch này GENERALIZE việc seed theo data (DATA-DRIVEN), KHÔNG hardcode doctype
link nào:
    - Với MỌI System Variable (AL Variable Library is_system=1) có
      source_doctype + source_field:
        + link_field = dò trên AL Bom Set bằng ĐÚNG hàm discovery mà engine
          dùng (`system_variable_resolver.resolve_source_link_fields`) — vì
          scope FB `_resolve_fb_context` đã là "AL Bom Set" (engine D3), và
          1.3 legacy cũng resolve từ ĐÚNG doc AL Bom Set này → cùng nguồn
          ⇒ semantics đảm bảo == old 1.3.
        + Có link_field → seed FVB source_type="linked_doctype_field",
          source_config={"link_field", "target_doctype": source_doctype,
          "target_field": source_field}, applies_to_doctype="AL Bom Set".
        + KHÔNG có link_field trên AL Bom Set → KHÔNG seed — engine 1.3 vẫn
          resolve nếu chính doctype cấp context có link (backward-compat giữ
          nguyên). Ghi vào fallback set.
    - KHÔNG làm chain_link_lookup (nếu source_doctype là record khác cần nối
      thêm chain từ AL Bom Set → KHÔNG đảm bảo semantics == 1.3 nếu 1.3
      không đi chain đó) → để engine fallback.
    - KHÔNG sửa patch v28_9 (đã chạy rồi — nếu chạy lại, _binding_exists
      chặn duplicate).

Golden-safe: scope + link giống hệt 1.3 → binding resolve CÙNG giá trị mà
resolver 1.3 resolve (cùng doc, cùng field). Child-table override
(AL Profile System.system_variables) KHÔNG nằm trong FVB — engine 1.4b áp lại
SAU FB merge (V6 P5) nên thứ tự cuối không đổi. Vars không mappable →
không có binding → `_resolve_fb_context` không trả → b1 flipped giữ resolver
1.3 fill-missing như cũ (guard `if var not in fb_ctx`).

Idempotent: check tồn tại (variable_name, applies_to_doctype, is_global)
trước khi insert — chống duplicate khi chạy lại / trùng binding v28_9 / trùng
COMPOSITE_PRICING_BINDING (install_fb_bindings, variable khác source_type).
"""
import frappe

from alumglass.al_bom_engine.system_variable_resolver import (
    resolve_source_link_fields)

# map var_type AL Variable Library → data_type Formula Variable Binding
_DTYPE_MAP = {
    "Float": "Float",
    "Int": "Int",
    "Currency": "Currency",
    "Check": "Check",
    "Data": "Data",
    "Select": "Data",
    "Link": "Data",
}


def _binding_exists(variable_name, applies_to_doctype, is_global):
    return frappe.db.exists("Formula Variable Binding", {
        "variable_name": variable_name,
        "applies_to_doctype": applies_to_doctype or "",
        "is_global": 1 if is_global else 0,
    })


def _other_binding_exists(variable_name):
    """Đã có binding KHÁC (mọi scope/is_global) cho cùng variable_name chưa.

    Nếu có → KHÔNG seed thêm: FB đã resolve biến đó theo binding hiện có,
    seed thêm 1 binding cùng tên chỉ gây mơ hồ thứ tự thắng trong
    get_live_context (2 binding cùng variable_name, resolve_priority như nhau).
    Engine legacy 1.3 khi đó cũng đã bị FB override — seed thêm không giúp gì.
    """
    return frappe.db.exists("Formula Variable Binding", {
        "variable_name": variable_name,
        "is_active": 1,
    })


def _insert(variable_name, variable_label, source_config, data_type,
            default_value, created, skipped, skip_reason=""):
    """Insert 1 FVB (AL Bom Set scope) nếu chưa tồn tại (idempotent)."""
    if _binding_exists(variable_name, "AL Bom Set", False):
        skipped["exists"] += 1
        return False
    if _other_binding_exists(variable_name):
        # Binding cùng tên đã active (vd COMPOSITE_MATERIAL_PRICE / global
        # constant) — KHÔNG tạo trùng, giữ nguyên binding hiện có.
        skipped[skip_reason or "other-binding"] += 1
        return False
    try:
        frappe.get_doc({
            "doctype": "Formula Variable Binding",
            "variable_name": variable_name,
            "variable_label": variable_label or variable_name,
            "source_type": "linked_doctype_field",
            "source_config": frappe.as_json(source_config),
            "resolve_priority": 100,
            "batch_group": "",
            "applies_to_doctype": "AL Bom Set",
            "applies_to_field": "",
            "data_type": data_type,
            "default_value": default_value if default_value is not None else "",
            "is_global": 0,
            "is_active": 1,
        }).insert(ignore_permissions=True, ignore_mandatory=True)
        created["seeded"] += 1
        return True
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "AlumGlass D6: seed FVB thất bại %s" % variable_name,
        )
        skipped["error"] += 1
        return False


def execute():
    created = {"seeded": 0}
    skipped = {"exists": 0, "no-link": 0, "other-binding": 0,
               "no-source": 0, "error": 0}

    # Nguồn "link_field khả seed" — meta AL Bom Set (KHÔNG hardcode doctype).
    # Scope engine resolve System Variable là AL Bom Set (engine D3) — chỉ seed
    # var nào AL Bom Set có link trực tiếp, để FVB linked_doctype_field resolve
    # ĐÚNG nguồn mà 1.3 legacy resolve.
    try:
        link_fields = resolve_source_link_fields("AL Bom Set")
    except Exception:
        link_fields = {}

    system_vars = frappe.get_all(
        "AL Variable Library",
        filters={"is_system": 1},
        fields=["var_name", "var_label", "var_type",
                "source_doctype", "source_field", "default_value"],
        order_by="var_name",
    ) or []

    seeded_list = []
    fallback_list = []

    for sv in system_vars:
        var_name = sv.get("var_name")
        source_doctype = sv.get("source_doctype") or ""
        source_field = sv.get("source_field") or ""
        if not var_name or not source_doctype or not source_field:
            skipped["no-source"] += 1
            fallback_list.append((var_name, "no-source_doctype/source_field"))
            continue
        link_field = link_fields.get(source_doctype)
        if not link_field:
            # Không có link trên AL Bom Set → FVB KHÔNG resolve được nguồn này
            # từ scope engine ⇒ KHÔNG seed (semantics == 1.3 không đảm bảo vì
            # 1.3 chỉ resolve qua link của doctype mà caller có; nếu doctype
            # khác có link thì engine tự dò). Giữ engine fallback.
            skipped["no-link"] += 1
            fallback_list.append((var_name, "no AL Bom Set link to %s" % source_doctype))
            continue
        dtype = _DTYPE_MAP.get(sv.get("var_type") or "Float", "Float")
        source_config = {
            "link_field": link_field,
            "target_doctype": source_doctype,
            "target_field": source_field,
        }
        if _insert(
            var_name,
            sv.get("var_label") or var_name,
            source_config,
            dtype,
            sv.get("default_value"),
            created,
            skipped,
            "other-binding",
        ):
            seeded_list.append((var_name, "%s.%s via AL Bom Set.%s"
                                % (source_doctype, source_field, link_field)))

    frappe.db.commit()

    _log = frappe.logger("alumglass")
    _log.info(
        "D6 seed_fvb_full_from_variable_library: created=%d skipped=%s"
        % (created["seeded"], skipped)
    )
    if seeded_list:
        _log.info("D6 SEEDED: %s"
                  % ", ".join("%s (%s)" % (n, s) for n, s in seeded_list))
    if fallback_list:
        _log.info("D6 FALLBACK (giữ engine 1.3): %s"
                  % ", ".join("%s (%s)" % (n, s) for n, s in fallback_list))
