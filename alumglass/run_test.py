import frappe, json
from frappe.utils import now
from frappe.model.naming import make_autoname

def main():
    bv_name = frappe.db.get_value("AL BOM", "BOM-CDMQ-2C", "current_version")
    company = frappe.defaults.get_global_default("company") or frappe.get_all("Company", limit=1, pluck="name")[0]

    # Tạo Quotation
    qtn_name = make_autoname("SAL-QTN-.#####")
    frappe.db.sql("""INSERT INTO `tabQuotation` (name, party_name, quotation_to, transaction_date, company, docstatus, al_project_ref, al_profile_system) VALUES (%s, %s, %s, %s, %s, 0, %s, %s)""",
        (qtn_name, "Khach Hang Test", "Customer", now(), company, "CDMQ-TEST", "XINGFA_55"))
    frappe.db.commit()

    # Tạo Quotation Item với al_bom_vars JSON
    qi_name = frappe.generate_hash(length=10)
    bom_vars = json.dumps({
        "W_mm": 2400, "H_mm": 2600, "n_panel": 2,
        "TransomHeight_mm": 600, "aluminum_color": "WHITE",
        "aluminum_origin": "IMPORT", "aluminum_thickness": 20,
        "aluminum_surface": "POWDER_COATED",
    })
    frappe.db.sql("""INSERT INTO `tabQuotation Item` (name, parent, parentfield, parenttype, item_code, item_name, qty, uom, stock_uom, al_bom, al_bom_version, al_bom_vars, idx) VALUES (%s, %s, 'items', 'Quotation', %s, %s, 1, 'Kg', 'Kg', %s, %s, %s, 1)""",
        (qi_name, qtn_name, "CDMQ-2C", "Cửa đi 2 cánh mở quay", "BOM-CDMQ-2C", bv_name, bom_vars))
    frappe.db.commit()

    print(f"Quotation: {qtn_name}, Item: {qi_name}")

    # Gọi calculate_bom
    from alumglass.api import calculate_bom
    result = calculate_bom(qi_name)
    actual = result.get('gia_vat', 0)
    expected = 22717289

    print(f"\n=== KẾT QUẢ (Formula Builder Engine) ===")
    print(f"GIA_VAT: {actual:,.0f} VND")
    print(f"Expected: {expected:,} VND")
    print(f"GIA_BAN: {result.get('gia_ban'):,.0f}")
    print(f"TONG_VL: {result.get('tong_vl'):,.0f}")
    print(f"Buckets: {json.dumps(result.get('buckets', {}), indent=2)}")
    print(f"Lines: {len(result.get('lines', []))} rows")

    if abs(actual - expected) < 100:
        print(f"\n✅ CHÍNH XÁC! GIA_VAT = 22,717,289 VND (FB Engine)")
    else:
        print(f"\n⚠️ Sai lệch: {actual:,.0f} vs {expected:,} (delta={abs(actual-expected):,.0f})")
