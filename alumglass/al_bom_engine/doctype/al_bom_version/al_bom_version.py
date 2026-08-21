import frappe, json
from frappe.model.document import Document


class ALBOMVersion(Document):
    """Snapshot bất biến của BOM - quản lý qua Workflow."""

    def before_insert(self):
        """Tự động snapshot BOM Set + Cost Template + Pricing Dimension khi tạo version."""
        if not self.bom_set_snapshot:
            self._take_snapshots()
        # P1: chụp pricing dimension ngay khi tạo version (cùng chỗ _take_snapshots).
        # Version tạo trực tiếp Published (vd seed) vẫn được snapshot đầy đủ.
        if not self.pricing_dimension_snapshot:
            self._snapshot_pricing_dimensions()

    def validate(self):
        """Validate trước mỗi lần save."""
        self._guard_published_immutability()

    def on_update(self):
        """Cập nhật current_version trên BOM cha khi Published."""
        if self.workflow_state == "Published" and self.bom:
            frappe.db.set_value("AL BOM", self.bom, "current_version", self.name)
        # P1: lưới an toàn cho version cũ (chưa có pricing_dimension_snapshot).
        # Nếu version ĐÃ Published mà field rỗng (tạo trước patch P1) → chụp bù
        # ngay lần save tiếp theo. Dùng set_value để không tái kích hoạt guard
        # (guard chỉ chặn khi giá trị cũ != giá trị mới; field đang rỗng nên
        # set lần đầu là hợp lệ).
        if self.workflow_state == "Published" and not self.pricing_dimension_snapshot:
            self._snapshot_pricing_dimensions()
            self.db_set("pricing_dimension_snapshot", self.pricing_dimension_snapshot)

    def _guard_published_immutability(self):
        """Chặn sửa snapshot fields sau khi đã Published — bảo toàn tính
        bất biến (immutable) mà README cam kết. Chỉ cho phép đổi
        workflow_state (vd Published -> Retired), không cho đổi nội dung.
        """
        if self.is_new():
            return
        prev = frappe.db.get_value(
            self.doctype, self.name,
            ["workflow_state", "bom_set_snapshot", "cost_template_snapshot",
             "pricing_dimension_snapshot"],
            as_dict=True,
        )
        if not prev or prev.workflow_state != "Published":
            return
        guarded = [
            ("bom_set_snapshot", "BOM Set"),
            ("cost_template_snapshot", "Cost Template"),
            ("pricing_dimension_snapshot", "Pricing Dimension"),
        ]
        for fieldname, label in guarded:
            if (self.get(fieldname) or "") != (prev.get(fieldname) or ""):
                frappe.throw(
                    f"AL BOM Version đã ở trạng thái Published — không được sửa "
                    f"snapshot {label} ({fieldname}). Hãy tạo 1 version mới "
                    f"(AL Design Revision) thay vì sửa version cũ, để giữ "
                    f"đúng lịch sử báo giá đã gửi khách hàng."
                )

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

    # ── P1: Snapshot Pricing Dimension + Variable Dimension Mapping ────
    def _snapshot_pricing_dimensions(self):
        """Chụp TOÀN BỘ bảng Pricing Dimension + Variable Dimension Mapping.

        Không filter theo BOM. Lý do: filter theo "dimension nào BOM này dùng"
        đòi hỏi parse hết Bom Set + Variable Set trước, dễ sót (VD:
        multiplier_chain có thể tham chiếu dimension không xuất hiện trực tiếp
        trong formula). 2 bảng này rất nhỏ (vài chục dòng) — snapshot toàn bộ
        an toàn và rẻ, đồng thời BomOrchestrator._get_dim_fieldnames() chỉ cần
        đọc snapshot là đủ, không phụ thuộc config live.

        Lưu ý field không tồn tại trên doctype (vd `pricing_mode`, `custom_fieldname`
        trên AL Variable Dimension Mapping) → KHÔNG query, tránh get_all lỗi.
        BomOrchestrator tự nối pricing_dimension → custom_fieldname qua bảng
        dimensions đã chụp.
        """
        dimensions = frappe.get_all(
            "AL Pricing Dimension",
            fields=["dimension_code", "dimension_type", "custom_fieldname"],
            order_by="dimension_code",
        )
        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            fields=["variable_name", "pricing_dimension", "price_multiplier"],
            order_by="variable_name",
        )

        self.pricing_dimension_snapshot = json.dumps(
            {
                "captured_at": frappe.utils.now_datetime().isoformat(),
                "dimensions": dimensions,
                "mappings": mappings,
            },
            default=str,
        )

    @staticmethod
    def _get_bom_item_formula_fields():
        """Đọc tất cả Small Text fields từ AL Bom Item doctype meta."""
        meta = frappe.get_meta("AL Bom Item")
        return [f.fieldname for f in meta.get("fields", [])
                if f.get("fieldtype") == "Small Text"]
