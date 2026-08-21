# -*- coding: utf-8 -*-
"""Print Format 'Báo giá AlumGlass' — C5 (báo giá tối thiểu).

Đọc dữ liệu ĐÃ TÍNH SẴN từ Quotation Item:
  - `al_bom_result` (JSON: buckets, cost_template, lines)
  - `al_bom`, `al_bom_version`, `al_gia_ban`, `al_gia_vat`
KHÔNG tính lại — báo giá chỉ là tầng trình bày trên data có sẵn.

Template nằm ở `templates/print_formats/bao_gia.html`. Quyết định thiết kế:
  - Không dùng CSS `zoom`/`@media screen` → tương thích wkhtmltopdf lẫn browser
    (xem memory eup-dntt-bulk-print-wkhtmltopdf.md).
  - Idempotent: không ghi đè Print Format đã tồn tại.
"""
import frappe

PRINT_FORMAT_NAME = "Báo giá AlumGlass"
TEMPLATE_PATH = "templates/print_formats/bao_gia.html"


def create_bao_gia_print_format():
    """Tạo Print Format 'Báo giá AlumGlass' nếu chưa tồn tại. Trả về True nếu đã tạo."""
    if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
        return False

    with open(
        frappe.get_app_path("alumglass", TEMPLATE_PATH), "r", encoding="utf-8"
    ) as f:
        template = f.read()

    frappe.get_doc({
        "doctype": "Print Format",
        "name": PRINT_FORMAT_NAME,
        "doc_type": "Quotation",
        "module": "Selling",
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
        "html": template,
        "description": "Báo giá AlumGlass — đọc al_bom_result (JSON) + al_gia_ban/al_gia_vat "
                       "từ Quotation Item. Không tính lại.",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.logger("alumglass").info("Đã tạo Print Format '%s'." % PRINT_FORMAT_NAME)
    return True
