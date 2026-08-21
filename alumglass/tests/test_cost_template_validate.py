# -*- coding: utf-8 -*-
"""
Unit Test: AL Cost Template validate() — FormulaValidator integration.

Kiểm tra validate() nhận diện đúng universe biến động:
- CT-01-STANDARD (14 dòng seed) → 0 false positive.
- String literal 'RULE-HEIGHT-MULT' không bị tách nhầm RULE/HEIGHT/MULT.
- Biến lowercase chưa khai báo (typo), hàm lạ, biến không tồn tại → cảnh báo.
- Giữ nguyên 2 hard-throw hiện có: công thức trống + dấu ngoặc không cân bằng.

CÁCH CHẠY
---------
    bench --site alumglass-dev run-tests --app alumglass \
        --module alumglass.tests.test_cost_template_validate
"""
import unittest.mock as mock

import frappe
from frappe.tests.utils import FrappeTestCase


def _make_doc(items):
    """Tạo doc AL Cost Template in-memory (không insert DB) để gọi validate()."""
    return frappe.get_doc({
        "doctype": "AL Cost Template",
        "template_code": "TEST-VALIDATE",
        "template_name": "Test Validate",
        "items": [
            {"doctype": "AL Cost Template Item", **row}
            for row in items
        ],
    })


class TestALCostTemplateValidate(FrappeTestCase):
    """validate() dùng universe biến động + FormulaValidator (AST)."""

    def _run_validate(self, items):
        """Gọi validate() với items và trả về list message msgprint đã gọi (nếu có)."""
        doc = _make_doc(items)
        with mock.patch("frappe.msgprint") as mocked:
            doc.validate()
        return [c.args[0] if c.args else "" for c in mocked.call_args_list]

    def test_ct_standard_seed_zero_warnings(self):
        """CT-01-STANDARD (14 dòng thật trong DB) → 0 warning/error sai."""
        doc = frappe.get_doc("AL Cost Template", "CT-01-STANDARD")
        self.assertEqual(len(doc.items), 14)
        with mock.patch("frappe.msgprint") as mocked:
            doc.validate()
        self.assertEqual(
            mocked.call_count, 0,
            f"False positive: {mocked.call_args_list}",
        )

    def test_string_literal_not_split(self):
        """'RULE-HEIGHT-MULT' là string literal — không tách RULE/HEIGHT/MULT."""
        calls = self._run_validate([
            {"line_code": "X", "calc_formula":
             "lookup_rule('RULE-HEIGHT-MULT', installation_height_m)", "is_subtotal": 0},
        ])
        self.assertEqual(calls, [])

    def test_previous_row_custom_code_known(self):
        """Line_code custom ở dòng trước → dòng sau dùng được (không false positive)."""
        calls = self._run_validate([
            {"line_code": "PHU_THU", "calc_formula": "100 + W_mm", "is_subtotal": 0},
            {"line_code": "X", "calc_formula": "PHU_THU * 2", "is_subtotal": 0},
        ])
        self.assertEqual(calls, [])

    def test_typo_lowercase_warns(self):
        """Biến lowercase chưa khai báo (typo installation_heigt_m) → cảnh báo."""
        calls = self._run_validate([
            {"line_code": "X", "calc_formula": "installation_heigt_m * 2", "is_subtotal": 0},
        ])
        joined = "\n".join(calls)
        self.assertIn("installation_heigt_m", joined)

    def test_unknown_function_warns(self):
        """Hàm lạ (lookup_ruleX) → cảnh báo hàm không hỗ trợ."""
        calls = self._run_validate([
            {"line_code": "X", "calc_formula":
             "lookup_ruleX('RULE-HEIGHT-MULT', W_mm)", "is_subtotal": 0},
        ])
        joined = "\n".join(calls)
        self.assertIn("lookup_ruleX", joined)

    def test_unknown_var_warns(self):
        """Biến thật sự không tồn tại (TONG_XYZ) → cảnh báo."""
        calls = self._run_validate([
            {"line_code": "X", "calc_formula": "TONG_XYZ + W_mm", "is_subtotal": 0},
        ])
        joined = "\n".join(calls)
        self.assertIn("TONG_XYZ", joined)

    def test_empty_formula_throws(self):
        """Công thức trống → vẫn chặn save (frappe.throw)."""
        doc = _make_doc([
            {"line_code": "X", "calc_formula": "", "is_subtotal": 0},
        ])
        with self.assertRaises(frappe.ValidationError):
            doc.validate()

    def test_unbalanced_parens_throws(self):
        """Dấu ngoặc không cân bằng → vẫn chặn save (frappe.throw)."""
        doc = _make_doc([
            {"line_code": "X", "calc_formula": "(W_mm + H_mm", "is_subtotal": 0},
        ])
        with self.assertRaises(frappe.ValidationError):
            doc.validate()
