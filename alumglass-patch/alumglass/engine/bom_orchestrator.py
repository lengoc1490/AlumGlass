"""BomOrchestrator — Engine tính BOM config-driven, dùng Formula Builder.

NGUYÊN TẮC: AlumGlass chỉ config, không hardcode nghiệp vụ.
- Mọi logic đến từ DB: Bom Item, Cost Bucket, Cost Template, Profile System, Product Type.
- Tính toán ủy thác cho Formula Builder: FormulaEngine (Bom Items) + FlexibleFormulaEngine (Cost Template).
- Engine này chỉ làm: đọc config → resolve biến → build formulas → gọi FB → lưu kết quả.

Flow 7 phase:
  B0: Version pinning
  B1: Gather inputs (al_bom_vars + scoped vars từ DB — data-driven)
  B2: Pre-fetch master data (batch query)
  B3: Build formula list cho FormulaEngine (FB)
  B4: Calculate Bom Items qua FormulaEngine (DAG + topo sort)
  B5: Aggregate cost buckets (Python loop)
  B6: Calculate Cost Template qua FlexibleFormulaEngine (FB)
  B7: Save results (single commit)
"""
import ast
import frappe
import json
import re
import math
from collections import defaultdict


# ── SAFE FUNCS dùng chung B4 + B6 (inject vào FormulaEngine / FlexibleFormulaEngine) ──
def _lookup_rule(rule_code, input_value=None):
    """Tra cứu AL Calculation Rule. Hỗ trợ CONSTANT, THRESHOLD, LOOKUP.

    Module-level để B4 (FormulaEngine.safe_funcs) và B6
    (FlexibleFormulaEngine.EngineConfig.custom_functions) dùng CHUNG một
    implementation — tránh duplicate + đảm bảo 2 phase resolve rule giống nhau.
    """
    try:
        rule = frappe.get_cached_doc("AL Calculation Rule", rule_code)
        result = rule.resolve(input_value)
        return result if result is not None else 0
    except frappe.DoesNotExistError:
        return 0


def _roundup(x, y):
    """Làm tròn lên (mirror seed config roundup = math.ceil)."""
    return math.ceil(x)


# ── TRACE (V6 P7/P8 — Phase 0b/1e): build trace thay token bằng giá trị ──
# Chung cho engine (B4 line vật tư + B6 cost template) và api (get_result_display
# fallback trace data cũ). Token không có trong ctx → giữ nguyên tên (trailing
# input / hàm lookup_rule). Số float round 4 chữ số.
_TRACE_TOKEN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{1,40})\b")


def _round_num(v):
    """Round float 4 chữ số cho trace; giữ nguyên int."""
    if isinstance(v, float):
        return round(v, 4)
    return v


def _default_price_list():
    """Price list mặc định — đọc từ Selling Settings (chuẩn Frappe/ERPNext),
    KHÔNG hardcode 'Standard Selling'. Fallback 'Standard Selling' chỉ khi
    Selling Settings chưa cấu hình (giữ hành vi cũ cho site mới/demo).
    Đồng bộ với fb_handlers.py (đã configurable qua source_config từ trước).
    """
    return frappe.db.get_single_value(
        "Selling Settings", "selling_price_list") or "Standard Selling"


def _build_trace(formula, ctx):
    """Trace dạng string: formula → thay token bằng giá trị ĐÃ DÙNG khi tính.

    V6 P7/P8: thay MỌI token có giá trị số trong ctx (kể cả line-code cost
    template / bucket — chính là giá trị đã resolve) → trace đọc được
    "8% × TONG_VL(1,000,000) = 80,000" (JS renderer định dạng % + dấu phẩy).
    """
    if not formula:
        return ""

    def _sub(m):
        token = m.group(1)
        if token in ctx and isinstance(ctx[token], (int, float)):
            return f"{token}={_round_num(ctx[token])}"
        return token

    return _TRACE_TOKEN.sub(_sub, formula)


# ── Phase 0b: Biến phần trăm lưu phần trăm nguyên (8/12/16/3/3/10) ──────
# Engine chia 100 → 0.08 trước khi dùng. Nhận diện theo suffix tên var:
#   *_PCT (NC_SX_PCT, OH_VC_PCT, OH_QLY_PCT), *_MARGIN (PROFIT_MARGIN),
#   *_RATE (VAT_RATE).
_PERCENT_VAR_SUFFIXES = ("_PCT", "_MARGIN", "_RATE")


# ── CONFIG: Các field kết quả ghi vào Quotation Item ─────────────────
OUTPUT_FIELDS = [
    "al_gia_vat", "al_gia_ban", "al_bom_result",
]

# ── DEFAULT: Các field trong Bom Item chứa công thức ─────────────────
# Dùng khi Bom Set không có formula_fieldnames config
DEFAULT_FORMULA_FIELDS = ["width", "height", "qty", "show_condition",
                           "item_condition_formula", "rule_input_expr"]


class BomOrchestrator:
    """Engine tính BOM 7-phase, hoàn toàn config-driven."""

    def __init__(self, quotation_item_name):
        self.quotation_item_name = quotation_item_name
        self.inputs = {}
        self.bom_items = []
        self.row_literals = {}
        self.bom_result = []
        self.buckets = defaultdict(float)
        self.cost_result = {}
        self.cost_template_trace = {}   # V6 P8: line_code → trace (build lúc tính)
        self.gia_vat = 0
        # B5 FB-max: lỗi structured từ engine (B4/B6) — lưu trong al_bom_result
        self.bom_engine_errors = {}
        self.cost_engine_errors = {}
        # Cached references (tránh load lại)
        self._qi_doc = None
        self._bom_doc = None
        self._formula_fieldnames = None
        self._dim_fieldname_cache = None   # Cache composite key field mapping
        self._dim_mapping_raw_cache = None  # V6 P10: cache mapping thô (chưa lọc category)
        self._line_formulas = defaultdict(dict)  # V6 P8: slug → {field: formula} (trace line vật tư)
        # V6 P4 (A5/A7): override config từ al_bom_vars — set trong b1.
        # Mọi override đều OPT-IN — không có key → giữ nguyên 100% hành vi cũ.
        self.accessory_set_code = None
        self.glass_master_override = None
        self.glass_master_map = {}
        self.profile_system_override = None
        self.cost_template_override = None
        # V6 P5 (Phase 1c): giá trị từ child table system_variables của AL Profile
        # System — áp lại sau FB binding (FB đọc offset_* field).
        self._profile_child_vars = {}

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════
    def run(self):
        self.b0_version_pinning()
        self.b1_gather_inputs()
        self.b2_prefetch_master_data()
        self.b3_build_formulas()
        self.b4_calculate_bom_items()
        self.b5_aggregate_cost_buckets()
        self.b6_calculate_cost_template()
        self.b7_save_results()
        return self._build_response()

    # ══════════════════════════════════════════════════════════════════
    # B0: Version Pinning
    # ══════════════════════════════════════════════════════════════════
    def b0_version_pinning(self):
        self._qi_doc = frappe.get_doc("Quotation Item", self.quotation_item_name)
        self.bom_code = self._qi_doc.get("al_bom")
        self.bom_version_name = self._qi_doc.get("al_bom_version")

        if self.bom_version_name:
            # get_cached_doc: snapshot docs are read-only, safe to cache
            self.bom_version = frappe.get_cached_doc(
                "AL BOM Version", self.bom_version_name)
        elif self.bom_code:
            self._bom_doc = frappe.get_cached_doc("AL BOM", self.bom_code)
            if self._bom_doc.current_version:
                self.bom_version = frappe.get_cached_doc(
                    "AL BOM Version", self._bom_doc.current_version)
                self.bom_version_name = self._bom_doc.current_version
            else:
                # V6 Phase 4: auto-create version Published từ BOM gốc +
                # set current_version trên AL BOM + pin al_bom_version vào
                # Quotation Item. Backward-compat: BOM đã có version → giữ
                # nguyên (nhánh trên). Rule live (BOM không version) vẫn dùng
                # cấu hình trực tiếp (engine không chết, tự tạo lần đầu).
                self.bom_version = self._auto_create_bom_version()
                self.bom_version_name = self.bom_version.name

    def _auto_create_bom_version(self):
        """B0 Phase 4: tạo AL BOM Version Published từ BOM gốc + pin.

        `before_insert` snapshot BOM Set + Cost Template + Pricing Dimension;
        `on_update` (Published) set `current_version` trên AL BOM. Pin
        `al_bom_version` vào Quotation Item — cùng transaction, commit ở B7.
        """
        from alumglass.al_bom_engine.doctype.al_bom.al_bom import create_bom_version_doc
        version = create_bom_version_doc(self.bom_code, workflow_state="Published")
        if self._qi_doc:
            frappe.db.set_value(
                "Quotation Item", self.quotation_item_name,
                "al_bom_version", version.name)
        return version

    # ══════════════════════════════════════════════════════════════════
    # B1: Gather Inputs — đọc từ al_bom_vars JSON + resolve system vars
    # ══════════════════════════════════════════════════════════════════
    def b1_gather_inputs(self):
        # ── 1.1 Đọc user inputs từ al_bom_vars JSON (đã có trong _qi_doc) ──
        bom_vars_str = self._qi_doc.get("al_bom_vars")
        bom_vars = {}
        if bom_vars_str:
            try:
                bom_vars = json.loads(bom_vars_str) if isinstance(
                    bom_vars_str, str) else bom_vars_str
            except json.JSONDecodeError:
                pass

        self.inputs.update(bom_vars.get("extra_vars", {}) if isinstance(
            bom_vars.get("extra_vars"), dict) else {})

        # ── 1.2 Global Variables từ Formula Builder ──────────────────
        for gv in frappe.get_all("Formula Global Variable",
                                  fields=["var_name", "constant_value"]):
            try:
                self.inputs[gv["var_name"]] = float(gv["constant_value"])
            except (ValueError, TypeError):
                self.inputs[gv["var_name"]] = gv["constant_value"]

        # ── 1.3 Resolve system variables từ AL Variable Library ──────
        #     (fallback backward-compat — B1 FB-max: FB override khi FVB đã seed)
        self._resolve_system_variables()

        # ── 1.4 FB-max (B1): nối get_live_context — global binding + system
        #     variable resolve tự động (topological sort + fallback default_value).
        #     FVB chưa seed (D3) → get_live_context trả ít/không binding → giữ
        #     resolver cũ ở 1.3. FB override Variable Library (nguồn chính FB).
        fb_ctx = self._resolve_fb_context()
        for key, value in fb_ctx.items():
            self.inputs[key] = value

        # ── 1.4b V6 P5 (Phase 1c): child table system_variables ưu tiên hơn
        #     FB binding tự resolve (FB đọc source_field/offset_* của profile).
        #     Child table = config tường minh theo profile → ghi đè sau cùng
        #     (trước bom_vars user input — user input vẫn thắng cuối cùng).
        for key, value in self._profile_child_vars.items():
            self.inputs[key] = value

        # ── 1.5 Merge user input values (bom_vars ghi đè) ────────────
        for key in list(bom_vars.keys()):
            if key not in ("extra_vars", "accessory_set", "glass_master"):
                self.inputs[key] = bom_vars[key]

        # ── 1.5b Capture override config từ al_bom_vars (V6 P4: A5/A7) ──
        # `_accessory_set`/`_profile_system`/`_cost_template` (Phase 1 convention
        # underscore-prefix) + `glass_master` (user var, không vào inputs).
        # Fallback `accessory_set` (convention cũ). Mọi override OPT-IN — không
        # có key → giữ nguyên 100% hành vi cũ (golden 2C/4C không đổi).
        self.accessory_set_code = None
        self.glass_master_override = None
        self.glass_master_map = {}
        self.profile_system_override = None
        self.cost_template_override = None
        if isinstance(bom_vars, dict):
            self.accessory_set_code = bom_vars.get(
                "_accessory_set") or bom_vars.get("accessory_set")
            self.glass_master_override = bom_vars.get("glass_master")
            # V6 P10: kính theo VỊ TRÍ (dialog "Kính theo vị trí" — Q1a đã lưu
            # {rep: mã_kính_đã_chọn}, rep = default_glass_master gốc của nhóm).
            # Trước bản vá này, engine chưa từng đọc key này → đổi kính đa vị
            # trí ở dialog KHÔNG có tác dụng thật, chỉ có mã global (1 kính
            # cho toàn BOM) hoạt động.
            gm_map = bom_vars.get("glass_master_map")
            if isinstance(gm_map, dict):
                self.glass_master_map = gm_map
            self.profile_system_override = bom_vars.get("_profile_system")
            self.cost_template_override = bom_vars.get("_cost_template")

        # ── 1.5c (V6 P4): override profile_system — resolve lại system vars
        #     từ profile system đã chọn. `_resolve_fb_context()` ở 1.4 dùng
        #     profile mặc định của Bom Set (scope AL Bom Set) → ghi đè giá trị
        #     vừa resolve ở 1.3. Áp lại khi có override (OPT-IN — không có
        #     override → giữ nguyên hành vi cũ).
        if self.profile_system_override:
            self._resolve_system_variables()

        # ── 1.6 Fallback default cho user variables (is_system=0) ─────
        # Variable Library có default_value (vd installation_height_m="3").
        # Quotation không truyền → lấy default, để cost template resolve
        # RULE-HEIGHT-MULT thay vì NameError → NC_LD=0.
        self._resolve_user_variable_defaults()

        # ── 1.7 (V6 P7 — Phase 0b): chuẩn hoá biến phần trăm ─────────
        # System var phần trăm lưu PHẦN TRĂM NGUYÊN (8/12/16/3/3/10) → chia
        # 100 → 0.08 trước khi dùng trong công thức. Golden-safe: 8/100=0.08
        # không đổi giá trị đầu vào cost template. Chạy SAU CÙNG (sau FB merge
        # + user vars) để cover mọi nguồn resolve.
        self._normalize_percent_inputs()

    def _normalize_percent_inputs(self):
        """Chuẩn hoá biến phần trăm: phần trăm nguyên (8) → decimal (0.08).

        An toàn mixed-data: value ≤ 1 (đã là decimal, data chưa migrate) → giữ
        nguyên; value > 1 (phần trăm nguyên) → chia 100. Idempotent — chạy lại
        không nhân đôi.
        """
        for key in list(self.inputs.keys()):
            if not key.endswith(_PERCENT_VAR_SUFFIXES):
                continue
            val = self.inputs[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                continue
            if abs(val) > 1:
                self.inputs[key] = val / 100.0

    def _resolve_user_variable_defaults(self):
        """B1 FB-max: fallback default cho user variables (is_system=0).

        Chỉ áp dụng cho biến CHƯA có giá trị trong inputs (user bom_vars
        đã nhập → giữ nguyên). Default từ AL Variable Library.default_value.
        """
        try:
            user_vars = frappe.get_all(
                "AL Variable Library",
                filters={"is_system": 0},
                fields=["var_name", "default_value"],
            ) or []
        except Exception:
            return
        for uv in user_vars:
            name = uv.get("var_name")
            if not name or name in self.inputs:
                continue
            dv = uv.get("default_value")
            if dv is None or str(dv).strip() == "":
                continue
            try:
                self.inputs[name] = float(dv)
            except (ValueError, TypeError):
                self.inputs[name] = dv

    def _resolve_system_variables(self):
        """DATA-DRIVEN: Đọc system variables từ AL Variable Library.

        Với mỗi system variable có source_doctype + source_field,
        tự động resolve giá trị. Thêm 1 system var mới = 1 record Library.
        """
        system_vars = frappe.get_all("AL Variable Library",
                                      filters={"is_system": 1},
                                      fields=["var_name", "source_doctype",
                                              "source_field", "default_value"])

        # Gom các var theo source_doctype để batch query
        by_doctype = defaultdict(list)
        for sv in system_vars:
            if sv.get("source_doctype") and sv.get("source_field"):
                by_doctype[sv["source_doctype"]].append(sv)

        # Cần biết tên record cụ thể để query
        bom_set = self._get_bom_set()
        if not bom_set:
            return

        # Map: doctype → record name
        # V6 P4: `_profile_system` override (từ al_bom_vars) ưu tiên hơn
        # profile system mặc định của Bom Set. OPT-IN — không có override
        # → giữ nguyên hành vi cũ.
        source_records = {
            "AL Profile System": self.profile_system_override or bom_set.get(
                "profile_system"),
            "AL Product Type": bom_set.get("product_type"),
        }

        # Resolve từng source doctype
        for doctype, vars_list in by_doctype.items():
            record_name = source_records.get(doctype)
            if not record_name:
                continue
            try:
                doc = frappe.get_cached_doc(doctype, record_name)
                for sv in vars_list:
                    val = doc.get(sv["source_field"])
                    if val is not None:
                        self.inputs[sv["var_name"]] = val
            except frappe.DoesNotExistError:
                pass

        # V6 P5 (Phase 1c): AL Profile System child table `system_variables`
        # ưu tiên hơn offset_* cứng (source_field) và default_value.
        # Mỗi row: variable (Link → AL Variable Library), value (Data), is_active.
        # Đã có value → ghi đè giá trị vừa resolve từ source_field. Value chuỗi
        # → parse số khi được, giữ nguyên nếu là công thức/ký tự.
        # Lưu thêm self._profile_child_vars để b1_gather_inputs áp lại SAU FB
        # binding (FB đọc offset_* field — child table phải thắng).
        self._profile_child_vars = {}
        profile_name = source_records.get("AL Profile System")
        if profile_name:
            try:
                profile_doc = frappe.get_cached_doc("AL Profile System", profile_name)
                for row in profile_doc.get("system_variables") or []:
                    if not row.get("is_active"):
                        continue
                    var_name = row.get("variable")
                    val = row.get("value")
                    if not var_name or val is None or str(val).strip() == "":
                        continue
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                    self.inputs[var_name] = val
                    self._profile_child_vars[var_name] = val
            except frappe.DoesNotExistError:
                pass

        # Fallback: system vars không có source_doctype hoặc không resolve được
        # → dùng default_value từ Variable Library
        for sv in system_vars:
            if sv["var_name"] not in self.inputs and sv.get("default_value"):
                try:
                    self.inputs[sv["var_name"]] = float(sv["default_value"])
                except (ValueError, TypeError):
                    self.inputs[sv["var_name"]] = sv["default_value"]

        # Fallback cuối: AL Calculation Rule CONSTANT (cho backward compat)
        for sv in system_vars:
            if sv["var_name"] not in self.inputs or self.inputs[sv["var_name"]] in (0, ""):
                fallback_code = sv["var_name"].replace("_", "-")
                try:
                    rule = frappe.get_cached_doc(
                        "AL Calculation Rule", fallback_code)
                    if rule.rule_type == "CONSTANT":
                        self.inputs[sv["var_name"]] = rule.constant_value or 0
                except frappe.DoesNotExistError:
                    pass

    def _resolve_fb_context(self):
        """B1 FB-max: resolve global binding + system var qua FB get_live_context.

        Scope context = {"current_doctype": <doctype>, "current_docname": <name>}
        — đúng chữ ký formula_builder.api.formula_builder.get_live_context.

        Scope ưu tiên "AL Bom Set" (khi có bom_set) để system-variable FVB (D3,
        source_type=linked_doctype_field, link_field=profile_system/product_type)
        resolve được từ AL Profile System / AL Product Type. Nếu không có Bom Set
        → fallback scope "Quotation Item" (hành vi cũ, an toàn).

        Trả về {var_name: value} từ danh sách variables (FB đã topological-sort
        + fallback default_value). Khi FVB chưa seed (D3) → get_live_context trả
        rất ít binding → dict rỗng/gần rỗng → caller giữ resolver cũ (1.3).

        Quan trọng (golden-safe): bỏ qua None, dict/list VÀ chuỗi rỗng. Nếu một
        binding resolve lỗi → default_value rỗng → "" KHÔNG được merge, để
        resolver 1.3 (Variable Library) giữ giá trị thật (vd OFFSET_FRAME=48).
        """
        try:
            from formula_builder.api.formula_builder import get_live_context
        except Exception:
            return {}
        # Scope: AL Bom Set khi có (system var FVB cần doc có link profile_system)
        scope_doctype = "Quotation Item"
        scope_docname = self.quotation_item_name
        try:
            bom_set = self._get_bom_set()
            if bom_set and getattr(bom_set, "name", None):
                scope_doctype = "AL Bom Set"
                scope_docname = bom_set.name
        except Exception:
            pass  # không resolve được Bom Set → giữ scope cũ, an toàn
        try:
            scope_json = json.dumps({
                "current_doctype": scope_doctype,
                "current_docname": scope_docname,
            })
            ctx = get_live_context(scope_json)
        except Exception:
            return {}
        if not ctx or not ctx.get("success"):
            return {}
        out = {}
        for v in ctx.get("variables") or []:
            name = v.get("name", "")
            val = v.get("value")
            if not name or val is None:
                continue
            # Chỉ merge giá trị scalar — Object (whole_doctype) không vào inputs
            if isinstance(val, (dict, list)):
                continue
            # Golden-safe: chuỗi rỗng cũng không merge (vd FVB default_value "")
            if isinstance(val, str) and not val.strip():
                continue
            # Coerce value từ BINDING (source != "field") về float nếu là số:
            # linked_doctype_field trả Decimal/numeric-string từ DB → để nguyên
            # sẽ TypeError khi arithmetic (vd NC_SX_PCT * TONG_VL). Doc field
            # (source="field") giữ nguyên type gốc, không coerce.
            if v.get("source") != "field" and not isinstance(val, (int, float)):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
            out[name] = val
        return out

    def _get_bom_set(self):
        """Lấy Bom Set doc (cached)."""
        if not self.bom_version or not self.bom_version.bom:
            return None
        if not self._bom_doc:
            try:
                self._bom_doc = frappe.get_cached_doc(
                    "AL BOM", self.bom_version.bom)
            except frappe.DoesNotExistError:
                return None
        if self._bom_doc.bom_set:
            try:
                return frappe.get_cached_doc("AL Bom Set", self._bom_doc.bom_set)
            except frappe.DoesNotExistError:
                pass
        return None

    def _load_accessories(self, bom_set):
        """B2 FB-max: nạp phụ kiện (VL_PK) từ AL Accessory Set.

        Bộ phụ kiện: bom_vars.accessory_set (ưu tiên) → Bom Set.default_accessory_set.
        Accessory items append vào bom_items như row COUNT — b3/b4/b5 xử lý
        giống Bom Item thường (qty_formula resolve qua FormulaEngine, lookup_rule
        đã có trong safe_funcs). Golden CDMQ-2C kỳ vọng VL_PK = tay_nam + khoa
        + ban_le ≈ 1,640,000 (bước engine v28.7 THIẾU sau 7-phase rewrite).
        """
        acc_code = self.accessory_set_code
        if not acc_code and bom_set:
            acc_code = bom_set.get("default_accessory_set")
        if not acc_code:
            return
        try:
            acc_doc = frappe.get_cached_doc("AL Accessory Set", acc_code)
        except frappe.DoesNotExistError:
            return
        for acc in (acc_doc.get("items") or []):
            slug = acc.get("slug", "")
            if not slug:
                continue
            qty_formula = str(acc.get("qty_formula") or "").strip()
            self.bom_items.append({
                "slug": slug,
                "item_code": acc.get("item_code", ""),
                "price_base_item": "",
                "qty": qty_formula if qty_formula else (acc.get("qty") or 1),
                "unit_price": acc.get("unit_price"),
                # V6 P10: cho phép override per-accessory (field mới trên
                # AL Accessory Item) — bỏ trống = mặc định COUNT/VL_PK
                # (100% backward-compat với record cũ).
                "calc_pattern": acc.get("calc_pattern") or "COUNT",
                "cost_bucket": acc.get("cost_bucket") or "VL_PK",
                "category": "",
                "default_glass_master": "",
                "item_selection_mode": "",
                "item_rule": "",
                "show_condition": "",
                "width": "",
                "height": "",
            })

    # ══════════════════════════════════════════════════════════════════
    # B2: Pre-fetch Master Data — batch query từ DB
    # ══════════════════════════════════════════════════════════════════
    def b2_prefetch_master_data(self):
        if not self.bom_version or not self.bom_version.bom_set_snapshot:
            frappe.throw("BOM Version không có snapshot")

        snap = json.loads(self.bom_version.bom_set_snapshot) if isinstance(
            self.bom_version.bom_set_snapshot, str
        ) else self.bom_version.bom_set_snapshot
        self.bom_items = snap.get("items", [])

        # ── B2 FB-max: nạp phụ kiện (VL_PK) từ AL Accessory Set ──────
        # Phải nạp TRƯỚC vòng gom codes để item_code của phụ kiện được
        # batch query weight + Item Price (KL-MZS20/KL-KHOA-01/KL-T-MJ06).
        bom_set = self._get_bom_set()
        self._load_accessories(bom_set)

        # ── Gom tất cả codes để batch query ──────────────────────────
        item_codes = []
        price_base_items = []
        glass_master_codes = []
        rule_codes = []

        for item in self.bom_items:
            ic = item.get("item_code")
            if ic:
                item_codes.append(ic)
            pbi = item.get("price_base_item")
            if pbi:
                price_base_items.append(pbi)
            gm = item.get("default_glass_master")
            if gm:
                glass_master_codes.append(gm)
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_codes.append(item["item_rule"])

        # V6 P10: thêm TẤT CẢ mã kính override (per vị trí + global) vào
        # batch query weight + price.
        if self.glass_master_map:
            item_codes.extend(self.glass_master_map.values())
        if self.glass_master_override:
            item_codes.append(self.glass_master_override)

        # ── Batch query #1: Item weights ─────────────────────────────
        weights = {}
        if item_codes:
            for it in frappe.get_all("Item",
                                      filters={"name": ("in", item_codes)},
                                      fields=["name", "weight_per_unit"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)

        # ── Batch query #2: Item Prices (composite-key aware) ────────
        # Lưu ý: 1 item_code có thể có NHIỀU dòng Item Price (khác màu/
        # xuất xứ/độ dày/bề mặt) — phải match đúng theo composite key
        # hiện tại (self.inputs), không được ghi đè tùy tiện theo thứ tự DB.
        all_price_items = list(set(item_codes + price_base_items))
        # ── B2 FB-max: thử resolve composite price qua FB binding
        #    (composite_key_lookup / aluminum_price_composite). Nếu chưa có
        #    binding nào cấu hình → None → fallback resolver cũ.
        prices = self._fetch_composite_prices_via_fb(all_price_items)
        if prices is None:
            prices = self._fetch_composite_prices(all_price_items)

        # ── Batch query #3: Glass Masters (B3 fix: 1 query thay vì N+1) ──
        # V6 P10: thêm TẤT CẢ mã kính override (per vị trí + global) vào
        # danh sách fetch.
        gm_fetch = set(glass_master_codes)
        gm_fetch |= set(self.glass_master_map.values())
        if self.glass_master_override:
            gm_fetch.add(self.glass_master_override)
        gm_fetch = list(gm_fetch)
        glass_masters = {}
        if gm_fetch:
            for gm in frappe.get_all("AL Glass Master",
                                      filters={"name": ("in", gm_fetch)},
                                      fields=["name", "total_thick_mm", "glass_type"]):
                glass_masters[gm["name"]] = {
                    "glass_thick": gm.get("total_thick_mm", 0),
                    "glass_type": gm.get("glass_type", ""),
                }

        # ── Batch query #4: Material Categories (scrap_pct + has_weight) ──
        # V6 P8 (Phase 1e): `has_weight` (NHÔM/THÉP/INOX = 1) cho renderer
        # cột Trọng lượng (chỉ hiện khi has_weight + weight_per_unit > 0).
        material_categories = {}
        cat_codes = list({item.get("category", "") for item in self.bom_items if item.get("category")})
        if cat_codes:
            for mc in frappe.get_all("AL Material Category",
                                      filters={"name": ("in", cat_codes)},
                                      fields=["name", "default_scrap_pct", "has_weight"]):
                material_categories[mc["name"]] = {
                    "scrap_pct": mc.get("default_scrap_pct", 0) or 0,
                    "has_weight": 1 if mc.get("has_weight") else 0,
                }

        # ── Pre-build glass_data cho rule resolution ──────────────
        # (phải build TRƯỚC khi resolve rules vì rule_input_expr
        #  tham chiếu glass_thick/glass_type từ glass master)
        # V6 P10: kính override resolve theo TỪNG vị trí (glass_master_map)
        # trước, global (glass_master_override) sau → nep/keo rule resolve
        # đúng độ dày kính của TỪNG vị trí đã đổi trong dialog, không còn bị
        # 1 mã global đè lên toàn bộ BOM.
        glass_data = {}
        for item in self.bom_items:
            slug = item.get("slug", "")
            gm_code = item.get("default_glass_master", "")
            resolved_gm = self._resolve_glass_override(gm_code) if gm_code else gm_code
            if resolved_gm and resolved_gm in glass_masters:
                glass_data[slug] = glass_masters[resolved_gm]
            else:
                glass_data[slug] = {"glass_thick": 0, "glass_type": ""}

        # ── Batch query #5: Dynamic Item Rules (NOW AFTER glass_data) ──
        resolved_items = {}
        resolved_item_names = {}
        for rule_code in set(rule_codes):
            rule_input = self._resolve_rule_input_for_code(rule_code, glass_data)
            if rule_input is not None and rule_input != "":
                resolved = self._resolve_dynamic_item(rule_code, rule_input)
                if resolved:
                    resolved_items[rule_code] = resolved
                    resolved_item_names[resolved] = True

        # ── Batch query #6: Resolved Item weights + prices ─────────
        if resolved_item_names:
            for it in frappe.get_all("Item",
                                      filters={"name": ("in", list(resolved_item_names))},
                                      fields=["name", "weight_per_unit"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)
            for ip in frappe.get_all("Item Price",
                                      filters={"item_code": ("in", list(resolved_item_names)),
                                               "price_list": _default_price_list()},
                                      fields=["item_code", "price_list_rate"]):
                prices[ip["item_code"]] = ip["price_list_rate"]

        # ── Build row_literals ───────────────────────────────────────
        for item in self.bom_items:
            slug = item.get("slug", "")
            ic = item.get("item_code", "")
            pbi = item.get("price_base_item", "")
            # V6 P10: line kính dùng mã kính đã resolve theo vị trí (hoặc
            # global) — giá tra theo Item Price của mã này (có composite key
            # nếu đã cấu hình Pricing Dimension cho category kính).
            gm_code = item.get("default_glass_master", "")
            if gm_code:
                resolved_gm = self._resolve_glass_override(gm_code)
                if resolved_gm in glass_masters:
                    ic = resolved_gm

            gd = glass_data.get(slug, {})
            _mc = material_categories.get(item.get("category", ""), {}) or {}
            lit = {
                "weight_per_unit": weights.get(ic, 0) if ic else 0,
                "unit_price": (prices.get(pbi, 0) if pbi
                               else (prices.get(ic, 0) if ic else 0)),
                "calc_pattern": item.get("calc_pattern", ""),
                "glass_thick": gd.get("glass_thick", 0),
                "glass_type": gd.get("glass_type", ""),
                "item_code": ic,
                "scrap_pct": _mc.get("scrap_pct", 0),
                # V6 P8 (Phase 1e): has_weight (NHÔM/THÉP/INOX) → renderer
                # cột Trọng lượng. Rule-resolve item giữ category gốc.
                "has_weight": _mc.get("has_weight", 0),
            }

            # Dynamic Item Rule resolution (glass_thick/type đã có từ glass_data)
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_code = item["item_rule"]
                resolved = resolved_items.get(rule_code)
                if resolved:
                    lit["item_code"] = resolved
                    lit["unit_price"] = prices.get(resolved, 0)
                    lit["weight_per_unit"] = weights.get(resolved, 0)

            # B2 FB-max: Accessory Item có thể ghi đè unit_price trực tiếp
            # (không cần Item Price). Row phụ kiện chỉ có slug/item_code/qty/
            # qty_formula/unit_price → ghi đè khi giá trị dương.
            if item.get("unit_price") not in (None, "", 0):
                lit["unit_price"] = item["unit_price"]

            self.row_literals[slug] = lit

        # ── Lưu formula_fieldnames từ Bom Set config ─────────────────
        bom_set = self._get_bom_set()
        if bom_set and bom_set.get("formula_fieldnames"):
            try:
                self._formula_fieldnames = json.loads(
                    bom_set.formula_fieldnames) if isinstance(
                    bom_set.formula_fieldnames, str
                ) else bom_set.formula_fieldnames
            except json.JSONDecodeError:
                self._formula_fieldnames = None

    def _get_dim_fieldnames(self):
        """Map variable_name -> custom_fieldname trên Item Price.

        P1 (versioning): ƯU TIÊN đọc từ `pricing_dimension_snapshot` trên
        BOM Version (immutable, chụp tại lúc publish) — để báo giá tái lập
        được kể cả khi ai đó sửa Pricing Dimension / multiplier sau đó.
        Chỉ fallback query LIVE khi snapshot rỗng (BOM Version cũ chưa backfill).
        Giữ nguyên cấu trúc trả về {variable_name: custom_fieldname}.
        """
        if self._dim_fieldname_cache is not None:
            return self._dim_fieldname_cache

        snapshot_raw = getattr(self.bom_version, "pricing_dimension_snapshot", None)
        if snapshot_raw:
            try:
                data = json.loads(snapshot_raw) if isinstance(
                    snapshot_raw, str) else snapshot_raw
                dims = {
                    d.get("dimension_code"): d.get("custom_fieldname")
                    for d in data.get("dimensions", [])
                }
                result = {
                    m.get("variable_name"): dims.get(m.get("pricing_dimension"))
                    for m in data.get("mappings", [])
                    if dims.get(m.get("pricing_dimension"))
                }
                self._dim_fieldname_cache = result
                return result
            except (ValueError, TypeError) as exc:
                frappe.log_error(
                    title="AlumGlass: pricing_dimension_snapshot parse lỗi",
                    message="BOM Version: %s — %s" % (
                        getattr(self.bom_version, "name", "?"), exc),
                )
                # rơi xuống fallback live bên dưới

        # FALLBACK — chỉ cho BOM Version cũ chưa backfill (P1)
        frappe.logger("alumglass").warning(
            "BOM Version %s không có pricing_dimension_snapshot — dùng config "
            "Pricing Dimension LIVE (không immutable). Nên backfill hoặc "
            "re-publish để báo giá tái lập được."
            % getattr(self.bom_version, "name", "?")
        )
        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            fields=["variable_name", "pricing_dimension"])
        dim_codes = list({m["pricing_dimension"] for m in mappings})
        dims = {}
        if dim_codes:
            for d in frappe.get_all(
                "AL Pricing Dimension",
                filters={"name": ("in", dim_codes)},
                fields=["name", "custom_fieldname"]):
                dims[d["name"]] = d["custom_fieldname"]

        self._dim_fieldname_cache = {
            m["variable_name"]: dims.get(m["pricing_dimension"])
            for m in mappings if dims.get(m["pricing_dimension"])
        }
        return self._dim_fieldname_cache

    def _get_dim_mappings_raw(self):
        """Mapping + dimension THÔ (chưa lọc material_category).

        Ưu tiên đọc snapshot bất biến (giống _get_dim_fieldnames()). Snapshot
        CŨ (trước bản vá V6 P10 — chưa có `material_category` trong mappings)
        sẽ khiến _dim_fieldnames_for_category() trả {} cho category cụ thể
        (an toàn: rơi về giá dòng "trần", KHÔNG throw) — nên re-publish/
        backfill BOM Version cũ để lọc category hoạt động đầy đủ.
        """
        if self._dim_mapping_raw_cache is not None:
            return self._dim_mapping_raw_cache

        snapshot_raw = getattr(self.bom_version, "pricing_dimension_snapshot", None)
        if snapshot_raw:
            try:
                data = json.loads(snapshot_raw) if isinstance(
                    snapshot_raw, str) else snapshot_raw
                dims = {
                    d.get("dimension_code"): d.get("custom_fieldname")
                    for d in data.get("dimensions", [])
                }
                mappings = data.get("mappings", [])
                self._dim_mapping_raw_cache = (mappings, dims)
                return self._dim_mapping_raw_cache
            except (ValueError, TypeError) as exc:
                frappe.log_error(
                    title="AlumGlass: pricing_dimension_snapshot parse lỗi (raw)",
                    message="BOM Version: %s — %s" % (
                        getattr(self.bom_version, "name", "?"), exc),
                )

        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            fields=["variable_name", "pricing_dimension", "material_category"])
        dim_codes = list({m["pricing_dimension"] for m in mappings})
        dims = {}
        if dim_codes:
            for d in frappe.get_all(
                "AL Pricing Dimension",
                filters={"name": ("in", dim_codes)},
                fields=["name", "custom_fieldname"]):
                dims[d["name"]] = d["custom_fieldname"]
        self._dim_mapping_raw_cache = (mappings, dims)
        return self._dim_mapping_raw_cache

    def _dim_fieldnames_for_category(self, category):
        """Lọc mapping theo material_category của ĐÚNG dòng BOM đang tra —
        đồng bộ hệt fb_handlers.aluminum_price_composite, để nhôm, kính, hay
        category thêm sau này đều xử lý theo 1 quy tắc duy nhất, không
        hardcode tên category nào.

        category rỗng → không lọc (giữ hành vi legacy cho dòng BOM chưa gán
        category, tương thích golden test cũ).
        """
        mappings, dims = self._get_dim_mappings_raw()
        if not category:
            return {
                m.get("variable_name"): dims.get(m.get("pricing_dimension"))
                for m in mappings if dims.get(m.get("pricing_dimension"))
            }
        return {
            m.get("variable_name"): dims.get(m.get("pricing_dimension"))
            for m in mappings
            if m.get("material_category") == category
            and dims.get(m.get("pricing_dimension"))
        }

    # B2 FB-max: source types có khả năng resolve composite price.
    _PRICING_SOURCE_TYPES = ("composite_key_lookup", "aluminum_price_composite")

    def _get_pricing_bindings(self):
        """B2 FB-max: lấy Formula Variable Binding có khả năng resolve giá.

        Filter: is_active + source_type ∈ {composite_key_lookup,
        aluminum_price_composite} + applies_to_doctype ∈ {"", Quotation Item,
        AL Bom Item}. Trả về list binding dict (đúng định dạng
        BatchBindingResolver), hoặc [] nếu chưa có binding nào cấu hình →
        caller fallback resolver cũ (_fetch_composite_prices).
        """
        try:
            return frappe.get_all(
                "Formula Variable Binding",
                filters={
                    "is_active": 1,
                    "source_type": ("in", list(self._PRICING_SOURCE_TYPES)),
                    "applies_to_doctype": ("in", ["", "Quotation Item", "AL Bom Item"]),
                },
                fields=[
                    "name", "variable_name", "variable_label", "source_type",
                    "source_config", "resolve_priority", "applies_to_doctype",
                    "applies_to_field", "is_global", "data_type", "default_value",
                ],
                order_by="resolve_priority asc",
            ) or []
        except Exception:
            return []

    def _fetch_composite_prices_via_fb(self, item_codes):
        """B2 FB-max: resolve composite price qua BatchBindingResolver.

        Với mỗi item_code, build row context (composite key từ self.inputs +
        item_code/price_base_item) và resolve toàn bộ pricing binding qua
        resolve_all_bindings_batch. Handler 'aluminum_price_composite' / source_type
        'composite_key_lookup' đọc composite key từ resolved_so_far.

        Trả về {item_code: price} — hoặc None nếu chưa có binding nào cấu hình
        (caller giữ _fetch_composite_prices cũ làm fallback — bảo toàn golden).
        """
        bindings = self._get_pricing_bindings()
        if not bindings:
            return None
        try:
            from formula_builder.api.batch_binding_resolver import (
                resolve_all_bindings_batch)
        except Exception:
            return None

        prices = {}
        for item_code in item_codes:
            row_ctx = dict(self.inputs)
            row_ctx["item_code"] = item_code
            row_ctx["price_base_item"] = item_code
            row_ctx["row"] = {
                "item_code": item_code,
                "price_base_item": item_code,
            }
            try:
                resolved = resolve_all_bindings_batch(
                    bindings, doc=self._qi_doc, pre_resolved=row_ctx)
            except Exception:
                continue
            # Lấy giá trị đầu tiên khác default rỗng trong các binding đã resolve
            for _var_name, val in resolved.items():
                if isinstance(val, (int, float)) and val:
                    prices[item_code] = float(val)
                    break
        return prices if prices else None

    def _fetch_composite_prices(self, item_codes):
        """Tra Item Price theo composite key, trả về {item_code: price_list_rate}.

        V6 P10: lọc dimension theo material_category của ĐÚNG dòng BOM sở
        hữu item_code/price_base_item đó — áp dụng như nhau cho nhôm, kính,
        hay category thêm sau này (không hardcode). Với mỗi item_code, chọn
        dòng Item Price khớp NHIỀU field composite nhất với self.inputs hiện
        tại. Nếu không dòng nào khớp đủ, fallback về dòng "trần" (không set
        field composite nào) làm giá mặc định.
        """
        if not item_codes:
            return {}

        # item_code/price_base_item -> category của dòng BOM tương ứng
        category_by_code = {}
        for item in self.bom_items:
            cat = item.get("category", "")
            for code_field in ("item_code", "price_base_item"):
                code = item.get(code_field)
                if code and code not in category_by_code:
                    category_by_code[code] = cat

        all_fieldnames = set()
        for code in item_codes:
            fns = self._dim_fieldnames_for_category(category_by_code.get(code, ""))
            all_fieldnames |= set(fns.values())
        price_fields = ["name", "item_code", "price_list_rate"] + list(all_fieldnames)

        rows_by_item = defaultdict(list)
        for ip in frappe.get_all(
            "Item Price",
            filters={"item_code": ("in", item_codes),
                     "price_list": _default_price_list()},
            fields=price_fields,
        ):
            rows_by_item[ip["item_code"]].append(ip)

        prices = {}
        for item_code, rows in rows_by_item.items():
            dim_fieldnames = self._dim_fieldnames_for_category(
                category_by_code.get(item_code, ""))
            prices[item_code] = self._match_composite_price(
                item_code, rows, dim_fieldnames)
        return prices

    def _match_composite_price(self, item_code, rows, dim_fieldnames):
        """Chọn dòng Item Price khớp nhất với composite key hiện tại.

        V6 P10: thuật toán thật nằm ở engine/composite_pricing.best_partial_match
        (dùng chung với fb_handlers.aluminum_price_composite, mode exact_match)
        — hàm này chỉ còn là wrapper giữ nguyên chữ ký cũ cho code/test đang gọi.
        """
        from alumglass.engine.composite_pricing import best_partial_match

        price = best_partial_match(rows, dim_fieldnames, self.inputs)
        if price is not None:
            return price

        frappe.throw(
            f"Không tìm được Item Price khớp cho '{item_code}' với composite "
            f"key hiện tại. Kiểm tra lại bảng giá (Item Price) hoặc thêm 1 "
            f"dòng giá mặc định không gắn dimension nào."
        )

    def _resolve_glass_override(self, rep_code):
        """Trả về mã kính THỰC TẾ dùng để tra giá/thông số cho 1 nhóm đại diện.

        rep_code = giá trị default_glass_master gốc của dòng BOM (chính là
        `rep` mà api.get_bom_meta() dùng để build glass_groups).

        Ưu tiên:
          1. glass_master_map[rep_code] — đổi theo TỪNG vị trí (dialog mới,
             hỗ trợ N kính khác nhau trong 1 BOM).
          2. glass_master_override — mã global cũ (1 kính cho toàn BOM,
             backward-compat khi dialog/BOM chưa có glass_groups).
          3. rep_code — không đổi gì (giữ nguyên hành vi khi user không sửa).
        """
        if not rep_code:
            return rep_code
        if self.glass_master_map:
            mapped = self.glass_master_map.get(rep_code)
            if mapped:
                return mapped
        if self.glass_master_override:
            return self.glass_master_override
        return rep_code

    def _resolve_rule_input_for_code(self, rule_code, glass_data=None):
        """Tìm rule_input phù hợp cho rule_code từ Bom Items.

        Dùng glass_data (pre-computed từ batch query) thay vì row_literals
        vì row_literals chưa được build tại thời điểm gọi hàm này.
        """
        for item in self.bom_items:
            if item.get("item_rule") == rule_code:
                expr = item.get("rule_input_expr", "")
                ref_match = re.match(
                    r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
                if ref_match:
                    ref_slug, ref_field = ref_match.group(
                        1), ref_match.group(2)
                    if glass_data and ref_slug in glass_data:
                        return glass_data[ref_slug].get(ref_field, 0)
                    ref_lit = self.row_literals.get(ref_slug, {})
                    return ref_lit.get(ref_field, 0)
        return None

    def _resolve_rule_input(self, item, lit):
        """Phân giải rule_input_expr: 'items.kinh_tren.glass_thick' → giá trị."""
        expr = item.get("rule_input_expr", "")
        ref_match = re.match(
            r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
        if ref_match:
            ref_slug, ref_field = ref_match.group(1), ref_match.group(2)
            ref_lit = self.row_literals.get(ref_slug, {})
            return ref_lit.get(ref_field, 0)
        return lit.get("glass_thick") if lit.get("glass_thick") else lit.get("glass_type", "")

    def _resolve_dynamic_item(self, rule_code, input_value):
        """Gọi AL Dynamic Item Rule để resolve item_code từ input."""
        from alumglass.al_formula_rules.doctype.al_dynamic_item_rule.al_dynamic_item_rule import resolve_item
        result = resolve_item(rule_code, input_value)
        return result.get("item_code") if result else None

    # ══════════════════════════════════════════════════════════════════
    # B3: Build Formulas — tạo formula list cho FormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b3_build_formulas(self):
        """Build list of {name, formula} dicts cho FormulaEngine.

        Dùng formula_fieldnames từ Bom Set config (data-driven),
        fallback DEFAULT_FORMULA_FIELDS nếu không có config.

        V6 Phase 1d: với line có calc_pattern, đọc `input_vars` (danh sách biến
        phụ) từ AL Quantity Calc Method → resolve giá trị từ (1) input_vars của
        line, (2) biến global user đã nhập, (3) row_literals, (4) default 0 →
        truyền vào lookup_calc_pattern dưới dạng keyword:
        lookup_calc_pattern(code, w, h, tlr, piece_length=...).
        Pattern không có biến phụ → formula giữ nguyên (backward-compat).
        """
        self.bom_formulas = []
        formula_fields = self._formula_fieldnames or DEFAULT_FORMULA_FIELDS

        # ── V6 P5 (Phase 1d): batch-fetch input_vars theo calc_pattern ──
        pattern_codes = list({
            item.get("calc_pattern", "") for item in self.bom_items
            if item.get("calc_pattern")})
        pattern_input_vars = {}
        if pattern_codes:
            for pv in frappe.get_all(
                    "AL Quantity Calc Method",
                    filters={"name": ("in", pattern_codes)},
                    fields=["name", "input_vars"]):
                raw = pv.get("input_vars") or []
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except (ValueError, TypeError):
                        raw = []
                pattern_input_vars[pv["name"]] = (
                    raw if isinstance(raw, list) else [])

        # 3 tham số positional chuẩn của lookup_calc_pattern — không cần extra.
        _POSITIONAL = {"width", "height", "weight_per_unit"}

        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            # Inject literals vào context (bao gồm scrap_pct từ Material Category)
            for key in ("weight_per_unit", "unit_price", "calc_pattern",
                         "glass_thick", "glass_type", "scrap_pct"):
                if key in lit:
                    self.inputs[f"{slug}__{key}"] = lit[key]

            # Pre-set defaults cho các field (tránh NameError trong engine)
            for field in ("width", "height", "qty", "calc_pattern",
                          "weight_per_unit", "unit_price", "scrap_pct"):
                if f"{slug}__{field}" not in self.inputs:
                    self.inputs[f"{slug}__{field}"] = (
                        "" if field == "calc_pattern" else 0)

            # ── V6 P5 (Phase 1d): resolve biến phụ + inject literal ──
            # Formula Builder normalize_formula chuyển MỌI '=' thành '=='
            # → keyword args KHÔNG dùng được trong formula. Truyền extra qua
            # dict literal positional: lookup_calc_pattern(code, w, h, tlr,
            # {'depth': slug__depth}). Dict literal qua SecurityValidator OK.
            extra_items = []
            line_vars = self._parse_line_input_vars(item)
            for v in pattern_input_vars.get(item.get("calc_pattern", ""), []) or []:
                if not isinstance(v, str) or not re.match(
                        r"^[A-Za-z_][A-Za-z0-9_]*$", v):
                    continue
                if v in _POSITIONAL:
                    continue
                # Thứ tự ưu tiên: line input_vars → global user input →
                # row_literals → 0. Value hợp lệ (khác "" ) mới inject; rỗng
                # → 0 (giữ literal để formula không NameError).
                val = line_vars.get(v)
                if val is None or str(val).strip() == "":
                    val = self.inputs.get(v)
                if val is None or str(val).strip() == "":
                    val = lit.get(v, 0)
                if val is None:
                    val = 0
                # JSON field trả string — ép về số khi được (pattern dùng
                # arithmetic); không phải số → giữ nguyên (on_error=default).
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
                self.inputs[f"{slug}__{v}"] = val
                extra_items.append(f"'{v}': {slug}__{v}")

            # Build formulas từ Bom Item fields (DATA-DRIVEN)
            for field in formula_fields:
                expr = item.get(field)
                if expr and str(expr).strip():
                    # B4 FB-max: items.X.Y → items['X']['Y'] bằng
                    # DotToSubscriptTransformer (thay regex thủ công).
                    normalized = self._normalize_items_ref(str(expr))
                    self.bom_formulas.append({
                        "name": f"{slug}__{field}",
                        "formula": normalized,
                    })
                    # V6 P8 (Phase 1e): nhớ formula chuẩn hoá cho trace line vật tư
                    self._line_formulas[slug][field] = normalized

            # Synthetic formulas (luôn được tạo)
            extra_str = (
                ", {" + ", ".join(extra_items) + "}" if extra_items else "")
            self.bom_formulas.append({
                "name": f"{slug}__unit_qty",
                "formula": (f"lookup_calc_pattern("
                            f"{slug}__calc_pattern, "
                            f"{slug}__width, "
                            f"{slug}__height, "
                            f"{slug}__weight_per_unit{extra_str})"),
            })
            self.bom_formulas.append({
                "name": f"{slug}__total_qty",
                "formula": f"{slug}__unit_qty * {slug}__qty",
            })
            self.bom_formulas.append({
                "name": f"{slug}__line_total",
                "formula": f"{slug}__total_qty * {slug}__unit_price",
            })

        # B4 FB-max: inject nested items dict cho DotToSubscriptTransformer.
        # Formula dùng items.X.Y → items['X']['Y'] eval với dict lồng.
        # Mirror toàn bộ flat {slug}__{field} của slug trong bom_items.
        slug_set = {it.get("slug", "") for it in self.bom_items if it.get("slug")}
        nested_items = defaultdict(dict)
        for key, value in self.inputs.items():
            slug, _, field = key.rpartition("__")
            if slug in slug_set and field:
                nested_items[slug][field] = value
        self.inputs["items"] = dict(nested_items)

    def _parse_line_input_vars(self, item):
        """Parse `input_vars` của 1 AL Bom Item (JSON object) → dict.

        Field là JSON → Frappe trả dict hoặc string; string thì parse.
        Không phải dict → {} (engine bỏ qua an toàn).
        """
        raw = item.get("input_vars")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _normalize_items_ref(self, expr):
        """B4 FB-max: chuyển items.X.Y → X__Y bằng normalize_global của FB.

        Cross-reference {table}.{slug}.{field} → {slug}__{field} là normalizer
        CANONICAL của FB (formula_builder/table_formula_builder.py — dùng bởi
        MultiTableFormulaBuilder). FormulaEngine tính trong FLAT namespace
        ({slug}__{field} là formula-result), nên items.kinh_tren.width phải trỏ
        tới kinh_tren__width (đã được DAG tính trước — dependency edge).

        ⚠ KHÔNG dùng DotToSubscriptTransformer ở đây: items.X.Y trong BOM là
        cross-reference tới FORMULA RESULT, KHÔNG phải access nested dict đã
        resolve sẵn. Nếu transform thành items['X']['Y'], engine đọc nested
        items dict chỉ chứa literal (computed field = 0) → nep/keo/gioang ra 0
        → lệch golden test. DotToSubscriptTransformer chỉ đúng khi `items` là
        dict RESOLVE SẴN (không phải trường hợp này).

        normalize_global giữ nguyên hành vi regex cũ (verify: output giống hệt
        trên toàn bộ formula BOM thật, kể cả slug có dấu '-' và subscript form).
        """
        if not expr or "items." not in expr:
            return expr
        try:
            from formula_builder.table_formula_builder import normalize_global
            return normalize_global(expr)
        except Exception:
            # Lạ — fallback regex thủ công giữ nguyên hành vi DB cũ
            return re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)

    # ══════════════════════════════════════════════════════════════════
    # B4: Calculate Bom Items — dùng FormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b4_calculate_bom_items(self):
        from formula_builder.formula_utils.engine_public import FormulaEngine
        from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import lookup_calc_pattern

        engine = FormulaEngine(
            formulas=self.bom_formulas,
            safe_funcs={
                "lookup_calc_pattern": lookup_calc_pattern,
                "lookup_rule": _lookup_rule,
                "roundup": _roundup,
            },
            on_error="default",
            default_value=0,
            deterministic=True,
        )

        result = engine.calculate(dict(self.inputs))
        # B5 FB-max: thu thập lỗi structured — 1 dòng lỗi KHÔNG chết cả BOM.
        # Div-by-zero vẫn fatal (errors.py) → phải chặn ở nguồn data.
        self.bom_engine_errors = engine.last_errors.copy()
        self.inputs.update(result)

        # V6 P8 (Phase 1e): batch-fetch output_unit theo calc_pattern (cho cột
        # ĐVT = output_unit của AL Quantity Calc Method).
        pattern_codes = list({
            item.get("calc_pattern", "") for item in self.bom_items
            if item.get("calc_pattern")})
        pattern_units = {}
        if pattern_codes:
            for pu in frappe.get_all(
                    "AL Quantity Calc Method",
                    filters={"name": ("in", pattern_codes)},
                    fields=["name", "output_unit"]):
                pattern_units[pu["name"]] = pu.get("output_unit", "") or ""

        # Build bom_result
        # V6 P8: ctx = inputs đã merge kết quả → build trace line vật tư
        # (width/height/qty formula → thay biến → kết quả).
        self.bom_result = []
        _trace_ctx = dict(self.inputs)
        for item in self.bom_items:
            slug = item.get("slug", "")
            lit = self.row_literals.get(slug, {})

            # Trace line vật tư (2 tầng — cấp 1): width/height/qty đã tính
            line_trace_parts = []
            for f in ("width", "height", "qty"):
                expr = self._line_formulas.get(slug, {}).get(f)
                val = result.get(f"{slug}__{f}")
                if expr and val is not None:
                    line_trace_parts.append(
                        f"{_build_trace(expr, _trace_ctx)} = {_round_num(val)}")
            line_trace = " | ".join(line_trace_parts)

            self.bom_result.append({
                "slug": slug,
                "item_code": lit.get("item_code", item.get("item_code", "")),
                "width": result.get(f"{slug}__width", 0),
                "height": result.get(f"{slug}__height", 0),
                "qty": result.get(f"{slug}__qty", 0),
                "unit_qty": result.get(f"{slug}__unit_qty", 0),
                "total_qty": result.get(f"{slug}__total_qty", 0),
                "unit_price": lit.get("unit_price", 0),
                "line_total": result.get(f"{slug}__line_total", 0),
                "cost_bucket": item.get("cost_bucket", ""),
                # V6 P8 (Phase 1e): contract renderer — ĐVT + Trọng lượng + trace
                "unit": pattern_units.get(item.get("calc_pattern", ""), ""),
                "weight_per_unit": lit.get("weight_per_unit", 0),
                "has_weight": lit.get("has_weight", 0),
                "trace": line_trace,
            })

    # ══════════════════════════════════════════════════════════════════
    # B5: Aggregate Cost Buckets — gom line_total theo cost_bucket
    # ══════════════════════════════════════════════════════════════════
    def b5_aggregate_cost_buckets(self):
        """Gom line_total theo cost_bucket (đọc từ Bom Item, không hardcode).

        B3 FB-max: LEAF bucket có source_type='aggregate_from_items' + source_config
        hợp lệ → resolve qua FB aggregate_from_items (sum theo key_field giống sumif,
        rows_source='resolved' đọc bom_result). AGGREGATE bucket do B6 tính.
        Fallback: bucket chưa cấu hình source_config → sum Python cũ (bảo toàn
        golden test — seed hiện tại chưa set source_config nên path này là default).

        ⚠ GATING (chưa quyết — báo Elon/Owner): giữ vocabulary Cost Bucket hiện có
        + handler resolve (khuyến nghị). Đổi hẳn sang FVB (bỏ vocab 8) cần Owner duyệt.
        """
        fb_buckets = self._resolve_cost_buckets_via_fb()
        buckets = defaultdict(float)
        for row in self.bom_result:
            bk = row.get("cost_bucket", "")
            if not bk:
                continue
            if bk in fb_buckets:
                # Đã có giá trị FB (aggregate toàn bộ rows) — set 1 lần
                if bk not in buckets:
                    buckets[bk] = fb_buckets[bk]
            else:
                buckets[bk] += row.get("line_total", 0)
        self.buckets = dict(buckets)

    def _resolve_cost_buckets_via_fb(self):
        """B3 FB-max: resolve LEAF Cost Bucket có source_type='aggregate_from_items'
        qua FB aggregate_from_items (rows_source='resolved', rows_var='bom_result').

        CHỈ dùng khi bucket record ĐÃ có source_config hợp lệ — KHÔNG tự suy ra
        default config (tránh đổi semantics golden test). Chưa có config → trả {}.
        """
        bucket_codes = list({
            row.get("cost_bucket", "") for row in self.bom_result if row.get("cost_bucket")})
        if not bucket_codes:
            return {}
        try:
            from formula_builder.api.batch_binding_resolver import (
                resolve_all_bindings_batch)
        except Exception:
            return {}

        # Đọc source_type/source_config từ AL Cost Bucket (vocabulary hiện có)
        try:
            records = frappe.get_all(
                "AL Cost Bucket",
                filters={"bucket_code": ("in", bucket_codes)},
                fields=["bucket_code", "bucket_role", "source_type", "source_config"],
            ) or []
        except Exception:
            return {}

        bindings = []
        for rec in records:
            if rec.get("source_type") != "aggregate_from_items":
                continue
            cfg_raw = rec.get("source_config") or ""
            cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) and cfg_raw.strip() else (
                cfg_raw if isinstance(cfg_raw, dict) else {})
            if not isinstance(cfg, dict) or not cfg:
                continue  # chưa có source_config → fallback sum Python
            binding = {
                "variable_name": rec["bucket_code"],
                "source_type": "aggregate_from_items",
                "source_config": cfg,
                "data_type": "Float",
                "default_value": cfg.get("default_value", 0),
            }
            bindings.append(binding)

        if not bindings:
            return {}

        pre_resolved = dict(self.inputs)
        pre_resolved["rows"] = [
            {k: v for k, v in row.items() if k in ("cost_bucket", "line_total")}
            for row in self.bom_result
        ]
        try:
            resolved = resolve_all_bindings_batch(
                bindings, doc=self._qi_doc, pre_resolved=pre_resolved)
        except Exception:
            return {}
        return {
            name: val for name, val in resolved.items()
            if isinstance(val, (int, float))
        }

    # ══════════════════════════════════════════════════════════════════
    # B6: Calculate Cost Template — dùng FlexibleFormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b6_calculate_cost_template(self):
        # V6 P4: `_cost_template` override (từ al_bom_vars) — dùng snapshot
        # build trực tiếp từ AL Cost Template doc thay vì snapshot của version.
        # OPT-IN — không có override → giữ nguyên hành vi cũ (golden-safe).
        if self.cost_template_override:
            ct = frappe.get_cached_doc(
                "AL Cost Template", self.cost_template_override)
            snap = {
                "template_code": ct.template_code,
                "template_name": ct.template_name,
                "items": [{
                    "line_code": i.line_code,
                    "line_label": i.line_label,
                    "calc_formula": i.calc_formula,
                    "cost_bucket": i.cost_bucket,
                    "is_final_price": i.get("is_final_price", 0),
                } for i in ct.items],
            }
        elif not self.bom_version or not self.bom_version.cost_template_snapshot:
            return
        else:
            snap = json.loads(self.bom_version.cost_template_snapshot) if isinstance(
                self.bom_version.cost_template_snapshot, str
            ) else self.bom_version.cost_template_snapshot

        from formula_builder.flexible_formula_engine import (
            FlexibleFormulaEngine, EngineConfig)

        # Build global_formulas từ Cost Template
        global_formulas = []
        referenced_codes = set()
        for item in snap.get("items", []):
            if item.get("calc_formula", "").strip():
                global_formulas.append({
                    "name": item["line_code"],
                    "formula": item["calc_formula"],
                })
                # B4 fix: Parse formula để tìm bucket codes được reference
                tokens = re.findall(
                    r'\b([A-Z][A-Z0-9_]{1,30})\b', item["calc_formula"])
                referenced_codes.update(t for t in tokens if not t.startswith(
                    ("TONG_", "GIA_", "PROFIT", "VAT", "DON_GIA")))

        # Build extra_context: bucket values + global vars
        extra_context = dict(self.inputs)
        extra_context.update(self.buckets)

        # B4 fix: Chỉ set default 0 cho bucket codes được reference
        # (không load toàn bộ bảng AL Cost Bucket)
        for code in referenced_codes:
            if code not in extra_context:
                extra_context[code] = 0.0

        # Tính qua FlexibleFormulaEngine
        # B6 FIX: truyền custom_functions — EngineConfig merge vào safe_funcs
        # của FormulaEngine bên trong. Thiếu nó → lookup_rule() bị
        # [ENGINE.UNKNOWN_FUNCTION] khi cost template seed dùng
        # lookup_rule('RULE-HEIGHT-MULT', installation_height_m) (NC_LD).
        from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import (
            lookup_calc_pattern)
        config = EngineConfig(
            global_formulas=global_formulas,
            extra_context=extra_context,
            on_error="default",
            default_value=0,
            deterministic=True,
            custom_functions={
                "lookup_calc_pattern": lookup_calc_pattern,
                "lookup_rule": _lookup_rule,
                "roundup": _roundup,
            },
        )
        engine = FlexibleFormulaEngine(config)
        result = engine.calculate(dict(self.inputs))

        values = result.values if hasattr(result, 'values') else dict(result)
        self.cost_result = dict(values)
        self.gia_vat = self.cost_result.get("GIA_VAT", 0)
        # B5 FB-max: lỗi structured từ cost template — lưu trong al_bom_result.
        self.cost_engine_errors = dict(result.errors) if hasattr(result, 'errors') else {}

        # V6 P8 (Phase 1e): trace diễn giải (2 tầng — cấp 2) — build TẠI LÚC
        # TÍNH với ctx đầy đủ (inputs + buckets + giá trị cost template) → lưu
        # theo line_code. Renderer hiện "8% × TONG_VL(1,000,000) = 80,000"
        # (JS định dạng % + dấu phẩy). Data cũ không có → fallback build ở
        # get_result_display.
        self.cost_template_trace = {}
        _trace_ctx = dict(extra_context)
        _trace_ctx.update(values)
        for item in snap.get("items", []):
            code = item.get("line_code", "")
            formula = item.get("calc_formula", "")
            if code and formula:
                self.cost_template_trace[code] = _build_trace(formula, _trace_ctx)

    # ══════════════════════════════════════════════════════════════════
    # B7: Save Results — SINGLE commit (B1 fix)
    # ══════════════════════════════════════════════════════════════════
    def b7_save_results(self):
        # Ghi TOÀN BỘ kết quả vào JSON (linh hoạt, mọi bucket đều lưu được)
        # B5 FB-max: errors structured (B4/B6) đi kèm — 1 dòng lỗi không chết cả BOM.
        full_result = {
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            # V6 P8: trace diễn giải cost template (line_code → trace) — lưu
            # kèm để get_result_display không phải re-resolve biến hệ thống.
            "cost_template_trace": self.cost_template_trace,
            "lines": self.bom_result,
            "gia_vat": self.gia_vat,
            "errors": {
                "bom_items": self.bom_engine_errors,
                "cost_template": self.cost_engine_errors,
            },
        }
        result_json = json.dumps(full_result, indent=2, default=str)

        # V5 (Owner): ConfigSnapshot CHỈ tạo khi submit Quotation (doc_events on_submit),
        # KHÔNG tạo mỗi lần tính toán. Đây là scope được Owner cho phép chạm engine —
        # chỉ bỏ phần ghi snapshot, KHÔNG đụng logic tính (B1-B5, cost engine, golden 2C/4C).
        # Ghi kết quả vào Quotation Item (1 lần set_value gộp multi-field)
        frappe.db.set_value("Quotation Item", self.quotation_item_name, {
            "al_gia_vat": self.gia_vat,
            "al_gia_ban": self.cost_result.get("GIA_BAN", 0),
            "al_bom_result": result_json,
        })

        # B1 fix: 1 commit duy nhất
        frappe.db.commit()

    # ── Response builder — trả về TOÀN BỘ cost_result ────────────────
    def _build_response(self):
        """Trả về toàn bộ kết quả. Client tự chọn key cần hiển thị."""
        return {
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            "lines": self.bom_result,
        }
