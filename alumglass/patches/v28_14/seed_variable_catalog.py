# -*- coding: utf-8 -*-
"""v28_14 — Seed Variable Catalog (Settings + Formula Field + Profile mẫu).

Vì sao cần patch thay vì sửa seed sẵn có:
  Ba bảng dưới đây (AL Variable Settings, AL Formula Field, AL Variable
  Profile) là MỚI, chưa có dữ liệu trên site đang chạy. Patch seed đúng 1 lần
  để:
    1. Hai danh sách từng hardcode trong `api/__init__.py` (Common Variables,
       Row Literals) chuyển thành DỮ LIỆU — thêm biến không phải sửa code.
    2. Các field công thức từng hardcode trong JS (`FORMULA_DOCTYPE_REGISTRY`)
       có record để JS đọc qua API.
    3. `AL Cost Template` / `AL Accessory Set` có profile mặc định, tránh rơi
       về danh sách biến quá rộng.

Idempotent: mọi bước đều `frappe.db.exists` trước khi ghi, chạy lại không
nhân đôi record và KHÔNG ghi đè cấu hình admin đã sửa tay.

⚠️ Field `doctype` của `AL Formula Field` phải đặt tên `target_doctype`:
`doctype` là từ khoá dành riêng của Frappe
(`frappe/model/base_document.py::_reserved_keywords`) — dùng làm fieldname sẽ
bị DocType từ chối khi migrate.
"""
import json

import frappe

# ══════════════════════════════════════════════════════════════════════
# 1. AL Variable Settings — common variables + row literals
# ══════════════════════════════════════════════════════════════════════
# (var_name, var_label, var_type, group_label, sort_order)
_COMMON_VARIABLES = (
    ("W_mm", "Chiều rộng (mm)", "Float", "BOM Input Variables", 10),
    ("H_mm", "Chiều cao (mm)", "Float", "BOM Input Variables", 20),
    ("n_panel", "Số cánh", "Int", "BOM Input Variables", 30),
    ("TransomHeight_mm", "Cao ô kính", "Float", "BOM Input Variables", 40),
    ("SideLiteWidth", "Rộng vách kính", "Float", "BOM Input Variables", 50),
    ("SideLiteHeight", "Cao vách kính", "Float", "BOM Input Variables", 60),
    ("installation_height_m", "Cao lắp đặt (m)", "Float", "BOM Input Variables", 70),
    ("TONG_M2", "Tổng diện tích (m²)", "Float", "BOM Input Variables", 80),
)

_ROW_LITERALS = (
    ("weight_per_unit", "TL riêng (kg/m)", "Float", "Row Literals", 10),
    ("unit_price", "Đơn giá", "Float", "Row Literals", 20),
    ("unit_qty", "SL đơn vị", "Float", "Row Literals", 30),
    ("total_qty", "Tổng SL", "Float", "Row Literals", 40),
    ("line_total", "Thành tiền", "Float", "Row Literals", 50),
    ("scrap_pct", "% Hao hụt", "Float", "Row Literals", 60),
    ("glass_thick", "Độ dày kính", "Float", "Row Literals", 70),
    ("glass_type", "Loại kính", "Data", "Row Literals", 80),
    ("calc_pattern", "Pattern", "Data", "Row Literals", 90),
    # Engine inject vào glass_data/row context (AL Glass Master.max_area_m2 —
    # khổ kính tối đa nhà cung cấp). Khai ở đây để cảnh báo `rule_input_expr`
    # không báo oan biến này.
    ("max_area_m2", "Khổ kính tối đa (m²)", "Float", "Row Literals", 100),
)


def _seed_settings():
    """Seed danh sách biến, KHÔNG đè cấu hình admin đã sửa.

    - `common_variables`: chỉ seed khi bảng đang RỖNG (đây là gợi ý cho người
      dùng, admin có thể đã thay bằng danh sách riêng).
    - `row_literals`: bổ sung theo TÊN còn thiếu (xem giải thích bên dưới).
    """
    settings = frappe.get_single("AL Variable Settings")
    changed = False

    if not (settings.get("common_variables") or []):
        for name, label, var_type, group, sort_order in _COMMON_VARIABLES:
            settings.append("common_variables", {
                "var_name": name,
                "var_label": label,
                "var_type": var_type,
                "group_label": group,
                "sort_order": sort_order,
                "is_active": 1,
                "description": "Biến người dùng nhập khi mở dialog Tham số BOM",
            })
        changed = True
        print("  · AL Variable Settings.common_variables: +%d"
              % len(_COMMON_VARIABLES))
    else:
        print("  · AL Variable Settings.common_variables: đã có, bỏ qua")

    # Row literal: bổ sung theo TÊN còn thiếu thay vì "chỉ khi bảng rỗng" —
    # để site đã seed một phần (hoặc bản cũ chưa có `max_area_m2`) vẫn nhận
    # đủ literal engine thực sự inject, mà KHÔNG đè nhãn/thứ tự admin đã sửa.
    existing_row_literals = {
        row.get("var_name") for row in (settings.get("row_literals") or [])
        if row.get("var_name")
    }
    added_row_literals = 0
    for name, label, var_type, group, sort_order in _ROW_LITERALS:
        if name in existing_row_literals:
            continue
        settings.append("row_literals", {
            "var_name": name,
            "var_label": label,
            "var_type": var_type,
            "group_label": group,
            "sort_order": sort_order,
            "is_active": 1,
            "description": "Engine inject theo từng dòng BOM khi tính giá",
        })
        added_row_literals += 1
    if added_row_literals:
        changed = True
    print("  · AL Variable Settings.row_literals: +%d (bỏ qua %d đã có)"
          % (added_row_literals, len(existing_row_literals)))

    if changed:
        settings.flags.ignore_permissions = True
        settings.save()


# ══════════════════════════════════════════════════════════════════════
# 2. AL Formula Field — sổ đăng ký field công thức
# ══════════════════════════════════════════════════════════════════════
_FORMULA_FIELDS = (
    # AL Bom Set — các field công thức trên dòng BOM
    ("AL Bom Set", "items", "width", "slug", {"height": "70px"}, 10),
    ("AL Bom Set", "items", "height", "slug", {"height": "70px"}, 20),
    ("AL Bom Set", "items", "qty", "slug", {"height": "70px"}, 30),
    ("AL Bom Set", "items", "show_condition", "slug", {"height": "70px"}, 40),
    ("AL Bom Set", "items", "item_condition_formula", "slug",
     {"height": "70px"}, 50),
    ("AL Bom Set", "items", "rule_input_expr", "slug", {"height": "70px"}, 60),
    # Bộ phụ kiện
    ("AL Accessory Set", "items", "qty_formula", "slug", {"height": "70px"}, 10),
    # Bảng giá thành
    ("AL Cost Template", "items", "calc_formula", "",
     {"height": "80px", "float_popup": True}, 10),
    # Field cấp cha
    ("AL Alert Config", "", "trigger_condition", "", {"height": "100px"}, 10),
    ("AL Quantity Calc Method", "", "calc_fn", "", {"height": "80px"}, 10),
    ("Formula Global Variable", "", "formula_expr", "", {"height": "80px"}, 10),
)


def _seed_formula_fields():
    created = 0
    skipped = 0
    for target_doctype, child_table, fieldname, id_field, opts, sort_order \
            in _FORMULA_FIELDS:
        exists = frappe.db.exists("AL Formula Field", {
            "target_doctype": target_doctype,
            "child_table": child_table,
            "fieldname": fieldname,
        })
        if exists:
            skipped += 1
            continue

        frappe.get_doc({
            "doctype": "AL Formula Field",
            "target_doctype": target_doctype,
            "child_table": child_table,
            "fieldname": fieldname,
            "id_field": id_field,
            # JSON field lưu chuỗi — json.dumps tường minh để patch đọc lại
            # bằng json.loads ở phía API/JS không phải đoán kiểu.
            "editor_opts": json.dumps(opts, ensure_ascii=False),
            "sort_order": sort_order,
            "is_active": 1,
        }).insert(ignore_permissions=True)
        created += 1

    print("  · AL Formula Field: +%d, bỏ qua %d" % (created, skipped))


# ══════════════════════════════════════════════════════════════════════
# 3. AL Variable Profile — profile mặc định + gán cho chứng từ đang trống
# ══════════════════════════════════════════════════════════════════════
_PROFILES = (
    {
        "profile_code": "P_COST_TEMPLATE_DEFAULT",
        "profile_name": "Mặc định — AL Cost Template",
        "description": (
            "Bộ biến cho bảng giá thành: chỉ vật liệu/chi phí, dòng tự định "
            "nghĩa đứng trước, thông số hệ, hằng số, binding và biến người "
            "dùng nhập. KHÔNG gợi ý row literal / slug: B6 chỉ có context "
            "`inputs ⊕ buckets`, không có các biến dạng `{slug}__*` / "
            "`items.*` — gợi ý sẽ dẫn tới công thức chạy ra 0/None. Common "
            "var VẪN gợi ý vì chúng nằm trong `inputs` (al_bom_vars)."),
        "assign_to": "AL Cost Template",
        "rules": (
            ("Include", "cost_bucket", "*", "01 · Vật liệu & chi phí", 10),
            ("Include", "cost_template_line", "AUTO",
             "02 · Dòng tự định nghĩa", 20),
            ("Include", "variable_library_system", "*",
             "03 · Thông số hệ", 30),
            ("Include", "formula_global", "*", "04 · Hằng số", 40),
            ("Include", "fvb_scope", "AUTO", "05 · Binding", 50),
            ("Include", "common_var", "*", "06 · Thông số nhập", 60),
        ),
        "cross_row": (),
    },
    {
        "profile_code": "P_ACCESSORY_DEFAULT",
        "profile_name": "Mặc định — AL Accessory Set",
        "description": (
            "Bộ biến cho bộ phụ kiện: vật liệu/chi phí, thông số hệ, biến "
            "người dùng của Variable Set gắn với bộ, hằng số, binding, row "
            "literal và biến chéo dòng trong chính bảng items."),
        "assign_to": "AL Accessory Set",
        "rules": (
            ("Include", "cost_bucket", "*", "01 · Vật liệu & chi phí", 10),
            ("Include", "variable_library_system", "*",
             "02 · Thông số hệ", 20),
            # AL Accessory Set.variable_set nay đã được adapter dùng —
            # qty_formula có thể cần biến user của chính bộ đó.
            ("Include", "variable_set", "AUTO", "03 · Thông số nhập", 30),
            ("Include", "formula_global", "*", "04 · Hằng số", 40),
            ("Include", "fvb_scope", "AUTO", "05 · Binding", 50),
            ("Include", "common_var", "*", "06 · Thông số nhập", 60),
            ("Include", "row_literal", "*", "07 · Dòng hiện tại", 70),
            ("Include", "slug_reference", "items", "08 · Dòng khác", 80),
        ),
        "cross_row": (
            {
                "table_field": "items",
                "id_field": "slug",
                # AL Accessory Item KHÔNG có field `line_name` (khác AL Bom
                # Item) — dùng `item_code` để nhãn biến chéo đọc được.
                "label_field": "item_code",
                # Chỉ field mà B3 THẬT SỰ tạo `{slug}__<field>` cho dòng
                # phụ kiện (b3_build_formulas): literal inject
                # (qty/unit_price/calc_pattern) + synthetic luôn tạo
                # (total_qty/line_total). `qty_formula` là CHUỖI CÔNG THỨC,
                # engine KHÔNG inject `{slug}__qty_formula` ⇒ ⛔ không gợi ý.
                "fields": json.dumps(
                    ["qty", "unit_price", "calc_pattern",
                     "total_qty", "line_total"],
                    ensure_ascii=False),
                "include_index_form": 1,
                "enabled": 1,
            },
        ),
    },
)


def _seed_profiles():
    created = 0
    for cfg in _PROFILES:
        code = cfg["profile_code"]
        if frappe.db.exists("AL Variable Profile", code):
            print("  · Profile %s: đã có, bỏ qua" % code)
        else:
            doc = frappe.get_doc({
                "doctype": "AL Variable Profile",
                "profile_code": code,
                "profile_name": cfg["profile_name"],
                "is_active": 1,
                "default_action": "EXCLUDE_ALL",
                "description": cfg["description"],
                "rules": [
                    {
                        "doctype": "AL Variable Profile Rule",
                        "action": action,
                        "source_kind": source_kind,
                        "source_ref": source_ref,
                        "group_label": group_label,
                        "sort_order": sort_order,
                        "is_active": 1,
                    }
                    for action, source_kind, source_ref, group_label, sort_order
                    in cfg["rules"]
                ],
                "cross_row": [
                    {"doctype": "AL Variable Cross Row", **row}
                    for row in cfg["cross_row"]
                ],
            })
            doc.flags.ignore_permissions = True
            doc.insert()
            created += 1
            print("  · Profile %s: đã tạo" % code)

        _assign_profile(cfg["assign_to"], code)

    print("  · AL Variable Profile: +%d" % created)


def _assign_profile(doctype, profile_code):
    """Gán profile cho các bản ghi ĐANG TRỐNG `variable_profile`.

    ⛔ Chỉ gán khi cột đã tồn tại (field `variable_profile` do thay đổi doctype
    JSON thêm vào) — tránh lỗi SQL ở môi trường chưa sync phần đó.
    """
    if not frappe.db.has_column(doctype, "variable_profile"):
        print("  · Gán %s → %s: bỏ qua (chưa có cột variable_profile)"
              % (doctype, profile_code))
        return

    rows = frappe.get_all(doctype, fields=["name", "variable_profile"])
    assigned = 0
    for row in rows:
        if row.get("variable_profile"):
            continue
        # update_modified=False: đây là cấu hình kỹ thuật, không được làm
        # "modified" của chứng từ nghiệp vụ nhảy — tránh nhiễu so sánh/đồng bộ.
        frappe.db.set_value(doctype, row["name"], "variable_profile",
                            profile_code, update_modified=False)
        assigned += 1
    print("  · Gán %s → %s: %d bản ghi" % (doctype, profile_code, assigned))


def execute():
    if not frappe.db.exists("DocType", "AL Variable Profile"):
        # Patch khai ở [post_model_sync] nên nhánh này chỉ xảy ra khi cấu hình
        # patches.txt sai. Báo LỚN thay vì bỏ qua im lặng (bỏ qua = patch được
        # đánh dấu đã chạy mà không seed gì, không ai biết).
        frappe.throw(
            "v28_14.seed_variable_catalog: chưa có doctype 'AL Variable "
            "Profile'. Patch này phải chạy ở [post_model_sync] sau khi sync "
            "doctype — kiểm tra lại alumglass/patches.txt."
        )

    print("v28_14 — seed Variable Catalog")
    _seed_settings()
    _seed_formula_fields()
    # ⛔ KHÔNG set `AL Variable Settings.default_profile`: mọi doctype chưa gán
    # profile phải tiếp tục chạy đường legacy (tương thích ngược tuyệt đối).
    # Chỉ gán `variable_profile` cho 2 doctype đích, và chỉ khi đang rỗng.
    _seed_profiles()

    # Patch convention của repo: ghi sổ rồi commit ngay (patch runner không
    # tự commit với mọi đường chạy).
    frappe.db.commit()
    print("v28_14 — xong")
