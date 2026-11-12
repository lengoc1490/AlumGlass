# -*- coding: utf-8 -*-
"""Sổ đăng ký adapter nguồn biến — THUẦN PYTHON, không import frappe.

Cách mở rộng (đúng thiết kế data-driven):
    @register_adapter("nguon_moi", label="Nguồn mới", order=55)
    def nguon_moi(ctx):
        return [ ... candidate dict ... ]

Sau đó thêm 1 dòng `source_kind` vào options của `AL Variable Profile Rule`
và khai rule trong profile. Catalog core không phải sửa.
"""
from collections import namedtuple

Adapter = namedtuple("Adapter", "source_kind label order fn")

_ADAPTERS = {}
_ADAPTER_SEQ = []


def register_adapter(source_kind, label="", order=100):
    """Decorator đăng ký 1 nguồn biến.

    `order` càng nhỏ càng được ưu tiên khi dedupe trùng tên (adapter đăng ký
    trước thắng khi mọi tiêu chí khác hoà).
    """
    kind = (source_kind or "").strip()
    if not kind:
        raise ValueError("source_kind không được rỗng")

    def decorator(fn):
        if kind in _ADAPTERS:
            # Ghi đè có kiểm soát: lần đăng ký sau thay bản trước, nhưng giữ
            # nguyên vị trí để thứ tự ưu tiên không nhảy khi import lại.
            _ADAPTERS[kind] = Adapter(kind, label or kind, int(order), fn)
            return fn
        _ADAPTERS[kind] = Adapter(kind, label or kind, int(order), fn)
        _ADAPTER_SEQ.append(kind)
        return fn

    return decorator


def get_adapters():
    """Trả danh sách adapter đã đăng ký, sắp theo `order` rồi thứ tự khai."""
    return sorted(
        (_ADAPTERS[k] for k in _ADAPTER_SEQ),
        key=lambda a: (a.order, _ADAPTER_SEQ.index(a.source_kind)),
    )


def get_adapter(source_kind):
    return _ADAPTERS.get(source_kind)


def list_source_kinds():
    """Metadata cho UI/admin: [{kind, label, order}]."""
    return [
        {"kind": a.source_kind, "label": a.label, "order": a.order}
        for a in get_adapters()
    ]


def get_adapter_label(source_kind):
    adapter = _ADAPTERS.get(source_kind)
    return adapter.label if adapter else (source_kind or "")
