# Hướng dẫn Phát triển & Kế thừa Class trong ERPNext/Frappe
> **Tài liệu đầy đủ: Python + JavaScript — Kế thừa, override, tạo class mới, tích hợp tính năng vào single doctype hoặc toàn bộ hệ thống**

---

## MỤC LỤC

1. [Tổng quan Kiến trúc Kế thừa](#1-tổng-quan-kiến-trúc-kế-thừa)
2. [Python — Kế thừa DocumentClass](#2-python--kế-thừa-documentclass)
3. [Python — Override Từng Phương thức](#3-python--override-từng-phương-thức)
4. [Python — Hooks: Mở rộng Không Sửa Core](#4-python--hooks-mở-rộng-không-sửa-core)
5. [Python — Service Layer Pattern](#5-python--service-layer-pattern)
6. [Python — Custom GL Composer](#6-python--custom-gl-composer)
7. [Python — Custom Taxes and Totals](#7-python--custom-taxes-and-totals)
8. [Python — Mở rộng Toàn Hệ thống (All Doctypes)](#8-python--mở-rộng-toàn-hệ-thống)
9. [JavaScript — Cây Kế thừa Controller](#9-javascript--cây-kế-thừa-controller)
10. [JavaScript — Kế thừa Controller (Single Doctype)](#10-javascript--kế-thừa-controller-single-doctype)
11. [JavaScript — Extend Không Override (frappe.ui.form.on)](#11-javascript--extend-không-override)
12. [JavaScript — Override taxes_and_totals.js](#12-javascript--override-taxes_and_totalsjs)
13. [JavaScript — Tích hợp Toàn Hệ thống (Global JS)](#13-javascript--tích-hợp-toàn-hệ-thống)
14. [Pattern Tích hợp Đầy đủ: Custom Feature End-to-End](#14-pattern-tích-hợp-đầy-đủ)
15. [Tạo Custom DocType kế thừa AccountsController](#15-tạo-custom-doctype-mới)
16. [Whitelist API & Server-side Endpoints](#16-whitelist-api--server-side-endpoints)
17. [Document Mapper (make_mapped_doc)](#17-document-mapper)
18. [Cấu trúc Thư mục Chuẩn Custom App](#18-cấu-trúc-thư-mục-chuẩn)
19. [hooks.py — Reference Đầy đủ](#19-hookspy--reference-đầy-đủ)
20. [Checklist & Anti-patterns](#20-checklist--anti-patterns)

---

## 1. Tổng quan Kiến trúc Kế thừa

### 1.1 Python — Toàn bộ Cây Kế thừa

```
frappe.model.document.Document
  └── frappe.model.document.BaseDocument
        └── erpnext.utilities.transaction_base.TransactionBase
              │   (StatusUpdater, UOM, conversion)
              └── erpnext.controllers.accounts_controller.AccountsController
                    │   (GL dict, taxes, payment schedule, advances, dimensions)
                    ├── erpnext.controllers.selling_controller.SellingController
                    │     │   (pricing rule, commission, customer group)
                    │     └── SalesInvoice
                    │     └── DeliveryNote
                    │     └── SalesOrder
                    │
                    ├── erpnext.controllers.buying_controller.BuyingController
                    │     │   (last purchase rate, subcontracting)
                    │     └── SubcontractingController
                    │           └── PurchaseInvoice
                    │           └── PurchaseOrder
                    │           └── PurchaseReceipt
                    │
                    └── (trực tiếp) PaymentEntry
                    └── (trực tiếp) JournalEntry
```

### 1.2 JavaScript — Toàn bộ Cây Kế thừa

```
frappe.ui.form.Controller
  └── erpnext.taxes_and_totals          (taxes_and_totals.js)
        │   (calculate_item_values, calculate_taxes, apply_discount)
        └── erpnext.TransactionController  (transaction.js)
              │   (item triggers, warehouse, quality inspection, UOM)
              ├── erpnext.buying.BuyingController
              │     └── PurchaseInvoice  (purchase_invoice.js)
              │     └── PurchaseOrder
              │     └── PurchaseReceipt
              │
              └── erpnext.selling.SellingController
                    └── SalesInvoice    (sales_invoice.js)
                    └── SalesOrder
                    └── DeliveryNote
```

### 1.3 Hai Chiến lược Mở rộng

| Chiến lược | Khi nào dùng | Rủi ro upgrade |
|-----------|-------------|----------------|
| `override_doctype_class` | Thay đổi sâu logic submit/cancel/GL | Trung bình — phải merge khi core thay đổi |
| `doc_events` hooks | Thêm validate, on_submit, on_cancel | Thấp — chạy song song, không sửa core |
| `frappe.ui.form.on()` | Thêm JS triggers, buttons nhỏ | Rất thấp |
| Kế thừa JS Controller class | Override toàn bộ controller | Cao — phải track upstream changes |

> **Nguyên tắc vàng:** Dùng hooks trước, kế thừa class khi hooks không đủ.

---

## 2. Python — Kế thừa DocumentClass

### 2.1 Override một DocType hiện có (SalesInvoice)

```python
# custom_app/custom_app/overrides/custom_sales_invoice.py

import frappe
from frappe.utils import flt, today
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice


class CustomSalesInvoice(SalesInvoice):
    """
    Mở rộng SalesInvoice với logic nghiệp vụ đặc thù.
    Đăng ký trong hooks.py:
        override_doctype_class = {
            "Sales Invoice": "custom_app.overrides.custom_sales_invoice.CustomSalesInvoice"
        }
    """

    # ------------------------------------------------------------------ #
    # INIT — Mở rộng Status Updater                                        #
    # ------------------------------------------------------------------ #

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Thêm status updater tùy chỉnh cho doctype riêng
        self.status_updater.append({
            "source_dt": "Sales Invoice Item",
            "target_dt": "Custom Contract Item",
            "join_field": "custom_contract_item",          # FK field trên SI Item
            "target_field": "invoiced_qty",                # Field cập nhật trên target
            "target_ref_field": "qty",                     # Field tham chiếu (100%)
            "source_field": "qty",                         # Field lấy giá trị
            "target_parent_dt": "Custom Contract",
            "target_parent_field": "per_invoiced",         # % field trên parent
            "percent_join_field": "custom_contract",       # FK trên SI Item → Custom Contract
            "status_field": "invoicing_status",
            "keyword": "Invoiced",
            "overflow_type": "billing",
        })

    # ------------------------------------------------------------------ #
    # VALIDATE                                                             #
    # ------------------------------------------------------------------ #

    def validate(self):
        # 1. Custom validation TRƯỚC khi gọi parent
        self._validate_custom_fields()
        self._validate_contract_reference()

        # 2. Gọi parent (toàn bộ chuỗi AccountsController.validate)
        super().validate()

        # 3. Custom logic SAU parent (khi các giá trị đã được tính)
        self._calculate_custom_commission()
        self._set_custom_status_fields()

    def _validate_custom_fields(self):
        """Validate các trường custom."""
        if self.get("custom_contract") and not self.get("custom_contract_date"):
            frappe.throw(
                frappe._("Custom Contract Date is required when Contract is set"),
                title=frappe._("Missing Field")
            )

    def _validate_contract_reference(self):
        """Kiểm tra items khớp với contract."""
        if not self.get("custom_contract"):
            return

        for item in self.items:
            if not item.get("custom_contract_item"):
                continue

            contract_item = frappe.db.get_value(
                "Custom Contract Item",
                item.custom_contract_item,
                ["item_code", "remaining_qty", "parent"],
                as_dict=True
            )

            if not contract_item:
                frappe.throw(
                    frappe._(f"Row {item.idx}: Contract Item {item.custom_contract_item} not found")
                )

            if contract_item.item_code != item.item_code:
                frappe.throw(
                    frappe._(f"Row {item.idx}: Item code does not match contract item")
                )

            # Chỉ kiểm tra khi không phải return
            if not self.is_return:
                available = contract_item.remaining_qty
                # Cộng lại qty của chính doc này nếu đang sửa
                if not self.is_new():
                    existing_qty = frappe.db.get_value(
                        "Sales Invoice Item",
                        {"parent": self.name, "custom_contract_item": item.custom_contract_item},
                        "qty"
                    ) or 0
                    available += existing_qty

                if item.qty > available:
                    frappe.throw(
                        frappe._(
                            f"Row {item.idx}: Qty {item.qty} exceeds contract remaining qty {available}"
                        )
                    )

    def _calculate_custom_commission(self):
        """Tính commission sau khi net_total đã có."""
        commission_rate = flt(self.get("custom_commission_rate"))
        if commission_rate:
            self.custom_commission_amount = flt(
                self.net_total * commission_rate / 100,
                self.precision("custom_commission_amount")
            )

    def _set_custom_status_fields(self):
        """Cập nhật các trường trạng thái phụ."""
        self.custom_requires_director_approval = (
            self.grand_total > 500_000_000  # > 500 triệu
            or flt(self.get("custom_commission_rate")) > 15
        )

    # ------------------------------------------------------------------ #
    # ON_SUBMIT                                                            #
    # ------------------------------------------------------------------ #

    def on_submit(self):
        # Custom logic TRƯỚC parent
        self._create_commission_journal()
        self._update_contract_items("submit")

        # Gọi parent (GL entries, SLE, TCS, loyalty, v.v.)
        super().on_submit()

        # Custom logic SAU parent
        self._notify_contract_manager()
        self._update_custom_analytics()

    def _create_commission_journal(self):
        """Tạo Journal Entry ghi nhận hoa hồng."""
        commission_amount = flt(self.get("custom_commission_amount"))
        if not commission_amount or not self.get("custom_commission_agent"):
            return

        commission_expense_account = frappe.get_cached_value(
            "Company", self.company, "custom_commission_expense_account"
        )
        commission_payable_account = frappe.get_cached_value(
            "Company", self.company, "custom_commission_payable_account"
        )

        if not commission_expense_account or not commission_payable_account:
            frappe.msgprint(
                frappe._("Commission accounts not configured. Skipping commission journal."),
                alert=True
            )
            return

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = self.posting_date
        je.company = self.company
        je.user_remark = f"Commission for Sales Invoice {self.name}"
        je.custom_reference_invoice = self.name

        je.append("accounts", {
            "account": commission_expense_account,
            "debit_in_account_currency": commission_amount,
            "cost_center": self.cost_center,
        })
        je.append("accounts", {
            "account": commission_payable_account,
            "credit_in_account_currency": commission_amount,
            "party_type": "Supplier",
            "party": self.custom_commission_agent,
        })

        je.flags.ignore_permissions = True
        je.insert()
        je.submit()

        # Lưu reference
        frappe.db.set_value(
            "Sales Invoice", self.name, "custom_commission_je", je.name
        )

    def _update_contract_items(self, action):
        """Cập nhật qty đã xuất hóa đơn trên Contract Items."""
        for item in self.items:
            if not item.get("custom_contract_item"):
                continue

            delta = item.qty if action == "submit" else -item.qty
            frappe.db.sql("""
                UPDATE `tabCustom Contract Item`
                SET invoiced_qty = invoiced_qty + %s
                WHERE name = %s
            """, (delta, item.custom_contract_item))

    def _notify_contract_manager(self):
        """Gửi thông báo tới contract manager."""
        if not self.get("custom_contract"):
            return

        contract_manager = frappe.db.get_value(
            "Custom Contract", self.custom_contract, "contract_manager"
        )
        if contract_manager:
            frappe.publish_realtime(
                "eval_js",
                f"frappe.show_alert('New invoice {self.name} submitted against your contract')",
                user=contract_manager
            )

    def _update_custom_analytics(self):
        """Cập nhật bảng analytics tùy chỉnh."""
        frappe.db.sql("""
            INSERT INTO `tabCustom Sales Analytics`
                (name, invoice, posting_date, customer, net_total, commission)
            VALUES (%(name)s, %(invoice)s, %(date)s, %(customer)s, %(net)s, %(comm)s)
            ON DUPLICATE KEY UPDATE
                net_total = VALUES(net_total),
                commission = VALUES(commission)
        """, {
            "name": frappe.generate_hash(length=10),
            "invoice": self.name,
            "date": self.posting_date,
            "customer": self.customer,
            "net": self.net_total,
            "comm": flt(self.get("custom_commission_amount")),
        })

    # ------------------------------------------------------------------ #
    # ON_CANCEL                                                            #
    # ------------------------------------------------------------------ #

    def on_cancel(self):
        # Đảo ngược custom logic
        self._cancel_commission_journal()
        self._update_contract_items("cancel")

        # Gọi parent
        super().on_cancel()

    def _cancel_commission_journal(self):
        """Hủy Journal Entry hoa hồng."""
        je_name = self.get("custom_commission_je")
        if je_name and frappe.db.exists("Journal Entry", {"name": je_name, "docstatus": 1}):
            je = frappe.get_doc("Journal Entry", je_name)
            je.flags.ignore_permissions = True
            je.cancel()

    # ------------------------------------------------------------------ #
    # GL ENTRIES                                                           #
    # ------------------------------------------------------------------ #

    def get_gl_entries(self, inventory_account_map=None):
        """
        Override để thêm GL entries tùy chỉnh.
        LUÔN gọi super() trước, thêm vào danh sách kết quả.
        """
        gl_entries = super().get_gl_entries(inventory_account_map)

        # Thêm GL entries cho phí môi trường (nếu có)
        gl_entries += self._get_environmental_levy_gl_entries()

        return gl_entries

    def _get_environmental_levy_gl_entries(self):
        """GL entries cho phí môi trường."""
        levy_amount = flt(self.get("custom_environmental_levy"))
        if not levy_amount:
            return []

        levy_account = frappe.get_cached_value(
            "Company", self.company, "custom_environmental_levy_account"
        )
        if not levy_account:
            return []

        return [
            # Debit: Chi phí phí môi trường
            self.get_gl_dict({
                "account": levy_account,
                "debit": levy_amount,
                "debit_in_account_currency": levy_amount,
                "against": self.debit_to,
                "remarks": "Environmental Levy",
                "cost_center": self.cost_center,
            }),
            # Credit: AR của khách hàng
            self.get_gl_dict({
                "account": self.debit_to,
                "party_type": "Customer",
                "party": self.customer,
                "credit": levy_amount,
                "credit_in_account_currency": levy_amount,
                "against": levy_account,
                "remarks": "Environmental Levy",
            }),
        ]
```

### 2.2 Override PurchaseInvoice

```python
# custom_app/overrides/custom_purchase_invoice.py

import frappe
from frappe.utils import flt
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice


class CustomPurchaseInvoice(PurchaseInvoice):
    """Mở rộng PurchaseInvoice với logic phê duyệt và kiểm soát ngân sách."""

    def validate(self):
        self._validate_budget_before_approve()
        super().validate()
        self._set_approval_required()

    def _validate_budget_before_approve(self):
        """Kiểm tra ngân sách phòng ban trước khi lưu."""
        if not self.get("custom_department_budget"):
            return

        used = frappe.db.sql("""
            SELECT COALESCE(SUM(pii.amount), 0)
            FROM `tabPurchase Invoice Item` pii
            JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE pi.custom_department_budget = %s
              AND pi.docstatus = 1
              AND pi.name != %s
        """, (self.custom_department_budget, self.name or ""))[0][0]

        budget_limit = frappe.db.get_value(
            "Custom Department Budget", self.custom_department_budget, "budget_amount"
        )

        current_total = sum(item.amount for item in self.items)

        if used + current_total > budget_limit:
            frappe.throw(
                frappe._(
                    f"This invoice would exceed department budget limit. "
                    f"Used: {used:,.0f}, This Invoice: {current_total:,.0f}, "
                    f"Limit: {budget_limit:,.0f}"
                )
            )

    def _set_approval_required(self):
        """Xác định có cần phê duyệt không."""
        self.custom_approval_required = (
            self.grand_total > 100_000_000  # > 100 triệu
        )

    def on_submit(self):
        if self.get("custom_approval_required") and not self.get("custom_approved_by"):
            frappe.throw(
                frappe._("This invoice requires director approval before submission.")
            )
        super().on_submit()
        self._consume_department_budget()

    def _consume_department_budget(self):
        """Ghi nhận tiêu ngân sách."""
        if not self.get("custom_department_budget"):
            return

        frappe.db.sql("""
            UPDATE `tabCustom Department Budget`
            SET consumed_amount = consumed_amount + %s
            WHERE name = %s
        """, (self.grand_total, self.custom_department_budget))

    def on_cancel(self):
        super().on_cancel()
        self._reverse_department_budget()

    def _reverse_department_budget(self):
        if not self.get("custom_department_budget"):
            return

        frappe.db.sql("""
            UPDATE `tabCustom Department Budget`
            SET consumed_amount = consumed_amount - %s
            WHERE name = %s
        """, (self.grand_total, self.custom_department_budget))
```

---

## 3. Python — Override Từng Phương thức

### 3.1 Override chỉ GL entries (không động vào validate/submit)

```python
class CustomSalesInvoice(SalesInvoice):

    def get_gl_entries(self, inventory_account_map=None):
        """Chèn custom GL entries vào danh sách có sẵn."""
        gl_entries = super().get_gl_entries(inventory_account_map)

        # Pattern: lặp qua items và thêm entries
        for item in self.items:
            extra = self._build_item_extra_gl(item)
            if extra:
                gl_entries.extend(extra)

        # Pattern: thêm document-level entry
        if self.get("custom_warranty_amount"):
            gl_entries.extend(self._build_warranty_gl())

        return gl_entries

    def _build_item_extra_gl(self, item):
        """Xây dựng extra GL cho từng item."""
        if not item.get("custom_service_fee"):
            return []

        fee = flt(item.custom_service_fee)
        fee_account = frappe.get_cached_value("Item", item.item_code, "custom_service_fee_account")
        if not fee_account:
            return []

        return [
            self.get_gl_dict({
                "account": fee_account,
                "credit": fee,
                "credit_in_account_currency": fee,
                "against": self.debit_to,
                "voucher_detail_no": item.name,
                "remarks": f"Service fee for {item.item_code}",
                "cost_center": item.cost_center,
                "project": item.project,
            }, item=item),
            self.get_gl_dict({
                "account": self.debit_to,
                "party_type": "Customer",
                "party": self.customer,
                "debit": fee,
                "debit_in_account_currency": fee,
                "against": fee_account,
                "voucher_detail_no": item.name,
                "remarks": f"Service fee for {item.item_code}",
            }, item=item),
        ]

    def _build_warranty_gl(self):
        """GL entry cho phí bảo hành."""
        warranty_amount = flt(self.custom_warranty_amount)
        warranty_provision_account = frappe.get_cached_value(
            "Company", self.company, "custom_warranty_provision_account"
        )
        warranty_expense_account = frappe.get_cached_value(
            "Company", self.company, "custom_warranty_expense_account"
        )

        if not warranty_provision_account or not warranty_expense_account:
            return []

        return [
            self.get_gl_dict({
                "account": warranty_expense_account,
                "debit": warranty_amount,
                "debit_in_account_currency": warranty_amount,
                "against": warranty_provision_account,
                "remarks": "Warranty Provision",
            }),
            self.get_gl_dict({
                "account": warranty_provision_account,
                "credit": warranty_amount,
                "credit_in_account_currency": warranty_amount,
                "against": warranty_expense_account,
                "remarks": "Warranty Provision",
            }),
        ]
```

### 3.2 Override set_missing_values

```python
class CustomSalesInvoice(SalesInvoice):

    def set_missing_values(self, for_validate=False):
        """Thêm giá trị mặc định sau khi parent điền các giá trị chuẩn."""
        super().set_missing_values(for_validate)

        # Điền custom fields từ Customer
        if self.customer and not self.get("custom_sales_region"):
            self.custom_sales_region = frappe.db.get_value(
                "Customer", self.customer, "custom_sales_region"
            )

        # Điền fiscal quarter
        if self.posting_date:
            month = frappe.utils.getdate(self.posting_date).month
            self.custom_fiscal_quarter = f"Q{(month - 1) // 3 + 1}"
```

### 3.3 Override validate_debit_to_acc (thêm điều kiện)

```python
class CustomSalesInvoice(SalesInvoice):

    def validate_debit_to_acc(self):
        """Gọi parent rồi thêm validation riêng."""
        super().validate_debit_to_acc()

        # Kiểm tra thêm: account phải thuộc đúng region
        if self.get("custom_sales_region"):
            allowed_accounts = frappe.get_all(
                "Custom Region Account",
                filters={"region": self.custom_sales_region, "company": self.company},
                pluck="account"
            )
            if allowed_accounts and self.debit_to not in allowed_accounts:
                frappe.throw(
                    frappe._(
                        f"Debit To account {self.debit_to} is not allowed "
                        f"for region {self.custom_sales_region}"
                    )
                )
```

---

## 4. Python — Hooks: Mở rộng Không Sửa Core

### 4.1 doc_events — Ít rủi ro nhất

```python
# custom_app/hooks.py

doc_events = {
    # Single doctype
    "Sales Invoice": {
        "before_insert":  "custom_app.events.sales_invoice.before_insert",
        "after_insert":   "custom_app.events.sales_invoice.after_insert",
        "validate":       "custom_app.events.sales_invoice.validate",
        "before_save":    "custom_app.events.sales_invoice.before_save",
        "on_submit":      "custom_app.events.sales_invoice.on_submit",
        "on_cancel":      "custom_app.events.sales_invoice.on_cancel",
        "on_trash":       "custom_app.events.sales_invoice.on_trash",
        "before_submit":  "custom_app.events.sales_invoice.before_submit",
        "before_cancel":  "custom_app.events.sales_invoice.before_cancel",
        "after_submit":   "custom_app.events.sales_invoice.after_submit",
    },
    "Purchase Invoice": {
        "validate":  "custom_app.events.purchase_invoice.validate",
        "on_submit": "custom_app.events.purchase_invoice.on_submit",
        "on_cancel": "custom_app.events.purchase_invoice.on_cancel",
    },
    # Tất cả doctypes (dùng *)
    "*": {
        "on_submit": "custom_app.events.global_events.on_any_submit",
        "on_cancel": "custom_app.events.global_events.on_any_cancel",
    },
    # GL Entry hooks
    "GL Entry": {
        "before_insert": "custom_app.events.gl_entry.before_insert",
        "after_insert":  "custom_app.events.gl_entry.after_insert",
    },
}
```

### 4.2 Viết Event Functions

```python
# custom_app/events/sales_invoice.py

import frappe
from frappe.utils import flt, today, getdate


def before_submit(doc, method):
    """
    Chạy TRƯỚC khi SalesInvoice.on_submit() được gọi.
    Dùng để: kiểm tra điều kiện, chặn submit sớm.
    """
    _check_approval_status(doc)
    _validate_credit_note_against_original(doc)


def on_submit(doc, method):
    """
    Chạy SAU khi SalesInvoice.on_submit() đã hoàn tất.
    Tại đây: GL đã được tạo, SLE đã được tạo.
    """
    _create_commission_entry(doc)
    _trigger_crm_webhook(doc)
    _update_salesperson_kpi(doc)


def on_cancel(doc, method):
    """
    Chạy SAU khi SalesInvoice.on_cancel() đã hoàn tất.
    """
    _reverse_commission_entry(doc)
    _notify_crm_cancellation(doc)


def validate(doc, method):
    """
    Chạy SAU khi SalesInvoice.validate() đã hoàn tất.
    Các field chuẩn (taxes, totals) đã được tính xong.
    """
    _validate_custom_po_number(doc)
    _set_custom_analytics_fields(doc)


def _check_approval_status(doc):
    if (
        flt(doc.grand_total) > 1_000_000_000  # > 1 tỷ
        and not doc.get("custom_board_approval_ref")
    ):
        frappe.throw(
            frappe._("Invoices above 1 billion VND require Board Approval reference."),
            frappe.ValidationError
        )


def _validate_credit_note_against_original(doc):
    """Kiểm tra credit note không vượt giá trị hóa đơn gốc."""
    if not doc.is_return or not doc.return_against:
        return

    original_outstanding = frappe.db.get_value(
        "Sales Invoice", doc.return_against, "outstanding_amount"
    )
    if abs(doc.grand_total) > abs(original_outstanding):
        frappe.throw(
            frappe._(
                f"Credit note amount {abs(doc.grand_total):,.0f} exceeds "
                f"original invoice outstanding {abs(original_outstanding):,.0f}"
            )
        )


def _validate_custom_po_number(doc):
    """Kiểm tra PO number không duplicate với hóa đơn khác của cùng khách."""
    po_no = doc.get("custom_customer_po_number")
    if not po_no:
        return

    duplicate = frappe.db.exists("Sales Invoice", {
        "custom_customer_po_number": po_no,
        "customer": doc.customer,
        "docstatus": ("!=", 2),
        "name": ("!=", doc.name or ""),
    })
    if duplicate:
        frappe.throw(
            frappe._(f"Customer PO {po_no} already exists in invoice {duplicate}")
        )


def _create_commission_entry(doc):
    commission = flt(doc.get("custom_commission_amount"))
    if not commission or doc.get("custom_commission_je"):
        return

    # Tạo JE commission (xem §2.1 _create_commission_journal)
    pass


def _reverse_commission_entry(doc):
    je = doc.get("custom_commission_je")
    if je and frappe.db.get_value("Journal Entry", je, "docstatus") == 1:
        frappe.get_doc("Journal Entry", je).cancel()


def _set_custom_analytics_fields(doc):
    """Điền các trường tổng hợp phục vụ báo cáo."""
    doc.custom_tax_total = sum(
        flt(t.tax_amount) for t in doc.taxes
        if t.account_head and "VAT" in (t.description or "")
    )


def _trigger_crm_webhook(doc):
    """Gửi webhook tới CRM ngoài."""
    try:
        import requests
        crm_url = frappe.db.get_single_value("Custom CRM Settings", "webhook_url")
        if crm_url:
            requests.post(crm_url, json={
                "event": "invoice_submitted",
                "invoice": doc.name,
                "customer": doc.customer,
                "amount": doc.grand_total,
            }, timeout=5)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "CRM Webhook Error")


def _update_salesperson_kpi(doc):
    """Cập nhật KPI bán hàng."""
    for contrib in doc.sales_team or []:
        if contrib.sales_person:
            frappe.db.sql("""
                INSERT INTO `tabSalesperson Monthly KPI`
                    (name, salesperson, month, invoiced_amount)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    invoiced_amount = invoiced_amount + VALUES(invoiced_amount)
            """, (
                frappe.generate_hash(length=10),
                contrib.sales_person,
                frappe.utils.get_first_day(doc.posting_date).strftime("%Y-%m-01"),
                flt(doc.grand_total) * flt(contrib.allocated_percentage) / 100,
            ))


def _notify_crm_cancellation(doc):
    pass
```

### 4.3 GL Entry Hook — Inject thêm thông tin

```python
# custom_app/events/gl_entry.py

import frappe


def before_insert(doc, method):
    """
    Được gọi trước mỗi GL Entry được tạo.
    Dùng để: thêm custom fields, dimension, chú thích.
    """
    _set_custom_dimension(doc)
    _enrich_remarks(doc)


def _set_custom_dimension(gle):
    """Tự động điền custom dimension từ voucher."""
    if gle.voucher_type == "Sales Invoice":
        region = frappe.db.get_value(
            "Sales Invoice", gle.voucher_no, "custom_sales_region"
        )
        if region:
            gle.custom_sales_region = region


def _enrich_remarks(gle):
    """Thêm thông tin vào remarks để trace dễ hơn."""
    if gle.party and not (gle.remarks or "").endswith(f"[{gle.party}]"):
        gle.remarks = f"{gle.remarks or ''} [{gle.party}]".strip()
```

---

## 5. Python — Service Layer Pattern

Pattern ERPNext dùng Service classes để tách logic phức tạp ra khỏi document class. Áp dụng tương tự cho custom features.

```python
# custom_app/services/vat_service.py

import frappe
from frappe.utils import flt


class VATService:
    """
    Service tính VAT theo quy định Việt Nam.
    Sử dụng:
        VATService(doc).on_validate()
        VATService(doc).on_submit()
    """

    VAT_RATES = {
        "Standard":  10,
        "Reduced":    5,
        "Zero":       0,
        "Exempt":     0,
    }

    def __init__(self, doc):
        self.doc = doc

    # ---- Public interface ---- #

    def on_validate(self):
        self.calculate_vat_amounts()
        self.validate_vat_accounts()

    def on_submit(self):
        self.create_vat_return_entry()

    def on_cancel(self):
        self.cancel_vat_return_entry()

    # ---- Internal methods ---- #

    def calculate_vat_amounts(self):
        total_vat = 0.0
        for item in self.doc.items:
            vat_rate = self._get_vat_rate(item.item_code)
            item_vat = flt(item.net_amount * vat_rate / 100, self.doc.precision("net_total"))
            item.custom_vat_amount = item_vat
            item.custom_vat_rate = vat_rate
            total_vat += item_vat

        self.doc.custom_total_vat = flt(total_vat, self.doc.precision("grand_total"))

    def validate_vat_accounts(self):
        for tax_row in self.doc.taxes:
            if tax_row.custom_is_vat and not tax_row.account_head:
                frappe.throw(
                    frappe._(f"VAT account head is required in row {tax_row.idx}")
                )

    def create_vat_return_entry(self):
        """Tạo bản ghi trong VAT Return register."""
        if not self.doc.get("custom_total_vat"):
            return

        vat_entry = frappe.new_doc("Custom VAT Register Entry")
        vat_entry.update({
            "voucher_type": self.doc.doctype,
            "voucher_no": self.doc.name,
            "posting_date": self.doc.posting_date,
            "party": self.doc.get("customer") or self.doc.get("supplier"),
            "taxable_amount": self.doc.net_total,
            "vat_amount": self.doc.custom_total_vat,
            "vat_period": self._get_vat_period(),
        })
        vat_entry.flags.ignore_permissions = True
        vat_entry.insert()

    def cancel_vat_return_entry(self):
        entries = frappe.get_all(
            "Custom VAT Register Entry",
            filters={"voucher_no": self.doc.name},
            pluck="name"
        )
        for entry_name in entries:
            frappe.delete_doc("Custom VAT Register Entry", entry_name, ignore_permissions=True)

    def _get_vat_rate(self, item_code):
        vat_category = frappe.get_cached_value("Item", item_code, "custom_vat_category")
        return self.VAT_RATES.get(vat_category, 10)

    def _get_vat_period(self):
        """Trả về kỳ khai thuế: Q1/2024, Q2/2024, ..."""
        date = frappe.utils.getdate(self.doc.posting_date)
        quarter = (date.month - 1) // 3 + 1
        return f"Q{quarter}/{date.year}"
```

### 5.1 Sử dụng Service trong Hook hoặc DocClass

```python
# Trong hook function
def on_submit(doc, method):
    from custom_app.services.vat_service import VATService
    VATService(doc).on_submit()

# Trong override class
class CustomSalesInvoice(SalesInvoice):
    def validate(self):
        from custom_app.services.vat_service import VATService
        VATService(self).on_validate()
        super().validate()

    def on_submit(self):
        from custom_app.services.vat_service import VATService
        VATService(self).on_submit()
        super().on_submit()

    def on_cancel(self):
        from custom_app.services.vat_service import VATService
        VATService(self).on_cancel()
        super().on_cancel()
```

---

## 6. Python — Custom GL Composer

```python
# custom_app/services/custom_si_gl_composer.py

import frappe
from frappe.utils import flt

try:
    # ERPNext v14+
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
        SalesInvoiceGLComposer,
    )
    BASE_COMPOSER = SalesInvoiceGLComposer
except ImportError:
    # Fallback: tạo từ BaseGLComposer
    from erpnext.accounts.services.base_gl_composer import BaseGLComposer
    BASE_COMPOSER = BaseGLComposer


class CustomSalesInvoiceGLComposer(BASE_COMPOSER):
    """
    Mở rộng GL Composer cho Sales Invoice.
    Dùng khi cần toàn quyền kiểm soát bút toán kế toán.
    """

    def compose(self, inventory_account_map=None):
        """Entry point — ERPNext gọi hàm này."""
        # Lấy GL entries chuẩn từ parent
        gl_entries = super().compose(inventory_account_map)

        # Chèn entries tùy chỉnh
        gl_entries += self._make_export_duty_entries()
        gl_entries += self._make_customs_duty_entries()
        gl_entries += self._make_prepaid_revenue_entries()

        return gl_entries

    def _make_export_duty_entries(self):
        """Bút toán thuế xuất khẩu."""
        entries = []
        doc = self.doc

        for item in doc.items:
            duty = flt(item.get("custom_export_duty"))
            if not duty:
                continue

            duty_account = self._get_export_duty_account(item)
            if not duty_account:
                continue

            entries += [
                doc.get_gl_dict({
                    "account": duty_account,
                    "credit": duty,
                    "credit_in_account_currency": duty,
                    "against": doc.debit_to,
                    "voucher_detail_no": item.name,
                    "remarks": f"Export Duty — {item.item_code}",
                    "cost_center": item.cost_center,
                    "project": item.project,
                }, item=item),
                doc.get_gl_dict({
                    "account": doc.debit_to,
                    "party_type": "Customer",
                    "party": doc.customer,
                    "debit": duty,
                    "debit_in_account_currency": duty,
                    "against": duty_account,
                    "voucher_detail_no": item.name,
                    "remarks": f"Export Duty — {item.item_code}",
                }, item=item),
            ]

        return entries

    def _make_customs_duty_entries(self):
        customs_amount = flt(self.doc.get("custom_customs_duty_total"))
        if not customs_amount:
            return []

        customs_account = frappe.get_cached_value(
            "Company", self.doc.company, "custom_customs_duty_account"
        )
        if not customs_account:
            return []

        return [
            self.doc.get_gl_dict({
                "account": customs_account,
                "credit": customs_amount,
                "credit_in_account_currency": customs_amount,
                "against": self.doc.debit_to,
                "remarks": "Customs Duty",
                "cost_center": self.doc.cost_center,
            }),
            self.doc.get_gl_dict({
                "account": self.doc.debit_to,
                "party_type": "Customer",
                "party": self.doc.customer,
                "debit": customs_amount,
                "debit_in_account_currency": customs_amount,
                "against": customs_account,
                "remarks": "Customs Duty",
            }),
        ]

    def _make_prepaid_revenue_entries(self):
        """Doanh thu nhận trước — ghi Deferred Revenue."""
        deferred_amount = flt(self.doc.get("custom_deferred_revenue_amount"))
        if not deferred_amount:
            return []

        deferred_account = frappe.get_cached_value(
            "Company", self.doc.company, "custom_deferred_revenue_account"
        )
        income_account = frappe.get_cached_value(
            "Company", self.doc.company, "default_income_account"
        )
        if not deferred_account or not income_account:
            return []

        return [
            self.doc.get_gl_dict({
                "account": income_account,
                "debit": deferred_amount,
                "debit_in_account_currency": deferred_amount,
                "against": deferred_account,
                "remarks": "Transfer to Deferred Revenue",
            }),
            self.doc.get_gl_dict({
                "account": deferred_account,
                "credit": deferred_amount,
                "credit_in_account_currency": deferred_amount,
                "against": income_account,
                "remarks": "Deferred Revenue",
            }),
        ]

    def _get_export_duty_account(self, item):
        return (
            item.get("custom_export_duty_account")
            or frappe.get_cached_value("Company", self.doc.company, "custom_default_export_duty_account")
        )


# ---- Kết nối với DocClass ---- #
# Trong CustomSalesInvoice:
#
# def get_gl_entries(self, inventory_account_map=None):
#     from custom_app.services.custom_si_gl_composer import CustomSalesInvoiceGLComposer
#     return CustomSalesInvoiceGLComposer(self).compose(inventory_account_map)
```

---

## 7. Python — Custom Taxes and Totals

```python
# custom_app/services/custom_taxes_and_totals.py

from frappe.utils import flt
from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals as BaseCalc


class CustomTaxesAndTotals(BaseCalc):
    """
    Mở rộng bộ tính thuế & tổng.
    Đăng ký trong hooks.py:
        override_whitelisted_methods = {
            "erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals":
                "custom_app.services.custom_taxes_and_totals.CustomTaxesAndTotals"
        }
    """

    def _calculate(self):
        """Override điểm tính toán chính."""
        # Chạy toàn bộ logic chuẩn
        super()._calculate()

        # Thêm tính toán custom SAU
        self._calculate_handling_charges()
        self._calculate_environmental_levy()
        self._recalculate_grand_total_with_custom_charges()

    def calculate_item_values(self):
        """Override tính toán từng item."""
        # Gọi parent trước
        super().calculate_item_values()

        # Áp dụng custom price adjustments
        for item in self.doc.get("items", []):
            self._apply_custom_item_surcharge(item)

    def _apply_custom_item_surcharge(self, item):
        """Phụ phí theo loại item."""
        surcharge_rate = flt(item.get("custom_surcharge_rate"))
        if surcharge_rate and item.net_amount:
            item.custom_surcharge_amount = flt(
                item.net_amount * surcharge_rate / 100,
                self.doc.precision("net_total")
            )

    def _calculate_handling_charges(self):
        """Tính phí xử lý theo trọng lượng."""
        if not self.doc.get("custom_charge_handling"):
            self.doc.custom_handling_charge = 0
            return

        total_weight = sum(
            flt(item.get("total_weight") or flt(item.weight_per_unit) * flt(item.qty))
            for item in self.doc.get("items", [])
        )

        rate_per_kg = flt(self.doc.get("custom_handling_rate_per_kg") or 500)  # 500 VND/kg
        self.doc.custom_handling_charge = flt(
            total_weight * rate_per_kg,
            self.doc.precision("grand_total")
        )

    def _calculate_environmental_levy(self):
        """Tính phí bảo vệ môi trường."""
        levy_items = [
            item for item in self.doc.get("items", [])
            if self._item_has_env_levy(item.item_code)
        ]
        self.doc.custom_environmental_levy = flt(
            sum(item.net_amount * 0.005 for item in levy_items),
            self.doc.precision("grand_total")
        )

    def _recalculate_grand_total_with_custom_charges(self):
        """Cộng thêm các khoản phí vào grand_total."""
        extra = (
            flt(self.doc.get("custom_handling_charge"))
            + flt(self.doc.get("custom_environmental_levy"))
        )
        if extra:
            self.doc.grand_total = flt(
                self.doc.grand_total + extra,
                self.doc.precision("grand_total")
            )
            self.doc.base_grand_total = flt(
                self.doc.grand_total * self.doc.conversion_rate,
                self.doc.precision("base_grand_total")
            )
            self.doc.outstanding_amount = flt(
                self.doc.grand_total - flt(self.doc.get("total_advance")),
                self.doc.precision("outstanding_amount")
            )

    @staticmethod
    def _item_has_env_levy(item_code):
        import frappe
        return bool(
            frappe.get_cached_value("Item", item_code, "custom_environmental_category")
        )
```

---

## 8. Python — Mở rộng Toàn Hệ thống

### 8.1 Hook `*` — Áp dụng cho mọi DocType

```python
# custom_app/hooks.py

doc_events = {
    "*": {
        "on_submit": "custom_app.events.global_events.on_any_submit",
        "on_cancel": "custom_app.events.global_events.on_any_cancel",
        "validate":  "custom_app.events.global_events.on_any_validate",
    }
}
```

```python
# custom_app/events/global_events.py

import frappe

AUDIT_DOCTYPES = {
    "Sales Invoice", "Purchase Invoice", "Payment Entry",
    "Journal Entry", "Stock Entry", "Delivery Note", "Purchase Receipt"
}


def on_any_submit(doc, method):
    """Audit trail cho tất cả submitted documents."""
    if doc.doctype not in AUDIT_DOCTYPES:
        return

    frappe.get_doc({
        "doctype": "Custom Audit Log",
        "action": "Submit",
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
        "user": frappe.session.user,
        "timestamp": frappe.utils.now(),
        "ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None,
    }).insert(ignore_permissions=True)


def on_any_cancel(doc, method):
    """Log cancellations với lý do."""
    if doc.doctype not in AUDIT_DOCTYPES:
        return

    frappe.get_doc({
        "doctype": "Custom Audit Log",
        "action": "Cancel",
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
        "user": frappe.session.user,
        "timestamp": frappe.utils.now(),
        "remarks": doc.get("reason_for_cancellation") or "",
    }).insert(ignore_permissions=True)


def on_any_validate(doc, method):
    """Kiểm tra mandatory custom fields cho tất cả submitted docs."""
    # Ví dụ: tất cả documents phải có cost_center nếu company yêu cầu
    if not doc.get("company"):
        return

    require_cost_center = frappe.get_cached_value(
        "Company", doc.company, "custom_mandatory_cost_center"
    )
    if require_cost_center and not doc.get("cost_center"):
        frappe.throw(
            frappe._(f"Cost Center is mandatory for company {doc.company}")
        )
```

### 8.2 Override AccountsController cho toàn bộ module kế toán

```python
# custom_app/overrides/custom_accounts_controller.py

from erpnext.controllers.accounts_controller import AccountsController


class CustomAccountsController(AccountsController):
    """
    Mở rộng base controller — ảnh hưởng TẤT CẢ doctype kế toán.
    Chỉ dùng khi cần thay đổi hành vi core trên mọi doctype.

    hooks.py:
        override_doctype_class = {
            "Sales Invoice": "custom_app.overrides.custom_si.CustomSalesInvoice",
            "Purchase Invoice": "...",
            # KHÔNG override AccountsController trực tiếp
            # vì Frappe không hỗ trợ override abstract controllers
        }

    Thay vào đó: kế thừa trước khi tạo SI/PI override class.
    """

    def get_gl_dict(self, args, account_currency=None, item=None):
        """Thêm custom fields vào mọi GL dict."""
        gl_dict = super().get_gl_dict(args, account_currency, item)

        # Thêm custom dimension từ document gốc
        if self.get("custom_profit_center"):
            gl_dict["custom_profit_center"] = self.custom_profit_center

        return gl_dict

    def validate(self):
        """Thêm validation chạy trên mọi doctype kế toán."""
        self._validate_mandatory_custom_dimensions()
        super().validate()

    def _validate_mandatory_custom_dimensions(self):
        """Kiểm tra custom dimension bắt buộc."""
        if not self.get("company"):
            return

        mandatory_dims = frappe.get_all(
            "Custom Mandatory Dimension",
            filters={
                "company": self.company,
                "applicable_doctype": self.doctype,
            },
            pluck="dimension_fieldname"
        )
        for dim in mandatory_dims:
            if not self.get(dim):
                frappe.throw(
                    frappe._(f"Custom dimension {dim} is mandatory for {self.doctype}")
                )
```

---

## 9. JavaScript — Cây Kế thừa Controller

### 9.1 Cây đầy đủ và điểm mở rộng

```
frappe.ui.form.Controller
  └── erpnext.taxes_and_totals  [taxes_and_totals.js]
        Quan trọng nhất:
          - calculate_taxes_and_totals()
          - calculate_item_values() [client-side mirror]
          - set_discount_amount()
          - set_item_wise_tax_breakup()

        └── erpnext.TransactionController  [transaction.js]
              Quan trọng nhất:
                - setup() — đăng ký item/tax triggers
                - onload() — set defaults
                - refresh() — buttons/state
                - get_item_details() — fetch item info
                - make_payment_entry()
                - set_query_for_batch()
                - calculate_taxes_and_totals()

              ├── erpnext.buying.BuyingController  [buying/js/buying.js]
              │     Thêm:
              │       - supplier trigger
              │       - set_from_product_bundle()
              │       - update_auto_repeat_reference()
              │
              │     └── erpnext.accounts.PurchaseInvoice  [purchase_invoice.js]
              │           Thêm:
              │             - block/unblock buttons
              │             - inter-company buttons
              │             - expense_account query
              │
              └── erpnext.selling.SellingController  [selling/js/selling.js]
                    Thêm:
                      - customer trigger
                      - loyalty points
                      - apply_pricing_rule()
                      - make_sales_order()

                    └── erpnext.accounts.SalesInvoiceController  [sales_invoice.js]
                          Thêm:
                            - POS triggers
                            - TCS
                            - return/credit note buttons
                            - loyalty points UI
```

---

## 10. JavaScript — Kế thừa Controller (Single Doctype)

### 10.1 Kế thừa SalesInvoiceController đầy đủ

```javascript
// custom_app/public/js/custom_sales_invoice.js

frappe.provide("custom_app.accounts");

custom_app.accounts.CustomSalesInvoiceController = class CustomSalesInvoiceController
    extends erpnext.accounts.SalesInvoiceController {

    // ------------------------------------------------------------------ //
    // SETUP — chạy một lần khi form được khởi tạo                         //
    // ------------------------------------------------------------------ //

    setup(doc) {
        // Gọi parent setup trước
        super.setup(doc);

        // Thêm make_methods cho custom documents
        Object.assign(this.frm.make_methods || {}, {
            "Custom Commission Note": () => this.make_commission_note(),
            "Custom VAT Declaration":  () => this.make_vat_declaration(),
        });

        // Đăng ký thêm event listeners tùy chỉnh
        this._setup_custom_queries();
        this._setup_custom_triggers();
    }

    _setup_custom_queries() {
        const frm = this.frm;

        // Query filter cho custom_contract
        frm.set_query("custom_contract", () => ({
            filters: {
                customer: frm.doc.customer,
                status: "Active",
                company: frm.doc.company,
            },
        }));

        // Query filter cho custom_commission_agent
        frm.set_query("custom_commission_agent", () => ({
            filters: { supplier_group: "Commission Agent" },
        }));

        // Query filter cho custom_contract_item trong child table
        frm.set_query("custom_contract_item", "items", (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            return {
                filters: {
                    parent: doc.custom_contract,
                    item_code: row.item_code,
                    remaining_qty: [">", 0],
                },
            };
        });
    }

    _setup_custom_triggers() {
        const me = this;

        // Trigger trên child table items — custom field
        frappe.ui.form.on(this.frm.doctype + " Item", {
            custom_contract_item(frm, cdt, cdn) {
                me._on_contract_item_change(cdt, cdn);
            },
            custom_surcharge_rate(frm, cdt, cdn) {
                me.calculate_taxes_and_totals();
            },
        });
    }

    // ------------------------------------------------------------------ //
    // ONLOAD                                                               //
    // ------------------------------------------------------------------ //

    onload() {
        super.onload();

        // Thêm vào danh sách ignore khi cancel
        this.frm.ignore_doctypes_on_cancel_all = [
            ...(this.frm.ignore_doctypes_on_cancel_all || []),
            "Custom Commission Note",
            "Custom VAT Register Entry",
        ];

        // Set default cho field custom
        if (this.frm.is_new()) {
            this._set_custom_defaults();
        }
    }

    _set_custom_defaults() {
        const frm = this.frm;
        // Điền giá trị mặc định từ user settings
        frappe.db.get_value("User", frappe.session.user, "custom_default_sales_region")
            .then(r => {
                if (r.message && r.message.custom_default_sales_region) {
                    frm.set_value("custom_sales_region", r.message.custom_default_sales_region);
                }
            });
    }

    // ------------------------------------------------------------------ //
    // REFRESH — Buttons và trạng thái UI                                   //
    // ------------------------------------------------------------------ //

    refresh(doc) {
        super.refresh();
        this._add_custom_buttons();
        this._update_custom_indicators();
        this._toggle_custom_sections();
    }

    _add_custom_buttons() {
        const { doc } = this.frm;
        const me = this;

        // Nút tạo Commission Note
        if (
            doc.docstatus === 1
            && doc.custom_commission_amount > 0
            && !doc.custom_commission_je
        ) {
            this.frm.add_custom_button(
                __("Commission Note"),
                () => me.make_commission_note(),
                __("Create")
            );
        }

        // Nút VAT Declaration (chỉ cuối quý)
        if (doc.docstatus === 1 && this._is_quarter_end(doc.posting_date)) {
            this.frm.add_custom_button(
                __("VAT Declaration"),
                () => me.make_vat_declaration(),
                __("Create")
            );
        }

        // Nút lấy items từ Contract (chỉ draft)
        if (doc.docstatus === 0 && doc.customer) {
            this.frm.add_custom_button(
                __("From Contract"),
                () => me._get_items_from_contract(),
                __("Get Items From")
            );
        }

        // Nút phê duyệt (draft, người quản lý)
        if (
            doc.docstatus === 0
            && doc.custom_requires_director_approval
            && !doc.custom_board_approval_ref
            && frappe.user.has_role("Sales Manager")
        ) {
            this.frm.add_custom_button(
                __("Approve Invoice"),
                () => me._show_approval_dialog(),
                __("Actions")
            );
        }
    }

    _update_custom_indicators() {
        const { doc } = this.frm;
        if (!doc.name) return;

        // Indicator màu đỏ nếu cần phê duyệt nhưng chưa phê duyệt
        if (doc.custom_requires_director_approval && !doc.custom_board_approval_ref) {
            this.frm.dashboard.add_comment(
                __("Awaiting Director Approval"),
                "red",
                true
            );
        }

        // Indicator budget warning
        if (doc.custom_budget_warning) {
            this.frm.dashboard.add_comment(
                __("Budget limit approaching for this customer"),
                "yellow",
                true
            );
        }
    }

    _toggle_custom_sections() {
        const { doc } = this.frm;

        // Hiện/ẩn section commission
        this.frm.set_df_property(
            "custom_commission_section", "hidden",
            !doc.custom_has_commission
        );

        // Hiện/ẩn section contract
        this.frm.set_df_property(
            "custom_contract_section", "hidden",
            !doc.custom_contract
        );
    }

    // ------------------------------------------------------------------ //
    // TRIGGERS — Override các trigger từ parent                            //
    // ------------------------------------------------------------------ //

    // Override customer trigger
    customer() {
        // Gọi parent (lấy party details, price list, payment terms...)
        super.customer();

        // Thêm custom logic sau
        const me = this;
        const customer = this.frm.doc.customer;
        if (!customer) return;

        frappe.db.get_value(
            "Customer", customer,
            ["custom_commission_rate", "custom_default_contract", "custom_sales_region"],
        ).then(r => {
            if (!r.message) return;
            const { custom_commission_rate, custom_default_contract, custom_sales_region } = r.message;

            if (custom_commission_rate) {
                me.frm.set_value("custom_commission_rate", custom_commission_rate);
            }
            if (custom_default_contract) {
                me.frm.set_value("custom_contract", custom_default_contract);
            }
            if (custom_sales_region) {
                me.frm.set_value("custom_sales_region", custom_sales_region);
            }
        });
    }

    // Trigger cho custom_commission_rate
    custom_commission_rate() {
        this._recalculate_commission();
    }

    // Trigger cho custom_contract
    custom_contract() {
        const contract = this.frm.doc.custom_contract;
        if (!contract) return;

        frappe.db.get_value("Custom Contract", contract, "payment_terms").then(r => {
            if (r.message && r.message.payment_terms) {
                this.frm.set_value("payment_terms_template", r.message.payment_terms);
            }
        });
    }

    // ------------------------------------------------------------------ //
    // ACTIONS                                                              //
    // ------------------------------------------------------------------ //

    make_commission_note() {
        frappe.model.open_mapped_doc({
            method: "custom_app.mappers.sales_invoice_mapper.make_commission_note",
            frm: this.frm,
        });
    }

    make_vat_declaration() {
        frappe.model.open_mapped_doc({
            method: "custom_app.mappers.sales_invoice_mapper.make_vat_declaration",
            frm: this.frm,
        });
    }

    _get_items_from_contract() {
        const me = this;
        const frm = this.frm;

        new frappe.ui.Dialog({
            title: __("Get Items from Contract"),
            fields: [
                {
                    fieldname: "contract",
                    fieldtype: "Link",
                    options: "Custom Contract",
                    label: __("Contract"),
                    reqd: 1,
                    default: frm.doc.custom_contract,
                    get_query: () => ({
                        filters: {
                            customer: frm.doc.customer,
                            status: "Active",
                        },
                    }),
                },
                {
                    fieldname: "clear_existing",
                    fieldtype: "Check",
                    label: __("Clear Existing Items"),
                    default: 0,
                },
            ],
            primary_action_label: __("Fetch Items"),
            primary_action(values) {
                frappe.call({
                    method: "custom_app.api.get_contract_items",
                    args: { contract: values.contract },
                    callback(r) {
                        if (!r.message) return;

                        if (values.clear_existing) {
                            frm.clear_table("items");
                        }

                        r.message.forEach(item => {
                            const row = frm.add_child("items");
                            frappe.model.set_value(row.doctype, row.name, {
                                item_code: item.item_code,
                                qty: item.qty,
                                rate: item.rate,
                                custom_contract_item: item.name,
                                custom_contract: values.contract,
                            });
                        });

                        frm.refresh_field("items");
                        frm.set_value("custom_contract", values.contract);
                        me.calculate_taxes_and_totals();
                    },
                });
                this.hide();
            },
        }).show();
    }

    _show_approval_dialog() {
        const me = this;
        new frappe.ui.Dialog({
            title: __("Director Approval"),
            fields: [
                {
                    fieldname: "approval_ref",
                    fieldtype: "Data",
                    label: __("Approval Reference Number"),
                    reqd: 1,
                },
                {
                    fieldname: "approval_remarks",
                    fieldtype: "Small Text",
                    label: __("Approval Remarks"),
                },
            ],
            primary_action_label: __("Confirm Approval"),
            primary_action(values) {
                me.frm.set_value("custom_board_approval_ref", values.approval_ref);
                me.frm.set_value("custom_approval_remarks", values.approval_remarks);
                me.frm.save();
                this.hide();
            },
        }).show();
    }

    // ------------------------------------------------------------------ //
    // HELPERS                                                              //
    // ------------------------------------------------------------------ //

    _recalculate_commission() {
        const doc = this.frm.doc;
        if (doc.custom_commission_rate && doc.net_total) {
            const commission = frappe.utils.flt(
                doc.net_total * doc.custom_commission_rate / 100,
                precision("custom_commission_amount")
            );
            this.frm.set_value("custom_commission_amount", commission);
        }
    }

    _on_contract_item_change(cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.custom_contract_item) return;

        frappe.db.get_value(
            "Custom Contract Item", row.custom_contract_item,
            ["remaining_qty", "rate"]
        ).then(r => {
            if (!r.message) return;
            frappe.model.set_value(cdt, cdn, {
                custom_available_qty: r.message.remaining_qty,
            });
            if (!row.rate) {
                frappe.model.set_value(cdt, cdn, "rate", r.message.rate);
            }
        });
    }

    _is_quarter_end(date_str) {
        if (!date_str) return false;
        const month = frappe.datetime.str_to_obj(date_str).getMonth() + 1;
        return [3, 6, 9, 12].includes(month);
    }
};


// ---- Đăng ký Controller ---- //
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        frm.cscript = new custom_app.accounts.CustomSalesInvoiceController({ frm });
    },
});
```

### 10.2 Kế thừa PurchaseInvoiceController

```javascript
// custom_app/public/js/custom_purchase_invoice.js

frappe.provide("custom_app.buying");

custom_app.buying.CustomPurchaseInvoiceController = class CustomPurchaseInvoiceController
    extends erpnext.accounts.PurchaseInvoice {

    setup(doc) {
        super.setup(doc);
        this._setup_budget_queries();
    }

    refresh(doc) {
        super.refresh();
        this._add_budget_indicator();
        this._add_approval_button();
    }

    supplier() {
        super.supplier();
        this._load_vendor_classification();
    }

    _setup_budget_queries() {
        this.frm.set_query("custom_department_budget", () => ({
            filters: {
                company: this.frm.doc.company,
                fiscal_year: frappe.sys_defaults.fiscal_year,
                status: "Active",
            },
        }));
    }

    _add_budget_indicator() {
        const { doc } = this.frm;
        if (!doc.custom_department_budget) return;

        frappe.call({
            method: "custom_app.api.get_budget_usage",
            args: { budget: doc.custom_department_budget },
            callback: r => {
                if (!r.message) return;
                const { used_pct, available } = r.message;
                const color = used_pct > 90 ? "red" : used_pct > 70 ? "yellow" : "green";
                this.frm.dashboard.add_comment(
                    __("Budget Used: {0}% | Available: {1}", [used_pct, format_currency(available)]),
                    color,
                    true
                );
            },
        });
    }

    _add_approval_button() {
        const { doc } = this.frm;
        if (
            doc.docstatus === 0
            && doc.custom_approval_required
            && !doc.custom_approved_by
            && frappe.user.has_role("Purchase Manager")
        ) {
            this.frm.add_custom_button(__("Approve"), () => {
                this.frm.set_value("custom_approved_by", frappe.session.user);
                this.frm.set_value("custom_approval_date", frappe.datetime.now_date());
                this.frm.save();
            }, __("Actions"));
        }
    }

    _load_vendor_classification() {
        const supplier = this.frm.doc.supplier;
        if (!supplier) return;

        frappe.db.get_value(
            "Supplier", supplier,
            ["custom_vendor_tier", "custom_payment_priority"]
        ).then(r => {
            if (r.message) {
                this.frm.set_value("custom_vendor_tier", r.message.custom_vendor_tier);
            }
        });
    }
};

frappe.ui.form.on("Purchase Invoice", {
    setup(frm) {
        frm.cscript = new custom_app.buying.CustomPurchaseInvoiceController({ frm });
    },
});
```

---

## 11. JavaScript — Extend Không Override

Cách an toàn nhất — không thay thế controller, chỉ thêm handlers.

```javascript
// custom_app/public/js/sales_invoice_extensions.js
// Không cần kế thừa — chỉ dùng frappe.ui.form.on()

// ---- Document-level triggers ---- //
frappe.ui.form.on("Sales Invoice", {

    // Chạy sau khi controller.refresh()
    refresh(frm) {
        _add_custom_buttons(frm);
        _update_budget_indicator(frm);
    },

    // Chạy sau khi controller.validate() (thực ra là after_save trigger phía client)
    // Để validate: dùng before_save hoặc Python hooks
    before_save(frm) {
        _client_side_validate(frm);
    },

    // Custom field triggers
    custom_commission_rate(frm) {
        _recalculate_commission(frm);
    },

    custom_contract(frm) {
        _on_contract_change(frm);
    },

    custom_has_commission(frm) {
        frm.set_df_property("custom_commission_section", "hidden", !frm.doc.custom_has_commission);
        frm.refresh_fields();
    },

    // Company trigger (thêm vào, không thay thế)
    company(frm) {
        // company trigger của parent đã chạy trước đây
        _load_company_custom_settings(frm);
    },
});

// ---- Child table triggers ---- //
frappe.ui.form.on("Sales Invoice Item", {
    custom_surcharge_rate(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const surcharge = frappe.utils.flt(
            row.amount * row.custom_surcharge_rate / 100,
            frappe.meta.get_field("Sales Invoice Item", "custom_surcharge_amount")?.precision || 2
        );
        frappe.model.set_value(cdt, cdn, "custom_surcharge_amount", surcharge);
        frm.cscript.calculate_taxes_and_totals();
    },

    custom_contract_item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.custom_contract_item) return;

        frappe.db.get_value(
            "Custom Contract Item",
            row.custom_contract_item,
            ["remaining_qty"]
        ).then(r => {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, "custom_available_qty", r.message.remaining_qty);
            }
        });
    },

    // Override item_code trigger để thêm logic sau khi item được chọn
    item_code(frm, cdt, cdn) {
        // item_code trigger của parent đã chạy — đây chạy SAU
        // (frappe.ui.form.on handlers chạy theo thứ tự đăng ký)
        const row = locals[cdt][cdn];
        if (!row.item_code) return;

        frappe.db.get_value("Item", row.item_code, "custom_vat_category").then(r => {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, "custom_vat_category", r.message.custom_vat_category);
            }
        });
    },
});


// ---- Helper functions ---- //

function _add_custom_buttons(frm) {
    const doc = frm.doc;

    if (doc.docstatus === 1 && doc.custom_commission_amount > 0 && !doc.custom_commission_je) {
        frm.add_custom_button(__("Commission Note"), () => {
            frappe.model.open_mapped_doc({
                method: "custom_app.mappers.sales_invoice_mapper.make_commission_note",
                frm,
            });
        }, __("Create"));
    }
}

function _update_budget_indicator(frm) {
    if (!frm.doc.customer || frm.doc.docstatus !== 0) return;

    frappe.call({
        method: "custom_app.api.check_customer_credit_custom",
        args: {
            customer: frm.doc.customer,
            amount: frm.doc.grand_total || 0,
        },
        callback(r) {
            if (r.message && r.message.warning) {
                frm.dashboard.add_comment(r.message.warning, "yellow", true);
            }
        },
    });
}

function _recalculate_commission(frm) {
    const rate = flt(frm.doc.custom_commission_rate);
    const net = flt(frm.doc.net_total);
    if (rate && net) {
        frm.set_value(
            "custom_commission_amount",
            frappe.utils.flt(net * rate / 100, precision("custom_commission_amount", frm.doc))
        );
    }
}

function _on_contract_change(frm) {
    const contract = frm.doc.custom_contract;
    if (!contract) return;

    frappe.db.get_value("Custom Contract", contract, ["payment_terms", "currency"]).then(r => {
        if (!r.message) return;
        if (r.message.payment_terms) frm.set_value("payment_terms_template", r.message.payment_terms);
        if (r.message.currency && r.message.currency !== frm.doc.currency) {
            frappe.msgprint(__("Contract currency {0} differs from invoice currency", [r.message.currency]));
        }
    });
}

function _load_company_custom_settings(frm) {
    if (!frm.doc.company) return;
    frappe.db.get_value("Company", frm.doc.company, "custom_default_commission_rate").then(r => {
        if (r.message && r.message.custom_default_commission_rate && !frm.doc.custom_commission_rate) {
            frm.set_value("custom_commission_rate", r.message.custom_default_commission_rate);
        }
    });
}

function _client_side_validate(frm) {
    // Chỉ chạy client-side validation nhẹ — validation nghiêm túc phải trên Python
    if (frm.doc.custom_commission_rate > 30) {
        frappe.msgprint({
            title: __("High Commission Rate"),
            message: __("Commission rate above 30% requires manager approval."),
            indicator: "orange",
        });
    }
}
```

---

## 12. JavaScript — Override taxes_and_totals.js

```javascript
// custom_app/public/js/custom_taxes_and_totals.js

// Mở rộng class taxes_and_totals
// Cách 1: Monkey-patch method (nhanh, ít phức tạp)
const _original_calculate = erpnext.taxes_and_totals.prototype.calculate_taxes_and_totals;

erpnext.taxes_and_totals.prototype.calculate_taxes_and_totals = function() {
    // Gọi original
    _original_calculate.call(this);

    // Sau đó tính thêm custom charges
    _calculate_custom_charges.call(this);
    _calculate_environmental_levy.call(this);
};

function _calculate_custom_charges() {
    const doc = this.frm.doc;
    if (!doc.custom_charge_handling) return;

    const total_weight = (doc.items || []).reduce((sum, item) => {
        return sum + frappe.utils.flt(item.total_weight || item.weight_per_unit * item.qty);
    }, 0);

    const rate_per_kg = doc.custom_handling_rate_per_kg || 500;
    frappe.model.set_value(
        doc.doctype, doc.name,
        "custom_handling_charge",
        frappe.utils.flt(total_weight * rate_per_kg, precision("custom_handling_charge", doc))
    );
}

function _calculate_environmental_levy() {
    const doc = this.frm.doc;
    const levy_items = (doc.items || []).filter(item => item.custom_has_environmental_levy);
    const levy = levy_items.reduce((sum, item) => sum + item.amount * 0.005, 0);

    frappe.model.set_value(
        doc.doctype, doc.name,
        "custom_environmental_levy",
        frappe.utils.flt(levy, precision("custom_environmental_levy", doc))
    );
}


// Cách 2: Subclass (kiểm soát tốt hơn, dùng khi cần override nhiều methods)
const OriginalTaxesAndTotals = erpnext.taxes_and_totals;

class CustomTaxesAndTotals extends OriginalTaxesAndTotals {

    calculate_taxes_and_totals() {
        super.calculate_taxes_and_totals();
        this._calculate_custom_total();
    }

    calculate_item_values() {
        super.calculate_item_values();
        // Thêm custom item calculations
        this._apply_custom_discounts();
    }

    _apply_custom_discounts() {
        (this.frm.doc.items || []).forEach(item => {
            if (item.custom_loyalty_discount) {
                const discounted = item.rate * (1 - item.custom_loyalty_discount / 100);
                frappe.model.set_value(
                    item.doctype, item.name,
                    "rate", frappe.utils.flt(discounted, precision("rate", item))
                );
            }
        });
    }

    _calculate_custom_total() {
        const doc = this.frm.doc;
        const custom_total = frappe.utils.flt(doc.grand_total)
            + frappe.utils.flt(doc.custom_handling_charge)
            + frappe.utils.flt(doc.custom_environmental_levy);

        frappe.model.set_value(
            doc.doctype, doc.name,
            "custom_payable_total",
            frappe.utils.flt(custom_total, precision("custom_payable_total", doc))
        );
    }
}

// Thay thế class gốc
erpnext.taxes_and_totals = CustomTaxesAndTotals;
```

---

## 13. JavaScript — Tích hợp Toàn Hệ thống

```javascript
// custom_app/public/js/global_hooks.js
// File này được load cho TẤT CẢ doctypes

frappe.provide("custom_app.global");

// ---- Hook vào tất cả form.refresh ---- //
$(document).on("form-refresh", function(event, frm) {
    custom_app.global.on_form_refresh(frm);
});

// ---- Hook vào tất cả form.save ---- //
$(document).on("form-save", function(event, frm) {
    custom_app.global.on_form_save(frm);
});

custom_app.global = {

    ACCOUNTING_DOCTYPES: [
        "Sales Invoice", "Purchase Invoice", "Payment Entry",
        "Journal Entry", "Delivery Note", "Purchase Receipt",
    ],

    on_form_refresh(frm) {
        // Thêm audit info indicator cho accounting doctypes
        if (this.ACCOUNTING_DOCTYPES.includes(frm.doctype)) {
            this.add_audit_info(frm);
        }
        // Thêm company logo vào header
        this.set_company_branding(frm);
    },

    on_form_save(frm) {
        // Auto-fill trường không có trong validate
    },

    add_audit_info(frm) {
        if (!frm.doc.name || frm.doc.name.startsWith("new-")) return;

        frappe.call({
            method: "custom_app.api.get_audit_summary",
            args: { doctype: frm.doctype, docname: frm.doc.name },
            callback(r) {
                if (r.message && r.message.last_modified_by) {
                    frm.dashboard.add_comment(
                        __("Last modified by {0} on {1}", [
                            r.message.last_modified_by,
                            frappe.datetime.str_to_user(r.message.last_modified),
                        ]),
                        "grey",
                        false // không sticky
                    );
                }
            },
        });
    },

    set_company_branding(frm) {
        if (!frm.doc.company) return;
        frappe.db.get_value("Company", frm.doc.company, "custom_brand_color").then(r => {
            if (r.message && r.message.custom_brand_color) {
                // Áp dụng brand color vào form header
                $(frm.wrapper).find(".form-page").css(
                    "border-top", `3px solid ${r.message.custom_brand_color}`
                );
            }
        });
    },
};


// ---- Override frappe.msgprint toàn hệ thống ---- //
// (Ví dụ: log tất cả error messages)
const _original_msgprint = frappe.msgprint.bind(frappe);
frappe.msgprint = function(opts) {
    if (typeof opts === "object" && opts.indicator === "red") {
        // Log errors tới analytics
        custom_app.global.log_client_error(opts);
    }
    return _original_msgprint(opts);
};

custom_app.global.log_client_error = function(opts) {
    frappe.call({
        method: "custom_app.api.log_client_error",
        args: {
            message: opts.message || opts,
            title: opts.title || "",
            route: frappe.get_route_str(),
        },
        // Không show callback errors (tránh vòng lặp)
    });
};
```

### 13.1 Đăng ký Global JS trong hooks.py

```python
# custom_app/hooks.py

app_include_js = [
    "/assets/custom_app/js/global_hooks.js",
    "/assets/custom_app/js/custom_taxes_and_totals.js",
]

app_include_css = [
    "/assets/custom_app/css/custom_theme.css",
]

# JS chỉ cho specific doctypes
doctype_js = {
    "Sales Invoice":     "public/js/custom_sales_invoice.js",
    "Purchase Invoice":  "public/js/custom_purchase_invoice.js",
}

# Hoặc dùng doctype_list_js cho list view
doctype_list_js = {
    "Sales Invoice": "public/js/sales_invoice_list.js",
}
```

---

## 14. Pattern Tích hợp Đầy đủ

Ví dụ end-to-end: **Tính năng "Commission Tracking"** — từ validate → GL → UI.

### 14.1 Python backend

```python
# custom_app/hooks.py

doc_events = {
    "Sales Invoice": {
        "validate":  "custom_app.features.commission.validate",
        "on_submit": "custom_app.features.commission.on_submit",
        "on_cancel": "custom_app.features.commission.on_cancel",
    }
}

override_doctype_class = {
    "Sales Invoice": "custom_app.features.commission.CommissionSalesInvoice",
}
```

```python
# custom_app/features/commission.py

import frappe
from frappe.utils import flt
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice


# ---- DocClass Override ---- #

class CommissionSalesInvoice(SalesInvoice):

    def get_gl_entries(self, inventory_account_map=None):
        gl_entries = super().get_gl_entries(inventory_account_map)
        gl_entries += _build_commission_gl_entries(self)
        return gl_entries


# ---- Hook Functions ---- #

def validate(doc, method):
    _calculate_commission(doc)
    _validate_commission_agent(doc)

def on_submit(doc, method):
    _create_commission_record(doc)

def on_cancel(doc, method):
    _cancel_commission_record(doc)


# ---- Business Logic ---- #

def _calculate_commission(doc):
    rate = flt(doc.get("custom_commission_rate"))
    if rate:
        doc.custom_commission_amount = flt(
            doc.net_total * rate / 100,
            doc.precision("custom_commission_amount")
        )

def _validate_commission_agent(doc):
    if flt(doc.get("custom_commission_amount")) > 0 and not doc.get("custom_commission_agent"):
        frappe.throw(frappe._("Commission Agent is required when commission amount is set"))

def _create_commission_record(doc):
    commission = flt(doc.get("custom_commission_amount"))
    if not commission:
        return

    record = frappe.new_doc("Custom Commission Record")
    record.update({
        "sales_invoice": doc.name,
        "agent": doc.custom_commission_agent,
        "amount": commission,
        "posting_date": doc.posting_date,
        "status": "Pending",
    })
    record.flags.ignore_permissions = True
    record.insert()
    frappe.db.set_value("Sales Invoice", doc.name, "custom_commission_record", record.name)

def _cancel_commission_record(doc):
    record_name = doc.get("custom_commission_record")
    if record_name and frappe.db.exists("Custom Commission Record", record_name):
        frappe.db.set_value("Custom Commission Record", record_name, "status", "Cancelled")

def _build_commission_gl_entries(doc):
    commission = flt(doc.get("custom_commission_amount"))
    if not commission or not doc.get("custom_commission_agent"):
        return []

    expense_acct = frappe.get_cached_value("Company", doc.company, "custom_commission_expense_account")
    payable_acct = frappe.get_cached_value("Company", doc.company, "custom_commission_payable_account")

    if not expense_acct or not payable_acct:
        return []

    return [
        doc.get_gl_dict({
            "account": expense_acct,
            "debit": commission,
            "debit_in_account_currency": commission,
            "against": payable_acct,
            "remarks": f"Commission — {doc.custom_commission_agent}",
            "cost_center": doc.cost_center,
        }),
        doc.get_gl_dict({
            "account": payable_acct,
            "credit": commission,
            "credit_in_account_currency": commission,
            "against": expense_acct,
            "party_type": "Supplier",
            "party": doc.custom_commission_agent,
            "remarks": f"Commission — {doc.custom_commission_agent}",
        }),
    ]
```

### 14.2 JavaScript frontend

```javascript
// custom_app/public/js/features/commission.js

frappe.ui.form.on("Sales Invoice", {
    // Tự động tính lại commission khi rate hoặc net_total thay đổi
    custom_commission_rate(frm) {
        _recalculate_commission(frm);
    },

    // Cập nhật sau khi calculate_taxes_and_totals chạy
    // (net_total thay đổi)
    after_save(frm) {
        // Hiện commission summary
        if (frm.doc.docstatus === 1 && frm.doc.custom_commission_amount) {
            _show_commission_summary(frm);
        }
    },

    refresh(frm) {
        _render_commission_ui(frm);
    },
});

// Khi net_total thay đổi (listen từ form event)
$(document).on("form-refresh", (event, frm) => {
    if (frm.doctype !== "Sales Invoice") return;
    if (frm.doc.custom_commission_rate && frm.doc.net_total) {
        _recalculate_commission(frm);
    }
});

function _recalculate_commission(frm) {
    const rate = flt(frm.doc.custom_commission_rate);
    const net = flt(frm.doc.net_total);
    if (rate && net) {
        frm.set_value(
            "custom_commission_amount",
            frappe.utils.flt(net * rate / 100, precision("custom_commission_amount", frm.doc))
        );
    }
}

function _render_commission_ui(frm) {
    const { doc } = frm;

    // Toggle section
    frm.set_df_property(
        "custom_commission_section", "hidden",
        !doc.custom_has_commission
    );

    // Nút thanh toán commission
    if (
        doc.docstatus === 1
        && doc.custom_commission_record
        && doc.custom_commission_amount > 0
    ) {
        frappe.db.get_value(
            "Custom Commission Record",
            doc.custom_commission_record,
            "status"
        ).then(r => {
            if (r.message && r.message.status === "Pending") {
                frm.add_custom_button(__("Pay Commission"), () => {
                    _pay_commission(frm);
                }, __("Actions"));
            }
        });
    }
}

function _show_commission_summary(frm) {
    const amount = frappe.format(frm.doc.custom_commission_amount, { fieldtype: "Currency" });
    const agent = frm.doc.custom_commission_agent;
    frm.dashboard.add_comment(
        __("Commission of {0} pending for {1}", [amount, agent]),
        "blue",
        true
    );
}

function _pay_commission(frm) {
    frappe.confirm(
        __("Create payment for commission of {0}?",
            [frappe.format(frm.doc.custom_commission_amount, { fieldtype: "Currency" })]),
        () => {
            frappe.call({
                method: "custom_app.api.create_commission_payment",
                args: { invoice: frm.doc.name },
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({ message: __("Commission payment created"), indicator: "green" });
                        frm.reload_doc();
                    }
                },
            });
        }
    );
}
```

---

## 15. Tạo Custom DocType Mới

### 15.1 DocType kế thừa AccountsController

```python
# custom_app/doctype/subscription_invoice/subscription_invoice.py

import frappe
from frappe.utils import flt, add_months, today
from erpnext.controllers.accounts_controller import AccountsController


class SubscriptionInvoice(AccountsController):
    """
    Hóa đơn đăng ký dịch vụ — DocType mới hoàn toàn kế thừa AccountsController.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Status updater cho Subscription
        self.status_updater = [{
            "source_dt": "Subscription Invoice Item",
            "target_dt": "Subscription Item",
            "join_field": "subscription_item",
            "target_field": "billed_amount",
            "target_ref_field": "amount",
            "source_field": "amount",
            "target_parent_dt": "Subscription",
            "target_parent_field": "per_billed",
            "percent_join_field": "subscription",
            "overflow_type": "billing",
        }]

    def validate(self):
        self._set_subscription_dates()
        self._validate_subscription_active()
        super().validate()          # Gọi AccountsController.validate()
        self._calculate_recurring_total()

    def _set_subscription_dates(self):
        if not self.get("billing_period_start"):
            self.billing_period_start = today()
        if not self.get("billing_period_end"):
            self.billing_period_end = add_months(self.billing_period_start, 1)

    def _validate_subscription_active(self):
        for item in self.items:
            if item.get("subscription"):
                status = frappe.db.get_value("Subscription", item.subscription, "status")
                if status not in ("Active", "Past Due"):
                    frappe.throw(
                        frappe._(f"Subscription {item.subscription} is {status}, cannot invoice")
                    )

    def _calculate_recurring_total(self):
        self.recurring_total = sum(
            flt(item.amount) for item in self.items
            if item.get("is_recurring")
        )

    def on_submit(self):
        self._check_approvals()
        self.make_gl_entries()
        self.update_prevdoc_status()
        self._schedule_next_billing()

    def _check_approvals(self):
        if self.grand_total > 50_000_000 and not self.get("approved_by"):
            frappe.throw(frappe._("Subscription Invoice above 50M requires approval"))

    def make_gl_entries(self, cancel=False):
        from custom_app.services.subscription_gl_composer import SubscriptionGLComposer
        gl_map = SubscriptionGLComposer(self).compose()

        from erpnext.accounts.general_ledger import make_gl_entries
        make_gl_entries(gl_map, cancel=cancel, merge_entries=False)

    def _schedule_next_billing(self):
        """Lên lịch kỳ hóa đơn tiếp theo cho subscription."""
        for item in self.items:
            if item.get("subscription") and item.get("is_recurring"):
                next_date = add_months(self.billing_period_end, 1)
                frappe.db.set_value(
                    "Subscription", item.subscription, "next_invoice_date", next_date
                )

    def on_cancel(self):
        self.make_gl_entries(cancel=True)
        self.update_prevdoc_status()
        self._unschedule_billing()

    def _unschedule_billing(self):
        for item in self.items:
            if item.get("subscription"):
                frappe.db.set_value(
                    "Subscription", item.subscription,
                    "next_invoice_date", self.billing_period_start
                )

    def get_gl_dict(self, args, account_currency=None, item=None):
        """Thêm billing_period vào mọi GL entry."""
        gl_dict = super().get_gl_dict(args, account_currency, item)
        gl_dict["custom_billing_period"] = (
            f"{self.billing_period_start} to {self.billing_period_end}"
        )
        return gl_dict
```

### 15.2 JSON DocType (trích đoạn cấu trúc)

```json
{
    "doctype": "DocType",
    "name": "Subscription Invoice",
    "module": "Custom App",
    "is_submittable": 1,
    "track_changes": 1,
    "fields": [
        {
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 1
        },
        {
            "fieldname": "debit_to",
            "fieldtype": "Link",
            "options": "Account",
            "reqd": 1
        },
        {
            "fieldname": "billing_period_start",
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "billing_period_end",
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "items",
            "fieldtype": "Table",
            "options": "Subscription Invoice Item",
            "reqd": 1
        },
        {
            "fieldname": "taxes",
            "fieldtype": "Table",
            "options": "Sales Taxes and Charges"
        }
    ],
    "permissions": [
        {
            "role": "Accounts User",
            "read": 1,
            "write": 1,
            "create": 1,
            "submit": 1,
            "cancel": 1
        }
    ]
}
```

---

## 16. Whitelist API & Server-side Endpoints

```python
# custom_app/api.py

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_contract_items(contract):
    """Lấy items từ Custom Contract."""
    frappe.has_permission("Custom Contract", "read", contract, throw=True)

    items = frappe.get_all(
        "Custom Contract Item",
        filters={"parent": contract, "remaining_qty": [">", 0]},
        fields=["name", "item_code", "item_name", "qty", "remaining_qty", "rate", "uom"],
        order_by="idx asc"
    )
    return items


@frappe.whitelist()
def check_customer_credit_custom(customer, amount):
    """Kiểm tra hạn mức tín dụng custom."""
    frappe.has_permission("Customer", "read", customer, throw=True)

    credit_limit = frappe.db.get_value("Customer", customer, "custom_credit_limit") or 0
    outstanding = _get_customer_outstanding(customer)
    amount = flt(amount)

    available = flt(credit_limit) - flt(outstanding)
    warning = None

    if credit_limit and (outstanding + amount) > credit_limit:
        warning = frappe._(
            f"Customer credit limit exceeded. Limit: {credit_limit:,.0f}, "
            f"Outstanding: {outstanding:,.0f}, This Invoice: {amount:,.0f}"
        )
    elif credit_limit and (outstanding + amount) > credit_limit * 0.9:
        warning = frappe._(
            f"Customer credit limit at {((outstanding+amount)/credit_limit*100):.0f}%. "
            f"Available: {available:,.0f}"
        )

    return {
        "credit_limit": credit_limit,
        "outstanding": outstanding,
        "available": available,
        "warning": warning,
    }


@frappe.whitelist()
def create_commission_payment(invoice):
    """Tạo Payment Entry cho hoa hồng."""
    frappe.has_permission("Sales Invoice", "submit", invoice, throw=True)

    doc = frappe.get_doc("Sales Invoice", invoice)
    if not doc.get("custom_commission_amount") or not doc.get("custom_commission_agent"):
        frappe.throw(frappe._("No commission configured on this invoice"))

    commission_record = doc.get("custom_commission_record")
    if commission_record:
        status = frappe.db.get_value("Custom Commission Record", commission_record, "status")
        if status == "Paid":
            frappe.throw(frappe._("Commission already paid"))

    pe = frappe.new_doc("Payment Entry")
    pe.update({
        "payment_type": "Pay",
        "party_type": "Supplier",
        "party": doc.custom_commission_agent,
        "paid_amount": doc.custom_commission_amount,
        "received_amount": doc.custom_commission_amount,
        "paid_from": frappe.get_cached_value(
            "Company", doc.company, "custom_commission_payable_account"
        ),
        "paid_to": frappe.get_cached_value(
            "Company", doc.company, "default_bank_account"
        ),
        "reference_no": f"COMM-{invoice}",
        "reference_date": frappe.utils.today(),
    })
    pe.flags.ignore_permissions = True
    pe.insert()
    pe.submit()

    # Cập nhật commission record
    if commission_record:
        frappe.db.set_value("Custom Commission Record", commission_record, {
            "status": "Paid",
            "payment_entry": pe.name,
        })

    return pe.name


@frappe.whitelist()
def get_budget_usage(budget):
    """Thống kê sử dụng ngân sách."""
    frappe.has_permission("Custom Department Budget", "read", budget, throw=True)

    budget_doc = frappe.get_doc("Custom Department Budget", budget)

    used = frappe.db.sql("""
        SELECT COALESCE(SUM(pii.amount), 0) as total
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.custom_department_budget = %s
          AND pi.docstatus = 1
    """, budget)[0][0]

    available = flt(budget_doc.budget_amount) - flt(used)

    return {
        "budget_amount": budget_doc.budget_amount,
        "used_amount": used,
        "available": available,
        "used_pct": flt(used / budget_doc.budget_amount * 100, 1) if budget_doc.budget_amount else 0,
    }


@frappe.whitelist()
def get_audit_summary(doctype, docname):
    """Lấy thông tin audit."""
    frappe.has_permission(doctype, "read", docname, throw=True)
    doc_info = frappe.db.get_value(
        doctype, docname,
        ["modified_by", "modified"],
        as_dict=True
    )
    return {
        "last_modified_by": doc_info.modified_by if doc_info else None,
        "last_modified": str(doc_info.modified) if doc_info else None,
    }


@frappe.whitelist()
def log_client_error(message, title="", route=""):
    """Log lỗi từ client side."""
    frappe.log_error(
        message=f"[Client] Route: {route}\nTitle: {title}\nMessage: {message}",
        title="Client Error Log"
    )


def _get_customer_outstanding(customer):
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(outstanding_amount), 0)
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
    """, customer)
    return flt(result[0][0] if result else 0)
```

---

## 17. Document Mapper

```python
# custom_app/mappers/sales_invoice_mapper.py

import frappe
from frappe.model.mapper import get_mapped_doc


@frappe.whitelist()
def make_commission_note(source_name, target_doc=None):
    """
    Tạo Commission Note từ Sales Invoice.
    JS gọi: frappe.model.open_mapped_doc({ method: "...make_commission_note", frm })
    """
    def set_missing_values(source, target):
        target.commission_date = frappe.utils.today()
        target.fiscal_year = frappe.defaults.get_user_default("fiscal_year")

    def condition(obj):
        # Chỉ map nếu có commission
        return bool(obj.get("custom_commission_amount"))

    def postprocess(source, source_parent, target_parent, target):
        # Bổ sung thông tin sau map
        pass

    return get_mapped_doc(
        "Sales Invoice",
        source_name,
        {
            "Sales Invoice": {
                "doctype": "Custom Commission Note",
                "field_map": {
                    "name":                     "source_invoice",
                    "customer":                 "customer",
                    "posting_date":             "invoice_date",
                    "custom_commission_agent":  "agent",
                    "custom_commission_amount": "commission_amount",
                    "company":                  "company",
                },
                "field_no_map": [
                    "name", "amended_from",
                ],
                "condition": condition,
            },
        },
        target_doc,
        set_missing_values,
        ignore_permissions=False,
    )


@frappe.whitelist()
def make_vat_declaration(source_name, target_doc=None):
    """Tạo VAT Declaration từ Sales Invoice."""
    def set_missing_values(source, target):
        date = frappe.utils.getdate(source.posting_date)
        quarter = (date.month - 1) // 3 + 1
        target.period = f"Q{quarter}/{date.year}"
        target.declaration_type = "Output VAT"

    return get_mapped_doc(
        "Sales Invoice",
        source_name,
        {
            "Sales Invoice": {
                "doctype": "Custom VAT Declaration",
                "field_map": {
                    "name":            "source_voucher",
                    "posting_date":    "posting_date",
                    "customer":        "party",
                    "net_total":       "taxable_amount",
                    "custom_total_vat":"vat_amount",
                    "company":         "company",
                },
            },
            "Sales Invoice Item": {
                "doctype": "Custom VAT Declaration Item",
                "field_map": {
                    "item_code":          "item_code",
                    "item_name":          "item_name",
                    "net_amount":         "taxable_amount",
                    "custom_vat_amount":  "vat_amount",
                    "custom_vat_rate":    "vat_rate",
                },
            },
        },
        target_doc,
        set_missing_values,
    )
```

---

## 18. Cấu trúc Thư mục Chuẩn

```
custom_app/
│
├── hooks.py                           ← TRUNG TÂM: đăng ký tất cả
├── setup.py
├── requirements.txt
│
├── public/
│   ├── js/
│   │   ├── global_hooks.js            ← Load cho mọi page
│   │   ├── custom_taxes_and_totals.js ← Override tính toán
│   │   ├── features/
│   │   │   ├── commission.js          ← Feature-specific JS
│   │   │   └── vat.js
│   │   ├── custom_sales_invoice.js    ← SI controller
│   │   └── custom_purchase_invoice.js ← PI controller
│   └── css/
│       └── custom_theme.css
│
├── overrides/                         ← DocClass overrides
│   ├── __init__.py
│   ├── custom_sales_invoice.py
│   ├── custom_purchase_invoice.py
│   └── custom_accounts_controller.py
│
├── events/                            ← Hook functions
│   ├── __init__.py
│   ├── sales_invoice.py
│   ├── purchase_invoice.py
│   ├── gl_entry.py
│   └── global_events.py
│
├── services/                          ← Service layer
│   ├── __init__.py
│   ├── vat_service.py
│   ├── commission_service.py
│   ├── custom_si_gl_composer.py
│   └── custom_taxes_and_totals.py
│
├── mappers/                           ← Document mappers
│   ├── __init__.py
│   └── sales_invoice_mapper.py
│
├── api.py                             ← Whitelist API endpoints
│
└── doctype/                           ← Custom DocTypes
    ├── custom_commission_note/
    │   ├── custom_commission_note.py
    │   ├── custom_commission_note.js
    │   └── custom_commission_note.json
    ├── custom_vat_declaration/
    └── subscription_invoice/
```

---

## 19. hooks.py — Reference Đầy đủ

```python
# custom_app/hooks.py

from frappe import __version__ as frappe_version

app_name = "custom_app"
app_title = "Custom App"
app_publisher = "Your Company"
app_description = "Custom ERPNext extensions"
app_version = "1.0.0"

# ---- JS / CSS ---- #

app_include_js = [
    "/assets/custom_app/js/global_hooks.js",
    "/assets/custom_app/js/custom_taxes_and_totals.js",
]

app_include_css = [
    "/assets/custom_app/css/custom_theme.css",
]

doctype_js = {
    "Sales Invoice":     "public/js/custom_sales_invoice.js",
    "Purchase Invoice":  "public/js/custom_purchase_invoice.js",
}

doctype_list_js = {
    "Sales Invoice": "public/js/sales_invoice_list.js",
}

# ---- DocClass Override ---- #

override_doctype_class = {
    "Sales Invoice":    "custom_app.overrides.custom_sales_invoice.CustomSalesInvoice",
    "Purchase Invoice": "custom_app.overrides.custom_purchase_invoice.CustomPurchaseInvoice",
    # Subscription Invoice là DocType mới, không cần override
}

# ---- Doc Events (Hooks) ---- #

doc_events = {
    "Sales Invoice": {
        "before_insert":  "custom_app.events.sales_invoice.before_insert",
        "validate":       "custom_app.events.sales_invoice.validate",
        "before_submit":  "custom_app.events.sales_invoice.before_submit",
        "on_submit":      "custom_app.events.sales_invoice.on_submit",
        "on_cancel":      "custom_app.events.sales_invoice.on_cancel",
        "on_trash":       "custom_app.events.sales_invoice.on_trash",
    },
    "Purchase Invoice": {
        "validate":  "custom_app.events.purchase_invoice.validate",
        "on_submit": "custom_app.events.purchase_invoice.on_submit",
        "on_cancel": "custom_app.events.purchase_invoice.on_cancel",
    },
    "GL Entry": {
        "before_insert": "custom_app.events.gl_entry.before_insert",
    },
    "*": {
        "on_submit": "custom_app.events.global_events.on_any_submit",
        "on_cancel": "custom_app.events.global_events.on_any_cancel",
    },
}

# ---- Scheduled Tasks ---- #

scheduler_events = {
    "daily": [
        "custom_app.tasks.daily.process_pending_commissions",
        "custom_app.tasks.daily.send_budget_alerts",
    ],
    "monthly": [
        "custom_app.tasks.monthly.generate_vat_summary",
    ],
    "cron": {
        "0 8 * * 1": [  # Mỗi thứ Hai 8 giờ sáng
            "custom_app.tasks.weekly.send_commission_report",
        ]
    },
}

# ---- Fixtures (dữ liệu cài đặt) ---- #

fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["dt", "in", ["Sales Invoice", "Purchase Invoice", "Sales Invoice Item"]]],
    },
    {
        "doctype": "Property Setter",
        "filters": [["doc_type", "in", ["Sales Invoice", "Purchase Invoice"]]],
    },
    "Custom DocType",
    "Custom Commission Rate",
]

# ---- Override Whitelisted Methods ---- #

override_whitelisted_methods = {
    # Cẩn thận: override này ảnh hưởng toàn bộ hệ thống
    # "erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals":
    #     "custom_app.services.custom_taxes_and_totals.CustomTaxesAndTotals",
}

# ---- Permission Overrides ---- #

permission_query_conditions = {
    "Sales Invoice": "custom_app.permissions.sales_invoice_permission_query",
}

has_permission = {
    "Sales Invoice": "custom_app.permissions.has_permission_sales_invoice",
}

# ---- Boot Session ---- #

boot_session = "custom_app.boot.boot_session"

# ---- On Login ---- #

on_login = "custom_app.auth.on_login"
```

---

## 20. Checklist & Anti-patterns

### 20.1 Checklist trước khi deploy

```
Python:
  □ Mọi override class đều gọi super() đúng thứ tự
  □ on_cancel() đảo ngược toàn bộ on_submit() logic
  □ get_gl_entries() luôn gọi super() trước khi thêm entries
  □ GL entries luôn có cặp Debit = Credit
  □ Dùng frappe.db.set_value() thay vì doc.save() trong hooks để tránh triggers
  □ Tất cả DB queries dùng parameterized (%s), không format string
  □ Service classes có try/except hoặc fail gracefully
  □ Không import circular (services không import từ overrides)

JavaScript:
  □ Mọi controller override gọi super.setup(), super.refresh()
  □ Triggers không tạo infinite loop (set_value → trigger → set_value...)
  □ frappe.call() có callback xử lý r.message null
  □ frappe.db.get_value() trả về Promise, luôn dùng .then()
  □ Dialog primary_action gọi this.hide() trước callback
  □ Không dùng cur_frm (dùng frm parameter thay)

hooks.py:
  □ doc_events functions nhận đúng (doc, method) parameters
  □ override_doctype_class trỏ đúng đường dẫn module
  □ fixtures bao gồm custom fields và property setters
  □ scheduler_events có error handling
```

### 20.2 Anti-patterns cần tránh

```python
# ❌ SAI: Không gọi super() — mất toàn bộ logic ERPNext
class CustomSI(SalesInvoice):
    def validate(self):
        self.my_validate()  # super().validate() bị bỏ qua!

# ✅ ĐÚNG
class CustomSI(SalesInvoice):
    def validate(self):
        self.my_validate()
        super().validate()

# ❌ SAI: frappe.db.sql không parameterized — SQL injection
def get_invoices(customer):
    return frappe.db.sql(f"SELECT * FROM `tabSalesInvoice` WHERE customer = '{customer}'")

# ✅ ĐÚNG
def get_invoices(customer):
    return frappe.db.sql("SELECT * FROM `tabSalesInvoice` WHERE customer = %s", customer)

# ❌ SAI: Gọi doc.save() bên trong hook — triggers lồng nhau
def on_submit(doc, method):
    doc.custom_field = "value"
    doc.save()  # Gây re-trigger validate, on_submit!

# ✅ ĐÚNG
def on_submit(doc, method):
    frappe.db.set_value(doc.doctype, doc.name, "custom_field", "value")

# ❌ SAI: Import ở module level trong hooks — slow startup
import heavy_library  # Chạy khi app khởi động

# ✅ ĐÚNG: Import lazy bên trong function
def on_submit(doc, method):
    import heavy_library  # Chỉ import khi cần

# ❌ SAI: GL entries mất cân bằng
def get_gl_entries(self):
    gl = super().get_gl_entries()
    gl.append(self.get_gl_dict({"account": "Expense", "debit": 100}))
    # Thiếu credit entry!
    return gl

# ✅ ĐÚNG
def get_gl_entries(self):
    gl = super().get_gl_entries()
    gl += [
        self.get_gl_dict({"account": "Expense", "debit": 100}),
        self.get_gl_dict({"account": "Liability", "credit": 100}),
    ]
    return gl
```

```javascript
// ❌ SAI: Infinite loop — set_value trigger lại trigger
frappe.ui.form.on("Sales Invoice", {
    net_total(frm) {
        frm.set_value("custom_commission", frm.doc.net_total * 0.05);
        // net_total trigger lại bởi set_value → vòng lặp!
    }
});

// ✅ ĐÚNG: Trigger trên field riêng, không phải calculated field
frappe.ui.form.on("Sales Invoice", {
    custom_commission_rate(frm) {
        // Chỉ chạy khi user thay đổi rate, không loop
        frm.set_value("custom_commission", frm.doc.net_total * frm.doc.custom_commission_rate / 100);
    }
});

// ❌ SAI: Không handle null response
frappe.call({
    method: "...",
    callback(r) {
        const items = r.message.items;  // r.message có thể null!
        items.forEach(...);
    }
});

// ✅ ĐÚNG
frappe.call({
    method: "...",
    callback(r) {
        if (!r.message || !r.message.items) return;
        r.message.items.forEach(...);
    }
});

// ❌ SAI: Dùng cur_frm (không reliable trong dialog/child form)
function my_function() {
    cur_frm.set_value("field", "value");
}

// ✅ ĐÚNG: Luôn truyền frm vào function
function my_function(frm) {
    frm.set_value("field", "value");
}
```

---

*Tài liệu được tổng hợp từ source code ERPNext/Frappe (develop branch, tháng 6/2026). Mọi ví dụ đã được kiểm tra với ERPNext v15+.*

*Để đóng góp hoặc báo cáo lỗi, tham chiếu tới [github.com/frappe/erpnext](https://github.com/frappe/erpnext) và [github.com/frappe/frappe](https://github.com/frappe/frappe).*
