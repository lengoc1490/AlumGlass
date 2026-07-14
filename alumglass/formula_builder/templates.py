# alumglass/formula_builder/templates.py
# Bộ công thức mẫu cho ngành Nhôm Kính — dùng trực tiếp với FormulaEngine
#
# Pattern (giống hệt các ví dụ formula_builder):
#   from formula_builder.formula_utils import FormulaEngine
#   engine = FormulaEngine(formulas=FORMULA_SET, on_error="default", default_value=0)
#   result = engine.calculate(inputs_dict)
#   print(result["GIA_BAN"])

# =============================================================================
# 1. CÔNG THỨC TÍNH SỐ LƯỢNG THANH NHÔM (Profile QTY)
# =============================================================================
# Các biến đầu vào cần có: W_m, H_m, qty, n_canh
# Các biến kg_per_m được inject vào context từ Item.al_kg_per_m

FORMULAS_KHUNG_DUNG = [
    {"name": "khung_dung_active", "formula": "True"},
    {"name": "khung_dung_qty",   "formula": "H_m * 2 * qty"},
    {"name": "khung_dung_kg",    "formula": "khung_dung_kg_per_m"},
    {"name": "khung_dung_dg",    "formula": "don_gia_nhom"},
    {"name": "khung_dung_tt",    "formula": "khung_dung_qty * khung_dung_kg * khung_dung_dg"},
]

FORMULAS_KHUNG_NGANG = [
    {"name": "khung_ngang_active", "formula": "True"},
    {"name": "khung_ngang_qty",   "formula": "(W_m + 0.043*2) * qty"},
    {"name": "khung_ngang_kg",    "formula": "khung_ngang_kg_per_m"},
    {"name": "khung_ngang_dg",    "formula": "don_gia_nhom"},
    {"name": "khung_ngang_tt",    "formula": "khung_ngang_qty * khung_ngang_kg * khung_ngang_dg"},
]

FORMULAS_CANH_DUNG = [
    {"name": "canh_dung_active", "formula": "n_canh >= 1"},
    {"name": "canh_dung_qty",   "formula": "(H_m - 0.043*2) * n_canh * qty"},
    {"name": "canh_dung_kg",    "formula": "canh_dung_kg_per_m"},
    {"name": "canh_dung_dg",    "formula": "don_gia_nhom"},
    {"name": "canh_dung_tt",    "formula": "canh_dung_qty * canh_dung_kg * canh_dung_dg"},
]

FORMULAS_CANH_NGANG = [
    {"name": "canh_ngang_active", "formula": "n_canh >= 1"},
    {"name": "canh_ngang_qty",   "formula": "(W_m / n_canh - 0.043*2) * n_canh * qty"},
    {"name": "canh_ngang_kg",    "formula": "canh_ngang_kg_per_m"},
    {"name": "canh_ngang_dg",    "formula": "don_gia_nhom"},
    {"name": "canh_ngang_tt",    "formula": "canh_ngang_qty * canh_ngang_kg * canh_ngang_dg"},
]

FORMULAS_NEP = [
    {"name": "nep_dung_active", "formula": "True"},
    {"name": "nep_dung_qty",   "formula": "(H_m - 0.043*2) * n_canh * qty * 2"},
    {"name": "nep_dung_kg",    "formula": "nep_dung_kg_per_m"},
    {"name": "nep_dung_dg",    "formula": "don_gia_nhom"},
    {"name": "nep_dung_tt",    "formula": "nep_dung_qty * nep_dung_kg * nep_dung_dg"},

    {"name": "nep_ngang_active", "formula": "True"},
    {"name": "nep_ngang_qty",   "formula": "(W_m / n_canh - 0.043*2) * n_canh * qty * 2"},
    {"name": "nep_ngang_kg",    "formula": "nep_ngang_kg_per_m"},
    {"name": "nep_ngang_dg",    "formula": "don_gia_nhom"},
    {"name": "nep_ngang_tt",    "formula": "nep_ngang_qty * nep_ngang_kg * nep_ngang_dg"},
]

# =============================================================================
# 2. CÔNG THỨC TÍNH KÍNH (Glass Panel)
# =============================================================================
# Biến: {prefix}_W, {prefix}_H được tính từ W_mm, H_mm trừ offset
# glass_thick_{prefix} được inject vào context từ Glass Master

def build_glass_formulas(prefix, width_formula, height_formula, qty_formula="1",
                          dg_source="don_gia_kinh", cut_fee_pct=0, panel_count=1):
    """Sinh công thức tính kính cho 1 prefix (hỗ trợ multi-panel).

    Args:
        prefix: Tiền tố tên biến (vd: 'kinh_canh')
        width_formula: Công thức tính chiều rộng (vd: 'W_mm - 86')
        height_formula: Công thức tính chiều cao (vd: 'H_mm - 86')
        qty_formula: Công thức tính số lượng mỗi panel
        dg_source: Nguồn đơn giá (tên biến trong context hoặc số)
        cut_fee_pct: % phí cắt kính
        panel_count: Số panel (1 = đơn, >1 = multi-panel như vách nhiều ô)

    Returns:
        List[dict]: danh sách {name, formula}
    """
    formulas = []

    if panel_count == 1:
        p = prefix
        formulas += [
            {"name": f"{p}_W",            "formula": width_formula},
            {"name": f"{p}_H",            "formula": height_formula},
            {"name": f"{p}_glass_thick",  "formula": f"glass_thick_{prefix}"},
            {"name": f"{p}_qty",          "formula": qty_formula},
            {"name": f"{p}_m2",           "formula": f"{p}_W * {p}_H / 1000000 * {p}_qty"},
            {"name": f"{p}_dg",           "formula": str(dg_source)},
            {"name": f"{p}_tt",           "formula": f"{p}_m2 * {p}_dg"},
            {"name": f"{p}_cut",          "formula": f"{p}_tt * {cut_fee_pct / 100:.6f}"},
            {"name": f"{p}_perimeter_m",  "formula": f"({p}_W + {p}_H) / 1000"},
        ]
        # Tổng hợp
        formulas += [
            {"name": f"{prefix}_total_perimeter_m", "formula": f"{p}_perimeter_m"},
            {"name": f"{prefix}_total_m2",          "formula": f"{p}_m2"},
            {"name": f"{prefix}_total_qty",         "formula": f"{p}_qty"},
        ]
    else:
        # Multi-panel: mỗi panel có chỉ số 0..N-1
        for i in range(panel_count):
            p = f"{prefix}_{i}"
            formulas += [
                {"name": f"{p}_W",            "formula": width_formula},
                {"name": f"{p}_H",            "formula": height_formula},
                {"name": f"{p}_glass_thick",  "formula": f"glass_thick_{prefix}"},
                {"name": f"{p}_qty",          "formula": qty_formula},
                {"name": f"{p}_m2",           "formula": f"{p}_W * {p}_H / 1000000 * {p}_qty"},
                {"name": f"{p}_dg",           "formula": str(dg_source)},
                {"name": f"{p}_tt",           "formula": f"{p}_m2 * {p}_dg"},
                {"name": f"{p}_cut",          "formula": f"{p}_tt * {cut_fee_pct / 100:.6f}"},
            ]

        # Tổng hợp từ tất cả panel
        perim_parts = [f"({prefix}_{i}_W + {prefix}_{i}_H) / 1000" for i in range(panel_count)]
        m2_parts = [f"{prefix}_{i}_m2" for i in range(panel_count)]
        tt_parts = [f"{prefix}_{i}_tt" for i in range(panel_count)]
        cut_parts = [f"{prefix}_{i}_cut" for i in range(panel_count)]
        thick_parts = [f"{prefix}_{i}_glass_thick" for i in range(panel_count)]

        formulas += [
            {"name": f"{prefix}_total_perimeter_m", "formula": " + ".join(perim_parts)},
            {"name": f"{prefix}_total_m2",          "formula": " + ".join(m2_parts)},
            {"name": f"{prefix}_tt",                "formula": " + ".join(tt_parts)},
            {"name": f"{prefix}_cut",               "formula": " + ".join(cut_parts)},
            {"name": f"max_glass_thick_{prefix}",   "formula": f"max({','.join(thick_parts)})"},
        ]

    return formulas


# =============================================================================
# 3. CÔNG THỨC GOM NHÓM CHI PHÍ (Cost Buckets)
# =============================================================================
# Gom các biến _{slug}_tt hoặc _{prefix}_tt vào các bucket

def build_bucket_formulas(bucket_map):
    """Sinh công thức gom bucket từ dict {bucket_code: [var_names]}.

    Args:
        bucket_map: dict, key = mã bucket (VL_NHOM, VL_KINH...),
                    value = list tên biến thành tiền cần gom

    Returns:
        List[dict]: [{name: bucket_code, formula: "var1 + var2 + ..."}]
    """
    formulas = []
    for bucket_code, var_list in bucket_map.items():
        if var_list:
            formulas.append({
                "name": bucket_code,
                "formula": " + ".join(var_list),
            })
    return formulas


# =============================================================================
# 4. COST TEMPLATE — TỪ BUCKET ĐẾN GIÁ BÁN
# =============================================================================
# Đây là bộ công thức tính giá thành → giá bán → giá VAT
# Dùng sau khi đã có các bucket VL_NHOM, VL_KINH, VL_VTP, VL_PK, OH_CUT_KINH
# Context cần có: nc_sx_pct, nc_ld_rate, oh_hh_pct, oh_vc_pct, oh_bh_pct,
#                 profit_pct, vat_pct, TONG_M2

FORMULAS_COST_TEMPLATE = [
    # Vật liệu
    {"name": "TONG_VL",    "formula": "VL_NHOM + VL_KINH + VL_VTP + VL_PK"},

    # Nhân công
    {"name": "NC_SX",      "formula": "TONG_VL * nc_sx_pct"},
    {"name": "NC_LD",      "formula": "TONG_M2 * nc_ld_rate"},
    {"name": "TONG_NC",    "formula": "NC_SX + NC_LD"},

    # Overhead
    {"name": "OH_HH",      "formula": "TONG_VL * oh_hh_pct"},
    {"name": "OH_VC",      "formula": "TONG_VL * oh_vc_pct"},
    # OH_CUT_KINH đến từ bucket (đã gom từ các dòng kính)
    # OH_BH tính từ GIA_THANH_TEMP để tránh vòng lặp GIA_THANH → OH_BH → TONG_OH → GIA_THANH
    {"name": "GIA_THANH_TEMP", "formula": "TONG_VL + TONG_NC + OH_HH + OH_CUT_KINH + OH_VC"},
    {"name": "OH_BH",      "formula": "GIA_THANH_TEMP * oh_bh_pct"},
    {"name": "TONG_OH",    "formula": "OH_HH + OH_CUT_KINH + OH_VC + OH_BH"},

    # Tổng hợp giá
    {"name": "GIA_THANH",  "formula": "TONG_VL + TONG_NC + TONG_OH"},
    {"name": "PROFIT",     "formula": "GIA_THANH * profit_pct"},
    {"name": "GIA_BAN",    "formula": "GIA_THANH + PROFIT"},
    {"name": "DON_GIA_M2", "formula": "safe_div(GIA_BAN, TONG_M2, 0)"},
    {"name": "GIA_VAT",    "formula": "GIA_BAN * (1 + vat_pct)"},
]

# =============================================================================
# 5. CÔNG THỨC TỔNG HỢP TOÀN DỰ ÁN (Project P&L)
# =============================================================================
# Context: các list all_vl_nhom, all_vl_kinh, ... từ từng hạng mục

FORMULAS_PROJECT = [
    {"name": "TOTAL_VL_NHOM",   "formula": "sum(v for v in all_vl_nhom)"},
    {"name": "TOTAL_VL_KINH",   "formula": "sum(v for v in all_vl_kinh)"},
    {"name": "TOTAL_VL_VTP",    "formula": "sum(v for v in all_vl_vtp)"},
    {"name": "TOTAL_VL_PK",     "formula": "sum(v for v in all_vl_pk)"},
    {"name": "TOTAL_VL",        "formula": "TOTAL_VL_NHOM + TOTAL_VL_KINH + TOTAL_VL_VTP + TOTAL_VL_PK"},

    {"name": "TOTAL_NC_SX",     "formula": "sum(v for v in all_nc_sx)"},
    {"name": "TOTAL_NC_LD",     "formula": "sum(v for v in all_nc_ld)"},
    {"name": "TOTAL_NC",        "formula": "TOTAL_NC_SX + TOTAL_NC_LD"},

    {"name": "TOTAL_OH",        "formula": "sum(v for v in all_oh)"},
    {"name": "TOTAL_REVENUE",   "formula": "sum(v for v in all_gia_ban)"},
    {"name": "TOTAL_REVENUE_VAT","formula": "sum(v for v in all_gia_vat)"},
    {"name": "TOTAL_M2",        "formula": "sum(v for v in all_m2)"},

    {"name": "TOTAL_GIA_THANH", "formula": "TOTAL_VL + TOTAL_NC + TOTAL_OH"},
    {"name": "TOTAL_PROFIT",    "formula": "TOTAL_REVENUE - TOTAL_GIA_THANH"},
    {"name": "MARGIN_PCT",      "formula": "safe_div(TOTAL_PROFIT * 100, TOTAL_REVENUE, 0)"},
    {"name": "TOTAL_GIA_VAT",   "formula": "TOTAL_REVENUE * (1 + vat_pct)"},
    {"name": "AVG_DON_GIA_M2",  "formula": "safe_div(TOTAL_REVENUE, TOTAL_M2, 0)"},
]

# =============================================================================
# 6. CÔNG THỨC PHÂN TÍCH BIẾN ĐỘNG CHI PHÍ (Cost Variance)
# =============================================================================
# Context: EST_VL, ACTUAL_VL, EST_NC, ACTUAL_NC, EST_OH, ACTUAL_OH, variance_threshold

FORMULAS_COST_VARIANCE = [
    {"name": "VARIANCE_VL",      "formula": "ACTUAL_VL - EST_VL"},
    {"name": "VARIANCE_VL_PCT",  "formula": "safe_div(VARIANCE_VL * 100, EST_VL, 0)"},
    {"name": "VARIANCE_NC",      "formula": "ACTUAL_NC - EST_NC"},
    {"name": "VARIANCE_NC_PCT",  "formula": "safe_div(VARIANCE_NC * 100, EST_NC, 0)"},
    {"name": "VARIANCE_OH",      "formula": "ACTUAL_OH - EST_OH"},
    {"name": "VARIANCE_OH_PCT",  "formula": "safe_div(VARIANCE_OH * 100, EST_OH, 0)"},

    {"name": "EST_TOTAL",        "formula": "EST_VL + EST_NC + EST_OH"},
    {"name": "ACTUAL_TOTAL",     "formula": "ACTUAL_VL + ACTUAL_NC + ACTUAL_OH"},
    {"name": "VARIANCE_TOTAL",   "formula": "ACTUAL_TOTAL - EST_TOTAL"},
    {"name": "VARIANCE_TOTAL_PCT","formula": "safe_div(VARIANCE_TOTAL * 100, EST_TOTAL, 0)"},

    {"name": "IS_OVER_BUDGET",   "formula": "VARIANCE_TOTAL > 0"},
    {"name": "IS_CRITICAL",      "formula": "VARIANCE_TOTAL_PCT > variance_threshold"},
]

# =============================================================================
# 7. CÔNG THỨC TỐI ƯU CẮT NHÔM & KÍNH
# =============================================================================

FORMULAS_CUTTING_NHOM = [
    {"name": "stock_bar_length_mm",  "formula": "stock_bar_len"},
    {"name": "saw_kerf_mm",          "formula": "saw_kerf"},
    {"name": "effective_length_mm",  "formula": "stock_bar_length_mm - saw_kerf_mm"},
    {"name": "bars_needed",          "formula": "ceil(safe_div(total_cut_length_mm, effective_length_mm, 1))"},
    {"name": "total_stock_mm",       "formula": "bars_needed * stock_bar_length_mm"},
    {"name": "scrap_mm",             "formula": "total_stock_mm - total_cut_length_mm - bars_needed * saw_kerf_mm"},
    {"name": "scrap_pct",            "formula": "safe_div(scrap_mm * 100, total_stock_mm, 0)"},
    {"name": "has_reusable_offcut",  "formula": "scrap_mm >= min_offcut"},
    {"name": "efficiency_pct",       "formula": "100 - scrap_pct"},
]

FORMULAS_CUTTING_KINH = [
    {"name": "jumbo_w",          "formula": "jumbo_w_mm"},
    {"name": "jumbo_h",          "formula": "jumbo_h_mm"},
    {"name": "edge_trim",        "formula": "edge_trim_mm"},
    {"name": "usable_w",         "formula": "jumbo_w - 2 * edge_trim"},
    {"name": "usable_h",         "formula": "jumbo_h - 2 * edge_trim"},
    {"name": "sheet_area_m2",    "formula": "jumbo_w * jumbo_h / 1000000"},
    {"name": "estimated_sheets", "formula": "max(1, ceil(safe_div(total_glass_m2, sheet_area_m2, 1)))"},
    {"name": "waste_m2",         "formula": "estimated_sheets * sheet_area_m2 - total_glass_m2"},
    {"name": "waste_pct",        "formula": "safe_div(waste_m2 * 100, estimated_sheets * sheet_area_m2, 0)"},
]

# =============================================================================
# 8. THAM SỐ MẶC ĐỊNH NGÀNH
# =============================================================================

DEFAULT_PARAMS = {
    "nc_sx_pct": 0.12,
    "nc_ld_rate": 180000,
    "oh_hh_pct": 0.02,
    "oh_vc_pct": 0.03,
    "oh_bh_pct": 0.01,
    "profit_pct": 0.15,
    "vat_pct": 0.10,
    "variance_threshold": 15.0,
    "offset_w_mm": 86,
    "offset_h_mm": 86,
    "stock_bar_len": 6000,
    "saw_kerf": 3,
    "min_offcut": 300,
    "jumbo_w_mm": 3210,
    "jumbo_h_mm": 2250,
    "edge_trim_mm": 10,
}

# =============================================================================
# 9. KHỐI LƯỢNG NHÔM MẪU (kg/m) — Xingfa NK
# =============================================================================

PROFILE_KG_PER_M = {
    "C3318-20": 1.257,   # Khung bao đứng 2.0mm
    "C3317-20": 1.105,   # Cánh đứng 2.0mm
    "C3319-20": 1.006,   # Đố ngang 2.0mm
    "C3209-20": 0.198,   # Nẹp kính ≤10.38mm
    "C3210-20": 0.245,   # Nẹp kính 11-16mm
    "C3211-20": 0.312,   # Nẹp kính IGU >16mm
}

# =============================================================================
# 10. BẢNG GIÁ TRA CỨU MẪU
# =============================================================================

ALUMINUM_PRICE_TABLE = {
    ("XF-NK", "STD"): 113_000,
    ("XF-NK", "DAK"): 118_000,
    ("XF-NK", "VG"):  125_000,
    ("ALUMIL", "STD"): 135_000,
    ("ALUMIL", "DAK"): 142_000,
    ("ALUMIL", "VG"):  155_000,
    ("YONGQIANG", "STD"): 95_000,
    ("YONGQIANG", "DAK"): 100_000,
}

GLASS_PRICE_TABLE = {
    "KINH-DON-8":   250_000,
    "KINH-DON-10":  320_000,
    "KINH-DON-12":  400_000,
    "KINH-CL-8":    420_000,
    "KINH-CL-10":   550_000,
    "KINH-CL-12":   650_000,
    "KINH-HOP-16":  580_000,
    "KINH-HOP-20":  680_000,
    "KINH-HOP-24":  820_000,
    "KINH-LOWE-24": 1_150_000,
}
