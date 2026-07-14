# 01_bao_gia.py — Ví dụ tính báo giá cửa nhôm kính
# Cách chạy: python3 01_bao_gia.py
#
# PATTERN (giống hệt các ví dụ formula_builder):
#   1. Định nghĩa formulas = [{name, formula}, ...]
#   2. Tạo engine = FormulaEngine(formulas, on_error="default", default_value=0)
#   3. Tạo context dict chứa input
#   4. Gọi engine.calculate(context) → nhận kết quả
#   5. In/ xử lý kết quả

from formula_builder.formula_utils import FormulaEngine
from alumglass.formula_builder.templates import (
    FORMULAS_KHUNG_DUNG, FORMULAS_KHUNG_NGANG,
    FORMULAS_CANH_DUNG, FORMULAS_CANH_NGANG, FORMULAS_NEP,
    build_glass_formulas, build_bucket_formulas,
    FORMULAS_COST_TEMPLATE,
    DEFAULT_PARAMS, PROFILE_KG_PER_M,
    ALUMINUM_PRICE_TABLE, GLASS_PRICE_TABLE,
)
from alumglass.formula_utils import lookup_aluminum_price, lookup_glass_price, fmt_vnd

import sys, time
sys.stdout.reconfigure(encoding='utf-8')


# ═══════════════════════════════════════════════════════════════════════════
# 1. ĐỊNH NGHĨA FORMULAS — ghép tất cả các bộ công thức lại
# ═══════════════════════════════════════════════════════════════════════════

def build_all_formulas(W_mm, H_mm, n_canh, qty, don_gia_nhom, glass_code,
                       offset_w=86, offset_h=86):
    """Xây dựng danh sách formulas đầy đủ cho 1 sản phẩm."""

    don_gia_kinh = lookup_glass_price(glass_code, GLASS_PRICE_TABLE)

    formulas = []

    # ── Nhôm: ghép tất cả profile formulas ────────────────────────────
    for profile_set in [FORMULAS_KHUNG_DUNG, FORMULAS_KHUNG_NGANG,
                        FORMULAS_CANH_DUNG, FORMULAS_CANH_NGANG,
                        FORMULAS_NEP]:
        formulas.extend(profile_set)

    # ── Kính: dùng builder function ───────────────────────────────────
    glass_f = build_glass_formulas(
        prefix="kinh_canh",
        width_formula=f"W_mm - {offset_w}",
        height_formula=f"H_mm - {offset_h}",
        qty_formula="1",
        dg_source=str(don_gia_kinh),
        cut_fee_pct=0,
        panel_count=1,
    )
    formulas.extend(glass_f)

    # ── VTP (vật tư phụ) — công thức trực tiếp ────────────────────────
    formulas.extend([
        {"name": "gioang_qty",  "formula": "kinh_canh_total_perimeter_m * qty * 2"},
        {"name": "gioang_dg",   "formula": "5000"},
        {"name": "gioang_tt",   "formula": "gioang_qty * gioang_dg"},

        {"name": "keo_qty",     "formula": "kinh_canh_total_perimeter_m * qty * 0.025"},
        {"name": "keo_dg",      "formula": "30000"},
        {"name": "keo_tt",      "formula": "keo_qty * keo_dg"},

        {"name": "vit_qty",     "formula": "(n_canh * 8 + 12) * qty"},
        {"name": "vit_dg",      "formula": "500"},
        {"name": "vit_tt",      "formula": "vit_qty * vit_dg"},

        {"name": "xop_qty",     "formula": "kinh_canh_total_perimeter_m * qty"},
        {"name": "xop_dg",      "formula": "2000"},
        {"name": "xop_tt",      "formula": "xop_qty * xop_dg"},
    ])

    # ── PK (phụ kiện) — công thức trực tiếp ───────────────────────────
    formulas.extend([
        {"name": "ban_le_qty",  "formula": "n_canh * 3 * qty"},
        {"name": "ban_le_dg",   "formula": "45000"},
        {"name": "ban_le_tt",   "formula": "ban_le_qty * ban_le_dg"},

        {"name": "khoa_qty",    "formula": "1 * qty"},
        {"name": "khoa_dg",     "formula": "350000"},
        {"name": "khoa_tt",     "formula": "khoa_qty * khoa_dg"},

        {"name": "tay_nam_qty", "formula": "n_canh * qty"},
        {"name": "tay_nam_dg",  "formula": "120000"},
        {"name": "tay_nam_tt",  "formula": "tay_nam_qty * tay_nam_dg"},

        {"name": "chan_chong_qty", "formula": "qty"},
        {"name": "chan_chong_dg",  "formula": "25000"},
        {"name": "chan_chong_tt",  "formula": "chan_chong_qty * chan_chong_dg"},
    ])

    # ── Gom buckets ─────────────────────────────────────────────────
    bucket_map = {
        "VL_NHOM": [
            "khung_dung_tt", "khung_ngang_tt",
            "canh_dung_tt", "canh_ngang_tt",
            "nep_dung_tt", "nep_ngang_tt",
        ],
        "VL_KINH": ["kinh_canh_tt"],
        "VL_VTP":  ["gioang_tt", "keo_tt", "vit_tt", "xop_tt"],
        "VL_PK":   ["ban_le_tt", "khoa_tt", "tay_nam_tt", "chan_chong_tt"],
        "OH_CUT_KINH": ["kinh_canh_cut"],
    }
    formulas.extend(build_bucket_formulas(bucket_map))

    # ── Cost template ────────────────────────────────────────────────
    formulas.extend(FORMULAS_COST_TEMPLATE)

    return formulas


# ═══════════════════════════════════════════════════════════════════════════
# 2. TẠO ENGINE + CONTEXT → TÍNH → KẾT QUẢ
# ═══════════════════════════════════════════════════════════════════════════

def tinh_bao_gia(W_mm=1200, H_mm=2200, n_canh=2, qty=1,
                 brand="XF-NK", color="STD", glass_code="KINH-CL-10",
                 print_detail=True):
    """Tính báo giá 1 sản phẩm — đúng pattern FormulaEngine."""

    # ── Bước 1: Định nghĩa formulas ──────────────────────────────────
    don_gia_nhom = lookup_aluminum_price(brand, color, ALUMINUM_PRICE_TABLE)
    formulas = build_all_formulas(W_mm, H_mm, n_canh, qty, don_gia_nhom, glass_code)

    # ── Bước 2: Tạo engine ───────────────────────────────────────────
    engine = FormulaEngine(
        formulas=formulas,
        on_error="raise",
        default_value=0,
        deterministic=True,
    )

    # ── Bước 3: Tạo context (inputs dict) ─────────────────────────────
    W_m = W_mm / 1000
    H_m = H_mm / 1000

    ctx = {
        # Kích thước
        "W_mm": W_mm, "H_mm": H_mm, "W_m": W_m, "H_m": H_m,
        "qty": qty, "n_canh": n_canh,
        # Đơn giá
        "don_gia_nhom": don_gia_nhom,
        # kg/m cho từng profile (từ Item master)
        "khung_dung_kg_per_m": 1.257,
        "khung_ngang_kg_per_m": 1.257,
        "canh_dung_kg_per_m": 1.105,
        "canh_ngang_kg_per_m": 1.105,
        "nep_dung_kg_per_m": 0.198,
        "nep_ngang_kg_per_m": 0.198,
        # Kính
        "glass_thick_kinh_canh": 10.0,
        # Tham số cost template
        "TONG_M2": W_m * H_m * qty,
        "nc_sx_pct": 0.12, "nc_ld_rate": 180_000,
        "oh_hh_pct": 0.02, "oh_vc_pct": 0.03,
        "oh_bh_pct": 0.01, "profit_pct": 0.15, "vat_pct": 0.10,
    }

    # ── Bước 4: Tính toán ────────────────────────────────────────────
    t0 = time.perf_counter()
    result = engine.calculate(ctx)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # ── Bước 5: In kết quả ───────────────────────────────────────────
    if print_detail:
        print(f"\n{'='*70}")
        print(f"  BÁO GIÁ — Cửa đi {brand} {color} | {n_canh} cánh | Kính {glass_code}")
        print(f"  Kích thước: {W_mm}×{H_mm}mm | SL: {qty} | Diện tích: {ctx['TONG_M2']:.3f}m²")
        print(f"  Đơn giá nhôm: {fmt_vnd(don_gia_nhom)} đ/kg")
        print(f"{'='*70}")

        print(f"\n  {'KHOẢN MỤC':<35} {'THÀNH TIỀN':>20}")
        print(f"  {'-'*55}")
        for label, key in [
            ("VL_NHOM — Vật liệu Nhôm", "VL_NHOM"),
            ("VL_KINH — Vật liệu Kính", "VL_KINH"),
            ("VL_VTP  — Vật tư phụ",    "VL_VTP"),
            ("VL_PK   — Phụ kiện",      "VL_PK"),
        ]:
            print(f"  {label:<35} {fmt_vnd(result.get(key, 0)):>17} đ")
        print(f"  {'─'*55}")
        for label, key in [
            ("TONG_VL — TỔNG VẬT LIỆU", "TONG_VL"),
            ("NC_SX   — Nhân công SX",   "NC_SX"),
            ("NC_LD   — Nhân công LĐ",   "NC_LD"),
            ("TONG_NC — TỔNG NHÂN CÔNG", "TONG_NC"),
            ("OH_HH   — Hao hụt",        "OH_HH"),
            ("OH_VC   — Vận chuyển",     "OH_VC"),
            ("OH_BH   — Bảo hành DP",    "OH_BH"),
            ("TONG_OH — TỔNG OVERHEAD",  "TONG_OH"),
        ]:
            print(f"  {label:<35} {fmt_vnd(result.get(key, 0)):>17} đ")
        print(f"  {'═'*55}")
        for label, key in [
            ("GIA_THANH — GIÁ THÀNH",    "GIA_THANH"),
            ("PROFIT — Lợi nhuận (15%)", "PROFIT"),
            ("GIA_BAN — GIÁ BÁN",        "GIA_BAN"),
            ("DON_GIA_M2 — Đơn giá /m²", "DON_GIA_M2"),
            ("GIA_VAT — GIÁ SAU VAT",    "GIA_VAT"),
        ]:
            print(f"  {label:<35} {fmt_vnd(result.get(key, 0)):>17} đ")
        print(f"  {'═'*55}")
        print(f"  ⚡ Tính trong {elapsed_ms:.2f}ms")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 3. SO SÁNH PHƯƠNG ÁN — cùng engine, khác context
# ═══════════════════════════════════════════════════════════════════════════

def so_sanh_phuong_an():
    """So sánh giá khi đổi màu/kính/brand — cùng formulas, khác context."""

    base_formulas = build_all_formulas(1200, 2200, 2, 1, 113000, "KINH-CL-10")
    engine = FormulaEngine(formulas=base_formulas, on_error="raise", default_value=0)

    def make_ctx(W_mm, H_mm, n_canh, qty, don_gia_nhom, glass_thick, tong_m2):
        return {
            "W_mm": W_mm, "H_mm": H_mm,
            "W_m": W_mm/1000, "H_m": H_mm/1000,
            "qty": qty, "n_canh": n_canh,
            "don_gia_nhom": don_gia_nhom,
            "khung_dung_kg_per_m": 1.257, "khung_ngang_kg_per_m": 1.257,
            "canh_dung_kg_per_m": 1.105, "canh_ngang_kg_per_m": 1.105,
            "nep_dung_kg_per_m": 0.198, "nep_ngang_kg_per_m": 0.198,
            "glass_thick_kinh_canh": glass_thick,
            "TONG_M2": tong_m2,
            "nc_sx_pct": 0.12, "nc_ld_rate": 180000,
            "oh_hh_pct": 0.02, "oh_vc_pct": 0.03,
            "oh_bh_pct": 0.01, "profit_pct": 0.15, "vat_pct": 0.10,
        }

    scenarios = [
        ("XF-NK STD, Kính CL10",    113000, 10.0),
        ("XF-NK VG (+12k), Kính CL10", 125000, 10.0),
        ("ALUMIL STD, Kính CL10",   135000, 10.0),
        ("XF-NK STD, Kính Hộp 24",  113000, 24.0),
        ("XF-NK STD, CL10, qty=10", 113000, 10.0),
    ]

    base_m2 = 1.2 * 2.2
    print(f"\n{'='*80}")
    print(f"  SO SÁNH PHƯƠNG ÁN — Cửa đi 1200×2200mm, 2 cánh")
    print(f"{'='*80}")
    print(f"  {'Phương án':<40} {'Giá bán':>15} {'/m²':>12} {'Chênh':>10}")
    print(f"  {'-'*40} {'-'*15} {'-'*12} {'-'*10}")

    base_result = None
    for i, (label, dg_nhom, thick) in enumerate(scenarios):
        qty = 10 if "qty=10" in label else 1
        ctx = make_ctx(1200, 2200, 2, qty, dg_nhom, thick, base_m2 * qty)
        r = engine.calculate(ctx)
        if i == 0:
            base_result = r
        delta = ""
        if base_result and i > 0:
            d = r["GIA_BAN"] - base_result["GIA_BAN"]
            pct = d / base_result["GIA_BAN"] * 100
            sign = "+" if d >= 0 else ""
            delta = f"{sign}{pct:.1f}%"
        print(f"  {label:<40} {fmt_vnd(r['GIA_BAN']):>12} đ {fmt_vnd(r['DON_GIA_M2']):>9} đ {delta:>10}")

    return engine


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Demo 1: Báo giá chi tiết 1 sản phẩm
    tinh_bao_gia(W_mm=1200, H_mm=2200, n_canh=2, qty=1,
                 brand="XF-NK", color="STD", glass_code="KINH-CL-10")

    # Demo 2: So sánh phương án (cùng engine, khác context)
    so_sanh_phuong_an()

    print(f"\n{'='*70}")
    print(f"  ✅ Hoàn thành! Pattern: formulas → Engine(context) → result")
    print(f"{'='*70}\n")
