"""
DiscountStack — Áp dụng AL Discount Rule sau FormulaEngine (Hook A)
"""
import frappe
from frappe.utils import flt


class DiscountStack:
    """Áp dụng chiết khấu sau khi FormulaEngine tính xong GIA_BAN."""

    @staticmethod
    def apply(result, quotation_item, bom_doc, **kwargs):
        """Hook A — chạy sau FormulaEngine.calculate().

        Tìm các AL Discount Rule applicable → resolve stack → ghi vào quotation_item.
        """
        try:
            # Lấy thông tin khách hàng
            parent_docname = (
                quotation_item.get("parent")
                or getattr(quotation_item, "parent", None)
            )
            if not parent_docname:
                return

            customer = frappe.db.get_value("Quotation", parent_docname, "party_name")
            if not customer:
                return

            customer_group = frappe.db.get_value("Customer", customer, "customer_group")

            qty = flt(
                quotation_item.get("qty")
                or getattr(quotation_item, "qty", 1)
            )
            amount = flt(result.get("GIA_BAN", 0))

            # Tìm tất cả rules active, sắp xếp theo priority (số nhỏ = ưu tiên cao)
            rules = frappe.get_all(
                "AL Discount Rule",
                filters={"is_active": 1},
                fields=["*"],
                order_by="priority asc",
            )

            # Lọc rules applicable
            applicable = []
            for r in rules:
                if DiscountStack._rule_matches(r, customer, customer_group, bom_doc, qty, amount):
                    applicable.append(r)

            if not applicable:
                return

            # Resolve stack
            total_disc = 0.0
            applied_rule_name = None
            applied_rule_doc = None

            for r in applicable:
                rule_doc = frappe.get_doc("AL Discount Rule", r["name"])
                disc = DiscountStack._get_discount_pct(rule_doc, qty)

                if not rule_doc.stackable:
                    # Non-stackable rule thắng hoàn toàn
                    total_disc = disc
                    applied_rule_name = r["name"]
                    applied_rule_doc = rule_doc
                    break
                else:
                    total_disc += disc
                    if applied_rule_name is None:
                        applied_rule_name = r["name"]
                        applied_rule_doc = rule_doc

            # Cap max_total_discount
            max_disc = flt(
                frappe.db.get_single_value("AL Alert Config", "max_total_discount_pct") or 15
            )
            if total_disc > max_disc:
                total_disc = max_disc

            # Tính giá thương mại
            gia_ban_thuong_mai = amount * (1 - total_disc / 100)

            # Ghi vào quotation_item
            qi_name = (
                quotation_item.get("name")
                or getattr(quotation_item, "name", None)
            )
            if qi_name:
                frappe.db.set_value("Quotation Item", qi_name, "al_discount_pct", total_disc)
                frappe.db.set_value("Quotation Item", qi_name, "al_gia_thuong_mai", gia_ban_thuong_mai)
                frappe.db.set_value("Quotation Item", qi_name, "al_discount_rule", applied_rule_name)

                # Trigger approval nếu vượt ngưỡng
                approval_threshold = flt(
                    applied_rule_doc.approval_threshold_pct if applied_rule_doc else 0
                )
                if approval_threshold > 0 and total_disc > approval_threshold:
                    frappe.db.set_value("Quotation Item", qi_name, "al_approval_status", "PENDING")

        except Exception as e:
            frappe.log_error(
                title="DiscountStack.apply failed",
                message=str(e),
            )

    @staticmethod
    def _rule_matches(rule, customer, customer_group, bom_doc, qty, amount):
        """Kiểm tra rule có áp dụng được không."""
        # Customer match
        if rule.get("applies_to_customer") and rule["applies_to_customer"] != customer:
            return False
        # Customer group match (chỉ check nếu không có customer cụ thể)
        if (
            not rule.get("applies_to_customer")
            and rule.get("applies_to_customer_group")
            and rule["applies_to_customer_group"] != customer_group
        ):
            return False

        # BOM match
        if rule.get("applies_to_bom") and rule["applies_to_bom"] != bom_doc.name:
            return False

        # Amount range
        if rule.get("min_amount") and flt(amount) < flt(rule["min_amount"]):
            return False
        if rule.get("max_amount") and flt(rule["max_amount"]) > 0 and flt(amount) > flt(rule["max_amount"]):
            return False

        # Date range
        from frappe.utils import today
        if rule.get("valid_from") and str(rule["valid_from"]) > str(today()):
            return False
        if rule.get("valid_to") and str(rule["valid_to"]) < str(today()):
            return False

        return True

    @staticmethod
    def _get_discount_pct(rule_doc, qty):
        """Lấy discount_pct từ rule (fixed hoặc tier-based)."""
        if rule_doc.rule_type == "VOLUME" and rule_doc.al_discount_tiers:
            for tier in rule_doc.al_discount_tiers:
                min_qty = flt(tier.min_qty)
                max_qty = flt(tier.max_qty)
                if qty >= min_qty and (max_qty == 0 or qty <= max_qty):
                    return flt(tier.discount_pct)
            return 0
        return flt(rule_doc.discount_pct or 0)
