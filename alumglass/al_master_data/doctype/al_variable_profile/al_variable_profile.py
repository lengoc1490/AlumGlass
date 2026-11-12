# -*- coding: utf-8 -*-
"""AL Variable Profile — danh mục biến theo ngữ cảnh (controller)."""
import json

import frappe
from frappe import _
from frappe.model.document import Document


class ALVariableProfile(Document):
    """Profile quyết định bộ biến nào NGƯỜI DÙNG thấy khi gõ công thức.

    Đây chỉ là lớp *gợi ý / lọc* — KHÔNG tham gia resolve giá trị lúc tính
    giá, nên sửa/xoá profile không làm đổi số tiền của BOM đã tính.
    """

    def validate(self):
        # Chặn sớm `only_fields` sai định dạng: lỗi cấu hình ở đây sẽ làm
        # autocomplete lọc sai âm thầm (không ai thấy biến), khó lần ra.
        for row in self.get("rules") or []:
            raw = (row.get("only_fields") or "").strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                frappe.throw(_(
                    "Rule dòng {0}: 'Chỉ hiện ở field' phải là JSON list. "
                    "Ví dụ: [\"qty\",\"width\"]"
                ).format(row.idx))
            if not isinstance(parsed, list):
                frappe.throw(_(
                    "Rule dòng {0}: 'Chỉ hiện ở field' phải là JSON list."
                ).format(row.idx))
