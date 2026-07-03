# AL Profile Line — Core material line: Aluminum / Glass / Consumable / Accessory
# Auto-generate slug from sort_order + line_name
# Validate ctx_inject_prefix must NOT end with a digit
# Validate if line_type='Glass' then ctx_inject_prefix is required and unique in Profile Set
import re
import frappe
from frappe.model.document import Document


class ALProfileLine(Document):
    def before_insert(self):
        self._auto_generate_slug()

    def validate(self):
        self._auto_generate_slug()
        self._validate_ctx_inject_prefix()
        self._validate_glass_required_fields()
        self._validate_aluminum_required_fields()

    def _auto_generate_slug(self):
        """Auto-generate slug from sort_order + line_type + line_name.

        Examples: aluminum_0010, glass_kinh_canh, consumable_0100, accessory_0150
        """
        if self.slug:
            return  # Already set manually

        type_prefix = {
            "Aluminum": "aluminum",
            "Glass": "glass",
            "Consumable": "consumable",
            "Accessory": "accessory",
        }.get(self.line_type, "unknown")

        if self.ctx_inject_prefix and self.line_type == "Glass":
            # Glass lines use ctx_inject_prefix as slug base
            self.slug = f"glass_{self.ctx_inject_prefix}"
        elif self.sort_order:
            self.slug = f"{type_prefix}_{self.sort_order:04d}"
        else:
            self.slug = f"{type_prefix}_0000"

    def _validate_ctx_inject_prefix(self):
        """Validate ctx_inject_prefix for Glass lines.

        1. Must NOT end with a digit (interferes with panel indexing {prefix}_0).
        2. Must be UNIQUE within the parent Profile Set.
        """
        if self.line_type != "Glass":
            return

        prefix = (self.ctx_inject_prefix or "").strip()
        if not prefix:
            frappe.throw(
                f"Glass line '{self.line_name or self.slug}': "
                "Context Inject Prefix is required for Glass lines"
            )

        # Must not end with a digit
        if re.search(r'[0-9]$', prefix):
            frappe.throw(
                f"Context Inject Prefix '{prefix}' must NOT end with a digit. "
                f"This would conflict with panel index naming ({prefix}_0, {prefix}_1, ...). "
                f"Use a descriptive name like 'kinh_canh' instead."
            )

        # Must be unique within the Profile Set
        if self.parent:
            existing = frappe.db.sql(
                """
                SELECT name, ctx_inject_prefix FROM `tabAL Profile Line`
                WHERE parent=%s AND line_type='Glass'
                AND ctx_inject_prefix=%s AND name!=%s
                """,
                (self.parent, prefix, self.name),
                as_dict=True,
            )
            if existing:
                frappe.throw(
                    f"Context Inject Prefix '{prefix}' is already used by "
                    f"another Glass line in this Profile Set. "
                    f"Each Glass line must have a unique prefix."
                )

    def _validate_glass_required_fields(self):
        """Validate Glass-specific required fields."""
        if self.line_type != "Glass":
            return
        if not self.default_glass_master:
            frappe.throw(
                f"Glass line '{self.line_name}': Default Glass Master is required"
            )

    def _validate_aluminum_required_fields(self):
        """Validate Aluminum-specific required fields."""
        if self.line_type != "Aluminum":
            return
        if not self.item_code:
            frappe.throw(
                f"Aluminum line '{self.line_name}': Item Code is required"
            )
