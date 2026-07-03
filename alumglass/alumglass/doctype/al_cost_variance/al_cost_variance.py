# AL Cost Variance — Compare Quotation price vs actual Purchase price
# In before_insert: auto-calculate variance_pct and variance_status
# Validate no duplicate (quotation_item, purchase_invoice, item_code)
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALCostVariance(Document):
    def before_insert(self):
        """Auto-calculate variance metrics before insert."""
        self._calculate_variance()

    def validate(self):
        # Check for duplicate entry
        existing = frappe.db.exists(
            "AL Cost Variance",
            {
                "quotation_item": self.quotation_item,
                "purchase_invoice": self.purchase_invoice,
                "item_code": self.item_code,
                "name": ("!=", self.name) if self.name else ("!=", ""),
            },
        )
        if existing:
            frappe.throw(
                f"A Cost Variance already exists for "
                f"Quotation Item '{self.quotation_item}', "
                f"Purchase Invoice '{self.purchase_invoice}', "
                f"Item '{self.item_code}'"
            )
        self._calculate_variance()

    def _calculate_variance(self):
        """Calculate variance_pct and determine variance_status."""
        quoted = flt(self.quoted_unit_price)
        actual = flt(self.actual_unit_price)

        if quoted == 0:
            self.variance_pct = 0
            self.variance_status = "NORMAL"
            self.variance_amount = 0
            self.impact_on_margin = 0
            return

        self.variance_amount = actual - quoted
        self.variance_pct = round(((actual - quoted) / quoted) * 100, 2)

        if self.variance_pct < -5:
            self.variance_status = "FAVORABLE"
        elif abs(self.variance_pct) < 5:
            self.variance_status = "NORMAL"
        elif abs(self.variance_pct) < 15:
            self.variance_status = "CAUTION"
        else:
            self.variance_status = "ALERT"

        # Impact on margin
        self.impact_on_margin = self.variance_amount
