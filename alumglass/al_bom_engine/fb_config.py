"""Đọc "named constant" (1 giá trị cấu hình đặt tên) qua Formula Variable
Binding — cơ chế DUY NHẤT dùng cho MỌI nhu cầu "chọn 1 giá trị cho 1 mục đích
cụ thể" (khác Check field — dành cho property lặp lại trên nhiều record).
Admin cấu hình qua UI Formula Variable Binding sẵn có — sửa được ngay, không
cần bench migrate, không cần thêm field/doctype mới cho mỗi nhu cầu phát sinh.
"""
import frappe


def get_named_constant(variable_name, default=None):
    """Đọc giá trị 1 Formula Variable Binding (thường source_type="constant")
    theo tên biến. Cache theo request (frappe.local).

    Args:
        variable_name: tên binding cần đọc (vd "DEFAULT_ACCESSORY_CATEGORY").
        default: giá trị trả về nếu binding không tồn tại/inactive/lỗi —
            KHÔNG default ngầm 1 chuỗi đoán mò trong code.
    """
    cache = getattr(frappe.local, "_al_named_constant_cache", None)
    if cache is None:
        cache = {}
        frappe.local._al_named_constant_cache = cache
    if variable_name in cache:
        return cache[variable_name]

    rows = frappe.get_all(
        "Formula Variable Binding",
        filters={"variable_name": variable_name, "is_active": 1},
        fields=["source_type", "source_config", "data_type"],
        limit=1,
    )
    if not rows:
        frappe.log_error(
            f"get_named_constant: chưa có Formula Variable Binding active "
            f"tên '{variable_name}' — dùng default={default!r}. Tạo binding "
            f"qua UI Formula Variable Binding (source_type=constant).",
            "fb_config: named constant missing",
        )
        cache[variable_name] = default
        return default

    binding = dict(rows[0], variable_name=variable_name)
    try:
        from formula_builder.api.batch_binding_resolver import resolve_all_bindings_batch
        resolved = resolve_all_bindings_batch([binding], doc=None, pre_resolved={})
        value = resolved.get(variable_name, default)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"get_named_constant({variable_name})")
        value = default

    cache[variable_name] = value
    return value
