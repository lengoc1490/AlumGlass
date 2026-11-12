# -*- coding: utf-8 -*-
"""AL Common Variable — biến dùng chung, khai bằng dữ liệu."""
from frappe.model.document import Document


class ALCommonVariable(Document):
    """Một biến dùng chung (W_mm, TONG_M2, ...).

    Trước đây danh sách này viết tay trong `api/__init__.py`; nay khai ở đây
    để thêm biến không phải sửa code.
    """

    pass
