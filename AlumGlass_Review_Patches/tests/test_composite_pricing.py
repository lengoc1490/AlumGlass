# -*- coding: utf-8 -*-
"""
Test: Composite Key Pricing (mau sac/xuat xu/do day/be mat).

MUC DICH
--------
BomOrchestrator.b2_prefetch_master_data() hien tai chi loc Item Price theo
(item_code, price_list) - BO QUA cac custom field composite key duoc sinh tu
AL Pricing Dimension (vd custom_pd_MAU_SAC). He qua:
  1. Doi mau khong lam doi gia (aluminum_color=WHITE va DARK ra cung unit_price).
  2. Neu 1 item_code co nhieu dong Item Price, dict bi ghi de boi dong cuoi
     cung DB tra ve -> ket qua khong xac dinh (non-deterministic).

Test nay dung DUNG BOM mau co san trong seed_demo_data.py (BOM-CDMQ-2C) va
chi them 1 dong Item Price thu 2 (mau DARK, gia chenh manh) de bam vao dung
item_code da co san (NHOM-XINGFA). Neu patch chua duoc ap dung, test se FAIL
o assertNotEqual vi 2 gia ra giong nhau.

CACH CHAY
---------
    bench --site <your-site> run-tests --app alumglass \
        --module alumglass.tests.test_composite_pricing

(Hoac dat file nay vao alumglass/tests/ trong repo that su - Frappe tu
 discover moi file test_*.py trong thu muc tests/ cua tung app.)
"""
import json

import frappe
from frappe.model.naming import make_autoname
from frappe.tests.utils import FrappeTestCase

ITEM_CODE = "NHOM-XINGFA"          # item dai dien co san trong seed data
PRICE_LIST = "Standard Selling"
BOM_CODE = "BOM-CDMQ-2C"
DIMENSION_CODE = "MAU_SAC"         # AL Pricing Dimension da seed cho mau sac


class TestCompositePricing(FrappeTestCase):
    """Kiem chung: 2 mau khac nhau cua cung 1 item_code phai ra 2 gia khac nhau."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Lay dung ten field composite ma AL Pricing Dimension da tu sinh ra
        # tren Item Price (KHONG hardcode "custom_color" vi ten that phu thuoc
        # dimension_code, xem al_pricing_dimension.py: _sync_custom_field()).
        cls.color_fieldname = frappe.db.get_value(
            "AL Pricing Dimension", DIMENSION_CODE, "custom_fieldname")
        if not cls.color_fieldname:
            frappe.throw(
                f"Thieu du lieu seed: AL Pricing Dimension '{DIMENSION_CODE}'. "
                f"Hay chay seed_demo_data.seed_all() truoc khi test."
            )
        if not frappe.db.exists(
            "Custom Field", {"dt": "Item Price", "fieldname": cls.color_fieldname}
        ):
            frappe.throw(
                f"Custom Field '{cls.color_fieldname}' chua ton tai tren Item Price. "
                f"AL Pricing Dimension co the chua duoc sync dung cach."
            )

        cls._white_ip = cls._upsert_item_price("WHITE", 113000)
        cls._dark_ip = cls._upsert_item_price("DARK", 999000)  # chenh rat manh, de bat loi

    @classmethod
    def tearDownClass(cls):
        for name in (cls._white_ip, cls._dark_ip):
            if name and frappe.db.exists("Item Price", name):
                frappe.delete_doc("Item Price", name, force=True, ignore_permissions=True)
        super().tearDownClass()

    @classmethod
    def _upsert_item_price(cls, color, rate):
        filters = {
            "item_code": ITEM_CODE,
            "price_list": PRICE_LIST,
            cls.color_fieldname: color,
        }
        existing = frappe.db.exists("Item Price", filters)
        if existing:
            frappe.db.set_value("Item Price", existing, "price_list_rate", rate)
            frappe.db.commit()
            return existing
        doc = frappe.get_doc({
            "doctype": "Item Price",
            "item_code": ITEM_CODE,
            "price_list": PRICE_LIST,
            "price_list_rate": rate,
            cls.color_fieldname: color,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name

    # ------------------------------------------------------------------
    def _create_quotation_item(self, color):
        """Tao 1 Quotation + Quotation Item voi mau chi dinh (giong run_test.py)."""
        from frappe.utils import now

        company = (frappe.defaults.get_global_default("company")
                   or frappe.get_all("Company", limit=1, pluck="name")[0])
        bv_name = frappe.db.get_value("AL BOM", BOM_CODE, "current_version")
        self.assertTrue(bv_name, f"BOM '{BOM_CODE}' chua co current_version - chay seed truoc")

        qtn_name = make_autoname("SAL-QTN-.#####")
        frappe.db.sql("""INSERT INTO `tabQuotation`
            (name, party_name, quotation_to, transaction_date, company, docstatus,
             al_project_ref, al_profile_system)
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s)""",
            (qtn_name, "Test Composite Pricing", "Customer", now(), company,
             "TEST-COMPOSITE", "XINGFA_55"))

        bom_vars = {
            "W_mm": 2400, "H_mm": 2600, "n_panel": 2, "TransomHeight_mm": 600,
            "aluminum_color": color, "aluminum_origin": "IMPORT",
            "aluminum_thickness": 20, "aluminum_surface": "POWDER_COATED",
        }
        qi_name = frappe.generate_hash(length=10)
        frappe.db.sql("""INSERT INTO `tabQuotation Item`
            (name, parent, parentfield, parenttype, item_code, item_name, qty,
             uom, stock_uom, al_bom, al_bom_version, al_bom_vars, idx)
            VALUES (%s, %s, 'items', 'Quotation', %s, %s, 1, 'Kg', 'Kg', %s, %s, %s, 1)""",
            (qi_name, qtn_name, "CDMQ-2C", "Cua di 2 canh - test",
             BOM_CODE, bv_name, json.dumps(bom_vars)))
        frappe.db.commit()
        return qi_name

    def _calc_unit_price_for(self, color):
        """Chay BomOrchestrator that va tra ve unit_price cua dong item_code test."""
        from alumglass.engine.bom_orchestrator import BomOrchestrator

        qi_name = self._create_quotation_item(color)
        orch = BomOrchestrator(qi_name)
        result = orch.run()

        matches = [line for line in result.get("lines", [])
                   if line.get("item_code") == ITEM_CODE]
        self.assertTrue(
            matches,
            f"Khong tim thay dong BOM nao dung item_code='{ITEM_CODE}' trong ket qua - "
            f"kiem tra lai BOM_CODE/seed data."
        )
        return matches[0]["unit_price"]

    # ------------------------------------------------------------------
    def test_same_item_different_color_yields_different_price(self):
        """BUG DEMO: unit_price phai khac nhau giua WHITE (113,000) va DARK (999,000).

        Neu test nay FAIL voi 2 gia bang nhau -> b2_prefetch_master_data() dang
        bo qua composite key (custom_pd_MAU_SAC) khi tra Item Price.
        """
        price_white = self._calc_unit_price_for("WHITE")
        price_dark = self._calc_unit_price_for("DARK")

        self.assertNotEqual(
            price_white, price_dark,
            f"BUG XAC NHAN: unit_price giong nhau ({price_white}) du khac mau "
            f"(WHITE vs DARK). BomOrchestrator.b2_prefetch_master_data() dang "
            f"chi loc Item Price theo (item_code, price_list), bo qua field "
            f"composite '{self.color_fieldname}'. Xem fb_handlers.py:"
            f"aluminum_price_composite() - handler nay ton tai nhung khong "
            f"duoc goi trong luong tinh BOM that."
        )
        self.assertEqual(price_white, 113000)
        self.assertEqual(price_dark, 999000)

    def test_price_lookup_is_deterministic(self):
        """BUG DEMO: goi 5 lan lien tiep phai luon ra cung 1 gia cho cung 1 mau.

        Neu prices[item_code] bi ghi de boi thu tu tra ve khong dam bao tu DB
        (dict overwrite trong vong for), gia co the "nhay" giua cac lan chay.
        """
        results = {self._calc_unit_price_for("WHITE") for _ in range(5)}
        self.assertEqual(
            len(results), 1,
            f"BUG XAC NHAN: unit_price khong on dinh qua nhieu lan goi: {results}. "
            f"Nguyen nhan: dict prices[item_code] = ip['price_list_rate'] trong "
            f"vong for bi ghi de khi co nhieu dong Item Price cung item_code, "
            f"thu tu DB tra ve khong dam bao."
        )
