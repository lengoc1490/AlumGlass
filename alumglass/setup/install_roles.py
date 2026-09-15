"""Cài đặt Roles và Permissions cho AlumGlass ERP.

Được gọi từ after_install hook. Tạo 4 role nghiệp vụ + gán quyền
DocPerm cho từng nhóm doctype theo module.

Thiết kế theo least-privilege: nhân viên bán hàng KHÔNG cần System Manager.

QUAN TRỌNG: Tên module phải khớp CHÍNH XÁC với trường `module` trong
doctype JSON (case-sensitive). Xác minh bằng:
  SELECT DISTINCT module FROM tabDocType WHERE name LIKE 'AL %';
"""
import frappe


# ── Role definitions ──────────────────────────────────────────────────
ROLES = [
    {"role_name": "AL Sales User", "desk_access": 1},
    {"role_name": "AL BOM Manager", "desk_access": 1},
    {"role_name": "AL Site Engineer", "desk_access": 1},
    {"role_name": "AL Project Accountant", "desk_access": 1},
    # 🆕 v28.8: AL Technical Admin — độc quyền sửa calc_fn trên AL Quantity Calc Method.
    {"role_name": "AL Technical Admin", "desk_access": 1},
]


# ── Permission matrix: module → roles → (read, write, create, delete, ...) ──
# docstatus: 0 = tất cả bản ghi được phép (không submit/approve)
# Nếu doctype có workflow, quyền write/create/delete chỉ áp cho state trước Published
#
# TÊN MODULE PHẢI KHỚP CHÍNH XÁC VỚI doctype JSON (case-sensitive):
#   AL Master Data, AL Bom Engine, AL Formula Rules, AL Buying,
#   AL Stock, AL Manufacturing, AL Construction, AL Account,
#   AL Quality, AL AI Intelligence
MODULE_PERMISSIONS = {
    # ── AL Master Data: BOM Manager quản trị, Sales User read-only ──
    "AL Master Data": {
        "AL Sales User": {"read": 1, "export": 1},
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "import": 1,
        },
    },
    # ── AL Bom Engine: BOM Manager full quyền, Sales/Engineer read ──
    "AL Bom Engine": {
        "AL Sales User": {"read": 1, "export": 1},
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "import": 1,
        },
        "AL Site Engineer": {"read": 1, "export": 1},
    },
    # ── AL Formula Rules: chỉ BOM Manager ──
    "AL Formula Rules": {
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "import": 1,
        },
    },
    # ── AL Buying: BOM Manager + Project Accountant ──
    "AL Buying": {
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL Project Accountant": {
            "read": 1, "write": 1, "create": 1, "report": 1, "export": 1,
        },
    },
    # ── AL Stock: BOM Manager + Site Engineer read/write ──
    "AL Stock": {
        "AL BOM Manager": {"read": 1, "write": 1, "create": 1, "export": 1},
        "AL Site Engineer": {"read": 1, "write": 1, "create": 1, "export": 1},
    },
    # ── AL Manufacturing: BOM Manager + Site Engineer ──
    "AL Manufacturing": {
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL Site Engineer": {"read": 1, "export": 1, "report": 1},
    },
    # ── AL Construction: Site Engineer full, Accountant read ──
    "AL Construction": {
        "AL Site Engineer": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL Project Accountant": {"read": 1, "report": 1, "export": 1},
        "AL BOM Manager": {"read": 1, "export": 1},
    },
    # ── AL Account: Project Accountant full, BOM Manager read ──
    "AL Account": {
        "AL Project Accountant": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL BOM Manager": {"read": 1, "export": 1},
    },
    # ── AL Quality: BOM Manager + Site Engineer ──
    "AL Quality": {
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL Site Engineer": {"read": 1, "write": 1, "create": 1, "export": 1},
    },
    # ── AL AI Intelligence: read-only cho tất cả nghiệp vụ ──
    "AL AI Intelligence": {
        "AL Sales User": {"read": 1},
        "AL BOM Manager": {"read": 1},
        "AL Site Engineer": {"read": 1},
        "AL Project Accountant": {"read": 1},
    },
}

# ── Override đặc biệt per-doctype (v28.8) ────────────────────────────────
# AL Quantity Calc Method: chỉ AL Technical Admin mới write/create/delete.
# AL BOM Manager bị HẠ xuống read-only (trước đây full quyền qua module loop).
# Các doctype khác trong module "AL Formula Rules" (AL Calculation Rule,
# AL Dynamic Item Rule, ...) giữ nguyên quyền BOM Manager write.
CALC_METHOD_PERMISSIONS = {
    "AL BOM Manager": {"read": 1, "export": 1},
    "AL Technical Admin": {
        "read": 1, "write": 1, "create": 1, "delete": 1,
        "report": 1, "export": 1, "import": 1,
    },
}

# ── Core ERPNext doctypes cho Sales User ─────────────────────────────
# AL không có module "AL Selling" riêng — bán hàng nằm trong ERPNext
# core doctypes (Quotation, Quotation Item, Sales Order) với custom
# fields do alumglass thêm vào.
# Các doctype này thuộc module "Selling" của ERPNext.
CORE_DOCTYPE_PERMISSIONS = {
    "Quotation": {
        "AL Sales User": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "print": 1, "email": 1,
        },
        "AL BOM Manager": {"read": 1, "export": 1},
    },
    "Quotation Item": {
        "AL Sales User": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL BOM Manager": {"read": 1, "export": 1},
    },
    "Sales Order": {
        "AL Sales User": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "print": 1, "email": 1,
        },
        "AL BOM Manager": {"read": 1, "export": 1},
    },
    "Sales Order Item": {
        "AL Sales User": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1,
        },
        "AL BOM Manager": {"read": 1, "export": 1},
    },
}


# ── Override đặc biệt per-doctype: AL Change Order (governance) ─────────
# customer_approval/internal_approval đã đặt permlevel=1 trong JSON doctype
# (xem al_change_order.json) — 2 checkbox này quyết định điều kiện chuyển
# workflow_state="Approved" (giá trị hợp đồng thay đổi qua đây), nên KHÔNG
# thể để bất kỳ ai có quyền write cơ bản (permlevel 0, do module loop AL
# Construction cấp cho AL Site Engineer) tự tick — tách biệt nhiệm vụ
# (segregation of duties): người TẠO change order khác người XÁC NHẬN đã
# được duyệt thật. AL Site Engineer CHỈ có permlevel 0 (không có ở đây) →
# thấy 2 field này read-only trên form.
CHANGE_ORDER_APPROVAL_PERMISSIONS = {
    "System Manager": {"permlevel": 1, "read": 1, "write": 1},
    "AL Project Accountant": {"permlevel": 1, "read": 1, "write": 1},
    "AL Technical Admin": {"permlevel": 1, "read": 1, "write": 1},
}


def _upsert_docperm(dt_name, role_name, perm_values):
    """Tạo hoặc cập nhật 1 Custom DocPerm record.

    FIX: lọc theo CẢ (parent, role, permlevel) — trước đây chỉ lọc
    (parent, role), nên 1 role có sẵn DocPerm permlevel=0 (từ module loop)
    sẽ bị GHI ĐÈ thành permlevel=1 nếu sau đó gọi hàm này với permlevel=1
    cho field-level permission (mất luôn quyền truy cập cơ bản). Mỗi
    (role, permlevel) là 1 record riêng biệt trong Frappe.
    """
    if not frappe.db.exists("Role", role_name):
        return

    permlevel = perm_values.get("permlevel", 0)
    existing = frappe.db.exists(
        "Custom DocPerm",
        {"parent": dt_name, "role": role_name, "permlevel": permlevel})
    if existing:
        frappe.db.set_value("Custom DocPerm", existing, perm_values)
    else:
        docperm = frappe.new_doc("Custom DocPerm")
        docperm.parent = dt_name
        docperm.role = role_name
        docperm.permlevel = permlevel
        docperm.update(perm_values)
        docperm.insert(ignore_permissions=True)


def _set_full_docperm(dt_name, role_name, perm_values):
    """Cập nhật TOÀN BỘ perm record — quyền không liệt kê bị đặt 0.

    Dùng cho override per-doctype: đảm bảo quyền cũ (vd BOM Manager full từ
    module loop) bị HẠ xuống đúng trạng thái mới, không sót field.
    """
    full = {
        "read": 0, "write": 0, "create": 0, "delete": 0,
        "submit": 0, "cancel": 0, "amend": 0, "report": 0,
        "export": 0, "import": 0, "print": 0, "email": 0, "share": 0,
    }
    full.update(perm_values)
    _upsert_docperm(dt_name, role_name, full)


def install_roles_and_permissions():
    """Cài đặt roles + DocPerm cho tất cả AL doctypes + core ERPNext.

    Gọi từ after_install hook hoặc seed_demo_data.
    """
    # ── 1. Create roles ────────────────────────────────────────────
    for role_def in ROLES:
        if not frappe.db.exists("Role", role_def["role_name"]):
            frappe.get_doc({"doctype": "Role", **role_def}).insert(
                ignore_permissions=True)
            print(f"  Created Role: {role_def['role_name']}")
        else:
            print(f"  Role exists: {role_def['role_name']}")

    frappe.db.commit()

    # ── 2. Get all AL doctypes grouped by module ───────────────────
    al_modules = list(MODULE_PERMISSIONS.keys())
    all_al_doctypes = frappe.get_all("DocType",
        filters={"module": ("in", al_modules), "custom": 0},
        fields=["name", "module"])

    # ── 3. Add DocPerm for each AL doctype → role ─────────────────
    al_count = 0
    for dt_info in all_al_doctypes:
        dt_name = dt_info["name"]
        module = dt_info["module"]
        module_perms = MODULE_PERMISSIONS.get(module, {})

        for role_name, perm_values in module_perms.items():
            _upsert_docperm(dt_name, role_name, perm_values)
            al_count += 1

    frappe.db.commit()
    print(f"  ✅ AL doctype permissions: {al_count} DocPerm records "
          f"across {len(all_al_doctypes)} doctypes")

    # ── 3.5 Override per-doctype: AL Quantity Calc Method ─────────────
    # Hạ AL BOM Manager xuống read-only + cấp AL Technical Admin full.
    # Phải chạy SAU module loop (3) để ghi đè DocPerm module-level cũ.
    calc_count = 0
    for role_name, perm_values in CALC_METHOD_PERMISSIONS.items():
        _set_full_docperm("AL Quantity Calc Method", role_name, perm_values)
        calc_count += 1
    frappe.db.commit()
    print(f"  ✅ AL Quantity Calc Method override: {calc_count} DocPerm records "
          f"(BOM Manager read-only, AL Technical Admin full)")

    # ── 3.6 Override per-doctype: AL Change Order (permlevel 1 approval) ──
    # _upsert_docperm (không phải _set_full_docperm) — đây là (role,
    # permlevel=1) record RIÊNG BIỆT, cộng thêm bên cạnh permlevel=0 sẵn có
    # của module loop (3), không phải ghi đè/hạ quyền base level 0.
    change_order_count = 0
    for role_name, perm_values in CHANGE_ORDER_APPROVAL_PERMISSIONS.items():
        _upsert_docperm("AL Change Order", role_name, perm_values)
        change_order_count += 1
    frappe.db.commit()
    print(f"  ✅ AL Change Order approval override: {change_order_count} "
          f"DocPerm records permlevel=1 (customer_approval/internal_approval)")

    # ── 4. Add DocPerm for core ERPNext doctypes ───────────────────
    core_count = 0
    for dt_name, role_perms in CORE_DOCTYPE_PERMISSIONS.items():
        # Kiểm tra doctype có tồn tại (ERPNext core)
        if not frappe.db.exists("DocType", dt_name):
            print(f"  ⚠️  Skip: DocType '{dt_name}' không tồn tại")
            continue
        for role_name, perm_values in role_perms.items():
            _upsert_docperm(dt_name, role_name, perm_values)
            core_count += 1

    frappe.db.commit()
    print(f"  ✅ Core ERPNext doctype permissions: {core_count} DocPerm records")

    # ── 5. Self-check: báo cáo module nào trong config không có doctype nào ──
    configured = {m for m in al_modules}
    actual = {dt["module"] for dt in all_al_doctypes}
    missing = configured - actual
    if missing:
        print(f"  ⚠️  WARNING: Module(s) trong config nhưng không có doctype "
              f"nào: {missing} — kiểm tra lại tên module trong MODULE_PERMISSIONS")
    extra = actual - configured
    if extra:
        print(f"  ⚠️  WARNING: Module(s) có doctype nhưng chưa được config "
              f"quyền: {extra} — bổ sung vào MODULE_PERMISSIONS")


def get_module_for_doctype(doctype_name):
    """Map 1 doctype về module để cấp quyền thủ công nếu cần."""
    return frappe.db.get_value("DocType", doctype_name, "module")
