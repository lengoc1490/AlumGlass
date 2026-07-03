# AL Sales KPI — Sales performance tracking
# Validate no duplicate (sales_user, kpi_period, period_label)
# Validate target_amount > 0
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ALSalesKPI(Document):
    def validate(self):
        if flt(self.target_amount) <= 0:
            frappe.throw("Target Amount must be greater than 0")

        # Check for duplicate KPI period per user
        existing = frappe.db.exists(
            "AL Sales KPI",
            {
                "sales_user": self.sales_user,
                "kpi_period": self.kpi_period,
                "period_label": self.period_label,
                "name": ("!=", self.name) if self.name else ("!=", ""),
            },
        )
        if existing:
            frappe.throw(
                f"A KPI already exists for User '{self.sales_user}', "
                f"Period '{self.period_label}' ({self.kpi_period})"
            )
