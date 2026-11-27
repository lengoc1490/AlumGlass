"""B4 — đồng bộ `Formula Variable Binding` (FVB) từ master data của alumglass.

Vì sao có module này: trước đây việc seed FVB chỉ nằm trong một patch chạy lúc
migrate. Thêm 1 hằng số / 1 biến hệ mới ⇒ phải đợi kỳ migrate sau mới resolve
được qua Formula Builder. Nay cùng logic đó gọi được từ API (chạy tay, idempotent)
⇒ "khai biến mới là dùng được", ⛔ cần DEV, ⛔ cần migrate.

MỘT BẢN: patch migrate và API đều gọi `sync()` ở đây — không có bản chép thứ 2.

Phạm vi (giữ đúng như patch D3):
  1. Hằng số toàn cục — `Formula Global Variable` (is_active, value_source =
     CONSTANT, kiểu số) → FVB `source_type="constant"`, `is_global=1`.
  2. Biến hệ — `AL Variable Library` (is_system=1) có `source_doctype` +
     `source_field` **thuộc 2 nguồn có đường link trên AL Bom Set** → FVB
     `source_type="linked_doctype_field"`, `applies_to_doctype="AL Bom Set"`.

Biến do app tự resolve (biến người dùng theo bộ, literal theo dòng, cost
bucket…) ⛔ đưa vào FVB: Formula Builder không có bộ đọc tương ứng, ghi vào chỉ
tạo binding chết.

R2: chỉ ĐỌC/ghi DocType của FB qua document API thường — ⛔ sửa mã nguồn FB.
"""

import frappe

# Nguồn resolve hợp lệ cho system var ở scope AL Bom Set.
LINK_BY_SOURCE_DOCTYPE = {
    "AL Profile System": "profile_system",
    "AL Product Type": "product_type",
}

# var_type (AL Variable Library) → data_type (Formula Variable Binding)
DTYPE_MAP = {
    "Float": "Float",
    "Int": "Int",
    "Currency": "Currency",
    "Check": "Check",
    "Data": "Data",
    "Select": "Data",
    "Link": "Data",
}

NUMERIC_DTYPES = ("Float", "Int", "Currency", "Percent")

FVB_DOCTYPE = "Formula Variable Binding"


def _binding_exists(variable_name, applies_to_doctype, is_global):
    return frappe.db.exists(FVB_DOCTYPE, {
        "variable_name": variable_name,
        "applies_to_doctype": applies_to_doctype or "",
        "is_global": 1 if is_global else 0,
    })


def plan():
    """Danh sách FVB cần có — ⛔ đọc/ghi gì ngoài master data.

    Trả list[dict] đúng các khoá dùng để insert. Dùng cho `dry_run` và cho
    người vận hành xem trước.
    """
    planned = []

    # ── 1. Hằng số toàn cục ──────────────────────────────────────────
    for gv in frappe.get_all(
        "Formula Global Variable",
        filters={"is_active": 1, "value_source": "CONSTANT"},
        fields=["var_name", "label", "var_type", "constant_value"],
    ) or []:
        var_name = gv.get("var_name")
        if not var_name:
            continue
        dtype = gv.get("var_type") or "Float"
        if dtype not in NUMERIC_DTYPES:
            continue
        cval = gv.get("constant_value")
        if cval is None or str(cval).strip() == "":
            continue
        planned.append({
            "variable_name": var_name,
            "variable_label": gv.get("label") or var_name,
            "source_type": "constant",
            "source_config": {"value": cval},
            "applies_to_doctype": "",
            "data_type": dtype,
            "default_value": cval,
            "is_global": 1,
        })

    # ── 2. Biến hệ có nguồn resolve được ─────────────────────────────
    for sv in frappe.get_all(
        "AL Variable Library",
        filters={"is_system": 1},
        fields=["var_name", "var_label", "var_type", "source_doctype",
                "source_field", "default_value"],
    ) or []:
        var_name = sv.get("var_name")
        source_doctype = sv.get("source_doctype") or ""
        source_field = sv.get("source_field") or ""
        if not var_name or not source_field:
            continue
        link_field = LINK_BY_SOURCE_DOCTYPE.get(source_doctype)
        if not link_field:
            continue
        planned.append({
            "variable_name": var_name,
            "variable_label": sv.get("var_label") or var_name,
            "source_type": "linked_doctype_field",
            "source_config": {
                "link_field": link_field,
                "target_doctype": source_doctype,
                "target_field": source_field,
            },
            "applies_to_doctype": "AL Bom Set",
            "data_type": DTYPE_MAP.get(sv.get("var_type") or "Float", "Float"),
            "default_value": sv.get("default_value"),
            "is_global": 0,
        })

    return planned


def sync(dry_run=True):
    """Tạo các FVB còn thiếu. Idempotent.

    Args:
        dry_run: True ⇒ chỉ trả kế hoạch (⛔ ghi).

    Returns:
        {ok, dry_run, planned, created: [tên], skipped: [tên]}
    """
    planned = plan()
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "planned": planned,
            "created": [],
            "skipped": [],
        }

    created, skipped = [], []
    for item in planned:
        if _binding_exists(item["variable_name"],
                           item["applies_to_doctype"], item["is_global"]):
            skipped.append(item["variable_name"])
            continue
        try:
            frappe.get_doc({
                "doctype": FVB_DOCTYPE,
                "variable_name": item["variable_name"],
                "variable_label": item["variable_label"],
                "source_type": item["source_type"],
                "source_config": frappe.as_json(item["source_config"]),
                "resolve_priority": 100,
                "batch_group": "",
                "applies_to_doctype": item["applies_to_doctype"] or "",
                "applies_to_field": "",
                "data_type": item["data_type"],
                "default_value": item["default_value"]
                if item["default_value"] is not None else "",
                "is_global": item["is_global"],
                "is_active": 1,
            }).insert(ignore_permissions=True, ignore_mandatory=True)
            created.append(item["variable_name"])
        except Exception:
            # 1 binding lỗi ⛔ được chặn các binding khác.
            frappe.log_error(
                frappe.get_traceback(),
                "AlumGlass B4: đồng bộ FVB thất bại %s (%s)"
                % (item["variable_name"], item["applies_to_doctype"]),
            )
            skipped.append(item["variable_name"])

    if created:
        frappe.db.commit()

    return {
        "ok": True,
        "dry_run": False,
        "planned": planned,
        "created": created,
        "skipped": skipped,
    }
