# -*- coding: utf-8 -*-
"""AL Variable Cross Row — khai báo child table được gợi ý biến chéo dòng."""
from frappe.model.document import Document


class ALVariableCrossRow(Document):
    """Cấu hình `items.<slug>.<field>` cho một child table.

    Catalog đọc bảng này để sinh `references`; cơ chế resolve cross-row của
    runtime (normalize + inputs["items"]) KHÔNG đổi.
    """

    pass
