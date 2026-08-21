# -*- coding: utf-8 -*-
"""
Test: P2 — Async BOM Calculation (BOM lớn > ASYNC_BOM_THRESHOLD).

MỤC ĐÍCH
--------
`alumglass.api.calculate_bom` với BOM ≤ ngưỡng phải GIỮ NGUYÊN hành vi sync
(trả về {buckets, cost_template, lines}); BOM > ngưỡng → enqueue queue long +
trả {async: True, job_id}. Worker `_run_bom_calculation_job` set status
Queued→Running→Success (hoặc Failed) + publish_realtime cho user.

File này verify 4 hành vi:
  1. `_get_async_threshold()` đọc Formula Global Variable, fallback 150.
  2. `_estimate_bom_line_count()` đếm từ bom_set_snapshot của version pin.
  3. `_enqueue_bom_calculation()` trả {async: True, job_id} + enqueue queue long.
  4. `_run_bom_calculation_job()` set Success + publish_realtime (worker path).

CÁCH CHẠY
---------
    bench --site alumglass-dev run-tests --app alumglass \
        --module alumglass.tests.test_async_bom_calculation

Yêu cầu seed data BOM-CDMQ-2C (có bom_set_snapshot).
"""
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

BOM_CODE = "BOM-CDMQ-2C"


class TestAsyncBomCalculation(FrappeTestCase):
    """P2 — Threshold / line count / enqueue / worker job."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bv_name = frappe.db.get_value("AL BOM", BOM_CODE, "current_version")
        if not cls.bv_name:
            frappe.throw(
                f"BOM '{BOM_CODE}' chưa có current_version. Chạy seed trước."
            )

    # ── 1. Threshold ───────────────────────────────────────────────
    def test_threshold_reads_global_var(self):
        from alumglass.api import _get_async_threshold

        original = frappe.db.get_value(
            "Formula Global Variable", "ASYNC_BOM_THRESHOLD", "constant_value"
        )
        try:
            frappe.db.set_value(
                "Formula Global Variable", "ASYNC_BOM_THRESHOLD",
                "constant_value", "42", update_modified=False,
            )
            self.assertEqual(_get_async_threshold(), 42)
        finally:
            if original is not None:
                frappe.db.set_value(
                    "Formula Global Variable", "ASYNC_BOM_THRESHOLD",
                    "constant_value", original, update_modified=False,
                )

    def test_threshold_fallback_150(self):
        from alumglass.api import _get_async_threshold

        with patch("frappe.db.get_value", return_value=None):
            self.assertEqual(_get_async_threshold(), 150)
        with patch("frappe.db.get_value", return_value="abc"):
            self.assertEqual(_get_async_threshold(), 150)

    # ── 2. Line count từ bom_set_snapshot ──────────────────────────
    def test_estimate_line_count_from_snapshot(self):
        from alumglass.api import _estimate_bom_line_count

        qi = Mock()
        qi.get = Mock(side_effect=lambda k: {
            "al_bom_version": self.bv_name,
            "al_bom": BOM_CODE,
        }.get(k))

        count = _estimate_bom_line_count(qi)
        self.assertGreaterEqual(count, 1, "CDMQ-2C phải có ≥1 dòng BOM.")

    def test_estimate_line_count_zero_without_version(self):
        from alumglass.api import _estimate_bom_line_count

        qi = Mock()
        qi.get = Mock(return_value=None)
        self.assertEqual(_estimate_bom_line_count(qi), 0)

    # ── 3. Enqueue ─────────────────────────────────────────────────
    def test_enqueue_returns_async_and_job(self):
        from alumglass.api import _enqueue_bom_calculation

        qi = Mock()
        qi.name = "TEST-QI-ASYNC-ENQ"

        with patch("frappe.enqueue") as mock_enqueue:
            resp = _enqueue_bom_calculation(qi)

        self.assertTrue(resp["async"])
        self.assertTrue(resp["job_id"].startswith("albom-"))
        self.assertEqual(resp["status"], "Queued")

        mock_enqueue.assert_called_once()
        kwargs = mock_enqueue.call_args.kwargs
        self.assertEqual(kwargs["method"], "alumglass.api._run_bom_calculation_job")
        self.assertEqual(kwargs["queue"], "long")
        self.assertEqual(kwargs["timeout"], 600)
        self.assertEqual(kwargs["qi_name"], "TEST-QI-ASYNC-ENQ")
        self.assertEqual(kwargs["job_id"], resp["job_id"])

    # ── 4. Worker job ──────────────────────────────────────────────
    def test_run_job_success_sets_status_and_publishes(self):
        from alumglass.api import _run_bom_calculation_job

        fake_result = {
            "buckets": {"VL_NHOM": 100.0},
            "cost_template": {"GIA_VAT": 150.0},
            "lines": [{"slug": "khung_ngang_tren", "line_total": 100.0}],
        }

        with patch(
            "alumglass.engine.bom_orchestrator.BomOrchestrator.run",
            return_value=fake_result,
        ), patch("frappe.db.set_value") as mock_set, patch(
            "frappe.publish_realtime"
        ) as mock_pub:
            _run_bom_calculation_job(
                "TEST-QI-ASYNC-WORKER", "albom-test-job", "test@example.com"
            )

        # Worker phải set al_calc_status = Success (str fieldname)
        status_calls = [
            c for c in mock_set.call_args_list
            if c.args[0] == "Quotation Item"
            and c.args[2] == "al_calc_status"
        ]
        self.assertTrue(
            any(c.args[3] == "Running" for c in status_calls),
            "Worker phải set status Running trước khi chạy engine.",
        )
        self.assertTrue(
            any(c.args[3] == "Success" for c in status_calls),
            "Worker phải set status Success sau khi chạy xong.",
        )

        # publish_realtime với status Success + result chuẩn hoá 3 key
        mock_pub.assert_called_once()
        kwargs = mock_pub.call_args.kwargs
        self.assertEqual(kwargs["event"], "alumglass_bom_calc_done")
        self.assertEqual(kwargs["user"], "test@example.com")
        msg = kwargs["message"]
        self.assertEqual(msg["job_id"], "albom-test-job")
        self.assertEqual(msg["status"], "Success")
        self.assertIn("buckets", msg["result"])
        self.assertIn("cost_template", msg["result"])
        self.assertIn("lines", msg["result"])

    def test_run_job_failure_marks_failed_and_publishes(self):
        from alumglass.api import _run_bom_calculation_job

        with patch(
            "alumglass.engine.bom_orchestrator.BomOrchestrator.run",
            side_effect=RuntimeError("boom"),
        ), patch("frappe.db.set_value") as mock_set, patch(
            "frappe.publish_realtime"
        ) as mock_pub, patch("frappe.log_error") as mock_log:
            _run_bom_calculation_job(
                "TEST-QI-ASYNC-FAIL", "albom-test-fail", "test@example.com"
            )

        # Worker set Failed + al_calc_error (dict dạng {field: value})
        fail_calls = [
            c for c in mock_set.call_args_list
            if c.args[0] == "Quotation Item"
            and isinstance(c.args[2], dict)
            and c.args[2].get("al_calc_status") == "Failed"
        ]
        self.assertTrue(fail_calls, "Worker phải set status Failed khi lỗi.")
        self.assertTrue(
            fail_calls and fail_calls[-1].args[2].get("al_calc_error"),
            "Worker phải lưu al_calc_error khi lỗi.",
        )

        mock_log.assert_called_once()
        kwargs = mock_pub.call_args.kwargs
        msg = kwargs["message"]
        self.assertEqual(msg["status"], "Failed")
        self.assertIn("error", msg)

    # ── 5. calculate_bom routing ───────────────────────────────────
    def test_calculate_bom_sync_below_threshold(self):
        """BOM ≤ ngưỡng → chạy sync, KHÔNG enqueue. Response có đủ 3 key."""
        from alumglass.api import calculate_bom

        qi = Mock()
        qi.name = "TEST-QI-SYNC"
        qi.get = Mock(side_effect=lambda k: {
            "al_bom_version": self.bv_name,
            "al_bom": BOM_CODE,
        }.get(k))

        fake_result = {
            "buckets": {"VL_NHOM": 100.0},
            "cost_template": {"GIA_VAT": 150.0},
            "lines": [],
        }
        with patch("alumglass.api._estimate_bom_line_count", return_value=10), \
             patch("alumglass.api._get_async_threshold", return_value=150), \
             patch("frappe.get_doc", return_value=qi), \
             patch("alumglass.engine.bom_orchestrator.BomOrchestrator.run",
                   return_value=fake_result), \
             patch("frappe.enqueue") as mock_enqueue:
            resp = calculate_bom("TEST-QI-SYNC")

        self.assertIn("buckets", resp)
        self.assertIn("cost_template", resp)
        self.assertIn("lines", resp)
        self.assertFalse(resp.get("async"))
        mock_enqueue.assert_not_called()

    def test_calculate_bom_async_above_threshold(self):
        """BOM > ngưỡng → enqueue + trả {async: True, job_id}."""
        from alumglass.api import calculate_bom

        qi = Mock()
        qi.name = "TEST-QI-ASYNC"
        qi.get = Mock(side_effect=lambda k: {
            "al_bom_version": self.bv_name,
            "al_bom": BOM_CODE,
        }.get(k))

        with patch("alumglass.api._estimate_bom_line_count", return_value=500), \
             patch("alumglass.api._get_async_threshold", return_value=150), \
             patch("frappe.get_doc", return_value=qi), \
             patch("frappe.enqueue") as mock_enqueue:
            resp = calculate_bom("TEST-QI-ASYNC")

        self.assertTrue(resp["async"])
        self.assertTrue(resp["job_id"])
        self.assertEqual(resp["status"], "Queued")
        mock_enqueue.assert_called_once()
