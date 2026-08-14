# -*- coding: utf-8 -*-
"""
Test: Composite Key Pricing (màu sắc/xuất xứ/độ dày/bề mặt).

MỤC ĐÍCH
--------
BomOrchestrator.b2_prefetch_master_data() hiện tại chỉ lọc Item Price theo
(item_code, price_list) - BỎ QUA các custom field composite key được sinh từ
AL Pricing Dimension (vd custom_pd_mau_sac). Hệ quả:
  1. Đổi màu không làm đổi giá (aluminum_color=WHITE và DARK ra cùng unit_price).
  2. Nếu 1 item_code có nhiều dòng Item Price, dict bị ghi đè bởi dòng cuối
     cùng DB trả về -> kết quả không xác định (non-deterministic).

Test này dùng ĐÚNG BOM mẫu có sẵn trong seed_demo_data.py (BOM-CDMQ-2C) và
chỉ thêm 1 dòng Item Price thứ 2 (màu DARK, giá chênh mạnh) để bám vào đúng
item_code đã có sẵn (NHOM-XINGFA). Nếu patch chưa được áp dụng, test sẽ FAIL
ở assertNotEqual vì 2 giá ra giống nhau.

CÁCH CHẠY
---------
    bench --site <your-site> run-tests --app alumglass \
        --module alumglass.tests.test_composite_pricing

(Hoặc đặt file này vào alumglass/tests/ trong repo thật sự - Frappe tự
 discover mọi file test_*.py trong thư mục tests/ của từng app.)
"""
import json

import frappe
from frappe.model.naming import make_autoname
from frappe.tests.utils import FrappeTestCase

ITEM_CODE = "NHOM-XINGFA"          # item đại diện có sẵn trong seed data
PRICE_LIST = "Standard Selling"
BOM_CODE = "BOM-CDMQ-2C"
DIMENSION_CODE = "MAU_SAC"         # AL Pricing Dimension đã seed cho màu sắc


class TestCompositePricing(FrappeTestCase):
    """Kiểm chứng: 2 màu khác nhau của cùng 1 item_code phải ra 2 giá khác nhau."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Lấy đúng tên field composite mà AL Pricing Dimension đã tự sinh ra
        # trên Item Price (KHÔNG hardcode "custom_color" vì tên thật phụ thuộc
        # dimension_code, xem al_pricing_dimension.py: _sync_custom_field()).
        cls.color_fieldname = frappe.db.get_value(
            "AL Pricing Dimension", DIMENSION_CODE, "custom_fieldname")
        if not cls.color_fieldname:
            frappe.throw(
                f"Thiếu dữ liệu seed: AL Pricing Dimension '{DIMENSION_CODE}'. "
                f"Hãy chạy seed_demo_data.seed_all() trước khi test."
            )
        if not frappe.db.exists(
            "Custom Field", {"dt": "Item Price", "fieldname": cls.color_fieldname}
        ):
            frappe.throw(
                f"Custom Field '{cls.color_fieldname}' chưa tồn tại trên Item Price. "
                f"AL Pricing Dimension có thể chưa được sync đúng cách."
            )

        cls._white_ip = cls._upsert_item_price("WHITE", 113000)
        cls._dark_ip = cls._upsert_item_price("DARK", 999000)  # chênh rất mạnh, để bắt lỗi

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
        """Tạo 1 Quotation + Quotation Item với màu chỉ định (giống run_test.py)."""
        from frappe.utils import now

        company = (frappe.defaults.get_global_default("company")
                   or frappe.get_all("Company", limit=1, pluck="name")[0])
        bv_name = frappe.db.get_value("AL BOM", BOM_CODE, "current_version")
        self.assertTrue(bv_name, f"BOM '{BOM_CODE}' chưa có current_version - chạy seed trước")

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
        """Chạy BomOrchestrator thật và trả về unit_price của dòng item_code test."""
        from alumglass.engine.bom_orchestrator import BomOrchestrator

        qi_name = self._create_quotation_item(color)
        orch = BomOrchestrator(qi_name)
        result = orch.run()

        matches = [line for line in result.get("lines", [])
                   if line.get("item_code") == ITEM_CODE]
        self.assertTrue(
            matches,
            f"Không tìm thấy dòng BOM nào dùng item_code='{ITEM_CODE}' trong kết quả - "
            f"kiểm tra lại BOM_CODE/seed data."
        )
        return matches[0]["unit_price"]

    # ------------------------------------------------------------------
    def test_same_item_different_color_yields_different_price(self):
        """BUG DEMO: unit_price phải khác nhau giữa WHITE (113,000) và DARK (999,000).

        Nếu test này FAIL với 2 giá bằng nhau -> b2_prefetch_master_data() đang
        bỏ qua composite key (custom_pd_mau_sac) khi tra Item Price.
        """
        price_white = self._calc_unit_price_for("WHITE")
        price_dark = self._calc_unit_price_for("DARK")

        self.assertNotEqual(
            price_white, price_dark,
            f"BUG XÁC NHẬN: unit_price giống nhau ({price_white}) dù khác màu "
            f"(WHITE vs DARK). BomOrchestrator.b2_prefetch_master_data() đang "
            f"chỉ lọc Item Price theo (item_code, price_list), bỏ qua field "
            f"composite '{self.color_fieldname}'. Xem fb_handlers.py:"
            f"aluminum_price_composite() - handler này tồn tại nhưng không "
            f"được gọi trong luồng tính BOM thật."
        )
        self.assertEqual(price_white, 113000)
        self.assertEqual(price_dark, 999000)

    def test_price_lookup_is_deterministic(self):
        """BUG DEMO: gọi 5 lần liên tiếp phải luôn ra cùng 1 giá cho cùng 1 màu.

        Nếu prices[item_code] bị ghi đè bởi thứ tự trả về không đảm bảo từ DB
        (dict overwrite trong vòng for), giá có thể "nhảy" giữa các lần chạy.
        """
        results = {self._calc_unit_price_for("WHITE") for _ in range(5)}
        self.assertEqual(
            len(results), 1,
            f"BUG XÁC NHẬN: unit_price không ổn định qua nhiều lần gọi: {results}. "
            f"Nguyên nhân: dict prices[item_code] = ip['price_list_rate'] trong "
            f"vòng for bị ghi đè khi có nhiều dòng Item Price cùng item_code, "
            f"thứ tự DB trả về không đảm bảo."
        )
