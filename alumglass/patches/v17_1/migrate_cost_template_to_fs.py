"""
P1 Migration: Tạo Formula Set từ AL Cost Template Lines hiện có
+ Thêm trường formula_set vào AL Cost Template DocType
"""
import frappe
import json


def execute():
    """Chạy migration P1."""
    # 1. Thêm custom field formula_set vào AL Cost Template (nếu chưa có)
    _add_formula_set_field()

    # 2. Tạo Formula Set từ AL Cost Template
    count = _migrate_cost_templates()

    frappe.db.commit()
    print(f"\nP1 Migration complete:")
    print(f"  - Formula Sets created from Cost Templates: {count}")


def _add_formula_set_field():
    """Thêm field formula_set vào AL Cost Template."""
    if frappe.db.exists("Custom Field", {"dt": "AL Cost Template", "fieldname": "formula_set"}):
        print("  Field 'formula_set' already exists on AL Cost Template")
        return

    try:
        cf = frappe.new_doc("Custom Field")
        cf.dt = "AL Cost Template"
        cf.fieldname = "formula_set"
        cf.label = "Formula Set"
        cf.fieldtype = "Link"
        cf.options = "Formula Set"
        cf.insert_after = "template_name"
        cf.description = (
            "Tham chiếu đến Formula Set của formula_builder. "
            "Nếu được set, các dòng calc_formula trong Cost Template sẽ "
            "được thay thế bởi Formula Set này khi tính toán."
        )
        cf.insert(ignore_permissions=True)
        print("  Added field 'formula_set' to AL Cost Template")
    except Exception as e:
        print(f"  FAILED to add formula_set field: {e}")


def _migrate_cost_templates():
    """Tạo Formula Set từ mỗi AL Cost Template."""
    templates = frappe.get_all("AL Cost Template", fields=["name", "template_name", "template_code"])
    count = 0

    for t in templates:
        # Lấy cost template lines
        lines = frappe.get_all(
            "AL Cost Template Line",
            filters={"parent": t.name},
            fields=["line_code", "calc_formula", "line_label"],
            order_by="sort_order asc",
        )
        if not lines:
            continue

        # Tạo Formula Set code
        fs_code = f"CT-{t.template_code}" if t.template_code else f"CT-{t.name}"

        # Check duplicate
        if frappe.db.exists("Formula Set", fs_code):
            print(f"  Formula Set '{fs_code}' already exists — linking to Cost Template {t.name}")
            frappe.db.set_value("AL Cost Template", t.name, "formula_set", fs_code)
            count += 1
            continue

        try:
            # Tạo Formula Set
            fs = frappe.new_doc("Formula Set")
            fs.set_code = fs_code
            fs.label = t.template_name or t.name
            fs.is_active = 1

            for ln in lines:
                if not ln.calc_formula:
                    continue
                fs.append("formulas", {
                    "var_name": ln.line_code or f"cost_{ln.idx}",
                    "formula": ln.calc_formula,
                    "description": ln.line_label or "",
                })

            fs.insert(ignore_permissions=True)
            print(f"  Created Formula Set: {fs_code} ({len(fs.formulas)} formulas)")

            # Link vào Cost Template
            frappe.db.set_value("AL Cost Template", t.name, "formula_set", fs_code)
            count += 1

        except Exception as e:
            print(f"  FAILED: {t.name} — {e}")

    return count
