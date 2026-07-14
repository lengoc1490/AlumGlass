# alumglass/formula_utils/calculations.py
# Hàm tiện ích thuần (pure functions) — dùng để xây dựng context cho FormulaEngine
# hoặc tính nhanh độc lập không cần engine.

# =============================================================================
# 1. KÍNH
# =============================================================================

def glass_area_m2(W_mm, H_mm, qty=1):
    """Diện tích kính (m²) từ kích thước mm."""
    return float(W_mm) * float(H_mm) / 1_000_000 * float(qty)


def glass_price(W_mm, H_mm, unit_price_per_m2, qty=1, cut_fee_pct=0):
    """Tính giá 1 tấm kính."""
    area = glass_area_m2(W_mm, H_mm, qty)
    price = area * unit_price_per_m2
    cut = price * cut_fee_pct / 100
    return {"area_m2": round(area, 6), "price": round(price, 0),
            "cut_fee": round(cut, 0), "total": round(price + cut, 0)}


def glass_perimeter_m(W_mm, H_mm):
    """Chu vi kính (m)."""
    return (float(W_mm) + float(H_mm)) / 1000 * 2


def glass_weight_kg(area_m2, thickness_mm):
    """Trọng lượng kính (kg). Tỷ trọng kính ≈ 2.5 kg/m²/mm."""
    return area_m2 * thickness_mm * 2.5


# =============================================================================
# 2. NHÔM
# =============================================================================

def aluminum_weight_kg(length_m, kg_per_m, qty=1):
    """Trọng lượng nhôm (kg)."""
    return float(length_m) * float(kg_per_m) * float(qty)


def aluminum_price(length_m, kg_per_m, unit_price_per_kg, qty=1):
    """Giá 1 thanh/profile nhôm."""
    w = aluminum_weight_kg(length_m, kg_per_m, qty)
    return {"weight_kg": round(w, 3), "price": round(w * unit_price_per_kg, 0)}


def aluminum_cut_efficiency(total_cut_mm, bar_len_mm=6000, kerf_mm=3):
    """Hiệu suất cắt nhôm. Trả về {bars, scrap_mm, scrap_pct, efficiency_pct}."""
    effective = bar_len_mm - kerf_mm
    bars = max(1, int((total_cut_mm + effective - 1) / effective))
    total_stock = bars * bar_len_mm
    scrap = bars * effective - total_cut_mm
    return {
        "bars_needed": bars,
        "scrap_mm": round(scrap, 1),
        "scrap_pct": round(scrap / total_stock * 100, 2) if total_stock else 0,
        "efficiency_pct": round((1 - scrap / total_stock) * 100, 2) if total_stock else 100,
    }


# =============================================================================
# 3. LOOKUP
# =============================================================================

def lookup_aluminum_price(brand, color="STD", table=None):
    """Tra đơn giá nhôm (đ/kg) theo brand + màu."""
    if table is None:
        from .calculations import _DEFAULT_AL_PRICES
        table = _DEFAULT_AL_PRICES
    return float(table.get((brand, color), table.get((brand, "STD"), 0)))


def lookup_glass_price(glass_code, table=None):
    """Tra đơn giá kính (đ/m²)."""
    if table is None:
        from .calculations import _DEFAULT_GLASS_PRICES
        table = _DEFAULT_GLASS_PRICES
    return float(table.get(glass_code, 0))


_DEFAULT_AL_PRICES = {
    ("XF-NK", "STD"): 113_000, ("XF-NK", "DAK"): 118_000, ("XF-NK", "VG"): 125_000,
    ("ALUMIL", "STD"): 135_000, ("ALUMIL", "DAK"): 142_000, ("ALUMIL", "VG"): 155_000,
    ("YONGQIANG", "STD"): 95_000, ("YONGQIANG", "DAK"): 100_000,
}

_DEFAULT_GLASS_PRICES = {
    "KINH-DON-8": 250_000, "KINH-DON-10": 320_000, "KINH-DON-12": 400_000,
    "KINH-CL-8": 420_000, "KINH-CL-10": 550_000, "KINH-CL-12": 650_000,
    "KINH-HOP-16": 580_000, "KINH-HOP-20": 680_000, "KINH-HOP-24": 820_000,
    "KINH-LOWE-24": 1_150_000,
}


# =============================================================================
# 4. TÍNH NHANH (KHÔNG CẦN FORMULA ENGINE)
# =============================================================================

def quick_quote(W_mm, H_mm, n_canh=2, qty=1, brand="XF-NK", color="STD",
                glass_code="KINH-CL-10", **kw):
    """Tính nhanh báo giá 1 sản phẩm nhôm kính — không cần DB, không cần Engine.

    Returns:
        dict với GIA_BAN, DON_GIA_M2, GIA_VAT và meta (diện tích kính, kg nhôm...)
    """
    W_m = W_mm / 1000
    H_m = H_mm / 1000
    tong_m2 = W_m * H_m * qty

    don_gia_nhom = lookup_aluminum_price(brand, color)
    don_gia_kinh = lookup_glass_price(glass_code)

    nc_sx_pct = kw.get("nc_sx_pct", 0.12)
    nc_ld_rate = kw.get("nc_ld_rate", 180000)
    oh_hh_pct = kw.get("oh_hh_pct", 0.02)
    oh_vc_pct = kw.get("oh_vc_pct", 0.03)
    oh_bh_pct = kw.get("oh_bh_pct", 0.01)
    profit_pct = kw.get("profit_pct", 0.15)
    vat_pct = kw.get("vat_pct", 0.10)

    # Nhôm: chiều dài × kg/m ước tính
    lengths = [
        ("khung_dung",   H_m * 2,               1.257),
        ("khung_ngang",  W_m + 0.043*2,         1.257),
        ("canh_dung",   (H_m - 0.043*2) * n_canh, 1.105),
        ("canh_ngang",  (W_m/n_canh - 0.043*2) * n_canh, 1.105),
        ("nep_dung",    (H_m - 0.043*2) * n_canh * 2, 0.198),
        ("nep_ngang",   (W_m/n_canh - 0.043*2) * n_canh * 2, 0.198),
    ]
    al_kg = sum(length * qty * kpm for _, length, kpm in lengths)
    vl_nhom = al_kg * don_gia_nhom

    # Kính
    kinh_w = W_mm - 86
    kinh_h = H_mm - 86
    kinh_m2 = glass_area_m2(kinh_w, kinh_h, 1)
    vl_kinh = kinh_m2 * don_gia_kinh

    # VTP + PK ước tính
    vl_vtp = (vl_nhom + vl_kinh) * 0.05
    vl_pk = n_canh * (45000*3 + 120000) + 350000 + 25000

    # Tính giá thành (giải tuần tự, không có circular dependency)
    tong_vl = vl_nhom + vl_kinh + vl_vtp + vl_pk
    nc_sx = tong_vl * nc_sx_pct
    nc_ld = tong_m2 * nc_ld_rate if tong_m2 > 0 else 0
    tong_nc = nc_sx + nc_ld
    oh_hh = tong_vl * oh_hh_pct
    oh_vc = tong_vl * oh_vc_pct
    gia_thanh_temp = tong_vl + tong_nc + oh_hh + oh_vc
    oh_bh = gia_thanh_temp * oh_bh_pct
    tong_oh = oh_hh + oh_vc + oh_bh
    gia_thanh = tong_vl + tong_nc + tong_oh
    profit = gia_thanh * profit_pct
    gia_ban = gia_thanh + profit
    don_gia_m2 = gia_ban / tong_m2 if tong_m2 > 0 else 0
    gia_vat = gia_ban * (1 + vat_pct)

    return {
        "GIA_THANH": round(gia_thanh, 0), "GIA_BAN": round(gia_ban, 0),
        "DON_GIA_M2": round(don_gia_m2, 0), "GIA_VAT": round(gia_vat, 0),
        "TONG_VL": round(tong_vl, 0), "VL_NHOM": round(vl_nhom, 0),
        "VL_KINH": round(vl_kinh, 0), "VL_VTP": round(vl_vtp, 0),
        "VL_PK": round(vl_pk, 0), "TONG_M2": round(tong_m2, 4),
        "meta": {
            "W_mm": W_mm, "H_mm": H_mm, "n_canh": n_canh, "qty": qty,
            "brand": brand, "color": color, "glass_code": glass_code,
            "don_gia_nhom": don_gia_nhom, "don_gia_kinh": don_gia_kinh,
            "glass_area_m2": round(kinh_m2, 6), "aluminum_kg": round(al_kg, 3),
        },
    }


# =============================================================================
# 5. PHÂN TÍCH LỢI NHUẬN
# =============================================================================

def analyze_margin(gia_ban, gia_thanh, target_pct=15.0):
    """Phân tích biên lợi nhuận."""
    profit = gia_ban - gia_thanh
    margin = profit / gia_ban * 100 if gia_ban > 0 else 0
    meets = margin >= target_pct
    if not meets and gia_thanh > 0:
        need = gia_thanh / (1 - target_pct/100)
        hint = f"Cần giá bán tối thiểu {need:,.0f}đ để đạt margin {target_pct}%"
    else:
        hint = f"Đạt margin mục tiêu ({margin:.1f}% >= {target_pct}%)"
    return {"profit": round(profit, 0), "margin_pct": round(margin, 2),
            "meets_target": meets, "hint": hint}


# =============================================================================
# 6. FORMAT
# =============================================================================

def fmt_vnd(value):
    """Format số → chuỗi tiền VND."""
    return f"{value:,.0f}".replace(",", ".")
