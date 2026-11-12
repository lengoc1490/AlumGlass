# -*- coding: utf-8 -*-
"""AL Variable Profile Rule — một luật Include/Exclude trong profile."""
from frappe.model.document import Document


class ALVariableProfileRule(Document):
    """Dòng luật lọc biến.

    Việc khớp luật nằm ở `alumglass/variable_sources/rules.py` (thuần Python,
    không import frappe) để test được bằng `python3 -I` và để catalog core
    không phụ thuộc ORM. Controller này cố ý rỗng.
    """

    pass
