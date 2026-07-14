# 02_giathanh.py — Ví dụ tính giá thành toàn dự án & phân tích biến động
# Cách chạy: python3 02_giathanh.py
#
# PATTERN: formulas → Engine(context) → result
# Demo 1: Tổng hợp giá thành toàn dự án từ nhiều hạng mục
# Demo 2: Phân tích biến động chi phí (Cost Variance)
# Demo 3: Mass test performance với 100k items

from formula_builder.formula_utils import FormulaEngine
from alumglass.formula_builder.templates import (
    FORMULAS_PROJECT, FORMULAS_COST_VARIANCE,
    DEFAULT_PARAMS,
)
from alumglass.formula_utils import quick_quote, analyze_margin, fmt_vnd

import sys, time, random
sys.stdout.reconfigure(encoding='utf-8')


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 1: GIÁ THÀNH TOÀN DỰ ÁN — tổng hợp từ nhiều hạng mục BOM
# ═══════════════════════════════════════════════════════════════════════════

def demo_gia_thanh_du_an():
    """Tổng hợp giá thành dự án từ nhiều hạng mục đã tính BOM."""

    print(f"\n{'='*70}")
    print(f"  DEMO 1: GIÁ THÀNH TOÀN DỰ ÁN — Chung cư 50 căn hộ")
    print(f"{'='*70}")

    # ── Bước 1: Định nghĩa formulas (dùng bộ có sẵn) ──────────────────
    formulas = list(FORMULAS_PROJECT)

    # ── Bước 2: Tạo engine ───────────────────────────────────────────
    engine = FormulaEngine(
        formulas=formulas,
        on_error="default",
        default_value=0,
        deterministic=True,
    )

    # ── Bước 3: Xây dựng context — tổng hợp từ các hạng mục ──────────
    # Mỗi hạng mục đã được tính BOM riêng → lấy các giá trị tổng hợp
    items = []

    # Cửa đi chính (50 bộ)
    for _ in range(50):
        r = quick_quote(W_mm=1200, H_mm=2200, n_canh=2, qty=1)
        items.append(r)

    # Cửa sổ (100 bộ)
    for _ in range(100):
        r = quick_quote(W_mm=800, H_mm=1200, n_canh=1, qty=2)
        items.append(r)

    # Vách kính (5 mảng lớn)
    for _ in range(5):
        r = quick_quote(W_mm=3000, H_mm=3000, n_canh=1, qty=1,
                        glass_code="KINH-HOP-24")
        items.append(r)

    # Gom thành lists cho context
    ctx = {
        "all_vl_nhom": [it["VL_NHOM"] for it in items],
        "all_vl_kinh": [it["VL_KINH"] for it in items],
        "all_vl_vtp":  [it["VL_VTP"] for it in items],
        "all_vl_pk":   [it["VL_PK"] for it in items],
        "all_nc_sx":   [it["TONG_VL"] * 0.12 for it in items],  # ~NC_SX từ cost template
        "all_nc_ld":   [it["TONG_M2"] * 180000 for it in items],
        "all_oh":      [it["TONG_VL"] * 0.06 for it in items],  # ~OH tổng
        "all_gia_ban": [it["GIA_BAN"] for it in items],
        "all_gia_vat": [it["GIA_VAT"] for it in items],
        "all_m2":      [it["TONG_M2"] for it in items],
        "vat_pct": 0.10,
    }

    # ── Bước 4: Tính toán ────────────────────────────────────────────
    t0 = time.perf_counter()
    result = engine.calculate(ctx)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # ── Bước 5: In kết quả ───────────────────────────────────────────
    print(f"\n  📊 TỔNG HỢP {len(items)} HẠNG MỤC:")
    print(f"  {'─'*55}")
    for label, key in [
        ("Nhôm", "TOTAL_VL_NHOM"), ("Kính", "TOTAL_VL_KINH"),
        ("Vật tư phụ", "TOTAL_VL_VTP"), ("Phụ kiện", "TOTAL_VL_PK"),
    ]:
        print(f"  {label:<25} {fmt_vnd(result.get(key, 0)):>22} đ")
    print(f"  {'─'*55}")
    for label, key in [
        ("TỔNG VẬT LIỆU", "TOTAL_VL"),
        ("TỔNG NHÂN CÔNG", "TOTAL_NC"),
        ("TỔNG OVERHEAD", "TOTAL_OH"),
    ]:
        print(f"  {label:<25} {fmt_vnd(result.get(key, 0)):>22} đ")
    print(f"  {'═'*55}")
    for label, key in [
        ("TỔNG GIÁ THÀNH", "TOTAL_GIA_THANH"),
        ("TỔNG DOANH THU", "TOTAL_REVENUE"),
        ("TỔNG LỢI NHUẬN", "TOTAL_PROFIT"),
        ("MARGIN", "MARGIN_PCT"),
    ]:
        val = result.get(key, 0)
        if key == "MARGIN_PCT":
            print(f"  {label:<25} {val:>21.1f}%")
        else:
            print(f"  {label:<25} {fmt_vnd(val):>22} đ")
    print(f"  {'═'*55}")
    print(f"  TỔNG DIỆN TÍCH: {result.get('TOTAL_M2', 0):,.2f} m²")
    print(f"  ĐƠN GIÁ BÌNH QUÂN: {fmt_vnd(result.get('AVG_DON_GIA_M2', 0))} đ/m²")
    print(f"  ⚡ {elapsed_ms:.2f}ms")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 2: PHÂN TÍCH BIẾN ĐỘNG CHI PHÍ
# ═══════════════════════════════════════════════════════════════════════════

def demo_cost_variance():
    """So sánh chi phí ước tính vs thực tế (từ GL Entry)."""

    print(f"\n{'='*70}")
    print(f"  DEMO 2: PHÂN TÍCH BIẾN ĐỘNG CHI PHÍ (COST VARIANCE)")
    print(f"{'='*70}")

    # ── Bước 1: Định nghĩa formulas ──────────────────────────────────
    formulas = list(FORMULAS_COST_VARIANCE)

    # ── Bước 2: Tạo engine ───────────────────────────────────────────
    engine = FormulaEngine(
        formulas=formulas,
        on_error="default",
        default_value=0,
        deterministic=True,
    )

    # ── Bước 3: Context — giá trị ước tính vs thực tế ─────────────────
    ctx = {
        "EST_VL": 4_700_000,    # Ước tính từ BOM
        "ACTUAL_VL": 5_200_000,  # Thực tế từ GL Entry
        "EST_NC": 800_000,
        "ACTUAL_NC": 750_000,
        "EST_OH": 300_000,
        "ACTUAL_OH": 320_000,
        "variance_threshold": 15.0,
    }

    # ── Bước 4: Tính toán ────────────────────────────────────────────
    result = engine.calculate(ctx)

    # ── Bước 5: In kết quả ───────────────────────────────────────────
    print(f"\n  {'Khoản mục':<15} {'Ước tính':>15} {'Thực tế':>15} "
          f"{'Chênh lệch':>15} {'%':>10}  {'':>6}")
    print(f"  {'-'*15} {'-'*15} {'-'*15} {'-'*15} {'-'*10}")

    for label, est_k, act_k, var_k, pct_k in [
        ("Vật liệu",  "EST_VL",  "ACTUAL_VL",  "VARIANCE_VL",  "VARIANCE_VL_PCT"),
        ("Nhân công", "EST_NC",  "ACTUAL_NC",  "VARIANCE_NC",  "VARIANCE_NC_PCT"),
        ("Overhead",  "EST_OH",  "ACTUAL_OH",  "VARIANCE_OH",  "VARIANCE_OH_PCT"),
    ]:
        est = ctx[est_k]; act = ctx[act_k]
        delta = result[var_k]; pct = result[pct_k]
        sign = "+" if delta >= 0 else ""
        flag = "🔴" if delta > 0 else "🟢"
        print(f"  {label:<15} {fmt_vnd(est):>12} {fmt_vnd(act):>12} "
              f"{sign}{fmt_vnd(delta):>11} {sign}{pct:>8.1f}%  {flag}")

    print(f"  {'─'*15} {'─'*15} {'─'*15} {'─'*15} {'─'*10}")
    total_delta = result["VARIANCE_TOTAL"]
    total_pct = result["VARIANCE_TOTAL_PCT"]
    sign = "+" if total_delta >= 0 else ""
    print(f"  {'TỔNG':<15} {fmt_vnd(result['EST_TOTAL']):>12} "
          f"{fmt_vnd(result['ACTUAL_TOTAL']):>12} "
          f"{sign}{fmt_vnd(total_delta):>11} {sign}{total_pct:>8.1f}%")

    print(f"\n  📋 KẾT LUẬN:")
    if result["IS_OVER_BUDGET"]:
        print(f"     ⚠️  VƯỢT NGÂN SÁCH: {fmt_vnd(total_delta)}đ ({total_pct:.1f}%)")
        if result["IS_CRITICAL"]:
            print(f"     🚨 MỨC CRITICAL — Vượt ngưỡng {ctx['variance_threshold']}%!")
    else:
        print(f"     ✅ Trong ngân sách")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 3: MASS TEST — tính giá thành 10,000 sản phẩm
# ═══════════════════════════════════════════════════════════════════════════

def demo_mass_test():
    """Performance test với số lượng lớn."""

    print(f"\n{'='*70}")
    print(f"  DEMO 3: MASS TEST — 10,000 SẢN PHẨM")
    print(f"{'='*70}")

    N = 10_000

    # Tạo engine 1 lần
    formulas = list(FORMULAS_PROJECT)
    engine = FormulaEngine(formulas=formulas, on_error="default", default_value=0)

    # Sinh dữ liệu ngẫu nhiên
    print(f"  ⏳ Sinh {N:,} sản phẩm ngẫu nhiên...")
    all_vl_nhom = [random.uniform(1_000_000, 4_000_000) for _ in range(N)]
    all_vl_kinh = [random.uniform(300_000, 2_000_000) for _ in range(N)]
    all_vl_vtp  = [random.uniform(50_000, 300_000) for _ in range(N)]
    all_vl_pk   = [random.uniform(300_000, 1_500_000) for _ in range(N)]
    all_nc_sx   = [v * 0.12 for v in all_vl_nhom]
    all_nc_ld   = [random.uniform(200_000, 500_000) for _ in range(N)]
    all_oh      = [v * 0.06 for v in all_vl_nhom]
    all_gia_ban = [random.uniform(2_000_000, 10_000_000) for _ in range(N)]
    all_gia_vat = [v * 1.1 for v in all_gia_ban]
    all_m2      = [random.uniform(1.0, 6.0) for _ in range(N)]

    ctx = {
        "all_vl_nhom": all_vl_nhom, "all_vl_kinh": all_vl_kinh,
        "all_vl_vtp": all_vl_vtp, "all_vl_pk": all_vl_pk,
        "all_nc_sx": all_nc_sx, "all_nc_ld": all_nc_ld,
        "all_oh": all_oh, "all_gia_ban": all_gia_ban,
        "all_gia_vat": all_gia_vat, "all_m2": all_m2,
        "vat_pct": 0.10,
    }

    # Tính
    t0 = time.perf_counter()
    result = engine.calculate(ctx)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"  ✅ Hoàn thành {N:,} sản phẩm trong {elapsed_ms:.1f}ms "
          f"({elapsed_ms/N*1000:.3f}µs/item)")
    print(f"  Tổng doanh thu: {fmt_vnd(result['TOTAL_REVENUE'])} đ")
    print(f"  Margin: {result['MARGIN_PCT']:.1f}%")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    demo_gia_thanh_du_an()
    demo_cost_variance()
    demo_mass_test()
    print(f"\n{'='*70}")
    print(f"  ✅ Hoàn thành! Pattern: formulas → Engine(context) → result")
    print(f"{'='*70}\n")
