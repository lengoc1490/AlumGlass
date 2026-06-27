"""
BomOrchestrator v17 — 6 bước + Module Hooks
Điều phối toàn bộ luồng tính giá BOM
"""
import frappe
import json
from frappe.utils import flt
from formula_builder.formula_utils import FormulaEngine

from alumglass.engine.module_registry import fire_hooks, get_registered_hooks
from alumglass.engine.variable_resolver import VariableResolver
from alumglass.engine.profile_interpreter import ProfileInterpreter
from alumglass.engine.pk_resolver import PkResolver
from alumglass.engine.cost_accumulator import CostAccumulator
from alumglass.engine.snapshot_builder import SnapshotBuilder


class BomOrchestrator:
    """Orchestrator chính — 6 bước + fire hooks.

    Usage:
        orch = BomOrchestrator()
        result = orch.run(quotation_item, bom_doc)
    """

    def __init__(self):
        self.variable_resolver = VariableResolver()
        self.profile_interpreter = ProfileInterpreter()
        self.pk_resolver = PkResolver()
        self.cost_accumulator = CostAccumulator()
        self.snapshot_builder = SnapshotBuilder()

    def run(self, quotation_item, bom_doc_name):
        """Chạy toàn bộ pipeline tính giá.

        Args:
            quotation_item: dict hoặc Quotation Item document
            bom_doc_name: Tên AL BOM

        Returns:
            dict: {
                "result": {...},          # Kết quả FormulaEngine
                "inputs": {...},          # inputs_dict đã dùng
                "formulas": [...],        # Tất cả formulas đã build
                "snapshot_name": "...",   # ConfigSnapshot name
                "warnings": [...],        # Cảnh báo
                "cost_summary": [...],    # Cost summary cho UI
                "discount_info": {...},   # Discount info (sau Hook A)
                "version_info": {...},    # BOM Version info (sau Hook B)
            }
        """
        warnings = []
        bom_doc = frappe.get_doc("AL BOM", bom_doc_name)

        # ============================================================
        # BƯỚC 1: VariableResolver.resolve()
        # ============================================================
        inputs_dict = self.variable_resolver.resolve(quotation_item, bom_doc)

        # ============================================================
        # BƯỚC 2: ProfileInterpreter.pass1_scan()
        # ============================================================
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        glass_selections = self._safe_json(quotation_item, "al_glass_selections")

        variable_registry, panel_counts = self.profile_interpreter.pass1_scan(
            profile_set.al_lines, inputs_dict, glass_selections
        )

        # ============================================================
        # BƯỚC 3: ProfileInterpreter.pass2_build()
        # ============================================================
        all_formulas, bucket_acc = self.profile_interpreter.pass2_build(
            profile_set.al_lines, inputs_dict, variable_registry,
            panel_counts, glass_selections,
            self._safe_json(quotation_item, "al_pk_overrides"),
        )

        # ============================================================
        # BƯỚC 4: PkResolver.build_formulas()
        # ============================================================
        pk_overrides = self._safe_json(quotation_item, "al_pk_overrides")
        formulas_pk, pk_warnings = self.pk_resolver.build_formulas(
            bom_doc, pk_overrides
        )
        all_formulas += formulas_pk
        warnings += pk_warnings

        # ============================================================
        # BƯỚC 5: CostAccumulator.build_bucket_and_template_formulas()
        # ============================================================
        cost_template = (
            quotation_item.get("al_cost_template_override")
            or getattr(quotation_item, "al_cost_template_override", None)
            or bom_doc.default_cost_template
        )
        formulas_cost = self.cost_accumulator.build_bucket_and_template_formulas(
            bucket_acc, cost_template
        )
        all_formulas += formulas_cost

        # ============================================================
        # BƯỚC 6: FormulaEngine.calculate() — DUY NHẤT 1 LẦN
        # ============================================================
        try:
            engine = FormulaEngine(
                formulas=all_formulas,
                context=inputs_dict,
                deterministic=True,
                on_error="raise",
            )
            result = engine.calculate()
        except Exception as e:
            frappe.log_error(title="FormulaEngine calculation failed", message=str(e))
            raise

        # SnapshotBuilder.persist()
        snapshot = self.snapshot_builder.persist(
            quotation_item=quotation_item,
            bom_doc=bom_doc,
            inputs_dict=inputs_dict,
            formulas=all_formulas,
            result=result,
            profile_set=profile_set,
            pk_overrides=pk_overrides,
        )

        # Ghi kết quả vào quotation_item
        self._write_results_to_quotation_item(quotation_item, result, cost_template, snapshot)

        # ============================================================
        # HOOK A-D: fire_hooks('after_calculate')
        # ============================================================
        fire_hooks(
            "after_calculate",
            result=result,
            quotation_item=quotation_item,
            bom_doc=bom_doc,
            inputs_dict=inputs_dict,
            snapshot=snapshot,
        )

        # Đọc lại quotation_item để lấy các field đã được hooks ghi
        discount_info = self._read_discount_info(quotation_item)
        version_info = self._read_version_info(quotation_item)

        # Cost summary cho UI
        cost_summary = self.cost_accumulator.get_cost_summary(result, cost_template)

        return {
            "result": result,
            "inputs": inputs_dict,
            "formulas": all_formulas,
            "snapshot_name": snapshot.name,
            "warnings": warnings,
            "cost_summary": cost_summary,
            "discount_info": discount_info,
            "version_info": version_info,
        }

    def explain(self, formula_name, quotation_item, bom_doc_name):
        """Giải thích 1 formula — dùng cho EnrichedExplain UI."""
        bom_doc = frappe.get_doc("AL BOM", bom_doc_name)
        inputs_dict = self.variable_resolver.resolve(quotation_item, bom_doc)

        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        glass_selections = self._safe_json(quotation_item, "al_glass_selections")
        variable_registry, panel_counts = self.profile_interpreter.pass1_scan(
            profile_set.al_lines, inputs_dict, glass_selections
        )
        all_formulas, bucket_acc = self.profile_interpreter.pass2_build(
            profile_set.al_lines, inputs_dict, variable_registry,
            panel_counts, glass_selections,
            self._safe_json(quotation_item, "al_pk_overrides"),
        )
        formulas_pk, _ = self.pk_resolver.build_formulas(
            bom_doc, self._safe_json(quotation_item, "al_pk_overrides")
        )
        all_formulas += formulas_pk

        cost_template = (
            quotation_item.get("al_cost_template_override")
            or getattr(quotation_item, "al_cost_template_override", None)
            or bom_doc.default_cost_template
        )
        all_formulas += self.cost_accumulator.build_bucket_and_template_formulas(
            bucket_acc, cost_template
        )

        try:
            engine = FormulaEngine(
                formulas=all_formulas,
                context=inputs_dict,
                deterministic=True,
                on_error="raise",
            )
            return engine.explain(formula_name)
        except Exception as e:
            frappe.log_error(title="Explain failed", message=str(e))
            return {"error": str(e)}

    # ============================================================
    # BOM DIALOG CONFIG
    # ============================================================

    def get_bom_dialog_config(self, bom_doc_name):
        """Trả về config cho BOM Dialog UI (Variable Set, KINH lines, PK lines)."""
        bom_doc = frappe.get_doc("AL BOM", bom_doc_name)

        # Variable Set
        variables = []
        if bom_doc.variable_set:
            details = frappe.get_all(
                "AL Variable Set Detail",
                filters={"parent": bom_doc.variable_set},
                fields=["variable", "is_required", "override_default", "depends_on", "sort_order"],
                order_by="sort_order asc",
            )
            for d in details:
                var = frappe.db.get_value(
                    "AL Variable Library", d.variable,
                    ["var_code", "var_label", "var_type", "default_val", "options", "ui_widget"],
                    as_dict=True,
                )
                if var:
                    variables.append({**var, **{
                        "is_required": d.is_required,
                        "override_default": d.override_default,
                        "depends_on": d.depends_on,
                        "sort_order": d.sort_order,
                    }})

        # KINH lines
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        kinh_lines = []
        for line in profile_set.al_lines:
            if line.line_type != "KINH":
                continue
            kinh_lines.append({
                "line_name": line.line_name,
                "prefix": line.ctx_inject_prefix,
                "default_glass": line.default_glass_master,
                "panel_override_allowed": line.panel_glass_override_allowed,
                "panel_count_formula": line.panel_count_formula,
            })

        # PK lines (từ PK Set)
        pk_lines = []
        if bom_doc.pk_set:
            pk_set = frappe.get_doc("AL PK Set", bom_doc.pk_set)
            for line in pk_set.al_pk_lines:
                pk_lines.append({
                    "item_code": line.item_code,
                    "item_name": frappe.db.get_value("Item", line.item_code, "item_name"),
                    "allow_substitute": line.allow_substitute,
                    "substitute_item_group": line.substitute_item_group,
                    "sl_formula": line.sl_formula,
                })

        # Cost templates available
        cost_templates = frappe.get_all(
            "AL Cost Template",
            filters={"product_type": bom_doc.product_type},
            fields=["name", "template_name"],
        )

        # BOM Version info
        version_info = None
        if bom_doc.current_version:
            ver = frappe.db.get_value(
                "AL BOM Version", bom_doc.current_version,
                ["name", "version_number", "published_on", "snapshot_hash"],
                as_dict=True,
            )
            if ver:
                version_info = ver

        return {
            "bom_code": bom_doc.name,
            "bom_name": bom_doc.bom_name,
            "product_type": bom_doc.product_type,
            "brand": bom_doc.brand,
            "variables": variables,
            "kinh_lines": kinh_lines,
            "pk_lines": pk_lines,
            "cost_templates": cost_templates,
            "default_cost_template": bom_doc.default_cost_template,
            "version_info": version_info,
        }

    # ============================================================
    # COPY FIELDS — QT → SO → SI
    # ============================================================

    AL_FIELDS_TO_COPY = [
        "al_bom", "al_W_mm", "al_H_mm", "al_mau_nhom",
        "al_bom_vars", "al_glass_selections", "al_pk_overrides",
        "al_cost_template_override",
        "al_vl_nhom", "al_vl_kinh", "al_vl_vtp", "al_vl_pk",
        "al_tong_vl", "al_gia_thanh", "al_gia_ban", "al_gia_vat",
        "al_don_gia_m2", "al_config_snapshot",
        # v17 fields
        "al_bom_version", "al_discount_rule", "al_discount_pct",
        "al_gia_thuong_mai", "al_approval_status", "al_approved_by",
        "al_approval_note",
    ]

    def copy_al_fields_to_so(self, doc, method):
        """Hook: khi tạo Sales Order từ Quotation → copy al_* fields."""
        self._copy_al_fields(doc, "Sales Order Item")

    def copy_al_fields_to_si(self, doc, method):
        """Hook: khi tạo Sales Invoice từ SO → copy al_* fields."""
        self._copy_al_fields(doc, "Sales Invoice Item")

    def _copy_al_fields(self, doc, target_item_doctype):
        """Copy al_* fields từ source item sang target item."""
        for item in doc.items:
            source_docname = item.get("prevdoc_docname") or item.get("quotation_item")
            if not source_docname:
                continue
            source = frappe.get_doc(item.get("prevdoc_doctype") or "Quotation Item", source_docname)
            for field in self.AL_FIELDS_TO_COPY:
                val = source.get(field)
                if val is not None:
                    item.set(field, val)
            # Mark source
            item.set("al_source_quotation_item", source_docname)

    # ============================================================
    # HELPERS
    # ============================================================

    def _write_results_to_quotation_item(self, qi, result, cost_template, snapshot):
        """Ghi kết quả vào quotation_item fields sau khi calculate."""
        updates = {
            "al_vl_nhom": flt(result.get("VL_NHOM", 0)),
            "al_vl_kinh": flt(result.get("VL_KINH", 0)),
            "al_vl_vtp": flt(result.get("VL_VTP", 0)),
            "al_vl_pk": flt(result.get("VL_PK", 0)),
            "al_tong_vl": flt(result.get("TONG_VL", 0)),
            "al_gia_thanh": flt(result.get("GIA_THANH", 0)),
            "al_gia_ban": flt(result.get("GIA_BAN", 0)),
            "al_gia_vat": flt(result.get("GIA_VAT", 0)),
            "al_don_gia_m2": flt(result.get("DON_GIA_M2", 0)),
            "al_config_snapshot": snapshot.name,
        }

        if hasattr(qi, "db_set"):
            for field, val in updates.items():
                qi.db_set(field, val)
        elif isinstance(qi, dict):
            qi.update(updates)

    def _read_discount_info(self, qi):
        """Đọc discount info từ quotation_item (sau Hook A)."""
        disc_pct = qi.get("al_discount_pct") or getattr(qi, "al_discount_pct", None)
        if disc_pct:
            return {
                "rule": qi.get("al_discount_rule") or getattr(qi, "al_discount_rule", None),
                "pct": flt(disc_pct),
                "gia_thuong_mai": flt(qi.get("al_gia_thuong_mai") or getattr(qi, "al_gia_thuong_mai", 0)),
            }
        return None

    def _read_version_info(self, qi):
        """Đọc version info từ quotation_item (sau Hook B)."""
        ver_name = qi.get("al_bom_version") or getattr(qi, "al_bom_version", None)
        if ver_name:
            ver = frappe.db.get_value(
                "AL BOM Version", ver_name,
                ["version_number", "published_on", "snapshot_hash"],
                as_dict=True,
            )
            return ver
        return None

    @staticmethod
    def _safe_json(doc_or_dict, fieldname):
        """Parse JSON field an toàn."""
        val = doc_or_dict.get(fieldname) if isinstance(doc_or_dict, dict) else getattr(doc_or_dict, fieldname, None)
        if isinstance(val, dict):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}


# ============================================================
# WHITELISTED API METHODS
# ============================================================

@frappe.whitelist()
def calculate_quotation_item(quotation_item_name, bom_doc_name):
    """API: Tính giá cho 1 Quotation Item.
    Gọi từ JS client khi Sales nhấn "Tính giá".
    """
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    orch = BomOrchestrator()
    return orch.run(qi, bom_doc_name)


@frappe.whitelist()
def get_bom_dialog_config(bom_doc_name):
    """API: Lấy config cho BOM Dialog UI."""
    orch = BomOrchestrator()
    return orch.get_bom_dialog_config(bom_doc_name)


@frappe.whitelist()
def get_explain_tree(formula_name, quotation_item_name, bom_doc_name):
    """API: Giải thích 1 formula — EnrichedExplain."""
    qi = frappe.get_doc("Quotation Item", quotation_item_name)
    orch = BomOrchestrator()
    return orch.explain(formula_name, qi, bom_doc_name)


@frappe.whitelist()
def copy_al_fields_to_so(doc, method=None):
    """Hook: Copy al_* fields khi tạo Sales Order từ Quotation."""
    orch = BomOrchestrator()
    orch.copy_al_fields_to_so(doc, method)


@frappe.whitelist()
def copy_al_fields_to_si(doc, method=None):
    """Hook: Copy al_* fields khi tạo Sales Invoice từ SO."""
    orch = BomOrchestrator()
    orch.copy_al_fields_to_si(doc, method)
