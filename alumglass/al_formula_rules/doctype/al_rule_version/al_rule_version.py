# -*- coding: utf-8 -*-
"""AL Rule Version — bản chụp (snapshot) của một `AL Rule` theo thời gian.

⚠️ CHỈ GIỮ PARITY — CHƯA CÓ MÃ TẠO BẢN GHI MỚI:
    Cấu trúc này chép nguyên từ doctype version của rule cũ (đã xoá
    2026-11-23; dữ liệu version cũ được patch migrate chép sang đây) — cùng
    toàn bộ field: rule / version_name / valid_from / workflow_state /
    rule_snapshot_json — để chặng gộp không làm mất đường versioning đã có.

    Đã xác minh: **không có mã nào tạo bản ghi `AL Rule Version`** — không
    `validate`/`on_update` của `AL Rule`, không hook, không scheduler, không
    API nào ghi version. Vì vậy `AL Rule.current_version` sẽ luôn trống.
    Đây là chỗ GIỮ CHỖ cho versioning thật ở chặng sau.

    ⛔ Được tuyên bố là "đã có version" cho tới khi mã tạo bản ghi tồn tại.
"""

from frappe.model.document import Document


class ALRuleVersion(Document):
    """Bản chụp cấu hình của `AL Rule` (xem cảnh báo versioning ở đầu tệp)."""

    pass
