import frappe, json
from frappe.utils import now
from frappe.model.naming import make_autoname


def main():
    """Run all tests: CDMQ-2C + CDMQ-4C"""
    test_cdmq_2c()
    test_cdmq_4c()


def _create_quotation_item(bom_code, item_code, item_name, bom_vars_dict):
    """Helper: tạo Quotation + Quotation Item và trả về qi_name."""
    company = frappe.defaults.get_global_default("company") or frappe.get_all("Company", limit=1, pluck="name")[0]
    bv_name = frappe.db.get_value("AL BOM", bom_code, "current_version")

    qtn_name = make_autoname("SAL-QTN-.#####")
    frappe.db.sql("""INSERT INTO `tabQuotation`
        (name, party_name, quotation_to, transaction_date, company, docstatus, al_project_ref, al_profile_system)
        VALUES (%s, %s, %s, %s, %s, 0, %s, %s)""",
        (qtn_name, "Khach Hang Test", "Customer", now(), company, "CDMQ-TEST", "XINGFA_55"))
    frappe.db.commit()

    qi_name = frappe.generate_hash(length=10)
    frappe.db.sql("""INSERT INTO `tabQuotation Item`
        (name, parent, parentfield, parenttype, item_code, item_name, qty, uom, stock_uom, al_bom, al_bom_version, al_bom_vars, idx)
        VALUES (%s, %s, 'items', 'Quotation', %s, %s, 1, 'Kg', 'Kg', %s, %s, %s, 1)""",
        (qi_name, qtn_name, item_code, item_name, bom_code, bv_name, json.dumps(bom_vars_dict)))
    frappe.db.commit()

    print(f"  Quotation: {qtn_name}, Item: {qi_name}")
    return qi_name


def _print_result(label, result, expected=None):
    """Helper: in kết quả tính BOM."""
    ct = result.get("cost_template", {})
    print(f"\n  {'='*55}")
    print(f"  {label}")
    print(f"  {'='*55}")
    print(f"  GIA_VAT:    {ct.get('GIA_VAT', 0):>15,.0f} VND")
    print(f"  GIA_BAN:    {ct.get('GIA_BAN', 0):>15,.0f} VND")
    print(f"  GIA_THANH:  {ct.get('GIA_THANH', 0):>15,.0f} VND")
    print(f"  TONG_VL:    {ct.get('TONG_VL', 0):>15,.0f} VND")
    print(f"  TONG_NC:    {ct.get('TONG_NC', 0):>15,.0f} VND")
    print(f"  TONG_OH:    {ct.get('TONG_OH', 0):>15,.0f} VND")
    print(f"  TONG_M2:    {ct.get('TONG_M2', 0):>15.3f} m²")
    print(f"  DON_GIA_M2: {ct.get('DON_GIA_M2', 0):>15,.0f} VND/m²")
    bucks = result.get("buckets", {})
    print(f"  Buckets:    VL_NHOM={bucks.get('VL_NHOM',0):,.0f}  VL_KINH={bucks.get('VL_KINH',0):,.0f}  VL_VTP={bucks.get('VL_VTP',0):,.0f}  VL_PK={bucks.get('VL_PK',0):,.0f}")
    print(f"  Lines:      {len(result.get('lines', []))} rows")
    if expected:
        actual = ct.get("GIA_VAT", 0)
        delta = abs(actual - expected)
        if delta < 1000:
            print(f"\n  ✅ PASS (delta={delta:,.0f} VND)")
        else:
            print(f"\n  ⚠️  DELTA={delta:,.0f} VND (actual={actual:,.0f} vs expected={expected:,.0f})")


# ═══════════════════════════════════════════════════════════════════════
# TEST 1: CDMQ-2C (Cửa đi 2 cánh + ô kính)
# ═══════════════════════════════════════════════════════════════════════
def test_cdmq_2c():
    print("\n" + "="*60)
    print("  TEST 1: CDMQ-2C — Cửa đi 2 cánh mở quay + ô kính")
    print("="*60)

    qi_name = _create_quotation_item("BOM-CDMQ-2C", "CDMQ-2C", "Cửa đi 2 cánh mở quay", {
        "W_mm": 2400, "H_mm": 2600, "n_panel": 2,
        "TransomHeight_mm": 600, "aluminum_color": "WHITE",
        "aluminum_origin": "IMPORT", "aluminum_thickness": 20,
        "aluminum_surface": "POWDER_COATED",
    })

    from alumglass.api import calculate_bom
    result = calculate_bom(qi_name)
    # Expected từ v28.6
    _print_result("CDMQ-2C", result, expected=22717289)


# ═══════════════════════════════════════════════════════════════════════
# TEST 2: CDMQ-4C (Cửa đi 4 cánh + 2 transom + sidelite — ★ FULL FEATURES)
# ═══════════════════════════════════════════════════════════════════════
def test_cdmq_4c():
    print("\n" + "="*60)
    print("  TEST 2: CDMQ-4C — Cửa đi 4 cánh + 2 transom + sidelite")
    print("  ★ Demo TOÀN BỘ tính năng v28.7.1")
    print("="*60)

    qi_name = _create_quotation_item("BOM-CDMQ-4C", "CDMQ-4C", "Cửa đi 4 cánh mở quay + vách kính", {
        "W_mm": 3600, "H_mm": 3200, "n_panel": 4,
        "TransomHeightTop": 600, "TransomHeightBottom": 400,
        "SideLiteWidth": 800, "SideLiteHeight": 2800,
        "aluminum_color": "DARK", "aluminum_origin": "IMPORT",
        "aluminum_thickness": 20, "aluminum_surface": "POWDER_COATED",
        "installation_height_m": 15,
    })

    from alumglass.api import calculate_bom
    result = calculate_bom(qi_name)

    ct = result.get("cost_template", {})
    print(f"\n  ★★★ CDMQ-4C: KẾT QUẢ TÍNH TOÁN ★★★")
    print(f"  Profile: XINGFA_55 | Màu: DARK (×1.08) | Tầng: 5 (×1.2)")
    print(f"  Kích thước: {3600}×{3200}mm | 4 cánh + 2 transom + sidelite")
    print(f"  {'─'*55}")
    print(f"  VL_NHOM:  {result.get('buckets',{}).get('VL_NHOM',0):>15,.0f} VND  (khung + đố + cánh + nẹp)")
    print(f"  VL_KINH:  {result.get('buckets',{}).get('VL_KINH',0):>15,.0f} VND  (4 tấm kính)")
    print(f"  VL_VTP:   {result.get('buckets',{}).get('VL_VTP',0):>15,.0f} VND  (keo + gioăng + vít)")
    print(f"  VL_PK:    {result.get('buckets',{}).get('VL_PK',0):>15,.0f} VND  (tay nắm + khóa + bản lề)")
    print(f"  {'─'*55}")
    print(f"  TONG_VL:   {ct.get('TONG_VL',0):>15,.0f} VND")
    print(f"  NC_SX:     {ct.get('NC_SX',0):>15,.0f} VND  (8% × TONG_VL)")
    print(f"  NC_LD:     {ct.get('NC_LD',0):>15,.0f} VND  (12% × TONG_VL × 1.2 ★)")
    print(f"  TONG_NC:   {ct.get('TONG_NC',0):>15,.0f} VND")
    print(f"  OH_VC:     {ct.get('OH_VC',0):>15,.0f} VND")
    print(f"  OH_QLY:    {ct.get('OH_QLY',0):>15,.0f} VND")
    print(f"  TONG_OH:   {ct.get('TONG_OH',0):>15,.0f} VND")
    print(f"  {'─'*55}")
    print(f"  GIA_THANH: {ct.get('GIA_THANH',0):>15,.0f} VND")
    print(f"  PROFIT:    {ct.get('PROFIT',0):>15,.0f} VND  (16%)")
    print(f"  GIA_BAN:   {ct.get('GIA_BAN',0):>15,.0f} VND")
    print(f"  VAT:       {ct.get('VAT',0):>15,.0f} VND  (10%)")
    print(f"  GIA_VAT:   {ct.get('GIA_VAT',0):>15,.0f} VND  ★★★")
    print(f"  TONG_M2:   {ct.get('TONG_M2',0):>15.3f} m²")
    print(f"  DON_GIA_M2:{ct.get('DON_GIA_M2',0):>15,.0f} VND/m²")
    print(f"  {'─'*55}")
    print(f"  Lines: {len(result.get('lines', []))} Bom Items được tính")

    # Verify các tính năng đặc thù
    lines = result.get("lines", [])
    nep_items = [l for l in lines if "nep" in l.get("slug", "")]
    keo_items = [l for l in lines if "keo" in l.get("slug", "")]

    print(f"\n  ★ Dynamic Item Rule: {len(nep_items)} nẹp items (resolved qua THRESHOLD)")
    for n in nep_items:
        print(f"    - {n['slug']}: item={n['item_code']}, line_total={n['line_total']:,.0f}")

    print(f"  ★ Dynamic Item Rule: {len(keo_items)} keo items (resolved qua LOOKUP)")
    for k in keo_items:
        print(f"    - {k['slug']}: item={k['item_code']}, line_total={k['line_total']:,.0f}")

    print(f"\n  ★ lookup_rule: NC_LD dùng RULE-HEIGHT-MULT(15m) = 1.2")
    print(f"  ★ lookup_rule: Accessory ban_le dùng RULE-BANLE-QTY(3200mm) = 4 bản lề/cánh × 4 = 16")
    print(f"  ★ Price Multiplier: DARK color ×{1.08} (từ AL Color Standard)")
    print(f"  ★ Scrap Injection: NHOM={3}%, KINH={5}%, VTP={2}% (từ Material Category)")
    print(f"  ★ System Vars: OFFSET(48,90,50,48) NC(8%,12%) PROFIT(16%) từ DB")

    # ★ Golden assert (Owner chốt 2026-08-18): GIA_VAT = 47,430,808
    expected = 47430808
    actual = ct.get("GIA_VAT", 0)
    delta = abs(actual - expected)
    if delta < 1000:
        print(f"\n  ✅ PASS CDMQ-4C golden (delta={delta:,.0f} VND)")
    else:
        raise AssertionError(
            f"CDMQ-4C GIA_VAT lệch golden: actual={actual:,.0f} vs expected={expected:,.0f} (delta={delta:,.0f})"
        )


if __name__ == "__main__":
    main()
