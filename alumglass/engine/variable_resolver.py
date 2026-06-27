"""
VariableResolver v3 — P0: Dùng Formula Variable Binding + DAG topology
Kế thừa glass_thick injection từ v2. Tận dụng data_source_registry của FB.
"""
import frappe
import json
from frappe.utils import flt


class VariableResolver:
    """Resolve tất cả biến cần cho BOM calculation thành inputs_dict.

    v3 changes (P0):
    - Sử dụng Formula Variable Binding (FB native) thay vì AL Variable Binding
    - Binding được resolve theo topological order (Kahn's algorithm)
    - AL-specific source types (bom_variable, rule_engine_lookup) đăng ký
      qua custom handler trong fb_handlers.py
    - Fallback sang AL Variable Binding cũ nếu FB không available
    """

    def resolve(self, quotation_item, bom_doc):
        """Bước 1 của BomOrchestrator: tạo inputs_dict đầy đủ.

        Args:
            quotation_item: Quotation Item document (dict hoặc Document)
            bom_doc: AL BOM document

        Returns:
            dict: inputs_dict với tất cả biến đã resolve
        """
        # Bước 1: Resolve biến qua Formula Variable Binding (DAG topo)
        inputs_dict = self._resolve_bindings(quotation_item, bom_doc)

        # Bước 2: Inject glass_thick cho mọi dòng KINH (GIỮ NGUYÊN từ v2)
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        glass_selections = self._safe_json(quotation_item, "al_glass_selections")

        for line in profile_set.al_lines:
            if line.line_type != "KINH":
                continue
            prefix = line.ctx_inject_prefix
            glass_code = glass_selections.get(prefix) or line.default_glass_master
            if glass_code:
                thick = frappe.db.get_value(
                    "AL Glass Master", glass_code, "total_thick_mm"
                ) or 0
                inputs_dict[f"glass_thick_{prefix}"] = flt(thick)

        return inputs_dict

    def _resolve_bindings(self, quotation_item, bom_doc):
        """Resolve biến: ưu tiên dùng Formula Variable Binding (FB DAG),
        fallback sang AL Variable Binding nếu FB không khả dụng."""
        inputs = {}

        # === PRIMARY: Formula Variable Binding (FB native, có DAG) ===
        fb_bindings = frappe.get_all(
            "Formula Variable Binding",
            filters={"is_active": 1},
            fields=["*"],
        )
        if fb_bindings:
            try:
                from formula_builder.api.data_source_registry import (
                    resolve_bindings_with_deps,
                )
                # FB resolve với topological sort
                fb_result = resolve_bindings_with_deps(fb_bindings, quotation_item)
                inputs.update(fb_result)
            except ImportError:
                frappe.logger().warning(
                    "VariableResolver: formula_builder.data_source_registry "
                    "not available, falling back to AL Variable Binding"
                )
            except Exception as e:
                frappe.log_error(
                    title="FB resolve_bindings_with_deps failed",
                    message=str(e),
                )

        # === FALLBACK: AL Variable Binding (legacy, priority tuần tự) ===
        # Chỉ chạy nếu có AL Variable Binding records và FB không resolve được
        al_bindings = frappe.get_all(
            "AL Variable Binding",
            filters={"is_active": 1},
            fields=["*"],
            order_by="resolve_priority asc",
        )
        for b in al_bindings:
            var_name = b.variable_name
            if var_name not in inputs:  # Không ghi đè FB result
                val = self._resolve_legacy_binding(b, quotation_item, bom_doc)
                if val is not None:
                    inputs[var_name] = val

        # === BOM Variables (từ AL Variable Set) ===
        if bom_doc.variable_set:
            inputs.update(
                self._resolve_bom_variables(bom_doc, quotation_item)
            )

        # === Quotation inputs trực tiếp ===
        inputs.update(
            self._resolve_quotation_inputs(quotation_item)
        )

        return inputs

    def _resolve_legacy_binding(self, binding, quotation_item, bom_doc):
        """Resolve 1 AL Variable Binding cũ (legacy fallback)."""
        source_type = binding.source_type
        config = self._safe_json_parse(binding.source_config)

        if source_type == "Quotation Input":
            fieldname = config.get("fieldname", "")
            return quotation_item.get(fieldname)
        elif source_type == "BOM Variable":
            var_code = config.get("var_code", "")
            override_json = self._safe_json(quotation_item, "al_bom_vars")
            return override_json.get(var_code)
        elif source_type == "BOM Attribute":
            attr = config.get("attribute", "")
            return bom_doc.get(attr)
        elif source_type == "Rule Engine Result":
            return self._eval_lookup_rule(config, quotation_item, bom_doc)
        elif source_type == "Computed":
            return self._eval_simple_formula(config.get("formula", ""))
        elif source_type == "Context Inject":
            return None
        elif source_type == "Constant":
            return config.get("value")
        return None

    def _eval_lookup_rule(self, config, quotation_item, bom_doc):
        """Đánh giá Rule LOOKUP (legacy fallback)."""
        rule_code = config.get("rule_code", "")
        args_dict = config.get("args", {})
        if not rule_code:
            return None

        rule_name = frappe.db.get_value(
            "AL Calculation Rule",
            {"rule_code": rule_code, "rule_type": "LOOKUP", "is_active": 1},
            "name",
        )
        if not rule_name:
            return None

        # Build key values
        key_values = {}
        for arg_name, arg_source in args_dict.items():
            if isinstance(arg_source, str):
                if arg_source.startswith("qi."):
                    key_values[arg_name] = quotation_item.get(arg_source[3:])
                elif arg_source.startswith("bom."):
                    key_values[arg_name] = bom_doc.get(arg_source[4:])
                else:
                    key_values[arg_name] = arg_source
            else:
                key_values[arg_name] = arg_source

        lookup_rows = frappe.get_all(
            "AL Rule Lookup Row",
            filters={"parent": rule_name},
            fields=["key_1", "key_2", "key_3", "result_value"],
        )

        for row in lookup_rows:
            match = True
            for i in range(1, 4):
                if (key_values.get(f"key_{i}") and row.get(f"key_{i}")
                        and str(key_values[f"key_{i}"]) != str(row[f"key_{i}"])):
                    match = False
                    break
            if match:
                return self._cast_value(row.result_value)

        default = frappe.db.get_value(
            "AL Calculation Rule", rule_name, "lookup_default"
        )
        return self._cast_value(default)

    def _resolve_bom_variables(self, bom_doc, quotation_item):
        """Resolve biến từ AL Variable Set Detail (giữ nguyên)."""
        result = {}
        override_vars = self._safe_json(quotation_item, "al_bom_vars")

        details = frappe.get_all(
            "AL Variable Set Detail",
            filters={"parent": bom_doc.variable_set},
            fields=["variable", "override_default", "sort_order"],
            order_by="sort_order asc",
        )

        for d in details:
            var = frappe.db.get_value(
                "AL Variable Library",
                d.variable,
                ["var_code", "default_val", "var_type"],
                as_dict=True,
            )
            if not var:
                continue

            val = (
                override_vars.get(var.var_code)
                or d.override_default
                or var.default_val
            )
            if val is not None:
                result[var.var_code] = self._cast_value(val, var.var_type)

        return result

    def _resolve_quotation_inputs(self, quotation_item):
        """Resolve các input trực tiếp từ quotation_item fields."""
        result = {}
        direct_fields = {
            "al_W_mm": "W_mm",
            "al_H_mm": "H_mm",
            "al_mau_nhom": "mau_nhom",
            "qty": "qty",
        }
        for qi_field, var_name in direct_fields.items():
            val = quotation_item.get(qi_field)
            if val is not None:
                result[var_name] = flt(val) if qi_field != "al_mau_nhom" else val

        W_mm = flt(quotation_item.get("al_W_mm", 0))
        H_mm = flt(quotation_item.get("al_H_mm", 0))
        if W_mm:
            result["W_m"] = W_mm / 1000.0
        if H_mm:
            result["H_m"] = H_mm / 1000.0

        return result

    def _eval_simple_formula(self, formula):
        """Đánh giá công thức số học đơn giản (legacy fallback)."""
        if not formula:
            return None
        allowed = set("0123456789.+-*/() _")
        if not all(c in allowed for c in formula.replace(" ", "")):
            return None
        try:
            return flt(eval(formula, {"__builtins__": {}}, {}))
        except Exception:
            return None

    def _cast_value(self, val, var_type=None):
        """Chuyển đổi giá trị về đúng kiểu."""
        if val is None:
            return None
        if var_type in ("FLOAT", "Float"):
            return flt(val)
        elif var_type in ("INT", "Integer"):
            return int(flt(val))
        elif var_type in ("BOOL", "Check"):
            if isinstance(val, str):
                return val.lower() in ("1", "true", "yes")
            return bool(val)
        return val

    @staticmethod
    def _safe_json(doc_or_dict, fieldname):
        val = (doc_or_dict.get(fieldname) if isinstance(doc_or_dict, dict)
               else getattr(doc_or_dict, fieldname, None))
        return VariableResolver._safe_json_parse(val)

    @staticmethod
    def _safe_json_parse(val):
        if isinstance(val, dict):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
