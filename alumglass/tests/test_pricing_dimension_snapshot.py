# -*- coding: utf-8 -*-
"""
Test: P1 — Pricing Dimension Versioning (snapshot đóng băng).

MỤC ĐÍCH
--------
AL BOM Version nay chụp thêm `pricing_dimension_snapshot` (toàn bộ
AL Pricing Dimension + AL Variable Dimension Mapping) tại thời điểm tạo/
publish — để báo giá tái lập được kể cả khi config Pricing Dimension bị
đổi sau đó. File này verify 3 hành vi:

  1. Snapshot được chụp tự động khi tạo version mới (before_insert).
  2. Snapshot bất biến: sau Published, sửa field này → frappe.throw.
  3. BomOrchestrator._get_dim_fieldnames() ưu tiên đọc từ snapshot
     (không query config live).

CÁCH CHẠY
---------
    bench --site alumglass-dev run-tests --app alumglass \
        --module alumglass.tests.test_pricing_dimension_snapshot

Yêu cầu seed data (BOM-CDMQ-2C, AL Pricing Dimension, AL Variable Dimension
Mapping) — chạy seed_demo_data.seed_all() trước nếu chưa có.

LƯU Ý self-contained: mỗi test tự TẠO version mới (không phụ thuộc version
seed cũ có snapshot hay chưa — seed cũ tạo trước patch P1 có thể rỗng).
FrappeTestCase rollback transaction sau mỗi test → không rò rỉ current_version.
"""
import json

import frappe
from frappe.tests.utils import FrappeTestCase

BOM_CODE = "BOM-CDMQ-2C"


class TestPricingDimensionSnapshot(FrappeTestCase):
    """P1 — Snapshot + guard + orchestrator đọc snapshot."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("AL BOM", BOM_CODE):
            frappe.throw(
                f"Thiếu AL BOM '{BOM_CODE}'. Chạy seed_demo_data.seed_all() trước."
            )

    # ── 1. Snapshot chụp tự động khi insert ────────────────────────
    def test_snapshot_captured_on_insert(self):
        doc = self._make_version("Draft")
        self.assertTrue(
            doc.pricing_dimension_snapshot,
            "before_insert phải tự chụp pricing_dimension_snapshot.",
        )
        data = json.loads(doc.pricing_dimension_snapshot)
        self.assertIn("dimensions", data)
        self.assertIn("mappings", data)

        dim_codes = {d["dimension_code"] for d in data["dimensions"]}
        self.assertIn("MAU_SAC", dim_codes, "Snapshot phải chứa AL Pricing Dimension MAU_SAC.")

        mapping_names = {m["variable_name"] for m in data["mappings"]}
        self.assertIn(
            "aluminum_color", mapping_names,
            "Snapshot phải chứa mapping aluminum_color → MAU_SAC.",
        )

    # ── 2. Guard: Published rồi thì không sửa snapshot ─────────────
    def test_guard_blocks_modification_after_publish(self):
        doc = self._make_version("Published")
        original = doc.pricing_dimension_snapshot
        self.assertTrue(original, "Version Published mới phải có snapshot.")

        doc.pricing_dimension_snapshot = "{\"tampered\": true}"
        with self.assertRaises(frappe.ValidationError):
            doc.save()

        # save đã throw → không có gì bị ghi đè
        current = frappe.db.get_value(
            "AL BOM Version", doc.name, "pricing_dimension_snapshot"
        )
        self.assertEqual(current, original, "Guard phải chặn mọi ghi đè snapshot.")

    # ── 3. Orchestrator đọc từ snapshot (không query live) ─────────
    def test_orchestrator_reads_from_snapshot(self):
        from unittest.mock import patch

        from alumglass.engine.bom_orchestrator import BomOrchestrator

        version = self._make_version("Published")
        orch = BomOrchestrator("TEST-QI-UNUSED")
        orch.bom_version = frappe.get_cached_doc("AL BOM Version", version.name)

        # Chặn query live — nếu _get_dim_fieldnames chạy đúng snapshot thì
        # get_all không bao giờ bị gọi.
        with patch("frappe.get_all", side_effect=AssertionError(
            "_get_dim_fieldnames KHÔNG được query config live khi có snapshot."
        )):
            mapping = orch._get_dim_fieldnames()

        self.assertIsInstance(mapping, dict)
        self.assertEqual(mapping.get("aluminum_color"), "custom_pd_mau_sac")
        self.assertEqual(mapping.get("aluminum_origin"), "custom_pd_xuat_xu")

    # ── Helpers ────────────────────────────────────────────────────
    def _make_version(self, workflow_state):
        """Tạo version mới cho BOM-CDMQ-2C.

        Version Published làm on_update set current_version = version mới —
        FrappeTestCase rollback transaction sau test nên không rò rỉ, nhưng
        khôi phục phòng hờ (hygiene + chống race giữa các test cùng class).
        """
        original_cv = frappe.db.get_value("AL BOM", BOM_CODE, "current_version")

        doc = frappe.get_doc({
            "doctype": "AL BOM Version",
            "bom": BOM_CODE,
            "version_name": "p1-test-%s" % frappe.generate_hash(length=6),
            "valid_from": frappe.utils.now_datetime(),
            "workflow_state": workflow_state,
        })
        doc.insert(ignore_permissions=True)

        if original_cv:
            frappe.db.set_value(
                "AL BOM", BOM_CODE, "current_version", original_cv,
                update_modified=False,
            )
        self.addCleanup(
            lambda: frappe.delete_doc("AL BOM Version", doc.name, force=True)
        )
        return doc
