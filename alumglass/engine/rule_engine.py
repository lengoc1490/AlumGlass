"""
Rule Engine v3 — P0: CONSTANT/FORMULA/SEQUENCE delegated to Formula Global Variable/Formula Set
Chỉ giữ lại THRESHOLD và LOOKUP (domain-specific, table-based UX)
"""
import frappe
from frappe.utils import flt


class RuleEngine:
    """Chuyển đổi AL Calculation Rule thành formula hoặc giá trị cho FormulaEngine.

    v3 changes (P0):
    - CONSTANT → tra Formula Global Variable trước, fallback AL Rule
    - FORMULA  → tra Formula Global Variable trước, fallback AL Rule
    - SEQUENCE → tra Formula Set trước, fallback AL Rule
    - THRESHOLD, LOOKUP → giữ nguyên (không có FB equivalent)
    """

    def resolve_rule(self, rule_code, inputs_dict=None):
        """Resolve 1 rule → trả về (giá trị hoặc formula string).

        Returns:
            str|float|None: Giá trị hoặc biểu thức formula cho FormulaEngine
        """
        if not rule_code:
            return None

        rule = frappe.db.get_value(
            "AL Calculation Rule",
            {"rule_code": rule_code, "is_active": 1},
            ["name", "rule_type", "constant_value", "formula_expression",
             "threshold_input_var", "lookup_key_1_var", "lookup_key_2_var",
             "lookup_default"],
            as_dict=True,
        )
        if not rule:
            # Thử tra Formula Global Variable (FB)
            fb_val = self._try_fb_global(rule_code)
            if fb_val is not None:
                return fb_val
            frappe.log_error(f"Rule not found: {rule_code}")
            return "0"

        if rule.rule_type == "CONSTANT":
            # P0: Ưu tiên Formula Global Variable
            fb_val = self._try_fb_global(rule_code)
            if fb_val is not None:
                return str(flt(fb_val))
            return str(flt(rule.constant_value or 0))

        elif rule.rule_type == "FORMULA":
            # P0: Ưu tiên Formula Global Variable (FORMULA mode)
            fb_val = self._try_fb_global(rule_code)
            if fb_val is not None:
                return str(fb_val)
            return rule.formula_expression or "0"

        elif rule.rule_type == "THRESHOLD":
            # Giữ nguyên — domain-specific IFS chain
            return self._build_threshold_formula(rule)

        elif rule.rule_type == "LOOKUP":
            # Giữ nguyên — table-based lookup
            return self._evaluate_lookup(rule, inputs_dict or {})

        elif rule.rule_type == "SEQUENCE":
            # P1: Ưu tiên Formula Set
            fs_val = self._try_fb_formula_set(rule_code)
            if fs_val is not None:
                return fs_val
            return self._resolve_sequence(rule.name)

        return "0"

    # ============================================================
    # P0: Formula Global Variable integration
    # ============================================================

    def _try_fb_global(self, var_name):
        """Tra cứu Formula Global Variable (FB native).
        Returns value string hoặc None nếu không tìm thấy.
        """
        try:
            val = frappe.db.get_value(
                "Formula Global Variable",
                {"var_name": var_name, "is_active": 1},
                "constant_value",
            )
            if val is not None:
                return val

            # Nếu là FORMULA mode — evaluate qua FormulaEngine
            fb_var = frappe.db.get_value(
                "Formula Global Variable",
                {"var_name": var_name, "is_active": 1},
                ["value_source", "formula_expr", "constant_value"],
                as_dict=True,
            )
            if fb_var:
                if fb_var.value_source == "CONSTANT":
                    return fb_var.constant_value
                elif fb_var.value_source == "FORMULA" and fb_var.formula_expr:
                    # Return formula expression để FormulaEngine xử lý
                    return fb_var.formula_expr
        except Exception:
            pass
        return None

    def _try_fb_formula_set(self, set_code):
        """Tra cứu Formula Set (FB native).
        Returns list of formulas hoặc None nếu không tìm thấy.
        """
        try:
            lines = frappe.get_all(
                "Formula Set Line",
                filters={"parent": set_code},
                fields=["var_name", "formula"],
                order_by="idx asc",
            )
            if lines:
                return [
                    {"name": ln.var_name, "formula": ln.formula}
                    for ln in lines
                ]
        except Exception:
            pass
        return None

    # ============================================================
    # THRESHOLD — giữ nguyên
    # ============================================================

    def _build_threshold_formula(self, rule):
        """Xây dựng IF(...) chain từ bảng ngưỡng."""
        rows = frappe.get_all(
            "AL Rule Threshold Row",
            filters={"parent": rule.name},
            fields=["from_value", "to_value", "result_value"],
            order_by="from_value asc",
        )
        if not rows:
            return "0"

        input_var = rule.threshold_input_var or "x"
        parts = []
        for row in rows:
            to_val = row.to_value
            if to_val and flt(to_val) > 0:
                cond = f"{input_var} >= {row.from_value} and {input_var} < {to_val}"
            else:
                cond = f"{input_var} >= {row.from_value}"
            parts.append(f"IF({cond}, {row.result_value}")

        if len(parts) == 1:
            return parts[0].replace("IF(", "") + f", {parts[0].split(', ')[1]}, 0)"
        result = parts[-1].replace("IF(", "")
        for i in range(len(parts) - 2, -1, -1):
            result = f"{parts[i]}, {result}"
        return result

    # ============================================================
    # LOOKUP — giữ nguyên
    # ============================================================

    def _evaluate_lookup(self, rule, inputs_dict):
        """Tra cứu LOOKUP tại Python → trả về giá trị."""
        key1_val = inputs_dict.get(rule.lookup_key_1_var, "")
        key2_val = inputs_dict.get(rule.lookup_key_2_var, "")

        lookup_rows = frappe.get_all(
            "AL Rule Lookup Row",
            filters={"parent": rule.name},
            fields=["key_1", "key_2", "key_3", "result_value"],
        )

        for row in lookup_rows:
            match = True
            if key1_val and row.key_1 and str(key1_val) != str(row.key_1):
                match = False
            if key2_val and row.key_2 and str(key2_val) != str(row.key_2):
                match = False
            if match:
                return flt(row.result_value or 0)

        return flt(rule.lookup_default or 0)

    # ============================================================
    # SEQUENCE — legacy fallback
    # ============================================================

    def _resolve_sequence(self, rule_name):
        """Resolve SEQUENCE rule → trả về list công thức con (legacy)."""
        items = frappe.get_all(
            "AL Rule Sequence Item",
            filters={"parent": rule_name},
            fields=["rule", "sort_order"],
            order_by="sort_order asc",
        )
        formulas = []
        for item in items:
            result = self.resolve_rule(item.rule)
            if result is not None:
                formulas.append(result)
        return formulas

    def get_rule_as_input(self, rule_code, inputs_dict):
        """Đánh giá LOOKUP rule → giá trị số cho inputs_dict."""
        if not rule_code:
            return 0
        rule_type = frappe.db.get_value(
            "AL Calculation Rule", {"rule_code": rule_code}, "rule_type"
        )
        if rule_type == "LOOKUP":
            rule = frappe.db.get_value(
                "AL Calculation Rule",
                {"rule_code": rule_code},
                ["name", "lookup_key_1_var", "lookup_key_2_var", "lookup_default"],
                as_dict=True,
            )
            if rule:
                return self._evaluate_lookup(rule, inputs_dict)
        return 0
