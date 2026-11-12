# -*- coding: utf-8 -*-
"""AL Variable Settings — cấu hình chung cho Variable Catalog (Single).

Ba thứ sống ở đây:
- `default_profile`: profile dùng khi doctype ĐÃ khai field Link tới
  `AL Variable Profile` nhưng bản ghi để trống.
- `common_variables`: thay danh sách 8 biến BOM input từng viết tay trong code.
- `row_literals`: thay danh sách row literal từng viết tay trong code.
"""
from frappe.model.document import Document


class ALVariableSettings(Document):
    """Single — không có logic riêng; mọi giá trị được đọc qua catalog."""

    pass
