import frappe


def get_quotation_custom_fields():
    """Return custom field definitions for Quotation doctype."""
    return [
        {
            "fieldname": "al_product_type",
            "label": "AL Product Type",
            "fieldtype": "Link",
            "options": "AL Product Type",
            "insert_after": "quotation_to",
            "module": "AL Selling",
        },
        {
            "fieldname": "al_bom",
            "label": "AL BOM",
            "fieldtype": "Link",
            "options": "AL BOM",
            "insert_after": "al_product_type",
            "module": "AL Selling",
        },
        {
            "fieldname": "al_bom_version",
            "label": "AL BOM Version",
            "fieldtype": "Link",
            "options": "AL BOM Version",
            "insert_after": "al_bom",
            "module": "AL Selling",
        },
        # V6 P6 (E): bỏ al_profile_system trên Quotation — profile system giờ là
        # override item-level trong al_bom_vars (_profile_system). KHÔNG recreate.
        {
            "fieldname": "al_color",
            "label": "AL Color",
            "fieldtype": "Link",
            "options": "AL Color Standard",
            "insert_after": "al_bom_version",
            "module": "AL Selling",
        },
        {
            "fieldname": "al_aluminum_origin",
            "label": "Aluminum Origin",
            "fieldtype": "Select",
            "options": "IMPORT\nDOMESTIC",
            "insert_after": "al_color",
            "module": "AL Selling",
        },
        {
            "fieldname": "al_aluminum_thickness",
            "label": "Aluminum Thickness",
            "fieldtype": "Float",
            "insert_after": "al_aluminum_origin",
            "module": "AL Selling",
        },
        {
            "fieldname": "al_aluminum_surface",
            "label": "Aluminum Surface",
            "fieldtype": "Select",
            "options": "POWDER_COATED\nANODIZED\nWOOD_GRAIN",
            "insert_after": "al_aluminum_thickness",
            "module": "AL Selling",
        },
        {
            "fieldname": "al_loss_reason",
            "label": "Loss Reason",
            "fieldtype": "Select",
            "options": "GIA_CAO\nCHAM_TIEN_DO\nDOI_THU\nKHAC",
            "insert_after": "al_aluminum_surface",
            "module": "AL Selling",
        },
    ]


def install_custom_fields():
    """Install all AL Selling custom fields on ERPNext core doctypes."""
    for field_def in get_quotation_custom_fields():
        if not frappe.db.exists("Custom Field", {
            "dt": "Quotation",
            "fieldname": field_def["fieldname"]
        }):
            cf = frappe.new_doc("Custom Field")
            cf.dt = "Quotation"
            cf.update(field_def)
            cf.insert(ignore_permissions=True)
