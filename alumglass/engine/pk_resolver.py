"""
PkResolver — Xử lý AL PK Set: tạo formula cho phụ kiện + substitution
"""
import frappe
from frappe.utils import flt
from collections import defaultdict


class PkResolver:
    """Build formulas từ AL PK Set. Hỗ trợ substitution với validation."""

    def build_formulas(self, bom_doc, pk_overrides=None):
        """Xây dựng formula cho PK Set (nếu BOM có pk_set).

        Args:
            bom_doc: AL BOM document
            pk_overrides: dict {item_code_gốc: item_code_thay_thế}

        Returns:
            tuple: (formulas_pk, warnings)
        """
        if not bom_doc.pk_set:
            return [], []

        pk_overrides = pk_overrides or {}
        formulas = []
        warnings = []
        bucket_acc = defaultdict(list)
        idx = 0

        pk_set = frappe.get_doc("AL PK Set", bom_doc.pk_set)

        for line in pk_set.al_pk_lines:
            item_code = line.item_code
            actual_item = item_code

            # Check substitution
            override = pk_overrides.get(item_code)
            if override:
                if line.allow_substitute:
                    # Validate substitute item
                    valid = self._validate_substitute(override, line)
                    if valid:
                        actual_item = override
                    else:
                        warnings.append(
                            f"Dòng phụ kiện '{line.item_code}': item thay thế "
                            f"'{override}' không hợp lệ; dùng item mặc định."
                        )
                else:
                    warnings.append(
                        f"Dòng phụ kiện '{line.item_code}' không cho phép "
                        f"thay thế (allow_substitute=0); dùng item mặc định."
                    )

            # Quantity formula
            qty_formula = line.sl_formula or "1"

            # Unit price
            dg = self._get_item_price(actual_item, line.price_list)
            dg_str = str(flt(dg))

            # Generate formulas
            formulas.append({
                "name": f"pk_{idx:04d}_qty",
                "formula": qty_formula,
            })
            formulas.append({
                "name": f"pk_{idx:04d}_dg",
                "formula": dg_str,
            })
            formulas.append({
                "name": f"pk_{idx:04d}_tt",
                "formula": f"pk_{idx:04d}_qty * pk_{idx:04d}_dg",
            })

            bucket = line.cost_bucket or "VL_PK"
            bucket_acc[bucket].append(f"pk_{idx:04d}_tt")
            idx += 1

        # Build bucket formulas
        for bucket, var_list in bucket_acc.items():
            if var_list:
                formulas.append({
                    "name": bucket,
                    "formula": " + ".join(var_list),
                })

        return formulas, warnings

    def _validate_substitute(self, item_code, pk_line):
        """Validate item thay thế: phải active, đúng item_type, đúng group."""
        item = frappe.db.get_value(
            "Item", item_code,
            ["name", "disabled", "al_item_type", "item_group"],
            as_dict=True,
        )
        if not item or item.disabled:
            return False

        if item.al_item_type != "PHU_KIEN":
            return False

        if pk_line.substitute_item_group and item.item_group != pk_line.substitute_item_group:
            return False

        return True

    def _get_item_price(self, item_code, price_list=None):
        """Lấy đơn giá từ Item Price."""
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
