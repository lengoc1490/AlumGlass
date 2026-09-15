import frappe


def execute():
    """Backfill represents_color=1 cho dimension MAU_SAC hiện có."""
    if frappe.db.exists("AL Pricing Dimension", "MAU_SAC"):
        frappe.db.set_value("AL Pricing Dimension", "MAU_SAC", "represents_color", 1)
