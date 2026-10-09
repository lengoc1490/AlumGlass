import frappe, json
from frappe.model.document import Document

# Field hệ thống + field layout của AL Bom Item — KHÔNG chụp vào snapshot
# (là metadata/hình thức, không phải dữ liệu nghiệp vụ của dòng).
_SNAPSHOT_SKIP_FIELDNAMES = frozenset({
    "name", "parent", "parentfield", "parenttype", "idx", "docstatus",
    "owner", "creation", "modified", "modified_by",
})
_SNAPSHOT_SKIP_FIELDTYPES = frozenset({
    "Section Break", "Column Break", "Tab Break", "HTML", "Button",
    "Table", "Table MultiSelect",
})


class ALBOMVersion(Document):
    """Snapshot bất biến của BOM - quản lý qua Workflow."""

    def before_insert(self):
        """Tự động snapshot BOM Set + Cost Template + Pricing Dimension khi tạo version."""
        if not self.bom_set_snapshot:
            self._take_snapshots()
        # P1: chụp pricing dimension ngay khi tạo version (cùng chỗ _take_snapshots).
        if not self.pricing_dimension_snapshot:
            self._snapshot_pricing_dimensions()

    def validate(self):
        """Validate trước mỗi lần save."""
        self._backfill_pricing_snapshot_on_publish()
        self._guard_published_immutability()

    def on_update(self):
        """Cập nhật `current_version` trên BOM cha — CHỈ khi version VỪA Published.

        ⛔ KHÔNG set lại mỗi lần save một version Published: save lại một bản
        CŨ (sửa ghi chú, Retire rồi lưu...) sẽ kéo `current_version` của AL BOM
        LÙI về bản cũ đó.
        """
        if not self._just_entered_published():
            return
        if self.bom:
            frappe.db.set_value("AL BOM", self.bom, "current_version", self.name)

    # ── Trạng thái "vừa Publish" ───────────────────────────────────────
    def _just_entered_published(self):
        """True nếu lần lưu NÀY vừa chuyển workflow_state sang Published.

        `_doc_before_save` là bản ghi TRƯỚC khi lưu (Frappe nạp trong
        `check_if_latest()`, để rỗng khi là chứng từ mới) → so sánh được "vừa
        publish" với "save lại một bản đã Published từ lâu". Chứng từ mới insert
        (Workflow đặt Published làm trạng thái đầu) cũng tính là vừa publish.
        """
        if self.workflow_state != "Published":
            return False
        before = self.get_doc_before_save()
        if not before:
            return True
        return before.get("workflow_state") != "Published"

    def _backfill_pricing_snapshot_on_publish(self):
        """Chụp bù pricing dimension cho version CŨ (tạo trước patch P1) —
        CHỈ đúng lần version đó chuyển sang Published.

        ⛔ KHÔNG chụp bù cho bản Published đã lâu: `_snapshot_pricing_dimensions()`
        query cấu hình LIVE (AL Pricing Dimension / AL Variable Dimension
        Mapping) ⇒ chụp bù về sau là VIẾT LẠI snapshot lịch sử bằng cấu hình
        HÔM NAY, phá đúng tính bất biến mà `_guard_published_immutability` bảo vệ
        (và guard không thấy được vì `db_set` ghi thẳng DB, bỏ qua `validate()`).

        Vì vậy giá trị được gán vào `self` để đi qua đường save chuẩn — KHÔNG
        dùng `db_set`, không còn cửa hậu nào lách guard.
        """
        if self.pricing_dimension_snapshot:
            return
        if not self._just_entered_published():
            return
        self._snapshot_pricing_dimensions()

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

        # ── Fieldname DỮ LIỆU của AL Bom Item (đọc từ meta) ─────────
        data_fields = self._get_bom_item_data_fields()

        # Snapshot BOM Set
        if bom.bom_set:
            bs = frappe.get_cached_doc("AL Bom Set", bom.bom_set)
            items_snap = []
            for i in bs.items:
                if not getattr(i, "is_active", True):
                    continue
                # D6/F4a: chụp MỌI field dữ liệu của dòng, KHÔNG chỉ 12 field
                # cố định + field Small Text. Snapshot cũ thiếu fieldtype
                # Link/Data/Check/Float ⇒ engine đọc `item.get("default_color")`
                # (color_group_resolver.color_group_rep) luôn ra None ⇒ TOÀN BỘ
                # chuỗi override giá theo màu không bao giờ chạy; kéo theo
                # `supplier_location` / `install_position` / `cut_angle` luôn
                # trắng ở bảng Preview.
                items_snap.append(self._snapshot_item_row(i, data_fields))

            self.bom_set_snapshot = json.dumps({
                "set_code": bs.set_code,
                "set_name": bs.set_name,
                "product_type": bs.product_type,
                "profile_system": bs.profile_system,
                "items": items_snap,
            }, indent=2, default=str)

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
                    # V6 P10: chụp cờ is_final_price — BomOrchestrator dùng
                    # để xác định dòng nào là giá bán cuối cùng, KHÔNG hardcode
                    # tên line_code "GIA_VAT" nữa (xem al_cost_template_item.json).
                    "is_final_price": i.get("is_final_price", 0),
                    # D7: cờ dòng "giá trước VAT" (al_gia_ban) — snapshot cũ
                    # thiếu → item.get trả 0 → engine fallback GIA_BAN (cũ).
                    "is_pre_vat_price": i.get("is_pre_vat_price", 0),
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
            filters={"is_active": 1},
            # D6/F4a: chụp thêm `represents_color` và `link_doctype` — engine đang
            # đọc LIVE 2 field này (bom_orchestrator._get_color_dimension_codes
            # lọc `represents_color: 1`; _fetch_composite_prices_multiplier_chain
            # đọc `link_doctype`). Thiếu trong snapshot ⇒ báo giá cũ tái lập sai
            # khi ai đó đổi 2 cờ này về sau.
            fields=["dimension_code", "dimension_type", "custom_fieldname",
                    "represents_color", "link_doctype"],
            order_by="dimension_code",
        )
        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            filters={"is_active": 1},
            fields=["variable_name", "pricing_dimension", "price_multiplier",
                    "material_category"],
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
    def _snapshot_item_row(item, data_fields):
        """1 dòng AL Bom Item → dict MỌI field dữ liệu.

        Meta-driven để thêm field mới vào DocType là snapshot tự có, KHÔNG phải
        nhớ sửa hàm này (đúng lớp lỗi D6/F4a: snapshot cũ liệt kê tay 12 field
        nên field Link thêm sau đó — `default_color` — rơi mất im lặng).
        """
        return {fn: item.get(fn) for fn in data_fields}

    @staticmethod
    def _get_bom_item_data_fields():
        """Fieldname DỮ LIỆU của AL Bom Item — bỏ field hệ thống + field layout."""
        meta = frappe.get_meta("AL Bom Item")
        return [
            f.get("fieldname")
            for f in meta.get("fields", [])
            if f.get("fieldname")
            and f.get("fieldname") not in _SNAPSHOT_SKIP_FIELDNAMES
            and f.get("fieldtype") not in _SNAPSHOT_SKIP_FIELDTYPES
        ]
