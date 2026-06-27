"""
CostAccumulator v3 — P1+P2: Formula Set + FlexibleFormulaEngine

P1: AL Cost Template có thể reference 1 Formula Set (field: formula_set).
     Khi có formula_set → evaluate Formula Set thay vì build lines thủ công.
P2: Bucket formulas + cost template formulas được merge vào FlexibleFormulaEngine
     thay vì build danh sách [{name, formula}] thủ công.
"""
import frappe
import json
from frappe.utils import flt


class CostAccumulator:
    """Build bucket formulas và cost template formulas cho FormulaEngine.

    v3 changes (P1+P2):
    - Hỗ trợ formula_set field trên AL Cost Template (P1)
    - Dùng FlexibleFormulaEngine để evaluate cost template (P2)
    - Fallback: build thủ công như cũ nếu không có FB
    """

    def build_bucket_and_template_formulas(self, bucket_acc, cost_template_name):
        """Build tất cả formulas: bucket sums + cost template.

        Args:
            bucket_acc: defaultdict(list), key = bucket_code, value = list of var names
            cost_template_name: Tên AL Cost Template

        Returns:
            list: [{name, formula}] cho FormulaEngine DAG
        """
        formulas = []

        # ============================
        # 1. BUILD BUCKET FORMULAS (giữ nguyên — đơn giản)
        # ============================
        for bucket_code, var_list in bucket_acc.items():
            if var_list:
                formulas.append({
                    "name": bucket_code,
                    "formula": " + ".join(var_list),
                })

        if not cost_template_name:
            return formulas

        # ============================
        # 2. BUILD COST TEMPLATE FORMULAS
        # ============================

        # P1: Kiểm tra xem Cost Template có reference Formula Set không
        formula_set_code = frappe.db.get_value(
            "AL Cost Template", cost_template_name, "formula_set"
        )

        if formula_set_code:
            # === P1 PATH: Dùng Formula Set ===
            fs_formulas = self._get_formula_set_formulas(formula_set_code)
            if fs_formulas:
                formulas += fs_formulas
                return formulas
            # Fallback nếu Formula Set không có formulas

        # === P2 PATH: Dùng FlexibleFormulaEngine ===
        try:
            fe_formulas = self._build_via_flexible_engine(cost_template_name)
            if fe_formulas:
                formulas += fe_formulas
                return formulas
        except Exception as e:
            frappe.log_error(
                title="FlexibleFormulaEngine fallback — using manual build",
                message=str(e),
            )

        # === LEGACY PATH: Build thủ công ===
        template_lines = frappe.get_all(
            "AL Cost Template Line",
            filters={"parent": cost_template_name},
            fields=["line_code", "calc_formula", "sort_order"],
            order_by="sort_order asc",
        )

        for line in template_lines:
            if not line.calc_formula:
                continue
            formula_name = line.line_code or f"cost_line_{line.sort_order}"
            formulas.append({
                "name": formula_name,
                "formula": line.calc_formula,
            })

        return formulas

    # ============================================================
    # P1: Formula Set integration
    # ============================================================

    def _get_formula_set_formulas(self, formula_set_code):
        """Lấy formulas từ Formula Set của formula_builder.

        Returns:
            list of {name, formula} hoặc [] nếu không tìm thấy
        """
        try:
            lines = frappe.get_all(
                "Formula Set Line",
                filters={"parent": formula_set_code},
                fields=["var_name", "formula"],
                order_by="idx asc",
            )
            if lines:
                return [
                    {"name": ln.var_name, "formula": ln.formula}
                    for ln in lines
                ]
        except Exception as e:
            frappe.log_error(
                title=f"Formula Set read failed: {formula_set_code}",
                message=str(e),
            )
        return []

    # ============================================================
    # P2: FlexibleFormulaEngine integration
    # ============================================================

    def _build_via_flexible_engine(self, cost_template_name):
        """Dùng FlexibleFormulaEngine để evaluate cost template.

        Returns:
            list of {name, formula} hoặc [] nếu không thể dùng FB
        """
        try:
            from formula_builder.integration import (
                FlexibleFormulaEngine, EngineConfig, ChildTableConfig,
            )
        except ImportError:
            return []

        # Lấy cost template lines
        lines = frappe.get_all(
            "AL Cost Template Line",
            filters={"parent": cost_template_name},
            fields=["line_code", "calc_formula", "sort_order"],
            order_by="sort_order asc",
        )
        if not lines:
            return []

        # Convert thành định dạng cho FlexibleFormulaEngine
        rows = []
        for ln in lines:
            if not ln.calc_formula:
                continue
            rows.append({
                "line_code": ln.line_code or f"line_{ln.sort_order}",
                "calc_formula": ln.calc_formula,
            })

        if not rows:
            return []

        # Validate formulas (static AST check)
        try:
            engine = FlexibleFormulaEngine(EngineConfig(
                child_tables=[
                    ChildTableConfig(
                        table_key="cost_lines",
                        formula_field="calc_formula",
                        id_field="line_code",
                        row_fields=[],          # auto-detect
                        output_field=None,       # read-only
                        skip_empty_formula=True,
                    ),
                ],
                deterministic=True,
                on_error="raise",
            ))
            engine.validate_formulas({"cost_lines": rows})
        except Exception as e:
            frappe.log_error(
                title=f"Cost template validation failed: {cost_template_name}",
                message=str(e),
            )
            # Fallback: vẫn có thể tiếp tục với manual build

        # Trả về formulas cho FormulaEngine DAG chính
        formulas = []
        for row in rows:
            formulas.append({
                "name": row["line_code"],
                "formula": row["calc_formula"],
            })

        return formulas

    # ============================================================
    # DISPLAY HELPERS (giữ nguyên)
    # ============================================================

    def get_template_display_lines(self, cost_template_name):
        """Trả về danh sách dòng cost template để hiển thị UI."""
        if not cost_template_name:
            return []

        return frappe.get_all(
            "AL Cost Template Line",
            filters={"parent": cost_template_name},
            fields=[
                "sort_order", "line_code", "line_label",
                "cost_bucket", "is_subtotal", "show_on_quotation",
            ],
            order_by="sort_order asc",
        )

    def get_cost_summary(self, result, cost_template_name):
        """Từ kết quả FormulaEngine, tạo summary theo cost template structure."""
        display_lines = self.get_template_display_lines(cost_template_name)
        summary = []
        for line in display_lines:
            if not line.show_on_quotation:
                continue
            line_code = line.line_code
            value = flt(result.get(line_code, 0))
            summary.append({
                "label": line.line_label,
                "code": line_code,
                "value": value,
                "is_subtotal": line.is_subtotal,
                "sort_order": line.sort_order,
            })
        return sorted(summary, key=lambda x: x["sort_order"])
