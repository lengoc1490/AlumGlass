import frappe
from frappe.model.document import Document
from collections import defaultdict


class ALMaterialPlan(Document):
    """Kế hoạch vật tư - tổng hợp nhu cầu từ nhiều BOM."""

    def validate(self):
        if self.items:
            self._calculate_shortfalls()

    def _calculate_shortfalls(self):
        for item in self.items:
            if not item.item_code:
                continue
            item.stock_qty = frappe.db.get_value("Bin", {"item_code": item.item_code}, "actual_qty") or 0
            item.ordered_qty = item.ordered_qty or 0
            item.shortfall_qty = max(0, (item.required_qty or 0) - item.stock_qty - item.ordered_qty)

    def before_save(self):
        if not self.plan_code:
            from frappe.model.naming import make_autoname
            self.plan_code = make_autoname("MP-.#####")


@frappe.whitelist()
def aggregate_requirements(sales_orders):
    """Tổng hợp nhu cầu vật tư từ danh sách Sales Orders."""
    if isinstance(sales_orders, str):
        import json; sales_orders = json.loads(sales_orders)
    reqs = defaultdict(lambda: {"required_qty": 0, "sources": []})
    for so in sales_orders:
        items = frappe.get_all("Sales Order Item", filters={"parent": so},
            fields=["item_code","qty","al_bom","al_bom_version"])
        for item in items:
            if item.al_bom_version:
                bom_ver = frappe.get_doc("AL BOM Version", item.al_bom_version)
                if bom_ver.bom_set_snapshot:
                    import json as _j
                    snap = _j.loads(bom_ver.bom_set_snapshot) if isinstance(bom_ver.bom_set_snapshot, str) else bom_ver.bom_set_snapshot
                    for bi in snap.get("items", []):
                        reqs[bi["item_code"]]["required_qty"] += (bi.get("qty",1) or 1) * item.qty
                        reqs[bi["item_code"]]["sources"].append({"bom": item.al_bom, "slug": bi.get("slug","")})
    return dict(reqs)
