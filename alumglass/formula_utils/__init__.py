# alumglass/formula_utils/__init__.py
# Tiện ích tính toán ngành Nhôm Kính — pure functions
from .calculations import (
    glass_area_m2, glass_price, glass_perimeter_m, glass_weight_kg,
    aluminum_weight_kg, aluminum_price, aluminum_cut_efficiency,
    lookup_aluminum_price, lookup_glass_price,
    quick_quote, analyze_margin, fmt_vnd,
)
from .validators import (
    validate_bom_dimensions, validate_glass_thickness,
    validate_aluminum_profile, ValidationResult,
)

__all__ = [
    "glass_area_m2", "glass_price", "glass_perimeter_m", "glass_weight_kg",
    "aluminum_weight_kg", "aluminum_price", "aluminum_cut_efficiency",
    "lookup_aluminum_price", "lookup_glass_price",
    "quick_quote", "analyze_margin", "fmt_vnd",
    "validate_bom_dimensions", "validate_glass_thickness",
    "validate_aluminum_profile", "ValidationResult",
]
