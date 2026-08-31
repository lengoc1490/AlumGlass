"""Cài đặt Frappe Workflow THẬT cho các doctype đang dùng `workflow_state`
kiểu Select tự chế (kiểm tra chuyển trạng thái viết tay rải rác trong .py).

★ VẤN ĐỀ ĐÃ SỬA: `workflow_state` (Select) tự nó KHÔNG chặn được ai chuyển
sang trạng thái nào — chỉ là 1 field text bình thường, ai có quyền write
đều sửa được trực tiếp (kể cả nhảy cóc Draft -> Published bỏ qua duyệt).
Toàn bộ enforcement trước đây chỉ có ở vài chỗ `if self.workflow_state ==
"Approved": frappe.throw(...)` (business rule, KHÔNG phải role-gating).

★ GIẢI PHÁP: dùng đúng doctype `Workflow` có sẵn của Frappe — data-driven
100% (đổi role được duyệt, thêm trạng thái mới... đều qua UI/data, không
sửa code). Field `workflow_state` GIỮ NGUYÊN trên các doctype (Workflow chỉ
cần TÊN field này tồn tại, không cần đổi schema) — Frappe tự sinh:
  - Nút hành động ("Submit for Approval", "Approve"...) trên form, chỉ hiện
    với role được `allowed` ở đúng transition đó.
  - Chặn sửa `workflow_state` trực tiếp ngoài quy trình (kể cả qua Bulk Edit).
  - `allow_edit` per state — giới hạn AI được sửa các field khác khi doc
    đang ở trạng thái đó.
  - Audit trail đầy đủ (ai chuyển trạng thái nào lúc nào) qua Version log.

★ QUAN TRỌNG: logic nghiệp vụ hiện có trong .py (vd
`al_bom_version.py::_guard_published_immutability`,
`al_design_revision.py::_create_new_bom_version`,
`al_change_order.py::validate` check `customer_approval`/`internal_approval`)
KHÔNG bị thay thế — Workflow transition chỉ set field + gọi `doc.save()`
như bình thường, nên `validate()`/`on_update()` vẫn chạy y hệt trước giờ.
Đây là 2 TẦNG khác nhau:
  - Workflow = ai được phép bấm nút chuyển trạng thái nào (role-gating + UX).
  - .py validate()/on_update() = ràng buộc dữ liệu bất biến sau khi ở 1
    trạng thái nào đó (business rule, Workflow không thay được).
Với `AL Change Order`, thêm `condition` ở transition Pending→Approved
(`doc.customer_approval and doc.internal_approval`) để ẩn hẳn nút "Approve"
tới khi đủ điều kiện — validate() cũ VẪN GIỮ NGUYÊN làm lưới an toàn backend
(phòng trường hợp ai gọi thẳng API bỏ qua UI).

Gọi từ `hooks.py::_after_migrate` (idempotent — xóa & tạo lại mỗi lần chạy,
an toàn vì Workflow doctype không lưu dữ liệu nghiệp vụ, chỉ lưu cấu hình
transition — xóa/tạo lại không ảnh hưởng gì tới các document đã có
`workflow_state` hiện tại).
"""
import frappe


# ── Khai báo TOÀN BỘ workflow bằng data (không viết logic if/else tay) ──
# style: "" (mặc định/xám), "Warning" (cam), "Success" (xanh lá),
#        "Danger" (đỏ), "Primary" (xanh dương) — màu badge trên list view.
WORKFLOWS = [
    {
        "workflow_name": "AL BOM Version Workflow",
        "document_type": "AL BOM Version",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": "AL BOM Manager", "style": ""},
            {"state": "Pending Approval", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Warning"},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Primary"},
            {"state": "Published", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Success"},
            {"state": "Retired", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Danger"},
        ],
        "transitions": [
            {"state": "Draft", "action": "Submit for Approval",
             "next_state": "Pending Approval", "allowed": "AL BOM Manager"},
            {"state": "Pending Approval", "action": "Approve",
             "next_state": "Approved", "allowed": "AL Technical Admin"},
            {"state": "Pending Approval", "action": "Reject",
             "next_state": "Draft", "allowed": "AL Technical Admin"},
            {"state": "Approved", "action": "Publish",
             "next_state": "Published", "allowed": "AL Technical Admin"},
            {"state": "Published", "action": "Retire",
             "next_state": "Retired", "allowed": "AL BOM Manager"},
        ],
    },
    {
        "workflow_name": "AL Change Order Workflow",
        "document_type": "AL Change Order",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": "AL Site Engineer", "style": ""},
            {"state": "Pending", "doc_status": "0",
             "allow_edit": "AL BOM Manager", "style": "Warning"},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL BOM Manager", "style": "Success"},
            {"state": "Rejected", "doc_status": "0",
             "allow_edit": "AL BOM Manager", "style": "Danger"},
            {"state": "Implemented", "doc_status": "0",
             "allow_edit": "AL Site Engineer", "style": "Primary"},
        ],
        "transitions": [
            {"state": "Draft", "action": "Submit", "next_state": "Pending",
             "allowed": "AL Site Engineer"},
            {"state": "Draft", "action": "Submit", "next_state": "Pending",
             "allowed": "AL Sales User"},
            # ★ Điều kiện lấy ĐÚNG từ validate() cũ (al_change_order.py) — nay
            # ẩn hẳn nút "Approve" tới khi đủ 2 chữ ký duyệt, thay vì cho bấm
            # rồi mới throw lỗi. validate() cũ VẪN GIỮ làm lưới an toàn backend.
            {"state": "Pending", "action": "Approve", "next_state": "Approved",
             "allowed": "AL BOM Manager",
             "condition": "doc.customer_approval and doc.internal_approval"},
            {"state": "Pending", "action": "Reject", "next_state": "Rejected",
             "allowed": "AL BOM Manager"},
            {"state": "Approved", "action": "Implement", "next_state": "Implemented",
             "allowed": "AL Site Engineer"},
        ],
    },
    {
        "workflow_name": "AL Dynamic Item Rule Version Workflow",
        "document_type": "AL Dynamic Item Rule Version",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": "AL Technical Admin", "style": ""},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Primary"},
            {"state": "Published", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Success"},
            {"state": "Retired", "doc_status": "0",
             "allow_edit": "AL Technical Admin", "style": "Danger"},
        ],
        "transitions": [
            # Rule ảnh hưởng trực tiếp tới việc resolve item/giá toàn hệ thống
            # — độc quyền AL Technical Admin ở MỌI bước (khớp quy ước đã có
            # sẵn cho AL Quantity Calc Method.calc_fn, xem install_roles.py).
            {"state": "Draft", "action": "Approve", "next_state": "Approved",
             "allowed": "AL Technical Admin"},
            {"state": "Approved", "action": "Publish", "next_state": "Published",
             "allowed": "AL Technical Admin"},
            {"state": "Published", "action": "Retire", "next_state": "Retired",
             "allowed": "AL Technical Admin"},
        ],
    },
    {
        "workflow_name": "AL Design Revision Workflow",
        "document_type": "AL Design Revision",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": "AL Site Engineer", "style": ""},
            {"state": "Under Review", "doc_status": "0",
             "allow_edit": "AL BOM Manager", "style": "Warning"},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL BOM Manager", "style": "Success"},
            {"state": "Implemented", "doc_status": "0",
             "allow_edit": "AL Site Engineer", "style": "Primary"},
        ],
        "transitions": [
            {"state": "Draft", "action": "Submit for Review",
             "next_state": "Under Review", "allowed": "AL Site Engineer"},
            {"state": "Under Review", "action": "Approve",
             "next_state": "Approved", "allowed": "AL BOM Manager"},
            {"state": "Under Review", "action": "Send Back",
             "next_state": "Draft", "allowed": "AL BOM Manager"},
            # Approve -> Implemented: kích hoạt on_update() tạo BOM Version mới
            # (al_design_revision.py::_create_new_bom_version) — KHÔNG đổi.
            {"state": "Approved", "action": "Mark Implemented",
             "next_state": "Implemented", "allowed": "AL Site Engineer"},
        ],
    },
]


def install_workflows():
    """Idempotent — gọi lại bao nhiêu lần cũng an toàn (xóa & tạo lại theo
    đúng WORKFLOWS ở trên). KHÔNG đụng tới dữ liệu document đã có (chỉ xóa
    record Workflow — bảng cấu hình transition, không phải dữ liệu nghiệp vụ).
    Bỏ qua êm nếu document_type chưa tồn tại (vd module chưa migrate xong).
    """
    for wf in WORKFLOWS:
        if not frappe.db.exists("DocType", wf["document_type"]):
            continue
        if frappe.db.exists("Workflow", wf["workflow_name"]):
            frappe.delete_doc("Workflow", wf["workflow_name"],
                               force=True, ignore_permissions=True)

        doc = frappe.new_doc("Workflow")
        doc.workflow_name = wf["workflow_name"]
        doc.document_type = wf["document_type"]
        doc.workflow_state_field = "workflow_state"
        doc.is_active = 1
        doc.send_email_alert = 0
        for s in wf["states"]:
            doc.append("states", {
                "state": s["state"],
                "doc_status": s["doc_status"],
                "allow_edit": s["allow_edit"],
                "style": s.get("style") or "",
            })
        for t in wf["transitions"]:
            doc.append("transitions", {
                "state": t["state"],
                "action": t["action"],
                "next_state": t["next_state"],
                "allowed": t["allowed"],
                "condition": t.get("condition") or "",
            })
        doc.insert(ignore_permissions=True)
