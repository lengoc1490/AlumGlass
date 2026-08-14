# Hệ thống Phân quyền Frappe/ERPNext

> Tài liệu này mô tả toàn bộ kiến trúc và cơ chế phân quyền của Frappe Framework,
> áp dụng cho mọi app chạy trên nền tảng Frappe/ERPNext (v14+).

---

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Các khái niệm cốt lõi](#2-các-khái-niệm-cốt-lõi)
3. [Mô hình phân quyền](#3-mô-hình-phân-quyền)
4. [Các loại quyền (Rights)](#4-các-loại-quyền-rights)
5. [Cơ chế Permission Levels (Permlevel)](#5-cơ-chế-permission-levels-permlevel)
6. [Cơ chế If Owner](#6-cơ-chế-if-owner)
7. [User Permission chi tiết](#7-user-permission-chi-tiết)
8. [Document Sharing chi tiết](#8-document-sharing-chi-tiết)
9. [Hook-based Permissions](#9-hook-based-permissions)
10. [Permission Manager (UI)](#10-permission-manager-ui)
11. [Caching cơ chế phân quyền](#11-caching-cơ-chế-phân-quyền)
12. [Cách debug permission](#12-cách-debug-permission)
13. [Ví dụ thực tế](#13-ví-dụ-thực-tế)
14. [Lưu ý và Best Practices](#14-lưu-ý-và-best-practices)

---

## 1. Tổng quan kiến trúc

File trung tâm xử lý phân quyền:
- **`frappe/permissions.py`** — toàn bộ logic permission check
- **`frappe/model/db_query.py`** — build match conditions cho list query
- **`frappe/share.py`** — document sharing
- **`frappe/core/doctype/docperm/docperm.py`** — DocPerm DocType definition
- **`frappe/core/doctype/user_permission/user_permission.py`** — User Permission logic
- **`frappe/core/page/permission_manager/`** — UI permission manager

Hệ thống phân quyền Frappe hoạt động theo mô hình **Role-Based Access Control (RBAC)** mở rộng, kết hợp với nhiều cơ chế bổ sung:

| Cơ chế | Mô tả | Phạm vi |
|--------|-------|---------|
| **Role-based** | User → Role(s) → DocPerm → Rights | DocType-level |
| **Permission Level** | Kiểm soát field-level permissions theo cấp | Field-level |
| **If Owner** | Chủ sở hữu được quyền đặc biệt | Document-level |
| **User Permission** | Giới hạn bản ghi user được xem dựa trên link field | Record-level |
| **Sharing** | Chia sẻ tài liệu cho user khác với quyền cụ thể | Record-level |
| **Hook-based** | Override permission check bằng Python code | DocType/Document-level |

```
┌───────────────────────────────────────────────────────────┐
│                    Kiến trúc tổng thể                     │
├───────────────────────────────────────────────────────────┤
│  User                                                     │
│    │ assigned roles                                       │
│    ▼                                                      │
│  Has Role (N roles)                                       │
│    │ matched to DocPerm                                   │
│    ▼                                                      │
│  DocPerm / Custom DocPerm                                 │
│    ├── role + permlevel                                   │
│    ├── rights (read/write/create/delete/submit/...)       │
│    ├── if_owner                                           │
│    └── permlevel > 0 → field-level access                 │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Layer 1: DocType Permission (get_role_permissions)│   │
│  │  Layer 2: If Owner check                           │   │
│  │  Layer 3: User Permission (link-field restrict)    │   │
│  │  Layer 4: Controller Permission (has_permission)   │   │
│  │  Layer 5: Share Permission                         │   │
│  │  Layer 6: Permission Query Conditions (SQL)        │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

---

## 2. Các khái niệm cốt lõi

### 2.1 Role (Vai trò)

Role là đơn vị cơ bản nhất của phân quyền. Mỗi User được gán 1+ Role thông qua child table `Has Role`.

**Đặc điểm Role (DocType: `Role`):**
- **Autoname:** `field:role_name`
- **`desk_access`:** bật → user truy cập được Desk (System User)
- **`disabled`:** bật → role bị gỡ khỏi tất cả user
- **`two_factor_auth`:** bắt buộc 2FA
- **`restrict_to_domain`:** chỉ áp dụng trong domain cụ thể

**Các role tự động (AUTOMATIC_ROLES):**
```python
GUEST_ROLE = "Guest"            # Mọi user chưa login
ALL_USER_ROLE = "All"           # Mọi user (kể cả website user)
SYSTEM_USER_ROLE = "Desk User"  # User có desk_access
ADMIN_ROLE = "Administrator"    # Super admin — luôn có mọi quyền
```

**Nguyên tắc:**
- **Administrator** luôn bypass mọi permission check
- Guest chỉ có role "Guest"
- System User tự động có thêm "Desk User"
- Mọi user đều có "All" + "Guest"

**Lấy roles:**
```python
frappe.get_roles(user=None)  # → List[str]
# Administrator → tất cả roles trong hệ thống
# Guest → ["Guest"]
# User thường → roles từ Has Role + "All" + "Guest" + "Desk User"
```

### 2.2 Role Profile (Hồ sơ vai trò)

**DocType:** `Role Profile`

Role Profile gom nhiều Role vào một profile và gán cho User qua field `role_profile_name`. Khi đã dùng Role Profile, các role được quản lý tự động — không thêm/bớt thủ công trên User.

### 2.3 DocPerm (Permission Rule)

**DocType:** `DocPerm` — child table của `DocType`

Mỗi DocType có child table `permissions` chứa các DocPerm records:

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `role` | Link → Role | Role được áp dụng |
| `permlevel` | Int | Cấp độ permission |
| `if_owner` | Check | Chỉ áp dụng nếu user là owner |
| `select` | Check | Xem trong dropdown/link field |
| `read` | Check | Quyền đọc |
| `write` | Check | Quyền sửa |
| `create` | Check | Quyền tạo mới |
| `delete` | Check | Quyền xoá |
| `submit` | Check | Quyền submit |
| `cancel` | Check | Quyền cancel |
| `amend` | Check | Quyền amend |
| `print` | Check | Quyền in ấn |
| `email` | Check | Quyền gửi email |
| `report` | Check | Quyền report |
| `import` | Check | Quyền import |
| `export` | Check | Quyền export |
| `set_user_permissions` | Check | Quyền tạo User Permission |
| `share` | Check | Quyền share document |

### 2.4 Custom DocPerm

**DocType:** `Custom DocPerm`

Khi admin thay đổi permission qua UI, Frappe:
1. Copy toàn bộ DocPerm gốc → `Custom DocPerm` (nếu chưa có)
2. Chỉnh sửa trên `Custom DocPerm`
3. Khi đọc permissions: nếu có Custom DocPerm → dùng nó thay DocPerm gốc

```python
def get_doctypes_with_custom_docperms():
    return frappe.get_all("Custom DocPerm", pluck="parent", distinct=True)
```

### 2.5 User Permission (Giới hạn bản ghi)

**DocType:** `User Permission`

Giới hạn user chỉ thấy những bản ghi có giá trị link field khớp với `for_value`.

| Field | Mô tả |
|-------|-------|
| `user` | User bị giới hạn |
| `allow` | DocType làm khoá (vd: Customer, Warehouse) |
| `for_value` | Giá trị được phép (vd: "ABC Corp") |
| `is_default` | Giá trị mặc định khi tạo document mới |
| `apply_to_all_doctypes` | Áp dụng cho mọi doctype |
| `applicable_for` | Chỉ áp dụng cho doctype cụ thể |

### 2.6 Document Sharing

**DocType:** `DocShare`

User có quyền `share` trên DocType có thể chia sẻ document cụ thể cho user khác.

### 2.7 Custom Role

**DocType:** `Custom Role`

Gán role khác cho Page/Report (override role mặc định).

---

## 3. Mô hình phân quyền

### 3.1 Luồng kiểm tra quyền

Khi user thực hiện một hành động trên document, Frappe thực hiện theo thứ tự:

```
has_permission(doctype, ptype, doc)
  │
  ├── Administrator? → True (luôn được phép)
  │
  ├── Child table? → has_child_permission → kiểm tra parent
  │
  ├── Document-level check:
  │   ├── get_role_permissions(meta, user) → role + rights
  │   ├── Nếu có if_owner → áp dụng owner permissions
  │   └── Nếu không có quyền → check Share
  │
  ├── Document-specific check (if doc provided):
  │   ├── get_doc_permissions(doc, user)
  │   │   ├── has_controller_permissions → hook has_permission
  │   │   ├── get_role_permissions (cached)
  │   │   ├── Nếu is_submittable=0 → submit=0
  │   │   ├── Nếu allow_import=0 → import=0
  │   │   ├── Nếu có if_owner → merge owner perms
  │   │   └── has_user_permission → kiểm tra link fields
  │   └── Kiểm tra từng bước
  │
  └── List-level check (no doc):
      ├── get_role_permissions → có quyền read/select?
      ├── Nếu không → chỉ cho xem shared documents
      └── build_match_conditions → SQL restrictions
```

### 3.2 get_role_permissions (cốt lõi)

Hàm quan trọng nhất — trả về dict permissions tổng hợp từ tất cả roles của user:

```python
def get_role_permissions(doctype_meta, user=None, is_owner=None):
    roles = frappe.get_roles(user)
    applicable_permissions = [p for p in meta.permissions
                              if p.role in roles and p.permlevel == 0]

    perms = {"read": 0, "write": 0, ...}
    for ptype in rights:
        perms[ptype] = any(p.get(ptype) for p in applicable_permissions)

    # Nếu có if_owner → tách riêng owner permissions
    if has_if_owner_enabled:
        for ptype in rights:
            if only_if_owner(ptype):
                perms["if_owner"][ptype] = perms[ptype] and is_owner
                perms[ptype] = 1 if ptype in ("select", "read") else 0

    return perms
```

Kết quả được **cache trong frappe.local.role_permissions** theo key `(doctype, user, is_owner)`.

### 3.3 get_doc_permissions (trên một document cụ thể)

```python
def get_doc_permissions(doc, user=None, ptype=None):
    # 1. Kiểm tra controller permission hook
    if has_controller_permissions(doc, ptype, user) is False:
        return {ptype: 0}

    # 2. Lấy role permissions (đã cache)
    permissions = get_role_permissions(meta, user, is_owner=is_user_owner())

    # 3. Điều chỉnh theo meta flags
    if not meta.is_submittable: permissions["submit"] = 0
    if not meta.allow_import: permissions["import"] = 0

    # 4. Nếu có if_owner → merge owner perms
    if permissions.get("has_if_owner_enabled"):
        permissions.update(permissions.get("if_owner", {}))

    # 5. Kiểm tra User Permission
    if not has_user_permission(doc, user):
        if is_user_owner():
            permissions = permissions.get("if_owner", {})
            permissions["create"] = 0
        else:
            permissions = {}  # không quyền gì

    return permissions
```

### 3.4 Database-level: build_match_conditions

Khi user mở List View hoặc thực hiện query, Frappe tự động thêm SQL conditions:

```python
def build_match_conditions(self):
    role_permissions = frappe.permissions.get_role_permissions(...)
    self.shared = frappe.share.get_shared(self.doctype, self.user)

    # Nếu không có quyền read/select → chỉ shared docs
    if not role_permissions.get("select") and not role_permissions.get("read"):
        only_if_shared = True
        if not self.shared:
            raise PermissionError
        self.conditions.append(self.get_share_condition())
    else:
        if requires_owner_constraint(role_permissions):
            # Chỉ thấy document của chính mình
            match_conditions.append(owner_condition)
        elif role_permissions.get("read"):
            # Thêm user permission conditions
            self.add_user_permissions(user_permissions)

    # Thêm permission_query_conditions từ hooks
    doctype_conditions = self.get_permission_query_conditions()

    # Nếu có shared docs → OR với share condition
    if self.shared and conditions:
        conditions = f"({conditions}) or ({get_share_condition()})"
```

---

## 4. Các loại quyền (Rights)

Danh sách đầy đủ 18 quyền (defined in `frappe/permissions.py`):

```python
rights = (
    "select",    # Xem trong dropdown/link field (list các bản ghi)
    "read",      # Đọc nội dung document
    "write",     # Sửa document
    "create",    # Tạo mới document
    "delete",    # Xoá document
    "submit",    # Submit (chỉ với submittable doctypes)
    "cancel",    # Cancel submitted document
    "amend",     # Tạo bản amend (phiên bản mới từ cancelled)
    "print",     # In ấn
    "email",     # Gửi email
    "report",    # Xem trong report
    "import",    # Import dữ liệu
    "export",    # Export dữ liệu
    "set_user_permissions",  # Tạo User Permission cho doctype này
    "share",     # Chia sẻ document
)
```

**Phân nhóm:**

| Nhóm | Quyền | Mô tả |
|------|-------|-------|
| CRUD | `create`, `read`, `write`, `delete` | Thao tác cơ bản |
| Workflow | `submit`, `cancel`, `amend` | Dành cho submittable doctypes |
| Data | `import`, `export`, `report` | Thao tác dữ liệu hàng loạt |
| Giao tiếp | `print`, `email` | In ấn và gửi email |
| Quản trị | `select`, `share`, `set_user_permissions` | Quản lý truy cập |

> **`select` vs `read`:** `select` cho phép user thấy bản ghi trong dropdown (link field) dù không có `read`. Điều này cần thiết để user có thể chọn giá trị cho link field mà không cần đọc chi tiết document.

---

## 5. Cơ chế Permission Levels (Permlevel)

### Ý tưởng

- **permlevel = 0:** Document-level permissions — kiểm soát truy cập toàn bộ document
- **permlevel > 0:** Field-level permissions — kiểm soát field cụ thể

### Cách hoạt động

1. Mỗi field trong DocType JSON có thuộc tính `permlevel` (mặc định 0)
2. User cần có DocPerm với `permlevel` tương ứng để truy cập field đó
3. Permlevel chỉ có hiệu lực với field-level checks, không ảnh hưởng đến document-level

### Kiểm tra permlevel access

```python
meta.get_permlevel_access(ptype, user=None)
# → List[int] — danh sách permlevels user có quyền cho ptype
```

### Ứng dụng thực tế

Ví dụ: Field `salary` có `permlevel=1`:
- Tạo DocPerm cho role "HR Manager" với `permlevel=1, read=1`
- Chỉ HR Manager mới thấy/đọc được field `salary`
- Các role khác không thấy field này trong form

---

## 6. Cơ chế If Owner

### Mục đích

Cho phép chủ sở hữu document có quyền đặc biệt mà user khác không có.

### Cách hoạt động

Trong DocPerm:
- **`if_owner = 1`:** Quyền này **chỉ áp dụng** nếu user là owner của document

### Quy tắc xử lý

```python
# Trong get_role_permissions
if has_if_owner_enabled:
    for ptype in rights:
        # Nếu quyền CHỈ có với if_owner (không có perm without if_owner)
        if not has_permission_without_if_owner_enabled(ptype) and ptype != "create":
            perms["if_owner"][ptype] = pvalue and is_owner
            perms[ptype] = 1 if ptype in ("select", "read") else 0
```

### Ví dụ

DocPerm: Role "Employee", chỉ có `read=1, if_owner=1`:
- User có role Employee → có `select=1, read=1` (cơ bản)
- Trên document do user tạo → có **thêm** read từ if_owner (vẫn giữ nguyên)
  → Thực tế: user đã có read rồi, không thay đổi
- Nếu chỉ có `delete=1, if_owner=1`:
  → User có `select=1, read=1` tổng thể (để thấy document trong list)
  → Nhưng chỉ được delete document do mình tạo

---

## 7. User Permission chi tiết

### Mục đích

Hạn chế user chỉ thấy/tương tác với những bản ghi có liên quan đến một giá trị cụ thể.

### Cách hoạt động

```python
def has_user_permission(doc, user=None):
    user_permissions = get_user_permissions(user)

    # STEP 1: Kiểm tra trên chính doctype của document
    # VD: User chỉ được xem Customer "ABC Corp"
    if doctype in user_permissions:
        allowed = get_allowed_docs_for_doctype(...)
        if allowed and docname not in allowed:
            return False

    # STEP 2: Kiểm tra trên tất cả link fields
    # VD: User chỉ tạo được Sales Invoice cho Customer "ABC Corp"
    for field in meta.get_link_fields():
        if field.ignore_user_permissions: continue
        if field.options in user_permissions:
            if doc.get(field.fieldname) not in allowed:
                return False

    return True
```

### Ứng dụng cho List Query

```python
def add_user_permissions(self, user_permissions):
    for df in doctype_link_fields:
        if df.get("ignore_user_permissions"): continue
        values = user_permissions.get(df.options, {})
        if values:
            # Thêm SQL condition
            condition = f"`tab{doctype}`.`{fieldname}` in ({values})"
            match_conditions.append(condition)
```

### Cấu hình hệ thống

- **`apply_strict_user_permissions`:** Nếu bật, User Permission áp dụng ngay cả khi link field trống. Mặc định: tắt.

---

## 8. Document Sharing chi tiết

### Mục đích

Chia sẻ document cụ thể cho user khác — vượt qua rào cản role-based permissions.

### Cơ chế

**DocType:** `DocShare`

| Field | Mô tả |
|-------|-------|
| `share_doctype` | DocType của document được share |
| `share_name` | Tên document |
| `user` | User được share |
| `everyone` | Share cho tất cả (public) |
| `read` | Quyền đọc |
| `write` | Quyền sửa |
| `submit` | Quyền submit |
| `share` | Quyền share tiếp |

### API

```python
frappe.share.add(doctype, name, user, read=1, write=0, submit=0, share=0, everyone=0, notify=0)
frappe.share.remove(doctype, name, user)
frappe.share.set_permission(doctype, name, user, permission_to, value=1)
```

### Kiểm tra Share Permission

Khi user không có role-based permission, Frappe kiểm tra shared documents:

```python
# Trong has_permission
if not perm and not ignore_share_permissions:
    perm = false_if_not_shared()
```

### Share trong List Query

```python
# build_match_conditions
if self.shared and conditions:
    conditions = f"({conditions}) or ({self.get_share_condition()})"
```

Điều này có nghĩa: user thấy document trong list nếu **có role permission HOẶC document được shared**.

---

## 9. Hook-based Permissions

### 9.1 has_permission hook

Override permission check bằng controller method hoặc hook.

**Cách 1: Controller method**

Trong Python file của DocType:

```python
class MyDocType(Document):
    def has_permission(self, ptype, user=None):
        if ptype == "write":
            # Chỉ cho phép sửa nếu user là người tạo
            return self.owner == user
        return True  # None cũng được (fallthrough)
```

**Cách 2: Hooks**

Trong `hooks.py`:

```python
has_permission = {
    "Customer": "myapp.api.check_customer_permission",
    "*": "myapp.api.check_global_permission",
}
```

Hàm hook:

```python
def check_customer_permission(doc, ptype, user):
    if ptype == "delete":
        return False  # Không ai được xoá Customer
    return None  # Fallthrough → tiếp tục check mặc định
```

**Quy tắc:**
- Return `False` → từ chối truy cập
- Return `True` → cho phép (bỏ qua các check khác)
- Return `None` → tiếp tục check mặc định

### 9.2 permission_query_conditions hook

Thêm SQL conditions vào list query — dùng để filter bản ghi ở database level.

```python
# hooks.py
permission_query_conditions = {
    "Sales Invoice": "myapp.api.sales_invoice_permission_conditions",
}
```

```python
def sales_invoice_permission_conditions(user, doctype):
    if "Manager" in frappe.get_roles(user):
        return ""  # Manager thấy tất cả
    # User thường chỉ thấy invoice của phòng mình
    return """`tabSales Invoice`.`custom_department` =
              (SELECT `department` FROM `tabEmployee` WHERE `user` = {user})""".format(
        user=frappe.db.escape(user)
    )
```

Hooks được gọi từ `db_query.py`:

```python
def get_permission_query_conditions(self):
    conditions = []
    hooks = frappe.get_hooks("permission_query_conditions", {})
    condition_methods = hooks.get(self.doctype, []) + hooks.get("*", [])
    for method in condition_methods:
        if c := frappe.call(frappe.get_attr(method), self.user, doctype=self.doctype):
            conditions.append(c)

    # Server Script (Quản lý qua UI)
    if script := get_server_script_map().get("permission_query", {}).get(self.doctype):
        conditions.append(script.get_permission_query_conditions(self.user))

    return " and ".join(conditions) if conditions else ""
```

---

## 10. Permission Manager (UI)

**Route:** `/app/permission-manager`

**File:** `frappe/core/page/permission_manager/`

Chỉ **System Manager** mới truy cập được Permission Manager.

### Chức năng:

1. **Xem permissions** của một DocType hoặc Role
2. **Thêm permission rule** mới (role + permlevel)
3. **Sửa/xoá** permission rule
4. **Copy permissions** từ DocType khác
5. **Reset permissions** về mặc định

Khi thay đổi permission, hệ thống tự động validate:

```python
@frappe.whitelist()
def update_permission_property(doctype, role, permlevel, ptype, value=None, if_owner=0):
    setup_custom_perms(doctype)  # Tạo Custom DocPerm nếu chưa có
    # Update giá trị
    frappe.qb.update("Custom DocPerm").set(ptype, value).where(...).run()
    validate_permissions_for_doctype(doctype)
```

### Hạn chế:
- Không cho phép sửa permission của: DocType, Patch Log, Module Def, Transaction Log
- Role Administrator luôn ẩn khỏi Permission Manager
- Standard User Type roles không hiện

---

## 11. Caching cơ chế phân quyền

Frappe cache permissions ở 2 cấp:

### 11.1 In-memory cache (frappe.local)

```python
# frappe/local.py — trong cùng request
frappe.local.role_permissions  # dict với key (doctype, user, is_owner)
```

Cache này sống trong cùng request/connection. Hết request → tự động clear.

### 11.2 Redis cache

```python
frappe.cache().hget("roles", user, get)  # Cache roles của user
```

Cache roles của user trong Redis (TTL mặc định 6 giờ). Khi gán/thay đổi role, cache tự động invalidate.

### 11.3 Clear cache

Khi thay đổi permissions qua UI, Frappe tự động clear cache:

```python
def clear_permissions_cache():
    frappe.cache().delete_value("roles")
    frappe.cache().delete_value("user_permissions")
    frappe.cache().delete_value("doctype_meta")
```

---

## 12. Cách debug permission

### Kiểm tra quyền của user

```python
# Trong Python Console
import frappe

# Roles của user
frappe.get_roles("user@example.com")

# Role permissions cho một DocType
meta = frappe.get_meta("Sales Invoice")
frappe.permissions.get_role_permissions(meta, user="user@example.com")

# Document permissions cụ thể
doc = frappe.get_doc("Sales Invoice", "SINV-00001")
frappe.permissions.get_doc_permissions(doc, user="user@example.com")

# Kiểm tra nhanh
frappe.has_permission("Sales Invoice", "read", user="user@example.com")
frappe.has_permission("Sales Invoice", "write", "SINV-00001", user="user@example.com")

# User Permissions của user
frappe.permissions.get_user_permissions("user@example.com")

# Shared documents
frappe.share.get_shared("Sales Invoice", "user@example.com")
```

### Permission Logging

Khi `raise_exception=True` (mặc định), Frappe ghi log giải thích tại sao từ chối:

```python
frappe.flags["has_permission_check_logs"]  # List[str] — messages giải thích
```

Được in ra qua `msgprint`:

```python
@print_has_permission_check_logs
def has_permission(...):
    ...
```

### Report: Permitted Documents For User

**Route:** `/app/query-report/Permitted Documents For User`

Cho phép System Manager xem user được phép truy cập những document nào của một DocType.

---

## 13. Ví dụ thực tế

### Ví dụ 1: Sales User chỉ thấy Customer của mình

**Tạo User Permission:**
- User: `sales_rep@example.com`
- Allow: `Customer`
- For Value: `ABC Corp`
- Applicable For: `Sales Invoice`

**Kết quả:**
- User chỉ tạo được Sales Invoice cho Customer "ABC Corp"
- Trong List View Sales Invoice, chỉ thấy các invoice của "ABC Corp"

### Ví dụ 2: Manager được xem tất cả, nhân viên chỉ xem của mình

**DocPerm cho Sales Invoice:**

| Role | read | if_owner | write |
|------|------|----------|-------|
| Sales Manager | 1 | 0 | 1 |
| Sales User | 1 | 1 | 1 |

**Kết quả:**
- Sales Manager: thấy và sửa mọi Sales Invoice
- Sales User: được ghi nhận `read=1` tổng thể (vì có `if_owner` và cũng là owner)
  → thực tế: thấy tất cả trong list (read=1) nhưng chỉ sửa được của mình (write chỉ với if_owner)

### Ví dụ 3: Field-level permission cho lương

**Field setup:**
- Field `salary` trên Employee → `permlevel=1`

**DocPerm:**

| Role | permlevel | read |
|------|-----------|------|
| HR User | 0 | 1 |
| HR Manager | 1 | 1 |

**Kết quả:**
- HR User: thấy Employee nhưng không thấy field `salary`
- HR Manager: thấy cả field `salary`

### Ví dụ 4: Controller permission — không cho xoá Customer

```python
# Trong customer.py
class Customer(Document):
    def has_permission(self, ptype, user=None):
        if ptype == "delete":
            frappe.msgprint("Không được phép xoá Customer")
            return False
        return None  # Fallthrough
```

### Ví dụ 5: Permission Query Conditions — filter theo department

```python
# hooks.py
permission_query_conditions = {
    "Sales Invoice": "your_app.api.sales_invoice_permission_conditions"
}

# api.py
def sales_invoice_permission_conditions(user, doctype):
    if "Sales Manager" in frappe.get_roles(user):
        return ""  # Manager thấy tất cả
    employee = frappe.db.get_value("Employee", {"user": user}, "department")
    if employee:
        return """`tabSales Invoice`.`custom_department` = {dept}""".format(
            dept=frappe.db.escape(employee)
        )
    return "1=0"  # Không thấy gì
```

---

## 14. Lưu ý và Best Practices

### Thiết kế permissions

1. **Nguyên tắc Least Privilege:** Chỉ gán quyền tối thiểu cần thiết
2. **Không gán nhiều rule cho 1 role:** Thay vào đó, gán nhiều roles cho 1 user
3. **Dùng Role Profile cho user groups** để quản lý tập trung
4. **Tránh dùng Administrator cho user thường** — tạo role riêng

### User Permission

5. **Chỉ dùng User Permission khi thực sự cần** — nó ảnh hưởng performance (thêm JOIN/WHERE)
6. **Set `ignore_user_permissions=1` cho field không cần check** để tối ưu
7. **Kiểm tra `apply_strict_user_permissions`** — bật nếu cần check cả khi link field trống

### Hook permissions

8. **`has_permission` controller method** trả về `None` để fallthrough, `True/False` để quyết định
9. **`permission_query_conditions`** phải return SQL condition hợp lệ hoặc chuỗi rỗng
10. **Return `1=0`** nếu user không được thấy bất kỳ bản ghi nào

### Performance

11. Permissions được cache trong request — không sợ gọi nhiều lần
12. User Permission có thể gây chậm nếu có quá nhiều records — limit số lượng
13. `permission_query_conditions` chạy mỗi lần query list — tối ưu SQL

### Security

14. **Kiểm tra permission trong custom API endpoints:**
    ```python
    @frappe.whitelist()
    def my_api():
        frappe.has_permission("Sales Invoice", "write", throw=True)
        # hoặc
        if "Manager" not in frappe.get_roles():
            frappe.throw("Not permitted")
    ```
15. **Không dùng `ignore_permissions=True`** trừ khi thực sự cần
16. **Field-level permissions** chỉ áp dụng khi `apply_perm_level_on_api_calls` được bật
17. **Share permissions** không được kiểm tra qua API nếu `ignore_share_permissions=True`

### Permission Manager

18. Chỉ System Manager mới vào được Permission Manager
19. Khi thay đổi permission, Frappe tự động copy sang Custom DocPerm
20. Reset permissions sẽ xoá Custom DocPerm — quay về mặc định từ code

---

> *Tài liệu này dựa trên Frappe Framework v14+. Một số API có thể thay đổi ở phiên bản mới hơn.*

---

## 15. Case Study: Phân quyền phân hệ KPI

> Phần này phân tích một hệ thống phân quyền thực tế cho phân hệ KPI (Key Performance Indicator)
> gồm 9 DocTypes với nhiều tình huống phức tạp: đa cấp độ vai trò, giới hạn theo đơn vị,
> quyền thời gian, truy cập có điều kiện, và phân quyền theo chức năng (function-based).

### 15.1 Tổng quan các DocType và luồng nghiệp vụ

```
KPI Setting (Cấu hình chung)
       │
Measurement Scale (Thang đo)
       │
KPI Library (Thư viện KPI)
       │
       ├── KPI Assignment Template (Mẫu giao KPI)
       │         │
       │         ▼
       │    KPI Assignment (Bản giao KPI)
       │         │
       │         ▼
       │    KPI Data (Nhập liệu KPI)
       │         │
       │         ▼
       │    KPI Evaluation (Đánh giá KPI)
       │
KPI Group (Nhóm KPI) ─── phân loại thư viện
```

### 15.2 Ma trận phân quyền yêu cầu

#### 15.2.1 DocType Admin (Master Data)

Các DocType "master data" của phân hệ KPI — chỉ Admin mới có toàn quyền:

| DocType | Admin | Người dùng thường |
|---------|-------|-------------------|
| KPI Setting | CRUD + Menu | Ẩn hoàn toàn |
| Measurement Scale Completion Type | CRUD + Menu | Ẩn hoàn toàn |
| Measurement Scale Result Template | CRUD + Menu | Ẩn hoàn toàn |
| KPI Group | CRUD + Menu | Ẩn hoàn toàn |
| KPI Library | CRUD + Menu + Export + Search | Ẩn menu, nhưng Read-only khi được link đến từ KPI Assignment |

#### 15.2.2 DocType Nghiệp vụ

| DocType | Admin | Người dùng thường |
|---------|-------|-------------------|
| KPI Assignment Template | CRUD + Menu | Ẩn hoàn toàn |
| KPI Assignment | CRUD + Menu | Xem theo đơn vị, sửa có điều kiện |
| KPI Data | Xem toàn bộ, sửa nếu được phân công | Xem theo đơn vị, nhập theo phân công, sửa trong thời hạn |
| KPI Evaluation | Xem toàn bộ, đánh giá theo vai trò | Xem + đánh giá theo đơn vị |

### 15.3 Phân tích các tình huống phân quyền & Giải pháp

Dưới đây là tất cả các tình huống phân quyền xuất hiện trong hệ thống KPI, phân loại theo cơ chế Frappe tương ứng.

---

#### TÌNH HUỐNG 1: Role-based CRUD cơ bản (Admin vs User)

**Mô tả:** Một số DocType (KPI Setting, Measurement Scale, KPI Group, KPI Assignment Template) chỉ dành cho Admin. Người dùng thường không được thấy menu.

**Giải pháp Frappe — Role + DocPerm:**

```python
# 1. Tạo 2 roles:
#    - "KPI Admin" → desk_access = 1
#    - "KPI User"  → desk_access = 1 (nếu cần dùng các chức năng khác)

# 2. DocPerm cho KPI Setting:
#    Role: KPI Admin → read=1, write=1, create=1, delete=1
#    (Không tạo DocPerm nào cho KPI User → user không có quyền)

# 3. Trong hooks.py:
#    KPI Setting (và các master data) cần set "Restrict to domain" nếu có
#    Hoặc đơn giản: chỉ KPI Admin mới có DocPerm → user khác không thấy
```

**Hạn chế truy cập menu (workspace):**
```python
# Trong Workspace setting, chỉ cho phép Role "KPI Admin" thấy các trang liên quan
# Workspace → Set "KPI Admin" trong "Roles" column
```

---

#### TÌNH HUỐNG 2: Conditional Read-only — Thư viện KPI

**Mô tả:** Người dùng thường hoàn toàn không thấy menu Thư viện KPI. Nhưng khi mở KPI Assignment, user có thể bấm "Xem chi tiết" KPI được giao — **chỉ xem (Read-only)**, không được:
- Chỉnh sửa
- Chuyển sang KPI khác
- Mở danh sách toàn bộ thư viện

**Giải pháp — Controller Permission + Custom Button:**

```python
# GIẢI PHÁP KẾT HỢP:

# Bước 1: Role permission → KPI User không có quyền list KPI Library
# DocPerm cho KPI Library: chỉ KPI Admin có read, KPI User không có gì

# Bước 2: Trong KPI Assignment form, custom button "Xem chi tiết KPI"
# dùng frappe.call API endpoint riêng, không dùng route mặc định

# Bước 3: API endpoint trả về KPI data đã được format (read-only)
@frappe.whitelist()
def get_kpi_detail(kpi_name):
    """API cho nút 'Xem chi tiết KPI' trên KPI Assignment"""
    user = frappe.session.user
    if "KPI Admin" in frappe.get_roles(user):
        doc = frappe.get_doc("KPI Library", kpi_name)
    else:
        # KPI User: chỉ cho xem, không list
        doc = frappe.get_doc("KPI Library", kpi_name)
        # Force read-only trên client
        doc.flags.ignore_permissions = True
    # Chỉ trả về selected fields (không trả về doctype để client không mở form)
    return {
        "kpi_name": doc.kpi_name,
        "target": doc.target,
        "unit": doc.unit,
        # ... các field khác KHÔNG bao gồm doctype
    }

# Bước 4: Trên client (JS), dialog xem chi tiết (không phải form)
frappe.call({
    method: "your_app.api.get_kpi_detail",
    args: {kpi_name: cur_frm.doc.kpi},
    callback: function(r) {
        // Hiển thị dialog read-only
        var d = new frappe.ui.Dialog({
            title: "Chi tiết KPI",
            fields: [/* fields read-only */]
        });
        d.set_values(r.message);
        d.show();
    }
})
```

**Cách khác — Permission Query Conditions:**

Nếu muốn dùng form Frappe chuẩn nhưng hạn chế:

```python
# hooks.py
permission_query_conditions = {
    "KPI Library": "your_app.api.kpi_library_permission_conditions"
}

def kpi_library_permission_conditions(user, doctype):
    if "KPI Admin" in frappe.get_roles(user):
        return ""
    # KPI User: không thấy gì trong list view
    return "1=0"

# Trong KPI Library controller — override has_permission
class KPILibrary(Document):
    def has_permission(self, ptype, user=None):
        if "KPI Admin" in frappe.get_roles(user):
            return None  # fallthrough
        if ptype == "read":
            # Chỉ cho đọc nếu document này được link từ KPI Assignment của user
            # (phải tự implement logic kiểm tra)
            return False  # từ chối
        return False
```

---

#### TÌNH HUỐNG 3: Record-level Permission theo Đơn vị (Organizational Unit)

**Mô tả:** Người dùng thường chỉ thấy KPI Assignment, KPI Data, KPI Evaluation của **Đơn vị mình**, không được xem đơn vị khác.

**Giải pháp — User Permission (chuẩn Frappe):**

```python
# Cách 1: User Permission
# Tạo User Permission records:
#   User: nv_a@company.com
#   Allow: Department (hoặc Company/DonVi)
#   For Value: "Phòng Kinh doanh"
#   Applicable For: KPI Assignment, KPI Data, KPI Evaluation
#
# KPI Assignment có link field "don_vu" → User Permission tự động filter

# Trên DocType KPI Assignment cần:
# - Field "don_vi" (link → DonVi / Department) KHÔNG set ignore_user_permissions
# - Tạo User Permission cho user với allow=Department
```

**Giải pháp nâng cao — Permission Query Conditions:**

Khi mô hình đơn vị phức tạp (đa cấp, user thuộc nhiều đơn vị):

```python
# hooks.py
permission_query_conditions = {
    "KPI Assignment": "your_app.api.kpi_assignment_permission_conditions"
}

def kpi_assignment_permission_conditions(user, doctype):
    if "KPI Admin" in frappe.get_roles(user):
        return ""  # Admin thấy tất cả

    # Lấy đơn vị của user từ Employee
    employee = frappe.db.get_value("Employee", {"user": user}, ["department", "name"], as_dict=True)
    if not employee:
        return "1=0"  # Không có employee → không thấy gì

    # Filter KPI Assignment theo department
    return f"""`tabKPI Assignment`.`department` = {frappe.db.escape(employee.department)}"""
```

---

#### TÌNH HUỐNG 4: Function-based Permission — Người nhập liệu vs Trưởng đơn vị

**Mô tả:** Trên KPI Data, Admin chỉ sửa được nếu được gán vai trò "Người nhập liệu" hoặc "Trưởng đơn vị". Người dùng thường chỉ nhập KPI được phân công.

**Giải pháp — Custom Roles + Controller Permission:**

```python
# Bước 1: Tạo custom roles
# - "KPI Data Entry" (Người nhập liệu)
# - "KPI Unit Head" (Trưởng đơn vị)
# - "KPI Admin" (Admin phân hệ)

# Bước 2: DocPerm cho KPI Data
# Role "KPI Data Entry" → read=1, write=1, create=1
# Role "KPI Unit Head"  → read=1, write=1, create=1
# Role "KPI Admin"      → read=1, write=1, create=1, delete=1, submit=1, export=1

# Bước 3: Controller Permission — kiểm tra user có được gán KPI không
class KPIData(Document):
    def has_permission(self, ptype, user=None):
        user = user or frappe.session.user
        roles = frappe.get_roles(user)

        if "KPI Admin" in roles:
            return None  # fallthrough → DocPerm quyết định

        if ptype in ("read", "write", "create"):
            # Kiểm tra user có được gán KPI này không
            assigned = frappe.db.exists("KPI Assignment", {
                "user": user,
                "kpi": self.kpi,
                "department": self.department,
                "docstatus": 1  # đã submit
            })
            if assigned:
                return None  # fallthrough → DocPerm quyết định

            # Kiểm tra user là Trưởng đơn vị
            if "KPI Unit Head" in roles:
                unit_head_dept = frappe.db.get_value("Employee", {"user": user}, "department")
                if unit_head_dept == self.department:
                    return None  # được sửa data của đơn vị mình

            return False  # Không có quyền

        return False
```

---

#### TÌNH HUỐNG 5: Time-based Permission — Quyền sửa theo thời hạn

**Mô tả:** KPI Data và KPI Evaluation chỉ được sửa trong khoảng thời gian cho phép. Hết hạn → chỉ xem (Read-only).

**Giải pháp — Controller Permission kiểm tra thời gian:**

```python
class KPIData(Document):
    def has_permission(self, ptype, user=None):
        user = user or frappe.session.user

        if ptype == "read":
            return None  # ai cũng đọc được

        if ptype in ("write", "create"):
            # Lấy thời hạn từ KPI Assignment liên quan
            assignment = frappe.get_doc("KPI Assignment", self.kpi_assignment)

            from frappe.utils import nowdate
            today = nowdate()

            if assignment.data_entry_deadline:
                if today > assignment.data_entry_deadline:
                    frappe.msgprint(f"Đã quá hạn nhập liệu ({assignment.data_entry_deadline})")
                    return False

            # Kiểm tra user có được gán KPI này không
            # ... (tiếp logic từ tình huống 4)

        return None

class KPIEvaluation(Document):
    def has_permission(self, ptype, user=None):
        if ptype == "read":
            return None

        if ptype in ("write", "create"):
            # Kiểm tra thời gian đánh giá
            from frappe.utils import nowdate
            if self.evaluation_period_end and nowdate() > self.evaluation_period_end:
                frappe.msgprint("Đã quá hạn đánh giá")
                return False

            # Kiểm tra user thuộc đơn vị được đánh giá
            # ... (logic tương tự)
        return None
```

**Client-side validation (JS):**

```javascript
// Trên KPI Data form
frappe.ui.form.on("KPI Data", {
    setup: function(frm) {
        // Disable form nếu quá hạn
        if (frm.doc.data_entry_deadline && frappe.datetime.now_date() > frm.doc.data_entry_deadline) {
            frm.disable_form();
            frm.set_df_property("kpi_data_section", "hidden", 0);
            frappe.msgprint("Đã quá hạn nhập liệu. Form ở chế độ chỉ xem.");
        }
    },

    before_save: function(frm) {
        // Double-check trên client
        if (frm.doc.data_entry_deadline && frappe.datetime.now_date() > frm.doc.data_entry_deadline) {
            frappe.throw("Đã quá hạn nhập liệu. Không thể lưu.");
        }
    }
});
```

---

#### TÌNH HUỐNG 6: Field-level Permission theo vai trò

**Mô tả:** Trên KPI Assignment, Admin sửa được tất cả fields, trong khi người dùng thường chỉ sửa một số fields nhất định và chỉ trong thời điểm cho phép.

**Giải pháp — Permission Levels (permlevel) + Client-side control:**

```python
# Bước 1: Trong KPI Assignment DocType, set permlevel cho từng field:
# - Field "note", "custom_weight" → permlevel = 1 (chỉ Admin)
# - Field "target_value", "actual_value" → permlevel = 0 (ai cũng sửa được)

# Bước 2: DocPerm:
# Role "KPI Admin"   → permlevel=0: read=1, write=1
#                       permlevel=1: read=1, write=1 (field-level)
# Role "KPI User"    → permlevel=0: read=1, write=1
#                    → KHÔNG có permlevel=1 → không thấy/sửa được field permlevel=1

# Bước 3: Client-side — ẩn field dựa trên role
frappe.ui.form.on("KPI Assignment", {
    refresh: function(frm) {
        // Nếu không phải Admin, thêm logic read-only theo thời gian
        if (!frappe.user_roles.includes("KPI Admin")) {
            // Disable các field không được sửa sau deadline
            if (frappe.datetime.now_date() > frm.doc.deadline) {
                frm.set_df_property("target_value", "read_only", 1);
                frm.set_df_property("actual_value", "read_only", 1);
            }
        }
    }
});
```

---

#### TÌNH HUỐNG 7: Submit/Workflow Permission

**Mô tả:** KPI Assignment và KPI Data có thể cần qua workflow (Draft → Submitted → Approved). Chỉ Trưởng đơn vị mới được submit/approve.

**Giải pháp — Frappe Workflow + Custom Permissions:**

```python
# Bước 1: Trong KPI Assignment DocType:
# - is_submittable = 1
# - Tạo Workflow: Draft → Submitted → Approved

# Bước 2: DocPerm submit:
# Role "KPI Admin"    → submit=1, cancel=1, amend=1
# Role "KPI Unit Head" → submit=1 (chỉ submit, không cancel)
# Role "KPI Data Entry" → submit=0 (không được submit)

# Bước 3: Workflow transitions (nếu dùng Frappe Workflow):
# State "Draft" → "Submitted": allowed roles = ["KPI Admin", "KPI Unit Head"]
# State "Submitted" → "Approved": allowed roles = ["KPI Admin"]

# Bước 4: Controller — kiểm tra unit head chỉ submit được data đơn vị mình
class KPIAssignment(Document):
    def on_submit(self):
        user = frappe.session.user
        if "KPI Admin" not in frappe.get_roles(user):
            # Chỉ cho submit nếu user là trưởng đơn vị này
            employee = frappe.db.get_value("Employee", {"user": user}, "department")
            if employee != self.department:
                frappe.throw(f"Bạn không phải trưởng đơn vị {self.department}")
```

---

#### TÌNH HUỐNG 8: Xem dữ liệu theo cấp quản lý

**Mô tả:** Trưởng đơn vị thấy được KPI Data của tất cả nhân viên trong đơn vị mình. Admin thấy toàn hệ thống. Người dùng thường chỉ thấy của mình.

**Giải pháp — Permission Query Conditions mở rộng:**

```python
def kpi_data_permission_conditions(user, doctype):
    roles = frappe.get_roles(user)

    if "KPI Admin" in roles:
        return ""  # Thấy tất cả

    employee = frappe.db.get_value("Employee", {"user": user}, ["department", "name"], as_dict=True)
    if not employee:
        return "1=0"

    if "KPI Unit Head" in roles and "KPI Data Entry" in roles:
        # Trưởng đơn vị: thấy data của cả đơn vị
        return f"""`tabKPI Data`.`department` = {frappe.db.escape(employee.department)}"""

    if "KPI Data Entry" in roles:
        # Người nhập liệu: chỉ thấy KPI được gán
        return f"""`tabKPI Data`.`name` IN (
            SELECT `parent` FROM `tabKPI Assignment User`
            WHERE `user` = {frappe.db.escape(user)}
        )"""

    # Fallback: employee chỉ thấy KPI của mình
    return f"""`tabKPI Data`.`employee` = {frappe.db.escape(employee.name)}"""
```

---

#### TÌNH HUỐNG 9: API-level Permission

**Mô tả:** Các API endpoint custom (ví dụ: dashboard tổng hợp KPI, báo cáo) cũng phải enforce quyền.

**Giải pháp — Check quyền trong API:**

```python
@frappe.whitelist()
def get_kpi_dashboard(department=None):
    user = frappe.session.user
    roles = frappe.get_roles(user)

    # Admin: xem dashboard của any department
    # User: chỉ xem dashboard của department mình
    if "KPI Admin" not in roles:
        employee = frappe.db.get_value("Employee", {"user": user}, "department")
        if department and department != employee:
            frappe.throw("Bạn không có quyền xem dashboard của đơn vị khác")
        department = employee  # force department của user

    # Query data
    data = frappe.db.sql("""
        SELECT ... FROM `tabKPI Data`
        WHERE department = %(department)s
    """, {"department": department}, as_dict=1)

    return data
```

---

#### TÌNH HUỐNG 10: Permission delegation (Ủy quyền tạm thời)

**Mô tả:** Trưởng đơn vị có thể ủy quyền nhập liệu KPI cho người khác trong thời gian vắng mặt.

**Giải pháp — KPI Delegation DocType + Runtime Permission Check:**

```python
# DocType "KPI Delegation"
# - delegator (link → User): người ủy quyền
# - delegate (link → User): người được ủy quyền
# - department (link → Department): đơn vị
# - start_date, end_date: thời gian hiệu lực
# - kpi (optional): nếu null thì ủy quyền tất cả

# Trong KPIData.has_permission:
class KPIData(Document):
    def has_permission(self, ptype, user=None):
        user = user or frappe.session.user

        # Kiểm tra delegation
        if ptype in ("write", "create"):
            has_delegation = frappe.db.exists("KPI Delegation", {
                "delegate": user,
                "department": self.department,
                "start_date": ["<=", frappe.utils.nowdate()],
                "end_date": [">=", frappe.utils.nowdate()],
                "docstatus": 1,
                "kpi": ["in", [self.kpi, ""]]
            })
            if has_delegation:
                return None  # Được ủy quyền

        return None  # fallthrough
```

---

### 15.4 Ma trận giải pháp tổng hợp

| # | Tình huống | Cơ chế Frappe | Implementation |
|---|------------|---------------|----------------|
| 1 | Admin-only CRUD | Role + DocPerm | Tạo role "KPI Admin", chỉ gán DocPerm cho role này |
| 2 | Conditional Read-only từ context khác | Controller `has_permission` + API endpoint riêng + Dialog client-side | Không dùng form Frappe chuẩn, dùng API trả về dữ liệu thuần |
| 3 | Filter theo đơn vị | `permission_query_conditions` hook + User Permission | Filter SQL theo department của Employee |
| 4 | Function-based: Data Entry vs Unit Head | Custom roles + Controller `has_permission` | Kiểm tra role + kiểm tra phân công |
| 5 | Time-based write | Controller `has_permission` + Client-side disable | Kiểm tra deadline trước khi cho write |
| 6 | Field-level permission | `permlevel` trong DocType JSON + DocPerm | Set permlevel=1 cho field nhạy cảm |
| 7 | Submit/Approve workflow | Frappe Workflow + `is_submittable` + `on_submit` controller | Workflow states + transition rules |
| 8 | Multi-level data visibility | `permission_query_conditions` phân cấp | SQL conditions theo role hierarchy |
| 9 | API endpoint permission | Frappe `has_permission` + custom check | Kiểm tra quyền trong mỗi API |
| 10 | Temporary delegation | Custom DocType + runtime check | Kiểm tra delegation record trước khi cho phép |

### 15.5 Kiến trúc phân quyền đề xuất cho hệ thống KPI

```python
# ┌─────────────────────────────────────────────────────────────┐
# │                    KIẾN TRÚC PHÂN QUYỀN KPI                  │
# ├─────────────────────────────────────────────────────────────┤
# │                                                               │
# │  LAYER 1 — Role Definition                                    │
# │  ├── System Manager (built-in) → Quản trị hệ thống            │
# │  ├── KPI Admin → Quản trị phân hệ KPI                        │
# │  ├── KPI Unit Head → Trưởng đơn vị                           │
# │  ├── KPI Data Entry → Người nhập liệu                        │
# │  └── KPI Viewer → Người xem báo cáo                          │
# │                                                               │
# │  LAYER 2 — DocPerm (DocType-level)                           │
# │  ├── Master Data (KPI Setting, Scale, Group, Library)         │
# │  │   └── Chỉ KPI Admin có quyền                               │
# │  ├── KPI Assignment Template                                  │
# │  │   └── Chỉ KPI Admin có quyền                               │
# │  ├── KPI Assignment                                           │
# │  │   ├── KPI Admin → CRUD                                     │
# │  │   └── KPI Unit Head → CRUD (giới hạn đơn vị)              │
# │  ├── KPI Data                                                 │
# │  │   ├── KPI Admin → CRUD                                     │
# │  │   ├── KPI Unit Head → CRUD (đơn vị mình)                  │
# │  │   └── KPI Data Entry → CRUD (KPI được gán)                │
# │  └── KPI Evaluation                                           │
# │      ├── KPI Admin → CRUD                                     │
# │      └── KPI Unit Head → CRUD (đơn vị mình)                  │
# │                                                               │
# │  LAYER 3 — Permission Query Conditions (List-level)           │
# │  ├── KPI Assignment → filter theo department                  │
# │  ├── KPI Data → filter theo department + assigned items       │
# │  └── KPI Evaluation → filter theo department                  │
# │                                                               │
# │  LAYER 4 — Controller Permission (Document-level)             │
# │  ├── KPI Library → read-only exception logic                  │
# │  ├── KPI Data → time-window check + delegation check          │
# │  └── KPI Evaluation → time-window check + role-based eval     │
# │                                                               │
# │  LAYER 5 — Workflow (State-level)                             │
# │  ├── KPI Assignment: Draft → Submitted → Approved             │
# │  └── KPI Data: Draft → Submitted                              │
# │                                                               │
# └─────────────────────────────────────────────────────────────┘
```

### 15.6 Code implementation mẫu — File structure đề xuất

```
your_app/
├── hooks.py
│   ├── has_permission = {"KPI Library": "your_app.kpi.has_permission", ...}
│   └── permission_query_conditions = {
│         "KPI Assignment": "your_app.kpi.permission_conditions",
│         "KPI Data": "your_app.kpi.permission_conditions",
│         "KPI Evaluation": "your_app.kpi.permission_conditions",
│       }
│
├── kpi.py  (hoặc api/kpi_permissions.py)
│   ├── def has_permission(doc, ptype, user)
│   ├── def permission_conditions(user, doctype)
│   ├── def get_kpi_detail(kpi_name)           # API cho tình huống 2
│   ├── def get_kpi_dashboard(department)       # API cho tình huống 9
│   └── def check_delegation(user, department)  # Helper cho tình huống 10
│
├── kpi_delegation.py
│   └── class KPIDelegation(Document): ...
│
├── kpi_assignment.py
│   └── class KPIAssignment(Document):
│         def has_permission(self, ptype, user=None)
│         def on_submit(self)
│
├── kpi_data.py
│   └── class KPIData(Document):
│         def has_permission(self, ptype, user=None)
│         def validate(self)  # Kiểm tra thời hạn khi save
│
└── kpi_evaluation.py
    └── class KPIEvaluation(Document):
          def has_permission(self, ptype, user=None)
```

### 15.7 Các lưu ý đặc biệt cho hệ thống KPI

1. **Không dùng `ignore_permissions=True`** trong code trừ khi thực sự cần (các API read-only đặc biệt như tình huống 2)

2. **Cache invalidation:** Khi thay đổi phân công KPI hoặc delegation, clear cache:
   ```python
   frappe.cache().delete_value("roles")  # Force reload roles
   ```

3. **Performance cho Permission Query Conditions:** Nếu có nhiều user permissions, đảm bảo có index trên các field:
   ```sql
   -- Tạo index cho field department trên KPI Assignment, KPI Data, KPI Evaluation
   CREATE INDEX idx_kpi_assignment_department ON `tabKPI Assignment`(department);
   CREATE INDEX idx_kpi_data_department ON `tabKPI Data`(department);
   ```

4. **Kiểm tra permission ở cả 2 đầu (Server + Client):**
   - Server: `has_permission`, `permission_query_conditions`, controller validate
   - Client: disable form, ẩn button, check deadline trước khi cho save

5. **Audit Trail:** Log các thay đổi quan trọng (ai sửa KPI data, ai submit evaluation) bằng `frappe.get_doc(...).track_changes`

6. **Phân biệt rõ "Role" và "Chức năng":**
   - Role = quyền truy cập (KPI Admin, KPI User)
   - Chức năng (Function) = gán role cho user trong context cụ thể (VD: user A là Data Entry của phòng B)
   - Dùng **User Permission** để map chức năng, **Role** để map quyền

7. **Test permission:**
   ```python
   # Trong test
   def test_kpi_data_unit_head_can_write():
       user = "unit_head@example.com"
       doc = frappe.get_doc("KPI Data", "data-của-phòng-mình")
       assert frappe.permissions.get_doc_permissions(doc, user=user).get("write")

   def test_kpi_data_entry_cannot_write_after_deadline():
       # Mock deadline
       pass
   ```

8. **Xử lý edge case — Admin cũng bị giới hạn thời gian?**
   Tuỳ nghiệp vụ: nếu Admin cần override deadline → kiểm tra role trong controller:
   ```python
   if "KPI Admin" in frappe.get_roles(user):
       return None  # Admin bypass time check
   ```

---

### 15.8 Tổng kết — Lộ trình implement

```
PHASE 1 — Core Permission Setup (1-2 ngày)
├── Tạo roles: KPI Admin, KPI Unit Head, KPI Data Entry, KPI Viewer
├── Set DocPerm cho tất cả 9 DocTypes
├── Cấu hình Workspace menu → chỉ KPI Admin thấy master data
└── Assign roles cho users

PHASE 2 — Record-level & Query Conditions (2-3 ngày)
├── Implement permission_query_conditions cho KPI Assignment, Data, Evaluation
├── Kiểm tra mối quan hệ Employee ↔ User ↔ Department
└── Tạo User Permission records cho users

PHASE 3 — Business Logic Permissions (2-3 ngày)
├── Controller has_permission cho KPI Data (time-window + delegation)
├── Controller has_permission cho KPI Evaluation (time-window + role)
├── KPI Library read-only exception API
└── Client-side form control (disable form, ẩn nút)

PHASE 4 — Advanced Features (tuỳ chọn, 2-3 ngày)
├── KPI Delegation DocType + runtime check
├── Workflow cho KPI Assignment, KPI Data
├── Audit trail
└── Unit tests cho tất cả permission scenarios
```

---

## 16. Giải pháp mở rộng: NxExtendedPerm — Conditional Permission Engine

### 16.1 Vấn đề

Frappe core permissions có giới hạn:

| Bài toán | Core Frappe | Giải pháp hiện tại |
|----------|-------------|-------------------|
| Time-based write | Không hỗ trợ | Code controller riêng từng DocType |
| Function/Assignment-based | Không hỗ trợ | Code controller riêng |
| Context-dependent visibility | Không hỗ trợ | API + Dialog thủ công |
| Multi-condition (AND/OR) | Không hỗ trợ | Code Python phức tạp |
| Field-level động (theo state) | Chỉ static permlevel | Code controller + JS |
| Delegation | Không hỗ trợ | Code riêng |

Mỗi dự án lại implement lại từ đầu → tốn thời gian, khó maintain.

### 16.2 Giải pháp: NxExtendedPerm Engine

**Triết lý:** Xây dựng **rule engine phân quyền dạng Condition → Effect**, cấu hình qua UI, dùng chung 1 engine code cho mọi DocType.

```
┌─────────────────────────────────────────────────────────────────┐
│                    NxExtendedPerm Engine                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  hooks.py:                                                       │
│    has_permission = {"*": "nxperm.api.check}                     │
│    permission_query_conditions = {"*": "nxperm.api.conditions}   │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────┐    ┌────────────────────┐                  │
│  │  Rule Matcher    │───→│  Effect Applicator  │                  │
│  │  (đánh giá theo  │    │  (Allow / Deny +     │                  │
│  │   priority)      │    │   Field Overrides)   │                  │
│  └─────────────────┘    └────────────────────┘                  │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────┐                │
│  │         Condition Evaluators                   │                │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │                │
│  │  │  Role     │ │  Field   │ │  Time Window  │  │                │
│  │  │  Check    │ │  Match   │ │  Check        │  │                │
│  │  └──────────┘ └──────────┘ └──────────────┘  │                │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │                │
│  │  │  User In  │ │  Has     │ │  Custom       │  │                │
│  │  │  Table    │ │  Assign  │ │  Script       │  │                │
│  │  └──────────┘ └──────────┘ └──────────────┘  │                │
│  └─────────────────────────────────────────────┘                │
│                                                                   │
│  DATA (cấu hình qua UI, stored trong DocType):                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  NxPerm Policy  │  NxPerm Condition  │  NxPerm Assignment  │ │
│  │  (rule chính)    │  (điều kiện)       │  (gán function)     │ │
│  └─────────────────┘───────────────────┘─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 16.3 Kiến trúc DocType

#### 16.3.1 NxPerm Policy — Bộ quy tắc

DocType chính, mỗi record = một rule permission.

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `enabled` | Check | Bật/tắt rule |
| `rule_name` | Data | Tên rule (mô tả) |
| `priority` | Int | Độ ưu tiên (thấp = đánh giá trước) |
| `effect` | Select | **Allow** / **Deny** (cho phép/từ chối) |
| `target_doctype` | Link → DocType | DocType áp dụng |
| `permission_type` | Select | read / write / create / delete / submit / cancel / amend / print / email / report / import / export / select / * (all) |
| `match_all_doctypes` | Check | Nếu bật → áp dụng cho mọi DocType |
| `override_default` | Check | Nếu bật → override luôn Frappe core permission (thay vì fallthrough) |
| `stop_on_match` | Check | Dừng đánh giá các rule sau nếu rule này match |
| `description` | Text | Ghi chú |
| `conditions` | Table (NxPerm Condition) | Các điều kiện AND/OR |
| `field_overrides` | Table (NxPerm Field Override) | Field-level permissions |

**Effect "Allow" vs "Deny":**
- **Deny** (mặc định an toàn): Nếu rule match → từ chối, không fallthrough
- **Allow**: Nếu rule match → cho phép (override Frappe deny)
- Nếu không có rule nào match → fallthrough về Frappe core permission

#### 16.3.2 NxPerm Condition — Điều kiện

Child table của NxPerm Policy.

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `condition_type` | Select | Loại điều kiện (xem bảng dưới) |
| `logic` | Select | AND / OR (kết hợp với condition trước/sau) |
| `negate` | Check | NOT condition |
| `field` | Data | Tên field trên target DocType (hoặc "owner", "creation",...) |
| `field_meta` | Link → DocField | (Optional) chọn field từ UI |
| `operator` | Select | =, !=, >, <, >=, <=, in, not_in, between, is_set, is_not_set, like |
| `value` | Data | Giá trị so sánh (literal) |
| `value_source` | Select | **literal**: dùng value literal / **user_field**: lấy từ field của user / **doc_field**: lấy từ field khác của document / **current_time**: thời gian hiện tại / **today**: ngày hiện tại |
| `user_field_path` | Data | Đường dẫn field trên User/Employee (vd: `employee.department`) |
| `source_field` | Data | Field khác trên document để so sánh chéo |
| `ref_doctype` | Link → DocType | DocType tham chiếu (cho user_in_table, has_assignment) |
| `ref_field` | Data | Field chứa user (cho user_in_table) |
| `custom_script` | Code | Python expression (cho condition_type = script) |

**Các loại condition (`condition_type`):**

| Type | Ý nghĩa | Logic đánh giá |
|------|---------|----------------|
| `role_has` | User có role không | `frappe.get_roles(user) → contains value` |
| `field_equals` | Field của document == value | `doc.get(field) == value` |
| `field_user_match` | Field của document == field của user | `doc.get(field) == resolve_user_field(user, user_field_path)` |
| `user_is_owner` | User là owner của document | `doc.owner == user` |
| `user_in_table` | User có trong child table | `child_table.exists(doc, ref_field, user)` |
| `user_assigned` | User có assignment record | `NxPermAssignment.exists(user, doc, ...)` |
| `time_before` | Thời gian hiện tại < doc.field | `now() < doc.get(field)` |
| `time_after` | Thời gian hiện tại > doc.field | `now() > doc.get(field)` |
| `time_between` | Thời gian trong khoảng | `doc.get(start) <= now() <= doc.get(end)` |
| `field_compare` | So sánh 2 field của document | `doc.get(field) op doc.get(source_field)` |
| `cross_doc_field` | So sánh field với field của document liên quan | `frappe.db.get_value(ref_doctype, ref_doc, ref_field) op value` |
| `docstatus` | Document status | `doc.docstatus == value` (0=Draft, 1=Submitted, 2=Cancelled) |
| `workflow_state` | Workflow state | `doc.workflow_state == value` |
| `script` | Custom Python expression | `eval(script, context)` — sandboxed |

#### 16.3.3 NxPerm Field Override — Field-level permission động

Child table của NxPerm Policy. Khi rule match, tự động áp dụng field permissions.

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `field` | Link → DocField | Field bị ảnh hưởng |
| `override_read_only` | Check | Set read-only |
| `override_hidden` | Check | Ẩn field |
| `override_required` | Check | Bắt buộc nhập |
| `permlevel` | Int | Gán permlevel động (override permlevel từ DocType JSON) |

#### 16.3.4 NxPerm Assignment — Gán chức năng cho user trong context

DocType này giải quyết bài toán **"ai được làm gì trong bối cảnh nào"** — một khái niệm mà Frappe core không có.

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `user` | Link → User | User được gán |
| `function_role` | Link → Role | Vai trò chức năng (VD: "KPI Data Entry", "KPI Evaluator") |
| `target_doctype` | Link → DocType | DocType được áp dụng |
| `target_document` | Dynamic Link → target_doctype | (Optional) document cụ thể |
| `department` | Link → Department | (Optional) phòng ban |
| `from_date` | Date | Hiệu lực từ |
| `to_date` | Date | Hiệu lực đến |
| `is_active` | Check | Đang hiệu lực |

**Ví dụ:** User A là **Data Entry** cho **KPI Data** của **Phòng Kinh doanh** → tạo NxPerm Assignment với `function_role = "KPI Data Entry"`, `target_doctype = "KPI Data"`, `department = "Phòng Kinh doanh"`.

### 16.4 Engine: Cách đánh giá

#### 16.4.1 Luồng xử lý

```python
# nxperm/api.py — engine trung tâm

def nxperm_has_permission(doc, ptype, user):
    """
    Hook entry point: frappe.permissions.has_permission
    Gắn qua hooks.py: has_permission = {"*": "nxperm.api.nxperm_has_permission"}
    """
    # Bước 0: Administrator luôn bypass
    if user == "Administrator":
        return None  # fallthrough → Frappe core (sẽ return True)

    doctype = doc.doctype if hasattr(doc, "doctype") else doc

    # Bước 1: Load NxPerm Policies cho doctype này
    policies = get_nxperm_policies(doctype, ptype)

    # Bước 2: Đánh giá theo priority
    for policy in policies:
        result = evaluate_policy(policy, doc, ptype, user)
        if result == "allow":
            return True  # Cho phép
        elif result == "deny":
            # Ghi log lý do từ chối
            push_perm_check_log(
                f"Bị từ chối bởi NxPerm Policy: {policy.rule_name}"
            )
            return False  # Từ chối
        # result == None → không match, tiếp tục

    # Bước 3: Không có rule nào match → fallthrough về Frappe core
    return None


def evaluate_policy(policy, doc, ptype, user):
    """
    Đánh giá 1 policy.
    Trả về: "allow", "deny", hoặc None (không match / không áp dụng)
    """
    # Kiểm tra doc có thỏa tất cả conditions không
    if not evaluate_conditions(policy.conditions, doc, user):
        return None  # Conditions không match → skip

    # Policy match! Trả về effect
    return policy.effect  # "allow" hoặc "deny"


def evaluate_conditions(conditions, doc, user):
    """
    Đánh giá conditions theo logic AND/OR group.
    Hỗ trợ grouping: AND có độ ưu tiên cao hơn OR.
    """
    and_group = []
    or_group = []

    for cond in conditions:
        result = evaluate_single_condition(cond, doc, user)
        if cond.logic == "OR":
            or_group.append(result)
        else:
            and_group.append(result)

    # AND group: tất cả phải True
    and_ok = all(and_group) if and_group else True
    # OR group: ít nhất 1 True (nếu có)
    or_ok = any(or_group) if or_group else True

    return and_ok and or_ok
```

#### 16.4.2 Condition Evaluators

```python
def evaluate_single_condition(cond, doc, user):
    """Đánh giá một condition, trả về True/False"""

    # Resolve value (hỗ trợ value_source)
    value = resolve_value(cond, doc, user)

    # Lấy giá trị thực tế từ document
    doc_value = get_doc_value(cond, doc)

    # So sánh theo operator
    result = compare(doc_value, cond.operator, value)

    # Nếu negate = True → đảo ngược
    if cond.negate:
        result = not result

    return result


def resolve_value(cond, doc, user):
    """Resolve giá trị so sánh từ nhiều nguồn"""
    if cond.value_source == "literal":
        return cond.value
    elif cond.value_source == "user_field":
        # Lấy từ field của User/Employee
        return frappe.db.get_value("User", user, cond.user_field_path)
    elif cond.value_source == "user_employee_field":
        # Lấy từ Employee record của user
        employee = frappe.db.get_value("Employee", {"user": user}, cond.user_field_path)
        return employee
    elif cond.value_source == "doc_field":
        # Lấy từ field khác của document
        return doc.get(cond.source_field)
    elif cond.value_source == "current_time":
        return frappe.utils.now()
    elif cond.value_source == "today":
        return frappe.utils.today()
    return cond.value
```

#### 16.4.3 Field Override Engine

```python
def apply_field_overrides(doc, ptype, user):
    """
    Áp dụng field-level overrides cho document.
    Gọi từ client-side JS qua frappe.call hoặc set trong form setup.
    """
    doctype = doc.doctype
    policies = get_nxperm_policies(doctype, ptype)

    field_overrides = {}
    for policy in policies:
        if evaluate_conditions(policy.conditions, doc, user):
            for override in policy.field_overrides:
                if override.field not in field_overrides:
                    field_overrides[override.field] = {}
                field_overrides[override.field].update({
                    "read_only": override.override_read_only,
                    "hidden": override.override_hidden,
                    "required": override.override_required,
                    "permlevel": override.permlevel,
                })

    return field_overrides
```

### 16.5 Caching

```python
# Cache policies trong request để tránh query DB nhiều lần
def get_nxperm_policies(doctype, ptype):
    """Get NxPerm Policies với caching"""
    cache_key = f"nxperm_policies:{doctype}:{ptype}"

    if cache_key not in frappe.local.__dict__:
        # Lấy policies áp dụng cho doctype này
        policies = frappe.get_all("NxPerm Policy", filters={
            "enabled": 1,
        }, or_filters={
            "target_doctype": doctype,
            "match_all_doctypes": 1,
        }, or_conditions={
            "permission_type": ["in", [ptype, "*"]],
        }, order_by="priority asc")

        frappe.local.__dict__[cache_key] = policies

    return frappe.local.__dict__[cache_key]
```

### 16.6 10 tình huống KPI — Cấu hình bằng NxPerm

#### Tình huống 1: Master Data — Chỉ Admin

**NxPerm Policy:**
```
Rule name: "Block non-admin on KPI Setting"
Priority: 1
Effect: Deny
Target DocType: KPI Setting
Permission Type: *

Conditions:
  - type: role_has, logic: AND, negate: true
    value: "KPI Admin"
    → Nếu user KHÔNG có role KPI Admin → Deny
```

#### Tình huống 3: Filter KPI Assignment theo đơn vị

**NxPerm Policy:**
```
Rule name: "KPI Assignment - filter by department"
Priority: 10
Effect: Allow (dùng để thêm query condition)
Target DocType: KPI Assignment
Permission Type: read

Conditions:
  - type: field_user_match, logic: AND
    field: "department"
    value_source: "user_employee_field"
    user_field_path: "department"
    → Chỉ cho xem KPI Assignment có department == department của user
```

#### Tình huống 5: Time-based write trên KPI Data

**NxPerm Policy:**
```
Rule name: "KPI Data - deny write after deadline"
Priority: 1
Effect: Deny
Target DocType: KPI Data
Permission Type: write

Conditions:
  - type: time_after, logic: AND
    field: "data_entry_deadline"
    → Nếu deadline đã qua → Deny write
```

#### Tình huống 4: Người nhập liệu — chỉ sửa KPI được gán

**NxPerm Policy:**
```
Rule name: "KPI Data - only assigned can write"
Priority: 5
Effect: Deny
Target DocType: KPI Data
Permission Type: write

Conditions:
  - type: role_has, logic: AND, negate: true
    value: "KPI Admin"
    → Cho Admin bypass
  - type: user_assigned, logic: AND
    ref_doctype: "NxPerm Assignment"
    ref_field: "user"
    → Nếu user không có NxPerm Assignment cho KPI Data này → Deny
```

#### Tình huống 10: Delegation

**NxPerm Policy:**
```
Rule name: "KPI Data - delegation allow"
Priority: 3
Effect: Allow
Target DocType: KPI Data
Permission Type: write

Conditions:
  - type: user_assigned, logic: AND
    ref_doctype: "KPI Delegation"
    ref_field: "delegate"
    → Nếu user đang được ủy quyền → Allow write
```

#### Tình huống kết hợp: Field-level động

**NxPerm Policy:**
```
Rule name: "KPI Assignment - Unit head mode"
Priority: 20
Effect: Allow (kèm field overrides)
Target DocType: KPI Assignment
Permission Type: write

Conditions:
  - type: role_has, logic: AND
    value: "KPI Unit Head"

Field Overrides:
  - field: "approval_status", override_read_only: false
  - field: "evaluation_note", override_hidden: false
  - field: "target_value", override_read_only: false
  - field: "base_salary", override_read_only: true  (Trưởng đơn vị không sửa được lương)
```

### 16.7 Hooks Integration — Code 1 lần

```python
# === hooks.py — gắn vào Frappe core ===

has_permission = {
    "*": "nxperm.api_check.nxperm_has_permission",
}

permission_query_conditions = {
    "*": "nxperm.api_query.nxperm_query_conditions",
}

# === nxperm/api_check.py ===

import frappe
from frappe import _

# Cache local
NXPERM_CACHE = {}

def nxperm_has_permission(doc, ptype, user):
    """Global hook: kiểm tra NxPerm Policy"""
    if user == "Administrator":
        return None  # fallthrough → Frappe core (True)

    doctype = doc if isinstance(doc, str) else doc.doctype

    policies = _load_policies(doctype, ptype)
    for policy in policies:
        match = _evaluate_conditions(policy, doc, user)
        if match:
            if policy.effect == "allow":
                # Apply field overrides vào frappe.flags
                _store_field_overrides(policy, doctype)
                return True
            else:  # deny
                frappe.flags.setdefault("nxperm_deny_reasons", []).append(policy.rule_name)
                return False  # Từ chối

    return None  # Fallthrough


def nxperm_query_conditions(user, doctype):
    """Global hook: thêm filter conditions cho list query"""
    policies = _load_policies(doctype, "read")

    conditions = []
    for policy in policies:
        # Chỉ policy có condition type là query filter mới thêm vào
        if policy.effect == "deny":
            continue

        for cond in policy.conditions:
            if cond.condition_type == "field_user_match":
                value = _resolve_user_value(user, cond.user_field_path)
                if value:
                    conditions.append(
                        f"`tab{doctype}`.`{cond.field}` = {frappe.db.escape(value)}"
                    )

    return " and ".join(conditions)


def _load_policies(doctype, ptype):
    """Load NxPerm policies với caching"""
    key = f"nxperm:{doctype}:{ptype}"
    if key not in frappe.local.__dict__:
        policies = frappe.get_all(
            "NxPerm Policy",
            filters={"enabled": 1},
            or_filters={
                "target_doctype": doctype,
                "match_all_doctypes": 1,
            },
            or_conditions={
                "permission_type": [ptype, "*"],
            },
            order_by="priority asc",
            pluck="name",
        )
        # Load full doc
        frappe.local.__dict__[key] = [frappe.get_doc("NxPerm Policy", p) for p in policies]

    return frappe.local.__dict__[key]
```

### 16.8 Hướng dẫn implement trong app

**File structure cho app `nxperm`:**

```
nxperm/
├── __init__.py
├── hooks.py
├── nxperm/
│   ├── __init__.py
│   ├── api_check.py         # Engine: has_permission hook
│   ├── api_query.py         # Engine: permission_query_conditions hook
│   ├── api_field.py         # Engine: field-level overrides (client API)
│   ├── api_admin.py         # CRUD API cho NxPerm Policy (whitelist)
│   ├── condition_eval.py    # Condition evaluators registry
│   ├── value_resolver.py    # Value resolution từ nhiều nguồn
│   ├── cache.py             # Cache management
│   └── utils.py             # Helper functions
│
├── docs/                    # Tài liệu
│   └── design/nxperm-engine.md
│
├── fixtures/                # Pre-seeded policies mẫu
│   └── nxperm_policy.json
│
├── nxperm/doctype/
│   ├── nxperm_policy/
│   │   ├── nxperm_policy.json
│   │   ├── nxperm_policy.py
│   │   └── nxperm_policy.js
│   ├── nxperm_condition/
│   │   └── nxperm_condition.json    # Child table
│   ├── nxperm_field_override/
│   │   └── nxperm_field_override.json
│   └── nxperm_assignment/
│       ├── nxperm_assignment.json
│       ├── nxperm_assignment.py
│       └── nxperm_assignment.js
│
└── tests/
    ├── test_condition_eval.py
    ├── test_policy_kpi.py
    └── test_performance.py
```

### 16.9 Client-side Integration

Khi apply field overrides, cần trả về cho client JS để áp dụng:

```javascript
// nxperm/nxperm/doctype/nxperm_policy/nxperm_policy.js
// Hoặc global integration qua frappe.call khi load form

frappe.ui.form.on("Your DocType", {
    setup: function(frm) {
        // Gọi API lấy field overrides
        frappe.call({
            method: "nxperm.api_field.get_field_overrides",
            args: {
                doctype: frm.doctype,
                docname: frm.docname || ""
            },
            callback: function(r) {
                if (r.message) {
                    $.each(r.message, function(field, overrides) {
                        if (overrides.hidden) {
                            frm.set_df_property(field, "hidden", 1);
                        }
                        if (overrides.read_only) {
                            frm.set_df_property(field, "read_only", 1);
                        }
                        if (overrides.required) {
                            frm.set_df_property(field, "reqd", 1);
                        }
                    });
                }
            }
        });
    }
});
```

### 16.10 So sánh: Trước và Sau khi có NxExtendedPerm

#### Trước — Mỗi tình huống code riêng:

```python
# Trong mỗi controller file:
class KPIData(Document):
    def has_permission(self, ptype, user=None):
        # Time check
        if ptype == "write" and self.data_entry_deadline:
            if now() > self.data_entry_deadline:
                return False
        # Assignment check
        if not frappe.db.exists("KPI Assignment", {"user": user, "kpi": self.kpi}):
            return False
        return None

class KPIEvaluation(Document):
    def has_permission(self, ptype, user=None):
        # Logic khác tương tự nhưng khác DocType
        ...

class AnotherDocType(Document):
    def has_permission(self, ptype, user=None):
        # Cùng logic time-based nhưng viết lại
        ...
```

#### Sau — Cấu hình qua UI:

```
→ System Manager tạo NxPerm Policy trong UI
→ Không cần code controller cho từng DocType
→ Cùng 1 rule engine cho mọi DocType
→ Chỉ code 1 lần khi cần condition type mới
```

### 16.11 Roadmap

```
PHASE 1 — Core Engine (3-5 ngày)
├── Tạo app nxperm, các DocType cơ bản
├── Implement condition evaluators cốt lõi (role, field, time, user)
├── Hooks integration (has_permission, permission_query_conditions)
├── UI mẫu cho NxPerm Policy list/form
└── Unit tests cơ bản

PHASE 2 — Advanced Conditions (2-3 ngày)
├── Condition: user_in_table, user_assigned, cross_doc_field
├── NxPerm Assignment DocType + UI
├── Field-level override engine + client integration
└── Value resolver (user_field, doc_field, current_time)

PHASE 3 — UI & Admin (2-3 ngày)
├── Policy testing tool (simulate user + doc → test match)
├── Permission audit log (rule nào denied, lý do)
├── Bulk import/export policies
└── Debug mode (show which policy matched)

PHASE 4 — Production (2-3 ngày)
├── Performance optimization + indexing
├── Cache warming
├── Documentation + training
└── Migration tool (chuyển từ hardcode → policies)
```

### 16.12 Tổng kết

**NxExtendedPerm** giải quyết triệt để các vấn đề:

| Yêu cầu | Đáp ứng |
|----------|---------|
| Code 1 lần | Engine core viết 1 lần, mọi DocType dùng chung |
| Cấu hình qua UI | NxPerm Policy DocType + Conditions child table |
| Time-based | Condition type `time_before`, `time_after`, `time_between` |
| Function/Assignment-based | NxPerm Assignment + `user_assigned` condition |
| Field-level động | NxPerm Field Override + client integration |
| Context-dependent | Kết hợp nhiều conditions AND/OR |
| Delegation | `user_assigned` với time window |
| Query filtering | `permission_query_conditions` hook tự động |
| Multi-condition | AND/OR logic groups |
| Extensible | Thêm condition type mới = thêm 1 evaluator function |
| Audit | Deny reason tracking, policy match log |

> **Nguyên tắc:** NxExtendedPerm là **lớp bổ sung**, không thay thế Frappe core permissions.
> Luôn bật `override_default: false` (mặc định) để fallthrough về core permission khi không có policy nào match.
> Dùng `effect: Deny` làm mặc định (safe default). Chỉ dùng `effect: Allow` cho các exception cụ thể.

---

## 17. Đánh giá bảo mật: Phân quyền ERP đã đủ cho thực tế chưa?

> Phần này do **chuyên gia bảo mật ERP** đánh giá toàn bộ mô hình phân quyền
> (core Frappe + NxExtendedPerm) dưới góc nhìn **thực tế triển khai ERP doanh nghiệp**.
> Đánh giá dựa trên các tiêu chuẩn: SOX, ISO 27001, GDPR, và thực tiễn ERP Việt Nam.

---

### 17.1 Tổng quan đánh giá

| Tiêu chí | Core Frappe | + NxExtendedPerm | Cần thêm |
|----------|-------------|------------------|----------|
| Role-based CRUD | ✅ Đầy đủ | ✅ | - |
| Field-level tĩnh | ✅ Cơ bản (permlevel) | ✅ Field Override động | - |
| User Permission (record) | ✅ Cơ bản | ✅ Mở rộng | - |
| Time-based | ❌ Không có | ✅ Condition | - |
| Assignment/Function-based | ❌ Không có | ✅ NxPerm Assignment | - |
| Sharing | ✅ Cơ bản | ✅ | - |
| Workflow/State-based | ❌ Chỉ docstatus | ✅ workflow_state | - |
| Delegation | ❌ Không có | ✅ | - |
| **Segregation of Duties** | ❌ Không có | ❌ Chưa có | 🔴 **CẦN GẤP** |
| **Org Hierarchy** | ❌ Không có | ❌ Chưa có | 🔴 **CẦN GẤP** |
| **Break-Glass** | ❌ Không có | ❌ Chưa có | 🔴 **CẦN GẤP** |
| **Permission Review** | ❌ Không có | ❌ Chưa có | 🟡 Nên có |
| **Data Classification** | ❌ Không có | ❌ Chưa có | 🟡 Nên có |
| **API Security** | ⚠️ Cơ bản | ⚠️ | 🟡 Cần cải thiện |
| **Session/IP Restrict** | ❌ Không có | ❌ Chưa có | 🟢 Tuỳ chọn |
| **Audit Trail lịch sử** | ❌ Chỉ tracking | ❌ Chưa có | 🟡 Nên có |

> 🔴 **CẦN GẤP** = Phải có trước khi deploy ERP thực tế
> 🟡 **Nên có** = Cần cho compliance / doanh nghiệp lớn
> 🟢 **Tuỳ chọn** = Tuỳ mức độ bảo mật yêu cầu

---

### 17.2 🔴 Segregation of Duties (SoD) — Phân tách nhiệm vụ

#### Vấn đề

**SoD (Segregation of Duties)** là nguyên tắc an toàn quan trọng nhất trong ERP:
- **Một người không được vừa tạo PO, vừa approve PO**
- **Một người không được vừa nhập KPI, vừa đánh giá KPI của mình**
- **Một người không được vừa tạo invoice, vừa nhận thanh toán**

#### Hiện trạng

Cả Core Frappe và NxExtendedPerm đều không có cơ chế phát hiện hoặc ngăn chặn xung đột nhiệm vụ.

**Ví dụ nguy hiểm trong hệ thống KPI:**
- User A có role "KPI Data Entry" → nhập KPI cho chính mình
- User A có role "KPI Evaluator" → đánh giá KPI của chính mình
- → Kết quả: tự nhập, tự đánh giá, tự xác nhận — **mất tính khách quan**

#### Giải pháp — SoD Engine

```python
# sod/models.py
class SoDConflict:
    """
    Một cặp permission không được phép tồn tại đồng thời trên cùng 1 user trong 1 context.
    """
    # Ví dụ:
    SEPARATION_RULES = [
        # (doctype, ptype_A, ptype_B, context_field, message)
        ("KPI Data",    "create", "KPI Evaluation", "write", "period",
         "Người nhập KPI không được đồng thời đánh giá KPI trong cùng kỳ"),

        ("Purchase Order", "create", "Purchase Order", "submit",
         None, "Người tạo PO không được đồng thời submit PO"),

        ("Sales Invoice",  "create", "Payment Entry",  "create",
         "customer", "Người tạo invoice không được tạo payment entry cho cùng customer"),
    ]
```

**DocType: NxPerm SoD Rule**

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `rule_name` | Data | Tên quy tắc |
| `enabled` | Check | Bật/tắt |
| `severity` | Select | **hard_block** / **warning** / **audit_only** |
| `doctype_a` | Link → DocType | DocType thứ nhất |
| `ptype_a` | Select | Permission type A (create/write/submit) |
| `doctype_b` | Link → DocType | DocType thứ hai |
| `ptype_b` | Select | Permission type B |
| `context_field` | Data | (Optional) field để xác định "cùng bối cảnh" |
| `apply_to_same_user` | Check | Cảnh báo nếu cùng 1 user có cả 2 quyền |
| `apply_to_same_doc` | Check | Cảnh báo nếu user action trên cùng document |
| `message` | Text | Thông báo cho admin/Người dùng |
| `roles` | Table → Multi-select | (Optional) chỉ áp dụng cho role cụ thể. Để trống = tất cả |

**Cách hoạt động:**

```python
# Trong workflow hook — tự động check khi user thực hiện hành động
def check_sod(doc, method):
    """Hook: validate → check SoD trước khi save/submit"""
    user = frappe.session.user
    if user == "Administrator":
        return  # Bypass cho admin hệ thống

    rules = get_active_sod_rules(doc.doctype)
    for rule in rules:
        conflict = detect_sod_conflict(rule, doc, user)
        if conflict:
            if rule.severity == "hard_block":
                frappe.throw(_(rule.message), frappe.ValidationError)
            elif rule.severity == "warning":
                frappe.msgprint(_(f"Cảnh báo: {rule.message}"), alert=True, indicator="orange")
            # audit_only: chỉ log, không chặn


def detect_sod_conflict(rule, doc, user):
    """Phát hiện conflict cho 1 rule"""
    # Trường hợp 1: Cùng user có cả 2 quyền trên cùng context
    if rule.apply_to_same_user:
        has_perm_a = frappe.permissions.has_permission(rule.doctype_a, rule.ptype_a, user=user)
        has_perm_b = frappe.permissions.has_permission(rule.doctype_b, rule.ptype_b, user=user)
        if has_perm_a and has_perm_b:
            # Kiểm tra context (nếu có)
            if rule.context_field and doc.get(rule.context_field):
                # Kiểm tra user action trên cùng context value
                value = doc.get(rule.context_field)
                user_other_actions = frappe.db.exists(rule.doctype_b, {
                    rule.context_field: value,
                    "owner": user,
                })
                if user_other_actions:
                    return True
            else:
                return True  # Conflict thuần tuý
    return False
```

**Test phân quyền SoD (trong quy trình tuyển dụng/phân quyền):**

```python
# Khi assign role cho user, hệ thống cảnh báo nếu có SoD conflict:
def warn_sod_on_role_assignment(user, new_role):
    warnings = []
    # Lấy tất cả rules
    rules = frappe.get_all("NxPerm SoD Rule", {"enabled": 1})
    for rule in rules:
        # Kiểm tra nếu new_role + user's existing roles tạo conflict
        conflict = simulate_sod(rule, user, new_role)
        if conflict:
            warnings.append(conflict)
    if warnings:
        frappe.msgprint(
            f"Cảnh báo SoD: Gán role {new_role} có thể tạo xung đột: {', '.join(warnings)}",
            indicator="orange"
        )
```

---

### 17.3 🔴 Org Hierarchy — Permission kế thừa theo cây tổ chức

#### Vấn đề

Trong thực tế doanh nghiệp:
- Trưởng phòng Kinh doanh phải thấy được KPI của **tất cả nhân viên trong phòng**
- Giám đốc phải thấy KPI của **tất cả phòng ban**
- Nhân viên chỉ thấy KPI của **bản thân và đồng đội trong nhóm**

Hiện tại NxExtendedPerm chỉ filter theo `department = X` (so sánh bằng).
Không hỗ trợ quan hệ cha-con, không hỗ trợ cây tổ chức đa cấp.

#### Giải pháp — Inheritable Permission với Tree Structure

```python
# Sử dụng Nested Set Model (lft, rgt) của Frappe cho Department/Org Unit

def get_org_tree_condition(user, doctype, org_field="department"):
    """
    Trả về SQL condition cho phép user thấy dữ liệu của đơn vị mình
    VÀ tất cả đơn vị con.
    """
    employee = frappe.db.get_value("Employee", {"user": user},
                                     ["department", "name"], as_dict=True)
    if not employee:
        return "1=0"

    # Lấy lft, rgt của department của user
    dept = frappe.db.get_value("Department", employee.department, ["lft", "rgt"], as_dict=True)
    if not dept:
        return f"`tab{doctype}`.`{org_field}` = {frappe.db.escape(employee.department)}"

    # Filter: department có lft, rgt nằm trong khoảng của department user
    # → user thấy được dữ liệu của đơn vị mình VÀ các đơn vị con
    return f"""`tab{doctype}`.`{org_field}` IN (
        SELECT `name` FROM `tabDepartment`
        WHERE `lft` >= {dept.lft} AND `rgt` <= {dept.rgt}
    )"""
```

**Mở rộng NxPerm Condition với tree operator:**

| Condition Type | value | Ý nghĩa |
|----------------|-------|---------|
| `field_in_tree` | `department` | Field của document phải thuộc cây đơn vị của user (gồm cả cấp dưới) |
| `field_in_tree_self_only` | `department` | Chỉ đơn vị trực tiếp, không gồm cấp dưới |
| `field_in_tree_ancestor` | `department` | Đơn vị cấp trên của user (user thấy được dữ liệu cấp trên) |

---

### 17.4 🔴 Break-Glass — Truy cập khẩn cấp

#### Vấn đề

Khi người phụ trách đi vắng, cần có cơ chế **phá rào khẩn cấp** để:
- Người khác tạm thời được quyền nhập liệu KPI
- Manager được approve PO thay cho người vắng
- **Quan trọng:** Mọi break-glass đều phải được **log + approve sau**

#### Hiện trạng

Không có cơ chế nào. Nếu chỉ có 1 người có quyền, người đó đi vắng → hệ thống tê liệt.

#### Giải pháp — Break-Glass Protocol

```python
# DocType: NxPerm BreakGlass
# ┌──────────────────────┬──────────┬────────────────────────────────┐
# │ Field                │ Kiểu     │ Mô tả                         │
# ├──────────────────────┼──────────┼────────────────────────────────┤
# │ requester            │ Link→User│ Người yêu cầu                  │
# │ reason               │ Text     │ Lý do khẩn cấp                 │
# │ target_doctype       │ Link→Doc │ DocType cần quyền              │
# │ requested_permission │ Select   │ read/write/create/submit       │
# │ target_doc           │ Dynamic  │ Document cụ thể (hoặc * nếu all)│
# │ valid_from           │ Datetime │ Bắt đầu                        │
# │ valid_until          │ Datetime │ Kết thúc                       │
# │ status               │ Select   │ Pending / Approved / Denied / Expired │
# │ approved_by          │ Link→User│ Người approve                   │
# │ approved_at          │ Datetime │ Thời gian approve               │
# └──────────────────────┴──────────┴────────────────────────────────┘

class NxPermBreakGlass(Document):
    def after_insert(self):
        # Notify người có thể approve
        notify_approvers(self)

    def on_update(self):
        if self.status == "Approved":
            # Tự động tạo NxPerm Assignment tạm thời
            assignment = frappe.get_doc({
                "doctype": "NxPerm Assignment",
                "user": self.requester,
                "function_role": "___break_glass___",  # role đặc biệt
                "target_doctype": self.target_doctype,
                "target_document": self.target_doc,
                "permission_type": self.requested_permission,
                "from_date": self.valid_from,
                "to_date": self.valid_until,
                "reference_break_glass": self.name,  # track nguồn gốc
            })
            assignment.insert(ignore_permissions=True)
            frappe.msgprint(f"Break-Glass approved: {self.name}")

            # Audit log
            log_audit(
                event="break_glass_granted",
                user=self.requester,
                doctype=self.target_doctype,
                docname=self.target_doc,
                detail=f"Break-glass: {self.reason}, approved by {self.approved_by}"
            )
```

**Nguyên tắc Break-Glass trong engine:**

```python
# Trong nxperm_has_permission, KIỂM TRA BREAK-GLASS TRƯỚC KHI TỪ CHỐI:
def nxperm_has_permission(doc, ptype, user):
    # ... đánh giá policies ...

    # Nếu không có policy nào match → check break-glass trước khi từ chối
    if has_active_break_glass(user, doctype, ptype, doc_name):
        log_audit(
            event="break_glass_used",
            user=user,
            doctype=doctype,
            docname=doc_name,
            detail="Break-glass access granted"
        )
        return True

    return None  # Fallthrough
```

---

### 17.5 🟡 Permission Review & Certification

#### Vấn đề

Theo SOX/ISO 27001, doanh nghiệp phải định kỳ:
1. **Review** ai đang có quyền gì
2. **Certify** quyền còn cần thiết không
3. **Revoke** quyền không còn dùng

Hiện tại không có cơ chế này.

#### Giải pháp — Permission Review Schedule

```python
# DocType: NxPerm Review
# - review_cycle: Monthly / Quarterly / Yearly
# - review_date: ngày review
# - assigned_to: người review (thường là trưởng bộ phận hoặc system manager)
# - status: Pending / Certified / Revoked

# Report: "User Permission Matrix" xuất tất cả user + roles + NxPerm Assignments
# Report: "Unused Permissions" — user không login > 90 ngày nhưng vẫn có quyền
```

**Tính năng cần implement trong phase sau:**
```python
def generate_permission_matrix():
    """Xuất ma trận user × role × doctype × permission type"""
    rows = []
    users = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"})
    for user in users:
        roles = frappe.get_roles(user.name)
        # Lấy DocPerm coverage từ roles
        for role in roles:
            perms = frappe.get_all("DocPerm", filters={"role": role},
                                   fields=["parent", "read", "write", "create"])
            for p in perms:
                rows.append({"user": user.name, "role": role, "doctype": p.parent, ...})
    # Xuất Excel
    ...


def detect_orphan_permissions():
    """Phát hiện user không còn active nhưng vẫn có quyền"""
    inactive_users = frappe.db.sql("""
        SELECT u.name FROM `tabUser` u
        LEFT JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE u.enabled = 1
        AND u.last_active_date < DATE_SUB(NOW(), INTERVAL 90 DAY)
        AND u.user_type = 'System User'
        AND hr.role IS NOT NULL
        GROUP BY u.name
    """)
    return inactive_users
```

---

### 17.6 🟡 Data Classification — Phân loại dữ liệu

#### Vấn đề

Không phải dữ liệu nào cũng có độ nhạy cảm như nhau:
- **Công khai:** Tên phòng ban, chức danh
- **Nội bộ:** KPI mục tiêu
- **Nhạy cảm:** Lương, thưởng, KPI thực tế
- **Bí mật:** Chiến lược kinh doanh, KPI chiến lược

Hiện tại không có khái niệm classification, không thể cấm export dữ liệu nhạy cảm.

#### Giải pháp — Data Classification Tag + Prevent Export

```python
# Mở rộng field của NxPerm Policy với:
# - data_classification: public / internal / sensitive / confidential
# - prevent_export: nếu bật → không cho export/bản in khi policy match

# Trong export hook:
def check_export_permission(doctype, user):
    """Kiểm tra trước khi export"""
    if is_data_classified(doctype, "confidential"):
        # Chỉ cho export nếu user được phép
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("Dữ liệu bảo mật không được phép xuất")
```

---

### 17.7 🟡 API & MCP Security — Bảo vệ API endpoint

#### Vấn đề

Trong hệ thống NxCom, có 2 cổng chính:
1. **Frappe REST API** (`/api/method/...`, `/api/resource/...`)
2. **MCP Tools** (qua `frappe.client.*`, gọi trực tiếp Python)

MCP bypass các guard của Frappe (CSRF, HTTP method check, perm decorator).
Một tool `frappe.client.get_doc('KPI Library', '*')` có thể leak dữ liệu.

#### Giải pháp — API Permission Layer

```python
# Trong MCP tool wrapper, kiểm tra permission trước khi trả dữ liệu:

# 1. Ràng buộc phạm vi: MCP chỉ trả về dữ liệu người dùng được phép
def mcp_safe_get_doc(doctype, name):
    """Wrapper frappe.get_doc có check permission"""
    doc = frappe.get_doc(doctype, name)
    if not frappe.has_permission(doctype, "read", doc):
        frappe.throw("No permission", frappe.PermissionError)
    return doc


# 2. List documents: filter qua permission query conditions
def mcp_safe_list_documents(doctype, filters=None, limit=20):
    """Wrapper frappe.get_list có permission check"""
    # Frappe.get_list tự động build_match_conditions
    # Nếu NxPerm query conditions hook đã gắn → tự động filter
    return frappe.get_list(doctype, filters=filters, limit=limit)


# 3. Rate limiting trên MCP endpoint
def mcp_rate_limit(key, max_requests=100, window_seconds=60):
    """Giới hạn số request MCP từ 1 user"""
    # Dùng Redis để count requests
    pass
```

---

### 17.8 🟡 Policy Conflict Resolution — Giải quyết xung đột

#### Vấn đề

Khi có nhiều policies, xung đột là không tránh khỏi:

| Policy | Effect | Priority | Condition |
|--------|--------|----------|-----------|
| Block write sau deadline | Deny | 1 | Time after deadline |
| Manager luôn được write | Allow | 5 | Role = Manager |
| **Kết quả** | **Allow** | Manager vẫn write được dù quá hạn | ✅ Đúng |
| **Nhưng nếu đảo priority?** | | | |

**Hiện tại chưa giải quyết triệt để các kịch bản:**
- 2 policies cùng priority, 1 Allow 1 Deny → cái nào thắng?
- Policy A match trước, effect Allow → có skip hay không?

#### Giải pháp — Conflict Resolution Strategy

```python
# Trong engine, thêm config cho mỗi policy:
RESOLUTION_STRATEGIES = {
    "priority_allow_deny": """
        Priority-based. Cùng priority → Deny thắng (safe default).
        Dừng đánh giá khi gặp match đầu tiên.
        FIRST MATCH WINS (nếu không có stop_on_match)
    """,
    "deny_override_allow": """
        Deny luôn thắng Allow bất kể priority.
        Áp dụng cho compliance-critical policies (SOX).
    """,
    "most_specific_wins": """
        Policy với nhiều conditions nhất (most specific) được ưu tiên.
    """
}

# Thêm field cho NxPerm Policy:
# - resolution: select → "first_match" / "deny_wins" / "allow_wins"
```

---

### 17.9 🟡 Policy Simulation — Mô phỏng phân quyền

#### Cần thiết

Trước khi deploy policy mới, cần **test thử** trên user thật.

#### Giải pháp — "What-If" Tool

```python
def simulate_policy(policy_name, test_user, test_doctype, test_ptype, test_doc=None):
    """
    Mô phỏng: user X có được phép Y trên document Z không?
    Trả về: result + giải thích từng bước
    """
    results = {
        "user": test_user,
        "doctype": test_doctype,
        "ptype": test_ptype,
        "document": test_doc,
        "steps": [],
        "final_decision": None,
    }

    # Step 1: Core Frappe roles
    roles = frappe.get_roles(test_user)
    results["steps"].append({"step": "Frappe Roles", "roles": roles})

    # Step 2: NxPerm Policies
    policies = get_nxperm_policies(test_doctype, test_ptype)
    for p in policies:
        match = _evaluate_conditions(p, test_doc, test_user)
        results["steps"].append({
            "step": f"NxPerm Policy: {p.rule_name}",
            "priority": p.priority,
            "effect": p.effect,
            "conditions_match": match,
            "conditions_detail": [{
                "type": c.condition_type,
                "field": c.field,
                "operator": c.operator,
                "value": c.value,
                "result": _eval_single(c, test_doc, test_user)
            } for c in p.conditions]
        })
        if match:
            results["final_decision"] = p.effect
            break

    # Step 3: SoD check
    sod_conflicts = detect_sod_conflicts(test_user, test_doctype, test_ptype)
    results["sod_conflicts"] = sod_conflicts

    return results
```

---

### 17.10 Bảng đánh giá chi tiết: 12 rủi ro bảo mật ERP

| # | Rủi ro | Mô tả | Mức | Giải pháp |
|---|--------|-------|-----|-----------|
| R1 | **SoD violation** | 1 user vừa nhập vừa đánh giá KPI | 🔴 CRITICAL | SoD Rule Engine (§17.2) |
| R2 | **Org hierarchy leak** | User thấy data đơn vị khác qua list view | 🔴 HIGH | Tree Permission (§17.3) |
| R3 | **No break-glass** | Người duy nhất vắng → bottleneck | 🔴 HIGH | Break-Glass Protocol (§17.4) |
| R4 | **Permission creep** | User chuyển phòng nhưng còn quyền cũ | 🟡 MEDIUM | Permission Review (§17.5) |
| R5 | **Data export leak** | User export KPI lương ra Excel mang về nhà | 🟡 MEDIUM | Data Classification (§17.6) |
| R6 | **MCP API bypass** | Tool gọi trực tiếp Python không qua permission check | 🟡 MEDIUM | API Permission Layer (§17.7) |
| R7 | **Policy conflict** | 2 policies đối nghịch → undefined behavior | 🟡 MEDIUM | Conflict Resolution (§17.8) |
| R8 | **Privilege escalation** | User dùng field override API để tăng quyền | 🟡 MEDIUM | Validate field overrides server-side |
| R9 | **No permission audit** | Không biết ai đã làm gì, khi nào | 🟡 MEDIUM | Audit Trail (§17.11) |
| R10 | **TOCTOU race** | Permission thay đổi giữa check và action | 🟢 LOW | Transaction guard |
| R11 | **Brute-force API** | Gọi API liên tục dù bị từ chối | 🟢 LOW | Rate limiting |
| R12 | **Session fixation** | Giữ session cũ sau khi bị thu hồi quyền | 🟢 LOW | Session refresh on permission change |

### 17.11 Bổ sung: Audit Trail chi tiết — Permission Event Log

**DocType cần thêm: NxPerm Audit Log** — bắt buộc cho compliance.

| Field | Mô tả |
|-------|-------|
| `event_type` | `grant` / `revoke` / `deny` / `break_glass` / `sod_violation` / `policy_change` |
| `user` | User bị ảnh hưởng |
| `actor` | User thực hiện hành động (có thể khác target) |
| `doctype` | DocType bị ảnh hưởng |
| `docname` | Document cụ thể (nếu có) |
| `policy` | NxPerm Policy triggered (nếu có) |
| `effect` | allow / deny |
| `reason` | Lý do (từ push_perm_check_log) |
| `ip_address` | IP của request |
| `timestamp` | Thời gian (auto set) |
| `detail` | JSON detail |

**Cách tích hợp vào engine:**

```python
def log_audit(event_type, user, doctype=None, docname=None,
               policy=None, effect=None, reason=None, detail=None):
    """Ghi audit log bất đồng bộ (không block request)"""
    frappe.enqueue(
        "nxperm.audit.log_audit_async",
        queue="short",
        event_type=event_type,
        user=user,
        doctype=doctype,
        docname=docname,
        policy=policy,
        effect=effect,
        reason=reason,
        detail=detail,
        ip_address=frappe.local.request_ip if frappe.request else None,
    )
```

---

### 17.12 Kết luận: Lộ trình hoàn thiện

#### Mức độ sẵn sàng cho production ERP

```
CURRENT STATE (core Frappe + NxExtendedPerm):
├── Dùng được cho:                                                 ✅
│   - Hệ thống nhỏ (< 50 users)                                   
│   - Không yêu cầu compliance (SOX/ISO)                          
│   - Role đơn giản, không SoD                                    
│   - Một cấp tổ chức (không cây hierarchy)                       
│                                                                  
├── CẦN thêm trước khi deploy ERP lớn (> 200 users):              🔴
│   - 17.2 SoD Engine              (3-5 ngày)                     
│   - 17.3 Org Hierarchy           (2-3 ngày)                     
│   - 17.4 Break-Glass             (2-3 ngày)                     
│   - 17.11 Audit Log              (1-2 ngày)                     
│                                                                  
└── Nên thêm cho enterprise:                                       🟡
    - 17.5 Permission Review       (2-3 ngày)                    
    - 17.6 Data Classification     (1-2 ngày)                    
    - 17.7 API Security Layer      (2-3 ngày)                    
    - 17.9 Policy Simulation       (1-2 ngày)                    
```

#### Đánh giá tổng thể

| Khía cạnh | Điểm | Lý do |
|-----------|------|-------|
| **Tính năng permission** | 7/10 | Đáp ứng tốt role/field/record-based, nhưng thiếu org hierarchy |
| **Bảo mật** | 6/10 | SoD là lỗ hổng nghiêm trọng chưa xử lý. Break-glass chưa có. |
| **Compliance** | 4/10 | Chưa đáp ứng SOX/ISO 27001 nếu thiếu SoD + Audit + Review |
| **Khả năng mở rộng** | 8/10 | Kiến trúc condition engine rất linh hoạt, dễ thêm evaluator |
| **Admin UI** | 7/10 | Config được qua UI, nhưng còn thiếu simulation tool |
| **Performance** | 7/10 | Cache + indexing ok, nhưng cẩn thận với N+1 queries khi nhiều policies |
| **Tổng thể ERP thực tế** | **6.5/10** | Đủ cho SME, cần thêm 4 module cho enterprise |

#### Priority khắc phục

```
Ưu tiên 1 (TRƯỚC KHI GO-LIVE):
  [🔴 R1] SoD Engine
  [🔴 R2] Org Hierarchy Permission
  [🔴 R3] Break-Glass Protocol
  [🟡 R9] Audit Trail

Ưu tiên 2 (THÁNG 1 SAU GO-LIVE):
  [🟡 R4] Permission Review Schedule
  [🟡 R5] Data Classification + Export Guard
  [🟡 R7] Policy Conflict Resolution

Ưu tiên 3 (THÁNG 2-3):
  [🟡 R6] MCP Security Layer
  [🟡 R8] Field Override Server Validation
  [🟡 R11] Simulation Tool
  [🟢 R10+R12] Edge cases hardening
```

---

### 17.13 Tổng kết

> **"Permission system có thể đủ cho demo, nhưng chưa đủ cho ERP thực tế."**

**Những điểm mạnh của NxExtendedPerm:**
- Kiến trúc condition engine rất tốt — dễ mở rộng
- Config qua UI — giảm code lặp
- Hooks integration — không xung đột với Frappe core
- 10 tình huống KPI đã cover được nhiều pattern phổ biến
- Field override động là ý tưởng mạnh

**Những điểm còn thiếu cho ERP thực tế:**
1. **🔴 SoD (Segregation of Duties)** — Rủi ro số 1, không thể deploy ERP tài chính nếu thiếu
2. **🔴 Org Hierarchy** — Filter bằng department phẳng không đủ. ERP có cây tổ chức 5-7 cấp.
3. **🔴 Break-Glass** — Thiếu cơ chế này, doanh nghiệp sẽ gọi điện yêu cầu "chạy SQL" thay vì xài đúng tính năng
4. **🟡 Audit Trail chi tiết** — Cần cho compliance và điều tra sự cố
5. **🟡 Permission Review** — SOX yêu cầu review định kỳ, nếu không → fail audit
6. **🟡 API Security** — MCP bypass, cần wrapper layer

**Khuyến nghị:**
- **Không deploy production ERP tài chính** nếu chưa có SoD + Audit
- **Có thể deploy** cho hệ thống KPI nội bộ (không liên quan tài chính) với core Frappe + NxExtendedPerm
- **SME (< 50 users, 1 cấp tổ chức)** chỉ cần thêm Audit là đủ
- **Enterprise (> 200 users, đa cấp, compliance)** cần đủ cả 4 module priority 1
