import frappe, json
from frappe.model.document import Document


class ALBOMVersion(Document):
    """Snapshot bất biến của BOM - quản lý qua Workflow."""

    def before_insert(self):
        """Tự động snapshot BOM Set + Cost Template khi tạo version."""
        if not self.bom_set_snapshot:
            self._take_snapshots()

    def on_update(self):
        """Cập nhật current_version trên BOM cha khi Published."""
        if self.workflow_state == "Published" and self.bom:
            frappe.db.set_value("AL BOM", self.bom, "current_version", self.name)

    def _take_snapshots(self):
        if not self.bom:
            return
        bom = frappe.get_cached_doc("AL BOM", self.bom)

        # ── Lấy dynamic formula fieldnames từ AL Bom Item meta ──────
        formula_fields = self._get_bom_item_formula_fields()

        # Snapshot BOM Set
        if bom.bom_set:
            bs = frappe.get_cached_doc("AL Bom Set", bom.bom_set)
            items_snap = []
            for i in bs.items:
                if not getattr(i, "is_active", True):
                    continue
                row = {
                    "slug": i.slug,
                    "category": i.category,
                    "item_code": i.item_code,
                    "item_selection_mode": i.item_selection_mode,
                    "item_rule": i.item_rule,
                    "calc_pattern": i.calc_pattern,
                    "cost_bucket": i.cost_bucket,
                    "price_type": i.price_type,
                    "price_base_item": i.price_base_item,
                    "default_glass_master": i.default_glass_master,
                    "ctx_inject_prefix": i.ctx_inject_prefix,
                }
                # Include ALL formula fields dynamically
                for ff in formula_fields:
                    val = getattr(i, ff, None)
                    if val is not None and str(val).strip():
                        row[ff] = val
                items_snap.append(row)

            self.bom_set_snapshot = json.dumps({
                "set_code": bs.set_code,
                "set_name": bs.set_name,
                "product_type": bs.product_type,
                "profile_system": bs.profile_system,
                "items": items_snap,
            }, indent=2)

        # Snapshot Cost Template
        if bom.default_cost_template:
            ct = frappe.get_cached_doc("AL Cost Template", bom.default_cost_template)
            self.cost_template_snapshot = json.dumps({
                "template_code": ct.template_code,
                "template_name": ct.template_name,
                "items": [{
                    "line_code": i.line_code,
                    "line_label": i.line_label,
                    "calc_formula": i.calc_formula,
                    "cost_bucket": i.cost_bucket,
                } for i in ct.items],
            }, indent=2)

    @staticmethod
    def _get_bom_item_formula_fields():
        """Đọc tất cả Small Text fields từ AL Bom Item doctype meta."""
        meta = frappe.get_meta("AL Bom Item")
        return [f.fieldname for f in meta.get("fields", [])
                if f.get("fieldtype") == "Small Text"]
