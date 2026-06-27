"""
ProfileInterpreter v2 — 2-pass: Scan → Build formulas
Xử lý al_lines (NHOM/KINH/VTP/PK) → sinh formula cho FormulaEngine DAG
"""
import frappe
from frappe.utils import flt
from collections import defaultdict
from alumglass.engine.rule_engine import RuleEngine


class ProfileInterpreter:
    """2-pass interpreter cho AL Profile Set.

    Pass 1: Scan tất cả dòng → đăng ký tên biến (variable_registry), panel_counts
    Pass 2: Build formulas dựa trên registry
    """

    def __init__(self):
        self.rule_engine = RuleEngine()

    # ============================================================
    # PASS 1 — SCAN
    # ============================================================

    def pass1_scan(self, al_lines, inputs_dict, glass_selections):
        """Quét tất cả dòng → đăng ký biến và đếm panel.

        Returns:
            tuple: (variable_registry, panel_counts)
        """
        variable_registry = {}
        panel_counts = {}

        for line in sorted(al_lines, key=lambda l: l.sort_order):
            if not self._is_active_line(line):
                continue
            slug = line.slug

            if line.line_type == "NHOM":
                variable_registry[slug] = [
                    f"{slug}_active",
                    f"{slug}_qty",
                    f"{slug}_kg",
                    f"{slug}_dg",
                    f"{slug}_tt",
                ]
            elif line.line_type == "KINH":
                prefix = line.ctx_inject_prefix
                N = self._eval_panel_count(line, inputs_dict)
                panel_counts[slug] = N
                if N == 1:
                    variables = [
                        f"{prefix}_W", f"{prefix}_H", f"{prefix}_qty",
                        f"{prefix}_glass_thick_mm", f"{prefix}_m2",
                        f"{prefix}_dg", f"{prefix}_tt", f"{prefix}_cut",
                        f"{prefix}_total_perimeter_m", f"{prefix}_total_m2",
                    ]
                else:
                    variables = []
                    for i in range(N):
                        variables += [
                            f"{prefix}_{i}_W", f"{prefix}_{i}_H",
                            f"{prefix}_{i}_glass_thick_mm",
                            f"{prefix}_{i}_m2", f"{prefix}_{i}_tt",
                        ]
                    variables += [f"{prefix}_total_perimeter_m", f"{prefix}_total_m2"]
                variable_registry[slug] = variables

            elif line.line_type == "VTP":
                variable_registry[slug] = [
                    f"{slug}_active", f"{slug}_qty", f"{slug}_dg", f"{slug}_tt",
                ]
            elif line.line_type == "PK":
                variable_registry[slug] = [
                    f"pk_{slug}_qty", f"pk_{slug}_dg", f"pk_{slug}_tt",
                ]

        return variable_registry, panel_counts

    # ============================================================
    # PASS 2 — BUILD
    # ============================================================

    def pass2_build(self, al_lines, inputs_dict, variable_registry,
                    panel_counts, glass_selections, pk_overrides):
        """Xây dựng tất cả formula cho FormulaEngine DAG.

        Returns:
            tuple: (all_formulas, bucket_acc)
        """
        formulas = []
        bucket_acc = defaultdict(list)
        all_panel_thick_vars = []

        for line in sorted(al_lines, key=lambda l: l.sort_order):
            if not self._is_active_line(line):
                continue
            slug = line.slug

            if line.line_type == "NHOM":
                formulas += self._build_nhom(line, slug, inputs_dict, bucket_acc)

            elif line.line_type == "KINH":
                N = panel_counts.get(slug, 1)
                prefix = line.ctx_inject_prefix
                new_formulas, thick_vars = self._build_kinh(
                    line, slug, prefix, N, inputs_dict,
                    glass_selections, bucket_acc,
                )
                formulas += new_formulas
                all_panel_thick_vars += thick_vars

            elif line.line_type == "VTP":
                formulas += self._build_vtp(line, slug, bucket_acc)

            elif line.line_type == "PK":
                formulas += self._build_pk_inline(line, slug, pk_overrides, bucket_acc)

        # Tổng hợp kính
        formulas += self._build_kinh_aggregates(al_lines, panel_counts)

        # max_glass_thick_mm
        if all_panel_thick_vars:
            formulas.append({
                "name": "max_glass_thick_mm",
                "formula": f"max({','.join(all_panel_thick_vars)})",
            })

        return formulas, bucket_acc

    # ============================================================
    # BUILD HELPERS — NHOM
    # ============================================================

    def _build_nhom(self, line, slug, inputs_dict, bucket_acc):
        """Sinh formula cho dòng NHOM."""
        formulas = []

        # Active condition
        show_cond = (line.show_condition or "").strip() or "True"
        formulas.append({"name": f"{slug}_active", "formula": show_cond})

        # Quantity
        if line.quantity_rule:
            qty_expr = self.rule_engine.resolve_rule(line.quantity_rule)
        else:
            qty_expr = line.qty_formula or "0"
        formulas.append({
            "name": f"{slug}_qty",
            "formula": f"IF({slug}_active, {qty_expr}, 0)",
        })

        # kg/m — từ Item
        kg_per_m = flt(frappe.db.get_value("Item", line.item_code, "al_kg_per_m") or 0)
        formulas.append({"name": f"{slug}_kg", "formula": str(kg_per_m)})

        # Đơn giá
        if line.price_type == "Fixed":
            dg_expr = str(flt(line.fixed_price or 0))
        elif line.price_type == "Rule" and line.price_rule:
            dg_expr = self.rule_engine.resolve_rule(line.price_rule, inputs_dict)
            if dg_expr is None:
                dg_expr = "0"
            dg_expr = str(dg_expr)
        else:
            # Item Price — dùng don_gia_nhom từ LOOKUP
            dg_expr = "don_gia_nhom"
        formulas.append({"name": f"{slug}_dg", "formula": str(dg_expr)})

        # Thành tiền
        formulas.append({
            "name": f"{slug}_tt",
            "formula": f"{slug}_qty * {slug}_kg * {slug}_dg",
        })

        # Bucket
        bucket = line.cost_bucket or "VL_NHOM"
        bucket_acc[bucket].append(f"{slug}_tt")
        return formulas

    # ============================================================
    # BUILD HELPERS — KINH
    # ============================================================

    def _build_kinh(self, line, slug, prefix, N, inputs_dict,
                    glass_selections, bucket_acc):
        """Sinh formula cho dòng KINH (với Panel Expansion)."""
        formulas = []
        all_thick_vars = []
        glass_thick_var = f"glass_thick_{prefix}"  # đã inject vào inputs_dict

        for i in range(N):
            p = f"{prefix}_{i}" if N > 1 else prefix

            # glass_thick từng panel
            panel_key = f"{prefix}__{i}" if N > 1 else prefix
            override_glass = glass_selections.get(panel_key)
            default_glass = glass_selections.get(prefix) or line.default_glass_master

            if override_glass and override_glass != default_glass:
                thick = flt(
                    frappe.db.get_value("AL Glass Master", override_glass, "total_thick_mm") or 0
                )
                formulas.append({"name": f"{p}_glass_thick_mm", "formula": str(thick)})
            else:
                formulas.append({"name": f"{p}_glass_thick_mm", "formula": glass_thick_var})
            all_thick_vars.append(f"{p}_glass_thick_mm")

            # Width
            if line.width_rule:
                w_expr = self.rule_engine.resolve_rule(line.width_rule)
            else:
                w_expr = line.width_formula or "W_mm"
            formulas.append({"name": f"{p}_W", "formula": str(w_expr)})

            # Height
            if line.height_rule:
                h_expr = self.rule_engine.resolve_rule(line.height_rule)
            else:
                h_expr = line.height_formula or "H_mm"
            formulas.append({"name": f"{p}_H", "formula": str(h_expr)})

            # Quantity per panel
            qty_expr = line.qty_per_panel_formula or "1"
            formulas.append({"name": f"{p}_qty", "formula": qty_expr})

            # Diện tích m²
            formulas.append({
                "name": f"{p}_m2",
                "formula": f"{p}_W * {p}_H / 1000000 * {p}_qty",
            })

            # Đơn giá kính
            glass_code = override_glass or default_glass
            dg = flt(self._get_glass_price(glass_code, line.price_list) or 0)
            formulas.append({"name": f"{p}_dg", "formula": str(dg)})

            # Thành tiền
            formulas.append({
                "name": f"{p}_tt",
                "formula": f"{p}_m2 * {p}_dg",
            })

            # Phí cắt kính
            cut_pct = flt(line.cut_fee_pct or 0)
            formulas.append({
                "name": f"{p}_cut",
                "formula": f"{p}_tt * {cut_pct / 100:.6f}",
            })

            bucket_acc["VL_KINH"].append(f"{p}_tt")
            bucket_acc["OH_CUT_KINH"].append(f"{p}_cut")

        return formulas, all_thick_vars

    def _build_kinh_aggregates(self, al_lines, panel_counts):
        """Sinh formula tổng hợp cho từng prefix kính và ALL_KINH."""
        formulas = []
        all_prefixes = []

        for line in al_lines:
            if line.line_type != "KINH" or not self._is_active_line(line):
                continue
            prefix = line.ctx_inject_prefix
            slug = line.slug
            N = panel_counts.get(slug, 1)
            all_prefixes.append(prefix)

            if N == 1:
                formulas.append({
                    "name": f"{prefix}_total_perimeter_m",
                    "formula": f"({prefix}_W + {prefix}_H) / 1000",
                })
                formulas.append({
                    "name": f"{prefix}_total_m2",
                    "formula": f"{prefix}_m2",
                })
                formulas.append({
                    "name": f"{prefix}_total_qty",
                    "formula": f"{prefix}_qty",
                })
            else:
                perim_parts = [f"({prefix}_{i}_W + {prefix}_{i}_H)/1000" for i in range(N)]
                m2_parts = [f"{prefix}_{i}_m2" for i in range(N)]
                formulas.append({
                    "name": f"{prefix}_total_perimeter_m",
                    "formula": " + ".join(perim_parts),
                })
                formulas.append({
                    "name": f"{prefix}_total_m2",
                    "formula": " + ".join(m2_parts),
                })

        # ALL_KINH aggregates
        if all_prefixes:
            formulas.append({
                "name": "ALL_KINH_total_perimeter_m",
                "formula": " + ".join(f"{p}_total_perimeter_m" for p in all_prefixes),
            })
            formulas.append({
                "name": "ALL_KINH_total_m2",
                "formula": " + ".join(f"{p}_total_m2" for p in all_prefixes),
            })

        return formulas

    # ============================================================
    # BUILD HELPERS — VTP
    # ============================================================

    def _build_vtp(self, line, slug, bucket_acc):
        """Sinh formula cho dòng VTP."""
        formulas = []
        show_cond = (line.show_condition or "").strip() or "True"
        formulas.append({"name": f"{slug}_active", "formula": show_cond})

        if line.quantity_rule:
            qty_expr = self.rule_engine.resolve_rule(line.quantity_rule)
        else:
            qty_expr = line.qty_formula or "0"
        formulas.append({
            "name": f"{slug}_qty",
            "formula": f"IF({slug}_active, {qty_expr}, 0)",
        })

        # Đơn giá
        if line.price_type == "Fixed":
            dg_expr = str(flt(line.fixed_price or 0))
        elif line.price_type == "Rule" and line.price_rule:
            dg_expr = str(self.rule_engine.resolve_rule(line.price_rule) or "0")
        else:
            dg = flt(self._get_item_price(line.item_code, line.price_list) or 0)
            dg_expr = str(dg)
        formulas.append({"name": f"{slug}_dg", "formula": dg_expr})

        formulas.append({
            "name": f"{slug}_tt",
            "formula": f"{slug}_qty * {slug}_dg",
        })

        bucket = line.cost_bucket or "VL_VTP"
        bucket_acc[bucket].append(f"{slug}_tt")
        return formulas

    # ============================================================
    # BUILD HELPERS — PK INLINE
    # ============================================================

    def _build_pk_inline(self, line, slug, pk_overrides, bucket_acc):
        """Sinh formula cho dòng PK inline."""
        formulas = []

        # Xác định item thực tế
        item_code = line.item_code
        if line.allow_substitute and pk_overrides.get(line.item_code):
            override_item = pk_overrides[line.item_code]
            # Validate: phải cùng item_group
            if line.substitute_item_group:
                actual_group = frappe.db.get_value("Item", override_item, "item_group")
                if actual_group == line.substitute_item_group:
                    item_code = override_item
                else:
                    frappe.log_error(
                        f"PK substitute validation failed: {override_item} not in group {line.substitute_item_group}"
                    )
            else:
                item_code = override_item

        # Số lượng
        sl_expr = line.sl_formula or "1"
        formulas.append({"name": f"pk_{slug}_qty", "formula": sl_expr})

        # Đơn giá
        dg = flt(self._get_item_price(item_code, line.price_list) or 0)
        formulas.append({"name": f"pk_{slug}_dg", "formula": str(dg)})

        # Thành tiền
        formulas.append({
            "name": f"pk_{slug}_tt",
            "formula": f"pk_{slug}_qty * pk_{slug}_dg",
        })

        bucket_acc["VL_PK"].append(f"pk_{slug}_tt")
        return formulas

    # ============================================================
    # UTILITY
    # ============================================================

    def _is_active_line(self, line):
        """Kiểm tra dòng có active không."""
        return getattr(line, "is_active", 1) == 1

    def _eval_panel_count(self, line, inputs_dict):
        """Đánh giá panel_count_formula → số panel."""
        formula = (line.panel_count_formula or "").strip()
        if not formula:
            return 1
        # Chỉ tham chiếu biến priority ≤ 40 từ inputs_dict
        try:
            ctx = {k: v for k, v in inputs_dict.items()}
            # Security: restricted eval with only numbers and basic operators
            allowed_names = {
                k: v for k, v in ctx.items()
                if isinstance(v, (int, float))
            }
            allowed_names.update({
                "int": int, "float": float,
                "round": round, "max": max, "min": min,
                "abs": abs,
            })
            result = eval(formula, {"__builtins__": {}}, allowed_names)
            return max(1, int(flt(result)))
        except Exception as e:
            frappe.log_error(f"Panel count eval failed: {formula} — {e}")
            return 1

    def _get_glass_price(self, glass_code, price_list=None):
        """Lấy đơn giá kính từ Item Price."""
        if not glass_code:
            return 0
        # Tìm item kính từ glass master
        item_code = frappe.db.get_value(
            "Item", {"al_glass_master": glass_code}, "name"
        )
        if not item_code:
            # Fallback: glass_code might be item_code itself
            item_code = glass_code
        return self._get_item_price(item_code, price_list)

    def _get_item_price(self, item_code, price_list=None):
        """Lấy đơn giá item từ Item Price."""
        if not item_code:
            return 0
        filters = {"item_code": item_code}
        if price_list:
            filters["price_list"] = price_list
        else:
            # Ưu tiên Standard Selling
            filters["selling"] = 1
        price = frappe.db.get_value(
            "Item Price",
            filters,
            "price_list_rate",
            order_by="valid_from desc",
        )
        return flt(price or 0)

    def _eval_rule_as_formula(self, rule_code):
        """Resolve rule → formula string cho FormulaEngine."""
        result = self.rule_engine.resolve_rule(rule_code)
        if result is None:
            return "0"
        return str(result)
