"""
Migration v17.1 — Auto-create Formula Set from existing AL Cost Template lines.
P1: Each AL Cost Template Line.calc_formula → Formula Set Line.formula.
AL Cost Template gets a new formula_set field pointing to the created Formula Set.
"""
import frappe


def execute():
    """Create Formula Set records from existing AL Cost Templates."""
    templates = frappe.get_all(
        "AL Cost Template",
        fields=["name", "template_code", "template_name"],
    )

    created_count = 0
    for tpl in templates:
        # Skip if already has formula_set
        existing_fs = frappe.db.get_value(
            "AL Cost Template", tpl.name, "formula_set"
        )
        if existing_fs:
            print(f"[v17.1] Cost Template '{tpl.template_code}' already has Formula Set, skipping.")
            continue

        lines = frappe.get_all(
            "AL Cost Template Line",
            filters={"parent": tpl.name},
            fields=["line_code", "calc_formula", "sort_order"],
            order_by="sort_order asc",
        )

        if not lines:
            continue

        # Create Formula Set
        fs_code = f"FS-{tpl.template_code}"
        try:
            fs = frappe.get_doc({
                "doctype": "Formula Set",
                "set_code": fs_code,
                "label": f"Cost: {tpl.template_name or tpl.template_code}",
                "linked_doctype": "Quotation Item",
            })
            fs.insert(ignore_permissions=True)

            # Create Formula Set Lines
            for i, ln in enumerate(lines):
                if not ln.calc_formula:
                    continue
                fs_line = frappe.get_doc({
                    "doctype": "Formula Set Line",
                    "parent": fs.name,
                    "parentfield": "formulas",
                    "parenttype": "Formula Set",
                    "var_name": ln.line_code or f"line_{ln.sort_order}",
                    "formula": ln.calc_formula,
                    "idx": i + 1,
                })
                fs_line.insert(ignore_permissions=True)

            # Link Formula Set to Cost Template
            frappe.db.set_value(
                "AL Cost Template", tpl.name, "formula_set", fs.name
            )
            created_count += 1
            print(f"[v17.1] Created Formula Set '{fs_code}' for Cost Template '{tpl.template_code}'")
        except Exception as e:
            print(f"[v17.1] Error creating Formula Set for '{tpl.template_code}': {e}")

    frappe.db.commit()
    print(f"[v17.1] Migration complete. Created {created_count} Formula Sets.")
