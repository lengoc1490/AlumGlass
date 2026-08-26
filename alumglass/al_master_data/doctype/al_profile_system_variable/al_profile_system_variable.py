# -*- coding: utf-8 -*-
# Copyright (c) 2026, NxCom and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ALProfileSystemVariable(Document):
    """Child table — biến hệ thống bổ sung theo hệ profile.

    variable: Link → AL Variable Library
    value:    Data (số hoặc công thức)
    is_active: Check — chỉ dùng row active.
    """
    pass
