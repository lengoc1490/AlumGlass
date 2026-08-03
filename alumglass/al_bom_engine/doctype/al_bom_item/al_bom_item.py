import frappe
from frappe.model.document import Document


class ALBomItem(Document):
    """Dòng vật tư thống nhất - Doctype TRUNG TÂM của hệ thống AlumGlass.

    Mỗi dòng đại diện 1 thành phần trong BOM sản phẩm.
    Validation DATA-DRIVEN dựa trên flags của AL Material Category.
    Hỗ trợ: NHOM, KINH, THEP, INOX, VTP, PK, NHUA, GO...
    """

    def validate(self):
        if not self.category:
            return
        cat = frappe.get_cached_doc("AL Material Category", self.category)

        # 1. Item Code bắt buộc khi mode=Fixed
        if cat.requires_item_code and self.item_selection_mode == "Fixed":
            if not self.item_code:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Item Code là bắt buộc "
                    f"cho category '{self.category}'"
                )

        # 2. Price Base Item đại diện để tra giá composite key
        if cat.requires_price_base_item and self.price_type == "Item Price":
            if not self.price_base_item:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Price Base Item là bắt buộc "
                    f"cho category '{self.category}'. "
                    f"Đây là Item đại diện để tra giá composite key."
                )

        # 3. Glass Master cho dòng KINH
        if cat.requires_glass_master and not self.default_glass_master:
            frappe.throw(
                f"Dòng '{self.slug or self.idx}': Default Glass Master là bắt buộc "
                f"cho category '{self.category}'. "
                f"Đây là nguồn glass_thick & glass_type."
            )

        # 4. CTX Inject Prefix
        if cat.requires_ctx_inject_prefix and not self.ctx_inject_prefix:
            frappe.throw(
                f"Dòng '{self.slug or self.idx}': CTX Inject Prefix là bắt buộc"
            )

        # 5. Qty Formula
        if not self.qty:
            frappe.throw(f"Dòng '{self.slug or self.idx}': Qty Formula là bắt buộc")

        # 6. Rule Mode validation
        if self.item_selection_mode == "Rule":
            if not self.item_rule:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Item Rule là bắt buộc khi mode=Rule"
                )
            if not self.rule_input_expr:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Rule Input Expression là bắt buộc "
                    f"khi mode=Rule. VD: items.kinh_tren.glass_thick"
                )

        if self.item_selection_mode == "Formula":
            if not self.item_condition_formula:
                frappe.throw(
                    f"Dòng '{self.slug or self.idx}': Item Condition Formula là bắt buộc "
                    f"khi mode=Formula"
                )

    def before_save(self):
        """Tự động fill category & line_name từ Slug Library."""
        if self.slug:
            try:
                slug_doc = frappe.get_cached_doc("AL Slug Library", self.slug)
                if not self.category:
                    self.category = slug_doc.category
                if not self.line_name:
                    self.line_name = slug_doc.label
            except frappe.DoesNotExistError:
                pass


@frappe.whitelist()
def get_slug_info(slug):
    """Trả về thông tin Slug để client tự fill."""
    if not slug:
        return {}
    doc = frappe.get_cached_doc("AL Slug Library", slug)
    return {"category": doc.category, "line_name": doc.label, "group_tag": doc.group_tag}


@frappe.whitelist()
def get_category_requirements(category_code):
    """Trả về requirement flags cho client-side validation."""
    if not category_code:
        return {}
    cat = frappe.get_cached_doc("AL Material Category", category_code)
    return {
        "requires_item_code": cat.requires_item_code,
        "requires_price_base_item": cat.requires_price_base_item,
        "requires_glass_master": cat.requires_glass_master,
        "requires_ctx_inject_prefix": cat.requires_ctx_inject_prefix,
        "has_weight": cat.has_weight,
        "has_dimensions": cat.has_dimensions,
        "default_calc_pattern": cat.default_calc_pattern,
        "default_cost_bucket": cat.default_cost_bucket,
    }
