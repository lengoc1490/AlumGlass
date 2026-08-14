# 03_du_toan.py — Ví dụ dự toán công trình & cutting plan & explain
# Cách chạy: python3 03_du_toan.py
#
# PATTERN: formulas → Engine(context) → result
# Demo 1: Dự toán công trình nhà phố với nhiều loại sản phẩm khác nhau
# Demo 2: Cutting plan — tối ưu cắt nhôm & kính
# Demo 3: Explain — giải thích chuỗi tính toán GIA_BAN

from formula_builder.formula_utils import FormulaEngine
from alumglass.formula_builder.templates import (
    FORMULAS_CUTTING_NHOM, FORMULAS_CUTTING_KINH, DEFAULT_PARAMS,
)
from alumglass.formula_utils import (
    quick_quote, aluminum_cut_efficiency, glass_area_m2, fmt_vnd, analyze_margin,
)

import sys, time, random
sys.stdout.reconfigure(encoding='utf-8')


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 1: DỰ TOÁN CÔNG TRÌNH NHÀ PHỐ
# ═══════════════════════════════════════════════════════════════════════════

def demo_du_toan_cong_trinh():
    """Dự toán toàn bộ công trình với nhiều loại sản phẩm."""

    print(f"\n{'='*70}")
    print(f"  DEMO 1: DỰ TOÁN CÔNG TRÌNH NHÀ PHỐ 3 TẦNG")
    print(f"{'='*70}")

    all_items = []

    # ── Cửa đi chính 4 cánh ───────────────────────────────────────────
    print(f"\n  🚪 CỬA ĐI CHÍNH — Xingfa NK, 4 cánh, Kính CL 10mm")
    r = quick_quote(W_mm=3600, H_mm=2400, n_canh=4, qty=1,
                    brand="XF-NK", color="STD", glass_code="KINH-CL-10")
    all_items.append(r)
    print(f"     Giá bán: {fmt_vnd(r['GIA_BAN'])} đ | /m²: {fmt_vnd(r['DON_GIA_M2'])} đ")

    # ── Cửa sổ (6 cái) ────────────────────────────────────────────────
    print(f"\n  🪟 CỬA SỔ — Xingfa NK, 2 cánh, Kính CL 8mm (×6)")
    r = quick_quote(W_mm=1200, H_mm=1200, n_canh=2, qty=1,
                    brand="XF-NK", color="STD", glass_code="KINH-CL-8")
    for _ in range(6):
        all_items.append(r)
    print(f"     Giá 1 cửa: {fmt_vnd(r['GIA_BAN'])} đ | 6 cửa: {fmt_vnd(r['GIA_BAN']*6)} đ")

    # ── Cửa lùa ban công (2 cái) ─────────────────────────────────────
    print(f"\n  🚪 CỬA LÙA BAN CÔNG — Xingfa NK, 2 cánh (×2)")
    r = quick_quote(W_mm=2400, H_mm=2200, n_canh=2, qty=1,
                    brand="XF-NK", color="VG", glass_code="KINH-CL-10")
    for _ in range(2):
        all_items.append(r)
    print(f"     Giá 1 cửa: {fmt_vnd(r['GIA_BAN'])} đ | 2 cửa: {fmt_vnd(r['GIA_BAN']*2)} đ")

    # ── Vách kính mặt tiền (Alumil, Kính Hộp 24mm) ───────────────────
    print(f"\n  🪟 VÁCH KÍNH MẶT TIỀN — Alumil STD, Kính Hộp 24mm")
    r = quick_quote(W_mm=3000, H_mm=3000, n_canh=1, qty=2,
                    brand="ALUMIL", color="STD", glass_code="KINH-HOP-24")
    all_items.append(r)
    print(f"     Giá: {fmt_vnd(r['GIA_BAN'])} đ | /m²: {fmt_vnd(r['DON_GIA_M2'])} đ")
    print(f"     Kính: {r['meta']['glass_area_m2']:.3f}m² | "
          f"Nhôm: {r['meta']['aluminum_kg']:.1f}kg")

    # ── Tổng hợp ─────────────────────────────────────────────────────
    total_gia_ban = sum(it["GIA_BAN"] for it in all_items)
    total_gia_vat = sum(it["GIA_VAT"] for it in all_items)
    total_m2 = sum(it["TONG_M2"] for it in all_items)
    total_vl_nhom = sum(it["VL_NHOM"] for it in all_items)
    total_vl_kinh = sum(it["VL_KINH"] for it in all_items)

    print(f"\n  {'═'*55}")
    print(f"  📊 TỔNG HỢP DỰ TOÁN ({len(all_items)} hạng mục)")
    print(f"  {'═'*55}")
    print(f"  Tổng VL Nhôm:     {fmt_vnd(total_vl_nhom):>18} đ")
    print(f"  Tổng VL Kính:     {fmt_vnd(total_vl_kinh):>18} đ")
    print(f"  Tổng diện tích:   {total_m2:>18.2f} m²")
    print(f"  {'─'*55}")
    print(f"  TỔNG GIÁ BÁN:     {fmt_vnd(total_gia_ban):>18} đ")
    print(f"  TỔNG SAU VAT:     {fmt_vnd(total_gia_vat):>18} đ")
    print(f"  ĐƠN GIÁ BÌNH QUÂN:{fmt_vnd(total_gia_ban/total_m2 if total_m2 else 0):>15} đ/m²")

    return all_items


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 2: CUTTING PLAN — tối ưu cắt nhôm & kính
# ═══════════════════════════════════════════════════════════════════════════

def demo_cutting_plan():
    """Tính tối ưu cắt nhôm (1D) và kính (2D nesting)."""

    print(f"\n{'='*70}")
    print(f"  DEMO 2: CUTTING PLAN — TỐI ƯU CẮT NHÔM & KÍNH")
    print(f"{'='*70}")

    # ── A. Cắt nhôm (1D) — dùng FormulaEngine ────────────────────────
    print(f"\n  🔪 CẮT NHÔM — Cửa đi 1200×2200mm, 2 cánh")

    # Các mảnh cần cắt
    pieces = [
        ("Khung đứng",     2200, 2),
        ("Khung ngang",    1243, 2),
        ("Cánh đứng",      2114, 2),
        ("Cánh ngang",      557, 2),
        ("Nẹp đứng",       2114, 2),
        ("Nẹp ngang",       557, 2),
        ("Nẹp kính đứng",  2114, 2),
        ("Nẹp kính ngang",  557, 2),
    ]
    total_cut = sum(length * qty for _, length, qty in pieces)

    # Cách 1: Dùng pure function (nhanh)
    eff = aluminum_cut_efficiency(total_cut, bar_len_mm=6000, kerf_mm=3)
    print(f"     {'Chi tiết':<20} {'Dài (mm)':>10} {'SL':>5}")
    for name, length, qty in pieces:
        print(f"     {name:<20} {length:>10} {qty:>5}")
    print(f"     {'─'*37}")
    print(f"     Tổng chiều dài: {total_cut:,.0f} mm")
    print(f"     Số thanh 6m:    {eff['bars_needed']} thanh")
    print(f"     Phế liệu:       {eff['scrap_mm']:,.0f} mm ({eff['scrap_pct']:.1f}%)")
    print(f"     Hiệu suất:      {eff['efficiency_pct']:.1f}%")

    # Cách 2: Dùng FormulaEngine (có explain/audit nếu cần)
    formulas = list(FORMULAS_CUTTING_NHOM)
    engine = FormulaEngine(formulas=formulas, on_error="raise", default_value=0)
    ctx = {
        "total_cut_length_mm": total_cut,
        "stock_bar_len": 6000,
        "saw_kerf": 3,
        "min_offcut": 300,
    }
    result = engine.calculate(ctx)
    print(f"     [Engine] bars={result['bars_needed']}, "
          f"scrap={result['scrap_pct']:.1f}%, "
          f"offcut={'✅' if result['has_reusable_offcut'] else '❌'}")

    # ── B. Cắt kính (2D nesting) ─────────────────────────────────────
    print(f"\n  🪚 CẮT KÍNH — 2 panel 1134×2114mm (jumbo 3210×2250mm)")

    total_glass = sum(glass_area_m2(w, h, 1) for _, w, h in [
        ("Panel A", 1134, 2114), ("Panel B", 1134, 2114),
    ])

    formulas_k = list(FORMULAS_CUTTING_KINH)
    engine_k = FormulaEngine(formulas=formulas_k, on_error="raise", default_value=0)
    ctx_k = {
        "total_glass_m2": total_glass,
        "jumbo_w_mm": 3210, "jumbo_h_mm": 2250,
        "edge_trim_mm": 10,
    }
    result_k = engine_k.calculate(ctx_k)

    print(f"     Panel A: 1134×2114mm | Panel B: 1134×2114mm")
    print(f"     Jumbo:   3210×2250mm (khả dụng {3210-20}×{2250-20}mm)")
    print(f"     Tổng diện tích kính: {total_glass:.3f} m²")
    print(f"     Số sheet ước tính:   {result_k['estimated_sheets']}")
    print(f"     Phế liệu:            {result_k['waste_m2']:.3f} m² "
          f"({result_k['waste_pct']:.1f}%)")

    return eff


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 3: EXPLAIN — giải thích chuỗi tính toán
# ═══════════════════════════════════════════════════════════════════════════

def demo_explain():
    """Dùng engine.explain() để xem chuỗi tính toán GIA_BAN."""

    print(f"\n{'='*70}")
    print(f"  DEMO 3: EXPLAIN — GIẢI THÍCH CHUỖI TÍNH TOÁN GIA_BAN")
    print(f"{'='*70}")

    # Import formulas từ ví dụ 01_bao_gia
    from alumglass.formula_builder.examples._01_formulas import \
        build_all_formulas  # noqa (sẽ tạo file helper)

    # Tạm thời build formulas trực tiếp
    from alumglass.formula_builder.templates import (
        FORMULAS_KHUNG_DUNG, FORMULAS_KHUNG_NGANG,
        FORMULAS_CANH_DUNG, FORMULAS_CANH_NGANG, FORMULAS_NEP,
        build_glass_formulas, build_bucket_formulas,
        FORMULAS_COST_TEMPLATE, ALUMINUM_PRICE_TABLE, GLASS_PRICE_TABLE,
    )
    from alumglass.formula_utils import lookup_glass_price

    formulas = []
    for ps in [FORMULAS_KHUNG_DUNG, FORMULAS_KHUNG_NGANG,
               FORMULAS_CANH_DUNG, FORMULAS_CANH_NGANG, FORMULAS_NEP]:
        formulas.extend(ps)

    formulas.extend(build_glass_formulas(
        "kinh_canh", "W_mm - 86", "H_mm - 86", "1",
        str(lookup_glass_price("KINH-CL-10", GLASS_PRICE_TABLE)),
    ))

    formulas.extend([
        {"name": "gioang_qty", "formula": "kinh_canh_total_perimeter_m * qty * 2"},
        {"name": "gioang_dg", "formula": "5000"},
        {"name": "gioang_tt", "formula": "gioang_qty * gioang_dg"},
    ])

    formulas.extend(build_bucket_formulas({
        "VL_NHOM": ["khung_dung_tt","khung_ngang_tt","canh_dung_tt","canh_ngang_tt","nep_dung_tt","nep_ngang_tt"],
        "VL_KINH": ["kinh_canh_tt"],
        "VL_VTP": ["gioang_tt"],
        "VL_PK": ["0"],
        "OH_CUT_KINH": ["kinh_canh_cut"],
    }))

    formulas.extend(FORMULAS_COST_TEMPLATE)

    engine = FormulaEngine(formulas=formulas, on_error="raise", default_value=0)

    ctx = {
        "W_mm": 1200, "H_mm": 2200, "W_m": 1.2, "H_m": 2.2,
        "qty": 1, "n_canh": 2,
        "don_gia_nhom": 113000,
        "khung_dung_kg_per_m": 1.257, "khung_ngang_kg_per_m": 1.257,
        "canh_dung_kg_per_m": 1.105, "canh_ngang_kg_per_m": 1.105,
        "nep_dung_kg_per_m": 0.198, "nep_ngang_kg_per_m": 0.198,
        "glass_thick_kinh_canh": 10.0,
        "TONG_M2": 2.64,
        "nc_sx_pct": 0.12, "nc_ld_rate": 180000,
        "oh_hh_pct": 0.02, "oh_vc_pct": 0.03,
        "oh_bh_pct": 0.01, "profit_pct": 0.15, "vat_pct": 0.10,
    }

    # explain() trả về ExplainResult với steps và to_text()
    expl = engine.explain("GIA_BAN", ctx)

    print(f"\n  Giá trị GIA_BAN: {fmt_vnd(expl.value)} đ")
    print(f"  Inputs sử dụng: {len(expl.inputs_used)} biến")
    print(f"\n  Chuỗi tính toán (tóm tắt 5 bước cuối):")
    for step in expl.steps[-5:]:
        deps_str = ", ".join(f"{k}={fmt_vnd(v)}" if isinstance(v, (int, float)) and v > 100
                            else f"{k}={v}" for k, v in list(step.deps.items())[:3])
        print(f"  {step.name} = {step.formula}")
        print(f"    → {fmt_vnd(step.value) if isinstance(step.value, (int, float)) else step.value}  "
              f"(từ: {deps_str})")

    return expl


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    demo_du_toan_cong_trinh()
    demo_cutting_plan()
    demo_explain()
    print(f"\n{'='*70}")
    print(f"  ✅ Hoàn thành! Pattern: formulas → Engine(context) → result")
    print(f"{'='*70}\n")
