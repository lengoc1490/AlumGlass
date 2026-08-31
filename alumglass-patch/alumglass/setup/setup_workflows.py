# -*- coding: utf-8 -*-
"""V6 P11 — Chuyển 4 doctype đang "tự chế" workflow_state (Select field +
if/elif rải rác trong .py) sang dùng Workflow THẬT của Frappe.

Trước bản vá này: `workflow_state` chỉ là 1 Select field thường, mọi kiểm
soát chuyển trạng thái nằm rải rác trong code Python (al_bom_version.py,
al_change_order.py, al_design_revision.py...) — ai có quyền `write` trên
doctype là sửa được field này thành BẤT KỲ giá trị nào, không phân biệt
role/thứ tự chuyển trạng thái hợp lệ.

Sau bản vá: dùng đúng doctype `Workflow` của Frappe — 100% data-driven
(State + Transition là record DB, sửa qua UI Workflow Builder, KHÔNG cần
sửa code khi đổi luật duyệt) và có SẴN miễn phí:
  - Nút hành động tự sinh trên form theo đúng state hiện tại + role user
  - Chặn quyền theo role TẠI TỪNG transition (chặt hơn field-level write)
  - Timeline tự ghi nhận ai chuyển trạng thái khi nào (Version doctype)
  - `condition` (Python expr trên `doc`) — vd Change Order chỉ cho
    Pending → Approved khi `doc.customer_approval and doc.internal_approval`,
    ẩn hẳn nút nếu chưa đủ điều kiện thay vì để user bấm rồi mới bị throw.

Thiết kế maker-checker: role "editor" hiện có (AL BOM Manager, AL Site
Engineer — đã cấp quyền qua install_roles.py) tạo/sửa bản nháp; 4 role MỚI
dưới đây (AL BOM Approver, AL Construction Manager, AL Formula Rule
Approver, AL Design Reviewer) là người DUYỆT — tách biệt người tạo và
người duyệt, đúng nguyên tắc kiểm soát nội bộ.

⚠ LƯU Ý KỸ THUẬT: `Workflow Document State.allow_edit` là Link ĐƠN tới
1 Role (không multi-value). Vì vậy state "Draft" để `allow_edit` RỖNG —
dựa hoàn toàn vào DocPerm gốc (đã giới hạn write cho đúng role editor qua
install_roles.py) thay vì khoá thêm ở tầng Workflow; chỉ state đang chờ
duyệt/đã duyệt mới gán `allow_edit` = role duyệt tương ứng.

⚠ LƯU Ý CHO CODE BACKEND TỰ TẠO/ĐỔI workflow_state (KHÔNG qua nút UI):
Frappe Workflow chỉ chặn transition khi save đi qua permission check bình
thường. Code hiện có tạo AL BOM Version với workflow_state="Draft" ngay
lúc insert (`al_bom.py::create_bom_version_doc`, `al_design_revision.py::
_create_new_bom_version`) — insert lần đầu KHÔNG bị coi là "transition"
(không có state trước đó) nên không bị chặn, vẫn hoạt động bình thường.
Riêng seed data (`setup/seed_demo_data.py`) tạo version thẳng ở trạng thái
"Published" — script này LUÔN dùng `doc.insert(ignore_permissions=True)`
(hàm `_ins()`), nên bỏ qua luôn permission check của Workflow — an toàn,
không cần sửa gì thêm.
"""
import frappe


# ── 1. Role duyệt (maker-checker) — MỚI, tách biệt role "editor" hiện có ──
APPROVER_ROLES = [
    "AL BOM Approver",           # Duyệt/Phát hành AL BOM Version
    "AL Construction Manager",   # Duyệt AL Change Order (phát sinh công trình)
    "AL Formula Rule Approver",  # Duyệt/Phát hành AL Dynamic Item Rule Version
    "AL Design Reviewer",        # Duyệt AL Design Revision
]

# ── 2. Quyền cơ bản (read/write) cho role duyệt trên đúng doctype của nó ──
# Role "editor" hiện có (AL BOM Manager, AL Site Engineer) đã có đủ CRUD
# qua install_roles.py — KHÔNG đụng vào. Chỉ thêm quyền tối thiểu cho role
# duyệt mới: cần read + write để mở form và bấm nút chuyển trạng thái;
# KHÔNG cấp create/delete (người duyệt không tự tạo/xóa bản ghi).
APPROVER_DOCTYPE_PERMISSIONS = {
    "AL BOM Version": {"AL BOM Approver": {"read": 1, "write": 1, "report": 1, "export": 1}},
    "AL Change Order": {"AL Construction Manager": {"read": 1, "write": 1, "report": 1, "export": 1}},
    "AL Dynamic Item Rule Version": {"AL Formula Rule Approver": {"read": 1, "write": 1, "report": 1, "export": 1}},
    "AL Design Revision": {"AL Design Reviewer": {"read": 1, "write": 1, "report": 1, "export": 1}},
}

# ── 3. Định nghĩa Workflow — states + transitions (data-driven, không hardcode luật ở code khác) ──
# doc_status luôn "0" vì cả 4 doctype đều is_submittable=0 (không dùng cơ
# chế Submit/Cancel của Frappe, chỉ dùng Select-state workflow thuần).
WORKFLOWS = [
    {
        "workflow_name": "AL BOM Version Workflow",
        "document_type": "AL BOM Version",
        "states": [
            # Draft: allow_edit để trống — DocPerm gốc (install_roles.py) đã
            # giới hạn write cho đúng "AL BOM Manager" (+ System Manager),
            # không cần Workflow khoá thêm (allow_edit chỉ nhận 1 Role Link,
            # không multi-value — để trống = dùng nguyên base DocPerm).
            {"state": "Draft", "doc_status": "0", "allow_edit": ""},
            {"state": "Pending Approval", "doc_status": "0",
             "allow_edit": "AL BOM Approver"},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL BOM Approver"},
            {"state": "Published", "doc_status": "0",
             "allow_edit": ""},  # bất biến — _guard_published_immutability() trong code vẫn là lớp chặn thứ 2
            {"state": "Retired", "doc_status": "0", "allow_edit": ""},
        ],
        "transitions": [
            {"state": "Draft", "action": "Gửi duyệt", "next_state": "Pending Approval",
             "allowed": "AL BOM Manager"},
            {"state": "Pending Approval", "action": "Duyệt", "next_state": "Approved",
             "allowed": "AL BOM Approver"},
            {"state": "Pending Approval", "action": "Từ chối", "next_state": "Draft",
             "allowed": "AL BOM Approver"},
            {"state": "Approved", "action": "Phát hành", "next_state": "Published",
             "allowed": "AL BOM Approver"},
            {"state": "Published", "action": "Ngưng dùng", "next_state": "Retired",
             "allowed": "AL BOM Approver"},
        ],
    },
    {
        "workflow_name": "AL Change Order Workflow",
        "document_type": "AL Change Order",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": ""},
            {"state": "Pending", "doc_status": "0",
             "allow_edit": "AL Construction Manager"},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL Construction Manager"},
            {"state": "Rejected", "doc_status": "0",
             "allow_edit": "AL Site Engineer"},
            {"state": "Implemented", "doc_status": "0", "allow_edit": ""},
        ],
        "transitions": [
            {"state": "Draft", "action": "Gửi duyệt", "next_state": "Pending",
             "allowed": "AL Site Engineer"},
            # Điều kiện khớp ĐÚNG logic đã có trong validate() (al_change_order.py)
            # — thêm ở đây để ẨN nút nếu chưa đủ 2 chữ ký, thay vì để user bấm
            # rồi mới bị throw. validate() vẫn giữ nguyên làm lớp chặn thứ 2
            # (phòng trường hợp update field qua API/import bỏ qua workflow UI).
            {"state": "Pending", "action": "Duyệt", "next_state": "Approved",
             "allowed": "AL Construction Manager",
             "condition": "doc.customer_approval and doc.internal_approval"},
            {"state": "Pending", "action": "Từ chối", "next_state": "Rejected",
             "allowed": "AL Construction Manager"},
            {"state": "Rejected", "action": "Sửa lại", "next_state": "Draft",
             "allowed": "AL Site Engineer"},
            {"state": "Approved", "action": "Đã triển khai", "next_state": "Implemented",
             "allowed": "AL Construction Manager"},
        ],
    },
    {
        "workflow_name": "AL Dynamic Item Rule Version Workflow",
        "document_type": "AL Dynamic Item Rule Version",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": ""},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL Formula Rule Approver"},
            {"state": "Published", "doc_status": "0", "allow_edit": ""},
            {"state": "Retired", "doc_status": "0", "allow_edit": ""},
        ],
        "transitions": [
            {"state": "Draft", "action": "Duyệt", "next_state": "Approved",
             "allowed": "AL Formula Rule Approver"},
            {"state": "Approved", "action": "Trả về nháp", "next_state": "Draft",
             "allowed": "AL Formula Rule Approver"},
            {"state": "Approved", "action": "Phát hành", "next_state": "Published",
             "allowed": "AL Formula Rule Approver"},
            {"state": "Published", "action": "Ngưng dùng", "next_state": "Retired",
             "allowed": "AL Formula Rule Approver"},
        ],
    },
    {
        "workflow_name": "AL Design Revision Workflow",
        "document_type": "AL Design Revision",
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": ""},
            {"state": "Under Review", "doc_status": "0",
             "allow_edit": "AL Design Reviewer"},
            {"state": "Approved", "doc_status": "0",
             "allow_edit": "AL Design Reviewer"},
            {"state": "Implemented", "doc_status": "0", "allow_edit": ""},
        ],
        "transitions": [
            {"state": "Draft", "action": "Gửi review", "next_state": "Under Review",
             "allowed": "AL BOM Manager"},
            {"state": "Under Review", "action": "Trả về nháp", "next_state": "Draft",
             "allowed": "AL Design Reviewer"},
            {"state": "Under Review", "action": "Duyệt", "next_state": "Approved",
             "allowed": "AL Design Reviewer"},
            {"state": "Approved", "action": "Đã triển khai", "next_state": "Implemented",
             "allowed": "AL Design Reviewer"},
        ],
    },
]


def _upsert_docperm(dt_name, role_name, perm_values):
    """Tạo hoặc cập nhật 1 Custom DocPerm record (giống hệt helper trong
    install_roles.py — không import chéo module để tránh phụ thuộc thứ tự
    load lúc install, tự chứa trong file này)."""
    if not frappe.db.exists("Role", role_name):
        return
    existing = frappe.db.exists(
        "Custom DocPerm", {"parent": dt_name, "role": role_name})
    if existing:
        frappe.db.set_value("Custom DocPerm", existing, perm_values)
    else:
        docperm = frappe.new_doc("Custom DocPerm")
        docperm.parent = dt_name
        docperm.role = role_name
        docperm.permlevel = 0
        docperm.update(perm_values)
        docperm.insert(ignore_permissions=True)


def install_workflows():
    """Cài Role duyệt + quyền tối thiểu + Workflow thật cho 4 doctype.

    Idempotent: bỏ qua Workflow đã tồn tại (không ghi đè — nếu bạn đã tự
    chỉnh Workflow qua UI Workflow Builder sau khi cài lần đầu, hàm này sẽ
    KHÔNG ghi đè thay đổi của bạn). Gọi từ hooks.py _after_install và
    _after_migrate (giống pattern install_roles_and_permissions()).
    """
    # 1. Roles
    for role_name in APPROVER_ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({
                "doctype": "Role", "role_name": role_name, "desk_access": 1,
            }).insert(ignore_permissions=True)
            print(f"  Created Role: {role_name}")
    frappe.db.commit()

    # 2. Quyền tối thiểu cho role duyệt
    perm_count = 0
    for dt_name, role_perms in APPROVER_DOCTYPE_PERMISSIONS.items():
        if not frappe.db.exists("DocType", dt_name):
            continue
        for role_name, perm_values in role_perms.items():
            _upsert_docperm(dt_name, role_name, perm_values)
            perm_count += 1
    frappe.db.commit()
    print(f"  ✅ Approver role permissions: {perm_count} DocPerm records")

    # 3. Workflow (state machine thật)
    wf_count = 0
    for wf_def in WORKFLOWS:
        if not frappe.db.exists("DocType", wf_def["document_type"]):
            continue
        if frappe.db.exists("Workflow", wf_def["workflow_name"]):
            continue  # đã cài — không ghi đè tuỳ chỉnh của user

        wf = frappe.new_doc("Workflow")
        wf.workflow_name = wf_def["workflow_name"]
        wf.document_type = wf_def["document_type"]
        wf.is_active = 1
        wf.workflow_state_field = "workflow_state"
        wf.send_email_alert = 0

        for s in wf_def["states"]:
            wf.append("states", {
                "state": s["state"],
                "doc_status": s["doc_status"],
                "allow_edit": s["allow_edit"],  # string rỗng hoặc 1 Role — Link đơn, không multi-value
            })
        for t in wf_def["transitions"]:
            row = {
                "state": t["state"],
                "action": t["action"],
                "next_state": t["next_state"],
                "allowed": t["allowed"],
            }
            if t.get("condition"):
                row["condition"] = t["condition"]
            wf.append("transitions", row)

        wf.insert(ignore_permissions=True)
        wf_count += 1
        print(f"  Created Workflow: {wf_def['workflow_name']}")

    frappe.db.commit()
    print(f"  ✅ Workflows: {wf_count}/{len(WORKFLOWS)} created "
          f"(số còn lại đã tồn tại từ trước — không bị ghi đè)")
