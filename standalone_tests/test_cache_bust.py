# -*- coding: utf-8 -*-
"""Test standalone cho `alumglass/setup/cache_bust.py` (hook `after_migrate`).

BỐI CẢNH (Owner 2026-11-23)
───────────────────────────
Frappe nhúng nội dung `doctype_js` vào form meta rồi cache ở Redis dưới hash
`doctype_form_meta` khi site TẮT developer mode (`frappe/desk/form/meta.py:36-49`).
Kéo mã mới + `bench restart` KHÔNG làm mới JS ⇒ hook `after_migrate` phải xoá
cache này để `bench migrate` là đủ đưa mã mới vào hiệu lực.

VÌ SAO ĐẶT Ở `standalone_tests/`
──────────────────────────────────
`bench run-tests --app alumglass` os.walk toàn bộ package `alumglass/` ⇒ một
tệp stub `frappe` nằm trong package sẽ thay `sys.modules["frappe"]` và phá lượt
chạy test của site (xem docstring `standalone_tests/test_phase_b_fbmax.py`).

CÁCH CHẠY (không cần site):
    python3 standalone_tests/test_cache_bust.py
"""

import importlib.util
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_CACHE_BUST_PATH = os.path.join(
    _REPO_ROOT, "alumglass", "setup", "cache_bust.py")


# ═══════════════════════════════════════════════════════════════════
# Stub `frappe` — cache SPY (ghi lại mọi lệnh hdel/delete_value)
# ═══════════════════════════════════════════════════════════════════
class FakeCache:
    """Cache in-memory tối thiểu + spy.

    Giữ đúng ngữ nghĩa Frappe mà hook dựa vào:
      · `hdel(name, key)` trên hash/key KHÔNG tồn tại = no-op (không ném);
      · `delete_value(key, shared=True)` xoá theo khoá `shared`.
    """

    def __init__(self, store=None):
        self.store = dict(store or {})
        self.hdel_calls = []
        self.delete_calls = []

    def hdel(self, name, key, shared=False):
        self.hdel_calls.append((name, key, shared))
        self.store.pop((name, key), None)

    def delete_value(self, keys, user=None, make_keys=True, shared=False):
        self.delete_calls.append((keys, shared))
        if isinstance(keys, (list, tuple)):
            for key in keys:
                self.store.pop(("__value__", key, shared), None)
        else:
            self.store.pop(("__value__", keys, shared), None)


class FakeLogger:
    def __init__(self):
        self.infos = []

    def info(self, msg, *args, **kwargs):
        self.infos.append((msg, args, kwargs))

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


class FakeFrappe(types.ModuleType):
    def __init__(self):
        super().__init__("frappe")
        self._cache = FakeCache()
        self._logger = FakeLogger()
        self.logger_calls = []

    def cache(self):
        return self._cache

    def logger(self, name=None):
        self.logger_calls.append(name)
        return self._logger


def install_stub():
    stub = FakeFrappe()
    sys.modules["frappe"] = stub
    return stub


def load_cache_bust():
    """Nạp tệp hook trực tiếp theo đường dẫn (không cần package `alumglass`)."""
    spec = importlib.util.spec_from_file_location(
        "alumglass_cache_bust_under_test", _CACHE_BUST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ═══════════════════════════════════════════════════════════════════
# Harness tối thiểu (không cần pytest, chạy được bằng python3 trực tiếp)
# ═══════════════════════════════════════════════════════════════════
_passed = 0
_failed = []


def check(name, fn):
    global _passed
    try:
        fn()
        _passed += 1
        print("  PASS  " + name)
    except Exception as exc:  # noqa: BLE001
        _failed.append(name)
        print("  FAIL  " + name)
        print("        " + str(exc))


def eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError("%s\n        thực tế: %r\n        mong đợi: %r"
                             % (msg or "không khớp", actual, expected))


def assert_(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "assert thất bại")


# ═══════════════════════════════════════════════════════════════════
# Ca test
# ═══════════════════════════════════════════════════════════════════
STUB = install_stub()
CACHE_BUST = load_cache_bust()


def reset():
    """Cache + logger sạch cho từng ca (spy không được dính dữ liệu ca trước)."""
    STUB._cache = FakeCache()
    STUB._logger = FakeLogger()
    STUB.logger_calls = []


def test_xoa_dung_2_key_doctype():
    reset()
    CACHE_BUST.after_migrate()
    calls = [(name, key) for (name, key, _shared) in STUB._cache.hdel_calls]
    eq(calls, [
        ("doctype_form_meta", "Quotation"),
        ("doctype_form_meta", "Sales Order"),
    ], "phải xoá ĐÚNG 2 key form meta của Quotation + Sales Order")


def test_xoa_assets_json_shared():
    reset()
    CACHE_BUST.after_migrate()
    eq(STUB._cache.delete_calls, [("assets_json", True), ("assets_json", False)],
       "assets_json phải xoá CẢ khoá shared (đường đọc get_assets_json) lẫn "
       "khoá thường (đường `bench clear-cache`)")


def test_cache_trong_khong_nem():
    reset()                     # rỗng hoàn toàn
    # ⛔ được ném khi cache/hash không tồn tại
    CACHE_BUST.after_migrate()
    eq(len(STUB._cache.hdel_calls), 2)


def test_idempotent_2_lan():
    reset()
    first = CACHE_BUST.after_migrate()
    second = CACHE_BUST.after_migrate()
    eq(first, 4, "lần 1: 2 hdel (doctype) + 2 delete_value (assets_json)")
    eq(second, 4, "lần 2 cũng 4 — ⛔ được ném / ⛔ được bỏ qua")
    eq(len(STUB._cache.hdel_calls), 4, "gọi hdel 2 key × 2 lần")
    eq(len(STUB._cache.delete_calls), 4, "assets_json xoá 2 biến thể × 2 lần")


def test_log_1_dong_co_so_key():
    reset()
    CACHE_BUST.after_migrate()
    eq(STUB.logger_calls, ["alumglass"], "logger phải mang tên app alumglass")
    eq(len(STUB._logger.infos), 1, "đúng 1 dòng log mỗi lần chạy")
    msg, args, _kwargs = STUB._logger.infos[0]
    assert_("cache_bust" in msg and 4 in args,
            "log phải nêu số key đã xoá: %r %r" % (msg, args))


def test_danh_sach_doctype_dung_khai_bao():
    eq(tuple(CACHE_BUST.CACHE_BUST_DOCTYPES), ("Quotation", "Sales Order"),
       "khai báo phải khớp doctype_js trong hooks.py")


def print_summary():
    total = _passed + len(_failed)
    print("\n" + "=" * 60)
    print("  TOTAL: %s  PASS: %s  FAIL: %s" % (total, _passed, len(_failed)))
    if _failed:
        print("  FAILED: %r" % _failed)
        return 1
    print("  ALL TESTS PASSED")
    return 0


check("(1) xoá đúng 2 key form meta (Quotation + Sales Order)", test_xoa_dung_2_key_doctype)
check("(2) xoá assets_json (cả khoá shared lẫn khoá thường)", test_xoa_assets_json_shared)
check("(3) cache trống ⇒ không ném", test_cache_trong_khong_nem)
check("(4) gọi 2 lần liên tiếp ⇒ idempotent", test_idempotent_2_lan)
check("(5) ghi 1 dòng log có số key đã xoá", test_log_1_dong_co_so_key)
check("(6) danh sách DocType khớp hooks.py", test_danh_sach_doctype_dung_khai_bao)

if __name__ == "__main__":
    sys.exit(print_summary())
