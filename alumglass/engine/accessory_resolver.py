"""
AccessoryResolver — Build accessory formulas from AL Accessory Set + substitution logic.
(Formerly pk_resolver.py — renamed per English naming conventions)
"""
import frappe
from frappe.utils import flt
from collections import defaultdict


class AccessoryResolver:
    """Build formulas from AL Accessory Set (formerly AL PK Set).
    Supports substitution with validation against substitute_item_group.
    """

    def build_formulas(self, bom_doc, accessory_overrides=None):
        """Build formulas for accessory set (if BOM has accessory_set).

        Args:
            bom_doc: AL BOM document
            accessory_overrides: dict {original_item_code: substitute_item_code}

        Returns:
            tuple: (formulas_accessory, warnings)
        """
        if not bom_doc.accessory_set:
            return [], []

        accessory_overrides = accessory_overrides or {}
        formulas = []
        warnings = []
        bucket_acc = defaultdict(list)
        idx = 0

        accessory_set = frappe.get_doc("AL Accessory Set", bom_doc.accessory_set)

        for line in accessory_set.al_accessory_lines:
            item_code = line.item_code
            actual_item = item_code

            # Check substitution
            override = accessory_overrides.get(item_code)
            if override:
                if line.allow_substitute:
                    valid = self._validate_substitute(override, line)
                    if valid:
                        actual_item = override
                    else:
                        warnings.append(
                            f"Accessory line '{line.item_code}': substitute "
                            f"'{override}' invalid; using default item."
                        )
                else:
                    warnings.append(
                        f"Accessory line '{line.item_code}' does not allow "
                        f"substitution (allow_substitute=0); using default item."
                    )

            # Quantity formula
            qty_formula = line.sl_formula or "1"

            # Unit price
            dg = self._get_item_price(actual_item, line.price_list)
            dg_str = str(flt(dg))

            # Generate formulas
            formulas.append({
                "name": f"acc_{idx:04d}_qty",
                "formula": qty_formula,
            })
            formulas.append({
                "name": f"acc_{idx:04d}_dg",
                "formula": dg_str,
            })
            formulas.append({
                "name": f"acc_{idx:04d}_tt",
                "formula": f"acc_{idx:04d}_qty * acc_{idx:04d}_dg",
            })

            bucket = line.cost_bucket or "VL_PK"
            bucket_acc[bucket].append(f"acc_{idx:04d}_tt")
            idx += 1

        # Build bucket formulas
        for bucket, var_list in bucket_acc.items():
            if var_list:
                formulas.append({
                    "name": bucket,
                    "formula": " + ".join(var_list),
                })

        return formulas, warnings

    def _validate_substitute(self, item_code, accessory_line):
        """Validate substitute item: must be active, correct item_type, correct group."""
        item = frappe.db.get_value(
            "Item", item_code,
            ["name", "disabled", "al_item_type", "item_group"],
            as_dict=True,
        )
        if not item or item.disabled:
            return False

        if item.al_item_type != "PHU_KIEN":
            return False

        if (
            accessory_line.substitute_item_group
            and item.item_group != accessory_line.substitute_item_group
        ):
            return False

        return True

    def _get_item_price(self, item_code, price_list=None):
        """Get unit price from Item Price."""
        if not item_code:
            return 0
        filters = {"item_code": item_code}
        if price_list:
            filters["price_list"] = price_list
        else:
            filters["selling"] = 1
        price = frappe.db.get_value(
            "Item Price", filters, "price_list_rate",
            order_by="valid_from desc",
        )
        return flt(price or 0)
