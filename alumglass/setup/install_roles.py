"""Cài đặt Roles và Permissions cho AlumGlass ERP.

Được gọi từ after_install hook. Tạo 4 role nghiệp vụ + gán quyền
DocPerm cho từng nhóm doctype theo module.

Thiết kế theo least-privilege: nhân viên bán hàng KHÔNG cần System Manager.
"""
import frappe


# ── Role definitions ──────────────────────────────────────────────────
ROLES = [
    {"role_name": "AL Sales User", "desk_access": 1},
    {"role_name": "AL BOM Manager", "desk_access": 1},
    {"role_name": "AL Site Engineer", "desk_access": 1},
    {"role_name": "AL Project Accountant", "desk_access": 1},
]

# ── Permission matrix: module → roles → (read, write, create, delete) ──
# docstatus: 0 = tất cả bản ghi được phép (không submit/approve)
# Nếu doctype có workflow, quyền write/create/delete chỉ áp cho state trước Published
MODULE_PERMISSIONS = {
    # ── AL Selling: Sales User dùng Quotation ──
    "AL Selling": {
        "AL Sales User": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "print": 1, "email": 1,
        },
        "AL BOM Manager": {"read": 1, "export": 1},
    },
    # ── AL Master Data: BOM Manager quản trị, Sales User read-only ──
    "AL Master Data": {
        "AL Sales User": {"read": 1, "export": 1},
        "AL BOM Manager": {
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "import": 1,
        },
    },
    # ── AL BOM Engine: BOM Manager full quyền, Sales/Engineer read ──
    "AL BOM Engine": {
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
    # ── AL AI: read-only cho tất cả nghiệp vụ ──
    "AL AI Intelligence": {
        "AL Sales User": {"read": 1},
        "AL BOM Manager": {"read": 1},
        "AL Site Engineer": {"read": 1},
        "AL Project Accountant": {"read": 1},
    },
    # ── Core ERPNext modules cho Sales User ──
    # Quotation/Sales Order: Sales User full quyền
    # (custom fields đã thêm vào các doctype này)
}


def install_roles_and_permissions():
    """Cài đặt roles + DocPerm cho tất cả AL doctypes.

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
    al_modules = [m for m in MODULE_PERMISSIONS]
    all_al_doctypes = frappe.get_all("DocType",
        filters={"module": ("in", al_modules), "custom": 0},
        fields=["name", "module"])

    # ── 3. Add DocPerm for each doctype → role ────────────────────
    for dt_info in all_al_doctypes:
        dt_name = dt_info["name"]
        module = dt_info["module"]
        module_perms = MODULE_PERMISSIONS.get(module, {})

        for role_name, perm_values in module_perms.items():
            if not frappe.db.exists("Role", role_name):
                continue

            # Check if perm already exists for this doctype+role
            existing = frappe.db.exists(
                "Custom DocPerm",
                {"parent": dt_name, "role": role_name})
            if existing:
                # Update existing
                frappe.db.set_value("Custom DocPerm", existing, perm_values)
            else:
                # Create new
                docperm = frappe.new_doc("Custom DocPerm")
                docperm.parent = dt_name
                docperm.role = role_name
                docperm.permlevel = 0
                docperm.update(perm_values)
                docperm.insert(ignore_permissions=True)

    frappe.db.commit()
    print(f"  ✅ Permissions configured for {len(all_al_doctypes)} AL doctypes")


def get_module_for_doctype(doctype_name):
    """Map 1 doctype về module để cấp quyền thủ công nếu cần."""
    return frappe.db.get_value("DocType", doctype_name, "module")
