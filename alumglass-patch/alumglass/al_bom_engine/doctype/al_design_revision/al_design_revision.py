import frappe
from frappe.model.document import Document


class ALDesignRevision(Document):
    """Thay đổi thiết kế/spec - có thể trigger BOM Version mới."""

    def on_update(self):
        old = self.get_doc_before_save()
        if not old:
            return
        if (self.workflow_state == "Approved" and old.workflow_state != "Approved"
            and self.requires_new_bom_version and not self.new_bom_version):
            self._create_new_bom_version()

    def _create_new_bom_version(self):
        if not self.bom:
            return
        existing = frappe.get_all("AL BOM Version", filters={"bom": self.bom},
                                   fields=["version_name"], order_by="creation DESC", limit=1)
        ver_num = 1
        if existing:
            try: ver_num = int(existing[0]["version_name"].replace("v","").split(".")[0]) + 1
            except: ver_num = 2
        doc = frappe.new_doc("AL BOM Version")
        doc.bom = self.bom
        doc.version_name = f"v{ver_num}.0"
        doc.valid_from = frappe.utils.now()
        doc.workflow_state = "Draft"
        # V6 P11: dùng ignore_permissions=True — đây là hệ quả TỰ ĐỘNG của
        # hành động "Duyệt" AL Design Revision (role AL Design Reviewer),
        # không phải người dùng chủ động bấm "New" trên AL BOM Version. Sau
        # khi thêm Workflow thật + role duyệt tách biệt (setup_workflows.py),
        # AL Design Reviewer KHÔNG có quyền create trên AL BOM Version (đúng
        # chủ ý — người duyệt thiết kế không nên tự tạo version tuỳ ý) →
        # nếu không có ignore_permissions=True ở đây, việc Duyệt Design
        # Revision sẽ throw PermissionError ngay khi cố tự tạo version mới.
        doc.insert(ignore_permissions=True)
        self.new_bom_version = doc.name
