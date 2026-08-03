"""Seed dữ liệu mẫu cho AlumGlass ERP.

Sản phẩm mẫu: Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)
Kết quả kỳ vọng: GIA_VAT = 22,717,289 VND với input chuẩn.
"""
import frappe
from frappe.utils import now


def seed_all():
    """Nhập toàn bộ dữ liệu mẫu - idempotent."""
    _seed_uoms()
    _seed_global_variables()
    _seed_item_groups()
    _seed_brands()
    _seed_color_standards()
    _seed_profile_systems()
    _seed_glass_types()
    _seed_glass_masters()
    _seed_calc_methods()
    _seed_cost_buckets()
    _seed_product_type()
    _seed_material_categories()
    _seed_slug_library()
    _seed_calc_rules()
    _seed_items()
    _seed_item_prices()
    _seed_dynamic_item_rules()
    _seed_cost_template()
    _seed_bom_items_and_set()
    _seed_bom()
    _seed_bom_version()
    frappe.db.commit()
    print("\nSeed data complete! Ready for calculate_bom() test.")


def _seed_uoms():
    """Tạo các UOM cần thiết nếu chưa có."""
    for uom_name in ["Kg", "m2", "m"]:
        if frappe.db.exists("UOM", uom_name):
            continue
        frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)


def _seed_global_variables():
    """Các biến toàn cục bất biến cho mọi BOM."""
    gvs = [
        ("VAT_RATE", 0.10), ("OH_VC_PCT", 0.03), ("OH_QLY_PCT", 0.03),
    ]
    for var_name, val in gvs:
        if frappe.db.exists("Formula Global Variable", var_name):
            continue
        frappe.get_doc({
            "doctype": "Formula Global Variable",
            "var_name": var_name,
            "constant_value": str(val),
            "value_source": "CONSTANT",
            "var_type": "Float",
        }).insert(ignore_permissions=True)


def _seed_item_groups():
    groups = [
        ("NHOM_PROFILE", "", 1), ("NHOM_XINGFA", "NHOM_PROFILE", 0),
        ("NHOM_ALUMIL", "NHOM_PROFILE", 0), ("KINH", "", 0),
        ("VTP", "", 0), ("ACCESSORY", "", 0),
    ]
    for name, parent, is_group in groups:
        if frappe.db.exists("Item Group", name): continue
        frappe.get_doc({
            "doctype": "Item Group", "item_group_name": name,
            "parent_item_group": parent or "All Item Groups", "is_group": is_group,
        }).insert(ignore_permissions=True)


def _seed_brands():
    for brand in ["XINGFA", "ALUMIL", "KINLONG"]:
        if frappe.db.exists("Brand", brand): continue
        frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)


def _seed_color_standards():
    for code, name, stock in [("WHITE", "Trắng", 1), ("DARK", "Đen", 1),
                               ("GRAY", "Ghi", 1), ("GO", "Vân gỗ", 0)]:
        if frappe.db.exists("AL Color Standard", code): continue
        frappe.get_doc({"doctype": "AL Color Standard", "color_code": code,
                         "color_name": name, "is_standard_stock": stock}).insert(ignore_permissions=True)


def _seed_profile_systems():
    for code, name, brand, fr, gl, fi, cb in [
        ("XINGFA_55", "Xingfa hệ 55", "XINGFA", 48, 90, 50, 48),
        ("ALUMIL_M9560", "Alumil M9560", "ALUMIL", 44, 86, 46, 44),
    ]:
        if frappe.db.exists("AL Profile System", code): continue
        frappe.get_doc({"doctype": "AL Profile System", "system_code": code,
            "system_name": name, "brand": brand, "offset_frame": fr,
            "offset_glass": gl, "offset_fixed": fi, "offset_crossbar": cb}).insert(ignore_permissions=True)


def _seed_glass_types():
    for code, name in [("DON","Kính dán"),("CUONG_LUC","Kính cường lực"),
                        ("HOP","Kính hộp"),("LOWE","Kính Low-E"),("LAM","Kính Lam")]:
        if frappe.db.exists("AL Glass Type", code): continue
        frappe.get_doc({"doctype": "AL Glass Type", "type_code": code, "type_name": name}).insert(ignore_permissions=True)


def _seed_glass_masters():
    for code, name, thick, gtype in [("KINH-LOWE-24","Kính Low-E 24mm",24,"LOWE"),
                                       ("KINH-DON-8","Kính dán 8mm",8,"DON")]:
        if frappe.db.exists("AL Glass Master", code): continue
        frappe.get_doc({"doctype": "AL Glass Master", "glass_code": code,
            "glass_name": name, "total_thick_mm": thick, "glass_type": gtype}).insert(ignore_permissions=True)


def _seed_calc_methods():
    for code, name, fn, unit in [
        ("LENGTH_TO_WEIGHT", "Length to Weight", "lambda w,h,tlr,**kw: (w/1000)*tlr", "kg"),
        ("AREA", "Area", "lambda w,h,tlr,**kw: (w/1000)*(h/1000)", "m2"),
        ("LENGTH_ONLY", "Length Only", "lambda w,h,tlr,**kw: w/1000", "m"),
        ("COUNT", "Count", "lambda w,h,tlr,**kw: 1", "cai"),
    ]:
        if frappe.db.exists("AL Quantity Calc Method", code): continue
        frappe.get_doc({"doctype": "AL Quantity Calc Method",
            "calc_pattern_code": code, "calc_pattern_name": name,
            "calc_fn": fn, "output_unit": unit}).insert(ignore_permissions=True)


def _seed_slug_library():
    slugs = [
        ("khung_ngang_tren","Khung ngang trên","NHOM","KHUNG"),
        ("khung_ngang_duoi","Khung ngang dưới","NHOM","KHUNG"),
        ("khung_dung","Khung đứng","NHOM","KHUNG"),
        ("do_ngang","Đố ngang","NHOM","KHUNG"),
        ("canh_ngang","Cánh ngang","NHOM","CANH"),
        ("canh_dung","Cánh đứng","NHOM","CANH"),
        ("kinh_tren","Kính cố định trên","KINH","GLASS"),
        ("kinh_duoi","Kính cánh dưới","KINH","GLASS"),
        ("nep_kinh_tren","Nẹp kính trên","NHOM","NEP"),
        ("nep_kinh_duoi","Nẹp kính dưới","NHOM","NEP"),
        ("keo_tren","Keo dán kính trên","VTP","KEO"),
        ("keo_duoi","Keo dán kính dưới","VTP","KEO"),
        ("gioang","Gioăng","VTP","GIOANG"),
        ("vit","Vít","VTP","VIT"),
        ("tay_nam","Tay nắm","PK","PK"),
        ("khoa","Khóa","PK","PK"),
        ("ban_le","Bản lề","PK","PK"),
    ]
    for slug, label, cat, tag in slugs:
        if frappe.db.exists("AL Slug Library", slug): continue
        frappe.get_doc({"doctype": "AL Slug Library", "slug": slug,
            "label": label, "category": cat, "group_tag": tag}).insert(ignore_permissions=True)


def _seed_material_categories():
    cats = [
        ("NHOM","Nhôm","LENGTH_TO_WEIGHT","VL_NHOM",1,0,0,0,1,1),
        ("KINH","Kính","AREA","VL_KINH",0,1,0,0,0,1),
        ("VTP","Vật tư phụ","LENGTH_ONLY","VL_VTP",0,0,0,0,0,1),
        ("PK","Phụ kiện","COUNT","VL_PK",0,0,0,0,0,1),
    ]
    for code, name, calc, bucket, ri, rpbi, rgm, rctx, hw, hd in cats:
        if frappe.db.exists("AL Material Category", code): continue
        frappe.get_doc({"doctype": "AL Material Category", "category_code": code,
            "category_name": name, "default_calc_pattern": calc, "default_cost_bucket": bucket,
            "requires_item_code": ri, "requires_price_base_item": rpbi,
            "requires_glass_master": rgm, "requires_ctx_inject_prefix": rctx,
            "has_weight": hw, "has_dimensions": hd}).insert(ignore_permissions=True)


def _seed_product_type():
    if not frappe.db.exists("AL Product Type", "DOOR"):
        frappe.get_doc({"doctype": "AL Product Type", "type_code": "DOOR",
            "type_name": "Cửa đi", "nc_pct": 0.08, "nc_ld_rate": 0.12,
            "profit_margin": 0.16}).insert(ignore_permissions=True)


def _seed_calc_rules():
    rules = [
        ("OFFSET-FRAME","Khe hở khung-cánh (default)","CONSTANT",48),
        ("OFFSET-GLASS","Khe hở cánh-kính (default)","CONSTANT",90),
        ("OFFSET-FIXED","Khe hở khung-kính cố định (default)","CONSTANT",50),
        ("OFFSET-DO-NGANG","Khe hở đố ngang (default)","CONSTANT",48),
    ]
    for code, name, rtype, val in rules:
        if frappe.db.exists("AL Calculation Rule", code): continue
        frappe.get_doc({"doctype": "AL Calculation Rule", "rule_code": code,
            "rule_name": name, "rule_type": rtype, "constant_value": val}).insert(ignore_permissions=True)


def _seed_dynamic_item_rules():
    # Rule 1: Nẹp kính theo độ dày
    if not frappe.db.exists("AL Dynamic Item Rule", "RULE-NEP-GLASSTHICK"):
        doc = frappe.get_doc({"doctype": "AL Dynamic Item Rule",
            "rule_code": "RULE-NEP-GLASSTHICK", "rule_name": "Chọn nẹp theo độ dày kính",
            "rule_type": "THRESHOLD"})
        doc.append("threshold_rows", {"from_value":0,"to_value":10.38,"result_item":"C3209-20"})
        doc.append("threshold_rows", {"from_value":10.39,"to_value":16,"result_item":"C3210-20"})
        doc.append("threshold_rows", {"from_value":16.01,"to_value":999,"result_item":"C3211-20"})
        doc.insert(ignore_permissions=True)

    # Rule 2: Keo theo loại kính
    if not frappe.db.exists("AL Dynamic Item Rule", "RULE-KEO-GLASSTYPE"):
        doc = frappe.get_doc({"doctype": "AL Dynamic Item Rule",
            "rule_code": "RULE-KEO-GLASSTYPE", "rule_name": "Chọn keo theo loại kính",
            "rule_type": "LOOKUP"})
        doc.append("lookup_rows", {"key_field":"LOWE","result_item":"KEO-TT-01"})
        doc.append("lookup_rows", {"key_field":"DON","result_item":"KEO-TT-02"})
        doc.insert(ignore_permissions=True)


def _seed_items():
    items = [
        ("NHOM-XINGFA","Nhôm Xingfa (đại diện)","NHOM_XINGFA","XINGFA","Kg",0),
        ("XF55-KB-20","Khung bao H55 2.0mm","NHOM_XINGFA","XINGFA","Kg",1.257),
        ("XF55-CANH-20","Cánh mở quay 2.0mm","NHOM_XINGFA","XINGFA","Kg",1.350),
        ("C3211-20","Nẹp kính >16mm","NHOM_XINGFA","XINGFA","Kg",0.312),
        ("C3210-20","Nẹp kính 11-16mm","NHOM_XINGFA","XINGFA","Kg",0.245),
        ("C3209-20","Nẹp kính <=10.38mm","NHOM_XINGFA","XINGFA","Kg",0.198),
        ("KINH-LOWE-24","Kính Low-E 24mm","KINH","","m2",0),
        ("KINH-DON-8","Kính dán 8mm","KINH","","m2",0),
        ("KEO-TT-01","Keo trung tính (Low-E)","VTP","","m",0),
        ("KEO-TT-02","Keo thường","VTP","","m",0),
        ("GIO-EPDM-55","Gioăng EPDM 55","VTP","","m",0),
        ("VIT-TK-35X16","Vít tự khoan 3.5x16","VTP","","Nos",0),
        ("KL-MZS20","Tay nắm Kinlong MZS20","ACCESSORY","KINLONG","Nos",0),
        ("KL-KHOA-01","Khóa Kinlong 01","ACCESSORY","KINLONG","Nos",0),
        ("KL-T-MJ06","Bản lề cối MJ06","ACCESSORY","KINLONG","Nos",0),
    ]
    for code, name, ig, brand, uom, wpm in items:
        if frappe.db.exists("Item", code): continue
        frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name,
            "item_group": ig, "brand": brand, "stock_uom": uom,
            "weight_per_unit": wpm, "is_stock_item": 1}).insert(ignore_permissions=True)


def _seed_item_prices():
    prices = [
        ("NHOM-XINGFA",113000,"WHITE"),
        ("NHOM-XINGFA",118000,"DARK"),
        ("NHOM-XINGFA",98000,"WHITE"),
        ("KINH-LOWE-24",1150000,None),
        ("KINH-DON-8",550000,None),
        ("KEO-TT-01",45000,None),
        ("KEO-TT-02",30000,None),
        ("GIO-EPDM-55",1250,None),
        ("VIT-TK-35X16",850,None),
        ("KL-MZS20",210000,None),
        ("KL-KHOA-01",350000,None),
        ("KL-T-MJ06",180000,None),
    ]
    for code, rate, color in prices:
        # Check existing by composite key
        existing = frappe.get_all("Item Price", filters={
            "item_code": code, "price_list_rate": rate,
            "price_list": "Standard Selling"
        }, limit=1)
        if existing:
            continue
        doc = frappe.get_doc({"doctype": "Item Price", "item_code": code,
            "price_list": "Standard Selling", "price_list_rate": rate})
        if color:
            doc.custom_color = color
        doc.insert(ignore_permissions=True)


def _seed_cost_buckets():
    buckets = [
        ("VL_NHOM","Vật liệu nhôm","LEAF","TONG_VL","aggregate_from_items"),
        ("VL_KINH","Vật liệu kính","LEAF","TONG_VL","aggregate_from_items"),
        ("VL_VTP","Vật tư phụ","LEAF","TONG_VL","aggregate_from_items"),
        ("VL_PK","Phụ kiện","LEAF","TONG_VL","aggregate_from_items"),
        ("TONG_VL","Tổng vật liệu","AGGREGATE","","formula"),
        ("NC_SX","Nhân công SX","LEAF","TONG_NC","formula"),
        ("NC_LD","Nhân công LĐ","LEAF","TONG_NC","formula"),
        ("TONG_NC","Tổng nhân công","AGGREGATE","","formula"),
        ("OH_VC","Overhead vận chuyển","LEAF","TONG_OH","formula"),
        ("OH_QLY","Overhead quản lý","LEAF","TONG_OH","formula"),
        ("TONG_OH","Tổng overhead","AGGREGATE","","formula"),
        ("GIA_THANH","Giá thành","AGGREGATE","","formula"),
        ("GIA_BAN","Giá bán chưa VAT","AGGREGATE","","formula"),
        ("GIA_VAT","Giá bán có VAT","AGGREGATE","","formula"),
    ]
    # Pass 1: Insert all without parent_bucket
    for code, name, role, parent, stype in buckets:
        if frappe.db.exists("AL Cost Bucket", code): continue
        frappe.get_doc({"doctype": "AL Cost Bucket", "bucket_code": code,
            "bucket_name": name, "bucket_role": role,
            "source_type": stype}).insert(ignore_permissions=True)
    # Pass 2: Set parent_bucket
    for code, name, role, parent, stype in buckets:
        if parent:
            frappe.db.set_value("AL Cost Bucket", code, "parent_bucket", parent)
    frappe.db.commit()


def _seed_cost_template():
    if frappe.db.exists("AL Cost Template", "CT-01-STANDARD"): return
    doc = frappe.get_doc({"doctype": "AL Cost Template",
        "template_code": "CT-01-STANDARD", "template_name": "Cost Template Chuẩn"})
    lines = [
        ("TONG_VL","VL_NHOM + VL_KINH + VL_VTP + VL_PK","TONG_VL",1),
        ("TONG_M2","(W_mm/1000)*(H_mm/1000)","",0),
        ("NC_SX","NC_SX_PCT * TONG_VL","NC_SX",0),
        ("NC_LD","NC_LD_PCT * TONG_VL","NC_LD",0),
        ("TONG_NC","NC_SX + NC_LD","TONG_NC",1),
        ("OH_VC","OH_VC_PCT * TONG_VL","OH_VC",0),
        ("OH_QLY","OH_QLY_PCT * (TONG_VL + TONG_NC)","OH_QLY",0),
        ("TONG_OH","OH_VC + OH_QLY","TONG_OH",1),
        ("GIA_THANH","TONG_VL + TONG_NC + TONG_OH","GIA_THANH",1),
        ("PROFIT","PROFIT_MARGIN * GIA_THANH","",0),
        ("GIA_BAN","GIA_THANH + PROFIT","GIA_BAN",1),
        ("DON_GIA_M2","GIA_BAN / TONG_M2","",0),
        ("VAT","VAT_RATE * GIA_BAN","",0),
        ("GIA_VAT","GIA_BAN + VAT","GIA_VAT",1),
    ]
    for code, formula, bucket, subtotal in lines:
        doc.append("items", {"line_code": code, "calc_formula": formula,
                              "cost_bucket": bucket or None, "is_subtotal": subtotal})
    doc.insert(ignore_permissions=True)


def _seed_bom_items_and_set():
    if frappe.db.exists("AL Bom Set", "BS-CDMQ-2C"): return
    doc = frappe.get_doc({"doctype": "AL Bom Set", "set_code": "BS-CDMQ-2C",
        "set_name": "Cửa đi 2 cánh mở quay + ô kính cố định", "product_type": "DOOR",
        "profile_system": "XINGFA_55"})

    items = [
        ("khung_ngang_tren","Fixed","XF55-KB-20","W_mm","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("khung_ngang_duoi","Fixed","XF55-KB-20","W_mm","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("khung_dung","Fixed","XF55-KB-20","H_mm","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("do_ngang","Fixed","XF55-KB-20","W_mm - 2*OFFSET_DO_NGANG","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_ngang","Fixed","XF55-CANH-20","W_mm/n_panel - OFFSET_FRAME","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_dung","Fixed","XF55-CANH-20","(H_mm-TransomHeight_mm) - OFFSET_FRAME","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("kinh_tren","Fixed","KINH-LOWE-24","W_mm - 2*OFFSET_FIXED","TransomHeight_mm - OFFSET_FIXED","1","AREA","VL_KINH","Fixed",""),
        ("kinh_duoi","Fixed","KINH-LOWE-24","W_mm/n_panel - OFFSET_GLASS","(H_mm-TransomHeight_mm) - OFFSET_GLASS","n_panel","AREA","VL_KINH","Fixed",""),
        ("nep_kinh_tren","Rule","","2*(items.kinh_tren.width + items.kinh_tren.height)","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("nep_kinh_duoi","Rule","","2*(items.kinh_duoi.width + items.kinh_duoi.height)","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("keo_tren","Rule","","2*(items.kinh_tren.width + items.kinh_tren.height)","","1","LENGTH_ONLY","VL_VTP","Fixed",""),
        ("keo_duoi","Rule","","2*(items.kinh_duoi.width + items.kinh_duoi.height)","","n_panel","LENGTH_ONLY","VL_VTP","Fixed",""),
        ("gioang","Fixed","GIO-EPDM-55","items.khung_ngang_tren.width + items.khung_ngang_duoi.width + 2*items.khung_dung.width","","1","LENGTH_ONLY","VL_VTP","Fixed",""),
        ("vit","Fixed","VIT-TK-35X16","","","10*n_panel + 8","COUNT","VL_VTP","Fixed",""),
        # PK items moved to accessory_items table below
    ]
    for slug, mode, item_code, width, height, qty, calc, bucket, ptype, pbi in items:
        # Lấy category từ Slug Library
        slug_cat = frappe.db.get_value("AL Slug Library", slug, "category")
        row = {
            "slug": slug, "category": slug_cat, "item_selection_mode": mode,
            "item_code": item_code or None,
            "width": width or None, "height": height or None, "qty": qty,
            "calc_pattern": calc, "cost_bucket": bucket, "price_type": ptype,
            "price_base_item": pbi or None,
        }
        # Rule config
        if mode == "Rule":
            if "nep" in slug:
                row["item_rule"] = "RULE-NEP-GLASSTHICK"
                row["rule_input_expr"] = f"items.{'kinh_tren' if 'tren' in slug else 'kinh_duoi'}.glass_thick"
            elif "keo" in slug:
                row["item_rule"] = "RULE-KEO-GLASSTYPE"
                row["rule_input_expr"] = f"items.{'kinh_tren' if 'tren' in slug else 'kinh_duoi'}.glass_type"
        # Glass config
        if slug in ("kinh_tren", "kinh_duoi"):
            row["default_glass_master"] = "KINH-LOWE-24"
            row["ctx_inject_prefix"] = slug
        doc.append("items", row)

    # Accessory items (Phụ kiện) - bảng riêng
    accessories = [
        ("tay_nam", "KL-MZS20", 1),
        ("khoa", "KL-KHOA-01", 1),
        ("ban_le", "KL-T-MJ06", "roundup(H_mm/700,0)*n_panel"),  # qty là formula
    ]
    for slug, item_code, qty in accessories:
        doc.append("accessory_items", {
            "slug": slug, "item_code": item_code, "qty": qty,
        })
    doc.insert(ignore_permissions=True)


def _seed_bom():
    if frappe.db.exists("AL BOM", "BOM-CDMQ-2C"): return
    frappe.get_doc({"doctype": "AL BOM", "bom_code": "BOM-CDMQ-2C",
        "bom_name": "Cửa đi 2 cánh mở quay + ô kính", "product_type": "DOOR",
        "brand": "XINGFA", "representative_item": "NHOM-XINGFA",
        "bom_set": "BS-CDMQ-2C", "default_cost_template": "CT-01-STANDARD",
    }).insert(ignore_permissions=True)


def _seed_bom_version():
    if frappe.db.exists("AL BOM Version", {"bom": "BOM-CDMQ-2C", "version_name": "v1.0"}):
        return
    doc = frappe.get_doc({"doctype": "AL BOM Version", "bom": "BOM-CDMQ-2C",
        "version_name": "v1.0", "valid_from": now(), "workflow_state": "Published"})
    doc.insert(ignore_permissions=True)
