import frappe
from frappe.model.document import Document


class ALBOM(Document):
    """BOM - liên kết Bom Set + Cost Template + Accessory Set."""

    def validate(self):
        if self.bom_set and not frappe.db.exists("AL Bom Set", self.bom_set):
            frappe.throw(f"BOM Set '{self.bom_set}' không tồn tại")
        if self.default_cost_template and not frappe.db.exists(
            "AL Cost Template", self.default_cost_template
        ):
            frappe.throw(f"Cost Template '{self.default_cost_template}' không tồn tại")


def next_version_name(bom_code):
    """Version name kế tiếp cho BOM: v1.0, v2.0, ... (tăng theo version hiện có)."""
    existing = frappe.get_all(
        "AL BOM Version",
        filters={"bom": bom_code},
        fields=["version_name"],
        order_by="creation DESC",
        limit=1,
    )
    if not existing:
        return "v1.0"
    try:
        major = int(str(existing[0]["version_name"]).replace("v", "").split(".")[0])
        return f"v{major + 1}.0"
    except (ValueError, IndexError, AttributeError):
        return "v2.0"


def create_bom_version_doc(bom_code, workflow_state="Draft"):
    """Tạo AL BOM Version mới từ BOM hiện tại.

    `before_insert` của AL BOM Version tự snapshot BOM Set + Cost Template +
    Pricing Dimension. workflow_state "Published" → `on_update` tự set
    `current_version` trên AL BOM (engine B0 auto-create dùng).
    """
    if not bom_code:
        frappe.throw("BOM code là bắt buộc")
    bom = frappe.get_doc("AL BOM", bom_code)
    doc = frappe.new_doc("AL BOM Version")
    doc.bom = bom.name
    doc.version_name = next_version_name(bom.name)
    doc.valid_from = frappe.utils.now()
    doc.workflow_state = workflow_state
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc


@frappe.whitelist()
def create_bom_version(bom_code):
    """Nút "Tạo BOM Version mới" trên AL BOM form — tạo version Draft.

    Trả về tên version mới để client refresh + thông báo.
    """
    doc = create_bom_version_doc(bom_code, workflow_state="Draft")
    frappe.db.commit()
    return {
        "name": doc.name,
        "version_name": doc.version_name,
        "workflow_state": doc.workflow_state,
    }


@frappe.whitelist()
def get_bom_structure(bom_code):
    """Trả về toàn bộ cấu trúc BOM."""
    bom = frappe.get_doc("AL BOM", bom_code)
    bom_set = frappe.get_doc("AL Bom Set", bom.bom_set)
    return {
        "bom": bom.as_dict(),
        "bom_set": bom_set.as_dict(),
        "items": [item.as_dict() for item in bom_set.items],
    }
