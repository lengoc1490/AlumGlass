# -*- coding: utf-8 -*-
"""Nguồn gốc của từng biến literal dòng BOM — MỘT CHỖ DUY NHẤT.

Vì sao cần
──────────
Cùng một con số (độ dày kính, đơn giá, % hao hụt…) đi vào engine qua nhiều
đường khác nhau, và giao diện gợi ý biến phải nói được "biến này lấy từ đâu"
để người cấu hình không đoán. Trước bản vá, mỗi nơi tự viết một câu mô tả
(uie `adapters.py`, tài liệu, seed) ⇒ sửa một chỗ là lệch các chỗ còn lại.

Module này giữ BẢNG ÁNH XẠ DUY NHẤT `var_name → (doctype, field, label)` cho
các literal mà `BomOrchestrator.b2_prefetch_master_data` inject vào
`row_literals`. Adapter `variable_sources.adapters.row_literal` và phần nhãn
gợi ý chéo dòng `_append_references` đọc từ đây.

Thứ tự ưu tiên
──────────────
1. Dòng `AL Row Literal` có `source_doctype` + `source_field` (cột mới) —
   người cấu hình khai tường minh, LUÔN thắng bảng mặc định.
2. Không khai ⇒ tra bảng `ROW_LITERAL_SOURCES` bên dưới theo `var_name`.

Vì sao đặt ở `variable_sources/` (không phải `al_bom_engine/`)
──────────────────────────────────────────────────────────────
`al_bom_engine/` chỉ chứa controller DocType; toàn bộ nguồn biến + adapter
đã nằm trong `variable_sources/`. Đặt cạnh người dùng của nó để import không
phải vòng qua package doctype.

Module THUẦN Python (không import frappe) — dùng được trong test standalone.
"""

#: `var_name` → nguồn mặc định.
#:
#: `label` là nhãn người đọc của BIẾN (không phải nhãn field), dùng khi cần
#: giải thích nguồn mà không có `AL Row Literal` tương ứng.
ROW_LITERAL_SOURCES = {
    # ── Kính (AL Glass Master) ───────────────────────────────────────
    "total_thick_mm": {
        "doctype": "AL Glass Master",
        "field": "total_thick_mm",
        "label": "Độ dày kính",
    },
    # Tên CŨ của cùng một giá trị — giữ để rule đã viết không vỡ.
    "glass_thick": {
        "doctype": "AL Glass Master",
        "field": "total_thick_mm",
        "label": "Độ dày kính (tên cũ)",
    },
    "glass_type": {
        "doctype": "AL Glass Master",
        "field": "glass_type",
        "label": "Loại kính",
    },
    "max_area_m2": {
        "doctype": "AL Glass Master",
        "field": "max_area_m2",
        "label": "Khổ kính tối đa (m²)",
    },
    # ── Vật tư / danh mục ────────────────────────────────────────────
    "scrap_pct": {
        "doctype": "AL Material Category",
        "field": "default_scrap_pct",
        "label": "% Hao hụt",
    },
    "has_weight": {
        "doctype": "AL Material Category",
        "field": "has_weight",
        "label": "Có tính trọng lượng",
    },
    "unit_price": {
        "doctype": "Item Price",
        "field": "price_list_rate",
        "label": "Đơn giá",
    },
    "weight_per_unit": {
        "doctype": "Item",
        "field": "weight_per_unit",
        "label": "TL riêng (kg/m)",
    },
    "calc_pattern": {
        "doctype": "AL Bom Item",
        "field": "calc_pattern",
        "label": "Pattern tính số lượng",
    },
}


def _row_value(row, fieldname):
    """Đọc field từ dict hoặc Document Frappe (cả hai đều có `.get`)."""
    if row is None:
        return None
    try:
        return row.get(fieldname)
    except Exception:
        return None


def get_source(var_name, row=None):
    """Nguồn của biến `var_name` → dict `{doctype, field, label}` hoặc None.

    `row` là dòng `AL Row Literal` (dict/Document) nếu có — `source_doctype` /
    `source_field` khai trên dòng THẮNG bảng mặc định (người cấu hình biết
    nguồn thật, kể cả khi biến chưa có trong bảng).
    """
    if not var_name:
        return None

    doctype = (_row_value(row, "source_doctype") or "").strip()
    field = (_row_value(row, "source_field") or "").strip()
    if doctype and field:
        default = ROW_LITERAL_SOURCES.get(var_name) or {}
        return {
            "doctype": doctype,
            "field": field,
            "label": default.get("label") or var_name,
        }

    return ROW_LITERAL_SOURCES.get(var_name)


def describe_source(var_name, row=None):
    """Chuỗi ngắn `"<Doctype>.<field>"`, rỗng khi không biết nguồn."""
    source = get_source(var_name, row)
    if not source:
        return ""
    return "%s.%s" % (source["doctype"], source["field"])


def provenance_note(var_name, row=None):
    """Câu nguồn hiển thị cho người dùng: `"Nguồn: <Doctype>.<field>"`."""
    described = describe_source(var_name, row)
    return "Nguồn: %s" % described if described else ""


#: Nhãn NGƯỜI ĐỌC của biến (khác `label` trong bảng trên — label ở đó phục vụ
#: màn hình cấu hình, có thể ghi "(tên cũ)"). Dùng cho câu giải thích bán hàng.
_DISPLAY_LABELS = {
    "total_thick_mm": "Độ dày kính",
    "glass_thick": "Độ dày kính",
    "glass_type": "Loại kính",
    "max_area_m2": "Khổ kính tối đa",
    "scrap_pct": "Hao hụt",
    "unit_price": "Đơn giá",
    "weight_per_unit": "Trọng lượng riêng",
    "calc_pattern": "Cách tính số lượng",
    "has_weight": "Tính trọng lượng",
}

#: Đơn vị hiển thị kèm giá trị (rỗng = không có).
_DISPLAY_UNITS = {
    "total_thick_mm": " mm",
    "glass_thick": " mm",
    "max_area_m2": " m²",
    "scrap_pct": "%",
}


def display_label(var_name):
    """Nhãn người đọc cho biến, ⛔ không lộ tên kỹ thuật."""
    if not var_name:
        return ""
    if var_name in _DISPLAY_LABELS:
        return _DISPLAY_LABELS[var_name]
    # Biến tuỳ biến: bỏ dấu gạch dưới, viết hoa chữ đầu.
    text = str(var_name).replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else ""


def display_unit(var_name):
    """Đơn vị của biến (chuỗi rỗng nếu không khai)."""
    return _DISPLAY_UNITS.get(var_name or "", "")

