# alumglass/formula_utils/validators.py
# Validators — kiểm tra tính hợp lệ của dữ liệu đầu vào

from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Kết quả validate."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def merge(self, other: "ValidationResult"):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if other.errors:
            self.is_valid = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def raise_if_invalid(self, context: str = ""):
        if not self.is_valid:
            prefix = f"[{context}] " if context else ""
            raise ValueError(f"{prefix}" + "; ".join(self.errors))


# =============================================================================
# 1. VALIDATE KÍCH THƯỚC BOM
# =============================================================================

def validate_bom_dimensions(
    W_mm: float,
    H_mm: float,
    qty: int = 1,
    n_canh: int = 1,
    product_type: str = "CUA_DI",
) -> ValidationResult:
    """Validate kích thước đầu vào của BOM.

    Kiểm tra các giới hạn thực tế trong ngành nhôm kính:
    - Kích thước tối thiểu/tối đa cho từng loại sản phẩm
    - Tỷ lệ W/H hợp lý
    - Số cánh hợp lý với chiều rộng
    """
    r = ValidationResult()

    W = float(W_mm)
    H = float(H_mm)
    q = int(qty)

    if W <= 0:
        r.add_error(f"Chiều rộng phải > 0: W_mm={W_mm}")
    if H <= 0:
        r.add_error(f"Chiều cao phải > 0: H_mm={H_mm}")
    if q <= 0:
        r.add_error(f"Số lượng phải > 0: qty={q}")
    if r.errors:
        return r

    # Giới hạn theo loại sản phẩm
    limits = {
        "CUA_DI":     {"W_min": 600, "W_max": 3600, "H_min": 1800, "H_max": 3500},
        "CUA_SO":     {"W_min": 400, "W_max": 2400, "H_min": 400,  "H_max": 2400},
        "CUA_LUA":    {"W_min": 600, "W_max": 3000, "H_min": 800,  "H_max": 3000},
        "VACH_KINH":  {"W_min": 500, "W_max": 6000, "H_min": 500,  "H_max": 6000},
    }
    lim = limits.get(product_type, limits["CUA_DI"])

    if W < lim["W_min"]:
        r.add_warning(
            f"Chiều rộng {W}mm < tối thiểu {lim['W_min']}mm cho {product_type}"
        )
    if W > lim["W_max"]:
        r.add_error(
            f"Chiều rộng {W}mm > tối đa {lim['W_max']}mm cho {product_type}"
        )
    if H < lim["H_min"]:
        r.add_warning(
            f"Chiều cao {H}mm < tối thiểu {lim['H_min']}mm cho {product_type}"
        )
    if H > lim["H_max"]:
        r.add_error(
            f"Chiều cao {H}mm > tối đa {lim['H_max']}mm cho {product_type}"
        )

    # Tỷ lệ W/H
    ratio = max(W, H) / min(W, H) if min(W, H) > 0 else 999
    if ratio > 5:
        r.add_warning(f"Tỷ lệ W/H = {ratio:.1f} > 5 — có thể không đảm bảo kết cấu")

    # Số cánh vs chiều rộng
    n_c = int(n_canh)
    min_width_per_canh = 300
    width_per_canh = W / n_c
    if width_per_canh < min_width_per_canh:
        r.add_error(
            f"Mỗi cánh chỉ {width_per_canh:.0f}mm — "
            f"tối thiểu {min_width_per_canh}mm/cánh. Giảm số cánh hoặc tăng W."
        )
    if width_per_canh > 1200:
        r.add_warning(f"Mỗi cánh {width_per_canh:.0f}mm > 1200mm — cân nhắc tăng số cánh")

    return r


# =============================================================================
# 2. VALIDATE KÍNH
# =============================================================================

def validate_glass_thickness(
    total_thick_mm: float,
    glass_type: str = "DON",
    W_mm: float = 0,
    H_mm: float = 0,
) -> ValidationResult:
    """Validate độ dày kính.

    Kiểm tra:
    - Độ dày tối thiểu/tối đa theo loại kính
    - Diện tích tối đa theo độ dày (an toàn)
    """
    r = ValidationResult()
    t = float(total_thick_mm)

    # Giới hạn độ dày theo loại
    type_limits = {
        "DON":        (3, 19),
        "CUONG_LUC":  (4, 19),
        "HOP":        (12, 60),
        "LOWE":       (12, 60),
        "LAMINATE":   (6, 40),
    }
    lo, hi = type_limits.get(glass_type, (3, 60))

    if t < lo:
        r.add_error(f"Độ dày kính {t}mm < tối thiểu {lo}mm cho loại {glass_type}")
    if t > hi:
        r.add_error(f"Độ dày kính {t}mm > tối đa {hi}mm cho loại {glass_type}")

    # Diện tích tối đa theo độ dày (quy tắc an toàn)
    if W_mm > 0 and H_mm > 0:
        area_m2 = W_mm * H_mm / 1_000_000
        # Diện tích tối đa khuyến nghị = thickness_mm * 0.5 m²
        max_area = t * 0.5
        if area_m2 > max_area:
            r.add_warning(
                f"Diện tích kính {area_m2:.2f}m² > khuyến nghị {max_area:.1f}m² "
                f"cho kính dày {t}mm. Cân nhắc tăng độ dày."
            )

    return r


# =============================================================================
# 3. VALIDATE NHÔM PROFILE
# =============================================================================

def validate_aluminum_profile(
    item_code: str,
    kg_per_m: float,
    usage_type: str = "KHUNG",  # KHUNG / CANH / NEP
) -> ValidationResult:
    """Validate thông số profile nhôm.

    Kiểm tra:
    - kg_per_m hợp lệ theo loại
    - Khoảng giá trị thực tế
    """
    r = ValidationResult()
    kpm = float(kg_per_m)

    usage_limits = {
        "KHUNG": (0.5, 3.0),
        "CANH":  (0.5, 2.5),
        "NEP":   (0.1, 1.5),
        "DO":    (0.3, 2.0),
        "GIOANG": (0.01, 0.3),
    }
    lo, hi = usage_limits.get(usage_type, (0.01, 5.0))

    if kpm < lo:
        r.add_warning(f"kg/m = {kpm} của {item_code} ({usage_type}) thấp hơn thông thường ({lo}-{hi})")
    if kpm > hi:
        r.add_warning(f"kg/m = {kpm} của {item_code} ({usage_type}) cao hơn thông thường ({lo}-{hi})")
    if kpm <= 0:
        r.add_error(f"kg/m của {item_code} phải > 0")

    return r
