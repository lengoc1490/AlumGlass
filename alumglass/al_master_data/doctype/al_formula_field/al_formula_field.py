# -*- coding: utf-8 -*-
"""AL Formula Field — sổ đăng ký field công thức (thay registry hardcode trong JS)."""
import frappe
from frappe import _
from frappe.model.document import Document


class ALFormulaField(Document):
    """Một field công thức cụ thể trên một doctype / child table.

    Thay cho `FORMULA_DOCTYPE_REGISTRY` hardcode trong `public/js/formula_setup.js`:
    thêm field mới = thêm 1 record, KHÔNG sửa JS.
    """

    def validate(self):
        self._validate_unique_combo()

    def _validate_unique_combo(self):
        """Chặn trùng bộ (doctype, child_table, fieldname) — Frappe không hỗ trợ
        unique theo tổ hợp nhiều cột nên phải kiểm tay ở đây.

        `target_doctype` là fieldname thật trong DB: KHÔNG đặt tên là `doctype`
        được vì đó là từ khoá dành riêng của Frappe (xem
        `frappe/model/base_document.py::_reserved_keywords`).
        """
        if not (self.target_doctype and self.fieldname):
            return

        filters = {
            "target_doctype": self.target_doctype,
            "child_table": self.child_table or "",
            "fieldname": self.fieldname,
        }
        # Bản ghi mới có thể chưa có tên (hash sinh sau validate) ⇒ chỉ thêm
        # điều kiện "khác chính nó" khi đã có tên thật.
        if self.name and not self.is_new():
            filters["name"] = ["!=", self.name]

        duplicate = frappe.db.exists("AL Formula Field", filters)
        if duplicate:
            frappe.throw(_(
                "Field {0} trên {1}{2} đã được đăng ký ở bản ghi {3}."
            ).format(
                frappe.bold(self.fieldname),
                frappe.bold(self.target_doctype),
                " / " + frappe.bold(self.child_table) if self.child_table else "",
                frappe.bold(duplicate),
            ), title=_("Trùng đăng ký field công thức"))
