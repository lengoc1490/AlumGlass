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


def initial_workflow_state(doctype="AL BOM Version", default="Draft"):
    """Trạng thái ĐẦU của Workflow đang bật cho `doctype` (đọc từ config trong DB).

    Vì sao cần: lõi Frappe CHỈ cho phép insert trực tiếp vào trạng thái đầu —
    `frappe/model/workflow.py::validate_workflow` coi chứng từ MỚI (`_doc_before_save`
    rỗng) là đang ở `workflow.states[0]`, chuyển sang state khác là throw
    WorkflowPermissionError. KHÔNG có cờ `ignore_workflow` trong lõi (grep toàn
    repo frappe: chỉ có `ignore_permissions`, mà nó chỉ bỏ qua PERMISSION).
    Nên lấy state đầu từ `install_workflows.py` (Workflow AL BOM Version: Draft)
    thay vì hardcode — đổi Workflow trong UI là code tự theo.
    """
    workflow_name = frappe.db.get_value(
        "Workflow", {"document_type": doctype, "is_active": 1}, "name"
    )
    if not workflow_name:
        return default
    rows = frappe.get_all(
        "Workflow Document State",
        filters={"parent": workflow_name},
        fields=["state"],
        order_by="idx asc",
        limit=1,
    )
    return rows[0]["state"] if rows else default


def create_bom_version_doc(bom_code, workflow_state=None):
    """Tạo AL BOM Version mới từ BOM hiện tại, ở trạng thái ĐẦU của Workflow.

    `before_insert` của AL BOM Version tự snapshot BOM Set + Cost Template +
    Pricing Dimension.

    ⛔ KHÔNG insert thẳng vào "Published" được: insert là chứng từ MỚI nên lõi
    Frappe luôn coi là đang ở trạng thái đầu và chặn mọi bước nhảy
    (`WorkflowPermissionError`) — `flags.ignore_permissions` KHÔNG cứu được vì
    nó không phải cơ chế bỏ-qua-Workflow. Muốn lên Published: tạo version ở
    trạng thái đầu rồi bấm nút chuyển trạng thái trên form (Đệ trình → Duyệt →
    Xuất bản) — lúc đó `on_update` mới set `current_version` trên AL BOM.

    Tham số `workflow_state` chỉ để tường minh trạng thái đầu; truyền state
    khác sẽ throw ngay tại đây với thông báo rõ, thay vì để lõi Frappe ném ra
    lỗi khó hiểu.
    """
    if not bom_code:
        frappe.throw("BOM code là bắt buộc")
    expected_state = initial_workflow_state()
    if workflow_state is None:
        workflow_state = expected_state
    elif workflow_state != expected_state:
        frappe.throw(
            f"AL BOM Version chỉ tạo được ở trạng thái '{expected_state}' "
            f"(trạng thái đầu của Workflow) — Frappe chặn mọi chuyển trạng thái "
            f"ngay khi tạo mới, không có cờ nào bỏ qua. Muốn "
            f"'{workflow_state}': tạo version ở '{expected_state}' rồi dùng các "
            f"nút chuyển trạng thái trên form (Đệ trình → Duyệt → Xuất bản)."
        )
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
    """Nút "Tạo BOM Version mới" trên AL BOM form — tạo version ở trạng thái đầu
    của Workflow (mặc định "Draft").

    Trả về tên version mới để client refresh + thông báo.
    """
    doc = create_bom_version_doc(bom_code)
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
