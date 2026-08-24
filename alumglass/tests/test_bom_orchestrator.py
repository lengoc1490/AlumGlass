# -*- coding: utf-8 -*-
"""
Integration Test: BomOrchestrator — CDMQ-2C & CDMQ-4C.

Xác nhận engine tính BOM cho kết quả ổn định sau mỗi lần thay đổi code.
Dùng seed data từ seed_demo_data.py.

CÁCH CHẠY
---------
    bench --site <your-site> run-tests --app alumglass \
        --module alumglass.tests.test_bom_orchestrator
"""
import json

import frappe
from frappe.model.naming import make_autoname
from frappe.tests.utils import FrappeTestCase


class TestBomOrchestratorCDMQ2C(FrappeTestCase):
    """Test CDMQ-2C: Cửa đi 2 cánh mở quay + ô kính."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bom_code = "BOM-CDMQ-2C"

    def _create_quotation_item(self, bom_code, item_code, item_name, bom_vars_dict):
        """Helper: tạo Quotation + Quotation Item và trả về qi_name."""
        from frappe.utils import now

        company = (frappe.defaults.get_global_default("company")
                   or frappe.get_all("Company", limit=1, pluck="name")[0])
        bv_name = frappe.db.get_value("AL BOM", bom_code, "current_version")
        self.assertTrue(bv_name, f"BOM '{bom_code}' chưa có current_version - chạy seed trước")

        qtn_name = make_autoname("SAL-QTN-.#####")
        frappe.db.sql("""INSERT INTO `tabQuotation`
            (name, party_name, quotation_to, transaction_date, company, docstatus)
            VALUES (%s, %s, %s, %s, %s, 0)""",
            (qtn_name, "Khach Hang Test", "Customer", now(), company))
        frappe.db.commit()

        qi_name = frappe.generate_hash(length=10)
        frappe.db.sql("""INSERT INTO `tabQuotation Item`
            (name, parent, parentfield, parenttype, item_code, item_name, qty,
             uom, stock_uom, al_bom, al_bom_version, al_bom_vars, idx)
            VALUES (%s, %s, 'items', 'Quotation', %s, %s, 1, 'Kg', 'Kg', %s, %s, %s, 1)""",
            (qi_name, qtn_name, item_code, item_name, bom_code, bv_name,
             json.dumps(bom_vars_dict)))
        frappe.db.commit()
        return qi_name

    def test_cdmq_2c_gia_vat_matches_expected(self):
        """CDMQ-2C: GIA_VAT ≈ 22,717,289 VND (dung sai <1,000 VND)."""
        from alumglass.api import calculate_bom

        qi_name = self._create_quotation_item("BOM-CDMQ-2C", "CDMQ-2C",
            "Cửa đi 2 cánh mở quay", {
                "W_mm": 2400, "H_mm": 2600, "n_panel": 2,
                "TransomHeight_mm": 600, "aluminum_color": "WHITE",
                "aluminum_origin": "IMPORT", "aluminum_thickness": 20,
                "aluminum_surface": "POWDER_COATED",
            })

        result = calculate_bom(qi_name)
        ct = result.get("cost_template", {})
        gia_vat = ct.get("GIA_VAT", 0)
        expected = 22717289

        delta = abs(gia_vat - expected)
        self.assertLess(
            delta, 1000,
            f"GIA_VAT={gia_vat:,.0f} lệch {delta:,.0f} so với expected={expected:,.0f} VND"
        )


class TestBomOrchestratorCDMQ4C(FrappeTestCase):
    """Test CDMQ-4C: Cửa đi 4 cánh + 2 transom + sidelite — FULL FEATURES."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bom_code = "BOM-CDMQ-4C"

    def _create_quotation_item(self, bom_code, item_code, item_name, bom_vars_dict):
        """Helper: tạo Quotation + Quotation Item và trả về qi_name."""
        from frappe.utils import now

        company = (frappe.defaults.get_global_default("company")
                   or frappe.get_all("Company", limit=1, pluck="name")[0])
        bv_name = frappe.db.get_value("AL BOM", bom_code, "current_version")
        self.assertTrue(bv_name, f"BOM '{bom_code}' chưa có current_version - chạy seed trước")

        qtn_name = make_autoname("SAL-QTN-.#####")
        frappe.db.sql("""INSERT INTO `tabQuotation`
            (name, party_name, quotation_to, transaction_date, company, docstatus)
            VALUES (%s, %s, %s, %s, %s, 0)""",
            (qtn_name, "Khach Hang Test", "Customer", now(), company))
        frappe.db.commit()

        qi_name = frappe.generate_hash(length=10)
        frappe.db.sql("""INSERT INTO `tabQuotation Item`
            (name, parent, parentfield, parenttype, item_code, item_name, qty,
             uom, stock_uom, al_bom, al_bom_version, al_bom_vars, idx)
            VALUES (%s, %s, 'items', 'Quotation', %s, %s, 1, 'Kg', 'Kg', %s, %s, %s, 1)""",
            (qi_name, qtn_name, item_code, item_name, bom_code, bv_name,
             json.dumps(bom_vars_dict)))
        frappe.db.commit()
        return qi_name

    def test_cdmq_4c_runs_and_returns_lines(self):
        """CDMQ-4C: Engine chạy thành công và trả về > 0 dòng BOM."""
        from alumglass.api import calculate_bom

        qi_name = self._create_quotation_item("BOM-CDMQ-4C", "CDMQ-4C",
            "Cửa đi 4 cánh mở quay + vách kính", {
                "W_mm": 3600, "H_mm": 3200, "n_panel": 4,
                "TransomHeightTop": 600, "TransomHeightBottom": 400,
                "SideLiteWidth": 800, "SideLiteHeight": 2800,
                "aluminum_color": "DARK", "aluminum_origin": "IMPORT",
                "aluminum_thickness": 20, "aluminum_surface": "POWDER_COATED",
                "installation_height_m": 15,
            })

        result = calculate_bom(qi_name)
        ct = result.get("cost_template", {})
        lines = result.get("lines", [])
        buckets = result.get("buckets", {})

        # Verify engine chạy thành công
        self.assertGreater(len(lines), 0, "CDMQ-4C phải trả về > 0 dòng BOM")
        self.assertGreater(ct.get("GIA_VAT", 0), 0, "GIA_VAT phải > 0")
        self.assertGreater(ct.get("GIA_BAN", 0), 0, "GIA_BAN phải > 0")
        self.assertGreater(ct.get("GIA_THANH", 0), 0, "GIA_THANH phải > 0")
        self.assertGreater(ct.get("TONG_VL", 0), 0, "TONG_VL phải > 0")

        # Verify cost buckets
        self.assertGreater(buckets.get("VL_NHOM", 0), 0, "VL_NHOM phải > 0")
        self.assertGreater(buckets.get("VL_KINH", 0), 0, "VL_KINH phải > 0")

    def test_cdmq_4c_has_dynamic_item_rules(self):
        """CDMQ-4C: Phải resolve được nẹp items qua Dynamic Item Rule."""
        from alumglass.api import calculate_bom

        qi_name = self._create_quotation_item("BOM-CDMQ-4C", "CDMQ-4C",
            "Cửa đi 4 cánh mở quay + vách kính", {
                "W_mm": 3600, "H_mm": 3200, "n_panel": 4,
                "TransomHeightTop": 600, "TransomHeightBottom": 400,
                "SideLiteWidth": 800, "SideLiteHeight": 2800,
                "aluminum_color": "DARK", "aluminum_origin": "IMPORT",
                "aluminum_thickness": 20, "aluminum_surface": "POWDER_COATED",
                "installation_height_m": 15,
            })

        result = calculate_bom(qi_name)
        lines = result.get("lines", [])

        # Tìm dòng nẹp (resolved qua Dynamic Item Rule)
        nep_items = [l for l in lines if "nep" in l.get("slug", "")]
        self.assertGreater(len(nep_items), 0,
            "Phải có ít nhất 1 dòng nẹp resolved qua Dynamic Item Rule")

        # Tìm dòng keo (resolved qua LOOKUP)
        keo_items = [l for l in lines if "keo" in l.get("slug", "")]
        self.assertGreater(len(keo_items), 0,
            "Phải có ít nhất 1 dòng keo resolved qua Dynamic Item Rule")
