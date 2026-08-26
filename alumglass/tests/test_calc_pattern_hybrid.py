# -*- coding: utf-8 -*-
"""Test lookup_calc_pattern HYBRID (DB-first + PATTERN_FORMULAS fallback) — v28.8.

Phạm vi (6 case — spec hướng A, job calc-pattern-hybrid-fallback):
  1. Pattern có DB record (LENGTH_TO_WEIGHT) → chạy qua DB (positive cache).
  2. Pattern không có DB record nhưng có builtin (AREA_M2, ...) → fallback PATTERN_FORMULAS.
  3. Pattern không DB + không builtin → ValueError liệt kê patterns available.
  4. calc_fn rỗng trên record → fallback builtin, không throw.
  5. _validate_calc_fn chặn __import__/getattr/open/lambda lồng; cho phép lambda chuẩn.
  6. Role: AL BOM Manager KHÔNG đổi được calc_fn; AL Technical Admin đổi được.

CHẠY:
    bench --site alumglass-dev run-tests --app alumglass --module alumglass.tests.test_calc_pattern_hybrid
    # hoặc qua pytest (site context):
    python -m pytest alumglass/tests/test_calc_pattern_hybrid.py -v

Lưu ý: cần site dev đã seed (alumglass.setup.seed_demo_data._calc_methods) và role
AL Technical Admin (alumglass.setup.install_roles.install_roles_and_permissions).
"""
import unittest

import frappe

from alumglass.formula_handlers import (
    _DB_PATTERN_CACHE,
    _NEGATIVE_CACHE,
    _validate_calc_fn,
    clear_calc_fn_cache,
    lookup_calc_pattern,
)


def _reset_cache():
    """Clear cache để mỗi test bắt đầu trạng thái sạch."""
    clear_calc_fn_cache()


class TestCalcPatternHybrid(unittest.TestCase):
    """HYBRID lookup_calc_pattern — 6 case bắt buộc (spec Phase 6)."""

    # ─────────────────────────────────────────────────────────
    # 1. DB path
    # ─────────────────────────────────────────────────────────
    def test_db_record_used_when_present(self):
        """Pattern có DB record (LENGTH_TO_WEIGHT đã seed) → chạy qua DB compile."""
        _reset_cache()
        val = lookup_calc_pattern("LENGTH_TO_WEIGHT", width=2000, height=0, weight_per_unit=1.5)
        self.assertAlmostEqual(val, 3.0, places=9)
        # Đã điền positive cache → chứng minh đi qua DB (không fallback).
        self.assertIn("LENGTH_TO_WEIGHT", _DB_PATTERN_CACHE)
        self.assertNotIn("LENGTH_TO_WEIGHT", _NEGATIVE_CACHE)
        _reset_cache()

    # ─────────────────────────────────────────────────────────
    # 2. Builtin fallback
    # ─────────────────────────────────────────────────────────
    def test_builtin_fallback_for_missing_db_record(self):
        """Pattern built-in cho giá trị đúng (DB hoặc fallback).

        Phase 1a: 12 pattern chuẩn (v28.md §C.4) + alias AREA/LENGTH_ONLY đã seed
        đủ DB → AREA_M2 (và mọi builtin khác) đi qua DB (positive cache). Fallback
        builtin vẫn được cover bởi test_empty_calc_fn_falls_back_to_builtin (#4)."""
        _reset_cache()
        # Giá trị theo PATTERN_FORMULAS spec — dù đi DB (đã seed) hay fallback đều khớp.
        cases = [
            ("LENGTH_M", {"width": 2500, "height": 0, "weight_per_unit": 0}, 2.5),
            ("AREA_M2", {"width": 2000, "height": 1000, "weight_per_unit": 0}, 2.0),
            ("PERIMETER_M", {"width": 2000, "height": 1000, "weight_per_unit": 0}, 6.0),
            ("VOLUME_M3", {"width": 2000, "height": 1000, "weight_per_unit": 0, "depth": 10}, 0.02),
            ("SET", {"width": 0, "height": 0, "weight_per_unit": 0}, 1),
        ]
        for code, kw, expected in cases:
            val = lookup_calc_pattern(code, **kw)
            self.assertAlmostEqual(val, expected, places=9, msg=f"{code}: {val} != {expected}")
        # Phase 1a: AREA_M2 đã seed DB record → đi qua positive cache (không phải negative).
        self.assertIn("AREA_M2", _DB_PATTERN_CACHE, "pattern đã seed DB phải vào positive cache")
        self.assertNotIn("AREA_M2", _NEGATIVE_CACHE)
        _reset_cache()

    # ─────────────────────────────────────────────────────────
    # 3. Unknown pattern → ValueError
    # ─────────────────────────────────────────────────────────
    def test_unknown_pattern_raises_value_error(self):
        """Pattern không DB + không builtin → ValueError liệt kê patterns available."""
        _reset_cache()
        with self.assertRaises(ValueError) as ctx:
            lookup_calc_pattern("UNKNOWN_PATTERN_XYZ", width=1000, height=0, weight_per_unit=0)
        msg = str(ctx.exception)
        self.assertIn("UNKNOWN_PATTERN_XYZ", msg)
        self.assertIn("LENGTH_TO_WEIGHT", msg)   # liệt kê built-in có sẵn
        self.assertIn("AREA_M2", msg)
        _reset_cache()

    # ─────────────────────────────────────────────────────────
    # 4. calc_fn empty → fallback
    # ─────────────────────────────────────────────────────────
    def test_empty_calc_fn_falls_back_to_builtin(self):
        """calc_fn rỗng trên record → fallback PATTERN_FORMULAS, không throw."""
        _reset_cache()
        orig = frappe.db.get_value("AL Quantity Calc Method", "LENGTH_TO_WEIGHT", "calc_fn")
        self.assertTrue(orig, "LENGTH_TO_WEIGHT phải có calc_fn (đã seed)")
        frappe.db.set_value("AL Quantity Calc Method", "LENGTH_TO_WEIGHT", "calc_fn", "")
        try:
            _reset_cache()
            val = lookup_calc_pattern("LENGTH_TO_WEIGHT", width=2000, height=0, weight_per_unit=1.5)
            self.assertAlmostEqual(val, 3.0, places=9)  # builtin: (w/1000)*tlr
            self.assertIn("LENGTH_TO_WEIGHT", _NEGATIVE_CACHE)
        finally:
            frappe.db.set_value("AL Quantity Calc Method", "LENGTH_TO_WEIGHT", "calc_fn", orig)
            _reset_cache()

    # ─────────────────────────────────────────────────────────
    # 5. _validate_calc_fn — AST whitelist
    # ─────────────────────────────────────────────────────────
    def test_validate_calc_fn_rejects_rce_and_nested_lambda(self):
        """_validate_calc_fn chặn __import__/getattr/open/lambda lồng; cho phép lambda chuẩn."""
        # Hợp lệ — không throw
        _validate_calc_fn("lambda w,h,tlr,**kw: (w/1000)*tlr")
        _validate_calc_fn("lambda w,h,tlr,**kw: (w/1000)*kw.get('depth',0)/1000")
        # Rỗng → OK (fallback)
        _validate_calc_fn("")
        _validate_calc_fn(None)

        bad_cases = [
            "lambda w,h,tlr,**kw: __import__('os')",
            "lambda w,h,tlr,**kw: getattr(x, '__class__')",
            "lambda w,h,tlr,**kw: open('/etc/passwd')",
            "lambda w,h,tlr,**kw: lambda: 1",
        ]
        for bad in bad_cases:
            with self.subTest(bad=bad):
                with self.assertRaises(Exception, msg=f"_validate_calc_fn không chặn: {bad}"):
                    _validate_calc_fn(bad)

    # ─────────────────────────────────────────────────────────
    # 6. Role guard (validate hook)
    # ─────────────────────────────────────────────────────────
    def test_role_guard_calc_fn_change(self):
        """AL BOM Manager không đổi được calc_fn; AL Technical Admin đổi được."""
        # Đảm bảo role tồn tại (idempotent)
        if not frappe.db.exists("Role", "AL Technical Admin"):
            frappe.get_doc({"doctype": "Role", "role_name": "AL Technical Admin",
                            "desk_access": 1}).insert(ignore_permissions=True)

        bom_email = "al_bom_mgr_test@example.com"
        tech_email = "al_tech_admin_test@example.com"
        orig = frappe.db.get_value("AL Quantity Calc Method", "LENGTH_TO_WEIGHT", "calc_fn")

        self._ensure_test_user(bom_email, "BOM Mgr Test", ["AL BOM Manager"])
        self._ensure_test_user(tech_email, "Tech Admin Test", ["AL Technical Admin"])
        frappe.db.commit()
        try:
            # BOM Manager — bị chặn
            frappe.set_user(bom_email)
            doc = frappe.get_doc("AL Quantity Calc Method", "LENGTH_TO_WEIGHT")
            doc.calc_fn = "lambda w,h,tlr,**kw: (w/1000)*tlr + 999"
            with self.assertRaises(frappe.ValidationError):
                doc.save(ignore_permissions=True)

            # AL Technical Admin — đổi được
            frappe.set_user(tech_email)
            doc = frappe.get_doc("AL Quantity Calc Method", "LENGTH_TO_WEIGHT")
            doc.calc_fn = "lambda w,h,tlr,**kw: (w/1000)*tlr + 1"
            doc.save(ignore_permissions=True)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("AL Quantity Calc Method", "LENGTH_TO_WEIGHT", "calc_fn", orig)
            self._cleanup_test_users([bom_email, tech_email])
            frappe.db.commit()
            _reset_cache()

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _ensure_test_user(email, first_name, role_names):
        """Tạo hoặc reset user test với đúng role."""
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)
            user.roles = []
            for r in role_names:
                user.append("roles", {"role": r})
            user.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "send_welcome_email": 0,
                "roles": [{"role": r} for r in role_names],
            }).insert(ignore_permissions=True)

    @staticmethod
    def _cleanup_test_users(emails):
        for email in emails:
            if frappe.db.exists("User", email):
                frappe.db.sql("DELETE FROM `tabHas Role` WHERE parent=%s", email)
                frappe.delete_doc("User", email, force=True)


if __name__ == "__main__":
    unittest.main()
