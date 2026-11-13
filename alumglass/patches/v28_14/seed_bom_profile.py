# -*- coding: utf-8 -*-
"""v28_14 — Seed profile mẫu `P_BOM_DEFAULT` cho `AL Bom Set`.

Vì sao patch MỚI, không sửa `seed_variable_catalog`:
  Patch cũ đã chạy và đã ghi Patch Log trên nhiều site ⇒ sửa `_PROFILES` ở đó
  KHÔNG có tác dụng (patch runner không chạy lại). Profile của `AL Bom Set`
  sinh sau, nên tách thành patch riêng — idempotent, chạy thêm lần nữa vô hại.

Nội dung profile — bám đúng runtime B4 (`bom_orchestrator.b3_build_formulas`
dựng công thức cho `AL Bom Item`, engine chạy ở bước B4):

  Include (theo group/sort):
    01 · Thông số hệ      variable_library_system  ·  *
    02 · Thông số nhập    variable_set             ·  AUTO (Variable Set của bộ)
    03 · Thông số nhập    common_var               ·  *
    04 · Hằng số          formula_global           ·  *
    05 · Binding          fvb_scope                ·  AUTO
    06 · Dòng khác        slug_reference           ·  items
  Cross-row: bảng `items`, khoá `slug`, nhãn `line_name`, bật form gợi ý.

⛔ CỐ Ý KHÔNG có 3 rule sau (khác hẳn `P_COST_TEMPLATE_DEFAULT`) — ghi rõ để
người sau không "bổ sung cho đủ":

  1. `cost_bucket` — bucket chỉ có giá trị SAU bước B5. Công thức trong
     `AL Bom Item` chạy ở B4 ⇒ gợi ý bucket ở đây dẫn người dùng tới công thức
     luôn ra 0.
  2. `row_literal` — literal trần (`unit_price`, `glass_thick`…) KHÔNG tồn tại
     trong namespace B4. Engine chỉ inject dạng `{slug}__<field>`; dạng đúng
     để tham chiếu là cross-row `items.<slug>.unit_price`. Danh sách
     `AL Variable Settings.row_literals` chỉ đăng ký TÊN cho gợi ý/validate,
     nó không tạo ra biến ở runtime B4.
  3. `cost_template_line` — chỉ có ở B6, và `AL Bom Set` cũng không Link tới
     `AL Cost Template`.

Idempotent:
  - Profile: `frappe.db.exists` trước khi tạo. Đã có ⇒ BỎ QUA, ⛔ không ghi đè
    rule admin đã sửa tay.
  - Gán: chỉ gán cho bản ghi `AL Bom Set` đang TRỐNG `variable_profile`, và
    chỉ khi cột đã tồn tại (`frappe.db.has_column`) — tránh lỗi SQL ở môi
    trường chưa sync phần doctype JSON.
"""
import json

import frappe

PROFILE_CODE = "P_BOM_DEFAULT"
PROFILE_NAME = "Mặc định — AL Bom Set"
DEFAULT_ACTION = "EXCLUDE_ALL"
ASSIGN_TO = "AL Bom Set"
PROFILE_DOCTYPE = "AL Variable Profile"

# (action, source_kind, source_ref, group_label, sort_order)
RULES = (
    ("Include", "variable_library_system", "*", "01 · Thông số hệ", 10),
    ("Include", "variable_set", "AUTO", "02 · Thông số nhập", 20),
    ("Include", "common_var", "*", "03 · Thông số nhập", 30),
    ("Include", "formula_global", "*", "04 · Hằng số", 40),
    ("Include", "fvb_scope", "AUTO", "05 · Binding", 50),
    ("Include", "slug_reference", "items", "06 · Dòng khác", 60),
)

# Field engine B3 THẬT SỰ tạo cho mỗi dòng BOM — chỉ những field này mới có
# nghĩa ở dạng cross-row `items.<slug>.<field>` trong công thức B4:
#   - FORMULA_FIELDS:        width, height, qty (+ show_condition chỉ là biến
#                            điều kiện, không phải giá trị số)
#   - ENGINE_SYNTHETIC_FIELDS: unit_qty, total_qty, line_total
#   - row literal engine inject: unit_price, weight_per_unit, glass_thick,
#                            glass_type, calc_pattern, scrap_pct
CROSS_ROW_FIELDS = (
    "width",
    "height",
    "qty",
    "unit_qty",
    "unit_price",
    "total_qty",
    "line_total",
    "weight_per_unit",
    "glass_thick",
    "glass_type",
    "calc_pattern",
    "scrap_pct",
)

CROSS_ROW = (
    {
        "table_field": "items",
        "id_field": "slug",
        "label_field": "line_name",
        "fields": json.dumps(list(CROSS_ROW_FIELDS), ensure_ascii=False),
        "include_index_form": 1,
        "enabled": 1,
    },
)

DESCRIPTION = (
    "Bộ biến cho BOM Set (engine B4): thông số hệ, biến người dùng của "
    "Variable Set gắn với bộ, common var, hằng số, binding và biến chéo dòng "
    "trong chính bảng items. CỐ Ý KHÔNG gợi ý cost_bucket (chỉ có sau B5), "
    "row_literal trần (B4 không có namespace đó — dùng dạng "
    "items.<slug>.<field>) và cost_template_line (chỉ có ở B6)."
)


def _build_profile_doc():
    """Dựng doc profile đầy đủ rule + cross-row (chưa insert)."""
    return frappe.get_doc({
        "doctype": PROFILE_DOCTYPE,
        "profile_code": PROFILE_CODE,
        "profile_name": PROFILE_NAME,
        "is_active": 1,
        "default_action": DEFAULT_ACTION,
        "description": DESCRIPTION,
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
            in RULES
        ],
        "cross_row": [
            {"doctype": "AL Variable Cross Row", **row}
            for row in CROSS_ROW
        ],
    })


def _ensure_profile():
    """Tạo profile nếu chưa có. Đã có ⇒ bỏ qua (giữ nguyên admin đã sửa).

    Trả True nếu lần này CÓ tạo mới.
    """
    if frappe.db.exists(PROFILE_DOCTYPE, PROFILE_CODE):
        print("  · Profile %s: đã có, bỏ qua (không ghi đè)" % PROFILE_CODE)
        return False

    doc = _build_profile_doc()
    doc.flags.ignore_permissions = True
    doc.insert()
    print("  · Profile %s: đã tạo" % PROFILE_CODE)
    return True


def _assign_profile():
    """Gán profile cho các `AL Bom Set` đang TRỐNG `variable_profile`.

    Trả số bản ghi đã gán trong lần chạy này.
    """
    if not frappe.db.has_column(ASSIGN_TO, "variable_profile"):
        # Field do doctype JSON thêm vào; môi trường chưa sync phần đó thì bỏ
        # qua bước gán thay vì nổ SQL. Profile vẫn đã được tạo ở trên.
        print("  · Gán %s → %s: bỏ qua (chưa có cột variable_profile)"
              % (ASSIGN_TO, PROFILE_CODE))
        return 0

    rows = frappe.get_all(ASSIGN_TO, fields=["name", "variable_profile"])
    assigned = 0
    for row in rows:
        if row.get("variable_profile"):
            continue
        # update_modified=False: đây là cấu hình kỹ thuật, không được làm
        # "modified" của chứng từ nghiệp vụ nhảy — tránh nhiễu so sánh/đồng bộ.
        frappe.db.set_value(ASSIGN_TO, row["name"], "variable_profile",
                            PROFILE_CODE, update_modified=False)
        assigned += 1

    print("  · Gán %s → %s: %d bản ghi (bỏ qua %d đã có profile)"
          % (ASSIGN_TO, PROFILE_CODE, assigned, len(rows) - assigned))
    return assigned


def execute():
    if not frappe.db.exists("DocType", PROFILE_DOCTYPE):
        # Patch khai ở [post_model_sync] nên nhánh này chỉ xảy ra khi cấu hình
        # patches.txt sai. Báo LỚN thay vì bỏ qua im lặng (bỏ qua = patch được
        # đánh dấu đã chạy mà không seed gì, không ai biết).
        frappe.throw(
            "v28_14.seed_bom_profile: chưa có doctype '%s'. Patch này phải "
            "chạy ở [post_model_sync] sau khi sync doctype — kiểm tra lại "
            "alumglass/patches.txt." % PROFILE_DOCTYPE
        )

    print("v28_14 — seed profile %s" % PROFILE_CODE)
    created = _ensure_profile()
    # ⛔ Luôn chạy bước gán, kể cả khi profile đã tồn tại: site có thể đã có
    # profile (admin tạo tay) nhưng bản ghi Bom Set vẫn còn trống.
    assigned = _assign_profile()

    print("  · Tổng: profile tạo mới=%d, bản ghi gán=%d" % (created, assigned))

    # Patch convention của repo: ghi sổ rồi commit ngay (patch runner không
    # tự commit với mọi đường chạy).
    frappe.db.commit()
    print("v28_14 — xong profile %s" % PROFILE_CODE)
