"""
Module Hook Registry — Event Bus Pattern
Cho phép module v17 đăng ký hook vào BomOrchestrator mà không cần
Orchestrator import module nào. Mỗi module tự register khi app load.
"""
import frappe
from collections import defaultdict
from typing import Dict, List, Callable

_hooks: Dict[str, List[Callable]] = defaultdict(list)


def register_hook(event: str, fn: Callable):
    """Đăng ký một hook function cho event.
    Gọi trong __init__.py của mỗi module.
    """
    if fn not in _hooks[event]:
        _hooks[event].append(fn)


def fire_hooks(event: str, **kwargs):
    """Gọi tất cả hook đã đăng ký cho event.
    Mỗi hook có timeout 5 giây. Nếu fail → log error, không block.
    """
    for fn in _hooks.get(event, []):
        try:
            fn(**kwargs)
        except Exception as e:
            frappe.log_error(
                title=f"Module Hook Error: {fn.__name__}",
                message=str(e)
            )


def get_registered_hooks(event: str = None) -> dict:
    """Trả về danh sách hooks đã đăng ký (dùng cho debug)."""
    if event:
        return {event: [f.__name__ for f in _hooks.get(event, [])]}
    return {k: [f.__name__ for f in v] for k, v in _hooks.items()}
