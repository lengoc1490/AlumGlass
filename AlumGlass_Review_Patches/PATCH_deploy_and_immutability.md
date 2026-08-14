# Patch 2: Khai báo dependency + khoá sửa AL BOM Version đã Published

## 2.1. `hooks.py` — khai báo `required_apps`

**Vấn đề:** `bom_orchestrator.py` import trực tiếp `formula_builder.formula_utils
.engine_public` và `formula_builder.flexible_formula_engine`, nhưng
`hooks.py`/`pyproject.toml` không khai báo app này là dependency bắt buộc.
Nếu `bench install-app alumglass` chạy trên site chưa có `formula_builder`,
app cài thành công (không lỗi lúc install) nhưng **crash ngay khi bấm "Tính
giá" lần đầu** (`ModuleNotFoundError`), gây trải nghiệm xấu và khó debug cho
người triển khai.

**Thêm vào `hooks.py`** (ngay dưới các biến `app_*`):
```python
required_apps = ["formula_builder"]
```
Frappe sẽ tự chặn `bench install-app alumglass` nếu `formula_builder` chưa
được cài trên bench, báo lỗi rõ ràng ngay từ bước cài đặt thay vì runtime.

**Ngoài ra khuyến nghị** ghi rõ version tối thiểu trong README (đã có ghi
"formula_utils v29.1+" trong docstring `hooks.py` — nên chuyển thành check
runtime, ví dụ trong `after_install`:
```python
def after_install():
    import formula_builder
    # ... assert version nếu formula_builder expose __version__
    install_all_custom_fields()
```

## 2.2. `al_bom_version.py` — khoá sửa snapshot sau khi Published

**Vấn đề:** `before_insert` chụp snapshot đúng 1 lần, nhưng không có gì chặn
việc sửa trực tiếp field `bom_set_snapshot`/`cost_template_snapshot` sau khi
`workflow_state = "Published"`. Điều này phá vỡ đúng lời hứa "Immutable BOM
versions" nêu trong README — về mặt kỹ thuật, ai có quyền sửa field vẫn có
thể thay đổi 1 version đã dùng để báo giá cho khách, khiến `ConfigSnapshot`
tham chiếu tới version đó không còn phản ánh đúng lịch sử.

**Thêm vào `al_bom_version.py`:**
```python
class ALBOMVersion(Document):
    """Snapshot bất biến của BOM - quản lý qua Workflow."""

    def before_insert(self):
        if not self.bom_set_snapshot:
            self._take_snapshots()

    def validate(self):
        self._guard_published_immutability()

    def _guard_published_immutability(self):
        """Chặn sửa snapshot fields sau khi đã Published — bảo toàn tính
        bất biến (immutable) mà README cam kết. Chỉ cho phép đổi
        workflow_state (vd Published -> Retired), không cho đổi nội dung.
        """
        if self.is_new():
            return
        prev = frappe.db.get_value(
            self.doctype, self.name,
            ["workflow_state", "bom_set_snapshot", "cost_template_snapshot"],
            as_dict=True,
        )
        if not prev or prev.workflow_state != "Published":
            return
        if (self.bom_set_snapshot != prev.bom_set_snapshot
                or self.cost_template_snapshot != prev.cost_template_snapshot):
            frappe.throw(
                "AL BOM Version đã ở trạng thái Published — không được sửa "
                "bom_set_snapshot/cost_template_snapshot. Hãy tạo 1 version "
                "mới (AL Design Revision) thay vì sửa version cũ, để giữ "
                "đúng lịch sử báo giá đã gửi khách hàng."
            )

    def on_update(self):
        """Cập nhật current_version trên BOM cha khi Published."""
        if self.workflow_state == "Published" and self.bom:
            frappe.db.set_value("AL BOM", self.bom, "current_version", self.name)

    # ... phần _take_snapshots() và _get_bom_item_formula_fields() giữ nguyên
```

**Lưu ý:** guard này chỉ chặn ở tầng Document (Python) — vẫn nên cân nhắc
thêm `is_submittable = 1` cho `AL BOM Version` ở bản sau (dùng `docstatus`
0/1/2 chuẩn của Frappe) để có khoá chặt hơn ở tầng framework thay vì tự viết
guard tay; nhưng việc đó đổi cách Workflow hiện tại đang vận hành (theo
`workflow_state`), nên cần đánh giá kỹ trước khi đổi — patch trên là bản vá
tối thiểu, an toàn, không phá vỡ Workflow đang có.
