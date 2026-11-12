# -*- coding: utf-8 -*-
"""Variable Catalog — tầng danh mục biến của AlumGlass.

Cấu trúc:
- `registry`  : sổ đăng ký adapter (thuần Python).
- `rules`     : bộ luật lọc + dedupe (THUẦN Python, không import frappe).
- `context`   : ngữ cảnh chứng từ (đọc DB — chỉ import khi thật sự chạy).
- `adapters`  : từng nguồn biến (§3 của spec).

⚠️ File này CỐ Ý chỉ re-export phần thuần Python: test `rules` chạy được bằng
`python3 -I` trên máy không có site. Import `context`/`adapters` (có frappe)
phải làm ở nơi thật sự cần, không ở đây.
"""
from alumglass.variable_sources.registry import (  # noqa: F401
    get_adapter,
    get_adapter_label,
    get_adapters,
    list_source_kinds,
    register_adapter,
)
from alumglass.variable_sources.rules import (  # noqa: F401
    EXCLUDE_ALL,
    INCLUDE_ALL,
    active_source_kinds,
    build_groups,
    dedupe_candidates,
    rule_matches,
    select_candidates,
)
