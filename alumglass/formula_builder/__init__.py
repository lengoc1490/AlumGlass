# alumglass/formula_builder/__init__.py
# Bộ công thức mẫu ngành Nhôm Kính — dùng trực tiếp với FormulaEngine
#
# Cách dùng:
#   from formula_builder.formula_utils import FormulaEngine
#   from alumglass.formula_builder import FORMULAS_COST_TEMPLATE
#   engine = FormulaEngine(formulas=FORMULAS_COST_TEMPLATE, ...)
#   result = engine.calculate(inputs_dict)

from .templates import (
    # Bộ công thức profile nhôm
    FORMULAS_KHUNG_DUNG,
    FORMULAS_KHUNG_NGANG,
    FORMULAS_CANH_DUNG,
    FORMULAS_CANH_NGANG,
    FORMULAS_NEP,
    # Builder function cho kính
    build_glass_formulas,
    # Builder function cho bucket
    build_bucket_formulas,
    # Bộ công thức cost template
    FORMULAS_COST_TEMPLATE,
    # Bộ công thức tổng hợp dự án
    FORMULAS_PROJECT,
    # Bộ công thức phân tích biến động
    FORMULAS_COST_VARIANCE,
    # Bộ công thức cắt
    FORMULAS_CUTTING_NHOM,
    FORMULAS_CUTTING_KINH,
    # Tham số & bảng giá
    DEFAULT_PARAMS,
    PROFILE_KG_PER_M,
    ALUMINUM_PRICE_TABLE,
    GLASS_PRICE_TABLE,
)

__all__ = [
    "FORMULAS_KHUNG_DUNG", "FORMULAS_KHUNG_NGANG",
    "FORMULAS_CANH_DUNG", "FORMULAS_CANH_NGANG", "FORMULAS_NEP",
    "build_glass_formulas", "build_bucket_formulas",
    "FORMULAS_COST_TEMPLATE", "FORMULAS_PROJECT",
    "FORMULAS_COST_VARIANCE", "FORMULAS_CUTTING_NHOM", "FORMULAS_CUTTING_KINH",
    "DEFAULT_PARAMS", "PROFILE_KG_PER_M",
    "ALUMINUM_PRICE_TABLE", "GLASS_PRICE_TABLE",
]
