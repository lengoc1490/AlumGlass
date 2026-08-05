import frappe


@frappe.whitelist()
def calculate_bom(quotation_item_name):
    """Tính BOM cho 1 dòng báo giá - trả về GIA_VAT + chi tiết.

    Đây là API chính được gọi từ nút "Tính giá" trên Quotation Item.
    """
    from alumglass.engine.bom_orchestrator import BomOrchestrator

    orch = BomOrchestrator(quotation_item_name)
    return orch.run()


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
    """Resolve giá trị THỰC TẾ từ document (Profile System, Product Type)."""
    vals = {}
    try:
        doc = frappe.get_cached_doc(doctype, docname)
        if doctype == "AL Bom Set":
            if doc.get("profile_system"):
                ps = frappe.get_cached_doc("AL Profile System", doc.profile_system)
                for f in ["offset_frame", "offset_glass", "offset_fixed", "offset_crossbar"]:
                    vals[f.upper()] = ps.get(f)
            if doc.get("product_type"):
                pt = frappe.get_cached_doc("AL Product Type", doc.product_type)
                vals["NC_SX_PCT"] = pt.get("nc_pct")
                vals["NC_LD_PCT"] = pt.get("nc_ld_rate")
                vals["PROFIT_MARGIN"] = pt.get("profit_margin")
    except Exception:
        pass
    return vals


@frappe.whitelist()
def get_formula_context(doctype, docname=None):
    """★ DATA-DRIVEN: Lấy context variables cho autocomplete formula fields.

    Không hardcode biến nào — mọi biến được khám phá động từ DB.
    Người dùng thêm biến mới = thêm record vào bảng tương ứng, không cần sửa code.

    Nguồn biến (theo thứ tự ưu tiên):
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
    for sv in frappe.get_all("AL Variable Library",
                             filters={"is_system": 1},
                             fields=["var_name", "var_label", "var_type",
                                     "default_value", "description",
                                     "source_doctype", "source_field"],
                             order_by="var_name"):
        actual = resolved.get(sv["var_name"])
        val = actual if actual is not None else sv.get("default_value")
        src = (f"ĐÃ RESOLVE từ {doctype} '{docname}'" if actual is not None
               else f"Default · Engine resolve từ {sv.get('source_doctype','')}.{sv.get('source_field','')} khi chạy BOM")
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
    if docname and doctype in ("AL Bom Set", "AL BOM", "AL Bom Engine"):
        _inject_variable_set_vars(variables, doctype, docname, resolved)

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

    return {
        "doctype": doctype,
        "docname": docname,
        "variables": variables,
        "references": references,
        "total_sources": len({v["source_type"] for v in variables}),
        "total_variables": len(variables),
    }


def _inject_variable_set_vars(variables, doctype, docname, resolved=None):
    """Resolve Variable Set từ document hiện tại và inject các biến."""
    resolved = resolved or {}
    variable_set_name = None
    try:
        if doctype == "AL Bom Set":
            variable_set_name = frappe.db.get_value("AL Bom Set", docname, "variable_set")
        elif doctype in ("AL BOM", "AL Bom Engine"):
            bom_set_name = frappe.db.get_value("AL BOM", docname, "bom_set")
            if bom_set_name:
                variable_set_name = frappe.db.get_value("AL Bom Set", bom_set_name, "variable_set")
    except Exception:
        pass
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
    Trả về list biến để JS dialog tự sinh form fields.
    """
    if not bom_code:
        return {"variables": []}

    bom = frappe.get_cached_doc("AL BOM", bom_code)
    if not bom.bom_set:
        return {"variables": []}

    bom_set = frappe.get_cached_doc("AL Bom Set", bom.bom_set)
    set_code = bom_set.set_code
    set_name = bom_set.set_name

    variables = []

    # ── 1. User variables từ Variable Set ─────────────────────────
    if bom_set.get("variable_set"):
        vs = frappe.get_cached_doc("AL Variable Set", bom_set.variable_set)
        set_code = vs.set_code
        set_name = vs.set_name
        for item in vs.items:
            var_name = item.variable if hasattr(item, 'variable') else item.var_name
            var_label = item.var_label or var_name
            var_type = item.var_type or "Data"
            link_doctype = item.link_doctype or ""
            select_options = item.select_options or ""

            variables.append({
                "var_name": var_name,
                "var_label": var_label,
                "var_type": var_type,
                "link_doctype": link_doctype,
                "select_options": select_options,
                "default_value": item.default_value or "",
                "is_required": item.is_required or 0,
                "sort_order": item.sort_order or 0,
            })

    # ── 2. System variables từ AL Variable Library (DATA-DRIVEN) ──
    for sv in frappe.get_all("AL Variable Library",
                              filters={"is_system": 1},
                              fields=["var_name", "var_label", "var_type",
                                      "default_value", "description"]):
        variables.append({
            "var_name": sv["var_name"],
            "var_label": sv.get("var_label") or sv["var_name"],
            "var_type": sv.get("var_type") or "Float",
            "link_doctype": "",
            "select_options": "",
            "default_value": sv.get("default_value") or "",
            "is_required": 0,
            "sort_order": 999,
            "is_system": True,
        })

    return {
        "variable_set_code": set_code,
        "variable_set_name": set_name,
        "variables": sorted(variables, key=lambda v: (
            v.get("is_system", False), v.get("sort_order", 0))),
    }
