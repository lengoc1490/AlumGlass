import frappe
from frappe.utils import now
from frappe.model.naming import make_autoname

def main():
    bv_name = frappe.db.get_value("AL BOM", "BOM-CDMQ-2C", "current_version")
    company = frappe.defaults.get_global_default("company") or frappe.get_all("Company", limit=1, pluck="name")[0]
    
    qtn_name = make_autoname("SAL-QTN-.#####")
    frappe.db.sql("""INSERT INTO `tabQuotation` (name, party_name, quotation_to, transaction_date, company, docstatus, al_product_type, al_bom, al_bom_version, al_profile_system) VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s)""",
        (qtn_name, "Khach Hang Test", "Customer", now(), company, "DOOR", "BOM-CDMQ-2C", bv_name, "XINGFA_55"))
    frappe.db.commit()
    
    qi_name = frappe.generate_hash(length=10)
    frappe.db.sql("""INSERT INTO `tabQuotation Item` (name, parent, parentfield, parenttype, item_code, item_name, qty, uom, stock_uom, al_bom, al_bom_version, al_W_mm, al_H_mm, al_transom_height_mm, al_n_panel, al_aluminum_color, al_aluminum_origin, al_aluminum_thickness, al_aluminum_surface, idx) VALUES (%s, %s, 'items', 'Quotation', %s, %s, 1, 'Kg', 'Kg', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
        (qi_name, qtn_name, "NHOM-XINGFA", "Nhôm Xingfa (đại diện)", "BOM-CDMQ-2C", bv_name, 2400, 2600, 600, 2, "WHITE", "IMPORT", 20, "POWDER_COATED"))
    frappe.db.commit()
    
    from alumglass.api import calculate_bom
    result = calculate_bom(qi_name)
    actual = result.get('gia_vat', 0)
    
    print(f"GIA_VAT: {actual:,.0f} VND (expected: 22,717,289)")
    expected = 22717289
    if abs(actual - expected) < 100:
        print("SUCCESS: GIA_VAT = 22,717,289 VND exactly!")
    else:
        print(f"DIFF: {actual:,.0f} vs {expected:,} (delta={abs(actual-expected):,.0f})")
        print(f"Buckets: {result.get('buckets', {})}")
