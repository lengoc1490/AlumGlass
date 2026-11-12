# -*- coding: utf-8 -*-
"""AL Row Literal — biến engine inject theo từng dòng BOM, khai bằng dữ liệu."""
from frappe.model.document import Document


class ALRowLiteral(Document):
    """Một row literal (unit_price, line_total, glass_thick, ...).

    Danh sách cũ viết tay trong `api/__init__.py`; nay khai ở đây.
    """

    pass
