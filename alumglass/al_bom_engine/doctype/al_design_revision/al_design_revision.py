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
        doc.insert()
        self.new_bom_version = doc.name
