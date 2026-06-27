"""Migration v17.0: Tạo Roles cho AlumGlass"""
import frappe

ROLES = [
    {"role_name": "AluGlass Admin", "desk_access": 1},
    {"role_name": "AluGlass Kỹ Thuật", "desk_access": 1},
    {"role_name": "AluGlass Sales", "desk_access": 1},
    {"role_name": "AluGlass Kế Toán", "desk_access": 1},
    {"role_name": "AluGlass Mua Hàng", "desk_access": 1},
    {"role_name": "AluGlass Director", "desk_access": 1},
]

def execute():
    for role_def in ROLES:
        if not frappe.db.exists("Role", role_def["role_name"]):
            frappe.new_doc("Role").update(role_def).insert(ignore_permissions=True)
            print(f"  Created role: {role_def['role_name']}")
    frappe.db.commit()
    print("Roles setup complete")
