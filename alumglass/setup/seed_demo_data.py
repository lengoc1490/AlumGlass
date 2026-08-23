"""Seed A-Z AlumGlass v28.7 — Cửa đi 2 cánh CDMQ-2C-TRANSOM"""
import frappe
from frappe.utils import now

def seed_all():
    _uoms(); _global_vars(); _seed_async_threshold(); _item_groups(); _brands(); _color_standards()
    _profile_systems(); _glass_types(); _glass_masters(); _calc_methods()
    _cost_buckets(); _product_type(); _material_categories(); _slug_library()
    _variable_library();
    _variable_set(); _calc_rules(); _items(); _item_prices()
    _dynamic_item_rules(); _pricing_dimensions(); _variable_dimension_mapping()
    _cost_template()
    _accessory_set(); _bom_items_and_set(); _bom(); _bom_version()
    # CDMQ-4C: seed sản phẩm phức tạp (4 cánh + 2 transom + sidelite).
    # ★ 2026-08-18 FIX: trước đây seed_cdmq_4c() KHÔNG được gọi trong seed_all()
    # → run_test.test_cdmq_4c() lỗi "AL BOM BOM-CDMQ-4C not found" trên site mới.
    # Phải chạy SAU _cost_template/_dynamic_item_rules/_items/_item_prices
    # (4C tham chiếu CT-01-STANDARD + RULE-NEP/KEO + items).
    seed_cdmq_4c()
    frappe.db.commit(); print("Seed A-Z complete ✓")

def _ex(dt,k): return frappe.db.exists(dt,k)
def _ins(doc): doc.insert(ignore_permissions=True)

def _uoms():
    for u in ["Kg","m2","m"]:
        if not _ex("UOM",u): _ins(frappe.get_doc({"doctype":"UOM","uom_name":u}))

def _global_vars():
    for v,val in [("VAT_RATE",0.10),("OH_VC_PCT",0.03),("OH_QLY_PCT",0.03)]:
        if not _ex("Formula Global Variable",v): _ins(frappe.get_doc({"doctype":"Formula Global Variable","var_name":v,"constant_value":str(val),"value_source":"CONSTANT","var_type":"Float"}))

def _seed_async_threshold():
    """P2 — Global Variable `ASYNC_BOM_THRESHOLD` (mặc định 150 dòng BOM).

    BOM có nhiều hơn N dòng (đếm từ bom_set_snapshot của version pin) sẽ tính
    qua background job (queue long) thay vì đồng bộ trong request — tránh
    timeout khi báo giá công trình lớn. Admin chỉnh trực tiếp trên UI Formula
    Global Variable, 0 dòng code. Idempotent.
    """
    if _ex("Formula Global Variable", "ASYNC_BOM_THRESHOLD"):
        return
    _ins(frappe.get_doc({
        "doctype": "Formula Global Variable",
        "var_name": "ASYNC_BOM_THRESHOLD",
        "label": "Async BOM Threshold (dòng)",
        "var_type": "Int",
        "value_source": "CONSTANT",
        "constant_value": "150",
        "is_active": 1,
        "description": "Số dòng BOM tối đa tính đồng bộ trong request. Vượt ngưỡng này → "
                       "tính qua background job (queue long, timeout 600s) + đẩy kết quả "
                       "về client qua realtime 'alumglass_bom_calc_done'. 0/trống = mọi "
                       "BOM chạy sync.",
    }))

def _item_groups():
    for n,p,ig in [("NHOM_PROFILE","",1),("NHOM_XINGFA","NHOM_PROFILE",0),("NHOM_ALUMIL","NHOM_PROFILE",0),("KINH","",0),("VTP","",0),("ACCESSORY","",0)]:
        if not _ex("Item Group",n): _ins(frappe.get_doc({"doctype":"Item Group","item_group_name":n,"parent_item_group":p or "All Item Groups","is_group":ig}))
    # SAN_PHAM: group cha cho SẢN PHẨM HOÀN CHỈNH (Item bán ra) — dùng làm filter
    # cho field "Mã sản phẩm" (AL BOM.representative_item / AL Bom Set.item_code /
    # AL Accessory Set.item_code). Item Group name = "SAN_PHAM" (code dùng trong
    # get_query filter), tên tiếng Việt đặt trong description. Job này CHỈ tạo
    # group, KHÔNG seed Item sản phẩm mới (sẽ tạo ở job khác).
    if not _ex("Item Group", "SAN_PHAM"):
        _ins(frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": "SAN_PHAM",
            "parent_item_group": "All Item Groups",
            "is_group": 1,
            "description": "Sản phẩm hoàn chỉnh — Item bán ra (mã sản phẩm) cho quotation.",
        }))

def _brands():
    for b in ["XINGFA","ALUMIL","KINLONG"]:
        if not _ex("Brand",b): _ins(frappe.get_doc({"doctype":"Brand","brand":b}))

def _color_standards():
    for c,n,s,pm in [("WHITE","Trắng",1,1.0),("DARK","Đen",1,1.08),("GRAY","Ghi",1,1.05),("GO","Vân gỗ",0,1.20)]:
        if not _ex("AL Color Standard",c): _ins(frappe.get_doc({"doctype":"AL Color Standard","color_code":c,"color_name":n,"is_standard_stock":s,"price_multiplier":pm}))

def _profile_systems():
    for c,n,b,fr,gl,fi,cb in [("XINGFA_55","Xingfa hệ 55","XINGFA",48,90,50,48),("ALUMIL_M9560","Alumil M9560","ALUMIL",44,86,46,44)]:
        if not _ex("AL Profile System",c): _ins(frappe.get_doc({"doctype":"AL Profile System","system_code":c,"system_name":n,"brand":b,"offset_frame":fr,"offset_glass":gl,"offset_fixed":fi,"offset_crossbar":cb}))

def _glass_types():
    for c,n in [("DON","Kính dán"),("CUONG_LUC","Kính cường lực"),("HOP","Kính hộp"),("LOWE","Kính Low-E"),("LAM","Kính Lam")]:
        if not _ex("AL Glass Type",c): _ins(frappe.get_doc({"doctype":"AL Glass Type","type_code":c,"type_name":n}))

def _glass_masters():
    for c,n,t,g in [("KINH-LOWE-24","Kính Low-E 24mm",24,"LOWE"),("KINH-DON-8","Kính dán 8mm",8,"DON")]:
        if not _ex("AL Glass Master",c): _ins(frappe.get_doc({"doctype":"AL Glass Master","glass_code":c,"glass_name":n,"total_thick_mm":t,"glass_type":g}))

def _calc_methods():
    """Pre-seed AL Quantity Calc Method: 4 legacy + 9 v28.8 (hybrid fallback).

    - calc_fn empty → hệ thống fallback PATTERN_FORMULAS (formula_handlers).
    - `group` dùng cho dropdown filter (get_available_patterns).
    - Idempotent: chỉ tạo khi chưa tồn tại (`_ex`). 4 record cũ giữ nguyên calc_fn
      → golden zero-risk (Bom Item seed reference AREA/LENGTH_ONLY vẫn resolve).
    """
    for c,n,fn,u,g in [
        # 4 pattern legacy (giữ nguyên calc_fn/output_unit từ seed cũ)
        ("LENGTH_TO_WEIGHT","Length to Weight","lambda w,h,tlr,**kw: (w/1000)*tlr","kg","Tuyến tính"),
        ("AREA","Area","lambda w,h,tlr,**kw: (w/1000)*(h/1000)","m2","Diện tích"),
        ("LENGTH_ONLY","Length Only","lambda w,h,tlr,**kw: w/1000","m","Tuyến tính"),
        ("COUNT","Count","lambda w,h,tlr,**kw: 1","cai","Đếm-Bộ"),
        # 9 pattern mới (v28.8) — khớp PATTERN_FORMULAS trong formula_handlers
        ("LENGTH_M","Length Meter","lambda w,h,tlr,**kw: w/1000","m","Tuyến tính"),
        ("HEIGHT_M","Height Meter","lambda w,h,tlr,**kw: h/1000","m","Tuyến tính"),
        ("LENGTH_TO_PIECES","Length to Pieces","lambda w,h,tlr,**kw: (w/1000)/kw.get('piece_length',1)","cai","Tuyến tính"),
        ("AREA_TO_WEIGHT","Area to Weight","lambda w,h,tlr,**kw: (w/1000)*(h/1000)*tlr","kg","Diện tích"),
        ("PERIMETER_M","Perimeter Meter","lambda w,h,tlr,**kw: 2*(w+h)/1000","m","Chu vi"),
        ("VOLUME_M3","Volume Cubic Meter","lambda w,h,tlr,**kw: (w/1000)*(h/1000)*kw.get('depth',0)/1000","m3","Thể tích"),
        ("SET","Set","lambda w,h,tlr,**kw: 1","bo","Đếm-Bộ"),
        ("COUNT_PER_LENGTH","Count per Length","lambda w,h,tlr,**kw: (w/1000)/kw.get('spacing',1)","cai","Đếm-Bộ"),
        ("COUNT_PER_AREA","Count per Area","lambda w,h,tlr,**kw: (w/1000)*(h/1000)/kw.get('area_per_piece',1)","cai","Đếm-Bộ"),
    ]:
        if not _ex("AL Quantity Calc Method",c):
            _ins(frappe.get_doc({"doctype":"AL Quantity Calc Method","calc_pattern_code":c,"calc_pattern_name":n,"calc_fn":fn,"output_unit":u,"group":g}))

def _cost_buckets():
    bkts=[("VL_NHOM","Vật liệu nhôm","LEAF","TONG_VL"),("VL_KINH","Vật liệu kính","LEAF","TONG_VL"),("VL_VTP","Vật tư phụ","LEAF","TONG_VL"),("VL_PK","Phụ kiện","LEAF","TONG_VL"),("TONG_VL","Tổng vật liệu","AGGREGATE",""),("NC_SX","Nhân công SX","LEAF","TONG_NC"),("NC_LD","Nhân công LĐ","LEAF","TONG_NC"),("TONG_NC","Tổng nhân công","AGGREGATE",""),("OH_VC","Overhead VC","LEAF","TONG_OH"),("OH_QLY","Overhead QL","LEAF","TONG_OH"),("TONG_OH","Tổng overhead","AGGREGATE",""),("GIA_THANH","Giá thành","AGGREGATE",""),("GIA_BAN","Giá bán chưa VAT","AGGREGATE",""),("GIA_VAT","Giá bán có VAT","AGGREGATE","")]
    for c,n,r,p in bkts:
        if not _ex("AL Cost Bucket",c): _ins(frappe.get_doc({"doctype":"AL Cost Bucket","bucket_code":c,"bucket_name":n,"bucket_role":r,"source_type":"aggregate_from_items" if r=="LEAF" and c.startswith("VL_") else "formula"}))
    for c,n,r,p in bkts:
        if p: frappe.db.set_value("AL Cost Bucket",c,"parent_bucket",p)
    frappe.db.commit()

def _product_type():
    if not _ex("AL Product Type","DOOR"): _ins(frappe.get_doc({"doctype":"AL Product Type","type_code":"DOOR","type_name":"Cửa đi","nc_pct":0.08,"nc_ld_rate":0.12,"profit_margin":0.16}))

def _material_categories():
    for c,n,calc,bkt,ri,rpbi,rgm,rctx,hw,hd,sp in [("NHOM","Nhôm","LENGTH_TO_WEIGHT","VL_NHOM",1,1,0,0,1,1,3),("KINH","Kính","AREA","VL_KINH",1,0,1,1,0,1,5),("VTP","Vật tư phụ","LENGTH_ONLY","VL_VTP",1,0,0,0,0,1,2),("PK","Phụ kiện","COUNT","VL_PK",1,0,0,0,0,0,0)]:
        if not _ex("AL Material Category",c): _ins(frappe.get_doc({"doctype":"AL Material Category","category_code":c,"category_name":n,"default_calc_pattern":calc,"default_cost_bucket":bkt,"requires_item_code":ri,"requires_price_base_item":rpbi,"requires_glass_master":rgm,"requires_ctx_inject_prefix":rctx,"has_weight":hw,"has_dimensions":hd,"default_scrap_pct":sp}))

def _slug_library():
    for s,l,c,t in [("khung_ngang_tren","Khung ngang trên","NHOM","KHUNG"),("khung_ngang_duoi","Khung ngang dưới","NHOM","KHUNG"),("khung_dung","Khung đứng","NHOM","KHUNG"),("do_ngang","Đố ngang","NHOM","KHUNG"),("canh_ngang","Cánh ngang","NHOM","CANH"),("canh_dung","Cánh đứng","NHOM","CANH"),("kinh_tren","Kính cố định trên","KINH","GLASS"),("kinh_duoi","Kính cánh dưới","KINH","GLASS"),("nep_kinh_tren","Nẹp kính trên","NHOM","NEP"),("nep_kinh_duoi","Nẹp kính dưới","NHOM","NEP"),("keo_tren","Keo dán kính trên","VTP","KEO"),("keo_duoi","Keo dán kính dưới","VTP","KEO"),("gioang","Gioăng","VTP","GIOANG"),("vit","Vít","VTP","VIT"),("tay_nam","Tay nắm","PK","PK"),("khoa","Khóa","PK","PK"),("ban_le","Bản lề","PK","PK"),
        # CDMQ-4C: 4 cánh + 2 transom + sidelite
        ("khung_dung_trai","Khung đứng trái","NHOM","KHUNG"),("khung_dung_phai","Khung đứng phải","NHOM","KHUNG"),("do_ngang_tren","Đố ngang trên","NHOM","KHUNG"),("do_ngang_duoi","Đố ngang dưới","NHOM","KHUNG"),("canh_dung_c1","Cánh đứng cánh 1","NHOM","CANH"),("canh_dung_c2","Cánh đứng cánh 2","NHOM","CANH"),("canh_dung_c3","Cánh đứng cánh 3","NHOM","CANH"),("canh_dung_c4","Cánh đứng cánh 4","NHOM","CANH"),("canh_ngang_c1","Cánh ngang cánh 1","NHOM","CANH"),("canh_ngang_c2","Cánh ngang cánh 2","NHOM","CANH"),("canh_ngang_c3","Cánh ngang cánh 3","NHOM","CANH"),("canh_ngang_c4","Cánh ngang cánh 4","NHOM","CANH"),("kinh_fixed_top","Kính cố định trên","KINH","GLASS"),("kinh_fixed_bottom","Kính cố định dưới","KINH","GLASS"),("kinh_canh","Kính cánh","KINH","GLASS"),("kinh_sidelite","Kính vách bên","KINH","GLASS"),("nep_kinh_top","Nẹp kính ô trên","NHOM","NEP"),("nep_kinh_bottom","Nẹp kính ô dưới","NHOM","NEP"),("nep_kinh_canh","Nẹp kính cánh","NHOM","NEP"),("nep_kinh_sidelite","Nẹp kính vách","NHOM","NEP"),("keo_top","Keo ô kính trên","VTP","KEO"),("keo_bottom","Keo ô kính dưới","VTP","KEO"),("keo_canh","Keo kính cánh","VTP","KEO"),("keo_sidelite","Keo kính vách","VTP","KEO")]:
        if not _ex("AL Slug Library",s): _ins(frappe.get_doc({"doctype":"AL Slug Library","slug":s,"label":l,"category":c,"group_tag":t}))


def _variable_library():
    """Thư viện biến tập trung — định nghĩa 1 lần, dùng nhiều nơi."""
    # Format: (var_name, var_label, var_type, link_doctype, select_options, default_value, category, is_system, source_doctype, source_field)
    libs = [
        # Kích thước
        ("W_mm", "Chiều rộng (mm)", "Float", "", "", "2400", "Kích thước", 0, "", ""),
        ("H_mm", "Chiều cao (mm)", "Float", "", "", "2600", "Kích thước", 0, "", ""),
        ("TransomHeight_mm", "Cao ô kính cố định (mm)", "Float", "", "", "600", "Kích thước", 0, "", ""),
        # Kích thước cho CDMQ-4C (dùng chung W_mm, H_mm cho cửa chính)
        ("TransomHeightTop", "Cao ô kính trên (mm)", "Float", "", "", "600", "Kích thước", 0, "", ""),
        ("TransomHeightBottom", "Cao ô kính dưới (mm)", "Float", "", "", "400", "Kích thước", 0, "", ""),
        ("SideLiteWidth", "Rộng vách kính (mm)", "Float", "", "", "800", "Kích thước", 0, "", ""),
        ("SideLiteHeight", "Cao vách kính (mm)", "Float", "", "", "2800", "Kích thước", 0, "", ""),
        # Cấu hình
        ("n_panel", "Số cánh", "Int", "", "", "2", "Cấu hình", 0, "", ""),
        ("glass_master", "Loại kính", "Link", "AL Glass Master", "", "", "Cấu hình", 0, "", ""),
        ("accessory_set", "Bộ phụ kiện", "Link", "AL Accessory Set", "", "", "Cấu hình", 0, "", ""),
        # Màu sắc & Xuất xứ
        ("aluminum_color", "Màu nhôm", "Link", "AL Color Standard", "", "WHITE", "Màu sắc", 0, "", ""),
        ("aluminum_origin", "Xuất xứ nhôm", "Select", "", "IMPORT\nDOMESTIC", "IMPORT", "Xuất xứ", 0, "", ""),
        # Kỹ thuật
        ("aluminum_thickness", "Độ dày nhôm (micron)", "Float", "", "", "20", "Kỹ thuật", 0, "", ""),
        ("aluminum_surface", "Bề mặt hoàn thiện", "Select", "", "POWDER_COATED\nANODIZED\nWOOD_GRAIN", "POWDER_COATED", "Kỹ thuật", 0, "", ""),
        # Thi công
        ("installation_height_m", "Chiều cao lắp đặt (m)", "Float", "", "", "3", "Thi công", 0, "", ""),
        # System variables — resolve tự động từ source_doctype.source_field
        ("OFFSET_FRAME", "Khe hở khung-cánh", "Float", "", "", "", "System", 1, "AL Profile System", "offset_frame"),
        ("OFFSET_GLASS", "Khe hở cánh-kính", "Float", "", "", "", "System", 1, "AL Profile System", "offset_glass"),
        ("OFFSET_FIXED", "Khe hở khung-kính cố định", "Float", "", "", "", "System", 1, "AL Profile System", "offset_fixed"),
        ("OFFSET_DO_NGANG", "Khe hở đố ngang", "Float", "", "", "", "System", 1, "AL Profile System", "offset_crossbar"),
        ("NC_SX_PCT", "% Nhân công SX", "Float", "", "", "0.08", "System", 1, "AL Product Type", "nc_pct"),
        ("NC_LD_PCT", "% Nhân công LĐ", "Float", "", "", "0.12", "System", 1, "AL Product Type", "nc_ld_rate"),
        ("PROFIT_MARGIN", "% Lợi nhuận", "Float", "", "", "0.16", "System", 1, "AL Product Type", "profit_margin"),
        ("VAT_RATE", "Thuế VAT", "Float", "", "", "0.10", "System", 1, "", ""),
        ("OH_VC_PCT", "% VC overhead", "Float", "", "", "0.03", "System", 1, "", ""),
        ("OH_QLY_PCT", "% QL overhead", "Float", "", "", "0.03", "System", 1, "", ""),
    ]
    for vn, vl, vt, lk, so, dv, cat, sys, sdt, sf in libs:
        if _ex("AL Variable Library", vn): continue
        _ins(frappe.get_doc({
            "doctype": "AL Variable Library", "var_name": vn, "var_label": vl,
            "var_type": vt, "link_doctype": lk or None, "select_options": so or None,
            "default_value": dv, "category": cat, "is_system": sys,
            "source_doctype": sdt or None, "source_field": sf or None,
        }))

def _variable_set():
    if _ex("AL Variable Set","VS-CDMQ"): return
    doc=frappe.get_doc({"doctype":"AL Variable Set","set_code":"VS-CDMQ","set_name":"Cửa đi 2 cánh mở quay + ô kính","product_type":"DOOR"})
    for vn,dv,sr,rq in [("W_mm","2400",10,1),("H_mm","2600",20,1),("TransomHeight_mm","600",30,0),("n_panel","2",40,1),("aluminum_color","WHITE",50,1),("aluminum_origin","IMPORT",60,1),("aluminum_thickness","20",70,0),("aluminum_surface","POWDER_COATED",80,0),("glass_master","",90,0),("accessory_set","",100,0),("installation_height_m","3",110,0)]:
        doc.append("items",{"variable":vn,"default_value":dv,"sort_order":sr,"is_required":rq})
    _ins(doc)

def _calc_rules():
    # Offset CONSTANT rules (backward compat)
    for c,n,t,v in [("OFFSET-FRAME","Khe hở khung-cánh","CONSTANT",48),("OFFSET-GLASS","Khe hở cánh-kính","CONSTANT",90),("OFFSET-FIXED","Khe hở khung-kính","CONSTANT",50),("OFFSET-DO-NGANG","Khe hở đố ngang","CONSTANT",48)]:
        if not _ex("AL Calculation Rule",c): _ins(frappe.get_doc({"doctype":"AL Calculation Rule","rule_code":c,"rule_name":n,"rule_type":t,"constant_value":v}))

    # RULE-BANLE-QTY: Số bản lề theo chiều cao cửa
    # ★ 2026-08-18 FIX (golden CDMQ-2C): tier 2101-2700 = 4 (không phải 3).
    # Golden test run_test.expect GIA_VAT=22,717,289 ⇔ VL_PK=2,000,000 ⇔
    # ban_le qty=8 (H_mm=2600 → 4 bản lề/cánh × 2 cánh). Tier cũ (3) ra 6
    # bản lề → VL_PK=1,640,000 → lệch golden 581,540. Kế hoạch (KE_HOACH_
    # TRIEN_KHAI_CHI_TIET.md §VL_PK: 2000000) + ví dụ MultiTableFormulaBuilder
    # (assert accessories__ban_le__qty == 8) cùng khớp 8 bản lề.
    if not _ex("AL Calculation Rule","RULE-BANLE-QTY"):
        doc = frappe.get_doc({"doctype":"AL Calculation Rule","rule_code":"RULE-BANLE-QTY","rule_name":"Số bản lề theo chiều cao","rule_type":"THRESHOLD"})
        for f,t,v in [(0,2100,2),(2101,2700,4),(2701,99999,4)]:
            doc.append("threshold_rows",{"from_value":f,"to_value":t,"result_value":v})
        _ins(doc)

    # RULE-HEIGHT-MULT: Hệ số nhân công theo độ cao lắp đặt
    if not _ex("AL Calculation Rule","RULE-HEIGHT-MULT"):
        doc = frappe.get_doc({"doctype":"AL Calculation Rule","rule_code":"RULE-HEIGHT-MULT","rule_name":"Hệ số NC theo độ cao","rule_type":"THRESHOLD"})
        for f,t,v in [(0,10,1.0),(10.1,30,1.2),(30.1,60,1.5),(60.1,999,2.0)]:
            doc.append("threshold_rows",{"from_value":f,"to_value":t,"result_value":v})
        _ins(doc)

def _items():
    for c,n,ig,b,u,w in [("NHOM-XINGFA","Nhôm Xingfa (đại diện)","NHOM_XINGFA","XINGFA","Kg",0),("XF55-KB-20","Khung bao H55 2.0mm","NHOM_XINGFA","XINGFA","Kg",1.257),("XF55-CANH-20","Cánh mở quay 2.0mm","NHOM_XINGFA","XINGFA","Kg",1.350),("C3211-20","Nẹp kính >16mm","NHOM_XINGFA","XINGFA","Kg",0.312),("C3210-20","Nẹp kính 11-16mm","NHOM_XINGFA","XINGFA","Kg",0.245),("C3209-20","Nẹp kính <=10.38mm","NHOM_XINGFA","XINGFA","Kg",0.198),("KINH-LOWE-24","Kính Low-E 24mm","KINH","","m2",0),("KINH-DON-8","Kính dán 8mm","KINH","","m2",0),("KEO-TT-01","Keo trung tính","VTP","","m",0),("KEO-TT-02","Keo thường","VTP","","m",0),("GIO-EPDM-55","Gioăng EPDM 55","VTP","","m",0),("VIT-TK-35X16","Vít tự khoan 3.5x16","VTP","","Nos",0),("KL-MZS20","Tay nắm Kinlong MZS20","ACCESSORY","KINLONG","Nos",0),("KL-KHOA-01","Khóa Kinlong 01","ACCESSORY","KINLONG","Nos",0),("KL-T-MJ06","Bản lề cối MJ06","ACCESSORY","KINLONG","Nos",0)]:
        if not _ex("Item",c): _ins(frappe.get_doc({"doctype":"Item","item_code":c,"item_name":n,"item_group":ig,"brand":b or None,"stock_uom":u,"weight_per_unit":w,"is_stock_item":1}))

def _item_prices():
    for c in ["NHOM-XINGFA","XF55-KB-20","XF55-CANH-20","C3211-20","C3210-20","C3209-20","KINH-LOWE-24","KINH-DON-8","KEO-TT-01","KEO-TT-02","GIO-EPDM-55","VIT-TK-35X16","KL-MZS20","KL-KHOA-01","KL-T-MJ06"]:
        frappe.db.sql("DELETE FROM `tabItem Price` WHERE item_code=%s",(c,))
    frappe.db.commit()
    for c,r in [("NHOM-XINGFA",113000),("XF55-KB-20",113000),("XF55-CANH-20",113000),("C3211-20",113000),("C3210-20",113000),("C3209-20",113000),("KINH-LOWE-24",1150000),("KINH-DON-8",550000),("KEO-TT-01",45000),("KEO-TT-02",30000),("GIO-EPDM-55",1250),("VIT-TK-35X16",850),("KL-MZS20",210000),("KL-KHOA-01",350000),("KL-T-MJ06",180000)]:
        _ins(frappe.get_doc({"doctype":"Item Price","item_code":c,"price_list":"Standard Selling","price_list_rate":r,"currency":"VND","buying":0,"selling":1}))

def _dynamic_item_rules():
    if not _ex("AL Dynamic Item Rule","RULE-NEP-GLASSTHICK"):
        doc=frappe.get_doc({"doctype":"AL Dynamic Item Rule","rule_code":"RULE-NEP-GLASSTHICK","rule_name":"Chọn nẹp theo độ dày kính","rule_type":"THRESHOLD"})
        for f,t,i in [(0,10.38,"C3209-20"),(10.39,16,"C3210-20"),(16.01,999,"C3211-20")]: doc.append("threshold_rows",{"from_value":f,"to_value":t,"result_item":i})
        _ins(doc)
    if not _ex("AL Dynamic Item Rule","RULE-KEO-GLASSTYPE"):
        doc=frappe.get_doc({"doctype":"AL Dynamic Item Rule","rule_code":"RULE-KEO-GLASSTYPE","rule_name":"Chọn keo theo loại kính","rule_type":"LOOKUP"})
        for k,i in [("LOWE","KEO-TT-01"),("DON","KEO-TT-02")]: doc.append("lookup_rows",{"key_field":k,"result_item":i})
        _ins(doc)

def _pricing_dimensions():
    for c,n,t,lk,so in [("MAU_SAC","Màu sắc","Link","AL Color Standard",""),("XUAT_XU","Xuất xứ","Select","","IMPORT\\nDOMESTIC"),("DO_DAY","Độ dày","Int","",""),("BE_MAT","Bề mặt","Select","","POWDER_COATED\\nANODIZED\\nWOOD_GRAIN")]:
        if not _ex("AL Pricing Dimension",c): _ins(frappe.get_doc({"doctype":"AL Pricing Dimension","dimension_code":c,"dimension_name":n,"dimension_type":t,"link_doctype":lk or None,"select_options":so or None}))

def _variable_dimension_mapping():
    """Map input variable → pricing dimension → composite key cho tra giá Item Price."""
    for vn, pd, mc, pm in [("aluminum_color","MAU_SAC","NHOM",1.0),("aluminum_origin","XUAT_XU","NHOM",1.0),("aluminum_thickness","DO_DAY","NHOM",1.0),("aluminum_surface","BE_MAT","NHOM",1.0)]:
        if not _ex("AL Variable Dimension Mapping",{"variable_name":vn,"pricing_dimension":pd}):
            _ins(frappe.get_doc({"doctype":"AL Variable Dimension Mapping","variable_name":vn,"pricing_dimension":pd,"material_category":mc,"price_multiplier":pm}))

def _cost_template():
    if _ex("AL Cost Template","CT-01-STANDARD"): return
    doc=frappe.get_doc({"doctype":"AL Cost Template","template_code":"CT-01-STANDARD","template_name":"Cost Template Chuẩn"})
    for c,f,b,st in [("TONG_VL","VL_NHOM + VL_KINH + VL_VTP + VL_PK","TONG_VL",1),("TONG_M2","(W_mm/1000)*(H_mm/1000)","",0),("NC_SX","NC_SX_PCT * TONG_VL","NC_SX",0),("NC_LD","NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)","NC_LD",0),("TONG_NC","NC_SX + NC_LD","TONG_NC",1),("OH_VC","OH_VC_PCT * TONG_VL","OH_VC",0),("OH_QLY","OH_QLY_PCT * (TONG_VL + TONG_NC)","OH_QLY",0),("TONG_OH","OH_VC + OH_QLY","TONG_OH",1),("GIA_THANH","TONG_VL + TONG_NC + TONG_OH","GIA_THANH",1),("PROFIT","PROFIT_MARGIN * GIA_THANH","",0),("GIA_BAN","GIA_THANH + PROFIT","GIA_BAN",1),("DON_GIA_M2","GIA_BAN / TONG_M2","",0),("VAT","VAT_RATE * GIA_BAN","",0),("GIA_VAT","GIA_BAN + VAT","GIA_VAT",1)]:
        doc.append("items",{"line_code":c,"calc_formula":f,"cost_bucket":b or None,"is_subtotal":st})
    _ins(doc)

def _accessory_set():
    """Bộ phụ kiện mẫu ACC-CDMQ-2C"""
    if _ex("AL Accessory Set","ACC-CDMQ-2C"): return
    doc=frappe.get_doc({"doctype":"AL Accessory Set","set_code":"ACC-CDMQ-2C","set_name":"Bộ PK Cửa đi 2 cánh mở quay","product_type":"DOOR","variable_set":"VS-CDMQ"})
    # Sử dụng lookup_rule("RULE-BANLE-QTY", H_mm) để tra số bản lề theo chiều cao
    for s,ic,q,qf in [("tay_nam","KL-MZS20",1,""),("khoa","KL-KHOA-01",1,""),("ban_le","KL-T-MJ06",0,"lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel")]:
        doc.append("items",{"slug":s,"item_code":ic,"qty":q,"qty_formula":qf})
    _ins(doc)

def _bom_items_and_set():
    if _ex("AL Bom Set","BS-CDMQ-2C"): return
    import json
    doc=frappe.get_doc({"doctype":"AL Bom Set","set_code":"BS-CDMQ-2C","set_name":"Cửa đi 2 cánh mở quay + ô kính cố định","product_type":"DOOR","profile_system":"XINGFA_55","variable_set":"VS-CDMQ","default_accessory_set":"ACC-CDMQ-2C",
        "formula_fieldnames":json.dumps(["width","height","qty","show_condition","item_condition_formula","rule_input_expr"])})
    items=[("khung_ngang_tren","Fixed","XF55-KB-20","W_mm","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("khung_ngang_duoi","Fixed","XF55-KB-20","W_mm","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("khung_dung","Fixed","XF55-KB-20","H_mm","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("do_ngang","Fixed","XF55-KB-20","W_mm - 2*OFFSET_DO_NGANG","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("canh_ngang","Fixed","XF55-CANH-20","W_mm/n_panel - OFFSET_FRAME","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("canh_dung","Fixed","XF55-CANH-20","(H_mm-TransomHeight_mm) - OFFSET_FRAME","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("kinh_tren","Fixed","KINH-LOWE-24","W_mm - 2*OFFSET_FIXED","TransomHeight_mm - OFFSET_FIXED","1","AREA","VL_KINH","Fixed",""),("kinh_duoi","Fixed","KINH-LOWE-24","W_mm/n_panel - OFFSET_GLASS","(H_mm-TransomHeight_mm) - OFFSET_GLASS","n_panel","AREA","VL_KINH","Fixed",""),("nep_kinh_tren","Rule","","2*(items.kinh_tren.width + items.kinh_tren.height)","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("nep_kinh_duoi","Rule","","2*(items.kinh_duoi.width + items.kinh_duoi.height)","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),("keo_tren","Rule","","2*(items.kinh_tren.width + items.kinh_tren.height)","","1","LENGTH_ONLY","VL_VTP","Fixed",""),("keo_duoi","Rule","","2*(items.kinh_duoi.width + items.kinh_duoi.height)","","n_panel","LENGTH_ONLY","VL_VTP","Fixed",""),("gioang","Fixed","GIO-EPDM-55","items.khung_ngang_tren.width + items.khung_ngang_duoi.width + 2*items.khung_dung.width","","1","LENGTH_ONLY","VL_VTP","Fixed",""),("vit","Fixed","VIT-TK-35X16","","","10*n_panel + 8","COUNT","VL_VTP","Fixed","")]
    for s,mode,ic,w,h,q,calc,bkt,ptype,pbi in items:
        cat=frappe.db.get_value("AL Slug Library",s,"category")
        row={"slug":s,"category":cat,"item_selection_mode":mode,"item_code":ic or None,"width":w or None,"height":h or None,"qty":q,"calc_pattern":calc,"cost_bucket":bkt,"price_type":ptype,"price_base_item":pbi or None}
        if mode=="Rule":
            row["item_rule"]="RULE-NEP-GLASSTHICK" if "nep" in s else "RULE-KEO-GLASSTYPE"
            row["rule_input_expr"]=f"items.{'kinh_tren' if 'tren' in s else 'kinh_duoi'}.{'glass_thick' if 'nep' in s else 'glass_type'}"
        if s in ("kinh_tren","kinh_duoi"): row["default_glass_master"]="KINH-LOWE-24"; row["ctx_inject_prefix"]=s
        doc.append("items",row)
    _ins(doc)

def _bom():
    if not _ex("AL BOM","BOM-CDMQ-2C"): _ins(frappe.get_doc({"doctype":"AL BOM","bom_code":"BOM-CDMQ-2C","bom_name":"Cửa đi 2 cánh mở quay + ô kính","product_type":"DOOR","brand":"XINGFA","representative_item":"NHOM-XINGFA","bom_set":"BS-CDMQ-2C","default_cost_template":"CT-01-STANDARD"}))

def _bom_version():
    if not _ex("AL BOM Version",{"bom":"BOM-CDMQ-2C","version_name":"v1.0"}): _ins(frappe.get_doc({"doctype":"AL BOM Version","bom":"BOM-CDMQ-2C","version_name":"v1.0","valid_from":now(),"workflow_state":"Published"}))


# ═══════════════════════════════════════════════════════════════════════
# CDMQ-4C: Cửa đi 4 cánh + 2 transom + sidelite (sản phẩm PHỨC TẠP)
# ═══════════════════════════════════════════════════════════════════════

def seed_cdmq_4c():
    """Seed sản phẩm phức tạp: Cửa đi 4 cánh + 2 ô kính cố định + vách kính bên.
    Demo TOÀN BỘ tính năng v28.7.1: system vars, cross-row ref, dynamic item rule,
    lookup_rule, price multiplier, scrap, cost template chain.
    """
    _variable_set_4c()
    _accessory_set_4c()
    _bom_items_and_set_4c()
    _bom_4c()
    _bom_version_4c()
    frappe.db.commit()
    print("Seed CDMQ-4C complete ✓")
    print("  BOM: BOM-CDMQ-4C | BS-CDMQ-4C | VS-CDMQ-4C | ACC-CDMQ-4C")
    print("  22 Bom Items | 4 Cost Buckets | 14 Cost Template lines")

def _variable_set_4c():
    if _ex("AL Variable Set","VS-CDMQ-4C"): return
    doc = frappe.get_doc({"doctype":"AL Variable Set","set_code":"VS-CDMQ-4C",
        "set_name":"Cửa đi 4 cánh mở quay + 2 ô kính + vách","product_type":"DOOR"})
    for vn,dv,sr,rq in [
        ("W_mm","3600",10,1),("H_mm","3200",20,1),
        ("TransomHeightTop","600",30,1),("TransomHeightBottom","400",40,1),
        ("n_panel","4",50,1),
        ("SideLiteWidth","800",60,0),("SideLiteHeight","2800",70,0),
        ("aluminum_color","DARK",80,1),("aluminum_origin","IMPORT",90,1),
        ("aluminum_thickness","20",100,0),("aluminum_surface","POWDER_COATED",110,0),
        ("installation_height_m","15",120,0),("glass_master","KINH-LOWE-24",130,0),
        ("accessory_set","ACC-CDMQ-4C",140,0),
    ]:
        doc.append("items",{"variable":vn,"default_value":dv,"sort_order":sr,"is_required":rq})
    _ins(doc)

def _accessory_set_4c():
    if _ex("AL Accessory Set","ACC-CDMQ-4C"): return
    doc = frappe.get_doc({"doctype":"AL Accessory Set","set_code":"ACC-CDMQ-4C",
        "set_name":"Bộ PK Cửa đi 4 cánh","product_type":"DOOR","variable_set":"VS-CDMQ-4C"})
    # ★ lookup_rule: số bản lề theo chiều cao (H_mm=3200 > 2700 → 4 bản lề/cánh)
    for s,ic,q,qf in [
        ("tay_nam","KL-MZS20",4,""),
        ("khoa","KL-KHOA-01",1,""),
        ("ban_le","KL-T-MJ06",0,"lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel"),
    ]:
        doc.append("items",{"slug":s,"item_code":ic,"qty":q,"qty_formula":qf})
    _ins(doc)

def _bom_items_and_set_4c():
    if _ex("AL Bom Set","BS-CDMQ-4C"): return
    import json
    doc = frappe.get_doc({"doctype":"AL Bom Set","set_code":"BS-CDMQ-4C",
        "set_name":"Cửa đi 4 cánh + 2 transom + sidelite",
        "product_type":"DOOR","profile_system":"XINGFA_55",
        "variable_set":"VS-CDMQ-4C","default_accessory_set":"ACC-CDMQ-4C",
        "formula_fieldnames":json.dumps(["width","height","qty","show_condition",
            "item_condition_formula","rule_input_expr"])})

    # Định nghĩa 22 Bom Items
    # Format: (slug, mode, item_code, width, height, qty, calc_pattern, cost_bucket, price_type, price_base_item)
    items = [
        # ── KHUNG BAO (4 dòng) ────────────────────────────────────
        ("khung_ngang_tren","Fixed","XF55-KB-20","W_mm","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("khung_ngang_duoi","Fixed","XF55-KB-20","W_mm","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("khung_dung_trai","Fixed","XF55-KB-20","H_mm","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("khung_dung_phai","Fixed","XF55-KB-20","H_mm","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        # ── ĐỐ NGANG (2 dòng) ─────────────────────────────────────
        ("do_ngang_tren","Fixed","XF55-KB-20","W_mm - 2*OFFSET_DO_NGANG","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("do_ngang_duoi","Fixed","XF55-KB-20","W_mm - 2*OFFSET_DO_NGANG","","1","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        # ── CÁNH ĐỨNG (4 cánh) ────────────────────────────────────
        ("canh_dung_c1","Fixed","XF55-CANH-20","(H_mm - TransomHeightTop - TransomHeightBottom) - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_dung_c2","Fixed","XF55-CANH-20","(H_mm - TransomHeightTop - TransomHeightBottom) - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_dung_c3","Fixed","XF55-CANH-20","(H_mm - TransomHeightTop - TransomHeightBottom) - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_dung_c4","Fixed","XF55-CANH-20","(H_mm - TransomHeightTop - TransomHeightBottom) - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        # ── CÁNH NGANG (4 cánh) ────────────────────────────────────
        ("canh_ngang_c1","Fixed","XF55-CANH-20","W_mm/n_panel - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_ngang_c2","Fixed","XF55-CANH-20","W_mm/n_panel - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_ngang_c3","Fixed","XF55-CANH-20","W_mm/n_panel - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("canh_ngang_c4","Fixed","XF55-CANH-20","W_mm/n_panel - OFFSET_FRAME","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        # ── KÍNH (4 dòng) ─────────────────────────────────────────
        ("kinh_fixed_top","Fixed","KINH-LOWE-24","W_mm - 2*OFFSET_FIXED","TransomHeightTop - OFFSET_FIXED","1","AREA","VL_KINH","Fixed",""),
        ("kinh_fixed_bottom","Fixed","KINH-LOWE-24","W_mm - 2*OFFSET_FIXED","TransomHeightBottom - OFFSET_FIXED","1","AREA","VL_KINH","Fixed",""),
        ("kinh_canh","Fixed","KINH-LOWE-24","W_mm/n_panel - OFFSET_GLASS","(H_mm - TransomHeightTop - TransomHeightBottom) - OFFSET_GLASS","n_panel","AREA","VL_KINH","Fixed",""),
        ("kinh_sidelite","Fixed","KINH-LOWE-24","SideLiteWidth - 2*OFFSET_FIXED","SideLiteHeight - 2*OFFSET_FIXED","1","AREA","VL_KINH","Fixed",""),
        # ── NẸP KÍNH (2 dòng — Rule-based: chọn nẹp theo glass_thick) ──
        ("nep_kinh_canh","Rule","","2*(items.kinh_canh.width + items.kinh_canh.height)","","2*n_panel","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        ("nep_kinh_sidelite","Rule","","2*(items.kinh_sidelite.width + items.kinh_sidelite.height)","","2","LENGTH_TO_WEIGHT","VL_NHOM","Item Price","NHOM-XINGFA"),
        # ── KEO (2 dòng — Rule-based: chọn keo theo glass_type) ──
        ("keo_canh","Rule","","2*(items.kinh_canh.width + items.kinh_canh.height)","","n_panel","LENGTH_ONLY","VL_VTP","Fixed",""),
        ("keo_sidelite","Rule","","2*(items.kinh_sidelite.width + items.kinh_sidelite.height)","","1","LENGTH_ONLY","VL_VTP","Fixed",""),
    ]

    for s,mode,ic,w,h,q,calc,bkt,ptype,pbi in items:
        cat = frappe.db.get_value("AL Slug Library",s,"category")
        row = {"slug":s,"category":cat,"item_selection_mode":mode,
            "item_code":ic or None,"width":w or None,"height":h or None,
            "qty":q,"calc_pattern":calc,"cost_bucket":bkt,
            "price_type":ptype,"price_base_item":pbi or None}
        if mode == "Rule":
            row["item_rule"] = "RULE-NEP-GLASSTHICK" if "nep" in s else "RULE-KEO-GLASSTYPE"
            target_glass = "kinh_canh" if "canh" in s else "kinh_sidelite"
            row["rule_input_expr"] = f"items.{target_glass}.{'glass_thick' if 'nep' in s else 'glass_type'}"
        if s in ("kinh_fixed_top","kinh_fixed_bottom","kinh_canh","kinh_sidelite"):
            row["default_glass_master"] = "KINH-LOWE-24"
            row["ctx_inject_prefix"] = s
        doc.append("items",row)

    # Thêm gioăng + vít (Fixed, không formula complex)
    for s,ic,w,h,q,calc,bkt,ptype,pbi in [
        ("gioang","GIO-EPDM-55","items.khung_ngang_tren.width + items.khung_ngang_duoi.width + 2*items.khung_dung_trai.width","","1","LENGTH_ONLY","VL_VTP","Fixed",""),
        ("vit","VIT-TK-35X16","","","15*n_panel + 20","COUNT","VL_VTP","Fixed",""),
    ]:
        cat = frappe.db.get_value("AL Slug Library",s,"category")
        doc.append("items",{"slug":s,"category":cat,"item_selection_mode":"Fixed",
            "item_code":ic,"width":w or None,"height":h or None,
            "qty":q,"calc_pattern":calc,"cost_bucket":bkt,
            "price_type":ptype,"price_base_item":pbi or None})
    _ins(doc)

def _bom_4c():
    if not _ex("AL BOM","BOM-CDMQ-4C"):
        _ins(frappe.get_doc({"doctype":"AL BOM","bom_code":"BOM-CDMQ-4C",
            "bom_name":"Cửa đi 4 cánh mở quay + 2 ô kính + vách kính",
            "product_type":"DOOR","brand":"XINGFA",
            "representative_item":"NHOM-XINGFA",
            "bom_set":"BS-CDMQ-4C","default_cost_template":"CT-01-STANDARD"}))

def _bom_version_4c():
    if not _ex("AL BOM Version",{"bom":"BOM-CDMQ-4C","version_name":"v1.0"}):
        _ins(frappe.get_doc({"doctype":"AL BOM Version","bom":"BOM-CDMQ-4C",
            "version_name":"v1.0","valid_from":now(),"workflow_state":"Published"}))


def cleanup_cdmq_4c():
    """Xóa toàn bộ records CDMQ-4C để re-seed."""
    import frappe
    # Xóa theo thứ tự: Version → BOM → Bom Set → Variable Set → Accessory Set
    for dt, filters in [
        ("AL BOM Version", {"bom": "BOM-CDMQ-4C"}),
        ("AL BOM", {"bom_code": "BOM-CDMQ-4C"}),
        ("AL Bom Set", {"set_code": "BS-CDMQ-4C"}),
        ("AL Variable Set", {"set_code": "VS-CDMQ-4C"}),
        ("AL Accessory Set", {"set_code": "ACC-CDMQ-4C"}),
    ]:
        for name in frappe.db.get_all(dt, filters=filters, pluck="name"):
            try:
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
                print(f"  Deleted {dt}: {name}")
            except Exception as e:
                print(f"  Skip {dt}: {e}")
    frappe.db.commit()
    print("Cleanup CDMQ-4C complete")
