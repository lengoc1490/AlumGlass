"""D3 — Seed `Formula Variable Binding` (FVB) từ master data của alumglass.

Từ B4 (2026-11-27), toàn bộ logic nằm ở `alumglass.fb_binding_sync` —
patch này chỉ gọi lại để kỳ migrate đầu tiên có sẵn binding. Lý do tách: cùng
một việc còn phải gọi được **sau khi thêm biến mới** (API
`alumglass.api.variable_catalog.sync_fb_bindings`), ⛔ đợi kỳ migrate sau.

Hai nhóm binding (đọc kỹ ở `fb_binding_sync.plan`):
  1. Hằng số toàn cục từ `Formula Global Variable` → `source_type=constant`.
  2. Biến hệ có nguồn `AL Profile System` / `AL Product Type` → FVB
     `linked_doctype_field`, phạm vi `AL Bom Set`.

Idempotent: đã có binding cùng (variable_name, applies_to_doctype, is_global)
thì bỏ qua. Biến không có đường link tương ứng ⛔ seed (engine vẫn đọc trực
tiếp từ Variable Library như cũ).
"""

import frappe

from alumglass.fb_binding_sync import sync


def execute():
    result = sync(dry_run=False)
    frappe.logger("alumglass").info(
        "D3 seed_fvb_from_variable_library (qua fb_binding_sync): "
        "created %d, skipped %d."
        % (len(result.get("created") or []), len(result.get("skipped") or []))
    )
