"""Phase 4 golden test — B0 auto-create AL BOM Version Published khi BOM rule-live.

Kiểm chứng:
1. BOM không có current_version → engine auto-create AL BOM Version Published
   (snapshot BOM Set + Cost Template + Pricing Dimension)
2. current_version được set trên AL BOM
3. al_bom_version được pin vào Quotation Item
4. Kết quả GIA_VAT khớp BOM gốc (cùng Bom Set) ≈ 22,717,289 (dung sai <1000)
5. Backward-compat: BOM đã có version Published → giữ nguyên, không tạo lại
"""
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now

BOM_CODE = "BOM-P4-LIVE-TEST"
QTN_NAME = "SAL-QTN-P4LIVE"
QI_NAME = "QI-P4LIVE-001"


class TestBomVersionAutoCreate(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = (frappe.defaults.get_global_default("company")
                       or frappe.get_all("Company", limit=1, pluck="name")[0])

    def tearDown(self):
        frappe.db.rollback()
        frappe.db.commit()

    def _create_live_bom(self):
        frappe.delete_doc("AL BOM", BOM_CODE, force=True)
        bom = frappe.new_doc("AL BOM")
        bom.bom_code = BOM_CODE
        bom.bom_set = "BS-CDMQ-2C"
        bom.default_cost_template = "CT-01-STANDARD"
        bom.representative_item = "NHOM-XINGFA"
        bom.product_type = "DOOR"
        bom.brand = "XINGFA"
        bom.is_active = 1
        bom.flags.ignore_permissions = True
        bom.insert()
        frappe.db.commit()
        self.assertIsNone(
            frappe.db.get_value("AL BOM", BOM_CODE, "current_version"),
            "BOM test phải bắt đầu ở trạng thái rule-live (chưa có version)")
        return bom.name

    def _create_quotation_item(self, bom_name):
        frappe.db.sql("DELETE FROM `tabQuotation Item` WHERE parent=%s", QTN_NAME)
        frappe.db.sql("DELETE FROM `tabQuotation` WHERE name=%s", QTN_NAME)
        frappe.db.sql(
            """INSERT INTO `tabQuotation`
               (name, party_name, quotation_to, transaction_date, company, docstatus)
               VALUES (%s, %s, %s, %s, %s, 0)""",
            (QTN_NAME, "Khach Hang Test", "Customer", now(), self.company))
        frappe.db.sql(
            """INSERT INTO `tabQuotation Item`
               (name, parent, parentfield, parenttype, item_code, item_name, qty,
                uom, stock_uom, al_bom, al_bom_version, al_bom_vars, idx)
               VALUES (%s, %s, 'items', 'Quotation', 'CDMQ-2C', 'Cua 2 canh', 1,
                       'Kg', 'Kg', %s, '', %s, 1)""",
            (QI_NAME, QTN_NAME, bom_name,
             json.dumps({
                 "W_mm": 2400, "H_mm": 2600, "n_panel": 2,
                 "TransomHeight_mm": 600, "aluminum_color": "WHITE",
                 "aluminum_origin": "IMPORT", "aluminum_thickness": 20,
                 "aluminum_surface": "POWDER_COATED",
             })))
        frappe.db.commit()
        return QI_NAME

    def test_b0_auto_creates_published_version(self):
        """BOM rule-live → engine tự tạo version Published + set current_version + pin."""
        from alumglass.api import calculate_bom

        bom_name = self._create_live_bom()
        qi_name = self._create_quotation_item(bom_name)

        result = calculate_bom(qi_name)
        ct = result.get("cost_template", {})
        gia_vat = ct.get("GIA_VAT", 0)

        # 1) Version Published được auto-create
        ver_name = frappe.db.get_value("Quotation Item", qi_name, "al_bom_version")
        self.assertTrue(ver_name, "al_bom_version phải được pin sau auto-create")
        version = frappe.get_doc("AL BOM Version", ver_name)
        self.assertEqual(version.workflow_state, "Published")
        self.assertTrue(version.bom_set_snapshot, "Snapshot BOM Set phải có items")
        self.assertTrue(version.cost_template_snapshot,
                        "Snapshot Cost Template phải có nội dung")
        self.assertTrue(version.pricing_dimension_snapshot,
                        "Snapshot Pricing Dimension phải có nội dung")

        # 2) current_version trên AL BOM được set = version vừa tạo
        self.assertEqual(
            frappe.db.get_value("AL BOM", bom_name, "current_version"), ver_name)

        # 3) Kết quả khớp BOM gốc (cùng Bom Set → cùng GIA_VAT)
        delta = abs(gia_vat - 22717289)
        self.assertLess(
            delta, 1000,
            f"GIA_VAT={gia_vat:,.0f} lệch {delta:,.0f} so với expected 22,717,289")

        # 4) Chạy lại lần 2 → KHÔNG tạo version mới (version đã Published)
        version_count_before = frappe.db.count(
            "AL BOM Version", filters={"bom": bom_name})
        calculate_bom(qi_name)
        version_count_after = frappe.db.count(
            "AL BOM Version", filters={"bom": bom_name})
        self.assertEqual(version_count_before, version_count_after,
                         "BOM đã có version Published → không được tạo thêm version")

    def test_b0_backward_compat_existing_version_unchanged(self):
        """Backward-compat: BOM đã có version Published → giữ nguyên, không tạo lại."""
        bom_code = "BOM-CDMQ-2C"
        current_version = frappe.db.get_value("AL BOM", bom_code, "current_version")
        self.assertTrue(current_version, "Fixture BOM-CDMQ-2C phải có current_version")

        version_count_before = frappe.db.count(
            "AL BOM Version", filters={"bom": bom_code})
        qi_name = self._create_quotation_item(bom_code)
        frappe.db.set_value("Quotation Item", qi_name, "al_bom_version",
                            current_version)

        from alumglass.api import calculate_bom
        calculate_bom(qi_name)

        version_count_after = frappe.db.count(
            "AL BOM Version", filters={"bom": bom_code})
        self.assertEqual(version_count_before, version_count_after,
                         "Backward-compat: không tạo thêm version cho BOM đã có version")
